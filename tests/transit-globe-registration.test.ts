/**
 * Coordinate registration.
 *
 * A 90-degree registration error between a globe's coastline artwork and its
 * geometry hid in this codebase for months before it was found and fixed on
 * 2026-08-07. The planner's globe is built so it cannot reproduce that class of
 * bug — coastlines are line geometry through the same `geoToVector` that places
 * waypoints and satellites, so there is no second coordinate system to drift
 * against. These tests are the evidence for that claim rather than the claim.
 *
 * The important test is the last one: it takes real landmarks with known
 * coordinates, converts them with the production transform, and asks how far the
 * *drawn coastline geometry* is from them. A rotation, a sign flip, a lat/lon
 * swap, or a degrees/radians slip all move a landmark off its own coast and are
 * caught here.
 */

import { describe, expect, it } from "vitest";
import { loadLand } from "./transit-fixtures";
import {
  TRANSIT_GLOBE_RADIUS,
  coastlineSegmentPositions,
  displayRadius,
  geoToVector,
} from "../src/transit-globe";
import type { LandGeoJson } from "../src/globe";

/**
 * The land artifact the current release manifest names. See tests/transit-fixtures.ts
 * for why this does not glob for it directly.
 */
const land: LandGeoJson = await loadLand();

/** The scene transform as written in src/globe.ts, copied here on purpose. */
function globeReferenceVector(latitudeDeg: number, longitudeDeg: number, radius: number) {
  const latitude = (latitudeDeg * Math.PI) / 180;
  const longitude = (longitudeDeg * Math.PI) / 180;
  return {
    x: radius * Math.cos(latitude) * Math.cos(longitude),
    y: radius * Math.sin(latitude),
    z: -radius * Math.cos(latitude) * Math.sin(longitude),
  };
}

describe("the planner globe uses the site's coordinate convention", () => {
  it("agrees with src/globe.ts geoRadiansToVector on every axis", () => {
    const cases: Array<[number, number]> = [
      [0, 0], [0, 90], [0, -90], [0, 180], [90, 0], [-90, 0],
      [21.35, -157.95], [35.28, 139.67], [-33.92, 18.42], [51.5, -0.13], [-54.8, -68.3],
    ];
    for (const [latitude, longitude] of cases) {
      const actual = geoToVector(latitude, longitude, TRANSIT_GLOBE_RADIUS);
      const expected = globeReferenceVector(latitude, longitude, TRANSIT_GLOBE_RADIUS);
      expect(actual.x).toBeCloseTo(expected.x, 10);
      expect(actual.y).toBeCloseTo(expected.y, 10);
      expect(actual.z).toBeCloseTo(expected.z, 10);
    }
  });

  it("puts the poles on the y axis and the prime meridian on the x axis", () => {
    const north = geoToVector(90, 0, 100);
    expect(north.y).toBeCloseTo(100, 9);
    expect(Math.hypot(north.x, north.z)).toBeCloseTo(0, 9);

    const greenwichEquator = geoToVector(0, 0, 100);
    expect(greenwichEquator.x).toBeCloseTo(100, 9);
    expect(greenwichEquator.y).toBeCloseTo(0, 9);
    expect(greenwichEquator.z).toBeCloseTo(0, 9);

    // 90 E goes to -z. This is the sign that a 90-degree error flips.
    const ninetyEast = geoToVector(0, 90, 100);
    expect(ninetyEast.z).toBeCloseTo(-100, 9);
    expect(ninetyEast.x).toBeCloseTo(0, 9);
  });

  it("preserves great-circle angles, so distances on the sphere are distances in the scene", () => {
    const a = geoToVector(21.35, -157.95, 100);
    const b = geoToVector(35.28, 139.67, 100);
    const angle = a.angleTo(b) * (180 / Math.PI);
    // Pearl Harbor to Yokosuka is 6,200 km, which is 55.8 degrees of arc.
    expect(angle).toBeCloseTo(55.8, 0);
  });

  it("orders altitudes monotonically and keeps everything above the surface", () => {
    expect(displayRadius(0)).toBe(TRANSIT_GLOBE_RADIUS);
    const radii = [0, 400, 550, 1200, 20200, 35786].map(displayRadius);
    for (let index = 1; index < radii.length; index += 1) {
      expect(radii[index]!).toBeGreaterThan(radii[index - 1]!);
    }
    expect(radii.at(-1)!).toBeLessThan(TRANSIT_GLOBE_RADIUS + 206);
  });
});

describe("the drawn coastline is where the transform says the coast is", () => {
  const positions = coastlineSegmentPositions(land, TRANSIT_GLOBE_RADIUS);

  /** Angular distance, in degrees of arc, to the nearest drawn coastline vertex. */
  function degreesToNearestCoastline(latitudeDeg: number, longitudeDeg: number): number {
    const target = geoToVector(latitudeDeg, longitudeDeg, TRANSIT_GLOBE_RADIUS);
    let nearest = Number.POSITIVE_INFINITY;
    for (let index = 0; index < positions.length; index += 3) {
      const dx = positions[index]! - target.x;
      const dy = positions[index + 1]! - target.y;
      const dz = positions[index + 2]! - target.z;
      const chord = Math.hypot(dx, dy, dz);
      if (chord < nearest) nearest = chord;
    }
    // Chord length on a sphere of radius R back to a central angle.
    return 2 * Math.asin(Math.min(1, nearest / (2 * TRANSIT_GLOBE_RADIUS))) * (180 / Math.PI);
  }

  it("has coastline data to test against", () => {
    expect(positions.length).toBeGreaterThan(30_000);
    expect(positions.length % 3).toBe(0);
  });

  it("places real coastal landmarks within a degree of drawn coastline", () => {
    // Coastal cities and capes. At Natural Earth's 110m generalisation a real
    // coastal point should be well inside one degree of arc (about 111 km) of a
    // drawn vertex. A 90-degree registration error puts these thousands of
    // kilometres out to sea.
    const coastal: Array<[string, number, number]> = [
      ["Pearl Harbor", 21.35, -157.95],
      ["Yokosuka", 35.28, 139.67],
      ["Cape Town", -33.92, 18.42],
      ["Cape Horn", -55.98, -67.27],
      ["Singapore", 1.29, 103.85],
      ["Gibraltar", 36.14, -5.35],
      ["Norfolk, Virginia", 36.85, -76.29],
      ["Reykjavik", 64.15, -21.94],
      ["Perth", -31.95, 115.86],
      ["Valparaiso", -33.05, -71.62],
      ["Djibouti", 11.59, 43.15],
    ];
    for (const [name, latitude, longitude] of coastal) {
      const separation = degreesToNearestCoastline(latitude, longitude);
      expect(separation, `${name} is ${separation.toFixed(2)} degrees from drawn coastline`)
        .toBeLessThan(2.5);
    }
  });

  it("records that the shipped land artifact has no small islands, because a Pacific planner will notice", () => {
    // manifest.land is Natural Earth 110m *admin-0 countries*: 177 features,
    // 10,654 vertices. Sovereign countries only, heavily generalised. Guam,
    // Wake, Midway and Diego Garcia are simply not in it - which is exactly the
    // set of places a transit planner puts waypoints on.
    //
    // This is an upstream data property, not a projection error, and this test
    // exists so the next person to see a waypoint floating in empty ocean finds
    // the reason here instead of hunting a coordinate bug. Fixing it means
    // publishing a finer land artifact from the release pipeline.
    const guam = degreesToNearestCoastline(13.44, 144.79);
    const diegoGarcia = degreesToNearestCoastline(-7.31, 72.41);
    expect(guam).toBeGreaterThan(5);
    expect(diegoGarcia).toBeGreaterThan(5);
    expect(land.features.length).toBe(177);
  });

  it("keeps deep-ocean points far from any drawn coastline", () => {
    // The other half of the check. If the transform were rotated, some of these
    // would land on a coast, and the previous test alone would not notice
    // because the world has a lot of coastline.
    const openOcean: Array<[string, number, number]> = [
      ["Point Nemo", -48.88, -123.39],
      ["Central North Pacific", 30, -160],
      ["Central South Atlantic", -30, -20],
      ["Central Indian Ocean", -20, 80],
    ];
    for (const [name, latitude, longitude] of openOcean) {
      const separation = degreesToNearestCoastline(latitude, longitude);
      expect(separation, `${name} is only ${separation.toFixed(2)} degrees from drawn coastline`)
        .toBeGreaterThan(5);
    }
  });

  it("is not fooled by a deliberately mis-registered transform", () => {
    // Prove the coastal test can actually fail. Rotate the whole landmark set 90
    // degrees in longitude - the exact error this codebase shipped once - and
    // the assertion has to break.
    //
    // Deliberately an ensemble rather than one point: the world has enough
    // coastline that any single rotated landmark can land near some unrelated
    // coast by luck. Pearl Harbor rotated 90 degrees east lands 2.4 degrees off
    // Hispaniola, which would have passed a single-point control and proved
    // nothing. The median over twelve landmarks cannot do that.
    const landmarks: Array<[number, number]> = [
      [21.35, -157.95], [35.28, 139.67], [-33.92, 18.42], [-55.98, -67.27],
      [1.29, 103.85], [36.14, -5.35], [36.85, -76.29], [64.15, -21.94],
      [-31.95, 115.86], [-33.05, -71.62], [11.59, 43.15], [40.6, 14.3],
    ];
    const trueSeparations = landmarks
      .map(([latitude, longitude]) => degreesToNearestCoastline(latitude, longitude))
      .sort((a, b) => a - b);
    const rotatedSeparations = landmarks
      .map(([latitude, longitude]) => degreesToNearestCoastline(latitude, longitude + 90))
      .sort((a, b) => a - b);
    const median = (values: number[]) => values[Math.floor(values.length / 2)]!;

    expect(median(trueSeparations)).toBeLessThan(1);
    expect(median(rotatedSeparations)).toBeGreaterThan(5);
    expect(Math.max(...trueSeparations)).toBeLessThan(2.5);
  });
});
