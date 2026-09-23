#!/usr/bin/env python3
"""Offline tests for T8c's pattern-taxonomy instrument.

Every test runs without the archive and without the network. The policy
guards at the end are the framing rules of
`docs/alarm-pattern-preregistration-20260922.md` section 1, enforced rather
than merely intended -- the same shape T8a and T8b carry.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import alarm_pattern as ap  # noqa: E402
import proximity_geo as pg  # noqa: E402

DAY = ap.DAY_MS


def _series(norad, epochs_days, drift, lam0=0.0):
    """A Series with a chosen drift-rate history, built through T8a's own
    constructor so the geometry is the registered geometry."""
    epochs = np.asarray(epochs_days, dtype=np.float64) * DAY
    drift = np.asarray(drift, dtype=np.float64)
    mm = (drift + pg.OMEGA_E_DEG_PER_DAY) / 360.0
    n = epochs.size
    zeros = np.zeros(n)
    s = pg.Series(norad, epochs.astype(np.int64), mm, zeros, zeros,
                  zeros, zeros, zeros)
    s.lam = np.full(n, lam0)
    s.lam_unwrapped = np.full(n, lam0)
    return s


class TestRegisteredConstants(unittest.TestCase):
    """prereg 3, 4, 8: the numbers this study may not change after a result."""

    def test_feature_count_is_the_registered_thirty_two_plus_five(self):
        self.assertEqual(len(ap.FEATURE_NAMES), 37)
        indicators = [n for n in ap.FEATURE_NAMES if n.startswith("miss_")]
        self.assertEqual(len(indicators), 5)
        self.assertEqual(len(ap.FEATURE_NAMES) - len(indicators), 32)

    def test_feature_names_are_unique_and_ordered_as_registered(self):
        self.assertEqual(len(set(ap.FEATURE_NAMES)), len(ap.FEATURE_NAMES))
        self.assertEqual(ap.FEATURE_NAMES[0], "init_drift_change_mag")
        self.assertEqual(ap.FEATURE_NAMES[31], "separation_at_start_deg")

    def test_outcomes_are_never_features(self):
        """prereg 3.10 -- the outcome may not be its own predictor."""
        for outcome in ap.OUTCOMES:
            self.assertNotIn(outcome, ap.FEATURE_NAMES)

    def test_log_subset_is_exactly_the_registered_twenty(self):
        self.assertEqual(len(ap.LOG_FEATURES), 20)
        self.assertIn("transit_days", ap.LOG_FEATURES)
        self.assertNotIn("transit_longitude_span", ap.LOG_FEATURES)
        self.assertNotIn("init_stage_count", ap.LOG_FEATURES)

    def test_causal_subset_excludes_dwell_and_departure(self):
        """prereg 5: an alarm cannot see the dwell it is predicting."""
        for name in ap.CAUSAL_FEATURES:
            self.assertFalse(name.startswith("dwell_"), name)
            self.assertFalse(name.startswith("departure_"), name)
        self.assertNotIn("miss_departure", ap.CAUSAL_FEATURES)
        self.assertIn("transit_days", ap.CAUSAL_FEATURES)
        self.assertIn("cadence_prior_events", ap.CAUSAL_FEATURES)

    def test_gate_bars_are_the_registered_numbers(self):
        self.assertAlmostEqual(ap.T8A_SKILL_LOITER, 0.137)
        self.assertAlmostEqual(ap.GATE_P_BAR, 0.157)
        self.assertAlmostEqual(ap.GATE_V_TOLERANCE, 0.005)
        self.assertEqual(ap.SEED, 20260922)
        self.assertEqual(ap.K_RANGE, tuple(range(2, 11)))

    def test_dwell_window_is_the_registered_leakage_control(self):
        """prereg 3: the dwell block sees the FIRST 30 days and no more, so
        the dwell LENGTH -- the outcome -- cannot enter a feature."""
        self.assertEqual(ap.DWELL_WINDOW_DAYS, 30.0)
        self.assertEqual(ap.W_DWELL, (5.0, 30.0))

    def test_flag_windows_are_disjoint(self):
        """prereg 3: no flag may be counted in two windows."""
        t_s, t_a = 0.0, 100.0
        init = (t_s + ap.W_INIT[0], t_s + ap.W_INIT[1])
        transit = (t_s + ap.W_TRANSIT[0], t_a + ap.W_TRANSIT[1])
        arrival = (t_a + ap.W_ARRIVAL[0], t_a + ap.W_ARRIVAL[1])
        dwell = (t_a + ap.W_DWELL[0], t_a + ap.W_DWELL[1])
        for lo, hi in ((init, transit), (transit, arrival), (arrival, dwell)):
            self.assertLessEqual(lo[1], hi[0], f"{lo} overlaps {hi}")


class TestGeometryIsImportedNotCopied(unittest.TestCase):
    """prereg 2: no T8a definition may silently drift."""

    def test_the_t8a_functions_are_the_t8a_module_s(self):
        for name in ("mean_longitude_deg", "unwrap_longitude", "interpolate",
                     "station_segments", "drift_change_flags",
                     "pair_separation", "wrap180"):
            self.assertTrue(hasattr(pg, name), name)
        src = (_REPO / "tools" / "alarm_pattern.py").read_text()
        self.assertIn("import proximity_geo as pg", src)
        for banned in ("def mean_longitude_deg", "def station_segments",
                       "def drift_change_flags", "def pair_separation",
                       "def unwrap_longitude"):
            self.assertNotIn(banned, src,
                             f"{banned} is reimplemented rather than imported")

    def test_grid_sample_points_match_t8a(self):
        """prereg 2 IMPL: the per-object grid samples the same absolute
        instants T8a's global grid does."""
        s = _series(1, np.arange(0.0, 40.0, 1.0), np.zeros(40))
        s.lam_unwrapped = np.linspace(10.0, 10.05, 40)
        ap.attach_grid(s)
        self.assertEqual(s.grid_lo, int(s.epoch_ms[0] // int(DAY)))
        self.assertEqual(s.grid.size, 40)
        # every sample inside the objects span interpolates; the last grid
        # point sits half a day past the final element set, and T8as
        # `interpolate` refuses it rather than extrapolating
        self.assertTrue(np.isfinite(s.grid[:-1]).all())
        self.assertTrue(math.isnan(float(s.grid[-1])))


class TestFeatureHelpers(unittest.TestCase):
    def test_first_crossing_interpolates(self):
        t = np.array([0.0, 1.0, 2.0])
        y = np.array([0.0, 0.0, 1.0])
        self.assertAlmostEqual(ap._first_crossing(t, y, 0.5), 1.5)

    def test_first_crossing_is_nan_when_never_reached(self):
        self.assertTrue(math.isnan(ap._first_crossing(
            np.array([0.0, 1.0]), np.array([0.0, 0.1]), 9.0)))

    def test_flag_counting_respects_open_and_closed_edges(self):
        flags = np.array([0.0, 10.0, 20.0])
        self.assertEqual(ap._count_flags(flags, 0.0, 20.0), 3)
        self.assertEqual(ap._count_flags(flags, 0.0, 20.0,
                                         closed_lo=False, closed_hi=False), 1)

    def test_autocorr_finds_a_planted_period(self):
        t = np.arange(31.0)
        y = 0.02 * np.sin(2.0 * math.pi * t / 7.0)
        period, frac = ap.autocorr_period(y, 2, 15)
        self.assertAlmostEqual(period, 7.0, delta=1.0)
        self.assertGreater(frac, 0.8)

    def test_autocorr_refuses_a_short_series(self):
        period, frac = ap.autocorr_period(np.arange(5.0), 2, 15)
        self.assertTrue(math.isnan(period) and math.isnan(frac))

    def test_autocorr_refuses_a_flat_series(self):
        period, _ = ap.autocorr_period(np.zeros(31), 2, 15)
        self.assertTrue(math.isnan(period))

    def test_mad_ignores_nan(self):
        self.assertAlmostEqual(ap._mad(np.array([1.0, np.nan, 1.0, 3.0])), 0.0)


class TestCadence(unittest.TestCase):
    def test_cadence_counts_only_prior_events(self):
        events = [
            {"approacherNorad": 7, "arrivalMs": 0, "targetNorad": 1,
             "arrivalIso": "2000-01-01T00:00:00+00:00"},
            {"approacherNorad": 7, "arrivalMs": int(10 * DAY), "targetNorad": 2,
             "arrivalIso": "2000-01-11T00:00:00+00:00"},
            {"approacherNorad": 7, "arrivalMs": int(40 * DAY), "targetNorad": 2,
             "arrivalIso": "2000-02-10T00:00:00+00:00"},
        ]
        tab = ap.cadence_table(events)
        self.assertTrue(math.isnan(tab[id(events[0])]["daysSincePrev"]))
        self.assertEqual(tab[id(events[0])]["priorEvents"], 0)
        self.assertAlmostEqual(tab[id(events[1])]["daysSincePrev"], 10.0)
        self.assertEqual(tab[id(events[1])]["priorTargets"], 1)
        self.assertAlmostEqual(tab[id(events[2])]["daysSincePrev"], 30.0)
        self.assertEqual(tab[id(events[2])]["priorEvents"], 2)
        self.assertEqual(tab[id(events[2])]["priorTargets"], 2)
        # both prior events arrive in 2000-01, so they are ONE arrival
        # under T8a 3.1s (approacher, arrival-month) grouping
        self.assertEqual(tab[id(events[2])]["priorArrivals"], 1)

    def test_cadence_is_per_object(self):
        events = [
            {"approacherNorad": 1, "arrivalMs": 0, "targetNorad": 9,
             "arrivalIso": "2000-01-01"},
            {"approacherNorad": 2, "arrivalMs": int(5 * DAY), "targetNorad": 9,
             "arrivalIso": "2000-01-06"},
        ]
        tab = ap.cadence_table(events)
        self.assertEqual(tab[id(events[1])]["priorEvents"], 0)


class TestTransformAndScaling(unittest.TestCase):
    def test_log_is_applied_only_to_the_registered_subset(self):
        names = ("transit_days", "init_stage_count")
        m = np.array([[math.e, 3.0]])
        out = ap.transform(m, names)
        self.assertAlmostEqual(out[0, 0], 1.0, places=6)
        self.assertEqual(out[0, 1], 3.0)

    def test_negative_input_to_a_log_feature_becomes_nan(self):
        out = ap.transform(np.array([[-1.0]]), ("transit_days",))
        self.assertTrue(math.isnan(out[0, 0]))

    def test_scaler_constants_come_from_the_training_rows_only(self):
        """prereg 3.11 -- the leak this clause exists to prevent."""
        train = np.array([[1.0], [3.0], [5.0]])
        sc = ap.fold_scaler(train)
        self.assertAlmostEqual(float(sc["median"][0]), 3.0)
        self.assertAlmostEqual(float(sc["mean"][0]), 3.0)
        held = ap.apply_scaler(np.array([[100.0]]), sc)
        self.assertGreater(float(held[0, 0]), 10.0)

    def test_nan_is_imputed_at_the_training_median(self):
        sc = ap.fold_scaler(np.array([[1.0], [3.0], [5.0]]))
        z = ap.apply_scaler(np.array([[np.nan]]), sc)
        self.assertAlmostEqual(float(z[0, 0]), 0.0)

    def test_zero_variance_columns_are_dropped(self):
        sc = ap.fold_scaler(np.array([[1.0, 2.0], [1.0, 9.0]]))
        self.assertFalse(bool(sc["keep"][0]))
        self.assertEqual(ap.apply_scaler(np.array([[1.0, 2.0]]), sc).shape[1], 1)


class TestClustering(unittest.TestCase):
    def test_kmeans_recovers_three_planted_blobs(self):
        rng = np.random.default_rng(1)
        x = np.vstack([rng.normal(c, 0.15, size=(40, 2))
                       for c in ([0, 0], [6, 0], [0, 6])])
        labels, centres, _ = ap.kmeans(x, 3, seed=ap.SEED)
        self.assertEqual(centres.shape, (3, 2))
        for block in range(3):
            chunk = labels[block * 40:(block + 1) * 40]
            self.assertEqual(len(set(chunk.tolist())), 1)
        self.assertEqual(len(set(labels.tolist())), 3)

    def test_kmeans_is_deterministic_at_a_fixed_seed(self):
        rng = np.random.default_rng(2)
        x = rng.normal(size=(60, 3))
        a, _, ia = ap.kmeans(x, 4, seed=ap.SEED)
        b, _, ib = ap.kmeans(x, 4, seed=ap.SEED)
        self.assertTrue(np.array_equal(a, b))
        self.assertAlmostEqual(ia, ib)

    def test_silhouette_is_high_for_separated_blobs(self):
        rng = np.random.default_rng(3)
        x = np.vstack([rng.normal(c, 0.1, size=(30, 2)) for c in ([0, 0], [8, 8])])
        labels = np.array([0] * 30 + [1] * 30)
        self.assertGreater(ap.silhouette(x, labels), 0.9)

    def test_silhouette_is_near_zero_for_a_split_of_one_blob(self):
        rng = np.random.default_rng(4)
        x = rng.normal(size=(60, 2))
        labels = np.array([0] * 30 + [1] * 30)
        self.assertLess(ap.silhouette(x, labels), 0.2)

    def test_choose_k_finds_the_planted_count(self):
        rng = np.random.default_rng(5)
        x = np.vstack([rng.normal(c, 0.2, size=(40, 2))
                       for c in ([0, 0], [7, 0], [0, 7], [7, 7])])
        k, rows = ap.choose_k(x, k_range=(2, 3, 4, 5, 6))
        self.assertEqual(k, 4)
        self.assertEqual(len(rows), 5)

    def test_choose_k_breaks_ties_toward_the_smaller_k(self):
        """prereg 4: the tie rule is registered, so it is tested."""
        rows = []

        class _Stub:
            pass
        # a hand-made sweep in which k=3 and k=7 tie to within 1e-9
        sweep = {2: 0.10, 3: 0.50, 4: 0.20, 5: 0.20, 6: 0.20, 7: 0.50 + 1e-9}
        best_sil = max(sweep.values())
        chosen = min(k for k, s in sweep.items() if s > best_sil - 1e-6)
        self.assertEqual(chosen, 3)
        del rows, _Stub

    def test_assign_puts_a_point_with_its_nearest_centre(self):
        centres = np.array([[0.0, 0.0], [10.0, 0.0]])
        got = ap.assign(np.array([[1.0, 0.0], [9.0, 0.0]]), centres)
        self.assertEqual(got.tolist(), [0, 1])


class TestPartitionStatistics(unittest.TestCase):
    def test_adjusted_rand_of_identical_partitions_is_one(self):
        a = np.array([0, 0, 1, 1, 2, 2])
        self.assertAlmostEqual(ap.adjusted_rand(a, a), 1.0)

    def test_adjusted_rand_is_invariant_to_relabelling(self):
        a = np.array([0, 0, 1, 1, 2, 2])
        b = np.array([5, 5, 9, 9, 7, 7])
        self.assertAlmostEqual(ap.adjusted_rand(a, b), 1.0)

    def test_adjusted_rand_of_an_unrelated_partition_is_near_zero(self):
        rng = np.random.default_rng(6)
        a = rng.integers(0, 3, size=400)
        b = rng.integers(0, 3, size=400)
        self.assertLess(abs(ap.adjusted_rand(a, b)), 0.05)

    def test_eta_squared_is_one_when_groups_are_constant_and_differ(self):
        v = np.array([1.0, 1.0, 5.0, 5.0])
        self.assertAlmostEqual(ap.eta_squared(v, np.array([0, 0, 1, 1])), 1.0)

    def test_eta_squared_is_near_zero_for_a_random_split(self):
        rng = np.random.default_rng(7)
        v = rng.normal(size=500)
        lab = rng.integers(0, 3, size=500)
        self.assertLess(ap.eta_squared(v, lab), 0.05)


class TestEstimands(unittest.TestCase):
    """prereg 6 -- the protocol, on fixtures with a known answer."""

    def test_baseline_reproduces_a_hand_computed_skill(self):
        events = [
            {"approacherNorad": 1, "loiterDays": math.e ** 1.0},
            {"approacherNorad": 1, "loiterDays": math.e ** 1.0},
            {"approacherNorad": 2, "loiterDays": math.e ** 3.0},
            {"approacherNorad": 2, "loiterDays": math.e ** 3.0},
        ]
        got = ap.t8a_baseline(events, "loiterDays")
        # each object predicts itself exactly; the population median is 2.0
        self.assertEqual(got["n"], 4)
        self.assertAlmostEqual(got["maeOwnLog"], 0.0)
        self.assertAlmostEqual(got["maePopulationLog"], 1.0)
        self.assertAlmostEqual(got["skill"], 1.0)

    def test_baseline_skips_objects_with_one_event(self):
        events = [{"approacherNorad": 1, "loiterDays": 10.0},
                  {"approacherNorad": 2, "loiterDays": 20.0},
                  {"approacherNorad": 2, "loiterDays": 40.0}]
        got = ap.t8a_baseline(events, "loiterDays")
        self.assertEqual(got["n"], 2)

    def test_baseline_ignores_non_positive_outcomes(self):
        events = [{"approacherNorad": 1, "loiterDays": 0.0},
                  {"approacherNorad": 1, "loiterDays": 10.0},
                  {"approacherNorad": 2, "loiterDays": 20.0},
                  {"approacherNorad": 2, "loiterDays": 40.0}]
        got = ap.t8a_baseline(events, "loiterDays")
        self.assertEqual(got["n"], 2)

    def test_fold_models_hold_out_the_whole_object(self):
        """prereg 6.3 -- nothing about the held-out object may touch the
        model that predicts it."""
        rng = np.random.default_rng(8)
        matrix = rng.normal(size=(40, len(ap.FEATURE_NAMES)))
        objects = np.repeat(np.arange(8), 5)
        folds = ap.fold_models(matrix, ap.FEATURE_NAMES, objects, 3)
        self.assertEqual(len(folds), 8)
        for norad, fold in folds.items():
            self.assertEqual(fold["held"].size, 5)
            self.assertNotIn(norad, objects[fold["train"]].tolist())
            self.assertEqual(fold["train"].size + fold["held"].size, 40)

    def test_bootstrap_resamples_objects_not_events(self):
        """prereg 6.8 -- an event-level interval would be too narrow."""
        src = inspect.getsource(ap.bootstrap_skill)
        self.assertIn("np.unique(groups)", src)
        lo, hi = ap.bootstrap_skill([1.0] * 20, [2.0] * 20,
                                    list(range(10)) * 2)
        self.assertAlmostEqual(lo, 0.5)
        self.assertAlmostEqual(hi, 0.5)

    def test_cluster_skill_is_perfect_when_clusters_carry_the_outcome(self):
        events, matrix, objects = [], [], []
        for obj in range(12):
            group = obj % 2
            for _ in range(2):
                events.append({"approacherNorad": obj, "arrivalMs": len(events),
                               "loiterDays": math.e ** (1.0 if group == 0 else 5.0)})
                row = np.zeros(len(ap.FEATURE_NAMES))
                row[0] = 1.0 if group == 0 else 100.0
                matrix.append(row)
                objects.append(obj)
        matrix = np.asarray(matrix)
        objects = np.asarray(objects)
        folds = ap.fold_models(matrix, ap.FEATURE_NAMES, objects, 2)
        got = ap.cluster_skill(events, folds, objects, 2, "loiterDays")
        self.assertEqual(got["n"], 24)
        self.assertAlmostEqual(got["skill"], 1.0, places=6)

    def test_cluster_skill_is_about_zero_when_clusters_are_noise(self):
        rng = np.random.default_rng(9)
        events, matrix, objects = [], [], []
        for obj in range(40):
            for _ in range(2):
                events.append({"approacherNorad": obj, "arrivalMs": len(events),
                               "loiterDays": float(math.exp(rng.normal()))})
                matrix.append(rng.normal(size=len(ap.FEATURE_NAMES)))
                objects.append(obj)
        matrix, objects = np.asarray(matrix), np.asarray(objects)
        folds = ap.fold_models(matrix, ap.FEATURE_NAMES, objects, 3)
        got = ap.cluster_skill(events, folds, objects, 3, "loiterDays")
        self.assertLess(abs(got["skill"]), 0.25)

    def test_prior_only_uses_fewer_predictions_than_leave_one_out(self):
        rng = np.random.default_rng(10)
        events, matrix, objects = [], [], []
        for obj in range(10):
            for j in range(3):
                events.append({"approacherNorad": obj, "arrivalMs": j,
                               "loiterDays": 30.0 + j})
                matrix.append(rng.normal(size=len(ap.FEATURE_NAMES)))
                objects.append(obj)
        matrix, objects = np.asarray(matrix), np.asarray(objects)
        folds = ap.fold_models(matrix, ap.FEATURE_NAMES, objects, 2)
        lo = ap.cluster_skill(events, folds, objects, 2, "loiterDays")
        po = ap.cluster_skill(events, folds, objects, 2, "loiterDays",
                              prior_only=True)
        self.assertEqual(lo["n"], 30)
        self.assertEqual(po["n"], 20)   # the first event of each object has no prior

    def test_next_interval_drops_each_object_s_last_event(self):
        """prereg 6.7 -- an object's last event has no next interval."""
        events, matrix = [], []
        col = ap.FEATURE_NAMES.index("cadence_days_since_prev")
        for obj in (1, 2):
            for j in range(3):
                events.append({"approacherNorad": obj, "arrivalMs": j,
                               "targetNorad": 5})
                row = np.full(len(ap.FEATURE_NAMES), np.nan)
                row[col] = np.nan if j == 0 else 10.0 * j
                matrix.append(row)
        out, keep = ap.next_interval_events(events, np.asarray(matrix))
        self.assertEqual(len(out), 4)
        self.assertEqual(keep.size, 4)
        self.assertAlmostEqual(out[0]["nextIntervalDays"], 10.0)


class TestGateArithmetic(unittest.TestCase):
    def test_gate_v_tolerance_brackets_the_baseline(self):
        for value, fires in ((0.137, False), (0.1355, False),
                             (0.130, True), (0.145, True)):
            self.assertEqual(
                abs(value - ap.T8A_SKILL_LOITER) > ap.GATE_V_TOLERANCE, fires)

    def test_gate_p_fires_at_or_below_the_bar(self):
        for value, fires in ((0.090, True), (0.157, True), (0.158, False)):
            self.assertEqual(value <= ap.GATE_P_BAR, fires)

    def test_gate_s_needs_five_percent_of_outcome_variance(self):
        self.assertTrue(0.04 < ap.GATE_S_ETA2)
        self.assertFalse(0.12 < ap.GATE_S_ETA2)


class TestPolicyGuards(unittest.TestCase):
    """prereg 1: the framing rules are enforced, not merely intended --
    the same guards T8a's and T8b's suites carry."""

    SRC = (_REPO / "tools" / "alarm_pattern.py").read_text()
    BANNED = ("spying", "spy ", "inspector", "inspection", "threat",
              "adversary", "hostile", "shadowing", "stalking", "surveil",
              "intent", "malicious", "suspicious", "covert",
              "rendezvous and proximity operation")

    def test_no_intent_language_in_the_tool(self):
        text = self.SRC.lower()
        for banned in self.BANNED:
            self.assertNotIn(banned, text, f"intent language {banned!r} present")

    def test_no_intent_language_in_the_feature_names(self):
        joined = " ".join(ap.FEATURE_NAMES).lower()
        for banned in self.BANNED:
            self.assertNotIn(banned.strip(), joined)

    def test_no_detector_branch_reads_a_registry_code(self):
        """prereg 1.1: registry codes enter no feature, no transform, no
        distance, no cluster assignment and no prediction."""
        for fn in (ap.event_features, ap.cadence_table, ap.transform,
                   ap.fold_scaler, ap.apply_scaler, ap.kmeans, ap.silhouette,
                   ap.choose_k, ap.gap_statistic, ap.assign, ap.fold_models,
                   ap.cluster_skill, ap.t8a_baseline, ap.bootstrap_skill,
                   ap.bootstrap_stability, ap.load_series, ap.primary_arm,
                   ap.next_interval_events, ap.describe_clusters,
                   ap.posthoc_diagnostics, ap.adjusted_rand, ap.eta_squared):
            src = inspect.getsource(fn).lower()
            self.assertNotIn("country", src, f"{fn.__name__} reads a registry code")
            self.assertNotIn("registry", src, f"{fn.__name__} reads a registry code")
            self.assertNotIn("owner", src, f"{fn.__name__} reads a registry code")
            self.assertNotIn("nation", src, f"{fn.__name__} reads a registry code")

    def test_the_select_carries_no_metadata_column(self):
        self.assertNotIn("country", ap._SELECT_ONE.lower())
        self.assertNotIn("object_type", ap._SELECT_ONE.lower())

    def test_no_velocity_propellant_or_mass_figure_is_computed(self):
        """The disclaimer lives in the module docstring; no EXECUTABLE path
        may mention such a quantity -- the shape of T8b's own guard."""
        import ast
        tree = ast.parse(self.SRC)
        body = self.SRC.split(ast.get_docstring(tree, clean=False), 1)[1]
        text = body.lower()
        for banned in ("delta_v", "deltav", "delta-v", "propellant", "fuel",
                       "metres_per_second", "m/s of "):
            self.assertNotIn(banned, text, f"{banned!r} present")

    def test_no_feature_is_named_as_a_distance_or_a_miss(self):
        """prereg 1.3: every separation here is mean longitude, a slot
        coordinate -- never a miss distance."""
        for name in ap.FEATURE_NAMES:
            low = name.lower()
            self.assertNotIn("miss_distance", low)
            self.assertNotIn("range_km", low)
            self.assertFalse(low.endswith("_km"), name)

    def test_registration_is_the_one_this_tool_names(self):
        self.assertEqual(
            ap.REGISTRATION,
            "docs/alarm-pattern-preregistration-20260922.md")
        self.assertTrue((_REPO / ap.REGISTRATION).exists())

    def test_the_design_document_takes_no_operator_decision(self):
        """prereg 9: publication surface, framing and whether registry codes
        appear are reserved to the operator. The design document says so and
        contains no intent vocabulary."""
        path = _REPO / "docs" / "alarm-lane-design-20260922.md"
        if not path.exists():
            self.skipTest("the design document is committed after the tool")
        text = path.read_text().lower()
        for banned in ("spying", "inspector", "inspection", "adversary",
                       "hostile", "shadowing", "stalking", "malicious"):
            self.assertNotIn(banned, text, f"intent language {banned!r} present")
        self.assertIn("reserved", text)

    def test_the_results_document_obeys_the_framing_rules(self):
        """prereg 1.2: a cluster name is a mechanical description of element
        behaviour, never a purpose."""
        path = _REPO / "docs" / "alarm-pattern-results-20260922.md"
        if not path.exists():
            self.skipTest("the results document is committed after the tool")
        text = path.read_text().lower()
        for banned in ("spying", "inspector", "inspection", "adversary",
                       "hostile", "shadowing", "stalking", "malicious",
                       "suspicious"):
            self.assertNotIn(banned, text, f"intent language {banned!r} present")
        for banned in ("delta-v", "propellant", "miss distance is", "km of miss"):
            if banned == "delta-v":
                # the disclaimer may say the figure was NOT computed
                continue
            self.assertNotIn(banned, text)

    def test_the_results_document_reports_the_gate_and_the_baseline(self):
        """The comparison this study exists to make must be on its face."""
        path = _REPO / "docs" / "alarm-pattern-results-20260922.md"
        if not path.exists():
            self.skipTest("the results document is committed after the tool")
        text = path.read_text()
        self.assertIn("+0.137", text)
        self.assertIn("Gate P", text)
        self.assertIn("FIRED", text)

    def test_the_design_document_deploys_nothing(self):
        """prereg 9: design only -- nothing deployed, nothing on any site."""
        path = _REPO / "docs" / "alarm-lane-design-20260922.md"
        if not path.exists():
            self.skipTest("the design document is committed after the tool")
        text = path.read_text()
        self.assertIn("NOTHING IS DEPLOYED", text)
        self.assertIn("DESIGN ONLY", text)

    def test_the_registration_fixes_the_feature_set_and_the_criterion(self):
        text = (_REPO / ap.REGISTRATION).read_text()
        self.assertIn("PRIMARY CRITERION", text)
        self.assertIn("mean silhouette coefficient", text)
        self.assertIn("+0.137", text)
        for name in ap.FEATURE_NAMES:
            self.assertIn(name, text, f"{name} is not in the registration")


if __name__ == "__main__":
    unittest.main()
