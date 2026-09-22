"""Validation applied to every upstream fetch before its bytes are used.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import build_release


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class FetchValidationTests(unittest.TestCase):
    def test_malformed_upstream_does_not_replace_last_known_good_json(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            url = "https://example.test/data.json"
            with mock.patch.object(build_release, "CACHE", cache):
                cached = build_release.cache_path(url)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(b'{"status":"good"}')
                os.utime(cached, (1, 1))
                with mock.patch.object(
                    build_release.urllib.request,
                    "urlopen",
                    return_value=_Response(b'{"truncated":'),
                ), mock.patch.object(build_release.time, "sleep"):
                    value = build_release.fetch_json(url, 0)

                self.assertEqual(value, {"status": "good"})
                self.assertEqual(cached.read_bytes(), b'{"status":"good"}')
                self.assertGreater(cached.stat().st_mtime, 1)

    def test_fresh_malformed_cache_is_refetched_and_replaced_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            url = "https://example.test/data.json"
            with mock.patch.object(build_release, "CACHE", cache):
                cached = build_release.cache_path(url)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(b'{"truncated":')
                with mock.patch.object(
                    build_release.urllib.request,
                    "urlopen",
                    return_value=_Response(b'{"status":"recovered"}'),
                ):
                    value = build_release.fetch_json(url, 3600)

                self.assertEqual(value, {"status": "recovered"})
                self.assertEqual(cached.read_bytes(), b'{"status":"recovered"}')


if __name__ == "__main__":
    unittest.main()
