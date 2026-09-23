#!/usr/bin/env python3
"""T27: the per-object-noise detector arm, measured as a registered change
candidate against the shipped low-orbit manoeuvre detector.

Registered in `docs/t27-per-object-noise-preregistration-20260923.md`, committed
alone before this file existed.

The change under test is exactly two arguments at one call site: the pooled
population scale parameters handed to `proximity_plane.detect_manoeuvres` are
replaced by the object's own, from `proximity_plane.object_sigma_contributions`
-- an estimator already in the production file. Nothing else moves.

The production detector is IMPORTED and never edited; gate G1 records that its
file, the trigger and the low-orbit alarm arm are unchanged, with blob hashes.

Two stages, because the five estimands live on two populations that may never be
differenced against each other (gate G3):

  labels     E1 recall, E2 the two false-flag counts, E5 the burn-size bins,
             on the eleven-spacecraft label set and its labelled-quiet windows
  catalogue  E3 the passive control and E4 the catalogue-wide price, on the
             archive's own low-orbit population, read from the existing
             element-set column cache

Usage:
  per_object_noise.py --stage all --out docs/t27-per-object-noise-20260923.json
"""
from __future__ import annotations

import argparse
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
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import proximity_plane as pp                                    # noqa: E402
import truthset_recall as tr                                    # noqa: E402
from pipeline.orbit_events import _jeffreys_interval            # noqa: E402

# ---- registered constants (prereg 1.1, 3, 4, 5) --------------------------
SEED = 20260923
DRAWS = 2000
BLOCK_DAYS = 90.0
GROWTH_BAR = 2.0                      # prereg 3 E4
NEVER_PAYLOAD_CONCERN = 0.10          # prereg 3 E3b secondary screen
PLACEBO_SHIFT_DAYS = -730.0           # prereg 5.2
PLACEBO_SHIFT_FALLBACK_DAYS = 730.0
SIGMA_MIN_SETS = 8                    # object_sigma_contributions' own bar

POOLED_SIGMA_N = tr.POOLED_SIGMA_N
POOLED_SIGMA_THETA = tr.POOLED_SIGMA_THETA
DAY_MS = tr.DAY_MS
# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
CACHE_ROOT = Path(os.environ.get("ORBIT_COLUMN_CACHE",
                                 "element-column-cache.not-configured"))
ARCHIVE = tr.ARCHIVE

# prereg 6 G2: the cells this instrument must reproduce before any new number
# is read. Published in docs/t16b-truthset-results-20260922.md sections 3.2/3.5.
G2_TARGETS = {
    "shipped": {"hits": 90, "labels": 1134, "quietFlags": 18, "unmatched": 321},
    "perObject": {"hits": 128, "labels": 1134, "quietFlags": 18, "unmatched": 520},
}

DETECTOR_FILES = ("tools/proximity_plane.py", "tools/trigger_alarm.py",
                  "tools/alarm_lane_leo.py", "pipeline/orbit_events.py")


# ==========================================================================
# The change, and its registered fallback ladder (prereg 1.2, 1.4)
# ==========================================================================
def per_object_sigmas(el):
    """prereg 1.2 + 1.4. Returns (sigma_n, sigma_theta, fallback flags).

    Rung 1 of the ladder is inside `detect_manoeuvres` itself and is not
    touched here: an object with fewer than BURN_BASELINE_SAMPLES + 3 element
    sets is returned no flags at all.
    """
    sigma_theta, sigma_n = pp.object_sigma_contributions(el)
    fb = {"sigmaN": False, "sigmaTheta": False,
          "sigmaNZero": False, "sigmaThetaZero": False}
    if not np.isfinite(sigma_n):
        sigma_n, fb["sigmaN"] = POOLED_SIGMA_N, True
    elif sigma_n == 0.0:
        fb["sigmaNZero"] = True                    # rung 3: NOT replaced
    if not np.isfinite(sigma_theta):
        sigma_theta, fb["sigmaTheta"] = POOLED_SIGMA_THETA, True
    elif sigma_theta == 0.0:
        fb["sigmaThetaZero"] = True
    return float(sigma_n), float(sigma_theta), fb


def shifted_window_sigmas(el, lo_ms, hi_ms):
    """prereg 5.2, placebo P2: sigma from a window displaced in time, falling
    back to the opposite displacement and then to the whole history."""
    for shift in (PLACEBO_SHIFT_DAYS, PLACEBO_SHIFT_FALLBACK_DAYS):
        a, b = lo_ms + shift * DAY_MS, hi_ms + shift * DAY_MS
        m = (el["epoch_ms"] >= a) & (el["epoch_ms"] <= b)
        if int(m.sum()) >= SIGMA_MIN_SETS:
            sub = {k: v[m] for k, v in el.items() if isinstance(v, np.ndarray)}
            sn, st, _ = per_object_sigmas(sub)
            return sn, st, ("shifted" if shift == PLACEBO_SHIFT_DAYS
                            else "shiftedOpposite")
    sn, st, _ = per_object_sigmas(el)
    return sn, st, "wholeHistory"


def derangement(keys, seed=SEED):
    """prereg 5.1, placebo P1: a permutation in which no element keeps its own
    position. Rejection sampling with a fixed seed; deterministic."""
    keys = list(keys)
    rng = np.random.default_rng(seed)
    if len(keys) < 2:
        return {k: k for k in keys}
    for _ in range(10000):
        order = rng.permutation(len(keys))
        if all(order[i] != i for i in range(len(keys))):
            return {keys[i]: keys[int(order[i])] for i in range(len(keys))}
    raise RuntimeError("no derangement found")


# ==========================================================================
# Intervals
# ==========================================================================
def wilson(k, n):
    return tr.wilson(k, n)


def jeffreys(k, n):
    if n <= 0:
        return None
    lo, hi = _jeffreys_interval(int(k), int(n))
    return [float(lo), float(hi)]


def rate_cell(flags, exposure_days):
    """A rate on an exposure, never a point estimate alone (Paper B section
    2.4: a zero point estimate is never reported as a zero bound)."""
    n = int(round(exposure_days))
    ji = jeffreys(flags, n)
    return {
        "flags": int(flags),
        "exposureObjectDays": n,
        "perObjectDay": (flags / n) if n else None,
        "perObjectYear": (flags / (n / 365.25)) if n else None,
        "jeffreys95PerObjectDay": ji,
        "jeffreys95PerObjectYear": ([ji[0] * 365.25, ji[1] * 365.25]
                                    if ji else None),
    }


def paired_increment(hits_a, hits_b, units, draws=DRAWS, seed=SEED):
    """The increment (arm B minus arm A) in percentage points, with a bootstrap
    over the given unit labels. `units` assigns every label to a resampling
    unit -- the eleven object clusters, or the 90-day time blocks."""
    hits_a = np.asarray(hits_a, dtype=np.float64)
    hits_b = np.asarray(hits_b, dtype=np.float64)
    units = np.asarray(units)
    keys = np.unique(units)
    parts = [(hits_a[units == k], hits_b[units == k]) for k in keys]
    point = 100.0 * (hits_b.mean() - hits_a.mean()) if hits_a.size else None
    rng = np.random.default_rng(seed)
    draws_out = np.empty(draws, dtype=np.float64)
    for d in range(draws):
        pick = rng.integers(0, len(parts), size=len(parts))
        aa = np.concatenate([parts[i][0] for i in pick])
        bb = np.concatenate([parts[i][1] for i in pick])
        draws_out[d] = 100.0 * (bb.mean() - aa.mean()) if aa.size else np.nan
    lo, hi = (float(np.nanpercentile(draws_out, 2.5)),
              float(np.nanpercentile(draws_out, 97.5)))
    return {
        "incrementPoints": point,
        "ci95": [lo, hi],
        "units": int(keys.size),
        "draws": draws,
        "seed": seed,
        # prereg 6 G4: an increment inside its own half-width could not have
        # been demonstrated by this design, whatever its sign.
        "minimumDetectablePoints": (hi - lo) / 2.0,
        "demonstrable": (point is not None
                         and abs(point) >= (hi - lo) / 2.0),
        "lowerBoundAboveZero": lo > 0.0,
    }


# ==========================================================================
# Gates
# ==========================================================================
def detector_untouched():
    """prereg 6 G1."""
    proc = subprocess.run(["git", "diff", "--stat", "--"] + list(DETECTOR_FILES),
                          cwd=str(REPO), capture_output=True)
    dirty = proc.stdout.decode().strip()
    hashes = {}
    for path in DETECTOR_FILES:
        out = subprocess.run(["git", "hash-object", path], cwd=str(REPO),
                             capture_output=True)
        hashes[path] = out.stdout.decode().strip()
    return {"clean": dirty == "", "diffstat": dirty, "blobHashes": hashes}


# ==========================================================================
# Stage: labels (E1, E2, E5)
# ==========================================================================
def flags_of(el, sigma_n, sigma_theta):
    det = pp.detect_manoeuvres(el, sigma_n, sigma_theta)
    ep = el["epoch_ms"]
    empty = np.asarray([], dtype=np.int64)
    intrack = ep[det["intrack"]] if det["intrack"].size else empty
    plane = ep[det["plane"]] if det["plane"].size else empty
    either = np.union1d(intrack, plane)
    return {"intrack": intrack, "plane": plane, "either": either,
            "campaignStarts": tr.campaign_starts(either)}


def run_labels(say):
    labels, stable = tr.load_labels()
    by_sat, stable_by_sat = {}, {}
    for lab in labels:
        by_sat.setdefault(lab["sat"], []).append(lab)
    for win in stable:
        stable_by_sat.setdefault(win["sat"], []).append(win)

    cache = {}
    for sat, norad in sorted(tr.SAT_NORAD.items()):
        el = tr.load_elements(norad)
        if el is None:
            say(f"  {sat}: NO ARCHIVE ROWS")
            continue
        cache[sat] = el
    say(f"  {len(cache)} spacecraft, {len(labels)} labels, "
        f"{len(stable)} labelled-quiet windows")

    # ---- the four arms' scale parameters --------------------------------
    sig = {"shipped": {}, "perObject": {}, "placeboDonor": {}, "placeboShift": {}}
    fallbacks = {"perObject": [], "placeboShift": []}
    for sat, el in cache.items():
        sig["shipped"][sat] = (POOLED_SIGMA_N, POOLED_SIGMA_THETA, "pooled")
        sn, st, fb = per_object_sigmas(el)
        sig["perObject"][sat] = (sn, st, "own")
        if fb["sigmaN"] or fb["sigmaTheta"]:
            fallbacks["perObject"].append({"sat": sat, **fb})
        labs = by_sat.get(sat, [])
        lo = min(l["windowStartMs"] for l in labs) if labs else el["epoch_ms"][0]
        hi = max(l["windowEndMs"] for l in labs) if labs else el["epoch_ms"][-1]
        sn2, st2, how = shifted_window_sigmas(el, lo, hi)
        sig["placeboShift"][sat] = (sn2, st2, how)
        if how != "shifted":
            fallbacks["placeboShift"].append({"sat": sat, "fallback": how})
    donor = derangement(sorted(sig["perObject"]))
    for sat, src in donor.items():
        sn, st, _ = sig["perObject"][src]
        sig["placeboDonor"][sat] = (sn, st, f"donor:{src}")

    # ---- flags, floors -------------------------------------------------
    state = {}
    for arm in sig:
        per_sat = {}
        for sat, el in cache.items():
            sn, st, how = sig[arm][sat]
            per_sat[sat] = {
                "sigmaN": sn, "sigmaTheta": st, "source": how,
                "floor": tr.detector_floor(el, sn, st),
                "flags": flags_of(el, sn, st),
            }
        state[arm] = per_sat

    shipped_floor = {sat: s["floor"]["minDetectableDaMetres"]
                     for sat, s in state["shipped"].items()}

    # ---- E1 / E2 / E5 ---------------------------------------------------
    out_arms = {}
    hit_vectors = {}
    label_index = []          # (sat, eventMs) in a fixed order, all arms share
    for sat in sorted(cache):
        for lab in by_sat.get(sat, []):
            label_index.append(lab)

    for arm, per_sat in state.items():
        cells = {"overall": {"k": 0, "n": 0},
                 "byDaBin": {}, "byOwnFloor": {}, "byShippedFloor": {},
                 "bySpacecraft": {}, "byChannel": {"intrack": 0, "plane": 0},
                 "campaignLevel": {"k": 0, "n": 0},
                 "placeboAssociation": {"k": 0, "n": 0}}
        hits = np.zeros(len(label_index), dtype=np.float64)
        for i, lab in enumerate(label_index):
            sat = lab["sat"]
            if sat not in per_sat:
                continue
            st_ = per_sat[sat]
            el = cache[sat]
            ep = el["epoch_ms"]
            lo, hi = lab["windowStartMs"], lab["windowEndMs"]
            hit_i = bool(np.any((st_["flags"]["intrack"] >= lo)
                                & (st_["flags"]["intrack"] <= hi)))
            hit_p = bool(np.any((st_["flags"]["plane"] >= lo)
                                & (st_["flags"]["plane"] <= hi)))
            hit = hit_i or hit_p
            hits[i] = float(hit)
            cells["overall"]["n"] += 1
            cells["overall"]["k"] += int(hit)
            cells["byChannel"]["intrack"] += int(hit_i)
            cells["byChannel"]["plane"] += int(hit_p)
            cells["campaignLevel"]["n"] += 1
            cells["campaignLevel"]["k"] += int(np.any(
                (st_["flags"]["campaignStarts"] >= lo)
                & (st_["flags"]["campaignStarts"] <= hi)))
            cell = cells["bySpacecraft"].setdefault(sat, {"k": 0, "n": 0})
            cell["n"] += 1
            cell["k"] += int(hit)
            da = tr.bracketed_da_metres(el, lo, hi)
            cell = cells["byDaBin"].setdefault(tr.bin_of(da, tr.DA_BINS),
                                               {"k": 0, "n": 0})
            cell["n"] += 1
            cell["k"] += int(hit)
            for key, bar in (("byOwnFloor", st_["floor"]["minDetectableDaMetres"]),
                             ("byShippedFloor", shipped_floor[sat])):
                side = ("unknown" if da is None
                        else "aboveFloor" if da >= bar else "belowFloor")
                cell = cells[key].setdefault(side, {"k": 0, "n": 0})
                cell["n"] += 1
                cell["k"] += int(hit)
            for shift in tr.PLACEBO_SHIFT_DAYS:
                plo, phi = lo + shift * DAY_MS, hi + shift * DAY_MS
                if plo < ep[0] or phi > ep[-1]:
                    continue
                if any(abs(plo - other["eventMs"]) < 2.0 * DAY_MS
                       for other in by_sat.get(sat, [])):
                    continue
                cells["placeboAssociation"]["n"] += 1
                cells["placeboAssociation"]["k"] += int(np.any(
                    (st_["flags"]["either"] >= plo)
                    & (st_["flags"]["either"] <= phi)))
        hit_vectors[arm] = hits

        false_flags = {}
        totals = {"flagsInStableWindows": 0, "suspect": 0, "windowsHit": 0,
                  "stableWindows": 0, "stableWindowDays": 0.0,
                  "flagsInLabelSpan": 0, "flagsUnmatched": 0}
        per_sc = {}
        for sat, st_ in per_sat.items():
            ff = tr.false_flags(st_, stable_by_sat.get(sat, []), cache[sat],
                                by_sat.get(sat, []))
            per_sc[sat] = {
                "sigmaN": st_["sigmaN"], "sigmaTheta": st_["sigmaTheta"],
                "source": st_["source"],
                "floorMetres": st_["floor"]["minDetectableDaMetres"],
                "thresholdSetBy": st_["floor"]["thresholdSetBy"],
                "flagCounts": {k: int(v.size) for k, v in st_["flags"].items()},
                "falseFlags": ff,
            }
            totals["flagsInStableWindows"] += ff["flagsInStableWindows"]
            totals["suspect"] += ff["flagsInStableWindowsFlaggedSuspect"]
            totals["windowsHit"] += ff["stableWindowsWithAtLeastOneFlag"]
            totals["stableWindows"] += ff["stableWindows"]
            totals["stableWindowDays"] += ff["stableWindowDays"]
            totals["flagsInLabelSpan"] += ff.get("flagsInLabelSpan", 0)
            totals["flagsUnmatched"] += ff.get("flagsUnmatched", 0)
        totals["flagsPerStableWindowDay"] = (
            totals["flagsInStableWindows"] / totals["stableWindowDays"]
            if totals["stableWindowDays"] else None)
        false_flags = {"totals": totals, "perSpacecraft": per_sc}

        out_arms[arm] = {"cells": wrap_cells(cells), "falseFlags": false_flags}

    # ---- G2, before any new number is read ------------------------------
    g2 = {}
    for arm, want in G2_TARGETS.items():
        got = {"hits": out_arms[arm]["cells"]["overall"]["k"],
               "labels": out_arms[arm]["cells"]["overall"]["n"],
               "quietFlags": out_arms[arm]["falseFlags"]["totals"]["flagsInStableWindows"],
               "unmatched": out_arms[arm]["falseFlags"]["totals"]["flagsUnmatched"]}
        g2[arm] = {"published": want, "measured": got, "match": got == want}
    g2["clean"] = all(v["match"] for v in g2.values() if isinstance(v, dict))
    say(f"  G2 reproduction: {g2['clean']}  " + json.dumps(
        {k: v["measured"] for k, v in g2.items() if isinstance(v, dict)}))

    # ---- increments -----------------------------------------------------
    sats = np.asarray([lab["sat"] for lab in label_index])
    ev = np.asarray([lab["eventMs"] for lab in label_index], dtype=np.float64)
    blocks = np.floor((ev - ev.min()) / (BLOCK_DAYS * DAY_MS)).astype(np.int64)
    increments = {}
    for arm in ("perObject", "placeboDonor", "placeboShift"):
        increments[arm] = {
            "vsShipped": {
                "objectCluster": paired_increment(hit_vectors["shipped"],
                                                  hit_vectors[arm], sats),
                "timeBlock90d": paired_increment(hit_vectors["shipped"],
                                                 hit_vectors[arm], blocks),
            },
        }
        ci_o = increments[arm]["vsShipped"]["objectCluster"]
        ci_b = increments[arm]["vsShipped"]["timeBlock90d"]
        armOfRecord = "objectCluster" if ci_o["ci95"][0] <= ci_b["ci95"][0] else "timeBlock90d"
        increments[arm]["armOfRecord"] = armOfRecord
        increments[arm]["decisionLowerBound"] = (
            increments[arm]["vsShipped"][armOfRecord]["ci95"][0])

    # ---- P1's registered reading (prereg 1.5, 5.1) ----------------------
    k_po = out_arms["perObject"]["cells"]["overall"]["k"]
    k_p1 = out_arms["placeboDonor"]["cells"]["overall"]["k"]
    p1 = {
        "perObjectHits": k_po, "donorHits": k_p1,
        "differenceLabels": k_p1 - k_po,
        "reproducesWithinOneLabel": abs(k_p1 - k_po) <= 1,
        "registeredReading": (
            "the gain is the 50 m floor becoming binding, NOT per-object "
            "adaptation; the word describing adaptation is withheld"
            if abs(k_p1 - k_po) <= 1 else
            "the per-object scale is doing work the donor scale cannot"),
    }

    # ---- E5 reversal clause ---------------------------------------------
    rev = []
    for name, cell in out_arms["perObject"]["cells"]["byDaBin"].items():
        base = out_arms["shipped"]["cells"]["byDaBin"].get(name)
        if not base or not cell["n"]:
            continue
        if cell["k"] < base["k"]:
            mask = np.asarray([tr.bin_of(tr.bracketed_da_metres(
                cache[l["sat"]], l["windowStartMs"], l["windowEndMs"]),
                tr.DA_BINS) == name for l in label_index])
            inc = paired_increment(hit_vectors["shipped"][mask],
                                   hit_vectors["perObject"][mask], sats[mask])
            rev.append({"bin": name, "shipped": base["k"],
                        "perObject": cell["k"], "increment": inc,
                        "excludesZero": inc["ci95"][1] < 0.0})
    reversal = {"binsWorse": rev,
                "fires": any(r["excludesZero"] for r in rev)}

    return {
        "labelSet": {"labels": len(labels), "stableWindows": len(stable),
                     "spacecraft": sorted(cache)},
        "gates": {"G2_reproduction": g2},
        "arms": out_arms,
        "increments": increments,
        "placeboP1": p1,
        "reversalClause": reversal,
        "fallbacks": fallbacks,
    }


def wrap_cells(cells):
    def w(c):
        o = dict(c)
        o["recall"] = c["k"] / c["n"] if c["n"] else None
        o["wilson95"] = wilson(c["k"], c["n"])
        return o
    out = {"overall": w(cells["overall"]),
           "campaignLevel": w(cells["campaignLevel"]),
           "placeboAssociation": w(cells["placeboAssociation"]),
           "byChannel": cells["byChannel"]}
    for key in ("byDaBin", "byOwnFloor", "byShippedFloor", "bySpacecraft"):
        out[key] = {k: w(v) for k, v in sorted(cells[key].items())}
    return out


# ==========================================================================
# Stage: catalogue (E3, E4)
# ==========================================================================
def all_object_types(db, norads):
    """One query, not 68,749. Reads `object_type` and nothing else."""
    rows = db.execute("SELECT norad, object_type FROM object").fetchall()
    have = {int(r[0]): r[1] for r in rows}
    return {int(n): have.get(int(n)) for n in norads}


def campaign_count(flag_ms):
    if flag_ms.size == 0:
        return 0
    f = np.sort(flag_ms)
    return 1 + int((np.diff(f) / DAY_MS > pp.CAMPAIGN_MAX_GAP_DAYS).sum())


def run_catalogue(say, regime="LEO", limit=None):
    cache = pp.Cache(CACHE_ROOT).open()
    norads = [int(x) for x in cache.index_norad]
    if limit:
        norads = norads[:limit]
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    types = all_object_types(db, norads)
    db.close()
    say(f"  cache {CACHE_ROOT}: {len(norads):,} objects")

    arms = ("shipped", "perObject")
    summary = {a: {} for a in arms}
    sigma_rows = []
    theta_rows = []
    plane_at_floor = {a: 0 for a in arms}
    fallback = {"sigmaNPooled": 0, "sigmaThetaPooled": 0,
                "sigmaNZero": 0, "sigmaThetaZero": 0,
                "sigmaNAbovePooled": 0, "sigmaNBelowPooled": 0}
    done = 0
    for nd in norads:
        el = cache.elements(nd)
        if el is None:
            continue
        regs = {pp.REGIME_NAME[int(c)] for c in np.unique(el["regime"])}
        if regime not in regs:
            continue
        ep = el["epoch_ms"]
        span = float((ep[-1] - ep[0]) / DAY_MS) if ep.size > 1 else 0.0
        sn_po, st_po, fb = per_object_sigmas(el)
        theta_rows.append(st_po)
        fallback["sigmaNPooled"] += int(fb["sigmaN"])
        fallback["sigmaThetaPooled"] += int(fb["sigmaTheta"])
        fallback["sigmaNZero"] += int(fb["sigmaNZero"])
        fallback["sigmaThetaZero"] += int(fb["sigmaThetaZero"])
        if not fb["sigmaN"]:
            if sn_po > POOLED_SIGMA_N:
                fallback["sigmaNAbovePooled"] += 1
            else:
                fallback["sigmaNBelowPooled"] += 1
            sigma_rows.append(sn_po)
        for arm, (sn, st) in (("shipped", (POOLED_SIGMA_N, POOLED_SIGMA_THETA)),
                              ("perObject", (sn_po, st_po))):
            if pp.BURN_SIGMA_K * st <= pp.I_FLOOR_DEG:
                plane_at_floor[arm] += 1
            det = pp.detect_manoeuvres(el, sn, st)
            it = ep[det["intrack"]] if det["intrack"].size else np.asarray([], dtype=np.int64)
            pl = ep[det["plane"]] if det["plane"].size else np.asarray([], dtype=np.int64)
            summary[arm][nd] = {
                "elementSets": int(ep.size), "spanDays": span,
                "nIntrack": int(it.size), "nPlane": int(pl.size),
                "campaignsIntrack": campaign_count(it),
                "campaignsEither": campaign_count(np.union1d(it, pl)),
            }
        done += 1
        if done % 5000 == 0:
            say(f"    ... {done:,} low-orbit objects")
    say(f"  {done:,} low-orbit objects scored under both arms")

    labels = {nd: pp.class_label(types.get(nd)) for nd in summary["shipped"]}

    def admitted(nd, arm):
        s = summary[arm][nd]
        return (s["elementSets"] >= pp.CONTROL_MIN_ELEMENT_SETS
                and s["spanDays"] >= pp.CONTROL_MIN_SPAN_DAYS)

    # ---- E3a: the physically defined passive class ----------------------
    e3a, e3c, e4 = {}, {}, {}
    for cls in ("catalogue_passive", "payload"):
        for arm in arms:
            flags = exposure = 0.0
            objs = withflag = camp_it = 0
            n_it = n_pl = 0
            for nd, lbl in labels.items():
                if lbl != cls or not admitted(nd, "shipped"):
                    continue
                s = summary[arm][nd]
                objs += 1
                exposure += s["spanDays"]
                flags += s["nIntrack"] + s["nPlane"]
                n_it += s["nIntrack"]
                n_pl += s["nPlane"]
                camp_it += s["campaignsIntrack"]
                withflag += int(bool(s["nIntrack"] or s["nPlane"]))
            cell = rate_cell(flags, exposure)
            cell.update({"objects": objs, "objectsWithAnyFlag": withflag,
                         "intrackFlags": n_it, "planeFlags": n_pl,
                         "objectsWithAnyFlagFraction": (withflag / objs) if objs else None,
                         "campaignStartsIntrack": camp_it,
                         "alertsPerObjectYear": (camp_it / (exposure / 365.25))
                         if exposure else None})
            e3a.setdefault(cls, {})[arm] = cell

    e3a["note"] = ("catalogue_passive is DEBRIS and ROCKET BODY -- an UPPER "
                   "bound on the false-alarm rate, because some spent stages "
                   "do perform disposal burns. Admission is frozen at the "
                   "shipped arm's, so both arms are scored on one population.")
    for arm in arms:
        p = e3a["catalogue_passive"][arm]
        y = e3a["payload"][arm]
        e3c[arm] = {
            "passiveAlertsPerObjectYear": p["alertsPerObjectYear"],
            "payloadAlertsPerObjectYear": y["alertsPerObjectYear"],
            "ratio": (p["alertsPerObjectYear"] / y["alertsPerObjectYear"])
            if y["alertsPerObjectYear"] else None,
        }
    # the registered bound-versus-bound test
    sp = e3a["catalogue_passive"]["shipped"]
    po = e3a["catalogue_passive"]["perObject"]
    e3a["verdict"] = {
        "shippedJeffreysUpperPerObjectDay": sp["jeffreys95PerObjectDay"][1],
        "perObjectJeffreysLowerPerObjectDay": po["jeffreys95PerObjectDay"][0],
        "pointRatio": (po["perObjectDay"] / sp["perObjectDay"])
        if sp["perObjectDay"] else None,
        "fails": po["jeffreys95PerObjectDay"][0] > sp["jeffreys95PerObjectDay"][1],
        "underpowered": e3a["catalogue_passive"]["shipped"]["objects"] < 200,
    }
    e3c["fails"] = (e3c["perObject"]["ratio"] is not None
                    and e3c["shipped"]["ratio"] is not None
                    and e3c["perObject"]["ratio"] > e3c["shipped"]["ratio"])
    e3c["note"] = ("the live low-orbit alarm arm fails its own passive control "
                   "at 0.797 today; this ratio may not grow")

    # ---- E3b: the frozen never-manoeuvred class -------------------------
    never = [nd for nd in summary["shipped"]
             if not summary["shipped"][nd]["nIntrack"]
             and not summary["shipped"][nd]["nPlane"]
             and admitted(nd, "shipped")]
    never_payload = [nd for nd in never if labels.get(nd) == "payload"]
    e3b = {"frozenClassObjects": len(never),
           "frozenClassPayloadObjects": len(never_payload),
           "definitionIsCircular": True,
           "circularityNote": (
               "this class is DEFINED by the shipped detector raising no flag "
               "on it, so the shipped arm's rate is zero by construction and "
               "any per-object flag makes the change look worse for a reason "
               "that is not about the change. Reported, never gating."),
           "scopeLimit": (
               "T8b's published zero events over 18,792,698 object-days is an "
               "APPROACH-event rate from its whole analyze stage, not a flag "
               "rate. It is carried as context and is NOT re-scored here.")}
    for arm in arms:
        flags = exposure = 0.0
        withflag = n_it = n_pl = 0
        pflags = pexp = 0.0
        pwith = p_it = p_pl = 0
        for nd in never:
            s = summary[arm][nd]
            exposure += s["spanDays"]
            flags += s["nIntrack"] + s["nPlane"]
            n_it += s["nIntrack"]
            n_pl += s["nPlane"]
            withflag += int(bool(s["nIntrack"] or s["nPlane"]))
            if labels.get(nd) == "payload":
                pexp += s["spanDays"]
                pflags += s["nIntrack"] + s["nPlane"]
                p_it += s["nIntrack"]
                p_pl += s["nPlane"]
                pwith += int(bool(s["nIntrack"] or s["nPlane"]))
        e3b[arm] = {"wholeClass": {**rate_cell(flags, exposure),
                                   "objectsWithAnyFlag": withflag,
                                   "intrackFlags": n_it, "planeFlags": n_pl},
                    "payloadSubset": {**rate_cell(pflags, pexp),
                                      "objectsWithAnyFlag": pwith,
                                      "intrackFlags": p_it, "planeFlags": p_pl}}
    frac = (e3b["perObject"]["payloadSubset"]["objectsWithAnyFlag"]
            / len(never_payload)) if never_payload else None
    e3b["secondaryScreen"] = {
        "fractionOfFrozenPayloadObjectsNowFlagged": frac,
        "bar": NEVER_PAYLOAD_CONCERN,
        "namedConcern": (frac is not None and frac > NEVER_PAYLOAD_CONCERN)}

    # ---- E4: the catalogue-wide price -----------------------------------
    for arm in arms:
        flags = intrack = plane = camp_it = camp_ei = withflag = 0
        exposure = 0.0
        for nd, s in summary[arm].items():
            exposure += s["spanDays"]
            intrack += s["nIntrack"]
            plane += s["nPlane"]
            camp_it += s["campaignsIntrack"]
            camp_ei += s["campaignsEither"]
            withflag += int(bool(s["nIntrack"] or s["nPlane"]))
        flags = intrack + plane
        years = exposure / 365.25
        e4[arm] = {
            "objects": len(summary[arm]),
            "exposureObjectDays": int(round(exposure)),
            "exposureObjectYears": years,
            "intrackFlags": intrack, "planeFlags": plane, "flags": flags,
            "flagsPerObjectYear": flags / years if years else None,
            "campaignStartsIntrack": camp_it,
            "campaignStartsEither": camp_ei,
            "objectsWithAnyFlag": withflag,
        }
    e4["growth"] = {
        "flagsPerObjectYear": (e4["perObject"]["flagsPerObjectYear"]
                               / e4["shipped"]["flagsPerObjectYear"])
        if e4["shipped"]["flagsPerObjectYear"] else None,
        "campaignStartsIntrack": (e4["perObject"]["campaignStartsIntrack"]
                                  / e4["shipped"]["campaignStartsIntrack"])
        if e4["shipped"]["campaignStartsIntrack"] else None,
        "extraFlags": e4["perObject"]["flags"] - e4["shipped"]["flags"],
        "extraCampaignStarts": (e4["perObject"]["campaignStartsIntrack"]
                                - e4["shipped"]["campaignStartsIntrack"]),
        "bar": GROWTH_BAR,
    }
    e4["growth"]["extraFlagsPerYearAcrossCatalogue"] = (
        e4["growth"]["extraFlags"] / e4["shipped"]["exposureObjectYears"]
        * e4["shipped"]["objects"]) if e4["shipped"]["exposureObjectYears"] else None
    e4["growth"]["fails"] = any(
        (e4["growth"][k] is not None and e4["growth"][k] > GROWTH_BAR)
        for k in ("flagsPerObjectYear", "campaignStartsIntrack"))
    e4["sigmaDistribution"] = {
        "objectsWithOwnSigmaAbovePooled": fallback["sigmaNAbovePooled"],
        "objectsWithOwnSigmaBelowPooled": fallback["sigmaNBelowPooled"],
        "medianOwnSigmaN": float(np.median(sigma_rows)) if sigma_rows else None,
        "p95OwnSigmaN": float(np.percentile(sigma_rows, 95)) if sigma_rows else None,
        "pooledSigmaN": POOLED_SIGMA_N,
        "medianOwnSigmaTheta": float(np.median(theta_rows)) if theta_rows else None,
        "p95OwnSigmaTheta": float(np.percentile(theta_rows, 95)) if theta_rows else None,
        "pooledSigmaTheta": POOLED_SIGMA_THETA,
        # POST-REGISTRATION DIAGNOSTIC, labelled as such: how many objects have
        # their plane bar pinned to the 0.01 degree resolution floor rather than
        # to five of their own scales. T8b's plane channel sat at 3.5 degrees and
        # was effectively off; this says how far the change reopens it.
        "objectsWithPlaneBarAtTheResolutionFloor": plane_at_floor,
    }
    e4["fallbacks"] = fallback
    return {"regime": regime, "E3a": e3a, "E3b": e3b, "E3c": e3c, "E4": e4}


def run_sigma_by_class(say, regime="LEO"):
    """POST-REGISTRATION DIAGNOSTIC, labelled as such.

    E3a failed and E4's channel split showed the in-track passive count rising
    while the payload count fell. Neither direction is explicable without
    knowing how the per-object scale itself is distributed across the two
    classes, so it is measured here rather than asserted. No screen, threshold
    or decision rule depends on this pass.
    """
    cache = pp.Cache(CACHE_ROOT).open()
    norads = [int(x) for x in cache.index_norad]
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    types = all_object_types(db, norads)
    db.close()
    rows = {"catalogue_passive": [], "payload": []}
    for nd in norads:
        lbl = pp.class_label(types.get(nd))
        if lbl not in rows:
            continue
        el = cache.elements(nd)
        if el is None:
            continue
        if regime not in {pp.REGIME_NAME[int(c)] for c in np.unique(el["regime"])}:
            continue
        ep = el["epoch_ms"]
        if (ep.size < pp.CONTROL_MIN_ELEMENT_SETS
                or (ep[-1] - ep[0]) / DAY_MS < pp.CONTROL_MIN_SPAN_DAYS):
            continue
        st, sn = pp.object_sigma_contributions(el)
        if np.isfinite(sn):
            rows[lbl].append(float(sn))
    out = {}
    for lbl, vals in rows.items():
        v = np.asarray(vals, dtype=np.float64)
        out[lbl] = {
            "objects": int(v.size),
            "medianOwnSigmaN": float(np.median(v)) if v.size else None,
            "p25": float(np.percentile(v, 25)) if v.size else None,
            "p75": float(np.percentile(v, 75)) if v.size else None,
            "fractionBelowPooled": float((v < POOLED_SIGMA_N).mean()) if v.size else None,
            "medianAsMultipleOfPooled": (float(np.median(v)) / POOLED_SIGMA_N)
            if v.size else None,
        }
        say(f"  {lbl}: {out[lbl]['objects']:,} objects, median own scale "
            f"{out[lbl]['medianAsMultipleOfPooled']:.3f} x pooled, "
            f"{100 * out[lbl]['fractionBelowPooled']:.1f}% below pooled")
    out["pooledSigmaN"] = POOLED_SIGMA_N
    out["note"] = ("post-registration diagnostic; admission is the control's "
                   "own, 200 element sets and 365 days")
    return out


# ==========================================================================
def decide(labels_out, cat_out):
    """prereg 4. A clause that cannot be evaluated is a failing clause."""
    failing = []
    inc = labels_out["increments"]["perObject"]
    rec = inc["vsShipped"][inc["armOfRecord"]]
    if not rec["lowerBoundAboveZero"]:
        failing.append("E1 (increment lower bound not above zero)")
    elif not rec["demonstrable"]:
        failing.append("E1 (increment inside its own minimum detectable effect)")
    if cat_out is None:
        failing.append("E3a (not evaluated)")
        failing.append("E3c (not evaluated)")
        failing.append("E4 (not evaluated)")
    else:
        if cat_out["E3a"]["verdict"]["underpowered"]:
            failing.append("E3a (underpowered: fewer than 200 passive objects)")
        elif cat_out["E3a"]["verdict"]["fails"]:
            failing.append("E3a (passive rate demonstrably worse)")
        if cat_out["E3c"]["fails"]:
            failing.append("E3c (alarm lane passive/payload ratio grows)")
        if cat_out["E4"]["growth"]["fails"]:
            failing.append("E4 (catalogue-wide growth beyond the registered factor)")
    if labels_out["reversalClause"]["fires"]:
        failing.append("E5 (a burn-size bin reverses with an interval excluding zero)")
    return {"verdict": "SHIP-CANDIDATE" if not failing else "NOT SHIPPED",
            "failingClauses": failing}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=("labels", "catalogue", "sigma", "all"),
                    default="all")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=Path,
                    default=REPO / "docs" / "t27-per-object-noise-20260923.json")
    args = ap.parse_args(argv)

    def say(msg):
        print(msg, flush=True)

    gate = detector_untouched()
    say(f"G1 detector untouched: {gate['clean']}")
    if not gate["clean"]:
        say("G1 FIRED -- the track is void")
        say(gate["diffstat"])
        return 2

    out = {
        "registration": "docs/t27-per-object-noise-preregistration-20260923.md",
        "generatedUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED, "bootstrapDraws": DRAWS, "blockDays": BLOCK_DAYS,
        "change": {
            "callSite": "proximity_plane.detect_manoeuvres(el, sigma_n, sigma_theta)",
            "shipped": {"sigmaN": POOLED_SIGMA_N, "sigmaTheta": POOLED_SIGMA_THETA},
            "underTest": "proximity_plane.object_sigma_contributions(el)",
            "unchanged": {"k": pp.BURN_SIGMA_K,
                          "baselineSamples": pp.BURN_BASELINE_SAMPLES,
                          "daFloorKm": pp.DA_FLOOR_KM,
                          "iFloorDeg": pp.I_FLOOR_DEG,
                          "campaignMaxGapDays": pp.CAMPAIGN_MAX_GAP_DAYS},
        },
        "gates": {"G1_detectorUntouched": gate},
    }
    labels_out = cat_out = None
    if args.stage in ("labels", "all"):
        say("stage: labels (E1, E2, E5)")
        labels_out = run_labels(say)
        out["labels"] = labels_out
        out["gates"]["G2_reproduction"] = labels_out["gates"]["G2_reproduction"]
    if args.stage in ("catalogue", "all"):
        say("stage: catalogue (E3, E4)")
        cat_out = run_catalogue(say, limit=args.limit)
        out["catalogue"] = cat_out
    if args.stage in ("sigma", "all"):
        say("stage: the per-object scale by class (post-registration diagnostic)")
        out["sigmaByClass"] = run_sigma_by_class(say)
    if labels_out is not None:
        out["decision"] = decide(labels_out, cat_out)
        say("decision: " + json.dumps(out["decision"]))
    args.out.write_text(json.dumps(out, indent=2, default=float) + "\n")
    say(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
