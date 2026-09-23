#!/usr/bin/env python3
"""T16b measurement (B): what fraction of real, operator-reported manoeuvres
the programme's LEO burn detector flags — the first recall number the
programme has.

Registered in docs/t16b-truthset-preregistration-20260922.md.

The detector is `tools/proximity_plane.detect_manoeuvres`, T8b's own
arithmetic and the function the alarm lane's LEO arm triggers on. It is
imported and called, never edited; a gate records that its file is unchanged.

The labels are the MAD-LEO mission-reported subset (CC BY 4.0,
doi 10.6084/m9.figshare.33446503.v1): 1,134 manoeuvres of eleven geodetic and
altimetry spacecraft, taken from IDS/DORIS mission-published histories. The
element sets under test are this programme's own archive.

Two things are printed before any recall cell, because a recall number without
them is meaningless: the smallest semi-major-axis step each arm of the
detector can flag on that spacecraft, and the count of flags in labelled-quiet
windows.

Usage:
  truthset_recall.py --out docs/t16b-truthset-recall-20260922.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proximity_plane as pp                                    # noqa: E402

REPO = Path(__file__).resolve().parents[1]
# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
TRUTH_ROOT = Path(os.environ.get("ORBIT_TRUTHSET_ROOT",
                                 "truthset.not-configured"))
ARCHIVE = Path(os.environ.get("ORBIT_ARCHIVE_DB",
                              "element-archive.not-configured.sqlite3"))
MADLEO = TRUTH_ROOT / "madleo"

# T8b's pooled LEO calibration, as measured and published in
# docs/proximity-leo-results-20260922.md section 2.2. This is what "the
# detector at its shipped settings" means.
POOLED_SIGMA_N = 6.2747e-5          # rev/day
POOLED_SIGMA_THETA = 0.6994         # degrees

DAY_MS = 86400000.0

# sat_id -> NORAD, asserted against the archive's own object table by a test
SAT_NORAD = {
    "cryosat-2": 36508,
    "hy-2a": 37781,
    "jason-1": 26997,
    "jason-2": 33105,
    "jason-3": 41240,
    "saral": 39086,
    "sentinel-3a": 41335,
    "sentinel-3b": 43437,
    "sentinel-6a": 46984,
    "swot": 54754,
    "topex-poseidon": 22076,
}

PLACEBO_SHIFT_DAYS = (-90.0, -60.0, -30.0, 30.0, 60.0, 90.0)

# registered burn-size bins, on the archive-bracketed |delta a| proxy (metres)
DA_BINS = ((0.0, 20.0), (20.0, 50.0), (50.0, 100.0), (100.0, 200.0),
           (200.0, 500.0), (500.0, math.inf))

DETECTOR_FILES = ("tools/proximity_plane.py", "tools/trigger_alarm.py",
                  "tools/alarm_lane_leo.py")


def parse_iso(text: str) -> float:
    """MAD-LEO timestamps: ISO-8601 UTC, mixed millisecond and whole-second
    precision, always ending in Z."""
    text = text.strip()
    if not text:
        return float("nan")
    if text.endswith("Z"):
        text = text[:-1]
    return dt.datetime.fromisoformat(text).replace(
        tzinfo=dt.timezone.utc).timestamp() * 1000.0


def wilson(k: int, n: int, z: float = 1.959963985):
    if n == 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def load_labels():
    events = {}
    with (MADLEO / "mission_reported__annotations__maneuver_annotations.csv").open() as fh:
        for row in csv.DictReader(fh):
            events[row["annotation_id"]] = {
                "id": row["annotation_id"],
                "sat": row["sat_id"],
                "eventMs": parse_iso(row["event_time_utc"]),
                "role": row["event_time_role"],
                "opStartMs": parse_iso(row["reported_operation_start_utc"]),
                "opEndMs": parse_iso(row["reported_operation_end_utc"]),
                "windowStartMs": parse_iso(row["window_start_utc"]),
                "windowEndMs": parse_iso(row["window_end_utc"]),
                "impulses": int(row["impulse_count"] or 0),
                "uncertaintyS": float(row["time_uncertainty_seconds"] or 0.0),
            }
    with (MADLEO / "mission_reported__annotations__event_windows.csv").open() as fh:
        for row in csv.DictReader(fh):
            if row["annotation_id"] in events:
                events[row["annotation_id"]]["tier"] = row["confidence_tier"]
                events[row["annotation_id"]]["aligned"] = row["aligned"]
    stable = []
    with (MADLEO / "mission_reported__annotations__stable_windows.csv").open() as fh:
        for row in csv.DictReader(fh):
            stable.append({
                "id": row["annotation_id"],
                "sat": row["sat_id"],
                "startMs": parse_iso(row["window_start_utc"]),
                "endMs": parse_iso(row["window_end_utc"]),
                "tier": row["confidence_tier"],
                "suspect": "suspect_unreported_maneuver" in (row["quality_flags"] or ""),
            })
    return list(events.values()), stable


def load_elements(norad: int):
    """The object's whole archive history, in the shape the detector reads."""
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q "
        "FROM element_set WHERE norad=? ORDER BY epoch_ms", (norad,)).fetchall()
    db.close()
    if not rows:
        return None
    arr = np.asarray(rows, dtype=np.float64)
    return {
        "epoch_ms": arr[:, 0].astype(np.int64),
        "n": arr[:, 1] / 1e8,
        "e": arr[:, 2] / 1e8,
        "inc": arr[:, 3] / 1e4,
        "raan": arr[:, 4] / 1e4,
    }


def detector_floor(el, sigma_n, sigma_theta):
    """The smallest semi-major-axis step the in-track channel can flag, and the
    along-track impulse that produces it.

    Derived, not quoted:  a = (mu / (2 pi n / 86400)^2)^(1/3)  gives
    da/a = -(2/3) dn/n, so |da|min = (2/3)(a/n) thr_n; and for a near-circular
    orbit da = 2 dv / n_ang, so dv = da n_ang / 2.
    """
    n = float(np.median(el["n"]))
    a_km = float(pp.semi_major_axis_km(n))
    n_ang = 2.0 * math.pi * n / 86400.0                 # rad/s
    # the three terms of the shipped threshold, at this object's own median
    drag = 3.0 * float(np.median(np.abs(np.diff(el["n"]) /
                                       np.maximum(np.diff(el["epoch_ms"]) / DAY_MS, 1e-6))))
    spacing = float(np.median(np.diff(el["epoch_ms"]) / DAY_MS))
    terms = {
        "fitNoise": pp.BURN_SIGMA_K * sigma_n,
        "ownDrag": drag * spacing,
        "floor": 1.5 * n * pp.DA_FLOOR_KM / a_km,
    }
    thr_n = max(terms.values())
    da_km = (2.0 / 3.0) * (a_km / n) * thr_n
    return {
        "semiMajorAxisKm": a_km,
        "medianSpacingDays": spacing,
        "thresholdRevPerDay": thr_n,
        "thresholdTerms": {k: float(v) for k, v in terms.items()},
        "thresholdSetBy": max(terms, key=terms.get),
        "minDetectableDaMetres": da_km * 1000.0,
        "minDetectableDvMps": da_km * 1000.0 * n_ang / 2.0,
    }


def bracketed_da_metres(el, t0_ms, t1_ms):
    """|delta a| across a window, from the element sets bracketing it.

    MAD-LEO's own quality statistic. A stratifier, never evidence: it is read
    from the very elements the detector reads.
    """
    ep = el["epoch_ms"]
    before = np.nonzero(ep <= t0_ms)[0]
    after = np.nonzero(ep >= t1_ms)[0]
    if before.size == 0 or after.size == 0:
        return None
    a0 = float(pp.semi_major_axis_km(el["n"][before[-1]]))
    a1 = float(pp.semi_major_axis_km(el["n"][after[0]]))
    return abs(a1 - a0) * 1000.0


def bin_of(value, bins):
    if value is None:
        return "unknown"
    for lo, hi in bins:
        if lo <= value < hi:
            return f"{lo:g}-{hi:g} m" if math.isfinite(hi) else f">={lo:g} m"
    return "unknown"


def detector_state_clean():
    proc = subprocess.run(["git", "diff", "--stat", "--"] + list(DETECTOR_FILES),
                          cwd=str(REPO), capture_output=True)
    dirty = proc.stdout.decode().strip()
    hashes = {}
    for path in DETECTOR_FILES:
        out = subprocess.run(["git", "hash-object", path], cwd=str(REPO),
                             capture_output=True)
        hashes[path] = out.stdout.decode().strip()
    return {"clean": dirty == "", "diffstat": dirty, "blobHashes": hashes}


def measure(say):
    labels, stable = load_labels()
    by_sat: dict[str, list] = {}
    for lab in labels:
        by_sat.setdefault(lab["sat"], []).append(lab)
    stable_by_sat: dict[str, list] = {}
    for win in stable:
        stable_by_sat.setdefault(win["sat"], []).append(win)

    arms = {"pooled": (POOLED_SIGMA_N, POOLED_SIGMA_THETA), "perObject": None}
    results = {"arms": {}, "perSpacecraft": {}}

    cache = {}
    for sat, norad in sorted(SAT_NORAD.items()):
        el = load_elements(norad)
        if el is None:
            say(f"  {sat}: NO ARCHIVE ROWS")
            continue
        cache[sat] = el
        say(f"  {sat} ({norad}): {el['epoch_ms'].size} element sets, "
            f"{(el['epoch_ms'][-1] - el['epoch_ms'][0]) / DAY_MS:.0f} d span")

    for arm, sigmas in arms.items():
        per_sat = {}
        for sat, el in cache.items():
            if sigmas is None:
                s_theta, s_n = pp.object_sigma_contributions(el)
            else:
                s_n, s_theta = sigmas
            if not (np.isfinite(s_n) and np.isfinite(s_theta)):
                continue
            det = pp.detect_manoeuvres(el, float(s_n), float(s_theta))
            ep = el["epoch_ms"]
            intrack = ep[det["intrack"]] if det["intrack"].size else np.asarray([], dtype=np.int64)
            plane = ep[det["plane"]] if det["plane"].size else np.asarray([], dtype=np.int64)
            either = np.union1d(intrack, plane)
            campaigns = campaign_starts(either)
            per_sat[sat] = {
                "sigmaN": float(s_n), "sigmaTheta": float(s_theta),
                "floor": detector_floor(el, float(s_n), float(s_theta)),
                "flags": {"intrack": intrack, "plane": plane, "either": either,
                          "campaignStarts": campaigns},
            }
        results["arms"][arm] = per_sat

    # ---- recall ------------------------------------------------------------
    out_arms = {}
    for arm, per_sat in results["arms"].items():
        windows = {
            "madleoEventWindow": None,           # the label's own -6 h / +24 h
            "pm1d": 1.0,
            "pm3d": 3.0,
            "spacingAware": "spacing",
        }
        arm_out = {"windows": {}, "perSpacecraft": {}}
        for wname, wspec in windows.items():
            cells = {"overall": {"k": 0, "n": 0, "notEvaluable": 0},
                     "byTier": {}, "bySpacecraft": {}, "byImpulses": {},
                     "byDaBin": {}, "byFloor": {},
                     "byChannel": {"intrack": 0, "plane": 0},
                     "campaignLevel": {"k": 0, "n": 0},
                     "placebo": {"k": 0, "n": 0}}
            for sat, state in per_sat.items():
                el = cache[sat]
                ep = el["epoch_ms"]
                spacing_ms = float(np.median(np.diff(ep)))
                for lab in by_sat.get(sat, []):
                    if wspec is None:
                        lo, hi = lab["windowStartMs"], lab["windowEndMs"]
                    elif wspec == "spacing":
                        lo = lab["eventMs"] - 0.25 * DAY_MS
                        hi = lab["eventMs"] + 2.0 * spacing_ms
                    else:
                        lo = lab["eventMs"] - wspec * DAY_MS
                        hi = lab["eventMs"] + wspec * DAY_MS
                    evaluable = (ep.size >= pp.BURN_BASELINE_SAMPLES + 3
                                 and ep[0] <= lo and ep[-1] >= hi)
                    if not evaluable:
                        cells["overall"]["notEvaluable"] += 1
                        continue
                    hit_i = bool(np.any((state["flags"]["intrack"] >= lo)
                                        & (state["flags"]["intrack"] <= hi)))
                    hit_p = bool(np.any((state["flags"]["plane"] >= lo)
                                        & (state["flags"]["plane"] <= hi)))
                    hit = hit_i or hit_p
                    hit_c = bool(np.any((state["flags"]["campaignStarts"] >= lo)
                                        & (state["flags"]["campaignStarts"] <= hi)))
                    cells["overall"]["n"] += 1
                    cells["overall"]["k"] += int(hit)
                    cells["byChannel"]["intrack"] += int(hit_i)
                    cells["byChannel"]["plane"] += int(hit_p)
                    cells["campaignLevel"]["n"] += 1
                    cells["campaignLevel"]["k"] += int(hit_c)
                    for key, value in (("byTier", lab.get("tier", "?")),
                                       ("bySpacecraft", sat),
                                       ("byImpulses", str(lab["impulses"]))):
                        cell = cells[key].setdefault(value, {"k": 0, "n": 0})
                        cell["n"] += 1
                        cell["k"] += int(hit)
                    da = bracketed_da_metres(el, lab["windowStartMs"],
                                             lab["windowEndMs"])
                    cell = cells["byDaBin"].setdefault(bin_of(da, DA_BINS),
                                                       {"k": 0, "n": 0})
                    cell["n"] += 1
                    cell["k"] += int(hit)
                    # the same labels split at this arm's OWN floor
                    floor_m = state["floor"]["minDetectableDaMetres"]
                    side = ("unknown" if da is None
                            else "aboveFloor" if da >= floor_m else "belowFloor")
                    cell = cells["byFloor"].setdefault(side, {"k": 0, "n": 0})
                    cell["n"] += 1
                    cell["k"] += int(hit)
                    # POST-REGISTRATION CONTROL, labelled as such: the same
                    # association rule applied to windows displaced in time.
                    # Without it there is no way to say whether a recall of a
                    # few per cent is detection or the background density of
                    # flags on an object that is flagged often.
                    for shift in PLACEBO_SHIFT_DAYS:
                        plo = lo + shift * DAY_MS
                        phi = hi + shift * DAY_MS
                        if plo < ep[0] or phi > ep[-1]:
                            continue
                        if any(abs(plo - other["eventMs"]) < 2.0 * DAY_MS
                               for other in by_sat.get(sat, [])):
                            continue
                        cells["placebo"]["n"] += 1
                        cells["placebo"]["k"] += int(np.any(
                            (state["flags"]["either"] >= plo)
                            & (state["flags"]["either"] <= phi)))
            arm_out["windows"][wname] = with_intervals(cells)
        # ---- floors and false flags, per spacecraft ------------------------
        for sat, state in per_sat.items():
            el = cache[sat]
            das = [bracketed_da_metres(el, lab["windowStartMs"], lab["windowEndMs"])
                   for lab in by_sat.get(sat, [])]
            das = np.asarray([v for v in das if v is not None], dtype=np.float64)
            arm_out["perSpacecraft"][sat] = {
                "norad": SAT_NORAD[sat],
                "labelDeltaAMetres": {
                    "n": int(das.size),
                    "p25": float(np.percentile(das, 25)) if das.size else None,
                    "p50": float(np.median(das)) if das.size else None,
                    "p75": float(np.percentile(das, 75)) if das.size else None,
                    "belowThisArmsFloor": int((das < state["floor"]["minDetectableDaMetres"]).sum()) if das.size else 0,
                },
                "sigmaN": state["sigmaN"], "sigmaTheta": state["sigmaTheta"],
                "floor": state["floor"],
                "flagCounts": {
                    "intrack": int(state["flags"]["intrack"].size),
                    "plane": int(state["flags"]["plane"].size),
                    "either": int(state["flags"]["either"].size),
                    "campaignStarts": int(state["flags"]["campaignStarts"].size),
                },
                "falseFlags": false_flags(state, stable_by_sat.get(sat, []), el,
                                          by_sat.get(sat, [])),
            }
        out_arms[arm] = arm_out

    return out_arms, labels, stable, cache


def ids_corroboration(labels):
    """Registration section 3.7: does the labelled set still agree with its own
    upstream source? Corroboration only; no recall headline comes from here."""
    from truthset_growth import parse_ids_manoeuvres           # noqa: PLC0415
    out = {}
    for sat, code, name in (("sentinel-3a", "SEN3A", "s3aman.txt"),
                            ("sentinel-3b", "SEN3B", "s3bman.txt")):
        path = TRUTH_ROOT / "ids" / name
        if not path.exists():
            out[sat] = {"note": "the IDS manoeuvre history could not be read"}
            continue
        live = np.asarray(parse_ids_manoeuvres(path, code), dtype=np.float64)
        mine = sorted(lab["opStartMs"] for lab in labels if lab["sat"] == sat)
        if not mine:
            out[sat] = {"note": "no labels for this spacecraft"}
            continue
        last = max(mine)
        matched = 0
        for t in mine:
            if live.size and np.min(np.abs(live - t)) <= 2 * 3600 * 1000.0:
                matched += 1
        in_span = int(np.count_nonzero(live <= last))
        out[sat] = {
            "labelsInSet": len(mine),
            "labelsMatchedInLiveFile": matched,
            "toleranceHours": 2,
            "liveEventsWithinLabelSpan": in_span,
            "liveEventsAfterLabelSpan": int(live.size - in_span),
            "liveFileLastEventUtc": dt.datetime.fromtimestamp(
                float(live.max()) / 1000.0, dt.timezone.utc).isoformat(
                timespec="seconds") if live.size else None,
        }
    return out


def campaign_starts(flag_ms):
    if flag_ms.size == 0:
        return np.asarray([], dtype=np.int64)
    flags = np.sort(flag_ms)
    gaps = np.diff(flags) / DAY_MS > pp.CAMPAIGN_MAX_GAP_DAYS
    keep = np.concatenate(([True], gaps))
    return flags[keep]


def false_flags(state, stable_windows, el, labels):
    """Two counts, and neither is called a false-alarm rate.

    (1) flags inside MAD-LEO's labelled-quiet windows — an UPPER bound,
        because those windows are mined from a TLE archive rather than
        declared quiet by the operator, and the dataset itself flags some of
        them as suspected unreported manoeuvres;
    (2) flags anywhere inside the span the labels cover that are not matched
        to a label — reported as a count, not as a rate of error, because the
        completeness of the published manoeuvre history is not verified here.
    """
    either = state["flags"]["either"]
    inside = 0
    inside_suspect = 0
    windows_hit = 0
    window_days = 0.0
    for win in stable_windows:
        window_days += (win["endMs"] - win["startMs"]) / DAY_MS
        k = int(np.count_nonzero((either >= win["startMs"]) & (either <= win["endMs"])))
        inside += k
        if win["suspect"]:
            inside_suspect += k
        windows_hit += int(k > 0)
    out = {
        "stableWindows": len(stable_windows),
        "stableWindowDays": window_days,
        "flagsInStableWindows": inside,
        "flagsInStableWindowsFlaggedSuspect": inside_suspect,
        "stableWindowsWithAtLeastOneFlag": windows_hit,
        "flagsPerStableWindowDay": (inside / window_days) if window_days else None,
    }
    if labels:
        lo = min(lab["windowStartMs"] for lab in labels)
        hi = max(lab["windowEndMs"] for lab in labels)
        in_span = either[(either >= lo) & (either <= hi)]
        matched = np.zeros(in_span.size, dtype=bool)
        for lab in labels:
            matched |= ((in_span >= lab["windowStartMs"])
                        & (in_span <= lab["windowEndMs"]))
        years = (hi - lo) / DAY_MS / 365.25
        out.update({
            "labelSpanYears": years,
            "flagsInLabelSpan": int(in_span.size),
            "flagsUnmatched": int((~matched).sum()),
            "unmatchedPerYear": float((~matched).sum() / years) if years else None,
        })
    return out


def with_intervals(cells):
    def wrap(cell):
        out = dict(cell)
        out["recall"] = cell["k"] / cell["n"] if cell["n"] else None
        out["wilson95"] = wilson(cell["k"], cell["n"])
        return out
    out = {"overall": wrap(cells["overall"]),
           "campaignLevel": wrap(cells["campaignLevel"]),
           "placeboControl": wrap(cells["placebo"]),
           "byChannel": cells["byChannel"]}
    out["overall"]["notEvaluable"] = cells["overall"]["notEvaluable"]
    for key in ("byTier", "bySpacecraft", "byImpulses", "byDaBin", "byFloor"):
        out[key] = {k: wrap(v) for k, v in sorted(cells[key].items())}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path,
                    default=REPO / "docs" / "t16b-truthset-recall-20260922.json")
    args = ap.parse_args(argv)

    def say(msg):
        print(msg, flush=True)

    gate = detector_state_clean()
    say(f"detector files clean: {gate['clean']}")
    arms, labels, stable, cache = measure(say)

    out = {
        "registration": "docs/t16b-truthset-preregistration-20260922.md",
        "generatedUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "labelSet": {
            "name": "MAD-LEO mission-reported subset",
            "doi": "10.6084/m9.figshare.33446503.v1",
            "licence": "CC BY 4.0",
            "labels": len(labels),
            "stableWindows": len(stable),
            "spacecraft": sorted({lab["sat"] for lab in labels}),
        },
        "shippedSettings": {
            "pooledSigmaN": POOLED_SIGMA_N,
            "pooledSigmaTheta": POOLED_SIGMA_THETA,
            "k": pp.BURN_SIGMA_K,
            "baselineSamples": pp.BURN_BASELINE_SAMPLES,
            "daFloorKm": pp.DA_FLOOR_KM,
            "iFloorDeg": pp.I_FLOOR_DEG,
            "campaignMaxGapDays": pp.CAMPAIGN_MAX_GAP_DAYS,
        },
        "gates": {"B3_detectorUntouched": gate},
        "idsCorroboration": ids_corroboration(labels),
        "arms": arms,
    }
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    say(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
