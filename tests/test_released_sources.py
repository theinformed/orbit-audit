#!/usr/bin/env python3
"""Every code hash a receipt records still resolves to a file here.

A receipt in this repository pins the code that produced it by SHA-256. That
is only worth anything if something checks it, and checks it over every
receipt rather than over the two or three a particular suite happens to open.

This suite does three things.

  * It sweeps every JSON receipt under `docs/` for a (path, hash) pair naming
    a file in this repository, in each of the three shapes the receipts use --
    a `<name>` / `<name>Sha256` pair, a `{path, sha256}` object, and a mapping
    whose key is the path -- and requires the file to hash to what the receipt
    recorded, or, where `docs/released-source-hashes-20260923.json` accounts
    for the difference, to hash to that record's released value against a hash
    the record says it supersedes.
  * It requires every row of that record to be load-bearing: the file must
    exist and hash to `releasedSha256`, every superseded hash must differ from
    it and must actually appear in a published document, and the row must say
    which of the two permitted reasons applies. A row cannot be added to
    excuse a file nothing pinned.
  * It refuses an empty sweep, so the suite cannot pass by checking nothing.

No archive, no network.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import released_sources as rs  # noqa: E402

DOCS = _REPO / "docs"

# Directories a recorded path may point into, and the shape of a hash.
_ROOTS = ("docs/", "tools/", "pipeline/", "tests/", "ingest/", "ops/", "src/")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_CODE = (".py", ".mjs", ".ts", ".sh")
_KINDS = ("released-form", "later-revision")


def _resolve(name):
    """A repository-relative path for `name`, or None if it names nothing here."""
    if name.startswith(_ROOTS):
        return name if (_REPO / name).is_file() else None
    if name.endswith(_CODE) and "/" not in name:
        for root in ("tools", "pipeline", "ingest", "ops", "tests"):
            if (_REPO / root / name).is_file():
                return f"{root}/{name}"
    return None


def _pairs(node, out):
    """Collect (path, hash) pairs from any nesting of dicts and lists."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and _SHA.match(value):
                name = None
                if key.endswith("Sha256"):
                    sibling = node.get(key[: -len("Sha256")])
                    name = sibling if isinstance(sibling, str) else None
                elif key == "sha256":
                    sibling = node.get("path")
                    name = sibling if isinstance(sibling, str) else None
                else:
                    name = key          # the mapping shape: the key IS the path
                if name:
                    rel = _resolve(name)
                    if rel:
                        out.append((rel, value))
            _pairs(value, out)
    elif isinstance(node, list):
        for item in node:
            _pairs(item, out)
    return out


def recorded_pairs():
    """Every (repository path, recorded hash) a JSON receipt under docs/ holds."""
    found = []
    for path in sorted(DOCS.glob("*.json")):
        if path.name == rs.RECORD.name:
            continue
        try:
            doc = json.loads(path.read_text())
        except (ValueError, UnicodeDecodeError):
            continue
        for rel, sha in _pairs(doc, []):
            found.append((path.name, rel, sha))
    return found


def documents_naming(hashes):
    """Which of `hashes` appear literally in some published document."""
    seen = set()
    for path in sorted(DOCS.glob("*.json")) + sorted(DOCS.glob("*.md")):
        if path.name == rs.RECORD.name:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for value in hashes - seen:
            if value in text:
                seen.add(value)
        if seen == hashes:
            break
    return seen


class TestRecordedHashes(unittest.TestCase):
    def setUp(self):
        self.pairs = recorded_pairs()

    def test_the_sweep_finds_something_to_check(self):
        """A sweep that checks nothing must not be able to pass."""
        self.assertGreaterEqual(len(self.pairs), 50)
        self.assertGreaterEqual(len({rel for _, rel, _ in self.pairs}), 15)

    def test_every_recorded_hash_resolves(self):
        for receipt, rel, sha in self.pairs:
            self.assertTrue(
                rs.accepts(_REPO, rel, sha),
                f"{rel} does not hash to what {receipt} recorded, and "
                f"{rs.RECORD} does not account for the difference",
            )


class TestReleasedSourceRecord(unittest.TestCase):
    def setUp(self):
        self.doc = rs.record(_REPO)
        self.rows = self.doc["sources"]

    def test_it_says_what_differs_and_why(self):
        for key in ("what", "why", "howToCheck"):
            self.assertTrue(self.doc[key].strip(), key)
        for kind in _KINDS:
            self.assertTrue(self.doc["kinds"][kind].strip(), kind)

    def test_every_row_names_a_file_that_hashes_to_the_released_value(self):
        self.assertTrue(self.rows)
        for row in self.rows:
            path = _REPO / row["path"]
            self.assertTrue(path.is_file(), row["path"])
            self.assertEqual(rs.sha256_file(path), row["releasedSha256"],
                             row["path"])
            self.assertIn(row["kind"], _KINDS, row["path"])

    def test_no_superseded_hash_is_invented(self):
        """A row only earns its place if a published document records the hash."""
        wanted = set()
        for row in self.rows:
            self.assertTrue(row["supersedes"], row["path"])
            for value in row["supersedes"]:
                self.assertNotEqual(value, row["releasedSha256"], row["path"])
                wanted.add(value)
        self.assertEqual(sorted(wanted - documents_naming(wanted)), [])

    def test_no_path_appears_twice(self):
        paths = [row["path"] for row in self.rows]
        self.assertEqual(len(paths), len(set(paths)))


if __name__ == "__main__":
    unittest.main()
