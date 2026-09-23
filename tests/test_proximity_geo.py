"""Tests for T8a (tools/proximity_geo.py).

Coverage required by `docs/proximity-preregistration-20260922.md` section 8:
GMST against an independently computed epoch, lambda against a constructed
element set at a known longitude, the drift relation, wrap-around at +/-180,
a synthetic approach that must be detected, a synthetic drift-through that
must NOT be, a synthetic standing co-location that must not become an event,
and the attribution rule on a pair where the target moved instead.
"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools import proximity_geo as pg  # noqa: E402

DAY_MS = 86400000.0
J2000_MS = 946728000000  # 2000-01-01T12:00:00Z


def _ms(year, month, day, hour=0, minute=0, second=0):
    import datetime as dt
    return int(dt.datetime(year, month, day, hour, minute, second,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


def make_series(norad, epochs_ms, lam_deg, drift_deg_per_day=None,
                ecc=1e-4, inc=0.05):
    """Build a Series with a prescribed mean-longitude history.

    Constructed backwards through prereg 2.2: RAAN and argp are zeroed and the
    mean anomaly carries lambda + theta_G, which is exactly the inverse of the
    estimator under test, so the test is of the pipeline and not of a
    tautology in the estimator's own algebra.
    """
    epochs_ms = np.asarray(epochs_ms, dtype=np.int64)
    lam = np.asarray(lam_deg, dtype=np.float64)
    if drift_deg_per_day is None:
        drift_deg_per_day = np.gradient(lam, epochs_ms / DAY_MS) \
            if lam.size > 1 else np.zeros_like(lam)
    drift = np.broadcast_to(np.asarray(drift_deg_per_day, dtype=np.float64),
                            lam.shape).copy()
    mean_motion = (drift + pg.OMEGA_E_DEG_PER_DAY) / 360.0
    ma = np.mod(lam + pg.gmst_deg(epochs_ms), 360.0)
    return pg.Series(norad, epochs_ms, mean_motion,
                     np.full(lam.shape, ecc), np.full(lam.shape, inc),
                     np.zeros_like(lam), np.zeros_like(lam), ma)


class TestConstants(unittest.TestCase):
    def test_geostationary_radius(self):
        # prereg 2.1
        self.assertAlmostEqual(pg.A_GEO_KM, 42164.17, places=1)
        self.assertAlmostEqual(pg.A_GEO_KM - pg.EARTH_RADIUS_KM, 35786.03, places=1)

    def test_drift_semi_major_relation(self):
        # prereg 2.3: -0.0128421 deg/day per km, derived independently here
        n = math.sqrt(pg.MU_KM3_S2 / pg.A_GEO_KM ** 3)          # rad/s
        expect = -1.5 * (n * 86400.0 * 180.0 / math.pi) / pg.A_GEO_KM
        self.assertAlmostEqual(pg.DRIFT_PER_KM, expect, places=7)
        self.assertAlmostEqual(pg.DRIFT_PER_KM, -0.0128421, places=7)
        # round trip
        self.assertAlmostEqual(float(pg.semi_major_offset_km(-0.0128421)), 1.0,
                               places=3)

    def test_angular_scale(self):
        self.assertAlmostEqual(pg.KM_PER_DEG_GEO, 735.904, places=2)

    def test_triaxiality_acceleration(self):
        # prereg 2.6: ~1.7e-3 deg/day^2, the bound that chose D
        self.assertTrue(1.5e-3 < pg.LAMBDA_DDOT_MAX < 2.0e-3)

    def test_libration_zone_widths(self):
        # prereg 2.6 table; the reason D=30 is primary
        self.assertAlmostEqual(pg.libration_zone_half_width_deg(0.1, 30.0),
                               3.75, places=1)
        self.assertAlmostEqual(pg.libration_zone_half_width_deg(0.1, 14.0),
                               18.43, places=1)
        self.assertIsNone(pg.libration_zone_half_width_deg(0.1, 7.0))
        self.assertIsNone(pg.libration_zone_half_width_deg(0.2, 14.0))

    def test_drift_per_m_s_constant_is_recorded_only(self):
        # prereg 2.5: the constant exists; nothing multiplies it by a mass
        self.assertAlmostEqual(pg.DRIFT_PER_M_S, 0.35222, places=4)
        source = (_REPO / "tools" / "proximity_geo.py").read_text()
        # The commercial-civil-only overlay policy, enforced rather than
        # intended: the constant is DEFINED and REPORTED, and multiplies
        # nothing. Two references only -- its definition and the constants
        # block of the receipt.
        self.assertEqual(source.count("DRIFT_PER_M_S"), 2)
        for banned in ("propellant", "dry_mass", "isp_s", "specific_impulse"):
            self.assertNotIn(banned, source.lower())


class TestGmst(unittest.TestCase):
    def test_j2000(self):
        """GMST at J2000.0 is 280.46061837 deg (IAU 1982), computed here from
        the independent Meeus form rather than from the module's own series."""
        got = float(pg.gmst_deg(J2000_MS))
        self.assertAlmostEqual(got, 280.46061837, places=4)

    def test_advances_at_the_sidereal_rate(self):
        a = float(pg.gmst_deg(J2000_MS))
        b = float(pg.gmst_deg(J2000_MS + int(DAY_MS)))
        self.assertAlmostEqual((b - a) % 360.0, pg.OMEGA_E_DEG_PER_DAY % 360.0,
                               places=4)

    def test_independent_epoch(self):
        """2026-09-22T00:00:00Z, from the Meeus polynomial evaluated here."""
        t_ms = _ms(2026, 9, 22)
        jd = t_ms / DAY_MS + 2440587.5
        tc = (jd - 2451545.0) / 36525.0
        expect = (280.46061837 + 360.98564736629 * (jd - 2451545.0)
                  + 0.000387933 * tc * tc - tc ** 3 / 38710000.0) % 360.0
        self.assertAlmostEqual(float(pg.gmst_deg(t_ms)), expect, places=3)


class TestLongitude(unittest.TestCase):
    def test_known_longitude(self):
        t = _ms(2020, 6, 1)
        theta = float(pg.gmst_deg(t))
        for target in (-179.5, -90.0, 0.0, 75.1, 179.9):
            lam = float(pg.mean_longitude_deg(theta / 3.0, theta / 3.0,
                                              theta / 3.0 + target, t))
            self.assertAlmostEqual(lam, target, places=6)

    def test_wrap_boundary(self):
        self.assertAlmostEqual(float(pg.wrap180(180.0)), 180.0)
        self.assertAlmostEqual(float(pg.wrap180(-180.0)), 180.0)
        self.assertAlmostEqual(float(pg.wrap180(181.0)), -179.0)
        self.assertAlmostEqual(float(pg.wrap180(-181.0)), 179.0)
        self.assertAlmostEqual(float(pg.wrap180(540.0)), 180.0)

    def test_geostationary_object_holds_its_longitude(self):
        t = np.arange(0, 100) * int(DAY_MS) + _ms(2019, 1, 1)
        s = make_series(1, t, np.full(t.size, 120.0), drift_deg_per_day=0.0)
        self.assertLess(float(np.max(np.abs(pg.wrap180(s.lam - 120.0)))), 1e-6)
        self.assertLess(float(np.max(np.abs(s.drift))), 1e-9)

    def test_unwrap_across_the_dateline(self):
        t = np.arange(0, 40) * int(DAY_MS) + _ms(2019, 1, 1)
        lam = pg.wrap180(175.0 + 0.5 * np.arange(40))   # crosses +180
        s = make_series(2, t, lam, drift_deg_per_day=0.5)
        step = np.diff(s.lam_unwrapped)
        self.assertLess(float(np.max(np.abs(step - 0.5))), 1e-6)

    def test_drift_rate_from_mean_motion(self):
        n_geo = pg.OMEGA_E_DEG_PER_DAY / 360.0
        self.assertAlmostEqual(float(pg.drift_rate_deg_per_day(n_geo)), 0.0,
                               places=9)
        # 1 km high -> 0.0128 deg/day west (prereg 2.3)
        a = pg.A_GEO_KM + 1.0
        n = math.sqrt(pg.MU_KM3_S2 / a ** 3) * 86400.0 / (2 * math.pi)
        self.assertAlmostEqual(float(pg.drift_rate_deg_per_day(n)), -0.0128421,
                               places=5)


class TestInterpolation(unittest.TestCase):
    def test_gap_refusal(self):
        t = np.asarray([0, 1, 2, 20, 21], dtype=np.int64) * int(DAY_MS)
        y = np.asarray([0.0, 1.0, 2.0, 20.0, 21.0])
        q = np.asarray([1.5, 10.0, 20.5]) * DAY_MS
        got = pg.interpolate(t, y, q)
        self.assertAlmostEqual(got[0], 1.5)
        self.assertTrue(np.isnan(got[1]))       # inside the 18-day gap
        self.assertAlmostEqual(got[2], 20.5)


def _pair(a_lam, b_lam, days=400, start=None):
    start = start or _ms(2015, 1, 1)
    t = np.arange(days) * int(DAY_MS) + start
    a = make_series(101, t, a_lam(np.arange(days, dtype=float)))
    b = make_series(202, t, b_lam(np.arange(days, dtype=float)))
    return a, b


class TestEventDetection(unittest.TestCase):
    def test_synthetic_approach_is_detected(self):
        """A parks at 10 deg, drifts 0.1 deg/day to 20 deg, stays. B sits at
        20 deg throughout. prereg 4: this is an event and A is the approacher."""
        def a_lam(d):
            out = np.full(d.shape, 10.0)
            moving = (d >= 100) & (d < 200)
            out[moving] = 10.0 + 0.1 * (d[moving] - 100)
            out[d >= 200] = 20.0
            return out
        a, b = _pair(a_lam, lambda d: np.full(d.shape, 20.0))
        events, standing = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["approacherNorad"], 101)
        self.assertEqual(e["targetNorad"], 202)
        self.assertEqual(e["attribution"], "resolved")
        self.assertFalse(standing)
        self.assertGreater(e["loiterDays"], pg.D_PRIMARY_DAYS)
        self.assertLess(e["closestSeparationDeg"], pg.X_PRIMARY_DEG)
        self.assertGreater(e["approacherMotionDeg"], pg.X_FAR_DEG - pg.X_PRIMARY_DEG)
        self.assertAlmostEqual(e["closestSeparationKm"],
                               e["closestSeparationDeg"] * pg.KM_PER_DEG_GEO,
                               places=6)

    def test_drift_through_is_not_an_event(self):
        """The cannot-manoeuvre control's signature: A crosses B's longitude at
        a constant 0.1 deg/day and never stops. Time inside +/-0.1 deg is
        2X/|ddot| = 2 days, far below D."""
        a, b = _pair(lambda d: 10.0 + 0.1 * d,
                     lambda d: np.full(d.shape, 20.0))
        events, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(events, [])

    def test_slow_drift_through_cannot_satisfy_the_look_back(self):
        """A structural protection worth stating: a constant drift slow enough
        to dwell inside +/-X for D days cannot also have been X_far away
        within T_look. Dwell is 2X/|ddot| = 20 d at 0.01 deg/day, but covering
        the 1.9 deg from X_far at that rate takes 190 d > T_look = 180 d. So
        the registered definition rejects it at BOTH D = 30 d and D = 14 d."""
        a, b = _pair(lambda d: 18.0 + 0.01 * d,
                     lambda d: np.full(d.shape, 20.0), days=600)
        self.assertEqual(pg.pair_events(a, b, pg.X_PRIMARY_DEG, 30.0)[0], [])
        self.assertEqual(pg.pair_events(a, b, pg.X_PRIMARY_DEG, 14.0)[0], [])

    def test_libration_turnaround_is_why_D_is_30_not_14(self):
        """The prereg 2.6 table, exercised. An uncontrolled object decelerating
        at the registered triaxial rate turns around at B's longitude and
        dwells 2*sqrt(2X/lambda_ddot) = 21.7 d inside +/-0.1 deg. That passes
        D = 14 d -- which is why that arm is labelled WEAK -- and fails the
        primary D = 30 d."""
        k = pg.LAMBDA_DDOT_MAX
        d0 = math.sqrt(2.0 * k * 8.0)          # starts 8 deg out, stops at B
        t_stop = d0 / k
        def a_lam(d):
            return 20.0 - 8.0 + d0 * d - 0.5 * k * d * d
        a, b = _pair(a_lam, lambda d: np.full(d.shape, 20.0),
                     days=int(2 * t_stop) + 10)
        weak, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, 14.0)
        self.assertEqual(len(weak), 1)
        self.assertLess(weak[0]["loiterDays"], 30.0)
        primary, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, 30.0)
        self.assertEqual(primary, [])

    def test_standing_colocation_is_not_an_event(self):
        """Two objects that were never X_far apart produce no event, whatever
        their separation history inside the box (prereg 4, co-location vs
        approach)."""
        a, b = _pair(lambda d: 20.0 + 0.04 * np.sin(d / 7.0),
                     lambda d: np.full(d.shape, 20.0))
        events, standing = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(events, [])
        self.assertTrue(standing)

    def test_attribution_follows_the_object_that_moved(self):
        """The TARGET moves to the approacher's longitude: prereg 4.3 must name
        the object whose elements changed, regardless of argument order."""
        def b_lam(d):
            out = np.full(d.shape, 20.0)
            moving = (d >= 100) & (d < 200)
            out[moving] = 20.0 - 0.1 * (d[moving] - 100)
            out[d >= 200] = 10.0
            return out
        a, b = _pair(lambda d: np.full(d.shape, 10.0), b_lam)
        events, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["approacherNorad"], 202)
        self.assertEqual(events[0]["targetNorad"], 101)

    def test_symmetric_mutual_approach_is_rejected_and_counted(self):
        """Both objects close half the gap. Neither meets the registered 80%
        bar, so prereg 4.3 names no approacher and this is NOT an event. The
        rejection is counted rather than dropped in silence."""
        def a_lam(d):
            out = np.full(d.shape, 10.0)
            m = (d >= 100) & (d < 200)
            out[m] = 10.0 + 0.05 * (d[m] - 100)
            out[d >= 200] = 15.0
            return out
        def b_lam(d):
            out = np.full(d.shape, 20.0)
            m = (d >= 100) & (d < 200)
            out[m] = 20.0 - 0.05 * (d[m] - 100)
            out[d >= 200] = 15.0
            return out
        a, b = _pair(a_lam, b_lam)
        stats = {}
        events, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS,
                                   stats=stats)
        self.assertEqual(events, [])
        self.assertEqual(stats.get("attributionUnresolved"), 1)

    def test_both_moved_the_same_way_is_ambiguous(self):
        """Ambiguity is reachable when both objects travel far in the SAME
        direction while converging: each clears the 80% bar on a small
        relative change."""
        def a_lam(d):
            out = np.full(d.shape, 10.0)
            m = (d >= 100) & (d < 200)
            out[m] = 10.0 + 0.10 * (d[m] - 100)
            out[d >= 200] = 20.0
            return out
        def b_lam(d):
            out = np.full(d.shape, 12.0)
            m = (d >= 100) & (d < 200)
            out[m] = 12.0 + 0.08 * (d[m] - 100)
            out[d >= 200] = 20.0
            return out
        a, b = _pair(a_lam, b_lam)
        events, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["attribution"], "ambiguous")

    def test_departure_is_recorded(self):
        def a_lam(d):
            out = np.full(d.shape, 10.0)
            m = (d >= 100) & (d < 200)
            out[m] = 10.0 + 0.1 * (d[m] - 100)
            out[(d >= 200) & (d < 300)] = 20.0
            m2 = d >= 300
            out[m2] = 20.0 + 0.1 * (d[m2] - 300)
            return out
        a, b = _pair(a_lam, lambda d: np.full(d.shape, 20.0))
        events, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(events[0]["departureMs"])
        self.assertGreater(events[0]["departureMs"], events[0]["loiterEndMs"])

    def test_event_across_the_dateline(self):
        def a_lam(d):
            out = np.full(d.shape, 170.0)
            m = (d >= 100) & (d < 200)
            out[m] = 170.0 + 0.15 * (d[m] - 100)
            out[d >= 200] = 185.0
            return pg.wrap180(out)
        a, b = _pair(a_lam, lambda d: pg.wrap180(np.full(d.shape, 185.0)))
        events, _ = pg.pair_events(a, b, pg.X_PRIMARY_DEG, pg.D_PRIMARY_DAYS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["approacherNorad"], 101)


class TestSegmentationAndBurns(unittest.TestCase):
    def test_station_segments(self):
        days = 400
        t = np.arange(days) * int(DAY_MS) + _ms(2015, 1, 1)
        lam = np.full(days, 30.0)
        lam[150:250] = 30.0 + 0.2 * (np.arange(100))   # a 20 deg relocation
        lam[250:] = 50.0
        s = make_series(7, t, lam)
        pg.build_daily_grid([s])
        segs = pg.station_segments(s)
        self.assertGreaterEqual(len(segs), 2)
        lons = [float(pg.wrap180(np.median(s.grid[i0:i1 + 1]))) for i0, i1 in segs]
        self.assertAlmostEqual(min(lons), 30.0, places=1)
        self.assertAlmostEqual(max(lons), 50.0, places=1)
        rel = pg.relocations(s, segs)
        self.assertGreaterEqual(len(rel), 1)
        self.assertAlmostEqual(rel[0]["netChangeDeg"], 20.0, places=1)

    def test_drift_change_flag_fires_on_the_second_sample(self):
        days = 60
        t = np.arange(days) * int(DAY_MS) + _ms(2015, 1, 1)
        drift = np.zeros(days)
        drift[30:] = 0.5
        lam = np.cumsum(np.concatenate(([0.0], drift[:-1])))
        s = make_series(9, t, lam, drift_deg_per_day=drift)
        t_flag, size = pg.drift_change_flags(s, sigma_n=1e-5)
        self.assertGreater(t_flag.size, 0)
        # first confirmed flag is the epoch of the SECOND changed element set
        self.assertEqual(int(t_flag[0]), int(t[31]))
        self.assertAlmostEqual(float(size[0]), 0.5, places=6)

    def test_single_outlier_does_not_flag(self):
        days = 60
        t = np.arange(days) * int(DAY_MS) + _ms(2015, 1, 1)
        drift = np.zeros(days)
        drift[40] = 0.5                     # one bad fit only
        s = make_series(10, t, np.zeros(days), drift_deg_per_day=drift)
        t_flag, _ = pg.drift_change_flags(s, sigma_n=1e-5)
        self.assertEqual(t_flag.size, 0)

    def test_burn_floor_is_respected(self):
        """A change of 0.005 deg/day is below the registered 0.010 floor and
        must not flag however small sigma_n is (prereg 5.5)."""
        days = 60
        t = np.arange(days) * int(DAY_MS) + _ms(2015, 1, 1)
        drift = np.zeros(days)
        drift[30:] = 0.005
        s = make_series(11, t, np.zeros(days), drift_deg_per_day=drift)
        self.assertEqual(pg.drift_change_flags(s, sigma_n=1e-12)[0].size, 0)


class TestStatistics(unittest.TestCase):
    def test_icc_separates_structured_from_unstructured(self):
        rng = np.random.default_rng(0)
        structured = [rng.normal(m, 0.05, 4) for m in range(1, 9)]
        unstructured = [rng.normal(4.0, 2.0, 4) for _ in range(8)]
        self.assertGreater(pg.icc_one_way(structured), 0.9)
        self.assertLess(pg.icc_one_way(unstructured), 0.5)

    def test_bh_controls_at_q(self):
        p = np.asarray([0.001, 0.008, 0.02, 0.4, 0.9])
        got = pg.benjamini_hochberg(p, q=0.05)
        self.assertTrue(got[0] and got[1])
        self.assertFalse(got[3] or got[4])

    def test_poisson_sf(self):
        self.assertAlmostEqual(pg.poisson_sf(1, 2.0), 1 - math.exp(-2.0), places=12)
        self.assertAlmostEqual(pg.poisson_sf(0, 2.0), 1.0, places=12)
        self.assertLess(pg.poisson_sf(10, 1.0), 1e-6)

    def test_theil_sen(self):
        t = np.arange(50, dtype=float)
        y = 3.0 + 0.25 * t
        y[7] = 900.0                        # one gross outlier
        self.assertAlmostEqual(pg.theil_sen_slope(t, y), 0.25, places=6)


class TestPolicyGuards(unittest.TestCase):
    def test_no_intent_language_in_the_tool(self):
        """The framing rule is enforced, not merely intended."""
        text = (_REPO / "tools" / "proximity_geo.py").read_text().lower()
        for banned in ("spying", "spy ", "inspector", "inspection", "threat",
                       "adversary", "hostile", "shadowing", "stalking"):
            self.assertNotIn(banned, text, f"intent language {banned!r} present")

    def test_country_is_metadata_only(self):
        """No detector branch may read a country code. The only occurrences in
        the module are the metadata read and the event-row copy."""
        import inspect
        for fn in (pg.pair_events, pg.station_segments, pg.drift_change_flags,
                   pg.relocations, pg.permutation_null, pg.candidate_pairs,
                   pg.calibrate_sigma_n, pg.repetition_stats):
            src = inspect.getsource(fn).lower()
            self.assertNotIn("country", src,
                             f"{fn.__name__} reads a country code")
        # the class assignment reads object_type and nothing else
        self.assertNotIn("country", inspect.getsource(pg.class_of).lower())


if __name__ == "__main__":
    unittest.main()
