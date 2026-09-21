"""Paper B: the bounded, resumable archive re-detection that feeds both analyses.

One read-only pass over a registered systematic sample of the archive,
producing per-object tallies in four covariate factors and in fine inclination
bins. One pass, not two, because the covariate transfer (Analysis 1) and the
inclination curve (Analysis 2) need the same detector output sliced two ways,
and running the detector twice over the same rows would double the cost while
introducing the possibility of the two slices disagreeing.

Tallies are written PER OBJECT, not pre-aggregated. That costs a larger file
and buys the only thing that makes the headline interval believable: intervals
inside one object share a baseline and a fit history, so the uncertainty has to
be computed by resampling objects, and that is impossible from aggregate cells.

Everything it does is registered in `docs/paperb-preregistration-20260920.md`.
It opens the archive through `open_archive_for_reading`, so it holds no write
lock and cannot block the ingest or the running release sweep. It runs at
nice 19 under a cooperative wall-clock budget, checkpoints its object cursor,
and resumes from that cursor rather than restarting.

Usage:

    nice -n 19 ionice -c3 .venv-gpu/bin/python tools/paperb_measure.py \
        --modulus 5 --min-norad 0 --max-norad 22966 \
        --out /tmp/paperb-20260920/part0 --budget-seconds 3600
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline import orbit_campaigns as oc  # noqa: E402
from pipeline.orbit_events import NON_PROPULSIVE_SIGNATURES  # noqa: E402
from tools import paperb_strata as strata  # noqa: E402

PASSIVE_TYPES = ("DEBRIS", "ROCKET BODY")
PAYLOAD_TYPES = ("PAYLOAD",)
IN_SCOPE = PASSIVE_TYPES + PAYLOAD_TYPES
KAPPA = 32
MINIMUM_INTERVALS = 9  # the production admission rule, restated for the log


# Each cell is
#   [intervals,
#    flags_on,  inclination_on,  inclination_only_on,
#    flags_off, inclination_off, inclination_only_off]
# where "on" is the shipping detector (energy corroboration active, 56eef64)
# and "off" is the pre-corroboration detector reached through the existing
# `_inclination_corroboration=False` keyword on the production function.
#
# Both states are tallied in one pass over the same in-memory rows, per
# amendment 1 of the pre-registration. Analysis 1's headline floor is the "on"
# state, because that is the detector that ships. Analysis 2 needs the "off"
# state, because the corroboration rule abstains on precisely the
# inclination-only catches at and above 30 degrees that Analysis 2 measures, so
# under "on" that analysis is zero against zero by construction.
CELL_WIDTH = 7
POLICY_OFFSET = {"on": 1, "off": 4}


def _cell() -> list[int]:
    return [0] * CELL_WIDTH


def select_objects(db, modulus: int, minimum: int, maximum: int) -> dict[int, tuple[str, str]]:
    placeholders = ",".join("?" for _ in IN_SCOPE)
    sql = (
        "select norad,name,object_type from object "
        f"where norad %% {modulus} = 0 and norad > ? and norad <= ? "
        f"and object_type in ({placeholders}) order by norad"
    ).replace("%%", "%")
    return {
        norad: (name, object_type)
        for norad, name, object_type in db.execute(sql, (minimum, maximum, *IN_SCOPE))
    }


def measure(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    objects_path = out.with_suffix(".objects.jsonl")
    cursor_path = out.with_suffix(".cursor.json")
    summary_path = out.with_suffix(".summary.json")

    started = time.monotonic()
    cpu_started = time.process_time()

    db = oc.open_archive_for_reading()
    assert db.execute("pragma journal_mode").fetchone()[0] == "wal"
    db.execute("pragma busy_timeout=10000")
    # The hard bound is enforced inside SQLite itself: a cooperative check
    # between objects cannot interrupt a page read that has gone slow behind a
    # writer, and an unbounded reader on a loaded host is exactly the thing the
    # resource rules forbid.
    db.set_progress_handler(
        lambda: int(time.monotonic() - started > args.hard_seconds), 10000
    )

    facts = select_objects(db, args.modulus, args.min_norad, args.max_norad)
    expectations = oc.Expectations.load()
    catalog = oc.load_catalog(_REPO / "public" / "data")

    resume_after = None
    totals = {
        "passiveObjects": 0, "payloadObjects": 0,
        "passiveRows": 0, "payloadRows": 0,
        "passiveIntervals": 0, "payloadIntervals": 0,
        "passiveFlagsOn": 0, "payloadFlagsOn": 0,
        "passiveInclinationOn": 0, "payloadInclinationOn": 0,
        "passiveInclinationOnlyOn": 0, "payloadInclinationOnlyOn": 0,
        "passiveFlagsOff": 0, "payloadFlagsOff": 0,
        "passiveInclinationOff": 0, "payloadInclinationOff": 0,
        "passiveInclinationOnlyOff": 0, "payloadInclinationOnlyOff": 0,
        "passiveTooShortObjects": 0, "payloadTooShortObjects": 0,
    }
    digest = hashlib.sha256()
    if args.resume and cursor_path.is_file():
        saved = json.loads(cursor_path.read_text())
        resume_after = saved["lastNorad"]
        totals = saved["totals"]
        digest = hashlib.sha256()
        digest.update(bytes.fromhex(saved["digestState"]))
        # The cursor is written every hundred objects but the object file is
        # written every object, so a reader that died between the two leaves
        # records on disk that the saved totals do not know about. Resuming
        # from the cursor would then process those objects a SECOND time and
        # append them again: silently doubled exposure and doubled flags, with
        # no error anywhere. Truncate the file back to the cursor first, so
        # the file and the totals always describe the same set of objects.
        kept, dropped = [], 0
        with objects_path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                if json.loads(line)["norad"] <= resume_after:
                    kept.append(line)
                else:
                    dropped += 1
        if dropped:
            objects_path.write_text("".join(kept))
            print(f"truncated {dropped} object record(s) past the cursor", flush=True)
        print(f"resuming after NORAD {resume_after}, {len(kept)} records retained", flush=True)
    else:
        objects_path.write_text("")

    remaining = [n for n in facts if resume_after is None or n > resume_after]
    print(f"selected {len(facts)} objects, {len(remaining)} remaining", flush=True)

    sink = objects_path.open("a")
    processed = 0
    last_norad = resume_after
    stopped_early = False
    for norad, rows in oc.stream_object_rows(
        db, only=remaining, page_rows=args.page_rows,
    ):
        if time.monotonic() - started > args.budget_seconds:
            stopped_early = True
            break
        name, object_type = facts[norad]
        group = "payload" if object_type in PAYLOAD_TYPES else "passive"
        digest.update(json.dumps([norad, len(rows)], separators=(",", ":")).encode())
        totals[f"{group}Rows"] += len(rows)
        totals[f"{group}Objects"] += 1
        intervals = oc.intervals_from_rows(norad, name, object_type, rows)
        if len(intervals) < MINIMUM_INTERVALS:
            totals[f"{group}TooShortObjects"] += 1
            last_norad = norad
            processed += 1
            continue
        totals[f"{group}Intervals"] += len(intervals)

        cells: dict[str, list[int]] = {}
        curve: dict[str, list[int]] = {}
        zoom: dict[str, list[int]] = {}
        by_start: dict[int, tuple[str, str, str]] = {}
        for interval in intervals:
            key = strata.stratum_key(
                interval.perigee_altitude_km,
                interval.inclination_deg,
                interval.eccentricity,
                interval.span_days,
            )
            curve_key = str(strata.curve_bin(interval.inclination_deg))
            zoom_index = strata.zoom_bin(interval.inclination_deg)
            zoom_key = None if zoom_index is None else str(zoom_index)
            cells.setdefault(key, _cell())[0] += 1
            curve.setdefault(curve_key, _cell())[0] += 1
            if zoom_key is not None:
                zoom.setdefault(zoom_key, _cell())[0] += 1
            by_start[interval.start_ms] = (key, curve_key, zoom_key)

        for policy, corroboration in (("On", True), ("Off", False)):
            events = oc.detect_object_events(
                intervals,
                kappa=KAPPA,
                expectations=expectations,
                record=catalog.get(norad, {}),
                _inclination_corroboration=corroboration,
            )
            base = POLICY_OFFSET["on" if corroboration else "off"]
            for event in events:
                if event.signature in NON_PROPULSIVE_SIGNATURES:
                    continue
                totals[f"{group}Flags{policy}"] += 1
                located = by_start.get(event.start_ms)
                if located is None:
                    # An event whose interval is not in the exposure map would
                    # mean the detector and this tally disagree about the
                    # population. That is a defect, not a rounding difference.
                    raise RuntimeError(
                        f"event at {event.start_ms} for NORAD {norad} has no matching interval"
                    )
                key, curve_key, zoom_key = located
                tripped = {test.element for test in event.tests if test.tripped}
                for store, store_key in ((cells, key), (curve, curve_key), (zoom, zoom_key)):
                    if store_key is None:
                        continue
                    cell = store.setdefault(store_key, _cell())
                    cell[base] += 1
                    if "inclination" in tripped:
                        cell[base + 1] += 1
                        if tripped == {"inclination"}:
                            cell[base + 2] += 1
                if "inclination" in tripped:
                    totals[f"{group}Inclination{policy}"] += 1
                    if tripped == {"inclination"}:
                        totals[f"{group}InclinationOnly{policy}"] += 1

        sink.write(json.dumps({
            "norad": norad,
            "group": group,
            "rows": len(rows),
            "intervals": len(intervals),
            "cells": cells,
            "curve": curve,
            "zoom": zoom,
        }, separators=(",", ":")) + "\n")
        last_norad = norad
        processed += 1
        if processed % 100 == 0:
            sink.flush()
            cursor_path.write_text(json.dumps({
                "lastNorad": last_norad,
                "totals": totals,
                "digestState": digest.digest().hex(),
                "processed": processed,
            }))
            print(
                f"{processed}/{len(remaining)} last={last_norad} "
                f"{round(time.monotonic() - started, 1)}s {totals}",
                flush=True,
            )
    sink.close()
    cursor_path.write_text(json.dumps({
        "lastNorad": last_norad,
        "totals": totals,
        "digestState": digest.digest().hex(),
        "processed": processed,
    }))

    summary = {
        "complete": not stopped_early,
        "selection": (
            f"norad % {args.modulus} == 0, {args.min_norad} < norad <= {args.max_norad}, "
            f"object_type in {IN_SCOPE}, whole retained histories"
        ),
        "modulus": args.modulus,
        "minNorad": args.min_norad,
        "maxNorad": args.max_norad,
        "selectedObjects": len(facts),
        "processedObjectsThisRun": processed,
        "resumedAfterNorad": resume_after,
        "totals": totals,
        "inputDigest": digest.hexdigest(),
        "wallSeconds": time.monotonic() - started,
        "cpuSeconds": time.process_time() - cpu_started,
        "nice": os.getpriority(os.PRIO_PROCESS, 0),
        "detectorFlags": oc.detector_flags(),
        "kappa": KAPPA,
        "policies": {
            "on": "production HEAD, high-inclination energy corroboration active (56eef64)",
            "off": "detect_object_events(_inclination_corroboration=False), the "
                   "pre-corroboration detector the inclination finding was made in",
        },
        "cellLayout": [
            "intervals", "flagsOn", "inclinationOn", "inclinationOnlyOn",
            "flagsOff", "inclinationOff", "inclinationOnlyOff",
        ],
        "minimumIntervals": MINIMUM_INTERVALS,
        "budgetSeconds": args.budget_seconds,
        "hardSeconds": args.hard_seconds,
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    print("SUMMARY", json.dumps(summary["totals"]), flush=True)
    print("COMPLETE" if summary["complete"] else "INCOMPLETE-RESUMABLE", flush=True)
    return 0 if summary["complete"] else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modulus", type=int, default=5)
    parser.add_argument("--min-norad", type=int, default=0)
    parser.add_argument("--max-norad", type=int, default=2147483647)
    parser.add_argument("--out", required=True)
    parser.add_argument("--budget-seconds", type=float, default=3600.0)
    parser.add_argument("--hard-seconds", type=float, default=3660.0)
    parser.add_argument("--page-rows", type=int, default=8192)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    return measure(args)


if __name__ == "__main__":
    raise SystemExit(main())
