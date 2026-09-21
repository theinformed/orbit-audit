#!/usr/bin/env python3
"""Bounded sweep comparison; no production release/checkpoint writes.

Run at nice 15 / idle I/O priority. Prints JSON to stdout, retains no artifacts.
Worker-count runs use fresh processes; --compare-columnar alternates routes in
one process and builds production artifact bytes in auto-removed SSD scratch.
For worker-count comparisons, Linux /proc sampling sums simultaneous
RSS across its entire process tree (including the pool and resource tracker),
every 50 ms. Shared pages are counted per process, conservatively.
"""

import argparse
import dataclasses
import hashlib
import itertools
import json
import os
import signal
import subprocess
import sys
import time
import tempfile
import sqlite3
import contextlib
import io
import statistics
from unittest.mock import patch
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import orbit_campaigns as oc
from pipeline.orbit_events import load_catalog


def canonical(value):
    if dataclasses.is_dataclass(value):
        return {f.name: canonical(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in sorted(value.items(), key=lambda p: str(p[0]))}
    if isinstance(value, (list, tuple, array)):
        return [canonical(v) for v in value]
    return value


def tree_rss(pid):
    pending = [pid]
    seen = set()
    rss = 0
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        root = Path(f"/proc/{current}")
        try:
            rss += int((root / "statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            for children in root.glob("task/*/children"):
                pending.extend(int(p) for p in children.read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            pass
    return rss, len(seen)


def compare_columnar(args):
    """Real bounded extract, full sweep and production artifact bytes, no live writes.

    All scratch is temporary on SSD: <=512 MiB, <=2000 files, removed on exit.
    The source's metadata/data_version guard covers selection and extraction.
    No cold shards are copied or read; this is a bounded hot-population proof.
    """
    from pipeline import orbit_columnar as col, orbit_history as oh, orbit_release as release, orbit_sweep_gpu as gpu_module
    from pipeline.build_release import write_artifact
    from tools.verify_orbit_sweep_gpu import epoch, select
    from tools.benchmark_orbit_columnar import timed
    started = time.monotonic()
    def check():
        if time.monotonic() - started > args.timeout_seconds:
            raise TimeoutError("bounded columnar comparison exhausted its time budget")
    selection_args = argparse.Namespace(only=None, seed=20260912, objects=args.objects,
                                        start=epoch(args.start), end=epoch(args.end),
                                        min_rows=100, max_rows=args.max_rows)
    report = {"archive": str(args.archive), "start": args.start, "end": args.end,
              "cache": "warm OS caches; alternating order; no cache eviction; other host work continues",
              "kappa": release.DEFAULT_SELF_HISTORY_KAPPA, "detector_flags": oc.detector_flags()}
    with tempfile.TemporaryDirectory(prefix="orbit-columnar-sweep-", dir=ROOT / "state") as tmp:
        scratch = Path(tmp)
        path, root = scratch / "population.sqlite3", scratch / "columns"
        db = sqlite3.connect(path)
        try:
            db.executescript(oh._SCHEMA)
            db.execute("PRAGMA journal_mode=WAL")
            digest, total, held = hashlib.sha256(), 0, []
            with contextlib.closing(col._Source(args.archive)) as source:
                source.db.execute("PRAGMA busy_timeout=1000")
                source.db.set_progress_handler(lambda: int(time.monotonic() - started > args.timeout_seconds), 10000)
                selected, expected = select(source.db, selection_args)
                report["selection"] = selected
                for n, *_ in selected:
                    check()
                    raw = source.db.execute(
                        "SELECT * FROM element_set WHERE norad=? AND epoch_ms>=? AND epoch_ms<? "
                        "ORDER BY epoch_ms LIMIT ?", (n, selection_args.start, selection_args.end,
                                                     args.max_rows - total + 1)).fetchall()
                    total += len(raw)
                    if total > args.max_rows:
                        raise RuntimeError("actual extraction exceeded row bound")
                    digest.update(json.dumps(raw, separators=(",", ":")).encode())
                    # Replay the final complete epoch day using actual observed rows.
                    held.extend(r for r in raw if r[1] >= selection_args.end - 86400000)
                    prior = [r for r in raw if r[1] < selection_args.end - 86400000]
                    if raw:
                        marks = ",".join("?" for _ in raw[0])
                        db.executemany(f"INSERT INTO element_set VALUES ({marks})", prior)
                    facts = source.db.execute("SELECT * FROM object WHERE norad=?", (n,)).fetchall()
                    if facts:
                        db.executemany("INSERT INTO object VALUES (" + ",".join("?" for _ in facts[0]) + ")", facts)
                    source.check()
                source.check()
                if total != expected:
                    raise RuntimeError("selection/extraction counts differ")
            db.commit()
            report.update(rows=total, input_sha256=digest.hexdigest(), replay_rows=len(held))
            _, report["build"] = timed(lambda: col.maintain(root, archive=path, seconds=60,
                                                            budget_bytes=256 * 1024**2))
            if held:
                db.executemany("INSERT INTO element_set VALUES (" + ",".join("?" for _ in held[0]) + ")", held)
            oh.refresh_summary(db)
            db.commit()
            report["refresh"] = col.maintain(root, archive=path, seconds=60, budget_bytes=256 * 1024**2)
            report["store_bytes"], report["store_files"] = col._inventory(root)
            members = [r[0] for r in selected]
            catalog = load_catalog(ROOT / "public/data")
            catalog = {n: catalog.get(n, {}) for n in members}
            reference, artifacts = {}, {}
            results = []
            # Artifact construction runs outside the measured sweep; clock and
            # catalog are frozen for both tails. Production serializers execute.
            def artifact_bytes(scan, route):
                dest = scratch / route
                with contextlib.redirect_stdout(sys.stderr), \
                        patch.object(release, "load_catalog", return_value=catalog), \
                        patch.object(release, "_generation_time", return_value=args.end + "T00:00:00Z"), \
                        patch.object(release, "COHORT_DETECT_WORKERS", 1):
                    shards, events, drag = release.build_bundles(db, dest, scan=scan)
                for shard in shards:
                    write_artifact(dest, f"orbit-history-{shard['shard']:03d}", shard)
                write_artifact(dest, "orbit-events", events)
                write_artifact(dest, "orbit-drag", drag)
                files = {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob("*") if p.is_file()}
                if not files:
                    raise RuntimeError("artifact proof produced no files")
                return files
            for mode in args.columnar_modes:
                for repeat in range(args.repeats):
                    for route in (["sqlite", "columnar"] if repeat % 2 == 0 else ["columnar", "sqlite"]):
                        check()
                        log = io.StringIO()
                        options = {} if mode == "cpu" else {"gpu_devices": (args.device,), "gpu_ceiling_mib": 512}
                        with contextlib.redirect_stderr(log), \
                                patch.object(gpu_module, "_USAGE_LEDGER", scratch / "gpu-usage.jsonl"):
                            progress, timing = timed(lambda: oc.sweep_archive(
                                db, only=members, catalog=catalog, keep_summaries_for=set(members),
                                kappa=release.DEFAULT_SELF_HISTORY_KAPPA, workers=1,
                                columnar_root=False if route == "sqlite" else root, **options))
                        print(log.getvalue(), end="", file=sys.stderr, flush=True)
                        if not progress.complete or progress.objects_this_run != len(members):
                            raise RuntimeError("incomplete sweep")
                        if route == "columnar" and "SWEEP COLUMNAR FALLBACK:" in log.getvalue():
                            raise RuntimeError("columnar measurement fell back to SQLite")
                        gpu = next((json.loads(s.split(" ", 3)[3]) for s in log.getvalue().splitlines()
                                    if s.startswith("SWEEP GPU EXECUTION {")), None)
                        if mode == "gpu" and (gpu is None or gpu["outcome"] != "gpu"):
                            raise RuntimeError("GPU measurement used CPU fallback")
                        encoded = json.dumps(canonical(progress.passed), sort_keys=True).encode()
                        reference.setdefault(mode, encoded)
                        if encoded != reference[mode]:
                            raise RuntimeError("events/control counters/accumulator bytes differ")
                        if repeat == 0:
                            files = artifact_bytes(progress.passed, mode + "-" + route)
                            artifacts.setdefault(mode, files)
                            if files != artifacts[mode]:
                                raise RuntimeError("production artifact bytes differ")
                        results.append(dict(mode=mode, route=route, repeat=repeat, **timing,
                                            events=len(progress.passed.events), gpu=gpu,
                                            sha256=hashlib.sha256(encoded).hexdigest()))
                        print(f"COLUMNAR BENCH {mode}/{route}/{repeat}: {timing}", file=sys.stderr, flush=True)
                        files_on_disk = [p for p in scratch.rglob("*") if p.is_file()]
                        used = sum(p.stat().st_size for p in files_on_disk)
                        if used > 512 * 1024**2 or len(files_on_disk) > 2000:
                            raise RuntimeError("benchmark scratch budget exceeded")
                        report["scratch_peak_bytes"] = max(report.get("scratch_peak_bytes", 0), used)
            report.update(identical=True, runs=results,
                          cpu_gpu_accumulator_bytes_equal=len(set(reference.values())) == 1,
                          artifact_sha256={mode: {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
                                           for mode, files in artifacts.items()})
            report["medians"] = {}
            for mode in args.columnar_modes:
                cpu = {route: statistics.median(r["cpu_seconds"] for r in results
                                                if r["mode"] == mode and r["route"] == route)
                       for route in ("sqlite", "columnar")}
                report["medians"][mode] = dict(cpu, saved_cpu_seconds=cpu["sqlite"] - cpu["columnar"],
                    speedup=cpu["sqlite"] / cpu["columnar"],
                    refresh_plus_read_cpu_seconds=report["refresh"]["cpu_seconds"] + cpu["columnar"])
        finally:
            db.close()
    print(json.dumps(report, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=oc.archive_db_path())
    parser.add_argument("--objects", type=int, default=400)
    parser.add_argument("--after-norad", type=int, default=None)
    parser.add_argument("--max-rows", type=int, default=3_000_000)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, oc.sweep_worker_count()])
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--run-worker-count", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--compare-columnar", action="store_true")
    parser.add_argument("--columnar-modes", choices=("cpu", "gpu"), nargs="+", default=["cpu"])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-09-01")
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.objects <= 2000 or not 1 <= args.max_rows <= 10_000_000:
        parser.error("bounded benchmark requires 1..2000 objects and at most 10 million rows")
    if args.compare_columnar:
        if (args.objects > 256 or args.max_rows > 1_000_000 or not 1 <= args.repeats <= 5
                or not 0 < args.timeout_seconds <= 1800 or str(args.archive.resolve()).startswith("/mnt/")):
            parser.error("columnar proof requires <=256 objects, <=1M rows, <=5 repeats, <=1800s, SSD archive")
        compare_columnar(args)
        return
    if args.run_worker_count is not None:
        db = oc.open_archive_for_reading(args.archive)
        try:
            mode = db.execute("PRAGMA journal_mode").fetchone()[0]
            if mode != "wal":
                raise RuntimeError(f"benchmark requires the SSD/WAL archive, found {mode}")
            members = list(itertools.islice(itertools.chain.from_iterable(
                oc._sweep_ranges(db, None, args.after_norad)), args.objects))
            if not members:
                raise RuntimeError("empty benchmark range")
            marks = ",".join("?" for _ in members)
            rows = db.execute(f"SELECT count(*) FROM element_set WHERE norad IN ({marks})",
                              members).fetchone()[0]
            if rows > args.max_rows:
                raise RuntimeError(f"{rows} rows exceeds the explicit bound {args.max_rows}")
            catalog = load_catalog(ROOT / "public" / "data")
            started = time.monotonic()
            progress = oc.sweep_archive(db, only=members, workers=args.run_worker_count,
                                        catalog=catalog, keep_summaries_for=set(catalog))
            seconds = time.monotonic() - started
            digest = hashlib.sha256(json.dumps(canonical(progress.passed),
                                               sort_keys=True).encode()).hexdigest()
            print(json.dumps(dict(workers=args.run_worker_count, seconds=seconds, rows=rows,
                                  nice=os.getpriority(os.PRIO_PROCESS, 0),
                                  objects=progress.objects_this_run, firstNorad=members[0],
                                  lastNorad=members[-1], complete=progress.complete,
                                  summaries=len(progress.passed.summaries),
                                  events=len(progress.passed.events), sha256=digest)))
        finally:
            db.close()
        return

    results = []
    for workers in args.workers:
        command = [sys.executable, str(Path(__file__).resolve()),
                   "--archive", str(args.archive), "--objects", str(args.objects),
                   "--max-rows", str(args.max_rows), "--run-worker-count", str(workers)]
        if args.after_norad is not None:
            command += ["--after-norad", str(args.after_norad)]
        started = time.monotonic()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True,
                                   start_new_session=True)
        peak = processes = 0
        try:
            while process.poll() is None:
                rss, count = tree_rss(process.pid)
                peak, processes = max(peak, rss), max(processes, count)
                if time.monotonic() - started > args.timeout_seconds:
                    raise TimeoutError("bounded benchmark exceeded its time limit")
                time.sleep(0.05)
            output, _ = process.communicate()
            if process.returncode:
                raise RuntimeError(f"benchmark exited {process.returncode}")
        finally:
            if process.poll() is None:
                # Only this benchmark's private process group, never a service.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        result = json.loads(output)
        result.update(peakTreeRssMiB=round(peak / 1024**2, 1), peakProcesses=processes,
                      processWallSeconds=round(time.monotonic() - started, 3))
        results.append(result)
        print(json.dumps(result), flush=True)
    if len(results) > 1:
        baseline = next((r for r in results if r["workers"] == 1), results[0])
        print(json.dumps(dict(identical=len({r["sha256"] for r in results}) == 1,
                              baselineWorkers=baseline["workers"],
                              speedups=[round(baseline["seconds"] / r["seconds"], 3)
                                        for r in results])))


if __name__ == "__main__":
    main()
