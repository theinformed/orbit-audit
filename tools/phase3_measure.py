"""Phase 3: the full-archive, full-history passive-exposure extraction.

Registered in `docs/phase3-preregistration-20260921.md` section 3: a
covariate-targeted passive sampling pass that widens the `norad % 5 == 0`
systematic sample of Paper B. This module widens it to the limit -- **modulus
1, the entire retained archive** -- which is a strict superset of the targeted
oversample the registration names, and is the only version of that experiment
with no sampling headroom left behind it. That matters for the stop rule: a
stratum still short of `S_1000` after this pass cannot be filled by sampling
harder, because there is nothing left to sample.

Differences from `tools/paperb_measure.py`, both deliberate and both narrowing:

1. **One detector policy, not two.** Phase 3's estimand (section 1 of the
   registration) is defined on the detector that ships, i.e. high-inclination
   energy corroboration ACTIVE. Paper B ran the detector twice per object
   because its Analysis 2 needed the pre-corroboration state; Phase 3 has no
   Analysis 2. Dropping the second run is a scope reduction, not a method
   change, and it is what makes a 5x larger sample affordable inside the
   registered resource bounds.
2. **A perigee-offset sensitivity, carried as labelled extra cells.** Reviewer
   finding M14 observes that the archive's semi-major axis is derived
   Keplerian from the catalogue's Brouwer-Kozai mean motion with no Kozai
   transform, so the derived *perigee* inherits an inclination-dependent
   offset of about +3.35 km (i = 0) to -1.68 km (i = 90) at 500 km altitude.
   Perigee is a stratification factor here, so that offset can move an
   interval across a band edge. Every interval is therefore tallied three
   times -- at nominal perigee, at perigee + 3.35 km, and at perigee - 1.68 km
   -- so the effect on the stratum boundaries can be reported as a measured
   number instead of an assertion. The shifted tallies are a POST-HOC,
   NOT-PRE-REGISTERED diagnostic with no decision weight; the registered
   estimand is computed on the nominal tally alone.

Tallies are written PER OBJECT, for the same reason Paper B wrote them per
object: the registered primary interval is an object-level clustered
bootstrap, and that is impossible to compute from pre-aggregated cells.

Read-only throughout, through `open_archive_for_reading`, so it holds no write
lock and cannot block the ingest or the running `orbit_release` sweep.

Usage:

    nice -n 19 ionice -c3 .venv-gpu/bin/python tools/phase3_measure.py \
        --modulus 1 --min-norad 0 --max-norad 25000 \
        --out /tmp/phase3-20260921/part0 --budget-seconds 3600 --resume
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

# M14. The two extreme derived-perigee offsets the review quantifies at LEO,
# applied as a uniform shift rather than recomputed per interval: the point of
# the diagnostic is the WORST the band assignment can move, and a uniform
# shift of the whole population is the worst case for a band edge because it
# moves every interval near that edge in the same direction at once.
PERIGEE_OFFSETS_KM: tuple[tuple[str, float], ...] = (
    ("nominal", 0.0),
    ("up", 3.35),
    ("down", -1.68),
)
# The widest excursion in the review's table, used for the "how much exposure
# sits within one Kozai offset of a band edge" tally.
KOZAI_SPREAD_KM = 5.03

# Cell layout: [intervals, flags]. Phase 3's estimand needs exposure and the
# flag numerator, per population, per stratum, on the shipping detector. It
# does not need the inclination channel split, which is Analysis 2's business
# and is out of scope here.
CELL_WIDTH = 2


def _cell() -> list[int]:
    return [0] * CELL_WIDTH


def select_objects(db, modulus: int, minimum: int, maximum: int) -> dict[int, tuple[str, str]]:
    placeholders = ",".join("?" for _ in IN_SCOPE)
    modulus_clause = "" if modulus <= 1 else f"norad % {modulus} = 0 and "
    sql = (
        "select norad,name,object_type from object "
        f"where {modulus_clause}norad > ? and norad <= ? "
        f"and object_type in ({placeholders}) order by norad"
    )
    return {
        norad: (name, object_type)
        for norad, name, object_type in db.execute(sql, (minimum, maximum, *IN_SCOPE))
    }


def near_perigee_edge(perigee_km: float | None, spread_km: float = KOZAI_SPREAD_KM) -> bool:
    """Does this interval sit within one Kozai offset of a perigee band edge?

    Answers M14 in the only currency that matters for a stratified estimate:
    not "how big is the offset" but "how much exposure could the offset move
    into a different stratum".
    """
    if perigee_km is None:
        return False
    return strata.perigee_band(perigee_km - spread_km) != strata.perigee_band(
        perigee_km + spread_km
    )


def tally_object(intervals, events) -> dict:
    """Per-object cells under every registered and diagnostic binning.

    Split out from the archive loop so the offline self-test can drive it with
    synthetic intervals and never open the archive.
    """
    cells: dict[str, dict[str, list[int]]] = {name: {} for name, _ in PERIGEE_OFFSETS_KM}
    by_start: dict[int, dict[str, str]] = {}
    edge_intervals = 0
    edge_flags = 0

    for interval in intervals:
        keys = {}
        for name, offset in PERIGEE_OFFSETS_KM:
            perigee = interval.perigee_altitude_km
            shifted = None if perigee is None else perigee + offset
            key = strata.stratum_key(
                shifted,
                interval.inclination_deg,
                interval.eccentricity,
                interval.span_days,
            )
            keys[name] = key
            cells[name].setdefault(key, _cell())[0] += 1
        by_start[interval.start_ms] = keys
        if near_perigee_edge(interval.perigee_altitude_km):
            edge_intervals += 1
            by_start[interval.start_ms] = dict(keys, __edge__="1")

    flags = 0
    for event in events:
        if event.signature in NON_PROPULSIVE_SIGNATURES:
            continue
        located = by_start.get(event.start_ms)
        if located is None:
            # An event whose interval is not in the exposure map would mean the
            # detector and this tally disagree about the population. That is a
            # defect, not a rounding difference.
            raise RuntimeError(f"event at {event.start_ms} has no matching interval")
        flags += 1
        if located.get("__edge__"):
            edge_flags += 1
        for name, _ in PERIGEE_OFFSETS_KM:
            cells[name][located[name]][1] += 1

    return {
        "intervals": len(intervals),
        "flags": flags,
        "cells": cells["nominal"],
        "cellsUp": cells["up"],
        "cellsDown": cells["down"],
        "edgeIntervals": edge_intervals,
        "edgeFlags": edge_flags,
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
    # registered resource bounds forbid.
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
        "passiveFlags": 0, "payloadFlags": 0,
        "passiveEdgeIntervals": 0, "payloadEdgeIntervals": 0,
        "passiveEdgeFlags": 0, "payloadEdgeFlags": 0,
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
        # records on disk the saved totals do not know about. Resuming from the
        # cursor would then process those objects a SECOND time and append them
        # again: silently doubled exposure and doubled flags, with no error
        # anywhere. Truncate the file back to the cursor first. (Paper B hit
        # exactly this and fixed it at 46dee20; the fix is carried here rather
        # than rediscovered.)
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
    for norad, rows in oc.stream_object_rows(db, only=remaining, page_rows=args.page_rows):
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

        events = oc.detect_object_events(
            intervals,
            kappa=KAPPA,
            expectations=expectations,
            record=catalog.get(norad, {}),
            _inclination_corroboration=True,
        )
        tally = tally_object(intervals, events)
        totals[f"{group}Flags"] += tally["flags"]
        totals[f"{group}EdgeIntervals"] += tally["edgeIntervals"]
        totals[f"{group}EdgeFlags"] += tally["edgeFlags"]

        sink.write(json.dumps({
            "norad": norad,
            "group": group,
            "rows": len(rows),
            "intervals": tally["intervals"],
            "flags": tally["flags"],
            "cells": tally["cells"],
            "cellsUp": tally["cellsUp"],
            "cellsDown": tally["cellsDown"],
            "edgeIntervals": tally["edgeIntervals"],
            "edgeFlags": tally["edgeFlags"],
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
        "preregistration": "docs/phase3-preregistration-20260921.md",
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
        "policy": "production HEAD, high-inclination energy corroboration ACTIVE (56eef64)",
        "cellLayout": ["intervals", "flags"],
        "perigeeOffsetsKm": dict(PERIGEE_OFFSETS_KM),
        "kozaiSpreadKm": KOZAI_SPREAD_KM,
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
    parser.add_argument("--modulus", type=int, default=1)
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
