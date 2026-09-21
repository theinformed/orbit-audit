"""Tests for the orbit-history archive.

No network access anywhere in here, and `test_module_makes_no_network_calls`
enforces that the module itself cannot grow one.

Run with the same command as the rest of the Python suite:

    python3 -m unittest discover -s tests -p 'test_*.py'
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import math
import os
import random
import sqlite3
import tempfile
import threading
import time
import unittest
import unittest.mock
import zlib
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from pipeline import orbit_campaigns as oc
from pipeline import orbit_history as oh


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def gp_record(norad: int, epoch: str, **overrides) -> dict:
    record = {
        "NORAD_CAT_ID": str(norad),
        "OBJECT_NAME": f"TEST {norad}",
        "OBJECT_ID": "2020-001A",
        "OBJECT_TYPE": "PAYLOAD",
        "RCS_SIZE": "MEDIUM",
        "COUNTRY_CODE": "US",
        "LAUNCH_DATE": "2020-01-01",
        "EPOCH": epoch,
        "MEAN_MOTION": "15.50000000",
        "ECCENTRICITY": "0.00012340",
        "INCLINATION": "53.0500",
        "RA_OF_ASC_NODE": "120.4321",
        "ARG_OF_PERICENTER": "90.1234",
        "MEAN_ANOMALY": "270.9876",
        "BSTAR": "0.00012345000000",
        "MEAN_MOTION_DOT": "0.00000247",
        "MEAN_MOTION_DDOT": "0.0000000000000",
        "REV_AT_EPOCH": "12345",
    }
    for key, value in overrides.items():
        record[key] = value if value is None else str(value)
    return record


def synthetic_series(
    norad: int,
    *,
    count: int,
    start: dt.datetime,
    step_hours: float,
    mean_motion0: float,
    decay_per_day: float = 0.0,
    noise: float = 0.0,
    seed: int = 1,
    step_at: int | None = None,
    step_mean_motion: float = 0.0,
) -> list[dict]:
    """A believable element-set series with a controllable truth.

    `noise` is a Gaussian 1-sigma on mean motion, drawn from a seeded
    generator so the tests are deterministic. A repeating pattern will not do:
    a cyclic 'noise' sequence has a degenerate median absolute deviation, and
    a detector calibrated on it would look far better than it is.
    """
    rng = random.Random(seed)
    out = []
    for index in range(count):
        days = step_hours * index / 24.0
        epoch = start + dt.timedelta(days=days)
        value = mean_motion0 + decay_per_day * days
        if noise:
            value += rng.gauss(0.0, noise)
        if step_at is not None and index >= step_at:
            value += step_mean_motion
        out.append(
            gp_record(
                norad,
                epoch.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                MEAN_MOTION=f"{value:.8f}",
                RA_OF_ASC_NODE=f"{(120.0 + 5.0 * days) % 360.0:.4f}",
                ARG_OF_PERICENTER=f"{(90.0 + 3.9 * days) % 360.0:.4f}",
            )
        )
    return out


ALL_COLUMNS = f"norad, {', '.join(oh._ELEMENT_COLUMNS)}, ingest_hour"


class ArchiveTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.tmp = Path(self._directory.name)
        self.archive = oh.open_archive(self.tmp / "orbit-history.sqlite3")
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.archive.close)

    def rows(self) -> list[tuple]:
        return list(
            self.archive.execute(
                f"SELECT {ALL_COLUMNS} FROM element_set ORDER BY norad, epoch_ms"
            )
        )


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
class QuantisationTests(unittest.TestCase):
    def test_quantisation_is_exact_for_published_precision(self) -> None:
        self.assertEqual(oh.quantise("15.50000000", oh.SCALE_MEAN_MOTION), 1_550_000_000)
        self.assertEqual(oh.quantise("0.18360709", oh.SCALE_ECCENTRICITY), 18_360_709)
        self.assertEqual(oh.quantise("34.2423", oh.SCALE_ANGLE), 342_423)
        self.assertEqual(oh.quantise("0.00033236870000", oh.SCALE_BSTAR), 332_368_700)
        self.assertEqual(oh.quantise("-3.5366", oh.SCALE_BSTAR), -3_536_600_000_000)

    def test_a_missing_value_stays_missing_rather_than_becoming_zero(self) -> None:
        self.assertIsNone(oh.quantise(None, oh.SCALE_BSTAR))
        self.assertIsNone(oh.quantise("", oh.SCALE_BSTAR))

    def test_epoch_is_treated_as_utc_not_local_time(self) -> None:
        self.assertEqual(
            oh.parse_epoch_ms("2026-08-07T00:00:00.000000"),
            int(dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc).timestamp() * 1000),
        )


class RoundTripTests(ArchiveTestCase):
    def test_every_element_survives_the_archive(self) -> None:
        oh.ingest_records(self.archive, [gp_record(25544, "2026-08-07T01:17:34.339488")])
        (element,) = oh.series(self.archive, 25544)
        self.assertAlmostEqual(element.mean_motion, 15.5, places=9)
        self.assertAlmostEqual(element.eccentricity, 0.0001234, places=10)
        self.assertAlmostEqual(element.inclination, 53.05, places=6)
        self.assertAlmostEqual(element.bstar, 0.00012345, places=14)
        self.assertEqual(element.rev_at_epoch, 12345)
        self.assertEqual(
            element.epoch,
            dt.datetime(2026, 8, 7, 1, 17, 34, 339000, tzinfo=dt.timezone.utc),
        )

    def test_malformed_records_are_rejected_not_stored(self) -> None:
        bad = [
            {"NORAD_CAT_ID": "1"},
            gp_record(2, "2026-08-07T00:00:00", MEAN_MOTION="0"),
            gp_record(3, "2026-08-07T00:00:00", ECCENTRICITY="1.5"),
            gp_record(4, "2026-08-07T00:00:00", INCLINATION="200"),
            gp_record(5, "not-a-date"),
        ]
        result = oh.ingest_records(self.archive, bad)
        self.assertEqual(result.rejected, 5)
        self.assertEqual(result.elements_new, 0)

    def test_absurd_drag_terms_are_rejected_before_they_reach_sqlite(self) -> None:
        # B* is an inverse-Earth-radii drag coefficient; 1e12 is not a value
        # the atmosphere can produce, and quantised at 1e12 it also exceeds the
        # signed 64-bit range SQLite stores integers in. Left unguarded it
        # raises OverflowError inside the insert and takes the whole batch with
        # it - which is exactly how one bad record stopped the bulk backfill.
        bad = [
            gp_record(11, "2026-08-07T00:00:00", BSTAR="1e12"),
            gp_record(12, "2026-08-07T00:00:00", MEAN_MOTION_DOT="9e9"),
            gp_record(13, "2026-08-07T00:00:00", MEAN_MOTION_DDOT="-4e8"),
        ]
        result = oh.ingest_records(self.archive, bad)
        self.assertEqual(result.rejected, 3)
        self.assertEqual(result.elements_new, 0)

    def test_a_real_decaying_bstar_is_still_accepted(self) -> None:
        # The ceiling has to sit above anything real. A satellite in its final
        # days carries a B* of order 1e-2, and the guard must not touch it.
        oh.ingest_records(
            self.archive, [gp_record(14, "2026-08-07T00:00:00", BSTAR="0.05")]
        )
        (element,) = oh.series(self.archive, 14)
        self.assertAlmostEqual(element.bstar, 0.05, 10)

    def test_optional_fields_survive_as_null_not_zero(self) -> None:
        record = gp_record(9, "2026-08-07T00:00:00", BSTAR="", MEAN_MOTION_DDOT=None)
        oh.ingest_records(self.archive, [record])
        (element,) = oh.series(self.archive, 9)
        self.assertIsNone(element.bstar)
        self.assertIsNone(element.nddot)


# ---------------------------------------------------------------------------
# Capture semantics
# ---------------------------------------------------------------------------
class CaptureTests(ArchiveTestCase):
    def test_capture_is_idempotent(self) -> None:
        records = [gp_record(100 + i, "2026-08-07T00:00:00") for i in range(20)]
        first = oh.ingest_records(self.archive, records)
        second = oh.ingest_records(self.archive, records)
        self.assertEqual(first.elements_new, 20)
        self.assertEqual(second.elements_new, 0)
        self.assertEqual(second.duplicates, 20)
        self.assertEqual(len(self.rows()), 20)

    def test_a_new_epoch_appends_rather_than_replacing(self) -> None:
        oh.ingest_records(self.archive, [gp_record(7, "2026-08-07T00:00:00")])
        oh.ingest_records(self.archive, [gp_record(7, "2026-08-07T06:00:00")])
        self.assertEqual(len(oh.series(self.archive, 7)), 2)

    def test_object_metadata_is_updated_in_place(self) -> None:
        oh.ingest_records(self.archive, [gp_record(8, "2026-08-07T00:00:00")])
        oh.ingest_records(
            self.archive,
            [gp_record(8, "2026-08-07T06:00:00", OBJECT_NAME="RENAMED")],
        )
        name = self.archive.execute("SELECT name FROM object WHERE norad=8").fetchone()
        count = self.archive.execute("SELECT COUNT(*) FROM object").fetchone()
        self.assertEqual(name[0], "RENAMED")
        self.assertEqual(count[0], 1)

    def test_the_ledger_records_every_run_including_the_ones_that_added_nothing(self):
        oh.ingest_records(
            self.archive, [gp_record(1, "2026-08-07T00:00:00")], captured_ms=1000
        )
        oh.ingest_records(
            self.archive, [gp_record(1, "2026-08-07T00:00:00")], captured_ms=2000
        )
        rows = self.archive.execute(
            "SELECT captured_ms, elements_new FROM capture ORDER BY captured_ms"
        ).fetchall()
        self.assertEqual(rows, [(1000, 1), (2000, 0)])

    def test_capture_from_mirror_reads_a_file_and_records_its_mtime(self) -> None:
        mirror = self.tmp / "gp-active.json"
        mirror.write_text(json.dumps([gp_record(11, "2026-08-07T00:00:00")]))
        result = oh.capture_from_mirror(self.archive, mirror)
        self.assertEqual(result.elements_new, 1)
        source, mtime = self.archive.execute(
            "SELECT source, source_mtime_ms FROM capture"
        ).fetchone()
        self.assertEqual(source, "spacetrack:gp-active.json")
        self.assertIsNotNone(mtime)

    def test_capture_refuses_a_missing_or_empty_mirror(self) -> None:
        with self.assertRaises(oh.ArchiveError):
            oh.capture_from_mirror(self.archive, self.tmp / "absent.json")
        empty = self.tmp / "empty.json"
        empty.write_text("[]")
        with self.assertRaises(oh.ArchiveError):
            oh.capture_from_mirror(self.archive, empty)


class SchemaTests(unittest.TestCase):
    def test_schema_version_mismatch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.sqlite3"
            oh.open_archive(path).close()
            connection = sqlite3.connect(path)
            connection.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
            connection.commit()
            connection.close()
            with self.assertRaises(oh.ArchiveError):
                oh.open_archive(path)


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
class PhysicsTests(unittest.TestCase):
    def test_semi_major_axis_matches_the_value_space_track_publishes(self) -> None:
        # VANGUARD 1 in the live mirror: SEMIMAJOR_AXIS 8613.401 km at
        # MEAN_MOTION 10.86027427. We must land on space-track's own number.
        self.assertAlmostEqual(oh.semi_major_axis_km(10.86027427), 8613.401, delta=0.02)

    def test_j2_nodal_regression_matches_the_sun_synchronous_rate(self) -> None:
        # A 7078 km, 98.2 deg orbit is sun-synchronous: +0.9856 deg/day.
        mean_motion = 86400.0 / (2 * math.pi * math.sqrt(7078.0**3 / oh.MU_WGS72))
        element = oh.ElementSet(
            norad=1, epoch_ms=0, mean_motion=mean_motion, eccentricity=0.001,
            inclination=98.2, raan=0.0, arg_perigee=0.0, mean_anomaly=0.0,
            bstar=None, ndot=None, nddot=None, rev_at_epoch=None,
        )
        raan_dot, _ = oh.j2_secular_rates(element)
        self.assertAlmostEqual(raan_dot, 0.9856, delta=0.02)

    def test_delta_v_estimate_has_the_right_sign_and_order_of_magnitude(self) -> None:
        # Raising a 500 km circular orbit by 1 km needs about 55 cm/s:
        # dv = mu * da / (2 a^2 v), with v = sqrt(mu/a) = 7.613 km/s.
        rate = oh.Rate(
            start_ms=0, end_ms=86_400_000, span_days=1.0, da_km_per_day=1.0,
            de_per_day=0.0, di_deg_per_day=0.0, draan_resid_deg_per_day=0.0,
            dargp_resid_deg_per_day=0.0, a_start_km=6878.0, perigee_altitude_km=500.0,
        )
        self.assertAlmostEqual(oh._delta_v_from_da(rate), 0.553, delta=0.02)


class J2Tests(ArchiveTestCase):
    def test_pure_j2_precession_is_removed_and_never_looks_like_a_manoeuvre(self):
        reference = oh.ElementSet(
            norad=42, epoch_ms=0, mean_motion=14.0, eccentricity=0.001,
            inclination=98.2, raan=0.0, arg_perigee=0.0, mean_anomaly=0.0,
            bstar=None, ndot=None, nddot=None, rev_at_epoch=None,
        )
        raan_dot, argp_dot = oh.j2_secular_rates(reference)
        start = dt.datetime(2026, 1, 1)
        records = []
        for index in range(40):
            days = index * 0.25
            records.append(
                gp_record(
                    42,
                    (start + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    MEAN_MOTION="14.00000000",
                    ECCENTRICITY="0.00100000",
                    INCLINATION="98.2000",
                    RA_OF_ASC_NODE=f"{(raan_dot * days) % 360.0:.4f}",
                    ARG_OF_PERICENTER=f"{(argp_dot * days) % 360.0:.4f}",
                )
            )
        oh.ingest_records(self.archive, records)
        elements = oh.series(self.archive, 42)
        rate_list = oh.rates(elements)
        self.assertEqual(len(rate_list), 39)
        for rate in rate_list:
            # RAAN and argp wrap through 360 degrees repeatedly over ten days;
            # the residual after removing J2 must stay at the rounding floor.
            self.assertLess(abs(rate.draan_resid_deg_per_day), 0.01)
            self.assertLess(abs(rate.dargp_resid_deg_per_day), 0.01)
        self.assertEqual(oh.detect_manoeuvres(elements), [])

    def test_rates_skip_pairs_separated_by_a_long_tracking_gap(self) -> None:
        oh.ingest_records(
            self.archive,
            [
                gp_record(50, "2026-01-01T00:00:00"),
                gp_record(50, "2026-01-20T00:00:00"),
                gp_record(50, "2026-01-20T12:00:00"),
            ],
        )
        rate_list = oh.rates(oh.series(self.archive, 50))
        self.assertEqual(len(rate_list), 1)
        self.assertAlmostEqual(rate_list[0].span_days, 0.5, places=6)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
class ManoeuvreTests(ArchiveTestCase):
    def test_a_clean_step_in_mean_motion_is_flagged(self) -> None:
        records = synthetic_series(
            60, count=40, start=dt.datetime(2026, 1, 1), step_hours=6,
            mean_motion0=15.5, noise=1e-7,
            step_at=20, step_mean_motion=-2e-4,
        )
        oh.ingest_records(self.archive, records)
        events = oh.detect_manoeuvres(oh.series(self.archive, 60))
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.kind, "manoeuvre-candidate")
        self.assertEqual(event.confidence, "candidate")
        # Lowering mean motion raises the orbit.
        self.assertGreater(event.evidence["elements"]["semiMajorAxis"]["deltaMetres"], 0)
        self.assertGreater(event.evidence["deltaVEstimateMetresPerSecond"], 0)
        self.assertFalse(event.evidence["cohortScreened"])

    def test_pure_noise_produces_no_manoeuvres(self) -> None:
        records = synthetic_series(
            61, count=60, start=dt.datetime(2026, 1, 1), step_hours=6,
            mean_motion0=15.5,
            noise=1e-7,
        )
        oh.ingest_records(self.archive, records)
        self.assertEqual(oh.detect_manoeuvres(oh.series(self.archive, 61)), [])

    def test_smooth_drag_decay_is_not_flagged_as_a_manoeuvre(self) -> None:
        # A step, not a trend, is the signature. Otherwise every decaying LEO
        # object would be reported as burning continuously.
        records = synthetic_series(
            62, count=60, start=dt.datetime(2026, 1, 1), step_hours=6,
            mean_motion0=15.9, decay_per_day=2e-5, noise=1e-7,
        )
        oh.ingest_records(self.archive, records)
        self.assertEqual(oh.detect_manoeuvres(oh.series(self.archive, 62)), [])

    def test_leave_one_out_stops_a_large_step_from_hiding_itself(self) -> None:
        # With the candidate included in its own scatter estimate, one very
        # large step inflates the threshold enough to mask itself.
        records = synthetic_series(
            68, count=30, start=dt.datetime(2026, 1, 1), step_hours=6,
            mean_motion0=15.5, noise=1e-7,
            step_at=15, step_mean_motion=-5e-3,
        )
        oh.ingest_records(self.archive, records)
        self.assertEqual(len(oh.detect_manoeuvres(oh.series(self.archive, 68))), 1)

    def test_secular_inclination_drift_is_not_a_burn(self) -> None:
        """An abandoned GEO satellite's inclination walks about 0.85 deg/year
        under luni-solar perturbation with nobody touching it. Testing the
        inclination rate against zero instead of against its own median rate
        reports that drift as a manoeuvre on *every* interval - which is how a
        detector ends up claiming a dead satellite burns daily."""
        start = dt.datetime(2026, 1, 1)
        rng = random.Random(11)
        records = []
        for index in range(60):
            days = index * 1.0
            inclination = 0.0500 + 0.85 * days / 365.25
            records.append(
                gp_record(
                    69,
                    (start + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    MEAN_MOTION=f"{1.00270000 + rng.gauss(0.0, 3e-7):.8f}",
                    INCLINATION=f"{inclination:.4f}",
                )
            )
        oh.ingest_records(self.archive, records)
        elements = oh.series(self.archive, 69)
        # The drift is real and large: about 0.14 degrees over the window.
        self.assertGreater(elements[-1].inclination - elements[0].inclination, 0.1)
        self.assertEqual(oh.detect_manoeuvres(elements), [])
        self.assertEqual(oh.detect_station_keeping(elements), [])

    def test_a_step_on_top_of_a_secular_drift_is_still_found(self) -> None:
        """Centring on the median must not blind the detector to a real plane
        change laid over the drift."""
        start = dt.datetime(2026, 1, 1)
        rng = random.Random(12)
        records = []
        for index in range(60):
            days = index * 1.0
            inclination = 0.0500 + 0.85 * days / 365.25 + (0.05 if index >= 30 else 0.0)
            records.append(
                gp_record(
                    71,
                    (start + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    MEAN_MOTION=f"{1.00270000 + rng.gauss(0.0, 3e-7):.8f}",
                    INCLINATION=f"{inclination:.4f}",
                )
            )
        oh.ingest_records(self.archive, records)
        events = oh.detect_manoeuvres(oh.series(self.archive, 71))
        self.assertEqual(len(events), 1)
        self.assertIn("inclination", events[0].evidence["elements"])

    def test_a_short_series_yields_no_events_rather_than_a_guess(self) -> None:
        records = synthetic_series(
            67, count=5, start=dt.datetime(2026, 1, 1), step_hours=6, mean_motion0=15.5
        )
        oh.ingest_records(self.archive, records)
        elements = oh.series(self.archive, 67)
        self.assertEqual(oh.detect_manoeuvres(elements), [])
        self.assertEqual(oh.detect_drag(elements), [])
        self.assertFalse(oh.noise_floor(oh.rates(elements))["sufficient"])


class DragTests(ArchiveTestCase):
    def test_a_decaying_orbit_is_found_and_reported_as_accelerating(self) -> None:
        start = dt.datetime(2026, 1, 1)
        records = []
        for index in range(60):
            days = index * 0.25
            # Quadratic decay: mean motion rises, faster as it goes.
            value = 15.9 + 1e-5 * days + 2e-6 * days * days
            records.append(
                gp_record(
                    63,
                    (start + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    MEAN_MOTION=f"{value:.8f}",
                )
            )
        oh.ingest_records(self.archive, records)
        events = oh.detect_drag(oh.series(self.archive, 63))
        self.assertEqual(len(events), 1)
        evidence = events[0].evidence
        self.assertLess(evidence["medianDecayMetresPerDay"], 0)
        self.assertTrue(evidence["accelerating"])
        self.assertEqual(events[0].confidence, "candidate")

    def test_the_drag_detector_stays_silent_on_a_stable_orbit(self) -> None:
        records = synthetic_series(
            64, count=60, start=dt.datetime(2026, 1, 1), step_hours=6,
            mean_motion0=1.0027, noise=1e-8,
        )
        oh.ingest_records(self.archive, records)
        self.assertEqual(oh.detect_drag(oh.series(self.archive, 64)), [])


class StationKeepingTests(ArchiveTestCase):
    def _geo_series(self, norad: int, burn_indices) -> list[dict]:
        """A GEO satellite holding its slot.

        Each east-west correction is 1e-4 rev/day, which moves the semi-major
        axis by about 2.8 km - roughly 10 cm/s, a realistic slot correction
        and two hundred times the 12 m element-to-element scatter measured at
        GEO. A correction smaller than that scatter is genuinely invisible in
        GP elements, and the detector is right to stay quiet about it.
        """
        rng = random.Random(norad)
        start = dt.datetime(2026, 1, 1)
        mean_motion = 1.00270000
        records = []
        for index in range(120):
            if index in burn_indices:
                mean_motion += 1e-4
            records.append(
                gp_record(
                    norad,
                    (start + dt.timedelta(days=index * 0.5)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"
                    ),
                    MEAN_MOTION=f"{mean_motion + rng.gauss(0.0, 3e-7):.8f}",
                    INCLINATION="0.0500",
                )
            )
        return records

    def test_regular_corrections_are_recognised_as_station_keeping(self) -> None:
        oh.ingest_records(self.archive, self._geo_series(65, range(20, 120, 20)))
        events = oh.detect_station_keeping(oh.series(self.archive, 65))
        self.assertEqual(len(events), 1)
        evidence = events[0].evidence
        self.assertGreaterEqual(evidence["correctionCount"], 4)
        self.assertAlmostEqual(evidence["meanIntervalDays"], 10.0, delta=1.0)
        self.assertLess(evidence["intervalCoefficientOfVariation"], 0.6)

    def test_a_correction_below_the_measured_noise_floor_is_not_reported(self) -> None:
        """Silence is the honest answer when the evidence is not there.

        A 3e-6 rev/day nudge moves a GEO semi-major axis by 84 m, which sits
        inside the 12.4 m element-to-element scatter times the kappa the
        detector requires. Reporting it would be inventing a fact.
        """
        start = dt.datetime(2026, 1, 1)
        rng = random.Random(7)
        mean_motion = 1.00270000
        records = []
        for index in range(120):
            if index and index % 20 == 0:
                mean_motion += 3e-6
            records.append(
                gp_record(
                    70,
                    (start + dt.timedelta(days=index * 0.5)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"
                    ),
                    MEAN_MOTION=f"{mean_motion + rng.gauss(0.0, 3e-7):.8f}",
                    INCLINATION="0.0500",
                )
            )
        oh.ingest_records(self.archive, records)
        self.assertEqual(oh.detect_station_keeping(oh.series(self.archive, 70)), [])

    def test_irregular_manoeuvres_are_not_called_station_keeping(self) -> None:
        oh.ingest_records(self.archive, self._geo_series(66, {5, 9, 40, 100, 101}))
        self.assertEqual(oh.detect_station_keeping(oh.series(self.archive, 66)), [])


class NoiseFloorTests(unittest.TestCase):
    def test_the_floor_is_the_measured_catalogue_scatter_not_a_guess(self) -> None:
        sigma_a_leo = oh.noise_floor_for(450.0)[0]
        sigma_a_high_leo = oh.noise_floor_for(1000.0)[0]
        sigma_a_geo = oh.noise_floor_for(35786.0)[0]
        # Measured 2026-08-07: 1.67 m below 500 km, 0.10 m at 800-1500 km,
        # 12.44 m at GEO. Low LEO is noisier than high LEO because real drag
        # curvature contaminates the estimator; GEO is noisiest of all.
        self.assertAlmostEqual(sigma_a_leo * 1000.0, 1.67, places=2)
        self.assertAlmostEqual(sigma_a_high_leo * 1000.0, 0.10, places=2)
        self.assertAlmostEqual(sigma_a_geo * 1000.0, 12.44, places=2)
        self.assertGreater(sigma_a_geo, sigma_a_leo)
        self.assertGreater(sigma_a_leo, sigma_a_high_leo)

    def test_the_500_to_800_km_band_has_its_own_measured_value(self) -> None:
        """The densest part of the catalogue sits here - Starlink at
        540-560 km - so this is the band a wrong boundary would hurt most."""
        self.assertAlmostEqual(oh.noise_floor_for(550.0)[0] * 1000.0, 0.51, places=2)
        self.assertAlmostEqual(oh.noise_floor_for(800.0)[0] * 1000.0, 0.51, places=2)
        self.assertAlmostEqual(oh.noise_floor_for(800.1)[0] * 1000.0, 0.10, places=2)
        self.assertAlmostEqual(oh.noise_floor_for(500.0)[0] * 1000.0, 1.67, places=2)
        self.assertAlmostEqual(oh.noise_floor_for(500.1)[0] * 1000.0, 0.51, places=2)

    def test_an_unusable_altitude_gets_the_widest_floor_not_an_exception(self):
        self.assertEqual(
            oh.noise_floor_for(float("nan")), oh.CATALOGUE_NOISE_FLOOR[-1][1:]
        )

    def test_every_altitude_including_the_absurd_gets_a_floor(self) -> None:
        for altitude in (0.0, 499.9, 500.0, 800.0, 1500.0, 30000.0, 1e9):
            sigma_a, sigma_e, sigma_i = oh.noise_floor_for(altitude)
            self.assertGreater(sigma_a, 0)
            self.assertGreater(sigma_e, 0)
            self.assertGreater(sigma_i, 0)


class FalsePositiveTests(ArchiveTestCase):
    def test_passive_objects_are_the_control_population(self) -> None:
        for norad, object_type in ((200, "DEBRIS"), (201, "PAYLOAD")):
            records = synthetic_series(
                norad, count=40, start=dt.datetime(2026, 1, 1), step_hours=6,
                mean_motion0=15.5, noise=1e-7,
                seed=norad, step_at=20, step_mean_motion=-2e-4,
            )
            for record in records:
                record["OBJECT_TYPE"] = object_type
            oh.ingest_records(self.archive, records)
        report = oh.false_positive_rate(self.archive)
        # Only the debris object counts towards the control, and its single
        # step is by construction a false positive.
        self.assertEqual(report["controlObjects"], 1)
        self.assertEqual(report["falsePositives"], 1)
        self.assertAlmostEqual(
            report["falsePositiveRatePerInterval"], 1 / 39, delta=0.005
        )


# ---------------------------------------------------------------------------
# Population / storm tie-in
# ---------------------------------------------------------------------------
class PopulationTests(ArchiveTestCase):
    def test_decay_is_binned_on_perigee_and_excludes_manoeuvring_payloads(self) -> None:
        start = dt.datetime(2026, 1, 1)
        for index in range(40):
            records = synthetic_series(
                300 + index, count=6, start=start, step_hours=6,
                mean_motion0=15.5, decay_per_day=2e-5, noise=5e-8, seed=index,
            )
            for record in records:
                record["OBJECT_TYPE"] = "DEBRIS"
            oh.ingest_records(self.archive, records)
        # An orbit raise that must not pollute the density estimate.
        oh.ingest_records(
            self.archive,
            synthetic_series(
                999, count=6, start=start, step_hours=6,
                mean_motion0=15.5, decay_per_day=-5e-4,
            ),
        )
        shells = oh.population_decay(
            self.archive,
            start_ms=oh.parse_epoch_ms("2026-01-01T00:00:00"),
            end_ms=oh.parse_epoch_ms("2026-01-05T00:00:00"),
        )
        self.assertTrue(shells)
        for shell in shells:
            self.assertLess(shell["medianDecayMetresPerDay"], 0)
            self.assertGreaterEqual(shell["objects"], 20)


    def test_objects_are_counted_as_objects_not_as_intervals(self) -> None:
        """One object with forty element sets is one tracer of the density,
        not forty, and the minimum-population gate must agree."""
        start = dt.datetime(2026, 1, 1)
        for index in range(5):
            records = synthetic_series(
                350 + index, count=30, start=start, step_hours=6,
                mean_motion0=15.5, decay_per_day=2e-5, noise=5e-8, seed=index,
            )
            for record in records:
                record["OBJECT_TYPE"] = "DEBRIS"
            oh.ingest_records(self.archive, records)
        window = dict(
            start_ms=oh.parse_epoch_ms("2026-01-01T00:00:00"),
            end_ms=oh.parse_epoch_ms("2026-01-20T00:00:00"),
        )
        # 5 objects x 29 intervals = 145 rate samples; the gate is on objects.
        self.assertEqual(oh.population_decay(self.archive, **window), [])
        shells = oh.population_decay(self.archive, min_objects=5, **window)
        self.assertEqual(len(shells), 1)
        self.assertEqual(shells[0]["objects"], 5)
        self.assertEqual(shells[0]["intervals"], 145)


class DensityEnhancementTests(ArchiveTestCase):
    """The storm measurement, checked against a published excursion.

    KANOPUS-V 3's decay went from about 38 m/day to about 180 m/day at ~475 km
    during the May 2024 Gannon storm - a factor of 4.7, which because decay is
    linear in neutral density *is* a measured density ratio. That is the number
    this estimator has to be able to recover.
    """

    def _tracer(self, norad: int, *, decay_m_per_day: float, start, days, seed):
        """A passive object decaying at a prescribed rate near 475 km."""
        rng = random.Random(seed)
        mean_motion0 = 15.42          # ~475 km
        a0 = oh.semi_major_axis_km(mean_motion0)
        records = []
        step = 0.25
        count = int(days / step)
        for index in range(count):
            elapsed = index * step
            a = a0 + decay_m_per_day / 1000.0 * elapsed
            # a ~ n^(-2/3), so n = n0 * (a0/a)^(3/2)
            n = mean_motion0 * (a0 / a) ** 1.5
            records.append(
                gp_record(
                    norad,
                    (start + dt.timedelta(days=elapsed)).strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"
                    ),
                    MEAN_MOTION=f"{n + rng.gauss(0.0, 2e-8):.8f}",
                    OBJECT_TYPE="DEBRIS",
                )
            )
        return records

    def test_a_gannon_scale_density_excursion_is_recovered(self) -> None:
        quiet_start = dt.datetime(2026, 5, 1)
        storm_start = dt.datetime(2026, 5, 10)
        for index in range(30):
            oh.ingest_records(
                self.archive,
                self._tracer(
                    700 + index, decay_m_per_day=-38.0, start=quiet_start,
                    days=8.0, seed=index,
                ),
            )
            oh.ingest_records(
                self.archive,
                self._tracer(
                    700 + index, decay_m_per_day=-180.0, start=storm_start,
                    days=2.0, seed=1000 + index,
                ),
            )
        shells = oh.density_enhancement(
            self.archive,
            quiet_start_ms=oh.parse_epoch_ms("2026-05-01T00:00:00"),
            quiet_end_ms=oh.parse_epoch_ms("2026-05-09T00:00:00"),
            storm_start_ms=oh.parse_epoch_ms("2026-05-10T00:00:00"),
            storm_end_ms=oh.parse_epoch_ms("2026-05-12T00:00:00"),
        )
        self.assertEqual(len(shells), 1)
        shell = shells[0]
        self.assertEqual(shell["objects"], 30)
        self.assertAlmostEqual(shell["densityRatio"], 4.7, delta=0.3)
        self.assertLess(shell["standardError"], 0.3)

    def test_a_quiet_period_measures_no_enhancement(self) -> None:
        start = dt.datetime(2026, 5, 1)
        for index in range(30):
            oh.ingest_records(
                self.archive,
                self._tracer(
                    750 + index, decay_m_per_day=-38.0, start=start,
                    days=10.0, seed=index,
                ),
            )
        shells = oh.density_enhancement(
            self.archive,
            quiet_start_ms=oh.parse_epoch_ms("2026-05-01T00:00:00"),
            quiet_end_ms=oh.parse_epoch_ms("2026-05-05T00:00:00"),
            storm_start_ms=oh.parse_epoch_ms("2026-05-06T00:00:00"),
            storm_end_ms=oh.parse_epoch_ms("2026-05-10T00:00:00"),
        )
        self.assertEqual(len(shells), 1)
        self.assertAlmostEqual(shells[0]["densityRatio"], 1.0, delta=0.15)

    def test_a_baseline_that_is_not_decaying_is_refused(self) -> None:
        """Dividing by a near-zero or positive quiet rate invents a ratio."""
        start = dt.datetime(2026, 5, 1)
        for index in range(30):
            records = synthetic_series(
                780 + index, count=40, start=start, step_hours=6,
                mean_motion0=15.42, noise=2e-8, seed=index,
            )
            for record in records:
                record["OBJECT_TYPE"] = "DEBRIS"
            oh.ingest_records(self.archive, records)
        shells = oh.density_enhancement(
            self.archive,
            quiet_start_ms=oh.parse_epoch_ms("2026-05-01T00:00:00"),
            quiet_end_ms=oh.parse_epoch_ms("2026-05-05T00:00:00"),
            storm_start_ms=oh.parse_epoch_ms("2026-05-06T00:00:00"),
            storm_end_ms=oh.parse_epoch_ms("2026-05-10T00:00:00"),
        )
        # Roughly half the objects have a positive "quiet" rate from noise
        # alone, so the shell should never reach the 20-object minimum.
        self.assertEqual(shells, [])


class OrbitAveragingTests(ArchiveTestCase):
    def test_a_sub_orbit_interval_is_refused_for_drag_work(self) -> None:
        """Neutral density swings by a factor of two between day and night, so
        a decay rate over a fraction of a revolution measures local solar time
        rather than the atmosphere."""
        start = dt.datetime(2026, 5, 1)
        # 15.42 rev/day -> one revolution is 93.4 minutes.
        oh.ingest_records(
            self.archive,
            [
                gp_record(790, "2026-05-01T00:00:00", MEAN_MOTION="15.42000000"),
                gp_record(790, "2026-05-01T00:30:00", MEAN_MOTION="15.42000100"),
                gp_record(790, "2026-05-01T06:00:00", MEAN_MOTION="15.42000200"),
            ],
        )
        elements = oh.series(self.archive, 790)
        # Manoeuvre work keeps every interval; drag work keeps only the long one.
        self.assertEqual(len(oh.rates(elements)), 2)
        averaged = oh.rates(elements, min_span_orbits=oh.ORBIT_AVERAGING_MINIMUM)
        self.assertEqual(len(averaged), 1)
        self.assertGreater(averaged[0].span_days * 15.42, 3.0)


class GeomagneticTests(ArchiveTestCase):
    def test_the_kp_window_is_archived_and_deduplicated(self) -> None:
        artifact = self.tmp / "space-weather.json"
        artifact.write_text(
            json.dumps(
                {
                    "geomagnetic": {
                        "observedAt": "2026-08-07T07:14:00",
                        "kp": 1.0,
                        "series": [
                            {"time": "2026-08-07T05:29:00Z", "value": 0.0},
                            {"time": "2026-08-07T05:44:00Z", "value": 1.33},
                        ],
                    }
                }
            )
        )
        self.assertEqual(oh.capture_geomagnetic(self.archive, artifact), 2)
        self.assertEqual(oh.capture_geomagnetic(self.archive, artifact), 0)
        samples = oh.kp_series(
            self.archive,
            start_ms=oh.parse_epoch_ms("2026-08-07T00:00:00"),
            end_ms=oh.parse_epoch_ms("2026-08-08T00:00:00"),
        )
        self.assertEqual([value for _, value in samples], [0.0, 1.33])

    def test_a_json_null_where_an_object_belongs_is_survivable(self) -> None:
        """`payload.get("geomagnetic", {})` returns None, not {}, when the key
        is present with a null - and the next `.get` raises."""
        artifact = self.tmp / "null.json"
        for body in ('{"geomagnetic": null}', "null", "[]", '"a string"',
                     '{"geomagnetic": {"series": null}}'):
            artifact.write_text(body)
            self.assertEqual(oh.capture_geomagnetic(self.archive, artifact), 0)

    def test_a_manifest_that_is_not_an_object_is_survivable(self) -> None:
        root = self.tmp / "weird"
        root.mkdir()
        for body in ("null", "[]", '"a string"', "123"):
            (root / "manifest.json").write_text(body)
            self.assertIsNone(oh.space_weather_artifact_from_manifest(root))

    def test_the_artifact_is_resolved_through_the_manifest(self) -> None:
        """Artifacts are content-addressed, so their names change every build
        and a systemd unit cannot glob for them."""
        root = self.tmp / "data"
        (root / "artifacts").mkdir(parents=True)
        (root / "artifacts" / "space-weather-deadbeef.json").write_text("{}")
        (root / "manifest.json").write_text(
            json.dumps(
                {"spaceWeather": {"path": "artifacts/space-weather-deadbeef.json"}}
            )
        )
        resolved = oh.space_weather_artifact_from_manifest(root)
        self.assertEqual(resolved.name, "space-weather-deadbeef.json")

    def test_manifest_resolution_never_stops_the_capture(self) -> None:
        root = self.tmp / "nothing"
        self.assertIsNone(oh.space_weather_artifact_from_manifest(root))
        root.mkdir()
        (root / "manifest.json").write_text("{not json")
        self.assertIsNone(oh.space_weather_artifact_from_manifest(root))
        (root / "manifest.json").write_text(json.dumps({"spaceWeather": {}}))
        self.assertIsNone(oh.space_weather_artifact_from_manifest(root))
        (root / "manifest.json").write_text(
            json.dumps({"spaceWeather": {"path": "artifacts/absent.json"}})
        )
        self.assertIsNone(oh.space_weather_artifact_from_manifest(root))

    def test_a_missing_or_malformed_artifact_is_survivable(self) -> None:
        self.assertEqual(oh.capture_geomagnetic(self.archive, self.tmp / "gone.json"), 0)
        broken = self.tmp / "broken.json"
        broken.write_text("{not json")
        self.assertEqual(oh.capture_geomagnetic(self.archive, broken), 0)
        empty = self.tmp / "empty.json"
        empty.write_text(json.dumps({"geomagnetic": {}}))
        self.assertEqual(oh.capture_geomagnetic(self.archive, empty), 0)


# ---------------------------------------------------------------------------
# Cold shards and retention
# ---------------------------------------------------------------------------
class ColdShardTests(ArchiveTestCase):
    def test_varints_round_trip_including_negatives_and_the_null_sentinel(self):
        values = [0, 1, -1, 127, -128, 2**40, -(2**40), oh._MISSING]
        self.assertEqual(list(oh.decode_varints(oh.encode_varints(values))), values)

    def test_a_shard_round_trips_every_row_exactly(self) -> None:
        start = dt.datetime(2026, 3, 1)
        for norad in (400, 401):
            oh.ingest_records(
                self.archive,
                synthetic_series(
                    norad, count=30, start=start, step_hours=6,
                    mean_motion0=15.5, decay_per_day=1e-5,
                ),
            )
        rows = self.rows()
        self.assertEqual(oh.decode_shard(oh.encode_shard(rows)), rows)

    def test_a_shard_round_trips_null_columns(self) -> None:
        record = gp_record(402, "2026-03-01T00:00:00", BSTAR="", REV_AT_EPOCH=None)
        oh.ingest_records(self.archive, [record])
        rows = self.rows()
        decoded = oh.decode_shard(oh.encode_shard(rows))
        self.assertEqual(decoded, rows)
        self.assertIsNone(decoded[0][8])    # bstar_q
        self.assertIsNone(decoded[0][11])   # rev_at_epoch

    def test_decode_rejects_a_foreign_blob(self) -> None:
        with self.assertRaises(oh.ArchiveError):
            oh.decode_shard(zlib.compress(b"NOPE" + b"\x00" * 60))

    def test_export_month_selects_only_that_month(self) -> None:
        oh.ingest_records(self.archive, [gp_record(500, "2026-03-31T23:59:59")])
        oh.ingest_records(self.archive, [gp_record(500, "2026-04-01T00:00:01")])
        report = oh.export_month(self.archive, 2026, 3, self.tmp / "m.ohz")
        self.assertEqual(report["rows"], 1)

    def test_december_does_not_overflow_into_the_next_year(self) -> None:
        oh.ingest_records(self.archive, [gp_record(501, "2027-01-05T00:00:00")])
        report = oh.export_month(self.archive, 2026, 12, self.tmp / "d.ohz")
        self.assertEqual(report["rows"], 0)

    def test_prune_refuses_to_delete_data_that_is_not_safely_elsewhere(self) -> None:
        """The retention rule that matters: nothing leaves tier 1 until it is
        both decimated into tier 2 and inside a cold shard that read back
        identically."""
        oh.ingest_records(self.archive, [gp_record(600, "2026-01-01T00:00:00")])
        oh.ingest_records(self.archive, [gp_record(600, "2026-06-01T00:00:00")])
        with self.assertRaises(oh.ArchiveError):
            oh.prune_hot(self.archive, oh.parse_epoch_ms("2026-03-01T00:00:00"))
        self.assertEqual(len(oh.series(self.archive, 600)), 2)

    def test_prune_proceeds_once_the_day_is_decimated_and_shipped(self) -> None:
        oh.ingest_records(self.archive, [gp_record(600, "2026-01-01T00:00:00")])
        oh.ingest_records(self.archive, [gp_record(600, "2026-06-01T00:00:00")])
        oh.decimate_day(self.archive, oh.parse_epoch_ms("2026-01-01T00:00:00") // 86_400_000)
        oh.export_month(self.archive, 2026, 1, self.tmp / "jan.ohz")
        removed = oh.prune_hot(self.archive, oh.parse_epoch_ms("2026-03-01T00:00:00"))
        self.assertEqual(removed, 1)
        self.assertEqual(len(oh.series(self.archive, 600)), 1)
        # The pruned element set is still readable at daily resolution.
        self.assertEqual(len(oh.daily_series(self.archive, 600)), 1)

    def test_force_is_the_only_way_to_discard_data(self) -> None:
        oh.ingest_records(self.archive, [gp_record(601, "2026-01-01T00:00:00")])
        removed = oh.prune_hot(
            self.archive, oh.parse_epoch_ms("2026-03-01T00:00:00"), force=True
        )
        self.assertEqual(removed, 1)

    def test_an_unverified_shard_does_not_authorise_a_prune(self) -> None:
        oh.ingest_records(self.archive, [gp_record(602, "2026-01-01T00:00:00")])
        oh.decimate_day(self.archive, oh.parse_epoch_ms("2026-01-01T00:00:00") // 86_400_000)
        oh.export_month(self.archive, 2026, 1, self.tmp / "jan.ohz", verify=False)
        with self.assertRaises(oh.ArchiveError):
            oh.prune_hot(self.archive, oh.parse_epoch_ms("2026-03-01T00:00:00"))


class DecimationTests(ArchiveTestCase):
    def test_the_element_set_nearest_noon_is_the_one_kept(self) -> None:
        for hour in (1, 11, 13, 23):
            oh.ingest_records(
                self.archive, [gp_record(610, f"2026-05-04T{hour:02d}:00:00")]
            )
        day = oh.parse_epoch_ms("2026-05-04T00:00:00") // 86_400_000
        report = oh.decimate_day(self.archive, day)
        self.assertEqual(report["rowsIn"], 4)
        self.assertEqual(report["rowsKept"], 1)
        (kept,) = oh.daily_series(self.archive, 610)
        self.assertEqual(kept.epoch.hour, 11)

    def test_decimation_does_not_bleed_across_the_day_boundary(self) -> None:
        oh.ingest_records(self.archive, [gp_record(611, "2026-05-04T23:59:59")])
        oh.ingest_records(self.archive, [gp_record(611, "2026-05-05T00:00:01")])
        day = oh.parse_epoch_ms("2026-05-04T00:00:00") // 86_400_000
        self.assertEqual(oh.decimate_day(self.archive, day)["rowsIn"], 1)

    def test_decimation_is_idempotent(self) -> None:
        oh.ingest_records(self.archive, [gp_record(612, "2026-05-04T11:00:00")])
        day = oh.parse_epoch_ms("2026-05-04T00:00:00") // 86_400_000
        oh.decimate_day(self.archive, day)
        oh.decimate_day(self.archive, day)
        self.assertEqual(len(oh.daily_series(self.archive, 612)), 1)


class RollTests(ArchiveTestCase):
    def test_roll_decimates_exports_and_prunes_in_that_order(self) -> None:
        start = dt.datetime(2026, 1, 1)
        for index in range(40):
            oh.ingest_records(
                self.archive,
                [
                    gp_record(
                        620,
                        (start + dt.timedelta(days=index)).strftime(
                            "%Y-%m-%dT%H:%M:%S.%f"
                        ),
                    )
                ],
            )
        now_ms = oh.parse_epoch_ms("2026-06-15T00:00:00")
        report = oh.roll(
            self.archive, retain_days=100, cold_directory=self.tmp / "cold", now_ms=now_ms
        )
        self.assertEqual(report["retainDays"], 100)
        self.assertEqual(len(report["decimated"]), 40)
        exported = {entry["month"] for entry in report["exported"]}
        self.assertEqual(exported, {"2026-01", "2026-02"})
        self.assertTrue(all(entry["verified"] for entry in report["exported"]))
        # 100 days before 2026-06-15 is 2026-03-07, so all 40 January and
        # February element sets leave tier 1 and survive in tiers 2 and 3.
        self.assertEqual(report["pruned"], 40)
        self.assertEqual(oh.series(self.archive, 620), [])
        self.assertEqual(len(oh.daily_series(self.archive, 620)), 40)
        self.assertTrue((self.tmp / "cold" / "orbit-history-2026-01.ohz").exists())

    def test_roll_leaves_the_current_month_alone(self) -> None:
        oh.ingest_records(self.archive, [gp_record(621, "2026-06-02T00:00:00")])
        report = oh.roll(
            self.archive,
            retain_days=400,
            cold_directory=self.tmp / "cold",
            now_ms=oh.parse_epoch_ms("2026-06-15T00:00:00"),
        )
        self.assertEqual(report["exported"], [])
        self.assertEqual(len(oh.series(self.archive, 621)), 1)

    def test_a_partly_pruned_month_is_never_re_exported_over_its_own_shard(self):
        """The data-loss sequence this guards: export the whole month, prune
        part of it, then let late element sets arrive. A row-count guard is
        fooled by the late arrivals and rewrites the shard from the survivors,
        destroying the pruned rows in the only full-fidelity copy."""
        start = dt.datetime(2026, 1, 1)
        for index in range(20):
            oh.ingest_records(
                self.archive,
                [
                    gp_record(
                        630,
                        (start + dt.timedelta(days=index)).strftime(
                            "%Y-%m-%dT%H:%M:%S.%f"
                        ),
                    )
                ],
            )
        cold = self.tmp / "cold"
        first = oh.roll(
            self.archive,
            retain_days=160,
            cold_directory=cold,
            now_ms=oh.parse_epoch_ms("2026-06-15T00:00:00"),
        )
        self.assertEqual(first["exported"][0]["rows"], 20)
        self.assertEqual(first["pruned"], 5)          # 2026-01-01 .. 2026-01-05
        shard = (cold / "orbit-history-2026-01.ohz").read_bytes()
        self.assertEqual(len(oh.decode_shard(shard)), 20)

        # Late element sets for a day that was never pruned push the row count
        # back above what the shard recorded.
        for index in range(12):
            oh.ingest_records(
                self.archive,
                [gp_record(630, f"2026-01-25T{index:02d}:30:00")],
            )
        second = oh.roll(
            self.archive,
            retain_days=160,
            cold_directory=cold,
            now_ms=oh.parse_epoch_ms("2026-06-15T00:00:00"),
        )
        self.assertEqual(second["exported"], [])
        self.assertEqual(len(second["skipped"]), 1)
        self.assertEqual(second["skipped"][0]["month"], "2026-01")
        self.assertEqual((cold / "orbit-history-2026-01.ohz").read_bytes(), shard)
        self.assertEqual(len(oh.decode_shard(shard)), 20)

    def test_a_month_that_gains_late_element_sets_is_re_exported(self) -> None:
        """The opposite case: space-track does publish element sets whose epoch
        is already old, and a shard must be allowed to grow."""
        oh.ingest_records(self.archive, [gp_record(631, "2026-01-05T00:00:00")])
        cold = self.tmp / "cold"
        kwargs = dict(
            retain_days=400,
            cold_directory=cold,
            now_ms=oh.parse_epoch_ms("2026-03-15T00:00:00"),
        )
        self.assertEqual(oh.roll(self.archive, **kwargs)["exported"][0]["rows"], 1)
        oh.ingest_records(self.archive, [gp_record(631, "2026-01-06T00:00:00")])
        second = oh.roll(self.archive, **kwargs)
        self.assertEqual(second["exported"][0]["rows"], 2)
        self.assertEqual(second["skipped"], [])

    def test_a_day_is_left_to_settle_before_it_is_decimated(self) -> None:
        """Element sets arrive with epochs a day or two old; decimating the
        moment a day ends would pick the wrong representative."""
        oh.ingest_records(self.archive, [gp_record(632, "2026-06-14T11:00:00")])
        report = oh.roll(
            self.archive,
            retain_days=400,
            cold_directory=self.tmp / "cold",
            now_ms=oh.parse_epoch_ms("2026-06-15T06:00:00"),
        )
        self.assertEqual(report["decimated"], [])
        report = oh.roll(
            self.archive,
            retain_days=400,
            cold_directory=self.tmp / "cold",
            now_ms=oh.parse_epoch_ms("2026-06-17T06:00:00"),
        )
        self.assertEqual(len(report["decimated"]), 1)

    def test_a_lost_shard_file_revokes_permission_to_prune(self) -> None:
        """The ledger says the month is safe; the disk disagrees."""
        oh.ingest_records(self.archive, [gp_record(640, "2026-01-05T00:00:00")])
        cold = self.tmp / "cold"
        oh.roll(
            self.archive,
            retain_days=400,
            cold_directory=cold,
            now_ms=oh.parse_epoch_ms("2026-03-15T00:00:00"),
        )
        (cold / "orbit-history-2026-01.ohz").unlink()
        with self.assertRaises(oh.ArchiveError):
            oh.prune_hot(self.archive, oh.parse_epoch_ms("2026-02-01T00:00:00"))

    def test_a_corrupted_shard_file_revokes_permission_to_prune(self) -> None:
        oh.ingest_records(self.archive, [gp_record(641, "2026-01-05T00:00:00")])
        cold = self.tmp / "cold"
        oh.roll(
            self.archive,
            retain_days=400,
            cold_directory=cold,
            now_ms=oh.parse_epoch_ms("2026-03-15T00:00:00"),
        )
        shard = cold / "orbit-history-2026-01.ohz"
        shard.write_bytes(shard.read_bytes() + b"rot")
        with self.assertRaises(oh.ArchiveError):
            oh.prune_hot(self.archive, oh.parse_epoch_ms("2026-02-01T00:00:00"))

    def test_a_verified_shard_is_never_replaced_by_an_unverified_one(self) -> None:
        oh.ingest_records(self.archive, [gp_record(642, "2026-01-05T00:00:00")])
        destination = self.tmp / "jan.ohz"
        oh.export_month(self.archive, 2026, 1, destination)
        with self.assertRaises(oh.ArchiveError):
            oh.export_month(self.archive, 2026, 1, destination, verify=False)

    def test_the_prune_watermark_is_monotonic(self) -> None:
        oh.ingest_records(self.archive, [gp_record(643, "2026-01-05T00:00:00")])
        self.assertEqual(oh.pruned_before_ms(self.archive), 0)
        late = oh.parse_epoch_ms("2026-06-01T00:00:00")
        oh.prune_hot(self.archive, late, force=True)
        self.assertEqual(oh.pruned_before_ms(self.archive), late)
        oh.prune_hot(self.archive, oh.parse_epoch_ms("2026-02-01T00:00:00"), force=True)
        self.assertEqual(oh.pruned_before_ms(self.archive), late)

    def test_a_day_that_gains_a_late_element_set_is_decimated_again(self) -> None:
        oh.ingest_records(self.archive, [gp_record(644, "2026-06-10T20:00:00")])
        kwargs = dict(
            retain_days=400,
            cold_directory=self.tmp / "cold",
            now_ms=oh.parse_epoch_ms("2026-06-15T00:00:00"),
        )
        oh.roll(self.archive, **kwargs)
        self.assertEqual(oh.daily_series(self.archive, 644)[0].epoch.hour, 20)
        # A later capture brings an element set nearer noon for the same day.
        oh.ingest_records(self.archive, [gp_record(644, "2026-06-10T12:30:00")])
        report = oh.roll(self.archive, **kwargs)
        self.assertEqual(len(report["decimated"]), 1)
        self.assertEqual(oh.daily_series(self.archive, 644)[0].epoch.hour, 12)

    def test_the_settle_window_is_the_number_of_days_it_says(self) -> None:
        oh.ingest_records(self.archive, [gp_record(645, "2026-06-13T11:00:00")])
        kwargs = dict(retain_days=400, cold_directory=self.tmp / "cold")
        # 2026-06-13 is one day old on the 14th, two on the 15th.
        report = oh.roll(
            self.archive, now_ms=oh.parse_epoch_ms("2026-06-14T06:00:00"), **kwargs
        )
        self.assertEqual(report["decimated"], [])
        report = oh.roll(
            self.archive, now_ms=oh.parse_epoch_ms("2026-06-15T06:00:00"), **kwargs
        )
        self.assertEqual(len(report["decimated"]), 1)

    def test_roll_is_idempotent(self) -> None:
        oh.ingest_records(self.archive, [gp_record(622, "2026-01-02T00:00:00")])
        kwargs = dict(
            retain_days=400,
            cold_directory=self.tmp / "cold",
            now_ms=oh.parse_epoch_ms("2026-06-15T00:00:00"),
        )
        oh.roll(self.archive, **kwargs)
        second = oh.roll(self.archive, **kwargs)
        self.assertEqual(second["decimated"], [])
        self.assertEqual(len(oh.daily_series(self.archive, 622)), 1)


class StatsTests(ArchiveTestCase):
    def test_the_unix_epoch_is_data_not_absence(self) -> None:
        """`if epoch_ms` reports 1970-01-01T00:00:00Z as "no data"."""
        self.assertIsNone(oh._iso_or_none(None))
        self.assertEqual(oh._iso_or_none(0), "1970-01-01T00:00:00+00:00")

    def test_archive_stats_reports_provable_coverage(self) -> None:
        oh.ingest_records(
            self.archive,
            [gp_record(700, "2026-08-07T00:00:00")],
            captured_ms=1_754_524_800_000,
        )
        stats = oh.archive_stats(self.archive)
        self.assertEqual(stats["elementSets"], 1)
        self.assertEqual(stats["objects"], 1)
        self.assertEqual(stats["captures"], 1)
        self.assertEqual(stats["schemaVersion"], oh.SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# The rule that matters most
# ---------------------------------------------------------------------------
class BoundaryTests(unittest.TestCase):
    def test_module_makes_no_network_calls(self) -> None:
        """space-track is polled once an hour by one script under one identity.

        If this module ever grows a fetch, this test is what catches it.
        """
        source = Path(oh.__file__).read_text()
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {
            "urllib", "http", "requests", "httpx", "socket", "ftplib",
            "smtplib", "aiohttp", "ssl", "asyncio", "subprocess",
        }
        self.assertEqual(imported & forbidden, set())
        for banned in ("space-track.org", "celestrak.org", "urlopen("):
            self.assertNotIn(banned, source)

    def test_no_verbatim_tle_lines_are_archived(self) -> None:
        """Element sets are basic SSA data; mirroring the upstream TLE text at
        scale is what would make this a clearinghouse."""
        columns = {name for name in oh._ELEMENT_COLUMNS}
        self.assertNotIn("tle_line1", columns)
        self.assertNotIn("tle_line2", columns)
        source = Path(oh.__file__).read_text()
        self.assertNotIn('"TLE_LINE1"', source)
        self.assertNotIn('"TLE_LINE2"', source)


class CommandLineTests(unittest.TestCase):
    def test_capture_and_status_work_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            mirror = tmp / "gp-active.json"
            mirror.write_text(
                json.dumps(
                    [
                        gp_record(800, "2026-08-07T00:00:00"),
                        gp_record(801, "2026-08-07T00:30:00"),
                    ]
                )
            )
            archive_path = tmp / "orbit-history.sqlite3"
            stream = StringIO()
            with redirect_stdout(stream):
                code = oh.main(
                    ["--archive", str(archive_path), "--mirror", str(mirror), "--capture"]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stream.getvalue())["elementsNew"], 2)

            stream = StringIO()
            with redirect_stdout(stream):
                oh.main(["--archive", str(archive_path), "--status"])
            status = json.loads(stream.getvalue())
            self.assertEqual(status["elementSets"], 2)
            self.assertEqual(status["objects"], 2)


# ---------------------------------------------------------------------------
# Contention: the capture must win
# ---------------------------------------------------------------------------
# On 2026-08-08 the hourly capture died twice with `database is locked` while
# `orbit-release` held one cursor over the whole archive for 42 minutes. Every
# hour it misses is orbital history that cannot be recovered, because
# `gp-active.json` is overwritten in place by the next fetch.
#
# These are real SQLite tests against real files. Nothing here is mocked: a mock
# cannot have a locking protocol, and the locking protocol is the entire
# subject. Concurrency is done with threads holding their own connections, which
# was checked against the cross-process case first — a live cursor in another
# thread blocks a writer exactly as one in another process does.
def _populate(path: Path, *, objects: int, per_object: int) -> None:
    """A real archive with a known number of rows in known key order."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=TRUNCATE")
    connection.executescript(oh._SCHEMA)
    connection.executemany(
        "INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (norad, 1_700_000_000_000 + index * 21_600_000,
             1_550_000_000, 12_340, 530_500, 1_204_321, 901_234, 2_709_876,
             123_450, 247, 0, 12_345 + index, 0)
            for norad in range(1, objects + 1)
            for index in range(per_object)
        ],
    )
    connection.commit()
    connection.close()


class PagedScanEquivalenceTests(unittest.TestCase):
    """The paged scan must be indistinguishable from the statement it replaced."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "orbit-history.sqlite3"
        # 7 objects x 11 rows = 77, which is deliberately awkward: it is not a
        # multiple of any page size tested below except 7 and 11, so object
        # boundaries and page boundaries fall in different places.
        _populate(self.path, objects=7, per_object=11)
        self.connection = sqlite3.connect(self.path)
        self.addCleanup(self.connection.close)

    def unpaged(self) -> list[tuple]:
        return list(
            self.connection.execute(
                f"SELECT {oh.SCAN_COLUMNS} FROM element_set ORDER BY norad, epoch_ms"
            )
        )

    def test_every_page_size_returns_exactly_the_unpaged_rows(self) -> None:
        expected = self.unpaged()
        self.assertEqual(len(expected), 77)
        for page in (1, 2, 7, 11, 76, 77, 78, 1000):
            with self.subTest(page_rows=page):
                self.assertEqual(
                    list(oh.paged_element_sets(self.connection, page_rows=page)),
                    expected,
                )

    def test_a_row_count_that_is_an_exact_multiple_of_the_page_size(self) -> None:
        """The off-by-one that duplicates or drops a row lives exactly here.

        With 77 rows and a page of 11 the seventh page is full and the eighth is
        empty, so the loop has to decide to stop on an empty page rather than on
        a short one. With 78 rows and a page of 11 it stops on a short page.
        Both are asserted because a scan that handled one and not the other
        would still pass a test that only used a ragged table.
        """
        self.assertEqual(len(self.unpaged()) % 11, 0)
        self.assertEqual(
            list(oh.paged_element_sets(self.connection, page_rows=11)), self.unpaged()
        )
        self.connection.execute(
            "INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (7, 1_700_000_000_000 + 99 * 21_600_000, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0),
        )
        self.connection.commit()
        self.assertEqual(len(self.unpaged()) % 11, 1)
        self.assertEqual(
            list(oh.paged_element_sets(self.connection, page_rows=11)), self.unpaged()
        )

    def test_the_only_filter_is_paged_too_and_agrees(self) -> None:
        expected = list(
            self.connection.execute(
                f"SELECT {oh.SCAN_COLUMNS} FROM element_set WHERE norad IN (2,5) "
                "ORDER BY norad, epoch_ms"
            )
        )
        self.assertEqual(len(expected), 22)
        for page in (1, 3, 22, 23):
            with self.subTest(page_rows=page):
                self.assertEqual(
                    list(oh.paged_element_sets(self.connection, only=[2, 5], page_rows=page)),
                    expected,
                )

    def test_the_stream_groups_objects_identically_across_page_boundaries(self) -> None:
        """`stream_object_rows` buffers per object; pages cut through objects.

        An object whose rows straddle a page boundary must still be yielded once,
        whole and in order. A page size of 4 against 11 rows an object guarantees
        every object is split, and split at a different offset each time.
        """
        whole = {norad: rows for norad, rows in oc.stream_object_rows(
            self.connection, page_rows=10_000)}
        split = {norad: rows for norad, rows in oc.stream_object_rows(
            self.connection, page_rows=4)}
        self.assertEqual(sorted(whole), list(range(1, 8)))
        self.assertEqual(whole, split)
        for rows in split.values():
            self.assertEqual(len(rows), 11)
            self.assertEqual([row[0] for row in rows], sorted(row[0] for row in rows))

    def test_a_delete_ahead_of_the_cursor_cannot_make_the_scan_skip_a_row(self) -> None:
        """Key-set paging, not LIMIT/OFFSET, and this is why it had to be.

        `prune_hot` really does `DELETE FROM element_set WHERE epoch_ms < ?`, so
        the table is NOT append-only and a scan cannot assume it is. Under
        OFFSET paging a delete ahead of the cursor shifts every later row back
        by one and the scan silently skips one. Under key-set paging the next
        page resumes at the last key seen, so the surviving rows are all still
        returned in order.
        """
        seen: list[tuple] = []
        scan = oh.paged_element_sets(self.connection, page_rows=5)
        for _ in range(12):
            seen.append(next(scan))
        # Delete a row the cursor has not reached yet.
        victim = self.connection.execute(
            f"SELECT {oh.SCAN_COLUMNS} FROM element_set WHERE norad = 5 "
            "ORDER BY epoch_ms LIMIT 1"
        ).fetchone()
        self.connection.execute(
            "DELETE FROM element_set WHERE norad = ? AND epoch_ms = ?", victim[:2]
        )
        self.connection.commit()
        seen.extend(scan)
        survivors = self.unpaged()
        self.assertNotIn(victim, survivors)
        self.assertEqual(seen, survivors)


class WriterStarvationTests(unittest.TestCase):
    """A long reader must not be able to kill the capture."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "orbit-history.sqlite3"
        _populate(self.path, objects=40, per_object=200)

    def _write_while(self, read, *, timeout: float) -> tuple[bool, float]:
        """Run `read` in a thread; try to write against it; report what happened.

        The writer's busy timeout is deliberately much shorter than the read, so
        "the writer succeeded" can only mean the reader actually let go of the
        lock — never that the writer simply outwaited it.
        """
        outcome: dict[str, object] = {}
        reading = threading.Event()
        finished = threading.Event()

        def reader() -> None:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=0)
            try:
                read(connection, reading)
            finally:
                connection.close()
                finished.set()

        thread = threading.Thread(target=reader)
        thread.start()
        self.addCleanup(thread.join)
        self.assertTrue(reading.wait(30), "the reader never started")

        writer = sqlite3.connect(self.path, timeout=timeout)
        started = time.monotonic()
        try:
            writer.execute(
                "INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (99, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0),
            )
            writer.commit()
            wrote = True
        except sqlite3.OperationalError:
            wrote = False
        finally:
            waited = time.monotonic() - started
            writer.close()
        finished.wait(30)
        thread.join()
        return wrote, waited

    def test_an_unpaged_reader_starves_the_writer(self) -> None:
        """The defect itself, reproduced. If this ever passes, the premise is gone."""

        def read(connection, reading) -> None:
            cursor = connection.execute(
                f"SELECT {oh.SCAN_COLUMNS} FROM element_set ORDER BY norad, epoch_ms"
            )
            cursor.fetchone()
            reading.set()
            # Stand in for the 42 minutes the release spends analysing rows it
            # has already fetched -- all of it, in the old code, inside the
            # lifetime of this cursor.
            time.sleep(3.0)
            cursor.fetchall()

        wrote, waited = self._write_while(read, timeout=1.0)
        self.assertFalse(wrote, "the unpaged reader was expected to starve the writer")
        self.assertGreaterEqual(waited, 1.0)

    def test_a_paged_reader_lets_the_writer_through(self) -> None:
        """The fix. Same reader, same total work, same 3 seconds of holding the
        rows -- but the read transaction ends between pages, so the writer gets
        in with a busy timeout six times shorter than the read it is up against.
        """

        def read(connection, reading) -> None:
            for index, _row in enumerate(oh.paged_element_sets(connection, page_rows=250)):
                if index == 0:
                    reading.set()
                if index % 250 == 0:
                    time.sleep(0.1)

        wrote, waited = self._write_while(read, timeout=0.5)
        self.assertTrue(
            wrote, f"the paged reader still starved the writer (waited {waited:.2f}s)"
        )


class JournalModeLockTests(unittest.TestCase):
    """Why `open_archive` sets journal_mode unconditionally rather than checking.

    Guarding the pragma behind "only set it when it differs" was the obvious
    saving and it is worth nothing. These two tests pin the measurements that
    say so, so that the guard is not reintroduced -- and so that if a future
    SQLite changes either fact, something fails loudly instead of the capture
    quietly starving again.
    """

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "orbit-history.sqlite3"
        _populate(self.path, objects=4, per_object=25)

    def test_a_rollback_journal_mode_is_never_already_set_on_a_new_connection(self) -> None:
        """So a "has it changed?" check can never take the cheap branch.

        DELETE/TRUNCATE/PERSIST are properties of the CONNECTION; only WAL is
        recorded in the file. A fresh connection to an archive that has been
        written in TRUNCATE mode for months still reports `delete`.
        """
        first = sqlite3.connect(self.path)
        self.addCleanup(first.close)
        self.assertEqual(first.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(
            first.execute("PRAGMA journal_mode=TRUNCATE").fetchone()[0], "truncate"
        )
        first.commit()

        second = sqlite3.connect(self.path)
        self.addCleanup(second.close)
        self.assertEqual(second.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_setting_the_journal_mode_does_not_take_a_write_lock(self) -> None:
        """So the guard would not have saved a lock even if it could fire.

        Both forms need the same thing -- a read of page 1 -- and neither needs
        to write. Run here against a database another connection is holding
        SHARED: the pragma goes through, a real write does not.
        """
        reader = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=0)
        self.addCleanup(reader.close)
        cursor = reader.execute("SELECT norad, epoch_ms FROM element_set ORDER BY norad")
        cursor.fetchone()

        other = sqlite3.connect(self.path, timeout=0)
        self.addCleanup(other.close)
        self.assertEqual(other.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(
            other.execute("PRAGMA journal_mode=TRUNCATE").fetchone()[0], "truncate"
        )
        with self.assertRaises(sqlite3.OperationalError):
            other.execute(
                "INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (77, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0),
            )
            other.commit()


class BusyTimeoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "orbit-history.sqlite3"

    def test_the_default_is_generous_enough_to_outlast_the_archives_own_scans(self) -> None:
        """`archive_stats` alone holds the archive for 103 s on the live file.

        The old 60 s could not survive the release's cheapest whole-table query,
        let alone its main scan.
        """
        self.assertGreaterEqual(oh.DEFAULT_BUSY_TIMEOUT_SECONDS, 600.0)

    def test_the_timeout_is_tunable_and_bad_values_do_not_silently_shrink_it(self) -> None:
        with unittest.mock.patch.dict(
            os.environ, {"SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS": "12.5"}
        ):
            self.assertEqual(oh.busy_timeout_seconds(), 12.5)
        for bad in ("", "soon", "0", "-5"):
            with self.subTest(value=bad), unittest.mock.patch.dict(
                os.environ, {"SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS": bad}
            ), redirect_stderr(StringIO()):
                self.assertEqual(
                    oh.busy_timeout_seconds(), oh.DEFAULT_BUSY_TIMEOUT_SECONDS
                )

    def test_the_page_size_is_tunable_and_bad_values_do_not_silently_shrink_it(self) -> None:
        with unittest.mock.patch.dict(
            os.environ, {"SPACE_EXPLORER_ORBIT_SCAN_PAGE_ROWS": "1000"}
        ):
            self.assertEqual(oh.scan_page_rows(), 1000)
        for bad in ("", "lots", "0", "-1"):
            with self.subTest(value=bad), unittest.mock.patch.dict(
                os.environ, {"SPACE_EXPLORER_ORBIT_SCAN_PAGE_ROWS": bad}
            ), redirect_stderr(StringIO()):
                self.assertEqual(oh.scan_page_rows(), oh.DEFAULT_SCAN_PAGE_ROWS)

    def test_open_archive_actually_applies_the_configured_timeout(self) -> None:
        """A configured timeout that never reaches sqlite3.connect is the defect
        class `docs/OPEN-WORK.md` calls a green test over a never-executed
        default. Measured by how long a blocked write actually waits.
        """
        _populate(self.path, objects=2, per_object=50)
        holder = sqlite3.connect(self.path, timeout=0)
        self.addCleanup(holder.close)
        holder.execute("BEGIN EXCLUSIVE")

        with unittest.mock.patch.dict(
            os.environ, {"SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS": "1.5"}
        ):
            started = time.monotonic()
            with self.assertRaises(sqlite3.OperationalError):
                oh.open_archive(self.path)
            waited = time.monotonic() - started
        holder.rollback()
        self.assertGreaterEqual(waited, 1.4)
        self.assertLess(waited, 10.0)


class StarvedCaptureReportTests(unittest.TestCase):
    """A lost hour has to say it is a lost hour."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.tmp = Path(self._directory.name)
        self.path = self.tmp / "orbit-history.sqlite3"
        self.mirror = self.tmp / "gp-active.json"
        self.mirror.write_text(json.dumps([gp_record(900, "2026-08-08T10:00:00")]))

    def test_the_report_names_the_hour_the_mirror_and_the_irrecoverability(self) -> None:
        report = oh.starved_capture_report(
            self.mirror, waited_seconds=900.0, archive_path=self.path
        )
        now = dt.datetime.now(dt.timezone.utc)
        self.assertIn(now.strftime("%Y-%m-%dT%H:00Z"), report)
        self.assertIn(str(self.mirror), report)
        mtime = dt.datetime.fromtimestamp(
            self.mirror.stat().st_mtime, dt.timezone.utc
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        self.assertIn(mtime, report)
        self.assertIn("900 s", report)
        self.assertIn("NO", report)
        self.assertIn("orbit-release.service", report)
        self.assertNotIn("Traceback", report)

    def test_a_missing_mirror_still_produces_a_report_rather_than_an_OSError(self) -> None:
        self.mirror.unlink()
        report = oh.starved_capture_report(
            self.mirror, waited_seconds=1.0, archive_path=self.path
        )
        self.assertIn("unknown", report)

    def test_a_starved_capture_raises_ArchiveBusy_not_OperationalError(self) -> None:
        """The whole point: `main` must not let a bare traceback out.

        The archive is held EXCLUSIVE by another connection, which is precisely
        the state a writer sitting at PENDING puts it in.
        """
        _populate(self.path, objects=1, per_object=5)
        holder = sqlite3.connect(self.path, timeout=0)
        self.addCleanup(holder.close)
        holder.execute("BEGIN EXCLUSIVE")

        with unittest.mock.patch.dict(
            os.environ, {"SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS": "0.5"}
        ):
            with self.assertRaises(oh.ArchiveBusy) as raised:
                oh.main([
                    "--archive", str(self.path),
                    "--mirror", str(self.mirror),
                    "--capture",
                ])
        holder.rollback()
        message = str(raised.exception)
        self.assertIn("WAS LOST", message)
        self.assertIn(str(self.mirror), message)
        self.assertIsInstance(raised.exception, oh.ArchiveError)

    def test_a_lock_failure_that_is_not_a_capture_is_not_dressed_up_as_one(self) -> None:
        """`--status` losing the lock is an inconvenience, not a lost hour."""
        _populate(self.path, objects=1, per_object=5)
        holder = sqlite3.connect(self.path, timeout=0)
        self.addCleanup(holder.close)
        holder.execute("BEGIN EXCLUSIVE")

        with unittest.mock.patch.dict(
            os.environ, {"SPACE_EXPLORER_ORBIT_ARCHIVE_TIMEOUT_SECONDS": "0.5"}
        ):
            with self.assertRaises(sqlite3.OperationalError):
                oh.main(["--archive", str(self.path), "--status"])
        holder.rollback()


class MaintainedSummaryTests(unittest.TestCase):
    """The summaries have to equal the scan they replace. Every assertion here
    is that equality, computed both ways on the same rows.

    The reason for the shape of these tests: a summary that is merely close is
    worse than no summary, because it publishes a number nobody will ever
    re-derive. So none of these compares a summary against a constant. Each one
    compares it against the full scan of the same archive at the same instant.
    """

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "orbit-history.sqlite3"
        self.connection = oh.open_archive(self.path)
        self.addCleanup(self.connection.close)

    def _scan(self) -> tuple:
        return self.connection.execute(
            "SELECT COUNT(*), MIN(epoch_ms), MAX(epoch_ms) FROM element_set"
        ).fetchone()

    def _ingest(self, records) -> oh.CaptureResult:
        return oh.ingest_records(self.connection, records)

    def _spread(self, count: int, *, norad: int = 25544, start="2024-01-01"):
        """`count` element sets a week apart, so they land in several months."""
        base = dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc)
        return [
            gp_record(norad, (base + dt.timedelta(days=7 * index)).strftime("%Y-%m-%dT%H:%M:%S"))
            for index in range(count)
        ]

    # -- the summary equals the scan ---------------------------------------
    def test_the_summary_total_equals_the_count_it_replaces(self) -> None:
        self._ingest(self._spread(30))
        rows, earliest, latest = oh.summary_totals(self.connection)
        self.assertEqual((rows, earliest, latest), self._scan())

    def test_a_rebuild_from_scratch_equals_the_incremental_summary(self) -> None:
        """Two independent routes to the same three numbers."""
        self._ingest(self._spread(30))
        self._ingest(self._spread(10, norad=48274, start="2023-06-01"))
        incremental = oh.summary_totals(self.connection)
        oh.refresh_summary(self.connection)
        self.assertEqual(oh.summary_totals(self.connection), incremental)
        self.assertEqual(incremental, self._scan())

    def test_archive_stats_reports_the_same_numbers_from_summary_and_from_scan(self) -> None:
        self._ingest(self._spread(40))
        self._ingest(self._spread(15, norad=48274, start="2022-03-01"))
        summarised = oh.archive_stats(self.connection)
        scanned = oh.archive_stats(self.connection, exact=True)
        for field in ("elementSets", "earliestEpoch", "latestEpoch", "objects"):
            self.assertEqual(summarised[field], scanned[field], field)
        self.assertEqual(summarised["elementSetsSource"], "summary")
        self.assertEqual(scanned["elementSetsSource"], "scan")

    def test_every_month_row_equals_that_month_counted_from_the_table(self) -> None:
        self._ingest(self._spread(60))
        for month, rows, low, high in self.connection.execute(
            "SELECT month, rows, min_epoch_ms, max_epoch_ms FROM month_rollup"
        ).fetchall():
            year, number = int(month[:4]), int(month[5:7])
            start_ms, end_ms = oh.month_bounds(year, number)
            self.assertEqual(
                (rows, low, high),
                self.connection.execute(
                    "SELECT COUNT(*), MIN(epoch_ms), MAX(epoch_ms) FROM element_set "
                    "WHERE epoch_ms >= ? AND epoch_ms < ?",
                    (start_ms, end_ms),
                ).fetchone(),
                month,
            )

    def test_every_object_row_equals_that_object_counted_from_the_table(self) -> None:
        self._ingest(self._spread(20))
        self._ingest(self._spread(35, norad=48274, start="2021-01-01"))
        for norad, rows, low, high in self.connection.execute(
            "SELECT norad, rows, min_epoch_ms, max_epoch_ms FROM object_rollup"
        ).fetchall():
            self.assertEqual(
                (rows, low, high),
                self.connection.execute(
                    "SELECT COUNT(*), MIN(epoch_ms), MAX(epoch_ms) FROM element_set "
                    "WHERE norad = ?",
                    (norad,),
                ).fetchone(),
                norad,
            )

    # -- duplicates, which is where a counted-not-asked delta goes wrong ----
    def test_re_ingesting_the_same_records_moves_the_summary_by_zero(self) -> None:
        records = self._spread(25)
        first = self._ingest(records)
        before = oh.summary_totals(self.connection)
        second = self._ingest(records)
        self.assertEqual(first.elements_new, 25)
        self.assertEqual(second.elements_new, 0)
        self.assertEqual(oh.summary_totals(self.connection), before)
        self.assertEqual(oh.summary_totals(self.connection)[0], self._scan()[0])

    def test_a_half_overlapping_batch_counts_only_the_new_half(self) -> None:
        self._ingest(self._spread(20))
        self._ingest(self._spread(30))          # 20 already held, 10 new
        self.assertEqual(oh.summary_totals(self.connection)[0], 30)
        self.assertEqual(oh.summary_totals(self.connection)[0], self._scan()[0])

    def test_the_delta_refuses_to_be_written_when_it_disagrees_with_the_archive(self) -> None:
        """The cross-check itself. A wrong delta must raise, never accumulate."""
        with self.assertRaises(oh.ArchiveError) as raised:
            oh.apply_rollup_delta(
                self.connection, {"2024-01": [5, 1, 2]}, {1: [5, 1, 2]},
                inserted=4, expected=5,
            )
        self.assertIn("predicted 5", str(raised.exception))
        self.assertEqual(oh.summary_totals(self.connection)[0], 0)

    # -- staleness is declared, never hidden -------------------------------
    def test_a_newly_created_archive_is_already_summarised(self) -> None:
        """Empty rollups over an empty table are exact, not unbuilt."""
        self.assertIsNone(oh.summary_is_dirty(self.connection))
        self.assertEqual(oh.summary_totals(self.connection), (0, None, None))

    def test_an_archive_written_before_the_rollups_existed_reads_as_unbuilt(self) -> None:
        """The live archive's case: rows in the table, no summary behind them.

        This is what stops a stale zero being published as a row count.
        """
        self._ingest(self._spread(30))
        self.connection.execute("DELETE FROM meta WHERE key = 'summary_built_ms'")
        self.connection.execute("DELETE FROM month_rollup")
        self.assertEqual(oh.summary_is_dirty(self.connection), "never built")
        stats = oh.archive_stats(self.connection)
        self.assertEqual(stats["elementSetsSource"], "scan")
        self.assertEqual(stats["elementSets"], 30)

    def test_a_prune_marks_the_summary_stale_and_the_stats_fall_back_to_counting(self) -> None:
        self._ingest(self._spread(30))
        self.assertIsNone(oh.summary_is_dirty(self.connection))
        cutoff = int(dt.datetime(2024, 3, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
        removed = oh.prune_hot(self.connection, cutoff, force=True)
        self.assertGreater(removed, 0)
        self.assertIsNotNone(oh.summary_is_dirty(self.connection))
        stats = oh.archive_stats(self.connection)
        self.assertEqual(stats["elementSetsSource"], "scan")
        self.assertEqual(stats["elementSets"], self._scan()[0])

    def test_a_refresh_after_a_prune_makes_the_summary_exact_again(self) -> None:
        self._ingest(self._spread(30))
        cutoff = int(dt.datetime(2024, 3, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
        oh.prune_hot(self.connection, cutoff, force=True)
        oh.refresh_summary(self.connection)
        self.assertIsNone(oh.summary_is_dirty(self.connection))
        self.assertEqual(oh.summary_totals(self.connection), self._scan())

    def test_the_busiest_object_is_the_same_one_the_group_by_finds(self) -> None:
        self._ingest(self._spread(12, norad=25544))
        self._ingest(self._spread(40, norad=48274, start="2023-01-01"))
        self.assertEqual(
            oh.busiest_norad(self.connection),
            self.connection.execute(
                "SELECT norad FROM element_set GROUP BY norad ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()[0],
        )

    def test_the_busiest_object_still_answers_with_no_summary_at_all(self) -> None:
        """The fallback matters: an empty rollup and an empty archive differ."""
        self._ingest(self._spread(12, norad=25544))
        self.connection.execute("DELETE FROM object_rollup")
        oh.mark_summary_dirty(self.connection, "test")
        self.assertEqual(oh.busiest_norad(self.connection), 25544)


class ColdReadTests(unittest.TestCase):
    """A month that has left tier 1 must still answer, byte for byte."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.cold = self.root / "cold"
        self.connection = oh.open_archive(self.root / "orbit-history.sqlite3")
        self.addCleanup(self.connection.close)
        base = dt.datetime(2009, 5, 1, tzinfo=dt.timezone.utc)
        oh.ingest_records(
            self.connection,
            [
                gp_record(norad, (base + dt.timedelta(hours=6 * index)).strftime("%Y-%m-%dT%H:%M:%S"))
                for norad in (25544, 48274)
                for index in range(40)
            ],
        )

    def test_the_shard_on_disk_decodes_to_exactly_the_rows_the_archive_held(self) -> None:
        held = self.connection.execute(
            f"SELECT norad, {', '.join(oh._ELEMENT_COLUMNS)}, ingest_hour "
            "FROM element_set WHERE epoch_ms >= ? AND epoch_ms < ? "
            "ORDER BY norad, epoch_ms",
            oh.month_bounds(2009, 5),
        ).fetchall()
        oh.export_month(self.connection, 2009, 5, oh.shard_path(self.cold, 2009, 5))
        self.assertEqual(oh.read_cold_month(self.cold, 2009, 5), held)

    def test_a_month_with_no_shard_reads_as_none_not_as_empty(self) -> None:
        self.assertIsNone(oh.read_cold_month(self.cold, 2009, 4))

    def test_an_object_reads_the_same_from_cold_as_it_did_from_tier_one(self) -> None:
        start_ms, end_ms = oh.month_bounds(2009, 5)
        hot = oh.series(self.connection, 25544)
        oh.export_month(self.connection, 2009, 5, oh.shard_path(self.cold, 2009, 5))
        oh.prune_hot(self.connection, end_ms, force=True)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0], 0
        )
        cold = oh.cold_series(self.cold, 25544, start_ms=start_ms, end_ms=end_ms - 1)
        self.assertEqual(cold, hot)

    def test_a_cold_read_spanning_months_only_returns_the_object_asked_for(self) -> None:
        oh.export_month(self.connection, 2009, 5, oh.shard_path(self.cold, 2009, 5))
        start_ms = oh.month_bounds(2009, 1)[0]
        end_ms = oh.month_bounds(2009, 12)[1] - 1
        found = oh.cold_series(self.cold, 48274, start_ms=start_ms, end_ms=end_ms)
        self.assertEqual({element.norad for element in found}, {48274})
        self.assertEqual(len(found), 40)
        self.assertEqual(
            [element.epoch_ms for element in found],
            sorted(element.epoch_ms for element in found),
        )


if __name__ == "__main__":
    unittest.main()
