"""Offline tests for the Paper B analysis arithmetic.

No archive, no network, no GPU, no fixtures on disk: every case below is a
hand-computed or analytically known answer, so a failure here is a defect in
this task's statistics rather than a change in the sky. Run it before trusting
any number in `docs/paperb-results-20260920.md`:

    .venv-gpu/bin/python tools/paperb_selftest.py

The tests that matter most are the ones that check the estimators can produce
an UNFAVOURABLE answer: a reweighting that moves the floor upward, a TOST that
declines to declare equivalence, a boundary scan that finds nothing. An
analysis which can only confirm is not an analysis.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import paperb_strata as strata  # noqa: E402


class Bands(unittest.TestCase):
    def test_edges_are_lower_inclusive_upper_exclusive(self):
        self.assertEqual(strata.inclination_band(0.0), "0-1")
        self.assertEqual(strata.inclination_band(0.999), "0-1")
        self.assertEqual(strata.inclination_band(1.0), "1-5")
        self.assertEqual(strata.inclination_band(29.999), "15-30")
        self.assertEqual(strata.inclination_band(30.0), "30-60")
        self.assertEqual(strata.inclination_band(90.0), "90-120")

    def test_retrograde_180_lands_in_the_last_band(self):
        self.assertEqual(strata.inclination_band(180.0), "120-180")

    def test_eccentricity_decades(self):
        self.assertEqual(strata.eccentricity_class(0.0), "<0.001")
        self.assertEqual(strata.eccentricity_class(0.001), "0.001-0.01")
        self.assertEqual(strata.eccentricity_class(0.05), "0.01-0.1")
        self.assertEqual(strata.eccentricity_class(0.72), ">=0.1")

    def test_cadence_covers_the_whole_admissible_span(self):
        # MINIMUM_SPAN_DAYS 0.1 to MAXIMUM_JOINABLE_GAP_DAYS 3.0.
        self.assertEqual(strata.cadence_class(0.1), "<0.25 d")
        self.assertEqual(strata.cadence_class(0.25), "0.25-1 d")
        self.assertEqual(strata.cadence_class(1.0), "1-2 d")
        self.assertEqual(strata.cadence_class(3.0), ">=2 d")

    def test_stratum_key_round_trips_through_json(self):
        import json
        key = strata.stratum_key(820.0, 98.2, 0.0004, 0.5)
        self.assertEqual(key, "800-1200 km|90-120|<0.001|0.25-1 d")
        self.assertEqual(json.loads(json.dumps({key: 1})), {key: 1})
        self.assertEqual(strata.coarse_key(key), "800-1200 km|90-120")

    def test_curve_and_zoom_bins(self):
        self.assertEqual(strata.curve_bin(0.0), 0)
        self.assertEqual(strata.curve_bin(1.99), 0)
        self.assertEqual(strata.curve_bin(2.0), 1)
        self.assertEqual(strata.curve_bin(180.0), 89)
        self.assertEqual(strata.curve_bin_bounds(48), (96.0, 98.0))
        self.assertEqual(strata.zoom_bin(0.05), 0)
        self.assertEqual(strata.zoom_bin(1.95), 9)
        self.assertIsNone(strata.zoom_bin(2.0))

    def test_sso_band_aligns_with_curve_bin_edges(self):
        self.assertTrue(strata.is_sso(96.0))
        self.assertTrue(strata.is_sso(99.9))
        self.assertFalse(strata.is_sso(100.0))
        self.assertEqual(strata.curve_bin_bounds(strata.curve_bin(96.0))[0], strata.SSO_MIN_DEG)
        self.assertEqual(strata.curve_bin_bounds(strata.curve_bin(99.9))[1], strata.SSO_MAX_DEG)


class Jeffreys(unittest.TestCase):
    def test_zero_flags_never_yields_a_zero_upper_bound(self):
        low, high = strata.jeffreys(0, 1000)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)
        self.assertLess(high, 0.01)

    def test_interval_brackets_the_point_estimate(self):
        low, high = strata.jeffreys(50, 10000)
        self.assertLess(low, 0.005)
        self.assertGreater(high, 0.005)

    def test_tighter_with_more_exposure(self):
        narrow = strata.jeffreys(100, 100000)
        wide = strata.jeffreys(10, 10000)
        self.assertLess(narrow[1] - narrow[0], wide[1] - wide[0])


class ExactRatio(unittest.TestCase):
    def test_equal_rates_give_a_ratio_interval_around_one(self):
        result = strata.ratio_interval(500, 1_000_000, 500, 1_000_000)
        self.assertAlmostEqual(result["point"], 1.0, places=9)
        self.assertLess(result["low"], 1.0)
        self.assertGreater(result["high"], 1.0)

    def test_exposure_asymmetry_is_carried(self):
        # Same counts, payload observed on half the exposure: twice the rate.
        result = strata.ratio_interval(500, 1_000_000, 500, 500_000)
        self.assertAlmostEqual(result["point"], 2.0, places=9)
        self.assertGreater(result["low"], 1.5)

    def test_no_flags_anywhere_is_labelled_not_a_ratio_of_one(self):
        result = strata.ratio_interval(0, 1000, 0, 1000)
        self.assertIsNone(result["point"])
        self.assertIn("no flags", result["note"])

    def test_one_sided_when_a_population_has_no_flags(self):
        result = strata.ratio_interval(20, 100_000, 0, 100_000)
        self.assertEqual(result["low"], 0.0)
        self.assertGreater(result["high"], 0.0)
        self.assertIn("one-sided", result["note"])

    def test_interval_narrows_as_counts_grow(self):
        small = strata.ratio_interval(10, 100_000, 10, 100_000)
        large = strata.ratio_interval(1000, 10_000_000, 1000, 10_000_000)
        self.assertLess(large["high"] - large["low"], small["high"] - small["low"])


class Tost(unittest.TestCase):
    def test_large_matched_samples_are_declared_equivalent(self):
        result = strata.tost_ratio(1000, 1_000_000, 1000, 1_000_000, margin=1.5)
        self.assertTrue(result["equivalent"])
        self.assertLess(result["pValueTost"], 0.05)
        self.assertGreater(result["ratio90"]["low"], 1 / 1.5)
        self.assertLess(result["ratio90"]["high"], 1.5)

    def test_small_matched_samples_are_inconclusive_not_equivalent(self):
        # The whole point of TOST: a non-significant difference on five flags
        # a side is not evidence of equivalence, and must not be reported as it.
        result = strata.tost_ratio(5, 100_000, 5, 100_000, margin=1.5)
        self.assertFalse(result["equivalent"])
        self.assertGreater(result["superiorityPValueNoDecisionWeight"], 0.05)

    def test_a_genuinely_different_rate_fails_equivalence(self):
        result = strata.tost_ratio(1000, 1_000_000, 3000, 1_000_000, margin=1.5)
        self.assertFalse(result["equivalent"])
        self.assertGreater(result["ratio90"]["low"], 1.5)

    def test_tost_agrees_with_its_own_ninety_percent_interval(self):
        for passive, payload in ((1000, 1000), (1000, 1200), (1000, 1600), (40, 55)):
            with self.subTest(passive=passive, payload=payload):
                result = strata.tost_ratio(passive, 1_000_000, payload, 1_000_000, margin=1.5)
                inside = (
                    result["ratio90"]["low"] > 1 / 1.5
                    and result["ratio90"]["high"] < 1.5
                )
                self.assertEqual(result["equivalent"], inside)

    def test_margin_is_symmetric_on_the_log_scale(self):
        up = strata.tost_ratio(1000, 1_000_000, 1400, 1_000_000, margin=1.5)
        down = strata.tost_ratio(1400, 1_000_000, 1000, 1_000_000, margin=1.5)
        self.assertEqual(up["equivalent"], down["equivalent"])

    def test_empty_region_is_reported_inconclusive_not_equivalent(self):
        result = strata.tost_ratio(0, 0, 0, 0, margin=1.5)
        self.assertFalse(result["equivalent"])
        self.assertFalse(result["conclusive"])


class Reweighting(unittest.TestCase):
    def test_identical_covariate_mixes_leave_the_floor_alone(self):
        passive = {"a": (10, 10_000), "b": (20, 10_000)}
        payload = {"a": (0, 5_000), "b": (0, 5_000)}
        result = strata.reweight(passive, payload)
        self.assertAlmostEqual(result["rawFloorPerInterval"], 30 / 20_000)
        self.assertAlmostEqual(result["reweightedFloorPerInterval"], 30 / 20_000)
        self.assertAlmostEqual(result["ratioToRaw"], 1.0)

    def test_a_payload_mix_loaded_onto_the_noisy_stratum_raises_the_floor(self):
        passive = {"quiet": (1, 100_000), "noisy": (100, 100_000)}
        payload = {"quiet": (0, 1_000), "noisy": (0, 99_000)}
        result = strata.reweight(passive, payload)
        self.assertGreater(result["ratioToRaw"], 1.9)
        self.assertLess(result["reweightedFloorPerInterval"], 100 / 100_000)

    def test_a_payload_mix_loaded_onto_the_quiet_stratum_lowers_the_floor(self):
        passive = {"quiet": (1, 100_000), "noisy": (100, 100_000)}
        payload = {"quiet": (0, 99_000), "noisy": (0, 1_000)}
        result = strata.reweight(passive, payload)
        self.assertLess(result["ratioToRaw"], 0.2)

    def test_unsupported_strata_are_labelled_gaps_and_never_imputed(self):
        passive = {"seen": (10, 10_000)}
        payload = {"seen": (0, 5_000), "unseen": (0, 5_000)}
        result = strata.reweight(passive, payload)
        self.assertEqual(result["gapStrata"], 1)
        self.assertAlmostEqual(result["unsupportedPayloadExposureShare"], 0.5)
        self.assertEqual([g["stratum"] for g in result["gaps"]], ["unseen"])
        # The reweighted floor is the supported-strata estimate only.
        self.assertAlmostEqual(result["reweightedFloorPerInterval"], 10 / 10_000)

    def test_minimum_support_tier_moves_strata_into_the_gap_list(self):
        passive = {"thin": (0, 5), "thick": (10, 10_000)}
        payload = {"thin": (0, 5_000), "thick": (0, 5_000)}
        loose = strata.reweight(passive, payload, minimum_support=1)
        strict = strata.reweight(passive, payload, minimum_support=1_000)
        self.assertEqual(loose["gapStrata"], 0)
        self.assertEqual(strict["gapStrata"], 1)
        self.assertAlmostEqual(strict["unsupportedPayloadExposureShare"], 0.5)

    def test_worst_case_fill_is_pessimistic_and_says_so(self):
        passive = {"seen": (10, 10_000)}
        payload = {"seen": (0, 5_000), "unseen": (0, 5_000)}
        result = strata.reweight(passive, payload)
        filled = strata.worst_case_fill(result)
        self.assertGreater(filled["reweightedFloorPerInterval"],
                           result["reweightedFloorPerInterval"])
        self.assertAlmostEqual(filled["filledExposureShare"], 0.5)

    def test_zero_flag_strata_still_carry_a_nonzero_upper_bound(self):
        passive = {"empty": (0, 50_000)}
        payload = {"empty": (0, 10_000)}
        result = strata.reweight(passive, payload)
        self.assertEqual(result["reweightedFloorPerInterval"], 0.0)
        self.assertGreater(result["rows"][0]["passiveJeffreys95Per1000"][1], 0.0)


class Intervals(unittest.TestCase):
    def test_clustered_bootstrap_brackets_the_point_estimate(self):
        per_object = [{"a": (1, 1_000)} for _ in range(200)]
        per_object += [{"a": (0, 1_000)} for _ in range(200)]
        weights = {"a": 1.0}
        result = strata.bootstrap_reweighted(per_object, weights, draws=400, seed=1)
        self.assertLess(result["low95Per1000"], 0.5)
        self.assertGreater(result["high95Per1000"], 0.5)
        self.assertEqual(result["usableDraws"], 400)

    def test_clustered_bootstrap_is_wider_than_pretending_intervals_are_independent(self):
        # One object carries every flag: the object-level interval must notice.
        clustered = [{"a": (40, 1_000)}] + [{"a": (0, 1_000)} for _ in range(39)]
        spread = [{"a": (1, 1_000)} for _ in range(40)]
        wide = strata.bootstrap_reweighted(clustered, {"a": 1.0}, draws=500, seed=2)
        narrow = strata.bootstrap_reweighted(spread, {"a": 1.0}, draws=500, seed=2)
        self.assertGreater(
            wide["high95Per1000"] - wide["low95Per1000"],
            narrow["high95Per1000"] - narrow["low95Per1000"],
        )

    def test_bootstrap_is_deterministic_under_its_registered_seed(self):
        per_object = [{"a": (i % 3, 1_000)} for i in range(50)]
        first = strata.bootstrap_reweighted(per_object, {"a": 1.0}, draws=200, seed=strata.SEED)
        second = strata.bootstrap_reweighted(per_object, {"a": 1.0}, draws=200, seed=strata.SEED)
        self.assertEqual(first["low95Per1000"], second["low95Per1000"])
        self.assertEqual(first["high95Per1000"], second["high95Per1000"])

    def test_posterior_composite_is_conservative_as_registered(self):
        # Many empty strata: the half-flag prior must push the mean above the
        # observed rate, which is the inflation the pre-registration predicted.
        passive = {f"s{i}": (0, 1_000) for i in range(100)}
        passive["s0"] = (1, 1_000)
        weights = {k: 1.0 / len(passive) for k in passive}
        result = strata.posterior_composite(passive, weights, draws=4_000, seed=3)
        observed = 1000.0 * 1 / 100_000
        self.assertGreater(result["meanPer1000"], observed)


class BoundaryScan(unittest.TestCase):
    def _bins(self, spec):
        return [
            {"low": low, "passiveIntervals": pi, "passiveInclinationOnly": pf,
             "payloadIntervals": li, "payloadInclinationOnly": lf}
            for low, pi, pf, li, lf in spec
        ]

    def test_boundary_falls_out_where_the_rates_start_matching(self):
        bins = []
        for low in range(0, 180, 2):
            if low < 40:
                bins.append((low, 200_000, 20, 200_000, 20_000))  # strongly discriminating
            else:
                bins.append((low, 400_000, 400, 400_000, 400))    # matched
        found = strata.boundary_scan(self._bins(bins))
        self.assertEqual(found["boundaryDeg"], 40.0)

    def test_a_dominant_matched_region_can_dilute_the_boundary_downward(self):
        """A known, reported weakness of the registered pooled-region rule.

        The rule pools every bin at or above the candidate and tests the pooled
        ratio. When the matched high-inclination region carries far more
        exposure and far more flags than the discriminating low-inclination
        region, the pooled ratio stays inside the margin even at a candidate of
        zero degrees, and the rule returns zero. That is arithmetic, not a
        finding about the sky, and this test pins it so the results report can
        state it rather than discover it in review.
        """
        bins = []
        for low in range(0, 180, 2):
            if low < 40:
                bins.append((low, 200_000, 20, 200_000, 400))   # discriminating, but small
            else:
                bins.append((low, 400_000, 400, 400_000, 400))  # matched, and dominant
        found = strata.boundary_scan(self._bins(bins))
        self.assertEqual(found["boundaryDeg"], 0.0)
        # The per-candidate scan is what a reader must look at in that case: the
        # bin-level evidence is still in the table even when the summary is diluted.
        self.assertEqual(len(found["scan"]), 46)

    def test_no_boundary_is_reported_as_no_boundary_not_a_relaxed_margin(self):
        bins = [(low, 200_000, 20, 200_000, 400) for low in range(0, 180, 2)]
        found = strata.boundary_scan(self._bins(bins))
        self.assertIsNone(found["boundaryDeg"])

    def test_a_single_lucky_bin_cannot_set_the_boundary(self):
        # Matched only in one narrow window, discriminating above it: the
        # monotone-stability clause must refuse that window.
        bins = []
        for low in range(0, 180, 2):
            if 50 <= low < 54:
                bins.append((low, 400_000, 400, 400_000, 400))
            else:
                bins.append((low, 200_000, 20, 200_000, 400))
        found = strata.boundary_scan(self._bins(bins))
        self.assertIsNone(found["boundaryDeg"])

    def test_scan_covers_the_registered_grid(self):
        bins = self._bins([(low, 1_000, 0, 1_000, 0) for low in range(0, 180, 2)])
        found = strata.boundary_scan(bins)
        self.assertEqual(found["grid"][0], 0.0)
        self.assertEqual(found["grid"][-1], 90.0)
        self.assertEqual(len(found["scan"]), 46)


class RegisteredConstants(unittest.TestCase):
    """The pre-registration is the contract; these guard it from silent drift."""

    def test_margin_seed_and_target_match_the_registration(self):
        self.assertEqual(strata.EQUIVALENCE_MARGIN, 1.5)
        self.assertEqual(strata.SEED, 20260920)
        self.assertEqual(strata.BOOTSTRAP_DRAWS, 2000)
        self.assertEqual(strata.POSTERIOR_DRAWS, 20000)
        self.assertEqual(strata.TARGET_RATE_PER_INTERVAL, 0.001)
        self.assertEqual(strata.HIGH_INCLINATION_MIN_DEG, 30.0)
        self.assertEqual(strata.SSO_MIN_DEG, 96.0)
        self.assertEqual(strata.SSO_MAX_DEG, 100.0)

    def test_stratum_space_is_the_registered_768_cells(self):
        self.assertEqual(
            len(strata.PERIGEE_BANDS) * len(strata.INCLINATION_BANDS)
            * len(strata.ECCENTRICITY_CLASSES) * len(strata.CADENCE_CLASSES),
            768,
        )

    def test_perigee_bands_are_the_detectors_own(self):
        from pipeline.orbit_campaigns import _perigee_band
        for km, expected in ((250, "<300 km"), (400, "300-500 km"), (700, "500-800 km"),
                             (1000, "800-1200 km"), (1500, "1200-2000 km"), (35786, ">2000 km")):
            self.assertEqual(strata.perigee_band(km), _perigee_band(km))
            self.assertEqual(strata.perigee_band(km), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
