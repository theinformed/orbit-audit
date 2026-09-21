"""Guards on the hosted-payload / shared-mission table.

Two of these run against the *real* offline registry mirror rather than a
fixture, for the reason `tests/test_catalog_name_matching.py` was written: a
hand-typed catalog ID once pointed Canada's SAPPHIRE at KOMPSAT 2, and a fixture
of ten names would have passed every day it was wrong. If no mirror is present
those cases skip loudly rather than passing quietly.

No test here touches the network. The table is a file on disk and the registry
is a mirror on disk.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.catalog_audit import name_tokens
from pipeline.programme_participation import (
    PARTICIPATION_KINDS,
    PARTICIPATION_STATUS,
    load_participation,
    participation_disclosure,
    participation_index,
    programme_catalog,
    published_entry,
    validate_participation,
)

ROOT = Path(__file__).resolve().parents[1]
TABLE = load_participation()
ENTRIES = {key: entry for key, entry in TABLE.items() if not key.startswith("$")}


def _registry() -> dict[int, str]:
    """Catalog ID -> registry name, from whichever offline mirror is present."""
    registry: dict[int, str] = {}
    for path, key in (
        (ROOT / "runtime" / "spacetrack-mirror" / "satcat-active.json", "SATNAME"),
        (ROOT / "runtime" / "celestrak-mirror" / "satcat-active.json", "OBJECT_NAME"),
    ):
        if not path.is_file():
            continue
        for row in json.loads(path.read_text()):
            try:
                catalog_id = int(row["NORAD_CAT_ID"])
            except (KeyError, TypeError, ValueError):
                continue
            name = str(row.get(key) or row.get("OBJECT_NAME") or "").strip()
            if name:
                registry.setdefault(catalog_id, name)
    return registry


REGISTRY = _registry()


class ShippedTableTests(unittest.TestCase):
    def test_the_shipped_table_validates(self):
        validate_participation(TABLE)

    def test_every_entry_carries_a_public_citation(self):
        """No citation, no entry. This is the whole boundary of the feature."""
        for key, entry in ENTRIES.items():
            with self.subTest(entry=key):
                self.assertTrue(str(entry["source"]).startswith(("https://", "http://")))
                self.assertTrue(str(entry["programmeSource"]).startswith(("https://", "http://")))
                self.assertTrue(str(entry["sourceName"]).strip())

    def test_nothing_attaches_by_name(self):
        """The claim is keyed to a catalog ID, never to a spacecraft name.

        26 original Iridium spacecraft are still on orbit with names that no
        rule can separate from the 80 Iridium NEXT spacecraft that carry the
        Aireon payload. A name rule here attaches an ADS-B receiver to 1990s
        hardware that has never had one.
        """
        for key, entry in ENTRIES.items():
            with self.subTest(entry=key):
                self.assertEqual(entry.get("match"), "norad")
                self.assertNotIn("names", entry)
                self.assertNotIn("prefix", entry)

    def test_participation_kinds_are_from_the_closed_set(self):
        for key, entry in ENTRIES.items():
            with self.subTest(entry=key):
                self.assertIn(entry["participation"], PARTICIPATION_KINDS)
                self.assertIn(entry.get("status", "unstated"), PARTICIPATION_STATUS)


class RegistryPinTests(unittest.TestCase):
    """Every catalog ID must resolve to the spacecraft the author meant.

    The SAPPHIRE guard from `docs/catalog-accuracy-audit.md` §5A.2, applied to a
    second hand-written table.
    """

    def test_every_catalog_id_names_the_spacecraft_it_claims(self):
        if not REGISTRY:
            self.skipTest("no registry mirror present")
        for key, entry in ENTRIES.items():
            for catalog_id, intended in zip(entry["norad"], entry["noradNames"]):
                with self.subTest(entry=key, norad=catalog_id):
                    actual = REGISTRY.get(catalog_id)
                    self.assertIsNotNone(
                        actual, f"{key}: {catalog_id} is not in the registry at all"
                    )
                    self.assertTrue(
                        set(name_tokens(intended)) & set(name_tokens(actual)),
                        f"{key} claims catalog ID {catalog_id} as {intended!r}, "
                        f"which the registry calls {actual!r}",
                    )

    def test_the_iridium_entry_excludes_every_original_iridium_spacecraft(self):
        """The specific mis-attachment this table is shaped to prevent.

        Aireon flies on Iridium NEXT. The block-1 spacecraft launched between
        1997 and 2002 do not carry it, and their registry names are identical in
        form. This asserts the outcome rather than the mechanism, so it still
        fails if the mechanism is later replaced by something looser.
        """
        if not REGISTRY:
            self.skipTest("no registry mirror present")
        launches: dict[int, str] = {}
        path = ROOT / "runtime" / "spacetrack-mirror" / "satcat-active.json"
        if not path.is_file():
            self.skipTest("no space-track mirror present")
        for row in json.loads(path.read_text()):
            try:
                launches[int(row["NORAD_CAT_ID"])] = str(row.get("LAUNCH") or "")
            except (KeyError, TypeError, ValueError):
                continue
        claimed = {
            catalog_id
            for entry in ENTRIES.values()
            if entry["programmeId"] == "aireon"
            for catalog_id in entry["norad"]
        }
        self.assertTrue(claimed, "the Aireon entry has gone missing")
        for catalog_id in claimed:
            with self.subTest(norad=catalog_id):
                self.assertGreaterEqual(
                    launches.get(catalog_id, ""),
                    "2017-01-14",
                    f"catalog ID {catalog_id} predates the first Iridium NEXT launch",
                )


class IndexTests(unittest.TestCase):
    def test_an_object_can_hold_more_than_one_programme(self):
        index = participation_index(TABLE)
        counts = sorted((len(v) for v in index.values()), reverse=True)
        self.assertTrue(counts)
        # Not an accident of the current data: the field exists precisely
        # because one spacecraft can serve several programmes at once.
        self.assertGreaterEqual(counts[0], 2)

    def test_published_records_carry_the_reader_facing_fields(self):
        for entries in participation_index(TABLE).values():
            for record in entries:
                self.assertEqual(
                    record["participationLabel"], PARTICIPATION_KINDS[record["participation"]]
                )
                for field in ("programme", "sponsor", "operator", "note", "source", "sourceName"):
                    self.assertTrue(str(record[field]).strip())

    def test_the_programme_catalog_counts_objects_it_actually_attached(self):
        index = participation_index(TABLE)
        rows = programme_catalog(TABLE, index)
        self.assertTrue(rows)
        total = sum(row["objects"] for row in rows)
        self.assertEqual(total, sum(len(entries) for entries in index.values()))
        for row in rows:
            with self.subTest(programme=row["programmeId"]):
                self.assertTrue(str(row["summary"]).strip())
                if row["participantsPublished"]:
                    self.assertGreater(row["objects"], 0)
                else:
                    # A programme the public record documents without naming its
                    # spacecraft is listed with the reason, not quietly dropped.
                    self.assertEqual(row["objects"], 0)
                    self.assertTrue(str(row["participantsNote"]).strip())

    def test_a_programme_whose_participants_are_not_public_still_appears(self):
        """The CBSP case, asserted as an outcome rather than as a mechanism."""
        rows = {row["programmeId"]: row for row in programme_catalog(TABLE, participation_index(TABLE))}
        unattached = [row for row in rows.values() if not row["participantsPublished"]]
        self.assertTrue(
            unattached,
            "the leased-capacity programme with no publicly identified spacecraft has gone missing; "
            "it is the clearest teaching case in the table",
        )


class ValidatorTests(unittest.TestCase):
    """Each rule needs a test that fails when the rule is removed."""

    def _entry(self, **overrides):
        entry = {
            "match": "norad",
            "norad": [25544],
            "noradNames": ["ISS (ZARYA)"],
            "programmeId": "example",
            "programme": "Example Programme",
            "abbreviation": "EX",
            "programmeSummary": "A programme.",
            "programmeSource": "https://example.gov/programme",
            "sponsor": "An agency",
            "operator": "An operator",
            "participation": "hosted-payload",
            "status": "operational",
            "note": "A sentence.",
            "source": "https://example.gov/entry",
            "sourceName": "An agency",
        }
        entry.update(overrides)
        return {"Example": entry}

    def test_a_valid_entry_passes(self):
        validate_participation(self._entry())

    def test_a_name_match_is_refused(self):
        with self.assertRaises(ValueError):
            validate_participation(self._entry(match="prefix"))

    def test_a_missing_citation_is_refused(self):
        with self.assertRaises(ValueError):
            validate_participation(self._entry(source=""))
        with self.assertRaises(ValueError):
            validate_participation(self._entry(programmeSource="not-a-url"))

    def test_unstamped_catalog_ids_are_refused(self):
        with self.assertRaises(ValueError):
            validate_participation(self._entry(norad=[25544, 20580], noradNames=["ISS (ZARYA)"]))

    def test_an_unknown_participation_kind_is_refused(self):
        with self.assertRaises(ValueError):
            validate_participation(self._entry(participation="probably-related"))

    def test_a_missing_sponsor_is_refused(self):
        with self.assertRaises(ValueError):
            validate_participation(self._entry(sponsor=" "))

    def test_one_programme_may_not_be_described_two_ways(self):
        table = self._entry()
        table["Other"] = dict(table["Example"], programmeSummary="Something else.")
        with self.assertRaises(ValueError):
            validate_participation(table)

    def test_the_same_object_may_not_be_claimed_twice_for_one_programme(self):
        table = self._entry()
        table["Other"] = dict(table["Example"])
        with self.assertRaises(ValueError):
            validate_participation(table)

    def test_an_empty_object_list_needs_an_explicit_reason(self):
        with self.assertRaises(ValueError):
            validate_participation(self._entry(norad=[], noradNames=[]))
        validate_participation(
            self._entry(
                norad=[],
                noradNames=[],
                participantsNotPublic=True,
                participantsNote="The provider is named; the spacecraft are not.",
            )
        )

    def test_an_unattached_programme_may_not_also_claim_objects(self):
        with self.assertRaises(ValueError):
            validate_participation(
                self._entry(participantsNotPublic=True, participantsNote="Not named.")
            )

    def test_a_repeated_catalog_id_inside_one_entry_is_refused(self):
        with self.assertRaises(ValueError):
            validate_participation(
                self._entry(norad=[25544, 25544], noradNames=["ISS (ZARYA)", "ISS (ZARYA)"])
            )


class DisclosureTests(unittest.TestCase):
    def test_the_sentence_names_the_operator_the_programme_and_the_sponsor(self):
        record = published_entry(
            {
                "programmeId": "gbs",
                "programme": "Global Broadcast Service",
                "abbreviation": "GBS",
                "sponsor": "the U.S. Department of Defense",
                "operator": "the U.S. Navy",
                "participation": "hosted-payload",
                "status": "operational",
                "note": "A sentence.",
                "source": "https://example.mil/gbs",
                "sourceName": "An agency",
            }
        )
        prose = participation_disclosure([record], "the U.S. Navy")
        self.assertIn("Global Broadcast Service (GBS)", prose)
        self.assertIn("the U.S. Department of Defense", prose)
        self.assertIn("An agency", prose)
        self.assertIn("owned and operated by one organisation", prose)

    def test_an_ended_arrangement_is_not_written_in_the_present_tense(self):
        record = published_entry(
            {
                "programmeId": "chirp",
                "programme": "CHIRP",
                "sponsor": "an agency",
                "operator": "an operator",
                "participation": "hosted-payload",
                "status": "ended",
                "note": "A sentence.",
                "source": "https://example.gov/chirp",
                "sourceName": "An agency",
            }
        )
        prose = participation_disclosure([record], "an operator")
        self.assertIn("carried a payload", prose)
        self.assertIn("This arrangement has ended.", prose)

    def test_no_participation_produces_no_prose(self):
        self.assertEqual(participation_disclosure([], "an operator"), "")


if __name__ == "__main__":
    unittest.main()
