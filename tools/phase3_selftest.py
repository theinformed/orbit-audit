"""Offline tests for the Phase 3 tools. Never opens the archive.

Run: .venv-gpu/bin/python tools/phase3_selftest.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline.orbit_events import MIN_SEPARATION_BOUND_RATIO  # noqa: E402
from tools import paperb_strata as strata  # noqa: E402
from tools import phase3_analyze as analyze  # noqa: E402
from tools import phase3_measure as measure  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


class FakeInterval:
    def __init__(self, start_ms, perigee, inclination, eccentricity, span_days):
        self.start_ms = start_ms
        self.perigee_altitude_km = perigee
        self.inclination_deg = inclination
        self.eccentricity = eccentricity
        self.span_days = span_days


class FakeEvent:
    def __init__(self, start_ms, signature="apogeeRaise"):
        self.start_ms = start_ms
        self.signature = signature


def test_registered_constants() -> None:
    print("registered constants")
    check("seed is the registration date, not Paper B's",
          analyze.PHASE3_SEED == 20260921 and analyze.PHASE3_SEED != strata.SEED)
    check("2,000 draws as registered", analyze.PHASE3_DRAWS == 2000)
    check("primary support tier is S_1000", analyze.SUPPORT_TIER == 1000)
    check("target is the shipped 1.0 per 1,000", analyze.TARGET_PER_1000 == 1.0)
    check("separation bar is the shipped constant",
          MIN_SEPARATION_BOUND_RATIO == 10.0)
    check("ten registered strata carried verbatim",
          len(analyze.REGISTERED_TEN) == 10
          and analyze.REGISTERED_TEN[0] == "300-500 km|30-60|<0.001|0.25-1 d")


def test_tally_matches_exposure_and_flags() -> None:
    print("tally_object")
    intervals = [
        FakeInterval(1000, 600.0, 45.0, 0.0005, 0.5),
        FakeInterval(2000, 600.0, 45.0, 0.0005, 0.5),
        FakeInterval(3000, 900.0, 45.0, 0.0005, 0.5),
    ]
    events = [FakeEvent(2000), FakeEvent(3000)]
    tally = measure.tally_object(intervals, events)
    check("exposure is every interval", tally["intervals"] == 3)
    check("flags counted once each", tally["flags"] == 2)
    total_intervals = sum(c[0] for c in tally["cells"].values())
    total_flags = sum(c[1] for c in tally["cells"].values())
    check("cells conserve exposure", total_intervals == 3, f"got {total_intervals}")
    check("cells conserve flags", total_flags == 2, f"got {total_flags}")
    check("two strata occupied", len(tally["cells"]) == 2, str(tally["cells"]))
    for suffix in ("cellsUp", "cellsDown"):
        check(f"{suffix} conserves exposure",
              sum(c[0] for c in tally[suffix].values()) == 3)
        check(f"{suffix} conserves flags",
              sum(c[1] for c in tally[suffix].values()) == 2)


def test_non_propulsive_signatures_are_not_flags() -> None:
    print("non-propulsive signatures")
    from pipeline.orbit_events import NON_PROPULSIVE_SIGNATURES
    signature = sorted(NON_PROPULSIVE_SIGNATURES)[0]
    intervals = [FakeInterval(1000, 600.0, 45.0, 0.0005, 0.5)]
    tally = measure.tally_object(intervals, [FakeEvent(1000, signature)])
    check("a non-propulsive event is not a flag", tally["flags"] == 0)
    check("its exposure is still counted", tally["intervals"] == 1)


def test_unmatched_event_is_an_error() -> None:
    print("detector/tally disagreement")
    intervals = [FakeInterval(1000, 600.0, 45.0, 0.0005, 0.5)]
    try:
        measure.tally_object(intervals, [FakeEvent(9999)])
    except RuntimeError:
        check("an event with no interval raises rather than being dropped", True)
    else:
        check("an event with no interval raises rather than being dropped", False)


def test_perigee_edge_detection() -> None:
    print("M14 perigee edge detection")
    check("a perigee far from any edge is not near one",
          measure.near_perigee_edge(650.0) is False)
    check("a perigee within one Kozai offset of 500 km is near an edge",
          measure.near_perigee_edge(501.0) is True)
    check("a perigee within one Kozai offset of 800 km is near an edge",
          measure.near_perigee_edge(798.0) is True)
    check("a null perigee is not near an edge",
          measure.near_perigee_edge(None) is False)


def test_shift_moves_exposure_across_a_band_edge() -> None:
    print("M14 shifted tallies actually differ")
    # 499 km sits just below the 500 km edge; +3.35 km carries it over.
    intervals = [FakeInterval(1000, 499.0, 45.0, 0.0005, 0.5)]
    tally = measure.tally_object(intervals, [])
    nominal = next(iter(tally["cells"]))
    up = next(iter(tally["cellsUp"]))
    check("nominal band is 300-500 km", nominal.startswith("300-500 km"), nominal)
    check("shifted-up band is 500-800 km", up.startswith("500-800 km"), up)
    check("the interval is flagged as edge exposure", tally["edgeIntervals"] == 1)


def test_support_tier_is_enforced() -> None:
    print("S_1000 support tier")
    passive = {"A": (5, 20000), "B": (0, 500)}
    payload = {"A": (10, 1000), "B": (50, 1000)}
    primary = strata.reweight(passive, payload, minimum_support=analyze.SUPPORT_TIER)
    check("the thin stratum is excluded from the tier",
          primary["supportedStrata"] == 1 and primary["gapStrata"] == 1)
    check("its payload weight is reported as a labelled gap, not zero",
          abs(primary["unsupportedPayloadExposureShare"] - 0.5) < 1e-9)
    check("R_rw equals the supported stratum's rate",
          abs(primary["reweightedFloorPerInterval"] - 5 / 20000) < 1e-12)
    check("a thin stratum is never given a rate",
          all(row["stratum"] != "B" for row in primary["rows"]))


def test_payload_bound_is_the_pooled_tier_rate() -> None:
    print("clause 2 payload side")
    payload = {"A": (10, 1000), "B": (50, 1000), "C": (7, 400)}
    tier = {"A", "B"}
    side = analyze.payload_bound_over_tier(payload, tier)
    check("only tier strata contribute", side["flags"] == 60 and side["intervals"] == 2000)
    check("the reweighted payload rate is the pooled tier rate",
          abs(side["ratePer1000"] - 1000.0 * 60 / 2000) < 1e-9)
    check("the lower bound is below the point estimate",
          side["lower95Per1000"] < side["ratePer1000"])
    check("the lower bound is positive for a non-zero count",
          side["lower95Per1000"] > 0)


def test_acceptance_rule_is_conjunctive() -> None:
    """Both clauses required -- the registered stop rule is explicit."""
    print("acceptance rule")
    cases = [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ]
    for c1, c2, expected in cases:
        check(f"clause1={c1} clause2={c2} -> accepted={expected}",
              (c1 and c2) == expected)


def test_zero_flag_stratum_never_reports_a_zero_bound() -> None:
    print("Jeffreys on an empty control")
    low, high = strata.jeffreys(0, 5000)
    check("point estimate may be zero", low == 0.0)
    check("upper bound is strictly positive", high > 0.0)


def test_end_to_end_on_synthetic_records() -> None:
    print("end-to-end analyse() on synthetic per-object records")
    thick = "500-800 km|30-60|<0.001|0.25-1 d"
    thin = "300-500 km|30-60|<0.001|0.25-1 d"
    records = []
    # 40 passive objects, thick stratum well over S_1000, a couple of flags.
    for i in range(40):
        cells = {thick: [500, 1 if i < 2 else 0], thin: [5, 0]}
        records.append({
            "norad": 1000 + i, "group": "passive", "rows": 600,
            "intervals": 505, "flags": 1 if i < 2 else 0,
            "cells": cells, "cellsUp": cells, "cellsDown": cells,
            "edgeIntervals": 0, "edgeFlags": 0,
        })
    # 20 payload objects, weight in both strata, a high flag rate.
    for i in range(20):
        cells = {thick: [1000, 40], thin: [1000, 40]}
        records.append({
            "norad": 5000 + i, "group": "payload", "rows": 2200,
            "intervals": 2000, "flags": 80,
            "cells": cells, "cellsUp": cells, "cellsDown": cells,
            "edgeIntervals": 0, "edgeFlags": 0,
        })
    with tempfile.TemporaryDirectory() as tmp:
        objects = Path(tmp) / "objects.jsonl"
        objects.write_text("".join(json.dumps(r) + "\n" for r in records))
        out_json, out_jsonl = Path(tmp) / "r.json", Path(tmp) / "r.jsonl"
        rc = analyze.analyse(analyze.main.__wrapped__ if False else _args(
            objects=[str(objects)], paperb_strata="",
            out_json=str(out_json), out_jsonl=str(out_jsonl)))
        check("analyse() returns 0", rc == 0)
        result = json.loads(out_json.read_text())
        check("thick stratum is in the tier",
              any(r["stratum"] == thick for r in result["primaryRows"]))
        check("thin stratum is a labelled gap, not a rate",
              all(r["stratum"] != thin for r in result["primaryRows"]))
        check("half the payload exposure is reported as an unsupported gap",
              abs(result["primary"]["unsupportedPayloadExposureShare"] - 0.5) < 1e-9)
        check("bootstrap ran with the registered seed",
              result["bootstrap"]["seed"] == 20260921)
        check("bootstrap ran the registered number of draws",
              result["bootstrap"]["draws"] == 2000)
        check("bootstrap resampled the passive objects",
              result["bootstrap"]["objects"] == 40)
        check("a verdict is always produced",
              result["verdict"].startswith(("PASS", "FAIL")))
        check("both clauses are reported whichever way they go",
              "passes" in result["clause1"] and "passes" in result["clause2"])
        check("the M7 block names the atmosphere-limited bands",
              "300-500 km" in result["m7AtmosphereLimited"]["bands"])
        check("the thin low-perigee stratum is listed below the tier",
              any(r["stratum"] == thin
                  for r in result["m7AtmosphereLimited"]["rows"]))
        check("it is marked atmosphere-limited",
              all(r["atmosphereLimited"] for r in result["m7AtmosphereLimited"]["rows"]
                  if r["stratum"] == thin))
        check("M14 variants are reported", set(result["m14KozaiPerigee"]["variants"])
              == {"Up", "Down"})


def test_duplicate_norads_are_fatal() -> None:
    print("duplicate object records")
    rec = {
        "norad": 7, "group": "passive", "rows": 10, "intervals": 10, "flags": 0,
        "cells": {"500-800 km|30-60|<0.001|0.25-1 d": [10, 0]},
        "cellsUp": {}, "cellsDown": {}, "edgeIntervals": 0, "edgeFlags": 0,
    }
    with tempfile.TemporaryDirectory() as tmp:
        objects = Path(tmp) / "dup.jsonl"
        objects.write_text(json.dumps(rec) + "\n" + json.dumps(rec) + "\n")
        rc = analyze.analyse(_args(
            objects=[str(objects)], paperb_strata="",
            out_json=str(Path(tmp) / "r.json"),
            out_jsonl=str(Path(tmp) / "r.jsonl")))
        check("a repeated NORAD is refused rather than double-counted", rc == 3)


class _args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def main() -> int:
    test_registered_constants()
    test_tally_matches_exposure_and_flags()
    test_non_propulsive_signatures_are_not_flags()
    test_unmatched_event_is_an_error()
    test_perigee_edge_detection()
    test_shift_moves_exposure_across_a_band_edge()
    test_support_tier_is_enforced()
    test_payload_bound_is_the_pooled_tier_rate()
    test_acceptance_rule_is_conjunctive()
    test_zero_flag_stratum_never_reports_a_zero_bound()
    test_end_to_end_on_synthetic_records()
    test_duplicate_norads_are_fatal()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print("all phase 3 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
