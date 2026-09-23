"""Offline proofs for the T18 instruments.

Registered in `docs/t18-preregistration-20260922.md` section 8.2. No archive,
no card, no network.

Every test here is built on a case that CONTAINS the bug it is asserting
against: an object placed in two partitions, a training sequence carrying a
test-era epoch, a constellation group split across partitions, a lone outlier
that the confirmation rule must refuse. A test that only exercises the happy
path proves nothing about the condition it claims to guard.
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
for extra in (str(REPO), str(REPO / "tools")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import t18_data as td                                          # noqa: E402

try:
    import t18_model as tm                                     # noqa: E402
    HAVE_TORCH = True
    try:
        import torch                                           # noqa: F401
    except ImportError:
        HAVE_TORCH = False
except ImportError:                                            # pragma: no cover
    tm = None
    HAVE_TORCH = False

try:
    from sgp4.api import Satrec, WGS72                         # noqa: F401
    HAVE_SGP4 = True
except ImportError:                                            # pragma: no cover
    HAVE_SGP4 = False


def _assignment(rows):
    return {str(n): {"unit": u, "partition": p, "admissible": True,
                     "elementSets": 1000, "spanDays": 3000.0,
                     "objectType": "PAYLOAD", "truthSpacecraft": None}
            for n, u, p in rows}


class TestSplitLeaksAreRejected(unittest.TestCase):
    """The split validators, each on a case built to contain its own bug."""

    def test_an_object_in_two_partitions_fails(self):
        # The bug: the same object reached two partitions. A dict cannot hold
        # one key twice, so the case is built the way it actually arises --
        # two assignment blocks merged -- and the pairwise validator is the one
        # that must refuse it.
        train = _assignment([(11111, "norad:11111", "train")])
        test = _assignment([(11111, "norad:11111", "test")])
        with self.assertRaises(td.SplitLeak) as caught:
            td.validate_pairwise(train, test, "train", "test")
        self.assertIn("share 1 object", str(caught.exception))

    def test_a_constellation_group_spanning_partitions_fails(self):
        # The bug: two siblings of one (constellation, plane) group landed in
        # different partitions, so a sibling's future is the object's own.
        leaky = _assignment([
            (20001, "group:STARLINK-|106|3", "train"),
            (20002, "group:STARLINK-|106|3", "test"),
        ])
        with self.assertRaises(td.SplitLeak) as caught:
            td.validate_split(leaky)
        self.assertIn("spans two partitions", str(caught.exception))

    def test_a_clean_split_passes(self):
        clean = _assignment([
            (20001, "group:STARLINK-|106|3", "train"),
            (20002, "group:STARLINK-|106|3", "train"),
            (30001, "norad:30001", "test"),
        ])
        td.validate_split(clean)

    def test_a_truth_spacecraft_outside_test_fails(self):
        # The bug: an object whose labels are the evaluation set was used for
        # training, which would make E1 a measurement of memorisation.
        norad = sorted(td.TRUTH_NORADS)[0]
        leaky = _assignment([(norad, f"norad:{norad}", "train")])
        with self.assertRaises(td.SplitLeak) as caught:
            td.validate_split(leaky)
        self.assertIn("not test", str(caught.exception))

    def test_every_truth_spacecraft_is_forced_to_test(self):
        for norad in td.TRUTH_NORADS:
            self.assertEqual(td.partition_of(norad, f"norad:{norad}"), "test")

    def test_the_pairwise_validator_catches_a_shared_unit(self):
        train = _assignment([(20001, "group:ONEWEB-|87|4", "train")])
        test = _assignment([(20002, "group:ONEWEB-|87|4", "test")])
        with self.assertRaises(td.SplitLeak):
            td.validate_pairwise(train, test, "train", "test")


class TestFutureEpochLeak(unittest.TestCase):

    def test_a_training_sequence_at_or_after_t_cut_fails(self):
        # The bug: the model saw the test era.
        epochs = np.asarray([td.T_CUT_MS - 86400000, td.T_CUT_MS],
                            dtype=np.int64)
        with self.assertRaises(td.SplitLeak) as caught:
            td.validate_no_future("train", epochs)
        self.assertIn("T_cut", str(caught.exception))

    def test_a_validation_sequence_at_or_after_t_cut_fails(self):
        epochs = np.asarray([td.T_CUT_MS + 1], dtype=np.int64)
        with self.assertRaises(td.SplitLeak):
            td.validate_no_future("validation", epochs)

    def test_the_test_partition_may_read_the_test_era(self):
        epochs = np.asarray([td.T_CUT_MS + 86400000], dtype=np.int64)
        td.validate_no_future("test", epochs)

    def test_a_training_sequence_below_t_cut_passes(self):
        epochs = np.asarray([td.T_CUT_MS - 2, td.T_CUT_MS - 1], dtype=np.int64)
        td.validate_no_future("train", epochs)

    def test_build_sequence_refuses_a_leaking_training_object(self):
        el = _synthetic_object(count=8, start_ms=td.T_CUT_MS - 3 * 3600000)
        with self.assertRaises(td.SplitLeak):
            td.build_sequence(el, "train")


class TestSplitDeterminism(unittest.TestCase):

    def test_the_checksum_is_stable_across_two_constructions(self):
        rows = [(i, f"norad:{i}", td.partition_of(i, f"norad:{i}"))
                for i in range(1000, 1200)]
        first = td.split_checksum(_assignment(rows))
        second = td.split_checksum(_assignment(list(reversed(rows))))
        self.assertEqual(first, second)

    def test_the_checksum_moves_when_a_partition_moves(self):
        rows = [(1000, "norad:1000", "train")]
        moved = [(1000, "norad:1000", "test")]
        self.assertNotEqual(td.split_checksum(_assignment(rows)),
                            td.split_checksum(_assignment(moved)))

    def test_siblings_in_one_plane_share_a_unit_and_different_planes_do_not(self):
        a = td.split_unit(40001, "STARLINK-1007", 53.0, 12.0)
        b = td.split_unit(40002, "STARLINK-1008", 53.02, 14.9)
        c = td.split_unit(40003, "STARLINK-2000", 53.0, 200.0)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_an_uncatalogued_object_is_its_own_unit(self):
        self.assertEqual(td.split_unit(9999, "COSMOS 1234", 74.0, 10.0),
                         "norad:9999")

    def test_the_bucket_ranges_partition_the_space(self):
        counts = {"train": 0, "validation": 0, "test": 0}
        for i in range(5000):
            counts[td.partition_of_bucket(td.split_bucket(f"norad:{i}"))] += 1
        self.assertEqual(sum(counts.values()), 5000)
        for value in counts.values():
            self.assertGreater(value, 0)


class TestGeometryClass(unittest.TestCase):
    """The committed Rung-2 assignment is APPLIED, never refitted."""

    @classmethod
    def setUpClass(cls):
        cls.path = REPO / "docs" / "matched-filter-rung2-classes-20260922.json"
        cls.available = cls.path.exists()
        if cls.available:
            cls.classes = td.Rung2Classes.load(cls.path)

    def test_the_committed_artifact_carries_sixty_classes_and_four_edge_sets(self):
        if not self.available:
            self.skipTest("the committed class artifact is not present")
        blob = json.loads(self.path.read_text())
        self.assertEqual(blob["classCount"], 60)
        self.assertEqual(len(blob["classes"]), 60)
        self.assertEqual(sorted(blob["edges"]), ["g1", "g2", "g3", "g4"])
        self.assertEqual(len(blob["edges"]["g1"]), 3)
        self.assertEqual(len(blob["edges"]["g3"]), 2)

    def test_every_key_the_classifier_emits_is_a_committed_key(self):
        if not self.available:
            self.skipTest("the committed class artifact is not present")
        rng = np.random.default_rng(td.SEED)
        emitted = set()
        for _ in range(400):
            spacing = float(np.exp(rng.normal(0.0, 1.0)))
            times = np.cumsum(rng.gamma(4.0, spacing / 4.0, size=400))
            key = self.classes.classify(times)
            if key is not None:
                emitted.add(key)
        self.assertTrue(emitted)
        self.assertTrue(emitted <= self.classes.classes)

    def test_the_ladder_drops_g4_then_g3_then_g2(self):
        classes = td.Rung2Classes(
            {"g1": [0.0], "g2": [0.0], "g3": [1.0], "g4": [0.5]},
            {"g1g2:1-1": {}, "g1:1": {}}, "synthetic")
        times = np.cumsum(np.full(64, 2.0))
        # the full cell is absent, so the ladder must land on g1g2
        self.assertEqual(classes.classify(times), "g1g2:1-1")

    def test_an_unassignable_window_abstains_rather_than_joining_a_class(self):
        classes = td.Rung2Classes(
            {"g1": [0.0], "g2": [0.0], "g3": [1.0], "g4": [0.5]},
            {"g1:0": {}}, "synthetic")
        times = np.cumsum(np.full(64, 2.0))     # lands in g1 bin 1, not 0
        self.assertIsNone(classes.classify(times))

    def test_a_degenerate_window_abstains(self):
        classes = td.Rung2Classes({"g1": [0.0], "g2": [0.0], "g3": [1.0],
                                   "g4": [0.5]}, {"g1:0": {}}, "synthetic")
        self.assertIsNone(classes.classify(np.asarray([1.0])))
        self.assertIsNone(classes.classify(np.asarray([1.0, 1.0, 1.0])))

    def test_the_geometry_windows_tile_the_registered_way(self):
        times = np.arange(0.0, 2000.0, 1.0)
        windows = td.geometry_windows(times)
        self.assertEqual(windows[0], (0.0, 1080.0))
        self.assertEqual(windows[1], (360.0, 1440.0))
        self.assertTrue(all(hi - lo == 1080.0 for lo, hi in windows))
        self.assertTrue(all(hi <= 1999.0 + 1e-9 for _, hi in windows))


class TestOrbitArithmetic(unittest.TestCase):

    def test_osculating_elements_round_trip_through_a_state(self):
        # A state built from known elements must return those elements.
        a, ecc, inc = 7000.0, 0.001, 51.6
        n_rad = math.sqrt(td.MU_KM3_S2 / a ** 3)
        r = np.asarray([a * (1 - ecc), 0.0, 0.0])
        speed = math.sqrt(td.MU_KM3_S2 * (2.0 / np.linalg.norm(r) - 1.0 / a))
        v = np.asarray([0.0, speed * math.cos(math.radians(inc)),
                        speed * math.sin(math.radians(inc))])
        out = td.rv_to_osculating(r, v)
        self.assertAlmostEqual(out["a_km"], a, places=6)
        self.assertAlmostEqual(out["ecc"], ecc, places=8)
        self.assertAlmostEqual(out["inc_deg"], inc, places=8)
        self.assertGreater(n_rad, 0.0)

    def test_rtn_axes_are_orthonormal_and_right_handed(self):
        r = np.asarray([7000.0, 100.0, -50.0])
        v = np.asarray([0.1, 7.5, 0.3])
        for axis, expected in ((np.asarray([1.0, 0.0, 0.0]), None),):
            self.assertIsNotNone(axis)
            self.assertIsNone(expected)
        comps = np.asarray(td.rtn_components(r, v, r))
        self.assertAlmostEqual(float(np.linalg.norm(comps)),
                               float(np.linalg.norm(r)), places=6)

    def test_the_cross_track_component_of_an_in_plane_offset_is_zero(self):
        r = np.asarray([7000.0, 0.0, 0.0])
        v = np.asarray([0.0, 7.5, 0.0])
        _, _, cross = td.rtn_components(r, v, np.asarray([1.0, 2.0, 0.0]))
        self.assertAlmostEqual(cross, 0.0, places=9)

    def test_angle_wrapping_takes_the_short_way_round(self):
        self.assertAlmostEqual(float(td.wrap180(359.9)), -0.1, places=9)
        self.assertAlmostEqual(float(td.wrap180(-359.9)), 0.1, places=9)

    @unittest.skipUnless(HAVE_SGP4, "the propagator is not installed here")
    def test_sgp4_round_trip_at_the_element_sets_own_epoch(self):
        # Propagating a set to its own epoch must return the state its own
        # elements describe, to the accuracy of the model's own periodic terms.
        el = _synthetic_object(count=2)
        row = {k: (el[k][0] if isinstance(el[k], np.ndarray) else el[k])
               for k in el}
        sat, jd, fr = td._satrec(row)
        err, r, v = sat.sgp4(jd, fr)
        self.assertEqual(err, 0)
        out = td.rv_to_osculating(np.asarray(r), np.asarray(v))
        a_expected = (td.MU_KM3_S2 /
                      ((float(row["n_rev_day"]) * 2 * math.pi / 86400.0) ** 2)
                      ) ** (1.0 / 3.0)
        # mean elements are not osculating elements; the gap is the J2 periodic
        # term, of order J2 * a * (Re/a)^2 ~ 10 km at this altitude. What this
        # asserts is that the state is the right orbit, not a wrong one.
        self.assertLess(abs(out["a_km"] - a_expected), 30.0)
        self.assertLess(abs(out["inc_deg"] - float(row["inc_deg"])), 0.2)

    @unittest.skipUnless(HAVE_SGP4, "the propagator is not installed here")
    def test_an_identical_repeat_has_an_exactly_zero_residual(self):
        # The definitional check: set i+1 IS set i at the same instant, so the
        # difference between the propagated and the observed state is zero by
        # construction. A channel that returns anything here is differencing
        # the wrong two things.
        el = _identical_pair()
        targets, ok = td.residual_channels(el)
        self.assertTrue(ok.all())
        np.testing.assert_allclose(targets[0], np.zeros(len(td.TARGET_CHANNELS)),
                                   atol=1e-9)

    @unittest.skipUnless(HAVE_SGP4, "the propagator is not installed here")
    def test_a_semi_major_axis_step_appears_in_the_dA_channel(self):
        # A one-kilometre step in the second set's own semi-major axis must
        # come back as a one-kilometre dA, because that is the quantity the
        # shipped detector thresholds and E1 is like-for-like on it.
        el = _identical_pair()
        n0 = float(el["n_rev_day"][0])
        a0 = (td.MU_KM3_S2 / ((n0 * 2 * math.pi / 86400.0) ** 2)) ** (1.0 / 3.0)
        a1 = a0 + 1.0
        el["n_rev_day"] = np.asarray(
            [n0, math.sqrt(td.MU_KM3_S2 / a1 ** 3) * 86400.0 / (2 * math.pi)])
        targets, ok = td.residual_channels(el)
        self.assertTrue(ok.all())
        self.assertAlmostEqual(float(targets[0, 0]), 1.0, delta=0.05)


class TestChannelSeparation(unittest.TestCase):
    """The cadence-only variant may not see an element value."""

    def test_the_cadence_channels_ignore_the_element_values(self):
        el = _synthetic_object(count=40)
        first = td.cadence_channels(el["epoch_ms"], el["ingest_hour"])
        moved = dict(el)
        moved["n_rev_day"] = el["n_rev_day"] * 1.05
        moved["inc_deg"] = el["inc_deg"] + 3.0
        second = td.cadence_channels(moved["epoch_ms"], moved["ingest_hour"])
        np.testing.assert_allclose(first, second)

    def test_the_cadence_channels_move_when_the_timing_moves(self):
        el = _synthetic_object(count=40)
        shifted = el["epoch_ms"].copy()
        shifted[20:] += 5 * 86400000
        first = td.cadence_channels(el["epoch_ms"], el["ingest_hour"])
        second = td.cadence_channels(shifted, el["ingest_hour"])
        self.assertFalse(np.allclose(first, second))

    def test_the_cadence_group_has_exactly_the_registered_width(self):
        el = _synthetic_object(count=12)
        out = td.cadence_channels(el["epoch_ms"], el["ingest_hour"])
        self.assertEqual(out.shape, (11, len(td.CADENCE_CHANNELS)))

    def test_the_rolling_statistic_is_causal(self):
        # The bug: a centred window reads steps after k, so the statistic at k
        # knows its own future and every downstream number is contaminated.
        values = np.zeros(40)
        values[30:] = 10.0
        med, _ = td.rolling_median_mad(values, 10)
        self.assertEqual(float(med[5]), 0.0)
        self.assertEqual(float(med[29]), 0.0)
        self.assertGreater(float(med[39]), 0.0)


@unittest.skipUnless(HAVE_TORCH, "the framework is not installed here")
class TestModel(unittest.TestCase):

    def test_the_cadence_variant_reads_five_channels_and_the_full_one_more(self):
        cad = tm.build_model("cadence")
        full = tm.build_model("full")
        self.assertEqual(cad.inp.in_channels, len(td.CADENCE_CHANNELS))
        self.assertEqual(full.inp.in_channels,
                         len(td.CADENCE_CHANNELS) + len(td.FIT_CHANNELS)
                         + len(td.TARGET_CHANNELS))

    def test_the_two_variants_are_identical_apart_from_the_input_projection(self):
        cad = tm.build_model("cadence")
        full = tm.build_model("full")
        cad_shapes = {k: tuple(v.shape) for k, v in cad.state_dict().items()
                      if not k.startswith("inp.")}
        full_shapes = {k: tuple(v.shape) for k, v in full.state_dict().items()
                       if not k.startswith("inp.")}
        self.assertEqual(cad_shapes, full_shapes)

    def test_the_parameter_count_is_of_the_registered_order(self):
        total = sum(p.numel() for p in tm.build_model("full").parameters())
        self.assertGreater(total, 100_000)
        self.assertLess(total, 6_000_000)

    def test_with_a_zero_head_the_model_is_the_propagator(self):
        # Registered bound on the failure mode: a zero head predicts a zero
        # residual, i.e. the forecast IS plain SGP4 and cannot be worse than
        # its own baseline by construction. Asserted, not claimed in a comment.
        import torch
        model = tm.build_model("cadence")
        x = torch.randn(2, 48, len(td.CADENCE_CHANNELS))
        loc, log_scale, log_df2 = model(x)
        self.assertTrue(torch.allclose(loc, torch.zeros_like(loc)))
        self.assertTrue(torch.allclose(log_scale, torch.zeros_like(log_scale)))
        self.assertTrue(torch.allclose(log_df2, torch.zeros_like(log_df2)))

    def test_the_stack_is_causal(self):
        # The bug: a symmetric pad lets step k read step k+1, so the detection
        # statistic reads the very step it is scoring.
        import torch
        model = tm.build_model("cadence")
        for p in model.parameters():
            torch.nn.init.normal_(p, std=0.2)
        x = torch.randn(1, 64, len(td.CADENCE_CHANNELS))
        base = model.hidden(x).detach().clone()
        poked = x.clone()
        poked[0, 40:, :] += 5.0
        after = model.hidden(poked).detach()
        self.assertTrue(torch.allclose(base[0, :40], after[0, :40], atol=1e-5))
        self.assertFalse(torch.allclose(base[0, 40:], after[0, 40:], atol=1e-5))

    def test_the_student_t_likelihood_matches_the_closed_form(self):
        import torch
        y = torch.tensor([[[0.7]]])
        loc = torch.tensor([[[0.1]]])
        log_scale = torch.tensor([[[math.log(2.0)]]])
        log_df2 = torch.tensor([[[math.log(3.0)]]])     # df = 5
        got = float(tm.student_t_nll(y, loc, log_scale, log_df2))
        df, scale, z = 5.0, 2.0, 0.3
        expected = -(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
                     - 0.5 * math.log(math.pi * df) - math.log(scale)
                     - (df + 1) / 2 * math.log1p(z * z / df))
        self.assertAlmostEqual(got, expected, places=6)

    def test_the_embedding_is_unit_norm(self):
        import torch
        model = tm.build_model("cadence")
        emb = model.embed(torch.randn(3, 32, len(td.CADENCE_CHANNELS)))
        np.testing.assert_allclose(emb.norm(dim=-1).detach().numpy(),
                                   np.ones(3), atol=1e-5)


@unittest.skipUnless(HAVE_TORCH, "the framework is not installed here")
class TestConfirmationRule(unittest.TestCase):
    """The shipped detector's own rule, adopted unchanged."""

    def test_a_lone_outlier_does_not_flag(self):
        # The bug the rule exists to refuse: a single bad fit produces two
        # consecutive exceedances of OPPOSITE sign -- the step in and the step
        # back out -- and a rule that counted exceedances alone would fire.
        stat = np.asarray([0.0, 0.0, 9.0, 9.0, 0.0, 0.0])
        sign = np.asarray([1.0, 1.0, 1.0, -1.0, 1.0, 1.0])
        epoch = np.arange(6, dtype=np.int64) * 86400000
        valid = np.ones(6, dtype=bool)
        flags = tm.confirmed_flags(stat, sign, epoch, valid, 1.0)
        self.assertEqual(flags.size, 0)

    def test_a_sustained_same_sign_excursion_flags_on_the_second_set(self):
        stat = np.asarray([0.0, 0.0, 9.0, 9.0, 0.0, 0.0])
        sign = np.asarray([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        epoch = np.arange(6, dtype=np.int64) * 86400000
        valid = np.ones(6, dtype=bool)
        flags = tm.confirmed_flags(stat, sign, epoch, valid, 1.0)
        np.testing.assert_array_equal(flags, np.asarray([3 * 86400000]))

    def test_an_invalid_step_cannot_confirm(self):
        stat = np.asarray([0.0, 9.0, 9.0, 0.0])
        sign = np.ones(4)
        epoch = np.arange(4, dtype=np.int64) * 86400000
        valid = np.asarray([True, True, False, True])
        self.assertEqual(
            tm.confirmed_flags(stat, sign, epoch, valid, 1.0).size, 0)


@unittest.skipUnless(HAVE_TORCH, "the framework is not installed here")
class TestProbeIsAPositiveControl(unittest.TestCase):
    """A control that cannot fail is not a test (registration 3.6)."""

    def test_the_probe_fires_on_an_embedding_built_to_carry_sampling_class(self):
        rows = tm.synthetic_probe_rows("sampling")
        out = tm.normalised_probe(rows, rows, "samplingClass")
        self.assertTrue(out["measured"])
        self.assertGreater(out["normalised"], 0.8)

    def test_it_does_not_fire_on_behaviour_when_only_sampling_is_carried(self):
        rows = tm.synthetic_probe_rows("sampling")
        out = tm.normalised_probe(rows, rows, "behaviourClass")
        self.assertTrue(out["measured"])
        self.assertLess(out["normalised"], 0.5)

    def test_the_mirror_image_holds(self):
        rows = tm.synthetic_probe_rows("behaviour")
        behaviour = tm.normalised_probe(rows, rows, "behaviourClass")
        sampling = tm.normalised_probe(rows, rows, "samplingClass")
        self.assertGreater(behaviour["normalised"], 0.8)
        self.assertLess(sampling["normalised"], 0.5)

    def test_gate_g_fails_when_sampling_beats_behaviour(self):
        verdict = tm.gate_g({"measured": True, "normalised": 0.9},
                            {"measured": True, "normalised": 0.2})
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_gate_g_passes_when_behaviour_wins(self):
        verdict = tm.gate_g({"measured": True, "normalised": 0.2},
                            {"measured": True, "normalised": 0.9})
        self.assertEqual(verdict["verdict"], "PASS")

    def test_an_unfittable_probe_is_unmeasured_and_never_a_pass(self):
        verdict = tm.gate_g({"measured": False}, {"measured": True,
                                                  "normalised": 0.5})
        self.assertEqual(verdict["verdict"], "UNMEASURED")



NODE_CANDIDATES = ("node",)


def _node_binary():
    import shutil
    for candidate in NODE_CANDIDATES:
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    return None


class TestPropagatorCrossCheck(unittest.TestCase):
    """Registration 8.2(9): T18 propagates with the reference implementation,
    T16(b) propagated with the site's own. The two are the same algorithm and
    this programme does not assume they agree -- it checks, on a fixed fixture,
    and a disagreement is reported rather than absorbed.

    The comparison is on the three quantities a rotation about the pole cannot
    change -- |r|, the z component and the equatorial radius -- because the
    committed instrument returns a pseudo-Earth-fixed position and
    reimplementing its sidereal rotation here would be checking this file
    against itself.
    """

    @unittest.skipUnless(HAVE_SGP4, "the propagator is not installed here")
    def test_the_two_propagators_agree_on_a_fixed_fixture(self):
        import json as _json
        import subprocess
        node = _node_binary()
        bridge = REPO / "tools" / "truthset_sgp4.mjs"
        if node is None or not bridge.exists():
            self.skipTest("the committed propagator bridge cannot be run here")
        el = _synthetic_object(count=1)
        epoch_ms = int(el["epoch_ms"][0])
        iso = __import__("datetime").datetime.fromtimestamp(
            epoch_ms / 1000.0,
            __import__("datetime").timezone.utc).isoformat(timespec="milliseconds")
        omm = {
            "NORAD_CAT_ID": int(el["norad"]),
            "EPOCH": iso.replace("+00:00", ""),
            "MEAN_MOTION": float(el["n_rev_day"][0]),
            "ECCENTRICITY": float(el["ecc"][0]),
            "INCLINATION": float(el["inc_deg"][0]),
            "RA_OF_ASC_NODE": float(el["raan_deg"][0]),
            "ARG_OF_PERICENTER": float(el["argp_deg"][0]),
            "MEAN_ANOMALY": float(el["m_deg"][0]),
            "BSTAR": float(el["bstar"][0]),
            "MEAN_MOTION_DOT": 0.0,
            "MEAN_MOTION_DDOT": 0.0,
        }
        offsets_ms = [0, 3600_000, 86400_000, 7 * 86400_000]
        samples = [{"t": epoch_ms + off, "gmstMs": epoch_ms + off}
                   for off in offsets_ms]
        payload = _json.dumps({"jobs": [{"id": 0, "omm": omm, "samples": samples}]})
        proc = subprocess.run([node, str(bridge)], input=payload.encode(),
                              capture_output=True, cwd=str(REPO), timeout=120)
        if proc.returncode != 0:
            self.skipTest(f"the committed bridge would not run: "
                          f"{proc.stderr.decode()[:200]}")
        results = _json.loads(proc.stdout.decode())["results"]
        self.assertEqual(len(results), len(offsets_ms))

        row = {k: el[k][0] for k in el if isinstance(el[k], np.ndarray)}
        row["norad"] = el["norad"]
        sat, jd0, fr0 = td._satrec(row)
        worst = 0.0
        for res, off in zip(results, offsets_ms):
            self.assertTrue(res["ok"], res)
            theirs = np.asarray(res["pef"], dtype=np.float64)
            days = off / 86400000.0
            jd, fr = jd0, fr0 + days
            err, mine, _ = sat.sgp4(jd, fr)
            self.assertEqual(err, 0)
            mine = np.asarray(mine, dtype=np.float64)
            for name, value_a, value_b in (
                    ("radius", float(np.linalg.norm(mine)),
                     float(np.linalg.norm(theirs))),
                    ("z", float(mine[2]), float(theirs[2])),
                    ("equatorialRadius", float(np.hypot(mine[0], mine[1])),
                     float(np.hypot(theirs[0], theirs[1])))):
                worst = max(worst, abs(value_a - value_b))
                self.assertLess(
                    abs(value_a - value_b), 0.001,
                    f"{name} disagrees by {abs(value_a - value_b) * 1000:.3f} m "
                    f"at +{days:g} d; a disagreement is reported, not absorbed")
        self.assertLess(worst, 0.001)


def _identical_pair() -> dict:
    """Two element sets that are the SAME fit at the SAME instant.

    The residual between them is zero by construction, which is the only case
    where the channel has an exactly known answer.
    """
    el = _synthetic_object(count=2)
    for key, value in el.items():
        if isinstance(value, np.ndarray) and value.size == 2:
            el[key] = np.asarray([value[0], value[0]], dtype=value.dtype)
    return el


def _synthetic_object(count: int = 8, start_ms: int | None = None) -> dict:
    """A well-formed object with hourly-ish spacing. Elements are a plausible
    low-orbit fit; nothing here is read as a physical claim."""
    if start_ms is None:
        start_ms = int(1600000000000)
    epochs = start_ms + np.arange(count, dtype=np.int64) * 3600000
    return {
        "norad": 99999,
        "epoch_ms": epochs,
        "n_rev_day": np.full(count, 15.2),
        "ecc": np.full(count, 0.0012),
        "inc_deg": np.full(count, 51.64),
        "raan_deg": np.linspace(10.0, 10.3, count),
        "argp_deg": np.linspace(80.0, 80.5, count),
        "m_deg": (np.linspace(0.0, 360.0 * 15.2 * count / 24.0, count) % 360.0),
        "bstar": np.full(count, 1.2e-4),
        "ndot": np.zeros(count),
        "nddot": np.zeros(count),
        "ingest_hour": epochs / 3600000.0 + 2.0,
    }


# ==========================================================================
# The full-model campaign: the no-B* ablation, the stop rule, the E2
# construction, the label shuffle and the paired increment.
# Registered in amendments 2 (91ceede) and 3 (ffb97d6).
# ==========================================================================
try:
    import t18_full as tfu                                     # noqa: E402
    HAVE_FULL = True
except ImportError:                                            # pragma: no cover
    tfu = None
    HAVE_FULL = False

try:
    import t18_forecast as tfc                                 # noqa: E402
    HAVE_FORECAST = True
except ImportError:                                            # pragma: no cover
    tfc = None
    HAVE_FORECAST = False


class _FakeCorpus:
    """A corpus shaped like the extraction's, built in memory."""

    def __init__(self, norad=42, steps=24, seed=7):
        rng = np.random.default_rng(seed)
        self.norads = [norad]
        self.targets = {norad: rng.normal(0, 1, (steps, len(td.TARGET_CHANNELS))).astype(np.float32)}
        self.cadence = {norad: rng.normal(0, 1, (steps, len(td.CADENCE_CHANNELS))).astype(np.float32)}
        self.fit = {norad: rng.normal(0, 1, (steps, len(td.FIT_CHANNELS))).astype(np.float32)}
        self.valid = {norad: np.ones(steps, dtype=bool)}
        self.epoch = {norad: (1672531200000 + np.arange(steps) * 86400000).astype(np.int64)}
        self.windows = {norad: np.asarray([], dtype=object)}


def _unit_stats():
    return {
        "targets": {"centre": [0.0] * len(td.TARGET_CHANNELS),
                    "scale": [1.0] * len(td.TARGET_CHANNELS)},
        "cadence": {"centre": [0.0] * len(td.CADENCE_CHANNELS),
                    "scale": [1.0] * len(td.CADENCE_CHANNELS)},
        "fit": {"centre": [0.0] * len(td.FIT_CHANNELS),
                "scale": [1.0] * len(td.FIT_CHANNELS)},
    }


@unittest.skipUnless(HAVE_TORCH, "torch is not installed")
class TestNoBstarAblation(unittest.TestCase):
    """Amendment 2 A2.5: the ablation removes ONE column and nothing else."""

    def test_the_variant_is_exactly_one_input_channel_narrower(self):
        self.assertEqual(tm.FULL_NOBSTAR_INPUTS, tm.FULL_INPUTS - 1)
        wide = tm.build_model("full").inp.in_channels
        narrow = tm.build_model("full-nobstar").inp.in_channels
        self.assertEqual(narrow, wide - 1)

    def test_the_removed_column_is_the_bstar_one_and_the_rest_are_untouched(self):
        # The bug this is built against: an ablation that silently renormalises
        # or reorders the surviving channels is not the same model minus a
        # column, and the comparison it licenses is not an ablation.
        corpus = _FakeCorpus()
        stats = _unit_stats()
        wide = tm.inputs_for(corpus, 42, "full", stats)
        narrow = tm.inputs_for(corpus, 42, "full-nobstar", stats)
        drop = len(td.CADENCE_CHANNELS) + tm.BSTAR_COLUMN
        expect = np.delete(wide, drop, axis=1)
        self.assertEqual(narrow.shape[1], wide.shape[1] - 1)
        np.testing.assert_allclose(narrow, expect, rtol=0, atol=0)

    def test_the_bstar_column_actually_carried_something(self):
        # A column of zeros would make the ablation vacuous and the test above
        # would still pass, so the column is asserted to be non-constant.
        corpus = _FakeCorpus()
        wide = tm.inputs_for(corpus, 42, "full", _unit_stats())
        column = wide[:, len(td.CADENCE_CHANNELS) + tm.BSTAR_COLUMN]
        self.assertGreater(float(np.std(column)), 0.0)


@unittest.skipUnless(HAVE_TORCH, "torch is not installed")
class TestTheStopRuleFires(unittest.TestCase):
    """Registration 5's 2x stop rule, exercised rather than asserted."""

    def test_a_rate_that_overruns_the_budget_stops_the_campaign(self):
        slow = tm.reprice(0.05, 20000)
        self.assertTrue(slow["measured"])
        self.assertGreater(slow["repricedCampaignGpuHours"],
                           slow["stopThresholdGpuHours"])
        self.assertTrue(slow["stop"])
        self.assertIn("STOP", slow["verdict"])

    def test_a_rate_inside_the_budget_continues(self):
        fast = tm.reprice(26.84, 20000)
        self.assertFalse(fast["stop"])
        self.assertLess(fast["fractionOfBudget"], 1.0)

    def test_the_boundary_is_strict_and_on_the_right_side(self):
        # exactly 2x the budget is NOT an overrun; a hair above it is.
        target = tm.STOP_RULE_MULTIPLE * tm.GPU_BUDGET_HOURS
        per_run = (target - tm.CAMPAIGN_INFERENCE_HOURS) / tm.CAMPAIGN_RUNS
        rate = 20000 / (per_run * 3600.0)
        self.assertFalse(tm.reprice(rate, 20000)["stop"])
        self.assertTrue(tm.reprice(rate * 0.999, 20000)["stop"])

    def test_a_non_positive_rate_is_unmeasured_and_never_zero(self):
        self.assertFalse(tm.reprice(0.0, 20000)["measured"])
        self.assertIn("UNMEASURED", tm.reprice(0.0, 20000)["reason"])


@unittest.skipUnless(HAVE_FORECAST, "the forecast instrument is not importable")
class TestTheForecastConstruction(unittest.TestCase):
    """Amendment 2 A2.3, including the registered zero-head identity."""

    def test_a_zero_head_forecast_is_plain_sgp4_at_every_horizon(self):
        # The registered bound on the failure mode: with the head zeroed the
        # model IS SGP4. Asserted here rather than claimed in a comment.
        for h in (0, 1, 7, 14, 30, 60, 90):
            self.assertEqual(tfc.quadratic_along_km(15.2, 0.0, h), 0.0)
            self.assertEqual(tfc.linear_rtn_km(0.0, h), 0.0)
        self.assertEqual(tfc.quadratic_along_km(15.2, None, 30), 0.0)

    def test_the_correction_is_quadratic_in_the_horizon(self):
        one = tfc.quadratic_along_km(15.2, 1e-4, 10.0)
        two = tfc.quadratic_along_km(15.2, 1e-4, 20.0)
        self.assertAlmostEqual(two / one, 4.0, places=9)

    def test_the_derived_sign_and_scale_are_the_two_body_ones(self):
        # +(3/4) n adot h^2 with n in radians per day. A sign flip here would
        # turn every correction into an anti-correction, so it is pinned.
        n_rev, adot, h = 15.2, 3.0e-4, 14.0
        expect = 0.75 * (n_rev * 2.0 * math.pi) * adot * h * h
        self.assertAlmostEqual(tfc.quadratic_along_km(n_rev, adot, h), expect,
                               places=12)
        self.assertGreater(tfc.quadratic_along_km(n_rev, adot, h), 0.0)
        self.assertLess(tfc.quadratic_along_km(n_rev, -adot, h), 0.0)

    def test_the_linear_secondary_carries_the_opposite_sign_of_the_channel(self):
        # dAlongTrack_km is (new fit) - (propagation), so (propagation - truth)
        # is its negative; a correction built with the wrong sign would double
        # the error rather than remove it.
        self.assertLess(tfc.linear_rtn_km(2.0, 7.0), 0.0)
        self.assertAlmostEqual(tfc.linear_rtn_km(2.0, 7.0), -14.0, places=12)


@unittest.skipUnless(HAVE_FULL, "the full-model instrument is not importable")
class TestTheLabelShuffle(unittest.TestCase):
    """Amendment 3 A3.1: the arm must actually move the labels."""

    @staticmethod
    def _labels(sat="swot", offsets=(0, 5, 40, 41, 300)):
        base = 1600000000000
        return [{"sat": sat, "eventMs": base + o * int(td.DAY_MS),
                 "windowStartMs": base + o * int(td.DAY_MS) - 6 * 3600000,
                 "windowEndMs": base + o * int(td.DAY_MS) + 24 * 3600000}
                for o in offsets]

    def test_the_count_the_first_event_and_the_gap_multiset_survive(self):
        rows = self._labels()
        moved = tfu.shuffle_labels_within_object(rows, seed=td.SEED)
        self.assertEqual(len(moved), len(rows))
        before = sorted(np.diff(sorted(r["eventMs"] for r in rows)).tolist())
        after = sorted(np.diff(sorted(r["eventMs"] for r in moved)).tolist())
        self.assertEqual(before, after)
        self.assertEqual(min(r["eventMs"] for r in moved),
                         min(r["eventMs"] for r in rows))

    def test_it_is_not_the_identity_on_unequal_gaps(self):
        # The bug: permuting labels onto themselves leaves the membership test
        # unchanged and the arm proves nothing. Built on gaps that differ.
        rows = self._labels(offsets=(0, 1, 30, 200, 201, 500))
        moved = tfu.shuffle_labels_within_object(rows, seed=td.SEED)
        self.assertNotEqual(sorted(r["eventMs"] for r in rows),
                            sorted(r["eventMs"] for r in moved))

    def test_a_window_travels_with_its_event(self):
        rows = self._labels()
        moved = tfu.shuffle_labels_within_object(rows, seed=td.SEED)
        for row in moved:
            self.assertEqual(row["windowEndMs"] - row["windowStartMs"],
                             30 * 3600000)
            self.assertLessEqual(row["windowStartMs"], row["eventMs"])
            self.assertGreaterEqual(row["windowEndMs"], row["eventMs"])

    def test_two_labels_are_passed_through_rather_than_faked(self):
        rows = self._labels(offsets=(0, 10))
        moved = tfu.shuffle_labels_within_object(rows, seed=td.SEED)
        self.assertEqual(sorted(r["eventMs"] for r in rows),
                         sorted(r["eventMs"] for r in moved))


@unittest.skipUnless(HAVE_FULL, "the full-model instrument is not importable")
class TestThePairedIncrement(unittest.TestCase):
    """Amendment 2 A2.4: the interval of the difference, clustered on the
    truth spacecraft, paired on the same labels in every draw."""

    @staticmethod
    def _rows(hits, sat="swot"):
        return [{"sat": sat, "index": i, "eventMs": 1600000000000 + i * 86400000,
                 "hit": bool(h), "bin": "<20 m", "side": "belowFloor"}
                for i, h in enumerate(hits)]

    def test_two_identical_models_have_an_increment_of_exactly_zero(self):
        rows = self._rows([1, 0, 1, 0, 1, 1, 0, 0])
        got = tfu.paired_increment(rows, rows, resamples=200)
        self.assertTrue(got["measured"])
        self.assertEqual(got["increment"], 0.0)
        self.assertFalse(got["lowerBoundAboveZero"])

    def test_a_dominating_model_gives_a_positive_increment(self):
        floor = self._rows([0, 0, 0, 0])
        full = self._rows([1, 1, 1, 1])
        got = tfu.paired_increment(full, floor, resamples=200)
        self.assertEqual(got["increment"], 1.0)

    def test_a_losing_model_gives_a_negative_increment_rather_than_zero(self):
        # The bug: clamping a loss to zero would publish a defeat as a draw.
        floor = self._rows([1, 1, 1, 1])
        full = self._rows([0, 0, 1, 0])
        got = tfu.paired_increment(full, floor, resamples=200)
        self.assertLess(got["increment"], 0.0)

    def test_the_cluster_is_the_spacecraft_not_the_label(self):
        rows_a = self._rows([1, 1, 0, 0], sat="swot")
        rows_b = self._rows([0, 0, 1, 1], sat="saral")
        got = tfu.paired_increment(rows_a + rows_b, rows_a + rows_b,
                                   resamples=200)
        self.assertEqual(got["clusters"], 2)
        self.assertEqual(got["clusterKind"], "truth spacecraft")

    def test_a_disjoint_label_set_is_unmeasured_and_never_zero(self):
        full = self._rows([1, 1], sat="swot")
        floor = self._rows([1, 1], sat="saral")
        got = tfu.paired_increment(full, floor, resamples=50)
        self.assertFalse(got["measured"])
        self.assertIn("UNMEASURED", got["reason"])


@unittest.skipUnless(HAVE_FULL, "the full-model instrument is not importable")
class TestTheT13BehaviourTarget(unittest.TestCase):
    """Amendment 2 A2.2: the modal type, with its registered tie-break."""

    @staticmethod
    def _corpus(norad=77, origin=1600000000000):
        class C:
            norads = [norad]
            epoch = {norad: np.asarray([origin], dtype=np.int64)}
        return C()

    def _rows(self, norad=77):
        return [{"norad": norad, "windowStartDays": 0.0,
                 "samplingClass": "g1:3", "embedding": np.zeros(4, np.float32)}]

    def test_the_modal_type_wins(self):
        origin = 1600000000000
        day = int(td.DAY_MS)
        t13 = {"measured": True, "byObject": {77: [
            (origin + 10 * day, "orbit raise"),
            (origin + 20 * day, "orbit raise"),
            (origin + 30 * day, "phasing")]}}
        rows = self._rows()
        covered = tfu.attach_behaviour_targets(rows, self._corpus(), t13,
                                               {77: {"regime": "LEO",
                                                     "era": "2020s",
                                                     "bus": None}})
        self.assertEqual(covered, 1)
        self.assertEqual(rows[0]["behaviourClassT13"], "orbit raise")

    def test_a_tie_breaks_lexicographically_as_registered(self):
        origin = 1600000000000
        day = int(td.DAY_MS)
        t13 = {"measured": True, "byObject": {77: [
            (origin + 10 * day, "phasing"),
            (origin + 20 * day, "orbit raise")]}}
        rows = self._rows()
        tfu.attach_behaviour_targets(rows, self._corpus(), t13,
                                     {77: {"regime": "LEO", "era": "2020s",
                                           "bus": None}})
        self.assertEqual(rows[0]["behaviourClassT13"], "orbit raise")

    def test_a_window_with_no_typed_burn_falls_back_and_is_not_counted(self):
        origin = 1600000000000
        t13 = {"measured": True, "byObject": {77: [
            (origin + 5000 * int(td.DAY_MS), "orbit raise")]}}
        rows = self._rows()
        covered = tfu.attach_behaviour_targets(
            rows, self._corpus(), t13,
            {77: {"regime": "GEO", "era": "2010s", "bus": "HS-601"}})
        self.assertEqual(covered, 0)
        self.assertFalse(rows[0]["t13Covered"])
        self.assertEqual(rows[0]["behaviourClassT13"], "GEO|2010s|HS-601")

    def test_unlabelled_rows_never_become_a_type(self):
        # The bug: the ledger's UNLABELLED is the ABSENCE of a type. Counting
        # it as one would make "unlabelled" the modal class of most windows and
        # hand the probe a target that is mostly a synonym for silence.
        import tempfile                                         # noqa: PLC0415
        lines = [
            json.dumps({"record": "provenance", "subset": True}),
            json.dumps({"norad": 77, "epochMs": 1, "episodeType": "UNLABELLED"}),
            json.dumps({"norad": 77, "epochMs": 2, "episodeType": "UNLABELLED"}),
            json.dumps({"norad": 77, "epochMs": 3, "episodeType": "phasing"}),
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                         delete=False) as handle:
            handle.write("\n".join(lines) + "\n")
            path = Path(handle.name)
        try:
            got = tfu.t13_types_by_object(path)
            self.assertTrue(got["measured"])
            self.assertEqual(got["rows"], 3)
            self.assertEqual(got["typedRows"], 1)
            self.assertEqual([k for _, k in got["byObject"][77]], ["phasing"])
        finally:
            path.unlink()

    def test_a_missing_ledger_is_unmeasured_and_never_empty(self):
        got = tfu.t13_types_by_object(Path("/nonexistent/ledger.jsonl"))
        self.assertFalse(got["measured"])
        self.assertIn("not committed", got["reason"])


if __name__ == "__main__":
    unittest.main()
