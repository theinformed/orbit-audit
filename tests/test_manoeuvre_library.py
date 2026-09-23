#!/usr/bin/env python3
"""Offline tests for T13, the manoeuvre library.

Registration: docs/manoeuvre-library-preregistration-20260922.md.

Every test runs without the archive, without the element caches and without the
network. Nothing here is scheduled and nothing here publishes.

THESE TESTS ASSERT THE BUG FIRST. Every case recorded below was written
against the instrument BEFORE the instrument could satisfy it, run, and
observed to FAIL with the message quoted; the instrument (or, where the test
itself was wrong, the test) was then changed and the same case observed to
PASS. Both states were observed, in that order, and the failures are written
down here so a later reader can tell a test that caught something from a test
that was written to agree with the code.

Defects in the INSTRUMENT, found by these tests:

  1. `test_seeded_graveyard_raise_is_not_unlabelled` --
     "AssertionError: 'UNLABELLED' != 'graveyard raise'". A raise of 300 km at
     GEO is also a drift change of 3.85 deg/day, so rule G6 and rule G1 both
     fired on one burn and the exactly-one-rule requirement made it
     UNLABELLED. The registration section 4.1 fixes a STAGED evaluation -- G6
     then G7 first, the mutually exclusive G1-G5 after -- and the first
     `assign_type` was a single flat pass that ignored it.
  2. `test_seeded_decaying_burn_is_not_unlabelled` --
     "AssertionError: 'UNLABELLED' != 'decaying'", the same missing stage on
     arm P.
  3. `test_seeded_station_segment_after_the_burn_is_not_read`, first failure --
     "AssertionError: [] is not true : the fixture must contain a drift stop".
     Not the fixture: `geo_burns` differenced the two element sets either side
     of the flag. The registered detector flags the SECOND confirming element
     set, so the set immediately before a flag is already on the far side of
     the change and every delta came out near zero. The detector measures
     against its own trailing median baseline (T8a prereg 5.5) and now so does
     the library -- `trailing_baseline`.
  4. `test_seeded_station_segment_after_the_burn_is_not_read`, second failure --
     "AssertionError: True is not false : the only segment at this longitude
     begins after the burn". A station segment's offsets are relative to the
     daily grid's own origin, which `geo_burns` was not given: every segment
     landed in 1970, every segment therefore ended before every burn, and
     every drift stop would have been typed a return instead of a station
     acquisition. `test_seeded_station_segment_epochs_carry_the_grid_origin`
     now asserts the origin directly, so the defect cannot come back silently.
  5. `test_no_intent_language_in_the_tool` --
     "AssertionError: 'inspection' unexpectedly found in ...". A comment in the
     instrument used a word the inherited T8c list forbids. Reworded.
  6. `test_no_fuel_mass_or_delta_v_figure_anywhere` --
     the module docstring named the units it promises never to print. Reworded
     to say the same thing without carrying the words.

Defects in these TESTS, found by running them:

  7. `test_no_registry_field_in_the_rule_table` --
     "AssertionError: 'nation' present in the rule table". A substring test for
     ownership words forbids `inclination`, which is a kinematic element. The
     test now matches whole words.
  8. `test_forbidden_vocabulary_is_absent_from_the_artifact` --
     "AssertionError: 'accuracy' unexpectedly found". The artifact's own
     disclaimer says the figures are "not accuracy". The test now holds the
     disclaimer to the opposite standard: it MUST contain the denial, and the
     rest of the artifact must not contain the words at all.

Cases that passed from the first run, kept because they guard the bug a later
version is most likely to introduce: the both-channels-fired burn staying
UNLABELLED, and no rule reading a catalogue field.

The stage-0 precedence is a REGISTERED evaluation order, not a tie-break among
competing rules: it is fixed in the registration before any number, it is
published in the rule table, and the number of stage-0 assignments that also
satisfied a stage-1 rule is reported rather than hidden.
"""

from __future__ import annotations

import inspect
import json
import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO / "tools"), str(Path(__file__).resolve().parent), str(_REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_names  # noqa: E402  the names, kept out of this file

import manoeuvre_library as ml                       # noqa: E402
import proximity_geo as pg                           # noqa: E402
import proximity_plane as pp                         # noqa: E402
import stationkeeping_efficiency as se               # noqa: E402
from test_alarm_pattern import TestPolicyGuards as _T8cGuards  # noqa: E402

SRC = (_REPO / "tools" / "manoeuvre_library.py").read_text()


def geo_burn(**over):
    """A near-GEO burn record on which no rule fires unless `over` makes one."""
    b = {
        "norad": 90001, "arm": "G", "epochMs": 1.0e12,
        "driftBeforeDegPerDay": 0.0, "driftAfterDegPerDay": 0.0,
        "deltaDriftDegPerDay": 0.0,
        "incBeforeDeg": 0.05, "incAfterDeg": 0.05, "deltaIncDeg": 0.0,
        "lambdaAfterDeg": 10.0,
        "aBeforeKm": pg.A_GEO_KM, "aAfterKm": pg.A_GEO_KM, "deltaAKm": 0.0,
        "perigeeAltBeforeKm": 35786.0,
        "insideStationSegment": False, "priorStationHeld": False,
        "channel": "drift", "previousInTrackDeltaASign": None,
        # v2 fields. The default record has a quiet net channel over a
        # one-day span, so a v2 rule fires only where `over` makes it.
        "baselineSpanDays": 2.0,
        "naturalSpanDays": 1.0, "deltaIncNetDeg": 0.0,
        "deltaIncNetJ2Deg": 0.0, "deltaIncNetMeasuredModelDeg": 0.0,
        "netFloorDeg": ml.net_floor_deg({"naturalSpanDays": 1.0}),
        "incPredictedDeg": 0.05, "incBaselinePoleDeg": 0.05,
        "raanBaselinePoleDeg": 90.0,
    }
    b.update(over)
    return b


def plane_burn(**over):
    b = {
        "norad": 90002, "arm": "P", "epochMs": 1.0e12,
        "driftBeforeDegPerDay": None, "driftAfterDegPerDay": None,
        "deltaDriftDegPerDay": None,
        "incBeforeDeg": 53.0, "incAfterDeg": 53.0, "deltaIncDeg": 0.0,
        "lambdaAfterDeg": None,
        "aBeforeKm": 6878.0, "aAfterKm": 6878.0, "deltaAKm": 0.0,
        "perigeeAltBeforeKm": 500.0,
        "insideStationSegment": False, "priorStationHeld": None,
        "channel": "intrack", "previousInTrackDeltaASign": None,
    }
    b.update(over)
    return b


# ==========================================================================
class TestRuleTableIsRegistered(unittest.TestCase):
    """Registration section 3: no threshold may appear that is not a
    registered floor, quoted with the file and symbol it came from."""

    def test_every_rule_threshold_is_a_registered_floor(self):
        for rule in ml.rule_table("v1"):
            for t in rule["thresholds"]:
                self.assertIn(t["name"], ml.FLOORS)
                self.assertEqual(t["value"], ml.FLOORS[t["name"]]["value"])
                self.assertTrue(t["source"].strip(),
                                f"{rule['id']} threshold {t['name']} has no source")

    def test_floor_values_equal_the_constants_the_other_tracks_registered(self):
        self.assertEqual(ml.BURN_FLOOR, pg.BURN_FLOOR_DEG_PER_DAY)
        self.assertEqual(ml.CO_LOCATION_DEG, pg.X_PRIMARY_DEG)
        self.assertEqual(ml.RELOCATION_BAR_DEG, pg.X_FAR_DEG)
        self.assertEqual(ml.MATCH_TOLERANCE_DAYS, pg.MAX_GAP_DAYS)
        self.assertEqual(ml.IN_TRACK_FLOOR_KM, pp.DA_FLOOR_KM)
        self.assertEqual(ml.PLANE_FLOOR_DEG, pp.I_FLOOR_DEG)
        self.assertEqual(ml.CAMPAIGN_GAP_DAYS, pp.CAMPAIGN_MAX_GAP_DAYS)

    def test_the_stationed_band_is_derived_not_typed_in(self):
        self.assertAlmostEqual(ml.STATIONED_BAND,
                               6.0 * pg.X_PRIMARY_DEG / pg.D_PRIMARY_DAYS, places=12)
        self.assertAlmostEqual(ml.STATIONED_BAND, 0.020, places=12)

    def test_the_inclination_bar_is_five_sigma_on_the_quantum_floored_sigma(self):
        self.assertAlmostEqual(ml.INC_BAR_DEG, 5.0 * 1.67e-4, places=12)
        self.assertGreater(ml.INC_BAR_DEG, 1e-4,
                           "the bar must sit above the publication quantum")

    def test_the_graveyard_and_decay_floors_match_the_pipeline(self):
        src = (_REPO / "pipeline" / "orbit_events.py").read_text()
        self.assertIn("GEO_GRAVEYARD_MINIMUM_RAISE_KM = 235.0", src)
        self.assertIn("TERMINAL_DECAY_PERIGEE_KM = 200.0", src)
        self.assertIn("GEO_SEMI_MAJOR_AXIS_KM = 42164.0", src)
        self.assertEqual(ml.GRAVEYARD_RAISE_KM, 235.0)
        self.assertEqual(ml.DECAY_PERIGEE_KM, 200.0)
        self.assertEqual(ml.GEO_A_KM, 42164.0)

    def test_no_bare_numeric_threshold_inside_a_rule_body(self):
        """A rule compares against a module constant, never a literal."""
        for name, fn in vars(ml).items():
            if not (name.startswith("_g_") or name.startswith("_p_")):
                continue
            body = inspect.getsource(fn)
            for literal in re.findall(r"[<>]=?\s*(-?\d+\.?\d*(?:e-?\d+)?)", body):
                self.assertIn(literal, ("0", "0.0"),
                              f"{name} compares against the literal {literal}")


class TestExactlyOneRule(unittest.TestCase):
    """Registration section 5."""

    def test_one_rule_fires_gives_that_type(self):
        b = geo_burn(driftBeforeDegPerDay=0.0, driftAfterDegPerDay=0.5,
                     deltaDriftDegPerDay=0.5)
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], "drift start")
        self.assertEqual(got["ruleId"], "G1")
        self.assertEqual(got["competingRules"], [])

    def test_no_rule_fires_gives_unlabelled_with_a_reason(self):
        got = ml.assign_type(geo_burn(), "v1")
        self.assertEqual(got["type"], ml.UNLABELLED)
        self.assertEqual(got["reason"], "no-rule")
        self.assertEqual(got["competingRules"], [])

    def test_two_rules_fire_gives_unlabelled_naming_both(self):
        """A stop whose drift barely crosses the band, with an inclination
        change: rule G2 and rule G5 both hold and neither wins."""
        b = geo_burn(driftBeforeDegPerDay=0.0201, driftAfterDegPerDay=0.0200,
                     deltaDriftDegPerDay=-0.0001,
                     deltaIncDeg=0.01, priorStationHeld=True)
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], ml.UNLABELLED)
        self.assertEqual(got["reason"], "multi-fire")
        self.assertEqual(sorted(got["competingRules"]), ["G2", "G5"])

    def test_no_tie_break_token_exists_in_the_source(self):
        for token in ("priority", "tie_break", "tiebreak", "first_match",
                      "fallback_type", "default_type"):
            self.assertNotIn(token, SRC.lower(),
                             f"a tie-break named {token!r} is present")


class TestSeededViolations(unittest.TestCase):
    """The cases in the module docstring: each was observed to FAIL before the
    instrument was changed, and to PASS after."""

    def test_seeded_graveyard_raise_is_not_unlabelled(self):
        a0 = pg.A_GEO_KM
        a1 = a0 + 300.0
        b = geo_burn(aBeforeKm=a0, aAfterKm=a1, deltaAKm=300.0,
                     driftBeforeDegPerDay=0.0,
                     driftAfterDegPerDay=pg.DRIFT_PER_KM * 300.0,
                     deltaDriftDegPerDay=pg.DRIFT_PER_KM * 300.0)
        self.assertTrue(abs(b["driftAfterDegPerDay"]) > ml.STATIONED_BAND,
                        "a 300 km raise is also a drift start -- the seed is real")
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], "graveyard raise")
        self.assertEqual(got["ruleId"], "G6")

    def test_seeded_decaying_burn_is_not_unlabelled(self):
        b = plane_burn(perigeeAltBeforeKm=150.0, deltaAKm=-5.0,
                       aAfterKm=6873.0, channel="intrack")
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], "decaying")
        self.assertEqual(got["ruleId"], "P1")

    def test_seeded_plane_and_in_track_burn_is_unlabelled(self):
        """Both channels fired. No rule may claim it."""
        b = plane_burn(channel="both", deltaIncDeg=4.0, deltaAKm=3.0,
                       aAfterKm=6881.0)
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], ml.UNLABELLED)
        self.assertEqual(got["reason"], "no-rule")

    def test_seeded_station_segment_after_the_burn_is_not_read(self):
        """A segment at the same longitude that STARTS after the burn must not
        make the burn a return. Reading it is reading the future."""
        s, base = _synthetic_geo_series()
        segs = pg.station_segments(s)
        self.assertTrue(segs, "the fixture must contain a station segment")
        burns = ml.geo_burns(s, 6.0385e-4, segs, base)
        self.assertTrue(burns, "the fixture must contain a detected burn")
        stops = [b for b in burns if abs(b["driftBeforeDegPerDay"]) > ml.STATIONED_BAND
                 and abs(b["driftAfterDegPerDay"]) <= ml.STATIONED_BAND]
        self.assertTrue(stops, "the fixture must contain a drift stop")
        self.assertFalse(stops[0]["priorStationHeld"],
                         "the only segment at this longitude begins after the burn")

    def test_seeded_station_segment_epochs_carry_the_grid_origin(self):
        """A station segment's grid offsets are relative to the daily grid's
        own origin. Dropping it puts every segment in 1970 and makes every
        stop a return."""
        s, base = _synthetic_geo_series()
        segs = pg.station_segments(s)
        i0, i1 = segs[0]
        start_ms = (base + s.grid_lo + i0) * pg.DAY_MS
        self.assertGreater(start_ms, float(s.epoch_ms[0]) - pg.DAY_MS)
        self.assertLess(start_ms, float(s.epoch_ms[-1]) + pg.DAY_MS)

    def test_seeded_rule_reading_a_catalogue_field_is_refused(self):
        for name, fn in vars(ml).items():
            if not (name.startswith("_g_") or name.startswith("_p_")):
                continue
            body = inspect.getsource(fn)
            for field in ("objectType", "country", "registry", "operator",
                          "name", "objectId", "launchDate"):
                self.assertNotIn(field, body,
                                 f"{field!r} unexpectedly found in {name}")


class TestCausality(unittest.TestCase):
    """Registration section 4: nothing reads an element set later than the burn
    it types."""

    def test_rules_read_only_the_registered_input_fields(self):
        allowed = set(ml.RULE_INPUT_FIELDS)
        for name, fn in vars(ml).items():
            if not (name.startswith("_g_") or name.startswith("_p_")
                    or name == "net_floor_deg"):
                continue
            body = inspect.getsource(fn)
            for key in re.findall(r'b(?:urn)?[\.\[]\(?"?([A-Za-z]+)"?', body):
                if key in ("get", "arm", "test", "rid"):
                    continue
                self.assertIn(key, allowed, f"{name} reads unregistered {key!r}")

    def test_episode_types_are_not_burn_types(self):
        burn_types = {r.type_name for r in ml.RULE_SETS["v1"]}
        for ep in ml.EPISODE_TYPES:
            self.assertNotIn(ep, burn_types)

    def test_an_episode_never_rewrites_a_burn_type(self):
        burns = [
            {"norad": 1, "epochMs": 0.0, "type": "drift start", "deltaAKm": 0.0},
            {"norad": 1, "epochMs": 40 * pg.DAY_MS, "type": "drift stop",
             "deltaAKm": 0.0},
        ]
        before = [b["type"] for b in burns]
        ml.relocation_episodes(burns, lambda t, before=True: 0.0 if before else 9.0)
        self.assertEqual([b["type"] for b in burns], before)


class TestOwnershipLine(unittest.TestCase):
    """Registration section 7.3 and design section 6."""

    def test_no_registry_field_in_the_rule_table(self):
        """Whole words: `inclination` contains `nation` and is a kinematic
        element, so a substring test here would forbid the physics."""
        blob = json.dumps(ml.rule_table("v1")).lower()
        for banned in ("country", "registry", "operator", "nation", "owner",
                       "objecttype", "launch", "flag state"):
            self.assertIsNone(re.search(r"\b" + re.escape(banned) + r"\b", blob),
                              f"{banned!r} present in the rule table")

    def test_the_only_catalogue_reader_is_a_control(self):
        self.assertIn("def control_class", SRC)
        self.assertIn("def load_object_types", SRC)
        for fn in ml.ALL_RULE_FUNCTIONS:
            body = inspect.getsource(fn)
            self.assertNotIn("control_class", body)
            self.assertNotIn("load_object_types", body)

    def test_the_object_metadata_loader_drops_every_field_but_the_type(self):
        body = inspect.getsource(ml.load_object_types)
        self.assertIn("objectType", body)
        for field in ("country", "objectId", "launchDate"):
            self.assertNotIn(f'"{field}"', body)
            self.assertNotIn(f"'{field}'", body)


class TestNoLearnedClassifierAndNoGaussian(unittest.TestCase):
    """Registration section 1 and design section 5 rules (1) and (4)."""

    def test_no_learning_machinery_is_imported_or_named(self):
        low = SRC.lower()
        for token in ("sklearn", "kmeans", "k-means", "logistic", "randomforest",
                      "gradientboost", "torch", "keras", ".fit(", "train(",
                      "classifier", "predict_proba", "scaler"):
            self.assertNotIn(token, low, f"learning machinery {token!r} present")

    def test_no_gaussian_tail_bound_in_any_rule(self):
        for name, fn in vars(ml).items():
            if not (name.startswith("_g_") or name.startswith("_p_")):
                continue
            body = inspect.getsource(fn).lower()
            for token in ("sigma", "norm.", "erf", "gauss", "z_score", "zscore"):
                self.assertNotIn(token, body, f"{name} uses {token!r}")

    def test_the_two_sigma_bars_are_inherited_constants_not_computed_here(self):
        """5 sigma_i is a registered constant of another track. It appears once,
        in FLOORS, with its source -- not as an arithmetic step in a rule."""
        self.assertEqual(SRC.count("5.0 * 1.67e-4"), 1)


class TestPolicyGuards(unittest.TestCase):
    """The framing rules of the alarm design section 7, enforced not intended.
    The banned list is IMPORTED from T8c's suite so the two cannot drift."""

    BANNED = _T8cGuards.BANNED

    def test_the_banned_list_is_the_same_object(self):
        self.assertIs(self.BANNED, _T8cGuards.BANNED)

    def test_no_intent_language_in_the_tool(self):
        low = SRC.lower()
        for banned in self.BANNED:
            self.assertNotIn(banned, low, f"intent language {banned!r} present")

    def test_no_intent_language_in_any_type_name(self):
        joined = " ".join(ml.type_names("v1") + ml.EPISODE_TYPES).lower()
        for banned in self.BANNED:
            self.assertNotIn(banned.strip(), joined)

    def test_type_names_are_kinematic(self):
        for t in ml.type_names("v1"):
            for banned in ("mission", "purpose", "intent", "task", "objective",
                           "manoeuvre to", "attack", "defen"):
                self.assertNotIn(banned, t.lower())

    def test_no_fuel_mass_or_delta_v_figure_anywhere(self):
        low = SRC.lower()
        for token in ("delta-v", "deltav", "delta_v", "propellant", "fuel",
                      "kilograms", "_mps", "mps\"", "metres per second"):
            self.assertNotIn(token, low, f"{token!r} present in a library that "
                                         "publishes element units only")

    def test_no_tool_or_model_name_strings(self):
        low = SRC.lower()
        self.assertEqual(vendor_names.hits(low), [],
                         "a product or assistant name is in the library")


class TestUnlabelledStays(unittest.TestCase):
    """Registration section 5."""

    def test_unlabelled_is_terminal_in_the_source(self):
        self.assertNotIn("relabel", SRC.lower())
        self.assertNotIn("retype", SRC.lower())
        self.assertNotIn("reassign", SRC.lower())

    def test_assign_type_is_deterministic(self):
        b = geo_burn(driftBeforeDegPerDay=0.0201, driftAfterDegPerDay=0.0200,
                     deltaDriftDegPerDay=-0.0001, deltaIncDeg=0.01,
                     priorStationHeld=True)
        first = ml.assign_type(dict(b), "v1")
        for _ in range(5):
            self.assertEqual(ml.assign_type(dict(b), "v1"), first)

    def test_competing_rules_are_named_in_table_order(self):
        b = geo_burn(driftBeforeDegPerDay=0.0201, driftAfterDegPerDay=0.0200,
                     deltaDriftDegPerDay=-0.0001, deltaIncDeg=0.01,
                     priorStationHeld=True)
        got = ml.assign_type(b, "v1")
        order = [r.rid for r in ml.RULE_SETS["v1"]]
        idxs = [order.index(r) for r in got["competingRules"]]
        self.assertEqual(idxs, sorted(idxs))


class TestChecksums(unittest.TestCase):
    """Registration section 7.2."""

    def test_rules_sha_is_stable_across_calls(self):
        self.assertEqual(ml.rules_sha256("v1"), ml.rules_sha256("v1"))
        self.assertEqual(len(ml.rules_sha256("v1")), 64)

    def test_moving_a_floor_changes_the_library_identity(self):
        before = ml.rules_sha256("v1")
        saved = ml.FLOORS["burnFloorDegPerDay"]["value"]
        try:
            ml.FLOORS["burnFloorDegPerDay"]["value"] = saved * 2
            self.assertNotEqual(ml.rules_sha256("v1"), before)
        finally:
            ml.FLOORS["burnFloorDegPerDay"]["value"] = saved
        self.assertEqual(ml.rules_sha256("v1"), before)

    def test_renaming_a_type_changes_the_library_identity(self):
        before = ml.rules_sha256("v1")
        rule = ml.RULES_BY_ID["v1"]["G1"]
        saved = rule.type_name
        try:
            rule.type_name = saved + " x"
            self.assertNotEqual(ml.rules_sha256("v1"), before)
        finally:
            rule.type_name = saved
        self.assertEqual(ml.rules_sha256("v1"), before)

    def test_the_artifact_checksum_excludes_itself(self):
        art = ml.build_artifact(ml.Tally(), {}, {}, 0.0, "v1")
        digest = art.pop("artifactSha256")
        self.assertEqual(digest,
                         __import__("hashlib").sha256(
                             ml.canonical_json(art)).hexdigest())


class TestMatching(unittest.TestCase):
    """Registration section 6.3: the tolerance is the registered 5.0 days and
    nothing else."""

    def setUp(self):
        self.idx = ml.LabelIndex()
        self.idx.add(7, "t8aArrival", 1.0e12)
        self.idx.freeze()

    def test_exactly_at_the_tolerance_matches(self):
        t = 1.0e12 + ml.MATCH_TOLERANCE_DAYS * pg.DAY_MS
        self.assertIsNotNone(self.idx.nearest(7, t))

    def test_just_past_the_tolerance_does_not(self):
        t = 1.0e12 + (ml.MATCH_TOLERANCE_DAYS + 1e-6) * pg.DAY_MS
        self.assertIsNone(self.idx.nearest(7, t))

    def test_a_different_object_never_matches(self):
        self.assertIsNone(self.idx.nearest(8, 1.0e12))

    def test_contested_matches_are_flagged_and_the_nearest_wins(self):
        idx = ml.LabelIndex()
        idx.add(7, "t8aArrival", 1.0e12)
        idx.add(7, "t8aInitiatingFlag", 1.0e12 + 2 * pg.DAY_MS)
        idx.freeze()
        cls, dist, contested = idx.nearest(7, 1.0e12 + 0.5 * pg.DAY_MS)
        self.assertEqual(cls, "t8aArrival")
        self.assertTrue(contested)

    def test_a_window_label_matches_inside_the_window(self):
        idx = ml.LabelIndex()
        idx.add(7, "t10bNorthSouth", 1.0e12, 1.0e12 + 10 * pg.DAY_MS)
        idx.freeze()
        cls, dist, _ = idx.nearest(7, 1.0e12 + 5 * pg.DAY_MS)
        self.assertEqual(cls, "t10bNorthSouth")
        self.assertEqual(dist, 0.0)


class TestEpisodes(unittest.TestCase):
    """Registration section 4.3."""

    def test_relocation_needs_the_registered_two_degrees(self):
        burns = [{"norad": 1, "epochMs": 0.0, "type": "drift start"},
                 {"norad": 1, "epochMs": 50 * pg.DAY_MS, "type": "drift stop"}]
        near = ml.relocation_episodes(
            burns, lambda t, before: 0.0 if before else 1.9)
        self.assertEqual(near, [])
        far = ml.relocation_episodes(
            burns, lambda t, before: 0.0 if before else 2.1)
        self.assertEqual(len(far), 1)
        self.assertAlmostEqual(far[0]["netChangeDeg"], 2.1, places=9)

    def test_a_transfer_leg_run_needs_two_burns_in_the_same_direction(self):
        one = [{"norad": 1, "epochMs": 0.0, "type": "orbit raise", "deltaAKm": 5.0}]
        self.assertEqual(ml.transfer_leg_runs(one), [])
        two = one + [{"norad": 1, "epochMs": 10 * pg.DAY_MS,
                      "type": "orbit raise", "deltaAKm": 5.0}]
        got = ml.transfer_leg_runs(two)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["burns"], 2)
        self.assertAlmostEqual(got[0]["cumulativeDeltaAKm"], 10.0)

    def test_a_gap_longer_than_the_campaign_window_breaks_the_run(self):
        burns = [{"norad": 1, "epochMs": 0.0, "type": "orbit raise", "deltaAKm": 5.0},
                 {"norad": 1, "epochMs": 200 * pg.DAY_MS, "type": "orbit raise",
                  "deltaAKm": 5.0}]
        self.assertEqual(ml.transfer_leg_runs(burns), [])

    def test_a_phasing_burn_breaks_the_run(self):
        burns = [{"norad": 1, "epochMs": 0.0, "type": "orbit raise", "deltaAKm": 5.0},
                 {"norad": 1, "epochMs": 5 * pg.DAY_MS, "type": "phasing",
                  "deltaAKm": -5.0},
                 {"norad": 1, "epochMs": 10 * pg.DAY_MS, "type": "orbit raise",
                  "deltaAKm": 5.0}]
        self.assertEqual(ml.transfer_leg_runs(burns), [])


class TestArmPRules(unittest.TestCase):
    """Registration section 4.2."""

    def test_phasing_needs_the_previous_flag_to_reverse(self):
        same = plane_burn(deltaAKm=1.0, aAfterKm=6879.0,
                          previousInTrackDeltaASign=1)
        self.assertEqual(ml.assign_type(same, "v1")["type"], "orbit raise")
        rev = plane_burn(deltaAKm=1.0, aAfterKm=6879.0,
                         previousInTrackDeltaASign=-1)
        self.assertEqual(ml.assign_type(rev, "v1")["type"], "phasing")

    def test_a_first_flag_with_no_predecessor_is_a_raise_or_a_lower(self):
        up = plane_burn(deltaAKm=1.0, aAfterKm=6879.0)
        self.assertEqual(ml.assign_type(up, "v1")["type"], "orbit raise")
        down = plane_burn(deltaAKm=-1.0, aAfterKm=6877.0)
        self.assertEqual(ml.assign_type(down, "v1")["type"], "orbit lower")

    def test_a_change_below_the_in_track_floor_is_unlabelled(self):
        b = plane_burn(deltaAKm=0.049, aAfterKm=6878.049)
        self.assertEqual(ml.assign_type(b, "v1")["type"], ml.UNLABELLED)

    def test_inclination_adjust_needs_the_in_track_channel_quiet(self):
        good = plane_burn(channel="plane", deltaIncDeg=4.0, deltaAKm=0.01)
        self.assertEqual(ml.assign_type(good, "v1")["type"], "inclination adjust")
        noisy = plane_burn(channel="plane", deltaIncDeg=4.0, deltaAKm=1.0)
        self.assertEqual(ml.assign_type(noisy, "v1")["type"], ml.UNLABELLED)


class TestArmGRules(unittest.TestCase):
    """Registration section 4.1."""

    def test_drift_stop_and_station_acquisition_partition_every_stop(self):
        stop = dict(driftBeforeDegPerDay=0.5, driftAfterDegPerDay=0.001,
                    deltaDriftDegPerDay=-0.499)
        held = ml.assign_type(geo_burn(priorStationHeld=True, **stop), "v1")
        new = ml.assign_type(geo_burn(priorStationHeld=False, **stop), "v1")
        self.assertEqual(held["type"], "drift stop")
        self.assertEqual(new["type"], "station acquisition")

    def test_east_west_keeping_requires_a_station_segment(self):
        inside = geo_burn(deltaDriftDegPerDay=0.024,
                          driftBeforeDegPerDay=-0.012,
                          driftAfterDegPerDay=0.012,
                          insideStationSegment=True)
        self.assertEqual(ml.assign_type(inside, "v1")["type"], "east-west keeping")
        outside = dict(inside, insideStationSegment=False)
        self.assertEqual(ml.assign_type(outside, "v1")["type"], ml.UNLABELLED)

    def test_north_south_keeping_requires_the_drift_channel_quiet(self):
        quiet = geo_burn(deltaIncDeg=0.002, deltaDriftDegPerDay=0.0001)
        self.assertEqual(ml.assign_type(quiet, "v1")["type"], "north-south keeping")
        loud = geo_burn(deltaIncDeg=0.002, deltaDriftDegPerDay=0.5,
                        driftAfterDegPerDay=0.5)
        self.assertEqual(ml.assign_type(loud, "v1")["type"], ml.UNLABELLED)

    def test_a_drift_start_with_an_inclination_change_is_unlabelled(self):
        b = geo_burn(deltaDriftDegPerDay=0.5, driftAfterDegPerDay=0.5,
                     deltaIncDeg=0.01)
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], ml.UNLABELLED)
        self.assertEqual(got["reason"], "no-rule")

    def test_the_arm_g_rules_are_a_partition_over_a_swept_grid(self):
        """A sweep across the floors: no burn may fire two stage-1 arm-G rules
        except the registered G2/G5 and G3/G5 overlap, which is reported as
        multi-fire and never assigned."""
        multi = 0
        total = 0
        for d_before in (0.0, 0.005, 0.02, 0.0201, 0.5):
            for d_after in (0.0, 0.005, 0.02, 0.0201, 0.5):
                for d_inc in (0.0, 8.0e-4, 8.4e-4, 0.01):
                    for inside in (False, True):
                        for held in (False, True):
                            b = geo_burn(
                                driftBeforeDegPerDay=d_before,
                                driftAfterDegPerDay=d_after,
                                deltaDriftDegPerDay=d_after - d_before,
                                deltaIncDeg=d_inc,
                                insideStationSegment=inside,
                                priorStationHeld=held)
                            got = ml.assign_type(b, "v1")
                            total += 1
                            if got["reason"] == "multi-fire":
                                multi += 1
                                self.assertEqual(
                                    sorted(got["competingRules"])[1], "G5",
                                    "the only registered overlap is with G5")
        self.assertGreater(total, 0)
        self.assertLess(multi / total, 0.25)


class TestArtifactAndGates(unittest.TestCase):
    """Registration sections 7 and 8."""

    def test_the_artifact_carries_the_agreement_disclaimer(self):
        art = ml.build_artifact(ml.Tally(), {}, {}, 0.0, "v1")
        self.assertIn("not accuracy", art["note"])
        self.assertIn("not ground truth", art["note"])
        self.assertIn("screen, not a law", art["note"])

    def test_forbidden_vocabulary_is_absent_from_the_artifact(self):
        art = ml.build_artifact(ml.Tally(), {}, {}, 0.0, "v1")
        disclaimer = art.pop("note").lower()
        blob = json.dumps(art).lower()
        for banned in ("accuracy", "correctly", "validated", "ground truth",
                       "detection rate", "true positive"):
            self.assertNotIn(banned, blob,
                             f"{banned!r} outside the disclaimer")
        # the disclaimer is the one place the words may appear, to deny them
        self.assertIn("not accuracy", disclaimer)
        self.assertIn("not ground truth", disclaimer)

    def test_underpowered_types_get_no_confidence(self):
        got = ml.per_type_precision(
            {"drift start": {"t8aInitiatingFlag": 5}}, "v1")
        self.assertTrue(got["drift start"]["underpowered"])
        self.assertEqual(got["drift start"]["matched"], 5)

    def test_gate_f_fires_when_the_wrong_label_dominates(self):
        got = ml.per_type_precision(
            {"drift start": {"t8aInitiatingFlag": 5, "t10bNorthSouth": 40}},
            "v1")
        self.assertTrue(got["drift start"]["gateF"])

    def test_wilson_interval_brackets_the_point_estimate(self):
        lo, hi = ml.wilson(30, 100)
        self.assertLess(lo, 0.30)
        self.assertGreater(hi, 0.30)
        self.assertGreater(lo, 0.0)
        self.assertLess(hi, 1.0)

    def test_the_library_version_is_carried(self):
        art = ml.build_artifact(ml.Tally(), {}, {}, 0.0, "v1")
        self.assertEqual(art["libraryVersion"], "v1")
        self.assertEqual(art["registration"], ml.REGISTRATIONS["v1"])


class TestObjectLevelAndExternalArms(unittest.TestCase):
    """Registration sections 6.1 and 6.2."""

    def test_an_object_level_expected_class_is_a_gap_not_a_zero(self):
        got = ml.per_type_precision(
            {"east-west keeping": {"t10bNorthSouth": 40}},
            "v1")["east-west keeping"]
        self.assertIn(got["expectedLabelClass"], ml.OBJECT_LEVEL_LABEL_CLASSES)
        self.assertIsNone(got["forwardAgreement"])
        self.assertIsNone(got["wilson95"])
        self.assertFalse(got["gateF"],
                         "a gap may not fire a falsification gate")
        self.assertIn("labelled gap", got["note"])

    def test_a_burn_level_expected_class_still_scores(self):
        got = ml.per_type_precision(
            {"drift start": {"t8aInitiatingFlag": 30, "t8aArrival": 10}},
            "v1")
        self.assertAlmostEqual(got["drift start"]["forwardAgreement"], 0.75)

    def test_the_external_events_are_read_and_counted_honestly(self):
        """The registration section 6.1 says twelve objects. It is wrong: the
        file holds 34 events over TEN distinct NORADs. The count is asserted
        here at its true value and the results document carries the erratum,
        because a registration is corrected in the open, never quietly."""
        events = ml.external_events()
        self.assertEqual(len(events), 34)
        self.assertEqual(len({e["norad"] for e in events}), 10)
        for e in events:
            self.assertIsNotNone(e["epochMs"])
        self.assertNotIn(25544 - 25544, {e["norad"] for e in events})

    def test_the_external_check_is_a_listed_table_and_not_a_precision(self):
        events = [{"norad": 5, "epochMs": 1.0e12, "publishedKind": "reboost",
                   "dateExactness": "day"}]
        rows = ml.external_check(events, {5: [(1.0e12 + pg.DAY_MS, "orbit raise")]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nearestType"], "orbit raise")
        self.assertAlmostEqual(rows[0]["nearestOffsetDays"], 1.0)
        for key in rows[0]:
            self.assertNotIn("precision", key.lower())
            self.assertNotIn("accuracy", key.lower())

    def test_a_published_kind_never_becomes_a_type(self):
        kinds = {e["publishedKind"] for e in ml.external_events()}
        for k in kinds:
            self.assertNotIn(k, ml.type_names("v1"))


class TestDeltasAreTheDetectorsOwnStatistic(unittest.TestCase):
    """Both burn builders must measure the quantity that was DETECTED. The
    registered detectors flag the second confirming element set against a
    trailing fit, so a one-step difference across a flag measures something
    else and comes out near zero on a real step."""

    def test_arm_g_uses_the_trailing_baseline_not_the_previous_set(self):
        body = inspect.getsource(ml.geo_burns)
        self.assertIn("trailing_baseline", body)
        self.assertNotIn("series.drift[k - 1]", body)

    def test_arm_p_uses_the_rolling_fit_residual_not_the_previous_set(self):
        body = inspect.getsource(ml.plane_burns)
        self.assertIn("rolling_theil_sen_residual", body)
        self.assertNotIn("a[j] - a[j - 1]", body)

    def test_the_trailing_baseline_matches_the_detector_definition(self):
        rng = np.random.default_rng(20260922)
        v = rng.normal(size=60)
        base = ml.trailing_baseline(v)
        w = pg.BURN_BASELINE_SAMPLES
        for i in (w, 20, 40, 59):
            self.assertAlmostEqual(base[i], float(np.median(v[i - w:i])),
                                   places=12)
        self.assertTrue(np.all(np.isnan(base[:w])))

    def test_a_step_is_visible_to_the_baseline_and_invisible_to_a_difference(self):
        v = np.concatenate((np.full(20, 0.3), np.full(20, 0.0)))
        base = ml.trailing_baseline(v)
        k = 21
        self.assertAlmostEqual(v[k] - v[k - 1], 0.0, places=12)
        self.assertAlmostEqual(v[k] - base[k - 1], -0.3, places=12)

    def test_the_semi_major_axis_conversion_is_keplers_third_law(self):
        n0 = 15.2
        a0 = pp.semi_major_axis_km(n0)
        dn = 1e-6
        exact = pp.semi_major_axis_km(n0 + dn) - a0
        linear = -(2.0 * a0 / (3.0 * n0)) * dn
        self.assertAlmostEqual(exact / linear, 1.0, places=5)


class TestNoRuleBreakdownIsDescriptive(unittest.TestCase):
    def test_the_breakdown_assigns_nothing(self):
        b = geo_burn(deltaDriftDegPerDay=0.5, driftAfterDegPerDay=0.5,
                     deltaIncDeg=0.01)
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], ml.UNLABELLED)
        self.assertEqual(ml.no_rule_reason(b, "v1"), "G:both-channels-moved")
        self.assertEqual(ml.assign_type(b, "v1")["type"], ml.UNLABELLED)

    def test_every_breakdown_key_names_an_arm(self):
        for b in (geo_burn(), plane_burn(), plane_burn(channel="both"),
                  plane_burn(channel="plane"),
                  geo_burn(deltaDriftDegPerDay=0.5, driftAfterDegPerDay=0.5,
                           deltaIncDeg=0.01)):
            self.assertRegex(ml.no_rule_reason(b, "v1"), r"^[GP]:")


class TestExactSemiMajorAxis(unittest.TestCase):
    """Section 3: a rule reads `a`, so `a` is Kepler's third law and not the
    linearised interpretive offset whose own docstring forbids that use."""

    def test_a_at_zero_drift_is_the_geostationary_radius(self):
        self.assertAlmostEqual(ml._a_from_drift_km(0.0), pg.A_GEO_KM, places=6)

    def test_the_linearised_offset_is_not_used_in_the_burn_builder(self):
        body = inspect.getsource(ml.geo_burns)
        self.assertNotIn("semi_major_offset_km", body)

    def test_the_exact_form_and_the_linear_form_disagree_at_the_graveyard_bar(self):
        drift = ml.GRAVEYARD_RAISE_KM * pg.DRIFT_PER_KM
        exact = ml._a_from_drift_km(drift) - pg.A_GEO_KM
        linear = float(pg.semi_major_offset_km(drift))
        self.assertGreater(abs(exact - linear), 0.5,
                           "the two forms differ by more than half a kilometre "
                           "at the graveyard bar, so which one a rule reads "
                           "changes the answer")


class TestNothingIsScheduledOrPublished(unittest.TestCase):
    def test_no_timer_cron_or_network_call(self):
        low = SRC.lower()
        for token in ("crontab", "systemd", "schedule", "requests.",
                      "urllib", "http://", "https://", "subprocess"):
            self.assertNotIn(token, low, f"{token!r} present")


# --------------------------------------------------------------------------
def _synthetic_geo_series():
    """A near-GEO object that drifts east for 200 days, stops, and only THEN
    holds a station: the fixture for the causality seed. Daily element sets.

    lambda = RAAN + argp + M - theta_G, so with RAAN = argp = 0 the mean
    anomaly carries the longitude we mean, and the mean motion carries the
    drift through ddot = 360 n - omega_E.
    """
    day = pg.DAY_MS
    n = 420
    epoch = np.arange(n, dtype=np.float64) * day + 1.0e12
    drift = np.full(n, 0.30)
    drift[200:] = 0.0
    lam = np.empty(n)
    lam[0] = 0.0
    for k in range(1, n):
        lam[k] = lam[k - 1] + drift[k - 1]
    mean_motion = (drift + pg.OMEGA_E_DEG_PER_DAY) / 360.0
    ma = np.asarray(lam + pg.gmst_deg(epoch), dtype=np.float64)
    ecc = np.full(n, 1e-4)
    inc = np.full(n, 0.05)
    zeros = np.zeros(n)
    s = pg.Series(90003, epoch, mean_motion, ecc, inc, zeros, zeros, ma)
    base, _ = pg.build_daily_grid([s])
    return s, base


# ==========================================================================
# v2 -- docs/manoeuvre-library-v2-preregistration-20260922.md
# ==========================================================================
def _natural_only_geo_burn(span_days=18.0, inc_base=0.05, raan_base=90.0,
                           **over):
    """A near-GEO burn whose ENTIRE inclination change is the natural motion.

    Nothing moved the plane. The drift changed, and it changed enough to
    satisfy rule G1's three drift clauses. The inclination after the burn is
    exactly what the committed propagator says the plane would have reached on
    its own over the burn's own span, so the NET change is zero by
    construction and the RAW change is whatever eighteen days of luni-solar
    torque does to a geostationary plane.
    """
    inc_pred = ml._natural_prediction(inc_base, raan_base, pg.A_GEO_KM, 1e-4,
                                      span_days)
    b = geo_burn(driftBeforeDegPerDay=0.0, driftAfterDegPerDay=0.5,
                 deltaDriftDegPerDay=0.5,
                 incBeforeDeg=inc_base, incAfterDeg=inc_pred,
                 deltaIncDeg=inc_pred - inc_base,
                 incBaselinePoleDeg=inc_base, raanBaselinePoleDeg=raan_base,
                 naturalSpanDays=span_days, incPredictedDeg=inc_pred,
                 deltaIncNetDeg=inc_pred - inc_pred)
    b.update(over)
    return b


class TestV2AssertsTheBugFirst(unittest.TestCase):
    """v2 registration section 9 step 2. The seeded burn below was observed
    UNLABELLED under v1 and `drift start` under v2, on the same record, in the
    same run -- both states asserted here so neither can be lost."""

    def test_the_seeded_burn_really_is_all_natural_motion(self):
        """The fixture is only a fixture if the plane genuinely did not move."""
        b = _natural_only_geo_burn()
        self.assertAlmostEqual(b["deltaIncNetDeg"], 0.0, places=12)
        self.assertGreater(abs(b["deltaIncDeg"]), ml.INC_BAR_DEG,
                           "the fixture must clear v1's bar, or it tests nothing")
        # and the raw change must not exceed what the repository's own bound
        # says luni-solar gravity can do over this span, or the fixture is
        # asserting physics the programme has not registered.
        bound = (2.0 * math.pi / 53.0) * (abs(b["incBeforeDeg"]) + 7.44) \
            * b["naturalSpanDays"] / 365.25
        self.assertLess(abs(b["deltaIncDeg"]), bound)

    def test_v1_leaves_it_unlabelled_because_both_channels_moved(self):
        b = _natural_only_geo_burn()
        got = ml.assign_type(b, "v1")
        self.assertEqual(got["type"], ml.UNLABELLED)
        self.assertEqual(got["reason"], "no-rule")
        self.assertEqual(ml.no_rule_reason(b, "v1"), "G:both-channels-moved")

    def test_v2_labels_the_same_record_drift_start(self):
        b = _natural_only_geo_burn()
        got = ml.assign_type(b, "v2")
        self.assertEqual(got["type"], "drift start")
        self.assertEqual(got["ruleId"], "G1")
        self.assertEqual(got["competingRules"], [])

    def test_the_two_versions_disagree_on_one_record_in_one_run(self):
        b = _natural_only_geo_burn()
        self.assertNotEqual(ml.assign_type(dict(b), "v1")["type"],
                            ml.assign_type(dict(b), "v2")["type"])

    def test_a_real_plane_change_stays_north_south_keeping_under_v2(self):
        """The change must not label everything: a burn that moved the plane
        by more than the natural motion, with a quiet drift, is still G5."""
        b = _natural_only_geo_burn(driftBeforeDegPerDay=0.0,
                                   driftAfterDegPerDay=0.0,
                                   deltaDriftDegPerDay=0.0)
        floor = ml.net_floor_deg(b)
        b["incAfterDeg"] = b["incPredictedDeg"] + 10.0 * floor
        b["deltaIncNetDeg"] = 10.0 * floor
        b["deltaIncDeg"] = b["incAfterDeg"] - b["incBeforeDeg"]
        self.assertEqual(ml.assign_type(b, "v2")["type"], "north-south keeping")

    def test_a_net_change_just_under_the_floor_is_not_north_south_keeping(self):
        b = _natural_only_geo_burn(driftBeforeDegPerDay=0.0,
                                   driftAfterDegPerDay=0.0,
                                   deltaDriftDegPerDay=0.0)
        floor = ml.net_floor_deg(b)
        b["deltaIncNetDeg"] = floor * (1.0 - 1e-9)
        self.assertEqual(ml.assign_type(b, "v2")["type"], ml.UNLABELLED)
        b["deltaIncNetDeg"] = floor
        self.assertEqual(ml.assign_type(b, "v2")["type"], "north-south keeping")


class TestV2FloorIsDerivedNotPicked(unittest.TestCase):
    """v2 registration section 3."""

    RECEIPT = json.loads(
        (_REPO / "docs" / "stationkeeping-efficiency-20260922-receipt.json"
         ).read_text())

    def test_the_pole_residual_is_the_committed_measured_field(self):
        self.assertEqual(ml.POLE_RESIDUAL_DEG,
                         self.RECEIPT["poleNoiseFloor"]["sigmaPoleDeg"])
        self.assertEqual(self.RECEIPT["poleNoiseFloor"]["quietArcs"], 948942)

    def test_the_rate_error_is_the_committed_model_minus_calibration_gap(self):
        cal = self.RECEIPT["laplaceCalibrationUnregistered"]
        self.assertEqual(ml.CALIBRATED_POLE_SPEED_DEG_PER_YEAR,
                         cal["poleSpeedDegPerYear"]["median"])
        self.assertAlmostEqual(ml.MODEL_POLE_SPEED_DEG_PER_YEAR,
                               cal["modelPoleSpeedDegPerYear"], places=15)
        self.assertAlmostEqual(
            ml.RATE_ERROR_DEG_PER_DAY,
            abs(cal["modelPoleSpeedDegPerYear"]
                - cal["poleSpeedDegPerYear"]["median"]) / 365.25, places=18)

    def test_the_sense_of_the_circuit_is_the_measured_one(self):
        self.assertEqual(se.LAPLACE_SENSE, -1.0)
        self.assertTrue(
            self.RECEIPT["laplaceCalibrationUnregistered"]["allRetrograde"])

    def test_no_multiple_is_applied_to_either_term(self):
        """A kappa would be a pick. The floor at zero span IS the residual."""
        self.assertEqual(ml.net_floor_deg({"naturalSpanDays": 0.0}),
                         ml.POLE_RESIDUAL_DEG)

    def test_the_floor_grows_with_the_span_and_is_the_quadrature_sum(self):
        for dt in (0.5, 4.27, 18.04, 60.87):
            self.assertAlmostEqual(
                ml.net_floor_deg({"naturalSpanDays": dt}),
                math.sqrt(ml.POLE_RESIDUAL_DEG ** 2
                          + (ml.RATE_ERROR_DEG_PER_DAY * dt) ** 2), places=15)
        spans = [0.0, 1.0, 10.0, 100.0]
        floors = [ml.net_floor_deg({"naturalSpanDays": d}) for d in spans]
        self.assertEqual(floors, sorted(floors))

    def test_a_burn_with_no_span_gets_no_floor_and_no_type(self):
        self.assertIsNone(ml.net_floor_deg({"naturalSpanDays": None}))
        self.assertIsNone(ml.net_floor_deg({"naturalSpanDays": float("nan")}))
        b = _natural_only_geo_burn()
        b["naturalSpanDays"] = float("nan")
        self.assertEqual(ml.assign_type(b, "v2")["type"], ml.UNLABELLED)

    def test_the_clause_string_carries_the_constants_it_compares_against(self):
        for rid in ("G1", "G4", "G5"):
            blob = " ".join(ml.RULES_BY_ID["v2"][rid].clauses)
            self.assertIn(repr(ml.POLE_RESIDUAL_DEG), blob)
            self.assertIn(repr(ml.RATE_ERROR_DEG_PER_DAY), blob)

    def test_moving_either_net_constant_changes_the_library_identity(self):
        before = ml.rules_sha256("v2")
        for name in ("netPoleResidualDeg", "netRateErrorDegPerDay"):
            saved = ml.FLOORS[name]["value"]
            try:
                ml.FLOORS[name]["value"] = saved * 2.0
                self.assertNotEqual(ml.rules_sha256("v2"), before)
            finally:
                ml.FLOORS[name]["value"] = saved
        self.assertEqual(ml.rules_sha256("v2"), before)


class TestV2NaturalMotionPrediction(unittest.TestCase):
    """v2 registration section 2."""

    def test_the_prediction_is_the_committed_propagator_not_a_copy(self):
        src = inspect.getsource(ml._natural_prediction)
        self.assertIn("se.propagate_natural", src)

    def test_j2_is_not_added_on_top_in_the_primary_path(self):
        """The 7.4 deg tilt already balances the oblateness against the
        luni-solar torque, so the primary applies the rotation alone and the
        J2 variant is a companion no rule reads."""
        self.assertIs(
            inspect.signature(ml._natural_prediction)
            .parameters["include_j2"].default, False)
        for fn in ml.ALL_RULE_FUNCTIONS:
            self.assertNotIn("include_j2", inspect.getsource(fn))
        self.assertNotIn("deltaIncNetJ2Deg", " ".join(ml.RULE_INPUT_FIELDS))

    def test_the_sensitivity_form_reduces_to_the_committed_one(self):
        """The sensitivity arm changes CONSTANTS, not the model. At the
        committed constants the two forms must agree to machine precision."""
        for inc0, raan0, span in ((0.05, 90.0, 18.0), (2.0, 200.0, 5.0),
                                  (12.0, 15.0, 60.0)):
            a = ml._natural_prediction(inc0, raan0, pg.A_GEO_KM, 1e-4, span)
            b = ml._natural_prediction_at(
                inc0, raan0, span, se.LAPLACE_TILT_DEG,
                se.LAPLACE_PRECESSION_PERIOD_YR)
            self.assertAlmostEqual(a, b, places=12)

    def test_an_equatorial_plane_walks_toward_the_measured_node(self):
        """The measured sense is retrograde: an initially equatorial GEO plane
        must head toward RAAN ~90 deg, not 270. A prograde propagator would
        send the fixture the other way and every net change would be wrong."""
        p = se.pole_vector(1e-6, 0.0)
        w = se.natural_rate_vector(pg.A_GEO_KM, 1e-4, 1e-6)
        moved = se.rotate_about(p, w, math.sqrt(sum(c * c for c in w)) * 365.25)
        _, raan = se.pole_to_elements(moved)
        self.assertLess(abs(raan - 90.0), 20.0)

    def test_the_pole_baseline_is_a_unit_vector_and_is_causal(self):
        n = 60
        inc = np.linspace(0.05, 0.09, n)
        raan = (np.linspace(80.0, 100.0, n)) % 360.0
        ep = np.arange(n, dtype=np.float64) * pg.DAY_MS
        bi, br, be = ml.trailing_median_pole(inc, raan, ep)
        w = pg.BURN_BASELINE_SAMPLES
        self.assertTrue(np.all(np.isnan(bi[:w])), "a short window has no baseline")
        k = 40
        self.assertLess(be[k], ep[k], "the baseline epoch precedes the sample")
        self.assertGreaterEqual(be[k], ep[k - w - 1])
        self.assertAlmostEqual(bi[k], float(np.median(inc[k - w:k])), places=6)
        self.assertAlmostEqual(be[k], float(np.median(ep[k - w:k])), places=6)

    def test_a_componentwise_median_is_renormalised(self):
        n = 40
        inc = np.full(n, 5.0)
        raan = np.tile([0.0, 90.0], n // 2)
        ep = np.arange(n, dtype=np.float64) * pg.DAY_MS
        bi, br, _ = ml.trailing_median_pole(inc, raan, ep)
        k = 30
        p = se.pole_vector(float(bi[k]), float(br[k]))
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in p)), 1.0, places=12)

    def test_the_burn_builder_emits_the_net_fields_over_a_seeded_series(self):
        s, base = _synthetic_geo_series()
        burns = ml.geo_burns(s, 6.0385e-4, pg.station_segments(s), base)
        self.assertTrue(burns)
        b = burns[0]
        for k in ("naturalSpanDays", "incPredictedDeg", "deltaIncNetDeg",
                  "netFloorDeg", "deltaIncNetJ2Deg",
                  "deltaIncNetMeasuredModelDeg", "incBaselinePoleDeg",
                  "raanBaselinePoleDeg"):
            self.assertIn(k, b)
            self.assertTrue(np.isfinite(b[k]), f"{k} is not finite")
        self.assertGreater(b["naturalSpanDays"], 0.0)
        self.assertLess(b["naturalSpanDays"], b["baselineSpanDays"],
                        "the natural span runs from the window's median epoch")
        self.assertAlmostEqual(b["netFloorDeg"], ml.net_floor_deg(b), places=15)
        self.assertAlmostEqual(
            b["deltaIncNetDeg"], b["incAfterDeg"] - b["incPredictedDeg"],
            places=12)
        self.assertNotAlmostEqual(b["deltaIncNetDeg"], b["deltaIncDeg"],
                                  places=6,
                                  msg="the prediction removed nothing")

    def test_the_baseline_pole_tracks_the_baseline_inclination(self):
        s, base = _synthetic_geo_series()
        burns = ml.geo_burns(s, 6.0385e-4, pg.station_segments(s), base)
        for b in burns:
            self.assertAlmostEqual(b["incBaselinePoleDeg"], b["incBeforeDeg"],
                                   places=6)


class TestV2ChangesExactlyOneThing(unittest.TestCase):
    """v2 registration section 5: asserted, not claimed."""

    def test_every_other_rule_is_byte_identical_to_v1(self):
        h1 = ml.per_rule_sha256("v1")
        h2 = ml.per_rule_sha256("v2")
        for rid in ml.V2_UNCHANGED_RULE_IDS:
            self.assertEqual(h1[rid], h2[rid], f"{rid} is not byte-identical")
            self.assertIs(ml.RULES_BY_ID["v1"][rid], ml.RULES_BY_ID["v2"][rid])

    def test_every_changed_rule_has_a_different_hash(self):
        h1 = ml.per_rule_sha256("v1")
        h2 = ml.per_rule_sha256("v2")
        for rid in ml.V2_CHANGED_RULE_IDS:
            self.assertNotEqual(h1[rid], h2[rid],
                                f"{rid} changed without changing its identity")

    def test_the_two_halves_cover_every_rule_exactly_once(self):
        named = set(ml.V2_CHANGED_RULE_IDS) | set(ml.V2_UNCHANGED_RULE_IDS)
        self.assertEqual(named, set(ml.RULES_BY_ID["v1"]))
        self.assertEqual(len(ml.V2_CHANGED_RULE_IDS)
                         + len(ml.V2_UNCHANGED_RULE_IDS), len(named))

    def test_the_type_set_is_unchanged(self):
        self.assertEqual(ml.type_names("v1"), ml.type_names("v2"))

    def test_arm_p_is_untouched_rule_for_rule(self):
        for rid in ("P1", "P2", "P3", "P4", "P5"):
            self.assertIs(ml.RULES_BY_ID["v1"][rid].test,
                          ml.RULES_BY_ID["v2"][rid].test)

    def test_no_arm_p_rule_reads_a_net_constant(self):
        for r in ml.RULE_SETS["v2"]:
            if r.arm != "P":
                continue
            self.assertNotIn("netPoleResidualDeg", r.thresholds)
            self.assertNotIn("netRateErrorDegPerDay", r.thresholds)

    def test_an_arm_p_burn_types_identically_under_both_versions(self):
        for b in (plane_burn(deltaAKm=1.0), plane_burn(deltaAKm=-1.0),
                  plane_burn(channel="plane", deltaIncDeg=5.0),
                  plane_burn(channel="both", deltaAKm=1.0, deltaIncDeg=5.0),
                  plane_burn(perigeeAltBeforeKm=150.0)):
            self.assertEqual(ml.assign_type(dict(b), "v1"),
                             ml.assign_type(dict(b), "v2"))

    def test_the_partition_still_holds_by_construction(self):
        """G5 requires a quiet drift; G1 and G4 require a moved one. Whatever
        the inclination clause says, the three cannot co-fire."""
        b = _natural_only_geo_burn()
        for d in (0.0, 0.005, 0.0099999, 0.01, 0.5):
            b["deltaDriftDegPerDay"] = d
            b["deltaIncNetDeg"] = 1.0
            fired = set(ml.fired_rules(b, "v2", stage=1))
            self.assertFalse({"G1", "G5"} <= fired)
            self.assertFalse({"G4", "G5"} <= fired)
            self.assertFalse({"G1", "G4"} <= fired)


class TestV2DiscriminationsAssignNothing(unittest.TestCase):
    """v2 registration section 6.3. They are diagnostics ON the rule set."""

    def test_the_variant_types_come_off_the_same_record(self):
        b = _natural_only_geo_burn()
        b["deltaIncNetJ2Deg"] = b["deltaIncNetDeg"]
        b["deltaIncNetMeasuredModelDeg"] = b["deltaIncNetDeg"]
        d = ml._discriminations(b)
        self.assertEqual(d["typeUnderV1"], ml.UNLABELLED)
        self.assertEqual(set(d["typeUnderVariant"]),
                         set(ml.PREDICTION_VARIANTS))
        for t in d["typeUnderVariant"].values():
            self.assertEqual(t, "drift start")

    def test_a_variant_that_disagrees_is_visible(self):
        b = _natural_only_geo_burn()
        b["deltaIncNetJ2Deg"] = 1.0
        b["deltaIncNetMeasuredModelDeg"] = b["deltaIncNetDeg"]
        d = ml._discriminations(b)
        self.assertEqual(d["typeUnderVariant"]["asRegistered"], "drift start")
        self.assertEqual(d["typeUnderVariant"]["withJ2AddedOnTop"],
                         ml.UNLABELLED)

    def test_the_ratio_is_net_over_raw(self):
        b = _natural_only_geo_burn()
        b["deltaIncNetDeg"] = 0.5 * b["deltaIncDeg"]
        self.assertAlmostEqual(ml._discriminations(b)["ratioNetOverRawAbs"],
                               0.5, places=12)

    def test_no_variant_touches_the_assigned_type(self):
        b = _natural_only_geo_burn()
        b["deltaIncNetJ2Deg"] = 1.0
        b["deltaIncNetMeasuredModelDeg"] = 1.0
        before = ml.assign_type(dict(b), "v2")
        b.update(ml._discriminations(b))
        self.assertEqual(ml.assign_type(dict(b), "v2"), before)

    def test_the_span_bins_cover_the_line_without_a_gap(self):
        e = ml.SPAN_BIN_EDGES_DAYS
        self.assertEqual(e[0], 0.0)
        self.assertEqual(e[-1], float("inf"))
        self.assertEqual(list(e), sorted(e))


class TestV2StationAcquisitionMapping(unittest.TestCase):
    """v2 registration section 7."""

    def test_v1_kept_the_mapping_the_results_measured_to_be_wrong(self):
        self.assertEqual(ml.RULES_BY_ID["v1"]["G3"].expected_label,
                         "t10aPostTransferEndpoint")

    def test_v2_maps_station_acquisition_to_arrivals(self):
        self.assertEqual(ml.RULES_BY_ID["v2"]["G3"].expected_label,
                         "t8aArrival")

    def test_only_the_mapping_moved_not_a_clause(self):
        a = ml.RULES_BY_ID["v1"]["G3"].as_dict()
        b = ml.RULES_BY_ID["v2"]["G3"].as_dict()
        a.pop("expectedLabelClass")
        b.pop("expectedLabelClass")
        self.assertEqual(a, b)
        self.assertIs(ml.RULES_BY_ID["v1"]["G3"].test,
                      ml.RULES_BY_ID["v2"]["G3"].test)

    def test_two_arm_g_rules_may_name_the_same_class(self):
        self.assertEqual(ml.RULES_BY_ID["v2"]["G2"].expected_label,
                         ml.RULES_BY_ID["v2"]["G3"].expected_label)

    def test_the_post_transfer_class_is_still_scored_not_removed(self):
        got = ml.per_type_precision(
            {"station acquisition": {"t10aPostTransferEndpoint": 3,
                                     "t8aArrival": 40}}, "v2")
        self.assertEqual(got["station acquisition"]["expectedLabelClass"],
                         "t8aArrival")
        self.assertEqual(got["station acquisition"]["agreeing"], 40)
        self.assertFalse(got["station acquisition"]["gateF"])


class TestVersionIsNeverDefaulted(unittest.TestCase):
    """v1 registration section 7.2, enforced."""

    def test_the_version_is_a_required_argument_everywhere(self):
        for fn in (ml.assign_type, ml.fired_rules, ml.rule_table,
                   ml.rules_sha256, ml.per_type_precision, ml.no_rule_reason,
                   ml.build_artifact, ml.rules, ml.type_names,
                   ml.per_rule_sha256, ml.floors_for):
            params = inspect.signature(fn).parameters
            self.assertIn("version", params, f"{fn.__name__} has no version")
            self.assertIs(params["version"].default,
                          inspect.Parameter.empty,
                          f"{fn.__name__} defaults its version")

    def test_an_unknown_version_is_refused(self):
        for bad in ("v3", "", None, "V1"):
            with self.assertRaises((ValueError, KeyError)):
                ml.rules_sha256(bad)

    def test_the_cli_requires_the_version(self):
        src = inspect.getsource(ml.main)
        self.assertIn('"--library-version"', src)
        self.assertIn("required=True", src)


class TestV1PublishesOnlyItsOwnFields(unittest.TestCase):
    """v2 registration section 8.2. The burn record is version-independent --
    the same burn, two rule sets -- so a v1 run must be stopped from
    serialising the v2 fields the record now carries."""

    def _row(self, version):
        rows = []

        class _Fh:
            @staticmethod
            def write(line):
                rows.append(json.loads(line))

        b = _natural_only_geo_burn()
        tally = ml.Tally()
        ml._type_and_record(b, ml.LabelIndex().freeze() or ml.LabelIndex(),
                            tally, {}, _Fh, version)
        return rows[0], tally

    def test_a_v1_ledger_row_carries_no_net_field(self):
        row, _ = self._row("v1")
        for k in ml.V2_LEDGER_DELTAS:
            self.assertNotIn(k, row, f"a v1 ledger row leaked {k}")
        for k in ml.V1_LEDGER_DELTAS:
            self.assertIn(k, row)

    def test_a_v2_ledger_row_carries_them(self):
        row, _ = self._row("v2")
        for k in ml.V2_LEDGER_DELTAS:
            self.assertIn(k, row, f"a v2 ledger row is missing {k}")

    def test_the_v1_quantile_block_gains_no_key(self):
        _, t1 = self._row("v1")
        _, t2 = self._row("v2")
        self.assertEqual(set(t1.dist),
                         {"G:" + k for k in ml.V1_REPORTED_DELTAS})
        self.assertTrue({"G:" + k for k in ml.V2_REPORTED_DELTAS} <= set(t2.dist))
        self.assertFalse({"G:" + k for k in ml.V2_REPORTED_DELTAS} & set(t1.dist))


class TestV1StillReproduces(unittest.TestCase):
    """v2 registration section 8.2. The offline half of the proof; the full
    rerun and the field-for-field comparison live in the results document."""

    V1_RULES_SHA = ("164a5fd11e4c63744615bbf58c02289cc812c46b630458a85b84f9aee"
                    "35024f6")

    def test_the_v1_rule_set_identity_is_unchanged(self):
        self.assertEqual(ml.rules_sha256("v1"), self.V1_RULES_SHA)

    def test_the_committed_v1_artifact_agrees(self):
        art = json.loads(
            (_REPO / "docs" / "manoeuvre-library-v1-20260922.json").read_text())
        self.assertEqual(art["rulesSha256"], self.V1_RULES_SHA)
        self.assertEqual(art["rules"], ml.rule_table("v1"))
        self.assertEqual(art["floors"], ml.floors_for("v1"))

    def test_the_v1_floor_block_gained_nothing(self):
        self.assertNotIn("netPoleResidualDeg", ml.floors_for("v1"))
        self.assertIn("netPoleResidualDeg", ml.floors_for("v2"))

    def test_the_v1_artifact_schema_gained_no_field(self):
        v1 = ml.build_artifact(ml.Tally(), {}, {}, 0.0, "v1")
        v2 = ml.build_artifact(ml.Tally(), {}, {}, 0.0, "v2")
        art = json.loads(
            (_REPO / "docs" / "manoeuvre-library-v1-20260922.json").read_text())
        self.assertEqual(set(v1), set(art))
        self.assertEqual(set(v2) - set(v1),
                         {"perRuleSha256", "byteIdenticalToV1",
                          "v1RulesSha256", "discriminations"})

    def test_the_v1_artifact_sha_cannot_be_reproduced_and_is_not_faked(self):
        """Declared in the registration before the run: the artifact embeds
        the tool file's own hash, so a second rule set in the same file must
        change it. Pinning the old value would falsify the provenance record,
        so no such constant exists anywhere in the tool."""
        self.assertNotIn(
            "eb287e809c0cd1b2f0de0b5bbb80ba33e811a692ca794944ae3dda614abef465",
            SRC)



if __name__ == "__main__":
    unittest.main(verbosity=2)
