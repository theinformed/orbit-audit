#!/usr/bin/env python3
"""Offline proofs for T27's instrument.

Two of these assert the defect the change is supposed to fix, on series built
here rather than on archive data:

  * an object whose own fit noise is five times the pooled value must LOSE its
    false flags when the detector is given that object's own scale;
  * a 60 m semi-major-axis step on a quiet object must SURVIVE the change --
    it sits above the registered 50 m floor and below the shipped 102-126 m
    one, which is the whole reason the change is a candidate.

Nothing here reads the archive, the label set or the element-set cache.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO))

import proximity_plane as pp                                    # noqa: E402
import per_object_noise as pon                                  # noqa: E402

N_REV_DAY = 14.30          # a low-orbit mean motion, ~7,100 km
SETS = 400
SPACING_DAYS = 0.5


def build_series(n_series, spacing_days=SPACING_DAYS):
    """A synthetic element-set history with the mean motion supplied by the
    caller.

    The node is advanced at the object's own J2 secular rate rather than held
    fixed, so that the plane channel sees the residual it is built to see and
    contributes nothing. Holding the node fixed would make the detector's own
    J2 model the anomaly, which is an artefact of the fixture and not a
    property of the detector.
    """
    size = n_series.size
    n_series = np.asarray(n_series, dtype=np.float64)
    epoch = (np.arange(size, dtype=np.float64) * spacing_days
             * pp.DAY_MS + 1.0e12).astype(np.int64)
    ecc = np.full(size, 0.001)
    inc = np.full(size, 98.0)
    a_km = pp.semi_major_axis_km(n_series)
    rate = pp.j2_nodal_rate_deg_per_day(a_km, ecc, inc)
    raan = (120.0 + np.cumsum(np.concatenate(([0.0], rate[:-1] * spacing_days)))) % 360.0
    return {
        "epoch_ms": epoch,
        "n": n_series,
        "e": ecc,
        "inc": inc,
        "raan": raan,
    }


def da_metres_to_dn(da_m, n=N_REV_DAY):
    """da/a = -(2/3) dn/n  =>  |dn| = (3/2) (n/a) |da|.

    Derived from a = (mu / (2 pi n / 86400)^2)^(1/3); no value is quoted.
    """
    a_km = float(pp.semi_major_axis_km(n))
    return 1.5 * n * (da_m / 1000.0) / a_km


class TestTheDefect(unittest.TestCase):
    def test_noisy_object_loses_its_false_flags_under_its_own_scale(self):
        """An object whose own sigma is 5x pooled.

        NOTHING happens to this object: the series is fit noise about a fixed
        mean motion and nothing else, so every flag the pooled arm raises on it
        is false by construction. The pooled threshold sits at one of this
        object's own sigmas and it fires; the object's own threshold sits at
        five and it must not.
        """
        rng = np.random.default_rng(20260923)
        own_sigma = 5.0 * pon.POOLED_SIGMA_N
        n = N_REV_DAY + rng.normal(0.0, own_sigma, SETS)
        el = build_series(n)

        est_theta, est_n = pp.object_sigma_contributions(el)
        self.assertGreater(est_n, 3.0 * pon.POOLED_SIGMA_N,
                           "the estimator must recover a scale near 5x pooled")

        shipped = pp.detect_manoeuvres(el, pon.POOLED_SIGMA_N,
                                       pon.POOLED_SIGMA_THETA)
        sn, st, _ = pon.per_object_sigmas(el)
        own = pp.detect_manoeuvres(el, sn, st)

        self.assertGreater(shipped["intrack"].size, 50,
                           "the pooled arm must raise false flags here")
        removed = 1.0 - own["intrack"].size / shipped["intrack"].size
        self.assertGreater(removed, 0.95,
                           "the object's own scale must remove nearly all of "
                           f"them (shipped {shipped['intrack'].size}, own "
                           f"{own['intrack'].size})")

    def test_what_survives_is_the_statistic_own_tail_and_not_the_scale(self):
        """The same fixture at four times the scale again.

        The pooled arm flags far MORE as the object gets noisier, because its
        bar is fixed while the object is not. The object's own arm flags the
        same few epochs at either scale -- the residual statistic's own extreme
        tail, which no choice of scale removes. What the change removes is the
        mismatch; what it leaves is a property of the statistic.
        """
        out = {}
        for factor in (5.0, 20.0):
            rng = np.random.default_rng(20260923)
            el = build_series(N_REV_DAY
                              + rng.normal(0.0, factor * pon.POOLED_SIGMA_N, SETS))
            sn, st, _ = pon.per_object_sigmas(el)
            out[factor] = (
                pp.detect_manoeuvres(el, pon.POOLED_SIGMA_N,
                                     pon.POOLED_SIGMA_THETA)["intrack"],
                pp.detect_manoeuvres(el, sn, st)["intrack"])
        self.assertGreater(out[20.0][0].size, out[5.0][0].size,
                           "the pooled bar must flag a noisier object more")
        self.assertEqual(list(out[20.0][1]), list(out[5.0][1]),
                         "the object's own bar must be scale-invariant")
        self.assertLess(out[20.0][1].size, 0.02 * out[20.0][0].size)

    def test_the_five_sigma_bar_is_not_five_sigma_of_the_statistic_it_judges(self):
        """A property of the shipped detector, measured here rather than
        assumed: the rolling local-linear residual the in-track channel
        thresholds is wider than the fit noise that sets the threshold, so the
        nominal five-sigma bar stands at about three sigma of the statistic it
        is actually compared against. It is a screen, not a law."""
        rng = np.random.default_rng(20260923)
        sigma = 5.0 * pon.POOLED_SIGMA_N
        el = build_series(N_REV_DAY + rng.normal(0.0, sigma, 4000))
        res = pp.rolling_theil_sen_residual(el["epoch_ms"] / pp.DAY_MS, el["n"])
        inflation = float(np.std(res[pp.BURN_BASELINE_SAMPLES:]) / sigma)
        self.assertGreater(inflation, 1.3)
        self.assertLess(inflation, 2.2)

    def test_sixty_metre_step_survives_on_a_quiet_object(self):
        """A quiet, well-tracked object: a 60 m step sits above the registered
        50 m floor and below the shipped threshold, so the change must gain
        it."""
        rng = np.random.default_rng(20260923)
        own_sigma = 3.0e-7                  # the label spacecraft's own scale
        n = N_REV_DAY + rng.normal(0.0, own_sigma, SETS)
        step = da_metres_to_dn(60.0)
        n[200:] -= step                     # a raise: a falls -> n rises; sign
        el = build_series(n)                # is irrelevant, the rule is |.|

        sn, st, _ = pon.per_object_sigmas(el)
        self.assertLess(sn, pon.POOLED_SIGMA_N / 10.0)

        shipped = pp.detect_manoeuvres(el, pon.POOLED_SIGMA_N,
                                       pon.POOLED_SIGMA_THETA)
        own = pp.detect_manoeuvres(el, sn, st)
        self.assertEqual(shipped["intrack"].size, 0,
                         "the shipped 102-126 m floor must miss a 60 m step")
        self.assertGreater(own["intrack"].size, 0,
                           "the 50 m floor term must catch it")

    def test_the_floor_terms_are_where_the_registration_says(self):
        """prereg 1.5: on a quiet object the binding term stops being 5 sigma
        and becomes the 50 m floor."""
        rng = np.random.default_rng(20260923)
        el = build_series(N_REV_DAY + rng.normal(0.0, 3.0e-7, SETS))
        pooled = pon.tr.detector_floor(el, pon.POOLED_SIGMA_N,
                                       pon.POOLED_SIGMA_THETA)
        sn, st, _ = pon.per_object_sigmas(el)
        own = pon.tr.detector_floor(el, sn, st)
        self.assertEqual(pooled["thresholdSetBy"], "fitNoise")
        self.assertEqual(own["thresholdSetBy"], "floor")
        self.assertAlmostEqual(own["minDetectableDaMetres"], 50.0, delta=0.5)
        self.assertGreater(pooled["minDetectableDaMetres"], 100.0)


class TestFallbackLadder(unittest.TestCase):
    def test_too_few_sets_falls_back_to_pooled_in_both_channels(self):
        el = build_series(np.full(7, N_REV_DAY))
        sn, st, fb = pon.per_object_sigmas(el)
        self.assertTrue(fb["sigmaN"])
        self.assertTrue(fb["sigmaTheta"])
        self.assertEqual(sn, pon.POOLED_SIGMA_N)
        self.assertEqual(st, pon.POOLED_SIGMA_THETA)

    def test_zero_sigma_is_not_replaced(self):
        """prereg 1.4 rung 3: a zero scale is allowed and makes the floor terms
        binding, which is the designed behaviour."""
        el = build_series(np.full(40, N_REV_DAY))
        sn, st, fb = pon.per_object_sigmas(el)
        self.assertEqual(sn, 0.0)
        self.assertTrue(fb["sigmaNZero"])
        self.assertFalse(fb["sigmaN"])

    def test_one_channel_falling_back_leaves_the_other_alone(self):
        el = build_series(np.full(40, N_REV_DAY))
        el["inc"] = el["inc"] + np.arange(40) * 0.0
        sn, st, fb = pon.per_object_sigmas(el)
        self.assertFalse(fb["sigmaN"])
        self.assertFalse(fb["sigmaTheta"])

    def test_detector_returns_nothing_below_thirteen_sets(self):
        el = build_series(np.full(12, N_REV_DAY))
        det = pp.detect_manoeuvres(el, pon.POOLED_SIGMA_N, pon.POOLED_SIGMA_THETA)
        self.assertEqual(det["intrack"].size, 0)
        self.assertEqual(det["plane"].size, 0)


class TestPlacebos(unittest.TestCase):
    def test_donor_permutation_gives_no_object_its_own_scale(self):
        keys = [f"sat-{i}" for i in range(11)]
        d = pon.derangement(keys)
        self.assertEqual(sorted(d), sorted(keys))
        self.assertEqual(sorted(d.values()), sorted(keys))
        for k, v in d.items():
            self.assertNotEqual(k, v)

    def test_donor_permutation_is_deterministic(self):
        keys = [f"sat-{i}" for i in range(11)]
        self.assertEqual(pon.derangement(keys), pon.derangement(keys))

    def test_shifted_window_falls_back_when_the_window_is_empty(self):
        el = build_series(np.full(200, N_REV_DAY))
        lo = int(el["epoch_ms"][0])
        hi = int(el["epoch_ms"][-1])
        sn, st, how = pon.shifted_window_sigmas(el, lo, hi)
        self.assertIn(how, ("shifted", "shiftedOpposite", "wholeHistory"))


class TestIntervals(unittest.TestCase):
    def test_a_zero_count_never_gets_a_zero_upper_bound(self):
        cell = pon.rate_cell(0, 18_792_698)
        self.assertEqual(cell["perObjectDay"], 0.0)
        self.assertGreater(cell["jeffreys95PerObjectDay"][1], 0.0)

    def test_wilson_brackets_the_point_estimate(self):
        lo, hi = pon.wilson(90, 1134)
        self.assertLess(lo, 90 / 1134)
        self.assertGreater(hi, 90 / 1134)

    def test_increment_reports_its_own_minimum_detectable_effect(self):
        rng = np.random.default_rng(7)
        units = np.repeat(np.arange(11), 100)
        a = (rng.random(1100) < 0.08).astype(float)
        b = a.copy()
        b[:40] = 1.0
        inc = pon.paired_increment(a, b, units, draws=200)
        self.assertGreater(inc["incrementPoints"], 0.0)
        self.assertGreater(inc["minimumDetectablePoints"], 0.0)
        self.assertEqual(inc["units"], 11)

    def test_an_increment_inside_its_own_half_width_is_not_demonstrable(self):
        rng = np.random.default_rng(11)
        units = np.repeat(np.arange(11), 100)
        a = (rng.random(1100) < 0.08).astype(float)
        b = a.copy()
        b[0] = 1.0
        inc = pon.paired_increment(a, b, units, draws=200)
        self.assertFalse(inc["demonstrable"])


class TestBinsAndGates(unittest.TestCase):
    def test_burn_size_bins_are_the_registered_ones(self):
        self.assertEqual(pon.tr.bin_of(10.0, pon.tr.DA_BINS), "0-20 m")
        self.assertEqual(pon.tr.bin_of(60.0, pon.tr.DA_BINS), "50-100 m")
        self.assertEqual(pon.tr.bin_of(900.0, pon.tr.DA_BINS), ">=500 m")
        self.assertEqual(pon.tr.bin_of(None, pon.tr.DA_BINS), "unknown")

    def test_the_production_detector_is_untouched(self):
        gate = pon.detector_untouched()
        self.assertTrue(gate["clean"], gate["diffstat"])
        for path in pon.DETECTOR_FILES:
            self.assertEqual(len(gate["blobHashes"][path]), 40)

    def test_nothing_in_the_instrument_changes_a_shipped_constant(self):
        self.assertEqual(pp.BURN_SIGMA_K, 5.0)
        self.assertEqual(pp.DA_FLOOR_KM, 0.050)
        self.assertEqual(pp.I_FLOOR_DEG, 0.01)
        self.assertEqual(pp.BURN_BASELINE_SAMPLES, 10)
        self.assertEqual(pp.CAMPAIGN_MAX_GAP_DAYS, 180.0)
        self.assertEqual(pon.POOLED_SIGMA_N, 6.2747e-5)
        self.assertEqual(pon.POOLED_SIGMA_THETA, 0.6994)

    def test_the_reproduction_gate_carries_the_published_cells(self):
        self.assertEqual(pon.G2_TARGETS["shipped"]["hits"], 90)
        self.assertEqual(pon.G2_TARGETS["perObject"]["hits"], 128)
        self.assertEqual(pon.G2_TARGETS["shipped"]["quietFlags"], 18)
        self.assertEqual(pon.G2_TARGETS["perObject"]["quietFlags"], 18)

    def test_a_clause_that_cannot_be_evaluated_is_a_failing_clause(self):
        labels_out = {
            "increments": {"perObject": {
                "armOfRecord": "objectCluster",
                "vsShipped": {"objectCluster": {
                    "lowerBoundAboveZero": True, "demonstrable": True}}}},
            "reversalClause": {"fires": False},
        }
        out = pon.decide(labels_out, None)
        self.assertEqual(out["verdict"], "NOT SHIPPED")
        self.assertIn("E3a (not evaluated)", out["failingClauses"])

    def test_the_vocabulary_ban_holds_over_this_track(self):
        from persistent_pairs import banned_hits
        for path in (REPO / "tools" / "per_object_noise.py",
                     REPO / "tests" / "test_per_object_noise.py",
                     REPO / "docs" / "t27-per-object-noise-preregistration-20260923.md"):
            if path.exists():
                self.assertEqual(banned_hits(path.read_text()), [], str(path))


class TestSigmaEstimator(unittest.TestCase):
    def test_the_second_difference_divisor_is_the_derived_one(self):
        """Var(y[i+2] - 2y[i+1] + y[i]) = (1 + 4 + 1) s^2, so the robust scale
        of the second difference divided by sqrt(6) returns s."""
        rng = np.random.default_rng(3)
        s = 4.0e-6
        el = build_series(N_REV_DAY + rng.normal(0.0, s, 20000))
        _, est = pp.object_sigma_contributions(el)
        self.assertAlmostEqual(est / s, 1.0, delta=0.05)

    def test_a_secular_trend_does_not_inflate_the_estimate(self):
        rng = np.random.default_rng(5)
        s = 4.0e-6
        drift = np.arange(4000) * 2.0e-7
        el = build_series(N_REV_DAY + drift + rng.normal(0.0, s, 4000))
        _, est = pp.object_sigma_contributions(el)
        self.assertAlmostEqual(est / s, 1.0, delta=0.10)

    def test_a_minority_of_steps_does_not_move_the_median_scale(self):
        rng = np.random.default_rng(9)
        s = 4.0e-6
        n = N_REV_DAY + rng.normal(0.0, s, 4000)
        for k in range(200, 4000, 200):
            n[k:] += 500.0 * s
        el = build_series(n)
        _, est = pp.object_sigma_contributions(el)
        self.assertLess(est, 3.0 * s,
                        "the median absolute deviation must survive the steps")


if __name__ == "__main__":
    unittest.main(verbosity=2)
