/**
 * THE THREE FACET LISTS ARE THE DATA'S, AND THE OWNER LIST'S ARRANGEMENT IS
 * DEFINED IN EVERY STATE.
 *
 * Two separate promises are held here.
 *
 * The first is completeness: every mission type, every constellation and every
 * organization the published catalog carries has to be reachable from the rail.
 * Not "the top eighteen", not "the ones a table in this repo happens to know" —
 * a truncated owner slice once made "only U.S. Navy" quietly impossible,
 * because an owner that was not on the list bypassed the facet entirely. The
 * lists are derived from the rows; these tests measure that against a fixture
 * distilled from the real artifact and fail when the two drift.
 *
 * The second is that grouping is PRESENTATION. Breaking 716 organizations into
 * bands or into letters rearranges rows; it must never add one, lose one, or
 * change which ones are ticked.
 */
import { describe, expect, it } from "vitest";

import fixtureJson from "./fixtures/catalog-facets.json";
import { OWNER_COUNT_BANDS, ownerCountBand, ownerGroups, ownerInitial } from "../src/facet-groups";

const explorerSource = Object.values(
  import.meta.glob("../src/main.ts", { eager: true, query: "?raw", import: "default" }),
)[0] as string;

interface FacetEntry {
  mission: string;
  constellation: string;
  owner: string;
  orbit: string;
  count: number;
}
const entries = (fixtureJson as { entries: FacetEntry[] }).entries;

/** Owner name to spacecraft count, exactly as `buildOwnerFilters` computes it
 *  off the catalog rows. */
const ownerCounts = new Map<string, number>();
entries.forEach((entry) => ownerCounts.set(entry.owner, (ownerCounts.get(entry.owner) ?? 0) + entry.count));
const owners = [...ownerCounts.keys()];

describe("every value in the catalog is on the rail", () => {
  it("derives all three lists from the rows, with no cap and no allowlist", () => {
    // Mission: a Set over the rows, and every distinct value becomes a box.
    expect(explorerSource).toContain(
      "const facets = Array.from(new Set(this.catalog.satellites.map(missionFacet)));",
    );
    // Constellation: a Map over the rows, and every key becomes a box.
    expect(explorerSource).toContain("this.constellationCount = counts.size;");
    // Owner: `ownerFilterOrder` returns the priorities that exist plus EVERY
    // remaining name, so the shown list and the counted list are the same list.
    expect(explorerSource).toContain("const shown = ownerFilterOrder(counts, priorities);");
    expect(explorerSource).not.toMatch(/owner[A-Za-z]*\.slice\(0,\s*\d+\)/);
    expect(explorerSource).not.toMatch(/\.slice\(0,\s*\d+\)[^\n]*owner/i);
  });

  it("has a written label for every mission type the catalog publishes", () => {
    // THE DRIFT THIS CATCHES, live on 2026-08-21: the pipeline began
    // publishing `signals-intelligence` and the rail had no label for it, so
    // the box read "signals-intelligen…" in raw hyphenated form — and, because
    // `indexOf` returns -1 for an unlisted key and -1 sorts before 0, it sat at
    // the HEAD of the grid. The list was never short. The table it is ordered
    // by had drifted from the data.
    const table = /const missionLabels: Record<string, string> = \{([\s\S]*?)\n\};/.exec(explorerSource)?.[1] ?? "";
    expect(table.length).toBeGreaterThan(0);
    const labelled = new Set([...table.matchAll(/^\s*"?([a-z-]+)"?:/gm)].map((match) => match[1]!));
    const published = new Set(entries.map((entry) => entry.mission));
    expect(published.size).toBeGreaterThan(0);
    [...published].sort().forEach((mission) => expect([...labelled]).toContain(mission));
  });

  it("orders an unknown mission type LAST rather than first", () => {
    // The fix for the same defect, asserted on the ordering code itself: an
    // unlisted key ranks at the end of the table rather than at -1.
    expect(explorerSource).toContain("return index === -1 ? preferredOrder.length : index;");
    expect(explorerSource).toContain("facets.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));");
    expect(explorerSource).not.toContain(
      "facets.sort((a, b) => preferredOrder.indexOf(a) - preferredOrder.indexOf(b));",
    );
  });
});

describe("the count bands fit the catalog they are cut for", () => {
  it("puts every owner in exactly one band", () => {
    owners.forEach((owner) => {
      const count = ownerCounts.get(owner)!;
      const matches = OWNER_COUNT_BANDS.filter((band) => count >= band.min && count <= band.max);
      expect(matches).toHaveLength(1);
      expect(ownerCountBand(count)).toBe(matches[0]!.label);
    });
  });

  it("leaves no band holding most of the list", () => {
    // A band with four fifths of the owners in it has not sorted anything. The
    // real distribution's largest band is "exactly one spacecraft", 57% of 716.
    const grouped = ownerGroups(owners, ownerCounts, true, false)!;
    const largest = Math.max(...grouped.map((group) => group.members.length));
    expect(largest / owners.length).toBeLessThan(0.8);
  });

  it("never draws a band with nothing in it", () => {
    // `500–999` is empty against today's catalog and is KEPT in the ladder,
    // because it is where a second mega constellation lands. It is simply not
    // rendered while it is empty — in this dataset or in any other.
    const grouped = ownerGroups(owners, ownerCounts, true, false)!;
    grouped.forEach((group) => expect(group.members.length).toBeGreaterThan(0));
    expect(grouped.map((group) => group.label)).not.toContain("500–999");
    expect(OWNER_COUNT_BANDS.map((band) => band.label)).toContain("500–999");
    // …and it does appear the moment the data puts somebody in it.
    const withMid = new Map(ownerCounts).set("Hypothetical Fleet", 640);
    const regrouped = ownerGroups([...withMid.keys()], withMid, true, false)!;
    expect(regrouped.map((group) => group.label)).toContain("500–999");
  });

  it("descends, largest band at the top", () => {
    const grouped = ownerGroups(owners, ownerCounts, true, false)!;
    const ladder = OWNER_COUNT_BANDS.map((band) => band.label);
    const drawn = grouped.map((group) => group.label);
    expect(drawn).toEqual(ladder.filter((label) => drawn.includes(label)));
    // Each band's floor is above the next band's ceiling, so "descending" is a
    // property of the ladder rather than of this dataset.
    OWNER_COUNT_BANDS.slice(1).forEach((band, index) => {
      expect(band.max).toBeLessThan(OWNER_COUNT_BANDS[index]!.min);
    });
  });
});

describe("grouping rearranges the list and changes nothing else", () => {
  const shapes: [string, boolean, boolean][] = [
    ["by number", true, false],
    ["alphabetically", false, true],
    ["both", true, true],
  ];

  it("is the flat list, untouched, when neither toggle is on", () => {
    expect(ownerGroups(owners, ownerCounts, false, false)).toBeNull();
  });

  shapes.forEach(([name, byCount, alphabetically]) => {
    it(`holds every owner exactly once, ${name}`, () => {
      const grouped = ownerGroups(owners, ownerCounts, byCount, alphabetically)!;
      const flat = grouped.flatMap((group) => (group.children
        ? group.children.flatMap((child) => child.members)
        : group.members));
      expect(flat).toHaveLength(owners.length);
      expect(new Set(flat)).toEqual(new Set(owners));
    });

    it(`is stable — the same inputs give the same arrangement, ${name}`, () => {
      const first = JSON.stringify(ownerGroups(owners, ownerCounts, byCount, alphabetically));
      const shuffled = [...owners].reverse();
      const second = JSON.stringify(ownerGroups(shuffled, ownerCounts, byCount, alphabetically));
      expect(second).toBe(first);
    });
  });

  it("sorts alphabetically inside an alphabetical group", () => {
    const grouped = ownerGroups(owners, ownerCounts, false, true)!;
    grouped.forEach((group) => {
      expect(group.members).toEqual([...group.members].sort((left, right) => left.localeCompare(right)));
      group.members.forEach((member) => expect(ownerInitial(member)).toBe(group.label));
    });
    // A–Z ascending, with the catch-all last.
    const labels = grouped.map((group) => group.label);
    expect(labels.filter((label) => label !== "#"))
      .toEqual([...labels.filter((label) => label !== "#")].sort());
    if (labels.includes("#")) expect(labels[labels.length - 1]).toBe("#");
  });

  it("sorts count-descending then alphabetically inside a count band", () => {
    const grouped = ownerGroups(owners, ownerCounts, true, false)!;
    grouped.forEach((group) => {
      const expected = [...group.members].sort((left, right) =>
        (ownerCounts.get(right) ?? 0) - (ownerCounts.get(left) ?? 0) || left.localeCompare(right));
      expect(group.members).toEqual(expected);
    });
  });

  it("nests A–Z inside each band when both toggles are on", () => {
    const grouped = ownerGroups(owners, ownerCounts, true, true)!;
    grouped.forEach((band) => {
      expect(band.children).toBeDefined();
      const inside = band.children!.flatMap((letter) => letter.members);
      expect(new Set(inside)).toEqual(new Set(band.members));
      // The header counts what is under it.
      expect(band.members).toHaveLength(inside.length);
      band.children!.forEach((letter) => {
        letter.members.forEach((member) => expect(ownerInitial(member)).toBe(letter.label));
      });
      // Keys are unique across the whole tree, so a reader's open folds cannot
      // be confused for one another between two bands.
      const keys = band.children!.map((letter) => letter.key);
      expect(new Set(keys).size).toBe(keys.length);
    });
    const bandKeys = grouped.map((band) => band.key);
    expect(new Set(bandKeys).size).toBe(bandKeys.length);
  });
});

describe("the alphabet has somewhere to put everything", () => {
  it("files an accented name under its plain letter", () => {
    expect(ownerInitial("Électricité de France")).toBe("E");
    expect(ownerInitial("Ørsted")).toBe("#");
  });

  it("files digits and symbols under a single catch-all", () => {
    expect(ownerInitial("3D Networks")).toBe("#");
    expect(ownerInitial("  spire global")).toBe("S");
    expect(ownerInitial("")).toBe("#");
  });

  it("gives every organization in the real catalog a home", () => {
    owners.forEach((owner) => expect(ownerInitial(owner)).toMatch(/^[A-Z#]$/));
  });
});
