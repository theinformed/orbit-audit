import * as THREE from "three";
import { describe, expect, it } from "vitest";

import {
  EARTH_SCENE_RADIUS,
  gsmSceneAxes,
} from "../src/globe";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";
import { satelliteDisplayRadius } from "../src/globe";
import {
  type CuspedBoundaryDrivers,
  magneticPressureNpa,
  magnetopauseEvaluator,
} from "../src/magnetopause";
import {
  createExteriorCuspGeometry,
  createMagnetopauseSurfaceGeometry,
} from "../src/magnetopause-surfaces";

/**
 * The drawn boundary against the scene's one ruler.
 *
 * `tests/magnetopause-surfaces.test.ts` already proves the geometry module
 * honours whatever mapper it is handed. This file tests the other half, which
 * is the half that was actually broken: that the mapper the globe hands it is
 * the same one the satellites, the belts and the SWMF cut planes use, and
 * that it is a *pure radial* map — the anti-sunward tail stretch is gone,
 * because the ruler now carries the tail's elongation itself, and a scene
 * with exactly one radial map in every direction is the property that makes
 * "is this spacecraft inside the magnetopause" answerable by eye.
 */

/** Exactly what `SpaceGlobe.modelGsmPosition` does, reassembled from its parts. */
function modelGsmPosition(xRe: number, yRe: number, zRe: number) {
  const physicalRadius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(physicalRadius, EARTH_SCENE_RADIUS) / physicalRadius;
  return gsmSceneAxes(xRe, yRe, zRe).multiplyScalar(scale);
}

const QUIET: CuspedBoundaryDrivers = {
  dynamicPressureNpa: 0.92,
  magneticPressureNpa: magneticPressureNpa(2.53),
  bzGsmNt: 1.5,
  clockAngleRad: (335.9 * Math.PI) / 180,
  dipoleTiltRad: (8.6 * Math.PI) / 180,
};

const STORM: CuspedBoundaryDrivers = {
  dynamicPressureNpa: 20,
  magneticPressureNpa: magneticPressureNpa(45),
  bzGsmNt: -40,
  clockAngleRad: Math.PI,
  dipoleTiltRad: (8.6 * Math.PI) / 180,
};

const OPTIONS = {
  positionForGsm: modelGsmPosition,
  thetaSegments: 96,
  azimuthSegments: 96,
};

function subsolarSceneRadius(id: Parameters<typeof magnetopauseEvaluator>[0], drivers: CuspedBoundaryDrivers) {
  const evaluator = magnetopauseEvaluator(id, drivers);
  expect(evaluator).not.toBeNull();
  const surface = createMagnetopauseSurfaceGeometry(evaluator!, drivers, OPTIONS);
  expect(surface).not.toBeNull();
  const position = surface!.geometry.getAttribute("position");
  // Vertex 0 is theta = 0, the subsolar point.
  return new THREE.Vector3(position.getX(0), position.getY(0), position.getZ(0)).length();
}

describe("the drawn magnetopause sits on the scene's shared ruler", () => {
  it("puts the subsolar nose exactly where the satellite ruler would put that radius", () => {
    for (const id of ["shue1998", "nguyen2022", "lin2010"] as const) {
      const evaluator = magnetopauseEvaluator(id, QUIET)!;
      const expected = radiationBeltDisplayRadius(evaluator.subsolarRe, EARTH_SCENE_RADIUS);
      // The dayside is untouched by the tail stretch, so this has to be exact,
      // not close: the nose is where the "inside or outside" question is asked.
      expect(subsolarSceneRadius(id, QUIET)).toBeCloseTo(expected, 4);
      // And the same number is where a satellite at that radius would be drawn.
      expect(expected).toBeCloseTo(satelliteDisplayRadius((evaluator.subsolarRe - 1) * 6371), 4);
    }
  });

  it("maps every direction with the one radial ruler and no per-axis stretch", () => {
    // The retired anti-sunward stretch multiplied x by up to 1.85 on the
    // nightside, which made the tail the one direction where a drawn distance
    // could not be read against the shared ruler. The ruler now carries the
    // tail's elongation, so a point's drawn radius must equal the ruler's
    // answer for its physical radius in *every* direction, tail included.
    for (const [xRe, yRe, zRe] of [[-5, 0, 0], [-30, 4, 2], [-50, 0, 0], [0, 12, 0], [9, 0, 3]] as const) {
      const drawn = modelGsmPosition(xRe, yRe, zRe).length();
      const expected = radiationBeltDisplayRadius(Math.hypot(xRe, yRe, zRe), EARTH_SCENE_RADIUS);
      expect(drawn).toBeCloseTo(expected, 6);
    }
  });

  it("draws the nose-to-flank flaring at the surface's own physical ratio", () => {
    // The complaint this pins: with the live moderate-storm drivers (subsolar
    // standoff 7.35 Re) the Shue surface flares 1.64x from nose to terminator,
    // and the old logarithmic ruler drew that as 1.066x — a near-sphere
    // however correct the physics upstream was. Under those drivers the nose
    // and the terminator both live in the ruler's linear band (GEO to the
    // bow-shock nose), so the drawn ratio must now equal the physical ratio
    // exactly, not merely approach it.
    const moderate: CuspedBoundaryDrivers = {
      dynamicPressureNpa: 4.1,
      magneticPressureNpa: magneticPressureNpa(10),
      bzGsmNt: -14.5,
      clockAngleRad: (190.1 * Math.PI) / 180,
      dipoleTiltRad: 0.32,
    };
    const evaluator = magnetopauseEvaluator("shue1998", moderate)!;
    expect(evaluator.subsolarRe).toBeGreaterThan(6.6);
    const surface = createMagnetopauseSurfaceGeometry(evaluator, moderate, OPTIONS)!;
    const position = surface.geometry.getAttribute("position");
    const physical = surface.geometry.getAttribute("physicalRadiusRe");
    const drawnRadius = (index: number) =>
      new THREE.Vector3(position.getX(index), position.getY(index), position.getZ(index)).length();
    // Vertex 0 is the nose. The terminator row is theta = 90 degrees, which is
    // row 72 of 96 in the default 120-degree window.
    const azimuthSegments = 96;
    const terminatorIndex = 72 * azimuthSegments;
    const trueRatio = physical.getX(terminatorIndex) / physical.getX(0);
    const drawnRatio = drawnRadius(terminatorIndex) / drawnRadius(0);
    expect(physical.getX(terminatorIndex)).toBeLessThan(13);
    expect(trueRatio).toBeGreaterThan(1.5);
    expect(drawnRatio).toBeCloseTo(trueRatio, 6);
  });

  it("still shows the boundary moving inside geostationary orbit in a severe storm", () => {
    const geo = radiationBeltDisplayRadius(6.6, EARTH_SCENE_RADIUS);
    const quiet = subsolarSceneRadius("shue1998", QUIET);
    const storm = subsolarSceneRadius("shue1998", STORM);
    expect(quiet).toBeGreaterThan(geo);
    expect(storm).toBeLessThan(geo);
    // And the swing is legible rather than a rounding error on a 100-unit Earth.
    expect(quiet - storm).toBeGreaterThan(15);
  });

  it("moves the cusped surfaces visibly between quiet and storm drivers", () => {
    const quiet = subsolarSceneRadius("nguyen2022", QUIET);
    const storm = subsolarSceneRadius("nguyen2022", STORM);
    expect(quiet - storm).toBeGreaterThan(10);
  });

  it("draws an exterior cusp shell on the scene ruler under live-like drivers", () => {
    const cusp = createExteriorCuspGeometry(QUIET, OPTIONS);
    expect(cusp).not.toBeNull();
    expect(cusp!.cuspDepthRe).toBeGreaterThan(0);
    // The two fits are not nested: away from the funnel Lin sits outside
    // Nguyen, so the reported spread is negative. If this ever comes out
    // positive the shell has quietly become a shell around everything.
    expect(cusp!.modelSpreadRe).toBeLessThan(0);
    expect(cusp!.northLobeThetaRangeDeg).not.toBeNull();
    const position = cusp!.geometry.getAttribute("position");
    let drawn = 0;
    for (const index of cusp!.geometry.getIndex()!.array) {
      const radius = Math.hypot(position.getX(index), position.getY(index), position.getZ(index));
      // Every shell vertex must be inside the drawn scene, on the same ruler.
      expect(radius).toBeGreaterThan(EARTH_SCENE_RADIUS);
      expect(radius).toBeLessThan(radiationBeltDisplayRadius(60, EARTH_SCENE_RADIUS));
      drawn += 1;
    }
    expect(drawn).toBeGreaterThan(0);
  });
});
