#!/usr/bin/env python3
"""M0, M1, M2 -- the kinematic inputs the reach layer owes before it may
compute a reachable set.

Registration: `docs/kinematic-inputs-preregistration-20260922.md`, committed
alone at 3f8bcab before this file existed. Section references below (reg N)
point at that document; a choice the registration left open is marked IMPL and
justified in place, and a departure from it is marked DEVIATION and reported
in the results document as well.

  M0  class-conditional next-burn size quantiles, from committed ledgers only
  M1  the forward-propagation error at GEO beyond +30 d, measured by T8d's own
      `validate_propagator` with its `check_days` varied and nothing else
  M2  per-object LEO along-track phase-error growth against sigma_n and two
      drag proxies

Nothing here computes a propellant, mass or consumables figure; nothing here
reads a registry or country code; nothing here emits a distance between two
objects. Tests assert each of those three over the files this module writes.

Stages
------
  m0 | m1 | m2 | all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO), str(_REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_geo as pg            # noqa: E402  T8a's instrument
import proximity_plane as pp          # noqa: E402  T8b's instrument

REGISTRATION = "docs/kinematic-inputs-preregistration-20260922.md"
DOCS = _REPO / "docs"
# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
ARCHIVE = Path(os.environ.get("ORBIT_ARCHIVE_DB",
                              "element-archive.not-configured.sqlite3"))
T8D_WORK = Path(os.environ.get("ORBIT_TRIGGER_WORK",
                               "trigger-alarm-work.not-configured"))
T8B_WORK = Path(os.environ.get("ORBIT_PLANE_WORK",
                               "plane-detect-work.not-configured"))

DAY_MS = pg.DAY_MS
SEED = 20260922                                  # reg 4.2

# reg 2.3 -- the committed subset's own rule, as numbers
SUBSET_ROWS = 5904
SUBSET_POSITIVES = 904
SUBSET_SAMPLED_OTHERS = 5000
FULL_TABLE_ROWS = 226422
FULL_TABLE_SHA256 = ("f4c3ca9b96fbb8fda1c1d719699ee4f9f24c192cb7c4f3dc89fcc"
                     "8c7ff495c67")
OTHERS_WEIGHT = (FULL_TABLE_ROWS - SUBSET_POSITIVES) / SUBSET_SAMPLED_OTHERS

# reg 2.4 / 4.2 -- the power rule
MIN_N = 20

# reg 3.1 -- the published +30 d figures this measurement must reproduce
T8D_PROP_N = 49318
T8D_PROP_P50 = 0.408

# reg 3.3
HORIZONS_PRIMARY = (30.0, 60.0, 90.0, 180.0)
HORIZONS_FINE = (5.0, 10.0, 15.0, 20.0, 45.0, 120.0)

# reg 3.4 -- the thresholds M1 is read against, each a screen and not a law
COLOCATION_DEG = pg.X_PRIMARY_DEG                # 0.1
GATE_W_DEG = 2.0

# reg 4 -- LEO
M2_HORIZONS = (30.0, 60.0, 90.0, 180.0)
GAMMA_DEG = pp.GAMMA_DEG                         # 5.0
GAMMA_TIGHT = pp.GAMMA_SENSITIVITY[1]            # 0.2085
MAX_GAP_DAYS = pp.MAX_GAP_DAYS                   # 5.0
UNWRAP_SUSPECT_DEG = 90.0                        # reg 4.1
M2_STRATUM_TARGET = 400                          # reg 4.2
M2_MIN_ELEMENT_SETS = pp.CONTROL_MIN_ELEMENT_SETS
M2_MIN_SPAN_DAYS = pp.CONTROL_MIN_SPAN_DAYS

QUANTILES = (5, 25, 50, 75, 95)


# ==========================================================================
# Small shared arithmetic
# ==========================================================================
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def weighted_quantile(values, weights, q):
    """reg 2.3: the smallest value whose cumulative weight reaches q*W.

    With every weight equal this is the classical "lower" empirical quantile;
    it is used for the weighted and unweighted cases alike so that no class's
    quantiles are computed by a different rule from another's.
    """
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if v.size == 0:
        return float("nan")
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    cum = np.cumsum(w)
    target = (q / 100.0) * cum[-1]
    k = int(np.searchsorted(cum, target, side="left"))
    return float(v[min(k, v.size - 1)])


def quantile_block(values, weights=None, unit=None, note=None):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=np.float64)
    if weights is None:
        w = np.ones(v.size, dtype=np.float64)
    else:
        w = np.asarray(weights, dtype=np.float64)
        keep = np.isfinite(np.asarray(values, dtype=np.float64))
        w = w[keep]
    out = {"n": int(v.size), "unit": unit}
    if v.size:
        for q in QUANTILES:
            out[f"p{q}"] = weighted_quantile(v, w, q)
        out["min"] = float(v.min())
        out["max"] = float(v.max())
        out["weightedN"] = float(w.sum())
    out["underpowered"] = bool(v.size < MIN_N)
    if out["underpowered"]:
        out["power"] = f"UNDERPOWERED (n = {int(v.size)} < {MIN_N})"
    if note:
        out["note"] = note
    return out


def geo_drift_to_mps(drift_deg_per_day):
    """derived: a tangential impulse changes the mean-longitude drift rate by
    DRIFT_PER_M_S = 0.3522 deg/day per m/s (proximity_geo, from da = 2 dv/n
    and dlam_dot = -(3/2)(omega_E/a) da). Arithmetic on elements; not a fuel
    figure."""
    return abs(float(drift_deg_per_day)) / pg.DRIFT_PER_M_S


def leo_da_to_mps(da_km, a_km):
    """derived: da = 2 dv / n, with n the mean motion in rad/s at a_km."""
    n_rad_s = pp.mean_motion_rev_day(a_km) * 2.0 * math.pi / 86400.0
    return abs(float(da_km)) * 1000.0 * n_rad_s / 2.0


def read_jsonl(path, drop_provenance=True):
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if drop_provenance and (rec.get("record") == "provenance"
                                    or "_provenance" in rec):
                continue
            rows.append(rec)
    return rows


# ==========================================================================
# M0 -- class-conditional next-burn size (reg 2)
# ==========================================================================
def m0(out):
    t0 = time.time()
    res = {"registration": REGISTRATION,
           "estimand": ("the size of ONE burn of a class, from the committed "
                        "ledgers. NOT remaining propellant; no propellant, "
                        "mass or consumables figure is read or computed."),
           "classes": {}}

    # --- C1 relocation stop, GEO -----------------------------------------
    geo = read_jsonl(DOCS / "proximity-events-20260922.jsonl")
    prim = [e for e in geo if e.get("approacherClass") == "active"
            and e.get("attribution") == "resolved"]
    drift = [abs(e["transferDriftDegPerDay"]) for e in prim
             if e.get("transferDriftDegPerDay") is not None]
    res["classes"]["C1_relocation_stop_geo"] = {
        "source": "docs/proximity-events-20260922.jsonl",
        "selection": "approacherClass == active and attribution == resolved",
        "native": quantile_block(drift, unit="deg/day of drift the stop burn nulls"),
        "derivedMps": quantile_block([geo_drift_to_mps(d) for d in drift],
                                     unit="m/s (derived, 0.3522 deg/day per m/s)"),
        "detectionFloorNative": 0.010,
        "floorNote": ("the published 0.010 deg/day drift-change floor truncates "
                      "this distribution from below; p5 is as much the floor as "
                      "the objects"),
    }

    # --- C2 any confirmed drift change, GEO, weighted (reg 2.3) ----------
    trig = read_jsonl(DOCS / "trigger-alarm-triggers-20260922.jsonl")
    vals, wts, clusters = [], [], []
    for r in trig:
        m = r.get("init_drift_change_mag")
        if m is None:
            continue
        positive = bool(r.get("o1Positive")) or bool(r.get("o2Positive"))
        vals.append(abs(float(m)))
        wts.append(1.0 if positive else OTHERS_WEIGHT)
        clusters.append(r.get("cluster"))
    vals = np.asarray(vals)
    wts = np.asarray(wts)
    clusters = np.asarray([-1 if c is None else int(c) for c in clusters])

    res["classes"]["C2_any_drift_change_geo"] = {
        "source": ("docs/trigger-alarm-triggers-20260922.jsonl "
                   f"(committed {SUBSET_ROWS}-row subset; full table "
                   f"{FULL_TABLE_ROWS} rows)"),
        "selection": "every row, weighted per registration 2.3",
        "weighting": {"positiveWeight": 1.0, "otherWeight": OTHERS_WEIGHT,
                      "why": ("the subset is enriched: every positive plus a "
                              "uniform sample of the rest, so unweighted "
                              "quantiles would describe the sample, not the "
                              "226,422-row population")},
        "native": quantile_block(vals, wts, unit="deg/day"),
        "derivedMps": quantile_block([geo_drift_to_mps(v) for v in vals], wts,
                                     unit="m/s (derived)"),
        "detectionFloorNative": 0.010,
        "recall": ("UNMEASURED: 33% of T8a's events had no visible initiating "
                   "flag; this is a distribution over the burns the detector "
                   "saw and nothing here estimates the ones it did not"),
    }
    for c in (1, 0):
        sel = clusters == c
        res["classes"][f"C2{'a' if c == 1 else 'b'}_drift_change_cluster{c}"] = {
            "source": "same, cluster == %d (T8d taxonomy, primary-arm resolvable rows only)" % c,
            "native": quantile_block(vals[sel], wts[sel], unit="deg/day"),
            "derivedMps": quantile_block([geo_drift_to_mps(v) for v in vals[sel]],
                                         wts[sel], unit="m/s (derived)"),
        }

    # cross-check against the full table, gated on its sha (reg 2.3)
    full = T8D_WORK / "trigger-alarm-triggers-20260922-FULL.jsonl"
    check = {"path": str(full), "performed": False}
    if full.exists():
        sha = sha256_file(full)
        check["sha256"] = sha
        check["shaMatchesCommitted"] = bool(sha == FULL_TABLE_SHA256)
        if check["shaMatchesCommitted"]:
            fv = []
            with open(full) as fh:
                for line in fh:
                    r = json.loads(line)
                    if r.get("record") == "provenance":
                        continue
                    m = r.get("init_drift_change_mag")
                    if m is not None:
                        fv.append(abs(float(m)))
            check["performed"] = True
            check["fullTable"] = quantile_block(fv, unit="deg/day")
        else:
            check["note"] = ("sha256 disagrees with the committed "
                             "fullTableSha256; cross-check NOT performed")
    else:
        check["note"] = "full table absent; cross-check NOT performed"
    res["classes"]["C2_any_drift_change_geo"]["fullTableCrossCheck"] = check

    # --- C3 north-south keeping ------------------------------------------
    ns = [r for r in read_jsonl(DOCS / "stationkeeping-ns-20260922.jsonl")
          if r.get("informative")]
    dv = [r["dvExactMinimumMps"] for r in ns
          if r.get("dvExactMinimumMps") is not None]
    res["classes"]["C3_north_south_keeping_geo"] = {
        "source": "docs/stationkeeping-ns-20260922.jsonl, informative rows",
        "population": ("data/propulsion-catalog-v1.json, commercial-civil only "
                       "-- inherited from T10b, not widened here"),
        "objects": len({r["norad"] for r in ns}),
        "native": quantile_block(dv, unit="m/s (exact-minimum impulse)"),
    }
    by_bus = {}
    for r in ns:
        if r.get("dvExactMinimumMps") is None:
            continue
        by_bus.setdefault(r.get("busFamily") or "unlabelled", []).append(
            r["dvExactMinimumMps"])
    res["classes"]["C3a_north_south_by_bus"] = {
        "source": "same, grouped by busFamily",
        "buses": {b: quantile_block(v, unit="m/s") for b, v in sorted(by_bus.items())},
    }

    # --- C4 east-west keeping --------------------------------------------
    ew = read_jsonl(DOCS / "stationkeeping-ew-20260922.jsonl")
    per_burn = [r["detectedDvMps"] / r["detectedEvents"] for r in ew
                if r.get("detectedEvents") and r.get("detectedDvMps") is not None]
    theory = [r["theoryDvPerCycleMps"] for r in ew
              if r.get("theoryDvPerCycleMps") is not None]
    res["classes"]["C4_east_west_keeping_geo"] = {
        "source": "docs/stationkeeping-ew-20260922.jsonl",
        "selection": "segments with detectedEvents > 0",
        "detectedPerBurn": quantile_block(per_burn, unit="m/s per detected burn"),
        "derivedPerCycle": quantile_block(theory, unit="m/s per cycle (T10c derivation)"),
        "recall": ("1.81% median detected recall (T10c): the detected "
                   "distribution is over the LARGEST burns only and is "
                   "detectability-selected"),
    }

    # --- C5 transfer legs -------------------------------------------------
    tr = read_jsonl(DOCS / "transfer-loss-20260922.jsonl")
    prim_int, all_int = [], []
    for ph in tr:
        for iv in ph.get("intervals") or []:
            v = iv.get("exactMinimumImpulseMps")
            if v is None:
                continue
            all_int.append(v)
            if ph.get("informative"):
                prim_int.append(v)
    res["classes"]["C5_transfer_legs"] = {
        "source": "docs/transfer-loss-20260922.jsonl, intervals[]",
        "population": ("data/propulsion-catalog-v1.json, commercial-civil only "
                       "-- inherited from T10a/T10d, not widened here"),
        "phases": {"all": len(tr), "informative": sum(1 for p in tr if p.get("informative"))},
        "primaryInformative": quantile_block(prim_int, unit="m/s per leg (exact minimum)"),
        "allPhases": quantile_block(all_int, unit="m/s per leg (exact minimum)"),
    }

    # --- C6 LEO phasing campaign -----------------------------------------
    leo = read_jsonl(DOCS / "proximity-leo-events-20260922.jsonl")
    arm_m = [e for e in leo if e.get("armM")]
    da_from_rate, da_median, mps = [], [], []
    for e in arm_m:
        a_km = float(e["meanAKm"])
        k = pp.phase_rate_deg_per_day_per_km(a_km)
        rate = e.get("phaseRateMaxDegPerDay")
        if rate is not None and k:
            da = abs(float(rate) / k)
            da_from_rate.append(da)
            mps.append(leo_da_to_mps(da, a_km))
        if e.get("medianAbsDaKm") is not None:
            da_median.append(abs(float(e["medianAbsDaKm"])))
    plane_counts = [int(e.get("planeManoeuvresInCampaign") or 0) for e in arm_m]
    res["classes"]["C6_leo_phasing_campaign"] = {
        "source": "docs/proximity-leo-events-20260922.jsonl, armM rows",
        "daFromPhaseRate": quantile_block(
            da_from_rate, unit="km of |delta a| implied by phaseRateMaxDegPerDay"),
        "derivedMps": quantile_block(mps, unit="m/s (derived, da = 2 dv / n)"),
        "medianAbsDaDuringDwell": quantile_block(da_median, unit="km"),
        "detectionFloorKm": pp.DA_FLOOR_KM,
    }
    res["classes"]["C6i_leo_plane_change_in_campaign"] = {
        "source": "same, planeManoeuvresInCampaign",
        "totalPlaneManoeuvresAcrossArmM": int(sum(plane_counts)),
        "events": len(arm_m),
        "verdict": ("BLINDED CHANNEL -- not a zero-sized burn. T8b's plane "
                    "threshold is max(5 sigma_theta, 0.01 deg) = 3.5 deg "
                    "because the registered sigma_theta came back 145x too "
                    "large (T8b 2.3); the channel is essentially switched off, "
                    "so no plane-change size distribution exists to quantile."),
        "planeNoiseFloorDiagnosticDeg": 0.000148,
    }

    res["seconds"] = time.time() - t0
    out["M0"] = res
    return res


# ==========================================================================
# M1 -- Gate W beyond +30 d (reg 3)
# ==========================================================================
def _load_t8d(args):
    import pickle
    import trigger_alarm as ta
    arrays, emeta = ta.load_cached_extract(None)
    series = pg.build_series(arrays)
    del arrays
    by_norad = {s.norad: s for s in series}
    with open(T8D_WORK / "t8d-triggers.pkl", "rb") as fh:
        blob = pickle.load(fh)
    bundle = blob["bundle"]
    return ta, bundle, by_norad, emeta, blob.get("featurePathSha256")


def _qualifies_at(ta, triggers, by_norad, sigma_n, horizon_days):
    """reg 3.2 Arm B: the membership test `validate_propagator` applies, used
    ONLY to build the matched cohort. The cohort is then handed back to
    `validate_propagator` itself, and the run asserts that the function
    accepts every cohort member at every horizon -- so this mirror cannot
    silently disagree with the instrument it selects for."""
    keep = []
    flags_cache = {}
    for tr in triggers:
        s = by_norad.get(tr.norad)
        if s is None:
            continue
        if tr.norad not in flags_cache:
            flags_cache[tr.norad] = ta.flag_baselines(s, sigma_n)[0]
        fl = flags_cache[tr.norad]
        t_end = tr.tTrig + horizon_days * DAY_MS
        if np.any((fl > tr.tTrig) & (fl <= t_end)):
            continue
        k = int(np.searchsorted(s.epoch_ms, t_end, side="right")) - 1
        if k < 0 or abs(float(s.epoch_ms[k]) - t_end) > ta.MERGE_DAYS * DAY_MS:
            continue
        j = int(np.searchsorted(s.epoch_ms, tr.tTrig, side="right")) - 1
        if j < 0:
            continue
        if (float(s.epoch_ms[k]) - float(s.epoch_ms[j])) <= 0:
            continue
        keep.append(tr)
    return keep


def slot_spacing(ta, by_norad):
    """reg 3.4, ADDED HERE: the gaps between adjacent occupied mean longitudes
    of stationed objects at the archive's final element epoch. A description
    of today's belt, not a law and not a regulatory slot plan."""
    t_last = max(float(s.epoch_ms[-1]) for s in by_norad.values())
    sweep = ta.OccupancySweep(by_norad)
    lons, _ = sweep.at(t_last, -1)
    lons = np.sort(np.asarray(lons, dtype=np.float64))
    if lons.size < 2:
        return {"n": int(lons.size), "note": "too few occupied longitudes"}
    gaps = np.diff(lons)
    gaps = np.append(gaps, 360.0 - (lons[-1] - lons[0]))
    block = quantile_block(gaps, unit="deg between adjacent occupied longitudes")
    block.update({"occupiedLongitudes": int(lons.size),
                  "atEpochMs": t_last,
                  "definition": ("stationed = current element set inside the "
                                 "merge window, >= 30 d of history, "
                                 "|drift| <= 0.020 deg/day (the lane's own "
                                 "eligibility proxy)"),
                  "caveat": ("a description of the belt as the archive's last "
                             "epoch finds it; NOT a regulatory slot plan and "
                             "not a physical constant")})
    return block


def m1(out, args):
    t0 = time.time()
    ta, bundle, by_norad, emeta, feat_sha = _load_t8d(args)
    triggers = bundle["triggers"]
    sigma_n = float(bundle["sigma_n"])
    print(f"  M1: {len(triggers)} triggers, {len(by_norad)} histories, "
          f"sigma_n={sigma_n:.6g}", flush=True)

    res = {"registration": REGISTRATION,
           "instrument": ("tools/trigger_alarm.py::validate_propagator, "
                          "imported unchanged with check_days varied"),
           "triggers": len(triggers),
           "extract": emeta,
           "featurePathSha256": feat_sha,
           "published30d": {"n": T8D_PROP_N, "p50": T8D_PROP_P50,
                            "source": "docs/trigger-alarm-results-20260922.md section 4"}}

    # Gate K1 -- reproduction
    rep = ta.validate_propagator(triggers, by_norad, sigma_n, check_days=30.0)
    gate = {"n": rep.get("n"), "p50": rep.get("p50"),
            "nMatches": bool(rep.get("n") == T8D_PROP_N),
            "p50Matches": bool(round(float(rep.get("p50", float("nan"))), 3)
                               == T8D_PROP_P50)}
    gate["passed"] = bool(gate["nMatches"] and gate["p50Matches"])
    res["gateK1Reproduction"] = gate
    print(f"  M1 gate K1: n={gate['n']} p50={gate['p50']} passed={gate['passed']}",
          flush=True)
    if not gate["passed"]:
        res["armA"] = {"withheld": ("Gate K1 failed: a changed instrument may "
                                    "not be compared against a published "
                                    "number")}
        res["seconds"] = time.time() - t0
        out["M1"] = res
        return res

    horizons = sorted(set(HORIZONS_PRIMARY) | set(HORIZONS_FINE))
    arm_a = {}
    for h in horizons:
        r = ta.validate_propagator(triggers, by_norad, sigma_n, check_days=h)
        arm_a[f"{int(h)}"] = {k: r[k] for k in ("n", "p50", "p75", "p95") if k in r}
        print(f"    arm A +{int(h):>3} d: n={r.get('n')} "
              f"p50={r.get('p50')} p95={r.get('p95')}", flush=True)
    res["armA"] = {"note": ("each horizon on its own qualifying set, exactly "
                            "the +30 d method"), "byHorizon": arm_a}

    # Arm B -- the matched cohort
    cohort = triggers
    for h in HORIZONS_PRIMARY:
        cohort = _qualifies_at(ta, cohort, by_norad, sigma_n, h)
    arm_b, consistent = {}, True
    for h in HORIZONS_PRIMARY:
        r = ta.validate_propagator(cohort, by_norad, sigma_n, check_days=h)
        arm_b[f"{int(h)}"] = {k: r[k] for k in ("n", "p50", "p75", "p95") if k in r}
        if r.get("n") != len(cohort):
            consistent = False
        print(f"    arm B +{int(h):>3} d: n={r.get('n')} "
              f"p50={r.get('p50')} p95={r.get('p95')}", flush=True)
    res["armB"] = {"cohort": len(cohort),
                   "note": ("triggers qualifying at every primary horizon; the "
                            "only arm in which growth is a statement about "
                            "propagation rather than about which objects "
                            "stayed quiet"),
                   "selectorAgreesWithInstrument": consistent,
                   "byHorizon": arm_b}

    res["slotSpacing"] = slot_spacing(ta, by_norad)

    # The crossings, read against the registered screens
    def first_above(bar):
        for h in horizons:
            p50 = arm_a[f"{int(h)}"].get("p50")
            if p50 is not None and p50 > bar:
                return h
        return None

    slot_med = res["slotSpacing"].get("p50")
    res["crossings"] = {
        "colocationDeg": COLOCATION_DEG,
        "firstHorizonMedianAboveColocation": first_above(COLOCATION_DEG),
        "slotSpacingMedianDeg": slot_med,
        "firstHorizonMedianAboveSlotSpacing": (first_above(slot_med)
                                               if slot_med else None),
        "gateWBarDeg": GATE_W_DEG,
        "firstHorizonMedianAboveGateW": first_above(GATE_W_DEG),
        "note": ("every bar here is a screen, not a law: none of them says the "
                 "propagation becomes wrong at a horizon, only that its error "
                 "stops being small compared with the quantity the layer wants "
                 "to resolve"),
    }
    res["seconds"] = time.time() - t0
    out["M1"] = res
    return res


# ==========================================================================
# M2 -- LEO along-track phase-error growth (reg 4)
# ==========================================================================
def _m2_population(arm_m_norads):
    summary = {int(k): v for k, v in json.loads(
        (T8B_WORK / "detect-summary.json").read_text()).items()}
    meta = {int(k): v for k, v in json.loads(
        (T8B_WORK / "object-meta.json").read_text()).items()}
    flags_raw = json.loads((T8B_WORK / "detect-flags.json").read_text())
    flags = {}
    for k, v in flags_raw.items():
        a = np.asarray(v["intrack_ms"] + v["plane_ms"], dtype=np.float64)
        flags[int(k)] = np.sort(a)

    eligible = {}
    for nd, s in summary.items():
        if s.get("regimes") != ["LEO"]:
            continue
        if (s.get("elementSets", 0) < M2_MIN_ELEMENT_SETS
                or s.get("spanDays", 0.0) < M2_MIN_SPAN_DAYS):
            continue
        eligible[nd] = s

    never = {nd for nd, s in eligible.items()
             if not s.get("nIntrack") and not s.get("nPlane")}
    strata = {"S-arm-M": [], "S-payload": [], "S-never": [], "S-passive": []}
    for nd, s in eligible.items():
        label = pp.class_label((meta.get(nd) or {}).get("objectType"))
        if nd in arm_m_norads:
            strata["S-arm-M"].append(nd)
        elif nd in never:
            strata["S-never"].append(nd)
        elif label == "payload":
            strata["S-payload"].append(nd)
        elif label == "catalogue_passive":
            strata["S-passive"].append(nd)
    rng = np.random.default_rng(SEED)
    sampled = {}
    for name, nds in strata.items():
        nds = sorted(nds)
        if name == "S-arm-M" or len(nds) <= M2_STRATUM_TARGET:
            sampled[name] = nds
        else:
            pick = rng.choice(len(nds), size=M2_STRATUM_TARGET, replace=False)
            sampled[name] = sorted(int(nds[i]) for i in pick)
    return sampled, {k: len(v) for k, v in strata.items()}, flags, summary


def _object_elements(db, norad):
    rows = db.execute(
        "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, "
        "raan_q, arg_perigee_q, mean_anomaly_q, bstar_q FROM element_set "
        "WHERE norad = ? ORDER BY epoch_ms", (int(norad),)).fetchall()
    if len(rows) < 8:
        return None
    a = np.asarray(rows, dtype=np.float64)
    return {
        "epoch_ms": a[:, 0],
        "n": a[:, 1] / pp.SCALE_MM,
        "e": a[:, 2] / pp.SCALE_ECC,
        "inc": a[:, 3] / pp.SCALE_ANGLE,
        "raan": a[:, 4] / pp.SCALE_ANGLE,
        "argp": a[:, 5] / pp.SCALE_ANGLE,
        "ma": a[:, 6] / pp.SCALE_ANGLE,
        "bstar": a[:, 7] / 1e12,
    }


def phase_error_windows(el, flag_ms, horizon_days):
    """The two arms of reg 4.1.

    Arm P (DEVIATION from reg 4.1's literal u-form, declared in the results):
      phase error = |360 * integral_0^H (n(t) - n0) dt|, trapezoidal over the
      object's own observed mean motion. This is the along-track angle the
      object accumulates because its mean motion is not what it was, which is
      what an unmodelled semi-major-axis change or drag produces and what
      T8b's own model (gamma_dot = k(a) * da) says relative phase responds to.
      It carries no secular term, so nothing common-mode to both objects of a
      pair can enter it and no wrap can alias it.

    Arm U (reg 4.1 as written): the error of u = argp + M propagated at
      360 * n0, unwrapped. Reported so the size of the secular terms Arm P
      excludes is visible rather than asserted.
    """
    ep, n, argp, ma = el["epoch_ms"], el["n"], el["argp"], el["ma"]
    t = ep / DAY_MS
    hp, hu, suspects, used = [], [], 0, 0
    rejected = {"flagInWindow": 0, "noFarEnd": 0, "gap": 0, "unwrapSuspect": 0}
    i = 0
    while i < ep.size - 1:
        t_end = ep[i] + horizon_days * DAY_MS
        k = int(np.searchsorted(ep, t_end, side="right")) - 1
        if k <= i:
            i += 1
            continue
        if abs(float(ep[k]) - t_end) > MAX_GAP_DAYS * DAY_MS:
            rejected["noFarEnd"] += 1
            i = k if k > i else i + 1
            continue
        seg = slice(i, k + 1)
        if flag_ms.size and np.any((flag_ms > ep[i]) & (flag_ms <= ep[k])):
            rejected["flagInWindow"] += 1
            i = k
            continue
        if np.max(np.diff(ep[seg])) / DAY_MS > MAX_GAP_DAYS:
            rejected["gap"] += 1
            i = k
            continue
        # Arm P
        dn = n[seg] - n[i]
        integral = float(np.trapezoid(dn, t[seg])) if hasattr(np, "trapezoid") \
            else float(np.trapz(dn, t[seg]))
        # Arm U
        u_obs = pp.wrap360(argp[seg] + ma[seg])
        u_pred = u_obs[0] + 360.0 * n[i] * (t[seg] - t[i])
        raw = pp.wrap180(u_pred - u_obs)
        unw = np.degrees(np.unwrap(np.radians(raw)))
        step = float(np.max(np.abs(np.diff(unw)))) if unw.size > 1 else 0.0
        if step > UNWRAP_SUSPECT_DEG:
            suspects += 1
            rejected["unwrapSuspect"] += 1
        else:
            hu.append(abs(float(unw[-1])))
        hp.append(abs(360.0 * integral))
        used += 1
        i = k
    return {"armP": hp, "armU": hu, "windows": used,
            "unwrapSuspect": suspects, "rejected": rejected}


def m2(out, args):
    t0 = time.time()
    leo = read_jsonl(DOCS / "proximity-leo-events-20260922.jsonl")
    arm_m_norads = set()
    for e in leo:
        if e.get("armM"):
            arm_m_norads.add(int(e["approacher"]))
            arm_m_norads.add(int(e["target"]))
    sampled, stratum_sizes, flags, summary = _m2_population(arm_m_norads)
    total = sum(len(v) for v in sampled.values())
    print(f"  M2: {total} objects sampled over {len(sampled)} strata "
          f"(eligible {stratum_sizes})", flush=True)

    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    db.execute("PRAGMA query_only = 1")
    rows = []
    rejected_total = {"flagInWindow": 0, "noFarEnd": 0, "gap": 0,
                      "unwrapSuspect": 0}
    no_elements = 0
    done = 0
    for stratum, norads in sampled.items():
        for nd in norads:
            el = _object_elements(db, nd)
            done += 1
            if done % 250 == 0:
                print(f"    {done}/{total} objects, {time.time()-t0:.0f}s",
                      flush=True)
            if el is None:
                no_elements += 1
                continue
            sig_t, sig_n = pp.object_sigma_contributions(el)
            fl = flags.get(nd, np.asarray([], dtype=np.float64))
            row = {"norad": int(nd), "stratum": stratum,
                   "sigmaNRevDay": None if not np.isfinite(sig_n) else float(sig_n),
                   "bstarMedian": float(np.median(el["bstar"])),
                   "ndotRevDay2": float((summary.get(nd) or {}).get("ndot", float("nan"))),
                   "elementSets": int(el["epoch_ms"].size),
                   "aMedianKm": float(pp.semi_major_axis_km(np.median(el["n"]))),
                   "horizons": {}}
            for h in M2_HORIZONS:
                w = phase_error_windows(el, fl, h)
                for k in rejected_total:
                    rejected_total[k] += w["rejected"][k]
                row["horizons"][str(int(h))] = {
                    "windows": w["windows"],
                    "armPMedianDeg": (float(np.median(w["armP"]))
                                      if w["armP"] else None),
                    "armUMedianDeg": (float(np.median(w["armU"]))
                                      if w["armU"] else None),
                    "unwrapSuspect": w["unwrapSuspect"],
                }
            rows.append(row)
    db.close()

    jsonl = DOCS / "kinematic-inputs-m2-phase-20260922.jsonl"
    with open(jsonl, "w") as fh:
        fh.write(json.dumps({
            "record": "provenance", "study": "M2 LEO along-track phase error",
            "registration": REGISTRATION, "seed": SEED,
            "note": ("One row per sampled object. armP is the integrated "
                     "mean-motion phase error; armU is the registration's "
                     "literal u-form, reported for comparison. No registry "
                     "code, no country, no name, no delta-v and no fuel "
                     "figure is carried on any row."),
            "strataEligible": stratum_sizes,
            "strataSampled": {k: len(v) for k, v in sampled.items()}}) + "\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    res = {"registration": REGISTRATION,
           "objects": len(rows), "noElementSeries": no_elements,
           "strataEligible": stratum_sizes,
           "strataSampled": {k: len(v) for k, v in sampled.items()},
           "windowsRejected": rejected_total,
           "rows": str(jsonl.relative_to(_REPO)),
           "armP": {}, "armU": {}, "meaningfulHorizon": {},
           "covariates": {}}

    def per_stratum(arm, h):
        cells = {}
        for stratum in list(sampled) + ["POOLED"]:
            vals = [r["horizons"][str(int(h))][f"{arm}MedianDeg"] for r in rows
                    if (stratum == "POOLED" or r["stratum"] == stratum)
                    and r["horizons"][str(int(h))][f"{arm}MedianDeg"] is not None]
            cells[stratum] = quantile_block(vals, unit="deg")
        return cells

    for h in M2_HORIZONS:
        res["armP"][str(int(h))] = per_stratum("armP", h)
        res["armU"][str(int(h))] = per_stratum("armU", h)

    # reg 4.6 -- the meaningful-horizon fraction
    for h in M2_HORIZONS:
        cell = {}
        for bar_name, bar in (("gamma5", GAMMA_DEG), ("gamma2p5", GAMMA_DEG / 2.0),
                              ("gammaTight", GAMMA_TIGHT)):
            per = {}
            for stratum in list(sampled) + ["POOLED"]:
                sel = [r for r in rows
                       if (stratum == "POOLED" or r["stratum"] == stratum)]
                usable = [r for r in sel
                          if r["horizons"][str(int(h))]["armPMedianDeg"] is not None]
                inside = [r for r in usable
                          if r["horizons"][str(int(h))]["armPMedianDeg"] <= bar]
                per[stratum] = {
                    "objectsSampled": len(sel),
                    "withUsableWindow": len(usable),
                    "noUsableWindow": len(sel) - len(usable),
                    "inside": len(inside),
                    "fraction": (len(inside) / len(usable)) if usable else None,
                    "underpowered": bool(len(usable) < MIN_N),
                }
            cell[bar_name] = {"barDeg": bar, "byStratum": per}
        res["meaningfulHorizon"][str(int(h))] = cell

    # covariates: deciles and Spearman, association only
    def spearman(x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        ok = np.isfinite(x) & np.isfinite(y)
        x, y = x[ok], y[ok]
        if x.size < 3:
            return None, int(x.size)
        rx = np.argsort(np.argsort(x)).astype(np.float64)
        ry = np.argsort(np.argsort(y)).astype(np.float64)
        rx -= rx.mean()
        ry -= ry.mean()
        den = math.sqrt(float((rx ** 2).sum()) * float((ry ** 2).sum()))
        return (float((rx * ry).sum() / den) if den else None), int(x.size)

    for h in M2_HORIZONS:
        err = [r["horizons"][str(int(h))]["armPMedianDeg"] for r in rows]
        block = {}
        for name, key in (("sigmaN", "sigmaNRevDay"), ("bstar", "bstarMedian"),
                          ("ndot", "ndotRevDay2")):
            cov = [r[key] if r[key] is not None else float("nan") for r in rows]
            rho, n = spearman(cov, [e if e is not None else float("nan")
                                    for e in err])
            # deciles of the covariate, median error in each
            c = np.asarray(cov, dtype=np.float64)
            e = np.asarray([x if x is not None else float("nan") for x in err],
                           dtype=np.float64)
            ok = np.isfinite(c) & np.isfinite(e)
            deciles = []
            if ok.sum() >= 10:
                cs, es = c[ok], e[ok]
                edges = np.quantile(cs, np.linspace(0, 1, 11))
                for d in range(10):
                    lo, hi = edges[d], edges[d + 1]
                    m = (cs >= lo) & (cs <= hi if d == 9 else cs < hi)
                    deciles.append({"decile": d + 1, "lo": float(lo),
                                    "hi": float(hi), "n": int(m.sum()),
                                    "medianErrorDeg": (float(np.median(es[m]))
                                                       if m.sum() else None)})
            block[name] = {"spearman": rho, "n": n, "deciles": deciles}
        res["covariates"][str(int(h))] = block
    res["covariateNote"] = ("association only: no functional form is fitted "
                            "and no drag model is built. LEO drag remains "
                            "unmodelled and this measurement does not "
                            "discharge that.")
    res["designArithmeticUnderTest"] = {
        "claim": ("design 2.5: sigma_n = 6.27e-5 rev/day implies 2.0 deg of "
                  "phase at 90 d at the median"),
        "isA": "noise-propagation calculation, not a measurement",
        "measuredArmPMedian90d": res["armP"]["90"]["POOLED"].get("p50"),
    }
    res["seconds"] = time.time() - t0
    out["M2"] = res
    return res


# ==========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="M0/M1/M2 kinematic inputs")
    ap.add_argument("--stage", choices=("m0", "m1", "m2", "all"), default="all")
    ap.add_argument("--out", type=Path, default=DOCS)
    ap.add_argument("--date", default="20260922")
    args = ap.parse_args(argv)

    started, cpu0 = time.time(), time.process_time()
    path = args.out / f"kinematic-inputs-{args.date}.json"
    out = json.loads(path.read_text()) if path.exists() else {}

    if args.stage in ("m0", "all"):
        print("M0: class-conditional next-burn size ...", flush=True)
        m0(out)
    if args.stage in ("m1", "all"):
        print("M1: forward error beyond +30 d ...", flush=True)
        m1(out, args)
    if args.stage in ("m2", "all"):
        print("M2: LEO along-track phase-error growth ...", flush=True)
        m2(out, args)

    out["registration"] = REGISTRATION
    out["measuredAt"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(out, indent=1, default=float))

    receipt = {
        "study": "M0/M1/M2 kinematic inputs",
        "registration": REGISTRATION,
        "stage": args.stage,
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "host": os.uname().nodename, "executionMode": "cpu",
        "wallSeconds": time.time() - started,
        "cpuSeconds": time.process_time() - cpu0,
        "sourceSha256": {
            "tools/kinematic_inputs.py": sha256_file(Path(__file__)),
            REGISTRATION: sha256_file(_REPO / REGISTRATION),
        },
    }
    for name in ("proximity-events-20260922.jsonl",
                 "trigger-alarm-triggers-20260922.jsonl",
                 "stationkeeping-ns-20260922.jsonl",
                 "stationkeeping-ew-20260922.jsonl",
                 "transfer-loss-20260922.jsonl",
                 "proximity-leo-events-20260922.jsonl"):
        p = DOCS / name
        if p.exists():
            receipt["sourceSha256"][f"docs/{name}"] = sha256_file(p)
    rpath = args.out / f"kinematic-inputs-{args.date}-receipt.json"
    if rpath.exists():
        prev = json.loads(rpath.read_text())
        prev.setdefault("stages", {})[args.stage] = receipt
        rpath.write_text(json.dumps(prev, indent=1, default=float))
    else:
        receipt["stages"] = {args.stage: dict(receipt)}
        rpath.write_text(json.dumps(receipt, indent=1, default=float))
    print(f"wrote {path} and {rpath} in {time.time()-started:.1f}s", flush=True)
    return out


if __name__ == "__main__":
    main()
