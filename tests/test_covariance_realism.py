"""Offline tests for T19, on synthetic files in the published format.

Each test asserts the bug before it asserts the fix: the scenario is run once
with the guard and once without, and the unguarded run is asserted to reproduce
the behaviour the guard exists to prevent.  A guard test whose code path is
never reached passes for the wrong reason.

Nothing here opens a socket or reads the archive.
"""

from __future__ import annotations

import datetime as dt
import gzip
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import covariance_realism as cr  # noqa: E402
import starlink_collect as collect  # noqa: E402

MU = cr.MU_KM3_S2
RADIUS_KM = 6900.0
INCLINATION = math.radians(53.0)
STEP_SECONDS = 3600  # one hour, so a 72 h fixture is 73 records rather than 4,321


def state_at(seconds: float) -> tuple[np.ndarray, np.ndarray]:
    """A circular orbit, written out so the fixture's physics is visible."""
    n = math.sqrt(MU / RADIUS_KM**3)
    angle = n * seconds
    position = RADIUS_KM * np.array(
        [math.cos(angle), math.sin(angle) * math.cos(INCLINATION), math.sin(angle) * math.sin(INCLINATION)]
    )
    velocity = RADIUS_KM * n * np.array(
        [-math.sin(angle), math.cos(angle) * math.cos(INCLINATION), math.cos(angle) * math.sin(INCLINATION)]
    )
    return position, velocity


def epoch_token(moment: dt.datetime) -> str:
    day_of_year = moment.timetuple().tm_yday
    return (
        f"{moment.year:04d}{day_of_year:03d}"
        f"{moment.hour:02d}{moment.minute:02d}{moment.second:02d}.000"
    )


def sigma_at_lead(lead_hours: float) -> tuple[float, float, float]:
    """Formal sigmas in metres, growing with lead the way the real files do."""
    radial = 0.7 + 2.0 * lead_hours
    in_track = 0.9 + 12.0 * lead_hours**2
    cross = 1.1 + 0.05 * lead_hours
    return radial, in_track, cross


def covariance_line_terms(sigmas_m: tuple[float, float, float]) -> list[float]:
    """21 lower-triangle terms in km^2, diagonal only."""
    terms = [0.0] * 21
    for index, axis in zip(cr.eph.DIAGONAL_INDEX[:3], range(3)):
        terms[index] = (sigmas_m[axis] / 1000.0) ** 2
    for index in cr.eph.DIAGONAL_INDEX[3:]:
        terms[index] = 1.0e-12
    return terms


def write_ephemeris(
    path: Path,
    *,
    catalogue: str,
    start: dt.datetime,
    span_hours: float = 72.0,
    offset_inertial_km=None,
    burn_at_hours: float | None = None,
    burn_dv_km_s: float = 0.0,
    sigma_override=None,
    created: dt.datetime | None = None,
    issue: int = 1,
    drop_offset_after_hours: float | None = None,
) -> Path:
    """One file in the published format, gzipped, with the published filename."""
    created = created or (start + dt.timedelta(minutes=12))
    stop = start + dt.timedelta(hours=span_hours)
    records = int(span_hours * 3600 / STEP_SECONDS) + 1
    offset = np.zeros(3) if offset_inertial_km is None else np.asarray(offset_inertial_km, float)

    lines = [
        f"created:{created:%Y-%m-%d %H:%M:%S} UTC",
        f"ephemeris_start:{start:%Y-%m-%d %H:%M:%S} UTC "
        f"ephemeris_stop:{stop:%Y-%m-%d %H:%M:%S} UTC step_size:{STEP_SECONDS}",
        "ephemeris_source:blend",
        "UVW",
    ]
    absolute_start = start.timestamp()
    for index in range(records):
        seconds = index * STEP_SECONDS
        position, velocity = state_at(absolute_start + seconds)
        if drop_offset_after_hours is None or seconds < drop_offset_after_hours * 3600.0:
            position = position + offset
        if burn_at_hours is not None and seconds >= burn_at_hours * 3600.0:
            elapsed = seconds - burn_at_hours * 3600.0
            direction = velocity / np.linalg.norm(velocity)
            velocity = velocity + burn_dv_km_s * direction
            position = position + burn_dv_km_s * direction * elapsed
        moment = start + dt.timedelta(seconds=seconds)
        lines.append(
            f"{epoch_token(moment)} "
            + " ".join(f"{value:.10f}" for value in position)
            + " "
            + " ".join(f"{value:.10f}" for value in velocity)
        )
        lead_hours = seconds / 3600.0
        sigmas = sigma_override(lead_hours) if sigma_override else sigma_at_lead(lead_hours)
        terms = covariance_line_terms(sigmas)
        for chunk in range(3):
            lines.append(" ".join(f"{value:.10e}" for value in terms[chunk * 7 : chunk * 7 + 7]))

    name = (
        f"MEME_{catalogue}_STARLINK-{catalogue}_{issue}_Operational_{issue}"
        f"_UNCLASSIFIED.txt.gz"
    )
    destination = path / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destination, "wt", encoding="ascii") as handle:
        handle.write("\n".join(lines) + "\n")
    return destination


BASE = dt.datetime(2026, 9, 22, 0, 0, 0, tzinfo=dt.timezone.utc)


class ContainmentOnACalibratedGaussian(unittest.TestCase):
    """A calibrated covariance must return the nominal fraction; a wrong one must not."""

    def _build(self, directory: Path, inflation: float, count: int = 240) -> None:
        rng = np.random.default_rng(20260922)
        lead = 12.0
        sigmas = np.array(sigma_at_lead(lead))
        for index in range(count):
            catalogue = str(100000 + index)
            earlier_start = BASE
            later_start = BASE + dt.timedelta(hours=8)
            write_ephemeris(directory, catalogue=catalogue, start=earlier_start)

            # The residual is drawn in the covariance frame at the comparison
            # instant, then carried into the inertial frame, so the measured
            # Mahalanobis distance is chi-square with three degrees of freedom
            # by construction when `inflation` is 1.
            instant = earlier_start.timestamp() + lead * 3600.0
            position, velocity = state_at(instant)
            basis = cr.uvw_basis(position, velocity)
            draw_m = rng.normal(0.0, sigmas * inflation)
            offset_km = (basis.T @ draw_m) / 1000.0
            write_ephemeris(
                directory,
                catalogue=catalogue,
                start=later_start,
                offset_inertial_km=offset_km,
                issue=2,
            )

    def test_calibrated_returns_the_nominal_fraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory, inflation=1.0)
            payload = cr.run(directory, self_test_files=2)
            cell = payload["containment"]["leads"][12.0]
            self.assertEqual(cell["status"], "measured")
            low, high = cell["wilson95"]
            self.assertLessEqual(low, 0.95)
            self.assertGreaterEqual(high, 0.95)
            self.assertAlmostEqual(cell["kRobust"], 1.0, delta=0.15)

    def test_a_covariance_three_times_too_small_fails_the_same_test(self):
        """The negative control: the test must be able to fail."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory, inflation=3.0)
            payload = cr.run(directory, self_test_files=2)
            cell = payload["containment"]["leads"][12.0]
            low, high = cell["wilson95"]
            self.assertLess(high, 0.95)
            self.assertGreater(cell["kRobust"], 2.0)


class ReplanExclusion(unittest.TestCase):
    """A re-plan discontinuity must be excluded AND counted, not absorbed."""

    def _build(self, directory: Path, burn_dv_km_s: float, clean_count: int = 60) -> None:
        rng = np.random.default_rng(6)
        for index in range(clean_count):
            catalogue = str(200000 + index)
            write_ephemeris(directory, catalogue=catalogue, start=BASE)
            offset = rng.normal(0.0, 0.0005, 3)
            write_ephemeris(
                directory,
                catalogue=catalogue,
                start=BASE + dt.timedelta(hours=8),
                offset_inertial_km=offset,
                issue=2,
            )
        # One spacecraft whose later issue carries a manoeuvre inside the overlap.
        catalogue = "300001"
        write_ephemeris(directory, catalogue=catalogue, start=BASE)
        write_ephemeris(
            directory,
            catalogue=catalogue,
            start=BASE + dt.timedelta(hours=8),
            burn_at_hours=20.0,
            burn_dv_km_s=burn_dv_km_s,
            issue=2,
        )

    def test_the_replan_is_excluded_and_counted(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory, burn_dv_km_s=0.002)
            payload = cr.run(directory, self_test_files=2)
            self.assertGreaterEqual(payload["exclusions"]["replansExcluded"], 1)
            self.assertGreater(payload["exclusions"]["replanThresholdM"], 0.0)
            clean = payload["containment"]["leads"][48.0]["n"]
            contaminated = payload["containmentWithReplans"]["leads"][48.0]["n"]
            self.assertEqual(contaminated - clean, payload["exclusions"]["replansExcluded"])

    def test_with_the_rule_disabled_the_contaminated_pair_survives(self):
        """The bug, asserted: without the exclusion the manoeuvre enters the number."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory, burn_dv_km_s=0.002)
            payload = cr.run(directory, self_test_files=2)
            with_replans = payload["containmentWithReplans"]["leads"][48.0]
            without = payload["containment"]["leads"][48.0]
            self.assertGreater(with_replans["n"], without["n"])
            self.assertGreater(with_replans["p95M2"], without["p95M2"])

    def test_a_pair_with_no_manoeuvre_is_not_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory, burn_dv_km_s=0.0)
            payload = cr.run(directory, self_test_files=2)
            self.assertEqual(payload["exclusions"]["replansExcluded"], 0)


class ConstantColumnCensus(unittest.TestCase):
    """A constant column must be detected; a varying one must not be called constant."""

    def test_a_constant_column_is_detected_and_a_varying_one_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            count = 120
            for index in range(count):
                def sigmas(lead_hours: float, index=index):
                    if lead_hours >= 72.0:
                        # Two fixed values across every file: a constant column.
                        return (300.0, 3800.0 if index % 2 else 3000.0, 500.0)
                    return (
                        0.7 + 0.01 * index + 2.0 * lead_hours,
                        0.9 + 0.02 * index + 12.0 * lead_hours**2,
                        1.1 + 0.03 * index + 0.05 * lead_hours,
                    )

                write_ephemeris(
                    directory,
                    catalogue=str(400000 + index),
                    start=BASE,
                    sigma_override=sigmas,
                )
            payload = cr.census(sorted(directory.rglob("MEME_*.txt.gz")))
            cycle = next(iter(payload["cycles"].values()))
            self.assertEqual(cycle["files"], count)

            at_72 = cycle["leads"][72.0]
            self.assertEqual(at_72[0]["distinctValues"], 1)
            self.assertEqual(at_72[1]["distinctValues"], 2)
            self.assertEqual(at_72[2]["distinctValues"], 1)

            at_12 = cycle["leads"][12.0]
            for axis in at_12:
                self.assertEqual(axis["distinctValues"], count)

            # The licence condition is applied mechanically, not by judgement.
            # The rule is a function of n, and says so: two distinct values across
            # 120 files is 1.67%, above the 1% licence, so column 2 is NOT
            # licensed here even though it is plainly constant-ish. Columns 1 and
            # 3 take a single value and clear it.
            self.assertIn("72.0", payload["placeholderLicensed"])
            self.assertEqual(sorted(payload["placeholderLicensed"]["72.0"]), [1, 3])
            self.assertAlmostEqual(at_72[1]["distinctShare"], 2 / count)
            self.assertNotIn("12.0", payload["placeholderLicensed"])

    def test_the_non_monotonicity_is_measured_per_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)

            def sigmas(lead_hours: float):
                if lead_hours >= 72.0:
                    return (300.0, 3800.0, 500.0)
                if lead_hours >= 48.0:
                    return (103.0, 2514.0, 58.0)  # below the 24 h in-track value
                if lead_hours >= 24.0:
                    return (93.0, 3300.0, 6.7)
                return (0.7 + 2.0 * lead_hours, 0.9 + 12.0 * lead_hours**2, 1.1)

            for index in range(40):
                write_ephemeris(
                    directory, catalogue=str(500000 + index), start=BASE, sigma_override=sigmas
                )
            payload = cr.census(sorted(directory.rglob("MEME_*.txt.gz")))
            cycle = next(iter(payload["cycles"].values()))
            # The census reports ADJACENT leads on its own grid, so the step
            # down in the in-track column lands on the pair that brackets it.
            # Asserting the bracketing pair rather than a hard-coded 24 -> 48
            # keeps this test honest when the grid gains resolution.
            falls = {
                key: value
                for key, value in cycle["nonMonotonic"].items()
                if key.endswith("axis2") and value["fraction"] == 1.0
            }
            self.assertEqual(list(falls), ["47.0->48.0 axis2"])
            self.assertEqual(falls["47.0->48.0 axis2"]["count"], 40)
            # and nothing claims a cross-track fall at that step
            self.assertNotIn("47.0->48.0 axis3", cycle["nonMonotonic"])


class RepublishedTail(unittest.TestCase):
    """A later issue that republishes the earlier issue's own states tests nothing.

    Agreement to better than the file's print precision is identity, not two
    predictions that coincide. Those instants carry no information about the
    covariance and must not be counted as containment.
    """

    def _build(self, directory: Path, count: int = 60) -> None:
        rng = np.random.default_rng(11)
        for index in range(count):
            catalogue = str(700000 + index)
            write_ephemeris(directory, catalogue=catalogue, start=BASE)
            write_ephemeris(
                directory,
                catalogue=catalogue,
                start=BASE + dt.timedelta(hours=8),
                offset_inertial_km=rng.normal(0.0, 0.002, 3),
                # Beyond 48 h of ITS OWN lead the later issue republishes the
                # earlier issue's states verbatim.
                drop_offset_after_hours=48.0,
                issue=2,
            )

    def test_the_republished_tail_is_detected_and_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory)
            payload = cr.run(directory, self_test_files=2)

            # 56 h of the earlier issue's lead is 48 h of the later issue's.
            for lead in (56.0, 60.0, 72.0):
                cell = payload["containment"]["leads"].get(lead)
                if cell is None:
                    continue
                self.assertEqual(cell["identicalState"], cell["pairsOffered"])
                self.assertEqual(cell["n"], 0)
                self.assertIn("NO INFORMATIVE PAIR", cell["status"])

            for lead in (12.0, 24.0, 36.0):
                cell = payload["containment"]["leads"][lead]
                self.assertEqual(cell["identicalState"], 0)
                self.assertEqual(cell["n"], cell["pairsOffered"])

    def test_with_the_rule_disabled_the_republished_tail_scores_as_perfect(self):
        """The bug, asserted: counted in, an identical state is a zero residual."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory)
            payload = cr.run(directory, self_test_files=2)
            counted = payload["containmentCountingIdenticalStates"]["leads"][60.0]
            self.assertEqual(counted["status"], "measured")
            self.assertEqual(counted["containedFraction"], 1.0)
            self.assertEqual(counted["medianM2"], 0.0)
            self.assertEqual(payload["containment"]["leads"][60.0]["n"], 0)

    def test_the_splice_is_located_at_the_later_issues_own_lead(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._build(directory)
            issues = cr.scan_issues(directory)
            pairs, _ = cr.build_pairs(issues)
            scan = cr.splice_scan(pairs, sample=20)
            self.assertEqual(scan["identicalTailNotContiguous"], 0)
            self.assertAlmostEqual(
                scan["firstIdenticalLeadHoursOfLaterIssue"]["median"], 48.0, places=6
            )
            self.assertAlmostEqual(
                scan["firstIdenticalLeadHoursOfLaterIssue"]["min"], 48.0, places=6
            )
            self.assertAlmostEqual(
                scan["firstIdenticalLeadHoursOfLaterIssue"]["max"], 48.0, places=6
            )


class UnreachableLeads(unittest.TestCase):
    """Leads shorter than the publication cadence are UNREACHABLE, never a number."""

    def test_short_leads_report_unreachable(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for index in range(40):
                catalogue = str(600000 + index)
                write_ephemeris(directory, catalogue=catalogue, start=BASE)
                write_ephemeris(
                    directory,
                    catalogue=catalogue,
                    start=BASE + dt.timedelta(hours=8),
                    offset_inertial_km=(0.001, 0.0, 0.0),
                    issue=2,
                )
            payload = cr.run(directory, self_test_files=2)
            for lead in (1.0, 3.0, 6.0):
                cell = payload["containment"]["leads"][lead]
                self.assertEqual(cell["n"], 0)
                self.assertIn("UNREACHABLE", cell["status"])
            # Four of the forty spacecraft carry a catalogue field ending in 0
            # and are the pre-registered calibration hold-out, excluded from
            # every reported number.
            self.assertEqual(payload["exclusions"]["calibrationHoldout"], 4)
            self.assertEqual(payload["containment"]["leads"][12.0]["n"], 36)


class ConsequenceDerivation(unittest.TestCase):
    """The two Pc regimes must have opposite signs, as the registration derives."""

    def test_near_field_ratio_approaches_k_squared_and_far_field_reverses(self):
        sigmas = (300.0, 3800.0, 500.0)
        payload = cr.consequence(sigmas, 0.25, misses_m=(0.0,))
        for row in payload["misses"]:
            # Near field: the ratio is k^2, so a covariance that is too LARGE
            # (k < 1) UNDERSTATES the probability at small miss.
            self.assertAlmostEqual(row["ratioPublishedOverSelfConsistent"], 0.0625, delta=0.02)

        # Far field: the sign reverses. A miss several sigma out is dominated by
        # the exponential, and the wider covariance puts more probability there.
        # Which regime a given miss is in is a property of the AXIS it lies
        # along, not of the miss distance alone: 3,000 m is seven sigma along
        # the projected radial axis and well inside one sigma along the in-track
        # one. Both rows are asserted, because that contrast is the reason the
        # registration forbids quoting a ratio without its miss geometry.
        far = cr.consequence(sigmas, 0.7, misses_m=(3000.0,))
        radial = [row for row in far["misses"] if "radial" in row["direction"]]
        in_plane = [row for row in far["misses"] if "in-plane" in row["direction"]]
        self.assertTrue(radial and in_plane)
        for row in radial:
            self.assertGreater(row["ratioLog10"], 0.0)
            self.assertGreater(row["ratioPublishedOverSelfConsistent"], 1.0)
        for row in in_plane:
            self.assertLess(row["ratioPublishedOverSelfConsistent"], 1.0)

    def test_the_ratio_does_not_depend_on_the_crossing_speed(self):
        sigmas = (300.0, 3800.0, 500.0)
        ratios = []
        for angle in (60.0, 120.0):
            payload = cr.consequence(sigmas, 0.5, crossing_deg=angle, misses_m=(0.0,))
            ratios.append(payload["misses"][0]["ratioPublishedOverSelfConsistent"])
            self.assertNotAlmostEqual(
                payload["relativeSpeedKmS"],
                cr.consequence(sigmas, 0.5, crossing_deg=60.0, misses_m=(0.0,))[
                    "relativeSpeedKmS"
                ]
                if angle != 60.0
                else 0.0,
            )
        self.assertAlmostEqual(ratios[0], ratios[1], delta=0.01)


class CollectorCadence(unittest.TestCase):
    """The collector's cadence rules, driven at an injected clock, socket-free."""

    def _roots(self, directory: Path):
        roots = collect.ingest.Roots(root=directory)
        for folder in (roots.state, roots.starlink_raw, roots.requests_ledger.parent):
            folder.mkdir(parents=True, exist_ok=True)
        return roots

    def test_a_second_pass_inside_the_interval_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            roots = self._roots(Path(temporary))
            first = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.timezone.utc)
            collect.write_state(roots, {"passes": [{"startedAt": first.isoformat()}]})
            verdict = collect.due(roots, first + dt.timedelta(minutes=30))
            self.assertFalse(verdict.due)
            self.assertIn("interval", verdict.reason)
            self.assertTrue(collect.due(roots, first + dt.timedelta(hours=3)).due)

    def test_the_daily_ceiling_refuses_a_fifth_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            roots = self._roots(Path(temporary))
            base = dt.datetime(2026, 9, 22, 0, 0, tzinfo=dt.timezone.utc)
            collect.write_state(
                roots,
                {
                    "passes": [
                        {"startedAt": (base + dt.timedelta(hours=4 * index)).isoformat()}
                        for index in range(4)
                    ]
                },
            )
            verdict = collect.due(roots, base + dt.timedelta(hours=18))
            self.assertFalse(verdict.due)
            self.assertIn("ceiling", verdict.reason)

    def test_with_the_rule_disabled_the_refused_pass_proceeds(self):
        """The bug, asserted: without the cadence gate the pass is not refused."""
        with tempfile.TemporaryDirectory() as temporary:
            roots = self._roots(Path(temporary))
            first = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.timezone.utc)
            collect.write_state(roots, {"passes": [{"startedAt": first.isoformat()}]})
            calls = []

            def transport(url, validators):
                calls.append(url)
                return collect.ingest.Response(status=200, body=b"MEME_1_STARLINK-1_1_Operational_1_UNCLASSIFIED.txt\n", headers={})

            with self.assertRaises(collect.NotDue):
                collect.run_pass(
                    roots,
                    now=first + dt.timedelta(minutes=5),
                    transport=transport,
                    hostname=collect.ingest.STARLINK_HOST,
                    enforce_due=True,
                )
            self.assertEqual(calls, [])

            collect.run_pass(
                roots,
                now=first + dt.timedelta(minutes=5),
                transport=transport,
                hostname=collect.ingest.STARLINK_HOST,
                enforce_due=False,
            )
            self.assertGreaterEqual(len(calls), 1)

    def test_an_answered_304_is_not_a_halt(self):
        """The bug, asserted: the inherited engine reads a 304 as a transport halt."""
        with tempfile.TemporaryDirectory() as temporary:
            roots = self._roots(Path(temporary))
            now = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.timezone.utc)
            day = roots.starlink_raw / "2026" / "09" / "22"
            day.mkdir(parents=True, exist_ok=True)
            held = day / "MANIFEST-20260922T000000Z.txt.gz"
            with gzip.open(held, "wb") as handle:
                handle.write(b"MEME_1_STARLINK-1_1_Operational_1_UNCLASSIFIED.txt\n")
            collect.ingest._write_json(
                roots.state / "bodies-starlink.json",
                {"MANIFEST": {"sha256": "abc", "bytes": 1}},
            )
            collect.ingest._write_json(
                roots.state / "validators-starlink.json",
                {"MANIFEST": {"etag": '"x"', "lastModified": None, "bodySha256": "abc"}},
            )

            def transport(url, validators):
                if url.endswith("MANIFEST.txt"):
                    self.assertTrue(validators, "a 304 must answer a validator we sent")
                    return collect.ingest.Response(status=304, body=b"", headers={})
                return collect.ingest.Response(status=200, body=b"body", headers={})

            summary = collect.run_pass(
                roots,
                now=now,
                transport=transport,
                hostname=collect.ingest.STARLINK_HOST,
                only_missing=False,
            )
            self.assertTrue(summary["manifestUnchanged"])
            self.assertIsNone(collect.ingest.halted(roots))


if __name__ == "__main__":
    unittest.main()
