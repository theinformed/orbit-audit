from __future__ import annotations

import base64
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.aurora_history import (
    AuroraFormatError,
    build_aurora_bundle,
    load_snapshot_frames,
    parse_ovation_latest,
    snapshot_current_frame,
)


def sample_payload(
    *,
    observed_at: str = "2026-08-06T20:00:00Z",
    valid_at: str = "2026-08-06T21:33:00Z",
) -> dict[str, object]:
    values: dict[tuple[int, int], int | None] = {
        (0, -1): 0,
        (0, 0): 10,
        (0, 1): 20,
        (1, -1): 30,
        (1, 0): None,
        (1, 1): 50,
        (2, -1): 60,
        (2, 0): 70,
        (2, 1): 80,
    }
    return {
        "Observation Time": observed_at,
        "Forecast Time": valid_at,
        "Data Format": "[Longitude, Latitude, Aurora]",
        "type": "MultiPoint",
        "coordinates": [[longitude, latitude, values[(longitude, latitude)]] for longitude in range(3) for latitude in range(-1, 2)],
    }


class AuroraParserTests(unittest.TestCase):
    def test_preserves_zero_missing_mask_both_hemispheres_and_actual_lead(self) -> None:
        parsed = parse_ovation_latest(sample_payload())
        self.assertEqual(parsed["grid"]["longitudeCount"], 3)
        self.assertEqual(parsed["grid"]["latitudeCount"], 3)
        self.assertEqual(parsed["grid"]["order"], "latitude-major, south-to-north, west-to-east")
        frame = parsed["frame"]
        self.assertEqual(frame["leadMinutes"], 93)
        self.assertEqual(frame["validCellCount"], 8)
        self.assertEqual(frame["missingCellCount"], 1)
        self.assertEqual(frame["hemispheres"]["north"]["maximumProbabilityPercent"], 80)
        self.assertEqual(frame["hemispheres"]["south"]["maximumProbabilityPercent"], 60)
        self.assertEqual(list(base64.b64decode(frame["probabilityU8"])), [0, 30, 60, 10, 0, 70, 20, 50, 80])
        validity = base64.b64decode(frame["validityBits"])
        self.assertEqual([(validity[index // 8] >> (index % 8)) & 1 for index in range(9)], [1, 1, 1, 1, 0, 1, 1, 1, 1])

    def test_rejects_duplicates_fractional_probabilities_and_bad_ranges(self) -> None:
        duplicate = sample_payload()
        duplicate["coordinates"] = [*duplicate["coordinates"], [0, -1, 5]]  # type: ignore[index]
        with self.assertRaises(AuroraFormatError):
            parse_ovation_latest(duplicate)

        fractional = sample_payload()
        fractional["coordinates"][0][2] = 2.5  # type: ignore[index]
        with self.assertRaises(AuroraFormatError):
            parse_ovation_latest(fractional)

        out_of_range = sample_payload()
        out_of_range["coordinates"][0][2] = 101  # type: ignore[index]
        with self.assertRaises(AuroraFormatError):
            parse_ovation_latest(out_of_range)


class AuroraHistoryTests(unittest.TestCase):
    def test_first_run_reports_unavailable_history_instead_of_inventing_it(self) -> None:
        retrieved_at = dt.datetime(2026, 8, 6, 20, 10, tzinfo=dt.timezone.utc)
        bundle = build_aurora_bundle(
            sample_payload(observed_at="2026-08-06T19:00:00Z", valid_at="2026-08-06T20:05:00Z"),
            retrieved_at=retrieved_at,
            history_hours=48,
        )
        self.assertEqual(bundle["schemaVersion"], "noaa-ovation-history.v1")
        self.assertFalse(bundle["time"]["coverageComplete"])
        self.assertEqual(bundle["time"]["noDataIntervals"][0]["reason"], "before-bigmem-accumulation")
        self.assertEqual(bundle["sourceAvailability"]["publicNumericDistribution"], "latest grid only")
        self.assertEqual(bundle["sourceAvailability"]["publicRenderedImageHistoryHours"], 24)
        self.assertIn("rendered-image reconstruction", bundle["sourceAvailability"]["notUsed"])
        self.assertEqual(bundle["time"]["activeForecast"], {
            "sourceObservedAt": "2026-08-06T19:00:00Z",
            "forecastValidAt": "2026-08-06T20:05:00Z",
            "feedRetrievedAt": "2026-08-06T20:10:00Z",
            "selectionWindowMinutes": 12,
            "definition": (
                "near-live display exception for this exact latest NOAA grid only; feedRetrievedAt "
                "is the bigmem retrieval time, not a NOAA issue time, and historical gaps remain unavailable"
            ),
        })
        self.assertIn("history uses only forecast-valid time", bundle["time"]["selection"])

    def test_publishes_the_equatorial_seam_rule_without_touching_source_bytes(self) -> None:
        payload = sample_payload(observed_at="2026-08-06T19:00:00Z", valid_at="2026-08-06T20:05:00Z")
        bundle = build_aurora_bundle(
            payload,
            retrieved_at=dt.datetime(2026, 8, 6, 20, 10, tzinfo=dt.timezone.utc),
        )
        seam = bundle["display"]["equatorialSeam"]
        self.assertFalse(seam["sourceBytesModified"])
        self.assertIn("missing", seam["handling"])
        self.assertEqual(seam["bandLatitudeDeg"], 5)
        self.assertEqual(seam["isolationLatitudeDeg"], 10)
        self.assertTrue(any("seam" in limitation for limitation in bundle["limitations"]))
        # The reducer stays lossless: the equator row it now documents is still
        # published exactly as NOAA sent it.
        stored = list(base64.b64decode(bundle["frames"][-1]["probabilityU8"]))
        self.assertEqual(stored, [0, 30, 60, 10, 0, 70, 20, 50, 80])
        validity = base64.b64decode(bundle["frames"][-1]["validityBits"])
        self.assertEqual([(validity[index // 8] >> (index % 8)) & 1 for index in range(9)], [1, 1, 1, 1, 0, 1, 1, 1, 1])

    def test_bigmem_snapshots_round_trip_only_matching_native_grids(self) -> None:
        retrieved_at = dt.datetime(2026, 8, 6, 20, 10, tzinfo=dt.timezone.utc)
        bundle = build_aurora_bundle(
            sample_payload(observed_at="2026-08-06T19:00:00Z", valid_at="2026-08-06T20:05:00Z"),
            retrieved_at=retrieved_at,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = snapshot_current_frame(root, bundle)
            frames = load_snapshot_frames(
                root,
                start=retrieved_at - dt.timedelta(hours=1),
                end=retrieved_at + dt.timedelta(hours=1),
                grid=bundle["grid"],
            )
            self.assertEqual([frame["validAt"] for frame in frames], ["2026-08-06T20:05:00Z"])

            document = json.loads(path.read_text())
            document["grid"]["longitudeStepDeg"] = 2
            path.write_text(json.dumps(document))
            self.assertEqual(load_snapshot_frames(
                root,
                start=retrieved_at - dt.timedelta(hours=1),
                end=retrieved_at + dt.timedelta(hours=1),
                grid=bundle["grid"],
            ), [])

    def test_internal_snapshot_gap_is_explicit(self) -> None:
        older = parse_ovation_latest(sample_payload(
            observed_at="2026-08-06T18:55:00Z",
            valid_at="2026-08-06T19:00:00Z",
        ))["frame"]
        bundle = build_aurora_bundle(
            sample_payload(observed_at="2026-08-06T19:55:00Z", valid_at="2026-08-06T20:00:00Z"),
            retrieved_at=dt.datetime(2026, 8, 6, 20, 0, tzinfo=dt.timezone.utc),
            historical_frames=[older],
            history_hours=2,
        )
        gaps = [interval for interval in bundle["time"]["noDataIntervals"] if interval["reason"] == "snapshot-gap"]
        self.assertEqual(gaps, [{
            "from": "2026-08-06T19:12:00Z",
            "to": "2026-08-06T20:00:00Z",
            "reason": "snapshot-gap",
        }])


if __name__ == "__main__":
    unittest.main()
