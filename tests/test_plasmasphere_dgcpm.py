"""Offline tests for the DGCPM plasmasphere simulation.

Nothing here reaches the network; the Kp drive is synthesised in each test.

The tests are arithmetic identities and published values wherever one exists,
because this module's failure mode is a plausible picture built on a sign
error. Three checks in particular are the ones that would catch that:

* ``test_convection_amplitude_matches_published_values`` reproduces the two
  numbers Pierrard et al. (2008) print for the Maynard & Chen Kp law;
* ``test_corotation_only_flow_is_eastward_at_the_corotation_rate`` shows the
  drift solver reproduces rigid corotation exactly when convection is off;
* ``test_convection_is_sunward`` shows the convection term drives plasma
  earthward at midnight and outward at noon, which is the direction that
  distinguishes the real pattern from its mirror image.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline.plasmasphere_dgcpm import (
    CARPENTER_ANDERSON_SATURATED_INTERCEPT,
    CARPENTER_ANDERSON_SATURATED_SLOPE,
    DENSITY_ENCODING,
    DGCPM_DEFAULTS,
    EARTH_ANGULAR_RATE_RAD_S,
    EARTH_RADIUS_M,
    MAX_PUBLISHED_FRAMES,
    PUBLISHED_L_COUNT,
    PUBLISHED_MLT_COUNT,
    VOLLAND_STERN,
    DgcpmGrid,
    DgcpmState,
    PlasmasphereDgcpmError,
    build_bundle,
    convection_amplitude_v_per_m,
    convection_amplitude_v_per_re2,
    corotation_potential_scale_v,
    dipole_flux_tube_volume_m3_per_wb,
    drift_velocity,
    drive_digest,
    encode_density,
    equatorial_dipole_field_t,
    frame_times,
    initial_content,
    join_kp_series,
    kp_at,
    last_closed_boundary_l,
    parse_estimated_kp,
    parse_three_hour_kp,
    plasmapause_radius_by_mlt,
    plume_metrics,
    publish,
    published_cadence_minutes,
    saturation_density_cm3,
    simulate,
    stagnation_l,
    total_potential_v,
    trough_density_cm3,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def kp_ramp(
    start: dt.datetime,
    hours: float,
    values: list[tuple[float, float]],
) -> list[tuple[dt.datetime, float]]:
    """A drive series from (hours-after-start, Kp) knots, sampled 3-hourly."""
    knots = sorted(values)
    series: list[tuple[dt.datetime, float]] = []
    step = 3.0
    elapsed = 0.0
    while elapsed <= hours + 1e-9:
        kp = np.interp(elapsed, [hour for hour, _ in knots], [value for _, value in knots])
        series.append((start + dt.timedelta(hours=elapsed), float(kp)))
        elapsed += step
    return series


class VollandSternTest(unittest.TestCase):
    def test_convection_amplitude_matches_published_values(self):
        """Pierrard, Khazanov, Cabrera & Lemaire (2008), JGR 113, A08212, sec 2.

        The paper prints A = 0.045/(1 - 0.159 Kp + 0.0093 Kp^2)^3 kV/Re^2 and
        states "the value of A varies from A = 45 V/Re^2 for Kp = 0 to over
        800 V/Re^2 for Kp 6".
        """
        self.assertAlmostEqual(convection_amplitude_v_per_re2(0.0), 45.0, delta=0.1)
        self.assertGreater(convection_amplitude_v_per_re2(6.0), 800.0)
        # And the reference implementation's own constant, in its own units.
        self.assertAlmostEqual(convection_amplitude_v_per_m(0.0), 7.05e-6, places=12)

    def test_amplitude_is_monotone_in_activity(self):
        values = [convection_amplitude_v_per_re2(kp) for kp in np.arange(0.0, 8.01, 0.25)]
        self.assertTrue(all(b > a for a, b in zip(values, values[1:])))

    def test_corotation_scale_is_the_familiar_92_kilovolts(self):
        self.assertAlmostEqual(corotation_potential_scale_v() / 1000.0, 91.8, delta=0.2)

    def test_potential_is_the_sum_of_its_two_printed_terms(self):
        amplitude = convection_amplitude_v_per_m(3.0)
        for l_shell in (2.0, 4.5, 7.25):
            for phi in (0.0, 1.1, math.pi, 4.9):
                expected = (
                    amplitude * EARTH_RADIUS_M * l_shell ** 2 * math.sin(phi)
                    - corotation_potential_scale_v() / l_shell
                )
                self.assertAlmostEqual(
                    float(total_potential_v(l_shell, phi, amplitude)), expected, places=6
                )

    def test_stagnation_point_solves_its_own_definition(self):
        """L_s is exactly where the azimuthal drift vanishes on the dusk meridian."""
        for kp in (0.0, 2.0, 5.0, 7.0):
            amplitude = convection_amplitude_v_per_m(kp)
            radius = stagnation_l(amplitude)
            dusk = np.array([[3.0 * math.pi / 2.0]])
            _, azimuthal = drift_velocity(np.array([[radius]]), dusk, amplitude)
            self.assertAlmostEqual(float(azimuthal[0, 0]), 0.0, delta=1e-12)

    def test_stagnation_point_moves_inward_with_activity(self):
        quiet = stagnation_l(convection_amplitude_v_per_m(1.0))
        storm = stagnation_l(convection_amplitude_v_per_m(6.0))
        self.assertLess(storm, quiet)
        # Quiet-time stagnation is well outside geostationary; a Kp 6 storm
        # brings it inside L 4.5. Both are the textbook numbers.
        self.assertGreater(quiet, 7.5)
        self.assertLess(storm, 4.5)


class DriftTest(unittest.TestCase):
    def test_corotation_only_flow_is_eastward_at_the_corotation_rate(self):
        """With A = 0 the solver must reproduce rigid corotation exactly."""
        l_values = np.array([[2.0], [4.0], [6.5]])
        phi = np.zeros_like(l_values)
        radial, azimuthal = drift_velocity(l_values, phi, 0.0)
        np.testing.assert_allclose(radial, 0.0, atol=1e-12)
        np.testing.assert_allclose(azimuthal, EARTH_ANGULAR_RATE_RAD_S, rtol=1e-9)

    def test_convection_is_sunward(self):
        """Inward at midnight, outward at noon: the return flow, not its mirror.

        phi is measured from midnight and increases eastward, so phi = 0 is
        midnight and phi = pi is noon.
        """
        amplitude = convection_amplitude_v_per_m(5.0)
        l_values = np.array([[6.0]])
        midnight, _ = drift_velocity(l_values, np.array([[0.0]]), amplitude)
        noon, _ = drift_velocity(l_values, np.array([[math.pi]]), amplitude)
        self.assertLess(float(midnight[0, 0]), 0.0)
        self.assertGreater(float(noon[0, 0]), 0.0)
        self.assertAlmostEqual(float(midnight[0, 0]), -float(noon[0, 0]), places=6)

    def test_dipole_field_is_the_surface_value_over_l_cubed(self):
        surface = float(equatorial_dipole_field_t(1.0))
        # 3.1e-5 T at the magnetic equator, the standard dipole strength.
        self.assertAlmostEqual(surface, 3.1e-5, delta=0.1e-5)
        for l_shell in (2.0, 4.0, 6.0):
            self.assertAlmostEqual(
                float(equatorial_dipole_field_t(l_shell)), surface / l_shell ** 3, places=12
            )


class FluxTubeTest(unittest.TestCase):
    def test_volume_grows_faster_than_l_to_the_fourth(self):
        """The L^4 term dominates, with the ionospheric foot factor increasing."""
        volumes = [float(dipole_flux_tube_volume_m3_per_wb(l)) for l in (2.0, 4.0, 8.0)]
        self.assertTrue(all(b > a for a, b in zip(volumes, volumes[1:])))
        self.assertGreater(volumes[1] / volumes[0], 16.0)
        self.assertLess(volumes[1] / volumes[0], 20.0)

    def test_saturation_matches_the_frontend_constants(self):
        """The ceiling here and the empirical layer's profile are one model.

        Reads the two coefficients out of src/inner-magnetosphere.ts rather than
        restating them, so the two halves of the site cannot drift apart
        silently.
        """
        source = (REPOSITORY_ROOT / "src" / "inner-magnetosphere.ts").read_text()
        slope = re.search(r"saturatedSlopePerL:\s*(-?[\d.]+)", source)
        intercept = re.search(r"saturatedIntercept:\s*(-?[\d.]+)", source)
        self.assertIsNotNone(slope)
        self.assertIsNotNone(intercept)
        self.assertEqual(float(slope.group(1)), CARPENTER_ANDERSON_SATURATED_SLOPE)
        self.assertEqual(float(intercept.group(1)), CARPENTER_ANDERSON_SATURATED_INTERCEPT)

    def test_saturation_reproduces_the_papers_order_of_magnitude_at_l_three(self):
        """Carpenter & Anderson select saturated profiles at about 1000 el/cc at L = 3."""
        self.assertGreater(float(saturation_density_cm3(3.0)), 700.0)
        self.assertLess(float(saturation_density_cm3(3.0)), 1400.0)

    def test_trough_is_the_reference_implementations_own_curve(self):
        for l_shell in (3.0, 5.0, 8.0):
            self.assertAlmostEqual(
                float(trough_density_cm3(l_shell)), 0.5 * (10.0 / l_shell) ** 4, places=9
            )
        # At L = 5 that is 8 cm^-3, between Carpenter & Anderson's own quoted
        # night (4.8) and day (11.7) trough values at the same L.
        self.assertAlmostEqual(float(trough_density_cm3(5.0)), 8.0, places=9)


class BoundaryTest(unittest.TestCase):
    def test_last_closed_boundary_bulges_toward_dusk(self):
        grid = DgcpmGrid()
        amplitude = convection_amplitude_v_per_m(1.0)
        boundary = last_closed_boundary_l(grid.l_values, grid.phi_values, amplitude)
        hours = grid.mlt_hours
        dusk = boundary[int(np.argmin(np.abs(hours - 18.0)))]
        midnight = boundary[int(np.argmin(np.abs(hours - 0.0)))]
        dawn = boundary[int(np.argmin(np.abs(hours - 6.0)))]
        self.assertGreater(dusk, midnight)
        self.assertGreater(dusk, dawn)

    def test_boundary_contracts_when_activity_rises(self):
        grid = DgcpmGrid()
        quiet = last_closed_boundary_l(grid.l_values, grid.phi_values, convection_amplitude_v_per_m(1.0))
        storm = last_closed_boundary_l(grid.l_values, grid.phi_values, convection_amplitude_v_per_m(6.0))
        self.assertTrue(np.all(storm <= quiet + 1e-9))
        self.assertLess(float(np.mean(storm)), float(np.mean(quiet)) - 1.0)


class SolverTest(unittest.TestCase):
    def test_upwind_creates_no_new_extremum(self):
        """First-order upwind under its CFL condition is monotone.

        This is the numerical guarantee the whole layer rests on: whatever the
        advection does to the field, it cannot invent a density that was not
        already somewhere on the grid.
        """
        grid = DgcpmGrid(l_count=30, mlt_count=48)
        state = DgcpmState(grid, initial_content(grid, 2.0))
        low = float(np.min(state.content))
        high = float(np.max(state.content))

        # Advection only: no sources, no boundary refresh.
        content = state.content.copy()
        from pipeline.plasmasphere_dgcpm import _time_step_s, _upwind_step

        amplitude = convection_amplitude_v_per_m(2.0)
        radial, azimuthal = drift_velocity(grid.grid_l, grid.grid_phi, amplitude)
        for _ in range(400):
            step = _time_step_s(radial, azimuthal, grid, 1e9)
            content = _upwind_step(content, radial, azimuthal, grid, step)
            self.assertGreaterEqual(float(np.min(content)), low - 1e-6 * high)
            self.assertLessEqual(float(np.max(content)), high * (1.0 + 1e-9))

    def test_content_never_exceeds_the_carpenter_anderson_ceiling(self):
        grid = DgcpmGrid(l_count=30, mlt_count=48)
        start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        series = kp_ramp(start, 72.0, [(0.0, 1.0), (24.0, 6.0), (48.0, 1.0), (72.0, 1.0)])
        state = DgcpmState(grid, initial_content(grid, 1.0))
        state.advance_to(start, start + dt.timedelta(hours=72), series)
        self.assertTrue(np.all(state.content <= grid.saturated_content * (1.0 + 1e-9)))

    def test_losses_are_removals_and_fills_are_additions(self):
        grid = DgcpmGrid(l_count=24, mlt_count=36)
        start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        series = kp_ramp(start, 48.0, [(0.0, 2.0), (48.0, 2.0)])
        state = DgcpmState(grid, initial_content(grid, 2.0))
        state.advance_to(start, start + dt.timedelta(hours=48), series)
        self.assertGreater(state.filled_total, 0.0)
        self.assertGreater(state.lost_total, 0.0)
        self.assertGreater(state.steps, 10)

    def test_with_filling_disabled_the_interior_only_loses_content(self):
        """Nothing but the modelled source can raise a flux tube's content.

        The dayside source is switched off by zeroing its weight, the outer
        boundary refresh is left in place, and the total content strictly inside
        the outermost shell is required not to grow.
        """
        grid = DgcpmGrid(l_count=30, mlt_count=48)
        grid.dayside_weight = np.zeros_like(grid.dayside_weight)
        start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        series = kp_ramp(start, 36.0, [(0.0, 3.0), (36.0, 3.0)])
        state = DgcpmState(grid, initial_content(grid, 3.0))
        before = float(np.sum(state.content[:-1]))
        state.advance_to(start, start + dt.timedelta(hours=36), series)
        after = float(np.sum(state.content[:-1]))
        self.assertLessEqual(after, before)
        self.assertEqual(state.filled_total, 0.0)


class ErosionAndPlumeTest(unittest.TestCase):
    """The acceptance behaviour, as numbers rather than as a screenshot."""

    @classmethod
    def setUpClass(cls):
        cls.start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        # Five quiet days, then a Kp 6 storm, then recovery.
        cls.series = kp_ramp(
            cls.start,
            168.0,
            [(0.0, 1.0), (110.0, 1.0), (120.0, 6.0), (132.0, 3.0), (156.0, 1.0), (168.0, 1.0)],
        )
        cls.grid = DgcpmGrid(l_count=40, mlt_count=72)
        frames_at = [cls.start + dt.timedelta(hours=hour) for hour in range(108, 169, 4)]
        cls.result = simulate(cls.series, frames_at, grid=cls.grid)

    def test_the_plasmasphere_erodes_across_the_storm(self):
        boundaries = [
            [value for value in frame["plasmapauseLByMlt"] if value is not None]
            for frame in self.result["frames"]
        ]
        quiet = float(np.median(boundaries[0]))
        storm = min(float(np.median(row)) for row in boundaries)
        self.assertGreater(quiet, 4.5, "a five-day quiet spin-up should leave a wide plasmasphere")
        self.assertLess(storm, quiet - 1.0, "the Kp 6 storm must visibly erode it")

    def test_a_dusk_side_plume_forms_during_the_storm(self):
        plumes = [frame["plume"] for frame in self.result["frames"]]
        present = [plume for plume in plumes if plume.get("present")]
        self.assertGreaterEqual(len(present), 3, "the plume must survive more than one frame")
        for plume in present:
            self.assertGreaterEqual(plume["peakMltHours"], 12.0)
            self.assertLessEqual(plume["peakMltHours"], 22.0)
            self.assertGreater(plume["extentL"], 0.5)

    def test_the_quiet_field_has_no_plume(self):
        self.assertFalse(self.result["frames"][0]["plume"].get("present"))

    def test_convection_amplitude_tracks_the_drive(self):
        amplitudes = [frame["convectionAmplitudeVPerRe2"] for frame in self.result["frames"]]
        kps = [frame["kp"] for frame in self.result["frames"]]
        self.assertAlmostEqual(max(kps), 6.0, delta=0.3)
        self.assertGreater(max(amplitudes), 800.0)
        self.assertLess(min(amplitudes), 100.0)


class DiagnosticTest(unittest.TestCase):
    def test_plasmapause_contour_is_found_by_interpolation(self):
        l_values = np.array([2.0, 3.0, 4.0, 5.0])
        # One MLT column falling through 50 cm^-3 between L = 3 and L = 4.
        density = np.array([[500.0], [100.0], [25.0], [5.0]])
        found = plasmapause_radius_by_mlt(density, l_values)
        self.assertGreater(found[0], 3.0)
        self.assertLess(found[0], 4.0)
        # log10 interpolation: 2 -> 1.398 across one L, target 1.699.
        expected = 3.0 + (math.log10(100.0) - math.log10(50.0)) / (math.log10(100.0) - math.log10(25.0))
        self.assertAlmostEqual(float(found[0]), expected, places=6)

    def test_plasmapause_is_nan_when_the_contour_is_never_reached(self):
        l_values = np.array([2.0, 3.0, 4.0])
        density = np.array([[5.0], [4.0], [3.0]])
        self.assertTrue(math.isnan(float(plasmapause_radius_by_mlt(density, l_values)[0])))

    def test_plume_metric_needs_a_dusk_protrusion(self):
        hours = np.arange(48) * 0.5
        flat = np.full(48, 4.0)
        self.assertFalse(plume_metrics(flat, hours)["present"])
        bulged = flat.copy()
        bulged[(hours >= 16.0) & (hours <= 18.0)] = 6.0
        result = plume_metrics(bulged, hours)
        self.assertTrue(result["present"])
        self.assertAlmostEqual(result["extentL"], 2.0, places=6)
        self.assertGreaterEqual(result["peakMltHours"], 16.0)


class EncodingTest(unittest.TestCase):
    def test_density_round_trips_through_the_declared_encoding(self):
        values = np.array([[1.0, 10.0, 100.0], [1000.0, 5000.0, 0.05]])
        encoded = encode_density(values)
        raw = np.frombuffer(base64.b64decode(encoded), dtype="<u2").astype(float)
        minimum = float(DENSITY_ENCODING["minimum"])
        maximum = float(DENSITY_ENCODING["maximum"])
        decoded = 10.0 ** (minimum + (raw / 65535.0) * (maximum - minimum))
        decoded = decoded.reshape(values.shape)
        for expected, actual in zip(values.ravel(), decoded.ravel()):
            clamped = min(max(expected, 10.0 ** minimum), 10.0 ** maximum)
            self.assertAlmostEqual(actual / clamped, 1.0, delta=1e-3)

    def test_encoding_is_l_major_with_mlt_fastest(self):
        values = np.array([[1.0, 2.0], [3.0, 4.0]])
        raw = np.frombuffer(base64.b64decode(encode_density(values)), dtype="<u2")
        self.assertEqual(len(raw), 4)
        self.assertLess(raw[0], raw[1])
        self.assertLess(raw[1], raw[2])


class DriveTest(unittest.TestCase):
    def test_three_hour_product_parses_the_header_row_shape(self):
        raw = [
            ["time_tag", "Kp", "a_running", "station_count"],
            ["2026-08-02T00:00:00", 1.0, 4, 8],
            ["2026-08-02T03:00:00", 2.33, 9, 8],
        ]
        parsed = parse_three_hour_kp(raw)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[1][1], 2.33)
        self.assertEqual(parsed[0][0].tzinfo, dt.timezone.utc)

    def test_unreadable_rows_are_skipped_not_guessed(self):
        raw = [
            ["time_tag", "Kp"],
            ["2026-08-02T00:00:00", 1.0],
            ["not a time", 2.0],
            ["2026-08-02T06:00:00", "n/a"],
            ["2026-08-02T09:00:00", 99.0],
        ]
        self.assertEqual(len(parse_three_hour_kp(raw)), 1)

    def test_estimated_product_prefers_the_continuous_column(self):
        raw = [{"time_tag": "2026-08-09T12:00:00", "kp_index": 1, "estimated_kp": 0.67}]
        self.assertEqual(parse_estimated_kp(raw)[0][1], 0.67)

    def test_join_never_overlaps_and_reports_the_boundary(self):
        base = dt.datetime(2026, 8, 9, tzinfo=dt.timezone.utc)
        three = [(base + dt.timedelta(hours=3 * i), 1.0) for i in range(4)]
        estimated = [
            (base + dt.timedelta(hours=8, minutes=m), 3.0) for m in range(0, 120, 5)
        ]
        joined, provenance = join_kp_series(three, estimated, estimated_step_minutes=30)
        times = [at for at, _ in joined]
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(set(times)), len(times))
        self.assertEqual(provenance["definitiveCount"], 4)
        self.assertGreater(provenance["estimatedCount"], 0)
        self.assertTrue(all(at > three[-1][0] for at, _ in joined[4:]))

    def test_join_refuses_without_definitive_samples(self):
        with self.assertRaises(PlasmasphereDgcpmError):
            join_kp_series([], [(dt.datetime.now(dt.timezone.utc), 3.0)])

    def test_kp_interpolates_linearly_and_holds_flat_outside(self):
        base = dt.datetime(2026, 8, 9, tzinfo=dt.timezone.utc)
        series = [(base, 1.0), (base + dt.timedelta(hours=3), 4.0)]
        self.assertEqual(kp_at(series, base - dt.timedelta(hours=5)), 1.0)
        self.assertEqual(kp_at(series, base + dt.timedelta(hours=9)), 4.0)
        self.assertAlmostEqual(kp_at(series, base + dt.timedelta(hours=1)), 2.0, places=9)

    def test_simulate_refuses_a_spin_up_that_is_too_short(self):
        base = dt.datetime(2026, 8, 9, tzinfo=dt.timezone.utc)
        series = [(base, 2.0), (base + dt.timedelta(hours=6), 2.0)]
        with self.assertRaises(PlasmasphereDgcpmError):
            simulate(series, [base + dt.timedelta(hours=6)], grid=DgcpmGrid(l_count=20, mlt_count=24))


class PublishedShapeTest(unittest.TestCase):
    def test_frame_times_sit_on_a_fixed_utc_grid(self):
        end = dt.datetime(2026, 8, 9, 22, 47, 13, tzinfo=dt.timezone.utc)
        times = frame_times(end, 48.0, 120)
        self.assertLessEqual(len(times), MAX_PUBLISHED_FRAMES)
        for at in times:
            self.assertEqual(at.minute, 0)
            self.assertEqual(at.second, 0)
            self.assertEqual(int(at.timestamp()) % (120 * 60), 0)
        # Same window a minute later gives the same grid: the artifact does not
        # churn between five-minute publish cycles.
        self.assertEqual(times, frame_times(end + dt.timedelta(minutes=1), 48.0, 120))

    def test_cadence_ladder_respects_the_frame_budget(self):
        cadence = published_cadence_minutes(48.0)
        self.assertLessEqual((48.0 * 60) / cadence, MAX_PUBLISHED_FRAMES - 1)

    def test_digest_changes_with_the_drive_and_not_with_the_clock(self):
        base = dt.datetime(2026, 8, 9, tzinfo=dt.timezone.utc)
        series = [(base + dt.timedelta(hours=3 * i), 2.0) for i in range(8)]
        times = frame_times(base + dt.timedelta(hours=24), 48.0, 120)
        first = drive_digest(series, times)
        self.assertEqual(first, drive_digest(list(series), list(times)))
        moved = list(series)
        moved[-1] = (moved[-1][0], 4.0)
        self.assertNotEqual(first, drive_digest(moved, times))

    def test_bundle_declares_everything_the_browser_needs(self):
        base = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
        series = kp_ramp(base, 168.0, [(0.0, 2.0), (120.0, 5.0), (168.0, 2.0)])
        provenance = {"joinRule": "test fixture"}
        bundle = build_bundle(
            series,
            provenance,
            now=base + dt.timedelta(hours=168),
            grid=DgcpmGrid(l_count=24, mlt_count=36),
        )
        self.assertEqual(bundle["status"], "physics-simulation")
        self.assertEqual(bundle["grid"]["lCount"], PUBLISHED_L_COUNT)
        self.assertEqual(bundle["grid"]["mltCount"], PUBLISHED_MLT_COUNT)
        self.assertEqual(len(bundle["grid"]["lValues"]), PUBLISHED_L_COUNT)
        self.assertEqual(len(bundle["grid"]["mltHours"]), PUBLISHED_MLT_COUNT)
        self.assertIn("electronDensity", bundle["fieldEncodings"])
        self.assertIn("notModelled", bundle["model"])
        self.assertTrue(any("ring current" in line for line in bundle["model"]["notModelled"]))
        self.assertEqual(bundle["model"]["doi"], DGCPM_DEFAULTS["doi"])
        self.assertEqual(bundle["model"]["electricField"]["doi"], VOLLAND_STERN["doi"])
        for frame in bundle["frames"]:
            decoded = np.frombuffer(base64.b64decode(frame["densityU16"]), dtype="<u2")
            self.assertEqual(len(decoded), PUBLISHED_L_COUNT * PUBLISHED_MLT_COUNT)
            self.assertEqual(len(frame["plasmapauseLByMlt"]), PUBLISHED_MLT_COUNT)
            self.assertEqual(len(frame["steepestGradientLByMlt"]), PUBLISHED_MLT_COUNT)

    def test_publish_returns_a_manifest_fragment_and_caches(self):
        base = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
        three_hour_raw = [["time_tag", "Kp"]] + [
            [(base + dt.timedelta(hours=3 * i)).strftime("%Y-%m-%dT%H:%M:%S"), 2.0]
            for i in range(57)
        ]
        written: list[str] = []

        def fake_write(_root: Path, prefix: str, value: object) -> tuple[str, str]:
            written.append(prefix)
            return f"artifacts/{prefix}-test.json", "0" * 64

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            fragment = publish(
                root, fake_write, three_hour_raw, None,
                now=base + dt.timedelta(hours=168), cache_root=cache,
            )
            self.assertEqual(written, ["plasmasphere-dgcpm"])
            record = fragment["plasmasphere"]
            self.assertEqual(record["path"], "artifacts/plasmasphere-dgcpm-test.json")
            self.assertGreater(record["frameCount"], 1)
            self.assertIn("spinUpHours", record)
            cached = list(cache.glob("dgcpm-*.json"))
            self.assertEqual(len(cached), 1)
            # The second call must reuse the cached bundle, not recompute it.
            payload = json.loads(cached[0].read_text())
            payload["frames"][0]["kp"] = -1.0
            cached[0].write_text(json.dumps(payload))
            again = publish(
                root, fake_write, three_hour_raw, None,
                now=base + dt.timedelta(hours=168), cache_root=cache,
            )
            self.assertEqual(again["plasmasphere"]["frameCount"], record["frameCount"])


if __name__ == "__main__":
    unittest.main()
