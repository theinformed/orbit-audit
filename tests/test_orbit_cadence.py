"""Offline tests for the T3 cadence machinery.

No archive, no GPU, no network. The array functions in `tools/cadence_core.py`
take an explicit array module, so these tests exercise the *same* code path the
GPU run executes -- only the module differs. A GPU kernel no test can reach is
a kernel nobody has checked, and this suite exists so that is not the case here.

Every constant asserted below is asserted against
`docs/cadence-preregistration-20260921.md`. If a test here fails after an edit,
the edit has moved a registered quantity, which is the point.
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

from tools import cadence_core as core  # noqa: E402


def irregular_times(count, span_days, seed):
    """Epochs with the archive's flavour of irregularity: a nominal cadence
    jittered enough that no uniform grid describes it."""
    rng = np.random.default_rng(seed)
    step = span_days / count
    times = np.cumsum(rng.uniform(0.25 * step, 1.75 * step, size=count))
    return times * (span_days / times[-1])


def single_window(times, values):
    t = np.asarray(times, dtype=np.float64)[None, :]
    v = np.asarray(values, dtype=np.float64)[None, :]
    m = np.ones_like(t)
    return t, v, m


class RegisteredGrid(unittest.TestCase):
    def test_band_edges_are_the_registered_ones(self):
        grid = core.frequency_grid()
        self.assertAlmostEqual(float(grid[0]), 1.0 / 220.0, places=12)
        self.assertLessEqual(float(grid[-1]), 0.5 + 1e-12)
        self.assertGreater(float(grid[-1]), 0.5 - 1.0 / (core.OVERSAMPLE * core.WINDOW_DAYS))

    def test_resolution_and_count(self):
        grid = core.frequency_grid()
        df = 1.0 / (core.OVERSAMPLE * core.WINDOW_DAYS)
        np.testing.assert_allclose(np.diff(grid), df, rtol=1e-12)
        self.assertEqual(grid.size, 2676)

    def test_highest_frequency_stays_below_the_first_sampling_alias_carrier(self):
        # Derived in the pre-registration section 0.2: the archive's spectral
        # window has its lowest carrier at 1.0 cycles/day. The band must stop
        # strictly below it, or an alias of an out-of-band signal could land
        # inside the searched band.
        self.assertLess(float(core.frequency_grid()[-1]), 1.0)

    def test_cycle_floor_holds(self):
        grid = core.frequency_grid()
        self.assertGreaterEqual(grid[0] * core.WINDOW_DAYS, core.MIN_CYCLES_IN_WINDOW)


class GeneralisedLombScargle(unittest.TestCase):
    def test_recovers_an_injected_period_from_irregular_samples(self):
        grid = core.frequency_grid()
        for period in (7.0, 14.0, 30.0, 64.0, 180.0):
            t = irregular_times(2000, core.WINDOW_DAYS, seed=int(period))
            y = 3.0 + 0.5 * np.sin(2 * math.pi * t / period + 0.7)
            power = core.gls_power(*single_window(t, y), grid, np)
            recovered = 1.0 / grid[int(power.argmax())]
            self.assertLess(abs(recovered - period) / period, 0.02,
                            f"period {period} recovered as {recovered}")

    def test_pure_sinusoid_explains_almost_all_the_variance(self):
        grid = core.frequency_grid()
        t = irregular_times(1500, core.WINDOW_DAYS, seed=11)
        y = 100.0 + 2.0 * np.sin(2 * math.pi * t / 21.0)
        power = core.gls_power(*single_window(t, y), grid, np)
        # Not 1.0: the registered grid is finite, so the true frequency
        # generally falls between two grid points and some power is lost.
        self.assertGreater(float(power.max()), 0.95)

    def test_power_is_bounded_in_the_unit_interval(self):
        grid = core.frequency_grid()
        rng = np.random.default_rng(3)
        t = irregular_times(900, core.WINDOW_DAYS, seed=3)
        y = rng.normal(size=t.size)
        power = core.gls_power(*single_window(t, y), grid, np)
        self.assertGreaterEqual(float(power.min()), 0.0)
        self.assertLessEqual(float(power.max()), 1.0)

    def test_floating_mean_matters(self):
        # A large offset is exactly what a classical (non-generalised)
        # periodogram mishandles. The generalised form must be indifferent to it.
        grid = core.frequency_grid()
        t = irregular_times(800, core.WINDOW_DAYS, seed=5)
        signal = 0.4 * np.sin(2 * math.pi * t / 17.0)
        low = core.gls_power(*single_window(t, signal), grid, np)
        high = core.gls_power(*single_window(t, signal + 5.0e4), grid, np)
        # 1e-4 and not machine precision on purpose: the variance sum
        # sum(w y^2) - mean^2 cancels catastrophically once the offset dwarfs
        # the signal, and at 5e4 against 0.4 that costs about six digits in
        # float64. This is the measured reason `tools/cadence_measure.py`
        # centres and scales each window in float64 BEFORE casting to float32 --
        # mean motion is ~14 rev/day and a station-keeping signal can be 1e-6,
        # which float32 at 14.0 (resolution 1.7e-6) would erase outright.
        np.testing.assert_allclose(low, high, rtol=1e-4, atol=1e-9)

    def test_an_uncentred_float32_window_would_lose_the_signal(self):
        # The bug the centring in cadence_measure exists to prevent, asserted
        # so that removing the centring fails a test rather than quietly
        # returning noise.
        grid = core.frequency_grid()[:600]
        t = irregular_times(1200, core.WINDOW_DAYS, seed=31)
        signal = 1.0e-6 * np.sin(2 * math.pi * t / 27.0)
        naive = (14.0 + signal).astype(np.float32).astype(np.float64) - 14.0
        centred = signal
        naive_power = core.gls_power(*single_window(t, naive), grid, np).max()
        centred_power = core.gls_power(*single_window(t, centred), grid, np).max()
        self.assertGreater(centred_power, 0.9)
        self.assertLess(naive_power, centred_power)

    def test_padding_with_a_mask_changes_nothing(self):
        grid = core.frequency_grid()[:400]
        t = irregular_times(600, core.WINDOW_DAYS, seed=7)
        y = np.sin(2 * math.pi * t / 11.0) + 0.1 * np.cos(2 * math.pi * t / 5.0)
        unpadded = core.gls_power(*single_window(t, y), grid, np)
        pad = 250
        tp = np.zeros((1, t.size + pad))
        yp = np.zeros((1, t.size + pad))
        mp = np.zeros((1, t.size + pad))
        tp[0, :t.size] = t
        yp[0, :t.size] = y
        mp[0, :t.size] = 1.0
        padded = core.gls_power(tp, yp, mp, grid, np)
        np.testing.assert_allclose(unpadded, padded, rtol=1e-8, atol=1e-10)

    def test_batched_rows_are_independent(self):
        grid = core.frequency_grid()[:600]
        rows = []
        for i, period in enumerate((9.0, 33.0, 120.0)):
            t = irregular_times(500, core.WINDOW_DAYS, seed=100 + i)
            rows.append((t, np.sin(2 * math.pi * t / period)))
        width = max(t.size for t, _ in rows)
        T = np.zeros((3, width)); Y = np.zeros((3, width)); M = np.zeros((3, width))
        for i, (t, y) in enumerate(rows):
            T[i, :t.size] = t; Y[i, :t.size] = y; M[i, :t.size] = 1.0
        batched = core.gls_power(T, Y, M, grid, np)
        for i, (t, y) in enumerate(rows):
            alone = core.gls_power(*single_window(t, y), grid, np)
            np.testing.assert_allclose(batched[i], alone[0], rtol=1e-7, atol=1e-9)

    def test_frequency_chunking_does_not_change_the_answer(self):
        grid = core.frequency_grid()[:500]
        t = irregular_times(700, core.WINDOW_DAYS, seed=13)
        y = np.sin(2 * math.pi * t / 23.0)
        a = core.gls_power(*single_window(t, y), grid, np, chunk=7)
        b = core.gls_power(*single_window(t, y), grid, np, chunk=500)
        np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-12)


class PhysicalSignalShapes(unittest.TestCase):
    """The shapes the pre-registration says the instrument must and must not see."""

    @staticmethod
    def station_kept_mean_motion(t, cadence_days, decay_per_day=2.0e-7, step=None):
        """Drag raises mean motion continuously; a burn drops it back.

        n rises as the orbit decays (a falls, n rises), so a reboost is a
        DOWNWARD step in n. The sawtooth is the physical shape section 2.1 of
        the pre-registration describes.
        """
        step = step if step is not None else decay_per_day * cadence_days
        burns = np.floor(t / cadence_days)
        return 14.0 + decay_per_day * t - step * burns

    def test_a_station_keeping_sawtooth_is_recovered_at_its_fundamental(self):
        grid = core.frequency_grid()
        for cadence in (10.0, 21.0, 45.0):
            t = irregular_times(2400, core.WINDOW_DAYS, seed=int(cadence * 7))
            y = self.station_kept_mean_motion(t, cadence)
            T, Y, M = single_window(t, y)
            residual = core.detrend_batch(T, Y, M, np)
            power = core.gls_power(T, residual, M, grid, np)
            recovered = 1.0 / grid[int(power.argmax())]
            self.assertLess(abs(recovered - cadence) / cadence, 0.03,
                            f"cadence {cadence} recovered as {recovered}")
            self.assertGreater(float(power.max()), 0.5)

    def test_pure_drag_decay_without_burns_leaves_little_in_band_power(self):
        # The passive class's defining shape. After the registered cubic
        # detrend a smooth decay must not masquerade as a rhythm.
        grid = core.frequency_grid()
        t = irregular_times(2400, core.WINDOW_DAYS, seed=404)
        y = 14.0 + 2.0e-7 * t + 3.0e-11 * t ** 2
        T, Y, M = single_window(t, y)
        residual = core.detrend_batch(T, Y, M, np)
        power = core.gls_power(T, residual, M, grid, np)
        self.assertLess(float(power.max()), 0.2)

    def test_continuous_low_thrust_is_invisible_as_registered(self):
        # Pre-registration section 9.1 declares this blind spot. The test
        # asserts the blind spot is real, so that a later change which
        # accidentally made a ramp look periodic would be caught.
        grid = core.frequency_grid()
        t = irregular_times(2400, core.WINDOW_DAYS, seed=909)
        y = 14.0 - 5.0e-7 * t            # a steady raise, no discontinuity
        T, Y, M = single_window(t, y)
        residual = core.detrend_batch(T, Y, M, np)
        power = core.gls_power(T, residual, M, grid, np)
        self.assertLess(float(power.max()), 0.1)


class Detrending(unittest.TestCase):
    def test_a_cubic_is_removed_exactly(self):
        t = irregular_times(500, core.WINDOW_DAYS, seed=21)
        y = 3.0 - 2e-4 * t + 5e-7 * t ** 2 - 1e-10 * t ** 3
        T, Y, M = single_window(t, y)
        residual = core.detrend_batch(T, Y, M, np)
        self.assertLess(float(np.abs(residual).max()), 1e-9 * max(1.0, float(np.abs(y).max())))

    def test_an_in_band_sinusoid_survives_the_detrend(self):
        t = irregular_times(2000, core.WINDOW_DAYS, seed=22)
        signal = 1e-6 * np.sin(2 * math.pi * t / 30.0)
        y = 14.0 + 2e-7 * t + signal
        T, Y, M = single_window(t, y)
        residual = core.detrend_batch(T, Y, M, np)[0]
        kept = np.std(residual) / np.std(signal)
        self.assertGreater(kept, 0.95)
        self.assertLess(kept, 1.05)

    def test_the_masked_tail_is_ignored_by_the_fit(self):
        t = irregular_times(400, core.WINDOW_DAYS, seed=23)
        y = 2.0 + 1e-4 * t
        T = np.zeros((1, 600)); Y = np.zeros((1, 600)); M = np.zeros((1, 600))
        T[0, :400] = t; Y[0, :400] = y; M[0, :400] = 1.0
        Y[0, 400:] = 1e9          # garbage behind the mask
        residual = core.detrend_batch(T, Y, M, np)
        self.assertLess(float(np.abs(residual[0, :400]).max()), 1e-8)
        np.testing.assert_array_equal(residual[0, 400:], 0.0)


class Windows(unittest.TestCase):
    def test_tiling_uses_the_registered_length_and_step(self):
        first = 0
        last = int(5000 * core.DAY_MS)
        bounds = core.window_bounds(first, last)
        self.assertEqual(bounds[0], (0.0, core.WINDOW_DAYS))
        self.assertAlmostEqual(bounds[1][0] - bounds[0][0], core.STEP_DAYS)
        for _start, end in bounds:
            self.assertLessEqual(end, 5000.0 + 1e-6)

    def test_no_window_is_emitted_for_a_short_history(self):
        self.assertEqual(core.window_bounds(0, int(500 * core.DAY_MS)), [])

    def test_each_admissibility_reason_can_fire(self):
        good_t = np.linspace(0.0, 1000.0, 1200)
        good_v = np.linspace(14.0, 14.001, 1200)
        self.assertEqual(core.window_admissible(good_t, good_v), (True, ""))
        self.assertEqual(core.window_admissible(good_t[:100], good_v[:100])[1], "samples")
        gap_t = np.concatenate([np.linspace(0, 400, 700), np.linspace(500, 1000, 700)])
        self.assertEqual(core.window_admissible(gap_t, np.linspace(14, 14.001, 1400))[1], "gap")
        short_t = np.linspace(0.0, 800.0, 1200)
        self.assertEqual(core.window_admissible(short_t, good_v)[1], "span")
        self.assertEqual(core.window_admissible(good_t, np.full(1200, 14.0))[1], "constant")

    def test_the_gap_bound_is_a_multiple_of_the_repository_gap_constant(self):
        from pipeline.orbit_campaigns import MAXIMUM_JOINABLE_GAP_DAYS
        self.assertEqual(core.WINDOW_MAX_GAP_DAYS, 15.0 * MAXIMUM_JOINABLE_GAP_DAYS)


class Split(unittest.TestCase):
    def test_is_deterministic_and_by_object(self):
        self.assertEqual(core.split_half(25544), core.split_half(25544))
        self.assertIn(core.split_half(25544), ("calibration", "audit"))

    def test_is_close_to_balanced_over_the_catalogue_range(self):
        halves = [core.split_half(n) for n in range(1, 40001)]
        share = halves.count("calibration") / len(halves)
        self.assertGreater(share, 0.49)
        self.assertLess(share, 0.51)

    def test_depends_on_the_registered_salt(self):
        import hashlib
        digest = hashlib.sha256(f"{core.SPLIT_SALT}:25544".encode()).hexdigest()
        expected = "calibration" if int(digest[:8], 16) % 2 == 0 else "audit"
        self.assertEqual(core.split_half(25544), expected)
        self.assertEqual(core.SPLIT_SALT, "t3-20260921")


class MultipleTesting(unittest.TestCase):
    def test_benjamini_hochberg_step_up(self):
        # Benjamini & Hochberg 1995, the worked example of their section 4
        # (m = 15, q = 0.05): the procedure rejects the first four.
        p = np.array([0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298,
                      0.0344, 0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000])
        reject = core.benjamini_hochberg(p, q=0.05)
        self.assertEqual(int(reject.sum()), 4)
        self.assertTrue(reject[:4].all())
        self.assertFalse(reject[4:].any())

    def test_step_up_rejects_past_a_gap(self):
        # The defining difference from a naive per-hypothesis cut: a p-value
        # above its own threshold is still rejected when a LATER one passes.
        p = np.array([0.001, 0.04, 0.009])
        reject = core.benjamini_hochberg(p, q=0.05)
        self.assertEqual(int(reject.sum()), 3)

    def test_rejects_nothing_when_nothing_is_small(self):
        self.assertEqual(int(core.benjamini_hochberg(np.full(100, 0.5)).sum()), 0)

    def test_empty_input(self):
        self.assertEqual(core.benjamini_hochberg([]).size, 0)

    def test_controls_the_false_discovery_rate_under_the_global_null(self):
        rng = np.random.default_rng(core.SEED)
        discoveries = 0
        trials = 200
        for _ in range(trials):
            discoveries += int(core.benjamini_hochberg(rng.uniform(size=500), q=0.05).sum() > 0)
        self.assertLess(discoveries / trials, 0.12)

    def test_empirical_pvalue_floor_and_direction(self):
        reference = np.arange(100, dtype=float)
        self.assertAlmostEqual(core.empirical_pvalue(1e9, reference), 1.0 / 101.0)
        self.assertAlmostEqual(core.empirical_pvalue(-1e9, reference), 101.0 / 101.0)
        self.assertGreater(core.empirical_pvalue(50.0, reference),
                           core.empirical_pvalue(90.0, reference))


class BandsAndConversions(unittest.TestCase):
    def test_sample_count_bands(self):
        self.assertEqual(core.n_band(300), "300-600")
        self.assertEqual(core.n_band(599), "300-600")
        self.assertEqual(core.n_band(600), "600-1200")
        self.assertEqual(core.n_band(50000), ">=4800")

    def test_window_count_bands(self):
        self.assertEqual(core.window_count_band(2), "2-3")
        self.assertEqual(core.window_count_band(3), "2-3")
        self.assertEqual(core.window_count_band(4), "4-7")
        self.assertEqual(core.window_count_band(99), ">=16")

    def test_geostationary_mean_motion_gives_the_geostationary_radius(self):
        # One sidereal day per revolution: 86164.0905 s.
        a = core.semi_major_axis_km(86400.0 / 86164.0905)
        self.assertLess(abs(a - 42164.17), 0.2)

    def test_perigee_of_a_circular_low_orbit(self):
        # 500 km circular: a = 6878.137 km, so n follows from Kepler.
        n = math.sqrt(core.MU_KM3_S2 / 6878.137 ** 3) * 86400.0 / (2 * math.pi)
        self.assertLess(abs(core.perigee_km(n, 0.0) - 500.0), 0.01)

    def test_borrowed_constants_have_not_drifted(self):
        from pipeline.orbit_campaigns import REPEAT_RELATIVE_TOLERANCE
        from pipeline.orbit_events import MIN_SEPARATION_BOUND_RATIO, PASSIVE_TYPES
        self.assertEqual(core.SHIFT_TOLERANCE, REPEAT_RELATIVE_TOLERANCE)
        self.assertEqual(core.GATE_B_INFORMATIVE, MIN_SEPARATION_BOUND_RATIO)
        self.assertEqual(tuple(core.PASSIVE_TYPES), tuple(PASSIVE_TYPES))
        self.assertEqual(core.SEED, 20260921)

    def test_stratum_key_is_paper_bs(self):
        from tools import paperb_strata
        self.assertIs(core.stratum_key, paperb_strata.stratum_key)


class Changepoints(unittest.TestCase):
    def test_the_shift_tolerance_is_a_relative_period_difference(self):
        # 10 d against 14 d is a shift at the registered 0.35 tolerance;
        # 10 d against 13 d is not. Stated as a test so the direction of the
        # comparison cannot be quietly inverted later.
        def shifted(a, b):
            return abs(a - b) / min(a, b) > core.SHIFT_TOLERANCE
        self.assertTrue(shifted(10.0, 14.0))
        self.assertFalse(shifted(10.0, 13.0))


class Analysis(unittest.TestCase):
    """The decision rules in `tools/cadence_analyze.py`, exercised on fixtures."""

    def setUp(self):
        from tools import cadence_analyze
        self.an = cadence_analyze

    def _row(self, sig, periods, indices=None):
        indices = list(range(len(sig))) if indices is None else indices
        return {"windowSignificant": list(sig), "windowPeriodsDays": list(periods),
                "windowIndices": list(indices)}

    def test_a_steady_rhythm_produces_no_changepoint(self):
        row = self._row([True] * 6, [14.0] * 6)
        shifts, stops = self.an._changepoints(row)
        self.assertEqual(shifts, [])
        self.assertEqual(stops, [])

    def test_a_rhythm_that_shifts_is_found(self):
        row = self._row([True] * 6, [10.0, 10.0, 10.0, 30.0, 30.0, 30.0])
        shifts, _ = self.an._changepoints(row)
        # The registered rule flags every boundary whose straddling medians
        # differ, so ONE transition in a six-window object is declared at three
        # consecutive boundaries. That is what the registration says, so it is
        # what is reported -- and `episodes` merges them for the reader.
        self.assertEqual(len(shifts), 3)
        self.assertEqual(self.an.episodes(shifts), 1)
        self.assertAlmostEqual(shifts[1]["periodBeforeDays"], 10.0)
        self.assertAlmostEqual(shifts[1]["periodAfterDays"], 30.0)

    def test_two_separated_transitions_are_two_episodes(self):
        periods = [10.0] * 3 + [30.0] * 4 + [10.0] * 3
        row = self._row([True] * 10, periods)
        shifts, _ = self.an._changepoints(row)
        self.assertEqual(self.an.episodes(shifts), 2)

    def test_no_shift_means_no_episode(self):
        self.assertEqual(self.an.episodes([]), 0)

    def test_a_shift_inside_the_tolerance_is_not_a_shift(self):
        row = self._row([True] * 6, [10.0, 10.0, 10.0, 13.0, 13.0, 13.0])
        shifts, _ = self.an._changepoints(row)
        self.assertEqual(shifts, [])

    def test_a_rhythm_that_stops_is_found(self):
        row = self._row([True, True, True, False, False, False], [21.0] * 6)
        _, stops = self.an._changepoints(row)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(stops[0]["periodBeforeDays"], 21.0)

    def test_a_gap_in_the_windows_cannot_be_read_as_a_stop(self):
        # Windows 3 and 4 were INADMISSIBLE, so they are absent from the index.
        # Pre-registration 7.2: leaving the archive is not stopping station-
        # keeping, and the "after" side must be usable for a stop to count.
        row = self._row([True, True, False, False],
                        [21.0, 21.0, 90.0, 90.0], indices=[0, 1, 5, 6])
        shifts, stops = self.an._changepoints(row)
        self.assertEqual(stops, [])
        self.assertEqual(shifts, [])

    def test_too_few_windows_yields_nothing(self):
        row = self._row([True, True, False], [21.0, 21.0, 90.0])
        self.assertEqual(self.an._changepoints(row), ([], []))

    def test_harmonic_flag(self):
        # f* at twice a comparably strong peak: ambiguous.
        self.assertTrue(self.an._harmonic_flag(0.10, 0.05, 0.8))
        # comparable peak at an unrelated frequency: not a harmonic.
        self.assertFalse(self.an._harmonic_flag(0.10, 0.037, 0.8))
        # a harmonic relationship but a negligible second peak: not ambiguous.
        self.assertFalse(self.an._harmonic_flag(0.10, 0.05, 0.1))

    def test_regime_labels(self):
        self.assertEqual(self.an.regime(550.0, 0.0005, 53.0), "LEO")
        self.assertEqual(self.an.regime(35786.0, 0.0002, 0.05), "GEO")
        self.assertEqual(self.an.regime(35786.0, 0.0002, 60.0), "GEO-inclined")
        self.assertEqual(self.an.regime(300.0, 0.72, 27.0), "LEO")
        self.assertEqual(self.an.regime(20000.0, 0.001, 55.0), "MEO")
        self.assertEqual(self.an.regime(5000.0, 0.6, 7.0), "GTO/HEO")

    def test_operator_family_is_prefix_matched_and_admits_ignorance(self):
        self.assertEqual(self.an.operator_family("STARLINK-3005"), "Starlink (SpaceX)")
        self.assertEqual(self.an.operator_family("COSMOS 2251"), "Cosmos (Russian)")
        self.assertEqual(self.an.operator_family("SOMETHING ELSE"), "unclassified")
        self.assertEqual(self.an.operator_family(""), "unclassified")

    def test_fallback_ladder_keys_drop_the_registered_factors_in_order(self):
        data = {"perigeeKm": np.array([550.0]), "inclinationDeg": np.array([53.0]),
                "eccentricity": np.array([0.0004]), "medianSpacingDays": np.array([0.4]),
                "n": np.array([2700])}
        full, drop_e, drop_i, drop_p = self.an.cell_keys(data)
        self.assertEqual(full[0].count("|"), 4)
        self.assertEqual(drop_e[0].count("|"), 3)
        self.assertEqual(drop_i[0].count("|"), 2)
        self.assertEqual(drop_p[0].count("|"), 1)
        self.assertTrue(full[0].endswith("|2400-4800"))
        self.assertNotIn("<0.001", drop_e[0])

    def test_a_cell_below_the_minimum_is_not_given_a_threshold(self):
        keys = np.array(["a"] * (core.MIN_CELL_WINDOWS) + ["b"] * (core.MIN_CELL_WINDOWS - 1))
        values = np.arange(keys.size, dtype=float)
        table, sizes = self.an.percentile_table(keys, values, core.MIN_CELL_WINDOWS, 99.0)
        self.assertIn("a", table)
        self.assertNotIn("b", table)
        self.assertEqual(sizes["b"], core.MIN_CELL_WINDOWS - 1)


if __name__ == "__main__":
    unittest.main()
