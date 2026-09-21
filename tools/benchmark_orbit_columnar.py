#!/usr/bin/env python3
"""Bounded read-only live benchmark plus explicitly synthetic offline daily append.

Run with nice/ionice and OPENBLAS_NUM_THREADS=1. All scratch has a TemporaryDirectory
lifetime; only JSON stdout survives. No network, GPU, timer or live database writes.
"""
import argparse
import hashlib
import json
import resource
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from pipeline import orbit_campaigns as oc, orbit_history as oh, orbit_columnar as col


def timed(fn):
    wall, cpu = time.perf_counter(), time.process_time()
    value = fn()
    return value, {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu}


def consume(objects, *, copy):
    # Touch every byte on BOTH paths, proving this is not mmap setup vs real reads.
    h, rows, count = hashlib.sha256(), 0, 0
    for norad, arrays in objects:
        count += 1
        rows += len(arrays["epoch_ms"])
        h.update(int(norad).to_bytes(8, "little"))
        for name in col.FIELDS:
            array = arrays[name].copy() if copy else arrays[name]
            h.update(memoryview(array).cast("B"))
    return {"objects": count, "rows": rows, "sha256": h.hexdigest()}


def sqlite_arrays(path, only):
    source = col._Source(path)
    try:
        for n, rows in oc.stream_object_rows(source.db, only=only, page_rows=32768):
            source.check()
            arrays = {name: np.asarray([row[i] for row in rows],
                       dtype="<i8" if i == 0 else "<f8") for i, name in enumerate(col.FIELDS)}
            yield n, arrays
        source.check()
    finally:
        source.close()


def from_store(root, path, *, copy):
    with col.open_store(root, archive=path) as store:
        return consume(((o.norad, o.columns) for o in store.iter_objects()), copy=copy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", type=int, default=96)
    parser.add_argument("--max-rows", type=int, default=750000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--scratch-parent", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    if not 1 <= args.objects <= 256 or not 1 <= args.max_rows <= 2000000 or not 1 <= args.repeats <= 5:
        parser.error("bounds: objects <= 256, rows <= 2M, repeats <= 5")
    path = oh.archive_db_path()
    source = col._Source(path)
    try:
        if source.db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
            raise RuntimeError("Live benchmark requires SSD/WAL")
        counts = source.db.execute("SELECT norad,rows FROM object_rollup ORDER BY norad").fetchall()
        total_rows = sum(r[1] for r in counts)
        candidates = np.linspace(0, len(counts) - 1, args.objects, dtype=int)
        members, estimated = [], 0
        for i in candidates:
            n, count = counts[i]
            if count > 0 and estimated + count <= args.max_rows:
                members.append(n)
                estimated += count
        # Enforce the actual read bound, independently of possibly stale rollups.
        actual = 0
        for n in members:
            actual += len(source.db.execute("SELECT epoch_ms FROM element_set WHERE norad=? LIMIT ?",
                                           (n, args.max_rows - actual + 1)).fetchall())
            if actual > args.max_rows:
                raise RuntimeError("Actual rows exceed the explicit bound")
        latest = source.db.execute("SELECT captured_ms FROM capture ORDER BY captured_ms DESC LIMIT 1").fetchone()
        day = None
        if latest:
            end = latest[0] // 86400000 * 86400000
            r = source.db.execute("SELECT count(*),sum(elements_new) FROM capture WHERE captured_ms>=? AND captured_ms<?",
                                  (end - 86400000, end)).fetchone()
            day = {"start_ms": end - 86400000, "capture_records": r[0], "elements_new": r[1]}
        # This is only sample selection, never a content certificate. The build
        # opens its own guarded source and subsequent parity covers that scope.
    finally:
        source.close()
    if not actual:
        raise RuntimeError("Empty benchmark slice")
    report = {"source": str(path), "live_rollup_rows_not_a_full_count": total_rows,
              "live_rollup_objects": len(counts), "only": members, "bounded_rows": actual,
              "previous_complete_capture_day": day,
              "pre_measurement_estimate": {"target_rows": 216000000, "column_bytes": 216000000 * 56,
                  "build_seconds_at_100k_to_300k_rows_per_second": [720, 2160]},
              "cache_policy": "warm OS cache, no cache eviction, single CPU, live workloads remain running"}
    with tempfile.TemporaryDirectory(prefix="orbit-columnar-bench-", dir=args.scratch_parent) as tmp:
        root = Path(tmp) / "live-store"
        manifest, report["build"] = timed(lambda: col.build(root, archive=path, only=members))
        if manifest["rows"] != actual:
            raise RuntimeError("Sample changed after row-bound preflight; discard benchmark")
        report["store_bytes"], report["store_files"] = col._inventory(root)
        report["arrays"] = []
        for i in range(args.repeats):
            run = {}
            # Alternate order to reduce order/load bias.
            paths = ["sqlite", "store_views", "store_copies"]
            if i % 2:
                paths.reverse()
            for route in paths:
                if route == "sqlite":
                    value, timing = timed(lambda: consume(sqlite_arrays(path, members), copy=False))
                else:
                    value, timing = timed(lambda: from_store(root, path, copy=route == "store_copies"))
                run[route] = dict(timing, **value)
            if len({r["sha256"] for r in run.values()}) != 1:
                raise RuntimeError("Full-byte SQLite/store parity failed")
            report["arrays"].append(run)
        _, report["verify"] = timed(lambda: col.verify(root, archive=path))

        # Copy only the bounded selected projection to a brand-new OFFLINE fixture.
        fixture = Path(tmp) / "daily-fixture.sqlite3"
        db = sqlite3.connect(fixture)
        try:
            db.execute("CREATE TABLE element_set(norad INTEGER,epoch_ms INTEGER,mean_motion_q INTEGER,"
                       "eccentricity_q INTEGER,inclination_q INTEGER,bstar_q INTEGER,raan_q INTEGER,"
                       "arg_perigee_q INTEGER,PRIMARY KEY(norad,epoch_ms)) WITHOUT ROWID")
            db.execute("PRAGMA journal_mode=WAL")
            src = col._Source(path)
            tails, day_rows, future_rows = [], [], []
            try:
                for n, raw in col._raw_objects(src, members):
                    rows = [(n, *(int(row[name]) if name != "bstar" or row["valid"] else None for name in col.FIELDS))
                            for row in raw]
                    if day:
                        day_rows.extend(r for r in rows if day["start_ms"] <= r[1] < day["start_ms"] + 86400000)
                        future_rows.extend(r for r in rows if r[1] >= day["start_ms"] + 86400000)
                        baseline = [r for r in rows if r[1] < day["start_ms"]]
                    else:
                        baseline = rows
                    db.executemany("INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?)", baseline)
                    tails.append(rows[-1])
                db.commit()
                src.check()
            finally:
                src.close()
            offline = Path(tmp) / "daily-store"
            col.build(offline, archive=fixture)
            if day:
                db.executemany("INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?)", day_rows)
                db.commit()
                m, timing = timed(lambda: col.append(offline, archive=fixture))
                report["observed_day_replay_append"] = dict(timing, start_ms=day["start_ms"],
                    added_rows=len(day_rows), affected_objects=len({r[0] for r in day_rows}),
                    source_scan_seconds=m["maintenance"]["source_scan_seconds"],
                    explanation="actual selected-object rows for the complete UTC day, replayed only into an OFFLINE fixture")
                col.verify(offline, archive=fixture)
                if from_store(offline, fixture, copy=False) != consume(sqlite_arrays(fixture, None), copy=False):
                    raise RuntimeError("Observed-day replay parity failed")
                db.executemany("INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?)", future_rows)
                db.commit()
                col.append(offline, archive=fixture)
            report["synthetic_day_append"] = []
            for fraction in (0.1, 1.0):
                affected = tails[:max(1, int(len(tails) * fraction))]
                for row in affected:
                    latest_epoch = db.execute("SELECT max(epoch_ms) FROM element_set WHERE norad=?", (row[0],)).fetchone()[0]
                    for halfday in (1, 2):
                        db.execute("INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?)",
                                   (row[0], latest_epoch + halfday * 43200000, *row[2:]))
                db.commit()
                m, timing = timed(lambda: col.append(offline, archive=fixture))
                report["synthetic_day_append"].append(dict(timing, affected_objects=len(affected),
                    added_rows=2 * len(affected), source_scan_seconds=m["maintenance"]["source_scan_seconds"],
                    explanation="two new epochs per affected object in an OFFLINE fixture; not measured live ingestion"))
                col.verify(offline, archive=fixture)
                if from_store(offline, fixture, copy=False) != consume(sqlite_arrays(fixture, None), copy=False):
                    raise RuntimeError("Offline append parity failed")
        finally:
            db.close()
        report["peak_process_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["temporary_bytes_before_cleanup"], _ = col._inventory(Path(tmp))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
