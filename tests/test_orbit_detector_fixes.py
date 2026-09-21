"""Offline F3/F1/F4 mechanics. Full-archive acceptance is a separate red suite."""
import contextlib
import io
import statistics
import unittest
from pathlib import Path
from dataclasses import replace
from unittest import mock

from pipeline import orbit_campaigns as oc, orbit_events as oe, orbit_release as release
from test_orbit_campaigns import BASE_MS, DAY_MS, intervals, series


# DETECTOR-DESIGN.md, predeclared table (names verbatim):
# Era: pre-2013 | 2013-2020 | 2021+
# Perigee band: < 500 | 500–800 | 800–1,500 | 1,500–30,000 | GEO+
# Minimum passive intervals per stratum: 200,000
ERAS = ("pre-2013", "2013-2020", "2021+")
BANDS = ("<500", "500-800", "800-1500", "1500-30000", "GEO+")


class DetectorFixTests(unittest.TestCase):
    def test_all_unmeasured_fixes_ship_disabled(self):
        self.assertEqual(oc.detector_flags(), {
            "INCLINATION_FLOOR_TAIL_AWARE": False,
            "MATCHED_CONTROL_STRATA_ENABLED": False,
            "DECLINE_AFTER_TRACKING_GAP": False,
        })

    def test_inclination_tail_and_geo_exemption_and_other_elements(self):
        residuals = [0.0] * 30 + [1e-4] * 60 + [0.01] * 10
        mad = statistics.median(residuals) * 1.4826
        self.assertEqual(oc._residual_floor("inclination", residuals, 900), mad)
        with mock.patch.object(oc, "INCLINATION_FLOOR_TAIL_AWARE", True):
            for altitude in (400, 600, 1000, 10000, 30000):
                self.assertGreaterEqual(oc._residual_floor("inclination", residuals, altitude), 2e-3)
            self.assertEqual(oc._residual_floor("inclination", residuals, 35786), mad)
            for element in ("semiMajorAxis", "eccentricity"):
                self.assertEqual(oc._residual_floor(element, residuals, 900).hex(), mad.hex())
            self.assertEqual(oc._residual_floor("inclination", [], 900), 0)

    def test_production_pass_supplies_residuals_and_median_perigee(self):
        observed = intervals(series(steps={45: 2000}))
        original = oc._residual_floor
        with mock.patch.object(oc, "INCLINATION_FLOOR_TAIL_AWARE", True), \
                mock.patch.object(oc, "_residual_floor", wraps=original) as floor:
            oc.detect_object_events(observed, kappa=32)
        self.assertEqual({call.args[0] for call in floor.call_args_list}, set(oc.ELEMENTS))
        for call in floor.call_args_list:
            self.assertEqual(call.args[2], statistics.median(i.perigee_altitude_km for i in observed))
            self.assertEqual(len(call.args[1]), len(observed))

    def test_five_day_gap_declines_a_two_km_step_but_contiguous_step_survives(self):
        rows = series(steps={45.25: 2000})
        contiguous = intervals(rows)
        # Keep the epochs at days 40 and 45: exactly five days between arcs.
        gapped = intervals([row for row in rows if not BASE_MS + 40 * DAY_MS < row[0] < BASE_MS + 45 * DAY_MS])
        at = BASE_MS + 45 * DAY_MS
        self.assertTrue(any(e.start_ms == at for e in oc.detect_object_events(gapped, kappa=32)))
        diagnostics = {}
        log = io.StringIO()
        with mock.patch.object(oc, "DECLINE_AFTER_TRACKING_GAP", True), contextlib.redirect_stderr(log):
            found = oc.detect_object_events(gapped, kappa=32, diagnostics=diagnostics)
            unchanged = oc.detect_object_events(contiguous, kappa=32)
        self.assertFalse(any(e.start_ms == at for e in found))
        self.assertTrue(any(e.start_ms == at for e in unchanged))
        self.assertEqual(diagnostics["trackingGapDroppedIntervals"], 1)
        self.assertIn("dropped 1 interval(s)", log.getvalue())

    def test_gap_edge_and_every_tripped_channel_have_a_reason(self):
        observed = intervals(series(days=10))
        trip = oe.ChannelTest("inclination", .01, .0001, 100, 100, 20, True, True)
        tests = [trip, replace(trip, element="eccentricity"), replace(trip, tripped=False)]
        with mock.patch.object(oc, "DECLINE_AFTER_TRACKING_GAP", True):
            for gap, declined in ((3 * DAY_MS - 1, False), (3 * DAY_MS, True), (5 * DAY_MS, True)):
                pair = [observed[0], replace(observed[1], start_ms=observed[0].end_ms + gap)]
                result, reason = oc._decline_tracking_gap(tests, pair, 1)
                self.assertEqual(any(t.tripped for t in result), not declined)
                if declined:
                    self.assertIn("the fit is on a new arc", reason)
                    self.assertTrue(all(t.reason == reason for t in result[:2]))
                self.assertIsNone(result[2].reason)
            self.assertEqual(oc._decline_tracking_gap(tests, observed, 0)[0], tests)


class MatchedControlTests(unittest.TestCase):
    @staticmethod
    def measured():
        scan = oc.ArchivePass(passive_intervals=1_000_000, passive_flags=100,
                              payload_intervals=1_000_000, payload_flags=10_000)
        for era in ERAS:
            for band in BANDS:
                scan.strata[era, band] = oc.ArchivePass(
                    passive_intervals=200_000, passive_flags=10,
                    payload_intervals=200_000, payload_flags=2000)
        return scan

    def test_fifteen_strata_include_empty_and_failing_measurements(self):
        self.assertEqual(oc.CONTROL_ERAS, ERAS)
        self.assertEqual(oc.CONTROL_BANDS, BANDS)
        scan = self.measured()
        scan.strata.pop((ERAS[0], BANDS[0]))
        scan.strata[ERAS[1], BANDS[1]].passive_intervals = 199_999
        scan.strata[ERAS[2], BANDS[2]].passive_flags = 900
        measured = oc.control_rates_by_object(scan, kappa=32)
        self.assertTrue(measured["sufficientToLabel"])
        self.assertEqual(sum(len(bands) for bands in measured["strata"].values()), 15)
        for era, band in ((ERAS[0], BANDS[0]), (ERAS[1], BANDS[1]), (ERAS[2], BANDS[2])):
            block = measured["strata"][era][band]
            self.assertFalse(block["sufficientToLabel"])
            self.assertIsInstance(block["blockingReason"], str)
        self.assertIn("not measured", measured["trackingGapDroppedIntervals"])
        self.assertIn("not measured", measured["catalogueGeoNorthSouthKeepingEvents"])
        with mock.patch.object(oc, "DECLINE_AFTER_TRACKING_GAP", True):
            scan.tracking_gap_drops = 7
            self.assertEqual(oc.control_rates_by_object(scan, kappa=32)["trackingGapDroppedIntervals"], 7)

    def test_implausible_costs_pool_into_the_published_control(self):
        """M24: the full-population count now reaches the published block, the

        same way trackingGapDroppedIntervals and inclinationUncorroborated
        already do -- unconditionally, since no flag gates this counter.
        """
        scan = self.measured()
        scan.implausible_costs = 5
        self.assertEqual(oc.control_rates_by_object(scan, kappa=32)["implausibleCosts"], 5)

    def test_era_and_band_boundaries_follow_the_noise_floor(self):
        for date, era in (("2012-12-31T23:59:59Z", ERAS[0]), ("2013-01-01T00:00:00Z", ERAS[1]),
                          ("2020-12-31T23:59:59Z", ERAS[1]), ("2021-01-01T00:00:00Z", ERAS[2])):
            for altitude, band in ((500, BANDS[0]), (500.001, BANDS[1]), (800, BANDS[1]),
                                   (800.001, BANDS[2]), (1500, BANDS[2]), (1500.001, BANDS[3]),
                                   (30000, BANDS[3]), (30000.001, BANDS[4])):
                self.assertEqual(oc.control_stratum(oe._parse_iso_ms(date), altitude), {"era": era, "band": band})
        self.assertIsInstance(oc.control_stratum(None, 500), str)
        self.assertIsInstance(oc.control_stratum(BASE_MS, float("nan")), str)

    def test_note_counts_denominators_even_without_events_across_eras_and_bands(self):
        observed = intervals(series(steps={45: 2000}))
        first = [replace(i, start_ms=oe._parse_iso_ms("2012-12-30T00:00:00Z"),
                         perigee_altitude_km=900) for i in observed[:10]]
        second = observed[10:]
        events = oc.detect_object_events(observed, kappa=32)
        scan = oc.ArchivePass()
        for kind in ("DEBRIS", "ROCKET BODY", "PAYLOAD"):
            scan.note(kind, len(observed), len(events), oc._covered_days(observed),
                      observed=first + second, propulsive=events)
        self.assertEqual(scan.strata[ERAS[0], BANDS[2]].passive_intervals, 20)
        self.assertEqual(scan.strata[ERAS[0], BANDS[2]].passive_flags, 0)
        for attr in ("passive_intervals", "passive_flags", "payload_intervals", "payload_flags"):
            self.assertEqual(sum(getattr(s, attr) for s in scan.strata.values()), getattr(scan, attr))

    def test_publication_uses_unrounded_stratum_on_headlines_shards_and_honesty(self):
        scan = self.measured()
        scan.strata["2021+", "800-1500"].payload_flags = 1
        event = oc.detect_object_events(intervals(series(steps={45: 2000})), kappa=32)[0]
        scan.events = [replace(event, perigee_altitude_km=800.04)]
        # as_dict() displays 800.0, but the control must remain in 800-1500.
        self.assertEqual(scan.events[0].as_dict()["perigeeAltitudeKm"], 800.0)
        stubs = {
            "load_catalog": {1: {}},
            "archive_stats": {"lastCapture": "2026-09-09T00:00:00Z", "latestEpoch": "2026-09-09T00:00:00Z"},
            "load_intervals": [], "detect_events": [],
            "control_rates": {"sufficientToLabel": False},
            "coverage": {}, "kp_context": None, "read_series": {1: []},
            "observation_span_days": 0, "population_decay": [], "kp_series": [],
            "_density_if_possible": {}, "space_weather_gaps": [],
        }
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(oc, "MATCHED_CONTROL_STRATA_ENABLED", True))
            stack.enter_context(mock.patch.object(oc, "archive_maturity_from_scan", return_value={}))
            stack.enter_context(mock.patch.object(oc, "scan_archive", side_effect=AssertionError("no sweep")))
            for name, value in stubs.items():
                stack.enter_context(mock.patch.object(release, name, return_value=value))
            shards, bundle, _ = release.build_bundles(mock.Mock(), Path("unused"), scan=scan)
        headline = bundle["events"][0]
        full = shards[0]["objects"][0]["events"][0]
        for record in (headline, full):
            self.assertEqual(record["controlStratum"], {"era": "2021+", "band": "800-1500"})
            self.assertFalse(record["manoeuvreLabelPermitted"])
        self.assertIn("2021+ / 800-1500", full["card"]["honesty"])
        self.assertIn("candidate", full["card"]["honesty"])
        self.assertNotIn("This is a manoeuvre", full["card"]["honesty"])
        self.assertIn("Lower bound", full["deltaV"]["note"])

    def test_failed_stratum_cannot_borrow_pooled_pass_and_policy_is_all_strata_and(self):
        scan = self.measured()
        scan.strata[ERAS[0], BANDS[2]].payload_flags = 1
        controls = oc.control_rates_by_object(scan, kappa=32)
        record = {"objectType": "PAYLOAD", "signature": "inclination-change",
                  "startAt": "2005-01-01T00:00:00Z", "perigeeAltitudeKm": 900,
                  "tests": [{"tripped": True, "basis": "self-history"}]}
        self.assertTrue(controls["sufficientToLabel"])
        with mock.patch.object(oc, "MATCHED_CONTROL_STRATA_ENABLED", True):
            selected = release._controls_for(record, {}, controls)
            self.assertFalse(release._event_label_permitted(record, selected))
            self.assertEqual(selected["controlStratum"], {"era": ERAS[0], "band": BANDS[2]})
            policy = release._label_policy({"sufficientToLabel": True}, controls)
            self.assertFalse(policy["manoeuvreLabelPermitted"])
            self.assertFalse(policy["byBasis"]["byStratum"][ERAS[0]][BANDS[2]]["manoeuvreLabelPermitted"])
            record["startAt"] = "2024-01-01T00:00:00Z"
            selected = release._controls_for(record, {}, controls)
            self.assertTrue(release._event_label_permitted(record, selected))
            record["perigeeAltitudeKm"] = None
            self.assertFalse(release._event_label_permitted(record, release._controls_for(record, {}, controls)))


if __name__ == "__main__":
    unittest.main()
