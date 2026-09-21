import { describe, expect, it } from "vitest";
import {
  classifyGeoSubtype,
  classifyOrbit,
  deriveOrbit,
  footprintAngularRadius,
  footprintPoints,
  propagateOmm,
  propagateOmmInFrozenEarthFrame,
} from "../src/orbit";
import type { OmmRecord } from "../src/types";

const inclinedGso: OmmRecord = {
  OBJECT_NAME: "SBIRS GEO-4 teaching fixture",
  OBJECT_ID: "2017-004A",
  EPOCH: "2026-08-06T05:34:17.227776",
  MEAN_MOTION: 1.00273363,
  ECCENTRICITY: 0.00025656,
  INCLINATION: 2.3375,
  RA_OF_ASC_NODE: 44.4709,
  ARG_OF_PERICENTER: 86.9211,
  MEAN_ANOMALY: 289.0667,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 41937,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 3510,
  BSTAR: 0,
  MEAN_MOTION_DOT: 0.00000133,
  MEAN_MOTION_DDOT: 0,
};

describe("orbit derivation", () => {
  it("classifies a typical low-Earth orbit", () => {
    const orbit = deriveOrbit(15.5, 0.0007, 51.6);
    expect(orbit.regime).toBe("LEO");
    expect(orbit.periodMinutes).toBeGreaterThan(90);
    expect(orbit.periodMinutes).toBeLessThan(95);
    expect(orbit.perigeeKm).toBeGreaterThan(350);
    expect(orbit.apogeeKm).toBeLessThan(500);
  });

  it("distinguishes geostationary geometry from generic high orbits", () => {
    expect(classifyOrbit(35770, 35805, 1436, 0.1, 0.0001)).toBe("GEO");
    expect(classifyOrbit(500, 39800, 720, 63.4, 0.72)).toBe("HEO");
    // INCLINED GEOSYNCHRONOUS, from the live catalog rather than invented.
    // BEIDOU 3 IGSO-1 differs from the GEO case above in inclination alone.
    expect(classifyOrbit(35672.5, 35900.7, 1436.099, 58.797, 0.00271)).toBe("IGSO");
    // QZS-2 (MICHIBIKI-2) is the eccentric end of the class at e = 0.075 --
    // still inside the 0.15 ceiling the GEO test uses, and its 38,963 km apogee
    // stays under the 40,000 km the HEO test needs, so it does not slip past.
    expect(classifyOrbit(32613.6, 38962.8, 1436.18, 39.328, 0.07529)).toBe("IGSO");
    // The 20 deg wall, held from both sides. It is one threshold, not two.
    expect(classifyOrbit(35770, 35805, 1436, 19.999, 0.0001)).toBe("GEO");
    expect(classifyOrbit(35770, 35805, 1436, 20.0, 0.0001)).toBe("IGSO");
    // A genuine OTHER survives: IPM 2/BREEZE-M, a spent upper stage in a
    // near-circular 25.2-hour disposal orbit ABOVE the belt. Its period is past
    // the geosynchronous window, so widening IGSO must never reach it.
    expect(classifyOrbit(36877.4, 37604.9, 1511.045, 5.543, 0.00834)).toBe("OTHER");
  });

  it("separates geostationary geometry from other geosynchronous objects", () => {
    expect(classifyGeoSubtype(1436.1, 0.04, 0.0003)).toBe("geostationary");
    expect(classifyGeoSubtype(1436.1, 8.2, 0.0003)).toBe("other-gso");
    expect(classifyGeoSubtype(1450, 0.04, 0.0003)).toBe("other-gso");
  });

  it("keeps the inertial orbit distinct from a compact Earth-fixed GSO trace", () => {
    const frameTime = new Date("2026-08-06T19:59:27Z");
    const ground = [];
    const inertial = [];
    for (let hour = -12; hour <= 12; hour += 1) {
      const sampleTime = new Date(frameTime.getTime() + hour * 3_600_000);
      const groundState = propagateOmm(inclinedGso, sampleTime);
      const inertialState = propagateOmmInFrozenEarthFrame(inclinedGso, sampleTime, frameTime);
      if (groundState) ground.push(groundState);
      if (inertialState) inertial.push(inertialState);
    }

    expect(Math.max(...ground.map((state) => state.longitudeDeg)) - Math.min(...ground.map((state) => state.longitudeDeg))).toBeLessThan(1);
    expect(Math.max(...ground.map((state) => state.latitudeDeg)) - Math.min(...ground.map((state) => state.latitudeDeg))).toBeGreaterThan(4);
    expect(Math.min(...inertial.map((state) => state.x))).toBeLessThan(-30_000);
    expect(Math.max(...inertial.map((state) => state.x))).toBeGreaterThan(30_000);
  });
});

describe("geometric horizon footprint", () => {
  it("shrinks as minimum elevation increases", () => {
    expect(footprintAngularRadius(550, 10)).toBeLessThan(footprintAngularRadius(550, 0));
  });

  it("returns a closed WGS-84 tangent-horizon polygon", () => {
    const points = footprintPoints(12, 179, 550, 0, 48);
    expect(points).toHaveLength(49);
    expect(points[0]?.[0]).toBeCloseTo(points.at(-1)?.[0] ?? 0, 8);
    expect(points[0]?.[1]).toBeCloseTo(points.at(-1)?.[1] ?? 0, 8);
  });

  it("places every zero-elevation boundary point on the spacecraft tangent plane", () => {
    const a = 6378.137;
    const b = 6356.752314245;
    const e2 = 1 - b ** 2 / a ** 2;
    const latitude = 62 * Math.PI / 180;
    const longitude = 15 * Math.PI / 180;
    const height = 1200;
    const n = a / Math.sqrt(1 - e2 * Math.sin(latitude) ** 2);
    const satellite = {
      x: (n + height) * Math.cos(latitude) * Math.cos(longitude),
      y: (n + height) * Math.cos(latitude) * Math.sin(longitude),
      z: (n * (1 - e2) + height) * Math.sin(latitude),
    };
    footprintPoints(62, 15, height, 0, 64).forEach(([pointLongitude, pointLatitude]) => {
      const lat = pointLatitude * Math.PI / 180;
      const lon = pointLongitude * Math.PI / 180;
      const surfaceN = a / Math.sqrt(1 - e2 * Math.sin(lat) ** 2);
      const surface = {
        x: surfaceN * Math.cos(lat) * Math.cos(lon),
        y: surfaceN * Math.cos(lat) * Math.sin(lon),
        z: surfaceN * (1 - e2) * Math.sin(lat),
      };
      const tangent = satellite.x * surface.x / a ** 2
        + satellite.y * surface.y / a ** 2
        + satellite.z * surface.z / b ** 2;
      expect(tangent).toBeCloseTo(1, 8);
    });
  });
});
