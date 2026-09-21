"""Tests for the literature check.

**No network.** Every test injects a fake transport; the one test that touches
the real one asserts that it refuses. `test_the_default_transport_is_offline`
is the guard that matters: if somebody swaps the default, the suite starts
making outbound requests from a machine that must not do that unattended, and
this test fails first.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.discovery_literature import (
    CLASS_TERMS,
    LiteratureError,
    offline_transport,
    parse_arxiv,
    parse_crossref,
    relevant,
    run_searches,
    search_plan,
    subject_terms,
)
from pipeline.discovery_queue import read_lines

OBJECT_CANDIDATE = {
    "candidateId": "disc-test",
    "class": "orbit-contradicts-catalog",
    "subject": {"kind": "object", "noradId": 41194, "name": "GAOFEN 4"},
}

SHELL_CANDIDATE = {
    "candidateId": "disc-shell",
    "class": "correlated-shell-decay",
    "subject": {"kind": "shell", "perigeeAltitudeKm": [550.0, 600.0]},
}

ARXIV_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <published>2019-04-02T00:00:00Z</published>
    <title>Geometric calibration of GaoFen 4 in geostationary orbit</title>
    <summary>We calibrate the GaoFen 4 area array camera.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/9999.0000v1</id>
    <published>2021-01-01T00:00:00Z</published>
    <title>An unrelated study of galaxy clusters</title>
    <summary>Nothing to do with satellites.</summary>
  </entry>
</feed>
"""

CROSSREF_JSON = json.dumps(
    {
        "message": {
            "items": [
                {
                    "DOI": "10.5194/example",
                    "title": ["ON-ORBIT GEOMETRIC CALIBRATION FOR GaoFen-4"],
                    "issued": {"date-parts": [[2016]]},
                    "container-title": ["ISPRS Archives"],
                },
                {
                    "DOI": "10.1000/other",
                    "title": ["Sea surface wind from Gaofen-3-02"],
                    "issued": {"date-parts": [[2025]]},
                    "container-title": ["Remote Sensing"],
                },
            ]
        }
    }
).encode()


def fake_transport(url: str) -> bytes:
    return ARXIV_XML if "arxiv" in url else CROSSREF_JSON


def exploding_transport(url: str) -> bytes:
    raise LiteratureError("HTTP 503")


class Planning(unittest.TestCase):
    def test_the_plan_narrows_class_terms_by_the_subject(self) -> None:
        plan = search_plan(OBJECT_CANDIDATE)
        queries = [step["query"] for step in plan]
        self.assertTrue(any("GAOFEN" in query for query in queries))
        self.assertTrue(
            any(term in " ".join(queries) for term in CLASS_TERMS["orbit-contradicts-catalog"])
        )

    def test_the_plan_is_data_and_carries_a_url_for_every_arm(self) -> None:
        for step in search_plan(OBJECT_CANDIDATE):
            self.assertIn(step["source"], {"arxiv", "crossref", "ads-manual", "web-manual"})
            self.assertTrue(step["url"].startswith("https://"))
            self.assertTrue(step["why"])

    def test_the_ads_arm_is_present_and_marked_not_run(self) -> None:
        """An unrun search recorded as unrun is honest; omitting it is not."""
        ads = [step for step in search_plan(OBJECT_CANDIDATE) if step["source"] == "ads-manual"]
        self.assertEqual(len(ads), 1)
        self.assertIs(ads[0]["run"], False)
        self.assertIn("adsabs", ads[0]["url"])

    def test_the_manual_arms_are_present_and_never_run_automatically(self) -> None:
        """arXiv and Crossref miss Chinese-language work, proceedings and
        operator pages. Those arms are listed for a person, not automated: a
        blog post is not a publication and a machine that cannot tell would
        quietly close a finding with one."""
        manual = {
            step["source"] for step in search_plan(OBJECT_CANDIDATE) if step.get("run") is False
        }
        self.assertEqual(manual, {"ads-manual", "web-manual"})
        check = run_searches(
            OBJECT_CANDIDATE, transport=fake_transport, delay_seconds=0, sleep=lambda _: None
        )
        not_run = [s for s in check.searches if s["status"] == "not-run"]
        self.assertEqual(len(not_run), 2)
        for search in not_run:
            self.assertTrue(search["reason"])

    def test_a_fragment_is_searched_by_phenomenon_not_by_its_catalogue_label(self) -> None:
        """Observed live: "DELTA high area-to-mass ratio debris solar radiation
        pressure" returned condensed-matter papers on the anomalous Hall
        effect. A catalogue label for a fragment is not a searchable identity,
        so the class terms go unqualified and the name arm is not attempted."""
        fragment = {
            "candidateId": "d",
            "class": "decay-rate-out-of-family",
            "subject": {"kind": "object", "name": "DELTA 1 DEB", "objectType": "DEBRIS"},
        }
        plan = search_plan(fragment)
        for step in plan:
            if step["source"] in ("arxiv", "crossref"):
                self.assertNotIn("DELTA", step["query"])
        skipped = [step for step in plan if step["source"] == "object-name"]
        self.assertEqual(len(skipped), 1)
        self.assertIs(skipped[0]["run"], False)

    def test_a_programme_name_still_narrows_the_class_terms(self) -> None:
        """The other side: a real programme name is exactly what should qualify."""
        named = {
            "candidateId": "g",
            "class": "decay-rate-out-of-family",
            "subject": {"kind": "object", "name": "GAOFEN 4", "objectType": "GEO"},
        }
        queries = [step["query"] for step in search_plan(named) if step["source"] == "arxiv"]
        self.assertTrue(any(query.startswith("GAOFEN") for query in queries))

    def test_a_fragment_is_recognised_without_an_object_type(self) -> None:
        """A candidate rebuilt from an older sweep artifact may carry no type."""
        for name in ("DELTA 1 DEB", "SL-16 R/B", "BREEZE-M DEB (TANK)", "LEASAT 4 PKM"):
            plan = search_plan(
                {"class": "decay-rate-out-of-family", "subject": {"kind": "object", "name": name}}
            )
            self.assertTrue(
                any(step["source"] == "object-name" for step in plan),
                f"{name} was treated as a programme name",
            )

    def test_a_shell_is_searched_by_altitude_and_never_given_a_name(self) -> None:
        terms = subject_terms(SHELL_CANDIDATE)
        self.assertTrue(any("km" in term for term in terms))
        blob = json.dumps(search_plan(SHELL_CANDIDATE))
        self.assertNotIn("noradId", blob)

    def test_the_programme_name_is_searched_as_well_as_the_flight(self) -> None:
        self.assertEqual(subject_terms({"subject": {"kind": "object", "name": "GAOFEN 13 02"}}),
                         ["GAOFEN 13 02", "GAOFEN 13", "GAOFEN"])


class Parsing(unittest.TestCase):
    def test_arxiv_atom(self) -> None:
        results = parse_arxiv(ARXIV_XML)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["year"], "2019")
        self.assertEqual(results[0]["source"], "arxiv")

    def test_crossref_json(self) -> None:
        results = parse_crossref(CROSSREF_JSON)
        self.assertEqual(results[0]["doi"], "10.5194/example")
        self.assertEqual(results[0]["url"], "https://doi.org/10.5194/example")
        self.assertEqual(results[0]["year"], "2016")

    def test_malformed_payloads_raise_rather_than_return_nothing(self) -> None:
        """Silently returning [] would read as 'we searched and found nothing'."""
        with self.assertRaises(LiteratureError):
            parse_arxiv(b"not xml")
        with self.assertRaises(LiteratureError):
            parse_crossref(b"not json")


class Relevance(unittest.TestCase):
    def test_the_flight_number_must_match_not_only_the_programme(self) -> None:
        """The first version marked every GaoFen-4 paper relevant to GAOFEN 13."""
        gaofen4 = {"title": "ON-ORBIT GEOMETRIC CALIBRATION FOR GaoFen-4"}
        self.assertTrue(relevant(gaofen4, OBJECT_CANDIDATE))
        self.assertFalse(
            relevant(gaofen4, {"subject": {"kind": "object", "name": "GAOFEN 13"}})
        )

    def test_every_numeric_token_must_match(self) -> None:
        gaofen302 = {"title": "Sea surface wind from Gaofen-3-02"}
        self.assertFalse(
            relevant(gaofen302, {"subject": {"kind": "object", "name": "GAOFEN 13 02"}})
        )

    def test_a_shell_hit_is_always_kept_for_the_reviewer(self) -> None:
        self.assertTrue(relevant({"title": "anything"}, SHELL_CANDIDATE))


class Running(unittest.TestCase):
    def test_the_default_transport_is_offline(self) -> None:
        """The guard that stops this suite from ever making a request."""
        with self.assertRaises(LiteratureError):
            offline_transport("https://example.invalid/")
        check = run_searches(OBJECT_CANDIDATE, delay_seconds=0, sleep=lambda _: None)
        self.assertFalse(check.found_prior_work)
        statuses = {search["status"] for search in check.searches}
        self.assertEqual(statuses, {"error", "not-run"})

    def test_a_hit_is_found_and_marked(self) -> None:
        check = run_searches(
            OBJECT_CANDIDATE,
            transport=fake_transport,
            delay_seconds=0,
            sleep=lambda _: None,
        )
        self.assertTrue(check.found_prior_work)
        relevant_hits = [hit for hit in check.results if hit["relevant"]]
        self.assertTrue(relevant_hits)
        self.assertTrue(any("GaoFen" in hit["title"] for hit in relevant_hits))

    def test_irrelevant_hits_are_recorded_but_not_counted_as_prior_work(self) -> None:
        check = run_searches(
            {"candidateId": "x", "class": "orbit-contradicts-catalog",
             "subject": {"kind": "object", "name": "NOTHING LIKE THIS 77"}},
            transport=fake_transport,
            delay_seconds=0,
            sleep=lambda _: None,
        )
        self.assertFalse(check.found_prior_work)
        self.assertTrue(check.results, "results are still recorded")
        self.assertFalse(any(hit["relevant"] for hit in check.results))

    def test_an_error_is_recorded_rather_than_swallowed(self) -> None:
        check = run_searches(
            OBJECT_CANDIDATE,
            transport=exploding_transport,
            delay_seconds=0,
            sleep=lambda _: None,
        )
        errored = [search for search in check.searches if search["status"] == "error"]
        self.assertTrue(errored)
        self.assertIn("503", errored[0]["reason"])
        self.assertFalse(check.found_prior_work)

    def test_results_are_deduplicated_across_queries(self) -> None:
        check = run_searches(
            OBJECT_CANDIDATE,
            transport=fake_transport,
            delay_seconds=0,
            sleep=lambda _: None,
        )
        urls = [hit.get("url") for hit in check.results]
        self.assertEqual(len(urls), len(set(urls)))

    def test_every_query_that_ran_is_recorded_with_its_url(self) -> None:
        check = run_searches(
            OBJECT_CANDIDATE,
            transport=fake_transport,
            delay_seconds=0,
            sleep=lambda _: None,
        )
        self.assertEqual(len(check.searches), len(search_plan(OBJECT_CANDIDATE)))
        for search in check.searches:
            self.assertTrue(search["url"])
            self.assertTrue(search["query"])


class Recording(unittest.TestCase):
    def test_a_check_is_written_to_the_ledger_with_its_searches(self) -> None:
        from pipeline.discovery_literature import check_entry
        from pipeline.discovery_queue import QueueEntry

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "literature.jsonl"
            entry = QueueEntry(candidate=OBJECT_CANDIDATE, literature=[], reviews=[])
            check_entry(
                entry,
                transport=fake_transport,
                recorded_by="human:sean",
                literature_path=path,
                sleep=lambda _: None,
            )
            record = read_lines(path)[0]
            self.assertEqual(record["candidateId"], "disc-test")
            self.assertEqual(record["recordedBy"], "human:sean")
            self.assertTrue(record["foundPriorWork"])
            self.assertTrue(record["searches"])
            self.assertIn("absenceMeaning", record)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
