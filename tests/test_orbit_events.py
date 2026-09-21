#!/usr/bin/env python3
"""Tests for orbit-change classification, cost, controls and narrative gating.

No network, no archive on disk required: every test either builds its own
in-memory SQLite archive or works on constructed `Interval` objects.

The tests are grouped by the failure each one exists to prevent, because
`docs/OPEN-WORK.md` records four defect classes this codebase has already
produced with green tests over them — green tests that never execute the
production path being the first. Where a test exercises a path that a real run
took, it says so.
"""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from pipeline import orbit_events as oe
from pipeline import orbit_narrative as on
from pipeline.orbit_history import MU_WGS72, RE_WGS72, open_archive, paged_element_sets


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def mean_motion_for(a_km: float) -> float:
    """rev/day for a given semi-major axis, the inverse of semi_major_axis_km."""
    return math.sqrt(MU_WGS72 / a_km**3) * 86400.0 / (2.0 * math.pi)


def make_interval(
    *,
    norad: int = 1,
    name: str = "TEST OBJECT",
    object_type: str = "PAYLOAD",
    a_km: float = RE_WGS72 + 550.0,
    delta_a_km: float = 0.0,
    delta_i_deg: float = 0.0,
    delta_e: float = 0.0,
    eccentricity: float = 0.0005,
    inclination_deg: float = 53.0,
    span_days: float = 0.5,
    bstar: float | None = 1e-4,
    start_ms: int = 1_754_000_000_000,
    node_residual_deg: float | None = 0.0,
    apse_residual_deg: float | None = 0.0,
) -> oe.Interval:
    """One interval, with the two angles moving by their J2 drift plus a residual.

    The residuals default to zero, which means "this orbit's node and apse line
    did exactly what the Earth's oblateness makes them do" -- the null the two
    new channels are tested against. Passing None for either leaves that angle
    unmeasured, which is what an element set read without the angle columns
    produces.
    """
    drift = oe.j2_secular_rates_deg_per_day(a_km, eccentricity, inclination_deg)
    if drift is None or node_residual_deg is None or apse_residual_deg is None:
        delta_raan = delta_argp = raan_start = argp_start = None
    else:
        raan_start, argp_start = 40.0, 120.0
        delta_raan = drift[0] * span_days + node_residual_deg
        delta_argp = drift[1] * span_days + apse_residual_deg
    return oe.Interval(
        norad=norad,
        name=name,
        object_type=object_type,
        start_ms=start_ms,
        end_ms=start_ms + int(span_days * 86_400_000),
        span_days=span_days,
        a_start_km=a_km,
        a_end_km=a_km + delta_a_km,
        delta_a_km=delta_a_km,
        delta_e=delta_e,
        delta_i_deg=delta_i_deg,
        eccentricity=eccentricity,
        inclination_deg=inclination_deg,
        perigee_altitude_km=a_km * (1.0 - eccentricity) - RE_WGS72,
        apogee_altitude_km=a_km * (1.0 + eccentricity) - RE_WGS72,
        bstar=bstar,
        mean_motion_rev_per_day=mean_motion_for(a_km),
        raan_deg=raan_start,
        arg_perigee_deg=argp_start,
        delta_raan_deg=delta_raan,
        delta_arg_perigee_deg=delta_argp,
    )


def quiet_population(count: int = 40, **kwargs) -> list[oe.Interval]:
    """A cohort of objects at the same altitude doing nothing but decaying."""
    return [
        make_interval(norad=1000 + index, delta_a_km=-0.005, **kwargs)
        for index in range(count)
    ]


def moving_series(norad: int = 77, *, follow: int = 4, span_days: float = 0.5,
                  start_ms: int = 1_754_000_000_000, **kwargs) -> list[oe.Interval]:
    """One object that moves once and then stays where it moved to.

    The residual kwargs apply to the FIRST interval only; the ones after it
    have residuals of zero, which is what "the orbit stayed rotated" looks like
    in first differences — the angle does not come back, so no later interval
    differs from its J2 prediction.

    """
    quiet = {key: 0.0 for key in ("node_residual_deg", "apse_residual_deg")}
    out = [make_interval(norad=norad, span_days=span_days, start_ms=start_ms, **kwargs)]
    for step in range(1, follow + 1):
        out.append(
            make_interval(
                norad=norad,
                span_days=span_days,
                start_ms=start_ms + int(step * span_days * 86_400_000),
                **{**kwargs, **quiet},
            )
        )
    return out


# ---------------------------------------------------------------------------
class DeltaVArithmetic(unittest.TestCase):
    """The number that turns 'something changed' into 'this cost 12 m/s'."""

    def test_tangential_matches_the_closed_form(self):
        a_km = RE_WGS72 + 550.0
        interval = make_interval(a_km=a_km, delta_a_km=1.0)
        test = oe.ChannelTest("semiMajorAxis", 1000.0, 1.0, 1000.0, None, 0, False, True)
        cost = oe.delta_v(interval, oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None), [test])
        expected = 0.5 * math.sqrt(MU_WGS72 / a_km**3) * 1000.0
        self.assertAlmostEqual(cost.tangential, expected, places=9)
        # 1 km of altitude at 550 km costs about 55 cm/s -- the teaching figure
        # in data/orbit_manoeuvre_expectations.json.
        self.assertAlmostEqual(cost.tangential, 0.547, places=2)

    def test_plane_change_is_two_hundred_times_more_expensive_per_unit(self):
        """The single most useful number for reading an orbital history."""
        a_km = RE_WGS72 + 550.0
        raise_test = oe.ChannelTest("semiMajorAxis", 1000.0, 1.0, 1000.0, None, 0, False, True)
        plane_test = oe.ChannelTest("inclination", 1.0, 1e-4, 1e4, None, 0, False, True)
        raise_cost = oe.delta_v(
            make_interval(a_km=a_km, delta_a_km=1.0),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [raise_test],
        )
        plane_cost = oe.delta_v(
            make_interval(a_km=a_km, delta_i_deg=1.0),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [plane_test],
        )
        self.assertAlmostEqual(plane_cost.plane_change, 132.4, places=0)
        self.assertGreater(plane_cost.plane_change / raise_cost.tangential, 200.0)

    def test_geo_north_south_year_matches_the_derived_budget(self):
        """0.85 deg/yr of luni-solar drift is about 46 m/s/yr to correct."""
        a_km = 42164.0
        test = oe.ChannelTest("inclination", 0.85, 1e-4, 8500.0, None, 0, False, True)
        cost = oe.delta_v(
            make_interval(a_km=a_km, inclination_deg=0.0, eccentricity=0.0, delta_i_deg=0.85),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [test],
        )
        self.assertAlmostEqual(cost.plane_change, 45.6, places=0)

    def test_an_untripped_channel_contributes_nothing_to_the_cost(self):
        """Regression: an abandoned apogee kick motor was billed 0.11 m/s.

        Its Delta-v total was dominated by an inclination residual that had
        failed its own significance test, while the tangential part it was
        actually flagged on was 0.005 m/s. Evidence and cost must come from the
        same test.
        """
        tripped = oe.ChannelTest("semiMajorAxis", 149.0, 12.4, 12.0, None, 0, False, True)
        untripped = oe.ChannelTest("inclination", 0.0021, 0.0002, 10.5, None, 0, False, False)
        cost = oe.delta_v(
            make_interval(a_km=42164.0, eccentricity=0.0001, inclination_deg=7.4),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [tripped, untripped],
        )
        self.assertEqual(cost.plane_change, 0.0)
        self.assertGreater(abs(cost.tangential), 0.0)


# ---------------------------------------------------------------------------
class NaturalFloors(unittest.TestCase):
    """Nothing is tested against zero. Every element drifts on its own."""

    def test_lunisolar_bound_recovers_the_known_geo_drift_rate(self):
        bound = oe.lunisolar_inclination_bound_deg(42164.0, 0.0, 365.25)
        self.assertAlmostEqual(bound, 0.88, places=1)

    def test_lunisolar_bound_is_zero_in_low_earth_orbit(self):
        self.assertEqual(oe.lunisolar_inclination_bound_deg(RE_WGS72 + 550.0, 53.0, 1.0), 0.0)

    def test_lunisolar_bound_grows_with_inclination(self):
        low = oe.lunisolar_inclination_bound_deg(42164.0, 0.0, 1.0)
        high = oe.lunisolar_inclination_bound_deg(42164.0, 15.0, 1.0)
        self.assertGreater(high, low)

    def test_geo_libration_bound_is_the_derived_140_metres_a_day(self):
        self.assertAlmostEqual(oe.geo_libration_bound_metres(42164.0, 0.0001, 1.0), 140.0)
        self.assertEqual(oe.geo_libration_bound_metres(RE_WGS72 + 550.0, 0.0001, 1.0), 0.0)

    def test_a_dead_geo_object_drifting_naturally_is_not_an_event(self):
        """Regression, from the live archive.

        INTELSAT 4-F1 (launched 1971, dead for decades) and the apogee kick
        motor of METEOSAT 2 were both reported as performing north-south
        station-keeping, because the inclination test ran against zero and
        luni-solar drift is a 17-sigma signal every single day.
        """
        population = [
            make_interval(
                norad=2000 + index,
                a_km=42164.0,
                eccentricity=0.0002,
                inclination_deg=7.4,
                span_days=1.0,
                bstar=None,
                delta_i_deg=0.0023,       # exactly the natural rate
                delta_a_km=0.10,          # inside the libration bound
            )
            for index in range(30)
        ]
        events = oe.detect_events(population, expectations=oe.Expectations.load())
        propulsive = [e for e in events if e.signature not in oe.NON_PROPULSIVE_SIGNATURES]
        self.assertEqual(propulsive, [])

    def test_a_real_geo_east_west_burn_is_still_found(self):
        """The bound must not be so wide that it hides the thing it protects.

        A real east-west correction is a few cm/s, which is one to three km of
        semi-major axis -- twenty times the libration bound.
        """
        population = [
            make_interval(norad=2000 + index, a_km=42164.0, eccentricity=0.0002,
                          inclination_deg=0.05, span_days=1.0, bstar=None, delta_a_km=0.05)
            for index in range(30)
        ]
        population.append(
            make_interval(norad=42662, name="TEST GEO", a_km=42164.0, eccentricity=0.0006,
                          inclination_deg=0.08, span_days=1.0, bstar=None, delta_a_km=2.152)
        )
        events = oe.detect_events(population)
        found = [e for e in events if e.norad == 42662]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].signature, "geo-east-west-keeping")
        # About 7.7 cm/s -- the size of a real geostationary longitude
        # correction, and the figure the live archive produced for CHINASAT 16.
        self.assertAlmostEqual(found[0].delta_v.total, 0.077, places=2)


# ---------------------------------------------------------------------------
class DragSeparation(unittest.TestCase):
    """Drag is predicted from B* and the population, not assumed away."""

    def test_drag_prediction_scales_with_the_ballistic_coefficient(self):
        population = [
            make_interval(norad=3000 + index, bstar=1e-4, delta_a_km=-0.010, span_days=1.0)
            for index in range(30)
        ]
        heavy = make_interval(norad=9999, bstar=3e-4, delta_a_km=-0.030, span_days=1.0)
        index = oe.CohortIndex(population + [heavy])
        prediction = oe.predict_drag(heavy, index)
        self.assertTrue(prediction.applicable)
        # Three times the B*, three times the predicted decay.
        self.assertAlmostEqual(prediction.predicted_delta_a_metres, -30.0, places=0)

    def test_a_high_area_to_mass_fragment_is_not_a_manoeuvre(self):
        """Regression: a FENGYUN 1C fragment was reported as drag make-up.

        Its B* is several times its neighbours', so it decays several times
        faster, and a cohort compared on raw decay rate calls that a burn.
        Normalising by B* is what makes it ordinary.
        """
        population = [
            make_interval(norad=3000 + index, object_type="DEBRIS", bstar=1e-4,
                          delta_a_km=-0.010, span_days=1.0)
            for index in range(30)
        ]
        fragment = make_interval(norad=31955, name="FENGYUN 1C DEB", object_type="DEBRIS",
                                 bstar=5e-4, delta_a_km=-0.050, span_days=1.0)
        events = oe.detect_events(population + [fragment])
        flagged = [
            e for e in events
            if e.norad == 31955 and e.signature not in oe.NON_PROPULSIVE_SIGNATURES
        ]
        self.assertEqual(flagged, [])

    def test_drag_cannot_raise_an_orbit_so_a_raise_needs_no_drag_model(self):
        population = [
            make_interval(norad=3000 + index, delta_a_km=-0.005, span_days=1.0, bstar=None)
            for index in range(30)
        ]
        riser = make_interval(norad=4242, delta_a_km=+1.5, span_days=1.0, bstar=None)
        events = oe.detect_events(population + [riser])
        found = [e for e in events if e.norad == 4242]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].signature, "along-track-raise")

    def test_a_fall_without_a_drag_model_is_not_claimed_as_propulsive(self):
        """The asymmetry, stated as a test.

        Falling is exactly what drag does. Without a drag prediction there is
        nothing to attribute a fall to, and the honest label says so instead of
        naming a burn.
        """
        lone = make_interval(norad=4243, delta_a_km=-1.5, span_days=1.0, bstar=None)
        events = oe.detect_events([lone] + quiet_population(count=3, span_days=1.0))
        found = [e for e in events if e.norad == 4243]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].signature, "drag-and-thrust-not-separable")
        self.assertIn(found[0].signature, oe.NON_PROPULSIVE_SIGNATURES)

    def test_terminal_decay_is_never_a_manoeuvre(self):
        """Regression: a rocket body 126 km up, losing 57 km a day on its way
        into the atmosphere, was reported as a 30 m/s disposal lowering."""
        reentering = make_interval(
            norad=20965, name="USA 67 R/B(2)", object_type="ROCKET BODY",
            a_km=RE_WGS72 + 660.0, eccentricity=0.08, delta_a_km=-56.7, span_days=0.88,
        )
        self.assertLess(reentering.perigee_altitude_km, oe.TERMINAL_DECAY_PERIGEE_KM)
        events = oe.detect_events([reentering] + quiet_population(count=30, span_days=0.88))
        found = [e for e in events if e.norad == 20965]
        self.assertTrue(all(e.signature == "re-entry-decay" for e in found))


# ---------------------------------------------------------------------------
class CohortBehaviour(unittest.TestCase):
    """The cohort is a statistical population and never a set of neighbours."""

    def test_cohort_statistic_exposes_no_membership(self):
        """The structural half of mission-speculation-design.md Section 1.6.

        A capability with no function to call cannot be invoked by a later
        refactor. If this test fails, someone has added one.
        """
        index = oe.CohortIndex(quiet_population(count=30))
        statistic = index.statistic(
            make_interval(norad=1), lambda c: c.delta_a_km, floor=1.0
        )
        self.assertIsNotNone(statistic)
        for attribute in ("members", "objects", "norads", "names", "neighbours"):
            self.assertFalse(hasattr(statistic, attribute), attribute)
        self.assertEqual(
            set(vars(statistic)), {"count", "median", "scale", "screened"}
        )

    def test_time_buckets_preserve_exact_overlap_and_do_not_duplicate_long_intervals(self):
        bucket_ms = oe.COHORT_TIME_BUCKET_HOURS * 3_600_000
        start_ms = (1_754_000_000_000 // bucket_ms) * bucket_ms + 5 * 3_600_000
        target = make_interval(norad=1, start_ms=start_ms, span_days=0.5)
        overlapping = [
            make_interval(
                norad=2000 + index,
                start_ms=start_ms - 3_600_000,
                span_days=1.0,
                delta_a_km=float(index) / 1000.0,
            )
            for index in range(8)
        ]
        non_overlapping = [
            make_interval(
                norad=3000 + index,
                start_ms=start_ms + 2 * 86_400_000,
                span_days=0.5,
                delta_a_km=10.0,
            )
            for index in range(8)
        ]
        statistic = oe.CohortIndex(overlapping + non_overlapping).statistic(
            target, lambda candidate: candidate.delta_a_km
        )
        self.assertIsNotNone(statistic)
        self.assertEqual(statistic.count, 8)
        self.assertAlmostEqual(statistic.median, 0.0035)

    def test_long_duration_class_looks_back_far_enough_to_find_overlap(self):
        target = make_interval(norad=1, span_days=0.5)
        long_overlaps = [
            make_interval(
                norad=4000 + index,
                start_ms=target.start_ms - 2 * 86_400_000,
                span_days=3.0,
                delta_a_km=float(index) / 1000.0,
            )
            for index in range(8)
        ]
        statistic = oe.CohortIndex(long_overlaps).statistic(
            target, lambda candidate: candidate.delta_a_km
        )
        self.assertIsNotNone(statistic)
        self.assertEqual(statistic.count, 8)

    def test_combined_statistics_are_identical_to_individual_queries(self):
        target = make_interval(norad=1, inclination_deg=53.0)
        population = [
            make_interval(
                norad=5000 + index,
                inclination_deg=53.0 if index < 8 else 70.0,
                delta_a_km=float(index) / 1000.0,
                bstar=1e-4 + index * 1e-6,
            )
            for index in range(16)
        ]
        index = oe.CohortIndex(population)
        semi_major = lambda candidate: oe.normalised_deviation(candidate, "semiMajorAxis")
        specific = lambda candidate: (candidate.delta_a_km / candidate.span_days) / candidate.bstar
        combined = index.statistics(
            target,
            {
                "semiMajorAxis": (semi_major, 1.0, False),
                "drag": (specific, 0.0, True),
            },
        )
        self.assertEqual(
            combined["semiMajorAxis"],
            index.statistic(target, semi_major, floor=1.0),
        )
        self.assertEqual(
            combined["drag"],
            index.statistic(target, specific, ignore_inclination=True),
        )

    def test_a_shell_that_moves_together_is_not_a_manoeuvre(self):
        """A storm bends every object in a shell at once; that is weather."""
        population = [
            make_interval(norad=5000 + index, delta_a_km=-0.4, span_days=1.0)
            for index in range(40)
        ]
        events = oe.detect_events(population)
        propulsive = [e for e in events if e.signature not in oe.NON_PROPULSIVE_SIGNATURES]
        self.assertEqual(propulsive, [])

    def test_one_object_that_departs_from_its_shell_is_found(self):
        population = [
            make_interval(norad=5000 + index, delta_a_km=-0.4, span_days=1.0)
            for index in range(40)
        ]
        population.append(make_interval(norad=6000, delta_a_km=+2.0, span_days=1.0))
        events = oe.detect_events(population)
        found = [e for e in events if e.norad == 6000]
        self.assertEqual(len(found), 1)
        self.assertNotIn(found[0].signature, oe.NON_PROPULSIVE_SIGNATURES)

    def test_two_workers_preserve_serial_events_and_order_exactly(self):
        population = [
            make_interval(
                norad=7000 + index,
                delta_a_km=(2.0 if index in (17, 68) else -0.4),
                span_days=1.0,
            )
            for index in range(80)
        ]
        serial = [event.as_dict() for event in oe.detect_events(population, workers=1)]
        parallel = [event.as_dict() for event in oe.detect_events(population, workers=2)]
        self.assertEqual(parallel, serial)

    def test_parallel_work_is_split_into_more_chunks_than_workers(self):
        """A dense second half must not leave the first worker idle."""
        self.assertGreater(oe.COHORT_PARALLEL_CHUNKS_PER_WORKER, 1)

    def test_a_very_short_interval_cannot_poison_the_cohort_scale(self):
        """Regression, from the live archive.

        Comparing raw per-day RATES let a twenty-minute interval turn a metre of
        fit noise into kilometres per day. A handful of those set the
        geostationary cohort's robust scale to about 144 km/day, against which a
        real 2.7 km/day station-keeping burn scored z = 0.02 and was discarded.
        """
        self.assertGreaterEqual(oe.MINIMUM_SPAN_DAYS, 0.05)
        long_run = make_interval(norad=7000, delta_a_km=-0.4, span_days=1.0)
        short_run = make_interval(norad=7001, delta_a_km=-0.4, span_days=0.01)
        # Normalised deviation is dimensionless and comparable; the raw rates
        # differ by a factor of a hundred.
        self.assertAlmostEqual(
            oe.normalised_deviation(long_run, "semiMajorAxis") / 1.0,
            oe.normalised_deviation(short_run, "semiMajorAxis"),
            delta=1e-9,
        )


# ---------------------------------------------------------------------------
class Controls(unittest.TestCase):
    """The measurement that decides whether anything may be called a manoeuvre."""

    def test_incomplete_beta_matches_closed_form(self):
        """Regression: the first continued fraction returned I(2,3,0.5) = 1.22.

        A cumulative distribution function cannot exceed 1, and every
        false-alarm confidence interval was built on it.
        """
        self.assertAlmostEqual(oe._regularised_incomplete_beta(2, 3, 0.5), 0.6875, places=9)
        self.assertAlmostEqual(oe._regularised_incomplete_beta(1, 1, 0.3), 0.3, places=9)
        self.assertAlmostEqual(oe._regularised_incomplete_beta(3, 1, 0.5), 0.125, places=9)
        for a, b, x in ((6.5, 143.5, 0.02), (0.5, 4.5, 0.3), (10, 2, 0.9)):
            value = oe._regularised_incomplete_beta(a, b, x)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_zero_observed_flags_does_not_claim_a_zero_rate(self):
        """The single most misleading number this module could publish."""
        low, high = oe._jeffreys_interval(0, 4)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.3)   # four trials bound almost nothing

    def test_the_interval_tightens_as_the_control_deepens(self):
        _, narrow = oe._jeffreys_interval(0, 4000)
        _, wide = oe._jeffreys_interval(0, 40)
        self.assertLess(narrow, wide)

    def test_a_thin_control_never_permits_the_manoeuvre_label(self):
        population = quiet_population(count=30)
        events = oe.detect_events(population)
        controls = oe.control_rates(population, events)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIsNotNone(controls["blockingReason"])

    def test_cohort_label_uses_the_one_per_thousand_target_not_one_percent(self):
        passive = [SimpleNamespace(object_type="DEBRIS") for _ in range(10_000)]
        payload = [SimpleNamespace(object_type="PAYLOAD") for _ in range(10_000)]
        events = [
            SimpleNamespace(signature="orbit-raising", object_type="DEBRIS")
            for _ in range(10)
        ] + [
            SimpleNamespace(signature="orbit-raising", object_type="PAYLOAD")
            for _ in range(100)
        ]
        controls = oe.control_rates(passive + payload, events)
        self.assertLess(controls["passiveControl"]["interval95"][1], 0.01)
        self.assertGreater(controls["passiveControl"]["interval95"][1], 0.001)
        self.assertFalse(controls["sufficientToLabel"])

    def test_cohort_label_also_requires_payload_separation(self):
        passive = [SimpleNamespace(object_type="DEBRIS") for _ in range(5_000)]
        payload = [SimpleNamespace(object_type="PAYLOAD") for _ in range(5_000)]
        controls = oe.control_rates(passive + payload, [])
        self.assertLess(controls["passiveControl"]["interval95"][1], 0.001)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("not yet flagged significantly", controls["blockingReason"])

        payload_events = [
            SimpleNamespace(signature="orbit-raising", object_type="PAYLOAD")
            for _ in range(50)
        ]
        separated = oe.control_rates(passive + payload, payload_events)
        self.assertTrue(separated["sufficientToLabel"])

    def test_a_detector_that_stopped_detecting_does_not_earn_the_label(self):
        """Significance is not separation, and this is how the gate is bought.

        Passive: nothing flagged in 20,000 intervals, so the false-alarm upper
        bound clears the design target comfortably. Payloads: flagged at one in
        a thousand, which at these counts is a p-value of about 8e-6 -- the
        old gate's second condition, satisfied. But the payload rate stands
        only about five times clear of the false-alarm floor once both are read
        at their bounds, so up to one flag in five on a payload could be the
        same noise. That is a detector that has bought its clean blank by
        detecting almost nothing, and it may not lend an individual event the
        word manoeuvre.
        """
        passive = [SimpleNamespace(object_type="DEBRIS") for _ in range(20_000)]
        payload = [SimpleNamespace(object_type="PAYLOAD") for _ in range(20_000)]
        events = [
            SimpleNamespace(signature="orbit-raising", object_type="PAYLOAD")
            for _ in range(20)
        ]
        controls = oe.control_rates(passive + payload, events)
        # Both of the OLD conditions pass.
        self.assertLess(controls["passiveControl"]["interval95"][1], 0.001)
        self.assertTrue(controls["excessSignificant"])
        # The gate is shut anyway, and says why in words.
        self.assertFalse(controls["sufficientToLabel"])
        self.assertLess(controls["separation"]["boundRatio"], 10.0)
        self.assertFalse(controls["separation"]["meets"])
        self.assertIn("times the false-alarm floor", controls["blockingReason"])

    def test_the_separation_gate_is_a_ratio_of_bounds_not_of_point_estimates(self):
        """Point estimates would read this control as infinitely separated."""
        verdict = oe.separation_verdict(0.0005, 0.0075)
        self.assertAlmostEqual(verdict["boundRatio"], 15.0, places=3)
        self.assertTrue(verdict["meets"])
        self.assertIsNone(verdict["gap"])
        # An unmeasured rate is a labelled gap, never a quiet pass.
        unmeasured = oe.separation_verdict(None, 0.0075)
        self.assertFalse(unmeasured["meets"])
        self.assertIsNone(unmeasured["boundRatio"])
        self.assertIn("cannot be stated", unmeasured["gap"])

    def test_the_self_history_lane_carries_the_same_separation_requirement(self):
        """The campaign scan decides on a p-value; the release layer does not.

        `orbit_campaigns.control_rates_by_object` publishes both Jeffreys
        intervals but gates on the passive upper bound and a two-proportion
        test. At 89 million control intervals that test is significant for a
        rate ratio of 1.001, so the effect size is required here, where the
        self-history control becomes what the card and the gate read.
        """
        from pipeline import orbit_release as orl

        self_controls = {
            "kappa": 32.0,
            "sufficientToLabel": True,       # what the campaign scan concluded
            "blockingReason": None,
            "passive": {"flags": 20, "intervals": 20_000, "ratePerInterval": 0.001,
                        "jeffreys95": [0.00065, 0.00155]},
            "payload": {"flags": 40, "intervals": 20_000, "ratePerInterval": 0.002,
                        "jeffreys95": [0.00148, 0.00272]},
            "separation": {"z": 2.9, "approximatePValue": 0.004, "ratio": 2.0},
            "targetRatePerInterval": 0.001,
            "note": "measured",
        }
        record = {"objectType": "PAYLOAD",
                  "tests": [{"tripped": True, "basis": "self-history"}]}
        controls = orl._controls_for(record, {"sufficientToLabel": False}, self_controls)
        self.assertFalse(controls["sufficientToLabel"])
        self.assertLess(controls["rateSeparation"]["boundRatio"], 10.0)
        self.assertIn("times the false-alarm floor", controls["blockingReason"])
        self.assertFalse(orl._event_label_permitted(record, controls))
        policy = orl._label_policy({"sufficientToLabel": False}, self_controls)
        self.assertFalse(policy["byBasis"]["selfHistory"])
        self.assertIn("times the false-alarm floor", policy["reason"])

        separated = {
            **self_controls,
            "payload": {"flags": 400, "intervals": 20_000, "ratePerInterval": 0.02,
                        "jeffreys95": [0.0182, 0.022]},
        }
        opened = orl._controls_for(record, {"sufficientToLabel": False}, separated)
        self.assertTrue(opened["sufficientToLabel"])
        self.assertTrue(orl._event_label_permitted(record, opened))

    def test_cohort_label_requires_payload_rate_to_be_higher(self):
        passive = [SimpleNamespace(object_type="DEBRIS") for _ in range(10_000)]
        payload = [SimpleNamespace(object_type="PAYLOAD") for _ in range(100_000)]
        passive_events = [
            SimpleNamespace(signature="orbit-raising", object_type="DEBRIS")
        ]
        controls = oe.control_rates(passive + payload, passive_events)
        self.assertLess(controls["excessSignificance"]["z"], 0)
        self.assertLess(controls["excessSignificance"]["approximatePValue"], 0.01)
        self.assertFalse(controls["excessSignificant"])
        self.assertFalse(controls["sufficientToLabel"])
        self.assertIn("not yet flagged significantly", controls["blockingReason"])

    def test_non_propulsive_signatures_are_not_counted_as_false_alarms(self):
        """Drag on a piece of debris is not a false alarm; it is the answer."""
        population = [
            make_interval(norad=8000 + index, object_type="DEBRIS", delta_a_km=-0.4, span_days=1.0)
            for index in range(30)
        ]
        events = oe.detect_events(population, include_drag_only=True)
        controls = oe.control_rates(population, events)
        self.assertEqual(controls["passiveControl"]["flags"], 0)

    def test_two_proportion_test_reports_insignificance_honestly(self):
        result = oe._two_proportion_z(17, 374, 2, 148)
        self.assertIsNotNone(result["z"])
        self.assertLess(abs(result["z"]), 1.96)


# ---------------------------------------------------------------------------
class GroundTruthScoring(unittest.TestCase):
    """The positive control: manoeuvres an operator published."""

    def setUp(self):
        self.truth = oe.GroundTruth(
            version="test",
            entries=[
                {"object": "IN WINDOW", "norad": 25544, "occurredAt": "2026-08-07T12:00:00Z",
                 "type": "reboost", "source": "https://example.invalid/a"},
                {"object": "BEFORE ARCHIVE", "norad": 25544, "occurredAt": "2024-05-10T12:00:00Z",
                 "type": "reboost", "source": "https://example.invalid/b"},
                {"object": "NO CATALOG NUMBER", "norad": None, "occurredAt": "2026-08-07T12:00:00Z",
                 "type": "reboost", "source": "https://example.invalid/c"},
            ],
        )
        self.start = oe._parse_iso_ms("2026-08-06T00:00:00Z")
        self.end = oe._parse_iso_ms("2026-08-08T00:00:00Z")

    def test_a_published_event_outside_the_window_is_pending_not_a_miss(self):
        """Scoring a 2024 burn against a 2026 archive scores the calendar."""
        score = oe.score_against_ground_truth(
            [], self.truth, archive_start_ms=self.start, archive_end_ms=self.end
        )
        reasons = {entry["reason"] for entry in score["pendingEvents"]}
        self.assertIn("outside-archive-window", reasons)
        self.assertIn("no-catalog-number-published", reasons)
        self.assertEqual(score["inArchiveWindow"], 1)
        self.assertEqual(score["notDetected"], 1)

    def test_a_detected_event_is_matched_and_carries_its_citation(self):
        event = oe.OrbitEvent(
            norad=25544, name="ISS (ZARYA)", object_type="PAYLOAD",
            start_ms=oe._parse_iso_ms("2026-08-07T10:00:00Z"),
            end_ms=oe._parse_iso_ms("2026-08-07T14:00:00Z"),
            signature="along-track-raise", confidence="candidate",
            delta_v=oe.DeltaV(0.5, 0.0, 0.0, 0.5, 0.0, 500.0),
            drag=oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            tests=[], expectation={}, regime="LEO",
            perigee_altitude_km=410.0, apogee_altitude_km=420.0, inclination_deg=51.6,
        )
        score = oe.score_against_ground_truth(
            [event], self.truth, archive_start_ms=self.start, archive_end_ms=self.end
        )
        self.assertEqual(score["detected"], 1)
        self.assertEqual(score["detectionRate"], 1.0)
        self.assertEqual(score["matches"][0]["source"], "https://example.invalid/a")

    def test_a_missing_truth_table_degrades_rather_than_raising(self):
        truth = oe.GroundTruth.load(oe.ROOT / "data" / "does-not-exist.json")
        self.assertEqual(truth.entries, [])


# ---------------------------------------------------------------------------
class OpacityGate(unittest.TestCase):
    """docs/mission-speculation-design.md Sections 1.3 to 1.5."""

    def test_opaque_designators_are_denied(self):
        for name in ("USA 326", "TJS-19", "COSMOS 2560", "SHIYAN 12 02", "YAOGAN-36 03C",
                     "NROL-44", "OBJECT E", "UNKNOWN 1"):
            self.assertTrue(oe.opacity_denied(name, "unknown", "other", "low"), name)

    def test_the_gate_is_symmetric_with_respect_to_nationality(self):
        """A rule about evidence, not a rule about sensitivity."""
        self.assertTrue(oe.opacity_denied("USA 326", "military", "other", "high"))
        self.assertTrue(oe.opacity_denied("COSMOS 2560", "military", "other", "high"))

    def test_ordinary_objects_keep_their_purpose_language(self):
        for name in ("SENTINEL-2A", "ISS (ZARYA)", "STARLINK-4105", "GOES 18"):
            self.assertFalse(oe.opacity_denied(name, "civil", "earth-observation", "high"), name)

    def test_an_unrelated_name_starting_with_a_denied_token_is_not_captured(self):
        self.assertFalse(oe.opacity_denied("COSMOSPHERE DEMO", "civil", "technology", "high"))
        self.assertFalse(oe.opacity_denied("USAT 1", "commercial", "communications", "high"))

    def test_a_denied_object_still_gets_every_physical_number(self):
        """Absence must be indistinguishable from ordinary absence (Section 1.5).

        The gate removes purpose language. It must not remove the physics, and
        it must not add a badge.
        """
        population = quiet_population(count=30, span_days=1.0)
        population.append(
            make_interval(norad=63924, name="TJS-19", delta_a_km=2.0, span_days=1.0)
        )
        events = oe.detect_events(
            population, catalog={63924: {"sector": "military", "mission": "other"}}
        )
        found = next(e for e in events if e.norad == 63924)
        self.assertTrue(found.opaque)
        record = found.as_dict()
        self.assertFalse(record["purposeLanguagePermitted"])
        self.assertGreater(record["deltaV"]["totalMetresPerSecond"], 0)
        self.assertNotIn("withheld", str(record).lower())
        self.assertNotIn("redact", str(record).lower())

    def test_the_evidence_sheet_omits_mission_fields_for_a_denied_object(self):
        """A field that is not in the prompt cannot be leaked by a model."""
        record = {"purposeLanguagePermitted": False, "signature": "along-track-raise",
                  "expectation": {"class": "Low Earth orbit payload"},
                  "catalog": {"mission": "communications"}, "constellation": "Starlink"}
        sheet = on.evidence_sheet(record, {})
        self.assertNotIn("mission", sheet)
        self.assertNotIn("constellation", sheet)
        self.assertNotIn("objectClass", sheet)


# ---------------------------------------------------------------------------
class Expectations(unittest.TestCase):
    """Sean's insight, in code: what is ordinary depends on the object."""

    def setUp(self):
        self.expectations = oe.Expectations.load()

    def test_a_passive_object_can_never_be_expected_to_manoeuvre(self):
        interval = make_interval(object_type="ROCKET BODY")
        match = self.expectations.match(interval, {})
        verdict = oe.score_against_expectation(
            interval, "along-track-raise",
            oe.DeltaV(0.1, 0, 0, 0.1, 0, 100), match,
        )
        self.assertEqual(verdict["verdict"], "impossible-for-class")

    def test_a_starlink_raising_its_orbit_is_ordinary(self):
        interval = make_interval(name="STARLINK-4105")
        match = self.expectations.match(interval, {})
        self.assertEqual(match["id"], "starlink")
        verdict = oe.score_against_expectation(
            interval, "along-track-raise", oe.DeltaV(0.5, 0, 0, 0.5, 0, 900), match
        )
        self.assertEqual(verdict["verdict"], "expected-for-class")

    def test_thrust_excess_is_explicitly_ordinary_for_electric_propulsion_fleets(self):
        for name in ("STARLINK-4105", "ONEWEB-0123"):
            interval = make_interval(name=name)
            match = self.expectations.match(interval, {})
            self.assertIn("thrust-excess", match["ordinarySignatures"])
            verdict = oe.score_against_expectation(
                interval, "thrust-excess", oe.DeltaV(0.5, 0, 0, 0.5, 0, 900), match
            )
            self.assertEqual(verdict["verdict"], "expected-for-class")

    def test_an_oversized_burn_is_flagged_even_when_the_type_is_ordinary(self):
        interval = make_interval(name="STARLINK-4105")
        match = self.expectations.match(interval, {})
        verdict = oe.score_against_expectation(
            interval, "along-track-raise", oe.DeltaV(50, 0, 0, 50, 0, 90000), match
        )
        self.assertEqual(verdict["verdict"], "larger-than-typical")

    def test_inclination_change_is_ordinary_only_for_a_sun_synchronous_orbit(self):
        """A sun-synchronous operator adjusts inclination as maintenance,
        because the nodal rate depends on it. Nobody else does."""
        sso = make_interval(a_km=RE_WGS72 + 550.0, inclination_deg=97.79)
        self.assertTrue(oe.sun_synchronous(sso.a_start_km, sso.eccentricity, sso.inclination_deg))
        match = self.expectations.match(sso, {})
        self.assertEqual(match["id"], "sun-synchronous-imager")
        self.assertIn("inclination-change", match["ordinarySignatures"])

        ordinary = make_interval(a_km=RE_WGS72 + 550.0, inclination_deg=53.0, name="NOT SSO")
        match = self.expectations.match(ordinary, {})
        self.assertNotIn("inclination-change", match["ordinarySignatures"])

    def test_the_sun_synchronous_rate_is_the_textbook_one(self):
        self.assertTrue(oe.sun_synchronous(RE_WGS72 + 800.0, 0.001, 98.6))
        self.assertFalse(oe.sun_synchronous(RE_WGS72 + 800.0, 0.001, 53.0))

    def test_every_expectation_entry_carries_a_citation(self):
        for entry in self.expectations.classes:
            self.assertTrue(entry.get("citations"), entry.get("id"))


# ---------------------------------------------------------------------------
class DeterministicNarrative(unittest.TestCase):
    """The fallback has to be publishable on its own, or the model is gating."""

    def make_record(self, **overrides):
        record = {
            "norad": 53168, "name": "STARLINK-4105", "objectType": "PAYLOAD",
            "signature": "along-track-lower",
            "signatureLabel": "in-plane lowering", "regime": "LEO",
            "startAt": "2026-08-07T06:03:31Z", "endAt": "2026-08-07T18:00:02Z",
            "perigeeAltitudeKm": 534.4, "inclinationDeg": 53.16,
            "deltaV": {"totalMetresPerSecond": 3.2085, "planeChangeMetresPerSecond": 0.0},
            "drag": {"applicable": True, "predictedDeltaAMetres": -397.7,
                     "predictedSigmaMetres": 229.5, "propulsiveDeltaAMetres": -5843.5},
            "tests": [{"element": "semiMajorAxis", "delta": -5843.5, "floorSigma": 229.5,
                       "cohortZ": -37.0, "cohortCount": 16, "cohortScreened": False,
                       "tripped": True}],
            "expectation": {"verdict": "expected-for-class", "class": "Starlink"},
            "spaceWeather": {"kpMax": None},
            "constellation": "Starlink", "sunSynchronous": False,
        }
        record.update(overrides)
        return record

    def setUp(self):
        self.controls = {
            "passiveControl": {"flags": 2, "intervals": 148, "interval95": [0.0028, 0.0426]},
            "excessSignificance": {"z": 1.756},
            "excessSignificant": False,
        }

    def test_the_card_carries_evidence_floor_control_and_alternatives(self):
        card = on.describe(self.make_record(), self.controls)
        for section in ("observation", "cost", "control", "alternatives", "honesty", "footer"):
            self.assertTrue(card[section], section)
        self.assertIn("floor", card["observation"])
        self.assertIn("lower bound", card["cost"])
        self.assertIn("cannot manoeuvre", card["honesty"])

    def test_the_card_never_claims_confirmation(self):
        """The headline says "inferred, not confirmed" on purpose, so the test
        looks for the CLAIM forms rather than the word."""
        text = json_text(on.describe(self.make_record(), self.controls)).lower()
        for phrase in ("is confirmed", "confirms", "we know that", "proves", "certainly",
                       "definitely", "was commanded", "was ordered"):
            self.assertNotIn(phrase, text, phrase)
        self.assertIn("inferred, not confirmed", text)

    def test_the_card_never_predicts_a_re_entry_date(self):
        card = on.describe(
            self.make_record(signature="re-entry-decay", signatureLabel="re-entry decay"),
            self.controls,
        )
        text = json_text(card).lower()
        self.assertNotIn("will re-enter", text)
        self.assertNotIn("predicted to", text)

    def test_the_card_says_so_when_there_was_no_cohort(self):
        record = self.make_record()
        record["tests"][0]["cohortZ"] = None
        card = on.describe(record, self.controls)
        self.assertIn("not enough objects", card["control"])

    def test_the_honesty_line_reports_the_measured_control(self):
        card = on.describe(self.make_record(), self.controls)
        self.assertIn("148", card["honesty"])
        self.assertIn("not yet statistically significant", card["honesty"])

    def test_the_honesty_line_does_not_call_a_negative_difference_an_excess(self):
        controls = {
            **self.controls,
            "excessSignificance": {"z": -3.2, "approximatePValue": 0.001},
        }
        card = on.describe(self.make_record(), controls)
        self.assertIn("payloads is lower", card["honesty"])
        self.assertIn("required positive separation is absent", card["honesty"])
        self.assertNotIn("payloads is higher", card["honesty"])

    def test_an_event_whose_own_control_passed_earns_manoeuvre_but_not_confirmation(self):
        controls = {
            "passiveControl": {
                "flags": 0,
                "intervals": 10_000,
                "interval95": [0.0, 0.00025],
            },
            "excessSignificance": {"z": 9.0, "approximatePValue": 0.0},
            "excessSignificant": True,
            "sufficientToLabel": True,
        }
        record = self.make_record(manoeuvreLabelPermitted=True)
        card = on.describe(record, controls)
        self.assertIn("This is a manoeuvre inferred", card["honesty"])
        self.assertIn("earns the word manoeuvre", card["honesty"])
        self.assertIn("inferred, not confirmed", card["headline"])
        self.assertNotIn("This is a candidate", card["honesty"])

    def test_an_event_specific_refusal_overrides_a_passing_lane(self):
        controls = {
            "passiveControl": {
                "flags": 0,
                "intervals": 10_000,
                "interval95": [0.0, 0.00025],
            },
            "excessSignificance": {"z": 9.0, "approximatePValue": 0.0},
            "excessSignificant": True,
            "sufficientToLabel": True,
        }
        card = on.describe(
            self.make_record(
                objectType="DEBRIS",
                manoeuvreLabelPermitted=False,
                expectation={"verdict": "impossible-for-class", "class": "debris"},
            ),
            controls,
        )
        # The claim is stated at the strength of its warrant: the catalogue's
        # classification, which is strong evidence and not a proof, because a
        # catalogue entry can be wrong or stale.
        self.assertIn("The catalogue lists this object", card["honesty"])
        self.assertIn("on the strength of that classification", card["honesty"])
        self.assertIn("an entry can be wrong or out of date", card["honesty"])
        self.assertNotIn("by construction", card["honesty"])
        # ...and the refusal it licenses is not weakened by the hedge.
        self.assertIn("can never lend the word manoeuvre", card["honesty"])
        self.assertNotIn("earns the word manoeuvre", card["honesty"])

    def test_the_card_names_the_detector_that_judged_the_event(self):
        """`controlBasis` is published on every record; the reader sees it here.

        Two detectors with separate blanks both write "the detector flagged N
        of M". Without the basis the reader cannot tell which instrument's
        false-alarm rate is being quoted at them.
        """
        self_card = on.describe(
            self.make_record(controlBasis="self-history"), self.controls
        )
        self.assertIn("judges each object against its own past", self_card["honesty"])
        cohort_card = on.describe(
            self.make_record(controlBasis="cohort"), self.controls
        )
        self.assertIn("against its neighbours", cohort_card["honesty"])
        # No basis on the record: say "the detector", never guess one.
        plain = on.describe(self.make_record(), self.controls)
        self.assertIn("the detector that judged this event", plain["honesty"])
        self.assertNotIn("own past", plain["honesty"])
        sheet = on.evidence_sheet(
            self.make_record(controlBasis="self-history"), self.controls
        )
        self.assertEqual(sheet["falseAlarmControl"]["basis"], "self-history")


def json_text(value) -> str:
    import json

    return json.dumps(value)


# ---------------------------------------------------------------------------
class NarrativeGate(unittest.TestCase):
    """What the model is allowed to say, enforced in code rather than in a prompt."""

    def setUp(self):
        self.event = {
            "norad": 53168, "startAt": "2026-08-07T06:03:31Z", "endAt": "2026-08-07T18:00:02Z",
            "signature": "along-track-lower", "regime": "LEO",
            "drag": {"propulsiveDeltaAMetres": -5843.5},
            "expectation": {"verdict": "expected-for-class"},
            "spaceWeather": {"kpMax": None}, "constellation": "Starlink",
            "sunSynchronous": False,
        }
        self.key = on.event_key(self.event)

    def candidate(self, text: str, caveat: str = "This reading is drawn only from public elements and cannot separate a burn from a fitting artefact."):
        return {
            "eventKey": self.key,
            "text": text,
            "caveat": caveat,
            "generatedAt": "2026-08-07T23:00:00Z",
        }

    def now(self):
        import datetime as dt

        return dt.datetime(2026, 8, 7, 23, 30, tzinfo=dt.timezone.utc)

    def accepts(self, candidate) -> bool:
        return on.validate_candidate(candidate, self.event, now=self.now()) is not None

    GOOD = (
        "The published elements show the semi-major axis falling by more than atmospheric drag "
        "accounts for, with the plane essentially unchanged. The evidence is consistent with a "
        "deliberate in-plane lowering rather than a fitting artefact."
    )

    def test_a_well_formed_hedged_narrative_is_accepted(self):
        self.assertTrue(self.accepts(self.candidate(self.GOOD)))

    def test_a_number_in_digits_is_rejected(self):
        self.assertFalse(self.accepts(self.candidate(self.GOOD + " It cost 3 m/s.")))

    def test_a_number_spelled_out_is_rejected(self):
        """Banning digits alone is not enough; the model spells it instead."""
        self.assertFalse(
            self.accepts(self.candidate(self.GOOD + " It fell by about six kilometres."))
        )

    def test_an_unhedged_claim_is_rejected(self):
        self.assertFalse(
            self.accepts(
                self.candidate(
                    "The operator lowered the orbit with a retrograde burn, reducing the "
                    "semi-major axis well below where drag alone would have taken it."
                )
            )
        )

    def test_the_word_confirmed_is_rejected(self):
        self.assertFalse(
            self.accepts(self.candidate(self.GOOD + " This is confirmed by the elements."))
        )

    def test_a_cause_that_was_never_computed_is_rejected(self):
        """The core rule: the model may only phrase what code put on the list."""
        self.assertNotIn("sun-synchronous-maintenance", on.candidate_causes(self.event))
        self.assertFalse(
            self.accepts(
                self.candidate(
                    self.GOOD + " This appears to hold the local solar time of the orbit."
                )
            )
        )

    def test_a_storm_cause_is_rejected_when_no_storm_was_recorded(self):
        self.assertNotIn("storm-driven-drag", on.candidate_causes(self.event))
        self.assertFalse(
            self.accepts(
                self.candidate(self.GOOD + " A geomagnetic storm likely drove this.")
            )
        )

    def test_a_storm_cause_is_offered_when_kp_was_actually_raised(self):
        event = dict(self.event, signature="along-track-raise",
                     spaceWeather={"kpMax": 6.0})
        self.assertIn("storm-driven-drag", on.candidate_causes(event))

    def test_relational_language_is_rejected(self):
        """No evidence about any second object was ever computed, so a model
        using this language is inventing it, not repeating it."""
        self.assertFalse(
            self.accepts(
                self.candidate(self.GOOD + " It appears to be working with another satellite.")
            )
        )

    def test_mission_language_is_rejected(self):
        self.assertFalse(
            self.accepts(
                self.candidate(self.GOOD + " The evidence suggests a surveillance role.")
            )
        )

    def test_a_direction_that_contradicts_the_numbers_is_rejected(self):
        self.assertFalse(
            self.accepts(
                self.candidate(
                    "The published elements suggest the spacecraft raised its orbit well above "
                    "where drag alone would have left it, which is consistent with a prograde burn."
                )
            )
        )

    def test_a_narrative_for_a_different_event_is_rejected(self):
        candidate = self.candidate(self.GOOD)
        candidate["eventKey"] = "9999|x|y|z"
        self.assertFalse(self.accepts(candidate))

    def test_a_narrative_written_before_a_reclassification_is_rejected(self):
        candidate = self.candidate(self.GOOD)
        reclassified = dict(self.event, signature="deorbit-lowering")
        self.assertIsNone(on.validate_candidate(candidate, reclassified, now=self.now()))

    def test_a_stale_narrative_is_rejected(self):
        import datetime as dt

        stale = dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc)
        self.assertIsNone(on.validate_candidate(self.candidate(self.GOOD), self.event, now=stale))

    def test_a_caveat_echoed_from_the_input_is_rejected(self):
        """Observed live in the space-weather brief: asked for a caveat about
        its own reading, the model returned one from its input."""
        echoed = on.CAUSE_VOCABULARY["fit-artefact"]["detail"]
        self.assertFalse(self.accepts(self.candidate(self.GOOD, caveat=echoed)))

    def test_an_impossible_object_is_offered_only_the_artefact_explanation(self):
        event = dict(self.event, expectation={"verdict": "impossible-for-class"})
        self.assertEqual(on.candidate_causes(event), ["fit-artefact"])


# ---------------------------------------------------------------------------
class ArchiveIntegration(unittest.TestCase):
    """End to end over a real, in-memory archive. No files, no network."""

    def test_load_intervals_reads_a_real_schema(self):
        """Deliberately runs the production query against the production schema.

        The first of the four defect classes in docs/OPEN-WORK.md is a green
        test that never executes the production path. Constructed `Interval`
        objects exercise none of the SQL, the quantisation, or the per-object
        grouping, so this one uses `open_archive` itself.
        """
        connection = open_archive(_memory_path())
        try:
            self._seed(connection)
            intervals = oe.load_intervals(connection)
            self.assertEqual(len(intervals), 1)
            interval = intervals[0]
            self.assertEqual(interval.norad, 25544)
            self.assertEqual(interval.name, "ISS (ZARYA)")
            self.assertAlmostEqual(interval.span_days, 1.0, places=6)
            self.assertAlmostEqual(interval.delta_a_km, 1.0, places=2)
            self.assertAlmostEqual(interval.bstar, 2.5e-4, places=9)
        finally:
            connection.close()

    def test_the_epoch_window_still_selects_exactly_what_sql_selected(self):
        """`since_ms`/`until_ms` moved out of SQL and into Python on 2026-08-08.

        They had to: the scan is now paged, and `LIMIT` counts rows that
        survive the WHERE clause, so a 45-day window over a 22-year archive
        would make a single "page" walk most of the table — reinstating the
        long lock the paging exists to remove. Nothing about which rows are
        selected may change with it, and the boundaries are where that would
        show, so every combination of both edges is checked against the query
        the old code ran.
        """
        connection = open_archive(_memory_path())
        try:
            base = 1_700_000_000_000
            for norad in (10, 20, 30):
                connection.execute(
                    "INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)",
                    (norad, f"O{norad}", "X", "PAYLOAD", "S", "US", "2020-01-01", 0, 0),
                )
                for index in range(20):
                    connection.execute(
                        "INSERT INTO element_set VALUES (?,?,?,?,?,0,0,0,?,0,0,0,0)",
                        (norad, base + index * 86_400_000,
                         int((15.5 + 1e-6 * index) * 1e8), 12_340, 530_500, 123),
                    )
            connection.commit()

            def with_sql(since, until):
                query = ("SELECT norad, epoch_ms, mean_motion_q, eccentricity_q, "
                         "inclination_q, bstar_q FROM element_set")
                clauses, params = [], []
                if since is not None:
                    clauses.append("epoch_ms >= ?"), params.append(since)
                if until is not None:
                    clauses.append("epoch_ms <= ?"), params.append(until)
                if clauses:
                    query += " WHERE " + " AND ".join(clauses)
                return list(connection.execute(query + " ORDER BY norad, epoch_ms", params))

            def with_python(since, until):
                return [
                    row
                    for row in paged_element_sets(connection, page_rows=7)
                    if (since is None or row[1] >= since)
                    and (until is None or row[1] <= until)
                ]

            edges = (None, base - 1, base, base + 9 * 86_400_000,
                     base + 19 * 86_400_000, base + 10**12)
            for since in edges:
                for until in edges:
                    with self.subTest(since=since, until=until):
                        self.assertEqual(with_python(since, until), with_sql(since, until))

            # And the shipped function, not just the row source underneath it.
            self.assertEqual(len(oe.load_intervals(connection)), 57)
            self.assertEqual(
                len(oe.load_intervals(connection, since_ms=base + 10 * 86_400_000)), 27
            )
        finally:
            connection.close()

    def test_observation_span_uses_the_capture_ledger_not_the_epochs(self):
        """Regression, from the live archive.

        After one hour of capture the epoch span read as seventeen days,
        because one snapshot contains epochs days old and occasionally epochs
        stamped in the future. Every maturity decision keyed on it was wrong.
        """
        connection = open_archive(_memory_path())
        try:
            self._seed(connection)
            connection.execute(
                "INSERT INTO capture(captured_ms, source, records_read, elements_new, "
                "objects_seen, rejected) VALUES (?,?,?,?,?,?)",
                (1_754_000_000_000, "test", 2, 2, 1, 0),
            )
            connection.execute(
                "INSERT INTO capture(captured_ms, source, records_read, elements_new, "
                "objects_seen, rejected) VALUES (?,?,?,?,?,?)",
                (1_754_003_600_000, "test", 2, 0, 1, 2),
            )
            connection.commit()
            span = oe.observation_span_days(connection)
            self.assertAlmostEqual(span, 3_600_000 / 86_400_000, places=6)
            maturity = oe.archive_maturity(connection, oe.load_intervals(connection))
            self.assertLess(maturity["observationSpanDays"], 1.0)
            self.assertFalse(
                next(c for c in maturity["capabilities"]
                     if c["id"] == "measured-false-alarm-rate")["available"]
            )
        finally:
            connection.close()

    @staticmethod
    def _seed(connection):
        a0 = RE_WGS72 + 410.0
        for offset, a_km in ((0, a0), (86_400_000, a0 + 1.0)):
            connection.execute(
                "INSERT INTO element_set(norad, epoch_ms, mean_motion_q, eccentricity_q, "
                "inclination_q, raan_q, arg_perigee_q, mean_anomaly_q, bstar_q, ingest_hour) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    25544,
                    1_754_000_000_000 + offset,
                    round(mean_motion_for(a_km) * 1e8),
                    round(0.0004 * 1e8),
                    round(51.6 * 1e4),
                    0, 0, 0,
                    round(2.5e-4 * 1e12),
                    0,
                ),
            )
        connection.execute(
            "INSERT INTO object(norad, name, object_type, first_seen_ms, last_seen_ms) "
            "VALUES (?,?,?,?,?)",
            (25544, "ISS (ZARYA)", "PAYLOAD", 0, 0),
        )
        connection.commit()


# ---------------------------------------------------------------------------
class TheNodeAndTheApseLine(unittest.TestCase):
    """The two elements the archive stored and the detector ignored.

    Every test here exists to stop one specific thing: a channel that reports
    the Earth's own oblateness as a manoeuvre. That failure would not be
    subtle — nodal regression in low Earth orbit is about a degree a day
    against a catalogue scatter of 1e-4 degrees — and it would fire on every
    object in the catalogue on every interval.
    """

    def test_the_two_j2_implementations_agree(self):
        """`orbit_history.j2_secular_rates` and this module's must not drift apart.

        One takes a whole ElementSet, the other three scalars, and both are on
        the read path of a shipped detector. Pinned across a sun-synchronous
        orbit, a Molniya orbit at the critical inclination, and a
        near-geostationary one.
        """
        from pipeline.orbit_history import ElementSet, j2_secular_rates

        for a_km, ecc, inc in (
            (RE_WGS72 + 800.0, 0.001, 98.6),
            (26600.0, 0.74, 63.4),
            (42164.0, 0.0002, 5.0),
        ):
            element = ElementSet(
                norad=1, epoch_ms=0, mean_motion=mean_motion_for(a_km), eccentricity=ecc,
                inclination=inc, raan=0.0, arg_perigee=0.0, mean_anomaly=0.0,
                bstar=0.0, ndot=0.0, nddot=0.0, rev_at_epoch=0,
            )
            expected = j2_secular_rates(element)
            measured = oe.j2_secular_rates_deg_per_day(a_km, ecc, inc)
            self.assertAlmostEqual(measured[0], expected[0], places=9)
            self.assertAlmostEqual(measured[1], expected[1], places=9)

    def test_the_critical_inclination_stops_the_apse_line(self):
        """63.4 degrees is where J2 leaves the apse line alone. Molniya is flown there."""
        _, argp_dot = oe.j2_secular_rates_deg_per_day(26600.0, 0.74, 63.4349)
        self.assertLess(abs(argp_dot), 1e-3)

    def test_ordinary_nodal_regression_is_not_a_manoeuvre(self):
        """The failure this whole design exists to prevent.

        A sun-synchronous orbit's node regresses about a degree a day. Fed the
        raw element difference, a channel would see ten thousand sigma of it on
        every interval of every object.
        """
        interval = make_interval(
            a_km=RE_WGS72 + 800.0, inclination_deg=98.6, eccentricity=0.001
        )
        self.assertAlmostEqual(interval.raan_residual_deg, 0.0, places=12)
        self.assertGreater(abs(interval.delta_raan_deg), 0.4)
        index = oe.CohortIndex([interval] + quiet_population(
            a_km=RE_WGS72 + 800.0, inclination_deg=98.6, eccentricity=0.001
        ))
        previous = oe.APSIDAL_CHANNEL_ENABLED
        oe.APSIDAL_CHANNEL_ENABLED = True
        try:
            tests = oe.angle_channels(interval, index, kappa=oe.DEFAULT_KAPPA)
        finally:
            oe.APSIDAL_CHANNEL_ENABLED = previous
        self.assertEqual([t.element for t in tests], ["raan", "argPerigee"])
        self.assertFalse(any(t.tripped for t in tests))

    def test_a_plane_rotation_that_leaves_a_e_and_i_alone_is_found(self):
        """The manoeuvre the detector was blind to before: a pure node change."""
        population = quiet_population(count=40, inclination_deg=53.0)
        mover = moving_series(inclination_deg=53.0, node_residual_deg=0.5)
        events = oe.detect_events(mover + population)
        found = [e for e in events if e.norad == 77]
        self.assertEqual([e.signature for e in found], ["node-change"])
        # And it is charged as a plane change, not as anything in-plane.
        self.assertGreater(found[0].delta_v.plane_change, 40.0)
        self.assertEqual(found[0].delta_v.tangential, 0.0)

    def test_the_apse_line_channel_ships_disabled(self):
        """It raised the passive-control rate, so it is off. That is the rule.

        Measured over a seven-day window of the live archive the channel took
        the passive control from 47 flags to 58 on objects that cannot
        manoeuvre, and the cohort screen did not save it — the fourteen tripped
        tests had cohort z-scores from 8.5 to 147. The constant is asserted
        here so that switching it on is a deliberate act with a failing test in
        front of it, rather than a line someone flips while reading.
        """
        self.assertFalse(oe.APSIDAL_CHANNEL_ENABLED)
        self.assertTrue(oe.NODE_CHANNEL_ENABLED)

    def test_an_apsidal_rotation_is_found_when_the_channel_is_switched_on(self):
        """The channel works; it is off because of what it also finds."""
        population = quiet_population(count=40, eccentricity=0.02, inclination_deg=53.0)
        mover = moving_series(
            eccentricity=0.02, inclination_deg=53.0, apse_residual_deg=0.3
        )
        previous = oe.APSIDAL_CHANNEL_ENABLED
        oe.APSIDAL_CHANNEL_ENABLED = True
        try:
            events = oe.detect_events(mover + population)
        finally:
            oe.APSIDAL_CHANNEL_ENABLED = previous
        found = [e for e in events if e.norad == 77]
        self.assertEqual([e.signature for e in found], ["apsidal-change"])
        self.assertGreater(found[0].delta_v.apsidal, 0.0)

    def test_the_apse_line_channel_is_not_opened_on_a_circular_orbit(self):
        """The argument of perigee is not defined for a circle; the fit wanders."""
        interval = make_interval(eccentricity=1e-5, apse_residual_deg=90.0)
        index = oe.CohortIndex([interval] + quiet_population(eccentricity=1e-5))
        previous = oe.APSIDAL_CHANNEL_ENABLED
        oe.APSIDAL_CHANNEL_ENABLED = True
        try:
            elements = [t.element for t in oe.angle_channels(interval, index, kappa=8.0)]
        finally:
            oe.APSIDAL_CHANNEL_ENABLED = previous
        self.assertNotIn("argPerigee", elements)

    def test_neither_angle_channel_trips_without_a_cohort_behind_it(self):
        """Six of the eight node false alarms on the control had no cohort at all.

        The floors these channels use bound some of the ways an angle moves for
        free, not all of them, and the cohort is the only control that sees the
        rest. A test is still emitted, so the reader can tell a channel that
        declined from a channel that was never opened.
        """
        lonely = make_interval(
            norad=99, a_km=RE_WGS72 + 4000.0, eccentricity=0.3, inclination_deg=27.0,
            node_residual_deg=5.0,
        )
        index = oe.CohortIndex([lonely])
        tests = oe.angle_channels(lonely, index, kappa=8.0)
        self.assertEqual([t.element for t in tests], ["raan"])
        self.assertIsNone(tests[0].cohort_z)
        self.assertFalse(tests[0].tripped)

    def test_the_node_channel_is_not_opened_on_the_geostationary_ring(self):
        """The node is not defined for an equatorial orbit either."""
        interval = make_interval(
            a_km=42164.0, inclination_deg=0.05, eccentricity=0.0002, node_residual_deg=30.0
        )
        index = oe.CohortIndex([interval] + quiet_population(
            a_km=42164.0, inclination_deg=0.05, eccentricity=0.0002
        ))
        elements = [t.element for t in oe.angle_channels(interval, index, kappa=8.0)]
        self.assertNotIn("raan", elements)

    def test_an_interval_without_the_angle_columns_is_judged_on_what_it_has(self):
        interval = make_interval(node_residual_deg=None, apse_residual_deg=None)
        index = oe.CohortIndex([interval] + quiet_population())
        self.assertFalse(interval.angles_measured)
        self.assertEqual(oe.angle_channels(interval, index, kappa=8.0), [])

    def test_the_node_floor_grows_as_the_orbit_flattens(self):
        """sigma / sin i, because (i, RAAN sin i) is the well-conditioned pair."""
        steep = oe.natural_floor(make_interval(inclination_deg=90.0), "raan")
        shallow = oe.natural_floor(make_interval(inclination_deg=5.0), "raan")
        self.assertGreater(shallow, 5.0 * steep)

    def test_the_apse_floor_grows_as_the_orbit_rounds(self):
        """sigma_e / e, because the fit determines the eccentricity VECTOR."""
        eccentric = oe.natural_floor(make_interval(eccentricity=0.1), "argPerigee")
        rounder = oe.natural_floor(make_interval(eccentricity=0.002), "argPerigee")
        self.assertGreater(rounder, 10.0 * eccentric)

    def test_the_node_channel_is_held_to_a_stricter_kappa_than_its_neighbours(self):
        """Read off the control curve, not off a distribution.

        Over one release window the channel's largest z on any object with no
        propulsion was 9.6, and its payload tail ran to 47.8. A multiple of
        1.5 puts the bar at 12 when the module runs at its usual kappa of 8:
        clear of the passive tail with a margin, and 41 payload detections
        still standing. Asserted here as a multiple rather than as a bare 12,
        because a run at another operating point has to move both together or
        the single kappa the controls report stops meaning anything.
        """
        self.assertEqual(oe.NODE_CHANNEL_KAPPA_MULTIPLIER, 1.5)
        floor = oe.natural_floor(make_interval(inclination_deg=53.0), "raan")
        # Ten floors of node residual: over the bar the other three channels
        # are held to, under the one this channel is held to.
        interval = make_interval(inclination_deg=53.0, node_residual_deg=10.0 * floor)
        index = oe.CohortIndex([interval] + quiet_population(inclination_deg=53.0))
        at_module_kappa = oe.angle_channels(interval, index, kappa=oe.DEFAULT_KAPPA)
        self.assertFalse(at_module_kappa[0].tripped)
        without_the_multiple = oe.angle_channels(
            interval, index, kappa=oe.DEFAULT_KAPPA / oe.NODE_CHANNEL_KAPPA_MULTIPLIER
        )
        self.assertTrue(without_the_multiple[0].tripped)

    def test_a_node_crossing_zero_has_not_moved_three_hundred_and_fifty_nine_degrees(self):
        pair = oe.interval_from_pair(
            1, "X", "PAYLOAD",
            (0, 15.0, 0.001, 53.0, 1e-4, 359.9, 10.0),
            (86_400_000 // 2, 15.0, 0.001, 53.0, 1e-4, 0.1, 10.0),
        )
        self.assertAlmostEqual(pair.delta_raan_deg, 0.2, places=6)


# ---------------------------------------------------------------------------
class PlaneAndApseArithmetic(unittest.TestCase):
    """The two new cost terms, against their closed forms."""

    def test_a_node_change_alone_costs_two_v_sin_i_sin_half(self):
        a_km = RE_WGS72 + 800.0
        interval = make_interval(a_km=a_km, inclination_deg=98.6, eccentricity=0.0)
        test = oe.ChannelTest("raan", 1.0, 1e-4, 1e4, None, 0, False, True)
        cost = oe.delta_v(
            interval, oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None), [test]
        )
        speed = math.sqrt(MU_WGS72 / a_km) * 1000.0
        expected = (
            2.0 * speed * abs(math.sin(math.radians(98.6))) * math.sin(math.radians(1.0) / 2.0)
        )
        self.assertAlmostEqual(cost.plane_change, expected, places=6)

    def test_a_node_change_at_the_pole_is_free_and_at_the_equator_is_not(self):
        """sin i is the whole content of the node term, and it is a real physical fact."""
        self.assertAlmostEqual(oe.plane_rotation_deg(90.0, 90.0, 1.0), 1.0, places=6)
        self.assertLess(oe.plane_rotation_deg(1.0, 1.0, 1.0), 0.02)

    def test_the_plane_rotation_reduces_to_the_inclination_change_exactly(self):
        """Regression: the arccosine form invented a microdegree out of rounding.

        With no node change the combined rotation must be the inclination
        change to the last bit, or every event whose plane channels did not
        trip is billed for a plane change that did not happen.
        """
        self.assertEqual(oe.plane_rotation_deg(7.4, 7.4, 0.0), 0.0)
        self.assertAlmostEqual(oe.plane_rotation_deg(53.0, 54.0, 0.0), 1.0, places=12)

    def test_an_apse_rotation_costs_two_e_root_mu_over_p_sin_half(self):
        interval = make_interval(a_km=26600.0, eccentricity=0.74, inclination_deg=63.4)
        test = oe.ChannelTest("argPerigee", 1.0, 1e-4, 1e4, None, 0, False, True)
        cost = oe.delta_v(
            interval, oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None), [test]
        )
        p_km = 26600.0 * (1.0 - 0.74**2)
        expected = (
            2.0 * 0.74 * math.sqrt(MU_WGS72 / p_km) * 1000.0
            * math.sin(math.radians(1.0) / 2.0)
        )
        self.assertAlmostEqual(cost.apsidal, expected, places=6)
        # One degree of apse-line rotation on a Molniya ellipse is about 74 m/s,
        # which is why a Molniya orbit is flown at the critical inclination and
        # lets J2 leave its apse line alone instead of paying to hold it.
        self.assertAlmostEqual(cost.apsidal, 74.3, places=0)

    def test_an_untripped_angle_channel_contributes_nothing(self):
        """The same discipline the inclination channel already had."""
        tripped = oe.ChannelTest("semiMajorAxis", 149.0, 12.4, 12.0, None, 0, False, True)
        node = oe.ChannelTest("raan", 5.0, 1e-4, 5e4, None, 0, False, False)
        apse = oe.ChannelTest("argPerigee", 5.0, 1e-4, 5e4, None, 0, False, False)
        cost = oe.delta_v(
            make_interval(a_km=26600.0, eccentricity=0.74, inclination_deg=63.4),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [tripped, node, apse],
        )
        self.assertEqual(cost.plane_change, 0.0)
        self.assertEqual(cost.apsidal, 0.0)

    def test_a_plane_rotation_can_never_break_the_physical_ceiling(self):
        """And that is a derivation, not luck, so it is worth pinning.

        The plane term is `2 V_apogee sin(theta/2)`, which is at most
        `2 V_apogee`; the ceiling is `2 V_perigee`; and apogee speed is never
        greater than perigee speed. So the guard cannot fire on a plane
        rotation alone, however large — a half-turn of the plane is expensive
        but it is not impossible, and a bound that rejected it would be wrong.
        """
        test = oe.ChannelTest("raan", 180.0, 1e-4, 1e6, None, 0, False, True)
        cost = oe.delta_v(
            make_interval(a_km=RE_WGS72 + 550.0, inclination_deg=90.0, eccentricity=0.01),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [test],
        )
        self.assertIsNone(cost.implausible)
        self.assertGreater(cost.plane_change, 14_000.0)

    def test_the_physical_ceiling_still_guards_the_total_that_now_holds_them(self):
        """The guard is on the total, and the total now has two more terms in it."""
        absurd = oe.ChannelTest("semiMajorAxis", 5.0e7, 1.0, 5.0e7, None, 0, False, True)
        node = oe.ChannelTest("raan", 10.0, 1e-4, 1e5, None, 0, False, True)
        cost = oe.delta_v(
            make_interval(a_km=RE_WGS72 + 550.0, inclination_deg=90.0),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [absurd, node],
        )
        self.assertIsNotNone(cost.implausible)

    def test_a_large_node_change_is_flagged_as_beyond_routine(self):
        """The operational flag reaches the new channels as well as the old ones."""
        test = oe.ChannelTest("raan", 20.0, 1e-4, 2e5, None, 0, False, True)
        cost = oe.delta_v(
            make_interval(a_km=RE_WGS72 + 550.0, inclination_deg=90.0),
            oe.DragPrediction(False, "x", 0.0, 0.0, None, 0, None),
            [test],
        )
        self.assertIsNone(cost.implausible)
        self.assertIsNotNone(cost.beyond_routine)


def _memory_path():
    """A throwaway on-disk archive under the test's own temp directory.

    `open_archive` runs PRAGMAs and a schema script that an in-memory URI
    handles fine, but it also calls `mkdir` on the parent, so a real path keeps
    the production code path intact rather than special-casing it for tests.
    """
    import tempfile

    directory = tempfile.mkdtemp(prefix="orbit-events-test-")
    from pathlib import Path

    return Path(directory) / "archive.sqlite3"


if __name__ == "__main__":
    unittest.main()
