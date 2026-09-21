"""The coverage tracker's arithmetic, and the two promises it makes.

Promise one: the page is never published.  It is written into the one tree the
publish gate structurally cannot stage, nothing in the front end links to it,
and it carries no inline script -- the nginx catch-all sends
``script-src 'self'`` with no ``'unsafe-inline'``, so an inline script would be
silently dropped and the only person allowed to read the page would be reading a
broken one.

Promise two: **a 403 is not a dead link.**  Several publishers and every .mil
host in this catalog refuse automated clients outright.  A tracker that reported
those as rot would be printing a false accusation beside a perfectly good
citation, and the first person to check one by hand would stop believing the
whole column.  That is asserted here from both ends -- the classifier, and the
grading step that consumes it.

No network, no clock, no systemd.  Every assertion below is an identity.
"""

from __future__ import annotations

import collections
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from pipeline import coverage_tracker as tracker

ROOT = Path(__file__).resolve().parents[1]


def record(**overrides):
    """A minimal catalog row: described, cited, corroborated, specific."""
    base = {
        "id": 44444,
        "name": "EXAMPLESAT 7",
        "purpose": "EXAMPLESAT 7 is the seventh spacecraft of a fictional series, "
                   "flown for the purposes of this test and for nothing else at all, "
                   "and this sentence is comfortably past the length floor.",
        "purposeSource": "https://example.invalid/examplesat",
        "purposeKind": "curated",
        "classificationBasis": "norad-id",
        "classificationConfidence": "high",
        "contestedAttribution": None,
        "constellation": None,
        "ownerCode": "US",
        "orbit": "LEO",
        "mission": "technology",
        "sector": "civil",
        "programmes": None,
        "launchDate": "2019-04-01",
        "omm": {"EPOCH": "2026-08-19T00:00:00"},
    }
    base.update(overrides)
    return base


def gaps_for(row, shared=None, liveness=None):
    counts = collections.Counter(shared or {str(row.get("purpose") or ""): 1})
    return {
        gap["dimension"]
        for gap in tracker.grade_record(row, counts, liveness or {})
    }


class Dimensions(unittest.TestCase):
    def test_every_dimension_has_a_positive_weight_and_a_reason(self):
        for dimension in tracker.DIMENSIONS:
            self.assertGreater(dimension.weight, 0, dimension.key)
            self.assertTrue(dimension.why.strip(), dimension.key)

    def test_dimension_keys_are_unique(self):
        keys = [dimension.key for dimension in tracker.DIMENSIONS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_a_complete_card_trips_nothing(self):
        self.assertEqual(gaps_for(record()), set())

    def test_the_generators_apology_is_graded_as_no_description(self):
        for marker in tracker.UNKNOWN_TEMPLATE_MARKERS:
            row = record(purpose=marker + ", and here is some more text after it.")
            self.assertIn("no-description", gaps_for(row), marker)

    def test_a_radio_licence_is_graded_as_evidence_but_thin_evidence(self):
        self.assertIn("licence-only", gaps_for(record(classificationBasis="radio-licence")))

    def test_a_missing_citation_is_graded(self):
        self.assertIn("no-source", gaps_for(record(purposeSource=None)))
        self.assertIn("no-source", gaps_for(record(purposeSource="not-a-url")))


class PerObjectDetail(unittest.TestCase):
    """The dimension the whole tracker exists for."""

    SHARED = ("A low-Earth-orbit spacecraft in a large constellation, relaying "
              "broadband internet traffic through a distributed network of peers.")

    def test_family_prose_shared_with_siblings_and_naming_nothing_is_graded(self):
        row = record(name="EXAMPLESAT 7", purpose=self.SHARED)
        self.assertIn("no-per-object-detail", gaps_for(row, shared={self.SHARED: 4660}))

    def test_the_same_text_on_a_single_object_is_not_graded(self):
        row = record(name="EXAMPLESAT 7", purpose=self.SHARED)
        self.assertNotIn("no-per-object-detail", gaps_for(row, shared={self.SHARED: 1}))

    def test_a_designator_from_the_name_is_an_anchor(self):
        """How the GPS cards pass: the text carries SVN, PRN, plane and slot."""
        text = self.SHARED + " This one is flight 7 in plane C, slot 4."
        row = record(name="EXAMPLESAT 7", purpose=text)
        self.assertTrue(tracker.has_per_object_anchor(row))
        self.assertNotIn("no-per-object-detail", gaps_for(row, shared={text: 30}))

    def test_the_retired_registry_tail_is_not_an_anchor(self):
        """INVERTED 2026-08-20, and the inversion is the point.

        This asserted the opposite: that "This object's registry record: about
        550 km up ..." counted as saying something about THIS object. The
        sentence is gone from the cards -- it restated the Satellite Details
        grid in prose on 1,205 of them -- so a card carrying it could only mean
        it had been reintroduced. The tracker must not bless it back.
        """
        text = self.SHARED + " This object's registry record: about 550 km up."
        row = record(name="NAMELESS", purpose=text)
        self.assertFalse(tracker.has_per_object_anchor(row))
        self.assertFalse(hasattr(tracker, "REGISTRY_TAIL"))

    def test_naming_the_family_is_not_the_same_as_naming_the_object(self):
        """A Starlink line naming 'Starlink' still says nothing per-object."""
        text = "A spacecraft in the Examplesat constellation, relaying traffic."
        row = record(name="EXAMPLESAT 7", purpose=text)
        self.assertTrue(tracker.names_its_family(row))
        self.assertFalse(tracker.has_per_object_anchor(row))
        found = gaps_for(row, shared={text: 12})
        self.assertIn("no-per-object-detail", found)
        self.assertNotIn("never-names-itself", found)

    def test_never_names_itself_needs_siblings_too(self):
        """On its own it fires on cards plainly about their object, so it is
        graded only in combination -- CALSPHERE 1's card opens 'A passive
        metal sphere' and is about nothing else."""
        text = "A passive metal sphere with no power and no transmitter, flown in 1964 " \
               "as one of a matched pair so that comparing their decay isolated drag."
        row = record(name="CALSPHERE 1", purpose=text)
        self.assertFalse(tracker.names_its_family(row))
        self.assertNotIn("never-names-itself", gaps_for(row, shared={text: 1}))
        self.assertIn("never-names-itself", gaps_for(row, shared={text: 9}))


class TheThreeKindsOfMissing(unittest.TestCase):
    """A card can fail to describe its object for three different reasons, and
    merging them hides which sweep would fix which."""

    UNKNOWN = ("The public catalog does not identify this spacecraft's payload. "
               "What is on record is its radio licence: its transmitters are filed "
               "under the ITU Earth Exploration service in the SatNOGS community "
               "database.")

    def test_a_spectrum_filing_in_place_of_a_mission_is_its_own_finding(self):
        """PAZ is a Spanish X-band SAR imaging satellite and its card says
        'Earth Exploration service'. True, cited, corroborated, and not what
        the spacecraft is for."""
        row = record(name="PAZ", purpose=self.UNKNOWN,
                     classificationBasis="radio-licence", purposeKind="template",
                     classificationConfidence="medium")
        found = gaps_for(row)
        self.assertIn("licence-only", found)
        self.assertNotIn("no-description", found, "the three kinds must stay disjoint")

    def test_a_rideshare_dispenser_slot_is_graded_apart_from_it(self):
        row = record(name="R2", purposeKind="class", classificationBasis="unclassified",
                     classificationConfidence="low", purposeSource=None,
                     purpose="No public source names this spacecraft's payload, which "
                             "is ordinary for its class: it is one of 13 objects.")
        found = gaps_for(row)
        self.assertIn("class-not-object", found)
        self.assertNotIn("no-description", found)
        self.assertNotIn("licence-only", found)

    def test_the_licence_lane_is_not_blamed_on_an_owner_partition(self):
        """Corrected 2026-08-20: these are a lane's output, not a seam."""
        row = record(name="PAZ", ownerCode="SPN", purpose=self.UNKNOWN,
                     classificationBasis="radio-licence")
        import datetime as dt
        cause = tracker.attribute_cause(
            row, [{"dimension": "licence-only"}], dt.date(2026, 8, 20))
        self.assertIn("radio-licence lane", cause)
        self.assertNotIn("partition", cause)

    def test_a_radio_licence_corroborates_the_transmitter_not_the_mission(self):
        self.assertIn("radio-licence", tracker.CORROBORATED_BASES)
        self.assertIn("radio-licence", tracker.MISSION_UNCORROBORATED_BASES)
        row = record(classificationBasis="radio-licence", purpose=self.UNKNOWN)
        self.assertIn("weak-classification", gaps_for(row))


class Exemptions(unittest.TestCase):
    """Every carve-out the site applies, enumerated. An audit whose exemptions
    nobody can list is not an audit."""

    @classmethod
    def setUpClass(cls):
        catalog = {"satellites": [
            record(id=1, name="PAZ", classificationBasis="radio-licence",
                   purposeKind="template",
                   purpose="The public catalog does not identify this spacecraft's "
                           "payload. What is on record is its radio licence."),
            record(id=2, name="R2", purposeKind="class",
                   purpose="No public source names this spacecraft's payload, which "
                           "is ordinary for its class."),
        ]}
        cls.rows = tracker.front_end_exemptions(catalog)

    def test_it_finds_the_front_ends_prefix_list(self):
        self.assertTrue(any("TEMPLATE_PURPOSE_PREFIXES" in row["where"] for row in self.rows))

    def test_it_reports_the_gap_that_hid_the_radio_licence_cards(self):
        gap = [row for row in self.rows if "gap between its list and ours" in row["where"]]
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0]["objects"], 1, "PAZ passes the front end's check and fails ours")

    def test_it_reports_the_basis_the_two_definitions_disagree_about(self):
        chip = [row for row in self.rows if "CORROBORATED_BASES" in row["where"]]
        self.assertEqual([row["objects"] for row in chip], [1])
        self.assertIn("radio-licence", chip[0]["rule"])

    def test_the_lists_are_read_from_source_not_retyped(self):
        source = (ROOT / "src" / "main.ts").read_text(encoding="utf-8")
        self.assertTrue(tracker._ts_string_array(source, "TEMPLATE_PURPOSE_PREFIXES"))
        self.assertIn("radio-licence", tracker._ts_string_set(source, "CORROBORATED_BASES"))


class ConfidenceAndEvidence(unittest.TestCase):
    def test_high_confidence_on_a_name_pattern_is_a_conflict(self):
        row = record(classificationBasis="name-pattern", classificationConfidence="high")
        found = gaps_for(row)
        self.assertIn("confidence-conflict", found)
        self.assertIn("weak-classification", found)

    def test_high_confidence_over_hedged_prose_is_a_conflict(self):
        row = record(purpose="This spacecraft is assessed to carry an imaging payload, "
                             "which is a hedge, and the chip above it says high confidence.")
        self.assertIn("confidence-conflict", gaps_for(row))

    def test_medium_confidence_over_the_same_hedge_is_not(self):
        row = record(classificationConfidence="medium", classificationBasis="assessed",
                     purpose="This spacecraft is assessed to carry an imaging payload, "
                             "which is a hedge, and the chip above it agrees with it.")
        self.assertNotIn("confidence-conflict", gaps_for(row))

    def test_a_basis_that_corroborates_the_mission_is_never_weak(self):
        """`radio-licence` is deliberately not in this set. It corroborates the
        transmitter, and the question a description answers is the mission."""
        for basis in tracker.CORROBORATED_BASES - tracker.MISSION_UNCORROBORATED_BASES:
            self.assertNotIn("weak-classification",
                             gaps_for(record(classificationBasis=basis)), basis)


class ForbiddenToCallItDead(unittest.TestCase):
    """A 403 is not a dead link. Asserted at the classifier and at the grader."""

    def test_a_refused_automated_client_is_unverifiable_not_dead(self):
        for status in (401, 403, 429):
            verdict = {"state": "unverifiable", "status": status}
            found = gaps_for(record(), liveness={record()["purposeSource"]: verdict})
            self.assertNotIn("dead-source", found, status)

    def test_a_404_is_dead(self):
        verdict = {"state": "dead", "status": 404}
        self.assertIn("dead-source",
                      gaps_for(record(), liveness={record()["purposeSource"]: verdict}))

    def test_one_dns_failure_is_not_enough_to_accuse_a_citation(self):
        verdict = {"state": "dns-failure", "status": "dns", "strikes": 1}
        self.assertNotIn("dead-source",
                         gaps_for(record(), liveness={record()["purposeSource"]: verdict}))

    def test_two_dns_failures_are(self):
        verdict = {"state": "dns-failure", "status": "dns",
                   "strikes": tracker.DNS_STRIKES_FOR_DEAD}
        self.assertIn("dead-source",
                      gaps_for(record(), liveness={record()["purposeSource"]: verdict}))

    def test_an_unconfirmed_dns_failure_is_never_treated_as_a_fresh_cache_entry(self):
        entry = {"state": "dns-failure", "strikes": 1, "checkedAtEpoch": 1.0e12}
        self.assertFalse(tracker._cache_is_fresh(entry, 1.0e12))
        entry["strikes"] = tracker.DNS_STRIKES_FOR_DEAD
        self.assertTrue(tracker._cache_is_fresh(entry, 1.0e12))


class TheClassifierItself(unittest.TestCase):
    """`urllib_probe`'s own verdicts, with a fake opener and no network.

    These exist because the first version of this suite asserted the promise
    only at the grading step, which consumes a verdict someone else produced.
    Rewriting `urllib_probe` to call a 403 dead broke the promise and passed
    every test. It does not any more.
    """

    @staticmethod
    def _probe(behaviour):
        return tracker.urllib_probe(
            "https://example.invalid/page", opener=behaviour, sleep=lambda _s: None
        )

    @staticmethod
    def _raiser(code):
        def opener(request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url, code, "denied", {}, None
            )
        return opener

    def test_a_403_on_both_head_and_get_is_unverifiable(self):
        verdict = self._probe(self._raiser(403))
        self.assertEqual(verdict["state"], "unverifiable")
        self.assertIn("NOT a dead link", verdict["note"])

    def test_a_401_and_a_429_are_unverifiable_too(self):
        for code in (401, 429):
            self.assertEqual(self._probe(self._raiser(code))["state"], "unverifiable", code)

    def test_a_404_is_dead_and_a_410_is_dead(self):
        for code in (404, 410):
            self.assertEqual(self._probe(self._raiser(code))["state"], "dead", code)

    def test_a_500_is_unverifiable_because_the_page_may_be_fine_tomorrow(self):
        self.assertEqual(self._probe(self._raiser(500))["state"], "unverifiable")

    def test_a_name_that_does_not_resolve_is_held_back_for_a_second_opinion(self):
        def opener(request, timeout=None):
            raise urllib.error.URLError("[Errno -2] Name or service not known")
        self.assertEqual(self._probe(opener)["state"], "dns-failure")

    def test_a_timeout_is_never_an_accusation(self):
        def opener(request, timeout=None):
            raise TimeoutError("timed out")
        self.assertEqual(self._probe(opener)["state"], "unverifiable")

    def test_head_is_tried_before_get_so_the_publisher_serves_no_body(self):
        seen = []

        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False

        def opener(request, timeout=None):
            seen.append(request.get_method())
            return Response()

        verdict = self._probe(opener)
        self.assertEqual(seen, ["HEAD"])
        self.assertEqual(verdict["method"], "HEAD")

    def test_a_405_falls_back_to_a_ranged_get(self):
        seen = []

        class Response:
            status = 206
            def __enter__(self): return self
            def __exit__(self, *args): return False

        def opener(request, timeout=None):
            seen.append((request.get_method(), request.headers.get("Range")))
            if request.get_method() == "HEAD":
                raise urllib.error.HTTPError(request.full_url, 405, "no", {}, None)
            return Response()

        verdict = self._probe(opener)
        self.assertEqual(verdict["state"], "live")
        self.assertEqual(seen, [("HEAD", None), ("GET", "bytes=0-2047")])

    def test_the_user_agent_names_a_person_who_can_be_complained_to(self):
        self.assertIn("contact", tracker.USER_AGENT)
        self.assertIn("@", tracker.USER_AGENT)

    def test_there_is_a_global_floor_as_well_as_a_per_host_one(self):
        self.assertGreater(tracker.MIN_REQUEST_INTERVAL_S, 0)
        self.assertGreater(tracker.MIN_GLOBAL_INTERVAL_S, 0)


class NetworkIsOptIn(unittest.TestCase):
    def test_the_default_transport_refuses(self):
        with self.assertRaises(tracker.LivenessRefused):
            tracker.offline_probe("https://example.invalid/")

    def test_a_zero_budget_makes_no_calls_at_all(self):
        def explode(url):
            raise AssertionError(f"the tracker fetched {url} without being asked to")

        with tempfile.TemporaryDirectory() as directory:
            cache, coverage = tracker.refresh_liveness(
                ["https://example.invalid/a", "https://example.invalid/b"],
                probe=explode, budget=0, cache_path=Path(directory) / "liveness.json",
            )
        self.assertEqual(cache, {})
        self.assertEqual(coverage["checkedThisRun"], 0)
        self.assertEqual(coverage["staleRemaining"], 2)

    def test_a_failure_is_cached_as_a_result_so_the_next_run_does_not_re_ask(self):
        """The behaviour whose absence put this project's address in CelesTrak's
        firewall: a URL that has never succeeded has no cache entry, so without
        recording the failure the next run asks the same stranger again."""
        calls = []

        def probe(url):
            calls.append(url)
            return {"state": "dead", "status": 404}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liveness.json"
            tracker.refresh_liveness(["https://example.invalid/a"], probe=probe,
                                     budget=10, cache_path=path)
            tracker.refresh_liveness(["https://example.invalid/a"], probe=probe,
                                     budget=10, cache_path=path)
        self.assertEqual(len(calls), 1, "the second run re-asked a question already answered")

    def test_the_budget_is_a_hard_ceiling(self):
        calls = []

        def probe(url):
            calls.append(url)
            return {"state": "live", "status": 200}

        with tempfile.TemporaryDirectory() as directory:
            tracker.refresh_liveness(
                [f"https://example.invalid/{index}" for index in range(50)],
                probe=probe, budget=7, cache_path=Path(directory) / "liveness.json",
            )
        self.assertEqual(len(calls), 7)

    def test_a_probe_that_throws_does_not_take_the_report_down(self):
        def probe(url):
            raise RuntimeError("the internet fell over")

        with tempfile.TemporaryDirectory() as directory:
            cache, _ = tracker.refresh_liveness(
                ["https://example.invalid/a"], probe=probe, budget=1,
                cache_path=Path(directory) / "liveness.json",
            )
        self.assertEqual(cache["https://example.invalid/a"]["state"], "unverifiable")


class LegacyVerdicts(unittest.TestCase):
    def test_a_dns_dead_written_before_the_two_strike_rule_is_downgraded_on_load(self):
        legacy = {"https://example.invalid/a": {"state": "dead", "status": "dns",
                                                "checkedAtEpoch": 1.0}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liveness.json"
            path.write_text(json.dumps(legacy))
            healed = tracker.load_liveness_cache(path)
        entry = healed["https://example.invalid/a"]
        self.assertEqual(entry["state"], "dns-failure")
        self.assertEqual(entry["strikes"], 1)

    def test_a_real_404_is_left_alone(self):
        legacy = {"https://example.invalid/a": {"state": "dead", "status": 404}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liveness.json"
            path.write_text(json.dumps(legacy))
            healed = tracker.load_liveness_cache(path)
        self.assertEqual(healed["https://example.invalid/a"]["state"], "dead")

    def test_the_downgrade_is_idempotent(self):
        once = tracker._normalise_verdict({"state": "dead", "status": "dns"})
        twice = tracker._normalise_verdict(dict(once))
        self.assertEqual(once, twice)


class Ranking(unittest.TestCase):
    def test_prominence_comes_from_the_front_end_not_from_here(self):
        featured = tracker.featured_constellations()
        self.assertIn("GPS", featured)
        self.assertGreater(len(featured), 1)

    def test_the_copy_of_density_rank_has_not_drifted_from_main_ts(self):
        self.assertEqual(tracker.check_density_rank_matches_front_end(), [])

    def test_a_featured_weather_satellite_outranks_an_anonymous_cubesat(self):
        goes = record(name="GOES 16", constellation="GOES", mission="weather",
                      sector="civil", purposeKind="template")
        cubesat = record(name="CUBY 4", constellation=None, mission="other",
                         sector="unknown", purposeKind="template")
        featured = ["GOES"]
        self.assertGreater(tracker.importance(goes, featured, 4)[0],
                           tracker.importance(cubesat, featured, 4)[0])

    def test_every_score_carries_the_reasons_that_produced_it(self):
        goes = record(name="GOES 16", constellation="GOES", mission="weather")
        score, reasons = tracker.importance(goes, ["GOES"], 4)
        self.assertGreater(score, 0)
        self.assertTrue(reasons)

    def test_one_mega_constellation_cannot_own_the_ranking(self):
        """Uncapped, 4,660 identical Starlink cards outrank the site for ever."""
        row = record(constellation="Starlink")
        big = tracker.importance(row, [], 4660)[0]
        moderate = tracker.importance(row, [], 200)[0]
        self.assertEqual(big, moderate)

    def test_an_object_with_no_element_set_is_penalised_because_it_is_not_drawn(self):
        drawn = record()
        undrawn = record(omm={})
        self.assertGreater(tracker.importance(drawn, [], 1)[0],
                           tracker.importance(undrawn, [], 1)[0])

    def test_the_headline_table_shows_both_tiers(self):
        rows = [
            tracker.Graded(record(id=index), [{"dimension": "no-description"}],
                           "c", 900 - index, 1, [])
            for index in range(30)
        ] + [
            tracker.Graded(record(id=1000 + index, constellation=f"C{index}"),
                           [{"dimension": "no-per-object-detail"}], "c", 10, 1, [])
            for index in range(30)
        ]
        picked = tracker.top_objects(rows, limit=20)
        tiers = collections.Counter(tracker.tier_of(entry) for entry in picked)
        self.assertEqual(tiers["missing"], 10)
        self.assertEqual(tiers["generic"], 10,
                         "a global ordering buries every prominent card that merely "
                         "reads weakly, which is the failure this tracker was built after")


class PublishGate(unittest.TestCase):
    def test_the_output_is_not_in_the_publish_allowlist_tree(self):
        self.assertNotIn("artifacts", tracker.DEFAULT_HTML.parts)
        self.assertNotIn("artifacts", tracker.DEFAULT_JSON.parts)
        self.assertEqual(tracker.DEFAULT_HTML.parent.name, "review")
        self.assertEqual(tracker.DEFAULT_JSON.parent.name, "review")

    def test_it_refuses_to_write_into_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts" / "coverage.html"
            with self.assertRaises(SystemExit):
                tracker.main(["--html", str(target), "--json", str(target.with_suffix(".json"))])

    def test_nothing_in_the_front_end_links_to_the_page(self):
        for name in ("index.html", "src/main.ts"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("satellite-coverage", text, f"{name} references the hidden tree")
            self.assertNotIn("data/review", text, f"{name} references the hidden tree")


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = {
            "satellites": [
                record(id=1, name="GOOD ONE"),
                record(id=2, name="BAD ONE", purpose="No public source names this "
                       "spacecraft's payload, so this site does not claim one.",
                       purposeSource=None, purposeKind="template",
                       classificationBasis="name-pattern",
                       classificationConfidence="medium"),
            ],
            "totalAvailable": 2, "taxonomyVersion": "test", "upstreamAsOf": "2026-08-20T00:00:00Z",
        }
        graded = tracker.grade_catalog(catalog, {})
        summary = tracker.summarise(catalog, graded, {"distinctUrls": 0, "cached": 0}, [])
        cls.html = tracker.render(summary, graded)
        cls.summary = summary

    def test_it_says_it_is_operator_only(self):
        self.assertIn("OPERATOR ONLY", self.html)
        self.assertIn("NOT PUBLISHED", self.html)

    def test_it_asks_not_to_be_indexed(self):
        self.assertIn('name="robots"', self.html)
        self.assertIn("noindex", self.html)

    def test_it_carries_no_script_because_the_csp_would_drop_it(self):
        self.assertNotIn("<script", self.html.lower())

    def test_it_explains_that_a_403_is_not_a_dead_link(self):
        self.assertIn("403", self.html)
        self.assertIn("unverifiable", self.html)

    def test_every_dimension_appears_on_the_page_with_its_count(self):
        for dimension in tracker.DIMENSIONS:
            self.assertIn(dimension.key, self.html, dimension.key)
            self.assertIn(dimension.title, self.html, dimension.key)

    def test_the_undescribed_object_is_found_and_the_described_one_is_not(self):
        self.assertEqual(self.summary["objectsWithAnyGap"], 1)
        self.assertEqual(self.summary["objectsClean"], 1)
        self.assertEqual(self.summary["byDimension"]["no-description"]["objects"], 1)


if __name__ == "__main__":
    unittest.main()
