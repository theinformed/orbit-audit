"""The guard that makes a non-existent CelesTrak group fail loudly, once.

NOTHING HERE TOUCHES THE NETWORK. Every body is a captured fixture. celestrak.org
may be reached only from the VPS, direct, and never on a schedule; a test that
checked a group name against the live service would be exactly the impoliteness
this guard exists to prevent, dressed up as diligence.

THE FIXTURE
-----------
``INVALID_QUERY_BODY`` is the real answer, captured from the VPS on 2026-08-18.
CelesTrak returns it with **HTTP 200** and ``Content-Type: text/plain`` even
though ``FORMAT=json`` was requested, which is why a status-code check saw
success, and why five group names this project does not have (``noaa``,
``swarm``, ``molniya``, ``raduga``, ``gorizont``) were requested on a weekly
timer for an unknown length of time with nothing ever reporting a failure.

HOW TO PROVE THIS TEST ACTUALLY TESTS SOMETHING
-----------------------------------------------
Sabotage the guard and watch it go red. In ingest/celestrak_groups.py, make
``looks_like_invalid_query`` return False and delete the JSON-decode raise, then
run this file. The assertions below must fail. They were run that way before
this file was committed; see the commit message. An assertion that passes both
ways is worse than no assertion, and this repo has shipped one before.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest import celestrak_groups as guard  # noqa: E402

# Captured from the VPS, byte for byte, on 2026-08-18. HTTP 200, text/plain.
INVALID_QUERY_BODY = (
    b'Invalid query: "GROUP=swarm&FORMAT=json" (GROUP=swarm not found)'
)

# The shape of a real answer: a JSON array of OMM records.
VALID_BODY = json.dumps([
    {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544,
        "EPOCH": "2026-08-18T12:00:00",
        "MEAN_MOTION": 15.5,
    },
    {
        "OBJECT_NAME": "CSS (TIANHE)",
        "OBJECT_ID": "2021-035A",
        "NORAD_CAT_ID": 48274,
        "EPOCH": "2026-08-18T12:00:00",
        "MEAN_MOTION": 15.6,
    },
]).encode()

GROUP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=swarm&FORMAT=json"
GOOD_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json"


class BodyGuardTests(unittest.TestCase):
    """A 200 is not success. The body decides."""

    def test_invalid_query_body_is_rejected(self):
        with self.assertRaises(guard.InvalidCelestrakGroup) as caught:
            guard.validate_group_body(INVALID_QUERY_BODY, url=GROUP_URL)
        self.assertEqual(caught.exception.group, "swarm")
        self.assertIn("Invalid query", caught.exception.excerpt)

    def test_valid_json_array_passes(self):
        records = guard.validate_group_body(VALID_BODY, url=GOOD_URL)
        self.assertEqual([record["NORAD_CAT_ID"] for record in records], [25544, 48274])

    def test_the_marker_is_matched_case_insensitively_and_only_at_the_head(self):
        self.assertTrue(guard.looks_like_invalid_query(b'INVALID QUERY: "GROUP=x"'))
        # A satellite whose name happened to contain the phrase, a long way into
        # a real payload, must not be mistaken for a refusal.
        buried = json.dumps(
            [{"OBJECT_NAME": "X" * 600 + " invalid query", "NORAD_CAT_ID": 1}]
        ).encode()
        self.assertFalse(guard.looks_like_invalid_query(buried))
        guard.validate_group_body(buried, url=GOOD_URL)

    def test_html_error_page_is_rejected_even_with_a_200(self):
        with self.assertRaises(guard.InvalidCelestrakGroup):
            guard.validate_group_body(b"<html><body>502 Bad Gateway</body></html>", url=GROUP_URL)

    def test_empty_body_is_rejected(self):
        with self.assertRaises(guard.InvalidCelestrakGroup):
            guard.validate_group_body(b"   \n", url=GROUP_URL)

    def test_a_bare_scalar_is_not_records(self):
        with self.assertRaises(guard.InvalidCelestrakGroup):
            guard.validate_group_body(b'"No GP data found"', url=GROUP_URL)

    def test_group_name_is_taken_from_the_url(self):
        self.assertEqual(guard.group_from_url(GROUP_URL), "swarm")
        self.assertEqual(
            guard.group_from_url("https://celestrak.org/satcat/records.php?GROUP=active&FORMAT=JSON"),
            "active",
        )
        self.assertIsNone(guard.group_from_url("https://celestrak.org/satcat/jsonDir.php"))


class LedgerTests(unittest.TestCase):
    """The failure has to outlive the log line that reported it."""

    def setUp(self):
        self.state = Path(tempfile.mkdtemp(prefix="celestrak-ledger-"))
        self.addCleanup(shutil.rmtree, self.state, True)

    def _error(self, group="swarm"):
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=json"
        try:
            guard.validate_group_body(INVALID_QUERY_BODY, url=url, group=group)
        except guard.InvalidCelestrakGroup as error:
            return error
        raise AssertionError("the guard accepted an Invalid query body")

    def test_recording_quarantines_the_group(self):
        self.assertEqual(guard.quarantined_groups(self.state), set())
        guard.record_invalid_group(self.state, self._error(), seen_by="unit test")
        self.assertEqual(guard.quarantined_groups(self.state), {"swarm"})
        row = guard.read_ledger(self.state)["swarm"]
        self.assertEqual(row["count"], 1)
        self.assertIn("Invalid query", row["excerpt"])

    def test_a_second_sighting_counts_rather_than_duplicating(self):
        guard.record_invalid_group(self.state, self._error())
        guard.record_invalid_group(self.state, self._error())
        ledger = guard.read_ledger(self.state)
        self.assertEqual(list(ledger), ["swarm"])
        self.assertEqual(ledger["swarm"]["count"], 2)

    def test_clearing_forgets_it(self):
        guard.record_invalid_group(self.state, self._error())
        guard.record_invalid_group(self.state, self._error("raduga"))
        self.assertEqual(guard.clear_ledger(self.state, "swarm"), ["swarm"])
        self.assertEqual(guard.quarantined_groups(self.state), {"raduga"})
        self.assertEqual(guard.clear_ledger(self.state), ["raduga"])
        self.assertEqual(guard.quarantined_groups(self.state), set())

    def test_an_unwritable_state_directory_does_not_break_the_run(self):
        row = guard.record_invalid_group(self.state / "nope" / "\0bad", self._error())
        self.assertEqual(row["group"], "swarm")

    def test_the_sentence_names_the_group(self):
        guard.record_invalid_group(self.state, self._error())
        sentence = guard.ledger_sentence(guard.read_ledger(self.state))
        self.assertIn("swarm", sentence)
        self.assertIn("REJECTED", sentence)
        self.assertIn("No CelesTrak group", guard.ledger_sentence({}))


class ConfiguredListTests(unittest.TestCase):
    """Offline shape checks. No request is made to find any of this out."""

    def test_the_five_measured_absent_names_are_refused(self):
        for name in ("noaa", "swarm", "molniya", "raduga", "gorizont"):
            with self.subTest(group=name):
                problems = guard.malformed_group_names(["stations", name])
                self.assertTrue(problems, f"{name} was accepted")
                self.assertEqual(problems[0][0], name)

    def test_malformed_names_are_refused(self):
        for name in ("", " stations", "star link", "GROUP=stations", "a/b"):
            with self.subTest(group=name):
                self.assertTrue(guard.malformed_group_names([name]), f"{name!r} was accepted")

    def test_duplicates_are_refused(self):
        self.assertTrue(guard.malformed_group_names(["stations", "stations"]))

    def test_real_names_pass_including_the_one_with_capitals(self):
        self.assertEqual(
            guard.malformed_group_names([
                "science", "geodetic", "amateur", "weather", "resource", "engineering",
                "education", "military", "radar", "cubesat", "other-comm", "stations",
                "gnss", "nnss", "musson", "sarsat", "argos", "dmc", "tdrss",
                "iridium-NEXT", "gps-ops", "other-comm2",
            ]),
            [],
        )

    def test_assert_raises_with_the_offending_name_in_the_message(self):
        with self.assertRaises(ValueError) as caught:
            guard.assert_group_list_is_sane(["stations", "swarm"], where="a list")
        self.assertIn("swarm", str(caught.exception))
        self.assertIn("a list", str(caught.exception))
        guard.assert_group_list_is_sane(["stations"], where="a list")


class MirrorIntegrationTests(unittest.TestCase):
    """The VPS mirror: the first invalid response halts every later request."""

    def setUp(self):
        from ingest import celestrak_mirror  # noqa: PLC0415

        self.mirror = celestrak_mirror
        self.tmp = Path(tempfile.mkdtemp(prefix="celestrak-mirror-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # HALT_MARKER is derived from STATE at import, so it has to be moved
        # explicitly or halt() writes into the real repository.
        for name, value in (
            ("CACHE", self.tmp / "cache"),
            ("STATE", self.tmp / "state"),
            ("HALT_MARKER", self.tmp / "state" / "HALTED.json"),
            ("SATCAT_APPLIED", self.tmp / "state" / "satcat-applied-signature.json"),
            ("LAST_ATTEMPT", self.tmp / "state" / "last-request-at.json"),
            # Added 2026-08-27 with conditional requests. Same reason as
            # HALT_MARKER above: without it the seeded change ledger was written
            # into the real repository, on bigmem, which may not touch this lane.
            ("VALIDATORS", self.tmp / "state" / "http-validators.json"),
        ):
            patch = mock.patch.object(celestrak_mirror, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        for name in ("alert_human", "log"):
            patch = mock.patch.object(celestrak_mirror, name, mock.Mock())
            patch.start()
            self.addCleanup(patch.stop)
        no_sleep = mock.patch.object(celestrak_mirror.time, "sleep", lambda *_: None)
        no_sleep.start()
        self.addCleanup(no_sleep.stop)

    def _serve(self, bodies):
        """Replace the socket, not the guard. Nothing here opens a connection."""
        calls = []

        class Response:
            status = 200

            def __init__(self, body):
                self._body = body

            def read(self, _size=-1):
                body, self._body = self._body, b""
                return body

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def urlopen(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            calls.append(url)
            group = guard.group_from_url(url)
            return Response(bodies.get(group, VALID_BODY))

        return calls, mock.patch.object(self.mirror.DIRECT_OPENER, "open", urlopen)

    def test_a_bad_group_halts_the_run_before_another_group_is_tried(self):
        bad = self.mirror.GROUPS[0]
        self.mirror.CACHE.mkdir(parents=True)
        (self.mirror.CACHE / "satcat-dir.json").write_text("[]")
        calls, patched = self._serve({bad: INVALID_QUERY_BODY})
        with patched:
            code = self.mirror.run()

        self.assertEqual(code, 2)
        self.assertTrue(self.mirror.HALT_MARKER.exists())
        self.assertFalse((self.mirror.CACHE / f"group-{bad}.json").exists(),
                         "an Invalid query body was written to the cache as if it were data")
        self.assertEqual(guard.quarantined_groups(self.mirror.STATE), {bad})
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.mirror.alert_human.called, "nobody was told")

    def test_a_quarantined_group_is_never_requested_again(self):
        bad = self.mirror.GROUPS[0]
        self.mirror.CACHE.mkdir(parents=True)
        (self.mirror.CACHE / "satcat-dir.json").write_text("[]")
        calls, patched = self._serve({bad: INVALID_QUERY_BODY})
        with patched:
            self.mirror.run()
            first = [url for url in calls if guard.group_from_url(url) == bad]
            self.mirror.run()
            again = [url for url in calls if guard.group_from_url(url) == bad]
        self.assertEqual(len(first), 1)
        self.assertEqual(len(again), 1, "a group CelesTrak had already refused was asked again")

    def test_a_bad_satcat_directory_halts_everything(self):
        calls, patched = self._serve({None: INVALID_QUERY_BODY})
        with patched:
            code = self.mirror.run()
        self.assertEqual(code, 2)
        self.assertTrue(self.mirror.HALT_MARKER.exists())

    def test_a_malformed_group_list_refuses_to_query_at_all(self):
        def must_not_be_called(*_args, **_kwargs):
            raise AssertionError("a request was made on a list known to be broken")

        with mock.patch.object(self.mirror, "GROUP_LIST_PROBLEMS", [("swarm", "does not exist")]), \
             mock.patch.object(self.mirror.DIRECT_OPENER, "open", must_not_be_called):
            self.assertEqual(self.mirror.run(), 4)

    def test_the_shipped_group_list_is_well_formed(self):
        self.assertEqual(self.mirror.GROUP_LIST_PROBLEMS, [])


class BuildReleaseIntegrationTests(unittest.TestCase):
    """The publisher: a rejected group is not a transient outage."""

    def setUp(self):
        from pipeline import build_release  # noqa: PLC0415

        self.build = build_release
        self.cache = Path(tempfile.mkdtemp(prefix="celestrak-build-test-"))
        self.addCleanup(shutil.rmtree, self.cache, True)
        patch = mock.patch.object(build_release, "CACHE", self.cache)
        patch.start()
        self.addCleanup(patch.stop)
        no_mirror = mock.patch.object(build_release, "CELESTRAK_MIRROR", self.cache / "absent")
        no_mirror.start()
        self.addCleanup(no_mirror.stop)

    def test_publisher_direct_fetch_is_unconditionally_forbidden(self):
        with self.assertRaisesRegex(RuntimeError, "direct CelesTrak network access is forbidden"):
            self.build.fetch_celestrak(GROUP_URL, 3600, retries=2)

    def test_absent_mirror_never_falls_through_to_network(self):
        with mock.patch.object(self.build, "fetch_bytes", side_effect=AssertionError("network")):
            self.assertEqual(self.build.fetch_celestrak_fleet_memberships(), {})

    def test_a_mirrored_invalid_query_file_is_not_read_as_records(self):
        mirror = self.cache / "mirror"
        mirror.mkdir(parents=True, exist_ok=True)
        (mirror / "group-swarm.json").write_bytes(INVALID_QUERY_BODY)
        (mirror / "group-stations.json").write_bytes(VALID_BODY)
        with mock.patch.object(self.build, "CELESTRAK_MIRROR", mirror):
            self.assertIsNone(self.build.mirror_records("group-swarm.json"))
            self.assertEqual(len(self.build.mirror_records("group-stations.json")), 2)
        self.assertEqual(guard.quarantined_groups(self.cache), {"swarm"})

    def test_the_shipped_group_lists_are_well_formed(self):
        for name in ("CELESTRAK_MISSION_CATEGORY_GROUPS",):
            with self.subTest(list=name):
                self.assertEqual(guard.malformed_group_names(getattr(self.build, name)), [])
        self.assertEqual(guard.malformed_group_names(tuple(self.build.CELESTRAK_FLEET_GROUPS)), [])


class NoNetworkTests(unittest.TestCase):
    """The guard itself must not be able to reach out."""

    def test_the_guard_module_contains_no_fetching_machinery(self):
        source = Path(guard.__file__).read_text()
        for forbidden in ("urlopen", "requests.get", "socket.create_connection", "http.client"):
            self.assertNotIn(forbidden, source, f"{forbidden} appeared in the guard module")


if __name__ == "__main__":
    unittest.main()
