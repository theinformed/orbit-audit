"""Offline tests for the T16a ingest, registered in
`docs/t16a-ingest-registration-20260922.md`.

Nothing here opens a socket. Every outbound call goes through an injected
transport that records what it was asked for, so a test that claims a request
was refused can prove the request was never made rather than assuming it.

Every guard is NEGATIVE-CONTROLLED: the same scenario is run a second time with
that one guard disabled, and the bad behaviour is asserted to reproduce. A
guard test whose code path is never reached passes for the wrong reason, and
this file would rather fail loudly than pass quietly.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import starlink_ephemeris as eph
from tools import supgp_ingest as si

try:
    import sgp4  # noqa: F401

    HAVE_PROPAGATOR = True
except ImportError:  # pragma: no cover
    HAVE_PROPAGATOR = False


# ---------------------------------------------------------------------------
# Fixtures, built here rather than committed, so they cannot drift from the
# assertions that read them.
# ---------------------------------------------------------------------------

EPOCH_A = "2026-09-22T08:00:00.000000"
EPOCH_B = "2026-09-22T14:00:00.000000"


def supgp_record(norad=44713, epoch=EPOCH_A, element_set_no=101, name="STARLINK-1007",
                 classification="C", mean_motion=15.06, mean_anomaly=10.0):
    return {
        "OBJECT_NAME": name,
        "OBJECT_ID": "2019-074A",
        "EPOCH": epoch,
        "MEAN_MOTION": mean_motion,
        "ECCENTRICITY": 0.0001,
        "INCLINATION": 53.05,
        "RA_OF_ASC_NODE": 120.0,
        "ARG_OF_PERICENTER": 80.0,
        "MEAN_ANOMALY": mean_anomaly,
        "EPHEMERIS_TYPE": 0,
        "CLASSIFICATION_TYPE": classification,
        "NORAD_CAT_ID": norad,
        "ELEMENT_SET_NO": element_set_no,
        "REV_AT_EPOCH": 33333,
        "BSTAR": 1.0e-5,
        "MEAN_MOTION_DOT": 1.0e-7,
        "MEAN_MOTION_DDOT": 0,
        "ORIGINATOR": "CELESTRAK",
        # Two fields the standard element-set feed does not carry and the
        # supplemental one does: which input product the fit came from, and the
        # residual of the fit itself.
        "DATA_SOURCE": "SpaceX-E",
        "RMS": 0.0123,
    }


EPHEMERIS_FIXTURE = "\n".join(
    [
        "created:2026-09-22 09:05:43 UTC",
        "ephemeris_start:2026-09-22 08:00:00 UTC ephemeris_stop:2026-09-22 08:02:00 UTC "
        "step_size:60",
        "ephemeris_source:blend",
        "UVW",
        "2026265080000.000 -272.4756692049 -2393.0072798939 6343.2539345128 "
        "7.5597464009 1.0223508256 0.7092230334",
        "4.0000000000e-06 -3.7361597005e-07 9.0000000000e-06 4.2623530866e-11 "
        "2.2116411284e-10 1.6000000000e-05 7.9824047249e-10",
        "-9.0374890925e-10 7.6056375032e-13 1.9276593589e-12 -4.5847017313e-10 "
        "4.0370328554e-10 -1.2696901476e-12 -8.1970535731e-13",
        "5.0500271067e-13 -3.8610978546e-13 1.3918657685e-12 1.6230948867e-09 "
        "-8.9084744844e-16 -1.1360379765e-15 5.4461176295e-12",
        "2026265080100.000 181.3865356929 -2326.2450958667 6371.2394277032 "
        "7.5632193750 1.2022045327 0.2232729581",
        "4.9812379727e-07 -4.3761535350e-07 8.7414821534e-07 6.3191397568e-11 "
        "1.7943536891e-10 1.4171482757e-06 8.9391434292e-10",
        "-1.0452761612e-09 9.4408433898e-13 2.1409639403e-12 -5.0725458276e-10 "
        "4.7165480042e-10 -1.5094042482e-12 -9.2057909432e-13",
        "5.5610058170e-13 -2.3775522865e-13 1.1184321971e-12 1.8430598576e-09 "
        "-4.1397915243e-16 -1.5267659876e-15 5.2105926563e-12",
        "",
    ]
)


class Recorder:
    """An injected transport. It records, and it never reaches a network."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def ok(body: bytes, headers=None) -> si.Response:
    return si.Response(status=200, body=body, headers=headers or {})


def body_for(records) -> bytes:
    return json.dumps(records).encode("utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.roots = si.Roots(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def ledger(self) -> list[dict]:
        if not self.roots.requests_ledger.exists():
            return []
        return [
            json.loads(line)
            for line in self.roots.requests_ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


# ---------------------------------------------------------------------------
# Registration 5.3 -- deduplication
# ---------------------------------------------------------------------------


class Deduplication(Base):
    def test_a_duplicate_epoch_in_one_file_is_archived_once(self):
        """The registered bug: a fixture carrying the same element set twice."""
        rows, _ = si.rows_from_supgp(
            [supgp_record(), supgp_record()],
            "starlink",
            fetched_at_ms=1,
            body_sha256="a" * 64,
            host="test",
        )
        summary = si.ingest_supgp_rows(self.roots.supgp_db, rows)
        self.assertEqual(summary["recordsRead"], 2)
        self.assertEqual(summary["elementsNew"], 1)
        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["rowsAfter"], 1)

    def test_re_ingesting_the_same_file_adds_nothing(self):
        rows, _ = si.rows_from_supgp(
            [supgp_record()], "starlink", fetched_at_ms=1, body_sha256="a" * 64, host="test"
        )
        si.ingest_supgp_rows(self.roots.supgp_db, rows)
        again = si.ingest_supgp_rows(self.roots.supgp_db, rows)
        self.assertEqual(again["elementsNew"], 0)
        self.assertEqual(again["duplicates"], 1)
        self.assertEqual(again["rowsAfter"], 1)

    def test_the_naive_gp_key_loses_a_second_element_set_for_one_object(self):
        """NEGATIVE CONTROL for the registered key.

        The provider states one object can carry several supplemental element
        sets at one time. Under the GP archive's key that is a collision and
        the second set is silently dropped; under the registered key both
        survive. Without this test the registered key is a preference with no
        evidence behind it.
        """
        records = [
            supgp_record(element_set_no=101, mean_anomaly=10.0),
            supgp_record(element_set_no=207, mean_anomaly=11.0),
        ]
        rows, _ = si.rows_from_supgp(
            records, "starlink", fetched_at_ms=1, body_sha256="a" * 64, host="test"
        )

        registered = si.ingest_supgp_rows(
            self.roots.root / "registered.sqlite3", rows, key=si.REGISTERED_KEY
        )
        self.assertEqual(registered["elementsNew"], 2, "both element sets must survive")

        naive = si.ingest_supgp_rows(
            self.roots.root / "naive.sqlite3", rows, key=si.NAIVE_GP_KEY
        )
        self.assertEqual(naive["elementsNew"], 1, "the bad behaviour must reproduce")
        self.assertEqual(naive["duplicates"], 1)

    def test_a_new_epoch_appends_rather_than_replacing(self):
        rows_a, _ = si.rows_from_supgp(
            [supgp_record(epoch=EPOCH_A)], "starlink", fetched_at_ms=1,
            body_sha256="a" * 64, host="test",
        )
        rows_b, _ = si.rows_from_supgp(
            [supgp_record(epoch=EPOCH_B)], "starlink", fetched_at_ms=2,
            body_sha256="b" * 64, host="test",
        )
        si.ingest_supgp_rows(self.roots.supgp_db, rows_a)
        summary = si.ingest_supgp_rows(self.roots.supgp_db, rows_b)
        self.assertEqual(summary["rowsAfter"], 2)

    def test_the_same_object_in_two_sets_is_two_rows(self):
        rows_a, _ = si.rows_from_supgp(
            [supgp_record()], "starlink", fetched_at_ms=1, body_sha256="a" * 64, host="test"
        )
        rows_b, _ = si.rows_from_supgp(
            [supgp_record()], "orbcomm", fetched_at_ms=1, body_sha256="a" * 64, host="test"
        )
        si.ingest_supgp_rows(self.roots.supgp_db, rows_a)
        summary = si.ingest_supgp_rows(self.roots.supgp_db, rows_b)
        self.assertEqual(summary["rowsAfter"], 2)

    def test_a_capture_that_adds_nothing_is_still_written_to_the_ledger(self):
        raw = self.roots.supgp_raw / "2026" / "09" / "sup-gp-starlink-20260922T080000Z.json.gz"
        raw.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(raw, "wb") as handle:
            handle.write(body_for([supgp_record()]))
        si.ingest_supgp_file(self.roots, raw, host="test")
        si.ingest_supgp_file(self.roots, raw, host="test")
        lines = [
            json.loads(line)
            for line in self.roots.captures_ledger.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1]["elementsNew"], 0)
        self.assertEqual(lines[1]["set"], "starlink")


# ---------------------------------------------------------------------------
# Registration 5.2 -- provenance read off the record
# ---------------------------------------------------------------------------


class Provenance(Base):
    def test_the_operator_flag_comes_from_the_classification_field(self):
        rows, notes = si.rows_from_supgp(
            [supgp_record(classification="C")], "starlink",
            fetched_at_ms=7, body_sha256="c" * 64, host="a-host",
        )
        columns = {name: value for name, value in zip(si._COLUMNS, rows[0])}
        self.assertEqual(columns["classification"], "C")
        self.assertEqual(columns["operator_derived"], 1)
        self.assertEqual(columns["prediction"], 1)
        self.assertEqual(columns["covariance"], 0)
        self.assertEqual(columns["source"], "celestrak-supgp")
        self.assertEqual(columns["body_sha256"], "c" * 64)
        self.assertEqual(columns["fetched_at_ms"], 7)
        self.assertEqual(columns["ingest_host"], "a-host")
        self.assertEqual(notes["classificationNotC"], 0)

    def test_a_record_without_the_marker_is_not_relabelled(self):
        """NEGATIVE CONTROL for the flag's grounds.

        If the flag were inferred from the set name it would be 1 here, because
        the set is still the supplemental one. It is read off the record, so it
        is 0, and the record is counted rather than dropped.
        """
        rows, notes = si.rows_from_supgp(
            [supgp_record(classification="U")], "starlink",
            fetched_at_ms=7, body_sha256="c" * 64, host="a-host",
        )
        columns = {name: value for name, value in zip(si._COLUMNS, rows[0])}
        self.assertEqual(columns["operator_derived"], 0)
        self.assertEqual(notes["classificationNotC"], 1)
        self.assertEqual(notes["rejected"], 0)

    def test_a_physically_impossible_element_is_rejected_and_counted(self):
        bad = supgp_record()
        bad["ECCENTRICITY"] = 1.4
        worse = supgp_record(norad=1)
        worse["MEAN_MOTION"] = 0.0
        rows, notes = si.rows_from_supgp(
            [bad, worse, supgp_record(norad=2)], "starlink",
            fetched_at_ms=1, body_sha256="d" * 64, host="test",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(notes["read"], 3)
        self.assertEqual(notes["rejected"], 2)
        self.assertEqual(notes["byReason"]["eccentricity-out-of-range"], 1)
        self.assertEqual(notes["byReason"]["mean-motion-not-positive"], 1)

    def test_the_two_fields_only_this_feed_carries_are_archived_not_dropped(self):
        rows, _ = si.rows_from_supgp(
            [supgp_record()], "starlink", fetched_at_ms=1, body_sha256="f" * 64, host="test"
        )
        columns = {name: value for name, value in zip(si._COLUMNS, rows[0])}
        self.assertEqual(columns["data_source"], "SpaceX-E")
        self.assertAlmostEqual(columns["fit_rms_km"], 0.0123)

    def test_a_record_without_those_fields_stores_null_rather_than_zero(self):
        bare = supgp_record()
        del bare["DATA_SOURCE"]
        del bare["RMS"]
        rows, _ = si.rows_from_supgp(
            [bare], "starlink", fetched_at_ms=1, body_sha256="f" * 64, host="test"
        )
        columns = {name: value for name, value in zip(si._COLUMNS, rows[0])}
        self.assertIsNone(columns["data_source"])
        self.assertIsNone(
            columns["fit_rms_km"], "a missing residual and a residual of zero differ"
        )

    def test_the_post_manoeuvre_marker_survives_verbatim(self):
        rows, _ = si.rows_from_supgp(
            [supgp_record(name="INTELSAT 901 [PM]")], "intelsat",
            fetched_at_ms=1, body_sha256="e" * 64, host="test",
        )
        columns = {name: value for name, value in zip(si._COLUMNS, rows[0])}
        self.assertEqual(columns["object_name"], "INTELSAT 901 [PM]")


# ---------------------------------------------------------------------------
# Registration 3 and 4 -- the route and the budget
# ---------------------------------------------------------------------------


class Etiquette(Base):
    def gate(self, **overrides):
        settings = dict(
            roots=self.roots,
            lane="supgp",
            expected_host=si.SUPGP_HOST,
            interval_seconds=si.SUPGP_INTERVAL_SECONDS,
            requests_per_process=si.SUPGP_REQUESTS_PER_PROCESS,
            gap_seconds=0.0,
            hostname=si.SUPGP_HOST,
        )
        settings.update(overrides)
        return si.RequestGate(**settings)

    def test_an_unverified_set_name_never_reaches_a_socket(self):
        transport = Recorder([])
        with self.assertRaises(si.Refused):
            si.fetch_supgp(
                self.roots, ["oneweb"], transport=transport, hostname=si.SUPGP_HOST
            )
        self.assertEqual(transport.calls, [], "a guessed set name must cost no request")

    def test_the_verified_names_are_exactly_the_registered_five(self):
        self.assertEqual(
            sorted(si.VERIFIED_SUPGP_SETS),
            ["glonass", "gps", "intelsat", "orbcomm", "starlink"],
        )

    def test_the_url_builder_is_the_only_one_and_matches_the_documented_endpoint(self):
        self.assertEqual(
            si.supgp_url("starlink"),
            "https://celestrak.org/NORAD/elements/supplemental/"
            "sup-gp.php?FILE=starlink&FORMAT=json",
        )

    def test_a_wrong_host_refuses_before_the_socket(self):
        transport = Recorder([ok(body_for([supgp_record()]))])
        with self.assertRaises(si.Refused):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname="some-workstation"
            )
        self.assertEqual(transport.calls, [])
        self.assertEqual(self.ledger()[-1]["outcome"], "refused")

    def test_the_host_gate_is_what_stops_it(self):
        """NEGATIVE CONTROL: with only that guard off, the request is made."""
        transport = Recorder([ok(body_for([supgp_record()]))])
        si.fetch_supgp(
            self.roots, ["starlink"], transport=transport,
            hostname="some-workstation", enforce_host=False,
        )
        self.assertEqual(len(transport.calls), 1, "the bad behaviour must reproduce")

    def test_a_second_request_for_one_set_inside_the_interval_refuses(self):
        transport = Recorder([ok(body_for([supgp_record()]))])
        si.fetch_supgp(self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST)
        self.assertEqual(len(transport.calls), 1)
        with self.assertRaises(si.Refused):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=Recorder([ok(b"[]")]),
                hostname=si.SUPGP_HOST,
            )

    def test_the_interval_gate_is_what_stops_it(self):
        """NEGATIVE CONTROL: the same second request goes out with it off."""
        first = Recorder([ok(body_for([supgp_record()]))])
        si.fetch_supgp(self.roots, ["starlink"], transport=first, hostname=si.SUPGP_HOST)
        second = Recorder([ok(body_for([supgp_record()]))])
        si.fetch_supgp(
            self.roots, ["starlink"], transport=second,
            hostname=si.SUPGP_HOST, enforce_interval=False,
        )
        self.assertEqual(len(second.calls), 1, "the bad behaviour must reproduce")

    def test_the_per_process_ceiling_stops_the_fifth_request(self):
        gate = self.gate()
        for index in range(si.SUPGP_REQUESTS_PER_PROCESS):
            gate.check(f"set{index}")
            gate.spend(f"set{index}")
        with self.assertRaises(si.Refused):
            gate.check("set-over-the-line")

    def test_the_ceiling_gate_is_what_stops_it(self):
        gate = self.gate(enforce_ceiling=False)
        for index in range(si.SUPGP_REQUESTS_PER_PROCESS + 1):
            gate.check(f"set{index}")
            gate.spend(f"set{index}")
        self.assertEqual(
            gate.spent, si.SUPGP_REQUESTS_PER_PROCESS + 1, "the bad behaviour must reproduce"
        )

    def test_the_attempt_is_written_before_the_socket_so_a_crash_buys_no_retry(self):
        transport = Recorder([OSError("connection reset")])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )
        book = si._read_json(self.roots.state / "last-request-at-supgp.json", {})
        self.assertIn("starlink", book)

    def test_without_pre_recording_a_crash_leaves_no_trace(self):
        """NEGATIVE CONTROL for writing the timestamp first."""
        transport = Recorder([OSError("connection reset")])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport,
                hostname=si.SUPGP_HOST, record_attempt_before_socket=False,
            )
        book = si._read_json(self.roots.state / "last-request-at-supgp.json", {})
        self.assertNotIn("starlink", book, "the bad behaviour must reproduce")

    def test_a_transport_failure_halts_and_does_not_retry(self):
        transport = Recorder([OSError("connection reset")])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )
        self.assertEqual(len(transport.calls), 1, "exactly one attempt, never a retry")
        self.assertIsNotNone(si.halted(self.roots))

    def test_a_halt_marker_makes_the_next_run_socket_free(self):
        si.write_halt(self.roots, "an earlier refusal", {})
        transport = Recorder([ok(body_for([supgp_record()]))])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )
        self.assertEqual(transport.calls, [], "a halted run must open zero sockets")

    def test_the_halt_gate_is_what_stops_it(self):
        si.write_halt(self.roots, "an earlier refusal", {})
        transport = Recorder([ok(body_for([supgp_record()]))])
        si.fetch_supgp(
            self.roots, ["starlink"], transport=transport,
            hostname=si.SUPGP_HOST, enforce_halt=False,
        )
        self.assertEqual(len(transport.calls), 1, "the bad behaviour must reproduce")

    def test_every_unexpected_status_halts(self):
        for status in (301, 403, 404, 500, 503):
            with self.subTest(status=status):
                roots = si.Roots(Path(tempfile.mkdtemp()))
                transport = Recorder([si.Response(status=status, body=b"x", headers={})])
                with self.assertRaises(si.Halted):
                    si.fetch_supgp(
                        roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
                    )
                self.assertIsNotNone(si.halted(roots))

    def test_an_unsolicited_not_modified_still_halts(self):
        transport = Recorder([si.Response(status=304, body=b"", headers={})])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )

    def test_an_empty_body_halts(self):
        transport = Recorder([ok(b"")])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )

    def test_a_body_over_the_ceiling_halts(self):
        transport = Recorder([ok(b"x" * (si.BODY_CEILING_BYTES + 1))])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )

    def test_a_body_that_is_not_an_array_halts(self):
        transport = Recorder([ok(b'{"Invalid query": true}')])
        with self.assertRaises(si.Halted):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST
            )
        self.assertIsNotNone(si.halted(self.roots))

    def test_a_byte_identical_body_is_logged_as_a_wasted_request(self):
        body = body_for([supgp_record()])
        si.fetch_supgp(
            self.roots, ["starlink"], transport=Recorder([ok(body)]), hostname=si.SUPGP_HOST
        )
        si.fetch_supgp(
            self.roots, ["starlink"], transport=Recorder([ok(body)]),
            hostname=si.SUPGP_HOST, enforce_interval=False,
        )
        notes = [line.get("note") for line in self.ledger() if line["outcome"] == "ok"]
        self.assertIsNone(notes[0])
        self.assertIn("WASTED REQUEST", notes[1])

    def test_no_validator_is_sent_when_none_was_ever_seen(self):
        transport = Recorder([ok(body_for([supgp_record()]))])
        si.fetch_supgp(self.roots, ["starlink"], transport=transport, hostname=si.SUPGP_HOST)
        self.assertEqual(transport.calls[0][1], {})

    def test_a_validator_is_sent_only_when_it_is_bound_to_the_body_we_hold(self):
        body = body_for([supgp_record()])
        si.fetch_supgp(
            self.roots, ["starlink"],
            transport=Recorder([ok(body, {"etag": '"abc"'})]), hostname=si.SUPGP_HOST,
        )
        second = Recorder([si.Response(status=304, body=b"", headers={})])
        si.fetch_supgp(
            self.roots, ["starlink"], transport=second,
            hostname=si.SUPGP_HOST, enforce_interval=False,
        )
        self.assertEqual(second.calls[0][1], {"If-None-Match": '"abc"'})

        # Now break the binding: the stored hash no longer matches the body we
        # hold, so the validator must not be sent and the request degrades to
        # an honest full one rather than a false not-modified.
        path = self.roots.state / "bodies-supgp.json"
        book = si._read_json(path, {})
        book["starlink"]["sha256"] = "0" * 64
        si._write_json(path, book)
        third = Recorder([ok(body)])
        si.fetch_supgp(
            self.roots, ["starlink"], transport=third,
            hostname=si.SUPGP_HOST, enforce_interval=False,
        )
        self.assertEqual(third.calls[0][1], {})

    def test_the_ledger_records_a_line_for_every_attempt_and_every_refusal(self):
        si.fetch_supgp(
            self.roots, ["starlink"], transport=Recorder([ok(body_for([supgp_record()]))]),
            hostname=si.SUPGP_HOST,
        )
        with self.assertRaises(si.Refused):
            si.fetch_supgp(
                self.roots, ["starlink"], transport=Recorder([]), hostname=si.SUPGP_HOST
            )
        outcomes = [line["outcome"] for line in self.ledger()]
        self.assertEqual(outcomes, ["started", "ok", "refused"])

    def test_the_starlink_lane_refuses_on_the_wrong_host(self):
        transport = Recorder([ok(b"one.txt\n")])
        with self.assertRaises(si.Refused):
            si.fetch_starlink(self.roots, limit=1, transport=transport, hostname="a-vps")
        self.assertEqual(transport.calls, [])

    def test_the_starlink_run_refuses_a_limit_over_the_registered_ceiling(self):
        with self.assertRaises(si.Refused):
            si.fetch_starlink(
                self.roots, limit=si.STARLINK_FILES_PER_RUN + 1,
                transport=Recorder([]), hostname=si.STARLINK_HOST,
            )

    def test_the_manifest_sample_is_deterministic_and_spread(self):
        names = [f"file{index}" for index in range(1000)]
        first = si.sample_manifest(names, 10)
        second = si.sample_manifest(names, 10)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)
        self.assertEqual(first[0], "file0")
        self.assertEqual(first[-1], "file900")
        self.assertNotEqual(first, names[:10], "a prefix is a block, not a sample")

    def test_the_manifest_sample_returns_everything_when_it_is_small(self):
        self.assertEqual(si.sample_manifest(["a", "b"], 10), ["a", "b"])

    def test_a_halt_is_archived_rather_than_deleted_when_cleared(self):
        si.write_halt(self.roots, "a refusal", {})
        destination = si.clear_halt(self.roots, "investigated, reason recorded")
        self.assertTrue(destination.exists())
        self.assertIsNone(si.halted(self.roots))
        archived = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(archived["clearedBy"], "investigated, reason recorded")

    def test_clearing_a_halt_that_is_not_there_refuses(self):
        with self.assertRaises(si.Refused):
            si.clear_halt(self.roots, "nothing to clear")

    def test_the_outermost_guard_on_a_foreign_host_is_the_host_gate(self):
        """A wrapper that sees zero concludes the fetch succeeded.

        Run anywhere that is not the fetch host -- which is everywhere a test
        runs -- the host gate is the first thing to fire, and the status is
        non-zero.
        """
        si.write_halt(self.roots, "an earlier refusal", {})
        code = si.cli(
            [
                "--root", str(self.roots.root),
                "fetch-supgp", "starlink",
                "--other-lane-attempts-24h", "0",
            ]
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(code, 2)

    def test_a_halt_carries_its_own_exit_status(self):
        original = si.main

        def raise_halt(argv=None):
            raise si.Halted("a halt marker is in place")

        si.main = raise_halt
        try:
            self.assertEqual(si.cli([]), 3)
        finally:
            si.main = original

    def test_an_unverified_name_also_leaves_a_non_zero_exit_status(self):
        code = si.cli(
            [
                "--root", str(self.roots.root),
                "fetch-supgp", "oneweb",
                "--other-lane-attempts-24h", "0",
            ]
        )
        self.assertEqual(code, 2)

    def test_the_combined_ceiling_refuses_before_any_fetch(self):
        code = si.main(
            [
                "--root", str(self.roots.root),
                "fetch-supgp", "starlink", "orbcomm",
                "--other-lane-attempts-24h", "6",
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.ledger(), [], "nothing may be logged, nothing was asked")


# ---------------------------------------------------------------------------
# Registration 2.2 -- the operator ephemeris reader
# ---------------------------------------------------------------------------


class EphemerisReader(Base):
    def write(self, text=EPHEMERIS_FIXTURE, name="MEME_1_STARLINK-1007_x_Operational_y_"
                                                  "UNCLASSIFIED.txt") -> Path:
        path = self.roots.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="ascii")
        return path

    def test_the_header_is_read_exactly(self):
        ephemeris = eph.read(self.write())
        self.assertEqual(ephemeris.header.step_seconds, 60)
        self.assertEqual(ephemeris.header.source, "blend")
        self.assertEqual(ephemeris.header.covariance_frame, "UVW")
        self.assertEqual(
            ephemeris.header.start,
            dt.datetime(2026, 9, 22, 8, 0, tzinfo=dt.timezone.utc),
        )

    def test_the_day_of_year_epoch_token_resolves_to_the_right_calendar_day(self):
        self.assertEqual(
            eph.parse_epoch_token("2026265080000.000"),
            dt.datetime(2026, 9, 22, 8, 0, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(
            eph.parse_epoch_token("2026001000000.000"),
            dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc),
        )

    def test_a_token_of_the_wrong_width_raises_rather_than_being_split_somehow(self):
        for bad in ("202626508000.000", "20262650800000.000", "abcd265080000.0"):
            with self.subTest(token=bad):
                with self.assertRaises(eph.EphemerisFormatError):
                    eph.parse_epoch_token(bad)

    def test_twenty_one_covariance_terms_are_read_per_record(self):
        ephemeris = eph.read(self.write())
        self.assertEqual(len(ephemeris.records), 2)
        for record in ephemeris.records:
            self.assertEqual(len(record.covariance), 21)

    def test_the_diagonal_maps_to_the_lower_triangle_positions(self):
        ephemeris = eph.read(self.write())
        sigma = ephemeris.records[0].position_sigma_km
        # 4e-6, 9e-6 and 1.6e-5 square-kilometres are 2 mm, 3 mm and 4 mm.
        self.assertAlmostEqual(sigma[0] * 1000.0, 2.0, places=6)
        self.assertAlmostEqual(sigma[1] * 1000.0, 3.0, places=6)
        self.assertAlmostEqual(sigma[2] * 1000.0, 4.0, places=6)

    def test_a_negative_variance_raises_rather_than_being_square_rooted(self):
        broken = EPHEMERIS_FIXTURE.replace("4.0000000000e-06", "-4.0000000000e-06", 1)
        with self.assertRaises(eph.EphemerisFormatError):
            eph.read(self.write(broken, name="broken.txt")).records[0].position_sigma_km

    def test_a_truncated_record_raises_rather_than_being_skipped(self):
        lines = EPHEMERIS_FIXTURE.rstrip("\n").splitlines()
        with self.assertRaises(eph.EphemerisFormatError):
            eph.read(self.write("\n".join(lines[:-1]) + "\n", name="truncated.txt"))

    def test_a_covariance_line_of_the_wrong_width_raises(self):
        broken = EPHEMERIS_FIXTURE.replace("7.9824047249e-10", "7.9824047249e-10 1.0", 1)
        with self.assertRaises(eph.EphemerisFormatError):
            eph.read(self.write(broken, name="wide.txt"))

    def test_a_file_with_a_header_and_no_records_raises(self):
        header = "\n".join(EPHEMERIS_FIXTURE.splitlines()[:4]) + "\n"
        with self.assertRaises(eph.EphemerisFormatError):
            eph.read(self.write(header, name="headeronly.txt"))

    def test_the_spacecraft_name_is_the_only_join_the_filename_offers(self):
        self.assertEqual(
            eph.spacecraft_name(
                "MEME_100001_STARLINK-38128_2650853_Operational_1474361640_UNCLASSIFIED.txt"
            ),
            "STARLINK-38128",
        )
        self.assertIsNone(eph.spacecraft_name("MEME_1_2650853_Operational_x.txt"))

    def test_the_summary_records_the_frame_without_naming_its_axes(self):
        summary = si.summarise_ephemeris(self.write(), leads_hours=(0,))
        self.assertEqual(summary["covarianceFrame"], "UVW")
        self.assertEqual(summary["records"], 2)
        self.assertEqual(len(summary["sigmas"]), 1)
        self.assertAlmostEqual(summary["sigmas"][0]["sigmaAxis1M"], 2.0, places=6)

    def test_a_lead_beyond_the_span_contributes_nothing_rather_than_the_last_record(self):
        summary = si.summarise_ephemeris(self.write(), leads_hours=(0, 72))
        self.assertEqual([row["leadHours"] for row in summary["sigmas"]], [0])

    def test_an_ingested_file_carries_its_provenance_into_the_database(self):
        path = self.write()
        summary = si.ingest_starlink_file(
            self.roots, path, names={"STARLINK-1007": 44713}, host="test"
        )
        self.assertEqual(summary["norad"], 44713)
        connection = sqlite3.connect(self.roots.starlink_db)
        try:
            row = connection.execute(
                "SELECT operator_derived, prediction, covariance, source, ingest_host, norad "
                "FROM ephemeris_file"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row, (1, 1, 1, "spacex-starlink-ephemeris", "test", 44713))

    def test_an_unresolved_spacecraft_name_is_archived_as_null_not_guessed(self):
        path = self.write()
        summary = si.ingest_starlink_file(self.roots, path, names={}, host="test")
        self.assertIsNone(summary["norad"])


# ---------------------------------------------------------------------------
# Registration 7 -- the comparison
# ---------------------------------------------------------------------------


class Comparison(unittest.TestCase):
    def test_a_pure_radial_offset_projects_onto_radial_alone(self):
        reference_r = (7000.0, 0.0, 0.0)
        reference_v = (0.0, 7.5, 0.0)
        radial, along, normal = si.rtn_difference(
            reference_r, reference_v, (7000.1, 0.0, 0.0)
        )
        self.assertAlmostEqual(radial, 100.0, places=6)
        self.assertAlmostEqual(along, 0.0, places=6)
        self.assertAlmostEqual(normal, 0.0, places=6)

    def test_a_pure_along_track_offset_projects_onto_along_track_alone(self):
        reference_r = (7000.0, 0.0, 0.0)
        reference_v = (0.0, 7.5, 0.0)
        radial, along, normal = si.rtn_difference(
            reference_r, reference_v, (7000.0, 0.2, 0.0)
        )
        self.assertAlmostEqual(radial, 0.0, places=6)
        self.assertAlmostEqual(along, 200.0, places=6)
        self.assertAlmostEqual(normal, 0.0, places=6)

    def test_the_normal_axis_follows_the_angular_momentum(self):
        reference_r = (7000.0, 0.0, 0.0)
        reference_v = (0.0, 7.5, 0.0)
        _, _, normal = si.rtn_difference(reference_r, reference_v, (7000.0, 0.0, 0.05))
        self.assertAlmostEqual(normal, 50.0, places=6)

    def test_quantiles_are_defined_here_rather_than_inherited(self):
        values = [float(index) for index in range(101)]
        result = si.quantiles(values)
        self.assertAlmostEqual(result["p05"], 5.0)
        self.assertAlmostEqual(result["p50"], 50.0)
        self.assertAlmostEqual(result["p95"], 95.0)

    def test_a_set_below_the_floor_gets_counts_and_no_quantiles(self):
        paired = [
            {"norad": index, "gapSeconds": 0.0, "radialM": 1.0, "alongTrackM": 2.0,
             "crossTrackM": 3.0}
            for index in range(si.MINIMUM_OBJECTS_FOR_QUANTILES - 1)
        ]
        summary = si.summarise_pairs(paired, "tiny")
        self.assertIsNone(summary["quantiles"])
        self.assertIn("below the registered floor", summary["note"])

    def test_a_set_at_the_floor_gets_quantiles(self):
        paired = [
            {"norad": index, "gapSeconds": 3600.0, "radialM": float(index),
             "alongTrackM": float(index), "crossTrackM": 0.0}
            for index in range(si.MINIMUM_OBJECTS_FOR_QUANTILES)
        ]
        summary = si.summarise_pairs(paired, "just enough")
        self.assertIsNotNone(summary["quantiles"])
        self.assertEqual(summary["n"], si.MINIMUM_OBJECTS_FOR_QUANTILES)

    @unittest.skipUnless(HAVE_PROPAGATOR, "the propagation library is not installed")
    def test_an_element_set_propagated_to_its_own_epoch_differs_from_itself_by_zero(self):
        element = si.MeanElements(
            norad=44713,
            epoch=dt.datetime(2026, 9, 22, 8, 0, tzinfo=dt.timezone.utc),
            mean_motion=15.06, eccentricity=0.0001, inclination=53.05,
            raan=120.0, arg_perigee=80.0, mean_anomaly=10.0, bstar=1.0e-5,
        )
        code, position, velocity = si.propagate(element, element.epoch)
        self.assertEqual(code, 0)
        radial, along, normal = si.rtn_difference(position, velocity, position)
        self.assertAlmostEqual(radial, 0.0, places=9)
        self.assertAlmostEqual(along, 0.0, places=9)
        self.assertAlmostEqual(normal, 0.0, places=9)

    @unittest.skipUnless(HAVE_PROPAGATOR, "the propagation library is not installed")
    def test_a_known_mean_anomaly_offset_shows_up_along_track_and_not_radially(self):
        base = dict(
            norad=44713,
            epoch=dt.datetime(2026, 9, 22, 8, 0, tzinfo=dt.timezone.utc),
            mean_motion=15.06, eccentricity=0.0, inclination=53.05,
            raan=120.0, arg_perigee=0.0, bstar=0.0,
        )
        a = si.MeanElements(mean_anomaly=10.0, **base)
        b = si.MeanElements(mean_anomaly=10.001, **base)
        _, r_a, v_a = si.propagate(a, a.epoch)
        _, r_b, _ = si.propagate(b, a.epoch)
        radial, along, normal = si.rtn_difference(r_a, v_a, r_b)
        self.assertGreater(abs(along), 100.0)
        self.assertLess(abs(radial), 1.0)
        self.assertLess(abs(normal), 1.0)

    @unittest.skipUnless(HAVE_PROPAGATOR, "the propagation library is not installed")
    def test_an_object_with_no_counterpart_is_counted_not_dropped_silently(self):
        element = si.MeanElements(
            norad=99999,
            epoch=dt.datetime(2026, 9, 22, 8, 0, tzinfo=dt.timezone.utc),
            mean_motion=15.06, eccentricity=0.0001, inclination=53.05,
            raan=120.0, arg_perigee=80.0, mean_anomaly=10.0, bstar=1.0e-5,
        )
        result = si.compare_set([element], {})
        self.assertEqual(result["paired"], [])
        self.assertEqual(result["excluded"]["noGpRecord"], 1)

    @unittest.skipUnless(HAVE_PROPAGATOR, "the propagation library is not installed")
    def test_an_epoch_gap_over_the_ceiling_is_excluded_and_counted(self):
        epoch = dt.datetime(2026, 9, 22, 8, 0, tzinfo=dt.timezone.utc)
        shared = dict(
            mean_motion=15.06, eccentricity=0.0001, inclination=53.05,
            raan=120.0, arg_perigee=80.0, mean_anomaly=10.0, bstar=1.0e-5,
        )
        supplemental = si.MeanElements(norad=44713, epoch=epoch, **shared)
        stale = si.MeanElements(
            norad=44713, epoch=epoch - dt.timedelta(hours=30), **shared
        )
        result = si.compare_set([supplemental], {44713: stale})
        self.assertEqual(result["paired"], [])
        self.assertEqual(result["excluded"]["epochGapOverCeiling"], 1)


class SeveralElementSetsForOneObject(unittest.TestCase):
    def test_the_latest_epoch_wins_and_the_choice_is_counted(self):
        records = [
            supgp_record(epoch=EPOCH_A, element_set_no=101, mean_anomaly=10.0),
            supgp_record(epoch=EPOCH_B, element_set_no=207, mean_anomaly=11.0),
            supgp_record(norad=1, epoch=EPOCH_A, element_set_no=5),
        ]
        elements, multiple = si.latest_per_object(records)
        self.assertEqual(len(elements), 2)
        self.assertEqual(multiple, 1, "the choice must be counted, not made silently")
        chosen = {element.norad: element for element in elements}
        self.assertEqual(chosen[44713].mean_anomaly, 11.0)

    def test_an_unreadable_record_is_passed_over_rather_than_crashing_the_run(self):
        elements, _ = si.latest_per_object([{"NORAD_CAT_ID": "not a number"}])
        self.assertEqual(elements, [])


class CovarianceQuantiles(Base):
    def test_a_sample_below_the_floor_reports_counts_and_no_quantiles(self):
        path = self.roots.root / "one.txt"
        path.write_text(EPHEMERIS_FIXTURE, encoding="ascii")
        result = si.starlink_covariance_quantiles([path])
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["covarianceFrames"], ["UVW"])
        self.assertEqual(result["ephemerisSources"], ["blend"])
        entry = result["byLeadHours"]["0"]
        self.assertEqual(entry["n"], 1)
        self.assertIsNone(entry["sigmaAxis1M"])

    def test_an_unreadable_file_is_passed_over_and_not_counted(self):
        good = self.roots.root / "good.txt"
        good.write_text(EPHEMERIS_FIXTURE, encoding="ascii")
        bad = self.roots.root / "bad.txt"
        bad.write_text("not an ephemeris\n", encoding="ascii")
        result = si.starlink_covariance_quantiles([good, bad])
        self.assertEqual(result["files"], 1)


if __name__ == "__main__":
    unittest.main()
