"""Timed space-weather artifacts published with the release.

Covers exact frame coverage, OVATION point extraction, and the atomic publish of
an artifact whose timestamp must match the frame it carries.
"""

from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.build_release import (
    build_drap_release_bundle,
    exact_frame_coverage,
    ovation_points,
    publish_timed_environment_artifact,
    timed_environment_record,
)


def _ovation(count: int, poleward: bool = True) -> dict:
    latitude = 60 if poleward else 10
    return {"coordinates": [[index % 360, latitude, 50] for index in range(count)]}


class OvationPointsTests(unittest.TestCase):
    """build_space_weather() has no try/except around it.

    Anything raised while reading OVATION takes the catalog, geospace, D-RAP and
    the manifest down with it -- the same blast radius as the GloTEC incident of
    2026-08-08, which cost hours of publishes.
    """

    def test_a_healthy_grid_is_read_whole(self):
        self.assertEqual(len(ovation_points(_ovation(1200))), 1200)

    def test_an_absent_ovation_does_not_abort_the_publish(self):
        """Zero points is 'OVATION is not there this cycle', not a fault."""
        self.assertEqual(ovation_points({}), [])
        self.assertEqual(ovation_points({"coordinates": []}), [])

    def test_an_all_equatorward_grid_does_not_abort_the_publish(self):
        """Everything filtered out is indistinguishable from an absent grid."""
        self.assertEqual(ovation_points(_ovation(1200, poleward=False)), [])

    def test_one_malformed_triple_does_not_discard_the_other_thousands(self):
        payload = _ovation(1200)
        payload["coordinates"][17] = ["north", "60", 50]
        self.assertEqual(len(ovation_points(payload)), 1199)

    def test_a_short_but_present_grid_is_still_a_fault(self):
        """Deliberately unchanged: an absence degrades, a fault raises."""
        with self.assertRaises(RuntimeError):
            ovation_points(_ovation(20))


class ExactCoverageTests(unittest.TestCase):
    def test_reports_unavailable_edges_without_holding_or_interpolating(self) -> None:
        coverage = exact_frame_coverage(
            [
                {"validAt": "2026-08-06T19:00:00Z"},
                {"validAt": "2026-08-06T19:05:00Z"},
            ],
            requested_from=dt.datetime(2026, 8, 6, 18, 0, tzinfo=dt.timezone.utc),
            requested_to=dt.datetime(2026, 8, 6, 20, 0, tzinfo=dt.timezone.utc),
            stale_after_minutes=12,
        )
        self.assertFalse(coverage["coverageComplete"])
        self.assertEqual(coverage["actualCoverageHours"], round(17 / 60, 3))
        self.assertEqual(coverage["noDataIntervals"], [
            {
                "from": "2026-08-06T18:00:00Z",
                "to": "2026-08-06T19:00:00Z",
                "reason": "before-bigmem-accumulation",
            },
            {
                "from": "2026-08-06T19:17:00Z",
                "to": "2026-08-06T20:00:00Z",
                "reason": "after-latest-frame",
            },
        ])


class TimedManifestRecordTests(unittest.TestCase):
    def test_record_exposes_range_gaps_and_source_retention(self) -> None:
        bundle = {
            "frames": [{"validAt": "2026-08-06T18:00:00Z"}, {"validAt": "2026-08-06T19:00:00Z"}],
            "time": {
                "availableFrom": "2026-08-06T18:00:00Z",
                "availableTo": "2026-08-06T19:00:00Z",
                "requestedFrom": "2026-08-04T19:00:00Z",
                "requestedTo": "2026-08-06T19:00:00Z",
                "coverageComplete": False,
                "actualCoverageHours": 1.2,
                "noDataIntervals": [{
                    "from": "2026-08-04T19:00:00Z",
                    "to": "2026-08-06T18:00:00Z",
                    "reason": "before-bigmem-accumulation",
                }],
                "sourceRetentionLimited": True,
            },
        }
        record = timed_environment_record("artifacts/aurora-a.json", "abc", bundle)
        self.assertEqual(record, {
            "path": "artifacts/aurora-a.json",
            "sha256": "abc",
            "frameCount": 2,
            "validFrom": "2026-08-06T18:00:00Z",
            "validTo": "2026-08-06T19:00:00Z",
            "requestedFrom": "2026-08-04T19:00:00Z",
            "requestedTo": "2026-08-06T19:00:00Z",
            "coverageComplete": False,
            "actualCoverageHours": 1.2,
            "noDataIntervalCount": 1,
            "sourceRetentionLimited": True,
        })

    def test_parser_failure_preserves_prior_content_addressed_artifact(self) -> None:
        prior = {
            "path": "artifacts/drap-prior.json",
            "sha256": "prior-sha",
            "frameCount": 10,
            "validFrom": "2026-08-06T18:00:00Z",
            "validTo": "2026-08-06T19:00:00Z",
            "requestedFrom": "2026-08-04T19:00:00Z",
            "requestedTo": "2026-08-06T19:00:00Z",
            "coverageComplete": False,
            "actualCoverageHours": 1.0,
            "noDataIntervalCount": 1,
            "sourceRetentionLimited": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(temporary)
            artifact = data_root / prior["path"]
            artifact.parent.mkdir(parents=True)
            artifact.write_text("{}")
            (data_root / "manifest.json").write_text(json.dumps({"schema": 1, "drap": prior}))

            with patch("pipeline.build_release.fetch_text", return_value="not a NOAA D-RAP grid"):
                record = publish_timed_environment_artifact(
                    data_root,
                    key="drap",
                    prefix="drap",
                    builder=lambda: build_drap_release_bundle(
                        data_root / "snapshots",
                        retrieved_at=dt.datetime(2026, 8, 6, 20, 0, tzinfo=dt.timezone.utc),
                    ),
                )
            self.assertEqual(record, prior)
            self.assertEqual(sorted(path.name for path in (data_root / "artifacts").iterdir()), ["drap-prior.json"])

    def test_failure_without_prior_omits_only_that_optional_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(temporary)
            record = publish_timed_environment_artifact(
                data_root,
                key="aurora",
                prefix="aurora",
                builder=lambda: (_ for _ in ()).throw(ValueError("bad OVATION payload")),
            )
            self.assertIsNone(record)


if __name__ == "__main__":
    unittest.main()
