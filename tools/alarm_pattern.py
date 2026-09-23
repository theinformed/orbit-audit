#!/usr/bin/env python3
"""T8c: a behavioural pattern taxonomy over GEO approach events, and the
predictive-skill measurement that decides whether an alarm can claim a
pattern has been "seen before".

Every definition here is the one registered in
`docs/alarm-pattern-preregistration-20260922.md` and must not drift from it.
Section references below (prereg N) point at that document; where this module
makes an implementation choice the registration left open, the choice is
marked IMPL and justified in place.

The instrument is ownership-agnostic. Catalogue registry codes are carried on
no row this module writes and are read by no branch of it. Nothing here
computes a delta-V, a mass or any consumables figure, and nothing here emits
a distance: every separation is mean-longitude separation, a slot coordinate
(T8a 1.1).

Geometry, the mean-longitude definition, the unwrap, the daily grid, the
station segmentation and the drift-change flags are IMPORTED from
`tools/proximity_geo.py` rather than reimplemented, so that no T8a definition
can silently drift (prereg 2).

Stages
------
  features   per-object element histories -> the 32-feature table (prereg 3)
  analyze    the taxonomy (prereg 4, 5), the estimands (prereg 6), the gates
  all        both
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
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))

# The T8a instrument itself. Imported, never copied (prereg 2).
import proximity_geo as pg  # noqa: E402

DAY_MS = pg.DAY_MS
SEED = 20260922                                  # prereg 4, 7

REGISTRATION = "docs/alarm-pattern-preregistration-20260922.md"
EVENTS_PATH = _REPO / "docs" / "proximity-events-20260922.jsonl"
# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
ARCHIVE = Path(os.environ.get("ORBIT_ARCHIVE_DB",
                              "element-archive.not-configured.sqlite3"))

# prereg 3 -- the four disjoint flag-counting windows, in days about the
# event's own epochs. Fixed in the registration; not tunable here.
W_INIT = (-5.0, 1.0)          # about transferStart
W_TRANSIT = (1.0, -2.0)       # (transferStart + 1 d, arrival - 2 d)
W_ARRIVAL = (-2.0, 5.0)       # about arrival
W_DWELL = (5.0, 30.0)         # about arrival; the FIRST 30 d of the dwell
DWELL_WINDOW_DAYS = 30.0      # prereg 3 -- the leakage control
RAMP_FLOOR_DAYS = 0.5         # prereg 3.2 feature 4
BASELINE_SAMPLES = pg.BURN_BASELINE_SAMPLES     # 10
OVERSHOOT_WINDOW_DAYS = 15.0  # prereg 3.4 feature 13
BRAKE_LIMIT_DAYS = 15.0       # prereg 3.4 feature 12
PERIOD_LAGS = (2, 15)         # prereg 3.5 feature 18
K_RANGE = tuple(range(2, 11))                   # prereg 4
N_INIT = 50
MAX_ITER = 300
TOL = 1e-10
GAP_B = 50                                      # prereg 4
GAP_REF_N_INIT = 5            # IMPL: the reference draws' n_init; the
                              # registration fixes B and the box, not this.
STABILITY_DRAWS = 200                           # prereg 4
SKILL_BOOTSTRAP = 2000                          # prereg 6.8
LOG_EPS = 1e-9                                  # prereg 3.11

# prereg 8 -- the gates, as numbers
GATE_P_BAR = 0.157            # T8a's +0.137 plus the registered +0.02
GATE_Q_JACCARD = 0.5
GATE_R_ARI = 0.5
GATE_S_ETA2 = 0.05
GATE_T_MIN_CLUSTER = 20
GATE_T_MIN_PREDICTIONS = 50
GATE_U_FEATURE_FRACTION = 0.5
GATE_U_MISSING_FRACTION = 0.30
GATE_V_TOLERANCE = 0.005
T8A_SKILL_LOITER = 0.137      # T8a 5.2 -- the baseline this study is against
T8A_SKILL_SEPARATION = 0.008
GPU_RACE_SECONDS = 600.0      # prereg 7

# prereg 3 -- the feature table, in registration order: (name, log-transformed).
FEATURES = (
    ("init_drift_change_mag", True),
    ("init_ramp_days", True),
    ("init_stage_count", False),
    ("init_abruptness", True),
    ("transit_days", True),
    ("transit_drift_median", True),
    ("transit_drift_peak", True),
    ("transit_drift_flatness", False),
    ("transit_midcourse_count", False),
    ("transit_longitude_span", False),
    ("arrival_brake_mag", True),
    ("arrival_brake_days", True),
    ("arrival_overshoot_deg", True),
    ("arrival_residual_drift", True),
    ("arrival_flag_count", False),
    ("dwell_sk_tightness", True),
    ("dwell_rel_amplitude", True),
    ("dwell_rel_period_days", True),
    ("dwell_rel_osc_fraction", False),
    ("dwell_correction_rate", True),
    ("departure_observed", False),
    ("departure_drift_abs", True),
    ("departure_reverses", False),
    ("departure_dest_distance_deg", True),
    ("cadence_days_since_prev", True),
    ("cadence_prior_events", False),
    ("cadence_prior_targets", False),
    ("cadence_prior_arrivals", True),
    ("lead_causal_days", True),
    ("has_initiating_flag", False),
    ("libration_zone", False),
    ("separation_at_start_deg", True),
    ("miss_init_flag", False),
    ("miss_ramp", False),
    ("miss_brake_days", False),
    ("miss_dwell_period", False),
    ("miss_departure", False),
)
FEATURE_NAMES = tuple(n for n, _ in FEATURES)
LOG_FEATURES = frozenset(n for n, lg in FEATURES if lg)

# prereg 5 -- the causal subset: everything an observer possesses by arrival.
CAUSAL_FEATURES = tuple(
    n for n in FEATURE_NAMES
    if not n.startswith(("dwell_", "departure_")) and n != "miss_departure"
)

# prereg 3.10 -- the outcomes, which are never features.
OUTCOMES = ("loiterDays", "closestSeparationDeg")


# ==========================================================================
# Loading
# ==========================================================================
def load_events(path=EVENTS_PATH):
    """The committed T8a primary arm. The provenance record carries the
    sigma_n T8c must reuse rather than recalibrate (prereg 2)."""
    provenance, rows = None, []
    with open(path) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record") == "provenance":
                provenance = rec
                continue
            rows.append(rec)
    return provenance, rows


def primary_arm(rows):
    """prereg 2: active-class approacher, attribution resolved -- T8a's
    registered headline catalogue of 487."""
    return [e for e in rows
            if e.get("approacherClass") == "active"
            and e.get("attribution") == "resolved"]


_SELECT_ONE = (
    "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, "
    "raan_q, arg_perigee_q, mean_anomaly_q FROM element_set "
    "WHERE norad = ? AND mean_motion_q BETWEEN ? AND ? "
    "AND eccentricity_q <= ? AND inclination_q <= ? ORDER BY epoch_ms")


def load_series(db, norads):
    """Per-object near-GEO element history, by the primary key rather than a
    sequential scan. IMPL: `element_set` is WITHOUT ROWID on
    (norad, epoch_ms), so a few hundred indexed reads cost ~10 s against the
    293 s of T8a's full pass, and the rows kept are identical -- the same
    quantised filter of T8a 3.1, expressed in SQL rather than in Python."""
    mm_lo = int(round(pg.MM_MIN_REV_DAY * pg.SCALE_MM))
    mm_hi = int(round(pg.MM_MAX_REV_DAY * pg.SCALE_MM))
    ecc_hi = int(round(pg.ECC_MAX * pg.SCALE_ECC))
    inc_hi = int(round(pg.INC_MAX_DEG * pg.SCALE_ANGLE))
    out = {}
    for norad in sorted(norads):
        rows = db.execute(_SELECT_ONE,
                          (int(norad), mm_lo, mm_hi, ecc_hi, inc_hi)).fetchall()
        if len(rows) < 2:
            continue
        cols = list(zip(*rows))
        out[int(norad)] = pg.Series(
            int(norad),
            np.asarray(cols[0], dtype=np.int64),
            np.asarray(cols[1], dtype=np.float64) / pg.SCALE_MM,
            np.asarray(cols[2], dtype=np.float64) / pg.SCALE_ECC,
            np.asarray(cols[3], dtype=np.float64) / pg.SCALE_ANGLE,
            np.asarray(cols[4], dtype=np.float64) / pg.SCALE_ANGLE,
            np.asarray(cols[5], dtype=np.float64) / pg.SCALE_ANGLE,
            np.asarray(cols[6], dtype=np.float64) / pg.SCALE_ANGLE)
    return out


def attach_grid(series):
    """prereg 2 IMPL: a per-object daily grid whose SAMPLE POINTS are
    identical to T8a's global grid -- absolute day index x 86400000 + 43200000
    ms -- so `station_segments` sees the same numbers. `grid_lo` is stored
    here as the ABSOLUTE day index, which makes (grid_lo + i) * DAY_MS an
    epoch; T8a stores a global-relative offset in the same attribute."""
    lo = int(series.epoch_ms[0] // int(DAY_MS))
    hi = int(series.epoch_ms[-1] // int(DAY_MS))
    days = np.arange(lo, hi + 1, dtype=np.int64)
    targets = days.astype(np.float64) * DAY_MS + 0.5 * DAY_MS
    series.grid_lo = lo
    series.grid = pg.interpolate(series.epoch_ms, series.lam_unwrapped, targets)
    return series


# ==========================================================================
# prereg 3 -- feature extraction
# ==========================================================================
def _window(epochs, t_lo, t_hi):
    e = np.asarray(epochs, dtype=np.float64)
    return (e >= t_lo) & (e <= t_hi)


def _count_flags(flag_ms, t_lo, t_hi, closed_lo=True, closed_hi=True):
    f = np.asarray(flag_ms, dtype=np.float64)
    if f.size == 0:
        return 0
    lo_ok = f >= t_lo if closed_lo else f > t_lo
    hi_ok = f <= t_hi if closed_hi else f < t_hi
    return int(np.count_nonzero(lo_ok & hi_ok))


def _mad(x):
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.median(np.abs(x - np.median(x))))


def _first_crossing(t, y, level):
    """First time at which y reaches `level`, by linear interpolation between
    the bracketing samples. NaN when never reached."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    hit = np.where(y >= level)[0]
    if hit.size == 0:
        return float("nan")
    k = int(hit[0])
    if k == 0:
        return float(t[0])
    y0, y1 = y[k - 1], y[k]
    if y1 == y0:
        return float(t[k])
    frac = (level - y0) / (y1 - y0)
    return float(t[k - 1] + frac * (t[k] - t[k - 1]))


def autocorr_period(values, lag_lo, lag_hi):
    """prereg 3.5 features 18 and 19: the lag of the first local maximum of
    the autocorrelation of a linearly detrended daily series, and the
    variance fraction of the least-squares sinusoid at that lag."""
    y = np.asarray(values, dtype=np.float64)
    ok = np.isfinite(y)
    if int(ok.sum()) < 20:
        return float("nan"), float("nan")
    idx = np.where(ok)[0].astype(np.float64)
    slope, intercept = np.polyfit(idx, y[ok], 1)
    resid = np.zeros(y.size)
    resid[ok] = y[ok] - (slope * idx + intercept)
    var = float(np.dot(resid, resid))
    if var <= 0.0:
        return float("nan"), float("nan")
    top = min(lag_hi, resid.size - 2)
    if top < lag_lo:
        return float("nan"), float("nan")
    ac = np.array([float(np.dot(resid[:resid.size - k], resid[k:])) / var
                   for k in range(0, top + 2)])
    best = float("nan")
    for k in range(max(lag_lo, 1), min(top, ac.size - 2) + 1):
        if ac[k] > ac[k - 1] and ac[k] >= ac[k + 1]:
            best = float(k)
            break
    if not np.isfinite(best):
        return float("nan"), float("nan")
    omega = 2.0 * math.pi / best
    tt = np.arange(resid.size, dtype=np.float64)
    basis = np.column_stack([np.cos(omega * tt), np.sin(omega * tt)])
    coef, *_ = np.linalg.lstsq(basis, resid, rcond=None)
    fit = basis @ coef
    return best, float(min(np.dot(fit, fit) / var, 1.0))


def event_features(event, series_by_norad, flags_by_norad, segs_by_norad, cadence):
    """prereg 3: the 32 features and the 5 missingness indicators, for one
    event. No branch here reads a catalogue metadata column."""
    f = {n: float("nan") for n in FEATURE_NAMES}
    a = series_by_norad.get(event["approacherNorad"])
    b = series_by_norad.get(event["targetNorad"])
    t_s = float(event["transferStartMs"])
    t_a = float(event["arrivalMs"])
    t_d = event.get("departureMs")
    dd = event.get("departureDriftDegPerDay")
    flags = flags_by_norad.get(event["approacherNorad"], np.zeros(0))

    # ---- catalogue-carried features (prereg 3) ---------------------------
    icd = event.get("initiatingDriftChangeDegPerDay")
    f["init_drift_change_mag"] = abs(float(icd)) if icd is not None else float("nan")
    f["transit_days"] = float(event["transferDays"])
    f["transit_drift_median"] = abs(float(event["transferDriftDegPerDay"]))
    f["transit_longitude_span"] = abs(float(event["approacherMotionDeg"]))
    f["separation_at_start_deg"] = abs(float(event["separationAtTransferStartDeg"]))
    f["has_initiating_flag"] = 1.0 if event.get("initiatingFlagMs") is not None else 0.0
    f["libration_zone"] = 1.0 if event.get("libration_zone") else 0.0
    lead = event.get("leadCausalDays")
    f["lead_causal_days"] = float(lead) if lead is not None else float("nan")
    f["departure_observed"] = 1.0 if t_d is not None else 0.0
    f["departure_drift_abs"] = (abs(float(dd)) if (t_d is not None and dd is not None)
                                else float("nan"))

    # ---- cadence (prereg 3.7) -------------------------------------------
    c = cadence[id(event)]
    f["cadence_days_since_prev"] = c["daysSincePrev"]
    f["cadence_prior_events"] = float(c["priorEvents"])
    f["cadence_prior_targets"] = float(c["priorTargets"])
    f["cadence_prior_arrivals"] = float(c["priorArrivals"])

    # ---- flag windows (prereg 3) ----------------------------------------
    f["init_stage_count"] = float(_count_flags(
        flags, t_s + W_INIT[0] * DAY_MS, t_s + W_INIT[1] * DAY_MS))
    f["transit_midcourse_count"] = float(_count_flags(
        flags, t_s + W_TRANSIT[0] * DAY_MS, t_a + W_TRANSIT[1] * DAY_MS,
        closed_lo=False, closed_hi=False))
    f["arrival_flag_count"] = float(_count_flags(
        flags, t_a + W_ARRIVAL[0] * DAY_MS, t_a + W_ARRIVAL[1] * DAY_MS))
    dwell_flags = _count_flags(flags, t_a + W_DWELL[0] * DAY_MS,
                               t_a + W_DWELL[1] * DAY_MS, closed_lo=False)
    f["dwell_correction_rate"] = float(dwell_flags) * (30.0 / (W_DWELL[1] - W_DWELL[0]))

    if a is None:
        return _finish(f)

    e = a.epoch_ms.astype(np.float64)
    d = a.drift

    # ---- baselines (prereg 3.1) -----------------------------------------
    pre = np.where(e < t_s)[0]
    d_base = (float(np.median(d[pre[-BASELINE_SAMPLES:]]))
              if pre.size >= BASELINE_SAMPLES else float("nan"))
    m_tr = _window(e, t_s + W_INIT[0] * DAY_MS, t_a)
    amp = float("nan")
    if np.any(m_tr):
        dev = np.abs(d[m_tr] - d_base) if np.isfinite(d_base) else np.abs(d[m_tr])
        d_plateau = float(d[m_tr][int(np.argmax(dev))])
        amp = (abs(d_plateau - d_base) if np.isfinite(d_base) else abs(d_plateau))

    # ---- initiation (prereg 3.2) ----------------------------------------
    if np.isfinite(amp) and amp > 0 and np.isfinite(d_base) and np.any(m_tr):
        tt = (e[m_tr] - t_s) / DAY_MS
        dev = np.abs(d[m_tr] - d_base)
        t10 = _first_crossing(tt, dev, 0.1 * amp)
        t90 = _first_crossing(tt, dev, 0.9 * amp)
        if np.isfinite(t10) and np.isfinite(t90):
            f["init_ramp_days"] = max(t90 - t10, 0.0)
    ramp = f["init_ramp_days"]
    if np.isfinite(amp):
        f["init_abruptness"] = amp / max(ramp if np.isfinite(ramp) else 0.0,
                                         RAMP_FLOOR_DAYS)

    # ---- transit (prereg 3.3) -------------------------------------------
    m_full = _window(e, t_s, t_a)
    peak = float("nan")
    if np.any(m_full):
        ad = np.abs(d[m_full])
        peak = float(np.max(ad))
        f["transit_drift_peak"] = peak
        f["transit_drift_flatness"] = (float(np.mean(ad) / peak) if peak > 0
                                       else float("nan"))

    # ---- arrival (prereg 3.4) -------------------------------------------
    m_arr = _window(e, t_a - 5.0 * DAY_MS, t_a + 5.0 * DAY_MS)
    if np.count_nonzero(m_arr) >= 2:
        f["arrival_brake_mag"] = float(np.max(np.abs(np.diff(d[m_arr]))))
    m_res = _window(e, t_a, t_a + 5.0 * DAY_MS)
    if np.any(m_res):
        f["arrival_residual_drift"] = float(np.median(np.abs(d[m_res])))
    if np.isfinite(peak) and peak > 0:
        m_br = _window(e, t_s, t_a + 5.0 * DAY_MS)
        hot = np.where(m_br & (np.abs(d) >= 0.5 * peak))[0]
        if hot.size:
            k0 = int(hot[-1])
            after = np.where((np.arange(d.size) > k0)
                             & (np.abs(d) <= 0.1 * peak)
                             & (e <= t_a + BRAKE_LIMIT_DAYS * DAY_MS))[0]
            if after.size:
                f["arrival_brake_days"] = float((e[int(after[0])] - e[k0]) / DAY_MS)

    # ---- the pair series: overshoot and the relative-longitude structure --
    if b is not None:
        packed = pg.pair_separation(a, b, 0.0)
        if packed is not None:
            t, _la, _lb, sep, _abs_sep = packed
            sgn = float(np.sign(np.interp(t_s, t, sep))) if t.size else 0.0
            if sgn == 0.0:
                sgn = float(np.sign(sep[0])) if sep.size else 1.0
            m_over = _window(t, t_a, t_a + OVERSHOOT_WINDOW_DAYS * DAY_MS)
            if np.any(m_over):
                f["arrival_overshoot_deg"] = float(max(0.0, np.max(-sgn * sep[m_over])))
            # ---- dwell, FIRST 30 DAYS ONLY (prereg 3) --------------------
            m_dw = _window(t, t_a, t_a + DWELL_WINDOW_DAYS * DAY_MS)
            if np.count_nonzero(m_dw) >= 3:
                sd = sep[m_dw]
                f["dwell_rel_amplitude"] = float(
                    0.5 * (np.percentile(sd, 95) - np.percentile(sd, 5)))
                days = np.round((t[m_dw] - t_a) / DAY_MS).astype(int)
                grid = np.full(int(DWELL_WINDOW_DAYS) + 1, np.nan)
                for di, sv in zip(days, sd):
                    if 0 <= di < grid.size:
                        grid[di] = sv
                per, frac = autocorr_period(grid, PERIOD_LAGS[0], PERIOD_LAGS[1])
                f["dwell_rel_period_days"] = per
                f["dwell_rel_osc_fraction"] = frac

    m_sk = _window(e, t_a, t_a + DWELL_WINDOW_DAYS * DAY_MS)
    if np.count_nonzero(m_sk) >= 3:
        tt = (e[m_sk] - t_a) / DAY_MS
        yy = a.lam_unwrapped[m_sk]
        slope, intercept = np.polyfit(tt, yy, 1)
        f["dwell_sk_tightness"] = _mad(yy - (slope * tt + intercept))

    # ---- departure (prereg 3.6) -----------------------------------------
    if t_d is not None:
        k_a = int(np.argmin(np.abs(e - t_a)))
        k_s = int(np.argmin(np.abs(e - t_s)))
        drift_dir = float(np.sign(a.lam_unwrapped[k_a] - a.lam_unwrapped[k_s]))
        if dd is not None and drift_dir != 0.0:
            f["departure_reverses"] = 1.0 if float(np.sign(float(dd))) == drift_dir else -1.0
        lon0 = float(event["loiterLongitudeDeg"])
        for i0, i1 in segs_by_norad.get(event["approacherNorad"], []):
            if (a.grid_lo + i0) * DAY_MS >= float(t_d):
                lon = float(pg.wrap180(np.median(a.grid[i0:i1 + 1])))
                f["departure_dest_distance_deg"] = abs(float(pg.wrap180(lon - lon0)))
                break

    return _finish(f)


def _finish(f):
    """prereg 3.9 -- the five missingness indicators, computed last from the
    features themselves so they cannot disagree with them."""
    f["miss_init_flag"] = 0.0 if np.isfinite(f["init_drift_change_mag"]) else 1.0
    f["miss_ramp"] = 0.0 if np.isfinite(f["init_ramp_days"]) else 1.0
    f["miss_brake_days"] = 0.0 if np.isfinite(f["arrival_brake_days"]) else 1.0
    f["miss_dwell_period"] = 0.0 if np.isfinite(f["dwell_rel_period_days"]) else 1.0
    f["miss_departure"] = 0.0 if np.isfinite(f["departure_drift_abs"]) else 1.0
    return f


def _arrival_month(event):
    return (event.get("arrivalIso") or "")[:7]


def cadence_table(events):
    """prereg 3.7. Ordered by arrival, ties broken by target NORAD so the
    order is total and reproducible."""
    by_obj = {}
    for e in events:
        by_obj.setdefault(e["approacherNorad"], []).append(e)
    out = {}
    for group in by_obj.values():
        group = sorted(group, key=lambda e: (e["arrivalMs"], e["targetNorad"]))
        for i, e in enumerate(group):
            prior = group[:i]
            out[id(e)] = {
                "daysSincePrev": ((e["arrivalMs"] - prior[-1]["arrivalMs"]) / DAY_MS
                                  if prior else float("nan")),
                "priorEvents": len(prior),
                "priorTargets": len({p["targetNorad"] for p in prior}),
                "priorArrivals": len({_arrival_month(p) for p in prior}),
            }
    return out


# ==========================================================================
# prereg 3.11 -- transform, impute, standardise (fold-aware)
# ==========================================================================
def transform(matrix, names):
    """log(x + eps) on the registered subset; the rest raw (prereg 3.11)."""
    out = np.array(matrix, dtype=np.float64, copy=True)
    for j, name in enumerate(names):
        if name in LOG_FEATURES:
            col = out[:, j]
            ok = np.isfinite(col) & (col >= 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                out[:, j] = np.where(ok, np.log(col + LOG_EPS), np.nan)
    return out


def fold_scaler(train):
    """Medians, means and sds from the TRAINING fold only (prereg 3.11)."""
    with np.errstate(invalid="ignore"):
        med = np.nanmedian(train, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    filled = np.where(np.isfinite(train), train, med)
    mu = filled.mean(axis=0)
    sd = filled.std(axis=0)
    keep = sd > 0
    return {"median": med, "mean": mu, "sd": np.where(keep, sd, 1.0), "keep": keep}


def apply_scaler(x, scaler):
    filled = np.where(np.isfinite(x), x, scaler["median"])
    z = (filled - scaler["mean"]) / scaler["sd"]
    return z[:, scaler["keep"]]


# ==========================================================================
# prereg 4 -- k-means, the silhouette criterion, the gap statistic
# ==========================================================================
def _sqdist(x, centres):
    """||x - c||^2 via the expansion, which is what makes the 112 fold refits
    of prereg 6.3 affordable on one core."""
    return (np.sum(x * x, axis=1)[:, None]
            - 2.0 * (x @ centres.T)
            + np.sum(centres * centres, axis=1)[None, :])


def _kmeans_once(x, k, rng):
    n = x.shape[0]
    centres = np.empty((k, x.shape[1]))
    centres[0] = x[rng.integers(n)]
    closest = np.sum((x - centres[0]) ** 2, axis=1)
    for i in range(1, k):
        total = float(closest.sum())
        if total <= 0:
            centres[i] = x[rng.integers(n)]
        else:
            centres[i] = x[int(rng.choice(n, p=closest / total))]
        closest = np.minimum(closest, np.sum((x - centres[i]) ** 2, axis=1))
    prev = np.inf
    labels = np.zeros(n, dtype=np.int64)
    for _ in range(MAX_ITER):
        d2 = _sqdist(x, centres)
        labels = np.argmin(d2, axis=1)
        inertia = float(np.maximum(d2[np.arange(n), labels], 0.0).sum())
        far = int(np.argmax(d2[np.arange(n), labels]))
        for c in range(k):
            m = labels == c
            centres[c] = x[m].mean(axis=0) if np.any(m) else x[far]
        if prev - inertia <= TOL:
            break
        prev = inertia
    d2 = _sqdist(x, centres)
    labels = np.argmin(d2, axis=1)
    inertia = float(np.maximum(d2[np.arange(n), labels], 0.0).sum())
    return labels, centres, inertia


def kmeans(x, k, seed=SEED, n_init=N_INIT):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_init):
        cand = _kmeans_once(x, k, rng)
        if best is None or cand[2] < best[2]:
            best = cand
    return best


def silhouette(x, labels):
    """Mean silhouette coefficient, Euclidean."""
    n = x.shape[0]
    uniq = np.unique(labels)
    if uniq.size < 2 or n < 3:
        return float("nan")
    g = x @ x.T
    sq = np.diag(g)
    d = np.sqrt(np.maximum(sq[:, None] - 2.0 * g + sq[None, :], 0.0))
    sums = np.stack([d[:, labels == c].sum(axis=1) for c in uniq])
    counts = np.array([int(np.count_nonzero(labels == c)) for c in uniq], dtype=float)
    pos = {int(c): i for i, c in enumerate(uniq)}
    own = np.array([pos[int(l)] for l in labels])
    a = np.array([sums[own[i], i] / max(counts[own[i]] - 1.0, 1.0) for i in range(n)])
    means = sums / counts[:, None]
    means[own, np.arange(n)] = np.inf
    b = means.min(axis=0)
    denom = np.maximum(a, b)
    s = np.where((denom > 0) & (counts[own] > 1), (b - a) / np.where(denom > 0, denom, 1.0), 0.0)
    return float(np.mean(s))


def choose_k(x, k_range=K_RANGE, seed=SEED):
    """prereg 4 PRIMARY CRITERION: max mean silhouette over k, ties (< 1e-6)
    broken toward the SMALLER k. Nothing is eyeballed."""
    rows = []
    for k in k_range:
        labels, _c, inertia = kmeans(x, k, seed=seed)
        rows.append({"k": int(k), "silhouette": silhouette(x, labels),
                     "inertia": inertia,
                     "sizes": [int(np.count_nonzero(labels == c)) for c in range(k)]})
    best_sil = max(r["silhouette"] for r in rows)
    chosen = min(r["k"] for r in rows if r["silhouette"] > best_sil - 1e-6)
    return int(chosen), rows


def gap_statistic(x, k_range=K_RANGE, b=GAP_B, seed=SEED):
    """prereg 4 SECONDARY, reported and governing nothing."""
    rng = np.random.default_rng(seed)
    mean = x.mean(axis=0)
    xc = x - mean
    _u, _s, vt = np.linalg.svd(xc, full_matrices=False)
    xp = xc @ vt.T
    lo, hi = xp.min(axis=0), xp.max(axis=0)
    rows = []
    for k in k_range:
        _l, _c, inertia = kmeans(x, k, seed=seed)
        ref = []
        for _ in range(b):
            z = rng.uniform(lo, hi, size=xp.shape) @ vt + mean
            _l2, _c2, wk = kmeans(z, k, seed=int(rng.integers(1, 2 ** 31)),
                                  n_init=GAP_REF_N_INIT)
            ref.append(math.log(max(wk, 1e-300)))
        ref = np.asarray(ref)
        rows.append({"k": int(k),
                     "gap": float(ref.mean() - math.log(max(inertia, 1e-300))),
                     "sk": float(ref.std() * math.sqrt(1.0 + 1.0 / b))})
    chosen = None
    for i, r in enumerate(rows[:-1]):
        if r["gap"] >= rows[i + 1]["gap"] - rows[i + 1]["sk"]:
            chosen = r["k"]
            break
    return int(chosen if chosen is not None else rows[-1]["k"]), rows


def assign(x, centres):
    return np.argmin(_sqdist(x, centres), axis=1)


# ==========================================================================
# prereg 4 -- stability; prereg 8 -- the partition comparisons
# ==========================================================================
def bootstrap_stability(matrix, names, objects, k, draws=STABILITY_DRAWS, seed=SEED):
    """Approachers are resampled, not events (prereg 4)."""
    rng = np.random.default_rng(seed)
    raw = transform(matrix, names)
    x_all = apply_scaler(raw, fold_scaler(raw))
    base_labels, _c, _i = kmeans(x_all, k, seed=seed)
    base_sets = [set(np.where(base_labels == c)[0].tolist()) for c in range(k)]
    scores = [[] for _ in range(k)]
    uniq = np.unique(objects)
    index = {int(o): np.where(objects == o)[0] for o in uniq}
    for _ in range(draws):
        drawn = rng.choice(uniq, size=uniq.size, replace=True)
        idx = np.concatenate([index[int(o)] for o in drawn])
        sub = raw[idx]
        xb = apply_scaler(sub, fold_scaler(sub))
        lb, _cb, _ib = kmeans(xb, k, seed=seed, n_init=10)
        boot_sets = [set(idx[lb == c].tolist()) for c in range(k)]
        for c in range(k):
            best = 0.0
            for s in boot_sets:
                union = len(base_sets[c] | s)
                if union:
                    best = max(best, len(base_sets[c] & s) / union)
            scores[c].append(best)
    return base_labels, [float(np.median(s)) for s in scores]


def adjusted_rand(a, b):
    a, b = np.asarray(a), np.asarray(b)
    ua, ub = np.unique(a), np.unique(b)
    table = np.array([[int(np.count_nonzero((a == va) & (b == vb))) for vb in ub]
                      for va in ua], dtype=float)
    n = float(a.size)

    def c2(v):
        return v * (v - 1.0) / 2.0
    sum_ij = c2(table).sum()
    sum_i = c2(table.sum(axis=1)).sum()
    sum_j = c2(table.sum(axis=0)).sum()
    total = c2(n)
    expected = sum_i * sum_j / total if total else 0.0
    maximum = 0.5 * (sum_i + sum_j)
    return float((sum_ij - expected) / (maximum - expected)) if maximum != expected else 0.0


def eta_squared(values, labels):
    """Between-group variance fraction (prereg 8, gate S)."""
    v = np.asarray(values, dtype=np.float64)
    ok = np.isfinite(v)
    v, lab = v[ok], np.asarray(labels)[ok]
    if v.size < 3:
        return float("nan")
    grand = float(v.mean())
    ss_total = float(((v - grand) ** 2).sum())
    if ss_total <= 0:
        return float("nan")
    ss_between = sum(int(np.count_nonzero(lab == c)) * (float(v[lab == c].mean()) - grand) ** 2
                     for c in np.unique(lab))
    return float(ss_between / ss_total)


# ==========================================================================
# prereg 6 -- the estimands
# ==========================================================================
def t8a_baseline(events, key):
    """prereg 6.1/6.2 -- T8a 5.2's protocol, so gate V can check it."""
    by_obj = {}
    for e in events:
        by_obj.setdefault(e["approacherNorad"], []).append(e)
    repeaters = {n: v for n, v in by_obj.items() if len(v) >= 2}
    pop_vals = [e[key] for e in events
                if e.get(key) is not None and np.isfinite(e[key]) and e[key] > 0]
    if len(pop_vals) < 3:
        return None
    pop_median = float(np.median(np.log(pop_vals)))
    own_err, pop_err, groups = [], [], []
    for norad, v in repeaters.items():
        vals = [math.log(e[key]) for e in v
                if e.get(key) is not None and np.isfinite(e[key]) and e[key] > 0]
        if len(vals) < 2:
            continue
        for i in range(len(vals)):
            others = vals[:i] + vals[i + 1:]
            own_err.append(abs(vals[i] - float(np.median(others))))
            pop_err.append(abs(vals[i] - pop_median))
            groups.append(norad)
    if not own_err:
        return None
    lo, hi = bootstrap_skill(own_err, pop_err, groups)
    return {"n": len(own_err), "maeOwnLog": float(np.mean(own_err)),
            "maePopulationLog": float(np.mean(pop_err)),
            "skill": float(1.0 - np.mean(own_err) / np.mean(pop_err)),
            "ci95": [lo, hi]}


def bootstrap_skill(model_err, pop_err, groups, draws=SKILL_BOOTSTRAP, seed=SEED):
    """prereg 6.8: resample APPROACHERS, not events."""
    model_err = np.asarray(model_err, dtype=np.float64)
    pop_err = np.asarray(pop_err, dtype=np.float64)
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    if uniq.size < 2:
        return None, None
    rng = np.random.default_rng(seed)
    index = {int(o): np.where(groups == o)[0] for o in uniq}
    out = []
    for _ in range(draws):
        drawn = rng.choice(uniq, size=uniq.size, replace=True)
        idx = np.concatenate([index[int(o)] for o in drawn])
        pe = float(pop_err[idx].mean())
        if pe > 0:
            out.append(1.0 - float(model_err[idx].mean()) / pe)
    if not out:
        return None, None
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def fold_models(matrix, names, objects, k, seed=SEED):
    """prereg 6.3 -- one leave-one-OBJECT-out refit per approacher, computed
    once and reused by every estimand that shares (feature set, k). The
    transform, imputation and standardisation constants come from the fold."""
    raw = transform(matrix, names)
    objects = np.asarray(objects)
    out = {}
    for norad in np.unique(objects):
        out_mask = objects == norad
        train = np.where(~out_mask)[0]
        if train.size < k + 1:
            continue
        sc = fold_scaler(raw[train])
        x_tr = apply_scaler(raw[train], sc)
        labels_tr, centres, _i = kmeans(x_tr, k, seed=seed)
        held = np.where(out_mask)[0]
        x_ho = apply_scaler(raw[held], sc)
        out[int(norad)] = {"train": train, "labelsTrain": labels_tr,
                           "centres": centres, "held": held,
                           "labelsHeld": assign(x_ho, centres), "xHeld": x_ho}
    return out


def cluster_skill(events, folds, objects, k, outcome_key,
                  prior_only=False, self_assign=False):
    """prereg 6.3-6.7.

    `self_assign`  E2/E3c: the held-out event is assigned by its OWN features.
    `prior_only`   E1b/E3b: the cluster comes from strictly PRIOR events only.
    otherwise      E1a/E3a: the modal cluster of the object's OTHER events.
    """
    objects = np.asarray(objects)
    vals = np.array([math.log(e[outcome_key])
                     if (e.get(outcome_key) is not None
                         and np.isfinite(e[outcome_key]) and e[outcome_key] > 0)
                     else np.nan for e in events])
    finite = vals[np.isfinite(vals)]
    if finite.size < 3:
        return {"n": 0, "skill": None}
    pop_median = float(np.median(finite))
    model_err, pop_err, groups = [], [], []
    for norad, fold in folds.items():
        held = fold["held"]
        if not self_assign and held.size < 2:
            continue
        order = sorted(range(held.size), key=lambda j: events[held[j]]["arrivalMs"])
        train_vals = vals[fold["train"]]
        for pos, j in enumerate(order):
            i = int(held[j])
            if not np.isfinite(vals[i]):
                continue
            if self_assign:
                cluster = int(fold["labelsHeld"][j])
            else:
                peers = ([order[p] for p in range(pos)] if prior_only
                         else [order[p] for p in range(len(order)) if p != pos])
                if not peers:
                    continue
                peer_lab = [int(fold["labelsHeld"][p]) for p in peers]
                counts = np.bincount(peer_lab, minlength=k)
                top = int(counts.max())
                tied = [c for c in range(k) if counts[c] == top]
                if len(tied) == 1:
                    cluster = tied[0]
                else:
                    mean_vec = fold["xHeld"][peers].mean(axis=0)
                    cluster = tied[int(np.argmin(
                        [float(np.sum((mean_vec - fold["centres"][c]) ** 2))
                         for c in tied]))]
            pool = train_vals[fold["labelsTrain"] == cluster]
            pool = pool[np.isfinite(pool)]
            if pool.size == 0:
                continue
            model_err.append(abs(vals[i] - float(np.median(pool))))
            pop_err.append(abs(vals[i] - pop_median))
            groups.append(int(norad))
    if not model_err or float(np.mean(pop_err)) <= 0:
        return {"n": len(model_err), "skill": None}
    lo, hi = bootstrap_skill(model_err, pop_err, groups)
    return {"n": len(model_err),
            "skill": float(1.0 - np.mean(model_err) / np.mean(pop_err)),
            "maeModelLog": float(np.mean(model_err)),
            "maePopulationLog": float(np.mean(pop_err)),
            "ci95": [lo, hi], "objects": len(set(groups))}


def posthoc_diagnostics(events, matrix, objects, folds, labels, k, outcome_key,
                        neighbours=10, seed=SEED):
    """POST-REGISTRATION, labelled as such in the manner of T8a 7.4 and
    T8b 7.3. Changes no registered verdict and is not a registered estimand.

    Three questions the registered estimands cannot separate:

    D1  a CONTINUOUS predictor over the same rich features -- the median of
        the `neighbours` nearest training events in the same fold's
        standardised space. If D1 beats the baseline where the clustered
        predictor does not, the discretisation is what costs the skill; if it
        does not, the features carry no more about this outcome than the
        object's own two-number history does.
    D2  the cluster median and the object's own-history median averaged in
        log space -- the cheapest way to use both predictors at once.
    D3  the between-OBJECT variance fraction of the outcome, which bounds
        what ANY object-level predictor can achieve.
    """
    objects = np.asarray(objects)
    vals = np.array([math.log(e[outcome_key])
                     if (e.get(outcome_key) is not None
                         and np.isfinite(e[outcome_key]) and e[outcome_key] > 0)
                     else np.nan for e in events])
    finite = vals[np.isfinite(vals)]
    pop_median = float(np.median(finite))
    raw = transform(matrix, FEATURE_NAMES)
    d1 = {"model": [], "pop": [], "grp": []}
    d2 = {"model": [], "pop": [], "grp": []}
    for norad, fold in folds.items():
        held, train = fold["held"], fold["train"]
        sc = fold_scaler(raw[train])
        x_tr = apply_scaler(raw[train], sc)
        train_vals = vals[train]
        order = sorted(range(held.size), key=lambda j: events[held[j]]["arrivalMs"])
        own_vals = [vals[int(held[j])] for j in range(held.size)]
        for pos, j in enumerate(order):
            i = int(held[j])
            if not np.isfinite(vals[i]):
                continue
            d2_own = [own_vals[order[p]] for p in range(len(order)) if p != pos]
            d2_own = [v for v in d2_own if np.isfinite(v)]
            # D1: nearest training events, in this fold's own space
            d = _sqdist(fold["xHeld"][j:j + 1], x_tr)[0]
            near = np.argsort(d)[:neighbours]
            pool = train_vals[near]
            pool = pool[np.isfinite(pool)]
            if pool.size:
                d1["model"].append(abs(vals[i] - float(np.median(pool))))
                d1["pop"].append(abs(vals[i] - pop_median))
                d1["grp"].append(int(norad))
            # D2: the cluster median and the own-history median, averaged
            if d2_own:
                peer_lab = [int(fold["labelsHeld"][order[p]])
                            for p in range(len(order)) if p != pos]
                counts = np.bincount(peer_lab, minlength=k)
                cluster = int(np.argmax(counts))
                cpool = train_vals[fold["labelsTrain"] == cluster]
                cpool = cpool[np.isfinite(cpool)]
                if cpool.size:
                    pred = 0.5 * (float(np.median(cpool)) + float(np.median(d2_own)))
                    d2["model"].append(abs(vals[i] - pred))
                    d2["pop"].append(abs(vals[i] - pop_median))
                    d2["grp"].append(int(norad))

    def _pack(bag, label):
        if not bag["model"]:
            return {"n": 0, "skill": None, "label": label}
        lo, hi = bootstrap_skill(bag["model"], bag["pop"], bag["grp"])
        return {"n": len(bag["model"]), "label": label,
                "skill": float(1.0 - np.mean(bag["model"]) / np.mean(bag["pop"])),
                "maeModelLog": float(np.mean(bag["model"])),
                "maePopulationLog": float(np.mean(bag["pop"])),
                "ci95": [lo, hi], "objects": len(set(bag["grp"]))}

    return {
        "D1_knn": _pack(d1, f"{neighbours}-nearest training events, continuous"),
        "D2_cluster_plus_own": _pack(d2, "cluster median and own-history median, averaged"),
        "D3_betweenObjectEta2": eta_squared(vals, objects),
        "D3_betweenClusterEta2": eta_squared(vals, labels),
        "POST_REGISTRATION": True,
    }


def next_interval_events(events, matrix):
    """prereg 6.7 -- the outcome is the interval to the approacher's NEXT
    event, so an object's last event has none and is dropped."""
    col = FEATURE_NAMES.index("cadence_days_since_prev")
    by_obj = {}
    for i, e in enumerate(events):
        by_obj.setdefault(e["approacherNorad"], []).append(i)
    out_events, keep = [], []
    for idxs in by_obj.values():
        idxs = sorted(idxs, key=lambda i: (events[i]["arrivalMs"],
                                           events[i]["targetNorad"]))
        for pos in range(len(idxs) - 1):
            nxt = matrix[idxs[pos + 1], col]
            if np.isfinite(nxt) and nxt > 0:
                d = dict(events[idxs[pos]])
                d["nextIntervalDays"] = float(nxt)
                out_events.append(d)
                keep.append(idxs[pos])
    return out_events, np.asarray(keep, dtype=np.int64)


# ==========================================================================
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_features(events, provenance):
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=1")
    norads = ({e["approacherNorad"] for e in events}
              | {e["targetNorad"] for e in events})
    t0 = time.time()
    series = load_series(db, norads)
    load_s = time.time() - t0
    sigma_n = float(provenance["sigma_n_deg_per_day"])
    flags, segs = {}, {}
    for norad, s in series.items():
        attach_grid(s)
        flags[norad], _mag = pg.drift_change_flags(s, sigma_n)
        segs[norad] = pg.station_segments(s)
    cad = cadence_table(events)
    matrix = np.full((len(events), len(FEATURE_NAMES)), np.nan)
    for i, e in enumerate(events):
        f = event_features(e, series, flags, segs, cad)
        for j, name in enumerate(FEATURE_NAMES):
            matrix[i, j] = f[name]
    db.close()
    return matrix, len(series), load_s


def describe_clusters(events, matrix, objects, labels, x, keep, k):
    kept = [n for n, ok in zip(FEATURE_NAMES, keep) if ok]
    rows = []
    for c in range(k):
        m = labels == c
        idxs = np.where(m)[0]
        zc = x[m].mean(axis=0)
        order = np.argsort(-np.abs(zc))[:5]
        row = {
            "cluster": int(c), "n": int(m.sum()),
            "objects": int(len(set(objects[m].tolist()))),
            "top": [{"feature": kept[int(o)], "z": float(zc[int(o)])} for o in order],
            "centroid": {}, "outcomes": {},
            "flaggedFraction": float(np.mean(
                [1.0 if events[i].get("initiatingFlagMs") is not None else 0.0
                 for i in idxs])),
            "librationFraction": float(np.mean(
                [1.0 if events[i].get("libration_zone") else 0.0 for i in idxs])),
        }
        for j, name in enumerate(FEATURE_NAMES):
            col = matrix[m, j]
            col = col[np.isfinite(col)]
            row["centroid"][name] = float(np.median(col)) if col.size else None
        for key in OUTCOMES:
            v = np.array([events[i][key] for i in idxs
                          if events[i].get(key) is not None], dtype=np.float64)
            v = v[np.isfinite(v)]
            if v.size:
                row["outcomes"][key] = {
                    "n": int(v.size), "p25": float(np.percentile(v, 25)),
                    "median": float(np.median(v)),
                    "p75": float(np.percentile(v, 75)),
                    "p95": float(np.percentile(v, 95))}
        cad = matrix[m, FEATURE_NAMES.index("cadence_days_since_prev")]
        cad = cad[np.isfinite(cad)]
        row["cadenceDays"] = {
            "n": int(cad.size),
            "p25": float(np.percentile(cad, 25)) if cad.size else None,
            "median": float(np.median(cad)) if cad.size else None,
            "p75": float(np.percentile(cad, 75)) if cad.size else None}
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=("features", "analyze", "all"), default="all")
    ap.add_argument("--work", type=Path, required=True,
                    help="working directory for this arm's intermediate extracts")
    ap.add_argument("--arm", choices=("primary", "flagged"), default="primary")
    args = ap.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    started, cpu0 = time.time(), time.process_time()

    provenance, rows = load_events()
    events = primary_arm(rows)
    if args.arm == "flagged":
        events = [e for e in events if e.get("initiatingFlagMs") is not None]
    events.sort(key=lambda e: (e["approacherNorad"], e["arrivalMs"], e["targetNorad"]))
    print(f"  arm={args.arm}: {len(events)} events", flush=True)

    feat_path = args.work / f"features-{args.arm}.npz"
    load_s, n_series = None, None
    if args.stage in ("features", "all") or not feat_path.exists():
        matrix, n_series, load_s = build_features(events, provenance)
        np.savez(feat_path, matrix=matrix,
                 objects=np.array([e["approacherNorad"] for e in events], dtype=np.int64))
        print(f"  {n_series} element histories in {load_s:.1f}s; "
              f"feature table {matrix.shape}", flush=True)
        if args.stage == "features":
            return {"features": list(matrix.shape)}
    with np.load(feat_path) as z:
        matrix, objects = z["matrix"], z["objects"]

    result = {"schema": 1, "registration": REGISTRATION, "arm": args.arm,
              "events": len(events), "approachers": int(np.unique(objects).size),
              "featureNames": list(FEATURE_NAMES),
              "elementHistories": n_series, "historyLoadSeconds": load_s,
              "missingFraction": {n: float(np.mean(~np.isfinite(matrix[:, j])))
                                  for j, n in enumerate(FEATURE_NAMES)}}

    # ---- prereg 4: the taxonomy -----------------------------------------
    raw = transform(matrix, FEATURE_NAMES)
    sc = fold_scaler(raw)
    x = apply_scaler(raw, sc)
    k, sweep = choose_k(x)
    result["kSweep"], result["kChosen"] = sweep, k
    gk, grows = gap_statistic(x)
    result["gap"] = {"kChosen": gk, "rows": grows}
    labels, _centres, _in = kmeans(x, k)
    result["clusterSizes"] = [int(np.count_nonzero(labels == c)) for c in range(k)]
    result["clusters"] = describe_clusters(events, matrix, objects, labels, x,
                                           sc["keep"], k)
    _bl, jaccard = bootstrap_stability(matrix, FEATURE_NAMES, objects, k)
    result["stabilityJaccard"] = jaccard

    flagged = np.array([1 if e.get("initiatingFlagMs") is not None else 0
                        for e in events])
    result["ariFlagged"] = adjusted_rand(labels, flagged)
    loiter_log = np.array([math.log(e["loiterDays"]) for e in events])
    result["eta2Loiter"] = eta_squared(loiter_log, labels)
    result["eta2Separation"] = eta_squared(
        np.array([math.log(e["closestSeparationDeg"])
                  if e["closestSeparationDeg"] > 0 else np.nan for e in events]),
        labels)

    # ---- prereg 5: the causal taxonomy ----------------------------------
    cidx = [FEATURE_NAMES.index(n) for n in CAUSAL_FEATURES]
    craw = transform(matrix[:, cidx], CAUSAL_FEATURES)
    csc = fold_scaler(craw)
    cx = apply_scaler(craw, csc)
    ck, csweep = choose_k(cx)
    clabels, _cc, _ci = kmeans(cx, ck)
    result["causal"] = {
        "kChosen": ck, "kSweep": csweep, "features": list(CAUSAL_FEATURES),
        "clusterSizes": [int(np.count_nonzero(clabels == c)) for c in range(ck)],
        "eta2Loiter": eta_squared(loiter_log, clabels),
        "ariFlagged": adjusted_rand(clabels, flagged),
        "ariWithFull": adjusted_rand(clabels, labels),
        "clusters": describe_clusters(events, matrix, objects, clabels, cx,
                                      csc["keep"], ck)}

    # ---- prereg 6.2: gate V, before anything else -----------------------
    result["gateV"] = {key: t8a_baseline(events, key) for key in OUTCOMES}

    # ---- prereg 6.3-6.7: the estimands ----------------------------------
    t0 = time.time()
    folds = fold_models(matrix, FEATURE_NAMES, objects, k)
    cfolds = fold_models(matrix[:, cidx], CAUSAL_FEATURES, objects, ck)
    result["foldSeconds"] = time.time() - t0
    est = {
        "E1a_loiter": cluster_skill(events, folds, objects, k, "loiterDays"),
        "E1b_loiter": cluster_skill(events, folds, objects, k, "loiterDays",
                                    prior_only=True),
        "E2_loiter": cluster_skill(events, cfolds, objects, ck, "loiterDays",
                                   self_assign=True),
        "E3a_separation": cluster_skill(events, folds, objects, k,
                                        "closestSeparationDeg"),
        "E3b_separation": cluster_skill(events, folds, objects, k,
                                        "closestSeparationDeg", prior_only=True),
        "E3c_separation": cluster_skill(events, cfolds, objects, ck,
                                        "closestSeparationDeg", self_assign=True),
    }
    e4_events, e4_keep = next_interval_events(events, matrix)
    if len(e4_events) >= 10:
        e4_folds = fold_models(matrix[e4_keep], FEATURE_NAMES, objects[e4_keep], k)
        est["E4_interval"] = cluster_skill(e4_events, e4_folds, objects[e4_keep],
                                           k, "nextIntervalDays")
        est["E4_interval_prior"] = cluster_skill(e4_events, e4_folds,
                                                 objects[e4_keep], k,
                                                 "nextIntervalDays", prior_only=True)
        e4_pop = np.array([e["nextIntervalDays"] for e in e4_events])
        est["E4_population"] = {
            "n": int(e4_pop.size), "p25": float(np.percentile(e4_pop, 25)),
            "median": float(np.median(e4_pop)), "p75": float(np.percentile(e4_pop, 75))}
    result["estimands"] = est
    result["diagnostics"] = {
        "loiterDays": posthoc_diagnostics(events, matrix, objects, folds, labels,
                                          k, "loiterDays"),
        "closestSeparationDeg": posthoc_diagnostics(events, matrix, objects, folds,
                                                    labels, k, "closestSeparationDeg"),
    }

    # ---- prereg 8: the gates --------------------------------------------
    e1a = est["E1a_loiter"]["skill"]
    gv = result["gateV"]["loiterDays"]
    result["gates"] = {
        "P": bool(e1a is None or e1a <= GATE_P_BAR),
        "Q": bool(float(np.median(jaccard)) < GATE_Q_JACCARD),
        "R": bool(result["ariFlagged"] >= GATE_R_ARI),
        "S": bool(not np.isfinite(result["eta2Loiter"])
                  or result["eta2Loiter"] < GATE_S_ETA2),
        "T": bool(min(result["clusterSizes"]) < GATE_T_MIN_CLUSTER
                  or est["E1a_loiter"]["n"] < GATE_T_MIN_PREDICTIONS),
        "U": bool(float(np.mean([v > GATE_U_MISSING_FRACTION
                                 for v in result["missingFraction"].values()]))
                  > GATE_U_FEATURE_FRACTION),
        "V": bool(gv is None or abs(gv["skill"] - T8A_SKILL_LOITER) > GATE_V_TOLERANCE),
    }
    result["gateBars"] = {
        "P": GATE_P_BAR, "Q": GATE_Q_JACCARD, "R": GATE_R_ARI, "S": GATE_S_ETA2,
        "T": [GATE_T_MIN_CLUSTER, GATE_T_MIN_PREDICTIONS],
        "U": [GATE_U_FEATURE_FRACTION, GATE_U_MISSING_FRACTION],
        "V": GATE_V_TOLERANCE, "baselineLoiter": T8A_SKILL_LOITER,
        "baselineSeparation": T8A_SKILL_SEPARATION}

    wall = time.time() - started
    result.update({
        "wallSeconds": wall, "cpuSeconds": time.process_time() - cpu0,
        "gpuRaceRequired": bool(wall > GPU_RACE_SECONDS),
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "host": os.uname().nodename, "executionMode": "cpu",
        "eventsSha256": sha256_file(EVENTS_PATH),
        "sourceSha256": {
            "tools/alarm_pattern.py": sha256_file(Path(__file__)),
            "tools/proximity_geo.py": sha256_file(_REPO / "tools" / "proximity_geo.py"),
            REGISTRATION: sha256_file(_REPO / REGISTRATION)}})
    # The per-event feature table, committed beside the receipt. It carries
    # the approacher and target NORAD, the features, the two cluster labels
    # and the two outcomes -- and no catalogue metadata column of any kind.
    with open(args.work / f"alarm-pattern-features-{args.arm}.jsonl", "w") as fh:
        fh.write(json.dumps({
            "schema": 1, "record": "provenance", "study": "T8c pattern taxonomy",
            "registration": REGISTRATION, "arm": args.arm,
            "note": ("Features are the registered vector of prereg 3. `cluster` is "
                     "the prereg 4 taxonomy, `causalCluster` the prereg 5 one. "
                     "closestSeparationDeg is MEAN LONGITUDE separation, a slot "
                     "coordinate -- it is NOT a miss distance (T8a 1.1). No "
                     "catalogue metadata column is carried on any row."),
            "kChosen": int(k), "causalKChosen": int(ck),
            "eventsSha256": result["eventsSha256"]}) + "\n")
        for i, e in enumerate(events):
            row = {"approacherNorad": e["approacherNorad"],
                   "targetNorad": e["targetNorad"],
                   "arrivalIso": e.get("arrivalIso"),
                   "cluster": int(labels[i]), "causalCluster": int(clabels[i]),
                   "loiterDays": e["loiterDays"],
                   "closestSeparationDeg": e["closestSeparationDeg"]}
            for j, name in enumerate(FEATURE_NAMES):
                v = matrix[i, j]
                row[name] = (float(v) if np.isfinite(v) else None)
            fh.write(json.dumps(row) + "\n")
    (args.work / f"alarm-pattern-{args.arm}.json").write_text(
        json.dumps(result, indent=1, default=float))
    fired = [g for g, v in result["gates"].items() if v]
    print(f"  k={k} sizes={result['clusterSizes']} causal_k={ck}\n"
          f"  gateV reproduction={gv['skill'] if gv else None} "
          f"(T8a {T8A_SKILL_LOITER})\n"
          f"  E1a={e1a} E1b={est['E1b_loiter']['skill']} "
          f"E2={est['E2_loiter']['skill']}\n"
          f"  gates fired: {fired}   {wall:.1f}s wall", flush=True)
    return result


if __name__ == "__main__":
    main()
