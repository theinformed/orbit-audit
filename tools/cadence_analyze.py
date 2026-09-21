#!/usr/bin/env python3
"""T3 step 3: thresholds, multiple testing, change-points and the three gates.

Consumes only the per-window tables `tools/cadence_measure.py` wrote and the
extraction index. Every rule applied here is the one registered in
`docs/cadence-preregistration-20260921.md`; the section number is cited at each
one. Nothing in this program chooses a threshold, a percentile or a cut point
that the registration did not already fix.

Writes `docs/cadence-results-<date>.jsonl` (one row per object) and a
`*-receipt.json` of the population-level numbers the results report quotes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import cadence_core as core  # noqa: E402
from tools.cadence_measure import CHANNELS  # noqa: E402

# Presentational regime grouping for the E4 table only (prereg 2, E4). It is
# built from the registered banding quantities and decides nothing: no
# threshold, no p-value and no gate reads it.
def regime(perigee_km: float, ecc: float, incl: float) -> str:
    if perigee_km < 2000.0:
        return "LEO"
    if ecc >= 0.1:
        return "GTO/HEO"
    if perigee_km >= 30000.0 and incl < 25.0:
        return "GEO"
    if perigee_km >= 30000.0:
        return "GEO-inclined"
    return "MEO"


# Operator families, matched on the catalogue's own object name. Only families
# whose naming is unambiguous are listed; everything else is "unclassified",
# which is reported rather than guessed at.
OPERATOR_PREFIXES = (
    ("STARLINK", "Starlink (SpaceX)"),
    ("ONEWEB", "OneWeb"),
    ("IRIDIUM", "Iridium"),
    ("GLOBALSTAR", "Globalstar"),
    ("ORBCOMM", "Orbcomm"),
    ("NAVSTAR", "GPS (NAVSTAR)"),
    ("GALILEO", "Galileo"),
    ("BEIDOU", "BeiDou"),
    ("GLONASS", "GLONASS"),
    ("COSMOS", "Cosmos (Russian)"),
    ("YAOGAN", "Yaogan (Chinese)"),
    ("FLOCK", "Flock (Planet)"),
    ("SKYSAT", "SkySat (Planet)"),
    ("LEMUR", "Lemur (Spire)"),
    ("ICEYE", "ICEYE"),
    ("INTELSAT", "Intelsat"),
    ("EUTELSAT", "Eutelsat"),
    ("INMARSAT", "Inmarsat"),
    ("O3B", "O3b"),
    ("ASTRA", "Astra (SES)"),
    ("GONETS", "Gonets"),
    ("TIANHUI", "Tianhui (Chinese)"),
    ("GAOFEN", "Gaofen (Chinese)"),
)


def operator_family(name: str) -> str:
    upper = (name or "").upper()
    for prefix, label in OPERATOR_PREFIXES:
        if upper.startswith(prefix):
            return label
    return "unclassified"


def load_windows(paths, index):
    tables = [np.load(p) for p in paths]
    keys = tables[0].files
    data = {k: np.concatenate([t[k] for t in tables]) for k in keys}
    meta = {int(o["norad"]): o for o in index["objects"]}
    data["klass"] = np.array([meta[int(n)]["class"] for n in data["norad"]])
    data["half"] = np.array([meta[int(n)]["half"] or "" for n in data["norad"]])
    return data, meta


def cell_keys(data):
    """The registered 5-factor matching cell, plus its four fallback rungs (prereg 6.4)."""
    full, drop_e, drop_i, drop_p = [], [], [], []
    for perigee, incl, ecc, spacing, n in zip(
            data["perigeeKm"], data["inclinationDeg"], data["eccentricity"],
            data["medianSpacingDays"], data["n"]):
        stratum = core.stratum_key(float(perigee), float(incl), float(ecc), float(spacing))
        parts = stratum.split("|")           # perigee | inclination | ecc | cadence
        nb = core.n_band(int(n))
        full.append("|".join(parts + [nb]))
        drop_e.append("|".join([parts[0], parts[1], parts[3], nb]))
        drop_i.append("|".join([parts[0], parts[3], nb]))
        drop_p.append("|".join([parts[3], nb]))
    return [np.array(full), np.array(drop_e), np.array(drop_i), np.array(drop_p)]


def percentile_table(keys, values, minimum, percentile):
    buckets = defaultdict(list)
    for key, value in zip(keys, values):
        buckets[key].append(value)
    return {k: float(np.percentile(v, percentile)) for k, v in buckets.items()
            if len(v) >= minimum}, {k: len(v) for k, v in buckets.items()}


def analyse(art: Path, shards, out_stem: Path, channel: str) -> dict:
    index = json.loads((art / "index.json").read_text())
    data, meta = load_windows(shards, index)
    keep = data["channel"] == CHANNELS.index(channel)
    data = {k: v[keep] for k, v in data.items()}

    ladder = cell_keys(data)
    calib = (data["klass"] == "passive") & (data["half"] == "calibration")
    audit = (data["klass"] == "passive") & (data["half"] == "audit")
    payload = data["klass"] == "payload"

    # ---- prereg 6.3: window thresholds from the CALIBRATION half only -------
    thresholds = []
    cell_sizes = []
    for rung in ladder:
        table, sizes = percentile_table(rung[calib], data["pmax"][calib],
                                        core.MIN_CELL_WINDOWS, core.PRIMARY_PERCENTILE)
        thresholds.append(table)
        cell_sizes.append(sizes)
    pooled = float(np.percentile(data["pmax"][calib], core.PRIMARY_PERCENTILE))
    sensitivity = {str(p): float(np.percentile(data["pmax"][calib], p))
                   for p in core.SENSITIVITY_PERCENTILES}

    window_threshold = np.empty(data["pmax"].size, dtype=np.float64)
    window_rung = np.empty(data["pmax"].size, dtype=np.int8)
    for i in range(data["pmax"].size):
        for rung_index in range(4):
            value = thresholds[rung_index].get(ladder[rung_index][i])
            if value is not None:
                window_threshold[i] = value
                window_rung[i] = rung_index + 1
                break
        else:
            window_threshold[i] = pooled
            window_rung[i] = 5
    significant_window = data["pmax"] > window_threshold

    # ---- per-object aggregation --------------------------------------------
    objects = defaultdict(lambda: {"pmax": [], "freq": [], "sig": [], "window": [],
                                   "rung": [], "n": [], "perigee": [], "incl": [],
                                   "ecc": [], "spacing": [], "second": [],
                                   "secondFreq": [], "tStart": []})
    for i in range(data["pmax"].size):
        rec = objects[int(data["norad"][i])]
        rec["pmax"].append(float(data["pmax"][i]))
        rec["freq"].append(float(data["freqCyclesPerDay"][i]))
        rec["sig"].append(bool(significant_window[i]))
        rec["window"].append(int(data["window"][i]))
        rec["rung"].append(int(window_rung[i]))
        rec["n"].append(int(data["n"][i]))
        rec["perigee"].append(float(data["perigeeKm"][i]))
        rec["incl"].append(float(data["inclinationDeg"][i]))
        rec["ecc"].append(float(data["eccentricity"][i]))
        rec["spacing"].append(float(data["medianSpacingDays"][i]))
        rec["second"].append(float(data["secondPeakRatio"][i]))
        rec["secondFreq"].append(float(data["secondPeakFreq"][i]))
        rec["tStart"].append(int(data["tStartMs"][i]))

    rows = []
    for norad, rec in objects.items():
        order = np.argsort(rec["window"])
        for key in rec:
            rec[key] = [rec[key][i] for i in order]
        best = int(np.argmax(rec["pmax"]))
        info = meta[norad]
        rows.append({
            "norad": norad, "name": info["name"], "objectType": info["objectType"],
            "class": info["class"], "half": info["half"], "channel": channel,
            "windows": len(rec["pmax"]),
            "windowCountBand": core.window_count_band(len(rec["pmax"])),
            "statistic": float(rec["pmax"][best]),
            "dominantPeriodDays": 1.0 / rec["freq"][best],
            "bestWindow": rec["window"][best],
            "bestWindowStartMs": rec["tStart"][best],
            "matchRung": rec["rung"][best],
            "significantWindows": int(sum(rec["sig"])),
            "anyWindowOverThreshold": bool(any(rec["sig"])),
            "harmonicAmbiguous": _harmonic_flag(rec["freq"][best], rec["secondFreq"][best],
                                                rec["second"][best]),
            "regime": regime(float(np.median(rec["perigee"])), float(np.median(rec["ecc"])),
                             float(np.median(rec["incl"]))),
            "operator": operator_family(info["name"]),
            "medianPerigeeKm": float(np.median(rec["perigee"])),
            "medianInclinationDeg": float(np.median(rec["incl"])),
            "medianEccentricity": float(np.median(rec["ecc"])),
            "medianSpacingDays": float(np.median(rec["spacing"])),
            # The per-window arrays run to 60 entries on the longest-lived
            # objects and dominate the artifact's size. They are rounded to
            # more precision than any consumer uses -- 1e-3 d on a period whose
            # grid resolution is 6 d at the band top, and 1e-5 on a power whose
            # thresholds sit at 1e-2 -- so the file stays readable without any
            # decision depending on a digit that was dropped. Every scalar the
            # report quotes is stored at full precision above.
            "windowPeriodsDays": [round(1.0 / f, 3) for f in rec["freq"]],
            "windowPmax": [round(v, 5) for v in rec["pmax"]],
            "windowSignificant": rec["sig"],
            "windowIndices": rec["window"],
            "windowStartMs": rec["tStart"],
            "matchRungs": rec["rung"],
        })

    # ---- prereg 8.2/8.3: object-level null, window-count matched ------------
    calib_objects = [r for r in rows if r["class"] == "passive" and r["half"] == "calibration"]
    by_band = defaultdict(list)
    for r in calib_objects:
        by_band[r["windowCountBand"]].append(r["statistic"])
    pooled_reference = np.array([r["statistic"] for r in calib_objects])
    band_reference = {b: np.array(v) for b, v in by_band.items()
                      if len(v) >= core.MIN_CELL_WINDOWS}

    for r in rows:
        reference = band_reference.get(r["windowCountBand"])
        r["objectNullRung"] = 1 if reference is not None else 5
        if reference is None:
            reference = pooled_reference
        r["objectNullSize"] = int(reference.size)
        r["pValue"] = core.empirical_pvalue(r["statistic"], reference)
        r["pValueAtFloor"] = bool(abs(r["pValue"] - 1.0 / (1 + reference.size)) < 1e-12)

    verdicts = {}
    for group, selector in (("payload", lambda r: r["class"] == "payload"),
                            ("passive_audit", lambda r: r["class"] == "passive"
                                                        and r["half"] == "audit")):
        members = [r for r in rows if selector(r)]
        reject = core.benjamini_hochberg([r["pValue"] for r in members], core.FDR_Q)
        for r, flag in zip(members, reject):
            r["significantBH"] = bool(flag)
        verdicts[group] = members

    for r in rows:
        r.setdefault("significantBH", None)      # calibration half: not tested

    # ---- prereg 7: change-points -------------------------------------------
    for r in rows:
        r["shifts"], r["stops"] = _changepoints(r)

    # ---- prereg 10: the three gates ----------------------------------------
    receipt = _receipt(rows, verdicts, thresholds, cell_sizes, pooled, sensitivity,
                       band_reference, channel)

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    with open(f"{out_stem}.jsonl", "w") as handle:
        for r in sorted(rows, key=lambda r: r["norad"]):
            handle.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    Path(f"{out_stem}-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def _harmonic_flag(f_star, f_second, ratio) -> bool:
    """prereg 2.1: is the reported peak plausibly a harmonic of another strong peak?"""
    if ratio < 0.5 or f_second <= 0:
        return False
    for k in (2.0, 3.0):
        if abs(f_star - k * f_second) / f_star < 0.05 or abs(f_second - k * f_star) / f_second < 0.05:
            return True
    return False


def _changepoints(row):
    """prereg 7.1 (shift) and 7.2 (stop), on the object's ordered windows."""
    sig = row["windowSignificant"]
    periods = row["windowPeriodsDays"]
    indices = row["windowIndices"]
    shifts, stops = [], []
    if len(sig) < core.CHANGEPOINT_MIN_WINDOWS:
        return shifts, stops
    for k in range(1, len(sig) - 2):
        # A missing window index means an INADMISSIBLE window, and prereg 7.2
        # requires the "after" side to be usable -- otherwise "stopped keeping
        # station" and "left the archive" would be the same event. So only
        # boundaries whose four surrounding windows are consecutive count.
        if indices[k + 2] - indices[k - 1] != 3:
            continue
        before = sig[k - 1] and sig[k]
        after = sig[k + 1] and sig[k + 2]
        if before and after:
            p_before = float(np.median([periods[k - 1], periods[k]]))
            p_after = float(np.median([periods[k + 1], periods[k + 2]]))
            if abs(p_before - p_after) / min(p_before, p_after) > core.SHIFT_TOLERANCE:
                shifts.append({"afterWindow": indices[k], "periodBeforeDays": p_before,
                               "periodAfterDays": p_after})
        if before and not sig[k + 1] and not sig[k + 2]:
            stops.append({"afterWindow": indices[k],
                          "periodBeforeDays": float(np.median([periods[k - 1], periods[k]]))})
    return shifts, stops


def episodes(points):
    """Maximal runs of consecutive flagged boundaries, as one episode each.

    The registered rule (prereg 7.1) declares a shift at EVERY boundary whose
    two-window medians straddle the change, so one physical transition in a
    six-window object is declared three times. The registration is binding and
    the boundary count is reported as registered -- but it is not the number a
    reader wants, so the merged episode count is reported beside it, for the
    payload class and for the passive audit control alike. Merging is
    presentation: it changes no threshold and no verdict.
    """
    boundaries = sorted({p["afterWindow"] for p in points})
    merged = 0
    previous = None
    for b in boundaries:
        if previous is None or b != previous + 1:
            merged += 1
        previous = b
    return merged


def _fraction(members, key):
    hits = sum(1 for r in members if r[key])
    total = len(members)
    low, high = core._jeffreys_interval(hits, total) if total else (None, None)
    return {"hits": hits, "total": total,
            "fraction": (hits / total) if total else None,
            "jeffreys95": [low, high]}


def _receipt(rows, verdicts, thresholds, cell_sizes, pooled, sensitivity,
             band_reference, channel):
    payload = verdicts["payload"]
    audit = verdicts["passive_audit"]
    calibration = [r for r in rows if r["class"] == "passive" and r["half"] == "calibration"]

    bh_payload = _fraction(payload, "significantBH")
    bh_audit = _fraction(audit, "significantBH")
    raw_payload = _fraction(payload, "anyWindowOverThreshold")
    raw_audit = _fraction(audit, "anyWindowOverThreshold")

    gate_a = {"passiveAuditFractionBH": bh_audit["fraction"],
              "limit": core.GATE_A_MAX_PASSIVE_FRACTION,
              "verdict": ("CALIBRATED" if (bh_audit["fraction"] is not None
                                           and bh_audit["fraction"] <= core.GATE_A_MAX_PASSIVE_FRACTION)
                          else "UNCALIBRATED")}

    ratio = None
    if bh_payload["jeffreys95"][0] and bh_audit["jeffreys95"][1]:
        ratio = bh_payload["jeffreys95"][0] / bh_audit["jeffreys95"][1]
    if ratio is None:
        gate_b_verdict = "NOT EVALUABLE"
    elif ratio >= core.GATE_B_INFORMATIVE:
        gate_b_verdict = "INFORMATIVE"
    elif ratio >= core.GATE_B_WEAK:
        gate_b_verdict = "WEAK"
    else:
        gate_b_verdict = "UNINFORMATIVE"
    gate_b = {"boundToBoundRatio": ratio, "informativeAt": core.GATE_B_INFORMATIVE,
              "weakAt": core.GATE_B_WEAK, "verdict": gate_b_verdict,
              "payloadLower": bh_payload["jeffreys95"][0],
              "passiveAuditUpper": bh_audit["jeffreys95"][1]}

    coherent = [r for r in payload if r["significantWindows"] >= core.GATE_C_MIN_SIGNIFICANT_WINDOWS]
    gate_c = {"payloadObjectsWithThreeSignificantWindows": len(coherent),
              "required": core.GATE_C_MIN_OBJECTS,
              "verdict": "POWERED" if len(coherent) >= core.GATE_C_MIN_OBJECTS else "UNDERPOWERED"}

    rung_counts = defaultdict(int)
    for r in payload:
        rung_counts[r["matchRung"]] += 1
    fallback_share = sum(v for k, v in rung_counts.items() if k >= 3) / max(len(payload), 1)

    by_regime = defaultdict(lambda: {"objects": 0, "significant": 0, "periods": []})
    for r in payload:
        cell = by_regime[r["regime"]]
        cell["objects"] += 1
        if r["significantBH"]:
            cell["significant"] += 1
            cell["periods"].append(r["dominantPeriodDays"])
    regimes = {k: {"objects": v["objects"], "significant": v["significant"],
                   "fraction": v["significant"] / v["objects"] if v["objects"] else None,
                   "medianPeriodDays": float(np.median(v["periods"])) if v["periods"] else None,
                   "p25PeriodDays": float(np.percentile(v["periods"], 25)) if v["periods"] else None,
                   "p75PeriodDays": float(np.percentile(v["periods"], 75)) if v["periods"] else None}
               for k, v in sorted(by_regime.items())}

    by_operator = defaultdict(lambda: {"objects": 0, "significant": 0, "periods": []})
    for r in payload:
        cell = by_operator[r["operator"]]
        cell["objects"] += 1
        if r["significantBH"]:
            cell["significant"] += 1
            cell["periods"].append(r["dominantPeriodDays"])
    operators = {k: {"objects": v["objects"], "significant": v["significant"],
                     "fraction": v["significant"] / v["objects"] if v["objects"] else None,
                     "medianPeriodDays": float(np.median(v["periods"])) if v["periods"] else None}
                 for k, v in sorted(by_operator.items()) if v["objects"] >= 10}

    # prereg 6.4: the by-year null diagnostic for the unmatched solar-era confound.
    by_year = defaultdict(lambda: {"objects": 0, "significant": 0})
    for r in audit:
        year = 1970 + int(r["bestWindowStartMs"] / core.DAY_MS / 365.25)
        cell = by_year[year]
        cell["objects"] += 1
        cell["significant"] += int(bool(r["significantBH"]))
    null_by_year = {str(k): dict(v, fraction=v["significant"] / v["objects"])
                    for k, v in sorted(by_year.items()) if v["objects"] >= 50}

    by_nband = defaultdict(lambda: {"payload": 0, "payloadSig": 0, "audit": 0, "auditSig": 0})
    for group, key in ((payload, "payload"), (audit, "audit")):
        for r in group:
            band = core.window_count_band(r["windows"])
            by_nband[band][key] += 1
            by_nband[band][key + "Sig"] += int(bool(r["significantBH"]))

    shifts = sum(len(r["shifts"]) for r in payload)
    stops = sum(len(r["stops"]) for r in payload)
    audit_shifts = sum(len(r["shifts"]) for r in audit)
    audit_stops = sum(len(r["stops"]) for r in audit)
    shift_episodes = sum(episodes(r["shifts"]) for r in payload)
    stop_episodes = sum(episodes(r["stops"]) for r in payload)
    audit_shift_episodes = sum(episodes(r["shifts"]) for r in audit)
    audit_stop_episodes = sum(episodes(r["stops"]) for r in audit)
    payload_eligible = sum(1 for r in payload if r["windows"] >= core.CHANGEPOINT_MIN_WINDOWS)
    audit_eligible = sum(1 for r in audit if r["windows"] >= core.CHANGEPOINT_MIN_WINDOWS)

    return {
        "channel": channel,
        "registration": "docs/cadence-preregistration-20260921.md",
        "population": {"payloadObjects": len(payload),
                       "passiveCalibrationObjects": len(calibration),
                       "passiveAuditObjects": len(audit),
                       "totalWindowsAnalysed": sum(r["windows"] for r in rows)},
        "thresholds": {"pooledCalibrationP99": pooled,
                       "sensitivityPercentiles": sensitivity,
                       "cellsAtOrAboveMinimum": [len(t) for t in thresholds],
                       "objectNullBands": {k: int(v.size) for k, v in band_reference.items()}},
        "E3_bh": {"payload": bh_payload, "passiveAudit": bh_audit},
        "E3_rawWindowThreshold": {"payload": raw_payload, "passiveAudit": raw_audit},
        "matchRungs": {str(k): v for k, v in sorted(rung_counts.items())},
        "payloadExposureOnFallbackRungs": fallback_share,
        "E4_byRegime": regimes,
        "E4_byOperator": operators,
        "nullByYear": null_by_year,
        "byWindowCountBand": {k: dict(v) for k, v in sorted(by_nband.items())},
        "E2_changepoints": {
            "payloadEligibleObjects": payload_eligible,
            "payloadShifts": shifts, "payloadStops": stops,
            "payloadShiftEpisodes": shift_episodes, "payloadStopEpisodes": stop_episodes,
            "auditShiftEpisodes": audit_shift_episodes, "auditStopEpisodes": audit_stop_episodes,
            "payloadShiftEpisodesPerObject": shift_episodes / payload_eligible if payload_eligible else None,
            "payloadStopEpisodesPerObject": stop_episodes / payload_eligible if payload_eligible else None,
            "auditShiftEpisodesPerObject": audit_shift_episodes / audit_eligible if audit_eligible else None,
            "auditStopEpisodesPerObject": audit_stop_episodes / audit_eligible if audit_eligible else None,
            "payloadShiftsPerObject": shifts / payload_eligible if payload_eligible else None,
            "payloadStopsPerObject": stops / payload_eligible if payload_eligible else None,
            "auditEligibleObjects": audit_eligible,
            "auditShifts": audit_shifts, "auditStops": audit_stops,
            "auditShiftsPerObject": audit_shifts / audit_eligible if audit_eligible else None,
            "auditStopsPerObject": audit_stops / audit_eligible if audit_eligible else None},
        "gates": {"A": gate_a, "B": gate_b, "C": gate_c},
        "harmonicAmbiguousPayloads": sum(1 for r in payload if r["harmonicAmbiguous"]),
        "pValueAtFloorPayloads": sum(1 for r in payload if r["pValueAtFloor"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--shards", required=True, nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="stem; .jsonl and -receipt.json")
    parser.add_argument("--channel", default="mean_motion")
    args = parser.parse_args()
    receipt = analyse(args.artifacts, args.shards, args.out, args.channel)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
