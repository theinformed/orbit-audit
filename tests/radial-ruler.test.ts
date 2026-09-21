import { describe, expect, it } from "vitest";

import {
  RADIAL_RULER,
  RULER_EARTH_RADIUS_KM,
  radiusFromSharedDisplayRadius,
  sharedDisplayRadius,
  sharedRulerLocalSlope,
} from "../src/radial-ruler";

/**
 * The shared ruler's own contract, independent of any layer.
 *
 * Every inside/outside reading in the scene — satellite against belt, belt
 * against magnetopause, tracer against bow shock — rests on this one function
 * being strictly monotone and continuous. The layer tests check what each
 * layer does with the ruler; this file checks the ruler.
 */

const EARTH = 100;

describe("the shared radial ruler", () => {
  it("is strictly increasing from the surface to beyond the cut-plane corner", () => {
    let previous = sharedDisplayRadius(1, EARTH);
    for (let radiusRe = 1.01; radiusRe <= 70; radiusRe += 0.01) {
      const current = sharedDisplayRadius(radiusRe, EARTH);
      expect(current).toBeGreaterThan(previous);
      previous = current;
    }
  });

  it("is continuous at the anchor and across the taper", () => {
    for (const joint of [
      RADIAL_RULER.anchorRe,
      RADIAL_RULER.noseRampEndRe,
      RADIAL_RULER.taperStartRe,
      RADIAL_RULER.taperEndRe,
    ]) {
      const below = sharedDisplayRadius(joint - 1e-9, EARTH);
      const above = sharedDisplayRadius(joint + 1e-9, EARTH);
      expect(above - below).toBeLessThan(1e-5);
    }
  });

  it("has no STEP in its slope at any joint, which is what a corner in a drawn curve is", () => {
    // The reason, not the number. A purely radial map refracts a crossing
    // curve's tangent by atan(tan(psi) / slope), so a step in slope IS a
    // corner — of infinite curvature, which no tessellation can remove. Until
    // 2026-08-19 the slope stepped 0.1422 to 1 at the anchor, a 7.03x jump,
    // and every eccentric orbit line, 107 of the 143 traced field lines and
    // the exterior cusp shell crossed it. Marching MERIDIAN 9's drawn path
    // through the crossing at 0.5-second steps still left 11.96 degrees at one
    // vertex; with the ramp it measures 0.00.
    for (const joint of [
      RADIAL_RULER.anchorRe,
      RADIAL_RULER.noseRampEndRe,
      RADIAL_RULER.taperStartRe,
      RADIAL_RULER.taperEndRe,
    ]) {
      const below = sharedRulerLocalSlope(joint * (1 - 1e-9));
      const above = sharedRulerLocalSlope(joint * (1 + 1e-9));
      expect(Math.abs(above - below)).toBeLessThan(1e-6);
    }
  });

  it("bends a radially crossing curve by an amount that goes to zero as it is refined", () => {
    // The property the C1 joint exists for, stated the way the picture shows
    // it: refract a fixed physical direction on either side of the anchor and
    // the two drawn directions must agree in the limit. With the old step they
    // differed by 21.7 degrees no matter how close the two samples were.
    const drawnAngleFromRadial = (radiusRe: number, physicalAngleFromRadialRad: number) =>
      Math.atan2(Math.tan(physicalAngleFromRadialRad), sharedRulerLocalSlope(radiusRe));
    for (const physicalAngle of [(30 * Math.PI) / 180, (64.5 * Math.PI) / 180, (85 * Math.PI) / 180]) {
      for (const gap of [1e-2, 1e-4, 1e-6]) {
        const below = drawnAngleFromRadial(RADIAL_RULER.anchorRe * (1 - gap), physicalAngle);
        const above = drawnAngleFromRadial(RADIAL_RULER.anchorRe * (1 + gap), physicalAngle);
        expect(Math.abs(above - below)).toBeLessThan(60 * gap);
      }
    }
  });

  it("keeps the legacy logarithmic curve exactly, up to geostationary orbit", () => {
    for (const altitudeKm of [0, 200, 550, 1200, 20200, 35786]) {
      const radiusRe = 1 + altitudeKm / RULER_EARTH_RADIUS_KM;
      const legacy = EARTH * (1 + Math.min(2.05, 0.28 * Math.log1p(altitudeKm / 350)));
      expect(sharedDisplayRadius(radiusRe, EARTH)).toBeCloseTo(legacy, 9);
    }
  });

  it("is linear from the top of the joint ramp through the dayside boundary band", () => {
    // Ratios of drawn radii equal ratios of physical radii anywhere inside
    // the band — this is the property that makes the magnetopause flare and
    // the bow-shock standoff render in true proportion. The band starts at
    // `noseRampEndRe` rather than at the anchor, and that is the whole reason
    // the ramp ends where it does: the Shue surface's SMALLEST radius is its
    // nose, so a ramp that stops at or below the nose leaves every point of
    // the boundary inside this band and the drawn flaring exactly physical.
    const rampEnd = RADIAL_RULER.noseRampEndRe;
    const rampEndDrawn = sharedDisplayRadius(rampEnd, EARTH);
    for (const radiusRe of [7.35, 9, 12.03, RADIAL_RULER.taperStartRe]) {
      expect(sharedDisplayRadius(radiusRe, EARTH) / rampEndDrawn).toBeCloseTo(radiusRe / rampEnd, 9);
      expect(sharedRulerLocalSlope(radiusRe)).toBeCloseTo(1, 9);
    }
    // And the ramp ends at or below the standoff the reshaping was measured
    // against, which is also the lowest in the driver history the site holds.
    expect(rampEnd).toBeLessThanOrEqual(7.35);
  });

  it("moves nothing at or below geostationary orbit", () => {
    // The other half of the ramp's contract: it is paid for entirely above the
    // anchor. Every satellite shell, the plasmasphere, the ring current, the
    // belts' cores and geostationary orbit's own drawn position are exactly
    // where the logarithmic scale always put them.
    for (const altitudeKm of [0, 400, 1200, 20200, 35786]) {
      const radiusRe = 1 + altitudeKm / RULER_EARTH_RADIUS_KM;
      const legacy = EARTH * (1 + Math.min(2.05, 0.28 * Math.log1p(altitudeKm / 350)));
      expect(sharedDisplayRadius(radiusRe, EARTH)).toBeCloseTo(legacy, 9);
    }
  });

  it("agrees with its own slope function everywhere", () => {
    for (const radiusRe of [1.5, 3, 6, 6.7, 10, 15, 20, 24, 40, 65]) {
      const step = 1e-5;
      const here = sharedDisplayRadius(radiusRe, EARTH);
      const numerical = (sharedDisplayRadius(radiusRe + step, EARTH) - here) / step * (radiusRe / here);
      expect(sharedRulerLocalSlope(radiusRe)).toBeCloseTo(numerical, 3);
    }
  });

  it("round-trips a physical radius through the drawn radius and back", () => {
    for (const radiusRe of [1.05, 2, 6.6, 7.35, 12, 20, 30, 56, 65]) {
      const drawn = sharedDisplayRadius(radiusRe, EARTH);
      expect(radiusFromSharedDisplayRadius(drawn, EARTH)).toBeCloseTo(radiusRe, 6);
    }
  });

  it("scales linearly with the rendered Earth radius", () => {
    for (const radiusRe of [2, 9, 30]) {
      expect(sharedDisplayRadius(radiusRe, 2 * EARTH)).toBeCloseTo(2 * sharedDisplayRadius(radiusRe, EARTH), 9);
    }
  });
});
