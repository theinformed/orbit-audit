"""Storm-index tests driven by the real live payloads, with no network.

`tests/data/storm-indices-2026-08-08.json` is verbatim upstream JSON captured
on bigmem-PC at 2026-08-08T02:41:20Z: NOAA's modelled Geospace Dst, NOAA's
republished Kyoto quicklook Dst, the USGS geomagnetism web service, and the
tail of NOAA's propagated solar wind.  Nothing in it is synthetic.

Two things this file is deliberately careful about, both because this codebase
has a documented history of green tests over code paths that never execute:

* every parser test runs against the **real shape** of the product, not a
  hand-written stub that happens to match the parser; and
* the physics tests check the published check values from
  `docs/magnetosphere-realism-design.md`, so a coefficient typo fails here
  rather than shipping a plausible-looking wrong number.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.storm_indices import (  # noqa: E402
    DPS_JOULES_PER_NT,
    NEWELL_CALIBRATION,
    NEWELL_CALIBRATION_NOTE,
    build_storm_indices,
    classify_storm_phase,
    clock_angle_degrees,
    akasofu_epsilon_gw,
    boyle_cross_polar_cap_kv,
    derive_driver_terms,
    dynamic_pressure_npa,
    fetch_storm_sources,
    magnetic_pressure_npa,
    newell_coupling,
    parse_swpc_dst,
    parse_usgs_dst,
    pressure_corrected_dst,
    ring_current_energy_joules,
    storm_source_records,
    thin_series,
)

FIXTURE = json.loads((ROOT / "tests" / "data" / "storm-indices-2026-08-08.json").read_text())
CAPTURED_AT = dt.datetime(2026, 8, 8, 2, 41, 20, tzinfo=dt.timezone.utc)


def latest_driver() -> dict[str, object]:
    header = FIXTURE["propagatedSolarWindHeader"]
    return dict(zip(header, FIXTURE["propagatedSolarWindTail"][-1]))


class DerivedQuantities(unittest.TestCase):
    def test_dynamic_pressure_matches_the_omni_convention(self):
        # 1.6726e-6 * 7.77 * 265.9^2
        self.assertAlmostEqual(dynamic_pressure_npa(7.77, 265.9), 0.918861, places=5)

    def test_dynamic_pressure_rejects_a_zero_speed_rather_than_returning_zero(self):
        self.assertIsNone(dynamic_pressure_npa(7.77, 0.0))
        self.assertIsNone(dynamic_pressure_npa(None, 400.0))
        self.assertIsNone(dynamic_pressure_npa(5.0, float("nan")))

    def test_magnetic_pressure_is_b_squared_over_two_mu_zero(self):
        # 10 nT -> (1e-8 T)^2 / (2 * 4pi e-7) = 3.9789e-5 Pa*1e9 = 0.039789 nPa
        self.assertAlmostEqual(magnetic_pressure_npa(10.0), 0.0397887, places=6)

    def test_clock_angle_uses_the_northward_branch_fix(self):
        # Purely northward IMF is clock angle zero, purely southward is 180.
        self.assertAlmostEqual(clock_angle_degrees(0.0, 5.0), 0.0, places=6)
        self.assertAlmostEqual(clock_angle_degrees(0.0, -5.0), 180.0, places=6)
        # Duskward By with northward Bz sits in the first quadrant, and the
        # mirror case must land in the fourth, not be folded back into the
        # first. A naive atan(|By|/Bz) gets exactly this wrong.
        self.assertAlmostEqual(clock_angle_degrees(5.0, 5.0), 45.0, places=6)
        self.assertAlmostEqual(clock_angle_degrees(-5.0, 5.0), 315.0, places=6)
        self.assertAlmostEqual(clock_angle_degrees(5.0, -5.0), 135.0, places=6)
        self.assertAlmostEqual(clock_angle_degrees(-5.0, -5.0), 225.0, places=6)

    def test_clock_angle_is_undefined_with_no_transverse_field(self):
        self.assertIsNone(clock_angle_degrees(0.0, 0.0))

    def test_newell_is_zero_for_purely_northward_imf_and_grows_southward(self):
        self.assertAlmostEqual(newell_coupling(400.0, 0.0, 5.0), 0.0, places=9)
        southward = newell_coupling(400.0, 0.0, -5.0)
        assert southward is not None
        self.assertGreater(southward, 0.0)

    def test_the_published_band_scale_is_conditions_not_a_bz_lookup(self):
        """The ladder cannot be reproduced at any one solar-wind speed.

        The design document lists an IMF Bz beside each published value, which
        invites reading the ladder as a function of Bz. It is not: solving each
        published value for the speed that would produce it at By = 0 gives a
        speed that climbs monotonically from about 400 to about 1000 km/s. That
        is a coherent ladder of *conditions*, and this test pins it so nobody
        later re-labels the scale as a Bz mapping and puts a wrong number on
        screen.
        """
        speeds = []
        for entry in NEWELL_CALIBRATION:
            if entry["value"] == 0:
                continue
            bz = float(entry["representativeBzNt"])
            reference = newell_coupling(400.0, 0.0, bz)
            assert reference is not None
            speeds.append(400.0 * (float(entry["value"]) / reference) ** 0.75)
        self.assertEqual(speeds, sorted(speeds))
        self.assertGreater(speeds[0], 395.0)
        self.assertLess(speeds[0], 420.0)
        self.assertGreater(speeds[-1], 900.0)
        self.assertLess(speeds[-1], 1100.0)
        # And the honesty note travels with the numbers.
        self.assertIn("not a lookup table", NEWELL_CALIBRATION_NOTE)

    def test_epsilon_and_boyle_stay_finite_and_ordered(self):
        quiet = akasofu_epsilon_gw(400.0, 0.0, 0.0, 5.0)
        storm = akasofu_epsilon_gw(400.0, 0.0, 0.0, -15.0)
        assert quiet is not None and storm is not None
        self.assertAlmostEqual(quiet, 0.0, places=9)
        self.assertGreater(storm, 100.0)  # Akasofu's own substorm threshold
        potential = boyle_cross_polar_cap_kv(400.0, 0.0, 0.0, -15.0)
        assert potential is not None
        # Boyle is deliberately uncapped so the saturation line can be drawn.
        self.assertGreater(potential, 100.0)

    def test_dps_constant_is_the_published_four_times_ten_to_the_thirteen(self):
        self.assertAlmostEqual(DPS_JOULES_PER_NT / 1e13, 3.892, places=3)
        energy = ring_current_energy_joules(-100.0)
        assert energy is not None
        self.assertAlmostEqual(energy / 1e15, 3.892, places=3)

    def test_a_positive_dst_is_not_reported_as_ring_current_energy(self):
        # A positive excursion is magnetopause compression, not a ring current.
        self.assertEqual(ring_current_energy_joules(25.0), 0.0)

    def test_the_two_pressure_corrections_disagree_by_eighteen_nt_at_a_shock(self):
        corrected = pressure_corrected_dst(-100.0, 10.0)
        assert corrected is not None
        self.assertAlmostEqual(corrected["obrienMcPherronNt"], -112.0, places=1)
        self.assertAlmostEqual(corrected["burtonNt"], -130.0, places=1)
        self.assertAlmostEqual(
            corrected["burtonNt"] - corrected["obrienMcPherronNt"], -18.0, places=1
        )


class LivePayloadParsing(unittest.TestCase):
    def test_the_noaa_modelled_series_parses_and_runs_ahead_of_capture_time(self):
        samples = parse_swpc_dst(FIXTURE["noaaModelDst"])
        self.assertGreater(len(samples), 100)
        last = dt.datetime.fromisoformat(samples[-1]["at"].replace("Z", "+00:00"))
        lead_minutes = (last - CAPTURED_AT).total_seconds() / 60
        # The product's whole point: a nowcast issued into the future.
        self.assertGreater(lead_minutes, 30)
        self.assertLess(lead_minutes, 120)

    def test_the_kyoto_hourly_series_parses_on_the_hour(self):
        samples = parse_swpc_dst(FIXTURE["kyotoDst"])
        self.assertGreater(len(samples), 100)
        for sample in samples:
            self.assertTrue(sample["at"].endswith(":00:00Z"), sample["at"])

    def test_the_header_row_shape_parses_identically(self):
        # SWPC products appear in both shapes; neither may be assumed.
        objects = FIXTURE["kyotoDst"][:5]
        as_rows = [["time_tag", "dst"]] + [[row["time_tag"], row["dst"]] for row in objects]
        self.assertEqual(parse_swpc_dst(objects), parse_swpc_dst(as_rows))

    def test_usgs_dst3_parses_and_is_fresher_than_dst4(self):
        three = parse_usgs_dst(FIXTURE["usgsDst"], "Dst3")
        four = parse_usgs_dst(FIXTURE["usgsDst"], "Dst4")
        self.assertTrue(three and four)
        self.assertGreater(three[-1]["at"], four[-1]["at"])

    def test_an_all_null_usgs_response_yields_nothing_rather_than_an_empty_trace(self):
        # The USGS archive is a ~30-day rolling window and answers a request
        # outside it with HTTP 200 and a full-length array of nulls. Treating
        # 200 as "data present" would publish a present-but-empty observed
        # series on top of the modelled one.
        payload = json.loads(json.dumps(FIXTURE["usgsDst"]))
        for series in payload["values"]:
            series["values"] = [None] * len(series["values"])
        self.assertEqual(parse_usgs_dst(payload, "Dst3"), [])

    def test_an_unknown_element_is_not_silently_substituted(self):
        self.assertEqual(parse_usgs_dst(FIXTURE["usgsDst"], "DST"), [])

    def test_junk_payloads_parse_to_nothing_instead_of_raising(self):
        for payload in (None, {}, [], [{}], "nope", [["time_tag"], ["oops"]]):
            self.assertEqual(parse_swpc_dst(payload), [])
        for payload in (None, [], {"times": 3}, {"times": [], "values": {}}):
            self.assertEqual(parse_usgs_dst(payload), [])


class SeriesThinning(unittest.TestCase):
    def test_thinning_keeps_the_newest_sample_per_bucket_and_drops_old_ones(self):
        base = dt.datetime(2026, 8, 8, 2, 0, tzinfo=dt.timezone.utc)
        samples = [
            {"at": (base + dt.timedelta(minutes=minute)).isoformat().replace("+00:00", "Z"),
             "dstNt": float(minute)}
            for minute in range(0, 60)
        ]
        thinned = thin_series(samples, cadence_minutes=15, history_hours=1.0, now=base + dt.timedelta(minutes=59))
        self.assertEqual([sample["dstNt"] for sample in thinned], [14.0, 29.0, 44.0, 59.0])

    def test_bucket_edges_do_not_move_when_the_window_moves(self):
        # Rounded buckets that shift with the window are a defect class this
        # project has already shipped once; buckets here are floor divisions of
        # absolute epoch seconds and must be stable.
        base = dt.datetime(2026, 8, 8, 2, 0, tzinfo=dt.timezone.utc)
        samples = [
            {"at": (base + dt.timedelta(minutes=minute)).isoformat().replace("+00:00", "Z"),
             "dstNt": float(minute)}
            for minute in range(0, 60)
        ]
        first = thin_series(samples, cadence_minutes=15, history_hours=10.0, now=base + dt.timedelta(minutes=59))
        second = thin_series(samples, cadence_minutes=15, history_hours=10.0, now=base + dt.timedelta(minutes=180))
        self.assertEqual(first, second)


class StormPhase(unittest.TestCase):
    @staticmethod
    def series(values: list[float], *, start: dt.datetime) -> list[dict[str, object]]:
        return [
            {"at": (start + dt.timedelta(hours=index)).isoformat().replace("+00:00", "Z"), "dstNt": value}
            for index, value in enumerate(values)
        ]

    def test_a_flat_quiet_trace_is_labelled_quiet(self):
        start = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
        result = classify_storm_phase(self.series([2, 1, 3, 0, -4, 5], start=start), now=start + dt.timedelta(hours=5))
        self.assertEqual(result["label"], "quiet")
        self.assertIsNone(result["intensity"])

    def test_a_positive_excursion_before_any_depression_is_the_initial_phase(self):
        start = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
        result = classify_storm_phase(self.series([2, 6, 14, 22], start=start), now=start + dt.timedelta(hours=3))
        self.assertEqual(result["label"], "initial")

    def test_a_falling_depressed_trace_is_the_main_phase(self):
        start = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
        result = classify_storm_phase(self.series([10, -5, -35, -70], start=start), now=start + dt.timedelta(hours=3))
        self.assertEqual(result["label"], "main")
        self.assertEqual(result["intensity"], "moderate")
        self.assertAlmostEqual(float(result["minimumNt"]), -70.0)

    def test_a_rising_trace_after_the_minimum_is_recovery(self):
        start = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
        result = classify_storm_phase(
            self.series([10, -35, -120, -90, -60], start=start), now=start + dt.timedelta(hours=4)
        )
        self.assertEqual(result["label"], "recovery")
        self.assertEqual(result["intensity"], "intense")

    def test_no_samples_gives_unknown_rather_than_quiet(self):
        result = classify_storm_phase([], now=dt.datetime(2026, 8, 8, tzinfo=dt.timezone.utc))
        self.assertEqual(result["label"], "unknown")


class ArtifactAssembly(unittest.TestCase):
    def block(self, **overrides):
        arguments = {
            "model_dst_raw": FIXTURE["noaaModelDst"],
            "usgs_dst_raw": FIXTURE["usgsDst"],
            "kyoto_dst_raw": FIXTURE["kyotoDst"],
            "driver": latest_driver(),
            "now": CAPTURED_AT,
        }
        arguments.update(overrides)
        return build_storm_indices(**arguments)

    def test_the_three_dst_series_stay_separate(self):
        block = self.block()
        dst = block["dst"]
        self.assertEqual(dst["modelled"]["status"], "model")
        self.assertEqual(dst["observed"]["status"], "observed")
        self.assertEqual(dst["kyoto"]["status"], "observed")
        # Three distinct, populated traces, and none of them shares a list.
        for key in ("modelled", "observed", "kyoto"):
            self.assertTrue(dst[key]["series"], key)
        self.assertNotEqual(dst["modelled"]["series"], dst["observed"]["series"])
        self.assertNotEqual(dst["observed"]["series"], dst["kyoto"]["series"])

    def test_the_modelled_series_publishes_its_forward_lead(self):
        block = self.block()
        lead = block["dst"]["modelled"]["forwardLeadMinutes"]
        self.assertIsNotNone(lead)
        self.assertGreater(lead, 30)

    def test_the_observed_series_publishes_its_latency(self):
        block = self.block()
        latency = block["dst"]["observed"]["latencySeconds"]
        self.assertIsNotNone(latency)
        self.assertLess(latency, 20 * 60)

    def test_kyoto_carries_its_doi_wherever_it_appears(self):
        block = self.block()
        self.assertIn("10.17593/14515-74000", block["dst"]["kyoto"]["citation"])
        rows = storm_source_records(block)
        kyoto_rows = [row for row in rows if "Kyoto" in row["product"]]
        self.assertTrue(kyoto_rows)
        self.assertIn("10.17593/14515-74000", kyoto_rows[0]["citation"])

    def test_the_derived_coupling_matches_the_live_drivers(self):
        block = self.block()
        driver = latest_driver()
        derived = block["derived"]
        self.assertAlmostEqual(
            derived["clockAngleDeg"],
            round(clock_angle_degrees(float(driver["by"]), float(driver["bz"])), 1),
            places=6,
        )
        self.assertAlmostEqual(
            derived["newellCoupling"],
            round(newell_coupling(float(driver["speed"]), float(driver["by"]), float(driver["bz"])), 1),
            places=6,
        )
        self.assertAlmostEqual(
            block["drivers"]["dynamicPressureNpa"],
            round(dynamic_pressure_npa(float(driver["density"]), float(driver["speed"])), 4),
            places=6,
        )

    def test_the_imf_vector_survives_instead_of_being_discarded(self):
        # The entire point of the change: bx, by, bt and the velocity vector
        # used to be read from NOAA and thrown away.
        drivers = self.block()["drivers"]
        for key in ("bxNt", "byNt", "bzGsmNt", "btNt", "vxKps", "vyKps", "vzKps"):
            self.assertIsNotNone(drivers[key], key)

    def test_a_withheld_driver_removes_the_coupling_rather_than_inventing_it(self):
        block = self.block(driver=None)
        self.assertIsNone(block["derived"])
        self.assertIsNone(block["drivers"])
        # The Dst traces are independent of the solar-wind guard and stay.
        self.assertTrue(block["dst"]["observed"]["series"])

    def test_ring_current_energy_prefers_the_observed_index(self):
        block = self.block()
        self.assertEqual(block["ringCurrent"]["energySourceSeries"], "usgs-dst3-observed")
        self.assertIn("Dessler-Parker-Sckopke", block["ringCurrent"]["method"])
        self.assertIn("factor of two", block["ringCurrent"]["uncertainty"])

    def test_a_dead_source_removes_only_its_own_trace(self):
        block = self.block(usgs_dst_raw=None)
        self.assertEqual(block["dst"]["observed"]["series"], [])
        self.assertIsNone(block["dst"]["observed"]["latestNt"])
        self.assertTrue(block["dst"]["modelled"]["series"])
        self.assertEqual(block["ringCurrent"]["energySourceSeries"], "noaa-geospace-modelled")
        self.assertEqual(len(storm_source_records(block)), 2)

    def test_every_source_row_names_a_url_and_a_time(self):
        for row in storm_source_records(self.block()):
            self.assertTrue(row["url"].startswith("https://"))
            self.assertTrue(row["observedAt"].endswith("Z"))

    def test_the_block_is_json_serialisable_and_small(self):
        encoded = json.dumps(self.block(), separators=(",", ":"))
        self.assertLess(len(encoded), 120_000)
        self.assertEqual(json.loads(encoded)["kind"], "geomagnetic-storm-indices")


class FetchOrchestration(unittest.TestCase):
    def test_one_dead_endpoint_does_not_stop_the_others(self):
        calls: list[str] = []

        def fetcher(url: str, max_age_seconds: int):
            calls.append(url)
            if "geomag.usgs.gov" in url:
                raise RuntimeError("HTTP 503")
            return [{"time_tag": "2026-08-08T02:00:00", "dst": 7}]

        results = fetch_storm_sources(fetcher)
        self.assertEqual(len(calls), 3)
        self.assertIsNone(results["usgs"])
        self.assertIn("usgs", results["errors"])
        self.assertIsNotNone(results["model"])
        self.assertIsNotNone(results["kyoto"])

    def test_each_endpoint_is_requested_exactly_once_per_cycle(self):
        # CelesTrak banned this project once for retrying a failing request.
        # Nothing here may loop on an upstream.
        calls: list[str] = []

        def fetcher(url: str, max_age_seconds: int):
            calls.append(url)
            raise RuntimeError("HTTP 500")

        fetch_storm_sources(fetcher)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(len(calls), 3)


class DriverTerms(unittest.TestCase):
    def test_derive_driver_terms_reads_noaa_column_names_directly(self):
        header = FIXTURE["propagatedSolarWindHeader"]
        for values in FIXTURE["propagatedSolarWindTail"]:
            record = dict(zip(header, values))
            terms = derive_driver_terms(record)
            self.assertIsNotNone(terms["clockAngleDeg"])
            self.assertIsNotNone(terms["newellCoupling"])
            self.assertTrue(math.isfinite(terms["dynamicPressureNpa"]))

    def test_a_missing_column_degrades_that_term_only(self):
        record = dict(zip(FIXTURE["propagatedSolarWindHeader"], FIXTURE["propagatedSolarWindTail"][-1]))
        record["by"] = None
        terms = derive_driver_terms(record)
        self.assertIsNone(terms["clockAngleDeg"])
        self.assertIsNone(terms["newellCoupling"])
        self.assertIsNotNone(terms["dynamicPressureNpa"])


if __name__ == "__main__":
    unittest.main()


class ReleaseWiring(unittest.TestCase):
    """The pipeline functions the browser actually reads, on the real payload.

    These call `pipeline/build_release.py` itself rather than a copy of its
    logic, because the defect class this project keeps producing is a green
    test over a path production never takes.
    """

    def setUp(self):
        from pipeline.build_release import newest_propagated_record, propagated_driver_series

        self.propagated_driver_series = propagated_driver_series
        self.newest_propagated_record = newest_propagated_record
        self.raw = [FIXTURE["propagatedSolarWindHeader"], *FIXTURE["propagatedSolarWindTail"]]

    def test_the_published_driver_series_now_carries_the_imf_vector(self):
        rows = self.propagated_driver_series(self.raw, history_hours=1_000_000)
        self.assertTrue(rows)
        row = rows[-1]
        for key in ("bxNt", "byNt", "btNt", "magneticPressureNpa", "clockAngleDeg", "newellCoupling"):
            self.assertIsNotNone(row[key], key)
        # And the columns it already had are untouched.
        for key in ("speedKps", "densityCm3", "bzGsmNt", "dynamicPressureNpa", "subsolarStandoffRe", "flaringAlpha"):
            self.assertIsNotNone(row[key], key)

    def test_the_series_clock_angle_agrees_with_the_module(self):
        rows = self.propagated_driver_series(self.raw, history_hours=1_000_000)
        header = FIXTURE["propagatedSolarWindHeader"]
        by_arrival = {
            iso: dict(zip(header, values))
            for values in FIXTURE["propagatedSolarWindTail"]
            if (iso := str(dict(zip(header, values))["propagated_time_tag"]))
        }
        for row in rows:
            source = by_arrival[row["validAt"]]
            self.assertAlmostEqual(
                row["clockAngleDeg"],
                round(clock_angle_degrees(float(source["by"]), float(source["bz"])), 1),
                places=6,
            )

    def test_the_raw_row_recovered_for_the_storm_block_is_the_guarded_one(self):
        rows = self.propagated_driver_series(self.raw, history_hours=1_000_000)
        # Simulate the guard having truncated to the second-newest sample.
        truncated = rows[:-1]
        record = self.newest_propagated_record(self.raw, truncated[-1]["validAt"])
        self.assertIsNotNone(record)
        self.assertEqual(
            dt.datetime.fromisoformat(str(record["propagated_time_tag"]).replace("Z", "+00:00")),
            dt.datetime.fromisoformat(truncated[-1]["validAt"].replace("Z", "+00:00")),
        )

    def test_a_fully_withheld_series_recovers_no_record(self):
        self.assertIsNone(self.newest_propagated_record(self.raw, None))
        self.assertIsNone(self.newest_propagated_record(self.raw, "1999-01-01T00:00:00Z"))


class PhaseBaseline(unittest.TestCase):
    """The initial-phase rule must survive a series with an offset baseline.

    USGS Dst3 read +20.5 nT on 2026-08-08 while Kyoto read +7 for the same
    hour. They are both correct: they are different station sets with different
    baselines. A classifier that tested an absolute level would have labelled a
    completely quiet day a sudden commencement.
    """

    @staticmethod
    def series(values, *, start):
        return [
            {"at": (start + dt.timedelta(hours=index)).isoformat().replace("+00:00", "Z"), "dstNt": value}
            for index, value in enumerate(values)
        ]

    def test_a_high_but_flat_trace_is_quiet_not_a_sudden_commencement(self):
        start = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
        result = classify_storm_phase(
            self.series([19, 20, 21, 19, 20, 21, 20, 21], start=start),
            now=start + dt.timedelta(hours=7),
        )
        self.assertEqual(result["label"], "quiet")
        self.assertIsNotNone(result["baselineNt"])

    def test_the_same_step_is_detected_whatever_the_baseline(self):
        start = dt.datetime(2026, 8, 7, 12, tzinfo=dt.timezone.utc)
        step = [0, 0, 0, 0, 0, 0, 5, 20]
        for offset in (-25, 0, 20):
            result = classify_storm_phase(
                self.series([value + offset for value in step], start=start),
                now=start + dt.timedelta(hours=7),
            )
            self.assertEqual(result["label"], "initial", msg=f"offset {offset}")

    def test_the_phase_names_the_trace_it_read(self):
        block = build_storm_indices(
            model_dst_raw=FIXTURE["noaaModelDst"],
            usgs_dst_raw=FIXTURE["usgsDst"],
            kyoto_dst_raw=FIXTURE["kyotoDst"],
            driver=latest_driver(),
            now=CAPTURED_AT,
        )
        # Kyoto is the index the thresholds are defined on, so it goes first.
        self.assertEqual(block["phase"]["series"], "kyoto-quicklook")
        self.assertEqual(block["phase"]["label"], "quiet")
        self.assertIn("baselines", block["phase"]["baselineNote"])

    def test_a_missing_kyoto_trace_falls_back_and_says_so(self):
        block = build_storm_indices(
            model_dst_raw=FIXTURE["noaaModelDst"],
            usgs_dst_raw=FIXTURE["usgsDst"],
            kyoto_dst_raw=None,
            driver=latest_driver(),
            now=CAPTURED_AT,
        )
        self.assertEqual(block["phase"]["series"], "noaa-geospace-modelled")
