#!/usr/bin/env python3
"""Read-only archive slice: legacy serial vs streamed serial/pool, real writer.

No build_cache, publication, timers or production stage writes. Scratch lives in
one TemporaryDirectory, at most 2 GiB/8192 files, removed on exit. Defaults: 12
shards, <=2000 objects, <=10M rows, <=600 seconds/run, <4 GiB process-tree RSS.
--dry-run inventories selected inputs only. Run at nice 15 / idle I/O priority.
"""
import argparse
import hashlib
import json
import os
import pickle
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import orbit_campaigns as oc, orbit_release as release
from pipeline.orbit_tail import TailCheckpoint, TailEvents
from tools.benchmark_orbit_sweep import tree_rss


def load_prepared(path):
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        # Exactly the pre-change checkpoint load, including the temporary BLOB.
        raw = db.execute("SELECT value FROM stage WHERE name='prepared'").fetchone()[0]
        prepared = pickle.loads(raw)
        if not isinstance(prepared[4], dict):
            raise ValueError("legacy baseline requires a pre-streaming prepared checkpoint via --stages")
        return prepared
    finally:
        db.close()


def child(args):
    root = args.scratch
    indices = list(range(args.start_shard, args.start_shard + args.shards))
    if args.mode == "prepare":
        prepared = load_prepared(args.stages)
        wanted = {n for n in prepared[2] if n % release.HISTORY_SHARDS in indices}
        if len(wanted) > 2000:
            raise ValueError("slice exceeds 2000 objects")
        db = oc.open_archive_for_reading(args.archive)
        try:
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                raise ValueError("benchmark requires the SSD/WAL archive")
            rows = sum(db.execute(f"SELECT count(*) FROM {table} WHERE norad=?", (n,)).fetchone()[0]
                       for n in wanted for table in ("element_set", "element_set_daily"))
        finally:
            db.close()
        if rows > 10_000_000:
            raise ValueError("slice exceeds 10 million rows")
        if args.dry_run:
            print(json.dumps(dict(shards=indices, objects=len(wanted), rows=rows, dryRun=True)))
            return
        with TailCheckpoint(root / "inputs", "benchmark", root, None) as tail:
            batch, offset = [], 0
            for n in sorted(wanted):
                for record in prepared[4].get(n, []):
                    batch.append(record)
                    if len(batch) == 128:
                        TailEvents.put(tail.db, batch, offset)
                        offset += len(batch)
                        batch = []
            TailEvents.put(tail.db, batch, offset)
        compact = (*prepared[:4], TailEvents(root / "inputs"), prepared[5])
        with (root / "prepared.pickle").open("wb") as handle:
            pickle.dump(compact, handle, protocol=pickle.HIGHEST_PROTOCOL)
        print(json.dumps(dict(objects=len(wanted), rows=rows, events=offset + len(batch))))
        return

    # Include the real retained parent accumulator, but do not run the sweep.
    with args.sweep.open("rb") as handle:
        retained_scan = pickle.load(handle)
    if args.mode == "legacy":
        prepared = load_prepared(args.stages)
    else:
        with (root / "prepared.pickle").open("rb") as handle:
            prepared = pickle.load(handle)
    from pipeline.build_release import write_artifact
    output = root / "output"
    output.mkdir()
    db = oc.open_archive_for_reading(args.archive)
    started = time.monotonic()
    try:
        with TailCheckpoint(output / "tail", "benchmark", output, None) as tail:
            if args.mode == "legacy":
                for index in indices:
                    shard = release._history_shard(db, index, *prepared[2:])
                    if shard:
                        path, digest = write_artifact(output, f"orbit-history-{index:03d}", shard)
                        tail.pin(path, digest)
                        tail.save(f"shard:{index:03d}", dict(shard=index, path=path, sha256=digest,
                                                          objects=len(shard["objects"])))
                    else:
                        tail.save(f"shard:{index:03d}", None)
                    del shard
            else:
                release._write_tail_shards(db, prepared, tail, output, write_artifact,
                                           args.workers[0], indices=indices)
            seconds = time.monotonic() - started
            records = tail.values("shard:")
        # Include JSON/gzip and the production writer's plot derivatives.
        files = [(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted((output / "artifacts").iterdir())]
        digest = hashlib.sha256(json.dumps(files).encode()).hexdigest()
        print(json.dumps(dict(mode=args.mode, workers=args.workers[0], seconds=seconds,
                              secondsPerShard=seconds / len(indices), shards=len(indices),
                              objects=sum(r["objects"] for r in records if r), files=len(files),
                              sha256=digest, retainedSweepObjects=retained_scan['passed'].objects_scanned)))
    finally:
        db.close()


def run(args, scratch, mode, workers):
    command = [sys.executable, str(Path(__file__).resolve()), "--mode", mode,
               "--scratch", str(scratch), "--archive", str(args.archive),
               "--stages", str(args.stages), "--sweep", str(args.sweep),
               "--shards", str(args.shards), "--start-shard", str(args.start_shard),
               "--workers", str(workers)]
    if args.dry_run:
        command.append("--dry-run")
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, start_new_session=True)
    peak = count = 0
    try:
        while process.poll() is None:
            rss, children = tree_rss(process.pid)
            peak, count = max(peak, rss), max(count, children)
            if rss > 4 * 1024**3:
                raise RuntimeError("4 GiB tree RSS bound exceeded; reduce workers")
            if time.monotonic() - started > args.timeout_seconds:
                raise TimeoutError("bounded tail benchmark timed out")
            sizes = []
            for path in scratch.rglob('*'):
                try:
                    if path.is_file():
                        sizes.append(path.stat().st_size)
                except FileNotFoundError:
                    pass  # Atomic writer rename or committed journal removal.
            if len(sizes) > 8192 or sum(sizes) > 2 * 1024**3:
                raise RuntimeError("scratch budget exceeded")
            time.sleep(.05)
        output, _ = process.communicate()
        if process.returncode:
            raise RuntimeError(f"benchmark {mode} exited {process.returncode}")
        result = json.loads(output.splitlines()[-1])
        result.update(peakTreeRssMiB=round(peak / 1024**2, 1), peakProcesses=count,
                      processSeconds=round(time.monotonic() - started, 3))
        print(json.dumps(result), flush=True)
        return result
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)  # only OUR private benchmark group
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=oc.archive_db_path())
    parser.add_argument('--stages', type=Path, default=release.SWEEP_STATE_PATH.with_suffix('.tail') / 'stages.sqlite3')
    parser.add_argument('--sweep', type=Path, default=release.SWEEP_STATE_PATH)
    parser.add_argument('--shards', type=int, default=12)
    parser.add_argument('--start-shard', type=int, default=0)
    parser.add_argument('--workers', type=int, nargs='+', default=[1, oc.sweep_worker_count()])
    parser.add_argument('--timeout-seconds', type=float, default=600)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--mode', choices=['prepare', 'legacy', 'streamed'], help=argparse.SUPPRESS)
    parser.add_argument('--scratch', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not (1 <= args.shards <= 24 and 0 <= args.start_shard <= 256 - args.shards):
        parser.error('requires 1..24 shards within 0..255')
    if any(n < 1 for n in args.workers) or not 0 < args.timeout_seconds <= 600:
        parser.error('requires positive workers and timeout <=600s')
    if not args.archive.is_file():
        parser.error("read-only benchmark requires an existing archive")
    if args.mode:
        child(args)
        return
    with tempfile.TemporaryDirectory(prefix='orbit-tail-benchmark-') as directory:
        scratch = Path(directory)
        run(args, scratch, 'prepare', 1)
        if args.dry_run:
            return
        results = []
        for mode, workers in [('legacy', 1)] + [('streamed', n) for n in args.workers]:
            results.append(run(args, scratch, mode, workers))
            shutil.rmtree(scratch / 'output')
        print(json.dumps(dict(identical=len({r['sha256'] for r in results}) == 1,
                              speedups=[round(results[0]['seconds']/r['seconds'], 3) for r in results])))
        if len({r['sha256'] for r in results}) != 1:
            raise RuntimeError('slice artifacts differ')


if __name__ == '__main__':
    main()
