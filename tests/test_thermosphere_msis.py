"""Offline tests for the empirical thermosphere bundle.

No network: the drivers are constructed in the test and pymsis evaluates
locally.  Skipped whole when pymsis is absent, the same rule the NRLMSIS tests
in `test_thermosphere.py` already follow.

The defect this whole module answers, measured on the release of 2026-08-20:
NOAA WAM published 13 hourly frames covering 11.8 hours of a 120-hour slider,
9.8% of it, and the layer had nothing to draw for the other 90%.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import unittest

import numpy as np

from pipeline import thermosphere
from pipeline.msis_drivers import ApSeries, F107Series, kp_to_ap
from pipeline.thermosphere import (
    MSIS_HOURS_AHEAD,
    MSIS_HOURS_BACK,
    MSIS_SHARD_HOURS,
    PUBLISHED_ALTITUDES_KM,
    ThermosphereFormatError,
    build_msis_bundle,
    decode_log_density,
    msis_available,
    msis_grid,
    msis_publish_hours,
)

NOW = dt.datetime(2026, 8, 20, 3, 14, 0, tzinfo=dt.timezone.utc)
KP_START = NOW.replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=7)


def kp_rows(kp_by_index=None, count=88, storm_at=None):
    """Seven days back and three forward of 3-hourly Kp, the shape SWPC serves.

    The status labels copy NOAA exactly, INCLUDING the part that is misleading:
    the whole current UT day is `estimated`, so seven of its eight intervals
    carry that word while lying in the future. A tidied-up fixture that marked
    them `predicted` would let the pipeline's future-hour rule rot untested.
    """
    rows = []
    today = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + dt.timedelta(days=1)
    for index in range(count):
        when = KP_START + dt.timedelta(hours=3 * index)
        kp = 2.0
        if storm_at is not None and storm_at <= when < storm_at + dt.timedelta(hours=12):
            kp = 8.0
        if kp_by_index:
            kp = kp_by_index(index, when, kp)
        if when < today:
            status = "observed"
        elif when < tomorrow:
            status = "estimated"
        else:
            status = "predicted"
        rows.append({
            "time": when.isoformat().replace("+00:00", "Z"),
            "kp": kp,
            "status": status,
        })
    return rows


def flux_series(days_back=45, days_ahead=6):
    day = NOW.date()
    observed = {day - dt.timedelta(days=offset): 126.0 for offset in range(1, days_back)}
    predicted = {day + dt.timedelta(days=offset): 130.0 for offset in range(0, days_ahead)}
    return F107Series(observed, predicted, running_mean=132.0, running_mean_days=90,
                      running_mean_at=day - dt.timedelta(days=1))


class PublishHoursTests(unittest.TestCase):
    def test_the_window_is_the_sites_own_slider(self) -> None:
        hours = msis_publish_hours(NOW)
        span = (hours[-1] - hours[0]).total_seconds() / 3600
        # Extended out to shard boundaries at each end, so never SHORTER than
        # the slider. A shorter window re-creates the hole this exists to fill.
        self.assertGreaterEqual(span, MSIS_HOURS_BACK + MSIS_HOURS_AHEAD)
        self.assertLess(span, MSIS_HOURS_BACK + MSIS_HOURS_AHEAD + 2 * MSIS_SHARD_HOURS)
        self.assertLessEqual(hours[0], NOW - dt.timedelta(hours=MSIS_HOURS_BACK))
        self.assertGreaterEqual(hours[-1], NOW + dt.timedelta(hours=MSIS_HOURS_AHEAD))

    def test_every_hour_is_a_whole_utc_hour_on_a_shard_grid(self) -> None:
        hours = msis_publish_hours(NOW)
        self.assertTrue(all(h.minute == 0 and h.second == 0 for h in hours))
        self.assertEqual(hours[0].hour % MSIS_SHARD_HOURS, 0)

    def test_two_builds_minutes_apart_ask_for_the_same_hours(self) -> None:
        # THE PROPERTY THAT KEEPS 13 MB OFF THE WIRE. The publish runs every
        # five minutes; anchoring frames to `now` instead of to the clock would
        # give every shard a new content hash every cycle, rewriting and
        # re-sending the whole set to say exactly the same thing.
        self.assertEqual(
            msis_publish_hours(NOW),
            msis_publish_hours(NOW + dt.timedelta(minutes=5)),
        )

    def test_a_shard_length_that_does_not_divide_the_day_is_refused(self) -> None:
        with self.assertRaises(ThermosphereFormatError):
            msis_publish_hours(NOW, shard_hours=7)


class GridTests(unittest.TestCase):
    def test_it_is_the_same_grid_the_wam_layer_publishes(self) -> None:
        # Deliberate. MSIS carries no structure that needs 4 degrees of
        # latitude, but a coarser grid would make the two fields look different
        # at the boundary for a reason that is not the models.
        latitudes, longitudes = msis_grid()
        self.assertEqual((len(latitudes), len(longitudes)), (46, 45))
        self.assertEqual((latitudes[0], latitudes[-1]), (-90.0, 90.0))

    def test_the_longitude_seam_is_not_published_twice(self) -> None:
        _, longitudes = msis_grid()
        self.assertEqual(longitudes[0], 0.0)
        self.assertLess(longitudes[-1], 360.0)


@unittest.skipUnless(msis_available(), "pymsis is not installed")
class BundleTests(unittest.TestCase):
    def build(self, **kwargs):
        return build_msis_bundle(NOW, kp_rows=kwargs.pop("rows", kp_rows()),
                                 flux=kwargs.pop("flux", flux_series()), **kwargs)

    def test_it_covers_the_whole_slider_hourly(self) -> None:
        bundle = self.build()
        frames = [f for shard in bundle["shards"] for f in shard["frames"]]
        times = [thermosphere.parse_utc(f["validAt"]) for f in frames]
        self.assertGreaterEqual(len(frames), MSIS_HOURS_BACK + MSIS_HOURS_AHEAD)
        self.assertLessEqual(times[0], NOW - dt.timedelta(hours=MSIS_HOURS_BACK))
        self.assertGreaterEqual(times[-1], NOW + dt.timedelta(hours=MSIS_HOURS_AHEAD))
        gaps = {(b - a).total_seconds() / 60 for a, b in zip(times, times[1:])}
        self.assertEqual(gaps, {60.0})

    def test_the_shards_tile_the_window_without_overlapping(self) -> None:
        bundle = self.build()
        for earlier, later in zip(bundle["shards"], bundle["shards"][1:]):
            self.assertEqual(earlier["validTo"], later["validFrom"])
        for shard in bundle["shards"]:
            start = thermosphere.parse_utc(shard["validFrom"])
            end = thermosphere.parse_utc(shard["validTo"])
            for frame in shard["frames"]:
                self.assertTrue(start <= thermosphere.parse_utc(frame["validAt"]) < end)

    def test_a_frame_decodes_to_a_plausible_thermosphere(self) -> None:
        bundle = self.build()
        frame = bundle["shards"][0]["frames"][0]
        levels = len(frame["grid"]["altitudeKm"])
        rows = len(frame["grid"]["latitudeDeg"])
        columns = len(frame["grid"]["longitudeDeg"])
        codes = np.frombuffer(base64.b64decode(frame["codes"]), dtype=np.uint16)
        self.assertEqual(codes.size, levels * rows * columns)
        density = decode_log_density({
            "codes": codes.reshape(levels, rows, columns),
            "bits": frame["encoding"]["bits"],
            "logFloor": frame["encoding"]["logFloor"],
            "logCeiling": frame["encoding"]["logCeiling"],
        })
        # 120 km is around 1e-8 kg/m3 and 1000 km around 1e-15. Getting the
        # transpose wrong produces a field of exactly the right size and range
        # with the axes scrambled, so the check is that density falls MONOTONELY
        # with the altitude axis, not merely that it spans the right decades.
        column = density[:, rows // 2, columns // 2]
        self.assertTrue(np.all(np.diff(column) < 0), column)
        self.assertGreater(column[0], 1e-9)
        self.assertLess(column[-1], 1e-13)
        self.assertEqual(frame["validFraction"], 1.0)

    def test_the_published_altitudes_are_the_sites_own(self) -> None:
        bundle = self.build()
        self.assertEqual(bundle["publishedAltitudesKm"], list(PUBLISHED_ALTITUDES_KM))
        self.assertEqual(
            bundle["shards"][0]["frames"][0]["grid"]["altitudeKm"],
            list(PUBLISHED_ALTITUDES_KM),
        )

    def test_a_storm_thickens_the_air(self) -> None:
        # The whole reason for choosing an ap-driven model. If this does not
        # hold, the layer is a pretty picture that cannot teach the one lesson
        # it exists for.
        storm_at = (NOW - dt.timedelta(hours=24)).replace(minute=0, second=0, microsecond=0)
        quiet = self.build()
        stormy = self.build(rows=kp_rows(storm_at=storm_at))

        def mean_log_at(bundle, when):
            for shard in bundle["shards"]:
                for frame in shard["frames"]:
                    if frame["validAt"] != thermosphere.utc_iso(when):
                        continue
                    grid = frame["grid"]
                    shape = (len(grid["altitudeKm"]), len(grid["latitudeDeg"]), len(grid["longitudeDeg"]))
                    codes = np.frombuffer(base64.b64decode(frame["codes"]), dtype=np.uint16).reshape(shape)
                    density = decode_log_density({
                        "codes": codes, "bits": frame["encoding"]["bits"],
                        "logFloor": frame["encoding"]["logFloor"],
                        "logCeiling": frame["encoding"]["logCeiling"],
                    })
                    level = grid["altitudeKm"].index(420.0)
                    return float(np.log10(density[level]).mean())
            raise AssertionError(f"no frame at {when}")

        when = storm_at + dt.timedelta(hours=9)
        ratio = 10 ** (mean_log_at(stormy, when) - mean_log_at(quiet, when))
        # Kp 8 is ap 207 against Kp 2 ap 7. NRLMSIS under-responds to storms
        # and is documented as doing so, but it must respond.
        self.assertGreater(ratio, 1.5, f"global mean 420 km density ratio {ratio}")

    def test_the_forecast_half_of_the_timeline_is_marked_as_one(self) -> None:
        bundle = self.build()
        frames = [f for shard in bundle["shards"] for f in shard["frames"]]
        past = [f for f in frames if thermosphere.parse_utc(f["validAt"]) < NOW - dt.timedelta(hours=6)]
        ahead = [f for f in frames if thermosphere.parse_utc(f["validAt"]) > NOW + dt.timedelta(hours=6)]
        self.assertTrue(all(f["driverStatus"] == "observed" for f in past), "a past hour claimed forecast drivers")
        self.assertTrue(all(f["driverStatus"] == "predicted" for f in ahead), "a future hour claimed observed drivers")
        # NOAA labels the WHOLE current UT day `estimated` in its Kp product,
        # including intervals that have not happened yet -- measured
        # 2026-08-20T03:53Z, seven of the eight so labelled were in the future.
        # An hour ahead of the build is a forecast whatever the label says, or
        # tonight is badged as a reconstruction of something that has not
        # happened.
        estimated_future = [
            f for f in frames
            if f["drivers"]["apStatus"] == "estimated"
            and thermosphere.parse_utc(f["validAt"]) >= NOW
        ]
        self.assertTrue(estimated_future, "fixture no longer exercises the estimated-but-future case")
        self.assertTrue(all(f["driverStatus"] == "predicted" for f in estimated_future))
        self.assertTrue(all(f["drivers"]["aheadOfBuild"] for f in estimated_future))

    def test_a_future_hour_is_a_forecast_even_when_both_labels_say_otherwise(self) -> None:
        # THE ONE THAT WOULD ROT SILENTLY. Today's frames read `predicted` above
        # only because NOAA has not published today's F10.7 yet -- it lands at
        # 20:00 UT. After that, today is `observed` flux and `estimated` Kp, and
        # a rule that trusted the two labels would badge tonight's thermosphere
        # EMPIRICAL: a forecast presented as a reconstruction. So this test
        # drives the model with a flux series that HAS observed today, which is
        # what the live one looks like for most of every day.
        day = NOW.date()
        observed = {day - dt.timedelta(days=offset): 126.0 for offset in range(0, 45)}
        predicted = {day + dt.timedelta(days=offset): 130.0 for offset in range(1, 6)}
        flux = F107Series(observed, predicted, running_mean=132.0, running_mean_days=90,
                          running_mean_at=day)
        bundle = self.build(flux=flux)
        frames = [f for shard in bundle["shards"] for f in shard["frames"]]
        tonight = [
            f for f in frames
            if thermosphere.parse_utc(f["validAt"]) >= NOW
            and thermosphere.parse_utc(f["validAt"]).date() == day
        ]
        self.assertTrue(tonight, "no future hours left in today")
        for frame in tonight:
            self.assertEqual(frame["drivers"]["f107Status"], "observed")
            self.assertIn(frame["drivers"]["apStatus"], {"observed", "estimated"})
            self.assertEqual(frame["driverStatus"], "predicted", frame["validAt"])
        # ...and an hour that has already passed today is still a reconstruction.
        earlier = [
            f for f in frames
            if thermosphere.parse_utc(f["validAt"]) < NOW
            and thermosphere.parse_utc(f["validAt"]).date() == day
        ]
        self.assertTrue(earlier)
        self.assertTrue(all(f["driverStatus"] == "observed" for f in earlier))
        self.assertEqual({s["driverStatus"] for s in bundle["shards"]} - {"observed", "predicted", "mixed"}, set())

    def test_the_drivers_ride_on_the_frame(self) -> None:
        bundle = self.build()
        frame = bundle["shards"][0]["frames"][0]
        drivers = frame["drivers"]
        self.assertEqual(drivers["ap"], kp_to_ap(drivers["kp"]))
        self.assertEqual(len(drivers["apHistory"]), 7)
        self.assertEqual(drivers["f107a"], 132.0)

    def test_an_hour_the_drivers_cannot_reach_is_not_published(self) -> None:
        # No default ap, no held-over F10.7, no extrapolation: the series stops
        # and says where. Kp only to +12 h here.
        short = [row for row in kp_rows()
                 if thermosphere.parse_utc(row["time"]) <= NOW + dt.timedelta(hours=12)]
        bundle = self.build(rows=short)
        last = thermosphere.parse_utc(bundle["validTo"])
        self.assertLessEqual(last, NOW + dt.timedelta(hours=15))
        self.assertTrue(bundle["outsideDrivers"])
        self.assertIn("ap history", bundle["outsideDrivers"][0]["reason"])

    def test_it_is_labelled_empirical_and_never_model(self) -> None:
        bundle = self.build()
        self.assertEqual(bundle["model"]["model"], "nrlmsis21")
        self.assertEqual(bundle["model"]["modelStatus"], "empirical")
        self.assertEqual(bundle["source"]["status"], "empirical")
        self.assertIn("Bartels", bundle["drivers"]["ap"]["conversion"])
        self.assertIn("81-day", bundle["drivers"]["f107a"]["basis"])

    def test_the_bundle_serialises(self) -> None:
        json.dumps(self.build())


if __name__ == "__main__":
    unittest.main()
