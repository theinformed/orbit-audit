"""Private, bounded checkpoints for one orbit release tail (never served)."""

from __future__ import annotations

import hashlib
import io
import os
import pickle
import shutil
import signal
import sqlite3
import time
from pathlib import Path


class TailPaused(Exception):
    """A completed unit of work was saved before yielding the run."""


class TailCheckpoint:
    # One current build, at most 258 JSON/gzip pairs pinned against the public
    # artifact pruner. Hard links cost no additional data blocks on this SSD.
    # Metadata has a separate 2 GiB SQLite ceiling; journal <= another 2 GiB.
    ARTIFACT_BYTES = 8 * 1024**3
    ARTIFACT_FILES = 2 * (256 + 2)

    def __init__(self, root: Path, identity: str, data_root: Path, deadline: float | None):
        self.root, self.data_root, self.deadline = root, data_root, deadline
        self.stopped = False
        self.last_stage = None
        self.db = None
        self.previous_handler = None
        marker = root / "identity"
        if root.exists() and (not marker.exists() or marker.read_text() != identity):
            # Only the fixed private workspace of the superseded sweep.
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        # Never truncate this marker on resume: a signal in that window would
        # otherwise make the next invocation discard a valid completed tail.
        if not marker.exists():
            temporary = root / "identity.tmp"
            temporary.write_text(identity)
            temporary.replace(marker)
        (root / "artifacts").mkdir(exist_ok=True)

    def __enter__(self):
        self.db = sqlite3.connect(self.root / "stages.sqlite3")
        self.db.execute("PRAGMA max_page_count=524288")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS stage (name TEXT PRIMARY KEY, value BLOB)")
        self.db.commit()
        self.previous_handler = signal.signal(signal.SIGTERM, self._stop)
        return self

    def _stop(self, signum, frame):
        # Never throw between writing an artifact and committing its record.
        self.stopped = True

    def __exit__(self, *exc):
        signal.signal(signal.SIGTERM, self.previous_handler)
        self.db.close()

    def has(self, name):
        return self.db.execute("SELECT 1 FROM stage WHERE name = ?", (name,)).fetchone() is not None

    def load(self, name):
        row = self.db.execute("SELECT rowid FROM stage WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        # Avoid SELECT's two whole-BLOB copies alongside the deserialized graph.
        with self.db.blobopen("stage", "value", row[0], readonly=True) as blob:
            with io.BufferedReader(BlobReader(blob)) as reader:
                return pickle.load(reader)

    def expired(self):
        return self.stopped or (self.deadline is not None and time.time() >= self.deadline)

    def step(self, name, compute):
        if self.has(name):
            return self.load(name)
        return self.save(name, compute())

    def save(self, name, value, *, check_budget=True):
        with self.db:
            self.db.execute("INSERT INTO stage VALUES (?, ?)",
                            (name, pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)))
        self.last_stage = name
        # As in the sweep: finish one unit, save it, then check the clock.
        # A small budget must still make progress on every invocation.
        if check_budget and self.expired():
            raise TailPaused(name)
        return value

    def values(self, prefix):
        return [pickle.loads(row[0]) for row in self.db.execute(
            "SELECT value FROM stage WHERE name LIKE ? ORDER BY name", (prefix + "%",))]

    def pin(self, relative: str, digest: str):
        """Retain completed bytes even if the public pruner removes the name."""
        source = self.data_root / relative
        if source.parent != self.data_root / "artifacts":
            raise ValueError(f"unexpected artifact path: {relative}")
        with source.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != digest:
                raise ValueError(f"artifact digest mismatch: {relative}")
        pins = self.root / "artifacts"
        sources = [source]
        compressed = source.with_suffix(source.suffix + ".gz")
        if compressed.exists():
            sources.append(compressed)
        existing = list(pins.iterdir())
        additions = [s for s in sources if not (pins / s.name).exists()]
        if (len(existing) + len(additions) > self.ARTIFACT_FILES or
                sum(p.stat().st_size for p in existing + additions) > self.ARTIFACT_BYTES):
            raise RuntimeError("orbit tail artifact retention budget exceeded")
        for path in additions:
            os.link(path, pins / path.name)

    def restore(self, records, *, verify=True):
        """Verify the retained digest and restore pruned names before publishing."""
        for record in records:
            pinned = self.root / "artifacts" / Path(record["path"]).name
            if not pinned.is_file():
                raise FileNotFoundError(f"missing checkpoint artifact: {pinned.name}")
            if verify:
                with pinned.open("rb") as handle:
                    if hashlib.file_digest(handle, "sha256").hexdigest() != record["sha256"]:
                        raise ValueError(f"checkpoint artifact digest mismatch: {pinned.name}")
            target = self.data_root / record["path"]
            for source, dest in ((pinned, target),
                                 (pinned.with_suffix(".json.gz"), target.with_suffix(".json.gz"))):
                if source.exists() and not dest.exists():
                    os.link(source, dest)

    def clear(self):
        """Only after the manifest commit, or when this sweep is superseded."""
        shutil.rmtree(self.root)

    @staticmethod
    def status(root: Path):
        """Read-only retention inventory; also used by --sweep-status."""
        if not root.exists():
            return None
        files = [p for p in root.rglob("*") if p.is_file()]
        result = {"path": str(root), "files": len(files),
                  "bytes": sum(p.stat().st_size for p in files),
                  "artifactByteBudget": TailCheckpoint.ARTIFACT_BYTES,
                  "metadataByteBudget": 2 * 1024**3,
                  "retention": "current sweep only; removed after publication or supersession"}
        database = root / "stages.sqlite3"
        if database.exists():
            db = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
            try:
                result["shardsDone"] = db.execute(
                    "SELECT count(*) FROM stage WHERE name LIKE 'shard:%'").fetchone()[0]
            finally:
                db.close()
        return result


class BlobReader(io.RawIOBase):
    """Bounded streaming adapter for SQLite's seekable BLOB handle."""

    def __init__(self, blob):
        self.blob = blob

    def readable(self):
        return True

    def readinto(self, buffer):
        data = self.blob.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


class TailEvents:
    """Full cards stay on SSD; only one object's cards are materialized at a time.

    Lives in the existing stage DB, under its same 2 GiB cap and tail identity.
    Contains no connection, so a prepared checkpoint remains pickleable.
    """

    def __init__(self, root):
        self.root = Path(root)

    @staticmethod
    def put(db, records, offset=0):
        # One pickle per bounded batch retains pickle's shared-string memo;
        # pickling each card separately more than doubles metadata on disk.
        db.execute("CREATE TABLE IF NOT EXISTS card_batch (position INTEGER PRIMARY KEY, value BLOB)")
        db.execute("CREATE TABLE IF NOT EXISTS card_object "
                   "(norad INTEGER, position INTEGER, PRIMARY KEY(norad, position)) WITHOUT ROWID")
        if not records:
            return
        with db:
            db.execute("INSERT OR REPLACE INTO card_batch VALUES (?, ?)",
                       (offset, pickle.dumps(records, protocol=pickle.HIGHEST_PROTOCOL)))
            db.executemany("INSERT OR IGNORE INTO card_object VALUES (?, ?)",
                           ((n, offset) for n in {r["norad"] for r in records}))

    def get(self, norad, default=None):
        db = sqlite3.connect(f"{(self.root / 'stages.sqlite3').resolve().as_uri()}?mode=ro", uri=True)
        try:
            records = [r for row in db.execute(
                "SELECT b.value FROM card_object o JOIN card_batch b USING(position) "
                "WHERE o.norad = ? ORDER BY o.position", (norad,))
                for r in pickle.loads(row[0]) if r["norad"] == norad]
        finally:
            db.close()
        records.sort(key=lambda r: r["startAt"])
        return records if records else default
