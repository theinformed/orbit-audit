"""Offline regression tests for the CelesTrak usage-policy boundary."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from ingest import celestrak_mirror as mirror
from pipeline import build_release


class Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = io.BytesIO(body)
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class MirrorPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            mock.patch.object(mirror, "CACHE", root / "cache"),
            mock.patch.object(mirror, "STATE", root / "state"),
            mock.patch.object(mirror, "HALT_MARKER", root / "state" / "HALTED.json"),
            mock.patch.object(mirror, "SATCAT_APPLIED", root / "state" / "satcat-applied-signature.json"),
            mock.patch.object(mirror, "LAST_ATTEMPT", root / "state" / "last-request-at.json"),
            # Added 2026-08-27. Without it this offline test wrote the REAL
            # ingest/state/http-validators.json -- on bigmem, which is forbidden
            # from touching this lane at all. See SandboxCompletenessTests in
            # tests/test_celestrak_conditional_requests.py, which now fails if a
            # new mirror path constant is missing from any sandbox.
            mock.patch.object(mirror, "VALIDATORS", root / "state" / "http-validators.json"),
            mock.patch.object(mirror, "LOG", root / "mirror.log"),
            mock.patch.object(mirror, "POLITE_GAP", 0),
            mock.patch.object(mirror, "alert_human"),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp.cleanup()

    def test_active_gp_bulk_url_is_absent(self) -> None:
        source = Path(mirror.__file__).read_text()
        self.assertNotIn("gp.php?GROUP=active", source)
        self.assertNotIn("--force", source)

    def test_first_403_halts_and_later_run_opens_no_socket(self) -> None:
        body = b"This file has not updated since your last successful download"
        error = urllib.error.HTTPError(mirror.SATCAT_DIR, 403, "Forbidden", {}, io.BytesIO(body))
        with mock.patch.object(mirror.DIRECT_OPENER, "open", side_effect=error) as opened:
            self.assertEqual(mirror.run(), 2)
            self.assertEqual(mirror.run(), 0)
        self.assertEqual(opened.call_count, 1)
        marker = json.loads(mirror.HALT_MARKER.read_text())
        self.assertEqual(marker["status"], 403)
        self.assertIn("one-download-per-update", marker["classification"])

    def test_unchanged_directory_skips_full_satcat_and_caps_run_at_two(self) -> None:
        directory = json.dumps([{
            "FILE_NAME": "satcat.csv", "FILE_SIZE": "1200000", "FILE_MTIME": "2026-08-26 00:00:00"
        }]).encode()
        signature = mirror.satcat_signature(directory)
        mirror.STATE.mkdir(parents=True)
        mirror._mark_satcat_applied(signature, reason="test")
        calls: list[str] = []

        def open_request(request, timeout=0):
            del timeout
            calls.append(request.full_url)
            if "jsonDir" in request.full_url:
                return Response(directory)
            return Response(b'[{"NORAD_CAT_ID": 25544}]')

        with mock.patch.object(mirror.DIRECT_OPENER, "open", side_effect=open_request):
            self.assertEqual(mirror.run(), 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum("jsonDir" in url for url in calls), 1)
        self.assertFalse(any("records.php" in url for url in calls))
        self.assertFalse(any("GROUP=active" in url and "gp.php" in url for url in calls))

    def test_attempt_stamp_makes_next_run_socket_free(self) -> None:
        directory = json.dumps([{
            "FILE_NAME": "satcat.csv", "FILE_SIZE": "1200000", "FILE_MTIME": "2026-08-26 00:00:00"
        }]).encode()
        responses = [Response(directory), Response(b'[{"NORAD_CAT_ID": 25544}]')]
        with mock.patch.object(mirror.DIRECT_OPENER, "open", side_effect=responses) as opened:
            # Prevent the changed signature from consuming a second response.
            with mock.patch.object(mirror, "_read_applied_signature", return_value=mirror.satcat_signature(directory)):
                self.assertEqual(mirror.run(), 0)
                self.assertEqual(mirror.run(), 0)
        self.assertEqual(opened.call_count, 2)

    def test_publisher_direct_fetch_is_unconditionally_forbidden(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "direct CelesTrak network access is forbidden"):
            build_release.fetch_celestrak("https://celestrak.org/anything", 0)


if __name__ == "__main__":
    unittest.main()
