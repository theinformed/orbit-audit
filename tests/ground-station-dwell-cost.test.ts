import { describe, expect, it } from "vitest";
import { computeStationPasses, type GroundStation } from "../src/ground-stations";
import type { OmmRecord } from "../src/types";

/**
 * What one 24-hour dwell costs, and why anyone cares.
 *
 * `main.ts` renders a selected station's dwell inside `environmentLegendSpec`,
 * and that function runs on every environment tick — several times a second
 * during timed playback. A dwell is 2,880 coarse SGP4 samples plus a bisection
 * at every mask crossing, so if it were slow it would be slow in the one place
 * that cannot afford it, and only for the visitor who selected both a station
 * and a spacecraft. That is exactly the shape of a defect nobody reproduces.
 *
 * This is a budget, not a benchmark: it fails only if the cost has moved by an
 * order of magnitude, which is the change that would matter.
 */
const GOLDSTONE: GroundStation = {
  id: "nasa-dsn-goldstone-dss14",
  name: "Goldstone DSS-14 (Mars)",
  network: "NASA Deep Space Network",
  operator: "NASA / JPL-Caltech",
  operatorKind: "civil-agency",
  country: "United States",
  latitudeDeg: 35.425901,
  longitudeDeg: -116.889538,
  altitudeM: 1001,
  coordinatePrecision: "published-survey",
  roles: ["deep-space-tracking"],
  source: "https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf",
  sourceName: "DSN 810-005 Module 301 Rev. P, Table 5",
  sourceRetrieved: "2026-08-08",
  licence: "NASA/JPL-Caltech",
};

/**
 * A real published Landsat 8 element set, copied from release 20260809T044819Z
 * rather than read from disk: the cost being measured is the propagation, and a
 * fixture makes the measurement reproducible on a machine with no archive.
 */
const LANDSAT_8: OmmRecord = {
  ARG_OF_PERICENTER: 93.4322,
  BSTAR: 4.3921e-5,
  CLASSIFICATION_TYPE: "U",
  ECCENTRICITY: 0.0001278,
  ELEMENT_SET_NO: 999,
  EPHEMERIS_TYPE: 0,
  EPOCH: "2026-08-08T19:57:57.913056",
  INCLINATION: 98.2269,
  MEAN_ANOMALY: 266.7022,
  MEAN_MOTION: 14.57108132,
  MEAN_MOTION_DDOT: 0,
  MEAN_MOTION_DOT: 1.52e-6,
  NORAD_CAT_ID: 39084,
  OBJECT_ID: "2013-008A",
  OBJECT_NAME: "LANDSAT 8",
  RA_OF_ASC_NODE: 290.3327,
  REV_AT_EPOCH: 70556,
} as unknown as OmmRecord;

describe("a selected station's dwell is cheap enough to sit on the render path", () => {
  it("computes a 24-hour dwell inside the tick budget", () => {
    const from = new Date("2026-08-09T00:00:00Z");
    const started = performance.now();
    const dwell = computeStationPasses(GOLDSTONE, LANDSAT_8, {
      from,
      to: new Date(from.getTime() + 24 * 3600 * 1000),
    });
    const elapsed = performance.now() - started;

    // It answers something real rather than degenerately.
    expect(dwell.passes.length).toBeGreaterThan(0);
    expect(dwell.continuouslyVisible).toBe(false);
    expect(dwell.fractionOfWindow).toBeGreaterThan(0);
    expect(dwell.fractionOfWindow).toBeLessThan(1);

    // 250 ms is roughly ten times the measured cost. Crossing it means the
    // dwell has to move off the render path and behind a cache.
    expect(elapsed).toBeLessThan(250);
  });
});
