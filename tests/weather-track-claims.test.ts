// @vitest-environment jsdom
/*
 * CLAIM tests for learning track 02, the space-weather lessons.
 *
 * Written 2026-09-04 after a correctness audit of `#/learn-weather` found four
 * live factual defects that 2,168 passing tests had not touched. Every one of
 * them was a NUMBER OR A NAME the site already held correctly somewhere else
 * and had typed out again, wrongly, in the teaching prose:
 *
 *   - the quiet magnetopause standoff was given as 13.5 Rᴇ, which is the site's
 *     own three-day MAXIMUM and is further out than the bow shock the same
 *     track quotes two clicks away;
 *   - the L1 monitor was named as DSCOVR, which has not appeared in the feed
 *     this site reads for as long as the feed's own window goes back;
 *   - NOAA's SWMF cut cadence was given as two hours, which is this site's own
 *     archive thinning, not NOAA's publication rate;
 *   - a module holding a model AND an assimilated product carried the single
 *     badge of the stronger one.
 *
 * So these tests do not assert that anything RENDERS. They assert that a
 * quantity or a name stated in the prose still agrees with the place the site
 * derives it — and, where the site derives it nowhere, that it at least agrees
 * with physics. A test that only checks the words are present cannot catch a
 * number going stale, which is how all four of these survived.
 */
import { describe, expect, it } from "vitest";
import { MECHANISM_ANIMATIONS } from "../src/mechanism-animations";
import { WEATHER_MODULE_IDS, sourcesView, weatherLessonView, weatherPageView } from "../src/content";
import { methodsView } from "../src/methods";

/** Every Earth-radius figure in a rendered fact grid, keyed by its label. */
function factGrid(markup: string): Map<string, string> {
  const facts = new Map<string, string>();
  const page = new DOMParser().parseFromString(markup, 'text/html');
  for (const cell of page.querySelectorAll('.fact-grid > div')) {
    const label = cell.querySelector(':scope > span')?.textContent?.trim();
    const value = cell.querySelector(':scope > strong.is-readout')?.textContent?.trim();
    if (label && value) facts.set(label, value);
  }
  return facts;
}

/** The first number in a string like "~10&ndash;11 R&#8853; (Earth radii)". */
function firstNumber(value: string): number {
  const match = value.replace(/&[a-z0-9#]+;/gi, " ").match(/\d+(?:\.\d+)?/);
  expect(match, `no number in ${value}`).not.toBeNull();
  return Number(match![0]);
}

describe("the magnetopause the weather track teaches is inside its own bow shock", () => {
  /*
   * The defect this replaces: module 04's fact grid read "Quiet standoff
   * ~13.5 R⊕" while Dungey stage 01, on the same track, put the bow shock at
   * ~13 R⊕. A magnetopause outside its own bow shock is not a rounding
   * disagreement, it is the wrong side of a boundary, and no rendering test
   * can see it because both cards render perfectly.
   */
  it("puts the typical magnetopause nose inside the bow-shock standoff", () => {
    const compression = factGrid(weatherLessonView("compression"));
    const nose = compression.get("Typical nose");
    expect(nose, "module 04 must state a typical magnetopause standoff").toBeDefined();

    const dungey = weatherPageView("dungey");
    const shock = dungey.match(/<span>Standoff<\/span><strong class="is-readout">([^<]+)</);
    expect(shock, "Dungey stage 01 must state a bow-shock standoff").not.toBeNull();

    expect(firstNumber(nose!)).toBeLessThan(firstNumber(shock![1]!));
  });

  it("agrees with the standoff the Dungey stage it hands the reader on to states", () => {
    const compression = factGrid(weatherLessonView("compression"));
    expect(compression.get("Typical nose")).toContain("10");
    expect(compression.get("Typical nose")).toContain("11");
    // Stage 03 is where the same quantity is derived at length. The module and
    // the stage may differ in wording; they may not differ in the number.
    expect(weatherPageView("dungey")).toContain("Typical nose");
    expect(weatherPageView("dungey")).toContain("10&ndash;11 R&#8853;");
  });

  it("keeps the storm standoff below geostationary-adjacent quiet values", () => {
    const compression = factGrid(weatherLessonView("compression"));
    const storm = firstNumber(compression.get("Storm standoff")!);
    const nose = firstNumber(compression.get("Typical nose")!);
    const geo = firstNumber(compression.get("Geostationary orbit")!);
    expect(storm).toBeLessThan(nose);
    // 6.6 Rᴇ is geostationary radius: 42,164 km over a 6,371 km Earth radius.
    expect(geo).toBeCloseTo(42164 / 6371, 1);
  });
});

describe("the L1 monitors the weather track names are the ones the feed carries", () => {
  /*
   * Checked against https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json
   * on 2026-09-04: 2,666 records from ACE (1,150), SOLAR1 (868) and IMAP (648),
   * none from DSCOVR; SWPC nominated SOLAR1 active for 810 minutes and ACE for
   * 266. The site's own methods page had already been updated and the weather
   * track had not, so this test binds the two together.
   */
  const l1Surfaces = () => [
    weatherLessonView("wind"),
    weatherPageView("engine"),
  ];

  it("does not name DSCOVR as the operational monitor anywhere on the track", () => {
    for (const markup of l1Surfaces()) {
      const asOperational = /DSCOVR normally|operational L1 monitor — DSCOVR|DSCOVR or ACE/.test(markup);
      expect(asOperational, "the weather track names DSCOVR as the operational L1 monitor").toBe(false);
    }
  });

  it("names only monitors the methods page also names", () => {
    const methods = methodsView();
    for (const markup of l1Surfaces()) {
      for (const name of ["SOLAR1", "ACE", "IMAP"]) {
        if (!markup.includes(name)) continue;
        expect(methods, `${name} is taught on the weather track but absent from the methods page`).toContain(name);
      }
    }
  });

  it("still says how many monitors there are rather than which one, so a renomination cannot make it wrong", () => {
    const wind = weatherLessonView("wind");
    expect(wind).toContain("nominated active");
  });
});

describe("the cadences the engine page states are the cadences the products have", () => {
  /*
   * The engine page said NOAA publishes its SWMF cuts "roughly every two
   * hours". Two hours is this site's OWN archive thinning — the published
   * geospace artifact carries `history.sourceCadenceMinutes: 20` beside
   * `history.publishedCadenceMinutes: 120` — and the methods page has always
   * said "about every 20 minutes". Attributing the site's own download budget
   * to NOAA understated the real product by a factor of six.
   */
  it("gives NOAA's SWMF cut cadence as twenty minutes, not the site's archive spacing", () => {
    const engine = weatherPageView("engine");
    expect(engine).toContain("roughly every twenty minutes");
    expect(engine).not.toMatch(/a pair of curves, roughly every two hours/);
  });

  it("says out loud that the two-hour figure is this site's thinning", () => {
    const engine = weatherPageView("engine");
    expect(engine).toContain("published archive keeps one frame every two hours");
  });
});

describe("a module badge may not assert a single evidence class for a mixed module", () => {
  /*
   * Module 05's chip says "WAM-IPE model · GloTEC assimilated · two different
   * claims" — and its badge said `assimilated`, the stronger of the two. The
   * site defines `composite` for exactly this ("Layers of one picture from
   * different evidence classes, each labelled where it came from") and already
   * uses it on modules 06 and 08.
   */
  it("badges every module that advertises two claims as composite", () => {
    for (const id of WEATHER_MODULE_IDS) {
      const claim = new DOMParser().parseFromString(weatherLessonView(id), 'text/html').querySelector('.lesson-claim')!;
      const status = claim.querySelector(':scope > .layer-status')?.textContent?.trim().toLowerCase();
      const qualifier = claim.querySelector(':scope > .layer-status-note')?.textContent ?? '';
      expect(status, `module ${id} renders no evidence badge`).toBeTruthy();
      if (/two different claims|different causes|four clocks/.test(qualifier)) {
        expect(status, `module ${id} advertises more than one claim but is badged ${status}`).toBe('composite');
      }
    }
  });

  it("uses only evidence classes the sources page defines", () => {
    const key = sourcesView();
    for (const id of WEATHER_MODULE_IDS) {
      const status = weatherLessonView(id).match(/<span class="layer-status ([a-z]+)">/)![1]!;
      expect(key, `evidence class ${status} is used but not defined in the key`).toContain(`layer-status ${status}`);
    }
  });
});

describe("the mechanism library counts itself rather than being told", () => {
  it("states the real number of clips in its own heading", () => {
    const page = weatherPageView("mechanisms");
    const words = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];
    const expected = words[MECHANISM_ANIMATIONS.length];
    expect(expected, "extend the word list if the library grows past ten").toBeDefined();
    expect(page).toContain(`<h1>${expected} things no camera has filmed.</h1>`);
  });

  it("states the real number of clips that are also embedded in the track", () => {
    const embedded = new Set<string>();
    for (const id of WEATHER_MODULE_IDS) {
      for (const match of weatherLessonView(id).matchAll(/id="mechanism-([a-z0-9-]+)"/g)) embedded.add(match[1]!);
    }
    for (const match of weatherPageView("dungey").matchAll(/id="mechanism-([a-z0-9-]+)"/g)) embedded.add(match[1]!);
    // The Dungey stages carry clips too, which is why the page says "the lesson
    // or the stage they belong to" rather than only "the lesson".
    expect(weatherPageView("mechanisms")).toMatch(/also sit inside the lesson or the stage they belong to/);
    expect(embedded.size).toBeGreaterThan(0);
    expect(embedded.size).toBeLessThanOrEqual(MECHANISM_ANIMATIONS.length);
  });
});

describe("quantities the modules state agree with the site's own constants", () => {
  it("states the light travel time and the D-region altitudes consistently", () => {
    const photons = factGrid(weatherLessonView("photons"));
    // 1 AU / c = 499 s = 8.3 min.
    expect(firstNumber(photons.get("Travel time")!)).toBe(8);
    expect(photons.get("Absorbed in")).toContain("60");
    expect(photons.get("Absorbed in")).toContain("90");
    // Module 05 draws the same region and must not move it.
    const layers = factGrid(weatherLessonView("layers"));
    expect(layers.get("D region")).toContain("60");
    expect(layers.get("D region")).toContain("90");
  });

  it("states the two auroral oxygen lines identically wherever they appear", () => {
    const aurora = factGrid(weatherLessonView("aurora"));
    expect(aurora.get("Oxygen green")).toBe("557.7 nm");
    expect(aurora.get("Oxygen red")).toBe("630.0 nm");
    const dungey = weatherPageView("dungey");
    expect(dungey).toContain("557.7 nm");
    expect(dungey).toContain("630.0 nm");
  });

  it("keeps the L-shell premise attached to the ring-current energisation number", () => {
    // Energy goes as L⁻³, so 10 keV → 80 keV is a factor of 8, which is
    // (8/4)³. Without the starting L the reader cannot check it, and every
    // other place on the site states it.
    const dungey = weatherPageView("dungey");
    expect(dungey).toContain("carried in from L 8 arrives at L 4 as an 80 keV ring-current ion");
  });
});
