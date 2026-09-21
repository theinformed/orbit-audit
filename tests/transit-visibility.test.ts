import { describe, expect, it } from "vitest";
import {
  bisectCrossing,
  complementIntervals,
  coversEntirely,
  elevationDeg,
  extractWindows,
  mergeIntervals,
  rangeKm,
  recommendedStepSeconds,
  sphericalElevationDeg,
  summarizeCoverage,
  withinFootprint,
  type ElevationSample,
} from "../src/transit-visibility";
import { EARTH_RADIUS_KM, footprintAngularRadius, propagateOmm } from "../src/orbit";
import type { OmmRecord } from "../src/types";

const GEOSTATIONARY_ALTITUDE_KM = 35786.0;
const DEG = Math.PI / 180;

/**
 * An independent second implementation of the observer-to-satellite elevation,
 * written from the WGS-84 definitions rather than by calling satellite.js.
 *
 * This exists because the production path routes through a library helper
 * (`ecfToLookAngles`) whose argument order and units are exactly the kind of
 * thing that produces a plausible-looking wrong answer. Two implementations that
 * share no code have to agree.
 */
function independentElevationDeg(
  observerLatitudeDeg: number,
  observerLongitudeDeg: number,
  observerAltitudeKm: number,
  satelliteLatitudeDeg: number,
  satelliteLongitudeDeg: number,
  satelliteAltitudeKm: number,
): number {
  const a = 6378.137;
  const f = 1 / 298.257223563;
  const eSquared = f * (2 - f);
  const toEcef = (latitudeDeg: number, longitudeDeg: number, heightKm: number) => {
    const latitude = latitudeDeg * DEG;
    const longitude = longitudeDeg * DEG;
    const primeVertical = a / Math.sqrt(1 - eSquared * Math.sin(latitude) ** 2);
    return [
      (primeVertical + heightKm) * Math.cos(latitude) * Math.cos(longitude),
      (primeVertical + heightKm) * Math.cos(latitude) * Math.sin(longitude),
      (primeVertical * (1 - eSquared) + heightKm) * Math.sin(latitude),
    ] as const;
  };
  const observer = toEcef(observerLatitudeDeg, observerLongitudeDeg, observerAltitudeKm);
  const satellite = toEcef(satelliteLatitudeDeg, satelliteLongitudeDeg, satelliteAltitudeKm);
  const line = [
    satellite[0] - observer[0],
    satellite[1] - observer[1],
    satellite[2] - observer[2],
  ] as const;
  // Local geodetic up is the ellipsoid normal, which is NOT the position vector.
  const latitude = observerLatitudeDeg * DEG;
  const longitude = observerLongitudeDeg * DEG;
  const up = [
    Math.cos(latitude) * Math.cos(longitude),
    Math.cos(latitude) * Math.sin(longitude),
    Math.sin(latitude),
  ] as const;
  const range = Math.hypot(line[0], line[1], line[2]);
  const dot = line[0] * up[0] + line[1] * up[1] + line[2] * up[2];
  return Math.asin(Math.max(-1, Math.min(1, dot / range))) / DEG;
}

describe("elevation geometry", () => {
  it("puts a satellite directly overhead at 90 degrees", () => {
    expect(elevationDeg(0, 0, 0, 0, 0, GEOSTATIONARY_ALTITUDE_KM)).toBeCloseTo(90, 6);
    expect(elevationDeg(45, -30, 0, 45, -30, 700)).toBeCloseTo(90, 6);
    expect(elevationDeg(-62.5, 174, 0, -62.5, 174, 20200)).toBeCloseTo(90, 6);
  });

  it("does not confuse latitude with longitude", () => {
    // A lat/lon swap would make these two equal. They must not be.
    const overhead = elevationDeg(45, 0, 0, 45, 0, 800);
    const swapped = elevationDeg(45, 0, 0, 0, 45, 800);
    expect(overhead).toBeCloseTo(90, 6);
    expect(swapped).toBeLessThan(0);
  });

  it("agrees with an independent WGS-84 implementation that shares no code", () => {
    const cases: Array<[number, number, number, number, number, number]> = [
      [0, 0, 0, 0, 30, GEOSTATIONARY_ALTITUDE_KM],
      [35.6, 139.7, 0.02, 10, 175, GEOSTATIONARY_ALTITUDE_KM],
      [-33.9, 18.4, 0, 12.5, -75.2, 20200],
      [71.2, -156.8, 0.01, 64.9, -147.7, 550],
      [-54.8, -68.3, 0, 0, -100, 35786],
      [12.0, 43.0, 0.03, -8.0, 60.0, 1200],
    ];
    for (const [oLat, oLon, oAlt, sLat, sLon, sAlt] of cases) {
      expect(elevationDeg(oLat, oLon, oAlt, sLat, sLon, sAlt))
        .toBeCloseTo(independentElevationDeg(oLat, oLon, oAlt, sLat, sLon, sAlt), 8);
    }
  });

  it("reproduces the published geostationary horizon limit of about 81.3 degrees", () => {
    // From the equator a geostationary satellite reaches 0 degrees elevation at a
    // central angle of arccos(Re/r). With Re = 6378.137 and r = 42164.137 that is
    // 81.30 degrees of longitude separation - the standard published figure for
    // the geostationary visibility limit.
    const radius = EARTH_RADIUS_KM + GEOSTATIONARY_ALTITUDE_KM;
    const limitDeg = Math.acos(EARTH_RADIUS_KM / radius) / DEG;
    expect(limitDeg).toBeCloseTo(81.30, 2);
    expect(elevationDeg(0, 0, 0, 0, limitDeg, GEOSTATIONARY_ALTITUDE_KM)).toBeCloseTo(0, 4);
    expect(elevationDeg(0, 0, 0, 0, limitDeg - 1, GEOSTATIONARY_ALTITUDE_KM)).toBeGreaterThan(0);
    expect(elevationDeg(0, 0, 0, 0, limitDeg + 1, GEOSTATIONARY_ALTITUDE_KM)).toBeLessThan(0);
  });

  it("reproduces the published 5-degree geostationary coverage radius of about 76.3 degrees", () => {
    expect(footprintAngularRadius(GEOSTATIONARY_ALTITUDE_KM, 5) / DEG).toBeCloseTo(76.34, 1);
    expect(elevationDeg(0, 0, 0, 0, footprintAngularRadius(GEOSTATIONARY_ALTITUDE_KM, 5) / DEG, GEOSTATIONARY_ALTITUDE_KM))
      .toBeCloseTo(5, 3);
  });

  it("reproduces the published low-orbit horizon radius", () => {
    // A 400 km orbit sees to a central angle of arccos(Re/(Re+400)) = 19.79 deg,
    // about 2,200 km of ground distance - the familiar figure for the space
    // station's instantaneous horizon.
    const angleDeg = footprintAngularRadius(400, 0) / DEG;
    expect(angleDeg).toBeCloseTo(19.79, 1);
    expect(angleDeg * (Math.PI / 180) * EARTH_RADIUS_KM).toBeCloseTo(2202, -1);
  });

  it("returns a range consistent with the geostationary slant range at nadir and at the limb", () => {
    expect(rangeKm(0, 0, 0, 0, 0, GEOSTATIONARY_ALTITUDE_KM)).toBeCloseTo(35786, 0);
    // Slant range at the 0-degree limb is sqrt(r^2 - Re^2) = 41,679 km.
    const radius = EARTH_RADIUS_KM + GEOSTATIONARY_ALTITUDE_KM;
    const limbRange = Math.sqrt(radius ** 2 - EARTH_RADIUS_KM ** 2);
    expect(limbRange).toBeCloseTo(41679, -1);
    const limitDeg = Math.acos(EARTH_RADIUS_KM / radius) / DEG;
    expect(rangeKm(0, 0, 0, 0, limitDeg, GEOSTATIONARY_ALTITUDE_KM)).toBeCloseTo(limbRange, 0);
  });
});

describe("the spherical model the footprint circle draws, versus the rigorous answer", () => {
  it("agrees exactly at the equator, where geodetic and geocentric latitude coincide", () => {
    for (const separationDeg of [5, 20, 45, 70, 81]) {
      const rigorous = elevationDeg(0, 0, 0, 0, separationDeg, GEOSTATIONARY_ALTITUDE_KM);
      const spherical = sphericalElevationDeg(separationDeg * DEG, GEOSTATIONARY_ALTITUDE_KM);
      expect(spherical).toBeCloseTo(rigorous, 6);
    }
  });

  it("differs by less than a quarter of a degree at mid-latitude, and the sign is systematic", () => {
    // This is the flattening of the ellipsoid showing up as an elevation bias.
    // It is bounded by the maximum geodetic-geocentric latitude difference,
    // 0.19 degrees at 45 degrees latitude. Anything larger means a real error,
    // not a model difference - so bound it rather than merely observing it.
    let largest = 0;
    for (let latitude = -80; latitude <= 80; latitude += 10) {
      for (const separationDeg of [10, 30, 60]) {
        const satelliteLongitudeDeg = separationDeg;
        const rigorous = elevationDeg(latitude, 0, 0, 0, satelliteLongitudeDeg, GEOSTATIONARY_ALTITUDE_KM);
        const centralAngle = Math.acos(
          Math.min(1, Math.cos(latitude * DEG) * Math.cos(satelliteLongitudeDeg * DEG)),
        );
        const spherical = sphericalElevationDeg(centralAngle, GEOSTATIONARY_ALTITUDE_KM);
        largest = Math.max(largest, Math.abs(rigorous - spherical));
      }
    }
    expect(largest).toBeLessThan(0.25);
    expect(largest).toBeGreaterThan(0.01);
  });

  it("makes the drawn footprint circle exactly the set of points above the mask, in the spherical model", () => {
    for (const maskDeg of [0, 5, 10, 15]) {
      const radius = footprintAngularRadius(GEOSTATIONARY_ALTITUDE_KM, maskDeg);
      expect(withinFootprint(radius - 1e-9, GEOSTATIONARY_ALTITUDE_KM, maskDeg)).toBe(true);
      expect(withinFootprint(radius + 1e-9, GEOSTATIONARY_ALTITUDE_KM, maskDeg)).toBe(false);
      expect(sphericalElevationDeg(radius, GEOSTATIONARY_ALTITUDE_KM)).toBeCloseTo(maskDeg, 6);
    }
  });
});

describe("the elevation mask changes the answer", () => {
  it("shrinks a geostationary footprint monotonically as the mask rises", () => {
    const radii = [0, 5, 10, 20, 30].map((mask) => footprintAngularRadius(GEOSTATIONARY_ALTITUDE_KM, mask));
    for (let index = 1; index < radii.length; index += 1) {
      expect(radii[index]!).toBeLessThan(radii[index - 1]!);
    }
  });

  it("removes a satellite from the answer between 0 and 10 degrees", () => {
    // A geostationary satellite 79 degrees away in longitude is above a
    // 0-degree horizon and below a 5-degree mask. This is the whole reason the
    // mask is a control rather than a constant.
    const elevation = elevationDeg(0, 0, 0, 0, 79, GEOSTATIONARY_ALTITUDE_KM);
    expect(elevation).toBeGreaterThan(0);
    expect(elevation).toBeLessThan(5);
  });
});

describe("window extraction", () => {
  const sample = (timeMs: number, elevation: number): ElevationSample =>
    ({ timeMs, elevationDeg: elevation, rangeKm: 1000 });

  it("opens and closes a window at the mask crossing", () => {
    const windows = extractWindows(1, [
      sample(0, -5),
      sample(60_000, 5),
      sample(120_000, 20),
      sample(180_000, 4),
      sample(240_000, -8),
    ], { maskDeg: 5, gridStepSeconds: 60 });
    expect(windows).toHaveLength(1);
    expect(windows[0]!.startMs).toBe(60_000);
    expect(windows[0]!.peakElevationDeg).toBe(20);
    expect(windows[0]!.peakAtMs).toBe(120_000);
    expect(windows[0]!.truncatedAtStart).toBe(false);
    expect(windows[0]!.truncatedAtEnd).toBe(false);
    // The closing edge is interpolated between +20 and +4 crossing 5.
    expect(windows[0]!.endMs).toBeGreaterThan(120_000);
    expect(windows[0]!.endMs).toBeLessThan(180_000);
  });

  it("marks a window truncated when it is cut by the ends of the transit, not by geometry", () => {
    const windows = extractWindows(1, [sample(0, 30), sample(60_000, 40), sample(120_000, 35)], {
      maskDeg: 5,
      gridStepSeconds: 60,
    });
    expect(windows).toHaveLength(1);
    expect(windows[0]!.truncatedAtStart).toBe(true);
    expect(windows[0]!.truncatedAtEnd).toBe(true);
  });

  it("finds two windows separated by a gap", () => {
    const windows = extractWindows(1, [
      sample(0, 10), sample(60_000, -10), sample(120_000, -10), sample(180_000, 10),
    ], { maskDeg: 0, gridStepSeconds: 60 });
    expect(windows).toHaveLength(2);
  });

  it("returns nothing when the mask is never reached", () => {
    const windows = extractWindows(1, [sample(0, 4.9), sample(60_000, 4.99)], { maskDeg: 5, gridStepSeconds: 60 });
    expect(windows).toHaveLength(0);
  });

  it("refines an edge by bisection when a continuous elevation function is supplied", () => {
    // Elevation crosses 5 degrees at exactly t = 42,000 ms on this ramp.
    const elevationAt = (timeMs: number) => -10 + (timeMs / 60_000) * 20;
    const crossingMs = bisectCrossing(elevationAt, 5, 0, 60_000, 1);
    expect(crossingMs).toBeCloseTo(45_000, 0);
    const windows = extractWindows(1, [sample(0, -10), sample(60_000, 10)], {
      maskDeg: 5,
      gridStepSeconds: 60,
      edgeToleranceSeconds: 0.001,
      elevationAt,
    });
    expect(windows[0]!.startMs).toBeCloseTo(45_000, 0);
  });
});

describe("interval algebra", () => {
  it("merges overlapping and touching intervals", () => {
    expect(mergeIntervals([
      { startMs: 0, endMs: 10 },
      { startMs: 5, endMs: 20 },
      { startMs: 20, endMs: 25 },
      { startMs: 40, endMs: 50 },
    ])).toEqual([{ startMs: 0, endMs: 25 }, { startMs: 40, endMs: 50 }]);
  });

  it("finds the gaps inside a bounded transit", () => {
    expect(complementIntervals([{ startMs: 10, endMs: 20 }, { startMs: 30, endMs: 40 }], 0, 50))
      .toEqual([{ startMs: 0, endMs: 10 }, { startMs: 20, endMs: 30 }, { startMs: 40, endMs: 50 }]);
  });

  it("reports no gaps when coverage spans the transit", () => {
    expect(complementIntervals([{ startMs: -100, endMs: 200 }], 0, 100)).toEqual([]);
    expect(coversEntirely([{ startMs: -100, endMs: 200 }], 0, 100)).toBe(true);
  });

  it("treats a one-second handover seam as continuous only when told to", () => {
    const intervals = [{ startMs: 0, endMs: 50_000 }, { startMs: 51_000, endMs: 100_000 }];
    expect(coversEntirely(intervals, 0, 100_000)).toBe(false);
    expect(coversEntirely(intervals, 0, 100_000, 1000)).toBe(true);
  });

  it("summarises coverage fraction and longest gap", () => {
    const summary = summarizeCoverage(
      [{ startMs: 0, endMs: 25 }, { startMs: 50, endMs: 60 }],
      0,
      100,
    );
    expect(summary.coveredMs).toBe(35);
    expect(summary.transitMs).toBe(100);
    expect(summary.coveredFraction).toBeCloseTo(0.35, 10);
    expect(summary.continuous).toBe(false);
    expect(summary.gaps).toEqual([{ startMs: 25, endMs: 50 }, { startMs: 60, endMs: 100 }]);
    expect(summary.longestGapMs).toBe(40);
  });

  it("clips coverage that extends beyond the transit rather than counting it", () => {
    const summary = summarizeCoverage([{ startMs: -1000, endMs: 2000 }], 0, 100);
    expect(summary.coveredMs).toBe(100);
    expect(summary.coveredFraction).toBe(1);
  });
});

describe("grid step selection", () => {
  it("samples a low orbit far more often than a geostationary one", () => {
    expect(recommendedStepSeconds(92)).toBeLessThan(45);
    expect(recommendedStepSeconds(92)).toBeGreaterThan(20);
    expect(recommendedStepSeconds(1436)).toBe(300);
    expect(recommendedStepSeconds(718)).toBe(239.33333333333334);
  });

  it("never returns a step that would be useless at either extreme", () => {
    expect(recommendedStepSeconds(Number.NaN)).toBe(30);
    expect(recommendedStepSeconds(0)).toBe(30);
    expect(recommendedStepSeconds(1)).toBe(10);
    expect(recommendedStepSeconds(100_000)).toBe(300);
  });
});

/**
 * End-to-end against real SGP4, using the propagator the site already ships.
 *
 * The independent check here is a physical invariant rather than a number
 * copied from somewhere: a satellite in a near-geostationary orbit over a fixed
 * longitude must be continuously visible from a point beneath it and never
 * visible from the antipode, at any mask.
 */
describe("against the real propagator", () => {
  const geostationaryOmm: OmmRecord = {
    OBJECT_NAME: "TEST GEO",
    OBJECT_ID: "2020-000A",
    EPOCH: "2026-08-01T00:00:00.000000",
    MEAN_MOTION: 1.0027,
    ECCENTRICITY: 0.0001,
    INCLINATION: 0.02,
    RA_OF_ASC_NODE: 0,
    ARG_OF_PERICENTER: 0,
    MEAN_ANOMALY: 0,
    EPHEMERIS_TYPE: 0,
    CLASSIFICATION_TYPE: "U",
    NORAD_CAT_ID: 99999,
    ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 1000,
    BSTAR: 0,
    MEAN_MOTION_DOT: 0,
    MEAN_MOTION_DDOT: 0,
  };

  it("propagates to a geosynchronous altitude", () => {
    const state = propagateOmm(geostationaryOmm, new Date("2026-08-02T00:00:00Z"));
    expect(state).not.toBeNull();
    expect(state!.altitudeKm).toBeGreaterThan(35_500);
    expect(state!.altitudeKm).toBeLessThan(36_100);
  });

  it("is always visible from beneath it and never from the antipode", () => {
    const start = Date.parse("2026-08-02T00:00:00Z");
    let beneathVisible = 0;
    let antipodeVisible = 0;
    let steps = 0;
    for (let minute = 0; minute < 1440; minute += 15) {
      const state = propagateOmm(geostationaryOmm, new Date(start + minute * 60_000));
      if (!state) continue;
      steps += 1;
      const beneath = elevationDeg(0, state.longitudeDeg, 0, state.latitudeDeg, state.longitudeDeg, state.altitudeKm);
      const antipodeLongitude = ((state.longitudeDeg + 360) % 360) - 180;
      const antipode = elevationDeg(0, antipodeLongitude, 0, state.latitudeDeg, state.longitudeDeg, state.altitudeKm);
      if (beneath >= 10) beneathVisible += 1;
      if (antipode >= 0) antipodeVisible += 1;
    }
    expect(steps).toBeGreaterThan(90);
    expect(beneathVisible).toBe(steps);
    expect(antipodeVisible).toBe(0);
  });
});
