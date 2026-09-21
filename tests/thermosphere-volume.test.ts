import { describe, expect, test } from "vitest";
import * as THREE from "three";
import {
  THERMOSPHERE_VOLUME_ALTITUDE_KM,
  THERMOSPHERE_VOLUME_COLOR_HEX,
  THERMOSPHERE_VOLUME_TRANSFER,
  bakeThermosphereVolume,
  createThermosphereVolumeMesh,
} from "../src/thermosphere-volume";
import { RULER_EARTH_RADIUS_KM, sharedDisplayRadius } from "../src/radial-ruler";
import { circularOrbitalSpeedMs, dragDecelerationMs2, type DecodedFrame } from "../src/thermosphere";

/**
 * A frame with a known exponential profile, so the assertions are about what
 * the bake DOES rather than about whatever today's NOAA file happens to hold.
 * Density falls by one decade every 150 km, which is the right order for the
 * real thermosphere and makes the expected values checkable by hand.
 */
function exponentialFrame(): DecodedFrame {
  const altitudeKm = new Float64Array([120, 240, 360, 480, 600, 800, 1000]);
  const latitudeDeg = new Float64Array([-90, -45, 0, 45, 90]);
  const longitudeDeg = new Float64Array([0, 90, 180, 270]);
  const logDensity = new Float64Array(altitudeKm.length * latitudeDeg.length * longitudeDeg.length);
  let index = 0;
  for (let a = 0; a < altitudeKm.length; a += 1) {
    for (let b = 0; b < latitudeDeg.length; b += 1) {
      for (let c = 0; c < longitudeDeg.length; c += 1) {
        logDensity[index] = -8 - (altitudeKm[a]! - 120) / 150;
        index += 1;
      }
    }
  }
  return { validAt: "2026-08-19T00:00:00Z", altitudeKm, latitudeDeg, longitudeDeg, logDensity };
}

const EARTH = 100;

describe("the thermosphere volume bake", () => {
  test("spends its byte range on LOG density, so the satellite band is not one code", () => {
    const bake = bakeThermosphereVolume(exponentialFrame(), { earthSceneRadius: EARTH });
    // The field spans 5.87 decades; a linear byte would put everything above
    // ~200 km into code 0 and the lesson would be a black shell.
    expect(bake.logCeiling - bake.logFloor).toBeGreaterThan(5);
    const slab = bake.longitudeCount * bake.latitudeCount;
    // Two channels per sample: R absolute (drives opacity), G anomaly (colour).
    const absolute = (index: number) => bake.data[index * 2]!;
    const bottom = absolute(0);
    const top = absolute((bake.altitudeCount - 1) * slab);
    // Not 255 and 0 any more, and that is the point. The bake draws against a
    // FIXED display range rather than stretching each frame to fill the byte
    // range, so this frame -- which spans -8 to -13.87 inside a -15.6 to -7.2
    // window -- uses the part of the scale its own densities sit in and leaves
    // headroom above for air a storm has thickened.
    expect(bottom).toBe(231);
    expect(top).toBe(53);
    // Halfway up in altitude the LOG is halfway, so the byte is near the middle.
    const middle = absolute(Math.floor((bake.altitudeCount - 1) / 2) * slab);
    expect(middle).toBeGreaterThan(100);
    expect(middle).toBeLessThan(155);
  });

  test("resamples onto a uniform altitude axis, because a 3D texture has no other kind", () => {
    const bake = bakeThermosphereVolume(exponentialFrame(), { earthSceneRadius: EARTH });
    const slab = bake.longitudeCount * bake.latitudeCount;
    const absolute = (index: number) => bake.data[index * 2]!;
    const steps: number[] = [];
    for (let k = 0; k + 1 < bake.altitudeCount; k += 1) {
      steps.push(absolute(k * slab) - absolute((k + 1) * slab));
    }
    // A uniform altitude axis through an exponential profile gives a constant
    // drop per slab. Published levels are 30-200 km apart; feeding those in raw
    // would make this ragged, which is the bug this resampling exists to stop.
    const smallest = Math.min(...steps);
    const largest = Math.max(...steps);
    expect(largest - smallest).toBeLessThanOrEqual(2);
  });

  test("density falls with altitude everywhere, which is the one thing the picture must not get wrong", () => {
    const bake = bakeThermosphereVolume(exponentialFrame(), { earthSceneRadius: EARTH });
    const slab = bake.longitudeCount * bake.latitudeCount;
    const absolute = (index: number) => bake.data[index * 2]!;
    for (let k = 0; k + 1 < bake.altitudeCount; k += 1) {
      for (let s = 0; s < slab; s += 37) {
        // The ABSOLUTE channel must fall with height. The anomaly channel must
        // not be asserted here: it is rescaled per slab by design, so it is
        // near-constant down a column and that is the point of it.
        expect(absolute(k * slab + s)).toBeGreaterThanOrEqual(absolute((k + 1) * slab + s));
      }
    }
  });

  /**
   * This test used to assert the opposite, and asserting the opposite is what
   * let the defect stand. "Scales to the frame's own extremes so a storm is not
   * clipped" sounds protective and does the reverse: rescaling per frame moves
   * the scale WITH the storm, so the storm cancels and every hour draws the same
   * opacity. The scale is fixed now, the measurement is reported separately, and
   * the assertion is that more air is more opaque.
   */
  test("a storm is more air, and more air has to be more opaque", () => {
    const quiet = exponentialFrame();
    const storm = exponentialFrame();
    // Heat the whole column by half a decade, as a storm does.
    for (let i = 0; i < storm.logDensity.length; i += 1) storm.logDensity[i] = storm.logDensity[i]! + 0.5;
    const quietBake = bakeThermosphereVolume(quiet, { earthSceneRadius: EARTH });
    const stormBake = bakeThermosphereVolume(storm, { earthSceneRadius: EARTH });
    // The display window does not move with the weather.
    expect(stormBake.logFloor).toBe(quietBake.logFloor);
    expect(stormBake.logCeiling).toBe(quietBake.logCeiling);
    // What the frame actually held is still measured, and still reported.
    expect(stormBake.measured.maxLog10 - quietBake.measured.maxLog10).toBeCloseTo(0.5, 6);
    // And the bytes moved: 0.5 dex on the 8.4 dex display range is 15 codes.
    const slab = quietBake.longitudeCount * quietBake.latitudeCount;
    const absolute = (bake: typeof quietBake, index: number) => bake.data[index * 2]!;
    const middle = Math.floor((quietBake.altitudeCount - 1) / 2) * slab;
    expect(absolute(stormBake, middle) - absolute(quietBake, middle)).toBeGreaterThan(13);
    expect(absolute(stormBake, middle) - absolute(quietBake, middle)).toBeLessThan(17);
  });


  test("the day/night bulge survives the vertical falloff, which is why colour is an anomaly", () => {
    // Build a frame with a real horizontal contrast at every altitude: one
    // longitude half a decade denser than the other, on top of the exponential
    // falloff. Normalized against the whole 5.9-decade column that contrast is
    // under a tenth of the ramp and reads as flat — which is exactly what the
    // first version drew.
    const frame = exponentialFrame();
    const nLat = frame.latitudeDeg.length;
    const nLon = frame.longitudeDeg.length;
    for (let a = 0; a < frame.altitudeKm.length; a += 1) {
      for (let b = 0; b < nLat; b += 1) {
        for (let c = 0; c < nLon; c += 1) {
          if (c >= nLon / 2) continue;
          const at = a * nLat * nLon + b * nLon + c;
          frame.logDensity[at] = frame.logDensity[at]! + 0.5;
        }
      }
    }
    const bake = bakeThermosphereVolume(frame, { earthSceneRadius: EARTH });
    const slab = bake.longitudeCount * bake.latitudeCount;
    const mid = Math.floor((bake.altitudeCount - 1) / 2) * slab;
    let absMin = 255, absMax = 0, anomMin = 255, anomMax = 0;
    for (let s = 0; s < slab; s += 1) {
      const a = bake.data[(mid + s) * 2]!;
      const g = bake.data[(mid + s) * 2 + 1]!;
      absMin = Math.min(absMin, a); absMax = Math.max(absMax, a);
      anomMin = Math.min(anomMin, g); anomMax = Math.max(anomMax, g);
    }
    // Absolute barely moves across the slab; the anomaly uses the full ramp.
    expect(absMax - absMin).toBeLessThan(40);
    expect(anomMax - anomMin).toBeGreaterThan(200);
  });

  test("a frame with nothing in it does not produce a zero-width scale", () => {
    const empty = exponentialFrame();
    empty.logDensity.fill(Number.NaN);
    const bake = bakeThermosphereVolume(empty, { earthSceneRadius: EARTH });
    expect(bake.logCeiling).toBeGreaterThan(bake.logFloor);
    expect(bake.measured.sampleCount).toBe(0);
    expect(Array.from(bake.data).every((byte) => byte === 0)).toBe(true);
  });
});

describe("the claim the layer exists to teach", () => {
  const drawn = (altitudeKm: number) =>
    sharedDisplayRadius((RULER_EARTH_RADIUS_KM + altitudeKm) / RULER_EARTH_RADIUS_KM, EARTH);

  test("LEO is drawn INSIDE the air and geostationary is drawn outside it", () => {
    const bake = bakeThermosphereVolume(exponentialFrame(), { earthSceneRadius: EARTH });
    // NASA puts the thermosphere at about 80-700 km and says in those words
    // that the ISS orbits in it:
    // <https://science.nasa.gov/earth/earth-atmosphere/earths-atmosphere-a-multi-layered-cake/>
    const iss = drawn(420);
    expect(iss).toBeGreaterThan(bake.sceneRadiusMinimum);
    expect(iss).toBeLessThan(bake.sceneRadiusMaximum);

    const geostationary = drawn(35786);
    expect(geostationary).toBeGreaterThan(bake.sceneRadiusMaximum);
  });

  test("the shell is thick enough on screen to see a satellite sitting in it", () => {
    const bake = bakeThermosphereVolume(exponentialFrame(), { earthSceneRadius: EARTH });
    const thickness = bake.sceneRadiusMaximum - bake.sceneRadiusMinimum;
    // Measured 29.5 units on a globe of 100. If this ever collapses toward the
    // true-scale 13.8, the layer is back to being an invisible skin and the
    // lesson is gone -- that failure is exactly why the isopycnic shell was
    // replaced, so it is pinned rather than left to be noticed by eye.
    expect(thickness).toBeGreaterThan(25);
  });

  test("the air never becomes a wall that hides what is inside it", () => {
    // The first tuning drew a solid band and hid every satellite in it, which
    // is a picture that teaches the opposite of the lesson.
    expect(THERMOSPHERE_VOLUME_TRANSFER.maximumAccumulatedOpacity).toBeLessThan(0.8);
  });

  test("the ramp is ordered thin to thick, matching how the shader reads it", () => {
    expect(THERMOSPHERE_VOLUME_COLOR_HEX.length).toBeGreaterThanOrEqual(5);
    const luminance = (hex: string) => {
      const c = hex.replace("#", "");
      return 0.2126 * parseInt(c.slice(0, 2), 16)
        + 0.7152 * parseInt(c.slice(2, 4), 16)
        + 0.0722 * parseInt(c.slice(4, 6), 16);
    };
    const first = luminance(THERMOSPHERE_VOLUME_COLOR_HEX[0]!);
    const last = luminance(THERMOSPHERE_VOLUME_COLOR_HEX[THERMOSPHERE_VOLUME_COLOR_HEX.length - 1]!);
    expect(last).toBeGreaterThan(first);
  });

  test("nothing is drawn outside the published column", () => {
    expect(THERMOSPHERE_VOLUME_ALTITUDE_KM.low).toBe(120);
    expect(THERMOSPHERE_VOLUME_ALTITUDE_KM.high).toBe(1000);
  });
});

describe("the drag figure the card quotes", () => {
  test("is the right size for a large spacecraft at ISS altitude", () => {
    // rho at 420 km on the live field is about 2.5e-12 kg/m3; a = rho v^2 / 2B.
    const speed = circularOrbitalSpeedMs(420);
    expect(speed).toBeGreaterThan(7500);
    expect(speed).toBeLessThan(7800);
    const drag = dragDecelerationMs2(2.5e-12, speed, 100);
    // Around 7e-7 m/s2 — small, relentless, and the reason LEO decays. If this
    // ever lands orders of magnitude away, the card is quoting nonsense.
    expect(drag).toBeGreaterThan(1e-7);
    expect(drag).toBeLessThan(1e-6);
  });

  test("refuses to invent a ballistic coefficient", () => {
    // The catalogue does not hold mass and area for real objects, so a caller
    // must state the reference body rather than have a plausible number appear.
    expect(() => dragDecelerationMs2(2.5e-12, 7660, 0)).toThrow();
  });

  test("thicker air means more drag, which is the whole storm story", () => {
    const speed = circularOrbitalSpeedMs(420);
    const quiet = dragDecelerationMs2(2.5e-12, speed, 100);
    const storm = dragDecelerationMs2(2.5e-12 * 3, speed, 100);
    expect(storm / quiet).toBeCloseTo(3, 6);
  });
});

describe("the volume can draw over the globe, not only around it", () => {
  test("does not depth-test its BackSide proxy, and draws before the satellites", () => {
    // The rule these two settings encode, and the reason it is not a taste.
    //
    // The proxy is a BackSide sphere at the TOP of the volume, so every
    // fragment it rasterises sits on the far side of the atmosphere, further
    // from the camera than the opaque Earth. Any depth test against the globe
    // therefore rejects the whole globe-facing column and leaves the layer
    // drawing only in the limb ring -- measured on the shipped build as warm
    // excess (mean R minus B) of -25.9 over the disc against +53.4 in the
    // ring. The occlusion the layer needs is done in the shader instead: a ray
    // that reaches the globe stops at the Earth intersection.
    //
    // Satellites then stay visible because they are transparent at renderOrder
    // 0 and write no depth, so a volume drawn at a LOWER order is painted
    // under them. That is the whole reason satellites survive with the depth
    // test off, so it is asserted here beside it.
    const { mesh } = createThermosphereVolumeMesh(exponentialFrame(), { earthSceneRadius: EARTH });
    const material = mesh.material as THREE.ShaderMaterial;
    expect(material.side).toBe(THREE.BackSide);
    expect(material.depthTest).toBe(false);
    expect(material.depthWrite).toBe(false);
    expect(mesh.renderOrder).toBeLessThan(0);
    mesh.geometry.dispose();
    material.dispose();
  });
});
