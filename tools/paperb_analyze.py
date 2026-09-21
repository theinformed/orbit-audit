"""Paper B: turn the per-object tallies into the registered tables and verdicts.

Reads whatever `tools/paperb_measure.py` wrote, applies exactly the estimators
and decision rules registered in `docs/paperb-preregistration-20260920.md`, and
writes three artefacts:

- `docs/paperb-strata-20260920.jsonl` - one line per stratum-level measurement;
- `docs/paperb-results-20260920.json` - the machine receipt and every verdict;
- markdown tables on stdout, for the results report.

It computes no estimator that the registration does not name, and it reports
every verdict the registration asks for whether or not the verdict is
convenient. The one thing it adds is labelled `postHoc` in the output and
carries no decision weight.

    .venv-gpu/bin/python tools/paperb_analyze.py --inputs /tmp/paperb-20260920/part*.objects.jsonl
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import paperb_strata as strata  # noqa: E402

POLICY_SLOT = {"on": 1, "off": 4}


def _load(paths: list[str]):
    """Aggregate the per-object lines, keeping the per-object passive detail.

    The per-object detail is retained only for PASSIVE objects, because the
    clustered bootstrap resamples passive objects and nothing else. Holding the
    payload detail as well would triple the memory for no estimator.
    """
    cells = {g: defaultdict(lambda: [0] * 7) for g in ("passive", "payload")}
    curve = {g: defaultdict(lambda: [0] * 7) for g in ("passive", "payload")}
    zoom = {g: defaultdict(lambda: [0] * 7) for g in ("passive", "payload")}
    passive_objects: list[dict[str, list[int]]] = []
    counts = defaultdict(int)
    for path in paths:
        with open(path) as handle:
            for line in handle:
                record = json.loads(line)
                group = record["group"]
                counts[f"{group}Objects"] += 1
                counts[f"{group}Intervals"] += record["intervals"]
                counts[f"{group}Rows"] += record["rows"]
                for store, source in (
                    (cells[group], record["cells"]),
                    (curve[group], record["curve"]),
                    (zoom[group], record["zoom"]),
                ):
                    for key, cell in source.items():
                        target = store[key]
                        for i, value in enumerate(cell):
                            target[i] += value
                if group == "passive":
                    passive_objects.append(record["cells"])
    return cells, curve, zoom, passive_objects, counts


def _split(store: dict[str, list[int]], policy: str) -> dict[str, tuple[int, int]]:
    """(flags, intervals) per stratum for one detector policy."""
    slot = POLICY_SLOT[policy]
    return {key: (cell[slot], cell[0]) for key, cell in store.items()}


def _split_only(store: dict[str, list[int]], policy: str) -> dict[str, tuple[int, int]]:
    """(inclination-only flags, intervals) per stratum for one policy."""
    slot = POLICY_SLOT[policy] + 2
    return {key: (cell[slot], cell[0]) for key, cell in store.items()}


def _collapse(counts: dict[str, tuple[int, int]], mapper) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for key, (flags, intervals) in counts.items():
        target = out[mapper(key)]
        target[0] += flags
        target[1] += intervals
    return {k: (v[0], v[1]) for k, v in out.items()}


def _object_cells(objects, policy: str):
    slot = POLICY_SLOT[policy]
    return [
        {key: (cell[slot], cell[0]) for key, cell in record.items()}
        for record in objects
    ]


def analysis_one(cells, passive_objects, policy: str) -> dict:
    passive = _split(cells["passive"], policy)
    payload = _split(cells["payload"], policy)
    primary = strata.reweight(passive, payload, minimum_support=1)
    strict = strata.reweight(passive, payload, minimum_support=1000)
    coarse = strata.reweight(
        _collapse(passive, strata.coarse_key), _collapse(payload, strata.coarse_key)
    )
    weights = {row["stratum"]: row["weight"] for row in primary["rows"]}
    objects = _object_cells(passive_objects, policy)
    bootstrap = strata.bootstrap_reweighted(
        objects, weights, draws=strata.BOOTSTRAP_DRAWS, seed=strata.SEED,
    )
    posterior = strata.posterior_composite(
        passive, weights, draws=strata.POSTERIOR_DRAWS, seed=strata.SEED
    )
    worst = strata.worst_case_fill(primary)

    # The registration says the >=1,000-interval support tier is reported
    # ALONGSIDE the >=1 tier, not instead of it, so it gets the same two
    # intervals. It does not and cannot change the registered verdict above,
    # which is computed on the >=1 tier; it is here so a reader can see whether
    # a failure is driven by strata that carry real information or by strata
    # that carry a handful of intervals.
    strict_weights = {row["stratum"]: row["weight"] for row in strict["rows"]}
    strict_bootstrap = strata.bootstrap_reweighted(
        objects, strict_weights, draws=strata.BOOTSTRAP_DRAWS, seed=strata.SEED,
    )
    strict_posterior = strata.posterior_composite(
        passive, strict_weights, draws=strata.POSTERIOR_DRAWS, seed=strata.SEED
    )

    # Where does the payload weight sit relative to how much passive evidence
    # supports it? A stratum carrying several percent of the payload population
    # on a few hundred passive intervals is the whole reason a clustered
    # bootstrap can run away, and naming those strata is more useful than
    # quoting the width of the interval they produce.
    thin = sorted(
        (row for row in primary["rows"] if row["passiveIntervals"] < 2000),
        key=lambda row: -row["weight"],
    )
    thin_weight = sum(row["weight"] for row in thin)

    target = strata.TARGET_RATE_PER_INTERVAL
    below_target = (
        primary["reweightedFloorPerInterval"] < target
        and bootstrap["high95Per1000"] is not None
        and bootstrap["high95Per1000"] / 1000.0 < target
    )
    within_two = primary["ratioToRaw"] is not None and primary["ratioToRaw"] <= 2.0
    coverage_ok = primary["unsupportedPayloadExposureShare"] <= 0.20
    if not below_target:
        verdict = "DOES NOT TRANSFER: the reweighted floor or its upper bound reaches the target"
    elif not within_two:
        verdict = ("SURVIVES WEAKENED: below target, but more than 2x the raw floor; "
                   "the paper must quote the reweighted floor")
    else:
        verdict = "SURVIVES: below target and within 2x the raw floor"
    return {
        "policy": policy,
        "primary": primary,
        "strictSupport1000": strict,
        "coarseSensitivityB": coarse,
        "worstCaseFillSensitivityA": worst,
        "bootstrapPrimaryInterval": bootstrap,
        "posteriorSecondaryInterval": posterior,
        "strictSupportBootstrap": strict_bootstrap,
        "strictSupportPosterior": strict_posterior,
        "thinSupportDiagnostic": {
            "definition": "supported strata carrying fewer than 2,000 passive intervals",
            "count": len(thin),
            "payloadWeightShare": thin_weight,
            "heaviest": thin[:12],
        },
        "decision": {
            "targetPerInterval": target,
            "belowTargetIncludingUpperBound": below_target,
            "withinTwiceRaw": within_two,
            "unsupportedCoverageWithin20Percent": coverage_ok,
            "verdict": verdict,
            "sufficientOnItsOwn": coverage_ok,
        },
    }


def _curve_rows(curve, policy: str) -> list[dict]:
    slot = POLICY_SLOT[policy]
    rows = []
    keys = sorted({int(k) for k in curve["passive"]} | {int(k) for k in curve["payload"]})
    for index in keys:
        low, high = strata.curve_bin_bounds(index)
        passive = curve["passive"].get(str(index), [0] * 7)
        payload = curve["payload"].get(str(index), [0] * 7)
        row = {
            "bin": index, "low": low, "high": high,
            "passiveIntervals": passive[0],
            "passiveFlags": passive[slot],
            "passiveInclination": passive[slot + 1],
            "passiveInclinationOnly": passive[slot + 2],
            "payloadIntervals": payload[0],
            "payloadFlags": payload[slot],
            "payloadInclination": payload[slot + 1],
            "payloadInclinationOnly": payload[slot + 2],
        }
        for population in ("passive", "payload"):
            n = row[f"{population}Intervals"]
            for measure in ("Flags", "Inclination", "InclinationOnly"):
                k = row[f"{population}{measure}"]
                row[f"{population}{measure}Per1000"] = strata.rate_per_1000(k, n)
                low_b, high_b = strata.jeffreys(k, n)
                row[f"{population}{measure}Jeffreys95Per1000"] = [1000.0 * low_b, 1000.0 * high_b]
        row["ratioInclinationOnly"] = strata.ratio_interval(
            row["passiveInclinationOnly"], row["passiveIntervals"],
            row["payloadInclinationOnly"], row["payloadIntervals"],
        )
        row["ratioAllChannel"] = strata.ratio_interval(
            row["passiveFlags"], row["passiveIntervals"],
            row["payloadFlags"], row["payloadIntervals"],
        )
        row["postHocBinTost"] = strata.tost_ratio(
            row["passiveInclinationOnly"], row["passiveIntervals"],
            row["payloadInclinationOnly"], row["payloadIntervals"],
        )
        rows.append(row)
    return rows


def _zoom_rows(zoom, policy: str) -> list[dict]:
    slot = POLICY_SLOT[policy]
    rows = []
    keys = sorted({int(k) for k in zoom["passive"]} | {int(k) for k in zoom["payload"]})
    for index in keys:
        passive = zoom["passive"].get(str(index), [0] * 7)
        payload = zoom["payload"].get(str(index), [0] * 7)
        row = {
            "bin": index,
            "low": index * strata.ZOOM_BIN_DEG,
            "high": (index + 1) * strata.ZOOM_BIN_DEG,
            "passiveIntervals": passive[0], "passiveInclinationOnly": passive[slot + 2],
            "passiveFlags": passive[slot],
            "payloadIntervals": payload[0], "payloadInclinationOnly": payload[slot + 2],
            "payloadFlags": payload[slot],
        }
        row["passiveInclinationOnlyPer1000"] = strata.rate_per_1000(
            row["passiveInclinationOnly"], row["passiveIntervals"])
        row["payloadInclinationOnlyPer1000"] = strata.rate_per_1000(
            row["payloadInclinationOnly"], row["payloadIntervals"])
        row["passiveJeffreys95Per1000"] = [
            1000.0 * b for b in strata.jeffreys(row["passiveInclinationOnly"], row["passiveIntervals"])]
        row["payloadJeffreys95Per1000"] = [
            1000.0 * b for b in strata.jeffreys(row["payloadInclinationOnly"], row["payloadIntervals"])]
        row["ratioInclinationOnly"] = strata.ratio_interval(
            row["passiveInclinationOnly"], row["passiveIntervals"],
            row["payloadInclinationOnly"], row["payloadIntervals"])
        rows.append(row)
    return rows


def _pool(rows, predicate, field="InclinationOnly"):
    kp = sum(r[f"passive{field}"] for r in rows if predicate(r))
    ep = sum(r["passiveIntervals"] for r in rows if predicate(r))
    kl = sum(r[f"payload{field}"] for r in rows if predicate(r))
    el = sum(r["payloadIntervals"] for r in rows if predicate(r))
    return kp, ep, kl, el


def analysis_two(curve, zoom, policy: str) -> dict:
    rows = _curve_rows(curve, policy)
    zoom_rows = _zoom_rows(zoom, policy)
    high = strata.HIGH_INCLINATION_MIN_DEG

    def region(name, predicate):
        kp, ep, kl, el = _pool(rows, predicate)
        test = strata.tost_ratio(kp, ep, kl, el)
        test["region"] = name
        test["passiveJeffreys95Per1000"] = [1000.0 * b for b in strata.jeffreys(kp, ep)]
        test["payloadJeffreys95Per1000"] = [1000.0 * b for b in strata.jeffreys(kl, el)]
        return test

    sso = (strata.SSO_MIN_DEG, strata.SSO_MAX_DEG)
    regions = [
        region(f">={high:g} deg (registered primary)", lambda r: r["low"] >= high),
        region("30-60 deg", lambda r: 30.0 <= r["low"] < 60.0),
        region("60-90 deg excluding SSO", lambda r: 60.0 <= r["low"] < 90.0),
        region("SSO 96-100 deg", lambda r: sso[0] <= r["low"] < sso[1]),
        region("90-120 deg excluding SSO",
               lambda r: 90.0 <= r["low"] < 120.0 and not (sso[0] <= r["low"] < sso[1])),
        region("120-180 deg", lambda r: r["low"] >= 120.0),
        region(f">={high:g} deg excluding SSO",
               lambda r: r["low"] >= high and not (sso[0] <= r["low"] < sso[1])),
        region(f"<{high:g} deg (below the shipped boundary)", lambda r: r["low"] < high),
    ]
    scan = strata.boundary_scan(rows)

    passive_high = sum(r["passiveIntervals"] for r in rows if r["low"] >= high)
    payload_high = sum(r["payloadIntervals"] for r in rows if r["low"] >= high)
    passive_sso = sum(r["passiveIntervals"] for r in rows if sso[0] <= r["low"] < sso[1])
    payload_sso = sum(r["payloadIntervals"] for r in rows if sso[0] <= r["low"] < sso[1])

    primary = regions[0]
    inside = next(r for r in regions if r["region"] == "SSO 96-100 deg")
    outside = next(r for r in regions if r["region"].endswith("excluding SSO") and r["region"].startswith(">="))
    if inside["equivalent"] and outside["equivalent"]:
        composition = "not a composition artefact: equivalence holds inside and outside the SSO band"
    elif primary["equivalent"] and not outside["equivalent"]:
        composition = "COMPOSITION ARTEFACT: equivalence at >=30 deg holds only with SSO included"
    elif outside["equivalent"] and not inside["equivalent"]:
        composition = "SSO is a separate regime: equivalence holds outside it but not inside it"
    else:
        composition = "inconclusive: neither split establishes equivalence at the registered margin"

    return {
        "policy": policy,
        "curve": rows,
        "zoom": zoom_rows,
        "regions": regions,
        "boundaryScan": scan,
        "shippedBoundaryDeg": high,
        "boundaryAgreesWithShipped": scan["boundaryDeg"] == high,
        "ssoComposition": {
            "verdict": composition,
            "passiveSsoExposureShareOfHigh": passive_sso / passive_high if passive_high else 0.0,
            "payloadSsoExposureShareOfHigh": payload_sso / payload_high if payload_high else 0.0,
            "passiveHighIntervals": passive_high,
            "payloadHighIntervals": payload_high,
        },
        "postHocBinwiseNote": (
            "postHocBinTost on each curve row is NOT pre-registered and carries no "
            "decision weight; it exists so a diluted boundary can be recognised as dilution"
        ),
    }


def _markdown(one_on, one_off, two, counts, summaries) -> str:
    out: list[str] = []
    w = out.append

    def per1000(value):
        return "not estimable" if value is None else f"{value:.6f}"

    def times(value):
        return "not estimable" if value is None else f"{value:.4f}x"

    w("### Sample and exposure\n")
    w("| Measure | Passive | Payload |")
    w("|---|---:|---:|")
    w(f"| Objects with tallies | {counts['passiveObjects']:,} | {counts['payloadObjects']:,} |")
    w(f"| Element rows read | {counts['passiveRows']:,} | {counts['payloadRows']:,} |")
    w(f"| Usable intervals (exposure) | {counts['passiveIntervals']:,} | {counts['payloadIntervals']:,} |")
    totals = defaultdict(int)
    for summary in summaries:
        for key, value in summary["totals"].items():
            totals[key] += value
    w(f"| Admission exclusions (<9 intervals) | {totals['passiveTooShortObjects']:,} "
      f"| {totals['payloadTooShortObjects']:,} |")
    w(f"| Propulsive flags, corroboration ON | {totals['passiveFlagsOn']:,} | {totals['payloadFlagsOn']:,} |")
    w(f"| Propulsive flags, corroboration OFF | {totals['passiveFlagsOff']:,} | {totals['payloadFlagsOff']:,} |")
    w(f"| Inclination-channel catches, ON | {totals['passiveInclinationOn']:,} | {totals['payloadInclinationOn']:,} |")
    w(f"| Inclination-channel catches, OFF | {totals['passiveInclinationOff']:,} | {totals['payloadInclinationOff']:,} |")
    w(f"| Inclination-ONLY catches, ON | {totals['passiveInclinationOnlyOn']:,} | {totals['payloadInclinationOnlyOn']:,} |")
    w(f"| Inclination-ONLY catches, OFF | {totals['passiveInclinationOnlyOff']:,} | {totals['payloadInclinationOnlyOff']:,} |")
    w("")

    for label, result in (("corroboration ACTIVE (shipping detector)", one_on),
                          ("corroboration OFF (context only)", one_off)):
        p = result["primary"]
        b = result["bootstrapPrimaryInterval"]
        q = result["posteriorSecondaryInterval"]
        a = result["worstCaseFillSensitivityA"]
        w(f"### Analysis 1: reweighted passive floor, {label}\n")
        w("| Quantity | Per 1,000 usable intervals |")
        w("|---|---:|")
        w(f"| Raw passive floor | {per1000(p['rawFloorPer1000'])} |")
        w(f"| Raw Jeffreys 95% | [{per1000(p['rawJeffreys95Per1000'][0])}, "
          f"{per1000(p['rawJeffreys95Per1000'][1])}] |")
        w(f"| **Reweighted to the payload covariate mix** | **{per1000(p['reweightedFloorPer1000'])}** |")
        w(f"| Primary 95% (clustered object bootstrap) | [{per1000(b['low95Per1000'])}, "
          f"{per1000(b['high95Per1000'])}] |")
        w(f"| Secondary 95% (Jeffreys posteriors, conservative) | [{per1000(q['low95Per1000'])}, "
          f"{per1000(q['high95Per1000'])}] |")
        w(f"| Reweighted / raw | {times(p['ratioToRaw'])} |")
        w(f"| Target | {1000 * strata.TARGET_RATE_PER_INTERVAL:.3f} |")
        w(f"| Sensitivity A, gaps filled at the pooled upper bound | "
          f"{per1000(a['reweightedFloorPer1000'])} ({times(a['ratioToRaw'])} raw) |")
        w(f"| Sensitivity B, perigee x inclination only (48 cells) | "
          f"{per1000(result['coarseSensitivityB']['reweightedFloorPer1000'])} "
          f"({times(result['coarseSensitivityB']['ratioToRaw'])} raw) |")
        w("")
        sb = result["strictSupportBootstrap"]
        sq = result["strictSupportPosterior"]
        w("Registered secondary support tier (>=1,000 passive intervals per stratum), "
          "reported alongside and with no bearing on the verdict above:\n")
        w("| Quantity | Per 1,000 usable intervals |")
        w("|---|---:|")
        strict_row = result["strictSupport1000"]
        w(f"| Reweighted floor, >=1,000-interval strata only | "
          f"{per1000(strict_row['reweightedFloorPer1000'])} "
          f"({times(strict_row['ratioToRaw'])} raw) |")
        w(f"| Primary 95% (clustered object bootstrap) | [{per1000(sb['low95Per1000'])}, "
          f"{per1000(sb['high95Per1000'])}] |")
        w(f"| Secondary 95% (Jeffreys posteriors, conservative) | [{per1000(sq['low95Per1000'])}, "
          f"{per1000(sq['high95Per1000'])}] |")
        w("")
        thin = result["thinSupportDiagnostic"]
        w(f"Thin support: **{thin['count']}** supported strata hold fewer than 2,000 passive "
          f"intervals each yet carry **{thin['payloadWeightShare'] * 100:.2f}%** of the payload "
          f"weight between them. Heaviest:\n")
        w("| Stratum | Payload weight | Passive intervals | Passive flags | Passive rate /1,000 |")
        w("|---|---:|---:|---:|---:|")
        for row in thin["heaviest"]:
            w(f"| `{row['stratum']}` | {row['weight'] * 100:.3f}% | {row['passiveIntervals']:,} | "
              f"{row['passiveFlags']:,} | {row['passiveRatePer1000']:.6f} |")
        w("")
        w("| Support | Strata | Payload exposure in labelled gaps |")
        w("|---|---:|---:|")
        w(f"| Supported (>=1 passive interval) | {p['supportedStrata']} | "
          f"{p['unsupportedPayloadExposureShare'] * 100:.3f}% in {p['gapStrata']} gap strata |")
        s = result["strictSupport1000"]
        w(f"| Supported (>=1,000 passive intervals) | {s['supportedStrata']} | "
          f"{s['unsupportedPayloadExposureShare'] * 100:.3f}% in {s['gapStrata']} gap strata |")
        w("")
        w(f"**Registered verdict: {result['decision']['verdict']}**\n")
        if p["gaps"]:
            w("Largest labelled gaps (payload exposure with no passive support):\n")
            w("| Stratum | Payload intervals | Share of payload exposure |")
            w("|---|---:|---:|")
            for gap in p["gaps"][:12]:
                w(f"| `{gap['stratum']}` | {gap['payloadIntervals']:,} | "
                  f"{100.0 * gap['payloadIntervals'] / p['payloadIntervals']:.4f}% |")
            w("")

    w("### Analysis 1: the twenty heaviest payload strata\n")
    w("| Stratum | Payload weight | Passive intervals | Passive flags | "
      "Passive rate /1,000 | Passive Jeffreys 95% | Payload rate /1,000 |")
    w("|---|---:|---:|---:|---:|---|---:|")
    for row in one_on["primary"]["rows"][:20]:
        w(f"| `{row['stratum']}` | {row['weight'] * 100:.3f}% | {row['passiveIntervals']:,} | "
          f"{row['passiveFlags']:,} | {row['passiveRatePer1000']:.6f} | "
          f"[{row['passiveJeffreys95Per1000'][0]:.6f}, {row['passiveJeffreys95Per1000'][1]:.6f}] | "
          f"{row['payloadRatePer1000']:.6f} |")
    w("")

    w("### Analysis 2a: rate against inclination, 2-degree bins, pre-corroboration detector\n")
    w("Inclination-ONLY catches per 1,000 usable intervals, both populations, with "
      "Jeffreys 95% bounds and the exact conditional payload/passive ratio. Bins with "
      "no exposure are omitted; bins with no flags anywhere carry no ratio.\n")
    w("| Inclination | Passive intervals | Passive i-only | Rate /1,000 | Jeffreys 95% | "
      "Payload intervals | Payload i-only | Rate /1,000 | Jeffreys 95% | Ratio (exact 95%) |")
    w("|---|---:|---:|---:|---|---:|---:|---:|---|---|")
    for row in two["curve"]:
        if row["passiveIntervals"] == 0 and row["payloadIntervals"] == 0:
            continue
        ratio = row["ratioInclinationOnly"]
        if ratio["point"] is None and ratio["low"] is None:
            ratio_text = f"not a ratio ({ratio['note']})"
        elif ratio["point"] is None:
            ratio_text = f"one-sided [{ratio['low']:.3f}, {ratio['high']:.3f}]"
        else:
            ratio_text = f"{ratio['point']:.3f} [{ratio['low']:.3f}, {ratio['high']:.3f}]"
        w(f"| {row['low']:.0f}-{row['high']:.0f} | {row['passiveIntervals']:,} | "
          f"{row['passiveInclinationOnly']:,} | {row['passiveInclinationOnlyPer1000']:.6f} | "
          f"[{row['passiveInclinationOnlyJeffreys95Per1000'][0]:.6f}, "
          f"{row['passiveInclinationOnlyJeffreys95Per1000'][1]:.6f}] | "
          f"{row['payloadIntervals']:,} | {row['payloadInclinationOnly']:,} | "
          f"{row['payloadInclinationOnlyPer1000']:.6f} | "
          f"[{row['payloadInclinationOnlyJeffreys95Per1000'][0]:.6f}, "
          f"{row['payloadInclinationOnlyJeffreys95Per1000'][1]:.6f}] | {ratio_text} |")
    w("")

    w("### Analysis 2a zoom: 0.2-degree bins below 2 degrees (the GEO population)\n")
    w("| Inclination | Passive intervals | Passive i-only /1,000 | Payload intervals | "
      "Payload i-only /1,000 | Ratio (exact 95%) |")
    w("|---|---:|---:|---:|---:|---|")
    for row in two["zoom"]:
        ratio = row["ratioInclinationOnly"]
        if ratio["point"] is None and ratio["low"] is None:
            ratio_text = f"not a ratio ({ratio['note']})"
        elif ratio["point"] is None:
            ratio_text = f"one-sided [{ratio['low']:.3f}, {ratio['high']:.3f}]"
        else:
            ratio_text = f"{ratio['point']:.3f} [{ratio['low']:.3f}, {ratio['high']:.3f}]"
        w(f"| {row['low']:.1f}-{row['high']:.1f} | {row['passiveIntervals']:,} | "
          f"{row['passiveInclinationOnlyPer1000']:.6f} | {row['payloadIntervals']:,} | "
          f"{row['payloadInclinationOnlyPer1000']:.6f} | {ratio_text} |")
    w("")

    w("### Analysis 2b and 2c: exact conditional TOST by region\n")
    w(f"Registered margin: rate ratio inside [1/{strata.EQUIVALENCE_MARGIN:g}, "
      f"{strata.EQUIVALENCE_MARGIN:g}], alpha 0.05, two one-sided exact tests.\n")
    w("| Region | Passive i-only / exposure | Payload i-only / exposure | Ratio | "
      "Exact 90% ratio interval | TOST p | Superiority p (no decision weight) | Equivalent? |")
    w("|---|---:|---:|---:|---|---:|---:|---|")
    for test in two["regions"]:
        if not test.get("conclusive"):
            w(f"| {test['region']} | {test['flagsPassive']} | {test['flagsPayload']} | - | - | - | - | "
              f"no: {test['reason']} |")
            continue
        r90 = test["ratio90"]
        interval = ("not estimable" if r90["low"] is None
                    else f"[{r90['low']:.4f}, {r90['high']:.4f}]")
        point = "-" if r90["point"] is None else f"{r90['point']:.4f}"
        w(f"| {test['region']} | {test['flagsPassive']:,} / {int(test['exposurePassive']):,} | "
          f"{test['flagsPayload']:,} / {int(test['exposurePayload']):,} | {point} | {interval} | "
          f"{test['pValueTost']:.3g} | {test['superiorityPValueNoDecisionWeight']:.3g} | "
          f"{'YES' if test['equivalent'] else 'NO'} |")
    w("")
    w(f"**SSO composition verdict: {two['ssoComposition']['verdict']}**\n")
    w(f"SSO (96-100 deg) is {two['ssoComposition']['passiveSsoExposureShareOfHigh'] * 100:.2f}% of "
      f"passive exposure at >=30 deg and "
      f"{two['ssoComposition']['payloadSsoExposureShareOfHigh'] * 100:.2f}% of payload exposure there.\n")

    w("### Analysis 2a: the registered boundary scan\n")
    scan = two["boundaryScan"]
    found = "none" if scan["boundaryDeg"] is None else f"{scan['boundaryDeg']:.0f} deg"
    w(f"Rule: {scan['rule']}. **Data-driven boundary: {found}.** "
      f"Shipped boundary: {two['shippedBoundaryDeg']:.0f} deg.\n")
    w("| Candidate | Passive i-only / exposure | Payload i-only / exposure | "
      "Exact 90% ratio interval | Equivalent? |")
    w("|---|---:|---:|---|---|")
    for entry in scan["scan"]:
        test = entry["test"]
        if not test.get("conclusive"):
            w(f"| {entry['boundaryDeg']:.0f} | {test['flagsPassive']} | {test['flagsPayload']} | - | "
              f"no: {test['reason']} |")
            continue
        r90 = test["ratio90"]
        interval = ("not estimable" if r90["low"] is None
                    else f"[{r90['low']:.4f}, {r90['high']:.4f}]")
        w(f"| {entry['boundaryDeg']:.0f} | {test['flagsPassive']:,} / {int(test['exposurePassive']):,} | "
          f"{test['flagsPayload']:,} / {int(test['exposurePayload']):,} | {interval} | "
          f"{'YES' if test['equivalent'] else 'NO'} |")
    w("")

    w("### Post-hoc, NOT pre-registered: bin-wise equivalence\n")
    w("No decision weight. Present only so a diluted pooled boundary can be recognised "
      "as dilution rather than read as a physical edge.\n")
    w("| Inclination | Passive i-only | Payload i-only | Equivalent at the registered margin? |")
    w("|---|---:|---:|---|")
    for row in two["curve"]:
        if row["passiveIntervals"] == 0 and row["payloadIntervals"] == 0:
            continue
        test = row["postHocBinTost"]
        verdict = "YES" if test.get("equivalent") else (
            "inconclusive" if test.get("conclusive") else "no flags")
        w(f"| {row['low']:.0f}-{row['high']:.0f} | {row['passiveInclinationOnly']:,} | "
          f"{row['payloadInclinationOnly']:,} | {verdict} |")
    w("")
    return "\n".join(out)


def _source_hashes() -> dict:
    out = {}
    for name in ("pipeline/orbit_campaigns.py", "pipeline/orbit_events.py",
                 "tools/paperb_strata.py", "tools/paperb_measure.py", "tools/paperb_analyze.py",
                 "tools/paperb_selftest.py", "docs/paperb-preregistration-20260920.md"):
        path = _REPO / name
        if path.is_file():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--summaries", nargs="*", default=[])
    parser.add_argument("--jsonl", default=str(_REPO / "docs" / "paperb-strata-20260920.jsonl"))
    parser.add_argument("--json", default=str(_REPO / "docs" / "paperb-results-20260920.json"))
    parser.add_argument("--markdown", default=str(_REPO / "docs" / "paperb-tables-20260920.md"))
    args = parser.parse_args(argv)

    paths = sorted({p for pattern in args.inputs for p in glob.glob(pattern)})
    summary_paths = sorted({p for pattern in args.summaries for p in glob.glob(pattern)})
    summaries = [json.loads(Path(p).read_text()) for p in summary_paths]
    cells, curve, zoom, passive_objects, counts = _load(paths)

    one_on = analysis_one(cells, passive_objects, "on")
    one_off = analysis_one(cells, passive_objects, "off")
    two = analysis_two(curve, zoom, "off")
    two_on = analysis_two(curve, zoom, "on")

    with open(args.jsonl, "w") as handle:
        for policy, store in (("on", "on"), ("off", "off")):
            passive = _split(cells["passive"], policy)
            payload = _split(cells["payload"], policy)
            passive_only = _split_only(cells["passive"], policy)
            payload_only = _split_only(cells["payload"], policy)
            for key in sorted(set(passive) | set(payload)):
                p_flags, p_n = passive.get(key, (0, 0))
                l_flags, l_n = payload.get(key, (0, 0))
                perigee, inclination, eccentricity, cadence = key.split("|")
                handle.write(json.dumps({
                    "kind": "stratum",
                    "policy": policy,
                    "stratum": key,
                    "perigeeBand": perigee, "inclinationBand": inclination,
                    "eccentricityClass": eccentricity, "cadenceClass": cadence,
                    "passiveIntervals": p_n, "passiveFlags": p_flags,
                    "passiveInclinationOnly": passive_only.get(key, (0, 0))[0],
                    "passiveRatePer1000": strata.rate_per_1000(p_flags, p_n),
                    "passiveJeffreys95Per1000": [1000.0 * b for b in strata.jeffreys(p_flags, p_n)],
                    "payloadIntervals": l_n, "payloadFlags": l_flags,
                    "payloadInclinationOnly": payload_only.get(key, (0, 0))[0],
                    "payloadRatePer1000": strata.rate_per_1000(l_flags, l_n),
                    "payloadJeffreys95Per1000": [1000.0 * b for b in strata.jeffreys(l_flags, l_n)],
                    "passiveSupported": p_n >= 1,
                    "passiveSupported1000": p_n >= 1000,
                }, separators=(",", ":")) + "\n")
        for row in two["curve"]:
            handle.write(json.dumps({"kind": "curveBin", "policy": "off", **row},
                                    separators=(",", ":")) + "\n")
        for row in two["zoom"]:
            handle.write(json.dumps({"kind": "zoomBin", "policy": "off", **row},
                                    separators=(",", ":")) + "\n")
        for test in two["regions"]:
            handle.write(json.dumps({"kind": "regionTost", "policy": "off", **test},
                                    separators=(",", ":")) + "\n")
        for entry in two["boundaryScan"]["scan"]:
            handle.write(json.dumps({"kind": "boundaryCandidate", "policy": "off", **entry},
                                    separators=(",", ":")) + "\n")

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = None

    receipt = {
        "preregistration": "docs/paperb-preregistration-20260920.md",
        "commit": commit,
        "inputs": paths,
        "summaries": summaries,
        "sampleCounts": dict(counts),
        "analysis1CorroborationOn": one_on,
        "analysis1CorroborationOff": one_off,
        "analysis2PreCorroboration": two,
        "analysis2ShippingDetectorStructuralCheck": {
            "note": "shown only so the amendment's structural-zero claim is verifiable",
            "regions": two_on["regions"],
        },
        "sourceSha256": _source_hashes(),
        "registeredConstants": {
            "equivalenceMargin": strata.EQUIVALENCE_MARGIN,
            "seed": strata.SEED,
            "bootstrapDraws": strata.BOOTSTRAP_DRAWS,
            "posteriorDraws": strata.POSTERIOR_DRAWS,
            "targetRatePerInterval": strata.TARGET_RATE_PER_INTERVAL,
            "highInclinationMinDeg": strata.HIGH_INCLINATION_MIN_DEG,
            "ssoBandDeg": [strata.SSO_MIN_DEG, strata.SSO_MAX_DEG],
        },
    }
    Path(args.json).write_text(json.dumps(receipt, indent=2, default=str))
    tables = _markdown(one_on, one_off, two, counts, summaries)
    Path(args.markdown).write_text(tables)
    print(tables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
