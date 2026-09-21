import { describe, expect, it } from "vitest";
import { WEATHER_MODULE_IDS, weatherLessonView, weatherLessons, weatherPageView } from "../src/content";
import { MECHANISM_ANIMATIONS, mechanismLibraryRuntime } from "../src/mechanism-animations";
import { LAYER_PAGE_COUNTS, layerPageView, layerPagesIndexView } from "../src/layer-pages";
import { countWordCap } from "../src/count-words";

/**
 * The term contract and the closers.
 *
 * Sean, on the videos: "there are terms that are on the page that i'm not
 * defining." The audit behind docs/PLAN-learn-page-pedagogy.md found twenty-odd
 * of them, of which Kp and L-shell between them drove five layer pages while
 * being defined nowhere on the site. These assertions look brittle — they pin
 * phrases — and that is the point: each one is a definition a reader was
 * promised, and an edit that deletes one should fail a test that names it
 * rather than silently returning the page to asserting in a vocabulary it never
 * issued.
 *
 * The derived-count assertions are a different kind of pin. The index's doors
 * carried hand-written copies of facts the data already held, and two of the
 * three had gone stale: "6 min 32 s" against 7:12 of rendered clips, and "Ten
 * pages" against eleven that render. Asserting the rendered string equals the
 * computed one is the only form of this test that survives the next re-render.
 */

const modulePages = WEATHER_MODULE_IDS.map((id) => [id, weatherLessonView(id)] as const);

describe("the index quotes counts it computed rather than counts someone typed", () => {
  it("prints the mechanism library's real clip count and total runtime", () => {
    const index = weatherLessons();
    expect(index).toContain(`${MECHANISM_ANIMATIONS.length} clips &middot; ${mechanismLibraryRuntime()}`);
    // The two stale strings this replaced, by name, so a revert is loud.
    expect(index).not.toContain("6 min 32 s");
  });

  it("computes that runtime from the entries rather than from a constant", () => {
    // 1:27 + 1:09 + 1:19 + 1:11 + 1:00 + 1:06 = 432 s at the time of writing,
    // which is 7:12 and not the 6:32 the door used to claim.
    const seconds = MECHANISM_ANIMATIONS.reduce((total, m) => {
      const [minutes, rest] = m.runtime.split(":");
      return total + Number(minutes) * 60 + Number(rest);
    }, 0);
    expect(mechanismLibraryRuntime()).toBe(`${Math.floor(seconds / 60)} min ${seconds % 60} s`);
  });

  it("prints the number of layer pages that actually render", () => {
    const index = weatherLessons();
    expect(LAYER_PAGE_COUNTS.total).toBeGreaterThan(LAYER_PAGE_COUNTS.layers);
    expect(index).toContain(`${LAYER_PAGE_COUNTS.total} pages`);
    expect(index).not.toContain("Ten pages");
    expect(index).not.toContain("one per layer");
  });

  it("counts the same library in the door and in the page the door opens", () => {
    const word = countWordCap(MECHANISM_ANIMATIONS.length);
    expect(weatherLessons()).toContain(`${word} things no camera has filmed`);
    const library = weatherPageView("mechanisms");
    expect(library).toContain(`${word} short animations`);
    expect(library).toContain(`MECHANISM LIBRARY · ${word.toUpperCase()} THINGS NO CAMERA HAS FILMED`);
  });
});

describe("every term of art the learn routes print is issued somewhere on the route", () => {
  it("expands CME, EUV and SEP where a cold reader first meets them", () => {
    const photons = weatherLessonView("photons");
    expect(photons).toContain("extreme-ultraviolet (EUV)");
    expect(photons).toContain("a coronal mass ejection, an erupted cloud of solar plasma");
    expect(weatherLessons()).toContain("coronal mass ejections (CMEs)");
    expect(weatherLessonView("particles")).toContain("Solar energetic particles &mdash; SEPs &mdash;");
  });

  it("states plainly what Bz is, in the module that owns it, with IMF and GSM", () => {
    const wind = weatherLessonView("wind");
    expect(wind).toContain("north&ndash;south component of the interplanetary magnetic field");
    expect(wind).toContain("a Sun-referenced frame called GSM");
    expect(wind).toContain("Negative means southward");
  });

  it("issues L-shell on the Dungey page, where the first L on the route is printed", () => {
    const dungey = weatherPageView("dungey");
    expect(dungey).toContain("L labels a whole field line");
    expect(dungey).toContain("equatorial distance from Earth's centre, in Earth radii");
  });

  it("issues Kp and magnetospheric convection where the pileup used to be", () => {
    const dungey = weatherPageView("dungey");
    expect(dungey).toContain("0-to-9 planetary index of geomagnetic disturbance");
    expect(dungey).toContain("a standard model of magnetospheric convection");
    // The two model names moved to the Data & methods card; the stage keeps the
    // concept. Provenance is not lost, it is where named models belong.
    expect(dungey).not.toContain("Volland");
    expect(dungey).not.toContain("DGCPM");
  });

  it("names the substorm and glosses magnetic flux and MHD on the Dungey page", () => {
    const dungey = weatherPageView("dungey");
    expect(dungey).toContain("magnetic flux &mdash; pile up");
    expect(dungey).toContain("the substorm, the tail&rsquo;s own storm cycle");
    expect(dungey).toContain("magnetohydrodynamics, the plasma treated as one conducting fluid");
  });

  it("ties MUF and LUF to the letters, in the clip whose title uses one of them", () => {
    const library = weatherPageView("mechanisms");
    expect(library).toContain("the maximum usable frequency, the MUF");
    expect(library).toContain("the lowest usable frequency — the LUF, the floor");
  });

  it("glosses the terms modules 03 to 06 name in passing", () => {
    expect(weatherLessonView("wind")).toContain("the two funnels over the poles where the field lets particles in");
    expect(weatherLessonView("compression")).toContain("Earth radii, R&#8853;");
    expect(weatherLessonView("layers")).toContain("the plasma slowly twisting a signal&rsquo;s polarisation");
    expect(weatherLessonView("layers")).toContain("scintillation, the rapid flicker in amplitude and phase");
    expect(weatherLessonView("systems")).toContain("satellite-navigation (GNSS) error");
    expect(weatherLessonView("systems")).toContain("a single particle strike flipping a bit or latching a circuit");
  });

  it("issues L again on the layers route, which is entered cold by deep links", () => {
    const index = layerPagesIndexView();
    expect(index).toContain("equatorial distance from Earth's centre, in Earth radii");
  });

  it("defines the units and terms the layer pages print as bare symbols", () => {
    expect(layerPageView("thermosphere")).toContain("the linear-scale twin of Kp");
    expect(layerPageView("thermosphere")).toContain("mass divided by the product of drag coefficient and area");
    expect(layerPageView("ionosphere")).toContain("one TEC unit, 10¹⁶ electrons in a one-square-metre column");
    expect(layerPageView("plasmasphere")).toContain("0-to-9 planetary disturbance index");
    expect(layerPageView("plasmasphere")).toContain("the outermost drift path that still closes around the Earth");
    expect(layerPageView("radiation-belts")).toContain("pfu is particle flux units");
    expect(layerPageView("radiation-belts")).toContain("the angle between a particle's motion and the field line");
    expect(layerPageView("ring-current")).toContain("the last drift path that still closes around the Earth");
    expect(layerPageView("solar-wind")).toContain("astronomical units");
    expect(layerPageView("peak-surfaces")).not.toContain("isohypse");
  });

  it("defines GSM, the electrojet and the energy scale on the chain page", () => {
    const chain = layerPageView("substorm-chain");
    expect(chain).toContain("the standard Sun-referenced frame (GSM)");
    expect(chain).toContain("the concentrated east–west current flowing in the auroral ionosphere near 100 km");
    expect(chain).toContain("electron-volts being the energy scale of single particles");
  });
});

describe("every module ends on what the reader now knows, not on navigation", () => {
  it("renders a closer on all eight modules", () => {
    expect(modulePages).toHaveLength(8);
    for (const [id, page] of modulePages) {
      expect(page, id).toContain("WHAT YOU NOW KNOW");
      expect(page, id).toContain(`class="lesson-block lesson-close"`);
    }
  });

  it("places the closer after the live recipe and before the doors", () => {
    for (const [id, page] of modulePages) {
      expect(page.indexOf("WHAT YOU NOW KNOW"), id).toBeLessThan(page.indexOf("WHERE THIS GOES NEXT"));
    }
  });

  /**
   * The contract, as far as a machine can hold it: a closer may not introduce a
   * new number. A closer that teaches is a body section that arrived late, and
   * the cheapest proxy for "taught something new" is a digit that appears
   * nowhere else on the page.
   */
  it("introduces no number the module has not already printed", () => {
    for (const [id, page] of modulePages) {
      const closer = page.split(`class="lesson-block lesson-close"`)[1]?.split("</section>")[0] ?? "";
      expect(closer.length, id).toBeGreaterThan(80);
      const rest = page.replace(closer, "");
      for (const digits of closer.match(/\d+/g) ?? []) {
        expect(rest, `${id} closer introduces ${digits}`).toContain(digits);
      }
    }
  });
});

describe("module 01 stops splicing in a lesson it has not taught", () => {
  it("frames the clip's wider scope above the figure", () => {
    const photons = weatherLessonView("photons");
    expect(photons).toContain("belongs to module 05&rsquo;s ionosphere");
    expect(photons.indexOf("lesson-clip-framing")).toBeLessThan(photons.indexOf("layer-figure"));
  });

  it("labels the module-03 door by what module 03 is about", () => {
    const photons = weatherLessonView("photons");
    expect(photons).toContain("Module 03 &middot; the wind, and the switch it carries");
    // Module 02 is also "the other thing the Sun sends", and it is the next
    // module in the promised order.
    expect(photons).not.toContain("the other thing the Sun sends");
  });
});
