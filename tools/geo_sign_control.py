#!/usr/bin/env python3
"""T28 -- a GEO control built from the ramp-sign-versus-slot-side test.

Registration: docs/t28-geo-sign-control-preregistration-20260923.md, committed
ALONE at b56c8b6 before this file existed.

THE CLASSIFIER, in one paragraph. A flagged drift change either runs WITH the
local triaxial acceleration, which is what free motion does, or AGAINST it,
which is what holding a longitude box does. T22 measured that separation and
registered no operating point. This module turns it into one: an interval of a
history is admitted only when k consecutive flagged drift changes all carry the
free sign, when the libration half-amplitude the first integral implies over
those k chains exceeds the value at which a consumer's own dwell criterion
becomes kinematically unreachable, and when the whole thing sits inside a T8e
free-libration epoch. The interval asserted runs FORWARD from the last chain of
the evidence, so no consumer event is counted from the chains that admitted it.

IMPORTED, NOT REIMPLEMENTED. The epoch rule, the v1 flag rule, the chain rule,
the acceleration constant, the stable longitudes, the first integral, the leak
arithmetic and both synthetic generators all come from the modules that own
them; the test suite reads this file's source and fails if any of those names
is redefined here.

CPU only. No GPU is taken, so no gpu-consumers.json row is owed.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import geo_epoch_control as gce                     # noqa: E402
from tools import geo_passive_control as gec                   # noqa: E402
from tools import persistent_pairs as pp                       # noqa: E402
from tools import proximity_geo as pg                          # noqa: E402
from tools import trigger_alarm as ta                          # noqa: E402
from pipeline import orbit_campaigns                           # noqa: E402

DAY_MS = pp.DAY_MS
REGISTRATION = "docs/t28-geo-sign-control-preregistration-20260923.md"
REGISTRATION_COMMIT = "b56c8b6"

# --------------------------------------------------------------------------
# Registration 1 and 3.1 -- constants, imported and never retyped
# --------------------------------------------------------------------------
A_DEG_PER_DAY2 = gec.A_DEG_PER_DAY2
BASELINE_SAMPLES = gec.BASELINE_SAMPLES                        # 10
MAX_GAP_DAYS = pg.MAX_GAP_DAYS                                 # 5.0
EW_PERIOD_DAYS = gec.EW_PERIOD_DAYS                            # 14.00
SIGMA_K = gec.SIGMA_K                                          # 5
LEAK_BAR = gce.LEAK_BAR                                        # 0.10
HORIZON_DAYS = pg.T_LOOK_DAYS                                  # 180.0
V1_FLOOR_DEG_PER_DAY = pg.BURN_FLOOR_DEG_PER_DAY               # 0.010

# Registration 3.4 -- each consumer's own dwell criterion
T8A_X_DEG = pg.X_PRIMARY_DEG                                   # 0.1
T8A_D_DAYS = pg.D_PRIMARY_DAYS                                 # 30.0
T11_X_DEG = pp.X_PAIR_PRIMARY_DEG                              # 0.041667...
T11_D_DAYS = pp.D_PAIR_PRIMARY_DAYS                            # 56.00

# Registration 3.5
K_CANDIDATES = (1, 2, 3, 4, 5, 6)
Q_BAR = 0.01
T22_CARRIER_SIGN_FRACTION = 0.8294        # T22 7.3, for the p^k column only

SEED_LIBRATOR = gce.SEED_LIBRATOR                              # 20260922
SEED_KEEPER = gce.SEED_KEEPER                                  # 20260923
VALIDATION_OBJECTS = gec.VALIDATION_OBJECTS                    # 200

ARMS = ("A-NOAMP", "B-AMP", "C-AMP-CADENCE")
PRIMARY_ARM = "B-AMP"
CONSUMERS = gce.CONSUMERS
CATALOGUE_SHA256 = gec.CATALOGUE_SHA256

FREE, KEEPER, UNEVALUABLE = "free", "keeper", "unevaluable"


# ==========================================================================
# Registration 3.3 -- the completed, two-sided blind band
# ==========================================================================
def blind_band_ratio(sigma_n):
    """|sin 2u| below which a keeping burn at the measured cycle sits under
    the measured noise floor: 5 sigma_n / (A T / 2)."""
    return (SIGMA_K * float(sigma_n)) / (A_DEG_PER_DAY2 * EW_PERIOD_DAYS / 2.0)


def u_star_deg(sigma_n):
    r = blind_band_ratio(sigma_n)
    if r >= 1.0:
        return 45.0
    return 0.5 * math.degrees(math.asin(r))


def sign_evaluable(u_deg, sigma_n):
    """Registration 3.3: evaluable when |sin 2u| >= r, which excludes BOTH
    the stable and the unstable neighbourhood."""
    r = blind_band_ratio(sigma_n)
    return np.abs(np.sin(2.0 * np.radians(np.asarray(u_deg,
                                                     dtype=np.float64)))) >= r


# ==========================================================================
# Registration 3.4 -- the amplitude clause, derived from a dwell criterion
# ==========================================================================
def dwell_amplitude_deg(x_deg, d_days, acceleration=A_DEG_PER_DAY2):
    """The half-amplitude above which a free librator cannot stay inside
    `x_deg` of a FIXED longitude for `d_days`.

    At the turning point lambda'' = -A sin 2u_max and, to second order,
    dlambda = 0.5 A |sin 2u_max| t^2 about it. Requiring dlambda <= x at
    t = d/2 gives |sin 2u_max| <= 2 x / (A (d/2)^2).
    """
    half = float(d_days) / 2.0
    ratio = 2.0 * float(x_deg) / (float(acceleration) * half * half)
    if ratio >= 1.0:
        return 90.0
    return 0.5 * math.degrees(math.asin(ratio))


U_DWELL_DEG = dwell_amplitude_deg(T8A_X_DEG, T8A_D_DAYS)       # 15.755490
# T11's box was built from pp's own rounded acceleration (1.7006e-3), which
# differs from pg.LAMBDA_DDOT_MAX in the fifth significant figure. The bound is
# derived with the constant that built the box, so the derivation is internally
# consistent; the discrepancy is printed in the receipt and enters no decision.
T11_A_DEG_PER_DAY2 = pp.A_LONGITUDE_MAX_DEG_PER_DAY2
U_T11_DEG = dwell_amplitude_deg(T11_X_DEG, T11_D_DAYS,
                                acceleration=T11_A_DEG_PER_DAY2)


def dwell_excursion_deg(u_max_deg, t_days, acceleration=A_DEG_PER_DAY2):
    """The second-order excursion from the turning point, for the proofs."""
    return (0.5 * float(acceleration)
            * abs(math.sin(2.0 * math.radians(float(u_max_deg))))
            * float(t_days) ** 2)


# ==========================================================================
# Registration 3.2 -- the sign of one chain
# ==========================================================================
def chain_signs(series, sigma_n):
    """Every T8d flag chain on one object, with its free/keeper/unevaluable
    sign read from the ten-sample baseline window T8a's own flag rule used.

    Returns a list of dicts in time order. `flag_baselines` and `chain_flags`
    are imported; only the baseline-window LONGITUDE is computed here, by the
    same window arithmetic, because T8a's rule keeps the baseline drift and
    not the baseline longitude.
    """
    flags, sizes, bases = ta.flag_baselines(series, sigma_n)
    chains = ta.chain_flags(flags, sizes, bases)
    if not chains:
        return [], chains
    epoch = np.asarray(series.epoch_ms, dtype=np.float64)
    lam_u = np.asarray(series.lam_unwrapped, dtype=np.float64)
    w = BASELINE_SAMPLES
    out = []
    for t_first, t_trig, stages, drift_change, drift_base in chains:
        j = int(np.searchsorted(epoch, t_trig, side="left"))
        if j < w or j >= epoch.size:
            out.append({"tFirstMs": float(t_first), "tTrigMs": float(t_trig),
                        "stages": int(stages),
                        "driftChangeDegPerDay": float(drift_change),
                        "sign": UNEVALUABLE, "reason": "no-baseline-window",
                        "lamBaseDeg": None, "uBaseDeg": None,
                        "absSin2u": None, "index": j})
            continue
        lam_base = float(np.median(lam_u[j - w:j]))
        lam_wrapped = float(pg.wrap180(np.asarray([lam_base]))[0])
        _stable, u_b = gec.nearest_stable(np.asarray([lam_wrapped]))
        u_b = float(np.asarray(u_b).ravel()[0])
        abs_sin = abs(math.sin(2.0 * math.radians(u_b)))
        acc = float(gec.free_acceleration(np.asarray([lam_wrapped]))[0])
        if abs_sin < blind_band_ratio(sigma_n) or acc == 0.0:
            sign, reason = UNEVALUABLE, "blind-band"
        elif math.copysign(1.0, drift_change) == math.copysign(1.0, acc):
            sign, reason = FREE, None
        else:
            sign, reason = KEEPER, None
        out.append({"tFirstMs": float(t_first), "tTrigMs": float(t_trig),
                    "stages": int(stages),
                    "driftChangeDegPerDay": float(drift_change),
                    "sign": sign, "reason": reason,
                    "lamBaseDeg": lam_wrapped, "uBaseDeg": u_b,
                    "absSin2u": abs_sin, "index": j})
    return out, chains


# ==========================================================================
# Registration 3.5 -- persistence, measured before it is used
# ==========================================================================
def run_length_profile(sign_lists):
    """Over a population: the marginal free-sign fraction, the conditional
    P(next free | this free), the run-length histogram, and q_k -- the
    fraction of k-consecutive chain windows in which EVERY chain is free."""
    total = 0
    free = 0
    pairs = 0
    pairs_free_free = 0
    pairs_first_free = 0
    runs = {}
    q_num = {k: 0 for k in K_CANDIDATES}
    q_den = {k: 0 for k in K_CANDIDATES}
    for signs in sign_lists:
        seq = [c["sign"] for c in signs]
        total += len(seq)
        free += sum(1 for s in seq if s == FREE)
        for a, b in zip(seq[:-1], seq[1:]):
            pairs += 1
            if a == FREE:
                pairs_first_free += 1
                if b == FREE:
                    pairs_free_free += 1
        run = 0
        for s in seq + [None]:
            if s == FREE:
                run += 1
            else:
                if run:
                    runs[run] = runs.get(run, 0) + 1
                run = 0
        for k in K_CANDIDATES:
            if len(seq) < k:
                continue
            for i in range(len(seq) - k + 1):
                q_den[k] += 1
                if all(x == FREE for x in seq[i:i + k]):
                    q_num[k] += 1
    p = (free / total) if total else float("nan")
    p_keeper_false = 1.0 - T22_CARRIER_SIGN_FRACTION
    out = {
        "chains": total, "freeSignChains": free,
        "freeSignFraction": p,
        "chainPairs": pairs,
        "conditionalFreeGivenFree": (pairs_free_free / pairs_first_free
                                     if pairs_first_free else float("nan")),
        "runLengthHistogram": {str(k): v for k, v in sorted(runs.items())},
        "qK": {}, "independenceModelPK": {},
        "note": ("q_k is measured; p^k is the independence model from T22's "
                 "0.8294, printed beside it so the cost of dependence is "
                 "visible"),
    }
    for k in K_CANDIDATES:
        q = (q_num[k] / q_den[k]) if q_den[k] else float("nan")
        lo, hi = pp.clopper_pearson(q_num[k], q_den[k]) if q_den[k] else (
            float("nan"), float("nan"))
        out["qK"][str(k)] = {"windows": q_den[k], "allFree": q_num[k],
                             "q": q, "ci95": [lo, hi]}
        out["independenceModelPK"][str(k)] = p_keeper_false ** k
    return out


def choose_k(profile, bar=Q_BAR):
    """Registration 3.5: the smallest k in 1..6 whose MEASURED q_k <= bar."""
    for k in K_CANDIDATES:
        q = profile["qK"][str(k)]["q"]
        if np.isfinite(q) and q <= bar:
            return k, False
    return K_CANDIDATES[-1], True


# ==========================================================================
# Registration 4 -- the classifier
# ==========================================================================
def _baseline_offsets(epoch_ms):
    """dt_i = t_i - median(t_{i-10..i-1}), the reach of v1's own baseline."""
    t = np.asarray(epoch_ms, dtype=np.float64) / DAY_MS
    n = t.size
    w = BASELINE_SAMPLES
    dt = np.full(n, np.nan)
    if n < w + 1:
        return dt
    sw = np.lib.stride_tricks.sliding_window_view
    tcen = np.median(sw(t[:n - 1], w)[:n - w], axis=1)
    dt[w:] = t[w:] - tcen
    return dt


def cadence_limit_days(abs_sin_2u):
    """Registration 4.4: the baseline reach at which free motion at this
    amplitude could trip v1's floor. dt < floor / (A |sin 2u|)."""
    s = float(abs_sin_2u)
    if s <= 0.0:
        return float("inf")
    return V1_FLOOR_DEG_PER_DAY / (A_DEG_PER_DAY2 * s)


def classify_object(series, sigma_n, k, arm, epochs=None, signs=None,
                    horizon_days=None):
    """Every asserted interval of one object under one arm.

    Returns (intervals, diagnostics). Each interval is a dict carrying the
    evidence that admitted it. Nothing here reads a catalogue class, a name or
    a motive.
    """
    use_amp = arm in ("B-AMP", "C-AMP-CADENCE")
    use_cadence = arm == "C-AMP-CADENCE"
    if signs is None:
        signs, _ = chain_signs(series, sigma_n)
    if epochs is None:
        epochs, _diag = gce.find_epochs(series, sigma_n, familywise=True)

    t_ms = np.asarray(series.epoch_ms, dtype=np.float64)
    diag = {"epochs": len(epochs), "chains": len(signs),
            "noEpoch": 0, "catalogueGap": 0, "tooFewChains": 0,
            "keeperSign": 0, "unevaluableSign": 0, "amplitude": 0,
            "admitted": 0, "cadenceTruncated": 0}

    if not epochs:
        if t_ms.size >= 2 and float(np.median(np.diff(t_ms))) / DAY_MS > MAX_GAP_DAYS:
            diag["catalogueGap"] += 1
            diag["unclassifiableReason"] = "catalogue-gap"
        else:
            diag["noEpoch"] += 1
            diag["unclassifiableReason"] = "no-epoch"
        return [], diag

    lam = np.asarray(series.lam, dtype=np.float64)
    drift = np.asarray(series.drift, dtype=np.float64)
    s_all, u_all, _stable = gce.implied_s(lam, drift)
    dt_all = _baseline_offsets(t_ms)

    out = []
    for ep in epochs:
        inside = [c for c in signs
                  if ep["startMs"] <= c["tTrigMs"] <= ep["endMs"]]
        if len(inside) < k:
            diag["tooFewChains"] += 1
            continue
        run = []
        admitted_here = 0
        i = 0
        while i < len(inside):
            c = inside[i]
            if c["sign"] == FREE:
                run.append(c)
            else:
                if c["sign"] == KEEPER:
                    diag["keeperSign"] += 1
                else:
                    diag["unevaluableSign"] += 1
                run = []
                i += 1
                continue
            if len(run) < k:
                i += 1
                continue
            window = run[-k:]
            i0 = int(np.searchsorted(t_ms, window[0]["tTrigMs"], side="left"))
            i1 = int(np.searchsorted(t_ms, window[-1]["tTrigMs"], side="right"))
            seg = s_all[i0:max(i1, i0 + 1)]
            u_max = float(gce.implied_u_max_deg(np.nanmax(seg))) if seg.size \
                else float("nan")
            abs_sin = abs(math.sin(2.0 * math.radians(min(u_max, 90.0)))) \
                if np.isfinite(u_max) else 0.0
            if use_amp and not (np.isfinite(u_max) and u_max > U_DWELL_DEG):
                diag["amplitude"] += 1
                i += 1
                continue

            # Registration 4.1: the assertion runs FORWARD from the evidence.
            # It begins at the first element set STRICTLY AFTER t_trig(c_k),
            # so that no consumer event at or before the evidence is counted.
            evidence_end = float(window[-1]["tTrigMs"])
            j_start = int(np.searchsorted(t_ms, evidence_end, side="right"))
            if j_start >= t_ms.size:
                i += 1
                continue
            start = float(t_ms[j_start])
            end = float(ep["endMs"])
            terminator = None
            for later in inside:
                if later["tTrigMs"] > start and later["sign"] == KEEPER:
                    end = min(end, float(later["tFirstMs"]))
                    terminator = "keeper-sign-chain"
                    break
            if horizon_days is not None:
                end = min(end, start + float(horizon_days) * DAY_MS)
                if terminator is None:
                    terminator = "horizon"
            if use_cadence:
                limit = cadence_limit_days(abs_sin)
                j0 = int(np.searchsorted(t_ms, start, side="right"))
                j1 = int(np.searchsorted(t_ms, end, side="right"))
                bad = np.where(np.isfinite(dt_all[j0:j1])
                               & (dt_all[j0:j1] >= limit))[0]
                if bad.size:
                    end = float(t_ms[j0 + int(bad[0])])
                    terminator = "cadence"
                    diag["cadenceTruncated"] += 1
            if not (end > start):
                i += 1
                continue
            out.append({
                "norad": int(series.norad),
                "startMs": start, "endMs": end,
                "days": (end - start) / DAY_MS,
                "evidenceStartMs": float(window[0]["tTrigMs"]),
                "evidenceEndMs": evidence_end,
                "evidenceChains": k,
                "impliedUMaxDeg": u_max,
                "epochStartMs": float(ep["startMs"]),
                "epochEndMs": float(ep["endMs"]),
                "epochImpliedUMaxDeg": ep["impliedUMaxDeg"],
                "terminator": terminator or "epoch-end",
                "arm": arm,
            })
            admitted_here += 1
            diag["admitted"] += 1
            # the assertion has been made; resume scanning after the interval
            nxt = i + 1
            while nxt < len(inside) and inside[nxt]["tTrigMs"] <= end:
                nxt += 1
            run = []
            i = nxt
            continue
        if admitted_here == 0:
            pass
    return out, diag


# ==========================================================================
# Exposure and the readings -- imported arithmetic
# ==========================================================================
def _intervals(rows):
    out = {}
    for r in rows:
        out.setdefault(int(r["norad"]), []).append((r["startMs"], r["endMs"]))
    return out


def exposure_of(rows):
    per_day = {}
    for r in rows:
        a = int(math.ceil(r["startMs"] / DAY_MS))
        b = int(math.floor(r["endMs"] / DAY_MS))
        for d in range(a, b + 1):
            per_day.setdefault(d, set()).add(int(r["norad"]))
    return gce.exposure_from_days(per_day)


def arm_block(rows, label, events, episodes, chains, ref):
    iv = _intervals(rows)
    obj_days, pair_days = exposure_of(rows)
    n_t8a = gce.count_t8a(iv, events)
    n_t11 = gce.count_t11(iv, episodes)
    n_trig = gce.count_triggers(iv, chains)
    return {
        "arm": label,
        "intervals": len(rows),
        "objects": len(iv),
        "assertedDays": float(sum(r["days"] for r in rows)),
        "objectDays": obj_days,
        "pairDays": pair_days,
        "medianIntervalDays": (float(np.median([r["days"] for r in rows]))
                               if rows else None),
        "readings": {
            "t8aEvents": gce.reading(n_t8a, obj_days, ref["t8aEvents"],
                                     ref["objectDays"]),
            "t11Episodes": gce.reading(n_t11, pair_days, ref["t11Episodes"],
                                       ref["pairDays"]),
            "triggerChains": gce.reading(n_trig, obj_days,
                                         ref["triggerChains"],
                                         ref["objectDays"])},
        "secondaryReadings": {
            "t8aTransferStart": gce.count_t8a(iv, events,
                                              anchor="transferStartMs"),
            "t8aWholeSpan": gce.count_t8a(iv, events, anchor="span"),
            "t11Overlap": gce.count_t11(iv, episodes, rule="overlap")},
    }


# ==========================================================================
# Registration 6 -- validation BEFORE use
# ==========================================================================
def librator_amplitudes(seed, n=VALIDATION_OBJECTS):
    """The u_max `synthetic_librators` draws, by the same call order."""
    rng = np.random.default_rng(seed)
    return rng.uniform(1.0, 60.0, size=n)


def _signed_keeper(norad, slot_deg, years=8.0, sigma_n=None, seed=20260923):
    """A sawtooth about one slot whose ramp follows the SIGN of the triaxial
    acceleration there, so every burn carries the keeper sign."""
    ramp = float(gec.free_acceleration(np.asarray([slot_deg]))[0])
    half = abs(ramp) * gec.EW_PERIOD_DAYS / 4.0
    t = np.arange(0.0, years * 365.25, gec.SAMPLE_SPACING_DAYS)
    cycle = np.mod(t, gec.EW_PERIOD_DAYS)
    d = -math.copysign(half, ramp) + ramp * cycle
    lam = slot_deg + np.cumsum(d - np.mean(d)) * gec.SAMPLE_SPACING_DAYS
    if sigma_n:
        d = d + np.random.default_rng(seed).normal(0.0, sigma_n, size=d.size)
    return gec._SynSeries(norad, (t + 20000.0) * DAY_MS, pg.wrap180(lam), d)


def _slow_librator(norad, u_max_deg, years=20.0, spacing_days=None,
                   sigma_n=None, seed=20260923):
    """One free librator at a chosen half-amplitude, integrated by the
    generator T11b owns, optionally re-sampled at a chosen spacing."""
    ts, us, vs = gec._integrate_librators(np.asarray([0.0]),
                                          np.asarray([
                                              math.sqrt(2.0 * gec.A_RAD_PER_DAY2)
                                              * math.sin(math.radians(u_max_deg))]),
                                          years * 365.25)
    lam = np.degrees(us[:, 0]) + gec.STABLE_LONGITUDES_DEG[0]
    drift = np.degrees(vs[:, 0])
    t = np.asarray(ts, dtype=np.float64)
    if spacing_days is not None:
        step = max(1, int(round(spacing_days / gec.SAMPLE_SPACING_DAYS)))
        t, lam, drift = t[::step], lam[::step], drift[::step]
    if sigma_n:
        rng = np.random.default_rng(seed)
        drift = drift + rng.normal(0.0, sigma_n, size=drift.size)
    return gec._SynSeries(norad, (t + 20000.0) * DAY_MS,
                          pg.wrap180(lam), drift)


def validate(sigma_n, k):
    t0 = time.time()
    out = {"k": k, "uStarDeg": u_star_deg(sigma_n),
           "blindBandRatio": blind_band_ratio(sigma_n),
           "uDwellDeg": U_DWELL_DEG, "uT11Deg": U_T11_DEG}

    # ---- V1: synthetic free librators must be ADMITTED -------------------
    lib = gec.synthetic_librators(SEED_LIBRATOR, sigma_n=sigma_n)
    u_true = librator_amplitudes(SEED_LIBRATOR, len(lib))
    eligible, admitted_elig, rejected_by_sign, reasons = 0, 0, 0, {}
    sign_fracs = []
    for j, s in enumerate(lib):
        signs, _ = chain_signs(s, sigma_n)
        epochs, _d = gce.find_epochs(s, sigma_n, familywise=True)
        rows, diag = classify_object(s, sigma_n, k, "B-AMP",
                                     epochs=epochs, signs=signs)
        ev = [c for c in signs if c["sign"] != UNEVALUABLE]
        if ev:
            sign_fracs.append(sum(1 for c in ev if c["sign"] == FREE) / len(ev))
        if u_true[j] <= U_DWELL_DEG:
            continue
        eligible += 1
        if rows:
            admitted_elig += 1
            continue
        enough = any(len([c for c in signs
                          if e["startMs"] <= c["tTrigMs"] <= e["endMs"]]) >= k
                     for e in epochs)
        if enough and diag["admitted"] == 0 and diag["amplitude"] == 0:
            rejected_by_sign += 1
            why = "clause-a-sign"
        elif diag["amplitude"] > 0:
            why = "clause-b-amplitude"
        elif not epochs:
            why = diag.get("unclassifiableReason", "no-epoch")
        else:
            why = "too-few-chains"
        reasons[why] = reasons.get(why, 0) + 1
    out["V1"] = {
        "objects": len(lib), "eligible": eligible,
        "admittedEligible": admitted_elig,
        "admittedEligibleFraction": (admitted_elig / eligible
                                     if eligible else float("nan")),
        "rejectedByClauseA": rejected_by_sign,
        "hardBar": 0, "hardBarPassed": bool(rejected_by_sign == 0),
        "admissionBar": 0.80,
        "admissionBarPassed": bool(eligible and
                                   admitted_elig / eligible >= 0.80),
        "rejectionReasons": reasons,
        "unattributedRejections": int(eligible - admitted_elig
                                      - sum(reasons.values())),
        "pooledFreeSignFractionOnLibrators": (float(np.mean(sign_fracs))
                                              if sign_fracs else None),
    }

    # ---- V2: synthetic station-keepers must be EXCLUDED -------------------
    keep = gec.synthetic_keepers(SEED_KEEPER, sigma_n=sigma_n,
                                 self_consistent=True)
    slots = gce.keeper_slots(SEED_KEEPER, len(keep))
    _st, u_slot = gec.nearest_stable(slots)
    ustar = out["uStarDeg"]
    outside = [j for j in range(len(keep))
               if ustar <= abs(float(u_slot[j])) <= 90.0 - ustar]
    admitted_out, admitted_in, rows_admitted = 0, 0, []
    for j, s in enumerate(keep):
        rows, _d = classify_object(s, sigma_n, k, "B-AMP")
        if not rows:
            continue
        inside_band = j not in outside
        if inside_band:
            admitted_in += 1
        else:
            admitted_out += 1
        rows_admitted.append({"index": j, "slotDeg": float(slots[j]),
                              "absUSlotDeg": abs(float(u_slot[j])),
                              "insideBlindBand": inside_band,
                              "intervals": len(rows)})
    out["V2"] = {
        "objects": len(keep), "outsideBlindBand": len(outside),
        "admittedOutsideBlindBand": admitted_out,
        "admittedInsideBlindBand": admitted_in,
        "excludedOutsideFraction": ((len(outside) - admitted_out) / len(outside)
                                    if outside else float("nan")),
        "bar": 1.0,
        "passed": bool(admitted_out == 0),
        "admittedKeepers": rows_admitted}

    # labelled addendum, discovered during the proofs: the imported generator
    # ramps at |acc(slot)| regardless of the SIGN of acc, so at a slot where
    # acc < 0 its sawtooth ramps the way free motion would not and its burns
    # carry the FREE sign. A physically self-consistent keeper ramps WITH the
    # acceleration and burns AGAINST it. Both are reported.
    signed = [_signed_keeper(820000 + j, float(slots[j]), sigma_n=sigma_n)
              for j in range(len(keep))]
    adm_signed = 0
    for j, s in enumerate(signed):
        rows, _d = classify_object(s, sigma_n, k, "B-AMP")
        if rows and ustar <= abs(float(u_slot[j])) <= 90.0 - ustar:
            adm_signed += 1
    out["V2_signedRamp"] = {
        "objects": len(signed), "admittedOutsideBlindBand": adm_signed,
        "passed": bool(adm_signed == 0),
        "note": ("labelled addendum: the ramp follows the SIGN of the "
                 "acceleration at the object's own slot, so every burn "
                 "carries the keeper sign by construction")}

    # labelled arm: maximum-ramp keepers
    keep_max = gec.synthetic_keepers(SEED_KEEPER, sigma_n=sigma_n,
                                     self_consistent=False)
    adm_max = sum(1 for s in keep_max
                  if classify_object(s, sigma_n, k, "B-AMP")[0])
    out["V2_maxRamp"] = {"objects": len(keep_max), "admitted": adm_max,
                         "note": ("labelled arm: the ramp rate is the maximum "
                                  "triaxial acceleration rather than the "
                                  "acceleration at the object's own slot")}

    # ---- V3: the T8e leak case, split bar --------------------------------
    slow = _slow_librator(910001, 3.5, sigma_n=sigma_n)
    signs_slow, _ = chain_signs(slow, sigma_n)
    ev_slow = [c for c in signs_slow if c["sign"] != UNEVALUABLE]
    rows_a, diag_a = classify_object(slow, sigma_n, k, "A-NOAMP")
    rows_b, diag_b = classify_object(slow, sigma_n, k, "B-AMP")
    label_b = ("EXCLUDED-BY-AMPLITUDE" if (not rows_b and diag_b["amplitude"])
               else ("ADMITTED" if rows_b else "EXCLUDED-OTHER"))
    out["V3"] = {
        "uMaxDeg": 3.5, "chains": len(signs_slow),
        "evaluableChains": len(ev_slow),
        "freeSignChains": sum(1 for c in ev_slow if c["sign"] == FREE),
        "keeperSignChains": sum(1 for c in ev_slow if c["sign"] == KEEPER),
        "armA": {"intervals": len(rows_a), "diag": diag_a},
        "whyRefused": ("too-few-chains" if diag_a["tooFewChains"] and not rows_a
                       else ("keeper-sign" if diag_a["keeperSign"] and not rows_a
                             else ("no-epoch" if diag_a["epochs"] == 0
                                   else None))),
        "armB": {"intervals": len(rows_b), "label": label_b,
                 "diag": diag_b},
        "calledControlled": bool(diag_a["admitted"] == 0
                                 and diag_a["keeperSign"] > 0
                                 and not rows_a),
        "armAAdmitsBar": True,
        "armAAdmits": bool(rows_a),
        "amplitudeLabelCorrect": bool(label_b == "EXCLUDED-BY-AMPLITUDE"
                                      or bool(rows_b)),
        "passed": bool(bool(rows_a)
                       and (label_b == "EXCLUDED-BY-AMPLITUDE" or bool(rows_b)))}

    # ---- V4: the sparse librator ------------------------------------------
    sparse = _slow_librator(910002, 30.0, spacing_days=10.0, sigma_n=sigma_n)
    dense = _slow_librator(910003, 30.0, spacing_days=2.0, sigma_n=sigma_n)
    rows_s, diag_s = classify_object(sparse, sigma_n, k, "B-AMP")
    rows_d, diag_d = classify_object(dense, sigma_n, k, "B-AMP")
    out["V4"] = {
        "sparse": {"spacingDays": 10.0, "intervals": len(rows_s),
                   "reason": diag_s.get("unclassifiableReason"),
                   "epochs": diag_s["epochs"]},
        "dense": {"spacingDays": 2.0, "intervals": len(rows_d),
                  "epochs": diag_d["epochs"],
                  "reason": diag_d.get("unclassifiableReason")},
        "passed": bool(not rows_s
                       and diag_s.get("unclassifiableReason") == "catalogue-gap"
                       and diag_d["epochs"] > 0)}
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


def rescore_class_one(ledger_path, certified_keys):
    spoken, resolutions = {}, {}
    with open(ledger_path) as fh:
        for line in fh:
            row = json.loads(line)
            kind = row.get("record")
            if kind == "assessment" and row.get("spoken") and row.get("class") == 1:
                spoken[row["alertId"]] = row
            elif kind == "resolution":
                resolutions[row["alertId"]] = row
    before_n = len(spoken)
    before_k = sum(1 for aid in spoken
                   if resolutions.get(aid, {}).get("state") == "arrival")
    removed, removed_hits, kept_n, kept_k = 0, 0, 0, 0
    for aid, row in spoken.items():
        key = (int(row["norad"]), int(round(float(row["tTrigMs"]))))
        hit = resolutions.get(aid, {}).get("state") == "arrival"
        if key in certified_keys:
            removed += 1
            removed_hits += int(hit)
        else:
            kept_n += 1
            kept_k += int(hit)
    lo0, hi0 = pp.wilson(before_k, before_n)
    lo1, hi1 = pp.wilson(kept_k, kept_n)
    p0 = (before_k / before_n) if before_n else float("nan")
    p1 = (kept_k / kept_n) if kept_n else float("nan")
    return {"before": {"hits": before_k, "alerts": before_n, "precision": p0,
                       "wilson95": [lo0, hi0]},
            "after": {"hits": kept_k, "alerts": kept_n, "precision": p1,
                      "wilson95": [lo1, hi1]},
            "removed": removed, "removedHits": removed_hits}


def analyze(db, archive_path, w, args):
    started = time.time()
    cat = args.docs / "persistent-pairs-20260922.jsonl"
    sha = pg.sha256_file(cat)
    if sha != CATALOGUE_SHA256:
        raise SystemExit("GATE G-S7: the T11 catalogue pin does not match. "
                         f"{sha} != {CATALOGUE_SHA256}")
    episodes = load_jsonl(cat)
    t8a_path = args.docs / "proximity-events-20260922.jsonl"
    events = load_jsonl(t8a_path)
    sigma_n = w.sigma_n

    out = {"schema": 1,
           "measuredAt": datetime.now(timezone.utc).isoformat(),
           "registration": REGISTRATION,
           "registrationCommit": REGISTRATION_COMMIT,
           "host": socket.gethostname(), "executionMode": "cpu",
           "gpuConsumersRowOwed": False,
           "archive": pp._archive_meta(db, archive_path),
           "extract": w.extractMeta,
           "inputs": {"catalogue": cat.name, "catalogueSha256": sha,
                      "episodes": len(episodes),
                      "t8aCatalogue": t8a_path.name,
                      "t8aCatalogueSha256": pg.sha256_file(t8a_path),
                      "t8aEvents": len(events)},
           "derivations": {
               "aDegPerDay2": A_DEG_PER_DAY2,
               "sigmaNDegPerDay": sigma_n,
               "blindBandRatio": blind_band_ratio(sigma_n),
               "uStarDeg": u_star_deg(sigma_n),
               "blindBandUpperDeg": 90.0 - u_star_deg(sigma_n),
               "blindBandFractionOfLongitude":
                   8.0 * u_star_deg(sigma_n) / 360.0,
               "uDwellDeg": U_DWELL_DEG,
               "uT11Deg": U_T11_DEG,
               "uT11AccelerationUsed": T11_A_DEG_PER_DAY2,
               "uT11WithPgAcceleration": dwell_amplitude_deg(
                   T11_X_DEG, T11_D_DAYS, acceleration=A_DEG_PER_DAY2),
               "t8aXDeg": T8A_X_DEG, "t8aDDays": T8A_D_DAYS,
               "t11XDeg": T11_X_DEG, "t11DDays": T11_D_DAYS,
               "v1FloorDegPerDay": V1_FLOOR_DEG_PER_DAY,
               "cadenceLimitAtUDwellDays":
                   cadence_limit_days(abs(math.sin(2.0 * math.radians(
                       U_DWELL_DEG)))),
               "horizonDays": HORIZON_DAYS,
               "substrateMaxSpacingDays": (gec.MAX_BASELINE_SPAN_DAYS
                                           / 5.5)}}

    # ---------------- signs for every object, once ------------------------
    print("chain signs ...", flush=True)
    t_sign = time.time()
    signs_by, chains_by = {}, {}
    for s in w.series:
        sg, ch = chain_signs(s, sigma_n)
        signs_by[s.norad] = sg
        chains_by[s.norad] = ch
    out["signWallSeconds"] = time.time() - t_sign

    tally = {FREE: 0, KEEPER: 0, UNEVALUABLE: 0}
    for sg in signs_by.values():
        for c in sg:
            tally[c["sign"]] += 1
    out["chainSignTally"] = dict(tally)

    # ---------------- persistence, MEASURED before use --------------------
    devset = json.loads((_REPO / "docs"
                         / "matched-filter-devset-20260922.json").read_text())
    carriers = [int(n) for n in devset["eastWestCarriers"]]
    passives = [int(n) for n in devset["sameShellGeoPassiveControl"]]
    carrier_signs = [signs_by[n] for n in carriers if n in signs_by]
    passive_signs = [signs_by[n] for n in passives if n in signs_by]
    prof = run_length_profile(carrier_signs)
    prof["objects"] = len(carrier_signs)
    prof["rosterSize"] = len(carriers)
    out["persistence"] = {
        "carrier": prof,
        "passive": dict(run_length_profile(passive_signs),
                        objects=len(passive_signs), rosterSize=len(passives)),
    }
    k, k_exhausted = choose_k(prof)
    out["persistence"]["chosenK"] = k
    out["persistence"]["qBar"] = Q_BAR
    out["persistence"]["barExhausted"] = k_exhausted
    out["persistence"]["achievedQ"] = prof["qK"][str(k)]["q"]
    print(f"  k = {k} (q_k = {prof['qK'][str(k)]['q']:.5f})", flush=True)

    # ---------------- validation BEFORE use --------------------------------
    print("validation BEFORE use ...", flush=True)
    out["validation"] = validate(sigma_n, k)
    v = out["validation"]
    print(f"  V1 hard {v['V1']['hardBarPassed']} admit "
          f"{v['V1']['admittedEligibleFraction']:.3f} | V2 "
          f"{v['V2']['passed']} | V3 {v['V3']['passed']} | V4 "
          f"{v['V4']['passed']}", flush=True)

    # ---------------- epochs, once -----------------------------------------
    print("finding epochs ...", flush=True)
    t_ep = time.time()
    epochs_by = {}
    for s in w.series:
        eps, _d = gce.find_epochs(s, sigma_n, familywise=True)
        epochs_by[s.norad] = eps
    out["epochWallSeconds"] = time.time() - t_ep
    out["substrateEpochs"] = int(sum(len(e) for e in epochs_by.values()))
    print(f"  {out['substrateEpochs']:,} substrate epochs", flush=True)

    # ---------------- the matched reference --------------------------------
    watched = {s.norad: gce.watched_runs(s) for s in w.series}
    reference_pop = {n for n, c in w.classes.items() if c == "active"} - w.never
    ref_watched = {n: watched[n] for n in reference_pop if n in watched}
    ref_days = gce.days_map(ref_watched)
    ref_obj_days, ref_pair_days = gce.exposure_from_days(ref_days)
    ref = {"objectDays": ref_obj_days, "pairDays": ref_pair_days,
           "t8aEvents": gce.count_t8a(ref_watched, events),
           "t11Episodes": gce.count_t11(ref_watched, episodes),
           "triggerChains": gce.count_triggers(ref_watched, chains_by)}
    ref["population"] = len(reference_pop)
    ref["t8aRatePerObjectDay"] = ref["t8aEvents"] / ref_obj_days
    ref["t11RatePerPairDay"] = ref["t11Episodes"] / ref_pair_days
    ref["triggerRatePerObjectDay"] = ref["triggerChains"] / ref_obj_days
    ref["meaningfulZero"] = {
        "t8aObjectDays": 1.0 / ref["t8aRatePerObjectDay"],
        "t11PairDays": 1.0 / ref["t11RatePerPairDay"],
        "triggerObjectDays": 1.0 / ref["triggerRatePerObjectDay"]}
    ref["note"] = ("payload class minus the v1 never-manoeuvred set, on "
                   "watched days -- identical to T8e 5, so the two exposure "
                   "tables may be read side by side")
    out["reference"] = ref

    # ---------------- the arms ---------------------------------------------
    print("classifying ...", flush=True)
    rows_by_arm, diag_by_arm = {}, {}
    for arm in ARMS:
        rows, agg = [], {}
        for s in w.series:
            r, d = classify_object(s, sigma_n, k, arm,
                                   epochs=epochs_by[s.norad],
                                   signs=signs_by[s.norad])
            rows.extend(r)
            for key, val in d.items():
                if isinstance(val, (int, float)):
                    agg[key] = agg.get(key, 0) + val
        rows_by_arm[arm] = rows
        diag_by_arm[arm] = agg
        print(f"  {arm}: {len(rows):,} intervals", flush=True)

    out["arms"] = {arm: arm_block(rows_by_arm[arm], arm, events, episodes,
                                  chains_by, ref) for arm in ARMS}
    for arm in ARMS:
        out["arms"][arm]["diagnostics"] = diag_by_arm[arm]

    # S2 -- the purely causal horizon
    print("causal-horizon arm ...", flush=True)
    rows_s2 = []
    for s in w.series:
        r, _d = classify_object(s, sigma_n, k, PRIMARY_ARM,
                                epochs=epochs_by[s.norad],
                                signs=signs_by[s.norad],
                                horizon_days=HORIZON_DAYS)
        rows_s2.extend(r)
    out["armS2CausalHorizon"] = arm_block(rows_s2, "S2-" + PRIMARY_ARM, events,
                                          episodes, chains_by, ref)
    out["armS2CausalHorizon"]["note"] = (
        f"registration 5: the asserted interval ends at t_trig(c_k) + "
        f"{HORIZON_DAYS} d, truncated by a keeper-sign chain or the epoch, so "
        f"both ends are causal")

    # ---------------- E4, the operating-point curve ------------------------
    print("operating-point curve ...", flush=True)
    curve = []
    for kk in K_CANDIDATES:
        for arm in ("A-NOAMP", "B-AMP"):
            rows = []
            for s in w.series:
                r, _d = classify_object(s, sigma_n, kk, arm,
                                        epochs=epochs_by[s.norad],
                                        signs=signs_by[s.norad])
                rows.extend(r)
            blk = arm_block(rows, arm, events, episodes, chains_by, ref)
            curve.append({
                "k": kk, "arm": arm,
                "carrierFalseRateQk": prof["qK"][str(kk)]["q"],
                "independenceModelPk": (1.0 - T22_CARRIER_SIGN_FRACTION) ** kk,
                "objects": blk["objects"], "objectDays": blk["objectDays"],
                "pairDays": blk["pairDays"],
                "leak": {c: blk["readings"][c]["leakRatio"]
                         for c in CONSUMERS},
                "verdicts": {c: blk["readings"][c]["verdict"]
                             for c in CONSUMERS},
                "chosen": bool(kk == k and arm == PRIMARY_ARM)})
    out["E4OperatingPointCurve"] = curve

    # ---------------- E5, the alarm lane ------------------------------------
    if args.replay and Path(args.replay).exists():
        iv_primary = _intervals(rows_by_arm[PRIMARY_ARM])
        certified = set()
        for norad, iv in iv_primary.items():
            for _tf, t_trig, _st, _sz, _bs in chains_by.get(norad, ()):
                if gce.in_any(iv, float(t_trig)):
                    certified.add((int(norad), int(round(float(t_trig)))))
        out["E5"] = rescore_class_one(args.replay, certified)
        out["E5"]["certifiedChains"] = len(certified)
        out["E5"]["arm"] = PRIMARY_ARM
        out["E5"]["replaySha256"] = pg.sha256_file(Path(args.replay))
    else:
        out["E5"] = {"status": "LABELLED GAP -- replay ledger not present",
                     "path": str(args.replay)}

    # ---------------- V5, the parity split ----------------------------------
    rows = rows_by_arm[PRIMARY_ARM]
    out["V5ParitySplit"] = {
        "even": arm_block([r for r in rows if r["norad"] % 2 == 0], "even",
                          events, episodes, chains_by, ref),
        "odd": arm_block([r for r in rows if r["norad"] % 2 == 1], "odd",
                         events, episodes, chains_by, ref),
        "instabilityFactor": 3.0}

    # ---------------- the verdict -------------------------------------------
    leak_free_arms = []
    for arm in ARMS:
        rd = out["arms"][arm]["readings"]
        if all(rd[c]["verdict"] == "LEAK-FREE" for c in CONSUMERS):
            leak_free_arms.append({
                "arm": arm,
                "strict": all(rd[c]["leakRatioCi95"][1] <= LEAK_BAR
                              for c in CONSUMERS),
                "leak": {c: rd[c]["leakRatio"] for c in CONSUMERS}})
    rd_s2 = out["armS2CausalHorizon"]["readings"]
    if all(rd_s2[c]["verdict"] == "LEAK-FREE" for c in CONSUMERS):
        leak_free_arms.append({
            "arm": "S2-" + PRIMARY_ARM,
            "strict": all(rd_s2[c]["leakRatioCi95"][1] <= LEAK_BAR
                          for c in CONSUMERS),
            "leak": {c: rd_s2[c]["leakRatio"] for c in CONSUMERS}})

    per_consumer = {}
    for c in CONSUMERS:
        rows_c = [out["arms"][a]["readings"][c] for a in ARMS]
        rows_c.append(out["armS2CausalHorizon"]["readings"][c])
        evaluable = [r for r in rows_c if r["evaluable"]]
        if not evaluable:
            per_consumer[c] = {"reason": "exposure below the meaningful zero",
                               "bestExposureRatio": max(
                                   (r["exposure"] / r["meaningfulZeroExposure"]
                                    if r["meaningfulZeroExposure"] else 0.0)
                                   for r in rows_c)}
        else:
            best = min(evaluable, key=lambda r: r["leakRatio"])
            per_consumer[c] = {
                "reason": ("leak-free" if best["verdict"] == "LEAK-FREE"
                           else "all arms >= 0.10 with exposure above the "
                                "meaningful zero"),
                "bestLeakRatio": best["leakRatio"]}

    out["verdict"] = {
        "exists": bool(leak_free_arms),
        "sentence": ("a leak-free GEO control EXISTS" if leak_free_arms
                     else "a leak-free GEO control DOES NOT EXIST"),
        "leakFreeArms": leak_free_arms,
        "perConsumer": per_consumer,
        "armsRegistered": len(ARMS) + 1,
        "bar": LEAK_BAR}

    out["gates"] = {
        "G_S1": {"meaning": "the classifier admits nothing in the primary arm",
                 "intervals": out["arms"][PRIMARY_ARM]["intervals"],
                 "fired": bool(not rows_by_arm[PRIMARY_ARM])},
        "G_S2": {"meaning": "no reading has exposure above its meaningful zero",
                 "fired": bool(not any(
                     out["arms"][a]["readings"][c]["evaluable"]
                     for a in ARMS for c in CONSUMERS))},
        "G_S3": {"meaning": "every evaluable reading leaks",
                 "fired": bool(not leak_free_arms)},
        "G_S4": {"meaning": "the sign clause rejects free motion",
                 "rejectedByClauseA": v["V1"]["rejectedByClauseA"],
                 "fired": bool(not v["V1"]["hardBarPassed"])},
        "G_S5": {"meaning": "a keeper outside the blind band is admitted",
                 "admittedOutside": v["V2"]["admittedOutsideBlindBand"],
                 "fired": bool(not v["V2"]["passed"])},
        "G_S6": {"meaning": "the slow librator is mislabelled",
                 "fired": bool(not v["V3"]["passed"])},
        "G_S7": {"meaning": "provenance", "catalogueSha256": sha,
                 "fired": False},
        "G_S8": {"meaning": "persistence did not buy what 3.5 derived",
                 "chosenK": k, "achievedQ": prof["qK"][str(k)]["q"],
                 "fired": bool(k_exhausted)}}

    # ---------------- labelled diagnostics ----------------------------------
    iv_primary = _intervals(rows_by_arm[PRIMARY_ARM])
    by_object = {}
    for r in rows_by_arm[PRIMARY_ARM]:
        by_object.setdefault(int(r["norad"]), []).append(r)

    leaking_t8a = []
    for ev in events:
        n = int(ev["approacherNorad"])
        a = ev.get("arrivalMs")
        if a is None or n not in iv_primary:
            continue
        if not gce.in_any(iv_primary[n], float(a)):
            continue
        tgt = int(ev["targetNorad"])
        tgt_in = bool(tgt in iv_primary
                      and gce.in_any(iv_primary[tgt], float(a)))
        leaking_t8a.append({
            "approacherNorad": n, "targetNorad": tgt,
            "class": w.classes.get(n), "targetClass": w.classes.get(tgt),
            "arrival": pp.iso(float(a)), "loiterDays": ev.get("loiterDays"),
            "targetInClass": tgt_in})

    dts = []
    for norad, iv in iv_primary.items():
        s = next((x for x in w.series if x.norad == norad), None)
        if s is None:
            continue
        dt = _baseline_offsets(np.asarray(s.epoch_ms, dtype=np.float64))
        for _tf, t_trig, _st, _sz, _bs in chains_by.get(norad, ()):
            if not gce.in_any(iv, float(t_trig)):
                continue
            j = int(np.searchsorted(s.epoch_ms, t_trig, side="left"))
            if 0 <= j < dt.size and np.isfinite(dt[j]):
                dts.append(float(dt[j]))
    out["postRegistrationDiagnostics"] = {
        "label": ("post-registration where marked; the T-PRED cadence "
                  "measurement and the co-moving-partner measurement are "
                  "registered in 4.4 and 7.2 respectively"),
        "tPredBaselineOffsetAtLeakingChains": {
            "chains": len(dts),
            "p25": float(np.percentile(dts, 25)) if dts else None,
            "median": float(np.median(dts)) if dts else None,
            "p75": float(np.percentile(dts, 75)) if dts else None,
            "p95": float(np.percentile(dts, 95)) if dts else None,
            "archiveMedianBaselineReachDays":
                5.5 * gec.SAMPLE_SPACING_DAYS,
            "maxBaselineReachInAFiveDayGapRunDays": 5.5 * MAX_GAP_DAYS},
        "t8aLeaksWithPartnerClass": leaking_t8a,
        "classOfAdmittedObjects": {
            "active": sum(1 for n in by_object if w.classes.get(n) == "active"),
            "passive": sum(1 for n in by_object
                           if w.classes.get(n) == "passive"),
            "unknown": sum(1 for n in by_object if w.classes.get(n) is None)}}

    out["sourceSha256"] = {
        "tools/geo_sign_control.py": pg.sha256_file(Path(__file__))}
    out["wallSeconds"] = time.time() - started
    return out, rows_by_arm[PRIMARY_ARM]


def write_intervals(path, rows, meta):
    with Path(path).open("w") as fh:
        fh.write(json.dumps(meta, default=pp._json_default) + "\n")
        for r in sorted(rows, key=lambda x: (x["startMs"], x["norad"])):
            fh.write(json.dumps(r, default=pp._json_default) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, default=None)
    ap.add_argument("--work", type=Path,
                    default=_REPO / "runtime" / "proximity-geo")
    ap.add_argument("--docs", type=Path, default=_REPO / "docs")
    ap.add_argument("--out", type=Path, default=_REPO / "docs")
    ap.add_argument("--replay", type=Path, required=True,
                    help="the alarm lane replay ledger at the everything setting")
    ap.add_argument("--date", default="20260923")
    args = ap.parse_args(argv)

    db = orbit_campaigns.open_archive_for_reading(args.archive)
    db.execute("PRAGMA query_only=1")
    archive_path = next(r[2] for r in db.execute("PRAGMA database_list")
                        if r[1] == "main")
    print("building world ...", flush=True)
    w = pp.build_world(db, args.work)
    print(f"  {len(w.series):,} objects, sigma_n {w.sigma_n:.7f}", flush=True)
    out, rows = analyze(db, archive_path, w, args)
    receipt = args.out / f"t28-geo-sign-control-{args.date}-receipt.json"
    receipt.write_text(json.dumps(out, indent=1, default=pp._json_default)
                       + "\n")
    write_intervals(args.out / f"t28-geo-sign-control-{args.date}.jsonl", rows,
                    {"schema": 1, "record": "provenance",
                     "study": "GEO sign-and-persistence control",
                     "registration": REGISTRATION,
                     "archive": out["archive"], "extract": out["extract"],
                     "derivations": out["derivations"]})
    print(json.dumps({
        "verdict": out["verdict"]["sentence"],
        "k": out["persistence"]["chosenK"],
        "arms": {a: {"intervals": out["arms"][a]["intervals"],
                     "objectDays": out["arms"][a]["objectDays"],
                     "pairDays": out["arms"][a]["pairDays"],
                     "readings": {c: [out["arms"][a]["readings"][c]["verdict"],
                                      out["arms"][a]["readings"][c]["leakRatio"]]
                                  for c in CONSUMERS}}
                 for a in ARMS},
        "gates": {g: b["fired"] for g, b in out["gates"].items()}},
        indent=1, default=pp._json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
