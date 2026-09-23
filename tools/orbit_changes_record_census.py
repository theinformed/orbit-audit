#!/usr/bin/env python3
"""Census the published orbit-change record, so the paper can cite a committed file.

The record itself -- the content-addressed index the site fetches -- is a
published artifact under `public/data/artifacts/`, which is not tracked by this
repository.  This script COUNTS that artifact and nothing else: it performs no
measurement, reads no archive, and derives no quantity the artifact does not
already carry.  It pins the artifact's SHA-256 so a reader can check that the
counts below describe the file the manifest names.

    python3 tools/orbit_changes_record_census.py \
        --index public/data/artifacts/orbit-changes-index-<sha>.json \
        --out docs/orbit-changes-record-20260923.json

Every count is a tally over the artifact's own `rows` and `changes` arrays, or a
scalar copied verbatim from its header.  Nothing is rounded, inferred or filled.
"""
import argparse
import collections
import hashlib
import json
import os
import sys


def tally(rows, field):
    counts = collections.Counter(row.get(field) for row in rows)
    return {("null" if key is None else str(key)): int(value)
            for key, value in sorted(counts.items(),
                                     key=lambda kv: (-kv[1], str(kv[0])))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    raw = open(args.index, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    index = json.loads(raw.decode("utf-8"))
    rows = index["rows"]
    changes = index["changes"]

    orphan_by_family = collections.Counter(
        change["family"] for change in changes if not change.get("episodeId"))

    census = {
        "schema": 1,
        "what": ("a count of the published orbit-change record; no measurement "
                 "is performed here and no quantity is derived"),
        "indexPath": os.path.basename(args.index),
        "indexSha256": digest,
        "generatedAt": index["generatedAt"],
        "recordToMs": index["recordToMs"],
        "episodeSchema": index["versions"]["episodeSchema"],
        "trackerVersion": index["trackerVersion"],
        "modelVersion": index["modelVersion"],
        "modelChecksum": index["modelChecksum"],
        "manoeuvreLabelPermitted": index["manoeuvreLabelPermitted"],
        "stateRatesMeasured": index["stateRatesMeasured"],
        "episodes": len(rows),
        "changeSteps": len(changes),
        "stepsWithoutEpisode": index["stepsWithoutEpisode"],
        "stepsWithoutEpisodeByFamily": {k: int(v) for k, v in
                                        sorted(orphan_by_family.items())},
        "byState": tally(rows, "state"),
        "byClosure": tally(rows, "closure"),
        "byKind": tally(rows, "kind"),
        "byRegime": tally(rows, "regime"),
        "byStage": tally(rows, "stage"),
        "byVerdict": tally(rows, "verdict"),
        "reopenedEpisodes": sum(1 for row in rows if (row.get("reopened") or 0) > 0),
        "changeStepsByFamily": tally(changes, "family"),
        "changeStepsBySignature": tally(changes, "signatureLabel"),
        "families": index["families"],
        "measuredError": index["measuredError"],
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(census, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("wrote %s from %s (sha256 %s)" % (args.out, args.index, digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
