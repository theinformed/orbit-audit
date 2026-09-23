"""Tests for T11b part 2 (tools/geo_passive_control.py).

The first assertions are THE BUG: a synthetic free librator sampled across the
archive's own gaps is flagged as having changed its drift by T8a's constant
0.010 deg/day floor although nothing but triaxiality moved it, and is NOT
flagged by the v2 rule that predicts and subtracts free motion; and the
registered F1 rule, which applies a 0.10 false-alarm threshold once per 56-day
block and excludes on any hit, throws out a pure free librator, because the
minimum of N independent p-values is not a 0.10 test.

Then: the elliptic integral against independently computed values; the
small-amplitude period against 2 pi / sqrt(2A); the amplitude-rate relation at
the separatrix; the integrated pendulum's own period against the closed form;
the restoring acceleration's zeros and extrema; the v2 rule on a synthetic
station-keeper; the five libration bounds, each failed one at a time; the
Sidak threshold; the leak arithmetic on a fixture; and the vocabulary ban.
"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import persistent_pairs as pp                      # noqa: E402
from tools import proximity_geo as pg                         # noqa: E402
from tools import geo_passive_control as gpc                  # noqa: E402

SIGMA_N = 0.0006038533519066339          # T8a's measured value, unchanged


def _librator(u_max_deg=20.0, years=12.0, spacing_days=3.0, sigma_n=0.0,
              seed=11, step=0.5):
    """One free librator, integrated from the pendulum, sampled at a chosen
    element-set spacing. The integration step is coarser than the module's
    own because a 0.5-day RK4 step is 1,630 steps per libration period and the
    period test below shows the integration is accurate to better than 1%."""
    ts, us, vs = gpc._integrate_librators(
        [0.0],
        [gpc.OMEGA_0_RAD_PER_DAY * math.sin(math.radians(u_max_deg))],
        years * 365.25, step=step)
    # _integrate_librators already subsamples to the archive's median element
    # spacing, so the thinning factor is taken from what it returned.
    returned = float(ts[1] - ts[0])
    keep = max(1, int(round(spacing_days / returned)))
    ts, us, vs = ts[::keep], us[::keep], vs[::keep]
    lam = np.degrees(us[:, 0]) + gpc.STABLE_LONGITUDES_DEG[0]
    drift = np.degrees(vs[:, 0])
    if sigma_n:
        drift = drift + np.random.default_rng(seed).normal(
            0.0, sigma_n, size=drift.size)
    return gpc._SynSeries(1, (np.asarray(ts) + 20000.0) * gpc.DAY_MS,
                          pg.wrap180(lam), drift)


class TheBug(unittest.TestCase):
    def test_t8a_floor_flags_free_motion_and_v2_does_not(self):
        # 1.3-day sampling keeps the baseline span inside the registered
        # 14-day evaluability limit, so the comparison is a comparison of
        # thresholds and not of one rule refusing to look.
        # 2-day sampling puts the flag's 10-sample baseline centre about 11
        # days back -- inside the registered 14-day evaluability limit, and far
        # enough that free motion alone moves the drift rate by 1.9e-2 deg/day,
        # which is above T8a's constant 0.010 floor.
        s = _librator(u_max_deg=45.0, spacing_days=2.0, sigma_n=SIGMA_N)
        v1, _sizes = pg.drift_change_flags(s, SIGMA_N)
        self.assertGreater(
            v1.size, 0,
            "T8a's constant floor must flag a purely free librator sampled "
            "across the archive's own gaps -- that is the defect")
        v2, frac, _n = gpc.v2_flags_for(s, SIGMA_N)
        self.assertEqual(
            v2.size, 0,
            "the v2 rule must not flag motion the triaxial term explains")
        self.assertGreater(frac, 0.95,
                           "the librator must be evaluable, or the zero above "
                           "means nothing")

    def test_registered_f1_throws_out_a_free_librator(self):
        """The registered F1 excludes on ANY block below 0.10, and the minimum
        of N independent p-values is below 0.10 with probability 1 - 0.9^N.
        This records the defect rather than editing it out of the
        registration."""
        s = _librator(u_max_deg=25.0, years=20.0,
                      spacing_days=gpc.SAMPLE_SPACING_DAYS, sigma_n=SIGMA_N)
        fap, blocks = gpc.min_block_fap(s)
        self.assertGreater(blocks, 50)
        self.assertLessEqual(fap, gpc.F1_EXCLUDE_FAP,
                             "the registered F1 rule admits this librator, so "
                             "the defect this test records is gone")
        self.assertGreater(fap, gpc.sidak_block_alpha(blocks),
                           "the family-wise threshold must admit it")


class Physics(unittest.TestCase):
    def test_elliptic_k_against_independent_values(self):
        self.assertAlmostEqual(gpc.elliptic_k(0.0), math.pi / 2.0, places=14)
        self.assertAlmostEqual(gpc.elliptic_k(math.sqrt(0.5)),
                               1.8540746773013719, places=12)
        self.assertAlmostEqual(gpc.elliptic_k(0.5), 1.6857503548125961,
                               places=12)
        self.assertAlmostEqual(gpc.elliptic_k(0.9), 2.2805491384227703,
                               places=12)

    def test_small_amplitude_period_is_the_linear_one(self):
        self.assertAlmostEqual(gpc.T0_DAYS,
                               2.0 * math.pi / math.sqrt(
                                   2.0 * gpc.A_RAD_PER_DAY2), places=12)
        self.assertAlmostEqual(gpc.libration_period_days(0.001),
                               gpc.T0_DAYS, places=6)
        self.assertAlmostEqual(gpc.T0_DAYS, 815.4792173265513, places=9)

    def test_period_grows_with_amplitude(self):
        self.assertLess(gpc.libration_period_days(1.0),
                        gpc.libration_period_days(30.0))
        self.assertLess(gpc.libration_period_days(30.0),
                        gpc.libration_period_days(80.0))

    def test_amplitude_rate_relation(self):
        self.assertAlmostEqual(gpc.peak_rate_deg_per_day(90.0),
                               gpc.PEAK_RATE_COEFF_DEG_PER_DAY, places=12)
        self.assertAlmostEqual(gpc.peak_rate_deg_per_day(0.0), 0.0, places=14)
        self.assertAlmostEqual(gpc.PEAK_RATE_COEFF_DEG_PER_DAY,
                               0.4414582154284887, places=12)

    def test_integrated_pendulum_matches_the_closed_form(self):
        """The period-amplitude law is used as a BOUND on real objects, so it
        must first be shown to describe the equation it came from."""
        for u_max in (5.0, 20.0, 45.0):
            s = _librator(u_max_deg=u_max, years=10.0,
                          spacing_days=gpc.SAMPLE_SPACING_DAYS)
            sig = gpc.libration_signature(s)
            self.assertGreaterEqual(sig["turnarounds"], 2)
            self.assertLess(
                abs(sig["observedHalfPeriodDays"]
                    - gpc.libration_half_period_days(sig["uMaxDeg"]))
                / sig["predictedHalfPeriodDays"], 0.01,
                f"integrated half-period disagrees at u_max = {u_max}")

    def test_restoring_acceleration_vanishes_at_the_stable_longitudes(self):
        for s in gpc.STABLE_LONGITUDES_DEG:
            self.assertAlmostEqual(float(gpc.free_acceleration(
                np.array([s]))[0]), 0.0, places=14)
        # 45 degrees from a stable longitude is the extremum
        self.assertAlmostEqual(
            abs(float(gpc.free_acceleration(
                np.array([gpc.STABLE_LONGITUDES_DEG[0] + 45.0]))[0])),
            gpc.A_DEG_PER_DAY2, places=14)

    def test_restoring_acceleration_points_back(self):
        east = float(gpc.free_acceleration(
            np.array([gpc.STABLE_LONGITUDES_DEG[0] + 10.0]))[0])
        west = float(gpc.free_acceleration(
            np.array([gpc.STABLE_LONGITUDES_DEG[0] - 10.0]))[0])
        self.assertLess(east, 0.0)
        self.assertGreater(west, 0.0)


class V2Rule(unittest.TestCase):
    def test_station_keeper_is_flagged(self):
        keep = gpc.synthetic_keepers(3, n=5, years=6.0, sigma_n=SIGMA_N)
        for s in keep:
            ep, _f, _n = gpc.v2_flags_for(s, SIGMA_N)
            self.assertGreater(ep.size, 0)

    def test_quiet_series_is_not_flagged(self):
        n = 3000
        t = np.arange(n) * gpc.SAMPLE_SPACING_DAYS
        rng = np.random.default_rng(5)
        s = gpc._SynSeries(2, (t + 20000.0) * gpc.DAY_MS,
                           np.full(n, gpc.STABLE_LONGITUDES_DEG[0]),
                           rng.normal(0.0, SIGMA_N, size=n))
        ep, _f, _n = gpc.v2_flags_for(s, SIGMA_N)
        self.assertEqual(ep.size, 0)

    def test_single_step_change_needs_two_consecutive_samples(self):
        n = 200
        t = np.arange(n) * gpc.SAMPLE_SPACING_DAYS
        d = np.zeros(n)
        d[100] = 0.05                       # one sample only
        s = gpc._SynSeries(3, (t + 20000.0) * gpc.DAY_MS,
                           np.full(n, gpc.STABLE_LONGITUDES_DEG[0]), d)
        ep, _f, _n = gpc.v2_flags_for(s, SIGMA_N)
        self.assertEqual(ep.size, 0)
        d[101:] = 0.05                      # a step that persists
        s = gpc._SynSeries(3, (t + 20000.0) * gpc.DAY_MS,
                           np.full(n, gpc.STABLE_LONGITUDES_DEG[0]), d)
        ep, _f, _n = gpc.v2_flags_for(s, SIGMA_N)
        self.assertGreater(ep.size, 0)

    def test_evaluability_falls_with_sparse_sampling(self):
        dense = _librator(spacing_days=1.0)
        sparse = _librator(spacing_days=6.0)
        self.assertGreater(gpc.v2_flags_for(dense, SIGMA_N)[1],
                           gpc.v2_flags_for(sparse, SIGMA_N)[1])


class LibrationBounds(unittest.TestCase):
    def test_a_free_librator_passes_all_five(self):
        sig = gpc.libration_signature(_librator(u_max_deg=25.0, years=12.0))
        for key in ("c1BoundMotion", "c2Turnaround", "c3Centred",
                    "c4RateBound", "c5PeriodBound", "passed"):
            self.assertTrue(sig[key], key)

    def test_a_station_keeper_fails_the_turnaround_and_the_period(self):
        s = gpc.synthetic_keepers(4, n=1, years=6.0, sigma_n=SIGMA_N)[0]
        sig = gpc.libration_signature(s)
        self.assertFalse(sig["c2Turnaround"])
        self.assertFalse(sig["c5PeriodBound"])
        self.assertFalse(sig["passed"])

    def test_a_circulating_object_fails_the_bound_motion_clause(self):
        n = 2000
        t = np.arange(n) * 3.0
        lam = pg.wrap180(-180.0 + (t * 0.25) % 360.0)
        s = gpc._SynSeries(5, (t + 20000.0) * gpc.DAY_MS, lam,
                           np.full(n, 0.25))
        self.assertFalse(gpc.libration_signature(s)["passed"])

    def test_an_object_faster_than_free_motion_fails_the_rate_bound(self):
        s = _librator(u_max_deg=10.0, years=12.0)
        boosted = gpc._SynSeries(6, s.epoch_ms, s.lam, s.drift * 3.0)
        sig = gpc.libration_signature(boosted)
        self.assertFalse(sig["c4RateBound"])
        self.assertGreater(sig["maxAbsDriftDegPerDay"],
                           gpc.RATE_BOUND_FACTOR
                           * sig["predictedPeakRateDegPerDay"])

    def test_an_off_centre_swing_fails_the_centring_clause(self):
        s = _librator(u_max_deg=2.0, years=12.0)
        shifted = gpc._SynSeries(7, s.epoch_ms, pg.wrap180(s.lam + 30.0),
                                 s.drift)
        self.assertFalse(gpc.libration_signature(shifted)["c3Centred"])

    def test_one_turnaround_is_not_enough_for_the_period_bound(self):
        s = _librator(u_max_deg=25.0, years=2.0)
        sig = gpc.libration_signature(s)
        if sig["turnarounds"] < 2:
            self.assertFalse(sig["c5PeriodBound"])
            self.assertFalse(sig["passed"])


class Multiplicity(unittest.TestCase):
    def test_sidak_threshold(self):
        self.assertAlmostEqual(gpc.sidak_block_alpha(1), 0.10, places=12)
        for n in (10, 131, 500):
            a = gpc.sidak_block_alpha(n)
            self.assertAlmostEqual((1.0 - a) ** n, 0.90, places=12)
            self.assertLess(a, gpc.F1_EXCLUDE_FAP)

    def test_cadence_line_is_found_in_a_sawtooth(self):
        s = gpc.synthetic_keepers(8, n=1, years=6.0, sigma_n=SIGMA_N)[0]
        fap, blocks = gpc.min_block_fap(s)
        self.assertGreater(blocks, 10)
        self.assertLess(fap, 1e-6)


class Leak(unittest.TestCase):
    def test_leak_arithmetic_on_a_fixture(self):
        class _W:
            pass
        w = _W()
        w.series = []
        w.stationed_days = {1: np.arange(0, 100), 2: np.arange(50, 150),
                            3: np.arange(0, 10)}
        w.segs = {1: [(0, 99)], 2: [(0, 99)], 3: [(0, 9)]}
        for n in (1, 2, 3):
            s = gpc._SynSeries(n, np.zeros(1), np.zeros(1), np.zeros(1))
            w.series.append(s)
        episodes = [{"a": 1, "b": 2}, {"a": 1, "b": 3}]
        events = [1, 1, 2]
        ref = {"episodeRatePerPairDay": 1e-4,
               "eventRatePerObjectDay": 1e-3}
        got = gpc.leak_for(w, {1, 2}, episodes, events, ref)
        self.assertEqual(got["pairExposureDays"], 50)     # days 50..99
        self.assertEqual(got["episodes"], 1)
        self.assertEqual(got["stationedObjectDays"], 200)
        self.assertEqual(got["t8aEvents"], 3)
        self.assertFalse(got["leakFree"])
        self.assertFalse(got["unevaluable"])

    def test_no_exposure_is_unevaluable_and_not_leak_free(self):
        class _W:
            pass
        w = _W()
        w.series = [gpc._SynSeries(1, np.zeros(1), np.zeros(1), np.zeros(1))]
        w.stationed_days = {1: np.arange(0, 10)}
        w.segs = {1: [(0, 9)]}
        got = gpc.leak_for(w, {1}, [], [], None)
        self.assertEqual(got["pairExposureDays"], 0)
        self.assertTrue(got["unevaluable"])
        self.assertFalse(got["leakFree"])


class Framing(unittest.TestCase):
    def test_no_banned_vocabulary_in_the_module(self):
        hits = pp.banned_hits(Path(gpc.__file__).read_text())
        self.assertEqual(hits, [], f"banned vocabulary: {hits}")

    def test_registered_constants(self):
        self.assertEqual(gpc.MAX_BASELINE_SPAN_DAYS, 14.00)
        self.assertEqual(gpc.MAX_NON_EVALUABLE_FRACTION, 0.05)
        self.assertEqual(gpc.F1_EXCLUDE_FAP, 0.10)
        self.assertEqual(gpc.TURNAROUND_MIN_RUN_DAYS, 30.0)
        self.assertEqual(gpc.RATE_BOUND_FACTOR, 1.25)
        self.assertEqual(gpc.PERIOD_BOUND_FACTOR, 0.80)
        self.assertEqual(gpc.LEAK_BAR, 0.10)
        self.assertEqual(gpc.SEED, 20260922)
        self.assertEqual(gpc.V1_BAR, 0.95)
        self.assertEqual(gpc.V2_BAR, 0.95)

    def test_the_constant_is_t8as_committed_derivation(self):
        self.assertEqual(gpc.A_DEG_PER_DAY2, pg.LAMBDA_DDOT_MAX)
        self.assertEqual(gpc.STABLE_LONGITUDES_DEG, pg.STABLE_LONGITUDES_DEG)
        self.assertEqual(gpc.BASELINE_SAMPLES, pg.BURN_BASELINE_SAMPLES)
        self.assertEqual(gpc.SIGMA_K, pg.BURN_SIGMA_K)

    def test_east_west_burn_step_from_the_measured_cycle(self):
        self.assertAlmostEqual(gpc.EW_BURN_STEP,
                               gpc.A_DEG_PER_DAY2 * 14.0 / 2.0, places=15)
        self.assertGreater(gpc.EW_BURN_STEP, gpc.SIGMA_K * SIGMA_N)


if __name__ == "__main__":
    unittest.main()
