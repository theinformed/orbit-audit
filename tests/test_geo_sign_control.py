"""Offline proofs for T28's GEO sign-and-persistence control.

Registration: docs/t28-geo-sign-control-preregistration-20260923.md, committed
alone at b56c8b6. No archive, no network, no catalogue is read here.

Two of these proofs ASSERT THE BUG, in the registration's own words:
  * a keeper whose ramp opposes its slot side must be EXCLUDED;
  * a librator sampled sparsely must still be classifiable or marked
    unclassifiable -- never silently admitted.
"""

import math
import unittest
from pathlib import Path

import numpy as np

from tools import geo_epoch_control as gce
from tools import geo_passive_control as gec
from tools import geo_sign_control as gsc
from tools import persistent_pairs as pp
from tools import proximity_geo as pg
from tools import trigger_alarm as ta

SIGMA_N = 6.038533519066339e-4


def _keeper(norad, slot_deg, years=6.0, sigma_n=0.0, oppose=True, seed=7):
    """A sawtooth about one slot at the measured 14.00-day cycle.

    `oppose=True` is a real station-keeper: the drift ramps in the direction
    the triaxial acceleration pushes, and each burn resets it AGAINST that
    acceleration -- the keeper sign. `oppose=False` inverts the burn, which is
    physically a free-running object and must not be excluded by clause (a).
    """
    ramp = float(gec.free_acceleration(np.asarray([slot_deg]))[0])
    if oppose is False:
        ramp = -ramp
    half = abs(ramp) * gec.EW_PERIOD_DAYS / 4.0
    t = np.arange(0.0, years * 365.25, gec.SAMPLE_SPACING_DAYS)
    cycle = np.mod(t, gec.EW_PERIOD_DAYS)
    d = -math.copysign(half, ramp) + ramp * cycle
    lam = slot_deg + np.cumsum(d - np.mean(d)) * gec.SAMPLE_SPACING_DAYS
    if sigma_n:
        d = d + np.random.default_rng(seed).normal(0.0, sigma_n, size=d.size)
    return gec._SynSeries(norad, (t + 20000.0) * gsc.DAY_MS,
                          pg.wrap180(lam), d)


class DerivedThresholds(unittest.TestCase):
    """Registration 3.3 and 3.4 -- every threshold is a closed form."""

    def test_dwell_amplitude_closed_form(self):
        u = gsc.dwell_amplitude_deg(0.1, 30.0)
        self.assertAlmostEqual(u, 15.755490497334758, places=10)
        self.assertAlmostEqual(gsc.U_DWELL_DEG, u, places=12)

    def test_a_librator_at_u_dwell_crosses_exactly_the_window(self):
        """At exactly u_dwell the excursion from the turning point is 0.1 deg
        in exactly 15.0 days -- the criterion, met with equality."""
        self.assertAlmostEqual(
            gsc.dwell_excursion_deg(gsc.U_DWELL_DEG, 15.0), 0.1, places=12)
        self.assertGreater(gsc.dwell_excursion_deg(gsc.U_DWELL_DEG + 1.0, 15.0),
                           0.1)
        self.assertLess(gsc.dwell_excursion_deg(gsc.U_DWELL_DEG - 1.0, 15.0),
                        0.1)

    def test_t11_amplitude_matches_its_own_box(self):
        u = gsc.dwell_amplitude_deg(pp.X_PAIR_PRIMARY_DEG,
                                    pp.D_PAIR_PRIMARY_DAYS,
                                    acceleration=pp.A_LONGITUDE_MAX_DEG_PER_DAY2)
        self.assertAlmostEqual(u, 1.7916608492359865, places=10)
        self.assertAlmostEqual(gsc.U_T11_DEG, u, places=12)
        self.assertLess(gsc.U_T11_DEG, gsc.U_DWELL_DEG)

    def test_t11_bound_brackets_the_measured_leaking_episodes(self):
        """T8e 6 reports every leaking T11 episode at implied u_max between
        0.87 and 1.25 deg. The bound was derived without reference to them."""
        self.assertLess(1.25, gsc.U_T11_DEG)

    def test_blind_band_is_two_sided(self):
        u_star = gsc.u_star_deg(SIGMA_N)
        self.assertAlmostEqual(u_star, 7.345799838852717, places=9)
        self.assertTrue(bool(gsc.sign_evaluable(np.asarray([45.0]), SIGMA_N)[0]))
        self.assertFalse(bool(gsc.sign_evaluable(np.asarray([u_star * 0.5]),
                                                 SIGMA_N)[0]))
        self.assertFalse(bool(gsc.sign_evaluable(
            np.asarray([90.0 - u_star * 0.5]), SIGMA_N)[0]))
        self.assertFalse(bool(gsc.sign_evaluable(np.asarray([-85.0]),
                                                 SIGMA_N)[0]))

    def test_blind_band_fraction_is_sixteen_percent(self):
        frac = 8.0 * gsc.u_star_deg(SIGMA_N) / 360.0
        self.assertAlmostEqual(frac, 0.16324, places=4)

    def test_cadence_limit_closed_form(self):
        s = abs(math.sin(2.0 * math.radians(20.0)))
        self.assertAlmostEqual(gsc.cadence_limit_days(s),
                               0.010 / (gsc.A_DEG_PER_DAY2 * s), places=12)
        self.assertEqual(gsc.cadence_limit_days(0.0), float("inf"))

    def test_archive_cadence_cannot_trip_v1_from_free_motion(self):
        """Registration 4.4: at the archive's median spacing the requirement
        is |sin 2u| > 1.236, which is impossible."""
        reach = 5.5 * gec.SAMPLE_SPACING_DAYS
        need = 0.010 / (gsc.A_DEG_PER_DAY2 * reach)
        self.assertGreater(need, 1.0)
        reach_max = 5.5 * gsc.MAX_GAP_DAYS
        need_max = 0.010 / (gsc.A_DEG_PER_DAY2 * reach_max)
        self.assertLess(need_max, 1.0)
        self.assertAlmostEqual(0.5 * math.degrees(math.asin(need_max)),
                               6.17, places=1)


class TheTwoAccelerationConstants(unittest.TestCase):
    def test_they_differ_in_the_fifth_significant_figure(self):
        """A finding, asserted so it cannot be forgotten: T11's box was built
        from a rounded acceleration. The T11 bound is derived with the constant
        that built the box; it enters no decision either way."""
        self.assertNotEqual(pp.A_LONGITUDE_MAX_DEG_PER_DAY2, pg.LAMBDA_DDOT_MAX)
        self.assertLess(abs(pp.A_LONGITUDE_MAX_DEG_PER_DAY2
                            - pg.LAMBDA_DDOT_MAX) / pg.LAMBDA_DDOT_MAX, 1e-4)
        self.assertAlmostEqual(
            gsc.dwell_amplitude_deg(pp.X_PAIR_PRIMARY_DEG,
                                    pp.D_PAIR_PRIMARY_DAYS,
                                    acceleration=pg.LAMBDA_DDOT_MAX),
            1.7915600436140493, places=10)


class TheSubstrateCadenceCeiling(unittest.TestCase):
    def test_the_substrate_cannot_evaluate_a_coarse_cadence(self):
        """v2's evaluability needs dt = 5.5 h <= 14.00 d, so the substrate is
        blind above h = 2.545 d -- a quantified form of T8e blind spot 3."""
        self.assertAlmostEqual(gec.MAX_BASELINE_SPAN_DAYS / 5.5, 2.5454545,
                               places=6)
        coarse = gsc._slow_librator(910501, 30.0, years=8.0, spacing_days=4.0,
                                    sigma_n=SIGMA_N)
        _rows, diag = gsc.classify_object(coarse, SIGMA_N, 2, "B-AMP")
        self.assertEqual(diag["epochs"], 0)


class ImportedNotReimplemented(unittest.TestCase):
    def test_source_does_not_redefine_what_it_imports(self):
        src = Path(gsc.__file__).read_text()
        for name in ("def find_epochs", "def v2_flags", "def flag_baselines",
                     "def chain_flags", "def free_acceleration",
                     "def nearest_stable", "def implied_s", "def reading",
                     "def count_t8a", "def count_t11", "def count_triggers"):
            self.assertNotIn(name, src, name)

    def test_the_constant_is_the_committed_one(self):
        self.assertEqual(gsc.A_DEG_PER_DAY2, pg.LAMBDA_DDOT_MAX)
        self.assertEqual(gsc.T8A_X_DEG, pg.X_PRIMARY_DEG)
        self.assertEqual(gsc.T8A_D_DAYS, pg.D_PRIMARY_DAYS)
        self.assertEqual(gsc.V1_FLOOR_DEG_PER_DAY, pg.BURN_FLOOR_DEG_PER_DAY)


class FirstIntegral(unittest.TestCase):
    def test_s_is_conserved_along_the_pendulum(self):
        ts, us, vs = gec._integrate_librators(np.asarray([0.0]),
                                              np.asarray([
                                                  math.sqrt(2.0 * gec.A_RAD_PER_DAY2)
                                                  * math.sin(math.radians(25.0))]),
                                              400.0)
        lam = np.degrees(us[:, 0]) + gec.STABLE_LONGITUDES_DEG[0]
        s, _u, _st = gce.implied_s(pg.wrap180(lam), np.degrees(vs[:, 0]))
        self.assertLess(float(np.max(s) - np.min(s)), 1e-6)
        self.assertAlmostEqual(float(gce.implied_u_max_deg(np.max(s))), 25.0,
                               places=4)


class SignOfOneChain(unittest.TestCase):
    def test_a_keeper_carries_the_keeper_sign(self):
        s = _keeper(800101, 30.0)
        signs, _chains = gsc.chain_signs(s, SIGMA_N)
        ev = [c for c in signs if c["sign"] != gsc.UNEVALUABLE]
        self.assertGreater(len(ev), 10)
        keeper = sum(1 for c in ev if c["sign"] == gsc.KEEPER)
        self.assertGreater(keeper / len(ev), 0.9)

    def test_free_motion_carries_the_free_sign(self):
        s = gsc._slow_librator(910101, 40.0, years=6.0, sigma_n=SIGMA_N)
        signs, _chains = gsc.chain_signs(s, SIGMA_N)
        ev = [c for c in signs if c["sign"] != gsc.UNEVALUABLE]
        if ev:
            free = sum(1 for c in ev if c["sign"] == gsc.FREE)
            self.assertGreater(free / len(ev), 0.5)

    def test_a_chain_in_the_blind_band_is_unevaluable_not_free(self):
        stable = gec.STABLE_LONGITUDES_DEG[0]
        s = _keeper(800102, stable + 1.0)
        signs, _chains = gsc.chain_signs(s, SIGMA_N)
        for c in signs:
            if c["uBaseDeg"] is not None and abs(c["uBaseDeg"]) < 3.0:
                self.assertEqual(c["sign"], gsc.UNEVALUABLE)
                self.assertEqual(c["reason"], "blind-band")


class TheBugsTheSuiteMustCatch(unittest.TestCase):
    """The two assertions the registration names in section 6, V6."""

    def test_bug_one_keeper_whose_ramp_opposes_its_slot_side_is_excluded(self):
        """A keeper at a slot well outside the blind band, whose every drift
        change carries the keeper sign, must yield ZERO asserted intervals in
        every arm and for every k."""
        for slot in (30.0, -40.0, 120.0):
            s = _keeper(800200 + int(abs(slot)), slot, sigma_n=SIGMA_N)
            signs, _c = gsc.chain_signs(s, SIGMA_N)
            ev = [c for c in signs if c["sign"] != gsc.UNEVALUABLE]
            self.assertGreater(len(ev), 5, f"slot {slot} produced no chains")
            self.assertGreater(sum(1 for c in ev if c["sign"] == gsc.KEEPER)
                               / len(ev), 0.9, f"slot {slot}")
            for arm in gsc.ARMS:
                for k in (2, 3):
                    rows, _d = gsc.classify_object(s, SIGMA_N, k, arm)
                    self.assertEqual(rows, [], f"slot {slot} arm {arm} k {k}")

    def test_bug_two_a_sparsely_sampled_librator_is_never_silently_admitted(self):
        """Sampled beyond the catalogue gap it must be UNCLASSIFIABLE with a
        named reason and contribute no exposure; sampled inside the gap it
        must be classifiable."""
        sparse = gsc._slow_librator(910201, 30.0, years=8.0, spacing_days=10.0,
                                    sigma_n=SIGMA_N)
        rows, diag = gsc.classify_object(sparse, SIGMA_N, 2, "B-AMP")
        self.assertEqual(rows, [])
        self.assertEqual(diag.get("unclassifiableReason"), "catalogue-gap")
        self.assertEqual(gsc.exposure_of(rows), (0, 0))

        dense = gsc._slow_librator(910202, 30.0, years=8.0, spacing_days=2.0,
                                   sigma_n=SIGMA_N)
        _rows_d, diag_d = gsc.classify_object(dense, SIGMA_N, 2, "B-AMP")
        self.assertGreater(diag_d["epochs"], 0)
        self.assertIsNone(diag_d.get("unclassifiableReason"))


class Causality(unittest.TestCase):
    def test_an_asserted_interval_begins_after_its_own_evidence(self):
        # sampled at 2.0 d, inside the substrate's 2.545 d ceiling but with a
        # baseline reach of 11 d, so free motion at this amplitude DOES trip
        # v1 -- which is the only way this fixture can carry evidence at all.
        s = gsc._slow_librator(910301, 45.0, years=10.0, spacing_days=2.0,
                               sigma_n=SIGMA_N)
        rows, _d = gsc.classify_object(s, SIGMA_N, 1, "A-NOAMP")
        self.assertTrue(rows, "the causality proof must not be vacuous")
        for r in rows:
            self.assertGreater(r["startMs"], r["evidenceEndMs"])
            self.assertGreaterEqual(r["evidenceEndMs"], r["evidenceStartMs"])
            self.assertGreater(r["endMs"], r["startMs"])

    def test_an_event_at_the_evidence_epoch_is_not_counted(self):
        rows = [{"norad": 1, "startMs": 1000.0 * gsc.DAY_MS,
                 "endMs": 1100.0 * gsc.DAY_MS, "days": 100.0}]
        iv = gsc._intervals(rows)
        before = [{"approacherNorad": 1, "targetNorad": 2,
                   "arrivalMs": 999.0 * gsc.DAY_MS}]
        inside = [{"approacherNorad": 1, "targetNorad": 2,
                   "arrivalMs": 1050.0 * gsc.DAY_MS}]
        self.assertEqual(gce.count_t8a(iv, before), 0)
        self.assertEqual(gce.count_t8a(iv, inside), 1)


class UnclassifiableIsNotAdmission(unittest.TestCase):
    def test_too_few_chains_yields_nothing_and_says_so(self):
        s = gsc._slow_librator(910401, 2.0, years=4.0, sigma_n=SIGMA_N)
        rows, diag = gsc.classify_object(s, SIGMA_N, 6, "B-AMP")
        self.assertEqual(rows, [])
        self.assertEqual(gsc.exposure_of(rows), (0, 0))
        self.assertGreaterEqual(diag["tooFewChains"] + diag["amplitude"]
                                + diag["noEpoch"] + diag["catalogueGap"], 1)

    def test_the_amplitude_clause_separates_the_two_arms(self):
        """The T8e leak case: free by clause (a), refused by clause (b)."""
        slow = gsc._slow_librator(910402, 3.5, years=14.0, sigma_n=SIGMA_N)
        rows_b, diag_b = gsc.classify_object(slow, SIGMA_N, 1, "B-AMP")
        self.assertEqual(rows_b, [])
        if diag_b["epochs"] and diag_b["chains"] >= 1:
            self.assertGreaterEqual(diag_b["amplitude"] + diag_b["tooFewChains"],
                                    1)


class Persistence(unittest.TestCase):
    def test_q_k_counts_windows_not_chains(self):
        seq = [{"sign": s} for s in
               [gsc.FREE, gsc.FREE, gsc.KEEPER, gsc.FREE, gsc.FREE, gsc.FREE]]
        prof = gsc.run_length_profile([seq])
        self.assertEqual(prof["chains"], 6)
        self.assertEqual(prof["freeSignChains"], 5)
        self.assertEqual(prof["qK"]["1"]["windows"], 6)
        self.assertEqual(prof["qK"]["1"]["allFree"], 5)
        self.assertEqual(prof["qK"]["2"]["windows"], 5)
        self.assertEqual(prof["qK"]["2"]["allFree"], 3)
        self.assertEqual(prof["qK"]["3"]["windows"], 4)
        self.assertEqual(prof["qK"]["3"]["allFree"], 1)
        self.assertEqual(prof["runLengthHistogram"], {"2": 1, "3": 1})

    def test_unevaluable_breaks_the_run(self):
        seq = [{"sign": s} for s in
               [gsc.FREE, gsc.UNEVALUABLE, gsc.FREE]]
        prof = gsc.run_length_profile([seq])
        self.assertEqual(prof["qK"]["2"]["allFree"], 0)

    def test_choose_k_takes_the_smallest_that_meets_the_bar(self):
        prof = {"qK": {"1": {"q": 0.20}, "2": {"q": 0.05},
                       "3": {"q": 0.008}, "4": {"q": 0.001},
                       "5": {"q": 0.0005}, "6": {"q": 0.0001}}}
        self.assertEqual(gsc.choose_k(prof), (3, False))
        prof2 = {"qK": {str(i): {"q": 0.5} for i in range(1, 7)}}
        self.assertEqual(gsc.choose_k(prof2), (6, True))

    def test_the_independence_model_is_printed_not_used(self):
        seq = [{"sign": gsc.FREE} for _ in range(10)]
        prof = gsc.run_length_profile([seq])
        self.assertAlmostEqual(prof["independenceModelPK"]["2"],
                               (1.0 - 0.8294) ** 2, places=12)
        self.assertEqual(prof["qK"]["2"]["q"], 1.0)


class ExposureArithmetic(unittest.TestCase):
    def test_object_days_and_pair_days(self):
        rows = [{"norad": 1, "startMs": 10.0 * gsc.DAY_MS,
                 "endMs": 19.0 * gsc.DAY_MS, "days": 9.0},
                {"norad": 2, "startMs": 15.0 * gsc.DAY_MS,
                 "endMs": 19.0 * gsc.DAY_MS, "days": 4.0}]
        obj_days, pair_days = gsc.exposure_of(rows)
        self.assertEqual(obj_days, 10 + 5)
        self.assertEqual(pair_days, 5)

    def test_a_zero_below_the_meaningful_zero_is_unevaluable(self):
        r = gce.reading(0, 100, 500, 8_000_000)
        self.assertEqual(r["verdict"], "UNEVALUABLE")
        self.assertGreater(r["meaningfulZeroExposure"], r["exposure"])


class SecondOrderModel(unittest.TestCase):
    def test_the_neglected_term_is_below_a_tenth_of_a_percent(self):
        """Blind spot 6: the parabolic dwell model against an integrated
        trajectory, over T8a's own 30-day window at u_dwell."""
        u0 = gsc.U_DWELL_DEG
        ts, us, _vs = gec._integrate_librators(np.asarray([u0]),
                                               np.asarray([0.0]), 15.0)
        exact = abs(float(np.degrees(us[-1, 0]) - u0))
        approx = gsc.dwell_excursion_deg(u0, float(ts[-1]))
        self.assertLess(abs(exact - approx) / approx, 1e-3)


if __name__ == "__main__":
    unittest.main()
