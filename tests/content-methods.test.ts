// @vitest-environment jsdom
import indexMarkup from "../index.html?raw";
import { describe, expect, it } from "vitest";
import { overlongProse } from "./prose-blocks";
import { WEATHER_MODULE_IDS, sourcesView, weatherLessonView, weatherLessons, weatherPageView } from "../src/content";
import { RADIAL_RULER } from "../src/radial-ruler";

describe("environment teaching disclosures", () => {
  it("separates time-varying WAM-IPE peak geometry from column TEC and D-RAP", () => {
    const content = sourcesView();
    expect(content).toContain("WAM-IPE peak height + electron density");
    expect(content).toContain("HmF2 and NmF2 grids every five minutes");
    expect(content).toContain("quasi-neutral sum");
    expect(content).toContain("unsupported columns remain holes");
    expect(content).toContain("GloTEC ionosphere");
    expect(content).toContain("TEC is electrons integrated through a column");
    expect(content).toContain("D-RAP HF absorption");
    expect(content).toContain("vertical ground–ionosphere–ground path");
  });

  it("states exact OVATION history and selected-time no-data behavior", () => {
    const content = sourcesView();
    expect(content).toContain("NOAA publicly distributes only the latest native numeric grid");
    expect(content).toContain("neither is mirrored from the other");
    expect(content).toContain("historical selection remains strict by forecast-valid time");
    expect(content).toContain("No data is a scientific result");
  });

  it("explains the two real SWMF cuts without claiming a live volume", () => {
    const content = sourcesView();
    expect(content).toContain("Two intersecting GSM model cuts");
    expect(content).toContain("z=0 x-y plane");
    expect(content).toContain("y=0 x-z plane");
    expect(content).toContain("not a full 3-D volume");
    expect(content).toContain("Full 3-D SWMF through NASA CCMC");
    expect(content).toContain("asynchronous CCMC research runs");
  });

  it("keeps native and mapped RBE views scientifically distinct", () => {
    const content = sourcesView();
    expect(content).toContain("MODEL-NATIVE EQUATORIAL FLUX");
    expect(content).toContain("PITCH-RESOLVED DIPOLE-MAPPED ELECTRON VOLUME");
    expect(content).toContain("r=L cos²(λ)");
    expect(content).toContain("not native three-dimensional RBE output");
    // Methods must describe what the site actually opens on — the raymarched
    // omnidirectional volume with every published energy folded in — and must
    // still say the rest are reachable. This text was stale for a while: it
    // described a single-pitch bounce shell long after the default became the
    // raymarched volume, which is why the assertion now names the real one.
    expect(content).toContain("raymarched");
    expect(content).toContain("all four published energies folded into one volume");
    expect(content).toContain("one fixed 10¹–10⁵·⁵ ramp in every energy view");
    expect(content).toContain("remains selectable");
    expect(content).toContain("not native three-dimensional RBE output, particle density");
  });

  it("teaches users to compare dimensionality and valid time", () => {
    const content = weatherLessons();
    expect(content).toContain("One picture can contain different dimensions");
    expect(content).toContain("dimension + valid time + status");
  });
});

/**
 * The two long-form sections of the space-weather track.
 *
 * These assert USER-VISIBLE prose, not symbol names, because a symbol survives
 * a feature being unreachable and a sentence does not. The cross-file test is
 * the one that earns its place: it re-reads `index.html` and refuses any
 * control name the recipe quotes that the page does not actually have, which
 * is the failure mode a "see it for yourself" recipe has — instructions that
 * name a toggle the reader cannot find. Adding an invented control name to
 * that list was checked to fail before this was committed.
 */
describe("the Dungey cycle page", () => {
  it("names the cycle, its author and the single interaction behind it", () => {
    const content = weatherPageView("dungey");
    expect(content).toContain("One interaction, and every structure that follows from it");
    expect(content).toContain("Dungey cycle");
    expect(content).toContain("who worked it out in 1961");
    expect(content).toContain("a supersonic, magnetised plasma running into a planetary dipole");
  });

  it("keeps the physical one-line explanation of each structure", () => {
    const content = weatherPageView("dungey");
    // The bow-shock sentence is quoted almost verbatim from the project
    // owner's own wording; it is the reason this section exists.
    expect(content).toContain(
      "The solar wind moves faster than any wave that could warn the plasma ahead of the obstacle, so a shock forms — the same reason a supersonic jet has one.",
    );
    expect(content).toContain("Pressure balance, and nothing more complicated than that");
    expect(content).toContain("about 13.5 Earth radii on a very quiet day to about 7 during a storm");
    expect(content).toContain("plasma sheet itself is not drawn");
    expect(content).toContain("ions drift westward, electrons eastward");
    expect(content).toContain("Same trap, different tenants");
  });

  it("only tells the reader to switch on controls index.html really has", () => {
    const content = weatherPageView("dungey") + WEATHER_MODULE_IDS.map(weatherLessonView).join("");
    expect(content).toContain("See the Dungey cycle for yourself");
    // Every control the recipe and the stage cards name, checked against the
    // page. `&amp;` in the prose is the literal `&amp;` in index.html too.
    for (const control of [
      "Solar wind &amp; IMF",
      "Magnetosphere",
      "NOAA MHD cross-section",
      "Solar-wind flow — projected U + tracers",
      "Annotation: extracted boundary curves",
      "Annotation: empirical boundary models",
      "Auroral oval",
      "Radiation belts",
      // "Plasmasphere" until 2026-08-18: the grain cloud left the rail and its
      // boundary moved to the Current conditions page, so the recipe names the
      // ring current instead — the other trapped population, which does still
      // have a control.
      //
      // "Ring current" until 2026-08-20, when that control became "Plasma sheet
      // → ring current": the inner plasma sheet went onto the same switch,
      // because it is the SUPPLY and they are one injection seen at two radii.
      // The check itself is unchanged and is exactly what caught the rename —
      // the recipe was still sending a reader to a control that no longer had
      // that name.
      "Plasma sheet &rarr; ring current",
    ]) {
      expect(content, `the recipe never mentions ${control}`).toContain(control);
      expect(indexMarkup, `index.html has no control called ${control}`).toContain(control);
    }
    for (const cameraButton of ["cross-section-view", "polar-view"]) {
      expect(indexMarkup, `index.html has no #${cameraButton}`).toContain(`id="${cameraButton}"`);
    }
  });
});

describe("photons and plasma, on module 01", () => {
  it("separates photons from plasma without letting one predict the other", () => {
    const content = weatherLessonView("photons");
    expect(content).toContain("Billiard balls and waves");
    expect(content).toContain("arrive eight minutes later");
    expect(content).toContain("30 to 60 minutes of warning");
    expect(content).toContain("You cannot read the solar-wind speed off the X-ray flux");
  });
});

describe("the physics-engine page", () => {
  it("separates what is measured from what is modelled", () => {
    const content = weatherPageView("engine");
    expect(content).toContain("How this picture is built, and what it cannot know");
    expect(content).toContain("one point in space</strong>, 30 to 60 minutes upwind");
    expect(content).toContain("Two intersecting sheets and a pair of curves");
    expect(content).toContain("the equatorial cut at z = 0 and the noon–midnight meridional cut at y = 0");
  });

  it("describes the construction the code actually implements", () => {
    const content = weatherPageView("engine");
    expect(content).toContain("A tilted centred dipole");
    expect(content).toContain("Chapman–Ferraro image dipole");
    expect(content).toContain("Harris (1962) current-sheet tail");
    expect(content).toContain("fourth-order Runge–Kutta");
    expect(content).toContain("found, not asserted");
  });

  it("states the calibration, its published residual and its refusal", () => {
    const content = weatherPageView("engine");
    expect(content).toContain("exact linear least squares in log space");
    expect(content).toContain("where the real model output exists, this picture is fitted to it");
    expect(content).toContain("FIT RMS");
    expect(content).toContain("outside 4–18 Earth radii");
  });

  it("states every limitation plainly rather than in a footnote", () => {
    const content = weatherPageView("engine");
    expect(content).toContain("A single upstream sample is not the wind that arrives");
    expect(content).toContain("Two cuts are not a volume");
    expect(content).toContain("nominal</em> for 549 of those minutes");
    expect(content).toContain("the L1 feed does not publish it");
    expect(content).toContain("Topology is the claim; positions are not");
    expect(content).toContain("An empty globe is a scientific result");
  });

  it("explains the compressed radial scale the toolbar label no longer carries", () => {
    const content = weatherPageView("engine");
    expect(content).toContain("Why the distances on the globe are not to scale");
    expect(content).toContain("Surface to geostationary orbit (6.6 Earth radii): logarithmic");
    expect(content).toContain("Geostationary orbit to 7.35 Earth radii: the joint");
    expect(content).toContain("7.35 out to 13 Earth radii: linear");
    expect(content).toContain("Beyond 13 Earth radii: tapered");
    expect(content).toContain("is not proportional to a real distance");
    // The four bands must agree with the ruler the scene actually uses.
    expect(RADIAL_RULER.taperStartRe).toBe(13);
    expect(RADIAL_RULER.taperEndRe).toBe(24);
    expect(RADIAL_RULER.anchorRe).toBeCloseTo(6.6, 1);
    expect(RADIAL_RULER.noseRampEndRe).toBe(7.35);
    // And the page must keep saying where the shape claim STOPS being exact,
    // which is the half a reader can check against a storm they lived through.
    expect(content).toContain("below 7.35 Earth radii the drawn flare is understated");
  });
});

/**
 * The redesign's own guards.
 *
 * Sean's verdict on the page this replaced was that the modules "don't go
 * anywhere" and there was "no content". These tests are the negative controls
 * for exactly that: a card may only ADVERTISE an entry point it really has,
 * every entry point must resolve to a real page, and every "switch this on"
 * button must name a control `index.html` actually contains. Adding a module
 * with a clip row and no clip was checked to fail before this was committed.
 */
describe("the space-weather track's eight lessons", () => {
  it("has no 180px diagram box left on it", () => {
    // The glow box was the visual signature of a placeholder nobody filled,
    // and there were eight of them above the fold's worth of scroll.
    expect(weatherLessons()).not.toContain('class="diagram"');
    for (const id of WEATHER_MODULE_IDS) expect(weatherLessonView(id)).not.toContain('class="diagram"');
  });

  it("makes every module card a real target that opens a real page", () => {
    const index = weatherLessons();
    const opened = [...index.matchAll(/data-weather-lesson="([a-z-]+)"/g)].map((m) => m[1]!);
    expect(new Set(opened)).toEqual(new Set(WEATHER_MODULE_IDS));
    for (const id of WEATHER_MODULE_IDS) {
      const page = weatherLessonView(id);
      // A page, not the index bounced back at the reader.
      expect(page, `module ${id} does not open its own page`).toContain("data-weather-index");
      expect(page).not.toContain('id="weather-index"');
      expect(page).toContain("WHY IT HAPPENS");
    }
  });

  it("opens all three long-form pages, and none of them is the index", () => {
    for (const page of ["dungey", "mechanisms", "engine"]) {
      const markup = weatherPageView(page);
      expect(markup, `${page} falls through to the index`).not.toContain('id="weather-index"');
      expect(markup).toContain("data-weather-index");
    }
    expect(weatherLessons()).toContain('data-weather-page="dungey"');
    expect(weatherLessons()).toContain('data-weather-page="mechanisms"');
    expect(weatherLessons()).toContain('data-weather-page="engine"');
  });

  it("never advertises an entry point the module does not have", () => {
    const index = weatherLessons();
    const cards = index.split('<article class="lesson-card module-card">').slice(1);
    expect(cards).toHaveLength(WEATHER_MODULE_IDS.length);
    for (const card of cards) {
      const id = /data-weather-lesson="([a-z-]+)"/.exec(card)?.[1] ?? "";
      const page = weatherLessonView(id);
      expect(card.includes('class="is-clip"'), `${id} claims a clip`).toBe(page.includes("<video"));
      expect(card.includes('class="is-live"'), `${id} claims a globe layer`).toBe(page.includes("data-open-layer"));
      // A module with nothing on the globe says so instead of growing a
      // button that switches on something else.
      expect(card.includes('class="is-gap"'), `${id} claims a gap`).toBe(!page.includes("data-open-layer"));
    }
  });

  it("only offers to switch on layers index.html really has", () => {
    const track = WEATHER_MODULE_IDS.map(weatherLessonView).join("");
    const ids = [...track.matchAll(/data-open-layer="([a-zA-Z-]+)"/g)].map((m) => m[1]!);
    expect(ids.length).toBeGreaterThan(8);
    for (const id of new Set(ids)) {
      expect(indexMarkup, `index.html has no #${id}`).toContain(`id="${id}"`);
    }
  });

  it("prints the camera glyph the button actually carries", () => {
    // Module 04 shipped a review draft quoting the meridional camera as
    // "(∅)" — U+2205 EMPTY SET — while the button in index.html carries
    // "⊘", U+2298 CIRCLED DIVISION SLASH. A recipe that prints a symbol the
    // control does not have is the same defect as naming a control that does
    // not exist, and it is invisible in review because the two glyphs differ
    // by a stroke.
    const track = [weatherLessons(), weatherPageView("dungey"), ...WEATHER_MODULE_IDS.map(weatherLessonView)].join("");
    for (const glyph of ["\u2298", "\u2299"]) {
      if (!track.includes(glyph)) continue;
      expect(indexMarkup, `index.html has no button carrying ${JSON.stringify(glyph)}`).toContain(`>${glyph}<`);
    }
    // And the near-miss glyphs must not appear at all.
    for (const wrong of ["\u2205", "\u2609", "\u25CB"]) {
      expect(track, `the track quotes ${JSON.stringify(wrong)}, which is not a button on this site`).not.toContain(wrong);
    }
  });

  it("keeps the track's prose in blocks a reader can finish", () => {
    const surfaces = [weatherLessons(), ...WEATHER_MODULE_IDS.map(weatherLessonView),
      ...["dungey", "engine", "mechanisms"].map(weatherPageView)];
    for (const markup of surfaces) expect(overlongProse(markup)).toEqual([]);
  });
});
