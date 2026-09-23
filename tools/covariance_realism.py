"""Covariance realism of a megaconstellation's public ephemerides.

T19.  Registration: `docs/t19-covariance-realism-preregistration-20260922.md`,
committed alone before this file existed.  Every threshold, every lead, every
exclusion rule and every floor in here is fixed by that document; nothing is
chosen after seeing a number.

Three measurements, in the registration's order:

1. **Self-consistency containment.**  For two overlapping issues of the same
   spacecraft's ephemeris, the residual between the earlier issue's prediction
   and the later issue's state at the same instant, tested against the *earlier
   issue's own published covariance* at that lead.  Mahalanobis distance against
   a chi-square expectation, the method Park et al. (AMOS 2019) applied to their
   own data.

   **The word is self-consistency, never accuracy.**  A later issue is a later
   prediction, not a measurement.  The residual attributes to neither issue.

2. **The distinct-value census.**  Per issue, per lead, per covariance column,
   how many distinct values the operator publishes across every file of that
   issue.

3. **The consequence.**  What a covariance that is not self-consistent does to a
   two-dimensional collision probability, derived rather than asserted, in both
   the near-field and far-field regimes -- they have opposite signs, so a single
   ratio without its miss distance would be a misrepresentation.

The file reader is `starlink_ephemeris`, reused and not forked.  Both sides of
every comparison are the same operator's files in the same frame, so no frame
transformation, no time-scale conversion and no propagator enters the residual.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import starlink_ephemeris as eph  # noqa: E402  the reader, reused not forked

# --- constants fixed by the registration -----------------------------------

MU_KM3_S2 = 398600.4418  # WGS-84 / EGM-96 geocentric gravitational constant

REQUESTED_LEAD_HOURS = (1.0, 3.0, 6.0, 12.0, 24.0, 48.0, 72.0)
NATIVE_LEAD_HOURS = (8.0, 12.0, 16.0, 24.0, 36.0, 48.0, 60.0, 72.0)
CENSUS_LEAD_HOURS = (
    0.0, 1.0, 3.0, 6.0, 12.0, 24.0, 36.0,
    # A fine grid across 40-72 h, because the containment collapse and the
    # republished tail both live in that band and a coarse grid cannot say
    # where a column stops being a propagated uncertainty.
    40.0, 44.0, 46.0, 47.0, 48.0, 49.0, 50.0, 52.0, 54.0, 56.0, 58.0,
    60.0, 64.0, 68.0, 72.0,
)

LEAD_TOLERANCE_SECONDS = 30.0
MINIMUM_OVERLAP_HOURS = 12.0
MINIMUM_PAIRS_FOR_STATISTICS = 30

CHI2_3_MEDIAN = 2.365974          # chi-square, 3 dof, p = 0.50
CHI2_3_95 = 7.814728              # chi-square, 3 dof, p = 0.95
CHI2_1_MEDIAN = 0.4549364         # chi-square, 1 dof, p = 0.50
NORMAL_95_TWO_SIDED = 1.959964    # standard normal, two-sided 95%
PARK_DISTANCE = 4.0               # Park et al., AMOS 2019: 95.2% at or below

INTERPOLATION_POINTS = 9          # 8th-order Lagrange, CCSDS OEM practice
INTERPOLATION_SELF_TEST_LIMIT_M = 1.0

OFF_CADENCE_TOLERANCE_HOURS = 2.0
HOLDOUT_LAST_DIGIT = "0"
REPLAN_THRESHOLD_MULTIPLIER = 3.0
REPLAN_THRESHOLD_QUANTILE = 0.99

CENSUS_PLACEHOLDER_SHARE = 0.01   # distinct values below 1% of files licenses the word

# Positions are printed to 1e-10 km. Two states that agree to better than a
# tenth of a millimetre are the SAME PUBLISHED NUMBERS, not two predictions that
# happen to coincide: at ten significant figures, agreement is identity. This is
# a property of the file format, not a chosen tolerance.
IDENTICAL_STATE_LIMIT_M = 1.0e-4

# --- the consequence's chosen geometry, labelled as chosen -----------------

HARD_BODY_RADIUS_M = 10.0         # a CHOSEN conservative screen, not a measured dimension
CROSSING_ANGLES_DEG = (30.0, 60.0, 90.0, 120.0, 150.0)
REPRESENTATIVE_CROSSING_DEG = 90.0
MISS_DISTANCES_M = (0.0, 100.0, 300.0, 1000.0)
PC_LEAD_HOURS = (24.0, 48.0, 72.0)


# ---------------------------------------------------------------------------
# Small statistics, written out so the reader can see them
# ---------------------------------------------------------------------------


def wilson_interval(successes: int, trials: int, z: float = NORMAL_95_TWO_SIDED) -> tuple[float, float]:
    """Wilson score interval. Returns (low, high) as fractions.

    Wilson rather than the normal approximation because the fractions measured
    here sit near 0 and near 1, where the normal interval leaves the unit
    interval and stops meaning anything.
    """
    if trials <= 0:
        return (float("nan"), float("nan"))
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = (z / denominator) * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return (max(0.0, centre - half), min(1.0, centre + half))


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_median(values: Sequence[float]) -> float:
    """The median, or NaN for an empty sample -- an absence, never a zero."""
    values = [value for value in values if not math.isnan(value)]
    return statistics.median(values) if values else float("nan")


def quantile(values: Sequence[float], probability: float) -> float:
    """Linear-interpolated quantile on the sorted sample."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[int(position)]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


# ---------------------------------------------------------------------------
# Reading only the records a measurement needs
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FileIndex:
    """A file's header plus the records at the indices a caller asked for."""

    path: Path
    header: eph.EphemerisHeader
    records: dict[int, eph.EphemerisRecord]
    record_count: int


def _lines(path: Path) -> Iterable[str]:
    with gzip.open(path, "rt", encoding="ascii", errors="strict") as handle:
        for line in handle:
            yield line


def read_indices(path: Path, indices: Sequence[int]) -> FileIndex:
    """Header plus the four-line record blocks at the given record indices.

    The tabulation is uniform, so a lead time is a record index and the file
    does not have to be parsed in full.  Parsing is still done by the reader's
    own block parser -- the format is understood in one place only.
    """
    wanted = sorted(set(int(index) for index in indices if index >= 0))
    wanted_set = set(wanted)
    stream = _lines(path)
    header_lines = []
    for line in stream:
        header_lines.append(line)
        if len(header_lines) == 4:
            break
    header = eph.parse_header(header_lines)

    records: dict[int, eph.EphemerisRecord] = {}
    block: list[str] = []
    index = 0
    if not wanted:
        # A header-only read must not decompress the whole tabulation: the issue
        # scan touches every file in the archive and would otherwise cost an
        # order of magnitude more than the measurement it feeds.
        return FileIndex(path=path, header=header, records=records, record_count=-1)
    highest = max(wanted)
    for line in stream:
        if not line.strip():
            continue
        block.append(line)
        if len(block) < 4:
            continue
        if index in wanted_set:
            records[index] = eph._record_from_block(block)
        block = []
        index += 1
        if highest >= 0 and index > highest and len(records) == len(wanted_set):
            # Keep counting records only when the caller needs the count.
            break
    return FileIndex(path=path, header=header, records=records, record_count=index)


def record_count(path: Path) -> int:
    total = 0
    for _ in _lines(path):
        total += 1
    return max(0, (total - 4 + 3) // 4)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def uvw_basis(position_km: Sequence[float], velocity_km_s: Sequence[float]) -> np.ndarray:
    """Rows are U (radial), V (in-track), W (cross-track), from one state.

    The operator labels the covariance frame `UVW`.  T16a discharged the
    identification of column 1/2/3 with this triad as CONSISTENT -- the axis
    whose published sigma grows fastest with lead is the second, which is what
    a near-circular orbit's along-track error growth predicts -- but not as an
    independent determination.  Every output here carries the column index
    beside the axis name for that reason.
    """
    r = np.asarray(position_km, dtype=float)
    v = np.asarray(velocity_km_s, dtype=float)
    u_hat = r / np.linalg.norm(r)
    h = np.cross(r, v)
    w_hat = h / np.linalg.norm(h)
    v_hat = np.cross(w_hat, u_hat)
    return np.vstack([u_hat, v_hat, w_hat])


def position_covariance_m2(record: eph.EphemerisRecord) -> np.ndarray:
    """The 3x3 position block, km^2 in the file, returned in m^2."""
    c = record.covariance
    matrix = np.array(
        [
            [c[0], c[1], c[3]],
            [c[1], c[2], c[4]],
            [c[3], c[4], c[5]],
        ],
        dtype=float,
    )
    return matrix * 1.0e6


def osculating_semi_major_axis_km(position_km, velocity_km_s) -> float:
    r = float(np.linalg.norm(position_km))
    v2 = float(np.dot(velocity_km_s, velocity_km_s))
    energy_term = 2.0 / r - v2 / MU_KM3_S2
    if energy_term <= 0.0:
        return float("nan")
    return 1.0 / energy_term


def lagrange_interpolate(times: Sequence[float], values: np.ndarray, at: float) -> np.ndarray:
    """Component-wise Lagrange interpolation of a vector series.

    `times` are seconds from a common origin; `values` is (n, 3).
    """
    n = len(times)
    out = np.zeros(values.shape[1], dtype=float)
    for i in range(n):
        term = 1.0
        for j in range(n):
            if i == j:
                continue
            term *= (at - times[j]) / (times[i] - times[j])
        out += term * values[i]
    return out


# ---------------------------------------------------------------------------
# Issues and pairs
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Issue:
    path: Path
    catalogue: str
    created: dt.datetime
    start: dt.datetime
    stop: dt.datetime
    step_seconds: int
    source: str
    frame: str


def catalogue_of(name: str) -> str | None:
    parts = name.split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return parts[1]


def scan_issues(root: Path) -> list[Issue]:
    """Header-only scan of every held ephemeris file."""
    issues: list[Issue] = []
    for path in sorted(root.rglob("MEME_*.txt.gz")):
        catalogue = catalogue_of(path.name)
        if catalogue is None:
            continue
        try:
            index = read_indices(path, [])
        except (eph.EphemerisFormatError, OSError, EOFError):
            continue
        header = index.header
        issues.append(
            Issue(
                path=path,
                catalogue=catalogue,
                created=header.created,
                start=header.start,
                stop=header.stop,
                step_seconds=header.step_seconds,
                source=header.source,
                frame=header.covariance_frame,
            )
        )
    return issues


def build_pairs(issues: Sequence[Issue]) -> tuple[list[tuple[Issue, Issue]], dict]:
    """Adjacent issue pairs of the same spacecraft, with the rejects counted."""
    by_catalogue: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        by_catalogue[issue.catalogue].append(issue)

    pairs: list[tuple[Issue, Issue]] = []
    counts = Counter()
    for catalogue, group in by_catalogue.items():
        group = sorted(group, key=lambda item: (item.start, item.created))
        if len(group) < 2:
            counts["spacecraft with a single issue held"] += 1
            continue
        counts["spacecraft with two or more issues held"] += 1
        for earlier, later in zip(group, group[1:]):
            if later.created <= earlier.created or later.start <= earlier.start:
                counts["rejected: later issue not later"] += 1
                continue
            overlap = (earlier.stop - later.start).total_seconds() / 3600.0
            if overlap < MINIMUM_OVERLAP_HOURS:
                counts["rejected: overlap under 12 h"] += 1
                continue
            pairs.append((earlier, later))
            counts["pairs accepted"] += 1
    return pairs, dict(counts)


# ---------------------------------------------------------------------------
# The residual, per pair
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PairResult:
    catalogue: str
    cadence_hours: float
    overlap_hours: float
    holdout: bool
    off_cadence: bool
    delta_a_step_m: float
    leads: dict  # lead hours -> per-lead figures
    interpolated_points: int
    exact_points: int
    notes: list[str]
    new_information_horizon_hours: float = float("nan")


def window_indices(nearest: int, half: int, count: int) -> list[int]:
    """A contiguous interpolation window, slid inside the tabulation's range.

    At the first and last common instants the centred window runs off the end of
    the later issue's tabulation.  Sliding it keeps the same polynomial degree
    and keeps the instant inside the window's span, so it is still interpolation
    and never extrapolation.
    """
    span = 2 * half + 1
    if count < span:
        return list(range(count))
    low = min(max(nearest - half, 0), count - span)
    return list(range(low, low + span))


def _b_state_at(b_index: FileIndex, b_start: dt.datetime, instant: dt.datetime,
                step: float, count: int):
    """Issue B's position at `instant`: exact record, else 8th-order Lagrange."""
    offset = (instant - b_start).total_seconds()
    nearest = int(round(offset / step))
    if nearest in b_index.records:
        record = b_index.records[nearest]
        if abs((record.epoch - instant).total_seconds()) < 1e-6:
            return np.asarray(record.position_km, dtype=float), False, record
    half = INTERPOLATION_POINTS // 2
    indices = window_indices(nearest, half, count)
    if any(index not in b_index.records for index in indices):
        return None
    times = [(b_index.records[index].epoch - instant).total_seconds() for index in indices]
    values = np.array([b_index.records[index].position_km for index in indices], dtype=float)
    return lagrange_interpolate(times, values, 0.0), True, None


def measure_pair(
    earlier: Issue,
    later: Issue,
    leads_hours: Sequence[float],
) -> PairResult | None:
    step = float(earlier.step_seconds)
    if step <= 0 or later.step_seconds != earlier.step_seconds:
        return None

    cadence_hours = (later.start - earlier.start).total_seconds() / 3600.0
    overlap_hours = (earlier.stop - later.start).total_seconds() / 3600.0

    # Issue A's record indices: the requested leads that land inside the overlap,
    # plus the first and last common instants for the semi-major-axis test.
    first_common = later.start
    last_common = earlier.stop
    a_first = int(math.ceil((first_common - earlier.start).total_seconds() / step))
    a_last = int(math.floor((last_common - earlier.start).total_seconds() / step))
    lead_indices: dict[float, int] = {}
    for lead in leads_hours:
        index = int(round(lead * 3600.0 / step))
        if a_first <= index <= a_last:
            lead_indices[lead] = index
    if not lead_indices and a_last < a_first:
        return None

    a_wanted = sorted(set(list(lead_indices.values()) + [a_first, a_last]))
    a_index = read_indices(earlier.path, a_wanted)
    if a_first not in a_index.records or a_last not in a_index.records:
        return None

    # Issue B's record indices: a window around each instant, for interpolation.
    half = INTERPOLATION_POINTS // 2
    b_count = int(round((later.stop - later.start).total_seconds() / step)) + 1
    b_wanted: set[int] = set()
    for index in a_wanted:
        instant = earlier.start + dt.timedelta(seconds=index * step)
        nearest = int(round((instant - later.start).total_seconds() / step))
        b_wanted.update(window_indices(nearest, half, b_count))
        if 0 <= nearest < b_count:
            b_wanted.add(nearest)
    b_index = read_indices(later.path, sorted(b_wanted))

    notes: list[str] = []
    exact = 0
    interpolated = 0

    # --- the registered re-plan discriminant: a step in the osculating a ---
    def delta_a_at(a_record_index: int) -> float:
        record_a = a_index.records.get(a_record_index)
        if record_a is None:
            return float("nan")
        instant = record_a.epoch
        offset = (instant - later.start).total_seconds()
        nearest = int(round(offset / step))
        indices = window_indices(nearest, half, b_count)
        if any(index not in b_index.records for index in indices):
            return float("nan")
        times = [(b_index.records[index].epoch - instant).total_seconds() for index in indices]
        positions = np.array([b_index.records[index].position_km for index in indices], dtype=float)
        velocities = np.array([b_index.records[index].velocity_km_s for index in indices], dtype=float)
        r_b = lagrange_interpolate(times, positions, 0.0)
        v_b = lagrange_interpolate(times, velocities, 0.0)
        a_b = osculating_semi_major_axis_km(r_b, v_b)
        a_a = osculating_semi_major_axis_km(record_a.position_km, record_a.velocity_km_s)
        return (a_b - a_a) * 1000.0

    delta_a_first = delta_a_at(a_first)
    delta_a_last = delta_a_at(a_last)
    delta_a_step = abs(delta_a_last - delta_a_first)

    leads: dict[float, dict] = {}
    for lead, index in lead_indices.items():
        record_a = a_index.records.get(index)
        if record_a is None:
            continue
        instant = record_a.epoch
        nominal = earlier.start + dt.timedelta(hours=lead)
        if abs((instant - nominal).total_seconds()) > LEAD_TOLERANCE_SECONDS:
            continue
        answer = _b_state_at(b_index, later.start, instant, step, b_count)
        if answer is None:
            continue
        r_b, was_interpolated, b_record = answer
        if was_interpolated:
            interpolated += 1
        else:
            exact += 1
        d_m = (r_b - np.asarray(record_a.position_km, dtype=float)) * 1000.0
        basis = uvw_basis(record_a.position_km, record_a.velocity_km_s)
        d_frame = basis @ d_m

        p = position_covariance_m2(record_a)
        try:
            factor = np.linalg.cholesky(p)
        except np.linalg.LinAlgError:
            notes.append(f"lead {lead}: covariance not positive definite")
            continue
        solved = np.linalg.solve(factor, d_frame)
        m2 = float(np.dot(solved, solved))
        sigmas = np.sqrt(np.diag(p))
        z = d_frame / sigmas
        identical = bool(np.max(np.abs(d_m)) < IDENTICAL_STATE_LIMIT_M)
        covariance_relative_difference = None
        if b_record is not None and b_record.covariance:
            b_sigmas = np.sqrt(np.diag(position_covariance_m2(b_record)))
            with np.errstate(divide="ignore", invalid="ignore"):
                covariance_relative_difference = float(
                    np.max(np.abs(b_sigmas - sigmas) / np.where(sigmas > 0, sigmas, np.nan))
                )
        leads[lead] = {
            "identical": identical,
            "covarianceRelativeDifference": covariance_relative_difference,
            "residualM": [float(value) for value in d_frame],
            "sigmaM": [float(value) for value in sigmas],
            "z": [float(value) for value in z],
            "m2": m2,
            "m": math.sqrt(m2),
            "interpolated": was_interpolated,
            "normM": float(np.linalg.norm(d_m)),
        }

    if not leads:
        return None

    # The lead beyond which the later issue stops carrying new information:
    # the smallest lead on the measured grid such that this and every longer
    # lead in the overlap publishes the same state as the earlier issue.
    horizon = float("nan")
    ordered = sorted(leads)
    for position, lead in enumerate(ordered):
        if all(leads[longer]["identical"] for longer in ordered[position:]):
            horizon = lead
            break

    return PairResult(
        catalogue=earlier.catalogue,
        cadence_hours=cadence_hours,
        overlap_hours=overlap_hours,
        holdout=earlier.catalogue.endswith(HOLDOUT_LAST_DIGIT),
        off_cadence=False,  # set by the caller once the median cadence is known
        delta_a_step_m=delta_a_step,
        leads=leads,
        interpolated_points=interpolated,
        exact_points=exact,
        notes=notes,
        new_information_horizon_hours=horizon,
    )


def splice_scan(pairs: Sequence[tuple[Issue, Issue]], sample: int = 200,
                resolution_hours: float = 1.0) -> dict:
    """Where in the overlap the later issue stops differing from the earlier one.

    The lead grid is coarse; this walks the overlap at one-hour resolution and
    reports the first instant at which the two issues publish the same state and
    never differ again.  It also counts the pairs for which "identical" is not a
    single contiguous tail, because a rule that assumes a clean splice must be
    able to report when the data does not have one.
    """
    firsts: list[float] = []
    firsts_later: list[float] = []
    absolute: list[str] = []
    non_contiguous = 0
    never = 0
    always = 0
    examined = 0
    step_pairs = max(1, len(pairs) // sample)
    for earlier, later in pairs[::step_pairs][:sample]:
        step = float(earlier.step_seconds)
        if step <= 0 or later.step_seconds != earlier.step_seconds:
            continue
        begin = int(math.ceil((later.start - earlier.start).total_seconds() / step))
        end = int(math.floor((earlier.stop - earlier.start).total_seconds() / step))
        stride = int(round(resolution_hours * 3600.0 / step))
        indices = list(range(begin, end + 1, stride))
        if len(indices) < 3:
            continue
        try:
            a_index = read_indices(earlier.path, indices)
        except (eph.EphemerisFormatError, OSError, EOFError):
            continue
        b_count = int(round((later.stop - later.start).total_seconds() / step)) + 1
        b_wanted = []
        mapping = {}
        for index in indices:
            record = a_index.records.get(index)
            if record is None:
                continue
            nearest = int(round((record.epoch - later.start).total_seconds() / step))
            if 0 <= nearest < b_count:
                mapping[index] = nearest
                b_wanted.append(nearest)
        if not b_wanted:
            continue
        try:
            b_index = read_indices(later.path, sorted(set(b_wanted)))
        except (eph.EphemerisFormatError, OSError, EOFError):
            continue

        flags: list[tuple[int, bool]] = []
        for index in indices:
            record_a = a_index.records.get(index)
            record_b = b_index.records.get(mapping.get(index, -1))
            if record_a is None or record_b is None:
                continue
            difference = (
                np.asarray(record_b.position_km, dtype=float)
                - np.asarray(record_a.position_km, dtype=float)
            ) * 1000.0
            flags.append((index, bool(np.max(np.abs(difference)) < IDENTICAL_STATE_LIMIT_M)))
        if not flags:
            continue
        examined += 1
        if all(flag for _, flag in flags):
            always += 1
            continue
        if not any(flag for _, flag in flags):
            never += 1
            continue
        tail_start = None
        for position in range(len(flags) - 1, -1, -1):
            if flags[position][1]:
                tail_start = position
            else:
                break
        if tail_start is None:
            never += 1
            continue
        if any(flag for _, flag in flags[:tail_start]):
            non_contiguous += 1
        first_index = flags[tail_start][0]
        firsts.append(first_index * step / 3600.0)
        moment = earlier.start + dt.timedelta(seconds=first_index * step)
        absolute.append(moment.isoformat())
        firsts_later.append((moment - later.start).total_seconds() / 3600.0)

    return {
        "pairsExamined": examined,
        "resolutionHours": resolution_hours,
        "identicalAtEveryInstant": always,
        "identicalAtNoInstant": never,
        "identicalTailNotContiguous": non_contiguous,
        "firstIdenticalLeadHours": {
            "n": len(firsts),
            "median": safe_median(firsts),
            "p05": quantile(firsts, 0.05),
            "p95": quantile(firsts, 0.95),
            "min": min(firsts) if firsts else float("nan"),
            "max": max(firsts) if firsts else float("nan"),
        },
        "firstIdenticalLeadHoursOfLaterIssue": {
            "n": len(firsts_later),
            "median": safe_median(firsts_later),
            "p05": quantile(firsts_later, 0.05),
            "p95": quantile(firsts_later, 0.95),
            "min": min(firsts_later) if firsts_later else float("nan"),
            "max": max(firsts_later) if firsts_later else float("nan"),
            "note": "the lead, measured from the LATER issue's own start, beyond "
            "which that issue republishes the earlier issue's states",
        },
        "firstIdenticalAbsoluteUtc": {
            "earliest": min(absolute) if absolute else None,
            "median": sorted(absolute)[len(absolute) // 2] if absolute else None,
            "latest": max(absolute) if absolute else None,
        },
    }


# ---------------------------------------------------------------------------
# The interpolation self-test
# ---------------------------------------------------------------------------


def interpolation_self_test(paths: Sequence[Path], samples_per_file: int = 8) -> dict:
    """Leave-one-out on real files: remove a record, interpolate onto its epoch.

    Deliberately conservative: production interpolation uses the nine nearest
    records including both flanks of the instant, while leave-one-out has to
    span a gap, so this residual is an upper bound on the production one.
    """
    residuals: list[float] = []
    half = INTERPOLATION_POINTS // 2
    for path in paths:
        try:
            total = record_count(path)
        except (OSError, EOFError):
            continue
        if total < INTERPOLATION_POINTS + 2:
            continue
        centres = [
            half + 1 + int(k * (total - 2 * half - 2) / max(1, samples_per_file - 1))
            for k in range(samples_per_file)
        ]
        wanted: set[int] = set()
        for centre in centres:
            for delta in range(-half, half + 1):
                wanted.add(centre + delta)
        try:
            index = read_indices(path, sorted(wanted))
        except (eph.EphemerisFormatError, OSError, EOFError):
            continue
        for centre in centres:
            neighbours = [centre + delta for delta in range(-half, half + 1) if delta != 0]
            if any(item not in index.records for item in neighbours):
                continue
            target = index.records.get(centre)
            if target is None:
                continue
            times = [(index.records[item].epoch - target.epoch).total_seconds() for item in neighbours]
            values = np.array([index.records[item].position_km for item in neighbours], dtype=float)
            estimate = lagrange_interpolate(times, values, 0.0)
            residuals.append(
                float(np.linalg.norm(estimate - np.asarray(target.position_km, dtype=float)) * 1000.0)
            )
    if not residuals:
        return {"n": 0}
    return {
        "n": len(residuals),
        "files": len(paths),
        "medianM": statistics.median(residuals),
        "p95M": quantile(residuals, 0.95),
        "maxM": max(residuals),
        "limitM": INTERPOLATION_SELF_TEST_LIMIT_M,
        "withinLimit": quantile(residuals, 0.95) <= INTERPOLATION_SELF_TEST_LIMIT_M,
        "note": "leave-one-out with the record removed; production interpolation "
        "keeps both flanks, so this is an upper bound",
    }


# ---------------------------------------------------------------------------
# Containment, aggregated
# ---------------------------------------------------------------------------


def summarise_containment(results: Sequence[PairResult], leads: Sequence[float],
                          label: str, *, informative_only: bool = True) -> dict:
    out: dict = {
        "label": label,
        "informativeOnly": informative_only,
        "informativeRule": (
            "an instant at which the later issue publishes the SAME state as the "
            "earlier one carries no new information and cannot test a covariance; "
            "agreement below the file's own print precision is identity, not "
            "coincidence"
        ),
        "leads": {},
    }
    for lead in leads:
        m2_values = []
        z_values = [[], [], []]
        norms = []
        offered = 0
        identical = 0
        covariance_differences = []
        for result in results:
            entry = result.leads.get(lead)
            if entry is None:
                continue
            offered += 1
            if entry["identical"]:
                identical += 1
                if entry.get("covarianceRelativeDifference") is not None:
                    covariance_differences.append(entry["covarianceRelativeDifference"])
                if informative_only:
                    continue
            m2_values.append(entry["m2"])
            norms.append(entry["normM"])
            for axis in range(3):
                z_values[axis].append(entry["z"][axis])
        n = len(m2_values)
        cell: dict = {
            "n": n,
            "pairsOffered": offered,
            "identicalState": identical,
            "identicalFraction": (identical / offered) if offered else float("nan"),
            "medianCovarianceRelativeDifferenceWhereIdentical": safe_median(covariance_differences),
        }
        if n == 0:
            if offered:
                cell["status"] = (
                    "NO INFORMATIVE PAIR at this lead: the later issue publishes the "
                    "earlier issue's own state at every one of the "
                    f"{offered} overlapping pairs"
                )
            else:
                cell["status"] = "UNREACHABLE at this lead: no pair overlaps it"
            out["leads"][lead] = cell
            continue
        if n < MINIMUM_PAIRS_FOR_STATISTICS:
            cell["status"] = (
                f"counts only: n = {n} is below the registered floor of "
                f"{MINIMUM_PAIRS_FOR_STATISTICS} pairs"
            )
            out["leads"][lead] = cell
            continue

        inside = sum(1 for value in m2_values if value <= CHI2_3_95)
        low, high = wilson_interval(inside, n)
        park = sum(1 for value in m2_values if math.sqrt(value) <= PARK_DISTANCE)
        park_low, park_high = wilson_interval(park, n)
        median_m2 = statistics.median(m2_values)
        k = math.sqrt(median_m2 / CHI2_3_MEDIAN)
        k95 = math.sqrt(quantile(m2_values, 0.95) / CHI2_3_95)

        per_axis = []
        for axis in range(3):
            values = z_values[axis]
            inside_axis = sum(1 for value in values if abs(value) <= NORMAL_95_TWO_SIDED)
            axis_low, axis_high = wilson_interval(inside_axis, len(values))
            median_z2 = statistics.median([value * value for value in values])
            per_axis.append(
                {
                    "columnIndex": axis + 1,
                    "axisNameFromLabel": ("radial", "in-track", "cross-track")[axis],
                    "containedFraction": inside_axis / len(values),
                    "wilson95": [axis_low, axis_high],
                    "kRobust": math.sqrt(median_z2 / CHI2_1_MEDIAN),
                    "k95": quantile([abs(value) for value in values], 0.95) / NORMAL_95_TWO_SIDED,
                    "medianAbsZ": statistics.median([abs(value) for value in values]),
                    "rmsZ": math.sqrt(statistics.fmean([value * value for value in values])),
                }
            )

        cell.update(
            {
                "status": "measured",
                "containedFraction": inside / n,
                "wilson95": [low, high],
                "nominal": 0.95,
                "parkDistanceFraction": park / n,
                "parkWilson95": [park_low, park_high],
                "parkReference": 0.952,
                "medianM2": median_m2,
                "p95M2": quantile(m2_values, 0.95),
                "kRobust": k,
                "kRobustLowerBound": k / math.sqrt(2.0),
                "k95": k95,
                "medianResidualNormM": safe_median(norms),
                "p95ResidualNormM": quantile(norms, 0.95),
                "perAxis": per_axis,
            }
        )
        out["leads"][lead] = cell
    return out


# ---------------------------------------------------------------------------
# The distinct-value census
# ---------------------------------------------------------------------------


def issue_cycle(created: dt.datetime, cycle_hours: float = 8.0) -> str:
    """The publication cycle a file belongs to, from its own creation stamp."""
    seconds = created.timestamp()
    bucket = math.floor(seconds / (cycle_hours * 3600.0))
    start = dt.datetime.fromtimestamp(bucket * cycle_hours * 3600.0, tz=dt.timezone.utc)
    return start.strftime("%Y-%m-%dT%H:%MZ")


def census(paths: Sequence[Path], leads_hours: Sequence[float] = CENSUS_LEAD_HOURS) -> dict:
    """Distinct published sigma values per issue, per lead, per column."""
    per_cycle: dict[str, dict] = {}
    unreadable = 0
    monotonicity: dict[str, Counter] = defaultdict(Counter)

    for path in paths:
        try:
            probe = read_indices(path, [])
        except (eph.EphemerisFormatError, OSError, EOFError):
            unreadable += 1
            continue
        step = float(probe.header.step_seconds)
        if step <= 0:
            unreadable += 1
            continue
        indices = {lead: int(round(lead * 3600.0 / step)) for lead in leads_hours}
        try:
            index = read_indices(path, sorted(indices.values()))
        except (eph.EphemerisFormatError, OSError, EOFError):
            unreadable += 1
            continue
        cycle = issue_cycle(probe.header.created)
        bucket = per_cycle.setdefault(
            cycle,
            {
                "files": 0,
                "values": {lead: [Counter(), Counter(), Counter()] for lead in leads_hours},
                "createdFirst": probe.header.created.isoformat(),
                "createdLast": probe.header.created.isoformat(),
                "sources": Counter(),
                "frames": Counter(),
            },
        )
        bucket["files"] += 1
        bucket["sources"][probe.header.source] += 1
        bucket["frames"][probe.header.covariance_frame] += 1
        if probe.header.created.isoformat() < bucket["createdFirst"]:
            bucket["createdFirst"] = probe.header.created.isoformat()
        if probe.header.created.isoformat() > bucket["createdLast"]:
            bucket["createdLast"] = probe.header.created.isoformat()

        sigma_by_lead: dict[float, list[float]] = {}
        for lead, record_index in indices.items():
            record = index.records.get(record_index)
            if record is None:
                continue
            c = record.covariance
            diagonal = (c[0], c[2], c[5])
            sigmas = []
            for axis, value in enumerate(diagonal):
                if value < 0:
                    continue
                sigma = math.sqrt(value) * 1000.0
                bucket["values"][lead][axis][sigma] += 1
                sigmas.append(sigma)
            if len(sigmas) == 3:
                sigma_by_lead[lead] = sigmas

        ordered = sorted(sigma_by_lead)
        for previous, following in zip(ordered, ordered[1:]):
            for axis in range(3):
                if sigma_by_lead[following][axis] < sigma_by_lead[previous][axis]:
                    monotonicity[cycle][f"{previous}->{following} axis{axis + 1}"] += 1

    out: dict = {"unreadable": unreadable, "cycles": {}}
    for cycle, bucket in sorted(per_cycle.items()):
        files = bucket["files"]
        cycle_out: dict = {
            "files": files,
            "createdFirst": bucket["createdFirst"],
            "createdLast": bucket["createdLast"],
            "sources": dict(bucket["sources"]),
            "frames": dict(bucket["frames"]),
            "leads": {},
            "nonMonotonic": {
                key: {"count": value, "fraction": value / files}
                for key, value in sorted(monotonicity[cycle].items())
            },
        }
        for lead in leads_hours:
            counters = bucket["values"][lead]
            per_axis = []
            for axis, counter in enumerate(counters):
                total = sum(counter.values())
                distinct = len(counter)
                top = counter.most_common(5)
                values = list(counter.elements()) if total <= 200000 else None
                per_axis.append(
                    {
                        "columnIndex": axis + 1,
                        "axisNameFromLabel": ("radial", "in-track", "cross-track")[axis],
                        "n": total,
                        "distinctValues": distinct,
                        "distinctShare": (distinct / total) if total else float("nan"),
                        "topValues": [
                            {"sigmaM": value, "count": count, "share": count / total}
                            for value, count in top
                        ],
                        "medianM": statistics.median(values) if values else None,
                        "p05M": quantile(values, 0.05) if values else None,
                        "p95M": quantile(values, 0.95) if values else None,
                    }
                )
            cycle_out["leads"][lead] = per_axis
        out["cycles"][cycle] = cycle_out

    # The licence condition for the word "placeholder", applied mechanically.
    licensed: dict[float, list[int]] = {}
    for lead in leads_hours:
        for axis in range(3):
            ok = True
            seen = False
            for cycle_out in out["cycles"].values():
                cell = cycle_out["leads"][lead][axis]
                if cell["n"] == 0:
                    continue
                seen = True
                if cell["distinctShare"] >= CENSUS_PLACEHOLDER_SHARE:
                    ok = False
            if seen and ok:
                licensed.setdefault(lead, []).append(axis + 1)
    out["placeholderLicensed"] = {str(lead): columns for lead, columns in licensed.items()}
    out["placeholderRule"] = (
        f"the word is licensed only where a lead's distinct-value count is below "
        f"{CENSUS_PLACEHOLDER_SHARE:.0%} of the file count in EVERY issue measured"
    )
    return out


# ---------------------------------------------------------------------------
# The consequence: a two-dimensional collision probability
# ---------------------------------------------------------------------------


def encounter_plane_covariance(
    covariance_uvw_m2: np.ndarray, crossing_deg: float
) -> tuple[np.ndarray, np.ndarray, float]:
    """Combined covariance projected onto the encounter plane.

    Both objects are spacecraft of the same constellation carrying the same
    published covariance in their own UVW frame, at the same lead.  At the
    conjunction point they share the radial direction, and their in-track axes
    differ by the crossing angle about that radial direction, so the secondary's
    covariance is the primary's rotated about U.  The combined covariance is the
    sum, which assumes the two solutions are independent -- stated, not hidden:
    intra-constellation solutions from one operator's one process are plausibly
    correlated, and a positive correlation would make the combined covariance
    smaller and every Pc here larger.
    """
    theta = math.radians(crossing_deg)
    # Axes ordered (U, V, W) = (radial, in-track, cross-track).
    rotation = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(theta), -math.sin(theta)],
            [0.0, math.sin(theta), math.cos(theta)],
        ]
    )
    combined = covariance_uvw_m2 + rotation @ covariance_uvw_m2 @ rotation.T

    # Relative velocity, with the primary's velocity along V and the secondary's
    # rotated by theta in the V-W plane (both in the local horizontal plane).
    v_rel = np.array([0.0, math.cos(theta) - 1.0, math.sin(theta)])
    norm = np.linalg.norm(v_rel)
    if norm == 0.0:
        raise ValueError("a zero crossing angle has no encounter plane")
    v_hat = v_rel / norm

    # Encounter plane: any two orthonormal vectors perpendicular to v_hat.
    seed = np.array([1.0, 0.0, 0.0])  # radial, which is perpendicular to v_hat here
    e1 = seed - np.dot(seed, v_hat) * v_hat
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(v_hat, e1)
    basis = np.vstack([e1, e2])
    projected = basis @ combined @ basis.T
    return projected, basis, norm


def pc_two_dimensional(
    projected_m2: np.ndarray, miss_m: Sequence[float], radius_m: float,
    grid: int = 512
) -> float:
    """Alfano/Foster 2-D Pc, integrated on the encounter plane.

    Integration is in polar coordinates centred on the hard-body disk, so the
    domain is exact and only the integrand is discretised.
    """
    eigenvalues, eigenvectors = np.linalg.eigh(projected_m2)
    if np.any(eigenvalues <= 0):
        return float("nan")
    sigma = np.sqrt(eigenvalues)
    centre = eigenvectors.T @ np.asarray(miss_m, dtype=float)

    total = 0.0
    for i in range(grid):
        rho = radius_m * (i + 0.5) / grid
        d_rho = radius_m / grid
        for j in range(grid):
            phi = 2.0 * math.pi * (j + 0.5) / grid
            d_phi = 2.0 * math.pi / grid
            x = centre[0] + rho * math.cos(phi)
            y = centre[1] + rho * math.sin(phi)
            exponent = -0.5 * ((x / sigma[0]) ** 2 + (y / sigma[1]) ** 2)
            total += math.exp(exponent) * rho * d_rho * d_phi
    return total / (2.0 * math.pi * sigma[0] * sigma[1])


def consequence(
    published_sigmas_m: Sequence[float],
    scale_k: float,
    *,
    crossing_deg: float = REPRESENTATIVE_CROSSING_DEG,
    radius_m: float = HARD_BODY_RADIUS_M,
    misses_m: Sequence[float] = MISS_DISTANCES_M,
    radius_km: float = 6900.0,
) -> dict:
    """Pc with the published covariance against Pc with the self-consistent one."""
    published = np.diag(np.asarray(published_sigmas_m, dtype=float) ** 2)
    speed = math.sqrt(MU_KM3_S2 / radius_km)
    v_rel = 2.0 * speed * math.sin(math.radians(crossing_deg) / 2.0)

    out = {
        "crossingAngleDeg": crossing_deg,
        "orbitRadiusKm": radius_km,
        "circularSpeedKmS": speed,
        "relativeSpeedKmS": v_rel,
        "hardBodyRadiusM": radius_m,
        "hardBodyRadiusNote": "a CHOSEN conservative screen, not a measured dimension",
        "scaleK": scale_k,
        "misses": [],
    }
    projected_published, _, _ = encounter_plane_covariance(published, crossing_deg)
    projected_scaled, _, _ = encounter_plane_covariance(published * scale_k * scale_k, crossing_deg)

    for miss in misses_m:
        for direction, label in (((1.0, 0.0), "along the projected radial axis"),
                                 ((0.0, 1.0), "along the projected in-plane axis")):
            offset = (miss * direction[0], miss * direction[1])
            pc_published = pc_two_dimensional(projected_published, offset, radius_m)
            pc_scaled = pc_two_dimensional(projected_scaled, offset, radius_m)
            if pc_scaled > 0.0 and pc_published > 0.0:
                log_ratio = math.log10(pc_published) - math.log10(pc_scaled)
                ratio = 10.0**log_ratio if abs(log_ratio) < 300 else math.inf * (1 if log_ratio > 0 else 0)
            else:
                log_ratio = float("inf") if pc_published > 0 else float("nan")
                ratio = float("inf") if pc_published > 0 else float("nan")
            out["misses"].append(
                {
                    "missM": miss,
                    "direction": label,
                    "pcPublished": pc_published,
                    "pcSelfConsistent": pc_scaled,
                    "ratioPublishedOverSelfConsistent": ratio,
                    "ratioLog10": log_ratio,
                }
            )
    return out


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def median_orbit_radius_km(issues: Sequence[Issue], sample: int = 400) -> float:
    """The representative orbital radius, measured from the files themselves."""
    radii: list[float] = []
    step = max(1, len(issues) // sample)
    for issue in issues[::step][:sample]:
        try:
            index = read_indices(issue.path, [0])
        except (eph.EphemerisFormatError, OSError, EOFError):
            continue
        record = index.records.get(0)
        if record is None:
            continue
        radii.append(float(np.linalg.norm(record.position_km)))
    return safe_median(radii)


def run(root: Path, *, limit: int | None = None, self_test_files: int = 25) -> dict:
    issues = scan_issues(root)
    pairs, pair_counts = build_pairs(issues)
    if limit is not None:
        pairs = pairs[:limit]

    cadences = [(later.start - earlier.start).total_seconds() / 3600.0 for earlier, later in pairs]
    median_cadence = statistics.median(cadences) if cadences else float("nan")

    leads = sorted(set(REQUESTED_LEAD_HOURS) | set(NATIVE_LEAD_HOURS))
    results: list[PairResult] = []
    failed = 0
    for earlier, later in pairs:
        try:
            result = measure_pair(earlier, later, leads)
        except (eph.EphemerisFormatError, OSError, EOFError, ValueError):
            failed += 1
            continue
        if result is None:
            failed += 1
            continue
        result.off_cadence = abs(result.cadence_hours - median_cadence) > OFF_CADENCE_TOLERANCE_HOURS
        results.append(result)

    holdout = [result for result in results if result.holdout]
    reported = [result for result in results if not result.holdout]

    holdout_steps = [result.delta_a_step_m for result in holdout
                     if not math.isnan(result.delta_a_step_m)]
    if holdout_steps:
        threshold = REPLAN_THRESHOLD_MULTIPLIER * quantile(holdout_steps, REPLAN_THRESHOLD_QUANTILE)
    else:
        threshold = float("nan")

    off_cadence = [result for result in reported if result.off_cadence]
    on_cadence = [result for result in reported if not result.off_cadence]
    replans = [result for result in on_cadence
               if not math.isnan(result.delta_a_step_m) and result.delta_a_step_m > threshold]
    clean = [result for result in on_cadence
             if math.isnan(result.delta_a_step_m) or result.delta_a_step_m <= threshold]

    splice = splice_scan(pairs)
    sample_paths = [later.path for _, later in pairs[:self_test_files]]
    self_test = interpolation_self_test(sample_paths)

    census_paths = [issue.path for issue in issues]
    census_out = census(census_paths)

    # --- the consequence, from the measured k and the measured geometry ---
    radius_km = median_orbit_radius_km(issues)
    containment = summarise_containment(
        clean, leads, "re-plans excluded; informative instants only"
    )
    consequences = {}
    for lead in PC_LEAD_HOURS:
        cell = containment["leads"].get(lead, {})
        if cell.get("status") != "measured":
            consequences[str(lead)] = {
                "status": cell.get("status", "not measured"),
                "note": "no scale factor at this lead, so no Pc number is produced",
            }
            continue
        sigmas = None
        for cycle_out in census_out["cycles"].values():
            cells = cycle_out["leads"].get(lead)
            if cells and all(item["medianM"] for item in cells):
                sigmas = [item["medianM"] for item in cells]
                break
        if sigmas is None:
            consequences[str(lead)] = {"status": "no published sigma median at this lead"}
            continue
        block = {
            "publishedSigmaM": sigmas,
            "scaleK": cell["kRobust"],
            "scaleKLowerBound": cell["kRobustLowerBound"],
            "representative": consequence(
                sigmas, cell["kRobust"], radius_km=radius_km if not math.isnan(radius_km) else 6900.0
            ),
            "crossingAngleFamily": {},
        }
        for angle in CROSSING_ANGLES_DEG:
            family = consequence(
                sigmas,
                cell["kRobust"],
                crossing_deg=angle,
                misses_m=(0.0,),
                radius_km=radius_km if not math.isnan(radius_km) else 6900.0,
            )
            block["crossingAngleFamily"][str(angle)] = {
                "relativeSpeedKmS": family["relativeSpeedKmS"],
                "ratioAtZeroMiss": family["misses"][0]["ratioPublishedOverSelfConsistent"],
            }
        consequences[str(lead)] = block

    return {
        "issuesHeld": len(issues),
        "spacecraft": len({issue.catalogue for issue in issues}),
        "pairCounts": pair_counts,
        "pairsMeasured": len(results),
        "pairsFailed": failed,
        "cadenceHours": {
            "median": median_cadence,
            "p05": quantile(cadences, 0.05) if cadences else float("nan"),
            "p95": quantile(cadences, 0.95) if cadences else float("nan"),
            "min": min(cadences) if cadences else float("nan"),
            "max": max(cadences) if cadences else float("nan"),
        },
        "exclusions": {
            "calibrationHoldout": len(holdout),
            "holdoutRule": f"catalogue field ending in {HOLDOUT_LAST_DIGIT!r}",
            "replanThresholdM": threshold,
            "replanThresholdRule": (
                f"{REPLAN_THRESHOLD_MULTIPLIER} x the "
                f"{REPLAN_THRESHOLD_QUANTILE:.0%} quantile of the semi-major-axis step "
                f"on the hold-out, which is then excluded from every reported number"
            ),
            "replansExcluded": len(replans),
            "replanFraction": len(replans) / len(on_cadence) if on_cadence else float("nan"),
            "offCadenceExcluded": len(off_cadence),
            "offCadenceRule": f"|cadence - median| > {OFF_CADENCE_TOLERANCE_HOURS} h",
            "reportedPairs": len(clean),
        },
        "interpolationSelfTest": self_test,
        "spliceScan": splice,
        "medianOrbitRadiusKm": radius_km,
        "consequence": consequences,
        "containment": containment,
        "containmentWithReplans": summarise_containment(
            on_cadence, leads, "re-plans NOT excluded, for comparison"
        ),
        "containmentCountingIdenticalStates": summarise_containment(
            clean,
            leads,
            "re-plans excluded, but instants where the later issue republishes the "
            "earlier issue's own state COUNTED as contained -- shown because the "
            "registration did not anticipate them and a reader must see what they do",
            informative_only=False,
        ),
        "newInformationHorizonHours": {
            "median": safe_median([r.new_information_horizon_hours for r in clean]),
            "p05": quantile(
                [r.new_information_horizon_hours for r in clean
                 if not math.isnan(r.new_information_horizon_hours)], 0.05
            ),
            "p95": quantile(
                [r.new_information_horizon_hours for r in clean
                 if not math.isnan(r.new_information_horizon_hours)], 0.95
            ),
            "pairsWithAHorizon": sum(
                1 for r in clean if not math.isnan(r.new_information_horizon_hours)
            ),
            "pairsWithoutOne": sum(
                1 for r in clean if math.isnan(r.new_information_horizon_hours)
            ),
            "note": "the smallest lead beyond which the later issue republishes the "
            "earlier issue's own state at every measured lead in the overlap",
        },
        "census": census_out,
        "semiMajorAxisStepM": {
            "holdoutN": len(holdout_steps),
            "holdoutP99": quantile(holdout_steps, 0.99) if holdout_steps else float("nan"),
            "holdoutMedian": safe_median(holdout_steps),
            "reportedMedian": safe_median(
                [result.delta_a_step_m for result in on_cadence]
            ),
        },
    }


def source_sha256() -> dict:
    """The exact bytes that produced the numbers."""
    import hashlib

    here = Path(__file__).resolve().parent
    out = {}
    for name in ("covariance_realism.py", "starlink_collect.py", "starlink_ephemeris.py"):
        path = here / name
        if path.exists():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="directory of gzipped public ephemeris products",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--self-test-files", type=int, default=25)
    parser.add_argument("--registration-commit", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    import socket as _socket

    payload = {
        "study": "T19 covariance realism of a megaconstellation's public ephemerides",
        "registration": "docs/t19-covariance-realism-preregistration-20260922.md",
        "registrationCommit": args.registration_commit,
        "generated": utc_now_iso(),
        "host": _socket.gethostname(),
        "archive": str(args.root),
        "runs": run(args.root, limit=args.limit, self_test_files=args.self_test_files),
        "sourceSha256": source_sha256(),
    }
    text = json.dumps(payload, indent=1, sort_keys=True, default=str)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
