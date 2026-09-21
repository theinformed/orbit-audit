import base64
import math
import struct
import unittest

from pipeline import swmf


def _decoded_u16(encoded: str) -> list[int]:
    body = base64.b64decode(encoded)
    return list(struct.unpack(f"<{len(body) // 2}H", body))


def _synthetic_plane() -> dict[str, list[float]]:
    plane = {name: [] for name in ("x", "cross", *swmf._PlaneSampler.field_names)}
    for x_step in range(-40, 51):
        x_value = x_step * 0.5
        for cross_step in range(-50, 51):
            cross_value = cross_step * 0.5
            radius = math.hypot(x_value, cross_value)
            if x_value > 0 and radius > 18:
                density, pressure, speed, magnetic = 2.0, 0.01, 400.0, 5.0
            elif x_value > 0 and radius > 14:
                density, pressure, speed, magnetic = 8.0, 0.2, 150.0, 10.0
            else:
                density, pressure, speed, magnetic = 0.5, 0.1, 20.0, 50.0
            if radius > 0:
                bx = -cross_value / radius * magnetic
                by = x_value / radius * magnetic
            else:
                bx, by = magnetic, 0.0
            current = 0.001 + 0.2 * math.exp(-((radius - 14.0) / 0.35) ** 2)
            plane["x"].append(x_value)
            plane["cross"].append(cross_value)
            plane["rho"].append(density)
            plane["ux"].append(-speed)
            plane["uy"].append(0.0)
            plane["uz"].append(0.0)
            plane["bx"].append(bx)
            plane["by"].append(by)
            plane["bz"].append(0.0)
            plane["pressure"].append(pressure)
            plane["jx"].append(0.0)
            plane["jy"].append(0.0)
            plane["jz"].append(current)
    return plane


def _synthetic_rbe_file(
    bad_radii: dict[tuple[int, int], float] | None = None,
    misordered: set[tuple[int, int]] | None = None,
) -> bytes:
    """A well-formed RBE file, optionally with specific cells made bad.

    ``bad_radii`` maps (radial index, MLT index) to a mapped equatorial radius
    outside the plausibility band. ``misordered`` names cells whose stored
    source-grid coordinates disagree with the declared grid.
    """
    bad_radii = bad_radii or {}
    misordered = misordered or set()
    radial_count, mlt_count, energy_count, pitch_count = 51, 48, 12, 12
    energies = [10.0 + index * 10 for index in range(energy_count)]
    pitch = [0.01 + index * 0.08 for index in range(pitch_count)]
    radial = [10.0 + index for index in range(radial_count)]
    lines = [
        f"1.01570 {radial_count} {mlt_count} {energy_count} {pitch_count} 2",
        " ".join(map(str, energies)),
        " ".join(map(str, pitch)),
        " ".join(map(str, radial)),
        " ".join(["0"] * 11),
    ]
    distribution = " ".join(str(index + 1) for index in range(energy_count * pitch_count))
    for radial_index, radial_value in enumerate(radial):
        for mlt_index in range(mlt_count):
            source_mlt = mlt_index * 0.5
            mapped_mlt = source_mlt + 0.25
            equatorial_radius = bad_radii.get(
                (radial_index, mlt_index), 1.1 + radial_index * 0.1)
            stored_radial, stored_mlt = radial_value, source_mlt
            if (radial_index, mlt_index) in misordered:
                stored_mlt = source_mlt + 5.0
            lines.append(f"{stored_radial} {stored_mlt} {equatorial_radius} {mapped_mlt} 1e-5 50 0")
            lines.append(distribution)
    return ("\n".join(lines) + "\n").encode("ascii")


class SwmfStructureTests(unittest.TestCase):
    def test_structure_profiles_recover_supported_dayside_transitions(self) -> None:
        result = swmf._derive_plane_structures(_synthetic_plane(), "equatorial")
        bow = _decoded_u16(result["bowShockRadiusU16"])
        magnetopause = _decoded_u16(result["magnetopauseProxyRadiusU16"])
        center = list(swmf.STRUCTURE_ANGLES_DEGREES).index(0)

        self.assertAlmostEqual(bow[center] / swmf.STRUCTURE_RADIUS_SCALE, 18.0, delta=0.75)
        self.assertAlmostEqual(magnetopause[center] / swmf.STRUCTURE_RADIUS_SCALE, 14.0, delta=0.75)
        supported_pairs = [
            (outer, inner)
            for outer, inner in zip(bow, magnetopause)
            if outer != swmf.STRUCTURE_MISSING_U16 and inner != swmf.STRUCTURE_MISSING_U16
        ]
        self.assertGreater(len(supported_pairs), 20)
        self.assertTrue(all(outer > inner for outer, inner in supported_pairs))
        self.assertGreater(result["projectedFlowStreamlines"]["lineCount"], 0)
        self.assertGreater(result["projectedMagneticStreamlines"]["lineCount"], 0)
        for field in ("projectedFlowStreamlines", "projectedMagneticStreamlines"):
            encoded = result[field]
            offsets = _decoded_u16(encoded["offsetsU16"])
            self.assertEqual(len(offsets), encoded["lineCount"] + 1)
            self.assertEqual(offsets[-1], encoded["pointCount"])
        flow = result["projectedFlowStreamlines"]
        self.assertEqual(len(_decoded_u16(flow["speedU16"])), flow["pointCount"])
        self.assertTrue(all(value > 0 for value in _decoded_u16(flow["speedU16"])))

    def test_uniform_solar_wind_does_not_fabricate_boundaries(self) -> None:
        samples = [
            {
                "radius": 30.0 - index * 0.25,
                "density": 2.0,
                "speed": 400.0,
                "magneticField": 5.0,
                "pressure": 0.01,
                "currentDensity": 0.001,
            }
            for index in range(80)
        ]
        self.assertEqual(swmf._ray_boundaries(samples), (None, None))

    def test_scalar_encoding_keeps_missing_and_saturation_distinct(self) -> None:
        values = [math.nan, -1.0, 5.0, 20.0]
        encoded, masks = swmf._quantized_with_mask(
            values,
            list(range(len(values))),
            {"scale": "linear", "minimum": 0.0, "maximum": 10.0},
        )
        self.assertEqual(_decoded_u16(encoded), [0, 0, 32768, 65535])
        self.assertEqual(
            list(base64.b64decode(masks)),
            [swmf.FIELD_MASK_MISSING, swmf.FIELD_MASK_CLIPPED_LOW, 0, swmf.FIELD_MASK_CLIPPED_HIGH],
        )

    def test_rbe_uses_mapped_equatorial_mlt_not_uniform_source_grid_mlt(self) -> None:
        radius, magnetic_local_time = swmf._rbe_equatorial_coordinate(
            [70.16, 23.5, 9.968, 23.941, 2.136e-8, 50.0, 0.0]
        )
        self.assertEqual(radius, 9.968)
        self.assertEqual(magnetic_local_time, 23.941)
        self.assertNotEqual(magnetic_local_time, 23.5)

    def test_rbe_reducer_retains_all_pitch_channels_for_selected_energies(self) -> None:
        reduced = swmf._parse_radiation(_synthetic_rbe_file())
        coordinates = _decoded_u16(reduced["coordinatesU16"])
        self.assertEqual(coordinates[:4], [1100, 250, 1100, 750])
        self.assertEqual(len(reduced["pitchCoordinatesSin"]), 12)
        self.assertEqual(len(reduced["pitchAnglesDegrees"]), 12)
        for energy in reduced["energiesKev"]:
            key = str(energy)
            self.assertEqual(len(_decoded_u16(reduced["electronFlux"][key])), 51 * 48)
            self.assertEqual(len(_decoded_u16(reduced["pitchResolvedElectronFlux"][key])), 51 * 48 * 12)
            self.assertEqual(reduced["gridShape"], {"radialCount": 51, "magneticLocalTimeCount": 48})


class RbeOutlierHandling(unittest.TestCase):
    """The published RBE grid must stay a rectangle that gridShape describes.

    src/radiation-belt.ts validateGridShape() throws a RangeError unless
    radialCount * magneticLocalTimeCount equals the published point count. When
    the outlier path first dropped single cells it produced 2447 points under a
    51x48 gridShape, so the browser would have thrown the moment the branch fired
    -- and it does not fire while the data happens to sit inside the band, which
    is why nothing showed it. These are the proofs that it cannot happen again.
    """

    def shape_is_consistent(self, reduced: dict) -> int:
        shape = reduced["gridShape"]
        points = len(_decoded_u16(reduced["coordinatesU16"])) // 2
        product = shape["radialCount"] * shape["magneticLocalTimeCount"]
        self.assertEqual(product, points)
        self.assertEqual(reduced["count"], points)
        for energy in reduced["energiesKev"]:
            self.assertEqual(len(_decoded_u16(reduced["electronFlux"][str(energy)])), points)
            self.assertEqual(
                len(_decoded_u16(reduced["pitchResolvedElectronFlux"][str(energy)])), points * 12)
        return points

    def test_a_clean_frame_still_publishes_the_whole_grid(self):
        self.assertEqual(self.shape_is_consistent(swmf._parse_radiation(_synthetic_rbe_file())),
                         51 * 48)

    def test_one_out_of_band_cell_does_not_break_the_grid_contract(self):
        reduced = swmf._parse_radiation(_synthetic_rbe_file(bad_radii={(3, 7): 55.0}))
        self.assertEqual(self.shape_is_consistent(reduced), 50 * 48)
        self.assertEqual(reduced["gridShape"],
                         {"radialCount": 50, "magneticLocalTimeCount": 48})

    def test_one_out_of_band_cell_does_not_discard_the_frame(self):
        """The whole point of the outlier path: one bad cell keeps the layer."""
        reduced = swmf._parse_radiation(_synthetic_rbe_file(bad_radii={(3, 7): 55.0}))
        self.assertGreater(reduced["count"], 0)

    def test_two_bad_cells_in_one_shell_cost_only_that_shell(self):
        reduced = swmf._parse_radiation(
            _synthetic_rbe_file(bad_radii={(3, 7): 55.0, (3, 9): 61.0}))
        self.assertEqual(reduced["gridShape"]["radialCount"], 50)

    def test_a_misordered_block_drops_its_shell_instead_of_raising(self):
        """This used to raise, which was the same defect shape as the band."""
        reduced = swmf._parse_radiation(_synthetic_rbe_file(misordered={(11, 2)}))
        self.assertEqual(self.shape_is_consistent(reduced), 50 * 48)

    def test_the_backstop_measures_genuinely_bad_cells_not_quantisation(self):
        """Two bad cells in two shells is 0.08% of the frame, not 3.9%.

        Shell quantisation removes 96 cells to keep the grid rectangular. If the
        backstop counted those it would turn Sean's 2% tolerance into 0.04% and
        fail frames he intended to publish.
        """
        reduced = swmf._parse_radiation(
            _synthetic_rbe_file(bad_radii={(3, 7): 55.0, (20, 9): 61.0}))
        self.assertEqual(self.shape_is_consistent(reduced), 49 * 48)

    def test_a_frame_that_is_mostly_bad_still_fails(self):
        """Serving a hollowed-out belt would be worse than serving none."""
        bad = {(radial, mlt): 55.0 for radial in range(40) for mlt in range(48)}
        with self.assertRaises(RuntimeError) as raised:
            swmf._parse_radiation(_synthetic_rbe_file(bad_radii=bad))
        self.assertIn("RBE_MAX_OUTLIER_FRACTION", str(raised.exception))

    def test_a_stretched_tail_inside_the_widened_band_is_kept_whole(self):
        """16.15 and 17.05 R_E are the values NOAA actually served on 08-07/08-08.

        They are a stretched tail, not corruption. Under the old <= 15 band each
        one discarded the entire geospace bundle.
        """
        reduced = swmf._parse_radiation(
            _synthetic_rbe_file(bad_radii={(3, 7): 16.15, (20, 9): 17.049}))
        self.assertEqual(self.shape_is_consistent(reduced), 51 * 48)


if __name__ == "__main__":
    unittest.main()
