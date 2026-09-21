#!/usr/bin/env python3
"""Tests for the SuperMAG ingest. No network: every response is a fixture.

The things worth testing here are not the happy path. They are the ways this
service fails while looking successful, because `docs/gannon-storm-module-
design.md` §4.1.1 lists SuperMAG by name in its "HTTP 200 is not success"
catalogue, and the very first real run added a case that catalogue did not have.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))
import supermag_ingest as sm  # noqa: E402


def record(tval: float, sme=100.0, sml=-40.0, smu=60.0) -> dict:
    return {"tval": tval, "SME": sme, "SML": sml, "SMU": smu}


def day_of(records) -> bytes:
    return json.dumps(records).encode()


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200) -> None:
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False


class FakeOpener:
    """Answers with a scripted sequence, and records how often it was asked."""

    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def open(self, request, timeout=None):  # noqa: ARG002
        self.calls.append(request.full_url)
        answer = self.responses.pop(0) if self.responses else b"[]"
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, tuple):
            return FakeResponse(answer[0], answer[1])
        return FakeResponse(answer)


class EntityBoundaryTest(unittest.TestCase):
    def test_refuses_any_host_but_bigmem(self):
        for host in ("theinformed-vps", "localhost", "bigmem-pc", ""):
            with self.assertRaises(SystemExit) as caught:
                sm.enforce_entity_boundary(host)
            self.assertIn("REFUSING TO RUN", str(caught.exception))

    def test_allows_bigmem(self):
        sm.enforce_entity_boundary("bigmem-PC")

    def test_the_guard_names_the_same_host_as_the_spacetrack_ingest(self):
        # SuperMAG and space-track are both personal registrations, so they
        # live on the same machine. Two guards that disagree are worse than one.
        source = (
            Path(__file__).resolve().parents[1] / "ingest" / "spacetrack_ingest.py"
        ).read_text()
        self.assertIn(f'SPACETRACK_HOST = "{sm.SUPERMAG_HOST}"', source)


class CredentialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "credentials"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text: str, mode: int = 0o600) -> Path:
        self.path.write_text(text)
        self.path.chmod(mode)
        return self.path

    def test_reads_the_userid(self):
        self.write("# a comment\nSUPERMAG_LOGON=a-userid\n")
        self.assertEqual(sm.load_logon(self.path), "a-userid")

    def test_absent_file_explains_how_to_make_one(self):
        with self.assertRaises(SystemExit) as caught:
            sm.load_logon(self.path)
        self.assertIn("chmod 600", str(caught.exception))

    def test_refuses_a_world_readable_credential(self):
        self.write("SUPERMAG_LOGON=a-userid\n", mode=0o644)
        with self.assertRaises(SystemExit) as caught:
            sm.load_logon(self.path)
        self.assertIn("refusing to read", str(caught.exception))

    def test_refuses_a_file_without_the_key(self):
        self.write("SOMETHING_ELSE=x\n")
        with self.assertRaises(SystemExit):
            sm.load_logon(self.path)


class TwoHundredIsNotSuccessTest(unittest.TestCase):
    """Every one of these arrives as HTTP 200 with a body that is not data."""

    def test_the_documented_invalid_username_body(self):
        with self.assertRaises(sm.Halted) as caught:
            sm.validate_payload(b"ERROR: Invalid username")
        self.assertIn("error body", str(caught.exception))
        # A rejected userid must NEVER be retried - that is the CelesTrak ban.
        self.assertFalse(caught.exception.transient)

    def test_the_php_warning_page_their_backend_actually_served(self):
        # Verbatim shape of what 2024-05-09 returned on 2026-08-09, with a 200.
        body = (
            b"<br />\n<b>Warning</b>:  shell_exec(): Unable to execute "
            b"'/disks/d0510/project/su..."
        )
        with self.assertRaises(sm.Halted) as caught:
            sm.validate_payload(body)
        # Their fault, not ours, so this one may be retried exactly once.
        self.assertTrue(caught.exception.transient)

    def test_an_empty_body(self):
        with self.assertRaises(sm.Halted):
            sm.validate_payload(b"   ")

    def test_a_well_formed_response_with_no_records(self):
        with self.assertRaises(sm.Halted) as caught:
            sm.validate_payload(b"[]")
        self.assertIn("no records", str(caught.exception))

    def test_records_missing_the_indices(self):
        with self.assertRaises(sm.Halted) as caught:
            sm.validate_payload(json.dumps([{"tval": 1.0}]).encode())
        self.assertIn("SME", str(caught.exception))

    def test_an_all_null_series(self):
        # The USGS `type=definitive` failure in another costume: a valid
        # response carrying no measurement at all. Not transient - asking again
        # will not conjure data that does not exist.
        body = json.dumps([record(1.0, sme=None), record(2.0, sme=None)]).encode()
        with self.assertRaises(sm.Halted) as caught:
            sm.validate_payload(body)
        self.assertIn("null", str(caught.exception))
        self.assertFalse(caught.exception.transient)

    def test_an_all_fill_series_is_an_unprocessed_window_not_a_quiet_day(self):
        # Third entry in this service's "200 is not success" catalogue, and the
        # one that got past every check above. Measured live on 2026-08-12:
        # 2026-07-25 and 2026-08-01 each returned 1,440 correctly-shaped records
        # in which every value was 999999, while 2024-05-10 returned 1,440 with
        # none. Stored unguarded, a filled day reads downstream as a real day on
        # which the auroral electrojet was flat.
        body = day_of([record(1.0, sme=999999.0, sml=999999.0, smu=999999.0)] * 4)
        with self.assertRaises(sm.Halted) as caught:
            sm.validate_payload(body)
        self.assertIn("fill", str(caught.exception))
        self.assertIn("not processed", str(caught.exception))

    def test_one_filled_minute_inside_a_real_day_is_still_data(self):
        # The guard is about a window SuperMAG has not computed, not about the
        # ordinary gaps every ground network has. A day with real values in it
        # must survive so those gaps reach `published_series` to become nulls.
        rows = sm.validate_payload(day_of([record(1.0, sme=999999.0), record(2.0)]))
        self.assertEqual(len(rows), 2)

    def test_is_fill_accepts_both_shapes_of_no_value(self):
        for absent in (None, 999999.0, 999999, -999999.0, "nope"):
            self.assertTrue(sm.is_fill(absent), absent)
        for present in (0.0, -4057.6, 120.0):
            self.assertFalse(sm.is_fill(present), present)

    def test_a_good_body_survives(self):
        rows = sm.validate_payload(day_of([record(1.0), record(2.0)]))
        self.assertEqual(len(rows), 2)


class FetchTest(unittest.TestCase):
    def test_a_five_hundred_is_transient_and_a_four_hundred_is_not(self):
        for code, transient in ((503, True), (400, False), (403, False)):
            opener = FakeOpener(
                urllib.error.HTTPError("u", code, "boom", None, None)
            )
            with self.assertRaises(sm.Halted) as caught:
                sm.fetch_window("who", sm.GANNON_START, 60, opener=opener)
            self.assertEqual(caught.exception.transient, transient, code)

    def test_the_userid_is_sent_as_the_logon_parameter(self):
        opener = FakeOpener(day_of([record(1.0)]))
        sm.fetch_window("a-userid", sm.GANNON_START, 60, opener=opener)
        self.assertIn("logon=a-userid", opener.calls[0])


class IngestRangeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.start = dt.datetime(2024, 5, 10, tzinfo=dt.timezone.utc)
        self.end = dt.datetime(2024, 5, 12, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, opener, **kwargs):
        return sm.ingest_range(
            self.start, self.end, root=self.root, logon="who",
            opener=opener, gap_seconds=0, **kwargs
        )

    def test_writes_one_file_per_day(self):
        opener = FakeOpener(day_of([record(1.0)]), day_of([record(2.0)]))
        report = self.run_it(opener)
        self.assertEqual(report["recordsWritten"], 2)
        self.assertEqual(len(opener.calls), 2)
        self.assertTrue(sm.day_path(self.root, dt.date(2024, 5, 10)).exists())
        self.assertTrue(sm.day_path(self.root, dt.date(2024, 5, 11)).exists())

    def test_a_day_already_held_is_never_asked_for_again(self):
        opener = FakeOpener(day_of([record(1.0)]), day_of([record(2.0)]))
        self.run_it(opener)
        again = FakeOpener()
        report = self.run_it(again)
        self.assertEqual(again.calls, [])
        self.assertEqual(len(report["skipped"]), 2)

    def test_a_transient_fault_is_retried_exactly_once_and_then_succeeds(self):
        # The real 2024-05-09 incident: a PHP warning page, then the same day
        # served perfectly moments later.
        opener = FakeOpener(
            b"<br />\n<b>Warning</b>:  shell_exec(): Unable to execute '/disks/...",
            day_of([record(1.0)]),
            day_of([record(2.0)]),
        )
        report = self.run_it(opener)
        self.assertEqual(len(opener.calls), 3)
        self.assertNotIn("halted", report)
        self.assertEqual(report["retried"][0]["day"], "2024-05-10")
        self.assertEqual(report["recordsWritten"], 2)

    def test_a_transient_fault_twice_running_halts(self):
        broken = b"<br />\n<b>Warning</b>:  shell_exec(): Unable to execute"
        opener = FakeOpener(broken, broken, day_of([record(1.0)]))
        report = self.run_it(opener)
        self.assertEqual(len(opener.calls), 2)  # one try, one retry, then stop
        self.assertIn("after one retry", report["halted"]["reason"])

    def test_a_rejected_userid_halts_without_a_single_retry(self):
        opener = FakeOpener(b"ERROR: Invalid username", day_of([record(1.0)]))
        report = self.run_it(opener)
        self.assertEqual(len(opener.calls), 1)
        self.assertIn("error body", report["halted"]["reason"])

    def test_a_halt_stops_the_next_run_until_a_human_clears_it(self):
        self.run_it(FakeOpener(b"ERROR: Invalid username"))
        again = FakeOpener(day_of([record(1.0)]))
        report = self.run_it(again)
        self.assertEqual(again.calls, [])
        self.assertIn("halted", report)
        sm.halt_marker(self.root).unlink()
        cleared = self.run_it(FakeOpener(day_of([record(1.0)]), day_of([record(2.0)])))
        self.assertEqual(cleared["recordsWritten"], 2)

    def test_the_halt_marker_never_records_the_userid(self):
        """The userid is the whole credential and it travels in the query.

        A halt marker is exactly the kind of file that gets pasted into a chat
        window, so it records the path and never the query string.
        """
        self.run_it(FakeOpener(b"ERROR: Invalid username"))
        text = sm.halt_marker(self.root).read_text()
        self.assertNotIn("who", text)
        self.assertNotIn("logon", text)
        self.assertIn("/services/indices.php", text)

    def test_a_failed_day_leaves_no_partial_file_to_be_mistaken_for_data(self):
        opener = FakeOpener(b"ERROR: Invalid username")
        self.run_it(opener)
        self.assertFalse(sm.day_path(self.root, dt.date(2024, 5, 10)).exists())
        self.assertEqual(list(self.root.glob("**/*.next")), [])


class PublishedSeriesTest(unittest.TestCase):
    """What may leave this machine, and in what shape."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.start = dt.datetime(2024, 5, 10, tzinfo=dt.timezone.utc)
        self.end = dt.datetime(2024, 5, 11, tzinfo=dt.timezone.utc)
        minute = self.start.timestamp()
        rows = [
            record(minute + 60 * i, sme=100.0 + i, sml=-40.0 - i) for i in range(60)
        ]
        (self.root / "indices").mkdir(parents=True)
        sm.day_path(self.root, dt.date(2024, 5, 10)).write_text(json.dumps(rows))

    def tearDown(self):
        self.tmp.cleanup()

    def test_decimates_to_the_asked_for_cadence(self):
        series = sm.published_series(
            self.start, self.end, root=self.root, cadence_minutes=5
        )
        self.assertEqual(len(series["samples"]), 12)

    def test_carries_the_citation_that_is_the_condition_of_use(self):
        series = sm.published_series(self.start, self.end, root=self.root)
        self.assertIn("SuperMAG", series["citation"])
        self.assertIn("Gjerloev", series["citation"])
        self.assertIn("not redistributed", series["usage"])

    def test_reports_the_peak_westward_electrojet(self):
        series = sm.published_series(self.start, self.end, root=self.root)
        self.assertEqual(series["peakSml"], min(s["sml"] for s in series["samples"]))

    def test_a_filled_minute_is_published_as_a_gap_and_never_as_a_value(self):
        # A 999999 that survives to a plot is a 999999 nT electrojet, which
        # would dwarf the -4,058 nT the real Gannon storm reached and rescale
        # every axis it touches. It becomes null at this boundary, and it must
        # not be able to win `peakSml` either.
        minute = self.start.timestamp()
        rows = [record(minute + 60 * i, sml=-40.0 - i) for i in range(60)]
        rows[10] = record(minute + 600, sme=999999.0, sml=999999.0, smu=999999.0)
        sm.day_path(self.root, dt.date(2024, 5, 10)).write_text(json.dumps(rows))
        series = sm.published_series(
            self.start, self.end, root=self.root, cadence_minutes=5
        )
        filled = [s for s in series["samples"] if s["t"].endswith("10:00Z")]
        self.assertTrue(filled)
        for sample in filled:
            self.assertIsNone(sample["sml"])
            self.assertIsNone(sample["sme"])
        self.assertLess(series["peakSml"], 0)

    def test_it_returns_values_rather_than_the_mirror(self):
        # Dataset redistribution is the thing JHU/APL did not clear, so the
        # publishable object must not be, or contain, a path into the mirror.
        series = sm.published_series(self.start, self.end, root=self.root)
        blob = json.dumps(series)
        self.assertNotIn(str(self.root), blob)
        self.assertNotIn("indices/", blob)


if __name__ == "__main__":
    unittest.main()
