#!/usr/bin/env python3
"""T22 -- the physics-scheduled null for geostationary east-west keeping.

Registration: `docs/t22-scheduled-null-preregistration-20260923.md`, committed
ALONE before this file existed. Every constant, screen, estimand, null and
decision rule below is fixed there; nothing here invents one.

WHAT THIS IS. Under the triaxial longitude acceleration

    d^2 lambda / dt^2 = acc(lambda) = -A sin 2(lambda - lambda_s)

a station-kept object follows a parabola between burns. Given the epoch of a
burn, the longitude and drift rate it leaves behind, and the band the object is
held in, the epoch at which the next burn is REQUIRED is the first exit of that
parabola from the band -- registration eq. (4). This module measures how often
a detected drift change arrives on that schedule.

WHAT THIS IS NOT. Not a detector, not an alert, not a statement about what any
operator did. Every burn here is another instrument's flag on element sets.
Angles and times only: no velocity-change, consumable, mass or lifetime
quantity is computed for any object, and no catalogue metadata column is read.

IMPORTED, NOT REIMPLEMENTED. The flag epochs, the chain rule, the acceleration
constant, the stable longitudes and the free-acceleration function all come
from the modules that own them; the test suite reads this file's source and
fails if any of those names is redefined here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import geo_passive_control as gpc  # noqa: E402
from tools import proximity_geo as pg  # noqa: E402
from tools import trigger_alarm as ta  # noqa: E402

REGISTRATION = "docs/t22-scheduled-null-preregistration-20260923.md"
REGISTRATION_COMMIT = "1f27ef5"
SEED = 20260923

DAY_MS = pg.DAY_MS

# ---------------------------------------------------------------------------
# Registration section 1.1 -- constants, imported and never retyped
# ---------------------------------------------------------------------------
A_DEG_PER_DAY2 = pg.LAMBDA_DDOT_MAX                  # 1.7006955627927864e-3
STABLE_LONGITUDES_DEG = pg.STABLE_LONGITUDES_DEG     # (75.1, -104.7)
SIGMA_N = 6.038533519066339e-4                       # T8a provenance, reused
MERGE_DAYS = ta.MERGE_DAYS                           # 5.0
BASELINE_SAMPLES = pg.BURN_BASELINE_SAMPLES          # 10
MAX_GAP_DAYS = pg.MAX_GAP_DAYS                       # 5.0

# Registration section 1.1 / 2.4 -- measured inputs carried from elsewhere
DEADBAND_DEG = 0.02633                # t10c v2 registered primary
DEADBAND_SYSTEMATIC = (0.025, 0.033)  # its published systematic range
SIGMA_DEADBAND_DEG = (DEADBAND_SYSTEMATIC[1] - DEADBAND_SYSTEMATIC[0]) / (2.0 * 1.96)
SIGMA_LAMBDA_DEG = 0.0066540706667427025             # t10c v2 section 1

# Registration section 3.4 -- screens
SLOT_WINDOW_DAYS = 45.0
SLOT_MIN_SAMPLES = 20
MIN_ACC_FRACTION = math.sin(math.radians(8.0))       # |a| >= A sin 8 deg
MAX_TAU_DAYS = 365.0
MAX_SLOT_SPREAD_DEG = 5.0

# Registration section 3.3 -- nulls
NULL_DRAWS = 1000
MC_DRAWS = 2000
MC_TOLERANCE = 0.10

EW_TYPE = "east-west keeping"
RELOCATION_PRIMARY = ("drift start",)
RELOCATION_UNION = ("drift start", "drift stop", "station acquisition")


# ===========================================================================
# Pure arithmetic -- every function below is offline-testable
# ===========================================================================
def slot_acceleration(longitude_deg):
    """acc(lambda) in deg/day^2, from the module that owns the constant."""
    return float(gpc.free_acceleration(np.asarray([float(longitude_deg)]))[0])


def optimal_cycle_days(deadband_deg, acceleration_deg_per_day2):
    """Registration eq. (6): the optimal one-burn cycle, 4 sqrt(D/|a|)."""
    a = abs(float(acceleration_deg_per_day2))
    if a <= 0.0:
        return float("inf")
    return 4.0 * math.sqrt(float(deadband_deg) / a)


def edge_cycle_days(rate_deg_per_day, acceleration_deg_per_day2):
    """Registration eq. (5): a burn at the exit edge, 2 |lambdadot| / |a|."""
    a = abs(float(acceleration_deg_per_day2))
    if a <= 0.0:
        return float("inf")
    return 2.0 * abs(float(rate_deg_per_day)) / a


def ols_fit(x, y):
    """Ordinary least squares, returning intercept, slope and their sigma.

    The sigma are the fit covariance scaled by the fit's own residual variance
    (registration 2.4), so an object whose elements are noisier gets a wider
    window and one whose elements are quiet gets a narrower one.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = x.size
    if n < 3:
        return (float("nan"),) * 4
    xbar = float(x.mean())
    sxx = float(((x - xbar) ** 2).sum())
    if sxx <= 0.0:
        return (float("nan"),) * 4
    slope = float(((x - xbar) * (y - y.mean())).sum() / sxx)
    intercept = float(y.mean() - slope * xbar)
    resid = y - (intercept + slope * x)
    s2 = float((resid ** 2).sum()) / (n - 2)
    var_slope = s2 / sxx
    var_intercept = s2 * (1.0 / n + xbar * xbar / sxx)
    return (intercept, slope,
            math.sqrt(max(var_intercept, 0.0)), math.sqrt(max(var_slope, 0.0)))


def _positive_roots(acceleration, rate, offset):
    """Strictly positive roots of 0.5 a t^2 + v t + offset = 0."""
    a = float(acceleration)
    v = float(rate)
    c = float(offset)
    if a == 0.0:
        if v == 0.0:
            return []
        t = -c / v
        return [t] if t > 0.0 else []
    disc = v * v - 2.0 * a * c
    # A double root is a tangency, not a crossing. The comparison is relative
    # to the discriminant's own terms so that it is scale-free; this is
    # floating-point hygiene on an exact algebraic condition, not a threshold
    # on a physical quantity.
    if disc <= 1e-12 * (v * v + abs(2.0 * a * c)):
        return []
    root = math.sqrt(disc)
    out = []
    for sign in (+1.0, -1.0):
        t = (-v + sign * root) / a
        if t > 0.0:
            out.append(t)
    return out


def exit_time_days(lambda_n, rate_n, acceleration, lambda_centre, deadband):
    """Registration eq. (4): the first exit of the parabola from the band.

    An EXIT is a crossing, not a touch: at the root the motion must carry the
    object OUT of the band. The optimal one-burn cycle is tangent to the far
    edge, and a tangency that returns the object to the band is not a burn --
    without this clause eq. (4) would return the half cycle of eq. (6) rather
    than the cycle, which is what `tests.test_scheduled_null` asserts.

    Returns (tau_days, edge_sign, reason). `tau_days` is nan when there is no
    strictly positive exit; `reason` names which registered case applies, so a
    pair is never silently dropped.
    """
    lam = float(lambda_n)
    centre = float(lambda_centre)
    band = float(deadband)
    if not (math.isfinite(lam) and math.isfinite(centre)
            and math.isfinite(float(rate_n)) and math.isfinite(float(acceleration))):
        return float("nan"), 0, "not-finite"
    if abs(lam - centre) > band:
        # The object is outside the band at the burn, so the first exit is not
        # strictly positive. Registration 3.4 screen 6 counts this case.
        return float("nan"), 0, "outside-band-at-burn"
    best_t, best_edge = float("inf"), 0
    for edge_sign in (+1.0, -1.0):
        edge = centre + edge_sign * band
        for t in _positive_roots(acceleration, rate_n, lam - edge):
            outward = float(acceleration) * t + float(rate_n)
            if edge_sign * outward <= 0.0:
                continue                      # a tangency or a re-entry
            if t < best_t:
                best_t, best_edge = t, int(edge_sign)
    if not math.isfinite(best_t):
        return float("nan"), 0, "no-positive-root"
    return best_t, best_edge, "ok"


def exit_time_sigma(tau_days, rate_n, acceleration, edge_sign,
                    sigma_rate, sigma_lambda_n, sigma_centre, sigma_deadband,
                    sigma_acceleration):
    """Registration eq. (7)-(12), by implicit differentiation of eq. (4).

    f(tau) = 0.5 a tau^2 + v tau + (lambda_n - lambda_e) = 0, so
    df/dtau = a tau + v = V, the drift rate AT the exit, and each partial is
    -(df/dx)/V. This is the same algebra as (7)-(11) written once instead of
    five times, and a test asserts the two agree at the exit edge.
    """
    tau = float(tau_days)
    speed = float(acceleration) * tau + float(rate_n)
    if not math.isfinite(speed) or speed == 0.0:
        return float("nan"), {}
    partials = {
        "rate": -tau / speed,
        "lambdaN": -1.0 / speed,
        "lambdaCentre": 1.0 / speed,
        "deadband": float(edge_sign) / speed,
        "acceleration": -0.5 * tau * tau / speed,
    }
    sigmas = {
        "rate": float(sigma_rate),
        "lambdaN": float(sigma_lambda_n),
        "lambdaCentre": float(sigma_centre),
        "deadband": float(sigma_deadband),
        "acceleration": float(sigma_acceleration),
    }
    total = 0.0
    for key, part in partials.items():
        total += (part * sigmas[key]) ** 2
    return math.sqrt(total), partials


def exit_time_sigma_montecarlo(lambda_n, rate_n, acceleration, lambda_centre,
                               deadband, sigma_rate, sigma_lambda_n,
                               sigma_centre, sigma_deadband, sigma_acceleration,
                               draws=MC_DRAWS, seed=SEED):
    """Registration check MC1: the propagation, done again by sampling."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(int(draws)):
        tau, _, reason = exit_time_days(
            lambda_n + rng.normal(0.0, sigma_lambda_n),
            rate_n + rng.normal(0.0, sigma_rate),
            acceleration + rng.normal(0.0, sigma_acceleration),
            lambda_centre + rng.normal(0.0, sigma_centre),
            deadband + rng.normal(0.0, sigma_deadband))
        if reason == "ok" and math.isfinite(tau):
            out.append(tau)
    if len(out) < 10:
        return float("nan")
    arr = np.asarray(out)
    return float(np.percentile(arr, 84.135) - np.percentile(arr, 15.865)) / 2.0


def wilson(successes, total, z=1.959963984540054):
    """Wilson score interval, the programme's standard."""
    n = int(total)
    k = int(successes)
    if n <= 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def odds_ratio(a, b, c, d, z=1.959963984540054):
    """OR = (a/b)/(c/d) with a log-scale interval.

    `a` off-schedule with the type, `b` off-schedule without, `c` on-schedule
    with, `d` on-schedule without. Haldane-Anscombe 0.5 is added to every cell
    if any cell is zero, and the correction is reported rather than hidden.
    """
    cells = [float(a), float(b), float(c), float(d)]
    corrected = any(x == 0.0 for x in cells)
    if corrected:
        cells = [x + 0.5 for x in cells]
    ca, cb, cc, cd = cells
    if cb <= 0 or cc <= 0 or cd <= 0:
        return {"oddsRatio": float("nan"), "ci": [float("nan")] * 2,
                "haldaneAnscombe": corrected}
    ratio = (ca / cb) / (cc / cd)
    se = math.sqrt(sum(1.0 / x for x in cells))
    return {"oddsRatio": ratio,
            "ci": [math.exp(math.log(ratio) - z * se),
                   math.exp(math.log(ratio) + z * se)],
            "haldaneAnscombe": corrected,
            "cells": {"offWith": a, "offWithout": b,
                      "onWith": c, "onWithout": d}}


def slot_sign_rule(centre_longitude_deg):
    """Registration eq. (14): the sign a slot-holding burn must carry.

    A burn that holds a slot pushes the drift rate AGAINST the acceleration,
    so the required sign is -sign(acc(lambda_c)).
    """
    acc = slot_acceleration(centre_longitude_deg)
    if acc == 0.0:
        return 0
    return -1 if acc > 0.0 else +1


# ===========================================================================
# Fixtures -- the synthetic populations the registration's proofs need
# ===========================================================================
class FixtureSeries:
    """The same shape the element series carry, for offline proofs."""

    __slots__ = ("norad", "epoch_ms", "lam", "lam_unwrapped", "drift")

    def __init__(self, norad, epoch_ms, lam, drift):
        self.norad = int(norad)
        self.epoch_ms = np.asarray(epoch_ms, dtype=np.float64)
        self.lam_unwrapped = np.asarray(lam, dtype=np.float64)
        self.lam = pg.wrap180(self.lam_unwrapped)
        self.drift = np.asarray(drift, dtype=np.float64)


def synthetic_deadband_cycle(norad, centre_deg, deadband_deg, acceleration,
                             years=8.0, spacing_days=0.5, noise=0.0, seed=SEED,
                             start_day=20000.0, apex_fraction=1.0):
    """A one-burn parabolic cycle with a PLANTED band and acceleration.

    Burn at the edge the acceleration pushes toward, sized so the apex just
    touches the far edge; the exact cycle is 4 sqrt(D/|a|). Returns the series
    and the true burn epochs in ms, so a proof can compare recovered epochs
    with planted ones.
    """
    rng = np.random.default_rng(seed)
    a = float(acceleration)
    band = float(deadband_deg)
    f = float(apex_fraction)
    sign = 1.0 if a > 0 else -1.0
    speed = math.sqrt(2.0 * abs(a) * (1.0 + f) * band)
    period = 2.0 * speed / abs(a)
    t = np.arange(0.0, float(years) * 365.25, float(spacing_days))
    phase = np.mod(t, period)
    rate0 = -sign * speed
    lam = (float(centre_deg) + sign * band + rate0 * phase
           + 0.5 * a * phase * phase)
    drift = rate0 + a * phase
    if noise:
        lam = lam + rng.normal(0.0, noise, size=lam.size)
        drift = drift + rng.normal(0.0, noise, size=drift.size)
    burns = np.arange(period, t[-1], period)
    return (FixtureSeries(norad, (t + start_day) * DAY_MS, lam, drift),
            (burns + start_day) * DAY_MS, period)


# ===========================================================================
# Chains, pairs and the prediction
# ===========================================================================
def chains_of(series, sigma_n=SIGMA_N):
    """The registered burn unit: T8d's flag chains, imported not rebuilt."""
    flags, sizes, bases = ta.flag_baselines(series, sigma_n)
    return ta.chain_flags(flags, sizes, bases)


def _window_indices(epoch_ms, t_from, t_to, count):
    lo = int(np.searchsorted(epoch_ms, t_from, side="left"))
    hi = int(np.searchsorted(epoch_ms, t_to, side="left"))
    if hi - lo < count:
        return None
    return lo, lo + count


def median_offset_fraction(apex_fraction):
    """Deviation V3, derived: where the MEDIAN longitude of a cycle sits.

    A one-burn cycle burns at `lambda_c + s D` with `s = sign(a)` and turns
    around at `lambda_c - s f D`, `f` the apex fraction (`f = 1` is the optimal
    cycle, which just touches the far edge). Then
    `lambda = lambda_c - s f D + (|a|/2) x^2` on `x in [-T/2, T/2]` with
    `T = 2 V / |a|` and `V = sqrt(2 |a| (1 + f) D)`. For a uniformly sampled
    cycle the median of `|x|` is `T/4`, so the median of `(|a|/2) x^2` is
    `V^2 / (8 |a|) = (1 + f) D / 4` and

        median(lambda) = lambda_c + s D [ (1 + f)/4 - f ],

    i.e. the band centre is `median + s D k` with `k = f - (1 + f)/4`.
    At `f = 1` that is exactly `D/2`.

    The registration fixed the PLAIN median as the centre, which is `k = 0`
    and corresponds to `f = 1/3`. On a cycle that reaches further than that,
    the plain median puts the burn outside its own band and admits nothing;
    which `k` is right depends on a waveform the archive does not hand over,
    so the run sweeps `k` and reports every arm.
    """
    f = float(apex_fraction)
    return f - (1.0 + f) / 4.0


CENTRE_OFFSET_DERIVED = median_offset_fraction(1.0)      # 0.5, optimal cycle
CENTRE_OFFSET_SWEEP = (0.0, 0.25, CENTRE_OFFSET_DERIVED)
"""`k = 0` is the registration's plain median; the sweep is reported whole."""


def pair_records(series, chains, deadband=DEADBAND_DEG,
                 sigma_acceleration=0.0, slot_types=None, predict=True,
                 centre_offset_fraction=0.0):
    """One record per consecutive chain pair on one object.

    Every quantity entering the prediction of `t_{n+1}` is read from element
    sets at epochs strictly before `t_{n+1}` (registration 3.4 screen 2); the
    fit window is truncated there and a proof asserts the truncation.
    """
    out = []
    epoch = series.epoch_ms
    if epoch.size < 3:
        return out
    spacing = float(np.median(np.diff(epoch))) / DAY_MS
    sigma_obs = spacing / math.sqrt(12.0)
    for i in range(len(chains) - 1):
        t_first, t_trig = float(chains[i][0]), float(chains[i][1])
        drift_change = float(chains[i][3])
        t_next = float(chains[i + 1][0])
        rec = {
            "norad": int(series.norad),
            "tBurnMs": t_first,
            "tTrigMs": t_trig,
            "tNextMs": t_next,
            "tNextTrigMs": float(chains[i + 1][1]),
            "observedIntervalDays": (t_next - t_first) / DAY_MS,
            "driftChangeDegPerDay": drift_change,
            "type": (slot_types or {}).get((int(series.norad), int(round(t_trig)))),
            "nextType": (slot_types or {}).get(
                (int(series.norad), int(round(float(chains[i + 1][1]))))),
            "admitted": False,
            "reason": None,
            "elementSpacingDays": spacing,
        }
        if not (t_next > t_trig):
            rec["reason"] = "next-chain-not-after"
            out.append(rec)
            continue

        window = _window_indices(epoch, t_trig, t_next, BASELINE_SAMPLES)
        if window is None:
            rec["reason"] = "too-few-element-sets"
            out.append(rec)
            continue
        lo, hi = window
        tau = (epoch[lo:hi] - t_trig) / DAY_MS
        rate0, acc_fit, sigma_rate, sigma_acc_fit = ols_fit(tau, series.drift[lo:hi])
        lam0, _, sigma_lam0, _ = ols_fit(tau, series.lam_unwrapped[lo:hi])
        rec.update({"rateDegPerDay": rate0, "accFitDegPerDay2": acc_fit,
                    "sigmaRate": sigma_rate, "sigmaAccFit": sigma_acc_fit,
                    "sigmaLambdaN": sigma_lam0, "lambdaNDeg": lam0})
        if not all(math.isfinite(v) for v in (rate0, acc_fit, lam0)):
            rec["reason"] = "fit-not-finite"
            out.append(rec)
            continue

        span = _window_indices(epoch, t_first, t_next, 2)
        if span is None:
            rec["reason"] = "too-few-element-sets"
            out.append(rec)
            continue
        i0 = int(np.searchsorted(epoch, t_first, side="left"))
        i1 = int(np.searchsorted(epoch, t_next, side="right"))
        if i1 - i0 >= 2 and float(np.max(np.diff(epoch[i0:i1]))) / DAY_MS > MAX_GAP_DAYS:
            rec["reason"] = "gap-inside-pair"
            out.append(rec)
            continue

        w0 = int(np.searchsorted(epoch, t_first - SLOT_WINDOW_DAYS * DAY_MS))
        w1 = int(np.searchsorted(epoch, t_first + SLOT_WINDOW_DAYS * DAY_MS))
        if w1 - w0 < SLOT_MIN_SAMPLES:
            rec["reason"] = "slot-window-too-thin"
            out.append(rec)
            continue
        median_longitude = float(np.median(series.lam_unwrapped[w0:w1]))
        acc_at_median = slot_acceleration(pg.wrap180(np.asarray([median_longitude]))[0])
        centre = median_longitude + (math.copysign(1.0, acc_at_median)
                                     * float(centre_offset_fraction) * deadband)
        sigma_centre = 1.253 * SIGMA_LAMBDA_DEG / math.sqrt(w1 - w0)
        rec["medianLongitudeDeg"] = median_longitude
        rec["lambdaCentreDeg"] = centre
        rec["centreOffsetFraction"] = float(centre_offset_fraction)
        rec["sigmaLambdaCentre"] = sigma_centre

        s0 = int(np.searchsorted(epoch, t_first - SLOT_WINDOW_DAYS * DAY_MS))
        s1 = int(np.searchsorted(epoch, t_next + SLOT_WINDOW_DAYS * DAY_MS))
        spread = float(np.percentile(series.lam_unwrapped[s0:s1], 75)
                       - np.percentile(series.lam_unwrapped[s0:s1], 25)) \
            if s1 - s0 >= 4 else float("inf")
        rec["slotSpreadDeg"] = spread

        acc = slot_acceleration(pg.wrap180(np.asarray([centre]))[0])
        rec["accDerivedDegPerDay2"] = acc
        rec["accRatio"] = acc_fit / acc if acc != 0.0 else float("nan")
        rec["signRuleRequired"] = slot_sign_rule(pg.wrap180(np.asarray([centre]))[0])
        rec["signRuleHeld"] = bool(
            rec["signRuleRequired"] != 0
            and math.copysign(1.0, drift_change) == rec["signRuleRequired"])

        if not predict:
            rec["reason"] = "pass-one"
            out.append(rec)
            continue
        if abs(acc) < MIN_ACC_FRACTION * A_DEG_PER_DAY2:
            rec["reason"] = "acceleration-too-small"
            out.append(rec)
            continue
        if spread > MAX_SLOT_SPREAD_DEG:
            rec["reason"] = "relocating"
            out.append(rec)
            continue

        tau_star, edge, reason = exit_time_days(lam0, rate0, acc, centre, deadband)
        rec["edgeSign"] = edge
        rec["exitReason"] = reason
        if reason != "ok" or not math.isfinite(tau_star):
            rec["reason"] = reason
            out.append(rec)
            continue
        if tau_star > MAX_TAU_DAYS:
            rec["reason"] = "horizon-beyond-a-year"
            rec["tauStarDays"] = tau_star
            out.append(rec)
            continue

        sigma_tau, _ = exit_time_sigma(
            tau_star, rate0, acc, edge, sigma_rate, sigma_lam0, sigma_centre,
            SIGMA_DEADBAND_DEG, sigma_acceleration)
        if not math.isfinite(sigma_tau):
            rec["reason"] = "sigma-not-finite"
            out.append(rec)
            continue
        window_days = 2.0 * math.sqrt(sigma_tau ** 2 + sigma_obs ** 2)
        # The parabola's origin is where its state was measured: the chain's
        # closing flag t_trig (registration 2.4), not its opening flag.
        predicted = t_trig + tau_star * DAY_MS
        rec.update({
            "tauStarDays": tau_star,
            "sigmaTauDays": sigma_tau,
            "sigmaObsDays": sigma_obs,
            "windowDays": window_days,
            "tPredMs": predicted,
            "errorDays": (t_next - predicted) / DAY_MS,
            "onSchedule": abs(t_next - predicted) / DAY_MS <= window_days,
            "admitted": True,
            "reason": "admitted",
        })
        out.append(rec)
    return out


# ===========================================================================
# Arms
# ===========================================================================
def _series_for(arrays, norads):
    keep = np.isin(arrays["norad"], np.fromiter(sorted(norads), dtype=np.int64))
    sub = {k: v[keep] for k, v in arrays.items()}
    return {s.norad: s for s in pg.build_series(sub)}


def load_types(path, norads):
    """(norad, epoch_ms) -> type, from the pinned arm-G ledger."""
    want = set(int(n) for n in norads)
    out = {}
    with open(path) as fh:
        for line in fh:
            if '"norad"' not in line:
                continue
            row = json.loads(line)
            nd = row.get("norad")
            if nd is None or int(nd) not in want:
                continue
            out[(int(nd), int(round(float(row["epochMs"]))))] = row.get("type")
    return out


def pass_one(series_by_norad, types):
    """Registration 2.4: sigma_a is MEASURED here. No estimand is computed."""
    ratios, diffs, arcs = [], [], 0
    for nd, s in series_by_norad.items():
        for rec in pair_records(s, chains_of(s), slot_types=types,
                                predict=False):
            acc = rec.get("accDerivedDegPerDay2")
            fit = rec.get("accFitDegPerDay2")
            if acc is None or fit is None or not math.isfinite(fit) or acc == 0.0:
                continue
            if abs(acc) < MIN_ACC_FRACTION * A_DEG_PER_DAY2:
                continue
            arcs += 1
            ratios.append(fit / acc)
            diffs.append(fit - acc)
    if arcs < 10:
        return {"arcs": arcs, "sigmaAcceleration": float("nan")}
    d = np.asarray(diffs)
    r = np.asarray(ratios)
    mad = float(np.median(np.abs(d - np.median(d))))
    return {
        "arcs": arcs,
        "sigmaAcceleration": 1.4826 * mad,
        "medianDifference": float(np.median(d)),
        "ratioQuantiles": {q: float(np.percentile(r, p)) for q, p in
                           (("p5", 5), ("p25", 25), ("p50", 50),
                            ("p75", 75), ("p95", 95))},
        "ratioRobustScatter": float(1.4826 * np.median(np.abs(r - np.median(r)))),
    }


def run_arm(series_by_norad, types, sigma_acceleration, deadband=DEADBAND_DEG,
            centre_offset_fraction=0.0):
    records = []
    for nd in sorted(series_by_norad):
        chains = chains_of(series_by_norad[nd])
        records.extend(pair_records(
            series_by_norad[nd], chains, deadband=deadband,
            sigma_acceleration=sigma_acceleration, slot_types=types,
            centre_offset_fraction=centre_offset_fraction))
    return records


def null_random_phase(admitted, seed=SEED, draws=NULL_DRAWS):
    """Registration N1: the same windows, the observed interval distribution."""
    if not admitted:
        return {"draws": 0}
    rng = np.random.default_rng(seed)
    observed = np.asarray([r["observedIntervalDays"] for r in admitted])
    windows = np.asarray([r["windowDays"] for r in admitted])
    fractions = np.empty(draws)
    for k in range(draws):
        drawn = rng.choice(observed, size=observed.size, replace=True)
        fractions[k] = float(np.mean(np.abs(observed - drawn) <= windows))
    return {"draws": draws, "median": float(np.median(fractions)),
            "p95": float(np.percentile(fractions, 95)),
            "mean": float(fractions.mean())}


def null_shuffle_within_object(admitted, seed=SEED, draws=NULL_DRAWS):
    """Registration N2: tau* shuffled among one object's own admitted pairs."""
    by_object = {}
    for r in admitted:
        by_object.setdefault(r["norad"], []).append(r)
    usable = {k: v for k, v in by_object.items() if len(v) >= 2}
    if not usable:
        return {"draws": 0, "pairs": 0}
    rng = np.random.default_rng(seed)
    fractions = np.empty(draws)
    total = sum(len(v) for v in usable.values())
    for k in range(draws):
        hits = 0
        for rows in usable.values():
            taus = rng.permutation([r["tauStarDays"] for r in rows])
            for row, tau in zip(rows, taus):
                predicted = row["tBurnMs"] + tau * DAY_MS
                hits += abs(row["tNextMs"] - predicted) / DAY_MS <= row["windowDays"]
        fractions[k] = hits / total
    return {"draws": draws, "pairs": total,
            "median": float(np.median(fractions)),
            "p95": float(np.percentile(fractions, 95))}


def enrichment(admitted, type_names):
    wanted = set(type_names)
    a = b = c = d = 0
    for r in admitted:
        has = r.get("nextType") in wanted
        if r["onSchedule"]:
            c += has
            d += not has
        else:
            a += has
            b += not has
    return odds_ratio(a, b, c, d)


def sign_summary(records):
    usable = [r for r in records if r.get("signRuleRequired") not in (None, 0)]
    held = sum(1 for r in usable if r.get("signRuleHeld"))
    p, lo, hi = wilson(held, len(usable))
    return {"chains": len(usable), "held": held,
            "fraction": p, "wilson95": [lo, hi]}


# ===========================================================================
# E5 -- the alarm lane's class-1 precision, re-scored
# ===========================================================================
def rescore_class_one(ledger_path, on_schedule_keys, unschedulable_note):
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
    removed, removed_hits = 0, 0
    kept_n, kept_k = 0, 0
    for aid, row in spoken.items():
        key = (int(row["norad"]), int(round(float(row["tTrigMs"]))))
        hit = resolutions.get(aid, {}).get("state") == "arrival"
        if key in on_schedule_keys:
            removed += 1
            removed_hits += hit
        else:
            kept_n += 1
            kept_k += hit
    p0, lo0, hi0 = wilson(before_k, before_n)
    p1, lo1, hi1 = wilson(kept_k, kept_n)
    return {
        "before": {"hits": before_k, "alerts": before_n,
                   "precision": p0, "wilson95": [lo0, hi0]},
        "after": {"hits": kept_k, "alerts": kept_n,
                  "precision": p1, "wilson95": [lo1, hi1]},
        "removed": removed, "removedHits": removed_hits,
        "note": unschedulable_note,
    }


# ===========================================================================
# Driver
# ===========================================================================
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def summarise(records, label):
    admitted = [r for r in records if r["admitted"]]
    reasons = {}
    for r in records:
        reasons[r["reason"] or "none"] = reasons.get(r["reason"] or "none", 0) + 1
    out = {"arm": label, "pairs": len(records), "admitted": len(admitted),
           "objects": len({r["norad"] for r in records}),
           "admittedObjects": len({r["norad"] for r in admitted}),
           "reasons": reasons}
    if admitted:
        for name, key in (("windowDays", "windowDays"),
                          ("tauStarDays", "tauStarDays"),
                          ("observedIntervalDays", "observedIntervalDays"),
                          ("errorDays", "errorDays")):
            arr = np.asarray([r[key] for r in admitted])
            out[name] = {q: float(np.percentile(arr, p)) for q, p in
                         (("p5", 5), ("p25", 25), ("p50", 50),
                          ("p75", 75), ("p95", 95))}
        ratio = np.asarray([r["tauStarDays"] / r["observedIntervalDays"]
                            for r in admitted if r["observedIntervalDays"] > 0])
        out["tauOverObserved"] = {"median": float(np.median(ratio))}
    return out


def branch_diagnostics(pairs):
    """POST-REGISTRATION, labelled. Not an estimand, gates nothing.

    Where the eleven days go: the exit edge the predictor picks, the drift rate
    against the one the flown interval needs, and the band that rate implies.
    Computed over the WHOLE admitted population so that every figure quoted in
    the results document is in the receipt rather than in a thinned file.
    """
    if not pairs:
        return {"label": "POST-REGISTRATION, not an estimand", "pairs": 0}
    rate = np.abs([r["rateDegPerDay"] for r in pairs])
    acc = np.abs([r["accDerivedDegPerDay2"] for r in pairs])
    observed = np.asarray([r["observedIntervalDays"] for r in pairs])
    tau = np.asarray([r["tauStarDays"] for r in pairs])
    offset = np.abs([r["lambdaNDeg"] - r["lambdaCentreDeg"] for r in pairs])
    span = np.asarray([(r["tTrigMs"] - r["tBurnMs"]) / DAY_MS for r in pairs])
    remaining = np.asarray([(r["tNextMs"] - r["tTrigMs"]) / DAY_MS for r in pairs])
    needed = observed * acc / 2.0
    side = np.asarray([math.copysign(1.0, r["accDerivedDegPerDay2"]) for r in pairs])
    near = np.asarray([r["edgeSign"] for r in pairs]) == side
    on = np.asarray([r["onSchedule"] for r in pairs])

    def quart(a):
        return {q: float(np.percentile(a, p)) for q, p in
                (("p25", 25), ("p50", 50), ("p75", 75))}

    def branch(mask, name):
        n = int(mask.sum())
        k = int(on[mask].sum())
        p, lo, hi = wilson(k, n)
        return {"edge": name, "pairs": n, "share": float(mask.mean()),
                "onSchedule": k, "fraction": p, "wilson95": [lo, hi],
                "medianTauDays": float(np.median(tau[mask])) if n else float("nan"),
                "medianObservedDays": float(np.median(observed[mask])) if n else float("nan")}

    return {
        "label": "POST-REGISTRATION, not an estimand, gates nothing",
        "pairs": len(pairs),
        "postBurnRateDegPerDay": quart(rate),
        "rateTheObservedCycleNeeds": quart(needed),
        "neededOverMeasured": quart(needed / rate),
        "deadbandImpliedByTheRateDeg": quart(rate ** 2 / (4.0 * acc)),
        "burnOffsetFromCentreDeg": quart(offset),
        "chainSpanDays": quart(span),
        "tauOverRemainingHorizon": quart(tau / remaining),
        "branches": [branch(near, "burn-side edge, a full cycle"),
                     branch(~near, "far edge, a half cycle")],
    }


def evaluate(carrier_records, passive_records, replay_records, replay_path):
    """Every estimand of registration section 3.3, for one centre estimator."""
    carrier_admitted = [r for r in carrier_records if r["admitted"]]
    ew = [r for r in carrier_admitted if r["type"] == EW_TYPE]
    e1_k = sum(1 for r in ew if r["onSchedule"])
    e1_p, e1_lo, e1_hi = wilson(e1_k, len(ew))
    n1 = null_random_phase(ew)
    n2 = null_shuffle_within_object(ew)

    passive_admitted = [r for r in passive_records if r["admitted"]]
    e2a_k = sum(1 for r in passive_admitted if r["onSchedule"])
    e2a_p, e2a_lo, e2a_hi = wilson(e2a_k, len(passive_admitted))
    if ew:
        lo_q = float(np.percentile([r["tauStarDays"] for r in ew], 25))
        hi_q = float(np.percentile([r["tauStarDays"] for r in ew], 75))
    else:
        lo_q = hi_q = float("nan")
    matched = [r for r in passive_admitted
               if math.isfinite(lo_q) and lo_q <= r["tauStarDays"] <= hi_q]
    e2b_k = sum(1 for r in matched if r["onSchedule"])
    e2b_p, e2b_lo, e2b_hi = wilson(e2b_k, len(matched))

    on_keys = {(r["norad"], int(round(r["tNextTrigMs"])))
               for r in replay_records
               if r["admitted"] and r["onSchedule"] and r["type"] == EW_TYPE}
    e5 = rescore_class_one(
        replay_path, on_keys,
        "an alert with no admitted east-west predecessor stays in the "
        "denominator: it is a labelled gap, not an on-schedule burn")

    clauses, verdict = {}, "PASS"
    if len(ew) < 200 or len(matched) < 50:
        verdict = "VOID -- UNDERPOWERED"
        clauses = {"carrierPairs": len(ew), "horizonMatchedPassivePairs": len(matched),
                   "bars": [200, 50]}
    else:
        p1 = bool(e1_p >= 0.80)
        p2 = bool(e1_lo > n1.get("p95", 1.0))
        p3 = bool(e2b_hi < e1_lo)
        clauses = {"P1_fraction_at_least_080": p1,
                   "P2_above_the_random_phase_null": p2,
                   "P3_passives_separated": p3}
        if not p2:
            verdict = "FAIL -- the physics adds nothing over a window of that width"
        elif not p3:
            verdict = "FAIL -- passives are on-schedule at the same rate"
        elif not p1:
            verdict = ("PARTIAL -- the schedule is measured and does not reach "
                       "the registered 0.80 bar")

    gap = float(np.median([r["observedIntervalDays"] for r in ew])) if ew else float("nan")
    window = float(np.median([r["windowDays"] for r in ew])) if ew else float("nan")
    error = float(np.median([r["errorDays"] for r in ew])) if ew else float("nan")
    spacing = float(np.median([r["elementSpacingDays"] for r in ew])) if ew else float("nan")

    return {
        "E1": {"onSchedule": e1_k, "pairs": len(ew), "fraction": e1_p,
               "wilson95": [e1_lo, e1_hi],
               "objects": len({r["norad"] for r in ew}),
               "medianObservedIntervalDays": gap,
               "medianWindowDays": window,
               "medianSignedErrorDays": error,
               "medianElementSpacingDays": spacing,
               "allAdmittedCarrierPairs": len(carrier_admitted)},
        "E1b": {"N1_randomPhase": n1, "N2_shuffleWithinObject": n2},
        "E2": {"a_pooledDeadband": {"onSchedule": e2a_k,
                                    "pairs": len(passive_admitted),
                                    "fraction": e2a_p,
                                    "wilson95": [e2a_lo, e2a_hi]},
               "b_horizonMatched": {"onSchedule": e2b_k, "pairs": len(matched),
                                    "fraction": e2b_p,
                                    "wilson95": [e2b_lo, e2b_hi],
                                    "tauRangeDays": [lo_q, hi_q]}},
        "E3": {"primary_driftStart": enrichment(carrier_admitted, RELOCATION_PRIMARY),
               "union": enrichment(carrier_admitted, RELOCATION_UNION),
               "unionNote": ("`drift stop` carries Gate F wherever it is "
                             "printed; `station acquisition`'s 0.751 is a "
                             "mapping corrected to match a measured outcome "
                             "and may not be scored as a successful "
                             "prediction")},
        "E4": {"carrier": sign_summary(carrier_records),
               "passive": sign_summary(passive_records),
               "carrierOnSchedule": sign_summary([r for r in carrier_admitted
                                                  if r["onSchedule"]]),
               "carrierOffSchedule": sign_summary([r for r in carrier_admitted
                                                   if not r["onSchedule"]])},
        "E5": e5,
        "postRegistrationBranchDiagnostics": branch_diagnostics(ew),
        "W1_defectRule": {
            "medianWindowDays": window,
            "medianObservedIntervalDays": gap,
            "fires": bool(window > gap / 3.0)
            if math.isfinite(window) and math.isfinite(gap) else None},
        "verdict": verdict,
        "verdictClauses": clauses,
        "arms": {"carrier": summarise(carrier_records, "carrier"),
                 "passive": summarise(passive_records, "passive"),
                 "replay": summarise(replay_records, "replay")},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=_REPO / "docs")
    ap.add_argument("--ledger", type=Path, required=True,
                    help="the manoeuvre-type library ledger, version 2")
    ap.add_argument("--replay", type=Path, required=True,
                    help="the alarm lane replay ledger at the everything setting")
    ap.add_argument("--date", default="20260923")
    args = ap.parse_args(argv)
    started = time.time()
    args.out.mkdir(parents=True, exist_ok=True)

    devset = json.loads((_REPO / "docs/matched-filter-devset-20260922.json").read_text())
    carriers = [int(n) for n in devset["eastWestCarriers"]]
    passives = [int(n) for n in devset["sameShellGeoPassiveControl"]]

    replay_norads = set()
    with open(args.replay) as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("record") == "assessment" and row.get("spoken") \
                    and row.get("class") == 1:
                replay_norads.add(int(row["norad"]))

    arrays, extract_meta = ta.load_cached_extract()
    every = set(carriers) | set(passives) | replay_norads
    series = _series_for(arrays, every)
    del arrays
    types = load_types(args.ledger, every)

    carrier_series = {n: series[n] for n in carriers if n in series}
    passive_series = {n: series[n] for n in passives if n in series}
    replay_series = {n: series[n] for n in sorted(replay_norads) if n in series}

    pass1 = pass_one(carrier_series, types)
    sigma_acc = pass1["sigmaAcceleration"]

    results, ledger_rows = {}, []
    arm_names = {0.0: "k=0.00 registered median",
                 0.25: "k=0.25",
                 CENTRE_OFFSET_DERIVED: "k=0.50 V3 derived centre"}
    for offset in CENTRE_OFFSET_SWEEP:
        name = arm_names[offset]
        carrier_records = run_arm(carrier_series, types, sigma_acc,
                                  centre_offset_fraction=offset)
        passive_records = run_arm(passive_series, types, sigma_acc,
                                  centre_offset_fraction=offset)
        replay_records = run_arm(replay_series, types, sigma_acc,
                                 centre_offset_fraction=offset)
        block = evaluate(carrier_records, passive_records, replay_records,
                         args.replay)
        block["centreOffsetFraction"] = offset
        results[name] = block
        for r in carrier_records + passive_records:
            if r["admitted"]:
                r = dict(r)
                r["centreArm"] = name
                ledger_rows.append(r)
        print(f"  arm {name}: carrier pairs "
              f"{block['E1']['pairs']}, verdict {block['verdict']}", flush=True)

    mc = []
    ew = [r for r in ledger_rows
          if r["centreArm"] == arm_names[CENTRE_OFFSET_DERIVED]
          and r["type"] == EW_TYPE]
    for r in ew[:200]:
        mc_sigma = exit_time_sigma_montecarlo(
            r["lambdaNDeg"], r["rateDegPerDay"], r["accDerivedDegPerDay2"],
            r["lambdaCentreDeg"], DEADBAND_DEG, r["sigmaRate"],
            r["sigmaLambdaN"], r["sigmaLambdaCentre"], SIGMA_DEADBAND_DEG,
            sigma_acc, draws=400)
        if math.isfinite(mc_sigma) and r["sigmaTauDays"] > 0:
            mc.append(mc_sigma / r["sigmaTauDays"])

    receipt = {
        "artifact": "t22-scheduled-null-receipt",
        "registration": REGISTRATION,
        "registrationCommit": REGISTRATION_COMMIT,
        "seed": SEED,
        "host": "pc", "executionMode": "CPU, one core",
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wallSeconds": time.time() - started,
        "inputs": {
            "extract": extract_meta,
            "ledger": {"path": str(args.ledger), "sha256": sha256_file(args.ledger)},
            "replay": {"path": str(args.replay), "sha256": sha256_file(args.replay)},
            "toolSha256": sha256_file(Path(__file__)),
            "carrierRoster": len(carriers), "passiveRoster": len(passives),
            "carrierSeries": len(carrier_series),
            "passiveSeries": len(passive_series),
            "replayObjects": len(replay_series),
        },
        "constants": {
            "A_degPerDay2": A_DEG_PER_DAY2,
            "stableLongitudesDeg": list(STABLE_LONGITUDES_DEG),
            "deadbandDeg": DEADBAND_DEG,
            "sigmaDeadbandDeg": SIGMA_DEADBAND_DEG,
            "sigmaLambdaDeg": SIGMA_LAMBDA_DEG,
            "sigmaN": SIGMA_N,
            "mergeDays": MERGE_DAYS,
            "baselineSamples": BASELINE_SAMPLES,
            "optimalCycleAtMaxAccelerationDays": optimal_cycle_days(
                DEADBAND_DEG, A_DEG_PER_DAY2),
            "accelerationNeededForA14DayCycle": 16.0 * DEADBAND_DEG / 196.0,
        },
        "passOne": pass1,
        "E0": {"ratioQuantiles": pass1.get("ratioQuantiles"),
               "ratioRobustScatter": pass1.get("ratioRobustScatter"),
               "sigmaAcceleration": sigma_acc,
               "arcs": pass1.get("arcs")},
        "passiveExposure": {
            "objectsWithSeries": len(passive_series),
            "elementSets": int(sum(s.epoch_ms.size for s in passive_series.values())),
            "objectDays": float(sum((s.epoch_ms[-1] - s.epoch_ms[0]) / DAY_MS
                                    for s in passive_series.values())),
            "chains": int(sum(len(chains_of(s)) for s in passive_series.values())),
        },
        "carrierExposure": {
            "objectsWithSeries": len(carrier_series),
            "elementSets": int(sum(s.epoch_ms.size for s in carrier_series.values())),
            "objectDays": float(sum((s.epoch_ms[-1] - s.epoch_ms[0]) / DAY_MS
                                    for s in carrier_series.values())),
            "chains": int(sum(len(chains_of(s)) for s in carrier_series.values())),
        },
        "MC1": {"checked": len(mc),
                "medianRatio": float(np.median(mc)) if mc else float("nan"),
                "tolerance": MC_TOLERANCE},
        "deviationV3": CENTRE_OFFSET_DERIVED,
        "results": results,
    }

    receipt_path = args.out / f"t22-scheduled-null-{args.date}-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=1, sort_keys=True,
                                       default=float))

    ledger_path = args.out / f"t22-scheduled-null-{args.date}.jsonl"
    step = max(1, len(ledger_rows) // 5000)
    with ledger_path.open("w") as fh:
        fh.write(json.dumps({
            "record": "provenance", "study": "T22 physics-scheduled null",
            "registration": REGISTRATION,
            "registrationCommit": REGISTRATION_COMMIT,
            "seed": SEED, "thinningStep": step, "rowsHeld": len(ledger_rows),
            "note": ("One row per ADMITTED pair, all three centre arms. Angles and "
                     "times only. A burn is a detected drift change, never a "
                     "record of what an operator did."),
        }) + "\n")
        for r in ledger_rows[::step]:
            fh.write(json.dumps(r, separators=(",", ":"), default=float) + "\n")

    print(json.dumps({"E0": receipt["E0"], "MC1": receipt["MC1"],
                      "results": results}, indent=1, default=float)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
