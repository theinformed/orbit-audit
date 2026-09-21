"""Orbital lifetime: what is measured, what is assumed, and what is refused.

The refusals matter as much as the numbers here. This estimate goes on the
cards of objects nobody has written about, where a reader has nothing else to
judge it against, so the failure that must not happen is a confident figure
about the wrong physics -- a re-entry date for a spacecraft that is holding its
altitude with thrusters.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import build_release, orbital_lifetime  # noqa: E402

DAY_MS = 86_400_000


def series(
    start_km: float,
    rate_km_per_day: float,
    days: float = 600.0,
    count: int = 200,
    jump_km: float = 0.0,
) -> list[dict[str, float]]:
    """A synthetic element-set series, optionally with one manoeuvre in it."""
    rows = []
    for index in range(count):
        elapsed = days * index / (count - 1)
        value = start_km + rate_km_per_day * elapsed
        if jump_km and index > count // 2:
            value += jump_km
        rows.append({"t": int(elapsed * DAY_MS), "semiMajorAxisKm": value})
    return rows


class DensityTableTests(unittest.TestCase):
    """The table is a checked-in constant, so it needs a regression pin."""

    def test_it_matches_published_nrlmsis_values_to_the_order_they_are_quoted_at(self):
        # Textbook NRLMSIS figures: about 6e-13 at 400 km at solar minimum and
        # about 6e-12 at solar maximum; roughly a decade lower at 500 km.
        for altitude, level, low, high in (
            (400.0, "low", 4e-13, 1e-12),
            (400.0, "high", 4e-12, 9e-12),
            (500.0, "low", 5e-14, 2e-13),
            (500.0, "high", 8e-13, 3e-12),
            (800.0, "high", 1e-14, 8e-14),
        ):
            with self.subTest(altitude=altitude, level=level):
                value = orbital_lifetime.density_kg_m3(level, altitude)
                self.assertGreater(value, low)
                self.assertLess(value, high)

    def test_density_falls_with_height_and_rises_with_solar_activity(self):
        previous = {level: float("inf") for level in orbital_lifetime.DENSITY_LEVELS}
        for altitude in range(200, 1300, 25):
            values = {
                level: orbital_lifetime.density_kg_m3(level, float(altitude))
                for level in orbital_lifetime.DENSITY_LEVELS
            }
            for level, value in values.items():
                with self.subTest(altitude=altitude, level=level):
                    self.assertLess(value, previous[level])
                previous[level] = value
            # Above the turbopause a hotter thermosphere is a fatter one, at
            # every altitude. This is the whole reason lifetime has a band.
            self.assertLess(values["low"], values["mean"])
            self.assertLess(values["mean"], values["high"])

    def test_the_solar_swing_at_500_km_is_more_than_an_order_of_magnitude(self):
        """The number that makes a single-figure lifetime dishonest."""
        ratio = (orbital_lifetime.density_kg_m3("high", 500.0)
                 / orbital_lifetime.density_kg_m3("low", 500.0))
        self.assertGreater(ratio, 10.0)

    def test_interpolation_is_logarithmic_not_linear(self):
        """Halfway up a 10 km step of an exponential is not halfway in value."""
        low = orbital_lifetime.density_kg_m3("mean", 500.0)
        high = orbital_lifetime.density_kg_m3("mean", 510.0)
        middle = orbital_lifetime.density_kg_m3("mean", 505.0)
        self.assertLess(middle, (low + high) / 2)
        self.assertAlmostEqual(middle, (low * high) ** 0.5, delta=middle * 1e-9)

    def test_off_the_ends_of_the_table_clamps_rather_than_extrapolates(self):
        self.assertEqual(orbital_lifetime.density_kg_m3("mean", 10.0),
                         orbital_lifetime.DENSITY_TABLE[0][2])
        self.assertEqual(orbital_lifetime.density_kg_m3("mean", 90_000.0),
                         orbital_lifetime.DENSITY_TABLE[-1][2])

    def test_an_unknown_solar_level_is_refused_rather_than_defaulted(self):
        with self.assertRaises(ValueError):
            orbital_lifetime.density_kg_m3("quiet-ish", 500.0)


class MeasuredDecayTests(unittest.TestCase):
    def test_a_plainly_decaying_orbit_is_measured_to_its_own_slope(self):
        measured = orbital_lifetime.measured_decay_km_per_day(series(6878.0, -0.05))
        self.assertIsNotNone(measured)
        self.assertAlmostEqual(measured, -0.05, places=6)

    def test_a_station_kept_orbit_is_refused(self):
        """WORLDVIEW 1 has two years of history and no trend, because it is

        being flown. The old arithmetic turned that into "199 years to
        re-entry", which is a confident answer to a question the data does not
        contain.
        """
        held = [
            {"t": index * 3 * DAY_MS,
             "semiMajorAxisKm": 6869.0 + (0.4 if index % 2 else -0.4)}
            for index in range(200)
        ]
        self.assertIsNone(orbital_lifetime.measured_decay_km_per_day(held))

    def test_an_orbit_being_raised_is_refused(self):
        """LEGION 3 gained 68 km over the window. It is not coming down."""
        self.assertIsNone(orbital_lifetime.measured_decay_km_per_day(series(6828.0, +0.09)))

    def test_a_step_in_the_fit_does_not_capture_the_slope(self):
        """The reason the slope is Theil-Sen and not least squares.

        These are fitted mean elements, not measurements, and a re-fit after a
        gap in tracking moves them by a kilometre or two with nothing having
        happened in orbit. An endpoint fit is defenceless against that; the
        median of the pairwise slopes barely registers it.
        """
        jumped = series(6878.0, -0.05, jump_km=2.0)
        robust = orbital_lifetime.measured_decay_km_per_day(jumped)
        self.assertIsNotNone(robust)
        self.assertAlmostEqual(robust, -0.05, places=2)

    def test_a_step_big_enough_to_be_a_real_manoeuvre_is_refused_outright(self):
        """And here the robustness stops, deliberately.

        A +40 km step is not a fitting artefact, it is a spacecraft raising its
        orbit, and an object that raises its orbit is not passively decaying --
        so there is no honest lifetime to quote for it at all. The graded
        behaviour in between is real and is the method's main weakness: a 10 km
        step biases the measured rate by about a third, which is inside the
        solar-activity band the published sentence already declares and is why
        that sentence says "roughly".
        """
        jumped = series(6878.0, -0.05, jump_km=40.0)
        naive = ((jumped[-1]["semiMajorAxisKm"] - jumped[0]["semiMajorAxisKm"])
                 / ((jumped[-1]["t"] - jumped[0]["t"]) / DAY_MS))
        self.assertGreater(naive, 0, "the control: a two-point fit reads it as RISING")
        self.assertIsNone(orbital_lifetime.measured_decay_km_per_day(jumped))

    def test_a_record_too_short_to_mean_anything_is_refused(self):
        """Neutral density changes by a factor of two between day and night.

        A fortnight of element sets measures that, and the current storm, and
        not the trend. Most of the 2026 rideshare passengers are here.
        """
        self.assertIsNone(orbital_lifetime.measured_decay_km_per_day(series(6878.0, -0.05, days=30.0)))

    def test_a_handful_of_element_sets_is_refused_however_long_it_spans(self):
        self.assertIsNone(
            orbital_lifetime.measured_decay_km_per_day(series(6878.0, -0.05, days=900.0, count=6)))


class ReentryIntegrationTests(unittest.TestCase):
    def test_the_band_runs_the_right_way_round(self):
        """An active Sun brings it down sooner. If this ever inverts, the card

        is telling a reader the opposite of the physics the rest of the site
        teaches.
        """
        active = orbital_lifetime.years_to_reentry(500.0, -0.04, "high")
        average = orbital_lifetime.years_to_reentry(500.0, -0.04, "mean")
        quiet = orbital_lifetime.years_to_reentry(500.0, -0.04, "low")
        self.assertLess(active, average)
        self.assertLess(average, quiet)

    def test_a_small_satellite_at_500_km_lands_in_the_years_to_decades_range(self):
        years = orbital_lifetime.years_to_reentry(500.0, -0.04, "mean")
        self.assertGreater(years, 1.0)
        self.assertLess(years, 100.0)

    def test_lower_orbits_come_down_sooner_at_the_same_measured_rate(self):
        low = orbital_lifetime.years_to_reentry(430.0, -0.04, "mean")
        high = orbital_lifetime.years_to_reentry(600.0, -0.04, "mean")
        self.assertLess(low, high)

    def test_a_rising_orbit_has_no_re_entry_date(self):
        self.assertIsNone(orbital_lifetime.years_to_reentry(500.0, +0.01, "mean"))

    def test_anything_beyond_a_thousand_years_is_returned_as_unknowable(self):
        """GMS-T at 1,197 km integrates to some thousands of years. That is not

        a prediction, and a reader would still read it as one.
        """
        self.assertIsNone(orbital_lifetime.years_to_reentry(1197.0, -0.00018, "mean"))


class PublishedSentenceTests(unittest.TestCase):
    def test_no_measurement_produces_no_sentence_at_all(self):
        self.assertEqual(orbital_lifetime.lifetime_sentence(None), "")

    def test_the_sentence_names_the_assumption_that_dominates_it(self):
        text = orbital_lifetime.lifetime_sentence(
            orbital_lifetime.estimate(500.0, series(6878.0, -0.04)))
        self.assertIn("km a year", text)
        self.assertIn("solar cycle", text)
        self.assertIn("Sun", text)

    def test_a_lifetime_is_never_quoted_to_a_decimal_place(self):
        """The band around it spans a factor of five to twenty."""
        for rate in (-0.005, -0.01, -0.02, -0.04, -0.06, -0.09):
            with self.subTest(rate=rate):
                text = orbital_lifetime.lifetime_sentence(
                    orbital_lifetime.estimate(520.0, series(6898.0, rate)))
                self.assertNotRegex(text, r"\d\.\d years")

    def test_an_object_drag_will_never_reach_says_so_instead_of_guessing(self):
        text = orbital_lifetime.lifetime_sentence(
            orbital_lifetime.estimate(1197.0, series(7575.0, -0.00018)))
        self.assertIn("will not bring it down", text)
        self.assertNotIn("years out", text)


class ArchiveReadTests(unittest.TestCase):
    def test_a_missing_manifest_costs_a_clause_and_not_a_publish(self):
        self.assertEqual(orbital_lifetime.decay_samples(Path("/nonexistent"), [123]), {})

    def test_only_the_shards_holding_the_wanted_objects_are_opened(self):
        with_root = self._fixture(norad=69902)
        opened: list[str] = []
        real_is_file = Path.is_file

        def counting_is_file(self):  # noqa: ANN001
            if "orbit-history-" in str(self):
                opened.append(str(self))
            return real_is_file(self)

        Path.is_file = counting_is_file
        try:
            series_map = orbital_lifetime.decay_samples(with_root, [69902])
        finally:
            Path.is_file = real_is_file
        self.assertIn(69902, series_map)
        # 69902 % 256 == 14, and nothing else may be touched: the full shard
        # set is 2.3 GB, and reading it inside a five-minute publish cycle is
        # how this site lost four hours of publishes on 2026-08-08.
        self.assertEqual(len(opened), 1)
        self.assertIn("orbit-history-014", opened[0])

    def _fixture(self, norad: int) -> Path:
        """A manifest with SEVERAL shards, only one of which is wanted.

        With one shard in the manifest, "open every shard" and "open the shard
        this object is in" do exactly the same thing, and the test cannot tell
        them apart -- which is what the first version of this fixture did.
        """
        import tempfile

        root = Path(tempfile.mkdtemp())
        (root / "artifacts").mkdir()
        wanted_shard = norad % 256
        entries = []
        for shard in {wanted_shard, 0, 1, 99, 255}:
            path = f"artifacts/orbit-history-{shard:03d}-test.json"
            holder = norad if shard == wanted_shard else 900_000 + shard
            (root / path).write_text(json.dumps(
                {"objects": [{"norad": holder, "samples": series(6970.0, -0.03)}]}))
            entries.append({"shard": shard, "path": path})
        (root / "manifest.json").write_text(json.dumps({"orbitHistory": {"shards": entries}}))
        return root


class AttachmentTests(unittest.TestCase):
    """Which cards get the sentence, and -- more to the point -- which do not."""

    def _root(self, norad: int) -> Path:
        import tempfile

        root = Path(tempfile.mkdtemp())
        (root / "artifacts").mkdir()
        shard = norad % 256
        path = f"artifacts/orbit-history-{shard:03d}-test.json"
        (root / path).write_text(json.dumps(
            {"objects": [{"norad": norad, "samples": series(6878.0, -0.05)}]}))
        (root / "manifest.json").write_text(json.dumps(
            {"orbitHistory": {"shards": [{"shard": shard, "path": path}]}}))
        return root

    def _record(self, norad: int, kind: str, orbit: str = "LEO") -> dict:
        return {
            "id": norad, "purposeKind": kind, "orbit": orbit,
            "perigeeKm": 494.0, "apogeeKm": 506.0,
            "purpose": "Something already written.",
        }

    def test_a_class_described_leo_object_gets_the_measured_sentence(self):
        record = self._record(1000, "class")
        build_release.attach_orbital_lifetime([record], self._root(1000))
        self.assertIn("Its own tracked orbit is losing about", record["purpose"])
        self.assertTrue(record["purpose"].startswith("Something already written."))

    def test_a_curated_card_is_left_alone(self):
        """It is interesting on a dead cubesat and noise on a research

        satellite whose card already says what it does. Sean: "I just don't
        want useless filler or redundant bullshit."
        """
        record = self._record(1000, "curated")
        build_release.attach_orbital_lifetime([record], self._root(1000))
        self.assertNotIn("tracked orbit", record["purpose"])

    def test_a_non_leo_object_is_left_alone(self):
        record = self._record(1000, "class", orbit="GEO")
        build_release.attach_orbital_lifetime([record], self._root(1000))
        self.assertNotIn("tracked orbit", record["purpose"])

    def test_an_unreadable_archive_leaves_the_class_description_intact(self):
        record = self._record(1000, "class")
        build_release.attach_orbital_lifetime([record], Path("/nonexistent"))
        self.assertEqual(record["purpose"], "Something already written.")


if __name__ == "__main__":
    unittest.main()
