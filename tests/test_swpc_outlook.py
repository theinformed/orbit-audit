from __future__ import annotations

import datetime as dt
import unittest

from pipeline.swpc_outlook import normalize_swpc_outlook, parse_three_day_geomag


SCALES = {
    "-1": {
        "DateStamp": "2026-08-05",
        "TimeStamp": "19:45:00",
        "R": {"Scale": "1", "Text": "minor", "MinorProb": None, "MajorProb": None},
        "S": {"Scale": "0", "Text": "none", "Prob": None},
        "G": {"Scale": "2", "Text": "moderate"},
    },
    "0": {
        "DateStamp": "2026-08-06",
        "TimeStamp": "19:45:00",
        "R": {"Scale": "0", "Text": "none", "MinorProb": None, "MajorProb": None},
        "S": {"Scale": "0", "Text": "none", "Prob": None},
        "G": {"Scale": "0", "Text": "none"},
    },
    "1": {
        "DateStamp": "2026-08-06",
        "TimeStamp": "19:45:00",
        "R": {"Scale": None, "Text": None, "MinorProb": "10", "MajorProb": "1"},
        "S": {"Scale": None, "Text": None, "Prob": "1"},
        "G": {"Scale": "0", "Text": "none"},
    },
    "2": {
        "DateStamp": "2026-08-07",
        "TimeStamp": "00:00:00",
        "R": {"Scale": None, "Text": None, "MinorProb": "20", "MajorProb": "5"},
        "S": {"Scale": None, "Text": None, "Prob": "2"},
        "G": {"Scale": "1", "Text": "minor"},
    },
    "3": {
        "DateStamp": "2026-08-08",
        "TimeStamp": "00:00:00",
        "R": {"Scale": None, "Text": None, "MinorProb": "30", "MajorProb": "10"},
        "S": {"Scale": None, "Text": None, "Prob": "3"},
        "G": {"Scale": "2", "Text": "moderate"},
    },
}

THREE_DAY = """:Product: 3-Day Forecast
:Issued: 2026 Aug 06 1250 UTC
#
A. NOAA Geomagnetic Activity Observation and Forecast

NOAA Kp index breakdown Aug 06-Aug 08 2026

Rationale: No G1 storms are expected. No significant solar-wind
features are forecast.

B. NOAA Solar Radiation Activity Observation and Forecast

Rationale: No S1 storms are expected.
No favorable source activity is forecast.

C. NOAA Radio Blackout Activity and Forecast

Rationale: A slight chance of R1-R2 events persists as active regions
rotate off the disk.
"""

GEOMAG = """:Product: Geomagnetic Forecast
:Issued: 2026 Aug 05 2205 UTC
#
NOAA Ap Index Forecast
Observed Ap 04 Aug 010
Estimated Ap 05 Aug 005
Predicted Ap 06 Aug-08 Aug 004-012-009

NOAA Geomagnetic Activity Probabilities 06 Aug-08 Aug
Active                10/28/20
Minor storm           01/25/15
Moderate storm        01/10/01
Strong-Extreme storm  01/01/01
"""

KP = [
    {"time_tag": "2026-08-06T15:00:00", "kp": 0.67, "observed": "observed", "noaa_scale": None},
    {"time_tag": "2026-08-06T18:00:00", "kp": 1.0, "observed": "estimated", "noaa_scale": None},
    {"time_tag": "2026-08-07T00:00:00", "kp": 5.0, "observed": "predicted", "noaa_scale": "G1"},
]

RAW_ALERT_MESSAGE = (
    "Space Weather Message Code: WARK05\r\n"
    "Issue Time: 2026 Aug 06 1900 UTC\r\n\r\n"
    "EXTENDED WARNING: Geomagnetic K-index of 5 expected\r\n"
    "Now Valid Until: 2026 Aug 07 0300 UTC"
)
ALERTS = [
    {
        "product_id": "K05W",
        "issue_datetime": "2026-08-06 19:00:52.687",
        "message": RAW_ALERT_MESSAGE,
    }
]


class SwpcOutlookTests(unittest.TestCase):
    def test_complete_bundle_preserves_product_semantics(self) -> None:
        result = normalize_swpc_outlook(
            noaa_scales=SCALES,
            three_day_forecast=THREE_DAY,
            three_day_geomag=GEOMAG,
            kp_forecast=KP,
            alerts=ALERTS,
            retrieved_at=dt.datetime(2026, 8, 6, 19, 50, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(result["schemaVersion"], "swpc-outlook.v1")
        self.assertEqual(result["retrievedAt"], "2026-08-06T19:50:00Z")
        self.assertEqual(result["parseWarnings"], [])

        scales = result["noaaScales"]
        self.assertEqual(scales["latestObserved"]["asOf"], "2026-08-06T19:45:00Z")
        self.assertEqual(scales["latestObserved"]["radioBlackout"]["level"], 0)
        self.assertEqual(scales["rolling24HourMaximum"]["windowStart"], "2026-08-05T19:45:00Z")
        self.assertEqual(scales["rolling24HourMaximum"]["windowEnd"], "2026-08-06T19:45:00Z")
        self.assertEqual(scales["rolling24HourMaximum"]["geomagnetic"]["level"], 2)
        self.assertEqual(scales["forecastDays"][0]["dayIndex"], 1)
        self.assertEqual(scales["forecastDays"][0]["date"], "2026-08-06")
        self.assertEqual(scales["forecastDays"][0]["radioBlackout"]["r1R2ProbabilityPercent"], 10)
        self.assertEqual(scales["forecastDays"][2]["solarRadiation"]["s1OrGreaterProbabilityPercent"], 3)
        self.assertEqual(scales["forecastDays"][2]["geomagnetic"]["level"], 2)

        forecast = result["threeDayForecast"]
        self.assertEqual(forecast["issuedAt"], "2026-08-06T12:50:00Z")
        self.assertEqual(
            forecast["rationales"]["geomagnetic"],
            "No G1 storms are expected. No significant solar-wind features are forecast.",
        )
        self.assertEqual(
            forecast["rationales"]["solarRadiation"],
            "No S1 storms are expected. No favorable source activity is forecast.",
        )
        self.assertIn("rotate off the disk", forecast["rationales"]["radioBlackout"])

        geomag = result["geomagneticForecast"]
        self.assertEqual(geomag["issuedAt"], "2026-08-05T22:05:00Z")
        self.assertEqual(geomag["ap"]["observed"], {"date": "2026-08-04", "value": 10})
        self.assertEqual(
            geomag["ap"]["predicted"],
            [
                {"date": "2026-08-06", "value": 4},
                {"date": "2026-08-07", "value": 12},
                {"date": "2026-08-08", "value": 9},
            ],
        )
        self.assertEqual(geomag["activityProbabilities"][1]["activePercent"], 28)
        self.assertEqual(geomag["activityProbabilities"][1]["moderateStormPercent"], 10)
        self.assertEqual(geomag["activityProbabilities"][2]["strongToExtremeStormPercent"], 1)

        rows = result["kpForecast"]["rows"]
        self.assertEqual([row["status"] for row in rows], ["observed", "estimated", "predicted"])
        self.assertEqual(rows[2]["time"], "2026-08-07T00:00:00Z")
        self.assertEqual(rows[2]["noaaScale"], "G1")

        alerts = result["alerts"]
        self.assertTrue(alerts["recentNotNecessarilyActive"])
        self.assertEqual(alerts["items"][0]["state"], "recent-not-necessarily-active")
        self.assertEqual(alerts["items"][0]["issuedAt"], "2026-08-06T19:00:52.687Z")
        self.assertEqual(alerts["items"][0]["rawMessage"], RAW_ALERT_MESSAGE)

    def test_malformed_products_fail_soft_with_nulls_and_warnings(self) -> None:
        result = normalize_swpc_outlook(
            noaa_scales={
                "0": {
                    "DateStamp": "not-a-date",
                    "TimeStamp": "bad",
                    "R": {"Scale": "quiet", "MinorProb": "125"},
                    "S": "not-an-object",
                    "G": {"Scale": None, "Text": None},
                },
                "1": [],
            },
            three_day_forecast="not a forecast",
            three_day_geomag=None,
            kp_forecast=[{"time_tag": "bad", "kp": 12, "observed": "maybe", "noaa_scale": "G9"}, None],
            alerts=[{"product_id": "TEST", "issue_datetime": "bad", "message": 7}, "bad"],
            retrieved_at="not-a-time",
        )

        self.assertGreater(len(result["parseWarnings"]), 10)
        self.assertIsNone(result["retrievedAt"])
        self.assertIsNone(result["noaaScales"]["latestObserved"]["asOf"])
        self.assertIsNone(result["noaaScales"]["latestObserved"]["radioBlackout"]["level"])
        self.assertIsNone(result["noaaScales"]["latestObserved"]["radioBlackout"]["r1R2ProbabilityPercent"])
        self.assertEqual(len(result["noaaScales"]["forecastDays"]), 3)
        self.assertIsNone(result["threeDayForecast"]["issuedAt"])
        self.assertIsNone(result["threeDayForecast"]["rationales"]["radioBlackout"])
        self.assertIsNone(result["geomagneticForecast"]["ap"]["observed"]["value"])
        self.assertEqual(result["kpForecast"]["rows"][0]["status"], None)
        self.assertEqual(result["kpForecast"]["rows"][0]["kp"], None)
        self.assertEqual(result["alerts"]["items"][0]["rawMessage"], None)
        self.assertTrue(result["alerts"]["recentNotNecessarilyActive"])

    def test_geomag_partial_dates_cross_year_boundary(self) -> None:
        text = """:Product: Geomagnetic Forecast
:Issued: 2026 Dec 31 2200 UTC
NOAA Ap Index Forecast
Observed Ap 30 Dec 005
Estimated Ap 31 Dec 006
Predicted Ap 01 Jan-03 Jan 007-008-009
NOAA Geomagnetic Activity Probabilities 01 Jan-03 Jan
Active 10/20/30
Minor storm 01/02/03
Moderate storm 00/01/02
Strong-Extreme storm 00/00/01
"""
        result = parse_three_day_geomag(text)

        self.assertEqual(result["parseWarnings"], [])
        self.assertEqual(
            [entry["date"] for entry in result["ap"]["predicted"]],
            ["2027-01-01", "2027-01-02", "2027-01-03"],
        )
        self.assertEqual(
            [entry["date"] for entry in result["activityProbabilities"]],
            ["2027-01-01", "2027-01-02", "2027-01-03"],
        )


if __name__ == "__main__":
    unittest.main()
