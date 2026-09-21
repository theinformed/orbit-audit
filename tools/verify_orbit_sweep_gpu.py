#!/usr/bin/env python3
"""Bounded, read-only real-archive GPU verification. JSON receipt to stdout only.

No release builder, checkpoint, shard, network fetch, or persistent cache writer.
--dry-run selects by actual window coverage without initializing CUDA.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import orbit_campaigns as oc
from pipeline import orbit_release as release
from pipeline.orbit_sweep_gpu import Verification


def epoch(value):
    return int(dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def select(db, args):
    """Indexed NORAD+epoch seeks; never a whole element-table date scan."""
    facts = {n: (name, kind) for n, name, kind in db.execute("SELECT norad,name,object_type FROM object")}
    if args.only:
        candidates = list(dict.fromkeys(args.only))
        if len(candidates) != len(args.only):
            raise ValueError("--only contains duplicates")
    else:
        candidates = sorted(facts)
        random.Random(args.seed).shuffle(candidates)
        candidates = candidates[:10000]
    selected, rows = [], 0
    for n in candidates:
        count = db.execute("SELECT count(*) FROM (SELECT 1 FROM element_set WHERE norad=? "
                           "AND epoch_ms>=? AND epoch_ms<? LIMIT 50001)",
                           (n, args.start, args.end)).fetchone()[0]
        if not args.min_rows <= count <= 50000:
            if args.only:
                raise ValueError(f"--only {n} has {count} rows in window; control population cannot shrink")
            continue
        epochs = db.execute("SELECT epoch_ms,mean_motion_q FROM element_set WHERE norad=? "
                            "AND epoch_ms>=? AND epoch_ms<? ORDER BY epoch_ms", (n, args.start, args.end)).fetchall()
        usable = [(a[0] + b[0]) // 2 for a, b in zip(epochs, epochs[1:])
                  if oc.MINIMUM_SPAN_DAYS <= (b[0] - a[0]) / 86400000 <= oc.MAXIMUM_JOINABLE_GAP_DAYS
                  and a[1] > 0 and b[1] > 0]
        covered_blocks = {t // int(oc.BLOCK_DAYS * 86400000) for t in usable}
        if len(usable) < args.min_rows - 1 or len(covered_blocks) < oc.MINIMUM_BASELINE_BLOCKS + 1:
            if args.only:
                raise ValueError(f"--only {n} lacks usable interval/block coverage; cannot shrink controls")
            continue
        if rows + count > args.max_rows:
            raise ValueError("selected population exceeds --max-rows; choose fewer objects/shorter window")
        selected.append((n, count, *facts.get(n, (f"OBJECT {n}", "UNKNOWN"))))
        rows += count
        if not args.only and len(selected) == args.objects:
            break
    expected = len(args.only) if args.only else args.objects
    if len(selected) != expected:
        raise ValueError(f"coverage-qualified population {len(selected)} != requested {expected}")
    return sorted(selected), rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, default=oc.archive_db_path())
    p.add_argument("--start", type=epoch, default=epoch("2024-01-01"))
    p.add_argument("--end", type=epoch, default=epoch("2026-09-01"))
    p.add_argument("--objects", type=int, default=1000)
    p.add_argument("--only", type=int, nargs="+")
    p.add_argument("--min-rows", type=int, default=300)
    p.add_argument("--max-rows", type=int, default=5_000_000)
    p.add_argument("--seed", type=int, default=20260912)
    p.add_argument("--devices", type=int, nargs="+", default=[1])
    p.add_argument("--ceiling-mib", type=int, default=512)
    p.add_argument("--kappa", type=float, default=release.DEFAULT_SELF_HISTORY_KAPPA)
    p.add_argument("--include-raan", action="store_true", help="also verify the currently disabled node channel; no source policy change")
    p.add_argument("--detector-fixes", action="store_true", help="exercise all three optional detector fixes")
    p.add_argument("--timeout-seconds", type=float, default=1200)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if (not 1 <= args.objects <= 2000 or not 9 <= args.min_rows <= 50000
            or not 1 <= args.max_rows <= 10_000_000 or args.start >= args.end
            or not 0 < args.timeout_seconds <= 1800 or (args.only and len(args.only) > 2000)):
        p.error("requires 1..2000 objects, 9..50000 minimum rows, <=10M rows, <=1800s, nonempty window")
    if not args.archive.is_file() or str(args.archive.resolve()).startswith("/mnt/"):
        p.error("requires an existing SSD archive")
    if args.include_raan:
        oc.ELEMENTS = ("semiMajorAxis", "inclination", "eccentricity", "raan")
    if args.detector_fixes:
        for name in oc.detector_flags():
            setattr(oc, name, True)
    started = time.perf_counter()
    db = sqlite3.connect(f"file:{args.archive}?mode=ro", uri=True, timeout=10)
    db.execute("PRAGMA query_only=1")
    db.set_progress_handler(lambda: int(time.perf_counter() - started > args.timeout_seconds), 10000)
    try:
        if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
            raise RuntimeError("bounded verification requires the SSD/WAL archive")
        selected, rows = select(db, args)
        base = dict(archive=str(args.archive), startMs=args.start, endMs=args.end,
                    selectedObjects=len(selected), selectedRows=rows, kappa=args.kappa,
                    elements=oc.ELEMENTS, detectorFlags=oc.detector_flags(),
                    populationSha256=hashlib.sha256(json.dumps(selected).encode()).hexdigest(),
                    seed=args.seed, dryRun=args.dry_run)
        if args.dry_run:
            print(json.dumps({**base, "selection": selected}))
            return 0
        digest, event_digest = hashlib.sha256(), hashlib.sha256()
        kinds, intervals_seen, events_seen, measured_rows = {}, 0, 0, 0
        expectations = oc.Expectations.load()
        compute_wall, compute_cpu = time.perf_counter(), time.process_time()
        with Verification(tuple(args.devices), args.ceiling_mib) as verifier:
            for index, (n, count, name, kind) in enumerate(selected):
                if time.perf_counter() - started > args.timeout_seconds:
                    raise TimeoutError("bounded verification deadline exceeded")
                raw = db.execute("SELECT epoch_ms,mean_motion_q,eccentricity_q,inclination_q,bstar_q,raan_q,arg_perigee_q "
                                 "FROM element_set WHERE norad=? AND epoch_ms>=? AND epoch_ms<? "
                                 "ORDER BY epoch_ms LIMIT 50001", (n, args.start, args.end)).fetchall()
                if len(raw) != count:
                    raise RuntimeError(f"{n}: archive changed during selection; rerun fixed window")
                measured_rows += len(raw)
                digest.update(json.dumps([n, raw], separators=(",", ":")).encode())
                decoded = [(t, m / 1e8, e / 1e8, i / 1e4, None if b is None else b / 1e12,
                            r / 1e4, a / 1e4) for t, m, e, i, b, r, a in raw]
                intervals = oc.intervals_from_rows(n, name or f"OBJECT {n}", kind or "UNKNOWN", decoded)
                if len(intervals) < oc.MINIMUM_BASELINE_INTERVALS + 1:
                    raise RuntimeError(f"{n}: selected rows produced no usable baseline; cannot shrink controls")
                events = oc.detect_object_events(intervals, kappa=args.kappa,
                                                 expectations=expectations, gpu_verifier=verifier)
                event_digest.update(json.dumps([asdict(e) for e in events], sort_keys=True).encode())
                bucket = kinds.setdefault(kind or "UNKNOWN", dict(objects=0, intervals=0, events=0))
                bucket["objects"] += 1
                bucket["intervals"] += len(intervals)
                bucket["events"] += len(events)
                intervals_seen += len(intervals)
                events_seen += len(events)
                if (index + 1) % 50 == 0:
                    print(f"GPU sweep verified {index+1}/{len(selected)} objects, {intervals_seen:,} intervals, "
                          f"{verifier.disagreements} disagreements, {time.perf_counter()-started:.1f}s", file=sys.stderr, flush=True)
            report = verifier.report()
        gpu_cpu = sum(d["cpuSeconds"] for d in report["devices"])
        report.update(base, intervals=intervals_seen, events=events_seen, measuredRows=measured_rows,
                      strata=kinds, inputSha256=digest.hexdigest(), eventSha256=event_digest.hexdigest(),
                      wallSeconds=time.perf_counter() - started,
                      verificationWallSeconds=time.perf_counter() - compute_wall,
                      verificationCpuCoreMinutes=(time.process_time() - compute_cpu) / 60,
                      arithmeticCpuCoreMinutesSavedEstimate=(report["cpuReferenceSeconds"] - gpu_cpu) / 60,
                      savingsNote="paired measured CPU arithmetic minus GPU preparation/launch CPU; verification itself saves no CPU; excludes publication/tail")
        print(json.dumps(report, sort_keys=True), flush=True)
        return 0 if report["outcome"] == "agreement" and measured_rows == rows else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
