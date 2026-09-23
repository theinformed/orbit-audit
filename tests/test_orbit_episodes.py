#!/usr/bin/env python3
"""The change-episode tracker, on element series small enough to reason about.

Six fixtures, one per row of the design's build table, and each one exists
because the rule it covers can be got wrong in a way that still looks like a
working ledger:

* a relocation must pass INITIATED -> IN PROGRESS -> COMPLETED, and it is the
  ORDER that carries the meaning: a tracker that jumps straight to completed
  tells a reader the object has settled while it is still moving;
* a staged transfer that pauses long enough for the dwell to elapse must
  RE-OPEN rather than leave two episodes, because two episodes for one journey
  is a count nobody can use and a false completion nobody can see;
* a continuous raise must stay IN PROGRESS for as long as the climb lasts,
  which is the whole of what the operator asked for;
* keeping near the belt must OPEN NOTHING -- it is the baseline an episode
  departs from, and a ledger that lists it lists every satellite every
  fortnight;
* a sustained fall must OPEN NOTHING, because that is what the atmosphere does
  and no instrument in this programme separates it from a slow retrograde burn;
* an object that stops being tracked must LAPSE and must never be promoted to
  completed, because an empty window is not a settled orbit.

Every series here is synthetic and built in this file. Nothing reads the
archive, so the whole suite runs in under a second.
"""

from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import orbit_episodes as ep  # noqa: E402
from pipeline.orbit_history import semi_major_axis_km  # noqa: E402
from tools import proximity_geo as pg  # noqa: E402

DAY_MS = ep.DAY_MS
T0 = 1_600_000_000_000          # a fixed instant; nothing here reads a clock
OMEGA_E = pg.OMEGA_E_DEG_PER_DAY
MU_KM3_S2 = 398600.4418


def _at(day: float) -> int:
    return int(T0 + day * DAY_MS)


def _mean_motion_for_axis(axis_km: float) -> float:
    """Revolutions per day for a semi-major axis, the inverse of the reader."""
    seconds = 2.0 * math.pi * math.sqrt(axis_km ** 3 / MU_KM3_S2)
    return 86400.0 / seconds


def geo_elements(profile, cadence_days: float = 1.0) -> dict[str, np.ndarray]:
    """A near-belt series whose slot coordinate follows `profile(day)`.

    `profile` returns `(lambda_deg, drift_deg_per_day)`. Mean motion is set
    from the drift, and the mean anomaly is set so the instrument's own
    `mean_longitude_deg` reproduces the requested coordinate exactly. The two
    therefore agree by construction, which is what lets the station segmenter
    and the drift test be exercised on the same fixture.
    """
    days = np.arange(profile.low, profile.high + cadence_days / 2.0, cadence_days)
    epoch_ms = np.asarray([_at(day) for day in days], dtype=np.float64)
    lam = np.asarray([profile.lam(day) for day in days], dtype=np.float64)
    drift = np.asarray([profile.drift(day) for day in days], dtype=np.float64)
    gmst = pg.gmst_deg(epoch_ms)
    return {
        "epochMs": epoch_ms,
        "meanMotion": (OMEGA_E + drift) / 360.0,
        "eccentricity": np.full(days.size, 2.0e-4),
        "inclination": np.full(days.size, 0.05),
        "raan": np.zeros(days.size),
        "argPerigee": np.zeros(days.size),
        "meanAnomaly": np.mod(lam + gmst, 360.0),
    }


class GeoProfile:
    def __init__(self, low: float, high: float, segments):
        self.low, self.high = low, high
        self.segments = segments          # [(from_day, drift_deg_per_day)]

    def drift(self, day: float) -> float:
        rate = 0.0
        for start, value in self.segments:
            if day >= start:
                rate = value
        return rate

    def lam(self, day: float) -> float:
        """The coordinate reached by integrating the drift from the opening."""
        value = 10.0
        step = 0.25
        here = self.low
        while here < day - 1e-9:
            span = min(step, day - here)
            value += self.drift(here) * span
            here += span
        return value


def outside_elements(
    axis_of_day, low: float, high: float, cadence_days: float = 0.5,
    inclination_deg: float = 51.6, eccentricity: float = 1.0e-3,
) -> dict[str, np.ndarray]:
    days = np.arange(low, high + cadence_days / 2.0, cadence_days)
    epoch_ms = np.asarray([_at(day) for day in days], dtype=np.float64)
    axis = np.asarray([axis_of_day(day) for day in days], dtype=np.float64)
    return {
        "epochMs": epoch_ms,
        "meanMotion": np.asarray([_mean_motion_for_axis(value) for value in axis]),
        "eccentricity": np.full(days.size, eccentricity),
        "inclination": np.full(days.size, inclination_deg),
        "raan": np.full(days.size, 120.0),
        "argPerigee": np.full(days.size, 90.0),
        "meanAnomaly": np.mod(np.arange(days.size) * 37.0, 360.0),
    }


def reader(bundles: dict[int, dict[str, np.ndarray]]):
    """An `elements` callable over fixed arrays, clipped to the asked window."""
    def read(norad: int, low_ms: int, high_ms: int) -> dict[str, np.ndarray]:
        bundle = bundles.get(int(norad))
        if bundle is None:
            return {name: np.zeros(0) for name in
                    ("epochMs", "meanMotion", "eccentricity", "inclination",
                     "raan", "argPerigee", "meanAnomaly")}
        inside = (bundle["epochMs"] >= low_ms) & (bundle["epochMs"] <= high_ms)
        return {name: values[inside] for name, values in bundle.items()}
    return read


def newest(bundles: dict[int, dict[str, np.ndarray]]):
    def read(norad: int) -> int | None:
        bundle = bundles.get(int(norad))
        if bundle is None or bundle["epochMs"].size == 0:
            return None
        return int(bundle["epochMs"][-1])
    return read


def catalogue_step(norad: int, day: float, signature: str, regime: str,
                   name: str = "FIXTURE", span_days: float = 1.0) -> dict:
    import datetime as dt

    def iso(value: float) -> str:
        moment = dt.datetime.fromtimestamp(_at(value) / 1000.0, tz=dt.timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "eventKey": f"{norad}|{iso(day)}|{signature}",
        "norad": norad,
        "name": name,
        "regime": regime,
        "signature": signature,
        "signatureLabel": signature.replace("-", " "),
        "startAt": iso(day),
        "endAt": iso(day + span_days),
        "confidence": "candidate",
    }


def run(*, now_day: float, events=(), bundles=None, sustained=None, geo=(), leo=()):
    bundles = bundles or {}
    return ep.episodes(
        now_ms=_at(now_day),
        catalogue_events=list(events),
        geo_record=list(geo),
        leo_record=list(leo),
        elements=reader(bundles),
        newest_epoch=newest(bundles),
        sustained=sustained,
    )


# ---------------------------------------------------------------------------
# 1. An impulsive relocation near the belt
# ---------------------------------------------------------------------------
RELOCATION = GeoProfile(low=-60.0, high=200.0,
                        segments=[(-60.0, 0.0), (2.0, 0.25), (82.0, 0.0)])


class RelocationTest(unittest.TestCase):
    """INITIATED -> IN PROGRESS -> COMPLETED, in that order, on one series."""

    def setUp(self):
        self.bundles = {700: geo_elements(RELOCATION)}
        self.events = [catalogue_step(700, 0.0, "along-track-raise", "GEO")]

    def episode(self, now_day: float):
        found = run(now_day=now_day, events=self.events, bundles=self.bundles)
        self.assertEqual(len(found), 1, f"expected one episode at day {now_day}")
        return found[0]

    def test_it_is_initiated_before_the_orbit_has_carried_it_anywhere(self):
        episode = self.episode(1.0)
        self.assertEqual(episode["state"], "INITIATED")
        self.assertIsNone(episode["completedMs"])
        self.assertFalse(episode["trend"]["trending"])

    def test_it_is_in_progress_while_the_drift_is_outside_the_stationed_band(self):
        episode = self.episode(40.0)
        self.assertEqual(episode["state"], "IN PROGRESS")
        self.assertTrue(episode["trend"]["trending"])
        self.assertIsNone(episode["completedMs"])
        self.assertEqual(episode["closure"], "open")

    def test_it_completes_only_once_a_new_station_has_formed(self):
        episode = self.episode(180.0)
        self.assertEqual(episode["state"], "COMPLETED")
        self.assertEqual(episode["closure"], "settled")
        self.assertIsNotNone(episode["completedMs"])
        self.assertGreater(episode["completedMs"], _at(82.0))

    def test_the_current_state_moves_while_the_initial_one_does_not(self):
        early, late = self.episode(40.0), self.episode(70.0)
        self.assertEqual(early["initial"], late["initial"])
        self.assertNotEqual(early["current"]["lambdaDeg"], late["current"]["lambdaDeg"])

    def test_the_record_names_the_rules_that_produced_it(self):
        episode = self.episode(40.0)
        self.assertEqual(episode["versions"]["trackerVersion"], ep.TRACKER_VERSION)
        self.assertEqual(episode["versions"]["episodeSchema"], ep.EPISODE_SCHEMA)


# ---------------------------------------------------------------------------
# 2. A staged transfer that pauses long enough to look settled
# ---------------------------------------------------------------------------
def staged_axis(day: float) -> float:
    base = 7000.0
    if day < 0.0:
        return base
    if day < 10.0:
        return base + 0.4 * day
    if day < 100.0:
        return base + 4.0
    return base + 4.0 + 0.4 * (day - 100.0)


class StagedTransferTest(unittest.TestCase):
    """A pause inside the campaign window re-opens the episode, it does not end it."""

    def setUp(self):
        self.bundles = {701: outside_elements(staged_axis, -20.0, 140.0)}
        self.events = [
            catalogue_step(701, 0.0, "along-track-raise", "LEO"),
            catalogue_step(701, 100.0, "along-track-raise", "LEO"),
        ]

    def test_one_journey_is_one_episode_and_the_pause_is_counted(self):
        found = run(now_day=130.0, events=self.events, bundles=self.bundles)
        self.assertEqual(len(found), 1, "a pause must not split one journey in two")
        episode = found[0]
        self.assertEqual(episode["reopened"], 1)
        self.assertEqual(episode["state"], "IN PROGRESS")
        self.assertIsNone(episode["completedMs"])
        self.assertEqual(episode["closure"], "open")
        self.assertEqual([step["epochMs"] for step in episode["steps"]],
                         [_at(0.0), _at(100.0)])

    def test_it_reads_as_settled_while_the_pause_is_all_there_is(self):
        found = run(now_day=60.0, events=self.events[:1], bundles=self.bundles)
        self.assertEqual(found[0]["state"], "COMPLETED")
        self.assertEqual(found[0]["reopened"], 0)


# ---------------------------------------------------------------------------
# 3. A continuous raise
# ---------------------------------------------------------------------------
class ContinuousRaiseTest(unittest.TestCase):
    """A climb with no step to open on stays in progress for the whole climb."""

    def setUp(self):
        self.bundles = {702: outside_elements(lambda day: 6900.0 + 0.06 * max(day, 0.0),
                                              -1.0, 30.0)}

    def test_it_opens_and_stays_in_progress_across_six_blocks(self):
        found = run(now_day=30.0, bundles=self.bundles, sustained={702: True})
        self.assertEqual(len(found), 1)
        episode = found[0]
        self.assertEqual(episode["kind"], "continuous")
        self.assertEqual(episode["state"], "IN PROGRESS")
        self.assertTrue(episode["trend"]["trending"])
        self.assertEqual(episode["trend"]["test"], "block-slope")
        self.assertGreater(episode["current"]["semiMajorAxisKm"],
                           episode["initial"]["semiMajorAxisKm"])

    def test_no_verdict_means_no_episode_rather_than_a_guess(self):
        self.assertEqual(run(now_day=30.0, bundles=self.bundles), [])
        self.assertEqual(run(now_day=30.0, bundles=self.bundles, sustained={702: False}), [])


# ---------------------------------------------------------------------------
# 4. Keeping near the belt
# ---------------------------------------------------------------------------
KEEPING = GeoProfile(low=-60.0, high=120.0,
                     segments=[(-60.0, 0.0), (0.0, 0.004), (7.0, -0.004), (14.0, 0.004)])


class KeepingOpensNothingTest(unittest.TestCase):
    """A satellite holding its own slot is the baseline, not an episode."""

    def test_an_east_west_keeping_cycle_opens_nothing(self):
        bundles = {703: geo_elements(KEEPING)}
        events = [catalogue_step(703, day, "geo-east-west-keeping", "GEO")
                  for day in (0.0, 14.0, 28.0, 42.0)]
        self.assertEqual(run(now_day=90.0, events=events, bundles=bundles), [])

    def test_a_north_south_keeping_cycle_opens_nothing_either(self):
        bundles = {704: geo_elements(KEEPING)}
        events = [catalogue_step(704, 0.0, "geo-north-south-keeping", "GEO")]
        self.assertEqual(run(now_day=90.0, events=events, bundles=bundles), [])


# ---------------------------------------------------------------------------
# 5. A sustained fall
# ---------------------------------------------------------------------------
class SustainedFallOpensNothingTest(unittest.TestCase):
    """What the atmosphere does is not a change this record claims."""

    def test_a_decaying_orbit_opens_nothing(self):
        bundles = {705: outside_elements(lambda day: 6700.0 - 0.09 * max(day, 0.0),
                                         -1.0, 40.0)}
        events = [catalogue_step(705, 0.0, "drag-decay", "LEO")]
        self.assertEqual(run(now_day=40.0, events=events, bundles=bundles), [])

    def test_an_orbit_the_instruments_cannot_separate_opens_nothing(self):
        bundles = {706: outside_elements(lambda day: 6700.0 - 0.09 * max(day, 0.0),
                                         -1.0, 40.0)}
        events = [catalogue_step(706, 0.0, "drag-and-thrust-not-separable", "LEO")]
        self.assertEqual(run(now_day=40.0, events=events, bundles=bundles), [])


# ---------------------------------------------------------------------------
# 6. A tracking lapse
# ---------------------------------------------------------------------------
class TrackingLapseTest(unittest.TestCase):
    """An empty window is not a settled orbit."""

    def setUp(self):
        # The elements stop ten days after the opening; the dwell would have
        # elapsed at day fifteen on a window with nothing in it.
        self.bundles = {707: outside_elements(
            lambda day: 7100.0 + (0.6 * day if 0.0 <= day < 5.0 else (3.0 if day >= 5.0 else 0.0)),
            -20.0, 10.0)}
        self.events = [catalogue_step(707, 0.0, "along-track-raise", "LEO")]

    def test_the_episode_lapses_and_is_never_promoted_to_completed(self):
        found = run(now_day=40.0, events=self.events, bundles=self.bundles)
        self.assertEqual(len(found), 1)
        episode = found[0]
        self.assertEqual(episode["closure"], "lapsed")
        self.assertNotEqual(episode["state"], "COMPLETED")
        self.assertIsNone(episode["completedMs"])

    def test_it_keeps_the_state_it_reached(self):
        episode = run(now_day=40.0, events=self.events, bundles=self.bundles)[0]
        self.assertIn(episode["state"], ("INITIATED", "IN PROGRESS"))


# ---------------------------------------------------------------------------
# The registered records, and the properties the release step depends on
# ---------------------------------------------------------------------------
GEO_ROW = {
    "approacherNorad": 800, "targetNorad": 801,
    "approacherName": "FIXTURE MOVER", "targetName": "FIXTURE HELD",
    "approacherClass": "active", "attribution": "resolved",
    "approacherCountry": "ZZ", "targetCountry": "ZZ",
    "transferStartMs": _at(-40.0), "initiatingFlagMs": _at(-45.0),
    "arrivalMs": _at(0.0), "loiterEndMs": _at(40.0), "departureMs": _at(50.0),
    "arrivalIso": "2020-09-13T12:26:40Z",
    "initiatingDriftChangeDegPerDay": 0.24,
    "departureDriftDegPerDay": -0.01, "loiterLongitudeDeg": 10.0, "loiterDays": 40.0,
}

LEO_ROW = {
    "armM": True, "approacher": 810, "target": 811,
    "approacherName": "FIXTURE PHASER", "targetName": "FIXTURE PARTNER",
    "approacherRegistry": "ZZ",
    "campaignStartMs": _at(-120.0), "initiatingConfirmMs": _at(-118.0),
    "arrivalMs": _at(-60.0), "endMs": _at(-20.0),
}


class RegisteredRecordTest(unittest.TestCase):
    def test_a_registered_co_location_is_a_completed_episode_with_its_partner(self):
        found = run(now_day=100.0, geo=[GEO_ROW])
        self.assertEqual(len(found), 1)
        episode = found[0]
        self.assertEqual(episode["state"], "COMPLETED")
        self.assertEqual(episode["closure"], "settled")
        self.assertEqual(episode["partnerNorad"], 801)
        self.assertEqual(episode["kind"], "impulsive")

    def test_an_arrival_with_no_confirmed_opening_says_so(self):
        row = dict(GEO_ROW)
        row["initiatingFlagMs"] = None
        episode = run(now_day=100.0, geo=[row])[0]
        self.assertEqual(episode["kind"], "not-observed-onset")
        self.assertIsNone(episode["initial"])

    def test_a_registered_phasing_campaign_is_a_completed_episode(self):
        episode = run(now_day=100.0, leo=[LEO_ROW])[0]
        self.assertEqual(episode["state"], "COMPLETED")
        self.assertEqual(episode["kind"], "campaign")
        self.assertEqual(episode["partnerNorad"], 811)

    def test_nothing_after_the_injected_moment_is_ever_visible(self):
        self.assertEqual(run(now_day=-200.0, geo=[GEO_ROW], leo=[LEO_ROW]), [])

    def test_no_record_carries_a_country_or_a_registry_code(self):
        found = run(now_day=100.0, geo=[GEO_ROW], leo=[LEO_ROW])
        self.assertTrue(found)
        import json
        for episode in found:
            text = json.dumps(episode)
            self.assertNotIn("ountry", text)
            self.assertNotIn("egistry", text)
            self.assertNotIn("ZZ", text)


class ReadingTest(unittest.TestCase):
    """Slots and gaps, never a sentence, and never a number nobody measured."""

    FIGURES = {"k": 28, "n": 822, "precisionPercent": "3.4",
               "wilsonLo": "2.4", "wilsonHi": "4.9", "horizonDays": 90,
               "artifact": "docs/alarm-lane-model-20260922.json",
               "version": "trigger-time-taxonomy/20260922/1", "checksum": "9cf012aa"}

    def test_every_clause_is_a_labelled_gap_until_its_measurement_lands(self):
        episode = run(now_day=100.0, geo=[GEO_ROW])[0]
        reading = episode["reading"]
        self.assertFalse(reading["r1"]["filled"])
        self.assertEqual(reading["r1"]["gap"]["owed"], "M4")
        self.assertFalse(reading["r2"]["filled"])
        self.assertEqual(reading["r2"]["gap"]["owed"], "M5")
        self.assertFalse(reading["r3"]["filled"])
        self.assertEqual(reading["r3"]["gap"]["owed"], "M3")
        self.assertTrue(reading["r4"]["filled"])

    def test_no_clause_ever_carries_prose(self):
        episode = run(now_day=100.0, geo=[GEO_ROW])[0]
        for clause in episode["reading"].values():
            self.assertNotIn("text", clause)
            self.assertIn("slots", clause)

    def test_the_one_clause_that_can_carry_a_number_carries_the_bundle_s(self):
        found = ep.episodes(
            now_ms=_at(100.0), catalogue_events=[], geo_record=[GEO_ROW], leo_record=[],
            elements=reader({}), newest_epoch=newest({}), class_figures=self.FIGURES,
        )
        clause = found[0]["reading"]["r3"]
        self.assertTrue(clause["filled"])
        self.assertEqual(clause["slots"]["k"], 28)
        self.assertEqual(clause["slots"]["n"], 822)
        self.assertEqual(clause["slots"]["stage"], "S1")
        self.assertEqual(clause["earnedBy"]["version"], "trigger-time-taxonomy/20260922/1")

    def test_a_phasing_campaign_gets_no_belt_figure(self):
        found = ep.episodes(
            now_ms=_at(100.0), catalogue_events=[], geo_record=[], leo_record=[LEO_ROW],
            elements=reader({}), newest_epoch=newest({}), class_figures=self.FIGURES,
        )
        self.assertFalse(found[0]["reading"]["r3"]["filled"])


class InjectedClockTest(unittest.TestCase):
    """A later clock keeps what an earlier one decided.

    This is the property that makes the replay and the live product one thing.
    If an episode can complete on Tuesday and be in progress again on Thursday
    without a new step, then the state chip is a measurement of when somebody
    looked, and two of this module's rules were exactly that until the
    injected-clock exercise caught them: a registered row clamped its
    completion to the clock, and the trend test read the object's newest
    element set rather than the episode's own.
    """

    def _at_clock(self, now_day: float):
        bundles = {700: geo_elements(RELOCATION)}
        events = [catalogue_step(700, 0.0, "along-track-raise", "GEO")]
        found = run(now_day=now_day, events=events, bundles=bundles, geo=[GEO_ROW])
        return {episode["key"]: episode for episode in found}

    def test_a_completed_episode_stays_completed_at_every_later_clock(self):
        early = self._at_clock(180.0)
        settled = {key for key, episode in early.items() if episode["state"] == "COMPLETED"}
        self.assertTrue(settled, "the fixture must settle something by day 180")
        for later_day in (200.0, 400.0, 900.0):
            late = self._at_clock(later_day)
            for key in settled:
                self.assertIn(key, late, f"{key} vanished at day {later_day}")
                self.assertEqual(late[key]["state"], "COMPLETED", key)
                self.assertEqual(late[key]["onsetMs"], early[key]["onsetMs"], key)
                self.assertEqual(late[key]["completedMs"], early[key]["completedMs"], key)

    def test_a_registered_row_that_has_not_departed_yet_is_not_completed(self):
        # The arrival is at day 0 and the departure at day 50, so a clock at
        # day 10 must not report a completion, and must not date one at day 10.
        found = run(now_day=10.0, geo=[GEO_ROW])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["state"], "IN PROGRESS")
        self.assertIsNone(found[0]["completedMs"])
        self.assertEqual(found[0]["closure"], "open")

    def test_its_completion_is_the_record_own_date_once_it_has_passed(self):
        found = run(now_day=100.0, geo=[GEO_ROW])
        self.assertEqual(found[0]["state"], "COMPLETED")
        self.assertEqual(found[0]["completedMs"], _at(50.0))


class PurityTest(unittest.TestCase):
    def test_two_calls_over_the_same_inputs_produce_the_same_records(self):
        bundles = {700: geo_elements(RELOCATION)}
        events = [catalogue_step(700, 0.0, "along-track-raise", "GEO")]
        once = run(now_day=180.0, events=events, bundles=bundles, geo=[GEO_ROW])
        twice = run(now_day=180.0, events=events, bundles=bundles, geo=[GEO_ROW])
        self.assertEqual(once, twice)

    def test_it_mutates_nothing_it_is_given(self):
        events = [catalogue_step(700, 0.0, "along-track-raise", "GEO")]
        rows = [dict(GEO_ROW)]
        before = copy.deepcopy((events, rows))
        run(now_day=180.0, events=events, bundles={700: geo_elements(RELOCATION)}, geo=rows)
        self.assertEqual(copy.deepcopy((events, rows)), before)

    def test_the_order_is_fixed_rather_than_whatever_the_dictionary_gave(self):
        bundles = {700: geo_elements(RELOCATION), 701: outside_elements(staged_axis, -20.0, 140.0)}
        events = [catalogue_step(701, 100.0, "along-track-raise", "LEO"),
                  catalogue_step(700, 0.0, "along-track-raise", "GEO")]
        found = run(now_day=140.0, events=events, bundles=bundles)
        updates = [episode["updatedMs"] for episode in found]
        self.assertEqual(updates, sorted(updates, reverse=True))


if __name__ == "__main__":
    unittest.main()
