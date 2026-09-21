"""Tests for the hidden review surface, and for the gate that keeps it hidden.

The important test in this file is `PublishGate`. It does not assert that we
*intend* the page to stay off the site — it runs the real `deploy/publish_data.py`
over a data root that contains the page, and asserts the page is not in the
staged output. That is the same script `pipeline/publish_vps.sh` runs before it
rsyncs, so a passing test here is evidence about production rather than about a
comment.

No network.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline.discovery_page import DEFAULT_OUTPUT, main, render
from pipeline.discovery_queue import HONESTY_LABEL, QueueEntry

ROOT = Path(__file__).resolve().parents[1]

ENTRY = QueueEntry(
    candidate={
        "candidateId": "disc-test",
        "class": "orbit-contradicts-catalog",
        "subject": {"kind": "object", "noradId": 41194, "name": "GAOFEN 4"},
        "headline": "GAOFEN 4 is catalogued as earth-observation, and its own orbit is not "
        "the geometry that mission ordinarily uses.",
        "measured": {"periodMinutes": 1436.13, "inclinationDeg": 0.4841},
        "expected": {"source": "the published orbit-vs-mission table"},
        "margin": "a categorical contradiction",
        "observedWindow": {"from": "2026-08-07T12:00:00Z", "to": "2026-08-07T12:00:00Z"},
        "reproduce": {"command": "python3 -m pipeline.catalog_audit", "inputs": {"noradId": 41194}},
        "alternativeExplanations": ["the label may be wrong"],
        "detectorVersion": "2026-08-07.1",
        "fingerprint": "abcdef0123456789",
        "honesty": HONESTY_LABEL,
    },
    literature=[
        {
            "recordedAt": "2026-08-07T23:00:00Z",
            "recordedBy": "human:sean",
            "toolVersion": "2026-08-07.1",
            "searches": [
                {"source": "crossref", "query": "GAOFEN 4", "status": "ok", "hits": 8,
                 "url": "https://api.crossref.org/works"},
                {"source": "ads-manual", "query": "GAOFEN 4", "status": "not-run", "hits": None,
                 "url": "https://ui.adsabs.harvard.edu/"},
            ],
            "results": [
                {"title": "On-orbit geometric calibration for GaoFen-4", "relevant": True,
                 "source": "crossref", "year": "2016", "url": "https://doi.org/10.5194/x"},
                {"title": "Something else entirely", "relevant": False, "source": "arxiv"},
            ],
            "foundPriorWork": True,
        }
    ],
    reviews=[],
)


class Copy(unittest.TestCase):
    def setUp(self) -> None:
        self.html = render([ENTRY], sweep={"detectorVersion": "2026-08-07.1"})

    def test_it_declares_itself_operator_only(self) -> None:
        self.assertIn("OPERATOR ONLY", self.html)
        self.assertIn("NOT PUBLISHED", self.html)

    def test_it_carries_a_noindex_directive(self) -> None:
        self.assertIn('name="robots"', self.html)
        self.assertIn("noindex", self.html)

    def test_it_never_claims_a_discovery(self) -> None:
        """The site is showing its working, not claiming a result."""
        lowered = self.html.lower()
        for phrase in (
            "we discovered",
            "we have discovered",
            "first detection",
            "previously unreported",
            "never before",
            "new discovery",
            "we found a new",
        ):
            self.assertNotIn(phrase, lowered, f"the page claims a discovery: {phrase!r}")

    def test_the_honesty_label_is_the_code_owned_one(self) -> None:
        self.assertIn("noticed, not something the site discovered", self.html)

    def test_a_hit_is_presented_as_a_result_rather_than_a_failure(self) -> None:
        self.assertIn("Prior work found", self.html)
        self.assertIn("costs nothing to be second", self.html)

    def test_the_searches_are_shown_including_the_one_that_did_not_run(self) -> None:
        self.assertIn("ads-manual", self.html)
        self.assertIn("not-run", self.html)

    def test_the_reproduce_command_is_shown(self) -> None:
        self.assertIn("pipeline.catalog_audit", self.html)

    def test_alternative_explanations_are_shown(self) -> None:
        self.assertIn("the label may be wrong", self.html)

    def test_an_empty_queue_says_so_rather_than_looking_broken(self) -> None:
        html = render([], sweep={})
        self.assertIn("real result, not an error state", html)

    def test_deferrals_are_rendered_as_prominently_as_candidates(self) -> None:
        html = render(
            [],
            sweep={
                "deferrals": [
                    {
                        "class": "correlated-shell-decay",
                        "status": "not-yet-computable",
                        "needs": "two windows",
                        "why": "the diurnal cycle",
                        "have": {"baselineDays": 0.2},
                    }
                ]
            },
        )
        self.assertIn("Detectors that cannot run yet", html)
        self.assertIn("the diurnal cycle", html)

    def test_the_false_alarm_control_is_shown_rather_than_filtered_away(self) -> None:
        html = render(
            [],
            sweep={
                "falseAlarms": {
                    "count": 1,
                    "events": [
                        {"name": "SL-16 R/B", "objectType": "ROCKET BODY",
                         "signature": "along-track-raise", "deltaVMetresPerSecond": 0.0006,
                         "startAt": "2026-08-07T00:00:00Z"}
                    ],
                }
            },
        )
        self.assertIn("Known false alarms", html)
        self.assertIn("SL-16 R/B", html)
        # The page must still call these flags wrong -- but on the strength of
        # the catalogue, not as a law of nature. A fragment cannot burn; a
        # catalogue entry can be wrong or out of date, and that is the one way a
        # listed line could be something else. Asserting the hedge as well as the
        # claim is what stops the sentence drifting back to "by construction".
        self.assertIn("is wrong", html)
        self.assertIn("on the strength of the catalogue", html)
        self.assertNotIn("wrong by construction", html)

    def test_the_boundaries_are_stated_on_the_page(self) -> None:
        self.assertIn("eligibility gate denies", self.html)
        self.assertIn("No automatic publication", self.html)
        self.assertIn("makes no reference to nationality", self.html)


class PublishGate(unittest.TestCase):
    """The gate, asserted against the real publishing script."""

    def test_the_default_output_is_not_inside_the_artifact_tree(self) -> None:
        self.assertNotIn("artifacts", DEFAULT_OUTPUT.parts)
        self.assertEqual(DEFAULT_OUTPUT.parent.name, "review")

    def test_writing_into_the_artifact_tree_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "artifacts" / "discovery-queue.html"
            target.parent.mkdir(parents=True)
            with self.assertRaises(SystemExit):
                main(["--output", str(target)])

    def test_a_truncated_sweep_file_degrades_rather_than_crashing(self) -> None:
        """A sweep takes minutes and is written in place, so a render started
        during one finds a half-written file. The queue is read separately and
        must still render."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            partial = root / "sweep.json"
            partial.write_text('{"candidates": [')
            output = root / "review" / "page.html"
            self.assertEqual(main(["--output", str(output), "--sweep-json", str(partial)]), 0)
            self.assertTrue(output.is_file())
            self.assertIn("Discovery review queue", output.read_text())

    def test_the_real_publisher_does_not_stage_the_review_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, destination = root / "source", root / "destination"
            (source / "artifacts").mkdir(parents=True)
            (source / "review").mkdir(parents=True)

            payload = b"catalog"
            (source / "artifacts" / "catalog.json").write_bytes(payload)
            import hashlib

            (source / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "release": "test",
                        "catalog": {
                            "path": "artifacts/catalog.json",
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        },
                    }
                )
            )
            (source / "review" / "discovery-queue.html").write_text(
                render([ENTRY], sweep={}), encoding="utf-8"
            )
            (source / "review" / "discovery-sweep.json").write_text("{}")

            subprocess.run(
                ["python3", str(ROOT / "deploy" / "publish_data.py"), str(source), str(destination)],
                check=True,
            )

            self.assertTrue((destination / "artifacts" / "catalog.json").is_file())
            self.assertFalse((destination / "review").exists())
            staged = sorted(path.name for path in destination.rglob("*") if path.is_file())
            self.assertNotIn("discovery-queue.html", staged)
            self.assertNotIn("discovery-sweep.json", staged)

    def test_the_live_manifest_does_not_reference_the_review_tree(self) -> None:
        """If this ever fails, the page has become publishable."""
        manifest_path = ROOT / "public" / "data" / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("no local manifest to check")
        blob = manifest_path.read_text()
        self.assertNotIn("review/", blob)
        self.assertNotIn("discovery", blob)

    def test_nothing_in_the_frontend_links_to_the_page(self) -> None:
        """No nav entry, no route, no fetch. Checked against the sources."""
        for name in ("index.html", "src/main.ts", "src/content.ts"):
            path = ROOT / name
            if not path.is_file():
                continue
            text = path.read_text()
            self.assertNotIn("discovery-queue", text, f"{name} references the hidden page")
            self.assertNotIn("data/review", text, f"{name} references the hidden tree")

    def test_there_is_still_no_sitemap_or_robots_file_to_leak_it(self) -> None:
        for name in ("sitemap.xml", "robots.txt"):
            self.assertFalse((ROOT / name).exists(), name)
            self.assertFalse((ROOT / "public" / name).exists(), name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
