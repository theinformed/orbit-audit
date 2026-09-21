"""Guards over the United States partition of the curated override table.

WHY THIS FILE EXISTS. Four defect classes in this repository all came from a
description reaching a spacecraft it was not written about: `TERRA` claimed
`SKYTERRA 1`, `DSP` claimed `RIGIDSPHERE 2`, and three rules written against
CelesTrak's spelling (`SES-`, `EUTE`, `^GSAT-(?:8|10|15)`) matched NOTHING at
all because this catalog is built from space-track, which writes `GSAT 8`. Both
failures are silent: one publishes a confident falsehood, the other publishes
nothing while the table looks full.

So this partition is written entirely as `match: "norad"` entries -- a catalog
number cannot be a coincidental substring of anything -- and the tests below are
the negative controls that say so, run against the REAL published catalog rather
than a fixture.

THE TRAP THIS PARTITION ACTUALLY HIT, and the reason the GPS test is specific.
The obvious way to identify a GPS satellite is its PRN: CelesTrak names the
operational objects `GPS BIIR-5 (PRN 22)` and the Coast Guard's constellation
table gives PRN -> SVN, plane and slot. But a PRN is a *slot in a broadcast
plan*, not an identity: it is handed from a retiring satellite to its
replacement. On the day this partition was written, NAVCEN listed PRN 13 against
SVN 43 -- a Block IIR spacecraft launched in 1997 and decommissioned in April
2026 -- while CelesTrak had already assigned PRN 13 to `GPS BIII-10`, launched
in 2026. A PRN join would have described a brand-new GPS III spacecraft as a
twenty-nine-year-old Block IIR. `test_the_prn_handover_did_not_move_a_block`
is the assertion that it did not.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from pipeline import build_release
from pipeline.build_release import load_overrides, matching_override, validate_overrides
from pipeline import satnogs_verify

ROOT = Path(__file__).resolve().parents[1]
PARTITION_PATH = ROOT / "data" / "satellite_overrides_us.json"
PARTITION = json.loads(PARTITION_PATH.read_text())
MERGED = load_overrides()


def _published_catalog() -> dict[int, dict]:
    try:
        catalog = satnogs_verify.published_catalog(ROOT / "public" / "data")
    except Exception:  # pragma: no cover - no release published on this machine
        return {}
    return {int(row["id"]): row for row in catalog["satellites"] if row.get("id") is not None}


CATALOG = _published_catalog()
CLAIMED = {int(n) for entry in PARTITION.values() for n in entry.get("norad", ())}


class PartitionShapeTests(unittest.TestCase):
    def test_the_merged_table_including_this_partition_is_valid(self):
        validate_overrides(MERGED)

    def test_every_entry_attaches_by_catalog_number_only(self):
        """No entry here may be reachable by name, in either direction.

        `matching_override` reads the KEY as the name fragment for `prefix` and
        `token` mode. Every key in this file is deliberately shaped `@us/...`,
        which is not a substring of any spacecraft name, so even a future edit
        that changed a mode by mistake still could not attach one of these
        paragraphs to a name it happens to share letters with.
        """
        for key, entry in PARTITION.items():
            with self.subTest(override=key):
                self.assertEqual(entry.get("match"), "norad")
                self.assertTrue(entry.get("norad"), "an entry with no catalog number claims nothing")
                self.assertTrue(key.startswith("@us/"), "keys are namespaced so they cannot collide")
                self.assertTrue(entry.get("individual"), "these are per-spacecraft descriptions")

    def test_every_description_carries_a_source_url(self):
        for key, entry in PARTITION.items():
            with self.subTest(override=key):
                self.assertTrue(entry.get("purpose"), "an entry with no description says nothing")
                self.assertTrue(str(entry.get("source", "")).startswith("https://"))

    def test_an_assessed_entry_names_its_assessor(self):
        for key, entry in PARTITION.items():
            if entry.get("evidence") == "assessed":
                with self.subTest(override=key):
                    self.assertTrue(str(entry.get("assessedBy", "")).strip())

    def test_no_catalog_number_is_claimed_twice_across_the_whole_table(self):
        """Two partitions claiming one spacecraft is decided by dict order today."""
        seen: dict[int, str] = {}
        for key, entry in MERGED.items():
            if entry.get("match") != "norad":
                continue
            for number in entry.get("norad", ()):
                previous = seen.get(int(number))
                self.assertIsNone(
                    previous, f"catalog number {number} claimed by both {previous!r} and {key!r}"
                )
                seen[int(number)] = key


class AttachmentTests(unittest.TestCase):
    """Run against the real published catalog, not a fixture."""

    def setUp(self):
        if not CATALOG:
            self.skipTest("no published catalog on this machine; run where a release exists")

    def test_every_claimed_object_receives_this_partition_entry(self):
        for key, entry in PARTITION.items():
            for number in entry.get("norad", ()):
                with self.subTest(override=key, norad=number):
                    record = CATALOG.get(int(number))
                    self.assertIsNotNone(record, f"{key} claims {number}, which is not in the catalog")
                    matched = matching_override(record["name"], MERGED, int(number))
                    self.assertIsNotNone(matched)
                    self.assertEqual(matched[1], "norad")
                    self.assertEqual(matched[0].get("purpose"), entry["purpose"])

    def test_the_recorded_name_still_matches_the_catalog(self):
        """A renamed object is how a correct catalog number starts lying."""
        for key, entry in PARTITION.items():
            names = entry.get("noradNames") or []
            for number, name in zip(entry.get("norad", ()), names):
                record = CATALOG.get(int(number))
                if record is None:
                    continue
                with self.subTest(override=key):
                    self.assertEqual(record["name"], name)

    def test_no_description_reaches_an_object_this_partition_did_not_claim(self):
        """The negative control. Sweep all 8,000 objects, not a sample."""
        texts = {entry["purpose"]: key for key, entry in PARTITION.items()}
        leaked: list[str] = []
        for number, record in CATALOG.items():
            if number in CLAIMED:
                continue
            matched = matching_override(record["name"], MERGED, number)
            if matched and matched[0].get("purpose") in texts:
                leaked.append(f"{record['name']} ({number}) picked up {texts[matched[0]['purpose']]}")
        self.assertEqual(leaked, [], "\n".join(leaked[:20]))

    def test_named_siblings_that_must_not_be_swept_up(self):
        """The specific near-misses, named, so a future edit trips over them.

        Each is a real object in this catalog whose name shares a prefix with a
        family in this partition and which belongs to somebody else.
        """
        for name in ("YAMAL 401", "SKYTERRA 1", "GALAXY 19", "STARLINK-1007"):
            candidates = [r for r in CATALOG.values() if r["name"].upper().startswith(name.split()[0])]
            if not candidates:
                continue
            for record in candidates:
                if record["id"] in CLAIMED:
                    continue
                with self.subTest(name=record["name"]):
                    matched = matching_override(record["name"], MERGED, record["id"])
                    if matched is None:
                        continue
                    self.assertNotIn(
                        matched[0].get("purpose"),
                        {entry["purpose"] for entry in PARTITION.values()},
                        f"{record['name']} picked up a United States partition description",
                    )


#: Constellations this partition covers completely, as the catalogue spells them.
#: Checked against the real published names -- `HAWK-`, not `HAWKEYE`; `GHGSAT-C`,
#: not `GHGSat-C`; `TOMORROW-S`, not `TOMORROW.IO`. Three name rules in this
#: repository once matched NOTHING because they were written against CelesTrak's
#: spelling while the catalogue is built from space-track.
COVERED_FAMILIES = (
    "NAVSTAR", "HAWK-", "SKYSAT", "PELICAN-", "GHGSAT-C", "TOMORROW-S",
    "APRIZESAT", "AEROCUBE", "CHECKMATE", "WILDFIRE", "SPACEMOBILE", "STARLING",
)


class FamilyCoverageTests(unittest.TestCase):
    """A tripwire, and it is meant to go off.

    These constellations are covered object by object, by catalogue number, which
    is the only attachment this partition allows. The cost of that choice is that
    a NEWLY LAUNCHED member gets no description until somebody adds a line -- and
    the failure mode of "no description" is silence, which is exactly what the
    site's owner was complaining about when this work started.

    So the silence is converted into a red test. When HawkEye flies Cluster 15 or
    the Space Force launches GPS III SV11, this fails and names the object. That
    is not a broken test; it is the work item. Add the entry, or drop the family
    from COVERED_FAMILIES with a reason.
    """

    def setUp(self):
        if not CATALOG:
            self.skipTest("no published catalog on this machine; run where a release exists")

    def test_the_catalogue_spells_these_families_the_way_the_rules_do(self):
        """A family prefix that matches nothing is a rule that silently does nothing."""
        for prefix in COVERED_FAMILIES:
            with self.subTest(family=prefix):
                hits = [r for r in CATALOG.values() if r["name"].upper().startswith(prefix)]
                self.assertTrue(hits, f"no catalogue object starts with {prefix!r}; the rule is stale")

    def test_no_member_of_a_covered_family_is_left_undescribed(self):
        missing: list[str] = []
        for record in CATALOG.values():
            upper = record["name"].upper()
            if not any(upper.startswith(prefix) for prefix in COVERED_FAMILIES):
                continue
            if record["id"] not in CLAIMED:
                missing.append(f"{record['name']} ({record['id']}) launched {record.get('launchDate')}")
        self.assertEqual(
            missing, [],
            "new members of a covered family carry no description:\n" + "\n".join(sorted(missing)),
        )


class GpsTests(unittest.TestCase):
    """GPS is the site's featured default constellation, so it gets its own guards."""

    def setUp(self):
        self.gps = {
            int(entry["norad"][0]): entry
            for key, entry in PARTITION.items()
            if key.startswith("@us/gps/")
        }

    def test_every_navstar_object_in_the_catalog_is_described(self):
        if not CATALOG:
            self.skipTest("no published catalog on this machine")
        navstar = {n for n, r in CATALOG.items() if r["name"].upper().startswith("NAVSTAR")}
        self.assertTrue(navstar, "the catalog has no NAVSTAR objects; this test is stale")
        self.assertEqual(navstar - set(self.gps), set(), "a GPS satellite is still undescribed")

    def test_each_card_names_its_own_block_svn_and_slot(self):
        """A family paragraph repeated 39 times is what 'no details' feels like."""
        for number, entry in self.gps.items():
            with self.subTest(norad=number):
                text = entry["purpose"]
                self.assertRegex(text, r"(Block IIR|Block IIR-M|Block IIF|GPS III) flight \d+")
                self.assertRegex(text, r"SVN \d+")
                self.assertEqual(entry["mission"], "navigation")
                self.assertEqual(entry["organization"], "U.S. Space Force")

    def test_the_prn_handover_did_not_move_a_block(self):
        """PRN 13 moved from SVN 43 to GPS III SV10 while this was being written."""
        oldest = self.gps[24876]["purpose"]
        self.assertIn("Block IIR flight 2", oldest)
        self.assertIn("SVN 43", oldest)
        self.assertNotIn("GPS III", oldest)
        for number, entry in self.gps.items():
            with self.subTest(norad=number):
                self.assertNotIn("GPS III flight 10", entry["purpose"])

    def test_no_two_gps_cards_claim_the_same_space_vehicle_number(self):
        svns = [re.search(r"SVN (\d+)", entry["purpose"]).group(1) for entry in self.gps.values()]
        self.assertEqual(len(svns), len(set(svns)), "two GPS cards claim one space vehicle")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
