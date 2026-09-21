"""Paper B: covariate strata, exact ratio statistics, and the reweighting.

Everything in this module is pure arithmetic over counts. It reads no archive
and opens no connection, so `tools/paperb_selftest.py` exercises all of it
offline. The measurement program (`tools/paperb_measure.py`) supplies the
counts; the report program (`tools/paperb_analyze.py`) consumes the results.

Every definition here is the one registered in
`docs/paperb-preregistration-20260920.md` and must not drift from it. Where the
repository already owned a band or an estimator, this module *borrows* it rather
than restating it, so a later change to the detector's own bands cannot leave a
silently divergent copy behind:

- perigee bands come from `orbit_campaigns._perigee_band`;
- Jeffreys intervals come from `orbit_events._jeffreys_interval`;
- the regularised incomplete beta comes from `orbit_events`.

The two things this module does add are the eccentricity banding (registered as
decade boundaries, never tuned) and the exact conditional ratio statistics,
which the repository did not previously have in any form. The published control
compares two rates with a pooled normal approximation and says in its own
`caution` field that this is an order-of-magnitude statement; an equivalence
claim cannot be built on that, so the ratio work here is exact throughout.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Iterable, Sequence

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pipeline.orbit_campaigns import _perigee_band  # noqa: E402
from pipeline.orbit_events import (  # noqa: E402
    _jeffreys_interval,
    _regularised_incomplete_beta,
)

# --------------------------------------------------------------------------
# Registered bands. Edges are lower-inclusive, upper-exclusive; the final
# inclination band includes 180 degrees exactly.
# --------------------------------------------------------------------------

INCLINATION_EDGES: tuple[tuple[float, str], ...] = (
    (1.0, "0-1"),
    (5.0, "1-5"),
    (15.0, "5-15"),
    (30.0, "15-30"),
    (60.0, "30-60"),
    (90.0, "60-90"),
    (120.0, "90-120"),
    (181.0, "120-180"),
)

ECCENTRICITY_EDGES: tuple[tuple[float, str], ...] = (
    (0.001, "<0.001"),
    (0.01, "0.001-0.01"),
    (0.1, "0.01-0.1"),
    (math.inf, ">=0.1"),
)

# The interval span IS the gap between the two TLE epochs it was built from, so
# this factor is the TLE update cadence and not a proxy for it. Bounded below by
# MINIMUM_SPAN_DAYS (0.1) and above by MAXIMUM_JOINABLE_GAP_DAYS (3.0), so the
# four classes cover the whole admissible range with nothing outside them.
CADENCE_EDGES: tuple[tuple[float, str], ...] = (
    (0.25, "<0.25 d"),
    (1.0, "0.25-1 d"),
    (2.0, "1-2 d"),
    (math.inf, ">=2 d"),
)

PERIGEE_BANDS: tuple[str, ...] = (
    "<300 km", "300-500 km", "500-800 km", "800-1200 km", "1200-2000 km", ">2000 km",
)
INCLINATION_BANDS: tuple[str, ...] = tuple(label for _, label in INCLINATION_EDGES)
ECCENTRICITY_CLASSES: tuple[str, ...] = tuple(label for _, label in ECCENTRICITY_EDGES)
CADENCE_CLASSES: tuple[str, ...] = tuple(label for _, label in CADENCE_EDGES)

# Registered geometric definition of the sun-synchronous band for Analysis 2c.
# Fixed, not fitted: it is the inclination range the SSO family occupies at LEO
# altitudes, and the 2-degree curve bins of Analysis 2a align with both edges.
SSO_MIN_DEG = 96.0
SSO_MAX_DEG = 100.0

# Analysis 2a bin widths.
CURVE_BIN_DEG = 2.0
ZOOM_BIN_DEG = 0.2
ZOOM_MAX_DEG = 2.0

# The published control's own target, restated here only so the decision rule
# has a named constant rather than a literal buried in a comparison.
TARGET_RATE_PER_INTERVAL = 0.001

HIGH_INCLINATION_MIN_DEG = 30.0
EQUIVALENCE_MARGIN = 1.5
BOOTSTRAP_DRAWS = 2000
POSTERIOR_DRAWS = 20000
SEED = 20260920


def _band(value: float, edges: Sequence[tuple[float, str]]) -> str:
    for edge, label in edges:
        if value < edge:
            return label
    return edges[-1][1]


def inclination_band(degrees: float) -> str:
    return _band(degrees, INCLINATION_EDGES)


def eccentricity_class(eccentricity: float) -> str:
    return _band(eccentricity, ECCENTRICITY_EDGES)


def cadence_class(span_days: float) -> str:
    return _band(span_days, CADENCE_EDGES)


def perigee_band(perigee_km: float | None) -> str:
    return _perigee_band(perigee_km)


def stratum_key(
    perigee_km: float | None, inclination_deg: float, eccentricity: float, span_days: float
) -> str:
    """The registered four-factor stratum, as one stable string key.

    A string rather than a tuple because these keys are written to JSONL and
    read back; round-tripping a tuple through JSON turns it into a list and
    then silently fails to match a dict built from tuples. That failure mode is
    exactly the kind that produces a wrong number with no error, so the key is
    a string on both sides of the file.
    """
    return "|".join((
        perigee_band(perigee_km),
        inclination_band(inclination_deg),
        eccentricity_class(eccentricity),
        cadence_class(span_days),
    ))


def coarse_key(stratum: str) -> str:
    """Sensitivity B: the same stratum collapsed to perigee x inclination."""
    parts = stratum.split("|")
    return "|".join(parts[:2])


def curve_bin(degrees: float) -> int:
    """Index of the 2-degree Analysis-2a bin containing this inclination."""
    if degrees >= 180.0:
        return int(180.0 / CURVE_BIN_DEG) - 1
    return int(max(degrees, 0.0) // CURVE_BIN_DEG)


def curve_bin_bounds(index: int) -> tuple[float, float]:
    return index * CURVE_BIN_DEG, (index + 1) * CURVE_BIN_DEG


def zoom_bin(degrees: float) -> int | None:
    if degrees >= ZOOM_MAX_DEG or degrees < 0.0:
        return None
    return int(degrees // ZOOM_BIN_DEG)


def is_sso(degrees: float) -> bool:
    return SSO_MIN_DEG <= degrees < SSO_MAX_DEG


# --------------------------------------------------------------------------
# Single-rate statistics
# --------------------------------------------------------------------------


def jeffreys(flags: int, intervals: int, level: float = 0.95) -> tuple[float, float]:
    """Equal-tailed Jeffreys interval, borrowed from the published control.

    Zero flags gives a non-zero upper bound, which is the entire reason this
    estimator and not Wald: a stratum with no observed false alarm has not
    demonstrated a false-alarm rate of zero, it has demonstrated a bound.
    """
    return _jeffreys_interval(flags, intervals, level)


def rate_per_1000(flags: int, intervals: int) -> float:
    return 0.0 if intervals <= 0 else 1000.0 * flags / intervals


# --------------------------------------------------------------------------
# Exact conditional ratio statistics
# --------------------------------------------------------------------------
#
# Two independent Poisson counts k_P ~ Poisson(lambda_P E_P) and
# k_L ~ Poisson(lambda_L E_L). Conditioning on the total N = k_P + k_L removes
# the nuisance rate entirely and leaves
#
#     k_L | N  ~  Binomial(N, p(theta)),  p(theta) = theta E_L / (theta E_L + E_P)
#
# with theta = lambda_L / lambda_P the payload-to-passive rate ratio. Every
# ratio interval and every equivalence test below is an exact binomial
# statement about that one parameter. No normal approximation appears anywhere
# in this section, which matters because several bins of the inclination curve
# hold single-digit counts where a normal approximation is simply wrong.


def _binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), via the beta identity."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    return _regularised_incomplete_beta(n - k, k + 1, 1.0 - p)


def _binomial_sf_inclusive(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    return _regularised_incomplete_beta(k, n - k + 1, p)


def _beta_quantile(a: float, b: float, target: float) -> float:
    """Inverse regularised incomplete beta by bisection.

    Same technique, and the same 200 halvings, as the repository's Jeffreys
    interval: this pipeline runs on a plain interpreter with no SciPy, and a
    dependency added for one quantile would be a dependency the release has to
    carry forever.
    """
    if a <= 0.0:
        return 0.0
    if b <= 0.0:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2.0
        if _regularised_incomplete_beta(a, b, mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _theta_from_p(p: float, exposure_passive: float, exposure_payload: float) -> float:
    if p >= 1.0:
        return math.inf
    if p <= 0.0:
        return 0.0
    return (p / (1.0 - p)) * (exposure_passive / exposure_payload)


def ratio_interval(
    flags_passive: int,
    exposure_passive: float,
    flags_payload: int,
    exposure_payload: float,
    level: float = 0.95,
) -> dict:
    """Exact conditional interval for theta = payload rate / passive rate.

    Clopper-Pearson on the conditional binomial, mapped back to theta. Returns
    `None` bounds rather than a number where the data cannot support one: no
    flags at all in either population is not a ratio of one, and a zero count on
    one side gives a genuinely one-sided bound. Callers must label those cases
    rather than plot them.
    """
    total = flags_passive + flags_payload
    if exposure_passive <= 0 or exposure_payload <= 0:
        return {"point": None, "low": None, "high": None, "note": "no exposure"}
    if total == 0:
        return {"point": None, "low": None, "high": None, "note": "no flags in either population"}
    alpha = 1.0 - level
    p_low = 0.0 if flags_payload == 0 else _beta_quantile(flags_payload, total - flags_payload + 1, alpha / 2.0)
    p_high = 1.0 if flags_payload == total else _beta_quantile(flags_payload + 1, total - flags_payload, 1.0 - alpha / 2.0)
    rate_passive = flags_passive / exposure_passive
    rate_payload = flags_payload / exposure_payload
    point = None if rate_passive == 0 else rate_payload / rate_passive
    return {
        "point": point,
        "low": _theta_from_p(p_low, exposure_passive, exposure_payload),
        "high": _theta_from_p(p_high, exposure_passive, exposure_payload),
        "note": (
            "one-sided: no payload flags" if flags_payload == 0 else
            "one-sided: no passive flags" if flags_passive == 0 else None
        ),
    }


def tost_ratio(
    flags_passive: int,
    exposure_passive: float,
    flags_payload: int,
    exposure_payload: float,
    margin: float = EQUIVALENCE_MARGIN,
    alpha: float = 0.05,
) -> dict:
    """Exact conditional TOST for theta inside [1/margin, margin].

    Equivalence is declared only when BOTH one-sided exact tests reject, which
    is the same statement as the exact 1-2*alpha conditional interval for theta
    lying wholly inside the margin. Both are returned, because a reader who
    distrusts one will check the other and they cannot disagree.

    The superiority p-value rides along with no decision weight at all. It is
    here so that a reader can see for themselves that the original
    "rates are identical because p > 0.05" was null-acceptance, and that this
    test is a different claim rather than the same claim restated.
    """
    total = flags_passive + flags_payload
    if exposure_passive <= 0 or exposure_payload <= 0 or total == 0:
        return {
            "equivalent": False,
            "conclusive": False,
            "reason": "no exposure or no flags in either population",
            "margin": margin,
            "flagsPassive": flags_passive,
            "flagsPayload": flags_payload,
        }
    p_upper_null = (margin * exposure_payload) / (margin * exposure_payload + exposure_passive)
    lower_theta = 1.0 / margin
    p_lower_null = (lower_theta * exposure_payload) / (lower_theta * exposure_payload + exposure_passive)
    # H0: theta >= margin. Reject when the payload count is implausibly SMALL.
    p_value_upper = _binomial_cdf(flags_payload, total, p_upper_null)
    # H0: theta <= 1/margin. Reject when the payload count is implausibly LARGE.
    p_value_lower = _binomial_sf_inclusive(flags_payload, total, p_lower_null)
    p_equal = (exposure_payload) / (exposure_payload + exposure_passive)
    observed = _binomial_cdf(flags_payload, total, p_equal)
    superiority = 2.0 * min(observed, 1.0 - _binomial_cdf(flags_payload - 1, total, p_equal))
    interval90 = ratio_interval(
        flags_passive, exposure_passive, flags_payload, exposure_payload, level=1.0 - 2.0 * alpha
    )
    interval95 = ratio_interval(
        flags_passive, exposure_passive, flags_payload, exposure_payload, level=0.95
    )
    equivalent = p_value_upper < alpha and p_value_lower < alpha
    return {
        "equivalent": equivalent,
        "conclusive": True,
        "margin": margin,
        "alpha": alpha,
        "pValueUpper": p_value_upper,
        "pValueLower": p_value_lower,
        "pValueTost": max(p_value_upper, p_value_lower),
        "superiorityPValueNoDecisionWeight": min(1.0, superiority),
        "ratio90": interval90,
        "ratio95": interval95,
        "flagsPassive": flags_passive,
        "flagsPayload": flags_payload,
        "exposurePassive": exposure_passive,
        "exposurePayload": exposure_payload,
        "ratePassivePer1000": rate_per_1000(flags_passive, int(exposure_passive)),
        "ratePayloadPer1000": rate_per_1000(flags_payload, int(exposure_payload)),
    }


# --------------------------------------------------------------------------
# The reweighting
# --------------------------------------------------------------------------


def reweight(
    passive: dict[str, tuple[int, int]],
    payload: dict[str, tuple[int, int]],
    *,
    minimum_support: int = 1,
) -> dict:
    """Carry the per-stratum passive rate onto the payload covariate mix.

    `passive` and `payload` map stratum key -> (flags, intervals).

    Returns the raw floor, the reweighted floor, the per-stratum table, and the
    labelled gaps. A stratum with payload exposure but passive exposure below
    `minimum_support` is NOT given a rate: it is recorded as a gap, and its
    share of payload exposure is reported. Filling it with the pooled rate would
    be the single most dishonest line this module could contain, because it
    would turn "we never measured this" into "we measured this and it was
    average".
    """
    passive_flags = sum(f for f, _ in passive.values())
    passive_intervals = sum(n for _, n in passive.values())
    payload_intervals_total = sum(n for _, n in payload.values())
    raw = 0.0 if passive_intervals == 0 else passive_flags / passive_intervals

    supported: dict[str, float] = {}
    gaps: dict[str, int] = {}
    for key, (_, payload_n) in payload.items():
        if payload_n <= 0:
            continue
        passive_n = passive.get(key, (0, 0))[1]
        if passive_n >= minimum_support:
            supported[key] = float(payload_n)
        else:
            gaps[key] = payload_n

    supported_payload = sum(supported.values())
    rows = []
    reweighted = 0.0
    for key, payload_n in sorted(supported.items(), key=lambda kv: -kv[1]):
        p_flags, p_intervals = passive[key]
        weight = payload_n / supported_payload if supported_payload else 0.0
        rate = p_flags / p_intervals
        low, high = jeffreys(p_flags, p_intervals)
        reweighted += weight * rate
        l_flags, l_intervals = payload[key]
        rows.append({
            "stratum": key,
            "weight": weight,
            "passiveFlags": p_flags,
            "passiveIntervals": p_intervals,
            "passiveRatePer1000": 1000.0 * rate,
            "passiveJeffreys95Per1000": [1000.0 * low, 1000.0 * high],
            "payloadFlags": l_flags,
            "payloadIntervals": l_intervals,
            "payloadRatePer1000": rate_per_1000(l_flags, l_intervals),
        })

    gap_exposure = sum(gaps.values())
    return {
        "rawFloorPerInterval": raw,
        "rawFloorPer1000": 1000.0 * raw,
        "rawJeffreys95Per1000": [1000.0 * b for b in jeffreys(passive_flags, passive_intervals)],
        "reweightedFloorPerInterval": reweighted,
        "reweightedFloorPer1000": 1000.0 * reweighted,
        "ratioToRaw": (reweighted / raw) if raw > 0 else None,
        "passiveFlags": passive_flags,
        "passiveIntervals": passive_intervals,
        "payloadIntervals": payload_intervals_total,
        "supportedStrata": len(supported),
        "gapStrata": len(gaps),
        "minimumSupport": minimum_support,
        "unsupportedPayloadExposure": gap_exposure,
        "unsupportedPayloadExposureShare": (
            gap_exposure / payload_intervals_total if payload_intervals_total else 0.0
        ),
        "rows": rows,
        "gaps": sorted(
            ({"stratum": k, "payloadIntervals": v,
              "passiveIntervals": passive.get(k, (0, 0))[1]} for k, v in gaps.items()),
            key=lambda row: -row["payloadIntervals"],
        ),
    }


def worst_case_fill(result: dict) -> dict:
    """Sensitivity A: gaps filled with the pooled passive Jeffreys upper bound.

    Deliberately pessimistic, and registered as such before it was computed. It
    answers "suppose every stratum we could not measure is as bad as the worst
    the pooled control allows" and nothing more.
    """
    payload_total = result["payloadIntervals"]
    if payload_total <= 0:
        return {"reweightedFloorPer1000": None}
    upper = result["rawJeffreys95Per1000"][1] / 1000.0
    supported_share = 1.0 - result["unsupportedPayloadExposureShare"]
    filled = result["reweightedFloorPerInterval"] * supported_share + upper * (1.0 - supported_share)
    return {
        "reweightedFloorPerInterval": filled,
        "reweightedFloorPer1000": 1000.0 * filled,
        "ratioToRaw": filled / result["rawFloorPerInterval"] if result["rawFloorPerInterval"] else None,
        "fillRatePer1000": 1000.0 * upper,
        "filledExposureShare": 1.0 - supported_share,
    }


def bootstrap_reweighted(
    per_object: Sequence[dict[str, tuple[int, int]]],
    weights: dict[str, float],
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = SEED,
) -> dict:
    """Object-level clustered bootstrap of the reweighted floor.

    `per_object` is one dict per admitted PASSIVE object, mapping stratum key to
    that object's (flags, intervals). Resampling whole objects is the point: the
    intervals inside one object share a baseline, a fit history and a TLE
    cadence, so treating 3.7 million intervals as 3.7 million independent trials
    would produce an interval far too narrow to believe. This is the interval
    the report quotes.

    Payload weights are held fixed, as registered: the estimand is the passive
    rate carried onto the payload covariate distribution *as it actually is*.
    """
    import numpy as np

    keys = sorted(weights)
    index = {key: i for i, key in enumerate(keys)}
    n_keys = len(keys)
    n_objects = len(per_object)
    flags = np.zeros((n_objects, n_keys), dtype=np.float64)
    intervals = np.zeros((n_objects, n_keys), dtype=np.float64)
    for row, cells in enumerate(per_object):
        for key, (f, n) in cells.items():
            position = index.get(key)
            if position is None:
                continue
            flags[row, position] = f
            intervals[row, position] = n
    weight_vector = np.array([weights[key] for key in keys], dtype=np.float64)

    rng = np.random.default_rng(seed)
    estimates = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        picks = rng.integers(0, n_objects, size=n_objects)
        # Resampling with replacement is the same as weighting each object by
        # how many times it was drawn, so one matrix product replaces a gather
        # of the whole (objects x strata) table per draw. Identical arithmetic,
        # and it is the difference between a bootstrap that finishes and one
        # that has to be cut short and explained away.
        multiplicity = np.bincount(picks, minlength=n_objects).astype(np.float64)
        f_sum = multiplicity @ flags
        n_sum = multiplicity @ intervals
        live = n_sum > 0
        if not live.any():
            estimates[draw] = math.nan
            continue
        w = weight_vector * live
        total = w.sum()
        if total <= 0:
            estimates[draw] = math.nan
            continue
        rates = np.zeros(n_keys, dtype=np.float64)
        rates[live] = f_sum[live] / n_sum[live]
        estimates[draw] = float((w / total * rates).sum())
    finite = estimates[np.isfinite(estimates)]
    return {
        "method": "object-level clustered nonparametric bootstrap, percentile",
        "draws": draws,
        "usableDraws": int(finite.size),
        "seed": seed,
        "objects": n_objects,
        "meanPer1000": float(1000.0 * finite.mean()) if finite.size else None,
        "low95Per1000": float(1000.0 * np.percentile(finite, 2.5)) if finite.size else None,
        "high95Per1000": float(1000.0 * np.percentile(finite, 97.5)) if finite.size else None,
    }


def posterior_composite(
    passive: dict[str, tuple[int, int]],
    weights: dict[str, float],
    *,
    draws: int = POSTERIOR_DRAWS,
    seed: int = SEED,
) -> dict:
    """Secondary interval: independent Jeffreys posteriors, weighted and summed.

    Registered in advance as CONSERVATIVE and reported whatever it says. With
    several hundred occupied strata the Beta(k+0.5, n-k+0.5) prior contributes
    half a pseudo-flag per stratum, and those pseudo-flags land hardest exactly
    in the small strata that carry the most payload weight per observed flag.
    That upward push is a property of the prior, not a finding about the sky.
    """
    import numpy as np

    keys = sorted(weights)
    a = np.array([passive.get(k, (0, 0))[0] + 0.5 for k in keys], dtype=np.float64)
    b = np.array([
        max(passive.get(k, (0, 0))[1] - passive.get(k, (0, 0))[0], 0) + 0.5 for k in keys
    ], dtype=np.float64)
    w = np.array([weights[k] for k in keys], dtype=np.float64)
    w = w / w.sum() if w.sum() else w
    rng = np.random.default_rng(seed)
    samples = rng.beta(a, b, size=(draws, len(keys)))
    estimates = samples @ w
    return {
        "method": "independent per-stratum Jeffreys posterior draws, percentile",
        "draws": draws,
        "seed": seed,
        "note": "conservative by construction: half a pseudo-flag per occupied stratum",
        "meanPer1000": float(1000.0 * estimates.mean()),
        "low95Per1000": float(1000.0 * np.percentile(estimates, 2.5)),
        "high95Per1000": float(1000.0 * np.percentile(estimates, 97.5)),
    }


def boundary_scan(
    bins: Sequence[dict],
    *,
    margin: float = EQUIVALENCE_MARGIN,
    grid: Iterable[float] = tuple(float(x) for x in range(0, 92, 2)),
) -> dict:
    """The registered data-driven corroboration boundary.

    `bins` are the 2-degree curve bins, each carrying `low`, `passiveIntervals`,
    `passiveInclinationOnly`, `payloadIntervals`, `payloadInclinationOnly`.

    For each candidate theta, pool every bin at or above it and run the exact
    TOST. theta* is the SMALLEST candidate that passes and whose every larger
    candidate also passes. The monotone-stability clause is what stops one
    fortunate bin from setting a boundary: a boundary that only works at exactly
    one place on the grid is a coincidence, not a physical edge.
    """
    candidates = sorted(grid)
    results = []
    for theta in candidates:
        pooled = [b for b in bins if b["low"] >= theta]
        kp = sum(b["passiveInclinationOnly"] for b in pooled)
        ep = sum(b["passiveIntervals"] for b in pooled)
        kl = sum(b["payloadInclinationOnly"] for b in pooled)
        el = sum(b["payloadIntervals"] for b in pooled)
        test = tost_ratio(kp, ep, kl, el, margin=margin)
        results.append({"boundaryDeg": theta, "test": test})
    passing = [r["test"].get("equivalent", False) for r in results]
    boundary = None
    for position, theta in enumerate(candidates):
        if all(passing[position:]) and passing[position]:
            boundary = theta
            break
    return {
        "margin": margin,
        "grid": candidates,
        "boundaryDeg": boundary,
        "rule": (
            "smallest grid boundary whose pooled region passes exact TOST at the "
            "registered margin, and every larger grid boundary also passes"
        ),
        "scan": results,
    }
