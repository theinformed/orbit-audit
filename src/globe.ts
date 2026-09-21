import * as THREE from "three";
import { EmpiricalDRegionLayer, type DRegionSurfaceState } from "./d-region-empirical";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  AuroraSurfaceLayerController,
  DrapSurfaceLayerController,
} from "./environment-surface-layer";
import type { EnvironmentSurfaceState } from "./environment-surface-layer";
import { GroundPerturbationLayer, sampleGroundPerturbation } from "./ground-perturbation";
import type {
  GroundCurrentSystemKey,
  GroundFieldBundle,
  GroundFieldSample,
  GroundFieldState,
} from "./ground-perturbation";
import { GeospaceRuntime } from "./geospace-runtime";
import type { GeospaceStructureRegion } from "./geospace-runtime";
import type {
  GeospaceRuntimeFrameState,
  GeospaceRuntimeLegendMetadata,
  PlasmaSheetLegendMetadata,
  RadiationBeltRuntimeView,
} from "./geospace-runtime";
import { decodeBoundaryProfile } from "./geospace-structures";
import type {
  EncodedFrameStructures,
  GeospaceStructuresDefinition,
} from "./geospace-structures";
import { IonosphereVolumeLayer } from "./ionosphere-volume";
import { IonosphereDensityVolumeLayer } from "./ionosphere-density-volume";
import type { IonosphereRegionId, IonosphereVolumeBake } from "./ionosphere-density-volume";
import type { IonosphereSurfaceState } from "./ionosphere-volume";
import type { MagnetopauseDriverSample } from "./environment-time";
import {
  type CuspedBoundaryDrivers,
  type MagnetopauseModelId,
  magneticPressureNpa,
  magnetopauseEvaluator,
  nguyenBoundary,
  nguyenUnindentedRadiusRe,
  shueBoundary,
  shueTailTheta,
} from "./magnetopause";
import {
  type CuspEntryPath,
  type ExteriorCuspGeometry,
  type MagnetopauseLegendEntry,
  type MagnetopauseProfilePlane,
  type MagnetopauseSurfaceOptions,
  createCuspEntryPaths,
  createExteriorCuspGeometry,
  createExteriorCuspProfileGeometry,
  createMagnetopauseProfileGeometry,
  createMagnetopauseSurfaceGeometry,
  magnetopauseLegend,
} from "./magnetopause-surfaces";
import {
  type PlasmasphereLayerField,
  createPlasmasphereFieldObject,
  setPlasmasphereDisplayTime,
} from "./inner-magnetosphere";
import {
  type RingCurrentFormation,
  type RingCurrentIllustration,
  createRingCurrentObject,
  paintRingCurrentPulse,
  setRingCurrentDisplayTime,
} from "./ring-current-illustration";
import {
  FIELD_LINE_DISPLAY_LOG_RANGE,
  FIELD_LINE_METHOD,
  type BoundaryCalibration,
  type BoundaryCurvePoint,
  type FieldLineIntegrityReport,
  type FieldLineSummary,
  type TracedFieldLine,
  fitShueToBoundaryCurve,
  traceMagnetosphereFieldLines,
  truncatedEndFade,
  verifyTracedMagnetosphere,
} from "./magnetosphere-field-lines";
import { decimalYear, dipoleAxis, dipoleTilt } from "./dipole-tilt";
import { InnerPlasmaSheet, innerEdgeRe } from "./inner-plasma-sheet";
import type { SubstormState } from "./substorm-chain";
import { clockAngleRad } from "./storm-indices";
import { footprintPoints, greenwichSiderealAngle } from "./orbit";
import { DEFAULT_RADIATION_ENERGY_KEV, radiationBeltDisplayRadius } from "./radiation-belt";
import {
  type DistanceScaleId,
  RADIAL_RULER,
  RULER_EARTH_RADIUS_KM,
  activeDistanceScale,
  radiusFromSharedDisplayRadius,
  rulerJointBandSegments,
  setActiveDistanceScale,
  sharedDisplayRadius,
} from "./radial-ruler";
import {
  createSolarWindVisual,
  createXrayIrradianceVisual,
} from "./solar-input-visuals";
import type { SolarWindVisual, SolarWindVisualMode, TailReturnOptions, XrayIrradianceVisual } from "./solar-input-visuals";
import type { AuroraBundle } from "./aurora-time";
import type { DrapBundle } from "./drap";
import type { AuroraPoint, GeospaceBundle, GeospaceField, GeospacePlane, IonosphereVolumeBundle, MissionCapability, SatelliteRecord, TecPoint } from "./types";
import type { DecodedFrame } from "./thermosphere";
import { ThermosphereVolumeLayer } from "./thermosphere-volume";

type GeoJsonCoordinates = number[] | GeoJsonCoordinates[];
export interface LandGeoJson {
  features: Array<{ geometry: { type: string; coordinates: GeoJsonCoordinates } }>;
}

export const EARTH_SCENE_RADIUS = 100;

/**
 * Earth's limb glow, as a multiple of the DRAWN globe radius. Exported so a
 * test can pin the one thing about it that matters scientifically: it is not
 * on the shared ruler, so it means a different altitude on each distance
 * scale, and it lands inside the ionosphere volume on both. See
 * `applyAirglowVisibility`.
 */
export const EARTH_AIRGLOW_SHELL_SCALE = 1.07;

/**
 * Where the GloTEC total-electron-content map is drawn: on the globe, not at
 * an altitude. TEC is a column integral and has no height, so the map goes on
 * the column's footprint with just enough lift to clear the basemap and the
 * coastlines at 100.06. Exported so a test can pin the two properties that
 * matter -- the same drawn radius on both distance scales, and below every
 * layer that does carry an altitude on either of them. See `buildIonosphere`.
 */
export const TEC_MAP_SCENE_RADIUS = EARTH_SCENE_RADIUS * 1.003;
/**
 * Coastlines sit a hair above the globe: the sphere is drawn as a 96x64
 * polyhedron, whose flat faces sag up to 0.054 scene units inside the true
 * sphere. 100.06 clears that sag everywhere while staying 4 km off the
 * surface at Earth scale, which is far too little to see as parallax.
 */
const COASTLINE_SCENE_RADIUS = 100.06;
export type ReferenceFrame = "earth-fixed" | "inertial";
export type FieldRendering = "smooth" | "native";

/** Geographic point to this globe's scene axes. */
export function geoRadiansToSceneVector(latitude: number, longitude: number, radius: number) {
  return new THREE.Vector3(
    radius * Math.cos(latitude) * Math.cos(longitude),
    radius * Math.sin(latitude),
    -radius * Math.cos(latitude) * Math.sin(longitude),
  );
}

export function geoToSceneVector(latitudeDeg: number, longitudeDeg: number, radius: number) {
  return geoRadiansToSceneVector((latitudeDeg * Math.PI) / 180, (longitudeDeg * Math.PI) / 180, radius);
}

/** Geographic longitude, in degrees, of a direction in scene axes. */
export function sceneAzimuthDegrees(point: THREE.Vector3) {
  return (Math.atan2(-point.z, point.x) * 180) / Math.PI;
}

/**
 * Geographic latitude and longitude of a point in earth-fixed scene axes —
 * the inverse of `geoToSceneVector`, kept beside it so the two cannot drift
 * apart. Any radius is accepted: the direction alone carries the geography.
 */
export function sceneVectorToGeo(point: THREE.Vector3): { latitudeDeg: number; longitudeDeg: number } {
  const radius = point.length();
  if (radius <= 0) throw new RangeError("A zero-length scene vector has no geographic direction");
  return {
    latitudeDeg: (Math.asin(THREE.MathUtils.clamp(point.y / radius, -1, 1)) * 180) / Math.PI,
    longitudeDeg: sceneAzimuthDegrees(point),
  };
}

/**
 * Where a raster globe layer actually draws a geographic longitude.
 *
 * Every map on this globe is an equirectangular texture whose horizontal
 * coordinate is u = (longitude + 180) / 360 — the Earth's painted canvas, the
 * TEC and aurora canvases through longitudeTextureX, and the D-RAP and aurora
 * history grids through the sampling offset in environment-surface-layer.
 * This walks the mesh's own vertices, texture coordinates and world transform
 * to report the scene azimuth that column is rendered at.
 *
 * It must equal the azimuth geoToSceneVector gives the same longitude. It did
 * not: all four layers carried an extra `rotation.y = -PI/2`, which drew every
 * map 90 degrees west of the satellites, ground tracks, footprints, graticule
 * and day/night terminator laid over it. That hid for as long as it did
 * because the graticule is unlabelled at 15-degree spacing and 90 is a
 * multiple of 15.
 */
export function equirectangularLayerAzimuth(
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.Material | THREE.Material[]>,
  longitudeDeg: number,
): { azimuthDeg: number; textureCoordinateError: number } {
  const uv = mesh.geometry.getAttribute("uv");
  const position = mesh.geometry.getAttribute("position");
  if (!uv || !position) throw new RangeError("Layer geometry carries no texture coordinates");
  const wantedU = ((((longitudeDeg + 180) / 360) % 1) + 1) % 1;
  let bestIndex = -1;
  let bestDistance = Infinity;
  for (let index = 0; index < uv.count; index += 1) {
    const rawU = Math.abs(uv.getX(index) - wantedU);
    const deltaU = Math.min(rawU, 1 - rawU);
    // The equator, so latitude never enters the azimuth being measured.
    const deltaV = Math.abs(uv.getY(index) - 0.5);
    const distance = deltaU * deltaU + deltaV * deltaV;
    if (distance >= bestDistance) continue;
    bestDistance = distance;
    bestIndex = index;
  }
  mesh.updateMatrixWorld(true);
  const point = new THREE.Vector3(
    position.getX(bestIndex),
    position.getY(bestIndex),
    position.getZ(bestIndex),
  ).applyMatrix4(mesh.matrixWorld);
  return { azimuthDeg: sceneAzimuthDegrees(point), textureCoordinateError: Math.sqrt(bestDistance) };
}

/** Smallest signed difference between two azimuths, in degrees. */
export function azimuthDifferenceDegrees(first: number, second: number) {
  return ((((first - second) % 360) + 540) % 360) - 180;
}

/**
 * Where a satellite at this altitude is drawn.
 *
 * This is the scene's radial ruler expressed on altitude in kilometres;
 * radiationBeltDisplayRadius is the identical curve expressed in Earth radii,
 * and the geospace layers go through that. Both resolve to the shared curve in
 * `src/radial-ruler.ts`: logarithmic out to geostationary orbit, then linear
 * through the dayside boundary system so boundary shape survives, then
 * tapering down the tail. Radial distance is compressed and is never
 * quantitative.
 */
export function satelliteDisplayRadius(altitudeKm: number) {
  return sharedDisplayRadius(1 + Math.max(0, altitudeKm) / RULER_EARTH_RADIUS_KM, EARTH_SCENE_RADIUS);
}

export function altitudeFromSatelliteDisplayRadius(radius: number) {
  return Math.max(
    0,
    (radiusFromSharedDisplayRadius(Math.max(EARTH_SCENE_RADIUS, radius), EARTH_SCENE_RADIUS) - 1)
      * RULER_EARTH_RADIUS_KM,
  );
}

/**
 * The scene radius the view frames when nothing but the globe and the surface
 * layers are drawn: Earth plus the shell up to 600 km, where the ionospheric
 * peak surfaces live, on the same radial ruler as everything else.
 *
 * This is also the site's opening framing. Sean asked to start "just a touch"
 * zoomed out from the old hand-picked camera position, and expressing it as a
 * scene radius rather than a camera distance is what lets the opening view and
 * the automatic re-framing below share one code path — they cannot drift.
 */
export const DEFAULT_VIEW_SCENE_RADIUS = satelliteDisplayRadius(600);

/**
 * The clear band the framing leaves on each edge of the scene, as a fraction
 * of the frame's short side.
 *
 * Everything the framing aims at is centred on Earth, so what is being fitted
 * is a sphere — and a centred sphere is seen along its TANGENT cone, not
 * across its equator. At a camera distance d it occupies asin(R/d) of the
 * frame; the rule below used to divide by tan(), which is the angle to a point
 * at radius R in the plane through the origin and is always the smaller of the
 * two. Its `margin = 1.1` therefore did not buy 10%. Measured off the rendered
 * pixels at 1440x900, where the scene is 1050x832 beside the rail: the
 * thermosphere shell — the one layer whose drawn edge sits at the framed
 * radius — filled 95.1% of the frame's height, 15 px of sky above it, and
 * 96.6% in the state Sean actually reported, which is 10 px. His words for it
 * were "it zoomed in just a little too much... close enough that the user will
 * have to zoom out a little".
 *
 * 0.05 leaves 5% clear on each edge — 42 px of that 832 px height, and 20 px
 * of the 390 px width on a phone, where the narrow side binds. Measured after
 * the change, the same shell draws 88.3% with 44 px above it. It is a
 * deliberately small correction: it dollies the camera 6.8% further out, where
 * one press of the zoom-out control is 28%, so it removes the crowding without
 * making the visitor's own correction for them. Padding is not free — the
 * globe is the biggest thing on the screen and the owner has separately said
 * it can look empty — so the cost was measured too: the opening view, Earth
 * and its air glow with no layer on, goes from 74.0% to 71.4%.
 *
 * A FRACTION, never a distance in scene units. This scene runs from a 100-unit
 * globe through a magnetopause a few hundred units out to a tail past 700, and
 * a padding tuned to look right around the globe would be invisible around the
 * magnetosphere. It is also expressed against the drawn frame rather than
 * against the radial ruler, so it survives the ruler being re-tuned underneath
 * it.
 *
 * EVERY path that re-frames uses this one number, so switching a layer on or
 * off, selecting a spacecraft, resetting the view, flipping the distance scale
 * and each of the four camera presets all leave the same band of sky. The
 * cross-section, polar and satellite presets used to pass their own 1.02-1.06
 * — values that, read through the tangent rule, CROPPED the fitted sphere by
 * 1-6% rather than padding it, which is what hand-tuning against a rule whose
 * margin was not what it claimed produces.
 */
export const VIEW_EDGE_MARGIN_FRACTION = 0.05;

/**
 * How far back the camera must sit for everything within `sceneRadius` of
 * Earth's centre to fit inside the frame with `margin` of it clear on each
 * edge.
 *
 * `sceneRadiusForActiveLayers()` reports a reach from the origin and Earth
 * always stays in the middle of the picture, so the subject is a sphere of
 * that radius and the honest solve is through its silhouette: the sphere fills
 * the frame's short side when asin(R/d) equals the half-angle the frame
 * allows. Solving that, rather than inverting a tangent, is what makes the
 * constant above mean the thing it is measured to be.
 *
 * The SHORT side binds because the vertical FOV is fixed and the horizontal
 * one follows the aspect: on the desktop scene (1050x832 beside the rail) the
 * height decides, on a phone in portrait the width does.
 *
 * Exported so the framing rule can be exercised directly; the camera method
 * that calls it adds only the dolly clamp.
 */
export function distanceToFrameSceneRadius(
  sceneRadius: number,
  fovDegrees: number,
  aspect: number,
  margin = VIEW_EDGE_MARGIN_FRACTION,
): number {
  const halfVertical = THREE.MathUtils.degToRad(fovDegrees) / 2;
  const halfHorizontal = Math.atan(Math.tan(halfVertical) * Math.max(0.2, aspect));
  const halfAngle = Math.max(0.05, Math.min(halfVertical, halfHorizontal));
  // Guarded rather than trusted: a margin of half the frame or more would
  // divide by an angle of zero and throw the camera to infinity.
  const fill = Math.max(0.1, Math.min(1, 1 - 2 * margin));
  return sceneRadius / Math.sin(Math.atan(fill * Math.tan(halfAngle)));
}

/**
 * When the view should re-frame itself, and when it must leave the visitor
 * alone.
 *
 * If what is drawn no longer fits, always pull back — otherwise switching a
 * layer on shows nothing at all. If it would fit more tightly than the current
 * view (a layer was switched off) only come back in when the visitor has not
 * zoomed by hand since the last automatic framing, so the camera never fights
 * them. An off-centre orbit target always re-frames, because Earth belongs in
 * the middle of the picture. The reset control forces the decision either way.
 */
export function shouldReframeView(options: {
  wantedDistance: number;
  currentDistance: number;
  autoFrameDistance: number | null;
  targetOffCentre: boolean;
  force?: boolean;
}): boolean {
  if (options.force) return true;
  if (options.targetOffCentre) return true;
  if (options.autoFrameDistance === null) return Math.abs(options.wantedDistance - options.currentDistance) >= 2;
  // More room is needed than the view has ever been given: the layer that was
  // just switched on does not fit, so pull back even over a manual zoom.
  if (options.wantedDistance > options.autoFrameDistance * 1.02) return true;
  // Otherwise the layers need no more room than before. Coming back in is only
  // ours to do while the visitor has left the zoom alone.
  const adjustedByHand = Math.abs(options.currentDistance - options.autoFrameDistance)
    > Math.max(8, options.autoFrameDistance * 0.05);
  if (adjustedByHand) return false;
  return Math.abs(options.wantedDistance - options.currentDistance) >= 2;
}

/**
 * How far the furthest corner of a bounding box sits from the scene origin.
 *
 * Framing keeps Earth in the middle of the view, so what matters is not the
 * size of a layer but how far it reaches from Earth's centre in the worst
 * direction — which is the corner built from each axis' larger extreme.
 */
export function boundingRadiusFromOrigin(box: THREE.Box3) {
  if (box.isEmpty()) return 0;
  return Math.hypot(
    Math.max(Math.abs(box.min.x), Math.abs(box.max.x)),
    Math.max(Math.abs(box.min.y), Math.abs(box.max.y)),
    Math.max(Math.abs(box.min.z), Math.abs(box.max.z)),
  );
}

export const FOOTPRINT_FILL_RADIUS = 100.78;
/**
 * How much of the cap's lift above the globe must survive the tessellation.
 *
 * Flat triangles cannot follow a sphere. A triangle whose corners sit on a
 * sphere of radius R and which spans an angular step s falls R(1-cos(s/2))
 * below that sphere at the middle of its longest edge. The coverage cap is
 * lifted only FOOTPRINT_FILL_RADIUS - EARTH_SCENE_RADIUS above the globe, so
 * once that sag exceeds the lift the cap's own triangles pass *inside* the
 * opaque Earth, the Earth wins the depth test, and the cap shows bands of
 * missing fill that crawl as the spacecraft moves. Keeping a clearance rather
 * than merely a positive margin also keeps the cap clear of depth-buffer
 * quantisation when the camera is pulled far back.
 */
export const FOOTPRINT_FILL_MINIMUM_CLEARANCE = 0.6;
const FOOTPRINT_FILL_MINIMUM_RINGS = 7;
const FOOTPRINT_FILL_MAXIMUM_RINGS = 64;

/** Depth of the dip between a chord and the sphere arc it replaces. */
export function sphericalChordSag(radius: number, angularStepRad: number) {
  return radius * (1 - Math.cos(angularStepRad / 2));
}

/**
 * Concentric rings needed so the cap's flat triangles stay clear of the globe.
 *
 * The azimuthal chords around each ring spend part of the sag budget too, so
 * they are subtracted before the radial step is solved for.
 */
export function footprintFillRingCount(
  angularRadiusRad: number,
  segments: number,
  fillRadius = FOOTPRINT_FILL_RADIUS,
  earthRadius = EARTH_SCENE_RADIUS,
  clearance = FOOTPRINT_FILL_MINIMUM_CLEARANCE,
) {
  const azimuthalStep = (Math.PI * 2) / Math.max(3, segments);
  const budget = fillRadius - earthRadius - clearance - sphericalChordSag(fillRadius, azimuthalStep);
  if (!Number.isFinite(angularRadiusRad) || angularRadiusRad <= 0) return FOOTPRINT_FILL_MINIMUM_RINGS;
  if (!(budget > 0)) return FOOTPRINT_FILL_MAXIMUM_RINGS;
  const maximumStep = 2 * Math.acos(THREE.MathUtils.clamp(1 - budget / fillRadius, -1, 1));
  if (!(maximumStep > 0)) return FOOTPRINT_FILL_MAXIMUM_RINGS;
  return THREE.MathUtils.clamp(
    Math.ceil(angularRadiusRad / maximumStep),
    FOOTPRINT_FILL_MINIMUM_RINGS,
    FOOTPRINT_FILL_MAXIMUM_RINGS,
  );
}

/**
 * Drop the repeated closing vertex the footprint generators emit.
 *
 * The closing point is recomputed at bearing 2π rather than copied, so it
 * differs from the first point in the last bits and an exact equality test
 * never fires. Left in place it produced a degenerate wrap-around triangle.
 */
export function footprintFillEdgePoints(boundary: readonly THREE.Vector3[]): THREE.Vector3[] {
  const first = boundary[0];
  const last = boundary.at(-1);
  if (boundary.length > 3 && first && last && last.distanceTo(first) <= 1e-6 * Math.max(1, first.length())) {
    return boundary.slice(0, -1);
  }
  return [...boundary];
}

/** Great-circle interpolation between two directions, unlike a normalised lerp. */
function slerpDirection(from: THREE.Vector3, to: THREE.Vector3, amount: number) {
  const cosine = THREE.MathUtils.clamp(from.dot(to), -1, 1);
  const angle = Math.acos(cosine);
  if (!(angle > 1e-7)) return to.clone();
  const sine = Math.sin(angle);
  return from
    .clone()
    .multiplyScalar(Math.sin((1 - amount) * angle) / sine)
    .addScaledVector(to, Math.sin(amount * angle) / sine)
    .normalize();
}

export interface FootprintFillGeometry {
  positions: Float32Array;
  edgeAmounts: Float32Array;
  indices: number[];
  rings: number;
  angularRadiusRad: number;
}

/**
 * Triangulate the coverage cap as concentric rings of equal angular step.
 *
 * Ring positions are great-circle interpolations rather than normalised
 * linear ones so the step between rings really is uniform, and the ring count
 * comes from footprintFillRingCount so that step is small enough to hold the
 * whole cap above the globe.
 */
export function buildFootprintFillGeometry(boundary: readonly THREE.Vector3[]): FootprintFillGeometry {
  const edge = footprintFillEdgePoints(boundary);
  const directions = edge.map((point) => point.clone().normalize());
  const centerDirection = directions
    .reduce((sum, direction) => sum.add(direction), new THREE.Vector3())
    .normalize();
  const angularRadiusRad = directions.reduce(
    (widest, direction) => Math.max(widest, Math.acos(THREE.MathUtils.clamp(centerDirection.dot(direction), -1, 1))),
    0,
  );
  const rings = footprintFillRingCount(angularRadiusRad, directions.length);

  const positions = new Float32Array((1 + rings * directions.length) * 3);
  const edgeAmounts = new Float32Array(1 + rings * directions.length);
  positions[0] = centerDirection.x * FOOTPRINT_FILL_RADIUS;
  positions[1] = centerDirection.y * FOOTPRINT_FILL_RADIUS;
  positions[2] = centerDirection.z * FOOTPRINT_FILL_RADIUS;
  edgeAmounts[0] = 0;
  for (let ring = 1; ring <= rings; ring += 1) {
    const amount = ring / rings;
    directions.forEach((direction, segment) => {
      const vertex = 1 + (ring - 1) * directions.length + segment;
      const placed = slerpDirection(centerDirection, direction, amount).multiplyScalar(FOOTPRINT_FILL_RADIUS);
      positions[vertex * 3] = placed.x;
      positions[vertex * 3 + 1] = placed.y;
      positions[vertex * 3 + 2] = placed.z;
      edgeAmounts[vertex] = amount;
    });
  }

  const indices: number[] = [];
  for (let segment = 0; segment < directions.length; segment += 1) {
    indices.push(0, 1 + segment, 1 + ((segment + 1) % directions.length));
  }
  for (let ring = 1; ring < rings; ring += 1) {
    const innerStart = 1 + (ring - 1) * directions.length;
    const outerStart = 1 + ring * directions.length;
    for (let segment = 0; segment < directions.length; segment += 1) {
      const next = (segment + 1) % directions.length;
      indices.push(innerStart + segment, outerStart + segment, innerStart + next);
      indices.push(innerStart + next, outerStart + segment, outerStart + next);
    }
  }
  return { positions, edgeAmounts, indices, rings, angularRadiusRad };
}

export interface ScreenRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export function screenRectsOverlap(first: ScreenRect, second: ScreenRect) {
  return first.left < second.right
    && first.right > second.left
    && first.top < second.bottom
    && first.bottom > second.top;
}

export function screenRectContains(outer: ScreenRect, inner: ScreenRect) {
  return inner.left >= outer.left
    && inner.right <= outer.right
    && inner.top >= outer.top
    && inner.bottom <= outer.bottom;
}

/**
 * A satellite label may only be drawn where the globe itself is on screen and
 * nothing is painted over it: outside the canvas it collides with the control
 * rail, and inside it collides with the floating cards.
 */
export function labelPlacementIsOccluded(
  label: ScreenRect,
  viewport: ScreenRect,
  occluders: readonly ScreenRect[],
) {
  if (!screenRectContains(viewport, label)) return true;
  return occluders.some((occluder) => screenRectsOverlap(label, occluder));
}

/** The subset of computed style the occlusion scan reads. */
export interface LabelOccluderStyle {
  display: string;
  visibility: string;
  opacity: string;
  backgroundColor: string;
  backdropFilter: string;
}

/** Alpha of a computed background-color string; 0 when it paints nothing. */
export function paintedBackgroundAlpha(backgroundColor: string): number {
  const value = backgroundColor.trim().toLowerCase();
  if (value === "" || value === "transparent" || value === "none") return 0;
  const channels = /^rgba?\(([^)]+)\)$/.exec(value);
  if (!channels) return 0;
  const parts = channels[1]!.split(/[\s,/]+/).filter((part) => part.length > 0);
  if (parts.length < 3) return 0;
  if (parts.length < 4) return 1;
  const alpha = Number.parseFloat(parts[3]!);
  if (!Number.isFinite(alpha)) return 0;
  return parts[3]!.endsWith("%") ? alpha / 100 : alpha;
}

/** Would this element visually hide the globe behind it? */
export function elementHidesGlobe(style: LabelOccluderStyle, minimumAlpha: number) {
  if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") return false;
  const opacity = Number.parseFloat(style.opacity);
  const resolvedOpacity = Number.isFinite(opacity) ? opacity : 1;
  if (resolvedOpacity < minimumAlpha) return false;
  const backdrop = style.backdropFilter.trim().toLowerCase();
  if (backdrop !== "" && backdrop !== "none") return true;
  return paintedBackgroundAlpha(style.backgroundColor) * resolvedOpacity >= minimumAlpha;
}

/** The minimum DOM surface the occlusion scan needs; real Elements satisfy it. */
export interface LabelOccluderCandidate {
  getBoundingClientRect(): ScreenRect;
  readonly children: ArrayLike<LabelOccluderCandidate>;
}

export interface LabelOccluderScanOptions {
  readStyle: (element: LabelOccluderCandidate) => LabelOccluderStyle | null;
  /** True for the globe container itself and anything opted out of the scan. */
  isGlobeSurface: (element: LabelOccluderCandidate) => boolean;
  /** True for ancestors of the globe: painted below it, so descend instead. */
  containsGlobeSurface: (element: LabelOccluderCandidate) => boolean;
  /** True for elements that declare themselves occluders regardless of style. */
  isDeclaredOccluder?: (element: LabelOccluderCandidate) => boolean;
  minimumAlpha?: number;
  maximumVisited?: number;
}

/**
 * Discover the on-screen regions that cover the globe, from the live DOM.
 *
 * Nothing here knows the name, selector or pixel position of any panel: an
 * element counts as an occluder because it overlaps the canvas and actually
 * paints over it, so a panel that moves, resizes, collapses or is added later
 * is picked up without changing this file.
 */
export function collectLabelOccluderRects(
  root: LabelOccluderCandidate,
  viewport: ScreenRect,
  options: LabelOccluderScanOptions,
): ScreenRect[] {
  const minimumAlpha = options.minimumAlpha ?? 0.25;
  const maximumVisited = options.maximumVisited ?? 4000;
  const rects: ScreenRect[] = [];
  const queue: LabelOccluderCandidate[] = [root];
  let cursor = 0;
  let visited = 0;
  while (cursor < queue.length && visited < maximumVisited) {
    const element = queue[cursor]!;
    cursor += 1;
    visited += 1;
    if (options.isGlobeSurface(element)) continue;
    const rect = element.getBoundingClientRect();
    const paints = rect.right > rect.left && rect.bottom > rect.top;
    const descends = options.containsGlobeSurface(element);
    if (!descends && (!paints || !screenRectsOverlap(rect, viewport))) continue;
    const style = options.readStyle(element);
    if (style && style.display === "none") continue;
    if (!descends && paints && (options.isDeclaredOccluder?.(element) || (style && elementHidesGlobe(style, minimumAlpha)))) {
      rects.push({
        left: Math.max(rect.left, viewport.left),
        top: Math.max(rect.top, viewport.top),
        right: Math.min(rect.right, viewport.right),
        bottom: Math.min(rect.bottom, viewport.bottom),
      });
      continue;
    }
    for (let index = 0; index < element.children.length; index += 1) queue.push(element.children[index]!);
  }
  return rects;
}

/** Right-handed mapping from GSM axes into this globe's scene axes. */
export function gsmSceneAxes(xGsm: number, yGsm: number, zGsm: number) {
  return new THREE.Vector3(xGsm, zGsm, yGsm === 0 ? 0 : -yGsm);
}

/** Scene-frame unit vector for a geographic latitude/longitude direction. */
function sceneDirectionFromLatLon(latitudeRad: number, longitudeRad: number) {
  return new THREE.Vector3(
    Math.cos(latitudeRad) * Math.cos(longitudeRad),
    Math.sin(latitudeRad),
    -Math.cos(latitudeRad) * Math.sin(longitudeRad),
  ).normalize();
}

/**
 * The Sun direction in scene coordinates — the exact computation
 * `setSimulationTime` applies, exported so the GSM-frame tests exercise the
 * production path rather than a re-derivation.
 */
export function sceneSunDirection(date: Date, frame: ReferenceFrame): THREE.Vector3 {
  const point = calculateSubsolarPoint(date);
  const direction = sceneDirectionFromLatLon(
    (point.latitudeDeg * Math.PI) / 180,
    (point.longitudeDeg * Math.PI) / 180,
  );
  if (frame === "inertial") {
    direction.applyAxisAngle(new THREE.Vector3(0, 1, 0), greenwichSiderealAngle(date));
  }
  return direction;
}

/**
 * The instantaneous geodipole axis (direction of the NORTH geomagnetic pole)
 * in the same scene coordinates the Earth mesh and `sunDirection` use. The
 * pole position comes from the IGRF-13 dipole coefficients `dipole-tilt.ts`
 * already carries (secular variation included), and the reference-frame spin
 * is exactly the one the Sun direction gets, so the two vectors can never
 * drift apart across the earth-fixed/inertial toggle.
 */
export function sceneDipoleAxisDirection(date: Date, frame: ReferenceFrame): THREE.Vector3 {
  const axis = dipoleAxis(decimalYear(date));
  const direction = sceneDirectionFromLatLon(
    (axis.poleLatitudeDeg * Math.PI) / 180,
    (axis.poleLongitudeDeg * Math.PI) / 180,
  );
  if (frame === "inertial") {
    direction.applyAxisAngle(new THREE.Vector3(0, 1, 0), greenwichSiderealAngle(date));
  }
  return direction;
}

/**
 * The full GSM frame for the sun-aligned group, as a quaternion.
 *
 * Everything inside `sunFrameGroup` is authored in GSM coordinates (through
 * `gsmSceneAxes`), and GSM is DEFINED by its roll about the Sun line: X points
 * at the Sun and the geodipole axis lies in the X–Z plane, Y dusk-positive.
 * The old `setFromUnitVectors(+x, sunDirection)` construction produced the
 * minimal rotation taking +x to the Sun, leaving that roll arbitrary — so the
 * field model's dipole tilt was applied in the wrong meridian, and the drawn
 * cusp/field-line footpoints ringed roughly the geographic pole while the
 * OVATION aurora (geographic coordinates on the Earth mesh) correctly ringed
 * the magnetic pole ~11° away, by an error that varied with time of day.
 *
 * Basis: X_gsm = sun direction; Y_gsm = m̂ × X̂ (m̂ the northern dipole axis),
 * which is dusk-positive and puts the axis in the X–Z plane by construction;
 * Z_gsm completes the right-handed set. The scene mapping (x, z, −y) is a
 * proper rotation, so the cross products hold unchanged in scene coordinates.
 */
export function gsmFrameQuaternion(
  sunDirection: THREE.Vector3,
  dipoleAxisDirection: THREE.Vector3,
): THREE.Quaternion {
  const xGsm = sunDirection.clone().normalize();
  const yGsm = new THREE.Vector3().crossVectors(dipoleAxisDirection, xGsm);
  if (yGsm.lengthSq() < 1e-12) {
    // Dipole axis along the Sun line — unreachable for Earth (the axis never
    // leans closer than ~55° to the Sun), but a defined fallback beats NaN.
    return new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1, 0, 0), xGsm);
  }
  yGsm.normalize();
  const zGsm = new THREE.Vector3().crossVectors(xGsm, yGsm).normalize();
  // Children hold GSM (X, Y, Z) in local (x, z, −y) per gsmSceneAxes, so the
  // group's local axes must map: +x → X_gsm, +y → Z_gsm, +z → −Y_gsm.
  const basis = new THREE.Matrix4().makeBasis(xGsm, zGsm, yGsm.clone().negate());
  return new THREE.Quaternion().setFromRotationMatrix(basis);
}
const missionColors: Record<MissionCapability, number> = {
  weather: 0x29d4e3,
  communications: 0xf5c96a,
  "missile-warning": 0xff7b78,
  navigation: 0xa98cff,
  "earth-observation": 0x76e6a5,
  science: 0x76e6a5,
  "human-spaceflight": 0xffffff,
  technology: 0xb9c9d3,
  other: 0xb9c9d3,
};

export interface SatelliteRenderState {
  latitudeRad: number;
  longitudeRad: number;
  altitudeKm: number;
  velocityKps: number;
}

export interface GlobeOptions {
  container: HTMLElement;
  satellites: SatelliteRecord[];
  land: LandGeoJson;
  onSelect: (index: number) => void;
  /**
   * A click that landed on no spacecraft. Ground-station pins sit on the
   * Earth's surface, under everything the satellite picker can hit, so they are
   * offered the click only after the spacecraft picker has declined it —
   * a spacecraft is the primary object on this globe and stays that way.
   */
  onEmptyPick?: (clientX: number, clientY: number) => void;
  onGeospaceFrame?: (validAt: string, leadMinutes: number, runAt: string) => void;
}

type GeospaceBundleWithStructures = Omit<GeospaceBundle, "frames"> & {
  structures?: GeospaceStructuresDefinition;
  frames: Array<GeospaceBundle["frames"][number] & { structures?: EncodedFrameStructures }>;
};

export function geospaceSuccessorIndex(frameIndex: number, frameCount: number) {
  if (frameCount <= 1) return 0;
  return Math.min(Math.max(0, frameIndex) + 1, frameCount - 1);
}

export function glotecQualityOpacity(quality: number | null) {
  // GloTEC quality_flag is a capped observation-count indicator, not a
  // categorical good/bad flag. Keep the background visible but restrained,
  // then add only a modest monotonic emphasis for better-observed profiles.
  const observationCount = quality === null || !Number.isFinite(quality)
    ? 0
    : Math.max(0, Math.min(5, quality));
  return 0.3 + (observationCount / 5) * 0.18;
}

export function longitudeTextureX(longitude: number, width: number) {
  const normalized = ((longitude + 180) % 360 + 360) % 360 - 180;
  return ((normalized + 180) / 360) * width;
}

/**
 * Width of the Earth's equirectangular basemap texture, in pixels.
 *
 * The basemap carries only low-frequency colour — the ocean gradient and the
 * land fill. Coastlines are drawn as geometry (see coastlineSegmentPositions)
 * because no raster can stay sharp here: at the closest camera distance the
 * globe fills the viewport with about 11 degrees of latitude, so a 2048-wide
 * map is magnified roughly 25 times and every texel edge is visible.
 *
 * 2048 is deliberate and measured, not a leftover. A 4096-wide basemap was
 * built and compared side by side at the deepest zoom: with the hard edges
 * moved off the raster, the two are indistinguishable, because what is left is
 * a smooth gradient and a land fill whose edge is covered by the drawn
 * coastline. It cost 33 MB of texture memory and about 16 ms per frame on the
 * software renderer, for no visible difference.
 *
 * Height is always half the width, because equirectangular means 360 degrees
 * of longitude across and 180 of latitude down.
 *
 * Cost, uncompressed RGBA with a full mip chain (x4/3): 2048 x 1024 -> 11.2 MB.
 */
export function earthTextureWidth(options: { maxTextureSize: number }) {
  // A device that cannot hold 2048 is not one this globe should be forcing a
  // basemap onto at all; 1024 keeps it drawing rather than failing.
  return Math.max(1024, Math.min(2048, options.maxTextureSize));
}

/**
 * Coastlines and borders as line segments on the sphere, in scene axes.
 *
 * Returned as an explicit pair-per-segment list rather than a polyline so that
 * rings which cross the antimeridian simply drop the wrapping segment instead
 * of drawing a line straight across the map — the same break the canvas path
 * used to make with moveTo.
 *
 * These points go through geoRadiansToSceneVector, the same function that
 * places satellites, ground tracks and the graticule. That is deliberate: it
 * makes the coastline registration true by construction rather than by a
 * separate texture convention that can drift 90 degrees out.
 */
export function coastlineSegmentPositions(land: LandGeoJson, radius: number) {
  const positions: number[] = [];
  // The source is country polygons, so every international border is a shared
  // edge that both neighbours carry. Drawing it once instead of twice removes
  // a quarter of the geometry and stops shared borders rendering brighter than
  // coastlines, which double-blending was making them. Natural Earth's
  // neighbouring rings share exact coordinates, so an exact key is enough.
  const drawn = new Set<string>();
  const pushRing = (ring: number[][]) => {
    if (ring.length < 2) return;
    for (let index = 1; index < ring.length; index += 1) {
      const from = ring[index - 1]!;
      const to = ring[index]!;
      const fromLon = from[0] ?? 0;
      const fromLat = from[1] ?? 0;
      const toLon = to[0] ?? 0;
      const toLat = to[1] ?? 0;
      // A step of more than half the world in longitude is the seam, not a coast.
      if (Math.abs(toLon - fromLon) > 180) continue;
      const forward = `${fromLon},${fromLat}|${toLon},${toLat}`;
      const backward = `${toLon},${toLat}|${fromLon},${fromLat}`;
      if (drawn.has(forward) || drawn.has(backward)) continue;
      drawn.add(forward);
      const a = geoToSceneVector(fromLat, fromLon, radius);
      const b = geoToSceneVector(toLat, toLon, radius);
      positions.push(a.x, a.y, a.z, b.x, b.y, b.z);
    }
  };
  land.features.forEach((feature) => {
    const polygons = feature.geometry.type === "Polygon"
      ? [feature.geometry.coordinates as number[][][]]
      : feature.geometry.coordinates as number[][][][];
    polygons.forEach((polygon) => polygon.forEach((ring) => pushRing(ring)));
  });
  return new Float32Array(positions);
}

/**
 * Solo mode overrides the filter-driven candidate set with just the selected
 * satellite, without mutating mission/constellation/owner filter state. When
 * Solo is off this simply reproduces the filtered set (plus the selection,
 * so a satellite excluded by filters still stays visible once selected) —
 * turning Solo back off therefore restores exactly the previous filter
 * result rather than a separately tracked snapshot.
 */
export function resolveVisibleIndices(
  filteredIndices: Iterable<number>,
  selectedIndex: number | null,
  soloSelected: boolean,
): Set<number> {
  if (soloSelected && selectedIndex !== null) return new Set([selectedIndex]);
  const indices = new Set(filteredIndices);
  if (selectedIndex !== null) indices.add(selectedIndex);
  return indices;
}

export interface SubsolarPoint {
  latitudeDeg: number;
  longitudeDeg: number;
}

function normalizeDegrees(degrees: number) {
  return ((degrees % 360) + 360) % 360;
}

/**
 * Approximate the geographic point directly beneath the Sun.
 *
 * This uses a compact solar-coordinate and sidereal-time calculation. It is
 * deterministic, inexpensive enough for an interactive time slider, and
 * comfortably more precise than the globe's schematic rendering requires.
 */
export function calculateSubsolarPoint(date: Date): SubsolarPoint {
  const timestamp = date.getTime();
  if (!Number.isFinite(timestamp)) throw new RangeError("Simulation time must be a valid Date");

  const julianDate = timestamp / 86_400_000 + 2_440_587.5;
  const daysSinceJ2000 = julianDate - 2_451_545;
  const meanLongitude = normalizeDegrees(280.46 + 0.9856474 * daysSinceJ2000);
  const meanAnomaly = normalizeDegrees(357.528 + 0.9856003 * daysSinceJ2000) * Math.PI / 180;
  const eclipticLongitude = normalizeDegrees(
    meanLongitude + 1.915 * Math.sin(meanAnomaly) + 0.02 * Math.sin(2 * meanAnomaly),
  ) * Math.PI / 180;
  const obliquity = (23.439 - 0.0000004 * daysSinceJ2000) * Math.PI / 180;
  const rightAscension = normalizeDegrees(Math.atan2(
    Math.cos(obliquity) * Math.sin(eclipticLongitude),
    Math.cos(eclipticLongitude),
  ) * 180 / Math.PI);
  const declination = Math.asin(Math.sin(obliquity) * Math.sin(eclipticLongitude)) * 180 / Math.PI;
  const julianCenturies = daysSinceJ2000 / 36_525;
  const greenwichSiderealTime = normalizeDegrees(
    280.46061837
      + 360.98564736629 * daysSinceJ2000
      + 0.000387933 * julianCenturies ** 2
      - julianCenturies ** 3 / 38_710_000,
  );
  const longitudeDeg = ((rightAscension - greenwichSiderealTime + 540) % 360) - 180;

  return { latitudeDeg: declination, longitudeDeg };
}

/**
 * The three empirical boundary fits' own colours.
 *
 * Module-level and exported so the legend can print a swatch from the very
 * constant the material reads: `MAGNETOPAUSE_SURFACE_STYLE` below takes its
 * `color` from here, so a swatch and the pixels it points at cannot drift
 * apart. Same rule as `EXTERIOR_CUSP_COLOR` and `GEOSPACE_BOUNDARY_COLORS`.
 */
/**
 * The probed point's marker.
 *
 * Deliberately NOT the satellite selection cyan and deliberately not that
 * glyph: a filled dot inside a ring already means "this spacecraft is
 * selected", and a probe answers about a PLACE. Amber, and an open crosshair
 * with nothing in the middle, because the middle is the thing being asked
 * about and covering it would be the one mistake this marker can make.
 */
export const PROBE_POINT_COLOR = "255, 190, 105";

/**
 * Is a point on the globe's surface on the face turned toward the camera?
 *
 * Pulled out as a pure function because it is the whole of the probe marker's
 * hide-on-the-far-side rule, and a rule that can only be checked by orbiting a
 * software-rendered globe and counting amber pixels is a rule that will not get
 * checked. Here it is four numbers and an inequality.
 *
 * The point's outward normal is the point itself, the Earth's centre being the
 * origin, so the near face is exactly `normal · (camera − point) > 0`. Written
 * against the camera POSITION rather than its view direction so it stays
 * correct for a perspective camera close in, where "toward the camera" and
 * "toward the middle of the screen" are not the same question.
 */
export function probePointFacesCamera(point: THREE.Vector3, cameraPosition: THREE.Vector3): boolean {
  return point.dot(cameraPosition) > point.lengthSq();
}

export const MAGNETOPAUSE_MODEL_COLORS: Record<MagnetopauseModelId, number> = {
  shue1998: 0x77e3d2,
  nguyen2022: 0x8fd7ff,
  lin2010: 0xc7a6ff,
};

/**
 * THE AMBER OF THE CUSP FUNNELS. One copy, because the legend now names it.
 *
 * These two funnels are the only thing the magnetosphere layer's default face
 * draws that is not on its colour ramp, and on the shipped build nothing on the
 * page said what they were. Sean read them as bow shocks — an understandable
 * reading of a large warm surface standing off the dayside, and the wrong way
 * round: a bow shock is where the solar wind is STOPPED, well upstream of
 * everything else here, while the cusp is the one place on the dayside where it
 * gets IN. A swatch that names them has to be the same colour as the thing it
 * names, so both the material and the legend read this.
 */
export const EXTERIOR_CUSP_COLOR = 0xffb257;

export class SpaceGlobe {
  private readonly container: HTMLElement;
  private readonly satellites: SatelliteRecord[];
  private readonly scene = new THREE.Scene();
  private readonly camera: THREE.PerspectiveCamera;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly controls: OrbitControls;
  private readonly starField: THREE.Points;
  private readonly satelliteMesh: THREE.Points;
  private readonly satelliteMaterial: THREE.ShaderMaterial;
  private readonly satellitePositions: THREE.BufferAttribute;
  private readonly satelliteColors: THREE.BufferAttribute;
  private readonly satelliteFrom: Float32Array;
  private readonly satelliteTargets: Float32Array;
  private readonly satelliteRenderable: Uint8Array;
  private readonly visible = new Set<number>();
  private readonly latestStates: Array<SatelliteRenderState | null>;
  private readonly pickViewProjection = new THREE.Matrix4();
  private readonly geoPickRaycaster = new THREE.Raycaster();
  private readonly hoverLabel: HTMLDivElement;
  private readonly selectedLabel: HTMLDivElement;
  private readonly earthFixedGroup = new THREE.Group();
  private readonly satelliteFrameGroup = new THREE.Group();
  private readonly sunFrameGroup = new THREE.Group();
  private readonly selectionOrbitGroup = new THREE.Group();
  private readonly selectionEarthGroup = new THREE.Group();
  private readonly selectionFootprintGroup = new THREE.Group();
  private readonly selectionMarker: THREE.Sprite;
  /** Where the reader last asked a question about a place. Built once, moved, never rebuilt. */
  private readonly probePointMarker: THREE.Sprite;
  /** Whether a place is being probed at all. The facing test decides the rest. */
  private probePointVisible = false;
  private readonly probePointScratch = new THREE.Vector3();
  private readonly regionGroup = new THREE.Group();
  private readonly geospaceGroup = new THREE.Group();
  private readonly solarWindGroup = new THREE.Group();
  private readonly photonGroup = new THREE.Group();
  private readonly sunLight = new THREE.DirectionalLight(0xdffaff, 2.3);
  private readonly sunDirection = new THREE.Vector3(1, 0, 0);
  private readonly magnetosphere: THREE.Group;
  private ionosphereVolume: IonosphereVolumeLayer | null = null;
  /**
   * The ray-marched electron-density field, drawn with the peak surfaces
   * rather than instead of them: the volume shows the column TEC integrates,
   * the surfaces show where the published peak criterion actually found a
   * distinct E or F1 maximum. See `ionosphere-density-volume.ts`.
   */
  private ionosphereDensityVolume: IonosphereDensityVolumeLayer | null = null;
  /**
   * Earth's own limb glow. Held so it can step aside for the ionosphere; see
   * `applyAirglowVisibility`.
   */
  private airglowShell: THREE.Mesh | null = null;
  private ionospherePhotonFluxWm2: number | null = null;
  private readonly dRegionEmpirical = new EmpiricalDRegionLayer(EARTH_SCENE_RADIUS);
  private ionosphereVolumeEnabled = false;
  private ionosphereVolumeDataAvailable = false;
  private readonly ionosphere: THREE.Mesh;
  private readonly aurora: THREE.Mesh;
  private readonly onGeospaceFrame?: (validAt: string, leadMinutes: number, runAt: string) => void;
  private geospace: GeospaceBundle | null = null;
  private geospaceRuntime: GeospaceRuntime | null = null;
  // Density is the opening field — see the note in GeospaceRuntime's
  // constructor. The UI's default field button must match.
  private geospaceField: GeospaceField = "density";
  // Meridional is the opening cut — the noon-midnight plane of every textbook
  // figure, and the runtime's own default. The UI's default plane button must
  // match both.
  private geospacePlaneMode: GeospacePlane | "both" = "meridional";
  private radiationEnergyKev = DEFAULT_RADIATION_ENERGY_KEV;
  private radiationPitchIndex: number | null = null;
  private radiationView: RadiationBeltRuntimeView = "dipoleMapped3d";
  private geospaceSimulationTimeMs: number | null = null;
  private solarWindModelFrameValidAt: string | null | undefined;
  private readonly solarWindVisual: SolarWindVisual;
  private readonly xrayVisual: XrayIrradianceVisual;
  private drapSurface: DrapSurfaceLayerController | null = null;
  private auroraHistorySurface: AuroraSurfaceLayerController | null = null;
  private thermosphere: ThermosphereVolumeLayer | null = null;
  private thermosphereEnabled = false;
  private groundField: GroundPerturbationLayer | null = null;
  private groundFieldBundle: GroundFieldBundle | null = null;
  private groundFieldSystem: GroundCurrentSystemKey = "total";
  private groundFieldLayerEnabled = false;
  private animationFrame = 0;
  private hoverPickAnimationFrame = 0;
  private pendingHoverPointer: { clientX: number; clientY: number } | null = null;
  private selectionPointerDown: { clientX: number; clientY: number } | null = null;
  private lastFrameTime = performance.now();
  private lastRenderedAt = performance.now();
  private interpolationStartedAt = performance.now();
  private interpolationDurationMs = 0;
  private interpolationActive = false;
  private environmentalAnimationElapsedSeconds = 0;
  private auroraPoints: AuroraPoint[] = [];
  private tecPoints: TecPoint[] = [];
  private tecRange: [number, number] = [0, 1];
  private auroraHemisphere: "both" | "north" | "south" = "both";
  private selectedIndex: number | null = null;
  private hoverIndex: number | null = null;
  /** True while the reader has armed an explicit "click a place" pick. */
  private pointPickModeValue = false;
  private labelOccluders: ScreenRect[] = [];
  private labelViewport: ScreenRect | null = null;
  private lastLabelOcclusionScanAt = 0;
  private rendererPixelRatioCap = 1.75;
  private maximumFrameRate = 60;
  private earthMaterial!: THREE.MeshStandardMaterial;
  private coastlineMaterial!: THREE.ShaderMaterial;
  private coastlines!: THREE.LineSegments;
  private environmentalMotionEnabled = true;
  private satelliteLabelsEnabled = true;
  private referenceFrame: ReferenceFrame = "earth-fixed";
  private fieldRendering: FieldRendering = "smooth";
  private simulationTime = new Date();
  private selectedOrbitFrameRotationY = 0;
  /**
   * The outermost drawn radius of the selected spacecraft's orbit line, in
   * scene units, measured off the vertices as they are built. `focusSatellite`
   * frames this; the box-corner radius would over-frame a tilted ellipse by up
   * to 41%.
   */
  private selectedOrbitDrawnReach = 0;
  /**
   * A new set of spacecraft has been asked for and has not been framed yet.
   *
   * The visible set and the POSITIONS of that set arrive in two different
   * calls: `setVisible` says who is drawn, and the propagator's solution
   * lands in `updateSatellites` some time later. Framing at `setVisible`
   * would measure a set that is still at the origin, so the decision is held
   * here until the first solution that actually covers the new set. It is the
   * same shape as the re-frame `setGeospaceModel` does when its bundle lands.
   */
  private satelliteFramingPending = false;
  private selectedFootprintVisible = false;
  private lastFootprintVisualAt = 0;
  private footprintMinElevationDeg = 0;
  private cameraDolly: { fromDistance: number; toDistance: number; fromTarget: THREE.Vector3; startedAt: number; durationMs: number } | null = null;
  /**
   * The distance the view last chose for itself. Comparing it with where the
   * camera actually is tells us whether the visitor has zoomed by hand since,
   * without having to listen to control events that also fire when they only
   * rotate the globe.
   */
  private autoFrameDistance: number | null = null;
  /**
   * The camera as it stood when the visitor left the teaching scale, restored
   * verbatim when they return — the toggle must never cost anyone their view.
   */
  private teachingCameraState: {
    position: THREE.Vector3;
    up: THREE.Vector3;
    target: THREE.Vector3;
    autoFrameDistance: number | null;
  } | null = null;
  /**
   * The last selection geometry as handed in, in physical coordinates, so a
   * distance-scale change can redraw the orbit line and footprint through the
   * new ruler without asking the worker to recompute anything.
   */
  private lastSelectedGeometryInputs: {
    orbitPoints: Array<{ latitudeDeg: number; longitudeDeg: number; altitudeKm: number }>;
    groundPoints: Array<[number, number]>;
    footprint: Array<[number, number]>;
    frameDate: Date;
  } | null = null;
  /** Kept for distance-scale rebuilds; the layer bakes positions at build. */
  private ionosphereBundle: IonosphereVolumeBundle | null = null;
  private magnetosphereLayerEnabled = false;
  private magnetosphereDataAvailable = true;
  /** Live Shue subsolar standoff, in Earth radii; the framing helper needs it. */
  private magnetopauseStandoffRe = 9.5;
  private geospaceLayerEnabled = false;
  /** Named cross-section regions switched on independently of the cut planes. */
  private readonly structureRegions = new Set<GeospaceStructureRegion>();
  private radiationLayerEnabled = false;
  /**
   * The derived plasma-beta cut. A layer of its own, not a setting of the
   * magnetosphere layer, because it answers a different question — where the
   * plasma is in charge rather than how much of it there is — and because a
   * reader wants it beside the field lines it explains, not buried under them.
   */
  private plasmaSheetLayerEnabled = false;
  private plasmaSheetPlaneMode: GeospacePlane | "both" = "meridional";
  private drapLayerEnabled = false;
  private auroraLayerEnabled = false;
  private solarWindLayerEnabled = false;
  private solarWindDataAvailable = true;
  private photonLayerEnabled = false;
  private photonDataAvailable = true;
  private disposed = false;
  /**
   * Which magnetopause surfaces are drawn when the drivers support them.
   *
   * All three, deliberately, and there is no user control. Nguyen's current
   * sheet and Lin's cusp inner boundary are the pair whose *difference* is the
   * exterior cusp, and they carry the dayside. Shue is kept because it is the
   * only one of the three fitted down the tail — it is drawn from where the
   * other two stop, so the familiar tail survives without a smooth surface
   * being laid over the indentations that are the point.
   */
  private readonly magnetopauseModels: readonly MagnetopauseModelId[] = [
    "nguyen2022",
    "lin2010",
    "shue1998",
  ];
  /**
   * THE POLAR-CUSP FUNNELS: OFF UNTIL THE READER ASKS FOR THEM.
   *
   * They used to be drawn unconditionally, and Sean read the two orange
   * funnels as a bow shock -- which is close to their opposite. Naming them in
   * the legend and on the card fixed the WORDS; this flag fixes WHEN. Sean, on
   * the shipped build of 2026-08-26: "I see the polar cusps, but I think what
   * we should do is hide them, but have them able to be toggled in the layer
   * browser ... The cusps would only be shown in the legend and on the screen
   * if the user wants to see them."
   *
   * ONE flag for BOTH places this class draws that amber surface, because a
   * reader who switched them off must not meet them again by opening some
   * other annotation: the context funnel beside the traced field lines
   * (`field-line-context-exterior-cusp`) and the shaded volume between Lin and
   * Nguyen inside the empirical boundary annotation (`empirical-exterior-cusp`
   * and `empirical-exterior-cusp-cross-section`). `annotate-polar-cusps`, in
   * this layer's own settings, is its only control.
   */
  private cuspFunnelsEnabledValue = false;
  private magnetopauseLegendEntries: MagnetopauseLegendEntry[] = [];
  private magnetopauseFallbackReason: string | null = null;
  /**
   * How the empirical boundary set is presented. `surface` is the closed
   * translucent shell; `cross-section` is the textbook cut — profile curves in
   * the noon-midnight meridian and the dawn-dusk plane, with the exterior-cusp
   * funnel filled only where the two published surfaces genuinely cross.
   * A closed shell viewed from outside is one blob (its near and far walls
   * pile up), which is why every printed figure of this system is a cut.
   */
  private magnetopauseDisplayValue: "surface" | "cross-section" = "surface";
  private lastMagnetopauseDriver: MagnetopauseDriverSample | null = null;
  /** The animated cusp-entry cue: rebuilt with the surfaces, animated per frame. */
  private cuspEntryTracks: Array<{ points: THREE.Vector3[]; cumulative: number[]; total: number }> = [];
  private cuspEntryPoints: THREE.Points | null = null;
  private cuspEntryElapsedSeconds = 0;
  /**
   * The 3-D magnetosphere: driven field lines traced through the
   * dipole + Chapman–Ferraro image + Harris-tail construction, inside a
   * subtle copy of the live empirical boundary. This is what the
   * `geospace` layer shows by default; the NOAA MHD cut is the layer's
   * embedded cross-section OPTION, not its face.
   */
  private readonly fieldLineGroup = new THREE.Group();
  /** The cusp-entry cue in its own group so field lines, boundary annotation and solar wind can all share it. */
  private readonly cuspEntryGroup = new THREE.Group();
  private fieldLineSignature = "";
  /**
   * The traced set the guided solar wind is currently riding, held so the
   * guidance can be rebuilt when a LAYER changes without re-tracing the field.
   *
   * A trace costs 25-60 ms. Switching the plasma-sheet or auroral layer on
   * changes which legs of the Dungey cycle the guided particles are given, and
   * that is a rebuild of a few dozen polylines, not of the magnetosphere.
   */
  private tracedFieldLinesValue: readonly TracedFieldLine[] | null = null;
  /** Guards the guidance rebuild, which now depends on layers as well as on drivers. */
  private fieldGuidanceSignature = "";
  private fieldLineSummaryValue: FieldLineSummary | null = null;
  /** The per-rebuild integrity check of the traced set; null before the first trace. */
  private fieldLineIntegrityValue: FieldLineIntegrityReport | null = null;
  /**
   * Whether the two amber CUSP FUNNELS are currently in the scene beside the
   * traced lines.
   *
   * They are the only thing this layer draws that is not on its colour ramp,
   * and they are conditional — `cuspedDrivers` refuses without a dipole tilt,
   * an IMF clock angle and a magnetic pressure — so the legend has to be told
   * whether they exist rather than assuming they do. A legend entry for a
   * surface that is not drawn is the same defect as a drawn surface with no
   * legend entry, pointing the other way.
   */
  private fieldLineCuspFunnelsValue = false;
  /** The per-frame MHD magnetopause calibration; null = Shue-from-L1. */
  private fieldLineCalibration: BoundaryCalibration | null = null;
  /** Whether the NOAA MHD cut planes are shown inside the 3-D scene. */
  private mhdCutEnabledValue = false;
  /**
   * The formation loop the ring current is currently drawing, and the legend
   * swatch that breathes with it.
   *
   * Both live here because the animation frame is where the ring current's
   * clock actually advances. Handing the swatch the SAME
   * `environmentalAnimationElapsedSeconds` the volume is handed, a few lines
   * apart, is what makes the two agree by construction: there is no second
   * duration anywhere for them to drift apart on, and the swatch freezes with
   * the volume the instant environmental motion is switched off.
   */
  private ringCurrentFormationState: RingCurrentFormation | null = null;
  private ringCurrentPulseSurface: HTMLElement | null = null;
  private plasmasphereLayerEnabled = false;
  private readonly plasmasphereGroup = new THREE.Group();
  private plasmasphereFieldState: PlasmasphereLayerField | null = null;
  /**
   * The drawn stipple, kept so the render loop can advance its corotation.
   *
   * The grains stream through a sun-fixed density field; the angle they have
   * turned through is a uniform, so advancing it is one assignment per frame
   * rather than any work per grain.
   */
  private plasmasphereObject: THREE.Points | null = null;
  /**
   * The ring-current ILLUSTRATION: drift paths, the Alfven layer for the
   * selected ion energy, and the drifting ions themselves.
   *
   * It sits in the sun-fixed group beside the plasmasphere because it is drawn
   * in the same magnetic local time frame and, more to the point, because it is
   * computed in the SAME convection field — see `src/ring-current-illustration.ts`.
   * Nothing in it is measured, and every surface that shows it says so.
   */
  private ringCurrentLayerEnabled = false;
  /**
   * The inner plasma sheet rides on the RING-CURRENT toggle, not on one of its
   * own. Sean: "Potentially ring current and plasma sheet as one option if they
   * are that closely related." They are the same injection seen at two radii,
   * and separate switches would let a reader turn off the cause and keep the
   * effect. It also means this ships without adding a row to a rail that is
   * already at its budget.
   */
  private innerPlasmaSheet: InnerPlasmaSheet | null = null;
  private substormStateValue: SubstormState | null = null;
  private readonly ringCurrentGroup = new THREE.Group();
  private ringCurrentState: RingCurrentIllustration | null = null;
  /** The drifting-ion markers, kept so the render loop can advance them. */
  private ringCurrentObject: THREE.Object3D | null = null;

  constructor({ container, satellites, land, onSelect, onEmptyPick, onGeospaceFrame }: GlobeOptions) {
    this.container = container;
    this.satellites = satellites;
    this.onGeospaceFrame = onGeospaceFrame;
    this.latestStates = satellites.map(() => null);
    // OrbitControls never lets the camera closer than minDistance = 125 to the
    // origin, so the nearest geometry is ~25 units away and a near plane of 1
    // clips nothing. It buys a 10x finer depth buffer everywhere, which is
    // what keeps translucent surfaces drawn within a scene unit of the globe
    // resolvable on 16-bit depth contexts.
    this.camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 1, 3600);
    // Direction only; the distance is chosen below from DEFAULT_VIEW_SCENE_RADIUS
    // through the same framing helper the automatic re-framing uses.
    this.camera.position.set(0, 70, 330);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, this.rendererPixelRatioCap));
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.append(this.renderer.domElement);
    this.hoverLabel = this.buildSatelliteLabel("satellite-map-label satellite-map-label--hover");
    this.selectedLabel = this.buildSatelliteLabel("satellite-map-label satellite-map-label--selected");
    container.append(this.hoverLabel, this.selectedLabel);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.055;
    this.controls.minDistance = 125;
    // The shared radial ruler puts the -50 Re magnetotail cut near 720 scene
    // units and the SWMF cut-plane corner near 740. Framing that corner with
    // VIEW_EDGE_MARGIN_FRACTION clear costs 3.06 x its radius on the desktop
    // scene (1050x832 beside the rail, 42-degree FOV, height binding) — 2,265
    // — so the dolly has to reach 2,500 or the deepest layer would frame
    // against this limit instead of against the rule, as it did at 2,200. The
    // far plane at 3,600 still holds the whole scene from there: 2,500 of
    // distance plus 740 of reach.
    //
    // A phone is deliberately NOT covered. The scene is 390x746 there, aspect
    // 0.52, and the narrow side turns the same fit into 5.63 x radius: 3,319
    // for the magnetopause reach and 4,163 for that corner, at which Earth
    // would draw 58 px across. The outer magnetosphere therefore still frames
    // against this limit on a phone rather than shrink the subject of the
    // site to a dot for a tail every reference depiction crops anyway.
    // Measured at the limit, the boundary fills 86% of the width and the
    // polar preset is cut off at 100% — unchanged in kind from the old 2,200
    // (89% and 100%), and the one place where the margin above is answered by
    // a clamp rather than by the rule.
    this.controls.maxDistance = 2500;
    this.controls.enablePan = false;
    // Sean asked the site to open "just a touch" zoomed out. Doing it here,
    // through the same helper the automatic re-framing uses, is what keeps the
    // opening view and every later framing decision on one rule.
    this.camera.position.setLength(this.distanceToFrame(DEFAULT_VIEW_SCENE_RADIUS));
    this.autoFrameDistance = this.camera.position.length();
    // The pose above, reachable from a driven test of the REAL page.
    //
    // `main.ts` keeps its globe private and publishes nothing, which is right;
    // this is the one quantity a test of the camera-authority rule has to be
    // able to read, and there is exactly one globe on a page. A function
    // rather than the object, so what a caller gets is always the pose NOW and
    // never a stale snapshot, and read-only in both directions: it hands back
    // arrays and numbers, and there is no setter beside it.
    if (typeof window !== "undefined") {
      (window as unknown as Record<string, unknown>).spaceCameraPose = () => this.cameraPose();
    }

    this.starField = this.buildStars();
    this.scene.add(this.starField);
    this.earthFixedGroup.add(this.buildEarth(land));
    this.earthFixedGroup.add(this.buildCoastlines(land));
    this.earthFixedGroup.add(this.buildGraticule());
    this.scene.add(this.earthFixedGroup);
    this.airglowShell = this.buildAtmosphere();
    this.scene.add(this.airglowShell);

    const markerGeometry = new THREE.BufferGeometry();
    this.satellitePositions = new THREE.BufferAttribute(new Float32Array(satellites.length * 3), 3);
    this.satelliteFrom = new Float32Array(satellites.length * 3);
    this.satelliteTargets = new Float32Array(satellites.length * 3);
    this.satelliteRenderable = new Uint8Array(satellites.length);
    this.satellitePositions.setUsage(THREE.DynamicDrawUsage);
    markerGeometry.setAttribute("position", this.satellitePositions);
    const markerColors = new Float32Array(satellites.length * 3);
    satellites.forEach((satellite, index) => {
      new THREE.Color(missionColors[satellite.mission]).toArray(markerColors, index * 3);
    });
    this.satelliteColors = new THREE.BufferAttribute(markerColors, 3);
    markerGeometry.setAttribute("color", this.satelliteColors);
    this.satelliteMaterial = new THREE.ShaderMaterial({
      uniforms: {
        pointSize: { value: 3.4 },
        pixelRatio: { value: this.renderer.getPixelRatio() },
      },
      vertexColors: true,
      transparent: true,
      depthTest: true,
      depthWrite: false,
      vertexShader: `
        uniform float pointSize;
        uniform float pixelRatio;
        varying vec3 markerColor;
        void main() {
          markerColor = color;
          gl_PointSize = pointSize * pixelRatio;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 markerColor;
        void main() {
          float radius = length(gl_PointCoord - vec2(0.5));
          if (radius > 0.5) discard;
          float edge = 1.0 - smoothstep(0.32, 0.5, radius);
          float glow = 1.0 - smoothstep(0.08, 0.5, radius);
          gl_FragColor = vec4(markerColor * (1.05 + glow * 0.35), edge * 0.94);
        }
      `,
    });
    this.satelliteMesh = new THREE.Points(markerGeometry, this.satelliteMaterial);
    this.satelliteMesh.frustumCulled = false;
    this.satelliteFrameGroup.add(this.satelliteMesh);
    this.scene.add(this.satelliteFrameGroup);

    this.selectionMarker = this.buildSelectionMarker();
    this.selectionMarker.visible = false;
    this.satelliteFrameGroup.add(this.selectionMarker);

    // The probe marker goes in the EARTH-FIXED group, not the satellite frame:
    // it names a place on the ground, so it has to turn with the ground. Its
    // depth test is on, which is what makes it disappear behind the globe when
    // the point it marks rotates to the far side — the correct behaviour, and
    // free.
    this.probePointMarker = this.buildProbePointMarker();
    this.probePointMarker.visible = false;
    this.earthFixedGroup.add(this.probePointMarker);

    this.ionosphere = this.buildIonosphere();
    this.ionosphere.visible = false;
    this.earthFixedGroup.add(this.ionosphere);
    this.dRegionEmpirical.mesh.visible = false;
    this.earthFixedGroup.add(this.dRegionEmpirical.mesh);

    this.aurora = this.buildAurora();
    this.aurora.visible = false;
    this.earthFixedGroup.add(this.aurora);

    this.regionGroup.visible = false;
    this.buildRegions();
    this.earthFixedGroup.add(this.regionGroup);

    this.magnetosphere = this.buildMagnetosphere();
    this.magnetosphere.visible = false;
    this.sunFrameGroup.add(this.magnetosphere);

    this.fieldLineGroup.name = "driven-magnetosphere-field-lines";
    this.fieldLineGroup.visible = false;
    this.fieldLineGroup.userData.method = FIELD_LINE_METHOD;
    this.sunFrameGroup.add(this.fieldLineGroup);

    this.cuspEntryGroup.name = "cusp-entry-cue";
    this.cuspEntryGroup.visible = false;
    this.sunFrameGroup.add(this.cuspEntryGroup);

    this.ringCurrentGroup.name = "ring-current-illustration";
    this.ringCurrentGroup.visible = false;
    this.sunFrameGroup.add(this.ringCurrentGroup);


    this.innerPlasmaSheet = new InnerPlasmaSheet({
      positionForGsm: (xRe, yRe, zRe) => this.modelGsmPosition(xRe, yRe, zRe),
    });
    this.sunFrameGroup.add(this.innerPlasmaSheet.group);

    this.plasmasphereGroup.name = "empirical-plasmasphere";
    this.plasmasphereGroup.visible = false;
    this.sunFrameGroup.add(this.plasmasphereGroup);

    this.geospaceGroup.visible = false;
    this.sunFrameGroup.add(this.geospaceGroup);

    this.solarWindVisual = createSolarWindVisual({
      earthRadiusRe: 1,
      magnetopauseStandoffRe: 9.5,
      positionForGsm: (xRe, yRe, zRe) => this.modelGsmPosition(xRe, yRe, zRe),
      positionForPlane: (xRe, crossRe, plane) => this.modelPlanePosition(xRe, crossRe, plane),
      pixelRatio: this.renderer.getPixelRatio(),
      modelSecondsPerDisplaySecond: 45,
      // RAISED FROM 2,200 ON 2026-08-27. Sean: *"the particles are a bit too
      // small and diffuse now."* The upstream face is now cut to the frame,
      // which is about five times wider in drawn radius than the 22 Rₑ disc it
      // replaced, so the same 2,200 tracers would have covered five times the
      // page at a fifth of the density. The count and the glyph size move
      // together with the face, which is why they are one change.
      particleCount: 4600,
      // The published cuts carry only ~11 flow paths per plane, so at the
      // default 3 tracers per path the model-projected mode drew about 66
      // points where the fallback draws 2,200 — switching to the *better*
      // evidence made the layer look like it had turned off. Two dozen
      // tracers per path keep each path a visibly beaded stream, and the
      // beads' spacing is the model's own local speed: they bunch where the
      // shock slows the flow.
      tracersPerModelPath: 24,
      // In scene units, on the shared ruler. A tracer streak has to survive
      // the log radial compression at 30 Re and still be a few pixels long, or
      // the deflection is only visible to someone already watching for it.
      trailLength: 20,
    });
    this.solarWindGroup.add(this.solarWindVisual.group);
    this.solarWindGroup.visible = false;
    this.sunFrameGroup.add(this.solarWindGroup);

    this.xrayVisual = createXrayIrradianceVisual({
      earthRadius: EARTH_SCENE_RADIUS,
      upperAtmosphereRadius: EARTH_SCENE_RADIUS * 1.035,
      pixelRatio: this.renderer.getPixelRatio(),
      // Only the beam's entry distance goes through the shared mapping; the
      // rays themselves are straight in the drawn scene, which is where the
      // reader judges whether light is deflected. See the note above
      // `buildXrayPhotonRays`.
      positionForGsm: (xRe, yRe, zRe) => this.modelGsmPosition(xRe, yRe, zRe),
      photonUpstreamStartRe: 34,
    });
    this.photonGroup.add(this.xrayVisual.group);
    this.photonGroup.visible = false;
    this.sunFrameGroup.add(this.photonGroup);

    this.scene.add(this.sunFrameGroup, this.selectionOrbitGroup, this.selectionEarthGroup, this.selectionFootprintGroup);

    const ambient = new THREE.AmbientLight(0x497484, 0.9);
    this.setSimulationTime(new Date());
    this.scene.add(ambient, this.sunLight);

    this.renderer.domElement.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch" || !this.satelliteLabelsEnabled) return;
      this.pendingHoverPointer = { clientX: event.clientX, clientY: event.clientY };
      if (this.hoverPickAnimationFrame !== 0) return;
      this.hoverPickAnimationFrame = requestAnimationFrame(() => {
        this.hoverPickAnimationFrame = 0;
        const pointer = this.pendingHoverPointer;
        this.pendingHoverPointer = null;
        if (!pointer || this.disposed || !this.satelliteLabelsEnabled) return;
        const index = this.pickSatellite(pointer.clientX, pointer.clientY, 12);
        this.hoverIndex = index === this.selectedIndex ? null : index;
        if (this.hoverIndex === null) {
          this.hoverLabel.classList.remove("is-visible");
          return;
        }
        this.setSatelliteLabel(this.hoverLabel, this.hoverIndex);
        // Place through the same path the render loop uses so a label that
        // lands under a panel is never shown even for a single frame.
        this.refreshLabelOcclusion(performance.now());
        this.positionSatelliteLabel(this.hoverLabel, this.hoverIndex);
      });
    });
    this.renderer.domElement.addEventListener("pointerleave", () => {
      this.pendingHoverPointer = null;
      if (this.hoverPickAnimationFrame !== 0) cancelAnimationFrame(this.hoverPickAnimationFrame);
      this.hoverPickAnimationFrame = 0;
      this.hoverIndex = null;
      this.hoverLabel.classList.remove("is-visible");
    });
    this.renderer.domElement.addEventListener("pointerdown", (event) => {
      this.selectionPointerDown = { clientX: event.clientX, clientY: event.clientY };
    });
    this.renderer.domElement.addEventListener("pointerup", (event) => {
      const start = this.selectionPointerDown;
      this.selectionPointerDown = null;
      if (!start || Math.hypot(event.clientX - start.clientX, event.clientY - start.clientY) > 6) return;
      // In POINT PICK MODE the reader has said, in the interface, that their
      // next click is about a PLACE. Spacecraft stop intercepting it: an
      // armed pick that quietly opened a satellite card because a marker
      // happened to be over the Pacific would be the mode failing silently,
      // which is the one thing an explicit mode must never do.
      const index = this.pointPickModeValue ? null : this.pickSatellite(event.clientX, event.clientY, 18);
      if (index !== null) onSelect(index);
      else onEmptyPick?.(event.clientX, event.clientY);
    });
    this.renderer.domElement.addEventListener("pointercancel", () => { this.selectionPointerDown = null; });

    window.addEventListener("resize", this.resize);
    this.animate();
  }

  private resize = () => {
    if (this.disposed) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, this.rendererPixelRatioCap));
    this.satelliteMaterial.uniforms.pixelRatio!.value = this.renderer.getPixelRatio();
    // Every panel rectangle just moved; do not wait out the scan throttle.
    this.lastLabelOcclusionScanAt = 0;
    this.geospaceRuntime?.setPixelRatio(this.renderer.getPixelRatio());
    this.solarWindVisual.setPixelRatio(this.renderer.getPixelRatio());
    this.xrayVisual.setPixelRatio(this.renderer.getPixelRatio());
    this.renderer.setSize(width, height);
  };

  /**
   * The Earth's basemap: ocean and land colour only.
   *
   * Everything with a hard edge has moved off this canvas. Coastlines are now
   * geometry (buildCoastlines) and the graticule already was (buildGraticule),
   * which is what lets the globe stay sharp when the camera comes in close.
   * What is left here is smooth colour, so magnifying it is not visible.
   */
  private paintEarthCanvas(land: LandGeoJson, width: number) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = width / 2;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas 2D is unavailable");

    const ocean = context.createLinearGradient(0, 0, 0, canvas.height);
    ocean.addColorStop(0, "#0b2c3a");
    ocean.addColorStop(0.5, "#061a25");
    ocean.addColorStop(1, "#092b38");
    context.fillStyle = ocean;
    context.fillRect(0, 0, canvas.width, canvas.height);

    const drawRing = (ring: number[][], fill: boolean) => {
      if (ring.length < 2) return;
      context.beginPath();
      let previousX: number | null = null;
      ring.forEach((coordinate, index) => {
        const lon = coordinate[0] ?? 0;
        const lat = coordinate[1] ?? 0;
        const x = ((lon + 180) / 360) * canvas.width;
        const y = ((90 - lat) / 180) * canvas.height;
        if (index === 0 || (previousX !== null && Math.abs(x - previousX) > canvas.width / 2)) context.moveTo(x, y);
        else context.lineTo(x, y);
        previousX = x;
      });
      if (fill) context.fill();
      // Stroked in the fill colour, not a coastline colour: this only closes
      // the half-covered pixels along the edge of the fill so the boundary is
      // antialiased into the land instead of stair-stepping out of it.
      context.stroke();
    };
    context.fillStyle = "#143842";
    context.strokeStyle = "#143842";
    context.lineWidth = 1;
    land.features.forEach((feature) => {
      const polygons = feature.geometry.type === "Polygon"
        ? [feature.geometry.coordinates as number[][][]]
        : feature.geometry.coordinates as number[][][][];
      polygons.forEach((polygon) => polygon.forEach((ring, ringIndex) => drawRing(ring, ringIndex === 0)));
    });
    return canvas;
  }

  private buildEarthTexture(land: LandGeoJson, width: number) {
    const texture = new THREE.CanvasTexture(this.paintEarthCanvas(land, width));
    texture.colorSpace = THREE.SRGBColorSpace;
    // Anisotropic filtering only helps where the map is minified at a grazing
    // angle — near the limb, and when zoomed out. It does nothing for the
    // close-in blur, which is magnification. Both cases are worth having.
    texture.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
    return texture;
  }

  private buildEarth(land: LandGeoJson) {
    const width = earthTextureWidth({ maxTextureSize: this.renderer.capabilities.maxTextureSize });
    const texture = this.buildEarthTexture(land, width);
    const geometry = new THREE.SphereGeometry(EARTH_SCENE_RADIUS, 96, 64);
    this.earthMaterial = new THREE.MeshStandardMaterial({ map: texture, roughness: 1, metalness: 0.05 });
    // No extra spin. three.js SphereGeometry already places texture u = 0.5 on
    // +X, and the canvas above paints longitude 0 at u = 0.5, which is exactly
    // where geoToSceneVector puts longitude 0. See equirectangularLayerAzimuth.
    return new THREE.Mesh(geometry, this.earthMaterial);
  }

  /**
   * Coastlines and borders as lines on the sphere rather than paint on a map.
   *
   * A line drawn as geometry is rasterised fresh every frame at whatever the
   * screen resolution is, so it is exactly as sharp at the closest zoom as at
   * the furthest. The old baked strokes were 1.25 px in a 2048-wide image, and
   * the closest camera magnifies that image about 25 times.
   *
   * The shader reproduces the day/night terminator the painted coastlines used
   * to get from the sun light, so the night side still reads as night.
   */
  private buildCoastlines(land: LandGeoJson) {
    this.coastlineMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: {
        sunDirection: { value: this.sunDirection },
        dayColor: { value: new THREE.Color(0x8fe4ec) },
        nightColor: { value: new THREE.Color(0x1c5f6d) },
      },
      vertexShader: `
        varying float vSunlight;
        uniform vec3 sunDirection;
        void main() {
          vec3 worldNormal = normalize((modelMatrix * vec4(position, 0.0)).xyz);
          vSunlight = dot(worldNormal, normalize(sunDirection));
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          // A small constant nudge towards the camera in clip space. The lines
          // sit on the sphere, and the sphere is a 96x64 polyhedron whose flat
          // faces cut inside it; this keeps the lines in front of those faces
          // at every camera distance without lifting them off the globe.
          gl_Position.z -= 0.0002 * gl_Position.w;
        }
      `,
      fragmentShader: `
        varying float vSunlight;
        uniform vec3 dayColor;
        uniform vec3 nightColor;
        void main() {
          float daylight = smoothstep(-0.14, 0.16, vSunlight);
          gl_FragColor = vec4(mix(nightColor, dayColor, daylight), 0.9);
        }
      `,
    });
    // One object, not a tiled set. Splitting the coastline into 32 tiles so
    // three.js could frustum-cull them was built and measured: at the default
    // view it culled nothing and cost 30 extra draw calls per frame, and at the
    // deepest zoom it saved 17% of the line vertices for 17 extra draw calls,
    // because the view frustum still contains most of the far hemisphere.
    const geometry = new THREE.BufferGeometry();
    const positions = coastlineSegmentPositions(land, COASTLINE_SCENE_RADIUS);
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    this.coastlines = new THREE.LineSegments(geometry, this.coastlineMaterial);
    return this.coastlines;
  }

  /**
   * Earth's limb glow is decoration, and it is drawn at a fixed fraction of
   * the DRAWN globe rather than at an altitude on the shared ruler. That is
   * defensible for a planet's own halo and indefensible next to a layer that
   * is on the ruler, because the two then sit at the same drawn radius while
   * meaning different things.
   *
   * Measured: the shell is at 1.07 drawn Earth radii. On the teaching ruler
   * that is 99.4 km, and the altitude picker's "E region alone" band is
   * 90-175 km, which draws from 106.91 to 111.60 scene units -- so the glow
   * sits 0.09 scene units above the FLOOR of the isolated E band, under half a
   * pixel at the default framing. Isolate the E region and the reader is
   * looking at two concentric cyan shells, one of them a modelled electron
   * density and one of them scenery, with nothing on screen to tell them
   * apart. It is worse on the true-distance scale, where the same 1.07 is
   * 446 km -- the F2 peak's neighbourhood -- because a fixed scene radius
   * moves against every layer that is on the ruler when the scale changes.
   *
   * So the glow steps aside while the ionosphere layer is drawn. This is the
   * rule the D-region h' surface already follows against the density volume:
   * whatever is measuring the bottom of the picture owns it, and the thing
   * that is only decorating it goes away rather than competing.
   */
  private applyAirglowVisibility() {
    if (this.airglowShell) this.airglowShell.visible = !this.ionosphereVolumeEnabled;
  }

  private buildAtmosphere() {
    const material = new THREE.ShaderMaterial({
      transparent: true,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      // An additive glow must never write depth. Left at the material default
      // this 107-unit shell stamped its own far surface into the depth buffer
      // and erased every translucent scientific layer drawn behind it.
      depthWrite: false,
      vertexShader: `varying vec3 vNormal; void main(){ vNormal=normalize(normalMatrix*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
      fragmentShader: `varying vec3 vNormal; void main(){ float glow=pow(0.72-dot(vNormal,vec3(0.0,0.0,1.0)),3.4); gl_FragColor=vec4(0.10,0.78,0.92,1.0)*glow*0.42; }`,
    });
    return new THREE.Mesh(new THREE.SphereGeometry(EARTH_SCENE_RADIUS * EARTH_AIRGLOW_SHELL_SCALE, 64, 48), material);
  }

  private buildGraticule() {
    const group = new THREE.Group();
    // The basemap used to carry a second, painted copy of this grid at 0.18
    // alpha, which is what actually showed at close zoom, blurred. With that
    // copy gone the remaining vector grid carries the whole weight, so it is
    // raised to roughly what the two composited to.
    const material = new THREE.LineBasicMaterial({ color: 0x4b92a2, transparent: true, opacity: 0.27 });
    for (let latitude = -75; latitude <= 75; latitude += 15) {
      const points: THREE.Vector3[] = [];
      for (let longitude = -180; longitude <= 180; longitude += 3) points.push(this.geoToVector(latitude, longitude, 100.15));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material));
    }
    for (let longitude = -165; longitude <= 180; longitude += 15) {
      const points: THREE.Vector3[] = [];
      for (let latitude = -90; latitude <= 90; latitude += 3) points.push(this.geoToVector(latitude, longitude, 100.15));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material));
    }
    return group;
  }

  private buildStars() {
    let seed = 93241;
    const random = () => {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      return seed / 4294967296;
    };
    const positions = new Float32Array(2400 * 3);
    for (let index = 0; index < 2400; index += 1) {
      const radius = 900 + random() * 600;
      const theta = random() * Math.PI * 2;
      const phi = Math.acos(2 * random() - 1);
      positions[index * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[index * 3 + 1] = radius * Math.cos(phi);
      positions[index * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return new THREE.Points(geometry, new THREE.PointsMaterial({ color: 0x9dc5d0, size: 1.2, transparent: true, opacity: 0.55, sizeAttenuation: true }));
  }

  private buildSelectionMarker() {
    const canvas = document.createElement("canvas");
    canvas.width = 96;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    if (context) {
      const glow = context.createRadialGradient(48, 48, 18, 48, 48, 46);
      glow.addColorStop(0, "rgba(92,232,241,0)");
      glow.addColorStop(0.62, "rgba(92,232,241,0.05)");
      glow.addColorStop(0.8, "rgba(92,232,241,0.42)");
      glow.addColorStop(1, "rgba(92,232,241,0)");
      context.fillStyle = glow;
      context.fillRect(0, 0, 96, 96);
      context.strokeStyle = "rgba(210,251,255,0.96)";
      context.lineWidth = 2;
      context.beginPath();
      context.arc(48, 48, 29, 0, Math.PI * 2);
      context.stroke();
      context.fillStyle = "#d8fcff";
      context.beginPath();
      context.arc(48, 48, 3.2, 0, Math.PI * 2);
      context.fill();
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: true, depthWrite: false }));
    sprite.scale.set(12, 12, 1);
    return sprite;
  }

  /**
   * An open crosshair: a ring, four ticks reaching in toward it, and an empty
   * centre. Drawn the same way `buildSelectionMarker` draws its ring — one
   * canvas, one sprite — because that is this file's way of making a marker and
   * a second technique here would be a second thing to maintain.
   */
  private buildProbePointMarker() {
    const canvas = document.createElement("canvas");
    canvas.width = 96;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    if (context) {
      const glow = context.createRadialGradient(48, 48, 16, 48, 48, 46);
      glow.addColorStop(0, `rgba(${PROBE_POINT_COLOR},0)`);
      glow.addColorStop(0.72, `rgba(${PROBE_POINT_COLOR},0.16)`);
      glow.addColorStop(1, `rgba(${PROBE_POINT_COLOR},0)`);
      context.fillStyle = glow;
      context.fillRect(0, 0, 96, 96);
      context.strokeStyle = `rgba(${PROBE_POINT_COLOR},0.98)`;
      context.lineWidth = 3;
      context.beginPath();
      context.arc(48, 48, 22, 0, Math.PI * 2);
      context.stroke();
      // Four ticks, stopping short of the ring's inside. They point at the
      // place without drawing over it.
      context.lineWidth = 3;
      for (const [dx, dy] of [[0, -1], [0, 1], [-1, 0], [1, 0]] as const) {
        context.beginPath();
        context.moveTo(48 + dx * 32, 48 + dy * 32);
        context.lineTo(48 + dx * 25, 48 + dy * 25);
        context.stroke();
      }
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    // depthTest OFF, and the far side handled by geometry instead — see
    // `updateProbePointFacing`. With the depth test on, the sprite is a flat
    // camera-facing quad sitting 0.4 units above a sphere that keeps curving
    // toward the camera underneath it, so the half of the ring nearer the
    // middle of the visible disc was buried in the globe and the crosshair
    // rendered as a broken arc. Measured on the page before this line changed.
    //
    // The obvious alternative — lift the sprite until it clears — is the one
    // move this file must not make. A radius on this globe MEANS an altitude:
    // it is the mixed-scale lie that got the three ionosphere peak surfaces
    // retired, and a marker naming a place on the ground has no business
    // floating at 130 km to win an argument with the z-buffer.
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false }));
    sprite.renderOrder = 3;
    sprite.scale.set(9, 9, 1);
    return sprite;
  }

  /**
   * Hide the probe marker when the place it names has turned away.
   *
   * What the depth test used to do, done exactly rather than approximately: the
   * marker is visible while its own outward normal still faces the camera. The
   * dot product is against the camera POSITION rather than its direction so it
   * stays right under a perspective camera close in.
   *
   * Per frame because the CAMERA is what moves here. Measured while testing
   * this: running the timeline forward twelve hours does not carry a marked
   * place to the far side, because this globe holds geography still and moves
   * the sun — the terminator sweeps, the continents do not. So the far side is
   * reached by orbiting the camera, which the reader can do at any moment and
   * between any two frames.
   */
  private updateProbePointFacing() {
    if (!this.probePointVisible) {
      this.probePointMarker.visible = false;
      return;
    }
    const worldPosition = this.probePointMarker.getWorldPosition(this.probePointScratch);
    this.probePointMarker.visible = probePointFacesCamera(worldPosition, this.camera.position);
  }

  private buildSatelliteLabel(className: string) {
    const label = document.createElement("div");
    label.className = className;
    label.setAttribute("aria-hidden", "true");
    label.append(document.createElement("strong"), document.createElement("span"));
    return label;
  }

  private setSatelliteLabel(label: HTMLDivElement, index: number) {
    const satellite = this.satellites[index];
    if (!satellite) return;
    const name = label.querySelector("strong");
    const origin = label.querySelector("span");
    if (name) name.textContent = satellite.name;
    if (origin) origin.textContent = satellite.ownerLabel;
  }

  private pickSatellite(clientX: number, clientY: number, radiusPixels: number): number | null {
    const bounds = this.renderer.domElement.getBoundingClientRect();
    if (bounds.width <= 0 || bounds.height <= 0) return null;
    const pointerX = clientX - bounds.left;
    const pointerY = clientY - bounds.top;
    if (pointerX < 0 || pointerX > bounds.width || pointerY < 0 || pointerY > bounds.height) return null;

    this.camera.updateMatrixWorld();
    this.pickViewProjection.multiplyMatrices(this.camera.projectionMatrix, this.camera.matrixWorldInverse);
    const matrix = this.pickViewProjection.elements;
    let nearestIndex: number | null = null;
    let nearestDistanceSquared = radiusPixels * radiusPixels;

    this.visible.forEach((index) => {
      if (this.satelliteRenderable[index] !== 1) return;
      const world = this.satelliteWorldPosition(index);
      const { x, y, z } = world;
      const clipW = matrix[3]! * x + matrix[7]! * y + matrix[11]! * z + matrix[15]!;
      if (clipW <= 0) return;
      const inverseW = 1 / clipW;
      const ndcX = (matrix[0]! * x + matrix[4]! * y + matrix[8]! * z + matrix[12]!) * inverseW;
      const ndcY = (matrix[1]! * x + matrix[5]! * y + matrix[9]! * z + matrix[13]!) * inverseW;
      const ndcZ = (matrix[2]! * x + matrix[6]! * y + matrix[10]! * z + matrix[14]!) * inverseW;
      if (Math.abs(ndcX) > 1 || Math.abs(ndcY) > 1 || ndcZ < -1 || ndcZ > 1) return;
      const screenX = (ndcX * 0.5 + 0.5) * bounds.width;
      const screenY = (-ndcY * 0.5 + 0.5) * bounds.height;
      const distanceSquared = (screenX - pointerX) ** 2 + (screenY - pointerY) ** 2;
      if (distanceSquared > nearestDistanceSquared || this.satelliteCoordinatesAreOccluded(x, y, z)) return;
      nearestDistanceSquared = distanceSquared;
      nearestIndex = index;
    });

    return nearestIndex;
  }

  private satelliteIsOccluded(index: number) {
    const world = this.satelliteWorldPosition(index);
    return this.satelliteCoordinatesAreOccluded(world.x, world.y, world.z);
  }

  private satelliteWorldPosition(index: number) {
    this.satelliteFrameGroup.updateMatrixWorld(true);
    return new THREE.Vector3(
      this.satellitePositions.getX(index),
      this.satellitePositions.getY(index),
      this.satellitePositions.getZ(index),
    ).applyMatrix4(this.satelliteFrameGroup.matrixWorld);
  }

  private satelliteCoordinatesAreOccluded(x: number, y: number, z: number) {
    const deltaX = x - this.camera.position.x;
    const deltaY = y - this.camera.position.y;
    const deltaZ = z - this.camera.position.z;
    const lengthSquared = deltaX ** 2 + deltaY ** 2 + deltaZ ** 2;
    if (lengthSquared === 0) return false;
    const closestFraction = THREE.MathUtils.clamp(-(
      this.camera.position.x * deltaX
        + this.camera.position.y * deltaY
        + this.camera.position.z * deltaZ
    ) / lengthSquared, 0, 1);
    const closestX = this.camera.position.x + deltaX * closestFraction;
    const closestY = this.camera.position.y + deltaY * closestFraction;
    const closestZ = this.camera.position.z + deltaZ * closestFraction;
    return closestFraction < 0.999
      && closestX ** 2 + closestY ** 2 + closestZ ** 2 < EARTH_SCENE_RADIUS ** 2;
  }

  /**
   * Re-read which parts of the globe are covered by interface panels.
   *
   * Panels do not move between frames, so this is throttled; label placement
   * itself still runs every frame against the cached rectangles.
   */
  private refreshLabelOcclusion(now: number, force = false) {
    if (!force && now - this.lastLabelOcclusionScanAt < 250) return;
    this.lastLabelOcclusionScanAt = now;
    const document = this.container.ownerDocument;
    const view = document.defaultView;
    if (!view || !document.body) {
      this.labelViewport = null;
      this.labelOccluders = [];
      return;
    }
    const viewport = this.container.getBoundingClientRect();
    this.labelViewport = viewport;
    this.labelOccluders = collectLabelOccluderRects(
      document.body as unknown as LabelOccluderCandidate,
      viewport,
      {
        readStyle: (element) => view.getComputedStyle(element as unknown as Element),
        isGlobeSurface: (element) => {
          const node = element as unknown as Element;
          return node === this.container || node.hasAttribute?.("data-globe-label-clear") === true;
        },
        containsGlobeSurface: (element) => (element as unknown as Element).contains?.(this.container) === true,
        isDeclaredOccluder: (element) =>
          (element as unknown as Element).hasAttribute?.("data-globe-label-occluder") === true,
      },
    );
  }

  private positionSatelliteLabel(label: HTMLDivElement, index: number) {
    if (!this.visible.has(index) || this.satelliteRenderable[index] !== 1 || this.satelliteIsOccluded(index)) {
      label.classList.remove("is-visible");
      return;
    }
    const point = this.satelliteWorldPosition(index).project(this.camera);
    if (point.z < -1 || point.z > 1) {
      label.classList.remove("is-visible");
      return;
    }
    label.style.left = `${(point.x * 0.5 + 0.5) * this.container.clientWidth}px`;
    label.style.top = `${(-point.y * 0.5 + 0.5) * this.container.clientHeight}px`;
    const viewport = this.labelViewport;
    if (viewport && labelPlacementIsOccluded(label.getBoundingClientRect(), viewport, this.labelOccluders)) {
      label.classList.remove("is-visible");
      return;
    }
    label.classList.add("is-visible");
  }

  /**
   * The GloTEC surface is a MAP, and it is now drawn like one.
   *
   * It used to be a sphere at a hard-coded scene radius of 109, which was on
   * no ruler at all. Read back through the two scales that is 133 km on the
   * teaching curve and 573 km on true distance -- the same drawn shell
   * claiming two altitudes 4.3x apart, decided by a Display setting. Against
   * the ionospheric column it is the sum of (60 to 2,655 km, drawn 104.4 to
   * 160.0 on the teaching scale and 100.94 to 141.66 on true distance) the
   * shell sat 8.2% of the way up the column on one scale and 19.8% up on the
   * other. It slid through the very layer it totals when the visitor flipped
   * a switch, which is exactly what the shared ruler exists to prevent.
   *
   * It cannot be fixed by putting it on the ruler, because TEC has no height
   * to put there: it is electrons integrated through the whole column, and
   * the site says so in its own methods card -- "it cannot locate the D, E or
   * F boundaries, cannot give a vertical profile". Any altitude at all would
   * be a claim the measurement does not make.
   *
   * So it is drawn on the column's FOOTPRINT instead: a wash on the globe,
   * lifted 0.3% of the drawn Earth radius, which is enough to sit clear of
   * the basemap and the coastlines at 100.06 and nothing more. Two properties
   * follow, and they are what the test pins. It is identical on both distance
   * scales, because the drawn globe is radius 1 on both, so it can never move
   * against another layer when the scale changes. And it is below every layer
   * on this globe that does have an altitude, on both scales -- the lowest of
   * those is now the ionospheric column floor at 60 km (100.94 on true
   * distance, 104.43 on teaching) -- so it can never be read as one of them.
   *
   * Updated 2026-09-04: this used to name the D-RAP map at 35 km (100.55) as
   * the lowest. It was 35 km only on true distance -- the shell was built on a
   * private true-distance formula, so on the teaching scale the same radius
   * read as 6.9 km. D-RAP now stands at 70 km on the shared ruler, which is
   * the reference height this site's own D-region page gives it, and the
   * ordering argument above is unchanged because the TEC wash is still the
   * lowest thing drawn.
   *
   * The visible cost is the outer glow ring the old radius produced at the
   * limb. That ring was the false altitude.
   */
  private buildIonosphere() {
    return new THREE.Mesh(
      new THREE.SphereGeometry(TEC_MAP_SCENE_RADIUS, 64, 48),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.6, depthWrite: false, blending: THREE.AdditiveBlending }),
    );
  }

  private buildAurora() {
    return new THREE.Mesh(
      new THREE.SphereGeometry(101.55, 64, 48),
      new THREE.MeshBasicMaterial({
        transparent: true,
        opacity: 0.9,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
  }

  /**
   * The three schematic D / E / F shells.
   *
   * CORRECTNESS FIX 2026-09-04: these were three hard-coded scene radii — 102,
   * 104 and 110 against a globe drawn at 100 — on no ruler at all. Inverted
   * through the two scales the site actually offers, the shells labelled D, E
   * and F stood at:
   *
   *                teaching scale      true distance
   *      "D"           25.9 km            127 km
   *      "E"           53.7 km            255 km
   *      "F"          150.2 km            637 km
   *
   * On the default scale the D shell was in the stratosphere and the E shell
   * was below the D region, both of them under the 60 km floor of the
   * ionospheric column drawn beside them (104.43). The same three shells
   * claimed a second, different set of heights the moment a visitor switched
   * to true distance — the one thing the shared ruler exists to prevent, and
   * the exact failure written up at length for the old TEC shell a few hundred
   * lines above this.
   *
   * SCHEMATIC is a licence about the DENSITY — "conceptual bands, not density
   * data", which the legend says and which stays true. It is not a licence to
   * put a layer at the wrong height: heights are operational tier on this
   * site, and a reader studying for a qualification reads these three shells
   * against each other and against the globe.
   *
   * The altitudes are the site's own, from `content.ts`'s ionosphere fact
   * list: "D region 60–90 km" (75 km, its middle), "E region ~110 km", "F2
   * peak ~300 km". They go through `satelliteDisplayRadius`, the shared ruler,
   * so all three are right on both scales and `rebuildRegionShells` keeps them
   * right across a switch.
   */
  private buildRegions() {
    const regions = [
      { altitudeKm: 75, color: 0xff7b78, opacity: 0.055 },
      { altitudeKm: 110, color: 0xf5c96a, opacity: 0.05 },
      { altitudeKm: 300, color: 0xa98cff, opacity: 0.045 },
    ];
    regions.forEach(({ altitudeKm, color, opacity }) => {
      // These are deliberately schematic altitude bands, not density fields.
      // Solar geometry changes only their visual emphasis. The HEIGHT is not
      // schematic — see above.
      const shell = new THREE.Mesh(
        new THREE.SphereGeometry(satelliteDisplayRadius(altitudeKm), 48, 32),
        new THREE.ShaderMaterial({
          uniforms: {
            shellColor: { value: new THREE.Color(color) },
            baseOpacity: { value: opacity },
            sunDirection: { value: this.sunDirection },
          },
          transparent: true,
          side: THREE.DoubleSide,
          depthWrite: false,
          vertexShader: `
            varying vec3 worldNormal;
            void main() {
              worldNormal = normalize(mat3(modelMatrix) * normal);
              gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
          `,
          fragmentShader: `
            uniform vec3 shellColor;
            uniform float baseOpacity;
            uniform vec3 sunDirection;
            varying vec3 worldNormal;
            void main() {
              float solarCosine = dot(normalize(worldNormal), normalize(sunDirection));
              float daylight = smoothstep(-0.18, 0.3, solarCosine);
              float opacity = mix(baseOpacity * 0.22, baseOpacity * 1.25, daylight);
              gl_FragColor = vec4(shellColor, opacity);
            }
          `,
        }),
      );
      // The altitude travels with the mesh so the rebuild below does not need a
      // second copy of the table that could drift from this one.
      shell.userData.schematicRegionAltitudeKm = altitudeKm;
      this.regionGroup.add(shell);
    });
  }

  /**
   * Redraw the three schematic shells through the live ruler. Called from
   * `rebuildRadialGeometry`, for the same reason every other baked consumer is.
   */
  private rebuildRegionShells() {
    for (const child of this.regionGroup.children) {
      const altitudeKm = (child.userData as { schematicRegionAltitudeKm?: number }).schematicRegionAltitudeKm;
      if (typeof altitudeKm !== "number" || !(child instanceof THREE.Mesh)) continue;
      const previous = child.geometry;
      child.geometry = new THREE.SphereGeometry(satelliteDisplayRadius(altitudeKm), 48, 32);
      previous.dispose();
    }
  }

  private buildMagnetosphere() {
    // Empty until a driver sample arrives. There is no placeholder surface:
    // the layer is hidden while `magnetosphereDataAvailable` is false, and a
    // boundary drawn from invented drivers is exactly the thing the layer
    // contract forbids.
    const group = new THREE.Group();
    group.name = "magnetopause";
    return group;
  }

  /**
   * Per-surface appearance.
   *
   * Three surfaces can be on screen at once and they say different things, so
   * they are drawn at different weights rather than in three equally loud
   * colours. Shue is the familiar axisymmetric context that carries the tail;
   * Nguyen's current sheet is the outer wall of the cusp and gets the most
   * presence; Lin's cusp inner boundary is the inner wall. `cuspGain` is what
   * lets the funnel read: it is multiplied by Nguyen's own published `C/2`
   * proximity, so the brightening sits exactly where the model puts the cusp
   * and nowhere else.
   */
  private static readonly MAGNETOPAUSE_SURFACE_STYLE: Record<
    MagnetopauseModelId,
    { color: number; baseAlpha: number; rimGain: number; cuspGain: number; fadeIn: number; fadeStart: number }
  > = {
    shue1998: { color: MAGNETOPAUSE_MODEL_COLORS.shue1998, baseAlpha: 0.004, rimGain: 0.082, cuspGain: 0, fadeIn: 0.10, fadeStart: 0.72 },
    nguyen2022: { color: MAGNETOPAUSE_MODEL_COLORS.nguyen2022, baseAlpha: 0.014, rimGain: 0.170, cuspGain: 0.26, fadeIn: 0, fadeStart: 0.94 },
    lin2010: { color: MAGNETOPAUSE_MODEL_COLORS.lin2010, baseAlpha: 0.008, rimGain: 0.105, cuspGain: 0.14, fadeIn: 0, fadeStart: 0.94 },
  };

  private boundaryMaterial(id: MagnetopauseModelId) {
    const style = SpaceGlobe.MAGNETOPAUSE_SURFACE_STYLE[id];
    return new THREE.ShaderMaterial({
      uniforms: {
        boundaryColor: { value: new THREE.Color(style.color) },
        baseAlpha: { value: style.baseAlpha },
        rimGain: { value: style.rimGain },
        cuspGain: { value: style.cuspGain },
        fadeIn: { value: style.fadeIn },
        fadeStart: { value: style.fadeStart },
      },
      transparent: true,
      // Every empirical boundary here is open down-tail. Draw both walls with a
      // restrained Fresnel treatment, then fade the last part of the model
      // domain so an arbitrary cutoff never reads as a physical cap.
      side: THREE.DoubleSide,
      depthWrite: false,
      vertexShader: `
        attribute float boundaryProgress;
        attribute float cuspProximity;
        varying vec3 viewNormal;
        varying vec3 viewDirection;
        varying float sunwardPosition;
        varying float tailProgress;
        varying float cuspWeight;
        void main() {
          vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
          viewNormal = normalize(normalMatrix * normal);
          viewDirection = normalize(-viewPosition.xyz);
          sunwardPosition = position.x;
          tailProgress = boundaryProgress;
          cuspWeight = cuspProximity;
          gl_Position = projectionMatrix * viewPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 boundaryColor;
        uniform float baseAlpha;
        uniform float rimGain;
        uniform float cuspGain;
        uniform float fadeIn;
        uniform float fadeStart;
        varying vec3 viewNormal;
        varying vec3 viewDirection;
        varying float sunwardPosition;
        varying float tailProgress;
        varying float cuspWeight;
        void main() {
          float rim = pow(1.0 - abs(dot(normalize(viewNormal), normalize(viewDirection))), 1.6);
          float dayside = smoothstep(-180.0, 160.0, sunwardPosition);
          // fadeIn hides the seam where the Shue tail picks up from the two
          // cusped fits; fadeStart hides the far cutoff, which is a limit of
          // the model domain and not a physical cap.
          float rampIn = fadeIn > 0.0 ? smoothstep(0.0, fadeIn, tailProgress) : 1.0;
          float tailFade = rampIn * (1.0 - smoothstep(fadeStart, 1.0, tailProgress));
          float alpha = (baseAlpha + rimGain * rim + 0.010 * dayside + cuspGain * cuspWeight) * tailFade;
          gl_FragColor = vec4(boundaryColor * (0.72 + 0.52 * rim + 0.40 * cuspWeight), alpha);
        }
      `,
    });
  }

  /**
   * The shaded volume between Lin's cusp inner boundary and Nguyen's current
   * sheet.
   *
   * Opacity is driven by the geometry's own `gapThicknessRe`, so the funnel is
   * densest where the two published surfaces are furthest apart and vanishes
   * where they meet. Nothing here invents a falloff: the shell only exists
   * where `r_Nguyen - r_Lin > 0`, which `magnetopause-surfaces.ts` has already
   * decided, and this material simply does not draw what is not there.
   */
  private exteriorCuspMaterial() {
    return new THREE.ShaderMaterial({
      uniforms: { cuspColor: { value: new THREE.Color(EXTERIOR_CUSP_COLOR) } },
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
      vertexShader: `
        attribute float gapThicknessRe;
        attribute float cuspProximity;
        varying vec3 viewNormal;
        varying vec3 viewDirection;
        varying float gapRe;
        varying float cuspWeight;
        void main() {
          vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
          viewNormal = normalize(normalMatrix * normal);
          viewDirection = normalize(-viewPosition.xyz);
          gapRe = gapThicknessRe;
          cuspWeight = cuspProximity;
          gl_Position = projectionMatrix * viewPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 cuspColor;
        varying vec3 viewNormal;
        varying vec3 viewDirection;
        varying float gapRe;
        varying float cuspWeight;
        void main() {
          float rim = pow(1.0 - abs(dot(normalize(viewNormal), normalize(viewDirection))), 1.4);
          // The shell exists only where the two published surfaces genuinely
          // cross, so every fragment here is inside the funnel. Opacity still
          // rises with the real thickness, but from a floor rather than from
          // zero: a 0.15 Re funnel on a quiet northward day is small and it is
          // real, and fading it to nothing would hide the model's own answer.
          // The measured thickness in Earth radii is on the legend either way.
          float depth = 0.12 + 0.88 * clamp(gapRe / 1.2, 0.0, 1.0);
          float alpha = depth * (0.10 + 0.34 * rim) + 0.06 * cuspWeight * depth;
          gl_FragColor = vec4(cuspColor * (0.80 + 0.45 * rim), alpha);
        }
      `,
    });
  }

  /**
   * Turn one propagated solar-wind sample into the drivers the cusped
   * boundaries need, or `null` if it cannot support them.
   *
   * Nguyen and Lin both need a dipole tilt, and Nguyen additionally needs the
   * IMF clock angle. Neither can be guessed: a tilt of 0 is a real and common
   * value, so defaulting to it would draw a symmetric magnetosphere at a moment
   * when the real one is leaning 30 degrees, and a clock angle invented from Bz
   * alone throws away the whole By half of the reconnection geometry. When
   * either is missing this returns `null` and the caller draws Shue and says
   * Shue.
   */
  private cuspedDrivers(driver: MagnetopauseDriverSample): CuspedBoundaryDrivers | null {
    const tilt = dipoleTilt(this.simulationTime);
    const clock = clockAngleRad(driver.byNt, driver.bzGsmNt);
    if (!tilt || clock === null) return null;
    const magnetic = driver.magneticPressureNpa
      ?? (driver.btNt !== null ? magneticPressureNpa(driver.btNt) : null);
    if (magnetic === null || !Number.isFinite(magnetic)) return null;
    return {
      dynamicPressureNpa: driver.dynamicPressureNpa,
      magneticPressureNpa: magnetic,
      bzGsmNt: driver.bzGsmNt,
      clockAngleRad: clock,
      dipoleTiltRad: tilt.radians,
    };
  }

  private populateMagnetosphere(group: THREE.Group, driver: MagnetopauseDriverSample) {
    this.disposeGroup(group);
    this.cuspEntryTracks = [];
    this.cuspEntryPoints = null;
    const cusped = this.cuspedDrivers(driver);
    // Shue needs only Pd and Bz, so it is always evaluable from a sample that
    // produced a standoff at all. It is the honest fallback: the surface the
    // site has always drawn, still labelled as what it is.
    const fallback: CuspedBoundaryDrivers = {
      dynamicPressureNpa: driver.dynamicPressureNpa,
      magneticPressureNpa: 0,
      bzGsmNt: driver.bzGsmNt,
      clockAngleRad: 0,
      dipoleTiltRad: 0,
    };
    const drivers = cusped ?? fallback;
    const selected: MagnetopauseModelId[] = cusped ? [...this.magnetopauseModels] : ["shue1998"];

    const baseOptions: MagnetopauseSurfaceOptions = {
      // The scene's shared ruler, and the only mapper any of these surfaces
      // sees. Nothing in the boundary layer owns a radial scale of its own.
      positionForGsm: (xRe, yRe, zRe) => this.modelGsmPosition(xRe, yRe, zRe),
      thetaSegments: 96,
      azimuthSegments: 96,
    };
    // Where the two cusped fits stop. Neither is a tail model, so beyond this
    // the only surface with any claim to the geometry is Shue.
    const cuspedCutoffRad = (120 * Math.PI) / 180;

    const drawn: MagnetopauseModelId[] = [];
    let cuspGeometry: ExteriorCuspGeometry | null = null;

    /** Per-model theta window: see the long comment on the surface branch. */
    const thetaWindow = (id: MagnetopauseModelId, evaluator: { subsolarRe: number }) =>
      id === "shue1998"
        ? {
          maximumThetaRad: shueTailTheta(evaluator.subsolarRe, driver.flaringAlpha, 50),
          minimumThetaRad: cusped ? cuspedCutoffRad : 0,
        }
        : { maximumThetaRad: cuspedCutoffRad };

    if (this.magnetopauseDisplayValue === "cross-section") {
      // The textbook cut. Each model becomes a profile curve in the two cut
      // planes; the exterior cusp becomes a filled lens on the noon meridian.
      for (const id of selected) {
        const evaluator = magnetopauseEvaluator(id, drivers);
        if (!evaluator) continue;
        let anyPlane = false;
        for (const plane of ["meridional", "equatorial"] as const satisfies readonly MagnetopauseProfilePlane[]) {
          const profile = createMagnetopauseProfileGeometry(evaluator, plane, {
            ...baseOptions,
            thetaSegments: 192,
            ...thetaWindow(id, evaluator),
          });
          if (!profile) continue;
          const style = SpaceGlobe.MAGNETOPAUSE_SURFACE_STYLE[id];
          const line = new THREE.LineSegments(
            profile,
            new THREE.LineBasicMaterial({
              color: style.color,
              transparent: true,
              // The meridian carries the cusps; the equatorial curve is
              // context and is kept quieter so the funnels stay the subject.
              opacity: plane === "meridional" ? 0.9 : 0.38,
              depthWrite: false,
            }),
          );
          line.name = `empirical-magnetopause-profile-${id}-${plane}`;
          line.userData = {
            model: id,
            plane,
            status: "published-empirical-fit-profile",
            units: "Earth radii (R_E)",
          };
          group.add(line);
          anyPlane = true;
        }
        if (anyPlane) drawn.push(id);
      }
      if (cusped && this.cuspFunnelsEnabledValue) {
        const lens = createExteriorCuspProfileGeometry(cusped, { ...baseOptions, thetaSegments: 192 });
        if (lens) {
          const mesh = new THREE.Mesh(
            lens,
            new THREE.MeshBasicMaterial({
              color: EXTERIOR_CUSP_COLOR,
              transparent: true,
              opacity: 0.42,
              side: THREE.DoubleSide,
              depthWrite: false,
            }),
          );
          mesh.name = "empirical-exterior-cusp-cross-section";
          mesh.userData = {
            status: "region-between-two-published-fits",
            derivation: "the span where Lin's cusp inner boundary lies inside Nguyen's current sheet",
          };
          group.add(mesh);
        }
        // The legend still reports funnel depth and spread; a coarse stats
        // pass costs little and keeps the numbers identical in both modes.
        cuspGeometry = createExteriorCuspGeometry(cusped, {
          ...baseOptions,
          thetaSegments: 48,
          azimuthSegments: 48,
        });
        cuspGeometry?.geometry.dispose();
      }
    } else {
      for (const id of selected) {
        const evaluator = magnetopauseEvaluator(id, drivers);
        if (!evaluator) continue;
        const surface = createMagnetopauseSurfaceGeometry(evaluator, drivers, {
          ...baseOptions,
          /*
           * Shue is drawn as the **tail continuation only** whenever the cusped
           * surfaces are available, picking up at the zenith angle where they
           * stop and running out to the -50 Re cutoff.
           *
           * Not a styling choice. The cusps are indentations, so they show in the
           * silhouette — and a smooth axisymmetric surface laid over the dayside
           * sits *outside* the indentation and puts the smooth silhouette back,
           * which is exactly the picture this whole feature exists to replace.
           * Shue keeps the tail because it is the only one of the three fitted
           * there; Nguyen and Lin stop where their fits do rather than
           * extrapolating a surface the papers do not support.
           *
           * When the drivers cannot support the cusped models, Shue is drawn
           * whole and labelled as what it is.
           */
          ...thetaWindow(id, evaluator),
        });
        if (!surface) continue;
        const mesh = new THREE.Mesh(surface.geometry, this.boundaryMaterial(id));
        mesh.name = `empirical-magnetopause-${id}`;
        group.add(mesh);
        drawn.push(id);
      }

      if (cusped && this.cuspFunnelsEnabledValue) {
        cuspGeometry = createExteriorCuspGeometry(cusped, baseOptions);
        if (cuspGeometry) {
          const mesh = new THREE.Mesh(cuspGeometry.geometry, this.exteriorCuspMaterial());
          mesh.name = "empirical-exterior-cusp";
          group.add(mesh);
        }
      }
    }

    // The entry cue rides the same live surfaces in both presentations: the
    // funnel is where the solar wind actually reaches the atmosphere, and
    // watching something fall down it is the point of drawing the cusp at all.
    // It lives in its own group so the 3-D field-line view and the solar-wind
    // layer can show particles funnelling into the poles without the empirical
    // annotation having to be switched on.
    this.disposeGroup(this.cuspEntryGroup);
    if (cusped) this.buildCuspEntryCue(this.cuspEntryGroup, cusped);
    this.applyCuspEntryVisibility();

    this.magnetopauseLegendEntries = magnetopauseLegend(
      drivers,
      cuspGeometry ? [...drawn, "exteriorCusp"] : drawn,
      cuspGeometry,
    );
    this.magnetopauseFallbackReason = cusped
      ? null
      : "No IMF clock angle for the selected time, so only the axisymmetric Shue surface is drawn. "
        + "The cusped boundaries need the full IMF vector and a dipole tilt, and neither is invented.";

    this.solarWindVisual.setBoundaryRadiusForDirection(
      this.drawnBoundaryRadiusField(drivers, drawn, cuspedCutoffRad),
    );
    // The solar-wind layer draws its own faint copy of this obstacle so that
    // its sheath is legible on its own. Here the real boundary is on screen
    // with its legend and its drivers, so the cue comes off.
    this.solarWindVisual.setBoundaryDrawnElsewhere(this.magnetosphere.visible);
  }

  /**
   * The animated cusp-entry cue: shocked plasma falling down the funnel the
   * two live empirical surfaces define, continued along an ideal dipole line
   * to the top of the atmosphere near 75 degrees — the dayside cusp aurora's
   * neighbourhood, arrived at by mapping rather than drawn at the answer.
   *
   * The path geometry is driven (it swings equatorward as Bz turns south,
   * because Nguyen's cusp latitude does); the motion along it is illustrative
   * and the legend says so. The faint path lines are drawn so a paused frame
   * still shows where the funnel leads.
   */
  private buildCuspEntryCue(group: THREE.Group, cusped: CuspedBoundaryDrivers) {
    const paths: CuspEntryPath[] = createCuspEntryPaths(cusped);
    if (paths.length === 0) return;

    const linePositions: number[] = [];
    this.cuspEntryTracks = paths.map((path) => {
      // Drawn in pieces across the ruler's joint band for the same reason the
      // field lines are: these paths choose their steps in physical space and
      // every one of them crosses the anchor on its way down the funnel.
      const points: THREE.Vector3[] = [];
      for (let index = 0; index < path.pointsGsmRe.length; index += 1) {
        const point = path.pointsGsmRe[index]!;
        const previousPoint = index > 0 ? path.pointsGsmRe[index - 1]! : null;
        const pieces = previousPoint
          ? rulerJointBandSegments(
            Math.hypot(previousPoint.xRe, previousPoint.yRe, previousPoint.zRe),
            Math.hypot(point.xRe, point.yRe, point.zRe),
          )
          : 1;
        for (let piece = 1; piece < pieces; piece += 1) {
          const amount = piece / pieces;
          points.push(this.modelGsmPosition(
            previousPoint!.xRe + (point.xRe - previousPoint!.xRe) * amount,
            previousPoint!.yRe + (point.yRe - previousPoint!.yRe) * amount,
            previousPoint!.zRe + (point.zRe - previousPoint!.zRe) * amount,
          ));
        }
        points.push(this.modelGsmPosition(point.xRe, point.yRe, point.zRe));
      }
      const cumulative: number[] = [0];
      for (let index = 1; index < points.length; index += 1) {
        cumulative.push(cumulative[index - 1]! + points[index]!.distanceTo(points[index - 1]!));
        linePositions.push(
          points[index - 1]!.x, points[index - 1]!.y, points[index - 1]!.z,
          points[index]!.x, points[index]!.y, points[index]!.z,
        );
      }
      return { points, cumulative, total: cumulative.at(-1) ?? 0 };
    });

    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(linePositions, 3));
    const lines = new THREE.LineSegments(
      lineGeometry,
      new THREE.LineBasicMaterial({ color: 0xffc46a, transparent: true, opacity: 0.28, depthWrite: false }),
    );
    lines.name = "cusp-entry-paths";
    lines.userData = {
      status: "illustrative-cue-along-live-empirical-funnel",
      geometryDrivenBy: "Nguyen 2022 + Lin 2010 from the live drivers; ideal-dipole continuation below the boundary",
      motion: "illustrative — no measured velocity exists along this path",
    };
    group.add(lines);

    const tracersPerPath = 4;
    const tracerCount = this.cuspEntryTracks.length * tracersPerPath;
    const tracerGeometry = new THREE.BufferGeometry();
    tracerGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(tracerCount * 3), 3));
    // A round soft-edged sprite, not THREE.PointsMaterial: unshaped GL points
    // are literal squares, and a string of bright squares falling into the
    // poles is exactly what Sean flagged as an artifact.
    const tracers = new THREE.Points(
      tracerGeometry,
      new THREE.ShaderMaterial({
        uniforms: {
          color: { value: new THREE.Color(0xffd9a0) },
          opacity: { value: 0.9 },
          pointSize: { value: 2.6 },
          pixelRatio: { value: Math.max(0.25, this.renderer.getPixelRatio()) },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        vertexShader: `
          uniform float pointSize;
          uniform float pixelRatio;
          void main() {
            gl_PointSize = pointSize * pixelRatio;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 color;
          uniform float opacity;
          void main() {
            float radius = length(gl_PointCoord - vec2(0.5));
            if (radius > 0.5) discard;
            float softEdge = 1.0 - smoothstep(0.25, 0.5, radius);
            gl_FragColor = vec4(color, opacity * softEdge);
          }
        `,
      }),
    );
    tracers.name = "cusp-entry-tracers";
    tracers.frustumCulled = false;
    tracers.userData = lines.userData;
    group.add(tracers);
    this.cuspEntryPoints = tracers;
    this.updateCuspEntryCue(0);
  }

  private updateCuspEntryCue(deltaSeconds: number) {
    const points = this.cuspEntryPoints;
    const positions = points?.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    if (!points || !positions || this.cuspEntryTracks.length === 0) return;
    this.cuspEntryElapsedSeconds += deltaSeconds;
    const tracersPerPath = Math.floor(positions.count / this.cuspEntryTracks.length);
    // One full fall takes ~9 display seconds: slow enough to follow by eye,
    // fast enough that a reader who just switched the layer on sees motion.
    const cycleSeconds = 9;
    this.cuspEntryTracks.forEach((track, trackIndex) => {
      for (let tracerIndex = 0; tracerIndex < tracersPerPath; tracerIndex += 1) {
        const phase = (this.cuspEntryElapsedSeconds / cycleSeconds + tracerIndex / tracersPerPath
          + trackIndex * 0.17) % 1;
        const distance = phase * track.total;
        let segment = 1;
        while (segment < track.cumulative.length - 1 && track.cumulative[segment]! < distance) segment += 1;
        const before = track.cumulative[segment - 1]!;
        const span = Math.max(1e-6, track.cumulative[segment]! - before);
        const alongSegment = THREE.MathUtils.clamp((distance - before) / span, 0, 1);
        const position = track.points[segment - 1]!.clone().lerp(track.points[segment]!, alongSegment);
        positions.setXYZ(trackIndex * tracersPerPath + tracerIndex, position.x, position.y, position.z);
      }
    });
    positions.needsUpdate = true;
  }

  /** `surface` (closed shells) or `cross-section` (the textbook cut). */
  setMagnetopauseDisplay(mode: "surface" | "cross-section") {
    if (mode === this.magnetopauseDisplayValue) return;
    this.magnetopauseDisplayValue = mode;
    if (this.lastMagnetopauseDriver && this.magnetosphereDataAvailable) {
      this.populateMagnetosphere(this.magnetosphere, this.lastMagnetopauseDriver);
    }
  }

  get magnetopauseDisplay() {
    return this.magnetopauseDisplayValue;
  }

  /**
   * The colour ramp of the driven field lines: the site's |B| palette over
   * log10 field strength, so one visual language covers both the traced lines
   * and the BATS-R-US |B| cut. The endpoints the legend prints come from the
   * same shared constant.
   */
  private static fieldLineColor(logFieldNt: number): THREE.Color {
    const [low, high] = FIELD_LINE_DISPLAY_LOG_RANGE;
    const t = THREE.MathUtils.clamp((logFieldNt - low) / (high - low), 0, 1);
    const dark = new THREE.Color(0x4a4390);
    const middle = new THREE.Color(0xa98cff);
    const bright = new THREE.Color(0x5ce8f1);
    const color = t < 0.5 ? dark.lerp(middle, t * 2) : middle.lerp(bright, (t - 0.5) * 2);
    // Lift the floor: a weak-field tail line must still be visible over the
    // sky, because the stretched tail is half of what the picture teaches.
    return color.multiplyScalar(0.62 + 0.5 * t);
  }

  /**
   * The 3-D magnetosphere: driven field lines inside a subtle copy of the
   * live empirical boundary, with the cusp funnels the two cusped fits define.
   *
   * Everything here is driven by the same propagated L1 sample the empirical
   * boundary uses, plus the same dipole tilt, so scrubbing the 48 h replay
   * deforms the field lines, the boundary and the funnels together. The trace
   * itself is verified numerically in tests/magnetosphere-field-lines.test.ts
   * before any pixel of it is trusted.
   */
  private populateFieldLines(driver: MagnetopauseDriverSample) {
    const tilt = dipoleTilt(this.simulationTime);
    if (!tilt) {
      this.clearFieldLines();
      return;
    }
    const signature = [
      driver.subsolarStandoffRe.toFixed(4),
      driver.bzGsmNt.toFixed(2),
      driver.dynamicPressureNpa.toFixed(3),
      tilt.radians.toFixed(3),
      this.fieldLineCalibration
        ? `mhd:${this.fieldLineCalibration.frameValidAt}:${this.fieldLineCalibration.standoffRe.toFixed(3)}`
        : "shue",
      // The cusp annotation is part of what this rebuild BUILDS, not only of
      // what it shows, so it belongs in the guard: without it, ticking the box
      // would match the cached signature and return before drawing anything.
      this.cuspFunnelsEnabledValue ? "cusps" : "no-cusps",
    ].join("|");
    if (signature === this.fieldLineSignature && this.fieldLineGroup.children.length > 0) {
      this.applyFieldLineVisibility();
      return;
    }
    this.fieldLineSignature = signature;
    this.disposeGroup(this.fieldLineGroup);
    const traced = traceMagnetosphereFieldLines({
      dynamicPressureNpa: driver.dynamicPressureNpa,
      bzGsmNt: driver.bzGsmNt,
      dipoleTiltRad: tilt.radians,
      boundaryCalibration: this.fieldLineCalibration,
    });
    this.fieldLineSummaryValue = traced?.summary ?? null;
    this.fieldLineCuspFunnelsValue = false;
    if (!traced) {
      this.fieldLineIntegrityValue = null;
      this.tracedFieldLinesValue = null;
      this.refreshFieldGuidance();
      this.applyFieldLineVisibility();
      return;
    }
    // The per-rebuild sanity check: strided segment-vs-field faithfulness plus
    // endpoint topology, Earth clearance and truncation discipline (~3 ms
    // against a 25–60 ms trace). If the traced set fails its own invariants,
    // draw NOTHING and let the card carry the refusal — the same grammar the
    // boundary fit uses when an implausible fit is thrown away. Impossible
    // geometry must never be drawn silently.
    const integrity = verifyTracedMagnetosphere(traced);
    this.fieldLineIntegrityValue = integrity;
    if (!integrity.ok) {
      this.fieldLineSummaryValue = null;
      this.tracedFieldLinesValue = null;
      this.refreshFieldGuidance();
      this.applyFieldLineVisibility();
      return;
    }

    const positions: number[] = [];
    const colors: number[] = [];
    const emit = (line: TracedFieldLine) => {
      // Closed lines carry the loops; open and boundary lines carry the polar
      // caps, the funnels and the tail. All are drawn; weight separates them.
      const weight = line.topology === "closed" ? 1 : 0.88;
      // Arc length still ahead of each vertex, physical Re, so the cut end of
      // an open or boundary-truncated line can fade out instead of stopping
      // dead — the tail cutoff and the truncation surface are model-domain
      // limits, not physics, and the boundary surfaces already fade theirs.
      // Opacity only: the traced geometry (which the guided solar wind rides)
      // is untouched.
      const points = line.pointsGsmRe;
      const remainingArcRe = new Array<number>(points.length);
      remainingArcRe[points.length - 1] = 0;
      for (let index = points.length - 2; index >= 0; index -= 1) {
        const a = points[index]!;
        const b = points[index + 1]!;
        remainingArcRe[index] = remainingArcRe[index + 1]!
          + Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
      }
      let previous: THREE.Vector3 | null = null;
      let previousColor: THREE.Color | null = null;
      let previousPoint: { x: number; y: number; z: number } | null = null;
      for (let index = 0; index < line.pointsGsmRe.length; index += 1) {
        const point = line.pointsGsmRe[index]!;
        const mapped = this.modelGsmPosition(point.x, point.y, point.z);
        // Fade toward the footpoints. Twelve MLT spokes converge over each
        // pole, and with additive blending the un-faded bundle summed into a
        // bright spear that read as an artifact through the planet; the
        // references let their lines dissolve into the atmosphere instead.
        const radius = Math.hypot(point.x, point.y, point.z);
        const footpointFade = 0.12 + 0.88 * THREE.MathUtils.smoothstep(radius, 1.1, 1.9);
        const endFade = truncatedEndFade(line.topology, remainingArcRe[index]!);
        const color = SpaceGlobe.fieldLineColor(line.logFieldNt[index] ?? 1)
          .multiplyScalar(weight * footpointFade * endFade);
        if (previous && previousColor && previousPoint) {
          // Decimate by drawn length: the ruler compresses the near-Earth leg
          // so densely that emitting every RK4 step would triple the vertex
          // count without adding a visible pixel.
          if (mapped.distanceTo(previous) < 1.1 && index < line.pointsGsmRe.length - 1) continue;
          // ...but across the ruler's joint band the same chord's drawn image
          // is a curve, so it is drawn in pieces rather than as one facet.
          const pieces = rulerJointBandSegments(
            Math.hypot(previousPoint.x, previousPoint.y, previousPoint.z),
            Math.hypot(point.x, point.y, point.z),
          );
          let stepStart = previous;
          let stepColor = previousColor;
          for (let piece = 1; piece <= pieces; piece += 1) {
            const amount = piece / pieces;
            const stepEnd = piece === pieces ? mapped : this.modelGsmPosition(
              previousPoint.x + (point.x - previousPoint.x) * amount,
              previousPoint.y + (point.y - previousPoint.y) * amount,
              previousPoint.z + (point.z - previousPoint.z) * amount,
            );
            // Colour is already interpolated along a segment by the renderer,
            // so interpolating it here draws exactly the same gradient.
            const endColor = piece === pieces
              ? color
              : previousColor.clone().lerp(color, amount);
            positions.push(stepStart.x, stepStart.y, stepStart.z, stepEnd.x, stepEnd.y, stepEnd.z);
            colors.push(
              stepColor.r, stepColor.g, stepColor.b,
              endColor.r, endColor.g, endColor.b,
            );
            stepStart = stepEnd;
            stepColor = endColor;
          }
        }
        previous = mapped;
        previousColor = color;
        previousPoint = point;
      }
    };
    traced.lines.forEach(emit);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    const lines = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.62,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    lines.name = "driven-field-lines";
    lines.frustumCulled = false;
    lines.userData = {
      ...FIELD_LINE_METHOD,
      colorEncodes: "log10 |B| of the stated construction, nT",
      boundarySource: traced.parameters.boundarySource,
      drivenBy: `${traced.parameters.boundarySource === "noaa-mhd-frame"
        ? `MHD-calibrated standoff ${traced.parameters.standoffRe.toFixed(2)} Re`
        : `Shue standoff ${driver.subsolarStandoffRe.toFixed(2)} Re`} · Bz ${driver.bzGsmNt.toFixed(1)} nT · Pd ${driver.dynamicPressureNpa.toFixed(2)} nPa · tilt ${(tilt.radians * 180 / Math.PI).toFixed(1)}°`,
    };
    this.fieldLineGroup.add(lines);

    // No closed boundary envelope is drawn around the lines. There used to be
    // a translucent Shue + Nguyen context surface here, and under quiet
    // drivers — tail dissolved, ruler foreshortened — it degenerated into a
    // smooth white ball around everything, exactly the "perfect sphere" Sean
    // flagged and exactly the outline-with-nothing-inside this project
    // retired. The field lines themselves carry the shape: compressed dayside
    // loops, open caps, stretched two-lobe tail. Only the exterior-cusp
    // funnels remain as context, because they are localized, meaningfully
    // non-spherical, and mark where the boundary-truncated lines converge and
    // the guided solar wind falls in. They are OFF until the reader ticks
    // "Annotation: polar cusps" in this layer's settings -- see
    // `cuspFunnelsEnabledValue` for why the default flipped.
    const cusped = this.cuspedDrivers(driver);
    if (cusped && this.cuspFunnelsEnabledValue) {
      const funnel = createExteriorCuspGeometry(cusped, {
        positionForGsm: (xRe, yRe, zRe) => this.modelGsmPosition(xRe, yRe, zRe),
        thetaSegments: 64,
        azimuthSegments: 64,
      });
      if (funnel) {
        const mesh = new THREE.Mesh(funnel.geometry, this.exteriorCuspMaterial());
        mesh.name = "field-line-context-exterior-cusp";
        mesh.userData = {
          role: "context-cusp-funnel-for-field-lines",
          status: "empirical",
        };
        this.fieldLineGroup.add(mesh);
        // Set HERE, at the one statement that puts the funnels in the scene,
        // rather than from the drivers that might have supported them.
        this.fieldLineCuspFunnelsValue = true;
      }
    }
    // Hand the solar wind the traced lines to couple to: the guided
    // sub-population follows these exact polylines when both layers are on,
    // and carries on round the rest of the Dungey cycle when the plasma-sheet
    // layer is on as well.
    this.tracedFieldLinesValue = traced.lines;
    this.refreshFieldGuidance();
    this.applyFieldLineVisibility();
  }

  private clearFieldLines() {
    this.disposeGroup(this.fieldLineGroup);
    this.fieldLineSignature = "";
    this.fieldLineSummaryValue = null;
    this.fieldLineIntegrityValue = null;
    this.fieldLineCuspFunnelsValue = false;
    this.fieldLineGroup.visible = false;
    this.tracedFieldLinesValue = null;
    this.refreshFieldGuidance();
  }

  /**
   * What the guided wind is allowed to do past the lobes, for this instant and
   * these layers.
   *
   * Null in every case where the site does not know enough to draw it, and
   * each null is a different fact:
   *
   *   - the reader has not asked for the plasma sheet, so the ride ends at the
   *     lobes exactly as it did before this existed;
   *   - there is no measured substorm state, which is what happens past the
   *     propagation lead — no measured Bz means no loading means no inner edge
   *     to inject to;
   *   - there is no dipole tilt for the instant, and the whole tail geometry
   *     hangs off the tilt;
   *   - there are no propagated drivers, so there is no Shue boundary to check
   *     the drawn path against, and an unchecked path through the tail is how
   *     the inner plasma sheet came to be drawn in the magnetosheath.
   *
   * Nothing here supplies a default for any of them.
   */
  private tailReturnOptions(): TailReturnOptions | null {
    // NOT GATED ON THE PLASMA-SHEET LAYER ANY MORE. It was, and that put the
    // second half of the wind's repertoire — the turn at the neutral line, the
    // injection earthward, the split into the ring current and the aurora —
    // behind a switch. Sean, 2026-08-27: "The particles should show all the
    // different movements regardless." What keeps it honest with those layers
    // off is the wind's own faint guidance cue, which draws the polylines the
    // particles ride, broken into dashes wherever the geometry is schematic
    // rather than traced. The MEASURED inputs below are still hard requirements: no
    // substorm state, no driver or no tilt and there is no chain, because
    // there would be nothing to shape it with.
    const state = this.substormStateValue;
    const driver = this.lastMagnetopauseDriver;
    const tilt = dipoleTilt(this.simulationTime);
    if (!state || !driver || !tilt) return null;
    return {
      dipoleTiltRad: tilt.radians,
      // The inner edge the plasma-sheet layer is DRAWING, from the same
      // measured substorm state, so the injected stream arrives at the edge of
      // the wedge on screen rather than at a number of its own.
      innerEdgeRe: innerEdgeRe(state),
      auroraBranch: this.auroraLayerEnabled,
      magnetopause: {
        subsolarStandoffRe: driver.subsolarStandoffRe,
        flaringAlpha: driver.flaringAlpha,
      },
    };
  }

  /**
   * Rebuild the guided paths without re-tracing the field.
   *
   * Guarded by a signature that spans the traced set AND the layers and
   * measured quantities the return legs depend on, because this is now called
   * from three places that fire on every clock tick.
   */
  private refreshFieldGuidance() {
    const options = this.tailReturnOptions();
    const signature = [
      this.tracedFieldLinesValue ? this.fieldLineSignature : "none",
      options
        ? [
          options.dipoleTiltRad.toFixed(3),
          options.innerEdgeRe.toFixed(2),
          options.auroraBranch ? "aurora" : "no-aurora",
          options.magnetopause?.subsolarStandoffRe.toFixed(2) ?? "no-boundary",
          options.magnetopause?.flaringAlpha.toFixed(3) ?? "",
        ].join(":")
        : "off",
    ].join("|");
    if (signature === this.fieldGuidanceSignature) return;
    this.fieldGuidanceSignature = signature;
    if (!this.tracedFieldLinesValue) {
      this.solarWindVisual.setFieldGuidance(null);
      return;
    }
    this.solarWindVisual.setFieldGuidance(this.tracedFieldLinesValue, { tailReturn: options });
  }

  /**
   * The MEASURED rate the tail-return legs are animated at.
   *
   * `main.ts` computes it with `couplingDrive()` from the published Newell
   * et al. (2007) coupling function and the published band ladder, because
   * that ladder arrives inside the storm artifact and the globe never reads
   * artifacts directly. Null means there is no coupling number for the
   * selected instant, and the population comes off rather than idling.
   */
  setDungeyCouplingDrive(drive: number | null) {
    this.solarWindVisual.setCouplingDrive(drive);
  }

  /** What the last tail-return build did, for the legend and for tests. */
  getTailReturnReport() {
    return this.solarWindVisual.tailReturnReport;
  }

  private applyFieldLineVisibility() {
    this.fieldLineGroup.visible = this.geospaceLayerEnabled
      && this.fieldLineGroup.children.length > 0;
    // THE WIND MOVES THE SAME WAY WHICHEVER LAYERS ARE ON.
    //
    // It used to couple only while the magnetosphere layer was drawing the
    // field: with that layer off, every particle went back to pure obstacle
    // deflection, so the cusp funnelling, the snap-back and the plasma-sheet
    // and ring-current destinations were all behind a second switch. Sean,
    // 2026-08-27: "Yeah I guess the solar wind should move the same regardless
    // of what layer is turned on... The particles should show all the
    // different movements regardless."
    //
    // So the gate is now whether there are lines to ride, not whether they are
    // on screen. What keeps that honest is the second call: with the
    // magnetosphere layer off, the wind draws a faint cue of the guidance
    // polylines its own particles are riding, so nothing bends for a reason
    // the reader cannot see. See SOLAR_WIND_GUIDANCE_CUE.
    //
    // No new work per frame: the trace and the guided roster are already built
    // whenever a propagated driver exists, whatever the layer switches say.
    // What changes is that a few hundred more tracers are DRAWN.
    this.solarWindVisual.setCouplingActive(this.fieldLineGroup.children.length > 0);
    this.solarWindVisual.setFieldLinesDrawnElsewhere(this.fieldLineGroup.visible);
    this.applyCuspEntryVisibility();
  }

  private applyCuspEntryVisibility() {
    // Retired as a standalone cue. Sean's rule: particle motion appears only
    // when a charged-particle layer is on. With the solar wind on, its guided
    // species particles are what funnel into the cusps — along the drawn
    // field lines, not on a separate set of marks — so a second mark set here
    // was both redundant there and a surprise when the field was drawn alone.
    this.cuspEntryGroup.visible = false;
  }

  /** The numeric state of the driven field lines, for the layer's legend. */
  getFieldLineSummary(): FieldLineSummary | null {
    return this.fieldLineSummaryValue;
  }

  /** The per-rebuild integrity report, so the card can refuse honestly when a trace fails its own checks. */
  getFieldLineIntegrity(): FieldLineIntegrityReport | null {
    return this.fieldLineIntegrityValue;
  }

  /** Whether the amber cusp funnels are drawn beside the lines right now, so the legend can name them only when they are there. */
  getFieldLineCuspFunnelsDrawn(): boolean {
    return this.fieldLineCuspFunnelsValue;
  }

  /** Whether the reader has asked for the polar-cusp funnels at all. */
  get cuspFunnelsEnabled() {
    return this.cuspFunnelsEnabledValue;
  }

  /**
   * Show or hide the polar-cusp funnels, everywhere this class draws them.
   *
   * Both draws are built inside a populate pass rather than parked in a group
   * of their own, so the switch rebuilds rather than flips a `visible` flag.
   * That is the same shape `setMagnetopauseDisplay` already uses, and it keeps
   * `getFieldLineCuspFunnelsDrawn` meaning exactly what it says -- the legend
   * row follows the mesh because the flag is still set at the one statement
   * that puts the mesh in the scene, and nowhere else. The field-line rebuild
   * costs one re-trace (25-60 ms), once per click.
   */
  setCuspFunnelsEnabled(enabled: boolean) {
    if (enabled === this.cuspFunnelsEnabledValue) return;
    this.cuspFunnelsEnabledValue = enabled;
    if (this.lastMagnetopauseDriver && this.magnetosphereDataAvailable) {
      this.populateMagnetosphere(this.magnetosphere, this.lastMagnetopauseDriver);
    }
    if (this.lastMagnetopauseDriver) this.populateFieldLines(this.lastMagnetopauseDriver);
    else this.fieldLineCuspFunnelsValue = false;
  }

  /** Whether the NOAA MHD cut planes are drawn inside the 3-D scene. */
  get mhdCutEnabled() {
    return this.mhdCutEnabledValue;
  }

  setMhdCutEnabled(enabled: boolean) {
    if (enabled === this.mhdCutEnabledValue) return;
    this.mhdCutEnabledValue = enabled;
    this.applyGeospaceLayerVisibility();
    this.frameActiveLayers();
  }

  /**
   * The opening view of the 3-D magnetosphere: three-quarters on, slightly
   * north, Sun on the LEFT — the angle every reference rendering of the
   * system uses, in which the compressed dayside, both cusps and the tail are
   * all visible at once. Framed on the boundary system rather than the full
   * tail cutoff, so the Earth stays a legible sphere and the tail runs off
   * frame exactly as the reference depictions crop it.
   *
   * WHICH SIDE THE SUN IS ON IS THE POINT OF THIS PRESET, not a by-product.
   * Sean, 2026-08-27: "when we pull up magnetosphere it should be oriented so
   * that the sun is on the left of the page, just like we had it before."
   * Measured on the running page: `cameraPose().sunScreenX` is -0.758 here,
   * where negative is left. It comes out of the 0.72 weight on GSM +y (dusk)
   * against the 0.62 on sunward — three.js's screen-right, cross(up, back),
   * resolves that combination anti-sunward. Change either weight and check
   * that number before you ship it.
   *
   * Who calls this, and the rule that decides when: `orientMagnetosphereOnPullUp`
   * in `main.ts`, which is the ONE layer-driven camera move left on this site
   * and is guarded so it cannot rotate the globe under a reader. See 71b1437
   * and 3fd8089 for why every other one was removed.
   */
  focusMagnetosphereObliqueView() {
    const distance = this.distanceToFrame(Math.max(
      this.magnetosphereDisplayRadius(Math.max(20, this.magnetopauseStandoffRe * 1.9)),
      DEFAULT_VIEW_SCENE_RADIUS,
    ));
    this.sunFrameGroup.updateMatrixWorld(true);
    const quaternion = this.sunFrameGroup.quaternion;
    const gsmSunward = gsmSceneAxes(1, 0, 0).applyQuaternion(quaternion).normalize();
    const gsmNorth = gsmSceneAxes(0, 0, 1).applyQuaternion(quaternion).normalize();
    const gsmDusk = gsmSceneAxes(0, 1, 0).applyQuaternion(quaternion).normalize();
    const direction = gsmSunward.multiplyScalar(0.62)
      .add(gsmDusk.multiplyScalar(0.72))
      .add(gsmNorth.clone().multiplyScalar(0.34))
      .normalize();
    this.cameraDolly = null;
    this.camera.position.copy(direction).multiplyScalar(distance);
    this.camera.up.copy(gsmNorth);
    this.controls.target.set(0, 0, 0);
    this.autoFrameDistance = distance;
    this.controls.update();
  }

  /**
   * The outermost surface actually drawn, per direction, in physical Re.
   *
   * The solar-wind tracers deflect around this. They used to deflect around a
   * sphere sized on the subsolar standoff, and every one of these models
   * flares — Nguyen reaches about 1.4x its standoff at the terminator — so on
   * the flanks the sphere sat well inside the drawn surface and roughly one
   * tracer in eight was rendered inside the boundary the reader was looking
   * at. Deflection was happening; it was happening around the wrong shape.
   *
   * Two deliberate choices. Nguyen contributes its *unindented* radius,
   * because the cusp notch is an indentation in the current sheet and not a
   * channel the upstream flow is funnelled into; and each cusped model is held
   * at its own 120-degree cutoff rather than extrapolated, with Shue — the only
   * one of the three fitted down the tail — carrying the rest.
   */
  private drawnBoundaryRadiusField(
    drivers: CuspedBoundaryDrivers,
    drawn: readonly MagnetopauseModelId[],
    cuspedCutoffRad: number,
  ): ((thetaRad: number, azimuthRad: number) => number) | null {
    const contributors: Array<(thetaRad: number, azimuthRad: number) => number> = [];
    for (const id of drawn) {
      if (id === "nguyen2022") {
        const parameters = nguyenBoundary(drivers);
        if (!parameters) continue;
        contributors.push((theta, azimuth) =>
          nguyenUnindentedRadiusRe(Math.min(theta, cuspedCutoffRad), azimuth, drivers, parameters));
        continue;
      }
      const evaluator = magnetopauseEvaluator(id, drivers);
      if (!evaluator) continue;
      const cutoff = id === "shue1998" ? Math.PI : cuspedCutoffRad;
      contributors.push((theta, azimuth) => evaluator.radiusRe(Math.min(theta, cutoff), azimuth));
    }
    if (contributors.length === 0) return null;
    return (thetaRad, azimuthRad) => {
      let radius = 0;
      for (const contributor of contributors) {
        const candidate = contributor(thetaRad, azimuthRad);
        if (Number.isFinite(candidate) && candidate > radius) radius = candidate;
      }
      return radius > 0 ? radius : Number.NaN;
    };
  }

  /**
   * The scene's single radial ruler, shared by every layer.
   *
   * The globe used to carry two incompatible logarithmic compressions: the
   * satellite one (displayRadius, on altitude) and a much harsher geospace one
   * for the magnetopause and the SWMF cuts. Under those two rulers a
   * geostationary satellite — physically well inside the magnetopause — was
   * drawn at scene radius 229.8 while the magnetopause nose sat at 125.1, so
   * satellites appeared to orbit outside the boundary that contains them, and
   * the whole 1.2–12 Earth-radii belt system collapsed into a skin on the
   * globe. radiationBeltDisplayRadius is the same curve as displayRadius
   * expressed in Earth radii, so routing every layer through it puts
   * satellites, belts, magnetopause and the SWMF cut planes on one ruler and
   * makes "is this satellite inside the outer belt / inside the magnetopause"
   * answerable by eye.
   *
   * The curve itself lives in `src/radial-ruler.ts` and is no longer purely
   * logarithmic: from geostationary orbit out to the bow-shock nose it is
   * linear, so the boundary system's shape — a 1.64x nose-to-flank flare with
   * the site's own live drivers — survives to the screen instead of rendering
   * as a 1.07x near-sphere. Radial distance is still compressed and must not
   * be read quantitatively.
   */
  private magnetosphereDisplayRadius(radiusRe: number) {
    return radiationBeltDisplayRadius(radiusRe, EARTH_SCENE_RADIUS);
  }

  private modelPlanePosition(xRe: number, crossRe: number, plane: GeospacePlane) {
    return plane === "equatorial"
      ? this.modelGsmPosition(xRe, crossRe, 0)
      : this.modelGsmPosition(xRe, 0, crossRe);
  }

  /**
   * The GSM mapper is now purely radial: no anti-sunward stretch.
   *
   * The scene used to pull the nightside out 1.85x along the Sun-Earth axis,
   * because under the old logarithmic ruler the magnetotail rendered as a
   * sphere and something had to fake the elongation. The ruler now carries the
   * elongation genuinely — the drawn tail reaches 2.4x the drawn nose
   * distance, versus 2.0x under the stretch — so the exaggeration would only
   * double-count, and removing it also removes the one place the scene ever
   * departed from a pure radial map. Every layer in every frame is now on
   * exactly one ruler in every direction.
   */
  /**
   * The drawn radius of the frame's far corner, measured at the plane the
   * camera is looking at. Perspective, so this is the half-height at the
   * target distance times the aspect on the diagonal.
   */
  private viewCornerSceneRadius() {
    const distance = this.camera.position.distanceTo(this.controls.target);
    const halfHeight = distance * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2);
    return Math.hypot(halfHeight * this.camera.aspect, halfHeight);
  }

  private modelGsmPosition(xRe: number, yRe: number, zRe: number) {
    const physicalRadius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
    const scale = this.magnetosphereDisplayRadius(physicalRadius) / physicalRadius;
    // Scene Y is GSM Z and scene -Z is GSM Y, matching both published cuts.
    return gsmSceneAxes(xRe, yRe, zRe).multiplyScalar(scale);
  }

  /**
   * Placement for the radiation-belt layer, which owns its own radial policy
   * in src/radiation-belt.ts. It resolves to the same ruler as everything else
   * today; keeping the call site named separately means a later change to the
   * geospace compression cannot silently flatten the belts again.
   */
  private modelRadiationPosition(xRe: number, yRe: number, zRe: number) {
    const physicalRadius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
    const scale = radiationBeltDisplayRadius(physicalRadius, EARTH_SCENE_RADIUS) / physicalRadius;
    return gsmSceneAxes(xRe, yRe, zRe).multiplyScalar(scale);
  }

  distanceScale(): DistanceScaleId {
    return activeDistanceScale();
  }

  /**
   * Switch the whole scene between the teaching ruler and true distance.
   *
   * The ruler itself flips in `src/radial-ruler.ts`; what this method owns is
   * everything that HOLDS geometry baked through the old ruler — the two
   * scales must never mix on screen, so every baked consumer is rebuilt in
   * the same call: satellites and the selected orbit line, the boundary
   * surfaces, field lines and cusp cue, the plasmasphere stipple, the SWMF
   * cut planes/streamlines/belt volume, the solar-wind tracers, and the
   * ionosphere + D-region shells (whose teaching-scale curves are private
   * but whose true-distance branch is the shared k).
   *
   * Camera: entering true distance re-frames whatever is drawn (the same
   * structures sit up to 8.8x further out, so keeping the old distance would
   * leave the visitor inside the belts staring at haze); returning restores
   * the exact camera they left the teaching scale with.
   */
  setDistanceScale(scale: DistanceScaleId) {
    if (scale === activeDistanceScale()) return;
    const enteringTrueDistance = scale === "true-distance";
    if (enteringTrueDistance) {
      this.teachingCameraState = {
        position: this.camera.position.clone(),
        up: this.camera.up.clone(),
        target: this.controls.target.clone(),
        autoFrameDistance: this.autoFrameDistance,
      };
    }
    setActiveDistanceScale(scale);
    this.applyCameraRangeForScale(scale);
    this.rebuildRadialGeometry();
    if (!enteringTrueDistance && this.teachingCameraState) {
      const saved = this.teachingCameraState;
      this.teachingCameraState = null;
      this.cameraDolly = null;
      this.camera.position.copy(saved.position);
      this.camera.up.copy(saved.up);
      this.controls.target.copy(saved.target);
      this.autoFrameDistance = saved.autoFrameDistance;
      this.controls.update();
    } else {
      this.frameActiveLayers({ force: true });
    }
  }

  /**
   * How far out the camera may sit, and how far it can see, per scale.
   *
   * Teaching: the deepest drawn point (the -55 Re cut corner) lands near 740
   * units, framed from 2,265 on the desktop scene, so the zoom limit is 2,500.
   * True distance: the same corner is at sqrt(55² + 35²) = 65.2 Re = 6,520
   * units, and framing it with VIEW_EDGE_MARGIN_FRACTION clear costs 19,961 of
   * camera distance — so the zoom limit is 21,800 and the far plane 28,500
   * (21,800 + 6,520 of reach + margin). Both limits are sized for the desktop
   * scene; the constructor says why a phone is left to frame against them.
   * The near plane stays at 1: for a
   * perspective depth buffer the resolution near the camera is set by the
   * near plane, and (far-near)/far moves only from 0.9997 to 0.99996, so the
   * enlarged far plane costs no legible depth precision at the globe.
   */
  private applyCameraRangeForScale(scale: DistanceScaleId) {
    if (scale === "true-distance") {
      this.controls.maxDistance = 21800;
      this.camera.far = 28500;
    } else {
      this.controls.maxDistance = 2500;
      this.camera.far = 3600;
    }
    this.camera.updateProjectionMatrix();
  }

  /** Every consumer that bakes drawn radii, rebuilt through the live ruler. */
  private rebuildRadialGeometry() {
    this.reprojectSatellites();
    if (this.lastSelectedGeometryInputs) {
      const inputs = this.lastSelectedGeometryInputs;
      this.setSelectedGeometry(inputs.orbitPoints, inputs.groundPoints, inputs.footprint, inputs.frameDate);
    }
    // The field-line signature deliberately hashes only the drivers; the
    // ruler changed under it, so clear it or the populate call would no-op.
    this.fieldLineSignature = "";
    if (this.lastMagnetopauseDriver) {
      this.populateMagnetosphere(this.magnetosphere, this.lastMagnetopauseDriver);
      this.populateFieldLines(this.lastMagnetopauseDriver);
    }
    // Same story for the plasmasphere's rebuild key: identical field, new ruler.
    const plasmasphereField = this.plasmasphereFieldState;
    if (plasmasphereField) {
      this.plasmasphereFieldState = null;
      this.setPlasmasphere(plasmasphereField);
    }
    // And the ring-current drift paths, whose every vertex was mapped through
    // the ruler when it was built. Same trick: clear the guard so the rebuild
    // is not mistaken for a no-op, because the illustration itself is
    // unchanged and only the drawing of it moved.
    const ringCurrent = this.ringCurrentState;
    if (ringCurrent) {
      this.ringCurrentState = null;
      this.setRingCurrent(ringCurrent);
    }
    // Cut planes, streamlines, named structures and the belt-volume rebake.
    if (this.geospace) this.setGeospaceModel(this.geospace);
    // The solar-wind tracers remap through the shared mapper on every motion
    // tick; force one now so a paused scene cannot hold old-ruler positions.
    this.solarWindVisual.update(0);
    if (this.ionosphereBundle) this.setIonosphereModel(this.ionosphereBundle);
    // Rewrites the D-region surface's vertex positions through its
    // scale-aware radius without moving the simulation clock.
    this.dRegionEmpirical.setSimulationTime(this.simulationTime);
    // CORRECTNESS FIX 2026-09-04: the two environment surfaces were missing
    // from this sweep, so the D-RAP map and the auroral oval stayed at the
    // radius they were built at while everything around them moved. They are
    // on the shared ruler now (`environment-surface-layer.ts`), and this is
    // what keeps them on it.
    this.drapSurface?.rebuildForDistanceScale();
    this.auroraHistorySurface?.rebuildForDistanceScale();
    // The three schematic D/E/F shells are rebuilt for the same reason.
    this.rebuildRegionShells();
  }

  /**
   * Redraw every satellite at its remembered physical state through the live
   * ruler. Interpolation is dropped rather than continued: its endpoints were
   * scene positions on the old ruler, and lerping across scales would draw
   * every spacecraft somewhere neither scale puts it.
   */
  private reprojectSatellites() {
    this.latestStates.forEach((state, index) => {
      if (!state || this.satelliteRenderable[index] !== 1) return;
      const position = this.geoRadiansToVector(
        state.latitudeRad,
        state.longitudeRad,
        this.displayRadius(state.altitudeKm),
      );
      const offset = index * 3;
      this.satellitePositions.setXYZ(index, position.x, position.y, position.z);
      this.satelliteFrom[offset] = position.x;
      this.satelliteFrom[offset + 1] = position.y;
      this.satelliteFrom[offset + 2] = position.z;
      this.satelliteTargets[offset] = position.x;
      this.satelliteTargets[offset + 1] = position.y;
      this.satelliteTargets[offset + 2] = position.z;
    });
    this.interpolationActive = false;
    this.satellitePositions.needsUpdate = true;
  }

  setGeospaceModel(bundle: GeospaceBundle) {
    this.geospaceRuntime?.dispose();
    this.geospaceRuntime = null;
    this.geospaceGroup.clear();
    this.geospace = bundle;
    const runtime = new GeospaceRuntime({
      bundle,
      parent: this.geospaceGroup,
      field: this.geospaceField,
      plane: this.geospacePlaneMode,
      plasmaSheetPlane: this.plasmaSheetPlaneMode,
      plasmaSheetEnabled: this.plasmaSheetLayerEnabled,
      displayMode: this.fieldRendering,
      radiationView: this.radiationView,
      radiationEnergyKev: this.radiationEnergyKev,
      radiationPitchIndex: this.radiationPitchIndex ?? undefined,
      positionForPlane: (xRe, crossRe, plane) => this.modelPlanePosition(xRe, crossRe, plane),
      positionForGsm: (xRe, yRe, zRe) => this.modelGsmPosition(xRe, yRe, zRe),
      positionForRadiation: (xRe, yRe, zRe) => this.modelRadiationPosition(xRe, yRe, zRe),
      pixelRatio: this.renderer.getPixelRatio(),
      modelSecondsPerDisplaySecond: 45,
      // Embedded-cross-section extent: the cut is a slice through the 3-D
      // scene, clipped to the boundary region; the -55 Re tail corners belong
      // to the face-on study view of the data, not to the slice.
      cutExtentRe: { minimumXRe: -40, maximumCrossRe: 26 },
    });
    this.geospaceRuntime = runtime;
    this.geospaceSimulationTimeMs = null;
    this.solarWindModelFrameValidAt = undefined;
    this.updateGeospaceForSimulationTime(true);
    this.applyGeospaceLayerVisibility();
    // The bundle arrives asynchronously, well after the toggle that requested
    // it already re-framed the view. Frame again now that the cut planes and
    // structures actually exist, or a first-time visitor sees the field crop
    // off the edge of a camera sized for an empty layer.
    this.frameActiveLayers();
  }

  setGeospaceField(field: GeospaceField) {
    this.geospaceField = field;
    this.geospaceRuntime?.setField(field);
  }

  setGeospacePlane(plane: GeospacePlane | "both") {
    this.geospacePlaneMode = plane;
    this.geospaceRuntime?.setPlane(plane);
    this.applyGeospaceLayerVisibility();
  }

  setRadiationEnergy(energyKev: number) {
    this.radiationEnergyKev = energyKev;
    this.geospaceRuntime?.setRadiationEnergy(energyKev);
  }

  setRadiationView(view: RadiationBeltRuntimeView) {
    this.radiationView = view;
    this.geospaceRuntime?.setRadiationView(view);
  }

  setRadiationPitchIndex(index: number) {
    this.radiationPitchIndex = index;
    this.geospaceRuntime?.setRadiationPitchIndex(index);
  }

  getRadiationChoices() {
    return this.geospaceRuntime?.radiationChoices ?? null;
  }

  getGeospaceRuntimeState(): GeospaceRuntimeFrameState | null {
    return this.geospaceRuntime?.state ?? null;
  }

  getGeospaceLegendMetadata(): GeospaceRuntimeLegendMetadata | null {
    return this.geospaceRuntime?.getLegendMetadata() ?? null;
  }

  /** Which cut the derived plasma-beta layer is drawn on. */
  setPlasmaSheetPlane(plane: GeospacePlane | "both") {
    this.plasmaSheetPlaneMode = plane;
    this.geospaceRuntime?.setPlasmaSheetPlane(plane);
    this.applyGeospaceLayerVisibility();
  }

  get plasmaSheetPlane(): GeospacePlane | "both" {
    return this.plasmaSheetPlaneMode;
  }

  getPlasmaSheetLegendMetadata(): PlasmaSheetLegendMetadata | null {
    return this.geospaceRuntime?.getPlasmaSheetLegendMetadata() ?? null;
  }

  /**
   * Show one named region of the coupled cross-section on its own.
   *
   * The bow shock, the magnetosheath and the field lines were only reachable
   * through the `geospace` layer, whose control is hidden from the public UI
   * because the two-plane plasma presentation is not finished. That left the
   * three structures a reader most needs — and which are fully published —
   * with no path to the screen at all. Each is now switchable by itself, and a
   * guided walkthrough can drive them one at a time.
   */
  setStructureRegion(region: GeospaceStructureRegion, visible: boolean) {
    if (visible) this.structureRegions.add(region);
    else this.structureRegions.delete(region);
    this.applyGeospaceLayerVisibility();
  }

  structureRegionEnabled(region: GeospaceStructureRegion) {
    return this.structureRegions.has(region);
  }

  /** Whether the published data for a region has arrived for the selected time. */
  structureRegionAvailable(region: GeospaceStructureRegion) {
    return this.geospaceRuntime?.structureRegionAvailable(region) ?? false;
  }

  private applyGeospaceLayerVisibility() {
    const runtime = this.geospaceRuntime;
    if (!runtime) {
      this.geospaceGroup.visible = false;
      return;
    }
    const ready = runtime.state.status === "ready";
    // The field layer no longer implies the boundary curves or the projected
    // lines. The field IS the layer — the bow shock, the sheath and the
    // magnetopause appear in its colours — and everything else in this bundle
    // is an explicitly chosen overlay: annotation curves for comparison, or
    // the projected line data for readers who ask for it. Nothing is drawn on
    // top of the field by default, and an overlay draws only while its layer
    // is on — its checkbox lives in that layer's card, so an overlay that
    // outlived the layer would be on screen with its only control hidden.
    // The chosen overlays are remembered: switching the layer back on
    // restores them.
    const region = (name: GeospaceStructureRegion) =>
      ready && this.geospaceLayerEnabled && this.structureRegions.has(name);
    // The MHD cut is the layer's embedded cross-section OPTION. The layer's
    // default face is the 3-D driven field lines + boundary in
    // `fieldLineGroup`; a coloured plane only appears when explicitly asked
    // for, and then as a slice within the 3-D scene.
    runtime.cutGroup.visible = ready && this.geospaceLayerEnabled && this.mhdCutEnabledValue;
    // The BATS-R-US plane tracers belong to that same option: two bright
    // beaded curves confined to the cut planes are evidence when the cut is
    // on screen to carry them, and an artifact floating over the volumetric
    // shower when it is not.
    this.solarWindVisual.setPlaneTracersVisible(runtime.cutGroup.visible);
    runtime.bowShockGroup.visible = region("bowShock");
    runtime.magnetosheathGroup.visible = region("magnetosheath");
    runtime.magnetopauseProxyGroup.visible = region("magnetopause");
    runtime.magneticStreamlineGroup.visible = region("magneticField");
    runtime.flowStreamlineGroup.visible = region("flowStreamlines");
    runtime.boundaryGroup.visible = runtime.bowShockGroup.visible
      || runtime.magnetosheathGroup.visible
      || runtime.magnetopauseProxyGroup.visible;
    runtime.streamlineGroup.visible = runtime.magneticStreamlineGroup.visible
      || runtime.flowStreamlineGroup.visible;
    // Avoid drawing two copies of the same projected model tracers when the
    // dedicated solar-wind visual is already active.
    runtime.flowAdvectionGroup.visible = region("flowTracers") && !this.solarWindGroup.visible;
    runtime.radiationGroup.visible = ready && this.radiationLayerEnabled;
    runtime.plasmaSheetGroup.visible = ready && this.plasmaSheetLayerEnabled;
    this.geospaceGroup.visible = ready && (
      this.geospaceLayerEnabled
      || this.radiationLayerEnabled
      || this.plasmaSheetLayerEnabled
      || runtime.boundaryGroup.visible
      || runtime.streamlineGroup.visible
      || runtime.flowAdvectionGroup.visible
    );
  }

  private updateGeospaceForSimulationTime(force = false) {
    const runtime = this.geospaceRuntime;
    if (!runtime) return;
    const requestedMs = this.simulationTime.getTime();
    if (
      !force
      && this.geospaceSimulationTimeMs !== null
      && Math.abs(requestedMs - this.geospaceSimulationTimeMs) < 5_000
    ) return;
    this.geospaceSimulationTimeMs = requestedMs;
    const state = runtime.setSimulationTime(this.simulationTime);
    this.updateSolarWindModelFlow(state);
    this.applyGeospaceLayerVisibility();
    if (state.status === "ready") {
      this.onGeospaceFrame?.(state.structureFrameValidAt, state.leadMinutes, state.runAt);
    }
  }

  private updateSolarWindModelFlow(state: GeospaceRuntimeFrameState) {
    const validAt = state.status === "ready" ? state.structureFrameValidAt : null;
    if (validAt === this.solarWindModelFrameValidAt) return;
    this.solarWindModelFrameValidAt = validAt;
    if (!validAt || !this.geospace) {
      this.solarWindVisual.setModelFlow(null);
      this.setFieldLineCalibration(null);
      return;
    }
    const bundle = this.geospace as unknown as GeospaceBundleWithStructures;
    const frame = bundle.frames.find((candidate) => candidate.validAt === validAt);
    if (!bundle.structures || !frame?.structures) {
      this.solarWindVisual.setModelFlow(null);
      this.setFieldLineCalibration(null);
      return;
    }
    this.solarWindVisual.setModelFlow({
      definition: bundle.structures,
      projectedFlowStreamlines: {
        equatorial: frame.structures.equatorial.projectedFlowStreamlines,
        meridional: frame.structures.meridional.projectedFlowStreamlines,
      },
    });
    this.setFieldLineCalibration(
      SpaceGlobe.calibrationFromFrame(bundle.structures, frame.structures, validAt, this.lastMagnetopauseDriver),
    );
  }

  /**
   * Fit the frame's own extracted magnetopause curves — both published planes
   * of the same 3-D surface — to the Shue functional form, so the drawn field
   * construction can be pinned to the MHD's boundary rather than to
   * Shue-from-L1 while this frame is on screen. The L1 Shue surface for the
   * current driver is passed as the reference, so the calibration carries the
   * before/after residuals the card reports. Archived frames publish these
   * curves too, which is exactly why the replay stays calibrated.
   */
  private static calibrationFromFrame(
    definition: GeospaceStructuresDefinition,
    structures: EncodedFrameStructures,
    frameValidAt: string,
    driver: MagnetopauseDriverSample | null,
  ): BoundaryCalibration | null {
    const points: BoundaryCurvePoint[] = [];
    for (const plane of ["meridional", "equatorial"] as const) {
      const radii = decodeBoundaryProfile(definition, structures[plane].magnetopauseProxyRadiusU16);
      definition.anglesDegrees.forEach((angleDegrees, index) => {
        const radiusRe = radii[index];
        if (radiusRe === null || radiusRe === undefined || !Number.isFinite(radiusRe)) return;
        points.push({ thetaRad: (Math.abs(angleDegrees) * Math.PI) / 180, radiusRe });
      });
    }
    const reference = driver
      ? shueBoundary(driver.dynamicPressureNpa, driver.bzGsmNt)
      : null;
    return fitShueToBoundaryCurve(
      points,
      reference ? { standoffRe: reference.subsolarStandoffRe, flaringAlpha: reference.flaringAlpha } : null,
      frameValidAt,
    );
  }

  /** Swap the active calibration and retrace the field lines if it changed. */
  private setFieldLineCalibration(calibration: BoundaryCalibration | null) {
    const before = this.fieldLineCalibration;
    const unchanged = before === calibration
      || (before !== null && calibration !== null
        && before.frameValidAt === calibration.frameValidAt
        && before.standoffRe === calibration.standoffRe);
    this.fieldLineCalibration = calibration;
    if (!unchanged && this.lastMagnetopauseDriver) {
      this.populateFieldLines(this.lastMagnetopauseDriver);
    }
  }

  updateSatellites(
    indices: Uint32Array,
    states: Float32Array,
    targetStates: Float32Array,
    valid: Uint8Array,
    targetValid: Uint8Array,
    interpolationDurationMs: number,
  ) {
    indices.forEach((sourceIndex, outputIndex) => {
      const index = Number(sourceIndex);
      const offset = outputIndex * 4;
      const isVisible = this.visible.has(index) && valid[outputIndex] === 1;
      if (!isVisible) {
        this.satellitePositions.setXYZ(index, 0, 0, 0);
        this.satelliteRenderable[index] = 0;
        this.latestStates[index] = null;
        return;
      }
      const latitudeRad = states[offset] ?? 0;
      const longitudeRad = states[offset + 1] ?? 0;
      const altitudeKm = states[offset + 2] ?? 0;
      const velocityKps = states[offset + 3] ?? 0;
      const radius = this.displayRadius(altitudeKm);
      const position = this.geoRadiansToVector(latitudeRad, longitudeRad, radius);
      const vectorOffset = index * 3;
      if (this.satelliteRenderable[index] === 0) {
        this.satellitePositions.setXYZ(index, position.x, position.y, position.z);
      }
      this.satelliteFrom[vectorOffset] = this.satellitePositions.getX(index);
      this.satelliteFrom[vectorOffset + 1] = this.satellitePositions.getY(index);
      this.satelliteFrom[vectorOffset + 2] = this.satellitePositions.getZ(index);

      const hasTarget = targetValid[outputIndex] === 1;
      const targetLatitude = hasTarget ? targetStates[offset] ?? latitudeRad : latitudeRad;
      const targetLongitude = hasTarget ? targetStates[offset + 1] ?? longitudeRad : longitudeRad;
      const targetAltitude = hasTarget ? targetStates[offset + 2] ?? altitudeKm : altitudeKm;
      const targetPosition = this.geoRadiansToVector(targetLatitude, targetLongitude, this.displayRadius(targetAltitude));
      this.satelliteTargets[vectorOffset] = targetPosition.x;
      this.satelliteTargets[vectorOffset + 1] = targetPosition.y;
      this.satelliteTargets[vectorOffset + 2] = targetPosition.z;
      this.satelliteRenderable[index] = 1;
      this.latestStates[index] = { latitudeRad, longitudeRad, altitudeKm, velocityKps };
    });
    this.interpolationStartedAt = performance.now();
    this.interpolationDurationMs = Math.max(0, interpolationDurationMs);
    this.interpolationActive = this.interpolationDurationMs > 0;
    if (!this.interpolationActive) this.applySatelliteInterpolation(1);
    this.satellitePositions.needsUpdate = true;
    this.selectionMarker.visible = this.selectedIndex !== null && this.satelliteRenderable[this.selectedIndex] === 1;
    this.frameNewlyDrawnSatellites(indices);
  }

  /**
   * Frame a newly chosen set of spacecraft, once its positions have arrived.
   *
   * A solution already in flight when the reader changed the selection
   * carries the OLD index list, and the new members are still at the origin
   * in it — framing off that would measure a set that is not on screen and
   * then never look again. So the framing waits for the first solution whose
   * index list covers every spacecraft now visible. Coverage rather than
   * validity: a spacecraft whose elements fail to propagate never becomes
   * renderable, and waiting for it would hold the frame open forever.
   */
  private frameNewlyDrawnSatellites(indices: Uint32Array) {
    if (!this.satelliteFramingPending) return;
    let covered = 0;
    indices.forEach((sourceIndex) => {
      if (this.visible.has(Number(sourceIndex))) covered += 1;
    });
    if (covered < this.visible.size) return;
    this.satelliteFramingPending = false;
    this.frameActiveLayers();
  }

  holdSatelliteInterpolation() {
    if (!this.interpolationActive) return;
    const amount = Math.min(1, (performance.now() - this.interpolationStartedAt) / this.interpolationDurationMs);
    this.applySatelliteInterpolation(amount);
    this.interpolationActive = false;
  }

  setSatelliteColors(colors: readonly string[]) {
    colors.forEach((color, index) => {
      if (index >= this.satellites.length) return;
      const encoded = new THREE.Color(color);
      this.satelliteColors.setXYZ(index, encoded.r, encoded.g, encoded.b);
    });
    this.satelliteColors.needsUpdate = true;
  }

  setVisible(indices: Set<number>) {
    const previous = new Set(this.visible);
    this.visible.clear();
    indices.forEach((index) => this.visible.add(index));
    previous.forEach((index) => {
      if (this.visible.has(index)) return;
      this.satellitePositions.setXYZ(index, 0, 0, 0);
      this.satelliteRenderable[index] = 0;
      this.latestStates[index] = null;
    });
    this.satellitePositions.needsUpdate = true;
    // A DIFFERENT SET OF SPACECRAFT IS A DIFFERENT SUBJECT, so the frame is
    // reconsidered — once, here, at the choice, and never on the propagation
    // ticks in between, which would make the camera breathe with the orbits.
    //
    // This is the single door every entry point goes through: the featured
    // constellation of the day on load, every facet box, the solo buttons,
    // the select-all/clear-all controls, the orbit-band buttons, the
    // GEO-type buttons, show only the selected spacecraft, the mode switch
    // and the search/favourite paths all resolve to one `setVisible` call.
    // Hooking it here is what makes the reader's own selection behave the
    // same way the opening view does.
    //
    // An empty set needs no positions, so it is framed immediately; anything
    // else waits for a solution (see `satelliteFramingPending`).
    const changed = previous.size !== this.visible.size
      || [...this.visible].some((index) => !previous.has(index));
    if (!changed) return;
    if (this.visible.size === 0) this.frameActiveLayers();
    else this.satelliteFramingPending = true;
  }

  getState(index: number) {
    return this.latestStates[index] ?? null;
  }

  setSelected(index: number | null) {
    this.selectedIndex = index;
    this.selectionMarker.visible = index !== null && this.satelliteRenderable[index] === 1;
    if (index === null || !this.satelliteLabelsEnabled) {
      this.selectedLabel.classList.remove("is-visible");
    } else {
      this.setSatelliteLabel(this.selectedLabel, index);
      this.refreshLabelOcclusion(performance.now(), true);
      this.positionSatelliteLabel(this.selectedLabel, index);
    }
  }

  /**
   * The minimum-elevation mask angle (0/5/10 degrees) used both for the
   * geometry passed into setSelectedGeometry and for the live per-frame
   * footprint recompute in updateSelectedFootprintFromRenderedState, so the
   * shrinking coverage cap stays consistent as the satellite moves.
   */
  setFootprintMinElevation(minimumElevationDeg: number) {
    this.footprintMinElevationDeg = minimumElevationDeg;
  }

  setSelectedGeometry(
    orbitPoints: Array<{ latitudeDeg: number; longitudeDeg: number; altitudeKm: number }>,
    groundPoints: Array<[number, number]>,
    footprint: Array<[number, number]>,
    frameDate = this.simulationTime,
  ) {
    this.lastSelectedGeometryInputs = { orbitPoints, groundPoints, footprint, frameDate };
    this.disposeGroup(this.selectionOrbitGroup);
    this.disposeGroup(this.selectionEarthGroup);
    this.disposeGroup(this.selectionFootprintGroup);
    this.selectedOrbitFrameRotationY = greenwichSiderealAngle(frameDate);
    this.selectedFootprintVisible = footprint.length > 2;
    const orbitVectors = orbitPoints.map((point) => this.geoToVector(point.latitudeDeg, point.longitudeDeg, this.displayRadius(point.altitudeKm)));
    this.selectedOrbitDrawnReach = orbitVectors.reduce((reach, vector) => Math.max(reach, vector.length()), 0);
    const groundVectors = groundPoints.map(([lon, lat]) => this.geoToVector(lat, lon, 100.7));
    const footprintVectors = footprint.map(([lon, lat]) => this.geoToVector(lat, lon, 100.9));
    if (orbitVectors.length > 1) this.selectionOrbitGroup.add(this.line(orbitVectors, 0x5ce8f1, 0.92));
    if (groundVectors.length > 1) this.selectionEarthGroup.add(this.line(groundVectors, 0xff7b78, 0.72, true));
    if (footprintVectors.length > 2) {
      this.selectionFootprintGroup.add(this.buildFootprintFill(footprintVectors));
      this.selectionFootprintGroup.add(this.line(footprintVectors, 0xf5c96a, 0.98));
    }
    this.applyReferenceFrameTransforms();
  }

  clearSelectedGeometry() {
    this.lastSelectedGeometryInputs = null;
    this.selectedOrbitDrawnReach = 0;
    this.disposeGroup(this.selectionOrbitGroup);
    this.disposeGroup(this.selectionEarthGroup);
    this.disposeGroup(this.selectionFootprintGroup);
    this.selectedFootprintVisible = false;
  }

  /**
   * Hand the globe the measured substorm state for the selected instant.
   *
   * `null` takes the wedge off. That is what happens forward of the driver
   * record, and it is deliberate: there is no measured Bz past the propagation
   * lead, so there is no loading to draw and nothing is invented to fill it.
   */
  setSubstormState(state: SubstormState | null) {
    this.substormStateValue = state;
    // The inner edge the injected stream arrives at is this state's, so the
    // guided paths move with the measured substorm rather than standing still
    // through it. Before the early return below: the guidance does not depend
    // on the wedge having been constructed.
    this.refreshFieldGuidance();
    const sheet = this.innerPlasmaSheet;
    if (!sheet) return;
    // The tilt is a property of the instant being drawn. An untilted sheet
    // would sit at z = 0, which is the one place the real one reliably is NOT.
    const tilt = dipoleTilt(this.simulationTime);
    if (state && tilt) sheet.setState(state, tilt.radians);
    // No tilt means no instant the site can place the dipole at, and the sheet
    // centre is a function of the tilt. It comes off rather than being drawn
    // flat at z = 0, which is the one place the real one reliably is NOT.
    sheet.setVisible(this.ringCurrentLayerEnabled && state !== null && tilt !== null);
  }

  /**
   * THERE IS NO FORECAST MAGNETOSPHERE, AND NOTHING IS DRAWN PAST THE LAST
   * MEASUREMENT. There is deliberately no method here to draw one.
   *
   * A forecast band used to live at this point in the file: two Shue surfaces
   * at the corners of the measured driver envelope, joined into a closed body
   * and drawn across the whole forward half of the clock. `a0bf46f` built it
   * and `a810bef` re-inked it as a Fresnel rim after it rendered as a disc of
   * light. Sean, on the shipped build: *"what the fuck am I seeing in the
   * future? It looks ridiculous. If we can't get a forecasted magnetosphere,
   * just leave it off."*
   *
   * The ink was never the fault. Past the last measurement the drivers stop,
   * so the traced field lines, the cusps, the empirical surfaces and the NOAA
   * plasma field all correctly come off — and the band was left alone in an
   * empty scene, an open bowl reaching 597 scene units in a view framed for
   * 266 (measured, this build), with Earth a speck inside it. It was also
   * invisible to `sceneRadiusForActiveLayers()`, which never counted it, so
   * the camera could not even have framed it. Nothing in that picture said
   * "this is what we do not know"; it said "here is the magnetosphere", and it
   * was a shape nobody had measured.
   *
   * Why no replacement can be built from published data — the ENLIL and Kp
   * measurements that settle it — is in `src/magnetopause-forecast.ts`. What
   * the reader gets instead is the layer switched off and a card that says so,
   * built by `magnetosphereFieldLegendSpec` from `magnetopauseNoForecastAt`.
   */


  /** What the wedge is currently drawing, for the key card and for tests. */
  getInnerPlasmaSheetState(): Record<string, unknown> | null {
    const drawn = this.innerPlasmaSheet?.group.userData.state as Record<string, unknown> | undefined;
    return drawn ?? null;
  }

  setLayer(layer: "ionosphere" | "tec" | "aurora" | "drap" | "regions" | "magnetosphere" | "geospace" | "solarWind" | "photons" | "radiation" | "plasmaSheet" | "groundField" | "plasmasphere" | "ringCurrent" | "thermosphere", visible: boolean) {
    if (layer === "plasmasphere") {
      this.plasmasphereLayerEnabled = visible;
      this.plasmasphereGroup.visible = visible && this.plasmasphereFieldState !== null;
    }
    if (layer === "ringCurrent") {
      this.ringCurrentLayerEnabled = visible;
      this.ringCurrentGroup.visible = visible && this.ringCurrentState !== null;
      // One toggle, both populations. The sheet shows even when the ring
      // current has no frame to draw from, because its own drivers are a
      // different feed and the reader should not lose the supply because the
      // destination is unavailable.
      this.innerPlasmaSheet?.setVisible(visible && this.substormStateValue !== null);
      // The guided wind's ride now depends on this layer: with it on, the lobe
      // ride carries on round the rest of the Dungey cycle into the wedge this
      // layer draws. Off, it ends at the lobes exactly as it did before.
      this.refreshFieldGuidance();
    }
    if (layer === "thermosphere") {
      this.thermosphereEnabled = visible;
      this.thermosphere?.setEnabled(visible);
      return;
    }
    if (layer === "groundField") {
      this.groundFieldLayerEnabled = visible;
      this.groundField?.setEnabled(visible);
    }
    if (layer === "ionosphere") {
      this.ionosphereVolumeEnabled = visible;
      // The peak surfaces stay hidden whatever this toggle does; see
      // setIonosphereModel for why they were retired from the scene.
      if (this.ionosphereVolume) this.ionosphereVolume.points.visible = false;
      this.ionosphereDensityVolume?.setEnabled(visible && this.ionosphereVolumeDataAvailable);
      // The empirical D-region EFFECTIVE-HEIGHT surface is a different figure
      // from the density volume's D band -- h' is a VLF reflection height, not
      // a density contour -- but drawn together they read as one doubled
      // shell, so the volume owns the bottom of the picture and the h' surface
      // stays off while it is on.
      this.dRegionEmpirical.mesh.visible = visible && !this.ionosphereDensityVolume;
      this.applyAirglowVisibility();
    }
    if (layer === "tec") this.ionosphere.visible = visible;
    if (layer === "aurora") {
      this.auroraLayerEnabled = visible;
      // With the oval on, a share of the injected electrons stops drifting and
      // falls down the field line into it instead.
      this.refreshFieldGuidance();
      if (this.auroraHistorySurface) {
        this.auroraHistorySurface.setEnabled(visible);
        // The exact rolling model replaces, rather than overlays, the legacy
        // latest-frame texture. Missing historical time stays visibly missing.
        this.aurora.visible = false;
      } else {
        // Before the exact OVATION history bundle has finished loading,
        // `this.aurora` has no data plotted into it either: `updateAurora()`
        // is never called with real points in production (this.auroraPoints
        // starts as [] and nothing populates it — main.ts always drives the
        // history surface via setAuroraHistoryModel instead), so this mesh's
        // MeshBasicMaterial carries no map and no colour override, which
        // three.js renders as flat opaque white. Showing it here used to
        // flash that untextured, additively-blended, near-Earth-radius
        // sphere over the whole globe for the second or so
        // loadAuroraHistoryModel() takes to fetch the artifact — reported as
        // "the entire Earth blinks white for a second-ish when the aurora
        // layer loads." Stay hidden and let the real texture appear once the
        // fetch resolves and setAuroraHistoryModel() mounts it.
        this.aurora.visible = false;
      }
    }
    if (layer === "drap") {
      this.drapLayerEnabled = visible;
      this.drapSurface?.setEnabled(visible);
    }
    if (layer === "regions") this.regionGroup.visible = visible;
    if (layer === "magnetosphere") {
      this.magnetosphereLayerEnabled = visible;
      this.magnetosphere.visible = visible && this.magnetosphereDataAvailable;
      this.applyCuspEntryVisibility();
      // The wind layer's own obstacle cue is only there for when this is off.
      this.solarWindVisual.setBoundaryDrawnElsewhere(this.magnetosphere.visible);
    }
    if (layer === "geospace") {
      this.geospaceLayerEnabled = visible;
      this.applyGeospaceLayerVisibility();
      this.applyFieldLineVisibility();
    }
    if (layer === "solarWind") {
      this.solarWindLayerEnabled = visible;
      this.solarWindGroup.visible = visible && this.solarWindDataAvailable;
      this.applyGeospaceLayerVisibility();
      this.applyCuspEntryVisibility();
    }
    if (layer === "photons") {
      this.photonLayerEnabled = visible;
      this.photonGroup.visible = visible && this.photonDataAvailable;
    }
    if (layer === "radiation") {
      this.radiationLayerEnabled = visible;
      this.applyGeospaceLayerVisibility();
    }
    if (layer === "plasmaSheet") {
      this.plasmaSheetLayerEnabled = visible;
      // Before the visibility sweep and before any legend read: deriving beta
      // is a measured 230 ms per frame change, so the runtime does not do it
      // while the layer is hidden. Switching on has to populate the group
      // first, or the layer would appear empty until the next timeline step.
      this.geospaceRuntime?.setPlasmaSheetEnabled(visible);
      this.applyGeospaceLayerVisibility();
    }
  }

  setSolarWindConditions(speedKps: number | null, densityCm3: number | null = null) {
    this.solarWindDataAvailable = speedKps !== null && densityCm3 !== null;
    this.solarWindGroup.visible = this.solarWindLayerEnabled && this.solarWindDataAvailable;
    this.solarWindVisual.setConditions(speedKps, densityCm3);
    this.applyGeospaceLayerVisibility();
  }

  /**
   * Which solar-wind presentation is on screen right now: the published
   * BATS-R-US flow field, or the idealised no-penetration fallback that
   * stands in before the geospace bundle loads. Different evidence classes,
   * so the legend has to be able to ask.
   */
  getSolarWindMode(): SolarWindVisualMode {
    return this.solarWindVisual.mode;
  }

  setPhotonFlux(fluxWm2: number | null) {
    this.photonDataAvailable = fluxWm2 !== null;
    this.photonGroup.visible = this.photonLayerEnabled && this.photonDataAvailable;
    this.xrayVisual.setFlux(fluxWm2);
    this.dRegionEmpirical.setXrayFlux(fluxWm2);
    // The volume's empirical D band responds to the same measured irradiance,
    // which is what makes a flare visibly thicken and lower it.
    this.ionospherePhotonFluxWm2 = fluxWm2;
    this.ionosphereDensityVolume?.setXrayFlux(fluxWm2);
  }

  setRenderingOptions(options: {
    pixelRatioCap: number;
    maximumFrameRate: number;
    stars: boolean;
    environmentalMotion: boolean;
    satelliteLabels: boolean;
    satellitePointSize?: number;
  }) {
    this.rendererPixelRatioCap = THREE.MathUtils.clamp(options.pixelRatioCap, 0.75, 2);
    this.maximumFrameRate = THREE.MathUtils.clamp(options.maximumFrameRate, 15, 120);
    this.starField.visible = options.stars;
    this.environmentalMotionEnabled = options.environmentalMotion;
    this.satelliteLabelsEnabled = options.satelliteLabels;
    this.satelliteMaterial.uniforms.pointSize!.value = THREE.MathUtils.clamp(options.satellitePointSize ?? 3.4, 2.5, 5.5);
    if (!options.satelliteLabels) {
      this.hoverIndex = null;
      this.hoverLabel.classList.remove("is-visible");
      this.selectedLabel.classList.remove("is-visible");
    } else if (this.selectedIndex !== null) {
      this.setSatelliteLabel(this.selectedLabel, this.selectedIndex);
      this.positionSatelliteLabel(this.selectedLabel, this.selectedIndex);
    }
    this.resize();
    this.ionosphereVolume?.setRendering(
      this.renderer.getPixelRatio(),
      this.rendererPixelRatioCap <= 1 ? 0.8 : 1,
    );
  }

  setSimulationTime(date: Date) {
    this.simulationTime = new Date(date);
    this.ionosphereVolume?.setSimulationTime(date);
    this.ionosphereDensityVolume?.setSimulationTime(date);
    this.dRegionEmpirical.setSimulationTime(date);
    this.drapSurface?.setSimulationTime(date);
    this.auroraHistorySurface?.setSimulationTime(date);
    this.groundField?.setSimulationTime(date);
    this.updateGeospaceForSimulationTime();
    this.sunDirection.copy(sceneSunDirection(date, this.referenceFrame));
    this.applyReferenceFrameTransforms();
    // Full GSM frame, not just sun-pointing: the roll about the Sun line is
    // fixed by the live dipole axis, so the field lines, cusp funnels and MHD
    // cuts authored in GSM ring the same magnetic pole the aurora texture
    // rings. See gsmFrameQuaternion for the registration bug this closes.
    this.sunFrameGroup.quaternion.copy(
      gsmFrameQuaternion(this.sunDirection, sceneDipoleAxisDirection(date, this.referenceFrame)),
    );
    this.sunLight.position.copy(this.sunDirection).multiplyScalar(1_000);
  }

  setReferenceFrame(frame: ReferenceFrame) {
    this.referenceFrame = frame;
    this.setSimulationTime(this.simulationTime);
  }

  private applyReferenceFrameTransforms() {
    const earthRotation = this.referenceFrame === "inertial"
      ? greenwichSiderealAngle(this.simulationTime)
      : 0;
    this.earthFixedGroup.rotation.y = earthRotation;
    this.satelliteFrameGroup.rotation.y = earthRotation;
    this.selectionEarthGroup.rotation.y = earthRotation;
    this.selectionFootprintGroup.rotation.y = earthRotation;
    this.selectionOrbitGroup.rotation.y = this.referenceFrame === "inertial"
      ? this.selectedOrbitFrameRotationY
      : 0;
  }

  updateTec(points: TecPoint[], range: [number, number]) {
    this.tecPoints = points;
    this.tecRange = range;
    const canvas = document.createElement("canvas");
    canvas.width = this.fieldRendering === "smooth" ? 144 : 720;
    canvas.height = this.fieldRendering === "smooth" ? 72 : 360;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    const [minimum, maximum] = range;
    points.forEach((point) => {
      if (point.tec === null) return;
      const value = Math.max(0, Math.min(1, (point.tec - minimum) / Math.max(1, maximum - minimum)));
      const hue = 260 - value * 230;
      const alpha = glotecQualityOpacity(point.quality);
      context.fillStyle = `hsla(${hue}, 92%, 58%, ${alpha})`;
      const x = longitudeTextureX(point.lon, canvas.width);
      const y = ((90 - point.lat) / 180) * canvas.height;
      const cellWidth = this.fieldRendering === "smooth" ? 2.2 : 11;
      const cellHeight = this.fieldRendering === "smooth" ? 1.2 : 6;
      context.fillRect(x - cellWidth / 2, y - cellHeight / 2, cellWidth, cellHeight);
    });
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = this.fieldRendering === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.magFilter = this.fieldRendering === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.wrapS = THREE.RepeatWrapping;
    texture.generateMipmaps = false;
    const material = this.ionosphere.material as THREE.MeshBasicMaterial;
    material.map?.dispose();
    material.map = texture;
    material.color.set(0xffffff);
    material.needsUpdate = true;
  }

  updateAurora(points: AuroraPoint[]) {
    this.auroraPoints = points;
    const canvas = document.createElement("canvas");
    canvas.width = this.fieldRendering === "smooth" ? 360 : 720;
    canvas.height = this.fieldRendering === "smooth" ? 180 : 360;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    points.forEach((point) => {
      if (this.auroraHemisphere === "north" && point.lat < 0) return;
      if (this.auroraHemisphere === "south" && point.lat > 0) return;
      const probability = THREE.MathUtils.clamp(point.probability / 100, 0, 1);
      const hue = 120 - probability * 120;
      const alpha = Math.min(0.92, 0.08 + probability * 1.8);
      context.fillStyle = `hsla(${hue}, 100%, 58%, ${alpha})`;
      const x = longitudeTextureX(point.lon, canvas.width);
      const y = ((90 - point.lat) / 180) * canvas.height;
      const cell = this.fieldRendering === "smooth" ? 1.35 : 2.8;
      context.fillRect(x - cell / 2, y - cell / 2, cell, cell);
    });
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = this.fieldRendering === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.magFilter = this.fieldRendering === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.wrapS = THREE.RepeatWrapping;
    texture.generateMipmaps = false;
    const material = this.aurora.material as THREE.MeshBasicMaterial;
    material.map?.dispose();
    material.map = texture;
    material.color.set(0xffffff);
    material.needsUpdate = true;
  }

  setAuroraHemisphere(hemisphere: "both" | "north" | "south") {
    this.auroraHemisphere = hemisphere;
    // The exact history artifact is one official global grid containing both
    // hemispheres. Do not mask it into the old latest-frame teaching filter.
    if (this.auroraHistorySurface) return;
    this.updateAurora(this.auroraPoints);
  }

  setFieldRendering(mode: FieldRendering) {
    this.fieldRendering = mode;
    this.ionosphereVolume?.setSpatialMode(mode);
    this.drapSurface?.setDisplayMode(mode);
    this.auroraHistorySurface?.setDisplayMode(mode);
    this.groundField?.setDisplayMode(mode);
    if (this.tecPoints.length) this.updateTec(this.tecPoints, this.tecRange);
    if (this.auroraPoints.length) this.updateAurora(this.auroraPoints);
    this.geospaceRuntime?.setDisplayMode(mode);
    this.applyGeospaceLayerVisibility();
  }

  setDrapModel(bundle: DrapBundle): EnvironmentSurfaceState {
    this.drapSurface?.dispose();
    const layer = new DrapSurfaceLayerController(bundle, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      enabled: this.drapLayerEnabled,
      maxAnisotropy: this.renderer.capabilities.getMaxAnisotropy(),
    });
    layer.setDisplayMode(this.fieldRendering);
    layer.setSimulationTime(this.simulationTime);
    this.drapSurface = layer;
    this.earthFixedGroup.add(layer.mesh);
    return layer.state;
  }

  setAuroraHistoryModel(bundle: AuroraBundle): EnvironmentSurfaceState {
    this.auroraHistorySurface?.dispose();
    const layer = new AuroraSurfaceLayerController(bundle, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      enabled: this.auroraLayerEnabled,
      maxAnisotropy: this.renderer.capabilities.getMaxAnisotropy(),
    });
    layer.setDisplayMode(this.fieldRendering);
    layer.setSimulationTime(this.simulationTime);
    this.auroraHistorySurface = layer;
    this.earthFixedGroup.add(layer.mesh);
    // Never composite the current-frame fallback over exact history/no-data.
    this.aurora.visible = false;
    return layer.state;
  }

  /**
   * Mount the ground magnetic perturbation overlay.
   *
   * Earth-fixed, like the coastlines and the D-RAP shell, because this grid is
   * geographic. Putting it on the Sun-fixed group with the GSM cut planes would
   * spin it against the map.
   */
  /**
   * Install one decoded neutral-density frame and rebuild the surface.
   *
   * Earth-fixed, because NOAA publishes this field on a geographic grid:
   * the bulge sits over the heated hemisphere and must turn with the map,
   * not with the Sun-Earth line.
   */
  setThermosphereFrame(frame: DecodedFrame) {
    if (!this.thermosphere) {
      this.thermosphere = new ThermosphereVolumeLayer(EARTH_SCENE_RADIUS);
      this.earthFixedGroup.add(this.thermosphere.object3d());
    }
    this.thermosphere.setEnabled(this.thermosphereEnabled);
    return this.thermosphere.setFrame(frame);
  }

  /**
   * Draw no neutral air at all, because no published frame covers the clock.
   *
   * The layer object is kept so the reader's on/off choice and the level they
   * chose survive the gap; what goes is the mesh and every number derived from
   * a frame, so nothing downstream can quote an hour that is not being drawn.
   */
  clearThermosphereFrame() {
    this.thermosphere?.clear();
  }

  /** Which density level the surface follows, kg m^-3. */
  setThermosphereLevel(level: number) {
    this.thermosphere?.setLevel(level);
    return this.thermosphere?.lastSurface() ?? null;
  }

  /** The surface most recently built, for the legend's range. */
  thermosphereSurface() {
    return this.thermosphere?.lastSurface() ?? null;
  }

  setGroundFieldModel(bundle: GroundFieldBundle): GroundFieldState {
    this.groundField?.dispose();
    const layer = new GroundPerturbationLayer(bundle, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      enabled: this.groundFieldLayerEnabled,
      system: this.groundFieldSystem,
    });
    layer.setDisplayMode(this.fieldRendering);
    layer.setSimulationTime(this.simulationTime);
    this.groundField = layer;
    this.groundFieldBundle = bundle;
    this.earthFixedGroup.add(layer.mesh);
    return layer.state;
  }

  /**
   * Attach an Earth-fixed overlay built elsewhere, so it turns with the map.
   *
   * The ground-station pins are the first caller. They deliberately do not get
   * their own transform in here: `src/ground-stations.ts` imports
   * `geoToSceneVector` from this file, because a second copy of that arithmetic
   * is a second place for the quarter-turn registration bug to come back.
   */
  addEarthFixedOverlay(group: THREE.Group) {
    this.earthFixedGroup.add(group);
  }

  removeEarthFixedOverlay(group: THREE.Group) {
    this.earthFixedGroup.remove(group);
  }

  /**
   * Screen-space pick against an overlay this globe hosts but does not own.
   *
   * The canvas rectangle and the live camera are private and must stay that
   * way — a caller that measured the canvas itself would be a second source of
   * truth for the viewport, and this scene resizes. So the caller passes its
   * own picking function in and this supplies the frame to run it against.
   */
  pickOverlay<T>(
    clientX: number,
    clientY: number,
    pick: (x: number, y: number, camera: THREE.Camera, width: number, height: number) => T | null,
  ): T | null {
    const rect = this.renderer.domElement.getBoundingClientRect();
    return pick(clientX - rect.left, clientY - rect.top, this.camera, rect.width, rect.height);
  }

  /**
   * Where on Earth a click landed, or null if it missed the globe entirely.
   *
   * Ray against the Earth sphere, then `worldToLocal` through the earth-fixed
   * group before converting. That second step is the whole subtlety: in the
   * inertial frame that group carries the Greenwich sidereal rotation, so the
   * same pixel is a different meridian at a different simulation time. Undoing
   * the rotation is what makes a click report the place the visitor is looking
   * at in BOTH reference frames rather than only in earth-fixed.
   *
   * The near intersection is the one taken, so a click always names the
   * hemisphere facing the camera rather than the far side of the sphere.
   */
  /**
   * Arm or disarm the explicit "click a place" mode.
   *
   * The cursor changes and spacecraft stop taking the click. Default off, and
   * with it off nothing in the pointer path behaves any differently than it
   * did before this existed.
   */
  setPointPickMode(enabled: boolean) {
    if (enabled === this.pointPickModeValue) return;
    this.pointPickModeValue = enabled;
    this.container.classList.toggle("is-point-picking", enabled);
    // A hover label naming a spacecraft, while the mode says spacecraft are
    // not what this click is for, is a contradiction on screen.
    if (enabled) {
      this.hoverIndex = null;
      this.hoverLabel.classList.remove("is-visible");
    }
  }

  get pointPickMode(): boolean {
    return this.pointPickModeValue;
  }

  /**
   * Mark the place the probe is answering about, or clear it with null.
   *
   * The marker tracks THE PROBE POINT, not the pick mode. Those come apart the
   * moment a reader picks a point and then presses Escape to stop picking: the
   * panel is still open and still answering about that place, so a marker that
   * vanished on cancel would leave the sphere and the panel disagreeing, which
   * is the same half-feature this exists to close. It clears when the probe
   * closes, and a new pick moves it rather than adding a second one.
   *
   * One sprite for the page's lifetime. Nothing is allocated per pick, so there
   * is no texture to dispose and no way for repeated picking to leak.
   */
  setProbePoint(point: { latitudeDeg: number; longitudeDeg: number } | null) {
    if (!point) {
      this.probePointVisible = false;
      this.probePointMarker.visible = false;
      return;
    }
    // Just clear of the surface: coplanar with the sphere it would z-fight with
    // the very ground it is naming.
    this.probePointMarker.position.copy(
      geoToSceneVector(point.latitudeDeg, point.longitudeDeg, EARTH_SCENE_RADIUS * 1.004),
    );
    this.probePointVisible = true;
    this.updateProbePointFacing();
  }

  pickGeographicPoint(clientX: number, clientY: number): { latitudeDeg: number; longitudeDeg: number } | null {
    const rect = this.renderer.domElement.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    if (x < 0 || x > rect.width || y < 0 || y > rect.height) return null;
    this.camera.updateMatrixWorld();
    this.geoPickRaycaster.setFromCamera(
      new THREE.Vector2((x / rect.width) * 2 - 1, -(y / rect.height) * 2 + 1),
      this.camera,
    );
    const hit = this.geoPickRaycaster.ray.intersectSphere(
      new THREE.Sphere(new THREE.Vector3(0, 0, 0), EARTH_SCENE_RADIUS),
      new THREE.Vector3(),
    );
    if (!hit) return null;
    // The earth-fixed group carries the sidereal rotation in the inertial
    // frame, and `worldToLocal` reads its world matrix — which the render loop
    // refreshes per frame. Refreshing it here too means a click is answered
    // against the rotation it was actually aimed at, not the previous frame's.
    this.earthFixedGroup.updateMatrixWorld();
    return sceneVectorToGeo(this.earthFixedGroup.worldToLocal(hit));
  }

  setGroundFieldSystem(system: GroundCurrentSystemKey): GroundFieldState | null {
    this.groundFieldSystem = system;
    return this.groundField?.setCurrentSystem(system) ?? null;
  }

  getGroundFieldState(): GroundFieldState | null {
    return this.groundField?.state ?? null;
  }

  /** Every component of every current system under a point, or null. */
  sampleGroundField(latitudeDeg: number, longitudeDeg: number): GroundFieldSample | null {
    const layer = this.groundField;
    const frame = layer?.frame;
    if (!layer || !frame || layer.state.status !== "ready") return null;
    return sampleGroundPerturbation(this.groundFieldBundle!, frame, latitudeDeg, longitudeDeg);
  }

  getDrapSurfaceState(): EnvironmentSurfaceState | null {
    return this.drapSurface?.state ?? null;
  }

  getAuroraHistoryState(): EnvironmentSurfaceState | null {
    return this.auroraHistorySurface?.state ?? null;
  }

  getIonosphereSurfaceState(): IonosphereSurfaceState | null {
    return this.ionosphereVolume?.getSurfaceState() ?? null;
  }

  getDRegionSurfaceState(): DRegionSurfaceState {
    return this.dRegionEmpirical.getState();
  }

  setIonosphereModel(bundle: IonosphereVolumeBundle) {
    this.ionosphereBundle = bundle;
    if (this.ionosphereVolume) {
      this.earthFixedGroup.remove(this.ionosphereVolume.points);
      this.ionosphereVolume.dispose();
    }
    const layer = new IonosphereVolumeLayer(bundle, {
      earthSceneRadius: EARTH_SCENE_RADIUS,
      pixelRatio: this.renderer.getPixelRatio(),
      spatialMode: this.fieldRendering,
    });
    layer.points.visible = this.ionosphereVolumeEnabled && this.ionosphereVolumeDataAvailable;
    layer.setSimulationTime(this.simulationTime);
    this.ionosphereVolume = layer;
    // The three peak surfaces are NOT added to the scene any more. Retiring
    // them is the same move the thermosphere made with its isopycnic shell,
    // and for a sharper reason here: they were drawn on a private radius curve
    // (18*log1p(alt/350) against the shared ruler's 28*log1p) with an 8x
    // height exaggeration layered on top, so a satellite drawn at the F2 peak
    // altitude appeared 7.7 scene units ABOVE the F2 peak surface -- exactly
    // the mixed-scale lie the shared ruler exists to prevent. On top of that
    // they carried heavy isohypse contour lines that read as a topographic map
    // laid over the sky, and once the density volume is drawn they sit in
    // front of the very shell they were standing in for.
    //
    // What they uniquely knew is kept: the layer object stays alive, because
    // its getSurfaceState() reports the share of columns where the published
    // peak criterion actually resolves a distinct E or F1 maximum, and that
    // percentage is on the card. "A separate E layer is resolvable over 41% of
    // the globe right now" is the fact the holes in those surfaces were
    // gesturing at, and it is legible as a number and illegible as geometry.
    layer.points.visible = false;

    // Parented to the Earth-fixed group on purpose: the field is GEOGRAPHIC,
    // so the volume's local coordinates are geographic and its shader needs no
    // frame conversion at all.
    if (this.ionosphereDensityVolume) {
      this.earthFixedGroup.remove(this.ionosphereDensityVolume.object3d());
      this.ionosphereDensityVolume.dispose();
    }
    const density = new IonosphereDensityVolumeLayer(bundle, EARTH_SCENE_RADIUS);
    density.setXrayFlux(this.ionospherePhotonFluxWm2);
    density.setSimulationTime(this.simulationTime);
    density.setEnabled(this.ionosphereVolumeEnabled && this.ionosphereVolumeDataAvailable);
    this.ionosphereDensityVolume = density;
    this.earthFixedGroup.add(density.object3d());
    this.dRegionEmpirical.mesh.visible = false;
  }

  /** What the last bake measured, for the card to quote without re-deriving it. */
  getIonosphereVolumeBake(): IonosphereVolumeBake | null {
    return this.ionosphereDensityVolume?.lastBake() ?? null;
  }

  /**
   * Draw exactly these named regions of the ionosphere.
   *
   * Replaces the contiguous altitude window this used to expose. The density
   * volume is the only surface that can show a band in isolation, so it is the
   * only one that has to be told; the retired peak surfaces are not in the
   * scene and there is nothing there to clip.
   */
  setIonosphereRegionsEnabled(enabled: Record<IonosphereRegionId, boolean>) {
    this.ionosphereDensityVolume?.setRegionsEnabled(enabled);
  }

  setIonosphereDataAvailable(available: boolean) {
    this.ionosphereVolumeDataAvailable = available;
    this.applyAirglowVisibility();
    if (this.ionosphereVolume) this.ionosphereVolume.points.visible = false;
    this.ionosphereDensityVolume?.setEnabled(this.ionosphereVolumeEnabled && available);
  }

  /**
   * Rebuild the boundary layer from one propagated solar-wind sample.
   *
   * It takes the whole sample rather than the two Shue parameters because the
   * cusped surfaces need the rest of it: the IMF `By` for the clock angle and
   * `Bt` for the upstream magnetic pressure, on top of the pressure and `Bz`
   * Shue already used. Passing a driver instead of a pair of numbers is also
   * what keeps `populateMagnetosphere` from having to invent anything.
   */
  setMagnetopause(driver: MagnetopauseDriverSample | null) {
    const standoffRe = driver?.subsolarStandoffRe ?? null;
    this.magnetosphereDataAvailable = driver !== null
      && Number.isFinite(driver.subsolarStandoffRe) && driver.subsolarStandoffRe > 0
      && Number.isFinite(driver.flaringAlpha) && driver.flaringAlpha > 0
      && Number.isFinite(driver.dynamicPressureNpa) && driver.dynamicPressureNpa > 0
      && Number.isFinite(driver.bzGsmNt);
    this.magnetosphere.visible = this.magnetosphereLayerEnabled && this.magnetosphereDataAvailable;
    this.solarWindVisual.setMagnetopauseStandoffRe(standoffRe);
    this.lastMagnetopauseDriver = this.magnetosphereDataAvailable ? driver : null;
    if (!this.magnetosphereDataAvailable) {
      this.magnetopauseLegendEntries = [];
      this.magnetopauseFallbackReason = null;
      this.solarWindVisual.setBoundaryRadiusForDirection(null);
      this.solarWindVisual.setBoundaryDrawnElsewhere(false);
      this.cuspEntryTracks = [];
      this.cuspEntryPoints = null;
      this.disposeGroup(this.magnetosphere);
      this.disposeGroup(this.cuspEntryGroup);
      this.cuspEntryGroup.visible = false;
      // The field lines are driven by the same sample; without it they go
      // too, the same way every layer here disappears rather than freezes.
      this.clearFieldLines();
      return;
    }
    this.magnetopauseStandoffRe = driver!.subsolarStandoffRe;
    this.populateMagnetosphere(this.magnetosphere, driver!);
    this.populateFieldLines(driver!);
  }

  /**
   * The equatorial electron-density field for the selected instant, from
   * whichever model can answer for it — the published DGCPM simulation where
   * its frames reach, the Carpenter & Anderson empirical profile elsewhere —
   * or null when neither can. All the physics, the geometry and the colour
   * ramp live in `src/inner-magnetosphere.ts`; this method only adds and
   * removes what it is handed, so a missing record removes the field the same
   * way every other layer disappears rather than freezes.
   *
   * The rebuild guard compares `rebuildKey`, which is the identity of what
   * would be drawn rather than the instant it was asked for: switching from
   * the simulation to the fallback, or stepping to the next published frame,
   * rebuilds the stipple, while scrubbing across an hour that does not move
   * either model's parameters does not.
   */
  setPlasmasphere(field: PlasmasphereLayerField | null) {
    const previous = this.plasmasphereFieldState;
    const unchanged = field !== null && previous !== null
      && field.source === previous.source
      && field.rebuildKey === previous.rebuildKey;
    this.plasmasphereFieldState = field;
    if (unchanged) return;
    this.disposeGroup(this.plasmasphereGroup);
    this.plasmasphereObject = null;
    if (field) {
      const points = createPlasmasphereFieldObject(field, {
        positionForGsm: (xRe, yRe, zRe) => this.modelRadiationPosition(xRe, yRe, zRe),
      });
      // A rebuilt stipple picks the corotation angle back up on the next
      // rendered frame, from the same accumulated display clock, so stepping
      // to the next published frame does not snap the grains back to noon.
      setPlasmasphereDisplayTime(points, this.environmentalAnimationElapsedSeconds);
      this.plasmasphereObject = points;
      this.plasmasphereGroup.add(points);
    }
    this.plasmasphereGroup.visible = this.plasmasphereLayerEnabled && field !== null;
  }

  getPlasmasphereField(): PlasmasphereLayerField | null {
    return this.plasmasphereFieldState;
  }

  /**
   * The ring-current illustration for the selected instant, or null when the
   * published DGCPM frame that supplies its convection field does not reach it.
   *
   * Null is a real answer here and is drawn as absence, exactly as every other
   * layer's missing frame is: the drift paths are computed IN the plasmasphere
   * simulation's own electric field, so with no frame there is no field, and an
   * illustration drawn in an invented field would be the one thing this layer
   * must never be. The card says which of those it is.
   *
   * Guarded on `rebuildKey`, which is the identity of what would be drawn —
   * the frame, the charge sign and the reference energy — so scrubbing inside
   * one published frame costs nothing while stepping to the next rebuilds.
   */
  setRingCurrent(state: RingCurrentIllustration | null) {
    const previous = this.ringCurrentState;
    const unchanged = state !== null && previous !== null && state.rebuildKey === previous.rebuildKey;
    this.ringCurrentState = state;
    if (unchanged) return;
    this.disposeGroup(this.ringCurrentGroup);
    this.ringCurrentObject = null;
    this.ringCurrentFormationState = null;
    if (state) {
      const group = createRingCurrentObject(state, {
        positionForGsm: (xRe, yRe, zRe) => this.modelRadiationPosition(xRe, yRe, zRe),
        earthSceneRadius: EARTH_SCENE_RADIUS,
      });
      // Pick the formation phase back up from the same accumulated display
      // clock, so stepping to the next published frame does not snap the ring
      // back to empty. The whole group is handed over rather than one child:
      // what moves is the volume filling, not a marker cloud over it.
      setRingCurrentDisplayTime(group, this.environmentalAnimationElapsedSeconds);
      this.ringCurrentObject = group;
      this.ringCurrentFormationState = (group.userData.formationState as RingCurrentFormation | null) ?? null;
      this.ringCurrentGroup.add(group);
    }
    this.ringCurrentGroup.visible = this.ringCurrentLayerEnabled && state !== null;
  }

  getRingCurrentState(): RingCurrentIllustration | null {
    return this.ringCurrentState;
  }

  /**
   * The loop the ring current is drawing right now, for the surfaces that have
   * to quote its period. Read off the drawn object rather than recomputed:
   * `ringCurrentFormation` costs forty-odd RK4 traces, and a second copy of it
   * could quote a period the scene is not keeping.
   */
  getRingCurrentFormation(): RingCurrentFormation | null {
    return this.ringCurrentFormationState;
  }

  /**
   * The legend element whose `--legend-pulse` follows the ring current's loop.
   *
   * Re-registered by the explorer whenever the key cards are rebuilt, because
   * a rebuild replaces the node. Handed null when the ring current has no card
   * on screen.
   */
  setRingCurrentPulseSurface(element: HTMLElement | null) {
    if (this.ringCurrentPulseSurface === element) return;
    // The outgoing bar goes back to full rather than keeping whatever level it
    // was on when it left: a detached node cannot be updated again, and a
    // reattached one would come back frozen mid-breath.
    paintRingCurrentPulse(this.ringCurrentPulseSurface, null, 0);
    this.ringCurrentPulseSurface = element;
  }

  /**
   * What is actually drawn in the boundary layer right now, with its citations.
   *
   * Built from the evaluated models rather than written as prose, so the legend
   * cannot drift away from the geometry: if a surface fails to evaluate it
   * leaves the scene and the legend in the same call.
   */
  getMagnetopauseLegend(): MagnetopauseLegendEntry[] {
    return this.magnetopauseLegendEntries;
  }

  /** Why only Shue is drawn, when only Shue is drawn. `null` otherwise. */
  getMagnetopauseFallbackReason(): string | null {
    return this.magnetopauseFallbackReason;
  }

  /**
   * The obvious way back. It re-frames for whatever layers are on right now,
   * so it is also the escape hatch from any manual zoom.
   */
  resetView() {
    this.camera.up.set(0, 1, 0);
    this.frameActiveLayers({ force: true });
  }

  /**
   * How far back the camera must sit to fit a sphere of this scene radius.
   *
   * Framing is computed rather than hard-coded because the scene's radial
   * ruler decides how large every model layer is; a distance tuned by hand
   * silently stops framing the thing it was chosen for the moment that
   * changes.
   */
  private distanceToFrame(sceneRadius: number) {
    return THREE.MathUtils.clamp(
      distanceToFrameSceneRadius(sceneRadius, this.camera.fov, this.camera.aspect),
      this.controls.minDistance,
      this.controls.maxDistance,
    );
  }

  /**
   * The scene radius that has to fit inside the frame for everything currently
   * drawn to be visible, measured from the geometry itself rather than from a
   * table of per-layer numbers. Several layers can be on at once, so this is
   * the union of what they need; because they all sit on one radial ruler the
   * union is just a maximum.
   */
  sceneRadiusForActiveLayers(): number {
    this.scene.updateMatrixWorld(true);
    let radius = DEFAULT_VIEW_SCENE_RADIUS;
    const reach = (object: THREE.Object3D | null | undefined, enabled: boolean) => {
      if (!enabled || !object) return;
      radius = Math.max(radius, boundingRadiusFromOrigin(new THREE.Box3().setFromObject(object)));
    };
    if (this.magnetosphereLayerEnabled && this.magnetosphereDataAvailable) {
      reach(this.magnetosphere, true);
      // Floor: the dayside standoff must be inside the frame even in the frame
      // or two before the boundary mesh has been rebuilt for new drivers.
      radius = Math.max(radius, this.magnetosphereDisplayRadius(this.magnetopauseStandoffRe));
    }
    reach(this.solarWindGroup, this.solarWindLayerEnabled && this.solarWindDataAvailable);
    // The X-ray layer is framed on its tint, not on its beam. The inbound rays
    // enter at 34 Re; fitting their whole length would shrink Earth to a speck
    // for a layer whose subject is what happens AT Earth. Frame out to
    // geostationary orbit instead — enough approach to read the rays as
    // arriving — and let them enter from off-frame, the way the field lines'
    // far tail is deliberately cropped.
    if (this.photonLayerEnabled && this.photonDataAvailable) {
      reach(this.xrayVisual.glow, true);
      radius = Math.max(radius, this.magnetosphereDisplayRadius(RADIAL_RULER.anchorRe));
    }
    reach(this.plasmasphereGroup, this.plasmasphereGroup.visible);
    reach(this.ringCurrentGroup, this.ringCurrentGroup.visible);
    // The 3-D field lines run down the tail to -40 Re, and fitting that whole
    // reach would shrink the Earth to a dot. Frame the boundary system —
    // dayside, cusps and near tail — and let the far tail run off frame, the
    // way every reference depiction crops it.
    if (this.fieldLineGroup.visible) {
      radius = Math.max(radius, this.magnetosphereDisplayRadius(Math.max(20, this.magnetopauseStandoffRe * 1.9)));
    }
    if (this.radiationLayerEnabled || this.geospaceLayerEnabled) {
      // Eight Earth radii clears the outer electron belt on the shared ruler.
      radius = Math.max(radius, radiationBeltDisplayRadius(8, EARTH_SCENE_RADIUS));
    }
    // The plasma-field cut planes reach the model's own crop — the -55 Re
    // corner draws near 740 scene units — and a field the camera has cropped
    // teaches nothing. Measured from the geometry, so the frame follows
    // whatever the published bounds actually are.
    if (this.geospaceLayerEnabled && this.geospaceRuntime) {
      reach(this.geospaceRuntime.cutGroup, this.geospaceRuntime.cutGroup.visible);
    }
    // A bow shock the camera has cropped is no more findable than one drawn at
    // 0.13 opacity, so the named regions have to pull the framing out too.
    if (this.geospaceRuntime && this.structureRegions.size > 0) {
      reach(this.geospaceRuntime.boundaryGroup, this.geospaceRuntime.boundaryGroup.visible);
      reach(this.geospaceRuntime.streamlineGroup, this.geospaceRuntime.streamlineGroup.visible);
    }
    // AND THE SPACECRAFT. Every branch above measures a model layer, and the
    // satellites — the objects this site is named for — were not measured at
    // all: the floor was DEFAULT_VIEW_SCENE_RADIUS, which is a 600 km shell,
    // which is LEO. So the opening frame was sized for the LOWEST thing the
    // site draws and any fleet above it was drawn outside its own picture.
    // Live on 2026-08-26, the featured constellation was MUOS: five
    // spacecraft at 35,800 km, drawn at 230 scene units in a view framed for
    // 128, of which three were off screen entirely and two clipped the
    // corner. It is not a MUOS defect — GPS put 31 of its 40 outside the
    // frame on the same build — and it went unseen because the rotation had
    // been opening on Iridium, which is LEO, and Iridium fits.
    //
    // This is the same class as the forecast band recorded above: geometry
    // that was drawn while being invisible to the function that decides what
    // the camera must hold.
    radius = Math.max(radius, this.drawnSatelliteReach());
    return radius;
  }

  /**
   * How far the drawn spacecraft reach from Earth's centre, in scene units.
   *
   * Measured off the SAME position buffer the renderer draws from, so it
   * needs no table of altitudes per orbit class and cannot disagree with what
   * is on screen: a fleet that is drawn is framed, and a spacecraft filtered
   * out was zeroed by `setVisible` and contributes nothing. Vector lengths
   * rather than a `Box3` corner, because the frame is a sphere about the
   * origin and the box corner would over-frame a spread-out fleet by up to
   * 73%; the group these points hang from only ROTATES about the origin, so
   * a length read straight out of the buffer is already the world radius.
   *
   * ECCENTRIC FLEETS ARE FRAMED WHERE THEY ARE, not at their apogee. A
   * Molniya apogee draws at 241 units against a perigee at 128, and framing
   * the apogee of a fleet that is currently near perigee would open a picture
   * of an empty sky with a small Earth in it. Reading the drawn positions
   * gives the reader every spacecraft that exists on screen at the instant
   * they are looking, which is what all the satellites can be seen means;
   * as they climb, the frame does not chase them, because a camera that
   * breathed with the orbit would be its own defect. The moment the reader
   * SELECTS one of them, `focusSatellite` frames its whole drawn ellipse,
   * which is the case where apogee genuinely is the subject.
   *
   * The selected spacecraft's orbit line counts too, and for the same reason
   * the layers do: it is drawn, so cropping it teaches nothing. Without it,
   * switching any layer on after opening a Molniya orbit would dolly the
   * camera back in and cut the ellipse in half.
   */
  private drawnSatelliteReach(): number {
    let reach = 0;
    for (let index = 0; index < this.satelliteRenderable.length; index += 1) {
      if (this.satelliteRenderable[index] !== 1) continue;
      const length = Math.hypot(
        this.satellitePositions.getX(index),
        this.satellitePositions.getY(index),
        this.satellitePositions.getZ(index),
      );
      if (length > reach) reach = length;
    }
    if (this.selectionOrbitGroup.children.length > 0) reach = Math.max(reach, this.selectedOrbitDrawnReach);
    return reach;
  }

  /**
   * Make room for what is drawn, rather than sliding the scene sideways.
   *
   * The previous behaviour moved the orbit target off the origin to fit the
   * magnetotail, which pushed Earth to the right of the screen and left it
   * there for the rest of the session. Earth now always stays in the middle
   * and the camera dollies out instead.
   *
   * The rule for when to act: if what is drawn no longer fits, always pull
   * back, because otherwise switching a layer on shows nothing. If it would
   * fit more tightly than the current view — a layer was switched off — only
   * come back in when the visitor has not zoomed by hand since the last
   * automatic framing, so the view never fights them. The reset control forces
   * the framing either way.
   *
   * OPEN DEFECT, MEASURED 2026-08-27, NOT YET DIAGNOSED. This is documented
   * above and everywhere else as a pure DOLLY — it changes `distance` and
   * keeps the direction the reader is looking down — and the whole
   * camera-authority rule (`tests/camera-authority.test.ts`) rests on that
   * being true. It is not quite true. Driven off the real page, an untouched
   * camera holds its direction to 0.000 degrees over 40 seconds and settles
   * within half a second of a drag; but switching a layer on, which lands
   * here, moves the direction by 1.3, 2.0, 2.1, 4.4, 4.9 and 5.2 degrees
   * across six runs. Something in the re-seat below — `dollyTo` ->
   * `applyCameraFraming` -> `controls.update()` — is not preserving it.
   *
   * Small enough that no reader would call it the projection changing, and it
   * is NOT the defect 71b1437 removed (those moves were 24 to 110 degrees).
   * It is recorded here rather than only in commit d515fad because the next
   * agent to reason about who may move this camera will read this docstring
   * and would otherwise take "keeps the viewpoint" at its word.
   * `main.ts`'s `cameraTurnedByHand` sets its threshold clear of this on
   * purpose; shrink that threshold and you inherit this.
   */
  frameActiveLayers(options: { animate?: boolean; force?: boolean } = {}) {
    const wanted = this.distanceToFrame(this.sceneRadiusForActiveLayers());
    const reframe = shouldReframeView({
      wantedDistance: wanted,
      currentDistance: this.camera.position.distanceTo(this.controls.target),
      autoFrameDistance: this.autoFrameDistance,
      targetOffCentre: this.controls.target.lengthSq() > 1,
      force: options.force,
    });
    if (!reframe) return;
    this.dollyTo(wanted, options.animate !== false);
  }

  /**
   * WHERE THE CAMERA IS, as a reader-visible fact a test can read.
   *
   * The complaint this exists for is about camera AUTHORITY — "the projection
   * changes to polar ... it makes navigating really difficult" — and the whole
   * of the answer is a distinction between two moves. Widening keeps the
   * direction the reader is looking down and only changes `distance`; rotating
   * replaces `direction` and often `up`. Nothing else in the site reports
   * either, so a driven proof of "the layer did not take the wheel" had no
   * quantity to quote and would have been reduced to eyeballing two pictures.
   *
   * Read-only, and a plain snapshot rather than live objects, so nothing that
   * holds it can move the camera through it.
   */
  cameraPose() {
    const target = this.controls.target;
    const offset = this.camera.position.clone().sub(target);
    const distance = offset.length();
    // WHICH SIDE OF THE PAGE THE SUN IS ON, as a signed number.
    //
    // Sean, 2026-08-27: "when we pull up magnetosphere it should be oriented
    // so that the sun is on the left of the page, just like we had it
    // before." "Left" is not a property of any scene axis. `sunFrameGroup` is
    // rotated to the REAL Sun direction and turns through the day and the
    // year, so the only way to read it is to resolve the live sunward
    // direction against the camera's own screen-right axis. Screen-right is
    // built the way three.js builds it in `lookAt` — cross(up, back) — rather
    // than read off `matrixWorld`, so it is correct before the next render
    // rather than one frame late.
    //
    // Negative is LEFT, positive is RIGHT, and the magnitude says how far
    // from edge-on the Sun line sits: 1 is straight across the screen, 0 is
    // pointing at or away from the reader, where "left" means nothing.
    this.sunFrameGroup.updateMatrixWorld(true);
    const sunward = gsmSceneAxes(1, 0, 0).applyQuaternion(this.sunFrameGroup.quaternion).normalize();
    const back = distance > 1e-6 ? offset.clone().divideScalar(distance) : new THREE.Vector3(0, 0, 1);
    const screenRight = new THREE.Vector3().crossVectors(this.camera.up, back);
    if (screenRight.lengthSq() < 1e-9) screenRight.set(1, 0, 0);
    screenRight.normalize();
    return {
      distance,
      position: this.camera.position.toArray() as [number, number, number],
      target: target.toArray() as [number, number, number],
      direction: (distance > 1e-6 ? offset.clone().divideScalar(distance) : offset).toArray() as [number, number, number],
      up: this.camera.up.toArray() as [number, number, number],
      sunward: sunward.toArray() as [number, number, number],
      sunScreenX: screenRight.dot(sunward),
      sceneRadius: this.sceneRadiusForActiveLayers(),
    };
  }

  private dollyTo(distance: number, animate: boolean) {
    this.autoFrameDistance = distance;
    const reducedMotion = typeof window !== "undefined"
      && typeof window.matchMedia === "function"
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!animate || reducedMotion) {
      this.cameraDolly = null;
      this.applyCameraFraming(distance, new THREE.Vector3());
      return;
    }
    // A camera that jumps is disorienting. The scene's existing camera easing
    // is OrbitControls' damping, so this uses a comparably short, smoothly
    // decelerating move rather than inventing a longer cinematic one.
    this.cameraDolly = {
      fromDistance: this.camera.position.distanceTo(this.controls.target),
      toDistance: distance,
      fromTarget: this.controls.target.clone(),
      startedAt: performance.now(),
      durationMs: 520,
    };
  }

  private applyCameraFraming(distance: number, target: THREE.Vector3) {
    const direction = this.camera.position.clone().sub(this.controls.target);
    if (direction.lengthSq() < 1e-6) direction.set(0, 70, 330);
    this.controls.target.copy(target);
    this.camera.position.copy(target).add(direction.setLength(distance));
    this.controls.update();
  }

  private stepCameraDolly(now: number) {
    const dolly = this.cameraDolly;
    if (!dolly) return;
    const raw = Math.min(1, (now - dolly.startedAt) / dolly.durationMs);
    const eased = raw < 0.5 ? 2 * raw * raw : 1 - ((-2 * raw + 2) ** 2) / 2;
    const distance = THREE.MathUtils.lerp(dolly.fromDistance, dolly.toDistance, eased);
    const target = dolly.fromTarget.clone().multiplyScalar(1 - eased);
    this.applyCameraFraming(distance, target);
    if (raw >= 1) this.cameraDolly = null;
  }

  /**
   * Look along the Sun–Earth line. Earth stays centred and the view pulls back
   * far enough to hold the whole drawn boundary, nose to tail.
   *
   * This one puts the Sun on the RIGHT — `cameraPose().sunScreenX` is +0.985,
   * measured — and that is deliberate and left alone. It is the `#sun-earth-view`
   * button's own documented behaviour, and `energy-chain.ts` builds a
   * walkthrough step on it. The Sun-on-the-LEFT framing Sean asked for when
   * the magnetosphere is pulled up is `focusMagnetosphereObliqueView` below
   * (-0.758), which already had it; nothing here was flipped to get it.
   */
  focusSunEarthSideView() {
    const sunward = this.sunDirection.clone().normalize();
    const worldUp = new THREE.Vector3(0, 1, 0);
    let viewAxis = new THREE.Vector3().crossVectors(sunward, worldUp);
    if (viewAxis.lengthSq() < 1e-5) viewAxis = new THREE.Vector3(0, 0, 1);
    viewAxis.normalize();
    // The -50 Re Shue tail cutoff sits at a physical radius near 56 Re for
    // typical flaring; the ruler itself now carries the tail's reach, with no
    // separate stretch to account for.
    const tail = this.magnetosphereDisplayRadius(56);
    const distance = this.distanceToFrame(Math.max(tail, this.sceneRadiusForActiveLayers()));
    this.cameraDolly = null;
    this.camera.up.copy(worldUp);
    this.controls.target.set(0, 0, 0);
    this.camera.position.set(0, 0, 0).addScaledVector(viewAxis, distance).addScaledVector(worldUp, distance * 0.05);
    this.camera.position.setLength(distance);
    this.autoFrameDistance = distance;
    this.controls.update();
  }

  /**
   * The textbook view: looking straight down the dawn-dusk axis at the noon-
   * midnight meridian, Sun on the LEFT.
   *
   * "Sun to the right" until 2026-08-27, which was wrong, and wrong in the
   * one direction a reader would notice. Measured on the running page rather
   * than reasoned about: `cameraPose().sunScreenX` is -1.000 here — the Sun
   * line lies exactly across the screen and points LEFT. The camera sits on
   * GSM +y (dusk) with GSM +z up, and three.js builds screen-right as
   * cross(up, back) = cross(z_gsm, y_gsm) = -x_gsm, which is anti-sunward.
   * For the same reason the camera is on the scene MINUS-z axis when the
   * frame is unrotated, not the plus: `gsmSceneAxes(0, 1, 0)` is (0, 0, -1).
   *
   * Every cross-section a reader has ever seen of this system is drawn this
   * way, and there is a reason beyond convention: the layers here are nested
   * translucent shells, and from any oblique angle a shell reads as one blob
   * because you are looking through its near and far walls at once. Edge-on,
   * the same shells separate into the bands they are.
   */
  focusMeridionalCrossSection() {
    const distance = this.distanceToFrame(this.sceneRadiusForActiveLayers());
    // The GSM frame is rotated to the live Sun direction, so "look down the
    // dawn-dusk axis" is not a fixed scene axis: it is wherever GSM +y points
    // right now. Reading it off the same group the layers hang from is what
    // keeps this preset pointing at the meridian rather than at a stale one.
    this.sunFrameGroup.updateMatrixWorld(true);
    const gsmDawnDusk = gsmSceneAxes(0, 1, 0).applyQuaternion(this.sunFrameGroup.quaternion).normalize();
    const gsmNorth = gsmSceneAxes(0, 0, 1).applyQuaternion(this.sunFrameGroup.quaternion).normalize();
    this.cameraDolly = null;
    this.camera.position.copy(gsmDawnDusk).multiplyScalar(distance);
    this.camera.up.copy(gsmNorth);
    this.controls.target.set(0, 0, 0);
    this.autoFrameDistance = distance;
    this.controls.update();
  }

  /**
   * Straight down onto the north pole, noon at the top of the screen.
   *
   * This is the view in which the two cusp funnels, the auroral oval and the
   * dayside boundary share one frame: the funnels sit sunward of the pole,
   * the oval rings it, and the entry cue visibly connects the two. Up is the
   * live sunward direction read off the same rotated frame the layers hang
   * from, so noon stays at the top as the frame tracks the real Sun.
   */
  focusPolarView() {
    const distance = this.distanceToFrame(this.sceneRadiusForActiveLayers());
    this.sunFrameGroup.updateMatrixWorld(true);
    const gsmNorth = gsmSceneAxes(0, 0, 1).applyQuaternion(this.sunFrameGroup.quaternion).normalize();
    const gsmSunward = gsmSceneAxes(1, 0, 0).applyQuaternion(this.sunFrameGroup.quaternion).normalize();
    this.cameraDolly = null;
    this.camera.position.copy(gsmNorth).multiplyScalar(distance);
    this.camera.up.copy(gsmSunward);
    this.controls.target.set(0, 0, 0);
    this.autoFrameDistance = distance;
    this.controls.update();
  }

  /**
   * The belts three-quarters on: elevated enough that the outer torus reads
   * as a ring with the slot's gap inside it, low enough that the polar
   * funnels and the belts' vertical arch stay visible.
   *
   * The direction is fixed against the belts' own (GSM) axes, read off the
   * rotated frame the layers hang from, not against scene axes: a scene-fixed
   * direction lands anywhere between face-on and edge-on depending on season
   * and hour, and face-on is precisely the angle at which a torus stops
   * looking like one. Eight Earth radii of framing clears the outer belt on
   * the shared ruler while keeping the Earth a legible sphere at the centre
   * rather than a dot.
   */
  focusRadiationObliqueView() {
    const distance = this.distanceToFrame(Math.max(
      radiationBeltDisplayRadius(8, EARTH_SCENE_RADIUS),
      this.sceneRadiusForActiveLayers(),
    ));
    this.sunFrameGroup.updateMatrixWorld(true);
    const quaternion = this.sunFrameGroup.quaternion;
    const gsmSunward = gsmSceneAxes(1, 0, 0).applyQuaternion(quaternion).normalize();
    const gsmNorth = gsmSceneAxes(0, 0, 1).applyQuaternion(quaternion).normalize();
    const gsmDusk = gsmSceneAxes(0, 1, 0).applyQuaternion(quaternion).normalize();
    const direction = gsmSunward.multiplyScalar(0.8)
      .add(gsmDusk.multiplyScalar(0.6))
      .add(gsmNorth.clone().multiplyScalar(0.55))
      .normalize();
    this.cameraDolly = null;
    this.camera.position.copy(direction).multiplyScalar(distance);
    this.camera.up.copy(gsmNorth);
    this.controls.target.set(0, 0, 0);
    this.autoFrameDistance = distance;
    this.controls.update();
  }

  zoomBy(factor: number) {
    const offset = this.camera.position.clone().sub(this.controls.target);
    const distance = THREE.MathUtils.clamp(offset.length() * factor, this.controls.minDistance, this.controls.maxDistance);
    this.cameraDolly = null;
    this.camera.position.copy(this.controls.target).add(offset.setLength(distance));
    this.controls.update();
  }

  /**
   * Open the selected spacecraft's view where its whole orbit is visible.
   *
   * This used to frame the satellite's CURRENT altitude and nothing else —
   * `displayRadius(altitude) + 70` — which is the right rule only when the
   * orbit is a circle. Catch a Molniya near perigee and it is not: MERIDIAN 9
   * at 4,398 km altitude put the camera 243 scene units out while its own
   * apogee draws at 244, so the ellipse the visitor had just opened was
   * entirely off-frame, in every direction, with only a chord of it crossing
   * the picture. Framing the drawn line instead is measured off the geometry,
   * so it needs no per-regime table and is right at both ends of the range: a
   * LEO orbit reaches barely past the globe, so a low satellite still opens
   * close in, and CLUSTER II-FM7's 131,400 km apogee, the deepest in the
   * catalogue's HEO set, draws at 630 units and frames at 1,929 — inside the
   * 2,500 the controls allow, so no orbit in the catalogue frames off the
   * end of the dolly.
   */
  focusSatellite(index: number) {
    if (this.satelliteRenderable[index] !== 1) return;
    const direction = this.satelliteWorldPosition(index).normalize();
    const state = this.latestStates[index];
    const distance = Math.max(
      150,
      this.displayRadius(state?.altitudeKm ?? 0) + 70,
      this.selectedOrbitDrawnReach > 0 ? this.distanceToFrame(this.selectedOrbitDrawnReach) : 0,
    );
    // A dolly still in flight from a layer toggle would otherwise fight this.
    this.cameraDolly = null;
    this.camera.position.copy(direction.multiplyScalar(distance));
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  private line(points: THREE.Vector3[], color: number, opacity: number, dashed = false) {
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      dashed
        ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: 2.4, gapSize: 1.6, depthTest: true })
        : new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthTest: true }),
    );
    if (dashed) line.computeLineDistances();
    return line;
  }

  private buildFootprintFill(boundary: THREE.Vector3[]) {
    const cap = buildFootprintFillGeometry(boundary);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(cap.positions, 3));
    geometry.setAttribute("edgeAmount", new THREE.BufferAttribute(cap.edgeAmounts, 1));
    geometry.setIndex(cap.indices);
    return new THREE.Mesh(
      geometry,
      new THREE.ShaderMaterial({
        uniforms: { footprintColor: { value: new THREE.Color(0xf5c96a) } },
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false,
        vertexShader: `
          attribute float edgeAmount;
          varying float footprintEdgeAmount;
          void main() {
            footprintEdgeAmount = edgeAmount;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 footprintColor;
          varying float footprintEdgeAmount;
          void main() {
            float centerWeight = pow(1.0 - clamp(footprintEdgeAmount, 0.0, 1.0), 1.35);
            float opacity = mix(0.012, 0.20, centerWeight);
            gl_FragColor = vec4(footprintColor, opacity);
          }
        `,
      }),
    );
  }

  private disposeGroup(group: THREE.Group) {
    group.traverse((child) => {
      if (!(child instanceof THREE.Mesh || child instanceof THREE.Line || child instanceof THREE.Points)) return;
      child.geometry.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => material.dispose());
    });
    group.clear();
  }

  private geoToVector(latitudeDeg: number, longitudeDeg: number, radius: number) {
    return geoToSceneVector(latitudeDeg, longitudeDeg, radius);
  }

  private geoRadiansToVector(latitude: number, longitude: number, radius: number) {
    return geoRadiansToSceneVector(latitude, longitude, radius);
  }

  private displayRadius(altitudeKm: number) {
    return satelliteDisplayRadius(altitudeKm);
  }

  private altitudeFromDisplayRadius(radius: number) {
    return altitudeFromSatelliteDisplayRadius(radius);
  }

  private updateSelectedFootprintFromRenderedState(now: number) {
    if (!this.selectedFootprintVisible || this.selectedIndex === null || now - this.lastFootprintVisualAt < 50) return;
    const index = this.selectedIndex;
    if (this.satelliteRenderable[index] !== 1) return;
    const x = this.satellitePositions.getX(index);
    const y = this.satellitePositions.getY(index);
    const z = this.satellitePositions.getZ(index);
    const radius = Math.hypot(x, y, z);
    if (radius <= EARTH_SCENE_RADIUS) return;
    const latitudeDeg = Math.asin(THREE.MathUtils.clamp(y / radius, -1, 1)) * 180 / Math.PI;
    const longitudeDeg = Math.atan2(-z, x) * 180 / Math.PI;
    const boundary = footprintPoints(
      latitudeDeg,
      longitudeDeg,
      this.altitudeFromDisplayRadius(radius),
      this.footprintMinElevationDeg,
      96,
    ).map(([longitude, latitude]) => this.geoToVector(latitude, longitude, 100.9));
    this.disposeGroup(this.selectionFootprintGroup);
    if (boundary.length > 2) {
      this.selectionFootprintGroup.add(this.buildFootprintFill(boundary));
      this.selectionFootprintGroup.add(this.line(boundary, 0xf5c96a, 0.98));
    }
    this.lastFootprintVisualAt = now;
  }

  private applySatelliteInterpolation(amount: number) {
    this.visible.forEach((index) => {
      if (this.satelliteRenderable[index] !== 1) return;
      const offset = index * 3;
      this.satellitePositions.setXYZ(
        index,
        THREE.MathUtils.lerp(this.satelliteFrom[offset] ?? 0, this.satelliteTargets[offset] ?? 0, amount),
        THREE.MathUtils.lerp(this.satelliteFrom[offset + 1] ?? 0, this.satelliteTargets[offset + 1] ?? 0, amount),
        THREE.MathUtils.lerp(this.satelliteFrom[offset + 2] ?? 0, this.satelliteTargets[offset + 2] ?? 0, amount),
      );
    });
    this.satellitePositions.needsUpdate = true;
  }

  private animate = () => {
    if (this.disposed) return;
    const now = performance.now();
    const minimumFrameInterval = 1000 / this.maximumFrameRate;
    if (now - this.lastRenderedAt < minimumFrameInterval - 1) {
      this.animationFrame = requestAnimationFrame(this.animate);
      return;
    }
    this.lastRenderedAt = now;
    const delta = Math.min(0.1, (now - this.lastFrameTime) / 1000);
    this.lastFrameTime = now;
    this.stepCameraDolly(now);
    this.controls.update();
    // The solar wind's upstream face is cut to the FRAME, not to a fixed
    // number of Earth radii, so the front covers the whole left-hand side of
    // the page at every zoom and particles come in over the top and bottom
    // edges when the visitor pulls back. This hands over the drawn radius of
    // the frame's far corner at the target plane; the visual quantises it and
    // only re-cuts when it has moved enough to see. Outside the environmental
    // motion gate on purpose: the face has to follow the camera whether or not
    // the tracers are moving.
    if (this.solarWindGroup.visible) {
      this.solarWindVisual.setViewFaceRadius(this.viewCornerSceneRadius());
      // ...and how far away the camera is, which is the reference length the
      // wind's depth cues are measured against (SOLAR_WIND_DEPTH_CUE). Earth's
      // centre is the scene origin and `sunFrameGroup` only ever carries a
      // rotation, so the camera's distance from the origin IS its distance
      // from Earth in the tracers' own frame. Outside the environmental-motion
      // gate with the face, for the same reason: the picture has to follow the
      // camera whether or not the tracers are moving.
      this.solarWindVisual.setCameraDistance(this.camera.position.length());
    }
    if (this.environmentalMotionEnabled) {
      this.environmentalAnimationElapsedSeconds += delta;
      // Animation advances only visual tracer phase. Model/data frames remain
      // wholly controlled by setSimulationTime and the user's timeline.
      this.geospaceRuntime?.advanceAdvection(delta);
      // The plasmasphere's cold plasma corotates through its own sun-fixed
      // density field. This sits inside the environmental-motion gate with
      // every other flow glyph, so the grains freeze with them.
      if (this.plasmasphereObject) {
        setPlasmasphereDisplayTime(this.plasmasphereObject, this.environmentalAnimationElapsedSeconds);
      }
      // The ring current forms on the same clock — the tail supply arriving and
      // the trapped population closing westward — so it freezes with everything
      // else when a visitor switches environmental motion off.
      if (this.ringCurrentObject) {
        setRingCurrentDisplayTime(this.ringCurrentObject, this.environmentalAnimationElapsedSeconds);
      }
      this.solarWindVisual.update(this.environmentalAnimationElapsedSeconds);
      this.xrayVisual.update(this.environmentalAnimationElapsedSeconds);
      if (this.cuspEntryGroup.visible && this.cuspEntryPoints) this.updateCuspEntryCue(delta);
    }
    // The legend's colour bar, on the ring current's own loop clock. Outside
    // the motion gate on purpose: with motion off, or the layer off, the
    // formation handed over is null and the bar sits at full, which is how
    // every other layer's bar is drawn. Inside the gate it would instead
    // freeze wherever the last frame left it, dimmed.
    paintRingCurrentPulse(
      this.ringCurrentPulseSurface,
      this.environmentalMotionEnabled && this.ringCurrentGroup.visible ? this.ringCurrentFormationState : null,
      this.environmentalAnimationElapsedSeconds,
    );
    if (this.interpolationActive) {
      const amount = Math.min(1, (now - this.interpolationStartedAt) / this.interpolationDurationMs);
      this.applySatelliteInterpolation(amount);
      this.interpolationActive = amount < 1;
    }
    this.updateSelectedFootprintFromRenderedState(now);
    if (this.satelliteLabelsEnabled && (this.selectedIndex !== null || this.hoverIndex !== null)) {
      this.refreshLabelOcclusion(now);
    }
    this.updateProbePointFacing();
    if (this.selectedIndex !== null) {
      const index = this.selectedIndex;
      if (this.satelliteRenderable[index] === 1) {
        const pulse = 11.5 + Math.sin(now / 240) * 1.1;
        this.selectionMarker.position.set(
          this.satellitePositions.getX(index),
          this.satellitePositions.getY(index),
          this.satellitePositions.getZ(index),
        );
        this.selectionMarker.scale.set(pulse, pulse, 1);
        this.selectionMarker.visible = true;
        if (this.satelliteLabelsEnabled) this.positionSatelliteLabel(this.selectedLabel, index);
      }
    }
    if (this.satelliteLabelsEnabled && this.hoverIndex !== null) this.positionSatelliteLabel(this.hoverLabel, this.hoverIndex);
    this.renderer.render(this.scene, this.camera);
    this.animationFrame = requestAnimationFrame(this.animate);
  };

  destroy() {
    this.disposed = true;
    cancelAnimationFrame(this.animationFrame);
    if (this.hoverPickAnimationFrame !== 0) cancelAnimationFrame(this.hoverPickAnimationFrame);
    window.removeEventListener("resize", this.resize);
    if (this.ionosphereVolume) {
      this.earthFixedGroup.remove(this.ionosphereVolume.points);
      this.ionosphereVolume.dispose();
      this.ionosphereVolume = null;
    }
    if (this.ionosphereDensityVolume) {
      this.earthFixedGroup.remove(this.ionosphereDensityVolume.object3d());
      this.ionosphereDensityVolume.dispose();
      this.ionosphereDensityVolume = null;
    }
    this.drapSurface?.dispose();
    this.drapSurface = null;
    this.auroraHistorySurface?.dispose();
    this.auroraHistorySurface = null;
    this.groundField?.dispose();
    this.groundField = null;
    this.groundFieldBundle = null;
    this.geospaceRuntime?.dispose();
    this.geospaceRuntime = null;
    this.coastlines.geometry.dispose();
    this.coastlineMaterial.dispose();
    this.earthMaterial.map?.dispose();
    this.earthMaterial.dispose();
    this.solarWindVisual.dispose();
    this.dRegionEmpirical.dispose();
    this.xrayVisual.dispose();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
    this.hoverLabel.remove();
    this.selectedLabel.remove();
  }
}
