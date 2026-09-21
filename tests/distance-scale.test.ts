import { afterEach, describe, expect, it } from "vitest";

import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import {
  RULER_EARTH_RADIUS_KM,
  activeDistanceScale,
  parseDistanceScale,
  radiusFromSharedDisplayRadius,
  setActiveDistanceScale,
  sharedDisplayRadius,
  sharedRulerLocalSlope,
} from "../src/radial-ruler";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";
import { EARTH_SCENE_RADIUS, TEC_MAP_SCENE_RADIUS, satelliteDisplayRadius } from "../src/globe";
import { ionosphereDisplayRadius } from "../src/ionosphere-volume";
import { dRegionDisplayRadius } from "../src/d-region-empirical";
import { distanceScaleStrings } from "../src/main";

/**
 * The distance-scale toggle's contract: the teaching curve stays the default
 * (tests/radial-ruler.test.ts pins its shape), the true-distance curve is
 * exact proportionality, and — the property the whole feature hangs on — the
 * two scales can never mix, because every consumer resolves to the same
 * module-level mode. These tests drive the real mode switch, so each one
 * restores the default afterwards.
 */

const EARTH = 100;
const GPS_ALTITUDE_KM = 20180;
const GPS_RADIUS_RE = 1 + GPS_ALTITUDE_KM / RULER_EARTH_RADIUS_KM; // 4.167

afterEach(() => setActiveDistanceScale("teaching"));

describe("the default scale", () => {
  it("is the teaching scale, exactly as shipped", () => {
    expect(activeDistanceScale()).toBe("teaching");
    // A spot value of the legacy log branch: the default mapping is untouched.
    expect(sharedDisplayRadius(1 + 550 / RULER_EARTH_RADIUS_KM, EARTH))
      .toBeCloseTo(EARTH * (1 + 0.28 * Math.log1p(550 / 350)), 9);
  });

  it("rejects everything but the two scale names when restoring a preference", () => {
    expect(parseDistanceScale("teaching")).toBe("teaching");
    expect(parseDistanceScale("true-distance")).toBe("true-distance");
    for (const junk of ["linear", "", null, undefined, 3, {}, "TRUE-DISTANCE"]) {
      expect(parseDistanceScale(junk)).toBeNull();
    }
  });

  it("survives a persistence round-trip through the display-settings JSON shape", () => {
    // The same shape applyDisplaySettings writes and restoreDisplaySettings
    // parses: the scale rides in the one settings blob under `distanceScale`.
    const stored = JSON.stringify({ profile: "auto", distanceScale: "true-distance" });
    const parsed = JSON.parse(stored) as Partial<{ distanceScale: string }>;
    expect(parseDistanceScale(parsed.distanceScale)).toBe("true-distance");
    const storedDefault = JSON.stringify({ profile: "auto", distanceScale: "teaching" });
    expect(parseDistanceScale((JSON.parse(storedDefault) as { distanceScale: string }).distanceScale)).toBe("teaching");
    // A blob from before the feature simply lacks the key: default holds.
    expect(parseDistanceScale((JSON.parse("{}") as { distanceScale?: string }).distanceScale)).toBeNull();
  });
});

describe("the true-distance scale", () => {
  it("is exactly proportional: drawn(4.5 Re) / drawn(2.25 Re) = 2", () => {
    setActiveDistanceScale("true-distance");
    expect(sharedDisplayRadius(4.5, EARTH) / sharedDisplayRadius(2.25, EARTH)).toBe(2);
    for (const radiusRe of [1, 1.2, 2.5, 4.167, 6.6, 13, 24, 56, 65.2]) {
      expect(sharedDisplayRadius(radiusRe, EARTH)).toBe(EARTH * radiusRe);
    }
  });

  it("pins below-surface radii to the globe, like the teaching scale does", () => {
    setActiveDistanceScale("true-distance");
    expect(sharedDisplayRadius(0.5, EARTH)).toBe(EARTH);
  });

  it("inverts exactly", () => {
    setActiveDistanceScale("true-distance");
    for (const radiusRe of [1, 1.5, 4.167, 9.5, 65]) {
      expect(radiusFromSharedDisplayRadius(sharedDisplayRadius(radiusRe, EARTH), EARTH)).toBeCloseTo(radiusRe, 12);
    }
  });

  it("has log-log slope 1 above the surface, so drawn motion is true motion", () => {
    setActiveDistanceScale("true-distance");
    for (const radiusRe of [1.01, 2, 6.6, 13, 30]) {
      expect(sharedRulerLocalSlope(radiusRe)).toBe(1);
    }
    expect(sharedRulerLocalSlope(0.9)).toBe(0);
  });
});

describe("scene-wide consistency: one k for every consumer", () => {
  it("belts, satellites and the magnetopause nose all draw at the same k = 1 scene-Earth per Re", () => {
    setActiveDistanceScale("true-distance");
    const noseRe = 9.5; // a typical Shue standoff; any value must obey the same k
    // The belt layer's own named policy resolves to k * L exactly.
    for (const beltL of [1.77, 1.95, 2.08, 4.5]) {
      expect(radiationBeltDisplayRadius(beltL, EARTH_SCENE_RADIUS)).toBe(EARTH_SCENE_RADIUS * beltL);
    }
    // A satellite's drawn radius is k * its true geocentric distance.
    expect(satelliteDisplayRadius(GPS_ALTITUDE_KM)).toBeCloseTo(EARTH_SCENE_RADIUS * GPS_RADIUS_RE, 9);
    // The boundary mapper (modelGsmPosition divides drawn by physical radius)
    // sees the identical k, so the three families cannot shear apart.
    expect(sharedDisplayRadius(noseRe, EARTH_SCENE_RADIUS) / noseRe).toBe(EARTH_SCENE_RADIUS);
    expect(radiationBeltDisplayRadius(noseRe, EARTH_SCENE_RADIUS)).toBe(sharedDisplayRadius(noseRe, EARTH_SCENE_RADIUS));
  });

  it("keeps GPS inside the outer belt's radial span on BOTH scales", () => {
    // The cross-layer honesty the shared ruler was built for. Outer-belt span
    // here is the conservative L 3.0-6.6 electron belt; GPS flies at L ~4.17.
    for (const scale of ["teaching", "true-distance"] as const) {
      setActiveDistanceScale(scale);
      const gpsDrawn = satelliteDisplayRadius(GPS_ALTITUDE_KM);
      const beltInnerDrawn = radiationBeltDisplayRadius(3.0, EARTH_SCENE_RADIUS);
      const beltOuterDrawn = radiationBeltDisplayRadius(6.6, EARTH_SCENE_RADIUS);
      expect(gpsDrawn).toBeGreaterThan(beltInnerDrawn);
      expect(gpsDrawn).toBeLessThan(beltOuterDrawn);
    }
  });

  it("routes the ionosphere and D-region shells — the two private teaching curves — through k on the true scale", () => {
    setActiveDistanceScale("true-distance");
    // On the true scale a satellite AT the F-peak altitude draws AT the
    // F-peak shell; under the private teaching curves it would not, which is
    // exactly the mixed-scale lie the toggle forbids.
    for (const altitudeKm of [80, 300, 600]) {
      expect(ionosphereDisplayRadius(altitudeKm, EARTH_SCENE_RADIUS)).toBeCloseTo(satelliteDisplayRadius(altitudeKm), 9);
    }
    expect(dRegionDisplayRadius(74, EARTH_SCENE_RADIUS)).toBeCloseTo(satelliteDisplayRadius(74), 9);
    // And the teaching curves themselves are untouched on the default scale.
    setActiveDistanceScale("teaching");
    expect(ionosphereDisplayRadius(300)).toBeCloseTo(100 + Math.min(145, 18 * Math.log1p(300 / 350)), 9);
    // CORRECTNESS FIX 2026-09-04: the D-region surface is on the SHARED ruler
    // on both scales now. Its old private teaching curve drew the 70 km
    // daytime reflection height where the ruler puts 47 km, while calling
    // itself an exaggeration.
    expect(dRegionDisplayRadius(74)).toBeCloseTo(satelliteDisplayRadius(74), 9);
  });
});

describe("the honesty surfaces", () => {
  it("states the LEO collapse on the true scale and never claims compression there", () => {
    const truth = distanceScaleStrings("true-distance");
    expect(truth.legend).toMatch(/low Earth orbit/i);
    expect(truth.legend).toMatch(/proportional to real geocentric distance/);
    expect(truth.zoomOutTitle).not.toMatch(/compressed/);
    const teaching = distanceScaleStrings("teaching");
    expect(teaching.legend).toMatch(/compressed/);
    expect(teaching.zoomOutTitle).toMatch(/compressed scale/);
  });

  it("ships the toggle and its surfaces in the page and the restore path", () => {
    // Reachability, in the house style: the control exists in the document,
    // and the restore path actually reads the persisted key.
    expect(indexMarkup).toContain('data-distance-scale="teaching"');
    expect(indexMarkup).toContain('data-distance-scale="true-distance"');
    expect(indexMarkup).toContain('id="map-key-scale"');
    expect(explorerSource).toContain("parseDistanceScale(settings.distanceScale)");
    expect(explorerSource).toContain("distanceScale: this.distanceScale");
    expect(explorerSource).toContain("setDistanceScale(this.distanceScale)");
  });
});

describe("the TEC map is on the globe, not at an altitude", () => {
  afterEach(() => setActiveDistanceScale("teaching"));

  it("cannot move against another layer when the scale changes, and stays under everything that has a height", () => {
    // TEC is electrons integrated through a whole column, so it has no height
    // to be drawn at -- the site says exactly that in its own methods card.
    // The map therefore goes on the column's footprint, and these are the two
    // properties that makes it safe.
    //
    // 1. One drawn radius, both scales. The drawn globe is radius 1 on either
    //    curve, so a map pinned to the globe cannot slide against a layer that
    //    is on the ruler. The old hard-coded 109 could and did: read back
    //    through the ruler it is 133 km on the teaching curve and 573 km on
    //    true distance, and against the ionospheric column it is the sum of it
    //    sat 8.2% of the way up on one scale and 19.8% up on the other.
    // 2. Under everything with a height, on both scales, so it can never be
    //    read as one of them. The lowest of those is the D-RAP map at 35 km
    //    and the ionospheric column floor at 60 km.
    const clearOfTheGlobe = EARTH_SCENE_RADIUS * 1.0006; // basemap + coastlines
    const drapMapRadius = EARTH_SCENE_RADIUS * (1 + 35 / RULER_EARTH_RADIUS_KM);

    for (const scale of ["teaching", "true-distance"] as const) {
      setActiveDistanceScale(scale);
      expect(TEC_MAP_SCENE_RADIUS).toBeGreaterThan(clearOfTheGlobe);
      expect(TEC_MAP_SCENE_RADIUS).toBeLessThan(drapMapRadius);
      expect(TEC_MAP_SCENE_RADIUS).toBeLessThan(
        sharedDisplayRadius(1 + 60 / RULER_EARTH_RADIUS_KM, EARTH_SCENE_RADIUS),
      );
    }

    // And the disease, so nobody reintroduces a fixed scene radius up in the
    // column: the same 109 means two altitudes more than four times apart.
    setActiveDistanceScale("teaching");
    const teachingKm = (radiusFromSharedDisplayRadius(109, EARTH_SCENE_RADIUS) - 1) * RULER_EARTH_RADIUS_KM;
    setActiveDistanceScale("true-distance");
    const trueKm = (radiusFromSharedDisplayRadius(109, EARTH_SCENE_RADIUS) - 1) * RULER_EARTH_RADIUS_KM;
    expect(teachingKm).toBeGreaterThan(130);
    expect(teachingKm).toBeLessThan(136);
    expect(trueKm / teachingKm).toBeGreaterThan(4);
  });
});
