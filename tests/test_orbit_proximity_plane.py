"""Offline tests for T8b's plane-matching instrument.

Every test names the section of `docs/proximity-leo-preregistration-20260922.md`
it holds the implementation to. Nothing here touches the archive: the physics
is checked against hand computations and against numerical integration, and
the detector is checked against synthetic element series built in this file.
"""

from __future__ import annotations

import inspect
import json
import re
import math
import unittest
from pathlib import Path

import numpy as np

from tools import proximity_plane as pp

_REPO = Path(__file__).resolve().parents[1]

MU = 398600.4418
RE = 6378.137
DAY_MS = 86400000.0


def synth(norad, days, a_km, ecc, inc_deg, raan0_deg, argp_deg=0.0,
          ma0_deg=0.0, start_ms=1.5e12, cadence_days=0.5,
          a_schedule=None, inc_schedule=None, ma_offset=None):
    """A synthetic element series propagated with the J2 nodal regression of
    prereg 2.3 and the object's own mean motion. `a_schedule` and
    `inc_schedule` are callables of elapsed days that override a and i, which
    is how a manoeuvre is injected."""
    t = np.arange(0.0, days, cadence_days)
    a = np.full(t.size, float(a_km))
    inc = np.full(t.size, float(inc_deg))
    if a_schedule is not None:
        a = np.asarray([a_schedule(x) for x in t], dtype=np.float64)
    if inc_schedule is not None:
        inc = np.asarray([inc_schedule(x) for x in t], dtype=np.float64)
    e = np.full(t.size, float(ecc))
    rate = pp.j2_nodal_rate_deg_per_day(a, e, inc)
    raan = np.empty(t.size)
    raan[0] = raan0_deg
    if t.size > 1:
        raan[1:] = raan0_deg + np.cumsum(0.5 * (rate[1:] + rate[:-1])
                                         * np.diff(t))
    n = pp.mean_motion_rev_day(a)
    ma = np.empty(t.size)
    ma[0] = ma0_deg
    if t.size > 1:
        ma[1:] = ma0_deg + np.cumsum(360.0 * 0.5 * (n[1:] + n[:-1]) * np.diff(t))
    if ma_offset is not None:
        ma = ma + np.asarray([ma_offset(x) for x in t], dtype=np.float64)
    return {
        "epoch_ms": (start_ms + t * DAY_MS).astype(np.int64),
        "n": n, "e": e, "inc": inc,
        "raan": pp.wrap360(raan), "argp": np.full(t.size, float(argp_deg)),
        "ma": pp.wrap360(ma),
        "regime": np.full(t.size, pp.REGIME_CODE["LEO"], dtype=np.uint8),
    }


NO_FLAGS = {"all_ms": np.asarray([], dtype=np.float64),
            "plane_ms": np.asarray([], dtype=np.float64)}


class TestPlaneGeometry(unittest.TestCase):
    """prereg 2.1."""

    def test_orbit_normal_hand_computed(self):
        # equatorial prograde: the normal is +z
        np.testing.assert_allclose(pp.orbit_normal(0.0, 137.0),
                                   [0.0, 0.0, 1.0], atol=1e-12)
        # polar with RAAN 0: h = (0, -1, 0)
        np.testing.assert_allclose(pp.orbit_normal(90.0, 0.0),
                                   [0.0, -1.0, 0.0], atol=1e-12)
        # polar with RAAN 90: h = (1, 0, 0)
        np.testing.assert_allclose(pp.orbit_normal(90.0, 90.0),
                                   [1.0, 0.0, 0.0], atol=1e-12)
        # i = 60, RAAN = 30
        i, o = math.radians(60.0), math.radians(30.0)
        np.testing.assert_allclose(
            pp.orbit_normal(60.0, 30.0),
            [math.sin(i) * math.sin(o), -math.sin(i) * math.cos(o), math.cos(i)],
            atol=1e-12)

    def test_half_angle_and_cosine_forms_agree(self):
        rng = np.random.default_rng(7)
        ia = rng.uniform(0.1, 179.9, 400)
        ib = ia + rng.normal(0.0, 3.0, 400)
        oa = rng.uniform(0.0, 360.0, 400)
        ob = oa + rng.normal(0.0, 5.0, 400)
        np.testing.assert_allclose(
            pp.plane_separation_deg(ia, oa, ib, ob),
            pp.plane_separation_from_cosine_deg(ia, oa, ib, ob), atol=1e-7)

    def test_theta_is_never_below_delta_inclination(self):
        rng = np.random.default_rng(11)
        ia = rng.uniform(5.0, 175.0, 500)
        ib = rng.uniform(5.0, 175.0, 500)
        dom = rng.uniform(-180.0, 180.0, 500)
        theta = pp.plane_separation_deg(ia, 0.0, ib, -dom)
        self.assertTrue(np.all(theta >= np.abs(ia - ib) - 1e-9))

    def test_equality_exactly_at_zero_relative_raan(self):
        for ia, ib in ((53.0, 53.1), (98.6, 97.4), (63.4, 63.4)):
            self.assertAlmostEqual(
                float(pp.plane_separation_deg(ia, 37.0, ib, 37.0)),
                abs(ia - ib), places=10)

    def test_half_angle_form_is_accurate_at_small_theta(self):
        # a 0.001 deg separation the cosine form cannot resolve cleanly
        theta = float(pp.plane_separation_deg(53.0, 0.0, 53.0, 0.001 / math.sin(
            math.radians(53.0))))
        self.assertGreater(theta, 0.0)
        self.assertLess(abs(theta - 0.001), 2e-6)

    def test_cross_track_scale(self):
        self.assertAlmostEqual(
            float(pp.cross_track_km(0.2, pp.REF_LEO_A_KM)), 24.01, places=1)


class TestJ2(unittest.TestCase):
    """prereg 2.3."""

    def test_sun_synchronous_condition(self):
        rate = float(pp.j2_nodal_rate_deg_per_day(RE + 800.0, 0.0, 98.6))
        self.assertAlmostEqual(rate, 0.9856, delta=0.002)

    def test_anchor_values_from_the_registration(self):
        self.assertAlmostEqual(
            float(pp.j2_nodal_rate_deg_per_day(RE + 300.0, 0.0, 0.0)),
            -8.483, delta=0.002)
        self.assertAlmostEqual(
            float(pp.j2_nodal_rate_deg_per_day(RE + 500.0, 0.0, 53.0)),
            -4.605, delta=0.002)

    def test_derivative_against_a_numerical_one(self):
        a, e, i = RE + 500.0, 0.001, 53.0
        h = 1e-3
        num = (float(pp.j2_nodal_rate_deg_per_day(a + h, e, i))
               - float(pp.j2_nodal_rate_deg_per_day(a - h, e, i))) / (2 * h)
        self.assertAlmostEqual(float(pp.j2_nodal_rate_d_da(a, e, i)), num,
                               places=9)

    def test_registered_differential_number(self):
        val = abs(float(pp.j2_nodal_rate_d_da(RE + 500.0, 0.0, 53.0)))
        self.assertAlmostEqual(val, 0.002343, delta=2e-6)
        # 100 km buys 0.234 deg/day, the registration's headline arithmetic
        self.assertAlmostEqual(val * 100.0, 0.2343, delta=2e-4)

    def test_retrograde_node_advances(self):
        self.assertGreater(
            float(pp.j2_nodal_rate_deg_per_day(RE + 800.0, 0.0, 100.0)), 0.0)


class TestChanceCoplanarity(unittest.TestCase):
    """prereg 2.4 -- and the T8a failure this must not repeat."""

    def test_half_width_is_none_when_inclinations_are_too_far_apart(self):
        self.assertIsNone(pp.chance_coplanar_half_width_deg(0.2, 53.0, 53.5))

    def test_registered_worked_example(self):
        half = pp.chance_coplanar_half_width_deg(0.2, 53.0, 53.0)
        self.assertAlmostEqual(half, 0.2505, delta=5e-4)
        self.assertAlmostEqual(
            pp.chance_coplanar_dwell_days(0.2, 53.0, 53.0, 0.0167), 30.0,
            delta=0.1)

    def test_dwell_uses_the_supplied_own_rate_and_computes_none_itself(self):
        src = inspect.getsource(pp.chance_coplanar_dwell_days)
        self.assertNotIn("j2_nodal_rate", src)

    def test_zero_relative_nodal_rate_is_permanent(self):
        self.assertEqual(
            pp.chance_coplanar_dwell_days(0.2, 53.0, 53.0, 0.0), math.inf)

    def test_rate_relation(self):
        self.assertAlmostEqual(pp.chance_coplanar_rate_per_day(0.36), 0.002,
                               places=12)

    def test_dwell_bound_holds_for_a_numerically_integrated_j2_pair(self):
        """The bound is the thing T8a got wrong by measuring a nominal rather
        than an own quantity. Here it is checked against an integrated pair."""
        a_a, a_b = RE + 500.0, RE + 507.0
        inc = 53.0
        ra = float(pp.j2_nodal_rate_deg_per_day(a_a, 0.0, inc))
        rb = float(pp.j2_nodal_rate_deg_per_day(a_b, 0.0, inc))
        d_rate = ra - rb
        t = np.arange(0.0, 400.0, 0.05)
        theta = pp.plane_separation_deg(inc, ra * t, inc, rb * t - 0.30)
        inside = theta <= 0.2
        runs = pp.contiguous_runs(inside)
        self.assertTrue(runs)
        longest = max(t[e - 1] - t[s] for s, e in runs)
        bound = pp.chance_coplanar_dwell_days(0.2, inc, inc, d_rate)
        self.assertLessEqual(longest, bound * 1.02)
        self.assertGreater(longest, bound * 0.5)


class TestPhasing(unittest.TestCase):
    """prereg 2.5."""

    def test_registered_phase_rate_constant(self):
        self.assertAlmostEqual(
            float(pp.phase_rate_deg_per_day_per_km(RE + 500.0)),
            -1.19487, delta=1e-5)

    def test_registered_confinement_bound(self):
        self.assertAlmostEqual(
            pp.phase_confinement_da_km(5.0, 30.0, RE + 500.0), 0.1395,
            delta=1e-4)

    def test_bound_against_a_propagated_pair(self):
        """A pair offset by exactly the bound must sweep exactly Gamma in D."""
        a0 = RE + 500.0
        da = pp.phase_confinement_da_km(5.0, 30.0, a0)
        n_a = float(pp.mean_motion_rev_day(a0 + da))
        n_b = float(pp.mean_motion_rev_day(a0))
        swept = abs(360.0 * (n_a - n_b) * 30.0)
        self.assertAlmostEqual(swept, 5.0, delta=0.02)

    def test_tightest_registered_arm_implies_metres(self):
        # prereg 4.2: Gamma = 0.2085 deg at D = 30 d implies ~7 m
        self.assertAlmostEqual(
            1000.0 * pp.phase_confinement_da_km(0.2085, 30.0, RE + 500.0),
            5.8, delta=0.7)


class TestRegimes(unittest.TestCase):
    """prereg 3.1."""

    def test_bins(self):
        n = np.asarray([15.2, 2.0036, 1.0027, 2.0345, 16.5])
        e = np.asarray([0.001, 0.001, 0.0002, 0.7386, 0.0])
        i = np.asarray([53.0, 55.0, 0.05, 63.4, 51.6])
        codes = pp.regime_of(n, e, i)
        self.assertEqual(pp.REGIME_NAME[int(codes[0])], "LEO")
        self.assertEqual(pp.REGIME_NAME[int(codes[1])], "MEO")
        self.assertEqual(pp.REGIME_NAME[int(codes[2])], "nearGEO")
        self.assertEqual(pp.REGIME_NAME[int(codes[3])], "HEO")

    def test_near_geo_band_is_t8a_verbatim(self):
        self.assertEqual(pp.NEAR_GEO_MM, (0.95, 1.05))
        self.assertEqual(pp.NEAR_GEO_ECC, 0.01)
        self.assertEqual(pp.NEAR_GEO_INC_DEG, 25.0)

    def test_decaying_is_excluded(self):
        a = RE + 60.0
        n = float(pp.mean_motion_rev_day(a))
        self.assertEqual(pp.REGIME_NAME[int(pp.regime_of(
            np.asarray([n]), np.asarray([0.0]), np.asarray([51.6]))[0])],
            "decaying")

    def test_class_label_reads_only_object_type(self):
        self.assertEqual(pp.class_label("PAYLOAD"), "payload")
        self.assertEqual(pp.class_label("DEBRIS"), "catalogue_passive")
        self.assertEqual(pp.class_label("ROCKET BODY"), "catalogue_passive")
        self.assertIsNone(pp.class_label("UNKNOWN"))
        self.assertIsNone(pp.class_label(None))


class TestFastAngle(unittest.TestCase):
    """prereg 5.1."""

    def test_series_agrees_with_newton_for_small_eccentricity(self):
        m = np.linspace(0.0, 359.0, 200)
        for e in (0.0, 0.001, 0.01):
            np.testing.assert_allclose(pp.true_anomaly_deg(m, e),
                                       pp.true_anomaly_series_deg(m, e),
                                       atol=2e-3)

    def test_newton_solves_kepler(self):
        for e in (0.0, 0.1, 0.5, 0.74):
            for m in (0.0, 37.0, 180.0, 300.0):
                nu = float(pp.true_anomaly_deg(m, e))
                ea = 2.0 * math.atan2(
                    math.sqrt(1 - e) * math.sin(math.radians(nu) / 2),
                    math.sqrt(1 + e) * math.cos(math.radians(nu) / 2))
                back = math.degrees(ea - e * math.sin(ea)) % 360.0
                self.assertAlmostEqual(back, m % 360.0, places=6)

    def test_position_vector_is_unit_and_matches_geometry(self):
        r = pp.position_unit_vector(53.0, 20.0, 15.0, 100.0)
        self.assertAlmostEqual(float(np.linalg.norm(r)), 1.0, places=12)
        # at u = 0 the satellite is at the ascending node
        r0 = pp.position_unit_vector(53.0, 20.0, 0.0, 0.0)
        np.testing.assert_allclose(
            r0, [math.cos(math.radians(20.0)), math.sin(math.radians(20.0)), 0.0],
            atol=1e-12)

    def test_track_angle(self):
        a = pp.position_unit_vector(53.0, 0.0, 0.0, 0.0)
        b = pp.position_unit_vector(53.0, 0.0, 0.0, 30.0)
        self.assertAlmostEqual(float(pp.track_angle_deg(a, b)), 30.0, places=8)

    def test_fast_angle_is_refused_across_a_gap_longer_than_one_day(self):
        el_a = synth(1, 40.0, RE + 500.0, 0.001, 53.0, 0.0, cadence_days=0.5)
        el_b = synth(2, 40.0, RE + 500.0, 0.001, 53.0, 0.0, cadence_days=0.5)
        # punch a 3-day hole in B
        keep = ~((el_b["epoch_ms"] > el_b["epoch_ms"][10])
                 & (el_b["epoch_ms"] < el_b["epoch_ms"][10] + int(3 * DAY_MS)))
        el_b = {k: v[keep] for k, v in el_b.items()}
        ps = pp.pair_series(el_a, el_b, el_a["epoch_ms"][0], el_a["epoch_ms"][-1])
        self.assertIsNotNone(ps)
        self.assertFalse(np.all(ps["gamma_ok"]))
        inside_hole = ((ps["t_ms"] > el_b["epoch_ms"][10] + 1.2 * DAY_MS)
                       & (ps["t_ms"] < el_b["epoch_ms"][10] + 1.8 * DAY_MS))
        if inside_hole.any():
            self.assertFalse(bool(ps["gamma_ok"][inside_hole].any()))


class TestScreenAdmissibility(unittest.TestCase):
    """prereg 8.1."""

    def test_grid_step_is_half_the_dwell(self):
        self.assertEqual(pp.screen_grid_step_days(30.0), 15.0)
        self.assertEqual(pp.screen_grid_step_days(14.0), 7.0)

    def test_any_dwell_contains_two_consecutive_grid_points(self):
        """The counting argument the screen rests on, checked exhaustively."""
        for d in (14.0, 30.0, 60.0):
            step = pp.screen_grid_step_days(d)
            grid = np.arange(-1000.0, 1000.0, step)
            for start in np.linspace(0.0, step, 41):
                inside = (grid >= start) & (grid <= start + d)
                self.assertGreaterEqual(int(inside.sum()), 2)
                idx = np.nonzero(inside)[0]
                self.assertTrue(np.any(np.diff(idx) == 1))

    def test_da_window_is_generous(self):
        self.assertAlmostEqual(
            pp.screen_da_window_km(5.0, 30.0, RE + 500.0),
            1.5 * pp.phase_confinement_da_km(5.0, 30.0, RE + 500.0), places=12)

    def test_screen_keeps_a_close_pair_and_drops_a_far_one(self):
        a = np.asarray([7000.0, 7000.05, 7100.0])
        inc = np.asarray([53.0, 53.0, 53.0])
        raan = np.asarray([10.0, 10.1, 10.0])
        idx = np.arange(3, dtype=np.int64)
        li, ri = pp.screen_epoch_cpu(a, inc, raan, idx, a, inc, raan, idx,
                                     0.2, 0.209)
        got = {tuple(sorted(p)) for p in zip(li.tolist(), ri.tolist())}
        self.assertIn((0, 1), got)
        self.assertNotIn((0, 2), got)

    def test_screen_never_pairs_an_object_with_itself(self):
        a = np.asarray([7000.0, 7000.01])
        inc = np.asarray([53.0, 53.0])
        raan = np.asarray([10.0, 10.0])
        idx = np.asarray([4, 4], dtype=np.int64)     # same object, two rows
        li, ri = pp.screen_epoch_cpu(a, inc, raan, idx, a, inc, raan, idx,
                                     0.2, 0.209)
        self.assertEqual(li.size, 0)

    def test_screen_drops_a_pair_whose_inclinations_are_too_far_apart(self):
        a = np.asarray([7000.0, 7000.02])
        inc = np.asarray([53.0, 53.5])
        raan = np.asarray([10.0, 10.0])
        idx = np.arange(2, dtype=np.int64)
        li, _ = pp.screen_epoch_cpu(a, inc, raan, idx, a, inc, raan, idx,
                                    0.2, 0.209)
        self.assertEqual(li.size, 0)

    def test_gpu_chunk_stays_inside_the_registered_device_pool(self):
        # the widest screening epoch the LEO catalogue can present
        self.assertLessEqual(pp.gpu_chunk_bytes(40000, 1, 8, 8),
                             pp.GPU_POOL_LIMIT_BYTES)
        self.assertGreater(pp.gpu_chunk_bytes(40000, 40000, 8, 8),
                           pp.GPU_POOL_LIMIT_BYTES)


class TestDetector(unittest.TestCase):
    """prereg 5.4, 3.4."""

    def test_a_quiet_object_produces_no_flag(self):
        el = synth(1, 400.0, RE + 500.0, 0.001, 53.0, 0.0)
        d = pp.detect_manoeuvres(el, 1e-7, 1e-4)
        self.assertEqual(d["intrack"].size, 0)
        self.assertEqual(d["plane"].size, 0)

    def test_an_in_track_burn_is_flagged(self):
        # a real burn is smeared over a day or two by the element fits, so the
        # synthetic one is a two-day ramp rather than an instantaneous step
        el = synth(1, 400.0, RE + 500.0, 0.001, 53.0, 0.0,
                   a_schedule=lambda t: RE + 500.0 + 5.0 * min(
                       1.0, max(0.0, (t - 200.0) / 2.0)))
        d = pp.detect_manoeuvres(el, 1e-7, 1e-4)
        self.assertGreater(d["intrack"].size, 0)
        flagged = el["epoch_ms"][d["intrack"]] - el["epoch_ms"][0]
        self.assertTrue(np.any(np.abs(flagged / DAY_MS - 200.0) <= 1.5))

    def test_an_inclination_burn_is_flagged_on_the_plane_channel(self):
        el = synth(1, 400.0, RE + 500.0, 0.001, 53.0, 0.0,
                   inc_schedule=lambda t: 53.0 + 0.4 * min(
                       1.0, max(0.0, (t - 200.0) / 2.0)))
        d = pp.detect_manoeuvres(el, 1e-7, 1e-4)
        self.assertGreater(d["plane"].size, 0)

    def test_drag_alone_does_not_fire_the_in_track_channel(self):
        """The own-drag floor of prereg 5.4 is the anti-repeat of T8a's
        nominal-rather-than-own failure: a fast decayer must not be flagged
        for decaying."""
        el = synth(1, 400.0, RE + 300.0, 0.001, 51.6, 0.0,
                   a_schedule=lambda t: RE + 300.0 - 0.35 * t)
        d = pp.detect_manoeuvres(el, 1e-7, 1e-4)
        self.assertEqual(d["intrack"].size, 0)

    def test_a_single_bad_fit_does_not_fire_either_channel(self):
        el = synth(1, 400.0, RE + 500.0, 0.001, 53.0, 0.0)
        el = {k: v.copy() for k, v in el.items()}
        el["inc"][300] += 2.0
        el["n"][300] += 1e-3
        d = pp.detect_manoeuvres(el, 1e-7, 1e-4)
        self.assertEqual(d["intrack"].size, 0)
        self.assertEqual(d["plane"].size, 0)

    def test_the_in_track_floor_is_fifty_metres_of_semi_major_axis(self):
        self.assertEqual(pp.DA_FLOOR_KM, 0.050)

    def test_the_plane_floor_is_the_tle_resolution(self):
        self.assertEqual(pp.I_FLOOR_DEG, 0.01)

    def test_control_evidence_requirement(self):
        self.assertEqual(pp.CONTROL_MIN_ELEMENT_SETS, 200)
        self.assertEqual(pp.CONTROL_MIN_SPAN_DAYS, 365.0)

    def test_never_manoeuvred_excludes_an_object_with_a_synthetic_burn(self):
        """prereg 3.4: the control is manoeuvre history, not object_type."""
        quiet = synth(1, 400.0, RE + 500.0, 0.001, 53.0, 0.0)
        burned = synth(2, 400.0, RE + 500.0, 0.001, 53.0, 0.0,
                       a_schedule=lambda t: RE + 500.0 + 5.0 * min(
                           1.0, max(0.0, (t - 200.0) / 2.0)))
        dq = pp.detect_manoeuvres(quiet, 1e-7, 1e-4)
        db = pp.detect_manoeuvres(burned, 1e-7, 1e-4)
        self.assertTrue(dq["intrack"].size == 0 and dq["plane"].size == 0)
        self.assertFalse(db["intrack"].size == 0 and db["plane"].size == 0)


class TestCalibrationAndStatistics(unittest.TestCase):
    def test_second_difference_annihilates_a_linear_trend(self):
        t = np.arange(50.0)
        np.testing.assert_allclose(pp.second_difference(3.0 + 0.7 * t), 0.0,
                                   atol=1e-12)

    def test_mad_sigma(self):
        rng = np.random.default_rng(3)
        x = rng.normal(0.0, 2.0, 20000)
        self.assertAlmostEqual(pp.mad_sigma(x, 1.0), 2.0, delta=0.1)

    def test_theil_sen_ignores_a_gross_outlier(self):
        t = np.arange(50.0)
        y = 3.0 + 0.25 * t
        y[7] = 900.0
        self.assertAlmostEqual(pp.theil_sen_slope(t, y), 0.25, places=6)

    def test_wilson(self):
        lo, hi = pp.wilson(5, 100)
        self.assertLess(lo, 0.05)
        self.assertGreater(hi, 0.05)

    def test_kaplan_meier_with_no_censoring_matches_the_ecdf(self):
        km = pp.kaplan_meier([1.0, 2.0, 3.0, 4.0], [False] * 4)
        self.assertAlmostEqual(km[-1]["survival"], 0.0, places=12)
        self.assertAlmostEqual(pp.km_quantile(km, 0.5), 2.0, places=12)

    def test_kaplan_meier_carries_censoring(self):
        km = pp.kaplan_meier([1.0, 2.0, 3.0], [False, True, False])
        self.assertGreater(km[-1]["survival"], -1e-12)
        self.assertAlmostEqual(km[0]["survival"], 2.0 / 3.0, places=12)

    def test_wrap(self):
        self.assertAlmostEqual(float(pp.wrap180(190.0)), -170.0, places=12)
        self.assertAlmostEqual(float(pp.wrap180(-190.0)), 170.0, places=12)
        self.assertAlmostEqual(float(pp.wrap360(-10.0)), 350.0, places=12)

    def test_interpolation_is_refused_across_a_long_gap(self):
        src = np.asarray([0.0, 1.0, 20.0]) * DAY_MS
        val = np.asarray([0.0, 1.0, 20.0])
        out, ok = pp.interpolate_slow(src, val, np.asarray([0.5, 10.0]) * DAY_MS)
        self.assertTrue(bool(ok[0]))
        self.assertFalse(bool(ok[1]))


class TestEventDefinition(unittest.TestCase):
    """prereg 4 -- on synthetic pairs."""

    def _pair(self, el_a, el_b, flags_a=None, theta_p=0.2, gamma_p=5.0,
              d_days=30.0):
        return pp.evaluate_pair(1, 2, el_a, el_b, flags_a or NO_FLAGS,
                                theta_p, gamma_p, d_days, "LEO", {})

    def test_a_standing_co_orbital_pair_is_not_an_event(self):
        """prereg 4.3: never separated in plane and never in phase."""
        el_a = synth(1, 400.0, RE + 500.0, 0.001, 53.0, 0.0, ma0_deg=0.0)
        el_b = synth(2, 400.0, RE + 500.0, 0.001, 53.0, 0.0, ma0_deg=1.0)
        self.assertEqual(self._pair(el_a, el_b), [])

    def test_a_j2_only_drift_together_is_not_attributed_to_the_approacher(self):
        """prereg 2.4's false-alarm mechanism: the planes close by themselves
        and the counterfactual must say so."""
        a_b = RE + 500.0
        a_a = RE + 507.0
        el_b = synth(2, 900.0, a_b, 0.001, 53.0, 0.0, ma0_deg=0.0)
        el_a = synth(1, 900.0, a_a, 0.001, 53.0, -40.0, ma0_deg=0.0)
        for ev in self._pair(el_a, el_b):
            self.assertIn(ev["attribution"], ("natural", "ambiguous"))
            self.assertNotEqual(ev["attributionPlaneOnlyVariant"], "approacher")

    def test_a_plane_matching_campaign_is_detected_and_attributed(self):
        """The signature the registration derives: an inclination change that
        closes the plane, then a phase-confined dwell."""
        el_b = synth(2, 600.0, RE + 500.0, 0.001, 53.0, 0.0, ma0_deg=0.0)
        rate_b = float(pp.j2_nodal_rate_deg_per_day(RE + 500.0, 0.001, 53.0))

        def inc_a(t):
            if t < 200.0:
                return 59.0
            if t < 260.0:
                return 59.0 - 6.0 * (t - 200.0) / 60.0
            return 53.0

        el_a = synth(1, 600.0, RE + 500.0, 0.001, 53.0, 0.0, ma0_deg=0.2,
                     inc_schedule=inc_a)
        # A's node is made to track B's so only the inclination closes theta
        el_a["raan"] = el_b["raan"].copy()
        el_a["ma"] = pp.wrap360(el_b["ma"] + 0.2)
        flags = {"all_ms": np.asarray([el_a["epoch_ms"][420]], dtype=np.float64),
                 "plane_ms": np.asarray([el_a["epoch_ms"][420]], dtype=np.float64)}
        evs = self._pair(el_a, el_b, flags)
        self.assertTrue(evs, "the synthetic campaign must be detected")
        ev = evs[0]
        self.assertGreater(ev["planeClosureDeg"], 4.5)
        self.assertEqual(ev["attribution"], "approacher")
        self.assertGreater(ev["dwellDays"], 30.0)
        self.assertTrue(ev["corroborated"])
        self.assertGreater(ev["leadCausalDays"], 0.0)

    def test_attribution_names_the_object_whose_elements_changed(self):
        """prereg 4.5(a) with the roles reversed: the TARGET manoeuvred."""
        el_a = synth(1, 600.0, RE + 500.0, 0.001, 53.0, 0.0, ma0_deg=0.0)

        def inc_b(t):
            if t < 200.0:
                return 59.0
            if t < 260.0:
                return 59.0 - 6.0 * (t - 200.0) / 60.0
            return 53.0

        el_b = synth(2, 600.0, RE + 500.0, 0.001, 53.0, 0.0, ma0_deg=0.2,
                     inc_schedule=inc_b)
        el_b["raan"] = el_a["raan"].copy()
        el_b["ma"] = pp.wrap360(el_a["ma"] + 0.2)
        evs = self._pair(el_a, el_b)
        self.assertTrue(evs)
        self.assertEqual(evs[0]["attribution"], "target")

    def test_a_short_dwell_is_rejected(self):
        el_b = synth(2, 600.0, RE + 500.0, 0.001, 53.0, 0.0)

        def inc_a(t):
            if t < 200.0:
                return 59.0
            if t < 260.0:
                return 59.0 - 6.0 * (t - 200.0) / 60.0
            if t < 280.0:
                return 53.0
            return 59.0

        el_a = synth(1, 600.0, RE + 500.0, 0.001, 53.0, 0.0, inc_schedule=inc_a)
        el_a["raan"] = el_b["raan"].copy()
        el_a["ma"] = pp.wrap360(el_b["ma"] + 0.2)
        self.assertEqual(self._pair(el_a, el_b, d_days=30.0), [])

    def test_a_dwell_broken_by_a_long_gap_is_rejected(self):
        el_b = synth(2, 600.0, RE + 500.0, 0.001, 53.0, 0.0)

        def inc_a(t):
            return 59.0 if t < 200.0 else (
                59.0 - 6.0 * min(1.0, (t - 200.0) / 60.0))

        el_a = synth(1, 600.0, RE + 500.0, 0.001, 53.0, 0.0, inc_schedule=inc_a)
        el_a["raan"] = el_b["raan"].copy()
        el_a["ma"] = pp.wrap360(el_b["ma"] + 0.2)
        base = self._pair(el_a, el_b)
        self.assertTrue(base)
        t0 = el_a["epoch_ms"][0] + int(300 * DAY_MS)
        keep = ~((el_a["epoch_ms"] > t0) & (el_a["epoch_ms"] < t0 + int(8 * DAY_MS)))
        el_a2 = {k: v[keep] for k, v in el_a.items()}
        broken = self._pair(el_a2, el_b)
        self.assertTrue(all(e["dwellDays"] < base[0]["dwellDays"] or
                            e["arrivalMs"] != base[0]["arrivalMs"]
                            for e in broken) or not broken)

    def test_campaign_chaining_respects_the_one_hundred_and_eighty_day_gap(self):
        t_a = 1.6e12
        flags = np.asarray([t_a - 900 * DAY_MS, t_a - 800 * DAY_MS,
                            t_a - 100 * DAY_MS, t_a - 60 * DAY_MS])
        chain = pp.campaign_of(flags, t_a)
        self.assertEqual(chain.size, 2)
        self.assertAlmostEqual(float(chain[0]), t_a - 100 * DAY_MS, places=1)

    def test_campaign_respects_the_look_back_window(self):
        t_a = 1.6e12
        flags = np.asarray([t_a - 2000 * DAY_MS])
        self.assertEqual(pp.campaign_of(flags, t_a).size, 0)

    def test_registered_thresholds_are_the_registered_numbers(self):
        self.assertEqual(pp.THETA_P_DEG, 0.2)
        self.assertEqual(pp.GAMMA_DEG, 5.0)
        self.assertEqual(pp.D_DAYS, 30.0)
        self.assertEqual(pp.THETA_FAR_DEG, 5.0)
        self.assertEqual(pp.GAMMA_FAR_DEG, 60.0)
        self.assertEqual(pp.T_LOOK_DAYS, 1095.0)
        self.assertEqual(pp.ATTRIBUTION_SHARE, 0.8)
        self.assertEqual(pp.SEED, 20260922)

    def test_arm_m_requires_corroboration(self):
        ev = {"attribution": "approacher", "phaseArrested": True,
              "corroborated": False, "attributionPlaneOnlyVariant": "approacher"}
        g, m, gv, mv = pp.classify_arms(ev)
        self.assertTrue(g)
        self.assertFalse(m)
        ev["corroborated"] = True
        self.assertTrue(pp.classify_arms(ev)[1])


class TestGates(unittest.TestCase):
    """prereg 10.0: each bar is a formula AND its evaluated number, and the
    two must not disagree -- the T8a Gate A defect, made impossible here."""

    def test_gate_a_formula_and_number_agree(self):
        self.assertAlmostEqual(pp.GATE_A_SIGMA_THETA_MAX_DEG,
                               pp.THETA_P_DEG / 10.0, places=15)
        self.assertAlmostEqual(pp.GATE_A_SIGMA_THETA_MAX_DEG, 0.02, places=15)

    def test_gate_bars(self):
        self.assertEqual(pp.GATE_B_LEAK_RATIO, 0.10)
        self.assertEqual(pp.GATE_D_MIN_EVENTS, 20)
        self.assertEqual(pp.GATE_F_CENSOR_FRACTION, 0.20)
        self.assertEqual(pp.GATE_G_DWELL_EXCEEDANCE, 0.05)
        self.assertEqual(pp.GATE_H_FALSE_ALARM_RATIO, 0.5)

    def test_the_registered_scales_in_kilometres(self):
        """prereg 4.2's honesty statement: the primary box at a 500 km LEO."""
        self.assertAlmostEqual(
            float(pp.cross_track_km(pp.THETA_P_DEG, pp.REF_LEO_A_KM)), 24.0,
            delta=0.1)
        self.assertAlmostEqual(
            float(pp.cross_track_km(pp.GAMMA_DEG, pp.REF_LEO_A_KM)), 599.5,
            delta=0.5)
        self.assertAlmostEqual(
            pp.phase_confinement_da_km(pp.GAMMA_DEG, pp.D_DAYS,
                                       pp.REF_LEO_A_KM), 0.1395, delta=1e-4)


class TestPolicyGuards(unittest.TestCase):
    """The framing rules of the registration are enforced, not merely
    intended -- the same guards T8a's suite carries."""

    SRC = (_REPO / "tools" / "proximity_plane.py").read_text()

    def test_no_intent_language_in_the_tool(self):
        text = self.SRC.lower()
        for banned in ("spying", "spy ", "inspector", "inspection", "threat",
                       "adversary", "hostile", "shadowing", "stalking",
                       "rendezvous and proximity operation"):
            self.assertNotIn(banned, text, f"intent language {banned!r} present")

    def test_registry_codes_are_metadata_only(self):
        for fn in (pp.evaluate_pair, pp.find_dwells, pp.detect_manoeuvres,
                   pp.counterfactual_theta, pp.screen_epoch_cpu,
                   pp.screen_epoch_gpu, pp.run_screen, pp.build_screen_table,
                   pp.campaign_of, pp.classify_arms, pp.class_label,
                   pp.pair_series, pp.object_sigma_contributions):
            src = inspect.getsource(fn).lower()
            self.assertNotIn("country", src, f"{fn.__name__} reads a registry code")
            self.assertNotIn("registry", src, f"{fn.__name__} reads a registry code")

    def test_object_type_is_read_only_by_the_class_label(self):
        for fn in (pp.evaluate_pair, pp.find_dwells, pp.detect_manoeuvres,
                   pp.screen_epoch_cpu, pp.run_screen, pp.pair_series):
            self.assertNotIn("object_type", inspect.getsource(fn).lower())

    def test_no_velocity_or_propellant_figure_is_computed(self):
        """prereg 2.6: the two conversion constants live in the module
        docstring and in no executable path."""
        import re
        body = self.SRC.split('"""', 2)[2].lower()
        for banned in ("delta_v", "deltav", "dv_m_s", "propellant", "fuel",
                       "isp", "mass_kg", "m_per_s"):
            self.assertIsNone(re.search(rf"\b{banned}\b", body),
                              f"{banned!r} appears in an executable path")

    def test_no_site_surface_is_written(self):
        for banned in ("public/", "src/", "data/"):
            self.assertNotIn(f'"{banned}', self.SRC)

    def test_event_rows_carry_no_velocity_field(self):
        el_b = synth(2, 600.0, RE + 500.0, 0.001, 53.0, 0.0)

        def inc_a(t):
            return 59.0 if t < 200.0 else (
                59.0 - 6.0 * min(1.0, (t - 200.0) / 60.0))

        el_a = synth(1, 600.0, RE + 500.0, 0.001, 53.0, 0.0, inc_schedule=inc_a)
        el_a["raan"] = el_b["raan"].copy()
        el_a["ma"] = pp.wrap360(el_b["ma"] + 0.2)
        evs = pp.evaluate_pair(1, 2, el_a, el_b, NO_FLAGS, 0.2, 5.0, 30.0,
                               "LEO", {})
        self.assertTrue(evs)
        for ev in evs:
            for k in ev:
                self.assertNotIn("deltav", k.lower())
                self.assertNotIn("velocity", k.lower())
                self.assertNotIn("fuel", k.lower())
            json.dumps(ev)

    def test_the_registration_is_committed_and_names_the_instrument(self):
        doc = (_REPO / "docs" / "proximity-leo-preregistration-20260922.md")
        self.assertTrue(doc.exists())
        text = doc.read_text()
        self.assertIn("tools/proximity_plane.py", text)
        self.assertIn("committed **alone**", text)


if __name__ == "__main__":
    unittest.main()
