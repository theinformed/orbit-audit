import { describe, expect, it } from "vitest";
import {
  footprintMapShape,
  footprintShapeFromRing,
  normalizeLongitude,
  plotRect,
  splitRingAtAntimeridian,
  project,
  type GeoPoint,
} from "../src/ground-track-map";
import { footprintAngularRadius, footprintPoints } from "../src/orbit";

/**
 * The coverage footprint drawn on the flat map.
 *
 * The boundary is not computed here — it comes from footprintPoints in orbit.ts,
 * the generator the 3-D globe draws, called with the same minimum-elevation
 * mask. These tests hold that seam shut, and cover the two failure modes that
 * are specific to an equirectangular map:
 *
 *   - the +/-180 seam, where an unhandled ring smears a filled band across the
 *     whole world (and where this codebase has already produced a
 *     divide-by-zero: see tests/world-outlines.test.ts);
 *   - the poles, where a footprint that swallows one has a boundary that winds
 *     360 degrees in longitude and never closes on the map at all.
 */

const WIDTH = 960;
const HEIGHT = 594;

function everyVertex(shape: { polygons: GeoPoint[][] }): GeoPoint[] {
  return shape.polygons.flat();
}

function longestEdgeFraction(shape: { polygons: GeoPoint[][] }): number {
  const plot = plotRect(WIDTH, HEIGHT);
  let longest = 0;
  for (const polygon of shape.polygons) {
    for (let index = 0; index < polygon.length; index += 1) {
      const from = project(polygon[index]![0], polygon[index]![1], WIDTH, HEIGHT);
      const next = polygon[(index + 1) % polygon.length]!;
      const to = project(next[0], next[1], WIDTH, HEIGHT);
      longest = Math.max(longest, Math.abs(to.x - from.x));
    }
  }
  return longest / plot.width;
}

/** Great-circle separation, for checking the drawn ring against the mask angle. */
function angularDistanceDeg(a: GeoPoint, b: GeoPoint): number {
  const toRadians = Math.PI / 180;
  const [lonA, latA] = [a[0] * toRadians, a[1] * toRadians];
  const [lonB, latB] = [b[0] * toRadians, b[1] * toRadians];
  const cosine = Math.sin(latA) * Math.sin(latB)
    + Math.cos(latA) * Math.cos(latB) * Math.cos(lonA - lonB);
  return (Math.acos(Math.max(-1, Math.min(1, cosine))) * 180) / Math.PI;
}

describe("footprint comes from the globe's own geometry", () => {
  it("draws the boundary footprintPoints produces, at the mask angle the globe uses", () => {
    // A 5 degree mask takes the spherical path in footprintPoints, so the ring
    // is exactly the mask circle and can be checked against it directly.
    const shape = footprintMapShape(11.3, -75, 20200, 5)!;
    const expected = (footprintAngularRadius(20200, 5) * 180) / Math.PI;
    expect(shape.angularRadiusDeg).toBeCloseTo(expected, 9);
    expect(shape.enclosedPole).toBeNull();

    const centre: GeoPoint = [-75, 11.3];
    // Every vertex of the drawn polygon that came from the ring — that is, not
    // the two seam or pole patches, which this footprint does not need — sits
    // on the mask circle.
    for (const vertex of everyVertex(shape)) {
      expect(angularDistanceDeg(vertex, centre)).toBeCloseTo(expected, 6);
    }
  });

  it("shrinks as the mask angle rises, exactly as the globe's footprint does", () => {
    const radii = [0, 5, 10].map((mask) => footprintMapShape(0, 0, 550, mask)!.angularRadiusDeg);
    expect(radii[0]).toBeGreaterThan(radii[1]!);
    expect(radii[1]).toBeGreaterThan(radii[2]!);
    for (const [index, mask] of [0, 5, 10].entries()) {
      expect(radii[index]).toBeCloseTo((footprintAngularRadius(550, mask) * 180) / Math.PI, 9);
    }
  });

  it("declines to draw anything it cannot compute", () => {
    expect(footprintMapShape(Number.NaN, 0, 550, 0)).toBeNull();
    expect(footprintMapShape(0, 0, 0, 0)).toBeNull();
    expect(footprintMapShape(0, 0, -10, 0)).toBeNull();
    expect(footprintShapeFromRing([[0, 0], [1, 1]], 0)).toBeNull();
  });
});

describe("the antimeridian seam", () => {
  it("splits a footprint straddling 180 degrees into one shape per edge", () => {
    const shape = footprintMapShape(0, 179.2, 550, 0)!;
    expect(shape.crossesAntimeridian).toBe(true);
    expect(shape.polygons).toHaveLength(2);
    expect(shape.enclosedPole).toBeNull();

    // Each piece stays on its own side of the seam, and touches it.
    const sides = shape.polygons.map((polygon) => ({
      minimum: Math.min(...polygon.map(([longitude]) => longitude)),
      maximum: Math.max(...polygon.map(([longitude]) => longitude)),
    }));
    const east = sides.find((side) => side.maximum === 180)!;
    const west = sides.find((side) => side.minimum === -180)!;
    expect(east).toBeDefined();
    expect(west).toBeDefined();
    expect(east.minimum).toBeGreaterThan(0);
    expect(west.maximum).toBeLessThan(0);
  });

  it("never draws an edge that smears across the map", () => {
    // The symptom of an unsplit ring: one edge running most of the way across
    // the world. No footprint that avoids the poles may have one.
    for (const longitude of [179.9, 180, -179.9, -170, 0, 90]) {
      for (const altitude of [430, 20200, 35786]) {
        const shape = footprintMapShape(0, longitude, altitude, 0)!;
        expect(`${longitude}/${altitude}: ${shape.enclosedPole}`).toBe(`${longitude}/${altitude}: null`);
        expect(`${longitude}/${altitude}: ${longestEdgeFraction(shape) < 0.5}`)
          .toBe(`${longitude}/${altitude}: true`);
      }
    }
  });

  it("survives a ring that steps from exactly +180 to exactly -180", () => {
    // The divide-by-zero this codebase produced once: the interpolation
    // denominator is zero, NaN coordinates go into the path, and an SVG path
    // containing NaN silently draws nothing at all. Natural Earth's Antarctica
    // ring does exactly this step.
    //
    // The splitter is called raw here on purpose. footprintShapeFromRing
    // normalizes first, and normalizeLongitude maps +180 onto -180, so through
    // that door the step never survives to reach the guard — a test that went
    // in the front way would leave the guard unexecuted and still pass.
    const ring: GeoPoint[] = [
      [170, -10], [180, 0], [-180, 0], [-170, -10], [-175, -20], [175, -20],
    ];
    const pieces = splitRingAtAntimeridian(ring);
    expect(pieces.length).toBeGreaterThan(1);
    for (const [longitude, latitude] of pieces.flat()) {
      expect(Number.isFinite(longitude) && Number.isFinite(latitude)).toBe(true);
    }

    // And the same ring through the production entry point is still drawable.
    const shape = footprintShapeFromRing(ring, -10)!;
    expect(shape).not.toBeNull();
    for (const [longitude, latitude] of everyVertex(shape)) {
      expect(Number.isFinite(longitude) && Number.isFinite(latitude)).toBe(true);
    }
  });

  it("normalizes +180 onto -180, which is why the pole patch needs no guard", () => {
    // poleCapPolygon divides by (westGap + eastGap). That total is provably
    // positive because every longitude reaching it is in [-180, 180); this
    // pins the property that proof rests on.
    expect(normalizeLongitude(180)).toBe(-180);
    expect(normalizeLongitude(540)).toBe(-180);
    expect(normalizeLongitude(179.999999)).toBeLessThan(180);
    const shape = footprintMapShape(89.5, 180, 500, 0)!;
    expect(shape.enclosedPole).toBe("north");
    for (const [longitude, latitude] of everyVertex(shape)) {
      expect(Number.isFinite(longitude) && Number.isFinite(latitude)).toBe(true);
    }
  });
});

describe("the poles", () => {
  it("patches a footprint that swallows the north pole up to 90 degrees", () => {
    // 500 km gives a 21.8 degree cap; from 89 N it reaches over the pole.
    const shape = footprintMapShape(89, 30, 500, 0)!;
    expect(shape.enclosedPole).toBe("north");
    expect(shape.polygons).toHaveLength(1);

    const polygon = shape.polygons[0]!;
    const latitudes = polygon.map(([, latitude]) => latitude);
    const longitudes = polygon.map(([longitude]) => longitude);
    expect(Math.max(...latitudes)).toBe(90);
    expect(Math.min(...longitudes)).toBe(-180);
    expect(Math.max(...longitudes)).toBe(180);
    // The boundary is single-valued in longitude, so the polygon walks west to
    // east once before the polar patch; nothing doubles back over the seam.
    const boundary = polygon.slice(0, polygon.length - 2);
    for (let index = 1; index < boundary.length; index += 1) {
      expect(boundary[index]![0]).toBeGreaterThanOrEqual(boundary[index - 1]![0]);
    }
  });

  it("patches the south pole the same way", () => {
    const shape = footprintMapShape(-88.5, -120, 800, 0)!;
    expect(shape.enclosedPole).toBe("south");
    expect(Math.min(...shape.polygons[0]!.map(([, latitude]) => latitude))).toBe(-90);
  });

  it("does not claim a pole for a cap that merely reaches high latitudes", () => {
    // 550 km is a 22.8 degree cap: from 60 N it stops well short of the pole.
    const shape = footprintMapShape(60, 10, 550, 0)!;
    expect(shape.enclosedPole).toBeNull();
    expect(Math.max(...shape.polygons.flat().map(([, latitude]) => latitude))).toBeLessThan(90);
  });
});

describe("no footprint produces an undrawable coordinate", () => {
  it("stays finite and inside the world for every orbit, latitude, longitude and mask", () => {
    const problems: string[] = [];
    for (const latitude of [-89.9, -88, -60, -20, 0, 20, 60, 88, 89.9]) {
      for (const longitude of [-180, -179.99, -90, 0, 90, 179.99, 180]) {
        for (const altitude of [400, 550, 1200, 20200, 35786, 60000]) {
          for (const mask of [0, 5, 10]) {
            const shape = footprintMapShape(latitude, longitude, altitude, mask);
            if (!shape) {
              problems.push(`${latitude}/${longitude}/${altitude}/${mask}: no shape`);
              continue;
            }
            for (const [pointLongitude, pointLatitude] of everyVertex(shape)) {
              if (!Number.isFinite(pointLongitude) || !Number.isFinite(pointLatitude)) {
                problems.push(`${latitude}/${longitude}/${altitude}/${mask}: not finite`);
                break;
              }
              if (pointLongitude < -180 || pointLongitude > 180 || pointLatitude < -90 || pointLatitude > 90) {
                problems.push(`${latitude}/${longitude}/${altitude}/${mask}: outside the world`);
                break;
              }
            }
            if (shape.polygons.some((polygon) => polygon.length < 3)) {
              problems.push(`${latitude}/${longitude}/${altitude}/${mask}: degenerate polygon`);
            }
          }
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it("keeps the ring the globe generated rather than resampling it", () => {
    // A regression guard on the seam between the two views: the vertex count of
    // a footprint that needs no patching is the generator's, minus its repeated
    // closing vertex.
    const ring = footprintPoints(11.3, -75, 20200, 5, 180);
    const shape = footprintMapShape(11.3, -75, 20200, 5, 180)!;
    expect(shape.polygons).toHaveLength(1);
    expect(shape.polygons[0]).toHaveLength(ring.length - 1);
  });
});
