#!/usr/bin/env python3
"""T11b part 2 -- a GEO passive control, built by construction and proved.

Registration: docs/persistent-pairs-response-preregistration-20260922.md

T8b's LEO control was proved by running the unchanged detector on a class that
could not produce the signal and getting zero per unit exposure, with the
exposure printed. The same definition at GEO holds 9 objects and zero
pair-exposure-days, so the gate there is 0/0.

This module builds three GEO classes whose rules come from the triaxial term
with no fitted parameter -- class D from the v2 drift-change rule that
predicts and subtracts free motion instead of thresholding on a constant,
class F from the absence of the measured 14.00-day line together with five
one-sided free-libration bounds, and class I = D and F, the registered primary
control -- validates each rule against synthetic free librators and synthetic
station-keepers BEFORE using it, and then re-expresses two committed
catalogues over the classes to measure the leak.

CPU only.
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
from pipeline import orbit_campaigns                          # noqa: E402

DAY_MS = pp.DAY_MS
REGISTRATION = "docs/persistent-pairs-response-preregistration-20260922.md"

# --------------------------------------------------------------------------
# The physics, section 10 of the registration. Nothing here is fitted.
# --------------------------------------------------------------------------
A_DEG_PER_DAY2 = pg.LAMBDA_DDOT_MAX          # 1.7006955627927864e-3
A_RAD_PER_DAY2 = A_DEG_PER_DAY2 * math.pi / 180.0
OMEGA_0_RAD_PER_DAY = math.sqrt(2.0 * A_RAD_PER_DAY2)
T0_DAYS = 2.0 * math.pi / OMEGA_0_RAD_PER_DAY               # 815.4792 d
PEAK_RATE_COEFF_DEG_PER_DAY = OMEGA_0_RAD_PER_DAY * 180.0 / math.pi
STABLE_LONGITUDES_DEG = pg.STABLE_LONGITUDES_DEG            # (75.1, -104.7)

# --------------------------------------------------------------------------
# Registered constants (prereg 11, 12, 13)
# --------------------------------------------------------------------------
BASELINE_SAMPLES = pg.BURN_BASELINE_SAMPLES                  # 10, T8a unchanged
SIGMA_K = pg.BURN_SIGMA_K                                    # 5, T8a unchanged
MIN_ELEMENT_SETS = pp.NEVER_MIN_ELEMENT_SETS                 # 200
MIN_SPAN_DAYS = pp.NEVER_MIN_SPAN_DAYS                       # 365
MAX_BASELINE_SPAN_DAYS = 14.00                               # prereg 11.1
MAX_NON_EVALUABLE_FRACTION = 0.05                            # prereg 11.1

BLOCK_DAYS = pp.D_PAIR_PRIMARY_DAYS                          # 56.00
BLOCK_MIN_SAMPLES = 8
F1_EXCLUDE_FAP = 0.10                                        # prereg 11.2
# POST-REGISTRATION ADDITION, labelled wherever it is reported. The registered
# F1 applies a 0.10 false-alarm threshold once per 56-day block and excludes
# the object if ANY block fires. An object with N blocks therefore fires under
# the null with probability 1 - 0.9^N, which for the archive's typical N = 131
# is 1.000: the registered rule excludes very nearly everything, including a
# synthetic free librator, and empties the class it was meant to build. The
# family-wise threshold at the SAME 0.10 level is the Sidak correction, which
# introduces no new constant and no tuned parameter.
F1_FAMILYWISE = 0.10
TURNAROUND_MIN_RUN_DAYS = 30.0                               # prereg 11.2
CENTRE_TOLERANCE_DEG = 5.0
CENTRE_TOLERANCE_FRACTION = 0.25
RATE_BOUND_FACTOR = 1.25
PERIOD_BOUND_FACTOR = 0.80
MAX_DISPLACEMENT_DEG = 90.0

VALIDATION_OBJECTS = 200                                     # prereg 12
VALIDATION_YEARS = 20.0
SAMPLE_SPACING_DAYS = pp.MEDIAN_EPOCH_SPACING_DAYS           # 0.865
RK_STEP_DAYS = 0.01
V1_BAR = 0.95
V2_BAR = 0.95
V3_BURN_SCALES = tuple(np.linspace(0.1, 2.0, 20))
V3_FLAG_FRACTION = 0.50
V4_INSTABILITY_FACTOR = 3.0
LEAK_BAR = pp.GATE_B_LEAK_RATIO                              # 0.10
SEED = 20260922

EW_PERIOD_DAYS = pp.T_EAST_WEST_DAYS                         # 14.00
EW_DRIFT_HALF_AMPLITUDE = A_DEG_PER_DAY2 * EW_PERIOD_DAYS / 4.0
EW_BURN_STEP = A_DEG_PER_DAY2 * EW_PERIOD_DAYS / 2.0

CATALOGUE_SHA256 = ("5df77537334ac5792b708c4c93f84c14b28d07df"
                    "7803b5a7ccd459a29d0167bb")


# ==========================================================================
# Section 10.2 -- the pendulum's period and its amplitude-rate relation
# ==========================================================================
def elliptic_k(k):
    """Complete elliptic integral of the first kind, by the arithmetic-
    geometric mean. Checked in the test suite against independent values."""
    if k < 0.0 or k >= 1.0:
        if k == 0.0:
            return math.pi / 2.0
        raise ValueError("modulus out of range")
    a, b = 1.0, math.sqrt(1.0 - k * k)
    for _ in range(60):
        a, b = 0.5 * (a + b), math.sqrt(a * b)
        if abs(a - b) < 1e-16:
            break
    return math.pi / (2.0 * a)


def libration_period_days(u_max_deg):
    """Full period of the free libration of half-amplitude u_max, from the
    pendulum with the maximum triaxial restoring acceleration."""
    k = math.sin(math.radians(u_max_deg))
    return (2.0 / math.pi) * T0_DAYS * elliptic_k(k)


def libration_half_period_days(u_max_deg):
    return 0.5 * libration_period_days(u_max_deg)


def peak_rate_deg_per_day(u_max_deg):
    """|lambda'|_max = sqrt(2 A) sin(u_max), the amplitude-rate relation."""
    return PEAK_RATE_COEFF_DEG_PER_DAY * math.sin(math.radians(u_max_deg))


def nearest_stable(lon_deg):
    """The nearer stable longitude and the signed displacement from it."""
    best_u, best_s = None, None
    for s in STABLE_LONGITUDES_DEG:
        u = pg.wrap180(np.asarray(lon_deg, dtype=np.float64) - s)
        if best_u is None:
            best_u, best_s = u, np.full(np.shape(u), s, dtype=np.float64)
        else:
            take = np.abs(u) < np.abs(best_u)
            best_u = np.where(take, u, best_u)
            best_s = np.where(take, s, best_s)
    return best_s, best_u


def free_acceleration(lon_deg):
    """lambda'' = -A sin(2 (lambda - lambda_s)), deg/day^2."""
    _s, u = nearest_stable(lon_deg)
    return -A_DEG_PER_DAY2 * np.sin(2.0 * np.radians(u))


# ==========================================================================
# Section 11.1 -- the T8a v2 drift-change rule
# ==========================================================================
def v2_flags(epoch_ms, drift, lam, sigma_n):
    """A drift change is a flag only if it exceeds the measured noise floor
    AND is more than twice what free triaxial motion at this longitude could
    have produced over the same interval. No 0.010 deg/day floor.

    Returns (flag_epoch_ms, evaluable_fraction, samples_tested).
    """
    t = np.asarray(epoch_ms, dtype=np.float64) / DAY_MS
    d = np.asarray(drift, dtype=np.float64)
    lo = np.asarray(lam, dtype=np.float64)
    n = d.size
    w = BASELINE_SAMPLES
    if n < w + 2:
        return np.zeros(0), 0.0, 0
    base = np.full(n, np.nan)
    tcen = np.full(n, np.nan)
    lcen = np.full(n, np.nan)
    sw = np.lib.stride_tricks.sliding_window_view
    base[w:] = np.median(sw(d[:n - 1], w)[:n - w], axis=1)
    tcen[w:] = np.median(sw(t[:n - 1], w)[:n - w], axis=1)
    lcen[w:] = np.median(sw(lo[:n - 1], w)[:n - w], axis=1)
    dt = t - tcen
    acc_i = free_acceleration(lo)
    acc_c = free_acceleration(lcen)
    pred = 0.5 * (acc_c + acc_i) * dt
    dev = np.abs(d - base - pred)
    thresh = np.maximum(SIGMA_K * sigma_n, np.abs(acc_i) * dt)
    evaluable = np.isfinite(dt) & (dt <= MAX_BASELINE_SPAN_DAYS)
    tested = int(np.isfinite(dt).sum())
    frac = float(evaluable[np.isfinite(dt)].mean()) if tested else 0.0
    hot = np.isfinite(dev) & (dev > thresh) & evaluable
    confirmed = np.where(hot[:-1] & hot[1:])[0] + 1
    return np.asarray(epoch_ms)[confirmed], frac, tested


def v2_flags_for(series, sigma_n):
    return v2_flags(series.epoch_ms, series.drift, series.lam, sigma_n)


# ==========================================================================
# Section 11.2 -- F1, the absence of the measured 14.00-day line
# ==========================================================================
def sidak_block_alpha(n_blocks):
    """1 - (1 - 0.10)^(1/N): the per-block threshold whose family-wise rate
    over N blocks is the registered 0.10."""
    if n_blocks <= 0:
        return float("nan")
    return 1.0 - (1.0 - F1_FAMILYWISE) ** (1.0 / float(n_blocks))


def min_block_fap(series):
    """The smallest false-alarm probability the fixed-period cadence phasor
    returns over consecutive non-overlapping 56.00-day blocks."""
    t = series.epoch_ms / DAY_MS
    d = series.drift
    if t.size < BLOCK_MIN_SAMPLES:
        return float("nan"), 0
    edges = np.arange(t[0], t[-1] + BLOCK_DAYS, BLOCK_DAYS)
    idx = np.searchsorted(t, edges)
    best, blocks = float("inf"), 0
    for k in range(idx.size - 1):
        i0, i1 = int(idx[k]), int(idx[k + 1])
        if i1 - i0 < BLOCK_MIN_SAMPLES:
            continue
        fit = pp.cadence_phasor(t[i0:i1], d[i0:i1])
        if fit is None:
            continue
        blocks += 1
        best = min(best, float(fit["fap"]))
    if blocks == 0:
        return float("nan"), 0
    return best, blocks


# ==========================================================================
# Section 11.2 -- F2, five one-sided free-libration bounds
# ==========================================================================
def _sign_runs(t, values, min_run_days):
    """Runs of one sign lasting at least min_run_days. Returns
    [(sign, t_start, t_end)] in order."""
    s = np.sign(values)
    out = []
    i = 0
    n = s.size
    while i < n:
        if s[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and s[j + 1] == s[i]:
            j += 1
        if t[j] - t[i] >= min_run_days:
            out.append((int(s[i]), float(t[i]), float(t[j])))
        i = j + 1
    return out


def libration_signature(series):
    """The five registered bounds. Every one of them is one-sided, because A
    is an upper bound on the restoring acceleration (prereg 10.1)."""
    t = series.epoch_ms / DAY_MS
    lon = series.lam
    drift = series.drift
    out = {"c1BoundMotion": False, "c2Turnaround": False,
           "c3Centred": False, "c4RateBound": False, "c5PeriodBound": False,
           "uMaxDeg": None, "uMidDeg": None, "maxAbsDriftDegPerDay": None,
           "predictedPeakRateDegPerDay": None,
           "turnarounds": 0, "observedHalfPeriodDays": None,
           "predictedHalfPeriodDays": None, "stableLongitudeDeg": None,
           "passed": False}
    if t.size < BLOCK_MIN_SAMPLES:
        return out
    stable, u = nearest_stable(lon)
    if np.unique(stable).size != 1:
        return out
    out["stableLongitudeDeg"] = float(stable[0])
    if not np.all(np.abs(u) < MAX_DISPLACEMENT_DEG):
        return out
    out["c1BoundMotion"] = True

    u_hi, u_lo = float(np.max(u)), float(np.min(u))
    u_max = 0.5 * (u_hi - u_lo)
    u_mid = 0.5 * (u_hi + u_lo)
    out["uMaxDeg"], out["uMidDeg"] = u_max, u_mid

    runs = _sign_runs(t, drift, TURNAROUND_MIN_RUN_DAYS)
    turns = []
    for a, b in zip(runs[:-1], runs[1:]):
        if a[0] != b[0]:
            turns.append(0.5 * (a[2] + b[1]))
    out["turnarounds"] = len(turns)
    out["c2Turnaround"] = len(turns) >= 1

    out["c3Centred"] = abs(u_mid) <= max(
        CENTRE_TOLERANCE_DEG, CENTRE_TOLERANCE_FRACTION * u_max)

    if u_max <= 0.0:
        return out
    pred_rate = peak_rate_deg_per_day(u_max)
    max_rate = float(np.max(np.abs(drift)))
    out["maxAbsDriftDegPerDay"] = max_rate
    out["predictedPeakRateDegPerDay"] = pred_rate
    out["c4RateBound"] = max_rate <= RATE_BOUND_FACTOR * pred_rate

    pred_half = libration_half_period_days(min(u_max, 89.9))
    out["predictedHalfPeriodDays"] = pred_half
    if len(turns) >= 2:
        gaps = np.diff(np.asarray(turns))
        obs_half = float(np.median(gaps))
        out["observedHalfPeriodDays"] = obs_half
        out["c5PeriodBound"] = obs_half >= PERIOD_BOUND_FACTOR * pred_half
    out["passed"] = bool(out["c1BoundMotion"] and out["c2Turnaround"]
                         and out["c3Centred"] and out["c4RateBound"]
                         and out["c5PeriodBound"])
    return out


# ==========================================================================
# Section 12 -- validation BEFORE use
# ==========================================================================
class _SynSeries:
    __slots__ = ("norad", "epoch_ms", "lam", "lam_unwrapped", "drift")

    def __init__(self, norad, epoch_ms, lam, drift):
        self.norad = norad
        self.epoch_ms = epoch_ms
        self.lam = lam
        self.lam_unwrapped = lam
        self.drift = drift


def _integrate_librators(u0_deg, udot0, days, step=RK_STEP_DAYS):
    """u'' = -A sin 2u, in radians, RK4, vectorised across objects."""
    u = np.radians(np.asarray(u0_deg, dtype=np.float64))
    v = np.asarray(udot0, dtype=np.float64).copy()
    n_steps = int(round(days / step))
    keep = max(1, int(round(SAMPLE_SPACING_DAYS / step)))
    us, vs, ts = [], [], []

    def acc(x):
        return -A_RAD_PER_DAY2 * np.sin(2.0 * x)

    for k in range(n_steps + 1):
        if k % keep == 0:
            us.append(u.copy())
            vs.append(v.copy())
            ts.append(k * step)
        k1u, k1v = v, acc(u)
        k2u, k2v = v + 0.5 * step * k1v, acc(u + 0.5 * step * k1u)
        k3u, k3v = v + 0.5 * step * k2v, acc(u + 0.5 * step * k2u)
        k4u, k4v = v + step * k3v, acc(u + step * k3u)
        u = u + (step / 6.0) * (k1u + 2 * k2u + 2 * k3u + k4u)
        v = v + (step / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)
    return np.asarray(ts), np.asarray(us), np.asarray(vs)


def synthetic_librators(seed, n=VALIDATION_OBJECTS, years=VALIDATION_YEARS,
                        sigma_n=None):
    rng = np.random.default_rng(seed)
    u_max = rng.uniform(1.0, 60.0, size=n)
    phase = rng.uniform(0.0, 1.0, size=n)
    # start each object at a random point on its own orbit in the phase plane
    u0 = u_max * np.sin(2.0 * math.pi * phase)
    k = np.sin(np.radians(u_max))
    inner = np.clip(k ** 2 - np.sin(np.radians(u0)) ** 2, 0.0, None)
    v0 = np.sqrt(2.0 * A_RAD_PER_DAY2 * inner) * np.sign(
        np.cos(2.0 * math.pi * phase))
    days = years * 365.25
    ts, us, vs = _integrate_librators(u0, v0, days)
    lam = np.degrees(us) + STABLE_LONGITUDES_DEG[0]
    drift = np.degrees(vs)
    if sigma_n:
        drift = drift + rng.normal(0.0, sigma_n, size=drift.shape)
    epoch_ms = (ts + 20000.0) * DAY_MS
    out = []
    for j in range(n):
        out.append(_SynSeries(900000 + j, epoch_ms,
                              pg.wrap180(lam[:, j]), drift[:, j]))
    return out


def synthetic_keepers(seed, n=VALIDATION_OBJECTS, years=VALIDATION_YEARS,
                      sigma_n=None, burn_scale=1.0, self_consistent=False):
    """A longitude sawtooth about a slot, at the measured 14.00-day cycle."""
    rng = np.random.default_rng(seed)
    slots = rng.uniform(-180.0, 180.0, size=n)
    phase0 = rng.uniform(0.0, EW_PERIOD_DAYS, size=n)
    days = years * 365.25
    t = np.arange(0.0, days, SAMPLE_SPACING_DAYS)
    out = []
    for j in range(n):
        ramp = (abs(float(free_acceleration(np.array([slots[j]]))[0]))
                if self_consistent else A_DEG_PER_DAY2)
        half = ramp * EW_PERIOD_DAYS / 4.0
        cycle = np.mod(t + phase0[j], EW_PERIOD_DAYS)
        d = (-half + ramp * cycle) * burn_scale
        lam = slots[j] + np.cumsum(d - np.mean(d)) * SAMPLE_SPACING_DAYS
        if sigma_n:
            d = d + rng.normal(0.0, sigma_n, size=d.size)
        out.append(_SynSeries(800000 + j, (t + 20000.0) * DAY_MS,
                              pg.wrap180(lam), d))
    return out


def validate(sigma_n):
    t0 = time.time()
    out = {"sigmaNDegPerDay": sigma_n,
           "ewBurnStepDegPerDay": EW_BURN_STEP,
           "ewDriftHalfAmplitudeDegPerDay": EW_DRIFT_HALF_AMPLITUDE}

    lib = synthetic_librators(SEED, sigma_n=sigma_n)
    zero_flags = 0
    f2_pass = 0
    f1_pass = 0
    f1w_pass = 0
    for s in lib:
        ep, _frac, _n = v2_flags_for(s, sigma_n)
        if ep.size == 0:
            zero_flags += 1
        if libration_signature(s)["passed"]:
            f2_pass += 1
        fap, blocks = min_block_fap(s)
        if blocks > 0 and not (np.isfinite(fap) and fap <= F1_EXCLUDE_FAP):
            f1_pass += 1
        if blocks > 0 and not (np.isfinite(fap)
                               and fap <= sidak_block_alpha(blocks)):
            f1w_pass += 1
    out["V1"] = {"objects": len(lib),
                 "f1RegisteredAdmitted": f1_pass,
                 "f1RegisteredAdmittedFraction": f1_pass / len(lib),
                 "f1FamilywiseAdmitted": f1w_pass,
                 "f1FamilywiseAdmittedFraction": f1w_pass / len(lib),
                 "zeroV2Flags": zero_flags,
                 "zeroV2FlagFraction": zero_flags / len(lib),
                 "f2Passed": f2_pass,
                 "f2PassedFraction": f2_pass / len(lib),
                 "bar": V1_BAR,
                 "passed": bool(zero_flags / len(lib) >= V1_BAR
                                and f2_pass / len(lib) >= V1_BAR)}

    def keeper_stats(self_consistent, burn_scale=1.0, with_f1=False):
        keep = synthetic_keepers(SEED + 1, sigma_n=sigma_n,
                                 burn_scale=burn_scale,
                                 self_consistent=self_consistent)
        flagged = 0
        f2_fail = 0
        f1_excl = 0
        f1w_excl = 0
        for s in keep:
            if with_f1:
                fap, blocks = min_block_fap(s)
                if blocks > 0 and np.isfinite(fap) and fap <= F1_EXCLUDE_FAP:
                    f1_excl += 1
                if blocks > 0 and np.isfinite(fap) and fap <= sidak_block_alpha(blocks):
                    f1w_excl += 1
            ep, _f, _n = v2_flags_for(s, sigma_n)
            if ep.size > 0:
                flagged += 1
            sig = libration_signature(s)
            if not (sig["c2Turnaround"] and sig["c5PeriodBound"]):
                f2_fail += 1
        return {"objects": len(keep), "withV2Flag": flagged,
                "withV2FlagFraction": flagged / len(keep),
                "failingF2Criterion2or5": f2_fail,
                "failingFraction": f2_fail / len(keep),
                "excludedByF1Registered": f1_excl,
                "excludedByF1Familywise": f1w_excl,
                "excludedByF1RegisteredFraction": f1_excl / len(keep),
                "excludedByF1FamilywiseFraction": f1w_excl / len(keep)}

    v2a = keeper_stats(False, with_f1=True)
    v2a["bar"] = V2_BAR
    v2a["passed"] = bool(v2a["withV2FlagFraction"] >= V2_BAR
                         and v2a["failingFraction"] >= V2_BAR)
    out["V2"] = v2a
    v2b = keeper_stats(True, with_f1=True)
    v2b["note"] = ("post-registration addition, labelled: the ramp rate is "
                   "the triaxial acceleration at the object's own slot "
                   "rather than the registered maximum, so the synthetic "
                   "keeper is self-consistent")
    out["V2b"] = v2b

    floor = None
    ladder = []
    for scale in V3_BURN_SCALES:
        st = keeper_stats(True, burn_scale=float(scale))
        row = {"burnScale": float(scale),
               "burnStepDegPerDay": float(scale) * EW_BURN_STEP,
               "withV2FlagFraction": st["withV2FlagFraction"]}
        ladder.append(row)
        if floor is None and st["withV2FlagFraction"] >= V3_FLAG_FRACTION:
            floor = row["burnStepDegPerDay"]
    out["V3"] = {"ladder": ladder, "flagFraction": V3_FLAG_FRACTION,
                 "detectionFloorDegPerDay": floor,
                 "detectionFloorInEwBurns": (floor / EW_BURN_STEP
                                             if floor else None),
                 "routineEwBurnBelowFloor": bool(floor is None
                                                 or floor > EW_BURN_STEP)}
    out["wallSeconds"] = time.time() - t0
    return out


# ==========================================================================
# Section 11 -- the classes on the real population
# ==========================================================================
def classify(w):
    t0 = time.time()
    rows = {}
    for s in w.series:
        span = (s.epoch_ms[-1] - s.epoch_ms[0]) / DAY_MS
        admissible = (s.epoch_ms.size >= MIN_ELEMENT_SETS
                      and span >= MIN_SPAN_DAYS)
        ep2, frac, tested = v2_flags_for(s, w.sigma_n)
        ep1, _ = pg.drift_change_flags(s, w.sigma_n)
        fap, blocks = min_block_fap(s)
        sig = libration_signature(s)
        rows[s.norad] = {
            "norad": s.norad,
            "class": w.classes.get(s.norad),
            "elementSets": int(s.epoch_ms.size),
            "spanDays": float(span),
            "admissible": bool(admissible),
            "v1Flags": int(ep1.size),
            "v2Flags": int(ep2.size),
            "v2FlagEpochs": ep2,
            "evaluableFraction": frac,
            "evaluable": bool(frac >= 1.0 - MAX_NON_EVALUABLE_FRACTION),
            "minBlockFap": fap,
            "cadenceBlocks": blocks,
            "f1NoLine": bool(blocks > 0 and not (np.isfinite(fap)
                                                 and fap <= F1_EXCLUDE_FAP)),
            "f1NoLineFamilywise": bool(
                blocks > 0 and not (np.isfinite(fap)
                                    and fap <= sidak_block_alpha(blocks))),
            "sidakAlpha": sidak_block_alpha(blocks),
            "f2": sig,
        }
    for r in rows.values():
        r["inD"] = bool(r["class"] == "active" and r["admissible"]
                        and r["evaluable"] and r["v2Flags"] == 0)
        r["inF"] = bool(r["f1NoLine"] and r["f2"]["passed"])
        r["inI"] = bool(r["inD"] and r["inF"])
        r["inFw"] = bool(r["f1NoLineFamilywise"] and r["f2"]["passed"])
        r["inIw"] = bool(r["inD"] and r["inFw"])
    return rows, time.time() - t0


def pair_days(w, population):
    """T11's leak_check pair-day function, unchanged in form: days on which
    two members of the class are simultaneously stationed."""
    per_day = {}
    for s in w.series:
        if s.norad not in population:
            continue
        for d in w.stationed_days[s.norad].tolist():
            per_day[d] = per_day.get(d, 0) + 1
    return sum(k * (k - 1) // 2 for k in per_day.values())


def object_days(w, population):
    return int(sum(int(w.stationed_days[n].size) for n in population
                   if n in w.stationed_days))


def segments_of(w, population):
    return int(sum(len(w.segs[n]) for n in population if n in w.segs))


def leak_for(w, population, episodes, events, payload_ref):
    pd = pair_days(w, population)
    od = object_days(w, population)
    sg = segments_of(w, population)
    eps = sum(1 for e in episodes
              if e["a"] in population and e["b"] in population)
    evs = sum(1 for e in events if e in population)
    ep_rate = (eps / pd) if pd else float("nan")
    ev_rate = (evs / od) if od else float("nan")
    return {
        "objects": len(population),
        "pairExposureDays": pd, "episodes": eps,
        "episodeRatePerPairDay": ep_rate,
        "episodeLeakRatio": (ep_rate / payload_ref["episodeRatePerPairDay"]
                             if payload_ref and pd and
                             payload_ref["episodeRatePerPairDay"] else
                             float("nan")),
        "stationedObjectDays": od, "stationSegments": sg,
        "t8aEvents": evs, "eventRatePerObjectDay": ev_rate,
        "eventLeakRatio": (ev_rate / payload_ref["eventRatePerObjectDay"]
                           if payload_ref and od and
                           payload_ref["eventRatePerObjectDay"] else
                           float("nan")),
        "unevaluable": bool(pd == 0),
        "leakFree": bool(pd > 0 and od > 0 and eps == 0 and evs == 0),
    }


def load_jsonl(path):
    out = []
    with Path(path).open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                continue
            out.append(rec)
    return out


# ==========================================================================
# Section 14 -- the E1 re-expression
# ==========================================================================
def re_express_e1(rows, episodes, control):
    counts = {"provenStationKeeping": 0, "geometryOnly": 0, "unproven": 0}
    positive_v1 = 0
    positive_cadence = 0
    for e in episodes:
        a, b = e["a"], e["b"]
        t0, t1 = e["startMs"], e["endMs"]

        def flagged(n):
            r = rows.get(n)
            if r is None:
                return False
            ep = r["v2FlagEpochs"]
            return bool(np.any((ep >= t0) & (ep <= t1)))

        proven = flagged(a) and flagged(b)
        geometry = (a in control or b in control
                    or not rows.get(a, {}).get("evaluable", False)
                    or not rows.get(b, {}).get("evaluable", False))
        if proven:
            counts["provenStationKeeping"] += 1
        elif geometry:
            counts["geometryOnly"] += 1
        else:
            counts["unproven"] += 1
        if e.get("cadenceTestable"):
            positive_cadence += 1
        if (rows.get(a, {}).get("v1Flags", 0) > 0
                and rows.get(b, {}).get("v1Flags", 0) > 0):
            positive_v1 += 1
    counts["episodes"] = len(episodes)
    counts["addendumBothMembersHaveAnyV1Flag"] = positive_v1
    counts["addendumCadenceTestableEpisodes"] = positive_cadence
    return counts


# ==========================================================================
# Driver
# ==========================================================================
def analyze(db, archive_path, w, args):
    started = time.time()
    cat = args.docs / "persistent-pairs-20260922.jsonl"
    sha = pg.sha256_file(cat)
    if sha != CATALOGUE_SHA256:
        raise SystemExit(f"GATE G7: the T11 catalogue pin does not match. "
                         f"{sha} != {CATALOGUE_SHA256}")
    episodes = load_jsonl(cat)
    t8a_path = args.docs / "proximity-events-20260922.jsonl"
    t8a = load_jsonl(t8a_path)
    approachers = [int(e["approacherNorad"]) for e in t8a]

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
                      "t8aEvents": len(t8a)},
           "derivations": {
               "aDegPerDay2": A_DEG_PER_DAY2,
               "omega0RadPerDay": OMEGA_0_RAD_PER_DAY,
               "t0Days": T0_DAYS,
               "peakRateCoeffDegPerDay": PEAK_RATE_COEFF_DEG_PER_DAY,
               "stableLongitudesDeg": list(STABLE_LONGITUDES_DEG),
               "sigmaNDegPerDay": w.sigma_n,
               "fiveSigmaN": SIGMA_K * w.sigma_n,
               "t8aFloorDegPerDay": pg.BURN_FLOOR_DEG_PER_DAY,
               "freeMotionOverOneSampleDegPerDay":
                   A_DEG_PER_DAY2 * SAMPLE_SPACING_DAYS,
               "freeMotionOverBaselineDegPerDay":
                   A_DEG_PER_DAY2 * BASELINE_SAMPLES * SAMPLE_SPACING_DAYS,
               "ewBurnStepDegPerDay": EW_BURN_STEP}}

    print("validation BEFORE use ...", flush=True)
    out["validation"] = validate(w.sigma_n)
    print(f"  V1 {out['validation']['V1']['passed']} "
          f"V2 {out['validation']['V2']['passed']} "
          f"floor {out['validation']['V3']['detectionFloorDegPerDay']}",
          flush=True)

    print("classifying ...", flush=True)
    rows, secs = classify(w)
    out["classifyWallSeconds"] = secs

    d_set = {n for n, r in rows.items() if r["inD"]}
    f_set = {n for n, r in rows.items() if r["inF"]}
    i_set = d_set & f_set
    fw_set = {n for n, r in rows.items() if r["inFw"]}
    iw_set = d_set & fw_set
    payload = {n for n, r in rows.items() if r["class"] == "active"} - w.never
    ref = leak_for(w, payload, episodes, approachers, None)

    out["population"] = {
        "objects": len(rows),
        "payload": sum(1 for r in rows.values() if r["class"] == "active"),
        "cataloguePassive": sum(1 for r in rows.values()
                                if r["class"] == "passive"),
        "v1NeverManoeuvred": len(w.never),
        "v2ZeroFlag": sum(1 for r in rows.values() if r["v2Flags"] == 0),
        "v2ZeroFlagAdmissible": sum(1 for r in rows.values()
                                    if r["v2Flags"] == 0 and r["admissible"]),
        "nonEvaluable": sum(1 for r in rows.values() if not r["evaluable"]),
        "v1FlaggedButV2Clean": sum(1 for r in rows.values()
                                   if r["v1Flags"] > 0 and r["v2Flags"] == 0),
        "f1NoLine": sum(1 for r in rows.values() if r["f1NoLine"]),
        "f1NoLineFamilywise": sum(1 for r in rows.values()
                                  if r["f1NoLineFamilywise"]),
        "f2Passed": sum(1 for r in rows.values() if r["f2"]["passed"]),
        "f2FailingOnlyPeriodBound": sum(
            1 for r in rows.values()
            if r["f2"]["c1BoundMotion"] and r["f2"]["c2Turnaround"]
            and r["f2"]["c3Centred"] and r["f2"]["c4RateBound"]
            and not r["f2"]["c5PeriodBound"]),
        "classD": len(d_set), "classF": len(f_set), "classI": len(i_set),
        "classFfamilywise": len(fw_set), "classIfamilywise": len(iw_set)}

    out["reference"] = {"payloadNotNeverManoeuvred": ref}
    out["leak"] = {
        "D": leak_for(w, d_set, episodes, approachers, ref),
        "F": leak_for(w, f_set, episodes, approachers, ref),
        "I": leak_for(w, i_set, episodes, approachers, ref),
        "Fw": leak_for(w, fw_set, episodes, approachers, ref),
        "Iw": leak_for(w, iw_set, episodes, approachers, ref),
        "v1NeverManoeuvred": leak_for(w, set(w.never), episodes,
                                      approachers, ref),
        "bar": LEAK_BAR}
    out["leakNote"] = ("D, F and I are the registered classes. Fw and Iw use "
                       "the family-wise F1 threshold and are a "
                       "post-registration addition, labelled; both are leak-"
                       "tested and both are reported whatever they show.")

    even = {n for n in i_set if n % 2 == 0}
    odd = {n for n in i_set if n % 2 == 1}
    out["V4ParitySplit"] = {
        "even": leak_for(w, even, episodes, approachers, ref),
        "odd": leak_for(w, odd, episodes, approachers, ref),
        "instabilityFactor": V4_INSTABILITY_FACTOR}

    out["e1ReExpression"] = re_express_e1(rows, episodes, i_set)
    out["e1ReExpressionFamilywise"] = re_express_e1(rows, episodes, iw_set)

    prim = out["leak"]["I"]
    out["gates"] = {
        "G4": {"registeredMeaning": "the passive class does not exist",
               "pairExposureDays": prim["pairExposureDays"],
               "fired": bool(prim["unevaluable"])},
        "G5": {"registeredMeaning": "the passive class leaks",
               "bar": LEAK_BAR,
               "episodeLeakRatio": prim["episodeLeakRatio"],
               "eventLeakRatio": prim["eventLeakRatio"],
               "fired": bool(not prim["unevaluable"] and not prim["leakFree"])},
        "G6": {"registeredMeaning": ("the class rules do not do what they "
                                     "were derived to do"),
               "v1": out["validation"]["V1"]["passed"],
               "v2": out["validation"]["V2"]["passed"],
               "fired": bool(not (out["validation"]["V1"]["passed"]
                                  and out["validation"]["V2"]["passed"]))},
        "G7": {"registeredMeaning": "provenance", "catalogueSha256": sha,
               "fired": False}}

    out["classRows"] = [
        {k: v for k, v in r.items() if k != "v2FlagEpochs"}
        for r in rows.values() if r["inD"] or r["inF"] or r["inFw"]]
    out["sourceSha256"] = {
        "tools/geo_passive_control.py": pg.sha256_file(Path(__file__))}
    out["wallSeconds"] = time.time() - started
    return out


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
    out = analyze(db, archive_path, w, args)
    path = args.out / f"geo-passive-control-{args.date}-receipt.json"
    path.write_text(json.dumps(out, indent=1, default=pp._json_default) + "\n")
    print(json.dumps({"population": out["population"],
                      "leak": {k: {kk: v[kk] for kk in
                                   ("objects", "pairExposureDays", "episodes",
                                    "stationedObjectDays", "t8aEvents",
                                    "leakFree", "unevaluable")}
                               for k, v in out["leak"].items()
                               if isinstance(v, dict)},
                      "e1": out["e1ReExpression"],
                      "gates": {k: v["fired"] for k, v in
                                out["gates"].items()}},
                     indent=1, default=pp._json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
