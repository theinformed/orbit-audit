#!/usr/bin/env python3
"""Measure ONE bounded sweep mode per fresh process; no release/cache writes.

Run cpu, gpu and verify separately with identical arguments, then compare input
and result digests. A connection-local TEMP VIEW limits the historical window;
the real sweep reader, detector and accumulator run unchanged. CPU uses one
reader, matching the GPU lane; this is not a default worker-pool latency test.
--dry-run lists the exact population without CUDA or arithmetic. The only
writer is stdout/stderr (operator-owned receipts); no extracts are retained.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sqlite3
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import orbit_campaigns as oc
from pipeline.orbit_events import load_catalog
from pipeline.orbit_release import DEFAULT_SELF_HISTORY_KAPPA
from tools.benchmark_orbit_sweep import canonical
from tools.verify_orbit_sweep_gpu import epoch, select


def cpu_seconds():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + children.ru_utime + children.ru_stime


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("cpu", "gpu", "verify"), required=True)
    p.add_argument("--archive", type=Path, default=oc.archive_db_path())
    p.add_argument("--start", type=epoch, default=epoch("2024-01-01"))
    p.add_argument("--end", type=epoch, default=epoch("2026-09-01"))
    p.add_argument("--objects", type=int, default=1000)
    p.add_argument("--only", type=int, nargs="+")
    p.add_argument("--seed", type=int, default=20260912)
    p.add_argument("--min-rows", type=int, default=300)
    p.add_argument("--max-rows", type=int, default=5_000_000)
    p.add_argument("--device", type=int, default=1)
    p.add_argument("--ceiling-mib", type=int, default=512)
    p.add_argument("--timeout-seconds", type=float, default=600)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if (not 1 <= args.objects <= 2000 or not 9 <= args.min_rows <= 50000
            or not 1 <= args.max_rows <= 10_000_000 or args.start >= args.end
            or not 0 < args.timeout_seconds <= 1800 or (args.only and len(args.only) > 2000)
            or args.device < 0 or not 320 <= args.ceiling_mib <= 1335):
        p.error("requires <=2000 objects, <=10M rows, <=1800s, valid window/device/ceiling")
    if not args.archive.is_file() or str(args.archive.resolve()).startswith("/mnt/"):
        p.error("requires an existing SSD archive")
    started = time.perf_counter()
    db = sqlite3.connect(f"file:{args.archive}?mode=ro", uri=True, timeout=10)
    db.set_progress_handler(lambda: int(time.perf_counter() - started > args.timeout_seconds), 10000)
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
            raise RuntimeError("requires SSD/WAL archive")
        selected, expected_rows = select(db, args)
        members = [n for n, *_ in selected]
        base = dict(mode=args.mode, archive=str(args.archive), startMs=args.start, endMs=args.end,
                    objects=len(selected), selectedRows=expected_rows, seed=args.seed,
                    kappa=DEFAULT_SELF_HISTORY_KAPPA, elements=oc.ELEMENTS,
                    detectorFlags=oc.detector_flags(), cpuReaders=1,
                    nice=os.getpriority(os.PRIO_PROCESS, 0),
                    populationSha256=hashlib.sha256(json.dumps(selected).encode()).hexdigest())
        if args.dry_run:
            print(json.dumps({**base, "selection": selected}))
            return 0
        # Values are parsed integers. No data table or persistent schema is modified.
        db.execute(f"CREATE TEMP VIEW element_set AS SELECT * FROM main.element_set "
                   f"WHERE epoch_ms >= {args.start} AND epoch_ms < {args.end}")
        db.execute("PRAGMA query_only=1")
        catalog = load_catalog(ROOT / "public/data")
        digest, counts = hashlib.sha256(), {n: count for n, count, *_ in selected}
        stream = oc.stream_object_rows
        detect = oc.detect_object_events
        measured_intervals = 0

        def measured_detect(data, **kw):
            nonlocal measured_intervals
            measured_intervals += len(data)
            return detect(data, **kw)

        def measured_stream(*a, **kw):
            for n, rows in stream(*a, **kw):
                if time.perf_counter() - started > args.timeout_seconds:
                    raise TimeoutError("bounded measurement deadline exceeded")
                if n not in counts or len(rows) != counts.pop(n):
                    raise RuntimeError("archive population changed; cannot shrink the slice")
                digest.update(json.dumps([n, rows], separators=(",", ":")).encode())
                yield n, rows

        options = {} if args.mode == "cpu" else {
            "gpu_devices" if args.mode == "gpu" else "gpu_verify_devices": (args.device,),
            "gpu_ceiling_mib": args.ceiling_mib}
        wall, cpu = time.perf_counter(), cpu_seconds()
        log = io.StringIO()
        try:
            with patch.object(oc, "stream_object_rows", measured_stream), \
                    patch.object(oc, "detect_object_events", measured_detect), contextlib.redirect_stderr(log):
                progress = oc.sweep_archive(db, only=members, workers=1, catalog=catalog,
                                           keep_summaries_for=set(members),
                                           kappa=DEFAULT_SELF_HISTORY_KAPPA, **options)
        finally:
            print(log.getvalue(), file=sys.stderr, end="", flush=True)
        measured_wall, measured_cpu = time.perf_counter() - wall, cpu_seconds() - cpu
        if counts or not progress.complete or progress.objects_this_run != len(members):
            raise RuntimeError("incomplete bounded sweep")
        gpu_report = next((json.loads(line.split(" ", 3)[3]) for line in log.getvalue().splitlines()
                           if line.startswith(("SWEEP GPU EXECUTION {", "SWEEP GPU VERIFICATION {"))), None)
        scan = progress.passed
        result = dict(**base, wallSeconds=measured_wall, cpuCoreMinutes=measured_cpu / 60,
                      scope="real serial sweep including read/decode/input hashing, CUDA startup/cleanup and accumulator; excludes selection, output hashing and release tail",
                      intervals=measured_intervals,
                      inputSha256=digest.hexdigest(),
                      resultSha256=hashlib.sha256(json.dumps(canonical(scan), sort_keys=True).encode()).hexdigest(),
                      gpu=gpu_report)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if args.mode == "cpu" or gpu_report["outcome"] in ("gpu", "agreement") else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
