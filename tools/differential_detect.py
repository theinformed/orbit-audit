#!/usr/bin/env python3
"""T21: differential (common-mode-rejecting) manoeuvre detection.

Registered in `docs/t21-differential-preregistration-20260923.md`, committed
alone before this file existed.

The idea under test: the dominant errors in public element sets are COMMON to
objects sharing an orbit at the same epoch, so differencing one object's
elements against a co-orbital reference cancels them and lowers the
detection floor.

The registration derives the whole question down to one measurable number.
Writing each object's detector residual as a shared term plus an independent
term,

    r_X(t) = c(t) + eps_X(t),      Var(c) = sc^2,  Var(eps) = s^2

the single-object noise scale is sc^2 + s^2 and the differential's is 2 s^2,
because c cancels identically at matched epochs. With
rho = Corr(r_A, r_B) = sc^2 / (sc^2 + s^2) that gives

    R = s_diff / s_single = sqrt(2 (1 - rho))

so differencing helps if and only if rho > 1/2. R is both PREDICTED from a
measured rho and MEASURED directly, and the two must agree or the model is
reported wrong (registration 5.1, P1).

Every shipped estimator is imported from `tools/proximity_plane.py` and
`tools/proximity_geo.py` and neither file is edited; a gate records that.

Usage:
  differential_detect.py --arm all --out docs/t21-differential-results-<date>.json
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import proximity_plane as pp                                      # noqa: E402
import proximity_geo as pg                                        # noqa: E402

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
GEO_WORK = REPO / "runtime" / "proximity-geo"
GEO_EPISODES = REPO / "docs" / "persistent-pairs-20260922.jsonl"

DAY_MS = 86400000.0

# ---- registered constants (registration sections 1, 3, 4, 5) --------------
BASELINE_FLAG_RATE = 0.012642669007901668     # flags per quiet-window-day, T18 E1
MAX_GAP_DAYS = pp.MAX_GAP_DAYS                # 5.0, refusal of interpolation
# The registered grid was k in [1, 12] step 0.25. It is EXTENDED here, and the
# extension is recorded as a deviation in the results: on these two spacecraft
# the measured noise floor is about 2 m of semi-major axis, so no multiplier
# below 12 comes anywhere near the shipped detector's false-flag rate -- the
# shipped pooled sigma is itself about 420 of these objects' own sigmas. A grid
# that cannot reach the operating point cannot answer the registered question.
K_GRID = np.concatenate([np.arange(1.0, 12.0001, 0.25),
                         np.unique(np.round(np.geomspace(12.5, 2.0e6, 400), 3))])
K_GRID_REGISTERED_MAX = 12.0
COINCIDENT_TOL_DAYS = 0.05                    # for the interpolation-free rho
BLOCK_DAYS_FLOOR = 30.0                       # floor-ratio block bootstrap
BLOCK_DAYS_RECALL = 90.0                      # recall increment block bootstrap
BOOTSTRAP_N = 1000
SEED = 20260923
MODEL_AGREEMENT_FACTOR = 1.25                 # P1
RHO_BAR = 0.5                                 # F1
MIN_QUIET_SAMPLES = 200                       # G6
MIN_QUIET_WINDOW_DAYS = 50.0                  # G7
EVALUABILITY_BAR = 0.10                       # G4
DIRECTION_SCREEN_BAR = 0.70                   # 3.9
EPOCH_SHIFT_DAYS = 180.0                      # C3
GEO_QUIET_GUARD_DAYS = 7.0                    # 4.4
GEO_AGREE_DAYS = 2.0                          # 4.5
GEO_CONTROL_SHIFT_DAYS = 30.0                 # 4.5
GEO_FLOOR_DEG_PER_DAY = pg.BURN_FLOOR_DEG_PER_DAY
I_FLOOR_DEG = pp.I_FLOOR_DEG

# the published floors this track is read against (registration section 1)
PUBLISHED = {
    "shippedPooledRecall": {"k": 90, "n": 1134, "rate": 0.07936507936507936,
                            "wilson95": [0.06501510889203253, 0.09655525523650489],
                            "source": "docs/t16b-truthset-recall-20260922.json"},
    "scheduleFloorPooled": {"k": 58, "n": 1134, "rate": 0.05114638447971781,
                            "wilson95": [0.039772, 0.065551],
                            "source": "docs/t18-floor-20260922.json"},
    "shippedSentinel3Only": {"k": 10, "n": 292, "sentinel3a": [2, 147],
                             "sentinel3b": [8, 145],
                             "source": "docs/t16b-truthset-recall-20260922.json bySpacecraft"},
    "scheduleFloorSentinel3Only": {"k": 5, "n": 292, "sentinel3a": [0, 147],
                                   "sentinel3b": [5, 145],
                                   "source": "docs/t18-floor-20260922.json bySpacecraft"},
    "shippedFloorMetres": [102.2, 126.0],
    "perObjectFloorMetres": 50.0,
    "baselineFlagRatePerQuietWindowDay": BASELINE_FLAG_RATE,
}

SAT_NORAD = {
    "cryosat-2": 36508, "hy-2a": 37781, "jason-1": 26997, "jason-2": 33105,
    "jason-3": 41240, "saral": 39086, "sentinel-3a": 41335,
    "sentinel-3b": 43437, "sentinel-6a": 46984, "swot": 54754,
    "topex-poseidon": 22076,
}
PAIR = ("sentinel-3a", "sentinel-3b")

DETECTOR_FILES = ("tools/proximity_plane.py", "tools/proximity_geo.py")

DA_BINS = ((0.0, 20.0), (20.0, 50.0), (50.0, 100.0), (100.0, 200.0),
           (200.0, 500.0), (500.0, math.inf))


# ==========================================================================
# Input
# ==========================================================================
def load_elements(norad: int):
    db = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=1")
    rows = db.execute(
        "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q,"
        " arg_perigee_q, mean_anomaly_q FROM element_set WHERE norad=?"
        " ORDER BY epoch_ms", (norad,)).fetchall()
    db.close()
    if not rows:
        return None
    a = np.asarray(rows, dtype=np.float64)
    return {"norad": norad, "epoch_ms": a[:, 0].astype(np.int64),
            "n": a[:, 1] / 1e8, "e": a[:, 2] / 1e8, "inc": a[:, 3] / 1e4,
            "raan": a[:, 4] / 1e4, "argp": a[:, 5] / 1e4, "ma": a[:, 6] / 1e4}


def parse_iso(text: str) -> float:
    text = text.strip()
    if not text:
        return float("nan")
    if text.endswith("Z"):
        text = text[:-1]
    return dt.datetime.fromisoformat(text).replace(
        tzinfo=dt.timezone.utc).timestamp() * 1000.0


def load_labels():
    events = {}
    with (MADLEO / "mission_reported__annotations__maneuver_annotations.csv").open() as fh:
        for row in csv.DictReader(fh):
            events[row["annotation_id"]] = {
                "id": row["annotation_id"], "sat": row["sat_id"],
                "eventMs": parse_iso(row["event_time_utc"]),
                "windowStartMs": parse_iso(row["window_start_utc"]),
                "windowEndMs": parse_iso(row["window_end_utc"]),
                "impulses": int(row["impulse_count"] or 0),
            }
    stable = []
    with (MADLEO / "mission_reported__annotations__stable_windows.csv").open() as fh:
        for row in csv.DictReader(fh):
            stable.append({"sat": row["sat_id"],
                           "startMs": parse_iso(row["window_start_utc"]),
                           "endMs": parse_iso(row["window_end_utc"])})
    return list(events.values()), stable


# ==========================================================================
# Registration 3.2 -- the differential series, on each host's own epochs
# ==========================================================================
def interpolate_refusing_gaps(t_src, y_src, t_out, max_gap_days=MAX_GAP_DAYS):
    """Linear interpolation of y_src onto t_out, NaN across any bracket wider
    than `max_gap_days` (registration 3.2). Refused points are returned as
    NaN so the caller can count them; nothing is silently dropped."""
    t = np.asarray(t_src, dtype=np.float64)
    y = np.asarray(y_src, dtype=np.float64)
    q = np.asarray(t_out, dtype=np.float64)
    out = np.full(q.shape, np.nan)
    if t.size < 2:
        return out
    j = np.searchsorted(t, q, side="right") - 1
    inside = (j >= 0) & (j <= t.size - 2)
    if not np.any(inside):
        exact = (j == t.size - 1) & (q == t[-1])
        out[exact] = y[-1]
        return out
    js = j[inside]
    gap_days = (t[js + 1] - t[js]) / DAY_MS
    ok = gap_days <= max_gap_days
    idx = np.where(inside)[0][ok]
    js = js[ok]
    frac = (q[idx] - t[js]) / (t[js + 1] - t[js])
    out[idx] = y[js] + frac * (y[js + 1] - y[js])
    last = (j == t.size - 1) & (q == t[-1])
    out[last] = y[-1]
    return out


def hold_one_out_error(t_ms, y, max_gap_days=MAX_GAP_DAYS):
    """Registration 3.3: interpolate every interior sample from its two
    neighbours and report (measured - interpolated). This measures the
    curvature error and the partner's own fit noise together, which is what
    the differential actually inherits."""
    t = np.asarray(t_ms, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if t.size < 3:
        return np.asarray([])
    lo, mid, hi = t[:-2], t[1:-1], t[2:]
    span = (hi - lo) / DAY_MS
    frac = np.where(hi > lo, (mid - lo) / np.where(hi > lo, hi - lo, 1.0), np.nan)
    pred = y[:-2] + frac * (y[2:] - y[:-2])
    err = y[1:-1] - pred
    err[span > max_gap_days] = np.nan
    return err


def build_differential(host, partner, channel):
    """D on the HOST's own epochs, the partner interpolated (registration 3.2).

    The host's values are exact, so a step by the host spacecraft is sharp and
    only the partner's is smeared. Both orderings are built by the caller, so
    the asymmetry is symmetrised rather than mistaken for a per-object result.
    """
    y_h = host[channel]
    y_p = interpolate_refusing_gaps(partner["epoch_ms"], partner[channel],
                                    host["epoch_ms"])
    return host["epoch_ms"], y_h - y_p, np.isfinite(y_p)


# ==========================================================================
# Registration 3.4 -- the shipped detector shape, applied to any series
# ==========================================================================
def confirmed_indices(stat, thr):
    """T8b prereg 5.4's confirmation rule, reimplemented because it is a
    closure inside `pp.detect_manoeuvres` and cannot be imported: two
    consecutive samples over the bar AND agreeing in sign; the flag index is
    the SECOND one, the first instant a causal observer held the evidence.
    Test T5 asserts this reproduces the shipped in-track flags exactly."""
    stat = np.asarray(stat, dtype=np.float64)
    thr = np.asarray(thr, dtype=np.float64)
    hit = np.abs(stat) > thr
    c = np.zeros(stat.size, dtype=bool)
    if stat.size > 1:
        c[1:] = (hit[1:] & hit[:-1]
                 & (np.sign(stat[1:]) == np.sign(stat[:-1])))
    return np.nonzero(c)[0]


def series_residual(epoch_ms, y):
    """The shipped rolling Theil-Sen residual, imported unchanged."""
    t_days = np.asarray(epoch_ms, dtype=np.float64) / DAY_MS
    return pp.rolling_theil_sen_residual(t_days, np.nan_to_num(y, nan=0.0))


def series_sigma(y):
    """The shipped `object_sigma_contributions` arithmetic: the MAD of the
    second difference, which annihilates any smooth secular trend."""
    y = np.asarray(y, dtype=np.float64)
    y = y[np.isfinite(y)]
    if y.size < 8:
        return float("nan")
    return pp.mad_sigma(pp.second_difference(y), math.sqrt(6.0))


def swept_flags(epoch_ms, y, sigma, k, usable=None):
    """Registration 3.5: the swept arms are threshold = k*sigma alone -- the
    50 m DA_FLOOR and the drag term are dropped, so the bar is set by the
    MEASURED noise and a hypothesis about noise can be tested at all. The
    false-flag match is the guard: dropping terms can only raise the rate,
    and the sweep must then pick a larger k."""
    res = series_residual(epoch_ms, y)
    if usable is not None:
        res = np.where(usable, res, 0.0)
    idx = confirmed_indices(res, k * sigma)
    return np.asarray(epoch_ms, dtype=np.int64)[idx], res


# ==========================================================================
# Floors, correlation, bootstrap
# ==========================================================================
def floor_metres(a_km, n_rev_day, thr_rev_day):
    """T16b's derivation, reused: a = (mu/(2 pi n/86400)^2)^(1/3) gives
    da/a = -(2/3) dn/n so |da|min = (2/3)(a/n) thr_n; and da = 2 dv/n_ang for
    a near-circular orbit gives dv = da n_ang / 2."""
    da_km = (2.0 / 3.0) * (a_km / n_rev_day) * thr_rev_day
    n_ang = 2.0 * math.pi * n_rev_day / 86400.0
    return da_km * 1000.0, da_km * 1000.0 * n_ang / 2.0


def block_bootstrap(values_by_block, statistic, rng, n=BOOTSTRAP_N):
    """Resample whole time blocks with replacement (registration 3.6/3.7)."""
    blocks = [b for b in values_by_block if len(b[0]) > 0]
    if len(blocks) < 3:
        return None
    out = []
    for _ in range(n):
        pick = rng.integers(0, len(blocks), len(blocks))
        parts = [blocks[i] for i in pick]
        v = statistic(parts)
        if v is not None and np.isfinite(v):
            out.append(v)
    if len(out) < 50:
        return None
    lo, hi = np.percentile(out, [2.5, 97.5])
    return [float(lo), float(hi)]


def blocks_of(epoch_ms, arrays, block_days):
    """Partition aligned arrays into contiguous blocks of `block_days`."""
    t = np.asarray(epoch_ms, dtype=np.float64)
    if t.size == 0:
        return []
    key = np.floor((t - t[0]) / (block_days * DAY_MS)).astype(np.int64)
    out = []
    for b in np.unique(key):
        m = key == b
        out.append(tuple(np.asarray(a)[m] for a in arrays))
    return out


def mad_scale(x):
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size < 3:
        return float("nan")
    return float(np.median(np.abs(x - np.median(x))) * 1.4826)


def wilson(k, n):
    return list(pp.wilson(k, n)) if n else None


def in_any_window(times, windows):
    t = np.asarray(times, dtype=np.float64)
    m = np.zeros(t.size, dtype=bool)
    for lo, hi in windows:
        m |= (t >= lo) & (t <= hi)
    return m


def intersect_windows(wa, wb):
    out = []
    for lo1, hi1 in wa:
        for lo2, hi2 in wb:
            lo, hi = max(lo1, lo2), min(hi1, hi2)
            if hi > lo:
                out.append((lo, hi))
    return sorted(out)


def window_days(windows):
    return sum((hi - lo) for lo, hi in windows) / DAY_MS


def bin_of(value):
    if value is None or not np.isfinite(value):
        return "unknown"
    for lo, hi in DA_BINS:
        if lo <= value < hi:
            return f"{lo:g}-{hi:g} m" if math.isfinite(hi) else f">={lo:g} m"
    return "unknown"


def signed_bracketed_da_metres(el, t0, t1):
    ep = el["epoch_ms"]
    before = np.nonzero(ep <= t0)[0]
    after = np.nonzero(ep >= t1)[0]
    if before.size == 0 or after.size == 0:
        return None
    a0 = float(pp.semi_major_axis_km(el["n"][before[-1]]))
    a1 = float(pp.semi_major_axis_km(el["n"][after[0]]))
    return (a1 - a0) * 1000.0


def detector_state():
    diff = subprocess.run(["git", "diff", "--stat", "--"] + list(DETECTOR_FILES),
                          cwd=str(REPO), capture_output=True).stdout.decode().strip()
    hashes = {p: subprocess.run(["git", "hash-object", p], cwd=str(REPO),
                                capture_output=True).stdout.decode().strip()
              for p in DETECTOR_FILES}
    return {"clean": diff == "", "diffstat": diff, "blobHashes": hashes}


# ==========================================================================
# LEO arm
# ==========================================================================
def coincident_pairs(a, b, tol_days=COINCIDENT_TOL_DAYS):
    """Indices (ia, ib) of element sets of the two objects whose epochs differ
    by less than `tol_days`. Nothing is interpolated, so any statistic taken
    over these pairs is free of interpolation artefacts."""
    ta = a["epoch_ms"].astype(np.float64)
    tb = b["epoch_ms"].astype(np.float64)
    j = np.clip(np.searchsorted(tb, ta), 0, tb.size - 1)
    jm = np.clip(j - 1, 0, tb.size - 1)
    pick = np.where(np.abs(tb[j] - ta) <= np.abs(tb[jm] - ta), j, jm)
    dt = np.abs(tb[pick] - ta) / DAY_MS
    m = dt <= tol_days
    return np.nonzero(m)[0], pick[m], dt[m]


def pair_geometry(a, b):
    """Registration 3.1: the pair's geometry is MEASURED, not assumed. The
    brief's '~140 s apart' is an input to be checked.

    The along-track phase is taken over NEAR-COINCIDENT element sets and the
    residual time offset is closed by propagating the mean anomaly at the
    object's own mean motion, which is exact for a mean-element set by the
    definition of n; the argument of perigee is carried unpropagated, and at a
    sun-synchronous nodal rate of order 3 deg/day the error that leaves over a
    0.05 day offset is below 0.2 deg. Interpolating the mean anomaly across an
    ordinary element-set spacing would be meaningless -- half a day is about
    seven revolutions -- and is not done.
    """
    ia, ib, dtd = coincident_pairs(a, b)
    a_a = pp.semi_major_axis_km(a["n"][ia])
    a_b = pp.semi_major_axis_km(b["n"][ib])
    period_s = 86400.0 / float(np.median(a["n"]))
    u_a = a["argp"][ia] + a["ma"][ia]
    u_b = (b["argp"][ib] + b["ma"][ib]
           + 360.0 * b["n"][ib] * ((a["epoch_ms"][ia].astype(np.float64)
                                    - b["epoch_ms"][ib].astype(np.float64)) / DAY_MS))
    du = pp.wrap180(u_a - u_b)
    du_med = float(np.median(du))
    return {
        "coincidentElementSetPairs": int(ia.size),
        "coincidenceToleranceDays": COINCIDENT_TOL_DAYS,
        "medianEpochOffsetDays": float(np.median(dtd)) if dtd.size else None,
        "medianSemiMajorAxisKmA": float(np.median(a_a)),
        "medianSemiMajorAxisKmB": float(np.median(a_b)),
        "medianDeltaSemiMajorAxisMetres": float(np.median(a_a - a_b) * 1000.0),
        "medianInclinationDegA": float(np.median(a["inc"])),
        "medianDeltaInclinationDeg": float(np.median(a["inc"][ia] - b["inc"][ib])),
        "medianDeltaRaanDeg": float(np.median(pp.wrap180(a["raan"][ia] - b["raan"][ib]))),
        "orbitalPeriodSeconds": float(period_s),
        "medianAlongTrackPhaseDeg": du_med,
        "alongTrackPhaseQuartilesDeg": [float(v) for v in np.percentile(du, [25, 50, 75])],
        "medianAlongTrackSeparationSeconds": du_med / 360.0 * period_s,
        "medianAlongTrackSeparationSecondsAbsolute": abs(du_med) / 360.0 * period_s,
        "elementSetSpacingDays": {
            "sentinel-3a": float(np.median(np.diff(a["epoch_ms"])) / DAY_MS),
            "sentinel-3b": float(np.median(np.diff(b["epoch_ms"])) / DAY_MS)},
        "elementSets": {"sentinel-3a": int(a["epoch_ms"].size),
                        "sentinel-3b": int(b["epoch_ms"].size)},
        "note": ("the conductor's brief states ~140 s; this row is the measured "
                 "value and no claim depends on the brief's figure"),
    }


def leo_quiet_mask(epoch_ms, quiet_windows):
    return in_any_window(np.asarray(epoch_ms, dtype=np.float64), quiet_windows)


def _host_floor(host, partner, quiet_windows):
    """One host's single-object noise scale, its differential noise scale, and
    the ratio between them -- all three from the SAME samples, so that the
    point estimate and its bootstrap are the same statistic."""
    res_h = series_residual(host["epoch_ms"], host[channel_n(host)])
    _, d, ok = build_differential(host, partner, "n")
    res_d = series_residual(host["epoch_ms"], np.where(ok, d, np.nan))
    q = leo_quiet_mask(host["epoch_ms"], quiet_windows) & ok
    s_h, s_d = mad_scale(res_h[q]), mad_scale(res_d[q])
    ratio = s_d / s_h if (np.isfinite(s_h) and s_h > 0) else float("nan")
    bl = blocks_of(host["epoch_ms"][q], (res_h[q], res_d[q]), BLOCK_DAYS_FLOOR)

    def stat(parts):
        xh = np.concatenate([p[0] for p in parts])
        xd = np.concatenate([p[1] for p in parts])
        sh, sd = mad_scale(xh), mad_scale(xd)
        return sd / sh if (np.isfinite(sh) and sh > 0) else None

    ci = block_bootstrap(bl, stat, np.random.default_rng(SEED))
    lag1 = (float(np.corrcoef(res_d[q][:-1], res_d[q][1:])[0, 1])
            if q.sum() > 10 else None)
    a_km = float(pp.semi_major_axis_km(np.median(host["n"])))
    n_med = float(np.median(host["n"]))
    return {
        "quietSamples": int(q.sum()),
        "sigmaSingleRevPerDay": s_h, "sigmaDifferentialRevPerDay": s_d,
        "ratioMeasured": ratio, "ratio95": ci,
        "floorSingleMetresOfSemiMajorAxis": floor_metres(a_km, n_med, 5.0 * s_h)[0],
        "floorDifferentialMetresOfSemiMajorAxis": floor_metres(a_km, n_med, 5.0 * s_d)[0],
        "floorSingleMillimetresPerSecond": floor_metres(a_km, n_med, 5.0 * s_h)[1] * 1000.0,
        "floorDifferentialMillimetresPerSecond": floor_metres(a_km, n_med, 5.0 * s_d)[1] * 1000.0,
        "lag1AutocorrelationOfDifferentialResidual": lag1,
        "differentialSamplesRefusedForGap": int((~ok).sum()),
    }


def channel_n(_):
    return "n"


def coincident_rho(a, b, quiet_windows):
    """rho measured over near-coincident element sets, with NOTHING
    interpolated. This is the primary correlation number: measuring it through
    an interpolation of the sparser object onto the denser one's epochs biases
    it towards zero, because interpolation smooths away exactly the
    high-frequency part whose correlation is in question."""
    ia, ib, dtd = coincident_pairs(a, b)
    ra = series_residual(a["epoch_ms"], a["n"])[ia]
    rb = series_residual(b["epoch_ms"], b["n"])[ib]
    qa = leo_quiet_mask(a["epoch_ms"][ia], quiet_windows)
    m = qa & np.isfinite(ra) & np.isfinite(rb)
    if m.sum() < 20:
        return {"pairs": int(m.sum()), "rho": None,
                "note": "too few coincident quiet pairs"}
    rho = float(np.corrcoef(ra[m], rb[m])[0, 1])
    bl = blocks_of(a["epoch_ms"][ia][m], (ra[m], rb[m]), BLOCK_DAYS_FLOOR)

    def stat(parts):
        xa = np.concatenate([p[0] for p in parts])
        xb = np.concatenate([p[1] for p in parts])
        return float(np.corrcoef(xa, xb)[0, 1]) if xa.size > 8 else None

    ci = block_bootstrap(bl, stat, np.random.default_rng(SEED))
    s_a, s_b = mad_scale(ra[m]), mad_scale(rb[m])
    # the generalised, unequal-variance form of the section 2.2 derivation:
    # with r_X = c + eps_X and Var(eps_A) != Var(eps_B),
    #   Var(r_A - r_B) = sA^2 + sB^2   and   rho = sc^2 / sqrt(vA vB)
    # so, referenced to object A's own noise,
    #   R = sqrt((sA^2 + sB^2) / vA)  with  sX^2 = vX - sc^2.
    va, vb = s_a ** 2, s_b ** 2
    sc2 = max(0.0, rho * math.sqrt(va * vb))
    r_gen = math.sqrt(max(0.0, (va - sc2) + (vb - sc2)) / va) if va > 0 else float("nan")
    return {
        "pairs": int(m.sum()), "medianEpochOffsetDays": float(np.median(dtd[m])),
        "rho": rho, "rho95": ci,
        "sigmaA": s_a, "sigmaB": s_b, "sigmaRatioBOverA": (s_b / s_a) if s_a else None,
        "ratioDerivedEqualVariance": math.sqrt(max(0.0, 2.0 * (1.0 - rho))),
        "ratioDerivedUnequalVariance": r_gen,
        "note": ("the equal-variance form of registration 2.2 assumes the two "
                 "members carry the same noise; where they do not, the "
                 "generalised form referenced to object A is the one to read"),
    }


PASSBAND_WINDOW_DAYS = 5.0


def passband_matched_rho(a, b, quiet_windows, window_days_=PASSBAND_WINDOW_DAYS):
    """POST-REGISTRATION CONTROL, labelled as such, and the one that decides
    whether a near-zero correlation is a fact about the objects or an artefact
    of the instrument.

    The shipped residual filter has a window of ten SAMPLES. Two objects with
    different element-set cadences therefore get different time windows -- so
    a genuinely common error could still show a low correlation simply because
    the two residuals are taken through different passbands. Here each
    object's window is set in DAYS instead, to the same number of days for
    both, and the correlation is taken over near-coincident element sets with
    nothing interpolated."""
    out = {"windowDays": window_days_}
    ia, ib, _ = coincident_pairs(a, b)
    res = {}
    for name, el, idx in (("a", a, ia), ("b", b, ib)):
        spacing = float(np.median(np.diff(el["epoch_ms"])) / DAY_MS)
        w = max(4, int(round(window_days_ / max(spacing, 1e-6))))
        out[f"windowSamples_{name}"] = w
        r = pp.rolling_theil_sen_residual(
            el["epoch_ms"].astype(np.float64) / DAY_MS, el["n"], window=w)
        res[name] = r[idx]
    q = leo_quiet_mask(a["epoch_ms"][ia], quiet_windows)
    m = q & np.isfinite(res["a"]) & np.isfinite(res["b"])
    out["pairs"] = int(m.sum())
    if m.sum() < 20:
        out["rho"] = None
        return out
    rho = float(np.corrcoef(res["a"][m], res["b"][m])[0, 1])
    bl = blocks_of(a["epoch_ms"][ia][m], (res["a"][m], res["b"][m]), BLOCK_DAYS_FLOOR)

    def stat(parts):
        xa = np.concatenate([p[0] for p in parts])
        xb = np.concatenate([p[1] for p in parts])
        return float(np.corrcoef(xa, xb)[0, 1]) if xa.size > 8 else None

    out["rho"] = rho
    out["rho95"] = block_bootstrap(bl, stat, np.random.default_rng(SEED))
    out["sigmaA"] = mad_scale(res["a"][m])
    out["sigmaB"] = mad_scale(res["b"][m])
    out["ratioDerivedEqualVariance"] = math.sqrt(max(0.0, 2.0 * (1.0 - rho)))
    return out


def measure_floor(ea, eb, quiet_windows, say):
    """Registration 3.6. Printed before any recall cell (gate G3)."""
    res_a = series_residual(ea["epoch_ms"], ea["n"])
    res_b_on_a = interpolate_refusing_gaps(
        eb["epoch_ms"], series_residual(eb["epoch_ms"], eb["n"]), ea["epoch_ms"])
    _, d_a, ok_a = build_differential(ea, eb, "n")
    _, d_b, ok_b = build_differential(eb, ea, "n")
    res_da = series_residual(ea["epoch_ms"], np.where(ok_a, d_a, np.nan))
    res_db = series_residual(eb["epoch_ms"], np.where(ok_b, d_b, np.nan))
    res_b_own = series_residual(eb["epoch_ms"], eb["n"])

    qa = leo_quiet_mask(ea["epoch_ms"], quiet_windows) & ok_a
    qb = leo_quiet_mask(eb["epoch_ms"], quiet_windows) & ok_b
    both = qa & np.isfinite(res_b_on_a)

    s_a = mad_scale(res_a[qa]); s_b = mad_scale(res_b_own[qb])
    s_single = 0.5 * (s_a + s_b)
    s_da = mad_scale(res_da[qa]); s_db = mad_scale(res_db[qb])
    s_diff = 0.5 * (s_da + s_db)

    x = res_a[both]; y = res_b_on_a[both]
    rho = float(np.corrcoef(x, y)[0, 1]) if x.size > 8 else float("nan")
    ratio = s_diff / s_single if np.isfinite(s_single) and s_single > 0 else float("nan")
    derived = math.sqrt(max(0.0, 2.0 * (1.0 - rho))) if np.isfinite(rho) else float("nan")

    # POST-REGISTRATION REFINEMENT, labelled: registration 2.1's model is
    # written about RESIDUALS, so the quantity sqrt(2(1-rho)) predicts is the
    # DIFFERENCE OF THE RESIDUALS. The rolling Theil-Sen residual is a
    # median-based, non-linear filter, so the residual OF the differential is
    # a different series -- quieter still, and the one the detector actually
    # consumes. Both are reported: the model ratio carries the derivation
    # check of P1, the operational ratio carries the floor.
    res_model = res_a - res_b_on_a
    s_model = mad_scale(res_model[both])
    s_single_here = mad_scale(res_a[both])
    ratio_model = s_model / s_single_here if s_single_here > 0 else float("nan")

    rng = np.random.default_rng(SEED)
    bl = blocks_of(ea["epoch_ms"][both], (res_a[both], res_b_on_a[both],
                                          res_da[both], res_model[both]),
                   BLOCK_DAYS_FLOOR)

    def stat_rho(parts):
        xa = np.concatenate([p[0] for p in parts])
        xb = np.concatenate([p[1] for p in parts])
        if xa.size < 8:
            return None
        return float(np.corrcoef(xa, xb)[0, 1])

    def stat_ratio(parts):
        xa = np.concatenate([p[0] for p in parts])
        xd = np.concatenate([p[2] for p in parts])
        sa, sd = mad_scale(xa), mad_scale(xd)
        return sd / sa if sa > 0 else None

    def stat_ratio_model(parts):
        xa = np.concatenate([p[0] for p in parts])
        xm = np.concatenate([p[3] for p in parts])
        sa, sm = mad_scale(xa), mad_scale(xm)
        return sm / sa if sa > 0 else None

    rho_ci = block_bootstrap(bl, stat_rho, rng)
    ratio_ci = block_bootstrap(bl, stat_ratio, np.random.default_rng(SEED))
    ratio_model_ci = block_bootstrap(bl, stat_ratio_model, np.random.default_rng(SEED))

    a_km = float(pp.semi_major_axis_km(np.median(ea["n"])))
    n_med = float(np.median(ea["n"]))
    f_single_m, f_single_v = floor_metres(a_km, n_med, 5.0 * s_single)
    f_diff_m, f_diff_v = floor_metres(a_km, n_med, 5.0 * s_diff)

    lag1 = float(np.corrcoef(res_da[qa][:-1], res_da[qa][1:])[0, 1]) if qa.sum() > 10 else None

    out = {
        "perHost": {"sentinel-3a": _host_floor(ea, eb, quiet_windows),
                    "sentinel-3b": _host_floor(eb, ea, quiet_windows)},
        "coincidentRho": coincident_rho(ea, eb, quiet_windows),
        "passbandMatchedRho": passband_matched_rho(ea, eb, quiet_windows),
        "quietSamples": {"sentinel-3a": int(qa.sum()), "sentinel-3b": int(qb.sum()),
                         "bothUsable": int(both.sum())},
        "sigmaSingleRevPerDay": {"sentinel-3a": s_a, "sentinel-3b": s_b,
                                 "pooled": s_single},
        "sigmaDifferentialRevPerDay": {"hostA": s_da, "hostB": s_db, "pooled": s_diff},
        "rho": rho, "rho95": rho_ci,
        "ratioMeasured": ratio, "ratio95": ratio_ci,
        "ratioDerivedFromRho": derived,
        "ratioMeasuredOverDerived": (ratio / derived) if derived else None,
        "ratioModelDifferenceOfResiduals": ratio_model,
        "ratioModel95": ratio_model_ci,
        "ratioModelOverDerived": (ratio_model / derived) if derived else None,
        "ratioNote": ("ratioModel* is the difference of the two residuals, the "
                      "quantity the section 2.2 model predicts, and carries the "
                      "P1 derivation check; ratioMeasured is the residual of the "
                      "differential, the series the detector consumes, and "
                      "carries the floor. POST-REGISTRATION REFINEMENT."),
        "lag1AutocorrelationOfDifferentialResidual": lag1,
        "floorAtFiveSigma": {
            "singleMetresOfSemiMajorAxis": f_single_m,
            "singleMillimetresPerSecond": f_single_v * 1000.0,
            "differentialMetresOfSemiMajorAxis": f_diff_m,
            "differentialMillimetresPerSecond": f_diff_v * 1000.0,
            "note": ("five sigma on the MEASURED noise with the 50 m constant and "
                     "the drag term dropped; the shipped arm keeps all three and is "
                     "reported separately"),
        },
        "shippedFloorIsAConstantHere": {
            "pooledSigmaN": 6.2747e-5,
            "objectSigmaN": {"sentinel-3a": s_a, "sentinel-3b": s_b},
            "note": ("T16b measured these objects' own noise far below the pooled "
                     "population sigma that sets the shipped threshold; on this pair "
                     "the shipped 102-126 m floor is a population constant, not a "
                     "noise floor"),
        },
    }
    cr = out["coincidentRho"]
    pm = out["passbandMatchedRho"]
    say(f"  rho (interpolation-free, {cr.get('pairs')} pairs) = {cr.get('rho')}")
    say(f"  rho (passband-matched, {pm.get('pairs')} pairs) = {pm.get('rho')}")
    say(f"  rho (through interpolation onto 3A) = {rho:.4f}")
    for h in PAIR:
        ph = out["perHost"][h]
        say(f"  host {h}: R={ph['ratioMeasured']:.4f} {ph['ratio95']}  "
            f"floor {ph['floorSingleMetresOfSemiMajorAxis']:.2f} m -> "
            f"{ph['floorDifferentialMetresOfSemiMajorAxis']:.2f} m")
    return out, {"res_a": res_a, "res_b": res_b_own, "d_a": d_a, "d_b": d_b,
                 "ok_a": ok_a, "ok_b": ok_b, "qa": qa, "qb": qb}


def sweep_to_rate(epoch_ms, y, sigma, quiet_windows, quiet_days, usable,
                  rates=(BASELINE_FLAG_RATE,)):
    """Registration 3.5: the smallest threshold whose false-flag rate on the
    quiet intervals does not exceed a given per-window-day rate. Swept against
    every rate in one pass so that the two operating points read off the
    same curve."""
    rows = []
    chosen = {t: None for t in rates}
    for k in K_GRID:
        flags, _ = swept_flags(epoch_ms, y, sigma, float(k), usable)
        inq = int(in_any_window(flags, quiet_windows).sum())
        rate = inq / quiet_days if quiet_days > 0 else float("inf")
        row = {"k": float(k), "flags": int(flags.size),
               "flagsInQuiet": inq, "ratePerQuietWindowDay": rate,
               "beyondRegisteredGrid": bool(k > K_GRID_REGISTERED_MAX)}
        rows.append(row)
        for t in rates:
            if chosen[t] is None and rate <= t:
                chosen[t] = row
        if all(chosen[t] is not None for t in rates):
            break
    return chosen, rows


def recall_cells(flag_times, labels, el_by_sat, floor_m, usable_times=None):
    """`usable_times` maps a spacecraft to the epochs at which the arm could
    produce a flag at all. A label window containing none of them is NOT
    EVALUABLE (gate G4) rather than a miss."""
    cells = {"overall": {"k": 0, "n": 0}, "bySpacecraft": {}, "byDaBin": {},
             "byFloor": {}, "notEvaluable": 0, "hits": []}
    for lab in labels:
        lo, hi = lab["windowStartMs"], lab["windowEndMs"]
        if usable_times is not None:
            ut = usable_times.get(lab["sat"])
            if ut is None or not np.any((ut >= lo) & (ut <= hi)):
                cells["notEvaluable"] += 1
                continue
        hit = bool(np.any((flag_times >= lo) & (flag_times <= hi)))
        cells["overall"]["n"] += 1
        cells["overall"]["k"] += int(hit)
        c = cells["bySpacecraft"].setdefault(lab["sat"], {"k": 0, "n": 0})
        c["n"] += 1; c["k"] += int(hit)
        da = signed_bracketed_da_metres(el_by_sat[lab["sat"]], lo, hi)
        c = cells["byDaBin"].setdefault(bin_of(abs(da) if da is not None else None),
                                        {"k": 0, "n": 0})
        c["n"] += 1; c["k"] += int(hit)
        side = ("unknown" if da is None
                else "aboveFloor" if abs(da) >= floor_m else "belowFloor")
        c = cells["byFloor"].setdefault(side, {"k": 0, "n": 0})
        c["n"] += 1; c["k"] += int(hit)
        cells["hits"].append((lab["id"], lab["sat"], lab["eventMs"], int(hit)))
    return cells


def wrap_cells(cells):
    def w(c):
        o = dict(c)
        o["recall"] = c["k"] / c["n"] if c["n"] else None
        o["wilson95"] = wilson(c["k"], c["n"])
        return o
    out = {"overall": w(cells["overall"]), "notEvaluable": cells["notEvaluable"]}
    for key in ("bySpacecraft", "byDaBin", "byFloor"):
        out[key] = {k: w(v) for k, v in sorted(cells[key].items())}
    return out


def paired_increment(hits_a, hits_b, block_days, seed=SEED):
    """Paired block bootstrap of (recall_a - recall_b) over time blocks.
    Two spacecraft is not enough clusters for an object-clustered interval;
    the substitution and its limitation are registered in 3.7."""
    t = np.asarray([h[2] for h in hits_a], dtype=np.float64)
    ka = np.asarray([h[3] for h in hits_a], dtype=np.float64)
    kb = np.asarray([h[3] for h in hits_b], dtype=np.float64)
    order = np.argsort(t)
    t, ka, kb = t[order], ka[order], kb[order]
    bl = blocks_of(t, (ka, kb), block_days)
    point = float(ka.mean() - kb.mean()) if ka.size else float("nan")

    def stat(parts):
        a = np.concatenate([p[0] for p in parts])
        b = np.concatenate([p[1] for p in parts])
        return float(a.mean() - b.mean()) if a.size else None

    ci = block_bootstrap(bl, stat, np.random.default_rng(seed))
    lab = blocks_of(t, (ka, kb), 0.0001)  # one label per block = label bootstrap
    ci_lab = block_bootstrap(lab, stat, np.random.default_rng(seed))
    return {"incrementPoints": point * 100.0,
            "blockBootstrap95Points": [c * 100.0 for c in ci] if ci else None,
            "labelBootstrap95Points": [c * 100.0 for c in ci_lab] if ci_lab else None,
            "blocks": len(bl),
            "minimumDetectableIncrementPoints": (
                (ci[1] - ci[0]) / 2.0 * 100.0 if ci else None)}


def control_pair(ea, other, quiet_windows, label, say):
    """Registration 3.8. Returns rho and R for a non-co-orbital or shuffled
    partner, by the identical procedure."""
    res_a = series_residual(ea["epoch_ms"], ea["n"])
    res_o = interpolate_refusing_gaps(
        other["epoch_ms"], series_residual(other["epoch_ms"], other["n"]),
        ea["epoch_ms"])
    _, d, ok = build_differential(ea, other, "n")
    res_d = series_residual(ea["epoch_ms"], np.where(ok, d, np.nan))
    q = leo_quiet_mask(ea["epoch_ms"], quiet_windows) & ok & np.isfinite(res_o)
    if q.sum() < 20:
        return {"label": label, "usableQuietSamples": int(q.sum()),
                "note": "too few overlapping quiet samples to measure"}
    rho = float(np.corrcoef(res_a[q], res_o[q])[0, 1])
    s_single = mad_scale(res_a[q]); s_diff = mad_scale(res_d[q])
    ratio = s_diff / s_single if s_single > 0 else float("nan")
    bl = blocks_of(ea["epoch_ms"][q], (res_a[q], res_o[q], res_d[q]), BLOCK_DAYS_FLOOR)

    def stat_ratio(parts):
        xa = np.concatenate([p[0] for p in parts]); xd = np.concatenate([p[2] for p in parts])
        sa, sd = mad_scale(xa), mad_scale(xd)
        return sd / sa if sa > 0 else None

    def stat_rho(parts):
        xa = np.concatenate([p[0] for p in parts]); xo = np.concatenate([p[1] for p in parts])
        return float(np.corrcoef(xa, xo)[0, 1]) if xa.size > 8 else None

    ci = block_bootstrap(bl, stat_ratio, np.random.default_rng(SEED))
    rho_ci = block_bootstrap(bl, stat_rho, np.random.default_rng(SEED))
    coin = coincident_rho(ea, other, quiet_windows)
    passband = passband_matched_rho(ea, other, quiet_windows)
    say(f"  control {label}: rho={rho:.4f} (interp-free "
        f"{coin.get('rho')}, {coin.get('pairs')} pairs) R={ratio:.4f}")
    return {"label": label, "usableQuietSamples": int(q.sum()), "rho": rho,
            "coincidentRho": coin, "passbandMatchedRho": passband,
            "rho95": rho_ci, "ratioMeasured": ratio, "ratio95": ci,
            "ratioDerivedFromRho": math.sqrt(max(0.0, 2.0 * (1.0 - rho))),
            "sigmaSingle": s_single, "sigmaDifferential": s_diff}


def shifted_copy(el, days):
    out = dict(el)
    out["epoch_ms"] = el["epoch_ms"] + int(days * DAY_MS)
    return out


def permuted_copy(el, seed=SEED):
    rng = np.random.default_rng(seed)
    out = dict(el)
    perm = rng.permutation(el["n"].size)
    out["n"] = el["n"][perm]
    return out


def attribution(flag_times, flag_signs, labels, el_by_sat, say):
    """Registration 3.9: the sign rule, and the direction screen it rests on,
    measured rather than assumed."""
    screen = {}
    for sat, el in el_by_sat.items():
        das = [signed_bracketed_da_metres(el, l["windowStartMs"], l["windowEndMs"])
               for l in labels if l["sat"] == sat]
        das = np.asarray([d for d in das if d is not None])
        screen[sat] = {"n": int(das.size),
                       "fractionRaisingSemiMajorAxis": float((das > 0).mean()) if das.size else None,
                       "medianSignedDeltaAMetres": float(np.median(das)) if das.size else None}
    usable = all(s["fractionRaisingSemiMajorAxis"] is not None
                 and s["fractionRaisingSemiMajorAxis"] >= DIRECTION_SCREEN_BAR
                 for s in screen.values())
    k = n = 0
    for i, t in enumerate(flag_times):
        owners = {l["sat"] for l in labels
                  if l["windowStartMs"] <= t <= l["windowEndMs"]}
        if len(owners) != 1:
            continue
        owner = owners.pop()
        named = "sentinel-3a" if flag_signs[i] < 0 else "sentinel-3b"
        n += 1
        k += int(named == owner)
    out = {"directionScreen": screen, "screenBar": DIRECTION_SCREEN_BAR,
           "ruleUsable": bool(usable),
           "unambiguousFlags": n, "namedCorrectly": k,
           "accuracy": (k / n) if n else None, "wilson95": wilson(k, n),
           "chanceLevel": 0.5}
    if not usable:
        out["note"] = ("the direction screen is below the registered bar, so the "
                       "attribution rule is reported unusable; the measured "
                       "accuracy is printed anyway and carries no claim")
    say(f"  attribution: {k}/{n} on the unambiguous subset, rule usable={usable}")
    return out


def run_leo(say):
    labels_all, stable_all = load_labels()
    labels = [l for l in labels_all if l["sat"] in PAIR]
    el = {s: load_elements(SAT_NORAD[s]) for s in SAT_NORAD}
    ea, eb = el[PAIR[0]], el[PAIR[1]]
    say(f"  3A {ea['epoch_ms'].size} sets, 3B {eb['epoch_ms'].size} sets, "
        f"{len(labels)} labels")

    wa = [(w["startMs"], w["endMs"]) for w in stable_all if w["sat"] == PAIR[0]]
    wb = [(w["startMs"], w["endMs"]) for w in stable_all if w["sat"] == PAIR[1]]
    intersection = intersect_windows(wa, wb)
    intersection_days = window_days(intersection)
    shared = intersection
    shared_days = intersection_days
    fallback = None
    if shared_days < MIN_QUIET_WINDOW_DAYS:
        fallback = "union"
        shared = sorted(wa + wb)
        shared_days = window_days(shared)
    say(f"  shared quiet windows {len(shared)}, {shared_days:.1f} window-days"
        + (f" (FALLBACK {fallback})" if fallback else ""))

    geometry = pair_geometry(ea, eb)
    hoo = {}
    for s in PAIR:
        err = hold_one_out_error(el[s]["epoch_ms"], el[s]["n"])
        fin = err[np.isfinite(err)]
        a_km = float(pp.semi_major_axis_km(np.median(el[s]["n"])))
        n_med = float(np.median(el[s]["n"]))
        med = float(np.median(np.abs(fin))) if fin.size else float("nan")
        sig = mad_scale(fin)
        hoo[s] = {
            "interior": int(err.size), "usable": int(fin.size),
            "refusedForGap": int(err.size - fin.size),
            "medianAbsErrorRevPerDay": med, "madSigmaRevPerDay": sig,
            "medianAbsErrorMetresOfSemiMajorAxis": floor_metres(a_km, n_med, med)[0],
            "madSigmaMetresOfSemiMajorAxis": floor_metres(a_km, n_med, sig)[0],
        }
        say(f"  hold-one-out {s}: median |error| "
            f"{hoo[s]['medianAbsErrorMetresOfSemiMajorAxis']:.2f} m of a, "
            f"{hoo[s]['refusedForGap']} refused for gap")

    floors, series = measure_floor(ea, eb, shared, say)
    gates = {}
    gates["G6_sample"] = {
        "fired": floors["quietSamples"]["bothUsable"] < MIN_QUIET_SAMPLES,
        "bar": MIN_QUIET_SAMPLES, "value": floors["quietSamples"]["bothUsable"]}
    gates["G7_operatingPoint"] = {"fired": shared_days < MIN_QUIET_WINDOW_DAYS,
                                  "bar": MIN_QUIET_WINDOW_DAYS,
                                  "value": shared_days, "fallbackUsed": fallback}

    # ---- arms -------------------------------------------------------------
    _, d_a, ok_a = build_differential(ea, eb, "n")
    _, d_b, ok_b = build_differential(eb, ea, "n")
    sig_da = series_sigma(np.where(ok_a, d_a, np.nan))
    sig_db = series_sigma(np.where(ok_b, d_b, np.nan))
    usable_times = {PAIR[0]: ea["epoch_ms"][ok_a], PAIR[1]: eb["epoch_ms"][ok_b]}

    # GATE G4's consequence, applied: a label whose window holds no usable
    # differential sample is NOT EVALUABLE, and the registration requires
    # EVERY comparator -- including the shipped arms -- to be recomputed on
    # that same subset. Both the full and the restricted sets are reported.
    def evaluable(lab):
        ut = usable_times[lab["sat"]]
        return bool(np.any((ut >= lab["windowStartMs"]) & (ut <= lab["windowEndMs"])))

    labels_eval = [l for l in labels if evaluable(l)]
    not_evaluable = len(labels) - len(labels_eval)
    say(f"  evaluable labels {len(labels_eval)} of {len(labels)} "
        f"({not_evaluable} without a usable differential sample)")

    a_km = float(pp.semi_major_axis_km(np.median(ea["n"])))
    n_med = float(np.median(ea["n"])) 

    def combined_flags(specs, k):
        """One multiplier applied to every series of the arm, and the flags
        pooled -- so the arm has ONE operating point. Sweeping each series to
        the full rate budget separately and then pooling would double the
        arm's false-flag rate, which is what a first pass did."""
        ts, ss = [], []
        for ep, y, sig, us in specs:
            f, r = swept_flags(ep, y, sig, k, us)
            ts.append(f)
            ss.append(r[np.searchsorted(ep, f)] if f.size else np.asarray([]))
        t = np.concatenate(ts) if ts else np.asarray([], np.int64)
        s = np.concatenate(ss) if ss else np.asarray([])
        o = np.argsort(t)
        return t[o], s[o]

    def sweep_combined(specs, rates):
        rows, chosen = [], {r: None for r in rates}
        for k in K_GRID:
            t, _ = combined_flags(specs, float(k))
            inq = int(in_any_window(t, shared).sum())
            rate = inq / shared_days if shared_days > 0 else float("inf")
            rows.append({"k": float(k), "flags": int(t.size), "flagsInQuiet": inq,
                         "ratePerQuietWindowDay": rate,
                         "beyondRegisteredGrid": bool(k > K_GRID_REGISTERED_MAX)})
            for r in rates:
                if chosen[r] is None and rate <= r:
                    chosen[r] = rows[-1]
            if all(chosen[r] is not None for r in rates):
                break
        return chosen, rows

    arms = {}
    # S1 shipped, S2 per-object: the untouched detector
    for arm, sig in (("S1_shipped", (6.2747e-5, 0.6994)), ("S2_perObject", None)):
        times = []
        for s in PAIR:
            e = el[s]
            if sig is None:
                st, sn = pp.object_sigma_contributions(e)
            else:
                sn, st = sig
            det = pp.detect_manoeuvres(e, float(sn), float(st))
            idx = np.union1d(det["intrack"], det["plane"])
            times.append(e["epoch_ms"][idx] if idx.size else np.asarray([], np.int64))
        ft = np.sort(np.concatenate(times))
        inq = int(in_any_window(ft, shared).sum())
        cells = recall_cells(ft, labels_eval, el, PUBLISHED["shippedFloorMetres"][0])
        full = recall_cells(ft, labels, el, PUBLISHED["shippedFloorMetres"][0])
        arms[arm] = {"threshold": "shipped, untouched", "flags": int(ft.size),
                     "flagsInSharedQuiet": inq,
                     "ratePerQuietWindowDay": inq / shared_days,
                     "recall": wrap_cells(cells), "_hits": cells["hits"],
                     "recallOnAll292": wrap_cells(full)}

    # The second operating point, added post-registration and labelled: the
    # shipped detector's own false-flag rate ON THESE WINDOWS. The registered
    # 0.012642669 was measured over eleven spacecraft's quiet windows; the
    # like-for-like rate on this window set is what the shipped arm itself
    # achieves here, and both are swept.
    s1_rate = arms["S1_shipped"]["ratePerQuietWindowDay"]
    op_rates = (BASELINE_FLAG_RATE, s1_rate)
    tnames = {BASELINE_FLAG_RATE: "registeredPooledRate", s1_rate: "shippedOwnRateHere"}

    single_specs = [(el[s]["epoch_ms"], el[s]["n"], series_sigma(el[s]["n"]), None)
                    for s in PAIR]
    diff_specs = [(ea["epoch_ms"], np.where(ok_a, d_a, np.nan), sig_da, ok_a),
                  (eb["epoch_ms"], np.where(ok_b, d_b, np.nan), sig_db, ok_b)]
    s3_chosen, s3_rows = sweep_combined(single_specs, op_rates)
    d3_chosen, d3_rows = sweep_combined(diff_specs, op_rates)

    ft_primary = np.asarray([], np.int64)
    sg_primary = np.asarray([])
    for rate_goal in op_rates:
        tag = tnames[rate_goal]
        for name, specs, chosen, sigmas in (
                ("S3_singleSwept", single_specs, s3_chosen,
                 [series_sigma(el[s]["n"]) for s in PAIR]),
                ("D3_differentialSwept", diff_specs, d3_chosen, [sig_da, sig_db])):
            ch = chosen[rate_goal]
            k = ch["k"] if ch else float(K_GRID[-1])
            ft, sg = combined_flags(specs, k)
            inq = int(in_any_window(ft, shared).sum())
            thr = 0.5 * (k * sigmas[0] + k * sigmas[1])
            cells = recall_cells(ft, labels_eval, el, floor_metres(a_km, n_med, thr)[0])
            arms[f"{name}@{tag}"] = {
                "operatingPointRate": rate_goal,
                "chosenK": k, "reachedThatRate": ch is not None,
                "beyondRegisteredGrid": (ch or {}).get("beyondRegisteredGrid"),
                "achievedRatePerQuietWindowDay": inq / shared_days,
                "floorMetresOfSemiMajorAxisAtChosenK": floor_metres(a_km, n_med, thr)[0],
                "flags": int(ft.size), "flagsInSharedQuiet": inq,
                "recall": wrap_cells(cells), "_hits": cells["hits"]}
            if name == "D3_differentialSwept" and rate_goal == BASELINE_FLAG_RATE:
                ft_primary, sg_primary = ft, sg

    arms["_sweepCurves"] = {"S3": s3_rows, "D3": d3_rows}

    # D1 differential at the shipped multiplier, unswept
    ft_d1, _ = combined_flags(diff_specs, 5.0)
    inq_d1 = int(in_any_window(ft_d1, shared).sum())
    cells_d1 = recall_cells(
        ft_d1, labels_eval, el,
        floors["perHost"][PAIR[0]]["floorDifferentialMetresOfSemiMajorAxis"])
    arms["D1_differentialK5"] = {
        "sigmaHostA": sig_da, "sigmaHostB": sig_db, "flags": int(ft_d1.size),
        "flagsInSharedQuiet": inq_d1, "ratePerQuietWindowDay": inq_d1 / shared_days,
        "recall": wrap_cells(cells_d1), "_hits": cells_d1["hits"]}

    # ---- increments -------------------------------------------------------
    increments = {}
    for rate_goal in op_rates:
        tag = tnames[rate_goal]
        increments[f"D3_minus_S3@{tag}"] = paired_increment(
            arms[f"D3_differentialSwept@{tag}"]["_hits"],
            arms[f"S3_singleSwept@{tag}"]["_hits"], BLOCK_DAYS_RECALL)
    increments["D3_minus_S1shipped"] = paired_increment(
        arms[f"D3_differentialSwept@{tnames[BASELINE_FLAG_RATE]}"]["_hits"],
        arms["S1_shipped"]["_hits"], BLOCK_DAYS_RECALL)
    d3 = arms[f"D3_differentialSwept@{tnames[BASELINE_FLAG_RATE]}"]["recall"]["overall"]

    # ---- increments -------------------------------------------------------
    increments = {}
    for tgt in op_rates:
        tag = tnames[tgt]
        increments[f"D3_minus_S3@{tag}"] = paired_increment(
            arms[f"D3_differentialSwept@{tag}"]["_hits"],
            arms[f"S3_singleSwept@{tag}"]["_hits"], BLOCK_DAYS_RECALL)
    increments["D3_minus_S1shipped"] = paired_increment(
        arms[f"D3_differentialSwept@{tnames[BASELINE_FLAG_RATE]}"]["_hits"],
        arms["S1_shipped"]["_hits"], BLOCK_DAYS_RECALL)
    d3 = arms[f"D3_differentialSwept@{tnames[BASELINE_FLAG_RATE]}"]["recall"]["overall"]
    increments["againstPopulationMatched"] = {
        "shippedSentinel3Only": {"k": 10, "n": 292, "rate": 10 / 292,
                                 "incrementPoints": (d3["recall"] - 10 / 292) * 100.0},
        "scheduleFloorSentinel3Only": {"k": 5, "n": 292, "rate": 5 / 292,
                                       "incrementPoints": (d3["recall"] - 5 / 292) * 100.0},
    }
    increments["againstPooledDoesNotCompose"] = {
        "shippedPooled": {"rate": 0.07936507936507936,
                          "differencePoints": (d3["recall"] - 0.07936507936507936) * 100.0},
        "scheduleFloorPooled": {"rate": 0.05114638447971781,
                                "differencePoints": (d3["recall"] - 0.05114638447971781) * 100.0},
        "note": ("eleven-spacecraft numbers against a two-spacecraft number: printed "
                 "as cross-population reference and NOT as an increment"),
    }

    # ---- controls ---------------------------------------------------------
    others = [s for s in SAT_NORAD if s not in PAIR]
    a_reference = float(pp.semi_major_axis_km(np.median(ea["n"])))
    nearest = min(others, key=lambda s: abs(
        float(pp.semi_major_axis_km(np.median(el[s]["n"]))) - a_reference))
    controls = {
        "C1_nearestAltitudeNonCoOrbital": control_pair(
            ea, el[nearest], shared, f"C1 {nearest}", say),
        "C2_cryosat2": control_pair(ea, el["cryosat-2"], shared, "C2 cryosat-2", say),
        "C3_shiftedPlus180d": control_pair(
            ea, shifted_copy(eb, EPOCH_SHIFT_DAYS), shared, "C3 +180 d", say),
        "C3_shiftedMinus180d": control_pair(
            ea, shifted_copy(eb, -EPOCH_SHIFT_DAYS), shared, "C3 -180 d", say),
        "C3_permuted": control_pair(ea, permuted_copy(eb), shared, "C3 permuted", say),
    }
    controls["C1_selection"] = {
        "rule": ("among the other nine labelled spacecraft, the one whose median "
                 "semi-major axis is closest to Sentinel-3A's"),
        "chosen": nearest,
        "medianSemiMajorAxisKm": {s: float(pp.semi_major_axis_km(np.median(el[s]["n"])))
                                  for s in SAT_NORAD},
        "medianInclinationDeg": {s: float(np.median(el[s]["inc"])) for s in SAT_NORAD},
    }

    attrib = {
        "atMatchedRate": attribution(ft_primary, sg_primary, labels,
                                     {s: el[s] for s in PAIR}, say),
        "atShippedMultiplierK5": attribution(*combined_flags(diff_specs, 5.0),
                                             labels, {s: el[s] for s in PAIR}, say),
        "note": ("the matched-rate arm raises too few unambiguous flags to say "
                 "anything; the k = 5 arm raises thousands and is where the sign "
                 "rule can actually be measured, at a false-flag rate far above "
                 "any operating point -- so it measures the RULE, not a detector"),
    }

    # ---- gates ------------------------------------------------------------
    ne = not_evaluable
    unusable = int((~ok_a).sum()), int((~ok_b).sum())
    gates["G4_evaluability"] = {
        "fired": ne / max(1, len(labels)) > EVALUABILITY_BAR,
        "bar": EVALUABILITY_BAR,
        "notEvaluable": ne, "labels": len(labels),
        "evaluableLabels": len(labels_eval),
        "consequenceApplied": ("every arm, including the shipped ones, is scored "
                               "on the evaluable subset; the shipped arms carry "
                               "their all-292 cells beside it"),
        "differentialSamplesRefusedForGap": {"hostA": unusable[0], "hostB": unusable[1]}}

    for a in arms.values():
        a.pop("_hits", None)

    return {
        "pairGeometry": geometry,
        "interpolationError": hoo,
        "sharedQuietWindows": {
            "count": len(shared), "windowDays": shared_days, "fallback": fallback,
            "intersectionCount": len(intersection),
            "intersectionWindowDays": intersection_days,
            "sentinel3aStableWindows": len(wa), "sentinel3bStableWindows": len(wb),
            "sentinel3aWindowDays": window_days(wa),
            "sentinel3bWindowDays": window_days(wb),
            "note": ("the registered denominator is the INTERSECTION -- intervals "
                     "in which both spacecraft are labelled quiet. Where it is "
                     "below the registered 50 window-days the registration's own "
                     "fallback to the union is used and is named here.")},
        "floors": floors,
        "arms": arms,
        "increments": increments,
        "controls": controls,
        "attribution": attrib,
        "gates": gates,
    }


# ==========================================================================
# GEO arm
# ==========================================================================
def geo_series(arrays_by_norad, norad):
    return arrays_by_norad.get(int(norad))


def run_geo(say):
    meta = json.loads((GEO_WORK / "extract-meta.json").read_text())
    pinned = (meta["rowsScanned"] == 217007154 and meta["rowsKept"] == 11626494
              and meta["objectsKept"] == 1768)
    if not pinned:
        return {"gates": {"G8_geoInput": {"fired": True, "meta": meta}},
                "note": "GATE G8 fired: the near-GEO extract is not T8a's"}
    with np.load(GEO_WORK / "near-geo.npz") as z:
        arrays = {k: z[k] for k in z.files}
    series = {s.norad: s for s in pg.build_series(arrays)}
    say(f"  {len(series)} near-GEO objects")

    episodes = []
    with GEO_EPISODES.open() as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("record") == "provenance":
                continue
            episodes.append(r)
    say(f"  {len(episodes)} episodes")

    # per-episode differential floor
    rows = []
    agree_num = agree_den = 0
    rev_num = rev_den = 0
    ctrl_num = ctrl_den = 0
    ns_agree_num = ns_agree_den = 0
    ns_ctrl_num = ns_ctrl_den = 0
    single_flag_total = 0.0
    single_flag_days = 0.0
    all_rho, all_ratio, all_ratio_ns = [], [], []
    hoo_err = []
    refused = 0
    total_outputs = 0

    for ep in episodes:
        sa, sb = series.get(int(ep["a"])), series.get(int(ep["b"]))
        if sa is None or sb is None:
            continue
        t0, t1 = ep["startMs"], ep["endMs"]
        ia = np.searchsorted(sa.epoch_ms, [t0, t1])
        ib = np.searchsorted(sb.epoch_ms, [t0, t1])
        if ia[1] - ia[0] < 20 or ib[1] - ib[0] < 20:
            continue
        ta, tb = sa.epoch_ms[ia[0]:ia[1]], sb.epoch_ms[ib[0]:ib[1]]
        da_, db_ = sa.drift[ia[0]:ia[1]], sb.drift[ib[0]:ib[1]]
        inca, incb = sa.inc[ia[0]:ia[1]], sb.inc[ib[0]:ib[1]]

        hoo_err.append(hold_one_out_error(ta, da_))
        db_on_a = interpolate_refusing_gaps(tb, db_, ta)
        incb_on_a = interpolate_refusing_gaps(tb, incb, ta)
        total_outputs += ta.size
        refused += int((~np.isfinite(db_on_a)).sum())
        ok = np.isfinite(db_on_a)
        if ok.sum() < 20:
            continue
        ddiff = da_ - db_on_a
        idiff = inca - incb_on_a

        # single-object flags inside the episode
        fa = pg.drift_change_flags(_sub(sa, ia[0], ia[1]), _sigma_of(da_))[0]
        fb = pg.drift_change_flags(_sub(sb, ib[0], ib[1]), _sigma_of(db_))[0]
        single = np.sort(np.concatenate([fa, fb]))

        # quiet intervals: no single-object flag within +-7 d
        quiet = np.ones(ta.size, dtype=bool)
        for t in single:
            quiet &= np.abs(ta.astype(np.float64) - t) > GEO_QUIET_GUARD_DAYS * DAY_MS
        quiet &= ok
        if quiet.sum() < 12:
            continue

        res_a = _rate_residual(ta, da_)
        res_b = interpolate_refusing_gaps(tb, _rate_residual(tb, db_), ta)
        res_d = _rate_residual(ta, ddiff)
        res_ia = _rate_residual(ta, inca)
        res_id = _rate_residual(ta, idiff)
        m = quiet & np.isfinite(res_b)
        if m.sum() < 12:
            continue
        s_single = mad_scale(res_a[m]); s_diff = mad_scale(res_d[m])
        si_single = mad_scale(res_ia[m]); si_diff = mad_scale(res_id[m])
        if not (np.isfinite(s_single) and s_single > 0):
            continue
        rho = float(np.corrcoef(res_a[m], res_b[m])[0, 1])
        all_rho.append(rho); all_ratio.append(s_diff / s_single)
        if np.isfinite(si_single) and si_single > 0:
            all_ratio_ns.append(si_diff / si_single)

        # differential flags at the same shape
        fd = ta[confirmed_indices(res_d, max(5.0 * s_diff, GEO_FLOOR_DEG_PER_DAY))]
        fnd = ta[confirmed_indices(res_id, max(5.0 * si_diff, I_FLOOR_DEG))] \
            if np.isfinite(si_diff) else np.asarray([], np.int64)

        span_days = (t1 - t0) / DAY_MS
        single_flag_total += single.size
        single_flag_days += span_days

        for t in fd:
            agree_den += 1
            agree_num += int(np.any(np.abs(single - t) <= GEO_AGREE_DAYS * DAY_MS))
            for sh in (-GEO_CONTROL_SHIFT_DAYS, GEO_CONTROL_SHIFT_DAYS):
                ts = t + sh * DAY_MS
                if t0 <= ts <= t1:
                    ctrl_den += 1
                    ctrl_num += int(np.any(np.abs(single - ts) <= GEO_AGREE_DAYS * DAY_MS))
        for t in fnd:
            ns_agree_den += 1
            ns_agree_num += int(np.any(np.abs(single - t) <= GEO_AGREE_DAYS * DAY_MS))
            for sh in (-GEO_CONTROL_SHIFT_DAYS, GEO_CONTROL_SHIFT_DAYS):
                ts = t + sh * DAY_MS
                if t0 <= ts <= t1:
                    ns_ctrl_den += 1
                    ns_ctrl_num += int(np.any(np.abs(single - ts) <= GEO_AGREE_DAYS * DAY_MS))
        for t in single:
            rev_den += 1
            rev_num += int(np.any(np.abs(fd - t) <= GEO_AGREE_DAYS * DAY_MS))

        rows.append({"a": ep["a"], "b": ep["b"], "rho": rho,
                     "ratio": s_diff / s_single, "quietSamples": int(m.sum())})

    hoo = np.concatenate([h for h in hoo_err if h.size]) if hoo_err else np.asarray([])
    hoo = hoo[np.isfinite(hoo)]
    rho_arr = np.asarray(all_rho); ratio_arr = np.asarray(all_ratio)
    ns_arr = np.asarray(all_ratio_ns)
    rng = np.random.default_rng(SEED)

    def boot_median(x):
        if x.size < 8:
            return None
        s = [float(np.median(rng.choice(x, x.size, replace=True)))
             for _ in range(BOOTSTRAP_N)]
        return [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))]

    rho_med = float(np.median(rho_arr)) if rho_arr.size else float("nan")
    out = {
        "gates": {"G8_geoInput": {"fired": False, "pinnedCounts": True}},
        "episodesUsed": len(rows), "episodesRead": len(episodes),
        "interpolation": {"outputEpochs": total_outputs, "refusedForGap": refused,
                          "medianAbsHoldOneOutErrorDegPerDay":
                              float(np.median(np.abs(hoo))) if hoo.size else None,
                          "madSigmaDegPerDay": mad_scale(hoo)},
        "floors": {
            "rhoMedian": rho_med, "rho95": boot_median(rho_arr),
            "ratioMedianEastWest": float(np.median(ratio_arr)) if ratio_arr.size else None,
            "ratio95EastWest": boot_median(ratio_arr),
            "ratioDerivedFromRho": math.sqrt(max(0.0, 2.0 * (1.0 - rho_med))),
            "ratioMedianNorthSouth": float(np.median(ns_arr)) if ns_arr.size else None,
            "ratio95NorthSouth": boot_median(ns_arr),
            "ratioQuantilesEastWest": ([float(v) for v in np.percentile(ratio_arr, [10, 25, 50, 75, 90])]
                                       if ratio_arr.size else None),
            "note": ("quiet means no single-object flag within +-7 days -- a chosen "
                     "screen, not an operator's declaration; there is no manoeuvre "
                     "truth at GEO"),
        },
        "agreement": {
            "eastWest": {
                "differentialFlags": agree_den, "withSingleObjectFlagWithin2d": agree_num,
                "rate": (agree_num / agree_den) if agree_den else None,
                "wilson95": wilson(agree_num, agree_den),
                "controlShifted30d": {"n": ctrl_den, "k": ctrl_num,
                                      "rate": (ctrl_num / ctrl_den) if ctrl_den else None,
                                      "wilson95": wilson(ctrl_num, ctrl_den)},
                "lift": ((agree_num / agree_den) / (ctrl_num / ctrl_den))
                        if (agree_den and ctrl_den and ctrl_num) else None,
                "reverseSingleFlagsCoveredByDifferential": {
                    "n": rev_den, "k": rev_num,
                    "rate": (rev_num / rev_den) if rev_den else None},
            },
            "northSouth": {
                "differentialFlags": ns_agree_den,
                "withSingleObjectFlagWithin2d": ns_agree_num,
                "rate": (ns_agree_num / ns_agree_den) if ns_agree_den else None,
                "wilson95": wilson(ns_agree_num, ns_agree_den),
                "controlShifted30d": {"n": ns_ctrl_den, "k": ns_ctrl_num,
                                      "rate": (ns_ctrl_num / ns_ctrl_den) if ns_ctrl_den else None},
                "lift": ((ns_agree_num / ns_agree_den) / (ns_ctrl_num / ns_ctrl_den))
                        if (ns_agree_den and ns_ctrl_den and ns_ctrl_num) else None,
                "note": "the north-south channel is new to this programme at GEO",
            },
            "note": ("agreement is agreement; with no truth at GEO no number here is "
                     "accuracy and the word recall is not used"),
        },
        "perEpisode": rows[:400],
    }
    say(f"  GEO rho median {rho_med:.4f}, R median "
        f"{out['floors']['ratioMedianEastWest']:.4f} over {len(rows)} episodes")
    return out


class _Sub:
    __slots__ = ("norad", "epoch_ms", "drift", "inc")


def _sub(s, i0, i1):
    o = _Sub()
    o.norad = s.norad
    o.epoch_ms = s.epoch_ms[i0:i1]
    o.drift = s.drift[i0:i1]
    o.inc = s.inc[i0:i1]
    return o


def _sigma_of(d):
    return pp.mad_sigma(np.diff(np.asarray(d, dtype=np.float64)), math.sqrt(2.0))


def _rate_residual(t_ms, y):
    """Departure of y from its trailing 10-sample median, the shape
    `pg.drift_change_flags` uses, made available for any series."""
    y = np.asarray(y, dtype=np.float64)
    base = pp.sliding_median(y, pg.BURN_BASELINE_SAMPLES)
    return np.nan_to_num(y - base, nan=0.0)


# ==========================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=("leo", "geo", "all"), default="all")
    ap.add_argument("--out", type=Path,
                    default=REPO / "docs" / "t21-differential-results-20260923.json")
    args = ap.parse_args(argv)

    def say(m):
        print(m, flush=True)

    gate1 = detector_state()
    say(f"G1 detector files clean: {gate1['clean']}")
    out = {
        "registration": "docs/t21-differential-preregistration-20260923.md",
        "generatedUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "publishedFloorsReadFirst": PUBLISHED,
        "gates": {"G1_detectorUntouched": gate1},
        "constants": {"baselineFlagRatePerQuietWindowDay": BASELINE_FLAG_RATE,
                      "maxGapDays": MAX_GAP_DAYS, "seed": SEED,
                      "bootstrapResamples": BOOTSTRAP_N,
                      "kGrid": [float(K_GRID[0]), float(K_GRID[-1]), 0.25]},
    }
    if args.arm in ("leo", "all"):
        say("LEO arm ...")
        out["leo"] = run_leo(say)
    if args.arm in ("geo", "all"):
        say("GEO arm ...")
        out["geo"] = run_geo(say)
    args.out.write_text(json.dumps(out, indent=2, default=float) + "\n")
    say(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
