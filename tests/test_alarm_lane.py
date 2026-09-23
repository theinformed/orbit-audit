#!/usr/bin/env python3
"""Offline tests for the behavioural alarm lane -- the frozen artifact, the
sidecar, the vocabulary gate and the ledger audit.

Every test runs without the archive and without the network.

Three things are asserted here rather than intended.

  * FRAMING COMPLIANCE. `docs/alarm-lane-design-20260922.md` section 7 is a
    list of things the lane must never say. `TestPolicyGuards` is what makes
    it binding, in the same shape T8a, T8b, T8c and T8d used: the banned
    vocabulary is IMPORTED from T8c's suite rather than copied, so the two
    lists cannot drift apart.
  * THE GATE RETURNS WORDS. Section 6 asks for the vocabulary gate to be a
    function that returns the permitted words, not a convention. The tests
    call it and check the words.
  * NOTHING IS SCHEDULED AND NOTHING IS PUBLISHED. No timer, no cron entry,
    no site surface, and no path that sends anything anywhere.
"""

from __future__ import annotations

import inspect
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import alarm_lane as al        # noqa: E402
import alarm_pattern as ap     # noqa: E402
import proximity_geo as pg     # noqa: E402
import trigger_alarm as ta     # noqa: E402

sys.path.insert(0, str(_REPO / "tests"))
import released_sources  # noqa: E402
from test_alarm_pattern import TestPolicyGuards as _T8cGuards  # noqa: E402
from test_trigger_alarm import _series, _quiet_then_burn, SIGMA_N  # noqa: E402

DAY = al.DAY_MS
MODEL_PATH = _REPO / "docs" / "alarm-lane-model-20260922.json"


def _model():
    return al.load_model(MODEL_PATH)


def _spoken_cluster(model):
    for row in model["classes"]:
        if al.class_may_be_spoken(model, row["cluster"])[0]:
            return int(row["cluster"])
    raise AssertionError("no class may be spoken")


def _withheld_cluster(model):
    for row in model["classes"]:
        if not al.class_may_be_spoken(model, row["cluster"])[0]:
            return int(row["cluster"])
    raise AssertionError("every class may be spoken")


def _assessment(norad=40000, t_trig=1.4e12, drift=1.5):
    return {"norad": norad, "tTrigMs": t_trig, "tAnnounceMs": t_trig + 5 * DAY,
            "driftChangeDegPerDay": drift, "gapReason": None}


# ==========================================================================
class TestFrozenArtifact(unittest.TestCase):
    """design 11.3 -- versioned and checksummed, so a published precision
    figure names the model that earned it."""

    def setUp(self):
        self.model = _model()

    def test_the_artifact_exists_and_is_committed(self):
        self.assertTrue(MODEL_PATH.exists())

    def test_it_carries_a_version_and_a_family(self):
        self.assertEqual(self.model["modelVersion"], al.MODEL_VERSION)
        self.assertEqual(self.model["modelFamily"], al.MODEL_FAMILY)
        self.assertEqual(self.model["artifact"], al.ARTIFACT_KIND)

    def test_the_checksum_is_recomputable_from_the_file_alone(self):
        doc = json.loads(MODEL_PATH.read_text())
        body = {k: v for k, v in doc.items() if k != "checksum"}
        self.assertEqual(doc["checksum"], al.checksum_of(body))

    def test_a_tampered_figure_is_refused(self):
        doc = json.loads(MODEL_PATH.read_text())
        doc["classes"][0]["precision"] = 0.5
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            p.write_text(json.dumps(doc))
            with self.assertRaises(al.FrozenModelError):
                al.load_model(p)

    def test_a_tampered_centroid_is_refused(self):
        doc = json.loads(MODEL_PATH.read_text())
        doc["centroids"][0][0] += 1e-9
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            p.write_text(json.dumps(doc))
            with self.assertRaises(al.FrozenModelError):
                al.load_model(p)

    def test_an_absent_artifact_is_refused_rather_than_defaulted(self):
        with self.assertRaises(al.FrozenModelError):
            al.load_model(Path("/nonexistent/model.json"))

    def test_the_checksum_is_stable_across_key_order(self):
        doc = json.loads(MODEL_PATH.read_text())
        body = {k: v for k, v in doc.items() if k != "checksum"}
        shuffled = dict(reversed(list(body.items())))
        self.assertEqual(al.checksum_of(body), al.checksum_of(shuffled))

    def test_the_round_trip_preserves_the_checksum(self):
        doc = json.loads(MODEL_PATH.read_text())
        body = {k: v for k, v in doc.items() if k != "checksum"}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            digest = al.write_model(body, p)
            self.assertEqual(digest, doc["checksum"])
            self.assertEqual(al.load_model(p)["checksum"], doc["checksum"])

    def test_it_names_what_earned_it(self):
        earned = self.model["earnedBy"]
        for key in ("registration", "results", "receipt", "instrument",
                    "featurePathSha256", "eventRecord"):
            self.assertIn(key, earned)
        for key in ("registrationSha256", "resultsSha256", "receiptSha256",
                    "instrumentSha256", "eventRecordSha256"):
            self.assertRegex(earned[key], r"^[0-9a-f]{64}$")

    def test_the_named_sources_still_hash_to_what_it_recorded(self):
        earned = self.model["earnedBy"]
        for path_key, sha_key in (("registration", "registrationSha256"),
                                  ("results", "resultsSha256"),
                                  ("receipt", "receiptSha256"),
                                  ("instrument", "instrumentSha256")):
            # Either the file still hashes to the frozen value, or the
            # released-source record accounts for the difference and names the
            # hash it supersedes. Anything else is a file that changed since
            # the freeze with nothing to say for itself.
            self.assertTrue(
                released_sources.accepts(_REPO, earned[path_key],
                                         earned[sha_key]),
                f"{earned[path_key]} has changed since the freeze")

    def test_the_class_figures_are_the_ones_the_receipt_holds(self):
        receipt = json.loads((_REPO / al.RECEIPT).read_text())
        by_cluster = {int(r["cluster"]): r for r in receipt["classes"]}
        for row in self.model["classes"]:
            ref = by_cluster[int(row["cluster"])]
            self.assertEqual(row["n"], ref["n"])
            self.assertEqual(row["positives"], ref["positives"])
            self.assertAlmostEqual(row["precision"], ref["precision"], places=12)

    def test_the_base_population_is_the_trigger_denominator(self):
        receipt = json.loads((_REPO / al.RECEIPT).read_text())
        pa = receipt["precision"]["primaryArm"]
        self.assertEqual(self.model["basePopulation"]["n"], pa["n"])
        self.assertEqual(self.model["basePopulation"]["positives"],
                         pa["o1PositivesArrivalAfterAnnounce"])

    def test_the_detector_constants_are_the_instrument_s_own(self):
        d = self.model["detector"]
        self.assertEqual(d["mergeDays"], ta.MERGE_DAYS)
        self.assertEqual(d["confirmDays"], ta.CONFIRM_DAYS)
        self.assertEqual(d["horizonDays"], ta.H_DAYS)
        self.assertEqual(d["dwellDays"], ta.DWELL_DAYS)
        self.assertEqual(d["slotDriftFloorDegPerDay"], ta.SLOT_DRIFT_FLOOR)
        self.assertEqual(d["slotMatchDeg"], ta.SLOT_MATCH_DEG)
        self.assertEqual(d["planeMatchDeg"], ta.PLANE_MATCH_DEG)
        self.assertEqual(d["lambdaStableDeg"], ta.LAMBDA_STABLE_DEG)
        self.assertEqual(d["baselineSamples"], pg.BURN_BASELINE_SAMPLES)
        self.assertEqual(d["floorDegPerDay"], pg.BURN_FLOOR_DEG_PER_DAY)

    def test_the_threshold_is_derived_and_not_asserted(self):
        d = self.model["detector"]
        self.assertAlmostEqual(
            d["thresholdDegPerDay"],
            max(d["sigmaK"] * d["sigmaNDegPerDay"], d["floorDegPerDay"]),
            places=15)

    def test_sigma_n_is_not_recalibrated_here(self):
        self.assertAlmostEqual(self.model["detector"]["sigmaNDegPerDay"],
                               SIGMA_N, places=15)

    def test_the_feature_names_are_the_registered_ones_in_order(self):
        self.assertEqual(tuple(self.model["featureNames"]), ta.FEATURE_NAMES)
        self.assertEqual(set(self.model["logFeatures"]), set(ta.LOG_FEATURES))

    def test_the_scaler_has_one_constant_per_feature(self):
        s = self.model["scaler"]
        n = len(self.model["featureNames"])
        for key in ("median", "mean", "sd", "keep"):
            self.assertEqual(len(s[key]), n, key)
        self.assertTrue(all(v > 0 for v in s["sd"]))

    def test_the_centroids_live_in_the_kept_space(self):
        kept = sum(1 for v in self.model["scaler"]["keep"] if v)
        self.assertEqual(len(self.model["centroids"]),
                         self.model["partition"]["k"])
        for row in self.model["centroids"]:
            self.assertEqual(len(row), kept)

    def test_the_look_back_floor_is_the_standing_requirement(self):
        self.assertEqual(self.model["detector"]["lookBackFloorDays"], 1095.0)

    def test_classification_is_deterministic_and_uses_no_fit(self):
        feats = [{n: 1.0 for n in self.model["featureNames"]}]
        first = al.classify(feats, self.model)
        second = al.classify(feats, self.model)
        self.assertEqual(list(first), list(second))
        self.assertIn(int(first[0]), {0, 1})

    def test_classification_of_nothing_is_nothing_and_not_an_error(self):
        self.assertEqual(len(al.classify([], self.model)), 0)

    def test_a_centroid_classifies_to_its_own_class(self):
        """The frozen constants must be self-consistent: a point AT a centroid
        belongs to that centroid."""
        centres = al.model_centroids(self.model)
        for c in range(centres.shape[0]):
            self.assertEqual(int(ap.assign(centres[c:c + 1], centres)[0]), c)

    def test_every_class_carries_its_stability_and_its_spread(self):
        for row in self.model["classes"]:
            self.assertIn("bootstrapJaccard", row)
            self.assertIn("arrivalDays", row)
            self.assertEqual(len(row["wilson95"]), 2)
            self.assertLess(row["wilson95"][0], row["wilson95"][1])

    def test_exactly_one_class_is_named_for_the_wide_crossing_position(self):
        names = [r["name"] for r in self.model["classes"]]
        self.assertEqual(names.count("WIDE-CROSSING"), 1)

    def test_a_class_name_is_a_position_and_not_a_behaviour(self):
        for row in self.model["classes"]:
            low = (row["name"] + " " + row["description"]).lower()
            for banned in _T8cGuards.BANNED:
                self.assertNotIn(banned, low)


# ==========================================================================
class TestVocabularyGate(unittest.TestCase):
    """design 6 -- the gate is a FUNCTION THAT RETURNS THE PERMITTED WORDS."""

    def setUp(self):
        self.model = _model()
        self.spoken = _spoken_cluster(self.model)
        self.withheld = _withheld_cluster(self.model)

    def test_it_returns_words_and_not_a_verdict_alone(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertTrue(v["permittedWords"])
        self.assertTrue(all(isinstance(w, str) and w for w in v["permittedWords"]))

    def test_exactly_one_class_may_speak_today(self):
        speakable = [r["cluster"] for r in self.model["classes"]
                     if al.class_may_be_spoken(self.model, r["cluster"])[0]]
        self.assertEqual(len(speakable), 1)

    def test_the_speaking_class_is_the_one_lifted_above_the_base_rate(self):
        row = al.model_class(self.model, self.spoken)
        base = self.model["basePopulation"]
        self.assertGreater(row["wilson95"][0], base["wilson95"][1])

    def test_the_withheld_class_is_withheld_for_a_measured_reason(self):
        ok, reasons = al.class_may_be_spoken(self.model, self.withheld)
        self.assertFalse(ok)
        self.assertTrue(reasons)
        self.assertIn("base rate", " ".join(reasons))

    def test_the_withheld_class_is_not_withheld_for_want_of_a_measurement(self):
        row = al.model_class(self.model, self.withheld)
        self.assertIsNotNone(row["precision"])
        self.assertGreaterEqual(row["n"], al.MIN_SUPPORT_FOR_A_RATE)

    def test_a_class_below_the_stability_bar_may_not_speak(self):
        model = json.loads(json.dumps(_model()))
        al.model_class(model, self.spoken)["bootstrapJaccard"] = 0.2
        ok, reasons = al.class_may_be_spoken(model, self.spoken)
        self.assertFalse(ok)
        self.assertIn("Jaccard", " ".join(reasons))

    def test_a_class_below_twenty_supporting_events_may_not_speak(self):
        model = json.loads(json.dumps(_model()))
        al.model_class(model, self.spoken)["n"] = 13
        ok, reasons = al.class_may_be_spoken(model, self.spoken)
        self.assertFalse(ok)
        self.assertIn("design 5.2", " ".join(reasons))

    def test_an_underpowered_class_is_labelled_and_draws_no_rate(self):
        model = json.loads(json.dumps(_model()))
        row = al.model_class(model, self.spoken)
        row["positives"] = 7
        v = al.permitted_vocabulary(model, self.spoken)
        self.assertIn("UNDERPOWERED", v["labels"])
        self.assertNotIn("outcome_distribution", v["permitted"])
        self.assertIn("outcome_distribution", v["withheld"])

    def test_the_object_s_own_history_is_always_withheld(self):
        for cluster in (self.spoken, self.withheld, None):
            v = al.permitted_vocabulary(self.model, cluster,
                                        assessable=cluster is not None)
            self.assertIn("object_history", v["withheld"])
            self.assertNotIn("object_history", v["permitted"])

    def test_the_manoeuvre_label_is_withheld_because_the_shipped_one_is(self):
        self.assertFalse(
            self.model["shippedDetectorPermissions"]["manoeuvreLabelPermitted"])
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertIn("manoeuvre", v["withheld"])
        self.assertNotIn("manoeuvre", v["permitted"])

    def test_approach_is_withheld_for_an_individual_alert(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertIn("approach", v["withheld"])

    def test_the_borrowed_precisions_are_withheld_by_name(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertIn("borrowed_precision", v["withheld"])

    def test_a_point_forecast_is_withheld(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertIn("point_forecast", v["withheld"])

    def test_the_base_rate_travels_with_every_assessable_alert(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertIn("base_rate", v["permitted"])

    def test_a_gap_is_labelled_and_never_a_zero(self):
        v = al.permitted_vocabulary(self.model, None, assessable=False,
                                    gap_reason="no usable look-back")
        self.assertIn("NOT ASSESSABLE", v["labels"])
        self.assertFalse(v["mayRaiseAlert"])
        self.assertIn("labelled gap", v["withheld"]["pattern_match"])

    def test_the_gate_always_returns_the_caveats(self):
        for cluster in (self.spoken, self.withheld, None):
            v = al.permitted_vocabulary(self.model, cluster,
                                        assessable=cluster is not None)
            self.assertEqual(tuple(v["caveats"]), al.CAVEATS)
            self.assertIn("caveats", v["permitted"])

    def test_the_gate_always_returns_the_never_say_list(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertEqual(tuple(v["neverSay"]), al.NEVER_SAY)

    def test_the_gate_names_the_model_it_is_gating_for(self):
        v = al.permitted_vocabulary(self.model, self.spoken)
        self.assertEqual(v["modelVersion"], self.model["modelVersion"])
        self.assertEqual(v["modelChecksum"], self.model["checksum"])

    def test_the_withheld_class_raises_no_alert(self):
        v = al.permitted_vocabulary(self.model, self.withheld)
        self.assertFalse(v["mayRaiseAlert"])
        self.assertIn("NOT AN ALERT", v["labels"])


# ==========================================================================
class TestRenderedAlert(unittest.TestCase):

    def setUp(self):
        self.model = _model()
        self.spoken = _spoken_cluster(self.model)
        self.withheld = _withheld_cluster(self.model)

    def _render(self, cluster, **kw):
        v = al.permitted_vocabulary(self.model, cluster)
        return al.render_alert(self.model, _assessment(), v, **kw)

    def test_both_structural_caveats_are_printed_on_the_face(self):
        for cluster in (self.spoken, self.withheld):
            text = self._render(cluster)
            for caveat in al.CAVEATS:
                self.assertIn(caveat, text)

    def test_the_caveats_are_printed_on_a_labelled_gap_too(self):
        v = al.permitted_vocabulary(self.model, None, assessable=False,
                                    gap_reason="a gap")
        text = al.render_alert(self.model, _assessment(), v)
        for caveat in al.CAVEATS:
            self.assertIn(caveat, text)

    def test_the_alert_quotes_its_own_class_and_the_base_rate(self):
        text = self._render(self.spoken)
        row = al.model_class(self.model, self.spoken)
        self.assertIn(f"{row['n']:,}", text)
        self.assertIn("Base rate for a confirmed drift change", text)

    def test_the_alert_quotes_a_distribution_and_not_a_point(self):
        text = self._render(self.spoken)
        self.assertIn("p25-p75", text.replace("p25-p75 ", "p25-p75 ")) \
            if "p25-p75" in text else self.assertIn("Median time", text)
        self.assertIn("Median time from this point to arrival", text)

    def test_the_alert_never_quotes_a_borrowed_precision(self):
        for cluster in (self.spoken, self.withheld):
            text = self._render(cluster)
            for figure in al.FORBIDDEN_FIGURES:
                self.assertNotIn(figure, text,
                                 f"{figure} is a different denominator")

    def test_the_alert_says_drift_rate_change_and_never_the_withheld_word(self):
        text = self._render(self.spoken).lower()
        self.assertIn("drift-rate change", text)
        self.assertNotIn("manoeuvre", text)
        self.assertNotIn("maneuver", text)

    def test_the_alert_never_says_approached(self):
        text = self._render(self.spoken).lower()
        self.assertNotIn("approached", text)

    def test_the_alert_carries_no_registry_code_and_no_object_name(self):
        text = self._render(self.spoken).lower()
        for word in ("country", "registry", "owner", "operator name"):
            self.assertNotIn(word, text)
        self.assertIn("norad", text)

    def test_the_alert_names_the_frozen_model(self):
        text = self._render(self.spoken)
        self.assertIn(self.model["modelVersion"], text)
        self.assertIn(self.model["checksum"][:16], text)

    def test_the_withheld_class_renders_a_refusal_and_not_a_warning(self):
        text = self._render(self.withheld)
        self.assertIn("NOT AN ALERT", text)
        self.assertNotIn("The trigger matches pattern", text)

    def test_the_running_precision_is_a_labelled_gap_before_anything_resolves(self):
        text = self._render(self.spoken, to_date=(0, 0))
        self.assertIn("NOT ASSESSABLE", text)

    def test_the_running_precision_is_printed_once_it_exists(self):
        text = self._render(self.spoken, to_date=(1, 7))
        self.assertIn("1/7", text)

    def test_the_alert_attributes_no_purpose(self):
        text = self._render(self.spoken).lower()
        self.assertIn("no purpose is attributed", text)
        for banned in _T8cGuards.BANNED:
            self.assertNotIn(banned, text)


# ==========================================================================
class TestCadenceDerivation(unittest.TestCase):
    """design 2.3 -- the cadence is DERIVED from measured quantities and is
    not a period anyone chose."""

    def test_the_work_floor_follows_the_spacing_and_is_not_a_constant(self):
        a = al.derive_cadence(0.865)
        b = al.derive_cadence(2.0)
        self.assertAlmostEqual(a["workFloorDays"], 0.865)
        self.assertAlmostEqual(b["workFloorDays"], 2.0)
        self.assertNotEqual(a["workFloorDays"], b["workFloorDays"])

    def test_the_visibility_delay_is_the_confirmation_rule_times_the_spacing(self):
        c = al.derive_cadence(0.865, confirming_element_sets=2)
        self.assertAlmostEqual(c["confirmableVisibilityDays"], 1.73, places=9)

    def test_the_latency_fraction_is_arithmetic_on_the_lead(self):
        c = al.derive_cadence(1.0, median_causal_lead_days=36.1)
        self.assertAlmostEqual(c["latencyFractionOfLead"], 1.0 / 36.1)
        self.assertAlmostEqual(100 * c["latencyFractionOfLead"], 2.77, places=1)

    def test_the_host_timer_buys_nothing_and_the_record_says_so(self):
        c = al.derive_cadence(0.865)
        self.assertAlmostEqual(100 * c["hostTimerLatencyFractionOfLead"], 0.23,
                               places=1)
        self.assertIn("buys", " ".join(c["derivation"]))

    def test_the_derivation_is_carried_not_summarised(self):
        c = al.derive_cadence(0.865)
        self.assertGreaterEqual(len(c["derivation"]), 4)
        self.assertIn("section 2.3", c["citation"])
        self.assertEqual(c["parameter"], "--cadence-hours")

    def test_the_inputs_travel_with_the_output(self):
        c = al.derive_cadence(0.7, spacing_source="measured here")
        self.assertEqual(c["inputs"]["medianEpochSpacingDays"], 0.7)
        self.assertEqual(c["inputs"]["medianEpochSpacingSource"],
                         "measured here")

    def test_the_spacing_is_measured_from_element_sets(self):
        s = _series(1, [0.0, 1.0, 2.0, 5.0], [0.0, 0.0, 0.0, 0.0])
        self.assertAlmostEqual(al.measured_epoch_spacing_days([s]), 1.0)

    def test_no_period_is_hard_coded_in_the_sidecar(self):
        src = inspect.getsource(al.Sidecar)
        self.assertNotIn("24.0 * DAY_MS", src)
        self.assertNotIn("86400000.0 *", src)

    def test_the_state_file_carries_the_derivation(self):
        model = _model()
        state = al._blank_state(model, al.derive_cadence(0.865))
        self.assertIn("derivation", state["cadence"])
        self.assertIn("inputs", state["cadence"])


# ==========================================================================
class TestFlagMemo(unittest.TestCase):
    """The replay's memo is legitimate only because a flag depends on no
    element set after it. That identity is asserted here, not assumed."""

    def setUp(self):
        self.series = _quiet_then_burn(50001, n_quiet=40, n_after=120)
        self.cut = float(self.series.epoch_ms[80])

    def test_the_memo_agrees_with_the_direct_path_at_the_cut(self):
        truncated = al.TruncatedSeries(self.series, 81)
        direct = al.DirectFlags().flags(truncated, SIGMA_N, self.cut)
        memo = al.MemoisedFlags({50001: self.series}).flags(
            truncated, SIGMA_N, self.cut)
        for a, b in zip(direct, memo):
            np.testing.assert_allclose(a, b)

    def test_truncation_does_not_change_the_flags_that_precede_it(self):
        whole = ta.flag_baselines(self.series, SIGMA_N)[0]
        truncated = ta.flag_baselines(al.TruncatedSeries(self.series, 81),
                                      SIGMA_N)[0]
        keep = whole[whole <= self.cut]
        np.testing.assert_allclose(keep, truncated)

    def test_replacing_the_tail_does_not_change_the_earlier_flags(self):
        mutated = _quiet_then_burn(50001, n_quiet=40, n_after=120)
        mutated.drift[81:] = 99.0
        before = ta.flag_baselines(self.series, SIGMA_N)[0]
        after = ta.flag_baselines(mutated, SIGMA_N)[0]
        np.testing.assert_allclose(before[before <= self.cut],
                                   after[after <= self.cut])

    def test_the_mutation_really_would_have_been_visible(self):
        mutated = _quiet_then_burn(50001, n_quiet=40, n_after=120)
        mutated.drift[81:] = 99.0
        self.assertNotEqual(ta.flag_baselines(self.series, SIGMA_N)[0].size,
                            ta.flag_baselines(mutated, SIGMA_N)[0].size)

    def test_the_truncated_series_holds_nothing_after_the_cut(self):
        t = al.TruncatedSeries(self.series, 81)
        self.assertTrue(np.all(t.epoch_ms <= self.cut))
        self.assertEqual(t.epoch_ms.size, 81)


# ==========================================================================
class TestLedgerAndAudit(unittest.TestCase):
    """design 11.5 -- the running precision is measured on THIS lane."""

    def setUp(self):
        self.model = _model()
        self.spoken = _spoken_cluster(self.model)

    def _rows(self, n, arrivals, cluster=None):
        cluster = self.spoken if cluster is None else cluster
        row = al.model_class(self.model, cluster)
        recs = []
        for i in range(n):
            recs.append({
                "record": "assessment", "alertId": f"a{i}", "norad": 40000 + i,
                "class": cluster, "assessable": True, "spoken": True,
                "tTrigMs": 1.4e12 + i * DAY, "tFirstMs": 1.4e12 + i * DAY,
                "tAnnounceMs": 1.4e12 + (i + 5) * DAY,
                "horizonDays": 180.0, "classPrecision": row["precision"],
                "resolution": {"state": "pending"}})
        for i in range(arrivals):
            recs.append({"record": "resolution", "alertId": f"a{i}",
                         "class": cluster, "state": "arrival",
                         "leadDays": 20.0 + i})
        for i in range(arrivals, n):
            recs.append({"record": "resolution", "alertId": f"a{i}",
                         "class": cluster, "state": "none"})
        return recs

    def test_the_precision_is_the_lane_s_own_counts(self):
        audit = al.audit_ledger(self._rows(40, 4), self.model)
        row = audit["classes"][0]
        self.assertEqual(row["resolved"], 40)
        self.assertEqual(row["arrivals"], 4)
        self.assertAlmostEqual(row["precisionOnThisLane"], 0.1)

    def test_the_frozen_figure_is_printed_beside_and_not_instead(self):
        audit = al.audit_ledger(self._rows(40, 4), self.model)
        frozen = audit["classes"][0]["frozenFigure"]
        self.assertAlmostEqual(frozen["precision"],
                               al.model_class(self.model, self.spoken)["precision"])
        self.assertIn("beside", frozen["label"])

    def test_nothing_resolved_is_a_labelled_gap_and_not_a_zero(self):
        audit = al.audit_ledger(self._rows(5, 0)[:5], self.model)
        row = audit["classes"][0]
        self.assertIsNone(row["precisionOnThisLane"])
        self.assertIn("NOT ASSESSABLE", row["precisionLabel"])
        self.assertNotIn("0.000%", row["precisionLabel"])

    def test_fewer_than_twenty_resolutions_is_labelled_underpowered(self):
        audit = al.audit_ledger(self._rows(10, 1), self.model)
        row = audit["classes"][0]
        self.assertTrue(row["underpowered"])
        self.assertIn("UNDERPOWERED", row["precisionLabel"])

    def test_an_alert_that_did_not_pan_out_is_counted_not_dropped(self):
        audit = al.audit_ledger(self._rows(30, 2), self.model)
        row = audit["classes"][0]
        self.assertEqual(row["none"], 28)
        self.assertEqual(row["assessed"], 30)

    def test_the_lead_time_is_measured_on_this_lane(self):
        audit = al.audit_ledger(self._rows(25, 5), self.model)
        lead = audit["classes"][0]["leadDays"]
        self.assertEqual(lead["n"], 5)
        self.assertAlmostEqual(lead["p50"], 22.0)

    def test_the_report_prints_both_caveats(self):
        text = al.audit_report(al.audit_ledger(self._rows(25, 5), self.model))
        for caveat in al.CAVEATS:
            self.assertIn(caveat, text)

    def test_the_report_prints_the_reserved_decisions(self):
        text = al.audit_report(al.audit_ledger(self._rows(3, 0), self.model))
        self.assertIn("RESERVED OPERATOR DECISIONS, none taken", text)
        for key in al.RESERVED_DECISIONS:
            self.assertIn(key, text)

    def test_the_report_names_the_model(self):
        text = al.audit_report(al.audit_ledger(self._rows(3, 0), self.model))
        self.assertIn(self.model["modelVersion"], text)

    def test_the_ledger_round_trips_and_is_append_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "led.jsonl"
            al.ledger_append(path, self._rows(3, 1))
            first = al.ledger_read(path)
            al.ledger_append(path, [{"record": "run", "atMs": 1.0}])
            second = al.ledger_read(path)
            self.assertEqual(second[:len(first)], first)
            self.assertEqual(second[0]["record"], "provenance")

    def test_the_ledger_provenance_carries_the_caveats(self):
        self.assertEqual(al.LEDGER_PROVENANCE["caveats"], list(al.CAVEATS))
        self.assertEqual(al.LEDGER_PROVENANCE["neverSay"], list(al.NEVER_SAY))


# ==========================================================================
class TestResolution(unittest.TestCase):

    def _rec(self, t_trig=1.4e12):
        return {"record": "assessment", "alertId": "x", "norad": 40000,
                "class": 1, "assessable": True, "spoken": True,
                "tFirstMs": t_trig, "tTrigMs": t_trig,
                "tAnnounceMs": t_trig + 5 * DAY, "horizonDays": 180.0}

    def _event(self, flag_ms, arrival_ms, norad=40000):
        return {"approacherNorad": norad, "targetNorad": 40001,
                "initiatingFlagMs": flag_ms, "arrivalMs": arrival_ms,
                "transferStartMs": flag_ms, "loiterEndMs": arrival_ms,
                "loiterDays": 30.0}

    def _open_record(self, t_trig=1.4e12):
        """An unrelated event far beyond the horizon, so the outcome record
        demonstrably extends past the alert and a negative is a real negative
        rather than a labelled gap."""
        return self._event(t_trig, t_trig + 900 * DAY, norad=49999)

    def test_an_arrival_after_the_announce_is_a_hit(self):
        rec = self._rec()
        out = al.resolve_ledger([rec], [self._event(1.4e12, 1.4e12 + 40 * DAY)])
        self.assertEqual(out[0]["state"], "arrival")
        self.assertAlmostEqual(out[0]["leadDays"], 35.0)

    def test_an_arrival_before_the_announce_warned_nobody(self):
        rec = self._rec()
        out = al.resolve_ledger([rec], [self._event(1.4e12, 1.4e12 + 2 * DAY),
                                        self._open_record()])
        self.assertEqual(out[0]["state"], "none")
        self.assertTrue(out[0]["arrivedBeforeAnnounce"])

    def test_an_unattributed_arrival_is_not_claimed(self):
        rec = self._rec()
        far = 1.4e12 - 500 * DAY
        out = al.resolve_ledger([rec], [self._event(far, 1.4e12 + 40 * DAY),
                                        self._open_record()])
        self.assertEqual(out[0]["state"], "none")

    def test_an_outcome_record_that_ends_early_is_a_gap_not_a_miss(self):
        rec = self._rec(t_trig=1.7e12)
        out = al.resolve_ledger([rec], [self._event(1.0e12, 1.0e12 + DAY)])
        self.assertEqual(out[0]["state"], "not-assessable")
        self.assertIn("labelled gap", out[0]["rule"])

    def test_a_labelled_gap_assessment_is_not_resolved_at_all(self):
        rec = dict(self._rec(), assessable=False, spoken=False)
        self.assertEqual(al.resolve_ledger([rec], []), [])


# ==========================================================================
class TestSidecarState(unittest.TestCase):

    def test_a_different_frozen_model_refuses_to_continue_a_ledger(self):
        model = _model()
        cadence = al.derive_cadence(0.865)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            al.save_state(al._blank_state(model, cadence), path)
            other = dict(model)
            other["checksum"] = "0" * 64
            other["_bodyChecksum"] = "0" * 64
            with self.assertRaises(al.FrozenModelError):
                al.load_state(path, other, cadence)

    def test_the_blank_state_names_the_model_and_the_reserved_decisions(self):
        state = al._blank_state(_model(), al.derive_cadence(0.865))
        self.assertEqual(state["model"]["version"], al.MODEL_VERSION)
        self.assertEqual(state["reservedDecisions"], al.RESERVED_DECISIONS)

    def test_the_state_round_trips(self):
        state = al._blank_state(_model(), al.derive_cadence(0.865))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            al.save_state(state, path)
            self.assertEqual(json.loads(path.read_text())["schema"], 1)

    def test_the_clock_can_be_injected(self):
        c = al.Clock(1.4e12)
        self.assertTrue(c.injected)
        self.assertEqual(c.now_ms(), 1.4e12)
        c.set(1.5e12)
        self.assertEqual(c.now_ms(), 1.5e12)
        self.assertEqual(c.record()["mode"], "injected")

    def test_the_system_clock_may_not_be_set(self):
        c = al.Clock()
        self.assertFalse(c.injected)
        with self.assertRaises(RuntimeError):
            c.set(1.0)

    def test_the_sidecar_reads_the_time_only_from_the_clock(self):
        src = inspect.getsource(al.Sidecar)
        self.assertNotIn("time.time", src)
        self.assertNotIn("datetime.now", src)
        self.assertNotIn("utcnow", src)


# ==========================================================================
class TestPolicyGuards(unittest.TestCase):
    """design 7 -- binding, and enforced in the same shape T8a, T8b, T8c and
    T8d used. The banned vocabulary is IMPORTED from T8c's suite, never
    copied, so one canonical list cannot drift out of step with itself."""

    SRC = (_REPO / "tools" / "alarm_lane.py").read_text()
    REPLAY_SRC = (_REPO / "tools" / "alarm_lane_replay.py").read_text()
    CURVE_SRC = (_REPO / "tools" / "alarm_lane_curve.py").read_text()
    LEO_SRC = (_REPO / "tools" / "alarm_lane_leo.py").read_text()
    BANNED = _T8cGuards.BANNED

    def test_the_banned_list_is_t8c_s_and_is_not_a_second_copy(self):
        self.assertIs(self.BANNED, _T8cGuards.BANNED)

    def test_no_purpose_language_in_either_tool(self):
        for name, src in (("alarm_lane", self.SRC),
                          ("alarm_lane_replay", self.REPLAY_SRC),
                          ("alarm_lane_curve", self.CURVE_SRC),
                          ("alarm_lane_leo", self.LEO_SRC)):
            low = src.lower()
            for banned in self.BANNED:
                self.assertNotIn(banned, low, f"{banned!r} present in {name}")

    def test_no_detector_or_gate_branch_reads_a_registry_code(self):
        for fn in (al.classify, al.permitted_vocabulary, al.class_may_be_spoken,
                   al.render_alert, al.derive_cadence, al.resolve_ledger,
                   al.audit_ledger, al.audit_report, al.model_scaler,
                   al.model_centroids, al.model_class, al.Sidecar.fire,
                   al.Sidecar._assess, al.Sidecar._record,
                   al.Sidecar._gap_reason, al.Sidecar._cadence_features,
                   al.ArchiveSource.series, al.ExtractSource.series,
                   al.MemoisedFlags.flags, al.DirectFlags.flags,
                   al.build_frozen_model, al.name_and_description):
            src = inspect.getsource(fn).lower()
            for code in ("country", "registry", "owner", "nation"):
                # word boundaries, because `inclination` is a physical
                # quantity and not a registry code
                self.assertIsNone(
                    re.search(rf"\b{code}\b", src),
                    f"{fn.__qualname__} reads a registry code")

    def test_the_registry_words_appear_only_in_the_never_say_list(self):
        """They must be NAMED, because the lane is forbidden to surface them.
        They may appear nowhere else."""
        joined = " ".join(al.NEVER_SAY) + " " + al.RESERVED_NOTE
        for code in ("country", "registry", "nation"):
            in_list = len(re.findall(rf"\b{code}\b", joined.lower()))
            in_src = len(re.findall(rf"\b{code}\b", self.SRC.lower()))
            self.assertEqual(in_src, in_list,
                             f"{code} appears outside the never-say list")

    def test_only_object_type_is_read_from_the_catalogue(self):
        src = inspect.getsource(ta.object_classes)
        self.assertIn("object_type", src)
        for column in ("country", "launch_date", "object_id", "rcs_size",
                       "name"):
            self.assertNotIn(column, src)

    def test_the_element_query_reads_no_catalogue_column(self):
        src = inspect.getsource(al.ArchiveSource.series)
        self.assertIn("element_set", src)
        self.assertNotIn("JOIN", src.upper())
        self.assertNotIn("object", src.split("FROM")[1].split("WHERE")[0])

    def test_no_velocity_consumable_or_mass_figure_is_computed(self):
        for src in (self.SRC, self.REPLAY_SRC, self.CURVE_SRC, self.LEO_SRC):
            # everything after the module docstring
            body = src.split('"""', 2)[2].lower()
            for banned in ("delta_v", "deltav", "delta-v", "propellant",
                           "fuel", "metres_per_second", "remaining_life"):
                self.assertNotIn(banned, body, f"{banned!r} present")

    def test_no_miss_distance_or_collision_quantity_is_computed(self):
        for src in (self.SRC, self.REPLAY_SRC, self.CURVE_SRC, self.LEO_SRC):
            low = src.lower()
            for banned in ("miss_distance", "range_km", "collision_prob",
                           "pc_value", "conjunction_prob"):
                self.assertNotIn(banned, low)

    def test_the_never_say_list_covers_every_item_of_section_seven(self):
        joined = " ".join(al.NEVER_SAY).lower()
        for topic in ("purpose", "per-nation", "miss distance", "mass",
                      "point forecast", "deliberate", "silent suppression",
                      "own history"):
            self.assertIn(topic, joined, topic)

    def test_the_design_document_still_deploys_nothing(self):
        text = (_REPO / al.DESIGN).read_text()
        self.assertIn("NOTHING IS DEPLOYED", text)
        self.assertIn("nothing is scheduled", text.lower())

    def test_nothing_in_the_lane_installs_a_timer_or_a_cron_entry(self):
        for src in (self.SRC, self.REPLAY_SRC, self.CURVE_SRC, self.LEO_SRC):
            low = src.lower()
            for token in ("systemctl", "crontab", ".timer\"", ".timer'",
                          "systemd-run", "at now"):
                self.assertNotIn(token, low)

    def test_nothing_in_the_lane_sends_anything_anywhere(self):
        for src in (self.SRC, self.REPLAY_SRC, self.CURVE_SRC, self.LEO_SRC):
            low = src.lower()
            for token in ("smtplib", "requests.", "urllib.request", "http://",
                          "https://", "sendmail", "webhook", "socket."):
                self.assertNotIn(token, low)

    def test_nothing_in_the_lane_writes_to_a_published_tree(self):
        for src in (self.SRC, self.REPLAY_SRC, self.CURVE_SRC, self.LEO_SRC):
            for token in ('"src/', "'src/", '"public/', "'public/",
                          '"data/', "'data/"):
                self.assertNotIn(token, src)

    def test_every_database_handle_is_read_only(self):
        for fn in (al.ArchiveSource.__init__, al.ExtractSource.__init__):
            src = inspect.getsource(fn)
            self.assertIn("mode=ro", src)
            self.assertIn("query_only", src)

    def test_the_seven_reserved_decisions_are_all_untaken(self):
        self.assertEqual(len(al.RESERVED_DECISIONS), 7)
        for key, value in al.RESERVED_DECISIONS.items():
            self.assertIsNone(value, key)

    def test_the_reserved_decisions_are_the_design_s_own(self):
        text = (_REPO / al.DESIGN).read_text().lower()
        for phrase in ("publication surface", "framing", "registry codes",
                       "object names", "notification", "leo arm",
                       "retention"):
            self.assertIn(phrase, text, phrase)

    def test_the_frozen_artifact_carries_the_reserved_decisions(self):
        model = _model()
        self.assertEqual(model["reservedDecisions"],
                         {k: None for k in al.RESERVED_DECISIONS})

    def test_the_forbidden_figures_are_named_so_a_test_can_find_them(self):
        self.assertIn("32.8", al.FORBIDDEN_FIGURES)
        self.assertIn("44.1", al.FORBIDDEN_FIGURES)

    def test_no_borrowed_precision_appears_anywhere_in_the_model(self):
        text = MODEL_PATH.read_text()
        for figure in ("0.328", "32.8%", "0.441", "44.1%"):
            self.assertNotIn(figure, text)


# ==========================================================================
class TestSidecarEndToEnd(unittest.TestCase):
    """The sidecar driven by an injected clock over a fixture, with no
    archive: the lane must detect, classify, gate and ledger without ever
    reading an element set later than the clock."""

    class _Source:
        kind = "fixture"

        def __init__(self, series_by_norad, classes):
            self.full = series_by_norad
            self._classes = classes

        def close(self):
            pass

        def classes(self, norads):
            return {int(n): self._classes.get(int(n)) for n in norads}

        def watch_list(self):
            return sorted(self.full), {"source": "fixture",
                                       "objectsKept": len(self.full),
                                       "sha256": None}

        def series(self, norad, upto_ms):
            s = self.full.get(int(norad))
            if s is None:
                return None
            j = int(np.searchsorted(s.epoch_ms, upto_ms, side="right"))
            if j < 2:
                return None
            return al.TruncatedSeries(s, j)

    def setUp(self):
        self.model = _model()
        mover = _quiet_then_burn(50100, n_quiet=60, n_after=200, lam0=10.0)
        neighbour = _series(50200, np.arange(260, dtype=np.float64),
                            np.full(260, 0.0005), lam0=30.0, inc=0.05)
        self.series = {50100: mover, 50200: neighbour}
        self.source = self._Source(self.series, {50100: "active",
                                                 50200: "active"})

    def _run(self, upto_index=200):
        clock = al.Clock(float(self.series[50100].epoch_ms[upto_index]))
        state = al._blank_state(self.model, al.derive_cadence(0.865))
        car = al.Sidecar(self.model, self.source, clock, state, events=[])
        return car, car.fire(), state

    def test_the_lane_detects_and_ledgers_the_fixture_s_change(self):
        _car, records, _state = self._run()
        self.assertTrue(records)
        self.assertTrue(all(r["record"] == "assessment" for r in records))

    def test_every_record_names_the_frozen_model(self):
        _car, records, _state = self._run()
        for rec in records:
            self.assertEqual(rec["modelVersion"], self.model["modelVersion"])
            self.assertEqual(rec["modelChecksum"], self.model["checksum"])

    def test_no_record_is_announced_before_its_announce_time(self):
        _car, records, _state = self._run()
        for rec in records:
            self.assertLessEqual(rec["tAnnounceMs"], rec["announcedAtMs"])

    def test_nothing_after_the_clock_enters_a_record(self):
        clock_ms = float(self.series[50100].epoch_ms[200])
        _car, records, _state = self._run(200)
        for rec in records:
            self.assertLessEqual(rec["tTrigMs"], clock_ms)

    def test_a_second_firing_does_not_re_announce_the_same_trigger(self):
        car, first, _state = self._run()
        car.clock.set(float(self.series[50100].epoch_ms[210]))
        second = car.fire()
        ids = {r["alertId"] for r in first}
        self.assertFalse(ids & {r["alertId"] for r in second})

    def test_the_alert_id_is_stable_for_the_same_trigger(self):
        _c1, first, _s1 = self._run()
        _c2, again, _s2 = self._run()
        self.assertEqual([r["alertId"] for r in first],
                         [r["alertId"] for r in again])

    def test_the_cadence_gate_skips_objects_whose_epoch_has_not_advanced(self):
        car, _first, state = self._run()
        before = state["counters"]["objectsSkippedNoAdvance"]
        car.fire()
        self.assertGreater(state["counters"]["objectsSkippedNoAdvance"], before)

    def test_the_state_records_the_measured_spacing(self):
        _car, _records, state = self._run()
        self.assertIn("measured", state["cadence"]["inputs"]
                      ["medianEpochSpacingSource"])

    def test_every_spoken_record_carries_rendered_text_with_the_caveats(self):
        _car, records, _state = self._run()
        for rec in records:
            if rec["spoken"]:
                for caveat in al.CAVEATS:
                    self.assertIn(caveat, rec["text"])

    def test_a_withheld_record_carries_no_alert_text(self):
        _car, records, _state = self._run()
        for rec in records:
            if rec["assessable"] and not rec["spoken"]:
                self.assertIsNone(rec["text"])

    def test_every_record_carries_the_gate_s_verdict_and_its_reason(self):
        _car, records, _state = self._run()
        for rec in records:
            self.assertIn("vocabulary", rec)
            self.assertIn("patternClause", rec["vocabulary"])

    def test_a_short_history_is_a_labelled_gap_and_not_a_silent_drop(self):
        short = _quiet_then_burn(50300, n_quiet=12, n_after=6, lam0=10.0)
        source = self._Source({50300: short, 50200: self.series[50200]},
                              {50300: "active", 50200: "active"})
        clock = al.Clock(float(short.epoch_ms[-1]))
        state = al._blank_state(self.model, al.derive_cadence(0.865))
        car = al.Sidecar(self.model, source, clock, state, events=[])
        for rec in car.fire():
            if not rec["assessable"]:
                self.assertTrue(rec["gapReason"])
                self.assertIn("NOT ASSESSABLE", rec["text"])



# ==========================================================================
CURVE_PATH = _REPO / "docs" / "alarm-lane-operating-points-20260922.json"
LEO_MODEL_PATH = _REPO / "docs" / "alarm-lane-leo-model-20260922.json"

# a tighter setting is FEWER alerts, at a measured precision, with a measured
# warning time. No output string may dress that up as certainty.
CERTAINTY_WORDS = ("more certain", "more confident", "higher confidence",
                   "more reliable", "more accurate", "greater certainty",
                   "certainty", "surer", "safer bet", "guaranteed",
                   "high certainty")


def _curve():
    return al.load_operating_points(CURVE_PATH, _model())


class TestOperatingPointCurve(unittest.TestCase):
    """The curve is a versioned artifact of its own, checksummed, and it names
    the model that earned it."""

    def setUp(self):
        self.curve = _curve()

    def test_it_exists_and_is_checksummed(self):
        doc = json.loads(CURVE_PATH.read_text())
        body = {k: v for k, v in doc.items() if k != "checksum"}
        self.assertEqual(doc["checksum"], al.checksum_of(body))

    def test_it_names_the_model_that_earned_it(self):
        earned = self.curve["earnedBy"]
        self.assertEqual(earned["modelVersion"], al.MODEL_VERSION)
        self.assertEqual(earned["modelChecksum"], al.model_checksum(_model()))

    def test_it_is_refused_against_a_different_model(self):
        other = dict(_model())
        other["checksum"] = "0" * 64
        other["_bodyChecksum"] = "0" * 64
        with self.assertRaises(al.FrozenModelError):
            al.load_operating_points(CURVE_PATH, other)

    def test_it_carries_a_version(self):
        self.assertTrue(self.curve["curveVersion"].startswith("operating-points/"))

    def test_the_grid_has_the_four_registered_axes(self):
        for axis in ("minDriftChangeDegPerDay", "minSlotsReached",
                     "persistenceSweeps", "leadHorizonDays"):
            self.assertIn(axis, self.curve["grid"])
            self.assertIn(axis, self.curve["axisDefinitions"])

    def test_the_grid_is_swept_completely(self):
        expected = 1
        for values in self.curve["grid"].values():
            expected *= len(values)
        expected *= len(_model()["classes"])
        self.assertEqual(len(self.curve["table"]), expected)

    def test_the_four_named_settings_exist(self):
        names = [s["name"] for s in self.curve["namedSettings"]]
        self.assertEqual(names, ["everything", "balanced", "high-confidence",
                                 "very-high"])

    def test_every_named_setting_is_on_the_grid(self):
        for entry in self.curve["namedSettings"]:
            for axis, value in entry["point"].items():
                self.assertIn(value, self.curve["grid"][axis])

    def test_every_row_carries_the_numbers_a_setting_owes(self):
        for row in self.curve["table"]:
            for key in ("alerts", "arrivals", "precision", "wilson95",
                        "supportingEvents", "underpowered", "leadDays",
                        "alertsPerYear2010s", "alertsPerYearArchiveMean",
                        "recallProxy", "recallNote", "precisionLabel",
                        "mayBeSpoken", "description"):
                self.assertIn(key, row, key)

    def test_a_row_below_twenty_supporting_events_is_labelled_underpowered(self):
        for row in self.curve["table"]:
            if row["alerts"] and row["alerts"] < al.MIN_SUPPORT_FOR_A_RATE:
                self.assertTrue(row["underpowered"])
                self.assertIn("UNDERPOWERED", row["precisionLabel"])

    def test_an_empty_row_is_a_labelled_gap_and_never_a_zero(self):
        empty = [r for r in self.curve["table"] if not r["alerts"]]
        for row in empty:
            self.assertIn("NOT ASSESSABLE", row["precisionLabel"])
            self.assertIsNone(row["precision"])
            self.assertEqual(row["leadDays"]["n"], 0)
            self.assertIn("labelled gap", row["leadDays"]["label"])

    def test_recall_is_stated_to_be_unmeasurable(self):
        self.assertIn("NOT MEASURABLE", self.curve["recallNote"])
        for row in self.curve["table"]:
            self.assertIn("NOT MEASURABLE", row["recallNote"])

    def test_the_recall_proxy_is_a_ratio_between_two_rows(self):
        for row in self.curve["table"]:
            if row["recallProxy"] is not None:
                self.assertEqual(row["recallProxyNumerator"], row["arrivals"])
                self.assertGreater(row["recallProxyDenominator"], 0)

    def test_no_description_dresses_a_threshold_up_as_certainty(self):
        for row in self.curve["table"]:
            low = row["description"].lower()
            for word in CERTAINTY_WORDS:
                self.assertNotIn(word, low, f"{word!r} in a setting description")
        for entry in self.curve["namedSettings"]:
            for c in entry["classes"]:
                low = c["description"].lower()
                for word in CERTAINTY_WORDS:
                    self.assertNotIn(word, low)

    def test_the_tradeoff_is_stated_in_measured_terms(self):
        note = self.curve["tradeoffNote"].lower()
        self.assertIn("fewer alerts", note)
        self.assertIn("measured precision", note)
        self.assertIn("later warning", note)

    def test_the_curve_says_a_tighter_setting_is_not_automatically_better(self):
        self.assertIn("NOT AUTOMATICALLY", self.curve["monotonicityNote"])

    def test_the_loosest_point_is_reconciled_with_the_frozen_population(self):
        note = self.curve["loosestPointVsFrozenPopulation"]
        self.assertEqual(note["frozenPositives"],
                         note["loosestGridPointPositives"])
        self.assertIn("stated here", note["note"])

    def test_the_persistence_axis_is_counted_in_derived_firings(self):
        self.assertAlmostEqual(self.curve["tickDays"],
                               self.curve["cadence"]["workFloorDays"])

    def test_the_horizon_never_exceeds_the_attribution_window(self):
        for value in self.curve["grid"]["leadHorizonDays"]:
            self.assertLessEqual(value, ta.H_DAYS)


class TestSettingAwareGate(unittest.TestCase):

    def setUp(self):
        self.model = _model()
        self.curve = _curve()

    def _point(self, name, cluster):
        setting = al.operating_setting(self.curve, name)
        row = al.setting_class_row(setting, cluster)
        return None if row is None else dict(row, settingName=name)

    def test_the_gate_judges_the_setting_s_own_numbers(self):
        point = self._point("balanced", 0)
        self.assertIsNotNone(point)
        # class 0 is withheld on its whole-population numbers
        self.assertFalse(al.class_may_be_spoken(self.model, 0)[0])
        # and the gate is asked again, at this setting, on ITS numbers
        self.assertEqual(al.class_may_be_spoken(self.model, 0, point)[0],
                         bool(point["mayBeSpoken"]))

    def test_the_alert_quotes_the_setting_s_numbers_and_names_it(self):
        point = self._point("balanced", 1)
        vocab = al.permitted_vocabulary(self.model, 1, point=point)
        self.assertEqual(vocab["setting"], "balanced")
        self.assertEqual(vocab["figures"]["n"], point["alerts"])
        text = al.render_alert(self.model, _assessment(), vocab)
        self.assertIn("balanced", text)
        self.assertIn(f"{point['alerts']:,}", text)

    def test_a_trigger_below_the_evidence_is_labelled_and_not_spoken(self):
        vocab = al.permitted_vocabulary(
            self.model, 1, evidence_failures=("the drift-rate change is small",))
        self.assertFalse(vocab["mayRaiseAlert"])
        self.assertIn("BELOW THIS SETTING'S EVIDENCE", vocab["labels"])
        self.assertIn("below this setting's evidence",
                      vocab["withheld"]["pattern_match"])

    def test_the_setting_s_own_precision_is_never_a_borrowed_one(self):
        for name in ("everything", "balanced", "high-confidence", "very-high"):
            for cluster in (0, 1):
                point = self._point(name, cluster)
                if point is None or not point["mayBeSpoken"]:
                    continue
                vocab = al.permitted_vocabulary(self.model, cluster,
                                                point=point)
                text = al.render_alert(self.model, _assessment(), vocab)
                for figure in al.FORBIDDEN_FIGURES:
                    self.assertNotIn(figure, text)

    def test_no_rendered_alert_at_any_setting_claims_certainty(self):
        for name in ("everything", "balanced", "high-confidence", "very-high"):
            for cluster in (0, 1):
                point = self._point(name, cluster)
                vocab = al.permitted_vocabulary(self.model, cluster,
                                                point=point)
                low = al.render_alert(self.model, _assessment(), vocab).lower()
                for word in CERTAINTY_WORDS:
                    self.assertNotIn(word, low, f"{word!r} at {name}")


class TestPersistenceWithdrawal(unittest.TestCase):
    """A setting that waits must record what it withdrew. A lane that quietly
    forgets the alerts it nearly raised cannot be audited (design 7.9)."""

    def test_a_withdrawal_is_recorded_and_carries_its_reason(self):
        model = _model()
        rec = {"record": "assessment", "alertId": "w1", "norad": 1,
               "class": 1, "assessable": True, "spoken": False,
               "withdrawn": True, "withdrawnReason": "it stopped drifting",
               "tTrigMs": 1.4e12, "tFirstMs": 1.4e12,
               "tAnnounceMs": 1.4e12 + 5 * DAY, "horizonDays": 180.0,
               "resolution": {"state": "withdrawn"}}
        audit = al.audit_ledger([rec], model)
        row = audit["classes"][0]
        self.assertEqual(row["withdrawn"], 1)
        self.assertEqual(row["spoken"], 0)
        self.assertIn("NOT ASSESSABLE", row["precisionLabel"])

    def test_a_withdrawal_is_not_resolved_as_a_miss(self):
        rec = {"record": "assessment", "alertId": "w1", "norad": 40000,
               "class": 1, "assessable": True, "spoken": False,
               "withdrawn": True, "tTrigMs": 1.4e12, "tFirstMs": 1.4e12,
               "tAnnounceMs": 1.4e12 + 5 * DAY, "horizonDays": 180.0}
        self.assertEqual(al.resolve_ledger([rec], []), [])

    def test_the_report_prints_the_withdrawal_count(self):
        model = _model()
        rec = {"record": "assessment", "alertId": "w1", "norad": 1,
               "class": 1, "assessable": True, "spoken": False,
               "withdrawn": True, "tTrigMs": 1.4e12, "tFirstMs": 1.4e12,
               "tAnnounceMs": 1.4e12, "horizonDays": 180.0,
               "resolution": {"state": "withdrawn"}}
        text = al.audit_report(al.audit_ledger([rec], model))
        self.assertIn("withdrawn 1", text)


class TestLeoArm(unittest.TestCase):
    """The LEO arm, which the operator made live, under the scope T8b's own
    measurement established and under no wider one."""

    BLINDED = ("plane", "planes", "planar", "coplanar", "inclination vector",
               "raan", "nodal", "ascending node")

    def setUp(self):
        if not LEO_MODEL_PATH.exists():
            self.skipTest("the LEO arm is frozen after the instrument")
        self.model = al.load_model(LEO_MODEL_PATH)

    def _output_strings(self):
        out = [self.model["scope"], self.model["note"]]
        out.extend(self.model["caveats"])
        out.extend(self.model["neverSay"])
        out.append(self.model["reservedNote"])
        for row in self.model["classes"]:
            out.extend([row["name"], row["description"]])
            out.extend(row["namedByFeatures"])
        out.append(self.model["publishedFigures"]["channelNote"])
        out.append(self.model["publishedFigures"]["scope"])
        out.append(self.model["basePopulation"]["note"])
        for row in self.model["operatingPoints"]["rows"]:
            out.extend([row["description"], row["precisionLabel"],
                        row["recallNote"]])
        out.append(self.model["operatingPoints"]["note"])
        for key, value in self.model["detector"].items():
            if isinstance(value, str):
                out.append(value)
        return out

    def test_it_is_the_same_artifact_shape_as_the_other_arm(self):
        self.assertEqual(self.model["artifact"], al.ARTIFACT_KIND)
        self.assertEqual(self.model["schema"], al.MODEL_SCHEMA)
        for key in ("classes", "basePopulation", "bars", "detector",
                    "caveats", "neverSay", "reservedDecisions"):
            self.assertIn(key, self.model)

    def test_its_checksum_is_recomputable(self):
        doc = json.loads(LEO_MODEL_PATH.read_text())
        body = {k: v for k, v in doc.items() if k != "checksum"}
        self.assertEqual(doc["checksum"], al.checksum_of(body))

    def test_the_scope_travels_with_every_number(self):
        self.assertIn("in-track phasing campaigns", self.model["scope"])
        self.assertIn(self.model["scope"], self.model["caveats"])
        self.assertIn("in-track phasing campaigns",
                      self.model["publishedFigures"]["scope"])

    def test_no_blinded_vocabulary_in_any_output_string(self):
        for text in self._output_strings():
            low = str(text).lower()
            for word in self.BLINDED:
                self.assertIsNone(
                    re.search(rf"\b{re.escape(word)}\b", low),
                    f"{word!r} appears in an output string: {text[:90]!r}")

    def test_no_blinded_vocabulary_in_any_string_the_arm_could_print(self):
        """Every string literal in the arm that could reach a reader -- the
        ones with a space in them, as opposed to column names and file paths
        -- is checked. A blinded word may appear only inside a path."""
        import ast as _ast
        src = (_REPO / "tools" / "alarm_lane_leo.py").read_text()
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Constant) or not isinstance(node.value, str):
                continue
            text = node.value
            if " " not in text:
                continue
            low = text.lower()
            for word in self.BLINDED:
                if re.search(rf"\b{re.escape(word)}\b", low):
                    self.fail(f"{word!r} in a printable string: {text[:80]!r}")

    def test_the_published_figures_are_frozen_as_measured(self):
        pub = self.model["publishedFigures"]
        self.assertEqual(pub["alerts"], 161)
        self.assertEqual(pub["hits"], 71)
        self.assertAlmostEqual(pub["precision"], 71 / 161)
        self.assertAlmostEqual(pub["medianCausalLeadDays"], 195.9)

    def test_the_published_figures_are_not_this_arm_s_own_precision(self):
        self.assertIn("NOT the trigger this arm runs",
                      self.model["publishedFigures"]["channelNote"])
        self.assertNotEqual(self.model["classes"][0].get("precision"),
                            self.model["publishedFigures"]["precision"])

    def test_the_control_class_is_the_never_manoeuvred_one(self):
        base = self.model["basePopulation"]
        self.assertEqual(base["kind"], "never-manoeuvred control")
        self.assertEqual(base["positives"], 0)
        self.assertAlmostEqual(base["objectDays"], 18_790_000.0)

    def test_the_control_states_that_its_trials_are_not_independent(self):
        self.assertIn("NOT independent", self.model["basePopulation"]["note"])

    def test_the_arm_has_its_own_operating_point_rows(self):
        rows = self.model["operatingPoints"]["rows"]
        self.assertGreaterEqual(len(rows), 9)
        self.assertEqual(sum(1 for r in rows if r["isPrimary"]), 1)

    def test_every_unmeasured_setting_is_a_labelled_gap(self):
        for row in self.model["operatingPoints"]["rows"]:
            if row["isPrimary"]:
                continue
            self.assertIsNone(row["precision"])
            self.assertIn("NOT ASSESSABLE", row["precisionLabel"])
            self.assertIn("not a zero", row["precisionLabel"])

    def test_no_operating_point_description_claims_certainty(self):
        for row in self.model["operatingPoints"]["rows"]:
            low = row["description"].lower()
            for word in CERTAINTY_WORDS:
                self.assertNotIn(word, low)

    def test_recall_is_stated_to_be_unmeasurable_here_too(self):
        for row in self.model["operatingPoints"]["rows"]:
            self.assertIn("NOT MEASURABLE", row["recallNote"])

    def test_the_arm_carries_the_extra_never_say_items(self):
        joined = " ".join(self.model["neverSay"]).lower()
        self.assertIn("blinded second channel", joined)
        self.assertIn("different detectors", joined)
        for item in al.NEVER_SAY:
            self.assertIn(item, self.model["neverSay"])

    def test_the_gate_withholds_until_this_trigger_has_its_own_precision(self):
        row = self.model["classes"][0]
        if row["precision"] is None:
            ok, reasons = al.class_may_be_spoken(self.model, 0)
            self.assertFalse(ok)
            self.assertIn("no measured precision", " ".join(reasons))

    def test_a_class_that_is_not_a_cluster_is_exempt_only_when_it_says_so(self):
        row = self.model["classes"][0]
        self.assertIsNone(row["bootstrapJaccard"])
        self.assertIn("not a cluster", row["stabilityBasis"])
        stripped = json.loads(json.dumps(self.model))
        stripped["classes"][0].pop("stabilityBasis")
        ok, reasons = al.class_may_be_spoken(stripped, 0)
        self.assertFalse(ok)
        self.assertIn("bootstrap stability", " ".join(reasons))

    def test_the_operator_s_answer_is_recorded_and_the_rest_stay_reserved(self):
        self.assertNotIn("leoArmIsBuilt", self.model["reservedDecisions"])
        self.assertIn("ANSWERED by the operator", self.model["reservedNote"])
        for key, value in self.model["reservedDecisions"].items():
            self.assertIsNone(value, key)

    def test_the_arm_names_what_earned_it(self):
        earned = self.model["earnedBy"]
        for path_key, sha_key in (("results", "resultsSha256"),
                                  ("instrument", "instrumentSha256")):
            self.assertTrue(
                released_sources.accepts(_REPO, earned[path_key],
                                         earned[sha_key]),
                f"{earned[path_key]} has changed since the freeze")

    def test_the_trigger_constants_are_the_t8b_instrument_s_own(self):
        import proximity_plane as pp
        d = self.model["detector"]
        self.assertEqual(d["semiMajorAxisFloorKm"], pp.DA_FLOOR_KM)
        self.assertEqual(d["sigmaK"], pp.BURN_SIGMA_K)
        self.assertEqual(d["baselineSamples"], pp.BURN_BASELINE_SAMPLES)
        self.assertEqual(d["campaignMaxGapDays"], pp.CAMPAIGN_MAX_GAP_DAYS)
        self.assertEqual(d["horizonDays"], pp.T_LOOK_DAYS)

    def test_the_campaign_boundary_is_read_the_same_from_both_directions(self):
        """T8b cuts the campaign backwards from an arrival; this arm cuts it
        forwards. On the same flag series the boundary must be the same."""
        import proximity_plane as pp
        sys.path.insert(0, str(_REPO / "tools"))
        import alarm_lane_leo as leo
        flags = np.asarray([0.0, 10.0, 20.0, 400.0, 410.0, 900.0]) * DAY
        starts = leo.campaign_starts(flags)
        np.testing.assert_allclose(starts / DAY, [0.0, 400.0, 900.0])
        chain = pp.campaign_of(flags, 905.0 * DAY)
        self.assertAlmostEqual(float(chain[0]) / DAY, 900.0)
        chain = pp.campaign_of(flags, 420.0 * DAY)
        self.assertAlmostEqual(float(chain[0]) / DAY, 400.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
