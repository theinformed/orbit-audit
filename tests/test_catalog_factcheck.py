"""What the web fact-check lane is allowed to believe, and what it must refuse.

Every test here is a rule that, if it broke, would put a confident wrong claim on
a satellite card. The site carries a serving officer's name and is about to go in
front of test users, so the bar is not "does it find things" -- it is "can it be
talked into finding the wrong thing".

Nothing here touches the network or the GPU. The model's answers are supplied as
literals, which is exactly the point: the module's job is to decide whether a
model's answer is admissible, and that decision must be testable without one.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline import catalog_factcheck as fc


USA_170 = {
    "id": 27875,
    "name": "USA 170",
    "cosparId": "2003-040A",
    "mission": "other",
    "classificationBasis": "unclassified",
    "ownerCode": "US",
    "orbit": "GEO",
}

#: A real span, verbatim from the run of 2026-08-19.
WEEBAU = (
    "DSCS 3-14 # DSCS 3-F14 Also called USA-170 (code B6) Orig PL Name: DSCS III B-6 "
    "(Defense Satellite Communications System) --- ### Launch data: | Designation: | "
    "27875 / 03040A | | Launch date | 29 Aug 2003 - 23:13 UT |"
)


class KeyHandling(unittest.TestCase):
    def test_the_catalog_number_matches_on_a_digit_boundary(self):
        # A word boundary would match 27875 inside 127875, and a catalog of 8,000
        # five-digit numbers gives that plenty of chances to happen.
        self.assertTrue(fc.mentions_key("NORAD 27875 here", 27875, None))
        self.assertFalse(fc.mentions_key("part number 127875", 27875, None))
        self.assertFalse(fc.mentions_key("catalogue 278750", 27875, None))

    def test_a_cospar_id_matches_with_or_without_its_hyphen(self):
        self.assertTrue(fc.mentions_key("COSPAR 2003-040A", 1, "2003-040A"))
        self.assertTrue(fc.mentions_key("id 2003 040A", 1, "2003-040A"))

    def test_a_page_that_never_names_the_object_yields_no_key(self):
        self.assertEqual(fc.mentions_key("DSCS III is a US programme", 27875, "2003-040A"), [])


class Proximity(unittest.TestCase):
    def test_a_designation_beside_the_key_is_accepted(self):
        self.assertIsNotNone(
            fc.key_proximity(WEEBAU, "DSCS III B-6", 27875, "2003-040A")
        )

    def test_a_designation_far_from_the_key_is_refused(self):
        # The case this rule exists for: one page listing many launches, each
        # with its own designation beside its own catalog number.
        page = "USA 167 Payload: DSCS III A-3. Sat Cat: 27691." + (" filler." * 90) + \
               " USA 170 Payload: DSCS III B-6. Sat Cat: 27875."
        self.assertIsNone(fc.key_proximity(page, "DSCS III A-3", 27875, None))
        self.assertIsNotNone(fc.key_proximity(page, "DSCS III B-6", 27875, None))


class Normalisation(unittest.TestCase):
    def test_the_same_designation_written_differently_is_one_claim(self):
        # Found by a live run: four agreeing sources were reported as an even
        # split because "DSCS III A-3" and "DSCS-3 A3" normalised differently.
        for left, right in (
            ("DSCS III A-3", "DSCS-3 A3"),
            ("DSCS III B-6", "DSCS-3 B6"),
            ("MILSTAR-2 2", "Milstar 2-2"),
        ):
            self.assertEqual(
                fc.normalized_designation(left), fc.normalized_designation(right),
                f"{left!r} and {right!r} are the same claim",
            )

    def test_different_flight_numbers_stay_different(self):
        # The failure a reader would notice. Normalising must never merge these.
        self.assertNotEqual(
            fc.normalized_designation("DSCS III B-6"),
            fc.normalized_designation("DSCS III B-61"),
        )
        self.assertNotEqual(
            fc.normalized_designation("DSCS III A-3"),
            fc.normalized_designation("DSCS III B-3"),
        )


class ExtractionValidation(unittest.TestCase):
    def test_a_real_extraction_is_accepted(self):
        answer = {
            "designation": "DSCS III B-6",
            "quote": "Orig PL Name: DSCS III B-6 (Defense Satellite Communications System)",
        }
        accepted, why = fc.validated_extraction(answer, text=WEEBAU, satellite=USA_170)
        self.assertIsNotNone(accepted, why)
        self.assertEqual(accepted["designation"], "DSCS III B-6")

    def test_a_quote_that_is_not_in_the_source_is_refused(self):
        # The single most important test in this file. A model that invents a
        # plausible sentence must not be able to get a claim onto a card.
        answer = {
            "designation": "DSCS III B-6",
            "quote": "USA 170 is confirmed to be DSCS III B-6 by the US Space Force.",
        }
        accepted, why = fc.validated_extraction(answer, text=WEEBAU, satellite=USA_170)
        self.assertIsNone(accepted)
        self.assertEqual(why, "quote-not-in-source")

    def test_a_designation_not_inside_its_own_quote_is_refused(self):
        answer = {"designation": "DSCS III A-3", "quote": "Orig PL Name: DSCS III B-6"}
        accepted, why = fc.validated_extraction(answer, text=WEEBAU, satellite=USA_170)
        self.assertIsNone(accepted)
        self.assertEqual(why, "designation-not-in-quote")

    def test_the_object_s_own_name_is_not_another_name_for_it(self):
        # Pages repeat the catalogue name constantly and a model will hand it
        # back as "the other name": true, useless, and it would corroborate
        # itself across every source that exists.
        answer = {"designation": "USA-170", "quote": "Also called USA-170 (code B6)"}
        accepted, why = fc.validated_extraction(answer, text=WEEBAU, satellite=USA_170)
        self.assertIsNone(accepted)
        self.assertEqual(why, "designation-implausible")

    def test_a_trailing_gloss_is_trimmed_so_the_claim_still_corroborates(self):
        answer = {
            "designation": "DSCS III B-6 (Defense Satellite Communications System)",
            "quote": "Orig PL Name: DSCS III B-6 (Defense Satellite Communications System)",
        }
        accepted, _ = fc.validated_extraction(answer, text=WEEBAU, satellite=USA_170)
        self.assertEqual(accepted["designation"], "DSCS III B-6")

    def test_an_empty_answer_is_a_normal_outcome_not_an_error(self):
        accepted, why = fc.validated_extraction(
            {"designation": "", "quote": ""}, text=WEEBAU, satellite=USA_170
        )
        self.assertIsNone(accepted)
        self.assertEqual(why, "empty")


class ModelAnswerParsing(unittest.TestCase):
    def test_a_closed_reasoning_block_is_stripped(self):
        raw = '<think>The page mentions {a brace}. So the answer is...</think>{"designation": "X"}'
        self.assertEqual(fc.first_json_object(fc.strip_reasoning(raw)), {"designation": "X"})

    def test_an_unterminated_reasoning_block_leaves_nothing_behind(self):
        # The budget ran out mid-thought. There is no answer behind it, and
        # anything scraped out of the scratch work would be the model's guess.
        raw = '{"designation": "real"} <think>wait, maybe {"designation": "guess"}'
        self.assertEqual(fc.first_json_object(fc.strip_reasoning(raw)), {"designation": "real"})

    def test_a_brace_inside_a_copied_quote_does_not_break_the_parse(self):
        raw = '{"designation": "X", "quote": "table cell {27875} here"} trailing prose'
        parsed = fc.first_json_object(fc.strip_reasoning(raw))
        self.assertEqual(parsed["quote"], "table cell {27875} here")


class Corroboration(unittest.TestCase):
    @staticmethod
    def row(domain, tier, designation="DSCS III B-6"):
        return {"domain": domain, "tier": tier, "designation": designation,
                "url": f"https://{domain}/x", "quote": "q"}

    def test_one_source_is_never_enough(self):
        designation, why, _ = fc.corroborate([self.row("weebau.com", "enthusiast")])
        self.assertIsNone(designation)
        self.assertIn("1 independent source", why)

    def test_trackers_alone_are_never_enough(self):
        # Three trackers agreeing is one source agreeing with itself: they all
        # republish the catalogue this lane is checking.
        evidence = [
            self.row("keeptrack.space", "tracker"),
            self.row("n2yo.com", "tracker"),
            self.row("isstracker.pl", "tracker"),
        ]
        designation, why, _ = fc.corroborate(evidence)
        self.assertIsNone(designation)
        self.assertIn("tracker", why)

    def test_unrated_domains_cannot_carry_a_claim_either(self):
        # Otherwise the bar drops silently every time the search surfaces a
        # domain nobody has assessed.
        evidence = [
            self.row("keeptrack.space", "tracker"),
            self.row("some-aggregator.example", "unrated"),
        ]
        designation, _, _ = fc.corroborate(evidence)
        self.assertIsNone(designation)

    def test_two_domains_with_one_weight_bearing_source_settles_it(self):
        evidence = [
            self.row("keeptrack.space", "tracker"),
            self.row("weebau.com", "enthusiast"),
        ]
        designation, why, _ = fc.corroborate(evidence)
        self.assertEqual(designation, "DSCS III B-6")
        self.assertIn("2 independent sources", why)

    def test_one_site_repeating_itself_is_still_one_source(self):
        evidence = [
            self.row("weebau.com", "enthusiast"),
            self.row("weebau.com", "enthusiast"),
            self.row("weebau.com", "enthusiast"),
        ]
        designation, _, _ = fc.corroborate(evidence)
        self.assertIsNone(designation)

    def test_an_even_split_between_two_designations_writes_nothing(self):
        evidence = [
            self.row("keeptrack.space", "tracker", "DSCS III B-6"),
            self.row("weebau.com", "enthusiast", "DSCS III B-6"),
            self.row("astronautix.com", "reference", "DSCS III A-3"),
            self.row("en.wikipedia.org", "reference", "DSCS III A-3"),
        ]
        designation, why, _ = fc.corroborate(evidence)
        self.assertIsNone(designation)
        self.assertIn("split", why)

    def test_the_shown_spelling_prefers_a_weight_bearing_source(self):
        evidence = [
            self.row("keeptrack.space", "tracker", "DSCS-3 B6"),
            self.row("isstracker.pl", "tracker", "DSCS-3 B6"),
            self.row("weebau.com", "enthusiast", "DSCS III B-6"),
        ]
        designation, _, _ = fc.corroborate(evidence)
        self.assertEqual(designation, "DSCS III B-6")


class FlightNumberGuard(unittest.TestCase):
    def test_one_designation_claimed_by_two_objects_withdraws_both(self):
        # At least one is wrong and nothing here can say which, so neither ships.
        findings = {
            27691: {"id": 27691, "designation": "DSCS III B-6", "programme": "DSCS"},
            27875: {"id": 27875, "designation": "DSCS-3 B6", "programme": "DSCS"},
        }
        self.assertEqual(fc.unique_designations(findings), {})
        self.assertIn("more than one catalogue number", findings[27691]["withheld"])

    def test_distinct_designations_both_survive(self):
        findings = {
            27691: {"id": 27691, "designation": "DSCS III A-3", "programme": "DSCS"},
            27875: {"id": 27875, "designation": "DSCS III B-6", "programme": "DSCS"},
        }
        self.assertEqual(set(fc.unique_designations(findings)), {27691, 27875})


class ProgrammeTable(unittest.TestCase):
    def test_a_known_programme_resolves_from_any_spelling(self):
        for spelling in ("DSCS III B-6", "DSCS-3 B6", "DSCS 3 A 3"):
            matched = fc.programme_for(spelling)
            self.assertIsNotNone(matched, spelling)
            self.assertEqual(matched[1]["mission"], "communications")

    def test_a_programme_nobody_has_written_up_resolves_to_nothing(self):
        # The rule this pins has not changed: what a programme IS comes from a
        # person reading a source, never from the model's own knowledge, so a
        # designation the retrieval half corroborates but the table does not
        # cover resolves to NOTHING and the object stays unknown on the site.
        #
        # It used to be pinned on GSSAP 3 and CBAS 2, which were the live
        # examples on the day it was written. Both are now in the table, with
        # citations, so those two assertions had become a test of the table's
        # contents rather than of the rule. Trumpet and Mentor are the examples
        # now: real designations that the open record does discuss, that this
        # lane's retrieval half could plausibly return, and that nobody has
        # written a cited entry for.
        for unwritten in ("Trumpet 4", "Mentor 8", "Quasar 21"):
            with self.subTest(designation=unwritten):
                self.assertIsNone(fc.programme_for(unwritten))

    def test_the_programmes_that_have_been_written_up_do_resolve(self):
        """The other half of the rule, which the absence test alone cannot show.

        A test that only ever asserts absence stops being useful the moment the
        table grows -- and it fails for the RIGHT reason (someone did the work)
        while looking exactly like a regression. So each entry that exists is
        asserted to resolve to itself, from the spellings the retrieval half
        actually returned on live runs.
        """
        for designation, key in (
            ("DSCS III B-6", "DSCS"),
            ("Milstar 2-3", "MILSTAR"),
            ("DSP 22", "DSP"),
            ("DSP Flight 20", "DSP"),
            ("GSSAP 3", "GSSAP"),
            ("CBAS 2", "CBAS"),
        ):
            with self.subTest(designation=designation):
                matched = fc.programme_for(designation)
                self.assertIsNotNone(matched, designation)
                self.assertEqual(matched[0], key)

    def test_every_programme_entry_carries_a_checkable_source(self):
        # The first draft of this table was written from memory and three of its
        # five URLs were wrong -- AEHF and WGS were given the SAME spaceforce.mil
        # article id, and the DSCS fact sheet it cited does not exist. Every URL
        # in the table now was fetched and read. This test cannot re-fetch them,
        # so it checks the shape and, above all, that no two programmes share a
        # source: that collision is what exposed the fabrication.
        sources = [facts["source"] for facts in fc.PROGRAMME_FACTS.values()]
        self.assertEqual(len(sources), len(set(sources)),
                         "two programmes cite the same URL; at least one is wrong")
        for key, facts in fc.PROGRAMME_FACTS.items():
            self.assertTrue(facts["source"].startswith("https://"), key)
            self.assertIn(facts["sourceTier"], {"primary", "reference"}, key)
            # "other" is in this list, and it is not a shrug. The catalog's
            # mission vocabulary has no value for watching other satellites, so
            # every space-surveillance object on the site already carries
            # `mission: "other"` with `sector: "military"` -- SBSS, ORS-5,
            # S5, TJS -- which the interface renders as the "Other military"
            # facet rather than as "Other / unverified". GSSAP belongs with
            # them. What must NOT happen is an entry using "other" to avoid
            # choosing, which is why the description and the source are checked
            # in the same loop: an entry may be uncategorisable, never uncited.
            self.assertIn(facts["mission"], {
                "communications", "earth-observation", "navigation", "science",
                "weather", "technology", "missile-warning", "human-spaceflight",
                "other",
            }, key)
            self.assertGreater(len(facts["purpose"]), 80, key)
            self.assertIn(facts["sector"], {"military", "civil", "commercial", "mixed"}, key)


class SourceTiers(unittest.TestCase):
    def test_a_government_host_is_primary(self):
        self.assertEqual(fc.source_tier("https://www.spaceforce.mil/x"), "primary")

    def test_an_unknown_host_is_unrated_not_quietly_trusted(self):
        self.assertEqual(fc.source_tier("https://whatever.example/x"), "unrated")

    def test_subdomains_of_one_site_are_one_source(self):
        self.assertEqual(
            fc.registrable_domain("https://en.wikipedia.org/wiki/USA-169"),
            fc.registrable_domain("https://de.wikipedia.org/wiki/USA-169"),
        )


class TheKey(unittest.TestCase):
    def test_a_missing_key_fails_loudly_and_says_where_to_put_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            saved = os.environ.pop("EXA_API_KEY", None)
            os.environ["EXA_KEY_FILE"] = str(Path(tmp) / "absent.env")
            try:
                with self.assertRaises(fc.FactcheckUnavailable) as caught:
                    fc.require_key()
                self.assertIn("EXA_API_KEY", str(caught.exception))
                self.assertIn("exa.env", str(caught.exception))
            finally:
                os.environ.pop("EXA_KEY_FILE", None)
                if saved is not None:
                    os.environ["EXA_API_KEY"] = saved

    def test_the_key_is_read_from_the_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            saved = os.environ.pop("EXA_API_KEY", None)
            path = Path(tmp) / "exa.env"
            path.write_text("# a comment\nEXA_API_KEY=test-value-not-a-real-key\n")
            os.environ["EXA_KEY_FILE"] = str(path)
            try:
                self.assertEqual(fc.exa_key(), "test-value-not-a-real-key")
            finally:
                os.environ.pop("EXA_KEY_FILE", None)
                if saved is not None:
                    os.environ["EXA_API_KEY"] = saved


class FindingsFile(unittest.TestCase):
    def test_a_finding_with_no_citation_is_not_loaded(self):
        # A hand-edited or truncated file must degrade to "no claim", never to an
        # uncited claim on a card.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.json"
            path.write_text(json.dumps({"objects": {
                "27875": {"mission": "communications", "citations": []},
                "27691": {"mission": "communications",
                          "citations": [{"url": "https://x/y", "tier": "reference", "quote": "q"}]},
            }}))
            self.assertEqual(set(fc.load_findings(path)), {27691})

    def test_an_absent_file_is_an_empty_table_not_a_crash(self):
        self.assertEqual(fc.load_findings(Path("/nonexistent/factcheck.json")), {})

    def test_the_shipped_findings_all_carry_quoted_citations(self):
        shipped = fc.load_findings()
        self.assertTrue(shipped, "the lane has shipped no findings at all")
        for catalog_id, entry in shipped.items():
            self.assertGreaterEqual(len(entry["citations"]), 2, catalog_id)
            for citation in entry["citations"]:
                self.assertTrue(citation["url"].startswith("http"), catalog_id)
                self.assertTrue(citation["quote"].strip(), catalog_id)
            self.assertTrue(entry["programmeSource"].startswith("https://"), catalog_id)
            self.assertIn(entry["programmeSourceTier"], {"primary", "reference"}, catalog_id)

    def test_the_dscs_case_the_owner_found_is_fixed(self):
        # The case that started this. US military spacecraft are catalogued as
        # "USA nnn", so a DSCS rule matching the string "DSCS" matched nothing.
        shipped = fc.load_findings()
        self.assertEqual(shipped[27875]["designation"], "DSCS III B-6")
        self.assertEqual(shipped[27691]["designation"], "DSCS III A-3")
        for catalog_id in (27875, 27691):
            self.assertEqual(shipped[catalog_id]["mission"], "communications")
            self.assertEqual(shipped[catalog_id]["sector"], "military")


class GapCensus(unittest.TestCase):
    def test_a_family_is_the_part_of_a_name_its_series_shares(self):
        self.assertEqual(fc.designation_family("USA 170"), "USA")
        self.assertEqual(fc.designation_family("GEESAT-1 A03"), "GEESAT")
        self.assertEqual(fc.designation_family("HULIANWANG DIGUI-01"), "HULIANWANG DIGUI")

    def test_an_object_this_lane_already_filled_is_still_re_checked(self):
        # The trap that cost three findings on the first re-run. This module
        # reads the PUBLISHED catalogue, so a shipped finding stops the object
        # being "unclassified" -- and a bar that asked only for that found 15
        # objects where there had been 19, re-resolved one, and wrote a findings
        # file that silently dropped the other three, both DSCS spacecraft among
        # them. The report looked entirely healthy while it happened.
        shipped = dict(USA_170, mission="communications",
                       classificationBasis="web-corroborated")
        self.assertTrue(fc.is_unresolved(shipped))

    def test_an_object_another_lane_settled_is_left_alone(self):
        # A radio licence is something an operator filed with a regulator under
        # penalty. This lane must not re-open it, or compete with it.
        licensed = dict(USA_170, mission="communications",
                        classificationBasis="radio-licence")
        self.assertFalse(fc.is_unresolved(licensed))
        curated = dict(USA_170, mission="communications", classificationBasis="norad-id")
        self.assertFalse(fc.is_unresolved(curated))

    def test_only_objects_the_site_says_nothing_about_are_counted(self):
        rows = fc.gap_census([
            USA_170,
            {"id": 1, "name": "USA 171", "mission": "other",
             "classificationBasis": "unclassified", "ownerCode": "US", "orbit": "GEO"},
            {"id": 2, "name": "GOES 16", "mission": "weather",
             "classificationBasis": "name-pattern", "ownerCode": "US", "orbit": "GEO"},
        ])
        self.assertEqual([(row["family"], row["objects"]) for row in rows], [("USA", 2)])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
