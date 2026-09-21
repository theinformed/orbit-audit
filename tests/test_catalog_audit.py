"""Tests for the deterministic catalog accuracy harness.

Every case here is built from a hand-written fixture rather than the live
artifact, so the checks are pinned to behaviour instead of to today's data. The
mirror-wide sweep that must run against real data lives in
`tests/test_catalog_name_matching.py`; these are the unit-level guarantees under
it. No test in this file touches the network.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline import catalog_audit as audit


def satellite(**overrides):
    record = {
        "id": 37218,
        "name": "SKYTERRA 1",
        "cosparId": "2010-061A",
        "ownerCode": "US",
        "ownerLabel": "United States",
        "organization": "NASA",
        "launchDate": "2010-11-14",
        "mission": "earth-observation",
        "sector": "civil",
        "constellation": "Telesat",
        "sourceGroups": ["telesat"],
        "orbit": "GEO",
        "periodMinutes": 1436.1,
        "perigeeKm": 35778.0,
        "apogeeKm": 35793.6,
        "purpose": "A NASA Earth-observing mission carrying multiple instruments to study the "
        "atmosphere, land, oceans, and Earth's energy balance.",
        "purposeKind": "template",
        "classificationConfidence": "high",
        "omm": {"INCLINATION": 5.2},
    }
    record.update(overrides)
    return record


def registry(owner_st="US", owner_ct="US", **extra):
    reg = audit.Registry()
    reg.spacetrack_satcat[37218] = {
        "NORAD_CAT_ID": "37218",
        "OBJECT_NAME": "SKYTERRA 1",
        "OBJECT_ID": "2010-061A",
        "COUNTRY": owner_st,
        "LAUNCH": "2010-11-14",
        "PERIOD": "1436.1",
        "APOGEE": "35794",
        "PERIGEE": "35778",
        "INCLINATION": "5.23",
    }
    reg.celestrak_satcat[37218] = {
        "NORAD_CAT_ID": 37218,
        "OBJECT_NAME": "SKYTERRA 1",
        "OBJECT_ID": "2010-061A",
        "OWNER": owner_ct,
        "LAUNCH_DATE": "2010-11-14",
        "PERIOD": 1436.1,
        "APOGEE": 35794,
        "PERIGEE": 35778,
        "INCLINATION": 5.23,
    }
    for key, value in extra.items():
        setattr(reg, key, value)
    return reg


def checks_hit(findings):
    return {finding.check for finding in findings}


class TokenBoundaryHelperTests(unittest.TestCase):
    def test_a_fragment_at_the_end_of_a_token_is_not_a_match(self):
        self.assertFalse(audit.fragment_matches_tokens("TERRA", audit.name_tokens("SKYTERRA 1")))
        self.assertFalse(audit.fragment_matches_tokens("DSP", audit.name_tokens("RIGIDSPHERE 2")))

    def test_a_fragment_followed_by_a_flight_number_is_a_match(self):
        self.assertTrue(audit.fragment_matches_tokens("COSMIC", audit.name_tokens("FORMOSAT7-3/COSMIC2-3")))
        self.assertTrue(audit.fragment_matches_tokens("SES-", audit.name_tokens("SES 1")))

    def test_a_fragment_followed_by_more_letters_is_not_a_match(self):
        self.assertFalse(audit.fragment_matches_tokens("ASTRO", audit.name_tokens("ASTROCAST-0402")))
        self.assertFalse(audit.fragment_matches_tokens("FENGYUN", audit.name_tokens("FENGYUNG-4C")))

    def test_multiword_fragments_match_as_a_token_run(self):
        self.assertTrue(audit.fragment_matches_tokens("SUOMI NPP", audit.name_tokens("SUOMI NPP")))
        self.assertFalse(audit.fragment_matches_tokens("SUOMI NPP", audit.name_tokens("SUOMI 1")))


class RuleExtractionTests(unittest.TestCase):
    def test_the_production_rules_are_read_out_of_the_production_source(self):
        fragments = audit.extract_name_rule_fragments()
        self.assertIn("TERRA", fragments["classify"])
        self.assertIn("DSP", fragments["classify"])
        self.assertIn("STARLINK", fragments["identify_constellation"])

    def test_extraction_fails_loudly_rather_than_returning_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.py"
            empty.write_text("def classify(name, owner):\n    return None\n")
            self.assertEqual(audit.extract_name_rule_fragments(empty).get("classify"), [])


class SubstringOvermatchCheckTests(unittest.TestCase):
    def test_skyterra_is_caught(self):
        findings = audit.check_substring_overmatch([satellite()], registry())
        self.assertEqual(len(findings), 1)
        self.assertIn("TERRA", findings[0].evidence["fragments"])
        self.assertEqual(findings[0].severity, "contradiction")

    def test_a_clean_name_is_not_caught(self):
        clean = satellite(id=25994, name="TERRA")
        self.assertEqual(audit.check_substring_overmatch([clean], registry()), [])


class RegimeMissionCheckTests(unittest.TestCase):
    def test_an_unannotated_orbit_conflict_is_a_contradiction(self):
        """The release is expected to publish the strong cases, not hide them."""
        findings = audit.check_regime_mission([satellite()], registry())
        self.assertEqual([f.check for f in findings], ["regime-mission-contradiction"])
        self.assertEqual(findings[0].severity, "contradiction")
        self.assertIn("annotation", findings[0].detail)

    def test_an_annotated_orbit_conflict_is_not_a_finding(self):
        """Audit and site showing the same thing is the goal, not a defect."""
        annotated = satellite(contestedAttribution=[{"kind": "orbit-inconsistent"}])
        self.assertEqual(audit.check_regime_mission([annotated], registry()), [])

    def test_a_weak_rule_stays_a_review_item_and_off_the_card(self):
        weak = satellite(orbit="LEO", mission="navigation")
        findings = audit.check_regime_mission([weak], registry())
        self.assertEqual(findings[0].severity, "review")

    def test_geostationary_human_spaceflight_is_a_contradiction(self):
        findings = audit.check_regime_mission([satellite(mission="human-spaceflight")], registry())
        self.assertEqual(findings[0].severity, "contradiction")

    def test_a_consistent_pairing_produces_nothing(self):
        self.assertEqual(
            audit.check_regime_mission([satellite(mission="communications")], registry()), []
        )

    def test_regime_is_recomputed_from_registry_elements(self):
        self.assertEqual(audit.regime_from_elements(1436.1, 35794, 35778, 5.2, None), "GEO")
        # Same height, same sidereal period, tilted: BEIDOU 3 IGSO-1's own
        # published numbers. The only element that differs from the GEO line
        # above is inclination, which is exactly what separates the two classes.
        self.assertEqual(audit.regime_from_elements(1436.099, 35900.7, 35672.5, 58.797, None), "IGSO")
        # And the wall holds from the other side at 19.9 deg.
        self.assertEqual(audit.regime_from_elements(1436.1, 35794, 35778, 19.9, None), "GEO")
        self.assertEqual(audit.regime_from_elements(95.0, 500, 480, 51.6, None), "LEO")
        self.assertEqual(audit.regime_from_elements(718.0, 20200, 20180, 55.0, None), "MEO")
        self.assertEqual(audit.regime_from_elements(720.0, 39000, 500, 63.4, None), "HEO")


class OwnerCheckTests(unittest.TestCase):
    def test_disagreeing_with_every_registry_is_a_contradiction(self):
        findings = audit.check_owner_disagreement(
            [satellite(ownerCode="PRC")], registry(owner_st="US", owner_ct="US")
        )
        self.assertEqual(findings[0].severity, "contradiction")

    def test_picking_one_registrys_side_is_only_a_review_item(self):
        findings = audit.check_owner_disagreement(
            [satellite(ownerCode="US")], registry(owner_st="US", owner_ct="ESA")
        )
        self.assertEqual(findings[0].severity, "review")

    def test_agreement_produces_nothing(self):
        self.assertEqual(audit.check_owner_disagreement([satellite()], registry()), [])


class IdentityCheckTests(unittest.TestCase):
    def test_a_one_day_launch_gap_is_a_convention_difference(self):
        reg = registry()
        reg.celestrak_satcat[37218]["LAUNCH_DATE"] = "2010-11-15"
        findings = audit.check_identity_disagreement([satellite()], reg)
        self.assertEqual([f.severity for f in findings], ["review"])

    def test_a_wide_launch_gap_is_a_contradiction(self):
        reg = registry()
        reg.celestrak_satcat[37218]["LAUNCH_DATE"] = "2011-01-01"
        findings = audit.check_identity_disagreement([satellite()], reg)
        self.assertEqual([f.severity for f in findings], ["contradiction"])

    def test_cosmetic_name_differences_are_ignored(self):
        reg = registry()
        reg.celestrak_satcat[37218]["OBJECT_NAME"] = "SKYTERRA-1 (MSV 1)"
        self.assertNotIn("name-disagreement", checks_hit(audit.check_identity_disagreement([satellite()], reg)))

    def test_a_registry_identity_swap_is_reported(self):
        reg = registry()
        reg.celestrak_satcat[37218]["OBJECT_NAME"] = "BISONSAT"
        self.assertIn("name-disagreement", checks_hit(audit.check_identity_disagreement([satellite()], reg)))


class FleetCheckTests(unittest.TestCase):
    def test_a_fleet_whose_operator_cannot_be_the_registrant_is_flagged(self):
        findings = audit.check_fleet_overmatch([satellite()], registry())
        self.assertEqual(findings[0].severity, "contradiction")
        self.assertIn("Telesat", findings[0].detail)

    def test_a_consistent_fleet_is_not_flagged(self):
        self.assertEqual(
            audit.check_fleet_overmatch([satellite(constellation="Telesat")], registry(owner_st="CA", owner_ct="CA")),
            [],
        )

    def test_an_unknown_fleet_label_is_not_guessed_about(self):
        self.assertEqual(audit.check_fleet_overmatch([satellite(constellation="Zorb")], registry()), [])


class DescriptionCheckTests(unittest.TestCase):
    def test_a_shared_specific_description_flags_only_the_unsupported_member(self):
        terra = satellite(id=25994, name="TERRA", constellation=None, orbit="LEO",
                          mission="earth-observation", organization="NASA")
        findings = audit.check_shared_specific_description([terra, satellite()], registry())
        self.assertEqual([f.norad_id for f in findings], [37218])

    def test_a_generic_hedged_description_is_not_flagged(self):
        text = "Its purpose has not been independently verified for this object."
        records = [satellite(purpose=text), satellite(id=1, purpose=text)]
        self.assertEqual(audit.check_shared_specific_description(records, registry()), [])

    def test_boilerplate_ranking_counts_and_ranks(self):
        catalog = {"satellites": [satellite(), satellite(id=1), satellite(id=2, purpose="unique")]}
        rows = audit.boilerplate_ranking(catalog)
        self.assertEqual(rows[0]["count"], 2)
        self.assertIn("NASA", rows[0]["claims"])

    def test_an_organisation_that_cannot_register_here_is_a_contradiction(self):
        findings = audit.check_unsupported_specificity([satellite()], registry(owner_st="GER", owner_ct="GER"))
        self.assertIn("unsupported-organization", checks_hit(findings))


class TriageQueueTests(unittest.TestCase):
    def test_the_queue_is_data_only_and_needs_no_model(self):
        catalog = {"satellites": [satellite()]}
        findings = audit.run_audit(catalog, registry())
        queue = audit.model_triage_prompts(findings, catalog)
        self.assertTrue(queue)
        self.assertEqual(queue[0]["noradId"], 37218)
        self.assertIn("deterministicFinding", queue[0])

    def test_an_empty_queue_is_never_an_all_clear(self):
        # No contradictions -> empty queue, but the summary still reports the
        # review findings, so a caller cannot read "empty" as "clean".
        catalog = {"satellites": [satellite(organization="United States", constellation=None,
                                            mission="communications", purpose="x", name="ANIK F2")]}
        findings = audit.run_audit(catalog, registry())
        self.assertEqual(audit.model_triage_prompts(findings, catalog), [])
        self.assertIn("bySeverity", audit.summarise(findings, catalog))


class SummaryTests(unittest.TestCase):
    def test_counts_are_per_object_not_per_finding(self):
        catalog = {"satellites": [satellite()]}
        findings = audit.run_audit(catalog, registry())
        summary = audit.summarise(findings, catalog)
        self.assertEqual(summary["catalogObjects"], 1)
        self.assertEqual(summary["objectsContradicted"], 1)
        self.assertGreater(summary["findings"], summary["objectsContradicted"])

    def test_worst_offenders_rank_by_independent_check_agreement(self):
        catalog = {"satellites": [satellite(), satellite(id=99, name="ANIK F2", organization="Telesat",
                                                        constellation=None, mission="communications",
                                                        purpose="x")]}
        findings = audit.run_audit(catalog, registry())
        self.assertEqual(audit.worst_offenders(findings)[0]["noradId"], 37218)


class CatalogResolutionTests(unittest.TestCase):
    def test_a_missing_catalog_raises_rather_than_auditing_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = audit.ROOT
            try:
                audit.ROOT = Path(tmp)
                with self.assertRaises(FileNotFoundError):
                    audit.resolve_catalog_path(None)
            finally:
                audit.ROOT = original

    def test_a_non_catalog_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not-a-catalog.json"
            path.write_text(json.dumps({"frames": []}))
            with self.assertRaises(ValueError):
                audit.load_catalog(path)


if __name__ == "__main__":
    unittest.main()
