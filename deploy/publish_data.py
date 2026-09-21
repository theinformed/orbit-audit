#!/usr/bin/env python3
"""Stage only the artifacts referenced by the current atomic manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def artifact_records(manifest: dict[str, object]):
    """Yield content-addressed artifact records, including sharded ones.

    The manifest grows as new scientific layers are added. Discovering records
    by their path/hash contract prevents a new layer from publishing a manifest
    that references an artifact the staging allowlist forgot to copy.

    A layer may also publish a *set* of artifacts under one key rather than a
    single file, by carrying a list of records beside its summary fields --
    `orbitHistory` shards one object's history per file so that opening one
    satellite costs a hundred kilobytes instead of the whole archive. Those
    nested records use exactly the same path/hash contract, and without this
    walk they would be referenced by the manifest and silently never staged,
    which fails as a 404 in the browser rather than as an error here.
    """
    for key, value in manifest.items():
        if not isinstance(value, dict):
            continue
        path = value.get("path")
        digest = value.get("sha256")
        if isinstance(path, str) and isinstance(digest, str):
            yield key, path, digest
        for field, nested in value.items():
            if not isinstance(nested, list):
                continue
            for index, record in enumerate(nested):
                if not isinstance(record, dict):
                    continue
                path = record.get("path")
                digest = record.get("sha256")
                if isinstance(path, str) and isinstance(digest, str):
                    yield f"{key}.{field}[{index}]", path, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    manifest_path = args.source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    staging = args.destination.with_name(f".{args.destination.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "artifacts").mkdir(parents=True)

    source_root = args.source.resolve()
    source_artifacts = (source_root / "artifacts").resolve()
    for key, relative, expected_digest in artifact_records(manifest):
        source = (source_root / relative).resolve()
        if source_artifacts not in source.parents or not source.is_file():
            raise RuntimeError(f"invalid or missing artifact for {key}: {source}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != expected_digest:
            raise RuntimeError(f"sha256 mismatch for {source}")
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        compressed = source.with_suffix(f"{source.suffix}.gz")
        if compressed.exists():
            shutil.copy2(compressed, target.with_suffix(f"{target.suffix}.gz"))

    shutil.copy2(manifest_path, staging / "manifest.json")
    if args.destination.exists():
        backup = args.destination.with_name(f".{args.destination.name}.previous")
        if backup.exists():
            shutil.rmtree(backup)
        args.destination.rename(backup)
    staging.rename(args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
