/**
 * Browser-side half of the Dungey-cycle coupling verification.
 *
 * Instantiates the production globe, drives it from a chosen upstream IMF, and
 * switches the four layers on in the order a reader would: solar wind alone,
 * plus the magnetosphere, plus the plasma sheet, plus the auroral oval. The
 * spec screenshots each stage at a strongly southward IMF and at a northward
 * one, so the difference the MEASURED coupling function makes is visible in
 * pixels rather than asserted in prose.
 *
 * The drivers here are chosen rather than fetched, deliberately: the published
 * record for any particular afternoon may hold no strongly southward hour at
 * all, and the thing under test is that the picture follows the number. The
 * number itself is computed by the site's own `newellCoupling`, and placed on
 * the ladder the pipeline publishes, exactly as `main.ts` does it.
 */
import * as THREE from "three";
import { SpaceGlobe } from "../src/globe";
import { shueBoundary } from "../src/magnetopause";
import { newellCoupling } from "../src/storm-indices";
import { couplingDrive } from "../src/dungey-transport";
import { LOADING_REFERENCE_NT_MINUTES } from "../src/substorm-chain";
import type { SubstormState } from "../src/substorm-chain";
import type { MagnetopauseDriverSample } from "../src/environment-time";
import type { SatelliteRecord } from "../src/types";

/** The ladder `pipeline/storm_indices.py` publishes with the storm artifact. */
const NEWELL_CALIBRATION = [
  { label: "very quiet", value: 0 },
  { label: "quiet", value: 4773 },
  { label: "moderate", value: 10123 },
  { label: "storm", value: 27421 },
  { label: "severe", value: 60036 },
  { label: "extreme", value: 153333 },
];

export type CouplingStage = "wind" | "magnetosphere" | "plasma-sheet" | "aurora";

/** Where the camera stands. `north` looks down on the equatorial plane; `tail` looks up it from behind. */
export type ViewStation = "dusk" | "north" | "tail";

declare global {
  interface Window {
    __ready: boolean;
    __apply: (options: {
      bzGsmNt: number;
      byNt: number;
      speedKps: number;
      densityCm3: number;
      stage: CouplingStage;
      drivers?: boolean;
      distanceScene?: number;
      targetXRe?: number;
      /** Switch the Solar wind & IMF layer itself off, for the modifier invariant. */
      wind?: boolean;
      /**
       * The empirical boundary annotation (`annotate-empirical-boundaries`).
       *
       * OFF by default, which is the site's own default and is why it appears
       * in none of the stage captures. Kept switchable because "the boundary
       * is missing at northward Bz" is a question that can only be answered by
       * drawing it in both states.
       */
      boundary?: boolean;
      /** Where the camera stands; `north` puts dusk and dawn on opposite sides of the frame. */
      viewFrom?: ViewStation;
    }) => Record<string, unknown>;
    __measureFps: (frames?: number) => Promise<number>;
    __measureUpdateMs: (iterations?: number) => number;
    __renderInfo: () => Record<string, number>;
    __paintSpecies: (scheme: { proton: string; alpha: string; electron: string }) => number;
    /** Every named object in the sun-fixed frame, with whether it is actually on screen. */
    /** Preview-only: force an even three-way species mix so a palette can be judged. */
    __previewEvenSpeciesMix: (on: boolean) => Record<string, number>;
    /** The drawn return paths, vertex by vertex, for plotting where a species goes. */
    __returnPathGeometry: () => Array<Record<string, unknown>>;
    /** Where each species actually ends up, read off the geometry it rides. */
    __speciesRouting: () => Record<string, unknown>;
    __inventory: () => Array<Record<string, unknown>>;
    __counts: () => Record<string, unknown>;
    __lastError: string | null;
  }
}

window.__ready = false;
window.__lastError = null;

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites: [{ id: 1, name: "PROBE", ownerLabel: "None", mission: "other" } as unknown as SatelliteRecord],
  land: { features: [] },
  onSelect: () => {},
});
const internals = globe as unknown as Record<string, any>;

/**
 * The world-space extent of one named object, or null when it is not there.
 *
 * For answering "is that drawn" with a box rather than with an argument: a
 * thing can be present, visible, reachable and still be a different size and
 * in a different place than it was a moment ago.
 */
function measure(name: string): Record<string, unknown> | null {
  const root = internals.sunFrameGroup as THREE.Object3D;
  root.updateMatrixWorld(true);
  const found = root.getObjectByName(name);
  if (!found) return null;
  const box = new THREE.Box3().setFromObject(found);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  return {
    onScreen: onScreen(found),
    sizeX: Number(size.x.toFixed(1)),
    sizeY: Number(size.y.toFixed(1)),
    sizeZ: Number(size.z.toFixed(1)),
    centreX: Number(centre.x.toFixed(1)),
    centreY: Number(centre.y.toFixed(1)),
    centreZ: Number(centre.z.toFixed(1)),
  };
}

/** Visible, and every ancestor visible: what "on screen" actually means. */
function onScreen(object: THREE.Object3D | null | undefined): boolean {
  let node: THREE.Object3D | null = object ?? null;
  while (node) {
    if (!node.visible) return false;
    node = node.parent;
  }
  return true;
}

/** A fixed instant, so the dipole tilt is the same in every capture. */
const AT = new Date("2026-03-20T06:00:00Z");

function driverFor(speedKps: number, densityCm3: number, byNt: number, bzGsmNt: number): MagnetopauseDriverSample {
  const dynamicPressureNpa = 1.6726e-6 * densityCm3 * speedKps * speedKps;
  const shue = shueBoundary(dynamicPressureNpa, bzGsmNt)!;
  const btNt = Math.hypot(byNt, bzGsmNt);
  return {
    validAt: AT.toISOString(),
    observedAt: AT.toISOString(),
    speedKps,
    densityCm3,
    bzGsmNt,
    dynamicPressureNpa,
    subsolarStandoffRe: shue.subsolarStandoffRe,
    flaringAlpha: shue.flaringAlpha,
    byNt,
    btNt,
    magneticPressureNpa: (btNt * btNt) / (2 * 4 * Math.PI * 1e-7) * 1e-18 * 1e9,
  };
}

/**
 * The measured substorm state the plasma-sheet layer would have at this Bz.
 *
 * `onsetEvidence: "none"` and `injection: 0` on purpose: that is what the live
 * site has, because no auroral-electrojet index reaches the live timeline. The
 * loading is the honest one — the southward-Bz integral over the standard
 * window, at this Bz held steady.
 */
function substormFor(bzGsmNt: number): SubstormState {
  const southwardBzNtMinutes = Math.max(0, -bzGsmNt) * 90;
  return {
    phase: southwardBzNtMinutes / LOADING_REFERENCE_NT_MINUTES >= 0.35 ? "growth" : "quiet",
    loading: Math.min(1, southwardBzNtMinutes / LOADING_REFERENCE_NT_MINUTES),
    injection: 0,
    onset: null,
    minutesSinceOnset: null,
    onsetEvidence: "none",
    southwardBzNtMinutes,
    bzGsmNt,
  };
}

function frameTail(distanceScene = 950, targetXRe = -9, viewFrom: ViewStation = "dusk") {
  internals.cameraDolly = null;
  internals.sunFrameGroup.updateMatrixWorld(true);
  const quaternion = internals.sunFrameGroup.quaternion as THREE.Quaternion;
  // Scene directions of the GSM axes, through the same swizzle the mapper
  // uses (scene Y is GSM Z, scene -Z is GSM Y).
  const north = new THREE.Vector3(0, 1, 0).applyQuaternion(quaternion).normalize();
  const sunward = new THREE.Vector3(1, 0, 0).applyQuaternion(quaternion).normalize();
  const dusk = new THREE.Vector3().crossVectors(north, sunward).normalize();
  // Looking in from dusk and a little above: the noon-midnight meridian is
  // across the frame, so the cusps, the lobes, the tail and the oval are all
  // in one view. The camera is pushed off the Sun-Earth line so the tail is
  // not foreshortened onto the planet.
  //
  // From "north" instead, the equatorial plane is the frame and the camera
  // looks straight down the dipole axis. That is the only station from which
  // the drift split is a SCREEN direction rather than depth: dusk and dawn are
  // opposite sides of the picture, so a westward ion and an eastward electron
  // leaving the same injection are seen going opposite ways. From "dusk" they
  // separate toward and away from the lens and the split cannot be screenshot.
  //
  // From "tail" the camera stands down-tail of the injection and looks back up
  // the tail toward the Sun, tilted a little north. This is the station the
  // textbooks draw the ring current from: the westward and eastward branches
  // leave the same injection and fan out to opposite SIDES of the frame, and
  // Earth does not stand between the camera and either of them.
  const direction = viewFrom === "north"
    ? north.clone().multiplyScalar(1).add(sunward.clone().multiplyScalar(0.06))
    : viewFrom === "tail"
      ? sunward.clone().multiplyScalar(-1).add(north.clone().multiplyScalar(0.30))
      : dusk.clone().multiplyScalar(1)
      .add(north.clone().multiplyScalar(0.42))
      .add(sunward.clone().multiplyScalar(0.22));
  const target = internals.modelGsmPosition(targetXRe, 0, 0) as THREE.Vector3;
  internals.controls.target.copy(target);
  internals.camera.position.copy(target.clone().add(direction.normalize().multiplyScalar(distanceScene)));
  // Looking down the dipole axis, "up" cannot also be the dipole axis.
  internals.camera.up.copy(viewFrom === "north" ? sunward : north);
  internals.controls.update();
}

window.__apply = ({ bzGsmNt, byNt, speedKps, densityCm3, stage, drivers = true, distanceScene, targetXRe, wind = true, boundary = false, viewFrom = "dusk" }) => {
  globe.setSimulationTime(AT);
  const driver = drivers ? driverFor(speedKps, densityCm3, byNt, bzGsmNt) : null;
  globe.setSolarWindConditions(driver?.speedKps ?? null, driver?.densityCm3 ?? null);
  const coupling = driver ? newellCoupling(driver.speedKps, driver.byNt, driver.bzGsmNt) : null;
  const drive = couplingDrive(coupling, NEWELL_CALIBRATION);
  globe.setDungeyCouplingDrive(drive);
  globe.setMagnetopause(driver);
  globe.setSubstormState(driver ? substormFor(bzGsmNt) : null);

  // The particles belong to the Solar wind & IMF layer and to nothing else.
  // Every other layer here is a MODIFIER of how they move.
  globe.setLayer("solarWind", wind);
  globe.setLayer("geospace", stage !== "wind");
  globe.setLayer("ringCurrent", stage === "plasma-sheet" || stage === "aurora");
  globe.setLayer("aurora", stage === "aurora");
  globe.setLayer("magnetosphere", boundary && stage !== "wind");
  frameTail(distanceScene, targetXRe, viewFrom);
  return {
    coupling,
    drive,
    subsolarStandoffRe: driver?.subsolarStandoffRe ?? null,
    flaringAlpha: driver?.flaringAlpha ?? null,
    dynamicPressureNpa: driver?.dynamicPressureNpa ?? null,
    cuspFunnel: measure("field-line-context-exterior-cusp"),
    plasmaSheet: measure("inner-plasma-sheet-wedge"),
    ...window.__counts(),
  };
};

window.__counts = () => {
  const visual = internals.solarWindVisual;
  const guidance = visual.guidedPoints.geometry.userData.guidance ?? {};
  const paths = visual.guidancePaths as Array<Record<string, unknown>>;
  const alpha = visual.guidedPoints.geometry.getAttribute("flowAlpha");
  const tracers = (visual as any).guidedTracers as Array<{ pathIndex: number }>;
  let visible = 0;
  let returnTracers = 0;
  let visibleReturnTracers = 0;
  for (let index = 0; index < (alpha?.count ?? 0); index += 1) {
    const lit = alpha.getX(index) > 0.01;
    if (lit) visible += 1;
    if (paths[tracers[index]?.pathIndex ?? 0]?.role === "return") {
      returnTracers += 1;
      if (lit) visibleReturnTracers += 1;
    }
  }
  return {
    guidance,
    pathCount: paths.length,
    returnPaths: paths.filter((path) => path.role === "return").length,
    tracerCount: alpha?.count ?? 0,
    visibleTracers: visible,
    returnTracers,
    visibleReturnTracers,
    guidedVisible: visual.guidedPoints.visible === true,
    // Is ANY wind particle actually reachable on screen? Walks up the scene
    // graph, because a visible Points inside a hidden group draws nothing —
    // and the invariant is about what a reader sees, not about a flag.
    windOnScreen: onScreen(visual.guidedPoints) || onScreen(visual.points),
    couplingDrive: visual.couplingDrive,
    tailReturnReport: visual.tailReturnReport,
  };
};

/**
 * The JS cost this work actually adds, isolated from the renderer.
 *
 * The GPU figure on this box is meaningless — WSL Chromium runs WebGL in
 * software at 5-8 fps whatever is on screen — so the honest measurement of the
 * added cost is the per-frame CPU work in `SolarWindVisual.update`, which is
 * what would run on a phone as well.
 */
window.__measureUpdateMs = (iterations = 300) => {
  const visual = internals.solarWindVisual;
  // Warm up, so the first-call deoptimisation is not the measurement.
  for (let index = 0; index < 30; index += 1) visual.update(index * 0.016);
  const started = performance.now();
  for (let index = 0; index < iterations; index += 1) visual.update(index * 0.016);
  return (performance.now() - started) / iterations;
};

/**
 * Repaint the three species colours at runtime, for previewing a candidate
 * palette without editing the source. Verification hook only: the shipped
 * colours live in `SOLAR_WIND_SPECIES_PRESENTATION`.
 */
window.__paintSpecies = (scheme: { proton: string; alpha: string; electron: string }) => {
  const visual = internals.solarWindVisual;
  const materials = [visual.material, visual.trailMaterial, visual.guidedMaterial, visual.guidedTrailMaterial];
  for (const material of materials) {
    (material.uniforms.protonColor.value as THREE.Color).set(scheme.proton);
    (material.uniforms.alphaColor.value as THREE.Color).set(scheme.alpha);
    (material.uniforms.electronColor.value as THREE.Color).set(scheme.electron);
  }
  return materials.length;
};

/**
 * Preview-only: force an even three-way species mix.
 *
 * He2+ alphas are the assumed ~4% of the ions, which works out at about 1.9%
 * of everything drawn - so a crop holding forty particles holds, on average,
 * less than one alpha, and a palette candidate for the alpha cannot be judged
 * from an ordinary frame at all. This rewrites the `species` attribute to
 * index % 3 so all three are equally represented, purely so a colour can be
 * looked at. It is never the shipped mix: the real one comes from
 * `solarWindSpeciesMix()` and the measured density, and calling this with
 * `false` puts the geometry's own assignment back.
 */
window.__previewEvenSpeciesMix = (on: boolean) => {
  const visual = internals.solarWindVisual;
  const geometries = [
    visual.points.geometry,
    visual.guidedPoints.geometry,
    visual.trails.geometry,
    visual.guidedTrails.geometry,
  ].filter((geometry: any) => geometry?.getAttribute("species"));
  const counts: Record<string, number> = { geometries: geometries.length, rewritten: 0 };
  for (const geometry of geometries) {
    const attribute = geometry.getAttribute("species");
    const original = (geometry.userData.speciesOriginal ??= Float32Array.from(attribute.array as Float32Array));
    // A streak geometry carries two vertices per tracer and both must agree,
    // or one streak is drawn as two half-species.
    const perTracer = geometry.getAttribute("trailFade") ? 2 : 1;
    for (let index = 0; index < attribute.count; index += 1) {
      attribute.setX(index, on ? Math.floor(index / perTracer) % 3 : original[index]!);
    }
    attribute.needsUpdate = true;
    counts.rewritten += attribute.count;
  }
  return counts;
};

/**
 * Where each species actually ends up.
 *
 * The routing claim - positive ions drift west toward dusk, electrons east
 * toward dawn - is a claim about geometry, so it is read off the geometry
 * rather than asserted. For every guided tracer on a return path: its species,
 * the drift sense of the path it rides, the branch, and the GSM y of the last
 * vertex of that path. Positive GSM y is dusk, negative is dawn.
 */
window.__speciesRouting = () => {
  const visual = internals.solarWindVisual;
  const paths = visual.guidancePaths as Array<Record<string, any>>;
  const tracers = (visual as any).guidedTracers as Array<{ pathIndex: number; species: string }>;
  const alpha = visual.guidedPoints.geometry.getAttribute("flowAlpha");
  const rows: Record<string, any> = {};
  for (let index = 0; index < tracers.length; index += 1) {
    const tracer = tracers[index]!;
    const path = paths[tracer.pathIndex];
    if (!path || path.role !== "return") continue;
    const row = (rows[tracer.species] ??= {
      tracers: 0, lit: 0, westward: 0, eastward: 0, branches: {}, endY: [] as number[],
      endYByBranch: {} as Record<string, number[]>,
    });
    row.tracers += 1;
    if ((alpha?.getX(index) ?? 0) > 0.01) row.lit += 1;
    row[path.driftSense] += 1;
    row.branches[path.branch] = (row.branches[path.branch] ?? 0) + 1;
    row.endY.push(path.pointsGsmRe.at(-1).y as number);
    // Kept per branch as well, because the plain dusk/dawn tally over ALL of a
    // species' paths is not the routing answer. The aurora branch does not
    // drift anywhere: it ends at its footpoint, within a fifth of an Earth
    // radius of the noon-midnight meridian, and roughly half of those land at
    // y just above zero. Counted flat, that reads as "66 electrons went to
    // dusk", which is false. The drift question is only about the
    // ring-current branch.
    (row.endYByBranch[path.branch] ??= []).push(path.pointsGsmRe.at(-1).y as number);
  }
  const summary: Record<string, unknown> = {};
  for (const [species, row] of Object.entries<any>(rows)) {
    const ys = row.endY as number[];
    const mean = ys.reduce((sum: number, y: number) => sum + y, 0) / Math.max(1, ys.length);
    summary[species] = {
      tracers: row.tracers,
      lit: row.lit,
      westward: row.westward,
      eastward: row.eastward,
      branches: row.branches,
      meanEndYRe: Number(mean.toFixed(2)),
      minEndYRe: Number(Math.min(...ys).toFixed(2)),
      maxEndYRe: Number(Math.max(...ys).toFixed(2)),
      endsDuskward: ys.filter((y: number) => y > 0).length,
      endsDawnward: ys.filter((y: number) => y < 0).length,
      // The two numbers the drift claim actually rests on, plus the branch
      // that leaves the equatorial plane entirely.
      driftEndsDuskward: (row.endYByBranch["ring-current"] ?? []).filter((y: number) => y > 0).length,
      driftEndsDawnward: (row.endYByBranch["ring-current"] ?? []).filter((y: number) => y < 0).length,
      precipitatesToTheOval: (row.endYByBranch["aurora"] ?? []).length,
    };
  }
  return summary;
};

/**
 * The return paths as drawn, vertex by vertex.
 *
 * "Ions end up at dusk and electrons at dawn" is a claim about a drawing, so
 * the drawing is handed over and plotted rather than described. Each entry is
 * one path the layer put in the scene this instant: which species are allowed
 * on it, which way it drifts, which branch it is, where the schematic half
 * starts, and every GSM vertex.
 */
window.__returnPathGeometry = () => {
  const visual = internals.solarWindVisual;
  const paths = visual.guidancePaths as Array<Record<string, any>>;
  return paths
    .filter((path) => path.role === "return")
    .map((path) => ({
      branch: path.branch,
      driftSense: path.driftSense,
      speciesFilter: path.speciesFilter,
      hemisphere: path.hemisphere,
      schematicFromIndex: path.schematicFromIndex,
      footpointLatitudeDeg: path.footpointLatitudeDeg,
      points: (path.pointsGsmRe as Array<{ x: number; y: number; z: number }>)
        .map((point) => [Number(point.x.toFixed(3)), Number(point.y.toFixed(3)), Number(point.z.toFixed(3))]),
    }));
};

window.__renderInfo = () => {
  const info = internals.renderer.info.render;
  return { calls: info.calls, triangles: info.triangles, lines: info.lines, points: info.points };
};

/**
 * What is actually in the scene, and reachable, right now.
 *
 * For answering "why is that not drawn" with a reading rather than with an
 * argument: name, visibility of the object AND of every ancestor, and how many
 * vertices it holds.
 */
window.__inventory = () => {
  const rows: Array<Record<string, unknown>> = [];
  (internals.sunFrameGroup as THREE.Object3D).traverse((node: THREE.Object3D) => {
    const geometry = (node as THREE.Mesh).geometry as THREE.BufferGeometry | undefined;
    const vertices = geometry?.getAttribute?.("position")?.count ?? 0;
    if (!node.name && vertices === 0) return;
    rows.push({
      name: node.name || node.type,
      type: node.type,
      visible: node.visible,
      onScreen: onScreen(node),
      vertices,
      userDataKind: (node.userData as Record<string, unknown>)?.kind
        ?? (node.userData as Record<string, unknown>)?.role
        ?? null,
    });
  });
  return rows;
};

window.__measureFps = (frames = 90) => new Promise<number>((resolve) => {
  let counted = 0;
  const started = performance.now();
  const tick = () => {
    counted += 1;
    if (counted >= frames) {
      resolve((counted * 1000) / (performance.now() - started));
      return;
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
});

try {
  window.__apply({ bzGsmNt: -12, byNt: 3, speedKps: 600, densityCm3: 8, stage: "aurora" });
  window.__ready = true;
} catch (error) {
  window.__lastError = String(error);
}
