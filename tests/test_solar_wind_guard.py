"""Replay the real May 2024 Gannon-storm L1 monitors through the guard.

Every number in `tests/data/gannon-2024-05-l1-monitors.json` is verbatim
archived measurement: DSCOVR's Faraday cup and magnetometer from NOAA's
`archive.data.noaa.gov` 1-minute netCDF products, and ACE SWEPAM from CDAWeb's
HAPI service.  Nothing in the fixture is synthetic, and no test here touches
the network.

The point of the file is that this codebase has a documented history of green
tests over code paths that never execute.  A guard written for the 2024-05-11
DSCOVR failure that has never been shown to fire on it is not verified, and a
guard that has never been shown to stay quiet at the genuine 2024-05-10 17:05
shock arrival is worse than useless -- it would suppress exactly the events the
site exists to show.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.solar_wind_guard import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    FieldSample,
    PlasmaSample,
    assess_solar_wind,
    assess_rtsw,
    dynamic_pressure_npa,
)

FIXTURE = json.loads((ROOT / "tests" / "data" / "gannon-2024-05-l1-monitors.json").read_text())
UTC = dt.timezone.utc


def _time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _load(*window_names: str) -> tuple[list[PlasmaSample], list[FieldSample]]:
    plasma: list[PlasmaSample] = []
    fields: list[FieldSample] = []
    for name in window_names:
        window = FIXTURE["windows"][name]
        for stamp, (speed, density, temperature, quality) in window["dscovrPlasma"].items():
            plasma.append(
                PlasmaSample(
                    spacecraft="DSCOVR",
                    observed_at=_time(stamp),
                    speed_kps=speed,
                    density_cm3=density,
                    temperature_k=temperature,
                    product="DSCOVR FC f1m",
                    source_quality=quality,
                    source_active=True,
                )
            )
        for stamp, (speed, density, temperature) in window["acePlasma"].items():
            plasma.append(
                PlasmaSample(
                    spacecraft="ACE",
                    observed_at=_time(stamp),
                    speed_kps=speed,
                    density_cm3=density,
                    temperature_k=temperature,
                    product="ACE SWEPAM H0",
                )
            )
        for stamp, (bt, bz, quality) in window["dscovrField"].items():
            fields.append(
                FieldSample(
                    spacecraft="DSCOVR",
                    observed_at=_time(stamp),
                    bt_nt=bt,
                    bz_gsm_nt=bz,
                    product="DSCOVR MAG m1m",
                    source_quality=quality,
                )
            )
    return plasma, fields


def _assess(when: str, *windows: str):
    plasma, fields = _load(*windows)
    return assess_solar_wind(
        primary_spacecraft="DSCOVR",
        plasma=plasma,
        field_samples=fields,
        now=_time(when),
    )


class TheDefectItself(unittest.TestCase):
    """First establish, from the archive, that the old rule really was unsafe."""

    def test_dscovr_reported_nominal_quality_while_its_plasma_was_wrong(self) -> None:
        window = FIXTURE["windows"]["fault-sustained-2024-05-11"]
        nominal_but_wrong = 0
        for stamp, (speed, _density, _temperature, quality) in window["dscovrPlasma"].items():
            ace = window["acePlasma"].get(stamp)
            if ace is None or speed is None or not ace[0]:
                continue
            if quality == 0 and abs(speed - ace[0]) / ace[0] > 0.25:
                nominal_but_wrong += 1
        self.assertGreater(
            nominal_but_wrong,
            30,
            "the archived hour must contain minutes where DSCOVR said overall_quality=0 "
            "and still disagreed with ACE by more than 25%",
        )

    def test_the_old_rule_would_have_published_the_wrong_pressure(self) -> None:
        """And therefore an expanded magnetosphere during a record compression."""
        window = FIXTURE["windows"]["fault-sustained-2024-05-11"]
        ratios: list[float] = []
        standoffs: list[tuple[float, float]] = []
        for stamp, (speed, density, _temperature, quality) in window["dscovrPlasma"].items():
            ace = window["acePlasma"].get(stamp)
            if ace is None or speed is None or density is None:
                continue
            # The rule this guard replaced: trust `active and overall_quality == 0`.
            self.assertEqual(quality, 0)
            wrong = dynamic_pressure_npa(density, speed)
            truth = dynamic_pressure_npa(ace[1], ace[0])
            ratios.append(truth / wrong)
            # Shue (1998) scales the subsolar standoff as Pdyn ** (-1/6.6).
            standoffs.append((wrong ** (-1 / 6.6), truth ** (-1 / 6.6)))

        self.assertGreater(len(ratios), 50)
        ratios.sort()
        median_ratio = ratios[len(ratios) // 2]
        self.assertGreater(
            median_ratio,
            5.0,
            "DSCOVR's reported dynamic pressure must be several times too low across this hour",
        )
        # Every minute would have drawn the boundary further out than the truth.
        self.assertTrue(all(wrong > truth for wrong, truth in standoffs))


class TheGuardFiresOnTheRealFailure(unittest.TestCase):
    def test_disputed_within_fifteen_minutes_of_the_1343_failure(self) -> None:
        verdict = _assess("2024-05-11T13:55:00Z", "fault-onset-2024-05-11")
        self.assertEqual(verdict.verdict, "disputed")
        self.assertFalse(verdict.publish_plasma)
        self.assertFalse(verdict.publish_derived)
        self.assertIsNone(verdict.speed_kps)
        self.assertIsNone(verdict.density_cm3)

    def test_the_failure_is_caught_by_the_magnetometer_not_by_the_quality_flag(self) -> None:
        verdict = _assess("2024-05-11T13:55:00Z", "fault-onset-2024-05-11")
        step = next(check for check in verdict.checks if check.name == "step-coherence")
        self.assertEqual(step.outcome, "fail")
        self.assertGreater(step.numbers["speedStepFraction"], 0.25)
        self.assertGreater(step.numbers["densityStepFraction"], 0.80)
        self.assertLess(step.numbers["fieldStepFraction"], 0.05)
        # And the upstream flag says nothing is wrong, which is the whole point.
        self.assertIn(0, next(c for c in verdict.checks if c.name == "upstream-self-report").numbers["qualityFlags"])

    def test_no_second_spacecraft_was_reporting_at_the_onset(self) -> None:
        """The step check has to carry the failure alone for the first hours."""
        verdict = _assess("2024-05-11T13:55:00Z", "fault-onset-2024-05-11")
        cross = next(check for check in verdict.checks if check.name == "cross-source")
        self.assertEqual(cross.outcome, "skipped")

    def test_sustained_failure_is_caught_by_ace_disagreement(self) -> None:
        verdict = _assess("2024-05-11T15:45:00Z", "fault-sustained-2024-05-11")
        self.assertEqual(verdict.verdict, "disputed")
        cross = next(check for check in verdict.checks if check.name == "cross-source")
        self.assertEqual(cross.outcome, "fail")
        witness = next(row for row in verdict.comparisons if row.spacecraft == "ACE")
        self.assertFalse(witness.agrees)
        self.assertGreater(witness.speed_difference_fraction, 0.35)

    def test_the_visitor_is_told_why(self) -> None:
        verdict = _assess("2024-05-11T15:45:00Z", "fault-sustained-2024-05-11")
        self.assertIn("withheld", verdict.notice)
        self.assertIn("ACE", verdict.notice)
        self.assertIn("magnetopause standoff", verdict.notice)
        self.assertIn("(disputed)", verdict.resolved_label)
        published = verdict.as_dict()
        self.assertEqual(published["verdict"], "disputed")
        self.assertFalse(published["publishesDerivedPressure"])
        self.assertTrue(any(check["outcome"] == "fail" for check in published["checks"]))
        self.assertTrue(published["faultOnset"])

    def test_the_physical_bounds_do_not_catch_it(self) -> None:
        """Stated explicitly: bounds alone are not a guard.

        Every faulted value sits comfortably inside the plausible ranges. If
        this test ever starts failing because the bounds were tightened, the
        bounds have been tightened far enough to reject real solar wind.
        """
        verdict = _assess("2024-05-11T15:45:00Z", "fault-sustained-2024-05-11")
        bounds = next(check for check in verdict.checks if check.name == "physical-bounds")
        self.assertEqual(bounds.outcome, "pass")


class TheGuardStaysQuietWhenItShould(unittest.TestCase):
    def test_quiet_conditions_publish_normally(self) -> None:
        verdict = _assess("2024-05-03T12:00:00Z", "quiet-2024-05-03")
        self.assertEqual(verdict.verdict, "ok")
        self.assertTrue(verdict.publish_plasma)
        self.assertTrue(verdict.publish_derived)
        self.assertIsNotNone(verdict.speed_kps)

    def test_the_genuine_shock_arrival_is_not_suppressed(self) -> None:
        """2024-05-10 16:35 at L1 / 17:05 at the bow-shock nose.

        A naive rate-of-change rule rejects this. The guard must not: the field
        stepped with the plasma, which is exactly what a fast forward shock does.
        """
        for stamp in ("2024-05-10T16:45:00Z", "2024-05-10T16:55:00Z", "2024-05-10T17:05:00Z"):
            with self.subTest(stamp=stamp):
                verdict = _assess(stamp, "shock-2024-05-10")
                self.assertIn(verdict.verdict, {"ok", "uncorroborated"})
                self.assertTrue(verdict.publish_plasma)
                self.assertTrue(verdict.publish_derived)

    def test_the_shock_step_is_classified_coherent_not_rejected(self) -> None:
        verdict = _assess("2024-05-10T16:55:00Z", "shock-2024-05-10")
        step = next(check for check in verdict.checks if check.name == "step-coherence")
        self.assertEqual(step.outcome, "pass")
        if step.numbers:
            # The plasma really did step, and the field really did step with it.
            self.assertGreater(step.numbers["speedStepFraction"], 0.15)
            self.assertGreater(step.numbers["fieldStepFraction"], 0.10)

    def test_the_pre_failure_storm_sample_is_still_published(self) -> None:
        verdict = _assess("2024-05-11T13:35:00Z", "fault-onset-2024-05-11")
        self.assertTrue(verdict.publish_plasma)
        self.assertGreater(verdict.speed_kps, 700.0)


class TheGuardDegradesSafely(unittest.TestCase):
    def test_no_samples_at_all_withholds_rather_than_guesses(self) -> None:
        verdict = assess_solar_wind(
            primary_spacecraft="DSCOVR", plasma=[], now=dt.datetime(2024, 5, 11, tzinfo=UTC)
        )
        self.assertEqual(verdict.verdict, "rejected")
        self.assertFalse(verdict.publish_plasma)

    def test_a_naive_timestamp_is_refused_rather_than_localised(self) -> None:
        """bigmem-PC runs EDT; a naive datetime would silently shift by hours."""
        with self.assertRaises(ValueError):
            assess_solar_wind(
                primary_spacecraft="DSCOVR", plasma=[], now=dt.datetime(2024, 5, 11, 12, 0)
            )

    def test_a_lone_uncorroborated_source_is_labelled_as_such(self) -> None:
        plasma, fields = _load("quiet-2024-05-03")
        plasma = [row for row in plasma if row.spacecraft == "DSCOVR"]
        verdict = assess_solar_wind(
            primary_spacecraft="DSCOVR",
            plasma=plasma,
            field_samples=fields,
            now=_time("2024-05-03T12:00:00Z"),
        )
        self.assertEqual(verdict.verdict, "uncorroborated")
        self.assertTrue(verdict.publish_plasma)
        self.assertIn("uncorroborated", verdict.resolved_label)

    def test_absurd_values_are_rejected_outright(self) -> None:
        when = _time("2024-05-03T12:00:00Z")
        plasma = [
            PlasmaSample(
                spacecraft="DSCOVR",
                observed_at=when - dt.timedelta(minutes=index),
                speed_kps=9_999.0,
                density_cm3=4.0,
                temperature_k=50_000.0,
            )
            for index in range(30)
        ]
        verdict = assess_solar_wind(primary_spacecraft="DSCOVR", plasma=plasma, now=when)
        self.assertEqual(verdict.verdict, "rejected")
        self.assertIn("physically plausible", verdict.notice)


class TheNoaaFeedAdapter(unittest.TestCase):
    """The publisher only ever calls `assess_rtsw`; exercise that shape too."""

    @staticmethod
    def _rows(now: dt.datetime, source: str, speed: float, density: float, active: bool) -> list[dict]:
        return [
            {
                "time_tag": (now - dt.timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%S"),
                "active": active,
                "source": source,
                "proton_speed": speed,
                "proton_density": density,
                "proton_temperature": 60_000.0,
                "overall_quality": 0,
            }
            for index in range(45)
        ]

    @staticmethod
    def _mag(now: dt.datetime, source: str, bt: float, active: bool) -> list[dict]:
        return [
            {
                "time_tag": (now - dt.timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%S"),
                "active": active,
                "source": source,
                "bt": bt,
                "bz_gsm": -3.0,
                "overall_quality": 0,
            }
            for index in range(45)
        ]

    def test_agreeing_monitors_publish(self) -> None:
        now = dt.datetime(2026, 8, 7, 22, 30, tzinfo=UTC)
        wind = self._rows(now, "SOLAR1", 420.0, 5.0, True) + self._rows(now, "ACE", 430.0, 4.4, False)
        mag = self._mag(now, "SOLAR1", 6.0, True) + self._mag(now, "ACE", 6.4, False)
        decision = assess_rtsw(wind, mag, now)
        self.assertEqual(decision.wind.verdict, "ok")
        self.assertTrue(decision.publish_wind)
        self.assertFalse(decision.degraded)
        self.assertTrue(any(decision.wind_row_predicate()(row) for row in wind))

    def test_a_disagreeing_pair_withholds_every_dependent_field(self) -> None:
        now = dt.datetime(2026, 8, 7, 22, 30, tzinfo=UTC)
        wind = self._rows(now, "SOLAR1", 430.0, 2.0, True) + self._rows(now, "ACE", 900.0, 20.0, False)
        mag = self._mag(now, "SOLAR1", 6.0, True) + self._mag(now, "ACE", 6.4, False)
        decision = assess_rtsw(wind, mag, now)
        self.assertEqual(decision.wind.verdict, "disputed")
        self.assertTrue(decision.degraded)
        self.assertFalse(any(decision.wind_row_predicate()(row) for row in wind))
        published = decision.as_dict()
        self.assertIn("solarWind.dynamicPressureNpa", published["withheld"])
        self.assertIn("magnetopause.subsolarStandoffRe", published["withheld"])
        self.assertTrue(published["degraded"])
        self.assertIn("withheld", published["notice"])

    def test_two_agreeing_witnesses_out_vote_the_primary(self) -> None:
        now = dt.datetime(2026, 8, 7, 22, 30, tzinfo=UTC)
        wind = (
            self._rows(now, "SOLAR1", 430.0, 2.0, True)
            + self._rows(now, "ACE", 900.0, 18.0, False)
            + self._rows(now, "IMAP", 890.0, 20.0, False)
        )
        mag = self._mag(now, "SOLAR1", 6.0, True) + self._mag(now, "ACE", 6.4, False)
        decision = assess_rtsw(wind, mag, now)
        self.assertEqual(decision.wind.verdict, "substituted")
        self.assertTrue(decision.publish_wind)
        self.assertGreater(decision.wind.speed_kps, 800.0)
        self.assertIn("substituted for SOLAR1", decision.wind_label)

    def test_a_wholly_stale_feed_is_not_republished_as_current(self) -> None:
        stale = dt.datetime(2026, 8, 6, 4, 0, tzinfo=UTC)
        now = dt.datetime(2026, 8, 7, 22, 30, tzinfo=UTC)
        wind = self._rows(stale, "SOLAR1", 420.0, 5.0, True) + self._rows(stale, "ACE", 430.0, 4.4, False)
        mag = self._mag(stale, "SOLAR1", 6.0, True) + self._mag(stale, "ACE", 6.4, False)
        decision = assess_rtsw(wind, mag, now)
        self.assertEqual(decision.wind.verdict, "rejected")
        self.assertFalse(decision.publish_wind)

    def test_the_propagated_driver_series_is_truncated_at_the_fault(self) -> None:
        """The browser prefers this series over the headline sample.

        Guarding only the headline value would leave the wrong magnetosphere
        drawn on the globe, which is the failure this whole change is about.
        """
        now = dt.datetime(2026, 8, 7, 22, 30, tzinfo=UTC)
        wind = self._rows(now, "SOLAR1", 430.0, 2.0, True) + self._rows(now, "ACE", 900.0, 20.0, False)
        mag = self._mag(now, "SOLAR1", 6.0, True) + self._mag(now, "ACE", 6.4, False)
        decision = assess_rtsw(wind, mag, now)
        series = [
            {"observedAt": (now - dt.timedelta(minutes=step)).isoformat().replace("+00:00", "Z"), "speedKps": 430.0}
            for step in range(0, 240, 5)
        ]
        kept = decision.truncate_driver_series(series)
        self.assertTrue(kept, "pre-fault history must survive")
        self.assertLess(len(kept), len(series))
        onset = decision.wind.fault_onset
        self.assertTrue(all(_time(row["observedAt"]) < onset for row in kept))

    def test_thresholds_travel_into_the_artifact(self) -> None:
        now = dt.datetime(2026, 8, 7, 22, 30, tzinfo=UTC)
        wind = self._rows(now, "SOLAR1", 420.0, 5.0, True) + self._rows(now, "ACE", 430.0, 4.4, False)
        mag = self._mag(now, "SOLAR1", 6.0, True) + self._mag(now, "ACE", 6.4, False)
        published = assess_rtsw(wind, mag, now).as_dict()
        thresholds = published["solarWind"]["thresholds"]
        self.assertEqual(thresholds["speedRelativeTolerance"], DEFAULT_THRESHOLDS.speed_relative_tolerance)
        self.assertEqual(thresholds["plausibleSpeedKps"], [DEFAULT_THRESHOLDS.speed_min_kps, DEFAULT_THRESHOLDS.speed_max_kps])


class ThePublisherActuallyWithholds(unittest.TestCase):
    """Drive the archived storm through the publisher's own composition.

    Everything above proves the guard reaches the right verdict. That is not the
    same as proving the site stops drawing the wrong magnetosphere. The verdict
    only matters because `build_space_weather()` feeds the guard's predicates to
    `newest()`, takes `proton_speed` off whatever row comes back, and hands the
    resulting pressure to `shue_boundary()`. This class exercises that chain with
    the real functions from `pipeline/build_release.py` -- not reimplementations
    of them -- because a withheld sample is a path that never runs in ordinary
    operation, and an unexercised default is how this codebase has been bitten
    before.

    No network: `build_release` is imported for three pure helpers only.
    """

    @staticmethod
    def _rtsw_rows(*window_names: str) -> tuple[list[dict], list[dict]]:
        """The fixture in the exact JSON shape SWPC serves and the publisher reads."""
        wind: list[dict] = []
        mag: list[dict] = []
        for name in window_names:
            window = FIXTURE["windows"][name]
            for stamp, (speed, density, temperature, quality) in window["dscovrPlasma"].items():
                wind.append(
                    {
                        "time_tag": stamp.replace("Z", ""),
                        "active": True,
                        "source": "DSCOVR",
                        "proton_speed": speed,
                        "proton_density": density,
                        "proton_temperature": temperature,
                        "overall_quality": quality,
                    }
                )
            for stamp, (speed, density, temperature) in window["acePlasma"].items():
                wind.append(
                    {
                        "time_tag": stamp.replace("Z", ""),
                        "active": False,
                        "source": "ACE",
                        "proton_speed": speed,
                        "proton_density": density,
                        "proton_temperature": temperature,
                        "overall_quality": 0,
                    }
                )
            for stamp, (bt, bz, quality) in window["dscovrField"].items():
                mag.append(
                    {
                        "time_tag": stamp.replace("Z", ""),
                        "active": True,
                        "source": "DSCOVR",
                        "bt": bt,
                        "bz_gsm": bz,
                        "overall_quality": quality,
                    }
                )
        return wind, mag

    def _publish(self, when: str, *windows: str) -> dict:
        """Reproduce build_space_weather()'s solar-wind block, real functions only."""
        from pipeline import build_release

        wind, mag = self._rtsw_rows(*windows)
        decision = assess_rtsw(wind, mag, _time(when))

        # These four lines are build_space_weather(), copied in order.
        current_wind = build_release.newest(wind, decision.wind_row_predicate())
        current_mag = build_release.newest(mag, decision.imf_row_predicate())
        speed = float(current_wind["proton_speed"]) if current_wind.get("proton_speed") is not None else None
        density = float(current_wind["proton_density"]) if current_wind.get("proton_density") is not None else None
        pressure = 1.6726e-6 * density * speed**2 if speed is not None and density is not None else None
        bz = float(current_mag["bz_gsm"]) if current_mag.get("bz_gsm") is not None else None
        standoff, flaring = build_release.shue_boundary(pressure, bz)
        brief = build_release.deterministic_weather_brief(speed, bz, None, "—")
        if decision.degraded:
            brief = {**brief, "text": f"{decision.notice()} {brief['text']}"}
        return {
            "decision": decision,
            "speed": speed,
            "pressure": pressure,
            "standoff": standoff,
            "flaring": flaring,
            "brief": brief,
            "published": decision.as_dict(),
        }

    def test_the_magnetosphere_is_not_drawn_from_the_faulted_sample(self) -> None:
        """The whole point: no standoff at all, rather than an expanded one."""
        result = self._publish("2024-05-11T15:45:00Z", "fault-sustained-2024-05-11")
        self.assertEqual(result["decision"].wind.verdict, "disputed")
        self.assertIsNone(result["speed"], "the faulted speed must not reach the artifact")
        self.assertIsNone(result["pressure"])
        self.assertIsNone(result["standoff"], "an expanded magnetosphere is the failure being guarded")
        self.assertIsNone(result["flaring"])

    def test_the_withheld_path_does_not_crash_the_publisher(self) -> None:
        """A guard that takes the site down during a storm is not an improvement."""
        result = self._publish("2024-05-11T15:45:00Z", "fault-sustained-2024-05-11")
        self.assertIn("solarWind.dynamicPressureNpa", result["published"]["withheld"])
        self.assertIn("magnetopause.subsolarStandoffRe", result["published"]["withheld"])
        self.assertTrue(result["published"]["degraded"])
        self.assertTrue(result["brief"]["text"])

    def test_the_visitor_reads_the_reason_first(self) -> None:
        result = self._publish("2024-05-11T15:45:00Z", "fault-sustained-2024-05-11")
        text = result["brief"]["text"]
        self.assertTrue(text.startswith("Solar-wind speed and density are withheld"), text[:120])
        self.assertIn("DSCOVR", text)
        self.assertIn("ACE", text)

    def test_the_faulted_history_stops_at_the_onset(self) -> None:
        """Pre-fault storm history is real and stays on the page."""
        result = self._publish("2024-05-11T15:45:00Z", "fault-onset-2024-05-11", "fault-sustained-2024-05-11")
        decision = result["decision"]
        self.assertFalse(decision.publish_wind)
        onset = decision.wind.fault_onset
        self.assertIsNotNone(onset)
        wind, _mag = self._rtsw_rows("fault-onset-2024-05-11", "fault-sustained-2024-05-11")
        keep = decision.wind_series_predicate()
        kept = [row for row in wind if row.get("source") == "DSCOVR" and keep(row)]
        dropped = [row for row in wind if row.get("source") == "DSCOVR" and not keep(row)]
        self.assertTrue(kept, "the storm before the fault must survive")
        self.assertTrue(dropped, "the faulted stretch must be dropped")
        self.assertTrue(all(_time(row["time_tag"] + "Z") < onset for row in kept))

    def test_the_withheld_sample_still_carries_a_parseable_timestamp(self) -> None:
        """Withholding must not take the page down with it.

        `src/main.ts` renders this field with
        `new Date(observedAt).toISOString()`. In JavaScript `new Date("")` is an
        Invalid Date and `toISOString()` on it raises RangeError, so an empty
        string here would have thrown while rendering the weather panel -- the
        guard firing during a severe storm would have broken the page it exists
        to protect. The frontend is out of scope for this change and should not
        have to defend against its own publisher.
        """
        wind, mag = self._rtsw_rows("fault-sustained-2024-05-11")
        decision = assess_rtsw(wind, mag, _time("2024-05-11T15:45:00Z"))
        from pipeline import build_release

        current = build_release.newest(wind, decision.wind_row_predicate())
        self.assertEqual(current, {}, "this test is only meaningful while the sample is withheld")

        stamp = decision.observed_at(current, decision.wind)
        self.assertTrue(stamp, "observedAt must never be empty")
        # Parseable, and dated to the last moment the instrument was believable.
        parsed = dt.datetime.fromisoformat(stamp).replace(tzinfo=UTC)
        self.assertEqual(parsed, decision.wind.fault_onset)

    def test_the_genuine_shock_still_draws_a_compressed_magnetosphere(self) -> None:
        """The guard must not cost the site the event it exists to teach.

        Shue (1998) puts the quiet subsolar standoff near 10-11 Re. At the real
        2024-05-10 shock arrival the publisher must still produce a number, and a
        smaller one.
        """
        result = self._publish("2024-05-10T17:05:00Z", "shock-2024-05-10")
        self.assertIn(result["decision"].wind.verdict, {"ok", "uncorroborated"})
        self.assertIsNotNone(result["speed"])
        self.assertIsNotNone(result["standoff"])
        self.assertLess(result["standoff"], 10.0, "the shock compresses the boundary")
        self.assertGreater(result["standoff"], 4.0, "but not to an unphysical degree")
        self.assertFalse(result["decision"].degraded)

    def test_quiet_conditions_publish_a_normal_boundary(self) -> None:
        result = self._publish("2024-05-03T12:00:00Z", "quiet-2024-05-03")
        self.assertEqual(result["decision"].wind.verdict, "ok")
        self.assertIsNotNone(result["standoff"])
        self.assertGreater(result["standoff"], 8.0)
        self.assertLess(result["standoff"], 13.0)
        self.assertFalse(result["decision"].degraded)
        self.assertNotIn("withheld", result["brief"]["text"])


if __name__ == "__main__":
    unittest.main()
