"""Offline tests for the indices that drive the empirical thermosphere.

Nothing here reaches the network: the F10.7 parsers are handed the exact bytes
NOAA serves, and the ap series is built from Kp rows in the shape this site
already publishes them.

Why this file exists at all. The layer's whole claim to cover a 120-hour
timeline rests on three numbers, and two of the three are only as good as the
conversion behind them. An ap history in the wrong ORDER does not raise -- it
produces a plausible field driven by the wrong storm. A forecast Kp counted as
observed does not raise either; it produces a FORECAST badge that is silently
missing. Both are checked here.
"""

from __future__ import annotations

import datetime as dt
import json
import unittest

from pipeline.msis_drivers import (
    KP_TO_AP,
    ApSeries,
    DriverError,
    F107Series,
    driver_provenance,
    kp_to_ap,
    parse_f107_observed,
    parse_f107_outlook,
)


def kp_rows(start: dt.datetime, values, status="observed"):
    return [
        {
            "time": (start + dt.timedelta(hours=3 * index)).isoformat().replace("+00:00", "Z"),
            "kp": value,
            "status": status,
        }
        for index, value in enumerate(values)
    ]


class KpToApTests(unittest.TestCase):
    def test_the_table_is_the_published_one(self) -> None:
        # Spot values from Bartels' table. If this ever changes, MSIS is being
        # driven by a different geomagnetic history than the Kp chart on the
        # same page is drawing.
        self.assertEqual(len(KP_TO_AP), 28)
        self.assertEqual(kp_to_ap(0), 0)
        self.assertEqual(kp_to_ap(1), 4)
        self.assertEqual(kp_to_ap(2.33), 9)      # 2+
        self.assertEqual(kp_to_ap(4.0), 27)
        self.assertEqual(kp_to_ap(5.0), 48)      # G1 threshold
        self.assertEqual(kp_to_ap(6.67), 111)    # 7-
        self.assertEqual(kp_to_ap(8.67), 300)    # 9-
        self.assertEqual(kp_to_ap(9), 400)

    def test_it_is_a_lookup_and_not_a_curve(self) -> None:
        # The obvious shortcut -- fit something smooth through it -- gets storm
        # ap badly wrong, and storm ap is the only part of this the layer
        # exists to show. One third of a Kp unit at the top is a 33% step.
        self.assertEqual(kp_to_ap(9) / kp_to_ap(8.67), 400 / 300)
        # ...and one third of a unit at the bottom is not.
        self.assertEqual(kp_to_ap(1) - kp_to_ap(0.67), 1)

    def test_it_refuses_a_number_that_is_not_a_kp(self) -> None:
        for bad in (-0.1, 9.5, float("nan")):
            with self.assertRaises(DriverError):
                kp_to_ap(bad)


class ApSeriesTests(unittest.TestCase):
    START = dt.datetime(2026, 8, 13, 0, tzinfo=dt.timezone.utc)

    def series(self, count=40, status="observed"):
        return ApSeries(kp_rows(self.START, [(index % 10) / 3 for index in range(count)], status))

    def test_an_instant_takes_its_own_three_hour_interval(self) -> None:
        rows = kp_rows(self.START, [0, 3, 6, 9] + [1] * 20)
        series = ApSeries(rows)
        self.assertEqual(series.ap_at(self.START + dt.timedelta(hours=0)), kp_to_ap(0))
        self.assertEqual(series.ap_at(self.START + dt.timedelta(hours=2, minutes=59)), kp_to_ap(0))
        self.assertEqual(series.ap_at(self.START + dt.timedelta(hours=3)), kp_to_ap(3))
        self.assertEqual(series.ap_at(self.START + dt.timedelta(hours=8, minutes=59)), kp_to_ap(6))

    def test_daily_ap_is_the_mean_of_the_days_eight_intervals(self) -> None:
        rows = kp_rows(self.START, [0, 1, 2, 3, 4, 5, 6, 7] + [0] * 8)
        series = ApSeries(rows)
        expected = sum(kp_to_ap(value) for value in (0, 1, 2, 3, 4, 5, 6, 7)) / 8
        self.assertAlmostEqual(series.daily_ap(self.START + dt.timedelta(hours=13)), expected)

    def test_the_msis_history_is_in_msiss_order(self) -> None:
        # THE ONE THAT MATTERS. MSIS wants: daily Ap, ap now, -3 h, -6 h, -9 h,
        # the mean of 12-33 h ago and the mean of 36-57 h ago. Getting this
        # wrong does not raise; it draws a different storm. Every interval is
        # given a distinct Kp so a transposition cannot pass.
        values = [index / 3 for index in range(28)] * 2
        series = ApSeries(kp_rows(self.START, values))
        when = self.START + dt.timedelta(hours=57, minutes=30)   # inside interval 19
        history = series.msis_history(when)
        self.assertEqual(len(history), 7)
        index_of = lambda hours: int((57 - hours) // 3)  # noqa: E731
        self.assertEqual(history[1], kp_to_ap(values[index_of(0)]))
        self.assertEqual(history[2], kp_to_ap(values[index_of(3)]))
        self.assertEqual(history[3], kp_to_ap(values[index_of(6)]))
        self.assertEqual(history[4], kp_to_ap(values[index_of(9)]))
        block_a = [kp_to_ap(values[index_of(12 + 3 * step)]) for step in range(8)]
        block_b = [kp_to_ap(values[index_of(36 + 3 * step)]) for step in range(8)]
        self.assertAlmostEqual(history[5], sum(block_a) / 8)
        self.assertAlmostEqual(history[6], sum(block_b) / 8)
        self.assertAlmostEqual(history[0], series.daily_ap(when))

    def test_an_hour_without_a_full_history_is_not_drivable(self) -> None:
        # 57 hours of ap have to exist BEHIND an instant before MSIS's storm
        # formulation can be evaluated for it. Publishing a frame there anyway
        # would mean inventing the missing intervals.
        series = self.series(count=40)
        self.assertEqual(series.earliest_drivable(), self.START + dt.timedelta(hours=57))
        with self.assertRaises(DriverError):
            series.msis_history(self.START + dt.timedelta(hours=1))

    def test_coverage_ends_with_the_last_interval_not_its_start(self) -> None:
        series = self.series(count=40)
        last_start = self.START + dt.timedelta(hours=3 * 39)
        self.assertTrue(series.covers(last_start + dt.timedelta(hours=2, minutes=59)))
        self.assertFalse(series.covers(last_start + dt.timedelta(hours=3)))

    def test_the_forecast_half_of_the_series_says_so(self) -> None:
        rows = kp_rows(self.START, [1] * 20) + kp_rows(
            self.START + dt.timedelta(hours=60), [2] * 10, status="predicted"
        )
        series = ApSeries(rows)
        self.assertEqual(series.status_at(self.START + dt.timedelta(hours=1)), "observed")
        self.assertEqual(series.status_at(self.START + dt.timedelta(hours=61)), "predicted")

    def test_rows_that_are_not_kp_intervals_are_rejected_and_named(self) -> None:
        rows = kp_rows(self.START, [1] * 10)
        rows.append({"time": "2026-08-14T01:07:00Z", "kp": 3.0, "status": "observed"})
        rows.append({"time": "nonsense", "kp": 3.0, "status": "observed"})
        series = ApSeries(rows)
        self.assertEqual(len(series.rejected), 2)
        self.assertNotIn(dt.datetime(2026, 8, 14, 1, tzinfo=dt.timezone.utc), series.entries)

    def test_no_usable_rows_is_an_error_not_an_empty_series(self) -> None:
        with self.assertRaises(DriverError):
            ApSeries([{"time": "nonsense", "kp": 1}])


# The exact shape NOAA serves, trimmed. `flux` really is written in that
# expanded float form, and the running mean really is null on all but the noon
# record -- both of which a hand-written fixture would have tidied away.
F107_JSON = json.dumps([
    {"time_tag": "2026-08-19T22:00:00", "frequency": 2800, "flux": 1.250000000000000e+002,
     "reporting_schedule": "Afternoon", "avg_begin_date": None, "ninety_day_mean": None, "rec_count": None},
    {"time_tag": "2026-08-19T20:00:00", "frequency": 2800, "flux": 1.260000000000000e+002,
     "reporting_schedule": "Noon", "avg_begin_date": "2026-05-22T20:00:00",
     "ninety_day_mean": 1.320000000000000e+002, "rec_count": 90},
    {"time_tag": "2026-08-19T17:00:00", "frequency": 2800, "flux": 1.260000000000000e+002,
     "reporting_schedule": "Morning", "avg_begin_date": None, "ninety_day_mean": None, "rec_count": None},
    {"time_tag": "2026-08-18T20:00:00", "frequency": 2800, "flux": 1.240000000000000e+002,
     "reporting_schedule": "Noon", "avg_begin_date": None, "ninety_day_mean": None, "rec_count": None},
])

OUTLOOK_TEXT = """:Product: 27-day Space Weather Outlook Table 27DO.txt
:Issued: 2026 Aug 17 0058 UTC
#      27-day Space Weather Outlook Table
#   UTC      Radio Flux   Planetary   Largest
#  Date       10.7 cm      A Index    Kp Index
2026 Aug 19     130           5          2
2026 Aug 20     130           5          2
2026 Aug 21     125          12          4
"""


class F107Tests(unittest.TestCase):
    def test_only_the_noon_record_is_the_index(self) -> None:
        # NOAA reports three times a day and only the local-noon Penticton value
        # is F10.7. Taking whichever record came last would mix three different
        # quantities into one series and call the result an index.
        parsed = parse_f107_observed(F107_JSON)
        self.assertEqual(sorted(parsed["daily"]), [dt.date(2026, 8, 18), dt.date(2026, 8, 19)])
        self.assertEqual(parsed["daily"][dt.date(2026, 8, 19)], 126.0)
        self.assertEqual(parsed["runningMean"], 132.0)
        self.assertEqual(parsed["runningMeanDays"], 90)

    def test_the_outlook_gives_flux_and_deliberately_not_ap(self) -> None:
        rows = parse_f107_outlook(OUTLOOK_TEXT)
        self.assertEqual(rows[dt.date(2026, 8, 20)], 130.0)
        self.assertEqual(len(rows), 3)

    def test_observation_beats_the_outlook_where_both_exist(self) -> None:
        observed = parse_f107_observed(F107_JSON)["daily"]
        predicted = {day: flux for day, flux in parse_f107_outlook(OUTLOOK_TEXT).items()
                     if day not in observed}
        series = F107Series(observed, predicted, running_mean=132.0, running_mean_days=90,
                            running_mean_at=dt.date(2026, 8, 19))
        self.assertEqual(series.f107_for(dt.date(2026, 8, 19)), 126.0)   # observed, not 130
        self.assertEqual(series.status_for(dt.date(2026, 8, 19)), "observed")
        self.assertEqual(series.f107_for(dt.date(2026, 8, 20)), 130.0)
        self.assertEqual(series.status_for(dt.date(2026, 8, 20)), "predicted")

    def test_f107a_says_which_average_it_actually_is(self) -> None:
        # NRLMSIS defines F10.7A as the 81-day mean CENTRED on the day, and that
        # number does not exist for today: it needs forty days of the future.
        # Publishing NOAA's running mean under the name of the centred one is
        # the kind of quiet substitution this project does not make.
        series = F107Series({dt.date(2026, 8, 19): 126.0}, {}, running_mean=132.0,
                            running_mean_days=90, running_mean_at=dt.date(2026, 8, 19))
        self.assertEqual(series.f107a, 132.0)
        self.assertIn("81-day", series.f107a_basis)
        self.assertIn("90-day", series.f107a_basis)

    def test_without_a_published_mean_it_falls_back_and_says_how_many_days(self) -> None:
        series = F107Series({dt.date(2026, 8, 18): 124.0, dt.date(2026, 8, 19): 126.0}, {})
        self.assertEqual(series.f107a, 125.0)
        self.assertIn("2 observed days", series.f107a_basis)

    def test_an_unpublished_day_raises_rather_than_holding_the_last_value(self) -> None:
        series = F107Series({dt.date(2026, 8, 19): 126.0}, {})
        with self.assertRaises(DriverError):
            series.f107_for(dt.date(2026, 8, 25))


class ProvenanceTests(unittest.TestCase):
    def test_the_block_names_the_conversion_and_both_windows(self) -> None:
        start = dt.datetime(2026, 8, 13, 0, tzinfo=dt.timezone.utc)
        ap = ApSeries(
            kp_rows(start, [1] * 20)
            + kp_rows(start + dt.timedelta(hours=60), [2] * 10, status="predicted")
        )
        flux = F107Series({dt.date(2026, 8, 19): 126.0}, {dt.date(2026, 8, 20): 130.0},
                          running_mean=132.0, running_mean_days=90, running_mean_at=dt.date(2026, 8, 19))
        block = driver_provenance(ap, flux)
        self.assertIn("Bartels", block["ap"]["conversion"])
        # Observed coverage ends with the last OBSERVED interval, not the last
        # published one: a reader has to be able to see where the record stops
        # and the forecast starts.
        self.assertEqual(block["ap"]["observedThrough"], "2026-08-15T12:00:00Z")
        self.assertEqual(block["ap"]["validTo"], "2026-08-16T18:00:00Z")
        self.assertEqual(block["f107"]["observedThrough"], "2026-08-19")
        self.assertEqual(block["f107a"]["value"], 132.0)


if __name__ == "__main__":
    unittest.main()
