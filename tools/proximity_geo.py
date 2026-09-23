#!/usr/bin/env python3
"""T8a: GEO approach events from mean longitude and drift rate.

Every definition here is the one registered in
`docs/proximity-preregistration-20260922.md` and must not drift from it.
Section references below (prereg N) point at that document; where this module
makes an implementation choice the registration left open, the choice is
marked IMPL and justified in place.

The instrument is ownership-agnostic. Catalogue country/owner codes are
carried onto every event row as metadata and are read by **no** detector
branch. `object_type` is read only to assign the active/passive class of
prereg 3.2. Nothing here computes a delta-V, a mass, or any consumables
figure for any object.

Read-only against the archive (`PRAGMA query_only=1`), one sequential pass in
NORAD order so the clustered `element_set` table is read sequentially. CPU
only; no GPU stage is registered (prereg 8).

Stages
------
  extract   one pass over `element_set`, near-GEO rows only, to an npz cache
  analyze   longitudes, segments, events, nulls, repetition, lead times
  all       both
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
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline import orbit_campaigns, orbit_history  # noqa: E402
from pipeline.orbit_events import PASSIVE_TYPES  # noqa: E402  (prereg 3.2, borrowed)

# --------------------------------------------------------------------------
# Physical constants, derived in prereg 2. Quoted to the precision the
# derivation supports; recomputed here from WGS-84/IERS primitives so that a
# reader can check the arithmetic without leaving the file.
# --------------------------------------------------------------------------
MU_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6378.137
OMEGA_E_DEG_PER_DAY = 360.9856473              # sidereal rotation rate
OMEGA_E_RAD_PER_S = OMEGA_E_DEG_PER_DAY * math.pi / 180.0 / 86400.0
A_GEO_KM = (MU_KM3_S2 / OMEGA_E_RAD_PER_S ** 2) ** (1.0 / 3.0)   # prereg 2.1
DRIFT_PER_KM = -1.5 * OMEGA_E_DEG_PER_DAY / A_GEO_KM             # prereg 2.3
KM_PER_DEG_GEO = 2.0 * math.pi * A_GEO_KM / 360.0                # prereg 2.4
V_GEO_KM_S = math.sqrt(MU_KM3_S2 / A_GEO_KM)
# prereg 2.5 -- recorded so a reader can convert a deg/day figure. Never used.
DRIFT_PER_M_S = -DRIFT_PER_KM * (2.0 * A_GEO_KM / V_GEO_KM_S) / 1000.0
J22 = 1.8155e-6
_A_T_MAX_KM_S2 = 6.0 * J22 * (MU_KM3_S2 / A_GEO_KM ** 2) * (EARTH_RADIUS_KM / A_GEO_KM) ** 2
LAMBDA_DDOT_MAX = 3.0 * OMEGA_E_DEG_PER_DAY * _A_T_MAX_KM_S2 / V_GEO_KM_S * 86400.0  # prereg 2.6
STABLE_LONGITUDES_DEG = (75.1, -104.7)                            # prereg 2.6

# --------------------------------------------------------------------------
# Registered constants (docs/proximity-preregistration-20260922.md)
# --------------------------------------------------------------------------
SEED = 20260922                       # prereg 6.1, 8
N_PERMUTATIONS = 1000                 # prereg 6.1

MM_MIN_REV_DAY = 0.95                 # prereg 3.1
MM_MAX_REV_DAY = 1.05
ECC_MAX = 0.01
INC_MAX_DEG = 25.0

X_PRIMARY_DEG = 0.1                   # prereg 4
D_PRIMARY_DAYS = 30.0
X_SENSITIVITY = (0.05, 0.2, 0.5)
D_SENSITIVITY = (7.0, 14.0)
X_FAR_DEG = 2.0
T_LOOK_DAYS = 180.0
ATTRIBUTION_SHARE = 0.8
MAX_GAP_DAYS = 5.0                    # prereg 2.7 / 4
LOITER_MIN_OCCUPANCY_PER_DAY = 0.4    # prereg 2.7 / 4

STATION_HALF_WIDTH_DEG = 0.3          # prereg 5.3
STATION_MIN_DAYS = 30.0
BURN_BASELINE_SAMPLES = 10            # prereg 5.5
BURN_SIGMA_K = 5.0
BURN_FLOOR_DEG_PER_DAY = 0.010
GATE_A_SIGMA_MAX = X_PRIMARY_DEG / 10.0 / D_PRIMARY_DAYS   # prereg 5.4/10: 0.1deg/10 over 30d
GATE_B_PASSIVE_FRACTION = 0.02        # prereg 6.2 / 10
GATE_D_MIN_REPEATERS = 10             # prereg 10
FDR_Q = 0.05                          # prereg 7

DAY_MS = 86400000.0
SCALE_ANGLE = 1e4
SCALE_MM = 1e8
SCALE_ECC = 1e8

# IMPL: candidate-pair screen. A generous superset of every registered arm --
# 1.5x the widest X, and 0.8x the shortest D -- so the screen can only ever
# admit pairs, never reject a true event. Every survivor is then decided by
# the exact registered arithmetic on the union of element epochs (prereg 4).
SCREEN_RADIUS_DEG = 1.5 * max((X_PRIMARY_DEG,) + X_SENSITIVITY)
SCREEN_MIN_DAYS = 0.8 * min((D_PRIMARY_DAYS,) + D_SENSITIVITY)


# ==========================================================================
# prereg 2.2 -- mean longitude
# ==========================================================================
def gmst_deg(epoch_ms):
    """Greenwich Mean Sidereal Time, IAU-1982, degrees.

    The rotation SGP4's TEME -> pseudo-Earth-fixed conversion uses, and
    therefore the one consistent with a TLE's RAAN (prereg 2.2). UT1 is
    approximated by UTC and polar motion is neglected; both are registered
    in prereg 2.2 as errors below 0.0038 deg.
    """
    jd = np.asarray(epoch_ms, dtype=np.float64) / DAY_MS + 2440587.5
    t = (jd - 2451545.0) / 36525.0
    sec = (67310.54841
           + (876600.0 * 3600.0 + 8640184.812866) * t
           + 0.093104 * t * t
           - 6.2e-6 * t * t * t)
    return np.mod(sec / 240.0, 360.0)


def wrap180(deg):
    """Wrap to (-180, +180]."""
    out = np.mod(np.asarray(deg, dtype=np.float64) + 180.0, 360.0) - 180.0
    return np.where(out == -180.0, 180.0, out)


def mean_longitude_deg(raan_deg, arg_perigee_deg, mean_anomaly_deg, epoch_ms):
    """lambda = RAAN + argp + M - theta_G, wrapped (prereg 2.2).

    Carries no eccentricity or inclination periodic content by construction:
    it is a slot coordinate, NOT a position and NOT a miss distance
    (prereg 1.1).
    """
    return wrap180(np.asarray(raan_deg, dtype=np.float64)
                   + np.asarray(arg_perigee_deg, dtype=np.float64)
                   + np.asarray(mean_anomaly_deg, dtype=np.float64)
                   - gmst_deg(epoch_ms))


def drift_rate_deg_per_day(mean_motion_rev_day):
    """ddot = 360 n - omega_E, eastward positive (prereg 2.3)."""
    return 360.0 * np.asarray(mean_motion_rev_day, dtype=np.float64) - OMEGA_E_DEG_PER_DAY


def semi_major_offset_km(drift_deg_per_day):
    """Interpretive only (prereg 2.3). Never inside a detector decision."""
    return np.asarray(drift_deg_per_day, dtype=np.float64) / DRIFT_PER_KM


def unwrap_longitude(lam_deg, epoch_ms, drift_deg_per_day):
    """Unwrap lambda along one object's series (prereg 5.1).

    IMPL: the unwrap is drift-informed rather than naive. A naive
    `np.unwrap` assumes the true step is the one smaller than 180 deg, which
    is false for a fast drifter across a long gap (prereg 9.2). Here the step
    predicted by the object's own mean motion is removed first, the residual
    is wrapped, and the prediction is added back -- so the unwrap is wrong
    only if the element sets disagree with their own mean motion by half a
    revolution, which no gap in this archive can produce at GEO drift rates.
    """
    lam = np.asarray(lam_deg, dtype=np.float64)
    if lam.size == 0:
        return lam.copy()
    dt_days = np.diff(np.asarray(epoch_ms, dtype=np.float64)) / DAY_MS
    dd = np.asarray(drift_deg_per_day, dtype=np.float64)
    predicted = 0.5 * (dd[:-1] + dd[1:]) * dt_days
    residual = wrap180(np.diff(lam) - predicted)
    out = np.empty_like(lam)
    out[0] = lam[0]
    np.cumsum(predicted + residual, out=out[1:])
    out[1:] += lam[0]
    return out


def libration_zone_half_width_deg(x_deg, d_days):
    """Half-width around a stable longitude in which the passive-exclusion
    argument of prereg 2.6 does NOT hold. `None` means the bound is void
    everywhere at this (X, D)."""
    s = 2.0 * x_deg / (LAMBDA_DDOT_MAX * d_days * d_days)
    if s >= 1.0:
        return None
    return math.degrees(math.asin(s)) / 2.0


def in_libration_zone(lon_deg, x_deg, d_days):
    half = libration_zone_half_width_deg(x_deg, d_days)
    if half is None:
        return np.ones(np.shape(lon_deg), dtype=bool)
    lon = np.asarray(lon_deg, dtype=np.float64)
    flag = np.zeros(lon.shape, dtype=bool)
    for stable in STABLE_LONGITUDES_DEG:
        flag |= np.abs(wrap180(lon - stable)) <= half
    return flag


# ==========================================================================
# Stage 1 -- extract
# ==========================================================================
_SELECT = ("SELECT norad, epoch_ms, mean_motion_q, eccentricity_q, inclination_q, "
           "raan_q, arg_perigee_q, mean_anomaly_q FROM element_set")


def extract(db, out_dir, limit_rows=None, progress_every=20_000_000):
    """One sequential pass; keep near-GEO element sets only (prereg 3.1)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    mm_lo = int(round(MM_MIN_REV_DAY * SCALE_MM))
    mm_hi = int(round(MM_MAX_REV_DAY * SCALE_MM))
    ecc_hi = int(round(ECC_MAX * SCALE_ECC))
    inc_hi = int(round(INC_MAX_DEG * SCALE_ANGLE))

    cols = [[] for _ in range(8)]
    seen = 0
    started = time.time()
    for row in db.execute(_SELECT):
        seen += 1
        if not (mm_lo <= row[2] <= mm_hi):
            continue
        if row[3] > ecc_hi or row[4] > inc_hi:
            continue
        for i in range(8):
            cols[i].append(row[i])
        if limit_rows is not None and seen >= limit_rows:
            break
        if progress_every and seen % progress_every == 0:
            print(f"  ... {seen:,} rows scanned, {len(cols[0]):,} kept, "
                  f"{time.time() - started:.0f}s", flush=True)

    arrays = {
        "norad": np.asarray(cols[0], dtype=np.int64),
        "epoch_ms": np.asarray(cols[1], dtype=np.int64),
        "mean_motion": np.asarray(cols[2], dtype=np.float64) / SCALE_MM,
        "eccentricity": np.asarray(cols[3], dtype=np.float64) / SCALE_ECC,
        "inclination": np.asarray(cols[4], dtype=np.float64) / SCALE_ANGLE,
        "raan": np.asarray(cols[5], dtype=np.float64) / SCALE_ANGLE,
        "arg_perigee": np.asarray(cols[6], dtype=np.float64) / SCALE_ANGLE,
        "mean_anomaly": np.asarray(cols[7], dtype=np.float64) / SCALE_ANGLE,
    }
    meta = {
        "rowsScanned": seen,
        "rowsKept": int(arrays["norad"].size),
        "objectsKept": int(np.unique(arrays["norad"]).size),
        "wallSeconds": time.time() - started,
    }
    np.savez(out_dir / "near-geo.npz", **arrays)
    (out_dir / "extract-meta.json").write_text(json.dumps(meta, indent=2))
    return arrays, meta


def object_metadata(db, norads):
    """Catalogue metadata, carried onto event rows, read by no detector
    branch except `object_type` for the class of prereg 3.2."""
    out = {}
    for norad in norads:
        row = db.execute(
            "SELECT name, object_id, object_type, country, launch_date "
            "FROM object WHERE norad = ?", (int(norad),)).fetchone()
        out[int(norad)] = {
            "name": row[0] if row else None,
            "objectId": row[1] if row else None,
            "objectType": row[2] if row else None,
            "country": row[3] if row else None,
            "launchDate": row[4] if row else None,
        }
    return out


def class_of(object_type):
    if not object_type:
        return None
    upper = object_type.upper()
    if upper == "PAYLOAD":
        return "active"
    if upper in {t.upper() for t in PASSIVE_TYPES}:
        return "passive"
    return None


# ==========================================================================
# Per-object series
# ==========================================================================
class Series:
    __slots__ = ("norad", "epoch_ms", "lam", "lam_unwrapped", "drift",
                 "ecc", "inc", "raan", "day_index", "grid_lo", "grid")

    def __init__(self, norad, epoch_ms, mean_motion, ecc, inc, raan, argp, ma):
        order = np.argsort(epoch_ms, kind="stable")
        self.norad = int(norad)
        self.epoch_ms = epoch_ms[order]
        self.ecc = ecc[order]
        self.inc = inc[order]
        # Retained, epoch-ordered like every other channel. The mean longitude
        # below consumes RAAN and then throws it away; the orbit POLE needs it
        # back, and rebuilding it from lam would not be the same number.
        self.raan = raan[order]
        self.drift = drift_rate_deg_per_day(mean_motion[order])
        self.lam = mean_longitude_deg(raan[order], argp[order], ma[order], self.epoch_ms)
        self.lam_unwrapped = unwrap_longitude(self.lam, self.epoch_ms, self.drift)
        self.grid_lo = None
        self.grid = None


def build_series(arrays):
    norad = arrays["norad"]
    order = np.argsort(norad, kind="stable")
    sorted_norad = norad[order]
    bounds = np.searchsorted(sorted_norad, np.unique(sorted_norad), side="left")
    bounds = np.append(bounds, sorted_norad.size)
    out = []
    for k in range(bounds.size - 1):
        idx = order[bounds[k]:bounds[k + 1]]
        if idx.size < 2:
            continue
        out.append(Series(sorted_norad[bounds[k]],
                          arrays["epoch_ms"][idx], arrays["mean_motion"][idx],
                          arrays["eccentricity"][idx], arrays["inclination"][idx],
                          arrays["raan"][idx], arrays["arg_perigee"][idx],
                          arrays["mean_anomaly"][idx]))
    return out


def interpolate(epoch_ms, lam_unwrapped, targets_ms, max_gap_days=MAX_GAP_DAYS):
    """Linear interpolation of lambda onto `targets_ms`, refused across any
    element-set gap longer than `max_gap_days` (prereg 4). Refused points come
    back NaN and are counted by the caller, never silently dropped."""
    t = np.asarray(epoch_ms, dtype=np.float64)
    y = np.asarray(lam_unwrapped, dtype=np.float64)
    q = np.asarray(targets_ms, dtype=np.float64)
    out = np.full(q.shape, np.nan)
    if t.size < 2:
        return out
    j = np.searchsorted(t, q, side="right") - 1
    inside = (j >= 0) & (j <= t.size - 1)
    exact = inside & (q == t[np.clip(j, 0, t.size - 1)])
    out[exact] = y[j[exact]]
    span = inside & ~exact & (j <= t.size - 2)
    if np.any(span):
        js = j[span]
        gap_days = (t[js + 1] - t[js]) / DAY_MS
        ok = gap_days <= max_gap_days
        idx = np.where(span)[0][ok]
        js = js[ok]
        frac = (q[idx] - t[js]) / (t[js + 1] - t[js])
        out[idx] = y[js] + frac * (y[js + 1] - y[js])
    return out


def build_daily_grid(series_list):
    """Daily grid of wrapped lambda per object (IMPL: a screening index and
    the segmentation carrier; every event is decided by the exact
    union-of-epochs arithmetic of prereg 4, never by the grid)."""
    lo = min(int(s.epoch_ms[0] // int(DAY_MS)) for s in series_list)
    hi = max(int(s.epoch_ms[-1] // int(DAY_MS)) for s in series_list)
    days = np.arange(lo, hi + 1, dtype=np.int64)
    targets = days.astype(np.float64) * DAY_MS + 0.5 * DAY_MS
    for s in series_list:
        i0 = int(s.epoch_ms[0] // int(DAY_MS)) - lo
        i1 = int(s.epoch_ms[-1] // int(DAY_MS)) - lo
        sub = targets[i0:i1 + 1]
        s.grid_lo = i0
        s.grid = interpolate(s.epoch_ms, s.lam_unwrapped, sub)
    return lo, days.size


def station_segments(series):
    """Maximal intervals with |lambda - median| <= 0.3 deg throughout and
    length >= 30 d (prereg 5.3). Returns [(i0, i1)] as grid offsets.

    IMPL: grown one day at a time against a sorted window, so max, min and
    median are all O(1) reads and the registered median condition is checked
    exactly at every step rather than by trimming a too-long candidate.
    """
    import bisect
    g = series.grid
    n = g.size
    half = STATION_HALF_WIDTH_DEG
    segs = []
    i = 0
    while i < n:
        if not np.isfinite(g[i]):
            i += 1
            continue
        window = [float(g[i])]
        j = i
        while j + 1 < n and np.isfinite(g[j + 1]):
            v = float(g[j + 1])
            k = bisect.bisect_left(window, v)
            window.insert(k, v)
            m = len(window)
            med = (window[m // 2] if m % 2 else
                   0.5 * (window[m // 2 - 1] + window[m // 2]))
            if window[-1] - med > half or med - window[0] > half:
                window.pop(k)
                break
            j += 1
        if j - i + 1 >= STATION_MIN_DAYS:
            segs.append((i, j))
            i = j + 1
        else:
            i += 1
    return segs


# ==========================================================================
# prereg 5.4/5.5 -- noise calibration and drift-change flags
# ==========================================================================
def calibrate_sigma_n(series_list, classes, segs):
    """sigma_n: MAD of consecutive ddot_n differences inside stationed
    segments, scaled by 1.4826/sqrt(2), pooled over the active class
    (prereg 5.4). Measured, never assumed."""
    diffs = []
    for s in series_list:
        if classes.get(s.norad) != "active" or s.grid is None:
            continue
        for i0, i1 in segs[s.norad]:
            t0 = (s.grid_lo + i0) * DAY_MS
            t1 = (s.grid_lo + i1 + 1) * DAY_MS
            k0, k1 = np.searchsorted(s.epoch_ms, [t0, t1])
            if k1 - k0 >= 3:
                diffs.append(np.diff(s.drift[k0:k1]))
    if not diffs:
        return float("nan"), 0
    pooled = np.concatenate(diffs)
    mad = np.median(np.abs(pooled - np.median(pooled)))
    return float(mad * 1.4826 / math.sqrt(2.0)), int(pooled.size)


def drift_change_flags(series, sigma_n):
    """Flag epochs where ddot_n departs from its trailing median by more than
    max(5 sigma_n, 0.010 deg/day) at two consecutive element sets
    (prereg 5.5). The flag time is the epoch of the SECOND one, because that
    is the first instant a causal observer possessed the evidence."""
    d = series.drift
    n = d.size
    thresh = max(BURN_SIGMA_K * sigma_n, BURN_FLOOR_DEG_PER_DAY)
    if n < BURN_BASELINE_SAMPLES + 2:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    base = np.empty(n)
    base[:] = np.nan
    w = BURN_BASELINE_SAMPLES
    windows = np.lib.stride_tricks.sliding_window_view(d[:n - 1], w)
    base[w:] = np.median(windows[:n - w], axis=1)
    dev = np.abs(d - base)
    hot = np.isfinite(dev) & (dev > thresh)
    confirmed = np.where(hot[:-1] & hot[1:])[0] + 1
    return series.epoch_ms[confirmed], d[confirmed] - base[confirmed - 1]


# ==========================================================================
# prereg 4 -- the event definition, exact, on the union of element epochs
# ==========================================================================
def _runs(mask):
    if mask.size == 0:
        return []
    padded = np.concatenate(([False], mask, [False]))
    edges = np.diff(padded.astype(np.int8))
    return list(zip(np.where(edges == 1)[0], np.where(edges == -1)[0] - 1))


def pair_separation(a, b, min_days):
    """Mean-longitude separation of a pair on the union of their element
    epochs (prereg 4), computed once and reused by every registered arm."""
    lo = max(a.epoch_ms[0], b.epoch_ms[0])
    hi = min(a.epoch_ms[-1], b.epoch_ms[-1])
    if hi - lo < min_days * DAY_MS:
        return None
    ea = a.epoch_ms[(a.epoch_ms >= lo) & (a.epoch_ms <= hi)]
    eb = b.epoch_ms[(b.epoch_ms >= lo) & (b.epoch_ms <= hi)]
    union = np.union1d(ea, eb)
    if union.size < 3:
        return None
    la = interpolate(a.epoch_ms, a.lam_unwrapped, union)
    lb = interpolate(b.epoch_ms, b.lam_unwrapped, union)
    keep = np.isfinite(la) & np.isfinite(lb)
    if keep.sum() < 3:
        return None
    t = union[keep]
    la = la[keep]
    lb = lb[keep]
    sep = wrap180(la - lb)
    return t, la, lb, sep, np.abs(sep)


def events_from_separation(a, b, packed, x_deg, d_days, stats=None):
    """The registered event definition of prereg 4, applied to one arm.

    `stats`, when given, counts the loiters rejected at each registered
    criterion, so a rejection is reported rather than silently dropped.
    """
    def _rej(key):
        if stats is not None:
            stats[key] = stats.get(key, 0) + 1

    t, la, lb, sep, abs_sep = packed
    if (t[-1] - t[0]) < d_days * DAY_MS:
        return [], False
    events = []
    standing = bool(np.all(abs_sep <= x_deg))
    for i0, i1 in _runs(abs_sep <= x_deg):
        days = (t[i1] - t[i0]) / DAY_MS
        if days < d_days:
            _rej('loiterTooShort')
            continue
        if np.max(np.diff(t[i0:i1 + 1])) / DAY_MS > MAX_GAP_DAYS:
            _rej('loiterGapTooLong')
            continue
        if (i1 - i0 + 1) < LOITER_MIN_OCCUPANCY_PER_DAY * days:
            _rej('loiterUnderOccupied')
            continue
        # prior separation (prereg 4.2)
        look = (t >= t[i0] - T_LOOK_DAYS * DAY_MS) & (t < t[i0])
        far = np.where(look & (abs_sep >= X_FAR_DEG))[0]
        if far.size == 0:
            _rej('noPriorSeparation')
            continue
        k0 = int(far[-1])
        # approacher motion (prereg 4.3)
        move_a = abs(la[i0] - la[k0])
        move_b = abs(lb[i0] - lb[k0])
        relative = abs(sep[k0] - sep[i0])
        need = max(ATTRIBUTION_SHARE * relative, X_FAR_DEG - x_deg)
        a_ok = move_a >= need
        b_ok = move_b >= need
        if a_ok and b_ok:
            attribution = "ambiguous"
            approacher, target = a, b
        elif a_ok:
            attribution = "resolved"
            approacher, target = a, b
        elif b_ok:
            attribution = "resolved"
            approacher, target = b, a
        else:
            # Neither object moved 80% of the relative change: a symmetric
            # mutual approach. prereg 4.3 assigns no approacher, so this is
            # not an event. Counted, never silently dropped.
            _rej("attributionUnresolved")
            continue
        # departure (prereg 4.4)
        after = np.where((t > t[i1]) & (abs_sep >= X_FAR_DEG))[0]
        depart_ms = int(t[after[0]]) if after.size else None
        idx_close = i0 + int(np.argmin(abs_sep[i0:i1 + 1]))
        events.append({
            "approacherNorad": approacher.norad,
            "targetNorad": target.norad,
            "attribution": attribution,
            "transferStartMs": int(t[k0]),
            "arrivalMs": int(t[i0]),
            "loiterEndMs": int(t[i1]),
            "departureMs": depart_ms,
            "loiterDays": float(days),
            "loiterSamples": int(i1 - i0 + 1),
            "closestSeparationDeg": float(abs_sep[idx_close]),
            "closestSeparationKm": float(abs_sep[idx_close] * KM_PER_DEG_GEO),
            "medianSeparationDeg": float(np.median(abs_sep[i0:i1 + 1])),
            "separationAtTransferStartDeg": float(abs_sep[k0]),
            "approacherMotionDeg": float(move_a if approacher is a else move_b),
            "targetMotionDeg": float(move_b if approacher is a else move_a),
            "transferDays": float((t[i0] - t[k0]) / DAY_MS),
            "loiterLongitudeDeg": float(wrap180(np.median(la[i0:i1 + 1])
                                                if approacher is a
                                                else np.median(lb[i0:i1 + 1]))),
        })
    return events, standing


def pair_events(a, b, x_deg, d_days, stats=None):
    """Convenience wrapper: separation then one arm."""
    packed = pair_separation(a, b, d_days)
    if packed is None:
        return [], None
    return events_from_separation(a, b, packed, x_deg, d_days, stats=stats)


def candidate_pairs(series_list, grid_lo, n_days):
    """IMPL screen (see SCREEN_RADIUS_DEG). Counts, per day, how many days a
    pair spends within the screen radius; survivors go to the exact pass.

    Flat arrays rather than per-day Python lists: the grid holds tens of
    millions of object-days and a list of tuples that size does not fit in a
    sensible amount of memory.
    """
    days_l, lons_l, ids_l = [], [], []
    for si, s in enumerate(series_list):
        finite = np.where(np.isfinite(s.grid))[0]
        if finite.size == 0:
            continue
        days_l.append((finite + s.grid_lo).astype(np.int32))
        lons_l.append(wrap180(s.grid[finite]).astype(np.float32))
        ids_l.append(np.full(finite.size, si, dtype=np.int32))
    if not days_l:
        return [], 0
    days = np.concatenate(days_l)
    lons = np.concatenate(lons_l)
    ids = np.concatenate(ids_l)
    order = np.lexsort((lons, days))
    days, lons, ids = days[order], lons[order], ids[order]
    edges = np.searchsorted(days, np.arange(days[0], days[-1] + 2))
    counts = {}
    radius = SCREEN_RADIUS_DEG
    for k in range(edges.size - 1):
        lo, hi = int(edges[k]), int(edges[k + 1])
        m = hi - lo
        if m < 2:
            continue
        dl = lons[lo:hi]
        di = ids[lo:hi]
        # neighbours in sorted longitude
        j_end = np.searchsorted(dl, dl + radius, side="right")
        for i in range(m):
            for j in range(i + 1, int(j_end[i])):
                a, b = int(di[i]), int(di[j])
                key = (a, b) if a < b else (b, a)
                counts[key] = counts.get(key, 0) + 1
        # wrap-around at +/-180
        i = 0
        while i < m and dl[i] + 360.0 - dl[-1] <= radius:
            j = m - 1
            while j > i and dl[i] + 360.0 - dl[j] <= radius:
                a, b = int(di[i]), int(di[j])
                key = (a, b) if a < b else (b, a)
                counts[key] = counts.get(key, 0) + 1
                j -= 1
            i += 1
    return [k for k, v in counts.items() if v >= SCREEN_MIN_DAYS], len(counts)


# ==========================================================================
# prereg 5.3 -- relocations (the null's denominator and 5.6's alert base)
# ==========================================================================
def relocations(series, segs):
    """(origin_seg, arrival_seg) pairs whose longitude changed by >= X_far."""
    out = []
    for k in range(len(segs) - 1):
        i0, i1 = segs[k]
        j0, j1 = segs[k + 1]
        lon_a = float(wrap180(np.median(series.grid[i0:i1 + 1])))
        lon_b = float(wrap180(np.median(series.grid[j0:j1 + 1])))
        if abs(wrap180(lon_b - lon_a)) >= X_FAR_DEG:
            out.append({
                "originLonDeg": lon_a, "arrivalLonDeg": lon_b,
                "originEndDay": series.grid_lo + i1,
                "arrivalStartDay": series.grid_lo + j0,
                "arrivalEndDay": series.grid_lo + j1,
                "netChangeDeg": float(abs(wrap180(lon_b - lon_a))),
            })
    return out


def _jeffreys(k, n):
    """Two-sided 95% Jeffreys interval for a binomial proportion."""
    try:
        from scipy.stats import beta
    except Exception:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k + 0.5, n - k + 0.5))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 0.5, n - k + 0.5))
    return lo, hi


def benjamini_hochberg(pvals, q=FDR_Q):
    p = np.asarray(pvals, dtype=np.float64)
    if p.size == 0:
        return np.zeros(0, dtype=bool)
    order = np.argsort(p)
    ranked = p[order]
    m = p.size
    thresh = q * np.arange(1, m + 1) / m
    passing = np.where(ranked <= thresh)[0]
    out = np.zeros(m, dtype=bool)
    if passing.size:
        out[order[:passing[-1] + 1]] = True
    return out


def icc_one_way(groups):
    """One-way random-effects ICC over groups with >= 2 members."""
    groups = [np.asarray(g, dtype=np.float64) for g in groups if len(g) >= 2]
    groups = [g for g in groups if np.all(np.isfinite(g))]
    if len(groups) < 2:
        return float("nan")
    k = len(groups)
    n_total = sum(g.size for g in groups)
    grand = np.concatenate(groups).mean()
    ss_between = sum(g.size * (g.mean() - grand) ** 2 for g in groups)
    ss_within = sum(((g - g.mean()) ** 2).sum() for g in groups)
    if n_total - k <= 0 or k - 1 <= 0:
        return float("nan")
    ms_b = ss_between / (k - 1)
    ms_w = ss_within / (n_total - k)
    n_bar = n_total / k
    denom = ms_b + (n_bar - 1.0) * ms_w
    if denom == 0:
        return float("nan")
    return float((ms_b - ms_w) / denom)


def theil_sen_slope(t_days, y, max_points=60, rng=None):
    """Theil-Sen slope (prereg 5.2, ddot_lambda). Subsampled above
    `max_points` because the estimator is O(n^2) and a stationed segment can
    carry thousands of element sets; the subsample is deterministic."""
    t = np.asarray(t_days, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if t.size < 3:
        return float("nan")
    if t.size > max_points:
        idx = np.linspace(0, t.size - 1, max_points).astype(int)
        t, y = t[idx], y[idx]
    i, j = np.triu_indices(t.size, k=1)
    dt = t[j] - t[i]
    ok = dt > 0
    if not np.any(ok):
        return float("nan")
    return float(np.median((y[j][ok] - y[i][ok]) / dt[ok]))


def poisson_sf(k, mu):
    """P(X >= k) for X ~ Poisson(mu), computed without scipy."""
    if k <= 0:
        return 1.0
    if mu <= 0:
        return 0.0
    term = math.exp(-mu)
    cdf = term
    for n in range(1, int(k)):
        term *= mu / n
        cdf += term
    return max(0.0, min(1.0, 1.0 - cdf))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


PROFILE_KEYS = ("transferDriftDegPerDay", "transferDays", "approacherMotionDeg",
                "closestSeparationDeg", "loiterDays", "departureDriftDegPerDay")


def _iso(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


def analyze(db, archive_path, arrays, emeta, args):
    started = time.time()
    cpu0 = time.process_time()
    print("analyze: building per-object series ...", flush=True)
    series_list = build_series(arrays)
    norads = [s.norad for s in series_list]
    meta = object_metadata(db, norads)
    classes = {n: class_of(meta[n]["objectType"]) for n in norads}
    series_list = [s for s in series_list if classes.get(s.norad) is not None]
    by_norad = {s.norad: s for s in series_list}
    n_active = sum(1 for s in series_list if classes[s.norad] == "active")
    n_passive = len(series_list) - n_active
    print(f"  {len(series_list):,} classified objects "
          f"({n_active:,} active, {n_passive:,} passive)", flush=True)

    grid_lo, n_days = build_daily_grid(series_list)
    segs = {s.norad: station_segments(s) for s in series_list}
    print(f"  daily grid {n_days:,} days; "
          f"{sum(len(v) for v in segs.values()):,} stationed segments", flush=True)

    # ---- prereg 5.4: the one calibrated quantity -------------------------
    sigma_n, sigma_samples = calibrate_sigma_n(series_list, classes, segs)
    # prereg 5.2 cross-validation, reported whatever it says
    cross = []
    for s in series_list:
        if classes[s.norad] != "active":
            continue
        for i0, i1 in segs[s.norad][:3]:
            t0 = (s.grid_lo + i0) * DAY_MS
            t1 = (s.grid_lo + i1 + 1) * DAY_MS
            k0, k1 = np.searchsorted(s.epoch_ms, [t0, t1])
            if k1 - k0 < 10:
                continue
            slope = theil_sen_slope((s.epoch_ms[k0:k1] - s.epoch_ms[k0]) / DAY_MS,
                                    s.lam_unwrapped[k0:k1])
            if np.isfinite(slope):
                cross.append(float(np.median(s.drift[k0:k1])) - slope)
    cross = np.asarray(cross)
    cross_bias = float(np.median(cross)) if cross.size else float("nan")
    cross_scatter = (float(np.median(np.abs(cross - np.median(cross))) * 1.4826)
                     if cross.size else float("nan"))
    d_floor_30 = 6.0 * 0.1 / 30.0
    gate_a = (not np.isfinite(sigma_n)) or sigma_n >= GATE_A_SIGMA_MAX \
        or abs(cross_bias) > d_floor_30
    print(f"  sigma_n = {sigma_n:.6f} deg/day over {sigma_samples:,} pairs "
          f"(gate A bar {GATE_A_SIGMA_MAX:.6f}); "
          f"ddot_n - ddot_lambda bias {cross_bias:.6f}, scatter {cross_scatter:.6f}",
          flush=True)

    # ---- prereg 5.5: drift-change flags ---------------------------------
    flags = {}
    for s in series_list:
        t_flag, size = drift_change_flags(s, sigma_n)
        flags[s.norad] = (t_flag, size)

    # ---- candidate screen + exact pass (prereg 4) ------------------------
    print("analyze: screening candidate pairs ...", flush=True)
    cands, screened = candidate_pairs(series_list, grid_lo, n_days)
    print(f"  {screened:,} pairs seen by the screen, {len(cands):,} survive "
          f"to the exact pass", flush=True)

    arms = [("primary", X_PRIMARY_DEG, D_PRIMARY_DAYS)]
    arms += [(f"X={x}", x, D_PRIMARY_DAYS) for x in X_SENSITIVITY]
    arms += [(f"D={int(d)}", X_PRIMARY_DEG, d) for d in D_SENSITIVITY]

    results = {name: {"X": x, "D": d, "events": [], "standingColocations": 0,
                      "rejections": {}} for name, x, d in arms}
    min_days = min(d for _, _, d in arms)
    for i, j in cands:
        a, b = series_list[i], series_list[j]
        packed = pair_separation(a, b, min_days)
        if packed is None:
            continue
        for name, x_deg, d_days in arms:
            r = results[name]
            e, st = events_from_separation(a, b, packed, x_deg, d_days,
                                           stats=r["rejections"])
            if st:
                r["standingColocations"] += 1
            r["events"].extend(e)
    for name, x_deg, d_days in arms:
        for e in results[name]["events"]:
            _decorate(e, by_norad, flags, meta, classes, x_deg, d_days)
        ev = results[name]["events"]
        act = [e for e in ev if e["approacherClass"] == "active"
               and e["attribution"] == "resolved"]
        pas = [e for e in ev if e["approacherClass"] == "passive"
               and e["attribution"] == "resolved"]
        print(f"  arm {name:10s} X={x_deg} D={d_days:.0f}: {len(ev):5d} raw, "
              f"{len(act):4d} active, {len(pas):4d} passive, "
              f"{results[name]['standingColocations']:4d} standing co-locations",
              flush=True)

    events = [e for e in results["primary"]["events"]
              if e["approacherClass"] == "active" and e["attribution"] == "resolved"]

    # ---- prereg 5.3/5.6: relocations and alert precision -----------------
    relocs = {}
    for s in series_list:
        r = relocations(s, segs[s.norad])
        if r:
            relocs[s.norad] = r
    n_reloc_active = sum(len(v) for n, v in relocs.items() if classes[n] == "active")
    alerts = 0
    for n, rs in relocs.items():
        if classes[n] != "active":
            continue
        t_flag = flags[n][0]
        for r in rs:
            lo = (r["originEndDay"] - 1) * DAY_MS
            hi = (r["arrivalStartDay"] + 1) * DAY_MS
            if np.any((t_flag >= lo) & (t_flag <= hi)):
                alerts += 1

    # ---- prereg 6.1: the chance co-location null -------------------------
    print("analyze: permutation null ...", flush=True)
    null = permutation_null(series_list, segs, classes, relocs, grid_lo,
                            X_PRIMARY_DEG, D_PRIMARY_DAYS)
    print(f"  segment-level observed {null['observed']}, null mean "
          f"{null['nullMeanExcludingSelf']:.2f} "
          f"[{null['nullP2p5ExcludingSelf']:.0f}, {null['nullP97p5ExcludingSelf']:.0f}]",
          flush=True)

    # ---- prereg 7: repetition -------------------------------------------
    repetition = repetition_stats(events, relocs, null, classes)

    # ---- gates (prereg 10) ----------------------------------------------
    act_exposure = sum(len(segs[s.norad]) for s in series_list
                       if classes[s.norad] == "active") or 1
    pas_exposure = sum(len(segs[s.norad]) for s in series_list
                       if classes[s.norad] == "passive") or 1
    passive_events = [e for e in results["primary"]["events"]
                      if e["approacherClass"] == "passive"
                      and e["attribution"] == "resolved"
                      and not e["libration_zone"]]
    active_outside = [e for e in events if not e["libration_zone"]]
    act_rate = len(active_outside) / act_exposure
    pas_rate = len(passive_events) / pas_exposure
    gate_b = act_rate > 0 and pas_rate > GATE_B_PASSIVE_FRACTION * act_rate
    gate_c = (null["nullP2p5ExcludingSelf"] <= null["observed"]
              <= null["nullP97p5ExcludingSelf"])
    gate_d = repetition["repeaters2"] < GATE_D_MIN_REPEATERS
    leads = np.asarray([e["leadCausalDays"] for e in events
                        if e["leadCausalDays"] is not None], dtype=np.float64)
    null_lead_fraction = 1.0 - (leads.size / len(events)) if events else 1.0
    gate_e = (leads.size == 0) or float(np.median(leads)) <= 0 or null_lead_fraction > 0.5

    # ---- outputs ---------------------------------------------------------
    args.out.mkdir(parents=True, exist_ok=True)
    jsonl = args.out / f"proximity-events-{args.date}.jsonl"
    provenance = {
        "schema": 1,
        "record": "provenance",
        "study": "T8a GEO approach events",
        "registration": "docs/proximity-preregistration-20260922.md",
        "note": ("Ownership-agnostic instrument. country/objectType/name are "
                 "metadata carried for later analysis and enter no detector "
                 "decision except the active/passive class of prereg 3.2. "
                 "separationDeg is MEAN LONGITUDE separation, a slot "
                 "coordinate -- it is NOT a miss distance (prereg 1.1). "
                 "Drift rates are deg/day; no fuel figure is computed for any "
                 "object."),
        "archive": str(archive_path),
        "archiveBytes": archive_path.stat().st_size,
        "archiveMtimeMs": int(archive_path.stat().st_mtime * 1000),
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "arm": {"X_deg": X_PRIMARY_DEG, "D_days": D_PRIMARY_DAYS,
                "X_far_deg": X_FAR_DEG, "T_look_days": T_LOOK_DAYS},
        "sigma_n_deg_per_day": sigma_n,
    }
    with open(jsonl, "w") as fh:
        fh.write(json.dumps(provenance) + "\n")
        for e in sorted(results["primary"]["events"], key=lambda r: r["arrivalMs"]):
            fh.write(json.dumps(e) + "\n")

    summary = {
        "schema": 1,
        "measuredAt": provenance["measuredAt"],
        "registration": "docs/proximity-preregistration-20260922.md",
        "host": os.uname().nodename,
        "executionMode": "cpu",
        "archive": {
            "path": str(archive_path),
            "bytes": archive_path.stat().st_size,
            "mtimeMs": provenance["archiveMtimeMs"],
            "monthRollupSpan": list(db.execute(
                "SELECT MIN(month), MAX(month), SUM(rows) FROM month_rollup").fetchone()),
        },
        "extract": emeta,
        "population": {
            "classifiedObjects": len(series_list),
            "active": n_active, "passive": n_passive,
            "stationedSegments": int(sum(len(v) for v in segs.values())),
            "gridDays": n_days,
        },
        "calibration": {
            "sigma_n_deg_per_day": sigma_n,
            "sigma_n_samples": sigma_samples,
            "gateA_bar_deg_per_day": GATE_A_SIGMA_MAX,
            "crossValidationBias_deg_per_day": cross_bias,
            "crossValidationScatter_deg_per_day": cross_scatter,
            "crossValidationSegments": int(cross.size),
            "d_floor_30d": d_floor_30,
            "burnThreshold_deg_per_day": max(BURN_SIGMA_K * sigma_n,
                                             BURN_FLOOR_DEG_PER_DAY),
        },
        "screen": {"pairsSeen": screened, "pairsExact": len(cands),
                   "radiusDeg": SCREEN_RADIUS_DEG, "minDays": SCREEN_MIN_DAYS},
        "arms": {name: {
            "X": r["X"], "D": r["D"],
            "rawEvents": len(r["events"]),
            "activeResolved": sum(1 for e in r["events"]
                                  if e["approacherClass"] == "active"
                                  and e["attribution"] == "resolved"),
            "passiveResolved": sum(1 for e in r["events"]
                                   if e["approacherClass"] == "passive"
                                   and e["attribution"] == "resolved"),
            "ambiguous": sum(1 for e in r["events"]
                             if e["attribution"] == "ambiguous"),
            "librationZone": sum(1 for e in r["events"] if e["libration_zone"]),
            "librationHalfWidthDeg": libration_zone_half_width_deg(r["X"], r["D"]),
            "standingColocations": r["standingColocations"],
            "rejections": r["rejections"],
        } for name, r in results.items()},
        "relocations": {
            "activeRelocations": n_reloc_active,
            "relocationAlerts": alerts,
            "alertPrecision": (len(events) / alerts) if alerts else None,
            "alertPrecisionJeffreys95": _jeffreys(min(len(events), alerts), alerts)
            if alerts else None,
        },
        "leadTime": _lead_summary(events),
        "null": null,
        "repetition": repetition,
        "gates": {
            "A_instrumentUnfit": bool(gate_a),
            "B_detectorLeaks": bool(gate_b),
            "C_nullExplainsCatalogue": bool(gate_c),
            "D_underpoweredRepetition": bool(gate_d),
            "E_noLeadTime": bool(gate_e),
            "activeEventsPerStationedSegment": act_rate,
            "passiveEventsPerStationedSegment": pas_rate,
        },
        "constants": {
            "a_geo_km": A_GEO_KM,
            "drift_deg_per_day_per_km": DRIFT_PER_KM,
            "km_per_deg_geo": KM_PER_DEG_GEO,
            "lambda_ddot_max_deg_per_day2": LAMBDA_DDOT_MAX,
            "drift_deg_per_day_per_m_s": DRIFT_PER_M_S,
        },
        "sourceSha256": {
            "tools/proximity_geo.py": sha256_file(Path(__file__)),
            "pipeline/orbit_history.py": sha256_file(_REPO / "pipeline/orbit_history.py"),
            "pipeline/orbit_campaigns.py": sha256_file(_REPO / "pipeline/orbit_campaigns.py"),
            "pipeline/orbit_events.py": sha256_file(_REPO / "pipeline/orbit_events.py"),
        },
        "eventsFile": str(jsonl.relative_to(_REPO)),
        "eventsSha256": sha256_file(jsonl),
        "wallSeconds": time.time() - started,
        "cpuSeconds": time.process_time() - cpu0,
    }
    receipt = args.out / f"proximity-{args.date}-receipt.json"
    receipt.write_text(json.dumps(summary, indent=2, default=float))
    print(f"wrote {jsonl} and {receipt}", flush=True)
    print(json.dumps({k: summary[k] for k in
                      ("leadTime", "null", "repetition", "gates")},
                     indent=2, default=float))
    return 0


def _decorate(e, by_norad, flags, meta, classes, x_deg, d_days):
    a = by_norad[e["approacherNorad"]]
    e["approacherClass"] = classes[a.norad]
    for role, norad in (("approacher", e["approacherNorad"]),
                        ("target", e["targetNorad"])):
        m = meta[norad]
        e[role + "Name"] = m["name"]
        e[role + "ObjectId"] = m["objectId"]
        e[role + "ObjectType"] = m["objectType"]
        e[role + "Country"] = m["country"]          # metadata only (prereg 0)
        e[role + "LaunchDate"] = m["launchDate"]
    e["targetClass"] = classes[e["targetNorad"]]
    e["sameCountry"] = (e["approacherCountry"] is not None
                        and e["approacherCountry"] == e["targetCountry"])
    e["libration_zone"] = bool(in_libration_zone(e["loiterLongitudeDeg"],
                                                 x_deg, d_days))
    e["arrivalIso"] = _iso(e["arrivalMs"])
    e["loiterEndIso"] = _iso(e["loiterEndMs"])
    e["departureIso"] = _iso(e["departureMs"])
    e["transferStartIso"] = _iso(e["transferStartMs"])
    e["transferDriftDegPerDay"] = (abs(e["approacherMotionDeg"]) / e["transferDays"]
                                   if e["transferDays"] > 0 else float("nan"))
    e["transferDeltaSemiMajorKm"] = float(semi_major_offset_km(
        e["transferDriftDegPerDay"]))
    # departure drift rate, from the approacher's own mean motion after the loiter
    k = int(np.searchsorted(a.epoch_ms, e["loiterEndMs"]))
    k2 = min(a.epoch_ms.size - 1, k + 10)
    e["departureDriftDegPerDay"] = float(abs(np.median(a.drift[k:k2 + 1]))) \
        if k2 > k else float("nan")
    # prereg 5.5 lead times
    t_flag, size = flags[a.norad]
    lo = e["arrivalMs"] - T_LOOK_DAYS * DAY_MS
    hi = e["transferStartMs"] + DAY_MS
    inside = np.where((t_flag >= lo) & (t_flag < hi))[0]
    if inside.size:
        k_last = int(inside[-1])
        e["initiatingFlagMs"] = int(t_flag[k_last])
        e["initiatingFlagIso"] = _iso(int(t_flag[k_last]))
        e["initiatingDriftChangeDegPerDay"] = float(size[k_last])
        e["leadCausalDays"] = float((e["arrivalMs"] - t_flag[k_last]) / DAY_MS)
        # SECONDARY, added after registration and labelled as such: the FIRST
        # flag of the same transfer, which is what an operator would actually
        # have seen first. Never the headline.
        e["leadFirstFlagDays"] = float((e["arrivalMs"] - t_flag[int(inside[0])]) / DAY_MS)
    else:
        e["initiatingFlagMs"] = None
        e["initiatingFlagIso"] = None
        e["initiatingDriftChangeDegPerDay"] = None
        e["leadCausalDays"] = None
        e["leadFirstFlagDays"] = None


def _lead_summary(events):
    leads = np.asarray([e["leadCausalDays"] for e in events
                        if e["leadCausalDays"] is not None], dtype=np.float64)
    first = np.asarray([e["leadFirstFlagDays"] for e in events
                        if e["leadFirstFlagDays"] is not None], dtype=np.float64)
    def pct(a):
        if a.size == 0:
            return {}
        return {f"p{p}": float(np.percentile(a, p)) for p in (5, 25, 50, 75, 95)}
    return {
        "events": len(events),
        "withFlag": int(leads.size),
        "withoutFlag": len(events) - int(leads.size),
        "leadCausalDays": pct(leads),
        "leadCausalNonPositive": int((leads <= 0).sum()) if leads.size else 0,
        "leadCausalMean": float(leads.mean()) if leads.size else None,
        "secondary_leadFirstFlagDays": pct(first),
    }


def permutation_null(series_list, segs, classes, relocs, grid_lo, x_deg, d_days):
    """prereg 6.1. Paired: the SAME segment-level machinery decides the
    observed and the null counts, so only the destination longitude differs.

    Two null variants are reported. The registered draw is from the empirical
    distribution of occupied longitudes, which means the drawn longitude is
    itself occupied; `WithSelf` keeps that object as a match, `ExcludingSelf`
    does not. An object cannot be co-located with itself, so
    `ExcludingSelf` is the one used for gate C, and both are published.
    """
    rng = np.random.default_rng(SEED)
    stations = []          # (start_day, end_day, lon, norad)
    for s in series_list:
        for i0, i1 in segs[s.norad]:
            stations.append((s.grid_lo + i0, s.grid_lo + i1,
                             float(wrap180(np.median(s.grid[i0:i1 + 1]))), s.norad))
    starts = np.asarray([st[0] for st in stations])
    ends = np.asarray([st[1] for st in stations])
    lons = np.asarray([st[2] for st in stations])
    owners = np.asarray([st[3] for st in stations])

    cases = []
    for norad, rs in relocs.items():
        if classes[norad] != "active":
            continue
        for r in rs:
            overlap = np.minimum(ends, r["arrivalEndDay"]) - \
                np.maximum(starts, r["arrivalStartDay"]) + 1
            pool = np.where((overlap >= d_days) & (owners != norad))[0]
            if pool.size == 0:
                continue
            cases.append((r["arrivalLonDeg"], r["originLonDeg"], pool))

    def count(arrival_lon, origin_lon, pool, drawn_idx=None):
        near = np.abs(wrap180(arrival_lon - lons[pool])) <= x_deg
        far = np.abs(wrap180(origin_lon - lons[pool])) >= X_FAR_DEG
        hit = near & far
        if drawn_idx is not None:
            hit = hit & (pool != drawn_idx)
        return int(hit.sum())

    observed = sum(count(a, o, p) for a, o, p in cases)
    with_self = np.zeros(N_PERMUTATIONS, dtype=np.int64)
    without_self = np.zeros(N_PERMUTATIONS, dtype=np.int64)
    for arrival_lon, origin_lon, pool in cases:
        pool_lons = lons[pool]
        far = np.abs(wrap180(origin_lon - pool_lons)) >= X_FAR_DEG
        if not np.any(far):
            continue
        picks = rng.integers(pool.size, size=N_PERMUTATIONS)
        lam_star = pool_lons[picks]
        near = np.abs(wrap180(lam_star[:, None] - pool_lons[None, :])) <= x_deg
        hit = near & far[None, :]
        with_self += hit.sum(axis=1)
        self_hit = hit[np.arange(N_PERMUTATIONS), picks]
        without_self += hit.sum(axis=1) - self_hit.astype(np.int64)
    return {
        "permutations": N_PERMUTATIONS, "seed": SEED,
        "relocationCases": len(cases),
        "stationedSegments": len(stations),
        "observed": observed,
        "expectedUniformPerArrival": float(np.mean(
            [p.size * 2.0 * x_deg / 360.0 for _, _, p in cases])) if cases else None,
        "nullMeanWithSelf": float(with_self.mean()),
        "nullMeanExcludingSelf": float(without_self.mean()),
        "nullP2p5ExcludingSelf": float(np.percentile(without_self, 2.5)),
        "nullP97p5ExcludingSelf": float(np.percentile(without_self, 97.5)),
        "nullP2p5WithSelf": float(np.percentile(with_self, 2.5)),
        "nullP97p5WithSelf": float(np.percentile(with_self, 97.5)),
        "excessOverNull": observed - float(without_self.mean()),
        "observedGreaterThanNullFraction": float((without_self < observed).mean()),
    }


def repetition_stats(events, relocs, null, classes):
    """prereg 7."""
    by_obj = {}
    for e in events:
        by_obj.setdefault(e["approacherNorad"], []).append(e)
    repeaters = {n: v for n, v in by_obj.items() if len(v) >= 2}
    multi_target = {n: v for n, v in repeaters.items()
                    if len({e["targetNorad"] for e in v}) >= 2}

    groups = {k: [] for k in PROFILE_KEYS}
    for n, v in repeaters.items():
        for k in PROFILE_KEYS:
            vals = [e[k] for e in v if e.get(k) is not None and np.isfinite(e[k])
                    and e[k] > 0]
            if len(vals) >= 2:
                groups[k].append(np.log(np.asarray(vals)))
    icc = {k: icc_one_way(groups[k]) for k in PROFILE_KEYS}

    skill = {}
    for k in ("loiterDays", "closestSeparationDeg"):
        own_err, pop_err = [], []
        pop_vals = [e[k] for e in events if e.get(k) is not None
                    and np.isfinite(e[k]) and e[k] > 0]
        if len(pop_vals) < 3:
            skill[k] = None
            continue
        pop_median = float(np.median(np.log(pop_vals)))
        for n, v in repeaters.items():
            vals = [math.log(e[k]) for e in v if e.get(k) is not None
                    and np.isfinite(e[k]) and e[k] > 0]
            if len(vals) < 2:
                continue
            for i in range(len(vals)):
                others = vals[:i] + vals[i + 1:]
                own_err.append(abs(vals[i] - float(np.median(others))))
                pop_err.append(abs(vals[i] - pop_median))
        if not own_err:
            skill[k] = None
        else:
            skill[k] = {
                "n": len(own_err),
                "maeOwnLog": float(np.mean(own_err)),
                "maePopulationLog": float(np.mean(pop_err)),
                "skill": float(1.0 - np.mean(own_err) / np.mean(pop_err))
                if np.mean(pop_err) > 0 else None,
            }

    # prereg 7.4: per-object Poisson tail against the null rate, BH FDR
    per_case = (null["nullMeanExcludingSelf"] / null["relocationCases"]
                if null["relocationCases"] else 0.0)
    tested, pvals = [], []
    for n in sorted(by_obj):
        n_reloc = len([r for r in relocs.get(n, [])]) or 1
        mu = per_case * n_reloc
        tested.append(n)
        pvals.append(poisson_sf(len(by_obj[n]), mu))
    passed = benjamini_hochberg(np.asarray(pvals))
    survivors = [{"norad": tested[i], "events": len(by_obj[tested[i]]),
                  "p": pvals[i]} for i in range(len(tested)) if passed[i]]
    survivors.sort(key=lambda r: r["p"])

    return {
        "approachers": len(by_obj),
        "repeaters2": len(repeaters),
        "repeaters3": sum(1 for v in by_obj.values() if len(v) >= 3),
        "repeaters5": sum(1 for v in by_obj.values() if len(v) >= 5),
        "multiTargetRepeaters": len(multi_target),
        "iccLog": icc,
        "leaveOneOutSkill": skill,
        "nullEventsPerRelocation": per_case,
        "objectsTested": len(tested),
        "fdrSurvivors": len(survivors),
        "fdrTop": survivors[:25],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=("extract", "analyze", "all"), default="all")
    ap.add_argument("--archive", type=Path, default=None)
    ap.add_argument("--work", type=Path,
                    default=_REPO / "runtime" / "proximity-geo")
    ap.add_argument("--out", type=Path, default=_REPO / "docs")
    ap.add_argument("--date", default="20260922")
    ap.add_argument("--limit-rows", type=int, default=None)
    args = ap.parse_args(argv)

    args.work.mkdir(parents=True, exist_ok=True)
    db = orbit_campaigns.open_archive_for_reading(args.archive)
    db.execute("PRAGMA query_only=1")
    archive_path = Path(next(r[2] for r in db.execute("PRAGMA database_list")
                             if r[1] == "main"))

    if args.stage in ("extract", "all"):
        print("extract: one sequential pass over element_set ...", flush=True)
        arrays, emeta = extract(db, args.work, limit_rows=args.limit_rows)
        print(f"  scanned {emeta['rowsScanned']:,}  kept {emeta['rowsKept']:,} "
              f"rows over {emeta['objectsKept']:,} objects in "
              f"{emeta['wallSeconds']:.0f}s", flush=True)
    else:
        with np.load(args.work / "near-geo.npz") as z:
            arrays = {k: z[k] for k in z.files}
        emeta = json.loads((args.work / "extract-meta.json").read_text())

    if args.stage == "extract":
        return 0

    return analyze(db, archive_path, arrays, emeta, args)


if __name__ == "__main__":
    raise SystemExit(main())
