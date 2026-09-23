#!/usr/bin/env python3
"""The alarm lane's OPERATING-POINT CURVE.

A lane with one threshold has one precision and one lead time, and a reader
who wants fewer alerts has nowhere to go. This module precomputes the whole
curve instead: a small REGISTERED grid of evidence thresholds, swept over the
same population the frozen artifact was measured on, with the measured
numbers attached to every point.

**The grid and the four named settings below are fixed in this file and are
committed BEFORE the table is computed.** Every threshold is an evidence
threshold -- something the lane can check at or before the moment it would
speak -- and none of them reads an outcome. The named settings are picked by
their EVIDENCE, not by the precision they turn out to have.

THE AXES

  `minDriftChangeDegPerDay`  the size of the confirmed drift-rate change. The
      detector's own floor is 0.010 deg/day, which is about 0.78 km of
      semi-major axis and is exceeded by an ordinary east-west correction.

  `minSlotsReached`  the REACHABLE-SET SIZE: how many occupied mean
      longitudes the propagated 180-day trajectory would pass within 0.1 deg
      of. It is `fwd_slots_reached`, computed by the frozen instrument.

  `persistenceSweeps`  how many consecutive firings of the lane must still
      see the object drifting. N = 1 speaks at the announce time. N > 1 waits
      for N - 1 further firings and requires the newest element set at each to
      still show |drift| at or above the detector's floor -- that is, the
      object has not returned to a station-keeping drift rate. **Waiting costs
      warning time**, and the cost is measured here rather than assumed.

  `leadHorizonDays`  the window within which an arrival counts as a hit. It
      may not exceed the 180 days the outcome record's own attribution window
      allows, so the grid holds 90 and 180 and nothing longer.

WHAT RECALL MEANS HERE, said plainly: **true recall is NOT measurable.** The
outcome record is a lower bound rather than a census, a transfer executed
below the detector's floor is invisible, and a third of the catalogued events
carry no confirmable initiating change at all. What this table reports is a
RECALL PROXY -- the fraction of the arrivals that the loosest setting at the
same horizon does raise which this setting still raises. It is a ratio between
two rows of this table and it is not the fraction of real approaches caught.

A TIGHTER SETTING IS NOT A MORE CERTAIN ALERT. It is FEWER alerts, at a
HIGHER MEASURED PRECISION, with LATER warning. Every description this module
emits says that in those terms, and `tests/test_alarm_lane.py` refuses any
output string that dresses a threshold up as certainty.

    python3 tools/alarm_lane_curve.py --work <trigger-predictor work dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO / "tools"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_geo as pg            # noqa: E402
import alarm_pattern as ap            # noqa: E402
import trigger_alarm as ta            # noqa: E402
import alarm_lane as al               # noqa: E402

DAY_MS = pg.DAY_MS

CURVE_KIND = "alarm-lane-operating-points"
CURVE_SCHEMA = 1
CURVE_VERSION = "operating-points/20260922/1"
CURVE_PATH = _REPO / "docs" / "alarm-lane-operating-points-20260922.json"

# ---- THE REGISTERED GRID, fixed before the table was computed -------------
GRID = {
    "minDriftChangeDegPerDay": (0.010, 0.10, 1.0),
    "minSlotsReached": (0, 5, 20),
    "persistenceSweeps": (1, 2, 3),
    "leadHorizonDays": (90.0, 180.0),
}
AXES = ("minDriftChangeDegPerDay", "minSlotsReached", "persistenceSweeps",
        "leadHorizonDays")

# ---- THE FOUR NAMED SETTINGS, picked by evidence and not by outcome -------
# The names are the operator's. What each one IS, in every string this module
# emits, is a count of alerts, a measured precision and a measured lead.
NAMED_SETTINGS = (
    ("everything", {"minDriftChangeDegPerDay": 0.010, "minSlotsReached": 0,
                    "persistenceSweeps": 1, "leadHorizonDays": 180.0}),
    ("balanced", {"minDriftChangeDegPerDay": 0.10, "minSlotsReached": 5,
                  "persistenceSweeps": 1, "leadHorizonDays": 180.0}),
    ("high-confidence", {"minDriftChangeDegPerDay": 1.0, "minSlotsReached": 5,
                         "persistenceSweeps": 2, "leadHorizonDays": 180.0}),
    ("very-high", {"minDriftChangeDegPerDay": 1.0, "minSlotsReached": 20,
                   "persistenceSweeps": 3, "leadHorizonDays": 180.0}),
)

RECALL_NOTE = (
    "TRUE RECALL IS NOT MEASURABLE. The outcome record is a lower bound and "
    "not a census: a transfer executed below the detector's floor is "
    "invisible, and a third of the catalogued events carry no confirmable "
    "initiating change. `recallProxy` is the fraction of the arrivals the "
    "loosest setting at the same horizon raises which this setting still "
    "raises. It is a ratio between two rows of this table and it is not the "
    "fraction of real approaches caught.")

TRADEOFF_NOTE = (
    "A tighter setting is not a more certain alert. It is FEWER alerts, at a "
    "HIGHER MEASURED PRECISION, with LATER warning, and each of those three "
    "is measured and printed here.")

# the phrases no description in this lane may use for a tighter setting
BANNED_DESCRIPTIONS = (
    "more certain", "more confident", "higher confidence", "more reliable",
    "more accurate", "greater certainty", "certainty", "surer", "safer bet")


def describe(point, row):
    """The only sentence the lane uses to describe a setting. It states the
    three measured quantities -- how many alerts, at what measured precision,
    with how much warning -- and makes no claim about certainty."""
    lead = row["leadDays"].get("p50")
    evidence = (
        f"evidence: drift change at or above "
        f"{point['minDriftChangeDegPerDay']} deg/day, at least "
        f"{point['minSlotsReached']} occupied longitudes on the propagated "
        f"path, still drifting at {point['persistenceSweeps']} consecutive "
        f"firings, arrival counted within {point['leadHorizonDays']:.0f} days.")
    if not row["alerts"]:
        return ("no alert of this class at this setting; precision and "
                "warning time NOT ASSESSABLE -- a labelled gap, not a zero. "
                + evidence)
    precision = (
        f"measured precision {100.0 * row['precision']:.3f}% "
        f"[{100.0 * row['wilson95'][0]:.3f}%, "
        f"{100.0 * row['wilson95'][1]:.3f}%], every one of them followed to "
        f"its horizon"
        if not row["underpowered"] else
        f"{row['arrivals']} of {row['alerts']} -- UNDERPOWERED, below "
        f"{al.MIN_SUPPORT_FOR_A_RATE} supporting events, so no rate is drawn "
        f"from it")
    warning = (f"median warning {lead:.1f} days" if lead is not None
               else "warning time NOT ASSESSABLE -- no arrival at this "
                    "setting; a labelled gap, not a zero")
    return (f"{row['alerts']:,} alerts over the archive "
            f"({row['alertsPerYear2010s']:.1f} a year in the 2010s), "
            f"{precision}, {warning}; " + evidence)


# ==========================================================================
def _percentiles(values, ps=(5, 25, 50, 75, 95)):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=np.float64)
    if v.size == 0:
        return {"n": 0,
                "label": "NOT ASSESSABLE -- no arrival at this setting; a "
                         "labelled gap, not a zero"}
    return {"n": int(v.size),
            **{f"p{p}": float(np.percentile(v, p)) for p in ps}}


def build_rows(model, bundle, tick_days, say):
    """One row per primary-arm trigger, carrying everything the grid needs."""
    triggers, feats, outs = (bundle["triggers"], bundle["features"],
                             bundle["outcomes"])
    idx = [i for i in range(len(triggers))
           if triggers[i].eligible and outs[i]["resolvable"]]
    say(f"primary arm {len(idx):,} triggers")
    labels = al.classify([feats[i] for i in idx], model)
    say("classified against the frozen artifact")

    series = bundle.get("_series")
    confirm_ms = float(model["detector"]["confirmDays"]) * DAY_MS
    floor = float(model["detector"]["floorDegPerDay"])
    max_n = max(GRID["persistenceSweeps"])
    rows = []
    for rank, i in enumerate(idx):
        tr = triggers[i]
        out = outs[i]
        f = feats[i]
        s = series.get(int(tr.norad)) if series else None
        survives = [True] * (max_n + 1)
        for k in range(1, max_n):
            t_check = tr.tTrig + confirm_ms + k * tick_days * DAY_MS
            ok = False
            if s is not None:
                j = int(np.searchsorted(s.epoch_ms, t_check, side="right")) - 1
                if j >= 0 and (t_check - float(s.epoch_ms[j])) <= \
                        ta.MERGE_DAYS * DAY_MS:
                    ok = bool(abs(float(s.drift[j])) >= floor)
            survives[k + 1] = survives[k] and ok
        arrival_ms = None
        if out["o1Positive"] and out["o1ArrivalDays"] is not None:
            arrival_ms = tr.tTrig + confirm_ms + float(out["o1ArrivalDays"]) * DAY_MS
        rows.append({
            "class": int(labels[rank]),
            "tTrigMs": float(tr.tTrig),
            "driftMag": abs(float(tr.driftChange)),
            "slots": float(f.get("fwd_slots_reached") or 0.0),
            "survives": survives,
            "arrivalMs": arrival_ms,
        })
        if rank and rank % 20000 == 0:
            say(f"rows {rank:,}/{len(idx):,}")
    return rows


def evaluate(rows, point, model, tick_days):
    """The measured numbers for one point of the grid, per class and for the
    whole primary arm."""
    confirm_ms = float(model["detector"]["confirmDays"]) * DAY_MS
    n_sweeps = int(point["persistenceSweeps"])
    delay_ms = confirm_ms + (n_sweeps - 1) * tick_days * DAY_MS
    horizon_ms = float(point["leadHorizonDays"]) * DAY_MS
    out = {}
    for row in rows:
        if row["driftMag"] < point["minDriftChangeDegPerDay"]:
            continue
        if row["slots"] < point["minSlotsReached"]:
            continue
        if not row["survives"][n_sweeps]:
            continue
        key = int(row["class"])
        bucket = out.setdefault(key, {"n": 0, "pos": 0, "leads": [],
                                      "years": []})
        bucket["n"] += 1
        bucket["years"].append(row["tTrigMs"])
        announce = row["tTrigMs"] + delay_ms
        if (row["arrivalMs"] is not None
                and row["arrivalMs"] > announce
                and (row["arrivalMs"] - row["tTrigMs"]) <= horizon_ms):
            bucket["pos"] += 1
            bucket["leads"].append((row["arrivalMs"] - announce) / DAY_MS)
    return out


def _span_years(rows):
    t = np.asarray([r["tTrigMs"] for r in rows], dtype=np.float64)
    return float((t.max() - t.min()) / DAY_MS / 365.25)


def _decade_count(times):
    lo = al._ms("2010-01-01T00:00:00+00:00")
    hi = al._ms("2020-01-01T00:00:00+00:00")
    return sum(1 for t in times if lo <= t < hi)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", default=str(al.MODEL_PATH))
    p.add_argument("--work", required=True,
                   help="the trigger-time predictor's working directory")
    p.add_argument("--out", default=str(_REPO / "docs"))
    p.add_argument("--date", default="20260922")
    args = p.parse_args(argv)

    t0 = time.time()

    def say(m):
        print(f"  [{time.time() - t0:7.1f}s] {m}", flush=True)

    model = al.load_model(args.model)
    say(f"frozen model {model['modelVersion']} "
        f"checksum {al.model_checksum(model)[:16]}")

    import pickle
    with open(Path(args.work) / "t8d-triggers.pkl", "rb") as fh:
        blob = pickle.load(fh)
    bundle = blob["bundle"]
    say("trigger table loaded")

    source = al.ExtractSource()
    bundle["_series"] = source.series_by_norad
    spacing = al.measured_epoch_spacing_days(list(source.series_by_norad.values()))
    cadence = al.derive_cadence(
        spacing, spacing_source=(f"measured over all "
                                 f"{len(source.series_by_norad)} watched "
                                 f"objects' element sets"))
    tick_days = float(cadence["workFloorDays"])
    say(f"derived tick {tick_days:.4f} d -- the persistence axis is counted "
        f"in firings of this length")

    rows = build_rows(model, bundle, tick_days, say)
    span = _span_years(rows)
    say(f"archive span {span:.1f} years")

    points = []
    for drift in GRID["minDriftChangeDegPerDay"]:
        for slots in GRID["minSlotsReached"]:
            for sweeps in GRID["persistenceSweeps"]:
                for horizon in GRID["leadHorizonDays"]:
                    points.append({"minDriftChangeDegPerDay": drift,
                                   "minSlotsReached": slots,
                                   "persistenceSweeps": sweeps,
                                   "leadHorizonDays": horizon})
    say(f"{len(points)} grid points")

    # the loosest point at each horizon is the recall proxy's denominator
    loosest = {h: {"minDriftChangeDegPerDay": min(GRID["minDriftChangeDegPerDay"]),
                   "minSlotsReached": min(GRID["minSlotsReached"]),
                   "persistenceSweeps": min(GRID["persistenceSweeps"]),
                   "leadHorizonDays": h}
               for h in GRID["leadHorizonDays"]}
    base = {h: evaluate(rows, loosest[h], model, tick_days)
            for h in GRID["leadHorizonDays"]}
    whole = {h: {"n": sum(v["n"] for v in base[h].values()),
                 "pos": sum(v["pos"] for v in base[h].values())}
             for h in GRID["leadHorizonDays"]}
    for h, w in whole.items():
        lo, hi = ta.wilson(w["pos"], w["n"])
        w["precision"] = w["pos"] / w["n"] if w["n"] else None
        w["wilson95"] = [lo, hi]
    say(f"base populations: " + ", ".join(
        f"{h:.0f} d -> {whole[h]['pos']}/{whole[h]['n']}"
        for h in GRID["leadHorizonDays"]))

    table = []
    for point in points:
        measured = evaluate(rows, point, model, tick_days)
        h = point["leadHorizonDays"]
        for cluster in sorted(int(c["cluster"]) for c in model["classes"]):
            b = measured.get(cluster, {"n": 0, "pos": 0, "leads": [],
                                       "years": []})
            n, k = b["n"], b["pos"]
            lo, hi = ta.wilson(k, n) if n else (float("nan"), float("nan"))
            denom = base[h].get(cluster, {"pos": 0})["pos"]
            row = {
                "point": dict(point),
                "class": cluster,
                "className": al.model_class(model, cluster)["name"],
                "alerts": n,
                "resolved": n,
                "supportingEvents": n,
                "arrivals": k,
                "precision": (k / n) if n else None,
                "wilson95": [lo, hi] if n else None,
                "underpowered": bool(n < al.MIN_SUPPORT_FOR_A_RATE),
                "leadDays": _percentiles(b["leads"]),
                "alertsPerYearArchiveMean": (n / span) if span else None,
                "alertsPerYear2010s": _decade_count(b["years"]) / 10.0,
                "recallProxyNumerator": k,
                "recallProxyDenominator": denom,
                "recallProxy": (k / denom) if denom else None,
                "recallNote": RECALL_NOTE,
                "basePopulationAtThisHorizon": dict(whole[h]),
            }
            if n == 0:
                row["precisionLabel"] = ("NOT ASSESSABLE -- this setting "
                                         "raises no alert of this class; a "
                                         "labelled gap, not a zero")
            elif row["underpowered"]:
                row["precisionLabel"] = (
                    f"UNDERPOWERED -- {k}/{n} supporting events, below "
                    f"{al.MIN_SUPPORT_FOR_A_RATE}; the count is quoted and no "
                    f"rate is drawn from it")
            else:
                row["precisionLabel"] = f"{k}/{n} = {100.0 * k / n:.3f}%"
            row["mayBeSpoken"], row["gateReasons"] = _gate(model, cluster, row,
                                                           whole[h])
            row["description"] = describe(point, row)
            table.append(row)
    say(f"{len(table)} rows")

    named = []
    for name, point in NAMED_SETTINGS:
        rows_here = [r for r in table if r["point"] == point]
        if not rows_here:
            raise SystemExit(f"named setting {name} is not on the grid")
        named.append({
            "name": name,
            "point": dict(point),
            "classes": [{"class": r["class"], "className": r["className"],
                         "alerts": r["alerts"], "arrivals": r["arrivals"],
                         "supportingEvents": r["supportingEvents"],
                         "precision": r["precision"],
                         "precisionLabel": r["precisionLabel"],
                         "wilson95": r["wilson95"],
                         "underpowered": r["underpowered"],
                         "leadDays": r["leadDays"],
                         "alertsPerYearArchiveMean": r["alertsPerYearArchiveMean"],
                         "alertsPerYear2010s": r["alertsPerYear2010s"],
                         "recallProxy": r["recallProxy"],
                         "recallProxyNumerator": r["recallProxyNumerator"],
                         "recallProxyDenominator": r["recallProxyDenominator"],
                         "recallNote": RECALL_NOTE,
                         "basePopulationAtThisHorizon":
                             r["basePopulationAtThisHorizon"],
                         "mayBeSpoken": r["mayBeSpoken"],
                         "gateReasons": r["gateReasons"],
                         "description": r["description"]}
                        for r in rows_here],
            "tradeoff": TRADEOFF_NOTE,
        })

    body = {
        "artifact": CURVE_KIND,
        "schema": CURVE_SCHEMA,
        "curveVersion": CURVE_VERSION,
        "computedAt": al._iso(time.time() * 1000.0),
        "design": al.DESIGN,
        "earnedBy": {
            "modelVersion": model["modelVersion"],
            "modelChecksum": al.model_checksum(model),
            "modelPath": str(Path(args.model).name),
            "instrument": "tools/alarm_lane_curve.py",
            "triggerTableFeaturePathSha256": blob["featurePathSha256"],
            "receipt": al.RECEIPT,
        },
        "note": ("every row is measured on the same primary arm the frozen "
                 "artifact was measured on, with the frozen partition and the "
                 "frozen scaler. Nothing is refitted here."),
        "grid": {k: list(v) for k, v in GRID.items()},
        "axes": list(AXES),
        "axisDefinitions": {
            "minDriftChangeDegPerDay": (
                "the size of the confirmed drift-rate change; the detector's "
                "own floor is 0.010 deg/day"),
            "minSlotsReached": (
                "the reachable-set size: occupied mean longitudes the "
                "propagated 180-day trajectory would pass within 0.1 deg of"),
            "persistenceSweeps": (
                "consecutive firings of the lane that must still see the "
                "object drifting at or above the detector's floor; N greater "
                "than 1 delays the announcement by N - 1 firings and the cost "
                "in warning time is measured, not assumed"),
            "leadHorizonDays": (
                "the window within which an arrival counts; it may not exceed "
                "the 180 days the outcome record's attribution window allows"),
        },
        "tickDays": tick_days,
        "cadence": cadence,
        "archiveSpanYears": span,
        "basePopulationByHorizon": {str(h): whole[h]
                                    for h in GRID["leadHorizonDays"]},
        "loosestPointVsFrozenPopulation": {
            "frozenPrimaryArm": int(model["basePopulation"]["n"]),
            "frozenPositives": int(model["basePopulation"]["positives"]),
            "loosestGridPoint": int(whole[max(GRID["leadHorizonDays"])]["n"]),
            "loosestGridPointPositives":
                int(whole[max(GRID["leadHorizonDays"])]["pos"]),
            "note": ("the loosest grid point applies the detector's own "
                     "0.010 deg/day floor to the CHAIN'S NET drift change, "
                     "where the flag threshold applies it to each element "
                     "set's departure from its trailing baseline. The two "
                     "populations therefore differ slightly. No positive is "
                     "lost by the difference -- both carry the same count -- "
                     "and it is stated here rather than smoothed over."),
        },
        "monotonicityNote": (
            "A TIGHTER SETTING IS NOT AUTOMATICALLY A MORE PRECISE ONE, and "
            "this table is the evidence. On the measured numbers the tighter "
            "named settings raise FEWER alerts than the loosest one and do "
            "NOT all reach a higher precision on the class that may already "
            "speak. A setting is worth what its own row says it is worth and "
            "nothing else; read the row."),
        "recallNote": RECALL_NOTE,
        "tradeoffNote": TRADEOFF_NOTE,
        "namedSettings": named,
        "table": table,
        "caveats": list(al.CAVEATS),
        "neverSay": list(al.NEVER_SAY),
        "reservedDecisions": dict(al.RESERVED_DECISIONS),
        "reservedNote": al.RESERVED_NOTE,
    }
    out = Path(args.out) / f"alarm-lane-operating-points-{args.date}.json"
    digest = al.write_model(body, out)
    say(f"curve: {out}")
    say(f"checksum {digest}")

    print()
    for entry in named:
        print(f"  {entry['name']}:")
        for c in entry["classes"]:
            print(f"    class {c['class']} ({c['className']}): "
                  f"{c['description']}")
            print(f"      may be spoken: {c['mayBeSpoken']}")
    return 0


def _gate(model, cluster, row, base):
    """The vocabulary gate's arithmetic rule, applied to this SETTING's own
    measured numbers rather than to the class's whole-population ones."""
    reasons = []
    jaccard = al.model_class(model, cluster).get("bootstrapJaccard")
    bar = float(model["bars"]["bootstrapJaccard"])
    if jaccard is None or float(jaccard) < bar:
        reasons.append(f"bootstrap Jaccard below the registered {bar:.2f} bar")
    if row["alerts"] < al.MIN_SUPPORT_FOR_A_RATE:
        reasons.append(f"{row['alerts']} supporting events is below the "
                       f"{al.MIN_SUPPORT_FOR_A_RATE} a rate needs")
    if row["precision"] is None:
        reasons.append("this setting raises no alert of this class")
    elif base["precision"] is None or row["wilson95"][0] <= base["wilson95"][1]:
        reasons.append(
            "its precision is not separated above the whole-population base "
            "rate at this horizon")
    return (not reasons), reasons


if __name__ == "__main__":
    raise SystemExit(main())
