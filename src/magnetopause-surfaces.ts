import * as THREE from "three";

import {
  type CuspedBoundaryDrivers,
  type MagnetopauseEvaluator,
  type MagnetopauseModelId,
  magnetopauseEvaluator,
  magnetopausePointGsm,
  nguyenBoundary,
  nguyenCuspProximity,
} from "./magnetopause";

/**
 * Meshes for the empirical magnetopause set, including the exterior cusp.
 *
 * `magnetopause.ts` owns the physics and knows nothing about three.js; this
 * module owns the geometry and knows no physics. The split matters because the
 * physics is testable without a renderer and the geometry is testable without
 * a browser.
 *
 * ## The one radial ruler
 *
 * Every position produced here goes through a caller-supplied
 * `positionForGsm(x, y, z)` mapper, and that mapper must be the **same** one
 * the satellites, the radiation belts and the SWMF cut planes already use.
 * The scene was put on a single radial ruler deliberately, so that "is this
 * spacecraft inside the magnetopause" is answerable by eye. Nothing in this
 * module may introduce a second scale: it emits physical Earth radii and lets
 * the scene's own ruler decide where that lands.
 *
 * ## What the shaded volume between the surfaces is
 *
 * Nguyen 2022 traces the magnetopause current sheet; Lin 2010 traces the cusp
 * inner boundary. Where the inner boundary genuinely lies inside the current
 * sheet, the volume between them is the **exterior cusp** — a real, published,
 * two-surface object rather than an invented dimple.
 *
 * The two surfaces are **not** nested. They are independent fits with
 * different subsolar scales, and away from the funnel Lin's surface generally
 * sits *outside* Nguyen's; on the noon-north meridian at 2 nPa the sign flips
 * near 25° and again near 68° solar zenith angle. So the shell is built only
 * where the difference is positive, which turns out to be two lobes straddling
 * the cusp axes near noon and nothing at all on the flanks. **That geometry is
 * decided by the models, not chosen for the picture** — and it is why shading
 * the whole gap and labelling all of it "cusp" would be an overclaim.
 *
 * Every vertex additionally carries a `cuspProximity` attribute: Nguyen's own
 * `C/2`, which is 1 on a cusp axis and decays to 1/e one angular width away.
 * It is a published quantity, not a cosmetic falloff invented for the render,
 * and it lets the shader make the funnel legible without inventing a boundary.
 */

export interface MagnetopauseSurfaceOptions {
  /** Scene mapper. Must be the scene's shared radial ruler. */
  positionForGsm: (xRe: number, yRe: number, zRe: number) => THREE.Vector3;
  /** Polar samples from the nose to the tail cutoff. */
  thetaSegments?: number;
  /** Azimuthal samples around the Sun-Earth line. */
  azimuthSegments?: number;
  /**
   * Where to stop the open boundary, as a solar zenith angle in radians.
   *
   * Both cusped models are fitted on the dayside and flanks and neither is a
   * tail model, so the default stops at 120 degrees rather than extrapolating
   * a surface the fit does not support.
   */
  maximumThetaRad?: number;
  /**
   * Where to *start* the surface, as a solar zenith angle in radians.
   *
   * Zero — the subsolar point — for every surface that is drawn whole. It
   * exists so the axisymmetric Shue surface can be drawn as the tail
   * continuation only, picking up where the two cusped fits stop rather than
   * being laid over the top of them. Drawing a smooth surface across the
   * dayside hides the thing the cusped models were added to show: the funnel is
   * an indentation, so it appears in the silhouette, and a smooth surface
   * outside it puts the silhouette back.
   */
  minimumThetaRad?: number;
}

const DEFAULTS = {
  thetaSegments: 96,
  azimuthSegments: 96,
  maximumThetaRad: (120 * Math.PI) / 180,
  minimumThetaRad: 0,
};

function resolve(options: MagnetopauseSurfaceOptions) {
  const thetaSegments = Math.max(8, Math.floor(options.thetaSegments ?? DEFAULTS.thetaSegments));
  const azimuthSegments = Math.max(8, Math.floor(options.azimuthSegments ?? DEFAULTS.azimuthSegments));
  const maximumThetaRad = Math.min(
    Math.PI - 1e-6,
    Math.max(0.1, options.maximumThetaRad ?? DEFAULTS.maximumThetaRad),
  );
  const minimumThetaRad = Math.min(
    maximumThetaRad - 1e-6,
    Math.max(0, options.minimumThetaRad ?? DEFAULTS.minimumThetaRad),
  );
  return { thetaSegments, azimuthSegments, maximumThetaRad, minimumThetaRad };
}

/**
 * A closed-in-azimuth quad grid over (theta, azimuth).
 *
 * Azimuth wraps, so the last column reuses the first column's vertices rather
 * than duplicating them at a seam; theta does not wrap.
 */
function gridIndices(thetaSegments: number, azimuthSegments: number, valid: Uint8Array) {
  const indices: number[] = [];
  for (let thetaIndex = 0; thetaIndex < thetaSegments; thetaIndex += 1) {
    for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
      const next = (azimuthIndex + 1) % azimuthSegments;
      const a = thetaIndex * azimuthSegments + azimuthIndex;
      const b = thetaIndex * azimuthSegments + next;
      const c = (thetaIndex + 1) * azimuthSegments + next;
      const d = (thetaIndex + 1) * azimuthSegments + azimuthIndex;
      // A vertex whose model radius was not finite leaves a hole rather than
      // being filled from its neighbours. The site's boundary layers already
      // work this way: an unsupported sector is a hole, not an interpolation.
      if (valid[a] && valid[b] && valid[c]) indices.push(a, b, c);
      if (valid[a] && valid[c] && valid[d]) indices.push(a, c, d);
    }
  }
  return indices;
}

export interface MagnetopauseSurfaceGeometry {
  geometry: THREE.BufferGeometry;
  /** Subsolar radius of the drawn surface, physical Re. */
  subsolarRe: number;
  /** Smallest and largest physical radius on the drawn surface, Re. */
  radiusRangeRe: [number, number];
}

/**
 * One boundary surface.
 *
 * Vertex attributes: `position` in scene units, `boundaryProgress` (0 at the
 * nose, 1 at the tail cutoff) for a tail fade, `physicalRadiusRe` so a shader
 * or a picker can recover the model value the vertex came from, and
 * `cuspProximity` for the cusped models.
 */
export function createMagnetopauseSurfaceGeometry(
  evaluator: MagnetopauseEvaluator,
  drivers: CuspedBoundaryDrivers,
  options: MagnetopauseSurfaceOptions,
): MagnetopauseSurfaceGeometry | null {
  const { thetaSegments, azimuthSegments, maximumThetaRad, minimumThetaRad } = resolve(options);
  const nguyen = evaluator.model.id === "shue1998" ? null : nguyenBoundary(drivers);
  const vertexCount = (thetaSegments + 1) * azimuthSegments;
  const positions = new Float32Array(vertexCount * 3);
  const boundaryProgress = new Float32Array(vertexCount);
  const physicalRadius = new Float32Array(vertexCount);
  const cuspProximity = new Float32Array(vertexCount);
  const valid = new Uint8Array(vertexCount);
  let minimumRe = Number.POSITIVE_INFINITY;
  let maximumRe = 0;

  for (let thetaIndex = 0; thetaIndex <= thetaSegments; thetaIndex += 1) {
    const progress = thetaIndex / thetaSegments;
    const theta = minimumThetaRad + progress * (maximumThetaRad - minimumThetaRad);
    for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
      const azimuth = (azimuthIndex / azimuthSegments) * Math.PI * 2;
      const index = thetaIndex * azimuthSegments + azimuthIndex;
      const point = magnetopausePointGsm(evaluator, theta, azimuth);
      if (!Number.isFinite(point.radiusRe)) continue;
      options.positionForGsm(point.xRe, point.yRe, point.zRe).toArray(positions, index * 3);
      boundaryProgress[index] = progress;
      physicalRadius[index] = point.radiusRe;
      cuspProximity[index] = nguyen ? nguyenCuspProximity(theta, azimuth, nguyen) : 0;
      valid[index] = 1;
      minimumRe = Math.min(minimumRe, point.radiusRe);
      maximumRe = Math.max(maximumRe, point.radiusRe);
    }
  }
  if (!Number.isFinite(minimumRe)) return null;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("boundaryProgress", new THREE.BufferAttribute(boundaryProgress, 1));
  geometry.setAttribute("physicalRadiusRe", new THREE.BufferAttribute(physicalRadius, 1));
  geometry.setAttribute("cuspProximity", new THREE.BufferAttribute(cuspProximity, 1));
  geometry.setIndex(gridIndices(thetaSegments, azimuthSegments, valid));
  geometry.computeVertexNormals();
  return {
    geometry,
    subsolarRe: evaluator.subsolarRe,
    radiusRangeRe: [minimumRe, maximumRe],
  };
}

export interface ExteriorCuspGeometry {
  geometry: THREE.BufferGeometry;
  /** Greatest thickness of the drawn funnel, Re. */
  cuspDepthRe: number;
  /** Where that greatest thickness sits, as a solar zenith angle in degrees. */
  cuspDepthThetaDeg: number;
  /**
   * Thickness on Nguyen's own cusp axis, Re.
   *
   * Deliberately reported separately, and it is smaller than `cuspDepthRe`.
   * The two models put their cusps at different solar zenith angles - Lin's
   * vertex sits several degrees equatorward of Nguyen's - so the funnel is at
   * its widest *between* the two axes rather than on either one. Quoting the
   * maximum as "the depth on the cusp axis" would be a small, easy overclaim.
   */
  depthOnNguyenAxisRe: number;
  /**
   * Median signed separation `r_Nguyen - r_Lin` well away from the cusp axes.
   *
   * Usually **negative**: the two fits have different subsolar scales, so away
   * from the funnel Lin's surface generally sits outside Nguyen's. It is
   * reported rather than hidden because it is the honest measure of how far
   * apart two published magnetopause models are when neither is claiming a
   * cusp.
   *
   * CORRECTNESS NOTE 2026-09-04: it is NOT always negative, and the sign flip
   * is the thing to watch. Measured: −0.99 Re at Pd 0.92 / Bz +1.5, −0.63 at
   * Pd 2 / Bz 0, then **+0.07** at Bz −5, **+0.21** at Bz −6 and **+0.44** at
   * Pd 8 / Bz −15. When it goes positive the shell stops being two lobes and
   * becomes a wrap over the dayside and flanks — see the legend note in
   * `magnetopauseLegend`, which now reports that rather than denying it.
   */
  modelSpreadRe: number;
  /** Solar zenith angles on the noon-north meridian where the shell exists. */
  northLobeThetaRangeDeg: [number, number] | null;
}

/**
 * The closed lens between Lin's inner boundary and Nguyen's current sheet.
 *
 * Both walls are written into one geometry so the volume can be drawn as a
 * single translucent solid: the outer wall, the inner wall with reversed
 * winding, and a rim at the tail cutoff.
 *
 * ⚠️ **The two surfaces cross, and that is what makes this honest.** Lin's
 * boundary is not inside Nguyen's everywhere — the two are independent fits
 * with different subsolar scales, and away from the funnel Lin generally sits
 * *outside*. Only where Lin's additive cusp term pulls it in does it dip
 * inside the current sheet. So the shell is built **only where
 * `r_Nguyen - r_Lin > 0`**, and the result is not a spherical shell with a
 * label on it. Shading the whole gap and calling all of it a cusp would be the
 * overclaim; letting the models decide where the funnel is costs nothing.
 *
 * ⚠️ **CORRECTNESS NOTE 2026-09-04: "two lobes that vanish on the flanks" is
 * only true at quiet and northward drivers.** This paragraph used to assert it
 * unconditionally. The two fits respond to southward Bz differently, so the
 * crossing region opens out: measured north-lobe zenith span on the noon
 * meridian is 33–67.5° at Pd 0.92 / Bz +1.5, but 12–109.5° at Bz −5 and
 * 0–108° at Bz −6, i.e. from the subsolar nose out past the terminator. The
 * legend now reports the measured span rather than promising a shape, and
 * `modelSpreadRe` records the sign flip that goes with it. Gating the build on
 * Nguyen's cusp proximity as well as on thickness would make the drawn volume
 * a funnel at every driver state; that is a design decision about what this
 * annotation is, and it has not been taken here.
 */
export function createExteriorCuspGeometry(
  drivers: CuspedBoundaryDrivers,
  options: MagnetopauseSurfaceOptions,
): ExteriorCuspGeometry | null {
  const outer = magnetopauseEvaluator("nguyen2022", drivers);
  const inner = magnetopauseEvaluator("lin2010", drivers);
  const nguyen = nguyenBoundary(drivers);
  if (!outer || !inner || !nguyen) return null;
  const { thetaSegments, azimuthSegments, maximumThetaRad } = resolve(options);

  const wallVertexCount = (thetaSegments + 1) * azimuthSegments;
  const positions = new Float32Array(wallVertexCount * 2 * 3);
  const gapThickness = new Float32Array(wallVertexCount * 2);
  const cuspProximity = new Float32Array(wallVertexCount * 2);
  const valid = new Uint8Array(wallVertexCount);

  let cuspDepthRe = 0;
  let cuspDepthThetaDeg = Number.NaN;
  let depthOnNguyenAxisRe = 0;
  let northLobeMinDeg = Number.POSITIVE_INFINITY;
  let northLobeMaxDeg = Number.NEGATIVE_INFINITY;
  const spreadSamples: number[] = [];

  for (let thetaIndex = 0; thetaIndex <= thetaSegments; thetaIndex += 1) {
    const theta = (thetaIndex / thetaSegments) * maximumThetaRad;
    for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
      const azimuth = (azimuthIndex / azimuthSegments) * Math.PI * 2;
      const index = thetaIndex * azimuthSegments + azimuthIndex;
      const outerPoint = magnetopausePointGsm(outer, theta, azimuth);
      const innerPoint = magnetopausePointGsm(inner, theta, azimuth);
      if (!Number.isFinite(outerPoint.radiusRe) || !Number.isFinite(innerPoint.radiusRe)) continue;
      const proximity = nguyenCuspProximity(theta, azimuth, nguyen);
      const thickness = outerPoint.radiusRe - innerPoint.radiusRe;
      if (proximity < 0.05) spreadSamples.push(thickness);
      // Only the region where the cusp inner boundary genuinely lies inside
      // the current sheet is part of the shell. Everywhere else the two models
      // simply disagree, and disagreement is not a cusp.
      if (!(thickness > 0)) continue;
      options.positionForGsm(outerPoint.xRe, outerPoint.yRe, outerPoint.zRe)
        .toArray(positions, index * 3);
      options.positionForGsm(innerPoint.xRe, innerPoint.yRe, innerPoint.zRe)
        .toArray(positions, (wallVertexCount + index) * 3);
      gapThickness[index] = thickness;
      gapThickness[wallVertexCount + index] = thickness;
      cuspProximity[index] = proximity;
      cuspProximity[wallVertexCount + index] = proximity;
      valid[index] = 1;
      if (azimuthIndex === 0) {
        const degrees = (theta * 180) / Math.PI;
        northLobeMinDeg = Math.min(northLobeMinDeg, degrees);
        northLobeMaxDeg = Math.max(northLobeMaxDeg, degrees);
      }
      if (thickness > cuspDepthRe) {
        cuspDepthRe = thickness;
        cuspDepthThetaDeg = (theta * 180) / Math.PI;
      }
      // On Nguyen's own axis, which is not where the funnel is widest.
      if (proximity > 0.85) depthOnNguyenAxisRe = Math.max(depthOnNguyenAxisRe, thickness);
    }
  }
  if (!spreadSamples.length && !(cuspDepthRe > 0)) return null;

  const indices = gridIndices(thetaSegments, azimuthSegments, valid);
  const shellIndices: number[] = [...indices];
  for (let triangle = 0; triangle < indices.length; triangle += 3) {
    // Reversed winding on the inner wall so both faces point out of the shell.
    shellIndices.push(
      indices[triangle + 2]! + wallVertexCount,
      indices[triangle + 1]! + wallVertexCount,
      indices[triangle]! + wallVertexCount,
    );
  }
  const rimRow = thetaSegments * azimuthSegments;
  for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
    const next = (azimuthIndex + 1) % azimuthSegments;
    const a = rimRow + azimuthIndex;
    const b = rimRow + next;
    if (!valid[a] || !valid[b]) continue;
    shellIndices.push(a, a + wallVertexCount, b + wallVertexCount, a, b + wallVertexCount, b);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("gapThicknessRe", new THREE.BufferAttribute(gapThickness, 1));
  geometry.setAttribute("cuspProximity", new THREE.BufferAttribute(cuspProximity, 1));
  geometry.setIndex(shellIndices);
  geometry.computeVertexNormals();

  const sorted = spreadSamples.slice().sort((first, second) => first - second);
  const modelSpreadRe = sorted.length ? sorted[Math.floor(sorted.length / 2)]! : Number.NaN;
  return {
    geometry,
    cuspDepthRe,
    cuspDepthThetaDeg,
    depthOnNguyenAxisRe,
    modelSpreadRe,
    northLobeThetaRangeDeg:
      Number.isFinite(northLobeMinDeg) && Number.isFinite(northLobeMaxDeg)
        ? [northLobeMinDeg, northLobeMaxDeg]
        : null,
  };
}

// ---------------------------------------------------------------------------
// Cross-section presentation
// ---------------------------------------------------------------------------

/**
 * The plane a profile curve lives in. `meridional` is the noon-midnight
 * meridian (azimuth 0 north and pi south, where both cusps live);
 * `equatorial` is the dawn-dusk plane (azimuth pi/2 and 3pi/2).
 */
export type MagnetopauseProfilePlane = "meridional" | "equatorial";

const PROFILE_AZIMUTHS: Record<MagnetopauseProfilePlane, readonly [number, number]> = {
  meridional: [0, Math.PI],
  equatorial: [Math.PI / 2, (3 * Math.PI) / 2],
};

/**
 * One empirical surface as a curve in one cut plane.
 *
 * This is the textbook presentation: every printed figure of this system is a
 * meridional cross-section, because a closed translucent shell viewed from
 * outside is one blob — the near and far walls pile onto each other — while
 * the same surface cut open is a line whose indentations can actually be
 * seen. The cusp funnels are indentations, so this is the only presentation
 * in which they read at all.
 *
 * Vertices are emitted as line-segment pairs through the same `positionForGsm`
 * ruler as everything else. Angles where the model returns no radius leave a
 * gap rather than being bridged.
 */
export function createMagnetopauseProfileGeometry(
  evaluator: MagnetopauseEvaluator,
  plane: MagnetopauseProfilePlane,
  options: MagnetopauseSurfaceOptions,
): THREE.BufferGeometry | null {
  const { thetaSegments, maximumThetaRad, minimumThetaRad } = resolve(options);
  const positions: number[] = [];
  const progress: number[] = [];
  for (const azimuth of PROFILE_AZIMUTHS[plane]) {
    let previous: { point: THREE.Vector3; progress: number } | null = null;
    for (let thetaIndex = 0; thetaIndex <= thetaSegments; thetaIndex += 1) {
      const fraction = thetaIndex / thetaSegments;
      const theta = minimumThetaRad + fraction * (maximumThetaRad - minimumThetaRad);
      const point = magnetopausePointGsm(evaluator, theta, azimuth);
      if (!Number.isFinite(point.radiusRe)) {
        previous = null;
        continue;
      }
      const scene = options.positionForGsm(point.xRe, point.yRe, point.zRe);
      if (previous) {
        positions.push(previous.point.x, previous.point.y, previous.point.z, scene.x, scene.y, scene.z);
        progress.push(previous.progress, fraction);
      }
      previous = { point: scene, progress: fraction };
    }
  }
  if (positions.length === 0) return null;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("boundaryProgress", new THREE.Float32BufferAttribute(progress, 1));
  geometry.userData = {
    plane,
    representation: "empirical-boundary-profile-curve",
    model: evaluator.model.id,
  };
  return geometry;
}

/**
 * The exterior-cusp funnel as a filled cross-section in the noon meridian.
 *
 * The same rule as the closed shell: a triangle exists only where Lin's inner
 * boundary genuinely lies inside Nguyen's current sheet (`r_N - r_L > 0`), so
 * the fill is the two published lobes and nothing else. Each hemisphere is
 * built independently; a hemisphere with no positive-thickness span simply
 * does not appear.
 */
export function createExteriorCuspProfileGeometry(
  drivers: CuspedBoundaryDrivers,
  options: MagnetopauseSurfaceOptions,
): THREE.BufferGeometry | null {
  const outer = magnetopauseEvaluator("nguyen2022", drivers);
  const inner = magnetopauseEvaluator("lin2010", drivers);
  if (!outer || !inner) return null;
  const { thetaSegments, maximumThetaRad } = resolve(options);
  const positions: number[] = [];
  const thickness: number[] = [];
  const indices: number[] = [];
  for (const azimuth of [0, Math.PI]) {
    let previousPair: { outerIndex: number; innerIndex: number } | null = null;
    for (let thetaIndex = 0; thetaIndex <= thetaSegments; thetaIndex += 1) {
      const theta = (thetaIndex / thetaSegments) * maximumThetaRad;
      const outerPoint = magnetopausePointGsm(outer, theta, azimuth);
      const innerPoint = magnetopausePointGsm(inner, theta, azimuth);
      const gap = outerPoint.radiusRe - innerPoint.radiusRe;
      if (!Number.isFinite(gap) || !(gap > 0)) {
        previousPair = null;
        continue;
      }
      const outerScene = options.positionForGsm(outerPoint.xRe, outerPoint.yRe, outerPoint.zRe);
      const innerScene = options.positionForGsm(innerPoint.xRe, innerPoint.yRe, innerPoint.zRe);
      const outerIndex = positions.length / 3;
      positions.push(outerScene.x, outerScene.y, outerScene.z, innerScene.x, innerScene.y, innerScene.z);
      thickness.push(gap, gap);
      const innerIndex = outerIndex + 1;
      if (previousPair) {
        indices.push(
          previousPair.outerIndex, previousPair.innerIndex, innerIndex,
          previousPair.outerIndex, innerIndex, outerIndex,
        );
      }
      previousPair = { outerIndex, innerIndex };
    }
  }
  if (indices.length === 0) return null;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("gapThicknessRe", new THREE.Float32BufferAttribute(thickness, 1));
  geometry.setIndex(indices);
  geometry.userData = {
    plane: "meridional",
    representation: "exterior-cusp-cross-section",
    derivation: "the span where Lin's cusp inner boundary lies inside Nguyen's current sheet, on the noon meridian",
  };
  return geometry;
}

// ---------------------------------------------------------------------------
// Cusp entry cue
// ---------------------------------------------------------------------------

export interface CuspEntryPath {
  /** Path points in physical GSM Re, ordered from the magnetosheath inward. */
  pointsGsmRe: Array<{ xRe: number; yRe: number; zRe: number }>;
  hemisphere: "north" | "south";
  /** Dipole footpoint latitude of the continuation, degrees. */
  footpointLatitudeDeg: number;
  /** The dipole L of the funnel's inner vertex, dimensionless. */
  dipoleL: number;
}

/**
 * The paths of the animated cusp-entry cue: from the magnetosheath just
 * outside Nguyen's current sheet, down the exterior-cusp funnel to Lin's
 * inner boundary, then along an ideal dipole field line to the top of the
 * atmosphere.
 *
 * ## What is driven and what is illustrative — the honest split
 *
 * The *funnel* is the two live empirical surfaces: its mouth, walls and
 * throat move with pressure, Bz, clock angle and tilt, so the paths swing
 * equatorward as Bz turns south because Nguyen's cusp latitude does. The
 * *continuation* below the boundary is the same centered ideal dipole the
 * radiation-belt mapping already declares: the funnel vertex sits at
 * magnetic latitude lambda_0 and radius r_0, its field line is
 * r = L cos^2(lambda) with L = r_0 / cos^2(lambda_0), and that line is
 * followed to r = 1.05 Re.
 *
 * ⚠️ **CORRECTNESS NOTE 2026-09-04, and it is NOT fixed.** This paragraph used
 * to say that lands "near 75-78 degrees latitude — the dayside cusp aurora's
 * real neighbourhood". Measured over 105 driver states (Pd 1/2/5 nPa, Bz -10
 * to +5 nT, tilt -0.55 to +0.55 rad), the north footpoint comes out:
 *
 *     min 71.8   p25 77.8   median 81.2   p75 85.8   max 89.0 degrees
 *     inside the claimed 75-78 band: 21.9%      above 80: 57.1%
 *
 * so more than half the time the cue lands poleward of the 77-80 degree band
 * the site's own satellite-fundamentals copy gives the cusp footprint. Two
 * causes, and only the first is certain:
 *
 *   1. `vertexLatitude = cuspTheta` equates a GSM SOLAR ZENITH ANGLE with a
 *      MAGNETIC latitude. They differ by the dipole tilt, and the rest of this
 *      site rotates rather than assuming (`dungey-transport.ts` through
 *      `gsmFromDipoleFrame`; `radiation-belt-volume.ts` through `smFromGsm`).
 *      On the noon meridian z_sm = r*sin(theta + psi) for the north cusp, so
 *      the magnetic latitude is theta + psi, not theta. At tilt -0.5 rad this
 *      is the difference between L = 1,070 and a footpoint at 88.2 degrees —
 *      effectively the magnetic pole — and something an order of magnitude
 *      smaller. The guard at `cuspTheta >= PI/2 + 0.6` never fires on it.
 *   2. Even at zero tilt the ideal-dipole continuation gives L = 68 and a
 *      82.9 degree footpoint, because Nguyen's cusp axis sits at 68.6 degrees
 *      zenith at 9 Re and a dipole line through that point really does have
 *      L = 68. The real field in the cusp is not dipolar, which is the
 *      approximation this leg already declares.
 *
 * Fixing (1) means rebuilding the continuation in SM and rotating it back,
 * and the drawn leg's in-plane angle would stop equalling the latitude, so it
 * is a geometry change rather than a wording one. It has NOT been made here:
 * a confident wrong correction to drawn geometry is worse than a described
 * error. The claim is corrected; the mapping is reported.
 *
 * The *motion* along the path is illustrative: no measured
 * velocity exists along it, and the layer's legend says so.
 *
 * Entry happens through the cusp rather than through the closed boundary,
 * which is the lesson: the solar-wind tracers deflect around the same
 * surfaces these paths thread.
 */
export function createCuspEntryPaths(
  drivers: CuspedBoundaryDrivers,
  options: { samples?: number; azimuthSpreadRad?: number; pathsPerHemisphere?: number } = {},
): CuspEntryPath[] {
  const nguyen = nguyenBoundary(drivers);
  const outer = magnetopauseEvaluator("nguyen2022", drivers);
  const inner = magnetopauseEvaluator("lin2010", drivers);
  if (!nguyen || !outer || !inner) return [];
  const samples = Math.max(12, Math.floor(options.samples ?? 36));
  const pathsPerHemisphere = Math.max(1, Math.floor(options.pathsPerHemisphere ?? 3));
  const spread = options.azimuthSpreadRad ?? 0.22;

  const paths: CuspEntryPath[] = [];
  for (const hemisphere of ["north", "south"] as const) {
    const baseAzimuth = hemisphere === "north" ? 0 : Math.PI;
    const cuspTheta = hemisphere === "north" ? nguyen.northCuspThetaRad : nguyen.southCuspThetaRad;
    if (!Number.isFinite(cuspTheta) || cuspTheta <= 0 || cuspTheta >= Math.PI / 2 + 0.6) continue;
    for (let pathIndex = 0; pathIndex < pathsPerHemisphere; pathIndex += 1) {
      const azimuthOffset = pathsPerHemisphere === 1
        ? 0
        : ((pathIndex / (pathsPerHemisphere - 1)) - 0.5) * 2 * spread;
      const azimuth = baseAzimuth + azimuthOffset;
      const outerRadius = outer.radiusRe(cuspTheta, azimuth);
      const innerRadius = inner.radiusRe(cuspTheta, azimuth);
      if (!Number.isFinite(outerRadius) || !Number.isFinite(innerRadius)) continue;
      // The funnel only exists where the two surfaces genuinely cross.
      const vertexRadius = Math.min(innerRadius, outerRadius);
      const mouthRadius = Math.max(innerRadius, outerRadius) + 1.5;

      // Magnetic latitude of a point at zenith angle theta on the noon
      // meridian: the point is (r cos th, ~0, +/- r sin th), so its latitude
      // magnitude is exactly theta.
      const latitudeSign = hemisphere === "north" ? 1 : -1;
      const vertexLatitude = cuspTheta;
      const dipoleL = vertexRadius / Math.cos(vertexLatitude) ** 2;
      const footLatitude = Math.acos(Math.sqrt(Math.min(1, 1.05 / dipoleL)));

      const points: CuspEntryPath["pointsGsmRe"] = [];
      // Both legs live in the vertical plane spanned by sunward x-hat and the
      // path's own transverse direction t-hat. For the exact noon meridian
      // t-hat is +/-z-hat; a small azimuth offset tips the plane slightly so
      // the cue has volume without leaving the funnel's neighbourhood.
      const transverseY = Math.sin(azimuth);
      const transverseZ = Math.cos(azimuth);
      const inPlane = (radius: number, angleFromSunward: number) => ({
        xRe: radius * Math.cos(angleFromSunward),
        yRe: radius * Math.sin(angleFromSunward) * transverseY,
        zRe: radius * Math.sin(angleFromSunward) * transverseZ,
      });
      // Leg 1: radially down the funnel axis from the mouth to the vertex.
      const funnelSteps = Math.floor(samples * 0.4);
      for (let step = 0; step <= funnelSteps; step += 1) {
        const radius = mouthRadius + (vertexRadius - mouthRadius) * (step / funnelSteps);
        points.push(inPlane(radius, cuspTheta));
      }
      // Leg 2: the ideal-dipole continuation from the vertex to 1.05 Re. The
      // in-plane angle from sunward equals the magnetic latitude magnitude on
      // the noon meridian, so the two legs join without a seam.
      const dipoleSteps = samples - funnelSteps;
      for (let step = 1; step <= dipoleSteps; step += 1) {
        const latitude = vertexLatitude + (footLatitude - vertexLatitude) * (step / dipoleSteps);
        const radius = dipoleL * Math.cos(latitude) ** 2;
        points.push(inPlane(radius, latitude));
      }
      paths.push({
        pointsGsmRe: points,
        hemisphere,
        footpointLatitudeDeg: (latitudeSign * footLatitude * 180) / Math.PI,
        dipoleL,
      });
    }
  }
  return paths;
}

export interface MagnetopauseLegendEntry {
  id: MagnetopauseModelId | "exteriorCusp";
  label: string;
  status: "empirical";
  detail: string;
  note: string;
}

/**
 * The legend text for whatever is currently drawn.
 *
 * Built from the evaluated models rather than written as prose, so a driver
 * change moves the numbers on screen and a model change moves the words. The
 * honesty line is not optional and is not separable from the entry.
 */
export function magnetopauseLegend(
  drivers: CuspedBoundaryDrivers,
  selected: Array<MagnetopauseModelId | "exteriorCusp">,
  cusp?: ExteriorCuspGeometry | null,
): MagnetopauseLegendEntry[] {
  const entries: MagnetopauseLegendEntry[] = [];
  const format = (value: number, digits = 2) => (Number.isFinite(value) ? value.toFixed(digits) : "—");
  const tiltDeg = (drivers.dipoleTiltRad * 180) / Math.PI;
  const clockDeg = ((((drivers.clockAngleRad * 180) / Math.PI) % 360) + 360) % 360;
  for (const id of selected) {
    if (id === "exteriorCusp") {
      entries.push({
        id,
        label: "EXTERIOR CUSP",
        status: "empirical",
        detail: cusp
          ? `funnel up to ${format(cusp.cuspDepthRe)} Re thick at ${format(cusp.cuspDepthThetaDeg, 1)}° zenith`
            + ` · ${format(cusp.depthOnNguyenAxisRe)} Re on Nguyen's own cusp axis`
            + (cusp.northLobeThetaRangeDeg
              ? ` · north lobe spans ${format(cusp.northLobeThetaRangeDeg[0], 0)}–`
                + `${format(cusp.northLobeThetaRangeDeg[1], 0)}° zenith`
              : "")
            + ` · the two fits differ by ${format(cusp.modelSpreadRe)} Re away from the cusps`
          : "unavailable",
        // CORRECTNESS FIX 2026-09-04: this note asserted a SHAPE that the
        // construction does not guarantee, and under the drivers a reader is
        // most likely to have on screen it is the wrong shape. The shell is
        // built wherever `r_Nguyen - r_Lin > 0`, and the two fits respond to
        // southward Bz differently, so that region opens out. Measured on the
        // real evaluators, north-lobe zenith span on the noon meridian:
        //
        //   Pd 0.92, Bz +1.5   33.0 – 67.5 deg   (a lobe, as claimed)
        //   Pd 2.0,  Bz  0     39.0 – 61.5 deg
        //   Pd 2.0,  Bz -5     12.0 – 109.5 deg
        //   Pd 2.5,  Bz -6      0.0 – 108.0 deg  (includes the subsolar nose)
        //   Pd 8.0,  Bz -15     0.0 – 105.0 deg
        //
        // and `modelSpreadRe`, which the field's own docstring says to "expect
        // to be negative", comes out +0.07 at Bz -5, +0.21 at -6 and +0.44 in
        // the storm case. So under southward IMF the drawn thing is a shell
        // over most of the dayside and both flanks, which is exactly what the
        // sentence promised it was not. The shipped guard
        // (`tests/magnetopause-surfaces.test.ts`, "is a pair of lobes near
        // noon") asserts drawn/count < 0.5 on the QUIET state only, so it has
        // never seen this.
        //
        // The note now reads the measurement instead of asserting the shape.
        // WHETHER THE GEOMETRY SHOULD ALSO BE GATED on Nguyen's cusp proximity
        // — so the shell really is a funnel rather than the region where two
        // fits happen to cross — is a design decision about what this
        // annotation draws, and is the owner's, not this fix's.
        note:
          "The volume between two published empirical surfaces: Lin's cusp inner boundary "
          + "and Nguyen's magnetopause current sheet. Drawn wherever Lin's boundary lies "
          + "inside Nguyen's, and the span above says where that is. "
          + (cusp && cusp.northLobeThetaRangeDeg
            && (cusp.northLobeThetaRangeDeg[0] <= 10 || cusp.northLobeThetaRangeDeg[1] >= 90)
            ? "Right now that region is NOT a pair of cusp lobes: under a southward IMF the two "
              + "fits cross over most of the modelled dayside and out onto the flanks, and where "
              + "the span reaches 0° the shading includes the subsolar nose, which no cusp does. "
              + "Read only the thickest part, near the cusp axes, as a funnel; the rest is spread "
              + "between two independent fits."
            : "Right now that region is a pair of lobes on the noon meridian rather than a shell "
              + "around the whole magnetosphere. Away from the cusps the two fits still differ, "
              + "and that difference is model spread, not a cusp."),
      });
      continue;
    }
    const evaluator = magnetopauseEvaluator(id, drivers);
    if (!evaluator) continue;
    const driverText =
      id === "shue1998"
        ? `Pd ${format(drivers.dynamicPressureNpa)} nPa · Bz ${format(drivers.bzGsmNt)} nT`
        : `Pd ${format(drivers.dynamicPressureNpa)} nPa · Bz ${format(drivers.bzGsmNt)} nT`
          + ` · clock ${format(clockDeg, 0)}° · tilt ${format(tiltDeg, 1)}°`;
    entries.push({
      id,
      label: evaluator.model.label.toUpperCase(),
      status: "empirical",
      detail: `${evaluator.model.surface} · subsolar ${format(evaluator.subsolarRe)} Re · ${driverText}`,
      note: evaluator.model.note,
    });
  }
  return entries;
}
