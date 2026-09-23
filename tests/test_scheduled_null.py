#!/usr/bin/env python3
"""Offline proofs for T22, the physics-scheduled null.

Registration section 5 lists twelve groups and every one is here. No archive,
no network, no clock: each test builds its own population from the module's own
fixture generator and asserts an arithmetic fact about it.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_names  # noqa: E402  the names, kept out of this file

from tools import geo_passive_control as gpc  # noqa: E402
from tools import proximity_geo as pg  # noqa: E402
from tools import scheduled_null as sn  # noqa: E402
from tools import trigger_alarm as ta  # noqa: E402
from tests.test_alarm_pattern import TestPolicyGuards  # noqa: E402

SRC = (_REPO / "tools" / "scheduled_null.py").read_text()

PLANTED_CENTRE = 30.0            # the acceleration is near its maximum here
PLANTED_SPACING = 0.1
PLANTED_APEX = 0.8               # a burn with margin: the apex clears the edge


def planted(band, noise=2e-5, years=3.0, sigma_acc=1e-5, offset=None,
            apex=PLANTED_APEX, centre=PLANTED_CENTRE, norad=800001):
    """One synthetic object flying a parabolic cycle with a PLANTED band."""
    if offset is None:
        offset = sn.median_offset_fraction(apex)
    series, burns, period = sn.synthetic_deadband_cycle(
        norad, centre, band, sn.slot_acceleration(centre),
        years=years, spacing_days=PLANTED_SPACING, noise=noise,
        apex_fraction=apex)
    chains = sn.chains_of(series)
    records = sn.pair_records(series, chains, deadband=band,
                              sigma_acceleration=sigma_acc,
                              centre_offset_fraction=offset)
    return series, burns, period, chains, records


# ---------------------------------------------------------------------------
# 1. The algebra of the root
# ---------------------------------------------------------------------------
class TestAlgebra(unittest.TestCase):

    def test_exit_edge_closed_form_both_signs(self):
        """Registration eq. (5): at Delta = 0, tau* = 2 |lambdadot| / |a|."""
        for a in (+1.7e-3, -1.7e-3):
            band = 0.02633
            sign = 1.0 if a > 0 else -1.0
            lam = sign * band                     # the burn is at the exit edge
            rate = -sign * 0.0090
            tau, edge, reason = sn.exit_time_days(lam, rate, a, 0.0, band)
            self.assertEqual(reason, "ok")
            self.assertAlmostEqual(tau, sn.edge_cycle_days(rate, a), places=9)
            self.assertAlmostEqual(tau, 2.0 * abs(rate) / abs(a), places=9)
            self.assertEqual(edge, int(sign))

    def test_optimal_one_burn_cycle_closed_form(self):
        """Registration eq. (6): tau* = 4 sqrt(D/|a|) for the optimal cycle."""
        for a in (+1.7006955627927864e-3, -1.7006955627927864e-3):
            band = 0.02633
            sign = 1.0 if a > 0 else -1.0
            lam = sign * band
            rate = -sign * 2.0 * math.sqrt(abs(a) * band)
            tau, _, reason = sn.exit_time_days(lam, rate, a, 0.0, band)
            self.assertEqual(reason, "ok")
            self.assertAlmostEqual(tau, sn.optimal_cycle_days(band, a), places=8)
            self.assertAlmostEqual(tau, 4.0 * math.sqrt(band / abs(a)), places=8)

    def test_apex_touches_the_far_edge_on_the_optimal_cycle(self):
        a, band = 1.7006955627927864e-3, 0.02633
        rate = -2.0 * math.sqrt(a * band)
        apex = -rate / a
        low = band + rate * apex + 0.5 * a * apex * apex
        self.assertAlmostEqual(low, -band, places=9)

    def test_outside_the_band_at_the_burn_is_named_not_dropped(self):
        tau, _, reason = sn.exit_time_days(0.5, -0.01, 1.7e-3, 0.0, 0.02633)
        self.assertTrue(math.isnan(tau))
        self.assertEqual(reason, "outside-band-at-burn")

    def test_the_registered_arithmetic_of_section_2_3(self):
        """A 14.00 d cycle needs an acceleration above the derived maximum."""
        needed = 16.0 * sn.DEADBAND_DEG / (14.00 ** 2)
        self.assertAlmostEqual(needed, 2.1493877551020407e-3, places=12)
        self.assertGreater(needed, sn.A_DEG_PER_DAY2)
        self.assertAlmostEqual(needed / sn.A_DEG_PER_DAY2, 1.2638, places=3)
        self.assertAlmostEqual(
            sn.optimal_cycle_days(sn.DEADBAND_DEG, sn.A_DEG_PER_DAY2),
            15.73882, places=4)


# ---------------------------------------------------------------------------
# 2. The constant-acceleration bound of eq. (2)
# ---------------------------------------------------------------------------
class TestConstantAccelerationBound(unittest.TestCase):

    def _integrate(self, u0_deg, rate0, days, step=0.001):
        u = math.radians(u0_deg)
        v = math.radians(rate0)
        a_rad = gpc.A_RAD_PER_DAY2
        n = int(days / step)
        for _ in range(n):
            acc = -a_rad * math.sin(2.0 * u)
            u += v * step + 0.5 * acc * step * step
            v += acc * step
        return math.degrees(u)

    @staticmethod
    def _relative_bound(u0):
        """Registration eq. (2)."""
        return 2.0 * abs(1.0 / math.tan(math.radians(2.0 * u0))) \
            * (2.0 * sn.DEADBAND_DEG) * math.pi / 180.0

    def test_eq_2_bounds_the_acceleration_change_across_the_band(self):
        band = sn.DEADBAND_DEG
        for u0 in (5.0, 10.0, 30.0, 45.0, 60.0, 80.0):
            lon = 75.1 + u0
            a0 = sn.slot_acceleration(lon)
            worst = max(abs(sn.slot_acceleration(lon + d) - a0) / abs(a0)
                        for d in (-2.0 * band, 2.0 * band))
            # (2) is the first-order term; at 45 degrees it vanishes and the
            # next Taylor term, 2 (2D pi/180)^2, is what remains.
            second = 2.0 * ((2.0 * band) * math.pi / 180.0) ** 2
            self.assertLessEqual(worst, self._relative_bound(u0) * 1.05 + second)

    def test_the_parabola_tracks_the_integration_over_one_cycle(self):
        band = sn.DEADBAND_DEG
        for u0 in (10.0, 30.0, 45.0):
            a = -sn.A_DEG_PER_DAY2 * math.sin(math.radians(2.0 * u0))
            rate0 = -math.copysign(2.0 * math.sqrt(abs(a) * band), a)
            span = 4.0 * math.sqrt(band / abs(a))
            exact = self._integrate(u0, rate0, span)
            parabola = u0 + rate0 * span + 0.5 * a * span * span
            self.assertLess(abs(exact - parabola), 0.1 * band)

    def test_the_bound_grows_toward_an_equilibrium(self):
        self.assertLess(self._relative_bound(10.0), 1e-2)
        self.assertGreater(self._relative_bound(1.0),
                           10.0 * self._relative_bound(10.0))


# ---------------------------------------------------------------------------
# 3. ASSERT THE BUG -- a planted sawtooth must be predicted to the tolerance
# ---------------------------------------------------------------------------
class TestPlantedSawtooth(unittest.TestCase):

    def test_the_detector_finds_one_chain_per_planted_burn(self):
        _, burns, _, chains, _ = planted(sn.DEADBAND_DEG)
        self.assertGreater(len(chains), 50)
        self.assertLessEqual(abs(len(chains) - burns.size), 2)

    def test_the_planted_epochs_are_recovered(self):
        series, burns, _, chains, _ = planted(sn.DEADBAND_DEG)
        found = np.asarray([c[0] for c in chains])
        errors = []
        for t in burns[:len(found)]:
            errors.append(abs(found - t).min() / pg.DAY_MS)
        self.assertLess(float(np.median(errors)), 2.0 * PLANTED_SPACING)

    def test_on_schedule_fraction_at_least_095_at_the_derived_tolerance(self):
        for band in (sn.DEADBAND_DEG, 0.0180):
            _, _, period, _, records = planted(band)
            admitted = [r for r in records if r["admitted"]]
            self.assertGreater(len(admitted), 40, f"band {band}")
            hit = sum(1 for r in admitted if r["onSchedule"])
            self.assertGreaterEqual(hit / len(admitted), 0.95, f"band {band}")
            observed = np.asarray([r["observedIntervalDays"] for r in admitted])
            self.assertAlmostEqual(float(np.median(observed)), period, delta=0.3)
            errors = np.asarray([r["errorDays"] for r in admitted])
            self.assertLess(abs(float(np.median(errors))), 3.0 * PLANTED_SPACING)

    def test_the_optimal_form_alone_would_miss_the_narrower_band(self):
        """Eq. (6) at the registered D, used instead of eq. (4), fails."""
        band = 0.0180
        _, _, period, _, records = planted(band)
        admitted = [r for r in records if r["admitted"]]
        wrong = sn.optimal_cycle_days(sn.DEADBAND_DEG, sn.slot_acceleration(PLANTED_CENTRE))
        window = float(np.median([r["windowDays"] for r in admitted]))
        self.assertGreater(abs(wrong - period), window)
        hit = sum(1 for r in admitted
                  if abs(r["observedIntervalDays"] - wrong) <= r["windowDays"])
        self.assertLess(hit / len(admitted), 0.05)

    def test_the_median_longitude_offset_is_the_derived_one(self):
        """Deviation V3, derived: median = centre - s k D, k = f - (1+f)/4."""
        self.assertAlmostEqual(sn.median_offset_fraction(1.0), 0.5, places=12)
        self.assertAlmostEqual(sn.median_offset_fraction(1.0 / 3.0), 0.0, places=12)
        band = sn.DEADBAND_DEG
        sign = math.copysign(1.0, sn.slot_acceleration(PLANTED_CENTRE))
        for apex in (0.6, 0.8, 1.0):
            _, _, _, _, records = planted(band, apex=apex)
            admitted = [r for r in records if r["admitted"]]
            self.assertGreater(len(admitted), 10, f"apex {apex}")
            offsets = [(r["medianLongitudeDeg"] - PLANTED_CENTRE) / band
                       for r in admitted]
            self.assertAlmostEqual(float(np.median(offsets)),
                                   -sign * sn.median_offset_fraction(apex),
                                   delta=0.10, msg=f"apex {apex}")

    def test_the_registered_median_alone_admits_nothing(self):
        """Why the sweep exists: k = 0 puts the burn outside its own band."""
        _, _, _, _, records = planted(sn.DEADBAND_DEG, offset=0.0, apex=1.0)
        admitted = [r for r in records if r["admitted"]]
        self.assertEqual(len(admitted), 0)
        reasons = {r["reason"] for r in records if not r["admitted"]}
        self.assertIn("outside-band-at-burn", reasons)

    def test_a_sub_millidegree_centre_error_destroys_the_schedule(self):
        """Why the centre sweep exists, and why it is the whole difficulty.

        The band is 0.02633 deg wide and the derived window is a third of a
        day. A centre mis-specified by 0.15 of a band -- four thousandths of a
        degree -- moves the predicted epoch by more than that window, and the
        on-schedule fraction goes from every pair to none.
        """
        band = sn.DEADBAND_DEG
        _, _, _, _, right = planted(band, apex=1.0, offset=0.50)
        _, _, _, _, wrong = planted(band, apex=1.0, offset=0.35)
        ok = [r for r in right if r["admitted"]]
        off = [r for r in wrong if r["admitted"]]
        self.assertGreater(len(ok), 20)
        self.assertGreater(len(off), 20)
        self.assertEqual(sum(r["onSchedule"] for r in ok), len(ok))
        self.assertLess(sum(r["onSchedule"] for r in off) / len(off), 0.10)
        shift = abs(float(np.median([r["errorDays"] for r in off]))
                    - float(np.median([r["errorDays"] for r in ok])))
        self.assertGreater(shift, 0.5 * float(np.median(
            [r["windowDays"] for r in ok])))

    def test_the_sign_rule_holds_on_every_planted_burn(self):
        _, _, _, _, records = planted(sn.DEADBAND_DEG)
        summary = sn.sign_summary(records)
        self.assertGreater(summary["chains"], 40)
        self.assertEqual(summary["fraction"], 1.0)


# ---------------------------------------------------------------------------
# 4. A librator must produce no on-schedule prediction
# ---------------------------------------------------------------------------
class TestLibrator(unittest.TestCase):

    def test_a_clean_librator_produces_no_burn_at_all(self):
        objects = gpc.synthetic_librators(sn.SEED, n=12, years=6.0)
        chains = sum(len(sn.chains_of(s)) for s in objects)
        self.assertEqual(chains, 0)

    def test_a_noisy_librator_is_not_on_schedule_above_its_own_null(self):
        objects = gpc.synthetic_librators(sn.SEED, n=40, years=8.0,
                                          sigma_n=0.0045)
        records = []
        for s in objects:
            records.extend(sn.pair_records(s, sn.chains_of(s),
                                           sigma_acceleration=3e-4))
        admitted = [r for r in records if r["admitted"]]
        if not admitted:
            self.assertEqual(len(admitted), 0)   # free motion, no reset at all
            return
        fraction = sum(1 for r in admitted if r["onSchedule"]) / len(admitted)
        null = sn.null_random_phase(admitted, draws=200)
        self.assertLessEqual(fraction, null["p95"] + 1e-12)

    def test_a_librator_does_not_pass_the_sign_rule_like_a_keeper(self):
        objects = gpc.synthetic_librators(sn.SEED, n=40, years=8.0,
                                          sigma_n=0.0045)
        records = []
        for s in objects:
            records.extend(sn.pair_records(s, sn.chains_of(s), predict=False))
        summary = sn.sign_summary(records)
        if summary["chains"] >= 20:
            half = (summary["wilson95"][1] - summary["wilson95"][0]) / 2.0
            self.assertLessEqual(summary["fraction"], 0.5 + half)


# ---------------------------------------------------------------------------
# 5. MC1 -- the propagation, checked by sampling
# ---------------------------------------------------------------------------
class TestPropagation(unittest.TestCase):

    CASE = dict(lambda_n=30.015, rate_n=-0.006, acceleration=1.70e-3,
                lambda_centre=30.0, deadband=0.02633)

    def test_linear_and_montecarlo_agree_within_the_registered_tolerance(self):
        tau, edge, reason = sn.exit_time_days(**self.CASE)
        self.assertEqual(reason, "ok")
        sigmas = dict(sigma_rate=2.0e-4, sigma_lambda_n=1.0e-3,
                      sigma_centre=6.0e-4, sigma_deadband=sn.SIGMA_DEADBAND_DEG,
                      sigma_acceleration=1.5e-4)
        linear, partials = sn.exit_time_sigma(
            tau, self.CASE["rate_n"], self.CASE["acceleration"], edge, **sigmas)
        mc = sn.exit_time_sigma_montecarlo(
            self.CASE["lambda_n"], self.CASE["rate_n"],
            self.CASE["acceleration"], self.CASE["lambda_centre"],
            self.CASE["deadband"], draws=4000, **sigmas)
        self.assertLess(abs(mc / linear - 1.0), sn.MC_TOLERANCE)

    def test_the_partials_match_the_registered_closed_forms_at_the_edge(self):
        a, band = 1.70e-3, 0.02633
        rate = -2.0 * math.sqrt(a * band)
        tau, edge, _ = sn.exit_time_days(band, rate, a, 0.0, band)
        _, partials = sn.exit_time_sigma(tau, rate, a, edge, 1.0, 1.0, 1.0,
                                         1.0, 1.0)
        self.assertAlmostEqual(abs(partials["rate"]), 2.0 / a, places=6)
        self.assertAlmostEqual(abs(partials["acceleration"]), tau / a, places=6)
        self.assertAlmostEqual(abs(partials["lambdaN"]), 1.0 / abs(rate), places=6)

    def test_the_tolerance_has_no_floor_and_no_grid(self):
        self.assertNotIn("max(2.0 * sigma", SRC)
        for banned in ("minimum_window", "WINDOW_FLOOR", "round(window"):
            self.assertNotIn(banned, SRC)


# ---------------------------------------------------------------------------
# 6/9. Statistics
# ---------------------------------------------------------------------------
class TestStatistics(unittest.TestCase):

    def test_wilson_against_hand_values(self):
        p, lo, hi = sn.wilson(14, 272)
        self.assertAlmostEqual(p, 0.05147058823529412, places=12)
        self.assertAlmostEqual(lo, 0.03090, places=4)
        self.assertAlmostEqual(hi, 0.08453, places=4)

    def test_wilson_on_an_empty_population_is_not_a_zero(self):
        p, lo, hi = sn.wilson(0, 0)
        self.assertTrue(math.isnan(p) and math.isnan(lo) and math.isnan(hi))

    def test_odds_ratio_against_hand_values(self):
        out = sn.odds_ratio(20, 80, 10, 90)
        self.assertAlmostEqual(out["oddsRatio"], (20 / 80) / (10 / 90), places=12)
        se = math.sqrt(1 / 20 + 1 / 80 + 1 / 10 + 1 / 90)
        self.assertAlmostEqual(out["ci"][0],
                               math.exp(math.log(out["oddsRatio"])
                                        - 1.959963984540054 * se), places=12)
        self.assertFalse(out["haldaneAnscombe"])

    def test_haldane_anscombe_is_applied_and_declared(self):
        out = sn.odds_ratio(0, 50, 10, 40)
        self.assertTrue(out["haldaneAnscombe"])
        self.assertTrue(math.isfinite(out["oddsRatio"]))

    def test_ols_recovers_a_planted_line(self):
        x = np.arange(10.0)
        y = 3.0 + 0.5 * x
        intercept, slope, si, ss = sn.ols_fit(x, y)
        self.assertAlmostEqual(intercept, 3.0, places=9)
        self.assertAlmostEqual(slope, 0.5, places=9)
        self.assertLess(si, 1e-9)
        self.assertLess(ss, 1e-9)


# ---------------------------------------------------------------------------
# 7. Imported, not reimplemented
# ---------------------------------------------------------------------------
class TestImportedIdentity(unittest.TestCase):

    def test_the_owned_names_are_the_owners(self):
        self.assertIs(sn.chains_of.__globals__["ta"].chain_flags, ta.chain_flags)
        self.assertIs(sn.chains_of.__globals__["ta"].flag_baselines,
                      ta.flag_baselines)
        self.assertEqual(sn.A_DEG_PER_DAY2, pg.LAMBDA_DDOT_MAX)
        self.assertEqual(sn.STABLE_LONGITUDES_DEG, pg.STABLE_LONGITUDES_DEG)
        self.assertEqual(sn.MERGE_DAYS, ta.MERGE_DAYS)
        self.assertEqual(sn.BASELINE_SAMPLES, pg.BURN_BASELINE_SAMPLES)

    def test_nothing_owned_elsewhere_is_redefined_here(self):
        for banned in ("def chain_flags", "def flag_baselines",
                       "def free_acceleration", "def mean_longitude_deg",
                       "def drift_rate_deg_per_day", "LAMBDA_DDOT_MAX ="):
            self.assertNotIn(banned, SRC,
                             f"{banned} is reimplemented rather than imported")

    def test_the_acceleration_function_is_the_owner(self):
        for lon in (-170.0, -60.0, 0.0, 30.0, 120.0):
            self.assertAlmostEqual(
                sn.slot_acceleration(lon),
                float(gpc.free_acceleration(np.asarray([lon]))[0]), places=15)


# ---------------------------------------------------------------------------
# 8. Causality
# ---------------------------------------------------------------------------
class TestCausality(unittest.TestCase):

    def test_no_element_at_or_after_the_observed_next_burn_enters_the_fit(self):
        series, _, _, chains, records = planted(sn.DEADBAND_DEG)
        for rec in records:
            if not rec["admitted"]:
                continue
            lo = int(np.searchsorted(series.epoch_ms, rec["tTrigMs"], side="left"))
            hi = lo + sn.BASELINE_SAMPLES
            self.assertLess(float(series.epoch_ms[hi - 1]), rec["tNextMs"])

    def test_a_pair_with_too_few_causal_elements_is_named_not_admitted(self):
        epoch = np.arange(0.0, 40.0, 0.5) * pg.DAY_MS
        drift = np.zeros(epoch.size)
        lam = np.zeros(epoch.size)
        series = sn.FixtureSeries(1, epoch, lam, drift)
        chains = [(epoch[0], epoch[1], 1, 0.02, 0.0),
                  (epoch[3], epoch[4], 1, -0.02, 0.0)]
        records = sn.pair_records(series, chains)
        self.assertEqual(records[0]["reason"], "too-few-element-sets")
        self.assertFalse(records[0]["admitted"])


# ---------------------------------------------------------------------------
# 10/11/12. The programme's standing guards
# ---------------------------------------------------------------------------
class TestGuards(unittest.TestCase):

    def test_no_intent_language(self):
        text = SRC.lower()
        for banned in TestPolicyGuards.BANNED:
            self.assertNotIn(banned, text, f"intent language {banned!r} present")

    def test_no_consumable_or_velocity_change_quantity(self):
        text = SRC.lower()
        for banned in ("delta_v", "deltav", "delta-v", "propellant", "fuel",
                       "isp", "remaining life", "dry mass"):
            self.assertNotIn(banned, text, f"{banned!r} present")

    def test_no_registry_or_ownership_column_is_read(self):
        text = SRC.lower()
        for banned in ("country", "owner", "operator_", "registry",
                       "object_name", "launch_site"):
            self.assertNotIn(banned, text, f"{banned!r} present")

    def test_no_model_or_tool_name(self):
        text = SRC.lower()
        self.assertEqual(vendor_names.hits(text), [],
                         "a product or assistant name is in the instrument")

    def test_nothing_is_written_to_a_shipped_tree(self):
        for banned in ('"src/', "'src/", '"data/', "'data/", '"public/',
                       "'public/", '"pipeline/', "'pipeline/"):
            self.assertNotIn(banned, SRC)

    def test_no_timer_no_transport(self):
        for banned in ("smtplib", "urllib.request", "requests.", "socket",
                       "webhook", "crontab", "systemd", "http://", "https://"):
            self.assertNotIn(banned, SRC, f"{banned!r} present")

    def test_a_labelled_gap_is_never_a_zero(self):
        """An empty arm must not be reported as a rate of zero."""
        self.assertTrue(all(math.isnan(v) for v in sn.wilson(0, 0)))
        summary = sn.sign_summary([])
        self.assertEqual(summary["chains"], 0)
        self.assertTrue(math.isnan(summary["fraction"]))


# ---------------------------------------------------------------------------
# The nulls and the summariser
# ---------------------------------------------------------------------------
class TestNulls(unittest.TestCase):

    def _admitted(self):
        _, _, _, _, records = planted(sn.DEADBAND_DEG)
        return [r for r in records if r["admitted"]]

    def test_the_random_phase_null_is_far_below_a_true_schedule(self):
        """Four slots, four accelerations, four cycle lengths: a draw from the
        pooled interval distribution is then not this object's own cycle."""
        admitted = []
        for k, centre in enumerate((30.0, 50.0, -30.0, 10.0)):
            _, _, _, _, records = planted(sn.DEADBAND_DEG, centre=centre,
                                          norad=800010 + k)
            admitted.extend(r for r in records if r["admitted"])
        measured = sum(1 for r in admitted if r["onSchedule"]) / len(admitted)
        null = sn.null_random_phase(admitted, draws=300)
        self.assertGreater(measured, null["p95"])

    def test_the_within_object_shuffle_needs_two_pairs(self):
        self.assertEqual(sn.null_shuffle_within_object([])["pairs"], 0)

    def test_summariser_counts_every_pair_and_names_every_reason(self):
        _, _, _, _, records = planted(sn.DEADBAND_DEG)
        out = sn.summarise(records, "fixture")
        self.assertEqual(out["pairs"], len(records))
        self.assertEqual(sum(out["reasons"].values()), len(records))


if __name__ == "__main__":
    unittest.main()
