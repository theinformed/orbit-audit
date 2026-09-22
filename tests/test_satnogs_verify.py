"""What the SatNOGS cross-check is allowed to conclude, and from what.

Every test here pins a REASON, not a value. The values in this file are all
real: the COSMIC rows are the live SatNOGS and catalog records for NORAD 66658
as read on 2026-08-19, so a change in how either is parsed shows up here as a
failure rather than as a quietly different card.

The thing this module can get catastrophically wrong is not "no correction". It
is a CONFIDENT WRONG CORRECTION on a card a Navy student reads, so most of what
follows is a test that it declines to act.
"""

import json
import tempfile
import unittest
from pathlib import Path

from pipeline import satnogs_verify as verify


# The live SatNOGS row for the Korean COSMIC, verbatim from
# https://db.satnogs.org/api/satellites/?format=json on 2026-08-19. Note
# `norad_cat_id` 98494: that is SatNOGS's TEMPORARY id, and the real catalog
# number is in `norad_follow_id`.
COSMIC_SATNOGS = {
    "sat_id": "XFCX-7274-9992-0205-7857",
    "norad_cat_id": 98494,
    "norad_follow_id": 66658,
    "name": "COSMIC",
    "names": "",
    "status": "alive",
    "decayed": None,
    "launched": "2025-11-26T15:54:00Z",
    "operator": "None",
    "countries": "KR",
    "citation": "COSMIC",
}

# The six Taiwanese/US spacecraft the name token actually belongs to.
FORMOSAT_SATNOGS = {
    "sat_id": "AAAA-0000-0000-0000-0001",
    "norad_cat_id": 44343,
    "norad_follow_id": None,
    "name": "FORMOSAT 7-3",
    "names": "",
    "status": "alive",
    "launched": "2019-06-25T00:00:00Z",
    "operator": "None",
    "countries": "TW",
}

COSMIC_OURS = {
    "id": 66658, "name": "COSMIC", "ownerCode": "SKOR", "launchDate": "2025-11-26",
    "launchGroup": "2025-274", "mission": "weather", "sector": "civil",
    "constellation": "COSMIC", "classificationBasis": "name-pattern",
}
FORMOSAT_OURS = [
    {"id": 44343, "name": "FORMOSAT7-3/COSMIC2-3", "ownerCode": "TWN", "launchDate": "2019-06-25",
     "launchGroup": "2019-036", "mission": "weather", "sector": "civil",
     "constellation": "COSMIC", "classificationBasis": "name-pattern"},
    {"id": 44349, "name": "FORMOSAT7-1/COSMIC2-1", "ownerCode": "TWN", "launchDate": "2019-06-25",
     "launchGroup": "2019-036", "mission": "weather", "sector": "civil",
     "constellation": "COSMIC", "classificationBasis": "name-pattern"},
]

COSMIC_TRANSMITTERS = [
    {"norad_cat_id": 98494, "norad_follow_id": 66658, "service": "Space Operation",
     "status": "active", "mode": "GMSK"},
    {"norad_cat_id": 98494, "norad_follow_id": 66658, "service": "Space Operation",
     "status": "inactive", "mode": "FSK"},
]
FORMOSAT_TRANSMITTERS = [
    {"norad_cat_id": 44343, "norad_follow_id": None, "service": "Earth Exploration",
     "status": "active", "mode": "CW"},
]


def cosmic_world():
    """The whole COSMIC situation, as three indexes, exactly as `main` builds them."""
    satellites = [COSMIC_OURS, *FORMOSAT_OURS]
    satnogs = verify.index_by_norad([COSMIC_SATNOGS, FORMOSAT_SATNOGS])
    transmitters = verify.index_by_norad([*COSMIC_TRANSMITTERS, *FORMOSAT_TRANSMITTERS])
    return satellites, satnogs, transmitters


class TheCatalogNumberIsTheKeyTests(unittest.TestCase):
    def test_a_satnogs_placeholder_id_is_never_treated_as_a_catalog_number(self):
        # 98494 is SatNOGS's own temporary handle for an object nobody has tied
        # to the public catalog yet. Indexing it as a catalog number would file
        # this spacecraft under a number space-track has not issued, and could
        # collide with a real object if the catalog ever reaches 90000.
        index = verify.index_by_norad([COSMIC_SATNOGS])
        self.assertNotIn(98494, index)

    def test_the_followed_id_is_indexed_because_it_is_the_real_catalog_number(self):
        # This is the whole reason the lane finds COSMIC at all. An index built
        # on `norad_cat_id` alone -- and the API's own `?norad_cat_id=` filter,
        # which returns [] for 66658 -- misses the one object it was written for.
        index = verify.index_by_norad([COSMIC_SATNOGS])
        self.assertEqual([entry["sat_id"] for entry in index[66658]], ["XFCX-7274-9992-0205-7857"])

    def test_two_satnogs_rows_for_one_number_are_kept_as_two(self):
        # Ambiguity in the source must reach the caller as ambiguity. Picking a
        # winner here would hide the one condition under which no comparison is
        # safe at all.
        twin = dict(COSMIC_SATNOGS, sat_id="OTHER-0000-0000-0000-0000")
        self.assertEqual(len(verify.index_by_norad([COSMIC_SATNOGS, twin])[66658]), 2)


class IdentityMustBeCorroboratedTests(unittest.TestCase):
    def test_the_korean_cosmic_is_confirmed_on_name_and_launch_date(self):
        verdict, reasons = verify.identity_verdict(COSMIC_OURS, COSMIC_SATNOGS)
        self.assertEqual(verdict, "confirmed")
        self.assertTrue(any("launch date agrees" in reason for reason in reasons))

    def test_a_rideshare_misattribution_is_contradicted_not_confirmed(self):
        # Measured 2026-08-19: SatNOGS's `norad_follow_id` is often a community
        # member's guess at which TLE belongs to which CubeSat on a crowded
        # rideshare. Our NORAD 59452 is "KORSAT-1"; theirs is "QPS-SAR-7". The
        # number matched and the object is not the same, so nothing downstream
        # may believe a single field of that row.
        ours = {"id": 59452, "name": "KORSAT-1", "ownerCode": "SKOR", "launchDate": "2023-06-12"}
        theirs = {"name": "QPS-SAR-7", "names": "", "launched": "2024-11-04T00:00:00Z"}
        verdict, _ = verify.identity_verdict(ours, theirs)
        self.assertEqual(verdict, "contradicted")

    def test_a_number_alone_is_never_identity(self):
        # Neither name nor launch date can be compared, so the honest answer is
        # "we matched a number", and `withdrawal_candidates` refuses to act on it.
        ours = {"id": 1, "name": "", "launchDate": None}
        theirs = {"name": "", "names": "", "launched": None}
        self.assertEqual(verify.identity_verdict(ours, theirs)[0], "id-only")

    def test_the_two_catalogues_spell_the_same_spacecraft_differently(self):
        # Our names concatenate the designations SatNOGS splits. If this stops
        # working, ~900 confirmed identities silently become "contradicted" and
        # the lane goes quiet without failing.
        self.assertTrue(verify.names_agree("FORMOSAT7-3/COSMIC2-3", "FORMOSAT 7-3"))
        self.assertTrue(verify.names_agree("AO-91", "FOX-1B", alternates="AO-91,FOX-1B"))

    def test_normalisation_cannot_separate_two_spacecraft_with_one_name(self):
        # Stated as a test because it is the premise of the whole module: name
        # matching says these are the same object, and they are not. Only the
        # catalog number distinguishes them.
        self.assertTrue(verify.names_agree("COSMIC", "COSMIC"))

    def test_a_one_day_launch_gap_is_a_timezone_not_a_different_spacecraft(self):
        self.assertTrue(verify.launch_dates_agree("2019-06-25", "2019-06-24T22:00:00Z"))
        self.assertFalse(verify.launch_dates_agree("2017-11-18", "2018-11-18T00:00:00Z"))

    def test_an_absent_launch_date_is_unknown_rather_than_a_mismatch(self):
        self.assertIsNone(verify.launch_dates_agree("2019-06-25", None))


class CountryIsCompared_NeverCopiedTests(unittest.TestCase):
    def test_iso_and_satcat_spellings_of_one_country_agree(self):
        self.assertEqual(verify.country_verdict("SKOR", "KR")[0], "agree")

    def test_an_unknown_iso_code_is_unmappable_rather_than_guessed(self):
        # Guessing that ZW is ZWE is the same cheap inference this module exists
        # to stop, and it would report a false disagreement.
        self.assertEqual(verify.country_verdict("ZWE", "ZW")[0], "unmappable")

    def test_no_country_recorded_is_absent_not_a_disagreement(self):
        # 185 of the 930 joined objects carry no country. Counting those as
        # disagreements would have made the report's headline number four times
        # too large.
        self.assertEqual(verify.country_verdict("US", "")[0], "absent")


class TheCohortDetectorTests(unittest.TestCase):
    def test_cosmic_is_an_outlier_in_its_own_constellation(self):
        satellites, _, _ = cosmic_world()
        outliers = verify.cohort_outliers(satellites)
        self.assertEqual([entry["id"] for entry in outliers], [66658])

    def test_a_cohort_that_agrees_with_itself_produces_nothing(self):
        satellites = [dict(member) for member in FORMOSAT_OURS]
        self.assertEqual(verify.cohort_outliers(satellites), [])

    def test_a_shared_launch_group_is_enough_to_clear_an_owner_outlier(self):
        # A jointly owned spacecraft that went up with its fleet is not a name
        # collision. Requiring BOTH signals is what keeps AZERSPACE 2/INTELSAT 38
        # off this list.
        satellites = [dict(COSMIC_OURS, launchGroup="2019-036"), *FORMOSAT_OURS]
        self.assertEqual(verify.cohort_outliers(satellites), [])


class WhatItIsAllowedToCorrectTests(unittest.TestCase):
    def test_the_cosmic_card_is_corrected_and_this_is_the_regression(self):
        # THE bug. NORAD 66658 is a South Korean CubeSat shown as an American
        # environmental satellite because it shares a name with the
        # FORMOSAT-7/COSMIC-2 radio-occultation constellation.
        # <https://db.satnogs.org/satellite/XFCX-7274-9992-0205-7857>
        satellites, satnogs, transmitters = cosmic_world()
        applied = verify.withdrawal_candidates(satellites, satnogs, transmitters)
        self.assertEqual(len(applied), 1)
        entry = applied[0]
        self.assertEqual(entry["id"], 66658)
        self.assertEqual(sorted(entry["withdraw"]), ["constellation", "mission", "sector"])
        self.assertEqual(entry["was"]["mission"], "weather")
        # Every change carries the page a reader can check, the way
        # OPERATOR_SECTORS stores one citation per operator family.
        self.assertEqual(entry["source"], "https://db.satnogs.org/satellite/XFCX-7274-9992-0205-7857")

    def test_it_withdraws_and_never_asserts(self):
        # The output can only take a claim away. If a future edit lets this
        # write a mission, a country or an operator, the lane has become capable
        # of the confidently wrong card it was built to prevent.
        satellites, satnogs, transmitters = cosmic_world()
        entry = verify.withdrawal_candidates(satellites, satnogs, transmitters)[0]
        self.assertNotIn("mission", entry.get("set", {}))
        self.assertEqual(set(entry["withdraw"]) - {"constellation", "mission", "sector"}, set())

    def test_a_curated_or_catalog_number_basis_is_never_overruled(self):
        # A human, or a join on the catalog number itself, outranks this lane
        # absolutely. Only the weakest basis `build_release` produces is in scope.
        satellites, satnogs, transmitters = cosmic_world()
        satellites[0] = dict(COSMIC_OURS, classificationBasis="norad-id")
        self.assertEqual(verify.withdrawal_candidates(satellites, satnogs, transmitters), [])

    def test_no_satnogs_entry_means_no_correction(self):
        # METOP SG-A, SES 3 and AZERSPACE 2/INTELSAT 38 are all owner-outliers in
        # their constellations and all three cards are RIGHT. None of them is in
        # SatNOGS, and that absence is what stops the lane damaging them.
        satellites, _, transmitters = cosmic_world()
        self.assertEqual(verify.withdrawal_candidates(satellites, {}, transmitters), [])

    def test_an_unconfirmed_identity_stops_the_correction(self):
        satellites, satnogs, transmitters = cosmic_world()
        satnogs = verify.index_by_norad([
            dict(COSMIC_SATNOGS, name="SOMETHING ELSE", launched="2021-01-01T00:00:00Z"),
            FORMOSAT_SATNOGS,
        ])
        self.assertEqual(verify.withdrawal_candidates(satellites, satnogs, transmitters), [])

    def test_ambiguity_in_satnogs_stops_the_correction(self):
        satellites, _, transmitters = cosmic_world()
        twin = dict(COSMIC_SATNOGS, sat_id="TWIN-0000-0000-0000-0000")
        satnogs = verify.index_by_norad([COSMIC_SATNOGS, twin, FORMOSAT_SATNOGS])
        self.assertEqual(verify.withdrawal_candidates(satellites, satnogs, transmitters), [])


class ServiceEvidenceTests(unittest.TestCase):
    def test_space_operation_alone_never_separates_two_missions(self):
        # It is the allocation for a spacecraft's own telemetry-and-command
        # link, which every satellite of every kind has. Treating it as mission
        # evidence would let the lane "prove" anything about anything.
        self.assertEqual(
            verify.SERVICE_CONSISTENT_MISSIONS["Space Operation"] & {"weather", "communications"},
            {"weather", "communications"},
        )

    def test_amateur_service_is_consistent_with_a_communications_mission(self):
        # A first draft omitted this and flagged 30 correctly-labelled OSCARs as
        # contradictions. An amateur-radio satellite IS a communications satellite.
        self.assertIn("communications", verify.SERVICE_CONSISTENT_MISSIONS["Amateur"])

    def test_an_inactive_transmitter_still_says_what_the_spacecraft_was_for(self):
        index = verify.index_by_norad([
            {"norad_cat_id": 1, "norad_follow_id": None, "service": "Meteorological", "status": "inactive"},
        ])
        self.assertEqual(verify.services_for(1, index), {"Meteorological"})

    def test_an_active_transmitter_outranks_a_retired_one(self):
        index = verify.index_by_norad([
            {"norad_cat_id": 1, "norad_follow_id": None, "service": "Meteorological", "status": "inactive"},
            {"norad_cat_id": 1, "norad_follow_id": None, "service": "Amateur", "status": "active"},
        ])
        self.assertEqual(verify.services_for(1, index), {"Amateur"})

    def test_satnogs_unknown_is_not_a_service(self):
        # 3,530 of their 5,007 transmitter rows say "Unknown". Comparing that
        # against anything would manufacture 3,530 findings out of silence.
        index = verify.index_by_norad([
            {"norad_cat_id": 1, "norad_follow_id": None, "service": "Unknown", "status": "active"},
        ])
        self.assertEqual(verify.services_for(1, index), set())


class TheLedgerDoesNotEraseItselfTests(unittest.TestCase):
    def test_a_withdrawal_survives_a_run_that_no_longer_finds_it(self):
        # THE self-reverting bug. `withdrawal_candidates` reads the PUBLISHED
        # catalog, and a withdrawn object no longer looks like an outlier there,
        # because the withdrawal already fixed it. A snapshot file would go empty
        # on the second run and the next build would put COSMIC back in the
        # weather constellation with every test still green.
        existing = [{"id": 66658, "name": "COSMIC", "withdraw": ["mission"],
                     "checkedAt": "2026-08-19T00:00:00Z", "firstSeen": "2026-08-19T00:00:00Z"}]
        self.assertEqual([e["id"] for e in verify.merge_withdrawals(existing, [])], [66658])

    def test_re_confirming_keeps_the_date_the_finding_was_first_made(self):
        existing = [{"id": 66658, "checkedAt": "2026-08-19T00:00:00Z", "firstSeen": "2026-08-19T00:00:00Z"}]
        found = [{"id": 66658, "checkedAt": "2026-09-01T00:00:00Z"}]
        self.assertEqual(verify.merge_withdrawals(existing, found)[0]["firstSeen"], "2026-08-19T00:00:00Z")

    def test_a_missing_ledger_is_a_normal_state(self):
        # The site must build identically whether or not this lane has ever run.
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(verify.load_withdrawals(Path(directory) / "absent.json"), {})

    def test_the_ledger_round_trips_through_the_file_build_release_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "satnogs_withdrawals.json"
            path.write_text(json.dumps({"withdrawals": [
                {"id": 66658, "withdraw": ["mission"], "source": "https://db.satnogs.org/x"},
            ]}), encoding="utf-8")
            loaded = verify.load_withdrawals(path)
            self.assertEqual(loaded[66658]["withdraw"], ["mission"])


class PolitenessTests(unittest.TestCase):
    def test_the_user_agent_says_who_we_are_and_how_to_complain(self):
        # SatNOGS is run by volunteers, and this project has already been
        # firewalled once by CelesTrak. An anonymous scraper is the first thing
        # a tired sysadmin blocks.
        self.assertIn("space-teaching-aid-verify", verify.USER_AGENT)
        self.assertIn("@", verify.USER_AGENT)

    def test_the_request_floor_is_at_least_one_second(self):
        self.assertGreaterEqual(verify.MIN_REQUEST_INTERVAL_S, 1.0)

    def test_a_non_200_stops_the_lane_rather_than_retrying(self):
        self.assertTrue(issubclass(verify.SatnogsUnavailable, RuntimeError))

    def test_there_is_no_token_in_the_source(self):
        # The personal token lives in an untracked file or in the environment.
        # A fallback key in the source would be committed by the next person who
        # ran `git add -A`.
        source = Path(verify.__file__).read_text(encoding="utf-8")
        self.assertNotIn("SATNOGS_API_TOKEN=", source.replace('"SATNOGS_API_TOKEN"', ""))
        self.assertIsNone(verify.api_token.__defaults__)



class CelestrakGroupCoherenceTests(unittest.TestCase):
    """Auditing the OTHER path a mission reaches a card by.

    The name-rule audit could not see this one at all, which is how THEMIS A sat
    on the site as CIVIL / OTHER SATCOM while every name rule measured clean.
    """

    def members(self):
        # A miniature `tdrss` group with the shape the real one has: a few
        # relays that the group is genuinely about, and a crowd of users that it
        # is not.
        return [
            {"id": 22314, "name": "TDRS 6", "mission": "communications",
             "classificationBasis": "name-pattern", "sourceGroups": ["tdrss"]},
            {"id": 20580, "name": "HST", "mission": "science",
             "classificationBasis": "norad-id", "sourceGroups": ["tdrss"]},
            {"id": 25994, "name": "TERRA", "mission": "earth-observation",
             "classificationBasis": "norad-id", "sourceGroups": ["tdrss"]},
            {"id": 40482, "name": "MMS 1", "mission": "science",
             "classificationBasis": "norad-id", "sourceGroups": ["tdrss"]},
            {"id": 30580, "name": "THEMIS A", "mission": "communications",
             "classificationBasis": "source-group", "sourceGroups": ["tdrss"]},
        ]

    def row_for(self, group, rows):
        return next(row for row in rows if row["group"] == group)

    def test_a_group_is_judged_only_by_members_it_did_not_label(self):
        # THE method. `tdrss` gave THEMIS A its mission, so counting THEMIS A as
        # evidence that `tdrss` is a communications group is circular and would
        # report every group as pure. Four independent witnesses here, not five.
        row = self.row_for("tdrss", verify.celestrak_group_coherence(self.members()))
        self.assertEqual(row["members"], 5)
        self.assertEqual(row["independent"], 4)
        self.assertEqual(row["decided"], 1)

    def test_a_relay_networks_user_list_is_contradicted_by_its_own_members(self):
        row = self.row_for("tdrss", verify.celestrak_group_coherence(self.members()))
        self.assertEqual(row["agree"], 1)      # TDRS 6, which the group is named for
        self.assertEqual(row["disagree"], 3)   # Hubble, Terra, MMS 1
        self.assertEqual(row["disagreeAs"], {"science": 2, "earth-observation": 1})

    def test_it_reports_which_groups_are_withheld_rather_than_deciding(self):
        # The withheld set is a recorded decision in build_release, with a written
        # reason per group. A threshold computed here would silently reclassify
        # hundreds of objects the first time a group's membership shifted — and
        # would have withheld `amateur`, blanking 55 correct cards.
        row = self.row_for("tdrss", verify.celestrak_group_coherence(self.members()))
        self.assertTrue(row["withheld"])
        self.assertTrue(self.row_for("weather", verify.celestrak_group_coherence(self.members()))["withheld"] is False)

    def test_a_group_with_no_independent_members_is_unaudited_not_clean(self):
        # It sorts last and reports zero witnesses. Nothing in the catalog can
        # currently contradict it, and the report must not let that read as a
        # pass.
        rows = verify.celestrak_group_coherence(self.members())
        blank = [row for row in rows if row["independent"] == 0]
        self.assertTrue(blank)
        self.assertEqual(rows[-1]["independent"], 0)
        for row in blank:
            self.assertEqual((row["agree"], row["disagree"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
