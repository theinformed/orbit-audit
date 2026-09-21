import unittest

from pipeline.build_release import (
    catalog_priority,
    classify,
    identify_launch_group,
    normalize_launch_date,
    select_catalog_satellites,
)


def catalog_record(
    catalog_id: int,
    name: str,
    *,
    launch_date: str | None,
    launch_group: str | None,
    constellation: str | None = "Starlink",
    mission: str = "communications",
    sector: str = "commercial",
    purpose_kind: str = "template",
):
    return {
        "id": catalog_id,
        "name": name,
        "launchDate": launch_date,
        "launchGroup": launch_group,
        "constellation": constellation,
        "mission": mission,
        "sector": sector,
        "purposeKind": purpose_kind,
    }


class AuthoritativeSatelliteClassificationTests(unittest.TestCase):
    def assert_classification(self, name, expected):
        self.assertEqual(classify(name, "US"), expected)

    def test_named_military_communications_programs(self):
        for name in (
            "UFO 2 (USA 95)",
            "UFO 4 (USA 108)",
            "UFO 10 (USA 146)",
            "UFO 11 (USA 174)",
        ):
            self.assert_classification(
                name,
                ("communications", "military", "UHF Follow-On (UFO)", "U.S. Navy", "high"),
            )

        self.assert_classification(
            "TACSAT 4",
            (
                "communications",
                "military",
                "TacSat",
                "U.S. Navy / Naval Research Laboratory",
                "high",
            ),
        )
        self.assert_classification(
            "ATHENA-FIDUS",
            ("communications", "military", None, "France / Italy", "high"),
        )

    def test_arctic_broadband_mission_is_mixed_use_communications(self):
        for name in ("ASBM-1", "ASBM-2"):
            self.assert_classification(
                name,
                (
                    "communications",
                    "mixed",
                    "Arctic Satellite Broadband Mission",
                    "Space Norway",
                    "high",
                ),
            )

    def test_similar_but_unsupported_names_remain_unclassified(self):
        for name in ("UFO 3", "TACSAT 3", "TACSAT 6", "ASBM-3", "ATHENA-FIDUS X"):
            mission, sector, constellation, _, confidence = classify(name, "US")
            self.assertEqual(mission, "other", name)
            self.assertEqual(sector, "unknown", name)
            self.assertIsNone(constellation, name)
            self.assertEqual(confidence, "low", name)


class CatalogSelectionTests(unittest.TestCase):
    def test_launch_metadata_normalization(self):
        self.assertEqual(identify_launch_group("2026-175A"), "2026-175")
        self.assertEqual(identify_launch_group("2026-175AZ"), "2026-175")
        self.assertIsNone(identify_launch_group("STARLINK-38184"))
        self.assertEqual(normalize_launch_date("2026-08-01T12:30:00Z"), "2026-08-01")
        self.assertIsNone(normalize_launch_date("TBD"))
        self.assertIsNone(normalize_launch_date(None))

    def test_complete_recent_cohort_is_reserved_then_older_starlinks_are_hash_sampled(self):
        recent = [
            catalog_record(1001, "STARLINK-38184", launch_date="2026-08-01", launch_group="2026-175"),
            # A missing date on one row must not split a cohort whose other row proves it is recent.
            catalog_record(1002, "STARLINK-38112", launch_date=None, launch_group="2026-175"),
        ]
        older = [
            catalog_record(10, "STARLINK-0001", launch_date="2025-01-01", launch_group="2025-001"),
            catalog_record(20, "STARLINK-0002", launch_date="2025-01-02", launch_group="2025-002"),
            catalog_record(30, "STARLINK-0003", launch_date="2025-01-03", launch_group="2025-003"),
            catalog_record(40, "STARLINK-0004", launch_date="2025-01-04", launch_group="2025-004"),
        ]
        newest_upstream_launch = catalog_record(
            2000,
            "UNRELATED PAYLOAD",
            launch_date="2026-08-06",
            launch_group="2026-178",
            constellation="Unrelated",
            mission="other",
            sector="unknown",
        )

        selected = select_catalog_satellites(recent + older + [newest_upstream_launch], 4)
        selected_ids = {record["id"] for record in selected}
        expected_older = sorted(older, key=catalog_priority)[:2]

        self.assertEqual(len(selected), 4)
        self.assertTrue({1001, 1002}.issubset(selected_ids))
        self.assertEqual(selected_ids - {1001, 1002}, {record["id"] for record in expected_older})
        self.assertNotEqual(
            [record["id"] for record in expected_older],
            [record["id"] for record in sorted(older, key=lambda record: record["name"])[:2]],
        )

    def test_ceiling_cannot_silently_split_promised_recent_cohort(self):
        recent = [
            catalog_record(index, f"STARLINK-{index}", launch_date="2026-08-01", launch_group="2026-175")
            for index in range(3)
        ]
        with self.assertRaisesRegex(RuntimeError, "complete recent launch cohorts"):
            select_catalog_satellites(recent, 2)


if __name__ == "__main__":
    unittest.main()
