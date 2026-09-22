"""The facet fixture the filter-healing tests reason over must match the
published catalog.

tests/fixtures/catalog-facets.json is a distillation of the real catalog
artifact into (mission facet, constellation, owner, orbit) -> count rows, so
the vitest suite can run the "only US Navy / only Starlink / only Metop"
scenarios against real populations without the ~44 GB data tree. This guard
runs where that tree exists (the processing machine) and fails loudly if the
published catalog's facet structure drifts away from the fixture; elsewhere it
skips rather than pretending to have checked.

Regenerating the fixture: group the catalog artifact's satellites by the same
facet rule reproduced in mission_facet() below (it mirrors missionFacet() in
src/main.ts), count each (mission, constellation or __independent__,
organization, orbit) triple, and write {satelliteTotal, entries:[...]}.
"""

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "catalog-facets.json"
MANIFEST = REPO / "public" / "data" / "manifest.json"

INDEPENDENT = "__independent__"


def mission_facet(satellite):
    """Mirror of missionFacet() in src/main.ts — keep the two in lockstep."""
    if satellite["mission"] == "communications" and satellite["sector"] == "military":
        return "milsatcom"
    if satellite["mission"] == "communications" and satellite["sector"] == "commercial":
        return "commercial-satcom"
    if satellite["mission"] == "other" and satellite["sector"] == "military":
        return "military-other"
    return satellite["mission"]


@unittest.skipUnless(MANIFEST.exists(), "published data tree not present on this machine")
class CatalogFacetFixtureAgreesWithLiveCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())
        manifest = json.loads(MANIFEST.read_text())
        catalog_path = REPO / "public" / "data" / manifest["catalog"]["path"]
        cls.satellites = json.loads(catalog_path.read_text())["satellites"]

    def live_counts(self):
        counts = {}
        for satellite in self.satellites:
            key = (
                mission_facet(satellite),
                satellite.get("constellation") or INDEPENDENT,
                satellite["organization"],
                satellite["orbit"],
            )
            counts[key] = counts.get(key, 0) + 1
        return counts

    def test_totals_and_triples_match(self):
        """The fixture must still describe the catalog's facet STRUCTURE.

        It used to demand exact equality of every count, and that is a test of
        the wrong thing: the catalog republishes every five minutes and objects
        decay, so a handful of Starlinks leaving orbit failed this guard
        overnight while nothing about the facet rule had changed. A guard that
        cries wolf daily is a guard nobody reads.

        What this actually protects is the vitest filter-healing suite, which
        reasons over the fixture's populations to run the "only US Navy",
        "only Starlink", "only Metop" scenarios. That suite needs populations
        that are REAL and roughly current; it does not need yesterday's exact
        integers. So the thresholds below are deliberately loose enough for
        orbital decay and tight enough to catch the failure that matters: a
        change to `mission_facet()` or to the catalog's classification that
        moves a whole group between facets.
        """
        live = self.live_counts()
        fixture_rows = {
            (row["mission"], row["constellation"], row["owner"], row["orbit"]): row["count"]
            for row in self.fixture["entries"]
        }
        # The catalog is capped at a fixed browser ceiling, so this is exact.
        self.assertEqual(self.fixture["satelliteTotal"], len(self.satellites))

        # A triple appearing or disappearing with only a few objects in it is
        # ordinary churn. One carrying a real population is a classification
        # change, and the fixture has to be regenerated for it.
        churn = 5
        appeared = {k: v for k, v in live.items() if k not in fixture_rows and v > churn}
        vanished = {k: v for k, v in fixture_rows.items() if k not in live and v > churn}
        self.assertEqual(appeared, {}, "facet triples appeared with real populations")
        self.assertEqual(vanished, {}, "facet triples the fixture claims have emptied")

        # Per-triple drift: 5% or 25 objects, whichever is larger. A decayed
        # constellation member is inside that; a group being re-labelled is not.
        drifted = {
            key: (count, live[key])
            for key, count in fixture_rows.items()
            if key in live and abs(live[key] - count) > max(25, 0.05 * count)
        }
        self.assertEqual(drifted, {}, "facet populations moved too far to still be current")

        # Whole-facet totals are the sharpest instrument here: re-labelling one
        # group shows up as two facets moving in opposite directions even when
        # every individual triple looks plausible.
        def by_facet(counts):
            totals = {}
            for (mission, _constellation, _owner, _orbit), count in counts.items():
                totals[mission] = totals.get(mission, 0) + count
            return totals

        fixture_facets, live_facets = by_facet(fixture_rows), by_facet(live)
        self.assertEqual(set(fixture_facets), set(live_facets), "a mission facet appeared or vanished")
        facet_drift = {
            facet: (total, live_facets[facet])
            for facet, total in fixture_facets.items()
            if abs(live_facets[facet] - total) > max(25, 0.05 * total)
        }
        self.assertEqual(facet_drift, {}, "a whole mission facet changed size — check mission_facet()")

    def test_seans_scenarios_still_have_their_populations(self):
        """The named scenarios must not silently become empty as the catalog
        evolves — if one does, the corresponding vitest scenario is testing a
        population that no longer exists and both need revisiting."""
        owners = {}
        constellations = {}
        for satellite in self.satellites:
            owners[satellite["organization"]] = owners.get(satellite["organization"], 0) + 1
            name = satellite.get("constellation")
            if name:
                constellations[name] = constellations.get(name, 0) + 1
        self.assertGreater(owners.get("U.S. Navy", 0), 0)
        self.assertGreater(constellations.get("Starlink", 0), 0)
        self.assertGreater(constellations.get("Metop", 0), 0)


if __name__ == "__main__":
    unittest.main()
