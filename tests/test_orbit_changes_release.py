#!/usr/bin/env python3
"""The Orbit changes release step, on an archive small enough to reason about.

Every assertion here is about a property the section depends on and cannot
check for itself at run time:

* the artifacts are a pure function of their inputs, so two runs produce the
  same bytes and therefore the same content-addressed names;
* the registered filters are the studies' own, so an unregistered row cannot
  reach a public list by being in the same file as a registered one;
* no artifact carries a field the section is not allowed to print -- a registry
  code, a country, a velocity change, a separation in kilometres -- because an
  absent field cannot be printed by accident, and a present one eventually is;
* the resonance integration reproduces the stable points two registrations
  arrived at independently;
* an absent alert ledger produces a labelled gap and never a zero.

One test reads the real archive when it is on this machine, and says so in its
skip message when it is not: the reconstruction of the phase angle is checked
against the frozen record's own median for every campaign the archive covers.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
import statistics
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import orbit_changes_release as release  # noqa: E402
from pipeline.orbit_history import SCALE_ANGLE, SCALE_ECCENTRICITY, SCALE_MEAN_MOTION  # noqa: E402

DAY_MS = release.DAY_MS
T0 = 1_700_000_000_000          # a fixed instant; nothing here reads a clock
GEO_MEAN_MOTION = 1.0027379093  # one revolution per sidereal day


def _quantise(mean_motion, ecc, inc, raan, argp, mean_anomaly):
    return (
        int(round(mean_motion * SCALE_MEAN_MOTION)),
        int(round(ecc * SCALE_ECCENTRICITY)),
        int(round(inc * SCALE_ANGLE)),
        int(round(raan % 360.0 * SCALE_ANGLE)),
        int(round(argp % 360.0 * SCALE_ANGLE)),
        int(round(mean_anomaly % 360.0 * SCALE_ANGLE)),
    )


def build_fixture_archive(path: Path) -> None:
    """A handful of objects with the archive's real schema and nothing else."""
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE element_set (
            norad INTEGER NOT NULL, epoch_ms INTEGER NOT NULL,
            mean_motion_q INTEGER NOT NULL, eccentricity_q INTEGER NOT NULL,
            inclination_q INTEGER NOT NULL, raan_q INTEGER NOT NULL,
            arg_perigee_q INTEGER NOT NULL, mean_anomaly_q INTEGER NOT NULL,
            bstar_q INTEGER, ndot_q INTEGER, nddot_q INTEGER,
            rev_at_epoch INTEGER, ingest_hour INTEGER NOT NULL,
            PRIMARY KEY (norad, epoch_ms)
        ) WITHOUT ROWID;
        CREATE TABLE object (
            norad INTEGER PRIMARY KEY, name TEXT, object_id TEXT, object_type TEXT,
            rcs_size TEXT, country TEXT, launch_date TEXT,
            first_seen_ms INTEGER NOT NULL, last_seen_ms INTEGER NOT NULL
        );
        CREATE TABLE object_rollup (
            norad INTEGER PRIMARY KEY, rows INTEGER NOT NULL,
            min_epoch_ms INTEGER NOT NULL, max_epoch_ms INTEGER NOT NULL
        );
        """
    )

    def insert(norad, day, mean_motion, ecc, inc, raan, argp, mean_anomaly):
        epoch = T0 + day * DAY_MS
        db.execute(
            "INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,0)",
            (norad, epoch, *_quantise(mean_motion, ecc, inc, raan, argp, mean_anomaly)),
        )

    # 100: a stationed belt object. Mean motion exactly synchronous, so the
    # fitted drift rate is zero and it sits below the lane's own slot floor.
    # 200: the same, drifting east at a rate the floor excludes.
    # 300/400: a co-orbiting low-orbit pair, one a quarter of a revolution
    # behind the other, which is a phase angle a reader could compute by hand.
    for day in range(-200, 1):
        insert(100, day, GEO_MEAN_MOTION, 0.0002, 0.05, 10.0, 20.0, (30.0 + 360.0 * GEO_MEAN_MOTION * day))
        insert(200, day, GEO_MEAN_MOTION * 1.0002, 0.0003, 0.08, 50.0, 60.0, (70.0 + 360.0 * GEO_MEAN_MOTION * 1.0002 * day))
        insert(300, day, 15.2, 0.001, 51.6, 120.0, 90.0, (0.0 + 360.0 * 15.2 * day))
        insert(400, day, 15.2, 0.001, 51.6, 120.0, 90.0, (90.0 + 360.0 * 15.2 * day))
    # 200 raises its semi-major axis on day -100, which is the catalogued change.
    for day in range(1, 41):
        insert(200, day, GEO_MEAN_MOTION * 0.9995, 0.0003, 0.08, 50.0, 60.0,
               (70.0 + 360.0 * GEO_MEAN_MOTION * 0.9995 * day))

    for norad, name in ((100, "FIXTURE ALPHA"), (200, "FIXTURE BETA"),
                        (300, "FIXTURE GAMMA"), (400, "FIXTURE DELTA")):
        span = db.execute(
            "SELECT COUNT(*), MIN(epoch_ms), MAX(epoch_ms) FROM element_set WHERE norad = ?",
            (norad,),
        ).fetchone()
        db.execute("INSERT INTO object VALUES (?,?,?,?,?,?,?,?,?)",
                   (norad, name, f"{norad}-A", "PAYLOAD", "LARGE", "ZZ", "2000-01-01",
                    span[1], span[2]))
        db.execute("INSERT INTO object_rollup VALUES (?,?,?,?)", (norad, *span))
    db.commit()
    db.close()


FIXTURE_EVENTS_BUNDLE = {
    "generatedAt": "2026-09-22T10:50:18Z",
    "labelPolicy": {"manoeuvreLabelPermitted": False},
    "events": [
        {
            "eventKey": "200|2023-11-14T22:13:20Z|geo-east-west-keeping",
            "norad": 200,
            "name": "FIXTURE BETA",
            "regime": "GEO",
            "signature": "geo-east-west-keeping",
            "signatureLabel": "east-west keeping",
            "startAt": "2023-11-14T22:13:20Z",
            "endAt": "2023-11-15T22:13:20Z",
            "spanDays": 1.0,
            "confidence": "candidate",
            "expectationVerdict": "in-family",
            "controlBasis": "self-history",
            "deltaVMetresPerSecond": 12.5,
            "objectType": "PAYLOAD",
        },
        {
            "eventKey": "300|2023-11-14T22:13:20Z|inclination-change",
            "norad": 300,
            "name": "FIXTURE GAMMA",
            "regime": "LEO",
            "signature": "inclination-change",
            "signatureLabel": "plane change",
            "startAt": "2023-11-14T22:13:20Z",
            "endAt": "2023-11-15T22:13:20Z",
            "spanDays": 1.0,
            "confidence": "candidate",
            "expectationVerdict": "in-family",
            "controlBasis": "self-history",
            "deltaVMetresPerSecond": 44.0,
            "objectType": "PAYLOAD",
        },
    ],
}

# One registered row and one the registration excludes, in the same file, so
# that the filter is what decides and not the file.
FIXTURE_GEO_RECORD = [
    {"record": "provenance", "study": "fixture"},
    {
        "approacherNorad": 200, "targetNorad": 100,
        "approacherClass": "active", "attribution": "resolved",
        "approacherName": "FIXTURE BETA", "targetName": "FIXTURE ALPHA",
        "approacherCountry": "ZZ", "targetCountry": "ZZ", "sameCountry": True,
        "transferStartMs": T0 - 100 * DAY_MS,
        "arrivalMs": T0 - 60 * DAY_MS,
        "loiterEndMs": T0 - 20 * DAY_MS,
        "departureMs": T0 - 10 * DAY_MS,
        "arrivalIso": "2023-09-18T22:13:20Z",
        "transferDriftDegPerDay": 0.25,
        "departureDriftDegPerDay": -0.01,
        "loiterLongitudeDeg": 10.0,
        "loiterDays": 40.0,
        "medianSeparationDeg": 0.02,
        "closestSeparationKm": 14.7,
        "leadCausalDays": 30.0,
        "initiatingDriftChangeDegPerDay": 0.24,
    },
    {
        "approacherNorad": 300, "targetNorad": 400,
        "approacherClass": "passive", "attribution": "resolved",
        "arrivalIso": "2023-09-18T22:13:20Z",
        "transferStartMs": T0 - 100 * DAY_MS, "arrivalMs": T0 - 60 * DAY_MS,
    },
]

FIXTURE_LEO_RECORD = [
    {
        "armM": True, "armG": True, "corroborated": True,
        "approacher": 300, "target": 400,
        "approacherName": "FIXTURE GAMMA", "targetName": "FIXTURE DELTA",
        "approacherRegistry": "ZZ", "targetRegistry": "ZZ",
        "campaignStartMs": T0 - 120 * DAY_MS,
        "arrivalMs": T0 - 60 * DAY_MS,
        "endMs": T0 - 20 * DAY_MS,
        "departureMs": T0 - 15 * DAY_MS,
        "dwellDays": 40.0, "campaignDays": 60.0,
        "medianGammaDeg": 90.0, "closestGammaDeg": 89.9,
        "medianThetaDeg": 0.01,
        "phaseRateMaxDegPerDay": 0.5, "phaseRateFinalDegPerDay": 0.0,
        "leadCausalDays": 60.0, "meanAKm": 6871.0,
    },
    {"armM": False, "armG": True, "approacher": 100, "target": 200,
     "campaignStartMs": T0 - 120 * DAY_MS, "arrivalMs": T0 - 60 * DAY_MS, "endMs": T0},
]

# The real table, read from the artifact that measured it. A fixture copy would
# be a second source for a number whose whole point is that it has one.
MEASURED_ERROR = release.forward_error(json.loads(release.KINEMATIC_INPUTS.read_text()))


class Recorder:
    """A stand-in for the release writer that keeps the bytes instead of files."""

    def __init__(self) -> None:
        self.written: dict[str, Any] = {}

    def __call__(self, data_root: Path, prefix: str, value):
        import hashlib

        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        path = f"artifacts/{prefix}-{digest[:16]}.json"
        self.written[path] = value
        return path, digest


def run_build(archive: Path, recorder: Recorder, *, ledger: Path | None = None,
              replay_ledgers: dict[str, Path] | None = None,
              replay_receipt: Path | None = None):
    connection = release.open_readonly(archive)
    try:
        return release.build(
            connection,
            Path("/nonexistent"),
            recorder,
            generated_at="2026-09-22T10:50:18Z",
            events_bundle=FIXTURE_EVENTS_BUNDLE,
            geo_record=FIXTURE_GEO_RECORD,
            leo_record=FIXTURE_LEO_RECORD,
            model=json.loads(release.FROZEN_MODEL.read_text()),
            measured_error=MEASURED_ERROR,
            ledger_path=ledger or Path("/nonexistent/ledger.jsonl"),
            # The replay is injected so the default build's assertions are about
            # a fixture and not about a four-thousand-line record; one test
            # below reads the real one, which is the record the section ships.
            replay_ledgers={} if replay_ledgers is None else replay_ledgers,
            replay_receipt=replay_receipt or Path("/nonexistent/receipt.json"),
            now_ms=T0,
        )
    finally:
        connection.close()


class OrbitChangesReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temporary = tempfile.TemporaryDirectory()
        cls.archive = Path(cls._temporary.name) / "fixture.sqlite3"
        build_fixture_archive(cls.archive)
        cls.recorder = Recorder()
        cls.fragment = run_build(cls.archive, cls.recorder)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    # -- the artifacts are a function of their inputs -----------------------
    def test_two_runs_over_the_same_inputs_produce_the_same_bytes(self):
        again = Recorder()
        fragment = run_build(self.archive, again)
        self.assertEqual(self.fragment, fragment)
        self.assertEqual(sorted(self.recorder.written), sorted(again.written))

    def test_the_archive_is_opened_read_only(self):
        connection = release.open_readonly(self.archive)
        with self.assertRaises(sqlite3.OperationalError):
            connection.execute("DELETE FROM element_set")
        connection.close()

    # -- the registered filters decide, not the file ------------------------
    def test_only_registered_rows_reach_the_index(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        families = [row["family"] for row in index["changes"]]
        self.assertEqual(families.count("geoColocation"), 1)
        self.assertEqual(families.count("leoStation"), 1)
        self.assertEqual(families.count("catalogue"), 2)
        self.assertEqual(index["families"]["geoColocation"]["rows"], 1)
        self.assertEqual(index["families"]["leoStation"]["rows"], 1)

    def test_the_index_carries_the_shipped_label_permission_unchanged(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        self.assertIs(index["manoeuvreLabelPermitted"], False)

    def test_rows_are_newest_first_and_ordered_the_same_way_every_run(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        starts = [row["startMs"] for row in index["changes"]]
        self.assertEqual(starts, sorted(starts, reverse=True))
        # The ledger's own rows are episodes, newest by the moment they were
        # last seen, which is the order the tracker guarantees.
        updated = [row["updatedMs"] for row in index["rows"]]
        self.assertEqual(updated, sorted(updated, reverse=True))

    # -- what no artifact may carry -----------------------------------------
    def test_no_artifact_carries_a_field_the_section_may_not_print(self):
        banned = ("country", "registry", "deltav", "separationkm", "missdistance",
                  "propellant", "mass", "objectid", "theta")

        def walk(value, path):
            if isinstance(value, dict):
                for key, item in value.items():
                    lowered = key.lower()
                    for term in banned:
                        self.assertNotIn(term, lowered, f"{path}.{key} carries {term!r}")
                    walk(item, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]")

        for path, payload in self.recorder.written.items():
            walk(payload, path)

    def test_the_phasing_arm_publishes_phase_and_no_plane_separation(self):
        events = [payload for payload in self.recorder.written.values()
                  if isinstance(payload, dict) and payload.get("family") == "leoStation"]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertIn("phase", event)
        self.assertIn("medianPhaseDeg", event["facts"])
        self.assertNotIn("plane", json.dumps(event).lower())

    # -- the belt ------------------------------------------------------------
    def test_the_belt_flags_stationed_at_the_lane_own_floor(self):
        belt = self.recorder.written[self.fragment["belt"]["path"]]
        rows = {row["norad"]: row for row in belt["rows"]}
        self.assertIn(100, rows)
        self.assertIn(200, rows)
        self.assertTrue(rows[100]["stationed"])
        self.assertFalse(rows[200]["stationed"])
        self.assertGreater(abs(rows[200]["driftDegPerDay"]), belt["stationedDriftFloorDegPerDay"])
        self.assertLessEqual(abs(rows[100]["driftDegPerDay"]), belt["stationedDriftFloorDegPerDay"])
        self.assertEqual(rows[100]["name"], "FIXTURE ALPHA")
        self.assertEqual([row["longitudeDeg"] for row in belt["rows"]],
                         sorted(row["longitudeDeg"] for row in belt["rows"]))

    def test_the_belt_excludes_objects_that_are_not_near_the_belt(self):
        belt = self.recorder.written[self.fragment["belt"]["path"]]
        self.assertNotIn(300, {row["norad"] for row in belt["rows"]})

    # -- the resonance integration ------------------------------------------
    def test_the_integration_holds_both_registered_stable_points(self):
        model = json.loads(release.FROZEN_MODEL.read_text())
        acceleration = model["detector"]["lambdaDdotDegPerDay2"]
        stable = model["detector"]["lambdaStableDeg"]
        for point in (stable, stable - 180.0):
            path = release.forward_path(point, 0.0, 180.0, acceleration=acceleration,
                                        stable_deg=stable)
            self.assertAlmostEqual(path[-1], path[0], places=6)
        # The two the low-orbit study's sibling registered independently. The
        # agreement to 0.2 deg is the check that the single-harmonic form is the
        # right one; it is not a free parameter.
        from tools.proximity_geo import STABLE_LONGITUDES_DEG
        for registered, derived in zip(sorted(STABLE_LONGITUDES_DEG),
                                       sorted((stable, release.geo.wrap180(stable - 180.0).item()))):
            # Rounded because the difference is EXACTLY the 0.2 deg the
            # results quote, and in doubles that lands a few parts in 10^15
            # above it.
            self.assertLessEqual(round(abs(registered - derived), 6), 0.2)

    def test_a_displaced_object_librates_back_towards_the_stable_point(self):
        model = json.loads(release.FROZEN_MODEL.read_text())
        stable = model["detector"]["lambdaStableDeg"]
        path = release.forward_path(stable + 20.0, 0.0, 180.0,
                                    acceleration=model["detector"]["lambdaDdotDegPerDay2"],
                                    stable_deg=stable)
        self.assertLess(path[-1], path[0])
        self.assertGreater(path[-1], stable)

    def test_a_straight_line_would_be_wrong_by_the_quantity_the_design_names(self):
        # Half K H squared at 180 days, which the registration gives as 27.5 deg.
        model = json.loads(release.FROZEN_MODEL.read_text())
        acceleration = model["detector"]["lambdaDdotDegPerDay2"]
        omitted = 0.5 * acceleration * 180.0 ** 2
        self.assertAlmostEqual(omitted, 27.5, delta=0.5)

    # -- the labelled gaps ---------------------------------------------------
    def test_no_ledger_and_no_replay_is_a_labelled_gap_and_never_a_zero(self):
        alerts = self.recorder.written[self.fragment["alerts"]["path"]]
        self.assertIs(alerts["available"], False)
        self.assertIs(alerts["live"], False)
        self.assertEqual(alerts["gap"], "lane-not-running")
        self.assertIsNone(alerts["alerts"])
        self.assertIsNone(alerts["counts"])
        self.assertEqual(len(alerts["caveats"]), 2)

    def test_a_present_ledger_is_read_counted_and_marked_live(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "alarm-lane-ledger.jsonl"
            ledger.write_text(
                json.dumps({"record": "provenance", "setting": "everything"}) + "\n"
                + json.dumps({"record": "assessment", "alertId": "a", "spoken": True,
                              "assessable": True, "class": 1, "norad": 100,
                              "tTrigMs": T0 - 10 * DAY_MS}) + "\n"
                + json.dumps({"record": "assessment", "alertId": "b", "spoken": False,
                              "assessable": True, "class": 0, "norad": 100}) + "\n"
                + json.dumps({"record": "assessment", "alertId": "c", "spoken": False,
                              "assessable": False, "norad": 100}) + "\n"
                + json.dumps({"record": "resolution", "alertId": "a", "state": "arrival",
                              "leadDays": 12.0}) + "\n"
            )
            recorder = Recorder()
            fragment = run_build(self.archive, recorder, ledger=ledger)
            alerts = recorder.written[fragment["alerts"]["path"]]
        self.assertIs(alerts["available"], True)
        self.assertIs(alerts["live"], True)
        self.assertEqual(alerts["source"], "lane")
        self.assertEqual(alerts["counts"]["assessed"], 3)
        self.assertEqual(alerts["counts"]["notAssessable"], 1)
        self.assertEqual(alerts["counts"]["withheld"], 1)
        self.assertEqual(alerts["counts"]["raised"], 1)
        # The lane's own precision, counted from its resolutions: one alert
        # raised, one arrival. It is never the frozen figure and never replaces
        # it -- the page prints the pair.
        self.assertEqual(alerts["counts"]["runningPrecision"], 1.0)
        self.assertEqual(len(alerts["alerts"]), 1)

    # -- the replay, which is what there is to read today --------------------
    def test_the_replay_is_published_as_a_replay_and_never_as_a_live_lane(self):
        recorder = Recorder()
        fragment = run_build(self.archive, recorder,
                             replay_ledgers=release.REPLAY_LEDGERS,
                             replay_receipt=release.REPLAY_RECEIPT)
        alerts = recorder.written[fragment["alerts"]["path"]]
        self.assertIs(alerts["available"], True)
        # THE FIELD SAYS IT BEFORE ANY PROSE DOES. A page cannot draw this as
        # live without deleting something.
        self.assertIs(alerts["live"], False)
        self.assertEqual(alerts["source"], "replay")
        self.assertEqual(fragment["alerts"]["source"], "replay")
        self.assertIs(fragment["alerts"]["live"], False)
        exercise = alerts["exercise"]
        self.assertEqual(exercise["mode"], "injected")
        self.assertTrue(exercise["window"]["startIso"].startswith("2010"))
        self.assertTrue(exercise["window"]["endIso"].startswith("2020"))
        self.assertIn("SYNTHETIC EXERCISE", exercise["status"])
        self.assertEqual(sorted(exercise["ledgers"]), ["everything", "high-confidence"])

    def test_every_spoken_replay_row_is_published_and_none_is_summarised_away(self):
        recorder = Recorder()
        fragment = run_build(self.archive, recorder,
                             replay_ledgers=release.REPLAY_LEDGERS,
                             replay_receipt=release.REPLAY_RECEIPT)
        alerts = recorder.written[fragment["alerts"]["path"]]
        listed = alerts["listedSetting"]
        spoken = [row for row in release.read_jsonl(release.REPLAY_LEDGERS[listed])
                  if row.get("spoken") is True]
        self.assertEqual(len(alerts["alerts"]), len(spoken))
        self.assertEqual({row["alertId"] for row in alerts["alerts"]},
                         {row["alertId"] for row in spoken})
        for row in alerts["alerts"]:
            # The lane's own words, verbatim: the page composes nothing.
            self.assertTrue(row["text"])
            self.assertEqual(row["class"], 1)
            self.assertIsNotNone(row["driftChangeDegPerDay"])
            self.assertIsNotNone(row["stages"])
        # ...and the withheld rows are COUNTS, not rows: the artifact carries no
        # card for a change the lane did not speak.
        counts = alerts["counts"]
        self.assertGreater(counts["withheld"], 0)
        self.assertGreater(counts["notAssessable"], 0)
        self.assertEqual(counts["raised"], len(alerts["alerts"]))

    def test_the_lane_precision_is_counted_from_its_own_resolutions(self):
        recorder = Recorder()
        fragment = run_build(self.archive, recorder,
                             replay_ledgers=release.REPLAY_LEDGERS,
                             replay_receipt=release.REPLAY_RECEIPT)
        alerts = recorder.written[fragment["alerts"]["path"]]
        counts = alerts["counts"]
        # Counted here from the ledger, independently of the artifact.
        rows = release.read_jsonl(release.REPLAY_LEDGERS[alerts["listedSetting"]])
        spoken = {row["alertId"] for row in rows if row.get("spoken") is True}
        resolutions = [row for row in rows
                       if row.get("record") == "resolution" and row["alertId"] in spoken]
        arrivals = sum(1 for row in resolutions if row["state"] == "arrival")
        closed = sum(1 for row in resolutions if row["state"] in ("arrival", "none"))
        self.assertEqual(counts["runningPositives"], arrivals)
        self.assertEqual(counts["runningSupport"], closed)
        self.assertAlmostEqual(counts["runningPrecision"], arrivals / closed)
        # It is not the frozen figure, and the frozen figure is beside it.
        frozen = alerts["classFigures"]["1"]["precision"]
        self.assertNotAlmostEqual(counts["runningPrecision"], frozen, places=4)

    def test_the_low_orbit_arm_is_a_withheld_gate_with_the_number_that_withheld_it(self):
        alerts = self.recorder.written[self.fragment["alerts"]["path"]]
        leo = alerts["leo"]
        self.assertIs(leo["available"], False)
        self.assertEqual(leo["gate"], "withheld")
        # Never a zero on its own: the count of what it assessed travels with
        # the count of what it raised.
        self.assertEqual(leo["raised"], 0)
        self.assertGreater(leo["assessed"], 5000)
        self.assertGreater(leo["passiveControlRatio"], leo["passiveControlBar"])

    def test_the_dial_reads_every_number_from_the_operating_point_table(self):
        settings = self.recorder.written[self.fragment["settings"]["path"]]
        curve = json.loads(release.CURVE_PATH.read_text())
        self.assertEqual(settings["curveVersion"], curve["curveVersion"])
        self.assertEqual(settings["curveChecksum"], curve["checksum"])
        self.assertEqual([point["stop"] for point in settings["points"]],
                         [setting["name"] for setting in curve["namedSettings"]])
        for point, setting in zip(settings["points"], curve["namedSettings"]):
            row = next(entry for entry in setting["classes"]
                       if entry["className"] == "WIDE-CROSSING")
            self.assertEqual(point["precision"], row["precision"])
            self.assertEqual(point["wilson95"], list(row["wilson95"]))
            self.assertEqual(point["leadDays"]["p50"], row["leadDays"]["p50"])
            self.assertEqual(point["alertsPerYear"], row["alertsPerYear2010s"])
            self.assertEqual(point["support"], row["alerts"])
            self.assertEqual(point["source"], "operating-points")
        self.assertEqual(settings["defaultStop"], "everything")
        self.assertIsNone(settings["gap"])

    def test_a_tighter_stop_is_not_a_more_precise_one_and_the_table_says_so(self):
        # The uncomfortable measured fact, asserted here so that a future curve
        # which no longer says it cannot land quietly: the loosest setting has
        # the highest measured precision of the four.
        settings = self.recorder.written[self.fragment["settings"]["path"]]
        precisions = [point["precision"] for point in settings["points"]]
        self.assertEqual(max(precisions), precisions[0])
        self.assertLess(precisions[2], precisions[0])

    def test_an_underpowered_stop_is_not_offered(self):
        # No named setting of the shipped curve is underpowered, so the rule is
        # exercised against a seeded one: a row with fewer alerts than the bar a
        # rate may be quoted at comes back NOT offered, with its reason.
        curve = json.loads(release.CURVE_PATH.read_text())
        model = json.loads(release.FROZEN_MODEL.read_text())
        bar = model["bars"]["minSupportForARate"]
        seeded = next(entry for entry in curve["namedSettings"][1]["classes"]
                      if entry["className"] == "WIDE-CROSSING")
        seeded["alerts"] = bar - 1
        seeded["underpowered"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curve.json"
            path.write_text(json.dumps(curve))
            settings = release.settings_artifact(model, path)
        offered = {point["stop"]: point["offered"] for point in settings["points"]}
        self.assertIs(offered["everything"], True)
        self.assertIs(offered[curve["namedSettings"][1]["name"]], False)
        reason = next(point["notOfferedReason"] for point in settings["points"]
                      if point["stop"] == curve["namedSettings"][1]["name"])
        self.assertEqual(reason, "underpowered")

    # -- the element change --------------------------------------------------
    def test_the_catalogued_change_is_the_element_sets_either_side_of_it(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        row = next(entry for entry in index["changes"]
                   if entry["key"].startswith("200|"))
        self.assertEqual(row["changeUnit"], "degPerDay")
        # Beta's mean motion falls from 1.0002 to 0.9995 of synchronous, so the
        # drift rate falls by about 360 times the difference in revolutions.
        self.assertAlmostEqual(row["changeValue"], 360.0 * GEO_MEAN_MOTION * (0.9995 - 1.0002),
                               places=3)

    def test_an_event_file_travels_with_every_step_that_has_a_series(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        for row in index["changes"]:
            if row["key"].startswith(("geo|", "leo|")):
                self.assertIsNotNone(row["event"], row["key"])
                self.assertIn(row["event"], self.recorder.written)
        self.assertEqual(len(self.fragment["events"]),
                         sum(1 for row in index["changes"] if row["event"]))

    def test_the_ledger_rows_are_episodes_and_the_steps_name_them(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        keys = {row["key"] for row in index["rows"]}
        self.assertTrue(keys)
        # Every step belongs to exactly one episode, and the join is one-way:
        # the step carries the episode's key and the episode lists no steps,
        # so the long keys are stored once.
        opened = 0
        for step in index["changes"]:
            if step["episodeId"] is None:
                continue
            opened += 1
            self.assertIn(step["episodeId"], keys)
        self.assertGreater(opened, 0)
        # A step that opened nothing is counted, never dropped and never given
        # a row of its own: routine keeping must not open an episode, and the
        # fixture's east-west keeping cycle is exactly that case.
        self.assertEqual(index["stepsWithoutEpisode"],
                         sum(1 for step in index["changes"] if step["episodeId"] is None))
        self.assertGreater(index["stepsWithoutEpisode"], 0)
        for row in index["rows"]:
            self.assertIsNone(row["steps"])
            self.assertIn(row["state"], ("INITIATED", "IN PROGRESS", "COMPLETED"))
            self.assertIn(row["closure"], ("open", "settled", "lapsed"))

    def test_a_ledger_row_carries_only_the_state_its_delta_line_draws(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        allowed = {"semiMajorAxisKm", "inclinationDeg", "lambdaDeg", "driftDegPerDay"}
        for row in index["rows"]:
            for side in ("initial", "current"):
                state = row[side]
                if state is None:
                    continue
                self.assertTrue(set(state) <= allowed, f"{row['key']} {side}: {sorted(state)}")

    def test_the_state_rates_themselves_are_declared_unmeasured(self):
        index = self.recorder.written[self.fragment["index"]["path"]]
        self.assertIs(index["stateRatesMeasured"], False)
        self.assertTrue(index["trackerVersion"])
        for row in index["rows"]:
            self.assertIsNone(row["reading"])

    def test_the_forward_path_is_anchored_on_an_observed_coordinate(self):
        event = next(payload for payload in self.recorder.written.values()
                     if isinstance(payload, dict) and payload.get("family") == "geoColocation")
        forward = event["forward"]
        self.assertEqual(forward["anchor"], "event")
        self.assertEqual(len(forward["values"]), int(round(forward["horizonDays"])) + 1)
        slot = (forward["fromMs"] - event["series"]["startMs"]) // DAY_MS
        self.assertEqual(event["series"]["values"][slot], forward["values"][0])

    def test_the_path_stops_where_membership_was_measured_and_the_band_does_not(self):
        event = next(payload for payload in self.recorder.written.values()
                     if isinstance(payload, dict) and payload.get("family") == "geoColocation")
        measured = event["measuredError"]
        forward = event["forward"]
        # M1 cut the design's horizon: membership is resolvable to +20 d and an
        # arrival time to co-location precision only to +10 d, so the DRAWN path
        # stops at 20 even though the class's arrivals run to 90.
        self.assertEqual(measured["membershipHorizonDays"], 20)
        self.assertEqual(measured["precisionHorizonDays"], 10)
        self.assertEqual(forward["horizonDays"], 20)
        self.assertEqual(len(forward["values"]), 21)
        self.assertGreater(forward["classArrivalP95Days"], forward["horizonDays"])
        # The band's centres run to the last horizon that WAS measured, because
        # what the band shows there is true and is the point: it grows past the
        # objects it is drawn among.
        self.assertEqual(forward["bandHorizonDays"], 180)
        self.assertEqual(len(forward["bandCentres"]), 181)
        self.assertEqual(measured["unfitHorizonDays"], 180)
        self.assertGreater(measured["byHorizon"]["180"]["p50Deg"], measured["unfitBarDeg"])
        # ...and by then it is wider than the belt's own measured slot spacing.
        self.assertGreater(measured["byHorizon"]["180"]["p50Deg"], measured["slotSpacingP50Deg"])


class RecordExtentTest(unittest.TestCase):
    """THE RECORD CANNOT RUN PAST THE MOMENT IT WAS BUILT.

    The ledger header prints `recordToMs`; `recordToMs` is the largest
    `updatedMs` on any episode; and an episode that is still open takes the
    build's `now_ms` as its `updatedMs` by construction. So the whole chain
    rests on `now_ms`, and `now_ms` defaulted to `MAX(max_epoch_ms)` over the
    rollup -- which a forward-dated element set carries into the future. On
    2026-09-22 ten of the archive's 68,089 objects held an epoch the clock had
    not reached, the furthest 2026-09-26, and the header read "Record to 24 Sep
    2026" on 22 Sep 2026.

    This is the one class in this file that reads the clock, because a date in
    the future is only a defect with respect to one.
    """

    @classmethod
    def setUpClass(cls):
        cls._temporary = tempfile.TemporaryDirectory()
        cls.archive = Path(cls._temporary.name) / "forward-dated.sqlite3"
        build_fixture_archive(cls.archive)
        cls.clock = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        # One element set issued four days AHEAD of the clock, which is the
        # shape the real archive had and the input that produced the header.
        cls.ahead = cls.clock + 4 * DAY_MS
        db = sqlite3.connect(cls.archive)
        db.execute(
            "INSERT INTO element_set VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,0)",
            (100, cls.ahead, *_quantise(GEO_MEAN_MOTION, 0.0002, 0.05, 10.0, 20.0, 30.0)),
        )
        db.execute("UPDATE object_rollup SET max_epoch_ms = ? WHERE norad = 100", (cls.ahead,))
        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_the_fixture_actually_carries_the_epoch_that_caused_this(self):
        # Without this the tests below could pass on an archive that never had
        # the defect in it, which is how a regression test dies quietly.
        connection = release.open_readonly(self.archive)
        try:
            naive = connection.execute("SELECT MAX(max_epoch_ms) FROM object_rollup").fetchone()[0]
        finally:
            connection.close()
        self.assertGreater(naive, self.clock)

    def test_the_present_is_the_newest_epoch_the_clock_has_reached(self):
        # Pure: the clock is injected, so this assertion is about the archive.
        connection = release.open_readonly(self.archive)
        try:
            present = release.archive_present(connection, clock_ms=T0 + 20 * DAY_MS)
            reached = connection.execute(
                "SELECT MAX(max_epoch_ms) FROM object_rollup WHERE max_epoch_ms <= ?",
                (T0 + 20 * DAY_MS,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(present, reached)
        self.assertLessEqual(present, T0 + 20 * DAY_MS)

    def test_the_record_to_date_is_never_past_the_newest_element_set_behind_it(self):
        recorder = Recorder()
        # AN EPISODE THAT IS STILL OPEN IS THE ONE THAT CARRIES `now_ms` ONTO
        # THE HEADER, so the record under test has one: a co-location that has
        # arrived and not yet departed as of the clock. A fixture of settled
        # episodes cannot reproduce this defect, and a test that cannot
        # reproduce it is not guarding against it.
        geo_record = [dict(row) for row in FIXTURE_GEO_RECORD]
        geo_record[1]["departureMs"] = self.clock + 10 * DAY_MS
        geo_record[1]["loiterEndMs"] = self.clock + 10 * DAY_MS
        connection = release.open_readonly(self.archive)
        try:
            # `now_ms` is NOT passed: the default is the path that was wrong, so
            # the default is the path under test.
            fragment = release.build(
                connection,
                Path("/nonexistent"),
                recorder,
                generated_at="2026-09-22T10:50:18Z",
                events_bundle=FIXTURE_EVENTS_BUNDLE,
                geo_record=geo_record,
                leo_record=FIXTURE_LEO_RECORD,
                model=json.loads(release.FROZEN_MODEL.read_text()),
                measured_error=MEASURED_ERROR,
                ledger_path=Path("/nonexistent/ledger.jsonl"),
                replay_ledgers={},
                replay_receipt=Path("/nonexistent/receipt.json"),
            )
            newest_reached = connection.execute(
                "SELECT MAX(epoch_ms) FROM element_set WHERE epoch_ms <= ?", (self.clock,)
            ).fetchone()[0]
        finally:
            connection.close()
        index = recorder.written[fragment["index"]["path"]]
        self.assertIsNotNone(index["recordToMs"])
        self.assertTrue(any(row["closure"] == "open" for row in index["rows"]),
                        "the fixture opened no episode, so nothing carries the present moment")
        # The record runs to the newest element set the clock has reached, and
        # no further: not to the forward-dated one, and not to the clock itself.
        self.assertLessEqual(index["recordToMs"], newest_reached)
        self.assertLess(index["recordToMs"], self.ahead)
        # ...and no episode row the header is computed from breaks the bound
        # either, so a future date cannot arrive through a row it did not pick.
        for row in index["rows"]:
            self.assertLessEqual(row["updatedMs"], newest_reached, row["key"])


class MeasuredErrorSourceTest(unittest.TestCase):
    def test_the_ribbon_reads_its_numbers_out_of_the_artifact_that_measured_them(self):
        measured = release.forward_error(json.loads(release.KINEMATIC_INPUTS.read_text()))
        # The published +30 d figures, still where they were, now beside the
        # nine other horizons the same method measured.
        self.assertAlmostEqual(measured["byHorizon"]["30"]["p50Deg"], 0.408, places=3)
        self.assertAlmostEqual(measured["byHorizon"]["30"]["p95Deg"], 2.080, places=3)
        self.assertEqual(measured["byHorizon"]["30"]["n"], 49318)
        self.assertEqual(measured["publishedP50Deg"], 0.408)
        # The error grows with the horizon, at every percentile, monotonically.
        horizons = sorted(int(key) for key in measured["byHorizon"])
        for lower, higher in zip(horizons, horizons[1:]):
            for percentile in ("p50Deg", "p75Deg", "p95Deg"):
                self.assertLess(measured["byHorizon"][str(lower)][percentile],
                                measured["byHorizon"][str(higher)][percentile])

    def test_it_refuses_the_table_when_the_reproduction_check_did_not_pass(self):
        inputs = json.loads(release.KINEMATIC_INPUTS.read_text())
        inputs["M1"]["gateK1Reproduction"]["passed"] = False
        with self.assertRaises(SystemExit):
            release.forward_error(inputs)

    def test_the_published_thirty_day_row_is_still_in_the_results_it_came_from(self):
        measured = release.gate_w_error(release.TRIGGER_RESULTS.read_text())
        self.assertEqual(measured["p50Deg"], 0.408)
        self.assertEqual(measured["support"], 49318)


class PhaseReconstructionTest(unittest.TestCase):
    """The phase series against the frozen record that measured it.

    The archive is thirteen gigabytes and lives on one machine, so this skips
    where it is absent and says which check did not run.
    """

    def setUp(self):
        from pipeline.orbit_history import archive_db_path

        self.archive = archive_db_path()
        if not self.archive.is_file():
            self.skipTest(f"the orbit archive is not on this machine ({self.archive}); "
                          "the phase reconstruction is UNCHECKED here")

    def test_the_reconstruction_agrees_with_the_record_it_is_drawn_against(self):
        connection = release.open_readonly(self.archive)
        registered = [row for row in release.read_jsonl(release.LEO_RECORD) if row.get("armM")]
        differences = []
        uncovered = 0
        for record in registered:
            series = release.phase_series(connection, int(record["approacher"]),
                                          int(record["target"]), int(record["campaignStartMs"]))
            low, high = int(record["arrivalMs"]), int(record["endMs"])
            inside = [value for index, value in enumerate(series["values"])
                      if value is not None and low <= series["startMs"] + index * DAY_MS <= high]
            if not inside:
                uncovered += 1
                continue
            differences.append(abs(statistics.median(inside) - record["medianGammaDeg"]))
        connection.close()
        self.assertGreaterEqual(len(differences), 45,
                                "too few campaigns have archive coverage to check the reconstruction")
        # The study's own phase arm is 5 deg wide. Measured on 2026-09-22 the
        # worst disagreement over the covered campaigns was 0.395 deg and the
        # median was 0.005 deg, so half a degree is a bar with room in it rather
        # than one drawn around the result.
        self.assertLessEqual(max(differences), 0.5)
        self.assertLessEqual(statistics.median(differences), 0.05)
        # Campaigns the archive does not cover in their dwell window are a real
        # and reportable state: their series is holes, and the section draws a
        # labelled gap rather than a flat line.
        self.assertLess(uncovered, len(registered))


if __name__ == "__main__":
    unittest.main()
