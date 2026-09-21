"""Offline tests for the thermosphere neutral-density reducer.

Every test builds its own NetCDF fixture on disk; nothing here reaches the
network.  The NRLMSIS tests are skipped when `pymsis` is absent and always pass
F10.7/Ap explicitly, because pymsis silently downloads historical indices when
they are omitted.
"""

from __future__ import annotations

import datetime as dt
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline import thermosphere
from pipeline.thermosphere import (
    AVOGADRO,
    CURATED_DENSITY_EVENTS,
    DEFAULT_THERMOSPHERE_MODEL,
    MODEL_ASSESSMENT_CITATION,
    MOLAR_MASS_KG,
    THERMOSPHERE_MODELS,
    WAM_ARCHIVE_START,
    ThermosphereFormatError,
    compare_models_for_event,
    global_mean_msis_density,
    resolve_thermosphere_model,
    archive_cycle_prefix,
    archive_frame_url,
    archive_listing_url,
    circular_orbital_speed_m_s,
    compare_to_msis,
    decay_rate_km_per_day,
    decode_log_density,
    drag_deceleration_m_s2,
    encode_log_density,
    ionised_fraction,
    mass_density_from_species,
    msis_available,
    msis_profile,
    pack_validity_mask,
    parse_frame_key,
    parse_wam_fixed_height,
    pressure_scale_height_km,
    reduce_thermosphere_frame,
    source_metadata,
)

ALTITUDES = [float(a) for a in range(100, 1001, 10)]
LATITUDES = [float(v) for v in np.linspace(-90.0, 90.0, 91)]
LONGITUDES = [float(v) for v in np.arange(0.0, 360.0, 4.0)]


# Global-mean neutral mass density measured from the real NOAA `wam_fixed_height`
# frame for 2024-05-08 12:00Z (quiet, solar maximum), pole rows excluded.  The
# fixture interpolates these anchors in log-density so it is a physically
# realistic thermosphere rather than a toy exponential -- which is what lets the
# NRLMSIS cross-check below be a meaningful assertion instead of a tautology.
WAM_REFERENCE_PROFILE = {
    100.0: 4.5518e-07,
    150.0: 2.2518e-09,
    200.0: 3.3061e-10,
    250.0: 9.2468e-11,
    300.0: 3.3398e-11,
    350.0: 1.3818e-11,
    400.0: 6.2296e-12,
    450.0: 2.9829e-12,
    500.0: 1.4948e-12,
    600.0: 4.1726e-13,
    700.0: 1.3136e-13,
    800.0: 4.6674e-14,
    1000.0: 9.2326e-15,
}


def synthetic_density(
    altitudes=ALTITUDES, latitudes=LATITUDES, longitudes=LONGITUDES, *, fill_poles=True
):
    """A realistic thermosphere: the measured WAM profile plus a dayside bulge."""
    anchors = sorted(WAM_REFERENCE_PROFILE)
    base = np.power(
        10.0,
        np.interp(
            np.asarray(altitudes, dtype=float),
            anchors,
            [math.log10(WAM_REFERENCE_PROFILE[a]) for a in anchors],
        ),
    )[:, None, None]
    lat = np.asarray(latitudes)[None, :, None]
    lon = np.asarray(longitudes)[None, None, :]

    diurnal = 1.0 + 0.4 * np.cos(np.deg2rad(lon - 150.0)) * np.cos(np.deg2rad(lat))
    density = base * diurnal
    density = np.broadcast_to(density, (len(altitudes), len(latitudes), len(longitudes))).copy()

    if fill_poles:
        for index, value in enumerate(latitudes):
            if abs(abs(value) - 90.0) < 1e-6:
                density[:, index, :] = 0.0
    return density


def write_fixture(
    path: Path,
    *,
    density=None,
    altitudes=ALTITUDES,
    latitudes=LATITUDES,
    longitudes=LONGITUDES,
    valid_at=dt.datetime(2026, 8, 7, 12, 0, tzinfo=dt.timezone.utc),
    omit=(),
):
    import netCDF4

    if density is None:
        density = synthetic_density(altitudes, latitudes, longitudes)

    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("lon", len(longitudes))
        dataset.createDimension("lat", len(latitudes))
        dataset.createDimension("hlevs", len(altitudes))
        dataset.createDimension("time", 1)
        if "lon" not in omit:
            dataset.createVariable("lon", "f4", ("lon",))[:] = longitudes
        if "lat" not in omit:
            dataset.createVariable("lat", "f4", ("lat",))[:] = latitudes
        if "hlevs" not in omit:
            dataset.createVariable("hlevs", "f4", ("hlevs",))[:] = altitudes
        if "time" not in omit:
            epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
            dataset.createVariable("time", "f8", ("time",))[:] = [
                (valid_at - epoch).total_seconds() / 86400.0
            ]
        if "den" not in omit:
            variable = dataset.createVariable("den", "f4", ("time", "hlevs", "lat", "lon"))
            variable[:] = density[None, ...]
    return path


class FixtureMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def parse(self, **kwargs):
        import netCDF4

        path = write_fixture(self.root / "frame.nc", **kwargs)
        with netCDF4.Dataset(path) as dataset:
            return parse_wam_fixed_height(dataset)


class ParserTests(FixtureMixin):
    def test_parses_a_well_formed_frame_and_preserves_physical_units(self) -> None:
        frame = self.parse()
        self.assertEqual(frame["validAt"], "2026-08-07T12:00:00Z")
        self.assertEqual(frame["altitudeKm"][0], 100.0)
        self.assertEqual(frame["altitudeKm"][-1], 1000.0)
        self.assertEqual(np.asarray(frame["densityKgM3"]).shape, (91, 91, 90))
        # Values stay in SI as published; no rescaling on the way in.
        self.assertLess(frame["densityKgM3"][-1].max(), frame["densityKgM3"][0].max())

    def test_source_pole_fill_is_a_hole_not_a_density(self) -> None:
        frame = self.parse()
        valid = np.asarray(frame["valid"])
        poles = [i for i, v in enumerate(frame["latitudeDeg"]) if abs(abs(v) - 90.0) < 1e-6]
        self.assertEqual(len(poles), 2)
        for index in poles:
            self.assertFalse(valid[:, index, :].any())
        # Everything that is not a pole row must have survived.
        interior = np.delete(valid, poles, axis=1)
        self.assertTrue(interior.all())
        expected = 1.0 - (len(poles) * len(frame["longitudeDeg"]) * len(frame["altitudeKm"])) / valid.size
        self.assertAlmostEqual(frame["validFraction"], expected, places=9)

    def test_rejects_a_frame_missing_the_density_variable(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            self.parse(omit=("den",))

    def test_rejects_a_non_monotonic_altitude_axis(self) -> None:
        scrambled = list(ALTITUDES)
        scrambled[5], scrambled[6] = scrambled[6], scrambled[5]
        with self.assertRaises(ThermosphereFormatError):
            self.parse(altitudes=scrambled)

    def test_rejects_a_vertically_inverted_density_field(self) -> None:
        """A flipped vertical axis is the failure that would look most normal."""
        flipped = synthetic_density()[::-1].copy()
        with self.assertRaises(ThermosphereFormatError):
            self.parse(density=flipped)

    def test_rejects_a_frame_that_is_mostly_holes(self) -> None:
        sparse = synthetic_density()
        sparse[:, :70, :] = 0.0
        with self.assertRaises(ThermosphereFormatError):
            self.parse(density=sparse)

    def test_rejects_densities_outside_a_thermospheric_range(self) -> None:
        wrong_units = synthetic_density() * 1e12  # e.g. someone published g/cm^3
        with self.assertRaises(ThermosphereFormatError):
            self.parse(density=wrong_units)

    def test_rejects_a_frame_with_no_valid_samples(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            self.parse(density=np.zeros((len(ALTITUDES), len(LATITUDES), len(LONGITUDES))))

    def test_a_negative_sentinel_is_a_hole_not_a_density(self) -> None:
        """The WAM products do not share one fill convention.

        `wam_fixed_height` writes 0 into the pole rows; `wam05` writes -99999
        into both `den400` and `ON2`.  netCDF4 masks the latter, but
        `np.asarray` on a masked array hands back the raw buffer with the
        sentinel intact, so the mask has to be resolved rather than assumed.
        """
        density = synthetic_density(fill_poles=False)
        for index, value in enumerate(LATITUDES):
            if abs(abs(value) - 90.0) < 1e-6:
                density[:, index, :] = -99999.0
        frame = self.parse(density=density)
        valid = np.asarray(frame["valid"])
        poles = [i for i, v in enumerate(LATITUDES) if abs(abs(v) - 90.0) < 1e-6]
        for index in poles:
            self.assertFalse(valid[:, index, :].any())
        self.assertGreater(np.asarray(frame["densityKgM3"])[valid].min(), 0.0)

    def test_non_finite_source_cells_become_holes(self) -> None:
        """NOAA's real 2024-05-11 00Z Gannon frame contains 68 of these.

        They are +inf and NaN at 120-130 km between 72S and 82S -- the southern
        auroral oval at the altitude of peak Joule heating, i.e. exactly where
        the storm was most intense, on exactly the frame this layer exists to
        show.  Left unguarded an `inf` renders as the top of the colour scale
        sitting inside the auroral oval, which is entirely plausible-looking and
        completely wrong.
        """
        density = synthetic_density()
        level = ALTITUDES.index(120.0)
        density[level, 5:9, 3:6] = np.inf
        density[level + 1, 5:9, 3:6] = np.nan
        frame = self.parse(density=density)
        valid = np.asarray(frame["valid"])
        self.assertFalse(valid[level, 5:9, 3:6].any())
        self.assertFalse(valid[level + 1, 5:9, 3:6].any())
        self.assertTrue(np.isfinite(np.asarray(frame["levelMeanDensityKgM3"])).all())
        reduced = reduce_thermosphere_frame(frame, longitude_stride=1, latitude_stride=1)
        self.assertLess(reduced["validFraction"], frame["validFraction"] + 1e-12)


class EncodingTests(unittest.TestCase):
    def test_roundtrip_is_within_one_quantum_and_holes_decode_to_nan(self) -> None:
        density = np.array([[4.5e-7, 1.0e-9], [1.0e-12, 9.0e-15]])
        valid = np.array([[True, True], [True, False]])
        for bits in (8, 16):
            encoded = encode_log_density(density, valid, bits=bits)
            decoded = decode_log_density(encoded)
            self.assertTrue(np.isnan(decoded[1, 1]))
            error = np.abs(np.log10(decoded[valid]) - np.log10(density[valid]))
            self.assertLessEqual(error.max(), encoded["quantumDex"] / 2 + 1e-12)

    def test_zero_code_is_reserved_so_a_hole_is_never_the_lowest_density(self) -> None:
        density = np.array([[1e-17]])  # sits exactly on the encoding floor
        encoded = encode_log_density(density, np.array([[True]]), bits=8)
        self.assertEqual(int(np.asarray(encoded["codes"])[0, 0]), 1)
        empty = encode_log_density(density, np.array([[False]]), bits=8)
        self.assertEqual(int(np.asarray(empty["codes"])[0, 0]), 0)

    def test_sixteen_bit_quantum_is_small_enough_to_quote_a_drag_number(self) -> None:
        encoded = encode_log_density(np.array([[1e-12]]), np.array([[True]]), bits=16)
        # 0.03% in density; a quoted drag figure is then limited by the physics.
        self.assertLess(10 ** encoded["quantumDex"] - 1.0, 0.001)
        coarse = encode_log_density(np.array([[1e-12]]), np.array([[True]]), bits=8)
        self.assertGreater(10 ** coarse["quantumDex"] - 1.0, 0.05)

    def test_rejects_values_outside_the_declared_encoding_domain(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            encode_log_density(np.array([[1.0]]), np.array([[True]]), bits=8)

    def test_rejects_an_unsupported_width(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            encode_log_density(np.array([[1e-12]]), np.array([[True]]), bits=12)

    def test_validity_mask_packs_one_bit_per_sample(self) -> None:
        valid = np.array([True, False, True, True, False, False, False, False, True])
        packed = pack_validity_mask(valid)
        self.assertEqual(len(packed), 2)
        self.assertEqual(packed[0], 0b00001101)
        self.assertEqual(packed[1], 0b00000001)


class ReductionTests(FixtureMixin):
    def test_decimation_preserves_source_samples_rather_than_averaging(self) -> None:
        frame = self.parse()
        reduced = reduce_thermosphere_frame(frame, longitude_stride=2, latitude_stride=2)
        self.assertEqual(reduced["grid"]["longitudeDeg"], frame["longitudeDeg"][::2])
        self.assertEqual(reduced["grid"]["latitudeDeg"], frame["latitudeDeg"][::2])
        decoded = decode_log_density(
            {
                "codes": reduced["codes"],
                "bits": reduced["encoding"]["bits"],
                "logFloor": reduced["encoding"]["logFloor"],
                "logCeiling": reduced["encoding"]["logCeiling"],
            }
        )
        source = np.asarray(frame["densityKgM3"])[:, ::2, ::2]
        finite = np.isfinite(decoded)
        ratio = decoded[finite] / source[finite]
        # Half a 16-bit quantum over the encoding domain is 2.0e-4 in density.
        self.assertTrue(np.allclose(ratio, 1.0, rtol=5e-4))

    def test_reduction_does_not_dilate_a_hole_into_a_neighbour(self) -> None:
        frame = self.parse()
        reduced = reduce_thermosphere_frame(frame, longitude_stride=1, latitude_stride=1)
        decoded = decode_log_density(
            {
                "codes": reduced["codes"],
                "bits": reduced["encoding"]["bits"],
                "logFloor": reduced["encoding"]["logFloor"],
                "logCeiling": reduced["encoding"]["logCeiling"],
            }
        )
        self.assertEqual(int(np.isnan(decoded).sum()), int((~np.asarray(frame["valid"])).sum()))

    def test_selected_altitudes_are_the_nearest_published_levels(self) -> None:
        frame = self.parse()
        reduced = reduce_thermosphere_frame(frame, altitudes_km=[105.0, 402.0, 999.0])
        self.assertEqual(reduced["grid"]["altitudeKm"], [100.0, 400.0, 1000.0])

    def test_mask_length_matches_the_reduced_sample_count(self) -> None:
        frame = self.parse()
        reduced = reduce_thermosphere_frame(frame, longitude_stride=2, latitude_stride=2)
        samples = math.prod(len(reduced["grid"][k]) for k in ("altitudeKm", "latitudeDeg", "longitudeDeg"))
        self.assertEqual(len(reduced["validMask"]), math.ceil(samples / 8))

    def test_metadata_labels_the_layer_a_model_of_the_neutral_gas(self) -> None:
        frame = self.parse()
        meta = source_metadata([frame])
        self.assertEqual(meta["status"], "model")
        self.assertIn("neutral", meta["quantity"])
        self.assertEqual(meta["validFrom"], "2026-08-07T12:00:00Z")


class UpstreamAddressingTests(unittest.TestCase):
    def test_builds_the_archive_prefix_and_frame_url(self) -> None:
        cycle = dt.datetime(2024, 5, 11, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(archive_cycle_prefix(cycle), "v1.2/wfs.20240511/00/")
        url = archive_frame_url(cycle, dt.datetime(2024, 5, 11, 0, 10, tzinfo=dt.timezone.utc))
        self.assertTrue(url.endswith("wam_fixed_height.wfs.t00z.wam10.20240511_001000.nc"))
        self.assertIn("v1.2/wfs.20240511/00/", url)
        self.assertIn("list-type=2", archive_listing_url(cycle))

    def test_rejects_a_cycle_that_is_not_on_the_six_hourly_boundary(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            archive_cycle_prefix(dt.datetime(2024, 5, 11, 3, tzinfo=dt.timezone.utc))

    def test_rejects_a_frame_time_off_the_ten_minute_cadence(self) -> None:
        cycle = dt.datetime(2024, 5, 11, 0, tzinfo=dt.timezone.utc)
        with self.assertRaises(ThermosphereFormatError):
            archive_frame_url(cycle, dt.datetime(2024, 5, 11, 0, 5, tzinfo=dt.timezone.utc))

    def test_parses_a_real_archive_key(self) -> None:
        key = "v1.2/wfs.20240510/00/wam_fixed_height.wfs.t00z.wam10.20240509_211000.nc"
        cycle_hour, valid_at = parse_frame_key(key)
        self.assertEqual(cycle_hour, 0)
        self.assertEqual(valid_at, dt.datetime(2024, 5, 9, 21, 10, tzinfo=dt.timezone.utc))

    def test_rejects_a_key_from_a_different_product(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            parse_frame_key("v1.2/wfs.20240510/00/wfs.t00z.ipe10.20240509_211000.nc")


class SpeciesReconstructionTests(unittest.TestCase):
    def test_matches_a_hand_computed_mass_density(self) -> None:
        n_o, n_o2, n_n2 = 1.2e14, 1.8e11, 9.0e12
        expected = (
            MOLAR_MASS_KG["O"] * n_o
            + MOLAR_MASS_KG["O2"] * n_o2
            + MOLAR_MASS_KG["N2"] * n_n2
        ) / AVOGADRO
        got = float(mass_density_from_species(n_o, n_o2, n_n2))
        self.assertAlmostEqual(got / expected, 1.0, places=12)
        # Sanity: this is a ~400 km density.
        self.assertLess(got, 1e-11)
        self.assertGreater(got, 1e-13)

    def test_rejects_mismatched_species_grids(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            mass_density_from_species(np.zeros((2, 2)), np.zeros((2, 3)), np.zeros((2, 2)))


class DragTests(unittest.TestCase):
    def test_drag_is_linear_in_density(self) -> None:
        """The claim the layer exists to make, asserted rather than assumed."""
        one = drag_deceleration_m_s2(1.0e-12, 400.0, 60.0)
        two = drag_deceleration_m_s2(2.0e-12, 400.0, 60.0)
        self.assertAlmostEqual(two / one, 2.0, places=12)

    def test_drag_ratio_is_independent_of_the_ballistic_coefficient(self) -> None:
        """Why the site can quote a storm/quiet ratio without knowing the spacecraft."""
        quiet, storm = 6.2e-12, 1.41e-11
        ratios = {
            bc: drag_deceleration_m_s2(storm, 400.0, bc) / drag_deceleration_m_s2(quiet, 400.0, bc)
            for bc in (5.9, 59.0, 106.0)
        }
        self.assertAlmostEqual(min(ratios.values()), max(ratios.values()), places=12)
        self.assertAlmostEqual(next(iter(ratios.values())), storm / quiet, places=12)

    def test_decay_is_negative_and_grows_with_density(self) -> None:
        slow = decay_rate_km_per_day(1.0e-12, 400.0, 60.0)
        fast = decay_rate_km_per_day(4.0e-12, 400.0, 60.0)
        self.assertLess(slow, 0.0)
        self.assertLess(fast, slow)
        self.assertAlmostEqual(fast / slow, 4.0, places=12)

    def test_decay_at_starlink_insertion_altitude_is_days_not_years(self) -> None:
        """A 210 km parking orbit is genuinely marginal; that is the whole story."""
        rate = decay_rate_km_per_day(1.6e-10, 210.0, 59.0)
        self.assertLess(rate, -5.0)
        self.assertGreater(rate, -40.0)

    def test_decay_at_an_operational_altitude_is_negligible_by_comparison(self) -> None:
        rate = decay_rate_km_per_day(1.5e-13, 550.0, 59.0)
        self.assertGreater(rate, -0.1)

    def test_orbital_speed_is_the_familiar_seven_and_a_half_kilometres_a_second(self) -> None:
        self.assertAlmostEqual(circular_orbital_speed_m_s(400.0) / 1000.0, 7.67, places=1)

    def test_rejects_a_non_physical_ballistic_coefficient(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            drag_deceleration_m_s2(1e-12, 400.0, 0.0)


class ThermodynamicTests(unittest.TestCase):
    def test_scale_height_of_atomic_oxygen_at_thermospheric_temperature(self) -> None:
        height = pressure_scale_height_km(1100.0, MOLAR_MASS_KG["O"], 400.0)
        self.assertGreater(height, 50.0)
        self.assertLess(height, 90.0)

    def test_a_heavier_gas_has_a_smaller_scale_height(self) -> None:
        light = pressure_scale_height_km(1100.0, MOLAR_MASS_KG["O"], 400.0)
        heavy = pressure_scale_height_km(1100.0, MOLAR_MASS_KG["N2"], 400.0)
        self.assertLess(heavy, light)

    def test_the_ionosphere_is_a_trace_constituent_of_the_thermosphere(self) -> None:
        """1e12 electrons in 7e14 neutrals: about one particle in seven hundred."""
        fraction = ionised_fraction(1.0e12, 7.0e14)
        self.assertLess(fraction, 0.01)
        self.assertAlmostEqual(1.0 / fraction, 700.0, places=0)

    def test_rejects_an_empty_neutral_gas(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            ionised_fraction(1e12, 0.0)


@unittest.skipUnless(msis_available(), "pymsis is not installed")
class NrlmsisTests(FixtureMixin):
    """NRLMSIS is optional, and these run entirely offline: indices are explicit."""

    WHEN = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)

    def test_density_falls_monotonically_through_the_thermosphere(self) -> None:
        rows = msis_profile(self.WHEN, 0.0, 0.0, [200, 300, 400, 500, 600], 110.0, 110.0, 4.0)
        densities = [row["massDensityKgM3"] for row in rows]
        self.assertEqual(densities, sorted(densities, reverse=True))

    def test_temperature_becomes_isothermal_at_the_exospheric_value(self) -> None:
        rows = msis_profile(self.WHEN, 0.0, 0.0, [400, 600, 1000], 110.0, 110.0, 4.0)
        temperatures = [row["temperatureK"] for row in rows]
        self.assertGreater(temperatures[0], 700.0)
        self.assertAlmostEqual(temperatures[1], temperatures[2], delta=1.0)

    def test_density_rises_with_solar_activity_and_more_so_higher_up(self) -> None:
        """The solar-cycle lesson, as an assertion about the model's behaviour."""
        ratios = {}
        for altitude in (200.0, 400.0, 600.0):
            low = msis_profile(self.WHEN, 0.0, 0.0, [altitude], 68.0, 68.0, 4.0)[0]
            high = msis_profile(self.WHEN, 0.0, 0.0, [altitude], 250.0, 250.0, 4.0)[0]
            ratios[altitude] = high["massDensityKgM3"] / low["massDensityKgM3"]
        self.assertGreater(ratios[200.0], 1.5)
        self.assertGreater(ratios[400.0], ratios[200.0])
        self.assertGreater(ratios[600.0], ratios[400.0])
        self.assertGreater(ratios[600.0], 20.0)

    def test_geomagnetic_activity_raises_density(self) -> None:
        quiet = msis_profile(self.WHEN, 0.0, 40.0, [400.0], 110.0, 110.0, 4.0, storm_mode=True)[0]
        storm = msis_profile(self.WHEN, 0.0, 40.0, [400.0], 110.0, 110.0, 111.0, storm_mode=True)[0]
        self.assertGreater(storm["massDensityKgM3"], quiet["massDensityKgM3"])

    def test_the_unrestricted_nrlmsise00_version_also_runs(self) -> None:
        """`version="0"` is the licence-safe fallback; it must stay exercised."""
        rows = msis_profile(self.WHEN, 0.0, 0.0, [400.0], 110.0, 110.0, 4.0, version="0")
        self.assertGreater(rows[0]["massDensityKgM3"], 0.0)

    def test_atomic_oxygen_dominates_the_upper_thermosphere_by_number(self) -> None:
        row = msis_profile(self.WHEN, 0.0, 0.0, [400.0], 110.0, 110.0, 4.0)[0]
        self.assertGreater(row["oNumberDensityM3"], 5.0 * row["n2NumberDensityM3"])

    def test_cross_check_against_the_wam_frame_agrees_to_within_an_order_of_magnitude(self) -> None:
        """Two models disagreeing is expected; a factor of ten is a broken pipeline."""
        # The fixture reproduces a solar-maximum WAM frame, so the empirical
        # model is driven with a matching F10.7 rather than a default one.
        frame = self.parse()
        rows = compare_to_msis(frame, 180.0, 180.0, 4.0, altitudes_km=(300.0, 400.0))
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertGreater(row["ratio"], 0.1)
            self.assertLess(row["ratio"], 10.0)
            # In practice the two agree far better than the guard band.
            self.assertLess(abs(math.log10(row["ratio"])), 0.5)

    def test_rejects_an_empty_altitude_list(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            msis_profile(self.WHEN, 0.0, 0.0, [], 110.0, 110.0, 4.0)


class ModelSelectionTests(unittest.TestCase):
    INSIDE = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
    OUTSIDE = dt.datetime(2022, 2, 3, 18, tzinfo=dt.timezone.utc)  # the Starlink storm

    def test_wam_is_the_default_where_it_has_coverage(self) -> None:
        selection = resolve_thermosphere_model(None, self.INSIDE)
        self.assertEqual(selection["model"], "wamNeutral")
        self.assertEqual(selection["model"], DEFAULT_THERMOSPHERE_MODEL)
        self.assertFalse(selection["fallbackApplied"])

    def test_outside_wam_coverage_it_falls_back_and_says_so(self) -> None:
        selection = resolve_thermosphere_model(None, self.OUTSIDE)
        self.assertEqual(selection["model"], "nrlmsis21")
        self.assertTrue(selection["fallbackApplied"])
        self.assertIn("2023-03-21", selection["reason"])

    def test_the_label_always_follows_the_model_actually_used(self) -> None:
        """The property the RBE control has, asserted here rather than assumed.

        A fallback that kept WAM's label would be the worst possible outcome:
        NRLMSIS numbers presented as NOAA operational output.
        """
        for when in (self.INSIDE, self.OUTSIDE):
            for requested in (None, "wamNeutral", "nrlmsis21"):
                selection = resolve_thermosphere_model(requested, when)
                record = THERMOSPHERE_MODELS[selection["model"]]
                self.assertEqual(selection["modelLabel"], record["label"])
                self.assertEqual(selection["modelStatus"], record["status"])
                self.assertEqual(selection["representation"], record["description"])

    def test_an_explicit_nrlmsis_request_is_honoured_inside_wam_coverage(self) -> None:
        selection = resolve_thermosphere_model("nrlmsis21", self.INSIDE)
        self.assertEqual(selection["model"], "nrlmsis21")
        self.assertFalse(selection["fallbackApplied"])
        self.assertEqual(selection["reason"], "Selected by the viewer.")

    def test_nrlmsis_is_never_itself_out_of_coverage(self) -> None:
        """There is no date at which the layer has nothing to draw."""
        for year in (1958, 2003, 2022, 2026, 2035):
            selection = resolve_thermosphere_model(
                "nrlmsis21", dt.datetime(year, 6, 1, tzinfo=dt.timezone.utc)
            )
            self.assertEqual(selection["model"], "nrlmsis21")
            self.assertFalse(selection["fallbackApplied"])

    def test_an_explicit_wam_request_still_falls_back_outside_coverage(self) -> None:
        selection = resolve_thermosphere_model("wamNeutral", self.OUTSIDE)
        self.assertEqual(selection["model"], "nrlmsis21")
        self.assertTrue(selection["fallbackApplied"])
        self.assertEqual(selection["requested"], "wamNeutral")

    def test_a_forecast_endpoint_bounds_wam_above(self) -> None:
        end = dt.datetime(2026, 8, 9, 0, tzinfo=dt.timezone.utc)
        inside = resolve_thermosphere_model(None, self.INSIDE, wam_valid_to=end)
        beyond = resolve_thermosphere_model(
            None, dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc), wam_valid_to=end
        )
        self.assertEqual(inside["model"], "wamNeutral")
        self.assertEqual(beyond["model"], "nrlmsis21")
        self.assertTrue(beyond["fallbackApplied"])

    def test_rejects_an_unknown_model_name(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            resolve_thermosphere_model("jb2008", self.INSIDE)

    def test_every_model_record_carries_a_label_class_and_honest_limitation(self) -> None:
        for key, record in THERMOSPHERE_MODELS.items():
            for field in ("label", "status", "shortName", "description", "strength", "limitation"):
                self.assertTrue(record[field].strip(), f"{key}.{field} is empty")
            self.assertEqual(record["label"], record["label"].upper())

    def test_the_two_models_do_not_share_an_evidence_class(self) -> None:
        """`model` and `empirical` are different rows in the evidence vocabulary."""
        statuses = {record["status"] for record in THERMOSPHERE_MODELS.values()}
        self.assertEqual(statuses, {"model", "empirical"})


class CuratedEventTests(unittest.TestCase):
    def test_every_event_carries_a_resolvable_citation(self) -> None:
        for key, event in CURATED_DENSITY_EVENTS.items():
            citation = event["citation"]
            for field in ("authors", "year", "title", "journal", "doi", "quotedFinding"):
                self.assertTrue(str(citation[field]).strip(), f"{key}.citation.{field} is empty")
            self.assertRegex(citation["doi"], r"^10\.\d{4,}/")
            self.assertIsInstance(citation["year"], int)

    def test_every_event_states_its_observation_baseline_and_instrument(self) -> None:
        for key, event in CURATED_DENSITY_EVENTS.items():
            self.assertTrue(event["observedBy"].strip(), key)
            self.assertTrue(event["observedBaseline"].strip(), key)
            low, high = event["observedRatio"]
            self.assertGreaterEqual(high, low)
            self.assertGreater(low, 1.0, f"{key}: a storm enhancement must exceed 1")

    def test_events_predating_the_wam_archive_declare_no_wam_ratio(self) -> None:
        """Silence about coverage is how a model gets credit for a date it never saw."""
        for key, event in CURATED_DENSITY_EVENTS.items():
            when = dt.datetime.fromisoformat(event["date"]).replace(tzinfo=dt.timezone.utc)
            if when < WAM_ARCHIVE_START:
                self.assertIsNone(event["wamRatio"], f"{key} predates the WAM archive")
            self.assertTrue(event["wamNote"].strip(), key)

    def test_the_general_assessment_citation_is_present(self) -> None:
        self.assertRegex(MODEL_ASSESSMENT_CITATION["doi"], r"^10\.\d{4,}/")
        self.assertIn("MSIS", MODEL_ASSESSMENT_CITATION["quotedFinding"])


@unittest.skipUnless(msis_available(), "pymsis is not installed")
class ModelComparisonTests(unittest.TestCase):
    def test_global_mean_removes_the_diurnal_confound(self) -> None:
        """Two longitudes 12 h apart in local time differ; their global means do not.

        Getting this wrong is what made the first draft of the comparison table
        report a ratio dominated by local time rather than by the storm.
        """
        when = dt.datetime(2024, 5, 11, 2, tzinfo=dt.timezone.utc)
        # At 02:00 UT, 30 deg E is pre-dawn and 210 deg E is late afternoon.
        early = msis_profile(when, 30.0, 0.0, [400.0], 220.0, 190.0, 22.0)[0]["massDensityKgM3"]
        late = msis_profile(when, 210.0, 0.0, [400.0], 220.0, 190.0, 22.0)[0]["massDensityKgM3"]
        self.assertGreater(max(early, late) / min(early, late), 1.5)

        mean_a = global_mean_msis_density(when, 400.0, 220.0, 190.0, [22.0] * 7)
        mean_b = global_mean_msis_density(
            when + dt.timedelta(hours=12), 400.0, 220.0, 190.0, [22.0] * 7
        )
        self.assertAlmostEqual(mean_a / mean_b, 1.0, delta=0.05)

    def test_nrlmsis_under_responds_on_every_curated_event(self) -> None:
        """The teaching object itself, asserted so it cannot silently stop being true."""
        for key in CURATED_DENSITY_EVENTS:
            with self.subTest(event=key):
                result = compare_models_for_event(key)
                observed_low = result["observed"]["ratioLow"]
                msis = result["nrlmsis21"]["ratio"]
                self.assertGreater(msis, 1.0, "MSIS must at least respond to the storm")
                self.assertLess(
                    msis,
                    observed_low,
                    f"{key}: MSIS {msis:.2f}x should fall short of the observed "
                    f"{observed_low:.2f}x",
                )
                self.assertGreater(result["nrlmsis21"]["shortfall"], 1.0)

    def test_wam_beats_nrlmsis_on_the_one_event_both_cover(self) -> None:
        result = compare_models_for_event("gannon-2024")
        self.assertIsNotNone(result["wam"]["ratio"])
        self.assertGreater(result["wam"]["ratio"], result["nrlmsis21"]["ratio"])

    def test_rejects_an_unknown_event(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            compare_models_for_event("carrington-1859")



class SelectPublishTimesTest(unittest.TestCase):
    """The release window, which must never invent a time NOAA did not publish."""

    @staticmethod
    def _series(start, count, minutes=10):
        return [start + dt.timedelta(minutes=minutes * i) for i in range(count)]

    def test_every_selected_time_was_published(self):
        now = dt.datetime(2026, 8, 17, 9, 32, tzinfo=dt.timezone.utc)
        available = self._series(dt.datetime(2026, 8, 17, 3, 10, tzinfo=dt.timezone.utc), 75)
        picked = thermosphere.select_publish_times(available, now)
        self.assertTrue(picked)
        for moment in picked:
            self.assertIn(moment, available)

    def test_thins_to_the_cadence(self):
        now = dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)
        available = self._series(dt.datetime(2026, 8, 17, 6, 0, tzinfo=dt.timezone.utc), 60)
        picked = thermosphere.select_publish_times(available, now, cadence_minutes=60)
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(picked, picked[1:])]
        # Every gap is at least the cadence, except the last, which is allowed to
        # be short because the forecast endpoint is always kept.
        self.assertTrue(all(gap >= 60 for gap in gaps[:-1]), gaps)

    def test_keeps_the_forecast_endpoint(self):
        now = dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)
        available = self._series(dt.datetime(2026, 8, 17, 8, 0, tzinfo=dt.timezone.utc), 40)
        picked = thermosphere.select_publish_times(available, now, cadence_minutes=60)
        self.assertEqual(picked[-1], available[-1],
                         "the last published frame states how far ahead NOAA has committed")

    def test_a_gap_stays_a_gap(self):
        # Half an hour missing from the middle: the selection must not bridge it
        # by shifting a neighbour into the hole.
        now = dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)
        start = dt.datetime(2026, 8, 17, 7, 0, tzinfo=dt.timezone.utc)
        available = [t for t in self._series(start, 40)
                     if not (dt.datetime(2026, 8, 17, 8, 0, tzinfo=dt.timezone.utc)
                             <= t < dt.datetime(2026, 8, 17, 8, 30, tzinfo=dt.timezone.utc))]
        picked = thermosphere.select_publish_times(available, now, cadence_minutes=30)
        for moment in picked:
            self.assertIn(moment, available)

    def test_window_excludes_what_is_out_of_range(self):
        now = dt.datetime(2026, 8, 17, 12, 0, tzinfo=dt.timezone.utc)
        available = self._series(dt.datetime(2026, 8, 17, 0, 0, tzinfo=dt.timezone.utc), 200)
        picked = thermosphere.select_publish_times(
            available, now, hours_back=2, hours_ahead=2, cadence_minutes=30)
        self.assertTrue(all(
            dt.datetime(2026, 8, 17, 10, 0, tzinfo=dt.timezone.utc) <= t
            <= dt.datetime(2026, 8, 17, 14, 0, tzinfo=dt.timezone.utc) for t in picked), picked)

    def test_rejects_a_nonsense_cadence(self):
        with self.assertRaises(thermosphere.ThermosphereFormatError):
            thermosphere.select_publish_times([], dt.datetime.now(dt.timezone.utc),
                                              cadence_minutes=0)


class DiscoverLatestCycleTest(unittest.TestCase):
    """Walking back to a cycle that actually published."""

    def test_walks_back_past_an_empty_cycle(self):
        now = dt.datetime(2026, 8, 17, 7, 0, tzinfo=dt.timezone.utc)
        served = []

        def fetch(url):
            served.append(url)
            if "/06/" in url:
                return b"<ListBucketResult></ListBucketResult>"
            return (
                b"<ListBucketResult><Contents><Key>"
                b"v1.2/wfs.20260817/00/wam_fixed_height.wfs.t00z.wam10.20260817_004000.nc"
                b"</Key></Contents></ListBucketResult>"
            )

        cycle, frames = thermosphere.discover_latest_cycle(now, fetch=fetch)
        self.assertEqual(cycle.hour, 0)
        self.assertEqual(frames, [dt.datetime(2026, 8, 17, 0, 40, tzinfo=dt.timezone.utc)])

    def test_raises_when_nothing_published(self):
        def fetch(_url):
            return b"<ListBucketResult></ListBucketResult>"

        with self.assertRaises(thermosphere.ThermosphereFormatError):
            thermosphere.discover_latest_cycle(
                dt.datetime(2026, 8, 17, 7, 0, tzinfo=dt.timezone.utc), fetch=fetch)

    def test_ignores_other_products_in_the_same_cycle(self):
        def fetch(_url):
            return (
                b"<ListBucketResult>"
                b"<Contents><Key>v1.2/wfs.20260817/06/ipe05.wfs.t06z.20260817_060000.nc</Key></Contents>"
                b"<Contents><Key>v1.2/wfs.20260817/06/wam_fixed_height.wfs.t06z.wam10.20260817_061000.nc</Key></Contents>"
                b"</ListBucketResult>"
            )

        _cycle, frames = thermosphere.discover_latest_cycle(
            dt.datetime(2026, 8, 17, 7, 0, tzinfo=dt.timezone.utc), fetch=fetch)
        self.assertEqual(len(frames), 1, "only neutral-density frames belong to this layer")


class BuildThermosphereBundleTest(unittest.TestCase):
    """The whole path, against bytes, with no network and no netCDF4."""

    def _listing(self, times):
        rows = b"".join(
            f"<Contents><Key>v1.2/wfs.20260817/06/wam_fixed_height.wfs.t06z.wam10."
            f"{t:%Y%m%d_%H%M%S}.nc</Key></Contents>".encode()
            for t in times
        )
        return b"<ListBucketResult>" + rows + b"</ListBucketResult>"

    def _bundle(self, *, fail_at=None, now=None):
        times = [dt.datetime(2026, 8, 17, 6, 0, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(30)]
        listing = self._listing(times)

        def fetch(url):
            if "list-type=2" in url:
                return listing
            if fail_at and fail_at in url:
                raise RuntimeError("archive returned a truncated object")
            return b"frame-bytes"

        def open_dataset(_payload, valid_at):
            return _FakeDataset(valid_at)

        return thermosphere.build_thermosphere_bundle(
            now=now or dt.datetime(2026, 8, 17, 7, 0, tzinfo=dt.timezone.utc),
            altitudes_km=(200.0, 400.0),
            longitude_stride=45,
            latitude_stride=45,
            fetch=fetch,
            open_dataset=open_dataset,
        )

    def test_builds_a_bundle_with_provenance(self):
        bundle = self._bundle()
        self.assertTrue(bundle["frames"])
        self.assertEqual(bundle["skipped"], [])
        self.assertEqual(bundle["model"]["model"], "wamNeutral")
        self.assertFalse(bundle["model"]["fallbackApplied"])
        self.assertEqual(bundle["source"]["status"], "model",
                         "the thermosphere layer is a model field and must say so")
        self.assertLessEqual(bundle["validFrom"], bundle["validTo"])

    def test_one_bad_frame_becomes_a_recorded_gap_not_a_silent_one(self):
        bundle = self._bundle(fail_at="20260817_070000")
        self.assertTrue(bundle["frames"], "the rest of the series still publishes")
        self.assertTrue(bundle["skipped"], "a dropped frame must be recorded")
        self.assertIn("truncated", bundle["skipped"][0]["reason"])

    def test_refuses_to_publish_an_empty_field(self):
        with self.assertRaises(thermosphere.ThermosphereFormatError):
            self._bundle(fail_at="wam_fixed_height")


class _FakeDataset:
    """The smallest thing `parse_wam_fixed_height` will accept."""

    def __init__(self, valid_at):
        import numpy as np

        self._valid_at = valid_at
        levels = np.array([100.0 + 10.0 * i for i in range(91)], dtype=float)
        lat = np.linspace(-90.0, 90.0, 91)
        lon = np.linspace(0.0, 356.0, 90)
        # A plain exponential atmosphere: real enough to survive validation, and
        # monotone so a test can reason about it.
        scale_km = 50.0
        density = np.empty((levels.size, lat.size, lon.size), dtype=float)
        for index, altitude in enumerate(levels):
            density[index, :, :] = 1e-9 * np.exp(-(altitude - 100.0) / scale_km)
        self.variables = {
            "hlevs": _FakeVariable(levels, units="km"),
            "lat": _FakeVariable(lat, units="degrees_north"),
            "lon": _FakeVariable(lon, units="degrees_east"),
            "den": _FakeVariable(density, units="kg m^-3"),
            # The real product carries "days since 1970-01-01"; anything else is
            # read as the epoch, which is how this fake first reported every
            # frame as 1970 and quietly turned the layer into a fallback.
            "time": _FakeVariable(
                np.array([(valid_at - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc))
                          .total_seconds() / 86400.0]),
                units="days since 1970-01-01",
            ),
        }

    def close(self):
        return None


class _FakeVariable:
    def __init__(self, values, units=""):
        self._values = values
        self.units = units
        self.shape = getattr(values, "shape", ())

    def __getitem__(self, item):
        return self._values[item]

    def ncattrs(self):
        return ["units"]

    def getncattr(self, name):
        return getattr(self, name)


class CycleCoversNowTest(unittest.TestCase):
    """Newest is not the same as useful.

    NOAA publishes a cycle's frames as the run produces them, so the most recent
    cycle is routinely the one LEAST able to cover the present. Measured
    2026-08-18 at 21:26Z: the 18Z cycle had published only as far as 20:10Z, and
    taking it left the live layer with three frames that all ended in the past
    and a legend reading "no data at this time".
    """

    @staticmethod
    def _listing(cycle_hour, times):
        rows = b"".join(
            f"<Contents><Key>v1.2/wfs.20260818/{cycle_hour:02d}/wam_fixed_height.wfs."
            f"t{cycle_hour:02d}z.wam10.{t:%Y%m%d_%H%M%S}.nc</Key></Contents>".encode()
            for t in times
        )
        return b"<ListBucketResult>" + rows + b"</ListBucketResult>"

    def _fetch(self, published):
        def fetch(url):
            for hour, times in published.items():
                if f"/{hour:02d}/" in url:
                    return self._listing(hour, times)
            return b"<ListBucketResult></ListBucketResult>"
        return fetch

    def test_skips_a_newer_cycle_that_has_not_reached_now(self):
        now = dt.datetime(2026, 8, 18, 21, 26, tzinfo=dt.timezone.utc)
        published = {
            # The 18Z run is still producing: it stops before now.
            18: [dt.datetime(2026, 8, 18, 15, 10, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(31)],
            # The 12Z run finished and reaches well past now.
            12: [dt.datetime(2026, 8, 18, 9, 10, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(90)],
        }
        cycle, frames = thermosphere.discover_latest_cycle(now, fetch=self._fetch(published))
        self.assertEqual(cycle.hour, 12, "the 18Z cycle cannot cover the present yet")
        self.assertGreaterEqual(frames[-1], now)

    def test_prefers_the_newest_cycle_that_does_reach_now(self):
        now = dt.datetime(2026, 8, 18, 21, 26, tzinfo=dt.timezone.utc)
        published = {
            18: [dt.datetime(2026, 8, 18, 15, 10, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(60)],
            12: [dt.datetime(2026, 8, 18, 9, 10, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(90)],
        }
        cycle, _frames = thermosphere.discover_latest_cycle(now, fetch=self._fetch(published))
        self.assertEqual(cycle.hour, 18, "newest wins once it actually covers now")

    def test_publishes_the_best_it_has_when_nothing_reaches_now(self):
        # A short series ending in the past is still honest: the layer says
        # "no data at this time" and offers the jump. An empty release would say
        # the field does not exist.
        now = dt.datetime(2026, 8, 18, 21, 26, tzinfo=dt.timezone.utc)
        published = {
            18: [dt.datetime(2026, 8, 18, 15, 10, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(10)],
            12: [dt.datetime(2026, 8, 18, 9, 10, tzinfo=dt.timezone.utc)
                 + dt.timedelta(minutes=10 * i) for i in range(10)],
        }
        cycle, frames = thermosphere.discover_latest_cycle(now, fetch=self._fetch(published))
        self.assertTrue(frames, "a past-ending series still publishes")
        self.assertEqual(cycle.hour, 18, "the furthest-forward of the bad options")

if __name__ == "__main__":
    unittest.main()
