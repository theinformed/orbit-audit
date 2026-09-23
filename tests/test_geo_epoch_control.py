"""Tests for the GEO libration-epoch control (tools/geo_epoch_control.py).

The first assertions are THE BUG, both of them registered in advance by
docs/geo-libration-epoch-control-preregistration-20260922.md section 7 V-E3:

1. A keeping interval sandwiched between two free intervals must be SPLIT OUT.
   An epoch finder that walks the history looking for quiet stretches and
   merges across a flagged one -- or that averages the whole history into a
   single verdict, which is what the object-level control did -- returns ONE
   epoch spanning the keeping and so carries the controlled interval into the
   control. The registered rule must return TWO epochs whose union excludes
   the keeping interval.
2. A free librator sampled at 2-day spacing must be ADMITTED. At that spacing
   free triaxial motion moves the drift rate by A * 11 d = 1.87e-2 deg/day
   across the residual rule's own baseline, which is 6.2 times the measured
   5 sigma_n term and 1.9 times the constant floor the earlier rule used. An
   implementation that thresholds on a constant, or that fails to predict and
   subtract free motion, flags the librator and admits nothing.

Then: the first integral against the closed-form amplitude-rate relation and
against an integrated pendulum; the separatrix; the one-sided energy bound and
its derived blindness to a symmetric velocity reversal; the derived keeper
displacement u*; the sample-level rules, each failed one at a time; the
minimum-length rule; the cadence rejection; the turnaround stratification; the
exposure and leak arithmetic on fixtures; the agreement of the residual detail
function with the committed rule it re-derives; and the vocabulary ban.
"""

import json
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
from tools import geo_epoch_control as gec                    # noqa: E402

SIGMA_N = 0.0006038533519066339          # T8a's measured value, unchanged
DAY_MS = pp.DAY_MS


class _S:
    """The three fields the epoch finder reads. Nothing else is available to
    it, so nothing else can enter a decision."""

    __slots__ = ("norad", "epoch_ms", "lam", "drift", "lam_unwrapped")

    def __init__(self, norad, epoch_ms, lam, drift):
        self.norad = int(norad)
        self.epoch_ms = np.asarray(epoch_ms, dtype=np.float64)
        self.lam = np.asarray(lam, dtype=np.float64)
        self.drift = np.asarray(drift, dtype=np.float64)
        self.lam_unwrapped = self.lam


def _integrate(u0_deg, v0_rad, days, step=0.05):
    """One pendulum, u'' = -A sin 2u, in radians."""
    a = gec.A_RAD_PER_DAY2
    u = math.radians(u0_deg)
    v = float(v0_rad)
    n = int(round(days / step))
    ts, us, vs = [], [], []

    def acc(x):
        return -a * math.sin(2.0 * x)

    for k in range(n + 1):
        ts.append(k * step)
        us.append(u)
        vs.append(v)
        k1u, k1v = v, acc(u)
        k2u, k2v = v + 0.5 * step * k1v, acc(u + 0.5 * step * k1u)
        k3u, k3v = v + 0.5 * step * k2v, acc(u + 0.5 * step * k2u)
        k4u, k4v = v + step * k3v, acc(u + step * k3u)
        u += (step / 6.0) * (k1u + 2 * k2u + 2 * k3u + k4u)
        v += (step / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)
    return np.asarray(ts), np.asarray(us), np.asarray(vs)


def librator(u_max_deg=20.0, days=1500.0, spacing=0.865, sigma_n=None,
             seed=7, t0_days=20000.0, norad=900001, phase_deg=None):
    """A free librator sampled at a chosen element-set spacing."""
    sigma_n = SIGMA_N if sigma_n is None else sigma_n
    u0 = -u_max_deg if phase_deg is None else phase_deg
    k2 = math.sin(math.radians(u_max_deg)) ** 2
    inner = max(0.0, k2 - math.sin(math.radians(u0)) ** 2)
    v0 = math.sqrt(2.0 * gec.A_RAD_PER_DAY2 * inner)
    ts, us, vs = _integrate(u0, v0, days)
    keep = max(1, int(round(spacing / 0.05)))
    ts, us, vs = ts[::keep], us[::keep], vs[::keep]
    lam = pg.wrap180(np.degrees(us) + gpc.STABLE_LONGITUDES_DEG[0])
    drift = np.degrees(vs)
    if sigma_n:
        drift = drift + np.random.default_rng(seed).normal(
            0.0, sigma_n, size=drift.size)
    return _S(norad, (ts + t0_days) * DAY_MS, lam, drift)


def keeper(days=400.0, spacing=0.865, slot=35.0, sigma_n=None, seed=8,
           t0_days=20000.0, norad=800001):
    """A longitude sawtooth about a slot at the measured 14.00-day cycle, with
    the ramp rate the triaxial acceleration at the object's own slot."""
    sigma_n = SIGMA_N if sigma_n is None else sigma_n
    a = abs(float(gpc.free_acceleration(np.array([slot]))[0]))
    half = a * gec.EW_PERIOD_DAYS / 4.0
    t = np.arange(0.0, days, spacing)
    cycle = np.mod(t, gec.EW_PERIOD_DAYS)
    d = -half + a * cycle
    lam = slot + np.cumsum(d - np.mean(d)) * spacing
    if sigma_n:
        d = d + np.random.default_rng(seed).normal(0.0, sigma_n, size=d.size)
    return _S(norad, (t + t0_days) * DAY_MS, pg.wrap180(lam), d)


def _stable_east():
    return gpc.STABLE_LONGITUDES_DEG[0]


class TheBug(unittest.TestCase):
    """The two registered bugs, asserted before anything else."""

    def test_keeper_between_two_free_intervals_is_split_out(self):
        free_a = librator(u_max_deg=30.0, days=700.0, phase_deg=-30.0)
        # the keeping interval, at a slot the librator sweeps through and
        # well outside the derived blind spot u*
        keep = keeper(days=400.0, slot=_stable_east() + 20.0)
        # the second free interval
        free_b = librator(u_max_deg=30.0, days=700.0, phase_deg=-25.0,
                          seed=9)

        t = np.concatenate([
            free_a.epoch_ms,
            keep.epoch_ms - keep.epoch_ms[0] + free_a.epoch_ms[-1]
            + 0.865 * DAY_MS,
            free_b.epoch_ms - free_b.epoch_ms[0]
            + free_a.epoch_ms[-1] + (400.0 + 2 * 0.865) * DAY_MS])
        lam = np.concatenate([free_a.lam, keep.lam, free_b.lam])
        drift = np.concatenate([free_a.drift, keep.drift, free_b.drift])
        s = _S(700001, t, lam, drift)

        eps, _d = gec.find_epochs(s, SIGMA_N)
        self.assertGreaterEqual(len(eps), 2,
                                "the keeping interval was averaged in")
        k0 = float(free_a.epoch_ms[-1])
        k1 = k0 + 400.0 * DAY_MS
        for e in eps:
            overlap = (min(e["endMs"], k1) - max(e["startMs"], k0)) / DAY_MS
            self.assertLessEqual(
                overlap, 2.0 * gec.EW_PERIOD_DAYS,
                "an admitted epoch swallowed the keeping interval")

    def test_librator_sampled_at_two_day_spacing_is_admitted(self):
        s = librator(u_max_deg=20.0, days=1200.0, spacing=2.0,
                     sigma_n=SIGMA_N, norad=900002)
        eps, diag = gec.find_epochs(s, SIGMA_N)
        self.assertTrue(eps, f"nothing admitted at 2-day spacing: {diag}")
        self.assertGreaterEqual(sum(e["days"] for e in eps), 200.0)

    def test_two_day_spacing_free_motion_exceeds_the_old_constant_floor(self):
        """Why the previous test is a test and not a formality."""
        baseline_span = 5.5 * 2.0
        free = gec.A_DEG_PER_DAY2 * baseline_span
        self.assertGreater(free, pg.BURN_FLOOR_DEG_PER_DAY)
        self.assertGreater(free, gec.SIGMA_K * SIGMA_N)


class FirstIntegral(unittest.TestCase):

    def test_s_equals_sin2_umax_at_the_turning_point(self):
        for u_max in (1.0, 5.0, 20.0, 45.0, 60.0):
            lam = _stable_east() + u_max
            s, u, _st = gec.implied_s(np.array([lam]), np.array([0.0]))
            self.assertAlmostEqual(float(s[0]),
                                   math.sin(math.radians(u_max)) ** 2, 12)
            self.assertAlmostEqual(float(u[0]), u_max, 9)

    def test_s_equals_sin2_umax_at_the_stable_longitude(self):
        for u_max in (1.0, 20.0, 60.0):
            v = gpc.peak_rate_deg_per_day(u_max)
            s, _u, _st = gec.implied_s(np.array([_stable_east()]),
                                       np.array([v]))
            self.assertAlmostEqual(float(s[0]),
                                   math.sin(math.radians(u_max)) ** 2, 10)

    def test_s_is_conserved_along_an_integrated_pendulum(self):
        s = librator(u_max_deg=40.0, days=1200.0, sigma_n=0.0)
        vals, _u, _st = gec.implied_s(s.lam, s.drift)
        self.assertLess(float(np.max(vals) - np.min(vals)), 1e-6)

    def test_implied_u_max_inverts_s(self):
        for u_max in (1.0, 17.5, 60.0, 89.0):
            s = math.sin(math.radians(u_max)) ** 2
            self.assertAlmostEqual(float(gec.implied_u_max_deg(s)), u_max, 9)

    def test_separatrix_is_s_equal_one(self):
        v_sep = gpc.PEAK_RATE_COEFF_DEG_PER_DAY      # sin(90 deg) = 1
        s, _u, _st = gec.implied_s(np.array([_stable_east()]),
                                   np.array([v_sep]))
        self.assertAlmostEqual(float(s[0]), 1.0, 12)
        s2, _u2, _st2 = gec.implied_s(np.array([_stable_east()]),
                                      np.array([1.01 * v_sep]))
        self.assertGreater(float(s2[0]), 1.0)


class EnergyBound(unittest.TestCase):

    def test_free_motion_passes_its_own_bound(self):
        s = librator(u_max_deg=45.0, days=900.0, sigma_n=SIGMA_N)
        vals, u, _st = gec.implied_s(s.lam, s.drift)
        ok = gec.energy_step_ok(s.epoch_ms / DAY_MS, vals, u, s.drift,
                                SIGMA_N)
        self.assertTrue(bool(np.all(ok)))

    def test_an_asymmetric_velocity_change_breaks_it(self):
        s = librator(u_max_deg=45.0, days=900.0, sigma_n=0.0)
        drift = s.drift.copy()
        k = drift.size // 2
        drift[k:] += 0.05                       # a one-sided change
        vals, u, _st = gec.implied_s(s.lam, drift)
        ok = gec.energy_step_ok(s.epoch_ms / DAY_MS, vals, u, drift, SIGMA_N)
        self.assertFalse(bool(np.all(ok)))

    def test_it_is_blind_to_a_symmetric_reversal_by_construction(self):
        """Registration 3.3, derived in advance and asserted here so the
        blindness is a stated property and not a surprise."""
        lam = np.array([40.0, 40.0])
        v = gpc.free_acceleration(np.array([40.0]))[0] * \
            gec.EW_PERIOD_DAYS / 4.0
        s, _u, _st = gec.implied_s(lam, np.array([v, -v]))
        self.assertAlmostEqual(float(s[0]), float(s[1]), 15)


class DerivedKeeperBlindSpot(unittest.TestCase):

    def test_u_star_matches_its_derivation(self):
        """The registration's FORMULA is the rule; the value it printed
        beside the formula, 7.3468 deg, is a transcription error at the
        fourth significant figure. The exact evaluation is 7.34580 deg, the
        instrument uses the formula, and the discrepancy is reported in the
        results document rather than edited out of the registration."""
        u = gec.u_star_deg(SIGMA_N)
        ratio = (gec.SIGMA_K * SIGMA_N) / (gec.A_DEG_PER_DAY2
                                           * gec.EW_PERIOD_DAYS / 2.0)
        self.assertAlmostEqual(math.sin(math.radians(2 * u)), ratio, 12)
        self.assertAlmostEqual(u, 7.345800, 5)
        self.assertLess(abs(u - 7.3468), 0.0011)

    def test_a_keeper_outside_u_star_is_excluded(self):
        for slot in (_stable_east() + 30.0, _stable_east() + 60.0):
            s = keeper(days=500.0, slot=slot, sigma_n=SIGMA_N)
            eps, _d = gec.find_epochs(s, SIGMA_N)
            self.assertEqual(eps, [], f"keeper at {slot} admitted")


class SampleRules(unittest.TestCase):

    def test_v2_detail_reproduces_the_committed_rule_exactly(self):
        s = librator(u_max_deg=30.0, days=900.0, sigma_n=SIGMA_N)
        det = gec.v2_detail(s.epoch_ms, s.drift, s.lam, SIGMA_N)
        ep, _frac, _n = gpc.v2_flags(s.epoch_ms, s.drift, s.lam, SIGMA_N)
        self.assertEqual(sorted(np.asarray(s.epoch_ms)[det["flagIdx"]]
                                .tolist()), sorted(np.asarray(ep).tolist()))

    def test_a_sample_above_the_separatrix_is_inadmissible(self):
        s = librator(u_max_deg=20.0, days=800.0)
        drift = s.drift.copy()
        drift[:] = 2.0 * gpc.PEAK_RATE_COEFF_DEG_PER_DAY
        bad = _S(700002, s.epoch_ms, s.lam, drift)
        eps, _d = gec.find_epochs(bad, SIGMA_N)
        self.assertEqual(eps, [])

    def test_a_catalogue_gap_breaks_the_run(self):
        s = librator(u_max_deg=20.0, days=1400.0)
        t = s.epoch_ms.copy()
        k = t.size // 2
        t[k:] += 40.0 * DAY_MS                      # a 40-day gap
        gapped = _S(700003, t, s.lam, s.drift)
        eps, _d = gec.find_epochs(gapped, SIGMA_N)
        for e in eps:
            self.assertFalse(e["startMs"] < t[k - 1] < e["endMs"])

    def test_a_cell_change_breaks_the_run(self):
        """An object whose nearest stable longitude changes has left the cell
        and cannot be inside one admitted epoch across the change."""
        s = librator(u_max_deg=20.0, days=800.0)
        lam = s.lam.copy()
        k = lam.size // 2
        lam[k:] = lam[k:] - 180.0                   # the other cell
        moved = _S(700004, s.epoch_ms, pg.wrap180(lam), s.drift)
        eps, _d = gec.find_epochs(moved, SIGMA_N)
        for e in eps:
            self.assertFalse(e["startMs"] < s.epoch_ms[k] < e["endMs"])


class RunRules(unittest.TestCase):

    def test_a_run_shorter_than_the_minimum_is_not_admitted(self):
        s = librator(u_max_deg=20.0, days=50.0)
        eps, diag = gec.find_epochs(s, SIGMA_N)
        self.assertEqual(eps, [])
        self.assertGreaterEqual(diag["rejectedShort"]
                                + diag["rejectedFewSamples"], 1)

    def test_the_minimum_length_is_four_measured_cycles(self):
        self.assertAlmostEqual(gec.MIN_EPOCH_DAYS,
                               4.0 * gec.EW_PERIOD_DAYS, 12)
        self.assertEqual(gec.MIN_EPOCH_SAMPLES, gec.BASELINE_SAMPLES + 2)

    def test_a_cadence_line_rejects_the_whole_run(self):
        """A run carrying the measured line is rejected, not split."""
        s = librator(u_max_deg=3.0, days=600.0)
        drift = s.drift + 1.5e-3 * np.sin(
            2 * math.pi * (s.epoch_ms / DAY_MS) / gec.EW_PERIOD_DAYS)
        lined = _S(700005, s.epoch_ms, s.lam, drift)
        eps, diag = gec.find_epochs(lined, SIGMA_N)
        self.assertEqual(eps, [])
        self.assertGreaterEqual(diag["rejectedCadence"], 1)

    def test_the_sidak_threshold_is_the_registered_family_wise_level(self):
        for n in (1, 4, 11, 131):
            a = gpc.sidak_block_alpha(n)
            self.assertAlmostEqual(1.0 - (1.0 - a) ** n, 0.10, 12)
        self.assertAlmostEqual(gpc.sidak_block_alpha(1), 0.10, 12)


class Stratification(unittest.TestCase):

    def test_a_short_epoch_far_from_the_turning_point_is_quiet(self):
        s = librator(u_max_deg=30.0, days=200.0, phase_deg=0.0)
        eps, _d = gec.find_epochs(s, SIGMA_N)
        self.assertTrue(eps)
        self.assertTrue(all(not e["turnaround"] for e in eps))

    def test_an_epoch_spanning_a_turning_point_is_turn(self):
        s = librator(u_max_deg=30.0, days=500.0, phase_deg=-30.0)
        eps, _d = gec.find_epochs(s, SIGMA_N)
        self.assertTrue(eps)
        self.assertTrue(any(e["turnaround"] for e in eps))

    def test_the_turnaround_probability_bound_is_what_was_registered(self):
        """2 turnarounds per full period; the period is never shorter than
        the small-amplitude value."""
        self.assertGreaterEqual(gpc.libration_period_days(1.0),
                                gec.T0_DAYS - 1e-6)
        self.assertAlmostEqual(2.0 * 60.0 / gec.T0_DAYS, 0.1472, 4)


class Exposure(unittest.TestCase):

    def test_pair_days_count_simultaneous_membership_only(self):
        eps = [{"norad": 1, "startMs": 0.0, "endMs": 10.0 * DAY_MS,
                "days": 10.0},
               {"norad": 2, "startMs": 5.0 * DAY_MS, "endMs": 15.0 * DAY_MS,
                "days": 10.0},
               {"norad": 3, "startMs": 100.0 * DAY_MS,
                "endMs": 110.0 * DAY_MS, "days": 10.0}]
        per_day = gec.epoch_days(eps)
        obj_days, pair_days = gec.exposure_from_days(per_day)
        self.assertEqual(pair_days, 6)          # days 5..10 inclusive
        self.assertEqual(obj_days, 11 + 11 + 11)

    def test_watched_runs_break_at_the_registered_gap(self):
        t = np.array([0.0, 1.0, 2.0, 50.0, 51.0, 52.0]) * DAY_MS
        s = _S(5, t, np.zeros(6), np.zeros(6))
        runs = gec.watched_runs(s)
        self.assertEqual(len(runs), 2)
        self.assertAlmostEqual(runs[0][1] / DAY_MS, 2.0, 9)

    def test_containment_and_overlap_differ(self):
        iv = [(0.0, 10.0)]
        self.assertTrue(gec.contains(iv, 2.0, 8.0))
        self.assertFalse(gec.contains(iv, 2.0, 12.0))
        self.assertTrue(gec.overlaps(iv, 2.0, 12.0))
        self.assertFalse(gec.overlaps(iv, 11.0, 12.0))


class LeakArithmetic(unittest.TestCase):

    def test_a_zero_on_too_little_exposure_is_unevaluable(self):
        r = gec.reading(0, 100, 500, 1_000_000)
        self.assertEqual(r["verdict"], "UNEVALUABLE")
        self.assertAlmostEqual(r["meaningfulZeroExposure"], 2000.0, 6)

    def test_a_zero_on_enough_exposure_is_leak_free(self):
        r = gec.reading(0, 5000, 500, 1_000_000)
        self.assertEqual(r["verdict"], "LEAK-FREE")
        self.assertEqual(r["leakRatio"], 0.0)

    def test_a_rate_above_the_bar_leaks(self):
        r = gec.reading(10, 5000, 500, 1_000_000)
        self.assertEqual(r["verdict"], "LEAKS")
        self.assertGreater(r["leakRatio"], gec.LEAK_BAR)

    def test_the_bar_is_the_one_the_earlier_gate_used(self):
        self.assertEqual(gec.LEAK_BAR, pp.GATE_B_LEAK_RATIO)
        self.assertEqual(gec.LEAK_BAR, 0.10)

    def test_counting_uses_the_registered_anchor(self):
        iv = {7: [(100.0, 200.0)]}
        ev = [{"approacherNorad": 7, "arrivalMs": 150.0,
               "transferStartMs": 50.0, "departureMs": 250.0}]
        self.assertEqual(gec.count_t8a(iv, ev), 1)
        self.assertEqual(gec.count_t8a(iv, ev, anchor="transferStartMs"), 0)
        self.assertEqual(gec.count_t8a(iv, ev, anchor="span"), 0)

    def test_episode_counting_needs_both_members(self):
        iv = {1: [(0.0, 100.0)], 2: [(0.0, 50.0)]}
        eps = [{"a": 1, "b": 2, "startMs": 10.0, "endMs": 40.0},
               {"a": 1, "b": 2, "startMs": 10.0, "endMs": 80.0},
               {"a": 1, "b": 3, "startMs": 10.0, "endMs": 40.0}]
        self.assertEqual(gec.count_t11(iv, eps), 1)
        self.assertEqual(gec.count_t11(iv, eps, rule="overlap"), 2)


class Constants(unittest.TestCase):

    def test_every_constant_is_carried_or_derived(self):
        self.assertEqual(gec.A_DEG_PER_DAY2, pg.LAMBDA_DDOT_MAX)
        self.assertEqual(gec.SIGMA_K, pg.BURN_SIGMA_K)
        self.assertEqual(gec.BASELINE_SAMPLES, pg.BURN_BASELINE_SAMPLES)
        self.assertEqual(gec.MAX_GAP_DAYS, pg.MAX_GAP_DAYS)
        self.assertEqual(gec.BLOCK_DAYS, pp.D_PAIR_PRIMARY_DAYS)
        self.assertEqual(gec.EW_PERIOD_DAYS, pp.T_EAST_WEST_DAYS)
        self.assertAlmostEqual(gec.T0_DAYS, 815.4792, 4)
        self.assertAlmostEqual(gec.TWO_A_RAD, 2.0 * gec.A_DEG_PER_DAY2
                               * math.pi / 180.0, 18)

    def test_the_floor_the_earlier_rule_used_is_not_referenced_here(self):
        src = (_REPO / "tools" / "geo_epoch_control.py").read_text()
        self.assertNotIn("BURN_FLOOR_DEG_PER_DAY", src)


class Vocabulary(unittest.TestCase):

    def test_no_banned_word_in_the_tool_or_this_suite(self):
        for name in ("tools/geo_epoch_control.py",
                     "tests/test_geo_epoch_control.py",
                     "docs/geo-libration-epoch-control-preregistration-"
                     "20260922.md"):
            text = (_REPO / name).read_text()
            self.assertEqual(pp.banned_hits(text), [], name)

    def test_no_catalogue_metadata_enters_a_decision(self):
        src = (_REPO / "tools" / "geo_epoch_control.py").read_text()
        for field in ("objectType", "registry", "launchDate", "country"):
            self.assertNotIn(field, src)


class EpochRecord(unittest.TestCase):

    def test_a_record_carries_no_motive_and_serialises(self):
        s = librator(u_max_deg=25.0, days=700.0, sigma_n=SIGMA_N)
        eps, _d = gec.find_epochs(s, SIGMA_N)
        self.assertTrue(eps)
        for e in eps:
            row = {k: v for k, v in e.items() if k not in ("i0", "i1")}
            json.loads(json.dumps(row, default=pp._json_default))
            self.assertGreaterEqual(e["days"], gec.MIN_EPOCH_DAYS)
            self.assertGreaterEqual(e["elementSets"], gec.MIN_EPOCH_SAMPLES)
            self.assertLessEqual(e["impliedUMaxDeg"], 90.0)
            self.assertIn("turnaround", e)


if __name__ == "__main__":
    unittest.main()
