#!/usr/bin/env python3
"""Delete old unreferenced immutable artifacts while preserving the live manifest set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

# Basenames that are never pruned, whatever their age and whether or not the
# CURRENT manifest still references them.
#
# A published artifact that a PAGE cites by content address is not garbage the
# moment the manifest moves on. The citation is part of the text: a reader who
# follows it after rotation reaches the file gets a 404. Learning chapter 08,
# "Earning the word" (src/orbit-verdict.ts), quotes this bundle's counts and
# links it as source 5 -- on a page whose entire subject is not claiming more
# than the evidence supports, which makes a dead evidence link the worst
# possible failure there. Its first freeze cited
# orbit-events-b3112145df7493d8.json; rotation deleted that file on every host,
# and both the chapter's citation and tests/orbit-verdict.test.ts broke with it.
# The test now reads a committed fixture instead (an immutable input does not
# belong in a rotated directory); this pin is what keeps the READER's copy alive.
#
# Add a basename here only together with the citation that needs it, and drop it
# in the same change that stops citing the file. The ".gz" peer is pinned
# automatically, exactly as for manifest-referenced artifacts.
PINNED_ARTIFACTS = frozenset({
    "orbit-events-f0aee9b89f1c200f.json",
})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root", type=Path)
    parser.add_argument("--max-age-hours", type=float, default=72)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.data_root.resolve()
    manifest_path = root / "manifest.json"
    artifacts = root / "artifacts"
    if root in {Path("/"), Path("/root"), Path("/home")} or not manifest_path.is_file() or not artifacts.is_dir():
        raise RuntimeError(f"refusing unsafe or incomplete data root: {root}")

    manifest = json.loads(manifest_path.read_text())

    def referenced(container: dict, key: str):
        """Every path/sha256 record under one manifest key, sharded or not.

        A layer may publish a SET of artifacts under one key -- `orbitHistory`
        ships one file per 256th of the catalogue -- carrying a list of records
        beside its summary fields. Those use the same path/hash contract, and a
        walk that only looked at the top level would treat every shard as
        unreferenced and delete the live ones out from under the site.
        """
        if isinstance(container.get("path"), str) and isinstance(container.get("sha256"), str):
            yield key, container["path"]
        for field, nested in container.items():
            if not isinstance(nested, list):
                continue
            for index, record in enumerate(nested):
                if not isinstance(record, dict):
                    continue
                if isinstance(record.get("path"), str) and isinstance(record.get("sha256"), str):
                    yield f"{key}.{field}[{index}]", record["path"]

    keep: set[Path] = set()
    for key, record in manifest.items():
        if not isinstance(record, dict):
            continue
        for label, relative in referenced(record, key):
            path = (root / relative).resolve()
            if artifacts not in path.parents:
                raise RuntimeError(f"manifest path for {label} escapes artifact root: {path}")
            keep.add(path)
            keep.add(path.with_suffix(f"{path.suffix}.gz"))

    for name in sorted(PINNED_ARTIFACTS):
        pinned = (artifacts / name).resolve()
        if artifacts not in pinned.parents:
            raise RuntimeError(f"pinned artifact escapes artifact root: {pinned}")
        keep.add(pinned)
        keep.add(pinned.with_suffix(f"{pinned.suffix}.gz"))
        if not pinned.is_file():
            # Loud, not fatal: the pin cannot resurrect a file, and a publish run
            # must not fail on one host because the artifact has not landed there
            # yet. But a cited bundle that is already gone is exactly the defect
            # this list exists to stop, so it must never pass in silence.
            print(f"WARNING: pinned artifact {name} is missing from {artifacts}; a page cites it")

    cutoff = time.time() - args.max_age_hours * 3600
    removed_count = 0
    removed_bytes = 0
    for path in artifacts.iterdir():
        if not path.is_file() or path in keep or path.stat().st_mtime >= cutoff:
            continue
        if not path.name.endswith((".json", ".json.gz", ".svg", ".svg.gz")):
            continue
        removed_count += 1
        removed_bytes += path.stat().st_size
        if not args.dry_run:
            path.unlink()
    print(f"pruned {removed_count} unreferenced artifacts ({removed_bytes} bytes) from {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
