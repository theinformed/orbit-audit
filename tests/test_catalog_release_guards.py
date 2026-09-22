"""Guards on what a catalog release is allowed to change, and on where fleet
evidence may be recovered from when the mirror empties.

Both exist because of the same day. On 2026-08-07 the CelesTrak fetch moved to
the VPS, the bigmem-side rsync overwrote the fuller local group cache with the
VPS's near-empty one, and 4,802 objects lost their fleet label between two
builds two hours apart -- with nothing printed, nothing failing, and nobody
told. Nothing had changed in orbit.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import build_release

ROOT = Path(build_release.__file__).resolve().parent.parent


def catalog(objects, upstream="2026-08-07T14:00:00"):
    return {"schema": 1, "upstreamAsOf": upstream, "satellites": objects}


def record(norad, **overrides):
    base = {
        "id": norad,
        "name": f"OBJECT {norad}",
        "mission": "communications",
        "sector": "commercial",
        "constellation": "Starlink",
        "organization": "SpaceX",
        "purpose": "a description",
        "sourceGroups": ["starlink"],
    }
    base.update(overrides)
    return base


def write_release(root: Path, release: str, objects, name="manifest.json"):
    artifact_dir = root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    relative = f"artifacts/catalog-{release}.json"
    (root / relative).write_text(json.dumps(catalog(objects)))
    manifest = {"release": release, "catalog": {"path": relative, "sha256": "0" * 64}}
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest))
    return manifest


class SourceGroupRecoveryTests(unittest.TestCase):
    def test_the_richest_recent_release_wins_not_merely_the_newest(self):
        """The newest release inherits the emptiness that caused the problem."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_release(root, "20260807T180000Z",
                          [record(i) for i in range(100)],
                          name="manifests/manifest-20260807T180000Z.json")
            write_release(root, "20260807T210000Z",
                          [record(i, sourceGroups=[] if i else ["starlink"]) for i in range(100)])
            recovered, as_of = build_release.recoverable_source_groups(
                root, now=dt.datetime(2026, 8, 7, 22, tzinfo=dt.timezone.utc)
            )
            self.assertEqual(len(recovered), 100)
            self.assertEqual(as_of, "2026-08-07T18:00:00Z")

    def test_recovery_carries_the_true_source_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_release(root, "20260801T120000Z", [record(1)])
            _, as_of = build_release.recoverable_source_groups(
                root, now=dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc)
            )
            self.assertEqual(as_of, "2026-08-01T12:00:00Z")

    def test_evidence_older_than_the_carry_forward_window_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_release(root, "20260601T120000Z", [record(1)])
            recovered, as_of = build_release.recoverable_source_groups(
                root, now=dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc)
            )
            self.assertEqual(recovered, {})
            self.assertIsNone(as_of)

    def test_a_missing_artifact_is_skipped_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_release(root, "20260807T180000Z", [record(1)])
            (root / "artifacts" / "catalog-20260807T180000Z.json").unlink()
            recovered, _ = build_release.recoverable_source_groups(
                root, now=dt.datetime(2026, 8, 7, 20, tzinfo=dt.timezone.utc)
            )
            self.assertEqual(recovered, {})

    def test_an_empty_tree_recovers_nothing_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_release.recoverable_source_groups(Path(tmp)), ({}, None))


class CatalogDriftTests(unittest.TestCase):
    def test_drift_counts_only_objects_present_in_both_releases(self):
        before = catalog([record(1), record(2)])
        after = [record(1), record(3)]
        drift = build_release.catalog_drift(before, after)
        self.assertEqual(drift["comparable"], 1)

    def test_a_changed_mission_is_counted_and_shown(self):
        before = catalog([record(1)])
        after = [record(1, mission="earth-observation")]
        drift = build_release.catalog_drift(before, after)
        self.assertEqual(drift["changed"]["mission"], 1)
        self.assertIn("mission", drift["examples"][0])

    def test_a_large_silent_rewrite_stops_the_build(self):
        before = catalog([record(i) for i in range(1000)])
        after = [record(i, purpose="rewritten") for i in range(1000)]
        with self.assertRaises(RuntimeError) as raised:
            build_release.report_catalog_drift(before, after)
        self.assertIn("SPACE_EXPLORER_ALLOW_CATALOG_DRIFT", str(raised.exception))

    def test_a_small_change_publishes_without_ceremony(self):
        before = catalog([record(i) for i in range(1000)])
        after = [record(i, purpose="rewritten" if i < 3 else "a description") for i in range(1000)]
        drift = build_release.report_catalog_drift(before, after)
        self.assertEqual(drift["changed"]["purpose"], 3)

    def test_a_first_build_with_no_predecessor_is_not_blocked(self):
        self.assertEqual(build_release.report_catalog_drift(None, [record(1)])["comparable"], 0)

    def test_the_gate_can_be_acknowledged_for_an_intended_taxonomy_change(self):
        before = catalog([record(i) for i in range(1000)])
        after = [record(i, mission="other") for i in range(1000)]
        original = build_release.CATALOG_DRIFT_ALLOWED
        try:
            build_release.CATALOG_DRIFT_ALLOWED = True
            drift = build_release.report_catalog_drift(before, after)
        finally:
            build_release.CATALOG_DRIFT_ALLOWED = original
        self.assertEqual(drift["changed"]["mission"], 1000)


#: Real rows from the shipped catalog, so these tests exercise the values the
#: generator actually meets rather than invented ones. The defect was reported
#: against specific cards; these are three of them.
REAL_ROWS = {
    # TIANMU-1 11: a CelesTrak `weather` category label, no published payload.
    58645: dict(
        name="TIANMU-1 11", mission="weather", sector="civil", orbit="LEO", basis="source-group",
        registry=dict(perigeeKm=476.1, apogeeKm=490.1, periodMinutes=94.269,
                      launchDate="2023-12-25", launchGroup="2023-205",
                      ownerLabel="People's Republic of China"),
    ),
    # USA 115: nothing established at all, and a near-circular GEO.
    23712: dict(
        name="USA 115", mission="other", sector="unknown", orbit="GEO", basis="unclassified",
        registry=dict(perigeeKm=35760.0, apogeeKm=35814.0, periodMinutes=1436.1,
                      launchDate="1995-11-06", launchGroup="1995-060",
                      ownerLabel="United States"),
    ),
    # OSCAR 10: a wildly eccentric orbit, where one altitude would be a lie.
    14129: dict(
        name="OSCAR 10", mission="communications", sector="unknown", orbit="HEO", basis="source-group",
        registry=dict(perigeeKm=4086.0, apogeeKm=35362.0, periodMinutes=699.5,
                      launchDate="1983-06-16", launchGroup="1983-058",
                      ownerLabel="Germany"),
    ),
}

#: The two openings this generator used to emit. 2,383 of 8,000 cards opened
#: with one of them, and both read as a card with no information on it:
#: nineteen and thirty-eight words respectively before the first fact.
RETIRED_OPENINGS = (
    "The public catalog does not identify this spacecraft's payload or mission,",
    "Its purpose has not been independently verified for this object:",
)


class HonestDescriptionTests(unittest.TestCase):
    def test_an_unknown_leo_object_is_told_what_KIND_of_thing_it_is(self):
        """The whole change of 2026-08-20, in one assertion.

        The previous generator answered "what is this" with the orbit, which is
        the row directly above the description in the Details grid. What a
        reader cannot get from that grid is the class: a small satellite, one of
        a crowd, flown by somebody who publishes nothing, unable to manoeuvre.
        """
        text = build_release.template_purpose("RIGIDSPHERE 2", "other", "unknown", "LEO")
        self.assertTrue(text.startswith("No public source names this spacecraft's payload"))
        self.assertIn("Small satellites in this band", text)
        self.assertIn("cannot be the one that moves", text)

    def test_a_crowded_launch_is_named_as_a_rideshare_and_a_quiet_one_is_not(self):
        """The one number in this text that is per-object, and it is derived.

        `identify_launch_group` plus a count of PAYLOAD rows says how many
        spacecraft the registry still lists from the same flight. A hundred is a
        rideshare and worth telling a reader about; two is a dedicated launch
        and the word would be wrong.
        """
        crowded = build_release.template_purpose(
            "CUBY 1", "other", "unknown", "LEO", "unclassified", None, cohort_payloads=110)
        self.assertIn("one of 110 payloads the registry lists from a single launch", crowded)
        self.assertIn("rideshare", crowded)
        alone = build_release.template_purpose(
            "GMS-T", "other", "unknown", "LEO", "unclassified", None, cohort_payloads=2)
        self.assertNotIn("rideshare", alone)
        self.assertNotIn("payloads the registry lists", alone)
        # ...and the boundary is a declared constant rather than a literal
        # buried in a branch, so moving it moves this test with it.
        edge = build_release.template_purpose(
            "X", "other", "unknown", "LEO", "unclassified", None,
            cohort_payloads=build_release.RIDESHARE_COHORT_PAYLOADS)
        self.assertIn("rideshare", edge)

    def test_a_launch_cohort_is_counted_over_payloads_only(self):
        """A Falcon upper stage and eighty pieces of debris are not passengers."""
        rows = [
            {"OBJECT_ID": "2026-156A", "OBJECT_TYPE": "PAYLOAD"},
            {"OBJECT_ID": "2026-156B", "OBJECT_TYPE": "PAYLOAD"},
            {"OBJECT_ID": "2026-156C", "OBJECT_TYPE": "ROCKET BODY"},
            {"OBJECT_ID": "2026-156D", "OBJECT_TYPE": "DEBRIS"},
            {"OBJECT_ID": "2020-001A", "OBJECT_TYPE": "PAYLOAD"},
            {"OBJECT_ID": "", "OBJECT_TYPE": "PAYLOAD"},
        ]
        counts = build_release.launch_cohort_payloads(rows)
        self.assertEqual(counts["2026-156"], 2)
        self.assertEqual(counts["2020-001"], 1)

    def test_no_description_opens_with_either_retired_apology(self):
        """The negative assertion, because this file has a history of rules that

        matched nothing and were believed anyway (`SES-`, `EUTE`, and a
        `^GSAT-(?:8|10|15)` that never fired because the catalog writes
        `GSAT 8`). A test that only checks the new shape would pass just as
        happily if the old branch were still reachable.
        """
        for norad, row in REAL_ROWS.items():
            text = build_release.template_purpose(
                row["name"], row["mission"], row["sector"], row["orbit"], row["basis"], row["registry"],
            )
            with self.subTest(norad=norad):
                for opening in RETIRED_OPENINGS:
                    self.assertNotIn(opening, text)
                self.assertTrue(text.startswith("No public source names this spacecraft's payload"))

    def test_the_description_never_restates_the_details_grid(self):
        """INVERTED on 2026-08-20, and the inversion is the point.

        This test used to assert that the generated description contained the
        altitude, the period, the launch date, the launch group and the
        registering state. It did, faithfully -- and every one of those is a row
        in the Satellite Details grid on the same screen, which is precisely the
        filler the standing rule forbids. A test that pins filler in place is
        worse than no test, because it makes removing the filler look like a
        regression. So it now pins the opposite, on the same real card.
        """
        row = REAL_ROWS[58645]
        # EVERY branch, on the same real card. Checking one of them is how a
        # guard like this goes quietly blind: the first version of this test
        # exercised only the small-satellite branch and did not notice the
        # registry read-out being put back into the rideshare one.
        for cohort in (None, 3, build_release.RIDESHARE_COHORT_PAYLOADS, 110):
            text = build_release.template_purpose(
                row["name"], row["mission"], row["sector"], row["orbit"], row["basis"],
                row["registry"], cohort_payloads=cohort,
            )
            for grid_value in ("483 km", "476", "490", "94.3", "94.2", "2023-12-25", "2023-205",
                               "People's Republic of China", "registered to", "TIANMU"):
                with self.subTest(cohort=cohort, grid_value=grid_value):
                    self.assertNotIn(grid_value, text)
        # ...and the regimes that take the floor branch state no numbers either.
        for norad in (23712, 14129):
            other = REAL_ROWS[norad]
            text = build_release.template_purpose(
                other["name"], other["mission"], other["sector"], other["orbit"],
                other["basis"], other["registry"],
            )
            with self.subTest(norad=norad):
                self.assertNotIn("km up", text)
                self.assertNotIn("registered to", text)
                self.assertNotIn("launch group", text)

    def test_the_clause_that_rendered_the_grid_into_prose_is_gone(self):
        """The executable half of the retirement note below.

        `registry_owner_clause` and `registry_facts_clause` formatted "about 976
        km up on a 104.6-minute period, launched 1964-10-06 in launch group
        1964-063, registered to the United States" -- five values, every one of
        them already a row in the Satellite Details grid on the same screen. A
        dormant helper is how this came back the second time, so the assertion
        is that the pipeline can no longer render the grid into a sentence at
        all, not merely that it currently does not.
        """
        for retired in ("registry_owner_clause", "registry_facts_clause"):
            self.assertFalse(hasattr(build_release, retired), retired)
        # String LITERALS, via the AST, not raw source: the tombstones that
        # replaced this code quote the sentence in a comment, and a comment
        # saying "never write this again" is the opposite of the defect. Only
        # text the pipeline can actually emit counts.
        tree = ast.parse(Path(build_release.__file__).read_text())
        literals = [node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        for shape in ("registry record", "km up", "launch group ", "registered to"):
            for literal in literals:
                self.assertNotIn(shape, literal, shape)

    def test_no_shipped_override_carries_the_retired_append_flag(self):
        """The real tables, not a fixture.

        `appendRegistryFacts` was an opt-in flag on an override entry, and it
        was set on 627 of them across the `_us` and `_cn` partitions, which put
        the registry read-out on 1,205 published cards -- 553 of them
        researched, curated prose it padded from behind. The flag is retired,
        and `validate_overrides` REFUSES it rather than ignoring it: a flag that
        is silently ignored comes back the moment somebody copies an old entry
        as a template, which is exactly how it came back the second time.
        """
        for path in sorted((ROOT / "data").glob("satellite_overrides*.json")):
            with self.subTest(path=path.name):
                self.assertNotIn("appendRegistryFacts", path.read_text())
        with self.assertRaises(ValueError) as raised:
            build_release.validate_overrides(
                {"@test/x/1": {"match": "norad", "norad": [1], "purpose": "A spacecraft.",
                               "source": "https://example.gov/x", "individual": True,
                               "appendRegistryFacts": True}},
            )
        self.assertIn("appendRegistryFacts", str(raised.exception))
        # ...and refused even where it was previously a no-op -- no `purpose` to
        # extend, flag set false -- so it cannot sit dormant in a table.
        with self.assertRaises(ValueError):
            build_release.validate_overrides(
                {"@test/x/1": {"match": "norad", "norad": [1], "appendRegistryFacts": False}},
            )

    def test_a_curated_override_is_published_exactly_as_written(self):
        """The end-to-end half, through `build_catalog` and the real tables.

        The guard above covered only the GENERATED description, which is
        precisely why the override path slipped past it: the read-out was
        removed from the fallback and came straight back through a flag, on ten
        times as many cards. So this drives the real override branch on real
        curated entries and asserts the published `purpose` is the curator's own
        text, character for character, plus nothing.

        An equality assertion rather than a list of forbidden substrings, on
        purpose: any appended sentence fails it, including one nobody has
        thought of yet.
        """
        curated = {
            norad: entry for norad, entry in self._norad_overrides().items()
            if entry.get("purpose") and not entry.get("shells")
            # A declared shell and a contested attribution both extend a
            # description on purpose, each from this object's own record: the
            # shell from its measured elements, the caveat from two named
            # analysts with a citation each. Both are content a reader is owed
            # and neither restates the grid, so they are excluded from the
            # character-for-character comparison rather than banned by it.
            and not entry.get("contestedAttribution")
        }
        self.assertGreater(len(curated), 50, "the curated tables have gone missing")
        sample = dict(sorted(curated.items())[:40])
        built = self._build_with(sample)
        self.assertEqual(set(built), set(sample))
        for norad, entry in sample.items():
            with self.subTest(norad=norad):
                self.assertEqual(built[norad]["purpose"], entry["purpose"])

    def test_no_published_description_restates_the_grid(self):
        """The sweep, over every object a real build produces.

        The equality test above proves the curated entries are untouched. This
        covers everything else the build can emit -- generated fallbacks, class
        descriptions, shell clauses -- against both the shapes the read-out used
        and this object's own grid values. It is the assertion that would have
        caught all three appearances of this defect.
        """
        sample = dict(sorted(self._norad_overrides().items())[:60])
        built = self._build_with(sample)
        self.assertTrue(built)
        for norad, record in built.items():
            purpose = record["purpose"]
            with self.subTest(norad=norad):
                for shape in ("registry record", " km up", "launch group",
                              "registered to", "-minute period"):
                    self.assertNotIn(shape, purpose, shape)
                # ...and this object's own grid values, which the forbidden
                # shapes above are only a proxy for.
                for value in (self.LAUNCH_DATE, self.LAUNCH_GROUP):
                    self.assertNotIn(value, purpose, value)

    # -- the harness the two tests above share ------------------------------

    #: Deliberately unlike any real orbit, so a grid value leaking into prose is
    #: unmistakable rather than a plausible number that happened to match.
    SYNTHETIC = dict(MEAN_MOTION="8.55501000", ECCENTRICITY="0.0004000",
                     INCLINATION="63.4321", EPOCH="2026-08-20T00:00:00",
                     RA_OF_ASC_NODE="12.3456", ARG_OF_PERICENTER="98.7654",
                     MEAN_ANOMALY="261.2345")
    LAUNCH_DATE = "1999-07-13"
    LAUNCH_GROUP = "1999-042"

    def _norad_overrides(self):
        """Every curated entry keyed on a catalog number, from the real tables."""
        found = {}
        for key, entry in build_release.load_overrides().items():
            tail = key.rsplit("/", 1)[-1]
            if entry.get("match") == "norad" and tail.isdigit():
                found[int(tail)] = entry
        return found

    def _build_with(self, wanted):
        """Run the real `build_catalog` over synthesised elements for `wanted`.

        No network: `fetch_celestrak_catalog` is the single upstream call and it
        is replaced here. CelesTrak may only be reached from the VPS, so a test
        that needed it would simply not run where this code is written.
        """
        ids = sorted(wanted)
        # The row-count floor in `build_catalog` is a real guard against a
        # truncated upstream, so the fixture clears it with filler that matches
        # no override rather than by lowering the bar.
        filler = [n for n in range(900000, 902000) if n not in set(ids)][:1200]
        gp, satcat = [], []
        for norad in ids + filler:
            gp.append({"NORAD_CAT_ID": str(norad), "OBJECT_NAME": f"FIXTURE {norad}",
                       "OBJECT_ID": f"{self.LAUNCH_GROUP}A", **self.SYNTHETIC})
            satcat.append({"NORAD_CAT_ID": str(norad), "OBJECT_NAME": f"FIXTURE {norad}",
                           "OWNER": "US", "LAUNCH_DATE": self.LAUNCH_DATE})
        original = build_release.fetch_celestrak_catalog
        build_release.fetch_celestrak_catalog = lambda: (gp, satcat, "fixture", {})
        try:
            catalog = build_release.build_catalog(len(gp))
        finally:
            build_release.fetch_celestrak_catalog = original
        return {record["id"]: record for record in catalog["satellites"]
                if record["id"] in set(ids)}

    # RETIRED 2026-08-20, in the same change that deleted what they tested.
    #
    # Three tests lived here: how an eccentric orbit was phrased against a
    # circular one, when "registered to" takes a definite article, and what an
    # unattributed owner did to the sentence. All three exercised
    # `registry_facts_clause` and `registry_owner_clause`, which formatted
    # "This object's registry record: about 976 km up on a 104.6-minute period,
    # launched 1964-10-06 in launch group 1964-063, registered to the United
    # States." Those functions are GONE -- the sentence restated the Satellite
    # Details grid, it had already been removed once and came back through a
    # dormant override flag, and the third time it was deleted at the root.
    #
    # They are deleted rather than repaired because there is no longer any code
    # path that renders a registry clause into prose. A test kept alive for
    # removed behaviour is an invitation to restore the behaviour, and this
    # particular defect has now been removed three times.
    #
    # The VALUES are untouched and still tested where they belong: perigeeKm,
    # apogeeKm, periodMinutes, launchDate, launchGroup and ownerLabel ship on
    # every catalog record and the card draws them in the grid. What must never
    # come back is prose that repeats them, and THAT is pinned by
    # `test_the_description_never_restates_the_details_grid` above -- which
    # checks every branch of the generator for exactly these values.

    def test_two_objects_in_different_regimes_do_not_share_a_description(self):
        """Repetition WITHIN a class is now deliberate, and across one is not.

        Fifty cards saying the same true thing about rideshare passengers is the
        point of a class description, so `catalog_audit.boilerplate_ranking`
        will rank these together and should. What must never collapse is the
        line between regimes: a low-orbit passenger, a geostationary object and
        a Molniya are three different animals and cannot inherit one paragraph.
        """
        texts = {build_release.template_purpose(**row) for row in REAL_ROWS.values()}
        self.assertEqual(len(texts), len(REAL_ROWS))

    def test_a_row_with_no_registry_facts_still_gets_the_orbit(self):
        text = build_release.template_purpose("X", "other", "unknown", "MEO")
        self.assertIn("medium Earth orbit", text)
        self.assertNotIn("—", text)

    def test_no_template_description_names_an_agency_or_an_instrument(self):
        for mission in ("other", "weather", "communications", "earth-observation", "science"):
            for orbit in ("LEO", "MEO", "GEO", "IGSO", "HEO", "OTHER"):
                text = build_release.template_purpose("X", mission, "civil", orbit)
                with self.subTest(mission=mission, orbit=orbit):
                    for forbidden in ("NASA", "NOAA", "ESA", "JAXA", "instrument", "sensor"):
                        self.assertNotIn(forbidden, text)




class OverrideClassificationTests(unittest.TestCase):
    """What an override match may claim about the mission label.

    These construct the case rather than reading the shipped catalog. The
    invariants below DO read it, and when they were first written both of them
    passed against every sabotage -- because the single object that had ever
    violated the rule (SMAP) had just been given a description, so there was
    nothing left for them to catch. An invariant with no instance is not a
    test, it is a comment that runs.
    """

    def test_an_operator_only_entry_does_not_promote_the_chip(self):
        """The live defect: SMAP, catalogue 40376, operator NASA, no mission.

        Matching the OBJECT by catalogue number is exact. It establishes
        nothing about the MISSION, which is what the chip reports.
        """
        basis, confidence = build_release.override_classification(
            {"match": "norad", "norad": [40376], "organization": "NASA",
             "source": "https://smap.jpl.nasa.gov/"},
            "norad", "unclassified", "low",
        )
        self.assertEqual((basis, confidence), ("unclassified", "low"))

    def test_an_entry_that_states_a_mission_does_promote_it(self):
        """...and the negative control, which is the half that would rot."""
        basis, confidence = build_release.override_classification(
            {"match": "norad", "mission": "earth-observation"}, "norad", "unclassified", "low",
        )
        self.assertEqual((basis, confidence), ("norad-id", "high"))

    def test_a_described_entry_promotes_even_without_a_mission_field(self):
        """A written, cited paragraph IS the mission claim."""
        basis, confidence = build_release.override_classification(
            {"match": "exact", "purpose": "A radar imaging satellite.",
             "source": "https://example.org/"}, "exact", "name-pattern", "medium",
        )
        self.assertEqual((basis, confidence), ("exact-name", "high"))

    def test_a_family_match_is_never_graded_as_high_as_a_catalogue_number(self):
        for kind, expected in (("prefix", "medium"), ("token", "medium")):
            with self.subTest(match=kind):
                _, confidence = build_release.override_classification(
                    {"mission": "communications"}, kind, "unclassified", "low")
                self.assertEqual(confidence, expected)


class ShippedCatalogInvariantTests(unittest.TestCase):
    """Rules that can only be checked against what actually shipped.

    Both of these are properties of the whole release rather than of one
    function, and both have already been violated once by code that passed
    every unit test in this file.
    """

    def setUp(self):
        data_root = ROOT / "public" / "data"
        manifest = data_root / "manifest.json"
        if not manifest.is_file():
            self.skipTest("no published release on this machine")
        record = json.loads(manifest.read_text()).get("catalog") or {}
        path = data_root / str(record.get("path", ""))
        if not path.is_file():
            self.skipTest("published manifest names a catalog artifact that is not on disk")
        self.satellites = json.loads(path.read_text())["satellites"]

    def test_no_class_described_card_draws_a_corroborated_chip(self):
        """The card must never look more certain than its own sentence.

        `purposeKind: "class"` means the description is this site's own account
        of what KIND of object this is -- it names no source and claims no
        mission. A corroborated basis puts a SOLID, confident chip above that
        sentence, which is the Tianmu-1 11 contradiction in a new place.

        It was live: an override carrying nothing but an operator attribution
        promoted the basis to "norad-id" at "high", because the entry matched
        the object by catalogue number. Matching the OBJECT is certain; it says
        nothing about the MISSION, which is what the chip reports. SMAP shipped
        that way -- `norad-id` and `high` beside "No public source names this
        spacecraft's payload".
        """
        # The interface's own rule, restated here rather than imported, because
        # it lives in TypeScript: a chip is corroborated when the basis is one
        # of these AND the confidence is not "low".
        corroborated = {"web-corroborated", "norad-id", "exact-name", "radio-licence"}
        offenders = [
            (record["name"], record["classificationBasis"], record["classificationConfidence"])
            for record in self.satellites
            if record.get("purposeKind") == "class"
            and record.get("classificationBasis") in corroborated
            and str(record.get("classificationConfidence", "")).lower() != "low"
        ]
        self.assertEqual(offenders, [], "class-described cards drawing a corroborated chip")

    def test_no_class_described_card_carries_a_source_link(self):
        """A "Source" link under "no public source names this payload" reads as

        a contradiction the reader is right to distrust, and it was live too:
        an operator-only override lends its own URL to the description slot, so
        SMAP hung a link to smap.jpl.nasa.gov beneath exactly that sentence.
        """
        offenders = [
            record["name"] for record in self.satellites
            if record.get("purposeKind") == "class" and record.get("purposeSource")
        ]
        self.assertEqual(offenders, [], "class-described cards carrying a citation")

    def test_the_registry_read_out_is_gone_from_every_shipped_description(self):
        """Removed three times now. The third removal deleted the functions."""
        offenders = [
            record["name"] for record in self.satellites
            if "This object's registry record:" in (record.get("purpose") or "")
        ]
        self.assertEqual(offenders[:5], [], f"{len(offenders)} cards still restate the Details grid")


class TaxonomyAcknowledgementTests(unittest.TestCase):
    """A deliberate taxonomy change must publish; an accidental one must not."""

    def test_a_bumped_taxonomy_version_is_the_acknowledgement(self):
        before = catalog([record(i) for i in range(1000)])
        before["taxonomyVersion"] = "2026-08-07.1"
        after = [record(i, mission="other") for i in range(1000)]
        drift = build_release.report_catalog_drift(before, after, "2026-08-07.4")
        self.assertEqual(drift["changed"]["mission"], 1000)

    def test_the_same_taxonomy_version_still_stops_a_silent_rewrite(self):
        before = catalog([record(i) for i in range(1000)])
        before["taxonomyVersion"] = "2026-08-07.4"
        after = [record(i, mission="other") for i in range(1000)]
        with self.assertRaises(RuntimeError):
            build_release.report_catalog_drift(before, after, "2026-08-07.4")

    def test_the_shipped_version_matches_what_the_builder_publishes(self):
        # 2026-08-19.1 is the SatNOGS cross-check wave: `classificationBasis`
        # gains "withdrawn-name-collision" and "radio-licence"; the template
        # description names the evidence it actually rests on instead of saying
        # "programme-name pattern" for every object alike, which was wrong on 356
        # of the 568 cards carrying it; and CelesTrak's `stations` group stops
        # implying crewed spaceflight for payloads merely deployed FROM a
        # station. 65 objects changed mission and 421 changed description.
        # Bumping this line is the acknowledgement the drift gate asks for.
        # .2, same day: THEMIS A was showing as CIVIL / OTHER SATCOM because it is in
        # CelesTrak's `tdrss` group, which lists a relay network's USERS. The four
        # participation groups now set neither mission nor fleet.
        # .3, same day: the web fact-check lane adds "web-corroborated". US
        # military spacecraft are catalogued as "USA nnn", so the classifier's
        # DSCS rule matched a string no catalogue entry contains and 19 objects
        # sat with no mission at all. Four now carry a programme identity backed
        # by independent published sources quoted against their catalogue number.
        # 2026-08-20.1: non-US military communications. MILSATCOM returned 101
        # objects, 93 of them American and none Chinese or Russian, because the
        # rules were written against American naming: Shentong-2 is catalogued
        # as "CHINASAT 2A" and Blagovest as "COSMOS 2520". `classificationBasis`
        # gains "assessed", so an analyst's reading can be published without
        # being dressed as an operator fact sheet. 19 objects joined MILSATCOM
        # and 25 joined OTHER MILITARY.
        # 2026-08-20.3: the China partition. 686 Chinese-operated objects carried no
        # description at all -- 186 Guowang, 63 GeeSAT, 28 Tianqi, 20 Tianmu and
        # a long tail -- against the stated goal of a paragraph or two on nearly
        # every satellite in the catalog. They now
        # carry researched, cited family prose plus a per-object clause read off
        # their own elements. `evidence: "assessed"` is used where the mission is
        # an outside analyst's reading rather than a Chinese statement: Yunhai
        # and Tianhui (the WMO's own OSCAR database records both as operated for
        # the PLA), LKW, Shiyan-12 and SJ-17. `mission`, `sector` and
        # `organization` move on those objects, which is most of this drift.
        # 2026-08-20.4 and .5: the United States partition, landed in two tranches.
        # 521 US-operated objects carried no description -- among them all 39 GPS
        # satellites, which the site loads as its featured default and which
        # space-track files under the programme's own NAVSTAR designation, so the
        # shared table's `NAVSTAR` prefix rule carried an operator and no mission
        # at all. 332 objects now carry a per-spacecraft description keyed on the
        # catalogue number: GPS with its block, flight, space vehicle number and
        # plane/slot; SDA Tranche 0, which turned out to be what the WILDFIRE,
        # CHECKMATE, BB and RAPTOR catalogue names conceal; the METOC instruments
        # (WSF-M, Coriolis/WindSat, PlanetiQ radio occultation, Tomorrow.io's
        # sounders); the space-environment missions this site teaches (PUNCH,
        # TRACERS, EZIE, DSX); and the USA-designator series, where the programme
        # behind the number is an outside analyst's reading and is published as
        # `evidence: "assessed"` at medium, twice with a contestedAttribution
        # because Krebs and McDowell name different spacecraft.
        # .6, same day: the drift gate did exactly what it is for. Four partition
        # tables were landing within the same hour, and a build that carried
        # 350 changed descriptions was refused because the acknowledgement it
        # compared against had already been spent by the previous partition's
        # build. One bump releases all of them; the gate stays a gate.
        # .7: the rest of the United States partition -- the commercial
        # geostationary fleets (EchoStar, DirecTV, Galaxy, SiriusXM, Viasat, and
        # the two former GOES satellites now flown by the Space Force as EWS-G),
        # plus the long tail of rideshare smallsats and orbital transfer
        # vehicles. 519 of the partition's 521 undescribed objects now carry a
        # per-spacecraft description; the two that do not are recorded as
        # unresolved rather than guessed.
        # .8: 1,218 objects, and almost all of it is a DELETION. The override
        # flag `appendRegistryFacts` appended "This object's registry record:
        # about 976 km up on a 104.6-minute period, launched 1964-10-06 in launch
        # group 1964-063, registered to the United States." to 1,205 published
        # descriptions, 553 of them researched curated prose that it padded from
        # behind. Every fact in that sentence is already a row in the Satellite
        # Details grid on the same screen. The flag is retired, the two functions
        # that rendered it are deleted, and an override still carrying the flag
        # now fails the build with the reason -- this was the THIRD appearance of
        # the same defect and the first two were fixed by removing a caller.
        # The remaining 13 are the first tranche of the SatNOGS lane's
        # undescribed objects, which had nothing to say about themselves but
        # which ITU service their transmitters were filed under.
        # .9: the operator's country. The card's country came from space-track's
        # SATCAT `COUNTRY` column, which is the state the object is ATTRIBUTED to
        # in the registry -- and for a rideshare smallsat that is routinely
        # whoever filed the paperwork, which tracks the BUILDER: IdeiaSpace ->
        # BRAZ, ISISPACE -> NETH, OHB Sweden -> SWED, ZfT -> GER, U-Space -> FR,
        # EnduroSat -> BGR. Live, that made SARI-1 and SARI-2 (Saudi) Brazilian,
        # LEONAV-1 (UAE) French, CLOUDCT-PRECURSOR (Technion) German. The
        # registry fact is NOT overwritten; Jonathan McDowell's GCAT supplies the
        # operator's country as a second, separately sourced field, and where the
        # two differ the card shows both, labelled. `organization` is replaced
        # only where the site was passing the registering state off AS the
        # operator, which was 12 objects.
        # .10: and nothing is read off a catalog number the two catalogues do not
        # agree about. GCAT records 55045 as the Satellogic imager NuSat-34 with
        # a Uruguayan operator; the registry and CelesTrak both record it as
        # CONTINUUM-1, Australian. 34 objects lose an operator country they
        # should never have been given, `operatorState` joins the drift gate's
        # watched fields, and the release counts the refusals in
        # `operatorStateEvidence.identityDisputedObjects` so the silence is a
        # labelled gap rather than an absence.
        # 2026-08-27.1: cohort corroboration. The question-marked chip on
        # STARLINK-11600 read as noise rather than as a caveat. 6,288 of 8,000
        # cards rested on `name-pattern` and drew the dashed, dimmed,
        # question-marked chip, so a mark built to warn about Tianmu-1 11 was
        # firing on four fifths of the catalog and had stopped carrying
        # information. The 18th Space Defense Squadron's naming within a launch
        # really is provisional -- LitSat-1 and LituanicaSat-1 were transposed
        # until Doppler measurements settled it -- so the scepticism was right
        # about IDENTITY and wrong about the MISSION CLASS, which is what the
        # chip states and which survives a transposition. A new published field
        # `missionCorroboration` records that an object's own fleet agrees with
        # it on owner, on mission and on launching in batches, with nothing
        # independent disputing any member; 8 constellations qualify and 5,099
        # objects carry it. `classificationBasis` is UNCHANGED on every object,
        # which is what this bump acknowledges: the drift gate watches the
        # published record, and a new field beside an unchanged one is still a
        # change in what the card tells a reader.
        self.assertEqual(build_release.TAXONOMY_VERSION, "2026-08-27.1")




class AttributionAnnotationTests(unittest.TestCase):
    """A claim, a competing signal, both attributed, no forced resolution.

    The first design withdrew a name-pattern mission that the object's own orbit
    contradicted. That was rejected: the disagreement is the most interesting
    thing in the record and teaches the site's own method -- that an orbit
    constrains what a spacecraft can be for -- by showing it disagreeing with a
    label. So the claim stands and the conflict is published beside it.
    """

    def _orbit(self, period, perigee, apogee, regime):
        return {"periodMinutes": period, "perigeeKm": perigee, "apogeeKm": apogee, "orbit": regime}

    def test_a_medium_orbit_imaging_claim_is_annotated_with_its_numbers(self):
        note = build_release.regime_conflict_note(
            "YAOGAN 45", "earth-observation", "name-pattern",
            self._orbit(271.08, 20000.0, 20200.0, "MEO"), 19.93,
        )
        self.assertIsNotNone(note)
        self.assertEqual(note["kind"], "orbit-inconsistent")
        self.assertEqual(note["claim"]["value"], "Earth observation")
        # The numbers must be in the annotation; that is what makes it evidence.
        for fragment in ("271-minute", "20°", "medium Earth orbit"):
            self.assertIn(fragment, note["counter"]["value"])
        self.assertIn("rather than resolving it", note["position"])

    def test_the_claim_itself_is_not_withdrawn(self):
        """Annotating, not resolving. The label survives the annotation."""
        note = build_release.regime_conflict_note(
            "YAOGAN-41", "earth-observation", "name-pattern",
            self._orbit(1436.17, 35780.0, 35800.0, "GEO"), 3.05,
        )
        self.assertIsNotNone(note)
        self.assertIn("geostationary orbit", note["counter"]["value"])

    def test_a_cited_per_spacecraft_entry_is_not_second_guessed(self):
        """GEO-KOMPSAT-2B really is geostationary Earth observation."""
        for basis in ("norad-id", "exact-name"):
            with self.subTest(basis=basis):
                self.assertIsNone(build_release.regime_conflict_note(
                    "GEO-KOMPSAT-2B", "earth-observation", basis,
                    self._orbit(1436.08, 35780.0, 35800.0, "GEO"), 0.05,
                ))

    def test_weak_mismatches_stay_off_the_card(self):
        """A card covered in hedges teaches nothing."""
        for mission, regime in (("navigation", "LEO"), ("missile-warning", "LEO"), ("technology", "GEO")):
            with self.subTest(mission=mission):
                self.assertIsNone(build_release.regime_conflict_note(
                    "SOMETHING", mission, "name-pattern",
                    self._orbit(100.0, 500.0, 550.0, regime), 51.6,
                ))

    def test_an_unclassified_object_is_never_annotated(self):
        self.assertIsNone(build_release.regime_conflict_note(
            "RIGIDSPHERE 2", "other", "unclassified",
            self._orbit(100.1, 956.0, 995.0, "LEO"), 87.6,
        ))

    def test_both_note_kinds_share_one_shape(self):
        contested = build_release.attribution_note(
            "contested-source",
            {"value": "a", "attributedTo": "X", "source": "https://x"},
            {"value": "b", "attributedTo": "Y", "source": "https://y"},
            "position",
        )
        orbit = build_release.regime_conflict_note(
            "YAOGAN 45", "earth-observation", "name-pattern",
            self._orbit(271.08, 20000.0, 20200.0, "MEO"), 19.93,
        )
        self.assertEqual(set(contested), {"kind", "claim", "counter", "position"})
        self.assertTrue({"kind", "claim", "counter", "position"} <= set(orbit))

    def test_the_caveat_prose_is_generated_from_the_field(self):
        """Prose and machine-readable field cannot drift if one makes the other."""
        note = build_release.regime_conflict_note(
            "YAOGAN 45", "earth-observation", "name-pattern",
            self._orbit(271.08, 20000.0, 20200.0, "MEO"), 19.93,
        )
        prose = build_release.contested_caveat([note])
        self.assertIn("271-minute", prose)
        self.assertIn("rather than resolving it", prose)
        self.assertNotIn("None", prose)


if __name__ == "__main__":
    unittest.main()
