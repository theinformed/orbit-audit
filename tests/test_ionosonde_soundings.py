"""What the ionosonde lane must refuse to do.

Every test here pins a REASON that came out of characterising the live feed on
2026-08-19, not a value that happened to be true that afternoon.
"""

from __future__ import annotations

import datetime as dt
import unittest

from pipeline.ionosonde_soundings import (
    FRESH_LIMIT_MINUTES,
    NOMINAL_E_HEIGHT_KM,
    STATIONS_URL,
    build_ionosonde_bundle,
    normalize_longitude,
    normalize_station,
    parse_sounding_time,
)

OBSERVED_AT = dt.datetime(2026, 8, 19, 19, 0, 0, tzinfo=dt.timezone.utc)


def record(**overrides):
    base = {
        "time": "2026-08-19T18:50:00",
        "fof2": 8.0, "hmf2": 300.0, "fof1": None, "hmf1": None,
        "foe": None, "hme": None, "foes": None, "cs": 100.0, "source": "giro",
        "station": {"code": "TS001", "name": "Test", "latitude": "40.0", "longitude": "12.0"},
    }
    station = overrides.pop("station", None)
    if station:
        base["station"].update(station)
    base.update(overrides)
    return base


class NormalizationTest(unittest.TestCase):
    def test_longitude_comes_back_to_the_convention_the_rest_of_the_site_uses(self):
        """Upstream publishes 0..360 - station longitudes ran 0.5 to 359.4 on the
        measured frame. Austin, Texas arrives as 262.3 and is at -97.7; read
        raw it would plot in the Indian Ocean."""
        self.assertAlmostEqual(normalize_longitude(262.3), -97.7, places=6)
        self.assertAlmostEqual(normalize_longitude(12.0), 12.0, places=6)

    def test_naive_upstream_timestamps_are_treated_as_utc(self):
        """They carry no offset. Stamping UTC here rather than at the comparison
        keeps a naive/aware mix out of the age arithmetic, where it would raise
        only after a release had already been built."""
        parsed = parse_sounding_time("2026-08-19T18:50:00")
        self.assertEqual(parsed.tzinfo, dt.timezone.utc)

    def test_an_unreadable_time_drops_the_record_rather_than_dating_it_now(self):
        self.assertIsNone(parse_sounding_time("not a time"))
        self.assertIsNone(normalize_station(record(time="not a time"), OBSERVED_AT))

    def test_a_record_with_no_position_is_dropped(self):
        self.assertIsNone(normalize_station(record(station={"latitude": None}), OBSERVED_AT))

    def test_a_sounding_that_scaled_nothing_is_kept(self):
        """A station that sounded and could scale nothing is a real observation
        of a disturbed or blanketed ionosphere. Dropping it would silently
        improve the network's apparent coverage."""
        parsed = normalize_station(record(fof2=None, hmf2=None), OBSERVED_AT)
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed["foF2Mhz"])


class LayerRulesTest(unittest.TestCase):
    def test_an_e_height_without_a_critical_frequency_draws_no_e_layer(self):
        """hmE alone is not evidence of an E layer: 18 of the 23 records
        carrying the nominal 110.0 km height had no foE at all, so an
        hmE-only E layer would draw a layer nobody measured."""
        parsed = normalize_station(record(foe=None, hme=110.0), OBSERVED_AT)
        self.assertIsNone(parsed["foEMhz"])
        self.assertIsNone(parsed["hmEKm"])

    def test_the_autoscalers_nominal_height_is_flagged_as_nominal(self):
        """hmE took exactly 110.0 in 23 of 101 records while every other value
        occurred once. It is a placeholder, not a scaled peak height."""
        parsed = normalize_station(record(foe=2.5, hme=NOMINAL_E_HEIGHT_KM), OBSERVED_AT)
        self.assertTrue(parsed["eHeightIsNominal"])
        parsed = normalize_station(record(foe=2.5, hme=104.315), OBSERVED_AT)
        self.assertFalse(parsed["eHeightIsNominal"])

    def test_sporadic_e_is_kept_under_its_own_name(self):
        """`foes` is SPORADIC E, not the regular E layer. Reading it as the E
        layer would report a thin irregular patch as the main layer."""
        parsed = normalize_station(record(foes=6.0, foe=None), OBSERVED_AT)
        self.assertEqual(parsed["foEsMhz"], 6.0)
        self.assertIsNone(parsed["foEMhz"])

    def test_an_f1_height_without_an_f1_frequency_draws_no_f1_layer(self):
        parsed = normalize_station(record(fof1=None, hmf1=200.0), OBSERVED_AT)
        self.assertIsNone(parsed["hmF1Km"])


class FreshnessTest(unittest.TestCase):
    """The upstream is a last-known-value roster with no expiry. On the measured
    frame 74 of 101 stations had not sounded in over a day and the oldest was
    11 years stale, so a naive nearest-station search hands a reader an
    11-year-old sounding and calls it current."""

    def fetch(self, payload):
        def fetch_json(url, max_age):
            self.assertEqual(url, STATIONS_URL)
            return payload
        return fetch_json

    def test_a_stale_station_is_dropped_and_counted(self):
        eleven_years_ago = (OBSERVED_AT - dt.timedelta(days=4088)).replace(tzinfo=None).isoformat()
        payload = [record(), record(time=eleven_years_ago, station={"code": "OLD01"})]
        bundle = build_ionosonde_bundle(self.fetch(payload), observed_at=OBSERVED_AT)
        self.assertEqual([s["code"] for s in bundle["stations"]], ["TS001"])
        self.assertEqual(bundle["staleStationCount"], 1)
        self.assertEqual(bundle["upstreamStationCount"], 2)

    def test_the_freshness_limit_is_hours_not_days(self):
        """A station silent for three hours has missed at least a dozen
        soundings - 13 of 101 records changed timestamp inside a 4-minute
        window - and is not 'current' by any reading."""
        self.assertEqual(FRESH_LIMIT_MINUTES, 180)

    def test_a_station_just_inside_the_limit_survives(self):
        edge = (OBSERVED_AT - dt.timedelta(minutes=FRESH_LIMIT_MINUTES - 1)).replace(tzinfo=None).isoformat()
        bundle = build_ionosonde_bundle(self.fetch([record(time=edge)]), observed_at=OBSERVED_AT)
        self.assertEqual(len(bundle["stations"]), 1)

    def test_a_payload_that_is_not_a_list_is_an_error_not_an_empty_network(self):
        """An upstream that changes shape must stop the lane, not quietly
        publish zero stations - which would read as 'the network is down'."""
        with self.assertRaises(RuntimeError):
            build_ionosonde_bundle(self.fetch({"stations": []}), observed_at=OBSERVED_AT)

    def test_the_bundle_carries_its_attribution_and_says_it_is_an_aggregator(self):
        """GIRO's Rules of the Road require the data provider be acknowledged,
        and kc2g is not the authority. Both facts travel with the data."""
        bundle = build_ionosonde_bundle(self.fetch([record()]), observed_at=OBSERVED_AT)
        self.assertIn("GIRO", bundle["attribution"])
        self.assertIn("CC BY-NC-SA", bundle["attribution"])
        self.assertIn("aggregator, not the authority", bundle["sourceNote"])
        self.assertEqual(bundle["evidence"], "observed")


if __name__ == "__main__":
    unittest.main()
