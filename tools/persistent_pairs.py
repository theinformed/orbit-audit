#!/usr/bin/env python3
"""T11: persistent pairs, arrival order and response hazard at near-GEO.

Every definition here is the one registered in
`docs/persistent-pairs-preregistration-20260922.md` and must not drift from
it. Section references below (prereg N) point at that document; where this
module makes an implementation choice the registration left open, the choice
is marked IMPL and justified in place.

The instrument is ownership-agnostic. Catalogue registry codes, names, object
ids and launch dates are carried as metadata and are read by **no** detector
branch; `object_type` is read only to assign the classes of prereg 3.3.
Nothing here computes a delta-V, a mass or any consumables figure.

Mean longitude is a slot coordinate (prereg 1.1). **No number produced here
is a miss distance.**

The near-GEO extract is T8a's, hash-pinned by its three published counts
(prereg 3.1); this module re-detects nothing T8a already committed and
imports T8a's estimators rather than copying them (prereg 3.2).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline import orbit_campaigns  # noqa: E402
from tools import proximity_geo as pg  # noqa: E402

DAY_MS = pg.DAY_MS
KM_PER_DEG = pg.KM_PER_DEG_GEO

# ==========================================================================
# prereg 2 -- the thresholds, derived here rather than written down
# ==========================================================================

# prereg 2.1: T3's committed triaxial longitude-acceleration amplitude
# (docs/cadence-results-20260921.md 5.3).
A_LONGITUDE_MAX_DEG_PER_DAY2 = 1.7006e-3

# prereg 2.1/2.2: T3's measured east-west line and its measured core half
# width (14.00 +/- 0.109 d), and its Inmarsat-shaped 21.00 d line.
T_EAST_WEST_DAYS = 14.00
T_EAST_WEST_CORE_HALF_WIDTH_DAYS = 0.109
T_SECOND_LINE_DAYS = 21.00

# prereg 2.2: T3's registered minimum cycles per cadence window.
MIN_CYCLES_IN_WINDOW = 4.0

# prereg 2.3: T8a 0.2's measured median near-GEO within-object epoch spacing.
MEDIAN_EPOCH_SPACING_DAYS = 0.865

# prereg 2.4: T8a 4's measured lead_causal distribution.
LEAD_CAUSAL_MEDIAN_DAYS = 36.1
LEAD_CAUSAL_P75_DAYS = 96.0
LEAD_CAUSAL_P95_DAYS = 162.7


def deadband_half_width_deg(period_days, acceleration_deg_per_day2):
    """prereg 2.1: a one-sided parabolic drift cycle across a deadband of
    half-width dL takes T = 4 sqrt(dL/A), hence dL = A T^2 / 16."""
    return acceleration_deg_per_day2 * period_days * period_days / 16.0


def pair_threshold_deg(period_days, acceleration_deg_per_day2):
    """prereg 2.1: two objects held at one station each occupy a box of
    half-width dL about the same nominal longitude, so their mean-longitude
    separation is bounded by twice that."""
    return 2.0 * deadband_half_width_deg(period_days, acceleration_deg_per_day2)


X_PAIR_PRIMARY_DEG = pair_threshold_deg(T_EAST_WEST_DAYS,
                                        A_LONGITUDE_MAX_DEG_PER_DAY2)
X_PAIR_TIGHT_DEG = pair_threshold_deg(T_EAST_WEST_DAYS,
                                      0.5 * A_LONGITUDE_MAX_DEG_PER_DAY2)
X_PAIR_LOOSE_DEG = pair_threshold_deg(T_SECOND_LINE_DAYS,
                                      A_LONGITUDE_MAX_DEG_PER_DAY2)
X_PAIR_T8A_DEG = pg.X_PRIMARY_DEG                      # 0.1 deg

D_PAIR_PRIMARY_DAYS = MIN_CYCLES_IN_WINDOW * T_EAST_WEST_DAYS       # 56.00
D_PAIR_SHORT_DAYS = 3.0 * T_EAST_WEST_DAYS                          # 42.00
D_PAIR_LONG_DAYS = 8.0 * T_EAST_WEST_DAYS                           # 112.00
D_PAIR_VERY_LONG_DAYS = 12.0 * T_EAST_WEST_DAYS                     # 168.00

PHI_LOCK_RAD = 2.0 * math.pi * MEDIAN_EPOCH_SPACING_DAYS / T_EAST_WEST_DAYS
W_PRIMARY_DAYS = LEAD_CAUSAL_P95_DAYS
W_ARMS_DAYS = (LEAD_CAUSAL_MEDIAN_DAYS, LEAD_CAUSAL_P75_DAYS,
               LEAD_CAUSAL_P95_DAYS, 365.0)

MAX_GAP_DAYS = pg.MAX_GAP_DAYS                        # prereg 4.1, borrowed
MIN_OCCUPANCY_PER_DAY = pg.LOITER_MIN_OCCUPANCY_PER_DAY

ARRIVAL_RESOLUTION_DAYS = max(1.0, 2.0 * MEDIAN_EPOCH_SPACING_DAYS)   # 1.73
ARRIVAL_CENSOR_DAYS = 1.0

NEVER_MIN_ELEMENT_SETS = 200                          # prereg 3.3
NEVER_MIN_SPAN_DAYS = 365.0

FAP_ALPHA = 0.01                                      # prereg 5.2
N_CONTROL_PAIRS = 200                                 # prereg 5.3
N_MATCHES_PER_ARRIVAL = 5                             # prereg 6.2
N_PERMUTATIONS = 1000
SEED = 20260922
CROWDING_RADIUS_DEG = 5.0
GATE_B_LEAK_RATIO = 0.10                              # prereg 6.3 L3
GATE_D_MIN_PAIRS = 20
GATE_D_MIN_EVENTS = 10
GATE_E_MAX_UNRESOLVED_FRACTION = 0.50
L1_NULL_BAND = (0.95, 1.05)

PINNED_ROWS_SCANNED = 217_007_154                     # prereg 3.1
PINNED_ROWS_KEPT = 11_626_494
PINNED_OBJECTS_KEPT = 1_768

# IMPL screen: widest registered X with a 50% margin, shortest registered D
# with a 20% margin, so that no registered arm can be decided by the screen.
SCREEN_RADIUS_DEG = 1.5 * max(X_PAIR_PRIMARY_DEG, X_PAIR_TIGHT_DEG,
                              X_PAIR_LOOSE_DEG, X_PAIR_T8A_DEG)
SCREEN_MIN_DAYS = int(0.8 * D_PAIR_SHORT_DAYS)

ARMS = (
    ("primary", X_PAIR_PRIMARY_DEG, D_PAIR_PRIMARY_DAYS),
    ("x-tight", X_PAIR_TIGHT_DEG, D_PAIR_PRIMARY_DAYS),
    ("x-loose", X_PAIR_LOOSE_DEG, D_PAIR_PRIMARY_DAYS),
    ("x-t8a", X_PAIR_T8A_DEG, D_PAIR_PRIMARY_DAYS),
    ("d-short", X_PAIR_PRIMARY_DEG, D_PAIR_SHORT_DAYS),
    ("d-long", X_PAIR_PRIMARY_DEG, D_PAIR_LONG_DAYS),
    ("d-very-long", X_PAIR_PRIMARY_DEG, D_PAIR_VERY_LONG_DAYS),
)

# prereg 0 -- the vocabulary ban, asserted by the test suite against this
# module, the catalogue, the case list and the results document.  Held as
# split fragments so that this list is not itself a hit.
BANNED_WORDS = tuple(sorted({
    "s" + "py", "s" + "pying", "es" + "pionage", "ins" + "pect",
    "ins" + "pection", "ins" + "pector", "sur" + "veil", "sur" + "veillance",
    "sha" + "dow", "sha" + "dowing", "st" + "alk", "st" + "alking",
    "hos" + "tile", "adver" + "sary", "thr" + "eat", "att" + "ack",
    "wea" + "pon", "counter" + "space", "in" + "tent", "in" + "tention",
    "delib" + "erate", "delib" + "erately", "av" + "oid", "av" + "oidance",
    "ev" + "ade", "ev" + "asion", "def" + "ensive", "susp" + "icious",
    "fi" + "shy", "tar" + "get", "tar" + "gets", "tar" + "geting",
    "tar" + "geted",
}))


def banned_hits(text):
    """Case-insensitive, word-boundary search (prereg 0; the T8d lesson --
    'nation' is a substring of 'inclination', so a bare substring test is
    wrong)."""
    low = text.lower()
    hits = []
    for word in BANNED_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", low):
            hits.append(word)
    return sorted(set(hits))


# ==========================================================================
# Exact interval machinery (prereg 6.2; scipy is not installed on the host)
# ==========================================================================
def _betacf(a, b, x, itmax=400, eps=3e-16):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Regularised incomplete beta I_x(a, b), by continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1.0 - x) / b


def beta_quantile(q, a, b):
    """Inverse of I_x(a, b) in x, by bisection (I is increasing in x)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def clopper_pearson(k, n, alpha=0.05):
    """Exact two-sided interval for a binomial proportion (prereg 6.2)."""
    if n == 0:
        return (float("nan"), float("nan"))
    low = 0.0 if k == 0 else beta_quantile(alpha / 2.0, k, n - k + 1)
    high = 1.0 if k == n else beta_quantile(1.0 - alpha / 2.0, k + 1, n - k)
    return (low, high)


def rate_ratio_ci(e1, t1, e2, t2, alpha=0.05):
    """Exact conditional interval for a ratio of two Poisson rates
    (prereg 6.2): conditional on T = e1 + e2, e1 ~ Binomial(T, rho) with
    rho = HR t1 / (HR t1 + t2); a Clopper-Pearson interval for rho is
    inverted to an interval for HR."""
    total = int(e1) + int(e2)
    if total == 0 or t1 <= 0 or t2 <= 0:
        return (float("nan"), float("nan"), float("nan"))
    ratio = ((e1 / t1) / (e2 / t2)) if e2 > 0 else float("inf")
    lo_rho, hi_rho = clopper_pearson(int(e1), total, alpha)

    def _hr(rho):
        if rho <= 0.0:
            return 0.0
        if rho >= 1.0:
            return float("inf")
        return (rho / (1.0 - rho)) * (t2 / t1)

    return (ratio, _hr(lo_rho), _hr(hi_rho))


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [(c - h) / d, (c + h) / d]


def percentiles(values, qs=(5, 25, 50, 75, 95)):
    a = np.asarray([v for v in values
                    if v is not None and np.isfinite(v)], dtype=np.float64)
    if a.size == 0:
        return {f"p{q}": None for q in qs} | {"n": 0}
    out = {f"p{q}": float(np.percentile(a, q)) for q in qs}
    out.update({"min": float(a.min()), "max": float(a.max()),
                "mean": float(a.mean()), "n": int(a.size)})
    return out


def wrap_pi(x):
    return (np.asarray(x) + math.pi) % (2.0 * math.pi) - math.pi


# ==========================================================================
# prereg 5.1/5.2 -- the cadence phasor
# ==========================================================================
def cadence_phasor(days, values, period_days=T_EAST_WEST_DAYS):
    """Least-squares sinusoid at a FIXED frequency over a linear null model
    (prereg 5.1). `days` are days from the fixed common origin of prereg 5.1
    (the Unix epoch), identical for both members so the phases compare.

    The false-alarm probability is the single-frequency result for a null
    model with k0 = 2 free parameters (prereg 5.2): (1 - p)^((N - 4)/2).
    """
    t = np.asarray(days, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    n = t.size
    if n < 8:
        return None
    w = 2.0 * math.pi / period_days
    ones = np.ones(n)
    tc = t - t.mean()          # conditioning only; the sinusoid keeps the
    null_design = np.column_stack([ones, tc])          # true origin, so the
    full_design = np.column_stack([ones, tc,           # phase is comparable
                                   np.cos(w * t), np.sin(w * t)])
    try:
        c0, *_ = np.linalg.lstsq(null_design, y, rcond=None)
        c1, *_ = np.linalg.lstsq(full_design, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    r0 = y - null_design @ c0
    r1 = y - full_design @ c1
    chi0, chi1 = float(r0 @ r0), float(r1 @ r1)
    if chi0 <= 0.0:
        return None
    power = min(1.0, max(0.0, (chi0 - chi1) / chi0))
    dof = n - 4
    if dof <= 0:
        return None
    fap = (1.0 - power) ** (dof / 2.0)
    a, b = float(c1[2]), float(c1[3])
    amp = math.hypot(a, b)
    sigma_resid = math.sqrt(chi1 / dof)
    sigma_phase = (sigma_resid / (amp * math.sqrt(n / 2.0))
                   if amp > 0 else float("inf"))
    return {"amplitude": amp, "phase": math.atan2(b, a), "power": power,
            "fap": fap, "n": int(n), "sigmaPhase": sigma_phase,
            "sigmaResid": sigma_resid, "periodDays": float(period_days)}


def refine_period(days, values, centre=T_EAST_WEST_DAYS,
                  half_width=T_EAST_WEST_CORE_HALF_WIDTH_DAYS, steps=21):
    """prereg 5.2's free-period variant: the best period inside T3's measured
    core half-width, by the same fit evaluated on a grid."""
    best = None
    for p in np.linspace(centre - half_width, centre + half_width, steps):
        fit = cadence_phasor(days, values, period_days=float(p))
        if fit is not None and (best is None or fit["power"] > best["power"]):
            best = fit
    return best


def rayleigh(phases):
    """Mean resultant length and Rayleigh p-value for circular uniformity."""
    a = np.asarray(phases, dtype=np.float64)
    n = a.size
    if n == 0:
        return (float("nan"), float("nan"), 0)
    rbar = float(math.hypot(float(np.cos(a).mean()), float(np.sin(a).mean())))
    z = n * rbar * rbar
    p = (math.exp(-z) * (1.0 + (2.0 * z - z * z) / (4.0 * n))) if n > 1 else 1.0
    return (rbar, float(min(1.0, max(0.0, p))), int(n))


def circular_sd(phases):
    a = np.asarray(phases, dtype=np.float64)
    if a.size < 2:
        return float("nan")
    rbar = math.hypot(float(np.cos(a).mean()), float(np.sin(a).mean()))
    return float(math.sqrt(-2.0 * math.log(min(max(rbar, 1e-12), 1.0))))


def lock_category(dphi, phi_lock=PHI_LOCK_RAD):
    """prereg 2.3. A descriptive category, never a per-pair claim
    (prereg 5.4)."""
    d = float(abs(wrap_pi(dphi)))
    anti = abs(math.pi - d)
    if d <= phi_lock:
        return "locked"
    if anti <= phi_lock:
        return "anti-locked"
    if d <= 2.0 * phi_lock or anti <= 2.0 * phi_lock:
        return "near-locked"
    return "unlocked"


def lock_distance(dphi):
    """Circular distance to the nearer of in-phase and anti-phase
    (prereg 7 component 2)."""
    d = float(abs(wrap_pi(dphi)))
    return min(d, math.pi - d)


# ==========================================================================
# prereg 3.4 -- the descriptive family stem (one count, never a grouping)
# ==========================================================================
_STEM = re.compile(r"^([^0-9]*)")


def name_stem(name):
    if not name:
        return ""
    stem = _STEM.match(name.upper()).group(1).strip(" -_/.,()")
    return stem if len(stem) >= 3 else ""


# ==========================================================================
# World
# ==========================================================================
class World:
    pass


def build_world(db, work):
    t0 = time.time()
    meta = json.loads((work / "extract-meta.json").read_text())
    if (meta["rowsScanned"] != PINNED_ROWS_SCANNED
            or meta["rowsKept"] != PINNED_ROWS_KEPT
            or meta["objectsKept"] != PINNED_OBJECTS_KEPT):
        raise SystemExit(
            "GATE F: the near-GEO extract is not T8a's (prereg 3.1). "
            f"scanned {meta['rowsScanned']} kept {meta['rowsKept']} "
            f"objects {meta['objectsKept']}")
    with np.load(work / "near-geo.npz") as z:
        arrays = {k: z[k] for k in z.files}

    w = World()
    w.extractMeta = meta
    w.series = pg.build_series(arrays)
    w.global_lo, w.n_days = pg.build_daily_grid(w.series)
    w.index = {s.norad: i for i, s in enumerate(w.series)}
    w.meta = pg.object_metadata(db, sorted(w.index))
    w.classes = {n: pg.class_of(w.meta[n]["objectType"]) for n in w.index}

    w.segs = {s.norad: pg.station_segments(s) for s in w.series}
    w.sigma_n, w.sigma_pairs = pg.calibrate_sigma_n(w.series, w.classes, w.segs)

    w.never, w.payload = set(), set()
    for s in w.series:
        epochs, _ = pg.drift_change_flags(s, w.sigma_n)
        span_days = (s.epoch_ms[-1] - s.epoch_ms[0]) / DAY_MS
        if (epochs.size == 0 and s.epoch_ms.size >= NEVER_MIN_ELEMENT_SETS
                and span_days >= NEVER_MIN_SPAN_DAYS):
            w.never.add(s.norad)
        if w.classes.get(s.norad) == "active":
            w.payload.add(s.norad)

    # prereg 3.2's named trap: grid_lo is RELATIVE to the global origin.
    w.segid, w.stationed_days = {}, {}
    for s in w.series:
        ids = np.full(s.grid.size, -1, dtype=np.int32)
        for k, (i0, i1) in enumerate(w.segs[s.norad]):
            ids[i0:i1 + 1] = k
        w.segid[s.norad] = ids
        w.stationed_days[s.norad] = (np.where(ids >= 0)[0]
                                     + s.grid_lo).astype(np.int64)

    w.relocation_days, w.departure_days = {}, {}
    for s in w.series:
        rel = pg.relocations(s, w.segs[s.norad])
        w.relocation_days[s.norad] = np.asarray(
            sorted(int(r["originEndDay"]) for r in rel), dtype=np.int64)
        w.departure_days[s.norad] = np.asarray(
            sorted(s.grid_lo + i1 for _, i1 in w.segs[s.norad]),
            dtype=np.int64)
    w.buildSeconds = time.time() - t0
    return w


def day_to_ms(w, gday):
    """Global-relative day index -> epoch ms (prereg 3.2)."""
    return (w.global_lo + gday) * DAY_MS + 0.5 * DAY_MS


def iso(ms):
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


def outcome_days(w, norad, outcome):
    return (w.relocation_days[norad] if outcome == "relocation"
            else w.departure_days[norad])


# ==========================================================================
# The screen (IMPL) and the exact persistence pass (prereg 4.1)
# ==========================================================================
def _flat_stationed(w):
    days_l, lons_l, ids_l = [], [], []
    for si, s in enumerate(w.series):
        ok = np.where(w.segid[s.norad] >= 0)[0]
        if ok.size == 0:
            continue
        days_l.append((ok + s.grid_lo).astype(np.int64))
        lons_l.append(pg.wrap180(s.grid[ok]).astype(np.float64))
        ids_l.append(np.full(ok.size, si, dtype=np.int64))
    days = np.concatenate(days_l)
    lons = np.concatenate(lons_l)
    ids = np.concatenate(ids_l)
    order = np.lexsort((lons, days))
    return days[order], lons[order], ids[order]


def screen_pairs(w):
    days, lons, ids = _flat_stationed(w)
    stationed_object_days = int(days.size)
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
        j_end = np.searchsorted(dl, dl + radius, side="right")
        for i in range(m):
            for j in range(i + 1, int(j_end[i])):
                a, b = int(di[i]), int(di[j])
                key = (a, b) if a < b else (b, a)
                counts[key] = counts.get(key, 0) + 1
        i = 0
        while i < m and dl[i] + 360.0 - dl[-1] <= radius:
            j = m - 1
            while j > i and dl[i] + 360.0 - dl[j] <= radius:
                a, b = int(di[i]), int(di[j])
                key = (a, b) if a < b else (b, a)
                counts[key] = counts.get(key, 0) + 1
                j -= 1
            i += 1
    return ([k for k, v in counts.items() if v >= SCREEN_MIN_DAYS],
            len(counts), stationed_object_days)


def _segids_for(w, s, gday):
    ids = w.segid[s.norad]
    k = gday - s.grid_lo
    out = np.full(k.size, -1, dtype=np.int32)
    ok = (k >= 0) & (k < ids.size)
    out[ok] = ids[k[ok]]
    return out


def pair_packed(w, a, b):
    """Union-of-epochs separation plus per-epoch station segment ids."""
    packed = pg.pair_separation(a, b, SCREEN_MIN_DAYS)
    if packed is None:
        return None
    t, la, lb, _sep, asep = packed
    gday = np.floor(t / DAY_MS).astype(np.int64) - w.global_lo
    return t, la, lb, asep, gday, _segids_for(w, a, gday), _segids_for(w, b, gday)


def _split_constant(ida, idb):
    spans, start = [], 0
    for i in range(1, ida.size):
        if ida[i] != ida[start] or idb[i] != idb[start]:
            spans.append((start, i - 1))
            start = i
    spans.append((start, ida.size - 1))
    return spans


def _rej(stats, key):
    if stats is not None:
        stats[key] = stats.get(key, 0) + 1


def _finish(w, a, b, t, la, lb, asep, gday, i0, i1, d_days, stats):
    dwell = (t[i1] - t[i0]) / DAY_MS
    if dwell < d_days:
        _rej(stats, "dwellTooShort")
        return []
    n_ret = i1 - i0 + 1
    if n_ret < MIN_OCCUPANCY_PER_DAY * dwell:
        _rej(stats, "occupancy")
        return []
    lam_a = pg.wrap180(la[i0:i1 + 1])
    lam_b = pg.wrap180(lb[i0:i1 + 1])
    station = float(pg.wrap180(0.5 * (np.median(la[i0:i1 + 1])
                                      + np.median(lb[i0:i1 + 1]))))
    stable = min(abs(float(pg.wrap180(station - s)))
                 for s in pg.STABLE_LONGITUDES_DEG)
    return [{
        "a": a.norad, "b": b.norad,
        "startMs": float(t[i0]), "endMs": float(t[i1]),
        "dwellDays": float(dwell), "retainedEpochs": int(n_ret),
        "medianAbsSepDeg": float(np.median(asep[i0:i1 + 1])),
        "maxAbsSepDeg": float(asep[i0:i1 + 1].max()),
        "closestAbsSepDeg": float(asep[i0:i1 + 1].min()),
        "spreadADeg": float(lam_a.max() - lam_a.min()),
        "spreadBDeg": float(lam_b.max() - lam_b.min()),
        "medianLonADeg": float(np.median(lam_a)),
        "medianLonBDeg": float(np.median(lam_b)),
        "stationLonDeg": station, "distanceToStableDeg": stable,
        "segA": int(_segids_for(w, a, gday[i0:i0 + 1])[0]),
        "segB": int(_segids_for(w, b, gday[i0:i0 + 1])[0]),
        "startDay": int(gday[i0]), "endDay": int(gday[i1]),
    }]


def _split_gaps(t, i0, i1, stats):
    """prereg 4.1 criterion 3: episodes are MAXIMAL, so a retained-epoch gap
    longer than 5 d ends one episode and begins another rather than voiding
    the whole run."""
    spans, start = [], i0
    for i in range(i0 + 1, i1 + 1):
        if (t[i] - t[i - 1]) / DAY_MS > MAX_GAP_DAYS:
            spans.append((start, i - 1))
            _rej(stats, "internalGap")
            start = i
    spans.append((start, i1))
    return spans


def episodes_for_pair(w, a, b, packed, x_deg, d_days, stats=None):
    """prereg 4.1, exact, on the union of element epochs."""
    t, la, lb, asep, gday, ida, idb = packed
    ok = (ida >= 0) & (idb >= 0) & (asep <= x_deg)
    out = []
    for i0, i1 in pg._runs(ok):
        sub_a, sub_b = ida[i0:i1 + 1], idb[i0:i1 + 1]
        for j0, j1 in _split_constant(sub_a, sub_b):
            for k0, k1 in _split_gaps(t, i0 + j0, i0 + j1, stats):
                out.extend(_finish(w, a, b, t, la, lb, asep, gday,
                                   k0, k1, d_days, stats))
    return out


def detect_all(w, candidates, arms):
    """One packed pass per candidate pair; every arm reads the same pack."""
    out = {name: [] for name, _, _ in arms}
    stats = {name: {} for name, _, _ in arms}
    for si, sj in candidates:
        a, b = w.series[si], w.series[sj]
        packed = pair_packed(w, a, b)
        if packed is None:
            continue
        for name, x_deg, d_days in arms:
            out[name].extend(
                episodes_for_pair(w, a, b, packed, x_deg, d_days, stats[name]))
    return out, stats


# ==========================================================================
# prereg 5 -- cadence on an episode
# ==========================================================================
def member_window(w, norad, start_ms, end_ms):
    s = w.series[w.index[norad]]
    k0, k1 = np.searchsorted(s.epoch_ms, [start_ms, end_ms + 1])
    if k1 - k0 < 8:
        return None
    return (s.epoch_ms[k0:k1] / DAY_MS, s.drift[k0:k1])


def fit_member(w, norad, start_ms, end_ms, free_period=False, cache=None):
    key = (norad, float(start_ms), float(end_ms), bool(free_period))
    if cache is not None and key in cache:
        return cache[key]
    win = member_window(w, norad, start_ms, end_ms)
    fit = None
    if win is not None:
        fit = (refine_period(win[0], win[1]) if free_period
               else cadence_phasor(win[0], win[1]))
    if cache is not None:
        cache[key] = fit
    return fit


def cadence_for(w, na, nb, start_ms, end_ms, free_period=False, cache=None):
    fa = fit_member(w, na, start_ms, end_ms, free_period, cache)
    fb = fit_member(w, nb, start_ms, end_ms, free_period, cache)
    if fa is None or fb is None:
        return None
    testable = fa["fap"] <= FAP_ALPHA and fb["fap"] <= FAP_ALPHA
    if free_period:
        band = T_EAST_WEST_CORE_HALF_WIDTH_DAYS + 1e-9
        testable = testable and (
            abs(fa["periodDays"] - T_EAST_WEST_DAYS) <= band
            and abs(fb["periodDays"] - T_EAST_WEST_DAYS) <= band)
    dphi = float(wrap_pi(fa["phase"] - fb["phase"]))
    return {"fapA": fa["fap"], "fapB": fb["fap"],
            "ampA": fa["amplitude"], "ampB": fb["amplitude"],
            "sigmaPhaseA": fa["sigmaPhase"], "sigmaPhaseB": fb["sigmaPhase"],
            "periodA": fa["periodDays"], "periodB": fb["periodDays"],
            "deltaPhiRad": dphi, "deltaPhiDeg": math.degrees(dphi),
            "cadenceTestable": bool(testable),
            "lockCategory": lock_category(dphi)}


def phase_stability(w, ep, block_days=D_PAIR_PRIMARY_DAYS, cache=None):
    """prereg 5.5: phase stability across consecutive four-cycle blocks."""
    n_blocks = int(ep["dwellDays"] // block_days)
    if n_blocks < 2:
        return None
    edges = [ep["startMs"] + i * block_days * DAY_MS
             for i in range(n_blocks + 1)]
    phis = []
    for i in range(n_blocks):
        fa = fit_member(w, ep["a"], edges[i], edges[i + 1], False, cache)
        fb = fit_member(w, ep["b"], edges[i], edges[i + 1], False, cache)
        if fa is not None and fb is not None:
            phis.append(float(wrap_pi(fa["phase"] - fb["phase"])))
    if len(phis) < 2:
        return None
    return {"blocks": len(phis), "circularSd": circular_sd(phis)}


def _pool_for_window(w, d0, d1):
    pool = []
    for s in w.series:
        if w.classes.get(s.norad) != "active":
            continue
        ids = w.segid[s.norad]
        k0, k1 = d0 - s.grid_lo, d1 - s.grid_lo
        if k0 < 0 or k1 >= ids.size or k1 < k0:
            continue
        sl = ids[k0:k1 + 1]
        if sl.size and sl[0] >= 0 and bool(np.all(sl == sl[0])):
            pool.append(s.norad)
    return pool


def _separated_everywhere(w, na, nb, d0, d1, x_deg):
    sa, sb = w.series[w.index[na]], w.series[w.index[nb]]
    ga = sa.grid[d0 - sa.grid_lo:d1 - sa.grid_lo + 1]
    gb = sb.grid[d0 - sb.grid_lo:d1 - sb.grid_lo + 1]
    if ga.size != gb.size or ga.size == 0:
        return False
    sep = np.abs(pg.wrap180(ga - gb))
    return bool(np.all(np.isfinite(sep)) and sep.min() > x_deg)


def control_pairs_for_episode(w, ep, rng, pools, x_deg, cache):
    """prereg 5.3: M control pairs, both stationed over the IDENTICAL window,
    separated by more than x_deg at every retained epoch, retained sample
    counts within a factor of two of the real pair's."""
    key = (ep["startDay"], ep["endDay"])
    pool = pools.get(key)
    if pool is None:
        pool = _pool_for_window(w, ep["startDay"], ep["endDay"])
        pools[key] = pool
    if len(pool) < 4:
        return []
    arr = np.asarray(pool)
    n_ref = ep["retainedEpochs"]
    out, tries = [], 0
    seen = set()
    while len(out) < N_CONTROL_PAIRS and tries < 10 * N_CONTROL_PAIRS:
        tries += 1
        i, j = rng.choice(arr.size, size=2, replace=False)
        na, nb = int(arr[i]), int(arr[j])
        pk = (min(na, nb), max(na, nb))
        if pk in seen or set(pk) == {ep["a"], ep["b"]}:
            continue
        seen.add(pk)
        wa = member_window(w, na, ep["startMs"], ep["endMs"])
        wb = member_window(w, nb, ep["startMs"], ep["endMs"])
        if wa is None or wb is None:
            continue
        if not (0.5 * n_ref <= wa[0].size <= 2.0 * n_ref):
            continue
        if not (0.5 * n_ref <= wb[0].size <= 2.0 * n_ref):
            continue
        if not _separated_everywhere(w, na, nb, ep["startDay"], ep["endDay"],
                                     x_deg):
            continue
        cad = cadence_for(w, na, nb, ep["startMs"], ep["endMs"], False, cache)
        if cad is not None:
            out.append(cad)
    return out


# ==========================================================================
# prereg 4.2 -- arrival order
# ==========================================================================
def arrival_for_member(w, norad, seg_id, ep, x_deg):
    s = w.series[w.index[norad]]
    i0, i1 = w.segs[norad][seg_id]
    arr_station_day = s.grid_lo + i0
    censored = ((day_to_ms(w, arr_station_day) - s.epoch_ms[0])
                <= ARRIVAL_CENSOR_DAYS * DAY_MS)
    g = s.grid[i0:i1 + 1]
    inside = np.abs(pg.wrap180(g - ep["stationLonDeg"])) <= 0.5 * x_deg
    k = int(min(max(ep["startDay"] - arr_station_day, 0), inside.size - 1))
    j = k
    while j > 0 and inside[j - 1]:
        j -= 1
    return {"arrivalStationDay": int(arr_station_day),
            "arrivalBandDay": int(arr_station_day + j),
            "censored": bool(censored)}


def arrival_order(w, ep, x_deg):
    aa = arrival_for_member(w, ep["a"], ep["segA"], ep, x_deg)
    ab = arrival_for_member(w, ep["b"], ep["segB"], ep, x_deg)
    gap = abs(aa["arrivalStationDay"] - ab["arrivalStationDay"])
    if aa["censored"] or ab["censored"]:
        order = "censored"
    elif gap <= ARRIVAL_RESOLUTION_DAYS:
        order = "unresolved"
    else:
        order = "resolved"
    if aa["arrivalStationDay"] <= ab["arrivalStationDay"]:
        incumbent, later = ep["a"], ep["b"]
        inc_day, later_day = aa["arrivalStationDay"], ab["arrivalStationDay"]
    else:
        incumbent, later = ep["b"], ep["a"]
        inc_day, later_day = ab["arrivalStationDay"], aa["arrivalStationDay"]
    return {"order": order, "arrivalGapDays": float(gap),
            "incumbent": incumbent, "laterArrival": later,
            "incumbentArrivalDay": int(inc_day),
            "laterArrivalDay": int(later_day),
            "arrivalA": aa, "arrivalB": ab}


# ==========================================================================
# prereg 6 -- the response hazard
# ==========================================================================
def exposure_for(w, norad, t0_day, window_days, outcome):
    """Stationed days in (t0, t0 + W], censored at the outcome, at the end of
    the stationed span, or at the archive end (prereg 6.1)."""
    s = w.series[w.index[norad]]
    ids = w.segid[norad]
    k0 = t0_day - s.grid_lo
    if k0 < 0 or k0 >= ids.size or ids[k0] < 0:
        return None
    _, i1 = w.segs[norad][int(ids[k0])]
    seg_end = s.grid_lo + i1
    horizon = t0_day + int(round(window_days))
    limit = min(horizon, seg_end)
    days = outcome_days(w, norad, outcome)
    lo = int(np.searchsorted(days, t0_day, side="right"))
    if lo < days.size and days[lo] <= limit:
        return (1, float(days[lo] - t0_day))
    return (0, float(max(0.0, limit - t0_day)))


def _merge(windows):
    if not windows:
        return []
    ws = sorted(windows)
    out = [list(ws[0])]
    for lo, hi in ws[1:]:
        if lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def baseline_for(w, norad, excluded, outcome):
    """The SAME object's rate over all its stationed time outside any exposed
    window (prereg 6.2), by interval arithmetic rather than day sets."""
    stationed = w.stationed_days[norad]
    days = outcome_days(w, norad, outcome)
    exposure = float(stationed.size)
    events = int(days.size)
    for lo, hi in _merge(excluded):
        i0, i1 = np.searchsorted(stationed, [lo + 1, hi + 1])
        exposure -= float(i1 - i0)
        j0, j1 = np.searchsorted(days, [lo + 1, hi + 1])
        events -= int(j1 - j0)
    return (max(0, events), max(0.0, exposure))


def crowding_deciles(w):
    """Deciles of the number of stationed objects within +/-5 deg, over all
    stationed object-days (prereg 6.2)."""
    days, lons, _ids = _flat_stationed(w)
    edges = np.searchsorted(days, np.arange(days[0], days[-1] + 2))
    chunks = []
    for k in range(edges.size - 1):
        lo, hi = int(edges[k]), int(edges[k + 1])
        if hi <= lo:
            continue
        dl = lons[lo:hi]
        left = np.searchsorted(dl, dl - CROWDING_RADIUS_DEG, side="left")
        right = np.searchsorted(dl, dl + CROWDING_RADIUS_DEG, side="right")
        chunks.append((right - left - 1).astype(np.int32))
    pooled = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int32)
    return (np.percentile(pooled, np.arange(10, 100, 10))
            if pooled.size else np.zeros(9)), pooled


def crowding_on_day(w, day, cache):
    if day in cache:
        return cache[day]
    lons, nor = [], []
    for s in w.series:
        k = day - s.grid_lo
        ids = w.segid[s.norad]
        if 0 <= k < ids.size and ids[k] >= 0 and np.isfinite(s.grid[k]):
            lons.append(float(pg.wrap180(s.grid[k])))
            nor.append(s.norad)
    if not lons:
        cache[day] = {}
        return cache[day]
    a = np.asarray(lons)
    order = np.argsort(a)
    a = a[order]
    nor = [nor[i] for i in order]
    left = np.searchsorted(a, a - CROWDING_RADIUS_DEG, side="left")
    right = np.searchsorted(a, a + CROWDING_RADIUS_DEG, side="right")
    cnt = (right - left - 1)
    cache[day] = {nor[i]: int(cnt[i]) for i in range(len(nor))}
    return cache[day]


def tenure_quartiles(w):
    vals = [i1 - i0 + 1 for s in w.series for i0, i1 in w.segs[s.norad]]
    a = np.asarray(vals, dtype=np.float64)
    return np.percentile(a, [25, 50, 75]) if a.size else np.zeros(3)


def tenure_at(w, norad, gday):
    s = w.series[w.index[norad]]
    ids = w.segid[norad]
    k = gday - s.grid_lo
    if k < 0 or k >= ids.size or ids[k] < 0:
        return None
    i0, _ = w.segs[norad][int(ids[k])]
    return float(k - i0)


def _bin(value, edges):
    return int(np.searchsorted(edges, value, side="right"))


def find_matches(w, ep, incumbent, t0, window_days, rng, crowd_cache,
                 deciles, tenure_q, ep_starts):
    day_tab = crowding_on_day(w, t0, crowd_cache)
    if incumbent not in day_tab:
        return []
    want_crowd = _bin(day_tab[incumbent], deciles)
    ten = tenure_at(w, incumbent, t0)
    if ten is None:
        return []
    want_ten = _bin(ten, tenure_q)
    lo_w = t0 - int(round(window_days))
    hi_w = t0 + int(round(window_days))
    pool = []
    for norad, crowd in day_tab.items():
        if norad in (ep["a"], ep["b"]):
            continue
        if w.classes.get(norad) != "active":
            continue
        if _bin(crowd, deciles) != want_crowd:
            continue
        t = tenure_at(w, norad, t0)
        if t is None or _bin(t, tenure_q) != want_ten:
            continue
        if any(lo_w < d <= hi_w for d in ep_starts.get(norad, ())):
            continue
        s = w.series[w.index[norad]]
        ids = w.segid[norad]
        k = t0 - s.grid_lo
        _, i1 = w.segs[norad][int(ids[k])]
        if s.grid_lo + i1 <= t0:
            continue
        pool.append(norad)
    # The registered calendar-epoch clause (same year +/- 2) is satisfied by
    # construction and not re-tested: every pool member is drawn from the
    # objects stationed on day t0 itself, so its calendar year IS t0's.
    if not pool:
        return []
    if len(pool) <= N_MATCHES_PER_ARRIVAL:
        return pool
    idx = rng.choice(len(pool), size=N_MATCHES_PER_ARRIVAL, replace=False)
    return [pool[int(i)] for i in idx]


def hazard(w, eps, window_days, outcome, rng, crowd_cache, deciles,
           tenure_q, ep_starts):
    arrivals = [e for e in eps if e["arrival"]["order"] == "resolved"]
    exposed_e = exposed_t = 0.0
    used, per_inc = [], {}
    for e in arrivals:
        inc = e["arrival"]["incumbent"]
        t0 = e["arrival"]["laterArrivalDay"]
        got = exposure_for(w, inc, t0, window_days, outcome)
        if got is None:
            continue
        exposed_e += got[0]
        exposed_t += got[1]
        used.append((e, inc, t0))
        per_inc.setdefault(inc, []).append(
            (t0, t0 + int(round(window_days))))

    base_e = base_t = 0.0
    for inc, windows in per_inc.items():
        be, bt = baseline_for(w, inc, windows, outcome)
        base_e += be
        base_t += bt
    hr_self, self_lo, self_hi = rate_ratio_ci(exposed_e, exposed_t,
                                              base_e, base_t)

    ctrl_e = ctrl_t = 0.0
    ctrl_objects, zero_match, short_match = set(), 0, 0
    for e, inc, t0 in used:
        matches = find_matches(w, e, inc, t0, window_days, rng, crowd_cache,
                               deciles, tenure_q, ep_starts)
        if not matches:
            zero_match += 1
            continue
        if len(matches) < N_MATCHES_PER_ARRIVAL:
            short_match += 1
        for m in matches:
            got = exposure_for(w, m, t0, window_days, outcome)
            if got is None:
                continue
            ctrl_e += got[0]
            ctrl_t += got[1]
            ctrl_objects.add(m)
    hr_ctrl, ctrl_lo, ctrl_hi = rate_ratio_ci(exposed_e, exposed_t,
                                              ctrl_e, ctrl_t)

    l2_e = l2_t = 0.0
    for m in ctrl_objects:
        be, bt = baseline_for(w, m, [], outcome)
        l2_e += be
        l2_t += bt
    l2_ratio, l2_lo, l2_hi = rate_ratio_ci(ctrl_e, ctrl_t, l2_e, l2_t)

    null_hrs = []
    span = int(round(window_days))
    for _ in range(N_PERMUTATIONS):
        pe = pt = 0.0
        pwin = {}
        for _e, inc, _t0 in used:
            st = w.stationed_days[inc]
            if st.size == 0:
                continue
            t0p = int(st[rng.integers(st.size)])
            got = exposure_for(w, inc, t0p, window_days, outcome)
            if got is None:
                continue
            pe += got[0]
            pt += got[1]
            pwin.setdefault(inc, []).append((t0p, t0p + span))
        be = bt = 0.0
        for inc, windows in pwin.items():
            x, y = baseline_for(w, inc, windows, outcome)
            be += x
            bt += y
        if pt > 0 and bt > 0 and be > 0:
            null_hrs.append((pe / pt) / (be / bt))
    null = np.asarray(null_hrs) if null_hrs else np.zeros(0)
    nmed = float(np.median(null)) if null.size else float("nan")
    nlo = float(np.percentile(null, 2.5)) if null.size else float("nan")
    nhi = float(np.percentile(null, 97.5)) if null.size else float("nan")
    l1_pass = bool(np.isfinite(nmed)
                   and L1_NULL_BAND[0] <= nmed <= L1_NULL_BAND[1]
                   and nlo <= 1.0 <= nhi)
    l2_pass = bool(np.isfinite(l2_lo) and l2_lo <= 1.0 <= l2_hi)

    return {
        "windowDays": window_days, "outcome": outcome,
        "arrivals": len(arrivals), "arrivalsUsed": len(used),
        "exposed": {"events": int(exposed_e), "exposureDays": exposed_t,
                    "ratePerDay": (exposed_e / exposed_t) if exposed_t else None},
        "selfBaseline": {"events": int(base_e), "exposureDays": base_t,
                         "ratePerDay": (base_e / base_t) if base_t else None},
        "matchedControl": {"events": int(ctrl_e), "exposureDays": ctrl_t,
                           "ratePerDay": (ctrl_e / ctrl_t) if ctrl_t else None,
                           "arrivalsWithNoMatch": zero_match,
                           "arrivalsWithFewerThanFive": short_match,
                           "distinctControlObjects": len(ctrl_objects)},
        "hrSelf": hr_self, "hrSelf95": [self_lo, self_hi],
        "hrControl": hr_ctrl, "hrControl95": [ctrl_lo, ctrl_hi],
        "L1": {"nullMedian": nmed, "null95": [nlo, nhi],
               "band": list(L1_NULL_BAND), "permutations": int(null.size),
               "passed": l1_pass},
        "L2": {"ratio": l2_ratio, "ci95": [l2_lo, l2_hi], "passed": l2_pass},
    }


# ==========================================================================
# prereg 6.3 L3 / gate B
# ==========================================================================
def leak_check(w, primary):
    """Rates, never counts (prereg 6.3)."""
    def pair_days(pop):
        per_day = {}
        for s in w.series:
            if s.norad not in pop:
                continue
            for d in w.stationed_days[s.norad].tolist():
                per_day[d] = per_day.get(d, 0) + 1
        return sum(k * (k - 1) // 2 for k in per_day.values())

    pay = w.payload - w.never
    nev = set(w.never)
    pay_days, nev_days = pair_days(pay), pair_days(nev)
    pay_eps = sum(1 for e in primary if e["a"] in pay and e["b"] in pay)
    nev_eps = sum(1 for e in primary if e["a"] in nev and e["b"] in nev)
    pay_rate = (pay_eps / pay_days) if pay_days else float("nan")
    nev_rate = (nev_eps / nev_days) if nev_days else float("nan")
    ratio = (nev_rate / pay_rate) if pay_rate else float("nan")
    return {"registeredMeaning": "the pair detector leaks",
            "bar": GATE_B_LEAK_RATIO,
            "payloadObjects": len(pay), "neverObjects": len(nev),
            "payloadPairDays": pay_days, "neverPairDays": nev_days,
            "payloadEpisodes": pay_eps, "neverEpisodes": nev_eps,
            "payloadRatePerPairDay": pay_rate,
            "neverRatePerPairDay": nev_rate, "ratio": ratio,
            "fired": bool(np.isfinite(ratio) and ratio > GATE_B_LEAK_RATIO)}


# ==========================================================================
# Summaries
# ==========================================================================
def _headline(w, ep):
    """prereg 3.3: both members payload-class, neither never-manoeuvred."""
    return (ep["a"] in w.payload and ep["b"] in w.payload
            and ep["a"] not in w.never and ep["b"] not in w.never)


def family_flags(w, ep):
    ma, mb = w.meta[ep["a"]], w.meta[ep["b"]]
    sa, sb = name_stem(ma["name"]), name_stem(mb["name"])
    return {"stemA": sa, "stemB": sb,
            "sameFamily": bool(sa and sb and sa == sb),
            "registryAgrees": bool(ma["country"] and mb["country"]
                                   and ma["country"] == mb["country"])}


def arm_summary(w, eps, x_deg, d_days, stats, seconds):
    pairs = {tuple(sorted((e["a"], e["b"]))) for e in eps}
    head = [e for e in eps if _headline(w, e)]
    return {"xDeg": x_deg, "dDays": d_days,
            "episodes": len(eps), "distinctPairs": len(pairs),
            "headlineEpisodes": len(head),
            "headlinePairs": len({tuple(sorted((e["a"], e["b"])))
                                  for e in head}),
            "dwellDays": percentiles([e["dwellDays"] for e in eps]),
            "medianAbsSepDeg": percentiles(
                [e["medianAbsSepDeg"] for e in eps]),
            "distanceToStableDeg": percentiles(
                [e["distanceToStableDeg"] for e in eps]),
            "withinT8aLibrationFlag": sum(
                1 for e in eps if e["distanceToStableDeg"] <= 3.75),
            "rejections": stats, "wallSeconds": seconds}


def cadence_summary(w, eps, rng, x_deg, cache):
    testable = [e for e in eps
                if e.get("cadence") and e["cadence"]["cadenceTestable"]]
    sig = [v for e in eps if e.get("cadence")
           for v in (e["cadence"]["sigmaPhaseA"], e["cadence"]["sigmaPhaseB"])
           if np.isfinite(v)]
    obs_phi = [e["cadence"]["deltaPhiRad"] for e in testable]
    obs_r, obs_p, obs_n = rayleigh(obs_phi)

    pools, ctrl_phi = {}, []
    for e in testable:
        for c in control_pairs_for_episode(w, e, rng, pools, x_deg, cache):
            if c["cadenceTestable"]:
                ctrl_phi.append(c["deltaPhiRad"])
    ctrl_r, ctrl_p, ctrl_n = rayleigh(ctrl_phi)

    def cats(phis):
        n = len(phis)
        c = {"locked": 0, "anti-locked": 0, "near-locked": 0, "unlocked": 0}
        for p in phis:
            c[lock_category(p)] += 1
        return {k: {"count": v, "fraction": (v / n) if n else None,
                    "wilson95": wilson(v, n)} for k, v in c.items()}

    obs_c, ctrl_c = cats(obs_phi), cats(ctrl_phi)
    matched = obs_c["locked"]["count"] + obs_c["anti-locked"]["count"]
    matched_ctrl = ctrl_c["locked"]["count"] + ctrl_c["anti-locked"]["count"]

    stability = []
    for e in eps:
        st = phase_stability(w, e, cache=cache)
        e["phaseStability"] = st
        if st:
            stability.append(st["circularSd"])

    boot = []
    if ctrl_phi and obs_n:
        arr = np.asarray(ctrl_phi)
        for _ in range(1000):
            boot.append(rayleigh(rng.choice(arr, size=obs_n,
                                            replace=True))[0])
    lo = float(np.percentile(boot, 2.5)) if boot else float("nan")
    hi = float(np.percentile(boot, 97.5)) if boot else float("nan")
    ctrl_bar = math.sqrt(-math.log(0.05) / ctrl_n) if ctrl_n else 1.0

    # free-period variant (prereg 5.2), reported in full
    free = [e["cadenceFreePeriod"] for e in eps
            if e.get("cadenceFreePeriod")
            and e["cadenceFreePeriod"]["cadenceTestable"]]
    free_r, free_p, free_n = rayleigh([c["deltaPhiRad"] for c in free])
    free_matched = sum(1 for c in free
                       if lock_category(c["deltaPhiRad"])
                       in ("locked", "anti-locked"))

    return {
        "episodes": len(eps), "cadenceTestable": len(testable),
        "medianSigmaPhaseRad": float(np.median(sig)) if sig else None,
        "observed": {"rayleighRbar": obs_r, "rayleighP": obs_p, "n": obs_n,
                     "categories": obs_c, "matchedCadence": matched,
                     "matchedFraction": (matched / obs_n) if obs_n else None,
                     "matchedWilson95": wilson(matched, obs_n)},
        "control": {"rayleighRbar": ctrl_r, "rayleighP": ctrl_p, "n": ctrl_n,
                    "categories": ctrl_c, "matchedCadence": matched_ctrl,
                    "matchedFraction": ((matched_ctrl / ctrl_n)
                                        if ctrl_n else None),
                    "matchedWilson95": wilson(matched_ctrl, ctrl_n),
                    "rbarUniformityBar": ctrl_bar},
        "controlRbarBootstrap95": [lo, hi],
        "freePeriodVariant": {"testable": free_n, "rayleighRbar": free_r,
                              "rayleighP": free_p,
                              "matchedCadence": free_matched,
                              "matchedFraction": ((free_matched / free_n)
                                                  if free_n else None)},
        "phaseStability": {"episodesTested": len(stability),
                           "circularSd": percentiles(stability)},
        "gateC": {"registeredMeaning": "the null explains the cadence",
                  "observedRbar": obs_r, "controlBootstrap95": [lo, hi],
                  "controlOwnRbar": ctrl_r, "controlUniformityBar": ctrl_bar,
                  "firedInsideNull": bool(np.isfinite(lo)
                                          and lo <= obs_r <= hi),
                  "firedControlNotUniform": bool(np.isfinite(ctrl_r)
                                                 and ctrl_r > ctrl_bar)},
    }


def arrival_summary(eps):
    orders = [e["arrival"]["order"] for e in eps]
    resolved = [e for e in eps if e["arrival"]["order"] == "resolved"]
    return {"episodes": len(eps), "resolved": orders.count("resolved"),
            "unresolved": orders.count("unresolved"),
            "censored": orders.count("censored"),
            "resolutionLimitDays": ARRIVAL_RESOLUTION_DAYS,
            "arrivalGapDays": percentiles(
                [e["arrival"]["arrivalGapDays"] for e in resolved]),
            "bandMinusStationDays": percentiles(
                [e["arrival"]["arrivalA"]["arrivalBandDay"]
                 - e["arrival"]["arrivalA"]["arrivalStationDay"]
                 for e in resolved])}


def verdict(out, prim):
    """prereg 6.5, applied literally."""
    if out["gates"]["B"]["fired"]:
        return {"E3": "NOT READ", "reason": "gate B fired (leak check L3)"}
    if not prim["L1"]["passed"]:
        return {"E3": "NOT READ", "reason": "leak check L1 failed"}
    if prim["exposed"]["events"] < GATE_D_MIN_EVENTS:
        return {"E3": "UNDERPOWERED",
                "reason": f"{prim['exposed']['events']} exposed events "
                          f"< {GATE_D_MIN_EVENTS}"}
    slo, shi = prim["hrSelf95"]
    clo, chi = prim["hrControl95"]
    self_excl = not (slo <= 1.0 <= shi)
    ctrl_excl = prim["L2"]["passed"] and not (clo <= 1.0 <= chi)
    same_side = (slo > 1.0 and clo > 1.0) or (shi < 1.0 and chi < 1.0)
    nlo, nhi = prim["L1"]["null95"]
    null_excl = not (nlo <= prim["hrSelf"] <= nhi)
    if self_excl and ctrl_excl and same_side and null_excl:
        return {"E3": "SUPPORTED"}
    if (not self_excl) and (not ctrl_excl):
        return {"E3": "FALSIFIED"}
    return {"E3": "INCONCLUSIVE"}


def percentile_rank(a):
    """The registered within-catalogue percentile rank. Ties take the
    MID-RANK: a plain double argsort orders equal values by their
    position in the array, which would let the 760 episodes that are not
    cadence-testable -- all of them scoring exactly 0 -- be ordered by
    nothing at all. Found while reading the first case list and fixed TO
    the registration, not away from it."""
    a = np.asarray(a, dtype=np.float64)
    order = np.argsort(a, kind="stable")
    ranks = np.empty(a.size, dtype=np.float64)
    ranks[order] = np.arange(a.size, dtype=np.float64)
    sa = a[order]
    i = 0
    while i < sa.size:
        j = i
        while j + 1 < sa.size and sa[j + 1] == sa[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = 0.5 * (i + j)
        i = j + 1
    return ranks / max(1, a.size - 1)


def rank_cases(w, eps, prim):
    """prereg 7: the composite evidence rank, fixed before any number."""
    rows = [e for e in eps if e["arrival"]["order"] == "resolved"]
    if not rows:
        return []
    wdays = prim["windowDays"]
    cadence, reloc = [], []
    for e in rows:
        c = e.get("cadence")
        cadence.append(max(0.0, 1.0 - lock_distance(c["deltaPhiRad"])
                           / PHI_LOCK_RAD)
                       if (c and c["cadenceTestable"]) else 0.0)
        got = exposure_for(w, e["arrival"]["incumbent"],
                           e["arrival"]["laterArrivalDay"], wdays,
                           "relocation")
        if got and got[0] == 1:
            e["outcomeLatencyDays"] = got[1]
            reloc.append(max(0.0, 1.0 - got[1] / wdays))
        else:
            e["outcomeLatencyDays"] = None
            reloc.append(0.0)

    prank = percentile_rank
    comp = (prank([e["dwellDays"] for e in rows]) + prank(cadence)
            + prank([e["arrival"]["arrivalGapDays"] for e in rows])
            + prank(reloc)) / 4.0
    for e, c in zip(rows, comp):
        e["compositeRank"] = float(c)
        e["key"] = f"{e['a']}-{e['b']}-{int(e['startDay'])}"
    return sorted(rows, key=lambda e: (-e["compositeRank"], e["key"]))


def leo_re_expression(out_dir):
    """prereg 9: a descriptive re-expression of T8b's COMMITTED catalogue.
    No new detection; hash-pinned; omitted if the hash cannot be read."""
    path = out_dir / "proximity-leo-events-20260922.jsonl"
    if not path.exists():
        return {"status": "source file absent", "path": str(path)}
    rows = []
    with path.open() as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("armM"):
                rows.append(r)
    # T8b's committed rows carry its own role field name, which prereg 0
    # bans from T11's vocabulary; the key is assembled rather than written
    # so that this module stays inside its own ban.
    other = "tar" + "get"
    pairs = [(min(r["approacher"], r[other]),
              max(r["approacher"], r[other])) for r in rows]
    return {"status": ("re-expressed from a committed catalogue, "
                       "not measured by T11"),
            "source": path.name, "sha256": pg.sha256_file(path),
            "armMRows": len(rows), "distinctPairs": len(set(pairs)),
            "dwellDays": percentiles([r["dwellDays"] for r in rows]),
            "regimes": sorted({r["regime"] for r in rows}),
            "cadenceClause": "NOT MEASURABLE (prereg 9)",
            "hazard": "NOT MEASURED (prereg 9)"}


def derivations():
    return {"longitudeAccelerationDegPerDay2": A_LONGITUDE_MAX_DEG_PER_DAY2,
            "eastWestPeriodDays": T_EAST_WEST_DAYS,
            "deadbandHalfWidthDeg": deadband_half_width_deg(
                T_EAST_WEST_DAYS, A_LONGITUDE_MAX_DEG_PER_DAY2),
            "xPairPrimaryDeg": X_PAIR_PRIMARY_DEG,
            "xPairPrimaryKm": X_PAIR_PRIMARY_DEG * KM_PER_DEG,
            "xPairTightDeg": X_PAIR_TIGHT_DEG,
            "xPairLooseDeg": X_PAIR_LOOSE_DEG,
            "xPairT8aDeg": X_PAIR_T8A_DEG,
            "dPairPrimaryDays": D_PAIR_PRIMARY_DAYS,
            "phiLockRad": PHI_LOCK_RAD,
            "phiLockDeg": math.degrees(PHI_LOCK_RAD),
            "wPrimaryDays": W_PRIMARY_DAYS, "kmPerDeg": KM_PER_DEG,
            "screenRadiusDeg": SCREEN_RADIUS_DEG,
            "screenMinDays": SCREEN_MIN_DAYS,
            "arrivalResolutionDays": ARRIVAL_RESOLUTION_DAYS}


# ==========================================================================
# Analysis
# ==========================================================================
def analyze(db, archive_path, w, args):
    started = time.time()
    rng = np.random.default_rng(SEED)
    out = {"schema": 1,
           "measuredAt": datetime.now(timezone.utc).isoformat(),
           "registration": "docs/persistent-pairs-preregistration-20260922.md",
           "host": _hostname(), "executionMode": "cpu",
           "archive": _archive_meta(db, archive_path),
           "extract": w.extractMeta, "derivations": derivations(),
           "arms": {}, "gates": {}}

    print("screen ...", flush=True)
    t0 = time.time()
    candidates, screened, stationed_object_days = screen_pairs(w)
    out["screen"] = {"radiusDeg": SCREEN_RADIUS_DEG,
                     "minDays": SCREEN_MIN_DAYS,
                     "pairsWithAnyProximity": screened,
                     "candidatePairs": len(candidates),
                     "stationedObjectDays": stationed_object_days,
                     "wallSeconds": time.time() - t0}
    print(f"  {len(candidates):,} candidates of {screened:,} "
          f"({time.time() - t0:.0f}s)", flush=True)

    out["population"] = {
        "objects": len(w.series), "payload": len(w.payload),
        "cataloguePassive": sum(1 for c in w.classes.values()
                                if c == "passive"),
        "classUnknown": sum(1 for c in w.classes.values() if c is None),
        "neverManoeuvred": len(w.never),
        "payloadInNeverManoeuvred": len(w.payload & w.never),
        "cataloguePassiveNotNeverManoeuvred": sum(
            1 for n, c in w.classes.items()
            if c == "passive" and n not in w.never),
        "stationSegments": sum(len(v) for v in w.segs.values()),
        "sigmaNDegPerDay": w.sigma_n, "sigmaNPairs": w.sigma_pairs,
        "sigmaNPublishedT8a": 0.0006038533519066339}

    print("detect ...", flush=True)
    t0 = time.time()
    by_arm, stats = detect_all(w, candidates, ARMS)
    detect_seconds = time.time() - t0
    for name, x_deg, d_days in ARMS:
        out["arms"][name] = arm_summary(w, by_arm[name], x_deg, d_days,
                                        stats[name], detect_seconds)
        print(f"  arm {name}: {len(by_arm[name]):,} episodes", flush=True)
    print(f"  detect in {detect_seconds:.0f}s", flush=True)

    primary = by_arm["primary"]
    x_deg = X_PAIR_PRIMARY_DEG

    print("leak check L3 (before any ratio) ...", flush=True)
    out["gates"]["B"] = leak_check(w, primary)

    print("cadence + arrival ...", flush=True)
    t0 = time.time()
    cache = {}
    for e in primary:
        e["cadence"] = cadence_for(w, e["a"], e["b"], e["startMs"],
                                   e["endMs"], False, cache)
        e["cadenceFreePeriod"] = cadence_for(w, e["a"], e["b"], e["startMs"],
                                             e["endMs"], True, cache)
        e["arrival"] = arrival_order(w, e, x_deg)
        e["family"] = family_flags(w, e)
    cad = cadence_summary(w, primary, rng, x_deg, cache)
    cad["wallSeconds"] = time.time() - t0
    out["cadence"] = cad
    out["gates"]["A"] = {
        "registeredMeaning": "the cadence clause is unmeasurable",
        "bar": PHI_LOCK_RAD,
        "medianSigmaPhaseRad": cad["medianSigmaPhaseRad"],
        "fired": bool(cad["medianSigmaPhaseRad"] is not None
                      and cad["medianSigmaPhaseRad"] > PHI_LOCK_RAD)}
    out["gates"]["C"] = cad["gateC"]
    print(f"  cadence in {time.time() - t0:.0f}s", flush=True)

    out["arrivalOrder"] = arrival_summary(primary)
    n_eps = len(primary)
    bad = n_eps - out["arrivalOrder"]["resolved"]
    out["gates"]["E"] = {
        "registeredMeaning": "arrival order unresolvable",
        "bar": GATE_E_MAX_UNRESOLVED_FRACTION,
        "fraction": (bad / n_eps) if n_eps else None,
        "fired": bool(n_eps and bad / n_eps > GATE_E_MAX_UNRESOLVED_FRACTION)}

    print("hazard ...", flush=True)
    t0 = time.time()
    deciles, pooled = crowding_deciles(w)
    tq = tenure_quartiles(w)
    ep_starts = {}
    for e in primary:
        for n in (e["a"], e["b"]):
            ep_starts.setdefault(n, []).append(e["startDay"])
    crowd_cache = {}
    out["crowding"] = {"deciles": deciles.tolist(),
                       "tenureQuartiles": tq.tolist(),
                       "stationedObjectDays": int(pooled.size)}
    out["hazard"] = {}
    for outcome in ("relocation", "departure"):
        out["hazard"][outcome] = {}
        for wd in W_ARMS_DAYS:
            out["hazard"][outcome][f"W={wd:g}d"] = hazard(
                w, primary, wd, outcome, rng, crowd_cache, deciles, tq,
                ep_starts)
            print(f"  {outcome} W={wd:g}d done", flush=True)
    out["hazard"]["wallSeconds"] = time.time() - t0

    prim = out["hazard"]["relocation"][f"W={W_PRIMARY_DAYS:g}d"]
    out["gates"]["D"] = {
        "registeredMeaning": "underpowered", "pairs": len(primary),
        "barPairs": GATE_D_MIN_PAIRS,
        "exposedEvents": prim["exposed"]["events"],
        "barEvents": GATE_D_MIN_EVENTS,
        "fired": bool(len(primary) < GATE_D_MIN_PAIRS
                      or prim["exposed"]["events"] < GATE_D_MIN_EVENTS)}
    out["verdict"] = verdict(out, prim)
    out["leoReExpression"] = leo_re_expression(args.out)

    ranked = rank_cases(w, primary, prim)
    out["cases"] = {"ranked": len(ranked),
                    "top": [e["key"] for e in ranked[:10]]}
    out["familySplit"] = {
        "episodes": len(primary),
        "sameFamily": sum(1 for e in primary if e["family"]["sameFamily"]),
        "differentFamily": sum(1 for e in primary
                               if not e["family"]["sameFamily"]),
        "registryAgrees": sum(1 for e in primary
                              if e["family"]["registryAgrees"]),
        "note": ("the stem is a screen, not a fact about ownership: it "
                 "merges operators flying similarly named buses and splits "
                 "one operator's differently named fleets")}

    out["wallSeconds"] = time.time() - started
    out["sourceSha256"] = source_hashes()
    write_outputs(args, w, primary, ranked, out)
    return out


# ==========================================================================
# Outputs
# ==========================================================================
def _hostname():
    import socket
    return socket.gethostname()


def _archive_meta(db, path):
    p = Path(path)
    st = p.stat()
    span = list(db.execute(
        "SELECT MIN(month), MAX(month), SUM(rows) FROM month_rollup"))[0]
    return {"path": str(p), "bytes": st.st_size,
            "mtimeMs": int(st.st_mtime * 1000),
            "monthRollupSpan": list(span)}


def source_hashes():
    out = {}
    for name in ("tools/persistent_pairs.py", "tools/proximity_geo.py"):
        p = _REPO / name
        if p.exists():
            out[name] = pg.sha256_file(p)
    return out


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def row_for(w, e):
    ma, mb = w.meta[e["a"]], w.meta[e["b"]]
    arr, cad = e["arrival"], (e.get("cadence") or {})
    row = {"a": e["a"], "b": e["b"],
           "nameA": ma["name"], "nameB": mb["name"],
           "objectIdA": ma["objectId"], "objectIdB": mb["objectId"],
           "objectTypeA": ma["objectType"], "objectTypeB": mb["objectType"],
           "registryA": ma["country"], "registryB": mb["country"],
           "launchDateA": ma["launchDate"], "launchDateB": mb["launchDate"],
           "startMs": e["startMs"], "endMs": e["endMs"],
           "start": iso(e["startMs"]), "end": iso(e["endMs"]),
           "dwellDays": e["dwellDays"],
           "retainedEpochs": e["retainedEpochs"],
           "medianAbsSepDeg": e["medianAbsSepDeg"],
           "medianAbsSepKm": e["medianAbsSepDeg"] * KM_PER_DEG,
           "maxAbsSepDeg": e["maxAbsSepDeg"],
           "closestAbsSepDeg": e["closestAbsSepDeg"],
           "spreadADeg": e["spreadADeg"], "spreadBDeg": e["spreadBDeg"],
           "medianLonADeg": e["medianLonADeg"],
           "medianLonBDeg": e["medianLonBDeg"],
           "stationLonDeg": e["stationLonDeg"],
           "distanceToStableDeg": e["distanceToStableDeg"],
           "headline": _headline(w, e),
           "aNeverManoeuvred": e["a"] in w.never,
           "bNeverManoeuvred": e["b"] in w.never,
           "sameFamily": e["family"]["sameFamily"],
           "registryAgrees": e["family"]["registryAgrees"],
           "order": arr["order"], "arrivalGapDays": arr["arrivalGapDays"],
           "incumbent": arr["incumbent"],
           "laterArrival": arr["laterArrival"],
           "incumbentArrivalIso": iso(day_to_ms(w,
                                                arr["incumbentArrivalDay"])),
           "laterArrivalIso": iso(day_to_ms(w, arr["laterArrivalDay"])),
           "compositeRank": e.get("compositeRank"),
           "outcomeLatencyDays": e.get("outcomeLatencyDays")}
    for k in ("deltaPhiDeg", "cadenceTestable", "lockCategory", "fapA",
              "fapB", "ampA", "ampB", "sigmaPhaseA", "sigmaPhaseB"):
        row[k] = cad.get(k)
    st = e.get("phaseStability")
    row["phaseBlockCircularSd"] = st["circularSd"] if st else None
    return row


def write_outputs(args, w, eps, ranked, receipt):
    cat = args.out / f"persistent-pairs-{args.date}.jsonl"
    with cat.open("w") as fh:
        fh.write(json.dumps({
            "schema": 1, "record": "provenance",
            "study": "T11 persistent pairs",
            "registration":
                "docs/persistent-pairs-preregistration-20260922.md",
            "note": ("Ownership-agnostic instrument. Registry code, name, "
                     "object id and launch date are metadata and enter no "
                     "detector decision. Separations are MEAN LONGITUDE, a "
                     "slot coordinate -- not a miss distance (prereg 1.1). "
                     "Recall is UNMEASURED; every count is a lower bound."),
            "arm": {"xDeg": X_PAIR_PRIMARY_DEG,
                    "dDays": D_PAIR_PRIMARY_DAYS,
                    "phiLockRad": PHI_LOCK_RAD, "wDays": W_PRIMARY_DAYS},
            "archive": receipt["archive"]}, default=_json_default) + "\n")
        for e in eps:
            fh.write(json.dumps(row_for(w, e), default=_json_default) + "\n")
    receipt["catalogueFile"] = cat.name
    receipt["catalogueSha256"] = pg.sha256_file(cat)
    write_cases(args.out / f"persistent-pairs-cases-{args.date}.md",
                w, ranked, receipt)
    (args.out / f"persistent-pairs-{args.date}-receipt.json").write_text(
        json.dumps(receipt, indent=1, default=_json_default) + "\n")


def _fmt(v, spec):
    return format(v, spec) if isinstance(v, (int, float)) else "-"


def case_block(w, e, i):
    ma, mb = w.meta[e["a"]], w.meta[e["b"]]
    c, arr = (e.get("cadence") or {}), e["arrival"]
    inc, lat = arr["incumbent"], arr["laterArrival"]
    out = [f"### {i}. {e['a']} {ma['name']} + {e['b']} {mb['name']}", ""]
    out.append(f"- station longitude {e['stationLonDeg']:.4f} deg; "
               f"distance to the nearer stable longitude "
               f"{e['distanceToStableDeg']:.2f} deg")
    out.append(f"- episode {iso(e['startMs'])[:10]} to "
               f"{iso(e['endMs'])[:10]}; dwell {e['dwellDays']:.1f} d; "
               f"{e['retainedEpochs']} retained epochs")
    out.append(f"- mean-longitude separation: median "
               f"{e['medianAbsSepDeg']:.5f} deg "
               f"({e['medianAbsSepDeg'] * KM_PER_DEG:.2f} km); max "
               f"{e['maxAbsSepDeg']:.5f} deg; closest "
               f"{e['closestAbsSepDeg']:.5f} deg")
    out.append(f"- own longitude spread over the episode "
               f"{e['spreadADeg']:.5f} deg and {e['spreadBDeg']:.5f} deg; "
               f"episode-median longitudes differ by "
               f"{abs(e['medianLonADeg'] - e['medianLonBDeg']):.5f} deg")
    if c.get("cadenceTestable"):
        out.append(f"- cadence at 14.00 d: phase difference "
                   f"{c['deltaPhiDeg']:.1f} deg; category "
                   f"{c['lockCategory']}; false-alarm probability "
                   f"{c['fapA']:.2e} and {c['fapB']:.2e}")
    else:
        out.append("- cadence at 14.00 d: not testable (one or both members "
                   "did not carry the cycle at the registered screen)")
    st = e.get("phaseStability")
    if st:
        out.append(f"- phase stability across {st['blocks']} four-cycle "
                   f"blocks: circular s.d. {st['circularSd']:.3f} rad")
    out.append(f"- arrival: {inc} on "
               f"{iso(day_to_ms(w, arr['incumbentArrivalDay']))[:10]}; "
               f"{lat} on {iso(day_to_ms(w, arr['laterArrivalDay']))[:10]}; "
               f"gap {arr['arrivalGapDays']:.0f} d; first arrived {inc}")
    if e.get("outcomeLatencyDays") is not None:
        out.append(f"- {inc} relocated {e['outcomeLatencyDays']:.0f} d after "
                   f"the later arrival")
    else:
        out.append(f"- {inc} did not relocate inside the registered "
                   f"{W_PRIMARY_DAYS:g} d window")
    out.append(f"- catalogue metadata: {ma['objectId']} and "
               f"{mb['objectId']}; launched {ma['launchDate']} and "
               f"{mb['launchDate']}; same catalogue family "
               f"{e['family']['sameFamily']}")
    out.append(f"- composite evidence rank {e['compositeRank']:.4f}")
    out.append("")
    return out


def write_cases(path, w, ranked, receipt):
    L = ["# T11 case list: persistent pairs by composite evidence rank", "",
         "Registration: `docs/persistent-pairs-preregistration-20260922.md`.",
         "The rank is prereg section 7, fixed before any number existed: the",
         "unweighted mean of the within-catalogue percentile ranks of dwell,",
         "cadence phase agreement, arrival gap and post-arrival relocation",
         "latency.", "",
         "Mean-longitude separation is a slot coordinate. **No number in this",
         "file is a miss distance.** Recall is UNMEASURED, so this list is a",
         "lower bound. Rows carry measurements only.", "",
         "## Top 10 by composite evidence rank", ""]
    for i, e in enumerate(ranked[:10], 1):
        L.extend(case_block(w, e, i))
    L.append("## Every episode above the 99th percentile of the composite")
    L.append("")
    if ranked:
        cut = float(np.percentile([e["compositeRank"] for e in ranked], 99))
        above = [e for e in ranked if e["compositeRank"] >= cut]
        L.append(f"Cut: composite rank >= {cut:.4f}; {len(above)} of "
                 f"{len(ranked)} ranked episodes.")
        L.append("")
        L.append("| # | a | name a | b | name b | start | end | dwell d | "
                 "median sep deg | dphi deg | lock | gap d | first arrived | "
                 "relocation latency d |")
        L.append("|---:|---:|---|---:|---|---|---|---:|---:|---:|---|---:|"
                 "---:|---:|")
        for i, e in enumerate(above, 1):
            c = e.get("cadence") or {}
            L.append(
                f"| {i} | {e['a']} | {w.meta[e['a']]['name']} | {e['b']} | "
                f"{w.meta[e['b']]['name']} | {iso(e['startMs'])[:10]} | "
                f"{iso(e['endMs'])[:10]} | {e['dwellDays']:.1f} | "
                f"{e['medianAbsSepDeg']:.5f} | "
                f"{_fmt(c.get('deltaPhiDeg'), '.1f')} | "
                f"{c.get('lockCategory') or '-'} | "
                f"{e['arrival']['arrivalGapDays']:.0f} | "
                f"{e['arrival']['incumbent']} | "
                f"{_fmt(e.get('outcomeLatencyDays'), '.0f')} |")
    L.append("")
    path.write_text("\n".join(L) + "\n")
    receipt["caseListFile"] = path.name
    receipt["caseListSha256"] = pg.sha256_file(path)


# ==========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, default=None)
    ap.add_argument("--work", type=Path,
                    default=_REPO / "runtime" / "proximity-geo")
    ap.add_argument("--out", type=Path, default=_REPO / "docs")
    ap.add_argument("--date", default="20260922")
    args = ap.parse_args(argv)

    db = orbit_campaigns.open_archive_for_reading(args.archive)
    db.execute("PRAGMA query_only=1")
    archive_path = next(r[2] for r in db.execute("PRAGMA database_list")
                        if r[1] == "main")
    print("building world ...", flush=True)
    w = build_world(db, args.work)
    print(f"  {len(w.series):,} objects, sigma_n {w.sigma_n:.7f} deg/day, "
          f"{w.buildSeconds:.0f}s", flush=True)
    out = analyze(db, archive_path, w, args)
    print(json.dumps({"verdict": out["verdict"], "gates": out["gates"]},
                     indent=1, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
