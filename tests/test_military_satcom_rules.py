"""The MILSATCOM rules, checked against the strings the site actually publishes.

WHY THIS FILE IS SHAPED THE WAY IT IS. Four times now this catalogue has shipped
a mission rule that matched nothing, and every one of them was a rule written
against a naming convention the registry does not use: `SES-` against a registry
that writes "SES 1", `EUTE` against a registry that writes "EUTE 172A",
`^GSAT-(?:8|10|15)` against a registry that writes "GSAT 8", and a `DSCS` rule
against a registry that writes "USA 170". Every one of those rules also had tests
over it. The tests passed because they asserted what the author BELIEVED the
names were.

So nothing here is written from belief. Every expectation below is a literal
string lifted out of the published catalog artifact, and every rule is asserted
in both directions: the objects it must take, and the named siblings it must
leave alone. The negative half is not decoration -- it is the half that would
have caught "TERRA" claiming SKYTERRA 1 and "DSP" claiming RIGIDSPHERE 2.

Where no published catalog is present the mirror-backed cases skip loudly, for
the reason `test_catalog_name_matching` gives: a silently-skipped guard is the
same failure again.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.build_release import (
    BASIS_EVIDENCE,
    matching_override,
    validate_overrides,
)

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = json.loads((ROOT / "data" / "satellite_overrides.json").read_text())
MANIFEST = ROOT / "public" / "data" / "manifest.json"


def _published_satellites() -> list[dict]:
    if not MANIFEST.is_file():
        return []
    manifest = json.loads(MANIFEST.read_text())
    reference = manifest.get("catalog")
    if not reference:
        return []
    path = ROOT / "public" / "data" / "artifacts" / Path(str(reference.get("path") or reference)).name
    if not path.is_file():
        return []
    return json.loads(path.read_text())["satellites"]


PUBLISHED = _published_satellites()


def resolved_names(entry_key: str) -> list[str]:
    """Every published spacecraft name the override table routes to this entry.

    Deliberately runs the production matcher over the production names rather
    than re-implementing the match: a test that reimplements the rule tests the
    reimplementation.
    """
    target = OVERRIDES[entry_key]
    names = []
    for satellite in PUBLISHED:
        matched = matching_override(satellite["name"], OVERRIDES, satellite["id"])
        if matched is not None and matched[0] is target:
            names.append(satellite["name"])
    return sorted(names)


def override_for(name: str, catalog_id: int) -> str | None:
    """Which entry key claims this object, or None."""
    matched = matching_override(name, OVERRIDES, catalog_id)
    if matched is None:
        return None
    for key, entry in OVERRIDES.items():
        if entry is matched[0]:
            return key
    return None


@unittest.skipUnless(PUBLISHED, "no published catalog on this machine")
class ChineseMilitaryCommunicationsTests(unittest.TestCase):
    """Shentong-2 flies under a civil ChinaSat name. Sixteen ChinaSats do not."""

    def test_the_four_shentong_2_satellites_are_claimed_by_catalog_number(self):
        self.assertEqual(
            resolved_names("CHINASAT 2 (SHENTONG-2)"),
            ["CHINASAT 2A", "CHINASAT 2C", "CHINASAT 2D", "CHINASAT 2E"],
        )

    def test_no_other_chinasat_is_swept_into_the_military_entry(self):
        # THE NEGATIVE CONTROL. Every one of these is a China Satcom commercial
        # broadcast or broadband spacecraft, and calling any of them a PLA
        # military comsat is precisely the failure that costs this site more
        # than the gap does. Names copied from the published catalog, including
        # the inconsistent hyphenation the registry actually uses.
        siblings = [
            "CHINASAT 9", "CHINASAT 10", "CHINASAT 11", "CHINASAT 12", "CHINASAT 16",
            "CHINASAT 19", "CHINASAT 4A", "CHINASAT 6C", "CHINASAT 6D", "CHINASAT 9B",
            "CHINASAT 10R", "CHINASAT-3A", "CHINASAT 3B", "CHINASAT-6E", "CHINASAT-9C",
            "CHINASAT-26",
        ]
        by_name = {s["name"]: s["id"] for s in PUBLISHED}
        for name in siblings:
            with self.subTest(name=name):
                self.assertIn(name, by_name, f"{name} is not in the published catalog any more")
                self.assertIsNone(override_for(name, by_name[name]))

    def test_the_two_suspected_fenghuo_2_birds_are_deliberately_left_alone(self):
        # ChinaSat 1D and 1E are REPORTED to be Fenghuo-2 tactical military
        # comsats, and the strongest wording any source offers is "might be a
        # Fenghuo class". That is not enough to put a MILSATCOM label on a
        # spacecraft, so the site says nothing. If a better source appears, this
        # test is the place that records why it did not before.
        by_name = {s["name"]: s["id"] for s in PUBLISHED}
        for name in ("CHINASAT 1D", "CHINASAT 1E"):
            with self.subTest(name=name):
                self.assertIsNone(override_for(name, by_name[name]))


@unittest.skipUnless(PUBLISHED, "no published catalog on this machine")
class TongxinJishuShiyanTests(unittest.TestCase):
    def test_every_published_tjs_object_is_claimed(self):
        published_tjs = sorted(s["name"] for s in PUBLISHED if s["name"].upper().startswith("TJS"))
        self.assertGreaterEqual(len(published_tjs), 25)
        self.assertEqual(resolved_names("TJS"), published_tjs)

    def test_the_flights_present_when_the_rule_was_written_are_all_covered(self):
        # Frozen list, so a future registry rename shows up as a failure here
        # rather than as objects quietly falling out of the filter.
        expected = [
            "TJS-1", "TJS-2", "TJS-3", "TJS-4", "TJS-5", "TJS-6", "TJS-7", "TJS-9",
            "TJS-10", "TJS-11", "TJS-12", "TJS-13", "TJS-14", "TJS-15", "TJS-16",
            "TJS-17", "TJS-19", "TJS-20", "TJS-22", "TJS-23", "TJS-24", "TJS-25",
            "TJS-26A", "TJS-27A", "TJS-27B",
        ]
        self.assertEqual(sorted(set(expected) - set(resolved_names("TJS"))), [])

    def test_a_name_that_merely_starts_with_the_letters_is_not_a_tjs(self):
        for imposter in ("TJSAT 1", "TJSTAR", "TJSX-4"):
            with self.subTest(name=imposter):
                self.assertIsNone(override_for(imposter, 999_999))

    def test_tjs_claims_no_mission_only_a_sector(self):
        # China calls them communications-technology experiments; analysts read
        # several as SIGINT or early warning. The site claims the half they
        # agree on. This assertion is what stops a later edit quietly promoting
        # 25 classified Chinese spacecraft into MILSATCOM.
        entry = OVERRIDES["TJS"]
        self.assertEqual(entry["mission"], "other")
        self.assertEqual(entry["sector"], "military")


@unittest.skipUnless(PUBLISHED, "no published catalog on this machine")
class RussianMilitaryCommunicationsTests(unittest.TestCase):
    """Russia catalogues military spacecraft as COSMOS nnnn. The number is the
    only handle there is, so these rules are keyed on catalog number, and the
    negative control names the COSMOS objects in the same orbits that must not
    be caught."""

    def test_blagovest_is_the_four_geostationary_kosmos_numbers_and_no_others(self):
        self.assertEqual(
            resolved_names("COSMOS (BLAGOVEST)"),
            ["COSMOS 2520", "COSMOS 2526", "COSMOS 2533", "COSMOS 2539"],
        )

    def test_garpun_is_one_object(self):
        self.assertEqual(resolved_names("COSMOS (GARPUN)"), ["COSMOS 2513"])

    def test_the_other_classified_kosmos_objects_are_left_unclaimed(self):
        # THE NEGATIVE CONTROL. Kosmos 2510/2518/2541/2546/2552/2563 are the EKS
        # (Tundra) early-warning satellites in the same highly elliptical band,
        # 2589/2590 are assessed as a counterspace pair, and 2596 is unidentified.
        # None of them is a communications satellite, and a rule keyed on the
        # word COSMOS would have taken all nine.
        by_name = {s["name"]: s["id"] for s in PUBLISHED}
        for name in ("COSMOS 2510", "COSMOS 2518", "COSMOS 2541", "COSMOS 2546",
                     "COSMOS 2552", "COSMOS 2563", "COSMOS 2589", "COSMOS 2590",
                     "COSMOS 2596"):
            with self.subTest(name=name):
                self.assertIn(name, by_name)
                self.assertIsNone(override_for(name, by_name[name]))

    def test_meridian_takes_every_published_flight(self):
        published = sorted(s["name"] for s in PUBLISHED if s["name"].upper().startswith("MERIDIAN"))
        self.assertEqual(
            published,
            ["MERIDIAN 10", "MERIDIAN 11", "MERIDIAN 7", "MERIDIAN 8", "MERIDIAN 9"],
        )
        self.assertEqual(resolved_names("MERIDIAN"), published)

    def test_raduga_1m_is_the_single_surviving_flight(self):
        self.assertEqual(resolved_names("RADUGA 1M"), ["RADUGA 1M-3"])

    def test_gonets_is_civil_and_matches_both_spellings_the_registry_uses(self):
        # The exact trap that killed the SES and GSAT rules, in the one place it
        # was going to bite next: the registry writes BOTH "GONETS M 03" (space)
        # and "GONETS-M 23" (hyphen) in the same catalog. Asserted against the
        # published strings, not against either spelling anyone would guess.
        published = sorted(s["name"] for s in PUBLISHED if s["name"].upper().startswith("GONETS"))
        self.assertIn("GONETS M 03", published)
        self.assertIn("GONETS-M 23", published)
        self.assertEqual(resolved_names("GONETS"), published)
        self.assertEqual(OVERRIDES["GONETS"]["sector"], "civil")


@unittest.skipUnless(PUBLISHED, "no published catalog on this machine")
class AlliedMilitaryCommunicationsTests(unittest.TestCase):
    """The five programmes the site already knew, moved off a name prefix, plus
    the three it did not know at all."""

    def test_each_catalog_number_names_the_spacecraft_the_entry_claims(self):
        by_id = {s["id"]: s["name"] for s in PUBLISHED}
        for key in ("SKYNET", "SYRACUSE", "AEHF", "WGS", "MUOS", "COMSATBW",
                    "SPAINSAT", "OPTUS C1"):
            entry = OVERRIDES[key]
            with self.subTest(entry=key):
                self.assertEqual(entry["match"], "norad",
                                 f"{key} must be pinned to catalog numbers, not to a name")
                for catalog_id, intended in zip(entry["norad"], entry["noradNames"]):
                    published = by_id.get(catalog_id)
                    self.assertIsNotNone(published, f"{key}: {catalog_id} is not published")
                    self.assertEqual(published, intended,
                                     f"{key} claims {catalog_id} as {intended!r}, "
                                     f"the catalog publishes {published!r}")

    def test_the_populations_are_the_ones_measured_on_2026_08_20(self):
        self.assertEqual(len(resolved_names("SKYNET")), 4)
        self.assertEqual(len(resolved_names("SYRACUSE")), 3)
        self.assertEqual(len(resolved_names("AEHF")), 6)
        self.assertEqual(len(resolved_names("WGS")), 10)
        self.assertEqual(len(resolved_names("MUOS")), 5)
        self.assertEqual(len(resolved_names("COMSATBW")), 2)
        self.assertEqual(len(resolved_names("SPAINSAT")), 2)

    def test_a_dual_use_spacecraft_is_not_filed_as_military(self):
        # Optus C1 carries a Ku-band commercial payload AND an ADF military one.
        # MILSATCOM is `communications` + `military`; putting this object there
        # would tell a reader the whole spacecraft belongs to Defence.
        self.assertEqual(OVERRIDES["OPTUS C1"]["sector"], "mixed")

    def test_the_other_optus_satellites_are_not_touched(self):
        by_name = {s["name"]: s["id"] for s in PUBLISHED}
        for name in ("OPTUS D1", "OPTUS D3", "OPTUS 10"):
            with self.subTest(name=name):
                self.assertIsNone(override_for(name, by_name[name]))


class AssessedEvidenceClassTests(unittest.TestCase):
    """An assessment must say whose it is, and must not read as documentation."""

    ASSESSED_KEYS = (
        "CHINASAT 2 (SHENTONG-2)", "TJS", "MERIDIAN", "RADUGA 1M",
        "COSMOS (BLAGOVEST)", "COSMOS (GARPUN)",
    )

    def test_the_basis_has_a_sentence_a_reader_can_weigh(self):
        self.assertIn("assessed", BASIS_EVIDENCE)
        self.assertIn("no operator or government has published", BASIS_EVIDENCE["assessed"])

    def test_every_assessed_entry_names_its_analyst_and_cites_a_page(self):
        for key in self.ASSESSED_KEYS:
            entry = OVERRIDES[key]
            with self.subTest(entry=key):
                self.assertEqual(entry["evidence"], "assessed")
                self.assertTrue(entry["assessedBy"].strip())
                self.assertTrue(entry["source"].startswith("http"))

    def test_the_card_itself_says_the_claim_is_assessed(self):
        # Belt and braces, exactly as `contested_caveat` is: the machine-readable
        # basis drives the chip, and the prose says it too, so a release where
        # the interface has not caught up still tells the reader the truth.
        for key in self.ASSESSED_KEYS:
            with self.subTest(entry=key):
                purpose = OVERRIDES[key]["purpose"].lower()
                self.assertTrue(
                    "assessed" in purpose or "analysts" in purpose,
                    f"{key}: the description does not tell the reader it is an assessment",
                )

    def test_an_assessment_with_no_named_analyst_is_refused(self):
        with self.assertRaises(ValueError):
            validate_overrides({
                "X": {"match": "norad", "norad": [1], "evidence": "assessed",
                      "source": "https://example.invalid/x"},
            })

    def test_an_assessment_with_no_source_is_refused(self):
        with self.assertRaises(ValueError):
            validate_overrides({
                "X": {"match": "norad", "norad": [1], "evidence": "assessed",
                      "assessedBy": "somebody"},
            })

    def test_an_unknown_evidence_class_is_refused(self):
        with self.assertRaises(ValueError):
            validate_overrides({"X": {"match": "norad", "norad": [1], "evidence": "rumoured"}})

    def test_the_shipped_table_validates(self):
        validate_overrides(OVERRIDES)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
