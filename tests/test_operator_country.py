"""THE COUNTRY THAT IS THE BUILDER'S, NOT THE OPERATOR'S.

On 2026-08-20 the live site said SARI-1 and SARI-2 -- Saudi university payloads
-- were Brazilian, ANISCSAT-1 (Azerbaijan) was Brazilian, SPOQC (Heriot-Watt)
was Dutch, GARAI-B (SATLANTIS, Spain) was Swedish, LEONAV-1 (UAE) was French and
CLOUDCT-PRECURSOR (Technion) was German. Every one of those wrong countries is
the country of the company that BUILT the spacecraft: IdeiaSpace, ISISPACE, OHB
Sweden, U-Space, ZfT. The value came from space-track's SATCAT ``COUNTRY``
column, which is the state the object is attributed to in the registry and which
for a rideshare smallsat is routinely whoever filed the paperwork.

The country itself is a citable registry fact and is NOT overwritten. What was
wrong was that the site had nowhere else to put the operator's country, so it
showed the registering state in a row labelled "Owner / operator" and listed the
object under that country in the owner filter.

These guards are about the CLASS, not those eight objects:

* nothing may present a registering state AS the operator when an
  operator-focused catalogue puts the operator somewhere else;
* nothing may read an operator's country off a catalog number the two
  catalogues do not agree about -- that is the same error from the other side,
  and it is how another spacecraft's operator lands on this one's card;
* the cross-check must still REACH the catalog -- a lookup that silently stops
  matching anything is this project's most-repeated failure, and it looks
  exactly like a clean release;
* the import must not carry GCAT's own duplicate-catalog-number rows through.

Run against the real mirror and the real published artifact. A fixture cannot
fail the way any of these fail.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline import build_release

ROOT = Path(build_release.__file__).resolve().parent.parent


def gcat_fixture(rows: list[tuple[str, str, str]] | list[tuple[str, str, str, str]]) -> str:
    """A miniature satcat.tsv. Rows are (JCAT, Satcat, Name[, PLName])."""
    header = "#JCAT\tSatcat\tName\tPLName\tState\n"
    body = ""
    for row in rows:
        jcat, satcat, name = row[0], row[1], row[2]
        payload = row[3] if len(row) > 3 else ""
        body += f"{jcat}\t{satcat}\t{name}\t{payload}\tUS\n"
    return header + body


class DuplicateCatalogNumberTests(unittest.TestCase):
    """GCAT has three rows today whose ``Satcat`` number belongs to another row.

    ``S68468`` (DB-BECON-2-VU) claims 68488, which is Vindler 2.0.1. ``S69898``
    (GRUS-3E) claims 66898, which is Starlink 36065. ``S69903`` (Balkan-3) claims
    66903, Starlink 36077. A bulk import that took the last row it saw would put
    a Bulgarian operator on a Starlink and never say so.
    """

    def load(self, text: str) -> dict[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "satcat.tsv").write_text(text)
            original = build_release.GCAT_MIRROR
            build_release.GCAT_MIRROR = root
            try:
                return {
                    catalog_id: entry["state"]
                    for catalog_id, entry in build_release.gcat_operator_records().items()
                }
            finally:
                build_release.GCAT_MIRROR = original

    def test_the_row_whose_own_identifier_agrees_keeps_the_number(self):
        states = self.load(gcat_fixture([
            ("S68488", "68488", "Vindler 2.0.1"),
            ("S68468", "68488", "DB-BECON-2-VU"),
        ]))
        self.assertEqual(states.get(68488), "United States")
        self.assertNotIn(68468, states, "the mistyped row must not claim its own number either")

    def test_a_number_no_row_can_substantiate_is_dropped_entirely(self):
        states = self.load(gcat_fixture([
            ("S70001", "68488", "one typo"),
            ("S70002", "68488", "another typo"),
        ]))
        self.assertNotIn(68488, states)

    def test_an_undisputed_row_is_kept(self):
        states = self.load(gcat_fixture([("S12345", "12345", "ordinary")]))
        self.assertEqual(states.get(12345), "United States")

    def test_a_state_code_with_no_label_publishes_nothing_rather_than_the_code(self):
        text = "#JCAT\tSatcat\tName\tPLName\tState\nS12345\t12345\tordinary\t\tZZZ\n"
        self.assertEqual(self.load(text), {})

    def test_the_live_mirror_still_carries_all_three_known_collisions(self):
        """If GCAT fixes them this test says so instead of quietly passing."""
        rows = build_release._read_gcat_table("satcat.tsv")
        if rows is None:
            self.skipTest("no GCAT mirror on this machine")
        claimed: dict[str, int] = {}
        for row in rows:
            number = row.get("Satcat", "").strip()
            if number.isdigit():
                claimed[number] = claimed.get(number, 0) + 1
        collisions = sorted(number for number, count in claimed.items() if count > 1)
        self.assertTrue(
            collisions,
            "no duplicate catalog numbers in the GCAT mirror at all -- either upstream "
            "fixed them, or the table stopped being read; check which before deleting this",
        )


class IdentityAgreementTests(unittest.TestCase):
    """THE SECOND CLASS: the two catalogues disagreeing about WHICH spacecraft.

    A NORAD number is a shared key, and a shared key is not a shared opinion.
    GCAT records 55045 as NuSat-34, a 41.5 kg Satellogic imager operated from
    Montevideo; space-track records it as CONTINUUM-1, Australian, and CelesTrak
    -- asked directly on 2026-08-20 -- agrees with space-track. 22826 is ITAMSAT
    to the registry and Healthsat 2 to GCAT. Both catalogues accept the same
    COSPAR piece in both cases, so the piece cannot tell them apart.

    Reading an operator's country off such a row would put ANOTHER spacecraft's
    operator on the card. That is the defect this whole cross-check exists to
    repair, arrived at from the other side, and it is the specific way that
    importing a second catalogue in bulk goes wrong.
    """

    def entry(self, name: str, payload: str = "") -> dict[str, object]:
        return {
            "state": "Uruguay",
            "names": build_release.catalog_name_forms(name) | build_release.catalog_name_forms(payload),
        }

    def test_a_row_naming_a_different_spacecraft_publishes_nothing(self):
        self.assertIsNone(
            build_release.published_operator_state(
                "CONTINUUM-1", "AUS", "Australia", self.entry("Amelia Earhart", "NuSat-34")
            )
        )

    def test_a_payload_name_is_enough_to_recognise_the_same_spacecraft(self):
        """GCAT calls 68419 ARQSAT-1; only its payload name says FEMTO-1.

        Dropping the payload name would silently lose a correct correction, and
        losing one quietly is indistinguishable from never having had it.
        """
        self.assertEqual(
            build_release.published_operator_state(
                "FEMTO-1", "BGR", "Bulgaria", self.entry("ARQSAT-1", "Femto-1")
            ),
            "Uruguay",
        )

    def test_a_parenthesised_alias_on_our_side_counts_as_our_name(self):
        self.assertEqual(
            build_release.published_operator_state(
                "OSCAR 11 (UOSAT 2)", "BGR", "Bulgaria", self.entry("UoSAT-OSCAR-11")
            ),
            "Uruguay",
        )

    def test_punctuation_and_case_are_not_a_disagreement(self):
        for ours, theirs in (("SARI-1", "Sari 1"), ("GARAI-B", "GARAI B"), ("ANISCSAT-1", "ANISCSAT")):
            with self.subTest(ours=ours):
                self.assertEqual(
                    build_release.published_operator_state(ours, "BGR", "Bulgaria", self.entry(theirs)),
                    "Uruguay",
                )

    def test_no_row_at_all_publishes_nothing(self):
        self.assertIsNone(build_release.published_operator_state("ANYTHING", "US", "United States", None))

    def test_the_gate_is_not_vacuous_against_the_real_mirror(self):
        """A guard that no live row can trip is a guard that has stopped working.

        Modelled on `RuleReachesARealNameTests`, which caught two shipped rules
        matching zero real registry names. This asserts the opposite direction of
        the same property: on the REAL mirror and the REAL published catalog
        there must still be objects the identity gate refuses, or the gate has
        quietly become a no-op and the next mis-joined row will publish.
        """
        catalog = published_catalog(self)
        records = build_release.gcat_operator_records()
        if not records:
            self.skipTest("no GCAT mirror on this machine")
        refused = [
            record["name"]
            for record in catalog["satellites"]
            if record["id"] in records
            and not build_release.gcat_identity_agrees(record["name"], records[record["id"]])
            and not build_release.operator_state_agrees(
                record.get("ownerCode", ""), record["ownerLabel"], records[record["id"]]["state"]
            )
        ]
        self.assertTrue(
            refused,
            "the identity gate refuses nothing in the whole published catalog, which has "
            "never been true; either it stopped being applied or the names stopped being read",
        )


def published_catalog(case: unittest.TestCase) -> dict:
    """The real published artifact, or a skip. Never a fixture.

    Every property below has already been violated by a release that a fixture
    would have called green.
    """
    data_root = ROOT / "public" / "data"
    manifest = data_root / "manifest.json"
    if not manifest.is_file():
        case.skipTest("no published release on this machine")
    record = json.loads(manifest.read_text()).get("catalog") or {}
    path = data_root / str(record.get("path", ""))
    if not path.is_file():
        case.skipTest("published manifest names a catalog artifact that is not on disk")
    return json.loads(path.read_text())


class StateLabelTableTests(unittest.TestCase):
    """A label for a code the source never emits is a rule that cannot fire.

    Three name rules have shipped on this site that matched zero spacecraft, and
    the failure mode is always the same: nothing errors, the value simply never
    appears. Same guard, applied to the state code book.
    """

    def test_every_state_label_is_for_a_code_gcat_actually_uses(self):
        rows = build_release._read_gcat_table("satcat.tsv")
        if rows is None:
            self.skipTest("no GCAT mirror on this machine")
        emitted = {row.get("State", "").strip() for row in rows}
        dead = sorted(code for code in build_release.GCAT_STATE_LABELS if code not in emitted)
        self.assertEqual(dead, [], "state labels for codes GCAT never writes")

    def test_no_label_is_a_bare_code_dressed_up_as_a_country(self):
        """A field labelled as a country must not print an abbreviation.

        This is the mistake OWNER_LABELS was written to stop: the card said
        "SAUD" in a row headed OWNER / OPERATOR, which reads as a name the site
        knows rather than a code it failed to expand.
        """
        offenders = [
            code for code, label in build_release.GCAT_STATE_LABELS.items()
            if label == code
        ]
        self.assertEqual(offenders, [], "labels that are the raw code again")


class RegistryCodeDecisionTests(unittest.TestCase):
    """Every registry country code must have been decided about, one way.

    The two tables answer different questions -- "which GCAT states mean the
    same thing as this registry code" and "this registry code is an
    organisation, so no state can mean the same thing as it" -- and a code in
    neither would fall through to the empty set and start publishing a second
    country row for a country the site is already showing. Falling through to a
    default is how these tables rot.
    """

    def setUp(self):
        self.satellites = published_catalog(self)["satellites"]

    def test_every_registry_code_is_decided(self):
        decided = set(build_release.REGISTRY_COUNTRY_EQUIVALENTS) | build_release.REGISTRY_CODES_NOT_A_COUNTRY
        undecided = sorted({
            record["ownerCode"] for record in self.satellites
            if record.get("ownerCode") and record["ownerCode"] not in decided
        })
        self.assertEqual(undecided, [], "registry codes in neither table")

    def test_no_code_is_in_both_tables(self):
        both = sorted(set(build_release.REGISTRY_COUNTRY_EQUIVALENTS) & build_release.REGISTRY_CODES_NOT_A_COUNTRY)
        self.assertEqual(both, [], "a code cannot both name a country and not name one")

    def test_every_equivalence_names_a_country_the_state_table_can_produce(self):
        """An equivalent country that GCAT can never emit silences nothing.

        Same failure as a name rule that matches no spacecraft: the entry looks
        like a decision, and it has no effect at all.
        """
        producible = set(build_release.GCAT_STATE_LABELS.values())
        dead = sorted(
            f"{code}:{label}"
            for code, labels in build_release.REGISTRY_COUNTRY_EQUIVALENTS.items()
            for label in labels
            if label not in producible
        )
        self.assertEqual(dead, [], "equivalences naming a country GCAT never writes")


class ShippedOperatorCountryTests(unittest.TestCase):
    """Properties of the release itself. Every one has already been violated live."""

    def setUp(self):
        self.catalog = published_catalog(self)
        self.satellites = self.catalog["satellites"]
        self.records = build_release.gcat_operator_records()

    def expected(self, record) -> str | None:
        """The pipeline's own rule, CALLED rather than copied.

        A test that restates the rule it is checking passes the moment both
        copies drift the same way, which is how this project has shipped green
        tests over dead rules before.
        """
        return build_release.published_operator_state(
            record["name"],
            record.get("ownerCode", ""),
            record["ownerLabel"],
            self.records.get(record["id"]),
        )

    def test_no_card_presents_a_registering_state_as_its_operator(self):
        """THE CLASS. Not the eight objects -- the shape they all had.

        ``organizationSource: "registry"`` means the site knows no operator and
        is showing the registry's country instead. That is honest only while the
        registry's country IS the operator's. Where an operator-focused
        catalogue puts the operator in a different country, showing the
        registering state under an operator's label is a claim about who flies
        the spacecraft that no source supports.
        """
        if not self.records:
            self.skipTest("no GCAT mirror on this machine")
        offenders = [
            (record["id"], record["name"], record["organization"], self.expected(record))
            for record in self.satellites
            if record.get("organizationSource") == "registry" and self.expected(record)
        ]
        self.assertEqual(
            offenders[:8], [],
            f"{len(offenders)} card(s) show a registering state where the operator is elsewhere",
        )

    def test_no_operator_country_comes_from_a_row_naming_another_spacecraft(self):
        """THE SECOND CLASS, against the shipped artifact rather than a fixture.

        Every published operator country must come from a GCAT row the registry
        agrees is the same spacecraft. Recomputed from the mirror, so a build
        that bypassed the gate cannot hide behind its own output.
        """
        if not self.records:
            self.skipTest("no GCAT mirror on this machine")
        offenders = [
            (record["id"], record["name"], record["operatorState"])
            for record in self.satellites
            if record.get("operatorState")
            and not build_release.gcat_identity_agrees(record["name"], self.records.get(record["id"]))
        ]
        self.assertEqual(
            offenders[:8], [],
            f"{len(offenders)} card(s) carry an operator country read off another spacecraft's row",
        )

    def test_the_cross_check_still_reaches_the_published_catalog(self):
        """A lookup that matches nothing publishes a clean, wrong release.

        Recomputed from the mirror rather than read back out of the artifact:
        every object the mirror says has an operator in a different country must
        carry that country in the release. If the join breaks -- a renamed
        column, an emptied mirror, a changed key -- this goes red instead of the
        site quietly reverting to the registry's answer everywhere.
        """
        if not self.records:
            self.skipTest("no GCAT mirror on this machine")
        expected = {
            record["id"]: self.expected(record)
            for record in self.satellites
            if self.expected(record)
        }
        self.assertTrue(
            expected,
            "the mirror and the catalog now agree on every single object, which has never "
            "been true; the join has almost certainly stopped matching",
        )
        wrong = sorted(
            record["id"] for record in self.satellites
            if record["id"] in expected and record.get("operatorState") != expected[record["id"]]
        )
        self.assertEqual(wrong[:8], [], f"{len(wrong)} object(s) lost or changed their operator country")

    def test_the_operator_country_is_never_published_as_a_duplicate_of_the_registry(self):
        """Two rows saying the same country imply two sources agreeing."""
        offenders = [
            record["name"] for record in self.satellites
            if record.get("operatorState")
            and str(record["operatorState"]).lower() == str(record["ownerLabel"]).lower()
        ]
        self.assertEqual(offenders[:8], [], "operator country repeating the registering state")

    def test_the_release_says_whether_the_check_ran_at_all(self):
        """An object with no operator country and a release that never checked

        look identical on a card. Only one is a finding, so the release states
        which -- the same distinction `fleetEvidence` exists to draw. A refusal
        is a third case and gets its own count, because "we looked and declined"
        is not "we looked and agreed".
        """
        evidence = self.catalog.get("operatorStateEvidence")
        self.assertIsInstance(evidence, dict, "release publishes no operatorStateEvidence")
        self.assertIn("available", evidence)
        self.assertIn("checkedObjects", evidence)
        self.assertIn("differingObjects", evidence)
        self.assertIn("identityDisputedObjects", evidence)
        self.assertTrue(evidence.get("source"), "the cross-check must name its source")

    def test_the_registering_state_is_still_published_beside_it(self):
        """The fix must not overwrite a registry fact with a second opinion."""
        offenders = [
            record["name"] for record in self.satellites
            if record.get("operatorState") and not record.get("ownerLabel")
        ]
        self.assertEqual(offenders, [], "objects that lost their registering state")

    def test_the_refusal_count_is_reproducible_from_the_artifact(self):
        """A number nobody can recompute is not evidence of anything.

        `identityDisputedObjects` first shipped as a loop counter over every
        candidate the builder walked, and it read 64 for a catalog carrying 34 --
        a plausible-looking number that no reader could get back to. It is now
        counted over the objects that ship, and this recomputes it from the
        mirror and the artifact to say so.
        """
        if not self.records:
            self.skipTest("no GCAT mirror on this machine")
        refused = [
            record["id"] for record in self.satellites
            if record["id"] in self.records
            and not build_release.gcat_identity_agrees(record["name"], self.records[record["id"]])
            and not build_release.operator_state_agrees(
                record.get("ownerCode", ""),
                record["ownerLabel"],
                self.records[record["id"]]["state"],
            )
        ]
        self.assertEqual(
            self.catalog["operatorStateEvidence"]["identityDisputedObjects"],
            len(refused),
            "the published refusal count does not match the published catalog",
        )

    def test_operator_country_is_a_watched_field(self):
        """It is a row on the card, so a build that blanked every one of them

        must not publish clean. The drift gate is where "a claim changed" is
        noticed at all, and a displayed claim that is not in it is unguarded.
        """
        self.assertIn("operatorState", build_release._DRIFT_FIELDS)


if __name__ == "__main__":
    unittest.main()
