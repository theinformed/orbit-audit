"""The released copy of a file, and the copies a receipt pinned before it.

Every measurement in this repository writes a receipt that records the
SHA-256 of the code that produced it, so a reader can tell whether the file in
front of them is the file that earned the number. Some files here do not hash
to the value an older receipt recorded, for two reasons and only two:

  * *released form* — the copy released here differs from the copy that was
    measured in comments, docstrings and installation-specific path defaults
    only; or
  * *later revision* — the instrument was revised later in the programme,
    after the receipt that pins the earlier copy was written.

`docs/released-source-hashes-20260923.json` names every such file, the hashes
it supersedes, which of the two reasons applies and where each superseded hash
was recorded. This module reads that record so a test can ask "is this file
the one the receipt pinned, or a form of it the record accounts for?" and get
a yes only when the record says so. No receipt is rewritten, and a file that
changes for any other reason still fails.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RECORD = Path("docs") / "released-source-hashes-20260923.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(repo: Path) -> dict:
    return json.loads((repo / RECORD).read_text())


def by_path(repo: Path) -> dict:
    return {row["path"]: row for row in record(repo)["sources"]}


def accepts(repo: Path, rel: str, recorded: str) -> bool:
    """True when `rel` on disk is the file a receipt recording `recorded` pinned.

    Either the file still hashes to the recorded value, or the released-source
    record carries a row for this exact path whose released hash is the file on
    disk and whose superseded list contains the recorded value. Nothing else is
    accepted.
    """
    on_disk = sha256_file(repo / rel)
    if on_disk == recorded:
        return True
    row = by_path(repo).get(rel)
    if row is None:
        return False
    return (row["releasedSha256"] == on_disk
            and recorded in row["supersedes"])
