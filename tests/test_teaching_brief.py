"""Tests for the model-written teaching brief's validity rules.

Since 2026-08-08 the tolerance is a WORD boundary rather than a distance, so
several of these are now identities against the site's own vocabulary: the edges
in ``_WORD_EDGES`` are compared directly with the thresholds
``deterministic_weather_brief`` applies to the same quantities, and a change too
small to move a value out of its band is asserted not to throw away the brief.
"""

from __future__ import annotations

import datetime as dt
import unittest

from pipeline.build_release import canonical_json, deterministic_weather_brief, sha256
from pipeline.teaching_brief import (
    MAX_BRIEF_AGE_MINUTES,
    _EXCLUDED_KEYS,
    _WORD_EDGES,
    band_bounds,
    brief_fingerprint,
    edge_margin,
    latest_observed_at,
    facts_snapshot,
    snapshot_still_describes,
    validate_candidate,
)

NOW = dt.datetime(2026, 8, 7, 12, 0, tzinfo=dt.timezone.utc)


def facts(speed=400.0, kp=1.0, xray="B2.7", observed="2026-08-07T11:55:00Z"):
    return {
        "solarWind": {
            "observedAt": observed,
            "sourceSpacecraft": "SOLAR1",
            "speedKps": speed,
            "densityCm3": 4.0,
            "dynamicPressureNpa": 0.5,
        },
        "imf": {"observedAt": observed, "sourceSpacecraft": "SOLAR1", "btNt": 3.0, "bzGsmNt": -1.0},
        "geomagnetic": {"observedAt": observed, "kp": kp},
        "xray": {"observedAt": observed, "class": xray},
        "ionosphere": {"observedAt": observed, "status": "assimilated", "tecRange": [1, 30], "medianHmF2Km": 317.0},
        "magnetopause": {
            "status": "model",
            "model": "Shue",
            "subsolarStandoffRe": 10.2,
            "flaringAlpha": 0.58,
            "caveat": "An axisymmetric empirical boundary driven by upstream pressure and IMF Bz; "
            "it is not a measured surface.",
        },
    }


def candidate(f, generated=NOW, **overrides):
    base = {
        "schema": 1,
        "kind": "model-assisted",
        "reasoningUsed": True,
        "factsFingerprint": brief_fingerprint(f, sha256, canonical_json),
        "factsSnapshot": facts_snapshot(f),
        "generatedAt": generated.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "observationsAt": latest_observed_at(f),
        "text": "The upstream solar wind is relatively slow and the interplanetary field is only weakly southward, "
        "so the magnetosphere is not being driven hard at the moment.",
        "caveat": "A fact-bounded snapshot, not a forecast of local effects.",
    }
    base.update(overrides)
    return base


class TeachingBriefValidityTests(unittest.TestCase):
    def test_timestamps_do_not_change_the_binding(self):
        """The old contract hashed observedAt, so a brief expired within one cycle."""
        early = facts(observed="2026-08-07T11:00:00Z")
        later = facts(observed="2026-08-07T11:55:00Z")
        self.assertIsNotNone(validate_candidate(candidate(early), later, sha256, canonical_json, now=NOW))

    def test_drift_across_a_rounding_boundary_keeps_the_brief(self):
        """Measured live: Kp 0.0->1.0, Bt 2.5->5.0, speed 300->250 in rounded terms
        rejected a brief whose underlying values had barely moved."""
        before = facts(speed=274.0, kp=0.4)
        after = facts(speed=276.0, kp=0.6)
        self.assertIsNotNone(validate_candidate(candidate(before), after, sha256, canonical_json, now=NOW))


    def test_material_change_invalidates_the_brief(self):
        quiet = facts(speed=400.0, kp=1.0)
        storm = facts(speed=700.0, kp=7.0)
        self.assertIsNone(validate_candidate(candidate(quiet), storm, sha256, canonical_json, now=NOW))


    def test_flare_class_letter_is_material_but_the_decimal_is_not(self):
        self.assertTrue(snapshot_still_describes(facts_snapshot(facts(xray="B2.7")), facts(xray="B4.1")))
        self.assertFalse(snapshot_still_describes(facts_snapshot(facts(xray="B2.7")), facts(xray="M1.2")))


    def test_small_drift_within_a_quantisation_step_keeps_the_brief(self):
        self.assertTrue(validate_candidate(candidate(facts(speed=400.0)), facts(speed=405.0), sha256, canonical_json, now=NOW))


    def test_stale_brief_is_rejected_even_when_conditions_match(self):
        old = NOW - dt.timedelta(minutes=MAX_BRIEF_AGE_MINUTES + 1)
        self.assertIsNone(validate_candidate(candidate(facts(), generated=old), facts(), sha256, canonical_json, now=NOW))


    def test_a_brief_containing_a_digit_is_rejected(self):
        f = facts()
        bad = candidate(f, text="Solar wind is near 400 km/s which is unremarkable for this part of the cycle today.")
        self.assertIsNone(validate_candidate(bad, f, sha256, canonical_json, now=NOW))


    def test_brief_without_reasoning_is_rejected(self):
        f = facts()
        self.assertIsNone(validate_candidate(candidate(f, reasoningUsed=False), f, sha256, canonical_json, now=NOW))


    def test_accepted_brief_carries_its_observation_time(self):
        f = facts()
        brief = validate_candidate(candidate(f), f, sha256, canonical_json, now=NOW)
        self.assertIsNotNone(brief)
        self.assertEqual(brief["observationsAt"], "2026-08-07T11:55:00Z")
        self.assertEqual(brief["kind"], "model-assisted")


    def test_caveat_echoed_from_the_fact_packet_is_rejected(self):
        """Observed live: the model returned the Shue caveat as its own caveat."""
        f = facts()
        echoed = candidate(f, caveat=f["magnetopause"]["caveat"])
        self.assertIsNone(validate_candidate(echoed, f, sha256, canonical_json, now=NOW))

    def test_a_brief_spelling_a_number_out_in_words_is_rejected(self):
        """Observed live: the model evaded the digit ban by writing the value out."""
        f = facts()
        for evasion in (
            "Flow speeds are below three hundred kilometers per second across the interval today.",
            "The modeled standoff distance exceeds twelve Earth radii under present conditions.",
        ):
            self.assertIsNone(validate_candidate(candidate(f, text=evasion), f, sha256, canonical_json, now=NOW))

    def test_ordinary_qualitative_prose_still_passes(self):
        f = facts()
        self.assertIsNotNone(validate_candidate(candidate(f), f, sha256, canonical_json, now=NOW))

    def test_tec_range_is_not_part_of_the_binding_at_all(self):
        """It encodes "the upstream was absent" more often than a real change.

        When the assimilated field is missing the ionosphere layer publishes
        [0, 1] rather than a gap. Measured over 253 real packets across 25.9 h,
        that happened on 19 of them; excluding those, the observed range was 46
        to 65 TECU, which is one word wide. Both the small drift and the large
        collapse are now outside the binding, and MAX_BRIEF_AGE_MINUTES is what
        bounds them.
        """
        self.assertIn("tecRange", _EXCLUDED_KEYS)
        for after in ([1.7, 33.0], [0, 1], [1.0, 95.0]):
            changed = facts()
            changed["ionosphere"]["tecRange"] = after
            self.assertTrue(snapshot_still_describes(facts_snapshot(facts()), changed))

    def test_snapshot_drops_timestamps_and_spacecraft(self):
        reduced = facts_snapshot(facts())
        self.assertTrue("observedAt" not in reduced["solarWind"])
        self.assertTrue("sourceSpacecraft" not in reduced["solarWind"])
        self.assertEqual(reduced["solarWind"]["speedKps"], 400.0)


class WordBandTests(unittest.TestCase):
    """The tolerance is now the width of a word, so prove it against the words.

    Every assertion here is an identity: either two numbers taken from different
    modules are equal, or a value is on one side of a comparison. Nothing here
    reads the brief and decides whether it is still apt.
    """

    def test_speed_edges_are_the_ones_the_site_publishes(self):
        """450 and 600 are where deterministic_weather_brief changes its word."""
        for edge, below, above in ((450.0, "relatively slow", "moderate"),
                                   (600.0, "moderate", "fast")):
            self.assertIn(edge, _WORD_EDGES[("solarWind", "speedKps")])
            self.assertIn(below, deterministic_weather_brief(edge - 0.1, 0.0, 1.0, "B1.0")["text"])
            self.assertIn(above, deterministic_weather_brief(edge, 0.0, 1.0, "B1.0")["text"])

    def test_bz_edges_are_the_ones_the_site_publishes(self):
        self.assertEqual(_WORD_EDGES[("imf", "bzGsmNt")], (-5.0, 5.0))
        self.assertIn("southward enough",
                      deterministic_weather_brief(400.0, -5.0, 1.0, "B1.0")["text"])
        self.assertIn("near neutral",
                      deterministic_weather_brief(400.0, -4.9, 1.0, "B1.0")["text"])
        self.assertIn("northward",
                      deterministic_weather_brief(400.0, 5.0, 1.0, "B1.0")["text"])

    def test_kp_edges_are_the_ones_the_site_publishes(self):
        self.assertEqual(_WORD_EDGES[("geomagnetic", "kp")], (4.0, 5.0))
        self.assertIn("below NOAA", deterministic_weather_brief(400.0, 0.0, 3.9, "B1.0")["text"])
        self.assertIn("active but below",
                      deterministic_weather_brief(400.0, 0.0, 4.0, "B1.0")["text"])
        self.assertIn("storm range",
                      deterministic_weather_brief(400.0, 0.0, 5.0, "B1.0")["text"])

    def test_the_margin_is_a_tenth_of_the_narrowest_band(self):
        self.assertEqual(edge_margin((450.0, 600.0)), 15.0)
        self.assertEqual(edge_margin((4.0, 5.0)), 0.1)
        self.assertEqual(edge_margin(()), 0.0)

    def test_a_value_on_an_edge_belongs_to_the_band_above_it(self):
        self.assertEqual(band_bounds((450.0, 600.0), 450.0), (450.0, 600.0))
        self.assertEqual(band_bounds((450.0, 600.0), 449.9), (float("-inf"), 450.0))
        self.assertEqual(band_bounds((450.0, 600.0), 600.0), (600.0, float("inf")))

    def test_a_change_too_small_to_change_a_word_keeps_the_brief(self):
        """The whole point. 3% off a value is not a new sentence.

        Kp 1.0 -> 1.03 and speed 400 -> 412 are both 3% moves that stay inside
        the same published band, and each one used to be able to cost seventy
        seconds of a GPU shared with a human waiting on it.
        """
        before = facts(speed=400.0, kp=1.0)
        after = facts(speed=412.0, kp=1.03)
        self.assertTrue(snapshot_still_describes(facts_snapshot(before), after))
        self.assertIsNotNone(validate_candidate(candidate(before), after, sha256,
                                                canonical_json, now=NOW))

    def test_crossing_a_word_boundary_invalidates_the_brief(self):
        """449 to 460 is a smaller move than 400 to 440, and it is the one that counts."""
        self.assertFalse(snapshot_still_describes(facts_snapshot(facts(speed=400.0)),
                                                  facts(speed=470.0)))
        self.assertTrue(snapshot_still_describes(facts_snapshot(facts(speed=400.0)),
                                                 facts(speed=440.0)))

    def test_jitter_across_an_edge_does_not_throw_the_brief_away(self):
        """A value resting on a boundary must not re-buy the brief every cycle.

        449.9 -> 455.0 crosses the 450 edge, but by less than the margin, so the
        band is not treated as left. This is the rounded-bucket instability the
        module docstring records, expressed at the only boundary that is left.
        """
        self.assertTrue(snapshot_still_describes(facts_snapshot(facts(speed=449.9)),
                                                 facts(speed=455.0)))
        self.assertFalse(snapshot_still_describes(facts_snapshot(facts(speed=449.9)),
                                                  facts(speed=466.0)))

    def test_an_absent_value_is_not_a_material_change(self):
        """The solar wind went missing on 16 of 253 real cycles.

        A gap is the loss of the evidence that could show a change, not a change.
        Rewriting the brief about a fact packet with LESS in it than the last one
        spent GPU for nothing.
        """
        present = facts(speed=400.0)
        absent = facts(speed=400.0)
        absent["solarWind"]["speedKps"] = None
        self.assertTrue(snapshot_still_describes(facts_snapshot(present), absent))
        self.assertTrue(snapshot_still_describes(facts_snapshot(absent), present))

    def test_the_source_caveat_cannot_invalidate_the_brief(self):
        """It is prose with the guard's own digits in it, and it changes every cycle.

        Measured: 11 distinct variants across 253 packets, differing only in the
        two spacecraft readings quoted inside the sentence.
        """
        self.assertIn("caveat", _EXCLUDED_KEYS)
        changed = facts()
        changed["magnetopause"]["caveat"] = (
            facts()["magnetopause"]["caveat"]
            + " Solar-wind speed and density are withheld: SOLAR1 reads 278 km/s while IMAP "
              "reads 285 km/s over the same hour."
        )
        self.assertTrue(snapshot_still_describes(facts_snapshot(facts()), changed))

    def test_dropping_the_caveat_from_the_binding_leaves_the_echo_check_intact(self):
        """The two rules read different things: one reads the snapshot, one reads facts."""
        f = facts()
        self.assertIsNone(validate_candidate(candidate(f, caveat=f["magnetopause"]["caveat"]),
                                             f, sha256, canonical_json, now=NOW))


if __name__ == "__main__":
    unittest.main()
