"""Phase 3: the registered covariate-aware gate measurement.

Computes exactly what `docs/phase3-preregistration-20260921.md` registers and
nothing else:

- Section 1 estimand: `R_rw = sum_{s in S_1000} w_s * r_s`, the passive
  per-stratum false-alarm rate carried onto the **payload** covariate
  distribution, restricted to the `>=1,000-passive-interval` support tier as
  the PRIMARY estimand.
- Section 1 uncertainty: the object-level clustered nonparametric bootstrap,
  2,000 resamples, **seed 20260921**.
- Section 2 acceptance rule, both clauses required:
    1. `R_rw`'s primary bootstrap 95% upper bound < `targetRatePerInterval`
       (0.001 per interval, i.e. 1.0 per 1,000).
    2. reweighted separation >= `MIN_SEPARATION_BOUND_RATIO` (10.0), read
       bound-to-bound exactly as `orbit_events.separation_verdict` reads it:
       payload LOWER bound over passive UPPER bound.

Every estimator is **imported** from `tools/paperb_strata.py` rather than
reimplemented, because the registration says Phase 3 reuses "Paper B's
registered machinery without modification" and a second implementation of a
registered estimator is a second chance to get it subtly different.
`MIN_SEPARATION_BOUND_RATIO` and the target rate are imported from the
shipped detector for the same reason: Phase 3 applies the existing standard to
a new quantity, it does not restate the standard.

Two labelled POST-HOC diagnostics are reported alongside, both with **no
decision weight**, both answering reviewer findings rather than the
registration:

- **M14 (Kozai)**: the estimand recomputed on the perigee-shifted tallies, plus
  the share of exposure sitting within one Kozai offset of a perigee band edge.
- **M7 (atmosphere-limited strata)**: which payload-weighted strata remain
  below `S_1000` when the sample is the ENTIRE archive, and how much payload
  weight they carry. On a full-archive pass this is the decisive form of the
  question, because there is no remaining sample to draw: a stratum short here
  is short because the exposure does not exist, not because it was not looked
  for.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline.orbit_events import MIN_SEPARATION_BOUND_RATIO  # noqa: E402
from tools import paperb_strata as strata  # noqa: E402

# Registered in section 1 of the Phase 3 pre-registration. Not Paper B's 20260920:
# "so that no single bootstrap draw is ever reused across two registered decisions".
PHASE3_SEED = 20260921
PHASE3_DRAWS = 2000
SUPPORT_TIER = 1000  # S_1000, the registered PRIMARY support tier
TARGET_PER_1000 = 1000.0 * strata.TARGET_RATE_PER_INTERVAL

# The ten strata named in section 3 of the registration, in the registered
# order. The results table is keyed to these, as deliverable 2 requires.
REGISTERED_TEN: tuple[str, ...] = (
    "300-500 km|30-60|<0.001|0.25-1 d",
    ">2000 km|0-1|<0.001|0.25-1 d",
    "500-800 km|30-60|<0.001|<0.25 d",
    "300-500 km|90-120|<0.001|0.25-1 d",
    ">2000 km|0-1|<0.001|1-2 d",
    "300-500 km|30-60|<0.001|<0.25 d",
    ">2000 km|0-1|<0.001|<0.25 d",
    "500-800 km|30-60|<0.001|1-2 d",
    "300-500 km|30-60|<0.001|1-2 d",
    "300-500 km|90-120|<0.001|<0.25 d",
)

# M7. Perigee bands in which passive exposure is bounded by atmospheric
# lifetime rather than by observation effort. Debris at these altitudes decays
# in months to a few years and the rate is strongly solar-cycle dependent, so a
# denser pass cannot manufacture exposure the atmosphere has already removed.
ATMOSPHERE_LIMITED_BANDS: tuple[str, ...] = ("<300 km", "300-500 km")


def load_objects(paths: list[Path]) -> tuple[dict, dict, list[dict], list[dict], dict]:
    """Aggregate per-object records into the four tallies the analysis needs."""
    passive: dict[str, list[int]] = {}
    payload: dict[str, list[int]] = {}
    passive_objects: list[dict[str, tuple[int, int]]] = []
    payload_objects: list[dict[str, tuple[int, int]]] = []
    shifted = {
        "Up": ({}, {}),
        "Down": ({}, {}),
    }
    meta = {
        "objects": 0, "passiveObjects": 0, "payloadObjects": 0,
        "passiveIntervals": 0, "payloadIntervals": 0,
        "passiveFlags": 0, "payloadFlags": 0,
        "passiveEdgeIntervals": 0, "payloadEdgeIntervals": 0,
        "passiveEdgeFlags": 0, "payloadEdgeFlags": 0,
        "duplicateNorads": 0,
    }
    seen: set[int] = set()
    for path in paths:
        with path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                norad = record["norad"]
                if norad in seen:
                    # Two shards overlapping, or a resume that double-counted.
                    # Either is silently doubled exposure, so it is an error.
                    meta["duplicateNorads"] += 1
                    continue
                seen.add(norad)
                group = record["group"]
                target = passive if group == "passive" else payload
                bucket = passive_objects if group == "passive" else payload_objects
                per_object: dict[str, tuple[int, int]] = {}
                for key, (intervals, flags) in record["cells"].items():
                    slot = target.setdefault(key, [0, 0])
                    slot[0] += flags
                    slot[1] += intervals
                    per_object[key] = (flags, intervals)
                bucket.append((norad, per_object))
                for suffix in ("Up", "Down"):
                    store = shifted[suffix][0 if group == "passive" else 1]
                    for key, (intervals, flags) in record[f"cells{suffix}"].items():
                        slot = store.setdefault(key, [0, 0])
                        slot[0] += flags
                        slot[1] += intervals
                meta["objects"] += 1
                meta[f"{group}Objects"] += 1
                meta[f"{group}Intervals"] += record["intervals"]
                meta[f"{group}Flags"] += record["flags"]
                meta[f"{group}EdgeIntervals"] += record["edgeIntervals"]
                meta[f"{group}EdgeFlags"] += record["edgeFlags"]
    # The clustered bootstrap resamples objects BY INDEX, so the order of this
    # list is part of the estimator's input: shuffle it and the same seed draws
    # a different set of objects and returns a different interval. Object order
    # here is the order records were read, which depends on how many shards the
    # extraction was split into and what order their files were passed on the
    # command line -- none of which is part of the registered estimand. Sorting
    # by NORAD pins it, so the reported interval is reproducible from the same
    # archive regardless of how the extraction was parallelised.
    passive_objects.sort(key=lambda item: item[0])
    payload_objects.sort(key=lambda item: item[0])
    passive_objects[:] = [cells for _, cells in passive_objects]
    payload_objects[:] = [cells for _, cells in payload_objects]

    to_pairs = lambda d: {k: (v[0], v[1]) for k, v in d.items()}
    meta["shifted"] = {
        suffix: (to_pairs(a), to_pairs(b)) for suffix, (a, b) in shifted.items()
    }
    return to_pairs(passive), to_pairs(payload), passive_objects, payload_objects, meta


def payload_bound_over_tier(payload: dict, tier_keys: set[str]) -> dict:
    """The reweighted payload rate and its Jeffreys 95% bounds over `S_1000`.

    `R^L_rw = sum_s w_s * r^L_s` with `w_s = n_s^L / sum n_s^L` is, by
    construction, the POOLED payload rate over the same strata -- the weights
    are the payload exposure shares, so the weighted mean of the per-stratum
    payload rates is exactly the pooled payload rate. The Jeffreys interval on
    the pooled counts is therefore the interval on the reweighted quantity, and
    it is the same estimator `_control_rates` already applies to get
    `payload_lower` for `separation_verdict`.
    """
    flags = sum(f for k, (f, _) in payload.items() if k in tier_keys)
    intervals = sum(n for k, (_, n) in payload.items() if k in tier_keys)
    low, high = strata.jeffreys(flags, intervals)
    return {
        "flags": flags,
        "intervals": intervals,
        "ratePer1000": strata.rate_per_1000(flags, intervals),
        "jeffreys95Per1000": [1000.0 * low, 1000.0 * high],
        "lower95Per1000": 1000.0 * low,
    }


def payload_bootstrap_lower(
    payload_objects: list[dict], tier_keys: set[str], weights: dict[str, float]
) -> dict:
    """SECONDARY, labelled: clustered payload-object bootstrap of `R^L_rw`.

    The registration's primary bootstrap resamples PASSIVE objects, because the
    estimand is a passive rate. The payload side of clause 2 has no registered
    clustered interval, so the shipped `separation_verdict` estimator (Jeffreys
    on pooled payload counts) is the primary here and this is reported beside
    it. If the two disagree about clause 2, that disagreement is reported.
    """
    result = strata.bootstrap_reweighted(
        payload_objects, weights, draws=PHASE3_DRAWS, seed=PHASE3_SEED
    )
    result["method"] = (
        "SECONDARY, not registered: object-level clustered bootstrap of the "
        "reweighted PAYLOAD rate, percentile"
    )
    return result


def analyse(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.objects]
    passive, payload, passive_objects, payload_objects, meta = load_objects(paths)
    if meta["duplicateNorads"]:
        print(
            f"FATAL: {meta['duplicateNorads']} duplicate NORAD record(s) across inputs; "
            "that is doubled exposure, not a rounding difference",
            file=sys.stderr,
        )
        return 3

    # ---- The registered estimand, section 1 -------------------------------
    primary = strata.reweight(passive, payload, minimum_support=SUPPORT_TIER)
    context = strata.reweight(passive, payload, minimum_support=1)

    weights = {row["stratum"]: row["weight"] for row in primary["rows"]}
    tier_keys = set(weights)
    bootstrap = strata.bootstrap_reweighted(
        passive_objects, weights, draws=PHASE3_DRAWS, seed=PHASE3_SEED
    )

    # ---- The registered acceptance rule, section 2 ------------------------
    upper = bootstrap["high95Per1000"]
    clause1 = {
        "requirement": (
            "R_rw primary clustered-bootstrap 95% upper bound below the published "
            "target of 1.0 per 1,000 usable intervals"
        ),
        "upperBoundPer1000": upper,
        "targetPer1000": TARGET_PER_1000,
        "passes": bool(upper is not None and upper < TARGET_PER_1000),
    }

    payload_side = payload_bound_over_tier(payload, tier_keys)
    payload_boot = payload_bootstrap_lower(payload_objects, tier_keys, weights)
    ratio = (
        None if not upper or upper <= 0 else payload_side["lower95Per1000"] / upper
    )
    ratio_secondary = (
        None
        if not upper or upper <= 0 or payload_boot["low95Per1000"] is None
        else payload_boot["low95Per1000"] / upper
    )
    clause2 = {
        "requirement": (
            "reweighted separation, payload LOWER bound over R_rw UPPER bound, at "
            f"least {MIN_SEPARATION_BOUND_RATIO}x -- the shipped "
            "separation_verdict logic applied to the reweighted quantity"
        ),
        "payloadLower95Per1000": payload_side["lower95Per1000"],
        "passiveUpper95Per1000": upper,
        "boundRatio": ratio,
        "requiredBoundRatio": MIN_SEPARATION_BOUND_RATIO,
        "passes": bool(ratio is not None and ratio >= MIN_SEPARATION_BOUND_RATIO),
        "secondaryBoundRatio": ratio_secondary,
        "secondaryPasses": bool(
            ratio_secondary is not None and ratio_secondary >= MIN_SEPARATION_BOUND_RATIO
        ),
    }

    accepted = clause1["passes"] and clause2["passes"]

    # ---- M7: what the full archive could not fill -------------------------
    short = []
    for key, (payload_flags, payload_intervals) in payload.items():
        if payload_intervals <= 0 or key in tier_keys:
            continue
        passive_n = passive.get(key, (0, 0))[1]
        short.append({
            "stratum": key,
            "perigeeBand": key.split("|")[0],
            "passiveIntervals": passive_n,
            "payloadIntervals": payload_intervals,
            "payloadWeightOfTotal": payload_intervals / meta["payloadIntervals"],
            "shortfallToS1000": max(0, SUPPORT_TIER - passive_n),
            "atmosphereLimited": key.split("|")[0] in ATMOSPHERE_LIMITED_BANDS,
        })
    short.sort(key=lambda r: -r["payloadIntervals"])
    atmosphere = [r for r in short if r["atmosphereLimited"]]
    m7 = {
        "note": (
            "POST-HOC, not pre-registered. On a full-archive pass there is no "
            "remaining sample to draw, so a stratum below S_1000 here is short "
            "because the exposure does not exist, not because it was not sought."
        ),
        "strataBelowS1000": len(short),
        "payloadWeightBelowS1000": sum(r["payloadWeightOfTotal"] for r in short),
        "atmosphereLimitedStrata": len(atmosphere),
        "atmosphereLimitedPayloadWeight": sum(
            r["payloadWeightOfTotal"] for r in atmosphere
        ),
        "atmosphereLimitedShareOfGap": (
            sum(r["payloadWeightOfTotal"] for r in atmosphere)
            / sum(r["payloadWeightOfTotal"] for r in short)
            if short else 0.0
        ),
        "bands": ATMOSPHERE_LIMITED_BANDS,
        "rows": short[:40],
    }

    # M7, the measured form. The claim "passive exposure at low perigee is
    # bounded by atmospheric lifetime, not by observation effort" is testable
    # from this pass without any atmosphere model: it predicts that the ratio
    # of passive to payload exposure COLLAPSES as perigee falls, because the
    # atmosphere removes fragments on a timescale of months there while
    # payloads in the same shell are drag-compensated and stay. A denser pass
    # cannot change that ratio; only the atmosphere and the solar cycle can.
    band_summary: dict[str, dict] = {}

    def _band(name: str) -> dict:
        return band_summary.setdefault(name, {
            "passiveIntervals": 0, "passiveFlags": 0, "payloadIntervals": 0,
            "payloadStrata": 0, "strataBelowTier": 0, "payloadWeightBelowTier": 0.0,
        })

    for key, (flags, intervals) in passive.items():
        slot = _band(key.split("|")[0])
        slot["passiveIntervals"] += intervals
        slot["passiveFlags"] += flags
    for key, (_, intervals) in payload.items():
        if intervals <= 0:
            continue
        slot = _band(key.split("|")[0])
        slot["payloadIntervals"] += intervals
        slot["payloadStrata"] += 1
        if key not in tier_keys:
            slot["strataBelowTier"] += 1
            slot["payloadWeightBelowTier"] += intervals / meta["payloadIntervals"]
    for name, slot in band_summary.items():
        slot["passivePerPayloadExposure"] = (
            slot["passiveIntervals"] / slot["payloadIntervals"]
            if slot["payloadIntervals"] else None
        )
        slot["atmosphereLimited"] = name in ATMOSPHERE_LIMITED_BANDS
    m7["perigeeBandSummary"] = band_summary

    # ---- M14: the Kozai perigee offset, as a measured sensitivity ---------
    m14 = {
        "note": (
            "POST-HOC, not pre-registered, no decision weight. Derived perigee "
            "inherits an inclination-dependent Kozai offset (+3.35 km at i=0, "
            "-1.68 km at i=90, at 500 km altitude); perigee is a stratification "
            "factor, so the offset can move exposure across a band edge."
        ),
        "edgeExposureSharePassive": (
            meta["passiveEdgeIntervals"] / meta["passiveIntervals"]
            if meta["passiveIntervals"] else 0.0
        ),
        "edgeExposureSharePayload": (
            meta["payloadEdgeIntervals"] / meta["payloadIntervals"]
            if meta["payloadIntervals"] else 0.0
        ),
        "edgeFlagsPassive": meta["passiveEdgeFlags"],
        "edgeFlagsPayload": meta["payloadEdgeFlags"],
        "variants": {},
    }
    for suffix in ("Up", "Down"):
        s_passive, s_payload = meta["shifted"][suffix]
        shifted_primary = strata.reweight(
            s_passive, s_payload, minimum_support=SUPPORT_TIER
        )
        m14["variants"][suffix] = {
            "reweightedFloorPer1000": shifted_primary["reweightedFloorPer1000"],
            "rawFloorPer1000": shifted_primary["rawFloorPer1000"],
            "ratioToRaw": shifted_primary["ratioToRaw"],
            "supportedStrata": shifted_primary["supportedStrata"],
            "unsupportedPayloadExposureShare":
                shifted_primary["unsupportedPayloadExposureShare"],
        }

    # ---- The registered ten, before and after -----------------------------
    prior = {}
    if args.paperb_strata:
        for line in Path(args.paperb_strata).open():
            row = json.loads(line)
            if row.get("kind") == "stratum" and row.get("policy") == "on":
                prior[row["stratum"]] = row
    ten = []
    for key in REGISTERED_TEN:
        before = prior.get(key, {})
        passive_n = passive.get(key, (0, 0))[1]
        passive_k = passive.get(key, (0, 0))[0]
        ten.append({
            "stratum": key,
            "sampledPassiveIntervals": before.get("passiveIntervals"),
            "sampledPassiveFlags": before.get("passiveFlags"),
            "fullPassiveIntervals": passive_n,
            "fullPassiveFlags": passive_k,
            "growthFactor": (
                passive_n / before["passiveIntervals"]
                if before.get("passiveIntervals") else None
            ),
            "payloadIntervals": payload.get(key, (0, 0))[1],
            "payloadWeightOfTotal": (
                payload.get(key, (0, 0))[1] / meta["payloadIntervals"]
                if meta["payloadIntervals"] else 0.0
            ),
            "reachedS1000": passive_n >= SUPPORT_TIER,
            "inPrimaryTier": key in tier_keys,
        })

    result = {
        "preregistration": "docs/phase3-preregistration-20260921.md",
        "estimand": (
            "payload-covariate-reweighted passive false-alarm floor at the "
            "S_1000 support tier, shipping detector (corroboration active)"
        ),
        "seed": PHASE3_SEED,
        "draws": PHASE3_DRAWS,
        "supportTier": SUPPORT_TIER,
        "meta": {k: v for k, v in meta.items() if k != "shifted"},
        "primary": {k: v for k, v in primary.items() if k != "rows"},
        "primaryRows": primary["rows"],
        "contextTierS1": {k: v for k, v in context.items() if k not in ("rows", "gaps")},
        "bootstrap": bootstrap,
        "payloadSide": payload_side,
        "payloadBootstrap": payload_boot,
        "clause1": clause1,
        "clause2": clause2,
        "accepted": accepted,
        "verdict": (
            "PASS -- both registered clauses met"
            if accepted
            else "FAIL -- the covariate-aware gate does not yet ship"
        ),
        "registeredTen": ten,
        "m7AtmosphereLimited": m7,
        "m14KozaiPerigee": m14,
        "registeredConstants": {
            "targetRatePerInterval": strata.TARGET_RATE_PER_INTERVAL,
            "MIN_SEPARATION_BOUND_RATIO": MIN_SEPARATION_BOUND_RATIO,
        },
    }

    Path(args.out_json).write_text(json.dumps(result, indent=2))
    with Path(args.out_jsonl).open("w") as sink:
        for row in primary["rows"]:
            sink.write(json.dumps(dict(row, kind="stratum", tier="S_1000"),
                                  separators=(",", ":")) + "\n")
        for row in short:
            sink.write(json.dumps(dict(row, kind="belowTier"),
                                  separators=(",", ":")) + "\n")

    print(f"objects           {meta['objects']}")
    print(f"passive intervals {meta['passiveIntervals']:,} flags {meta['passiveFlags']:,}")
    print(f"payload intervals {meta['payloadIntervals']:,} flags {meta['payloadFlags']:,}")
    print(f"raw floor /1000   {primary['rawFloorPer1000']:.6f}")
    print(f"R_rw    /1000     {primary['reweightedFloorPer1000']:.6f}  "
          f"({primary['ratioToRaw']:.4f}x raw)")
    print(f"bootstrap 95%     [{bootstrap['low95Per1000']:.6f}, {upper:.6f}]  "
          f"seed {PHASE3_SEED}")
    print(f"S_1000 strata     {primary['supportedStrata']}  "
          f"gap payload share {primary['unsupportedPayloadExposureShare']:.5%}")
    print(f"clause 1 (<{TARGET_PER_1000}) {'PASS' if clause1['passes'] else 'FAIL'}")
    print(f"clause 2 (>={MIN_SEPARATION_BOUND_RATIO}x) "
          f"{'PASS' if clause2['passes'] else 'FAIL'} ratio="
          f"{'n/a' if ratio is None else format(ratio, '.4f')}")
    print(f"VERDICT           {result['verdict']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", nargs="+", required=True)
    parser.add_argument("--paperb-strata", default="docs/paperb-strata-20260920.jsonl")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-jsonl", required=True)
    args = parser.parse_args(argv)
    return analyse(args)


if __name__ == "__main__":
    raise SystemExit(main())
