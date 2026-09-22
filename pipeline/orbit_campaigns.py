#!/usr/bin/env python3
"""Per-object orbital history: how often an object corrects, what it spends, and what is unusual *for it*.

`pipeline/orbit_events.py` answers "what kind of change was this, and what did
it cost", judged against a **cohort** — other objects at the same altitude and
inclination over the same hours. That detector was built deliberately for an
archive hours old, because a cohort needs many objects at one moment rather than
one object over many months.

This module is the other half, and it only became possible when the archive
gained real depth. It judges an object against **its own history**, which is the
control the operational questions actually require:

* *"how often a satellite needs correction"* is a cadence, and a cadence is a
  property of one object's own time series.
* *"ones that constantly need a similar correction"* is a repeat cluster: the
  same signature, at a similar cost, at a similar spacing.
* *"one that is acting out of the ordinary"* has two readings and both are
  computed here — out of the ordinary for its **class**
  (`data/orbit_manoeuvre_expectations.json`, already scored by `orbit_events`)
  and out of the ordinary for **itself**, which no class file can encode.

Why the self-history baseline is better than a modelled one
-----------------------------------------------------------
The expectation for the next interval is the **median of this object's own
recent intervals**, not a drag model and not a perturbation formula. That single
choice absorbs, with no constants to get wrong:

* atmospheric drag, including this object's own ballistic coefficient, which no
  longer has to be recovered from a B* that is often unfitted or negative;
* a geomagnetic storm, because the object's neighbours *in time* flew through
  the same storm;
* the solar cycle, for the same reason, which is the thing
  `docs/orbit-browser-wiring.md` §7 records as needing F10.7 to correct for;
* luni-solar precession of the plane and triaxial libration at geostationary
  altitude — the two natural drifts that made the first cohort run report
  station-keeping on satellites dead since the 1970s. Here they are simply part
  of what this object normally does.

The catalogue's measured noise floor and those two analytic bounds are still
applied underneath, as an absolute floor, so a self-history scale that collapses
on a very quiet object cannot manufacture a detection.

Median of medians, because a plain window median is too slow and a mean is not
robust at all
-------------------------------------------------------------------------------
A median over a +/-30 day window recomputed at every interval is O(N w log w),
which at fifteen million intervals is not a computation that finishes. Instead
intervals are bucketed into five-day **blocks**; each block contributes one
median rate and one median absolute deviation; and the baseline for a block is
the median of the block medians within +/-6 blocks.

That is not only faster, it is *more* robust in the way that matters here. A
burn contaminates its own block, and one contaminated block among thirteen is
outvoted; the burn therefore cannot lift the baseline it is being measured
against. The interval-level scale comes from the median of the block MADs over
the same window, so the scale is likewise taken from blocks that do not contain
the event.

What this module does not do
----------------------------
* It does not label anything a manoeuvre. Every event it produces carries
  `confidence` beginning with `candidate`, exactly as `orbit_events` does, and
  the label policy is decided by the measured false-alarm rate in
  `control_rates_by_object`, never here.
* It does not associate objects with one another. It reads one object at a
  time and has no access to any other object's identity, which is the
  structural half of `docs/mission-speculation-design.md` §1.6.
* It does not speculate about purpose. It reuses `opacity_denied` from
  `orbit_events` unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import multiprocessing
import os
import signal
import sqlite3
import statistics
import sys
import time
from array import array
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                      # pragma: no cover - CLI convenience
    sys.path.insert(0, str(ROOT))

from pipeline.orbit_events import (  # noqa: E402
    ANGLE_QUANTISATION_DEG,
    ChannelTest,
    DRAG_MODEL_CEILING_KM,
    DeltaV,
    DragPrediction,
    Expectations,
    GroundTruth,
    Interval,
    MINIMUM_SPAN_DAYS,
    MINIMUM_USABLE_BSTAR,
    MU_WGS72,
    NODE_CHANNEL_KAPPA_MULTIPLIER,
    NODE_MINIMUM_INCLINATION_DEG,
    NON_PROPULSIVE_SIGNATURES,
    OrbitEvent,
    PASSIVE_TYPES,
    RE_WGS72,
    SCAN_COLUMNS_WITH_ANGLES,
    separation_verdict,
    TERMINAL_DECAY_PERIGEE_KM,
    _iso,
    _jeffreys_interval,
    _parse_iso_ms,
    _two_proportion_z,
    classify_change,
    delta_v,
    interval_from_pair,
    load_catalog,
    natural_floor,
    noise_floor_for,
    opacity_denied,
    score_against_expectation,
    sun_synchronous,
)
from pipeline.orbit_events import observation_span_days  # noqa: E402
from pipeline import orbit_history  # noqa: E402
from pipeline.orbit_history import (ARCHIVE_NAME, archive_db_path, archive_root,
                                    archive_stats, open_archive)  # noqa: E402

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Constants, each with the reason it has the value it has
# ---------------------------------------------------------------------------
# Five days. Long enough that a block holds several element sets for anything
# the catalogue tracks routinely (space-track publishes 1-3 fits a day for a
# typical payload, so a block holds 5-15), short enough that thirteen of them
# span a window over which drag is genuinely slowly varying.
BLOCK_DAYS = 5.0

# +/-6 blocks, so a baseline is drawn from up to thirteen blocks spanning sixty
# days. The breakdown point of a median is 50%: an object would have to be
# manoeuvring in seven of thirteen blocks before its own burns became its
# baseline. An object doing that is one of the daily-station-keeping cases the
# expectations file already describes as ordinary, and for those the honest
# answer really is "this is what it always does".
BASELINE_BLOCKS = 6

# A baseline needs at least this many blocks and this many intervals behind it.
# Below either, the object gets no self-history verdict at all and says so;
# `orbit_events`' cohort screen is the detector that covers those objects.
MINIMUM_BASELINE_BLOCKS = 3
MINIMUM_BASELINE_INTERVALS = 8

# The standalone/calibration default. Production supplies its independently
# measured self-history operating point from `orbit_release`; the cohort lane
# keeps its own threshold and control.
DEFAULT_KAPPA = 8.0

# This is a separate, fixture-proven candidate lane. Its evidence threshold is
# intentionally frozen at the value it was designed and tested with: calibrating
# the ordinary self-history step detector must not silently tune a lane that has
# no live positive campaign yet.
THRUST_EXCESS_KAPPA = DEFAULT_KAPPA

# An object needs this many intervals before a *cadence* is reported. Four
# corrections at irregular spacing are not a cadence, and dividing an event
# count by an observation span shorter than the cadence itself produces a rate
# that is pure sampling artefact.
MINIMUM_EVENTS_FOR_CADENCE = 3

# Two events count as "the same correction again" when their costs agree within
# this fraction. A tolerance band rather than a rounded bucket, for the reason
# `pipeline/teaching_brief.py` documents at length: a bucket boundary is
# unstable exactly where the data sits, so two 0.999 m/s burns can land either
# side of a 1 m/s edge and stop being the same correction.
REPEAT_RELATIVE_TOLERANCE = 0.35

# Below this the relative tolerance is meaningless because the numbers are all
# tiny; costs under it are compared on an absolute band instead.
REPEAT_ABSOLUTE_TOLERANCE_MPS = 0.02

# An interval longer than this is not a gap in the object's activity, it is a
# gap in the archive, and a cadence must never be computed across one. The
# archive holds a real hole between the end of the bulk bundles and the start of
# live capture; a "days between corrections" figure that spans it would be a
# measurement of the hole.
MAXIMUM_JOINABLE_GAP_DAYS = 3.0

# How long a change has to stay before it is believed. Two days is several
# fitted element sets for anything the catalogue tracks routinely, so a single
# loose fit cannot survive it, while a real burn survives it forever.
PERSISTENCE_HORIZON_DAYS = 2.0

# ---------------------------------------------------------------------------
# Continuous thrust
# ---------------------------------------------------------------------------
# A STEP DETECTOR CANNOT SEE A LOW-THRUST BURN, and no amount of tuning makes
# it. Electric propulsion spread over days changes the semi-major axis by a few
# metres per revolution; there is no discontinuity between two element sets for
# `step_persistence` to find, and there is nothing wrong with that -- measured
# on the live archive, STARLINK-3005 offers 789 usable intervals and produces
# zero events, which is the correct answer to the question the step detector
# asks and a useless answer to the question a reader has.
#
# The question a reader has is a different one: this is a continuous-burn
# design, but on this day we see greater burn than usual. So there are two
# separate claims here, and keeping them separate is the point.
#
# **One: is this object under thrust at all.** Atmospheric drag can only take
# energy out of an orbit. An object whose semi-major axis climbs, and keeps
# climbing, block after block, is doing something the atmosphere cannot do. No
# drag model is needed for that -- only the sign -- and it is a publishable
# fact the site currently says nothing about. The converse is NOT claimed: a
# sustained FALL is exactly what drag does, and separating a slow retrograde
# burn from the atmosphere needs a drag prediction this per-object pass does
# not have. It says so rather than guessing.
#
# **Two: was this interval faster than that object's own normal thrust.** An
# excess over a fitted baseline. Not a measured burn -- nobody publishes what
# the thruster did -- and the signature is named `thrust-excess` rather than
# reusing `manoeuvre` so that no reader, and no downstream summary, can mistake
# the one for the other.

# Four five-day blocks, so twenty days of one-signed climb before the word
# "sustained" is used. Three would be the module's baseline minimum, and three
# blocks is a fortnight -- inside the range over which a geomagnetic storm and
# its recovery can bend a whole shell one way and then the other.
SUSTAINED_THRUST_MINIMUM_BLOCKS = 4

# What fraction of the blocks in the window must climb. Not all of them: a
# thrusting object still coasts through a safe-mode day or a conjunction
# avoidance, and demanding unanimity would throw away exactly the objects whose
# thrust varies -- which are the ones the second test is for.
SUSTAINED_THRUST_SIGN_AGREEMENT = 0.8

# How far above zero the median block rate has to sit, in units of the standard
# error of that median (the block-to-block robust scale over the square root of
# the block count). The same robust-sigma multiple the rest of the module uses,
# applied to a different statistic on purpose: this is a test of a median
# against zero over many blocks, not of one interval against its neighbours.
#
# Swept against the passive control over 29,401 objects of the live archive
# (10,020 of them debris or spent stages), with the sign-agreement bar beside
# it:
#
#     kappa   agreement   passive claims   payload claims
#       8        0.8            0                33
#       8        1.0            0                11
#       4        0.8            1                72
#       4        1.0            0                25
#       3        0.8            4                92
#       2        0.8            6               160
#
# The shipped point is the top row: it is the only one that both claims nothing
# on 10,020 objects with no propulsion AND keeps the most payloads, which is
# not the usual shape of such a curve and is worth noticing -- relaxing kappa
# below 8 buys payloads at the cost of the control, while demanding unanimity
# instead of four fifths costs two thirds of the payloads and buys nothing,
# because the control was already empty.
SUSTAINED_THRUST_KAPPA = DEFAULT_KAPPA

# How much faster than its own baseline an interval has to climb before it is
# called an excess. A ratio rather than an absolute rate, because the whole
# point is that the object's own normal thrust sets the scale: twice the usual
# climb is the same statement about a Starlink raising at 200 m/day as about
# one raising at 20. The significance test underneath it is separate and is
# measured in the object's own noise, so this is the MATERIALITY bar and not
# the evidence bar -- both have to be cleared.
THRUST_EXCESS_RATIO = 2.0

# How much of the step has to still be there at the end of that window. Half,
# rather than all, because the baseline is itself an estimate and because a
# manoeuvre is often followed by a corrective one in the other direction --
# demanding the full step back would throw away exactly the objects that
# manoeuvre most.
PERSISTENCE_FRACTION = 0.5


# ---------------------------------------------------------------------------
# Streaming the archive
# ---------------------------------------------------------------------------
def open_archive_for_reading(path: Path | None = None) -> sqlite3.Connection:
    """A connection that cannot write, and therefore cannot be blocked by a writer.

    `orbit_history.open_archive` sets `PRAGMA journal_mode=TRUNCATE` and runs the
    schema script, both of which take a write lock. That is correct for the
    ingest, and it means **every reader using it fails with `database is locked`
    while the bulk back-fill is importing** — which is hours at a time, on the
    same file, and was observed doing exactly that.

    Reading is a different job with different needs, so it gets a different
    door: `mode=ro` via URI, no pragmas, no schema. A reader still waits behind a
    writer's commit, which is why the timeout is generous, but it is never
    refused for wanting a lock it does not need.

    Falls back to the read-write opener when the file does not exist, so the
    absent-archive path still produces the same error the callers already handle.
    """
    target = path if path is not None else archive_db_path()
    if not target.is_file():
        return open_archive(path)
    # The same generous timeout the writers use, and it matters more since the
    # scan was paged: this connection now acquires a SHARED lock once per page
    # — roughly 190 times over the live archive — instead of once for the run.
    # Every one of those acquisitions can land while the back-fill is committing,
    # and a reader that gives up half way through leaves the release with no
    # fresh fragment at all.
    connection = sqlite3.connect(
        f"file:{target}?mode=ro", uri=True, timeout=orbit_history.busy_timeout_seconds()
    )
    connection.execute("PRAGMA query_only=1")
    return connection



def stream_object_rows(
    connection: sqlite3.Connection,
    *,
    since_ms: int | None = None,
    only: Sequence[int] | None = None,
    page_rows: int | None = None,
    start_after_norad: int | None = None,
) -> Iterator[tuple[int, list[tuple[int, float, float, float, float | None]]]]:
    """Yield one object at a time, in catalogue order, holding one object at a time.

    `element_set` is `WITHOUT ROWID` keyed on `(norad, epoch_ms)`, so an
    unfiltered ordered scan is a sequential walk of the primary-key b-tree: no
    sort, no temporary file, and measured at 215,000 rows/s warm on this
    machine. A `WHERE epoch_ms BETWEEN ...` clause does **not** help — there is
    no index on `epoch_ms`, so it is the same full scan with a filter on top,
    and it is also what forced the whole result into memory in the first
    implementation of this pass.

    `since_ms` is applied in Python for that reason: it costs nothing beyond
    the scan that was happening anyway, and it never changes the access path.

    THE SCAN IS PAGED, AND THAT IS NOT AN OPTIMISATION
    --------------------------------------------------
    The rows come from `orbit_history.paged_element_sets`, which ends its read
    transaction every `page_rows` rows. This function used to open one cursor
    and iterate it to the end, which held a SHARED lock on the archive for the
    32-45 minutes the release takes — and in rollback-journal mode a SHARED lock
    is what stops a writer reaching EXCLUSIVE. The hourly capture, whose data
    cannot be re-fetched, was starved to death by it twice on 2026-08-08.

    Note that the lock was held not merely for the reading but for the whole of
    the caller's work as well, because the caller does its analysis between
    `next()` calls on the cursor. Paging drops the lock during that too, which
    is most of the run.
    """
    rows = orbit_history.paged_element_sets(
        connection,
        only=only,
        page_rows=page_rows,
        start_after_norad=start_after_norad,
        columns=SCAN_COLUMNS_WITH_ANGLES,
    )

    current: int | None = None
    buffer: list[tuple] = []
    for norad, epoch_ms, mm_q, ecc_q, inc_q, bstar_q, raan_q, argp_q in rows:
        if norad != current:
            if current is not None and buffer:
                yield current, buffer
            current, buffer = norad, []
        if since_ms is not None and epoch_ms < since_ms:
            continue
        buffer.append(
            (
                epoch_ms,
                mm_q / 1e8,
                ecc_q / 1e8,
                inc_q / 1e4,
                None if bstar_q is None else bstar_q / 1e12,
                raan_q / 1e4,
                argp_q / 1e4,
            )
        )
    if current is not None and buffer:
        yield current, buffer


def intervals_from_rows(
    norad: int,
    name: str,
    object_type: str,
    rows: Sequence[Sequence[Any]],
    *,
    minimum_span_days: float = MINIMUM_SPAN_DAYS,
    max_gap_days: float = MAXIMUM_JOINABLE_GAP_DAYS,
    epoch_slices: dict | None = None,
) -> list[Interval]:
    """Consecutive usable pairs for one object.

    Identical in every field to what `orbit_events.load_intervals` builds,
    because since the node and apse-line channels were added the two call the
    SAME constructor -- `orbit_events.interval_from_pair` -- rather than
    holding two hand-copied bodies that had to be kept field-for-field
    identical. The agreement of the two detectors is the release's only
    cross-check, so a divergence between them would have read as a
    disagreement about the sky rather than as a typo. The only difference left
    is that this one is fed one object at a time.

    A row is `(epoch_ms, mean_motion, eccentricity, inclination, bstar)` with
    the node and argument of perigee optionally appended; a five-element row
    simply produces an Interval whose angle channels are not opened.
    """
    columns = getattr(rows, "columns", None)
    if columns is not None:
        # tolist converts in C to the SAME Python scalars as the SQLite reader.
        # Zip is lazy: no full list of row tuples or dequantisation pass.
        from pipeline.orbit_columnar import FIELDS
        epoch = columns["epoch_ms"]
        values = [columns[n].tolist() for n in FIELDS]
        values[4] = [None if math.isnan(v) else v for v in values[4]]
        iterator = iter(zip(*values))
        first = next(iterator, None)
        def pairs():
            nonlocal first
            for second in iterator:
                yield first, second
                first = second
        paired = pairs()
        out = []
        positions = []
    else:
        out = []
        paired = zip(rows, rows[1:])
    for position, (first, second) in enumerate(paired):
        built = interval_from_pair(
            norad,
            name,
            object_type,
            first,
            second,
            minimum_span_days=minimum_span_days,
            max_gap_days=max_gap_days,
        )
        if built is not None:
            out.append(built)
            if columns is not None and epoch_slices is not None:
                positions.append(position)
    if columns is not None and epoch_slices is not None:
        # Contiguous accepted pairs borrow slices directly. Rejected interior
        # pairs need a gather; never misalign epochs with the accepted intervals.
        import numpy as np
        if positions and positions[-1] - positions[0] + 1 == len(positions):
            start, end = positions[0], positions[-1] + 1
            epoch_slices["starts"] = epoch[start:end]
            epoch_slices["ends"] = epoch[start + 1:end + 1]
        else:
            indices = np.asarray(positions, dtype=np.int64)
            epoch_slices["starts"], epoch_slices["ends"] = epoch[indices], epoch[indices + 1]
    return out


# ---------------------------------------------------------------------------
# The self-history baseline
# ---------------------------------------------------------------------------
# The self-history node channel is implemented below, but the complete
# 2026-09-04 archive control produced 63,190 RAAN trips on passive objects.
# The acceptance rule is explicit: any passive node flags keep this channel
# off. Cohort RAAN remains independently enabled in orbit_events.py.
SELF_HISTORY_NODE_CHANNEL_ENABLED = False
# DETECTOR-DESIGN.md F3/F1/F4: implemented, not calibrated. The offline
# acceptance suite (tests/acceptance_detector_fixes.py) must earn each switch
# with a separate whole-archive measurement. Fixture success is not evidence.
INCLINATION_FLOOR_TAIL_AWARE = False
MATCHED_CONTROL_STRATA_ENABLED = False
DECLINE_AFTER_TRACKING_GAP = False


def detector_flags() -> dict[str, bool]:
    """Part of the checkpoint identity and published measurement provenance."""
    return {
        "INCLINATION_FLOOR_TAIL_AWARE": INCLINATION_FLOOR_TAIL_AWARE,
        "MATCHED_CONTROL_STRATA_ENABLED": MATCHED_CONTROL_STRATA_ENABLED,
        "DECLINE_AFTER_TRACKING_GAP": DECLINE_AFTER_TRACKING_GAP,
    }


ELEMENTS = ("semiMajorAxis", "inclination", "eccentricity") + (
    ("raan",) if SELF_HISTORY_NODE_CHANNEL_ENABLED else ()
)


def _observed(interval: Interval, element: str) -> float | None:
    if element == "semiMajorAxis":
        return interval.delta_a_km * 1000.0
    if element == "inclination":
        return interval.delta_i_deg
    if element == "raan":
        node_defined = (
            interval.angles_measured
            and abs(interval.inclination_deg) >= NODE_MINIMUM_INCLINATION_DEG
            and abs(interval.inclination_deg - 180.0) >= NODE_MINIMUM_INCLINATION_DEG
        )
        return interval.raan_residual_deg if node_defined else None
    return interval.delta_e


@dataclass(frozen=True)
class Baseline:
    """What this object normally does per day, and how tightly it does it."""

    rate: float           # median rate, per day, in the element's own units
    scale: float          # robust interval-level scatter of that rate, per day
    blocks: int
    samples: int
    # The two sources `scale` is the larger of, kept separately because they
    # behave differently when several intervals are averaged. `within` is the
    # interval-to-interval scatter inside a block: part of it is per-fit noise,
    # so it AVERAGES DOWN over n intervals. `between` is the block-to-block
    # scatter of the baseline itself: it is the object's rate genuinely moving,
    # so it does not average down at all. A test over one interval wants the
    # larger of the two, which is what `scale` is and what `_self_channel`
    # uses. A test over a whole day of intervals wants
    # `hypot(within / sqrt(n), between)`, and could not compute it from `scale`
    # alone. Appended with defaults so the keyword constructions in the tests
    # are untouched.
    within: float = 0.0
    between: float = 0.0

    @property
    def usable(self) -> bool:
        return self.blocks >= MINIMUM_BASELINE_BLOCKS and self.samples >= MINIMUM_BASELINE_INTERVALS


@dataclass(frozen=True)
class _Block:
    median: float
    mad: float
    count: int


def _blocks_for(intervals: Sequence[Interval], element: str) -> dict[int, _Block]:
    """One median and one MAD per five-day block of this object's own history."""
    grouped: dict[int, list[float]] = {}
    for interval in intervals:
        if interval.span_days <= 0:
            continue
        index = int(interval.mid_ms // int(BLOCK_DAYS * 86_400_000))
        observed = _observed(interval, element)
        if observed is None:
            continue
        grouped.setdefault(index, []).append(observed / interval.span_days)
    blocks: dict[int, _Block] = {}
    for index, rates in grouped.items():
        median = statistics.median(rates)
        mad = statistics.median([abs(rate - median) for rate in rates]) * 1.4826
        blocks[index] = _Block(median=median, mad=mad, count=len(rates))
    return blocks


def baseline_at(blocks: dict[int, _Block], index: int) -> Baseline:
    """Median of the block medians within +/-`BASELINE_BLOCKS`, excluding this block.

    **Excluding this block is the part that matters.** A burn is in its own
    block, and a baseline that included it would have absorbed part of the very
    thing being measured — the "billing an operator for a channel that never
    tripped" mistake in a different disguise.
    """
    medians: list[float] = []
    mads: list[float] = []
    samples = 0
    for offset in range(-BASELINE_BLOCKS, BASELINE_BLOCKS + 1):
        if offset == 0:
            continue
        block = blocks.get(index + offset)
        if block is None:
            continue
        medians.append(block.median)
        mads.append(block.mad)
        samples += block.count
    if not medians:
        return Baseline(rate=0.0, scale=0.0, blocks=0, samples=0)
    median = statistics.median(medians)
    # Two sources of scatter, and the larger wins: the interval-to-interval
    # scatter inside blocks, and the block-to-block scatter of the baseline
    # itself. The second matters on an object whose drag is changing fast --
    # a tight block scatter around a rapidly moving baseline would otherwise
    # report the movement as a burn.
    within = statistics.median(mads)
    between = statistics.median([abs(m - median) for m in medians]) * 1.4826
    return Baseline(
        rate=median,
        scale=max(within, between),
        blocks=len(medians),
        samples=samples,
        within=within,
        between=between,
    )


def _self_channel(
    interval: Interval,
    element: str,
    baseline: Baseline,
    *,
    kappa: float,
    own_floor: float = 0.0,
) -> ChannelTest | None:
    """One element tested against this object's own recent behaviour.

    Nothing is tested against zero, for the same reason `orbit_events._channel`
    says so at length; here the expectation is measured from the object rather
    than from its neighbours.

    **Two noise terms, not one, because a fitted element set has two kinds of
    error and they scale differently.** There is an error in each individual
    fit, which is a fixed number of metres and does not care how long the
    interval was; and there is an error in the rate the baseline predicts,
    which does grow with the interval. Combining them in quadrature is the
    difference between a working detector and one that fires constantly on
    short intervals.

    `own_floor` is the first term, **measured from this object's own residuals**
    rather than taken from the catalogue-wide table. That table
    (`orbit_events.CATALOGUE_NOISE_FLOOR`) was measured on 787 triples of the
    live catalogue, which is dominated by well-tracked payloads. A tumbling
    fragment with a poor radar cross-section is fitted far more loosely than
    that, and holding it to a payload's noise floor reported 1.39% of all
    passive intervals as manoeuvres — fourteen times the design target, on
    objects with no propulsion at all. The catalogue floor is still applied as
    a lower bound, so this can only ever make the detector more conservative,
    never less.
    """
    observed = _observed(interval, element)
    if observed is None:
        return None
    floor_sigma = max(natural_floor(interval, element), own_floor)
    expected = baseline.rate * interval.span_days
    expectation_sigma = baseline.scale * interval.span_days
    residual = observed - expected
    sigma = math.hypot(floor_sigma, expectation_sigma)
    floor_z = residual / sigma if sigma > 0 else 0.0
    self_z = residual / expectation_sigma if expectation_sigma > 0 else None
    tripped = (
        baseline.usable
        and abs(floor_z) > kappa
        and (self_z is None or abs(self_z) > kappa)
    )
    return ChannelTest(
        element=element,
        delta=residual,
        floor_sigma=sigma,
        floor_z=floor_z,
        cohort_z=self_z,
        cohort_count=baseline.samples,
        cohort_screened=baseline.usable,
        tripped=tripped,
        basis="self-history",
    )


def step_persistence(
    intervals: Sequence[Interval],
    baselines: Sequence[dict[str, Baseline]],
    position: int,
    *,
    element: str,
) -> dict[str, Any]:
    """Did the orbit stay changed, or did the next fit put it back?

    **This is a physical test, not a threshold, and it is what finally
    separated the detector from its own noise.** A manoeuvre moves the orbit
    and the orbit stays moved: the operator spent propellant and bought a new
    semi-major axis. A bad fit moves one published element set and the next one
    puts it back, because nothing physical happened.

    So the residual is accumulated forward. If interval `k` really was a step,
    the running sum of (observed - expected) over the intervals after it stays
    near the size of the step. If `k` was one loose fit at its own boundary
    epoch, the very next interval carries an equal and opposite residual and
    the running sum collapses to nothing.

    Measured on 203,719 intervals of debris and spent stages -- objects that
    cannot manoeuvre, so every flag is wrong by construction -- requiring the
    displacement to survive two days took the false-alarm rate from
    8.4 per 1,000 intervals to the figure recorded in
    `docs/orbit-browser-wiring.md` §5, without moving kappa at all.

    The honest cost: an event in the last two days of an object's coverage, or
    immediately before a gap, has nothing after it to be persistent *in*, and
    is declined rather than guessed at. A reboost on the archive's final day is
    therefore missed. That is the right way round -- the alternative is a
    detector whose newest and most eye-catching claims are its least tested.
    """
    interval = intervals[position]
    observed = _observed(interval, element)
    if observed is None:
        return {"persistent": False, "reason": "this element is not measurable on this interval"}
    residual = observed - baselines[position][element].rate * interval.span_days
    if residual == 0:
        return {"persistent": False, "reason": "no residual to persist"}

    # Look back one interval first. A single loose fit produces TWO tripped
    # intervals, not one: the excursion away from the trend and the return to
    # it. The forward test rejects the excursion, because the return cancels
    # it -- but it accepts the return, whose own "step" is followed by a level
    # that stays put forever, since it is the trend the object was always on.
    # The signature of a return is an immediately preceding residual of the
    # opposite sign and comparable size, and propellant cannot produce that
    # pattern: a burn is not preceded by an equal and opposite burn one element
    # set earlier.
    if position > 0:
        previous = intervals[position - 1]
        joinable = interval.start_ms - previous.end_ms <= MAXIMUM_JOINABLE_GAP_DAYS * 86_400_000
        previous_observed = _observed(previous, element)
        previous_residual = (
            None
            if previous_observed is None
            else previous_observed
                 - baselines[position - 1][element].rate * previous.span_days
        )
        if joinable and previous_residual is not None and previous_residual * residual < 0 and (
            abs(previous_residual + residual) < PERSISTENCE_FRACTION * abs(residual)
        ):
            return {
                "persistent": False,
                "element": element,
                "reason": "the element set immediately before this one moved the same amount the "
                          "other way, so this is the catalogue's fit returning to trend rather "
                          "than a change in the orbit",
                "intervalsChecked": 0,
            }

    horizon_ms = int(PERSISTENCE_HORIZON_DAYS * 86_400_000)
    running = residual
    lowest = abs(residual)
    checked = 0
    previous_end = interval.end_ms
    for later, later_baselines in zip(intervals[position + 1:], baselines[position + 1:]):
        if later.start_ms - previous_end > MAXIMUM_JOINABLE_GAP_DAYS * 86_400_000:
            break                                   # a gap: nothing to test against
        if later.start_ms - interval.end_ms > horizon_ms:
            break
        later_observed = _observed(later, element)
        if later_observed is None:
            break
        running += later_observed - later_baselines[element].rate * later.span_days
        # Sign agreement matters as much as magnitude: a displacement that
        # comes back through zero and out the other side is not the original
        # step surviving, it is a different excursion.
        lowest = min(lowest, running if residual > 0 else -running)
        checked += 1
        previous_end = later.end_ms

    observed_horizon_ms = previous_end - interval.end_ms
    if checked == 0 or observed_horizon_ms < horizon_ms:
        return {
            "persistent": False,
            "reason": "the archive does not continue for two observed days after this interval, "
                      "so the change could not be checked for persistence",
            "intervalsChecked": checked,
            "observedHorizonDays": round(observed_horizon_ms / 86_400_000.0, 3),
        }
    survived = lowest / abs(residual)
    return {
        "persistent": survived >= PERSISTENCE_FRACTION,
        "element": element,
        "stepSize": residual,
        "survivingFraction": round(survived, 3),
        "intervalsChecked": checked,
        "horizonDays": PERSISTENCE_HORIZON_DAYS,
        "observedHorizonDays": round(observed_horizon_ms / 86_400_000.0, 3),
        "reason": (
            "the change was still there after the following element sets"
            if survived >= PERSISTENCE_FRACTION
            else "the next element sets put the orbit back, which propellant cannot do"
        ),
    }


def sustained_thrust(intervals: Sequence[Interval]) -> dict[str, Any]:
    """Is this object under continuous thrust, and how hard?

    **The whole test is the sign.** Atmospheric drag removes energy from an
    orbit and cannot add it. An object whose semi-major axis climbs across
    block after block of its own history is being pushed, and the claim needs
    no drag model, no ballistic coefficient and no cohort -- which is what
    makes it safe to make on an object whose B* is unfitted or negative, and
    what makes it impossible to make by accident on a piece of debris.

    Four things have to hold, and each of them is there because something else
    can raise a semi-major axis or fake a rise:

    * **Enough blocks, mostly agreeing.** Twenty days of climb, in at least
      four fifths of the five-day blocks. One storm recovery is not a thruster.
    * **The median block rate is above zero by more than its own standard
      error**, measured from the block-to-block scatter rather than assumed.
    * **The object is not re-entering.** Below `TERMINAL_DECAY_PERIGEE_KM` the
      fits are being dragged around faster than they can be made and no
      propulsive claim of any kind is asserted.

    AND THE GATE THAT MATTERS MOST, WHICH THE PASSIVE CONTROL PUT THERE
    ------------------------------------------------------------------
    **The whole argument is "drag can only take energy out", and it is only an
    argument where drag is certainly acting.** The first version of this
    function applied it everywhere and duly reported sustained thrust on 86
    objects that have no propulsion: geostationary transfer stages, spent
    upper stages in the geosynchronous neighbourhood, and Molniya-orbit debris.
    None of those is a paradox. Above the drag regime nothing is guaranteed to
    be pushing `a` down, so a slow rise is not evidence that something pushed
    it up: near the geosynchronous ring the Earth's equatorial ellipticity
    oscillates `a` on a period of years, which a month of observation cannot
    tell from a climb; on a highly eccentric orbit the mean elements are
    fitted through a regime the model handles worst, and third-body gravity
    moves the orbit on periods of months.

    So the claim is confined to orbits where the null is a guarantee rather
    than an assumption: **apogee inside the drag regime, and a usable positive
    ballistic coefficient.** An object that is entirely inside the atmosphere's
    reach, and is coupled to it, must be losing energy. If it is not, something
    is holding it up. Outside that regime the function declines and says which
    gate it failed, because "we cannot tell here" is a different statement from
    "it is not thrusting" and the two must not be published as the same thing.

    That one gate also subsumes the geostationary triaxiality trap, which the
    first version of this function guarded separately with
    `geo_libration_bound_metres`: the geostationary ring is 35,786 km up and
    the drag ceiling is 1,400 km, so the ring is outside this test entirely and
    a second bound on it would be a branch that can never run.

    A sustained FALL returns `underThrust` false with a reason that says why,
    rather than a claim: that is what drag looks like, and this pass has no
    drag prediction to subtract from it.
    """
    usable = [i for i in intervals if i.span_days > 0]
    if not usable:
        return {"underThrust": False, "reason": "no usable intervals"}
    latest = usable[-1]
    # The LOWEST perigee in the window, not the current one. An object that
    # climbed out of the terminal-decay regime during the window spent the
    # early part of it being fitted through air that was changing faster than
    # the arc, and those intervals are in the median this verdict rests on.
    if min(i.perigee_altitude_km for i in usable) < TERMINAL_DECAY_PERIGEE_KM:
        return {
            "underThrust": False,
            "reason": (
                "perigee was below two hundred kilometres inside this window, where the "
                "atmosphere changes the orbit faster than the elements describing it can "
                "be fitted"
            ),
        }
    if max(i.apogee_altitude_km for i in usable) > DRAG_MODEL_CEILING_KM:
        return {
            "underThrust": False,
            "reason": (
                "this orbit reaches above the altitude where atmospheric drag governs the "
                "semi-major axis, so a rise in it is not by itself evidence that anything "
                "pushed: nothing is guaranteed to be pushing the other way"
            ),
        }
    if latest.bstar is None or latest.bstar < MINIMUM_USABLE_BSTAR:
        return {
            "underThrust": False,
            "reason": (
                "no usable ballistic coefficient, so there is no evidence this object is "
                "coupled to the atmosphere at all and no drag for thrust to be measured against"
            ),
        }
    blocks = _blocks_for(usable, "semiMajorAxis")
    if len(blocks) < SUSTAINED_THRUST_MINIMUM_BLOCKS:
        return {
            "underThrust": False,
            "blocks": len(blocks),
            "reason": (
                f"only {len(blocks)} five-day block(s) of history; a sustained rate needs "
                f"{SUSTAINED_THRUST_MINIMUM_BLOCKS}"
            ),
        }
    medians = [block.median for block in blocks.values()]
    median = statistics.median(medians)
    scale = statistics.median([abs(m - median) for m in medians]) * 1.4826
    agreement = (
        sum(1 for m in medians if (m > 0) == (median > 0)) / len(medians) if median else 0.0
    )
    standard_error = scale / math.sqrt(len(medians)) if scale > 0 else 0.0
    common = {
        "metresPerDay": round(median, 3),
        "blocks": len(medians),
        "signAgreement": round(agreement, 3),
        "blockScaleMetresPerDay": round(scale, 3),
        "observedDays": round(_covered_days(usable), 2),
    }
    if median <= 0:
        return {
            "underThrust": False,
            **common,
            "reason": (
                "the semi-major axis is falling on average, which is what atmospheric drag "
                "does; separating a slow retrograde burn from the atmosphere needs a drag "
                "prediction, and this pass judges an object only against itself"
            ),
            # A LABELLED GAP, not a verdict of "not thrusting". The most common
            # kind of continuously-thrusting satellite there is -- one holding
            # station against drag -- has a net rate near zero and lands here,
            # and saying only "false" about it would publish a blank where a
            # known blind spot belongs.
            "gap": (
                "A satellite whose thruster exactly cancels its drag has a net rate near zero "
                "and cannot be told apart from one that simply is not decaying without a "
                "prediction of how fast drag alone would bring it down. That prediction needs "
                "a population of comparable objects at the same altitude over the same hours, "
                "which the cohort detector has and this per-object pass does not. So this is "
                "'not shown to be thrusting', which is not the same as 'not thrusting'."
            ),
        }
    if agreement < SUSTAINED_THRUST_SIGN_AGREEMENT:
        return {
            "underThrust": False,
            **common,
            "reason": "the rise is not sustained: the blocks do not agree on its direction",
        }
    if standard_error > 0 and median < SUSTAINED_THRUST_KAPPA * standard_error:
        return {
            "underThrust": False,
            **common,
            "reason": "the average rise is inside the block-to-block scatter of the rate itself",
        }
    return {
        "underThrust": True,
        "direction": "raising",
        **common,
        "reason": (
            "the semi-major axis has climbed across most of the blocks in this object's "
            "history, and atmospheric drag can only take energy out of an orbit"
        ),
        "note": (
            "A rate, not a burn. What is measured is that the orbit is being pushed and how "
            "fast; nothing here says what is doing the pushing, and the figure is an average "
            "over the object's whole observed history rather than a thrust level."
        ),
    }


def window_persistence(
    intervals: Sequence[Interval],
    baselines: Sequence[dict[str, "Baseline"]],
    first: int,
    last: int,
    *,
    element: str,
) -> dict[str, Any]:
    """`step_persistence`, for a change spread over several intervals rather than one.

    Same physical test, same reason, same two halves: a real change leaves the
    orbit changed, and a loose fit is preceded or followed by an equal and
    opposite excursion. The only difference is what counts as "the change" --
    here it is the residual accumulated over the whole window `[first, last]`
    rather than the residual of one interval, because a low-thrust burn is
    spread across the several element sets published during it and has no
    single interval to be the step.

    `step_persistence` is the `first == last` case and is left alone: its
    wording is quoted verbatim on published cards and its behaviour is pinned
    by tests that were written against real archive failures.
    """
    observations = [_observed(intervals[k], element) for k in range(first, last + 1)]
    if any(observed is None for observed in observations):
        return {"persistent": False, "reason": "this element is not measurable across the window"}
    residual = sum(
        observed - baselines[k][element].rate * intervals[k].span_days
        for k, observed in zip(range(first, last + 1), observations)
        if observed is not None
    )
    if residual == 0:
        return {"persistent": False, "reason": "no residual to persist"}

    # The window before this one, of the same length. A catalogue re-fit that
    # moves an object and puts it back produces an excursion and a return, and
    # propellant cannot produce an equal and opposite burn immediately before.
    span = last - first + 1
    if first - span >= 0:
        previous_observations = [
            _observed(intervals[k], element) for k in range(first - span, first)
        ]
        previous = (
            None
            if any(observed is None for observed in previous_observations)
            else sum(
                observed - baselines[k][element].rate * intervals[k].span_days
                for k, observed in zip(range(first - span, first), previous_observations)
                if observed is not None
            )
        )
        joinable = (
            intervals[first].start_ms - intervals[first - 1].end_ms
            <= MAXIMUM_JOINABLE_GAP_DAYS * 86_400_000
        )
        if joinable and previous is not None and previous * residual < 0 and (
            abs(previous + residual) < PERSISTENCE_FRACTION * abs(residual)
        ):
            return {
                "persistent": False,
                "element": element,
                "reason": "the element sets immediately before this window moved the same "
                          "amount the other way, so this is the catalogue's fit returning to "
                          "trend rather than a change in the orbit",
                "intervalsChecked": 0,
            }

    horizon_ms = int(PERSISTENCE_HORIZON_DAYS * 86_400_000)
    running = residual
    lowest = abs(residual)
    checked = 0
    previous_end = intervals[last].end_ms
    for k in range(last + 1, len(intervals)):
        later = intervals[k]
        if later.start_ms - previous_end > MAXIMUM_JOINABLE_GAP_DAYS * 86_400_000:
            break
        if later.start_ms - intervals[last].end_ms > horizon_ms:
            break
        later_observed = _observed(later, element)
        if later_observed is None:
            break
        running += later_observed - baselines[k][element].rate * later.span_days
        lowest = min(lowest, running if residual > 0 else -running)
        checked += 1
        previous_end = later.end_ms

    observed_horizon_ms = previous_end - intervals[last].end_ms
    if checked == 0 or observed_horizon_ms < horizon_ms:
        return {
            "persistent": False,
            "reason": "the archive does not continue for two observed days after this window, "
                      "so the change could not be checked for persistence",
            "intervalsChecked": checked,
            "observedHorizonDays": round(observed_horizon_ms / 86_400_000.0, 3),
        }
    survived = lowest / abs(residual)
    return {
        "persistent": survived >= PERSISTENCE_FRACTION,
        "element": element,
        "stepSize": residual,
        "survivingFraction": round(survived, 3),
        "intervalsChecked": checked,
        "horizonDays": PERSISTENCE_HORIZON_DAYS,
        "observedHorizonDays": round(observed_horizon_ms / 86_400_000.0, 3),
    }


def _daily_windows(intervals: Sequence[Interval]) -> list[tuple[int, int]]:
    """Contiguous runs of intervals sharing a UTC day, as (first, last) indices.

    A day, because that is the unit the question is asked in -- on this day we
    see greater burn than usual -- and because it is the unit a
    low-thrust manoeuvre actually occupies: the catalogue publishes three to six
    fits a day for an object like this, so one day's thrust is spread over
    several intervals and is present in none of them as a step. A run is broken
    by an archive gap as well as by the date, so a window never spans a hole.
    """
    windows: list[tuple[int, int]] = []
    first = 0
    for index in range(1, len(intervals) + 1):
        ends = index == len(intervals)
        if not ends:
            same_day = (
                intervals[index].mid_ms // 86_400_000
                == intervals[first].mid_ms // 86_400_000
            )
            joinable = (
                intervals[index].start_ms - intervals[index - 1].end_ms
                <= MAXIMUM_JOINABLE_GAP_DAYS * 86_400_000
            )
            if same_day and joinable:
                continue
        windows.append((first, index - 1))
        first = index
    return windows


def thrust_excess_events(
    intervals: Sequence[Interval],
    baselines_by_interval: Sequence[dict[str, "Baseline"]],
    *,
    thrust: dict[str, Any],
    kappa: float,
    expectations: Expectations,
    record: dict[str, Any],
    already_flagged: set[int],
) -> list[OrbitEvent]:
    """Days on which a continuously-thrusting object climbed faster than it usually does.

    WHY THIS IS A DAY AND NOT AN INTERVAL, WHICH IS THE WHOLE POINT
    ---------------------------------------------------------------
    A per-interval test cannot find this and no threshold makes it able to. Run
    against one pair of element sets, the excess produced by a low-thrust system
    grows in proportion to the interval, and so does the rate error of the
    baseline it is measured against; the per-fit error stays where it is. So the
    signal-to-noise of a single interval is roughly fixed no matter how the
    threshold is set, and `_self_channel` at kappa=8 is already sitting on it.
    Summed over the several element sets published during one day, the excess
    adds LINEARLY while the per-fit errors add in QUADRATURE -- sqrt(n) against
    n -- and that gap is the only thing that makes the measurement possible.
    Measured on the live archive, STARLINK-3005 offers 789 intervals and the
    per-interval detector returns zero events on it, correctly.

    The noise model reflects that arithmetic exactly:

        rate_sigma = hypot( baseline.within / sqrt(n) , baseline.between )
        sigma      = hypot( floor * sqrt(n) , rate_sigma * total_span )

    -- `n` independent fit errors in quadrature, and a rate error whose two
    halves are treated as what they are. `within` is the interval-to-interval
    scatter of the rate, and averaging n intervals of a day divides it by
    sqrt(n); `between` is how far the object's own rate moves from block to
    block, which averaging does not touch. `_self_channel` uses the larger of
    the two, which is correct for a test over one interval and is what makes it
    blind here: applied to a day it would charge the full interval-level
    scatter to a mean that no longer has it.

    **The per-fit floor here is the catalogue's, and deliberately NOT
    `own_floor`.** `detect_object_events` measures `own_floor` from this
    object's own residuals against its own baseline, which is the right floor
    for a tumbling fragment whose fits are looser than the catalogue-wide table
    assumes. On an object under sustained thrust that same quantity is
    dominated by variation in the thrust, which is the very thing being
    measured: counting it as a per-fit error charges the object's thrust
    variability twice, once in the floor and once in `baseline.scale`, and
    makes an object systematically harder to judge the more it manoeuvres.

    Three bars, and a window has to clear all three:

    * **Materiality.** The window's mean rate is at least
      `THRUST_EXCESS_RATIO` times the baseline rate the object was on. A ratio,
      because the object's own thrust sets the scale: twice the usual climb is
      the same statement about a satellite raising at 200 m/day as about one
      raising at 20.
    * **Evidence.** The accumulated excess clears `kappa` times the sigma
      above.
    * **Persistence.** The orbit stayed where the excess put it, tested over
      the window by `window_persistence`.

    And one gate over all of them: `sustained_thrust` must already have found
    this object to be climbing under thrust. That is what makes the baseline
    being exceeded a THRUST baseline rather than an atmosphere, and it is also
    what keeps this lane off the passive control entirely -- drag cannot raise
    an orbit, so a spent stage cannot reach the gate, let alone the bars.

    The signature is `thrust-excess` and never `manoeuvre`. The Delta-v is
    computed from the EXCESS and not from the whole climb, so what a reader
    sees is "at least this much more than it usually spends", which is a lower
    bound on a difference and not a claim about a total.

    WHAT IT FOUND ON THIRTY DAYS OF THE LIVE ARCHIVE: NOTHING, AND THAT IS
    WORTH WRITING DOWN
    ----------------------------------------------------------------------
    Swept over 32,476 objects and 1.44 M intervals it produced zero events. On
    the 10,020 objects with no propulsion that is structural -- `underThrust`
    cannot be reached without a climb the atmosphere cannot produce -- and it
    is the point. On the 33 objects that WERE found under sustained thrust it
    is a real, if uninteresting, negative: three of their day-windows cleared
    this lane's bar, and all three had already been caught interval-by-interval
    by `_self_channel`, so the lane added nothing the step detector had not
    already said. A raising campaign at a steady rate has no day above its own
    baseline, which is the correct answer.

    So the mechanism is exercised by the fixtures in
    `tests/test_orbit_campaigns.py` -- which assert that the per-interval
    detector finds nothing in them, so they cannot pass on a step -- and it is
    NOT yet proven on live data. What would prove it is a window containing a
    thrust campaign that changes pace, and thirty days of archive did not hold
    one.
    """
    if not thrust.get("underThrust"):
        return []
    out: list[OrbitEvent] = []
    for first, last in _daily_windows(intervals):
        if any(position in already_flagged for position in range(first, last + 1)):
            continue
        members = list(range(first, last + 1))
        baseline = baselines_by_interval[first]["semiMajorAxis"]
        if not baseline.usable or baseline.rate <= 0:
            continue
        total_span = sum(intervals[k].span_days for k in members)
        if total_span <= 0:
            continue
        observed = sum(_observed(intervals[k], "semiMajorAxis") for k in members)
        expected = sum(
            baselines_by_interval[k]["semiMajorAxis"].rate * intervals[k].span_days
            for k in members
        )
        rate = observed / total_span
        if rate < THRUST_EXCESS_RATIO * baseline.rate:
            continue
        excess_metres = observed - expected
        floor = max(natural_floor(intervals[k], "semiMajorAxis") for k in members)
        rate_sigma = math.hypot(
            baseline.within / math.sqrt(len(members)), baseline.between
        )
        sigma = math.hypot(floor * math.sqrt(len(members)), rate_sigma * total_span)
        if sigma <= 0 or excess_metres <= kappa * sigma:
            continue
        persistence = window_persistence(
            intervals, baselines_by_interval, first, last, element="semiMajorAxis"
        )
        if not persistence["persistent"]:
            continue
        interval = intervals[first]
        test = ChannelTest(
            element="semiMajorAxis",
            delta=excess_metres,
            floor_sigma=sigma,
            floor_z=excess_metres / sigma,
            cohort_z=(
                excess_metres / (rate_sigma * total_span) if rate_sigma > 0 else None
            ),
            cohort_count=baseline.samples,
            cohort_screened=baseline.usable,
            tripped=True,
            basis="self-history",
        )
        # The baseline IS the prediction here, and it is a measurement rather
        # than a model: it is what this object has actually been doing, drag
        # and thrust together, over the blocks either side of this window.
        drag = DragPrediction(
            applicable=True,
            reason=(
                "measured from this object's own recent intervals, which are themselves "
                "under thrust"
            ),
            predicted_delta_a_metres=expected,
            sigma_metres=rate_sigma * total_span,
            specific_rate_km_per_day=None,
            cohort_count=baseline.samples,
            bstar=interval.bstar,
        )
        cost = delta_v(interval, drag, [test])
        if cost.implausible is not None:
            continue
        out.append(
            OrbitEvent(
                norad=interval.norad,
                name=interval.name,
                object_type=interval.object_type,
                start_ms=interval.start_ms,
                end_ms=intervals[last].end_ms,
                signature="thrust-excess",
                confidence="candidate",
                delta_v=cost,
                drag=drag,
                tests=[test],
                expectation=score_against_expectation(
                    interval, "thrust-excess", cost, expectations.match(interval, record)
                ),
                regime=interval.regime,
                perigee_altitude_km=interval.perigee_altitude_km,
                apogee_altitude_km=interval.apogee_altitude_km,
                inclination_deg=interval.inclination_deg,
                opaque=opacity_denied(
                    interval.name,
                    record.get("sector"),
                    record.get("mission"),
                    record.get("classificationConfidence"),
                ),
                catalog=record,
            )
        )
    return out


def _residual_floor(element: str, residuals: Sequence[float], perigee_km: float) -> float:
    """F3: only a quantisation-limited inclination floor may measure the tail.

    Linear interpolation at (n-1)*0.95, including small fixture populations.
    Residuals are absolute; a Gaussian's absolute 95th percentile is 1.96 sigma.
    The a/e estimators and the GEO inclination estimator stay bit-identical.
    """
    mad = statistics.median(residuals) * 1.4826 if residuals else 0.0
    if (INCLINATION_FLOOR_TAIL_AWARE and element == "inclination" and residuals
            and noise_floor_for(perigee_km)[2] <= ANGLE_QUANTISATION_DEG):
        ordered = sorted(residuals)
        index = (len(ordered) - 1) * 0.95
        low = int(index)
        high = min(low + 1, len(ordered) - 1)
        q95 = ordered[low] + (ordered[high] - ordered[low]) * (index - low)
        return max(mad, q95 / 1.96)
    return mad


def _decline_tracking_gap(
    tests: Sequence[ChannelTest], intervals: Sequence[Interval], position: int,
) -> tuple[list[ChannelTest], str | None]:
    if DECLINE_AFTER_TRACKING_GAP and position > 0:
        days = (intervals[position].start_ms - intervals[position - 1].end_ms) / 86_400_000
        if days >= MAXIMUM_JOINABLE_GAP_DAYS and any(t.tripped for t in tests):
            reason = f"first element set after a tracking gap of {days:g} days: the fit is on a new arc"
            return [replace(t, tripped=False, reason=reason) if t.tripped else t for t in tests], reason
    return list(tests), None


# Pre-registered at the measured discrimination collapse between 15--30 and
# 30--60 degrees; see docs/orbit-phase2b-corroboration-20260920.md. This is a
# corroboration requirement, not a larger z threshold or a sin(i) floor.
INCLINATION_CORROBORATION_MIN_DEG = 30.0
INCLINATION_UNCORROBORATED_REASON = (
    "inclination-only change unconfirmed by any energy channel; at these inclinations "
    "payloads trip this channel no more often than debris, so an uncorroborated trip "
    "carries no manoeuvre evidence"
)


def _inclination_uncorroborated(interval: Interval, tests: Sequence[ChannelTest]) -> bool:
    """Only persistence-surviving trips may corroborate this interval."""
    tripped = {test.element for test in tests if test.tripped}
    return (interval.inclination_deg >= INCLINATION_CORROBORATION_MIN_DEG
            and "inclination" in tripped
            and not tripped.intersection(("semiMajorAxis", "eccentricity")))


def detect_object_events(
    intervals: Sequence[Interval],
    *,
    kappa: float = DEFAULT_KAPPA,
    expectations: Expectations | None = None,
    record: dict[str, Any] | None = None,
    diagnostics: dict[str, int] | None = None,
    gpu_verifier=None,
    gpu_executor=None,
    gpu_epoch_slices=None,
    _inclination_corroboration: bool = True,
) -> list[OrbitEvent]:
    """Every interval of one object that departed from what that object normally does."""
    if gpu_verifier is not None and gpu_executor is not None:
        raise ValueError("GPU execution and verification are mutually exclusive")
    if len(intervals) < MINIMUM_BASELINE_INTERVALS + 1:
        return []
    expectations = expectations or Expectations.load()
    record = record or {}
    array_options = {} if gpu_epoch_slices is None else {"epoch_slices": gpu_epoch_slices}
    gpu_future = gpu_verifier.submit(intervals, kappa, **array_options) if gpu_verifier else None
    arithmetic_started = time.thread_time() if gpu_verifier else 0.0
    executed = gpu_executor.analyze(intervals, kappa, **array_options) if gpu_executor else None
    if executed is not None:
        baselines_by_interval = executed.baseline_rows()
        gpu_tripped = executed.tripped.any(axis=1)
    else:
        blocks = {element: _blocks_for(intervals, element) for element in ELEMENTS}

        # Pass one: the baseline for every interval, and the residual left over.
        # Nothing is judged yet -- the scale it will be judged against is measured
        # from these residuals, so it cannot be known until they all exist.
        block_index = [int(i.mid_ms // int(BLOCK_DAYS * 86_400_000)) for i in intervals]
        baselines_by_interval = [
            {element: baseline_at(blocks[element], index) for element in ELEMENTS}
            for index in block_index
        ]
        own_floor: dict[str, float] = {}
        median_perigee = statistics.median(i.perigee_altitude_km for i in intervals)
        for element in ELEMENTS:
            residuals = []
            for interval, baselines in zip(intervals, baselines_by_interval):
                observed = _observed(interval, element)
                if observed is None:
                    continue
                residuals.append(abs(observed - baselines[element].rate * interval.span_days))
            # The ordinary estimator remains the median absolute residual.
            # F3 alone lets quantisation-limited inclination see its fitter tail;
            # applying that change to a/e would absorb payload burns into the floor.
            own_floor[element] = _residual_floor(element, residuals, median_perigee)

    gpu_result = None
    if gpu_verifier:
        gpu_verifier.cpu_reference_seconds += time.thread_time() - arithmetic_started
        gpu_result = gpu_verifier.resolve(gpu_future)
        gpu_verifier.compare_baselines(gpu_result, baselines_by_interval, own_floor, intervals[0].norad)

    events: list[OrbitEvent] = []
    # Intervals whose implied cost breaks the 2V ceiling. Counted rather than
    # dropped in silence -- a bound that removes data owes the reader a number.
    implausible_costs = 0
    tracking_gap_drops = 0
    inclination_uncorroborated = 0
    flagged: set[int] = set()
    for position, (interval, baselines) in enumerate(zip(intervals, baselines_by_interval)):
        if executed is not None and not gpu_tripped[position]:
            # Consume device flags directly. Quiet intervals need no ChannelTest
            # allocation; the separate thrust pass still sees every baseline.
            continue
        arithmetic_started = time.thread_time() if gpu_verifier else 0.0
        if executed is not None:
            tests = executed.channel_tests(position, baselines)
        else:
            tests = [
                test
                for element in ELEMENTS
                if (test := _self_channel(
                    interval,
                    element,
                    baselines[element],
                    kappa=(
                        kappa * NODE_CHANNEL_KAPPA_MULTIPLIER
                        if element == "raan"
                        else kappa
                    ),
                    own_floor=own_floor[element],
                )) is not None
            ]
        if gpu_verifier:
            gpu_verifier.cpu_reference_seconds += time.thread_time() - arithmetic_started
            gpu_verifier.compare_channels(gpu_result, tests, position, interval.norad)
        if not any(test.tripped for test in tests):
            continue
        # Persistence belongs to the CHANNEL, not merely to the interval. A
        # semi-major-axis step and a one-fit node excursion can clear their
        # bars together; accepting the interval because the first persisted
        # used to let the unproven node change the signature and the Delta-v.
        # Decline each tripped channel independently, then price and classify
        # only the residuals that actually survived for two observed days.
        persistent_tests = []
        for test in tests:
            if test.tripped:
                arithmetic_started = time.thread_time() if gpu_verifier else 0.0
                if executed is not None:
                    persistent = bool(executed.persistent[position, executed.elements.index(test.element)])
                else:
                    persistent = step_persistence(
                        intervals, baselines_by_interval, position, element=test.element
                    )["persistent"]
                if gpu_verifier:
                    gpu_verifier.cpu_reference_seconds += time.thread_time() - arithmetic_started
                    gpu_verifier.compare_persistence(
                        gpu_result, position, test.element, persistent, interval.norad)
                if not persistent:
                    test = replace(test, tripped=False)
            persistent_tests.append(test)
        tests = persistent_tests
        if _inclination_corroboration:
            if executed is not None:
                uncorroborated = bool(executed.inclination_uncorroborated[position])
            else:
                uncorroborated = _inclination_uncorroborated(interval, tests)
            if gpu_verifier:
                gpu_verifier.compare_corroboration(
                    gpu_result, position, uncorroborated, interval.norad)
            if uncorroborated:
                inclination_uncorroborated += 1
                tests = [replace(test, tripped=False, reason=INCLINATION_UNCORROBORATED_REASON)
                         if test.element == "inclination" and test.tripped else test
                         for test in tests]
        if not any(test.tripped for test in tests):
            continue

        tests, gap_reason = _decline_tracking_gap(tests, intervals, position)
        if gap_reason is not None:
            tracking_gap_drops += 1
            continue

        a_baseline = baselines["semiMajorAxis"]
        # The measured baseline IS the drag prediction here, which is why it is
        # marked applicable: it is an observation of what the atmosphere has
        # been doing to this object, not a model of what it should be doing.
        drag = DragPrediction(
            applicable=a_baseline.usable,
            reason=(
                "measured from this object's own recent intervals"
                if a_baseline.usable
                else "not enough of this object's own history yet"
            ),
            predicted_delta_a_metres=a_baseline.rate * interval.span_days,
            sigma_metres=a_baseline.scale * interval.span_days,
            specific_rate_km_per_day=None,
            cohort_count=a_baseline.samples,
            bstar=interval.bstar,
        )
        cost = delta_v(interval, drag, tests)
        # THE 2V CEILING APPLIES HERE TOO.
        #
        # The cohort lane and the thrust lane both drop an interval whose
        # implied cost exceeds twice the speed at perigee -- a screen set inside
        # the true single-impulse bound of (1 + sqrt 2) * v, for the reasons in
        # orbit_events.THE PHYSICAL SCREEN. This lane did not, and it is the one
        # that judges nearly every published event. The result reached readers:
        # MOHAMMED VI-B led the published object list at 49,317 m/s, because
        # `scan.summaries` sorts by descending Delta-v and so puts the most
        # impossible figures first. A cost a reader could disprove with a pencil
        # must not ship as a measurement, in any lane.
        if cost.implausible is not None:
            implausible_costs += 1
            continue
        signature = classify_change(interval, drag, cost, tests)
        if signature in ("drag-decay", "re-entry-decay"):
            continue
        flagged.add(position)
        events.append(
            OrbitEvent(
                norad=interval.norad,
                name=interval.name,
                object_type=interval.object_type,
                start_ms=interval.start_ms,
                end_ms=interval.end_ms,
                signature=signature,
                # Never stronger than `candidate`, and one step weaker when the
                # object's own history was too thin to screen against.
                confidence="candidate" if a_baseline.usable else "candidate-thin-history",
                delta_v=cost,
                drag=drag,
                tests=tests,
                expectation=score_against_expectation(
                    interval, signature, cost, expectations.match(interval, record)
                ),
                regime=interval.regime,
                perigee_altitude_km=interval.perigee_altitude_km,
                apogee_altitude_km=interval.apogee_altitude_km,
                inclination_deg=interval.inclination_deg,
                opaque=opacity_denied(
                    interval.name,
                    record.get("sector"),
                    record.get("mission"),
                    record.get("classificationConfidence"),
                ),
                catalog=record,
            )
        )
    # The step detector has now had its say. What it cannot see by
    # construction -- a low-thrust object thrusting harder than it usually does
    # -- is a separate pass over the same baselines, and it only runs on an
    # object already shown to be climbing under thrust.
    events.extend(
        thrust_excess_events(
            intervals,
            baselines_by_interval,
            thrust=sustained_thrust(intervals),
            kappa=THRUST_EXCESS_KAPPA,
            expectations=expectations,
            record=record,
            already_flagged=flagged,
        )
    )
    events.sort(key=lambda event: event.start_ms)
    if diagnostics is not None:
        diagnostics["trackingGapDroppedIntervals"] = tracking_gap_drops
        diagnostics["inclinationUncorroborated"] = inclination_uncorroborated
        diagnostics["implausibleCosts"] = implausible_costs
    if inclination_uncorroborated:
        print(f"orbit_campaigns: abstained on {inclination_uncorroborated:,} inclination "
              f"channel trip(s): {INCLINATION_UNCORROBORATED_REASON}", file=sys.stderr)
    if tracking_gap_drops:
        print(f"orbit_campaigns: dropped {tracking_gap_drops:,} interval(s): first element set "
              "after a tracking gap of at least 3 days; the fit is on a new arc", file=sys.stderr)
    if implausible_costs:
        print(
            "orbit_campaigns: dropped {:,} interval(s) whose implied delta-v "
            "exceeded twice the perigee speed -- element pairs that do not "
            "describe one orbit".format(implausible_costs),
            file=sys.stderr,
        )
    return events


# ---------------------------------------------------------------------------
# Cadence, repeats, and what is unusual for this object in particular
# ---------------------------------------------------------------------------
def _covered_days(intervals: Sequence[Interval]) -> float:
    """Days the archive actually watched this object, never the calendar span.

    Sums the spans of joinable intervals rather than subtracting the first
    epoch from the last. The archive contains a real hole between the end of
    the bulk bundles and the start of live capture, and an object observed for
    a year in 2024 and an hour in 2026 has been watched for about a year, not
    for two and a half.
    """
    return sum(interval.span_days for interval in intervals)


def _segments(intervals: Sequence[Interval]) -> list[tuple[int, int]]:
    """Contiguous observation runs, as (start_ms, end_ms). Gaps break a run."""
    runs: list[tuple[int, int]] = []
    start = end = None
    for interval in intervals:
        if start is None:
            start, end = interval.start_ms, interval.end_ms
            continue
        if interval.start_ms - end > MAXIMUM_JOINABLE_GAP_DAYS * 86_400_000:
            runs.append((start, end))
            start, end = interval.start_ms, interval.end_ms
        else:
            end = interval.end_ms
    if start is not None:
        runs.append((start, end))
    return runs


def cadence_of(events: Sequence[OrbitEvent], intervals: Sequence[Interval]) -> dict[str, Any] | None:
    """How often this object corrects, and how regular that is.

    Regularity is `MAD / median` of the spacing — dimensionless, robust, and
    zero for a perfectly regular cadence. It is reported alongside the spacings
    rather than instead of them, because a single number that says "regular"
    without showing the intervals is exactly the kind of naked verdict this
    project has been burned by before.

    Spacings that cross an archive gap are dropped, not averaged in.
    """
    propulsive = [e for e in events if e.signature not in NON_PROPULSIVE_SIGNATURES]
    if len(propulsive) < MINIMUM_EVENTS_FOR_CADENCE:
        return None
    runs = _segments(intervals)
    times = sorted(event.start_ms for event in propulsive)
    spacings: list[float] = []
    for previous, current in zip(times, times[1:]):
        inside = any(start <= previous and current <= end for start, end in runs)
        if not inside:
            continue
        spacings.append((current - previous) / 86_400_000.0)
    if len(spacings) < 2:
        return None
    median = statistics.median(spacings)
    mad = statistics.median([abs(s - median) for s in spacings]) * 1.4826
    covered = _covered_days(intervals)
    return {
        "corrections": len(propulsive),
        "spacingsUsed": len(spacings),
        "medianDaysBetween": round(median, 3),
        "spacingScaleDays": round(mad, 3),
        "regularity": round(mad / median, 3) if median > 0 else None,
        "correctionsPerYear": round(len(propulsive) * 365.25 / covered, 2) if covered > 0 else None,
        "observedDays": round(covered, 3),
        "note": (
            "Spacings that would have crossed a gap in the archive are dropped rather than "
            "averaged in: an archive gap is not a period of inactivity."
        ),
    }


def _same_cost(a: float, b: float) -> bool:
    if max(abs(a), abs(b)) < REPEAT_ABSOLUTE_TOLERANCE_MPS:
        return True
    reference = max(abs(a), abs(b))
    return abs(a - b) <= REPEAT_RELATIVE_TOLERANCE * reference


def repeat_clusters(events: Sequence[OrbitEvent]) -> list[dict[str, Any]]:
    """Groups of corrections that are the same correction made again.

    Same signature, and a cost inside a tolerance band of the group's running
    median. A band rather than a bucket, deliberately: rounding costs into
    buckets puts a boundary exactly where a station-keeping population sits and
    splits one real cadence into two apparent ones.
    """
    propulsive = sorted(
        (e for e in events if e.signature not in NON_PROPULSIVE_SIGNATURES),
        key=lambda e: e.start_ms,
    )
    groups: list[dict[str, Any]] = []
    for event in propulsive:
        cost = event.delta_v.total
        for group in groups:
            if group["signature"] != event.signature:
                continue
            if _same_cost(statistics.median(group["costs"]), cost):
                group["costs"].append(cost)
                group["times"].append(event.start_ms)
                break
        else:
            groups.append(
                {
                    "signature": event.signature,
                    "costs": [cost],
                    "times": [event.start_ms],
                }
            )

    out: list[dict[str, Any]] = []
    for group in groups:
        if len(group["costs"]) < 2:
            continue
        spacings = [
            (b - a) / 86_400_000.0 for a, b in zip(group["times"], group["times"][1:])
        ]
        median_spacing = statistics.median(spacings) if spacings else None
        spacing_scale = (
            statistics.median([abs(s - median_spacing) for s in spacings]) * 1.4826
            if spacings
            else None
        )
        out.append(
            {
                "signature": group["signature"],
                "count": len(group["costs"]),
                "medianDeltaVMetresPerSecond": round(statistics.median(group["costs"]), 4),
                "deltaVSpreadMetresPerSecond": round(
                    statistics.median(
                        [abs(c - statistics.median(group["costs"])) for c in group["costs"]]
                    )
                    * 1.4826,
                    4,
                ),
                "medianDaysBetween": None if median_spacing is None else round(median_spacing, 3),
                "spacingScaleDays": None if spacing_scale is None else round(spacing_scale, 3),
                "firstAt": _iso(group["times"][0]),
                "lastAt": _iso(group["times"][-1]),
                "totalDeltaVMetresPerSecond": round(sum(group["costs"]), 4),
            }
        )
    out.sort(key=lambda group: -group["count"])
    return out


def out_of_family_for_itself(
    events: Sequence[OrbitEvent], clusters: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Corrections this object made that do not look like the ones it usually makes.

    Only computed once the object HAS a usual correction: an object with a
    single detected event has no established pattern, and calling that event
    anomalous would be calling every first observation anomalous.
    """
    if not clusters:
        return []
    established = max(clusters, key=lambda cluster: cluster["count"])
    if established["count"] < MINIMUM_EVENTS_FOR_CADENCE:
        return []
    reference = established["medianDeltaVMetresPerSecond"]
    unusual: list[dict[str, Any]] = []
    for event in events:
        if event.signature in NON_PROPULSIVE_SIGNATURES:
            continue
        cost = event.delta_v.total
        if event.signature == established["signature"] and _same_cost(reference, cost):
            continue
        unusual.append(
            {
                "at": _iso(event.start_ms),
                "signature": event.signature,
                "deltaVMetresPerSecond": round(cost, 4),
                "why": (
                    "a different kind of change from this object's usual one"
                    if event.signature != established["signature"]
                    else "the same kind of change, at a cost outside its usual band"
                ),
                "usualSignature": established["signature"],
                "usualDeltaVMetresPerSecond": reference,
                "usualCount": established["count"],
            }
        )
    return unusual


def decay_trend(intervals: Sequence[Interval]) -> dict[str, Any]:
    """Robust rate of change of semi-major axis, and what it implies.

    The median of per-day rates rather than a fitted slope, because a single
    manoeuvre inside the series would drag a least-squares slope by an
    arbitrary amount while leaving a median almost untouched.

    A remaining-life figure is only offered where a linear extrapolation is
    defensible at all: decay accelerates as an object falls, so the number is
    published as an **upper bound on time remaining**, and only below 600 km
    where drag is unambiguously the dominant term.
    """
    if not intervals:
        return {"metresPerDay": None, "note": "no usable intervals"}
    rates = [i.delta_a_km * 1000.0 / i.span_days for i in intervals if i.span_days > 0]
    if not rates:
        return {"metresPerDay": None, "note": "no usable intervals"}
    median = statistics.median(rates)
    latest = intervals[-1]
    result: dict[str, Any] = {
        "metresPerDay": round(median, 2),
        "perigeeAltitudeKm": round(latest.perigee_altitude_km, 1),
        "decaying": median < 0 and latest.perigee_altitude_km < 1400.0,
        "note": (
            "Median of this object's own per-day rates. A median rather than a fitted slope, so "
            "a manoeuvre inside the series cannot tilt it."
        ),
    }
    if median < 0 and latest.perigee_altitude_km < 600.0:
        altitude_m = max(latest.perigee_altitude_km - 120.0, 0.0) * 1000.0
        result["upperBoundDaysToReentry"] = round(altitude_m / abs(median), 1)
        result["reentryNote"] = (
            "An UPPER bound: decay accelerates as an object falls into denser air, so the real "
            "figure is shorter. Extrapolated to a 120 km perigee at today's rate, and only "
            "offered below 600 km where drag is unambiguously the dominant term."
        )
    return result


def summarise_object(
    intervals: Sequence[Interval],
    events: Sequence[OrbitEvent],
    *,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One publishable row: the columns the browser is asked to sort on."""
    record = record or {}
    first, last = intervals[0], intervals[-1]
    propulsive = [e for e in events if e.signature not in NON_PROPULSIVE_SIGNATURES]
    clusters = repeat_clusters(events)
    covered = _covered_days(intervals)
    spend = sum(e.delta_v.total for e in propulsive)
    runs = _segments(intervals)
    return {
        "norad": first.norad,
        "name": first.name,
        "objectType": first.object_type,
        "regime": last.regime,
        "perigeeAltitudeKm": round(last.perigee_altitude_km, 1),
        "apogeeAltitudeKm": round(last.apogee_altitude_km, 1),
        "inclinationDeg": round(last.inclination_deg, 3),
        "sunSynchronous": sun_synchronous(
            last.a_start_km, last.eccentricity, last.inclination_deg
        ),
        "mission": record.get("mission"),
        "sector": record.get("sector"),
        "constellation": record.get("constellation"),
        "intervals": len(intervals),
        "observedDays": round(covered, 3),
        "firstSeenAt": _iso(first.start_ms),
        "lastSeenAt": _iso(last.end_ms),
        "observationRuns": [
            {"fromAt": _iso(start), "toAt": _iso(end), "days": round((end - start) / 86_400_000.0, 2)}
            for start, end in runs
        ],
        "events": len(propulsive),
        "deltaVMetresPerSecond": round(spend, 4),
        "deltaVPerYearMetresPerSecond": (
            round(spend * 365.25 / covered, 3) if covered > 0 else None
        ),
        "cadence": cadence_of(events, intervals),
        "repeatClusters": clusters[:6],
        "unusualForItself": out_of_family_for_itself(events, clusters)[:6],
        "outOfFamilyForClass": any(
            e.expectation.get("verdict")
            in ("unusual-for-class", "impossible-for-class", "larger-than-typical")
            for e in propulsive
        ),
        "decay": decay_trend(intervals),
        # A fact about the object rather than an event on it, so it is a column
        # and not a row: "this thing is being pushed, and here is how fast" is
        # true of every interval at once and would be nonsense repeated on each.
        "sustainedThrust": sustained_thrust(intervals),
        "purposeLanguagePermitted": not opacity_denied(
            first.name,
            record.get("sector"),
            record.get("mission"),
            record.get("classificationConfidence"),
        ),
    }


# ---------------------------------------------------------------------------
# The whole-archive pass
# ---------------------------------------------------------------------------
# Predeclared F1 table. Match noise_floor_for's inclusive upper edges exactly.
CONTROL_ERAS = ("pre-2013", "2013-2020", "2021+")
CONTROL_BANDS = ("<500", "500-800", "800-1500", "1500-30000", "GEO+")
MINIMUM_STRATUM_PASSIVE_INTERVALS = 200_000


def control_stratum(start_ms: int | None, perigee_km: float | None) -> dict[str, str] | str:
    if start_ms is None or perigee_km is None or not math.isfinite(perigee_km):
        return "not calibrated: event epoch or perigee is not measured"
    try:
        year = dt.datetime.fromtimestamp(start_ms / 1000, dt.timezone.utc).year
    except (ValueError, OverflowError, OSError):
        return "not calibrated: event epoch is not usable"
    era = CONTROL_ERAS[0 if year < 2013 else 1 if year < 2021 else 2]
    band = next(name for name, row in zip(CONTROL_BANDS, orbit_history.CATALOGUE_NOISE_FLOOR)
                if perigee_km <= row[0])
    return {"era": era, "band": band}


def _perigee_band(km: float | None) -> str:
    """Coarse altitude bands. Drag, fit quality and regime all change with
    perigee, so a floor concentrated in one band is a different problem from one
    spread evenly."""
    if km is None:
        return "unknown"
    for edge, label in ((300, "<300 km"), (500, "300-500 km"), (800, "500-800 km"),
                        (1200, "800-1200 km"), (2000, "1200-2000 km")):
        if km < edge:
            return label
    return ">2000 km"


def _ranked_breakdown(raw: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Publish each dimension largest-first, with a share, so the top
    contributors are readable without post-processing."""
    out: dict[str, Any] = {}
    for dimension, counts in raw.items():
        total = sum(counts.values()) or 1
        out[dimension] = [
            {"value": value, "count": count, "share": round(count / total, 4)}
            for value, count in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
    return out


def _tally_breakdown(into: dict[str, dict[str, int]],
                     events: Sequence[OrbitEvent]) -> None:
    """Count flagged events by the dimensions Phase 2 will need to act on.

    `channel` is the interesting one: an event can trip more than one element,
    so each tripped element is counted AND the exact combination is counted
    separately. "inclination alone" and "semi-major axis plus inclination" are
    different findings -- the first smells like a conditioning artefact, the
    second like a real burn.
    """
    for event in events:
        def bump(dimension: str, value: str) -> None:
            bucket = into.setdefault(dimension, {})
            bucket[value] = bucket.get(value, 0) + 1

        bump("signature", event.signature or "unknown")
        bump("regime", event.regime or "unknown")
        bump("perigeeBand", _perigee_band(event.perigee_altitude_km))
        bump("confidence", event.confidence or "unknown")

        tripped = sorted(
            test.element for test in (event.tests or []) if getattr(test, "tripped", False)
        )
        for element in tripped:
            bump("channel", element)
        bump("channelCombination", "+".join(tripped) if tripped else "none")


@dataclass
class ArchivePass:
    events: list[OrbitEvent] = field(default_factory=list)
    summaries: list[dict[str, Any]] = field(default_factory=list)
    # Control counts stay scalar; compact per-object day terms below preserve
    # float addition order. Passive histories and intervals are never retained.
    passive_intervals: int = 0
    passive_flags: int = 0
    passive_objects: int = 0
    passive_object_days: float = 0.0
    passive_flagged_objects: int = 0
    payload_intervals: int = 0
    payload_flags: int = 0
    payload_objects: int = 0
    payload_object_days: float = 0.0
    objects_scanned: int = 0
    objects_with_baseline: int = 0

    strata: dict[tuple[str, str], ArchivePass] = field(default_factory=dict)
    tracking_gap_drops: int = 0
    implausible_costs: int = 0
    catalogue_geo_north_south_events: int | None = None
    # An old checkpoint finishes its entire sweep under its original policy.
    # Otherwise resumed counts would silently mix two detectors. New sweeps
    # always enable corroboration; this is checkpoint provenance, not a knob.
    inclination_corroboration: bool = True
    inclination_uncorroborated: int = 0

    # PHASE 0: what the two rates are MADE of.
    #
    # A rate tells you how often the detector fires and nothing about why. Both
    # remaining ways to improve separation -- lowering the floor or raising the
    # payload catch -- need to know which channels, signatures and regimes carry
    # the flags. Counting is free here: `note()` already receives the flagged
    # events themselves.
    #
    # Shape: {dimension: {value: count}}, plain dicts so it pickles and
    # serialises without ceremony.
    passive_breakdown: dict[str, dict[str, int]] = field(default_factory=dict)
    payload_breakdown: dict[str, dict[str, int]] = field(default_factory=dict)

    # Eight bytes per object/type/occupied stratum, never per element set.
    # Replaying these additions in NORAD order preserves the serial float sum:
    # adding rounded shard totals instead would change the last bits. Older
    # checkpoints seed a single prefix term; their completed work stays intact.
    _day_terms: dict[str, array] = field(default_factory=dict, repr=False)

    def __setstate__(self, state: dict) -> None:
        """Load a checkpoint written before the breakdown fields existed.

        The sweep pickles this object and resumes from it, and pickle restores
        __dict__ directly -- dataclass defaults do NOT apply. Without this, new
        code meeting an old checkpoint raises AttributeError on first access,
        the loader discards the checkpoint, and a sweep that had already walked
        68,000 objects starts again from zero. Backfilling is four lines and
        saves a working day.
        """
        self.__dict__.update(state)
        for name in ("passive_breakdown", "payload_breakdown", "_day_terms"):
            if name not in self.__dict__:
                setattr(self, name, {})
        for name, default in (("tracking_gap_drops", 0),
                              ("implausible_costs", 0),
                              ("catalogue_geo_north_south_events", None),
                              ("inclination_corroboration", False),
                              ("inclination_uncorroborated", 0)):
            if name not in self.__dict__:
                setattr(self, name, default)

    def _add_days(self, name: str, days: float) -> None:
        terms = self._day_terms.setdefault(name, array("d"))
        if not terms and getattr(self, name):
            terms.append(getattr(self, name))  # checkpoint predating the terms
        terms.append(days)
        setattr(self, name, getattr(self, name) + days)

    def merge(self, other: ArchivePass) -> None:
        """Append a disjoint, later NORAD range, including its nested controls.

        An object must belong wholly to one partial. Call in archive order;
        summaries are sorted only once the entire sweep has finished.
        """
        if self.inclination_corroboration != other.inclination_corroboration:
            if self.objects_scanned or self.passive_intervals or self.payload_intervals:
                raise ValueError("cannot merge sweeps with different inclination corroboration policies")
            self.inclination_corroboration = other.inclination_corroboration
        for name in (
            "passive_intervals", "passive_flags", "passive_objects",
            "passive_flagged_objects", "payload_intervals", "payload_flags",
            "payload_objects", "objects_scanned", "objects_with_baseline",
            "tracking_gap_drops", "implausible_costs",
            "inclination_uncorroborated",
        ):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        for name in ("passive_object_days", "payload_object_days"):
            terms = other._day_terms.get(name)
            if terms:
                for days in terms:
                    self._add_days(name, days)
            elif getattr(other, name):
                self._add_days(name, getattr(other, name))
        self.events.extend(other.events)
        self.summaries.extend(other.summaries)
        for key, partial in other.strata.items():
            self.strata.setdefault(key, ArchivePass(
                inclination_corroboration=self.inclination_corroboration)).merge(partial)
        for name in ("passive_breakdown", "payload_breakdown"):
            into = getattr(self, name)
            for dimension, buckets in getattr(other, name).items():
                counts = into.setdefault(dimension, {})
                for value, count in buckets.items():
                    counts[value] = counts.get(value, 0) + count
        if other.catalogue_geo_north_south_events is not None:
            self.catalogue_geo_north_south_events = (
                (self.catalogue_geo_north_south_events or 0)
                + other.catalogue_geo_north_south_events
            )

    def note(self, object_type: str, intervals: int, flags: int, days: float,
             *, observed: Sequence[Interval] | None = None,
             propulsive: Sequence[OrbitEvent] = ()) -> None:
        passive = (object_type or "").upper() in PASSIVE_TYPES
        if passive or (object_type or "").upper() == "PAYLOAD":
            _tally_breakdown(
                self.passive_breakdown if passive else self.payload_breakdown,
                propulsive,
            )
        if passive:
            self.passive_intervals += intervals
            self.passive_flags += flags
            self.passive_objects += 1
            self._add_days("passive_object_days", days)
            if flags:
                self.passive_flagged_objects += 1
        elif (object_type or "").upper() == "PAYLOAD":
            self.payload_intervals += intervals
            self.payload_flags += flags
            self.payload_objects += 1
            self._add_days("payload_object_days", days)

        # Per-object temporary groups; every interval and flag has the SAME key
        # rule as the event card. An object spanning eras/bands contributes its
        # object count once to each occupied stratum, not once per interval.
        if observed is not None:
            groups: dict[tuple[str, str], list[float]] = {}
            for interval in observed:
                key = control_stratum(interval.start_ms, interval.perigee_altitude_km)
                if isinstance(key, dict):
                    counts = groups.setdefault((key["era"], key["band"]), [0, 0, 0.0])
                    counts[0] += 1
                    counts[2] += interval.span_days
            for event in propulsive:
                key = control_stratum(event.start_ms, event.perigee_altitude_km)
                if isinstance(key, dict):
                    counts = groups.setdefault((key["era"], key["band"]), [0, 0, 0.0])
                    counts[1] += 1
            for key, (count, flagged, covered) in groups.items():
                self.strata.setdefault(key, ArchivePass(
                    inclination_corroboration=self.inclination_corroboration)).note(
                    object_type, int(count), int(flagged), covered)


def scan_archive(
    connection: sqlite3.Connection,
    *,
    kappa: float = DEFAULT_KAPPA,
    since_ms: int | None = None,
    only: Sequence[int] | None = None,
    catalog: dict[int, dict[str, Any]] | None = None,
    keep_summaries_for: set[int] | None = None,
    progress_every: int = 0,
) -> ArchivePass:
    """One streaming pass over the whole archive, bounded in memory.

    `keep_summaries_for` limits the published per-object rows to the objects the
    browser can actually show — the teaching catalogue — while the control
    counters still accumulate over **every** object, including the debris and
    spent stages nobody displays. That asymmetry is the point: the negative
    control is only worth having if it is measured over the whole passive
    population rather than over the handful of it that made an interesting row.
    """
    return sweep_archive(
        connection,
        kappa=kappa,
        since_ms=since_ms,
        only=only,
        catalog=catalog,
        keep_summaries_for=keep_summaries_for,
        progress_every=progress_every,
    ).passed


@dataclass
class SweepProgress:
    """What one slice of the archive sweep achieved, and where to pick it up.

    `resume_after` is the last object this slice FINISHED, or `None` when the
    slice reached the end of the archive. `None` is the only thing that means
    "the pass is whole"; every consumer of `passed` that publishes anything must
    check it, because a partial pass has partial controls and partial summaries
    and would publish a false-alarm rate measured over a fraction of the
    population.
    """

    passed: ArchivePass
    resume_after: int | None
    objects_this_run: int
    seconds: float

    @property
    def complete(self) -> bool:
        return self.resume_after is None


def sweep_worker_count() -> int:
    """Leave four logical CPUs for the other sites, with an operator override."""
    configured = os.environ.get("SPACE_EXPLORER_ORBIT_SWEEP_WORKERS")
    count = int(configured) if configured is not None else min(max(1, (os.cpu_count() or 1) - 4), 12)
    if count < 1:
        raise ValueError("orbit sweep workers must be positive")
    return count


SWEEP_SHARD_OBJECTS = 8
SWEEP_PAGE_ROWS = 8192
_worker_archive: sqlite3.Connection | None = None
_worker_columnar_store = None


def _start_sweep_worker(path: str, flags: dict[str, bool]) -> None:
    global _worker_archive, _worker_columnar_store
    # The parent handles TERM by draining bounded in-flight ranges, then hands
    # its caller a checkpointable prefix. Do not kill children mid-object.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    # Acceptance runs can set these switches in-process. A spawned interpreter
    # otherwise silently reverts to the source defaults, measuring another detector.
    for name in detector_flags():
        globals()[name] = flags[name]
    _worker_archive = open_archive_for_reading(Path(path))
    _worker_columnar_store = None


def _sweep_range(norads: list[int], options: dict[str, Any]) -> ArchivePass:
    global _worker_columnar_store
    assert _worker_archive is not None
    options = dict(options)
    root = options.pop("_columnar_root", None)
    if root is not None:
        from pipeline.orbit_columnar import open_store, require_scope
        if _worker_columnar_store is None:
            import atexit
            path = next(r[2] for r in _worker_archive.execute("PRAGMA database_list") if r[1] == "main")
            _worker_columnar_store = open_store(root, archive=path)
            atexit.register(_worker_columnar_store.close)
        # One map per worker lifetime, not an O(catalogue) parse/map for every
        # eight-object job. The parent also guards the entire pool's lifetime.
        store = _worker_columnar_store
        require_scope(store, norads)
        store.assert_current()
        result = _sweep_archive_serial(
            _worker_archive, only=norads, **options, _sort_summaries=False,
            _columnar_store=store).passed
        store.assert_current()
        return result
    return _sweep_archive_serial(
        _worker_archive, only=norads, **options, _sort_summaries=False,
        _page_rows=SWEEP_PAGE_ROWS,
    ).passed


def _sweep_ranges(connection: sqlite3.Connection, only: Sequence[int] | None,
                  start_after: int | None) -> Iterator[list[int]]:
    """Small consecutive NORAD ranges, without a DISTINCT scan of all rows.

    Each seek jumps over one object's history in the primary-key b-tree. Using
    element_set also includes histories whose object metadata is absent.
    """
    batch: list[int] = []
    if only:
        members = (n for n in sorted(set(only)) if start_after is None or n > start_after)
    else:
        def seek_members():
            cursor = -1 if start_after is None else start_after
            while True:
                row = connection.execute(
                    "SELECT norad FROM element_set WHERE norad > ? ORDER BY norad LIMIT 1",
                    (cursor,),
                ).fetchone()
                if row is None:
                    return
                cursor = row[0]
                yield cursor
        members = seek_members()
    for norad in members:
        batch.append(norad)
        if len(batch) == SWEEP_SHARD_OBJECTS:
            yield batch
            batch = []
    if batch:
        yield batch


def sweep_archive(
    connection: sqlite3.Connection, *, kappa: float = DEFAULT_KAPPA,
    since_ms: int | None = None, only: Sequence[int] | None = None,
    catalog: dict[int, dict[str, Any]] | None = None,
    keep_summaries_for: set[int] | None = None, progress_every: int = 0,
    start_after: int | None = None, deadline: float | None = None,
    into: ArchivePass | None = None, workers: int | None = None,
    gpu_devices: Sequence[int] | None = None,
    gpu_verify_devices: Sequence[int] | None = None, gpu_ceiling_mib: int = 1335,
    columnar_root=None, columnar_seconds: float = 60.0,
) -> SweepProgress:
    """Prefer a certified SSD store; fallback once, before committing slice results.

    No new ArchivePass fields or checkpoint identity. Failed columnar work is
    isolated from `into`, including failures on context exit or in pool workers.
    Maintenance gets at most 5% of the remaining slice and 60 seconds by default.
    Pass columnar_root=False to force the reference SQLite path.
    """
    options = dict(kappa=kappa, since_ms=since_ms, only=only, catalog=catalog,
                   keep_summaries_for=keep_summaries_for, progress_every=progress_every,
                   start_after=start_after, deadline=deadline, into=into, workers=workers,
                   gpu_devices=gpu_devices, gpu_verify_devices=gpu_verify_devices,
                   gpu_ceiling_mib=gpu_ceiling_mib,
                   _inclination_corroboration=(into.inclination_corroboration
                                               if into is not None else True))
    if gpu_devices is not None and gpu_verify_devices is not None:
        raise ValueError("GPU execution and verification are mutually exclusive")
    if columnar_root is False:
        return _sweep_archive_dispatch(connection, **options)
    try:
        from pipeline import orbit_columnar as col
    except ImportError as error:
        print(f"SWEEP COLUMNAR FALLBACK: {error}; using stream_object_rows", file=sys.stderr, flush=True)
        return _sweep_archive_dispatch(connection, **options)
    root = col.DEFAULT_ROOT if columnar_root is None else Path(columnar_root)
    path = next((r[2] for r in connection.execute("PRAGMA database_list") if r[1] == "main"), "")
    # A separate source connection cannot see uncommitted or TEMP shadow inputs.
    shadow = connection.execute(
        "SELECT 1 FROM sqlite_temp_master WHERE name IN ('element_set','object') LIMIT 1").fetchone()
    reason = None
    if not path or connection.in_transaction or shadow:
        reason = "connection-local inputs are not certified"
    elif columnar_root is None and Path(path).resolve() != archive_db_path().resolve():
        reason = "nondefault archive requires an explicit columnar_root"
    if reason is not None:
        print(f"SWEEP COLUMNAR FALLBACK: {reason}; using stream_object_rows", file=sys.stderr, flush=True)
        return _sweep_archive_dispatch(connection, **options)
    started, cpu_started = time.time(), time.process_time()
    try:
        seconds = max(0.0, columnar_seconds)
        if deadline is not None:
            seconds = min(seconds, max(0.0, deadline - time.time()) * 0.05)
        receipt = col.maintain(root, archive=path, only=only, seconds=seconds)
        print("SWEEP COLUMNAR MAINTENANCE " + json.dumps(receipt, sort_keys=True),
              file=sys.stderr, flush=True)
        with col.open_store(root, archive=path) as store:
            col.require_scope(store, only)
            progress = _sweep_archive_dispatch(connection, **dict(options, into=None), _columnar_store=store)
    except (col.IntegrityError, col.BudgetExceeded, OSError, ValueError, KeyError,
            TypeError, sqlite3.DatabaseError) as error:
        reason = " ".join(str(error).splitlines())
        print(f"SWEEP COLUMNAR FALLBACK: {reason}; discarded attempt cost "
              f"{time.time() - started:.3f}s wall/{time.process_time() - cpu_started:.3f}s CPU; "
              "using stream_object_rows", file=sys.stderr, flush=True)
        progress = _sweep_archive_dispatch(connection, **options)
    else:
        # Keep the merge OUTSIDE the retry handler: errors in checkpoint code
        # must never trigger a replay into an already modified accumulator.
        if into is not None:
            into.merge(progress.passed)
            progress.passed = into
            if progress.complete:
                into.summaries.sort(key=lambda row: -row["deltaVMetresPerSecond"])
    progress.seconds = time.time() - started
    return progress


def _sweep_archive_dispatch(
    connection: sqlite3.Connection,
    *,
    kappa: float = DEFAULT_KAPPA,
    since_ms: int | None = None,
    only: Sequence[int] | None = None,
    catalog: dict[int, dict[str, Any]] | None = None,
    keep_summaries_for: set[int] | None = None,
    progress_every: int = 0,
    start_after: int | None = None,
    deadline: float | None = None,
    into: ArchivePass | None = None,
    workers: int | None = None,
    gpu_devices: Sequence[int] | None = None,
    gpu_verify_devices: Sequence[int] | None = None,
    gpu_ceiling_mib: int = 1335,
    _columnar_store=None,
    _inclination_corroboration: bool = True,
) -> SweepProgress:
    """Sweep disjoint NORAD ranges with bounded process and result queues.

    Only the parent owns the accumulated checkpoint. Spawned workers open their
    own read-only connection and retain at most eight objects' compact results
    plus one object's analysis and an 8192-row page. At most `workers` ranges
    are outstanding, even when the first range is slow. Merge in NORAD order,
    never completion order, so the existing single resume cursor remains valid.

    On deadline/TERM stop submitting and drain the bounded outstanding ranges.
    Budgeting is cooperative: a slice may overrun by the slowest outstanding
    range plus checkpoint I/O. An already spent budget still advances one object.
    In-memory/uncommitted connections use the serial path because another
    connection cannot see those inputs. The tail checkpoint contract is unchanged.
    """
    workers = sweep_worker_count() if workers is None else workers
    if workers < 1:
        raise ValueError("orbit sweep workers must be positive")
    options = dict(kappa=kappa, since_ms=since_ms, catalog=catalog,
                   keep_summaries_for=keep_summaries_for,
                   _inclination_corroboration=(into.inclination_corroboration
                                               if into is not None else _inclination_corroboration))
    if gpu_devices is not None and gpu_verify_devices is not None:
        raise ValueError("GPU execution and verification are mutually exclusive")
    if gpu_devices is not None:
        # One reader and one object in flight; no CUDA contexts in CPU workers.
        from pipeline.orbit_sweep_gpu import Execution
        with Execution(tuple(gpu_devices), gpu_ceiling_mib) as executor:
            try:
                return _sweep_archive_serial(
                    connection, **options, only=only, progress_every=progress_every,
                    start_after=start_after, deadline=deadline, into=into, gpu_executor=executor,
                    _columnar_store=_columnar_store)
            finally:
                print("SWEEP GPU EXECUTION " + json.dumps(executor.report(), sort_keys=True),
                      file=sys.stderr, flush=True)
    if gpu_verify_devices is not None:
        # CPU remains authoritative; do not spawn a CUDA context per CPU worker.
        from pipeline.orbit_sweep_gpu import Verification
        with Verification(tuple(gpu_verify_devices), gpu_ceiling_mib) as verifier:
            try:
                return _sweep_archive_serial(
                    connection, **options, only=only, progress_every=progress_every,
                    start_after=start_after, deadline=deadline, into=into, gpu_verifier=verifier,
                    _columnar_store=_columnar_store)
            finally:
                print("SWEEP GPU VERIFICATION " + json.dumps(verifier.report(), sort_keys=True),
                      file=sys.stderr, flush=True)
    path = next((row[2] for row in connection.execute("PRAGMA database_list")
                 if row[1] == "main"), "")
    if (workers == 1 or not path or connection.in_transaction
            or (deadline is not None and time.time() >= deadline)):
        return _sweep_archive_serial(
            connection, **options, only=only, progress_every=progress_every,
            start_after=start_after, deadline=deadline, into=into,
            _columnar_store=_columnar_store,
        )

    started = time.time()
    if _columnar_store is not None:
        options["_columnar_root"] = str(_columnar_store.root)
    result = into if into is not None else ArchivePass(
        inclination_corroboration=options["_inclination_corroboration"])
    if catalog and result.catalogue_geo_north_south_events is None:
        result.catalogue_geo_north_south_events = 0
    ranges = iter(_sweep_ranges(connection, only, start_after))
    pending = deque()
    exhausted = False
    stopped = False
    cursor = start_after
    objects = 0

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    previous_handler = signal.signal(signal.SIGTERM, stop)
    try:
        # Spawn deliberately: fork would inherit the multi-GB accumulated pass
        # and its SQLite handle, and copy-on-write would not bound that cost.
        with ProcessPoolExecutor(max_workers=workers,
                                 mp_context=multiprocessing.get_context("spawn"),
                                 initializer=_start_sweep_worker,
                                 initargs=(path, detector_flags())) as pool:
            def submit():
                nonlocal exhausted
                batch = next(ranges, None)
                if batch is None:
                    exhausted = True
                    return
                local = dict(options)
                local["catalog"] = {n: catalog[n] for n in batch if catalog and n in catalog}
                if keep_summaries_for is not None:
                    local["keep_summaries_for"] = keep_summaries_for.intersection(batch)
                pending.append((batch[-1], pool.submit(_sweep_range, batch, local)))

            for _ in range(workers):
                submit()
                if exhausted:
                    break
            while pending:
                last, future = pending.popleft()
                partial = future.result()
                previous_count = result.objects_scanned
                result.merge(partial)
                objects += partial.objects_scanned
                cursor = last
                del partial, future
                if progress_every and result.objects_scanned // progress_every > previous_count // progress_every:
                    print(f"  {result.objects_scanned} objects, {time.time() - started:.0f}s, "
                          f"{len(result.events)} events", flush=True)
                if deadline is not None and time.time() >= deadline:
                    stopped = True
                if not stopped and not exhausted:
                    submit()
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    if not exhausted or (stopped and cursor is not None):
        return SweepProgress(result, cursor, objects, time.time() - started)
    result.summaries.sort(key=lambda row: -row["deltaVMetresPerSecond"])
    return SweepProgress(result, None, objects, time.time() - started)


def _sweep_archive_serial(
    connection: sqlite3.Connection,
    *,
    kappa: float = DEFAULT_KAPPA,
    since_ms: int | None = None,
    only: Sequence[int] | None = None,
    catalog: dict[int, dict[str, Any]] | None = None,
    keep_summaries_for: set[int] | None = None,
    progress_every: int = 0,
    start_after: int | None = None,
    deadline: float | None = None,
    into: ArchivePass | None = None,
    _sort_summaries: bool = True,
    _page_rows: int | None = None,
    gpu_verifier=None,
    gpu_executor=None,
    _columnar_store=None,
    _inclination_corroboration: bool = True,
) -> SweepProgress:
    """`scan_archive`, but stoppable on a wall-clock deadline and resumable.

    WHY THE PASS HAD TO BECOME RESUMABLE
    ------------------------------------
    Historical 9p measurements below explain why resumption exists. On SSD/WAL
    (2026-09-11), a bounded 400-object profile measured 129,357 rows/s reading
    and 81% of time in analysis; the parallel sweep addresses that CPU bottleneck.

    `scan_archive` is O(the whole archive) and the archive grew. It was written
    against 55.2 M element sets; the 2004-2025 back-fill has taken it to
    181.3 M, and `/mnt/d` is WSL drvfs 9p, where SQLite's 4 KiB page reads cost
    about 8.7 ms each. Measured cold on the live archive, 2026-08-18:
    **7,557 rows/s, so one whole pass is 6 h 40 m of reading.**

    `orbit-release.service` allows 3,600 s. So from 2026-08-13 every single
    nightly run was SIGTERMed at the ceiling having done one to two hours of
    work, and threw all of it away; the published orbit artifacts stood still
    from 2026-08-08 to 2026-08-18 while the unit reported a fresh failure every
    morning. Six consecutive runs, no progress, because the pass had no way to
    keep what it had already computed.

    A deadline plus a cursor fixes exactly that. Each run absorbs objects until
    its budget is spent, hands back the accumulated `ArchivePass` and the norad
    it stopped after, and the next run continues from there -- `into` is the
    previous run's pass, `start_after` its cursor. Nothing is published until a
    slice returns `complete`.

    THE SKEW THIS ACCEPTS, SAID OUT LOUD
    ------------------------------------
    Objects are therefore read at different times within one sweep, so a sweep
    is a mosaic rather than an instant. That is not new: `paged_element_sets`
    already ends its transaction every 250,000 rows, so rows inserted behind the
    cursor were always missed and rows inserted ahead of it were always
    included. Resuming widens that window from minutes to hours. It cannot lose
    an element set -- a row present for the whole sweep is returned exactly
    once, because the primary key of a row never changes -- and anything that
    arrives behind the cursor is in the next sweep. For a twenty-two year
    manoeuvre archive that is the right trade; for the hourly data it would not
    be, which is why the hourly data does not come through here.
    """
    catalog = catalog or {}
    expectations = Expectations.load()
    fact_query = "SELECT norad, name, object_type FROM object"
    if only:
        fact_query += " WHERE norad IN (" + ",".join("?" for _ in only) + ")"
    facts = {
        row[0]: (row[1] or f"OBJECT {row[0]}", row[2] or "UNKNOWN")
        for row in connection.execute(fact_query, tuple(only) if only else ())
    }
    result = into if into is not None else ArchivePass(
        inclination_corroboration=_inclination_corroboration)
    if catalog and result.catalogue_geo_north_south_events is None:
        result.catalogue_geo_north_south_events = 0
    started = time.time()
    objects_this_run = 0
    resume_after = start_after

    def absorb(norad: int, rows: list[tuple[int, float, float, float, float | None]]) -> None:
        name, object_type = facts.get(norad, (f"OBJECT {norad}", "UNKNOWN"))
        epochs = {} if _columnar_store is not None and (gpu_executor or gpu_verifier) else None
        intervals = intervals_from_rows(norad, name, object_type, rows, epoch_slices=epochs)
        result.objects_scanned += 1
        if len(intervals) < MINIMUM_BASELINE_INTERVALS + 1:
            return
        result.objects_with_baseline += 1
        record = catalog.get(norad, {})
        diagnostics: dict[str, int] = {}
        events = detect_object_events(
            intervals, kappa=kappa, expectations=expectations, record=record,
            diagnostics=diagnostics,
            gpu_verifier=gpu_verifier, gpu_executor=gpu_executor,
            gpu_epoch_slices=epochs,
            _inclination_corroboration=result.inclination_corroboration,
        )
        result.tracking_gap_drops += diagnostics.get("trackingGapDroppedIntervals", 0)
        result.implausible_costs += diagnostics.get("implausibleCosts", 0)
        uncorroborated = diagnostics.get("inclinationUncorroborated", 0)
        result.inclination_uncorroborated += uncorroborated
        if uncorroborated and object_type.upper() in (*PASSIVE_TYPES, "PAYLOAD"):
            breakdown = (result.passive_breakdown if object_type.upper() in PASSIVE_TYPES
                         else result.payload_breakdown)
            counts = breakdown.setdefault("abstention", {})
            counts["inclinationUncorroborated"] = counts.get("inclinationUncorroborated", 0) + uncorroborated
        if norad in catalog:
            result.catalogue_geo_north_south_events += sum(
                e.signature == "geo-north-south-keeping" for e in events)
        propulsive = [e for e in events if e.signature not in NON_PROPULSIVE_SIGNATURES]
        result.note(object_type, len(intervals), len(propulsive), _covered_days(intervals),
                    observed=intervals, propulsive=propulsive)
        if keep_summaries_for is not None and norad not in keep_summaries_for:
            return
        if events:
            result.events.extend(events)
        result.summaries.append(summarise_object(intervals, events, record=record))

    if _columnar_store is None:
        source = stream_object_rows(connection, since_ms=since_ms, only=only,
                                    start_after_norad=start_after, page_rows=_page_rows)
    else:
        source = ((obj.norad, obj) for obj in _columnar_store.iter_objects(
            only=only or None, since_ms=since_ms, start_after=start_after))
    for norad, rows in source:
        absorb(norad, rows)
        # Set AFTER the object is fully absorbed, never before: the cursor is a
        # promise that everything up to and including it is in `result`.
        resume_after = norad
        objects_this_run += 1
        if progress_every and result.objects_scanned % progress_every == 0:
            print(
                f"  {result.objects_scanned} objects, {time.time() - started:.0f}s, "
                f"{len(result.events)} events",
                flush=True,
            )
        if deadline is not None and time.time() >= deadline:
            # Deliberately NOT sorted: `summaries` is only ordered once, on the
            # slice that finishes the sweep, so a partial ordering is never
            # mistaken for a final one.
            return SweepProgress(
                result, resume_after, objects_this_run, time.time() - started
            )
    if _sort_summaries:
        result.summaries.sort(key=lambda row: -row["deltaVMetresPerSecond"])
    return SweepProgress(result, None, objects_this_run, time.time() - started)


def control_rates_by_object(scan: ArchivePass, *, kappa: float) -> dict[str, Any]:
    """Pooled control unchanged, plus all fifteen predeclared measured controls."""
    pooled = _control_rates(scan, kappa=kappa)
    pooled["detectorFlags"] = detector_flags()
    # DISCLOSURE, not a rate change: docs/paperb-preregistration-20260920.md's
    # registered covariate-matched transfer test (measured 2026-09-20, commits
    # f317a28..7626c55) found this pooled passive floor does not transfer to
    # the payload covariate mix. Numbers are read verbatim from
    # docs/paperb-results-20260920.json (analysis1CorroborationOn) and never
    # recomputed here; this block changes no threshold, no gate and no rate
    # above.
    pooled["covariateTransfer"] = {
        "measured": "2026-09-20",
        "rawFloorPer1000": 0.163,
        "payloadReweightedPer1000": 0.335,
        "honestTierPer1000": 0.224,
        "honestTierCI": [0.154, 1.846],
        # The multiplication a reader would otherwise have to do themselves, and
        # it goes against us: the published separation is computed on the RAW
        # floor, so dividing it by the measured reweighting factor gives the
        # separation on the floor this analysis says is the applicable one, and
        # that number is below MIN_SEPARATION_BOUND_RATIO. Disclosure only --
        # the shipped gate still reads the raw floor, and Phase 3 is where
        # changing that is registered.
        "compositeMatchedSeparation": 8.83,
        "compositeNote": (
            "raw-floor separation 18.191x divided by the registered reweighting "
            "factor 2.0591; the sensitivity variant (48 cells) gives 13.77x; "
            "see Phase 3"
        ),
        "verdict": (
            "registered transfer test failed; pooled floor may understate the "
            "payload-covariate floor; see Phase 3"
        ),
        "reference": "docs/paperb-*-20260920",
    }
    pooled["note"] += (
        " A registered covariate-matched transfer test found this pooled floor does not "
        "demonstrably bound the payload population; see covariateTransfer."
    )
    pooled["inclinationUncorroborated"] = {
        "enabled": scan.inclination_corroboration,
        "intervals": scan.inclination_uncorroborated if scan.inclination_corroboration else None,
        "minimumInclinationDeg": INCLINATION_CORROBORATION_MIN_DEG,
        "reason": INCLINATION_UNCORROBORATED_REASON,
        "gap": (None if scan.inclination_corroboration else
                "legacy checkpoint: entire sweep retains the pre-corroboration detector; "
                "abstentions are not measured until the next fresh sweep"),
    }
    pooled["trackingGapDroppedIntervals"] = (
        scan.tracking_gap_drops if DECLINE_AFTER_TRACKING_GAP
        else "not measured: DECLINE_AFTER_TRACKING_GAP is disabled"
    )
    # Counted since aee7ed8/M24 but, until now, only ever printed to stderr:
    # no committed artifact carried the full-population value. Recorded here
    # the same way as its siblings above -- a screen that removes data owes
    # the reader a number, not just a log line.
    pooled["implausibleCosts"] = scan.implausible_costs
    pooled["catalogueGeoNorthSouthKeepingEvents"] = (
        scan.catalogue_geo_north_south_events if scan.catalogue_geo_north_south_events is not None
        else "not measured: teaching catalogue was unavailable to the sweep"
    )
    pooled["strata"] = {
        era: {band: _control_rates(scan.strata.get((era, band), ArchivePass()), kappa=kappa,
                                  minimum_intervals=MINIMUM_STRATUM_PASSIVE_INTERVALS)
              for band in CONTROL_BANDS}
        for era in CONTROL_ERAS
    }
    pooled["strataDefinition"] = {
        "eras": list(CONTROL_ERAS),
        "perigeeBands": list(CONTROL_BANDS),
        "edges": "upper edges inclusive, exactly as CATALOGUE_NOISE_FLOOR: 500, 800, 1500, 30000 km",
        "minimumPassiveIntervals": MINIMUM_STRATUM_PASSIVE_INTERVALS,
    }
    for bands in pooled["strata"].values():
        high_eccentricity = bands["1500-30000"]
        if not high_eccentricity["sufficientToLabel"]:
            high_eccentricity["blockingReason"] = (
                "not calibrated for high-eccentricity orbits: " + high_eccentricity["blockingReason"])
    pooled["matchedControlStatus"] = (
        "measured; each event uses its era and noise-floor band"
        if MATCHED_CONTROL_STRATA_ENABLED else
        "not enabled: matched-control acceptance has not been measured"
    )
    return pooled


def _control_rates(scan: ArchivePass, *, kappa: float,
                   minimum_intervals: int = 200) -> dict[str, Any]:
    """The false-alarm rate of the self-history detector, on objects that cannot burn.

    Reported two ways, because they answer different questions and the second
    is the one an operator-facing figure needs:

    * **per interval** — how often a single pair of element sets is flagged.
      This is the number `docs/orbit-history-design.md` §3.7 sets a target for.
    * **per object-year** — how many spurious "corrections" a visitor would see
      on one dead object over a year of browsing. A per-interval rate of one in
      a thousand still means several flags a year on an object the catalogue
      fits three times a day, and saying only the first number would hide that.

    Intervals are Jeffreys, never Wald: at zero flags Wald returns [0, 0], a
    claim of a false-alarm rate of exactly zero, which is the single most
    misleading number this module could publish.
    """
    passive_rate = (
        scan.passive_flags / scan.passive_intervals if scan.passive_intervals else None
    )
    payload_rate = (
        scan.payload_flags / scan.payload_intervals if scan.payload_intervals else None
    )
    passive_low, passive_high = _jeffreys_interval(scan.passive_flags, scan.passive_intervals)
    payload_low, payload_high = _jeffreys_interval(scan.payload_flags, scan.payload_intervals)
    separation = _two_proportion_z(
        scan.payload_flags, scan.payload_intervals, scan.passive_flags, scan.passive_intervals
    )
    p = separation.get("approximatePValue")
    z = separation.get("z")
    payload_excess_significant = (
        z is not None and z > 0 and p is not None and p < 0.01
    )
    # SIGNIFICANCE IS NOT SEPARATION, at this sample size.
    #
    # The p-value above asks whether payloads are flagged more often than
    # passive objects AT ALL. Against 89.1 M passive and 62.5 M payload
    # intervals that question is answered by the size of the archive: the
    # pooled z is about 459, and the same test stays significant for a rate
    # ratio of 1.001. A detector tightened until it flags almost nothing would
    # still pass it -- which is precisely the way a false-alarm target can be
    # met by detecting nothing.
    #
    # So ask the second question too, in effect size: does the payload rate
    # stand clear of the passive floor by a wide margin? Bound against bound,
    # for the same reason the false-alarm half uses the upper bound.
    separation_bound = separation_verdict(passive_high, payload_low)
    separated = bool(separation_bound.get("meets"))
    # The design target, restated per interval.
    target = 1.0 / 1000.0
    sufficient = (
        scan.passive_intervals >= minimum_intervals
        and passive_high is not None
        and passive_high < target
        and payload_excess_significant
        and separated
    )
    blocking: str | None = None
    if not sufficient:
        if scan.passive_intervals < minimum_intervals:
            blocking = "the passive control holds too few intervals to bound a rate"
            if minimum_intervals != 200:
                blocking = f"not calibrated: {blocking} (requires {minimum_intervals:,})"
        elif passive_high is not None and passive_high >= target:
            blocking = (
                f"the upper bound on the false-alarm rate is {passive_high * 1000:.1f} per 1,000 "
                f"intervals, not below the design target of 1 per 1,000"
            )
        elif not payload_excess_significant:
            blocking = (
                "payloads are not yet flagged significantly more often than objects that cannot "
                "manoeuvre"
            )
        elif not separated:
            blocking = separation_bound.get("gap") or (
                "payloads are flagged more often than objects that cannot manoeuvre, but not by "
                "a wide enough margin to lend the word manoeuvre to any single flag"
            )
    return {
        "basis": "self-history",
        "kappa": kappa,
        "rateSeparation": separation_bound,
        "passive": {
            "objects": scan.passive_objects,
            "intervals": scan.passive_intervals,
            "flags": scan.passive_flags,
            "flaggedObjects": scan.passive_flagged_objects,
            "ratePerInterval": passive_rate,
            "ratePerObjectYear": (
                scan.passive_flags * 365.25 / scan.passive_object_days
                if scan.passive_object_days > 0
                else None
            ),
            "jeffreys95": [passive_low, passive_high],
            "objectDays": round(scan.passive_object_days, 1),
            # PHASE 0. What this rate is MADE of, by channel, signature, regime
            # and perigee band. A floor concentrated in one channel is a fixable
            # problem; one spread evenly is a property of the method.
            "breakdown": _ranked_breakdown(getattr(scan, "passive_breakdown", {})),
        },
        "payload": {
            "objects": scan.payload_objects,
            "intervals": scan.payload_intervals,
            "flags": scan.payload_flags,
            "ratePerInterval": payload_rate,
            "ratePerObjectYear": (
                scan.payload_flags * 365.25 / scan.payload_object_days
                if scan.payload_object_days > 0
                else None
            ),
            "jeffreys95": [payload_low, payload_high],
            "objectDays": round(scan.payload_object_days, 1),
            # The same decomposition for the payload side. Raising separation by
            # catching MORE real manoeuvres needs to know which channels are
            # already carrying the payload rate and which contribute nothing.
            "breakdown": _ranked_breakdown(getattr(scan, "payload_breakdown", {})),
        },
        "separation": {**separation,
                       "ratio": (payload_rate / passive_rate) if passive_rate else None},
        "targetRatePerInterval": target,
        "sufficientToLabel": bool(sufficient),
        "blockingReason": blocking,
        "note": (
            "Debris and spent rocket stages have no propulsion, so every flag on one is a false "
            "alarm by construction. The interval is Jeffreys rather than Wald: at zero flags "
            "Wald would report a false-alarm rate of exactly zero, which no control can support."
        ),
    }


def score_ground_truth_with_coverage(
    events: Sequence[OrbitEvent],
    truth: GroundTruth,
    coverage_by_norad: dict[int, list[tuple[int, int]]],
    *,
    match_window_hours: float = 36.0,
) -> dict[str, Any]:
    """Detection rate, scored only where the archive actually holds the object.

    **This is the correction the backfill forced.** `orbit_events.score_against_
    ground_truth` decides scorability from the archive's global first and last
    epoch. That was right when the archive was one continuous run of hours. It
    is wrong now: the archive holds a full year of 2024 and a few hours of
    2026-08-07 with a nineteen-month hole between them, so a published
    manoeuvre from 2026-04 sits inside the global window while the archive
    holds nothing whatever near it. Scored globally it would count as a MISS,
    and the detection rate would be driven down by a gap rather than by the
    detector.

    So scorability is decided per object, against that object's own contiguous
    observation runs.
    """
    matched: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    window_ms = int(match_window_hours * 3_600_000)

    by_norad: dict[int, list[OrbitEvent]] = {}
    for event in events:
        by_norad.setdefault(event.norad, []).append(event)

    for entry in truth.entries:
        occurred = _parse_iso_ms(entry.get("occurredAt"))
        norad = entry.get("norad")
        summary = {
            "object": entry.get("object"),
            "norad": norad,
            "occurredAt": entry.get("occurredAt"),
            "type": entry.get("type"),
            "publishedDeltaVMetresPerSecond": entry.get("deltaVMetresPerSecond"),
            "source": entry.get("source"),
        }
        if occurred is None:
            pending.append({**summary, "reason": "no-time-published"})
            continue
        if norad is None:
            pending.append({**summary, "reason": "no-catalog-number-published"})
            continue
        runs = coverage_by_norad.get(int(norad), [])
        covered = any(start <= occurred <= end for start, end in runs)
        if not covered:
            pending.append({**summary, "reason": "archive-holds-no-elements-here"})
            continue
        hit = next(
            (
                event
                for event in by_norad.get(int(norad), [])
                if event.signature not in NON_PROPULSIVE_SIGNATURES
                if event.start_ms - window_ms <= occurred <= event.end_ms + window_ms
            ),
            None,
        )
        if hit is None:
            missed.append(summary)
            continue
        published = entry.get("deltaVMetresPerSecond")
        detected = hit.delta_v.total
        matched.append(
            {
                **summary,
                "detectedSignature": hit.signature,
                "detectedDeltaVMetresPerSecond": round(detected, 4),
                "detectedStartAt": _iso(hit.start_ms),
                "detectedEndAt": _iso(hit.end_ms),
                # The single most informative number this whole feature can
                # produce: an element-derived cost against a cost an
                # accelerometer measured on board.
                "agreementRatio": (
                    round(detected / published, 3)
                    if isinstance(published, (int, float)) and published
                    else None
                ),
            }
        )

    scored = len(matched) + len(missed)
    return {
        "tableVersion": truth.version,
        "publishedEvents": len(truth.entries),
        "scorable": scored,
        "detected": len(matched),
        "notDetected": len(missed),
        "pending": len(pending),
        "detectionRate": (len(matched) / scored) if scored else None,
        "matches": matched,
        "misses": missed,
        "pendingEvents": pending[:200],
        "note": (
            "Scorability is decided per object against that object's own contiguous observation "
            "runs, not against the archive's global first and last epoch. The archive contains a "
            "real hole between the end of the bulk bundles and the start of live capture, and an "
            "event inside that hole is one the archive cannot see, not one the detector missed."
        ),
    }


def archive_maturity_from_scan(
    connection: sqlite3.Connection,
    scan: "ArchivePass",
    controls: dict[str, Any],
) -> dict[str, Any]:
    """What this archive can support, decided from what it HOLDS.

    Replaces `orbit_events.archive_maturity` on the backfilled archive, and it
    exists because that function got three things wrong the moment the bulk
    bundles landed — all three in the same direction, which is the dangerous
    one: it under-reported what the site could already do.

    1. **Maturity was keyed on the capture ledger.** Correct when the archive
       was one continuous run of hourly captures, and it was written that way
       to fix a real bug in the other direction. But the ledger records nine
       captures over a few hours, while the archive now holds a full year of
       2024. Every longitudinal view stayed switched off in front of data that
       could answer it.
    2. **`measured-false-alarm-rate` was hard-wired `available: False`.** A
       capability that can never become true is a dead branch, and this project
       has a named defect class for those. It is now read from the control.
    3. **The coverage note said the bulk element classes are "a separate, more
       tightly rate-limited product this installation does not use."** That was
       true of `gp_history`, the API class. space-track publishes the same
       history as yearly bundles on a cloud share and asks callers to use those
       instead, which is what `pipeline/orbit_history_backfill.py` does.

    Observation is measured as **object-days**: the summed span of intervals
    actually held, per object, never the calendar distance between the first
    and last epoch. The archive contains a real hole between the end of the
    bundles and the start of live capture, and an object watched for a year in
    2024 and an hour in 2026 has been watched for about a year.
    """
    stats = archive_stats(connection)
    ledger_days = observation_span_days(connection)
    held_days = scan.passive_object_days + scan.payload_object_days
    longest = max((row["observedDays"] for row in scan.summaries), default=0.0)
    with_cadence = sum(1 for row in scan.summaries if row.get("cadence"))
    with_repeats = sum(1 for row in scan.summaries if row.get("repeatClusters"))

    capabilities = [
        {
            "id": "population-cohort-screen",
            "available": scan.objects_scanned > 0,
            "needs": "about a hundred overlapping intervals across the population",
            "why": (
                "The cohort control compares an object against others at the same altitude and "
                "inclination over the same hours. It needs many objects at one moment, not one "
                "object over many months, so it works on the day the archive starts."
            ),
        },
        {
            "id": "per-object-cadence",
            "available": with_cadence > 0,
            "objectsReady": with_cadence,
            "needs": "at least three detected corrections for one object inside one observation run",
            "why": (
                "How often an object corrects is a property of its own time series and cannot be "
                "borrowed from the population."
            ),
        },
        {
            "id": "station-keeping-cadence",
            "available": with_repeats > 0,
            "objectsReady": with_repeats,
            "needs": "several complete cycles of the same correction, which for geostationary "
                     "east-west keeping means about three weeks",
            "why": (
                "A cadence needs several complete cycles before its regularity means anything. "
                "Four corrections at irregular spacing are not a cadence."
            ),
        },
        {
            "id": "storm-density-enhancement",
            "available": longest >= 7.0,
            "needs": "a geomagnetically quiet baseline window and a storm window in the same archive",
            "why": (
                "The density ratio is each object's storm-time decay against its OWN quiet-time "
                "decay, so the archive has to contain both."
            ),
        },
        {
            "id": "measured-false-alarm-rate",
            "available": bool(controls.get("sufficientToLabel")),
            "needs": "a passive control large enough to bound the rate below one in a thousand "
                     "intervals, and payloads flagged significantly more often than it",
            "blockedBy": controls.get("blockingReason"),
            "why": (
                "Until the false-alarm rate is bounded, no event may carry a manoeuvre label. "
                "The plots ship; the labels do not."
            ),
        },
    ]
    return {
        "archive": stats,
        "captureLedgerDays": round(ledger_days, 4),
        "observedObjectDays": round(held_days, 1),
        "longestSingleObjectDays": round(longest, 2),
        "objectsScanned": scan.objects_scanned,
        "objectsWithBaseline": scan.objects_with_baseline,
        "objectsSummarised": len(scan.summaries),
        "capabilities": capabilities,
        "spanNote": (
            "Maturity is decided on how much of each object the archive actually holds, summed "
            "over the intervals it can join, rather than on the capture ledger or on the distance "
            "between the first and last epoch. The ledger under-counts a back-filled archive by "
            "years; the epoch span over-counts it by the size of the hole in the middle."
        ),
        "coverageNote": (
            "The archive holds what the hourly capture has seen since 2026-08-07 and whatever the "
            "bulk back-fill has imported from space-track's published yearly bundles. The two do "
            "not meet: there is a real gap between the end of the bundles and the start of live "
            "capture, it is never interpolated across, and it is the reason an operator-published "
            "manoeuvre inside it is recorded as unscorable rather than as missed."
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--kappa", type=float, default=DEFAULT_KAPPA)
    parser.add_argument("--norad", type=int, action="append", default=None,
                        help="restrict to these catalogue numbers (repeatable)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--controls", action="store_true")
    parser.add_argument("--ground-truth", action="store_true")
    parser.add_argument("--events", action="store_true")
    parser.add_argument("--progress", type=int, default=0)
    parser.add_argument("--all-objects", action="store_true",
                        help="keep a summary row for every object, not just the teaching "
                             "catalogue. The control counters are accumulated over every object "
                             "either way; this only changes what is RETAINED, and retaining "
                             "thirty-one thousand rows is how a streaming pass stops streaming.")
    parser.add_argument("--out", type=Path, default=None, help="write the whole pass as JSON")
    args = parser.parse_args(argv)

    connection = open_archive_for_reading(args.archive)
    catalog = load_catalog(args.data_root)
    scan = scan_archive(
        connection,
        kappa=args.kappa,
        only=args.norad,
        catalog=catalog,
        keep_summaries_for=None if (args.all_objects or args.norad) else set(catalog),
        progress_every=args.progress,
    )
    controls = control_rates_by_object(scan, kappa=args.kappa)

    payload: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "objectsScanned": scan.objects_scanned,
        "objectsWithBaseline": scan.objects_with_baseline,
        "events": len(scan.events),
        "controls": controls,
    }
    if args.ground_truth:
        coverage = {
            row["norad"]: [
                (_parse_iso_ms(run["fromAt"]), _parse_iso_ms(run["toAt"]))
                for run in row["observationRuns"]
            ]
            for row in scan.summaries
        }
        payload["groundTruth"] = score_ground_truth_with_coverage(
            scan.events, GroundTruth.load(), coverage
        )
    if args.events:
        top = sorted(scan.events, key=lambda e: -abs(e.delta_v.total))[: args.limit]
        payload["topEvents"] = [e.as_dict() for e in top]
    if not args.controls and not args.ground_truth and not args.events:
        payload["topObjects"] = scan.summaries[: args.limit]

    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out} ({len(text)} bytes)")
    else:
        print(text)
    return 0


if __name__ == "__main__":                          # pragma: no cover
    raise SystemExit(main())
