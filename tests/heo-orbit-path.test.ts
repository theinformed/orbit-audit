import * as THREE from "three";
import { describe, expect, it } from "vitest";

import { geoToSceneVector, satelliteDisplayRadius } from "../src/globe";
import { propagateOmmInFrozenEarthFrame } from "../src/orbit";
import { adaptiveOrbitPath, orbitPathTolerance } from "../src/orbit-polyline";
import { RADIAL_RULER, RULER_EARTH_RADIUS_KM } from "../src/radial-ruler";
import type { OmmRecord } from "../src/types";

/**
 * The selected spacecraft's drawn orbit, end to end, on the orbits that broke.
 *
 * Sean's report was "the site cannot draw most HEO orbits. It draws part of one
 * or has weird kinks in the lines." Both halves are pinned here from real
 * element sets rather than from a synthetic ellipse, because both causes were
 * things a synthetic ellipse would have hidden:
 *
 *  - "part of one" was a fixed 24-hour cap on the drawn span, applied to an
 *    orbit that takes 53.5 hours to close. CLUSTER II-FM7 drew 44.9% of its
 *    orbit and stopped in empty space 407 scene units from where it started.
 *  - "weird kinks" was 180 samples spaced evenly in TIME, which on MERIDIAN 9
 *    left an 18x spread of drawn segment lengths and a 10.9 degree turn at one
 *    vertex near perigee.
 *
 * The element sets are the live CelesTrak OMMs for those objects as the
 * catalogue carried them on 2026-08-18, copied here so the guard does not
 * depend on a released artifact that is refreshed daily.
 *
 * The catalogue holds no INCLINED Tundra today — COSMOS 2590 is the only
 * object it carries at a Tundra period with real eccentricity, and it is
 * near-equatorial — so that case is covered for its period and eccentricity
 * only, and the inclined-crossing geometry is covered by MERIDIAN 9 and
 * CLUSTER II-FM7 instead. Inventing a plausible inclined Tundra element set
 * would test arithmetic against itself.
 */

const molniya: OmmRecord = {
  OBJECT_NAME: "MERIDIAN 9",
  OBJECT_ID: "2020-015A",
  EPOCH: "2026-08-18T06:43:06.043584",
  MEAN_MOTION: 2.00613619,
  ECCENTRICITY: 0.68397599,
  INCLINATION: 65.5383,
  RA_OF_ASC_NODE: 312.4508,
  ARG_OF_PERICENTER: 276.8462,
  MEAN_ANOMALY: 15.9451,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 45254,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 4753,
  BSTAR: 0,
  MEAN_MOTION_DOT: -0.00000035,
  MEAN_MOTION_DDOT: 0,
};

const tundraPeriod: OmmRecord = {
  OBJECT_NAME: "COSMOS 2590",
  OBJECT_ID: "2025-131D",
  EPOCH: "2026-08-16T01:53:19.462272",
  MEAN_MOTION: 1.00218406,
  ECCENTRICITY: 0.3643925,
  INCLINATION: 0.6915,
  RA_OF_ASC_NODE: 81.6556,
  ARG_OF_PERICENTER: 20.4702,
  MEAN_ANOMALY: 340.2516,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 64527,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 420,
  BSTAR: 0,
  MEAN_MOTION_DOT: -0.00000269,
  MEAN_MOTION_DDOT: 0,
};

/** The object Sean photographed: 53.5 hours, so the 24-hour cap cut it in half. */
const deepScienceOrbit: OmmRecord = {
  OBJECT_NAME: "CLUSTER II-FM7",
  OBJECT_ID: "2000-041A",
  EPOCH: "2026-08-16T08:33:20.293632",
  MEAN_MOTION: 0.44877167,
  ECCENTRICITY: 0.9119992,
  INCLINATION: 149.5559,
  RA_OF_ASC_NODE: 61.8704,
  ARG_OF_PERICENTER: 279.7536,
  MEAN_ANOMALY: 359.6603,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 26410,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 2057,
  BSTAR: 0,
  MEAN_MOTION_DOT: 0.00204628,
  MEAN_MOTION_DDOT: -0.0013535,
};

/**
 * The object Sean photographed the ruler's corner on: a V-shaped cusp on the
 * right-hand side, about a third of the way out from the globe, at the drawn
 * radius of geostationary orbit. Its eccentricity is what makes it the worst
 * case — it crosses that shell closest to radially, and refraction goes as
 * tan(psi).
 */
const photographedCusp: OmmRecord = {
  OBJECT_NAME: "THEMIS A",
  OBJECT_ID: "2007-004A",
  EPOCH: "2026-08-15T14:05:11.454432",
  MEAN_MOTION: 0.87844134,
  ECCENTRICITY: 0.83468094,
  INCLINATION: 9.046,
  RA_OF_ASC_NODE: 104.5165,
  ARG_OF_PERICENTER: 210.9785,
  MEAN_ANOMALY: 47.884,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 30580,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 4180,
  BSTAR: 0,
  MEAN_MOTION_DOT: -0.00000552,
  MEAN_MOTION_DDOT: 0,
};

/** The control: whatever fixes the ellipse must not cost the circle anything. */
const lowEarthOrbit: OmmRecord = {
  OBJECT_NAME: "ISS (ZARYA)",
  OBJECT_ID: "1998-067A",
  EPOCH: "2026-08-18T19:47:11.368896",
  MEAN_MOTION: 15.49494626,
  ECCENTRICITY: 0.0007621,
  INCLINATION: 51.6332,
  RA_OF_ASC_NODE: 350.0835,
  ARG_OF_PERICENTER: 60.8158,
  MEAN_ANOMALY: 299.3593,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 25544,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 58146,
  BSTAR: 0.00015811966,
  MEAN_MOTION_DOT: 0.00008426,
  MEAN_MOTION_DDOT: 0,
};

const AT = new Date("2026-08-19T05:46:38Z");

function periodMinutes(omm: OmmRecord) {
  return 1440 / omm.MEAN_MOTION;
}

function apogeeKm(omm: OmmRecord) {
  const semiMajorKm = Math.cbrt(
    (398600.4418 * (86400 / omm.MEAN_MOTION) ** 2) / (4 * Math.PI * Math.PI),
  );
  return semiMajorKm * (1 + omm.ECCENTRICITY) - 6378.137;
}

function drawnPositionOf(state: { latitudeDeg: number; longitudeDeg: number; altitudeKm: number }) {
  return geoToSceneVector(
    state.latitudeDeg,
    state.longitudeDeg,
    satelliteDisplayRadius(state.altitudeKm),
  );
}

/**
 * Exactly what `SpaceExplorer.refreshSelectedGeometry` builds for the orbit
 * line, plus the instant each vertex came from. The times are recovered by
 * remembering them as the propagator is called rather than by adding them to
 * the sampler's result, so the guard measures the same objects the site draws.
 */
function drawnOrbit(omm: OmmRecord) {
  const reach = satelliteDisplayRadius(Math.max(0, apogeeKm(omm)));
  const timeOf = new Map<object, number>();
  const propagate = (sampleTime: Date) => {
    const state = propagateOmmInFrozenEarthFrame(omm, sampleTime, AT, undefined);
    if (state) timeOf.set(state, sampleTime.getTime());
    return state;
  };
  const path = adaptiveOrbitPath({
    centre: AT,
    spanMinutes: periodMinutes(omm),
    sampleAt: propagate,
    drawnPosition: drawnPositionOf,
    toleranceSceneUnits: orbitPathTolerance(reach),
  });
  return {
    reach,
    tolerance: orbitPathTolerance(reach),
    altitudesKm: path.map((state) => state.altitudeKm),
    timesMs: path.map((state) => timeOf.get(state) ?? Number.NaN),
    vertices: path.map(drawnPositionOf),
    propagate,
  };
}

/** The even-in-time rule this replaced: 180 samples over min(period, 24 h). */
function evenlyTimedOrbit(omm: OmmRecord) {
  const spanMinutes = Math.min(periodMinutes(omm), 24 * 60);
  const timesMs: number[] = [];
  const altitudesKm: number[] = [];
  const vertices: THREE.Vector3[] = [];
  for (let index = 0; index <= 180; index += 1) {
    const sampleTime = new Date(AT.getTime() + (index / 180 - 0.5) * spanMinutes * 60000);
    const state = propagateOmmInFrozenEarthFrame(omm, sampleTime, AT, undefined);
    if (!state) continue;
    timesMs.push(sampleTime.getTime());
    altitudesKm.push(state.altitudeKm);
    vertices.push(drawnPositionOf(state));
  }
  return { timesMs, altitudesKm, vertices };
}

/**
 * How far the drawn polyline strays from the drawn path it stands for, in
 * scene units, measured by propagating a FRESH midpoint for every segment.
 * This is the quantity a kink actually is; a vertex-turn threshold is only its
 * shadow.
 */
function worstChordError(
  omm: OmmRecord,
  timesMs: number[],
  vertices: THREE.Vector3[],
) {
  let worst = 0;
  for (let index = 0; index + 1 < vertices.length; index += 1) {
    const a = vertices[index]!;
    const b = vertices[index + 1]!;
    const midpoint = propagateOmmInFrozenEarthFrame(
      omm,
      new Date((timesMs[index]! + timesMs[index + 1]!) / 2),
      AT,
      undefined,
    );
    if (!midpoint) continue;
    const truth = drawnPositionOf(midpoint);
    const chord = b.clone().sub(a);
    const lengthSquared = chord.lengthSq();
    const offset = truth.clone().sub(a);
    const along = lengthSquared > 0
      ? Math.max(0, Math.min(1, offset.dot(chord) / lengthSquared))
      : 0;
    worst = Math.max(worst, offset.sub(chord.multiplyScalar(along)).length());
  }
  return worst;
}

/** The orbit plane's normal, averaged over the whole path so no one pair sets it. */
function orbitNormal(vertices: THREE.Vector3[]) {
  const normal = new THREE.Vector3();
  for (let index = 0; index + 1 < vertices.length; index += 1) {
    normal.add(new THREE.Vector3().crossVectors(vertices[index]!, vertices[index + 1]!));
  }
  return normal.normalize();
}

/** Signed angle swept about the plane normal, vertex by vertex, in degrees. */
function sweptAngles(vertices: THREE.Vector3[]) {
  const normal = orbitNormal(vertices);
  const swept: number[] = [];
  for (let index = 0; index + 1 < vertices.length; index += 1) {
    const from = vertices[index]!.clone().normalize();
    const to = vertices[index + 1]!.clone().normalize();
    const cross = new THREE.Vector3().crossVectors(from, to);
    swept.push((Math.atan2(cross.dot(normal), from.dot(to)) * 180) / Math.PI);
  }
  return swept;
}

/** Direction change from one drawn segment to the next, in degrees. */
function vertexTurns(vertices: THREE.Vector3[]) {
  const turns: number[] = [];
  for (let index = 1; index + 1 < vertices.length; index += 1) {
    const back = vertices[index]!.clone().sub(vertices[index - 1]!);
    const forward = vertices[index + 1]!.clone().sub(vertices[index]!);
    if (back.length() < 1e-9 || forward.length() < 1e-9) {
      turns.push(0);
      continue;
    }
    const cosine = Math.max(-1, Math.min(1, back.normalize().dot(forward.normalize())));
    turns.push((Math.acos(cosine) * 180) / Math.PI);
  }
  return turns;
}

/**
 * The median and the worst vertex turn on a drawn line, in degrees, INCLUDING
 * the ruler's geostationary joint. It used to exclude a 3,000 km band around
 * that altitude, because the ruler's slope stepped there and the resulting
 * corner would have swamped any real sampler regression. The ruler is C1 as of
 * 2026-08-19, so the exclusion is gone and the joint is held to the same bar
 * as the rest of the line — which is the strongest statement this file can
 * make that the corner is not there any more.
 */
function turnStatistics(vertices: THREE.Vector3[], _altitudesKm: number[]) {
  const turns = vertexTurns(vertices);
  const sorted = [...turns].sort((left, right) => left - right);
  return {
    median: sorted[Math.floor(sorted.length / 2)] ?? 0,
    worst: sorted[sorted.length - 1] ?? 0,
  };
}

/** Altitude of the ruler's geostationary joint, where its slope ramp starts. */
const RULER_JOINT_ALTITUDE_KM = (RADIAL_RULER.anchorRe - 1) * RULER_EARTH_RADIUS_KM;

/** Altitude where that ramp reaches slope 1. */
const RULER_RAMP_END_ALTITUDE_KM = (RADIAL_RULER.noseRampEndRe - 1) * RULER_EARTH_RADIUS_KM;

/**
 * The instant an orbit crosses the ruler's anchor radius, found by scanning
 * the drawn span rather than solved for: the drawn path is what is being
 * interrogated, and the propagator's altitude is what the ruler is handed.
 */
function findJointCrossing(omm: OmmRecord): number | null {
  const spanMs = periodMinutes(omm) * 60000;
  const start = AT.getTime() - spanMs / 2;
  let previous: number | null = null;
  for (let index = 0; index <= 4000; index += 1) {
    const timeMs = start + (index / 4000) * spanMs;
    const state = propagateOmmInFrozenEarthFrame(omm, new Date(timeMs), AT, undefined);
    if (!state) continue;
    const above = state.altitudeKm - RULER_JOINT_ALTITUDE_KM;
    if (previous !== null && previous * above < 0) return timeMs;
    previous = above;
  }
  return null;
}

const cases = [
  { label: "MERIDIAN 9, a Molniya", omm: molniya },
  { label: "COSMOS 2590, at a Tundra period", omm: tundraPeriod },
  { label: "THEMIS A, the photographed cusp", omm: photographedCusp },
  { label: "CLUSTER II-FM7, 53.5 hours round", omm: deepScienceOrbit },
  { label: "ISS, the near-circular control", omm: lowEarthOrbit },
] as const;

describe("the drawn orbit line, on the orbits that broke", () => {
  it.each(cases.map((entry) => [entry.label, entry.omm] as const))(
    "%s draws one complete, closed revolution",
    (_label, omm) => {
      const { vertices, reach } = drawnOrbit(omm);
      const swept = sweptAngles(vertices);
      const total = swept.reduce((sum, step) => sum + step, 0);
      // A full revolution, and no vertex that goes backwards: a truncated span
      // stops short of 360, and a sampler that mis-orders its vertices shows up
      // as a negative step rather than as a smaller total.
      expect(Math.abs(total)).toBeGreaterThan(359.5);
      expect(Math.abs(total)).toBeLessThan(360.5);
      expect(swept.every((step) => Math.sign(step) === Math.sign(total))).toBe(true);
      // And it closes. The residual is real orbital drift over one period, not
      // a gap: measured 0.43% of the drawn reach for the ISS, whose atmosphere
      // moves it most, and under 0.2% for every high orbit here. Before this
      // change CLUSTER II-FM7's ends were 64% of its reach apart.
      const first = vertices[0]!;
      const last = vertices[vertices.length - 1]!;
      expect(last.distanceTo(first) / reach).toBeLessThan(0.006);
    },
  );

  it.each(cases.map((entry) => [entry.label, entry.omm] as const))(
    "%s stays within the drawn tolerance it was built to",
    (_label, omm) => {
      const { vertices, timesMs, tolerance } = drawnOrbit(omm);
      // The sampler's contract, stated directly and checked against freshly
      // propagated midpoints rather than against the ones the refinement
      // happened to look at: no chord of the drawn line departs from the path
      // it stands for by more than the tolerance. Measured 0.037 of 0.102 for
      // the ISS and 0.465 of 0.525 for CLUSTER II-FM7.
      expect(worstChordError(omm, timesMs, vertices)).toBeLessThanOrEqual(tolerance * 1.05);
      // Enough vertices that "no big turn" means something — a 30-vertex loop
      // could satisfy any turn bound by being a coarse polygon — and few
      // enough that this path can be rebuilt while the clock runs.
      expect(vertices.length).toBeGreaterThan(60);
      expect(vertices.length).toBeLessThan(400);
    },
  );

  it.each(cases.map((entry) => [entry.label, entry.omm] as const))(
    "%s carries no vertex that turns like a corner among its neighbours",
    (_label, omm) => {
      const { vertices, altitudesKm } = drawnOrbit(omm);
      // A kink is not a large turn — a tight bend is allowed to turn hard — it
      // is a turn that stands OUT of the line it belongs to. So the bar is the
      // line's own median turn, which makes it scale-free: measured 1.40x on
      // MERIDIAN 9, 1.23x on COSMOS 2590, 1.75x on CLUSTER II-FM7 and 1.00x on
      // the ISS. Three times the median is roughly twice the worst of those.
      const { median, worst } = turnStatistics(vertices, altitudesKm);
      expect(worst).toBeLessThan(Math.max(3 * median, 3));
    },
  );

  it("beats the even-in-time rule it replaced on exactly that measure", () => {
    // Re-measured here rather than remembered, because a bound is only worth
    // having if the rule it replaced would have broken it. 180 samples spaced
    // evenly in TIME leave an 18x spread of drawn segment lengths on a Molniya
    // — 38.7 scene units near perigee against 2.19 near apogee — and the turn
    // at the worst vertex comes out above seven times the line's own median.
    // That is the faceting on the Earthward side of the orbit that Sean
    // photographed.
    //
    // The comparison is on the Molniya alone, and the other two cases say why
    // that is the honest place to draw it. CLUSTER II-FM7's 53.5-hour period
    // meant the old rule drew only the slow apogee arc, where even spacing is
    // perfectly fine — its defect was the truncation, and the completeness
    // guard above is what catches that. COSMOS 2590 at e = 0.36 came out at
    // 2.7x, which is faceting the eye does not pick up; the old rule did not
    // fail everywhere, it failed as eccentricity rose.
    const even = evenlyTimedOrbit(molniya);
    const evenTurns = turnStatistics(even.vertices, even.altitudesKm);
    expect(evenTurns.worst / evenTurns.median).toBeGreaterThan(6);
    for (const omm of [molniya, tundraPeriod]) {
      const adaptive = drawnOrbit(omm);
      const adaptiveTurns = turnStatistics(adaptive.vertices, adaptive.altitudesKm);
      expect(adaptiveTurns.worst / adaptiveTurns.median).toBeLessThan(2);
    }
  });

  it.each([
    ["MERIDIAN 9", molniya],
    ["THEMIS A", photographedCusp],
    ["CLUSTER II-FM7", deepScienceOrbit],
  ] as const)(
    "%s crosses geostationary radius without the corner the ruler used to draw there",
    (_label, omm) => {
      // The defect this replaced: the shared ruler's log-log slope STEPPED
      // from 0.1422 to 1 at 6.617 Re, and a pure radial map refracts a
      // crossing tangent by atan(tan(psi) / slope), so an eccentric orbit bent
      // there by an amount no sampler could remove — 16.1 degrees on
      // MERIDIAN 9, 42.7 on THEMIS A, 45.6 on CLUSTER II-FM7, against 5.0, 6.5
      // and 8.0 for the worst vertex anywhere else on those same lines.
      const { vertices, altitudesKm } = drawnOrbit(omm);
      const turns = vertexTurns(vertices);
      const { median } = turnStatistics(vertices, altitudesKm);
      let atJoint = 0;
      turns.forEach((turn, index) => {
        const altitudeKm = altitudesKm[index + 1] ?? 0;
        // The whole joint band, anchor to ramp end, not just the anchor: the
        // refraction is spread across it now rather than concentrated at a
        // point, so a band-wide worst is the honest reading.
        if (altitudeKm >= RULER_JOINT_ALTITUDE_KM - 500
          && altitudeKm <= RULER_RAMP_END_ALTITUDE_KM + 500) atJoint = Math.max(atJoint, turn);
      });
      // The bar is the line's own median, exactly as it is for every other
      // vertex on the line: the joint may not stand out of the curve it
      // belongs to. Measured 5.0, 5.7 and 5.9 degrees against medians of 3.3,
      // 4.2 and 4.0.
      expect(atJoint).toBeLessThan(Math.max(2 * median, 3));
    },
  );

  it("draws the joint as a curve, not a corner: refining the samples drives its turn to zero", () => {
    // The measurement that separates a tight bend from a discontinuity, and
    // the one no amount of tessellation could have satisfied before. March the
    // drawn path straight through a joint crossing at a FIXED step and refine
    // the step: a corner's turn converges to a constant, a curve's goes to
    // zero. With the ruler's old step this measured 20.84 degrees at 120-second
    // steps and was still 11.96 at 0.5-second steps. With the C1 ramp it
    // measures 0.40 and 0.00.
    const crossing = findJointCrossing(molniya);
    expect(crossing).not.toBeNull();
    const worstTurnAtStep = (stepSeconds: number) => {
      const points: THREE.Vector3[] = [];
      for (let index = -20; index <= 20; index += 1) {
        const state = propagateOmmInFrozenEarthFrame(
          molniya,
          new Date(crossing! + index * stepSeconds * 1000),
          AT,
          undefined,
        );
        if (state) points.push(drawnPositionOf(state));
      }
      return Math.max(...vertexTurns(points));
    };
    const coarse = worstTurnAtStep(120);
    const fine = worstTurnAtStep(3);
    const finest = worstTurnAtStep(0.5);
    expect(coarse).toBeLessThan(2);
    expect(fine).toBeLessThan(coarse);
    expect(finest).toBeLessThan(0.05);
  });

  it("draws a circular orbit AT geostationary radius without that corner", () => {
    // The other half of the same reason: refraction goes as tan(psi), and a
    // circular orbit crosses no radius at all — its motion is purely
    // tangential — so the joint costs it nothing. This is what proves the
    // corner above is refraction rather than something about that altitude.
    const geostationary: OmmRecord = { ...tundraPeriod, ECCENTRICITY: 0.0001, MEAN_MOTION: 1.00273790 };
    const { vertices } = drawnOrbit(geostationary);
    expect(Math.max(...vertexTurns(vertices))).toBeLessThan(6);
  });
});

describe("the adaptive sampler itself", () => {
  const unitCircle = (at: Date) => ({ angle: (at.getTime() / 60000) * (Math.PI / 30) });
  const drawn = (sample: { angle: number }) => ({
    x: 100 * Math.cos(sample.angle),
    y: 0,
    z: 100 * Math.sin(sample.angle),
  });

  it("honours its chord bound rather than a vertex count", () => {
    for (const tolerance of [2, 0.5, 0.05]) {
      const path = adaptiveOrbitPath({
        centre: new Date(0),
        spanMinutes: 60,
        sampleAt: unitCircle,
        drawnPosition: drawn,
        toleranceSceneUnits: tolerance,
        maxVertices: 4000,
      });
      // Sagitta of a circular arc is R(1 - cos(step/2)); the bound has to hold
      // on the real curve, not just on the midpoints the refinement happened
      // to test, so this checks every segment against a fresh midpoint.
      const angles = path.map((sample) => sample.angle);
      let worst = 0;
      for (let index = 0; index + 1 < angles.length; index += 1) {
        const step = Math.abs(angles[index + 1]! - angles[index]!);
        worst = Math.max(worst, 100 * (1 - Math.cos(step / 2)));
      }
      expect(worst).toBeLessThanOrEqual(tolerance * 1.05);
    }
  });

  it("spends fewer vertices on a coarser tolerance", () => {
    const count = (tolerance: number) => adaptiveOrbitPath({
      centre: new Date(0),
      spanMinutes: 60,
      sampleAt: unitCircle,
      drawnPosition: drawn,
      toleranceSceneUnits: tolerance,
      maxVertices: 4000,
    }).length;
    expect(count(2)).toBeLessThan(count(0.05));
  });

  it("stops at its vertex budget instead of stalling the frame", () => {
    const path = adaptiveOrbitPath({
      centre: new Date(0),
      spanMinutes: 60,
      sampleAt: unitCircle,
      drawnPosition: drawn,
      toleranceSceneUnits: 1e-9,
      seedVertices: 16,
      maxVertices: 120,
    });
    expect(path.length).toBe(120);
  });

  it("leaves a chord alone where the propagator will not answer, rather than inventing one", () => {
    // A gap in what SGP4 will say is a gap in knowledge. Refining into it would
    // manufacture vertices from the endpoints, which is drawing a guess.
    const path = adaptiveOrbitPath({
      centre: new Date(0),
      spanMinutes: 60,
      sampleAt: (at) => (at.getTime() > 900_000 && at.getTime() < 1_800_000 ? null : unitCircle(at)),
      drawnPosition: drawn,
      toleranceSceneUnits: 0.05,
      maxVertices: 4000,
    });
    expect(path.length).toBeGreaterThan(30);
    expect(path.every((sample) => Number.isFinite(sample.angle))).toBe(true);
  });
});
