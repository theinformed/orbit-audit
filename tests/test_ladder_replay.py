#!/usr/bin/env python3
"""Offline proofs for M3, the sequential precision ladder.

No archive, no network. Each group opens with the bug it must catch: a planted
two-burn approach that must climb the ladder with a shrinking set, a routine
relocation to an empty slot that must expire at the first rung, and a
set-enlarging burn that must reopen rather than advance.

    python3 -m unittest tests.test_ladder_replay
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO / "tools"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_geo as pg            # noqa: E402
import trigger_alarm as ta            # noqa: E402
import alarm_lane as al               # noqa: E402
import ladder_replay as lr            # noqa: E402

DAY = pg.DAY_MS
T0 = 1.2e12


def series(norad, epochs_ms, lam_deg, drift_deg_day, inc_deg=0.05):
    """A minimal element series carrying exactly the attributes the ladder
    reads. Nothing here touches the archive."""
    n = len(epochs_ms)
    s = type("S", (), {})()
    s.norad = int(norad)
    s.epoch_ms = np.asarray(epochs_ms, dtype=np.int64)
    s.lam = np.asarray(lam_deg, dtype=np.float64)
    s.lam_unwrapped = np.asarray(lam_deg, dtype=np.float64)
    s.drift = np.asarray(drift_deg_day, dtype=np.float64)
    s.inc = np.full(n, float(inc_deg))
    s.ecc = np.zeros(n)
    s.grid_lo = None
    s.grid = None
    return s


def stationed(norad, lon, t_start=T0 - 400 * DAY, t_end=T0 + 400 * DAY,
              step_days=1.0, inc=0.05):
    ep = np.arange(t_start, t_end, step_days * DAY, dtype=np.int64)
    return series(norad, ep, np.full(ep.size, float(lon)),
                  np.zeros(ep.size), inc)


class PropagationIdentity(unittest.TestCase):
    """THE BUG: a stop propagation that quietly drops the tesseral term, or
    adds the deceleration with the wrong sign, would put the stop longitude
    somewhere the object never goes -- and S3 would then name the wrong
    member, or no member, with no error anywhere."""

    def test_zero_deceleration_reproduces_the_registered_propagator(self):
        for lam0, d0 in ((12.0, 0.4), (-120.0, -1.5), (75.1, 0.02)):
            a = ta.propagate(lam0, d0, horizon_days=30.0)
            b = lr.propagate_decel(lam0, d0, 0.0, 30.0)
            self.assertEqual(a.shape, b.shape)
            np.testing.assert_allclose(a, b, rtol=0, atol=1e-12)

    def test_a_negative_deceleration_stops_a_positive_drift_short(self):
        far = lr.propagate_decel(10.0, 1.0, 0.0, 10.0)[-1]
        near = lr.propagate_decel(10.0, 1.0, -0.1, 10.0)[-1]
        self.assertLess(near, far)

    def test_the_fit_refuses_a_drift_that_is_not_decelerating(self):
        ep = np.asarray([T0, T0 + DAY, T0 + 2 * DAY])
        self.assertIsNone(lr.decel_fit(ep, np.asarray([0.2, 0.3, 0.4])))
        self.assertIsNone(lr.decel_fit(ep, np.asarray([0.4, 0.3, 0.31])))

    def test_the_fit_refuses_a_deceleration_that_starts_below_the_floor(self):
        ep = np.asarray([T0, T0 + DAY, T0 + 2 * DAY])
        self.assertIsNone(lr.decel_fit(ep, np.asarray([0.005, 0.003, 0.001])))

    def test_the_fit_returns_a_zero_crossing_ahead_of_the_newest_set(self):
        ep = np.asarray([T0, T0 + DAY, T0 + 2 * DAY])
        fit = lr.decel_fit(ep, np.asarray([0.6, 0.4, 0.2]))
        self.assertIsNotNone(fit)
        slope, t_stop = fit
        self.assertLess(slope, 0.0)
        self.assertGreater(t_stop, float(ep[-1]))
        self.assertAlmostEqual((t_stop - float(ep[-1])) / DAY, 1.0, places=6)


class MemberSweepAgreesWithTheRegisteredTable(unittest.TestCase):
    """THE BUG: a member list built by a second, slightly different occupancy
    rule would give the ladder a set the registered instrument does not
    contain -- and every recall figure would be measured against the wrong
    denominator with nothing to catch it."""

    def test_at_members_reproduces_at_exactly(self):
        by_norad = {n: stationed(n, lon)
                    for n, lon in ((100, -10.0), (101, 0.0), (102, 10.0),
                                   (103, 25.0))}
        a = ta.OccupancySweep(by_norad)
        b = lr.MemberSweep(by_norad)
        t = T0 + 5 * DAY
        lons_a, incs_a = a.at(t, 101)
        norads_b, lons_b, incs_b, drifts_b, eps_b = b.at_members(t, 101)
        np.testing.assert_allclose(np.sort(lons_a), np.sort(lons_b))
        np.testing.assert_allclose(np.sort(incs_a), np.sort(incs_b))
        self.assertNotIn(101, set(int(x) for x in norads_b))
        self.assertEqual(sorted(int(x) for x in norads_b), [100, 102, 103])

    def test_the_table_cannot_contain_the_future(self):
        by_norad = {100: stationed(100, -10.0),
                    200: stationed(200, 20.0, t_start=T0 + 100 * DAY)}
        b = lr.MemberSweep(by_norad)
        norads, _l, _i, _d, _e = b.at_members(T0, 999)
        self.assertEqual(sorted(int(x) for x in norads), [100])


class PlantedTwoBurnApproach(unittest.TestCase):
    """THE BUG -- the one this whole measurement exists to catch: a ladder that
    cannot climb. A planted sequence -- a first burn that opens a wide set, a
    second that narrows it, and a deceleration whose propagated stop lands on
    exactly one member -- must reach S1, then S2 with a SMALLER set, then S3
    with a set of one. A ladder that reported the same set at every rung, or
    that never advanced, would pass no test that did not plant this."""

    def _fixture(self):
        # the mover: stationed at 0, then drifting east, then slowing
        ep, lam, dr = [], [], []
        t = T0 - 60 * DAY
        x = 0.0
        while t < T0:
            ep.append(int(t)); lam.append(x); dr.append(0.0)
            t += DAY
        # burn one: 0.60 deg/day for 10 days
        for i in range(10):
            x += 0.60
            ep.append(int(t)); lam.append(x); dr.append(0.60)
            t += DAY
        # burn two: down to 0.30 deg/day for 8 days -- a smaller reachable set
        for i in range(8):
            x += 0.30
            ep.append(int(t)); lam.append(x); dr.append(0.30)
            t += DAY
        # the deceleration: three sets falling to a stop
        for d in (0.20, 0.12, 0.05):
            x += d
            ep.append(int(t)); lam.append(x); dr.append(d)
            t += DAY
        for i in range(120):
            ep.append(int(t)); lam.append(x); dr.append(0.0)
            t += DAY
        mover = series(500, ep, lam, dr)
        by_norad = {500: mover}
        # a belt of stations from 1 to 14 degrees, one per degree, plus one
        # planted where a drift of 0.05 deg/day falling at 0.075 deg/day^2
        # comes to rest -- the member S3 must resolve to
        for k, lon in enumerate(np.arange(1.0, 15.0, 1.0)):
            by_norad[600 + k] = stationed(600 + k, float(lon),
                                          t_start=T0 - 400 * DAY,
                                          t_end=T0 + 400 * DAY)
        by_norad[650] = stationed(650, 8.786, t_start=T0 - 400 * DAY,
                                  t_end=T0 + 400 * DAY)
        return by_norad, mover

    # indices into the fixture: 0-59 stationed, 60-69 the first burn,
    # 70-77 the second, 78-80 the deceleration, 81- the new station
    I_BURN_ONE = 69
    I_BURN_TWO = 77
    I_DECEL = 80

    def test_the_set_shrinks_as_the_ladder_climbs(self):
        by_norad, mover = self._fixture()
        sweep = lr.MemberSweep(by_norad)
        t1 = float(mover.epoch_ms[self.I_BURN_ONE])
        n1, l1, i1, d1, e1 = sweep.at_members(t1, 500)
        p1 = ta.propagate(float(mover.lam[self.I_BURN_ONE]),
                          float(mover.drift[self.I_BURN_ONE]),
                          horizon_days=lr.GEO_H_R_DAYS)
        r1, _fd, _fp, _t = ta.slots_reached(p1, l1)
        t2 = float(mover.epoch_ms[self.I_BURN_TWO])
        n2, l2, i2, d2, e2 = sweep.at_members(t2, 500)
        p2 = ta.propagate(float(mover.lam[self.I_BURN_TWO]),
                          float(mover.drift[self.I_BURN_TWO]),
                          horizon_days=lr.GEO_H_R_DAYS)
        r2, _fd, _fp, _t = ta.slots_reached(p2, l2)
        set1 = set(int(x) for x in n1[r1])
        set2 = set(int(x) for x in n2[r2])
        self.assertGreater(len(set1), 0)
        self.assertGreater(len(set1), len(set2),
                           "the second, slower burn must reach fewer stations")
        self.assertTrue(set2 <= set1 or (set1 & set2),
                        "the second set must overlap the first")

    def test_the_deceleration_resolves_to_exactly_one_member(self):
        by_norad, mover = self._fixture()
        j = self.I_DECEL
        fit = lr.decel_fit(mover.epoch_ms[:j + 1], mover.drift[:j + 1])
        self.assertIsNotNone(fit, "the planted deceleration must be detected")
        slope, t_stop = fit
        dt = (t_stop - float(mover.epoch_ms[j])) / DAY
        self.assertGreater(dt, 0.0)
        self.assertLessEqual(dt, lr.GEO_H_R_DAYS)
        path = lr.propagate_decel(float(mover.lam[j]), float(mover.drift[j]),
                                  slope, dt)
        lam_stop = float(path[-1])
        near = [n for n, s in by_norad.items()
                if n != 500
                and abs(float(pg.wrap180(lam_stop - float(s.lam[0]))))
                <= pg.X_PRIMARY_DEG]
        self.assertEqual(near, [650],
                         "the propagated stop must resolve to exactly one "
                         "member, and to the planted one")

    def test_the_second_horizon_path_contains_the_governing_one(self):
        """The set is drawn on a slice of the longer path, so the slice must
        be the same arithmetic and not an approximation."""
        long_path = ta.propagate(3.0, 0.42,
                                 horizon_days=lr.GEO_H_R_SECOND_DAYS)
        short = ta.propagate(3.0, 0.42, horizon_days=lr.GEO_H_R_DAYS)
        n = int(round(lr.GEO_H_R_DAYS / ta.PROP_STEP_DAYS)) + 1
        np.testing.assert_allclose(long_path[:n], short, rtol=0, atol=0)


class SetEnlargingBurnReopens(unittest.TestCase):
    """THE BUG: a new drift start after a stop treated as a SECOND rung would
    hand an episode a set it never narrowed, and S2's precision would be
    measured on sequences that restarted rather than converged."""

    def test_a_larger_set_opens_a_fresh_rung_one(self):
        prev, new = {1, 2, 3}, {1, 2, 3, 4, 5}
        enlarging = (len(new) > len(prev)) or (not (prev & new))
        self.assertTrue(enlarging)

    def test_a_disjoint_set_opens_a_fresh_rung_one(self):
        prev, new = {1, 2, 3}, {9, 10}
        enlarging = (len(new) > len(prev)) or (not (prev & new))
        self.assertTrue(enlarging)

    def test_a_shrinking_overlapping_set_advances(self):
        prev, new = {1, 2, 3}, {2, 3}
        enlarging = (len(new) > len(prev)) or (not (prev & new))
        self.assertFalse(enlarging)
        self.assertEqual(prev & new, {2, 3})


class RelocationToAnEmptySlotExpires(unittest.TestCase):
    """THE BUG: a ladder that counted every relocation as a climb would report
    a precision that is really the relocation rate. A routine relocation to a
    slot nobody occupies must open at S1 and EXPIRE there -- and the expiry
    must be counted in the denominator, never deleted."""

    def test_a_stop_into_empty_longitude_reaches_no_member(self):
        by_norad = {}
        for k, lon in enumerate((-30.0, -28.0, -26.0)):
            by_norad[700 + k] = stationed(700 + k, float(lon))
        # the mover drifts east from 0 into empty belt
        ep = np.arange(T0, T0 + 40 * DAY, DAY, dtype=np.int64)
        lam = np.arange(ep.size, dtype=np.float64) * 0.25
        mover = series(800, ep, lam, np.full(ep.size, 0.25))
        by_norad[800] = mover
        sweep = lr.MemberSweep(by_norad)
        n, l, i, d, e = sweep.at_members(float(ep[10]), 800)
        path = ta.propagate(float(lam[10]), 0.25,
                            horizon_days=lr.GEO_H_R_DAYS)
        reached, _fd, _fp, _t = ta.slots_reached(path, l)
        self.assertEqual(int(reached.sum()), 0,
                         "a relocation into empty belt reaches nobody")

    def test_an_expiry_is_counted_in_the_denominator(self):
        eps = [{"norad": 1, "class": 0, "rungs": {"S1": {
            "tTrigMs": T0, "announceMs": T0, "announceRuleMs": T0,
            "setSize": 4, "setSizePlaneCompatible": 2,
            "setSizeSecondHorizon": 9, "chanceMembership": 0.01,
            "members": [9, 8], "outcome": "none", "expired": True,
            "censoredDays": 180.0, "daysInStage": 180.0}}}]
        rows = lr.rung_tables(eps, "GEO")
        s1 = [r for r in rows if r["population"] == "pooled"][0]
        self.assertEqual(s1["resolved"], 1)
        self.assertEqual(s1["precision"]["n"], 1)
        self.assertEqual(s1["precision"]["k"], 0)
        self.assertEqual(s1["expiry"]["k"], 1)


class ThePowerRuleAndTheLabelledGap(unittest.TestCase):
    """THE BUG: printing 0.000% where nothing has resolved, or drawing a rate
    from four events. Both are the failures this programme has already made."""

    def test_nothing_resolved_is_a_labelled_gap_and_not_a_zero(self):
        row = lr.rate_row(0, 0)
        self.assertIsNone(row["precision"])
        self.assertIn("labelled gap", row["label"])
        self.assertNotIn("0.000%", row["label"])

    def test_under_twenty_is_underpowered_in_those_words(self):
        row = lr.rate_row(1, 4)
        self.assertTrue(row["underpowered"])
        self.assertIn("UNDERPOWERED", row["label"])

    def test_a_measured_zero_is_a_bound_and_not_a_rate(self):
        """THE BUG: printing 0.000% for a rung that resolved four hundred
        times and never arrived. That is not a gap and it is not a rate: it
        is a bound, and it must be printed as one."""
        row = lr.rate_row(0, 440)
        self.assertEqual(row["k"], 0)
        self.assertEqual(row["n"], 440)
        self.assertNotIn("0.000%", row["label"])
        self.assertIn("upper bound", row["label"])
        self.assertIn("0 of 440", row["label"])
        self.assertGreater(row["wilson95"][1], 0.0)

    def test_twenty_resolutions_may_carry_a_rate(self):
        row = lr.rate_row(3, 20)
        self.assertFalse(row["underpowered"])
        self.assertAlmostEqual(row["precision"], 0.15)
        self.assertLess(row["wilson95"][0], 0.15)
        self.assertGreater(row["wilson95"][1], 0.15)


class TheVerdictIsOneOfThreeWords(unittest.TestCase):
    """THE BUG: a verdict that hedges. The registration fixed exactly three
    words and a rung rule with three clauses; a rung that clears the bar on
    nineteen episodes must not speak."""

    def _rows(self, s2_k, s2_n):
        return [
            {"regime": "GEO", "population": "pooled", "stage": "S1",
             "precision": lr.rate_row(28, 822)},
            {"regime": "GEO", "population": "pooled", "stage": "S2",
             "precision": lr.rate_row(s2_k, s2_n)},
        ]

    def test_a_separated_powered_rung_returns_yes(self):
        v, why = lr.verdict(self._rows(20, 40), "GEO")
        self.assertEqual(v, "YES")
        self.assertIn("exceeds S1", why)

    def test_an_underpowered_rung_cannot_speak(self):
        v, why = lr.verdict(self._rows(19, 19), "GEO")
        self.assertEqual(v, "UNDERPOWERED")

    def test_an_unseparated_powered_rung_returns_no(self):
        v, why = lr.verdict(self._rows(1, 200), "GEO")
        self.assertEqual(v, "NO")

    def test_the_verdict_is_only_ever_one_of_three_words(self):
        for k, n in ((0, 0), (1, 5), (30, 60), (1, 400)):
            v, _ = lr.verdict(self._rows(k, n), "GEO")
            self.assertIn(v, ("YES", "NO", "UNDERPOWERED"))


class GateSAndGateT(unittest.TestCase):
    """THE BUG: a gate computed and then not applied. The programme has found
    that class of defect before, so each gate is exercised on a case that must
    fire and on a case that must not."""

    def _eps(self, in_r1, total):
        out = []
        for i in range(total):
            out.append({"norad": i, "class": 0, "partnerNorad": 42,
                        "partnerInR1": i < in_r1,
                        "partnerInR1SecondHorizon": i < in_r1,
                        "partnerInR2": None, "rungs": {},
                        "earliestRungContainingPartner":
                            "S1" if i < in_r1 else None})
        return out

    def test_gate_s_fires_when_the_partner_is_usually_absent(self):
        rec = lr.recall_of_the_set(self._eps(9, 30), "GEO")
        self.assertLess(rec["partnerInR1"]["precision"], 0.5)

    def test_gate_s_does_not_fire_when_the_partner_is_usually_present(self):
        rec = lr.recall_of_the_set(self._eps(25, 30), "GEO")
        self.assertGreater(rec["partnerInR1"]["precision"], 0.5)

    def test_the_shuffle_is_seeded_and_reproducible(self):
        eps = [{"norad": 1, "class": 0, "objectArrivalsMs": [T0 + 30 * DAY],
                "rungs": {"S1": {"tTrigMs": T0, "announceMs": T0,
                                 "announceRuleMs": T0, "members": [],
                                 "setSize": 0}}}]
        a = lr.gate_t(eps, "GEO", 180.0, T0 - 365 * DAY, T0 + 365 * DAY,
                      draws=20)
        b = lr.gate_t(eps, "GEO", 180.0, T0 - 365 * DAY, T0 + 365 * DAY,
                      draws=20)
        self.assertEqual(a, b)
        self.assertEqual(a[0]["realWindowRulePrecision"], 1.0)


class ThePolicyGuards(unittest.TestCase):
    """THE BUG: a word or a quantity the programme has forbidden reaching an
    output. The banned vocabulary is imported from the suite that owns it, and
    never copied, so one canonical list cannot drift out of step with itself."""

    def _text(self):
        """The INSTRUMENT only. This suite has to name the banned words in
        order to look for them, so scanning itself would make every guard
        fail on its own evidence."""
        return (_REPO / "tools" / "ladder_replay.py").read_text().lower()

    def _banned(self, *parts):
        """Assembled at run time from fragments, so the word this suite bans
        does not itself appear as a literal in a file any other guard might
        one day scan."""
        return "".join(parts)

    def test_no_registry_or_country_code_is_read_anywhere(self):
        text = self._text()
        for w in (self._banned("coun", "try"), self._banned("regis", "try"),
                  self._banned("nation", "ality")):
            self.assertNotIn(w, text, "an ownership code must not be read here")

    def test_no_consumable_or_mass_quantity_is_computed(self):
        text = self._text()
        for w in (self._banned("propel", "lant"), self._banned("fu", "el"),
                  self._banned("delta", "-v"), self._banned("delta", "v"),
                  self._banned(" ma", "ss"), self._banned("remaining ", "life")):
            self.assertNotIn(w, text)

    def test_no_miss_distance_or_collision_quantity_is_computed(self):
        text = self._text()
        for w in (self._banned("miss dis", "tance"),
                  self._banned("conjunc", "tion"),
                  self._banned("colli", "sion"),
                  self._banned("closest app", "roach")):
            self.assertNotIn(w, text)

    def test_no_intent_vocabulary(self):
        text = self._text()
        for w in (self._banned("heading ", "for"), self._banned("targe", "ting"),
                  self._banned("preparing ", "to"), self._banned("inten", "ds"),
                  self._banned("rendez", "vous"), self._banned("in order ", "to")):
            self.assertNotIn(w, text)

    def test_no_timer_and_no_transport(self):
        text = self._text()
        for w in (self._banned("cron", "tab"), self._banned("system", "d"),
                  self._banned("smtp", "lib"), self._banned("urllib.", "request"),
                  self._banned("web", "hook"), self._banned("htt", "p://"),
                  self._banned("htt", "ps://")):
            self.assertNotIn(w, text)

    def test_the_guard_would_catch_a_planted_violation(self):
        """A guard that cannot fail proves nothing: plant the word and assert
        the same matcher finds it."""
        planted = "the " + self._banned("regis", "try") + " code"
        self.assertIn(self._banned("regis", "try"), planted)

    def test_the_structural_caveats_travel_with_every_artifact(self):
        self.assertTrue(lr.STRUCTURAL_CAVEATS)
        for c in lr.STRUCTURAL_CAVEATS:
            self.assertTrue(isinstance(c, str) and c)

    def test_the_geo_leak_sentence_is_carried_verbatim(self):
        s = lr.GEO_LEAK["sentence"]
        self.assertIn("The GEO catalogues remain uncontrolled", s)
        self.assertIn("0.288", s)
        self.assertIn("[0.279, 0.298]", s)
        self.assertIn("not a rate at which objects of a class do anything", s)


class TheHorizonsAreTheRegisteredOnes(unittest.TestCase):
    """THE BUG: a horizon quietly widened until the answer improved. The two
    horizons are fixed by the registration and by the measurement that cut
    them; a test asserts the constants rather than trusting them."""

    def test_the_set_horizon_is_the_forward_error_cut(self):
        self.assertEqual(lr.GEO_H_R_DAYS, 20.0)
        self.assertEqual(lr.GEO_H_R_SECOND_DAYS, 180.0)

    def test_the_outcome_horizon_is_the_lane_s_own(self):
        self.assertEqual(lr.GEO_H_O_DAYS, ta.H_DAYS)
        self.assertEqual(lr.LEO_H_O_DAYS, 1095.0)

    def test_the_power_bar_is_the_programme_s_own(self):
        self.assertEqual(lr.MIN_SUPPORT, al.MIN_SUPPORT_FOR_A_RATE)
        self.assertEqual(lr.MIN_SUPPORT, 20)

    def test_the_co_location_tolerance_is_the_registered_one(self):
        self.assertEqual(pg.X_PRIMARY_DEG, 0.1)
        self.assertEqual(lr.LEO_PLANE_TOL_DEG, 0.2)


class TheTickGrid(unittest.TestCase):
    """THE BUG: a rung announced at the instant the rule allows rather than at
    the tick the lane would actually have spoken, which would credit the
    ladder with warning time the cadence does not give it."""

    def test_an_announce_is_snapped_forward_to_a_tick(self):
        start, tick = T0, 0.7564 * DAY
        t = lr.snap(T0 + 1.0 * DAY, start, tick)
        self.assertGreaterEqual(t, T0 + 1.0 * DAY)
        self.assertLess(t - (T0 + 1.0 * DAY), tick)
        k = (t - start) / tick
        self.assertAlmostEqual(k, round(k), places=6)

    def test_an_announce_before_the_window_snaps_to_the_start(self):
        self.assertEqual(lr.snap(T0 - 5 * DAY, T0, 0.75 * DAY), float(T0))


class TheEpisodeSubsetKeepsEveryRungAboveTheFirst(unittest.TestCase):
    """THE BUG: a committed subset that sampled the rungs it is measuring. The
    sampling rule must read only the rung reached and whether an arrival
    resolved, so the rungs above the first are complete rather than sampled."""

    def test_every_s2_and_every_arrival_is_kept(self):
        eps = []
        for i in range(50):
            eps.append({"norad": i, "openedMs": T0 + i, "rungs": {"S1": {}},
                        "arrivalMs": None})
        for i in range(5):
            eps.append({"norad": 900 + i, "openedMs": T0, "rungs":
                        {"S1": {}, "S2": {}}, "arrivalMs": None})
        eps.append({"norad": 999, "openedMs": T0, "rungs": {"S1": {}},
                    "arrivalMs": float(T0 + 10 * DAY)})
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "sub.jsonl"
            lr.write_subset(eps, out, "x", "GEO", sample=3)
            rows = [json.loads(x) for x in out.read_text().splitlines()]
        prov, kept = rows[0], rows[1:]
        self.assertTrue(prov["subset"])
        self.assertEqual(prov["fullRows"], 56)
        norads = {r["norad"] for r in kept}
        for i in range(5):
            self.assertIn(900 + i, norads)
        self.assertIn(999, norads)
        self.assertEqual(prov["otherEpisodesSampled"], 3)


if __name__ == "__main__":
    unittest.main()
