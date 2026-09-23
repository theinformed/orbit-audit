#!/usr/bin/env python3
"""Offline proofs for T21's differential detector.

Registered in `docs/t21-differential-preregistration-20260923.md` section 8.2
before this file existed. The first three assert the BUG each is meant to
catch, not merely the happy path: a common-mode error that fails to cancel, a
real step that fails to survive, and a sign convention that names the wrong
spacecraft.
"""

import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_names  # noqa: E402  the names, kept out of this file

import differential_detect as dd                                  # noqa: E402
import proximity_plane as pp                                      # noqa: E402
from tools import persistent_pairs as ppair                       # noqa: E402

DAY_MS = 86400000.0


def _smooth_common(rng, n_samples, smooth_samples):
    """A common-mode series that is SMOOTH on the scale of the epoch offset.

    This matters and is not a convenience: the common term cancels only to
    the extent it can be interpolated from the partner's bracketing epochs.
    A common mode whose correlation time is shorter than the epoch offset
    survives differencing -- `TestCommonModeSmoothness` asserts exactly that,
    and it is the reason a fit-to-fit error and a density error behave
    differently under this instrument.
    """
    walk = np.cumsum(rng.normal(0.0, 1.0, n_samples + 4 * smooth_samples))
    kernel = np.ones(smooth_samples) / smooth_samples
    for _ in range(3):
        walk = np.convolve(walk, kernel, mode="same")
    out = walk[2 * smooth_samples:2 * smooth_samples + n_samples]
    return out - out.mean()


def synthetic_pair(n_samples=400, common_scale=3e-6, indep_scale=1e-6,
                   seed=11, spacing_days=0.5, offset_days=0.17,
                   smooth_samples=20):
    """Two co-orbital series sharing one error term and carrying independent
    fit noise each. Epochs differ, exactly as two real objects' do."""
    rng = np.random.default_rng(seed)
    t0 = 1.5e12
    ta = t0 + np.arange(n_samples) * spacing_days * DAY_MS
    tb = t0 + offset_days * DAY_MS + np.arange(n_samples) * spacing_days * DAY_MS
    base = 14.3
    common = _smooth_common(rng, n_samples, smooth_samples)
    scale = dd.series_sigma(common)
    common = common * (common_scale / scale) if scale > 0 else common
    common_b = np.interp(tb, ta, common)
    na = base + common + rng.normal(0.0, indep_scale, n_samples)
    nb = base + common_b + rng.normal(0.0, indep_scale, n_samples)
    a = {"norad": 1, "epoch_ms": ta.astype(np.int64), "n": na,
         "e": np.full(n_samples, 1e-4), "inc": np.full(n_samples, 98.6),
         "raan": np.linspace(0.0, 100.0, n_samples) % 360.0,
         "argp": np.full(n_samples, 90.0), "ma": np.linspace(0, 3600, n_samples) % 360.0}
    b = dict(a)
    b = {"norad": 2, "epoch_ms": tb.astype(np.int64), "n": nb,
         "e": a["e"].copy(), "inc": a["inc"].copy(), "raan": a["raan"].copy(),
         "argp": a["argp"].copy(), "ma": a["ma"].copy()}
    return a, b


class TestCommonModeCancels(unittest.TestCase):
    """T1 (registration 8.2). A common-mode error must cancel in the
    differential and must NOT cancel in either single series."""

    def test_common_mode_cancels(self):
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        sa = dd.series_sigma(a["n"])
        sb = dd.series_sigma(b["n"])
        _, d, ok = dd.build_differential(a, b, "n")
        sd = dd.series_sigma(np.where(ok, d, np.nan))
        self.assertTrue(ok.sum() > 0.9 * ok.size)
        # the differential is strictly quieter than either single series
        self.assertLess(sd, 0.6 * sa)
        self.assertLess(sd, 0.6 * sb)

    def test_the_ratio_matches_its_derivation(self):
        """R = sqrt(2(1-rho)) is the whole hypothesis; it must hold on data
        built to the model.

        The model of registration 2.1 is written about RESIDUALS, so the
        quantity it predicts is the difference of the two objects' residuals.
        The rolling Theil-Sen residual is a median-based, non-linear filter,
        so the residual OF the differential is not the difference OF the
        residuals; it is the series the detector actually consumes, it is
        quieter still, and it is asserted separately below.
        """
        for scale in (3e-7, 1e-6, 4e-6):
            a, b = synthetic_pair(common_scale=scale, indep_scale=5e-7)
            ra = dd.series_residual(a["epoch_ms"], a["n"])
            rb = dd.interpolate_refusing_gaps(
                b["epoch_ms"], dd.series_residual(b["epoch_ms"], b["n"]),
                a["epoch_ms"])
            m = np.isfinite(rb)
            m[:20] = False
            rho = float(np.corrcoef(ra[m], rb[m])[0, 1])
            measured = dd.mad_scale((ra - rb)[m]) / dd.mad_scale(ra[m])
            derived = math.sqrt(2.0 * (1.0 - rho))
            self.assertGreater(rho, 0.5)
            self.assertLess(abs(measured / derived - 1.0), 0.15,
                            f"scale {scale}: {measured} vs {derived}")

    def test_the_detector_series_is_no_worse_than_the_model_predicts(self):
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        ra = dd.series_residual(a["epoch_ms"], a["n"])
        rb = dd.interpolate_refusing_gaps(
            b["epoch_ms"], dd.series_residual(b["epoch_ms"], b["n"]), a["epoch_ms"])
        _, d, ok = dd.build_differential(a, b, "n")
        rd = dd.series_residual(a["epoch_ms"], np.where(ok, d, np.nan))
        m = ok & np.isfinite(rb)
        m[:20] = False
        model = dd.mad_scale((ra - rb)[m]) / dd.mad_scale(ra[m])
        operational = dd.mad_scale(rd[m]) / dd.mad_scale(ra[m])
        self.assertLessEqual(operational, model * 1.05)

    def test_no_common_mode_makes_it_worse(self):
        """The derivation's other half: with rho = 0 the differential is
        sqrt(2) WORSE. A test that only ever saw the favourable case would
        not catch a differential that silently halves its own noise."""
        rng = np.random.default_rng(7)
        a, b = synthetic_pair(common_scale=0.0, indep_scale=1e-6)
        a["n"] = 14.3 + rng.normal(0.0, 1e-6, a["n"].size)
        b["n"] = 14.3 + rng.normal(0.0, 1e-6, b["n"].size)
        sa = dd.series_sigma(a["n"])
        _, d, ok = dd.build_differential(a, b, "n")
        sd = dd.series_sigma(np.where(ok, d, np.nan))
        self.assertGreater(sd / sa, 1.05)


class TestCommonModeSmoothness(unittest.TestCase):
    """A limit of the method, found while building the T1 fixture and asserted
    rather than left implicit: the common term cancels only if it is smooth on
    the scale of the two objects' epoch offset. A common mode as rough as the
    sampling survives differencing, because the partner's value at the host's
    epoch has to be interpolated."""

    def test_a_rough_common_mode_does_not_cancel(self):
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7,
                              smooth_samples=1)
        sa = dd.series_sigma(a["n"])
        _, d, ok = dd.build_differential(a, b, "n")
        sd = dd.series_sigma(np.where(ok, d, np.nan))
        self.assertGreater(sd, 0.6 * sa)

    def test_a_smooth_common_mode_does_cancel(self):
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7,
                              smooth_samples=40)
        sa = dd.series_sigma(a["n"])
        _, d, ok = dd.build_differential(a, b, "n")
        sd = dd.series_sigma(np.where(ok, d, np.nan))
        self.assertLess(sd, 0.2 * sa)


class TestIndependentStepSurvives(unittest.TestCase):
    """T2 (registration 8.2). A step injected into ONE series must survive in
    the differential, at the same epoch and with the registered sign."""

    def test_step_survives_and_is_flagged(self):
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        k = 250
        step = -2.0e-4                      # a raises its semi-major axis
        a["n"] = a["n"].copy()
        a["n"][k:] += step
        _, d, ok = dd.build_differential(a, b, "n")
        sd = dd.series_sigma(np.where(ok, d, np.nan))
        flags, res = dd.swept_flags(a["epoch_ms"], np.where(ok, d, np.nan), sd, 5.0, ok)
        self.assertTrue(flags.size >= 1)
        near = np.abs(flags.astype(np.float64) - float(a["epoch_ms"][k]))
        self.assertLess(near.min() / DAY_MS, 3.0)
        j = int(np.argmin(near))
        idx = int(np.searchsorted(a["epoch_ms"], flags[j]))
        self.assertLess(res[idx], 0.0)      # A raised a -> D steps negative

    def test_a_simultaneous_step_is_attenuated_but_leaks(self):
        """A step applied to BOTH objects at the same instant is common mode,
        but the two objects' epochs differ, so the partner's step arrives in
        the differential smeared across one bracket instead of cancelling.
        The differential response is ATTENUATED, not zero, and the honest
        assertion is the attenuation factor. A test that demanded zero would
        be asserting something the epoch offset makes false."""
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        k = 250
        a["n"] = a["n"].copy(); b["n"] = b["n"].copy()
        a["n"][k:] += -2.0e-4
        b["n"][k:] += -2.0e-4
        _, d, ok = dd.build_differential(a, b, "n")
        rd = dd.series_residual(a["epoch_ms"], np.where(ok, d, np.nan))
        ra = dd.series_residual(a["epoch_ms"], a["n"])
        peak_single = float(np.abs(ra[k:k + 4]).max())
        peak_diff = float(np.abs(rd[k:k + 4]).max())
        self.assertGreater(peak_single / peak_diff, 2.5)

    def test_a_one_sided_step_is_not_attenuated(self):
        """The companion: a step on ONE object must come through the
        differential at close to full size, or the instrument is deaf. The
        measured through-put on this fixture is about 0.78 of the single
        series' own residual peak, so the bar is 0.7 and the shortfall is
        the local fit adapting to a series that carries two objects' noise."""
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        k = 250
        a["n"] = a["n"].copy()
        a["n"][k:] += -2.0e-4
        _, d, ok = dd.build_differential(a, b, "n")
        rd = dd.series_residual(a["epoch_ms"], np.where(ok, d, np.nan))
        ra = dd.series_residual(a["epoch_ms"], a["n"])
        peak_single = float(np.abs(ra[k:k + 4]).max())
        peak_diff = float(np.abs(rd[k:k + 4]).max())
        self.assertGreater(peak_diff / peak_single, 0.7)


class TestSignRule(unittest.TestCase):
    """T3 (registration 3.9, 8.2)."""

    def test_opposite_signs(self):
        a0, b0 = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        k = 250
        step = -2.0e-4
        a = dict(a0); a["n"] = a0["n"].copy(); a["n"][k:] += step
        _, da, oka = dd.build_differential(a, b0, "n")
        ra = dd.series_residual(a["epoch_ms"], np.where(oka, da, np.nan))

        b = dict(b0); b["n"] = b0["n"].copy(); b["n"][k:] += step
        _, db, okb = dd.build_differential(a0, b, "n")
        rb = dd.series_residual(a0["epoch_ms"], np.where(okb, db, np.nan))

        self.assertLess(ra[k + 1], 0.0)
        self.assertGreater(rb[k + 1], 0.0)


class TestGapRefusal(unittest.TestCase):
    """T4 (registration 3.2, 8.2)."""

    def test_gap_is_refused_not_dropped(self):
        t = np.asarray([0.0, 1.0, 9.0, 10.0]) * DAY_MS
        y = np.asarray([1.0, 2.0, 3.0, 4.0])
        q = np.asarray([0.5, 5.0, 9.5]) * DAY_MS
        out = dd.interpolate_refusing_gaps(t, y, q, max_gap_days=5.0)
        self.assertEqual(out.size, q.size)
        self.assertTrue(np.isfinite(out[0]))
        self.assertTrue(np.isnan(out[1]))       # inside the 8-day gap
        self.assertTrue(np.isfinite(out[2]))

    def test_hold_one_out_marks_the_gap(self):
        t = np.asarray([0.0, 1.0, 9.0, 10.0, 11.0]) * DAY_MS
        y = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0])
        err = dd.hold_one_out_error(t, y, max_gap_days=5.0)
        self.assertEqual(err.size, 3)
        self.assertTrue(np.isnan(err[0]))
        self.assertTrue(np.isnan(err[1]))
        self.assertTrue(np.isfinite(err[2]))


class TestDetectorShape(unittest.TestCase):
    """T5 (registration 3.4, 8.2): the reimplemented confirmation rule
    reproduces the shipped in-track channel EXACTLY on a single object when
    given the same threshold."""

    def test_matches_the_shipped_detector(self):
        rng = np.random.default_rng(3)
        n_s = 600
        t = 1.5e12 + np.arange(n_s) * 0.5 * DAY_MS
        n = 14.3 - np.arange(n_s) * 2e-7 + rng.normal(0.0, 8e-7, n_s)
        n[300:] += -3.0e-4
        el = {"epoch_ms": t.astype(np.int64), "n": n,
              "e": np.full(n_s, 1e-4), "inc": np.full(n_s, 98.6),
              "raan": np.linspace(0, 200, n_s) % 360.0}
        sigma_n = 1.0e-5
        shipped = pp.detect_manoeuvres(el, sigma_n, 1.0)["intrack"]

        # the shipped threshold, rebuilt from its three published terms
        t_days = t / DAY_MS
        res = pp.rolling_theil_sen_residual(t_days, n)
        a = pp.semi_major_axis_km(n)
        dtv = np.diff(t_days)
        inst = np.diff(n) / dtv
        sm = pp.sliding_median(inst, pp.BURN_BASELINE_SAMPLES)
        ndot = np.nan_to_num(np.concatenate((sm, [sm[-1]]))[:n_s], nan=0.0)
        spacing = np.empty(n_s); spacing[1:] = np.maximum(dtv, 1e-6); spacing[0] = spacing[1]
        thr = np.maximum(np.maximum(pp.BURN_SIGMA_K * sigma_n,
                                    3.0 * np.abs(ndot) * spacing),
                         1.5 * n * pp.DA_FLOOR_KM / a)
        mine = dd.confirmed_indices(res, thr)
        self.assertTrue(shipped.size > 0)
        np.testing.assert_array_equal(mine, shipped)


class TestFloorDerivation(unittest.TestCase):
    """T6 (registration 2.3, 8.2): the derivation reproduces T16b's published
    102.2-126.0 m and 54.0-58.7 mm/s from its published pooled sigma."""

    def test_reproduces_t16b(self):
        thr = pp.BURN_SIGMA_K * 6.2747e-5
        for n_rev, da_pub, dv_pub in ((14.524, 102.2, 54.0), (12.8, 126.0, 58.7)):
            a_km = float(pp.semi_major_axis_km(n_rev))
            da_m, dv_mps = dd.floor_metres(a_km, n_rev, thr)
            self.assertLess(abs(da_m / da_pub - 1.0), 0.005,
                            f"{n_rev}: {da_m} vs {da_pub}")
            self.assertLess(abs(dv_mps * 1000.0 / dv_pub - 1.0), 0.005,
                            f"{n_rev}: {dv_mps * 1000.0} vs {dv_pub}")

    def test_the_floor_is_linear_in_the_threshold(self):
        a_km = float(pp.semi_major_axis_km(14.3))
        one = dd.floor_metres(a_km, 14.3, 1e-5)[0]
        two = dd.floor_metres(a_km, 14.3, 2e-5)[0]
        self.assertAlmostEqual(two / one, 2.0, places=9)


class TestVocabulary(unittest.TestCase):
    """T7 (registration 8.2). The programme's own word-boundary ban."""

    def test_instrument_is_clean(self):
        hits = ppair.banned_hits(Path(dd.__file__).read_text())
        self.assertEqual(hits, [], f"banned vocabulary in the instrument: {hits}")

    def test_registration_and_results_are_clean(self):
        for name in ("t21-differential-preregistration-20260923.md",
                     "t21-differential-results-20260923.md",
                     "t21-differential-results-20260923.json"):
            path = _REPO / "docs" / name
            if not path.exists():
                continue
            hits = ppair.banned_hits(path.read_text())
            self.assertEqual(hits, [], f"banned vocabulary in {name}: {hits}")

    def test_no_tool_or_vendor_names(self):
        text = Path(dd.__file__).read_text().lower()
        self.assertEqual(vendor_names.hits(text), [],
                         "a vendor string is in the instrument")


class TestShuffledControl(unittest.TestCase):
    """T8 (registration 3.8, 8.2): the shuffled arm really is shuffled."""

    def test_shift_moves_every_epoch(self):
        a, b = synthetic_pair()
        s = dd.shifted_copy(b, 180.0)
        self.assertEqual(s["epoch_ms"].size, b["epoch_ms"].size)
        self.assertTrue(np.all(s["epoch_ms"] != b["epoch_ms"]))
        self.assertAlmostEqual(
            float(np.median(s["epoch_ms"] - b["epoch_ms"])) / DAY_MS, 180.0, places=6)

    def test_permutation_changes_the_order(self):
        a, b = synthetic_pair()
        p = dd.permuted_copy(b)
        self.assertEqual(p["n"].size, b["n"].size)
        self.assertGreater(float(np.mean(p["n"] != b["n"])), 0.9)
        np.testing.assert_allclose(np.sort(p["n"]), np.sort(b["n"]))

    def test_shuffling_destroys_the_common_mode(self):
        a, b = synthetic_pair(common_scale=4e-6, indep_scale=5e-7)
        _, d_true, ok_t = dd.build_differential(a, b, "n")
        _, d_sh, ok_s = dd.build_differential(a, dd.shifted_copy(b, 180.0), "n")
        s_true = dd.series_sigma(np.where(ok_t, d_true, np.nan))
        s_sh = dd.series_sigma(np.where(ok_s, d_sh, np.nan))
        self.assertGreater(s_sh, 2.0 * s_true)


class TestWindowArithmetic(unittest.TestCase):
    def test_intersection_and_days(self):
        wa = [(0.0, 10 * DAY_MS), (20 * DAY_MS, 30 * DAY_MS)]
        wb = [(5 * DAY_MS, 25 * DAY_MS)]
        inter = dd.intersect_windows(wa, wb)
        self.assertEqual(len(inter), 2)
        self.assertAlmostEqual(dd.window_days(inter), 10.0, places=9)

    def test_in_any_window(self):
        w = [(0.0, DAY_MS)]
        m = dd.in_any_window(np.asarray([0.5 * DAY_MS, 2 * DAY_MS]), w)
        self.assertTrue(m[0])
        self.assertFalse(m[1])


if __name__ == "__main__":
    unittest.main()
