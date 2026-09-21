/**
 * Proofs that the solar-wind tracers stay outside the boundary that is drawn.
 *
 * Two properties are worth defending, and both have a history here.
 *
 *   * No tracer may be inside the drawn magnetopause. The obstacle used to be
 *     a sphere sized on the subsolar standoff while the drawn boundary flares
 *     to about 1.4x that at the terminator, so 142 of 1,197 drawn tracers —
 *     one in eight — were rendered inside the surface the reader was looking
 *     at. It read as "the solar wind passes straight through", and that is
 *     what it was.
 *
 *   * The obstacle must track the published standoff rather than a constant.
 *     A frozen obstacle would still look like deflection while quietly
 *     ignoring a storm compressing the boundary by two Earth radii.
 *
 * The first property is asserted against the same model evaluator the renderer
 * builds the surface from, at directions chosen to include the flanks, because
 * the nose was never where the defect was.
 */
import * as THREE from "three";
import { describe, expect, it } from "vitest";
import {
  SOLAR_INPUT_VISUAL_METHOD,
  createIllustrativeUpstreamFlowGeometry,
  createSolarWindVisual,
  createXrayIrradianceVisual,
  illustrativeUpstreamDomain,
  tabulateObstacleShape,
  teachingFlowPointAroundObstacle,
} from "../src/solar-input-visuals";
import { magnetopauseEvaluator, nguyenBoundary, nguyenUnindentedRadiusRe } from "../src/magnetopause";
import type { CuspedBoundaryDrivers } from "../src/magnetopause";

/** A real storm-time driver set: compressed, southward, tilted. */
const drivers: CuspedBoundaryDrivers = {
  dynamicPressureNpa: 4.1,
  magneticPressureNpa: 0.089,
  bzGsmNt: -14.5,
  clockAngleRad: (190.1 * Math.PI) / 180,
  dipoleTiltRad: 0.32,
};

function drawnBoundaryRadius(source: CuspedBoundaryDrivers) {
  const nguyenParameters = nguyenBoundary(source);
  const lin = magnetopauseEvaluator("lin2010", source);
  const shue = magnetopauseEvaluator("shue1998", source);
  if (!nguyenParameters || !lin || !shue) throw new Error("test drivers must evaluate all three models");
  const cutoff = (120 * Math.PI) / 180;
  return (theta: number, azimuth: number) => Math.max(
    nguyenUnindentedRadiusRe(Math.min(theta, cutoff), azimuth, source, nguyenParameters),
    lin.radiusRe(Math.min(theta, cutoff), azimuth),
    shue.radiusRe(theta, azimuth),
  );
}

/** Radius of the drawn surface in the direction of a GSM point. */
function boundaryRadiusTowards(
  radius: (theta: number, azimuth: number) => number,
  xRe: number,
  yRe: number,
  zRe: number,
) {
  const distance = Math.hypot(xRe, yRe, zRe);
  const theta = Math.acos(Math.min(1, Math.max(-1, xRe / distance)));
  // Azimuth from GSM +z, which is magnetopausePointGsm's convention.
  return radius(theta, Math.atan2(yRe, zRe));
}

describe("solar-wind tracers against the drawn magnetopause", () => {
  it("puts no tracer inside the drawn boundary, on the flanks or at the nose", () => {
    const radius = drawnBoundaryRadius(drivers);
    const options = {
      earthRadiusRe: 1,
      magnetopauseStandoffRe: 7.4,
      magnetopauseGapRe: 1.25,
      boundaryRadiusForDirection: radius,
      particleCount: 4000,
      seed: 20260808,
    };
    const domain = illustrativeUpstreamDomain(options);
    const geometry = createIllustrativeUpstreamFlowGeometry(options);
    const x = geometry.getAttribute("gsmXRe");
    const y = geometry.getAttribute("gsmYRe");
    const z = geometry.getAttribute("gsmZRe");

    let flankSamples = 0;
    for (let index = 0; index < x.count; index += 1) {
      const xRe = x.getX(index);
      const yRe = y.getX(index);
      const zRe = z.getX(index);
      const distance = Math.hypot(xRe, yRe, zRe);
      const boundary = boundaryRadiusTowards(radius, xRe, yRe, zRe);
      expect(distance).toBeGreaterThan(boundary);
      // Cover the flanks explicitly: the sphere was right at the nose and
      // wrong everywhere else, so a test that only sampled x > 0 would have
      // passed over the defect it exists to catch.
      if (xRe < 0) flankSamples += 1;
    }
    expect(flankSamples).toBeGreaterThan(100);
    expect(geometry.userData.physicsModel).toContain("drawn-empirical-magnetopause");
    geometry.dispose();

    // And the shape is not merely enclosing: it is the boundary plus the gap.
    expect(domain.obstacle.shaped).toBe(true);
    expect(domain.obstacleRadiusRe).toBeCloseTo(radius(0, 0) + 1.25, 2);
  });

  it("keeps the no-penetration guarantee for a single deep flank sample", () => {
    const radius = drawnBoundaryRadius(drivers);
    const obstacle = tabulateObstacleShape(radius, 1.25);
    // A tracer aimed a long way inside the nose, at the terminator, on the
    // dawn meridian: the exact geometry the spherical obstacle got wrong.
    const point = teachingFlowPointAroundObstacle(0, 3, 0, obstacle);
    const distance = Math.hypot(point.xRe, point.yRe, point.zRe);
    expect(distance).toBeGreaterThan(boundaryRadiusTowards(radius, point.xRe, point.yRe, point.zRe));
    // The azimuth is conserved, which is what lets the obstacle be sampled on
    // the tracer's own meridian.
    expect(point.zRe).toBeCloseTo(0, 9);
    expect(point.yRe).toBeGreaterThan(3);
  });

  it("tracks the published standoff instead of a constant", () => {
    const quiet = createSolarWindVisual({ magnetopauseStandoffRe: 11, magnetopauseGapRe: 1.25 });
    const quietNose = quiet.points.geometry.userData.domain.obstacleRadiusRe as number;
    quiet.setMagnetopauseStandoffRe(7.4);
    const compressedNose = quiet.points.geometry.userData.domain.obstacleRadiusRe as number;
    expect(quietNose).toBeCloseTo(12.25, 6);
    expect(compressedNose).toBeCloseTo(8.65, 6);
    expect(compressedNose).toBeLessThan(quietNose);

    // A missing standoff must not freeze the compressed one in place: it
    // returns to the layer's own configured value rather than holding a
    // storm-time boundary over a time that published nothing.
    quiet.setMagnetopauseStandoffRe(null);
    expect(quiet.points.geometry.userData.domain.obstacleRadiusRe).toBeCloseTo(12.25, 6);
    quiet.dispose();

    // The same must hold through the shaped obstacle: a storm that compresses
    // the boundary has to move the surface the tracers turn around.
    const shaped = createSolarWindVisual({ magnetopauseGapRe: 1.25 });
    shaped.setBoundaryRadiusForDirection(drawnBoundaryRadius(drivers));
    const stormNose = shaped.points.geometry.userData.domain.obstacleRadiusRe as number;
    shaped.setBoundaryRadiusForDirection(drawnBoundaryRadius({
      ...drivers,
      dynamicPressureNpa: 1.2,
      bzGsmNt: 3,
    }));
    const calmNose = shaped.points.geometry.userData.domain.obstacleRadiusRe as number;
    expect(stormNose).toBeLessThan(calmNose);
    shaped.dispose();
  });

  it("draws one streak per tracer, along that tracer's own streamline", () => {
    const visual = createSolarWindVisual({
      magnetopauseStandoffRe: 7.4,
      boundaryRadiusForDirection: drawnBoundaryRadius(drivers),
      particleCount: 400,
      trailLength: 2,
      seed: 11,
    });
    visual.setConditions(420, 12);
    visual.update(3.5);
    const heads = visual.points.geometry.getAttribute("position");
    const streaks = visual.trails.geometry.getAttribute("position");
    expect(streaks.count).toBe(heads.count * 2);
    expect(visual.trails.geometry.drawRange.count).toBe(visual.points.geometry.drawRange.count * 2);

    let checked = 0;
    for (let index = 0; index < Math.min(200, heads.count); index += 1) {
      const headX = heads.getX(index);
      const headY = heads.getY(index);
      const headZ = heads.getZ(index);
      expect(streaks.getX(index * 2)).toBeCloseTo(headX, 5);
      expect(streaks.getY(index * 2)).toBeCloseTo(headY, 5);
      expect(streaks.getZ(index * 2)).toBeCloseTo(headZ, 5);
      // Fixed length, so the streak is never readable as a speed.
      const length = Math.hypot(
        streaks.getX(index * 2 + 1) - headX,
        streaks.getY(index * 2 + 1) - headY,
        streaks.getZ(index * 2 + 1) - headZ,
      );
      expect(length).toBeCloseTo(2, 4);
      checked += 1;
    }
    expect(checked).toBe(200);
    visual.dispose();
  });

  it("keeps the 3-D cloud drawn WITH the model plane tracers — never a two-plane-only layer", () => {
    // The regression this pins: model-projected mode used to REPLACE the 3-D
    // cloud with tracers confined to the two published cut planes, so from
    // any oblique camera the whole layer collapsed into a sparse dotted line.
    const visual = createSolarWindVisual({
      magnetopauseStandoffRe: 9.5,
      boundaryRadiusForDirection: drawnBoundaryRadius(drivers),
      particleCount: 900,
      seed: 5,
      modelFlow: null,
    });
    visual.setConditions(420, 8);
    const cloud = visual.points.geometry;
    const y = cloud.getAttribute("gsmYRe");
    const z = cloud.getAttribute("gsmZRe");
    // Genuinely volumetric: a healthy share of tracers sit well away from
    // BOTH published planes (equatorial z=0 and meridional y=0) at once.
    let offBothPlanes = 0;
    for (let index = 0; index < y.count; index += 1) {
      if (Math.abs(y.getX(index)) > 2 && Math.abs(z.getX(index)) > 2) offBothPlanes += 1;
    }
    expect(offBothPlanes / y.count).toBeGreaterThan(0.3);
    // And the cloud geometry survives a model-flow arrival untouched in kind.
    expect(cloud.userData.kind).toBe("physics-based-teaching-solar-wind-tracers");
    visual.dispose();
  });

  it("falls back to a sphere, and says so, when no boundary is drawn", () => {
    const visual = createSolarWindVisual({ magnetopauseStandoffRe: 9, magnetopauseGapRe: 1.5 });
    expect(visual.points.geometry.userData.physicsModel)
      .toBe("axisymmetric-incompressible-potential-flow-around-sphere");
    visual.setBoundaryRadiusForDirection(drawnBoundaryRadius(drivers));
    expect(visual.points.geometry.userData.physicsModel).toContain("drawn-empirical-magnetopause");
    visual.setBoundaryRadiusForDirection(null);
    expect(visual.points.geometry.userData.physicsModel)
      .toBe("axisymmetric-incompressible-potential-flow-around-sphere");
    visual.dispose();
  });
});

describe("X-ray photons against the same boundary", () => {
  /**
   * The one thing that must never be "fixed" here.
   *
   * Sean asked why the X-rays do not interact with the magnetosphere. Bending
   * them would make a prettier picture and teach a Navy officer something
   * false: X-rays are photons, they carry no charge, and no magnetic field
   * deflects them.
   *
   * The guard has had three shapes, following what the layer draws. It first
   * pinned that every drawn photon streak stayed exactly sunward. When the
   * glyph field was deleted (flux is a single scalar, not a spatial field —
   * HANDOFF-FIELD-FIRST.md §2 item 5) it became "no particle object exists at
   * all". Sean then asked for the arrival itself back, precisely because the
   * contrast is the lesson: "it would be good since users would see that they
   * don't deflect like the solar wind and IMF." So there is a drawn beam
   * again, and the guard returns to its strongest form — the beam is straight,
   * it is parallel, and the drivers that visibly move the wind's obstacle move
   * nothing about it at all.
   */
  it("draws a straight parallel beam that a storm driver cannot bend", () => {
    const quiet: CuspedBoundaryDrivers = {
      dynamicPressureNpa: 1.1,
      magneticPressureNpa: 0.02,
      bzGsmNt: 3.4,
      clockAngleRad: 0.2,
      dipoleTiltRad: 0.32,
    };
    // First: prove the driver change is one the WIND answers. Without this the
    // photon half of the test could pass against a driver set that moves
    // nothing, and prove nothing.
    const windOptions = {
      earthRadiusRe: 1,
      magnetopauseStandoffRe: 7.4,
      magnetopauseGapRe: 1.25,
      particleCount: 400,
      seed: 4242,
    };
    const quietWind = createIllustrativeUpstreamFlowGeometry({
      ...windOptions,
      boundaryRadiusForDirection: drawnBoundaryRadius(quiet),
    });
    const stormWind = createIllustrativeUpstreamFlowGeometry({
      ...windOptions,
      boundaryRadiusForDirection: drawnBoundaryRadius(drivers),
    });
    let movedTracers = 0;
    const quietY = quietWind.getAttribute("gsmYRe");
    const stormY = stormWind.getAttribute("gsmYRe");
    for (let index = 0; index < quietY.count; index += 1) {
      if (Math.abs(quietY.getX(index) - stormY.getX(index)) > 0.05) movedTracers += 1;
    }
    expect(movedTracers).toBeGreaterThan(100);
    quietWind.dispose();
    stormWind.dispose();

    // Now the photons, through the same driver change. The X-ray visual is
    // not even offered the boundary: there is no setter for a driver, a
    // standoff or a boundary field, so a future regression cannot quietly
    // start consulting one.
    const visual = createXrayIrradianceVisual({
      earthRadius: 100,
      upperAtmosphereRadius: 104,
      photonRayCount: 64,
      seed: 99,
    });
    expect((visual as unknown as { setBoundaryRadiusForDirection?: unknown }).setBoundaryRadiusForDirection)
      .toBeUndefined();
    expect((visual as unknown as { setMagnetopauseStandoffRe?: unknown }).setMagnetopauseStandoffRe)
      .toBeUndefined();
    expect((visual as unknown as { setConditions?: unknown }).setConditions).toBeUndefined();

    visual.setFlux(2.4e-5);
    const positions = visual.streaks.geometry.getAttribute("position") as THREE.BufferAttribute;
    const drawn = visual.drawnRayCount;
    expect(drawn).toBeGreaterThan(0);

    // Sample each ray at many points of its crossing and require the samples
    // to be collinear: cross-product area against the ray's own first-to-last
    // chord, in scene units, must vanish.
    for (let ray = 0; ray < drawn; ray += 1) {
      const samples: THREE.Vector3[] = [];
      for (let step = 0; step <= 40; step += 1) {
        // Drive the beam through the renderer's own update(), not through a
        // re-derivation: the phase offset makes each ray reach a different
        // progress at a given time, so read the ray back out of the buffer.
        visual.update(step * 0.01);
        samples.push(new THREE.Vector3(
          positions.getX(ray * 2),
          positions.getY(ray * 2),
          positions.getZ(ray * 2),
        ));
      }
      const first = samples[0]!;
      const last = samples.at(-1)!;
      const chord = last.clone().sub(first);
      expect(chord.length()).toBeGreaterThan(1);
      for (const sample of samples) {
        const offset = sample.clone().sub(first);
        // Distance from the chord line, in scene units on a 100-unit Earth.
        const deviation = offset.clone().cross(chord).length() / chord.length();
        expect(deviation).toBeLessThan(1e-4);
      }
      // Parallel, not merely straight: the transverse coordinates never move,
      // so every ray in the beam runs along the same Sun-Earth direction.
      const transverse = samples.map((sample) => Math.hypot(sample.y, sample.z));
      expect(Math.max(...transverse) - Math.min(...transverse)).toBeLessThan(1e-4);
    }

    expect(SOLAR_INPUT_VISUAL_METHOD.xray.limitation).toContain("does not deflect X-rays");
    expect(SOLAR_INPUT_VISUAL_METHOD.xray.photons).toContain("straight and parallel");
    visual.dispose();
  });
});
