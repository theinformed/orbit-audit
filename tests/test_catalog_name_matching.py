"""The regression test `docs/satellite-catalog-classification.md` has required
since it was written, and which nobody wrote.

It is run against the *real* cached registry mirror, not a fixture. That is the
whole point: the four defect classes this codebase has already produced all had
green tests over them, and two of those tests were green because they never
executed the production path. A fixture of ten spacecraft names would have
passed every day that RIGIDSPHERE 2 was on the public site claiming to be a
missile-warning satellite. Sixteen thousand real names would not.

If no mirror is present the mirror-backed cases skip loudly rather than pass
quietly, because a silently-skipped guard is the same failure again.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline import build_release
from pipeline.build_release import (
    OVERRIDE_MATCH_CONFIDENCE,
    OVERRIDE_MATCH_MODES,
    classify,
    classify_detailed,
    contains,
    matching_override,
    name_pattern,
    validate_overrides,
)
from pipeline.catalog_audit import extract_name_rule_fragments, name_tokens

ROOT = Path(__file__).resolve().parents[1]
# The merged table -- base file plus every `satellite_overrides_*.json`
# partition -- so a partition written by one agent inherits every guard in
# this module rather than being tested by nobody.
OVERRIDES = build_release.load_overrides()


def _mirror_names() -> list[str]:
    """Every spacecraft name in whichever offline registry mirror is present."""
    names: set[str] = set()
    for path, key in (
        (ROOT / "runtime" / "spacetrack-mirror" / "satcat-active.json", "SATNAME"),
        (ROOT / "runtime" / "celestrak-mirror" / "satcat-active.json", "OBJECT_NAME"),
    ):
        if not path.is_file():
            continue
        for row in json.loads(path.read_text()):
            value = str(row.get(key) or row.get("OBJECT_NAME") or "").strip()
            if value:
                names.add(value)
    return sorted(names)


MIRROR_NAMES = _mirror_names()


class TokenBoundaryTests(unittest.TestCase):
    """The exact matches that shipped wrong answers to the public site."""

    def test_the_names_that_shipped_wrong_answers_no_longer_match(self):
        # name, fragment that used to capture it, and what it actually is.
        cases = (
            ("SKYTERRA 1", "TERRA", "Ligado L-band mobile-satellite spacecraft"),
            ("RIGIDSPHERE 2 (LCS 4)", "DSP", "1971 radar calibration sphere"),
            ("SWISSCUBE", "ISS", "Swiss student cubesat"),
            ("AISSAT 4", "ISS", "Norwegian AIS ship tracking"),
            ("DB-GLOBE MISSION EARTH-UT", "ISS", "the word MISSION"),
            ("ANGOSAT 2", "GOSAT", "Angolan geostationary comsat"),
            ("NIGCOMSAT 1R", "GCOM", "Nigerian geostationary comsat"),
            ("ASTROCAST-0402", "ASTRO", "Swiss IoT communications constellation"),
            ("DRAGRACER 2 (AUGURY)", "GRACE", "tether deorbit demonstration"),
            ("TERRASAR-X", "TERRA", "German DLR/Airbus X-band radar"),
            ("E3TESTER-1", "TEST", "the word TESTER"),
            ("POLYTECH UNIVERSE-4", "TECH", "the word POLYTECH"),
        )
        for name, fragment, what in cases:
            with self.subTest(name=name):
                self.assertIn(fragment, name.upper(), "the test case itself is stale")
                self.assertFalse(
                    contains(name, (fragment,)),
                    f"{name} ({what}) still matches {fragment!r} inside a word",
                )

    def test_real_programme_names_still_match(self):
        for name, fragment in (
            ("TERRA", "TERRA"),
            ("GOES 16", "GOES"),
            ("SES 1", "SES-"),            # registry writes "SES 1"; rule wrote "SES-"
            ("SES-3", "SES-"),
            ("GPS BIIR-2 (PRN 13)", "GPS "),
            ("COSMOS 2501 (GLONASS)", "GLONASS"),
            ("FORMOSAT7-3/COSMIC2-3", "COSMIC"),   # series number, not another word
            ("EUTE 172A (GE 23)", "EUTE"),
            ("GALAXY 19", "GALAXY"),
            ("SUOMI NPP", "SUOMI NPP"),
        ):
            with self.subTest(name=name):
                self.assertTrue(contains(name, (fragment,)), f"{fragment!r} no longer matches {name}")

    def test_no_rule_fragment_matches_any_real_name_inside_a_word(self):
        """The mirror-wide sweep. This is the test that had to exist."""
        if not MIRROR_NAMES:
            self.skipTest("no registry mirror present; run on bigmem where the mirror lives")
        fragments = extract_name_rule_fragments()
        every = sorted(
            {fragment for group in fragments.values() for fragment in group} | set(OVERRIDES)
        )
        self.assertGreater(len(every), 50, "rule extraction found suspiciously few fragments")
        offenders: list[str] = []
        for name in MIRROR_NAMES:
            upper = name.upper()
            tokens = name_tokens(name)
            for fragment in every:
                core = fragment.upper().strip().strip("-_/ ")
                if not core or core not in upper:
                    continue
                if name_pattern(core).search(upper):
                    continue
                # Substring hit that the production matcher now rejects. That is
                # the correct outcome; assert the production matcher agrees.
                if contains(name, (fragment,)):
                    offenders.append(f"{name!r} still matched {fragment!r} inside a word")
                self.assertNotIn(
                    core, set(tokens), f"{name!r}/{core!r} tokenisation disagrees with the matcher"
                )
        self.assertEqual(offenders, [], "\n".join(offenders[:20]))


class OverrideAttachmentTests(unittest.TestCase):
    def test_shipped_override_table_is_valid(self):
        validate_overrides(OVERRIDES)

    def test_individual_descriptions_cannot_attach_by_pattern(self):
        for key, entry in OVERRIDES.items():
            if entry.get("individual"):
                with self.subTest(override=key):
                    self.assertIn(entry.get("match"), {"norad", "exact"})

    def test_an_individual_prefix_override_is_refused(self):
        with self.assertRaises(ValueError):
            validate_overrides({"TERRA": {"match": "prefix", "individual": True, "purpose": "x"}})

    def test_unknown_match_mode_is_refused(self):
        with self.assertRaises(ValueError):
            validate_overrides({"TERRA": {"match": "fuzzy", "purpose": "x"}})

    def test_terra_description_reaches_terra_and_nothing_else(self):
        self.assertIsNotNone(matching_override("TERRA", OVERRIDES, 25994))
        for name, norad in (("SKYTERRA 1", 37218), ("TERRA SAR X", 31698), ("TERRASAR-X", 31698)):
            with self.subTest(name=name):
                matched = matching_override(name, OVERRIDES, norad)
                organisation = matched[0].get("organization") if matched else None
                self.assertNotEqual(organisation, "NASA", f"{name} still claims NASA")

    def test_family_overrides_still_reach_their_family(self):
        for name, norad, expected in (
            ("STARLINK-37189", 68603, "SpaceX"),
            ("GOES 16", 41866, "NOAA / NASA"),
            ("COSMOS 2501 (GLONASS)", 40315, "Russian Federation"),
            ("NAVSTAR 80 (USA 309)", 46826, "U.S. Space Force"),
        ):
            with self.subTest(name=name):
                matched = matching_override(name, OVERRIDES, norad)
                self.assertIsNotNone(matched, f"{name} lost its override")
                self.assertEqual(matched[0].get("organization"), expected)

    def test_match_strength_orders_confidence(self):
        order = ["low", "medium", "high"]
        by_mode = {mode: OVERRIDE_MATCH_CONFIDENCE[mode] for mode in OVERRIDE_MATCH_MODES}
        self.assertGreaterEqual(order.index(by_mode["norad"]), order.index(by_mode["exact"]))
        self.assertGreaterEqual(order.index(by_mode["exact"]), order.index(by_mode["prefix"]))
        self.assertGreaterEqual(order.index(by_mode["exact"]), order.index(by_mode["token"]))


class OwnerOrganizationTests(unittest.TestCase):
    def test_agency_is_no_longer_guessed_from_the_spacecraft_name(self):
        """The NASA branch was wrong on six of the nine objects it claimed."""
        for name, owner_code in (
            ("TERRA SAR X", "GER"),
            ("ANGOSAT 2", "AGO"),
            ("NIGCOMSAT 1R", "NIG"),
            ("LEMUR 2 HUBBLE-4", "US"),
        ):
            with self.subTest(name=name):
                self.assertNotIn(
                    build_release.owner_organization(name.upper(), owner_code),
                    {"NASA", "JAXA", "NOAA / NASA"},
                )

    def test_registry_owner_is_expanded_rather_than_shown_as_a_code(self):
        for code, expected in (("SAUD", "Saudi Arabia"), ("ISRA", "Israel"), ("NIG", "Nigeria")):
            with self.subTest(code=code):
                self.assertEqual(build_release.owner_organization("ANY", code), expected)


class ClassificationBasisTests(unittest.TestCase):
    def test_basis_separates_a_pattern_guess_from_a_genuine_unknown(self):
        self.assertEqual(classify_detailed("STARLINK-37189", "US")[5], "name-pattern")
        self.assertEqual(classify_detailed("RIGIDSPHERE 2 (LCS 4)", "US")[5], "unclassified")
        self.assertEqual(classify_detailed("PRAETORIAN SDA_601", "US")[5], "exact-name")

    def test_classify_keeps_its_five_field_contract(self):
        self.assertEqual(len(classify("STARLINK-37189", "US")), 5)

    def test_a_pattern_match_no_longer_claims_high_confidence(self):
        self.assertEqual(classify_detailed("GOES 16", "US")[4], "medium")
        self.assertEqual(classify_detailed("PRAETORIAN SDA_601", "US")[4], "high")




class CuratedEntryTests(unittest.TestCase):
    """Every curated claim must name a real spacecraft and cite a real page.

    Written after a hand-typed catalog ID in this very file pointed the Canadian
    space-surveillance satellite SAPPHIRE at KOMPSAT 2. NORAD-keying removes the
    substring failure mode; it introduces a typing one, and the registry is
    sitting right there to check against.
    """

    def test_every_norad_keyed_entry_names_the_spacecraft_it_claims(self):
        if not MIRROR_NAMES:
            self.skipTest("no registry mirror present")
        registry: dict[int, str] = {}
        for path, key in (
            (ROOT / "runtime" / "spacetrack-mirror" / "satcat-active.json", "SATNAME"),
            (ROOT / "runtime" / "celestrak-mirror" / "satcat-active.json", "OBJECT_NAME"),
        ):
            if not path.is_file():
                continue
            for row in json.loads(path.read_text()):
                try:
                    registry.setdefault(int(row["NORAD_CAT_ID"]), str(row.get(key) or ""))
                except (KeyError, TypeError, ValueError):
                    continue
        for name, entry in OVERRIDES.items():
            if entry.get("match") != "norad":
                continue
            # Each ID is stamped with the registry name it was resolved from, so
            # the guard pins the ID to the spacecraft the author meant rather
            # than to the entry's label -- "ISS MODULE" and "MMS" are programme
            # labels, not spacecraft names.
            expected = entry.get("noradNames") or [name.split(" (")[0]] * len(entry["norad"])
            self.assertEqual(len(expected), len(entry["norad"]),
                             f"{name}: noradNames does not line up with norad")
            for norad, intended in zip(entry["norad"], expected):
                with self.subTest(entry=name, norad=norad):
                    actual = registry.get(norad)
                    self.assertIsNotNone(actual, f"{name}: {norad} is not in the registry at all")
                    self.assertTrue(
                        set(name_tokens(intended)) & set(name_tokens(actual)),
                        f"{name} claims catalog ID {norad} as {intended!r}, "
                        f"which the registry calls {actual!r}",
                    )

    def test_every_description_carries_a_source_url(self):
        for name, entry in OVERRIDES.items():
            if entry.get("purpose"):
                with self.subTest(entry=name):
                    # http:// is tolerated: some official agency pages
                    # (cmse.gov.cn, cbers.inpe.br) are not served over TLS, and
                    # a real citation beats a prettier one.
                    self.assertTrue(str(entry.get("source", "")).startswith(("https://", "http://")))

    def test_no_two_entries_claim_the_same_catalog_id(self):
        seen: dict[int, str] = {}
        for name, entry in OVERRIDES.items():
            for norad in entry.get("norad", ()):
                self.assertNotIn(norad, seen, f"{name} and {seen.get(norad)} both claim {norad}")
                seen[norad] = name




class OperatorSectorTests(unittest.TestCase):
    """Commercial operators were 6 of the 8 errors found by hand-verification."""

    def test_commercial_imaging_operators_are_not_civil(self):
        for name, operator in (
            ("SKYSAT C10", "Planet Labs"),
            ("JILIN-01 GAOFEN 3D 28", "Chang Guang Satellite Technology"),
            ("HAWK-5A", "HawkEye 360"),
            ("WORLDVIEW 3", "Maxar"),
            ("GHGSAT-C1", "GHGSat"),
            ("STRIX-1", "Synspective"),
        ):
            with self.subTest(name=name):
                result = build_release.operator_sector(name)
                self.assertIsNotNone(result, f"{name} has no operator rule")
                self.assertEqual(result[0], "commercial")
                self.assertEqual(result[1], operator)

    def test_transferred_weather_spacecraft_are_military(self):
        for name in ("EWS-G2", "EWS-G3"):
            with self.subTest(name=name):
                self.assertEqual(build_release.operator_sector(name)[0], "military")

    def test_an_operator_prefix_cannot_reach_a_longer_word(self):
        # "GLOBAL" is BlackSky; "GLOBALSTAR" is not.
        self.assertIsNotNone(build_release.operator_sector("GLOBAL-4"))
        self.assertIsNone(build_release.operator_sector("GLOBALSTAR M097"))
        self.assertIsNone(build_release.operator_sector("HAWKEYE PATHFINDER"))

    def test_every_operator_family_carries_a_source_url(self):
        for prefix, sector, operator, source in build_release.OPERATOR_SECTORS:
            with self.subTest(prefix=prefix):
                self.assertTrue(source.startswith("https://"), f"{prefix} has no source URL")
                self.assertIn(sector, {"commercial", "military", "civil", "mixed", "academic"})

    def test_the_audit_knows_about_every_operator_rule(self):
        """A claim-bearing rule the audit cannot see is reported as unsupported."""
        from pipeline.catalog_audit import extract_operator_prefixes
        extracted = set(extract_operator_prefixes())
        self.assertEqual(extracted, {prefix for prefix, _, _, _ in build_release.OPERATOR_SECTORS})


class MilitaryAssertionTests(unittest.TestCase):
    """A military claim on this site is higher-consequence than any other field.

    The site is published under the name of a serving U.S. Navy officer.
    RIGIDSPHERE 2 -- a radar calibration sphere -- reached the front page as a
    Defense Support Program missile-warning spacecraft. Every rule that can put
    "military" on a card must therefore be answerable to a public source.
    """

    def _military_rules(self):
        rules = []
        for key, entry in OVERRIDES.items():
            if entry.get("sector") == "military":
                rules.append((key, entry.get("source")))
        for prefix, sector, _operator, source in build_release.OPERATOR_SECTORS:
            if sector == "military":
                rules.append((prefix, source))
        return rules

    def test_every_military_rule_cites_a_source(self):
        rules = self._military_rules()
        self.assertGreater(len(rules), 5, "military rules were not found at all")
        for key, source in rules:
            with self.subTest(rule=key):
                self.assertTrue(
                    str(source or "").startswith(("https://", "http://")),
                    f"military classification {key!r} has no public source",
                )

    def test_a_calibration_sphere_is_not_a_missile_warning_spacecraft(self):
        mission, sector, _fleet, organisation, _confidence = classify("RIGIDSPHERE 2 (LCS 4)", "US")
        self.assertEqual(mission, "other")
        self.assertEqual(sector, "unknown")
        self.assertNotEqual(organisation, "U.S. Space Force")


if __name__ == "__main__":
    unittest.main()


class MergedOverrideTableTests(unittest.TestCase):
    """The override table is now assembled from several files, one per partition
    of the catalog, because four people writing descriptions into one JSON file
    at once makes every entry a merge conflict. Merging introduces two failure
    modes that a single file did not have, and both are pinned here.
    """

    def _files(self):
        directory = ROOT / "data"
        return [directory / "satellite_overrides.json"] + sorted(
            directory.glob("satellite_overrides_*.json")
        )

    def test_the_merge_actually_picks_up_the_partition_files(self):
        """A glob that silently matches nothing would leave every partition
        unpublished while every other test in this file still passed."""
        merged = build_release.load_overrides()
        for path in self._files():
            entries = json.loads(path.read_text())
            if not entries:
                continue
            with self.subTest(file=path.name):
                self.assertTrue(
                    set(entries) & set(merged),
                    f"{path.name} contributed nothing to the merged table",
                )

    def test_no_override_key_is_defined_in_two_files(self):
        """The base file wins a collision at build time rather than failing the
        publish, so the duplicate has to be caught here or it is caught nowhere:
        the losing entry would simply never appear, silently."""
        seen: dict[str, str] = {}
        for path in self._files():
            for key in json.loads(path.read_text()):
                with self.subTest(key=key):
                    self.assertNotIn(
                        key, seen,
                        f"{key!r} is defined in both {seen.get(key)} and {path.name}; "
                        "the base file wins and the other entry is dropped",
                    )
                    seen[key] = path.name

    def test_no_two_entries_across_files_claim_the_same_catalog_id(self):
        merged = build_release.load_overrides()
        seen: dict[int, str] = {}
        for name, entry in merged.items():
            for norad in entry.get("norad", ()):
                with self.subTest(norad=norad):
                    self.assertNotIn(
                        norad, seen, f"{name} and {seen.get(norad)} both claim {norad}"
                    )
                seen[norad] = name


class RuleReachesARealNameTests(unittest.TestCase):
    """THE RULE THAT MATCHES NOTHING.

    Three rules have shipped on this site that matched zero spacecraft, and none
    of them looked wrong: ``SES-``, ``EUTE`` and ``^GSAT-(?:8|10|15)``. They
    failed because this catalog is built from space-track, which writes names
    SPACE-SEPARATED -- the real published strings are ``SES 2``, ``EUTE 36D`` and
    ``GSAT 8`` -- while the author was reading CelesTrak, which hyphenates. A
    rule like that is invisible: nothing errors, the description simply never
    appears, and the card goes on saying that no public source names the payload.

    Run against the real registry mirror, not a fixture, for the reason stated at
    the top of this module.
    """

    #: Rules that reach nothing and were already in the table before this guard
    #: existed. Named individually, with what is actually wrong, so that the
    #: exemption is a to-do list rather than a hole:
    #:
    #: GPS  -- no name in the registry contains the string "GPS" at all. The real
    #:         spacecraft are "NAVSTAR 80 (USA 309)", which the NAVSTAR entry
    #:         reaches; this entry has never fired, and its description -- the
    #:         only one of the two that HAS a description -- has never been shown.
    #: DSP  -- the registry writes "USA 149 (DSP 20)", so the programme name is
    #:         not at the start and a prefix rule cannot reach it. It became dead
    #:         when prefix anchoring was introduced to stop "DSP" claiming
    #:         RIGIDSPHERE 2, which contains those three letters inside a word.
    #:         match="token" would reach the real ones without reaching that.
    #:
    #: Both are United States entries and belong to that partition to fix.
    RULES_KNOWN_DEAD = {"GPS", "DSP"}

    def test_every_override_reaches_at_least_one_real_spacecraft(self):
        if not MIRROR_NAMES:
            self.skipTest("no registry mirror present")
        merged = build_release.load_overrides()
        registry_ids = set()
        for path, _ in (
            (ROOT / "runtime" / "spacetrack-mirror" / "satcat-active.json", "SATNAME"),
            (ROOT / "runtime" / "celestrak-mirror" / "satcat-active.json", "OBJECT_NAME"),
        ):
            if path.is_file():
                for row in json.loads(path.read_text()):
                    try:
                        registry_ids.add(int(row["NORAD_CAT_ID"]))
                    except (KeyError, TypeError, ValueError):
                        continue
        for key, entry in merged.items():
            if key in self.RULES_KNOWN_DEAD:
                continue
            if entry.get("match") == "norad":
                # A catalog-number rule cannot mis-match; it can still name an ID
                # that is not in the registry, which is what this checks.
                with self.subTest(entry=key):
                    self.assertTrue(
                        set(entry.get("norad", ())) & registry_ids,
                        f"{key}: none of its catalog IDs are in the registry mirror",
                    )
                continue
            # Each rule is asked on its own. Asking through the merged table would
            # credit only whichever entry WINS a name, so a perfectly good family
            # rule would look dead the moment a per-spacecraft entry outranked it
            # on its only member.
            alone = {key: entry}
            with self.subTest(entry=key):
                self.assertTrue(
                    any(matching_override(name, alone, None) for name in MIRROR_NAMES),
                    f"{key}: matches no name in the {len(MIRROR_NAMES)}-name registry "
                    "mirror. Check the exact published string -- space-track writes "
                    "'GSAT 8', not 'GSAT-8'.",
                )

    def test_the_known_dead_rules_are_still_dead(self):
        """A negative control on the exemption above: if one of these starts
        matching, the exemption is stale and must come off, not stay as cover."""
        if not MIRROR_NAMES:
            self.skipTest("no registry mirror present")
        merged = build_release.load_overrides()
        for key in self.RULES_KNOWN_DEAD:
            if key not in merged:
                continue
            alone = {key: merged[key]}
            with self.subTest(entry=key):
                self.assertFalse(
                    any(matching_override(name, alone, None) for name in MIRROR_NAMES),
                    f"{key} now matches a real spacecraft; remove it from "
                    "RULES_KNOWN_DEAD so the guard covers it again",
                )

    def test_the_space_separated_names_that_defeated_earlier_rules_now_match(self):
        """The three recorded failures, stated as the strings that must match."""
        merged = build_release.load_overrides()
        for name, expect in (
            ("GSAT 8", "ISRO"),
            ("GSAT 7", "ISRO"),
            ("SES 2", "SES"),
            ("SES MPOWER-A F2", "SES"),
            ("EUTE 36D", "Eutelsat"),
            ("EUTELSAT 10B", "Eutelsat"),
            ("HOTBIRD 13F", "Eutelsat"),
        ):
            with self.subTest(name=name):
                matched = matching_override(name, merged, None)
                self.assertIsNotNone(matched, f"{name} is matched by no override")
                self.assertIn(
                    expect, matched[0].get("organization", ""),
                    f"{name} matched an override for {matched[0].get('organization')!r}",
                )

    def test_those_rules_do_not_sweep_up_their_siblings(self):
        """The other half of the same fix. A rule broad enough to catch the real
        name must still not catch a spacecraft that merely contains it -- which
        is how TERRA claimed SKYTERRA 1."""
        merged = build_release.load_overrides()
        for name, must_not_be in (
            ("BUGSAT 1", "GSAT"),
            ("BRITE-A TUGSAT-1", "GSAT"),
            ("GHGSAT-C1", "GSAT"),
            ("SDGSAT 1", "GSAT"),
            ("ASTRANIS UTILITYSAT", "ASTRA"),
            ("IRNSS 1B", "NSS"),
            ("HYDROGNSS-1", "NSS"),
            ("ARABSAT 5A", "ABS"),
            ("AZERSPACE 2/INTELSAT 38", "INTELSAT"),
        ):
            with self.subTest(name=name):
                matched = matching_override(name, merged, None)
                if matched is None:
                    continue
                claimed = next(k for k, v in merged.items() if v is matched[0])
                self.assertNotEqual(
                    claimed, must_not_be,
                    f"the {must_not_be!r} rule reached {name}, which is a different "
                    "spacecraft entirely",
                )
