/**
 * Dwell, passes, the published-link index, and the environment over a station.
 *
 * The element sets here are synthetic: they are valid SGP4 inputs chosen to
 * make a geometric property checkable, not claims about any real spacecraft.
 */
import { describe, expect, it } from "vitest";
import {
  ASSUMED_MINIMUM_ELEVATION_DEG,
  computeStationPasses,
  elevationDeg,
  indexGroundStations,
  sampleDrapAtStation,
  sampleTecAtStation,
  slantRangeKm,
  stationMinimumElevationDeg,
  stationVisibilityRing,
  type GroundStation,
  type GroundStationBundle,
} from "../src/ground-stations";
import { footprintAngularRadius, EARTH_RADIUS_KM } from "../src/orbit";
import type { DrapBundle } from "../src/drap";
import type { OmmRecord, SpaceWeatherBundle } from "../src/types";

function station(overrides: Partial<GroundStation> = {}): GroundStation {
  return {
    id: "test-station",
    name: "Test Station",
    network: "Test",
    operator: "Test",
    operatorKind: "civil-agency",
    country: "Testland",
    latitudeDeg: 37.9257,
    longitudeDeg: -75.4757,
    coordinatePrecision: "published-survey",
    roles: ["data-downlink"],
    source: "https://example.gov/",
    sourceName: "Test",
    sourceRetrieved: "2026-08-07",
    licence: "Public domain",
    ...overrides,
  };
}

function omm(overrides: Partial<OmmRecord> = {}): OmmRecord {
  return {
    OBJECT_NAME: "SYNTHETIC",
    OBJECT_ID: "2026-001A",
    EPOCH: "2026-08-07T00:00:00.000Z",
    MEAN_MOTION: 15.5,
    ECCENTRICITY: 0.0005,
    INCLINATION: 51.64,
    RA_OF_ASC_NODE: 120,
    ARG_OF_PERICENTER: 90,
    MEAN_ANOMALY: 0,
    EPHEMERIS_TYPE: 0,
    CLASSIFICATION_TYPE: "U",
    NORAD_CAT_ID: 99001,
    ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 1,
    BSTAR: 0.0001,
    MEAN_MOTION_DOT: 0,
    MEAN_MOTION_DDOT: 0,
    ...overrides,
  } as OmmRecord;
}

/** Same base64 the browser decodes with, without reaching for a Node global. */
function base64OfBytes(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

const WINDOW_START = new Date("2026-08-07T00:00:00Z");

describe("elevation and the coverage footprint are the same geometry", () => {
  /**
   * `stationVisibilityRing` is `footprintAngularRadius` read backwards. If the
   * two ever disagree, the translucent cap drawn on the globe stops touching
   * the station exactly at acquisition, which is the whole teaching point.
   */
  it("returns exactly the mask elevation everywhere on the visibility ring", () => {
    for (const altitudeKm of [420, 550, 780, 20200, 35786]) {
      for (const mask of [0, 5, 10, 25]) {
        const site = station({ latitudeDeg: 47.3, longitudeDeg: 8.5 });
        for (const [longitude, latitude] of stationVisibilityRing(site, altitudeKm, mask, 24)) {
          expect(elevationDeg(site, latitude, longitude, altitudeKm)).toBeCloseTo(mask, 6);
        }
      }
    }
  });

  it("reads 90 degrees straight overhead and the mask at the horizon radius", () => {
    const site = station({ latitudeDeg: 0, longitudeDeg: 0 });
    expect(elevationDeg(site, 0, 0, 550)).toBeCloseTo(90, 9);
    const horizon = (footprintAngularRadius(550, 0) * 180) / Math.PI;
    expect(elevationDeg(site, 0, horizon, 550)).toBeCloseTo(0, 6);
  });

  it("gives the altitude as the slant range straight overhead", () => {
    const site = station({ latitudeDeg: 12, longitudeDeg: -30 });
    expect(slantRangeKm(site, 12, -30, 550)).toBeCloseTo(550, 6);
    // And the horizon range is the tangent length, sqrt(r^2 - Re^2). Stepping
    // along the meridian, where a degree of latitude is a degree of arc.
    const horizon = (footprintAngularRadius(550, 0) * 180) / Math.PI;
    const radius = EARTH_RADIUS_KM + 550;
    expect(slantRangeKm(site, 12 + horizon, -30, 550))
      .toBeCloseTo(Math.sqrt(radius * radius - EARTH_RADIUS_KM * EARTH_RADIUS_KM), 3);
  });
});

describe("the horizon mask", () => {
  it("uses the operator's figure when the source publishes one", () => {
    expect(stationMinimumElevationDeg(station({ minimumElevationDeg: 3 })))
      .toEqual({ degrees: 3, published: true });
  });

  it("falls back to a disclosed assumption, flagged as unpublished", () => {
    expect(stationMinimumElevationDeg(station()))
      .toEqual({ degrees: ASSUMED_MINIMUM_ELEVATION_DEG, published: false });
  });
});

describe("passes and dwell", () => {
  const day = { from: WINDOW_START, to: new Date(WINDOW_START.getTime() + 86_400_000) };

  it("finds a plausible day of low-Earth-orbit passes over a mid-latitude station", () => {
    const dwell = computeStationPasses(station(), omm(), { ...day, stepSeconds: 20 });
    expect(dwell.passes.length).toBeGreaterThanOrEqual(3);
    expect(dwell.passes.length).toBeLessThanOrEqual(10);
    for (const pass of dwell.passes) {
      // A 420 km pass cannot last longer than the horizon-to-horizon transit.
      expect(pass.durationSeconds).toBeGreaterThan(60);
      expect(pass.durationSeconds).toBeLessThan(900);
      expect(pass.maximumElevationDeg).toBeGreaterThanOrEqual(dwell.minimumElevationDeg - 1e-6);
      expect(pass.maximumElevationDeg).toBeLessThanOrEqual(90 + 1e-9);
      expect(Date.parse(pass.endAt)).toBeGreaterThan(Date.parse(pass.startAt));
      expect(Date.parse(pass.maximumElevationAt)).toBeGreaterThanOrEqual(Date.parse(pass.startAt));
      expect(Date.parse(pass.maximumElevationAt)).toBeLessThanOrEqual(Date.parse(pass.endAt));
      expect(pass.profile.length).toBeGreaterThan(10);
    }
    // The residency figure Sean asked for: a small percentage of the day.
    expect(dwell.fractionOfWindow).toBeGreaterThan(0);
    expect(dwell.fractionOfWindow).toBeLessThan(0.1);
    expect(dwell.totalSecondsAboveMask)
      .toBeCloseTo(dwell.passes.reduce((sum, pass) => sum + pass.durationSeconds, 0), 6);
    expect(dwell.continuouslyVisible).toBe(false);
    expect(dwell.neverVisible).toBe(false);
  });

  it("brackets acquisition to the second regardless of the coarse step", () => {
    const coarse = computeStationPasses(station(), omm(), { ...day, stepSeconds: 60 });
    const fine = computeStationPasses(station(), omm(), { ...day, stepSeconds: 10 });
    expect(coarse.passes.length).toBe(fine.passes.length);
    coarse.passes.forEach((pass, index) => {
      const other = fine.passes[index]!;
      // Bisection is to one second; allow a couple for the different brackets.
      expect(Math.abs(Date.parse(pass.startAt) - Date.parse(other.startAt))).toBeLessThan(3000);
      expect(Math.abs(Date.parse(pass.endAt) - Date.parse(other.endAt))).toBeLessThan(3000);
      expect(Math.abs(pass.maximumElevationDeg - other.maximumElevationDeg)).toBeLessThan(0.5);
    });
  });

  it("raising the mask shortens the dwell and never lengthens it", () => {
    let previous = Infinity;
    for (const mask of [0, 5, 10, 20, 40]) {
      const dwell = computeStationPasses(station(), omm(), {
        ...day,
        stepSeconds: 20,
        minimumElevationDeg: mask,
      });
      expect(dwell.totalSecondsAboveMask).toBeLessThanOrEqual(previous + 1e-6);
      previous = dwell.totalSecondsAboveMask;
    }
  });

  it("reports a geostationary satellite as continuously above, not as a day-long pass", () => {
    // A near-stationary object; whichever station it is over, it either never
    // sets or never rises. A partial pass would mean the finder is wrong.
    const geo = omm({
      MEAN_MOTION: 1.0027,
      ECCENTRICITY: 0.0002,
      INCLINATION: 0.03,
      RA_OF_ASC_NODE: 95,
      ARG_OF_PERICENTER: 0,
      MEAN_ANOMALY: 200,
      NORAD_CAT_ID: 99002,
    });
    const sites = [
      station({ id: "a", latitudeDeg: 0, longitudeDeg: 0 }),
      station({ id: "b", latitudeDeg: 0, longitudeDeg: 90 }),
      station({ id: "c", latitudeDeg: 0, longitudeDeg: 180 }),
      station({ id: "d", latitudeDeg: 0, longitudeDeg: -90 }),
    ];
    const outcomes = sites.map((site) =>
      computeStationPasses(site, geo, {
        from: WINDOW_START,
        to: new Date(WINDOW_START.getTime() + 6 * 3_600_000),
        stepSeconds: 60,
      }));
    for (const dwell of outcomes) {
      expect(dwell.continuouslyVisible || dwell.neverVisible).toBe(true);
      if (dwell.continuouslyVisible) {
        expect(dwell.passes).toHaveLength(1);
        expect(dwell.passes[0]!.startClamped).toBe(true);
        expect(dwell.passes[0]!.endClamped).toBe(true);
        expect(dwell.fractionOfWindow).toBeCloseTo(1, 6);
      }
    }
    expect(outcomes.some((dwell) => dwell.continuouslyVisible)).toBe(true);
    expect(outcomes.some((dwell) => dwell.neverVisible)).toBe(true);
  });

  it("says never rather than nearly for an equatorial orbit seen from Svalbard", () => {
    const dwell = computeStationPasses(
      station({ id: "svalbard", latitudeDeg: 78.23, longitudeDeg: 15.4 }),
      omm({ INCLINATION: 0.02, MEAN_MOTION: 15.5, NORAD_CAT_ID: 99003 }),
      { ...day, stepSeconds: 60 },
    );
    expect(dwell.neverVisible).toBe(true);
    expect(dwell.passes).toEqual([]);
    expect(dwell.totalSecondsAboveMask).toBe(0);
    expect(dwell.fractionOfWindow).toBe(0);
  });

  it("gives a polar station far more dwell on a polar orbit than an equatorial one", () => {
    // The sun-synchronous downlink argument, as a number: this is why Svalbard
    // and Troll exist.
    const polarOrbit = omm({ INCLINATION: 98.2, MEAN_MOTION: 14.6, NORAD_CAT_ID: 99004 });
    const svalbard = computeStationPasses(
      station({ id: "svalbard", latitudeDeg: 78.23, longitudeDeg: 15.4 }),
      polarOrbit,
      { ...day, stepSeconds: 30 },
    );
    const equatorial = computeStationPasses(
      station({ id: "equator", latitudeDeg: 0.5, longitudeDeg: 15.4 }),
      polarOrbit,
      { ...day, stepSeconds: 30 },
    );
    expect(svalbard.passes.length).toBeGreaterThan(equatorial.passes.length * 2);
    expect(svalbard.totalSecondsAboveMask).toBeGreaterThan(equatorial.totalSecondsAboveMask * 2);
  });

  it("marks a pass already under way at the window edge rather than truncating it silently", () => {
    const full = computeStationPasses(station(), omm(), { ...day, stepSeconds: 20 });
    const first = full.passes[0]!;
    const midPass = new Date((Date.parse(first.startAt) + Date.parse(first.endAt)) / 2);
    const late = computeStationPasses(station(), omm(), {
      from: midPass,
      to: new Date(midPass.getTime() + 3_600_000),
      stepSeconds: 20,
    });
    expect(late.passes[0]!.startClamped).toBe(true);
    expect(late.passes[0]!.startAt).toBe(midPass.toISOString());
  });

  it("refuses a window that does not run forwards", () => {
    expect(() => computeStationPasses(station(), omm(), { from: day.to, to: day.from }))
      .toThrow(/finite start before its end/);
  });

  it("carries its method and its limits with it", () => {
    const dwell = computeStationPasses(station(), omm(), { ...day, stepSeconds: 120 });
    expect(dwell.method).toContain("SGP4");
    expect(dwell.limitation).toContain("not when anyone is talking to it");
    expect(dwell.searchStepSeconds).toBe(120);
  });
});

describe("the published-link index", () => {
  const bundle: GroundStationBundle = {
    schema: 1,
    status: "published-record",
    policy: { militarySites: "excluded", militarySitesRationale: "Pending." },
    attribution: "…",
    limitation: "…",
    stationCount: 2,
    linkCount: 3,
    stations: [station({ id: "alpha" }), station({ id: "beta" })],
    links: [
      { stationId: "alpha", noradId: 43013, satelliteName: "SAT-A", relationship: "data-downlink", relationshipLabel: "…", evidence: "…", source: "https://x/", sourceName: "x", sourceRetrieved: "2026-08-07" },
      { stationId: "beta", noradId: 43013, satelliteName: "SAT-A", relationship: "command-and-control", relationshipLabel: "…", evidence: "…", source: "https://x/", sourceName: "x", sourceRetrieved: "2026-08-07" },
      { stationId: "alpha", noradId: 25544, satelliteName: "SAT-B", relationship: "data-downlink", relationshipLabel: "…", evidence: "…", source: "https://x/", sourceName: "x", sourceRetrieved: "2026-08-07" },
    ],
    linksOutsideCatalog: [],
    relationshipLabels: {
      "command-and-control": "…",
      "data-downlink": "…",
      "tracking-telemetry-command": "…",
      "deep-space-tracking": "…",
    },
  };

  it("answers from the station and from the spacecraft", () => {
    const index = indexGroundStations(bundle);
    expect(index.linksForStation("alpha").map((link) => link.noradId)).toEqual([43013, 25544]);
    expect(index.linksForSatellite(43013).map((link) => link.stationId)).toEqual(["alpha", "beta"]);
    expect(index.stationsForSatellite(43013).map((entry) => entry.station.id)).toEqual(["alpha", "beta"]);
  });

  it("returns nothing rather than a guess for an object with no published link", () => {
    const index = indexGroundStations(bundle);
    expect(index.linksForSatellite(11111)).toEqual([]);
    expect(index.stationsForSatellite(11111)).toEqual([]);
    expect(index.linksForStation("gamma")).toEqual([]);
    expect(index.station("gamma")).toBeNull();
  });
});

describe("the environment over a station", () => {
  const ionosphere: SpaceWeatherBundle["ionosphere"] = {
    observedAt: "2026-08-07T12:00:00Z",
    status: "assimilated",
    gridDegrees: { lon: 10, lat: 10 },
    tecRange: [2, 40],
    medianHmF2Km: 320,
    points: [
      { lon: -80, lat: 40, tec: 18.5, anomaly: 1.1, hmF2: 310, quality: 4 },
      { lon: -70, lat: 40, tec: 22.5, anomaly: 1.3, hmF2: 320, quality: 3 },
      { lon: -80, lat: 30, tec: 30.5, anomaly: 1.4, hmF2: 340, quality: 5 },
      { lon: 100, lat: -20, tec: 44.0, anomaly: 2.0, hmF2: 380, quality: 2 },
    ],
  };

  it("reads the nearest published cell and says how far away it is", () => {
    // Wallops is 4.5 degrees east of the -80 cell and 5.5 west of the -70
    // one, so the -80 cell is the nearer of the two.
    const sample = sampleTecAtStation(ionosphere, station({ latitudeDeg: 37.9, longitudeDeg: -75.5 }))!;
    expect(sample.tecu).toBe(18.5);
    expect(sample.cellLongitudeDeg).toBe(-80);
    expect(sample.cellLatitudeDeg).toBe(40);
    expect(sample.offsetDeg).toBeGreaterThan(0);
    expect(sample.offsetDeg).toBeLessThan(10);
    expect(sample.evidence).toBe("assimilated");
    expect(sample.observedAt).toBe("2026-08-07T12:00:00Z");
    expect(sample.limitation).toContain("column integral");
  });

  it("does not invent a value where the source has none", () => {
    expect(sampleTecAtStation({ ...ionosphere, points: [] }, station())).toBeNull();
    expect(sampleTecAtStation(
      { ...ionosphere, points: [{ lon: 0, lat: 0, tec: null, anomaly: null, hmF2: null, quality: null }] },
      station(),
    )).toBeNull();
  });

  it("reads D-RAP from the exact source cell and the exact source frame", () => {
    // A 4x3 toy grid on D-RAP's own convention: north to south, west to east.
    const values = new Uint16Array([
      0, 0, 0, 0,
      50, 120, 0, 0,
      0, 0, 0, 0,
    ]);
    const bundle = {
      schemaVersion: "noaa-drap.v1",
      grid: {
        longitudeStartDeg: -180,
        longitudeStepDeg: 90,
        longitudeCount: 4,
        latitudeStartDeg: 60,
        latitudeStepDeg: -60,
        latitudeCount: 3,
        order: "latitude-major, north-to-south, west-to-east",
      },
      encoding: { type: "uint16-le-base64", scaleMhz: 0.1, missingValue: 65535 },
      time: { staleAfterMinutes: 30 },
      frames: [{
        validAt: "2026-08-07T11:45:00Z",
        valuesU16: base64OfBytes(new Uint8Array(values.buffer)),
        maximumHafMhz: 12,
        affectedCellPercent: { "3MHz": 1, "10MHz": 0, "30MHz": 0 },
      }],
    } as unknown as DrapBundle;

    const equator = station({ latitudeDeg: 2, longitudeDeg: -178 });
    const sample = sampleDrapAtStation(bundle, equator, new Date("2026-08-07T11:59:00Z"), 8);
    expect("reason" in sample).toBe(false);
    if ("reason" in sample) return;
    expect(sample.highestAffectedFrequencyMhz).toBeCloseTo(5, 6);
    expect(sample.validAt).toBe("2026-08-07T11:45:00Z");
    expect(sample.stale).toBe(false);
    // NOAA's own vertical two-pass scaling, (HAF/f)^1.5.
    expect(sample.absorptionDb).toBeCloseTo((5 / 8) ** 1.5, 9);
    expect(sample.limitation).toContain("never interpolated");
  });

  it("says there is no frame rather than reaching for a later one", () => {
    const bundle = {
      schemaVersion: "noaa-drap.v1",
      grid: { longitudeStartDeg: -180, longitudeStepDeg: 90, longitudeCount: 4, latitudeStartDeg: 60, latitudeStepDeg: -60, latitudeCount: 3, order: "latitude-major, north-to-south, west-to-east" },
      encoding: { type: "uint16-le-base64", scaleMhz: 0.1, missingValue: 65535 },
      time: { staleAfterMinutes: 30 },
      frames: [{ validAt: "2026-08-07T11:45:00Z", valuesU16: "", maximumHafMhz: 0, affectedCellPercent: { "3MHz": 0, "10MHz": 0, "30MHz": 0 } }],
    } as unknown as DrapBundle;
    expect(sampleDrapAtStation(bundle, station(), new Date("2026-08-07T10:00:00Z")))
      .toEqual({ reason: "no-frame-at-time" });
  });

  /**
   * The forward end of the same rule. D-RAP publishes no future frames and the
   * timeline runs 72 h past the last one, so without a ceiling the card printed
   * a three-day-old cell value as a bare "D-RAP HAF 3.5 MHz" with no age on it.
   */
  it("refuses to answer for a station past the end of the nowcast", () => {
    const values = new Uint16Array([50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50]);
    const bundle = {
      schemaVersion: "noaa-drap.v1",
      grid: { longitudeStartDeg: -180, longitudeStepDeg: 90, longitudeCount: 4, latitudeStartDeg: 60, latitudeStepDeg: -60, latitudeCount: 3, order: "latitude-major, north-to-south, west-to-east" },
      encoding: { type: "uint16-le-base64", scaleMhz: 0.1, missingValue: 65535 },
      time: { staleAfterMinutes: 30 },
      frames: [{ validAt: "2026-08-07T11:45:00Z", valuesU16: base64OfBytes(new Uint8Array(values.buffer)), maximumHafMhz: 5, affectedCellPercent: { "3MHz": 100, "10MHz": 0, "30MHz": 0 } }],
    } as unknown as DrapBundle;
    const here = station({ latitudeDeg: 2, longitudeDeg: -178 });
    // Inside the hold window the newest frame still answers, as it must: NOAA's
    // routine publication lag runs well past the staleness threshold.
    expect("reason" in sampleDrapAtStation(bundle, here, new Date("2026-08-07T12:45:00Z"))).toBe(false);
    // Three days past it, there is nothing to say and it says so.
    expect(sampleDrapAtStation(bundle, here, new Date("2026-08-10T11:45:00Z")))
      .toEqual({ reason: "past-nowcast" });
  });
});
