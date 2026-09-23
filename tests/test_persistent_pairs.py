"""Tests for T11 (tools/persistent_pairs.py).

Coverage required by `docs/persistent-pairs-preregistration-20260922.md`
section 11: the section 2.1 and 2.2 derivations against independently
computed values; the phasor fit recovering a constructed phase and amplitude;
phase-difference invariance under a shared time shift and its rotation under
a shift of one member; the false-alarm exponent against the registered
detrend degree; a synthetic pair that must be detected; a synthetic pair
broken in the middle that must not yield one long episode; a synthetic pair
one day short of the dwell that must not be detected; the gap refusal; the
global-origin day-index conversion; the exact beta inversion; the
arrival-order resolution and censoring rules; the section 0 vocabulary ban by
word-boundary inspection; and that no detector branch reads a registry code,
name, object id or launch date.
"""

import ast
import json
import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import persistent_pairs as pp  # noqa: E402
from tools import proximity_geo as pg  # noqa: E402

DAY_MS = 86400000.0


def _ms(year, month, day):
    import datetime as dt
    return int(dt.datetime(year, month, day,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


def make_series(norad, epochs_ms, lam_deg, drift_deg_per_day=None):
    """A Series with a prescribed mean-longitude history, constructed
    backwards through T8a prereg 2.2 (RAAN and argp zeroed, the mean anomaly
    carries lambda + theta_G), so the test exercises the pipeline and not a
    re-statement of the estimator."""
    epochs = np.asarray(epochs_ms, dtype=np.int64)
    lam = np.asarray(lam_deg, dtype=np.float64)
    gmst = np.asarray([pg.gmst_deg(e) for e in epochs])
    ma = (lam + gmst) % 360.0
    if drift_deg_per_day is None:
        mm = np.full(epochs.size,
                     (pg.OMEGA_E_DEG_PER_DAY + 0.0) / 360.0)
    else:
        d = np.asarray(drift_deg_per_day, dtype=np.float64)
        mm = (pg.OMEGA_E_DEG_PER_DAY + d) / 360.0
    return pg.Series(norad, epochs, mm,
                     np.full(epochs.size, 1e-4),
                     np.full(epochs.size, 0.05),
                     np.zeros(epochs.size), np.zeros(epochs.size), ma)


def build_world_from(series_list, classes=None):
    w = pp.World()
    w.series = series_list
    w.global_lo, w.n_days = pg.build_daily_grid(series_list)
    w.index = {s.norad: i for i, s in enumerate(series_list)}
    w.classes = classes or {s.norad: "active" for s in series_list}
    w.meta = {s.norad: {"name": f"OBJ {s.norad}", "objectId": None,
                        "objectType": "PAYLOAD", "country": None,
                        "launchDate": None} for s in series_list}
    w.segs = {s.norad: pg.station_segments(s) for s in series_list}
    w.segid, w.stationed_days = {}, {}
    for s in series_list:
        ids = np.full(s.grid.size, -1, dtype=np.int32)
        for k, (i0, i1) in enumerate(w.segs[s.norad]):
            ids[i0:i1 + 1] = k
        w.segid[s.norad] = ids
        w.stationed_days[s.norad] = (np.where(ids >= 0)[0]
                                     + s.grid_lo).astype(np.int64)
    w.relocation_days, w.departure_days = {}, {}
    for s in series_list:
        rel = pg.relocations(s, w.segs[s.norad])
        w.relocation_days[s.norad] = np.asarray(
            sorted(int(r["originEndDay"]) for r in rel), dtype=np.int64)
        w.departure_days[s.norad] = np.asarray(
            sorted(s.grid_lo + i1 for _, i1 in w.segs[s.norad]),
            dtype=np.int64)
    w.payload = set(w.index)
    w.never = set()
    return w


# ==========================================================================
class TestDerivations(unittest.TestCase):
    def test_deadband_half_width(self):
        """prereg 2.1: dL = A T^2 / 16, against T3's published 0.0208 deg."""
        dl = pp.deadband_half_width_deg(14.00, 1.7006e-3)
        self.assertAlmostEqual(dl, 1.7006e-3 * 196.0 / 16.0, places=12)
        self.assertAlmostEqual(dl, 0.020832, places=6)

    def test_x_pair_primary(self):
        self.assertAlmostEqual(pp.X_PAIR_PRIMARY_DEG, 0.0416647, places=6)
        self.assertAlmostEqual(pp.X_PAIR_PRIMARY_DEG * pp.KM_PER_DEG,
                               30.66, places=1)

    def test_x_pair_arms_ordered(self):
        self.assertLess(pp.X_PAIR_TIGHT_DEG, pp.X_PAIR_PRIMARY_DEG)
        self.assertLess(pp.X_PAIR_PRIMARY_DEG, pp.X_PAIR_LOOSE_DEG)
        self.assertLess(pp.X_PAIR_LOOSE_DEG, pp.X_PAIR_T8A_DEG)
        self.assertAlmostEqual(pp.X_PAIR_TIGHT_DEG,
                               0.5 * pp.X_PAIR_PRIMARY_DEG, places=12)

    def test_dwell_from_cycles(self):
        """prereg 2.2: D = T3's MIN_CYCLES_IN_WINDOW x the measured line."""
        from tools import cadence_core
        self.assertEqual(cadence_core.MIN_CYCLES_IN_WINDOW,
                         pp.MIN_CYCLES_IN_WINDOW)
        self.assertAlmostEqual(pp.D_PAIR_PRIMARY_DAYS, 56.0, places=10)

    def test_short_arm_is_the_rayleigh_floor(self):
        """prereg 2.2: three perfectly aligned phases reach p = e^-3."""
        self.assertAlmostEqual(pp.D_PAIR_SHORT_DAYS / pp.T_EAST_WEST_DAYS,
                               3.0, places=10)
        self.assertLess(math.exp(-3.0), 0.05)

    def test_phi_lock(self):
        """prereg 2.3: one median epoch spacing of the 14.00 d cycle."""
        self.assertAlmostEqual(pp.PHI_LOCK_RAD,
                               2 * math.pi * 0.865 / 14.0, places=12)
        # The registration's rad value is exact; its DEGREE gloss (22.244)
        # is a transcription slip of 0.0011 deg. The implementation encodes
        # the formula, as T8a's gate A implementation did, and the slip is
        # reported in the results document rather than edited away.
        self.assertAlmostEqual(math.degrees(pp.PHI_LOCK_RAD),
                               360.0 * 0.865 / 14.0, places=10)
        self.assertAlmostEqual(math.degrees(pp.PHI_LOCK_RAD), 22.2429,
                               places=4)

    def test_window_is_t8a_p95(self):
        self.assertAlmostEqual(pp.W_PRIMARY_DAYS, 162.7, places=10)
        self.assertIn(36.1, pp.W_ARMS_DAYS)
        self.assertIn(365.0, pp.W_ARMS_DAYS)

    def test_borrowed_constants_are_imports_not_copies(self):
        self.assertIs(pp.MAX_GAP_DAYS, pg.MAX_GAP_DAYS)
        self.assertIs(pp.MIN_OCCUPANCY_PER_DAY,
                      pg.LOITER_MIN_OCCUPANCY_PER_DAY)
        self.assertIs(pp.X_PAIR_T8A_DEG, pg.X_PRIMARY_DEG)


class TestBetaAndIntervals(unittest.TestCase):
    def test_betainc_known_values(self):
        # I_x(1,1) = x
        for x in (0.1, 0.5, 0.9):
            self.assertAlmostEqual(pp.betainc(1.0, 1.0, x), x, places=12)
        # I_x(2,1) = x^2 ; I_x(1,2) = 1-(1-x)^2
        self.assertAlmostEqual(pp.betainc(2.0, 1.0, 0.3), 0.09, places=12)
        self.assertAlmostEqual(pp.betainc(1.0, 2.0, 0.3),
                               1.0 - 0.49, places=12)
        # I_x(0.5,0.5) = (2/pi) arcsin(sqrt(x))
        self.assertAlmostEqual(pp.betainc(0.5, 0.5, 0.25),
                               (2 / math.pi) * math.asin(0.5), places=10)

    def test_beta_quantile_inverts(self):
        for (a, b, q) in ((2.0, 5.0, 0.025), (3.5, 1.5, 0.975),
                          (10.0, 10.0, 0.5)):
            x = pp.beta_quantile(q, a, b)
            self.assertAlmostEqual(pp.betainc(a, b, x), q, places=8)

    def test_clopper_pearson_known(self):
        lo, hi = pp.clopper_pearson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 1.0 - 0.025 ** 0.1, places=8)
        lo, hi = pp.clopper_pearson(10, 10)
        self.assertEqual(hi, 1.0)
        self.assertAlmostEqual(lo, 0.025 ** 0.1, places=8)

    def test_rate_ratio_point_estimate(self):
        ratio, lo, hi = pp.rate_ratio_ci(20, 100.0, 10, 100.0)
        self.assertAlmostEqual(ratio, 2.0, places=12)
        self.assertLess(lo, 2.0)
        self.assertGreater(hi, 2.0)

    def test_rate_ratio_interval_contains_one_when_equal(self):
        _, lo, hi = pp.rate_ratio_ci(10, 100.0, 10, 100.0)
        self.assertLessEqual(lo, 1.0)
        self.assertGreaterEqual(hi, 1.0)

    def test_wilson_matches_hand_value(self):
        lo, hi = pp.wilson(1, 2)
        self.assertAlmostEqual(0.5 * (lo + hi), 0.5, places=10)


class TestPhasor(unittest.TestCase):
    def _series(self, phase, amp=1.0, n=120, noise=0.0, seed=1,
                period=14.0, t0=20000.0):
        rng = np.random.default_rng(seed)
        t = t0 + np.arange(n) * 0.5
        y = amp * np.cos(2 * math.pi * t / period - phase)
        if noise:
            y = y + rng.normal(0.0, noise, n)
        return t, y

    def test_recovers_phase_and_amplitude(self):
        for phase in (0.0, 0.7, -2.1, 3.0):
            t, y = self._series(phase, amp=2.5)
            fit = pp.cadence_phasor(t, y)
            self.assertAlmostEqual(fit["amplitude"], 2.5, places=6)
            self.assertAlmostEqual(float(pp.wrap_pi(fit["phase"] - phase)),
                                   0.0, places=6)

    def test_delta_phi_invariant_under_shared_shift(self):
        t, ya = self._series(0.4)
        _, yb = self._series(1.9)
        fa, fb = pp.cadence_phasor(t, ya), pp.cadence_phasor(t, yb)
        d1 = float(pp.wrap_pi(fa["phase"] - fb["phase"]))
        # shift BOTH series in time by one full cycle: dphi is unchanged
        fa2 = pp.cadence_phasor(t + 14.0, ya)
        fb2 = pp.cadence_phasor(t + 14.0, yb)
        d2 = float(pp.wrap_pi(fa2["phase"] - fb2["phase"]))
        self.assertAlmostEqual(d1, d2, places=6)

    def test_delta_phi_rotates_when_one_member_shifts(self):
        t, ya = self._series(0.0)
        _, yb = self._series(0.0)
        quarter = 14.0 / 4.0
        fa = pp.cadence_phasor(t, ya)
        fb = pp.cadence_phasor(t, np.cos(2 * math.pi * (t - quarter) / 14.0))
        d = float(pp.wrap_pi(fa["phase"] - fb["phase"]))
        self.assertAlmostEqual(abs(d), math.pi / 2.0, places=5)

    def test_fap_exponent_matches_registered_detrend_degree(self):
        """prereg 5.2: the null model is a constant plus a slope, so the
        exponent is (N-4)/2 and not the more common (N-3)/2."""
        t, y = self._series(0.0, amp=0.0, noise=1.0, seed=7, n=60)
        fit = pp.cadence_phasor(t, y)
        expected = (1.0 - fit["power"]) ** ((fit["n"] - 4) / 2.0)
        self.assertAlmostEqual(fit["fap"], expected, places=12)
        wrong = (1.0 - fit["power"]) ** ((fit["n"] - 3) / 2.0)
        self.assertNotAlmostEqual(fit["fap"], wrong, places=6)

    def test_pure_noise_does_not_pass_the_screen(self):
        t, y = self._series(0.0, amp=0.0, noise=1.0, seed=11, n=100)
        fit = pp.cadence_phasor(t, y)
        self.assertGreater(fit["fap"], pp.FAP_ALPHA)

    def test_strong_line_passes_the_screen(self):
        t, y = self._series(0.9, amp=1.0, noise=0.2, seed=3, n=100)
        fit = pp.cadence_phasor(t, y)
        self.assertLess(fit["fap"], pp.FAP_ALPHA)

    def test_sigma_phase_falls_with_amplitude(self):
        t, y1 = self._series(0.3, amp=1.0, noise=0.3, seed=5, n=100)
        _, y2 = self._series(0.3, amp=4.0, noise=0.3, seed=5, n=100)
        f1, f2 = pp.cadence_phasor(t, y1), pp.cadence_phasor(t, y2)
        self.assertLess(f2["sigmaPhase"], f1["sigmaPhase"])

    def test_lock_categories(self):
        self.assertEqual(pp.lock_category(0.0), "locked")
        self.assertEqual(pp.lock_category(math.pi), "anti-locked")
        self.assertEqual(pp.lock_category(1.5 * pp.PHI_LOCK_RAD),
                         "near-locked")
        self.assertEqual(pp.lock_category(math.pi / 2.0), "unlocked")

    def test_lock_distance_symmetric(self):
        self.assertAlmostEqual(pp.lock_distance(0.2), 0.2, places=12)
        self.assertAlmostEqual(pp.lock_distance(math.pi - 0.2), 0.2,
                               places=12)

    def test_rayleigh_uniform_is_small(self):
        rng = np.random.default_rng(2)
        rbar, p, n = pp.rayleigh(rng.uniform(-math.pi, math.pi, 2000))
        self.assertLess(rbar, 0.1)
        self.assertGreater(p, 0.05)
        self.assertEqual(n, 2000)

    def test_rayleigh_concentrated_is_large(self):
        rbar, p, _ = pp.rayleigh(np.full(50, 0.3))
        self.assertAlmostEqual(rbar, 1.0, places=10)
        self.assertLess(p, 1e-10)

    def test_circular_sd_zero_for_identical(self):
        self.assertAlmostEqual(pp.circular_sd(np.full(5, 1.1)), 0.0,
                               places=5)


class TestNameStem(unittest.TestCase):
    def test_stem(self):
        self.assertEqual(pp.name_stem("INTELSAT 33E"), "INTELSAT")
        self.assertEqual(pp.name_stem("EUTE 8 WEST B"), "EUTE")
        self.assertEqual(pp.name_stem("ASTRA 1KR"), "ASTRA")
        # a stem shorter than three characters is not a family
        self.assertEqual(pp.name_stem("SL-12 R/B(2)"), "")
        self.assertEqual(pp.name_stem("COSMOS 2553"), "COSMOS")
        self.assertEqual(pp.name_stem(None), "")
        self.assertEqual(pp.name_stem("A1"), "")


class TestPersistence(unittest.TestCase):
    """prereg 4.1 on constructed pairs."""

    def _pair(self, dwell_days, sep_deg, break_at=None, gap_at=None,
              n_days=400):
        base = _ms(2010, 1, 1)
        epochs = np.array([base + int(i * DAY_MS) for i in range(n_days)],
                          dtype=np.int64)
        lam_a = np.full(n_days, 10.0)
        lam_b = np.full(n_days, 10.0 + sep_deg)
        # both drift back to a wide separation outside the shared interval
        start = 100
        end = start + int(dwell_days)
        lam_b[:start] = 10.0 + 5.0
        lam_b[end + 1:] = 10.0 + 5.0
        if break_at is not None:
            lam_b[start + break_at] = 10.0 + 5.0
        keep_a = np.ones(n_days, dtype=bool)
        if gap_at is not None:
            keep_a[start + gap_at:start + gap_at + 8] = False
        a = make_series(101, epochs[keep_a], lam_a[keep_a])
        b = make_series(202, epochs, lam_b)
        w = build_world_from([a, b])
        return w, a, b

    def test_detects_a_constructed_pair(self):
        w, a, b = self._pair(80, 0.01)
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        self.assertEqual(len(eps), 1)
        self.assertGreaterEqual(eps[0]["dwellDays"], 56.0)
        self.assertLess(eps[0]["maxAbsSepDeg"], pp.X_PAIR_PRIMARY_DEG)

    def test_separation_above_the_threshold_is_not_a_pair(self):
        w, a, b = self._pair(80, 3.0 * pp.X_PAIR_PRIMARY_DEG)
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        self.assertEqual(eps, [])

    def test_one_day_short_of_the_dwell_is_not_a_pair(self):
        w, a, b = self._pair(55, 0.01)
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        self.assertEqual(eps, [])

    def test_a_break_in_the_middle_does_not_make_one_long_episode(self):
        w, a, b = self._pair(160, 0.01, break_at=80)
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        self.assertEqual(len(eps), 2)
        for e in eps:
            self.assertLess(e["dwellDays"], 150.0)

    def test_gap_longer_than_five_days_refuses_the_episode(self):
        w, a, b = self._pair(80, 0.01, gap_at=30)
        packed = pp.pair_packed(w, a, b)
        stats = {}
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS, stats)
        self.assertEqual(eps, [])
        self.assertGreaterEqual(stats.get("internalGap", 0)
                                + stats.get("dwellTooShort", 0), 1)

    def test_global_origin_day_conversion(self):
        """prereg 3.2's named trap: grid_lo is RELATIVE to the global origin.
        The second object starts a year later, so a site that read grid_lo as
        an absolute epoch would be displaced by that year."""
        base = _ms(2000, 1, 1)
        later = _ms(2001, 1, 1)
        ea = np.array([base + int(i * DAY_MS) for i in range(500)],
                      dtype=np.int64)
        eb = np.array([later + int(i * DAY_MS) for i in range(500)],
                      dtype=np.int64)
        a = make_series(1, ea, np.full(ea.size, 20.0))
        b = make_series(2, eb, np.full(eb.size, 20.005))
        w = build_world_from([a, b])
        self.assertEqual(a.grid_lo, 0)
        self.assertGreater(b.grid_lo, 360)
        first_b_day = int(w.stationed_days[2][0])
        self.assertAlmostEqual(pp.day_to_ms(w, first_b_day) / DAY_MS,
                               (later / DAY_MS) + 0.5, delta=2.0)

    def test_pair_days_are_days_not_epochs(self):
        w, a, b = self._pair(80, 0.01)
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        e = eps[0]
        self.assertAlmostEqual(pp.day_to_ms(w, e["startDay"]) / DAY_MS,
                               e["startMs"] / DAY_MS, delta=1.5)


class TestArrivalOrder(unittest.TestCase):
    def _world(self, b_offset_days):
        base = _ms(2005, 1, 1)
        n = 600
        ea = np.array([base + int(i * DAY_MS) for i in range(n)],
                      dtype=np.int64)
        a = make_series(11, ea, np.full(n, -30.0))
        lam_b = np.full(n, -30.0 + 5.0)
        lam_b[b_offset_days:] = -30.005
        b = make_series(22, ea, lam_b)
        return build_world_from([a, b]), a, b

    def test_resolved_order_and_gap(self):
        w, a, b = self._world(200)
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        self.assertTrue(eps)
        order = pp.arrival_order(w, eps[0], pp.X_PAIR_PRIMARY_DEG)
        self.assertEqual(order["incumbent"], 11)
        self.assertEqual(order["laterArrival"], 22)
        self.assertGreater(order["arrivalGapDays"], 150)
        # object a's segment starts at its first element set -> left censored
        self.assertEqual(order["order"], "censored")

    def test_tie_inside_the_resolution_limit_is_unresolved(self):
        base = _ms(2005, 1, 1)
        n = 600
        ea = np.array([base + int(i * DAY_MS) for i in range(n)],
                      dtype=np.int64)
        # both arrive on the same day, both preceded by their own coverage
        lam_a = np.full(n, 40.0 + 5.0)
        lam_a[200:] = 40.0
        lam_b = np.full(n, 40.0 - 5.0)
        lam_b[200:] = 40.005
        a = make_series(31, ea, lam_a)
        b = make_series(32, ea, lam_b)
        w = build_world_from([a, b])
        packed = pp.pair_packed(w, a, b)
        eps = pp.episodes_for_pair(w, a, b, packed, pp.X_PAIR_PRIMARY_DEG,
                                   pp.D_PAIR_PRIMARY_DAYS)
        self.assertTrue(eps)
        order = pp.arrival_order(w, eps[0], pp.X_PAIR_PRIMARY_DEG)
        self.assertEqual(order["order"], "unresolved")
        self.assertLessEqual(order["arrivalGapDays"],
                             pp.ARRIVAL_RESOLUTION_DAYS)

    def test_resolution_limit_is_the_registered_value(self):
        self.assertAlmostEqual(pp.ARRIVAL_RESOLUTION_DAYS, 1.73, places=10)


class TestHazardMachinery(unittest.TestCase):
    def test_merge_overlapping_windows(self):
        self.assertEqual(pp._merge([(0, 10), (5, 20), (30, 40)]),
                         [[0, 20], [30, 40]])

    def test_baseline_excludes_the_exposed_window(self):
        base = _ms(2000, 1, 1)
        n = 400
        e = np.array([base + int(i * DAY_MS) for i in range(n)],
                     dtype=np.int64)
        s = make_series(7, e, np.full(n, 5.0))
        w = build_world_from([s])
        total = w.stationed_days[7].size
        ev, exp_all = pp.baseline_for(w, 7, [], "relocation")
        self.assertEqual(exp_all, float(total))
        lo = int(w.stationed_days[7][10])
        _, exp_cut = pp.baseline_for(w, 7, [(lo, lo + 50)], "relocation")
        self.assertAlmostEqual(exp_all - exp_cut, 50.0, delta=1.0)

    def test_exposure_stops_at_the_horizon(self):
        base = _ms(2000, 1, 1)
        n = 800
        e = np.array([base + int(i * DAY_MS) for i in range(n)],
                     dtype=np.int64)
        s = make_series(8, e, np.full(n, 5.0))
        w = build_world_from([s])
        t0 = int(w.stationed_days[8][10])
        ev, exposure = pp.exposure_for(w, 8, t0, 100.0, "relocation")
        self.assertEqual(ev, 0)
        self.assertAlmostEqual(exposure, 100.0, delta=1.0)

    def test_verdict_falsified_when_both_intervals_contain_one(self):
        out = {"gates": {"B": {"fired": False}}}
        prim = {"L1": {"passed": True, "null95": [0.9, 1.1]},
                "L2": {"passed": True},
                "exposed": {"events": 50},
                "hrSelf": 1.0, "hrSelf95": [0.8, 1.3],
                "hrControl": 1.0, "hrControl95": [0.7, 1.4]}
        self.assertEqual(pp.verdict(out, prim)["E3"], "FALSIFIED")

    def test_verdict_not_read_when_leak_fires(self):
        out = {"gates": {"B": {"fired": True}}}
        prim = {"L1": {"passed": True, "null95": [0.9, 1.1]},
                "L2": {"passed": True}, "exposed": {"events": 50},
                "hrSelf": 3.0, "hrSelf95": [2.0, 4.0],
                "hrControl": 3.0, "hrControl95": [2.0, 4.0]}
        self.assertEqual(pp.verdict(out, prim)["E3"], "NOT READ")

    def test_verdict_underpowered_below_the_bar(self):
        out = {"gates": {"B": {"fired": False}}}
        prim = {"L1": {"passed": True, "null95": [0.9, 1.1]},
                "L2": {"passed": True}, "exposed": {"events": 3},
                "hrSelf": 3.0, "hrSelf95": [2.0, 4.0],
                "hrControl": 3.0, "hrControl95": [2.0, 4.0]}
        self.assertEqual(pp.verdict(out, prim)["E3"], "UNDERPOWERED")

    def test_verdict_supported_requires_all_four_clauses(self):
        out = {"gates": {"B": {"fired": False}}}
        prim = {"L1": {"passed": True, "null95": [0.9, 1.1]},
                "L2": {"passed": True}, "exposed": {"events": 50},
                "hrSelf": 3.0, "hrSelf95": [2.0, 4.0],
                "hrControl": 2.5, "hrControl95": [1.8, 3.4]}
        self.assertEqual(pp.verdict(out, prim)["E3"], "SUPPORTED")
        prim["hrControl95"] = [0.9, 3.4]
        self.assertEqual(pp.verdict(out, prim)["E3"], "INCONCLUSIVE")


class TestFraming(unittest.TestCase):
    """prereg 0: the vocabulary ban, by word boundary (the T8d lesson --
    'nation' is a substring of 'inclination')."""

    def test_word_boundaries(self):
        self.assertEqual(pp.banned_hits("the inclination was 0.05 deg"), [])
        self.assertEqual(pp.banned_hits("station-keeping and stationed"), [])
        self.assertTrue(pp.banned_hits("it moved to " + "av" + "oid it"))

    def test_module_source_is_clean(self):
        hits = pp.banned_hits(Path(pp.__file__).read_text())
        self.assertEqual(hits, [], f"banned vocabulary in the module: {hits}")

    def test_committed_artefacts_are_clean(self):
        docs = _REPO / "docs"
        for name in ("persistent-pairs-20260922.jsonl",
                     "persistent-pairs-cases-20260922.md",
                     "persistent-pairs-results-20260922.md"):
            path = docs / name
            if not path.exists():
                continue
            hits = pp.banned_hits(path.read_text())
            self.assertEqual(hits, [], f"banned vocabulary in {name}: {hits}")

    def test_no_detector_branch_reads_a_registry_code(self):
        """Metadata may be written onto an output row and read nowhere else.
        Every reference to a metadata key must sit inside one of the three
        functions registered to carry metadata."""
        source = Path(pp.__file__).read_text()
        tree = ast.parse(source)
        allowed = {"family_flags", "row_for", "case_block", "write_cases",
                   "build_world", "banned_hits"}
        keys = {"country", "name", "objectId", "launchDate"}
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name in allowed:
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and sub.value in keys:
                    offenders.append((node.name, sub.value))
        self.assertEqual(offenders, [],
                         f"metadata read outside the allowed sites: "
                         f"{offenders}")

    def test_registry_code_absent_from_the_ranking_key(self):
        source = Path(pp.__file__).read_text()
        rank = source.split("def rank_cases", 1)[1].split("\ndef ", 1)[0]
        for key in ("country", "registry", "objectId", "launchDate"):
            self.assertNotIn(key, rank)


class TestLeakCheckShape(unittest.TestCase):
    def test_leak_check_compares_rates_not_counts(self):
        source = Path(pp.__file__).read_text()
        body = source.split("def leak_check", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("RatePerPairDay", body)
        self.assertIn("pair_days", body)

    def test_never_manoeuvred_evidence_bar(self):
        self.assertEqual(pp.NEVER_MIN_ELEMENT_SETS, 200)
        self.assertEqual(pp.NEVER_MIN_SPAN_DAYS, 365.0)

    def test_gate_b_bar_is_t8bs(self):
        self.assertAlmostEqual(pp.GATE_B_LEAK_RATIO, 0.10, places=12)


class TestCompositeRank(unittest.TestCase):
    def test_ties_take_the_mid_rank(self):
        """The registered percentile rank must not order equal values by
        their position in the array: most ranked episodes score exactly 0
        on the cadence component."""
        r = pp.percentile_rank([0.0, 0.0, 0.0, 0.0, 5.0])
        self.assertEqual(list(r[:4]), [1.5 / 4] * 4)
        self.assertEqual(r[4], 1.0)
        self.assertEqual(list(pp.percentile_rank([1.0, 2.0, 3.0])),
                         [0.0, 0.5, 1.0])
        self.assertEqual(list(pp.percentile_rank([7.0, 7.0])), [0.5, 0.5])

    def test_equal_weights_and_four_components(self):
        source = Path(pp.__file__).read_text()
        body = source.split("def rank_cases", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("/ 4.0", body)
        self.assertEqual(body.count("prank("), 4)   # four components


if __name__ == "__main__":
    unittest.main()
