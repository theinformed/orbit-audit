#!/usr/bin/env python3
"""Offline tests for the M0/M1/M2 kinematic inputs.

Every test runs without the archive and without the network. The committed
ledgers in `docs/` are read where a test's job is to assert that a row
selection still means what the registration says it means; a test whose ledger
is absent skips rather than passes.

The load-bearing files here are:

  `TestWeighting`      -- the enriched trigger subset must be weighted, and the
                          weighted quantile must recover the population it was
                          drawn from. An unweighted quantile over that subset
                          would describe the sample.
  `TestPhaseArithmetic`-- the integrated mean-motion phase error has a closed
                          form for a linear drift, and the test asserts the
                          implementation against it rather than against itself.
  `TestInstrumentIsImported` -- M1 may not carry its own copy of the forward
                          propagation or of its error measurement.
  `TestPolicyGuards`   -- no propellant, mass or consumables figure; no
                          registry or country code; no miss distance.
"""

from __future__ import annotations

import ast
import inspect
import json
import math
import sys
import textwrap
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import kinematic_inputs as ki  # noqa: E402
import proximity_geo as pg     # noqa: E402
import proximity_plane as pp   # noqa: E402

DOCS = _REPO / "docs"
DAY_MS = pg.DAY_MS


def _skip_without(path):
    if not path.exists():
        raise unittest.SkipTest(f"{path.name} absent")


# ==========================================================================
class TestWeightedQuantile(unittest.TestCase):

    def test_equal_weights_give_the_lower_empirical_quantile(self):
        v = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        w = [1.0] * 10
        self.assertEqual(ki.weighted_quantile(v, w, 50), 5.0)
        self.assertEqual(ki.weighted_quantile(v, w, 100), 10.0)
        self.assertEqual(ki.weighted_quantile(v, w, 5), 1.0)

    def test_a_weight_of_k_is_the_value_repeated_k_times(self):
        v = [1.0, 2.0, 3.0]
        w = [1.0, 7.0, 1.0]
        rep = [1.0] + [2.0] * 7 + [3.0]
        for q in (5, 25, 50, 75, 95):
            self.assertEqual(ki.weighted_quantile(v, w, q),
                             ki.weighted_quantile(rep, [1.0] * 9, q),
                             f"weight and replication disagree at p{q}")

    def test_quantiles_are_monotone_in_q(self):
        rng = np.random.default_rng(7)
        v = rng.lognormal(size=500)
        w = rng.uniform(0.5, 50.0, size=500)
        out = [ki.weighted_quantile(v, w, q) for q in (5, 25, 50, 75, 95)]
        self.assertEqual(out, sorted(out))

    def test_empty_is_nan_not_zero(self):
        self.assertTrue(math.isnan(ki.weighted_quantile([], [], 50)))


class TestWeighting(unittest.TestCase):
    """reg 2.3 -- the subset is enriched and must be weighted."""

    def test_the_registered_weight_is_the_sampling_ratio(self):
        self.assertAlmostEqual(
            ki.OTHERS_WEIGHT,
            (ki.FULL_TABLE_ROWS - ki.SUBSET_POSITIVES) / ki.SUBSET_SAMPLED_OTHERS)
        self.assertAlmostEqual(ki.OTHERS_WEIGHT, 45.1036, places=4)

    def test_weighting_recovers_the_population_an_enriched_sample_came_from(self):
        """The failure this guards: positives are large and all of them are
        kept, so an unweighted quantile over the subset is biased upward."""
        rng = np.random.default_rng(20260922)
        pop_others = rng.lognormal(mean=-3.0, sigma=0.6, size=100_000)
        pop_positive = rng.lognormal(mean=0.0, sigma=0.6, size=1_000)
        population = np.concatenate((pop_others, pop_positive))
        take = rng.choice(pop_others.size, size=2_000, replace=False)
        sample = np.concatenate((pop_others[take], pop_positive))
        weights = np.concatenate((np.full(2_000, pop_others.size / 2_000),
                                  np.ones(pop_positive.size)))
        truth = ki.weighted_quantile(population, np.ones(population.size), 50)
        weighted = ki.weighted_quantile(sample, weights, 50)
        naive = ki.weighted_quantile(sample, np.ones(sample.size), 50)
        self.assertLess(abs(weighted - truth) / truth, 0.05)
        self.assertGreater(abs(naive - truth) / truth, 0.10)


class TestQuantileBlock(unittest.TestCase):

    def test_power_rule_is_printed_in_the_registered_words(self):
        b = ki.quantile_block(list(range(19)))
        self.assertTrue(b["underpowered"])
        self.assertIn("UNDERPOWERED", b["power"])
        b = ki.quantile_block(list(range(20)))
        self.assertFalse(b["underpowered"])
        self.assertNotIn("power", b)

    def test_the_block_always_carries_its_n(self):
        for vals in ([], [1.0], list(range(100))):
            self.assertIn("n", ki.quantile_block(vals))

    def test_the_min_n_is_the_registered_twenty(self):
        self.assertEqual(ki.MIN_N, 20)


class TestConversions(unittest.TestCase):

    def test_geo_drift_conversion_is_the_repository_constant(self):
        self.assertAlmostEqual(ki.geo_drift_to_mps(pg.DRIFT_PER_M_S), 1.0, places=9)
        self.assertAlmostEqual(ki.geo_drift_to_mps(-pg.DRIFT_PER_M_S), 1.0, places=9)
        self.assertAlmostEqual(pg.DRIFT_PER_M_S, 0.3522, places=4)

    def test_leo_conversion_satisfies_da_equals_two_dv_over_n(self):
        a = 6878.137
        n_rad_s = pp.mean_motion_rev_day(a) * 2.0 * math.pi / 86400.0
        for dv in (0.5, 1.0, 13.1):
            da_km = 2.0 * dv / n_rad_s / 1000.0
            self.assertAlmostEqual(ki.leo_da_to_mps(da_km, a), dv, places=9)

    def test_one_metre_per_second_moves_geo_semi_major_axis_by_the_design_figure(self):
        """design 2.3: 27.43 km per m/s at GEO, 1.807 km per m/s at 500 km.
        Both are the same two-body relation; this asserts the module's LEO
        form against the design's GEO number so a sign or factor error in
        either cannot pass."""
        a_geo = pg.A_GEO_KM
        n_rad_s = math.sqrt(398600.4418 / a_geo ** 3)
        self.assertAlmostEqual(2.0 / n_rad_s / 1000.0, 27.43, places=1)
        self.assertAlmostEqual(ki.leo_da_to_mps(1.807, 6878.137), 1.0, places=2)


# ==========================================================================
class TestPhaseArithmetic(unittest.TestCase):
    """reg 4.1, arm P: 360 * integral (n(t) - n0) dt."""

    @staticmethod
    def _series(days, n_of_t, start_ms=1_000_000_000_000.0, step=1.0):
        t = np.arange(0.0, days + 1e-9, step)
        ep = start_ms + t * DAY_MS
        n = np.asarray([n_of_t(x) for x in t], dtype=np.float64)
        u = np.zeros(t.size)
        acc = 0.0
        for i in range(1, t.size):
            acc += 360.0 * 0.5 * (n[i] + n[i - 1]) * (t[i] - t[i - 1])
            u[i] = acc
        ma = pp.wrap360(u)
        return {"epoch_ms": ep, "n": n, "argp": np.zeros(t.size), "ma": ma,
                "e": np.full(t.size, 0.001), "inc": np.full(t.size, 53.0),
                "raan": np.zeros(t.size),
                "bstar": np.full(t.size, 1e-5)}

    def test_a_constant_mean_motion_produces_no_phase_error(self):
        el = self._series(120.0, lambda t: 15.22)
        w = ki.phase_error_windows(el, np.asarray([]), 30.0)
        self.assertEqual(w["windows"], 4)
        for v in w["armP"]:
            self.assertLess(v, 1e-6)

    def test_a_linear_drift_matches_its_closed_form(self):
        """n(t) = n0 + c t  =>  360 * integral = 360 c H^2 / 2."""
        c = 1e-5
        el = self._series(90.0, lambda t: 15.22 + c * t)
        for h in (30.0, 90.0):
            w = ki.phase_error_windows(el, np.asarray([]), h)
            self.assertTrue(w["armP"])
            self.assertAlmostEqual(w["armP"][0], 360.0 * c * h * h / 2.0,
                                   places=6)

    def test_arm_u_sees_the_same_first_window_as_arm_p(self):
        c = 1e-5
        el = self._series(30.0, lambda t: 15.22 + c * t)
        w = ki.phase_error_windows(el, np.asarray([]), 30.0)
        self.assertTrue(w["armU"])
        self.assertAlmostEqual(w["armU"][0], w["armP"][0], places=3)

    def test_a_detected_manoeuvre_inside_the_window_rejects_it(self):
        el = self._series(60.0, lambda t: 15.22)
        flag = np.asarray([el["epoch_ms"][10]])
        w = ki.phase_error_windows(el, flag, 30.0)
        self.assertGreaterEqual(w["rejected"]["flagInWindow"], 1)
        self.assertEqual(len(w["armP"]), 1)

    def test_a_gap_longer_than_the_merge_window_rejects_the_window(self):
        el = self._series(60.0, lambda t: 15.22)
        keep = np.ones(el["epoch_ms"].size, dtype=bool)
        keep[5:14] = False
        el = {k: v[keep] for k, v in el.items()}
        w = ki.phase_error_windows(el, np.asarray([]), 30.0)
        self.assertGreaterEqual(w["rejected"]["gap"] + w["rejected"]["noFarEnd"], 1)

    def test_a_missing_far_end_rejects_the_window(self):
        el = self._series(20.0, lambda t: 15.22)
        w = ki.phase_error_windows(el, np.asarray([]), 30.0)
        self.assertEqual(w["windows"], 0)

    def test_an_unwrappable_arm_u_window_is_excluded_not_counted_as_small(self):
        """A step of more than 90 deg between consecutive element sets means
        the unwrap is not supported; the window must leave arm U rather than
        alias back toward zero."""
        el = self._series(30.0, lambda t: 15.22 + 0.02 * t)   # deliberately extreme
        w = ki.phase_error_windows(el, np.asarray([]), 30.0)
        self.assertGreaterEqual(w["unwrapSuspect"], 1)
        self.assertEqual(w["armU"], [])
        self.assertEqual(len(w["armP"]), 1)

    def test_the_suspect_bar_is_the_registered_ninety_degrees(self):
        self.assertEqual(ki.UNWRAP_SUSPECT_DEG, 90.0)


class TestSlotSpacingArithmetic(unittest.TestCase):

    def test_the_gaps_of_a_wrapped_belt_sum_to_a_full_turn(self):
        lons = np.sort(np.asarray([-170.0, -20.0, 0.0, 45.0, 175.0]))
        gaps = np.diff(lons)
        gaps = np.append(gaps, 360.0 - (lons[-1] - lons[0]))
        self.assertAlmostEqual(float(gaps.sum()), 360.0, places=9)
        self.assertEqual(gaps.size, lons.size)


# ==========================================================================
class TestInstrumentIsImported(unittest.TestCase):
    """reg 3.1 -- M1 calls T8d's own function; it does not re-implement it."""

    SRC = (_REPO / "tools" / "kinematic_inputs.py").read_text()

    def test_m1_calls_the_registered_validator(self):
        self.assertIn("ta.validate_propagator(", self.SRC)

    def test_no_second_copy_of_the_propagation_or_its_error(self):
        for banned in ("def propagate", "def validate_propagator",
                       "def flag_baselines", "def build_triggers",
                       "def mean_longitude_deg", "def object_sigma_contributions"):
            self.assertNotIn(banned, self.SRC,
                             f"{banned} is reimplemented rather than imported")

    def test_the_cohort_selector_is_declared_as_a_selector_only(self):
        src = inspect.getsource(ki._qualifies_at)
        self.assertIn("ONLY to build the matched cohort", src)
        self.assertNotIn("errs", src, "the selector must not measure anything")

    def test_the_published_thirty_day_figures_are_the_gate(self):
        self.assertEqual(ki.T8D_PROP_N, 49318)
        self.assertEqual(ki.T8D_PROP_P50, 0.408)

    def test_the_registered_horizons_are_the_ones_the_design_asked_for(self):
        for h in (30.0, 60.0, 90.0, 180.0):
            self.assertIn(h, ki.HORIZONS_PRIMARY)

    def test_the_thresholds_are_the_registered_ones(self):
        self.assertEqual(ki.COLOCATION_DEG, pg.X_PRIMARY_DEG)
        self.assertEqual(ki.COLOCATION_DEG, 0.1)
        self.assertEqual(ki.GATE_W_DEG, 2.0)
        self.assertEqual(ki.GAMMA_DEG, pp.GAMMA_DEG)
        self.assertEqual(ki.MAX_GAP_DAYS, pp.MAX_GAP_DAYS)


# ==========================================================================
class TestPolicyGuards(unittest.TestCase):

    SRC = (_REPO / "tools" / "kinematic_inputs.py").read_text()

    def test_no_executable_path_reads_a_propellant_or_mass_field(self):
        """The fuel policy: the ledgers this module reads carry propellant
        columns; no branch here may touch one. The module docstring and the
        policy strings may NAME the policy, so the guard is on field access."""
        tree = ast.parse(self.SRC)
        touched = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                touched.add(node.attr.lower())
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value and node.value[0].islower() and " " not in node.value:
                    touched.add(node.value.lower())
        for banned in ("propellantremainingupperboundkg", "excesspropellantkgband",
                       "masskg", "propellantkg", "fuel"):
            self.assertNotIn(banned, touched,
                             f"a propellant or mass field {banned!r} is read")

    @staticmethod
    def _accessed_names(fn):
        """Every attribute name and every subscript key a function touches.

        Checked instead of raw source because the policy STRINGS name the
        codes they forbid ('no registry code, no country') and a guard that
        cannot tell a policy sentence from a field access would force the
        policy to go unwritten.
        """
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                names.add(node.attr.lower())
            elif isinstance(node, ast.Subscript) and isinstance(
                    node.slice, ast.Constant) and isinstance(node.slice.value, str):
                names.add(node.slice.value.lower())
            elif isinstance(node, ast.Call):
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        if " " not in a.value:
                            names.add(a.value.lower())
        return names

    def test_no_registry_or_country_code_is_read_anywhere(self):
        for fn in (ki.m0, ki.m1, ki.m2, ki._m2_population, ki._object_elements,
                   ki.phase_error_windows, ki.quantile_block,
                   ki.weighted_quantile, ki.slot_spacing, ki._qualifies_at):
            names = self._accessed_names(fn)
            for banned in ("country", "registry", "owner", "nation",
                           "approachercountry", "targetcountry",
                           "approacherregistry", "targetregistry"):
                self.assertNotIn(banned, names,
                                 f"{fn.__name__} reads a registry code")

    def test_the_archive_query_carries_no_metadata_column(self):
        src = inspect.getsource(ki._object_elements).lower()
        for banned in ("country", "object_type", "name", "rcs_size"):
            self.assertNotIn(banned, src)

    def test_no_intent_language(self):
        text = self.SRC.lower()
        for banned in ("spying", "spy ", "inspector", "inspection", "threat",
                       "adversary", "hostile", "shadowing", "stalking",
                       "surveil", "malicious", "suspicious", "covert"):
            self.assertNotIn(banned, text, f"intent language {banned!r} present")

    def test_no_miss_distance_is_emitted(self):
        text = self.SRC.lower()
        for banned in ("miss_distance", "missdistance", "range_km",
                       "conjunction"):
            self.assertNotIn(banned, text)

    def test_the_emitted_row_schema_carries_no_forbidden_field(self):
        path = DOCS / "kinematic-inputs-m2-phase-20260922.jsonl"
        _skip_without(path)
        with open(path) as fh:
            for line in fh:
                rec = json.loads(line)
                for key in rec:
                    low = key.lower()
                    for banned in ("country", "registry", "propellant", "fuel",
                                   "mass", "name", "miss"):
                        self.assertNotIn(banned, low,
                                         f"row key {key!r} violates the policy")


# ==========================================================================
class TestCommittedLedgerSelections(unittest.TestCase):
    """reg 2.2 -- the row selections must still pick the populations the
    registration named. A ledger that is re-measured and changes shape must
    fail here rather than silently re-define a class."""

    def test_the_geo_relocation_arm_is_t8a_s_registered_487(self):
        path = DOCS / "proximity-events-20260922.jsonl"
        _skip_without(path)
        rows = ki.read_jsonl(path)
        prim = [e for e in rows if e.get("approacherClass") == "active"
                and e.get("attribution") == "resolved"]
        self.assertEqual(len(prim), 487)

    def test_the_trigger_subset_is_the_registered_shape(self):
        path = DOCS / "trigger-alarm-triggers-20260922.jsonl"
        _skip_without(path)
        rows = ki.read_jsonl(path)
        self.assertEqual(len(rows), ki.SUBSET_ROWS)
        positives = sum(1 for r in rows
                        if r.get("o1Positive") or r.get("o2Positive"))
        self.assertEqual(positives, ki.SUBSET_POSITIVES)

    def test_the_north_south_arm_is_t10b_s_738_on_66_objects(self):
        path = DOCS / "stationkeeping-ns-20260922.jsonl"
        _skip_without(path)
        rows = [r for r in ki.read_jsonl(path) if r.get("informative")]
        self.assertEqual(len(rows), 738)
        self.assertEqual(len({r["norad"] for r in rows}), 66)

    def test_the_leo_arm_is_t8b_s_registered_71(self):
        path = DOCS / "proximity-leo-events-20260922.jsonl"
        _skip_without(path)
        rows = [e for e in ki.read_jsonl(path) if e.get("armM")]
        self.assertEqual(len(rows), 71)

    def test_the_leo_plane_channel_is_blind_and_must_not_be_read_as_a_zero(self):
        path = DOCS / "proximity-leo-events-20260922.jsonl"
        _skip_without(path)
        rows = [e for e in ki.read_jsonl(path) if e.get("armM")]
        total = sum(int(e.get("planeManoeuvresInCampaign") or 0) for e in rows)
        self.assertEqual(total, 0)
        out = DOCS / "kinematic-inputs-20260922.json"
        _skip_without(out)
        c = json.loads(out.read_text())["M0"]["classes"]["C6i_leo_plane_change_in_campaign"]
        self.assertIn("BLINDED CHANNEL", c["verdict"])
        self.assertNotIn("p50", c)


class TestResultsAreReadBackAgainstTheirGates(unittest.TestCase):
    """The defect class this programme has found four times: a bound computed,
    published, and never applied. These assert the published artifact carries
    the fields the design must read."""

    def _results(self):
        path = DOCS / "kinematic-inputs-20260922.json"
        _skip_without(path)
        return json.loads(path.read_text())

    def test_every_m0_class_carries_an_n_and_a_power_verdict(self):
        res = self._results()
        if "M0" not in res:
            raise unittest.SkipTest("M0 not measured yet")
        for name, c in res["M0"]["classes"].items():
            blocks = [v for v in c.values()
                      if isinstance(v, dict) and "underpowered" in v]
            for b in blocks:
                self.assertIn("n", b, f"{name} block without n")

    def test_m1_publishes_its_reproduction_gate(self):
        res = self._results()
        if "M1" not in res:
            raise unittest.SkipTest("M1 not measured yet")
        gate = res["M1"]["gateK1Reproduction"]
        self.assertIn("passed", gate)
        self.assertTrue(gate["passed"], "Gate K1 failed; no M1 figure may stand")
        self.assertEqual(gate["n"], ki.T8D_PROP_N)

    def test_m1_cohort_selector_agreed_with_the_instrument(self):
        res = self._results()
        if "M1" not in res or "armB" not in res["M1"]:
            raise unittest.SkipTest("M1 arm B not measured yet")
        self.assertTrue(res["M1"]["armB"]["selectorAgreesWithInstrument"],
                        "the cohort selector and validate_propagator disagree")

    def test_m2_reports_objects_without_a_usable_window_separately(self):
        res = self._results()
        if "M2" not in res:
            raise unittest.SkipTest("M2 not measured yet")
        cell = res["M2"]["meaningfulHorizon"]["90"]["gamma5"]["byStratum"]["POOLED"]
        self.assertIn("noUsableWindow", cell)
        self.assertEqual(cell["objectsSampled"],
                         cell["withUsableWindow"] + cell["noUsableWindow"])


if __name__ == "__main__":
    unittest.main()
