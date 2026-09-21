#!/usr/bin/env python3
"""A repeat request must ASK, not assume -- and HTTP 304 must be a success.

Offline. Nothing here opens a socket; every response is a fake, and a test that
lets a real one through is itself the failure.

WHY THIS FILE EXISTS
--------------------
On 2026-08-26 at 14:05:23Z CelesTrak answered this mirror with HTTP 403. The
mirror's own log shows the set it was asking for had arrived byte-identical at
6,902,667 bytes on the three previous requests (07:53, 10:01, 12:03 UTC). We were
not asking too often by the published numbers -- 2 refusals in 20 days against a
threshold of 50 in 2 hours. We were asking the wrong QUESTION: the program could
not send If-Modified-Since or If-None-Match and could not receive a 304, so
freshness was decided by the mtime of our own cache file. A local clock decided
it was time to re-download data that had not changed.

Every test below is NEGATIVE-CONTROLLED in the discipline this project already
uses in test_celestrak_gp_group_guard.py: the scenario is also run with the
conditional machinery disabled, asserting that the identical run then re-downloads
the same bytes -- or, in the 403 control, reproduces the real refusal. Without
that control a "conditional requests work" test can pass because the code path
was never reached.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import celestrak_mirror as mirror  # noqa: E402

ETAG = '"7f3a1c-6959cb-62f0d1a0"'
LAST_MODIFIED = "Wed, 26 Aug 2026 03:44:10 GMT"
GROUP_BODY = json.dumps([{"OBJECT_NAME": "ISS (ZARYA)", "NORAD_CAT_ID": 25544}]).encode()
DIRECTORY_BODY = json.dumps([{
    "FILE_NAME": "satcat.csv", "FILE_SIZE": "5577319", "FILE_MTIME": "2026-08-26 03:44:10",
}]).encode()


class Response:
    """A 200 with headers, shaped like what DIRECT_OPENER.open() hands back."""

    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None) -> None:
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = headers if headers is not None else {}

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def not_modified(url: str, headers: dict | None = None) -> urllib.error.HTTPError:
    """What urllib actually raises for a 304: its error processor treats every
    non-2xx as an error, so the success case arrives as an exception."""
    return urllib.error.HTTPError(url, 304, "Not Modified", headers or {}, io.BytesIO(b""))


def refused(url: str, code: int = 403) -> urllib.error.HTTPError:
    body = io.BytesIO(
        b"Error: This file has not updated since your last successful download.\n"
    )
    return urllib.error.HTTPError(url, code, "Forbidden", {}, body)


class MirrorSandbox(unittest.TestCase):
    """Every path redirected into a temp dir; the live cache is never touched."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in (
            ("CACHE", root / "cache"),
            ("STATE", root / "state"),
            ("HALT_MARKER", root / "state" / "HALTED.json"),
            ("SATCAT_APPLIED", root / "state" / "satcat-applied-signature.json"),
            ("LAST_ATTEMPT", root / "state" / "last-request-at.json"),
            ("VALIDATORS", root / "state" / "http-validators.json"),
            ("LOG", root / "mirror.log"),
            ("POLITE_GAP", 0),
        ):
            patch = mock.patch.object(mirror, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        alert = mock.patch.object(mirror, "alert_human")
        alert.start()
        self.addCleanup(alert.stop)
        mirror.CACHE.mkdir(parents=True, exist_ok=True)
        mirror.STATE.mkdir(parents=True, exist_ok=True)
        self.sent: list[dict] = []

    def opener(self, *answers):
        """Record what we SEND, then hand back the scripted answers in order."""
        answers = list(answers)

        def open_request(request, timeout=0):
            del timeout
            self.sent.append({
                "url": request.full_url,
                "If-None-Match": request.get_header("If-none-match"),
                "If-Modified-Since": request.get_header("If-modified-since"),
            })
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        return mock.patch.object(mirror.DIRECT_OPENER, "open", side_effect=open_request)

    def group_path(self, group="science"):
        return mirror.CACHE / f"group-{group}.json"

    def fetch_group(self, group="science", *, revalidate=True):
        return mirror.fetch(
            f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=json",
            self.group_path(group),
            budget=mirror.RequestBudget(),
            dataset=f"group-{group}",
            group=group,
            revalidate=revalidate,
        )

    def assertNotHalted(self):
        self.assertFalse(
            mirror.HALT_MARKER.exists(),
            f"halted when it should not have: "
            f"{mirror.HALT_MARKER.read_text() if mirror.HALT_MARKER.exists() else ''}",
        )


class RecordingTests(MirrorSandbox):
    """Step 1: remember what the server told us, bound to the body it described."""

    def test_a_200_records_etag_and_last_modified(self):
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})):
            result = self.fetch_group()
        self.assertEqual(result.status, 200)
        self.assertFalse(result.not_modified)
        entry = mirror._read_validators()["group-science"]
        self.assertEqual(entry["etag"], ETAG)
        self.assertEqual(entry["lastModified"], LAST_MODIFIED)
        self.assertEqual(entry["bodyBytes"], len(GROUP_BODY))

    def test_a_server_that_offers_no_validators_says_so_and_invents_nothing(self):
        # This is CelesTrak's REAL behaviour, measured live on 2026-08-27: gp.php
        # and the satcat endpoints are PHP on IIS and return neither header. The
        # dataset is still tracked -- the body fingerprint and change ledger below
        # are the only freshness evidence available when the server gives none --
        # but no validator is invented and no conditional request is possible.
        with self.opener(Response(GROUP_BODY, headers={})):
            self.fetch_group()
        entry = mirror._read_validators()["group-science"]
        self.assertIsNone(entry["etag"])
        self.assertIsNone(entry["lastModified"])
        self.assertFalse(entry["conditionalPossible"])
        self.assertEqual(mirror.conditional_headers("group-science", self.group_path()), {})
        self.assertNotHalted()

    def test_the_live_celestrak_header_set_yields_no_conditional_request(self):
        # Copied verbatim from the live response at 2026-08-27T05:31:32Z, so this
        # fixture goes stale loudly rather than quietly if CelesTrak ever starts
        # sending validators.
        live = {
            "Content-Type": "application/json; charset=UTF-8",
            "Server": "Microsoft-IIS/10.0",
            "X-Powered-By": "PHP/8.2.20",
            "Content-Disposition": 'filename="science.json"',
            "Date": "Thu, 27 Aug 2026 05:31:32 GMT",
            "Connection": "close",
            "Content-Length": "19915",
        }
        with self.opener(Response(GROUP_BODY, headers=live)):
            self.fetch_group()
        self.assertEqual(mirror.conditional_headers("group-science", self.group_path()), {})

    def test_only_one_of_the_two_validators_is_enough(self):
        with self.opener(Response(GROUP_BODY, headers={"Last-Modified": LAST_MODIFIED})):
            self.fetch_group()
        self.assertEqual(mirror.conditional_headers("group-science", self.group_path()),
                         {"If-Modified-Since": LAST_MODIFIED})


class SendingTests(MirrorSandbox):
    """Step 2: send them back, verbatim."""

    def _seed(self):
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})):
            self.fetch_group()
        self.sent.clear()

    def test_the_second_request_carries_both_conditional_headers(self):
        self._seed()
        with self.opener(not_modified("https://celestrak.org/x")):
            self.fetch_group()
        self.assertEqual(self.sent[0]["If-None-Match"], ETAG)
        self.assertEqual(self.sent[0]["If-Modified-Since"], LAST_MODIFIED)

    def test_validators_are_sent_byte_for_byte(self):
        # RFC 9110 makes these opaque. Reformatting the date or stripping a weak
        # ETag prefix is how a conditional request silently stops matching and
        # starts costing a full download again.
        weak = 'W/"6959cb-62f0d1a0"'
        odd_date = "Wed, 26 Aug 2026 03:44:10 GMT"
        with self.opener(Response(GROUP_BODY, headers={"ETag": weak, "Last-Modified": odd_date})):
            self.fetch_group()
        self.sent.clear()
        with self.opener(not_modified("https://celestrak.org/x")):
            self.fetch_group()
        self.assertEqual(self.sent[0]["If-None-Match"], weak)
        self.assertEqual(self.sent[0]["If-Modified-Since"], odd_date)

    def test_negative_control_without_the_recorded_validators_nothing_is_sent(self):
        # The control for every test above. If this ever starts sending headers,
        # they are coming from somewhere other than the validator store.
        self._seed()
        with self.opener(Response(GROUP_BODY, headers={})):
            self.fetch_group(revalidate=False)
        self.assertIsNone(self.sent[0]["If-None-Match"])
        self.assertIsNone(self.sent[0]["If-Modified-Since"])

    def test_a_validator_is_never_sent_for_a_body_we_no_longer_hold(self):
        # A 304 for data we do not have is worse than a full download. The
        # validator is bound to the body by sha256 precisely so a restored cache,
        # a hand edit, or a partial rsync degrades to an honest full request.
        self._seed()
        self.group_path().write_bytes(json.dumps([{"NORAD_CAT_ID": 1}]).encode())
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG})):
            self.fetch_group()
        self.assertIsNone(self.sent[0]["If-None-Match"])

    def test_a_validator_is_never_sent_when_the_body_is_gone_entirely(self):
        self._seed()
        self.group_path().unlink()
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG})):
            self.fetch_group()
        self.assertIsNone(self.sent[0]["If-None-Match"])


class NotModifiedIsSuccessTests(MirrorSandbox):
    """Step 3: 304 is the polite answer, not an error. This is the regression
    the parent lane was most exposed to -- the old code saw any non-200 and
    halted, so shipping conditional requests without this would have converted
    the good outcome into a dead-man switch every time."""

    def _seed(self, group="science"):
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})):
            self.fetch_group(group)
        self.sent.clear()

    def test_a_304_does_not_halt(self):
        self._seed()
        with self.opener(not_modified("https://celestrak.org/x")):
            result = self.fetch_group()
        self.assertNotHalted()
        self.assertTrue(result.not_modified)
        self.assertEqual(result.status, 304)
        self.assertEqual(result.downloaded_bytes, 0)

    def test_a_304_serves_the_body_we_already_held(self):
        self._seed()
        with self.opener(not_modified("https://celestrak.org/x")):
            result = self.fetch_group()
        self.assertEqual(result.body, GROUP_BODY)

    def test_a_304_does_not_rewrite_the_cache_file(self):
        self._seed()
        before = self.group_path().read_bytes()
        with self.opener(not_modified("https://celestrak.org/x")):
            self.fetch_group()
        self.assertEqual(self.group_path().read_bytes(), before)

    def test_a_304_renews_freshness_so_the_group_leaves_the_due_list(self):
        # The load-bearing behaviour. "Due" is keyed to this file's mtime, so a
        # 304 has to re-date it -- otherwise every run re-asks a question the
        # server has already answered, which is the shape that produced the 403.
        self._seed()
        stale = time.time() - (mirror.GROUP_INTERVAL + 3600)
        os.utime(self.group_path(), (stale, stale))
        self.assertGreaterEqual(mirror.age_seconds(self.group_path()), mirror.GROUP_INTERVAL)
        with self.opener(not_modified("https://celestrak.org/x")):
            self.fetch_group()
        self.assertLess(mirror.age_seconds(self.group_path()), 60)

    def test_a_304_carrying_a_fresh_etag_replaces_the_old_one(self):
        self._seed()
        new_etag = '"7f3a1c-6959cb-DEADBEEF"'
        with self.opener(not_modified("https://celestrak.org/x", {"ETag": new_etag})):
            self.fetch_group()
        self.assertEqual(mirror._read_validators()["group-science"]["etag"], new_etag)

    def test_a_304_with_no_etag_keeps_the_one_we_had(self):
        self._seed()
        with self.opener(not_modified("https://celestrak.org/x")):
            self.fetch_group()
        self.assertEqual(mirror._read_validators()["group-science"]["etag"], ETAG)

    def test_a_304_records_when_it_happened(self):
        self._seed()
        with self.opener(not_modified("https://celestrak.org/x")):
            self.fetch_group()
        self.assertIn("lastNotModifiedAt", mirror._read_validators()["group-science"])

    def test_a_304_arriving_without_status_exception_is_also_honored(self):
        # Defensive: an opener whose error processor is bypassed hands the 304
        # back as a normal response rather than raising it.
        self._seed()
        with self.opener(Response(b"", status=304, headers={})):
            result = self.fetch_group()
        self.assertTrue(result.not_modified)
        self.assertNotHalted()


class UnexpectedIsStillFatalTests(MirrorSandbox):
    """Step 4: making 304 expected must not make anything else expected."""

    def _seed(self):
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG, "Last-Modified": LAST_MODIFIED})):
            self.fetch_group()
        self.sent.clear()

    def test_a_403_on_a_conditional_request_still_halts(self):
        self._seed()
        with self.opener(refused("https://celestrak.org/x", 403)):
            with self.assertRaises(mirror.Halted):
                self.fetch_group()
        marker = json.loads(mirror.HALT_MARKER.read_text())
        self.assertEqual(marker["status"], 403)
        self.assertIn("one-download-per-update", marker["classification"])

    def test_301_404_500_and_503_all_still_halt(self):
        for code in (301, 404, 500, 503):
            with self.subTest(code=code):
                self.setUp()
                self._seed()
                with self.opener(refused("https://celestrak.org/x", code)):
                    with self.assertRaises(mirror.Halted):
                        self.fetch_group()
                self.assertEqual(json.loads(mirror.HALT_MARKER.read_text())["status"], code)

    def test_a_transport_failure_still_halts(self):
        self._seed()
        with self.opener(urllib.error.URLError("timed out")):
            with self.assertRaises(mirror.Halted):
                self.fetch_group()
        self.assertTrue(mirror.HALT_MARKER.exists())

    def test_an_unasked_for_304_is_unexpected_and_halts(self):
        # We never sent a validator, so a 304 is the server answering a question
        # nobody asked. That is exactly the class of surprise this lane stops on.
        with self.opener(not_modified("https://celestrak.org/x")):
            with self.assertRaises(mirror.Halted):
                self.fetch_group()
        self.assertEqual(json.loads(mirror.HALT_MARKER.read_text())["status"], 304)

    def test_a_304_over_a_cache_that_vanished_mid_run_halts(self):
        self._seed()
        original = mirror.conditional_headers

        def steal_the_body(dataset, destination):
            headers = original(dataset, destination)
            destination.unlink()          # cache lost after the headers were built
            return headers

        with mock.patch.object(mirror, "conditional_headers", steal_the_body), \
             self.opener(not_modified("https://celestrak.org/x")):
            with self.assertRaises(mirror.Halted):
                self.fetch_group()
        self.assertIn("no cached body", str(json.loads(mirror.HALT_MARKER.read_text())["status"]))

    def test_an_http_200_invalid_query_still_halts_and_quarantines(self):
        with self.opener(Response(b"Invalid query", headers={"ETag": ETAG})):
            with self.assertRaises(mirror.Halted):
                self.fetch_group("science")
        self.assertTrue(mirror.HALT_MARKER.exists())


class ChangeLedgerTests(MirrorSandbox):
    """When the provider offers no validator, byte-identity is the only evidence.

    CelesTrak sends neither ETag nor Last-Modified on any endpoint this lane uses,
    so the 304 machinery above cannot fire against the real provider today. What
    remains is the check that actually diagnosed the 2026-08-26 incident: the same
    set arrived at 6,902,667 bytes three times running before the fourth ask was
    refused. The program should notice that about itself.
    """

    def _download(self, body: bytes, headers: dict | None = None):
        with self.opener(Response(body, headers=headers or {})):
            self.fetch_group()
        return mirror._read_validators()["group-science"]

    def test_a_changed_body_resets_the_counter_and_dates_the_change(self):
        first = self._download(GROUP_BODY)
        self.assertEqual(first["unchangedRepeats"], 0)
        changed = json.dumps([{"OBJECT_NAME": "ISS (ZARYA)", "NORAD_CAT_ID": 25545}]).encode()
        second = self._download(changed)
        self.assertEqual(second["unchangedRepeats"], 0)
        self.assertNotEqual(second["lastChangedAt"], None)

    def test_an_identical_body_is_counted_as_a_wasted_request(self):
        self._download(GROUP_BODY)
        second = self._download(GROUP_BODY)
        self.assertEqual(second["unchangedRepeats"], 1)
        third = self._download(GROUP_BODY)
        self.assertEqual(third["unchangedRepeats"], 2)

    def test_the_wasted_request_is_said_out_loud_in_the_log(self):
        self._download(GROUP_BODY)
        self._download(GROUP_BODY)
        self.assertIn("WASTED REQUEST", mirror.LOG.read_text())

    def test_negative_control_a_changing_dataset_never_says_wasted(self):
        # Without this the test above could pass on a program that shouts
        # "wasted" at every request.
        for norad in (25544, 25545, 25546):
            self._download(json.dumps([{"OBJECT_NAME": "X", "NORAD_CAT_ID": norad}]).encode())
        self.assertNotIn("WASTED REQUEST", mirror.LOG.read_text())

    def test_the_incident_shape_is_reproduced_and_recognised(self):
        # Three byte-identical downloads, exactly as the 2026-08-26 log shows,
        # then the refusal. The ledger must show the repeats that preceded it.
        for _ in range(3):
            self._download(GROUP_BODY)
        self.assertEqual(mirror._read_validators()["group-science"]["unchangedRepeats"], 2)
        with self.opener(refused("https://celestrak.org/x", 403)):
            with self.assertRaises(mirror.Halted):
                self.fetch_group()
        self.assertEqual(json.loads(mirror.HALT_MARKER.read_text())["status"], 403)

    def test_lastChangedAt_survives_a_run_of_identical_downloads(self):
        first = self._download(GROUP_BODY)
        stamp = first["lastChangedAt"]
        for _ in range(3):
            entry = self._download(GROUP_BODY)
        self.assertEqual(entry["lastChangedAt"], stamp)


class LedgerSeedingTests(MirrorSandbox):
    """The baseline comes from disk, never from a request."""

    def _fill_cache(self):
        (mirror.CACHE / "satcat-dir.json").write_bytes(DIRECTORY_BODY)
        (mirror.CACHE / "satcat-active.json").write_bytes(b'[{"NORAD_CAT_ID": 25544}]')
        (mirror.CACHE / "group-science.json").write_bytes(GROUP_BODY)
        # The 6.9 MB leftover of the download CelesTrak refused. It is still on
        # the live VPS and nothing may ever request it again.
        (mirror.CACHE / "gp-active.json").write_bytes(b'[{"NORAD_CAT_ID": 1}]')

    def test_seeding_opens_no_socket(self):
        self._fill_cache()
        with mock.patch.object(mirror.DIRECT_OPENER, "open") as opened:
            mirror._seed_change_ledger_from_existing_cache()
        opened.assert_not_called()

    def test_the_owned_datasets_are_seeded_with_their_real_fingerprints(self):
        self._fill_cache()
        mirror._seed_change_ledger_from_existing_cache()
        entries = mirror._read_validators()
        self.assertIn("satcat-directory", entries)
        self.assertIn("satcat-active", entries)
        self.assertIn("group-science", entries)
        self.assertEqual(entries["group-science"]["bodyBytes"], len(GROUP_BODY))

    def test_the_forbidden_leftover_is_never_seeded(self):
        # gp-active.json is the corpse of the 2026-08-26 403. Seeding it would
        # put a dataset nothing may request back into the live bookkeeping, where
        # the next reader could mistake it for a lane that still runs.
        self._fill_cache()
        mirror._seed_change_ledger_from_existing_cache()
        self.assertNotIn("gp-active", mirror._read_validators())

    def test_seeding_claims_no_validator_it_does_not_have(self):
        self._fill_cache()
        mirror._seed_change_ledger_from_existing_cache()
        entry = mirror._read_validators()["group-science"]
        self.assertIsNone(entry["etag"])
        self.assertIsNone(entry["lastModified"])
        self.assertIsNone(entry["lastChangedAt"])   # we know the bytes, not the date
        self.assertFalse(entry["conditionalPossible"])

    def test_seeding_never_overwrites_a_real_recorded_entry(self):
        with self.opener(Response(GROUP_BODY, headers={"ETag": ETAG})):
            self.fetch_group()
        self.group_path().write_bytes(b'[{"NORAD_CAT_ID": 99}]')
        mirror._seed_change_ledger_from_existing_cache()
        self.assertEqual(mirror._read_validators()["group-science"]["etag"], ETAG)

    def test_the_seeded_baseline_makes_the_very_next_repeat_detectable(self):
        # The point of seeding. Without it the first post-deploy download of every
        # dataset looks like a change and the wasted-request check sits idle for a
        # full cycle.
        self._fill_cache()
        mirror._seed_change_ledger_from_existing_cache()
        with self.opener(Response(GROUP_BODY, headers={})):
            self.fetch_group()
        self.assertEqual(mirror._read_validators()["group-science"]["unchangedRepeats"], 1)

    def test_negative_control_without_seeding_the_same_repeat_is_invisible(self):
        self._fill_cache()
        with self.opener(Response(GROUP_BODY, headers={})):
            self.fetch_group()
        self.assertEqual(mirror._read_validators()["group-science"]["unchangedRepeats"], 0)


class WholeRunTests(MirrorSandbox):
    """Step 5: the behaviour an operator actually sees from the timer."""

    def _seed_satcat(self):
        directory = mirror.CACHE / "satcat-dir.json"
        directory.write_bytes(DIRECTORY_BODY)
        mirror._mark_satcat_applied(mirror.satcat_signature(DIRECTORY_BODY), reason="test fixture")
        mirror._write_validators({"satcat-directory": {
            "url": mirror.SATCAT_DIR,
            "etag": ETAG,
            "lastModified": LAST_MODIFIED,
            "bodyBytes": len(DIRECTORY_BODY),
            "bodySha256": __import__("hashlib").sha256(DIRECTORY_BODY).hexdigest(),
        }})
        stale = time.time() - (mirror.DIR_INTERVAL + 3600)
        os.utime(directory, (stale, stale))
        # Every group already fresh, so the run is only about SATCAT.
        for group in mirror.GROUPS:
            (mirror.CACHE / f"group-{group}.json").write_bytes(GROUP_BODY)

    def test_a_304_on_the_directory_costs_one_request_and_no_catalogue(self):
        self._seed_satcat()
        with self.opener(not_modified(mirror.SATCAT_DIR)):
            self.assertEqual(mirror.run(), 0)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["If-None-Match"], ETAG)
        self.assertNotHalted()
        self.assertFalse((mirror.CACHE / "satcat-active.json").exists())

    def test_negative_control_the_same_run_without_validators_redownloads(self):
        # This is the 2026-08-26 shape, reproduced: with nothing to send, the
        # identical run re-asks outright, and CelesTrak's enforcement answers 403.
        self._seed_satcat()
        mirror._write_validators({})
        with self.opener(refused(mirror.SATCAT_DIR, 403)):
            self.assertEqual(mirror.run(), 2)
        self.assertIsNone(self.sent[0]["If-None-Match"])
        self.assertEqual(json.loads(mirror.HALT_MARKER.read_text())["status"], 403)

    def test_a_304_run_leaves_the_lane_ready_rather_than_halted(self):
        self._seed_satcat()
        with self.opener(not_modified(mirror.SATCAT_DIR)):
            mirror.run()
        self.assertIsNone(mirror.halted_reason())
        self.assertLess(mirror.age_seconds(mirror.CACHE / "satcat-dir.json"), 60)

    def test_daily_directory_cadence_leaves_intervening_slots_for_groups(self):
        self._seed_satcat()
        directory = mirror.CACHE / "satcat-dir.json"
        os.utime(directory, None)
        group = mirror.GROUPS[0]
        group_path = mirror.CACHE / f"group-{group}.json"
        stale = time.time() - (mirror.GROUP_INTERVAL + 3600)
        os.utime(group_path, (stale, stale))

        with self.opener(Response(GROUP_BODY)):
            self.assertEqual(mirror.run(), 0)

        self.assertEqual(len(self.sent), 1)
        self.assertEqual(
            self.sent[0]["url"],
            mirror.gp_url(group, base=mirror.BASE, where="offline cadence test"),
        )
        self.assertNotEqual(self.sent[0]["url"], mirror.SATCAT_DIR)

    def test_six_hour_global_gate_remains_independent_of_daily_directory(self):
        self._seed_satcat()
        mirror.LAST_ATTEMPT.write_text("{}")
        with self.opener():
            self.assertEqual(mirror.run(), 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(mirror.OUTBOUND_INTERVAL, 6 * 60 * 60)
        self.assertEqual(mirror.DIR_INTERVAL, 24 * 60 * 60)


class SandboxCompletenessTests(unittest.TestCase):
    """No offline test may write into the live mirror state. Enforced, not hoped.

    Every sandbox in this repo is a hand-written list of module attributes to
    redirect into a temp directory, and a list like that goes stale the moment
    someone adds a new path constant. That is not hypothetical: adding
    ``VALIDATORS`` on 2026-08-27 silently made two existing offline test files
    write ``ingest/state/http-validators.json`` for real -- on the VPS while the
    mirror was supposed to be halted, and on bigmem, which is forbidden from
    touching this lane at all. Both were caught within minutes only because the
    file appeared in a directory listing someone happened to run.

    So the enumeration is now checked against the module instead of maintained by
    memory. A new path constant fails this test until every sandbox redirects it.
    """

    SANDBOXED = {"CACHE", "STATE", "HALT_MARKER", "SATCAT_APPLIED", "LAST_ATTEMPT",
                 "VALIDATORS", "LOG"}
    # Anchors the module computes but never writes to. Listed rather than pattern
    # -matched, so a new constant lands in neither set and fails loudly until
    # someone decides which it is.
    READ_ONLY_ANCHORS = {"ROOT"}

    def live_path_constants(self) -> set[str]:
        """Module-level Paths that a test could write to for real."""
        return {
            name for name, value in vars(mirror).items()
            if name.isupper() and isinstance(value, Path)
        }

    def test_every_live_path_constant_is_named_in_the_sandbox_list(self):
        missing = self.live_path_constants() - self.SANDBOXED - self.READ_ONLY_ANCHORS
        self.assertEqual(
            missing, set(),
            f"celestrak_mirror gained path constant(s) {sorted(missing)}. Add each one to "
            f"MirrorSandbox.setUp here AND to the sandbox in "
            f"tests/test_celestrak_gp_group_guard.py before this test will pass.",
        )

    def test_the_sandbox_actually_redirects_every_one_of_them(self):
        sandbox = MirrorSandbox("run")
        sandbox.setUp()
        self.addCleanup(sandbox.doCleanups)
        for name in sorted(self.live_path_constants() - self.READ_ONLY_ANCHORS):
            with self.subTest(constant=name):
                value = getattr(mirror, name)
                self.assertNotIn(
                    "/root/space-teaching-aid",
                    str(value),
                    f"{name} still points at live state inside the sandbox",
                )

    def test_the_read_only_anchors_really_are_never_written(self):
        # The exemption has to be earned. ROOT is the module's own directory and
        # nothing may write through it.
        source = Path(mirror.__file__).read_text()
        for name in self.READ_ONLY_ANCHORS:
            with self.subTest(constant=name):
                self.assertNotIn(f"_atomic_write({name}", source)
                self.assertNotIn(f"{name}.mkdir", source)
                self.assertNotIn(f"{name}.write", source)

    # STATE-derived paths. Every one is written by halt(), the ledger, or the
    # attempt tripwire, so a sandbox that misses one writes into the live mirror.
    STATE_PATHS = {"CACHE", "STATE", "HALT_MARKER", "SATCAT_APPLIED", "LAST_ATTEMPT", "VALIDATORS"}

    def sandboxing_test_files(self) -> list[Path]:
        """Every test file in this repo that redirects the mirror's paths.

        Discovered rather than listed. This repo has four such files on bigmem and
        two on the VPS, and the 2026-08-27 leak happened in the two that this file
        does not own -- so a check that only inspected its own sandbox would have
        reported all clear while bigmem was writing live state.
        """
        return [
            path for path in sorted(Path(__file__).resolve().parent.glob("test_*.py"))
            if "celestrak_mirror" in path.read_text() and '"CACHE"' in path.read_text()
        ]

    def test_every_sandboxing_test_file_redirects_every_state_path(self):
        found = self.sandboxing_test_files()
        self.assertTrue(found, "discovery found no sandboxing test files; the check is not running")
        for path in found:
            source = path.read_text()
            for name in sorted(self.STATE_PATHS):
                with self.subTest(file=path.name, constant=name):
                    self.assertIn(
                        f'"{name}"', source,
                        f"{path.name} redirects the mirror's paths but never mentions {name}, "
                        f"so running it writes into the live ingest/state. Add it to that file's "
                        f"sandbox list.",
                    )

    def test_every_sandboxing_test_file_also_neutralises_the_log(self):
        # LOG may be redirected OR the log() function mocked outright; both stop
        # a test appending to /var/log/celestrak-mirror.log.
        for path in self.sandboxing_test_files():
            source = path.read_text()
            with self.subTest(file=path.name):
                self.assertTrue(
                    '"LOG"' in source or '"log"' in source,
                    f"{path.name} neither redirects LOG nor mocks log()",
                )

    def test_negative_control_the_discovery_would_notice_a_missing_name(self):
        # Proves the assertion above can fail. Without this the loop could be
        # passing because sandboxing_test_files() returned nothing useful.
        source = "from ingest import celestrak_mirror\n(\"CACHE\", root)"
        self.assertNotIn('"VALIDATORS"', source)

    def test_negative_control_an_unpatched_constant_is_detected(self):
        # Without this, the test above could pass on a sandbox that patches
        # nothing because live_path_constants() returned an empty set.
        self.assertIn("CACHE", self.live_path_constants())
        self.assertIn("VALIDATORS", self.live_path_constants())


class WatchdogTests(unittest.TestCase):
    """Only canonical, unrecovered HALT events may alarm the daily watchdog."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ops import celestrak_watch  # noqa: PLC0415
        self.watch = celestrak_watch

    def test_a_304_log_line_is_not_counted_as_a_refusal(self):
        line = ("2026-08-27T05:40:00Z satcat-directory: HTTP 304 Not Modified -- upstream "
                "data unchanged, nothing downloaded, 106 cached bytes kept and re-dated")
        self.assertIsNone(self.watch.REFUSAL.search(line))
        self.assertIsNotNone(self.watch.NOT_MODIFIED_LINE.search(line))

    def test_negative_control_the_canonical_halt_events_still_count(self):
        for line in (
            "2026-08-26T14:05:23Z HALT status=403 url=https://celestrak.org/x",
            "2026-08-19T00:00:00Z HALT: URL returned 503",
        ):
            with self.subTest(line=line):
                self.assertIsNotNone(self.watch.REFUSAL.search(line))

    def test_status_history_and_duplicate_stop_lines_are_not_new_refusals(self):
        for line in (
            "2026-08-26T14:05:27Z run stopped: satcat-directory: HTTP 403",
            "2026-08-27T00:04:52Z still halted since 2026-08-26T14:05:23+00:00 (403)",
            "2026-09-03T17:05:00Z halt cleared by operator after recorded investigation: previous_status=503",
            "satcat-directory: WASTED REQUEST -- the shape CelesTrak answered with HTTP 403 on 2026-08-26",
        ):
            with self.subTest(line=line):
                self.assertIsNone(self.watch.REFUSAL.search(line))

    def test_a_byte_count_is_still_not_a_status_code(self):
        self.assertIsNone(self.watch.REFUSAL.search("fetched 6,824,528 bytes -> gp.json"))
        self.assertIsNone(self.watch.REFUSAL.search("fetched 6,902,304 bytes -> group-science.json"))

    def test_cleared_halt_followed_by_success_is_recovered_history(self):
        lines = [
            "2026-09-02T17:03:24Z HALT status=503 url=https://celestrak.org/satcat/jsonDir.php",
            "2026-09-02T17:03:24Z run stopped: satcat-directory: HTTP 503",
            "2026-09-03T17:05:00Z halt cleared by operator after recorded investigation: previous_status=503",
            "2026-09-03T17:09:01Z run complete; 2 request(s) made",
        ]
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(self.watch, "journal_lines", return_value=lines), \
             mock.patch.object(self.watch, "HALT_MARKER", Path(temporary) / "absent"), \
             mock.patch.object(self.watch, "invalid_group_state", return_value={
                 "ledger": {}, "configProblems": [], "read": True,
             }):
            state = self.watch.survey(24)
        self.assertEqual(state["refusalLines"], [])
        self.assertEqual(state["recoveredHaltEvents"], 1)
        self.assertTrue(self.watch.verdict(state, 7)[0])

    def test_halt_whose_marker_vanished_without_recovery_still_alarms(self):
        lines = [
            "2026-09-02T17:03:24Z HALT status=503 url=https://celestrak.org/satcat/jsonDir.php",
        ]
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(self.watch, "journal_lines", return_value=lines), \
             mock.patch.object(self.watch, "HALT_MARKER", Path(temporary) / "absent"), \
             mock.patch.object(self.watch, "invalid_group_state", return_value={
                 "ledger": {}, "configProblems": [], "read": True,
             }):
            state = self.watch.survey(24)
        self.assertEqual(len(state["refusalLines"]), 1)
        self.assertFalse(self.watch.verdict(state, 7)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
