#!/usr/bin/env python3
"""A GEO control built on EPOCHS of free libration inside a history.

Registration: docs/geo-libration-epoch-control-preregistration-20260922.md

The object-level control failed for a physical reason that was measured, not
supposed: a stationed passive GEO object is a free librator, and a free
librator at its turnaround dwells beside whatever shares its longitude, which
is the shape the approach detector is built to find. That is a statement about
WHEN in a history the signal appears, not about WHICH objects carry it.

The unit here is therefore an interval of one object's element-set history over
which the motion is provably uncontrolled: no residual drift change above the
floor once free triaxial motion is predicted and subtracted, the local
free-libration bounds satisfied at every sample, no energy step beyond what
free motion could produce, and no 14.00-day line in any block inside it.

Every constant is committed by an earlier registration or derived from those
constants with no fit. CPU only.
"""

import argparse
import json
import math
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
import sys
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import persistent_pairs as pp                      # noqa: E402
from tools import proximity_geo as pg                         # noqa: E402
from tools import geo_passive_control as gec                  # noqa: E402
from tools import trigger_alarm as ta                         # noqa: E402
from pipeline import orbit_campaigns                          # noqa: E402

DAY_MS = pp.DAY_MS
REGISTRATION = "docs/geo-libration-epoch-control-preregistration-20260922.md"

# --------------------------------------------------------------------------
# Section 3.1 -- carried forward unchanged. Nothing here is fitted.
# --------------------------------------------------------------------------
A_DEG_PER_DAY2 = gec.A_DEG_PER_DAY2          # 1.7006955627927864e-3
A_RAD_PER_DAY2 = gec.A_RAD_PER_DAY2
TWO_A_RAD = 2.0 * A_RAD_PER_DAY2
T0_DAYS = gec.T0_DAYS                        # 815.4792
SIGMA_K = gec.SIGMA_K                        # 5, T8a unchanged
BASELINE_SAMPLES = gec.BASELINE_SAMPLES      # 10, T8a unchanged
MAX_BASELINE_SPAN_DAYS = gec.MAX_BASELINE_SPAN_DAYS          # 14.00
MAX_GAP_DAYS = pg.MAX_GAP_DAYS                               # 5.0
BLOCK_DAYS = gec.BLOCK_DAYS                                  # 56.00
BLOCK_MIN_SAMPLES = gec.BLOCK_MIN_SAMPLES                    # 8
EW_PERIOD_DAYS = gec.EW_PERIOD_DAYS                          # 14.00
TURNAROUND_MIN_RUN_DAYS = gec.TURNAROUND_MIN_RUN_DAYS        # 30.0
LEAK_BAR = gec.LEAK_BAR                                      # 0.10
DEG_TO_RAD = math.pi / 180.0

# Section 4.4 -- the run-level admission rule
MIN_EPOCH_DAYS = BLOCK_DAYS                                  # 56.00
MIN_EPOCH_SAMPLES = BASELINE_SAMPLES + 2                     # 12
F1_FAMILYWISE = gec.F1_FAMILYWISE                            # 0.10
F1_PER_BLOCK = gec.F1_EXCLUDE_FAP                            # 0.10, arm

# Section 3.3 -- the derived keeper blind spot is computed from the MEASURED
# sigma_n by `u_star_deg` below, not stored as a literal.
VALIDATION_OBJECTS = gec.VALIDATION_OBJECTS                  # 200
SEED_LIBRATOR = gec.SEED                                     # 20260922
SEED_KEEPER = gec.SEED + 1                                   # 20260923
V_E1_BAR = 1.0
V_E2_BAR = 1.0
V4_INSTABILITY_FACTOR = gec.V4_INSTABILITY_FACTOR            # 3.0

CATALOGUE_SHA256 = gec.CATALOGUE_SHA256
STRATA = ("ALL", "TURN", "QUIET")
CONSUMERS = ("t8aEvents", "t11Episodes", "triggerChains")


def u_star_deg(sigma_n):
    """Section 3.3: the slot displacement below which a keeping burn at the
    measured cycle sits under the measured noise floor.

    A |sin 2u| T/2 > 5 sigma_n  ->  |sin 2u| > 5 sigma_n / (A T / 2)
    """
    ratio = (SIGMA_K * sigma_n) / (A_DEG_PER_DAY2 * EW_PERIOD_DAYS / 2.0)
    if ratio >= 1.0:
        return 90.0
    return 0.5 * math.degrees(math.asin(ratio))


# ==========================================================================
# Section 3.2 -- the first integral as a local quantity
# ==========================================================================
def implied_s(lam_deg, drift_deg_per_day):
    """s = sin^2 u + v^2 / (2 A), with u the displacement from the NEARER
    stable longitude. Constant for free motion; computable from one element
    set. Returns (s, u_deg, stable_deg)."""
    stable, u_deg = gec.nearest_stable(lam_deg)
    u_rad = np.radians(np.asarray(u_deg, dtype=np.float64))
    v_rad = np.radians(np.asarray(drift_deg_per_day, dtype=np.float64))
    s = np.sin(u_rad) ** 2 + (v_rad * v_rad) / TWO_A_RAD
    return s, np.asarray(u_deg, dtype=np.float64), stable


def implied_u_max_deg(s):
    """The half-amplitude the first integral implies, arcsin sqrt(s)."""
    x = np.sqrt(np.clip(np.asarray(s, dtype=np.float64), 0.0, 1.0))
    return np.degrees(np.arcsin(x))


# ==========================================================================
# Section 4.2 -- sample-level admissibility
# ==========================================================================
def v2_detail(epoch_ms, drift, lam, sigma_n):
    """The v2 rule's own arrays, sample by sample.

    The flag indices this returns are asserted in the test suite to be exactly
    the epochs `geo_passive_control.v2_flags` returns, so the two cannot drift
    apart.
    """
    t = np.asarray(epoch_ms, dtype=np.float64) / DAY_MS
    d = np.asarray(drift, dtype=np.float64)
    lo = np.asarray(lam, dtype=np.float64)
    n = d.size
    w = BASELINE_SAMPLES
    empty = {"dt": np.zeros(0), "evaluable": np.zeros(0, dtype=bool),
             "flagIdx": np.zeros(0, dtype=np.int64), "tested": 0}
    if n < w + 2:
        return empty
    base = np.full(n, np.nan)
    tcen = np.full(n, np.nan)
    lcen = np.full(n, np.nan)
    sw = np.lib.stride_tricks.sliding_window_view
    base[w:] = np.median(sw(d[:n - 1], w)[:n - w], axis=1)
    tcen[w:] = np.median(sw(t[:n - 1], w)[:n - w], axis=1)
    lcen[w:] = np.median(sw(lo[:n - 1], w)[:n - w], axis=1)
    dt = t - tcen
    acc_i = gec.free_acceleration(lo)
    acc_c = gec.free_acceleration(lcen)
    pred = 0.5 * (acc_c + acc_i) * dt
    dev = np.abs(d - base - pred)
    thresh = np.maximum(SIGMA_K * sigma_n, np.abs(acc_i) * dt)
    evaluable = np.isfinite(dt) & (dt <= MAX_BASELINE_SPAN_DAYS)
    hot = np.isfinite(dev) & (dev > thresh) & evaluable
    confirmed = np.where(hot[:-1] & hot[1:])[0] + 1
    return {"dt": dt, "evaluable": evaluable,
            "flagIdx": confirmed.astype(np.int64),
            "tested": int(np.isfinite(dt).sum())}


def energy_step_ok(t_days, s, u_deg, drift, sigma_n):
    """Section 4.3, A5. Returns a boolean per consecutive pair (length n-1).

    |ds| <= dt * max(|v sin 2u|) + 5 sqrt(sig_s^2 + sig_s^2) + sig_r^2/(2A)
    every term derived from the committed constants.
    """
    n = s.size
    if n < 2:
        return np.zeros(0, dtype=bool)
    sig_r = sigma_n * DEG_TO_RAD
    v_rad = np.radians(np.asarray(drift, dtype=np.float64))
    u_rad = np.radians(np.asarray(u_deg, dtype=np.float64))
    free_rate = np.abs(v_rad * np.sin(2.0 * u_rad))
    sig_s = np.abs(v_rad) * sig_r / A_RAD_PER_DAY2
    dt = np.diff(np.asarray(t_days, dtype=np.float64))
    bound = (dt * np.maximum(free_rate[:-1], free_rate[1:])
             + SIGMA_K * np.sqrt(sig_s[:-1] ** 2 + sig_s[1:] ** 2)
             + sig_r * sig_r / TWO_A_RAD)
    return np.abs(np.diff(s)) <= bound


# ==========================================================================
# Section 4.4 -- the run-level tests
# ==========================================================================
def _blocks_in(t_days, drift, i0, i1):
    """Consecutive non-overlapping 56.00-day blocks from the run's own start.
    Returns (min_fap, n_blocks)."""
    t = t_days[i0:i1 + 1]
    d = drift[i0:i1 + 1]
    if t.size < BLOCK_MIN_SAMPLES:
        return float("nan"), 0
    edges = np.arange(t[0], t[-1] + BLOCK_DAYS, BLOCK_DAYS)
    idx = np.searchsorted(t, edges)
    best, blocks = float("inf"), 0
    for k in range(idx.size - 1):
        a, b = int(idx[k]), int(idx[k + 1])
        if b - a < BLOCK_MIN_SAMPLES:
            continue
        fit = pp.cadence_phasor(t[a:b], d[a:b])
        if fit is None:
            continue
        blocks += 1
        best = min(best, float(fit["fap"]))
    if blocks == 0:
        return float("nan"), 0
    return best, blocks


def _has_turnaround(t_days, drift, i0, i1):
    """Section 6: T11b bound 2, applied inside the run and used only to
    stratify."""
    runs = gec._sign_runs(t_days[i0:i1 + 1], drift[i0:i1 + 1],
                          TURNAROUND_MIN_RUN_DAYS)
    for a, b in zip(runs[:-1], runs[1:]):
        if a[0] != b[0]:
            return True
    return False


def find_epochs(series, sigma_n, familywise=True):
    """Section 4: every admitted free-libration epoch of one object.

    Returns (epochs, diagnostics). Each epoch is a dict; no epoch names a
    motive and no catalogue field enters any decision here.
    """
    t_ms = np.asarray(series.epoch_ms, dtype=np.float64)
    t = t_ms / DAY_MS
    lam = np.asarray(series.lam, dtype=np.float64)
    drift = np.asarray(series.drift, dtype=np.float64)
    n = t.size
    diag = {"elementSets": int(n), "candidateRuns": 0, "rejectedShort": 0,
            "rejectedFewSamples": 0, "rejectedCadence": 0,
            "rejectedNoBlock": 0, "admitted": 0}
    if n < MIN_EPOCH_SAMPLES:
        return [], diag

    det = v2_detail(t_ms, drift, lam, sigma_n)
    if det["evaluable"].size == 0:
        return [], diag
    s, u_deg, stable = implied_s(lam, drift)

    ok = det["evaluable"].copy()                       # A1
    ok[det["flagIdx"]] = False                         # A2
    ok &= np.abs(u_deg) < gec.MAX_DISPLACEMENT_DEG     # A3 local part
    ok &= np.isfinite(s) & (s <= 1.0)                  # A4

    pair_ok = energy_step_ok(t, s, u_deg, drift, sigma_n)          # A5
    gap_ok = np.diff(t) <= MAX_GAP_DAYS
    cell_ok = stable[:-1] == stable[1:]                # A3 run part
    link = pair_ok & gap_ok & cell_ok

    epochs = []
    i = 0
    while i < n:
        if not ok[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and ok[j + 1] and link[j]:
            j += 1
        diag["candidateRuns"] += 1
        i0, i1 = i, j
        i = j + 1
        span = t[i1] - t[i0]
        if i1 - i0 + 1 < MIN_EPOCH_SAMPLES:
            diag["rejectedFewSamples"] += 1
            continue
        if span < MIN_EPOCH_DAYS:
            diag["rejectedShort"] += 1
            continue
        fap, blocks = _blocks_in(t, drift, i0, i1)
        if blocks == 0:
            diag["rejectedNoBlock"] += 1
            continue
        alpha = (gec.sidak_block_alpha(blocks) if familywise
                 else F1_PER_BLOCK)
        if np.isfinite(fap) and fap <= alpha:
            diag["rejectedCadence"] += 1
            continue
        diag["admitted"] += 1
        seg_s = s[i0:i1 + 1]
        epochs.append({
            "norad": int(series.norad),
            "i0": int(i0), "i1": int(i1),
            "startMs": float(t_ms[i0]), "endMs": float(t_ms[i1]),
            "days": float(span), "elementSets": int(i1 - i0 + 1),
            "stableLongitudeDeg": float(stable[i0]),
            "impliedUMaxDeg": float(implied_u_max_deg(np.max(seg_s))),
            "medianAbsUDeg": float(np.median(np.abs(u_deg[i0:i1 + 1]))),
            "minBlockFap": float(fap), "cadenceBlocks": int(blocks),
            "sidakAlpha": float(alpha),
            "turnaround": bool(_has_turnaround(t, drift, i0, i1)),
        })
    return epochs, diag


# ==========================================================================
# Section 5 -- exposure
# ==========================================================================
def _day_span(start_ms, end_ms):
    return (int(math.ceil(start_ms / DAY_MS)), int(math.floor(end_ms / DAY_MS)))


def epoch_days(epochs):
    """day -> set of objects inside an admitted epoch on that day."""
    per_day = {}
    for e in epochs:
        a, b = _day_span(e["startMs"], e["endMs"])
        for d in range(a, b + 1):
            per_day.setdefault(d, set()).add(e["norad"])
    return per_day


def watched_runs(series, max_gap_days=MAX_GAP_DAYS):
    """Runs of element sets with no internal gap beyond the registered
    catalogue gap -- the days on which the detector could have seen the
    object. Returns [(start_ms, end_ms)]."""
    t = np.asarray(series.epoch_ms, dtype=np.float64)
    if t.size == 0:
        return []
    brk = np.where(np.diff(t) > max_gap_days * DAY_MS)[0]
    starts = np.concatenate(([0], brk + 1))
    ends = np.concatenate((brk, [t.size - 1]))
    return [(float(t[a]), float(t[b])) for a, b in zip(starts, ends) if b > a]


def days_map(intervals_by_object):
    per_day = {}
    for norad, ivs in intervals_by_object.items():
        for st, en in ivs:
            a, b = _day_span(st, en)
            for d in range(a, b + 1):
                per_day.setdefault(d, set()).add(norad)
    return per_day


def exposure_from_days(per_day):
    obj_days = sum(len(v) for v in per_day.values())
    pair_days = sum(len(v) * (len(v) - 1) // 2 for v in per_day.values())
    return int(obj_days), int(pair_days)


def in_any(intervals, t_ms):
    for st, en in intervals:
        if st <= t_ms <= en:
            return True
    return False


def contains(intervals, t0, t1):
    for st, en in intervals:
        if st <= t0 and t1 <= en:
            return True
    return False


def overlaps(intervals, t0, t1):
    for st, en in intervals:
        if st <= t1 and t0 <= en:
            return True
    return False


# ==========================================================================
# Section 8 -- the leak proof
# ==========================================================================
def count_t8a(intervals_by_object, events, anchor="arrivalMs"):
    """A row whose anchor is absent from the committed catalogue cannot be
    placed and is not counted; the count of such rows is returned beside the
    numerator so an absence is never read as a zero."""
    n, unplaceable = 0, 0
    for e in events:
        iv = intervals_by_object.get(int(e["approacherNorad"]))
        if not iv:
            continue
        if anchor == "span":
            a, b = e.get("transferStartMs"), e.get("departureMs")
            if a is None or b is None:
                unplaceable += 1
                continue
            if contains(iv, float(a), float(b)):
                n += 1
            continue
        v = e.get(anchor)
        if v is None:
            unplaceable += 1
            continue
        if in_any(iv, float(v)):
            n += 1
    count_t8a.unplaceable = unplaceable
    return n


def count_t11(intervals_by_object, episodes, rule="contains"):
    n = 0
    for e in episodes:
        ia = intervals_by_object.get(int(e["a"]))
        ib = intervals_by_object.get(int(e["b"]))
        if not ia or not ib:
            continue
        t0, t1 = float(e["startMs"]), float(e["endMs"])
        fn = contains if rule == "contains" else overlaps
        if fn(ia, t0, t1) and fn(ib, t0, t1):
            n += 1
    return n


def count_triggers(intervals_by_object, chains_by_object):
    n = 0
    for norad, iv in intervals_by_object.items():
        for _t_first, t_trig, _stages, _size, _base in chains_by_object.get(
                norad, ()):
            if in_any(iv, float(t_trig)):
                n += 1
    return n


def build_chains(series_by_norad, sigma_n):
    """T8d's own trigger arithmetic, unchanged, run WITHOUT the active-class
    restriction -- which is how a control is proved."""
    out = {}
    for norad, s in series_by_norad.items():
        flags, sizes, bases = ta.flag_baselines(s, sigma_n)
        out[norad] = ta.chain_flags(flags, sizes, bases)
    return out


def reading(events, exposure, ref_events, ref_exposure, bar=LEAK_BAR):
    rate = (events / exposure) if exposure else float("nan")
    ref_rate = (ref_events / ref_exposure) if ref_exposure else float("nan")
    need = (1.0 / ref_rate) if ref_rate and np.isfinite(ref_rate) else None
    ratio = (rate / ref_rate) if (exposure and ref_rate) else float("nan")
    if exposure and ref_exposure:
        _r, lo, hi = pp.rate_ratio_ci(events, exposure,
                                      ref_events, ref_exposure)
    else:
        lo, hi = float("nan"), float("nan")
    evaluable = bool(need is not None and exposure >= need)
    if not evaluable:
        verdict = "UNEVALUABLE"
    elif ratio <= bar:
        verdict = "LEAK-FREE"
    else:
        verdict = "LEAKS"
    return {"events": int(events), "exposure": int(exposure),
            "rate": rate, "referenceEvents": int(ref_events),
            "referenceExposure": int(ref_exposure), "referenceRate": ref_rate,
            "meaningfulZeroExposure": need, "leakRatio": ratio,
            "leakRatioCi95": [lo, hi], "bar": bar,
            "evaluable": evaluable, "verdict": verdict}


# ==========================================================================
# Section 7 -- validation BEFORE use
# ==========================================================================
def keeper_slots(seed, n=VALIDATION_OBJECTS):
    """The slot longitudes `synthetic_keepers` draws, recomputed by the same
    generator call order so that each keeper can be placed against u*."""
    rng = np.random.default_rng(seed)
    return rng.uniform(-180.0, 180.0, size=n)


def _admit_summary(objects, sigma_n, familywise=True):
    out = {"objects": len(objects), "withEpoch": 0, "epochs": 0,
           "epochDays": 0.0, "sampledDays": 0.0, "admittedDays": 0.0,
           "turn": 0, "quiet": 0, "perObject": []}
    for s in objects:
        eps, _d = find_epochs(s, sigma_n, familywise=familywise)
        span = (float(s.epoch_ms[-1]) - float(s.epoch_ms[0])) / DAY_MS
        got = sum(e["days"] for e in eps)
        out["sampledDays"] += span
        out["admittedDays"] += got
        out["epochs"] += len(eps)
        out["epochDays"] += got
        out["turn"] += sum(1 for e in eps if e["turnaround"])
        out["quiet"] += sum(1 for e in eps if not e["turnaround"])
        if eps:
            out["withEpoch"] += 1
        out["perObject"].append({"norad": int(s.norad), "epochs": len(eps),
                                 "days": got})
    out["withEpochFraction"] = out["withEpoch"] / max(1, len(objects))
    out["admittedDayFraction"] = (out["admittedDays"] /
                                  out["sampledDays"] if out["sampledDays"]
                                  else float("nan"))
    return out


def validate(sigma_n):
    t0 = time.time()
    ustar = u_star_deg(sigma_n)
    out = {"uStarDeg": ustar,
           "uStarDerivation": ("5 sigma_n / (A T/2); a keeper inside this "
                               "displacement of a stable longitude has burns "
                               "under the measured noise floor")}

    lib = gec.synthetic_librators(SEED_LIBRATOR, sigma_n=sigma_n)
    v1 = _admit_summary(lib, sigma_n)
    v1["bar"] = V_E1_BAR
    v1["passed"] = bool(v1["withEpoch"] == len(lib))
    v1.pop("perObject")
    out["V_E1"] = v1

    def keeper_arm(self_consistent):
        keep = gec.synthetic_keepers(SEED_KEEPER, sigma_n=sigma_n,
                                     self_consistent=self_consistent)
        summ = _admit_summary(keep, sigma_n)
        slots = keeper_slots(SEED_KEEPER, len(keep))
        _stable, u_slot = gec.nearest_stable(slots)
        admitted = [r["norad"] - 800000 for r in summ["perObject"]
                    if r["epochs"] > 0]
        rows = [{"index": int(k), "slotDeg": float(slots[k]),
                 "absUSlotDeg": float(abs(u_slot[k])),
                 "insideUStar": bool(abs(u_slot[k]) < ustar)}
                for k in admitted]
        summ.pop("perObject")
        summ["excluded"] = len(keep) - len(admitted)
        summ["excludedFraction"] = summ["excluded"] / len(keep)
        summ["admittedKeepers"] = rows
        summ["admittedOutsideUStar"] = sum(1 for r in rows
                                           if not r["insideUStar"])
        outside = [k for k in range(len(keep))
                   if abs(u_slot[k]) >= ustar]
        summ["keepersOutsideUStar"] = len(outside)
        summ["excludedOutsideUStar"] = (len(outside)
                                        - summ["admittedOutsideUStar"])
        summ["excludedOutsideUStarFraction"] = (
            summ["excludedOutsideUStar"] / len(outside) if outside
            else float("nan"))
        return summ

    v2 = keeper_arm(True)
    v2["bar"] = V_E2_BAR
    v2["primaryBarPassed"] = bool(v2["admittedOutsideUStar"] == 0)
    v2["overallBarPassed"] = bool(v2["excluded"] == v2["objects"])
    out["V_E2"] = v2
    v2b = keeper_arm(False)
    v2b["note"] = ("labelled arm: the ramp rate is the maximum triaxial "
                   "acceleration rather than the acceleration at the "
                   "object's own slot")
    out["V_E2_maxRamp"] = v2b
    out["wallSeconds"] = time.time() - t0
    return out


# ==========================================================================
# Driver
# ==========================================================================
def load_jsonl(path):
    out = []
    with Path(path).open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                continue
            out.append(rec)
    return out


def _intervals(epochs):
    out = {}
    for e in epochs:
        out.setdefault(e["norad"], []).append((e["startMs"], e["endMs"]))
    return out


def analyze(db, archive_path, w, args):
    started = time.time()
    cat = args.docs / "persistent-pairs-20260922.jsonl"
    sha = pg.sha256_file(cat)
    if sha != CATALOGUE_SHA256:
        raise SystemExit("GATE G-E7: the T11 catalogue pin does not match. "
                         f"{sha} != {CATALOGUE_SHA256}")
    episodes = load_jsonl(cat)
    t8a_path = args.docs / "proximity-events-20260922.jsonl"
    events = load_jsonl(t8a_path)

    sigma_n = w.sigma_n
    out = {"schema": 1,
           "measuredAt": datetime.now(timezone.utc).isoformat(),
           "registration": REGISTRATION,
           "host": socket.gethostname(), "executionMode": "cpu",
           "archive": pp._archive_meta(db, archive_path),
           "extract": w.extractMeta,
           "inputs": {"catalogue": cat.name, "catalogueSha256": sha,
                      "episodes": len(episodes),
                      "t8aCatalogue": t8a_path.name,
                      "t8aCatalogueSha256": pg.sha256_file(t8a_path),
                      "t8aEvents": len(events)},
           "derivations": {
               "aDegPerDay2": A_DEG_PER_DAY2,
               "twoARadPerDay2": TWO_A_RAD,
               "t0Days": T0_DAYS,
               "sigmaNDegPerDay": sigma_n,
               "fiveSigmaN": SIGMA_K * sigma_n,
               "ewBurnStepDegPerDay": gec.EW_BURN_STEP,
               "uStarDeg": u_star_deg(sigma_n),
               "minEpochDays": MIN_EPOCH_DAYS,
               "minEpochSamples": MIN_EPOCH_SAMPLES,
               "maxGapDays": MAX_GAP_DAYS,
               "maxBaselineSpanDays": MAX_BASELINE_SPAN_DAYS,
               "halfPeriodSmallAmplitudeDays": T0_DAYS / 2.0,
               "fullPeriodSmallAmplitudeDays": T0_DAYS}}

    print("validation BEFORE use ...", flush=True)
    out["validation"] = validate(sigma_n)
    print(f"  V-E1 {out['validation']['V_E1']['passed']} "
          f"V-E2 primary {out['validation']['V_E2']['primaryBarPassed']} "
          f"overall {out['validation']['V_E2']['overallBarPassed']}",
          flush=True)

    print("finding epochs ...", flush=True)
    t_ep = time.time()
    all_epochs, all_epochs_arm, diags = [], [], {}
    for s in w.series:
        eps, d = find_epochs(s, sigma_n, familywise=True)
        all_epochs.extend(eps)
        diags[s.norad] = d
        arm, _ = find_epochs(s, sigma_n, familywise=False)
        all_epochs_arm.extend(arm)
    out["epochWallSeconds"] = time.time() - t_ep
    print(f"  {len(all_epochs):,} admitted epochs "
          f"({time.time() - t_ep:.0f}s)", flush=True)

    series_by_norad = {s.norad: s for s in w.series}
    watched = {s.norad: watched_runs(s) for s in w.series}
    reference_pop = {n for n, c in w.classes.items() if c == "active"} - w.never
    ref_watched = {n: watched[n] for n in reference_pop if n in watched}
    ref_days = days_map(ref_watched)
    ref_obj_days, ref_pair_days = exposure_from_days(ref_days)

    print("building trigger chains ...", flush=True)
    chains = build_chains(series_by_norad, sigma_n)

    ref_t8a = count_t8a(ref_watched, events)
    ref_t11 = count_t11(ref_watched, episodes)
    ref_trig = count_triggers(ref_watched, chains)
    out["reference"] = {
        "population": len(reference_pop),
        "watchedObjectDays": ref_obj_days,
        "watchedPairDays": ref_pair_days,
        "t8aEvents": ref_t8a, "t11Episodes": ref_t11,
        "triggerChains": ref_trig,
        "t8aRatePerObjectDay": ref_t8a / ref_obj_days if ref_obj_days else None,
        "t11RatePerPairDay": ref_t11 / ref_pair_days if ref_pair_days else None,
        "triggerRatePerObjectDay": (ref_trig / ref_obj_days
                                    if ref_obj_days else None),
        "note": ("payload class minus the v1 never-manoeuvred set, on watched "
                 "days -- days inside a run of element sets with no gap "
                 "beyond the registered catalogue gap")}

    stationed_obj_days = int(sum(int(w.stationed_days[n].size)
                                 for n in reference_pop
                                 if n in w.stationed_days))
    out["reference"]["stationedObjectDaysForComparison"] = stationed_obj_days

    def stratum_block(epochs, label):
        iv = _intervals(epochs)
        per_day = epoch_days(epochs)
        obj_days, pair_days = exposure_from_days(per_day)
        near = [e for e in epochs if abs(e["medianAbsUDeg"])
                < out["derivations"]["uStarDeg"]]
        blk = {
            "stratum": label,
            "epochs": len(epochs),
            "objects": len(iv),
            "epochDays": float(sum(e["days"] for e in epochs)),
            "epochObjectDays": obj_days,
            "pairEpochDays": pair_days,
            "epochsInsideUStar": len(near),
            "epochDaysInsideUStar": float(sum(e["days"] for e in near)),
            "medianEpochDays": (float(np.median([e["days"] for e in epochs]))
                                if epochs else None),
            "readings": {
                "t8aEvents": reading(count_t8a(iv, events), obj_days,
                                     ref_t8a, ref_obj_days),
                "t11Episodes": reading(count_t11(iv, episodes), pair_days,
                                       ref_t11, ref_pair_days),
                "triggerChains": reading(count_triggers(iv, chains), obj_days,
                                         ref_trig, ref_obj_days)},
            "secondaryReadings": {
                "t8aTransferStart": count_t8a(iv, events,
                                              anchor="transferStartMs"),
                "t8aWholeSpan": count_t8a(iv, events, anchor="span"),
                "t11Overlap": count_t11(iv, episodes, rule="overlap")},
        }
        return blk

    turn = [e for e in all_epochs if e["turnaround"]]
    quiet = [e for e in all_epochs if not e["turnaround"]]
    out["strata"] = {"ALL": stratum_block(all_epochs, "ALL"),
                     "TURN": stratum_block(turn, "TURN"),
                     "QUIET": stratum_block(quiet, "QUIET")}
    out["perBlockCadenceArm"] = stratum_block(all_epochs_arm, "ALL")
    out["perBlockCadenceArm"]["note"] = (
        "sensitivity arm: the cadence threshold applied once per block at "
        "0.10 rather than family-wise over the blocks inside the run")

    # v2 flags over the same epochs, a labelled addendum (prereg 8.3)
    v2_by_object = {}
    for s in w.series:
        ep, _f, _n = gec.v2_flags_for(s, sigma_n)
        v2_by_object[s.norad] = ep
    iv_all = _intervals(all_epochs)
    v2_in_epochs = 0
    for norad, iv in iv_all.items():
        ep = v2_by_object.get(norad)
        if ep is None:
            continue
        v2_in_epochs += int(sum(1 for t in np.asarray(ep).tolist()
                                if in_any(iv, float(t))))
    out["v2FlagsInsideAdmittedEpochs"] = {
        "count": v2_in_epochs,
        "note": ("labelled addendum: zero by construction, since a v2 flag "
                 "epoch is inadmissible; printed so the construction is "
                 "visible rather than assumed")}

    # V-E4 parity
    even = [e for e in all_epochs if e["norad"] % 2 == 0]
    odd = [e for e in all_epochs if e["norad"] % 2 == 1]
    out["V_E4ParitySplit"] = {"even": stratum_block(even, "ALL-even"),
                              "odd": stratum_block(odd, "ALL-odd"),
                              "instabilityFactor": V4_INSTABILITY_FACTOR}

    # Section 9 -- the verdict
    leak_free = []
    for st in STRATA:
        for c in CONSUMERS:
            r = out["strata"][st]["readings"][c]
            if r["verdict"] == "LEAK-FREE":
                leak_free.append({"stratum": st, "consumer": c,
                                  "exposure": r["exposure"],
                                  "meaningfulZeroExposure":
                                      r["meaningfulZeroExposure"],
                                  "leakRatio": r["leakRatio"]})
    any_evaluable = any(out["strata"][st]["readings"][c]["evaluable"]
                        for st in STRATA for c in CONSUMERS)
    out["verdict"] = {
        "exists": bool(leak_free),
        "sentence": ("a GEO epoch control EXISTS" if leak_free
                     else "a GEO epoch control DOES NOT EXIST"),
        "leakFreeReadings": leak_free,
        "readingsRegistered": len(STRATA) * len(CONSUMERS),
        "reason": (None if leak_free else
                   ("insufficient admitted exposure" if not any_evaluable
                    else "leak"))}

    v = out["validation"]
    out["gates"] = {
        "G_E1": {"registeredMeaning": "the epoch rule admits nothing",
                 "admittedEpochs": len(all_epochs),
                 "fired": bool(not all_epochs)},
        "G_E2": {"registeredMeaning": "the exposure cannot support a zero",
                 "anyEvaluableReading": any_evaluable,
                 "fired": bool(not any_evaluable)},
        "G_E3": {"registeredMeaning": "the control leaks",
                 "fired": bool(any_evaluable and not leak_free)},
        "G_E4": {"registeredMeaning": "the stratification is degenerate",
                 "turnEpochs": len(turn), "quietEpochs": len(quiet),
                 "fired": bool(not turn or not quiet)},
        "G_E5": {"registeredMeaning": ("the rules do not do what they were "
                                       "derived to do"),
                 "vE1": v["V_E1"]["passed"],
                 "vE2Primary": v["V_E2"]["primaryBarPassed"],
                 "fired": bool(not (v["V_E1"]["passed"]
                                    and v["V_E2"]["primaryBarPassed"]))},
        "G_E6": {"registeredMeaning": "the derived blind spot is material",
                 "keepersAdmittedOutsideUStar":
                     v["V_E2"]["admittedOutsideUStar"],
                 "fired": bool(v["V_E2"]["admittedOutsideUStar"] > 0)},
        "G_E7": {"registeredMeaning": "provenance", "catalogueSha256": sha,
                 "fired": False}}

    out["diagnostics"] = {
        "objects": len(w.series),
        "objectsWithCandidateRun": sum(1 for d in diags.values()
                                       if d["candidateRuns"] > 0),
        "candidateRuns": sum(d["candidateRuns"] for d in diags.values()),
        "rejectedShort": sum(d["rejectedShort"] for d in diags.values()),
        "rejectedFewSamples": sum(d["rejectedFewSamples"]
                                  for d in diags.values()),
        "rejectedCadence": sum(d["rejectedCadence"] for d in diags.values()),
        "rejectedNoBlock": sum(d["rejectedNoBlock"] for d in diags.values())}

    # ----------------------------------------------------------------
    # POST-REGISTRATION, LABELLED EVERYWHERE IT IS REPORTED. None of this
    # enters a gate, a bar or the verdict. It exists because the registered
    # readings raised two questions the registration did not register a way
    # to answer: which motions carry the leak, and whether the blind spot
    # derived in section 3.3 was derived completely.
    # ----------------------------------------------------------------
    by_object = {}
    for e in all_epochs:
        by_object.setdefault(e["norad"], []).append(e)

    def epoch_at(norad, t_ms):
        for e in by_object.get(norad, ()):
            if e["startMs"] <= t_ms <= e["endMs"]:
                return e
        return None

    leaking = []
    for ev in events:
        n = int(ev["approacherNorad"])
        a = ev.get("arrivalMs")
        if a is None:
            continue
        e = epoch_at(n, float(a))
        if e is None:
            continue
        leaking.append({
            "approacherNorad": n,
            "approacherName": w.meta.get(n, {}).get("name"),
            "class": w.classes.get(n),
            "targetNorad": int(ev["targetNorad"]),
            "targetName": w.meta.get(int(ev["targetNorad"]), {}).get("name"),
            "arrival": pp.iso(float(a)),
            "loiterDays": ev.get("loiterDays"),
            "impliedUMaxDeg": e["impliedUMaxDeg"],
            "medianAbsUDeg": e["medianAbsUDeg"],
            "epochDays": e["days"],
            "stratum": "TURN" if e["turnaround"] else "QUIET"})

    bands = ((0.0, 1.0), (1.0, 5.0), (5.0, 20.0), (20.0, 90.0))
    band_rows = []
    for lo_b, hi_b in bands:
        sel = [e for e in all_epochs
               if lo_b <= e["impliedUMaxDeg"] < hi_b]
        iv = _intervals(sel)
        pd_ = epoch_days(sel)
        od, _pr = exposure_from_days(pd_)
        band_rows.append({
            "impliedUMaxDegFrom": lo_b, "impliedUMaxDegTo": hi_b,
            "epochs": len(sel), "objects": len(iv), "epochObjectDays": od,
            "t8aEvents": count_t8a(iv, events),
            "peakRateDegPerDay": gec.peak_rate_deg_per_day(hi_b),
            "daysToCrossPointOneDegAtPeakRate":
                (0.1 / gec.peak_rate_deg_per_day(hi_b)
                 if gec.peak_rate_deg_per_day(hi_b) > 0 else None),
            "reading": reading(count_t8a(iv, events), od, ref_t8a,
                               ref_obj_days)})

    t11_inside = []
    for ep in episodes:
        ia = by_object.get(int(ep["a"]))
        ib = by_object.get(int(ep["b"]))
        if not ia or not ib:
            continue
        t0, t1 = float(ep["startMs"]), float(ep["endMs"])
        ea = next((x for x in ia if x["startMs"] <= t0 and t1 <= x["endMs"]),
                  None)
        eb = next((x for x in ib if x["startMs"] <= t0 and t1 <= x["endMs"]),
                  None)
        if ea and eb:
            t11_inside.append({
                "a": int(ep["a"]), "b": int(ep["b"]),
                "nameA": w.meta.get(int(ep["a"]), {}).get("name"),
                "nameB": w.meta.get(int(ep["b"]), {}).get("name"),
                "start": ep.get("start"), "dwellDays": ep.get("dwellDays"),
                "impliedUMaxDegA": ea["impliedUMaxDeg"],
                "impliedUMaxDegB": eb["impliedUMaxDeg"],
                "stratumA": "TURN" if ea["turnaround"] else "QUIET",
                "stratumB": "TURN" if eb["turnaround"] else "QUIET"})

    ratio_u = ((SIGMA_K * sigma_n)
               / (A_DEG_PER_DAY2 * EW_PERIOD_DAYS / 2.0))
    out["postRegistrationDiagnostics"] = {
        "label": ("post-registration, labelled; enters no gate, no bar and "
                  "not the verdict"),
        "t8aEventsInsideAdmittedEpochs": leaking,
        "leakByImpliedAmplitudeBand": band_rows,
        "t11EpisodesInsideAdmittedEpochs": t11_inside,
        "classOfAdmittedObjects": {
            "active": sum(1 for n in by_object
                          if w.classes.get(n) == "active"),
            "passive": sum(1 for n in by_object
                           if w.classes.get(n) == "passive"),
            "unknown": sum(1 for n in by_object
                           if w.classes.get(n) is None)},
        "blindBandCompleted": {
            "registeredDerivation": ("section 3.3 solved |sin 2u| > ratio "
                                     "for u near 0 only"),
            "theAccelerationAlsoVanishesAt": 90.0,
            "ratio": ratio_u,
            "bandNearStableDeg": [0.0, u_star_deg(sigma_n)],
            "bandNearUnstableDeg": [90.0 - u_star_deg(sigma_n), 90.0],
            "fractionOfLongitudeInEitherBand":
                8.0 * u_star_deg(sigma_n) / 360.0}}

    out["sourceSha256"] = {
        "tools/geo_epoch_control.py": pg.sha256_file(Path(__file__))}
    out["wallSeconds"] = time.time() - started
    return out, all_epochs


def write_epochs(path, epochs, meta):
    with Path(path).open("w") as fh:
        fh.write(json.dumps(meta, default=pp._json_default) + "\n")
        for e in sorted(epochs, key=lambda r: (r["startMs"], r["norad"])):
            row = {k: v for k, v in e.items() if k not in ("i0", "i1")}
            fh.write(json.dumps(row, default=pp._json_default) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, default=None)
    ap.add_argument("--work", type=Path,
                    default=_REPO / "runtime" / "proximity-geo")
    ap.add_argument("--docs", type=Path, default=_REPO / "docs")
    ap.add_argument("--out", type=Path, default=_REPO / "docs")
    ap.add_argument("--date", default="20260922")
    args = ap.parse_args(argv)

    db = orbit_campaigns.open_archive_for_reading(args.archive)
    db.execute("PRAGMA query_only=1")
    archive_path = next(r[2] for r in db.execute("PRAGMA database_list")
                        if r[1] == "main")
    print("building world ...", flush=True)
    w = pp.build_world(db, args.work)
    print(f"  {len(w.series):,} objects, sigma_n {w.sigma_n:.7f}, "
          f"{w.buildSeconds:.0f}s", flush=True)
    out, epochs = analyze(db, archive_path, w, args)
    receipt = args.out / f"geo-libration-epoch-control-{args.date}-receipt.json"
    receipt.write_text(json.dumps(out, indent=1, default=pp._json_default)
                       + "\n")
    write_epochs(args.out / f"geo-libration-epochs-{args.date}.jsonl", epochs,
                 {"schema": 1, "record": "provenance",
                  "study": "GEO free-libration epochs",
                  "registration": REGISTRATION,
                  "archive": out["archive"], "extract": out["extract"],
                  "derivations": out["derivations"]})
    print(json.dumps({
        "verdict": out["verdict"]["sentence"],
        "strata": {k: {"epochs": v["epochs"], "objects": v["objects"],
                       "epochObjectDays": v["epochObjectDays"],
                       "pairEpochDays": v["pairEpochDays"],
                       "readings": {c: v["readings"][c]["verdict"]
                                    for c in CONSUMERS}}
                   for k, v in out["strata"].items()},
        "gates": {k: g["fired"] for k, g in out["gates"].items()}},
        indent=1, default=pp._json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
