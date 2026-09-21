"""Guards for the Russia / CIS partition of the override table.

WHY THIS FILE EXISTS. This partition is 144 hand-written catalog-number claims,
113 of them about spacecraft whose only public name is a Kosmos number. Kosmos
is a designation, not a programme: 145 objects in this catalog carry one, and
they are navigation satellites, ELINT satellites, early-warning satellites,
radar calibration spheres and two passive geodetic balls from 1989. A single
loose rule -- ``{"COSMOS": {"match": "prefix", "mission": "communications"}}``
-- would therefore be the largest single misattribution this pipeline has ever
been capable of, and it would look completely reasonable in review.

So every claim in this partition attaches by catalog number, and this module
asserts it in three ways: no entry may attach by name, each name-matched entry
must reach EXACTLY the spacecraft it was written for, and the objects most
likely to be swept up by a loosened rule are named individually and asserted
NOT to be claimed.

NEGATIVE CONTROL. A guard nobody has watched fail is not a guard. This file was
run against three deliberately broken copies of the partition, in a throwaway
tree so the live one was never sabotaged:

1. every Kosmos entry switched from `match: norad` to `match: prefix`
   -> 30 failures, `test_no_kosmos_claim_attaches_by_name` on all 28 entries.
2. one broad ``{"COSMOS": {"match": "prefix", ...}}`` family rule added -- the
   mistake an author would actually make
   -> `test_glonass_is_not_claimed_by_this_partition` failed on all 28 GLONASS
   spacecraft that carry a Kosmos number.
3. COSMOS 2504 folded into the Strela-3M/Rodnik family, which it resembles in
   inclination and launch but not in behaviour
   -> `test_the_objects_a_loose_rule_would_swallow` failed, and nothing else
   did, which is what a targeted guard is supposed to do.
"""

from __future__ import annotations

import glob
import json
import os
import unittest
from pathlib import Path

from pipeline import build_release
from pipeline.build_release import matching_override, validate_overrides

ROOT = Path(__file__).resolve().parents[1]
PARTITION_PATH = ROOT / "data" / "satellite_overrides_ru.json"
PARTITION = json.loads(PARTITION_PATH.read_text(encoding="utf-8"))
MERGED = build_release.load_overrides()


def _published_catalog() -> list[dict]:
    """The most recent published catalog, or [] when none has been built."""
    artifacts = glob.glob(str(ROOT / "public" / "data" / "artifacts" / "catalog-*.json"))
    if not artifacts:
        return []
    newest = max(artifacts, key=os.path.getmtime)
    return json.loads(Path(newest).read_text(encoding="utf-8")).get("satellites", [])


CATALOG = _published_catalog()


def _entry_key_for(name: str, catalog_id: int) -> str | None:
    """Which merged-table entry, by key, claims this spacecraft."""
    matched = matching_override(name, MERGED, catalog_id)
    if matched is None:
        return None
    for key, entry in MERGED.items():
        if entry is matched[0]:
            return key
    return None


class AttachmentTests(unittest.TestCase):
    """The rule that keeps 145 unlike spacecraft from becoming one claim."""

    def test_no_kosmos_claim_attaches_by_name(self):
        for key, entry in PARTITION.items():
            if not key.startswith("COSMOS"):
                continue
            with self.subTest(entry=key):
                self.assertEqual(
                    entry.get("match"), "norad",
                    f"{key} attaches by {entry.get('match')!r}. Every Kosmos number in this "
                    "catalog is a different programme; only a catalog ID may claim one.",
                )

    def test_the_partition_is_a_valid_override_table(self):
        validate_overrides(PARTITION)

    def test_every_claim_carries_a_source_url(self):
        for key, entry in PARTITION.items():
            with self.subTest(entry=key):
                self.assertTrue(str(entry.get("source", "")).startswith(("https://", "http://")))
                self.assertTrue(entry.get("purpose"), f"{key} claims nothing and should not exist")

    def test_an_assessment_never_promotes_itself(self):
        for key, entry in PARTITION.items():
            if entry.get("evidence") != "assessed":
                continue
            with self.subTest(entry=key):
                self.assertTrue(entry.get("assessedBy", "").strip(),
                                f"{key} is assessed but names no assessor")
                self.assertIn(entry.get("assessedConfidence", "medium"), {"medium", "low"})

    def test_only_a_single_spacecraft_entry_calls_itself_individual(self):
        for key, entry in PARTITION.items():
            if entry.get("individual"):
                with self.subTest(entry=key):
                    self.assertEqual(len(entry["norad"]), 1,
                                     f"{key} is marked individual but names {len(entry['norad'])} spacecraft")


class ReachTests(unittest.TestCase):
    """What each name-matched rule may touch, stated exhaustively.

    Written as equality rather than membership on purpose. `assertIn` would pass
    for a rule that had quietly grown to swallow its neighbours, which is the
    failure mode this file exists for.
    """

    EXPECTED_REACH = {
        "RASSVET-3": {f"RASSVET-3 {n}" for n in list(range(1, 4)) + list(range(5, 33))},
        "EXPRESS": {
            "EXPRESS 103", "EXPRESS 80", "EXPRESS AM-44", "EXPRESS AM-5", "EXPRESS AM-6",
            "EXPRESS AM-7", "EXPRESS AM-8", "EXPRESS AMU-3", "EXPRESS AMU-7", "EXPRESS AMU1",
            "EXPRESS AT1", "EXPRESS AT2",
        },
        "YAMAL": {"YAMAL 202", "YAMAL 300K", "YAMAL 401", "YAMAL 402", "YAMAL 601"},
        "KANOPUS-V": {"KANOPUS-V 3", "KANOPUS-V 4", "KANOPUS-V 5", "KANOPUS-V 6"},
        "RESURS P": {"RESURS P4", "RESURS P5"},
        "IONOSFERA-M": {"IONOSFERA-M 01", "IONOSFERA-M 02", "IONOSFERA-M 03", "IONOSFERA-M 04"},
        "KONDOR FKA": {"KONDOR FKA 1", "KONDOR FKA 2"},
        "OBZOR-R": {"OBZOR-R 01"},
        "KAZSAT": {"KAZSAT 2", "KAZSAT 3"},
        "KAZEOSAT": {"KAZEOSAT 1", "KAZEOSAT 2"},
        "PROGRESS MS": {"PROGRESS MS-33", "PROGRESS MS-34"},
        "SOYUZ MS": {"SOYUZ MS-29"},
        "PERSEUS M": {"PERSEUS M1", "PERSEUS M2"},
        "POLYTECH UNIVERSE": {"POLYTECH UNIVERSE-4", "POLYTECH UNIVERSE-5"},
    }

    def test_every_name_matched_rule_is_covered_by_this_table(self):
        named = {k for k, e in PARTITION.items() if e.get("match") != "norad"}
        self.assertEqual(named, set(self.EXPECTED_REACH),
                         "a name-matched rule was added or removed without stating its reach")

    def test_each_rule_reaches_exactly_the_spacecraft_it_was_written_for(self):
        if not CATALOG:
            self.skipTest("no published catalog to match against")
        actual: dict[str, set[str]] = {key: set() for key in self.EXPECTED_REACH}
        for satellite in CATALOG:
            key = _entry_key_for(satellite["name"], satellite["id"])
            if key in actual:
                actual[key].add(satellite["name"])
        for key, expected in self.EXPECTED_REACH.items():
            with self.subTest(rule=key):
                self.assertEqual(actual[key], expected)

    def test_the_family_rules_do_not_reach_their_own_exceptions(self):
        """Three spacecraft sit inside a family rule's blast radius on purpose."""
        if not CATALOG:
            self.skipTest("no published catalog to match against")
        for name, catalog_id, wrong_rule, right_rule in (
            # An infrared variant that needs its own paragraph, inside KANOPUS-V.
            ("KANOPUS-V-IK", 42825, "KANOPUS-V", "KANOPUS-V-IK"),
            # A different spacecraft generation, inside RESURS P.
            ("RESURS DK-1", 29228, "RESURS P", "RESURS DK-1"),
            # A launch failure that must not read as a working RSCC satellite.
            ("EXPRESS MD2", 38745, "EXPRESS", "EXPRESS MD2 (STRANDED)"),
        ):
            with self.subTest(name=name):
                self.assertEqual(_entry_key_for(name, catalog_id), right_rule,
                                 f"{name} should be claimed by {right_rule}, not {wrong_rule}")


class NegativeClaimTests(unittest.TestCase):
    """The objects a loosened Kosmos rule would swallow, named one by one."""

    def test_glonass_is_not_claimed_by_this_partition(self):
        """The 28 spacecraft whose name carries a Kosmos number AND GLONASS.

        They belong to the base table's GLONASS rule. If any entry in this file
        ever reaches one, a positioning satellite has been relabelled as a spy
        satellite -- on a site read by people who use GLONASS.
        """
        if not CATALOG:
            self.skipTest("no published catalog to match against")
        glonass = [s for s in CATALOG if "GLONASS" in s["name"].upper()]
        self.assertGreater(len(glonass), 15, "the GLONASS cohort has vanished; this test is not testing")
        for satellite in glonass:
            with self.subTest(name=satellite["name"]):
                self.assertNotIn(_entry_key_for(satellite["name"], satellite["id"]), PARTITION)

    def test_the_objects_a_loose_rule_would_swallow(self):
        """Each of these shares a Kosmos number, and often an orbit, with a
        programme it does not belong to."""
        if not CATALOG:
            self.skipTest("no published catalog to match against")
        for catalog_id, name, must_not_be in (
            # 579 x 1482 km at 82.5 deg -- the Strela/Rodnik inclination, but a
            # manoeuvring object that left the shell its launch companions kept.
            (40555, "COSMOS 2504", "COSMOS (STRELA-3M RODNIK-S)"),
            # Catalogued off the same launches as Lotos-S1 No. 807 and No. 808,
            # in the same plane, and identified by nobody.
            (54383, "COSMOS 2566", "COSMOS (LOTOS-S1 LIANA)"),
            (58172, "COSMOS 2571", "COSMOS (LOTOS-S1 LIANA)"),
            # Two inert calibration spheres in a sun-synchronous orbit close to
            # the Bars-M imaging shell.
            (39490, "COSMOS 2493 (SKRL 756)", "COSMOS (BARS-M)"),
            (39491, "COSMOS 2494 (SKRL 756)", "COSMOS (BARS-M)"),
            # A 1989 passive geodetic sphere sharing the GLONASS orbit.
            (19751, "COSMOS 1989 (ETALON 1)", "COSMOS (STRELA-3)"),
            # An amateur-radio satellite in the middle of a Strela cluster.
            (32953, "YUBELEINY", "COSMOS (STRELA-3)"),
        ):
            with self.subTest(name=name):
                self.assertNotEqual(_entry_key_for(name, catalog_id), must_not_be)

    def test_the_slovenian_trisat_is_not_this_trisat(self):
        """TRISAT here is AO OKB-5's picosatellite, not the University of
        Maribor's nanosatellite of the same name. The entry attaches by catalog
        number so that the collision cannot bite even if both ever fly here."""
        entry = PARTITION["TRISAT (OKB-5)"]
        self.assertEqual(entry["match"], "norad")
        self.assertEqual(sorted(entry["norad"]), [67298, 67482])


class CoverageTests(unittest.TestCase):
    """The owner's actual complaint: 'we have a TON of uncategorized satellites'."""

    SENTINELS = (
        "No public source names this spacecraft's payload",
        "The public catalog does not identify",
        "has not been independently verified",
    )

    def test_no_russian_or_cis_object_is_left_without_a_description(self):
        if not CATALOG:
            self.skipTest("no published catalog to match against")
        partition = [s for s in CATALOG if s.get("ownerCode") in {"CIS", "UKR", "KAZ"}]
        self.assertGreater(len(partition), 250, "the CIS cohort has shrunk; this test is not testing")
        residue = []
        for satellite in partition:
            purpose = satellite.get("purpose") or ""
            if not any(sentinel in purpose for sentinel in self.SENTINELS):
                continue
            matched = matching_override(satellite["name"], MERGED, satellite["id"])
            if matched is None or not matched[0].get("purpose"):
                residue.append(f"{satellite['id']} {satellite['name']}")
        self.assertEqual(residue, [], f"{len(residue)} Russian/CIS objects still say nothing")


if __name__ == "__main__":
    unittest.main()
