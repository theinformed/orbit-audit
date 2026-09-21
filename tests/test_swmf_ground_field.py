"""Proofs for the ground magnetic perturbation reduction. No network, no clock.

The file this reads is NOAA's `mag_grid`: the ground signature of a geomagnetic
storm on a geographic grid, split by the current system the model holds
responsible. Two properties are worth defending, and both have a history here:

  * the shape the file DECLARES and the rows it CARRIES must agree, because a
    grid published with the wrong shape is a browser-side crash or, worse, a
    field drawn at the wrong longitudes; and
  * a frame the run did not publish must arrive as a gap, never as a quiet
    field. A comfortable zero over a storm is the failure this whole site is
    built to avoid.

Every assertion below is an arithmetic identity or an exact refusal. Nothing
here is a judgement about whether a picture looks right.
"""

from __future__ import annotations

import base64
import datetime as dt
import math
import struct
import unittest

from pipeline import swmf


LONGITUDE_COUNT, LATITUDE_COUNT = swmf.MAG_GRID_EXPECTED_SHAPE
CELL_COUNT = LONGITUDE_COUNT * LATITUDE_COUNT
LONGITUDE_STEP = 360.0 / LONGITUDE_COUNT
LATITUDE_START = -85.0
LATITUDE_STEP = 5.0
#: One uint16 step, in nT. Every decode below is exact to half of this.
QUANTUM_NT = (swmf.GROUND_FIELD_ENCODING["maximum"] - swmf.GROUND_FIELD_ENCODING["minimum"]) / 65535


def cell_value(component: int, system: int, row: int, column: int) -> float:
    """A distinct, reproducible value per component/system/cell.

    Deliberately not smooth and not symmetric, so a transposed grid, a swapped
    component or a mixed-up current system cannot survive by coincidence.
    """
    seed = (component * 31 + system * 7 + row * 3 + column) % 97
    return (seed - 48) * 3.5 + row * 0.25 - column * 0.125


def synthetic_mag_grid(
    *,
    longitude_count: int = LONGITUDE_COUNT,
    latitude_count: int = LATITUDE_COUNT,
    declared_shape: tuple[int, int] | None = None,
    header: str = swmf.MAG_GRID_HEADER,
    columns: tuple[str, ...] = swmf.MAG_GRID_COLUMNS,
    drop_rows: int = 0,
    swap_rows: tuple[int, int] | None = None,
) -> bytes:
    """A byte-for-byte plausible mag_grid file, built to be picked apart."""
    declared = declared_shape or (longitude_count, latitude_count)
    lines = [
        header,
        "         0  1.9740000000E+04  2  0 15",
        f"{declared[0]:8d}{declared[1]:8d}",
        " ".join(columns),
    ]
    rows: list[str] = []
    for row in range(latitude_count):
        for column in range(longitude_count):
            values = [column * LONGITUDE_STEP, LATITUDE_START + row * LATITUDE_STEP]
            for system in range(4):
                for component in range(3):
                    values.append(cell_value(component, system + 1, row, column))
            # Column order is Lon Lat, then the three totals, then the four
            # per-source triples. The total is written as the exact sum, which
            # is what NOAA's own file does to 1.7e-8 nT.
            totals = [
                sum(values[2 + system * 3 + component] for system in range(4))
                for component in range(3)
            ]
            ordered = values[:2] + totals + values[2:]
            rows.append(" ".join(f"{value:.10E}" for value in ordered))
    if swap_rows is not None:
        first, second = swap_rows
        rows[first], rows[second] = rows[second], rows[first]
    if drop_rows:
        rows = rows[:-drop_rows]
    return "\n".join(lines + rows).encode("ascii")


def decode_u16(encoded: str) -> list[float]:
    raw = base64.b64decode(encoded)
    count = len(raw) // 2
    minimum = swmf.GROUND_FIELD_ENCODING["minimum"]
    span = swmf.GROUND_FIELD_ENCODING["maximum"] - minimum
    return [minimum + struct.unpack_from("<H", raw, index * 2)[0] / 65535 * span for index in range(count)]


def decode_u8(encoded: str) -> list[int]:
    return list(base64.b64decode(encoded))


class GridShape(unittest.TestCase):
    """What the header declares and what the file carries must be one number."""

    def test_parsed_shape_multiplies_out_to_the_rows_carried(self) -> None:
        parsed = swmf._parse_mag_grid(synthetic_mag_grid())
        self.assertEqual(parsed["longitudeCount"] * parsed["latitudeCount"], CELL_COUNT)
        for name in swmf.MAG_GRID_COLUMNS[2:]:
            self.assertEqual(len(parsed["columns"][name]), CELL_COUNT)

    def test_axes_are_exactly_the_arithmetic_progressions_they_claim(self) -> None:
        parsed = swmf._parse_mag_grid(synthetic_mag_grid())
        last_longitude = parsed["longitudeStartDeg"] + (parsed["longitudeCount"] - 1) * parsed["longitudeStepDeg"]
        last_latitude = parsed["latitudeStartDeg"] + (parsed["latitudeCount"] - 1) * parsed["latitudeStepDeg"]
        self.assertAlmostEqual(last_longitude, 360.0 - LONGITUDE_STEP, places=9)
        self.assertAlmostEqual(last_latitude, -LATITUDE_START, places=9)
        # The longitude axis closes the globe exactly once, which is the whole
        # reason the browser may wrap its texture rather than duplicate a column.
        self.assertAlmostEqual(parsed["longitudeCount"] * parsed["longitudeStepDeg"], 360.0, places=9)

    def test_a_row_short_of_the_declared_shape_is_refused(self) -> None:
        with self.assertRaises(RuntimeError) as raised:
            swmf._parse_mag_grid(synthetic_mag_grid(drop_rows=1))
        self.assertIn(str(CELL_COUNT), str(raised.exception))
        self.assertIn(str(CELL_COUNT - 1), str(raised.exception))

    def test_a_declared_shape_that_is_not_the_operational_grid_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            swmf._parse_mag_grid(synthetic_mag_grid(declared_shape=(LONGITUDE_COUNT, LATITUDE_COUNT + 1)))

    def test_two_rows_out_of_order_are_refused_rather_than_drawn_elsewhere(self) -> None:
        # Adjacent cells differ in longitude, so a swap moves a value to another
        # place on the Earth. This is the failure that must never be silent.
        with self.assertRaises(RuntimeError) as raised:
            swmf._parse_mag_grid(synthetic_mag_grid(swap_rows=(0, 1)))
        self.assertIn("ordering", str(raised.exception))

    def test_a_changed_header_sentence_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            swmf._parse_mag_grid(synthetic_mag_grid(header="Magnetometer grid (SM) [deg] dB (North-East-Down) [nT]"))

    def test_renamed_columns_are_refused(self) -> None:
        renamed = list(swmf.MAG_GRID_COLUMNS)
        renamed[5] = "dBnRing"
        with self.assertRaises(RuntimeError):
            swmf._parse_mag_grid(synthetic_mag_grid(columns=tuple(renamed)))


class CurrentSystemDecomposition(unittest.TestCase):
    """The four attributions add up to the total, exactly, cell by cell."""

    def setUp(self) -> None:
        self.parsed = swmf._parse_mag_grid(synthetic_mag_grid())
        self.encoded = swmf._encode_ground_frame(self.parsed)

    def test_the_four_sources_sum_to_the_total_in_the_source_columns(self) -> None:
        worst = 0.0
        for component in ("dBn", "dBe", "dBd"):
            total = self.parsed["columns"][component]
            parts = [self.parsed["columns"][f"{component}{suffix}"] for suffix in ("Mhd", "Fac", "Hal", "Ped")]
            for index in range(CELL_COUNT):
                worst = max(worst, abs(sum(part[index] for part in parts) - total[index]))
        self.assertLess(worst, 1e-3)

    def test_the_sum_survives_quantization_to_within_four_quanta(self) -> None:
        """Four rounded numbers can miss their rounded total by four half-steps."""
        for component in ("north", "east", "down"):
            total = decode_u16(self.encoded["fieldsU16"]["total"][component])
            parts = [
                decode_u16(self.encoded["fieldsU16"][system][component])
                for system in ("magnetospheric", "fieldAligned", "hall", "pedersen")
            ]
            worst = max(
                abs(sum(part[index] for part in parts) - total[index]) for index in range(CELL_COUNT)
            )
            self.assertLessEqual(worst, 4 * QUANTUM_NT)

    def test_every_published_cell_round_trips_to_half_a_quantum(self) -> None:
        for system, suffix in swmf.GROUND_CURRENT_SYSTEMS:
            for component, stem in swmf.GROUND_COMPONENTS:
                source = self.parsed["columns"][f"{stem}{suffix}"]
                decoded = decode_u16(self.encoded["fieldsU16"][system][component])
                self.assertEqual(len(decoded), CELL_COUNT)
                worst = max(abs(decoded[index] - source[index]) for index in range(CELL_COUNT))
                self.assertLessEqual(worst, QUANTUM_NT / 2 + 1e-9)

    def test_nothing_in_range_is_flagged_missing_or_clipped(self) -> None:
        for system, _ in swmf.GROUND_CURRENT_SYSTEMS:
            for component, _stem in swmf.GROUND_COMPONENTS:
                self.assertEqual(sum(decode_u8(self.encoded["fieldMasksU8"][system][component])), 0)

    def test_the_reported_maximum_is_the_grid_cell_it_names(self) -> None:
        extrema = self.encoded["extrema"]
        column = round((extrema["maximumHorizontalLongitudeDeg"] - 0.0) / LONGITUDE_STEP)
        row = round((extrema["maximumHorizontalLatitudeDeg"] - LATITUDE_START) / LATITUDE_STEP)
        index = row * LONGITUDE_COUNT + column
        north = self.parsed["columns"]["dBn"][index]
        east = self.parsed["columns"]["dBe"][index]
        self.assertAlmostEqual(math.hypot(north, east), extrema["maximumHorizontalNt"], places=3)
        # And it really is the largest, not merely a large one.
        largest = max(
            math.hypot(self.parsed["columns"]["dBn"][cell], self.parsed["columns"]["dBe"][cell])
            for cell in range(CELL_COUNT)
        )
        self.assertAlmostEqual(largest, extrema["maximumHorizontalNt"], places=3)


class MissingFrames(unittest.TestCase):
    """A frame the run did not publish is a hole, and says which hole."""

    def bundle(self, *, frames: list[dict], gaps: list[dict]):
        return swmf._ground_field_bundle(
            now=dt.datetime(2026, 8, 8, 18, 0, tzinfo=dt.timezone.utc),
            selected_times=[
                dt.datetime(2026, 8, 8, 17, 0, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=20 * step)
                for step in range(6)
            ],
            grid={"longitudeCount": LONGITUDE_COUNT, "latitudeCount": LATITUDE_COUNT,
                  "longitudeStartDeg": 0.0, "longitudeStepDeg": LONGITUDE_STEP,
                  "latitudeStartDeg": LATITUDE_START, "latitudeStepDeg": LATITUDE_STEP},
            frames=frames,
            gaps=gaps,
        )

    def frame(self, validAt: str) -> dict:
        return {"validAt": validAt, "runAt": validAt, "leadMinutes": 0}

    def test_a_gap_is_named_and_the_frame_count_drops_by_exactly_one(self) -> None:
        frames = [self.frame(f"2026-08-08T{17 + step // 3:02d}:{(step % 3) * 20:02d}:00Z") for step in range(5)]
        gaps = [{"validAt": "2026-08-08T18:40:00Z", "reason": "no-mag-grid-file-published"}]
        bundle = self.bundle(frames=frames, gaps=gaps)
        assert bundle is not None
        self.assertEqual(len(bundle["frames"]), 5)
        self.assertEqual(bundle["time"]["selectedFrameCount"], 6)
        self.assertEqual(len(bundle["frames"]) + len(bundle["time"]["noDataIntervals"]),
                         bundle["time"]["selectedFrameCount"])
        self.assertFalse(bundle["time"]["coverageComplete"])
        # The gap carries the time it is a gap FOR. A frame count alone cannot
        # tell the browser which UTC to refuse.
        self.assertEqual(bundle["time"]["noDataIntervals"][0]["validAt"], "2026-08-08T18:40:00Z")

    def test_no_gap_reports_complete_coverage(self) -> None:
        frames = [self.frame(f"2026-08-08T{17 + step // 3:02d}:{(step % 3) * 20:02d}:00Z") for step in range(6)]
        bundle = self.bundle(frames=frames, gaps=[])
        assert bundle is not None
        self.assertTrue(bundle["time"]["coverageComplete"])
        self.assertEqual(len(bundle["time"]["noDataIntervals"]), 0)

    def test_no_usable_frame_publishes_no_layer_at_all(self) -> None:
        """Not an empty grid of zeros. No bundle, so no artifact, so no layer."""
        self.assertIsNone(self.bundle(frames=[], gaps=[{"validAt": "x", "reason": "y"}]))

    def test_a_grid_that_was_never_established_publishes_no_layer(self) -> None:
        bundle = swmf._ground_field_bundle(
            now=dt.datetime(2026, 8, 8, 18, 0, tzinfo=dt.timezone.utc),
            selected_times=[dt.datetime(2026, 8, 8, 18, 0, tzinfo=dt.timezone.utc)],
            grid=None,
            frames=[self.frame("2026-08-08T18:00:00Z")],
            gaps=[],
        )
        self.assertIsNone(bundle)


class NonFiniteCells(unittest.TestCase):
    """One unusable cell is flagged, counted, and never encoded as zero."""

    def test_a_nan_cell_sets_the_missing_flag_and_is_counted(self) -> None:
        parsed = swmf._parse_mag_grid(synthetic_mag_grid())
        parsed["columns"]["dBn"][7] = float("nan")
        encoded = swmf._encode_ground_frame(parsed)
        mask = decode_u8(encoded["fieldMasksU8"]["total"]["north"])
        self.assertEqual(mask[7] & swmf.FIELD_MASK_MISSING, swmf.FIELD_MASK_MISSING)
        self.assertEqual(sum(1 for flag in mask if flag & swmf.FIELD_MASK_MISSING), 1)
        self.assertEqual(encoded["extrema"]["unusableCellCount"], 1)
        # The neighbouring component of the same cell is untouched: one bad
        # number costs one number, not a layer.
        self.assertEqual(decode_u8(encoded["fieldMasksU8"]["total"]["east"])[7], 0)

    def test_a_value_past_the_encodable_range_is_clipped_and_says_so(self) -> None:
        parsed = swmf._parse_mag_grid(synthetic_mag_grid())
        parsed["columns"]["dBn"][11] = swmf.GROUND_FIELD_ENCODING["maximum"] * 2
        encoded = swmf._encode_ground_frame(parsed)
        mask = decode_u8(encoded["fieldMasksU8"]["total"]["north"])
        self.assertEqual(mask[11] & swmf.FIELD_MASK_CLIPPED_HIGH, swmf.FIELD_MASK_CLIPPED_HIGH)
        self.assertEqual(decode_u16(encoded["fieldsU16"]["total"]["north"])[11],
                         swmf.GROUND_FIELD_ENCODING["maximum"])

    def test_the_encodable_range_covers_the_strongest_storm_signature_reported(self) -> None:
        # Ground perturbation in the severe-storm literature is a few thousand
        # nT. The range must contain that with room, and still resolve finer
        # than a magnetometer's noise floor of about 0.1 nT.
        self.assertGreaterEqual(swmf.GROUND_FIELD_ENCODING["maximum"], 5000.0)
        self.assertEqual(swmf.GROUND_FIELD_ENCODING["minimum"], -swmf.GROUND_FIELD_ENCODING["maximum"])
        self.assertLess(QUANTUM_NT, 0.2)


class HonestyContract(unittest.TestCase):
    """What the bundle is allowed to claim about itself."""

    def bundle(self):
        parsed = swmf._parse_mag_grid(synthetic_mag_grid())
        frame = {"validAt": "2026-08-08T18:00:00Z", "runAt": "2026-08-08T12:03:00Z", "leadMinutes": 357,
                 **swmf._encode_ground_frame(parsed)}
        return swmf._ground_field_bundle(
            now=dt.datetime(2026, 8, 8, 18, 0, tzinfo=dt.timezone.utc),
            selected_times=[dt.datetime(2026, 8, 8, 18, 0, tzinfo=dt.timezone.utc)],
            grid={key: value for key, value in parsed.items() if key != "columns"},
            frames=[frame],
            gaps=[],
        )

    def test_every_current_system_the_encoder_writes_is_described_in_the_bundle(self) -> None:
        bundle = self.bundle()
        assert bundle is not None
        described = {entry["key"] for entry in bundle["currentSystems"]}
        self.assertEqual(described, {key for key, _ in swmf.GROUND_CURRENT_SYSTEMS})
        self.assertEqual(described, set(bundle["frames"][0]["fieldsU16"]))

    def test_the_lumped_magnetospheric_field_is_never_called_the_ring_current(self) -> None:
        """It contains the cross-tail and magnetopause currents too.

        Naming it after one of the three would be a confident mislabel of a
        real number, which is worse than no label at all.
        """
        bundle = self.bundle()
        assert bundle is not None
        entry = next(item for item in bundle["currentSystems"] if item["key"] == "magnetospheric")
        self.assertNotIn("ring current", entry["label"].lower())
        for phrase in ("ring current", "cross-tail", "magnetopause"):
            self.assertIn(phrase, entry["meaning"].lower())

    def test_the_bundle_says_the_split_is_the_model_s_own_attribution(self) -> None:
        bundle = self.bundle()
        assert bundle is not None
        self.assertIn("attribution", bundle["attribution"].lower())
        self.assertIn("no instrument", bundle["attribution"].lower())

    def test_the_bundle_carries_no_wall_clock_so_its_content_hash_is_stable(self) -> None:
        """A generatedAt would mint a new artifact, and a new rsync, every cycle."""
        first = self.bundle()
        second = self.bundle()
        self.assertEqual(first, second)
        self.assertNotIn("generatedAt", first or {})

    def test_the_grid_declares_that_the_caps_are_absent_rather_than_quiet(self) -> None:
        bundle = self.bundle()
        assert bundle is not None
        self.assertEqual(bundle["grid"]["cellCount"], CELL_COUNT)
        self.assertIn("extrapolat", bundle["grid"]["polarCaps"].lower())
        covered_latitude = abs(bundle["grid"]["latitudeStartDeg"])
        self.assertLess(covered_latitude, 90.0)


class CacheHygiene(unittest.TestCase):
    """A cached file the pruner cannot name is a file that is never deleted."""

    def test_the_pruner_recognises_every_family_the_fetcher_caches(self) -> None:
        from pipeline import prune_swmf_cache

        for name in (
            "y0_20260808T1203_20260808T182900",
            "z0_20260808T1203_20260808T182900",
            "mag_grid_20260808T1203_20260808T182900.txt",
            "20260808_182900_e.fls",
        ):
            self.assertIsNotNone(prune_swmf_cache.MODEL_FILE.fullmatch(name), name)
        # And nothing else. The pruner deletes files; its pattern is a whitelist.
        for name in ("manifest.json", "..", "mag_grid.txt", "notes"):
            self.assertIsNone(prune_swmf_cache.MODEL_FILE.fullmatch(name), name)


if __name__ == "__main__":
    unittest.main()
