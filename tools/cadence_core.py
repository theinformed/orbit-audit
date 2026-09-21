"""T3 cadence fingerprints: the registered arithmetic, with no archive and no GPU.

Every definition in this module is the one registered in
`docs/cadence-preregistration-20260921.md` and must not drift from it. Where
the repository already owned a band, a tolerance or an estimator, this module
*borrows* it rather than restating it, exactly as `tools/paperb_strata.py`
does, so a later change cannot leave a silently divergent copy behind:

- the four-factor stratum comes from `tools/paperb_strata.stratum_key`;
- the passive class comes from `pipeline.orbit_events.PASSIVE_TYPES`;
- the rhythm-shift tolerance is `pipeline.orbit_campaigns.REPEAT_RELATIVE_TOLERANCE`;
- the separation bar is `pipeline.orbit_events.MIN_SEPARATION_BOUND_RATIO`;
- Jeffreys intervals come from `pipeline.orbit_events._jeffreys_interval`.

The array functions take an explicit array module (`numpy` or `cupy`), so the
identical code path is what the tests exercise offline and what the GPU runs.
That is deliberate: a GPU kernel that no test can reach is a kernel nobody has
checked.
"""

from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline.orbit_campaigns import REPEAT_RELATIVE_TOLERANCE  # noqa: E402
from pipeline.orbit_events import (  # noqa: E402
    MIN_SEPARATION_BOUND_RATIO,
    PASSIVE_TYPES,
    _jeffreys_interval,
)
from tools.paperb_strata import stratum_key  # noqa: E402

# --------------------------------------------------------------------------
# Registered constants (docs/cadence-preregistration-20260921.md)
# --------------------------------------------------------------------------
SEED = 20260921
SPLIT_SALT = "t3-20260921"

WINDOW_DAYS = 1080.0          # prereg 5.1
STEP_DAYS = 360.0             # prereg 5.1
DETREND_DEGREE = 3            # prereg 5.2

MIN_PERIOD_DAYS = 2.0         # prereg 4
MAX_PERIOD_DAYS = 220.0       # prereg 4
OVERSAMPLE = 5                # prereg 4
MIN_CYCLES_IN_WINDOW = 4.0    # prereg 4

WINDOW_MIN_SAMPLES = 300      # prereg 5.3(1)
WINDOW_MAX_GAP_DAYS = 45.0    # prereg 5.3(2)
WINDOW_MIN_SPAN_FRACTION = 0.90   # prereg 5.3(3)
MEAN_MOTION_QUANTUM = 1e-8    # prereg 5.3(4); SCALE_MEAN_MOTION = 1e8

PRIMARY_PERCENTILE = 99.0     # prereg 6.3
SENSITIVITY_PERCENTILES = (95.0, 99.9)
MIN_CELL_WINDOWS = 200        # prereg 6.4
FDR_Q = 0.05                  # prereg 8.3

CHANGEPOINT_MIN_WINDOWS = 4   # prereg 7
SHIFT_TOLERANCE = REPEAT_RELATIVE_TOLERANCE   # prereg 7.1, borrowed (0.35)

GATE_A_MAX_PASSIVE_FRACTION = 0.02   # prereg 10
GATE_B_INFORMATIVE = MIN_SEPARATION_BOUND_RATIO   # prereg 10, borrowed (10.0)
GATE_B_WEAK = 3.0
GATE_C_MIN_OBJECTS = 20
GATE_C_MIN_SIGNIFICANT_WINDOWS = 3

# Physical constants, WGS-84 / IERS, used for banding and for the interpretive
# semi-major-axis conversion only -- never on the analysed signal (prereg 3.2).
MU_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6378.137

DAY_MS = 86400000.0

# Sample-count bands (prereg 6.3), octave bins. Lower-inclusive.
N_BAND_EDGES = ((600, "300-600"), (1200, "600-1200"), (2400, "1200-2400"),
                (4800, "2400-4800"), (math.inf, ">=4800"))
# Usable-window-count bands (prereg 8.2). Lower-inclusive.
WINDOW_COUNT_BAND_EDGES = ((4, "2-3"), (8, "4-7"), (16, "8-15"), (math.inf, ">=16"))


def n_band(n_samples: int) -> str:
    for edge, label in N_BAND_EDGES:
        if n_samples < edge:
            return label
    return N_BAND_EDGES[-1][1]


def window_count_band(count: int) -> str:
    for edge, label in WINDOW_COUNT_BAND_EDGES:
        if count < edge:
            return label
    return WINDOW_COUNT_BAND_EDGES[-1][1]


def split_half(norad: int) -> str:
    """Registered calibration/audit split (prereg 6.2), by OBJECT, never window.

    sha256 of a fixed salt and the NORAD; even first 8 hex digits -> calibration.
    Deterministic, reproducible from this line alone, and independent of any
    ordering the measurement pass happens to use.
    """
    digest = hashlib.sha256(f"{SPLIT_SALT}:{int(norad)}".encode()).hexdigest()
    return "calibration" if int(digest[:8], 16) % 2 == 0 else "audit"


def semi_major_axis_km(mean_motion_rev_per_day: float) -> float:
    """a from the archived mean motion, by the Kepler relation.

    Registered (prereg 3.2) as an INTERPRETIVE conversion and as the banding
    input -- never as the analysed channel. The TLE mean motion is a Brouwer
    mean element, so this is the Kepler-equivalent semi-major axis and differs
    from the osculating value by terms of order J2; that offset is smooth in
    (a, e, i) and so is a trend, not an in-band rhythm, which is exactly why
    the analysed channel is n itself.
    """
    n_rad_s = mean_motion_rev_per_day * 2.0 * math.pi / 86400.0
    return (MU_KM3_S2 / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)


def perigee_km(mean_motion_rev_per_day: float, eccentricity: float) -> float:
    return semi_major_axis_km(mean_motion_rev_per_day) * (1.0 - eccentricity) - EARTH_RADIUS_KM


def frequency_grid() -> np.ndarray:
    """The registered grid (prereg 4): uniform in frequency, identical for every window.

    Closed form, evaluated the same way for every object, so no object can be
    given a grid tuned to it.
    """
    f_min = 1.0 / MAX_PERIOD_DAYS
    f_max = 1.0 / MIN_PERIOD_DAYS
    df = 1.0 / (OVERSAMPLE * WINDOW_DAYS)
    count = int(math.floor((f_max - f_min) / df)) + 1
    grid = f_min + df * np.arange(count, dtype=np.float64)
    # Registered cycle-count floor: every searched frequency completes at least
    # MIN_CYCLES_IN_WINDOW cycles. It binds nothing at the registered band, and
    # is asserted rather than applied so that a later band change cannot slip
    # past it silently.
    assert grid[0] * WINDOW_DAYS >= MIN_CYCLES_IN_WINDOW, "grid violates the registered cycle floor"
    return grid


# --------------------------------------------------------------------------
# Windowing and admissibility (prereg 5)
# --------------------------------------------------------------------------
def window_bounds(first_ms: int, last_ms: int) -> list[tuple[float, float]]:
    """Fixed-length windows tiled forward from the object's first epoch.

    A window is emitted only if its END is at or before the last epoch, so a
    trailing part-window is never analysed as if it were a full one.
    """
    span = (last_ms - first_ms) / DAY_MS
    out = []
    start = 0.0
    while start + WINDOW_DAYS <= span + 1e-9:
        out.append((start, start + WINDOW_DAYS))
        start += STEP_DAYS
    return out


def window_admissible(times_days: np.ndarray, values: np.ndarray) -> tuple[bool, str]:
    """The four registered admissibility conditions (prereg 5.3), in order."""
    n = times_days.size
    if n < WINDOW_MIN_SAMPLES:
        return False, "samples"
    gaps = np.diff(times_days)
    if gaps.size and float(gaps.max()) > WINDOW_MAX_GAP_DAYS:
        return False, "gap"
    if float(times_days[-1] - times_days[0]) < WINDOW_MIN_SPAN_FRACTION * WINDOW_DAYS:
        return False, "span"
    if float(values.max() - values.min()) <= MEAN_MOTION_QUANTUM:
        return False, "constant"
    return True, ""


# --------------------------------------------------------------------------
# Detrending (prereg 5.2)
# --------------------------------------------------------------------------
def detrend_batch(times, values, mask, xp, degree=DETREND_DEGREE):
    """Subtract the masked least-squares polynomial of `degree` from each row.

    `times` (B, N) in days measured from each window's own start, `values`
    (B, N), `mask` (B, N) in {0, 1}. Time is normalised to u in [-1, 1] across
    the registered window length before the fit, so the 4x4 normal-equation
    system is well conditioned regardless of the epoch scale.
    """
    u = (2.0 * times / WINDOW_DAYS) - 1.0
    u = u * mask
    powers = [xp.ones_like(u) * mask]
    for _ in range(degree):
        powers.append(powers[-1] * u)
    basis = xp.stack(powers, axis=1)                 # (B, degree+1, N)
    gram = basis @ xp.swapaxes(basis, 1, 2)          # (B, d+1, d+1)
    rhs = basis @ (values * mask)[:, :, None]        # (B, d+1, 1)
    # A masked window can still be rank-deficient in principle; a tiny ridge on
    # the diagonal keeps the solve total without moving a well-posed answer.
    eye = xp.eye(degree + 1, dtype=gram.dtype)[None, :, :]
    coeffs = xp.linalg.solve(gram + 1e-10 * eye, rhs)     # (B, d+1, 1)
    fitted = (xp.swapaxes(basis, 1, 2) @ coeffs)[:, :, 0]
    return (values - fitted) * mask


# --------------------------------------------------------------------------
# Generalised Lomb-Scargle (prereg 4)
# --------------------------------------------------------------------------
def gls_power(times, values, mask, freqs, xp, chunk=64):
    """Batched generalised Lomb-Scargle power, Zechmeister & Kurster 2009.

    Returns (B, F) power in [0, 1], the fraction of the window's variance the
    best-fitting sinusoid-plus-floating-mean explains at each frequency.

    GENERALISED rather than classical: the floating mean is fitted alongside the
    sinusoid. A classical periodogram assumes the mean is known to be zero, and
    after a polynomial detrend over a masked, irregularly sampled window it is
    only approximately zero -- which biases classical power upward at low
    frequency, precisely where this track looks.

    Uniform weights: the archive publishes no per-element uncertainty, so
    inventing one would be a fabricated covariance. w_i = mask_i / sum(mask).

    cos^2, sin^2 and cos*sin come from the double-angle identities on the single
    (cos, sin) pair rather than from further trigonometric calls, so each
    (window, sample, frequency) triple costs one sine and one cosine.

    NO MATRIX PRODUCT IS TAKEN. The ragged rows are padded with t = 0 and
    y = 0, so a padded sample contributes cos = 1, sin = 0, cos(2wt) = 1,
    sin(2wt) = 0 -- a constant that is subtracted exactly, by count, from the
    plain column sums. That turns every reduction into an unweighted sum and
    removes the dependency on cuBLAS, which this environment's CuPy wheel set
    does not ship. It is exact, not an approximation.
    """
    times = xp.asarray(times)
    mask = xp.asarray(mask)
    # Enforce the padding precondition rather than trusting the caller: a
    # nonzero value behind the mask would silently corrupt every sum below.
    times = times * mask
    values = xp.asarray(values) * mask

    width = times.shape[1]
    counts = mask.sum(axis=1)                            # (B,)
    padding = (width - counts)[:, None]                  # (B, 1)
    inv = 1.0 / xp.maximum(counts, 1.0)
    y_mean = (values.sum(axis=1)) * inv                  # (B,)
    yy = (values * values).sum(axis=1) * inv - y_mean * y_mean

    out = xp.empty((times.shape[0], freqs.shape[0]), dtype=times.dtype)
    two_pi = 2.0 * math.pi
    for lo in range(0, int(freqs.shape[0]), chunk):
        block = freqs[lo:lo + chunk]
        phase = (two_pi * times)[:, :, None] * block[None, None, :]
        cos = xp.cos(phase)
        sin = xp.sin(phase)
        sum_sin2 = (2.0 * sin * cos).sum(axis=1)
        sum_cos2 = (1.0 - 2.0 * sin * sin).sum(axis=1) - padding
        sum_cos = cos.sum(axis=1) - padding
        sum_sin = sin.sum(axis=1)
        cos *= values[:, :, None]
        sum_ycos = cos.sum(axis=1)
        sin *= values[:, :, None]
        sum_ysin = sin.sum(axis=1)
        del cos, sin

        iv = inv[:, None]
        c = sum_cos * iv
        s = sum_sin * iv
        yc = sum_ycos * iv - y_mean[:, None] * c
        ys = sum_ysin * iv - y_mean[:, None] * s
        c2 = sum_cos2 * iv
        s2 = sum_sin2 * iv

        cc = 0.5 * (1.0 + c2) - c * c
        ss = 0.5 * (1.0 - c2) - s * s
        cs = 0.5 * s2 - c * s
        det = cc * ss - cs * cs

        num = ss * yc * yc + cc * ys * ys - 2.0 * cs * yc * ys
        den = yy[:, None] * det
        power = xp.where(den > 0, num / xp.where(den > 0, den, 1.0), 0.0)
        # Power is a variance fraction; numerical noise can push it a hair
        # outside [0, 1] on a near-degenerate window. Clip rather than hide.
        out[:, lo:lo + chunk] = xp.clip(power, 0.0, 1.0)
    return out


# --------------------------------------------------------------------------
# Benjamini-Hochberg (prereg 8.3)
# --------------------------------------------------------------------------
def benjamini_hochberg(pvalues: Sequence[float], q: float = FDR_Q) -> np.ndarray:
    """Boolean rejection vector controlling the false discovery rate at q.

    BH rather than Bonferroni because the registered question is "what fraction
    of payloads have a rhythm" -- a fraction-of-discoveries question, which is
    what BH controls. Ties are handled by the standard step-up: the largest k
    with p_(k) <= k*q/m rejects every hypothesis at or below it.
    """
    p = np.asarray(pvalues, dtype=float)
    m = p.size
    if m == 0:
        return np.zeros(0, dtype=bool)
    order = np.argsort(p, kind="stable")
    ranked = p[order]
    thresholds = (np.arange(1, m + 1) * q) / m
    passing = np.nonzero(ranked <= thresholds)[0]
    reject = np.zeros(m, dtype=bool)
    if passing.size:
        reject[order[: passing[-1] + 1]] = True
    return reject


def empirical_pvalue(statistic: float, reference: np.ndarray) -> float:
    """(1 + #{reference >= statistic}) / (1 + n), the conservative finite-set form.

    The +1 in both places is what keeps a p-value from ever being reported as
    exactly zero on a finite reference set; the floor 1/(1+n) is real and the
    caller is required to report where it binds (prereg 8.3).
    """
    reference = np.asarray(reference, dtype=float)
    return float(1 + int(np.sum(reference >= statistic))) / float(1 + reference.size)


__all__ = [
    "SEED", "SPLIT_SALT", "WINDOW_DAYS", "STEP_DAYS", "DETREND_DEGREE",
    "MIN_PERIOD_DAYS", "MAX_PERIOD_DAYS", "OVERSAMPLE", "WINDOW_MIN_SAMPLES",
    "WINDOW_MAX_GAP_DAYS", "WINDOW_MIN_SPAN_FRACTION", "PRIMARY_PERCENTILE",
    "SENSITIVITY_PERCENTILES", "MIN_CELL_WINDOWS", "FDR_Q",
    "CHANGEPOINT_MIN_WINDOWS", "SHIFT_TOLERANCE", "GATE_A_MAX_PASSIVE_FRACTION",
    "GATE_B_INFORMATIVE", "GATE_B_WEAK", "GATE_C_MIN_OBJECTS",
    "GATE_C_MIN_SIGNIFICANT_WINDOWS", "PASSIVE_TYPES", "MIN_SEPARATION_BOUND_RATIO",
    "stratum_key", "_jeffreys_interval", "n_band", "window_count_band",
    "split_half", "semi_major_axis_km", "perigee_km", "frequency_grid",
    "window_bounds", "window_admissible", "detrend_batch", "gls_power",
    "benjamini_hochberg", "empirical_pvalue", "DAY_MS",
]
