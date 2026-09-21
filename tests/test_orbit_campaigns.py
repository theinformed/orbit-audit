#!/usr/bin/env python3
"""Tests for the per-object (self-history) orbit detector and its publishing path.

No network and no archive on disk: every test builds its own element-set series
or its own in-memory SQLite archive.

Grouped by the failure each test exists to prevent. `docs/OPEN-WORK.md` records
four defect classes this codebase has already produced *with green tests over
them* — a green test over a never-executed default being the first — so several
tests here assert that the production path really was taken, not merely that a
function returns something.
"""

from __future__ import annotations

import json
import io
import contextlib
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import orbit_campaigns as oc
from pipeline import orbit_events as oe
from pipeline import orbit_release as orl
from pipeline.orbit_history import MU_WGS72, RE_WGS72


DAY_MS = 86_400_000
BASE_MS = 1_700_000_000_000


def mean_motion_for(a_km: float) -> float:
    return math.sqrt(MU_WGS72 / a_km**3) * 86400.0 / (2.0 * math.pi)


def series(
    *,
    days: float = 90.0,
    cadence_hours: float = 6.0,
    a_km: float = RE_WGS72 + 420.0,
    decay_metres_per_day: float = -60.0,
    steps: dict[float, float] | None = None,
    spikes: dict[float, float] | None = None,
    inclination_deg: float = 51.6,
    eccentricity: float = 0.0004,
) -> list[tuple[int, float, float, float, float | None]]:
    """A synthetic element-set series with optional real steps and fake spikes.

    `steps` are permanent changes in semi-major axis, in metres, keyed on the day
    they happen — a burn. `spikes` are changes present in exactly one element set
    and gone from the next — a loose fit. Telling those two apart is the whole
    job of `step_persistence`, and no test of it is meaningful unless the fixture
    contains both.
    """
    steps = steps or {}
    spikes = spikes or {}
    rows: list[tuple[int, float, float, float, float | None]] = []
    samples = int(days * 24.0 / cadence_hours)
    for index in range(samples):
        day = index * cadence_hours / 24.0
        offset_m = decay_metres_per_day * day
        for at, size in steps.items():
            if day >= at:
                offset_m += size
        for at, size in spikes.items():
            if abs(day - at) < 1e-9:
                offset_m += size
        a = a_km + offset_m / 1000.0
        rows.append(
            (
                BASE_MS + int(day * DAY_MS),
                mean_motion_for(a),
                eccentricity,
                inclination_deg,
                1e-4,
            )
        )
    return rows


def intervals(rows, **kwargs) -> list[oe.Interval]:
    return oc.intervals_from_rows(1, "TEST OBJECT", kwargs.pop("object_type", "PAYLOAD"), rows)


# ---------------------------------------------------------------------------
# The baseline is measured, not modelled
# ---------------------------------------------------------------------------
class BaselineTests(unittest.TestCase):
    def test_baseline_recovers_the_decay_rate_it_was_given(self):
        """The whole design rests on this: drag is absorbed by measuring it."""
        rows = series(decay_metres_per_day=-137.0)
        blocks = oc._blocks_for(intervals(rows), "semiMajorAxis")
        middle = sorted(blocks)[len(blocks) // 2]
        baseline = oc.baseline_at(blocks, middle)
        self.assertTrue(baseline.usable)
        self.assertAlmostEqual(baseline.rate, -137.0, delta=3.0)

    def test_baseline_excludes_its_own_block(self):
        """A burn must never be allowed to become the baseline it is judged against.

        The same shape as the mistake `orbit_events` made when it billed an
        operator for a channel that never tripped: the evidence and the
        expectation have to come from different data.
        """
        blocks = {0: oc._Block(median=-50.0, mad=5.0, count=10),
                  1: oc._Block(median=9999.0, mad=5.0, count=10),
                  2: oc._Block(median=-50.0, mad=5.0, count=10),
                  3: oc._Block(median=-50.0, mad=5.0, count=10)}
        baseline = oc.baseline_at(blocks, 1)
        self.assertAlmostEqual(baseline.rate, -50.0, delta=0.001)

    def test_a_thin_history_is_declined_rather_than_guessed(self):
        rows = series(days=3.0, cadence_hours=24.0)
        self.assertEqual(oc.detect_object_events(intervals(rows)), [])


# ---------------------------------------------------------------------------
# Persistence: the test that separated the detector from its own noise
# ---------------------------------------------------------------------------
class PersistenceTests(unittest.TestCase):
    def test_a_real_step_is_found(self):
        rows = series(steps={45.0: 3000.0})
        events = oc.detect_object_events(intervals(rows))
        self.assertTrue(events, "a three-kilometre permanent raise must be detected")
        raise_events = [e for e in events if e.signature == "along-track-raise"]
        self.assertEqual(len(raise_events), 1)

    def test_a_one_fit_spike_of_the_same_size_is_not(self):
        """Identical amplitude, opposite verdict. This is the control test.

        A detector that fires on both is a detector measuring the catalogue's
        fitting process rather than the satellite.
        """
        rows = series(spikes={45.0: 3000.0})
        events = oc.detect_object_events(intervals(rows))
        self.assertEqual(
            [e.signature for e in events], [],
            "a change that the next element set undoes cannot be propulsive",
        )

    def test_persistence_declines_rather_than_guesses_at_the_end_of_coverage(self):
        step_at_the_very_end = series(days=60.0, steps={59.8: 4000.0})
        result = oc.step_persistence(
            intervals(step_at_the_very_end),
            [
                {element: oc.Baseline(rate=-60.0, scale=5.0, blocks=9, samples=90)
                 for element in oc.ELEMENTS}
                for _ in intervals(step_at_the_very_end)
            ],
            len(intervals(step_at_the_very_end)) - 1,
            element="semiMajorAxis",
        )
        self.assertFalse(result["persistent"])
        self.assertEqual(result["intervalsChecked"], 0)

    def test_one_following_fit_is_not_two_days_of_persistence(self):
        """The production bug: any follow-up interval used to satisfy a two-day claim."""
        built = intervals(series(days=60.0, steps={59.0: 4000.0}))
        baselines = [
            {element: oc.Baseline(rate=-60.0, scale=5.0, blocks=9, samples=90)
             for element in oc.ELEMENTS}
            for _ in built
        ]
        event_position = next(
            index for index, interval in enumerate(built)
            if interval.start_ms >= BASE_MS + int(59.0 * DAY_MS)
        )
        result = oc.step_persistence(
            built, baselines, event_position, element="semiMajorAxis"
        )
        self.assertGreater(result["intervalsChecked"], 0)
        self.assertLess(result["observedHorizonDays"], oc.PERSISTENCE_HORIZON_DAYS)
        self.assertFalse(result["persistent"])

    def test_a_node_step_uses_its_j2_residual_and_persists(self):
        built = intervals(series(days=60.0))
        position = len(built) // 2
        changed = []
        for index, interval in enumerate(built):
            residual = 0.0 if index < position else 0.2
            drift = interval.j2_drift_deg
            changed.append(oe.Interval(**{
                **vars(interval),
                "raan_deg": 40.0,
                "arg_perigee_deg": 20.0,
                "delta_raan_deg": (drift[0] if drift else 0.0)
                                  + (residual if index == position else 0.0),
                "delta_arg_perigee_deg": drift[1] if drift else 0.0,
            }))
        channels = (*oc.ELEMENTS, "raan")
        blocks = {element: oc._blocks_for(changed, element) for element in channels}
        indices = [int(i.mid_ms // int(oc.BLOCK_DAYS * DAY_MS)) for i in changed]
        baselines = [
            {element: oc.baseline_at(blocks[element], block) for element in channels}
            for block in indices
        ]
        verdict = oc.step_persistence(changed, baselines, position, element="raan")
        self.assertTrue(verdict["persistent"])

    def test_the_failed_self_history_node_control_keeps_the_channel_disabled(self):
        plain = series(days=90.0)
        rate = oe.j2_secular_rates_deg_per_day(
            RE_WGS72 + 420.0, 0.0004, 51.6
        )[0]
        with_node = []
        for epoch, mm, ecc, inc, bstar in plain:
            day = (epoch - BASE_MS) / DAY_MS
            raan = (40.0 + rate * day + (0.2 if day >= 45.0 else 0.0)) % 360.0
            with_node.append((epoch, mm, ecc, inc, bstar, raan, 20.0))
        events = oc.detect_object_events(intervals(with_node))
        self.assertFalse(oc.SELF_HISTORY_NODE_CHANNEL_ENABLED)
        self.assertNotIn("raan", oc.ELEMENTS)
        self.assertEqual([event for event in events if event.signature == "node-change"], [])

    def test_an_unpersistent_node_cannot_relabel_a_persistent_raise(self):
        plain = series(days=90.0, steps={45.0: 3000.0})
        rate = oe.j2_secular_rates_deg_per_day(
            RE_WGS72 + 420.0, 0.0004, 51.6
        )[0]
        with_node_spike = []
        for epoch, mm, ecc, inc, bstar in plain:
            day = (epoch - BASE_MS) / DAY_MS
            node_spike = 0.2 if abs(day - 45.0) < 1e-9 else 0.0
            raan = (40.0 + rate * day + node_spike) % 360.0
            with_node_spike.append((epoch, mm, ecc, inc, bstar, raan, 20.0))
        events = oc.detect_object_events(intervals(with_node_spike))
        self.assertEqual([event.signature for event in events], ["along-track-raise"])
        self.assertFalse(any(
            test.element == "raan" and test.tripped
            for test in events[0].tests
        ))

    def test_a_window_also_requires_two_observed_days_after_it(self):
        built = intervals(series(days=60.0, steps={59.0: 4000.0}))
        baselines = [
            {element: oc.Baseline(rate=-60.0, scale=5.0, blocks=9, samples=90)
             for element in oc.ELEMENTS}
            for _ in built
        ]
        first = next(
            index for index, interval in enumerate(built)
            if interval.start_ms >= BASE_MS + int(59.0 * DAY_MS)
        )
        result = oc.window_persistence(
            built, baselines, first, first, element="semiMajorAxis"
        )
        self.assertGreater(result["intervalsChecked"], 0)
        self.assertLess(result["observedHorizonDays"], oc.PERSISTENCE_HORIZON_DAYS)
        self.assertFalse(result["persistent"])

    def test_persistence_never_reaches_across_an_archive_gap(self):
        """A gap is not evidence of anything, in either direction."""
        rows = series(days=20.0) + series(days=20.0)[:0]
        left = intervals(rows)
        shifted = [
            oe.Interval(**{**vars(interval),
                           "start_ms": interval.start_ms + 400 * DAY_MS,
                           "end_ms": interval.end_ms + 400 * DAY_MS})
            for interval in left
        ]
        joined = left + shifted
        baselines = [
            {element: oc.Baseline(rate=-60.0, scale=5.0, blocks=9, samples=90)
             for element in oc.ELEMENTS}
            for _ in joined
        ]
        result = oc.step_persistence(joined, baselines, len(left) - 1, element="semiMajorAxis")
        self.assertEqual(result["intervalsChecked"], 0)


# ---------------------------------------------------------------------------
# The noise floor is measured from the object, not assumed from the catalogue
# ---------------------------------------------------------------------------
class ControlBreakdownTests(unittest.TestCase):
    """PHASE 0: the two control rates must say what they are made of.

    Knowing the detector fires 0.45 times per 1,000 passive intervals says
    nothing about WHY, and both remaining routes to better separation need to
    know which channels and signatures carry the flags. These tests pin the
    accounting, and -- more importantly -- pin the checkpoint compatibility that
    protects a sweep already in progress.
    """

    def _flagged(self):
        built = intervals(series(days=60.0, steps={30.0: 600_000.0}))
        events = oc.detect_object_events(built)
        return built, [e for e in events
                       if e.signature not in oc.NON_PROPULSIVE_SIGNATURES]

    def test_a_flagged_payload_is_decomposed(self):
        built, propulsive = self._flagged()
        self.assertTrue(propulsive, "fixture produced no flag to decompose")
        scan = oc.ArchivePass()
        scan.note("PAYLOAD", len(built), len(propulsive), 60.0,
                  observed=built, propulsive=propulsive)
        self.assertEqual(scan.payload_flags, len(propulsive))
        for dimension in ("signature", "channel", "regime", "perigeeBand"):
            self.assertIn(dimension, scan.payload_breakdown)
        # The counts must RECONCILE with the flag total, or the decomposition is
        # describing a different population from the rate it sits beside.
        by_signature = scan.payload_breakdown["signature"]
        self.assertEqual(sum(by_signature.values()), scan.payload_flags)

    def test_passive_and_payload_are_counted_apart(self):
        built, propulsive = self._flagged()
        scan = oc.ArchivePass()
        scan.note("DEBRIS", len(built), len(propulsive), 60.0,
                  observed=built, propulsive=propulsive)
        self.assertTrue(scan.passive_breakdown)
        self.assertFalse(scan.payload_breakdown,
                         "a debris flag was counted against the payload rate")

    def test_a_checkpoint_written_before_this_change_still_loads(self):
        """The one that protects a working day.

        The sweep pickles ArchivePass and resumes from it, and pickle restores
        __dict__ directly -- dataclass defaults do NOT apply to it. Without the
        __setstate__ backfill, new code meeting an old checkpoint raises
        AttributeError, the loader discards it, and a sweep that had already
        walked 68,000 objects restarts from zero.
        """
        old = oc.ArchivePass()
        old.passive_intervals = 12_345
        old.passive_flags = 67
        state = old.__dict__.copy()
        for absent in ("passive_breakdown", "payload_breakdown"):
            state.pop(absent, None)

        revived = oc.ArchivePass.__new__(oc.ArchivePass)
        revived.__setstate__(state)

        self.assertEqual(revived.passive_intervals, 12_345, "sweep progress lost")
        self.assertEqual(revived.passive_flags, 67)
        self.assertEqual(revived.passive_breakdown, {})
        self.assertEqual(revived.payload_breakdown, {})
        # And it must still be usable, not merely loadable.
        revived.note("DEBRIS", 10, 0, 1.0, observed=[], propulsive=[])

    def test_the_published_breakdown_is_ranked_with_shares(self):
        ranked = oc._ranked_breakdown({"signature": {"rare": 1, "common": 9}})
        self.assertEqual([r["value"] for r in ranked["signature"]],
                         ["common", "rare"])
        self.assertEqual(ranked["signature"][0]["share"], 0.9)


class PhysicalCeilingTests(unittest.TestCase):
    """No published event may cost more than twice its own perigee speed.

    That threshold is a conservative SCREEN, not the true single-impulse
    ceiling: what has to stay below escape is the final speed, not the
    impulse, so the true supremum is (1 + sqrt 2) * v_perigee, about
    2.414 * v_perigee. Twice perigee speed is kept about 21 per cent inside
    that true bound because no real spacecraft manoeuvre approaches even
    twice orbital speed (see pipeline/orbit_events.py, "THE PHYSICAL SCREEN,
    AND WHAT IT IS NOT", corrected 2026-09-21 after an adversarial physics
    review). A pair of element sets implying more than the screen is not an
    expensive manoeuvre, it is two fits that do not describe the same orbit
    -- most often a catalogue re-identification or a badly refitted decaying
    object.

    The screen was added to `delta_v()` and gated at the COHORT call site, but
    not here, in the lane that judges nearly every published event. The cost of
    that omission was visible to readers: MOHAMMED VI-B led the live object list
    at 49,317 m/s, because `scan.summaries` sorts by descending cost and so
    promotes the most impossible figure to the top of the page. Five of 1,500
    published events exceeded twice their own perigee speed.
    """

    # A 27,000 km step in semi-major axis -- chosen to clear 2V rather than
    # merely to be large. The first test below fails if it ever stops doing so,
    # because a fixture that quietly stopped breaching the ceiling would leave
    # the second test passing while proving nothing.
    @staticmethod
    def _absurd():
        return intervals(series(days=40.0, steps={20.0: 100_000_000.0}))

    def test_the_guard_actually_fires_on_this_fixture(self):
        """Guard the guard: prove the drop happened, via the report it prints."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            oc.detect_object_events(self._absurd())
        self.assertIn(
            "exceeded twice the perigee speed",
            stderr.getvalue(),
            "fixture no longer trips the ceiling, so the next test proves nothing",
        )

    def test_no_event_carries_an_impossible_cost(self):
        events = oc.detect_object_events(self._absurd())
        offenders = [event for event in events if event.delta_v.implausible is not None]
        self.assertEqual(
            [(e.norad, e.delta_v.implausible) for e in offenders],
            [],
            "an impossible cost reached the published events",
        )

    def test_implausible_costs_now_reach_diagnostics_not_only_stderr(self):
        """M24: the drop was counted and printed, but landed in no committed

        artifact. `diagnostics` now carries it, the same way
        `trackingGapDroppedIntervals` and `inclinationUncorroborated` already do.
        """
        diagnostics = {}
        oc.detect_object_events(self._absurd(), diagnostics=diagnostics)
        self.assertEqual(diagnostics["implausibleCosts"], 1)


class NoiseFloorTests(unittest.TestCase):
    def test_own_floor_can_only_raise_the_bar(self):
        """A quiet object must never be held to a LOWER bar than the catalogue's."""
        interval = intervals(series())[10]
        tight = oc._self_channel(interval, "semiMajorAxis",
                                 oc.Baseline(rate=0.0, scale=1.0, blocks=9, samples=90),
                                 kappa=8.0, own_floor=0.0)
        loose = oc._self_channel(interval, "semiMajorAxis",
                                 oc.Baseline(rate=0.0, scale=1.0, blocks=9, samples=90),
                                 kappa=8.0, own_floor=5000.0)
        self.assertGreater(loose.floor_sigma, tight.floor_sigma)
        self.assertLess(abs(loose.floor_z), abs(tight.floor_z))

    def test_a_noisy_object_is_not_reported_as_manoeuvring_constantly(self):
        """The measured failure: a loosely fitted object flagged on 1.4% of intervals."""
        import random

        rng = random.Random(7)
        rows = []
        for index in range(4 * 90):
            day = index / 4.0
            a = RE_WGS72 + 800.0 + rng.gauss(0.0, 0.05)      # 50 m of fit scatter
            rows.append((BASE_MS + int(day * DAY_MS), mean_motion_for(a), 0.001, 98.0, 1e-5))
        events = oc.detect_object_events(intervals(rows))
        self.assertLessEqual(
            len(events), 1,
            f"fit scatter alone produced {len(events)} events on one object",
        )

    def test_the_test_basis_travels_with_the_test(self):
        interval = intervals(series())[10]
        test = oc._self_channel(interval, "semiMajorAxis",
                                oc.Baseline(rate=0.0, scale=1.0, blocks=9, samples=90),
                                kappa=8.0)
        self.assertEqual(test.basis, "self-history")
        self.assertEqual(oe.ChannelTest(element="a", delta=0.0, floor_sigma=1.0, floor_z=0.0,
                                        cohort_z=None, cohort_count=0, cohort_screened=False,
                                        tripped=False).basis, "cohort")


# ---------------------------------------------------------------------------
# Cadence, repeats and what is unusual for the object itself
# ---------------------------------------------------------------------------
class CadenceTests(unittest.TestCase):
    def test_a_regular_cadence_is_recognised_as_regular(self):
        rows = series(days=140.0, steps={d: 2500.0 for d in (20.0, 40.0, 60.0, 80.0, 100.0)})
        own = intervals(rows)
        events = oc.detect_object_events(own)
        cadence = oc.cadence_of(events, own)
        self.assertIsNotNone(cadence)
        self.assertAlmostEqual(cadence["medianDaysBetween"], 20.0, delta=1.0)
        self.assertLess(cadence["regularity"], 0.1)

    def test_a_cadence_is_refused_below_three_corrections(self):
        rows = series(days=90.0, steps={30.0: 2500.0, 60.0: 2500.0})
        own = intervals(rows)
        self.assertIsNone(oc.cadence_of(oc.detect_object_events(own), own))

    def test_repeats_use_a_tolerance_band_not_a_rounded_bucket(self):
        """Two corrections either side of a round number are still the same correction.

        `pipeline/teaching_brief.py` documents the bucket-boundary defect at
        length; this is the same defect in a different file.
        """
        class Fake:
            def __init__(self, cost, at, signature="along-track-raise"):
                self.signature = signature
                self.delta_v = oe.DeltaV(0, 0, 0, cost, 0, 0)
                self.start_ms = at
        events = [Fake(0.999, BASE_MS), Fake(1.001, BASE_MS + 20 * DAY_MS),
                  Fake(1.02, BASE_MS + 40 * DAY_MS)]
        clusters = oc.repeat_clusters(events)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["count"], 3)

    def test_a_different_cost_is_a_different_correction(self):
        class Fake:
            def __init__(self, cost, at):
                self.signature = "along-track-raise"
                self.delta_v = oe.DeltaV(0, 0, 0, cost, 0, 0)
                self.start_ms = at
        clusters = oc.repeat_clusters(
            [Fake(1.0, BASE_MS), Fake(1.0, BASE_MS + DAY_MS), Fake(40.0, BASE_MS + 2 * DAY_MS)]
        )
        self.assertEqual([c["count"] for c in clusters], [2])

    def test_nothing_is_unusual_until_something_is_usual(self):
        class Fake:
            def __init__(self, cost, at):
                self.signature = "along-track-raise"
                self.delta_v = oe.DeltaV(0, 0, 0, cost, 0, 0)
                self.start_ms = at
        self.assertEqual(oc.out_of_family_for_itself([Fake(5.0, BASE_MS)], []), [])

    def test_observed_days_never_counts_an_archive_gap(self):
        """An object watched for a year in 2024 and an hour in 2026 has been
        watched for about a year, not for two and a half."""
        left = intervals(series(days=10.0))
        shifted = [
            oe.Interval(**{**vars(interval),
                           "start_ms": interval.start_ms + 600 * DAY_MS,
                           "end_ms": interval.end_ms + 600 * DAY_MS})
            for interval in intervals(series(days=1.0))
        ]
        covered = oc._covered_days(left + shifted)
        self.assertLess(covered, 12.0)
        self.assertEqual(len(oc._segments(left + shifted)), 2)


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
class ControlTests(unittest.TestCase):
    def test_a_control_with_no_flags_never_claims_a_rate_of_zero(self):
        scan = oc.ArchivePass()
        scan.passive_intervals = 400
        scan.passive_flags = 0
        scan.passive_objects = 12
        scan.passive_object_days = 900.0
        controls = oc.control_rates_by_object(scan, kappa=8.0)
        low, high = controls["passive"]["jeffreys95"]
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0, "Wald would return [0, 0] here, which no control supports")

    def test_labels_stay_shut_when_the_control_is_thin(self):
        scan = oc.ArchivePass()
        scan.passive_intervals = 40
        scan.passive_flags = 0
        controls = oc.control_rates_by_object(scan, kappa=8.0)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("too few intervals", controls["blockingReason"])

    def test_labels_stay_shut_when_the_measured_rate_is_above_target(self):
        scan = oc.ArchivePass()
        scan.passive_intervals = 200_000
        scan.passive_flags = 680          # the rate actually measured on this archive
        scan.payload_intervals = 50_000
        scan.payload_flags = 1_000
        controls = oc.control_rates_by_object(scan, kappa=8.0)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("per 1,000", controls["blockingReason"])

    def test_the_target_is_strict_and_equality_still_explains_the_block(self):
        scan = oc.ArchivePass()
        scan.passive_intervals = 1_000
        scan.passive_flags = 0
        scan.payload_intervals = 1_000
        scan.payload_flags = 100
        original = oc._jeffreys_interval
        try:
            oc._jeffreys_interval = lambda *_args, **_kwargs: (0.0005, 0.001)
            controls = oc.control_rates_by_object(scan, kappa=8.0)
        finally:
            oc._jeffreys_interval = original
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("per 1,000", controls["blockingReason"])

    def test_labels_require_payload_rate_to_be_higher(self):
        scan = oc.ArchivePass()
        scan.passive_intervals = 10_000
        scan.passive_flags = 1
        scan.payload_intervals = 100_000
        scan.payload_flags = 0
        controls = oc.control_rates_by_object(scan, kappa=8.0)
        self.assertLess(controls["separation"]["z"], 0)
        self.assertLess(controls["separation"]["approximatePValue"], 0.01)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("not yet flagged significantly", controls["blockingReason"])

    def test_the_control_counts_objects_the_browser_never_shows(self):
        """The negative control is only worth having if it is measured over the
        whole passive population, not the part that made an interesting row."""
        scan = oc.ArchivePass()
        scan.note("DEBRIS", intervals=100, flags=1, days=50.0)
        scan.note("ROCKET BODY", intervals=100, flags=0, days=50.0)
        scan.note("PAYLOAD", intervals=100, flags=9, days=50.0)
        self.assertEqual(scan.passive_intervals, 200)
        self.assertEqual(scan.passive_flags, 1)
        self.assertEqual(scan.payload_flags, 9)

    def test_the_published_control_discloses_the_registered_transfer_finding(self):
        """docs/paperb-results-20260920.md (f317a28..7626c55): the pooled passive
        floor does not transfer to the payload covariate mix. Disclosure only --
        this must not move sufficientToLabel, blockingReason or any rate."""
        scan = oc.ArchivePass()
        scan.passive_intervals = 40
        scan.passive_flags = 0
        controls = oc.control_rates_by_object(scan, kappa=8.0)
        transfer = controls["covariateTransfer"]
        self.assertEqual(transfer["measured"], "2026-09-20")
        self.assertEqual(transfer["rawFloorPer1000"], 0.163)
        self.assertEqual(transfer["payloadReweightedPer1000"], 0.335)
        self.assertEqual(transfer["honestTierPer1000"], 0.224)
        self.assertEqual(transfer["honestTierCI"], [0.154, 1.846])
        # 18.191 / 2.0591 = 8.83, below MIN_SEPARATION_BOUND_RATIO. The
        # disclosure carries the unfavourable composition rather than leaving
        # the reader to perform it.
        self.assertEqual(transfer["compositeMatchedSeparation"], 8.83)
        self.assertLess(transfer["compositeMatchedSeparation"], oe.MIN_SEPARATION_BOUND_RATIO)
        self.assertIn("13.77x", transfer["compositeNote"])
        self.assertIn("2.0591", transfer["compositeNote"])
        self.assertIn("registered transfer test failed", transfer["verdict"])
        self.assertIn("paperb", transfer["reference"])
        self.assertIn("covariateTransfer", controls["note"])
        # Disclosure, not a gate change: this scan is thin, so the control was
        # already shut before covariateTransfer was ever added.
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("too few intervals", controls["blockingReason"])


# ---------------------------------------------------------------------------
# Ground truth, scored against coverage rather than against the calendar
# ---------------------------------------------------------------------------
class GroundTruthTests(unittest.TestCase):
    def _truth(self, occurred_at: str) -> oe.GroundTruth:
        return oe.GroundTruth(
            version="test",
            entries=[{"object": "T", "norad": 1, "occurredAt": occurred_at,
                      "type": "reboost", "deltaVMetresPerSecond": 1.0, "source": "x"}],
        )

    def test_an_event_inside_the_archives_hole_is_unscorable_not_missed(self):
        """The defect the backfill created and this function exists to fix.

        The archive holds 2024 and a few hours of 2026 with a nineteen-month
        hole between. Scored on the archive's global first and last epoch, a
        2026-04 manoeuvre sits inside the window while the archive holds
        nothing near it, and the detection rate falls because of a gap rather
        than because of the detector.
        """
        coverage = {1: [(oe._parse_iso_ms("2024-01-01T00:00:00Z"),
                         oe._parse_iso_ms("2024-12-31T00:00:00Z"))]}
        scored = oc.score_ground_truth_with_coverage(
            [], self._truth("2026-04-16T00:00:00Z"), coverage
        )
        self.assertEqual(scored["notDetected"], 0)
        self.assertEqual(scored["pending"], 1)
        self.assertIsNone(scored["detectionRate"])
        self.assertEqual(scored["pendingEvents"][0]["reason"], "archive-holds-no-elements-here")

    def test_an_event_the_archive_covers_and_the_detector_missed_is_a_miss(self):
        coverage = {1: [(oe._parse_iso_ms("2024-01-01T00:00:00Z"),
                         oe._parse_iso_ms("2024-12-31T00:00:00Z"))]}
        scored = oc.score_ground_truth_with_coverage(
            [], self._truth("2024-06-01T00:00:00Z"), coverage
        )
        self.assertEqual(scored["notDetected"], 1)
        self.assertEqual(scored["detectionRate"], 0.0)

    def test_agreement_with_a_published_delta_v_is_reported(self):
        coverage = {1: [(oe._parse_iso_ms("2024-01-01T00:00:00Z"),
                         oe._parse_iso_ms("2024-12-31T00:00:00Z"))]}
        occurred = oe._parse_iso_ms("2024-06-01T00:00:00Z")
        event = oe.OrbitEvent(
            norad=1, name="T", object_type="PAYLOAD",
            start_ms=occurred - 3600_000, end_ms=occurred + 3600_000,
            signature="along-track-raise", confidence="candidate",
            delta_v=oe.DeltaV(1.1, 0.0, 0.0, 1.1, 0.0, 2000.0),
            drag=oe.DragPrediction(True, "x", 0.0, 1.0, None, 10, 1e-4),
            tests=[], expectation={}, regime="LEO",
            perigee_altitude_km=420.0, apogee_altitude_km=425.0, inclination_deg=51.6,
        )
        scored = oc.score_ground_truth_with_coverage(
            [event], self._truth("2024-06-01T00:00:00Z"), coverage
        )
        self.assertEqual(scored["detected"], 1)
        self.assertAlmostEqual(scored["matches"][0]["agreementRatio"], 1.1, places=3)


# ---------------------------------------------------------------------------
# Streaming, which is the whole reason this module exists in this shape
# ---------------------------------------------------------------------------
class StreamingTests(unittest.TestCase):
    def _archive(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE element_set (norad INTEGER, epoch_ms INTEGER, mean_motion_q INTEGER,
                eccentricity_q INTEGER, inclination_q INTEGER, raan_q INTEGER,
                arg_perigee_q INTEGER, mean_anomaly_q INTEGER, bstar_q INTEGER,
                ndot_q INTEGER, nddot_q INTEGER, rev_at_epoch INTEGER, ingest_hour INTEGER,
                PRIMARY KEY (norad, epoch_ms));
            CREATE TABLE element_set_daily (norad INTEGER, day INTEGER, epoch_ms INTEGER,
                mean_motion_q INTEGER, eccentricity_q INTEGER, inclination_q INTEGER,
                raan_q INTEGER, arg_perigee_q INTEGER, mean_anomaly_q INTEGER,
                bstar_q INTEGER, ndot_q INTEGER, nddot_q INTEGER, rev_at_epoch INTEGER,
                PRIMARY KEY (norad, day));
            CREATE TABLE object (norad INTEGER PRIMARY KEY, name TEXT, object_id TEXT,
                object_type TEXT, rcs_size TEXT, country TEXT, launch_date TEXT,
                first_seen_ms INTEGER, last_seen_ms INTEGER);
            """
        )
        for norad, kind in ((1, "PAYLOAD"), (2, "DEBRIS")):
            connection.execute(
                "INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)",
                (norad, f"OBJ {norad}", "X", kind, "SMALL", "US", "2020-01-01", 0, 0),
            )
            for epoch_ms, mm, ecc, inc, bstar in series(days=40.0):
                connection.execute(
                    "INSERT INTO element_set VALUES (?,?,?,?,?,0,0,0,?,0,0,0,0)",
                    (norad, epoch_ms, int(mm * 1e8), int(ecc * 1e8), int(inc * 1e4),
                     int(bstar * 1e12)),
                )
        connection.commit()
        return connection

    def test_the_stream_yields_one_object_at_a_time_in_catalogue_order(self):
        seen = [norad for norad, _rows in oc.stream_object_rows(self._archive())]
        self.assertEqual(seen, [1, 2])

    def test_the_scan_counts_controls_over_objects_it_does_not_retain(self):
        """`keep_summaries_for` bounds what is HELD, never what is MEASURED."""
        scan = oc.scan_archive(self._archive(), keep_summaries_for={1})
        self.assertEqual([row["norad"] for row in scan.summaries], [1])
        self.assertEqual(scan.passive_objects, 1)
        self.assertGreater(scan.passive_intervals, 0)

    def test_maturity_is_decided_on_what_the_archive_holds(self):
        connection = self._archive()
        scan = oc.scan_archive(connection, keep_summaries_for={1, 2})
        connection.execute(
            "CREATE TABLE capture (captured_ms INTEGER PRIMARY KEY, source TEXT, "
            "source_mtime_ms INTEGER, records_read INTEGER, elements_new INTEGER, "
            "objects_seen INTEGER, rejected INTEGER)"
        )
        connection.execute("CREATE TABLE geomagnetic (index_name TEXT, observed_ms INTEGER, value REAL)")
        connection.execute("CREATE TABLE cold_shard (id INTEGER PRIMARY KEY, rows INTEGER, "
                           "bytes INTEGER, verified_ms INTEGER)")
        maturity = oc.archive_maturity_from_scan(connection, scan, {"sufficientToLabel": False})
        self.assertEqual(maturity["captureLedgerDays"], 0.0)
        self.assertGreater(maturity["observedObjectDays"], 50.0,
                           "the capture ledger is empty; maturity must not be")

    def test_the_false_alarm_capability_is_not_hard_wired_shut(self):
        """It was. A capability that can never become true is a dead branch."""
        connection = self._archive()
        connection.execute(
            "CREATE TABLE capture (captured_ms INTEGER PRIMARY KEY, source TEXT, "
            "source_mtime_ms INTEGER, records_read INTEGER, elements_new INTEGER, "
            "objects_seen INTEGER, rejected INTEGER)"
        )
        connection.execute("CREATE TABLE geomagnetic (index_name TEXT, observed_ms INTEGER, value REAL)")
        connection.execute("CREATE TABLE cold_shard (id INTEGER PRIMARY KEY, rows INTEGER, "
                           "bytes INTEGER, verified_ms INTEGER)")
        scan = oc.scan_archive(connection, keep_summaries_for={1})
        opened = oc.archive_maturity_from_scan(connection, scan, {"sufficientToLabel": True})
        capability = next(c for c in opened["capabilities"] if c["id"] == "measured-false-alarm-rate")
        self.assertTrue(capability["available"])


# ---------------------------------------------------------------------------
# The sweep is resumable, because the archive outgrew one run
# ---------------------------------------------------------------------------
class ResumableSweepTests(unittest.TestCase):
    """The regression that killed six consecutive nightly runs (2026-08-13..18).

    `scan_archive` was one call that had to finish. When the 2004-2025 back-fill
    took `element_set` to 181.3 M rows a whole pass became 6 h 40 m against the
    unit's 3600 s ceiling, so every run was SIGTERMed part-way and discarded an
    hour or more of finished analysis. These tests hold the two properties that
    make that impossible to repeat: a slice can stop, and what it stopped with
    is worth exactly as much as if it had never stopped.
    """

    CATALOGUE = (1, 2, 3, 4, 5)

    def _archive(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE element_set (norad INTEGER, epoch_ms INTEGER, mean_motion_q INTEGER,
                eccentricity_q INTEGER, inclination_q INTEGER, raan_q INTEGER,
                arg_perigee_q INTEGER, mean_anomaly_q INTEGER, bstar_q INTEGER,
                ndot_q INTEGER, nddot_q INTEGER, rev_at_epoch INTEGER, ingest_hour INTEGER,
                PRIMARY KEY (norad, epoch_ms));
            CREATE TABLE object (norad INTEGER PRIMARY KEY, name TEXT, object_id TEXT,
                object_type TEXT, rcs_size TEXT, country TEXT, launch_date TEXT,
                first_seen_ms INTEGER, last_seen_ms INTEGER);
            """
        )
        for norad in self.CATALOGUE:
            kind = "PAYLOAD" if norad % 2 else "DEBRIS"
            connection.execute(
                "INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)",
                (norad, f"OBJ {norad}", "X", kind, "SMALL", "US", "2020-01-01", 0, 0),
            )
            for epoch_ms, mm, ecc, inc, bstar in series(days=40.0):
                connection.execute(
                    "INSERT INTO element_set VALUES (?,?,?,?,?,0,0,0,?,0,0,0,0)",
                    (norad, epoch_ms, int(mm * 1e8), int(ecc * 1e8), int(inc * 1e4),
                     int(bstar * 1e12)),
                )
        connection.commit()
        return connection

    def test_the_resume_cursor_skips_exactly_the_objects_already_done(self):
        """`start_after_norad` is a b-tree seek, not a filter over a re-scan."""
        connection = self._archive()
        seen = [norad for norad, _ in oc.stream_object_rows(connection, start_after_norad=3)]
        self.assertEqual(seen, [4, 5])
        self.assertEqual(
            [norad for norad, _ in oc.stream_object_rows(connection, start_after_norad=5)],
            [],
            "a cursor past the last object must end the sweep, not restart it",
        )

    def test_a_spent_budget_stops_the_sweep_and_says_where(self):
        progress = oc.sweep_archive(
            self._archive(), keep_summaries_for=set(self.CATALOGUE),
            deadline=0.0,   # already past: stop after the first object
        )
        self.assertFalse(progress.complete)
        self.assertEqual(progress.resume_after, 1)
        self.assertEqual(progress.objects_this_run, 1)

    def test_an_unbudgeted_sweep_still_reaches_the_end(self):
        progress = oc.sweep_archive(
            self._archive(), keep_summaries_for=set(self.CATALOGUE)
        )
        self.assertTrue(progress.complete)
        self.assertIsNone(progress.resume_after)
        self.assertEqual(progress.objects_this_run, len(self.CATALOGUE))

    def test_a_sweep_taken_in_slices_equals_the_sweep_taken_whole(self):
        """The property the whole design rests on. If this drifts, resuming lies.

        Not "roughly the same": the same summaries in the same order, the same
        events, and the same control counters. The counters are what decides
        whether the word "manoeuvre" is allowed on the page at all, so a sliced
        sweep that measured them over a different population would publish a
        false-alarm rate nobody could defend.
        """
        whole = oc.scan_archive(self._archive(), keep_summaries_for=set(self.CATALOGUE))

        connection = self._archive()
        sliced = None
        cursor = None
        guard = 0
        while True:
            guard += 1
            self.assertLess(guard, 50, "slicing failed to terminate")
            progress = oc.sweep_archive(
                connection, keep_summaries_for=set(self.CATALOGUE),
                start_after=cursor, into=sliced, deadline=0.0,
            )
            sliced, cursor = progress.passed, progress.resume_after
            if progress.complete:
                break

        self.assertEqual(
            [row["norad"] for row in sliced.summaries],
            [row["norad"] for row in whole.summaries],
        )
        self.assertEqual(len(sliced.events), len(whole.events))
        self.assertTrue(whole.strata, "the production sweep must populate matched controls")
        self.assertEqual(sliced.strata, whole.strata)
        for counter in ("passive_intervals", "passive_flags", "payload_intervals", "payload_flags"):
            self.assertEqual(sum(getattr(s, counter) for s in whole.strata.values()), getattr(whole, counter))
        for field in (
            "objects_scanned", "objects_with_baseline", "passive_intervals",
            "passive_flags", "passive_objects", "passive_flagged_objects",
            "payload_intervals", "payload_flags", "payload_objects",
        ):
            self.assertEqual(
                getattr(sliced, field), getattr(whole, field),
                f"{field} differs between a sliced sweep and a whole one",
            )

    def test_a_slice_never_sorts_the_summaries_it_has_not_finished(self):
        """A partial ordering that looks final is how a partial pass gets published."""
        progress = oc.sweep_archive(
            self._archive(), keep_summaries_for=set(self.CATALOGUE), deadline=0.0
        )
        self.assertFalse(progress.complete)
        self.assertEqual(len(progress.passed.summaries), 1)


class SweepStateTests(unittest.TestCase):
    """The checkpoint file: what it refuses, and what it must never damage."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        root = Path(self._directory.name)
        self._state_patch = (orl.SWEEP_STATE_PATH, orl.FRAGMENT_PATH)
        orl.SWEEP_STATE_PATH = root / "orbit-sweep-state.pickle"
        orl.FRAGMENT_PATH = root / "orbit-manifest.json"
        self.addCleanup(self._restore)

    def _restore(self):
        orl.SWEEP_STATE_PATH, orl.FRAGMENT_PATH = self._state_patch
        self._directory.cleanup()

    def _write(self, **overrides):
        state = {
            "version": orl.SWEEP_STATE_VERSION,
            "kappa": 8.0,
            "catalogSize": 3,
            "startedAt": "2026-08-18T00:00:00Z",
            "resumeAfter": 42,
            "passed": oc.ArchivePass(),
        }
        state.update(overrides)
        orl._write_sweep_state(state)

    def test_a_checkpoint_round_trips(self):
        self._write()
        state = orl._read_sweep_state(self_history_kappa=8.0, catalog_size=3)
        self.assertIsNotNone(state)
        self.assertEqual(state["resumeAfter"], 42)

    def test_each_fix_flag_is_part_of_the_checkpoint_identity(self):
        for flag in oc.detector_flags():
            with self.subTest(flag=flag):
                self._write()
                with mock.patch.object(oc, flag, True):
                    self.assertIsNone(orl._read_sweep_state(self_history_kappa=8.0, catalog_size=3))

    def test_a_checkpoint_from_a_different_detector_is_refused(self):
        """Continuing across a kappa change would mix two detectors' events."""
        self._write()
        self.assertIsNone(
            orl._read_sweep_state(self_history_kappa=6.0, catalog_size=3)
        )

    def test_a_checkpoint_from_the_previous_detector_version_is_refused(self):
        # v4 -> v5 only adds tail state, so v4 is explicitly migrated. v3
        # predates the current detector and must still be refused.
        self._write(version=3)
        self.assertIsNone(
            orl._read_sweep_state(self_history_kappa=8.0, catalog_size=3)
        )

    def test_v4_preserves_an_in_flight_sweep_and_backfills_old_pass_fields(self):
        passed = oc.ArchivePass(objects_scanned=68_000)
        del passed.passive_breakdown
        del passed.payload_breakdown
        self._write(version=4, passed=passed, resumeAfter=68042)
        state = orl._read_sweep_state(self_history_kappa=8.0, catalog_size=3)
        self.assertEqual(state["version"], 5)
        self.assertEqual(state["resumeAfter"], 68042)
        self.assertEqual(state["passed"].objects_scanned, 68_000)
        self.assertEqual(state["passed"].passive_breakdown, {})
        self.assertEqual(state["passed"].payload_breakdown, {})

    def test_a_checkpoint_from_a_different_catalogue_is_refused(self):
        self._write()
        self.assertIsNone(
            orl._read_sweep_state(self_history_kappa=8.0, catalog_size=4)
        )

    def test_a_corrupt_checkpoint_starts_a_fresh_sweep_rather_than_raising(self):
        orl.SWEEP_STATE_PATH.write_bytes(b"not a pickle")
        self.assertIsNone(
            orl._read_sweep_state(self_history_kappa=8.0, catalog_size=3)
        )

    def test_the_write_is_atomic_and_leaves_no_temporary_behind(self):
        self._write()
        self.assertFalse(orl.SWEEP_STATE_PATH.with_suffix(".pickle.tmp").exists())

    def test_the_bandwidth_interval_is_measured_from_the_published_fragment(self):
        """Not from a counter of our own, which could disagree with the shards."""
        generated_at = "2026-08-18T00:00:00Z"
        orl.FRAGMENT_PATH.write_text(json.dumps(
            {"generatedAt": generated_at, "manifest": {}}
        ))
        # Derived from the same parser the production path uses, so the test
        # cannot pass because both sides share a hand-typed epoch.
        midnight = oe._parse_iso_ms(generated_at) / 1000.0
        self.assertGreater(
            orl._seconds_until_sweep_due(20 * 3600.0, now=midnight + 3600.0), 0.0
        )
        self.assertEqual(
            orl._seconds_until_sweep_due(20 * 3600.0, now=midnight + 21 * 3600.0), 0.0
        )

    def test_no_fragment_means_a_sweep_is_due_now(self):
        """A site with no orbit artifacts at all must not be told to wait 20 h."""
        self.assertEqual(orl._seconds_until_sweep_due(20 * 3600.0, now=0.0), 0.0)

    def test_a_finished_pass_parked_at_the_end_cursor_re_enters_the_tail(self):
        """A dead tail must cost the tail, not another 6 h 40 m of sweeping.

        `SWEPT_TO_END` is above every catalogue number, so a resumed sweep from
        it yields no objects and reports complete immediately -- which is how the
        next run walks straight back to the tail with the finished pass instead
        of re-sweeping to rediscover it.
        """
        self._write(resumeAfter=orl.SWEPT_TO_END)
        state = orl._read_sweep_state(self_history_kappa=8.0, catalog_size=3)
        self.assertIsNotNone(state)

        connection = ResumableSweepTests._archive(ResumableSweepTests())
        progress = oc.sweep_archive(
            connection,
            keep_summaries_for=set(ResumableSweepTests.CATALOGUE),
            start_after=state["resumeAfter"],
            into=state["passed"],
        )
        self.assertTrue(progress.complete)
        self.assertEqual(progress.objects_this_run, 0)


# ---------------------------------------------------------------------------
# The publish path, which must never scan the archive again
# ---------------------------------------------------------------------------
class CohortWindowTests(unittest.TestCase):
    def test_release_thresholds_are_lane_specific(self):
        self.assertEqual(orl.COHORT_KAPPA, 8.0)
        self.assertEqual(orl.DEFAULT_SELF_HISTORY_KAPPA, 32.0)

    def test_sweep_status_validates_the_requested_self_history_threshold(self):
        with (
            mock.patch.object(orl, "load_catalog", return_value={}),
            mock.patch.object(orl, "_read_sweep_state", return_value=None) as read,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(
                orl.main(["--sweep-status", "--self-history-kappa", "29"]), 0
            )
        read.assert_called_once_with(self_history_kappa=29.0, catalog_size=0)

    def test_bundle_routes_each_threshold_only_to_its_own_detector(self):
        scan = oc.ArchivePass()
        stats = {
            "latestEpoch": "2026-09-10T03:47:38Z",
            "lastCapture": "2026-09-04T03:47:38Z",
        }
        with (
            mock.patch.object(orl, "load_catalog", return_value={}),
            mock.patch.object(orl, "archive_stats", return_value=stats),
            mock.patch.object(orl, "load_intervals", return_value=[]) as load,
            mock.patch.object(orl, "detect_events", return_value=[]) as cohort_detect,
            mock.patch.object(orl, "control_rates", return_value={}) as cohort_control,
            mock.patch.object(
                orl.orbit_campaigns,
                "control_rates_by_object",
                side_effect=RuntimeError("stop after both controls"),
            ) as self_control,
        ):
            with self.assertRaisesRegex(RuntimeError, "stop after both controls"):
                orl.build_bundles(
                    mock.Mock(),
                    Path("unused"),
                    self_history_kappa=32.0,
                    scan=scan,
                )
        load.assert_called_once()
        self.assertEqual(cohort_detect.call_args.kwargs["kappa"], 8.0)
        self.assertEqual(cohort_control.call_args.kwargs["kappa"], 8.0)
        self_control.assert_called_once_with(scan, kappa=32.0)

    def test_event_controls_follow_the_detector_that_tripped(self):
        cohort = {"sufficientToLabel": False, "basis": "cohort"}
        self_history = {
            "kappa": 8.0,
            "sufficientToLabel": True,
            "passive": {
                "flags": 0,
                "intervals": 10_000,
                "ratePerInterval": 0.0,
                "jeffreys95": [0.0, 0.00025],
            },
            "payload": {
                "flags": 100,
                "intervals": 10_000,
                "ratePerInterval": 0.01,
                "jeffreys95": [0.008, 0.012],
            },
            "separation": {"approximatePValue": 0.0, "ratio": None},
            "targetRatePerInterval": 0.001,
            "blockingReason": None,
            "note": "measured",
        }
        self_event = {
            "objectType": "PAYLOAD",
            "tests": [{"tripped": True, "basis": "self-history"}],
        }
        cohort_event = {
            "objectType": "PAYLOAD",
            "tests": [{"tripped": True, "basis": "cohort"}],
        }
        self.assertTrue(
            orl._controls_for(self_event, cohort, self_history)["sufficientToLabel"]
        )
        self.assertFalse(
            orl._controls_for(cohort_event, cohort, self_history)["sufficientToLabel"]
        )
        policy = orl._label_policy(cohort, self_history)
        self.assertFalse(policy["manoeuvreLabelPermitted"])
        self.assertEqual(
            policy["byBasis"], {"cohort": False, "selfHistory": True}
        )
        self.assertIn("cohort detector remain candidates", policy["reason"])
        self.assertTrue(orl._event_label_permitted(self_event, self_history))
        reversed_controls = orl._controls_for(
            self_event,
            cohort,
            {
                **self_history,
                "separation": {"z": -3.2, "approximatePValue": 0.001},
            },
        )
        self.assertFalse(reversed_controls["excessSignificant"])
        self.assertFalse(
            orl._event_label_permitted(
                {**self_event, "objectType": "DEBRIS"}, self_history
            )
        )
        self.assertFalse(
            orl._event_label_permitted(
                {**self_event, "objectType": "ROCKET BODY"}, self_history
            )
        )
        self.assertFalse(
            orl._event_label_permitted(
                {**self_event, "signature": "thrust-excess"}, self_history
            )
        )

        both = orl._label_policy(
            {**cohort, "sufficientToLabel": True}, self_history
        )
        self.assertTrue(both["manoeuvreLabelPermitted"])
        self.assertIsNone(both["reason"])

    def test_forward_dated_element_epochs_do_not_move_the_cohort_window(self):
        stats = {
            "latestEpoch": "2026-09-10T03:47:38Z",
            "lastCapture": "2026-09-04T03:47:38Z",
        }
        start_ms, end_ms = orl.cohort_window_bounds(stats)
        self.assertEqual(end_ms, oe._parse_iso_ms(stats["lastCapture"]))
        self.assertEqual(end_ms - start_ms, int(orl.COHORT_WINDOW_DAYS * DAY_MS))

    def test_an_archive_without_captures_caps_its_epoch_at_wall_clock_time(self):
        now_ms = oe._parse_iso_ms("2026-09-04T03:47:38Z")
        _start_ms, end_ms = orl.cohort_window_bounds(
            {"latestEpoch": "2026-09-10T03:47:38Z", "lastCapture": None},
            now_ms=now_ms,
        )
        self.assertEqual(end_ms, now_ms)


class PublishPathTests(unittest.TestCase):
    def test_publish_reads_a_fragment_and_never_opens_the_archive(self):
        """The regression that took the live site down for four hours.

        `publish()` used to scan the whole archive on every five-minute cycle.
        This asserts it cannot: `open_archive` is replaced with something that
        raises, and the publish still succeeds.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "artifacts").mkdir()
            (root / "artifacts" / "orbit-events-abc.json").write_text("{}")
            fragment = {"generatedAt": "2026-08-07T00:00:00Z",
                        "manifest": {"orbitEvents": {"path": "artifacts/orbit-events-abc.json",
                                                     "sha256": "abc"}}}
            original_path, original_open = orl.FRAGMENT_PATH, orl.open_archive
            try:
                orl.FRAGMENT_PATH = root / "fragment.json"
                orl.FRAGMENT_PATH.write_text(json.dumps(fragment))
                orl.open_archive = lambda *a, **k: self.fail("publish() opened the archive")
                self.assertEqual(orl.publish(root)["orbitEvents"]["sha256"], "abc")
            finally:
                orl.FRAGMENT_PATH, orl.open_archive = original_path, original_open

    def test_a_fragment_naming_a_missing_artifact_is_refused(self):
        """A fragment that outlived its artifacts would 404 in a visitor's
        browser rather than error in the pipeline, which is worse."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fragment = {"manifest": {"orbitEvents": {"path": "artifacts/gone.json"}}}
            original = orl.FRAGMENT_PATH
            try:
                orl.FRAGMENT_PATH = root / "fragment.json"
                orl.FRAGMENT_PATH.write_text(json.dumps(fragment))
                self.assertEqual(orl.read_fragment(root), {})
                with self.assertRaises(FileNotFoundError):
                    orl.publish(root)
            finally:
                orl.FRAGMENT_PATH = original

    def test_a_missing_fragment_raises_so_the_caller_preserves_the_old_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            original = orl.FRAGMENT_PATH
            try:
                orl.FRAGMENT_PATH = Path(directory) / "absent.json"
                with self.assertRaises(FileNotFoundError):
                    orl.publish(Path(directory))
            finally:
                orl.FRAGMENT_PATH = original

    def test_a_stale_fragment_falls_back_to_the_published_shards(self):
        """The silent half of the degrade path.

        `build_release.py` preserves orbitEvents and orbitDrag when this module
        raises, and skips orbitHistory, because that record is a list of 256
        shards and `prior_artifact_record` cannot see inside it. The shards are
        still on disk and still correct; without this the manifest just stops
        naming them and every plot disappears for a cycle.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "artifacts").mkdir()
            (root / "artifacts" / "orbit-history-000.json").write_text("{}")
            (root / "manifest.json").write_text(json.dumps({"orbitHistory": {
                "shardCount": 1,
                "shards": [{"shard": 0, "path": "artifacts/orbit-history-000.json", "sha256": "a"}],
            }}))
            original = orl.FRAGMENT_PATH
            try:
                orl.FRAGMENT_PATH = root / "absent.json"
                kept = orl.publish(root)
                self.assertIn("orbitHistory", kept)
                self.assertEqual(len(kept["orbitHistory"]["shards"]), 1)
            finally:
                orl.FRAGMENT_PATH = original

    def test_the_fallback_refuses_records_whose_files_are_gone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({
                "orbitEvents": {"path": "artifacts/gone.json", "sha256": "a"}}))
            self.assertEqual(orl.previous_records(root), {})

    def test_sharded_records_are_checked_shard_by_shard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "artifacts").mkdir()
            (root / "artifacts" / "orbit-history-000.json").write_text("{}")
            fragment = {"manifest": {"orbitHistory": {"shards": [
                {"shard": 0, "path": "artifacts/orbit-history-000.json", "sha256": "a"},
                {"shard": 1, "path": "artifacts/orbit-history-001.json", "sha256": "b"},
            ]}}}
            original = orl.FRAGMENT_PATH
            try:
                orl.FRAGMENT_PATH = root / "fragment.json"
                orl.FRAGMENT_PATH.write_text(json.dumps(fragment))
                self.assertEqual(orl.read_fragment(root), {},
                                 "one missing shard must invalidate the fragment")
            finally:
                orl.FRAGMENT_PATH = original


# ---------------------------------------------------------------------------
# Series decimation
# ---------------------------------------------------------------------------
class HeadlineSelectionTests(unittest.TestCase):
    """The bounded cross-catalogue list, which must not become a Starlink list."""

    @staticmethod
    def _record(norad: int, cost: float, truth: bool = False) -> dict:
        return {
            "norad": norad,
            "deltaV": {"totalMetresPerSecond": cost},
            "groundTruth": {"source": "x"} if truth else None,
        }

    def test_every_object_that_moved_is_represented(self):
        records = [self._record(1, 100.0 - index) for index in range(50)]
        records += [self._record(2, 0.01), self._record(3, 0.02)]
        headline = orl.select_headline_events(records, cap=10)
        self.assertEqual({record["norad"] for record in headline}, {1, 2, 3})

    def test_a_published_manoeuvre_is_carried_however_small(self):
        """It is the one thing on the page that can be checked against somebody
        else; dropping it for being small drops the evidence the detector works."""
        records = [self._record(1, 500.0 - index) for index in range(40)]
        records.append(self._record(9, 0.0001, truth=True))
        headline = orl.select_headline_events(records, cap=5)
        self.assertIn(9, {record["norad"] for record in headline})

    def test_the_cap_is_honoured(self):
        records = [self._record(norad, float(norad)) for norad in range(1, 400)]
        self.assertEqual(len(orl.select_headline_events(records, cap=25)), 25)

    def test_nothing_is_duplicated(self):
        records = [self._record(1, 5.0, truth=True), self._record(1, 4.0)]
        headline = orl.select_headline_events(records, cap=10)
        self.assertEqual(len(headline), len({id(record) for record in headline}))


class SeriesTests(unittest.TestCase):
    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE element_set (norad INTEGER, epoch_ms INTEGER, mean_motion_q INTEGER,
                eccentricity_q INTEGER, inclination_q INTEGER, bstar_q INTEGER,
                PRIMARY KEY (norad, epoch_ms));
            CREATE TABLE element_set_daily (norad INTEGER, epoch_ms INTEGER, mean_motion_q INTEGER,
                eccentricity_q INTEGER, inclination_q INTEGER, bstar_q INTEGER,
                PRIMARY KEY (norad, epoch_ms));
            """
        )
        for epoch_ms, mm, ecc, inc, bstar in series(days=120.0, cadence_hours=3.0):
            connection.execute(
                "INSERT INTO element_set VALUES (?,?,?,?,?,?)",
                (1, epoch_ms, int(mm * 1e8), int(ecc * 1e8), int(inc * 1e4), int(bstar * 1e12)),
            )
        connection.commit()
        return connection

    def test_a_year_of_elements_is_decimated_to_something_a_plot_can_draw(self):
        raw = 120 * 8
        kept = orl.read_series(self._connection(), {1})[1]
        self.assertLess(len(kept), raw / 3)

    def test_the_neighbourhood_of_an_event_escapes_the_grid(self):
        mark = BASE_MS + int(60 * DAY_MS)
        plain = orl.read_series(self._connection(), {1})[1]
        detailed = orl.read_series(self._connection(), {1}, {1: [mark]})[1]
        self.assertGreater(len(detailed), len(plain))
        window = [s for s in detailed if abs(s["t"] - mark) < 12 * 3_600_000]
        self.assertGreaterEqual(len(window), 6, "the burn itself must not be decimated away")

    def test_a_late_arrival_does_not_reshuffle_the_whole_series(self):
        """The self-invalidating cache key, in the one place it would cost most.

        The grid must be anchored to absolute time. Anchored to "twelve hours
        since the last one I kept", a single element set arriving early moves
        every sample after it, so all 256 content-addressed shards get new
        filenames on every publish cycle and 72 MB an hour is written and
        shipped for data that did not change.
        """
        connection = self._connection()
        before = orl.read_series(connection, {1})[1]
        # One extra element set, off-grid, in the middle of the series.
        mid = before[len(before) // 2]["t"] + 3_600_000
        connection.execute(
            "INSERT OR REPLACE INTO element_set VALUES (?,?,?,?,?,?)",
            (1, mid, int(mean_motion_for(RE_WGS72 + 420.0) * 1e8), 40000, 516000, 100000000),
        )
        after = orl.read_series(connection, {1})[1]
        kept_before = {sample["t"] for sample in before}
        kept_after = {sample["t"] for sample in after}
        self.assertLessEqual(
            len(kept_before - kept_after), 1,
            "an inserted element set must not evict the samples that were already chosen",
        )

    def test_objects_not_wanted_are_not_returned(self):
        self.assertEqual(orl.read_series(self._connection(), {999}), {})


# ---------------------------------------------------------------------------
class SustainedThrust(unittest.TestCase):
    """Drag can only take energy out. A climb that keeps climbing is being pushed."""

    def test_a_decaying_object_is_not_under_thrust(self):
        verdict = oc.sustained_thrust(intervals(series(decay_metres_per_day=-137.0)))
        self.assertFalse(verdict["underThrust"])
        self.assertIn("falling", verdict["reason"])

    def test_a_steadily_raising_object_is_under_thrust_at_the_rate_it_was_given(self):
        verdict = oc.sustained_thrust(intervals(series(decay_metres_per_day=+118.0)))
        self.assertTrue(verdict["underThrust"])
        self.assertEqual(verdict["direction"], "raising")
        self.assertAlmostEqual(verdict["metresPerDay"], 118.0, delta=3.0)

    def test_a_short_history_is_declined_rather_than_guessed_at(self):
        verdict = oc.sustained_thrust(intervals(series(days=12.0, decay_metres_per_day=+118.0)))
        self.assertFalse(verdict["underThrust"])
        self.assertIn("block", verdict["reason"])

    def test_a_geostationary_object_is_outside_this_test_altogether(self):
        """An abandoned geostationary object climbs for years and burns nothing.

        The Earth's equatorial ellipticity pulls it towards a stable longitude
        at up to 140 m/day, and a month of that is indistinguishable from a
        climb. The sign argument this function rests on — drag can only take
        energy out — has no force at an altitude where drag is not acting, so
        the whole geosynchronous neighbourhood is declined by the drag-regime
        gate rather than by a bound of its own.

        Measured on the live archive, this gate is most of the difference
        between 86 false claims of sustained thrust on objects with no
        propulsion and none.
        """
        rows = series(
            a_km=42164.0, decay_metres_per_day=+90.0, eccentricity=0.0002,
            inclination_deg=0.05,
        )
        verdict = oc.sustained_thrust(intervals(rows))
        self.assertFalse(verdict["underThrust"])
        self.assertIn("drag governs", verdict["reason"])

    def test_a_molniya_stage_climbing_for_a_month_is_not_called_thrusting(self):
        """The other half of what the gate removed: highly eccentric debris.

        Twenty-two of the 86 false claims were on objects like this one, whose
        mean elements are fitted through the regime the model handles worst and
        whose orbit is moved on a scale of months by the Moon and the Sun.
        """
        rows = series(
            a_km=26600.0, decay_metres_per_day=+220.0, eccentricity=0.72,
            inclination_deg=62.5,
        )
        verdict = oc.sustained_thrust(intervals(rows), )
        self.assertFalse(verdict["underThrust"])

    def test_an_object_with_no_usable_ballistic_coefficient_is_declined(self):
        """No B*, no evidence the object is coupled to the atmosphere at all."""
        rows = [
            (epoch, mm, ecc, inc, 0.0)
            for epoch, mm, ecc, inc, _ in series(decay_metres_per_day=+118.0)
        ]
        verdict = oc.sustained_thrust(intervals(rows))
        self.assertFalse(verdict["underThrust"])
        self.assertIn("ballistic coefficient", verdict["reason"])

    def test_the_station_keeping_blind_spot_is_labelled_rather_than_hidden(self):
        """The commonest continuous thruster there is lands in the "falling" branch.

        A satellite holding altitude against drag has a net rate near zero, and
        this pass has no drag prediction to compare that against. Publishing a
        bare false there would be publishing a blank where a known blind spot
        belongs.
        """
        verdict = oc.sustained_thrust(intervals(series(decay_metres_per_day=-40.0)))
        self.assertFalse(verdict["underThrust"])
        self.assertIn("cancels its drag", verdict["gap"])

    def test_a_re_entering_object_is_never_called_thrusting(self):
        rows = series(a_km=RE_WGS72 + 180.0, decay_metres_per_day=+400.0)
        self.assertFalse(oc.sustained_thrust(intervals(rows))["underThrust"])

    def test_the_verdict_travels_on_the_object_row(self):
        rows = series(decay_metres_per_day=+118.0)
        built = intervals(rows)
        summary = oc.summarise_object(built, oc.detect_object_events(built))
        self.assertTrue(summary["sustainedThrust"]["underThrust"])


# ---------------------------------------------------------------------------
class ThrustExcess(unittest.TestCase):
    """A day on which a continuously-thrusting object thrust harder than usual.

    The step detector cannot see this and no threshold makes it able to: a
    low-thrust burn spread over a day has no discontinuity between two element
    sets. The excess only becomes measurable when the day's intervals are
    summed, because the excess adds linearly across them while the per-fit
    errors add in quadrature.
    """

    @staticmethod
    def _raising(extra_day: float | None = None, extra_metres: float = 0.0,
                 wobble: float = 0.0, days: float = 90.0):
        """A climbing series, optionally with one day of extra climb, and jitter.

        The jitter matters: without it the object's own residuals are zero, its
        measured per-fit floor collapses, and the per-interval detector would
        find anything. A real electric-propulsion object varies day to day, and
        that variation is what hides the excess from a step detector.
        """
        import random

        generator = random.Random(20260904)
        rows = []
        samples = int(days * 4.0)
        offset_m = 0.0
        a_km = RE_WGS72 + 420.0
        for index in range(samples):
            day = index * 0.25
            rate = 200.0 + (generator.uniform(-wobble, wobble) if wobble else 0.0)
            if extra_day is not None and extra_day <= day < extra_day + 1.0:
                rate += extra_metres
            offset_m += rate * 0.25
            rows.append(
                (
                    BASE_MS + int(day * DAY_MS),
                    mean_motion_for(a_km + offset_m / 1000.0),
                    0.0004,
                    51.6,
                    1e-4,
                )
            )
        return rows

    def test_a_steady_climb_produces_no_excess(self):
        """The honest null: a constant thruster has no day above its own baseline."""
        built = intervals(self._raising(wobble=60.0))
        events = oc.detect_object_events(built)
        self.assertEqual([e for e in events if e.signature == "thrust-excess"], [])

    def test_a_day_of_extra_climb_is_found_where_no_single_interval_is_a_step(self):
        """The reason the lane exists, stated as a fixture.

        The extra climb is deliberately sized so that no ONE interval of the
        day clears the per-interval detector — the assertion below checks that
        it did not, so this test cannot pass by accident on a step the old
        detector would have found anyway — while the day as a whole clears the
        day-window detector.
        """
        built = intervals(self._raising(extra_day=45.0, extra_metres=440.0, wobble=60.0))
        events = oc.detect_object_events(built)
        excess = [e for e in events if e.signature == "thrust-excess"]
        self.assertTrue(excess, "a day well above the baseline must be found")
        self.assertEqual(
            [e.signature for e in events if e.signature != "thrust-excess"], [],
            "the per-interval detector must find nothing here, or this test proves nothing",
        )
        self.assertEqual(
            oe.SIGNATURE_PROSE["thrust-excess"][0], "above its own baseline",
            "the label must not say manoeuvre",
        )
        # The cost is the EXCESS and not the whole climb: a day of baseline at
        # 200 m/day is about 0.11 m/s and must not be inside this figure.
        self.assertGreater(excess[0].delta_v.total, 0.15)
        self.assertLess(excess[0].delta_v.total, 0.4)

    def test_self_history_calibration_does_not_retune_thrust_excess(self):
        built = intervals(self._raising(extra_day=45.0, extra_metres=440.0, wobble=60.0))
        with mock.patch.object(
            oc, "thrust_excess_events", wraps=oc.thrust_excess_events
        ) as detector:
            oc.detect_object_events(built, kappa=32.0)
        detector.assert_called_once()
        self.assertEqual(
            detector.call_args.kwargs["kappa"], oc.THRUST_EXCESS_KAPPA
        )
        self.assertEqual(oc.THRUST_EXCESS_KAPPA, 8.0)

    def test_an_object_that_is_only_decaying_never_reaches_the_lane(self):
        """The structural reason this cannot fire on the passive control.

        Drag removes energy, so a spent stage cannot be found under sustained
        thrust, so the gate in front of this lane is shut for every object that
        physically cannot manoeuvre.
        """
        built = intervals(series(days=90.0, decay_metres_per_day=-137.0, ), object_type="DEBRIS")
        events = oc.detect_object_events(built)
        self.assertEqual([e for e in events if e.signature == "thrust-excess"], [])

    def test_a_single_loose_fit_is_not_an_excess(self):
        """A spike present in one element set and gone from the next is not propellant."""
        rows = self._raising(wobble=60.0)
        index = len(rows) // 2
        epoch, mm, ecc, inc, bstar = rows[index]
        from pipeline.orbit_history import semi_major_axis_km
        bumped = semi_major_axis_km(mm) + 3.0
        rows[index] = (epoch, mean_motion_for(bumped), ecc, inc, bstar)
        events = oc.detect_object_events(intervals(rows))
        self.assertEqual([e for e in events if e.signature == "thrust-excess"], [])

    def test_the_window_persistence_check_rejects_a_return_to_trend(self):
        built = intervals(self._raising(wobble=0.0))
        baselines = [
            {element: oc.baseline_at(oc._blocks_for(built, element),
                                     int(i.mid_ms // int(oc.BLOCK_DAYS * 86_400_000)))
             for element in oc.ELEMENTS}
            for i in built
        ]
        verdict = oc.window_persistence(built, baselines, 40, 43, element="semiMajorAxis")
        self.assertIn("persistent", verdict)


if __name__ == "__main__":
    unittest.main()
