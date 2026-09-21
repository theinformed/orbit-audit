"""When a fleet may vouch for its members' mission class, and when it may not.

The chip on a satellite card states a MISSION CLASS -- "Commercial SATCOM" --
and until 2026-08-27 it drew that claim dashed, dimmed and question-marked on
6,288 of 8,000 objects, because their label came from a programme-name pattern.
Sean, on STARLINK-11600: "I don't like that ?", and "it looks ridiculous on the
display."

The scepticism was aimed at the right catalogue and the wrong claim. The 18th
Space Defense Squadron names objects within a launch on observation and corrects
them afterwards -- LitSat-1 and LituanicaSat-1 were transposed until Doppler
measurements settled it -- so which UNIT a Starlink is really is uncertain. What
survives a transposition is that both objects are Starlinks, and that is the
claim the chip makes.

`constellation_cohort_verdicts` establishes the surviving half. Every test here
pins a REASON it may or may not do so, and most of them are refusals: a rule
that promotes everything is the Tianmu-1 11 defect arriving from the other side.
"""

import unittest

from pipeline import satnogs_verify as verify


def member(catalog_id, **over):
    """One ordinary member of a healthy fleet, shaped like a published record."""
    row = {
        "id": catalog_id,
        "name": f"FLEETSAT-{catalog_id}",
        "constellation": "Fleetsat",
        "ownerCode": "US",
        "mission": "communications",
        "sector": "commercial",
        "launchGroup": "2025-039",
        "classificationBasis": "name-pattern",
    }
    row.update(over)
    return row


def fleet(size=12, **over):
    # Two launch groups, so the batching clause is satisfied honestly rather
    # than by every member sharing one designator.
    rows = [member(i, launchGroup="2025-039" if i % 2 else "2025-040") for i in range(size)]
    if over:
        rows[0].update(over)
    return rows


class CohortVerdictTests(unittest.TestCase):
    def verdict(self, rows):
        return verify.constellation_cohort_verdicts(rows)["Fleetsat"]

    def test_a_fleet_that_agrees_with_itself_vouches_for_its_members(self):
        result = self.verdict(fleet())
        self.assertTrue(result["consistent"], result["why"])
        self.assertEqual(result["members"], 12)
        self.assertEqual(result["ownerCode"], "US")
        self.assertEqual(result["ownerShare"], 1.0)

    def test_a_handful_of_objects_is_not_a_fleet(self):
        # Two spacecraft sharing an owner is a coincidence. The threshold is
        # where a reader would agree the word "fleet" starts.
        result = self.verdict(fleet(size=verify.COHORT_MIN_MEMBERS - 1))
        self.assertFalse(result["consistent"])
        self.assertIn("member(s) here", result["why"])

    def test_a_fleet_that_cannot_agree_who_owns_it_vouches_for_nobody(self):
        # Globalstar splits 12 GLOB / 6 US and Intelsat 13 ITSO / 5 US / 1 AZER.
        # Under a plurality rule each would corroborate its own larger faction
        # while contradicting the smaller -- a cohort disagreeing with itself,
        # read as agreement.
        rows = fleet(size=12)
        for row in rows[:5]:
            row["ownerCode"] = "LUXE"
        result = self.verdict(rows)
        self.assertFalse(result["consistent"])
        self.assertIn("who owns them", result["why"])

    def test_a_fleet_that_cannot_agree_what_it_is_vouches_for_nobody(self):
        # The clause that ties the check to the CLAIM. It costs nothing on the
        # live catalog and it is the reason a future name rule cannot drop a
        # missile-warning label into the Starlink cohort and have four thousand
        # siblings corroborate it.
        rows = fleet(size=12)
        for row in rows[:5]:
            row["mission"] = "missile-warning"
        result = self.verdict(rows)
        self.assertFalse(result["consistent"])
        self.assertIn("what they are", result["why"])

    def test_a_name_several_lone_objects_share_is_not_a_fleet(self):
        # GPS, Eutelsat, Fengyun, WGS, SES and Sentinel all fail here on the
        # live catalog: their members go up one at a time, so the name is the
        # only thing tying them together, which is the thing being tested.
        rows = [member(i, launchGroup=f"2025-{i:03d}") for i in range(12)]
        result = self.verdict(rows)
        self.assertFalse(result["consistent"])
        self.assertIn("same launch", result["why"])

    def test_one_disputed_member_stops_the_whole_fleet(self):
        # All 159 Yaogan carry a contested attribution: the US Department of
        # Defense and the operator do not agree about them. `identity_verdict`
        # already refuses to confirm anything an independent fact contradicts,
        # and this is that rule at cohort scale.
        rows = fleet(contestedAttribution=[{"kind": "disputed-operator"}])
        result = self.verdict(rows)
        self.assertFalse(result["consistent"])
        self.assertIn("disputes", result["why"])
        self.assertEqual(result["contestedMembers"], 1)

    def test_a_withdrawn_name_claim_stops_the_whole_fleet(self):
        rows = fleet(classificationBasis="withdrawn-name-collision")
        result = self.verdict(rows)
        self.assertFalse(result["consistent"])
        self.assertIn("withdrew", result["why"])

    def test_a_refusal_still_publishes_the_numbers_it_was_reached_on(self):
        # The refusals are the interesting half of the table -- they are why 159
        # Yaogan cards keep their question mark -- so they may never be an empty
        # row a reader has to take on trust.
        result = self.verdict(fleet(size=4))
        self.assertFalse(result["consistent"])
        self.assertTrue(result["why"])
        for key in ("members", "ownerCode", "ownerShare", "mission", "missionShare",
                    "batchedLaunchGroups", "contestedMembers", "withdrawnMembers"):
            self.assertIn(key, result)

    def test_the_verdict_is_the_cohorts_so_every_member_gets_the_same_answer(self):
        # Sean: "everything in starlink should share the same one yes?" He is
        # right. STARLINK-1892 and STARLINK-2001 are the only members of their
        # launch batches the browser ceiling retained and IRIDIUM 174 flew with
        # spares; judged per object those three hedge while thousands of
        # identical siblings do not, and a reader cannot tell why.
        rows = fleet(size=12)
        rows[0]["launchGroup"] = None          # nothing to compare it against
        rows[1]["launchGroup"] = "2025-999"    # launched alone
        verdicts = verify.constellation_cohort_verdicts(rows)
        self.assertTrue(verdicts["Fleetsat"]["consistent"])
        self.assertEqual(len(verdicts), 1)

    def test_an_object_in_no_fleet_is_never_vouched_for(self):
        self.assertEqual(verify.constellation_cohort_verdicts(
            [member(1, constellation=None), member(2, constellation="")]), {})


class PublishedFieldTests(unittest.TestCase):
    """What `build_catalog` records, and what it must leave alone."""

    def test_the_basis_is_recorded_beside_the_finding_never_replaced_by_it(self):
        # Sean intends to revisit this doctrine. Collapsing `name-pattern` into
        # the fleet finding would destroy how the label was actually arrived at,
        # and revisiting would then mean rebuilding data rather than editing one
        # rendering rule.
        import inspect

        from pipeline import build_release

        source = inspect.getsource(build_release.build_catalog)
        self.assertIn('record["missionCorroboration"] = "cohort-consistent"', source)
        self.assertNotIn('record["classificationBasis"] =', source)


if __name__ == "__main__":
    unittest.main()
