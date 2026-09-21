import { describe, expect, it } from "vitest";

import fixture from "./fixtures/thermosphere-frame.json";
import { RULER_EARTH_RADIUS_KM, sharedDisplayRadius } from "../src/radial-ruler";
import { decodeThermosphereFrame, isopycnicAltitudeKm, type ThermosphereFrame } from "../src/thermosphere";
import {
  SURFACE_ALTITUDE_DOMAIN_KM,
  buildIsopycnicContours,
  buildIsopycnicSurface,
  surfaceColor,
} from "../src/thermosphere-surface";

const frame = decodeThermosphereFrame(fixture as unknown as ThermosphereFrame);
const EARTH_SCENE_RADIUS = 2;

describe("the surface the layer draws", () => {
  it("places every vertex on the same ruler the satellites use", () => {
    // This is the whole point of the layer: if the surface used its own scale,
    // "is the satellite inside the atmosphere?" would be answered by a
    // coincidence of two scales rather than by the picture.
    const surface = buildIsopycnicSurface(frame, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      level: 1e-11,
      latitudeStepDeg: 30,
      longitudeStepDeg: 30,
    });
    for (let vertex = 0; vertex < surface.totalVertices; vertex += 1) {
      const altitude = surface.altitudeKm[vertex]!;
      if (!Number.isFinite(altitude)) continue;
      const radius = Math.hypot(
        surface.positions[vertex * 3]!,
        surface.positions[vertex * 3 + 1]!,
        surface.positions[vertex * 3 + 2]!,
      );
      const expected = sharedDisplayRadius(
        (RULER_EARTH_RADIUS_KM + altitude) / RULER_EARTH_RADIUS_KM,
        EARTH_SCENE_RADIUS,
      );
      expect(radius).toBeCloseTo(expected, 6);
    }
  });

  it("agrees with the physics module about the altitude it is drawing", () => {
    const surface = buildIsopycnicSurface(frame, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      level: 1e-11,
      latitudeStepDeg: 45,
      longitudeStepDeg: 45,
    });
    // Vertex (latIndex 2 => latitude 0, lonIndex 2 => longitude 90).
    const vertex = 2 * surface.longitudeCount + 2;
    expect(surface.altitudeKm[vertex]).toBeCloseTo(
      isopycnicAltitudeKm(frame, 0, 90, 1e-11)!,
      6,
    );
  });

  it("leaves a hole where the level is not crossed, rather than a floor", () => {
    // Denser than anything in the column: there is no such altitude anywhere,
    // so there must be no surface and no triangles at all.
    const surface = buildIsopycnicSurface(frame, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      level: 1e-6,
      latitudeStepDeg: 30,
      longitudeStepDeg: 30,
    });
    expect(surface.missingVertices).toBe(surface.totalVertices);
    expect(surface.indices.length).toBe(0);
    expect(surface.minAltitudeKm).toBeNaN();
  });

  it("drops only the quads that touch a hole", () => {
    // The fixture is missing one cell at 300 km, latitude -60, longitude 0. A
    // level that resolves through that cell loses the quads around it and keeps
    // the rest — a partial surface, honestly partial.
    const surface = buildIsopycnicSurface(frame, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      level: 1e-10,
      latitudeStepDeg: 30,
      longitudeStepDeg: 30,
    });
    expect(surface.missingVertices).toBeGreaterThan(0);
    expect(surface.missingVertices).toBeLessThan(surface.totalVertices);
    expect(surface.indices.length).toBeGreaterThan(0);
  });

  it("closes the longitude seam", () => {
    // The mesh runs 0..360 inclusive, so the last column coincides with the
    // first. If they disagreed there would be a visible crack down the globe.
    const surface = buildIsopycnicSurface(frame, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      level: 1e-11,
      latitudeStepDeg: 30,
      longitudeStepDeg: 30,
    });
    for (let latIndex = 0; latIndex < surface.latitudeCount; latIndex += 1) {
      const first = latIndex * surface.longitudeCount;
      const last = first + surface.longitudeCount - 1;
      expect(surface.altitudeKm[last]).toBeCloseTo(surface.altitudeKm[first]!, 9);
    }
  });
});

describe("the surface colour", () => {
  it("spans a fixed altitude domain, not the frame's own range", () => {
    // A per-frame ramp would paint a quiet day exactly like a storm.
    const low = surfaceColor(SURFACE_ALTITUDE_DOMAIN_KM.low);
    const high = surfaceColor(SURFACE_ALTITUDE_DOMAIN_KM.high);
    expect(low).not.toEqual(high);
    expect(surfaceColor(SURFACE_ALTITUDE_DOMAIN_KM.low - 100)).toEqual(low);
    expect(surfaceColor(SURFACE_ALTITUDE_DOMAIN_KM.high + 100)).toEqual(high);
  });

  it("rises in lightness with altitude, so a swelling surface reads as brighter", () => {
    const lightness = (altitude: number) => {
      const [r, g, b] = surfaceColor(altitude);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    let previous = -Infinity;
    for (let altitude = 250; altitude <= 600; altitude += 10) {
      const value = lightness(altitude);
      expect(value).toBeGreaterThanOrEqual(previous - 1e-9);
      previous = value;
    }
    expect(lightness(600)).toBeGreaterThan(lightness(250) + 0.2);
  });
});


describe("the contours that make the shape readable", () => {
  /**
   * The colour ramp alone could not show the surface's shape: about 80 km of
   * height across the whole globe, on a compressed radial ruler, at the low
   * opacity the layer needs in order not to bury the Earth. Measured on
   * production it drew as a smooth featureless shell.
   *
   * Each contour is the set of places the surface is at exactly one stated
   * altitude — a fact about the field, not shading invented to look
   * three-dimensional.
   */
  const surface = buildIsopycnicSurface(frame, {
    earthSceneRadius: EARTH_SCENE_RADIUS,
    level: 1e-11,
    latitudeStepDeg: 10,
    longitudeStepDeg: 10,
  });

  it("draws nothing when the surface is perfectly flat", () => {
    // The fixture's atmosphere has no horizontal structure at all, so an
    // honest contour set over it is EMPTY. Lines here would be invented relief.
    const points = buildIsopycnicContours(surface, { intervalKm: 25 });
    expect(points.length % 6).toBe(0);
    expect(points.length).toBe(0);
  });

  it("draws a line where the surface really does cross the level", () => {
    // Tilt the field so one hemisphere sits higher, which is what a storm does.
    const tilted = { ...surface, altitudeKm: Float64Array.from(surface.altitudeKm) };
    for (let index = 0; index < tilted.altitudeKm.length; index += 1) {
      const lat = Math.floor(index / surface.longitudeCount);
      tilted.altitudeKm[index] = 400 + lat * 6;
    }
    tilted.minAltitudeKm = 400;
    tilted.maxAltitudeKm = 400 + (surface.latitudeCount - 1) * 6;
    const points = buildIsopycnicContours(tilted, { intervalKm: 25 });
    expect(points.length).toBeGreaterThan(0);
    expect(points.length % 6).toBe(0);
    for (const value of points) expect(Number.isFinite(value)).toBe(true);
  });

  it("does not close a contour across a hole", () => {
    // A missing cell is a place the level was never resolved. Bridging it would
    // draw a line through data that does not exist.
    const holed = { ...surface, altitudeKm: Float64Array.from(surface.altitudeKm) };
    for (let index = 0; index < holed.altitudeKm.length; index += 1) {
      const lat = Math.floor(index / surface.longitudeCount);
      holed.altitudeKm[index] = 400 + lat * 6;
    }
    holed.minAltitudeKm = 400;
    holed.maxAltitudeKm = 400 + (surface.latitudeCount - 1) * 6;
    const full = buildIsopycnicContours(holed, { intervalKm: 25 }).length;
    holed.altitudeKm[Math.floor(holed.altitudeKm.length / 2)] = Number.NaN;
    const holed_count = buildIsopycnicContours(holed, { intervalKm: 25 }).length;
    expect(holed_count).toBeLessThan(full);
  });

  it("puts its lines on the surface, not floating near it", () => {
    const tilted = { ...surface, altitudeKm: Float64Array.from(surface.altitudeKm) };
    for (let index = 0; index < tilted.altitudeKm.length; index += 1) {
      const lat = Math.floor(index / surface.longitudeCount);
      tilted.altitudeKm[index] = 400 + lat * 6;
    }
    tilted.minAltitudeKm = 400;
    tilted.maxAltitudeKm = 400 + (surface.latitudeCount - 1) * 6;
    const points = buildIsopycnicContours(tilted, { intervalKm: 25 });
    // Every contour vertex must sit within a fraction of a percent of the
    // radius of the surface vertices around it — the small offset exists only
    // to stop depth fighting.
    const radii: number[] = [];
    for (let index = 0; index < points.length; index += 3) {
      radii.push(Math.hypot(points[index]!, points[index + 1]!, points[index + 2]!));
    }
    const surfaceRadii: number[] = [];
    for (let index = 0; index < surface.totalVertices; index += 1) {
      const r = Math.hypot(
        surface.positions[index * 3]!,
        surface.positions[index * 3 + 1]!,
        surface.positions[index * 3 + 2]!,
      );
      if (r > 0) surfaceRadii.push(r);
    }
    const low = Math.min(...surfaceRadii) * 0.99;
    const high = Math.max(...surfaceRadii) * 1.01;
    for (const radius of radii) {
      expect(radius).toBeGreaterThan(low);
      expect(radius).toBeLessThan(high);
    }
  });
});
