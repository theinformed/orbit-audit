import * as THREE from "three";
import { describe, expect, it } from "vitest";

import { magneticPressureNpa, magnetopauseEvaluator, nguyenBoundary } from "../src/magnetopause";
import {
  createExteriorCuspGeometry,
  createMagnetopauseSurfaceGeometry,
  magnetopauseLegend,
} from "../src/magnetopause-surfaces";
/**
 * The scene's shared radial ruler, as deployed.
 *
 * This is `radiationBeltDisplayRadius` from `src/radiation-belt.ts` — the one
 * curve the satellites, the radiation belts, the SWMF cuts and the
 * magnetopause were all put on so that "is this spacecraft inside the
 * magnetopause" is answerable by eye. It is written out here rather than
 * imported because that function lives on the integration branch and this
 * branch is cut from main; `src/magnetopause-surfaces.ts` deliberately takes
 * the mapper as a parameter and defines no ruler of its own, so there is no
 * second scale to drift out of step. The tests below use the real curve rather
 * than an identity mapper precisely so a second scale could not slip in while
 * every geometry assertion still passed.
 *
 * If the deployed ruler changes, this mirror and the pinned radiation-belt
 * tests move together.
 */
const EARTH_SCENE_RADIUS = 100;
const EARTH_RADIUS_KM = 6371;
const radiationBeltDisplayRadius = (radiusRe: number, earthSceneRadius: number) => {
  const altitudeKm = Math.max(0, radiusRe - 1) * EARTH_RADIUS_KM;
  return earthSceneRadius * (1 + Math.min(2.05, 0.28 * Math.log1p(altitudeKm / 350)));
};
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  // Scene Y is GSM Z and scene -Z is GSM Y, matching the published cuts.
  return new THREE.Vector3(xRe, zRe, -yRe).multiplyScalar(scale);
};

const QUIET = {
  dynamicPressureNpa: 0.9189,
  magneticPressureNpa: magneticPressureNpa(2.53),
  bzGsmNt: 1.5,
  clockAngleRad: (335.93 * Math.PI) / 180,
  dipoleTiltRad: (8.56 * Math.PI) / 180,
};

const STORM = {
  dynamicPressureNpa: 8,
  magneticPressureNpa: magneticPressureNpa(20),
  bzGsmNt: -15,
  clockAngleRad: Math.PI,
  dipoleTiltRad: (8.56 * Math.PI) / 180,
};

function attribute(geometry: THREE.BufferGeometry, name: string) {
  return geometry.getAttribute(name) as THREE.BufferAttribute;
}

describe("boundary surface meshes", () => {
  it("builds a closed-in-azimuth surface for each model", () => {
    for (const id of ["shue1998", "nguyen2022", "lin2010"] as const) {
      const evaluator = magnetopauseEvaluator(id, QUIET)!;
      const surface = createMagnetopauseSurfaceGeometry(evaluator, QUIET, {
        positionForGsm,
        thetaSegments: 32,
        azimuthSegments: 32,
      })!;
      expect(surface).not.toBeNull();
      expect(surface.geometry.getIndex()!.count).toBeGreaterThan(1000);
      expect(surface.subsolarRe).toBeGreaterThan(8);
      expect(surface.subsolarRe).toBeLessThan(16);
    }
  });

  it("passes every vertex through the scene's own radial ruler", () => {
    // Recovering the physical radius from the drawn position and finding the
    // shared ruler is what proves no second scale was introduced.
    const evaluator = magnetopauseEvaluator("nguyen2022", QUIET)!;
    const surface = createMagnetopauseSurfaceGeometry(evaluator, QUIET, {
      positionForGsm,
      thetaSegments: 16,
      azimuthSegments: 16,
    })!;
    const positions = attribute(surface.geometry, "position");
    const radii = attribute(surface.geometry, "physicalRadiusRe");
    for (let index = 0; index < positions.count; index += 1) {
      const physical = radii.getX(index);
      if (physical === 0) continue;
      const scene = Math.hypot(positions.getX(index), positions.getY(index), positions.getZ(index));
      expect(scene).toBeCloseTo(radiationBeltDisplayRadius(physical, EARTH_SCENE_RADIUS), 3);
    }
  });

  it("keeps a Shue surface perfectly axisymmetric in scene units too", () => {
    const evaluator = magnetopauseEvaluator("shue1998", QUIET)!;
    const surface = createMagnetopauseSurfaceGeometry(evaluator, QUIET, {
      positionForGsm,
      thetaSegments: 16,
      azimuthSegments: 16,
    })!;
    const radii = attribute(surface.geometry, "physicalRadiusRe");
    // One ring of constant theta must have one radius, whatever the azimuth.
    const ring: number[] = [];
    for (let azimuth = 0; azimuth < 16; azimuth += 1) ring.push(radii.getX(8 * 16 + azimuth));
    for (const value of ring) expect(value).toBeCloseTo(ring[0]!, 9);
    expect(attribute(surface.geometry, "cuspProximity").getX(8 * 16)).toBe(0);
  });

  it("gives a cusped surface a smaller minimum radius than its nose", () => {
    // The indentation is the only thing that can make the boundary dip below
    // its own subsolar distance, so this is a direct check that it is drawn.
    for (const id of ["nguyen2022", "lin2010"] as const) {
      const evaluator = magnetopauseEvaluator(id, QUIET)!;
      const surface = createMagnetopauseSurfaceGeometry(evaluator, QUIET, {
        positionForGsm,
        thetaSegments: 64,
        azimuthSegments: 32,
      })!;
      expect(surface.radiusRangeRe[0]).toBeLessThan(surface.subsolarRe);
    }
    const shue = magnetopauseEvaluator("shue1998", QUIET)!;
    const flat = createMagnetopauseSurfaceGeometry(shue, QUIET, {
      positionForGsm,
      thetaSegments: 64,
      azimuthSegments: 32,
    })!;
    // Shue's minimum IS its nose: it can never dip below it.
    expect(flat.radiusRangeRe[0]).toBeCloseTo(flat.subsolarRe, 6);
  });
});

describe("the exterior cusp shell", () => {
  it("exists, is bounded, and reports what it measured", () => {
    const cusp = createExteriorCuspGeometry(QUIET, {
      positionForGsm,
      thetaSegments: 96,
      azimuthSegments: 64,
    })!;
    expect(cusp).not.toBeNull();
    expect(cusp.cuspDepthRe).toBeGreaterThan(0.5);
    expect(cusp.cuspDepthRe).toBeLessThan(6);
    expect(cusp.cuspDepthThetaDeg).toBeGreaterThan(20);
    expect(cusp.cuspDepthThetaDeg).toBeLessThan(90);
    // The two models place their cusps at different zenith angles, so the
    // funnel is widest between them and thinner on either model's own axis.
    // Quoting the maximum as "the depth on the cusp axis" would overstate it.
    expect(cusp.depthOnNguyenAxisRe).toBeGreaterThan(0);
    expect(cusp.depthOnNguyenAxisRe).toBeLessThan(cusp.cuspDepthRe);
    // Away from the cusps the two fits differ, and Lin sits outside.
    expect(cusp.modelSpreadRe).toBeLessThan(0);
  });

  it("is a pair of lobes near noon, not a shell around the magnetosphere", () => {
    const cusp = createExteriorCuspGeometry(QUIET, {
      positionForGsm,
      thetaSegments: 96,
      azimuthSegments: 64,
    })!;
    const thickness = attribute(cusp.geometry, "gapThicknessRe");
    let drawn = 0;
    for (let index = 0; index < thickness.count; index += 1) {
      if (thickness.getX(index) > 0) drawn += 1;
    }
    // A shell would fill the grid. Two lobes fill a modest fraction of it.
    expect(drawn).toBeGreaterThan(0);
    expect(drawn / thickness.count).toBeLessThan(0.5);
    expect(cusp.northLobeThetaRangeDeg).not.toBeNull();
    const [start, end] = cusp.northLobeThetaRangeDeg!;
    expect(start).toBeGreaterThan(5);
    expect(end).toBeLessThan(110);
    expect(end - start).toBeGreaterThan(10);
  });

  it("never assigns a negative thickness to a drawn vertex", () => {
    // A negative gap means the inner boundary is outside the current sheet,
    // which is not a cusp and must not be shaded.
    const cusp = createExteriorCuspGeometry(STORM, {
      positionForGsm,
      thetaSegments: 48,
      azimuthSegments: 32,
    })!;
    const thickness = attribute(cusp.geometry, "gapThicknessRe");
    for (let index = 0; index < thickness.count; index += 1) {
      expect(thickness.getX(index)).toBeGreaterThanOrEqual(0);
    }
  });

  it("carries Nguyen's published cusp proximity, not an invented falloff", () => {
    const cusp = createExteriorCuspGeometry(QUIET, {
      positionForGsm,
      thetaSegments: 64,
      azimuthSegments: 32,
    })!;
    const proximity = attribute(cusp.geometry, "cuspProximity");
    let maximum = 0;
    for (let index = 0; index < proximity.count; index += 1) {
      maximum = Math.max(maximum, proximity.getX(index));
      expect(proximity.getX(index)).toBeGreaterThanOrEqual(0);
      expect(proximity.getX(index)).toBeLessThanOrEqual(1.000001);
    }
    // The lobes straddle a cusp axis, so the shell reaches close to 1.
    expect(maximum).toBeGreaterThan(0.7);
  });

  it("moves the funnel equatorward when the IMF turns south", () => {
    const quiet = createExteriorCuspGeometry(QUIET, {
      positionForGsm, thetaSegments: 96, azimuthSegments: 32,
    })!;
    const storm = createExteriorCuspGeometry(STORM, {
      positionForGsm, thetaSegments: 96, azimuthSegments: 32,
    })!;
    const quietCusp = nguyenBoundary(QUIET)!;
    const stormCusp = nguyenBoundary(STORM)!;
    expect(stormCusp.northCuspThetaRad).toBeLessThan(quietCusp.northCuspThetaRad);
    expect(storm.northLobeThetaRangeDeg![0]).toBeLessThan(quiet.northLobeThetaRangeDeg![0] + 1);
  });

  it("puts the northern lobe above the equator and the southern one below", () => {
    // The single easiest thing to get wrong here is the azimuth convention,
    // which would rotate both funnels onto the dawn-dusk line.
    const cusp = createExteriorCuspGeometry(QUIET, {
      positionForGsm, thetaSegments: 64, azimuthSegments: 32,
    })!;
    const positions = attribute(cusp.geometry, "position");
    const thickness = attribute(cusp.geometry, "gapThicknessRe");
    let north = 0;
    let south = 0;
    let equatorial = 0;
    for (let index = 0; index < positions.count; index += 1) {
      if (!(thickness.getX(index) > 0)) continue;
      const sceneY = positions.getY(index); // scene Y is GSM Z
      const sceneZ = positions.getZ(index); // scene -Z is GSM Y
      if (Math.abs(sceneY) < Math.abs(sceneZ)) equatorial += 1;
      else if (sceneY > 0) north += 1;
      else south += 1;
    }
    expect(north).toBeGreaterThan(0);
    expect(south).toBeGreaterThan(0);
    expect(equatorial).toBeLessThan(north + south);
  });

  it("returns nothing rather than a surface when the drivers are unusable", () => {
    expect(createExteriorCuspGeometry({ ...QUIET, dynamicPressureNpa: 0 }, { positionForGsm })).toBeNull();
    expect(createExteriorCuspGeometry({ ...QUIET, dipoleTiltRad: Number.NaN }, { positionForGsm })).toBeNull();
    const evaluator = magnetopauseEvaluator("nguyen2022", QUIET)!;
    expect(
      createMagnetopauseSurfaceGeometry(evaluator, { ...QUIET, dynamicPressureNpa: Number.NaN }, {
        positionForGsm,
      }),
    ).not.toBeNull(); // the evaluator was already built; the drivers only feed proximity
  });
});

describe("legend", () => {
  it("states the evidence class, the drivers and the limitation for each surface", () => {
    const cusp = createExteriorCuspGeometry(QUIET, { positionForGsm, thetaSegments: 48, azimuthSegments: 24 });
    const entries = magnetopauseLegend(QUIET, ["shue1998", "nguyen2022", "lin2010", "exteriorCusp"], cusp);
    expect(entries).toHaveLength(4);
    for (const entry of entries) {
      expect(entry.status).toBe("empirical");
      expect(entry.note.length).toBeGreaterThan(60);
    }
    expect(entries[0]!.detail).toMatch(/subsolar 1[01]\./);
    expect(entries[0]!.note).toMatch(/no cusps/i);
    // The cusped models show the drivers Shue cannot use.
    expect(entries[1]!.detail).toMatch(/clock/);
    expect(entries[1]!.detail).toMatch(/tilt/);
    expect(entries[3]!.detail).toMatch(/funnel up to/);
    expect(entries[3]!.detail).toMatch(/Nguyen's own cusp axis/);
    expect(entries[3]!.detail).toMatch(/north lobe spans/);
  });

  it("drops a surface whose drivers cannot support it rather than faking one", () => {
    const entries = magnetopauseLegend(
      { ...QUIET, dynamicPressureNpa: 0 },
      ["shue1998", "nguyen2022", "lin2010"],
    );
    expect(entries).toHaveLength(0);
  });
});
