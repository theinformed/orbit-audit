from __future__ import annotations

import base64
import datetime as dt
import io
import json
import struct
import tarfile
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from pipeline.drap import (
    DrapFormatError,
    build_drap_bundle,
    load_snapshot_frames,
    ncei_archive_query_url,
    parse_drap_global_frequencies,
    parse_ncei_archive_index,
    reduce_ncei_archive,
    snapshot_current_frame,
)


def sample_text(valid_at: str = "2026-08-06 20:26", value: float = 0.0) -> str:
    longitudes = list(range(-178, 179, 4))
    latitudes = list(range(89, -90, -2))
    lines = [
        "# DRAP Tabular Values",
        "# Product: D-Region Absorption",
        f"# Product Valid At : {valid_at} UTC",
        "# Estimated Recovery Time : No Estimate",
        "# X-RAY Message : Moderate X-ray Flux",
        "# X-RAY Warning :",
        "# Proton Message : Normal Proton Background",
        "# Proton Warning :",
        "# Frequency (MHz) as a function of Latitude and Longitude",
        "      " + " ".join(str(longitude) for longitude in longitudes),
        "-" * 80,
    ]
    for row_index, latitude in enumerate(latitudes):
        values = [value] * len(longitudes)
        if row_index == 0:
            values[0] = 3.0
            values[1] = 10.0
            values[2] = 30.0
        lines.append(f"{latitude:3d} | " + " ".join(f"{entry:.1f}" for entry in values))
    return "\n".join(lines) + "\n"


class DrapParserTests(unittest.TestCase):
    def test_parses_and_losslessly_quantizes_the_official_grid_contract(self) -> None:
        parsed = parse_drap_global_frequencies(sample_text())
        self.assertEqual(parsed["grid"]["longitudeCount"], 90)
        self.assertEqual(parsed["grid"]["latitudeCount"], 90)
        self.assertEqual(parsed["grid"]["longitudeStepDeg"], 4)
        self.assertEqual(parsed["grid"]["latitudeStepDeg"], -2)
        self.assertEqual(parsed["frame"]["validAt"], "2026-08-06T20:26:00Z")
        self.assertEqual(parsed["frame"]["maximumHafMhz"], 30.0)
        encoded = base64.b64decode(parsed["frame"]["valuesU16"])
        values = struct.unpack("<8100H", encoded)
        self.assertEqual(values[:4], (30, 100, 300, 0))
        self.assertEqual(parsed["messages"]["xray"], "Moderate X-ray Flux")
        self.assertIsNone(parsed["messages"]["xrayWarning"])

    def test_rejects_incomplete_rows_instead_of_painting_a_partial_globe(self) -> None:
        malformed = sample_text().replace("89 | 3.0 10.0", "89 | 3.0", 1)
        with self.assertRaises(DrapFormatError):
            parse_drap_global_frequencies(malformed)

    def test_bundle_preserves_nowcast_and_quiet_operational_semantics(self) -> None:
        bundle = build_drap_bundle(
            sample_text(),
            retrieved_at=dt.datetime(2026, 8, 6, 20, 27, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(bundle["schemaVersion"], "noaa-drap.v1")
        self.assertEqual(bundle["temporalKind"], "empirical-nowcast")
        self.assertFalse(bundle["time"]["futureAvailable"])
        self.assertEqual(bundle["time"]["selection"], "hold latest frame at or before requested UTC; do not interpolate")
        self.assertFalse(bundle["operationalDisplay"]["defaultVisible"])
        self.assertEqual(bundle["operationalDisplay"]["menu"], "advanced-layers")
        self.assertFalse(bundle["operationalDisplay"]["assumptionDriven"])


class DrapHistoryTests(unittest.TestCase):
    def test_daily_archive_reduction_ignores_pngs_and_keeps_one_frame_per_bucket(self) -> None:
        documents = [
            ("SWX_DRAP20_C_SWPC_20260806000100_GLOBAL.txt", sample_text("2026-08-06 00:01", 1.0)),
            ("SWX_DRAP20_C_SWPC_20260806001400_GLOBAL.txt", sample_text("2026-08-06 00:14", 2.0)),
            ("SWX_DRAP20_C_SWPC_20260806001600_GLOBAL.txt", sample_text("2026-08-06 00:16", 3.0)),
        ]
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            image = b"not relevant"
            image_info = tarfile.TarInfo("SWX_DRAP20_C_SWPC_20260806000100_GLOBAL.png")
            image_info.size = len(image)
            archive.addfile(image_info, io.BytesIO(image))
            for name, text in documents:
                encoded = text.encode()
                info = tarfile.TarInfo(name)
                info.size = len(encoded)
                archive.addfile(info, io.BytesIO(encoded))
        stream.seek(0)

        grid, frames = reduce_ncei_archive(stream, cadence_minutes=15)
        self.assertEqual(grid["longitudeCount"], 90)
        self.assertEqual([frame["validAt"] for frame in frames], [
            "2026-08-06T00:14:00Z",
            "2026-08-06T00:16:00Z",
        ])

    def test_bigmem_snapshots_round_trip_only_matching_grids_and_times(self) -> None:
        retrieved = dt.datetime(2026, 8, 6, 20, 27, tzinfo=dt.timezone.utc)
        bundle = build_drap_bundle(sample_text(), retrieved_at=retrieved)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = snapshot_current_frame(root, bundle)
            self.assertTrue(path.name.startswith("drap-20260806"))
            frames = load_snapshot_frames(
                root,
                start=retrieved - dt.timedelta(hours=1),
                end=retrieved,
                grid=bundle["grid"],
            )
            self.assertEqual([frame["validAt"] for frame in frames], ["2026-08-06T20:26:00Z"])

            document = json.loads(path.read_text())
            document["grid"]["longitudeStepDeg"] = 5
            path.write_text(json.dumps(document))
            self.assertEqual(load_snapshot_frames(
                root,
                start=retrieved - dt.timedelta(hours=1),
                end=retrieved,
                grid=bundle["grid"],
            ), [])

    def test_ncei_archive_discovery_is_bounded_to_the_official_product(self) -> None:
        start = dt.datetime(2026, 8, 5, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(ncei_archive_query_url(start, end)).query)
        self.assertEqual(query["sat"], ["SWPC-Models"])
        self.assertEqual(query["inst"], ["DRAP"])
        self.assertEqual(query["prod"], ["SWX_DRAP20"])

        files = parse_ncei_archive_index({
            "status": {"code": 200, "message": "OK"},
            "data": [
                {
                    "product": "SWX_DRAP20",
                    "file_link": "https://archive.data.noaa.gov/satellite-spaceweather/SWPC/Models/DRAP/SWX_DRAP20/2026/08/SWX_DRAP20_C_SWPC_20260805.tar.gz",
                    "size_bytes": 62_915_821,
                    "time_coverage_start": "2026-08-05T00:00:00.000Z",
                    "time_coverage_end": "2026-08-06T00:00:00.000Z",
                },
                {"product": "OTHER", "file_link": "https://example.invalid/not-noaa.tar.gz"},
            ],
        })
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["sizeBytes"], 62_915_821)


if __name__ == "__main__":
    unittest.main()
