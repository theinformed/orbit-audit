"""The ground-station table's guards, and the shape of what it publishes.

No network. Every case is a pure function of a dict.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pipeline.ground_stations import (
    RELATIONSHIP_LABELS,
    STATION_TABLE,
    StationTableError,
    build_ground_station_bundle,
    load_station_table,
    publish,
    resolve_links,
    validate_station_table,
)


def _separation_km(first: dict, second: dict) -> float:
    import math

    radius = 6371.0088
    lat1, lat2 = math.radians(first["latitudeDeg"]), math.radians(second["latitudeDeg"])
    delta_lon = math.radians(second["longitudeDeg"] - first["longitudeDeg"])
    inner = (math.sin((lat2 - lat1) / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(inner))


def minimal_table() -> dict:
    return {
        "schema": 1,
        "policy": {
            "militarySites": "excluded",
            "militarySitesRationale": "Pending the site owner's decision.",
        },
        "stations": [
            {
                "id": "example-station",
                "name": "Example Station",
                "network": "Example Network",
                "operator": "Example Agency",
                "operatorKind": "civil-agency",
                "country": "Neverland",
                "latitudeDeg": 12.5,
                "longitudeDeg": -34.5,
                "coordinatePrecision": "published-survey",
                "roles": ["data-downlink"],
                "bands": ["S", "X"],
                "source": "https://example.gov/stations",
                "sourceName": "Example Agency station list",
                "sourceRetrieved": "2026-08-07",
                "licence": "Public domain",
            }
        ],
        "links": [
            {
                "stationId": "example-station",
                "noradId": 12345,
                "satelliteName": "EXAMPLE-1",
                "relationship": "data-downlink",
                "evidence": "Example Agency states that EXAMPLE-1 mission data is received at Example Station.",
                "source": "https://example.gov/example-1",
                "sourceName": "Example Agency mission page",
                "sourceRetrieved": "2026-08-07",
            }
        ],
    }


class ValidatorTests(unittest.TestCase):
    def test_a_minimal_table_validates(self) -> None:
        validate_station_table(minimal_table())

    def test_station_without_a_citation_is_refused(self) -> None:
        table = minimal_table()
        table["stations"][0]["source"] = "Example Agency, personal communication"
        with self.assertRaisesRegex(StationTableError, "citation must be a URL"):
            validate_station_table(table)

    def test_link_without_a_citation_is_refused(self) -> None:
        table = minimal_table()
        del table["links"][0]["source"]
        with self.assertRaisesRegex(StationTableError, "citation must be a URL"):
            validate_station_table(table)

    def test_link_without_the_published_sentence_is_refused(self) -> None:
        """A relationship nobody can check is the thing this table exists to prevent."""
        table = minimal_table()
        table["links"][0]["evidence"] = "downlink"
        with self.assertRaisesRegex(StationTableError, "too short to be a published statement"):
            validate_station_table(table)

    def test_an_unknown_relationship_is_refused_rather_than_passed_through(self) -> None:
        table = minimal_table()
        table["links"][0]["relationship"] = "assessed-association"
        with self.assertRaisesRegex(StationTableError, "relationship must be one of"):
            validate_station_table(table)

    def test_an_unknown_role_is_refused(self) -> None:
        table = minimal_table()
        table["stations"][0]["roles"] = ["signals-intelligence"]
        with self.assertRaisesRegex(StationTableError, "unknown value"):
            validate_station_table(table)

    def test_military_site_is_refused_while_the_policy_excludes_them(self) -> None:
        table = minimal_table()
        table["stations"][0]["operatorKind"] = "military"
        with self.assertRaisesRegex(StationTableError, "site owner's decision"):
            validate_station_table(table)

    def test_military_site_validates_once_the_policy_says_so(self) -> None:
        table = minimal_table()
        table["stations"][0]["operatorKind"] = "military"
        table["policy"]["militarySites"] = "included"
        validate_station_table(table)

    def test_an_amateur_station_must_be_published_at_reduced_precision(self) -> None:
        table = minimal_table()
        table["stations"][0]["operatorKind"] = "amateur"
        with self.assertRaisesRegex(StationTableError, "privacy-reduced"):
            validate_station_table(table)
        table["stations"][0]["coordinatePrecision"] = "privacy-reduced"
        validate_station_table(table)

    def test_a_personal_field_on_a_station_is_refused(self) -> None:
        for field in ("address", "contact", "email", "ownerName", "callsign"):
            table = minimal_table()
            table["stations"][0][field] = "something"
            with self.assertRaisesRegex(StationTableError, "never a person"):
                validate_station_table(table)

    def test_coordinates_outside_the_world_are_refused(self) -> None:
        table = minimal_table()
        table["stations"][0]["latitudeDeg"] = 112
        with self.assertRaisesRegex(StationTableError, "latitudeDeg"):
            validate_station_table(table)
        table = minimal_table()
        table["stations"][0]["longitudeDeg"] = 361
        with self.assertRaisesRegex(StationTableError, "longitudeDeg"):
            validate_station_table(table)

    def test_a_link_to_an_unknown_station_is_refused(self) -> None:
        table = minimal_table()
        table["links"][0]["stationId"] = "somewhere-else"
        with self.assertRaisesRegex(StationTableError, "is not a station in this table"):
            validate_station_table(table)

    def test_duplicate_station_ids_are_refused(self) -> None:
        table = minimal_table()
        table["stations"].append(copy.deepcopy(table["stations"][0]))
        with self.assertRaisesRegex(StationTableError, "duplicate id"):
            validate_station_table(table)

    def test_duplicate_links_are_refused(self) -> None:
        table = minimal_table()
        table["links"].append(copy.deepcopy(table["links"][0]))
        with self.assertRaisesRegex(StationTableError, "duplicates an earlier link"):
            validate_station_table(table)

    def test_the_policy_block_is_required(self) -> None:
        table = minimal_table()
        del table["policy"]
        with self.assertRaisesRegex(StationTableError, "policy"):
            validate_station_table(table)


class BundleTests(unittest.TestCase):
    def test_links_split_on_whether_the_object_is_in_this_release(self) -> None:
        table = minimal_table()
        resolved, unresolved = resolve_links(table, [12345])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(unresolved, [])
        resolved, unresolved = resolve_links(table, [999])
        self.assertEqual(resolved, [])
        self.assertEqual(len(unresolved), 1)

    def test_a_published_link_outside_the_catalog_is_kept_and_reported(self) -> None:
        """Capped catalogs must not silently delete a cited relationship."""
        bundle = build_ground_station_bundle(minimal_table(), [])
        self.assertEqual(bundle["linkCount"], 0)
        self.assertEqual(len(bundle["linksOutsideCatalog"]), 1)
        self.assertEqual(bundle["linksOutsideCatalog"][0]["satelliteName"], "EXAMPLE-1")

    def test_every_published_link_carries_its_citation_into_the_artifact(self) -> None:
        bundle = build_ground_station_bundle(minimal_table(), [12345])
        for link in bundle["links"]:
            self.assertTrue(link["source"].startswith("https://"))
            self.assertTrue(link["sourceName"])
            self.assertGreaterEqual(len(link["evidence"]), 24)
            self.assertEqual(link["relationshipLabel"], RELATIONSHIP_LABELS[link["relationship"]])

    def test_the_bundle_states_that_nothing_is_inferred(self) -> None:
        bundle = build_ground_station_bundle(minimal_table(), [12345])
        self.assertIn("inferred", bundle["limitation"])
        self.assertIn("not a complete census", bundle["limitation"])

    def test_publish_returns_a_manifest_fragment(self) -> None:
        written: dict[str, object] = {}

        def write_artifact(data_root: Path, prefix: str, value: object) -> tuple[str, str]:
            written["prefix"] = prefix
            written["value"] = value
            return f"artifacts/{prefix}-abc.json", "abc"

        table_path = Path(__file__).with_name("_ground_stations_fixture.json")
        table_path.write_text(json.dumps(minimal_table()))
        try:
            fragment = publish(Path("."), write_artifact, [12345], table_path=table_path)
        finally:
            table_path.unlink()
        self.assertEqual(written["prefix"], "ground-stations")
        self.assertEqual(fragment["groundStations"]["stationCount"], 1)
        self.assertEqual(fragment["groundStations"]["linkCount"], 1)


class ShippedTableTests(unittest.TestCase):
    """The table that actually ships has to survive its own validator."""

    def test_the_checked_in_table_validates(self) -> None:
        table = load_station_table(STATION_TABLE)
        self.assertGreater(len(table["stations"]), 20)

    def test_every_shipped_station_carries_a_reachable_looking_citation(self) -> None:
        table = load_station_table(STATION_TABLE)
        for station in table["stations"]:
            self.assertTrue(
                station["source"].startswith("https://"),
                f"{station['id']} cites {station['source']!r}",
            )

    def test_the_shipped_table_excludes_military_sites_until_sean_decides(self) -> None:
        table = load_station_table(STATION_TABLE)
        self.assertEqual(table["policy"]["militarySites"], "excluded")
        self.assertEqual(
            [station["id"] for station in table["stations"] if station["operatorKind"] == "military"],
            [],
        )

    def test_every_link_is_stamped_with_the_name_its_norad_id_resolves_to(self) -> None:
        """A link's object has to be the object the publisher meant.

        ``noradId`` is five digits a human typed next to a quotation. Nothing
        else in the row can catch a slip in it: the citation still checks out,
        the evidence is still a real published sentence, and the map still
        draws a line — to the wrong spacecraft. This nearly happened once
        already, with 29268 typed for SAPPHIRE when 29268 is KOMPSAT 2.

        So every id is resolved against a checked-in registry fixture and the
        answer is stored on the row. A mistyped digit now surfaces as a name
        that does not match, in a diff, instead of as a quiet wrong line.
        """
        fixture = json.loads((Path(__file__).parent / "data" / "norad-registry-names.json").read_text())
        registry = fixture["names"]
        table = load_station_table(STATION_TABLE)
        for link in table["links"]:
            norad = str(link["noradId"])
            self.assertIn(
                norad,
                registry,
                f"{link['stationId']} cites NORAD {norad}, which is not in the registry fixture. "
                "Add it there from the offline SATCAT mirror rather than trusting the row.",
            )
            self.assertEqual(
                link.get("registryName"),
                registry[norad],
                f"{link['stationId']} -> NORAD {norad}: the row is stamped "
                f"{link.get('registryName')!r} but the registry says {registry[norad]!r}",
            )
            self.assertTrue(
                str(link.get("registrySource") or "").strip(),
                f"{link['stationId']} -> NORAD {norad}: a registry name needs to say which registry",
            )

    def test_the_registry_fixture_covers_exactly_what_the_table_uses(self) -> None:
        """A stale fixture would let a dropped object keep vouching for itself."""
        fixture = json.loads((Path(__file__).parent / "data" / "norad-registry-names.json").read_text())
        table = load_station_table(STATION_TABLE)
        self.assertEqual(
            sorted(fixture["names"]),
            sorted({str(link["noradId"]) for link in table["links"]}),
        )

    def test_no_two_stations_sit_on_top_of_each_other_undeclared(self) -> None:
        """Two operators publishing one antenna farm is two pins claiming two farms.

        Viasat's "Alice Springs" is 0.26 km from the Geoscience Australia pin
        and SSC's "Siracha" is 0.25 km from GISTDA's. Deep-space complexes do
        genuinely put dishes a few hundred metres apart, so proximity cannot
        simply be banned — it has to be declared, with a reason, in the diff.
        """
        table = load_station_table(STATION_TABLE)
        threshold = table.get("coLocationThresholdKm", 3.0)
        declared = {
            tuple(sorted(entry["stations"])) for entry in table.get("coLocated", [])
        }
        stations = table["stations"]
        undeclared = []
        for index, first in enumerate(stations):
            for second in stations[index + 1:]:
                gap = _separation_km(first, second)
                if gap >= threshold:
                    continue
                key = tuple(sorted((first["id"], second["id"])))
                if key not in declared:
                    undeclared.append(f"{key[0]} / {key[1]} ({gap:.2f} km)")
        self.assertEqual(undeclared, [], "these pairs may be one site entered twice")

    def test_every_co_location_declaration_names_real_stations_and_a_reason(self) -> None:
        table = load_station_table(STATION_TABLE)
        ids = {station["id"] for station in table["stations"]}
        entries = table.get("coLocated", [])
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(entry["stations"]), 2)
            for station_id in entry["stations"]:
                self.assertIn(station_id, ids)
            self.assertGreater(len(entry["reason"]), 24, entry["stations"])

    def test_the_shipped_table_publishes_some_links_in_both_directions(self) -> None:
        table = load_station_table(STATION_TABLE)
        self.assertGreater(len(table["links"]), 10)
        stations_with_links = {link["stationId"] for link in table["links"]}
        satellites_with_links = {link["noradId"] for link in table["links"]}
        self.assertGreater(len(stations_with_links), 4)
        self.assertGreater(len(satellites_with_links), 4)


if __name__ == "__main__":
    unittest.main()
