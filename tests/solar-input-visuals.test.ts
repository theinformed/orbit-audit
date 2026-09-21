import * as THREE from "three";
import { describe, expect, it } from "vitest";
import {
  SOLAR_INPUT_VISUAL_METHOD,
  XRAY_FLUX_GRADIENT_CSS,
  createDaysideExposureGeometry,
  DEFAULT_DOWNSTREAM_END_RE,
  createIllustrativeUpstreamFlowGeometry,
  createSolarWindObstacleSilhouette,
  createSolarWindVisual,
  createXrayIrradianceVisual,
  goesXrayClass,
  illustrativeUpstreamDomain,
  solarWindIntensityEncoding,
  teachingFlowPointAroundObstacle,
  xrayIrradianceEncoding,
  xrayPhotonRayHead,
} from "../src/solar-input-visuals";
import { sharedDisplayRadius } from "../src/radial-ruler";
import { shueBoundary } from "../src/magnetopause";
import type {
  EncodedProjectedStreamlines,
  GeospaceStructuresDefinition,
} from "../src/geospace-structures";

function littleEndianU16(values: number[]) {
  const bytes = new Uint8Array(values.length * 2);
  values.forEach((value, index) => {
    bytes[index * 2] = value & 255;
    bytes[index * 2 + 1] = value >>> 8;
  });
  return btoa(String.fromCharCode(...bytes));
}

function littleEndianI16(values: number[]) {
  return littleEndianU16(values.map((value) => value < 0 ? value + 65536 : value));
}

const definition: GeospaceStructuresDefinition = {
  status: "model-derived-proxies",
  coordinateSystem: "GSM",
  anglesDegrees: [-10, 0, 10],
  radiusEncoding: { storage: "little-endian uint16 base64", scaleRe: 0.01, missingValue: 65535 },
  streamlineEncoding: { storage: "compact", scaleRe: 0.01, flowSpeedScaleKps: 0.1 },
};

function projectedFlow(
  pointsHundredthsRe: Array<[number, number]>,
  speedTenthsKps: number[],
): EncodedProjectedStreamlines {
  return {
    lineCount: 1,
    pointCount: pointsHundredthsRe.length,
    coordinatesI16: littleEndianI16(pointsHundredthsRe.flat()),
    offsetsU16: littleEndianU16([0, pointsHundredthsRe.length]),
    speedU16: littleEndianU16(speedTenthsKps),
  };
}

describe("solar-wind input encodings", () => {
  it("responds monotonically to real upstream speed and density without calling glyphs particles", () => {
    const quiet = solarWindIntensityEncoding(300, 1);
    const active = solarWindIntensityEncoding(700, 20);
    expect(active.activeFraction).toBeGreaterThan(quiet.activeFraction);
    expect(active.opacity).toBeGreaterThan(quiet.opacity);
    expect(active.pointSize).toBeGreaterThan(quiet.pointSize);
    expect(quiet.pointSize).toBeGreaterThanOrEqual(1.55);
    expect(quiet.opacity).toBeGreaterThanOrEqual(0.28);
    expect(solarWindIntensityEncoding(null, 5).available).toBe(false);
    expect(SOLAR_INPUT_VISUAL_METHOD.solarWind.limitation).toContain("not observed individual trajectories");
    expect(SOLAR_INPUT_VISUAL_METHOD.solarWind.approximation).toContain("not an MHD");
  });

  it("deflects teaching tracers around a magnetopause-sized no-penetration obstacle", () => {
    const options = {
      earthRadiusRe: 1,
      magnetopauseStandoffRe: 9,
      magnetopauseGapRe: 1.5,
      upstreamStartRe: 24,
      particleCount: 600,
      seed: 7,
    };
    const earthRadiusForClamp = options.earthRadiusRe;
    const domain = illustrativeUpstreamDomain(options);
    const geometry = createIllustrativeUpstreamFlowGeometry(options);
    const x = [...geometry.getAttribute("gsmXRe").array];
    const y = geometry.getAttribute("gsmYRe");
    const z = geometry.getAttribute("gsmZRe");
    const alpha = [...geometry.getAttribute("flowAlpha").array];
    expect(domain.obstacleRadiusRe).toBe(10.5);
    // The shower carries on past Earth and down the tail, because that is what
    // the solar wind does. Sean: "it looks like it stops at the earth now...
    // in reality the majority of the solar wind flows right over it."
    //
    // The clamp is still here and still guards a degenerate domain, but it is
    // no longer what sets the default: an Earth of any radius cannot push the
    // end sunward of its own surface.
    expect(domain.downstreamEndRe).toBe(DEFAULT_DOWNSTREAM_END_RE);
    expect(domain.downstreamEndRe).toBeLessThan(-earthRadiusForClamp - 0.5);
    expect(illustrativeUpstreamDomain({ ...options, downstreamEndRe: 5 }).downstreamEndRe)
      .toBeCloseTo(-earthRadiusForClamp - 0.5, 6);
    expect(Math.min(...x)).toBeGreaterThanOrEqual(domain.downstreamEndRe);
    expect(Math.max(...x)).toBeLessThanOrEqual(domain.upstreamStartRe);
    for (let index = 0; index < x.length; index += 1) {
      expect(Math.hypot(x[index]!, y.getX(index), z.getX(index)))
        .toBeGreaterThanOrEqual(domain.obstacleRadiusRe - 1e-4);
    }
    expect(Math.min(...alpha)).toBeLessThan(0.1);
    expect(Math.max(...alpha)).toBeLessThanOrEqual(1);
    expect(geometry.userData).toMatchObject({
      kind: "physics-based-teaching-solar-wind-tracers",
      physicsModel: "axisymmetric-incompressible-potential-flow-around-sphere",
      classification: "teaching tracers—not observed individual trajectories",
    });

    const far = teachingFlowPointAroundObstacle(24, 2, 0, domain.obstacleRadiusRe);
    const flank = teachingFlowPointAroundObstacle(0, 2, 0, domain.obstacleRadiusRe);
    expect(flank.yRe).toBeGreaterThan(far.yRe * 4);
    expect(Math.hypot(flank.xRe, flank.yRe, flank.zRe)).toBeGreaterThan(domain.obstacleRadiusRe);
    geometry.dispose();
  });

  it("draws the obstacle it deflects the flow around, because the ruler cannot tell arriving flow from departed", () => {
    // The ruler measurement that closed the cloud into a shell. It is still
    // true, and it is why the fix is not "draw less flow".
    //
    // The layer owns no distance of its own: every tracer goes through
    // sharedDisplayRadius. Past the taper the ruler has a log-log slope of
    // 0.14, so out in the free stream a large change in physical distance is
    // almost no change in drawn distance. Flow 30 Re BEHIND Earth draws at
    // essentially the radius of flow 32 Re IN FRONT of it.
    const drawnEarthRadii = (radiusRe: number) => sharedDisplayRadius(radiusRe, 100) / 100;
    const arriving = drawnEarthRadii(32);
    const departed = drawnEarthRadii(30);
    expect(Math.abs(departed / arriving - 1)).toBeLessThan(0.05);

    // The deflection is the one thing the ruler still separates: the nose draws
    // well inside the free stream, and that gradient is the whole teaching
    // content of the layer.
    const domain = illustrativeUpstreamDomain({ earthRadiusRe: 1, magnetopauseStandoffRe: 9.5 });
    expect(drawnEarthRadii(domain.obstacleRadiusRe) / arriving).toBeLessThan(0.7);

    // What was missing was never the flow, it was the obstacle. Every tracer in
    // this domain impacts inside the tail's own transverse radius, so every one
    // of them ends up in the sheath: there is no undisturbed free stream here
    // to drop, and a sheath is only legible when the thing it sheathes is on
    // screen. So the layer draws it, from the SAME table the streamline solve
    // refuses to let a tracer through.
    const identity = (xRe: number, yRe: number, zRe: number) => new THREE.Vector3(xRe, yRe, zRe);
    const extent = (group: THREE.Group) => {
      const surface = group.getObjectByName("solar-wind-obstacle-surface") as THREE.Mesh;
      expect(surface).toBeTruthy();
      const drawn = surface.geometry.getAttribute("position");
      let noseX = -Infinity;
      let tailX = Infinity;
      for (let index = 0; index < drawn.count; index += 1) {
        noseX = Math.max(noseX, drawn.getX(index));
        tailX = Math.min(tailX, drawn.getX(index));
      }
      return { noseX, tailX };
    };

    // The spherical fallback has no tail to draw, and must not invent one: the
    // furthest back a sphere of radius a reaches by the boundary models' own
    // 150-degree cutoff is a*cos(150) = -0.866a.
    const spherical = extent(createSolarWindObstacleSilhouette(domain.obstacle, identity, {
      downstreamEndRe: domain.downstreamEndRe,
    }));
    expect(spherical.noseX).toBeCloseTo(domain.obstacleRadiusRe, 3);
    expect(spherical.tailX).toBeCloseTo(-0.866 * domain.obstacleRadiusRe, 1);

    // The shaped obstacle is the one that actually ships: Shue, flaring, plus
    // the display gap. It runs back down the tail, and it stops where the drawn
    // flow stops rather than at the surface's own 150-degree cutoff, which is
    // out past -44 Re at these drivers.
    const shue = shueBoundary(3.09, -2.5)!;
    const shaped = illustrativeUpstreamDomain({
      earthRadiusRe: 1,
      magnetopauseStandoffRe: shue.subsolarStandoffRe,
      boundaryRadiusForDirection: (thetaRad) =>
        shue.subsolarStandoffRe * (2 / (1 + Math.cos(thetaRad))) ** shue.flaringAlpha,
    });
    expect(shaped.obstacle.shaped).toBe(true);
    const tail = extent(createSolarWindObstacleSilhouette(shaped.obstacle, identity, {
      downstreamEndRe: shaped.downstreamEndRe,
    }));
    expect(tail.noseX).toBeCloseTo(shaped.obstacleRadiusRe, 3);
    expect(tail.tailX).toBeLessThan(-20);
    // It must never be drawn beyond where the flow itself is drawn.
    expect(tail.tailX).toBeGreaterThanOrEqual(shaped.downstreamEndRe - 1e-6);
    // And it must never sit inside the surface the tracers are held outside of,
    // or the tracers would visibly cross their own obstacle.
    const geometry = createIllustrativeUpstreamFlowGeometry({
      earthRadiusRe: 1,
      magnetopauseStandoffRe: 9.5,
      particleCount: 400,
      seed: 11,
    });
    const gx = geometry.getAttribute("gsmXRe");
    const gy = geometry.getAttribute("gsmYRe");
    const gz = geometry.getAttribute("gsmZRe");
    for (let index = 0; index < gx.count; index += 1) {
      const x = gx.getX(index);
      const y = gy.getX(index);
      const z = gz.getX(index);
      const radius = Math.hypot(x, y, z);
      const theta = Math.acos(Math.min(1, Math.max(-1, x / Math.max(1e-9, radius))));
      const azimuth = Math.atan2(y, z);
      expect(radius).toBeGreaterThanOrEqual(domain.obstacle.radiusAt(theta, azimuth) - 1e-3);
    }
    geometry.dispose();
  });

});

describe("BATS-R-US projected bulk-flow tracers", () => {
  it("samples supplied model paths and their local speed instead of inventing a volumetric trajectory", () => {
    const flow = projectedFlow([[600, 0], [700, 0], [800, 0]], [2000, 4000, 6000]);
    const visual = createSolarWindVisual({
      modelFlow: { definition, projectedFlowStreamlines: { equatorial: flow } },
      tracersPerModelPath: 1,
      maximumModelSegmentRe: 2,
      modelSecondsPerDisplaySecond: 1,
    });
    expect(visual.mode).toBe("model-projected");
    // The plane tracers ride in their own set; the 3-D illustrative cloud
    // stays drawn beside them so the layer reads as a wind from every angle.
    expect(visual.modelPoints.geometry.userData.kind).toBe("bats-r-us-projected-bulk-flow");
    expect(visual.points.geometry.userData.kind).toBe("physics-based-teaching-solar-wind-tracers");
    expect(visual.group.userData.labeling).toMatchObject({
      classification: "model-projected plane tracers inside an illustrative 3-D deflection cloud",
      not: "observed individual trajectories",
      cadenceDriver: "BATS-R-US local bulk-flow speed on the two published cuts",
    });

    // Halfway through the first 1 Re segment at its 300 km/s average speed.
    visual.update((6371 / 300) / 2);
    const position = visual.modelPoints.geometry.getAttribute("position");
    const speed = visual.modelPoints.geometry.getAttribute("modelSpeedKps");
    expect(position.getX(0)).toBeCloseTo(6.5, 4);
    expect(position.getY(0)).toBeCloseTo(0, 4);
    expect(speed.getX(0)).toBeCloseTo(300, 4);
    visual.dispose();
  });

  it("rejects a model chord through Earth and falls back to labeled teaching flow around the obstacle", () => {
    const crossing = projectedFlow([[-300, 0], [300, 0]], [4000, 4000]);
    const visual = createSolarWindVisual({
      modelFlow: { definition, projectedFlowStreamlines: { meridional: crossing } },
      maximumModelSegmentRe: 10,
      magnetopauseStandoffRe: 8,
      magnetopauseGapRe: 1,
      upstreamStartRe: 20,
    });
    expect(visual.mode).toBe("illustrative-upstream");
    visual.setConditions(550, 8);
    visual.update(10_000);
    const x = [...visual.points.geometry.getAttribute("gsmXRe").array];
    const y = visual.points.geometry.getAttribute("gsmYRe");
    const z = visual.points.geometry.getAttribute("gsmZRe");
    const obstacleRadius = visual.points.geometry.userData.domain.obstacleRadiusRe as number;
    expect(Math.min(...x)).toBeLessThan(0);
    for (let index = 0; index < x.length; index += 1) {
      expect(Math.hypot(x[index]!, y.getX(index), z.getX(index)))
        .toBeGreaterThanOrEqual(obstacleRadius - 1e-4);
    }
    expect(visual.group.userData.visualMode).toBe("illustrative-upstream");
    expect(visual.group.userData.labeling).toMatchObject({
      classification: "physics-based teaching tracers",
      not: "observed individual trajectories",
      cadenceDriver: "measured upstream bulk speed",
      populationDriver: "measured upstream proton density",
      approximation: "idealized no-penetration potential flow—not an MHD solution",
    });
    expect(visual.group.userData.currentDrivers).toEqual({ speedKps: 550, densityCm3: 8 });
    visual.dispose();
  });
});

describe("GOES X-ray irradiance view", () => {
  it("maps the 0.1-0.8 nm flux logarithmically to standard class and direct intensity", () => {
    expect(goesXrayClass(1e-8)).toBe("A1.0");
    expect(goesXrayClass(1e-7)).toBe("B1.0");
    expect(goesXrayClass(1e-6)).toBe("C1.0");
    expect(goesXrayClass(5e-5)).toBe("M5.0");
    expect(goesXrayClass(2e-4)).toBe("X2.0");
    expect(goesXrayClass(null)).toBe("—");
    const background = xrayIrradianceEncoding(1e-8);   // A1
    const quiet = xrayIrradianceEncoding(1e-7);        // B1
    const moderate = xrayIrradianceEncoding(1e-5);     // M1
    const flare = xrayIrradianceEncoding(1e-4);        // X1
    const major = xrayIrradianceEncoding(1e-3);        // X10
    expect(flare.normalizedFlux).toBeGreaterThan(quiet.normalizedFlux);

    // Sean's requirement, as a number: the tint has to track the class hard
    // enough that A is barely there and X is alarming. The shipped build ran
    // 0.22 at A1 to 0.56 at X10 — a factor of two and a half across five
    // decades of flux — and read as "the globe got slightly brighter".
    const opacities = [background, quiet, moderate, flare, major].map((e) => e.exposureOpacity);
    for (let index = 1; index < opacities.length; index += 1) {
      expect(opacities[index]!).toBeGreaterThan(opacities[index - 1]!);
    }
    expect(background.exposureOpacity).toBeLessThan(0.2);
    expect(major.exposureOpacity).toBeGreaterThan(0.8);
    expect(major.exposureOpacity / background.exposureOpacity).toBeGreaterThan(6);

    // Which hemisphere faces the Sun is geometry, not flux, so the terminator
    // stays legible at every class. It is what keeps the layer readable on a
    // quiet Sun, and it is why the tint itself is allowed to go faint.
    expect(background.terminatorOpacity).toBeGreaterThan(0.4);
    expect(major.terminatorOpacity).toBeGreaterThan(background.terminatorOpacity);

    // Flare state, from the class letter alone.
    expect(background.activityState).toBe("background");
    expect(moderate.activityState).toBe("flare");
    expect(flare.activityState).toBe("major-flare");

    expect(xrayIrradianceEncoding(null).exposureOpacity).toBe(0);
    expect(xrayIrradianceEncoding(null).terminatorOpacity).toBe(0);
    expect(xrayIrradianceEncoding(null).activityState).toBe("none");
    expect(xrayIrradianceEncoding(null).available).toBe(false);
    expect(XRAY_FLUX_GRADIENT_CSS).toContain("linear-gradient");
  });

  it("constructs only a dayside exposure shell — the one true spatial structure a uniform scalar has", () => {
    const radius = 104;
    const geometry = createDaysideExposureGeometry(radius, 6, 12);
    const positions = geometry.getAttribute("position");
    const weights = geometry.getAttribute("exposureWeight");
    for (let index = 0; index < positions.count; index += 1) {
      expect(positions.getX(index)).toBeGreaterThanOrEqual(0);
      expect(Math.hypot(positions.getX(index), positions.getY(index), positions.getZ(index)))
        .toBeCloseTo(radius, 4);
      expect(weights.getX(index)).toBeGreaterThanOrEqual(0);
      expect(weights.getX(index)).toBeLessThanOrEqual(1);
    }
    const xValues: number[] = [];
    for (let index = 0; index < positions.count; index += 1) xValues.push(positions.getX(index));
    expect(Math.min(...xValues)).toBe(0);
    geometry.dispose();
  });

  it("draws the exposure tint and the inbound beam, both driven by the measured flux", () => {
    const visual = createXrayIrradianceVisual({ earthRadius: 100, upperAtmosphereRadius: 104 });
    // Two objects, and only two: the sunlit-hemisphere tint and the inbound
    // beam. Nothing else about a single scalar is drawable.
    expect(visual.group.children).toEqual([visual.glow, visual.streaks]);

    const flare = visual.setFlux(1e-4);
    const flareOpacity = visual.glowMaterial.uniforms.opacity!.value as number;
    const flareColor = (visual.glowMaterial.uniforms.color!.value as THREE.Color).clone();
    const quiet = visual.setFlux(1e-7);
    const quietOpacity = visual.glowMaterial.uniforms.opacity!.value as number;
    const quietColor = (visual.glowMaterial.uniforms.color!.value as THREE.Color).clone();
    expect(flare.className).toBe("X1.0");
    expect(quiet.className).toBe("B1.0");
    expect(quietOpacity).toBeLessThan(flareOpacity);
    // The colour moves up the A-to-X ramp too, so a flare does not merely get
    // brighter in the globe's own cyan: it goes warm and then red.
    expect(flareColor.r).toBeGreaterThan(quietColor.r * 2);
    expect(flareColor.r).toBeGreaterThan(flareColor.b);
    expect(quietColor.b).toBeGreaterThan(quietColor.r);
    // Three separable terms, each keyed to something real. cos(solar zenith
    // angle) unflattened is what concentrates the tint at the sub-solar point
    // instead of washing the whole disc; the exposure geometry used to be
    // pow(cos, 0.55), which is why a camera looking near the sub-solar point
    // saw a uniform veil with no edge anywhere and read it as nothing.
    expect(visual.glowMaterial.fragmentShader).toContain("float dayside = clamp(incidentWeight, 0.0, 1.0);");
    expect(visual.glowMaterial.fragmentShader).not.toContain("pow(clamp(incidentWeight, 0.0, 1.0), 0.55)");
    expect(visual.glowMaterial.fragmentShader).toContain("float terminator = exp(-pow(dayside / 0.075, 2.0));");
    expect(visual.glowMaterial.uniforms.terminatorOpacity!.value).toBeGreaterThan(0.4);
    expect(visual.group.userData.labeling).toMatchObject({
      classification: "day/night exposure tint — geometry, not a photon track",
      intensityDriver: "GOES XRS 0.1-0.8 nm irradiance",
    });
    expect(visual.group.userData.currentFluxWm2).toBe(1e-7);
    // Geometry, not a screen-space glyph, so pixel ratio has nothing to scale.
    expect(() => visual.setPixelRatio(1.75)).not.toThrow();
    expect(() => visual.update(9_999)).not.toThrow();
    expect(visual.glowMaterial.uniforms.opacity!.value).toBe(quietOpacity);

    visual.setFlux(null);
    expect(visual.glow.visible).toBe(false);
    expect(visual.glowMaterial.uniforms.opacity!.value).toBe(0);
    expect(SOLAR_INPUT_VISUAL_METHOD.xray.limitation).toContain("does not deflect X-rays");
    visual.dispose();
  });
});

/**
 * ## The inbound beam
 *
 * Sean, on the live layer: "Can't we at least get some inbound x-ray photon
 * animations in that? ... It would be good since users would see that they
 * don't deflect like the solar wind and IMF."
 *
 * Four properties carry that lesson, and each is pinned here: the beam is
 * straight and parallel (also checked against a storm driver in
 * `tests/solar-wind-boundary.test.ts`), it ends by absorption on the dayside
 * and nowhere else, its population is the measured flux, and it freezes when
 * the visitor turns environmental motion off rather than vanishing.
 */
describe("X-ray inbound photon beam", () => {
  /** The globe's own GSM mapping, so the beam is measured on the shipped ruler. */
  const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
    const physicalRadius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
    const scale = sharedDisplayRadius(physicalRadius, 100) / physicalRadius;
    return new THREE.Vector3(xRe, zRe, yRe === 0 ? 0 : -yRe).multiplyScalar(scale);
  };

  const beamVisual = (options: Record<string, unknown> = {}) => createXrayIrradianceVisual({
    earthRadius: 100,
    upperAtmosphereRadius: 103.5,
    positionForGsm,
    photonUpstreamStartRe: 34,
    photonRayCount: 240,
    seed: 20260809,
    ...options,
  });

  it("ends every ray by absorption on the dayside shell — never the night side, never wrapped", () => {
    const visual = beamVisual();
    visual.setFlux(3e-5);
    const entryX = sharedDisplayRadius(34, 100);
    for (const ray of visual.photonRays) {
      const radius = Math.hypot(ray.absorption.x, ray.absorption.y, ray.absorption.z);
      // The absorption point is ON the shell the exposure tint paints.
      expect(radius).toBeCloseTo(103.5, 6);
      // And on its sunward side: x >= 0 with no exception, so no ray can end
      // past the terminator or carry on into the shadow.
      expect(ray.absorption.x).toBeGreaterThanOrEqual(0);
      expect(ray.incidenceCosine).toBeGreaterThanOrEqual(0);
      expect(ray.incidenceCosine).toBeLessThanOrEqual(1);
      // Nothing on the way in is ever inside the shell either: the head's
      // radius falls monotonically to the shell and stops there.
      for (let step = 0; step <= 50; step += 1) {
        const head = xrayPhotonRayHead(ray, entryX, step / 50);
        expect(Math.hypot(head.x, head.y, head.z)).toBeGreaterThanOrEqual(103.5 - 1e-9);
        expect(head.x).toBeGreaterThanOrEqual(0);
      }
    }
    // The same guarantee read back out of the buffer the renderer draws, so a
    // change made in update() alone cannot slip past the geometry check above.
    const positions = visual.streaks.geometry.getAttribute("position") as THREE.BufferAttribute;
    for (let step = 0; step <= 30; step += 1) {
      visual.update(step * 0.03);
      for (let index = 0; index < visual.drawnRayCount; index += 1) {
        const x = positions.getX(index * 2);
        const y = positions.getY(index * 2);
        const z = positions.getZ(index * 2);
        expect(x).toBeGreaterThanOrEqual(0);
        expect(Math.hypot(x, y, z)).toBeGreaterThanOrEqual(103.5 - 1e-3);
      }
    }
    expect(visual.streaks.geometry.userData.termination).toContain("never the night side");
    visual.dispose();
  });

  it("scales the drawn population and brightness with the measured flux, monotonically", () => {
    const visual = beamVisual();
    const classes = [1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3]; // A1 B1 C1 M1 X1 X10
    const counts: number[] = [];
    const opacities: number[] = [];
    for (const flux of classes) {
      const encoding = visual.setFlux(flux);
      counts.push(visual.drawnRayCount);
      opacities.push(visual.streakMaterial.uniforms.opacity!.value as number);
      expect(encoding.photonRayFraction).toBeGreaterThan(0);
    }
    for (let index = 1; index < counts.length; index += 1) {
      expect(counts[index]!).toBeGreaterThan(counts[index - 1]!);
      expect(opacities[index]!).toBeGreaterThan(opacities[index - 1]!);
    }
    // Quiet sun sparse, X-class a shower: the ends of the range have to be
    // tellable apart at a glance, not merely ordered.
    expect(counts.at(-1)!).toBeGreaterThan(counts[0]! * 8);
    expect(visual.group.userData.inboundRayCount).toBe(counts.at(-1));

    // No data, no beam. A placeholder shower from an invented flux is the
    // exact failure the layer's visibility contract exists to prevent.
    visual.setFlux(null);
    expect(visual.streaks.visible).toBe(false);
    expect(visual.drawnRayCount).toBe(0);
    expect(visual.streakMaterial.uniforms.opacity!.value).toBe(0);
    visual.dispose();
  });

  it("freezes where it is when environmental motion stops, and outruns the wind when it does not", () => {
    const visual = beamVisual();
    visual.setFlux(1e-5);
    const positions = visual.streaks.geometry.getAttribute("position") as THREE.BufferAttribute;
    const snapshot = () => Array.from(positions.array as Float32Array);

    // The renderer hands this its accumulated motion clock. Off means the
    // clock stops, so the same argument arrives every frame: the picture must
    // be identical, and it must still be a picture — a laid-out beam, not an
    // empty buffer collapsed on the origin.
    visual.update(4.5);
    const frozen = snapshot();
    visual.update(4.5);
    expect(snapshot()).toEqual(frozen);
    expect(frozen.some((value) => Math.abs(value) > 1)).toBe(true);
    visual.update(4.62);
    expect(snapshot()).not.toEqual(frozen);

    // And the speed contrast, measured the way the eye measures it: scene
    // units travelled per display second, against the wind's own tracers on
    // the same mapper. Light versus ~400 km/s is 750x and unwatchable; what
    // has to survive is that the photons visibly outpace the particles.
    const wind = createSolarWindVisual({
      earthRadiusRe: 1,
      magnetopauseStandoffRe: 9.5,
      positionForGsm,
      particleCount: 400,
      trailLength: 20,
      seed: 20260809,
    });
    wind.setConditions(420, 6.2);
    const windPositions = wind.points.geometry.getAttribute("position") as THREE.BufferAttribute;
    const displacement = (attribute: THREE.BufferAttribute, stride: number, before: Float32Array) => {
      const moves: number[] = [];
      for (let index = 0; index < attribute.count; index += stride) {
        const offset = index * 3;
        moves.push(Math.hypot(
          attribute.getX(index) - before[offset]!,
          attribute.getY(index) - before[offset + 1]!,
          attribute.getZ(index) - before[offset + 2]!,
        ));
      }
      moves.sort((a, b) => a - b);
      return moves[Math.floor(moves.length / 2)]!;
    };
    const step = 0.02;
    wind.update(3);
    const windBefore = Float32Array.from(windPositions.array as Float32Array);
    wind.update(3 + step);
    const windMove = displacement(windPositions, 1, windBefore);
    visual.update(3);
    const beamBefore = Float32Array.from(positions.array as Float32Array);
    visual.update(3 + step);
    // Stride 2 so only the streak heads are compared, not their tails.
    const beamMove = displacement(positions, 2, beamBefore);
    expect(windMove).toBeGreaterThan(0);
    expect(beamMove / windMove).toBeGreaterThan(3);

    wind.dispose();
    visual.dispose();
  });

  it("enters at a distance the shared radial mapping owns, and states its display choice", () => {
    const visual = beamVisual();
    visual.setFlux(1e-5);
    const positions = visual.streaks.geometry.getAttribute("position") as THREE.BufferAttribute;
    let farthest = 0;
    for (let step = 0; step < 40; step += 1) {
      visual.update(step * 0.02);
      for (let index = 0; index < visual.drawnRayCount; index += 1) {
        farthest = Math.max(farthest, positions.getX(index * 2));
      }
    }
    // The entry point is the ruler's answer for 34 Re — not a number this
    // module invented — so a change to the scene's distance scale carries it.
    expect(farthest).toBeGreaterThan(sharedDisplayRadius(34, 100) * 0.98);
    expect(farthest).toBeLessThanOrEqual(sharedDisplayRadius(34, 100) + 1e-6);
    // Beyond the bow shock nose, so a ray is already crossing the boundary
    // system when it first appears.
    expect(sharedDisplayRadius(34, 100)).toBeGreaterThan(sharedDisplayRadius(13, 100));
    expect(visual.streaks.geometry.userData.encoding).toContain("display cadence");
    expect(SOLAR_INPUT_VISUAL_METHOD.xray.photons).toContain("absorbed");
    visual.dispose();
  });
});
