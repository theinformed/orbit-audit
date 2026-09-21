/**
 * Ground stations: where the published antennas are, what they are published
 * as talking to, what the ionosphere is doing over them, and how long a
 * spacecraft actually stays above one.
 *
 * ## What this module does not do
 *
 * It never decides that a station and a spacecraft are related. Every
 * relationship arrives from `data/ground_stations.json` with the citation that
 * makes it, validated in `pipeline/ground_stations.py`. There is no function
 * here that takes a station and a catalog and returns candidate spacecraft,
 * and none may be added: `docs/mission-speculation-design.md` §1.6 excluded
 * object-to-object association, and associating a spacecraft with the antenna
 * that commands it is the same act pointed at the ground.
 *
 * `computeStationPasses` does take a station and an OMM together, but only for
 * a pair the reader has already selected, and it answers "when is this above
 * the horizon", which is geometry every tracking app on earth computes and
 * which asserts nothing about who talks to whom. It is never run across the
 * catalog looking for matches.
 *
 * ## Registration
 *
 * Every position on this overlay goes through `geoToSceneVector` — the same
 * function the satellites, ground tracks, footprints, graticule and terminator
 * use. It is imported, never reimplemented. The globe shipped for months with
 * its raster layers a quarter-turn west of its vector geometry, and the reason
 * that hid is that nothing on screen is labelled with a longitude. A second
 * copy of this arithmetic in this file would be a second place for that to
 * happen, so there isn't one.
 */
import * as THREE from "three";
import { json2satrec, type SatRec } from "satellite.js";
import { EARTH_SCENE_RADIUS, geoToSceneVector } from "./globe";
import { EARTH_RADIUS_KM, footprintAngularRadius, propagateOmm } from "./orbit";
import { sampleEmpiricalDRegion, type DRegionSample } from "./d-region-empirical";
import {
  decodeDrapValues,
  drapAbsorptionDbAtFrequency,
  DRAP_LIVE_EDGE_HOLD_MINUTES,
  selectDrapFrame,
  type DrapBundle,
} from "./drap";
import type { OmmRecord, SpaceWeatherBundle } from "./types";

// ---------------------------------------------------------------------------
// Published record
// ---------------------------------------------------------------------------

export type StationRole =
  | "deep-space-tracking"
  | "command-and-control"
  | "data-downlink"
  | "tracking-telemetry-command"
  | "launch-range-tracking"
  | "amateur-reception";

export type StationOperatorKind =
  | "civil-agency"
  | "scientific"
  | "commercial"
  | "academic"
  | "amateur"
  | "military";

/**
 * How well the published coordinate is known. `privacy-reduced` means the
 * publisher deliberately degraded it — SatNOGS rounds volunteer stations so a
 * home address cannot be read off the map. The interface must say so, and no
 * code may "improve" such a coordinate.
 */
export type StationCoordinatePrecision =
  | "published-survey"
  | "published-approximate"
  | "privacy-reduced";

export type StationRelationship =
  | "command-and-control"
  | "data-downlink"
  | "tracking-telemetry-command"
  | "deep-space-tracking";

export interface GroundStation {
  id: string;
  name: string;
  network: string;
  operator: string;
  operatorKind: StationOperatorKind;
  country: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeM?: number;
  coordinatePrecision: StationCoordinatePrecision;
  roles: StationRole[];
  bands?: string[];
  antennaDiameterM?: number;
  /** Published horizon mask. Absent means the source does not state one. */
  minimumElevationDeg?: number;
  note?: string;
  source: string;
  sourceName: string;
  sourceRetrieved: string;
  licence: string;
}

export interface GroundStationLink {
  stationId: string;
  noradId: number;
  satelliteName: string;
  relationship: StationRelationship;
  relationshipLabel: string;
  /** The published sentence, in the publisher's words. Always shown. */
  evidence: string;
  source: string;
  sourceName: string;
  sourceRetrieved: string;
  note?: string;
}

export interface GroundStationBundle {
  schema: 1;
  status: "published-record";
  policy: { militarySites: "excluded" | "included"; militarySitesRationale: string };
  attribution: string;
  limitation: string;
  stationCount: number;
  linkCount: number;
  stations: GroundStation[];
  links: GroundStationLink[];
  /** Published links whose spacecraft is not in today's capped catalog. */
  linksOutsideCatalog: GroundStationLink[];
  relationshipLabels: Record<StationRelationship, string>;
}

/**
 * Used when a station's source does not publish a horizon mask.
 *
 * Five degrees is a conventional operational floor, not a measurement, and the
 * interface must label it as this site's assumption rather than the operator's
 * figure. Passes are visibly sensitive to it, which is the point.
 */
export const ASSUMED_MINIMUM_ELEVATION_DEG = 5;

export function stationMinimumElevationDeg(station: GroundStation): {
  degrees: number;
  published: boolean;
} {
  return typeof station.minimumElevationDeg === "number"
    ? { degrees: station.minimumElevationDeg, published: true }
    : { degrees: ASSUMED_MINIMUM_ELEVATION_DEG, published: false };
}

// ---------------------------------------------------------------------------
// Indexing the published links, from both directions
// ---------------------------------------------------------------------------

export interface GroundStationIndex {
  bundle: GroundStationBundle;
  station(id: string): GroundStation | null;
  /** Published links naming this station. Never inferred, may be empty. */
  linksForStation(stationId: string): GroundStationLink[];
  /** Published links naming this spacecraft. Never inferred, may be empty. */
  linksForSatellite(noradId: number): GroundStationLink[];
  /** Stations a published link attaches to this spacecraft. */
  stationsForSatellite(noradId: number): Array<{ station: GroundStation; link: GroundStationLink }>;
}

export function indexGroundStations(bundle: GroundStationBundle): GroundStationIndex {
  const stations = new Map(bundle.stations.map((station) => [station.id, station]));
  const byStation = new Map<string, GroundStationLink[]>();
  const bySatellite = new Map<number, GroundStationLink[]>();
  for (const link of bundle.links) {
    if (!byStation.has(link.stationId)) byStation.set(link.stationId, []);
    byStation.get(link.stationId)!.push(link);
    if (!bySatellite.has(link.noradId)) bySatellite.set(link.noradId, []);
    bySatellite.get(link.noradId)!.push(link);
  }
  return {
    bundle,
    station: (id) => stations.get(id) ?? null,
    linksForStation: (id) => byStation.get(id) ?? [],
    linksForSatellite: (noradId) => bySatellite.get(noradId) ?? [],
    stationsForSatellite: (noradId) =>
      (bySatellite.get(noradId) ?? []).flatMap((link) => {
        const station = stations.get(link.stationId);
        return station ? [{ station, link }] : [];
      }),
  };
}

// ---------------------------------------------------------------------------
// Geometry shared with the rest of the globe
// ---------------------------------------------------------------------------

/** Scene radius station pins are drawn at: just clear of the globe's surface. */
export const STATION_SCENE_RADIUS = EARTH_SCENE_RADIUS + 0.55;

/**
 * Where a station is drawn.
 *
 * This delegates to the globe's own transform on purpose. If the scene's
 * convention ever changes, this moves with it instead of quietly disagreeing.
 */
export function stationScenePosition(
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  radius = STATION_SCENE_RADIUS,
): THREE.Vector3 {
  return geoToSceneVector(station.latitudeDeg, station.longitudeDeg, radius);
}

const DEG = Math.PI / 180;

/** Great-circle angle, in radians, between two geographic points. */
export function centralAngleRad(
  fromLatitudeDeg: number,
  fromLongitudeDeg: number,
  toLatitudeDeg: number,
  toLongitudeDeg: number,
): number {
  const lat1 = fromLatitudeDeg * DEG;
  const lat2 = toLatitudeDeg * DEG;
  const deltaLon = (toLongitudeDeg - fromLongitudeDeg) * DEG;
  const cosine = Math.sin(lat1) * Math.sin(lat2)
    + Math.cos(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  return Math.acos(Math.min(1, Math.max(-1, cosine)));
}

/**
 * Elevation, in degrees, of a spacecraft above a station's local horizon.
 *
 * Spherical Earth at `EARTH_RADIUS_KM`, which is the exact inverse of
 * `footprintAngularRadius` in `orbit.ts`: at elevation E the horizon ring is at
 * central angle `acos((Re/r) cos E) - E`, and this solves the same relation the
 * other way. Sharing the assumption is deliberate — the coverage cap drawn on
 * the globe and the pass list in the panel must agree, and a second Earth model
 * here would make them disagree by a few seconds at every acquisition.
 *
 * It is not a refraction-corrected, terrain-masked or antenna-limited
 * elevation, and the interface must not present it as one.
 */
export function elevationDeg(
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  subLatitudeDeg: number,
  subLongitudeDeg: number,
  altitudeKm: number,
): number {
  const gamma = centralAngleRad(
    station.latitudeDeg,
    station.longitudeDeg,
    subLatitudeDeg,
    subLongitudeDeg,
  );
  const radius = EARTH_RADIUS_KM + Math.max(0, altitudeKm);
  const sine = Math.sin(gamma);
  if (sine < 1e-12) return 90;
  return Math.atan2(Math.cos(gamma) - EARTH_RADIUS_KM / radius, sine) / DEG;
}

/** Slant range, in km, on the same spherical assumption as `elevationDeg`. */
export function slantRangeKm(
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  subLatitudeDeg: number,
  subLongitudeDeg: number,
  altitudeKm: number,
): number {
  const gamma = centralAngleRad(
    station.latitudeDeg,
    station.longitudeDeg,
    subLatitudeDeg,
    subLongitudeDeg,
  );
  const radius = EARTH_RADIUS_KM + Math.max(0, altitudeKm);
  return Math.sqrt(
    EARTH_RADIUS_KM * EARTH_RADIUS_KM + radius * radius
      - 2 * EARTH_RADIUS_KM * radius * Math.cos(gamma),
  );
}

/**
 * The ring of sub-satellite points from which a spacecraft at this altitude is
 * above the station's mask — the coverage footprint read backwards.
 *
 * Reuses `footprintAngularRadius`, so this ring and the selected satellite's
 * coverage cap are the same geometry seen from the two ends of the link. That
 * is the teaching point: they touch exactly at acquisition of signal.
 */
export function stationVisibilityRing(
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  altitudeKm: number,
  minimumElevationDeg: number,
  segments = 128,
): Array<[number, number]> {
  const angularRadius = footprintAngularRadius(altitudeKm, minimumElevationDeg);
  const lat1 = station.latitudeDeg * DEG;
  const lon1 = station.longitudeDeg * DEG;
  const points: Array<[number, number]> = [];
  for (let index = 0; index <= segments; index += 1) {
    const bearing = (index / segments) * Math.PI * 2;
    const latitude = Math.asin(
      Math.sin(lat1) * Math.cos(angularRadius)
        + Math.cos(lat1) * Math.sin(angularRadius) * Math.cos(bearing),
    );
    const longitude = lon1
      + Math.atan2(
        Math.sin(bearing) * Math.sin(angularRadius) * Math.cos(lat1),
        Math.cos(angularRadius) - Math.sin(lat1) * Math.sin(latitude),
      );
    points.push([longitude / DEG, latitude / DEG]);
  }
  return points;
}

// ---------------------------------------------------------------------------
// Passes and dwell
// ---------------------------------------------------------------------------

export interface StationPassSample {
  at: string;
  elevationDeg: number;
  azimuthDeg: number;
  rangeKm: number;
}

export interface StationPass {
  /** Acquisition of signal at the mask. Clamped to the window start if the pass was already in progress. */
  startAt: string;
  endAt: string;
  durationSeconds: number;
  maximumElevationDeg: number;
  maximumElevationAt: string;
  minimumRangeKm: number;
  /** The pass was already under way when the window opened. */
  startClamped: boolean;
  /** The pass had not ended when the window closed. */
  endClamped: boolean;
  profile: StationPassSample[];
}

export interface StationDwell {
  stationId: string;
  noradId: number;
  windowStart: string;
  windowEnd: string;
  minimumElevationDeg: number;
  minimumElevationIsPublished: boolean;
  passes: StationPass[];
  /** Total time above the mask in the window. */
  totalSecondsAboveMask: number;
  /** That time as a fraction of the window — the residency figure. */
  fractionOfWindow: number;
  longestPassSeconds: number;
  /**
   * The spacecraft never dropped below the mask inside the window. A
   * geostationary satellite over a station's meridian looks like this, and the
   * interface must say "continuously above" rather than quoting a pass length
   * that is really just the length of the window.
   */
  continuouslyVisible: boolean;
  /** No sample in the window reached the mask. */
  neverVisible: boolean;
  /** Coarse search step actually used, so the resolution is disclosable. */
  searchStepSeconds: number;
  method: string;
  limitation: string;
}

export interface StationPassOptions {
  from: Date;
  to: Date;
  minimumElevationDeg?: number;
  /** Coarse scan step. Refinement bisects to one second regardless. */
  stepSeconds?: number;
  /** Samples across each pass's elevation profile. */
  profileSamples?: number;
  satrec?: SatRec;
}

const PASS_METHOD = "SGP4 through satellite.js at the published mean elements, sampled on a coarse "
  + "step and bisected to one second at each mask crossing. Elevation is geometric on a spherical "
  + "Earth, the same assumption as the coverage footprint drawn on the globe.";

const PASS_LIMITATION = "Geometric visibility only. It is not corrected for refraction, terrain, "
  + "local obstructions, antenna pattern, keyhole limits, scheduling or link budget, and public "
  + "mean elements degrade away from their epoch. It says when the spacecraft is above the horizon, "
  + "not when anyone is talking to it.";

function isoOf(ms: number): string {
  return new Date(Math.round(ms)).toISOString();
}

interface Look {
  elevationDeg: number;
  azimuthDeg: number;
  rangeKm: number;
}

/**
 * Azimuth, in degrees clockwise from north, of the sub-satellite point seen
 * from the station. Shown on the pass card so a reader can point at the sky.
 */
function azimuthDeg(
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  subLatitudeDeg: number,
  subLongitudeDeg: number,
): number {
  const lat1 = station.latitudeDeg * DEG;
  const lat2 = subLatitudeDeg * DEG;
  const deltaLon = (subLongitudeDeg - station.longitudeDeg) * DEG;
  const bearing = Math.atan2(
    Math.sin(deltaLon) * Math.cos(lat2),
    Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon),
  ) / DEG;
  return (bearing + 360) % 360;
}

/**
 * Compute passes and dwell for one station and one spacecraft over a window.
 *
 * Reuses `propagateOmm` from `orbit.ts` rather than adding a second
 * propagator, and reuses the elevation relation that `footprintAngularRadius`
 * already encodes. There is no new orbital mechanics in this function.
 */
export function computeStationPasses(
  station: GroundStation,
  omm: OmmRecord,
  options: StationPassOptions,
): StationDwell {
  const startMs = options.from.getTime();
  const endMs = options.to.getTime();
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) {
    throw new RangeError("A pass window needs a finite start before its end");
  }
  const mask = stationMinimumElevationDeg(station);
  const minimumElevation = options.minimumElevationDeg ?? mask.degrees;
  const step = Math.max(1, options.stepSeconds ?? 30) * 1000;
  const profileSamples = Math.max(4, options.profileSamples ?? 48);
  const satrec = options.satrec ?? json2satrec(omm);

  const look = (ms: number): Look | null => {
    const state = propagateOmm(omm, new Date(ms), satrec);
    if (!state) return null;
    return {
      elevationDeg: elevationDeg(station, state.latitudeDeg, state.longitudeDeg, state.altitudeKm),
      azimuthDeg: azimuthDeg(station, state.latitudeDeg, state.longitudeDeg),
      rangeKm: slantRangeKm(station, state.latitudeDeg, state.longitudeDeg, state.altitudeKm),
    };
  };

  /**
   * Bisect a mask crossing to one second, given a time below the mask and a
   * time above it.
   *
   * `below` is earlier than `above` at acquisition and later at loss, so the
   * bracket is not ordered in time and the width has to be taken as an
   * absolute value. Getting that wrong is silent: the loop simply never runs
   * and every loss of signal is reported at the previous coarse sample, which
   * looks like a working pass list whose end times move when you change the
   * step. It did exactly that before this comment existed.
   */
  const crossing = (belowMs: number, aboveMs: number): number => {
    let low = belowMs;
    let high = aboveMs;
    for (let iteration = 0; iteration < 40 && Math.abs(high - low) > 1000; iteration += 1) {
      const middle = (low + high) / 2;
      const sample = look(middle);
      // A propagation failure inside the bracket cannot be resolved by
      // guessing; keep the conservative edge rather than inventing a time.
      if (!sample) return high;
      if (sample.elevationDeg >= minimumElevation) high = middle;
      else low = middle;
    }
    return high;
  };

  const passes: StationPass[] = [];
  let openedAtMs: number | null = null;
  let openedClamped = false;
  let anySample = false;
  let anyAbove = false;
  let anyBelow = false;

  let previousMs = startMs;
  let previousLook = look(startMs);
  if (previousLook) {
    anySample = true;
    if (previousLook.elevationDeg >= minimumElevation) {
      anyAbove = true;
      openedAtMs = startMs;
      openedClamped = true;
    } else {
      anyBelow = true;
    }
  }

  const closePass = (endAtMs: number, endClamped: boolean) => {
    if (openedAtMs === null) return;
    const from = openedAtMs;
    const to = endAtMs;
    const profile: StationPassSample[] = [];
    let maximumElevation = -90;
    let maximumAtMs = from;
    let minimumRange = Infinity;
    for (let index = 0; index <= profileSamples; index += 1) {
      const at = from + ((to - from) * index) / profileSamples;
      const sample = look(at);
      if (!sample) continue;
      profile.push({
        at: isoOf(at),
        elevationDeg: sample.elevationDeg,
        azimuthDeg: sample.azimuthDeg,
        rangeKm: sample.rangeKm,
      });
      if (sample.elevationDeg > maximumElevation) {
        maximumElevation = sample.elevationDeg;
        maximumAtMs = at;
      }
      minimumRange = Math.min(minimumRange, sample.rangeKm);
    }
    // Refine the culmination by ternary search over the sample spacing, so a
    // short high pass does not report the elevation of a coarse sample.
    const spacing = (to - from) / profileSamples;
    let low = Math.max(from, maximumAtMs - spacing);
    let high = Math.min(to, maximumAtMs + spacing);
    for (let iteration = 0; iteration < 32 && high - low > 500; iteration += 1) {
      const first = low + (high - low) / 3;
      const second = high - (high - low) / 3;
      const firstLook = look(first);
      const secondLook = look(second);
      if (!firstLook || !secondLook) break;
      if (firstLook.elevationDeg < secondLook.elevationDeg) low = first;
      else high = second;
    }
    const peak = look((low + high) / 2);
    if (peak && peak.elevationDeg > maximumElevation) {
      maximumElevation = peak.elevationDeg;
      maximumAtMs = (low + high) / 2;
      minimumRange = Math.min(minimumRange, peak.rangeKm);
    }
    passes.push({
      startAt: isoOf(from),
      endAt: isoOf(to),
      durationSeconds: (to - from) / 1000,
      maximumElevationDeg: maximumElevation,
      maximumElevationAt: isoOf(maximumAtMs),
      minimumRangeKm: Number.isFinite(minimumRange) ? minimumRange : Number.NaN,
      startClamped: openedClamped,
      endClamped,
      profile,
    });
    openedAtMs = null;
    openedClamped = false;
  };

  for (let ms = startMs + step; ms <= endMs; ms += step) {
    const at = Math.min(ms, endMs);
    const current = look(at);
    if (!current) {
      previousMs = at;
      continue;
    }
    anySample = true;
    const above = current.elevationDeg >= minimumElevation;
    if (above) anyAbove = true;
    else anyBelow = true;
    const wasAbove = openedAtMs !== null;
    if (above && !wasAbove) {
      openedAtMs = previousLook ? crossing(previousMs, at) : at;
      openedClamped = false;
    } else if (!above && wasAbove) {
      closePass(crossing(at, previousMs), false);
    }
    previousMs = at;
    previousLook = current;
  }
  if (openedAtMs !== null) closePass(endMs, true);

  const totalSeconds = passes.reduce((sum, pass) => sum + pass.durationSeconds, 0);
  const windowSeconds = (endMs - startMs) / 1000;
  return {
    stationId: station.id,
    noradId: Number(omm.NORAD_CAT_ID),
    windowStart: isoOf(startMs),
    windowEnd: isoOf(endMs),
    minimumElevationDeg: minimumElevation,
    minimumElevationIsPublished: options.minimumElevationDeg === undefined && mask.published,
    passes,
    totalSecondsAboveMask: totalSeconds,
    fractionOfWindow: windowSeconds > 0 ? totalSeconds / windowSeconds : 0,
    longestPassSeconds: passes.reduce((best, pass) => Math.max(best, pass.durationSeconds), 0),
    continuouslyVisible: anySample && anyAbove && !anyBelow,
    neverVisible: anySample && !anyAbove,
    searchStepSeconds: step / 1000,
    method: PASS_METHOD,
    limitation: PASS_LIMITATION,
  };
}

// ---------------------------------------------------------------------------
// Space weather over the station
// ---------------------------------------------------------------------------

export interface StationTecSample {
  tecu: number;
  /** Centre of the published GloTEC cell actually read. */
  cellLatitudeDeg: number;
  cellLongitudeDeg: number;
  /** How far the cell centre is from the station, in degrees of great circle. */
  offsetDeg: number;
  hmF2Km: number | null;
  quality: number | null;
  observedAt: string;
  evidence: "assimilated";
  limitation: string;
}

const TEC_LIMITATION = "GloTEC vertical total electron content in the published cell containing the "
  + "station, read without interpolation. It is a column integral: it sets the ionospheric group "
  + "delay a GNSS or downlink signal accumulates on a vertical path, and it cannot tell you the "
  + "peak height, the D-region, or HF absorption.";

/**
 * Nearest published GloTEC cell to a station.
 *
 * Deliberately nearest-cell rather than interpolated. The reader is being shown
 * "the ionosphere over this antenna", and a value that exists in the source at
 * a stated location is a more honest answer than a smooth number that exists
 * nowhere. The offset is reported so the approximation is visible.
 */
export function sampleTecAtStation(
  ionosphere: SpaceWeatherBundle["ionosphere"],
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
): StationTecSample | null {
  let best: SpaceWeatherBundle["ionosphere"]["points"][number] | null = null;
  let bestAngle = Infinity;
  for (const point of ionosphere.points) {
    if (point.tec === null || !Number.isFinite(point.tec)) continue;
    const angle = centralAngleRad(station.latitudeDeg, station.longitudeDeg, point.lat, point.lon);
    if (angle >= bestAngle) continue;
    bestAngle = angle;
    best = point;
  }
  if (!best || best.tec === null) return null;
  return {
    tecu: best.tec,
    cellLatitudeDeg: best.lat,
    cellLongitudeDeg: best.lon,
    offsetDeg: bestAngle / DEG,
    hmF2Km: best.hmF2,
    quality: best.quality,
    observedAt: ionosphere.observedAt,
    evidence: "assimilated",
    limitation: TEC_LIMITATION,
  };
}

export interface StationDrapSample {
  highestAffectedFrequencyMhz: number;
  /** Absorption at the frequency the reader chose, on NOAA's vertical two-pass scaling. */
  absorptionDb: number | null;
  frequencyMhz: number | null;
  cellLatitudeDeg: number;
  cellLongitudeDeg: number;
  validAt: string;
  ageMinutes: number;
  stale: boolean;
  evidence: "model";
  limitation: string;
}

export type StationDrapUnavailable = {
  /**
   * `past-nowcast` is the same missing state the layer itself grew on
   * 2026-08-27: D-RAP publishes no future frames, and the slider runs 72 h
   * forward, so without it this returned the newest frame's cell value as a
   * bare number for a station three days from now. The card prints that as
   * "D-RAP HAF 3.5 MHz" with no age on it, which is the strongest possible
   * claim about the weakest possible evidence.
   */
  reason: "no-frame-at-time" | "outside-grid" | "missing-cell" | "past-nowcast";
};

const DRAP_LIMITATION = "NOAA D-RAP 1 dB Highest Affected Frequency in the source cell containing "
  + "the station, at the exact frame at or before the selected time; D-RAP frames are never "
  + "interpolated. It is model guidance for a vertical ground-ionosphere-ground path, not this "
  + "station's link budget and not an outage report.";

/**
 * D-RAP over a station, from the exact source cell and the exact source frame.
 *
 * No spatial or temporal interpolation: the D-RAP contract in
 * `docs/SCIENTIFIC-LAYERS.md` forbids interpolating through time, and a station
 * is a point, so the honest answer is the cell it stands in.
 */
export function sampleDrapAtStation(
  bundle: DrapBundle,
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  at: Date,
  frequencyMhz: number | null = null,
): StationDrapSample | StationDrapUnavailable {
  const selection = selectDrapFrame(bundle, at);
  if (!selection) return { reason: "no-frame-at-time" };
  const newest = bundle.frames.at(-1);
  const pastRecord = newest !== undefined && at.getTime() > Date.parse(newest.validAt);
  if (pastRecord && selection.ageMinutes > DRAP_LIVE_EDGE_HOLD_MINUTES) return { reason: "past-nowcast" };
  const { grid } = bundle;
  // The grid is latitude-major, north to south, west to east.
  const longitude = ((station.longitudeDeg - grid.longitudeStartDeg) % 360 + 360) % 360;
  const column = Math.round(longitude / grid.longitudeStepDeg);
  const row = Math.round((station.latitudeDeg - grid.latitudeStartDeg) / grid.latitudeStepDeg);
  if (row < 0 || row >= grid.latitudeCount) return { reason: "outside-grid" };
  const wrappedColumn = ((column % grid.longitudeCount) + grid.longitudeCount) % grid.longitudeCount;
  const values = decodeDrapValues(bundle, selection.frame);
  const value = values[row * grid.longitudeCount + wrappedColumn];
  if (value === undefined || !Number.isFinite(value)) return { reason: "missing-cell" };
  return {
    highestAffectedFrequencyMhz: value,
    absorptionDb: frequencyMhz === null ? null : drapAbsorptionDbAtFrequency(value, frequencyMhz),
    frequencyMhz,
    cellLatitudeDeg: grid.latitudeStartDeg + row * grid.latitudeStepDeg,
    cellLongitudeDeg: ((grid.longitudeStartDeg + wrappedColumn * grid.longitudeStepDeg + 180) % 360 + 360) % 360 - 180,
    validAt: selection.frame.validAt,
    ageMinutes: selection.ageMinutes,
    stale: selection.stale,
    evidence: "model",
    limitation: DRAP_LIMITATION,
  };
}

export interface StationDRegionSample extends DRegionSample {
  limitation: string;
}

const D_REGION_LIMITATION = "Wait-Spies effective VLF reflection height and electron density at "
  + "74 km over the station, recomputed from the selected UTC, the local solar zenith angle and the "
  + "sampled GOES long-channel X-ray flux. It is an empirical teaching relationship inside its "
  + "published domain, not a chemistry model and not a measurement over this antenna.";

/** The empirical lower-D response directly over a station. */
export function sampleDRegionAtStation(
  station: Pick<GroundStation, "latitudeDeg" | "longitudeDeg">,
  at: Date,
  xrayFluxWm2: number | null,
): StationDRegionSample {
  return {
    ...sampleEmpiricalDRegion(station.latitudeDeg, station.longitudeDeg, at, xrayFluxWm2),
    limitation: D_REGION_LIMITATION,
  };
}

// ---------------------------------------------------------------------------
// The overlay
// ---------------------------------------------------------------------------

const OPERATOR_COLORS: Record<StationOperatorKind, number> = {
  "civil-agency": 0x76e6a5,
  scientific: 0x29d4e3,
  commercial: 0xf5c96a,
  academic: 0xa98cff,
  amateur: 0xb9c9d3,
  military: 0xff7b78,
};

export function stationColor(kind: StationOperatorKind): number {
  return OPERATOR_COLORS[kind] ?? OPERATOR_COLORS.amateur;
}

/**
 * The legend entry for the pins, derived from OPERATOR_COLORS itself so the
 * ramp can never drift from what is drawn. Pin colour is a real categorical
 * variable -- who operates the antenna -- and a legend that admitted no scale
 * fell through to the "SHAPE ONLY" bar, which told a reader the layer carried
 * no information. It carries exactly this much.
 */
export const STATION_OPERATOR_SCALE = {
  gradient: (() => {
    const entries = Object.entries(OPERATOR_COLORS);
    const step = 100 / entries.length;
    return `linear-gradient(90deg, ${entries.map(([, hex], index) =>
      `#${hex.toString(16).padStart(6, "0")} ${(index * step).toFixed(1)}% ${((index + 1) * step).toFixed(1)}%`).join(", ")})`;
  })(),
  minimum: "CIVIL",
  label: "OPERATOR CATEGORY \u00b7 CIVIL / SCI / COMM / ACAD / AMAT / MIL",
  maximum: "MIL",
} as const;

/** A square pin, so a station never reads as one of the round satellite dots. */
function pinTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  if (context) {
    context.translate(32, 32);
    context.rotate(Math.PI / 4);
    context.fillStyle = "rgba(255,255,255,0.95)";
    context.fillRect(-15, -15, 30, 30);
    context.globalCompositeOperation = "destination-out";
    context.fillRect(-9, -9, 18, 18);
    context.globalCompositeOperation = "source-over";
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export interface GroundStationLayerOptions {
  stations: GroundStation[];
  /** Marker size in pixels at the default interface scale. */
  markerSizePx?: number;
}

/**
 * The station pins, as one points buffer added to the globe's Earth-fixed
 * group. Positions come from `stationScenePosition`, which is the globe's own
 * transform; this class contains no coordinate arithmetic of its own.
 */
export class GroundStationLayer {
  readonly group = new THREE.Group();
  readonly stations: GroundStation[];
  private readonly points: THREE.Points;
  private readonly material: THREE.PointsMaterial;
  private readonly ringGroup = new THREE.Group();
  private readonly positions: THREE.Vector3[];

  constructor({ stations, markerSizePx = 9 }: GroundStationLayerOptions) {
    this.stations = stations;
    this.positions = stations.map((station) => stationScenePosition(station));
    const positions = new Float32Array(stations.length * 3);
    const colors = new Float32Array(stations.length * 3);
    const color = new THREE.Color();
    this.positions.forEach((vector, index) => {
      positions[index * 3] = vector.x;
      positions[index * 3 + 1] = vector.y;
      positions[index * 3 + 2] = vector.z;
      color.setHex(stationColor(stations[index]!.operatorKind));
      colors[index * 3] = color.r;
      colors[index * 3 + 1] = color.g;
      colors[index * 3 + 2] = color.b;
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    this.material = new THREE.PointsMaterial({
      size: markerSizePx,
      sizeAttenuation: false,
      map: pinTexture(),
      transparent: true,
      depthWrite: false,
      vertexColors: true,
    });
    this.points = new THREE.Points(geometry, this.material);
    this.points.renderOrder = 3;
    this.group.add(this.points);
    this.group.add(this.ringGroup);
    this.group.visible = false;
  }

  setVisible(visible: boolean) {
    this.group.visible = visible;
  }

  setMarkerSize(pixels: number) {
    this.material.size = pixels;
  }

  scenePosition(index: number): THREE.Vector3 | null {
    return this.positions[index]?.clone() ?? null;
  }

  /**
   * Draw the locus of sub-satellite points from which the chosen spacecraft
   * clears this station's mask. Pass `null` to clear it.
   */
  showVisibilityRing(
    stationIndex: number | null,
    altitudeKm: number,
    minimumElevationDeg: number,
  ) {
    this.disposeRing();
    if (stationIndex === null) return;
    const station = this.stations[stationIndex];
    if (!station) return;
    const ring = stationVisibilityRing(station, altitudeKm, minimumElevationDeg);
    const vectors = ring.map(([longitude, latitude]) =>
      geoToSceneVector(latitude, longitude, EARTH_SCENE_RADIUS + 0.35),
    );
    const geometry = new THREE.BufferGeometry().setFromPoints(vectors);
    const material = new THREE.LineBasicMaterial({
      color: stationColor(station.operatorKind),
      transparent: true,
      opacity: 0.65,
    });
    this.ringGroup.add(new THREE.Line(geometry, material));
  }

  /**
   * Nearest station within `radiusPx` of a screen point, skipping any pin on
   * the far side of the globe. Same screen-space approach as the satellite
   * picker, and generous for the same reason.
   */
  pick(
    x: number,
    y: number,
    camera: THREE.Camera,
    width: number,
    height: number,
    radiusPx = 14,
  ): number | null {
    if (!this.group.visible) return null;
    const cameraPosition = camera.getWorldPosition(new THREE.Vector3());
    const projected = new THREE.Vector3();
    let best: number | null = null;
    let bestDistance = radiusPx;
    this.positions.forEach((position, index) => {
      // Behind the horizon: the globe is between the camera and the pin.
      if (position.clone().normalize().dot(cameraPosition.clone().sub(position).normalize()) <= 0) return;
      projected.copy(position).project(camera);
      if (projected.z > 1) return;
      const screenX = ((projected.x + 1) / 2) * width;
      const screenY = ((1 - projected.y) / 2) * height;
      const distance = Math.hypot(screenX - x, screenY - y);
      if (distance >= bestDistance) return;
      bestDistance = distance;
      best = index;
    });
    return best;
  }

  /**
   * Drop the ring's GPU resources before clearing the group.
   *
   * `Group.clear()` only detaches children; it does not free their geometry or
   * material. The ring is rebuilt on every selection change and on every step
   * of the timeline, so detaching without disposing leaks a buffer per redraw.
   */
  private disposeRing() {
    for (const child of this.ringGroup.children) {
      if (!(child instanceof THREE.Line)) continue;
      child.geometry.dispose();
      (child.material as THREE.Material).dispose();
    }
    this.ringGroup.clear();
  }

  dispose() {
    this.points.geometry.dispose();
    this.material.map?.dispose();
    this.material.dispose();
    this.disposeRing();
    this.group.clear();
  }
}
