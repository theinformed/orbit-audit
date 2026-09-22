import shutil
import tempfile
from unittest import mock
from pathlib import Path
import json
from pipeline import build_release
import unittest

from pipeline.build_release import (
    CELESTRAK_FLEET_GROUPS,
    CELESTRAK_MISSION_CATEGORY_GROUPS,
    CELESTRAK_MISSION_GROUPS,
    PARTICIPATION_GROUPS,
    classify,
    repair_mission_from_groups,
    station_group_is_about_this_object,
)


class SatelliteClassificationTests(unittest.TestCase):
    def test_public_pwsa_transport_names_are_leo_milsatcom(self):
        for name in ("PRAETORIAN SDA_601", "PRAETORIAN SDA_521", "SDA_1664", "SDA_1684"):
            mission, sector, constellation, organization, confidence = classify(name, "US")
            self.assertEqual(mission, "communications")
            self.assertEqual(sector, "military")
            self.assertEqual(constellation, "PWSA Transport Layer")
            self.assertEqual(organization, "Space Development Agency")
            self.assertEqual(confidence, "high")

    def test_adjacent_ambiguous_sda_name_is_not_asserted_as_transport(self):
        mission, sector, constellation, organization, confidence = classify("SDA_1685", "US")
        self.assertEqual(mission, "other")
        self.assertEqual(sector, "unknown")
        self.assertIsNone(constellation)
        self.assertEqual(organization, "United States")
        self.assertEqual(confidence, "low")


class CelestrakGroupMissionRepairTests(unittest.TestCase):
    """Regression coverage for repair_mission_from_groups (docs/satellite-catalog-classification.md)."""

    def test_a_name_pattern_classification_is_never_overridden_by_group_membership(self):
        # A satellite classify() already resolved (mission != "other") must come
        # back untouched even if it happens to also carry an unrelated group.
        mission, sector, confidence = repair_mission_from_groups(
            "communications", "commercial", "high", ["science", "amateur"]
        )
        self.assertEqual((mission, sector, confidence), ("communications", "commercial", "high"))

    def test_prior_hardcoded_fallback_groups_resolve_identically_and_in_original_order(self):
        # These seven cases reproduce the exact literal fallback chain that
        # existed before the CelesTrak category-group expansion, in its
        # original priority order, so no previously resolved "other" repair
        # changes as a result of adding more groups after it.
        cases = [
            (["weather"], ("weather", "civil", "high")),
            (["gnss"], ("navigation", "mixed", "high")),
            (["science"], ("science", "civil", "high")),
            (["resource"], ("earth-observation", "civil", "medium")),
            (["stations"], ("human-spaceflight", "civil", "medium")),
            (["military"], ("other", "military", "high")),
            (["starlink"], ("communications", "commercial", "high")),
            (["oneweb"], ("communications", "commercial", "high")),
        ]
        for groups, expected in cases:
            with self.subTest(groups=groups):
                self.assertEqual(repair_mission_from_groups("other", "unknown", "low", groups), expected)

    def test_first_matching_group_in_priority_order_wins_when_several_apply(self):
        # "weather" is earlier in CELESTRAK_MISSION_GROUPS than "resource", so a
        # satellite carrying both must resolve as weather, not earth-observation.
        result = repair_mission_from_groups("other", "unknown", "low", ["resource", "weather"])
        self.assertEqual(result, ("weather", "civil", "high"))

    def test_new_category_groups_resolve_a_previously_unclassified_object(self):
        for groups, expected in (
            (["geodetic"], ("science", "civil", "high")),
            (["amateur"], ("communications", "civil", "high")),
            (["musson"], ("communications", "mixed", "medium")),
            (["nnss"], ("navigation", "civil", "high")),
            (["cubesat"], ("technology", "academic", "medium")),
        ):
            with self.subTest(groups=groups):
                self.assertEqual(repair_mission_from_groups("other", "unknown", "low", groups), expected)

    def test_group_names_celestrak_does_not_publish_are_not_requested(self):
        """Five names were removed on 2026-08-16 because they do not exist.

        Asked for a group it does not publish, CelesTrak answers **HTTP 200**
        with a plain-text ``Invalid query: "GROUP=noaa&FORMAT=JSON" (GROUP=noaa
        not found)``. A status-code check therefore sees success, and only the
        JSON validator catches it — the same "200 is not success" shape this
        project has been bitten by before. Measured one request each from the
        VPS, the only host permitted to reach celestrak.org.

        The repair rules keyed to them could never fire, and the requests could
        never succeed. This test exists so nobody restores them believing the
        mirror is simply behind.
        """
        for name in ("noaa", "swarm", "gorizont", "raduga", "molniya"):
            with self.subTest(group=name):
                self.assertNotIn(name, CELESTRAK_MISSION_CATEGORY_GROUPS)
                self.assertNotIn(name, [row[0] for row in CELESTRAK_MISSION_GROUPS])

    def test_no_matching_group_leaves_object_unresolved(self):
        result = repair_mission_from_groups("other", "unknown", "low", ["visual", "analyst"])
        self.assertEqual(result, ("other", "unknown", "low"))

    def test_mission_group_table_only_uses_the_sites_existing_mission_values(self):
        existing_missions = {
            "communications", "earth-observation", "navigation", "weather", "science",
            "human-spaceflight", "technology", "missile-warning", "other",
        }
        for group, mission, _sector, _confidence in CELESTRAK_MISSION_GROUPS:
            if mission is not None:
                self.assertIn(mission, existing_missions, group)



class HostedAugmentationTest(unittest.TestCase):
    """A satellite that hosts a navigation payload is not a navigation satellite.

    CelesTrak's `gnss` group mixes 157 core constellation members with 13
    communications satellites carrying an augmentation transponder, and it names
    the system for exactly the 13. Measured against the live group 2026-08-18.
    """

    def test_names_the_hosted_system(self):
        self.assertEqual(
            build_release.hosted_augmentation_system("GALAXY 30 (WAAS/PRN 135)"), "WAAS")
        self.assertEqual(
            build_release.hosted_augmentation_system("ASTRA 5B (EGNOS/PRN 123)"), "EGNOS")
        self.assertEqual(
            build_release.hosted_augmentation_system("LUCH 5A (SDCM/PRN 140)"), "SDCM")
        self.assertEqual(
            build_release.hosted_augmentation_system("GSAT-8 (GAGAN/PRN 127)"), "GAGAN")
        self.assertEqual(
            build_release.hosted_augmentation_system("INMARSAT 4-F2 (SOUTHPAN/PRN 122)"), "SOUTHPAN")

    def test_a_real_navigation_satellite_hosts_nothing(self):
        # The distinguishing mark: core members carry a PRN and no system name.
        for name in ("GPS BIIR-5  (PRN 22)", "COSMOS 2559", "BEIDOU-3 M21",
                     "GSAT0101 (PRN E11)", "NVS-01 (IRNSS-1J)"):
            self.assertIsNone(build_release.hosted_augmentation_system(name), name)

    def test_group_membership_still_labels_the_constellations(self):
        # 28 GLONASS satellites are catalogued as COSMOS and are unrecognisable
        # by name, so the group must keep setting their primary mission. This is
        # the regression the hosted-payload rule must not cause.
        mission, sector, confidence = build_release.repair_mission_from_groups(
            "other", "unknown", "low", ["gnss"])
        self.assertEqual(mission, "navigation")
        self.assertEqual(confidence, "high")

    def test_withholding_the_group_leaves_the_primary_alone(self):
        # What the catalog does for a hosted payload: the group is removed from
        # the evidence, so an unrecognised comms satellite stays unclassified
        # rather than being called a navigation satellite.
        mission, _sector, _confidence = build_release.repair_mission_from_groups(
            "other", "unknown", "low", [])
        self.assertEqual(mission, "other")

    def test_a_known_primary_was_never_at_risk(self):
        # Belt and braces: the repair is gated on "other" anyway, so a satellite
        # already known to be communications could never have been relabelled.
        mission, _sector, _confidence = build_release.repair_mission_from_groups(
            "communications", "commercial", "high", ["gnss"])
        self.assertEqual(mission, "communications")

    # The 7 of the 13 that no other rule recognised. Withholding the group kept
    # them from being called navigation satellites, but left them reading
    # mission "unknown" beside a navigation secondary -- a card describing only
    # the payload the spacecraft carries for someone else. Sources are cited at
    # the rules in build_release; each states the primary mission and the hosted
    # navigation payload, which is the shape the record already publishes.
    HOSTED_PRIMARIES = (
        ("ASTRA 5B (EGNOS/PRN 123)", "LUX", "commercial", "SES"),
        ("GSAT-8 (GAGAN/PRN 127)", "IND", "civil", "ISRO"),
        ("GSAT-10 (GAGAN/PRN 128)", "IND", "civil", "ISRO"),
        ("GSAT-15 (GAGAN/PRN 129)", "IND", "civil", "ISRO"),
        ("LUCH 5A (SDCM/PRN 140)", "CIS", "civil", "Roscosmos"),
        ("LUCH 5B (SDCM/PRN 125)", "CIS", "civil", "Roscosmos"),
        ("LUCH 5V (SDCM/PRN 141)", "CIS", "civil", "Roscosmos"),
    )

    def test_the_seven_unrecognised_hosts_now_name_their_primary_mission(self):
        for name, country, sector, operator in self.HOSTED_PRIMARIES:
            with self.subTest(name=name):
                mission, got_sector, _constellation, got_operator, confidence, basis = (
                    build_release.classify_detailed(name, country))
                self.assertEqual(mission, "communications")
                self.assertEqual(got_sector, sector)
                self.assertEqual(got_operator, operator)
                # A checked source per operator, so this is a certainty and says so.
                self.assertEqual(confidence, "high")
                self.assertEqual(basis, "exact-name")

    def test_the_hosted_secondary_survives_the_new_primary(self):
        # The whole point of naming the primary: the augmentation payload is
        # still reported, as the secondary it actually is.
        for name, _country, _sector, _operator in self.HOSTED_PRIMARIES:
            with self.subTest(name=name):
                self.assertIsNotNone(build_release.hosted_augmentation_system(name), name)

    def test_the_annotation_is_optional_not_required(self):
        # space-track writes the bare name; CelesTrak adds the "(GAGAN/PRN 127)"
        # annotation. The rule must recognise the spacecraft either way.
        for name in ("ASTRA 5B", "GSAT-8", "GSAT-10", "GSAT-15",
                     "LUCH 5A", "LUCH 5B", "LUCH 5V"):
            with self.subTest(name=name):
                self.assertEqual(build_release.classify(name, "")[0], "communications")

    def test_the_unhyphenated_spelling_the_catalog_actually_uses(self):
        # The catalog is built from space-track's SATCAT, which writes "GSAT 8".
        # A hyphen-only rule matched CelesTrak's group file and not one object on
        # the site: all three still read mission "other" beside their navigation
        # secondary. Measured against the published catalog 2026-08-18.
        for name in ("GSAT 8", "GSAT 10", "GSAT 15"):
            with self.subTest(name=name):
                mission, _sector, _constellation, organization, confidence = (
                    build_release.classify(name, "IND"))
                self.assertEqual(mission, "communications", name)
                self.assertEqual(organization, "ISRO")
                self.assertEqual(confidence, "high")

    def test_the_new_rules_do_not_reach_past_the_spacecraft_they_cite(self):
        # Each source covers named spacecraft, not a family. A sibling with no
        # checked source must stay unclassified rather than inherit the claim.
        for name in ("GSAT-7A", "GSAT-30", "GSAT-1", "LUCH 4", "LUCH 5",
                     "ASTRA 1N", "ASTRA 5A", "ASTRA 5B-2",
                     # The unhyphenated siblings that sit beside the three in the
                     # real catalog, and must not be swept up by the wider rule.
                     "GSAT 6", "GSAT 7", "GSAT 7A", "GSAT 9", "GSAT 11",
                     "GSAT 14", "GSAT 16", "GSAT 18", "GSAT 19", "GSAT 20",
                     "GSAT 29", "GSAT 30", "GSAT 31", "LUCH (OLYMP) 2"):
            with self.subTest(name=name):
                self.assertEqual(build_release.classify(name, "")[0], "other", name)

if __name__ == "__main__":
    unittest.main()


@unittest.skip("direct CelesTrak publisher fallback was removed; covered by compliance tests")
class CelestrakGroupFetchResilienceTests(unittest.TestCase):
    """Guards for the retry storm that got this machine blocked by CelesTrak."""

    def setUp(self):
        self._cache = tempfile.mkdtemp(prefix="celestrak-cache-")
        self._patch = mock.patch.object(build_release, "CACHE", Path(self._cache))
        self._patch.start()
        # These cover the direct-fetch fallback, which only applies when no VPS
        # mirror is present. A real mirror on the developer's box would otherwise
        # short-circuit the code under test.
        self._no_mirror = mock.patch.object(
            build_release, "CELESTRAK_MIRROR", Path(self._cache) / "absent-mirror"
        )
        self._no_mirror.start()
        self.addCleanup(self._no_mirror.stop)
        self._no_spacetrack = mock.patch.object(
            build_release, "SPACETRACK_MIRROR", Path(self._cache) / "absent-spacetrack"
        )
        self._no_spacetrack.start()
        self.addCleanup(self._no_spacetrack.stop)
        self.addCleanup(self._patch.stop)
        self.addCleanup(shutil.rmtree, self._cache, True)

    def test_a_failed_group_is_not_retried_until_the_backoff_expires(self):
        calls = []

        def explode(url, *_args, **_kwargs):
            calls.append(url)
            raise RuntimeError("timed out")

        with mock.patch.object(build_release, "fetch_bytes", side_effect=explode):
            build_release.fetch_celestrak_fleet_memberships()
            first = len(calls)
            self.assertGreater(first, 0)
            build_release.fetch_celestrak_fleet_memberships()
            self.assertEqual(len(calls), first, "a second run re-hammered groups that already failed")

    def test_backoff_still_uses_evidence_already_cached(self):
        group = sorted(set(build_release.CELESTRAK_FLEET_GROUPS) | set(build_release.CELESTRAK_MISSION_CATEGORY_GROUPS))[0]
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=JSON"
        Path(self._cache).mkdir(parents=True, exist_ok=True)
        build_release.cache_path(url).write_bytes(json.dumps([{"NORAD_CAT_ID": 25544}]).encode())
        (Path(self._cache) / f"celestrak-group-{group}-denied").touch()

        with mock.patch.object(build_release, "fetch_bytes", side_effect=RuntimeError("timed out")):
            memberships = build_release.fetch_celestrak_fleet_memberships()

        self.assertIn(25544, memberships, "backing off discarded evidence we already had on disk")
        self.assertIn(group, memberships[25544])

    def test_group_order_rotates_so_the_same_tail_is_not_always_starved(self):
        seen = set()
        for hour in (0, 5, 11):
            calls = []

            def record(url, *_args, **_kwargs):
                calls.append(url)
                raise RuntimeError("timed out")

            shutil.rmtree(self._cache, ignore_errors=True)
            Path(self._cache).mkdir(parents=True, exist_ok=True)
            with mock.patch.object(build_release.time, "time", return_value=hour * 3600.0), \
                 mock.patch.object(build_release, "fetch_bytes", side_effect=record):
                build_release.fetch_celestrak_fleet_memberships()
            self.assertTrue(calls)
            seen.add(calls[0])
        self.assertGreater(len(seen), 1, "the fetch order never rotates; the same groups starve every cycle")


@unittest.skip("environment kill switch replaced by an unconditional no-network boundary")
class CelestrakDisabledTests(unittest.TestCase):
    """The kill switch must silence the network without discarding evidence."""

    def setUp(self):
        self._cache = tempfile.mkdtemp(prefix="celestrak-off-")
        self._patch = mock.patch.object(build_release, "CACHE", Path(self._cache))
        self._patch.start()
        # These cover the direct-fetch fallback, which only applies when no VPS
        # mirror is present. A real mirror on the developer's box would otherwise
        # short-circuit the code under test.
        self._no_mirror = mock.patch.object(
            build_release, "CELESTRAK_MIRROR", Path(self._cache) / "absent-mirror"
        )
        self._no_mirror.start()
        self.addCleanup(self._no_mirror.stop)
        self._no_spacetrack = mock.patch.object(
            build_release, "SPACETRACK_MIRROR", Path(self._cache) / "absent-spacetrack"
        )
        self._no_spacetrack.start()
        self.addCleanup(self._no_spacetrack.stop)
        self.addCleanup(self._patch.stop)
        self.addCleanup(shutil.rmtree, self._cache, True)

    def test_disabled_makes_no_request_but_still_uses_cached_evidence(self):
        group = sorted(
            set(build_release.CELESTRAK_FLEET_GROUPS) | set(build_release.CELESTRAK_MISSION_CATEGORY_GROUPS)
        )[0]
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=JSON"
        Path(self._cache).mkdir(parents=True, exist_ok=True)
        build_release.cache_path(url).write_bytes(json.dumps([{"NORAD_CAT_ID": 25544}]).encode())

        def must_not_be_called(*_args, **_kwargs):
            raise AssertionError("a request was made to a host that has banned us")

        with mock.patch.object(build_release, "CELESTRAK_DISABLED", True), \
             mock.patch.object(build_release, "fetch_bytes", side_effect=must_not_be_called):
            memberships = build_release.fetch_celestrak_fleet_memberships()

        self.assertIn(25544, memberships, "the kill switch threw away evidence already on disk")
        self.assertIn(group, memberships[25544])


class CelestrakMirrorTests(unittest.TestCase):
    """bigmem must read the VPS mirror and never open a connection itself."""

    def setUp(self):
        self._mirror = tempfile.mkdtemp(prefix="celestrak-mirror-")
        self._patch = mock.patch.object(build_release, "CELESTRAK_MIRROR", Path(self._mirror))
        self._patch.start()
        self.addCleanup(self._patch.stop)
        # space-track now takes precedence over the CelesTrak mirror, so these
        # tests must run with no space-track mirror present or they would be
        # exercising the wrong source entirely.
        self._no_spacetrack = mock.patch.object(
            build_release, "SPACETRACK_MIRROR", Path(self._mirror) / "absent-spacetrack"
        )
        self._no_spacetrack.start()
        self.addCleanup(self._no_spacetrack.stop)
        self.addCleanup(shutil.rmtree, self._mirror, True)

    def _write(self, name, records):
        (Path(self._mirror) / name).write_bytes(json.dumps(records).encode())

    def test_catalog_comes_from_the_mirror_without_any_request(self):
        spacetrack = Path(self._mirror) / "absent-spacetrack"
        spacetrack.mkdir(parents=True)
        (spacetrack / "gp-active.json").write_bytes(json.dumps([
            {"NORAD_CAT_ID": 25544, "OBJECT_NAME": "ISS (ZARYA)"}
        ]).encode())
        (spacetrack / "satcat-active.json").write_bytes(json.dumps([
            {"NORAD_CAT_ID": 25544, "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_TYPE": "PAYLOAD"}
        ]).encode())
        self._write("satcat-active.json", [{"NORAD_CAT_ID": 25544, "OBJECT_NAME": "ISS (ZARYA)"}])

        def must_not_be_called(*_args, **_kwargs):
            raise AssertionError("bigmem contacted CelesTrak instead of using the VPS mirror")

        with mock.patch.object(build_release, "fetch_bytes", side_effect=must_not_be_called), \
             mock.patch.object(build_release, "fetch_json", side_effect=must_not_be_called):
            gp, satcat, source, _ = build_release.fetch_celestrak_catalog()

        self.assertEqual(source, "space-track.org (18 SDS)")
        self.assertEqual(len(gp), 1)
        self.assertEqual(len(satcat), 1)

    def test_group_membership_comes_from_the_mirror(self):
        self._write("group-starlink.json", [{"NORAD_CAT_ID": 44713}])

        def must_not_be_called(*_args, **_kwargs):
            raise AssertionError("bigmem contacted CelesTrak for a group list")

        with mock.patch.object(build_release, "fetch_bytes", side_effect=must_not_be_called):
            memberships = build_release.fetch_celestrak_fleet_memberships()

        self.assertIn("starlink", memberships.get(44713, set()))

    def test_absent_mirror_falls_back_rather_than_crashing(self):
        self.assertIsNone(build_release.mirror_records("gp-active.json"))
        self.assertIsNone(build_release.mirror_age_hours("gp-active.json"))


class StationsGroupIsNotAMissionTests(unittest.TestCase):
    """CelesTrak's `stations` group is "at a station", not "is a station".

    Found 2026-08-19 while cross-checking the catalog against SatNOGS. Six live
    cards said "crewed flight or an inhabited orbital facility" about objects
    that were DEPLOYED from the ISS and are still listed in the group weeks
    later: KNACKSAT-2 (a Thai university CubeSat, and SatNOGS records its radio
    in the Amateur service), UITMSAT, LEOPARD, HMU-SAT2, GXIBA-1, DUPLEX.

    It is the COSMIC failure in a different dress -- one coarse signal claiming
    a set of objects it was never about -- so the fix has the same shape: the
    group is withheld from the mission inference and the claim is withdrawn
    rather than replaced by a different guess.
    """

    def test_the_station_modules_still_read_as_human_spaceflight(self):
        # The thing the group is genuinely evidence for. If this regresses the
        # ISS itself stops being crewed spaceflight, which is worse than the bug.
        for name in ("ISS (ZARYA)", "ISS (NAUKA)", "CSS (TIANHE-1)", "CSS (WENTIAN)", "POISK"):
            with self.subTest(name=name):
                self.assertTrue(station_group_is_about_this_object(name))

    def test_the_visiting_vehicles_still_read_as_human_spaceflight(self):
        # Crew and cargo ferries are what the group is for and they change every
        # few months, so they are matched by family rather than enumerated.
        for name in ("PROGRESS MS-33", "SOYUZ MS-29", "DRAGON FREEDOM 3",
                     "CYGNUS NG-24", "TIANZHOU 10", "SZ-23", "SZ-21 MODULE"):
            with self.subTest(name=name):
                self.assertTrue(station_group_is_about_this_object(name))

    def test_a_cubesat_deployed_from_the_station_is_not_a_crewed_vehicle(self):
        # The six real cards. Each one told a reader a university CubeSat
        # carries people.
        for name in ("KNACKSAT-2", "UITMSAT", "LEOPARD", "HMU-SAT2", "GXIBA-1", "DUPLEX"):
            with self.subTest(name=name):
                self.assertFalse(station_group_is_about_this_object(name))

    def test_the_rule_declines_rather_than_asserts(self):
        # False means "we are not going to guess", never "this is a CubeSat".
        # A name rule that ASSERTS is how RIGIDSPHERE 2, a 1971 aluminium radar
        # calibration sphere, shipped as a missile-warning satellite; a name rule
        # that only declines can at worst leave a card saying "unknown".
        self.assertFalse(station_group_is_about_this_object(""))
        self.assertFalse(station_group_is_about_this_object("SOMETHING NOBODY HAS SEEN"))

    def test_the_boundary_is_the_start_of_the_name_not_a_substring(self):
        # "SWISSCUBE" contains "ISS". The 2026-08-07 substring bug made it human
        # spaceflight once already; this rule must not reintroduce it.
        self.assertFalse(station_group_is_about_this_object("SWISSCUBE"))
        self.assertFalse(station_group_is_about_this_object("AISSAT 4"))

    def test_withholding_the_group_leaves_an_honest_unknown(self):
        # A CubeSat whose ONLY group is `stations` ends up with no mission at
        # all, which is the truth. Nothing invents one to fill the gap.
        self.assertEqual(
            repair_mission_from_groups("other", "unknown", "low", []),
            ("other", "unknown", "low"),
        )

    def test_withholding_the_group_lets_a_better_group_decide(self):
        # KNACKSAT-2 carries `amateur` and `cubesat` as well. With `stations`
        # withheld it resolves as an amateur communications satellite, which is
        # what its radio licence says it is.
        self.assertEqual(
            repair_mission_from_groups("other", "unknown", "low", ["amateur", "cubesat"]),
            ("communications", "civil", "high"),
        )


class ParticipationIsNotIdentityTests(unittest.TestCase):
    """Some CelesTrak groups say what a spacecraft TAKES PART IN, not what it is.

    THEMIS A — one of NASA's five magnetospheric physics spacecraft, which fly
    far down the magnetotail to find where a substorm begins — was displayed as
    CIVIL / OTHER SATCOM. Not a name collision: it is in CelesTrak's
    `tdrss` group, and that group lists the relay network's USERS beside the
    eight TDRS relays themselves.

    Measured before this was written, counting only members the site classified
    from evidence the group did NOT give it: `sarsat` asserts communications and
    70 of 70 disagree; `tdrss` asserts communications and 11 of 14 disagree;
    `argos` asserts Earth observation and 2 of 2 disagree. Against that,
    `weather` scores 46 of 48 and `resource` 68 of 70 — those groups really are
    about a kind of spacecraft, and they stay.
    """

    def test_the_withheld_groups_are_the_measured_ones(self):
        # Pinned as a set so adding one is a deliberate act with a reason beside
        # it, and removing one cannot happen by accident.
        self.assertEqual(set(PARTICIPATION_GROUPS), {"tdrss", "sarsat", "argos", "stations"})

    def test_each_withheld_group_says_why_it_is_withheld(self):
        # The table is the argument. An entry with no reason is an assertion.
        for group, reason in PARTICIPATION_GROUPS.items():
            with self.subTest(group=group):
                self.assertGreater(len(reason), 80, f"{group}: give the reason, not a label")

    def test_a_relay_networks_customer_list_sets_no_mission(self):
        # THEMIS A's only group is `tdrss`. Withholding it leaves "other", which
        # is honest; the curated entry then supplies the real answer with NASA
        # cited. What must never happen again is the group asserting comms.
        self.assertEqual(
            repair_mission_from_groups("other", "unknown", "low", []),
            ("other", "unknown", "low"),
        )

    def test_the_groups_that_really_are_about_a_spacecraft_type_still_decide(self):
        # The counter-test. This change must not make the category fallback
        # useless: `weather`, `resource`, `science` and `cubesat` carried 46/48,
        # 68/70, 15/17 and 4/4 of their independent members and are untouched.
        for group, expected in (
            ("weather", ("weather", "civil", "high")),
            ("resource", ("earth-observation", "civil", "medium")),
            ("science", ("science", "civil", "high")),
            ("cubesat", ("technology", "academic", "medium")),
        ):
            with self.subTest(group=group):
                self.assertNotIn(group, PARTICIPATION_GROUPS)
                self.assertEqual(repair_mission_from_groups("other", "unknown", "low", [group]), expected)

    def test_amateur_is_deliberately_not_withheld(self):
        # It scored 0 of 3, which looks identical to `argos` until you read the
        # three: they are CubeSats that happen to carry a ham payload, and an
        # amateur-radio satellite genuinely IS a communications satellite. A
        # purity threshold applied mechanically would have withheld this group
        # and blanked 55 correct cards, which is why the withheld set is a
        # recorded decision and not a computed one.
        self.assertNotIn("amateur", PARTICIPATION_GROUPS)
        self.assertEqual(
            repair_mission_from_groups("other", "unknown", "low", ["amateur"]),
            ("communications", "civil", "high"),
        )

    def test_a_participation_group_never_becomes_a_fleet_either(self):
        # 58 objects were shown in a "fleet" they merely use: Hubble in TDRSS,
        # INSAT 3D in COSPAS-SARSAT, SARAL in ARGOS. The FLEET row on a card is
        # read as "flown together by one operator", which a relay network's
        # customer list is not.
        for group in ("tdrss", "sarsat", "argos"):
            with self.subTest(group=group):
                self.assertIn(group, CELESTRAK_FLEET_GROUPS)
                self.assertIn(group, PARTICIPATION_GROUPS)

    def test_the_real_relays_are_still_communications_by_name(self):
        # Withholding `tdrss` costs nothing for the eight spacecraft the group is
        # actually named after, because they are called TDRS and a name rule
        # reaches them. If that ever stops being true, this names it.
        mission, sector, _constellation, _org, _conf = classify("TDRS 12", "US")
        self.assertEqual(mission, "communications")
