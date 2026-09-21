/**
 * A PARAMETERISED copy of the shared radial ruler, plus the real element sets
 * the geostationary joint was argued over, so a ramp width can be priced
 * without editing `src/radial-ruler.ts`. Pass `rampEndRe = ANCHOR` for the
 * ruler as it was before 2026-08-19, when the joint was a step.
 *
 * Used by `geo-joint-ramp-sweep.ts` and `geo-joint-curvature.ts`; it prints
 * nothing itself.
 */
import * as THREE from "three";

import { EARTH_SCENE_RADIUS, geoToSceneVector } from "../src/globe";
import { propagateOmmInFrozenEarthFrame } from "../src/orbit";
import { RULER_EARTH_RADIUS_KM } from "../src/radial-ruler";
import type { OmmRecord } from "../src/types";

export const ANCHOR = 1 + 35786 / RULER_EARTH_RADIUS_KM;
const TAPER_START = 13;
const TAPER_END = 24;
const TAIL_SLOPE = 0.14;

function logBranch(r: number) {
  return 1 + Math.min(2.05, 0.28 * Math.log1p((Math.max(0, r - 1) * RULER_EARTH_RADIUS_KM) / 350));
}
function logBranchSlope(r: number) {
  if (!(r > 1)) return 0;
  const a = RULER_EARTH_RADIUS_KM / 350;
  return (0.28 * a * r) / ((1 + a * Math.max(0, r - 1)) * logBranch(r));
}
const ANCHOR_SLOPE = logBranchSlope(ANCHOR);

/** Local log-log slope with the joint ramp ending at rampEndRe (== ANCHOR means today's step). */
function slopeAt(r: number, rampEndRe: number) {
  if (!(r > ANCHOR)) return logBranchSlope(r);
  if (r < rampEndRe) {
    const t = Math.log(r / ANCHOR) / Math.log(rampEndRe / ANCHOR);
    return ANCHOR_SLOPE + (1 - ANCHOR_SLOPE) * t;
  }
  if (r <= TAPER_START) return 1;
  if (r >= TAPER_END) return TAIL_SLOPE;
  const t = (Math.log(r) - Math.log(TAPER_START)) / (Math.log(TAPER_END) - Math.log(TAPER_START));
  return 1 - (1 - TAIL_SLOPE) * t * t * (3 - 2 * t);
}

function integralAbove(lnR: number, rampEndRe: number) {
  const lnAnchor = Math.log(ANCHOR);
  const lnRamp = Math.log(rampEndRe);
  const lnTs = Math.log(TAPER_START);
  const lnTe = Math.log(TAPER_END);
  let total = 0;
  if (rampEndRe > ANCHOR) {
    const t = Math.min(1, (lnR - lnAnchor) / (lnRamp - lnAnchor));
    total += (lnRamp - lnAnchor) * (ANCHOR_SLOPE * t + ((1 - ANCHOR_SLOPE) * t * t) / 2);
  }
  const lnFloor = Math.max(lnAnchor, lnRamp);
  if (lnR > lnFloor) total += Math.min(lnR, lnTs) - lnFloor;
  if (lnR > lnTs) {
    const end = Math.min(lnR, lnTe);
    const t = (end - lnTs) / (lnTe - lnTs);
    total += (end - lnTs) - (1 - TAIL_SLOPE) * (lnTe - lnTs) * (t * t * t - (t * t * t * t) / 2);
  }
  if (lnR > lnTe) total += TAIL_SLOPE * (lnR - lnTe);
  return total;
}

export function drawn(r: number, rampEndRe: number, earth = EARTH_SCENE_RADIUS) {
  if (!(r > ANCHOR)) return earth * logBranch(r);
  return earth * logBranch(ANCHOR) * Math.exp(integralAbove(Math.log(r), rampEndRe));
}

export const AT = new Date("2026-08-19T05:46:38Z");

export const OMMS: Record<string, OmmRecord> = {
  "MERIDIAN 9": {
    OBJECT_NAME: "MERIDIAN 9", OBJECT_ID: "2020-015A", EPOCH: "2026-08-18T06:43:06.042720",
    MEAN_MOTION: 2.00613606, ECCENTRICITY: 0.68397671, INCLINATION: 65.5372,
    RA_OF_ASC_NODE: 312.4498, ARG_OF_PERICENTER: 276.8473, MEAN_ANOMALY: 15.9448,
    EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: 45254, ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 4753, BSTAR: 0, MEAN_MOTION_DOT: -0.00000035, MEAN_MOTION_DDOT: 0,
  },
  "THEMIS A": {
    OBJECT_NAME: "THEMIS A", OBJECT_ID: "2007-004A", EPOCH: "2026-08-15T14:05:11.454432",
    MEAN_MOTION: 0.87844134, ECCENTRICITY: 0.83468094, INCLINATION: 9.046,
    RA_OF_ASC_NODE: 104.5165, ARG_OF_PERICENTER: 210.9785, MEAN_ANOMALY: 47.884,
    EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: 30580, ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 4180, BSTAR: 0, MEAN_MOTION_DOT: -0.00000552, MEAN_MOTION_DDOT: 0,
  },
  "CLUSTER II-FM7": {
    OBJECT_NAME: "CLUSTER II-FM7", OBJECT_ID: "2000-041A", EPOCH: "2026-08-16T08:33:20.293632",
    MEAN_MOTION: 0.44877167, ECCENTRICITY: 0.9119992, INCLINATION: 149.5559,
    RA_OF_ASC_NODE: 61.8704, ARG_OF_PERICENTER: 279.7536, MEAN_ANOMALY: 359.6603,
    EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: 26410, ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 2057, BSTAR: 0, MEAN_MOTION_DOT: 0.00204628, MEAN_MOTION_DDOT: -0.0013535,
  },
  XMM: {
    OBJECT_NAME: "XMM", OBJECT_ID: "1999-066A", EPOCH: "2026-08-19T04:18:16.167456",
    MEAN_MOTION: 0.50127221, ECCENTRICITY: 0.46561945, INCLINATION: 64.1488,
    RA_OF_ASC_NODE: 282.1706, ARG_OF_PERICENTER: 63.7746, MEAN_ANOMALY: 0.0533,
    EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: 25989, ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 2331, BSTAR: 0, MEAN_MOTION_DOT: 0.00000056, MEAN_MOTION_DDOT: 0,
  },
  "SIRIUS XM-9": {
    OBJECT_NAME: "GEO CONTROL", OBJECT_ID: "2000-000A", EPOCH: "2026-08-16T01:53:19.462272",
    MEAN_MOTION: 1.00273790, ECCENTRICITY: 0.0001, INCLINATION: 0.6915,
    RA_OF_ASC_NODE: 81.6556, ARG_OF_PERICENTER: 20.4702, MEAN_ANOMALY: 340.2516,
    EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: 64527, ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 420, BSTAR: 0, MEAN_MOTION_DOT: -0.00000269, MEAN_MOTION_DDOT: 0,
  },
};

export function periodMinutes(omm: OmmRecord) { return 1440 / omm.MEAN_MOTION; }
export function apogeeKm(omm: OmmRecord) {
  const a = Math.cbrt((398600.4418 * (86400 / omm.MEAN_MOTION) ** 2) / (4 * Math.PI * Math.PI));
  return a * (1 + omm.ECCENTRICITY) - 6378.137;
}

/** Worst vertex turn at the joint, and worst anywhere else, on the drawn line. */
function measureOrbit(omm: OmmRecord, rampEndRe: number) {
  const position = (s: { latitudeDeg: number; longitudeDeg: number; altitudeKm: number }) =>
    geoToSceneVector(s.latitudeDeg, s.longitudeDeg, drawn(1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM, rampEndRe));
  const reach = drawn(1 + Math.max(0, apogeeKm(omm)) / RULER_EARTH_RADIUS_KM, rampEndRe);
  const path = adaptiveOrbitPath({
    centre: AT,
    spanMinutes: periodMinutes(omm),
    sampleAt: (t: Date) => propagateOmmInFrozenEarthFrame(omm, t, AT, undefined),
    drawnPosition: position,
    toleranceSceneUnits: orbitPathTolerance(reach),
  });
  const vertices = path.map(position);
  const radii = path.map((s) => 1 + Math.max(0, s.altitudeKm) / RULER_EARTH_RADIUS_KM);
  let inBand = 0;
  let outside = 0;
  const bandLow = ANCHOR - 0.35;
  const bandHigh = Math.max(rampEndRe, ANCHOR) + 0.35;
  for (let i = 1; i + 1 < vertices.length; i += 1) {
    const back = vertices[i]!.clone().sub(vertices[i - 1]!);
    const forward = vertices[i + 1]!.clone().sub(vertices[i]!);
    if (back.length() < 1e-9 || forward.length() < 1e-9) continue;
    const cos = Math.max(-1, Math.min(1, back.normalize().dot(forward.normalize())));
    const turn = (Math.acos(cos) * 180) / Math.PI;
    const r = radii[i]!;
    const crosses = (r >= bandLow && r <= bandHigh)
      || (radii[i - 1]! < bandHigh && radii[i + 1]! > bandLow && Math.min(radii[i - 1]!, radii[i + 1]!) < bandHigh
        && Math.max(radii[i - 1]!, radii[i + 1]!) > bandLow);
    if (crosses) inBand = Math.max(inBand, turn);
    else outside = Math.max(outside, turn);
  }
  return { joint: inBand, elsewhere: outside, vertices: vertices.length };
}

