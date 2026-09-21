// The catalog filter lists AND together, so one emptied list used to zero the
// whole result and raise a warning box that read as an error — the state Sean
// hit trying to plot only US Navy satellites. These tests pin the replacement.
//
// REVISED TWICE, AND THE SECOND REVISION IS THE ONE THIS FILE IS NOW ABOUT.
//
// 2026-08-27 removed "healing": an auto-selection that widened whichever lists
// were in the way so that a click would always show something. Sean hit the
// cost of it trying to plot only Russian MILSATCOM — Clear all in the owner box
// emptied his mission and fleet boxes too, and ticking the owner afterwards
// turned navigation, missile warning, earth observation and other-military back
// on underneath him (117 satellites; he had asked for the 50 that are both).
//
// 2026-08-28 is Sean's own design for the same problem, and it is a DIFFERENT
// mechanism rather than the old one restored:
//
//   "these lists are linked to one another smartly. say i click 'METOC' under
//    mission type. under the other two filter categories, the constellations
//    and owners will automatically be selected for all METOC satellites... a
//    user can then go in and deselect what they don't want... so say i plot all
//    metoc but i only want to see china. i can click metoc and deselect the
//    other countries and as i do the satellites will go off the viewer."
//
// The rules these tests pin:
//
//   * a POSITIVE CLICK links: it ticks, in the other two lists, every value the
//     clicked value's satellites carry. Unconditionally — there is no state in
//     which a positive click does something else — and as a UNION, so a second
//     positive click adds a second population instead of replacing the first;
//   * a DESELECTION removes exactly what was unticked and links nothing;
//   * a combination that matches nothing is said out loud in one line and left
//     standing, so it is visible and one click reversible.
//
// The difference from the withdrawn healer is not the direction of the arrow,
// it is WHEN and WHY it fires: healing was a repair that ran when a click would
// otherwise have failed, on deselections as well as selections, and branched on
// invisible bookkeeping about who had ticked what. Linking is the gesture
// itself, never runs on a deselection, and consults nothing.
//
// Every test below that changed with those rules carries its reason inline.
//
// The facet fixture is distilled from the real catalog artifact (8,000 objects,
// 2026-08-09) into (mission facet, constellation, owner, orbit) → count rows.
// Regenerate by grouping the catalog artifact's satellites with the same
// missionFacet() rule main.ts exports, if the catalog's facets ever change.
import { describe, expect, it } from "vitest";
import fixtureJson from "./fixtures/catalog-facets.json";
import {
  describeFacetLinking,
  facetChipText,
  facetMatchCount,
  linkAfterSelect,
  ownerFilterOrder,
  reportAfterDeselect,
  selectionIsEmpty,
} from "../src/main";
import type { FacetEntry, FacetName, FacetSelection } from "../src/main";

interface FixtureRow { mission: string; constellation: string; owner: string; orbit: string; count: number }
const fixture = fixtureJson as { satelliteTotal: number; entries: FixtureRow[] };

/** Page sources read the way module-reachability.test.ts reads them — no node
 * builtins, just the bundler's own raw imports. */
const rawSources = {
  ...import.meta.glob("../index.html", { eager: true, query: "?raw", import: "default" }),
  ...import.meta.glob("../src/styles.css", { eager: true, query: "?raw", import: "default" }),
} as Record<string, string>;

function expandRows(rows: FixtureRow[], orbitFilter: string | null = null): FacetEntry[] {
  const entries: FacetEntry[] = [];
  rows.forEach((row) => {
    for (let i = 0; i < row.count; i += 1) {
      entries.push({
        mission: row.mission,
        constellation: row.constellation,
        owner: row.owner,
        inOrbit: orbitFilter === null || row.orbit === orbitFilter,
      });
    }
  });
  return entries;
}

function values(entries: readonly FacetEntry[], facet: FacetName): Set<string> {
  return new Set(entries.map((entry) => entry[facet]));
}

function fullSelection(entries: readonly FacetEntry[]): FacetSelection {
  return {
    mission: values(entries, "mission"),
    constellation: values(entries, "constellation"),
    owner: values(entries, "owner"),
  };
}

function selection(parts: Partial<Record<FacetName, Iterable<string>>>, entries: readonly FacetEntry[]): FacetSelection {
  const full = fullSelection(entries);
  return {
    mission: parts.mission ? new Set(parts.mission) : full.mission,
    constellation: parts.constellation ? new Set(parts.constellation) : full.constellation,
    owner: parts.owner ? new Set(parts.owner) : full.owner,
  };
}

const catalogEntries = expandRows(fixture.entries);
const shownOwners = values(catalogEntries, "owner");
const NAVY = "U.S. Navy";
const PRC = "People's Republic of China";
const METOC = "weather";
const CMA = "China Meteorological Administration";

/** The state the catalog opens in: nothing ticked, nothing drawn. */
const BARE: FacetSelection = { mission: new Set(), constellation: new Set(), owner: new Set() };
const bare = (): FacetSelection => ({ mission: new Set(), constellation: new Set(), owner: new Set() });

/** One positive click on one row. */
function click(entries: readonly FacetEntry[], base: FacetSelection, facet: FacetName, value: string) {
  return linkAfterSelect(entries, base, shownOwners, facet, value);
}

/** One untick, which is a removal and never a link. */
function untick(entries: readonly FacetEntry[], base: FacetSelection, facet: FacetName, value: string) {
  const next: FacetSelection = {
    mission: new Set(base.mission),
    constellation: new Set(base.constellation),
    owner: new Set(base.owner),
  };
  next[facet].delete(value);
  return reportAfterDeselect(entries, next, shownOwners);
}

const countWhere = (predicate: (entry: FacetEntry) => boolean) => catalogEntries.filter(predicate).length;

describe("the exact state that produced Sean's error", () => {
  it("matches zero satellites before anything links: missions emptied, US Navy ticked", () => {
    // Pre-fix this state put the red warning box on screen and blamed the
    // visitor; the AND semantics themselves are unchanged and still yield 0.
    const sel = selection({ mission: [], owner: [NAVY] }, catalogEntries);
    expect(facetMatchCount(catalogEntries, sel, shownOwners)).toBe(0);
  });

  it("clicking the US Navy owner ticks the mission types the Navy flies, and shows them", () => {
    const sel = selection({ mission: [], owner: [NAVY] }, catalogEntries);
    const linked = click(catalogEntries, sel, "owner", NAVY);
    // The link selects exactly the mission facets the US Navy actually flies —
    // no more, no less. That was MILSATCOM alone until the US partition
    // described SPAWAR-CAL-O/R/OR, three 1U Navy calibration targets: military,
    // but passive spacecraft with no communications payload, so OTHER MILITARY.
    expect(linked.added.mission).toEqual(["military-other", "milsatcom"]);
    // The fleet list was already holding every fleet, so the link had nothing
    // to add there. It adds, it never replaces.
    expect(linked.added.constellation).toBeUndefined();
    expect(linked.matchCount).toBe(countWhere((entry) => entry.owner === NAVY));
    expect(describeFacetLinking(linked, "U.S. Navy")).toBe(
      "Also selected 2 mission types that U.S. Navy satellites carry.",
    );
  });
});

describe("Sean's six scenarios, driven on the real catalog fixture", () => {
  /**
   * SCENARIO 1. "say i click 'METOC' under mission type. under the other two
   * filter categories, the constellations and owners will automatically be
   * selected for all METOC satellites."
   */
  it("METOC out of a bare catalog fills both other lists and plots every METOC satellite", () => {
    const linked = click(catalogEntries, bare(), "mission", METOC);
    const metocCount = countWhere((entry) => entry.mission === METOC);
    expect(metocCount).toBeGreaterThan(100);
    expect(linked.matchCount).toBe(metocCount);
    expect(linked.selection.mission).toEqual(new Set([METOC]));
    // Every fleet and every organization those satellites carry, and nothing
    // else: the fill is read off the named satellites themselves.
    expect(linked.selection.constellation).toEqual(
      new Set(catalogEntries.filter((entry) => entry.mission === METOC).map((entry) => entry.constellation)),
    );
    expect(linked.selection.owner).toEqual(
      new Set(catalogEntries.filter((entry) => entry.mission === METOC).map((entry) => entry.owner)),
    );
    // And it is SAID, because the two lists it filled may be folded shut.
    expect(describeFacetLinking(linked, "METOC / weather")).toMatch(
      /^Also selected \d+ fleets and \d+ organizations that METOC \/ weather satellites carry\.$/,
    );
  });

  /**
   * SCENARIO 2, and the one the whole design turns on. "so say i plot all metoc
   * but i only want to see china. i can click metoc and deselect the other
   * countries and as i do the satellites will go off the viewer."
   *
   * Every untick is checked, not just the last one: nothing may be re-added at
   * any step, in any list, or the reader would be fighting the interface.
   */
  it("deselecting every organization but China leaves Chinese METOC, and puts nothing back", () => {
    let state = click(catalogEntries, bare(), "mission", METOC).selection;
    const keep = [...state.owner].filter((owner) => owner.startsWith(CMA));
    expect(keep.length).toBeGreaterThan(0);
    const mission = new Set(state.mission);
    const fleets = new Set(state.constellation);
    for (const owner of [...state.owner]) {
      if (keep.includes(owner)) continue;
      const before = new Set(state.owner);
      const step = untick(catalogEntries, state, "owner", owner);
      // A deselection removes the one value and touches nothing else, in any
      // list. This is the assertion the 2026-08-27 defect would fail.
      expect(step.selection.owner.has(owner)).toBe(false);
      expect(step.selection.owner.size).toBe(before.size - 1);
      expect(step.selection.mission).toEqual(mission);
      expect(step.selection.constellation).toEqual(fleets);
      expect(step.added).toEqual({});
      state = step.selection;
    }
    const chineseMetoc = countWhere((entry) => entry.mission === METOC && keep.includes(entry.owner));
    expect(chineseMetoc).toBeGreaterThan(0);
    expect(facetMatchCount(catalogEntries, state, shownOwners)).toBe(chineseMetoc);
    // Every other country really is off the viewer.
    expect(chineseMetoc).toBeLessThan(countWhere((entry) => entry.mission === METOC));
  });

  /**
   * SCENARIO 3. "or if they go into constellations and click Globalstar for
   * example the owner and the mission will be selected. they're tied together."
   */
  it("clicking Globalstar selects its owner and its mission", () => {
    const linked = click(catalogEntries, bare(), "constellation", "Globalstar");
    expect(linked.added.owner).toEqual(["Globalstar"]);
    expect(linked.added.mission).toEqual(["commercial-satcom"]);
    expect(linked.matchCount).toBe(countWhere((entry) => entry.constellation === "Globalstar"));
  });

  /**
   * SCENARIO 4. "or i click PRC and i just deselect all the mission types i
   * don't care about."
   */
  it("clicking PRC selects what China flies, and unticking a mission type takes it off", () => {
    const linked = click(catalogEntries, bare(), "owner", PRC);
    const allChinese = countWhere((entry) => entry.owner === PRC);
    expect(linked.matchCount).toBe(allChinese);
    expect(linked.selection.mission.size).toBeGreaterThan(1);
    const dropped = [...linked.selection.mission].filter((mission) => mission !== "earth-observation");
    let state = linked.selection;
    dropped.forEach((mission) => { state = untick(catalogEntries, state, "mission", mission).selection; });
    expect(state.mission).toEqual(new Set(["earth-observation"]));
    expect(facetMatchCount(catalogEntries, state, shownOwners))
      .toBe(countWhere((entry) => entry.owner === PRC && entry.mission === "earth-observation"));
  });

  /**
   * SCENARIO 5. Clear empties every list, and the globe with them. The
   * arithmetic is the same one Sean sanctioned for deselecting by hand: "if I
   * deselect everything, take all satellites off the map."
   */
  it("an empty selection draws nothing, and says nothing about it", () => {
    const cleared = reportAfterDeselect(catalogEntries, bare(), shownOwners);
    expect(cleared.matchCount).toBe(0);
    expect(selectionIsEmpty(cleared.selection)).toBe(true);
    expect(cleared.anyFacetEmpty).toBe(true);
    expect(describeFacetLinking(cleared)).toBeNull();
  });

  /**
   * SCENARIO 6. The band is the scope, not a selection: it changes which values
   * the three lists OFFER and plots nothing by itself. Here that is the
   * `inOrbit` flag — a bare selection inside a band still draws nothing.
   */
  it("a band narrows what is on offer and draws nothing on its own", () => {
    const leoOnly = expandRows(fixture.entries, "LEO");
    expect(reportAfterDeselect(leoOnly, bare(), shownOwners).matchCount).toBe(0);
    // And a click inside the band only ever names in-band satellites.
    const linked = linkAfterSelect(leoOnly, bare(), shownOwners, "mission", METOC);
    expect(linked.matchCount).toBe(leoOnly.filter((entry) => entry.inOrbit && entry.mission === METOC).length);
    expect(linked.matchCount).toBeLessThan(countWhere((entry) => entry.mission === METOC));
  });

  /**
   * THE SECOND POSITIVE CLICK IS ADDITIVE, and this is the rule Sean did not
   * specify, so here is the argument for it.
   *
   * REPLACING would make a tick take satellites OFF the viewer, which is the
   * opposite of what ticking a box says it does; and it would make his own
   * remedy incoherent, because "click metoc and deselect the other countries"
   * only reads as a remedy if the click put those countries there and left
   * them there. So the union it is: two clicks plot both populations, exactly,
   * with no double counting and nothing dropped.
   */
  it("a second positive click adds its population rather than replacing the first", () => {
    const first = click(catalogEntries, bare(), "mission", METOC);
    const second = click(catalogEntries, first.selection, "mission", "navigation");
    expect(second.selection.mission).toEqual(new Set([METOC, "navigation"]));
    expect(second.matchCount).toBe(
      countWhere((entry) => entry.mission === METOC) + countWhere((entry) => entry.mission === "navigation"),
    );
    // Nothing the first click ticked was taken away by the second.
    first.selection.owner.forEach((owner) => expect(second.selection.owner.has(owner)).toBe(true));
    first.selection.constellation.forEach((fleet) => expect(second.selection.constellation.has(fleet)).toBe(true));
  });
});

describe("one click is the whole of 'what if I want just...'", () => {
  // These used to need the "only" chip on the row, because a plain tick
  // intersected and a reader had to clear the list first. A plain tick links,
  // so out of a bare catalog it IS "only this". The chip is gone with them.
  it("only Starlink", () => {
    const linked = click(catalogEntries, bare(), "constellation", "Starlink");
    const starlink = countWhere((entry) => entry.constellation === "Starlink");
    expect(starlink).toBeGreaterThan(1000);
    expect(linked.matchCount).toBe(starlink);
  });

  it("only US Navy", () => {
    const linked = click(catalogEntries, bare(), "owner", NAVY);
    expect(linked.matchCount).toBe(countWhere((entry) => entry.owner === NAVY));
    // The owner list must actually constrain to the Navy alone — this only
    // works because every organization is listed, not a truncated top slice.
    expect(linked.selection.owner).toEqual(new Set([NAVY]));
  });

  it("only Metop", () => {
    const linked = click(catalogEntries, bare(), "constellation", "Metop");
    const metop = countWhere((entry) => entry.constellation === "Metop");
    expect(metop).toBeGreaterThan(0);
    expect(linked.matchCount).toBe(metop);
    expect(linked.added.owner?.length).toBeGreaterThan(0);
  });

  /**
   * ONLY RUSSIAN MILSATCOM — Sean's original errand, by the route his new
   * design gives him.
   *
   * REWRITTEN 2026-08-28. It used to prove that clearing the owner box and
   * then ticking one owner INTERSECTED, because nothing was allowed to widen a
   * list the reader had narrowed. That guarantee is withdrawn with the healer,
   * and the errand is not: the route is now tick the mission, then deselect the
   * organizations, which is what Sean himself wrote. Every untick sticks, and
   * the answer is the 50 rather than the 117.
   */
  it("tick MILSATCOM, deselect the other organizations, and the answer is the intersection", () => {
    const RU = "Russian Ministry of Defence (assessed)";
    const linked = click(catalogEntries, bare(), "mission", "milsatcom");
    expect(linked.matchCount).toBe(countWhere((entry) => entry.mission === "milsatcom"));
    expect(linked.selection.owner.has(RU)).toBe(true);

    let state = linked.selection;
    for (const owner of [...state.owner]) {
      if (owner === RU) continue;
      const step = untick(catalogEntries, state, "owner", owner);
      expect(step.added).toEqual({});
      expect(step.selection.mission).toEqual(new Set(["milsatcom"]));
      state = step.selection;
    }
    const russianMilsatcom = countWhere((entry) => entry.owner === RU && entry.mission === "milsatcom");
    const allRussian = countWhere((entry) => entry.owner === RU);
    expect(russianMilsatcom).toBeGreaterThan(0);
    expect(allRussian).toBeGreaterThan(russianMilsatcom); // the 117 was the old answer
    expect(state.owner).toEqual(new Set([RU]));
    expect(facetMatchCount(catalogEntries, state, shownOwners)).toBe(russianMilsatcom);
  });

  /**
   * CHINESE MILITARY COMMUNICATIONS: the catalog holds none, and the site still
   * says so rather than plotting something else.
   *
   * REWRITTEN 2026-08-28, and the route changed rather than the ruling. It used
   * to be reached by a positive click — tick MILSATCOM, tick PRC, get a line
   * instead of 400 Chinese spacecraft. A positive click LINKS now, so it can no
   * longer land there: ticking PRC plots what China flies, which is what Sean
   * asked a click to do. The zero is reached the way every narrowing is reached
   * now, by deselecting, and there it is still REPORTED and never repaired:
   * nothing is widened underneath the reader, and the selection is left
   * exactly as they set it. Not an undo, though — re-ticking the box is a
   * positive click and therefore links, so it comes back with everything that
   * goes with it. Clear and one tick is the way back to a small set.
   */
  it("no Chinese MILSATCOM: deselecting down to it reports the zero and changes nothing", () => {
    let state = click(catalogEntries, bare(), "mission", "milsatcom").selection;
    // China is not among the organizations MILSATCOM ticked, which is itself
    // the teachable fact, on screen, in the owner list.
    expect(state.owner.has(PRC)).toBe(false);
    state = click(catalogEntries, state, "owner", PRC).selection;
    for (const mission of [...state.mission]) {
      if (mission === "milsatcom") continue;
      state = untick(catalogEntries, state, "mission", mission).selection;
    }
    for (const owner of [...state.owner]) {
      if (owner === PRC) continue;
      state = untick(catalogEntries, state, "owner", owner).selection;
    }
    const final = reportAfterDeselect(catalogEntries, state, shownOwners);
    expect(final.matchCount).toBe(0);
    expect(final.selection.mission).toEqual(new Set(["milsatcom"]));
    expect(final.selection.owner).toEqual(new Set([PRC]));
    expect(final.anyFacetEmpty).toBe(false);
    expect(final.added).toEqual({});
    expect(describeFacetLinking(final)).toBe("Nothing matches that combination. Nothing was changed.");
  });
});

describe("deselection removes what was unticked, and nothing else", () => {
  const E = (mission: string, constellation: string, owner: string, inOrbit = true): FacetEntry =>
    ({ mission, constellation, owner, inOrbit });
  // A miniature navy-flavoured catalog: comms fleet, navigation fleet, and a
  // civilian weather bird from another agency.
  const mini = [
    E("milsatcom", "MUOS", "U.S. Navy"),
    E("milsatcom", "MUOS", "U.S. Navy"),
    E("navigation", "NAVSAT", "U.S. Navy"),
    E("weather", "GOES", "NOAA / NASA"),
  ];
  const miniOwners = values(mini, "owner");

  it("a deselection that still matches something changes nothing else", () => {
    // Comms deselected; the navigation bird still matches, so the fruitless
    // MUOS tick simply stays — lists keep the user's intent for later.
    const sel: FacetSelection = {
      mission: new Set(["navigation"]),
      constellation: new Set(["MUOS", "NAVSAT"]),
      owner: new Set(["U.S. Navy"]),
    };
    const settled = reportAfterDeselect(mini, sel, miniOwners);
    expect(settled.matchCount).toBe(1);
    expect(settled.selection).toEqual(sel);
    expect(settled.anyFacetEmpty).toBe(false);
    expect(describeFacetLinking(settled)).toBeNull();
  });

  /**
   * A deselection that hits zero used to wipe all three lists, on the argument
   * that pruning could not do better. The argument was sound and the conclusion
   * was still wrong — the reader had asked to take ONE tick off, and got three
   * boxes emptied. It is how "Clear all" in the owner box cleared Sean's screen,
   * twice. The zero is reported and left standing.
   */
  it("a deselection that zeroes the result changes nothing else, and says so", () => {
    const sel: FacetSelection = {
      mission: new Set(["navigation"]),
      constellation: new Set(["MUOS", "GOES"]),
      owner: new Set(["U.S. Navy"]),
    };
    const settled = reportAfterDeselect(mini, sel, miniOwners);
    expect(settled.matchCount).toBe(0);
    expect(settled.selection).toEqual(sel);
    expect(selectionIsEmpty(settled.selection)).toBe(false);
    // Every list still has ticks in it, so this zero is not something the
    // reader asked for — and that is the one case worth a line.
    expect(settled.anyFacetEmpty).toBe(false);
    expect(describeFacetLinking(settled)).toBe("Nothing matches that combination. Nothing was changed.");
  });

  /**
   * Emptying a list empties the GLOBE — the lists AND together and that is
   * arithmetic, not a policy, and Sean asked for exactly it: "if I deselect
   * everything, take all satellites off the map." What it does not do is empty
   * the other two lists.
   */
  it("emptying a list empties the globe and leaves the other lists standing", () => {
    const sel: FacetSelection = {
      mission: new Set(),
      constellation: new Set(["MUOS", "GOES"]),
      owner: new Set(["U.S. Navy", "NOAA / NASA"]),
    };
    const settled = reportAfterDeselect(mini, sel, miniOwners);
    expect(settled.matchCount).toBe(0);
    expect(settled.selection.constellation).toEqual(new Set(["MUOS", "GOES"]));
    expect(settled.selection.owner).toEqual(new Set(["U.S. Navy", "NOAA / NASA"]));
    expect(settled.anyFacetEmpty).toBe(true);
    // Picking one value back out of the emptied list plots what that value
    // names — the two MUOS birds — and takes nothing away.
    const back = linkAfterSelect(mini, settled.selection, miniOwners, "mission", "milsatcom");
    expect(back.matchCount).toBe(2);
    expect(back.added).toEqual({});
  });

  /**
   * Sean cleared every filter and the rail answered "Nothing matched any more,
   * so every filter was cleared. 0 shown - nothing selected." — "Duh. I cleared
   * everything. Why am I getting an error." A deliberate clear is a completed
   * action, so the only honest number of words for it is none.
   */
  it("clearing a list yourself is silent; a combination dying on you is not", () => {
    const cleared: FacetSelection = {
      mission: new Set(),
      constellation: new Set(["MUOS", "GOES"]),
      owner: new Set(["U.S. Navy", "NOAA / NASA"]),
    };
    const byVisitor = reportAfterDeselect(mini, cleared, miniOwners);
    expect(byVisitor.anyFacetEmpty).toBe(true);
    expect(describeFacetLinking(byVisitor)).toBeNull();

    const stillTicked: FacetSelection = {
      mission: new Set(["navigation"]),
      constellation: new Set(["GOES"]),
      owner: new Set(["U.S. Navy"]),
    };
    const settled = reportAfterDeselect(mini, stillTicked, miniOwners);
    expect(settled.anyFacetEmpty).toBe(false);
    expect(describeFacetLinking(settled)).toBe("Nothing matches that combination. Nothing was changed.");
  });

  it("never re-selects anything: a deselection's result is a subset of what the user had", () => {
    const sel: FacetSelection = {
      mission: new Set(["navigation"]),
      constellation: new Set(["MUOS", "NAVSAT", "GOES"]),
      owner: new Set(["U.S. Navy", "NOAA / NASA"]),
    };
    const settled = reportAfterDeselect(mini, sel, miniOwners);
    (["mission", "constellation", "owner"] as FacetName[]).forEach((facet) => {
      settled.selection[facet].forEach((value) => expect(sel[facet].has(value)).toBe(true));
    });
  });
});

describe("the visitor can deselect every box, one by one, to the calm empty globe", () => {
  it("no step is refused, nothing gets re-checked, and the run ends entirely empty", () => {
    const sel = fullSelection(catalogEntries);
    const plan: Array<[FacetName, string]> = [];
    (["owner", "constellation", "mission"] as FacetName[]).forEach((facet) => {
      values(catalogEntries, facet).forEach((value) => plan.push([facet, value]));
    });
    let state = sel;
    for (const [facet, value] of plan) {
      if (!state[facet].has(value)) continue;
      const next: FacetSelection = {
        mission: new Set(state.mission),
        constellation: new Set(state.constellation),
        owner: new Set(state.owner),
      };
      next[facet].delete(value);
      const settled = reportAfterDeselect(catalogEntries, next, shownOwners);
      // The unticked box stays unticked — deselection is never refused or undone.
      expect(settled.selection[facet].has(value)).toBe(false);
      // And it changes NOTHING but the box that was unticked (it used to be
      // allowed to remove more; that is what cleared Sean's screen).
      expect(settled.selection).toEqual(next);
      // The honest invariant is the arithmetic: a result of zero means some
      // list is empty, and an empty list under conjunctive lists IS zero.
      const someFacetEmpty = (["mission", "constellation", "owner"] as FacetName[])
        .some((name) => settled.selection[name].size === 0);
      expect(settled.matchCount >= 1 || someFacetEmpty).toBe(true);
      state = settled.selection;
      if (selectionIsEmpty(state)) break;
    }
    expect(selectionIsEmpty(state)).toBe(true);
  });
});

describe("linking converges in one pass", () => {
  // Pathological joint co-occurrence: each list pairwise overlaps the anchor
  // but no satellite satisfies them jointly.
  const trap: FacetEntry[] = [
    { mission: "m1", constellation: "c1", owner: "o1", inOrbit: true },
    { mission: "m2", constellation: "c2", owner: "o1", inOrbit: true },
  ];
  const trapOwners = new Set(["o1"]);

  /**
   * CHANGED 2026-08-28, and the direction of the change is the whole story of
   * this file. On 2026-08-27 this asserted that the healer REFUSED to break the
   * trap, because both other lists had ticks in them and were therefore the
   * reader's to keep. Under Sean's design there is no such category: a positive
   * click links into both other lists whatever they hold, so clicking o1 plots
   * both of o1's satellites and ticks m2 and c1 to say so.
   *
   * That is not the withdrawn defect wearing a new name. The defect was that
   * this happened as an unasked-for REPAIR, and on deselections, so a narrowing
   * could not survive. Here it happens because the reader clicked o1, and one
   * untick of m2 takes the second satellite straight back off.
   *
   * The convergence property the trap was built to test still holds: the fill
   * is read off the named satellites, so they all match afterwards and a second
   * identical click adds nothing.
   */
  it("links through the pairwise-overlap trap, and is a fixed point", () => {
    const sel: FacetSelection = { mission: new Set(["m1"]), constellation: new Set(["c2"]), owner: new Set(["o1"]) };
    expect(facetMatchCount(trap, sel, trapOwners)).toBe(0);
    const linked = linkAfterSelect(trap, sel, trapOwners, "owner", "o1");
    expect(linked.matchCount).toBe(2);
    expect(linked.added).toEqual({ mission: ["m2"], constellation: ["c1"] });
    // Fixed point: nothing left to iterate, in either direction.
    const again = linkAfterSelect(trap, linked.selection, trapOwners, "owner", "o1");
    expect(again.selection).toEqual(linked.selection);
    expect(again.added).toEqual({});
    const down = reportAfterDeselect(trap, linked.selection, trapOwners);
    expect(down.selection).toEqual(linked.selection);
    // And the reader's way back out is one untick, which sticks.
    const narrowed = reportAfterDeselect(trap, { ...linked.selection, mission: new Set(["m1"]) }, trapOwners);
    expect(narrowed.matchCount).toBe(1);
    expect(narrowed.added).toEqual({});
  });

  /**
   * CHANGED 2026-08-28. This used to prove the fill was read only from the
   * satellites that already cleared the reader's narrowing — "c2 belongs to the
   * m2 object, which the reader's mission tick excludes, so it is not offered".
   * The fill is now read from everything the click names, because that is what
   * makes a positive click's promise unconditional: click a value and you see
   * that value's satellites, with no state in which you do not.
   */
  it("fills from everything the click names, so the click always shows what it named", () => {
    const sel: FacetSelection = { mission: new Set(["m1"]), constellation: new Set(), owner: new Set(["o1"]) };
    const linked = linkAfterSelect(trap, sel, trapOwners, "owner", "o1");
    expect(linked.matchCount).toBe(2);
    expect(linked.added.constellation).toEqual(["c1", "c2"]);
    expect(linked.added.mission).toEqual(["m2"]);
  });

  /**
   * A POSITIVE CLICK CAN NEVER SHOW NOTHING. Swept over every value in every
   * list, from the bare catalog and from a narrowed one — this is the property
   * that lets the select-side "nothing matched" message be deleted rather than
   * left as unreachable furniture.
   */
  it("no click on any value in any list produces an empty result", () => {
    const narrowed = click(catalogEntries, bare(), "mission", METOC).selection;
    (["mission", "constellation", "owner"] as FacetName[]).forEach((facet) => {
      values(catalogEntries, facet).forEach((value) => {
        expect(linkAfterSelect(catalogEntries, bare(), shownOwners, facet, value).matchCount).toBeGreaterThan(0);
        expect(linkAfterSelect(catalogEntries, narrowed, shownOwners, facet, value).matchCount).toBeGreaterThan(0);
      });
    });
  });
});

describe("chips and status stay truthful and calm", () => {
  it("chip text follows the linked selection", () => {
    expect(facetChipText(0, 12)).toEqual({ text: "none", state: "empty" });
    expect(facetChipText(12, 12)).toEqual({ text: "all", state: "all" });
    expect(facetChipText(3, 12)).toEqual({ text: "3 of 12", state: "partial" });
  });

  /**
   * THE EMPTY STATE HAS NO VOICE AT ALL.
   *
   * `filterStatusMessage()` is deleted, not reworded. It was the only function
   * that mapped "the selection is empty" onto a sentence, and while it existed
   * every control added near it could call it — which is how "0 shown -
   * nothing selected" and "Show every satellite again" kept coming back on a
   * globe the reader had deliberately emptied. This pins the deletion.
   */
  it("exports no function that turns an empty selection into words", async () => {
    const main = await import("../src/main") as Record<string, unknown>;
    const emptyStateVoices = Object.keys(main).filter((name) => /^filterStatus|^emptyState|^describeEmpty/.test(name));
    expect(emptyStateVoices).toEqual([]);
  });

  /**
   * AND THE ONE SURVIVING MESSAGE IS NOT DEAD MACHINERY. It would be worth
   * deleting too if no reader could reach it, so this walks there by clicking:
   * click the GPS fleet, then untick Navigation in the mission list. Every GPS
   * object flies exactly that one mission, so unticking it leaves nothing — and
   * the reader did not ask for a zero, which is what makes it worth a line.
   */
  it("is reachable by clicking: click GPS, then untick the one mission GPS flies", () => {
    const linked = click(catalogEntries, bare(), "constellation", "GPS");
    expect(linked.matchCount).toBeGreaterThan(0);
    expect(linked.selection.mission).toEqual(new Set(["navigation"]));
    const settled = untick(catalogEntries, linked.selection, "mission", "navigation");
    // The mission list is now empty, which is the reader's own doing: silence.
    expect(settled.anyFacetEmpty).toBe(true);
    expect(describeFacetLinking(settled)).toBeNull();

    // Reached with ticks standing in all three lists instead: click GPS, click
    // GOES, then untick Navigation. Weather is still ticked, the GPS fleet is
    // still ticked, and the combination that is left matches nothing.
    const both = click(catalogEntries, linked.selection, "constellation", "GOES");
    const died = untick(catalogEntries, both.selection, "mission", "navigation");
    expect(died.selection.mission.size).toBeGreaterThan(0);
    expect(died.anyFacetEmpty).toBe(false);
    expect(died.matchCount).toBeGreaterThan(0);
  });

  /** The one thing that may speak, and the only thing: a change the reader did
   *  not type. `describeFacetLinking()` is the rail's single message channel
   *  and it has exactly one writer. */
  it("only a change the reader did not type produces a message", () => {
    const entries: FacetEntry[] = [
      { mission: "navigation", constellation: "GPS", owner: "U.S. Space Force", inOrbit: true },
      { mission: "weather", constellation: "GOES", owner: "NOAA / NASA", inOrbit: true },
    ];
    const owners = values(entries, "owner");
    // Ticks still standing in all three lists, and zero matches: the
    // combination died on the reader, so it says so.
    const died = reportAfterDeselect(entries, {
      mission: new Set(["navigation"]),
      constellation: new Set(["GOES"]),
      owner: new Set(["NOAA / NASA"]),
    }, owners);
    expect(describeFacetLinking(died)).toBe("Nothing matches that combination. Nothing was changed.");
    // The reader emptied the list themselves. Silence.
    const byHand = reportAfterDeselect(entries, {
      mission: new Set(),
      constellation: new Set(["GOES"]),
      owner: new Set(["NOAA / NASA"]),
    }, owners);
    expect(describeFacetLinking(byHand)).toBeNull();
    // A link speaks, because the ticks it made are the reader's answer.
    const linked = linkAfterSelect(entries, BARE, owners, "mission", "weather");
    expect(describeFacetLinking(linked, "METOC / weather")).toBe(
      "Also selected 1 fleet and 1 organization that METOC / weather satellites carry.",
    );
  });
});

describe("the owner facet lists every organization", () => {
  it("orders all owners with the audited priorities first and truncates nothing", () => {
    const counts = new Map<string, number>();
    catalogEntries.forEach((entry) => counts.set(entry.owner, (counts.get(entry.owner) ?? 0) + 1));
    const order = ownerFilterOrder(counts, ["NASA", "U.S. Navy"]);
    expect(order.length).toBe(counts.size);
    expect(counts.size).toBeGreaterThan(100); // 138 in the current catalog — far more than the old 18-row slice
    expect(order[0]).toBe("NASA");
    expect(order[1]).toBe("U.S. Navy");
    expect(new Set(order).size).toBe(order.length);
  });
});

describe("the rail says what Sean asked it to say", () => {
  const html = rawSources["../index.html"] ?? "";
  const css = rawSources["../src/styles.css"] ?? "";

  it("index.html carries the calm status line, not the warning block", () => {
    expect(html.length).toBeGreaterThan(0);
    expect(html).not.toContain("filter-warning");
    expect(html).toContain('id="filter-status"');
    expect(html).toContain("Show every satellite again");
  });

  /**
   * THE STRUCTURE, in Sean's own order: "start with 'Satellite Catalog' and to
   * the right 'x Selected' and a 'Clear' button and under that heading you'll
   * have the ALL LEO MEO GEO etc boxes... don't have 'catalog Filters' just
   * Mission Types, Constellations/Fleets, Owners/Organizations."
   */
  it("names the catalog, its three lists, and nothing that was cut", () => {
    // Comments stripped, because the page still EXPLAINS what came off it and
    // an assertion that cannot tell an explanation from a control would either
    // fail on the record or forbid keeping one.
    const markup = html.replace(/<!--[\s\S]*?-->/g, "");
    expect(markup).toContain("<h2>Satellite Catalog</h2>");
    expect(markup).toContain('id="catalog-clear"');
    expect(markup).toContain("Mission Types");
    expect(markup).toContain("Constellations / Fleets");
    expect(markup).toContain("Owners / Organizations");
    // The wrapper fold, its counter, and the per-list selection buttons.
    expect(markup).not.toContain("Catalog filters");
    expect(markup).not.toContain('id="filter-stack"');
    expect(markup).not.toContain("Select all");
    expect(markup).not.toContain("Clear this list");
    expect(markup).not.toContain("facet-only");
    // The sentence under the GEO subtype row: "that additional text stating
    // what they are needs to be deleted." The row itself stays.
    expect(markup).not.toContain("geo-filter-hint");
    expect(markup).toContain('data-geo-type="other-gso"');
    // The two arrangement toggles Sean asked to keep, by name.
    expect(markup).toContain("Sort by Number");
    expect(markup).toContain("Sort Alphabetically");
  });

  it("puts Find a satellite and Favorites below the catalog", () => {
    const catalog = html.indexOf('id="catalog-details"');
    const search = html.indexOf('id="search-details"');
    const favorites = html.indexOf('id="favorites-details"');
    expect(catalog).toBeGreaterThan(0);
    expect(search).toBeGreaterThan(catalog);
    expect(favorites).toBeGreaterThan(search);
  });

  it("styles the status as status, empty chips are not alarm-coloured, and the only-chip rule is gone", () => {
    expect(css.length).toBeGreaterThan(0);
    expect(css).not.toContain(".filter-warning");
    expect(css).toContain(".filter-status");
    expect(css).not.toMatch(/\.facet-state\[data-state="empty"\]\s*\{[^}]*--coral/);
    expect(css).not.toMatch(/\.filter-grid \.facet-only\s*\{/);
    expect(css).not.toMatch(/^\.filter-stack\s*\{/m);
    // A row worth nothing is still dimmed rather than hidden: hiding it would
    // claim the catalog does not contain the value.
    expect(css).toMatch(/\.filter-grid label\[data-context="none"\]\s*\{/);
  });
});

// Fixture-vs-live-catalog drift is guarded on the data machine by
// tests/test_catalog_facet_fixture.py, which reads the published artifact the
// bundler must never touch (the 44 GB public/data tree).
