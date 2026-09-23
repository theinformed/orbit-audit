#!/usr/bin/env python3
"""T8b: LEO/MEO/HEO approach events from plane matching and phasing.

Every definition here is the one registered in
`docs/proximity-leo-preregistration-20260922.md` and must not drift from it.
Section references below (prereg N) point at that document; where this module
makes an implementation choice the registration left open, the choice is
marked IMPL and justified in place.

The instrument is ownership-agnostic. Catalogue registry codes are carried
onto every event row as metadata and are read by **no** detector branch.
`object_type` is read only to assign the payload / catalogue-passive labels of
prereg 3.3. Nothing here computes a delta-V, a mass, or any consumables figure
for any object.

The two conversion constants of prereg 2.6 are recorded here, in this
docstring, and appear in no executable path:

    plane change     dV = 2 v sin(theta/2)      v = sqrt(mu/a)
    in-track change  dV = (v/2) (da/a)

A reader who wants a velocity figure can apply them; this module does not, and
`tests/test_orbit_proximity_plane.py` asserts that no event row carries one.

Read-only against the archive (`PRAGMA query_only=1`), one sequential pass in
NORAD order so the clustered `element_set` table is read sequentially.

Stages
------
  extract   one pass over `element_set`: a column cache, the per-object daily
            grid of prereg 3.2, and the per-object quiet-segment statistics
  detect    calibration (prereg 5.2), the manoeuvre detector (prereg 5.4) and
            the never-manoeuvred class (prereg 3.4)
  bench     the registered CPU-versus-GPU measurement of prereg 8.2
  screen    the provably-admissive coarse screen of prereg 8.1
  analyze   events, attribution, nulls, controls, lead times
  all       every stage in order
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

from pipeline import orbit_campaigns  # noqa: E402
from pipeline.orbit_events import PASSIVE_TYPES  # noqa: E402  (prereg 3.3, borrowed)

# --------------------------------------------------------------------------
# Physical primitives and the constants derived from them (prereg 2).
# Recomputed here from WGS-84/EGM-96 values so a reader can check the
# arithmetic without leaving the file.
# --------------------------------------------------------------------------
MU_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6378.137
J2 = 1.08262668e-3
OMEGA_E_DEG_PER_DAY = 360.9856473
OMEGA_E_RAD_PER_S = OMEGA_E_DEG_PER_DAY * math.pi / 180.0 / 86400.0
A_GEO_KM = (MU_KM3_S2 / OMEGA_E_RAD_PER_S ** 2) ** (1.0 / 3.0)   # 42164.1696

# The reference LEO radius every linear scale in prereg 4.2 is quoted at.
REF_LEO_ALT_KM = 500.0
REF_LEO_A_KM = EARTH_RADIUS_KM + REF_LEO_ALT_KM

DAY_MS = 86400000.0
SCALE_ANGLE = 1e4
SCALE_MM = 1e8
SCALE_ECC = 1e8

# --------------------------------------------------------------------------
# Registered constants (docs/proximity-leo-preregistration-20260922.md)
# --------------------------------------------------------------------------
SEED = 20260922                        # prereg 6.1, 8.3
N_PERMUTATIONS = 1000                  # prereg 6.1(b)
N_TIME_SHUFFLES = 200                  # prereg 6.3(b)
ARM_G_SAMPLE_PER_REGIME = 2000         # prereg 3.3

THETA_P_DEG = 0.2                      # prereg 4.2
THETA_P_SENSITIVITY = (0.05, 0.1, 0.5, 1.0)
GAMMA_DEG = 5.0
GAMMA_SENSITIVITY = (1.0, 0.2085)
D_DAYS = 30.0
D_SENSITIVITY = (14.0, 60.0)
THETA_FAR_DEG = 5.0
GAMMA_FAR_DEG = 60.0
T_LOOK_DAYS = 1095.0

MAX_GAP_DAYS = 5.0                     # prereg 4.4
FAST_ANGLE_MAX_GAP_DAYS = 1.0          # prereg 5.1
LOITER_MIN_OCCUPANCY_PER_DAY = 0.4     # prereg 4.4
ATTRIBUTION_SHARE = 0.8                # prereg 4.5(a)
PHASE_ARREST_RATIO = 0.2               # prereg 4.5(b)
CAMPAIGN_MAX_GAP_DAYS = 180.0          # prereg 5.5

QUIET_MIN_DAYS = 60.0                  # prereg 5.3
CONTROL_MIN_ELEMENT_SETS = 200         # prereg 3.4
CONTROL_MIN_SPAN_DAYS = 365.0          # prereg 3.4

BURN_BASELINE_SAMPLES = 10             # prereg 5.4
BURN_SIGMA_K = 5.0
DA_FLOOR_KM = 0.050                    # prereg 5.4, in-track floor
I_FLOOR_DEG = 0.01                     # prereg 5.4, TLE resolution floor
SLOW_PLANE_WINDOW_DAYS = 90.0          # prereg 9.2

LEO_CEILING_KM = 2000.0                # prereg 3.1
MEO_ECC_MAX = 0.25
DECAY_PERIGEE_KM = 100.0
NEAR_GEO_MM = (0.95, 1.05)             # T8a's band, excluded verbatim
NEAR_GEO_ECC = 0.01
NEAR_GEO_INC_DEG = 25.0

REGIMES = ("LEO", "MEO", "HEO")

# Gate bars, each as the formula AND its evaluated number (prereg 10.0).
GATE_A_SIGMA_THETA_MAX_DEG = THETA_P_DEG / 10.0                       # 0.02
GATE_B_LEAK_RATIO = 0.10
GATE_D_MIN_EVENTS = 20
GATE_F_CENSOR_FRACTION = 0.20
GATE_F_WALL_DAYS = 1050.0
GATE_G_DWELL_EXCEEDANCE = 0.05
GATE_H_FALSE_ALARM_RATIO = 0.5

GPU_POOL_LIMIT_BYTES = 2 * 1024 ** 3   # prereg 8.2


# ==========================================================================
# prereg 2.1 -- the plane-separation metric
# ==========================================================================
def orbit_normal(inc_deg, raan_deg):
    """Unit orbit normal, h = R_z(Omega) R_x(i) z (prereg 2.1).

    Returns an array with the vector along the LAST axis.
    """
    i = np.radians(np.asarray(inc_deg, dtype=np.float64))
    o = np.radians(np.asarray(raan_deg, dtype=np.float64))
    si, ci = np.sin(i), np.cos(i)
    return np.stack((si * np.sin(o), -si * np.cos(o), ci), axis=-1)


def plane_separation_deg(inc_a_deg, raan_a_deg, inc_b_deg, raan_b_deg):
    """Angle between two orbit planes, in the half-angle form of prereg 2.1.

        sin^2(theta/2) = sin^2((i_a - i_b)/2) + sin i_a sin i_b sin^2(dOmega/2)

    IMPL: the algebraically identical cosine form loses precision at the tenth
    of a degree T8b works at; this form is exact there and re-derives
    theta >= |di| directly, because both terms are non-negative.
    """
    ia = np.radians(np.asarray(inc_a_deg, dtype=np.float64))
    ib = np.radians(np.asarray(inc_b_deg, dtype=np.float64))
    dom = np.radians(np.asarray(raan_a_deg, dtype=np.float64)
                     - np.asarray(raan_b_deg, dtype=np.float64))
    s = (np.sin(0.5 * (ia - ib)) ** 2
         + np.sin(ia) * np.sin(ib) * np.sin(0.5 * dom) ** 2)
    return np.degrees(2.0 * np.arcsin(np.sqrt(np.clip(s, 0.0, 1.0))))


def plane_separation_from_cosine_deg(inc_a_deg, raan_a_deg, inc_b_deg, raan_b_deg):
    """The cosine form of prereg 2.1, kept only so a test can assert the two
    agree. Not used by any detector branch."""
    ha = orbit_normal(inc_a_deg, raan_a_deg)
    hb = orbit_normal(inc_b_deg, raan_b_deg)
    return np.degrees(np.arccos(np.clip(np.sum(ha * hb, axis=-1), -1.0, 1.0)))


def cross_track_km(theta_deg, a_km):
    """Linear scale of a plane separation: the cross-track excursion it
    permits, r sin(theta) (prereg 2.1). Interpretive only."""
    return np.asarray(a_km, dtype=np.float64) * np.sin(
        np.radians(np.asarray(theta_deg, dtype=np.float64)))


# ==========================================================================
# prereg 2.3 -- J2 nodal regression, and its differentials
# ==========================================================================
def mean_motion_rev_day(a_km):
    a = np.asarray(a_km, dtype=np.float64)
    return np.sqrt(MU_KM3_S2 / a ** 3) * 86400.0 / (2.0 * math.pi)


def semi_major_axis_km(n_rev_day):
    n = np.asarray(n_rev_day, dtype=np.float64) * 2.0 * math.pi / 86400.0
    return (MU_KM3_S2 / (n * n)) ** (1.0 / 3.0)


def j2_nodal_rate_deg_per_day(a_km, ecc, inc_deg):
    """Omega_dot = -(3/2) n J2 (Re/p)^2 cos i,  p = a(1-e^2)   (prereg 2.3).

    Validated in the registration against the sun-synchronous condition: at
    a = Re + 800 km, i = 98.6 deg this returns +0.985 deg/day against the
    Sun's +0.9856 deg/day.
    """
    a = np.asarray(a_km, dtype=np.float64)
    e = np.asarray(ecc, dtype=np.float64)
    i = np.radians(np.asarray(inc_deg, dtype=np.float64))
    n_deg_day = np.sqrt(MU_KM3_S2 / a ** 3) * 86400.0 * 180.0 / math.pi
    p = a * (1.0 - e * e)
    return -1.5 * n_deg_day * J2 * (EARTH_RADIUS_KM / p) ** 2 * np.cos(i)


def j2_nodal_rate_d_da(a_km, ecc, inc_deg):
    """d(Omega_dot)/da = -(7/2) Omega_dot / a (prereg 2.3)."""
    return -3.5 * j2_nodal_rate_deg_per_day(a_km, ecc, inc_deg) / np.asarray(
        a_km, dtype=np.float64)


# ==========================================================================
# prereg 2.4 -- chance co-planarity: dwell and rate, from OWN measured rates
# ==========================================================================
def chance_coplanar_half_width_deg(theta_p_deg, inc_a_deg, inc_b_deg):
    """Half-width in relative RAAN of the co-planar window (prereg 2.4).

    None when |di| >= theta_p: the pair never becomes co-planar to theta_p.
    """
    ia = math.radians(float(inc_a_deg))
    ib = math.radians(float(inc_b_deg))
    num = (math.sin(0.5 * math.radians(theta_p_deg)) ** 2
           - math.sin(0.5 * (ia - ib)) ** 2)
    den = math.sin(ia) * math.sin(ib)
    if num <= 0.0 or den <= 0.0:
        return None
    s = num / den
    if s >= 1.0:
        return 180.0
    return math.degrees(2.0 * math.asin(math.sqrt(s)))


def chance_coplanar_dwell_days(theta_p_deg, inc_a_deg, inc_b_deg,
                               d_omega_dot_deg_per_day):
    """Dwell of one chance co-planar crossing (prereg 2.4).

    `d_omega_dot_deg_per_day` MUST be the difference of the two objects' OWN
    fitted nodal rates over their OWN histories (prereg 5.3). Passing a
    nominal rate at a nominal altitude is the T8a failure this function
    exists to make impossible to repeat by accident, which is why the caller
    supplies the rate and this function never computes one.

    `math.inf` means the pair's relative node does not move: co-planarity, if
    it holds, holds forever (prereg 2.4 consequence 3).
    """
    half = chance_coplanar_half_width_deg(theta_p_deg, inc_a_deg, inc_b_deg)
    if half is None:
        return 0.0
    rate = abs(float(d_omega_dot_deg_per_day))
    if rate == 0.0:
        return math.inf
    return 2.0 * half / rate


def chance_coplanar_rate_per_day(d_omega_dot_deg_per_day):
    """Rate of co-planar crossings, 2|dOmega_dot|/360 per day (prereg 2.4)."""
    return 2.0 * abs(float(d_omega_dot_deg_per_day)) / 360.0


# ==========================================================================
# prereg 2.5 -- phasing
# ==========================================================================
def phase_rate_deg_per_day_per_km(a_km):
    """d(gamma_dot)/d(da) = -(3/2)(360 n / a) deg/day per km (prereg 2.5).

    -1.19487 deg/day per km at a = 6878.137 km.
    """
    a = np.asarray(a_km, dtype=np.float64)
    return -1.5 * 360.0 * mean_motion_rev_day(a) / a


def phase_confinement_da_km(gamma_deg, d_days, a_km):
    """|da| <= Gamma / (|d(gamma_dot)/d(da)| D)   (prereg 2.5).

    0.1395 km at Gamma = 5 deg, D = 30 d, a = 6878.137 km.
    """
    return float(gamma_deg) / (abs(phase_rate_deg_per_day_per_km(a_km))
                               * float(d_days))


# ==========================================================================
# prereg 5.1 -- the fast angle
# ==========================================================================
def true_anomaly_deg(mean_anomaly_deg, ecc, tol=1e-12, max_iter=60):
    """Newton solution of Kepler's equation, then the true anomaly."""
    m = np.radians(np.mod(np.asarray(mean_anomaly_deg, dtype=np.float64), 360.0))
    e = np.asarray(ecc, dtype=np.float64)
    ea = np.where(e < 0.8, m, np.pi * np.ones_like(m))
    for _ in range(max_iter):
        f = ea - e * np.sin(ea) - m
        fp = 1.0 - e * np.cos(ea)
        step = f / fp
        ea = ea - step
        if np.all(np.abs(step) < tol):
            break
    nu = 2.0 * np.arctan2(np.sqrt(1.0 + e) * np.sin(0.5 * ea),
                          np.sqrt(1.0 - e) * np.cos(0.5 * ea))
    return np.degrees(np.mod(nu, 2.0 * np.pi))


def true_anomaly_series_deg(mean_anomaly_deg, ecc):
    """Equation of the centre to O(e^2) (prereg 5.1). A test asserts it agrees
    with the Newton solution for e <= 0.01."""
    m = np.radians(np.asarray(mean_anomaly_deg, dtype=np.float64))
    e = np.asarray(ecc, dtype=np.float64)
    return np.degrees(np.mod(m + 2.0 * e * np.sin(m)
                             + 1.25 * e * e * np.sin(2.0 * m), 2.0 * np.pi))


def position_unit_vector(inc_deg, raan_deg, argp_deg, true_anom_deg):
    """r_hat = R_z(Omega) R_x(i) R_z(omega + nu) x_hat (prereg 5.1)."""
    i = np.radians(np.asarray(inc_deg, dtype=np.float64))
    o = np.radians(np.asarray(raan_deg, dtype=np.float64))
    u = np.radians(np.asarray(argp_deg, dtype=np.float64)
                   + np.asarray(true_anom_deg, dtype=np.float64))
    cu, su = np.cos(u), np.sin(u)
    ci, si = np.cos(i), np.sin(i)
    co, so = np.cos(o), np.sin(o)
    return np.stack((cu * co - su * ci * so,
                     cu * so + su * ci * co,
                     su * si), axis=-1)


def track_angle_deg(ra, rb):
    """Angle between two position directions (prereg 5.1)."""
    dot = np.clip(np.sum(ra * rb, axis=-1), -1.0, 1.0)
    return np.degrees(np.arccos(dot))


# ==========================================================================
# prereg 3.1 -- regimes
# ==========================================================================
def regime_of(n_rev_day, ecc, inc_deg):
    """Regime per element set (prereg 3.1). Vectorised; returns a byte code
    array: 0 decaying, 1 near-GEO (excluded), 2 LEO, 3 MEO, 4 HEO."""
    n = np.asarray(n_rev_day, dtype=np.float64)
    e = np.asarray(ecc, dtype=np.float64)
    i = np.asarray(inc_deg, dtype=np.float64)
    a = semi_major_axis_km(n)
    hp = a * (1.0 - e) - EARTH_RADIUS_KM
    ha = a * (1.0 + e) - EARTH_RADIUS_KM
    out = np.full(a.shape, 4, dtype=np.uint8)                      # HEO default
    meo = (e <= MEO_ECC_MAX) & (hp >= LEO_CEILING_KM) & (a <= 0.95 * A_GEO_KM)
    out[meo] = 3
    out[ha <= LEO_CEILING_KM] = 2
    near_geo = ((n >= NEAR_GEO_MM[0]) & (n <= NEAR_GEO_MM[1])
                & (e <= NEAR_GEO_ECC) & (i <= NEAR_GEO_INC_DEG))
    out[near_geo] = 1
    out[hp < DECAY_PERIGEE_KM] = 0
    return out


REGIME_CODE = {"decaying": 0, "nearGEO": 1, "LEO": 2, "MEO": 3, "HEO": 4}
REGIME_NAME = {v: k for k, v in REGIME_CODE.items()}


def class_label(object_type):
    """prereg 3.3. Reads `object_type` and nothing else."""
    if not object_type:
        return None
    upper = object_type.upper()
    if upper == "PAYLOAD":
        return "payload"
    if upper in {t.upper() for t in PASSIVE_TYPES}:
        return "catalogue_passive"
    return None


# ==========================================================================
# Stage 1 -- extract
# ==========================================================================
_SELECT = ("SELECT norad, epoch_ms, mean_motion_q, eccentricity_q, "
           "inclination_q, raan_q, arg_perigee_q, mean_anomaly_q "
           "FROM element_set")

_CACHE_COLS = (
    ("norad", np.int32), ("epoch_ms", np.int64), ("mm_q", np.uint32),
    ("ecc_q", np.int32), ("inc_q", np.int32), ("raan_q", np.int32),
    ("argp_q", np.int32), ("ma_q", np.int32), ("regime", np.uint8),
)


class Cache:
    """Memory-mapped element-set cache in NORAD/epoch order, with a per-object
    index. IMPL: the registration asks for element-set resolution for the
    manoeuvre detector (prereg 5.4) and daily resolution for the screen
    (prereg 3.2). Re-reading 217 M rows from SQLite for every stage costs
    ~620 s each time; one pass writes this cache and every later stage reads
    it sequentially from disk. Nothing about any definition changes."""

    def __init__(self, root):
        self.root = Path(root)
        self.arr = {}

    def path(self, name):
        return self.root / f"cache-{name}.npy"

    def open(self):
        for name, _ in _CACHE_COLS:
            self.arr[name] = np.load(self.path(name), mmap_mode="r")
        idx = np.load(self.root / "cache-index.npz")
        self.index_norad = idx["norad"]
        self.index_start = idx["start"]
        self.index_count = idx["count"]
        self._pos = {int(n): k for k, n in enumerate(self.index_norad)}
        return self

    def slice_for(self, norad):
        k = self._pos.get(int(norad))
        if k is None:
            return None
        s = int(self.index_start[k])
        c = int(self.index_count[k])
        return s, s + c

    def elements(self, norad, lo_ms=None, hi_ms=None):
        """Full-resolution element series for one object, as float degrees."""
        sl = self.slice_for(norad)
        if sl is None:
            return None
        s, e = sl
        ep = np.asarray(self.arr["epoch_ms"][s:e], dtype=np.int64)
        if lo_ms is not None or hi_ms is not None:
            m = np.ones(ep.size, dtype=bool)
            if lo_ms is not None:
                m &= ep >= lo_ms
            if hi_ms is not None:
                m &= ep <= hi_ms
            if not m.any():
                return None
            off = np.nonzero(m)[0]
            s2, e2 = s + int(off[0]), s + int(off[-1]) + 1
        else:
            s2, e2 = s, e
        return {
            "epoch_ms": np.asarray(self.arr["epoch_ms"][s2:e2], dtype=np.int64),
            "n": np.asarray(self.arr["mm_q"][s2:e2], dtype=np.float64) / SCALE_MM,
            "e": np.asarray(self.arr["ecc_q"][s2:e2], dtype=np.float64) / SCALE_ECC,
            "inc": np.asarray(self.arr["inc_q"][s2:e2], dtype=np.float64) / SCALE_ANGLE,
            "raan": np.asarray(self.arr["raan_q"][s2:e2], dtype=np.float64) / SCALE_ANGLE,
            "argp": np.asarray(self.arr["argp_q"][s2:e2], dtype=np.float64) / SCALE_ANGLE,
            "ma": np.asarray(self.arr["ma_q"][s2:e2], dtype=np.float64) / SCALE_ANGLE,
            "regime": np.asarray(self.arr["regime"][s2:e2], dtype=np.uint8),
        }


_GRID_COLS = (("norad", np.int32), ("day", np.int32), ("a", np.float64),
              ("e", np.float32), ("inc", np.float32), ("raan", np.float32),
              ("argp", np.float32))


def grid_path(out_dir, regime, name):
    return Path(out_dir) / f"grid-{regime}-{name}.npy"


def load_grid(out_dir, regime):
    return {name: np.load(grid_path(out_dir, regime, name), mmap_mode="r")
            for name, _ in _GRID_COLS}


def extract(db, out_dir, limit_rows=None, progress_every=25_000_000):
    """One sequential pass. Writes the element-set cache, the per-object index
    and the daily grid of prereg 3.2 (slow elements only: the fast angle is
    never evaluated on the grid)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = Cache(out_dir)
    handles = {name: open(cache.path(name), "wb") for name, _ in _CACHE_COLS}
    ghandles = {r: {name: open(grid_path(out_dir, r, name), "wb")
                    for name, _ in _GRID_COLS} for r in REGIMES}

    idx_norad, idx_start, idx_count = [], [], []
    buf = {name: [] for name, _ in _CACHE_COLS}
    gbuf = {r: {name: [] for name, _ in _GRID_COLS} for r in REGIMES}
    grid_rows = {r: 0 for r in REGIMES}
    grid_objs = {r: set() for r in REGIMES}

    written = 0
    seen = 0
    started = time.time()
    cur_norad = None
    cur = []

    def flush(force=False):
        if force or len(buf["norad"]) > 512:
            for name, dtype in _CACHE_COLS:
                if buf[name]:
                    np.concatenate(buf[name]).astype(dtype).tofile(handles[name])
                    buf[name] = []
        for r in REGIMES:
            if force or len(gbuf[r]["norad"]) > 512:
                for name, dtype in _GRID_COLS:
                    if gbuf[r][name]:
                        np.concatenate(gbuf[r][name]).astype(dtype).tofile(
                            ghandles[r][name])
                        gbuf[r][name] = []

    def finish_object():
        nonlocal written
        if cur_norad is None or not cur:
            return
        rows = np.asarray(cur, dtype=np.int64)
        rows = rows[np.argsort(rows[:, 0], kind="stable")]
        ep = rows[:, 0]
        n = rows[:, 1].astype(np.float64) / SCALE_MM
        e = rows[:, 2].astype(np.float64) / SCALE_ECC
        inc = rows[:, 3].astype(np.float64) / SCALE_ANGLE
        raan = rows[:, 4].astype(np.float64) / SCALE_ANGLE
        argp = rows[:, 5].astype(np.float64) / SCALE_ANGLE
        reg = regime_of(n, e, inc)

        idx_norad.append(cur_norad)
        idx_start.append(written)
        idx_count.append(rows.shape[0])
        written += rows.shape[0]

        buf["norad"].append(np.full(rows.shape[0], cur_norad, dtype=np.int32))
        buf["epoch_ms"].append(ep)
        buf["mm_q"].append(rows[:, 1])
        buf["ecc_q"].append(rows[:, 2])
        buf["inc_q"].append(rows[:, 3])
        buf["raan_q"].append(rows[:, 4])
        buf["argp_q"].append(rows[:, 5])
        buf["ma_q"].append(rows[:, 6])
        buf["regime"].append(reg)

        day = (ep // int(DAY_MS)).astype(np.int64)
        first = np.ones(day.size, dtype=bool)
        first[1:] = day[1:] != day[:-1]
        a = semi_major_axis_km(n)
        for rname in REGIMES:
            m = first & (reg == REGIME_CODE[rname])
            k = int(m.sum())
            if not k:
                continue
            g = gbuf[rname]
            g["norad"].append(np.full(k, cur_norad, dtype=np.int32))
            g["day"].append(day[m])
            g["a"].append(a[m])
            g["e"].append(e[m])
            g["inc"].append(inc[m])
            g["raan"].append(raan[m])
            g["argp"].append(argp[m])
            grid_rows[rname] += k
            grid_objs[rname].add(cur_norad)

    for row in db.execute(_SELECT):
        seen += 1
        if row[0] != cur_norad:
            finish_object()
            cur_norad = row[0]
            cur = []
            flush()
        cur.append(row[1:])
        if limit_rows is not None and seen >= limit_rows:
            break
        if progress_every and seen % progress_every == 0:
            print(f"  ... {seen:,} rows, {written:,} cached, "
                  f"{time.time() - started:.0f}s", flush=True)
    finish_object()
    flush(force=True)
    for h in handles.values():
        h.close()
    for r in REGIMES:
        for h in ghandles[r].values():
            h.close()

    # the columns were written raw; re-wrap each as a .npy so later stages can
    # memory-map them without carrying a separate dtype manifest
    for name, dtype in _CACHE_COLS:
        raw = np.fromfile(cache.path(name), dtype=dtype)
        np.save(cache.path(name), raw)
        del raw
    for r in REGIMES:
        for name, dtype in _GRID_COLS:
            raw = np.fromfile(grid_path(out_dir, r, name), dtype=dtype)
            np.save(grid_path(out_dir, r, name), raw)
            del raw

    np.savez(out_dir / "cache-index.npz",
             norad=np.asarray(idx_norad, dtype=np.int64),
             start=np.asarray(idx_start, dtype=np.int64),
             count=np.asarray(idx_count, dtype=np.int64))

    meta = {"rowsScanned": seen, "rowsCached": written,
            "objects": len(idx_norad), "wallSeconds": time.time() - started,
            "byRegime": {r: {"objectDays": grid_rows[r],
                             "objects": len(grid_objs[r])} for r in REGIMES}}
    (out_dir / "extract-meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def object_metadata(db, norads):
    """Catalogue metadata, carried onto event rows, read by no detector branch
    except `object_type` for the labels of prereg 3.3."""
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


def wrap180(deg):
    out = np.mod(np.asarray(deg, dtype=np.float64) + 180.0, 360.0) - 180.0
    return np.where(out == -180.0, 180.0, out)


def wrap360(deg):
    return np.mod(np.asarray(deg, dtype=np.float64), 360.0)


# ==========================================================================
# prereg 8.1 -- the provably admissive coarse screen
# ==========================================================================
def screen_grid_step_days(d_days):
    """prereg 8.1: step D/2, so any dwell of length >= D contains at least two
    grid points -- and, because the dwell is contiguous, two CONSECUTIVE ones.
    The screen can therefore reject no admissible event, with no inflation of
    the threshold at all."""
    return float(d_days) / 2.0


def screen_da_window_km(gamma_deg, d_days, a_km):
    """1.5x the phase-confinement bound of prereg 2.5, generous so the screen
    can only admit, never reject (prereg 8.1)."""
    return 1.5 * phase_confinement_da_km(gamma_deg, d_days, a_km)


def gpu_chunk_bytes(n_rows, n_cols, bytes_per_value=8, n_buffers=6):
    """Device-pool size implied by a screen chunk (prereg 8.2). A test asserts
    the chosen chunk stays at or below 2 GiB."""
    return int(n_rows) * int(n_cols) * int(bytes_per_value) * int(n_buffers)


def screen_epoch_cpu(a_app, inc_app, raan_app, idx_app,
                     a_all, inc_all, raan_all, idx_all,
                     theta_p_deg, da_window_km):
    """One screening epoch on CPU. Returns (i_app, i_all) index pairs whose
    plane separation is at or below theta_p AND whose semi-major axes are
    within the window. All three screens are provably admissive (prereg 8.1):
    the semi-major-axis window is necessary for prereg 2.5's phase
    confinement, |di| <= theta is necessary by prereg 2.1's exact lower bound,
    and theta itself is the criterion."""
    order = np.argsort(a_all, kind="stable")
    a_sorted = a_all[order]
    lo = np.searchsorted(a_sorted, a_app - da_window_km, side="left")
    hi = np.searchsorted(a_sorted, a_app + da_window_km, side="right")
    counts = (hi - lo).astype(np.int64)
    total = int(counts.sum())
    if total == 0:
        return (np.asarray([], dtype=np.int64), np.asarray([], dtype=np.int64))
    left = np.repeat(np.arange(a_app.size, dtype=np.int64), counts)
    offs = np.arange(total, dtype=np.int64) - np.repeat(
        np.cumsum(counts) - counts, counts)
    right = order[np.repeat(lo, counts) + offs]
    keep = idx_app[left] != idx_all[right]
    left, right = left[keep], right[keep]
    if left.size == 0:
        return left, right
    keep = np.abs(inc_app[left] - inc_all[right]) <= theta_p_deg
    left, right = left[keep], right[keep]
    if left.size == 0:
        return left, right
    theta = plane_separation_deg(inc_app[left], raan_app[left],
                                 inc_all[right], raan_all[right])
    keep = theta <= theta_p_deg
    return left[keep], right[keep]


def screen_epoch_gpu(xp, a_app, inc_app, raan_app, idx_app,
                     a_all, inc_all, raan_all, idx_all,
                     theta_p_deg, da_window_km):
    """The same screen on the device. Identical arithmetic; `xp` is cupy."""
    order = xp.argsort(a_all)
    a_sorted = a_all[order]
    lo = xp.searchsorted(a_sorted, a_app - da_window_km, side="left")
    hi = xp.searchsorted(a_sorted, a_app + da_window_km, side="right")
    counts = (hi - lo).astype(xp.int64)
    total = int(counts.sum())
    if total == 0:
        return (xp.zeros(0, dtype=xp.int64), xp.zeros(0, dtype=xp.int64))
    # IMPL: cupy's `repeat` does not take an array of repeat counts, so the
    # ragged expansion is built from a cumulative sum and a searchsorted --
    # the same index set, by a construction the device supports.
    cum = xp.cumsum(counts)
    starts = cum - counts
    left = xp.searchsorted(cum, xp.arange(total, dtype=xp.int64), side="right")
    offs = xp.arange(total, dtype=xp.int64) - starts[left]
    right = order[lo[left] + offs]
    keep = idx_app[left] != idx_all[right]
    left, right = left[keep], right[keep]
    if left.size == 0:
        return left, right
    keep = xp.abs(inc_app[left] - inc_all[right]) <= theta_p_deg
    left, right = left[keep], right[keep]
    if left.size == 0:
        return left, right
    ia = xp.radians(inc_app[left])
    ib = xp.radians(inc_all[right])
    dom = xp.radians(raan_app[left] - raan_all[right])
    s = (xp.sin(0.5 * (ia - ib)) ** 2
         + xp.sin(ia) * xp.sin(ib) * xp.sin(0.5 * dom) ** 2)
    theta = xp.degrees(2.0 * xp.arcsin(xp.sqrt(xp.clip(s, 0.0, 1.0))))
    keep = theta <= theta_p_deg
    return left[keep], right[keep]


# ==========================================================================
# Statistics
# ==========================================================================
def theil_sen_slope(t, y, max_points=40):
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = t.size
    if n < 2:
        return 0.0
    if n > max_points:
        step = max(1, n // max_points)
        t, y = t[::step], y[::step]
        n = t.size
    i, j = np.triu_indices(n, k=1)
    dt = t[j] - t[i]
    ok = dt != 0
    if not ok.any():
        return 0.0
    return float(np.median((y[j][ok] - y[i][ok]) / dt[ok]))


def second_difference(y):
    y = np.asarray(y, dtype=np.float64)
    if y.size < 3:
        return np.asarray([], dtype=np.float64)
    return y[2:] - 2.0 * y[1:-1] + y[:-2]


def mad_sigma(x, factor):
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.median(np.abs(x - np.median(x))) * 1.4826 / factor)


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2.0 * n)
    h = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return ((c - h) / d, (c + h) / d)


def kaplan_meier(times, censored):
    """KM survival of the lead time (prereg 5.7). `censored[i]` True means the
    initiating manoeuvre was not inside the look-back, so the true lead is at
    least `times[i]`."""
    t = np.asarray(times, dtype=np.float64)
    c = np.asarray(censored, dtype=bool)
    order = np.argsort(t, kind="stable")
    t, c = t[order], c[order]
    n = t.size
    surv, out = 1.0, []
    at_risk = n
    k = 0
    while k < n:
        tk = t[k]
        j = k
        d = 0
        while j < n and t[j] == tk:
            if not c[j]:
                d += 1
            j += 1
        if at_risk > 0 and d > 0:
            surv *= (1.0 - d / at_risk)
        out.append({"t": float(tk), "atRisk": int(at_risk), "events": int(d),
                    "survival": float(surv)})
        at_risk -= (j - k)
        k = j
    return out


def km_quantile(curve, q):
    for row in curve:
        if row["survival"] <= 1.0 - q:
            return row["t"]
    return None


def percentiles(x, ps=(5, 25, 50, 75, 95)):
    a = np.asarray([v for v in x if v is not None and np.isfinite(v)],
                   dtype=np.float64)
    if a.size == 0:
        return {str(p): None for p in ps}
    return {str(p): float(np.percentile(a, p)) for p in ps}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def iso(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).isoformat()


# ==========================================================================
# prereg 5.2 / 5.3 / 5.4 -- calibration, quiet segments, manoeuvre detection
# ==========================================================================
def sliding_median(x, window):
    """Median over the `window` samples PRECEDING each index; entries before
    the first full window are NaN. Vectorised."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= window:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(x, window)            # (n-window+1, window)
    med = np.median(w, axis=1)
    out[window:] = med[: n - window]
    return out


def centred_median(x, window):
    """Centred running median; edges fall back to the raw value."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if n < window or window < 3:
        return x.copy()
    from numpy.lib.stride_tricks import sliding_window_view
    med = np.median(sliding_window_view(x, window), axis=1)
    out = x.copy()
    half = window // 2
    out[half:half + med.size] = med
    return out


def rolling_theil_sen_residual(t_days, y, window=BURN_BASELINE_SAMPLES):
    """Residual of y[k] from a robust local FIT over the preceding `window`
    samples (prereg 5.4) -- a level and a slope, extrapolated to t[k], not a
    one-step difference. A fit is what the registration asks for, and it is
    also what makes a step in y visible at more than one epoch, so the
    two-consecutive-sample confirmation of prereg 5.4 can do its job.

    IMPL: an exact Theil-Sen over every trailing window of a 100,000-sample
    series is not affordable at archive scale. The slope is the median of the
    consecutive-difference slopes inside the window -- the Theil-Sen estimator
    restricted to adjacent pairs, the subset that carries the local trend --
    and the level is the window median, extrapolated from the window's median
    epoch. Both are medians, so both inherit Theil-Sen's breakdown point. The
    exact estimator is used wherever the sample is small (every per-object fit
    of prereg 5.3).
    """
    t = np.asarray(t_days, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = y.size
    if n < window + 2:
        return np.zeros(n, dtype=np.float64)
    dt = np.diff(t)
    inst = np.where(dt > 0, np.diff(y) / np.where(dt > 0, dt, 1.0), np.nan)
    sm = sliding_median(inst, window)
    slope = np.concatenate((sm, [sm[-1] if sm.size else 0.0]))[:n]
    slope = np.nan_to_num(slope, nan=0.0)
    level = sliding_median(y, window)
    level_t = sliding_median(t, window)
    base = level + slope * (t - level_t)
    res = y - base
    res[:window] = 0.0
    return np.nan_to_num(res, nan=0.0)


def object_sigma_contributions(el):
    """Per-object fit-noise contributions (prereg 5.2): the MAD of the SECOND
    difference of the plane direction and of the mean motion, taken inside the
    object's own quiet stretches. The second difference annihilates any smooth
    secular rotation and the drag trend, leaving fit-to-fit scatter."""
    n = el["n"]
    if n.size < 8:
        return (float("nan"), float("nan"))
    inc, raan = el["inc"], el["raan"]
    theta_step = plane_separation_deg(inc[1:], raan[1:], inc[:-1], raan[:-1])
    sigma_theta = mad_sigma(second_difference(theta_step), math.sqrt(6.0))
    sigma_n = mad_sigma(second_difference(n), math.sqrt(6.0))
    return (sigma_theta, sigma_n)


def detect_manoeuvres(el, sigma_n, sigma_theta):
    """prereg 5.4. Returns the confirmed in-track and plane flag indices and
    the object's own fitted secular rates.

    Both channels require two consecutive confirming element sets, so a single
    bad fit cannot fire either; the flag epoch is the SECOND set's, because
    that is the first instant a causal observer possessed the evidence (T8a
    section 5.5, reused unchanged).
    """
    ep = el["epoch_ms"]
    t = ep / DAY_MS
    n, e, inc, raan = el["n"], el["e"], el["inc"], el["raan"]
    a = semi_major_axis_km(n)
    size = n.size
    empty = np.asarray([], dtype=np.int64)
    if size < BURN_BASELINE_SAMPLES + 3:
        return {"intrack": empty, "plane": empty, "ndot": 0.0,
                "omegadot": 0.0, "n": size}

    dt = np.diff(t)
    # --- in-track channel (prereg 5.4) -----------------------------------
    res_n = rolling_theil_sen_residual(t, n)
    inst = np.where(dt > 0, np.diff(n) / np.where(dt > 0, dt, 1.0), np.nan)
    sm = sliding_median(inst, BURN_BASELINE_SAMPLES)
    ndot = np.nan_to_num(
        np.concatenate((sm, [sm[-1] if sm.size else 0.0]))[:size], nan=0.0)
    spacing = np.empty(size, dtype=np.float64)
    spacing[1:] = np.maximum(dt, 1e-6)
    spacing[0] = spacing[1]
    # the object's OWN drag term, and a floor of 50 m of semi-major axis
    n_floor = 1.5 * n * DA_FLOOR_KM / a
    thr_n = np.maximum(np.maximum(BURN_SIGMA_K * sigma_n,
                                  3.0 * np.abs(ndot) * spacing), n_floor)

    # --- plane channel (prereg 5.4, per consecutive element-set pair) -----
    di = np.zeros(size, dtype=np.float64)
    di[1:] = np.diff(inc)
    # IMPL (same registered purpose as the confirmation rule): the J2 model
    # of prereg 5.4 is evaluated from a 5-sample centred median of the
    # object's own (a, e, i), so that a single bad element fit cannot inject
    # itself into the MODEL as well as into the observation and thereby
    # manufacture two same-sign exceedances. The rate still comes from the
    # object's own measured elements and from no nominal (prereg 5.3).
    om_pred = j2_nodal_rate_deg_per_day(centred_median(a, 5),
                                        centred_median(e, 5),
                                        centred_median(inc, 5))
    dom_res = np.zeros(size, dtype=np.float64)
    dom_res[1:] = (wrap180(np.diff(raan))
                   - 0.5 * (om_pred[1:] + om_pred[:-1]) * dt)
    thr_p = max(BURN_SIGMA_K * sigma_theta, I_FLOOR_DEG)

    def confirmed(stat, thr):
        """Two consecutive element sets over the bar AND agreeing in sign.

        IMPL serving the registered purpose of prereg 5.4's confirmation rule
        ("so a single bad fit cannot fire it"): a lone outlier in a
        difference statistic produces two consecutive exceedances of OPPOSITE
        sign -- the step into the outlier and the step back out. Requiring
        agreement in sign is what makes the rule do the job the registration
        gives it; a sustained change agrees in sign by construction.
        """
        hit = np.abs(stat) > thr
        c = np.zeros(size, dtype=bool)
        c[1:] = (hit[1:] & hit[:-1]
                 & (np.sign(stat[1:]) == np.sign(stat[:-1])))
        return np.nonzero(c)[0]

    plane_idx = np.union1d(confirmed(di, thr_p), confirmed(dom_res, thr_p))

    raan_un = np.degrees(np.unwrap(np.radians(raan)))
    return {"intrack": confirmed(res_n, thr_n), "plane": plane_idx,
            "ndot": theil_sen_slope(t, n),
            "omegadot": theil_sen_slope(t, raan_un),
            "n": size}


def detect_stage(cache, db, out_dir):
    """prereg 5.2, 5.4, 3.4. Two passes over the cache: one to calibrate the
    fit noise, one to run the detector with the pooled value."""
    started = time.time()
    norads = [int(x) for x in cache.index_norad]
    sig_t, sig_n = [], []
    for nd in norads:
        el = cache.elements(nd)
        if el is None:
            continue
        st, sn = object_sigma_contributions(el)
        if np.isfinite(st):
            sig_t.append(st)
        if np.isfinite(sn):
            sig_n.append(sn)
    sigma_theta = float(np.median(sig_t)) if sig_t else float("nan")
    sigma_n = float(np.median(sig_n)) if sig_n else float("nan")
    sigma_theta_p95 = float(np.percentile(sig_t, 95)) if sig_t else float("nan")
    sigma_n_p95 = float(np.percentile(sig_n, 95)) if sig_n else float("nan")
    print(f"  calibration: sigma_theta={sigma_theta:.6g} deg (p95 "
          f"{sigma_theta_p95:.6g}), sigma_n={sigma_n:.6g} rev/day "
          f"(p95 {sigma_n_p95:.6g}), {time.time()-started:.0f}s", flush=True)

    flags = {}
    summary = {}
    for nd in norads:
        el = cache.elements(nd)
        if el is None:
            continue
        d = detect_manoeuvres(el, sigma_n, sigma_theta)
        ep = el["epoch_ms"]
        flags[nd] = {
            "intrack_ms": ep[d["intrack"]].tolist() if d["intrack"].size else [],
            "plane_ms": ep[d["plane"]].tolist() if d["plane"].size else [],
        }
        span = float((ep[-1] - ep[0]) / DAY_MS) if ep.size > 1 else 0.0
        summary[nd] = {
            "elementSets": int(ep.size), "spanDays": span,
            "firstMs": int(ep[0]), "lastMs": int(ep[-1]),
            "nIntrack": int(d["intrack"].size), "nPlane": int(d["plane"].size),
            "ndot": d["ndot"], "omegadot": d["omegadot"],
            "regimes": sorted({REGIME_NAME[int(c)]
                               for c in np.unique(el["regime"])}),
        }

    meta = object_metadata(db, norads)
    never, never_excluded = [], 0
    for nd, s in summary.items():
        if s["nIntrack"] or s["nPlane"]:
            continue
        if (s["elementSets"] < CONTROL_MIN_ELEMENT_SETS
                or s["spanDays"] < CONTROL_MIN_SPAN_DAYS):
            never_excluded += 1
            continue
        never.append(nd)
    never_set = set(never)

    labels = {nd: class_label(meta.get(nd, {}).get("objectType"))
              for nd in summary}
    cat_passive = {nd for nd, l in labels.items() if l == "catalogue_passive"}
    payload = {nd for nd, l in labels.items() if l == "payload"}

    cross = {
        "neverManoeuvred": len(never_set),
        "neverManoeuvredExcludedForThinEvidence": never_excluded,
        "cataloguePassive": len(cat_passive),
        "payload": len(payload),
        "payloadAndNeverManoeuvred": len(payload & never_set),
        "cataloguePassiveNotNeverManoeuvred": len(cat_passive - never_set),
        "cataloguePassiveAndNeverManoeuvred": len(cat_passive & never_set),
        "payloadWithPlaneManoeuvre": sum(
            1 for nd in payload if summary[nd]["nPlane"] > 0),
    }

    out = {
        "sigmaThetaDeg": sigma_theta, "sigmaThetaP95Deg": sigma_theta_p95,
        "sigmaNRevDay": sigma_n, "sigmaNP95RevDay": sigma_n_p95,
        "objects": len(summary), "wallSeconds": time.time() - started,
        "classCrossTabulation": cross,
    }
    (Path(out_dir) / "detect-meta.json").write_text(json.dumps(out, indent=2))
    np.savez(Path(out_dir) / "detect-flags.npz",
             norad=np.asarray(list(flags), dtype=np.int64),
             intrack=np.asarray([json.dumps(flags[k]["intrack_ms"])
                                 for k in flags], dtype=object),
             plane=np.asarray([json.dumps(flags[k]["plane_ms"])
                               for k in flags], dtype=object),
             allow_pickle=True)
    (Path(out_dir) / "detect-summary.json").write_text(
        json.dumps({str(k): v for k, v in summary.items()}))
    (Path(out_dir) / "detect-flags.json").write_text(
        json.dumps({str(k): v for k, v in flags.items()}))
    (Path(out_dir) / "object-meta.json").write_text(
        json.dumps({str(k): v for k, v in meta.items()}))
    print(json.dumps(out, indent=2))
    return out


# ==========================================================================
# The screening table: every object's slow elements at every screening epoch
# ==========================================================================
def build_screen_table(out_dir, regime, step_days, max_gap_days=MAX_GAP_DAYS):
    """For every screening epoch (prereg 8.1: step D/2), interpolate each
    object's slow elements to that epoch from its own daily grid, refusing
    across gaps longer than `max_gap_days` (prereg 4.4).

    RAAN is interpolated by removing the J2-predicted change first, wrapping
    the residual and adding the prediction back, so a fast-regressing object
    is not mis-unwrapped across a multi-day gap.
    """
    g = load_grid(out_dir, regime)
    norad = np.asarray(g["norad"])
    day = np.asarray(g["day"], dtype=np.int64)
    a = np.asarray(g["a"], dtype=np.float64)
    e = np.asarray(g["e"], dtype=np.float64)
    inc = np.asarray(g["inc"], dtype=np.float64)
    raan = np.asarray(g["raan"], dtype=np.float64)
    argp = np.asarray(g["argp"], dtype=np.float64)
    if norad.size == 0:
        return None

    step = int(round(step_days))
    d0 = int(day.min())
    d1 = int(day.max())
    epochs = np.arange((d0 // step) * step, d1 + step, step, dtype=np.int64)

    bounds = np.nonzero(np.diff(norad))[0] + 1
    starts = np.concatenate(([0], bounds))
    ends = np.concatenate((bounds, [norad.size]))

    cols = {k: [] for k in ("epoch_index", "object_index", "norad", "a", "e",
                            "inc", "raan", "argp", "omegadot_j2")}
    obj_list = []
    for oi, (s, en) in enumerate(zip(starts, ends)):
        nd = int(norad[s])
        obj_list.append(nd)
        dd = day[s:en]
        if dd.size < 2:
            continue
        lo = np.searchsorted(epochs, dd[0], side="left")
        hi = np.searchsorted(epochs, dd[-1], side="right")
        if hi <= lo:
            continue
        te = epochs[lo:hi]
        k = np.searchsorted(dd, te, side="right") - 1
        k = np.clip(k, 0, dd.size - 2)
        left, right = dd[k], dd[k + 1]
        gap = (right - left).astype(np.float64)
        ok = gap <= max_gap_days
        if not ok.any():
            continue
        te, k, left, right, gap = te[ok], k[ok], left[ok], right[ok], gap[ok]
        w = np.where(gap > 0, (te - left) / np.where(gap > 0, gap, 1.0), 0.0)
        aa = a[s:en][k] + w * (a[s:en][k + 1] - a[s:en][k])
        ee = e[s:en][k] + w * (e[s:en][k + 1] - e[s:en][k])
        ii = inc[s:en][k] + w * (inc[s:en][k + 1] - inc[s:en][k])
        pp = argp[s:en][k] + w * wrap180(argp[s:en][k + 1] - argp[s:en][k])
        om0 = raan[s:en][k]
        om1 = raan[s:en][k + 1]
        pred = j2_nodal_rate_deg_per_day(a[s:en][k], e[s:en][k], inc[s:en][k])
        resid = wrap180(om1 - om0 - pred * gap)
        oo = om0 + (pred * gap + resid) * w
        cols["epoch_index"].append(
            (np.searchsorted(epochs, te)).astype(np.int32))
        cols["object_index"].append(np.full(te.size, oi, dtype=np.int32))
        cols["norad"].append(np.full(te.size, nd, dtype=np.int32))
        cols["a"].append(aa)
        cols["e"].append(ee)
        cols["inc"].append(ii)
        cols["raan"].append(wrap360(oo))
        cols["argp"].append(wrap360(pp))
        cols["omegadot_j2"].append(
            j2_nodal_rate_deg_per_day(aa, ee, ii))

    packed = {k: (np.concatenate(v) if v else np.asarray([]))
              for k, v in cols.items()}
    order = np.lexsort((packed["object_index"], packed["epoch_index"]))
    packed = {k: v[order] for k, v in packed.items()}
    offsets = np.searchsorted(packed["epoch_index"],
                              np.arange(epochs.size + 1, dtype=np.int32))
    return {"epochs": epochs, "offsets": offsets, "objects": np.asarray(
        obj_list, dtype=np.int64), **packed}


# ==========================================================================
# prereg 8.2 -- the registered CPU-versus-GPU measurement
# ==========================================================================
def load_cupy():
    import glob
    import ctypes
    for pattern in (".venv-gpu/lib/python*/site-packages/nvidia/*/lib/*.so*",):
        for lib in sorted(glob.glob(str(_REPO / pattern))):
            try:
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass
    import cupy
    return cupy


def bench_screen(table, theta_p_deg, da_window_km, n_epochs=200,
                 use_gpu=True):
    """prereg 8.2: the fixed sub-problem is the `n_epochs` screening epochs
    beginning at the MEDIAN epoch of the regime. Both paths run the identical
    arithmetic; the winner by wall clock runs the full screen."""
    epochs = table["epochs"]
    start = max(0, epochs.size // 2)
    stop = min(epochs.size, start + n_epochs)
    slices = [(int(table["offsets"][k]), int(table["offsets"][k + 1]))
              for k in range(start, stop)]

    def run_cpu():
        t0 = time.time()
        pairs = 0
        for s, e in slices:
            if e - s < 2:
                continue
            a = table["a"][s:e]
            inc = table["inc"][s:e]
            raan = table["raan"][s:e]
            idx = table["object_index"][s:e].astype(np.int64)
            li, ri = screen_epoch_cpu(a, inc, raan, idx, a, inc, raan, idx,
                                      theta_p_deg, da_window_km)
            pairs += int(li.size)
        return time.time() - t0, pairs

    cpu_seconds, cpu_pairs = run_cpu()
    out = {"epochsBenchmarked": len(slices), "cpuSeconds": cpu_seconds,
           "cpuPairs": cpu_pairs, "gpuSeconds": None, "gpuPairs": None,
           "gpuError": None, "winner": "cpu"}
    if not use_gpu:
        out["gpuError"] = "not attempted"
        return out
    try:
        cp = load_cupy()
        # warm the device and the allocator before timing
        _ = cp.asarray(np.zeros(16, dtype=np.float64)).sum()
        cp.cuda.Stream.null.synchronize()
        t0 = time.time()
        pairs = 0
        for s, e in slices:
            if e - s < 2:
                continue
            a = cp.asarray(table["a"][s:e])
            inc = cp.asarray(table["inc"][s:e])
            raan = cp.asarray(table["raan"][s:e])
            idx = cp.asarray(table["object_index"][s:e].astype(np.int64))
            li, ri = screen_epoch_gpu(cp, a, inc, raan, idx, a, inc, raan, idx,
                                      theta_p_deg, da_window_km)
            pairs += int(li.size)
        cp.cuda.Stream.null.synchronize()
        out["gpuSeconds"] = time.time() - t0
        out["gpuPairs"] = pairs
        out["gpuDeviceBytesPeak"] = int(
            cp.get_default_memory_pool().used_bytes())
        out["gpuPoolLimitBytes"] = GPU_POOL_LIMIT_BYTES
        out["winner"] = "gpu" if out["gpuSeconds"] < cpu_seconds else "cpu"
    except Exception as exc:                       # noqa: BLE001
        out["gpuError"] = f"{type(exc).__name__}: {exc}"
    return out


def run_screen(table, theta_p_deg, da_window_km, path="cpu", cp=None,
               progress_every=200):
    """The full screen (prereg 8.1).

    A pair is kept only if it is below theta_p at **two consecutive** screening
    epochs. That filter is provably admissive by the same counting argument
    that fixes the grid step: a dwell of length >= D at a step of D/2 contains
    at least two grid points, and those points are consecutive because the
    dwell is contiguous. It is what keeps the surviving-pair count bounded
    inside constellation shells, where a single-epoch crossing is the normal
    state (prereg 2.4).

    Returns the unique candidate pairs as (object_index_a, object_index_b),
    a <= b.
    """
    epochs = table["epochs"]
    good = set()
    prev = set()
    started = time.time()
    total_hits = 0
    for k in range(epochs.size):
        s = int(table["offsets"][k])
        e = int(table["offsets"][k + 1])
        cur = set()
        if e - s >= 2:
            if path == "gpu":
                a = cp.asarray(table["a"][s:e])
                inc = cp.asarray(table["inc"][s:e])
                raan = cp.asarray(table["raan"][s:e])
                idx = cp.asarray(table["object_index"][s:e].astype(np.int64))
                li, ri = screen_epoch_gpu(cp, a, inc, raan, idx, a, inc, raan,
                                          idx, theta_p_deg, da_window_km)
                li = cp.asnumpy(li)
                ri = cp.asnumpy(ri)
                del a, inc, raan, idx
            else:
                a = table["a"][s:e]
                inc = table["inc"][s:e]
                raan = table["raan"][s:e]
                idx = table["object_index"][s:e].astype(np.int64)
                li, ri = screen_epoch_cpu(a, inc, raan, idx, a, inc, raan, idx,
                                          theta_p_deg, da_window_km)
            if li.size:
                total_hits += int(li.size)
                oi = table["object_index"][s:e]
                lo = oi[li].astype(np.int64)
                hi = oi[ri].astype(np.int64)
                lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
                cur = set(zip(lo.tolist(), hi.tolist()))
        good |= (cur & prev)
        prev = cur
        if progress_every and k % progress_every == 0:
            print(f"    screen epoch {k}/{epochs.size}, {len(good):,} pairs, "
                  f"{time.time()-started:.0f}s", flush=True)
    pairs = (np.asarray(sorted(good), dtype=np.int64) if good
             else np.zeros((0, 2), dtype=np.int64))
    return pairs, {"hits": total_hits, "uniquePairs": int(pairs.shape[0]),
                   "wallSeconds": time.time() - started, "path": path}


# ==========================================================================
# The exact pass: prereg 4, on element-set epochs
# ==========================================================================
def interpolate_slow(src_ms, values, targets_ms, max_gap_days=MAX_GAP_DAYS,
                     angle=False, j2_rate=None):
    """Linear interpolation of a slow element onto `targets_ms`, refused
    across any gap longer than `max_gap_days` (prereg 4.4). Returns
    (values, ok)."""
    src = np.asarray(src_ms, dtype=np.float64)
    tgt = np.asarray(targets_ms, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    if src.size < 2:
        return np.zeros(tgt.size), np.zeros(tgt.size, dtype=bool)
    k = np.clip(np.searchsorted(src, tgt, side="right") - 1, 0, src.size - 2)
    left, right = src[k], src[k + 1]
    gap = (right - left) / DAY_MS
    ok = (gap <= max_gap_days) & (tgt >= src[0]) & (tgt <= src[-1])
    w = np.where(gap > 0, (tgt - left) / np.where(gap > 0, right - left, 1.0), 0.0)
    if angle:
        step = wrap180(v[k + 1] - v[k]) if j2_rate is None else None
        if j2_rate is not None:
            pred = 0.5 * (j2_rate[k] + j2_rate[k + 1]) * gap
            step = pred + wrap180(v[k + 1] - v[k] - pred)
        out = v[k] + w * step
    else:
        out = v[k] + w * (v[k + 1] - v[k])
    return out, ok


def pair_series(el_a, el_b, lo_ms, hi_ms):
    """Evaluate theta, |gamma| and da at A's element-set epochs (prereg 4, 5.1).

    Returns a dict of arrays aligned to A's retained epochs.
    """
    ta = el_a["epoch_ms"].astype(np.float64)
    m = (ta >= lo_ms) & (ta <= hi_ms)
    if not m.any():
        return None
    ta = ta[m]
    a_a = semi_major_axis_km(el_a["n"][m])
    inc_a, raan_a = el_a["inc"][m], el_a["raan"][m]
    argp_a, ma_a, e_a, n_a = el_a["argp"][m], el_a["ma"][m], el_a["e"][m], el_a["n"][m]

    tb = el_b["epoch_ms"].astype(np.float64)
    if tb.size < 2:
        return None
    n_b_series = el_b["n"]
    a_b_series = semi_major_axis_km(n_b_series)
    j2_b = j2_nodal_rate_deg_per_day(a_b_series, el_b["e"], el_b["inc"])

    inc_b, ok1 = interpolate_slow(tb, el_b["inc"], ta)
    raan_b, ok2 = interpolate_slow(tb, el_b["raan"], ta, angle=True, j2_rate=j2_b)
    a_b, ok3 = interpolate_slow(tb, a_b_series, ta)
    e_b, ok4 = interpolate_slow(tb, el_b["e"], ta)
    argp_b, ok5 = interpolate_slow(tb, el_b["argp"], ta, angle=True)
    n_b, _ = interpolate_slow(tb, n_b_series, ta)
    ok = ok1 & ok2 & ok3 & ok4 & ok5
    if not ok.any():
        return None

    theta = plane_separation_deg(inc_a, raan_a, inc_b, raan_b)
    da = a_a - a_b

    # --- the fast angle, prereg 5.1 ---------------------------------------
    kb = np.clip(np.searchsorted(tb, ta), 0, tb.size - 1)
    kb_prev = np.clip(kb - 1, 0, tb.size - 1)
    use_prev = np.abs(ta - tb[kb_prev]) < np.abs(ta - tb[kb])
    kb = np.where(use_prev, kb_prev, kb)
    dt_fast = (ta - tb[kb]) / DAY_MS
    fast_ok = np.abs(dt_fast) <= FAST_ANGLE_MAX_GAP_DAYS
    ma_b = wrap360(el_b["ma"][kb] + 360.0 * n_b_series[kb] * dt_fast)
    nu_a = true_anomaly_deg(ma_a, e_a)
    nu_b = true_anomaly_deg(ma_b, e_b)
    ra = position_unit_vector(inc_a, raan_a, argp_a, nu_a)
    rb = position_unit_vector(inc_b, raan_b, argp_b, nu_b)
    gamma = track_angle_deg(ra, rb)

    # IMPL (prereg 4.5(b)): the relative phase RATE is taken from prereg 2.5's
    # derived relation gamma_dot = k(a) * da rather than from finite
    # differences of gamma, which alias at 15 rev/day. Same quantity, and the
    # only estimator of it that the sampling supports.
    gamma_dot = phase_rate_deg_per_day_per_km(0.5 * (a_a + a_b)) * da

    return {"t_ms": ta, "theta": theta, "gamma": gamma, "gamma_ok": ok & fast_ok,
            "da": da, "gamma_dot": gamma_dot, "ok": ok,
            "inc_a": inc_a, "raan_a": raan_a, "inc_b": inc_b, "raan_b": raan_b,
            "a_a": a_a, "a_b": a_b, "e_a": e_a, "e_b": e_b,
            "argp_a": argp_a, "argp_b": argp_b, "n_a": n_a, "n_b": n_b}


def contiguous_runs(mask):
    mask = np.asarray(mask, dtype=bool)
    if mask.size == 0:
        return []
    d = np.diff(mask.astype(np.int8))
    starts = list(np.nonzero(d == 1)[0] + 1)
    ends = list(np.nonzero(d == -1)[0] + 1)
    if mask[0]:
        starts.insert(0, 0)
    if mask[-1]:
        ends.append(mask.size)
    return list(zip(starts, ends))


def find_dwells(ps, theta_p, gamma_p, d_days, stats=None):
    """prereg 4.4: contiguous intervals of length >= D over which theta <= theta_p
    and |gamma| <= Gamma at every retained epoch, with the occupancy and gap
    requirements."""
    ok = ps["ok"] & ps["gamma_ok"]
    inside = ok & (ps["theta"] <= theta_p) & (ps["gamma"] <= gamma_p)
    t = ps["t_ms"] / DAY_MS
    out = []
    for s, e in contiguous_runs(inside):
        if e - s < 2:
            continue
        length = t[e - 1] - t[s]
        if length < d_days:
            if stats is not None:
                stats["tooShort"] = stats.get("tooShort", 0) + 1
            continue
        gaps = np.diff(t[s:e])
        if gaps.size and gaps.max() > MAX_GAP_DAYS:
            if stats is not None:
                stats["brokenByGap"] = stats.get("brokenByGap", 0) + 1
            continue
        if (e - s) < LOITER_MIN_OCCUPANCY_PER_DAY * length:
            if stats is not None:
                stats["lowOccupancy"] = stats.get("lowOccupancy", 0) + 1
            continue
        out.append((s, e))
    return out


def counterfactual_theta(ps, i0, i1):
    """prereg 4.5(a): the no-manoeuvre counterfactual plane of each object,
    propagated from its own state at t_0 at its OWN J2-predicted nodal rate,
    with inclination held constant."""
    dt = (ps["t_ms"][i1] - ps["t_ms"][i0]) / DAY_MS
    om_a = j2_nodal_rate_deg_per_day(ps["a_a"][i0], ps["e_a"][i0], ps["inc_a"][i0])
    om_b = j2_nodal_rate_deg_per_day(ps["a_b"][i0], ps["e_b"][i0], ps["inc_b"][i0])
    raan_a_cf = ps["raan_a"][i0] + om_a * dt
    raan_b_cf = ps["raan_b"][i0] + om_b * dt
    theta_noA = float(plane_separation_deg(ps["inc_a"][i0], raan_a_cf,
                                           ps["inc_b"][i1], ps["raan_b"][i1]))
    theta_noB = float(plane_separation_deg(ps["inc_a"][i1], ps["raan_a"][i1],
                                           ps["inc_b"][i0], raan_b_cf))
    return theta_noA, theta_noB


def campaign_of(flag_ms, t_a_ms, t_look_days=T_LOOK_DAYS,
                max_gap_days=CAMPAIGN_MAX_GAP_DAYS):
    """prereg 5.5: the contiguous chain of confirmed manoeuvres ending before
    t_a, with no internal gap longer than 180 days. Returns the chain."""
    f = np.asarray([x for x in flag_ms
                    if t_a_ms - t_look_days * DAY_MS <= x < t_a_ms],
                   dtype=np.float64)
    if f.size == 0:
        return f
    f = np.sort(f)
    gaps = np.diff(f) / DAY_MS
    cut = np.nonzero(gaps > max_gap_days)[0]
    start = int(cut[-1]) + 1 if cut.size else 0
    return f[start:]


def evaluate_pair(nd_a, nd_b, el_a, el_b, flags_a, theta_p, gamma_p, d_days,
                  regime, stats=None):
    """The full registered criteria for one ordered pair (prereg 4)."""
    lo = max(el_a["epoch_ms"][0], el_b["epoch_ms"][0])
    hi = min(el_a["epoch_ms"][-1], el_b["epoch_ms"][-1])
    if hi - lo < d_days * DAY_MS:
        return []
    ps = pair_series(el_a, el_b, lo, hi)
    if ps is None:
        return []
    events = []
    for s, e in find_dwells(ps, theta_p, gamma_p, d_days, stats):
        t_a_ms = float(ps["t_ms"][s])
        t_e_ms = float(ps["t_ms"][e - 1])
        look_lo = t_a_ms - T_LOOK_DAYS * DAY_MS
        pre = np.nonzero((ps["t_ms"] >= look_lo) & (ps["t_ms"] < t_a_ms)
                         & ps["ok"])[0]
        if pre.size == 0:
            if stats is not None:
                stats["noLookback"] = stats.get("noLookback", 0) + 1
            continue
        far = pre[(ps["theta"][pre] >= THETA_FAR_DEG)
                  | ((ps["gamma"][pre] >= GAMMA_FAR_DEG) & ps["gamma_ok"][pre])]
        if far.size == 0:
            if stats is not None:
                stats["standingPair"] = stats.get("standingPair", 0) + 1
            continue
        i0 = int(far[-1])
        theta_a = float(ps["theta"][s])

        def attribute(i_start):
            theta_start = float(ps["theta"][i_start])
            c = theta_start - theta_a
            noa, nob = counterfactual_theta(ps, i_start, s)
            ca, cb = noa - theta_a, nob - theta_a
            if c <= 0:
                return "natural", c, ca, cb
            a_ok = ca >= ATTRIBUTION_SHARE * c
            b_ok = cb >= ATTRIBUTION_SHARE * c
            if a_ok and b_ok:
                return "ambiguous", c, ca, cb
            if a_ok:
                return "approacher", c, ca, cb
            if b_ok:
                return "target", c, ca, cb
            return "natural", c, ca, cb

        attribution, C, C_A, C_B = attribute(i0)
        theta_0 = float(ps["theta"][i0])

        # ADDED AT IMPLEMENTATION TIME, NOT REGISTERED, and labelled as such
        # everywhere it is reported. The registered t_0 of prereg 4.5 is the
        # last epoch at which EITHER the plane or the phase was far, and in a
        # J2-assisted campaign the phase is far until the final arrest burn --
        # so the registered counterfactual window can open AFTER the plane has
        # already closed, and then C <= 0 and the closure is attributed to
        # nature by construction. This variant re-runs the identical
        # counterfactual from the last epoch at which the PLANE alone was far.
        # It changes no registered verdict and is offered as the T8c
        # recommendation, in the manner of T8a's section 7.4.
        far_plane = pre[ps["theta"][pre] >= THETA_FAR_DEG]
        if far_plane.size:
            i0p = int(far_plane[-1])
            attribution_plane, C_p, C_Ap, C_Bp = attribute(i0p)
            t0_plane_ms = float(ps["t_ms"][i0p])
        else:
            attribution_plane, C_p, C_Ap, C_Bp = "no-plane-separation", 0.0, 0.0, 0.0
            t0_plane_ms = None
        if stats is not None:
            stats[f"attr_{attribution}"] = stats.get(f"attr_{attribution}", 0) + 1

        seg = slice(i0, s + 1)
        gd = np.abs(ps["gamma_dot"][seg])
        gd_max = float(gd.max()) if gd.size else 0.0
        last10 = ps["t_ms"][seg] >= (t_a_ms - 10.0 * DAY_MS)
        gd_last = float(np.median(np.abs(ps["gamma_dot"][seg][last10]))) \
            if last10.any() else gd_max
        phase_arrested = bool(gd_max > 0 and gd_last <= PHASE_ARREST_RATIO * gd_max)

        chain = campaign_of(flags_a["all_ms"], t_a_ms)
        plane_chain = campaign_of(flags_a["plane_ms"], t_a_ms)
        corroborated = bool(chain.size > 0
                            and (C <= theta_p or plane_chain.size > 0))
        if chain.size:
            t_conf = float(chain[0])
            idx_first = np.searchsorted(el_a["epoch_ms"].astype(np.float64), t_conf)
            t_first = float(el_a["epoch_ms"][max(0, idx_first - 1)])
            lead_causal = (t_a_ms - t_conf) / DAY_MS
            lead_ideal = (t_a_ms - t_first) / DAY_MS
        else:
            t_conf = None
            lead_causal = None
            lead_ideal = None
        plane_hit = np.nonzero((ps["theta"][:s + 1] <= theta_p) & ps["ok"][:s + 1]
                               & (ps["t_ms"][:s + 1] >= ps["t_ms"][i0]))[0]
        t_plane = float(ps["t_ms"][plane_hit[0]]) if plane_hit.size else t_a_ms
        depart = np.nonzero((ps["t_ms"] > t_e_ms)
                            & ((ps["theta"] >= THETA_FAR_DEG)
                               | ((ps["gamma"] >= GAMMA_FAR_DEG) & ps["gamma_ok"])))[0]

        dwell = slice(s, e)
        events.append({
            "regime": regime, "approacher": int(nd_a), "target": int(nd_b),
            "thetaP": theta_p, "gamma": gamma_p, "dDays": d_days,
            "arrivalMs": t_a_ms, "arrival": iso(t_a_ms),
            "endMs": t_e_ms, "end": iso(t_e_ms),
            "dwellDays": (t_e_ms - t_a_ms) / DAY_MS,
            "dwellSamples": int(e - s),
            "closestThetaDeg": float(ps["theta"][dwell].min()),
            "medianThetaDeg": float(np.median(ps["theta"][dwell])),
            "closestGammaDeg": float(ps["gamma"][dwell].min()),
            "medianGammaDeg": float(np.median(ps["gamma"][dwell])),
            "medianAbsDaKm": float(np.median(np.abs(ps["da"][dwell]))),
            "meanAKm": float(np.mean(0.5 * (ps["a_a"][dwell] + ps["a_b"][dwell]))),
            "apsidalSeparationDeg": float(np.median(
                np.abs(wrap180(ps["argp_a"][dwell] - ps["argp_b"][dwell])))),
            "eccApproacher": float(np.median(ps["e_a"][dwell])),
            "eccTarget": float(np.median(ps["e_b"][dwell])),
            "campaignStartMs": float(ps["t_ms"][i0]),
            "campaignStart": iso(ps["t_ms"][i0]),
            "campaignDays": (t_a_ms - ps["t_ms"][i0]) / DAY_MS,
            "thetaAtCampaignStartDeg": theta_0,
            "planeClosureDeg": C,
            "closureAttributableToApproacherDeg": C_A,
            "closureAttributableToTargetDeg": C_B,
            "attribution": attribution,
            "attributionPlaneOnlyVariant": attribution_plane,
            "planeOnlyT0Ms": t0_plane_ms,
            "planeClosureDegPlaneOnlyVariant": C_p,
            "closureAttributableToApproacherDegPlaneOnlyVariant": C_Ap,
            "closureAttributableToTargetDegPlaneOnlyVariant": C_Bp,
            "phaseArrested": phase_arrested,
            "phaseRateMaxDegPerDay": gd_max,
            "phaseRateFinalDegPerDay": gd_last,
            "manoeuvresInCampaign": int(chain.size),
            "planeManoeuvresInCampaign": int(plane_chain.size),
            "corroborated": corroborated,
            "initiatingConfirmMs": t_conf,
            "initiatingConfirm": iso(t_conf) if t_conf else None,
            "leadCausalDays": lead_causal,
            "leadIdealDays": lead_ideal,
            "leadPlaneMatchDays": (t_a_ms - t_plane) / DAY_MS,
            "departureMs": float(ps["t_ms"][depart[0]]) if depart.size else None,
            "departure": iso(ps["t_ms"][depart[0]]) if depart.size else None,
        })
    return events


# ==========================================================================
# prereg 6 -- nulls and controls; prereg 10 -- gates; the analyze driver
# ==========================================================================
def stratum_of(a_km, inc_deg, regime):
    """prereg 6.1(b): regime x inclination band (10 deg) x altitude band
    (100 km at LEO, 1000 km at MEO and HEO)."""
    band = 100.0 if regime == "LEO" else 1000.0
    return (int(np.floor(inc_deg / 10.0)),
            int(np.floor((a_km - EARTH_RADIUS_KM) / band)))


def analytic_j2_null(pairs_rates, theta_p, d_days, exposure_days):
    """prereg 6.1(a): expected chance co-planar windows of dwell >= D, from
    each pair's OWN fitted nodal rates."""
    total = 0.0
    contributing = 0
    for inc_a, inc_b, d_omega_dot, exposure in pairs_rates:
        dwell = chance_coplanar_dwell_days(theta_p, inc_a, inc_b, d_omega_dot)
        if dwell == 0.0:
            continue
        if dwell < d_days:
            continue
        contributing += 1
        if math.isinf(dwell):
            total += 1.0          # permanently co-planar: one standing window
        else:
            total += exposure * chance_coplanar_rate_per_day(d_omega_dot)
    return {"expectedWindows": total, "contributingPairs": contributing,
            "exposureDays": exposure_days}


def load_flags(work):
    raw = json.loads((Path(work) / "detect-flags.json").read_text())
    out = {}
    for k, v in raw.items():
        intrack = np.asarray(v["intrack_ms"], dtype=np.float64)
        plane = np.asarray(v["plane_ms"], dtype=np.float64)
        allf = np.sort(np.concatenate((intrack, plane))) if (
            intrack.size or plane.size) else np.asarray([], dtype=np.float64)
        out[int(k)] = {"intrack_ms": intrack, "plane_ms": plane, "all_ms": allf}
    return out


def classify_arms(ev):
    """prereg 4.7. Arm G = criteria 1,2,3(a),3(b); arm M = arm G + 3(c).

    The `*Variant` pair applies the identical rule to the plane-only
    counterfactual window added at implementation time (see `evaluate_pair`);
    it is labelled everywhere it is reported and is in no registered headline.
    """
    arm_g = ev["attribution"] == "approacher" and ev["phaseArrested"]
    arm_m = arm_g and ev["corroborated"]
    arm_gv = (ev["attributionPlaneOnlyVariant"] == "approacher"
              and ev["phaseArrested"])
    arm_mv = arm_gv and ev["corroborated"]
    return arm_g, arm_m, arm_gv, arm_mv


def summarise_events(events, key):
    return percentiles([e[key] for e in events])


def analyze(work, db, regime, theta_p, gamma_p, d_days, out_prefix,
            gpu_ok=True, max_pairs=None, label="primary"):
    started = time.time()
    cache = Cache(work).open()
    flags = load_flags(work)
    summary = {int(k): v for k, v in json.loads(
        (Path(work) / "detect-summary.json").read_text()).items()}
    meta = {int(k): v for k, v in json.loads(
        (Path(work) / "object-meta.json").read_text()).items()}
    detect_meta = json.loads((Path(work) / "detect-meta.json").read_text())

    step = screen_grid_step_days(d_days)
    print(f"  building screen table ({regime}, step {step} d) ...", flush=True)
    table = build_screen_table(work, regime, step)
    if table is None:
        return None
    a_ref = float(np.median(table["a"]))
    da_window = screen_da_window_km(gamma_p, d_days, a_ref)
    print(f"  screen table: {table['epochs'].size} epochs, "
          f"{table['a'].size:,} object-epochs, da window {da_window:.4f} km "
          f"(reference a {a_ref:.1f} km), {time.time()-started:.0f}s", flush=True)

    bench = bench_screen(table, theta_p, da_window, use_gpu=gpu_ok)
    print("  CPU/GPU benchmark: " + json.dumps(bench), flush=True)
    cp = None
    path = bench["winner"]
    if path == "gpu":
        cp = load_cupy()
    pairs, screen_meta = run_screen(table, theta_p, da_window, path=path, cp=cp)
    print("  screen: " + json.dumps(screen_meta), flush=True)

    objects = table["objects"]
    never = set()
    payload = set()
    payload_plane = set()
    for nd, s in summary.items():
        lbl = class_label(meta.get(nd, {}).get("objectType"))
        if lbl == "payload":
            payload.add(nd)
            if s["nPlane"]:
                payload_plane.add(nd)
        if (not s["nIntrack"] and not s["nPlane"]
                and s["elementSets"] >= CONTROL_MIN_ELEMENT_SETS
                and s["spanDays"] >= CONTROL_MIN_SPAN_DAYS):
            never.add(nd)

    # exposure in object-days on the daily grid, per class (prereg 6.2)
    g = load_grid(work, regime)
    gn = np.asarray(g["norad"])
    uniq, counts = np.unique(gn, return_counts=True)
    exposure = {int(u): int(c) for u, c in zip(uniq, counts)}
    exp_never = sum(exposure.get(n, 0) for n in never)
    exp_payload = sum(exposure.get(n, 0) for n in payload)
    exp_cat_passive = sum(
        exposure.get(n, 0) for n in summary
        if class_label(meta.get(n, {}).get("objectType")) == "catalogue_passive")

    if max_pairs is not None and pairs.shape[0] > max_pairs:
        rng = np.random.default_rng(SEED)
        keep = rng.choice(pairs.shape[0], size=max_pairs, replace=False)
        pairs = pairs[np.sort(keep)]
        screen_meta["pairsSubsampledTo"] = int(max_pairs)

    stats = {}
    events = []
    t_eval = time.time()
    el_cache = {}

    def elements_of(nd):
        if nd not in el_cache:
            if len(el_cache) > 4096:
                el_cache.clear()
            el_cache[nd] = cache.elements(nd)
        return el_cache[nd]

    for k, (ia, ib) in enumerate(pairs):
        nd_a, nd_b = int(objects[ia]), int(objects[ib])
        el_a, el_b = elements_of(nd_a), elements_of(nd_b)
        if el_a is None or el_b is None:
            continue
        raw = evaluate_pair(nd_a, nd_b, el_a, el_b,
                            flags.get(nd_a, {"all_ms": np.asarray([]),
                                             "plane_ms": np.asarray([])}),
                            theta_p, gamma_p, d_days, regime, stats)
        for ev in raw:
            if ev["attribution"] == "target":
                # the object whose elements changed is the approacher
                sw = evaluate_pair(nd_b, nd_a, el_b, el_a,
                                   flags.get(nd_b, {"all_ms": np.asarray([]),
                                                    "plane_ms": np.asarray([])}),
                                   theta_p, gamma_p, d_days, regime, None)
                for e2 in sw:
                    if abs(e2["arrivalMs"] - ev["arrivalMs"]) < 2 * DAY_MS:
                        events.append(e2)
                continue
            events.append(ev)
        if k and k % 5000 == 0:
            print(f"    pairs {k:,}/{pairs.shape[0]:,}, {len(events):,} raw "
                  f"events, {time.time()-t_eval:.0f}s", flush=True)

    for ev in events:
        nd = ev["approacher"]
        ev["approacherClass"] = ("never_manoeuvred" if nd in never else
                                 ("payload" if nd in payload else "other"))
        ev["approacherObjectType"] = meta.get(nd, {}).get("objectType")
        ev["approacherName"] = meta.get(nd, {}).get("name")
        ev["approacherRegistry"] = meta.get(nd, {}).get("country")
        ev["approacherLaunchDate"] = meta.get(nd, {}).get("launchDate")
        ev["targetObjectType"] = meta.get(ev["target"], {}).get("objectType")
        ev["targetName"] = meta.get(ev["target"], {}).get("name")
        ev["targetRegistry"] = meta.get(ev["target"], {}).get("country")
        ev["targetLaunchDate"] = meta.get(ev["target"], {}).get("launchDate")
        (ev["armG"], ev["armM"],
         ev["armGVariant"], ev["armMVariant"]) = classify_arms(ev)

    arm_g = [e for e in events if e["armG"]]
    arm_m = [e for e in events if e["armM"]]
    arm_gv = [e for e in events if e["armGVariant"]]
    arm_mv = [e for e in events if e["armMVariant"]]

    def rate(evs, cls, exp):
        k = len({(e["approacher"], round(e["arrivalMs"])) for e in evs
                 if e["approacherClass"] == cls})
        return {"events": k, "exposureObjectDays": exp,
                "perObjectDay": (k / exp) if exp else None,
                "wilson95": wilson(k, exp) if exp else (None, None)}

    control = {
        "armG": {"neverManoeuvred": rate(arm_g, "never_manoeuvred", exp_never),
                 "payload": rate(arm_g, "payload", exp_payload)},
        "armM": {"neverManoeuvred": rate(arm_m, "never_manoeuvred", exp_never),
                 "payload": rate(arm_m, "payload", exp_payload)},
        "cataloguePassiveExposureObjectDays": exp_cat_passive,
    }
    gn_rate = control["armG"]["neverManoeuvred"]["perObjectDay"]
    gp_rate = control["armG"]["payload"]["perObjectDay"]
    control["armGLeakRatio"] = (gn_rate / gp_rate) if (gn_rate and gp_rate) else None

    leads = [e["leadCausalDays"] for e in arm_m]
    have = [x for x in leads if x is not None]
    censored = [T_LOOK_DAYS if x is None else x for x in leads]
    cens_flag = [x is None for x in leads]
    km = kaplan_meier(censored, cens_flag) if leads else []
    lead_block = {
        "armMEvents": len(arm_m),
        "withInitiatingManoeuvre": len(have),
        "withInitiatingFraction": (len(have) / len(arm_m)) if arm_m else None,
        "percentiles": percentiles(have),
        "kaplanMeierMedian": km_quantile(km, 0.5) if km else None,
        "kaplanMeierP25": km_quantile(km, 0.25) if km else None,
        "kaplanMeierP75": km_quantile(km, 0.75) if km else None,
        "atOrBeyondWall": sum(1 for x in censored if x >= GATE_F_WALL_DAYS),
        "curve": km[:400],
        "leadPlaneMatch": percentiles([e["leadPlaneMatchDays"] for e in arm_m]),
        "leadIdeal": percentiles([e["leadIdealDays"] for e in arm_m
                                  if e["leadIdealDays"] is not None]),
    }

    variant_leads = [e["leadCausalDays"] for e in arm_mv]
    v_have = [x for x in variant_leads if x is not None]
    v_cens = [T_LOOK_DAYS if x is None else x for x in variant_leads]
    v_flag = [x is None for x in variant_leads]
    v_km = kaplan_meier(v_cens, v_flag) if variant_leads else []
    variant_block = {
        "note": ("ADDED AT IMPLEMENTATION TIME, NOT REGISTERED. The registered "
                 "t_0 of prereg 4.5 opens the counterfactual window at the last "
                 "epoch at which EITHER the plane or the phase was far; this "
                 "variant opens it at the last epoch at which the PLANE alone "
                 "was far. It is in no registered headline."),
        "armG": len(arm_gv), "armM": len(arm_mv),
        "distinctApproachersArmM": len({e["approacher"] for e in arm_mv}),
        "distinctTargetsArmM": len({e["target"] for e in arm_mv}),
        "withInitiatingManoeuvre": len(v_have),
        "leadPercentiles": percentiles(v_have),
        "kaplanMeierMedian": km_quantile(v_km, 0.5) if v_km else None,
        "kaplanMeierP25": km_quantile(v_km, 0.25) if v_km else None,
        "kaplanMeierP75": km_quantile(v_km, 0.75) if v_km else None,
        "atOrBeyondWall": sum(1 for x in v_cens if x >= GATE_F_WALL_DAYS),
        "curve": v_km[:400],
        "leadPlaneMatch": percentiles([e["leadPlaneMatchDays"] for e in arm_mv]),
        "distributions": {k: summarise_events(arm_mv, k) for k in
                          ("dwellDays", "closestThetaDeg", "medianThetaDeg",
                           "closestGammaDeg", "medianGammaDeg",
                           "medianAbsDaKm", "campaignDays", "planeClosureDeg",
                           "apsidalSeparationDeg")} if arm_mv else {},
        "control": {
            "neverManoeuvred": rate(arm_gv, "never_manoeuvred", exp_never),
            "payload": rate(arm_gv, "payload", exp_payload)},
    }

    out = {
        "label": label, "regime": regime,
        "thresholds": {"thetaPDeg": theta_p, "gammaDeg": gamma_p,
                       "dDays": d_days, "thetaFarDeg": THETA_FAR_DEG,
                       "gammaFarDeg": GAMMA_FAR_DEG,
                       "tLookDays": T_LOOK_DAYS,
                       "daWindowKm": da_window,
                       "phaseConfinementDaKm": phase_confinement_da_km(
                           gamma_p, d_days, a_ref),
                       "crossTrackKmAtRef": float(cross_track_km(theta_p, REF_LEO_A_KM)),
                       "alongTrackKmAtRef": float(
                           cross_track_km(gamma_p, REF_LEO_A_KM))},
        "screen": screen_meta, "benchmark": bench,
        "rejections": stats,
        "counts": {
            "rawEvents": len(events),
            "armG": len(arm_g), "armM": len(arm_m),
            "attribution": {k.replace("attr_", ""): v for k, v in stats.items()
                            if k.startswith("attr_")},
            "standingPairs": stats.get("standingPair", 0),
            "distinctApproachersArmM": len({e["approacher"] for e in arm_m}),
            "distinctTargetsArmM": len({e["target"] for e in arm_m}),
            "distinctApproachersArmG": len({e["approacher"] for e in arm_g}),
        },
        "distributions": {
            k: summarise_events(arm_m, k) for k in
            ("dwellDays", "closestThetaDeg", "medianThetaDeg",
             "closestGammaDeg", "medianGammaDeg", "medianAbsDaKm",
             "campaignDays", "planeClosureDeg", "apsidalSeparationDeg")
        } if arm_m else {},
        "leadTime": lead_block,
        "control": control,
        "planeOnlyVariant": variant_block,
        "exposure": {"neverManoeuvredObjectDays": exp_never,
                     "payloadObjectDays": exp_payload,
                     "neverManoeuvredObjects": len(never),
                     "payloadObjects": len(payload),
                     "payloadWithPlaneManoeuvre": len(payload_plane)},
        "calibration": detect_meta,
        "wallSeconds": time.time() - started,
    }
    with open(f"{out_prefix}-events.jsonl", "w") as fh:
        for ev in sorted(events, key=lambda e: e["arrivalMs"]):
            fh.write(json.dumps(ev) + "\n")
    Path(f"{out_prefix}-summary.json").write_text(json.dumps(out, indent=2))
    return out


# ==========================================================================
# prereg 5.8, 6.1, 6.3, 10 -- precision, nulls, the two arm-M validations,
# the dwell-bound validation, and the gate ledger
# ==========================================================================
def plane_change_alerts(flags, meta, regime_objects):
    """prereg 5.8: every CAMPAIGN-INITIATING confirmed plane-type manoeuvre of
    a payload-class object is a plane-change alert.

    IMPL: the registration's alert is a plane manoeuvre that "begins a
    campaign closing at least theta_far - theta_p against ANY object". Testing
    that literally is an all-vs-all over the whole catalogue, which is exactly
    the scope prereg 3.3 declines and prereg 11 hands to a cluster. What is
    counted here is the campaign-initiating plane manoeuvre itself -- the
    observable a watching operator actually has, and the same denominator an
    alarm lane would raise -- and the substitution is stated in the results
    document rather than hidden. A campaign is a chain of confirmed manoeuvres
    with no internal gap longer than 180 days (prereg 5.5).
    """
    alerts = 0
    objects = 0
    for nd in regime_objects:
        if class_label(meta.get(nd, {}).get("objectType")) != "payload":
            continue
        pl = flags.get(nd, {}).get("plane_ms")
        if pl is None or pl.size == 0:
            continue
        objects += 1
        pl = np.sort(pl)
        alerts += 1 + int((np.diff(pl) / DAY_MS > CAMPAIGN_MAX_GAP_DAYS).sum())
    return {"alerts": alerts, "objectsRaisingAnAlert": objects}


def detector_false_alarm_rate(summary, meta, regime):
    """prereg 6.3(a): the manoeuvre detector's own flag rate on objects that
    physically cannot manoeuvre.

    IMPL: the registration asks for a leave-one-out re-derivation of the
    never-manoeuvred class. That class is DEFINED by having no flag, so its
    flag rate is zero by construction and a leave-one-out does not change it --
    the same tautology prereg 4.7 warns about for arm M. The measurement that
    is not a tautology, and the one reported, is the flag rate on the
    catalogue-passive class (DEBRIS and ROCKET BODY). It is an UPPER bound on
    the false-alarm rate, because some rocket bodies do perform disposal
    burns, and it is labelled as such everywhere it appears.
    """
    obj_years = 0.0
    flagged = 0
    n_objects = 0
    total_flags = 0
    for nd, s in summary.items():
        if class_label(meta.get(nd, {}).get("objectType")) != "catalogue_passive":
            continue
        if regime not in s.get("regimes", ()):
            continue
        if (s["elementSets"] < CONTROL_MIN_ELEMENT_SETS
                or s["spanDays"] < CONTROL_MIN_SPAN_DAYS):
            continue
        n_objects += 1
        obj_years += s["spanDays"] / 365.25
        total_flags += s["nIntrack"] + s["nPlane"]
        if s["nIntrack"] or s["nPlane"]:
            flagged += 1
    return {
        "population": "catalogue_passive (DEBRIS, ROCKET BODY) -- an UPPER bound",
        "objects": n_objects, "objectYears": obj_years,
        "objectsWithAnyFlag": flagged,
        "objectsWithAnyFlagFraction": (flagged / n_objects) if n_objects else None,
        "flags": total_flags,
        "flagsPerObjectYear": (total_flags / obj_years) if obj_years else None,
    }


def campaign_rate_per_object_year(summary, meta, flags, regime):
    """The denominator gate H compares the false-alarm rate to."""
    obj_years = 0.0
    campaigns = 0
    for nd, s in summary.items():
        if class_label(meta.get(nd, {}).get("objectType")) != "payload":
            continue
        if regime not in s.get("regimes", ()):
            continue
        obj_years += s["spanDays"] / 365.25
        pl = flags.get(nd, {}).get("plane_ms")
        if pl is not None and pl.size:
            campaigns += 1 + int(
                (np.diff(np.sort(pl)) / DAY_MS > CAMPAIGN_MAX_GAP_DAYS).sum())
    return {"objectYears": obj_years, "campaigns": campaigns,
            "campaignsPerObjectYear": (campaigns / obj_years) if obj_years else None}


def object_epoch_index(table):
    """Per-object views of the screening table, so a pair's shared epochs can
    be intersected without rescanning the table."""
    order = np.lexsort((table["epoch_index"], table["object_index"]))
    oi = table["object_index"][order]
    ep = table["epoch_index"][order]
    inc = table["inc"][order]
    raan = table["raan"][order]
    a = table["a"][order]
    bounds = np.nonzero(np.diff(oi))[0] + 1
    starts = np.concatenate(([0], bounds))
    ends = np.concatenate((bounds, [oi.size]))
    out = {}
    for s, e in zip(starts, ends):
        out[int(oi[s])] = {"epoch": ep[s:e], "inc": inc[s:e],
                           "raan": raan[s:e], "a": a[s:e]}
    return out


def pair_grid_dwell_days(idx, oi_a, oi_b, theta_p, step_days):
    """Longest run of consecutive screening epochs below theta_p, in days."""
    va, vb = idx.get(oi_a), idx.get(oi_b)
    if va is None or vb is None:
        return None
    common, ia, ib = np.intersect1d(va["epoch"], vb["epoch"],
                                    return_indices=True)
    if common.size < 2:
        return None
    theta = plane_separation_deg(va["inc"][ia], va["raan"][ia],
                                 vb["inc"][ib], vb["raan"][ib])
    inside = theta <= theta_p
    best = 0.0
    for s, e in contiguous_runs(inside):
        if e - s < 2:
            continue
        span = common[e - 1] - common[s]
        if np.all(np.diff(common[s:e]) == 1):
            best = max(best, float(span))
        else:
            # keep only the contiguous sub-runs of the epoch index
            brk = np.nonzero(np.diff(common[s:e]) != 1)[0]
            prev = s
            for b in list(brk + s + 1) + [e]:
                if b - prev >= 2:
                    best = max(best, float(common[b - 1] - common[prev]))
                prev = b
    return best * step_days if best > 0 else None


def dwell_bound_validation(idx, pairs, objects, own_omegadot, never,
                           theta_p, d_days, step_days, limit=400000):
    """prereg 10 gate G: more than 5% of held-out never-manoeuvred pairs
    exceeding their OWN-history chance-co-planarity dwell bound falsifies the
    bound -- the explicit non-repeat of T8a's section 7.2, where a bound
    derived from a NOMINAL quantity was falsified 5 times out of 5.

    The observed dwell is measured on the D/2 screening grid and is therefore
    a LOWER bound on the true dwell, so this test can only UNDER-report
    exceedances: a verdict of 'not falsified' is the weaker claim and is
    labelled as such.
    """
    tested = exceed = 0
    ratios = []
    infinite = 0
    for ia, ib in pairs[:limit]:
        nd_a, nd_b = int(objects[ia]), int(objects[ib])
        if nd_a not in never or nd_b not in never:
            continue
        va, vb = idx.get(int(ia)), idx.get(int(ib))
        if va is None or vb is None or va["inc"].size == 0 or vb["inc"].size == 0:
            continue
        i_a = float(np.median(va["inc"]))
        i_b = float(np.median(vb["inc"]))
        d_rate = own_omegadot.get(nd_a, 0.0) - own_omegadot.get(nd_b, 0.0)
        bound = chance_coplanar_dwell_days(theta_p, i_a, i_b, d_rate)
        if bound == 0.0:
            continue
        if math.isinf(bound):
            infinite += 1
            continue
        obs = pair_grid_dwell_days(idx, int(ia), int(ib), theta_p, step_days)
        if obs is None:
            continue
        tested += 1
        ratios.append(obs / bound)
        if obs > bound:
            exceed += 1
    return {"pairsTested": tested, "exceeding": exceed,
            "exceedingFraction": (exceed / tested) if tested else None,
            "wilson95": wilson(exceed, tested) if tested else (None, None),
            "pairsWithAZeroRelativeNodalRate": infinite,
            "observedOverBound": percentiles(ratios),
            "note": ("observed dwell measured on the D/2 screening grid is a "
                     "LOWER bound on the true dwell, so this test can only "
                     "under-report exceedances")}


def time_shuffled_corroboration(events, flags, n_draws=N_TIME_SHUFFLES,
                                seed=SEED):
    """prereg 6.3(b): re-run arm M's corroboration criterion with each
    approacher's manoeuvre epochs shifted by a random offset, preserving every
    object's manoeuvre RATE and TYPE MIX exactly while destroying the causal
    link to the closure. If the shuffled yield sits inside the 95% interval of
    the real one, the corroboration criterion is decorative."""
    rng = np.random.default_rng(seed)
    arm_g = [e for e in events if e["armG"]]
    real = sum(1 for e in arm_g if e["corroborated"])
    counts = []
    for _ in range(n_draws):
        k = 0
        for e in arm_g:
            f = flags.get(e["approacher"])
            if f is None:
                continue
            shift = rng.uniform(-T_LOOK_DAYS, T_LOOK_DAYS) * DAY_MS
            lo, hi = e["campaignStartMs"], e["arrivalMs"]
            allf = f["all_ms"] + shift
            planef = f["plane_ms"] + shift
            chain = np.any((allf >= lo) & (allf < hi))
            needs_plane = e["planeClosureDeg"] > e["thetaP"]
            plane_ok = (not needs_plane) or bool(
                np.any((planef >= lo) & (planef < hi)))
            if chain and plane_ok:
                k += 1
        counts.append(k)
    counts = np.asarray(counts, dtype=np.float64)
    return {"armGEvents": len(arm_g), "realCorroborated": real,
            "shuffledMean": float(counts.mean()) if counts.size else None,
            "shuffled95": [float(np.percentile(counts, 2.5)),
                           float(np.percentile(counts, 97.5))]
            if counts.size else None,
            "draws": int(n_draws),
            "realInsideShuffledInterval": bool(
                counts.size and np.percentile(counts, 2.5) <= real
                <= np.percentile(counts, 97.5))}


def analytic_j2_null(idx, pairs, objects, own_omegadot, theta_p, d_days,
                     step_days, limit=400000):
    """prereg 6.1(a): the derived expectation, per pair, from each object's OWN
    fitted nodal rate -- never from a nominal rate at a nominal altitude."""
    total = 0.0
    contributing = 0
    permanent = 0
    for ia, ib in pairs[:limit]:
        va, vb = idx.get(int(ia)), idx.get(int(ib))
        if va is None or vb is None or va["inc"].size == 0 or vb["inc"].size == 0:
            continue
        i_a = float(np.median(va["inc"]))
        i_b = float(np.median(vb["inc"]))
        d_rate = (own_omegadot.get(int(objects[ia]), 0.0)
                  - own_omegadot.get(int(objects[ib]), 0.0))
        dwell = chance_coplanar_dwell_days(theta_p, i_a, i_b, d_rate)
        if dwell == 0.0 or dwell < d_days:
            continue
        common = np.intersect1d(va["epoch"], vb["epoch"])
        exposure = float(common.size * step_days)
        contributing += 1
        if math.isinf(dwell):
            permanent += 1
            total += 1.0
        else:
            total += exposure * chance_coplanar_rate_per_day(d_rate)
    return {"expectedChanceCoplanarWindows": total,
            "contributingPairs": contributing,
            "permanentlyCoplanarPairs": permanent,
            "pairsConsidered": int(min(limit, pairs.shape[0]))}


def permutation_null(work, cache, table, idx, pairs, objects, events, flags,
                     meta, theta_p, gamma_p, d_days, regime,
                     n_permutations=N_PERMUTATIONS, seed=SEED):
    """prereg 6.1(b): each real arrival keeps its approacher and its entire
    element history; only the TARGET is redrawn, from the objects present at
    that epoch in the same stratum (regime x inclination band x altitude
    band), so the crowding, the shell structure and therefore the natural
    differential-J2 dynamics are preserved."""
    rng = np.random.default_rng(seed)
    epochs = table["epochs"]
    # stratum membership per screening epoch
    by_epoch = {}
    for k in range(epochs.size):
        s = int(table["offsets"][k])
        e = int(table["offsets"][k + 1])
        if e <= s:
            continue
        by_epoch[k] = (table["object_index"][s:e],
                       table["a"][s:e], table["inc"][s:e])

    arrivals = [e for e in events if e["armG"]]
    if not arrivals:
        return {"arrivals": 0, "note": "no arm-G arrival to permute"}
    obj_pos = {int(o): i for i, o in enumerate(objects)}
    counts = []
    gaps = 0
    el_cache = {}

    def elements_of(nd):
        if nd not in el_cache:
            if len(el_cache) > 2048:
                el_cache.clear()
            el_cache[nd] = cache.elements(nd)
        return el_cache[nd]

    pools = []
    for ev in arrivals:
        nd_a = ev["approacher"]
        oi_a = obj_pos.get(nd_a)
        day = int(ev["arrivalMs"] // DAY_MS)
        k = int(np.clip(np.searchsorted(epochs, day), 0, epochs.size - 1))
        pool = []
        if k in by_epoch and oi_a is not None:
            oi, aa, ii = by_epoch[k]
            here = np.nonzero(oi == oi_a)[0]
            if here.size:
                st = stratum_of(float(aa[here[0]]), float(ii[here[0]]), regime)
                cand = [int(o) for o, a_, i_ in zip(oi, aa, ii)
                        if stratum_of(float(a_), float(i_), regime) == st
                        and int(o) != oi_a]
                pool = cand
        if len(pool) < 10:
            gaps += 1
            pool = []
        pools.append((ev, pool))

    labelled_gap = sum(1 for _, p in pools if not p)
    stats = {}
    for _ in range(n_permutations):
        k = 0
        for ev, pool in pools:
            if not pool:
                continue
            nd_a = ev["approacher"]
            nd_b = int(objects[pool[rng.integers(len(pool))]])
            if nd_b == nd_a:
                continue
            el_a, el_b = elements_of(nd_a), elements_of(nd_b)
            if el_a is None or el_b is None:
                continue
            lo = ev["arrivalMs"] - T_LOOK_DAYS * DAY_MS
            hi = ev["arrivalMs"] + 2.0 * d_days * DAY_MS
            el_aw = _window(el_a, lo, hi)
            el_bw = _window(el_b, lo, hi)
            if el_aw is None or el_bw is None:
                continue
            got = evaluate_pair(nd_a, nd_b, el_aw, el_bw,
                                flags.get(nd_a, {"all_ms": np.asarray([]),
                                                 "plane_ms": np.asarray([])}),
                                theta_p, gamma_p, d_days, regime, stats)
            for g in got:
                gg, _, _, _ = classify_arms(g)
                if gg:
                    k += 1
                    break
        counts.append(k)
    counts = np.asarray(counts, dtype=np.float64)
    observed = len(arrivals)
    return {
        "permutations": int(n_permutations),
        "arrivalsPermuted": len(arrivals),
        "arrivalsWithATooThinStratum_labelledGap": labelled_gap,
        "observedArmG": observed,
        "nullMean": float(counts.mean()) if counts.size else None,
        "null95": [float(np.percentile(counts, 2.5)),
                   float(np.percentile(counts, 97.5))] if counts.size else None,
        "permutationsAtOrAboveObserved": int((counts >= observed).sum()),
        "observedInsideNull95": bool(
            counts.size and np.percentile(counts, 2.5) <= observed
            <= np.percentile(counts, 97.5)),
    }


def _window(el, lo_ms, hi_ms):
    m = (el["epoch_ms"] >= lo_ms) & (el["epoch_ms"] <= hi_ms)
    if m.sum() < 5:
        return None
    return {k: v[m] for k, v in el.items()}


def nulls_stage(work, regime, theta_p, gamma_p, d_days, out_prefix,
                n_permutations=N_PERMUTATIONS):
    """prereg 5.8, 6.1, 6.3 and the gate ledger of prereg 10."""
    started = time.time()
    cache = Cache(work).open()
    flags = load_flags(work)
    summary = {int(k): v for k, v in json.loads(
        (Path(work) / "detect-summary.json").read_text()).items()}
    meta = {int(k): v for k, v in json.loads(
        (Path(work) / "object-meta.json").read_text()).items()}
    detect_meta = json.loads((Path(work) / "detect-meta.json").read_text())
    run = json.loads(Path(f"{out_prefix}-summary.json").read_text())
    events = [json.loads(line) for line in
              open(f"{out_prefix}-events.jsonl")]

    step = screen_grid_step_days(d_days)
    table = build_screen_table(work, regime, step)
    a_ref = float(np.median(table["a"]))
    da_window = screen_da_window_km(gamma_p, d_days, a_ref)
    pairs, _ = run_screen(table, theta_p, da_window, path="cpu",
                          progress_every=0)
    idx = object_epoch_index(table)
    objects = table["objects"]
    own_omegadot = {nd: s["omegadot"] for nd, s in summary.items()}
    never = {nd for nd, s in summary.items()
             if not s["nIntrack"] and not s["nPlane"]
             and s["elementSets"] >= CONTROL_MIN_ELEMENT_SETS
             and s["spanDays"] >= CONTROL_MIN_SPAN_DAYS}
    regime_objects = [int(o) for o in objects]

    print("  analytic J2 null ...", flush=True)
    an = analytic_j2_null(idx, pairs, objects, own_omegadot, theta_p, d_days,
                          step)
    print("  dwell-bound validation (gate G) ...", flush=True)
    dw = dwell_bound_validation(idx, pairs, objects, own_omegadot, never,
                                theta_p, d_days, step)
    print("  time-shuffled corroboration (gate B') ...", flush=True)
    ts = time_shuffled_corroboration(events, flags)
    print("  permutation null ...", flush=True)
    pn = permutation_null(work, cache, table, idx, pairs, objects, events,
                          flags, meta, theta_p, gamma_p, d_days, regime,
                          n_permutations=n_permutations)
    alerts = plane_change_alerts(flags, meta, regime_objects)
    fa = detector_false_alarm_rate(summary, meta, regime)
    cr = campaign_rate_per_object_year(summary, meta, flags, regime)

    arm_m = [e for e in events if e["armM"]]
    arm_g = [e for e in events if e["armG"]]
    precision = {
        "alerts": alerts["alerts"],
        "objectsRaisingAnAlert": alerts["objectsRaisingAnAlert"],
        "armMEvents": len(arm_m),
        "distinctArmMArrivals": len({(e["approacher"], round(e["arrivalMs"]))
                                     for e in arm_m}),
        "precision": (len(arm_m) / alerts["alerts"]) if alerts["alerts"] else None,
        "wilson95": wilson(len(arm_m), alerts["alerts"]) if alerts["alerts"] else None,
    }

    # ---- the gate ledger (prereg 10) ------------------------------------
    sigma_theta_p95 = detect_meta["sigmaThetaP95Deg"]
    sigma_n = detect_meta["sigmaNRevDay"]
    da_noise_km = abs(sigma_n / (1.5 * mean_motion_rev_day(a_ref) / a_ref))
    da_bar_km = phase_confinement_da_km(gamma_p, d_days, a_ref) / 10.0
    leak_n = run["control"]["armG"]["neverManoeuvred"]["perObjectDay"]
    leak_p = run["control"]["armG"]["payload"]["perObjectDay"]
    leak_ratio = (leak_n / leak_p) if (leak_p not in (None, 0.0)
                                       and leak_n is not None) else None
    censored = sum(1 for e in arm_m
                   if e["leadCausalDays"] is None
                   or e["leadCausalDays"] >= GATE_F_WALL_DAYS)
    leads = [e["leadCausalDays"] for e in arm_m if e["leadCausalDays"] is not None]
    gates = {
        "A": {"meaning": "the instrument is unfit",
              "barFormula": "sigma_theta(p95) <= theta_p/10 AND da noise <= (Gamma/(k D))/10",
              "barEvaluated": {"sigmaThetaP95Deg": GATE_A_SIGMA_THETA_MAX_DEG,
                               "daNoiseKm": da_bar_km},
              "measured": {"sigmaThetaP95Deg": sigma_theta_p95,
                           "daNoiseKm": da_noise_km},
              "fired": bool(sigma_theta_p95 > GATE_A_SIGMA_THETA_MAX_DEG
                            or da_noise_km > da_bar_km)},
        "B": {"meaning": "the geometry arm leaks",
              "barFormula": "arm-G never-manoeuvred rate > 0.10 x arm-G payload rate",
              "barEvaluated": GATE_B_LEAK_RATIO,
              "measured": leak_ratio,
              "fired": bool(leak_ratio is not None
                            and leak_ratio > GATE_B_LEAK_RATIO)},
        "Bprime": {"meaning": "the corroboration is decorative",
                   "measured": ts,
                   "fired": bool(ts["realInsideShuffledInterval"])},
        "C": {"meaning": "the null explains the catalogue",
              "measured": pn,
              "fired": bool(pn.get("observedInsideNull95", False))},
        "D": {"meaning": "underpowered",
              "barEvaluated": GATE_D_MIN_EVENTS,
              "measured": len(arm_m),
              "fired": bool(len(arm_m) < GATE_D_MIN_EVENTS)},
        "E": {"meaning": "no lead time",
              "measured": {"medianLeadCausalDays": (
                  float(np.median(leads)) if leads else None),
                  "nullFraction": (1.0 - len(leads) / len(arm_m))
                  if arm_m else None},
              "fired": bool(arm_m and (not leads
                                       or float(np.median(leads)) <= 0.0
                                       or len(leads) / len(arm_m) < 0.5))},
        "F": {"meaning": "the lead time is censored by its own window",
              "barEvaluated": GATE_F_CENSOR_FRACTION,
              "measured": {"atOrBeyondWall": censored,
                           "fraction": (censored / len(arm_m)) if arm_m else None},
              "fired": bool(arm_m and censored / len(arm_m) > GATE_F_CENSOR_FRACTION)},
        "G": {"meaning": "the dwell bound is unvalidated",
              "barEvaluated": GATE_G_DWELL_EXCEEDANCE,
              "measured": dw,
              "fired": bool(dw["exceedingFraction"] is not None
                            and dw["exceedingFraction"] > GATE_G_DWELL_EXCEEDANCE)},
        "H": {"meaning": "the manoeuvre detector cannot corroborate",
              "barFormula": "false-alarm rate per object-year >= 0.5 x campaign rate per object-year",
              "barEvaluated": GATE_H_FALSE_ALARM_RATIO,
              "measured": {"falseAlarm": fa, "campaignRate": cr,
                           "ratio": (fa["flagsPerObjectYear"] / cr["campaignsPerObjectYear"])
                           if (fa["flagsPerObjectYear"] and cr["campaignsPerObjectYear"])
                           else None},
              "fired": None},
    }
    r = gates["H"]["measured"]["ratio"]
    gates["H"]["fired"] = bool(r is not None and r >= GATE_H_FALSE_ALARM_RATIO)

    out = {"regime": regime, "label": run["label"],
           "thresholds": run["thresholds"],
           "analyticJ2Null": an, "permutationNull": pn,
           "dwellBoundValidation": dw, "timeShuffledCorroboration": ts,
           "precision": precision, "detectorFalseAlarm": fa,
           "campaignRate": cr, "gates": gates,
           "armGLeakRatio": leak_ratio,
           "wallSeconds": time.time() - started}
    Path(f"{out_prefix}-nulls.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2)[:6000], flush=True)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=("extract", "detect", "bench", "screen",
                                 "analyze", "nulls", "all"))
    parser.add_argument("--archive", type=Path, required=True,
                        help="the element-set archive database")
    parser.add_argument("--work", type=Path, required=True,
                        help="working directory for intermediate extracts")
    parser.add_argument("--regime", default="LEO", choices=REGIMES)
    parser.add_argument("--theta-p", type=float, default=THETA_P_DEG)
    parser.add_argument("--gamma", type=float, default=GAMMA_DEG)
    parser.add_argument("--d-days", type=float, default=D_DAYS)
    parser.add_argument("--label", default="primary")
    parser.add_argument("--out-prefix", default=None)
    parser.add_argument("--no-gpu", action="store_true")
    parser.add_argument("--max-pairs", type=int, default=None)
    parser.add_argument("--limit-rows", type=int, default=None)
    parser.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)

    if args.stage in ("extract", "all"):
        db = orbit_campaigns.open_archive_for_reading(args.archive)
        print(json.dumps(extract(db, args.work, limit_rows=args.limit_rows),
                         indent=2))
        db.close()
    if args.stage in ("detect", "all"):
        db = orbit_campaigns.open_archive_for_reading(args.archive)
        detect_stage(Cache(args.work).open(), db, args.work)
        db.close()
    if args.stage in ("bench",):
        table = build_screen_table(args.work, args.regime,
                                   screen_grid_step_days(args.d_days))
        a_ref = float(np.median(table["a"]))
        print(json.dumps(bench_screen(
            table, args.theta_p,
            screen_da_window_km(args.gamma, args.d_days, a_ref),
            use_gpu=not args.no_gpu), indent=2))
    if args.stage in ("nulls",):
        prefix = args.out_prefix or str(args.work / f"{args.regime}-{args.label}")
        nulls_stage(args.work, args.regime, args.theta_p, args.gamma,
                    args.d_days, prefix, n_permutations=args.permutations)
    if args.stage in ("analyze", "all"):
        db = orbit_campaigns.open_archive_for_reading(args.archive)
        prefix = args.out_prefix or str(
            args.work / f"{args.regime}-{args.label}")
        out = analyze(args.work, db, args.regime, args.theta_p, args.gamma,
                      args.d_days, prefix, gpu_ok=not args.no_gpu,
                      max_pairs=args.max_pairs, label=args.label)
        db.close()
        if out is not None:
            trimmed = dict(out)
            trimmed["leadTime"] = {k: v for k, v in out["leadTime"].items()
                                   if k != "curve"}
            print(json.dumps(trimmed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
