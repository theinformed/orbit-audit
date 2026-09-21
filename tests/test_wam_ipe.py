from __future__ import annotations

import base64
import datetime as dt
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from netCDF4 import Dataset

from pipeline.wam_ipe import (
    PUBLISHED_CADENCE_MINUTES,
    ALTITUDE_INDICES,
    ION_DENSITY_VARIABLES,
    REQUESTED_HISTORY_HOURS,
    WAM_CACHE_RETENTION_HOURS,
    _prune_cache,
    _select_frame_urls,
    reduce_wam_ipe_files,
    reduce_wam_ipe_peak_files,
)


UTC = dt.timezone.utc


def write_ipe_fixture(
    path: Path,
    *,
    omit_variable: str | None = None,
    missing_sample: bool = False,
    init_date: str = "20260806_120000",
    fcst_date: str = "20260806_180000",
    layered_profile: bool = False,
) -> None:
    with Dataset(path, "w", format="NETCDF4") as dataset:
        dataset.createDimension("x01", 90)
        dataset.createDimension("x02", 91)
        dataset.createDimension("x03", 58)
        dataset.createVariable("lon", "f4", ("x01",))[:] = np.arange(0, 360, 4, dtype=np.float32)
        dataset.createVariable("lat", "f4", ("x02",))[:] = np.arange(-90, 92, 2, dtype=np.float32)
        dataset.createVariable("alt", "f4", ("x03",))[:] = np.array(
            [
                90, 95, 100, 105, 111, 116, 122, 129, 136, 143, 150, 158, 167, 175, 185,
                194, 204, 215, 227, 238, 251, 264, 278, 293, 308, 324, 341, 359, 378,
                398, 419, 441, 464, 489, 515, 542, 570, 600, 632, 665, 700, 737, 776,
                816, 859, 905, 952, 1002, 1055, 1169, 1295, 1435, 1590, 1762, 1952,
                2163, 2397, 2655,
            ],
            dtype=np.float32,
        )
        altitude_values = np.asarray(dataset.variables["alt"][:], dtype=np.float64)
        profile = np.interp(
            altitude_values,
            [90, 122, 167, 194, 227, 308, 952, 2655],
            [9, 11, 9.5, 11.2, 10.2, 12, 9, 8],
        )
        density_profile = np.power(10.0, profile).astype(np.float32) / len(ION_DENSITY_VARIABLES)
        for name in ION_DENSITY_VARIABLES:
            if name == omit_variable:
                continue
            variable = dataset.createVariable(
                name,
                "f4",
                ("x03", "x02", "x01"),
                zlib=True,
                fill_value=np.float32(-1e30),
            )
            variable[:] = density_profile[:, None, None] if layered_profile else np.float32(1e11 / len(ION_DENSITY_VARIABLES))
            if missing_sample and name == ION_DENSITY_VARIABLES[0]:
                variable[ALTITUDE_INDICES[0], 0, 0] = variable._FillValue
        dataset.init_date = init_date
        dataset.start_date = "20260806_090000"
        dataset.end_date = "20260808_120000"
        dataset.fcst_date = fcst_date
        dataset.run_type = "wfs"
        dataset.model = "ipe"
        dataset.cadence = "10"


def write_ipe05_fixture(path: Path) -> None:
    with Dataset(path, "w", format="NETCDF4") as dataset:
        dataset.createDimension("x01", 90)
        dataset.createDimension("x02", 91)
        dataset.createVariable("lon", "f4", ("x01",))[:] = np.arange(0, 360, 4, dtype=np.float32)
        dataset.createVariable("lat", "f4", ("x02",))[:] = np.arange(-90, 92, 2, dtype=np.float32)
        hm = np.add.outer(np.arange(91, dtype=np.float32), np.arange(90, dtype=np.float32)) + 250
        nm = np.full((91, 90), 1e12, dtype=np.float32)
        dataset.createVariable("HmF2", "f4", ("x02", "x01"))[:] = hm
        dataset.createVariable("NmF2", "f4", ("x02", "x01"))[:] = nm
        dataset.init_date = "20260806_120000"
        dataset.fcst_date = "20260806_180000"
        dataset.run_type = "wfs"
        dataset.model = "ipe"
        dataset.cadence = "05"


class WamIpeReductionTests(unittest.TestCase):
    def test_cache_pruner_protects_current_selection_and_keeps_resilience_margin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "space-explorer" / "wam-ipe-cache"
            cycle = root / "wfs.20260806" / "12"
            cycle.mkdir(parents=True)
            old_victim = cycle / "wfs.t12z.ipe10.20260806_180000.nc"
            old_protected = cycle / "wfs.t12z.ipe10.20260806_220000.nc"
            recent = cycle / "wfs.t12z.ipe10.20260807_020000.nc"
            for path in (old_victim, old_protected, recent):
                path.write_bytes(b"cache")
            now = time.time()
            old = now - (WAM_CACHE_RETENTION_HOURS + 1) * 3600
            os.utime(old_victim, (old, old))
            os.utime(old_protected, (old, old))

            with mock.patch.dict(os.environ, {"SPACE_EXPLORER_WAM_IPE_CACHE": str(root)}):
                dry_run = _prune_cache({old_protected}, dry_run=True, now=now)
                self.assertEqual(dry_run["removedFiles"], 1)
                self.assertTrue(old_victim.exists())
                applied = _prune_cache({old_protected}, now=now)

            self.assertEqual(WAM_CACHE_RETENTION_HOURS, REQUESTED_HISTORY_HOURS + 12)
            self.assertEqual(applied["removedFiles"], 1)
            self.assertFalse(old_victim.exists())
            self.assertTrue(old_protected.exists())
            self.assertTrue(recent.exists())

    def test_cache_pruner_refuses_a_window_shorter_than_published_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "space-explorer" / "wam-ipe-cache"
            root.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"SPACE_EXPLORER_WAM_IPE_CACHE": str(root)}):
                with self.assertRaisesRegex(RuntimeError, "unsafe WAM-IPE cache"):
                    _prune_cache(set(), retention_hours=REQUESTED_HISTORY_HOURS - 1)

    def test_exact_ipe05_hmf2_nmf2_are_preserved_as_five_minute_surface_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wfs.t12z.ipe05.20260806_180000.nc"
            write_ipe05_fixture(path)
            peak = reduce_wam_ipe_peak_files(
                [(dt.datetime(2026, 8, 6, 18, tzinfo=UTC), dt.datetime(2026, 8, 6, 12, tzinfo=UTC), path)],
                generated_at=dt.datetime(2026, 8, 6, 17, tzinfo=UTC),
                expected_latest_run_at=dt.datetime(2026, 8, 6, 12, tzinfo=UTC),
            )

        self.assertEqual(peak["sourceVariables"], ["HmF2", "NmF2"])
        self.assertEqual(peak["publishedCadenceMinutes"], 5)
        altitude = np.frombuffer(base64.b64decode(peak["frames"][0]["altitudeU16"]), dtype="<u2") * 0.1
        density = base64.b64decode(peak["frames"][0]["densityU8"])
        self.assertEqual(len(altitude), 45 * 46)
        self.assertAlmostEqual(float(altitude[0]), 250.0)
        self.assertGreater(max(density), 0)

    def test_profile_surfaces_require_real_column_peaks_and_never_create_a_d_layer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wfs.t12z.ipe10.20260806_180000.nc"
            write_ipe_fixture(path, layered_profile=True)
            bundle = reduce_wam_ipe_files(
                [(dt.datetime(2026, 8, 6, 18, tzinfo=UTC), dt.datetime(2026, 8, 6, 12, tzinfo=UTC), path)],
                generated_at=dt.datetime(2026, 8, 6, 17, tzinfo=UTC),
            )

        surfaces = bundle["frames"][0]["regionSurfaces"]
        self.assertGreater(surfaces["e"]["validColumnCount"], 0)
        self.assertGreater(surfaces["f1"]["validColumnCount"], 0)
        self.assertNotIn("d", surfaces)
        self.assertFalse(bundle["profileRegionSurfaces"]["dRegion"]["available"])
        self.assertIn("begins at 90 km", bundle["profileRegionSurfaces"]["dRegion"]["reason"])

    def test_reduction_preserves_vertical_coordinates_and_quantizes_quasi_neutral_density(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wfs.t12z.ipe10.20260806_180000.nc"
            write_ipe_fixture(path)
            bundle = reduce_wam_ipe_files(
                [(dt.datetime(2026, 8, 6, 18, tzinfo=UTC), dt.datetime(2026, 8, 6, 12, tzinfo=UTC), path)],
                generated_at=dt.datetime(2026, 8, 6, 20, tzinfo=UTC),
                expected_latest_run_at=dt.datetime(2026, 8, 6, 12, tzinfo=UTC),
            )

        self.assertEqual(bundle["status"], "forecast")
        self.assertEqual(bundle["runAt"], "2026-08-06T12:00:00Z")
        self.assertEqual(bundle["frames"][0]["validAt"], "2026-08-06T18:00:00Z")
        self.assertEqual(bundle["frames"][0]["runAt"], "2026-08-06T12:00:00Z")
        self.assertEqual(bundle["frames"][0]["leadMinutes"], 360)
        self.assertEqual(bundle["frames"][0]["phase"], "history")
        self.assertEqual(bundle["grid"]["ordering"], "altitude-latitude-longitude")
        self.assertEqual(bundle["grid"]["altitudesKm"][0], 90.0)
        self.assertEqual(bundle["grid"]["altitudesKm"][-1], 2655.0)
        self.assertEqual(bundle["grid"]["sampling"]["altitudeSourceIndices"], list(ALTITUDE_INDICES))
        self.assertEqual(bundle["grid"]["pointCount"], 30 * 46 * 45)
        encoded = base64.b64decode(bundle["frames"][0]["densityU8"], validate=True)
        self.assertEqual(len(encoded), bundle["grid"]["pointCount"])
        expected_code = round(((11 - 7) / (12.6 - 7)) * 255)
        self.assertEqual(set(encoded), {expected_code})
        validity = base64.b64decode(bundle["frames"][0]["validityBits"], validate=True)
        self.assertTrue(all(byte == 255 for byte in validity[:-1]))
        composition = base64.b64decode(bundle["frames"][0]["compositionU4"], validate=True)
        self.assertEqual(len(composition), bundle["grid"]["pointCount"] * 4)
        self.assertEqual(set(composition), {0x22, 0x02})
        self.assertEqual(bundle["ionComposition"]["species"], ["O+", "H+", "He+", "N+", "NO+", "O2+", "N2+"])
        self.assertIn("quasi-neutral", bundle["caveat"])
        self.assertIn("begins at 90 km", bundle["caveat"])

    def test_missing_published_ion_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.nc"
            write_ipe_fixture(path, omit_variable="NO_plus_density")
            with self.assertRaisesRegex(RuntimeError, "NO_plus_density"):
                reduce_wam_ipe_files(
                    [(dt.datetime(2026, 8, 6, 18, tzinfo=UTC), dt.datetime(2026, 8, 6, 12, tzinfo=UTC), path)],
                    generated_at=dt.datetime(2026, 8, 6, 20, tzinfo=UTC),
                )

    def test_missing_source_sample_remains_masked_in_density_and_composition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "masked.nc"
            write_ipe_fixture(path, missing_sample=True)
            bundle = reduce_wam_ipe_files(
                [(dt.datetime(2026, 8, 6, 18, tzinfo=UTC), dt.datetime(2026, 8, 6, 12, tzinfo=UTC), path)],
                generated_at=dt.datetime(2026, 8, 6, 20, tzinfo=UTC),
            )
        validity = base64.b64decode(bundle["frames"][0]["validityBits"], validate=True)
        density = base64.b64decode(bundle["frames"][0]["densityU8"], validate=True)
        composition = base64.b64decode(bundle["frames"][0]["compositionU4"], validate=True)
        self.assertEqual(validity[0] & 1, 0)
        self.assertEqual(density[0], 0)
        self.assertEqual(composition[:4], b"\x00\x00\x00\x00")

    def test_selection_spans_requested_history_and_latest_official_horizon(self) -> None:
        now = dt.datetime(2026, 8, 6, 20, 37, tzinfo=UTC)
        cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]] = []
        for cycle_offset in range(0, 9):
            run_at = dt.datetime(2026, 8, 4, 18, tzinfo=UTC) + dt.timedelta(hours=6 * cycle_offset)
            files = {
                run_at - dt.timedelta(hours=3) + dt.timedelta(minutes=10 * index): f"{run_at:%H}-{index}"
                for index in range(0, 55 * 6 + 1)
            }
            cycles.append((run_at, files))
        selected, coverage = _select_frame_urls(now, cycles)

        # 20:00, not 20:30: the grid is anchored on absolute multiples of the
        # published cadence rather than on the clock. It therefore starts a
        # little EARLIER than the bare `now - 48 h`, which is the safe
        # direction -- more history, never less.
        self.assertEqual(selected[0][0], dt.datetime(2026, 8, 4, 20, 0, tzinfo=UTC))
        cadence_seconds = PUBLISHED_CADENCE_MINUTES * 60
        epoch = dt.datetime(1970, 1, 1, tzinfo=UTC)
        self.assertEqual(
            (selected[0][0] - epoch).total_seconds() % cadence_seconds, 0,
            "the first frame must sit on the absolute cadence grid",
        )
        self.assertEqual(selected[-1][0], max(cycles[-1][1]))
        self.assertGreaterEqual(coverage["actualHistoryHours"], 48)
        self.assertFalse(coverage["sourceRetentionLimited"])
        self.assertGreaterEqual(coverage["forecastHours"], 48)
        self.assertTrue(all(right[0] > left[0] for left, right in zip(selected, selected[1:])))

    def test_successive_publish_runs_ask_for_the_same_frames(self) -> None:
        """The cache can only hit if the grid stops sliding.

        The publish job runs every five minutes. This selection used to be
        anchored on `now`, so the whole grid advanced with the clock, every
        target resolved to a different nearest source frame, and each run
        downloaded a fresh set. Measured on the live cache on 2026-09-08 that
        was a 24x overfetch: 1,052 full-field frames held, 22.34 GB, 995 of
        1,048 consecutive pairs exactly one source-cadence step apart, to ship
        one frame every four hours. It was the largest single writer to the
        spinning disk on that machine.
        """
        cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]] = []
        for cycle_offset in range(0, 9):
            run_at = dt.datetime(2026, 8, 4, 18, tzinfo=UTC) + dt.timedelta(hours=6 * cycle_offset)
            files = {
                run_at - dt.timedelta(hours=3) + dt.timedelta(minutes=10 * index): f"{run_at:%H}-{index}"
                for index in range(0, 55 * 6 + 1)
            }
            cycles.append((run_at, files))

        base = dt.datetime(2026, 8, 6, 20, 0, tzinfo=UTC)
        chosen = []
        for step in range(6):                      # 30 minutes of 5-minute runs
            now = base + dt.timedelta(minutes=5 * step)
            selected, _coverage = _select_frame_urls(now, cycles)
            chosen.append({valid_at for valid_at, _run_at, _url in selected})

        for index, later in enumerate(chosen[1:], start=1):
            self.assertEqual(
                later - chosen[0], set(),
                f"run {index} asked for frames run 0 did not; the grid is sliding again",
            )

    def test_cold_source_retention_shortfall_is_reported_not_invented(self) -> None:
        now = dt.datetime(2026, 8, 6, 20, 37, tzinfo=UTC)
        cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]] = []
        for cycle_offset in range(0, 8):
            run_at = dt.datetime(2026, 8, 5, 0, tzinfo=UTC) + dt.timedelta(hours=6 * cycle_offset)
            files = {
                run_at - dt.timedelta(hours=3) + dt.timedelta(minutes=10 * index): f"{run_at:%H}-{index}"
                for index in range(0, 55 * 6 + 1)
            }
            cycles.append((run_at, files))
        selected, coverage = _select_frame_urls(now, cycles)
        self.assertGreater(len(selected), 8)
        self.assertLess(coverage["actualHistoryHours"], 48)
        self.assertTrue(coverage["sourceRetentionLimited"])


if __name__ == "__main__":
    unittest.main()
