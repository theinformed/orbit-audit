#!/usr/bin/env python3
"""Offline tests for T8d's trigger-time instrument.

Every test runs without the archive and without the network.

The heart of the file is `TestLeakageAudit`, which discharges gate L of
`docs/trigger-alarm-preregistration-20260922.md` section 12: the trigger
feature vector must be bit-identical whether it is extracted from the full
series, from the series truncated at `t_trig`, or from a series whose
post-trigger element sets have been replaced by garbage. T8d's entire claim is
that its features exist at trigger time, and this is where that claim is
asserted rather than intended.

The policy guards IMPORT T8c's banned vocabulary rather than copying it, so
the two lists cannot drift apart.
"""

from __future__ import annotations

import inspect
import json
import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import trigger_alarm as ta  # noqa: E402
import alarm_pattern as ap  # noqa: E402
import proximity_geo as pg  # noqa: E402

sys.path.insert(0, str(_REPO / "tests"))
from test_alarm_pattern import TestPolicyGuards as _T8cGuards  # noqa: E402

DAY = ta.DAY_MS


def _series(norad, epochs_days, drift, lam0=0.0, inc=0.0):
    """A Series with a chosen drift history, built through T8a's own
    constructor so the geometry is the registered geometry. lambda is set
    directly afterwards, exactly as T8c's fixtures do."""
    epochs = np.asarray(epochs_days, dtype=np.float64) * DAY
    drift = np.asarray(drift, dtype=np.float64)
    mm = (drift + pg.OMEGA_E_DEG_PER_DAY) / 360.0
    n = epochs.size
    zeros = np.zeros(n)
    s = pg.Series(norad, epochs.astype(np.int64), mm, zeros,
                  np.full(n, float(inc)), zeros, zeros, zeros)
    # lambda integrated from the drift history, so the series is physically
    # self-consistent rather than flat.
    dt = np.diff(epochs) / DAY
    lam = np.empty(n)
    lam[0] = lam0
    lam[1:] = lam0 + np.cumsum(0.5 * (drift[:-1] + drift[1:]) * dt)
    s.lam = pg.wrap180(lam)
    s.lam_unwrapped = lam
    return s


def _quiet_then_burn(norad, n_quiet=40, n_after=400, quiet=0.001, burn=0.20,
                     lam0=10.0, inc=0.05, start_day=0.0):
    days = np.arange(n_quiet + n_after, dtype=np.float64) + start_day
    d = np.full(days.size, quiet)
    d[n_quiet:] = burn
    return _series(norad, days, d, lam0=lam0, inc=inc)


SIGMA_N = 6.038533519066339e-4


class TestRegisteredConstants(unittest.TestCase):
    """prereg 3, 4, 11: the numbers that may not change after a result."""

    def test_the_feature_vector_is_the_registered_nineteen_plus_three(self):
        self.assertEqual(len(ta.FEATURE_NAMES), 22)
        ind = [n for n in ta.FEATURE_NAMES if n.startswith("miss_")]
        self.assertEqual(len(ind), 3)
        self.assertEqual(len(ta.FEATURE_NAMES) - len(ind), 19)

    def test_feature_names_are_unique_and_in_registration_order(self):
        self.assertEqual(len(set(ta.FEATURE_NAMES)), len(ta.FEATURE_NAMES))
        self.assertEqual(ta.FEATURE_NAMES[0], "init_drift_change_mag")
        self.assertEqual(ta.FEATURE_NAMES[18], "fwd_plane_compatible_slots")

    def test_the_constants_are_t8a_s_own_and_are_not_reinvented(self):
        self.assertEqual(ta.MERGE_DAYS, pg.MAX_GAP_DAYS)
        self.assertEqual(ta.CONFIRM_DAYS, ta.MERGE_DAYS)
        self.assertEqual(ta.H_DAYS, pg.T_LOOK_DAYS)
        self.assertEqual(ta.DWELL_DAYS, pg.D_PRIMARY_DAYS)
        self.assertEqual(ta.SLOT_MATCH_DEG, pg.X_PRIMARY_DEG)
        self.assertEqual(ta.SLOT_MIN_HISTORY_DAYS, pg.STATION_MIN_DAYS)
        self.assertAlmostEqual(ta.SLOT_DRIFT_FLOOR, 0.02, places=12)
        self.assertEqual(ta.LAMBDA_DDOT, pg.LAMBDA_DDOT_MAX)

    def test_the_gate_bars_are_the_registered_numbers(self):
        self.assertEqual(ta.GATE_A_MIN_TRIGGERS, 200)
        self.assertEqual(ta.GATE_A_MIN_POSITIVES, 50)
        self.assertEqual(ta.GATE_D_MIN_CLASS, 20)
        self.assertEqual(ta.GATE_E_JACCARD, 0.5)
        self.assertEqual(ta.GATE_F_ARI, 0.5)
        self.assertEqual(ta.GATE_G_BAR, ap.GATE_P_BAR)
        self.assertEqual(ta.GATE_W_DEG, 2.0)
        self.assertEqual(ta.HYBRID_WEIGHT, 0.5)

    def test_the_hybrid_bar_is_t8c_s_own_and_the_baseline_is_t8a_s(self):
        self.assertAlmostEqual(ta.T8A_SKILL_LOITER, 0.137)
        self.assertAlmostEqual(ta.GATE_G_BAR, 0.157)


class TestResonanceDerivation(unittest.TestCase):
    """prereg 4.6: the propagation is derived, not asserted."""

    def test_the_single_harmonic_recovers_t8a_s_stable_longitudes(self):
        """sin(2(lam - 75.1)) = 0 with a restoring sign at 75.1 and -104.9;
        T8a registered (75.1, -104.7) independently."""
        for stable in pg.STABLE_LONGITUDES_DEG:
            self.assertLess(abs(ta._lam_ddot(stable)), 2e-5, stable)
            # restoring: a small displacement is pushed back
            self.assertLess(ta._lam_ddot(stable + 0.5), 0.0)
            self.assertGreater(ta._lam_ddot(stable - 0.5), 0.0)

    def test_the_unstable_points_repel(self):
        for unstable in (165.1, -14.9):
            self.assertLess(abs(ta._lam_ddot(unstable)), 2e-5)
            self.assertGreater(ta._lam_ddot(unstable + 0.5), 0.0)

    def test_K_is_T8a_s_constant_at_the_expected_magnitude(self):
        self.assertAlmostEqual(ta.LAMBDA_DDOT, 1.70e-3, places=4)

    def test_the_linearisation_the_registration_rejects_is_really_wrong(self):
        """prereg 4.6: a constant-drift propagation omits a term of order
        0.5 K H^2 = 27.5 deg at H = 180 d. If it did not, the RK4 would be
        needless ceremony and this test would say so."""
        omitted = 0.5 * ta.LAMBDA_DDOT * ta.H_DAYS ** 2
        self.assertGreater(omitted, 20.0)
        path = ta.propagate(0.0, 0.0)            # starts at rest, off a node
        self.assertGreater(abs(path[-1] - path[0]), 5.0)

    def test_the_one_day_step_matches_a_tenth_day_step(self):
        """prereg 4.6: step-size adequacy, asserted rather than assumed."""
        for lam0, d0 in ((10.0, 0.2), (-60.0, -0.5), (120.0, 0.02)):
            coarse = ta.propagate(lam0, d0, step_days=1.0)[-1]
            fine = ta.propagate(lam0, d0, step_days=0.1)[-1]
            self.assertLess(abs(coarse - fine), 1e-3, (lam0, d0))

    def test_a_stationary_object_at_a_stable_point_stays(self):
        path = ta.propagate(75.1, 0.0)
        self.assertLess(float(np.abs(path - 75.1).max()), 1e-6)


class TestSlotReaching(unittest.TestCase):
    def test_a_fast_drifter_does_not_step_over_a_narrow_slot(self):
        """A 5 deg/day path sampled daily would miss a 0.1 deg window if the
        segments were tested by their endpoints alone."""
        path = np.arange(0.0, 181.0) * 5.0
        reached, day, dist, total = ta.slots_reached(path, np.array([12.3]))
        self.assertTrue(bool(reached[0]))
        # the first pass is when the path ENTERS the 0.1 deg band, not when
        # it reaches the centre of it
        self.assertAlmostEqual(day[0], (12.3 - 0.1) / 5.0, places=6)
        self.assertAlmostEqual(total, 900.0, places=6)

    def test_a_slot_outside_the_reach_is_not_reached(self):
        path = np.arange(0.0, 181.0) * 0.01          # 1.8 deg of travel
        reached, _d, _p, _t = ta.slots_reached(path, np.array([90.0]))
        self.assertFalse(bool(reached[0]))

    def test_the_wrap_is_handled(self):
        path = np.arange(0.0, 181.0) * 2.0           # 0 -> 360 deg unwrapped
        reached, day, _p, _t = ta.slots_reached(path, np.array([-179.0]))
        self.assertTrue(bool(reached[0]))
        self.assertAlmostEqual(day[0], (181.0 - 0.1) / 2.0, places=6)

    def test_first_pass_is_the_earliest_pass(self):
        path = np.arange(0.0, 181.0) * 1.0
        reached, day, dist, _t = ta.slots_reached(
            path, np.array([10.0, 100.0, 40.0]))
        self.assertTrue(bool(reached.all()))
        self.assertLess(day[0], day[2])
        self.assertLess(day[2], day[1])
        for j in range(3):
            self.assertAlmostEqual(dist[j], day[j], places=6)

    def test_no_slots_is_not_an_error(self):
        path = np.arange(0.0, 181.0)
        reached, day, dist, total = ta.slots_reached(path, np.zeros(0))
        self.assertEqual(reached.size, 0)
        self.assertAlmostEqual(total, 0.0)


class TestFlagChaining(unittest.TestCase):
    def test_a_multi_stage_burn_is_one_trigger(self):
        flags = np.array([0.0, 2.0, 4.0, 40.0, 41.0]) * DAY
        sizes = np.array([0.01, 0.02, 0.03, 0.05, 0.06])
        bases = np.zeros(5)
        chains = ta.chain_flags(flags, sizes, bases)
        self.assertEqual(len(chains), 2)
        self.assertEqual(chains[0][2], 3)
        self.assertEqual(chains[1][2], 2)
        self.assertAlmostEqual(chains[0][3], 0.03)     # the LAST flag's size

    def test_a_gap_of_exactly_five_days_still_chains(self):
        flags = np.array([0.0, 5.0]) * DAY
        chains = ta.chain_flags(flags, np.array([0.01, 0.01]), np.zeros(2))
        self.assertEqual(len(chains), 1)

    def test_a_gap_just_over_five_days_splits(self):
        flags = np.array([0.0, 5.0 + 1e-6]) * DAY
        chains = ta.chain_flags(flags, np.array([0.01, 0.01]), np.zeros(2))
        self.assertEqual(len(chains), 2)

    def test_the_baseline_is_read_from_t8a_s_own_array(self):
        """prereg 4.1: d_base is the array `drift_change_flags` already
        computes, not a second definition."""
        s = _quiet_then_burn(90001)
        flags, sizes, bases = ta.flag_baselines(s, SIGMA_N)
        t8a_flags, t8a_sizes = pg.drift_change_flags(s, SIGMA_N)
        np.testing.assert_array_equal(flags, t8a_flags)
        np.testing.assert_allclose(sizes, t8a_sizes, rtol=0, atol=0)
        self.assertTrue(np.all(np.isfinite(bases)))
        self.assertAlmostEqual(float(bases[0]), 0.001, places=9)

    def test_the_announce_time_charges_the_confirmation_delay(self):
        tr = ta.Trigger(1, 0.0, 10.0 * DAY, 2, 0.2, 0.001)
        self.assertAlmostEqual(tr.tAnnounce, 15.0 * DAY)

    def test_eligibility_is_the_registered_drift_floor(self):
        self.assertTrue(ta.Trigger(1, 0, 0, 1, 0.2, 0.019).eligible)
        self.assertFalse(ta.Trigger(1, 0, 0, 1, 0.2, 0.021).eligible)
        self.assertFalse(ta.Trigger(1, 0, 0, 1, 0.2, float("nan")).eligible)


class TestOccupancy(unittest.TestCase):
    def _world(self):
        # a stationed neighbour, a drifter, and a newcomer with no history
        stationed = _series(1001, np.arange(0.0, 200.0), np.full(200, 0.0005),
                            lam0=30.0, inc=0.1)
        drifter = _series(1002, np.arange(0.0, 200.0), np.full(200, 0.30),
                          lam0=-50.0, inc=0.2)
        newcomer = _series(1003, np.arange(180.0, 200.0), np.full(20, 0.0005),
                           lam0=60.0, inc=3.0)
        return {s.norad: s for s in (stationed, drifter, newcomer)}

    def test_the_registered_definition_selects_only_the_stationed_object(self):
        world = self._world()
        lons, incs = ta.occupancy_reference(world, 195.0 * DAY, exclude_norad=9)
        self.assertEqual(lons.size, 1)
        self.assertAlmostEqual(float(lons[0]), 30.0 + 0.0005 * 195.0, places=3)
        self.assertAlmostEqual(float(incs[0]), 0.1, places=9)

    def test_the_sweep_agrees_with_the_reference_exactly(self):
        world = self._world()
        sweep = ta.OccupancySweep(world)
        for t_days in (35.0, 100.0, 190.0, 199.0):
            ref = ta.occupancy_reference(world, t_days * DAY, exclude_norad=1002)
            got = sweep.at(t_days * DAY, exclude_norad=1002)
            np.testing.assert_allclose(np.sort(got[0]), np.sort(ref[0]),
                                       rtol=0, atol=1e-12)
            self.assertEqual(got[0].size, ref[0].size)

    def test_a_stale_object_is_not_an_occupied_slot(self):
        world = self._world()
        lons, _i = ta.occupancy_reference(world, 210.0 * DAY, exclude_norad=9)
        self.assertEqual(lons.size, 0)

    def test_the_excluded_object_is_never_its_own_neighbour(self):
        world = self._world()
        lons, _i = ta.occupancy_reference(world, 195.0 * DAY, exclude_norad=1001)
        self.assertEqual(lons.size, 0)


class TestLeakageAudit(unittest.TestCase):
    """prereg 12 / gate L. THE test of this study.

    If any of these fails the study is void -- not caveated, void.
    """

    def _scene(self):
        approacher = _quiet_then_burn(2001, lam0=10.0)
        neighbour = _series(2002, np.arange(0.0, 440.0), np.full(440, 0.0004),
                            lam0=22.0, inc=0.06)
        far = _series(2003, np.arange(0.0, 440.0), np.full(440, 0.0004),
                      lam0=-120.0, inc=9.0)
        world = {s.norad: s for s in (approacher, neighbour, far)}
        flags, sizes, bases = ta.flag_baselines(approacher, SIGMA_N)
        chains = ta.chain_flags(flags, sizes, bases)
        self.assertTrue(chains, "the fixture must produce a flag chain")
        c = chains[0]
        trig = ta.Trigger(2001, c[0], c[1], c[2], c[3], c[4])
        return world, trig

    @staticmethod
    def _truncate(series, t_ms):
        k = int(np.searchsorted(series.epoch_ms, t_ms, side="right"))
        s = object.__new__(pg.Series)
        s.norad = series.norad
        s.epoch_ms = series.epoch_ms[:k].copy()
        s.lam = series.lam[:k].copy()
        s.lam_unwrapped = series.lam_unwrapped[:k].copy()
        s.drift = series.drift[:k].copy()
        s.ecc = series.ecc[:k].copy()
        s.inc = series.inc[:k].copy()
        s.day_index = None
        s.grid_lo = None
        s.grid = None
        return s

    @staticmethod
    def _mutate(series, t_ms):
        k = int(np.searchsorted(series.epoch_ms, t_ms, side="right"))
        s = object.__new__(pg.Series)
        s.norad = series.norad
        s.epoch_ms = series.epoch_ms.copy()
        s.lam = series.lam.copy()
        s.lam_unwrapped = series.lam_unwrapped.copy()
        s.drift = series.drift.copy()
        s.ecc = series.ecc.copy()
        s.inc = series.inc.copy()
        s.day_index = None
        s.grid_lo = None
        s.grid = None
        s.drift[k:] *= 17.0
        s.lam[k:] = pg.wrap180(s.lam[k:] + 123.0)
        s.lam_unwrapped[k:] += 123.0
        s.inc[k:] += 11.0
        return s

    def _vector(self, world, trig):
        occ = ta.occupancy_reference(world, trig.tTrig, trig.norad)
        view = ta.causal_view(world[trig.norad], trig.tTrig)
        f = ta.trigger_features(trig, view, occ)
        return [f[n] for n in ta.FEATURE_NAMES]

    def test_truncating_the_series_at_the_trigger_changes_nothing(self):
        world, trig = self._scene()
        full = self._vector(world, trig)
        cut = {n: self._truncate(s, trig.tTrig) for n, s in world.items()}
        truncated = self._vector(cut, trig)
        for name, a, b in zip(ta.FEATURE_NAMES, full, truncated):
            if isinstance(a, float) and math.isnan(a):
                self.assertTrue(math.isnan(b), name)
            else:
                self.assertEqual(a, b, f"{name} moved when the future was cut")

    def test_replacing_the_future_with_garbage_changes_nothing(self):
        world, trig = self._scene()
        full = self._vector(world, trig)
        bad = {n: self._mutate(s, trig.tTrig) for n, s in world.items()}
        mutated = self._vector(bad, trig)
        for name, a, b in zip(ta.FEATURE_NAMES, full, mutated):
            if isinstance(a, float) and math.isnan(a):
                self.assertTrue(math.isnan(b), name)
            else:
                self.assertEqual(a, b, f"{name} read the future")

    def test_the_mutation_really_would_have_been_visible(self):
        """A leakage test that a no-op would pass is worthless: assert the
        garbage is loud enough to move a feature that DID read it."""
        world, trig = self._scene()
        bad = {n: self._mutate(s, trig.tTrig) for n, s in world.items()}
        after = ta.causal_view(bad[2001], trig.tTrig + 100 * DAY)
        before = ta.causal_view(world[2001], trig.tTrig + 100 * DAY)
        self.assertGreater(float(np.abs(after.drift[-1] - before.drift[-1])), 1.0)
        self.assertGreater(float(np.abs(after.inc[-1] - before.inc[-1])), 10.0)

    def test_the_causal_view_holds_nothing_after_the_trigger(self):
        world, trig = self._scene()
        view = ta.causal_view(world[2001], trig.tTrig)
        self.assertTrue(np.all(view.epoch_ms <= trig.tTrig))
        self.assertGreater(view.epoch_ms.size, 0)

    def test_no_feature_name_is_a_post_trigger_quantity(self):
        for name in ta.FEATURE_NAMES:
            low = name.lower()
            for bad in ta.FORBIDDEN_PREFIXES:
                self.assertFalse(low.startswith(bad), name)
            for bad in ta.FORBIDDEN_SUBSTRINGS:
                self.assertNotIn(bad, low, name)

    def test_no_feature_path_calls_a_validation_only_function(self):
        """prereg 12: the propagator check reads post-trigger elements BY
        DESIGN and is quarantined behind a `validate_` name."""
        for fn in (ta.trigger_features, ta.attach_cadence, ta.propagate,
                   ta.slots_reached, ta.occupancy_reference,
                   ta.OccupancySweep.at, ta.causal_view, ta.feature_matrix):
            src = inspect.getsource(fn)
            self.assertNotIn("validate_", src, f"{fn.__name__} calls a validator")

    def test_the_feature_extractor_receives_a_causal_view_and_nothing_else(self):
        sig = list(inspect.signature(ta.trigger_features).parameters)
        self.assertEqual(sig[:3], ["trigger", "view", "occupancy"])
        src = inspect.getsource(ta.trigger_features)
        for forbidden in ("series_by_norad", "events", "arrivalMs", "loiterDays"):
            self.assertNotIn(forbidden, src)


class TestFeatureSemantics(unittest.TestCase):
    def setUp(self):
        self.world, self.trig = TestLeakageAudit()._scene()
        occ = ta.occupancy_reference(self.world, self.trig.tTrig, self.trig.norad)
        self.f = ta.trigger_features(
            self.trig, ta.causal_view(self.world[2001], self.trig.tTrig), occ)

    def test_the_drift_change_magnitude_is_the_burn(self):
        self.assertAlmostEqual(self.f["init_drift_change_mag"], 0.199, places=3)

    def test_the_sign_is_eastward_for_a_positive_drift(self):
        self.assertEqual(self.f["trig_drift_sign"], 1.0)

    def test_the_baseline_is_the_quiet_drift(self):
        self.assertAlmostEqual(self.f["trig_baseline_drift_abs"], 0.001, places=6)

    def test_the_abruptness_uses_the_half_day_floor_when_the_ramp_is_zero(self):
        f = dict(self.f)
        self.assertTrue(np.isfinite(f["init_abruptness"]))
        self.assertGreater(f["init_abruptness"], 0.0)

    def test_the_nearest_occupied_slot_is_the_neighbour(self):
        occ = ta.occupancy_reference(self.world, self.trig.tTrig, self.trig.norad)
        view = ta.causal_view(self.world[2001], self.trig.tTrig)
        expected = float(np.min(np.abs(pg.wrap180(occ[0] - view.lam[-1]))))
        self.assertEqual(occ[0].size, 2)          # the neighbour and the far one
        self.assertAlmostEqual(self.f["ctx_nearest_occupied_deg"], expected,
                               places=12)
        self.assertLess(self.f["ctx_nearest_occupied_deg"], 15.0)

    def test_the_forward_block_reaches_the_neighbour_and_not_the_far_object(self):
        self.assertGreaterEqual(self.f["fwd_slots_reached"], 1.0)
        self.assertTrue(np.isfinite(self.f["fwd_days_to_first_slot"]))
        self.assertGreater(self.f["fwd_path_length_deg"], 30.0)

    def test_plane_compatibility_screens_on_inclination(self):
        self.assertGreaterEqual(self.f["fwd_plane_compatible_slots"], 1.0)
        self.assertLessEqual(self.f["fwd_plane_compatible_slots"],
                             self.f["fwd_slots_reached"])

    def test_the_indicators_are_zero_one(self):
        for n in ("miss_ramp", "miss_fwd_slot"):
            self.assertIn(self.f[n], (0.0, 1.0))

    def test_an_empty_view_returns_all_nan_and_does_not_raise(self):
        empty = ta.causal_view(self.world[2001], -1.0)
        f = ta.trigger_features(self.trig, empty, (np.zeros(0), np.zeros(0)))
        self.assertTrue(all(math.isnan(v) for v in f.values()))


class TestCadence(unittest.TestCase):
    def test_prior_events_are_cut_at_loiter_end_not_arrival(self):
        """prereg 4.4: an event is not KNOWN to have happened until its
        30-day dwell has been observed."""
        t = 1000.0 * DAY
        triggers = [ta.Trigger(7, t, t, 1, 0.2, 0.001)]
        feats = [{n: float("nan") for n in ta.FEATURE_NAMES}]
        events = [{"approacherNorad": 7, "targetNorad": 8,
                   "arrivalMs": 990.0 * DAY, "loiterEndMs": 1020.0 * DAY},
                  {"approacherNorad": 7, "targetNorad": 9,
                   "arrivalMs": 900.0 * DAY, "loiterEndMs": 930.0 * DAY}]
        ta.attach_cadence(triggers, feats, events)
        self.assertEqual(feats[0]["cad_prior_events"], 1.0)
        self.assertEqual(feats[0]["cad_prior_targets"], 1.0)

    def test_the_first_trigger_has_no_previous_one(self):
        t0, t1 = 100.0 * DAY, 400.0 * DAY
        triggers = [ta.Trigger(7, t0, t0, 1, 0.2, 0.001),
                    ta.Trigger(7, t1, t1, 1, 0.2, 0.001)]
        feats = [{n: float("nan") for n in ta.FEATURE_NAMES} for _ in triggers]
        ta.attach_cadence(triggers, feats, [])
        self.assertTrue(math.isnan(feats[0]["cad_days_since_prev_trigger"]))
        self.assertEqual(feats[0]["miss_prev_trigger"], 1.0)
        self.assertEqual(feats[0]["cad_prior_triggers"], 0.0)
        self.assertAlmostEqual(feats[1]["cad_days_since_prev_trigger"], 300.0)
        self.assertEqual(feats[1]["cad_prior_triggers"], 1.0)


class TestOutcomes(unittest.TestCase):
    def _bits(self, arrival_days, flag_day, last_day=1000.0):
        s = _series(11, np.arange(0.0, last_day), np.full(int(last_day), 0.001))
        trig = ta.Trigger(11, flag_day * DAY, flag_day * DAY, 1, 0.2, 0.001)
        ev = [{"approacherNorad": 11, "targetNorad": 12,
               "initiatingFlagMs": flag_day * DAY,
               "transferStartMs": flag_day * DAY,
               "arrivalMs": arrival_days * DAY, "loiterDays": 40.0,
               "loiterEndMs": (arrival_days + 40.0) * DAY}]
        return ta.resolve_outcomes([trig], ev, {11: s})[0]

    def test_o1_uses_t8a_s_own_attribution(self):
        rec = self._bits(arrival_days=150.0, flag_day=100.0)
        self.assertTrue(rec["o1Positive"])
        self.assertAlmostEqual(rec["o1ArrivalDays"], 150.0 - 105.0)

    def test_an_unresolvable_trigger_is_not_a_negative(self):
        rec = self._bits(arrival_days=150.0, flag_day=900.0, last_day=1000.0)
        self.assertFalse(rec["resolvable"])

    def test_an_arrival_before_the_announce_is_flagged_not_hidden(self):
        rec = self._bits(arrival_days=102.0, flag_day=100.0)
        self.assertTrue(rec["o1Positive"])
        self.assertLess(rec["o1ArrivalDays"], 0.0)

    def test_a_flag_outside_the_chain_is_not_a_match(self):
        s = _series(11, np.arange(0.0, 1000.0), np.full(1000, 0.001))
        trig = ta.Trigger(11, 100.0 * DAY, 100.0 * DAY, 1, 0.2, 0.001)
        ev = [{"approacherNorad": 11, "targetNorad": 12,
               "initiatingFlagMs": 300.0 * DAY, "transferStartMs": 300.0 * DAY,
               "arrivalMs": 400.0 * DAY, "loiterDays": 40.0,
               "loiterEndMs": 440.0 * DAY}]
        rec = ta.resolve_outcomes([trig], ev, {11: s})[0]
        self.assertFalse(rec["o1Positive"])


class TestStatistics(unittest.TestCase):
    def test_wilson_brackets_the_point_estimate(self):
        lo, hi = ta.wilson(487, 1483)
        self.assertLess(lo, 487 / 1483)
        self.assertGreater(hi, 487 / 1483)
        self.assertAlmostEqual(lo, 0.3050, places=3)
        self.assertAlmostEqual(hi, 0.3529, places=3)

    def test_wilson_never_leaves_the_unit_interval(self):
        for k, n in ((0, 5), (5, 5), (0, 1), (1, 1), (1, 1000)):
            lo, hi = ta.wilson(k, n)
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)

    def test_wilson_of_nothing_is_not_a_zero(self):
        lo, hi = ta.wilson(0, 0)
        self.assertTrue(math.isnan(lo) and math.isnan(hi))

    def test_a_perfect_predictor_scores_one_and_the_base_rate_scores_zero(self):
        y = [1, 1, 0, 0, 1, 0, 1, 0]
        grp = [1, 1, 2, 2, 3, 3, 4, 4]
        base = [0.5] * 8
        self.assertAlmostEqual(ta.brier_skill(y, y, base, grp)["skill"], 1.0)
        self.assertAlmostEqual(ta.brier_skill(y, base, base, grp)["skill"], 0.0)

    def test_a_worse_than_base_predictor_scores_negative(self):
        y = [1, 0, 1, 0]
        grp = [1, 1, 2, 2]
        res = ta.brier_skill(y, [0.0, 1.0, 0.0, 1.0], [0.5] * 4, grp)
        self.assertLess(res["skill"], 0.0)

    def test_auc_is_a_half_for_a_constant_and_one_for_a_perfect_rank(self):
        y = [1, 0, 1, 0]
        self.assertAlmostEqual(ta.auc(y, [0.5] * 4), 0.5)
        self.assertAlmostEqual(ta.auc(y, [0.9, 0.1, 0.8, 0.2]), 1.0)

    def test_kappa_is_one_for_agreement_and_about_zero_for_independence(self):
        a = np.array([True, True, False, False])
        self.assertAlmostEqual(ta.cohens_kappa(a, a), 1.0)
        b = np.array([True, False, True, False])
        self.assertAlmostEqual(ta.cohens_kappa(a, b), 0.0)

    def test_percentiles_label_an_empty_set_rather_than_zeroing_it(self):
        self.assertEqual(ta.percentiles([]), {"n": 0})
        self.assertEqual(ta.percentiles([None, float("nan")]), {"n": 0})


class TestTaxonomyPlumbing(unittest.TestCase):
    def test_the_cluster_count_criterion_uses_t8c_s_own_primitives(self):
        """The criterion is T8c's -- max mean silhouette, ties toward the
        smaller k -- computed with T8c's own kmeans and silhouette. It is
        spelled out here rather than delegated to `ap.choose_k` only because
        DEVIATION D1a evaluates the silhouette on a subsample, which that
        function cannot express. The rule itself is unchanged."""
        src = inspect.getsource(ta.choose_k_by_silhouette)
        self.assertIn("ap.kmeans", src)
        self.assertIn("ap.silhouette", src)
        self.assertIn("1e-6", src)              # the registered tie rule
        # and it agrees with ap.choose_k when no subsample is taken
        rng = np.random.default_rng(5)
        blobs = np.vstack([rng.normal(loc, 0.2, size=(30, len(ta.FEATURE_NAMES)))
                           for loc in (0.0, 6.0, 12.0, 18.0)])
        blobs = np.abs(blobs) + 0.5
        mine, _l, _c, x, _rows, _sc = ta.choose_k_by_silhouette(
            blobs, ta.FEATURE_NAMES, subsample=None)
        theirs, _sweep = ap.choose_k(x)
        self.assertEqual(mine, theirs)

    def test_three_blobs_are_found_as_three(self):
        rng = np.random.default_rng(7)
        blobs = np.vstack([rng.normal(loc, 0.15, size=(40, len(ta.FEATURE_NAMES)))
                           for loc in (0.0, 8.0, 16.0)])
        blobs = np.abs(blobs) + 0.5
        k, labels, _c, _x, _s, _sc = ta.choose_k_by_silhouette(blobs, ta.FEATURE_NAMES)
        self.assertEqual(k, 3)
        self.assertEqual(len({int(v) for v in labels}), 3)

    def test_leave_one_object_out_is_used_when_it_is_affordable(self):
        """`n_folds = 0` is the registered protocol and is what the arms
        that can afford it use."""
        rng = np.random.default_rng(11)
        m = np.abs(rng.normal(3.0, 1.0, size=(60, len(ta.FEATURE_NAMES)))) + 0.2
        objects = np.repeat(np.arange(10), 6)
        assigned, folds = ta.fold_assignments(m, ta.FEATURE_NAMES, objects, 3,
                                              n_folds=0)
        self.assertTrue(np.all(assigned >= 0))
        self.assertEqual(len(folds), 10)
        for fold in folds.values():
            self.assertEqual(fold["train"].size, 54)
            self.assertEqual(fold["labelsTrain"].size, 54)
            self.assertEqual(fold["held"].size, 6)

    def test_the_grouped_folds_are_object_disjoint(self):
        """DEVIATION D1b: no approacher may appear in both the training rows
        and the held-out rows of the same fold. That is the property that
        makes the estimate honest, and it is asserted, not assumed."""
        rng = np.random.default_rng(11)
        m = np.abs(rng.normal(3.0, 1.0, size=(200, len(ta.FEATURE_NAMES)))) + 0.2
        objects = np.repeat(np.arange(40), 5)
        assigned, folds = ta.fold_assignments(m, ta.FEATURE_NAMES, objects, 3,
                                              n_folds=8)
        self.assertEqual(len(folds), 8)
        covered = set()
        for fold in folds.values():
            held = set(objects[fold["held"]].tolist())
            train = set(objects[fold["train"]].tolist())
            self.assertFalse(held & train, "an object is in both halves")
            self.assertFalse(held & covered, "an object is held out twice")
            covered |= held
        self.assertEqual(covered, set(range(40)))
        self.assertTrue(np.all(assigned >= 0))

    def test_the_silhouette_subsample_does_not_change_the_fit(self):
        """DEVIATION D1a: the k-means is fit on EVERY row; only the
        silhouette is evaluated on a subsample."""
        rng = np.random.default_rng(3)
        blobs = np.vstack([rng.normal(loc, 0.15, size=(300, len(ta.FEATURE_NAMES)))
                           for loc in (0.0, 8.0, 16.0)])
        blobs = np.abs(blobs) + 0.5
        k_full, labels_full, _c, _x, rows_full, _sc = ta.choose_k_by_silhouette(
            blobs, ta.FEATURE_NAMES, subsample=None)
        k_sub, labels_sub, _c2, _x2, rows_sub, _sc2 = ta.choose_k_by_silhouette(
            blobs, ta.FEATURE_NAMES, subsample=200, draws=3)
        self.assertEqual(k_full, 3)
        self.assertEqual(k_sub, k_full)
        np.testing.assert_array_equal(labels_full, labels_sub)
        self.assertEqual(len(rows_sub[0]["silhouetteDraws"]), 3)

    def test_gate_b_fires_when_the_classes_do_not_separate(self):
        flat = [{"n": 50, "precision": 0.30, "wilson95": [0.20, 0.42],
                 "underpowered": False},
                {"n": 50, "precision": 0.32, "wilson95": [0.21, 0.44],
                 "underpowered": False}]
        fired, spread, widest = ta._gate_b(flat)
        self.assertTrue(fired)
        self.assertAlmostEqual(spread, 0.02, places=9)

    def test_gate_b_does_not_fire_when_they_do(self):
        sharp = [{"n": 400, "precision": 0.10, "wilson95": [0.08, 0.13],
                  "underpowered": False},
                 {"n": 400, "precision": 0.70, "wilson95": [0.66, 0.74],
                  "underpowered": False}]
        fired, spread, widest = ta._gate_b(sharp)
        self.assertFalse(fired)
        self.assertGreater(spread, widest)

    def test_an_underpowered_class_does_not_decide_gate_b(self):
        rows = [{"n": 400, "precision": 0.30, "wilson95": [0.26, 0.35],
                 "underpowered": False},
                {"n": 3, "precision": 1.00, "wilson95": [0.44, 1.0],
                 "underpowered": True}]
        fired, spread, widest = ta._gate_b(rows)
        self.assertTrue(fired)          # only one powered class -> no separation
        self.assertIsNone(spread)


class TestPolicyGuards(unittest.TestCase):
    """prereg 1: the framing rules are enforced, not merely intended. The
    banned vocabulary is IMPORTED from T8c's suite, never copied."""

    SRC = (_REPO / "tools" / "trigger_alarm.py").read_text()
    BANNED = _T8cGuards.BANNED

    def test_the_banned_list_is_t8c_s_and_is_not_a_second_copy(self):
        self.assertIs(self.BANNED, _T8cGuards.BANNED)
        self.assertIn("intent", self.BANNED)

    def test_no_intent_language_in_the_tool(self):
        text = self.SRC.lower()
        for banned in self.BANNED:
            self.assertNotIn(banned, text, f"intent language {banned!r} present")

    def test_no_intent_language_in_the_feature_names(self):
        joined = " ".join(ta.FEATURE_NAMES).lower()
        for banned in self.BANNED:
            self.assertNotIn(banned.strip(), joined)

    def test_no_detector_branch_reads_a_registry_code(self):
        for fn in (ta.trigger_features, ta.attach_cadence, ta.propagate,
                   ta.slots_reached, ta.occupancy_reference, ta.OccupancySweep.at,
                   ta.feature_matrix, ta.choose_k_by_silhouette,
                   ta.fold_assignments, ta.skill_arrival, ta.m2_arrival,
                   ta.hybrid_mae_skill, ta.brier_skill, ta.wilson,
                   ta.describe_classes, ta.chain_flags, ta.flag_baselines,
                   ta.build_triggers, ta.resolve_outcomes, ta.m2_days):
            src = inspect.getsource(fn).lower()
            for code in ("country", "registry", "owner", "nation"):
                # word boundaries, because `inclination` is a physical
                # quantity and not a registry code
                self.assertIsNone(re.search(rf"\b{code}\b", src),
                                  f"{fn.__name__} reads a registry code")

    def test_only_object_type_is_read_and_only_for_t8a_s_class(self):
        src = inspect.getsource(ta.object_classes)
        self.assertIn("object_type", src)
        for code in ("country", "launch_date", "object_id", "rcs_size"):
            self.assertNotIn(code, src)

    def test_no_velocity_propellant_or_mass_figure_is_computed(self):
        import ast
        tree = ast.parse(self.SRC)
        body = self.SRC.split(ast.get_docstring(tree, clean=False), 1)[1]
        text = body.lower()
        for banned in ("delta_v", "deltav", "delta-v", "propellant", "fuel",
                       "metres_per_second", "m/s of "):
            self.assertNotIn(banned, text, f"{banned!r} present")

    def test_no_feature_is_named_as_a_distance_or_a_miss(self):
        for name in ta.FEATURE_NAMES:
            low = name.lower()
            self.assertNotIn("miss_distance", low)
            self.assertNotIn("range_km", low)
            self.assertFalse(low.endswith("_km"), name)

    def test_the_registration_is_the_one_this_tool_names(self):
        self.assertEqual(ta.REGISTRATION,
                         "docs/trigger-alarm-preregistration-20260922.md")
        self.assertTrue((_REPO / ta.REGISTRATION).exists())

    def test_the_registration_fixes_every_feature_and_the_criterion(self):
        text = (_REPO / ta.REGISTRATION).read_text()
        self.assertIn("THE CLUSTER-COUNT CRITERION, FIXED BEFORE ANY RUN", text)
        self.assertIn("mean silhouette", text)   # the registration wraps the line
        self.assertIn("+0.137", text)
        for name in ta.FEATURE_NAMES:
            self.assertIn(name, text, f"{name} is not in the registration")

    def test_the_registration_declares_the_out_of_sample_limit_in_advance(self):
        text = (_REPO / ta.REGISTRATION).read_text()
        self.assertIn("M2-L IS NOT OUT OF SAMPLE", text)

    def test_the_registration_says_the_denominator_is_not_t8a_s(self):
        text = (_REPO / ta.REGISTRATION).read_text()
        self.assertIn("not comparable", text)
        self.assertIn("1,483", text)

    def test_the_design_document_still_deploys_nothing(self):
        path = _REPO / "docs" / "alarm-lane-design-20260922.md"
        text = path.read_text()
        self.assertIn("NOTHING IS DEPLOYED", text)
        self.assertIn("DESIGN ONLY", text)

    def test_the_results_document_carries_the_gates_if_it_exists(self):
        path = _REPO / "docs" / "trigger-alarm-results-20260922.md"
        if not path.exists():
            self.skipTest("the results document is committed after the tool")
        text = path.read_text()
        for gate in ("Gate A", "Gate B", "Gate C", "Gate H", "Gate L"):
            self.assertIn(gate, text)
        self.assertIn("Wilson", text)
        # the compute deviations must be on the face of the document
        self.assertIn("D1a", text)
        self.assertIn("D1b", text)


class TestReceiptShape(unittest.TestCase):
    """If the receipt is committed, it must carry what the registration says."""

    PATH = _REPO / "docs" / "trigger-alarm-20260922-receipt.json"

    def setUp(self):
        if not self.PATH.exists():
            self.skipTest("the receipt is committed after the tool")
        self.r = json.loads(self.PATH.read_text())

    def test_it_names_the_registration_and_the_source_hashes(self):
        self.assertEqual(self.r["registration"], ta.REGISTRATION)
        self.assertIn("tools/trigger_alarm.py", self.r["sourceSha256"])
        self.assertIn(ta.REGISTRATION, self.r["sourceSha256"])

    def test_it_reuses_t8a_s_sigma_and_does_not_recalibrate(self):
        self.assertAlmostEqual(self.r["sigma_n_deg_per_day"], SIGMA_N, places=15)

    def test_it_asserts_t8a_s_three_extract_numbers(self):
        self.assertEqual(self.r["extract"]["rowsScanned"], ta.T8A_ROWS_SCANNED)
        self.assertEqual(self.r["extract"]["rowsKept"], ta.T8A_ROWS_KEPT)
        self.assertEqual(self.r["extract"]["objectsKept"], ta.T8A_OBJECTS_KEPT)

    def test_every_registered_gate_is_present(self):
        for gate in "ABCDEFGHWL":
            self.assertIn(gate, self.r["gates"])

    def test_the_unresolvable_triggers_are_counted_and_not_hidden(self):
        pop = self.r["population"]
        self.assertEqual(pop["triggers"] - pop["resolvable"],
                         pop["unresolvableNotAssessable"])

    def test_the_precision_note_disowns_t8a_s_denominator(self):
        self.assertIn("NOT comparable", self.r["precisionNote"])


class TestTriggerTableShape(unittest.TestCase):
    PATH = _REPO / "docs" / "trigger-alarm-triggers-20260922.jsonl"

    def setUp(self):
        if not self.PATH.exists():
            self.skipTest("the trigger table is committed after the tool")
        self.rows = []
        with open(self.PATH) as fh:
            for line in fh:
                rec = json.loads(line)
                if rec.get("record") == "provenance":
                    self.prov = rec
                    continue
                self.rows.append(rec)

    def test_no_row_carries_a_registry_code(self):
        banned = {"approacherCountry", "targetCountry", "country",
                  "approacherName", "targetName", "approacherObjectType",
                  "objectId", "approacherObjectId"}
        for row in self.rows[:200]:
            self.assertFalse(banned & set(row), set(row) & banned)

    def test_every_registered_feature_column_is_present(self):
        for name in ta.FEATURE_NAMES:
            self.assertIn(name, self.rows[0])

    def test_the_committed_table_says_it_is_a_subset_and_names_the_whole(self):
        """The full table is 241 MB and is not committed. What IS committed
        must say so, carry the full table's row count and sha256, and state
        the sampling rule -- otherwise a reader would take a bounded sample
        for a census."""
        self.assertTrue(self.prov["subset"])
        self.assertIn("fullTableSha256", self.prov)
        self.assertIn("fullTableRows", self.prov)
        self.assertIn("subsetRule", self.prov)
        self.assertEqual(len(self.rows), self.prov["subsetRows"])
        self.assertGreater(self.prov["fullTableRows"], len(self.rows))

    def test_every_positive_row_is_present_not_sampled(self):
        """The sampling rule reads only the outcome, and the positives are
        complete. A sampled positive set would make every precision in the
        document uncheckable."""
        pos = [r for r in self.rows if r["o1Positive"] or r["o2Positive"]]
        self.assertEqual(len(pos), self.prov["subsetPositives"])

    def test_no_post_trigger_column_is_present(self):
        for row in self.rows[:50]:
            for key in row:
                low = key.lower()
                for bad in ("transit_", "dwell_", "departure_", "lead_"):
                    self.assertFalse(low.startswith(bad), key)


if __name__ == "__main__":
    unittest.main()
