#!/usr/bin/env python3
"""Read-only published-event census and gap-aware EOL measurement helpers.

No network, detector invocation, archive writes, or production artifact writes.
Run at nice 19 / idle I/O. The CLI implements the feasibility stop, not a future
matched-control study. Its null outcomes must not be used as EOL watch scores.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import orbit_campaigns as oc  # noqa: E402

DAY_MS = 86_400_000
RAISE = "geo-graveyard-raise"
NSK = "geo-north-south-keeping"


def epoch(value):
    """Milliseconds UTC. A bare date is UTC midnight, never the host's midnight.

    Every timestamp in this archive and in both external SATCATs is UTC. A
    date-only string ("2009-12-29", a launch date, an ESA reference date, a
    calendar-year boundary) parses to a naive datetime, and `.timestamp()`
    would then read it in the host's local zone -- four or five hours off on
    this machine. That is enough to put a launch-day manoeuvre on the wrong
    side of its own launch date, which is exactly what it did before this was
    fixed. Event timestamps carry "Z" and were never affected.
    """
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


def iso(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def years_before(value, years):
    date = datetime.fromtimestamp(value / 1000, timezone.utc)
    year = date.year - years
    return int(date.replace(year=year, day=min(date.day, calendar.monthrange(year, date.month)[1])).timestamp() * 1000)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_json(root, record):
    data = (root / record["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"Artifact digest mismatch: {record['path']}")
    return json.loads(data)


def published_census(root, manifest, deadline):
    counts = Counter()
    objects = {}
    seen = set()
    total = 0
    for record in manifest["orbitHistory"]["shards"]:
        if time.monotonic() > deadline:
            raise TimeoutError("Published census deadline; no partial results accepted")
        shard = checked_json(root, record)
        for obj in shard["objects"]:
            norad = obj["norad"]
            if norad in seen:
                raise ValueError(f"Duplicate object {norad}")
            seen.add(norad)
            total += len(obj["events"])
            events = []
            for event in obj["events"]:
                if event.get("controlBasis") != "self-history":
                    continue
                counts[event["signature"]] += 1
                if event["signature"] in (RAISE, NSK):
                    events.append({key: event.get(key) for key in (
                        "norad", "name", "objectType", "startAt", "endAt", "signature",
                        "deltaV", "inclinationDeg", "confidence", "manoeuvreLabelPermitted",
                        "controlStratum", "controlBasis", "eventKey")})
            if events:
                objects[norad] = events
        if record["shard"] % 64 == 0:
            print(f"Verified shard {record['shard'] + 1}/256", flush=True)
    if len(seen) != manifest["orbitHistory"]["objects"]:
        raise ValueError("Manifest object count mismatch")
    return objects, dict(counts), len(seen), total


def window_evidence(events, intervals, start, end, *, measure=False):
    """Same-window NSK events; interval samples never cross an archive hole.

    Cadence follows oc.cadence_of's segment containment and minimum counts;
    unrounded spacings are retained here for research. measure=False implements
    the stop rule: expose counts/coverage but do not compute outcome medians.
    """
    chosen = sorted((e for e in events if e["signature"] == NSK
                     and start <= epoch(e["startAt"]) < end
                     and epoch(e["endAt"]) < end), key=lambda e: e["startAt"])
    runs = oc._segments(intervals)
    starts = [epoch(e["startAt"]) for e in chosen]
    spacings = [(b - a) / DAY_MS for a, b in zip(starts, starts[1:])
                if any(lo <= a <= b <= hi for lo, hi in runs)]
    coverage = sum(max(0, min(end, i.end_ms) - max(start, i.start_ms))
                   for i in intervals) / DAY_MS
    gaps = [(max(start, a[1]), min(end, b[0])) for a, b in zip(runs, runs[1:])
            if min(end, b[0]) > max(start, a[1])]
    costs = [e["deltaV"]["totalMetresPerSecond"] for e in chosen]
    if any(not math.isfinite(x) or x < 0 for x in costs):
        raise ValueError("Invalid published Delta-v")
    return {
        "from": iso(start), "toExclusive": iso(end), "nskEvents": len(chosen),
        "spacingsRetained": len(spacings),
        "spacingsExcludedAcrossGaps": max(0, len(starts) - 1) - len(spacings),
        "observedDays": coverage, "calendarDays": (end - start) / DAY_MS,
        "internalGaps": [{"from": iso(a), "to": iso(b), "days": (b-a)/DAY_MS} for a, b in gaps],
        "medianIntervalDays": statistics.median(spacings) if measure and len(chosen) >= 3 and len(spacings) >= 2 else None,
        "medianDeltaVMetresPerSecond": statistics.median(costs) if measure and costs else None,
    }


def ratios(baseline, final):
    """Missing or zero-denominator ratios are unknown, not infinite or zero."""
    result = {}
    for key, field in (("R_interval", "medianIntervalDays"), ("R_dv", "medianDeltaVMetresPerSecond")):
        a, b = baseline[field], final[field]
        result[key] = b / a if a is not None and a > 0 and b is not None else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public/data")
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=900)
    args = parser.parse_args()
    begun, cpu = time.monotonic(), time.process_time()
    deadline = begun + args.max_seconds
    raw = (args.data_root / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    bundle = checked_json(args.data_root, manifest["orbitEvents"])
    objects, counts, scanned, total = published_census(args.data_root, manifest, deadline)
    if total != bundle["eventsPublished"]["total"]:
        raise ValueError("Detail-event total differs from release total")
    retirees = {}
    for norad, events in objects.items():
        raises = sorted((e for e in events if e["signature"] == RAISE), key=lambda e: e["startAt"])
        if not raises or raises[0]["objectType"] != "PAYLOAD":
            continue
        t = epoch(raises[0]["startAt"])
        prior = [e for e in events if e["signature"] == NSK and epoch(e["endAt"]) < t]
        earliest = min((epoch(e["startAt"]) for e in prior), default=None)
        retirees[norad] = {
            "schema": 1, "role": "retiree-candidate", "norad": norad,
            "name": raises[0]["name"], "retirementAt": raises[0]["startAt"],
            "raiseEvents": raises, "priorNskEvents": len(prior),
            "earliestPriorNskAt": iso(earliest) if earliest is not None else None,
            "nskCalendarDepthYears": (t-earliest)/DAY_MS/365.25 if earliest is not None else None,
            "threeYearDepthUpperBoundEligible": earliest is not None and earliest <= years_before(t, 3),
        }
    upper = sum(r["threeYearDepthUpperBoundEligible"] for r in retirees.values())
    # The user's first stop rule forbids an underpowered outcomes study.
    if upper >= 15:
        raise RuntimeError("Census may pass: freeze complete matching before running outcomes; this CLI is census-only")
    path = oc.archive_db_path()
    if not path.is_file() or not str(path.resolve()).startswith("/home/sdegan/"):
        raise ValueError("Expected an existing SSD archive; refusing opener fallback")
    source_hashes = {str(Path(m.__file__).relative_to(ROOT)): digest(Path(m.__file__))
                     for m in (oc, oc.orbit_history)}
    db = oc.open_archive_for_reading(path)
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    assert db.execute("PRAGMA query_only").fetchone()[0] == 1
    metadata = {"path": str(path), "queryOnly": True,
                "journalMode": db.execute("PRAGMA journal_mode").fetchone()[0],
                "monthRollup": db.execute("SELECT month, rows FROM month_rollup ORDER BY month").fetchall()}
    rows_read = 0
    with db:
        for norad, record in sorted(retirees.items()):
            if time.monotonic() > deadline:
                raise TimeoutError("Archive census deadline")
            t = epoch(record["retirementAt"])
            facts = db.execute("SELECT launch_date, object_type FROM object WHERE norad=?", (norad,)).fetchone()
            record["archiveLaunchDate"] = facts[0] if facts else None
            record["archiveObjectType"] = facts[1] if facts else None
            row_groups = list(oc.stream_object_rows(db, only=[norad], page_rows=8192))
            rows = [r for _, group in row_groups for r in group if r[0] < t]
            rows_read += sum(len(group) for _, group in row_groups)
            record["archivePreRaiseRowsSha256"] = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
            iv = oc.intervals_from_rows(norad, record["name"], "PAYLOAD", rows)
            start = rows[0][0] if rows else years_before(t, 3)
            split = years_before(t, 1)
            record["archivePreRaiseRows"] = len(rows)
            record["baseline"] = window_evidence(objects[norad], iv, min(start, split), split)
            record["finalYear"] = window_evidence(objects[norad], iv, split, t)
            record["preRaiseObservedYears"] = oc._covered_days(iv) / 365.25
            record["cadenceEstimableInBothWindows"] = all(
                record[w]["nskEvents"] >= oc.MINIMUM_EVENTS_FOR_CADENCE
                and record[w]["spacingsRetained"] >= 2 for w in ("baseline", "finalYear"))
            record["usableUnderRegisteredRules"] = (
                record["threeYearDepthUpperBoundEligible"]
                and record["preRaiseObservedYears"] >= 3
                and record["cadenceEstimableInBothWindows"])
            record.update(R_interval=None, R_dv=None, status="not-measured-stop-rule",
                          sourceEventArtifactSha256=manifest["orbitEvents"]["sha256"])
    db.close()
    summary = {
        "schema": 1, "verdict": "underpowered", "scope": "published self-history detail records",
        "measuredAtUTC": datetime.now(timezone.utc).isoformat(),
        "manifestSha256": hashlib.sha256(raw).hexdigest(), "manifest": manifest,
        "eventArtifact": manifest["orbitEvents"], "eventCounts": counts,
        "objectsScanned": scanned, "allDetailEvents": total,
        "distinctRetireeCandidates": len(retirees), "threeYearDepthEligibleUpperBound": upper,
        "usableRetirees": sum(r["usableUnderRegisteredRules"] for r in retirees.values()),
        "requiredRetirees": 15, "controlObjectsMeasured": 0,
        "test": {"status": "not-run-stop-rule", "alpha": 0.05, "pValue": None,
                 "effectSize": None, "confidenceInterval95": None},
        "publishedControls": bundle["controls"]["selfHistory"],
        "publishedCoverage": bundle["coverage"], "archive": metadata,
        "sourceSha256": source_hashes, "analysisSourceSha256": digest(Path(__file__)),
        "archiveRowsRead": rows_read, "wallSeconds": time.monotonic()-begun,
        "cpuSeconds": time.process_time()-cpu,
    }
    for name, old in source_hashes.items():
        if digest(ROOT / name) != old:
            raise ValueError("Coverage code changed during census")
    # Exclusive creation: do not overwrite another agent's or an earlier run's evidence.
    with Path(str(args.output_prefix)+".jsonl").open("x") as f:
        for record in retirees.values():
            f.write(json.dumps(record, sort_keys=True, allow_nan=False)+"\n")
    with Path(str(args.output_prefix)+"-receipt.json").open("x") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    print(json.dumps({k: summary[k] for k in ("verdict", "distinctRetireeCandidates", "threeYearDepthEligibleUpperBound", "archiveRowsRead", "wallSeconds")}))


if __name__ == "__main__":
    main()
