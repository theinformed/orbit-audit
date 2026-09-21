import { afterEach, describe, expect, it } from "vitest";

import indexMarkup from "../index.html?raw";
import globeSource from "../src/globe.ts?raw";
import {
  RULER_EARTH_RADIUS_KM,
  radiusFromSharedDisplayRadius,
  setActiveDistanceScale,
  sharedDisplayRadius,
} from "../src/radial-ruler";
import explorerSource from "../src/main.ts?raw";
import { IONOSPHERE_REGION_BANDS, allIonosphereRegionsOn } from "../src/ionosphere-density-volume";
import { distanceScaleStrings, ionosphereRegionMarks, teachingScaleLegend } from "../src/main";

/**
 * Claims about HEIGHT, checked against the ruler that draws them.
 *
 * Every test here asserts a sentence or a constant a reader can see, not a
 * rendering. The site had 2,168 passing tests and none of them caught a legend
 * line, printed under every layer, that stated the sign of the near-Earth
 * distortion backwards — because a test that checks the code does what it was
 * written to do never asks whether the drawing tells the truth.
 */

const EARTH = 100;

/** The altitude a reader would infer from a drawn radius, read back through the live ruler. */
function altitudeReadFromDrawn(sceneRadius: number) {
  return (radiusFromSharedDisplayRadius(sceneRadius, EARTH) - 1) * RULER_EARTH_RADIUS_KM;
}

/** The drawn height of an altitude, expressed as the altitude it would be at the globe own scale. */
function drawnAltitudeEquivalentKm(altitudeKm: number) {
  return (sharedDisplayRadius(1 + altitudeKm / RULER_EARTH_RADIUS_KM, EARTH) / EARTH - 1) * RULER_EARTH_RADIUS_KM;
}

afterEach(() => setActiveDistanceScale("teaching"));

describe("the scale line names the direction the ruler actually bends", () => {
  it("stretches near-Earth altitude rather than compressing it, and says so", () => {
    setActiveDistanceScale("teaching");
    // The band every ionospheric region lives in is MAGNIFIED, by a lot.
    expect(drawnAltitudeEquivalentKm(100) / 100).toBeGreaterThan(4);
    expect(drawnAltitudeEquivalentKm(300) / 300).toBeGreaterThan(3);
    // And only past the crossover does it genuinely compress.
    expect(drawnAltitudeEquivalentKm(10_000) / 10_000).toBeLessThan(1);
    expect(drawnAltitudeEquivalentKm(35_786) / 35_786).toBeLessThan(0.3);

    const teaching = distanceScaleStrings("teaching");
    for (const sentence of [teaching.legend, teaching.legendCompressed, teaching.settingsNote, teaching.weatherNote]) {
      expect(sentence).toMatch(/stretch/i);
    }
    // The old wording, which had it backwards, must not come back.
    expect(teaching.legend).not.toMatch(/heights below GEO are compressed/);
    expect(teaching.settingsNote).not.toMatch(/compresses heights below GEO/);
    expect(indexMarkup).not.toMatch(/heights below GEO are compressed/);
  });

  it("crosses from stretch to compression at about 4,800 km, which is what the sentence quotes", () => {
    setActiveDistanceScale("teaching");
    expect(drawnAltitudeEquivalentKm(4_700)).toBeGreaterThan(4_700);
    expect(drawnAltitudeEquivalentKm(4_900)).toBeLessThan(4_900);
    expect(distanceScaleStrings("teaching").legend).toMatch(/4,800 km/);
  });

  it("assembles the same lead clause however many layers are on", () => {
    const lead = distanceScaleStrings("teaching").legendLead;
    expect(teachingScaleLegend("teaching", [])).toBe(`${lead}.`);
    expect(teachingScaleLegend("teaching", ["geospace"])).toContain(lead);
    expect(teachingScaleLegend("teaching", ["geospace"])).toContain("the far tail is foreshortened");
  });
});

describe("every layer that names an altitude is drawn at that altitude, on both scales", () => {
  /**
   * The invariant the shared ruler exists for. A layer on a private height
   * curve means one drawn shell claiming two different altitudes depending on a
   * Display setting, which is how the old TEC shell went wrong and how the
   * D-RAP map, the auroral oval and the three schematic D/E/F shells were all
   * still going wrong on 2026-09-04.
   */
  const shells: Array<{ what: string; altitudeKm: number }> = [
    { what: "D-RAP absorption map", altitudeKm: 70 },
    { what: "auroral oval", altitudeKm: 110 },
    { what: "schematic D shell", altitudeKm: 75 },
    { what: "schematic E shell", altitudeKm: 110 },
    { what: "schematic F shell", altitudeKm: 300 },
  ];

  for (const { what, altitudeKm } of shells) {
    it(`reads back as ${altitudeKm} km on both scales: ${what}`, () => {
      for (const scale of ["teaching", "true-distance"] as const) {
        setActiveDistanceScale(scale);
        const drawn = sharedDisplayRadius(1 + altitudeKm / RULER_EARTH_RADIUS_KM, EARTH);
        expect(altitudeReadFromDrawn(drawn)).toBeCloseTo(altitudeKm, 6);
      }
    });
  }

  it("names each ionospheric region by the band it switches, not by a fit's domain", () => {
    // The globe legend called the bottom row "D region · 60–85 km". 85 km is
    // the top of the Wait–Spies FIT; the region, the site's own layer page and
    // the selection band this row switches all say 90. A reader sitting a
    // qualification reads the number in the row name.
    // Every band edge the legend names has to be the edge the shader masks on.
    expect(IONOSPHERE_REGION_BANDS[0]).toMatchObject({ region: "D", lowKm: 60, highKm: 90 });
    for (const band of IONOSPHERE_REGION_BANDS) {
      const label = band.region === "F2"
        ? `F2 region · ${band.lowKm} km and above`
        : `${band.region} region · ${band.lowKm}–${band.highKm} km`;
      expect(explorerSource).toContain(label);
    }
    // And with nothing baked the legend names nothing, rather than naming four
    // regions over an empty scene.
    expect(ionosphereRegionMarks({
      bake: null, enabled: allIonosphereRegionsOn(), f1CriterionPercent: null, hmF2Km: null,
    }).marks).toHaveLength(0);
    expect(explorerSource).toContain("D region · 60–90 km");
    expect(explorerSource).not.toContain("D region · 60–85 km");
    expect(indexMarkup).not.toContain("60&ndash;85 km");
  });

  it("keeps the schematic D/E/F shells off hard-coded scene radii", () => {
    // The three shells used to be built at 102 / 104 / 110 scene units, which
    // the teaching ruler reads as 25.9 / 53.7 / 150.2 km — the D shell in the
    // stratosphere and the E shell below the D region.
    expect(globeSource).toContain("schematicRegionAltitudeKm");
    expect(globeSource).not.toMatch(/\{ radius: 102, color/);
  });

  it("orders the ionospheric shells the way the physics does, on both scales", () => {
    for (const scale of ["teaching", "true-distance"] as const) {
      setActiveDistanceScale(scale);
      const at = (km: number) => sharedDisplayRadius(1 + km / RULER_EARTH_RADIUS_KM, EARTH);
      // D absorption below the E region below the F peak, and the whole stack
      // above the column floor the ionosphere volume is drawn from.
      expect(at(60)).toBeLessThan(at(70));
      expect(at(70)).toBeLessThan(at(110));
      expect(at(110)).toBeLessThan(at(300));
    }
  });
});
