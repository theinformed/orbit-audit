import hashlib
import json
import os
import subprocess
import tempfile
import time
import sys
import pathlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class PublishDataTests(unittest.TestCase):
    def test_stages_every_top_level_artifact_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            artifacts = source / "artifacts"
            artifacts.mkdir(parents=True)
            records = {
                "catalog": b"catalog",
                "ionosphereModel": b"wam-ipe",
                "drap": b"drap",
                "aurora": b"ovation",
            }
            manifest: dict[str, object] = {"schema": 1, "release": "test"}
            for key, payload in records.items():
                relative = f"artifacts/{key}.json"
                (source / relative).write_bytes(payload)
                (source / f"{relative}.gz").write_bytes(b"gzip-" + payload)
                manifest[key] = {"path": relative, "sha256": digest(payload)}
            manifest["metadata"] = {"path": "not-an-artifact-without-a-hash"}
            (source / "manifest.json").write_text(json.dumps(manifest))

            subprocess.run(
                ["python3", str(ROOT / "deploy/publish_data.py"), str(source), str(destination)],
                check=True,
            )

            for key, payload in records.items():
                self.assertEqual((destination / f"artifacts/{key}.json").read_bytes(), payload)
                self.assertEqual((destination / f"artifacts/{key}.json.gz").read_bytes(), b"gzip-" + payload)
            self.assertEqual(json.loads((destination / "manifest.json").read_text())["release"], "test")

    def test_refuses_a_manifest_path_outside_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            payload = b"escape"
            (source / "outside.json").write_bytes(payload)
            (source / "manifest.json").write_text(json.dumps({
                "bad": {"path": "outside.json", "sha256": digest(payload)},
            }))
            result = subprocess.run(
                ["python3", str(ROOT / "deploy/publish_data.py"), str(source), str(root / "destination")],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid or missing artifact", result.stderr)


class PruneDataTests(unittest.TestCase):
    def test_preserves_dynamic_manifest_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data"
            artifacts = root / "artifacts"
            artifacts.mkdir(parents=True)
            retained = artifacts / "ionosphere.json"
            retained_gzip = artifacts / "ionosphere.json.gz"
            removed = artifacts / "old.json"
            retained.write_bytes(b"model")
            retained_gzip.write_bytes(b"compressed")
            removed.write_bytes(b"old")
            old = time.time() - 48 * 3600
            for path in (retained, retained_gzip, removed):
                os.utime(path, (old, old))
            (root / "manifest.json").write_text(json.dumps({
                "ionosphereModel": {"path": "artifacts/ionosphere.json", "sha256": digest(b"model")},
            }))

            subprocess.run(
                ["python3", str(ROOT / "deploy/prune_data.py"), str(root), "--max-age-hours", "1"],
                check=True,
            )

            self.assertTrue(retained.exists())
            self.assertTrue(retained_gzip.exists())
            self.assertFalse(removed.exists())


class ShardedArtifactRecords(unittest.TestCase):
    """A layer may publish a SET of artifacts under one manifest key.

    `orbitHistory` ships one file per 256th of the catalogue, so that opening
    one satellite's history costs about a hundred kilobytes instead of the whole
    archive. The shard records carry the same path/sha256 contract as any other
    artifact, but they sit in a list beside the key's summary fields rather than
    at the top level.

    Both discovery walks previously stopped at the top level, and the two
    failure modes are asymmetric and both bad: the staging copy silently omitted
    every shard, which surfaces as a 404 in a visitor's browser rather than as
    an error in the pipeline; and the pruner treated every live shard as
    unreferenced and deleted it out from under the site.
    """

    MANIFEST = {
        "catalog": {"path": "artifacts/catalog.json", "sha256": digest(b"catalog")},
        "orbitEvents": {"path": "artifacts/orbit-events.json", "sha256": digest(b"events")},
        "orbitHistory": {
            "shardCount": 2,
            "objects": 5,
            "shards": [
                {"shard": 0, "path": "artifacts/orbit-history-000.json", "sha256": digest(b"s0")},
                {"shard": 1, "path": "artifacts/orbit-history-001.json", "sha256": digest(b"s1")},
            ],
        },
        "release": "20260807",
    }

    def test_publish_stages_sharded_records_as_well_as_flat_ones(self):
        sys.path.insert(0, str(ROOT / "deploy"))
        try:
            from publish_data import artifact_records
        finally:
            sys.path.pop(0)
        found = {key for key, _, _ in artifact_records(self.MANIFEST)}
        self.assertEqual(
            found,
            {"catalog", "orbitEvents", "orbitHistory.shards[0]", "orbitHistory.shards[1]"},
        )

    def test_prune_keeps_live_shards_and_still_removes_a_real_orphan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "data"
            (root / "artifacts").mkdir(parents=True)
            bodies = {
                "catalog.json": b"catalog",
                "orbit-events.json": b"events",
                "orbit-history-000.json": b"s0",
                "orbit-history-001.json": b"s1",
                "orphan.json": b"orphan",
            }
            old = time.time() - 48 * 3600
            for name, body in bodies.items():
                path = root / "artifacts" / name
                path.write_bytes(body)
                os.utime(path, (old, old))
            (root / "manifest.json").write_text(json.dumps(self.MANIFEST))

            subprocess.run(
                ["python3", str(ROOT / "deploy/prune_data.py"), str(root), "--max-age-hours", "1"],
                check=True,
            )
            for name in ("catalog.json", "orbit-events.json",
                         "orbit-history-000.json", "orbit-history-001.json"):
                self.assertTrue((root / "artifacts" / name).exists(), name)
            self.assertFalse((root / "artifacts" / "orphan.json").exists())


if __name__ == "__main__":
    unittest.main()
