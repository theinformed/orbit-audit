// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { proseBlocks } from "./prose-blocks";
import { CONTROL_SNAPSHOT } from "../src/orbit-inference";
import { ARCHIVE_ROWS, GPU_ACCEPTANCE, WORKED_MEAN_MOTION_REV_DAY, semiMajorAxisKm } from "../src/orbit-computation";
import { VERDICT_SNAPSHOT as VERDICT_SNAPSHOT_FOR_CH09 } from "../src/orbit-verdict";
import {
  CHAPTERS,
  CHAPTER_MAP,
  GEO_ALTITUDE,
  GEO_RADIUS,
  MU_EARTH,
  R_EARTH,
  circularSpeed,
  combinedBurn,
  hohmann,
  horizonSurfacePercent,
  planeChange,
  propellantFraction,
  satelliteFundamentalsIndexView,
  satelliteFundamentalsPageView,
  sunSynchronousInclination,
  visViva,
} from "../src/satellite-fundamentals";

/**
 * The satellite-fundamentals track.
 *
 * Three things are tested here and they are deliberately different in kind:
 *
 *   1. THE ARITHMETIC IS RE-DERIVED, not re-read. Every Δv and speed printed
 *      on the page is recomputed below from the *closed-form* expressions in
 *      the literature rather than from the module's own vis-viva helper, so a
 *      mistake in the helper cannot be blessed by a test that calls it.
 *   2. THE RENDERED STRINGS ARE COMPARED against those independent numbers.
 *      A figure on screen that drifts from the formula that produced it is
 *      the exact failure this project has paid for elsewhere.
 *   3. EVERY CONTROL NAMED IN A "SEE IT LIVE" RECIPE MUST EXIST. A recipe
 *      that names a control the reader cannot find is worse than no recipe,
 *      and the only way to keep that true is to check it against the real
 *      markup on every run.
 */

const html = Object.values(
  import.meta.glob("../index.html", { eager: true, query: "?raw", import: "default" }),
)[0] as string;
const mainSource = Object.values(
  import.meta.glob("../src/main.ts", { eager: true, query: "?raw", import: "default" }),
)[0] as string;

const index = satelliteFundamentalsIndexView();
const pages = CHAPTERS.map((chapter) => satelliteFundamentalsPageView(chapter.id));
const everything = index + pages.join("");

/** Strip tags and normalise entities, so prose can be measured as prose. */
function text(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&mdash;/g, "—")
    .replace(/&rarr;/g, "→")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

describe("constants and derived figures", () => {
  it("uses the published WGS-84 constants", () => {
    expect(MU_EARTH).toBe(398600.4418);
    expect(R_EARTH).toBe(6378.137);
  });

  it("derives the geostationary radius and altitude that the sources quote", () => {
    // IADC-02-01 Rev. 2 and NASA Earth Observatory: 42,164 km / 35,786 km.
    expect(GEO_RADIUS).toBeCloseTo(42164.17, 1);
    expect(GEO_ALTITUDE).toBeCloseTo(35786.03, 1);
  });

  it("matches published circular speeds", () => {
    expect(circularSpeed(R_EARTH + 400)).toBeCloseTo(7.6686, 3);
    expect(circularSpeed(GEO_RADIUS)).toBeCloseTo(3.0747, 3);
  });

  it("puts the sun-synchronous inclination where the closed form does", () => {
    // Paek & Sung, ISSFD 2019: 700 km -> 98.19 degrees.
    expect(sunSynchronousInclination(700)).toBeCloseTo(98.19, 1);
  });

  it("reproduces the horizon coverage fractions quoted on the orbits page", () => {
    expect(horizonSurfacePercent(550)).toBeCloseTo(3.97, 1);
    expect(horizonSurfacePercent(GEO_ALTITUDE)).toBeCloseTo(42.44, 1);
  });
});

describe("the Hohmann arithmetic is independently checkable", () => {
  const r1 = R_EARTH + 400;
  const r2 = GEO_RADIUS;

  /**
   * The textbook closed form, which is algebraically distinct from the
   * module's route through vis-viva. Agreement between the two is the check.
   */
  const burn1 = Math.sqrt(MU_EARTH / r1) * (Math.sqrt((2 * r2) / (r1 + r2)) - 1);
  const burn2 = Math.sqrt(MU_EARTH / r2) * (1 - Math.sqrt((2 * r1) / (r1 + r2)));

  it("agrees with the closed-form delta-v expressions", () => {
    const transfer = hohmann(r1, r2);
    expect(transfer.burn1).toBeCloseTo(burn1, 9);
    expect(transfer.burn2).toBeCloseTo(burn2, 9);
    expect(transfer.total).toBeCloseTo(burn1 + burn2, 9);
  });

  it("matches the figures published for a 400 km start", () => {
    const transfer = hohmann(r1, r2);
    expect(transfer.burn1).toBeCloseTo(2.397, 2);
    expect(transfer.burn2).toBeCloseTo(1.456, 2);
    expect(transfer.total).toBeCloseTo(3.854, 2);
    expect(transfer.transferHours).toBeCloseTo(5.29, 1);
  });

  it("prints those same numbers on the page", () => {
    const page = satelliteFundamentalsPageView("manoeuvre");
    const transfer = hohmann(r1, r2);
    for (const value of [transfer.burn1, transfer.burn2, transfer.total]) {
      expect(page).toContain(value.toFixed(3));
    }
  });

  it("keeps vis-viva consistent with the circular case", () => {
    expect(visViva(r1, r1)).toBeCloseTo(circularSpeed(r1), 12);
  });
});

describe("plane changes", () => {
  it("reproduces the published 28.5 degree cost at GEO", () => {
    expect(planeChange(circularSpeed(GEO_RADIUS), 28.5)).toBeCloseTo(1.514, 2);
  });

  it("shows the combined burn beating the separate one", () => {
    const transfer = hohmann(R_EARTH + 400, GEO_RADIUS);
    const combined = combinedBurn(transfer.vApogee, transfer.v2, 28.5);
    const separate = transfer.burn2 + planeChange(transfer.v2, 28.5);
    expect(combined).toBeCloseTo(1.824, 2);
    expect(separate).toBeCloseTo(2.970, 2);
    expect(combined).toBeLessThan(separate);
  });

  it("agrees with the law of cosines degenerating to a simple plane change", () => {
    const v = circularSpeed(GEO_RADIUS);
    expect(combinedBurn(v, v, 28.5)).toBeCloseTo(planeChange(v, 28.5), 12);
  });
});

describe("the rocket equation", () => {
  it("gives the propellant fractions quoted for each engine class", () => {
    expect(propellantFraction(1.5, 220) * 100).toBeCloseTo(50, 0);
    expect(propellantFraction(1.5, 320) * 100).toBeCloseTo(38, 0);
    expect(propellantFraction(1.5, 1600) * 100).toBeCloseTo(9, 0);
    expect(propellantFraction(1.5, 3000) * 100).toBeCloseTo(5, 0);
  });

  it("is monotonic in specific impulse, which is the whole argument", () => {
    const fractions = [220, 320, 1600, 3000].map((isp) => propellantFraction(1.5, isp));
    for (let i = 1; i < fractions.length; i += 1) {
      expect(fractions[i]!).toBeLessThan(fractions[i - 1]!);
    }
  });
});

describe("the track structure", () => {
  it("offers nine chapters, each with a door on the index", () => {
    // 8 -> 9 on 2026-09-20: chapter 09, "Made from scratch, every day" — the
    // public computation story. Deliberate count change, not drift.
    expect(CHAPTERS).toHaveLength(9);
    for (const chapter of CHAPTERS) {
      expect(index).toContain(`data-fundamentals-page="${chapter.id}"`);
      expect(index).toContain(chapter.title);
    }
  });

  it("gives every chapter a way back and a way on", () => {
    for (const page of pages) {
      expect(page).toContain("data-fundamentals-index");
      expect(page).toContain("fund-pager");
    }
  });

  it("falls back to the index rather than erroring on an unknown chapter", () => {
    expect(satelliteFundamentalsPageView("no-such-chapter")).toBe(index);
  });

  it("numbers the chapters in reading order", () => {
    expect(CHAPTERS.map((chapter) => chapter.index)).toEqual(["01", "02", "03", "04", "05", "06", "07", "08", "09"]);
  });

  it("ends every chapter with its sources", () => {
    for (const chapter of CHAPTERS) {
      expect(chapter.sources.length).toBeGreaterThanOrEqual(6);
      const page = satelliteFundamentalsPageView(chapter.id);
      expect(page).toContain("Sources for this chapter");
      for (const source of chapter.sources) expect(page).toContain(source.title);
    }
  });

  it("never reintroduces the empty glow box this page replaced", () => {
    // src/styles.css:1254 gives .diagram a 180px radial glow with three words
    // in it. That is the defect. It must not come back by copy-paste.
    expect(everything).not.toContain('class="diagram"');
  });
});

describe("all ten original modules survive", () => {
  it("maps every one of them into a real chapter", () => {
    expect(CHAPTER_MAP).toHaveLength(10);
    const ids = new Set(CHAPTERS.map((chapter) => chapter.id));
    for (const entry of CHAPTER_MAP) {
      expect(ids.has(entry.nowIn)).toBe(true);
      expect(entry.note.length).toBeGreaterThan(10);
    }
  });

  it("covers the subjects those ten modules taught", () => {
    const body = text(everything).toLowerCase();
    for (const subject of [
      "geosynchronous", "free fall", "ground track", "footprint",
      "ephemeris", "pseudorange", "wavelength", "faraday rotation",
      "neutral", "constellation",
    ]) {
      expect(body).toContain(subject);
    }
  });

  it("covers everything the owner asked for by name", () => {
    const body = text(everything).toLowerCase();
    for (const subject of [
      "user terminal", "gateway", "uplink", "downlink", "crosslink",
      "forward link", "return link", "bent-pipe", "regenerative",
      "transponder", "spot beam", "eirp", "g/t", "path loss",
      "link margin", "polarization", "vis-viva", "hohmann", "bi-elliptic",
      "plane change", "station-keeping", "rocket equation", "graveyard",
      "payload", "bus", "solar wind", "single event", "total ionizing dose",
      "deep dielectric", "south atlantic anomaly", "starlink",
    ]) {
      expect(body).toContain(subject);
    }
  });
});

describe("chapter 09 arithmetic is independently checkable", () => {
  // Same rule as the Hohmann suite above: the closed form is written out HERE,
  // not imported, so a bug in the module cannot bless itself.
  const muWgs72 = 398600.8;
  const revPerDay = 15.44218077;
  const nRadPerSecond = revPerDay * 2 * Math.PI / 86400;
  const independentA = Math.cbrt(muWgs72 / (nRadPerSecond * nRadPerSecond));

  it("derives the same semi-major axis the module computes", () => {
    expect(semiMajorAxisKm(WORKED_MEAN_MOTION_REV_DAY)).toBeCloseTo(independentA, 6);
    expect(independentA).toBeCloseTo(6811.8, 1);
  });

  it("prints exactly those numbers on the page", () => {
    const page = satelliteFundamentalsPageView("how-the-numbers-are-made");
    const aText = independentA.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    expect(page).toContain(`= ${aText} km`);
    expect(page).toContain(`near ${Math.round(independentA - 6378.137)} km`);
    expect(page).toContain(`${(nRadPerSecond * 1000).toFixed(4)}×10⁻³ rad/s`);
  });

  it("quotes the acceptance record and the bundle counts it claims", () => {
    const page = satelliteFundamentalsPageView("how-the-numbers-are-made");
    expect(GPU_ACCEPTANCE.disagreements).toBe(0);
    expect(page).toContain(GPU_ACCEPTANCE.comparisons.toLocaleString("en-US"));
    expect(page).toContain(ARCHIVE_ROWS.toLocaleString("en-US"));
    // Bundle-derived counts must be the frozen snapshot's, not retyped copies.
    expect(page).toContain(VERDICT_SNAPSHOT_FOR_CH09.objectsScanned.toLocaleString("en-US"));
    expect(page).toContain(VERDICT_SNAPSHOT_FOR_CH09.eventsPublished.toLocaleString("en-US"));
  });

  it("animates only behind a reduced-motion guard, in both animated figures", () => {
    const page = satelliteFundamentalsPageView("how-the-numbers-are-made");
    for (const letter of ["C", "D"]) {
      const start = page.indexOf(`data-computation-figure="${letter}"`);
      expect(start).toBeGreaterThan(-1);
      const figure = page.slice(start, start + 3000);
      expect(figure).toContain("prefers-reduced-motion: no-preference");
    }
  });
});

describe("prose length — a wall of text is a defect even when it is true", () => {
  it("never runs a single block past 100 words", () => {
    expect(proseBlocks(everything).filter(block => block.words > 100)).toEqual([]);
  });

  it("breaks each chapter into several sections rather than one scroll", () => {
    for (const chapter of CHAPTERS) {
      expect(chapter.sections.length).toBeGreaterThanOrEqual(4);
    }
  });
});

describe("see it live", () => {
  const recipes = [...everything.matchAll(/<aside class="fund-live">([\s\S]*?)<\/aside>/g)]
    .map((match) => match[1] ?? "");

  it("puts a recipe in every chapter", () => {
    for (const chapter of CHAPTERS) {
      expect(satelliteFundamentalsPageView(chapter.id)).toContain("fund-live");
    }
    expect(recipes.length).toBeGreaterThanOrEqual(9);
  });


  it("only names controls the reader can actually find", () => {
    // The Dungey-cycle recipes on the sibling track set this rule: a recipe
    // that names a control that does not exist is worse than no recipe. The
    // only way to keep it true is to check it against the real markup.
    // Both sides are entity-decoded: index.html writes &rarr; and &amp; where
    // the recipe writes the character the reader sees.
    const decode = (value: string) => value
      .replace(/&amp;/g, "&").replace(/&rarr;/g, "\u2192").replace(/&mdash;/g, "\u2014");
    const markup = decode(html + mainSource);
    const named = new Set<string>();
    for (const recipe of recipes) {
      for (const match of recipe.matchAll(/<em>([^<]+)<\/em>/g)) named.add(decode(match[1] ?? ""));
    }
    expect(named.size).toBeGreaterThan(10);
    const missing = [...named].filter((label) => !markup.includes(label));
    expect(missing).toEqual([]);
  });

  it("only sends the reader to views the site actually has", () => {
    // Every view openContent() handles. NOT "the nav views in index.html" — that
    // stopped being the same set on 2026-08-21, when "learn-layers" came out of
    // the top nav and moved to a door inside Learn space weather. It is still a
    // route, and every cross-link here still resolves to it.
    const views = new Set(["explore", "now", "events", "learn-orbits", "learn-weather", "learn-layers", "connections", "transit", "sources"]);
    for (const match of everything.matchAll(/data-fundamentals-goto="([^"]+)"/g)) {
      expect(views.has(match[1] ?? "")).toBe(true);
    }
  });
});

describe("the gate figure must agree with the rule it is drawing", () => {
  // WHY THIS EXISTS. On 2026-09-08 the separation requirement was added to the
  // label gate: a lane must ALSO show the payload rate standing ten times clear
  // of the passive floor. The self-history lane went from open to shut that day
  // -- and this chapter's hardcoded snapshot still said `permitted: true`, so
  // the published figure rendered "GATE PASSED" and "MANOEUVRE — inferred" for
  // a lane the live bundle called shut.
  //
  // No test caught it. The figure rendered, the chapter's other assertions
  // passed, and a reader was told the opposite of what the data said. Tying the
  // drawn verdict to the same arithmetic the pipeline uses is what makes that
  // drift impossible to repeat quietly.
  const TARGET_RATE = 0.001;

  for (const [lane, item] of Object.entries(CONTROL_SNAPSHOT)) {
    it(`derives ${lane}'s verdict from its own numbers`, () => {
      const clearsFalseAlarmBound = item.passiveUpper < TARGET_RATE;
      const clearsSeparation = item.boundRatio >= item.requiredRatio;
      expect(item.permitted).toBe(clearsFalseAlarmBound && clearsSeparation);
    });

    it(`${lane} states a separation ratio and the bar it must clear`, () => {
      expect(Number.isFinite(item.boundRatio)).toBe(true);
      expect(item.requiredRatio).toBe(10);
    });
  }

  it("keeps both lanes shut while neither clears the separation bar", () => {
    // Not a tautology: it pins the CURRENT published position, so re-opening a
    // lane has to be a deliberate edit to this test rather than a silent drift.
    expect(CONTROL_SNAPSHOT.selfHistory.permitted).toBe(false);
    expect(CONTROL_SNAPSHOT.cohort.permitted).toBe(false);
  });
});
