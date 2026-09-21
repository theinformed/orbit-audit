import explorerSource from "../src/main.ts?raw";
import stylesSource from "../src/styles.css?raw";
import { describe, expect, it } from "vitest";

import {
  FACT_CELL_OVERRIDES,
  classificationBasisEvidence,
  classificationChipEvidence,
  factGridSpans,
  factValueVoice,
  hasPublishedDescription,
  orbitHistoryActionClause,
  ownershipRows,
  satelliteCardFacts,
  satelliteChips,
  satelliteDetailFacts,
  satelliteOrbitFacts,
} from "../src/main";
import {
  ARCHIVE_OFFLINE_ACTION,
  ARCHIVE_OFFLINE_BODY,
  ARCHIVE_OFFLINE_STATE,
  ARCHIVE_OFFLINE_TITLE,
  isArchiveOfflineStatus,
} from "../src/orbit-history";

/**
 * The satellite card's diet.
 *
 * The owner's complaint (handoff §4.6): the card runs to eight sections and
 * overflows a 1440-tall window, with `ORBIT LEO` implied by `ALTITUDE 955 km`,
 * `PERIOD` and `VELOCITY` being each other, and MILSATCOM stated three times.
 *
 * And the opposing constraint (§4.9), which is why this is not simply "cut
 * things": a third of the catalog is MISSING published facts, and the card
 * responded by deleting the "Owner / operator" row for 2,545 of 8,000 objects.
 * The card was simultaneously too long and too quiet.
 *
 * These drive the exact function the renderer calls, not a copy of it.
 */
const base = {
  organization: "U.S. Space Force",
  ownerLabel: "United States",
  organizationSource: "curated" as const,
  constellationFact: "Independent",
  facet: "communications",
  sector: "military",
};

/**
 * The orbital half of the card, split out of `satelliteCardFacts` on
 * 2026-08-19 so that "where it is" and "who runs it" are two named groups
 * rather than one list called "Satellite facts". The assertions below are the
 * same ones, moved to the function that now owns the rows.
 */
const orbitBase = {
  orbitLabel: "LEO",
  altitudeNow: "955 km",
  periodMinutes: 104.1,
  inclinationDeg: 53.22,
  perigee: "540 km",
  apogee: "560 km",
  subSatellitePoint: "12.3° N, 45.6° W",
  elementAge: "1.2 days old",
};

describe("values that were on the card twice", () => {
  /**
   * Velocity is exactly `v = √(μ(2/r − 1/a))` — determined by the altitude and
   * the period, both of which stay on the card. It carried no information.
   */
  it("no longer prints a velocity", () => {
    const labels = [...satelliteOrbitFacts(orbitBase), ...satelliteCardFacts(base)].map(([label]) => label);
    expect(labels).not.toContain("Velocity now");
    expect(labels.join(" ")).not.toMatch(/km\/s/);
  });

  /**
   * DELIBERATELY REVERSED, 2026-08-27. These three used to be asserted as ONE
   * ROW carrying one string, `LEO · 955 km now · 104.1 min period`. The row
   * was right about the facts and wrong about the reader twice over: it was
   * the only value on the card written as a sentence, and one string gets one
   * voice, which `factValueVoice` picks by LENGTH. Past 44 characters a value
   * is prose. The two GEO subtypes are long enough to push the string over;
   * LEO, MEO and HEO are not. So the SAME row printed cyan on an HEO card and
   * grey on the GEO card beside it, with nothing less certain or less measured
   * about either. See `satelliteOrbitFacts` for the measured strings.
   *
   * The regime is still derived from the period — that is why the three cells
   * are neighbours — but they are three cells, so each value is judged on its
   * own and the class name can no longer decide how its neighbours are set.
   */
  it("states orbit class, altitude and period as three cells in the grid's own grammar", () => {
    const rows = satelliteOrbitFacts(orbitBase);
    expect(rows.find(([label]) => label === "Orbit type")![1]).toBe("LEO");
    expect(rows.find(([label]) => label === "Altitude now")![1]).toBe("955 km");
    expect(rows.find(([label]) => label === "Period")![1]).toBe("104.1 min");
    // The sentence is gone, and so is the word "Orbit" standing alone.
    expect(rows.map(([label]) => label)).not.toContain("Orbit");
    expect(rows.map(([, value]) => value).join(" ")).not.toMatch(/min period/);
  });

  /**
   * The regression this split exists to close, driven through the REAL
   * classifier: the two values that are measurements must be classified as
   * measurements whatever the orbit class beside them is called.
   */
  it("gives the altitude and the period the same voice for a long class name as a short one", () => {
    const short = satelliteOrbitFacts(orbitBase);
    const long = satelliteOrbitFacts({ ...orbitBase, orbitLabel: "Other GSO", periodMinutes: 1436.1 });
    for (const label of ["Altitude now", "Period"]) {
      const a = short.find(([l]) => l === label)![1];
      const b = long.find(([l]) => l === label)![1];
      expect(factValueVoice(a), label).toBe("readout");
      expect(factValueVoice(b), label).toBe("readout");
    }
    // The old single string is what used to differ, and it is worth keeping the
    // proof of that here: it is the negative control for the split.
    expect(factValueVoice("LEO · 955 km now · 104.1 min period")).toBe("readout");
    expect(factValueVoice("Other GSO / near-GEO · 35,699 km now · 1436.1 min period")).toBe("prose");
  });

  it("still says which kind of GEO, because that is not derivable by eye", () => {
    const geo = satelliteOrbitFacts({ ...orbitBase, orbitLabel: "Other GSO", periodMinutes: 1420 });
    expect(geo.find(([label]) => label === "Orbit type")![1]).toBe("Other GSO");
  });

  /**
   * Every orbit class the pipeline can publish — `derive_orbit` emits LEO, MEO,
   * GEO, IGSO, HEO and OTHER, and a GEO is split again into the two subtypes by
   * `classifyGeoSubtype`. The class cell must be the value itself, unhedged and
   * unadorned, for all of them.
   */
  it("prints every class the pipeline publishes as the value of one cell", () => {
    for (const label of ["LEO", "MEO", "IGSO", "HEO", "OTHER", "Geostationary", "Other GSO"]) {
      const rows = satelliteOrbitFacts({ ...orbitBase, orbitLabel: label });
      expect(rows.find(([l]) => l === "Orbit type")![1], label).toBe(label);
    }
  });

  /**
   * The class cell is pinned rather than classified, so that it is the same on
   * every card. `FACT_CELL_OVERRIDES` is the whole list of pinned cells, and it
   * is asserted here rather than in a copy of it.
   *
   * It is pinned to a HALF COLUMN since 2026-08-27. It used to take the whole
   * row, which meant every card carried one full-width row holding a
   * three-letter value with an empty half beside it - the thing Sean was
   * pointing at when he asked whether the orbit type and the launch date could
   * sit side by side.
   */
  it("pins the orbit class cell so a long class name cannot change its treatment", () => {
    const pinned = FACT_CELL_OVERRIDES.get("Orbit type")!;
    expect(pinned.voice).toBe("readout");
    expect(pinned.spansRow).toBe(false);
  });

  /**
   * THE THREE IDENTITY LINES LOOK LIKE EACH OTHER, whatever they say.
   *
   * Sean: "those three lines with the owner, country, fleet - do those look
   * okay? ... they all have grey labels above them but they aren't the same
   * font." They were not: `factValueVoice` sorts by a 44-character cliff, so a
   * six-character operator was an answer and a sixty-eight-character one was
   * grey prose - the same kind of fact in two type voices, decided by how long
   * a company calls itself. Driven over the real values from the two
   * spacecraft in his screenshots.
   */
  it("gives every identity value the same voice, at any length", () => {
    const identityLabels = [
      "Owner / operator", "Operator's country", "Registering state",
      "Country / registry", "Constellation / fleet",
    ];
    for (const label of identityLabels) {
      const pinned = FACT_CELL_OVERRIDES.get(label)!;
      expect(pinned, label).toBeDefined();
      expect(pinned.voice, label).toBe("answer");
      expect(pinned.spansRow, label).toBe(false);
    }
    // The negative control: left to the length rule, these two values from the
    // same block of the same kind of card come out in different voices.
    expect(factValueVoice("SpaceX")).toBe("answer");
    expect(factValueVoice(
      "Aerospace Tianmu (Chongqing) Satellite Technology, a CASIC subsidiary",
    )).toBe("prose");
  });

  /**
   * These three were published for every object and were on the card already —
   * at the bottom of a shut provenance list at 9.28 px, the smallest type on
   * the surface. Inclination in particular is the latitude band the spacecraft
   * can ever reach, which is the question this audience asks first.
   */
  it("promotes inclination, perigee and apogee into the open section", () => {
    const rows = satelliteOrbitFacts(orbitBase);
    const labels = rows.map(([label]) => label);
    expect(labels.some((label) => label.startsWith("Inclination"))).toBe(true);
    expect(labels).toContain("Perigee");
    expect(labels).toContain("Apogee");
    expect(rows.find(([label]) => label.startsWith("Inclination"))![1]).toBe("53.2°");
    // TWO FACTS, TWO CELLS. Sean, 2026-08-31: "dont combine perigee and
    // apogee." A perigee and an apogee are different numbers about different
    // points in the orbit, and "540 km / 560 km" asked the reader to split
    // them. Splitting them also makes the grid twelve cells, which is what
    // retired the full-width cell the tests below used to pin.
    expect(rows.find(([label]) => label === "Perigee")![1]).toBe("540 km");
    expect(rows.find(([label]) => label === "Apogee")![1]).toBe("560 km");
  });

  /**
   * THE GLOSS CAME OFF THIS LABEL, AND IT COST SOMETHING. It read
   * "Inclination · latitude band" so the label carried what the number MEANS
   * and the value could stay a value. But a grid column is as wide as its
   * widest cell, and measured at 390 px that label was 114 px against a widest
   * VALUE of 112 -- so every column on the card was sized by a gloss rather
   * than by any number in it. Sean, looking at the result: "narrow!"
   *
   * So this now asserts the opposite of what it used to, deliberately: the
   * label is the bare quantity. The latitude-band fact is not defended
   * anywhere else on the card, and that is a real loss worth revisiting if the
   * width ever stops mattering.
   */
  it("keeps the inclination label to the quantity, so it does not set the column width", () => {
    const label = satelliteOrbitFacts(orbitBase).map(([l]) => l).find((l) => l.startsWith("Inclination"))!;
    expect(label).toBe("Inclination");
  });

  it("says the orbit is still being propagated instead of inventing an altitude", () => {
    const row = satelliteOrbitFacts({ ...orbitBase, altitudeNow: null }).find(([label]) => label === "Altitude now")!;
    expect(row[1]).toBe("propagating…");
    // Never blank and never a zero: one reads as a broken cell, the other as a
    // spacecraft at sea level.
    expect(row[1]).not.toBe("");
    expect(row[1]).not.toMatch(/^0/);
  });

  /**
   * The same rule for a period that cannot be stated. It is defensive — every
   * published record carries a finite period today — but the cell is the only
   * place the absence could show, so the absence is written in words there.
   */
  it("says so in words when the period is not a number, rather than printing NaN", () => {
    for (const periodMinutes of [Number.NaN, 0, Number.POSITIVE_INFINITY]) {
      const row = satelliteOrbitFacts({ ...orbitBase, periodMinutes }).find(([label]) => label === "Period")!;
      expect(row[1], String(periodMinutes)).toBe("Period unavailable");
    }
  });

  it("says the same about a sub-satellite point it does not have yet", () => {
    const row = satelliteOrbitFacts({ ...orbitBase, subSatellitePoint: null })
      .find(([label]) => label === "Sub-satellite point")!;
    expect(row[1]).toMatch(/propagating…/);
  });

  /**
   * The sector row is not "dropped when the badge states it" any more — it is
   * gone from the grid entirely, because the operator class is a CHIP in the
   * card's head for every object that has one. It used to print as a bare
   * lowercase word under a caption reading "Sector".
   */
  it("never prints a sector row, because the operator class is a chip", () => {
    const labels = satelliteCardFacts(base).map(([label]) => label);
    expect(labels).not.toContain("Sector");
  });
});

/**
 * The other half. Cutting alone would have made a card that is shorter and
 * still silent about who owns the spacecraft for a third of the catalog.
 */
describe("the owner row that used to vanish for 2,545 objects", () => {
  it("keeps both rows when the operator is genuinely a different name", () => {
    expect(ownershipRows("Iridium Communications", "United States", "curated")).toEqual([
      ["Owner / operator", "Iridium Communications"],
      ["Country / registry", "United States"],
    ]);
  });

  /**
   * The repair: not a guess, but saying WHOSE answer the name is. The project
   * reports attribution and never infers it, and its own doctrine is that when
   * no operator is published "the site says the registry's answer and stops".
   */
  it("says the registry's answer is the registry's, instead of hiding the row", () => {
    expect(ownershipRows("United States", "United States", "registry")).toEqual([
      ["Owner / operator", "United States · registry record"],
    ]);
  });

  /** Calling a curator's identification a registry record would be false provenance. */
  it("does not claim a registry record for a curated identification", () => {
    expect(ownershipRows("United States", "United States", "curated")).toEqual([
      ["Owner / operator", "United States"],
    ]);
  });

  it("compares names case- and whitespace-insensitively, as before", () => {
    expect(ownershipRows("  united states ", "United States", "registry"))
      .toEqual([["Owner / operator", "United States · registry record"]]);
  });

  it("falls back to the registry alone when no organization is published", () => {
    expect(ownershipRows("", "Japan")).toEqual([["Country / registry", "Japan"]]);
  });

  /**
   * What it must NEVER do: print a negative finding. "No operator published"
   * is a claim about the world that this site's sources cannot support.
   */
  it("never asserts that no operator exists", () => {
    for (const rows of [ownershipRows("", "Japan"), ownershipRows("United States", "United States", "registry")]) {
      expect(JSON.stringify(rows)).not.toMatch(/no operator|not published|unknown/i);
    }
  });

  /**
   * THE COUNTRY THAT WAS THE BUILDER'S.
   *
   * SARI-1 and SARI-2 are Saudi university payloads and the card said Brazil,
   * because the registry attributes them to the country of the integrator that
   * filed for them. The registering state is a real, citable fact and is not
   * overwritten here -- the repair is that the operator's country now has a row
   * of its own, so the reader sees the two answers and which is which.
   */
  it("shows the operator's country and the registering state as two labelled rows", () => {
    expect(ownershipRows("Saudi Arabia", "Brazil", "gcat-state", "Saudi Arabia")).toEqual([
      ["Operator's country", "Saudi Arabia"],
      ["Registering state", "Brazil"],
    ]);
  });

  it("never labels a country as the operator, however it was arrived at", () => {
    const rows = ownershipRows("Israel", "Germany", "gcat-state", "Israel");
    expect(rows.map(([label]) => label)).not.toContain("Owner / operator");
  });

  it("keeps a named operator above both countries", () => {
    expect(ownershipRows("Heriot-Watt University", "Netherlands", "curated", "United Kingdom")).toEqual([
      ["Owner / operator", "Heriot-Watt University"],
      ["Operator's country", "United Kingdom"],
      ["Registering state", "Netherlands"],
    ]);
  });

  it("says the country once when the two catalogues agree", () => {
    expect(ownershipRows("", "Japan", undefined, "Japan")).toEqual([["Country / registry", "Japan"]]);
    expect(ownershipRows("", "Japan", undefined, null)).toEqual([["Country / registry", "Japan"]]);
  });
});

describe("the citation the site was holding and never showing", () => {
  /**
   * `purposeSource` is published for 5,623 of 8,000 objects and was rendered
   * nowhere, while the same audit recorded that a third of purposes read as
   * uncited prose. It is now a link beside the purpose label.
   */
  it("renders purposeSource as a link beside the description it supports", () => {
    expect(explorerSource).toContain("purposeSource");
    // `buildStackCard` -> `buildSatelliteCard`, 2026-08-28. It never built a
    // stack, and after that date there is no stack for it to build into.
    const build = explorerSource.slice(explorerSource.indexOf("private buildSatelliteCard("));
    const card = build.slice(0, build.indexOf("\n  private "));
    expect(card).toMatch(/data-card-purpose-source/);
    expect(card).toMatch(/https\?:/);
    const render = explorerSource.slice(explorerSource.indexOf("private renderCardFields("));
    const body = render.slice(0, render.indexOf("\n  private "));
    // The provenance list states the MECHANISM behind the category chip now.
    expect(body).toMatch(/Category evidence/);
    expect(body).toMatch(/classificationBasisEvidence/);
  });

  it("is read through the narrow accessor rather than by widening the shared type", () => {
    // Bounded by the type's own closing brace rather than by a character
    // count. The property is "this field is declared INSIDE the narrow
    // accessor type", and a 400-character window was standing in for that —
    // so adding a fourth documented field to the type failed the test while
    // the property it names stayed true.
    expect(explorerSource).toMatch(/type CatalogEvidenceFields = \{[^}]*organizationSource\?/);
    expect(explorerSource).toMatch(/type CatalogEvidenceFields = \{[^}]*purposeSource\?/);
  });
});

describe("a satellite that does two jobs", () => {
  /**
   * GALAXY 30 is a television broadcast satellite that also carries the WAAS
   * transponder, which broadcasts GPS corrections. Both facts are true and the
   * card has to hold them without letting either one displace the other.
   *
   * Before this existed the site had one `mission` field, so the choice was
   * between calling a television satellite "navigation" and never mentioning
   * WAAS at all. It said nothing.
   */
  const base = {
    organization: "Intelsat",
    ownerLabel: "United States",
    constellationFact: "—",
    facet: "communications",
    sector: "commercial" as const,
  };

  it("names the hosted payload beside the primary mission, not instead of it", () => {
    const rows = satelliteCardFacts({
      ...base,
      secondaryMissions: [{ mission: "navigation", role: "augmentation", system: "WAAS" }],
    });
    const also = rows.find(([label]) => label === "Also carries");
    expect(also).toBeDefined();
    expect(also![1]).toContain("WAAS");
    // The primary is untouched: nothing in the card claims this is a
    // navigation satellite.
    expect(rows.map(([label]) => label)).not.toContain("Mission");
  });

  it("says nothing at all when there is no second role", () => {
    const rows = satelliteCardFacts(base);
    expect(rows.map(([label]) => label)).not.toContain("Also carries");
  });

  it("keeps the row count honest — one line, however many roles", () => {
    const rows = satelliteCardFacts({
      ...base,
      secondaryMissions: [
        { mission: "navigation", role: "augmentation", system: "WAAS" },
        { mission: "navigation", role: "augmentation", system: "EGNOS" },
      ],
    });
    const also = rows.filter(([label]) => label === "Also carries");
    expect(also).toHaveLength(1);
    expect(also[0]![1]).toBe("WAAS augmentation · EGNOS augmentation");
  });
});


/**
 * THE TWO CHIPS, AND THE ONE THING THEY MUST NEVER DO.
 *
 * The defect this replaces, on TIANMU-1 11: the card printed the category
 * `METOC / WEATHER` and then, three lines below it, "Its purpose has not been
 * independently verified for this object: the meteorological or environmental
 * observation label comes from the category CelesTrak files this object under".
 * A label and a retraction of the label, sixty words apart, on a card whose
 * standing complaint is that it is text-heavy.
 *
 * The evidence for that retraction is `classificationBasis`, which the catalog
 * publishes on every row. It is the chip's state now, and the sentence is gone.
 *
 * NOT `classificationConfidence`. Tianmu-1 11 carries "high" confidence AND the
 * hedge, because the two fields answer different questions — the pipeline's own
 * comment says confidence is deliberately not a read-off of the mechanism. A
 * chip drawn from confidence would have called that card corroborated.
 */
describe("the category and operator chips", () => {
  const tianmu = { mission: "weather", facet: "weather", sector: "civil", basis: "source-group" };

  it("marks a CelesTrak-category label as claimed rather than corroborated", () => {
    expect(classificationChipEvidence("source-group")).toBe("claimed");
    expect(satelliteChips(tianmu).every((chip) => chip.evidence === "claimed")).toBe(true);
  });

  /**
   * The military-classification lane publishes `assessed` for PLA, Russian and
   * allied systems, and asks in its own comment for exactly this: an assessment
   * by named analysts is a real, citable claim and it is still not the operator
   * saying so, "so it is deliberately NOT in the interface's CORROBORATED_BASES
   * and the card draws the same dashed, dimmed, question-marked chip it draws
   * for a bare name match".
   */
  it("draws an analysts' assessment as claimed, and says whose assessment it is", () => {
    expect(classificationChipEvidence("assessed", "medium")).toBe("claimed");
    expect(classificationBasisEvidence("assessed")).toMatch(/independent analysts/i);
    expect(classificationBasisEvidence("assessed")).toMatch(/no operator or government has published/i);
    // One entry per basis. Both lanes reached for this key on the same day.
    expect(explorerSource.match(/^\s*"assessed":/gm) ?? []).toHaveLength(1);
  });

  /**
   * Basis and confidence are written independently, so a reviewer can leave a
   * per-object basis AND a "low" grade: "I checked, and I am still not sure".
   * The chip has to show the doubt rather than the mechanism alone.
   */
  it("will not call a low-confidence row corroborated, whatever its basis says", () => {
    for (const basis of ["web-corroborated", "norad-id", "exact-name", "radio-licence"]) {
      expect(classificationChipEvidence(basis, "high"), basis).toBe("corroborated");
      expect(classificationChipEvidence(basis, "medium"), basis).toBe("corroborated");
      expect(classificationChipEvidence(basis, "low"), basis).toBe("claimed");
      expect(classificationChipEvidence(basis, "LOW "), basis).toBe("claimed");
    }
  });

  it("marks a name-pattern label claimed too — a family name is not a check on an object", () => {
    expect(classificationChipEvidence("name-pattern")).toBe("claimed");
  });

  it("marks the four bases that are tied to THIS object as corroborated", () => {
    for (const basis of ["web-corroborated", "norad-id", "exact-name", "radio-licence"]) {
      expect(classificationChipEvidence(basis), basis).toBe("corroborated");
    }
  });

  it("treats an unclassified or unrecognised basis as claimed, never as corroborated", () => {
    expect(classificationChipEvidence("unclassified")).toBe("claimed");
    expect(classificationChipEvidence(undefined)).toBe("claimed");
    expect(classificationChipEvidence("something-a-future-build-invents")).toBe("claimed");
  });

  it("puts the reason on the chip, so the retraction survives the sentence being deleted", () => {
    const [category] = satelliteChips(tianmu);
    expect(category!.why).toContain("CelesTrak");
    expect(category!.why).toContain("Nothing has been checked against this spacecraft");
    expect(classificationBasisEvidence("no-such-basis")).toMatch(/Nothing has been checked/);
  });

  it("renders NO category chip where the catalog establishes no category", () => {
    const chips = satelliteChips({ mission: "other", facet: "other", sector: "unknown", basis: "unclassified" });
    expect(chips).toHaveLength(0);
  });

  it("renders NO operator chip for an unknown sector — an absent chip, never an Unknown chip", () => {
    const chips = satelliteChips({ mission: "weather", facet: "weather", sector: "unknown", basis: "source-group" });
    expect(chips.map((chip) => chip.kind)).toEqual(["category"]);
  });

  it("drops the operator chip where the category chip already IS the operator class", () => {
    for (const facet of ["milsatcom", "commercial-satcom", "military-other"]) {
      const chips = satelliteChips({ mission: "communications", facet, sector: "military", basis: "exact-name" });
      expect(chips.map((chip) => chip.kind), facet).not.toContain("operator");
    }
  });

  it("names each operator class the catalog actually carries", () => {
    for (const [sector, label] of [
      ["military", "Military"],
      ["civil", "Civil / government"],
      ["commercial", "Commercial"],
      ["academic", "Academic"],
      ["mixed", "Mixed"],
    ] as const) {
      const chips = satelliteChips({ mission: "weather", facet: "weather", sector, basis: "norad-id" });
      expect(chips.find((chip) => chip.kind === "operator")!.label, sector).toBe(label);
    }
  });
});

/**
 * WHEN THE BACKGROUND SECTION EXISTS AT ALL.
 *
 * Sean: "make the section degrade gracefully: good prose where it exists,
 * nothing at all where it doesn't. Do not generate filler prose to fill empty
 * sections." The catalog has no empty `purpose` — it has 2,451 objects whose
 * purpose is this site's own generated hedge, which is filler that already
 * exists. That is what has to be recognised.
 *
 * Matched on the sentence `template_purpose()` emits rather than on the
 * `purposeKind` flag, because that flag reads "template" for the 65 SatNOGS
 * radio-licence descriptions, which are real cited prose about the object.
 */
describe("which spacecraft get a Satellite Background section", () => {
  it("shows the section for a real published description", () => {
    expect(hasPublishedDescription(
      "Suomi NPP, the first of the Joint Polar Satellite System spacecraft, carries VIIRS, CrIS and ATMS.",
    )).toBe(true);
  });

  it("shows it for a SatNOGS radio-licence description, which is real prose the flag calls a template", () => {
    expect(hasPublishedDescription(
      "The public catalog does not identify this spacecraft's payload. What is on record is its radio licence: "
      + "its transmitters are filed under the ITU Earth Exploration service in the SatNOGS community database.",
    )).toBe(true);
  });

  it("knows the generated read-out is not a published description, in all three shapes", () => {
    // The shape shipped from 2026-08-20: fact-led, one clause of gap.
    expect(hasPublishedDescription(
      "No public source names this spacecraft's payload, so this site does not claim one. What the registry "
      + "records is a low Earth orbit, the band used by imaging, weather, science and large broadband "
      + "constellations — about 483 km up on a 94.3-minute period, launched 2023-12-25.",
    )).toBe(false);
    // ...and the two apology-led shapes it replaced, which a release built
    // before that change still carries. A stale artifact must not start
    // claiming it holds a published description.
    expect(hasPublishedDescription(
      "Its purpose has not been independently verified for this object: the meteorological or environmental "
      + "observation label comes from the category CelesTrak files this object under.",
    )).toBe(false);
    expect(hasPublishedDescription(
      "The public catalog does not identify this spacecraft's payload or mission, so this site does not claim one.",
    )).toBe(false);
  });

  /**
   * Sean: "why do we still have satellite cards without information? I've asked
   * you to fix this a dozen times." Nothing was blank; 2,383 cards LED with
   * nineteen words about what was unknown. The section renders the registry's
   * own record now, so it renders for every object that has one -- and still
   * renders nothing at all, heading included, when there is nothing.
   */
  it("renders the section for any description, and nothing at all for none", () => {
    const build = explorerSource.slice(explorerSource.indexOf("private buildSatelliteCard("));
    const card = build.slice(0, build.indexOf("\n  private "));
    // The condition moved from the raw description to what the card will actually
    // PRINT, because since 2026-08-27 those are two different things: a long
    // description is printed as a shortened opening, and a thin one can gain a
    // researched paragraph about its fleet. The rule this test is about is
    // unchanged -- no paragraphs means no section, heading included.
    expect(card).toMatch(/background\.hidden = shape\.paragraphs\.length === 0/);
    expect(card).not.toMatch(/background\.hidden = !described/);
    expect(stylesSource).toContain(".card-section[hidden] { display: none; }");
  });

  it("hides it for an empty or missing description rather than inventing one", () => {
    expect(hasPublishedDescription("")).toBe(false);
    expect(hasPublishedDescription(null)).toBe(false);
  });
});

/**
 * THE ORDER SEAN SPECIFIED: owner/operator, country, constellation and the
 * launch date - the facts that do not change - then the whole orbit block.
 *
 * REVERSED DELIBERATELY, 2026-08-27. "Launched" used to be asserted as the
 * LAST row of the grid, under the live measurements, and the assertion below
 * now says the opposite. Sean, holding STARLINK-11600: "see how the grid of
 * blue text values has sort of a gap in it? ... reshuffle so that there are 2
 * columns of 3 rows without a gap." Moving the launch date up to the fixed
 * facts is what leaves EXACTLY seven live measurements below the orbit class -
 * altitude, period, inclination, perigee/apogee, sub-satellite point, element
 * age - which is that two-by-three block. It is also where the launch date
 * belongs on its own merits: it is a property of the object, like the operator
 * and the registry, not a reading that moves with the clock.
 */
describe("the Satellite Details grid", () => {
  const rows = satelliteDetailFacts({
    identity: satelliteCardFacts({
      organization: "NOAA / NASA",
      ownerLabel: "United States",
      organizationSource: "curated",
      constellationFact: "No named fleet identified",
    }),
    orbit: satelliteOrbitFacts({
      orbitLabel: "LEO",
      altitudeNow: "857 km",
      periodMinutes: 101.4,
      inclinationDeg: 98.8,
      perigee: "825 km",
      apogee: "829 km",
      subSatellitePoint: "80.9° S, 98.0° W",
      elementAge: "0.24 days",
    }),
    launchDate: "2011-10-28",
  });
  const labels = rows.map(([label]) => label);

  it("opens on who runs it and when it went up, before anything that moves", () => {
    expect(labels[0]).toBe("Owner / operator");
    expect(labels[1]).toBe("Country / registry");
    expect(labels[2]).toBe("Constellation / fleet");
    expect(labels[3]).toBe("Launched");
  });

  it("puts the whole orbit block after them, in one grid rather than a second fold", () => {
    for (const label of ["Orbit type", "Altitude now", "Period", "Inclination", "Perigee", "Apogee", "Sub-satellite point", "Element age"]) {
      expect(labels.indexOf(label), label).toBeGreaterThan(labels.indexOf("Launched"));
    }
  });

  /**
   * THE BLOCK SEAN ASKED FOR, COUNTED. Seven live measurements after the orbit
   * class - eight cells with the class itself, four rows of two, nothing left
   * over. Asserted as a count and an order rather than by eye, because the
   * whole complaint was about a shape.
   *
   * It was six until 2026-08-31, when Sean split the perigee/apogee cell in
   * two: "dont combine perigee and apogee... then bring down element days next
   * to it. that way perigee and apigee can be next to one another." The pairing
   * that produces is what the order below pins.
   */
  it("leaves exactly the seven live measurements below the orbit class", () => {
    const measured = labels.slice(labels.indexOf("Orbit type") + 1);
    expect(measured).toEqual([
      "Altitude now",
      "Period",
      "Inclination",
      "Perigee",
      "Apogee",
      "Sub-satellite point",
      "Element age",
    ]);
    // The evenness that matters is the WHOLE grid's, not this slice's: these
    // seven sit under four identity cells and the orbit class, so the grid is
    // twelve. Asserted in "has no cell that wants the full row" below, against
    // `factGridSpans`, which is the rule that actually decides the shape.
  });

  /**
   * AND NOTHING WANTS THE FULL ROW ANY MORE, which is the point of the split.
   *
   * The sub-satellite point used to be last and used to take the whole row: an
   * odd number of facts leaves exactly one cell with nothing to pair with, and
   * `factGridSpans` gave that cell the row. It went last so the one full-width
   * row sat at the card's bottom edge rather than mid-card, and it was laid
   * label-beside-value so the width was used rather than imitating a gap.
   *
   * Splitting perigee from apogee made the count EVEN, so both of those
   * workarounds are gone and every cell in the grid is the same shape. The
   * coordinate pair now pairs with the element age, which is what Sean asked
   * for. This asserts the property that matters - no cell takes the row - not
   * the identity of whichever cell happens to be last.
   */
  it("has no cell that wants the full row, because the count is even", () => {
    expect(labels.length % 2).toBe(0);
    expect(factGridSpans(rows).filter(Boolean).length).toBe(0);
  });

  /**
   * THE GAP ITSELF, driven through the shipped layout rule.
   *
   * `Orbit type` takes the whole row, and a full-width cell has to begin one.
   * With three ownership cells above it and no launch date among them, the
   * third sat alone in the left column with the right half of its row empty -
   * which is exactly what Sean was pointing at. `factGridSpans` places the
   * cells the way the grid does and reports which take the row; walking that
   * placement must never leave a half-row empty in front of a full-width cell,
   * and must never end with a lone cell either.
   */
  it("never leaves a cell beside an empty half", () => {
    const spans = factGridSpans(rows);
    let column = 0;
    for (let index = 0; index < spans.length; index += 1) {
      if (spans[index]) {
        expect(column, `cell ${index} (${labels[index]}) begins a full row`).toBe(0);
        continue;
      }
      column = column === 0 ? 1 : 0;
    }
    expect(column, "the last row is filled").toBe(0);
  });

  /**
   * The catalogue does not publish one fixed number of ownership rows -
   * `ownershipRows` returns one, two or three depending on whether the
   * operator, the registering state and the operator's country are the same
   * answer, "Also carries" appears only on a spacecraft with a second job, and
   * any value past 24 characters claims a row of its own. So the rule is
   * driven over every shape the card can actually take, not over one.
   */
  it("holds for every shape the ownership block can take", () => {
    const orbit = satelliteOrbitFacts({
      orbitLabel: "Other GSO",
      altitudeNow: "35,699 km",
      periodMinutes: 1436.1,
      inclinationDeg: 5.4,
      perigee: "35,690 km",
      apogee: "35,801 km",
      subSatellitePoint: "0.1° N, 100.0° W",
      elementAge: "0.9 days",
    });
    const shapes: Array<Array<[string, string]>> = [
      [["Owner / operator", "SpaceX"], ["Country / registry", "United States"], ["Constellation / fleet", "Starlink"]],
      [["Country / registry", "United States"], ["Constellation / fleet", "Independent"]],
      [["Owner / operator", "SES"], ["Operator's country", "Luxembourg"], ["Registering state", "United Kingdom"], ["Constellation / fleet", "Independent"]],
      [["Owner / operator", "United States Space Force"], ["Constellation / fleet", "Independent"], ["Also carries", "GPS III navigation payload"]],
    ];
    for (const identity of shapes) {
      for (const launchDate of ["2025-02-27", null]) {
        const shape = satelliteDetailFacts({ identity, orbit, launchDate });
        const spans = factGridSpans(shape);
        let column = 0;
        const where = `${identity.length} identity rows, launch ${String(launchDate)}`;
        for (let index = 0; index < spans.length; index += 1) {
          if (spans[index]) {
            expect(column, `${where}: ${shape[index]![0]} begins a full row`).toBe(0);
            continue;
          }
          column = column === 0 ? 1 : 0;
        }
        expect(column, `${where}: the last row is filled`).toBe(0);
      }
    }
  });

  it("omits the launch row rather than printing a blank one", () => {
    const without = satelliteDetailFacts({ identity: [], orbit: [], launchDate: null });
    expect(without).toHaveLength(0);
  });
});

/**
 * THE ORBIT ARCHIVE IS A FULL-WIDTH BOX AGAIN, and the four states survive the
 * move.
 *
 * It spent 2026-08-21 to 08-27 as a cell of the fact grid, which read well as
 * a fact and cost the grid its shape. Sean: "we just move it down to its own
 * box like we had it before, right between the grid of values and the 2d
 * ground track box." What must NOT change with the box is the honesty
 * contract: the shard is ~25 MB and is never fetched to draw a card, so four
 * different absences get four different sentences and none of them is a
 * number.
 */
describe("what the orbit-archive box says", () => {
  it("claims nothing at all when nothing has been downloaded", () => {
    // The ordinary case, on every card, before a reader has paid for a shard.
    // A box that said "History not loaded" would be asking the reader to
    // decode an internal state; saying nothing about the contents is both
    // shorter and more honest, and the state is still on the aria-label.
    expect(orbitHistoryActionClause("History not loaded")).toBe("");
  });

  it("keeps the other four distinguishable, and none of them a number", () => {
    expect(orbitHistoryActionClause(ARCHIVE_OFFLINE_STATE)).toBe(" — server offline");
    expect(orbitHistoryActionClause("History unavailable")).toBe(" — could not be read");
    expect(orbitHistoryActionClause("No stored elements")).toBe(" — no stored elements");
    expect(orbitHistoryActionClause("1,284 element sets on file")).toBe(" — 1,284 element sets");
    expect(orbitHistoryActionClause("1 element set on file")).toBe(" — 1 element set");
    // The number is never touched - only the trailing "on file", which is what
    // pushed the label past the one line the three boxes share.
    expect(orbitHistoryActionClause("12,345 element sets on file")).toContain("12,345");
    const clauses = [
      "History not loaded",
      ARCHIVE_OFFLINE_STATE,
      "History unavailable",
      "No stored elements",
      "1,284 element sets on file",
    ].map(orbitHistoryActionClause);
    expect(new Set(clauses).size).toBe(5);
    for (const clause of clauses.slice(0, 4)) expect(clause).not.toMatch(/\d/);
  });

  /**
   * THE ARCHIVE SERVER BEING OFFLINE IS NOT "COULD NOT BE READ", AND THIS IS
   * THE TEST THAT SAYS SO.
   *
   * Since 2026-08-27 the shards are on bigmem-PC and the VPS proxies them, so
   * the site can now be looking at a working release on a machine that is not
   * answering. "History unavailable" means a published file could not be read
   * -- a fault in what was shipped, which sends whoever investigates it to the
   * publish pipeline. Merging the two would send them to the wrong machine.
   *
   * The classifier is checked in the same breath, because the distinction is
   * only worth anything if the right statuses reach it: a 502/503/504 is the
   * gateway saying it could not reach the archive host, while a 404 is the
   * archive host itself answering, and that is a fact about a file.
   */
  it("says the archive server is offline as its own state, not as unavailable", () => {
    expect(ARCHIVE_OFFLINE_STATE).not.toBe("History unavailable");
    expect(orbitHistoryActionClause(ARCHIVE_OFFLINE_STATE))
      .not.toBe(orbitHistoryActionClause("History unavailable"));
    expect(isArchiveOfflineStatus(502)).toBe(true);
    expect(isArchiveOfflineStatus(503)).toBe(true);
    expect(isArchiveOfflineStatus(504)).toBe(true);
    // Negative controls. A 404 is the archive host answering; a 200 never
    // reaches this path at all; undefined is a failure with no status, which
    // is not evidence about any machine.
    expect(isArchiveOfflineStatus(404)).toBe(false);
    expect(isArchiveOfflineStatus(500)).toBe(false);
    expect(isArchiveOfflineStatus(200)).toBe(false);
    expect(isArchiveOfflineStatus(undefined)).toBe(false);
  });

  /**
   * What the dialog says, checked as words rather than as a shape, because the
   * whole point of the state is that a reader is told something specific.
   */
  it("tells a reader the machine is down, apologises, and offers a way to ask", () => {
    expect(ARCHIVE_OFFLINE_TITLE).toBe("The archive server is offline");
    expect(ARCHIVE_OFFLINE_BODY).toMatch(/not answering right now/);
    expect(ARCHIVE_OFFLINE_BODY).toMatch(/sorry/i);
    expect(ARCHIVE_OFFLINE_BODY).toMatch(/Sean and Derek/);
    // NO ADDRESS ON A PUBLIC PAGE. Sean built the feedback box instead of
    // publishing his mail, and this is the guard that keeps a later edit from
    // quietly putting one back.
    expect(ARCHIVE_OFFLINE_BODY).not.toMatch(/@/);
    expect(ARCHIVE_OFFLINE_BODY).not.toMatch(/mailto:/);
    expect(ARCHIVE_OFFLINE_TITLE + ARCHIVE_OFFLINE_ACTION).not.toMatch(/@/);
  });

  /**
   * ONE LINE, LIKE THE TWO BOXES BELOW IT. Measured on the built bundle at
   * 1440 on 2026-08-27: the box is 281 px wide, roughly 5.7 px a character at
   * the shipped size, and a label past about 240 px wraps and stands half a
   * box taller than its neighbours. "Open orbit history — 1,284 element sets
   * on file →" measured 257 px and wrapped; the clause below is 233 px. 42
   * characters is that budget written as a length this test can check without
   * a browser, and the count is given the widest value the archive could
   * plausibly reach.
   */
  it("keeps the whole label inside the one line the three boxes share", () => {
    for (const state of [
      "History not loaded",
      ARCHIVE_OFFLINE_STATE,
      "History unavailable",
      "No stored elements",
      "99,999 element sets on file",
    ]) {
      const label = `Open orbit history${orbitHistoryActionClause(state)} →`;
      expect(label.length, label).toBeLessThanOrEqual(42);
    }
  });

  /**
   * The voice is still taken from the STATE, so a count is tabular mono and an
   * absence is not - the same rule that governed the cell.
   */
  it("still sets a count as a measurement and an absence as a word", () => {
    expect(factValueVoice("1,284 element sets on file")).toBe("readout");
    expect(factValueVoice("History not loaded")).toBe("answer");
    expect(factValueVoice("History unavailable")).toBe("answer");
    expect(factValueVoice("No stored elements")).toBe("answer");
  });
});
