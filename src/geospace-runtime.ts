import * as THREE from "three";
import {
  GEOSPACE_SLICE_MASK,
  contourAdaptivePlaneField,
  prepareAdaptivePlaneField,
} from "./geospace-slice-data";
import type {
  EncodedAdaptivePlaneField,
  GeospaceSliceDisplayMode,
  PreparedAdaptivePlaneField,
  SmoothAdaptivePlaneOptions,
  SmoothedAdaptivePlaneField,
} from "./geospace-slice-data";
import {
  PLASMA_SHEET_BETA_LOG_RANGE,
  PLASMA_SHEET_BETA_THRESHOLD,
  PLASMA_SHEET_CONTOUR_LEVEL,
  PLASMA_SHEET_LIMITATION,
  PLASMA_SHEET_LINE_COLORS,
  PLASMA_SHEET_MEASUREMENT_WINDOW,
  PLASMA_SHEET_REFERENCE_X_RE,
  PLASMA_SHEET_REPRESENTATION,
  betaContourSource,
  isSmoothPlaneField,
  plasmaBetaPlaneField,
  plasmaBetaPointMaterial,
  plasmaBetaSurfaceMaterial,
  plasmaSheetColumns,
  plasmaSheetMetrics,
} from "./plasma-sheet";
import type {
  PlasmaBetaCounts,
  PlasmaBetaPlaneField,
  PlasmaSheetMetrics,
} from "./plasma-sheet";
import {
  buildProjectedFlowAdvectionPaths,
  createBoundaryProfileCurveGeometry,
  createBoundaryRimGeometry,
  createLoftedBoundaryGeometry,
  createMagnetosheathGeometry,
  createMagnetosheathRibbonGeometry,
  createProjectedLineSegmentsGeometry,
  decodeBoundaryProfile,
  sampleProjectedFlowAdvectionPath,
} from "./geospace-structures";
import type {
  EncodedFrameStructures,
  GeospaceStructurePlane,
  GeospaceStructuresDefinition,
  GsmPositionMapper,
  PlanePositionMapper,
  ProjectedAdvectionPath,
} from "./geospace-structures";
import {
  COMBINED_RADIATION_ENERGY_KEV,
  COMBINED_RADIATION_ENERGY_LABEL,
  GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS,
  RADIATION_BELT_VIEWS,
  RADIATION_PITCH_PRESENTATION_LABELS,
  RADIATION_ENERGY_COMBINATION,
  RADIATION_PITCH_PRESENTATION_QUANTITIES,
  createDipoleMappedRadiationGeometry,
  createGyrotropicDipoleMappedRadiationShells,
  combineRadiationEnergyChannels,
  createNativeEquatorialRadiationGeometry,
  dipoleMirrorLatitudeRadians,
  gyrotropicPitchBinWeights,
  isCombinedRadiationEnergy,
  trappedPitchIndex,
} from "./radiation-belt";
import {
  createRadiationFieldLineGuides,
  createRadiationVolumeMesh,
  setRadiationVolumeDipoleOffset,
  setRadiationVolumeDipoleTilt,
} from "./radiation-belt-volume";
import type { RadiationVolumeOpacityResolution } from "./radiation-belt-volume";
import { dipoleTilt } from "./dipole-tilt";
import { eccentricOffsetSm } from "./eccentric-dipole";
import type {
  RadiationBeltDefinition,
  RadiationBeltFrame,
  RadiationEnergyCombination,
  RadiationPitchPresentation,
  RadiationPositionMapper,
} from "./radiation-belt";
import type { GeospaceBundle, GeospaceField, GeospacePlane } from "./types";

export type GeospaceRuntimePlane = GeospacePlane | "both";
export type RadiationBeltRuntimeView = keyof typeof RADIATION_BELT_VIEWS;

/**
 * What the mapped 3-D view draws.
 *
 * `omnidirectional` is the shipped default: every locally trapped pitch channel
 * integrated over solid angle into one volume. `single` draws one published
 * channel as one bounce shell. `all` stacks every non-empty published channel.
 *
 * Neither of the other two is a sensible default, and both have shipped and been
 * rejected on sight. Stacking is not a neutral "show everything" option: ten
 * translucent shells nested inside one another sum to a filled volume whatever
 * each shell's own shape is, so the belts, the slot and the inner edge all
 * disappear into one blob and the viewer sees shell count rather than flux. One
 * channel is worse in the opposite direction: the highest published channel is
 * 81.2 degrees equatorial pitch, mirroring at 4.15 degrees latitude, so its
 * shell is a flat annulus about fourteen times wider than it is thick at every
 * L. It is an honest picture of one look direction and a misleading picture of
 * the belts. Both stay reachable as labelled teaching options.
 */
export type RadiationPitchMode = RadiationPitchPresentation;

/**
 * Pitch selection meaning "draw every published channel at once".
 *
 * It travels through the existing numeric `setRadiationPitchIndex` channel so
 * the mode needs no second control path; the emphasized channel stays whatever
 * was last chosen, which keeps every legend field populated in both modes.
 */
export const ALL_RADIATION_PITCH_CHANNELS = -1;

/**
 * Pitch selection meaning "integrate every locally trapped channel", which is
 * what the layer opens on. It rides the same numeric channel as
 * `ALL_RADIATION_PITCH_CHANNELS` for the same reason.
 */
export const OMNIDIRECTIONAL_RADIATION_PITCH = -2;

export interface GeospaceRuntimeReadyState {
  status: "ready";
  requestedAt: string;
  sourceFrames: readonly [string, string];
  interpolationFraction: number;
  structureFrameValidAt: string;
  runAt: string;
  leadMinutes: number;
  /** Minutes beyond the newest source frame; zero during native coverage. */
  edgeHoldMinutes: number;
}

export interface GeospaceRuntimeNoDataState {
  status: "no-data";
  requestedAt: string;
  reason: "empty-bundle" | "before-coverage" | "after-coverage" | "frame-gap" | "invalid-frame";
  coverage: { validFrom: string | null; validTo: string | null };
}

export type GeospaceRuntimeFrameState = GeospaceRuntimeReadyState | GeospaceRuntimeNoDataState;

export interface GeospaceRangeMetadata {
  scale: "linear" | "log10";
  encodedMinimum: number;
  encodedMaximum: number;
  physicalMinimum: number;
  physicalMaximum: number;
  units: string;
  endpointMeaning: string;
}

export interface GeospaceFieldLegendMetadata {
  kind: "swmf-cut";
  field: GeospaceField;
  title: string;
  coordinateSystem: string;
  range: GeospaceRangeMetadata;
  displayMode: GeospaceSliceDisplayMode;
  plane: GeospaceRuntimePlane;
  sourceFrames: readonly string[];
  validCount: number;
  missingCount: number;
  clippedLowCount: number;
  clippedHighCount: number;
  interpolatedCount: number;
  representation: string;
  /**
   * Whether the selected frames publish the plasma field at all. The archived
   * replay frames deliberately carry only the extracted boundary profiles and
   * streamlines — the full field is kept for the live window — and the legend
   * must say that plainly rather than showing zero counts with no reason.
   */
  fieldPublished: boolean;
}

export interface RadiationBeltLegendMetadata {
  kind: "rbe";
  title: string;
  range: GeospaceRangeMetadata;
  energyKev: number;
  /** What to print instead of an energy when the view is not one channel. */
  energyLabel: string | null;
  combinedEnergyView: boolean;
  energyCombination: RadiationEnergyCombination | null;
  /** Flux below which the volume view draws nothing; null off the volume. */
  opacityFloorLog10Flux: number | null;
  opacityFloorReason: string | null;
  /**
   * Where that floor came from on the data now loaded: derived from this
   * dataset's own field, taken from the shipped fallback table because the
   * field could not be read, or set explicitly by a caller. Null off the
   * volume view. The card prints it, so a fallback is never silent.
   */
  opacityFloorSource: RadiationVolumeOpacityResolution["floorSource"] | null;
  pitchIndex: number;
  pitchCoordinateSin: number;
  pitchAngleDegrees: number;
  view: RadiationBeltRuntimeView;
  viewLabel: string;
  viewStatus: string;
  sourcePitchChannelCount: number;
  displayedPitchChannelCount: number;
  selectedPitchEmphasized: boolean;
  /**
   * `omnidirectional` integrates every locally trapped channel into one volume;
   * `single` draws only `pitchIndex`; `all` stacks every non-empty published
   * channel and emphasizes `pitchIndex`. The legend must say which, because the
   * three read as completely different objects.
   */
  pitchMode: RadiationPitchMode;
  particlePopulation: "RBE model electrons only";
  representation: string;
  /**
   * What the layer does and does not claim about variation along the field line.
   * It differs between the presentations, so it is carried rather than assumed.
   */
  alongFieldInterpretation: string;
  /** The source's own coverage limit, which no presentation can escape. */
  sourceCoverage: string;
  validAt: string | null;
}

export interface GeospaceStructureLegendMetadata {
  kind: "swmf-structure-proxies";
  coordinateSystem: "GSM";
  boundaryStatus: "model-derived-proxies";
  boundaryUnits: "Earth radii (R_E)";
  flowSpeedUnits: "km/s";
  flowSpeedRange: [number, number] | null;
  /** Published bow-shock radius minus published magnetopause radius, in Re. */
  sheathThicknessRangeRe: [number, number] | null;
  /**
   * The published meridional bow-shock and magnetopause-proxy radii on the
   * subsolar ray (angle 0), in Re. These are the two numbers that move when
   * the storm compresses the dayside, and they are published for every frame
   * — including the archived ones that carry no field — so the data viewer
   * can show the compression as a number across the whole replay.
   */
  subsolarBowShockRe: number | null;
  subsolarMagnetopauseRe: number | null;
  structureDisplay: GeospaceStructureDisplay;
  representation: string;
  limitation: string;
  validAt: string | null;
}

/**
 * Everything the plasma-sheet layer's key card needs, and nothing it does not.
 *
 * `betaPublished` is the same distinction the plasma cut's `fieldPublished`
 * makes and it exists for the same reason: the archived replay frames carry
 * boundary profiles but no plasma field, so there is no pressure and no |B| to
 * divide, and the card has to say that rather than print zeros.
 */
export interface PlasmaSheetLegendMetadata {
  kind: "swmf-derived-plasma-beta";
  coordinateSystem: string;
  /** Whether the bracketing frames publish p and |B| at all. */
  betaPublished: boolean;
  plane: GeospaceRuntimePlane;
  displayMode: GeospaceSliceDisplayMode;
  /** Ramp endpoints, in log10 beta. */
  logRange: readonly [number, number];
  threshold: number;
  units: string;
  counts: PlasmaBetaCounts | null;
  metrics: PlasmaSheetMetrics | null;
  /** Whether the measured column scan could run on this frame at all. */
  metricsAvailable: boolean;
  representation: string;
  limitation: string;
  sourceFrames: readonly string[];
  validAt: string | null;
}

export interface GeospaceRuntimeLegendMetadata {
  state: GeospaceRuntimeFrameState;
  field: GeospaceFieldLegendMetadata;
  radiation: RadiationBeltLegendMetadata | null;
  structures: GeospaceStructureLegendMetadata;
}

export interface GeospaceRuntimeOptions {
  bundle: GeospaceBundle;
  parent?: THREE.Object3D;
  positionForPlane?: PlanePositionMapper;
  positionForGsm?: GsmPositionMapper;
  positionForRadiation?: RadiationPositionMapper;
  displayMode?: GeospaceSliceDisplayMode;
  field?: GeospaceField;
  plane?: GeospaceRuntimePlane;
  /** The derived plasma-beta layer's own cut choice; defaults to meridional. */
  plasmaSheetPlane?: GeospaceRuntimePlane;
  /**
   * Whether to derive the plasma-beta layer at all. Off by default: it is a
   * measured 230 ms per frame change, and it buys nothing while the layer is
   * hidden. See `plasmaSheetEnabledValue`.
   */
  plasmaSheetEnabled?: boolean;
  radiationView?: RadiationBeltRuntimeView;
  radiationEnergyKev?: number;
  radiationPitchIndex?: number;
  smoothing?: Omit<SmoothAdaptivePlaneOptions, "mode">;
  pixelRatio?: number;
  modelSecondsPerDisplaySecond?: number;
  structureDisplay?: GeospaceStructureDisplay;
  maximumInterpolationGapMs?: number;
  /** Short operational latency allowance after the newest published frame. */
  operationalEdgeHoldMs?: number;
  /**
   * Rendering extent for the cut planes, in GSM Re: samples tailward of
   * `minimumXRe` or beyond `maximumCrossRe` are not drawn.
   *
   * This is presentation, not data policy: when the cuts are shown embedded
   * inside the 3-D magnetosphere they are clipped to the boundary region so
   * they read as a cross-section through the scene rather than a wall behind
   * it. The mask counts in the legend still describe the full published
   * grid — clipping what is drawn never changes what the model published.
   */
  cutExtentRe?: { minimumXRe: number; maximumCrossRe: number } | null;
}

interface RuntimePlaneFrame {
  fieldsU16: Record<GeospaceField, string>;
  fieldMasksU8?: Record<GeospaceField, string>;
}

interface RuntimeRadiationFrame {
  coordinatesU16: string;
  electronFluxU16: Record<string, string>;
  pitchResolvedElectronFluxU16?: Record<string, string>;
}

interface RuntimeFrame {
  validAt: string;
  runAt: string;
  leadMinutes: number;
  planes: Record<GeospacePlane, RuntimePlaneFrame>;
  structures?: EncodedFrameStructures;
  radiationBelt: RuntimeRadiationFrame;
}

interface RuntimeBundleExtension {
  structures?: GeospaceStructuresDefinition;
  radiationBelt: GeospaceBundle["radiationBelt"] & Partial<RadiationBeltDefinition>;
  frames: RuntimeFrame[];
}

interface FrameEntry {
  frame: RuntimeFrame;
  originalIndex: number;
  timeMs: number;
}

interface FrameBracket {
  lower: FrameEntry;
  upper: FrameEntry;
  fraction: number;
  structure: FrameEntry;
  edgeHoldMinutes: number;
}

interface MaskCounts {
  valid: number;
  missing: number;
  clippedLow: number;
  clippedHigh: number;
  interpolated: number;
}

interface FlowTracer {
  path: ProjectedAdvectionPath;
  plane: GeospaceStructurePlane;
  phase: number;
}

const PLANES = ["equatorial", "meridional"] as const satisfies readonly GeospacePlane[];
const FIELDS = ["density", "speed", "pressure", "magneticField"] as const satisfies readonly GeospaceField[];

const FIELD_TITLES: Record<GeospaceField, string> = {
  density: "Mass density",
  speed: "Bulk plasma speed",
  pressure: "Thermal pressure",
  magneticField: "Magnetic-field magnitude",
};

/**
 * Low anchors sit well above the sky's black on purpose. When they were
 * near-black, the bottom third of every ramp — the magnetospheric cavity, the
 * tail lobes, the slowed sheath on the speed ramp — was indistinguishable
 * from the background, so real model output read as absence and only the
 * masked holes should. Every valid cell now lands on a visible colour, the
 * way the textbook cross-sections shade the whole cavity in blue. Changing
 * an anchor here means changing GEOSPACE_FIELD_GRADIENTS in main.ts to match,
 * or the legend lies about the ramp.
 */
const FIELD_PALETTES: Record<GeospaceField, readonly [number, number, number]> = {
  density: [0x1c3f66, 0x29d4e3, 0xf3ffff],
  speed: [0x23486b, 0x76e6a5, 0xf5c96a],
  pressure: [0x3a2b4d, 0xf5c96a, 0xff7b78],
  magneticField: [0x2b2750, 0xa98cff, 0x5ce8f1],
};

const defaultPlanePosition: PlanePositionMapper = (xRe, crossRe, plane) =>
  plane === "equatorial"
    ? new THREE.Vector3(xRe, 0, crossRe)
    : new THREE.Vector3(xRe, crossRe, 0);

const defaultGsmPosition: GsmPositionMapper = (xRe, yRe, zRe) => new THREE.Vector3(xRe, yRe, zRe);

function decodeBase64Bytes(encoded: string) {
  const binary = globalThis.atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

function decodeLittleEndianUint16(encoded: string) {
  const bytes = decodeBase64Bytes(encoded);
  if (bytes.byteLength % 2 !== 0) throw new RangeError("Encoded uint16 data has an odd byte count");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const values = new Uint16Array(bytes.byteLength / 2);
  for (let index = 0; index < values.length; index += 1) values[index] = view.getUint16(index * 2, true);
  return values;
}

function encodeLittleEndianUint16(values: ArrayLike<number>) {
  const bytes = new Uint8Array(values.length * 2);
  const view = new DataView(bytes.buffer);
  for (let index = 0; index < values.length; index += 1) view.setUint16(index * 2, values[index] ?? 0, true);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]!);
  return globalThis.btoa(binary);
}

function nearestEnergy(available: readonly number[], requested: number) {
  // The combined view is not a channel and must never be rounded into one of
  // them, so it is passed through untouched rather than snapped.
  if (isCombinedRadiationEnergy(requested)) return requested;
  return available.reduce(
    (nearest, candidate) => Math.abs(candidate - requested) < Math.abs(nearest - requested) ? candidate : nearest,
    available[0] ?? requested,
  );
}

function exactEnergyEntry(record: Record<string, string>, energyKev: number) {
  return Object.entries(record).find(([key]) => Math.abs(Number(key) - energyKev) < 1e-3)?.[1] ?? null;
}

function disposeMaterial(material: THREE.Material | THREE.Material[]) {
  if (Array.isArray(material)) material.forEach((item) => item.dispose());
  else material.dispose();
}

function disposeChildren(group: THREE.Group) {
  group.traverse((object) => {
    if (object === group) return;
    const renderable = object as THREE.Mesh | THREE.Points | THREE.LineSegments;
    renderable.geometry?.dispose();
    if (renderable.material) disposeMaterial(renderable.material);
  });
  group.clear();
}

function fieldPointMaterial(field: GeospaceField, pointSize: number, pixelRatio: number) {
  const palette = FIELD_PALETTES[field];
  return new THREE.ShaderMaterial({
    uniforms: {
      pointSize: { value: pointSize },
      pixelRatio: { value: Math.max(0.25, pixelRatio) },
      lowColor: { value: new THREE.Color(palette[0]) },
      middleColor: { value: new THREE.Color(palette[1]) },
      highColor: { value: new THREE.Color(palette[2]) },
    },
    transparent: true,
    depthWrite: false,
    vertexShader: `
      attribute float fieldValue;
      attribute float dataValid;
      attribute float saturation;
      uniform float pointSize;
      uniform float pixelRatio;
      varying float valueForColor;
      varying float saturationForColor;
      varying float validForColor;
      void main() {
        valueForColor = fieldValue;
        saturationForColor = saturation;
        validForColor = dataValid;
        gl_PointSize = dataValid > 0.5 ? pointSize * pixelRatio : 0.0;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 lowColor;
      uniform vec3 middleColor;
      uniform vec3 highColor;
      varying float valueForColor;
      varying float saturationForColor;
      varying float validForColor;
      void main() {
        if (validForColor < 0.5) discard;
        float radius = length(gl_PointCoord - vec2(0.5));
        if (radius > 0.5) discard;
        float value = clamp(valueForColor, 0.0, 1.0);
        vec3 color = value < 0.5
          ? mix(lowColor, middleColor, value * 2.0)
          : mix(middleColor, highColor, (value - 0.5) * 2.0);
        if (saturationForColor < -0.5) color = mix(color, lowColor, 0.65);
        if (saturationForColor > 0.5) color = mix(color, highColor, 0.65);
        float edge = 1.0 - smoothstep(0.34, 0.5, radius);
        gl_FragColor = vec4(color, edge * (0.2 + 0.68 * value));
      }
    `,
  });
}

/**
 * The plasma field as a continuous colour surface.
 *
 * The cut planes used to be drawn as screen-space dots, one per resampled
 * grid node. Dots survive as the honest presentation of the *native* adaptive
 * grid — where the point positions themselves are the data — but for the
 * smoothed regular grid they were an accident of implementation, and they had
 * a consequence: a discontinuity cannot be seen in a field of separated dots.
 * The bow shock IS a discontinuity in density and speed; drawn as a filled
 * surface it appears on its own, as a colour step in real model output, which
 * is the difference between showing the shock and drawing a picture of one.
 *
 * Triangles are indexed only where every corner carries a valid sample, so a
 * masked region is a hole in the surface, never an interpolation — the same
 * refusal the boundary layers already make.
 */
function fieldSurfaceMaterial(field: GeospaceField) {
  const palette = FIELD_PALETTES[field];
  return new THREE.ShaderMaterial({
    uniforms: {
      lowColor: { value: new THREE.Color(palette[0]) },
      middleColor: { value: new THREE.Color(palette[1]) },
      highColor: { value: new THREE.Color(palette[2]) },
    },
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    vertexShader: `
      attribute float fieldValue;
      attribute float dataValid;
      attribute float saturation;
      varying float valueForColor;
      varying float saturationForColor;
      varying float validForColor;
      void main() {
        valueForColor = fieldValue;
        saturationForColor = saturation;
        validForColor = dataValid;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 lowColor;
      uniform vec3 middleColor;
      uniform vec3 highColor;
      varying float valueForColor;
      varying float saturationForColor;
      varying float validForColor;
      void main() {
        if (validForColor < 0.999) discard;
        float value = clamp(valueForColor, 0.0, 1.0);
        vec3 color = value < 0.5
          ? mix(lowColor, middleColor, value * 2.0)
          : mix(middleColor, highColor, (value - 0.5) * 2.0);
        if (saturationForColor < -0.5) color = mix(color, lowColor, 0.65);
        if (saturationForColor > 0.5) color = mix(color, highColor, 0.65);
        // Alpha is nearly constant and high, deliberately. When alpha tracked
        // the value, the slow half of every ramp faded into the black sky, so
        // the magnetospheric cavity and the slowed sheath — the very regions
        // the shock is a jump INTO — read as absence instead of as data, and
        // only the missing-mask holes should read as absence. The colour ramp
        // is the encoding; opacity encodes nothing.
        gl_FragColor = vec4(color, 0.82 + 0.12 * value);
      }
    `,
  });
}

/** Triangles over the regular smooth grid, only where all corners are valid. */
function smoothGridIndices(width: number, height: number, valid: ArrayLike<number>) {
  const indices: number[] = [];
  for (let row = 0; row < height - 1; row += 1) {
    for (let column = 0; column < width - 1; column += 1) {
      const a = row * width + column;
      const b = a + 1;
      const c = a + width + 1;
      const d = a + width;
      if (valid[a] && valid[b] && valid[c]) indices.push(a, b, c);
      if (valid[a] && valid[c] && valid[d]) indices.push(a, c, d);
    }
  }
  return indices;
}

function radiationSurfaceMaterial(opacityScale = 1, highlightStrength = 0, fadeMirrorEdges = false) {
  return new THREE.ShaderMaterial({
    uniforms: {
      opacityScale: { value: THREE.MathUtils.clamp(opacityScale, 0, 1) },
      highlightStrength: { value: THREE.MathUtils.clamp(highlightStrength, 0, 1) },
      fadeMirrorEdges: { value: fadeMirrorEdges ? 1 : 0 },
    },
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.NormalBlending,
    vertexShader: `
      attribute float fluxValue;
      attribute float latitudeFraction;
      varying float fluxForColor;
      varying float mirrorFraction;
      void main() {
        fluxForColor = fluxValue;
        mirrorFraction = abs(latitudeFraction);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float opacityScale;
      uniform float highlightStrength;
      uniform float fadeMirrorEdges;
      varying float fluxForColor;
      varying float mirrorFraction;
      void main() {
        float value = clamp(fluxForColor, 0.0, 1.0);
        vec3 low = vec3(0.125, 0.102, 0.231);
        vec3 middle = vec3(0.663, 0.549, 1.0);
        vec3 high = vec3(0.961, 0.788, 0.416);
        vec3 color = value < 0.5 ? mix(low, middle, value * 2.0) : mix(middle, high, (value - 0.5) * 2.0);
        color = mix(color, vec3(1.0, 0.91, 0.62), 0.34 * highlightStrength);
        // No opacity floor. A floor makes a zero-flux surface partly opaque,
        // and with eleven nested pitch shells stacked the accumulated haze,
        // not the flux, sets how dark the volume looks — which flattened the
        // slot region's genuine three-decade drop to about 1.4:1 contrast
        // against the belt cores. Peak opacity is unchanged.
        float alpha = opacityScale * 0.53 * pow(value, 0.68);
        float mirrorFade = 1.0 - smoothstep(0.76, 1.0, mirrorFraction);
        alpha *= mix(1.0, mirrorFade, fadeMirrorEdges);
        gl_FragColor = vec4(color, alpha);
      }
    `,
  });
}

function emptyMaskCounts(): MaskCounts {
  return { valid: 0, missing: 0, clippedLow: 0, clippedHigh: 0, interpolated: 0 };
}

function addMaskCounts(total: MaskCounts, masks: Uint8Array) {
  masks.forEach((mask) => {
    if ((mask & GEOSPACE_SLICE_MASK.missing) !== 0) total.missing += 1;
    else total.valid += 1;
    if ((mask & GEOSPACE_SLICE_MASK.clippedLow) !== 0) total.clippedLow += 1;
    if ((mask & GEOSPACE_SLICE_MASK.clippedHigh) !== 0) total.clippedHigh += 1;
    if ((mask & GEOSPACE_SLICE_MASK.interpolated) !== 0) total.interpolated += 1;
  });
}

function combinePreparedFields(
  lower: PreparedAdaptivePlaneField,
  upper: PreparedAdaptivePlaneField,
  fraction: number,
) {
  if (lower.mode !== upper.mode || lower.values.length !== upper.values.length) return null;
  const values = new Float32Array(lower.values.length);
  const masks = new Uint8Array(lower.masks.length);
  for (let index = 0; index < values.length; index += 1) {
    const lowerMask = lower.masks[index]!;
    const upperMask = upper.masks[index]!;
    const lowerMissing = (lowerMask & GEOSPACE_SLICE_MASK.missing) !== 0;
    const upperMissing = (upperMask & GEOSPACE_SLICE_MASK.missing) !== 0;
    if (lowerMissing || upperMissing || !Number.isFinite(lower.values[index]) || !Number.isFinite(upper.values[index])) {
      values[index] = Number.NaN;
      masks[index] = lowerMask | upperMask | GEOSPACE_SLICE_MASK.missing;
    } else {
      values[index] = THREE.MathUtils.lerp(lower.values[index]!, upper.values[index]!, fraction);
      masks[index] = lowerMask | upperMask | (fraction > 0 && fraction < 1 ? GEOSPACE_SLICE_MASK.interpolated : 0);
    }
  }
  return { values, masks };
}

function rangeMetadata(
  encoding: { scale: "linear" | "log10"; minimum: number; maximum: number; units: string },
  endpointMeaning: string,
): GeospaceRangeMetadata {
  return {
    scale: encoding.scale,
    encodedMinimum: encoding.minimum,
    encodedMaximum: encoding.maximum,
    physicalMinimum: encoding.scale === "log10" ? 10 ** encoding.minimum : encoding.minimum,
    physicalMaximum: encoding.scale === "log10" ? 10 ** encoding.maximum : encoding.maximum,
    units: encoding.units,
    endpointMeaning,
  };
}

function selectedPitchFrame(
  definition: RadiationBeltDefinition,
  frame: RuntimeRadiationFrame,
  energyKev: number,
  pitchIndex: number,
) {
  const resolved = frame.pitchResolvedElectronFluxU16;
  const encoded = resolved ? exactEnergyEntry(resolved, energyKev) : null;
  if (!encoded) return null;
  const allValues = decodeLittleEndianUint16(encoded);
  const pitchCount = definition.pitchCoordinatesSin.length;
  if (allValues.length !== definition.count * pitchCount) return null;
  const selectedValues = new Uint16Array(definition.count);
  for (let pointIndex = 0; pointIndex < definition.count; pointIndex += 1) {
    selectedValues[pointIndex] = allValues[pointIndex * pitchCount + pitchIndex] ?? 0;
  }
  const selectedEncoded = encodeLittleEndianUint16(selectedValues);
  const key = String(energyKev);
  const selectedDefinition: RadiationBeltDefinition = {
    ...definition,
    pitchCoordinate: definition.pitchCoordinatesSin[pitchIndex]!,
    pitchCoordinatesSin: [definition.pitchCoordinatesSin[pitchIndex]!],
    pitchAnglesDegrees: [definition.pitchAnglesDegrees[pitchIndex]!],
  };
  const selectedFrame: RadiationBeltFrame = {
    coordinatesU16: frame.coordinatesU16,
    electronFluxU16: { [key]: selectedEncoded },
    pitchResolvedElectronFluxU16: { [key]: selectedEncoded },
  };
  return { definition: selectedDefinition, frame: selectedFrame };
}

/**
 * The named regions of the textbook cross-section, each backed by published
 * data and each switchable on its own.
 *
 * They used to share one `boundaryGroup` and one `streamlineGroup`, which
 * meant the bow shock and the magnetic field lines could only be shown by
 * switching on the whole two-plane plasma presentation — a control that is
 * hidden from the public UI. Nothing could reach them, so nothing drew them.
 */
/**
 * How the three boundary regions are drawn.
 *
 * `cross-section` draws each published profile as a curve in its own cut
 * plane, which is how every textbook figure of this system is drawn and the
 * only way the three regions read as three regions. `surface` keeps the
 * two-cut loft, which is a closed shell and reads as one blob from outside.
 */
export type GeospaceStructureDisplay = "cross-section" | "surface";

export type GeospaceStructureRegion =
  | "bowShock"
  | "magnetosheath"
  | "magnetopause"
  | "magneticField"
  | "flowStreamlines"
  | "flowTracers";

/**
 * The colour each named region is drawn in — ONE copy, because the legend has
 * to name these by colour and a second copy is how a swatch starts lying about
 * the thing it points at.
 *
 * The bow shock and the magnetosheath are both warm, and the exterior-cusp
 * funnels on the driven-field face of this same layer are warm too. That is
 * exactly why the legend has to name them: Sean read those funnels as bow
 * shocks on the shipped build, which is the misreading these swatches exist to
 * stop. Nothing here changes what is drawn.
 */
export const GEOSPACE_BOUNDARY_COLORS = {
  bowShock: 0xf5c96a,
  magnetopauseProxy: 0x5ce8f1,
  magnetosheath: 0xf3a86a,
} as const;

export const GEOSPACE_STRUCTURE_REGIONS: Record<GeospaceStructureRegion, {
  label: string;
  what: string;
  status: string;
}> = {
  bowShock: {
    label: "Bow shock",
    what: "Where the supersonic solar wind is abruptly slowed, heated and deflected before it ever reaches the magnetopause.",
    status: "Model-derived: the raywise jump located in the two published NOAA BATS-R-US cuts, lofted between them. The extraction runs only 70 degrees either side of the subsolar point, so this is a dayside CAP — no flanks, no tail — and its rim is drawn to show where the published surface ends. A real bow shock flares open and trails downstream indefinitely; that part is not in this release.",
  },
  magnetosheath: {
    label: "Magnetosheath",
    what: "The shocked, slowed, heated solar-wind plasma between the bow shock and the magnetopause.",
    status: "The region between two model-derived boundaries. It is bounded by published surfaces, not separately modelled, and nothing inside it is drawn as a field.",
  },
  magnetopause: {
    label: "Magnetopause (model-derived)",
    what: "The boundary of the cavity the Earth's field holds against the solar wind.",
    status: "Model-derived from the same two published cuts. Distinct from the empirical Shue/Nguyen/Lin surfaces on the magnetopause layer.",
  },
  magneticField: {
    label: "Earth's magnetic field",
    what: "The field lines themselves: compressed on the dayside, drawn out into the tail.",
    status: "In-plane projections of the published BATS-R-US B vectors on the two cuts. Projected lines, not traced three-dimensional field lines.",
  },
  flowStreamlines: {
    label: "Solar-wind flow lines",
    what: "The path the shocked flow takes around the obstacle.",
    status: "In-plane projections of the published BATS-R-US U vectors on the two cuts.",
  },
  flowTracers: {
    label: "Flow tracers",
    what: "Marks advected along those flow lines at the model's own local speed.",
    status: "Frozen-frame advection along projected paths. Not particle trajectories.",
  },
};

export class GeospaceRuntime {
  readonly group = new THREE.Group();
  readonly cutGroup = new THREE.Group();
  readonly boundaryGroup = new THREE.Group();
  readonly bowShockGroup = new THREE.Group();
  readonly magnetosheathGroup = new THREE.Group();
  readonly magnetopauseProxyGroup = new THREE.Group();
  readonly streamlineGroup = new THREE.Group();
  readonly magneticStreamlineGroup = new THREE.Group();
  readonly flowStreamlineGroup = new THREE.Group();
  readonly flowAdvectionGroup = new THREE.Group();
  readonly radiationGroup = new THREE.Group();
  /**
   * The derived plasma-beta cut: its own group because it is its own LAYER,
   * switched from the rail beside the radiation belts rather than from inside
   * the magnetosphere layer's settings. It rides this runtime because it is
   * computed from this runtime's frames — nothing else is shared.
   */
  readonly plasmaSheetGroup = new THREE.Group();

  private readonly bundle: GeospaceBundle;
  private readonly runtimeBundle: GeospaceBundle & RuntimeBundleExtension;
  private readonly frames: FrameEntry[];
  private readonly positionForPlane: PlanePositionMapper;
  private readonly positionForGsm: GsmPositionMapper;
  private readonly positionForRadiation: RadiationPositionMapper;
  private readonly smoothing: Omit<SmoothAdaptivePlaneOptions, "mode">;
  private pixelRatio: number;
  private readonly modelSecondsPerDisplaySecond: number;
  private readonly maximumInterpolationGapMs: number;
  private readonly operationalEdgeHoldMs: number;
  private readonly attachedParent: THREE.Object3D | null;
  private fieldValue: GeospaceField;
  private planeValue: GeospaceRuntimePlane;
  private displayModeValue: GeospaceSliceDisplayMode;
  private radiationViewValue: RadiationBeltRuntimeView;
  private radiationEnergyValue: number;
  private radiationPitchIndexValue: number;
  /** Inputs the currently built radiation geometry was made from. */
  private radiationGeometryKeyValue: string | null = null;
  /**
   * What the omnidirectional volume was last built with — including the floor
   * DERIVED from the loaded field rather than read out of a table. Null
   * whenever the volume is not what is drawn, so the readout can never quote a
   * floor belonging to a picture that is no longer on screen.
   */
  private dipoleTiltRadians: number | null = null;
  private dipoleOffsetSm: { x: number; y: number; z: number } | null = null;
  private radiationVolumeOpacityValue: RadiationVolumeOpacityResolution | null = null;
  private stateValue: GeospaceRuntimeFrameState;
  private bracket: FrameBracket | null = null;
  private maskCounts = emptyMaskCounts();
  private structureFrameValidAt: string | null = null;
  private flowSpeedRange: [number, number] | null = null;
  private sheathThicknessRange: [number, number] | null = null;
  private subsolarBowShockRe: number | null = null;
  private subsolarMagnetopauseRe: number | null = null;
  private fieldPublished = false;
  /**
   * The plasma-sheet layer's own cut-plane choice, kept separate from the
   * magnetosphere layer's `planeValue` on purpose: they are two layers, a
   * reader can have both on, and changing one layer's presentation must not
   * silently change the other's.
   */
  private plasmaSheetPlaneValue: GeospaceRuntimePlane;
  /**
   * Whether the plasma-sheet layer is switched on, and therefore whether its
   * rebuild runs at all.
   *
   * This gate is here because the cost was MEASURED, not assumed. Deriving
   * beta needs pressure and |B| for both bracketing frames, which is four
   * resamplings of the adaptive grid onto the display grid; one resampling of
   * the published meridional plane took 57 ms on a fast development machine,
   * so the layer costs about 230 ms of the ~290 ms a timeline step would take
   * with it always on. Paying that on every scrub for a layer that is off by
   * default would slow the whole site down for readers who never open it, and
   * this project already carries a low-resource-mode brief. Switching the
   * layer on rebuilds immediately, so the gate is invisible to anyone using it.
   */
  private plasmaSheetEnabledValue: boolean;
  private plasmaSheetCountsValue: PlasmaBetaCounts | null = null;
  private plasmaSheetMetricsValue: PlasmaSheetMetrics | null = null;
  private plasmaSheetPublished = false;
  private structureDisplayValue: GeospaceStructureDisplay;
  private readonly cutExtentRe: { minimumXRe: number; maximumCrossRe: number } | null;
  private flowTracers: FlowTracer[] = [];
  private advectionModelSeconds = 0;
  private disposed = false;

  constructor(options: GeospaceRuntimeOptions) {
    this.bundle = options.bundle;
    this.runtimeBundle = options.bundle as GeospaceBundle & RuntimeBundleExtension;
    this.positionForPlane = options.positionForPlane ?? defaultPlanePosition;
    this.positionForGsm = options.positionForGsm ?? defaultGsmPosition;
    this.positionForRadiation = options.positionForRadiation ?? this.positionForGsm;
    this.smoothing = options.smoothing ?? {};
    this.pixelRatio = Math.max(0.25, options.pixelRatio ?? 1);
    this.modelSecondsPerDisplaySecond = Math.max(0, options.modelSecondsPerDisplaySecond ?? 900);
    this.structureDisplayValue = options.structureDisplay ?? "cross-section";
    this.cutExtentRe = options.cutExtentRe ?? null;
    // Mass density is the opening field, decided by looking at the live
    // frames rather than by argument. Speed was tried first and failed a
    // specific way: the sheath and the cavity are BOTH slow, so on the speed
    // ramp the two regions merge and the magnetopause disappears. On the
    // density ramp the same frames show all three structures at once — the
    // shock as a jump (3.7x on the 2026-08-09 frames), the sheath as the
    // bright compressed band, and the magnetopause as the sharp edge into
    // the rarefied cavity — which is exactly the anatomy of the textbook
    // cross-section. Speed and pressure remain one click away.
    this.fieldValue = options.field ?? "density";
    // The noon-midnight cut is the opening plane: it is the view every
    // textbook figure of this system uses, and it is the plane in which the
    // bow shock, the magnetosheath, the compressed dayside and the tail all
    // appear in one picture. Two cuts at once read as an X of intersecting
    // sheets and bury exactly that picture, so "both" is a choice, not the
    // default.
    this.planeValue = options.plane ?? "meridional";
    // Meridional by default and for a reason specific to THIS layer: the
    // plasma sheet is a thin sheet seen edge-on in the noon-midnight cut, and
    // the equatorial cut is the plane a tilted dipole most often misses. The
    // equatorial view stays one click away because that miss is worth seeing.
    this.plasmaSheetPlaneValue = options.plasmaSheetPlane ?? "meridional";
    this.plasmaSheetEnabledValue = options.plasmaSheetEnabled ?? false;
    this.displayModeValue = options.displayMode ?? "smooth";
    this.radiationViewValue = options.radiationView ?? "nativeEquatorial";
    const energies = this.bundle.radiationBelt.energiesKev;
    this.radiationEnergyValue = nearestEnergy(energies, options.radiationEnergyKev ?? energies[0] ?? 0);
    this.radiationPitchIndexValue = this.clampedPitchSelection(options.radiationPitchIndex);
    this.frames = this.runtimeBundle.frames
      .map((frame, originalIndex) => ({ frame, originalIndex, timeMs: Date.parse(frame.validAt) }))
      .filter((entry) => Number.isFinite(entry.timeMs))
      .sort((first, second) => first.timeMs - second.timeMs);
    this.maximumInterpolationGapMs = options.maximumInterpolationGapMs
      ?? this.defaultMaximumInterpolationGapMs();
    this.operationalEdgeHoldMs = Math.max(0, options.operationalEdgeHoldMs ?? 30 * 60_000);
    this.attachedParent = options.parent ?? null;
    this.group.name = "geospace-runtime";
    this.cutGroup.name = "swmf-native-or-smoothed-cuts";
    this.boundaryGroup.name = "swmf-model-derived-boundary-proxies";
    this.bowShockGroup.name = "swmf-model-derived-bow-shock";
    this.magnetosheathGroup.name = "swmf-region-between-bow-shock-and-magnetopause";
    this.magnetopauseProxyGroup.name = "swmf-model-derived-magnetopause-proxy";
    this.streamlineGroup.name = "swmf-projected-streamlines";
    this.magneticStreamlineGroup.name = "swmf-projected-magnetic-field-lines";
    this.flowStreamlineGroup.name = "swmf-projected-bulk-flow-lines";
    this.flowAdvectionGroup.name = "swmf-model-time-flow-advection";
    this.radiationGroup.name = "rbe-radiation-environment";
    this.plasmaSheetGroup.name = "swmf-derived-plasma-beta-cut";
    // The sheath is drawn first so the two boundaries that define it read on
    // top of it rather than through it.
    this.boundaryGroup.add(this.magnetosheathGroup, this.bowShockGroup, this.magnetopauseProxyGroup);
    this.streamlineGroup.add(this.magneticStreamlineGroup, this.flowStreamlineGroup);
    this.group.add(
      this.cutGroup,
      this.plasmaSheetGroup,
      this.boundaryGroup,
      this.streamlineGroup,
      this.flowAdvectionGroup,
      this.radiationGroup,
    );
    this.group.userData.coordinateSystem = this.bundle.coordinateSystem;
    this.group.userData.noVolumetricReconstruction = true;
    this.attachedParent?.add(this.group);
    this.stateValue = this.noDataState("empty-bundle", new Date(Number.NaN));
    const initial = this.frames.at(-1);
    if (initial) this.setSimulationTime(new Date(initial.timeMs));
  }

  get state() {
    return this.stateValue;
  }

  get field() {
    return this.fieldValue;
  }

  get plane() {
    return this.planeValue;
  }

  get displayMode() {
    return this.displayModeValue;
  }

  get radiationView() {
    return this.radiationViewValue;
  }

  get radiationEnergyKev() {
    return this.radiationEnergyValue;
  }

  get radiationPitchIndex() {
    return this.radiationPitchIndexValue;
  }

  get radiationPitchMode(): RadiationPitchMode {
    if (this.radiationPitchIndexValue === ALL_RADIATION_PITCH_CHANNELS) return "all";
    if (this.radiationPitchIndexValue === OMNIDIRECTIONAL_RADIATION_PITCH) return "omnidirectional";
    return "single";
  }

  /**
   * The channel the legend names and the shell the single-channel view draws.
   *
   * In `all` mode this is still a real channel — the one that is emphasized —
   * so no legend field ever goes blank because of the display mode.
   */
  get radiationEmphasisPitchIndex() {
    if (this.radiationPitchIndexValue >= 0) return this.radiationPitchIndexValue;
    const definition = this.radiationDefinition();
    if (!definition) return 0;
    return trappedPitchIndex(definition.pitchCoordinatesSin);
  }

  get radiationChoices() {
    const definition = this.radiationDefinition();
    return {
      energiesKev: [...this.bundle.radiationBelt.energiesKev],
      /** The extra selection that is not a channel: every channel at once. */
      combinedEnergyKev: COMBINED_RADIATION_ENERGY_KEV,
      pitchCoordinatesSin: [...(definition?.pitchCoordinatesSin ?? [])],
      pitchAnglesDegrees: [...(definition?.pitchAnglesDegrees ?? [])],
      views: RADIATION_BELT_VIEWS,
    };
  }

  setField(field: GeospaceField) {
    if (!FIELDS.includes(field)) return;
    this.fieldValue = field;
    this.rebuildCuts();
  }

  get structureDisplay() {
    return this.structureDisplayValue;
  }

  setStructureDisplay(mode: GeospaceStructureDisplay) {
    if (mode === this.structureDisplayValue) return;
    this.structureDisplayValue = mode;
    this.rebuildStructures();
  }

  setPlane(plane: GeospaceRuntimePlane) {
    if (plane !== "both" && !PLANES.includes(plane)) return;
    this.planeValue = plane;
    this.rebuildCuts();
    this.rebuildStructures();
  }

  setDisplayMode(mode: GeospaceSliceDisplayMode) {
    this.displayModeValue = mode;
    this.rebuildCuts();
    this.rebuildPlasmaSheet();
  }

  get plasmaSheetPlane() {
    return this.plasmaSheetPlaneValue;
  }

  setPlasmaSheetPlane(plane: GeospaceRuntimePlane) {
    if (plane !== "both" && !PLANES.includes(plane)) return;
    this.plasmaSheetPlaneValue = plane;
    this.rebuildPlasmaSheet();
  }

  get plasmaSheetEnabled() {
    return this.plasmaSheetEnabledValue;
  }

  /**
   * Switch the derivation on or off. Switching ON rebuilds at once, so the
   * layer is populated by the time its own visibility is applied and its key
   * card is asked what it measured.
   */
  setPlasmaSheetEnabled(enabled: boolean) {
    if (enabled === this.plasmaSheetEnabledValue) return;
    this.plasmaSheetEnabledValue = enabled;
    this.rebuildPlasmaSheet();
  }

  setRadiationView(view: RadiationBeltRuntimeView) {
    this.radiationViewValue = view;
    this.rebuildRadiation();
  }

  setRadiationEnergy(energyKev: number) {
    this.radiationEnergyValue = nearestEnergy(this.bundle.radiationBelt.energiesKev, energyKev);
    this.rebuildRadiation();
  }

  setRadiationPitchIndex(pitchIndex: number) {
    this.radiationPitchIndexValue = this.clampedPitchSelection(pitchIndex);
    this.rebuildRadiation();
  }

  /**
   * Accepts a published channel index, `ALL_RADIATION_PITCH_CHANNELS`, or
   * `OMNIDIRECTIONAL_RADIATION_PITCH`.
   *
   * Anything else — including a stale index from a bundle that published more
   * channels — falls back to the omnidirectional integration rather than to any
   * one channel, because no single channel is a fair picture of the population
   * and index 0 is loss cone.
   */
  private clampedPitchSelection(pitchIndex: number | undefined) {
    const pitchGrid = this.runtimeBundle.radiationBelt.pitchCoordinatesSin;
    const fallback = OMNIDIRECTIONAL_RADIATION_PITCH;
    if (pitchIndex === undefined || !Number.isFinite(pitchIndex)) return fallback;
    const rounded = Math.floor(pitchIndex);
    if (rounded === ALL_RADIATION_PITCH_CHANNELS) return ALL_RADIATION_PITCH_CHANNELS;
    if (rounded === OMNIDIRECTIONAL_RADIATION_PITCH) return OMNIDIRECTIONAL_RADIATION_PITCH;
    if (rounded < 0 || rounded >= (pitchGrid?.length ?? 0)) return fallback;
    return rounded;
  }

  setSimulationTime(date: Date) {
    if (this.disposed) return this.stateValue;
    const bracket = this.findBracket(date);
    if (!("lower" in bracket)) {
      this.bracket = null;
      this.stateValue = bracket;
      this.clearVisuals();
      return this.stateValue;
    }
    this.bracket = bracket;
    this.stateValue = {
      status: "ready",
      requestedAt: date.toISOString(),
      sourceFrames: [bracket.lower.frame.validAt, bracket.upper.frame.validAt],
      interpolationFraction: bracket.fraction,
      structureFrameValidAt: bracket.structure.frame.validAt,
      runAt: bracket.structure.frame.runAt,
      leadMinutes: bracket.structure.frame.leadMinutes,
      edgeHoldMinutes: bracket.edgeHoldMinutes,
    };
    this.advectionModelSeconds = date.getTime() / 1000;
    // The belts hang off the DIPOLE, which swings about GSM z by up to ~34
    // degrees over a day and a year. Kept live with the clock rather than
    // frozen at bake time, so scrubbing tilts the belts continuously instead of
    // leaving them pinned to whatever the tilt happened to be when the volume
    // was built.
    this.dipoleTiltRadians = dipoleTilt(date)?.radians ?? null;
    // ...and where the dipole's CENTRE is. Fixed in geographic space, so in
    // this Sun-and-dipole frame it sweeps round once a day — which is exactly
    // what carries the inner belt down over the South Atlantic and back up.
    this.dipoleOffsetSm = eccentricOffsetSm(date);
    this.applyRadiationDipoleTilt();
    this.rebuildCuts();
    this.rebuildPlasmaSheet();
    this.rebuildStructures();
    this.rebuildRadiation();
    return this.stateValue;
  }

  /**
   * Point the belt volume at the dipole.
   *
   * A null tilt hides the volume rather than drawing an untilted one, on
   * `dipole-tilt.ts`'s own instruction: zero tilt is a real and common value,
   * so it must never double as the failure mode. An untilted belt is not a
   * degraded picture, it is a differently wrong one.
   */
  private applyRadiationDipoleTilt() {
    const mesh = this.radiationGroup.getObjectByName("rbe-omnidirectional-flux-volume");
    if (!(mesh instanceof THREE.Mesh)) return;
    const tilt = this.dipoleTiltRadians;
    const offset = this.dipoleOffsetSm;
    // Either one missing hides the layer. A zero offset is a CENTRED dipole and
    // an untilted belt is a differently wrong belt; neither is a degraded
    // picture that can be shown with a caveat.
    mesh.visible = tilt !== null && offset !== null;
    if (tilt !== null) setRadiationVolumeDipoleTilt(mesh, tilt);
    setRadiationVolumeDipoleOffset(mesh, offset);
  }

  setModelAdvectionTime(elapsedModelSeconds: number) {
    if (!Number.isFinite(elapsedModelSeconds)) return;
    this.advectionModelSeconds = elapsedModelSeconds;
    this.updateFlowTracers();
  }

  advanceAdvection(elapsedDisplaySeconds: number) {
    if (!Number.isFinite(elapsedDisplaySeconds)) return;
    this.advectionModelSeconds += elapsedDisplaySeconds * this.modelSecondsPerDisplaySecond;
    this.updateFlowTracers();
  }

  setPixelRatio(pixelRatio: number) {
    const value = Math.max(0.25, pixelRatio);
    this.pixelRatio = value;
    this.cutGroup.traverse((object) => {
      const material = (object as THREE.Points).material;
      if (material instanceof THREE.ShaderMaterial && material.uniforms.pixelRatio) {
        material.uniforms.pixelRatio.value = value;
      }
    });
    this.radiationGroup.traverse((object) => {
      const material = (object as THREE.Points).material;
      if (material instanceof THREE.ShaderMaterial && material.uniforms.pixelRatio) {
        material.uniforms.pixelRatio.value = value;
      }
    });
  }

  /**
   * The group carrying one named region, for callers that want to show the
   * bow shock or the field lines without switching on the whole two-plane
   * plasma presentation. This is the seam a guided walkthrough drives.
   */
  structureRegionGroup(region: GeospaceStructureRegion): THREE.Group {
    switch (region) {
      case "bowShock": return this.bowShockGroup;
      case "magnetosheath": return this.magnetosheathGroup;
      case "magnetopause": return this.magnetopauseProxyGroup;
      case "magneticField": return this.magneticStreamlineGroup;
      case "flowStreamlines": return this.flowStreamlineGroup;
      case "flowTracers": return this.flowAdvectionGroup;
    }
  }

  /** Whether a region has geometry for the selected time. */
  structureRegionAvailable(region: GeospaceStructureRegion): boolean {
    return this.stateValue.status === "ready"
      && this.structureRegionGroup(region).children.length > 0;
  }

  getLegendMetadata(): GeospaceRuntimeLegendMetadata {
    const encoding = this.bundle.fieldEncodings[this.fieldValue];
    const sourceFrames = this.stateValue.status === "ready" ? [...this.stateValue.sourceFrames] : [];
    const radiationDefinition = this.radiationDefinition();
    const emphasisPitchIndex = this.radiationEmphasisPitchIndex;
    const pitch = radiationDefinition?.pitchCoordinatesSin[emphasisPitchIndex];
    const pitchAngle = radiationDefinition?.pitchAnglesDegrees[emphasisPitchIndex];
    // Only the mapped 3-D view has a pitch presentation; the native equatorial
    // surface is one flat sheet of the artifact's own published quantity.
    const pitchPresentation: RadiationPitchPresentation | null = this.radiationViewValue === "dipoleMapped3d"
      ? this.radiationPitchMode
      : null;
    const radiation = radiationDefinition && pitch !== undefined && pitchAngle !== undefined
      ? {
          kind: "rbe" as const,
          // The artifact's own encoding.quantity describes the near-90-degree
          // channel it publishes as the 2-D surface. That is the right caption
          // for the native view and the wrong one for a pitch-integrated volume,
          // even though both ride the same log10 ramp.
          title: pitchPresentation === null
            ? radiationDefinition.encoding.quantity
            : RADIATION_PITCH_PRESENTATION_QUANTITIES[pitchPresentation],
          range: rangeMetadata(
            radiationDefinition.encoding,
            "Values at the encoded endpoints may be exact or saturated; the RBE source artifact does not publish a separate endpoint mask.",
          ),
          energyKev: this.radiationEnergyValue,
          // The combined view has no single energy to print, so it carries its
          // own label and says which integral it is. Every other view repeats
          // its channel energy, so the readout never goes blank.
          energyLabel: isCombinedRadiationEnergy(this.radiationEnergyValue)
            ? `${COMBINED_RADIATION_ENERGY_LABEL.toUpperCase()} · ${
              this.bundle.radiationBelt.energiesKev.length} PUBLISHED CHANNELS, `
              + `${RADIATION_ENERGY_COMBINATION === "energyWeighted" ? "ENERGY-WEIGHTED" : "NUMBER-FLUX"} `
              + "TRAPEZOIDAL BAND AVERAGE 88 keV - 2.32 MeV"
            : null,
          combinedEnergyView: isCombinedRadiationEnergy(this.radiationEnergyValue),
          energyCombination: isCombinedRadiationEnergy(this.radiationEnergyValue)
            ? RADIATION_ENERGY_COMBINATION
            : null,
          // The per-view opacity floor is disclosed wherever the layer speaks,
          // because it decides what is drawn at all in that view.
          opacityFloorLog10Flux: pitchPresentation === "omnidirectional"
            ? this.radiationVolumeOpacityValue?.opacityFloorLog10Flux ?? null
            : null,
          opacityFloorReason: pitchPresentation === "omnidirectional"
            ? this.radiationVolumeOpacityValue?.reason ?? null
            : null,
          opacityFloorSource: pitchPresentation === "omnidirectional"
            ? this.radiationVolumeOpacityValue?.floorSource ?? null
            : null,
          pitchIndex: emphasisPitchIndex,
          pitchCoordinateSin: pitch,
          pitchAngleDegrees: pitchAngle,
          view: this.radiationViewValue,
          viewLabel: pitchPresentation === null
            ? RADIATION_BELT_VIEWS[this.radiationViewValue].label
            : RADIATION_PITCH_PRESENTATION_LABELS[pitchPresentation],
          viewStatus: RADIATION_BELT_VIEWS[this.radiationViewValue].status,
          sourcePitchChannelCount: radiationDefinition.pitchCoordinatesSin.length,
          displayedPitchChannelCount: pitchPresentation === "omnidirectional"
            ? Number(this.radiationGroup.userData.displayedPitchChannelCount ?? 0)
            : this.radiationGroup.children.length,
          selectedPitchEmphasized: this.radiationViewValue === "dipoleMapped3d"
            && this.radiationGroup.children.some((child) => child.userData.selectedPitch === true),
          pitchMode: this.radiationViewValue === "dipoleMapped3d" ? this.radiationPitchMode : "single",
          particlePopulation: "RBE model electrons only" as const,
          representation: RADIATION_BELT_VIEWS[this.radiationViewValue].description,
          alongFieldInterpretation: pitchPresentation === "omnidirectional"
            ? GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.omnidirectionalAlongFieldInterpretation
            : GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.alongFieldInterpretation,
          sourceCoverage: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.sourceCoverage,
          validAt: this.structureFrameValidAt,
        }
      : null;
    return {
      state: this.stateValue,
      field: {
        kind: "swmf-cut",
        field: this.fieldValue,
        title: FIELD_TITLES[this.fieldValue],
        coordinateSystem: this.bundle.coordinateSystem,
        range: rangeMetadata(
          encoding,
          "Separate source-mask bits identify missing, clipped-low, and clipped-high values; smoothing ORs contributing masks and is marked interpolated.",
        ),
        displayMode: this.displayModeValue,
        plane: this.planeValue,
        sourceFrames,
        validCount: this.maskCounts.valid,
        missingCount: this.maskCounts.missing,
        clippedLowCount: this.maskCounts.clippedLow,
        clippedHighCount: this.maskCounts.clippedHigh,
        interpolatedCount: this.maskCounts.interpolated,
        // CORRECTNESS FIX 2026-09-04: not "Observed". BATS-R-US is a
        // magnetohydrodynamic SIMULATION, and `observed` is a load-bearing
        // evidence class on this site — the card's own badge beside this
        // sentence reads NOAA MODEL, and `content.ts` says of this very run
        // "these are somebody's calculation, not somebody's measurement". The
        // sense intended was "the published samples, unresampled", which the
        // rest of the sentence already carries.
        representation: "NOAA operational BATS-R-US model output, read at its own published adaptive-grid samples on the GSM z=0 and y=0 cuts; never a fabricated full volume.",
        fieldPublished: this.fieldPublished,
      },
      radiation,
      structures: {
        kind: "swmf-structure-proxies",
        coordinateSystem: "GSM",
        boundaryStatus: "model-derived-proxies",
        boundaryUnits: "Earth radii (R_E)",
        flowSpeedUnits: "km/s",
        flowSpeedRange: this.flowSpeedRange,
        sheathThicknessRangeRe: this.sheathThicknessRange,
        subsolarBowShockRe: this.subsolarBowShockRe,
        subsolarMagnetopauseRe: this.subsolarMagnetopauseRe,
        structureDisplay: this.structureDisplayValue,
        representation: "Bow-shock and magnetopause cues are raywise transitions derived from the two real model cuts; projected lines use the in-plane B or U vectors. The magnetosheath is the shell between those two boundaries, so it is bounded by published surfaces rather than modelled separately.",
        // "unpublished", not "unobserved": nothing in a simulation grid is
        // observed, and the gap being described is the sectors NOAA does not
        // publish a cut through.
        limitation: "The browser does not fill unpublished sectors, recover dawn-dusk topology, or claim a native 3-D SWMF volume. Nothing is drawn inside the magnetosheath shell: its shocked density, speed and temperature live on the cut planes, not in the region shading.",
        validAt: this.structureFrameValidAt,
      },
    };
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.clearVisuals();
    this.group.removeFromParent();
    this.group.clear();
  }

  private defaultMaximumInterpolationGapMs() {
    const gaps: number[] = [];
    for (let index = 1; index < this.frames.length; index += 1) {
      const gap = this.frames[index]!.timeMs - this.frames[index - 1]!.timeMs;
      if (gap > 0) gaps.push(gap);
    }
    if (gaps.length === 0) return 0;
    gaps.sort((first, second) => first - second);
    const median = gaps[Math.floor(gaps.length / 2)]!;
    return Math.max(median, median * 2.5);
  }

  private noDataState(reason: GeospaceRuntimeNoDataState["reason"], date: Date): GeospaceRuntimeNoDataState {
    return {
      status: "no-data",
      requestedAt: Number.isFinite(date.getTime()) ? date.toISOString() : "invalid",
      reason,
      coverage: {
        validFrom: this.frames[0]?.frame.validAt ?? null,
        validTo: this.frames.at(-1)?.frame.validAt ?? null,
      },
    };
  }

  private findBracket(date: Date): FrameBracket | GeospaceRuntimeNoDataState {
    const requested = date.getTime();
    if (this.frames.length === 0) return this.noDataState("empty-bundle", date);
    if (!Number.isFinite(requested)) return this.noDataState("invalid-frame", date);
    const first = this.frames[0]!;
    const last = this.frames.at(-1)!;
    if (requested < first.timeMs) return this.noDataState("before-coverage", date);
    if (requested > last.timeMs) {
      const ageMs = requested - last.timeMs;
      if (ageMs <= this.operationalEdgeHoldMs) {
        return {
          lower: last,
          upper: last,
          fraction: 0,
          structure: last,
          edgeHoldMinutes: ageMs / 60_000,
        };
      }
      return this.noDataState("after-coverage", date);
    }
    let upperIndex = this.frames.findIndex((entry) => entry.timeMs >= requested);
    if (upperIndex < 0) upperIndex = this.frames.length - 1;
    const upper = this.frames[upperIndex]!;
    const lower = requested === upper.timeMs ? upper : this.frames[Math.max(0, upperIndex - 1)]!;
    const gap = upper.timeMs - lower.timeMs;
    if (gap > this.maximumInterpolationGapMs && requested !== lower.timeMs && requested !== upper.timeMs) {
      return this.noDataState("frame-gap", date);
    }
    const fraction = gap === 0 ? 0 : (requested - lower.timeMs) / gap;
    return { lower, upper, fraction, structure: fraction < 0.5 ? lower : upper, edgeHoldMinutes: 0 };
  }

  private clearVisuals() {
    disposeChildren(this.cutGroup);
    disposeChildren(this.plasmaSheetGroup);
    this.plasmaSheetCountsValue = null;
    this.plasmaSheetMetricsValue = null;
    this.plasmaSheetPublished = false;
    disposeChildren(this.bowShockGroup);
    disposeChildren(this.magnetosheathGroup);
    disposeChildren(this.magnetopauseProxyGroup);
    disposeChildren(this.magneticStreamlineGroup);
    disposeChildren(this.flowStreamlineGroup);
    disposeChildren(this.flowAdvectionGroup);
    disposeChildren(this.radiationGroup);
    this.radiationGeometryKeyValue = null;
    this.maskCounts = emptyMaskCounts();
    this.flowTracers = [];
    this.flowSpeedRange = null;
    this.sheathThicknessRange = null;
    this.subsolarBowShockRe = null;
    this.subsolarMagnetopauseRe = null;
    this.fieldPublished = false;
    this.structureFrameValidAt = null;
    this.group.userData.dataAvailable = false;
  }

  /**
   * One named field of one plane of one frame, decoded and (optionally)
   * resampled onto the display grid.
   *
   * Named rather than implicit because the plasma-sheet layer needs two
   * SPECIFIC fields — pressure and |B| — regardless of which field the
   * magnetosphere layer's picker currently shows.
   */
  private preparedNamedField(
    frame: RuntimeFrame,
    plane: GeospacePlane,
    field: GeospaceField,
    mode: GeospaceSliceDisplayMode,
  ) {
    const planeFrame = frame.planes[plane];
    const masks = planeFrame?.fieldMasksU8?.[field];
    const values = planeFrame?.fieldsU16?.[field];
    if (!masks || !values) return null;
    const encoded: EncodedAdaptivePlaneField = { valuesU16: values, masksU8: masks };
    return prepareAdaptivePlaneField(this.bundle.planes[plane], encoded, {
      ...this.smoothing,
      mode,
    });
  }

  private preparedField(frame: RuntimeFrame, plane: GeospacePlane) {
    return this.preparedNamedField(frame, plane, this.fieldValue, this.displayModeValue);
  }

  /**
   * One named field of one plane, time-interpolated across the bracket exactly
   * as the plasma cut interpolates its own field. `source` is the lower
   * frame's prepared field, which carries the geometry the values belong to.
   */
  private combinedNamedField(plane: GeospacePlane, field: GeospaceField, mode: GeospaceSliceDisplayMode) {
    if (!this.bracket) return null;
    const lower = this.preparedNamedField(this.bracket.lower.frame, plane, field, mode);
    const upper = this.preparedNamedField(this.bracket.upper.frame, plane, field, mode);
    if (!lower || !upper) return null;
    const combined = combinePreparedFields(lower, upper, this.bracket.fraction);
    if (!combined) return null;
    return { source: lower, values: combined.values, masks: combined.masks };
  }

  /** The model-plane coordinates of one sample of a prepared field, in Re. */
  private planeSampleCoordinates(prepared: PreparedAdaptivePlaneField, index: number): [number, number] {
    if (prepared.mode === "native") {
      return [prepared.coordinates[index * 2] ?? 0, prepared.coordinates[index * 2 + 1] ?? 0];
    }
    const [minimumX, maximumX, minimumCross, maximumCross] = prepared.boundsRe;
    const column = index % prepared.width;
    const row = Math.floor(index / prepared.width);
    return [
      minimumX + (prepared.width > 1 ? (column * (maximumX - minimumX)) / (prepared.width - 1) : 0),
      minimumCross + (prepared.height > 1 ? (row * (maximumCross - minimumCross)) / (prepared.height - 1) : 0),
    ];
  }

  /**
   * Whether a sample falls inside the embedded-cross-section extent.
   *
   * Presentation only: it clips what is DRAWN so a cut reads as a slice
   * through the 3-D scene rather than a wall behind it. Every reported count
   * and every measurement still describes the whole published grid.
   */
  private withinCutExtent(prepared: PreparedAdaptivePlaneField, index: number) {
    if (!this.cutExtentRe) return true;
    const [xRe, crossRe] = this.planeSampleCoordinates(prepared, index);
    return xRe >= this.cutExtentRe.minimumXRe && Math.abs(crossRe) <= this.cutExtentRe.maximumCrossRe;
  }

  private positionsForPrepared(prepared: PreparedAdaptivePlaneField, plane: GeospacePlane) {
    const positions = new Float32Array(prepared.values.length * 3);
    if (prepared.mode === "native") {
      for (let index = 0; index < prepared.values.length; index += 1) {
        this.positionForPlane(
          prepared.coordinates[index * 2]!,
          prepared.coordinates[index * 2 + 1]!,
          plane,
        ).toArray(positions, index * 3);
      }
      return positions;
    }
    const [minimumX, maximumX, minimumCross, maximumCross] = prepared.boundsRe;
    const xStep = prepared.width > 1 ? (maximumX - minimumX) / (prepared.width - 1) : 0;
    const crossStep = prepared.height > 1 ? (maximumCross - minimumCross) / (prepared.height - 1) : 0;
    for (let row = 0; row < prepared.height; row += 1) {
      for (let column = 0; column < prepared.width; column += 1) {
        const index = row * prepared.width + column;
        this.positionForPlane(minimumX + column * xStep, minimumCross + row * crossStep, plane)
          .toArray(positions, index * 3);
      }
    }
    return positions;
  }

  private rebuildCuts() {
    disposeChildren(this.cutGroup);
    this.maskCounts = emptyMaskCounts();
    this.fieldPublished = false;
    if (!this.bracket) return;
    // Whether the bracketing frames carry the field at all, judged across
    // every plane rather than only the selected one: an archived frame that
    // publishes no field publishes it for neither plane, and the legend's
    // "no field in this frame" message must not flicker with the plane picker.
    const framePublishesField = (frame: RuntimeFrame) => PLANES.some((plane) =>
      Boolean(frame.planes?.[plane]?.fieldsU16?.[this.fieldValue]));
    this.fieldPublished = framePublishesField(this.bracket.lower.frame)
      && framePublishesField(this.bracket.upper.frame);
    PLANES.forEach((plane) => {
      if (this.planeValue !== "both" && this.planeValue !== plane) return;
      const lower = this.preparedField(this.bracket!.lower.frame, plane);
      const upper = this.preparedField(this.bracket!.upper.frame, plane);
      if (!lower || !upper) return;
      const combined = combinePreparedFields(lower, upper, this.bracket!.fraction);
      if (!combined) return;
      addMaskCounts(this.maskCounts, combined.masks);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(this.positionsForPrepared(lower, plane), 3));
      geometry.setAttribute("fieldValue", new THREE.BufferAttribute(combined.values, 1));
      geometry.setAttribute("sourceMask", new THREE.Uint8BufferAttribute(combined.masks, 1));
      // Validity for RENDERING: real data presence ANDed with the optional
      // display extent. The extent clips what is drawn — an embedded
      // cross-section stops at the boundary region — while the legend's mask
      // counts, taken from `combined.masks` above, keep describing the whole
      // published grid.
      const withinExtent = (index: number) => this.withinCutExtent(lower, index);
      geometry.setAttribute("dataValid", new THREE.Uint8BufferAttribute(
        Uint8Array.from(combined.masks, (mask, index) =>
          (mask & GEOSPACE_SLICE_MASK.missing) === 0 && withinExtent(index) ? 1 : 0),
        1,
      ));
      geometry.setAttribute("saturation", new THREE.Int8BufferAttribute(
        Int8Array.from(combined.masks, (mask) => {
          if ((mask & GEOSPACE_SLICE_MASK.clippedHigh) !== 0) return 1;
          if ((mask & GEOSPACE_SLICE_MASK.clippedLow) !== 0) return -1;
          return 0;
        }),
        1,
      ));
      const userData = {
        plane,
        field: this.fieldValue,
        mode: this.displayModeValue,
        source: "NOAA operational BATS-R-US published cut",
      };
      if (this.displayModeValue === "smooth" && lower.mode === "smooth") {
        // The filled field: the regular grid triangulated wherever every
        // corner is a supported sample. This is where the bow shock, the
        // magnetosheath and the magnetopause appear — as structure in the
        // model's own published fields, not as drawn overlays.
        const validity = geometry.getAttribute("dataValid") as THREE.BufferAttribute;
        geometry.setIndex(smoothGridIndices(lower.width, lower.height, validity.array as Uint8Array));
        const mesh = new THREE.Mesh(geometry, fieldSurfaceMaterial(this.fieldValue));
        mesh.name = `swmf-${plane}-${this.fieldValue}-${this.displayModeValue}`;
        mesh.frustumCulled = false;
        // The boundary-annotation curves are drawn in the same plane as the
        // field they annotate. Coplanar transparent objects have no reliable
        // depth order, so the field explicitly renders first: the annotation
        // must read over the field, never be buried under it.
        mesh.renderOrder = -2;
        mesh.userData = userData;
        this.cutGroup.add(mesh);
      } else {
        const material = fieldPointMaterial(this.fieldValue, 2.6, this.pixelRatio);
        const points = new THREE.Points(geometry, material);
        points.name = `swmf-${plane}-${this.fieldValue}-${this.displayModeValue}`;
        points.frustumCulled = false;
        points.userData = userData;
        this.cutGroup.add(points);
      }
    });
    this.group.userData.dataAvailable = this.cutGroup.children.length > 0;
  }

  /**
   * The plasma sheet, drawn as the plasma-beta field the published pressure
   * and |B| cuts already contain.
   *
   * Three things go into the group, in decreasing order of how much they
   * claim:
   *
   *  1. the beta FIELD itself, over the whole cut — a straight ratio of two
   *     published model values at every point, with the ramp's pale band on
   *     beta = 1 so the sheet, the lobes and the shocked sheath separate by
   *     colour alone;
   *  2. the traced beta = 1 curve, which is the conventional plasma-sheet
   *     boundary and is labelled as a convention on the card;
   *  3. the measured centre line: the locus of maximum beta, column by column
   *     down the tail. Under a tilted dipole it does not lie on z = 0, and
   *     that is the point of drawing it.
   *
   * Nothing is drawn where the model published nothing, and the measurement in
   * (3) refuses rather than approximates when the display grid it needs is not
   * the one on screen.
   */
  private rebuildPlasmaSheet() {
    disposeChildren(this.plasmaSheetGroup);
    this.plasmaSheetCountsValue = null;
    this.plasmaSheetMetricsValue = null;
    this.plasmaSheetPublished = false;
    if (!this.bracket || !this.plasmaSheetEnabledValue) return;
    const framePublishesBeta = (frame: RuntimeFrame) => PLANES.some((plane) =>
      Boolean(frame.planes?.[plane]?.fieldsU16?.pressure)
      && Boolean(frame.planes?.[plane]?.fieldsU16?.magneticField));
    this.plasmaSheetPublished = framePublishesBeta(this.bracket.lower.frame)
      && framePublishesBeta(this.bracket.upper.frame);
    if (!this.plasmaSheetPublished) return;

    const encodings = {
      pressure: this.bundle.fieldEncodings.pressure,
      magneticField: this.bundle.fieldEncodings.magneticField,
    };
    /** The beta field of one plane, in one display mode, or null. */
    const betaFor = (plane: GeospacePlane, mode: GeospaceSliceDisplayMode) => {
      const pressure = this.combinedNamedField(plane, "pressure", mode);
      const magnetic = this.combinedNamedField(plane, "magneticField", mode);
      if (!pressure || !magnetic) return null;
      const beta = plasmaBetaPlaneField(pressure, magnetic, encodings);
      return beta ? { source: pressure.source, beta } : null;
    };

    let measurementGrid: { source: SmoothedAdaptivePlaneField; beta: PlasmaBetaPlaneField } | null = null;
    const counts: PlasmaBetaCounts[] = [];

    PLANES.forEach((plane) => {
      if (this.plasmaSheetPlaneValue !== "both" && this.plasmaSheetPlaneValue !== plane) return;
      const computed = betaFor(plane, this.displayModeValue);
      if (!computed) return;
      const { source, beta } = computed;
      counts.push(beta.counts);
      if (plane === "meridional" && isSmoothPlaneField(source)) measurementGrid = { source, beta };

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(this.positionsForPrepared(source, plane), 3));
      geometry.setAttribute("fieldValue", new THREE.BufferAttribute(beta.values, 1));
      geometry.setAttribute("dataValid", new THREE.Uint8BufferAttribute(
        Uint8Array.from(beta.masks, (mask, index) =>
          (mask & GEOSPACE_SLICE_MASK.missing) === 0 && this.withinCutExtent(source, index) ? 1 : 0),
        1,
      ));
      const userData = {
        plane,
        quantity: "plasma beta",
        derivedFrom: ["pressure", "magneticField"],
        source: "NOAA operational BATS-R-US published cut",
      };
      if (this.displayModeValue === "smooth" && source.mode === "smooth") {
        const validity = geometry.getAttribute("dataValid") as THREE.BufferAttribute;
        geometry.setIndex(smoothGridIndices(source.width, source.height, validity.array as Uint8Array));
        const mesh = new THREE.Mesh(geometry, plasmaBetaSurfaceMaterial());
        mesh.name = `plasma-beta-${plane}-smooth`;
        mesh.frustumCulled = false;
        // Deterministic in the coplanar stack: above the magnetosphere
        // layer's own MHD cut (-2), below the boundary annotations (0) and
        // below this layer's own two curves (1 and 2). Both cuts are
        // transparent with depth writes off, so equal render orders would
        // blend them in whatever order three.js happened to pick.
        mesh.renderOrder = -1;
        mesh.userData = userData;
        this.plasmaSheetGroup.add(mesh);
      } else {
        const points = new THREE.Points(geometry, plasmaBetaPointMaterial(2.6, this.pixelRatio));
        points.name = `plasma-beta-${plane}-native`;
        points.frustumCulled = false;
        points.userData = userData;
        this.plasmaSheetGroup.add(points);
      }

      if (source.mode === "smooth") {
        const [contour] = contourAdaptivePlaneField(
          betaContourSource(source, beta),
          [PLASMA_SHEET_CONTOUR_LEVEL],
        );
        if (contour && contour.coordinates.length >= 4) {
          const kept: number[] = [];
          for (let index = 0; index + 3 < contour.coordinates.length; index += 4) {
            const x0 = contour.coordinates[index]!;
            const cross0 = contour.coordinates[index + 1]!;
            const x1 = contour.coordinates[index + 2]!;
            const cross1 = contour.coordinates[index + 3]!;
            if (this.cutExtentRe) {
              const inside = (x: number, cross: number) =>
                x >= this.cutExtentRe!.minimumXRe && Math.abs(cross) <= this.cutExtentRe!.maximumCrossRe;
              if (!inside(x0, cross0) || !inside(x1, cross1)) continue;
            }
            this.positionForPlane(x0, cross0, plane).toArray(kept, kept.length);
            this.positionForPlane(x1, cross1, plane).toArray(kept, kept.length);
          }
          if (kept.length >= 6) {
            const boundaryGeometry = new THREE.BufferGeometry();
            boundaryGeometry.setAttribute("position", new THREE.Float32BufferAttribute(kept, 3));
            const boundary = new THREE.LineSegments(boundaryGeometry, new THREE.LineBasicMaterial({
              color: PLASMA_SHEET_LINE_COLORS.boundary,
              transparent: true,
              opacity: 0.9,
              depthWrite: false,
            }));
            boundary.name = `plasma-beta-one-contour-${plane}`;
            boundary.frustumCulled = false;
            boundary.renderOrder = 1;
            boundary.userData = { plane, quantity: "plasma beta = 1 contour" };
            this.plasmaSheetGroup.add(boundary);
          }
        }
      }
    });

    // The measurement always wants the meridional plane on the regular display
    // grid, whichever plane is currently drawn and whichever display mode is
    // selected — the sheet's thickness is a noon-midnight quantity, and the
    // equatorial cut cannot report it at all. When the drawn presentation
    // already produced that grid it is reused; otherwise it is prepared once
    // more here rather than left unmeasured.
    let measurement: { source: SmoothedAdaptivePlaneField; beta: PlasmaBetaPlaneField } | null = measurementGrid;
    if (!measurement) {
      const computed = betaFor("meridional", "smooth");
      if (computed && isSmoothPlaneField(computed.source)) {
        measurement = { source: computed.source, beta: computed.beta };
        if (counts.length === 0) counts.push(computed.beta.counts);
      }
    }
    if (measurement) {
      const grid = {
        width: measurement.source.width,
        height: measurement.source.height,
        boundsRe: measurement.source.boundsRe,
        log10Beta: measurement.beta.log10Beta,
      };
      const columns = plasmaSheetColumns(grid, PLASMA_SHEET_MEASUREMENT_WINDOW);
      this.plasmaSheetMetricsValue = plasmaSheetMetrics(
        columns,
        PLASMA_SHEET_REFERENCE_X_RE,
        PLASMA_SHEET_MEASUREMENT_WINDOW,
      );
      const centre: number[] = [];
      columns.forEach((column) => {
        if (column.halfThicknessRe === null) return;
        this.positionForPlane(column.xRe, column.centreCrossRe, "meridional").toArray(centre, centre.length);
      });
      if (centre.length >= 6 && this.plasmaSheetPlaneValue !== "equatorial") {
        const centreGeometry = new THREE.BufferGeometry();
        centreGeometry.setAttribute("position", new THREE.Float32BufferAttribute(centre, 3));
        const line = new THREE.Line(centreGeometry, new THREE.LineBasicMaterial({
          color: PLASMA_SHEET_LINE_COLORS.centre,
          transparent: true,
          opacity: 0.95,
          depthWrite: false,
        }));
        line.name = "plasma-sheet-measured-centre";
        line.frustumCulled = false;
        line.renderOrder = 2;
        line.userData = { quantity: "locus of maximum plasma beta", plane: "meridional" };
        this.plasmaSheetGroup.add(line);
      }
    }

    this.plasmaSheetCountsValue = counts.length === 0 ? null : counts.reduce((total, entry) => ({
      valid: total.valid + entry.valid,
      missing: total.missing + entry.missing,
      sourceBounded: total.sourceBounded + entry.sourceBounded,
      displayClamped: total.displayClamped + entry.displayClamped,
      interpolated: total.interpolated + entry.interpolated,
      aboveThreshold: total.aboveThreshold + entry.aboveThreshold,
    }));
  }

  /**
   * What the plasma-sheet layer's key card prints. Never throws and never
   * invents: every field is either a measured number or an explicit null with
   * a state the card can name.
   */
  getPlasmaSheetLegendMetadata(): PlasmaSheetLegendMetadata {
    return {
      kind: "swmf-derived-plasma-beta",
      coordinateSystem: this.bundle.coordinateSystem,
      betaPublished: this.plasmaSheetPublished,
      plane: this.plasmaSheetPlaneValue,
      displayMode: this.displayModeValue,
      logRange: PLASMA_SHEET_BETA_LOG_RANGE,
      threshold: PLASMA_SHEET_BETA_THRESHOLD,
      units: "dimensionless",
      counts: this.plasmaSheetCountsValue,
      metrics: this.plasmaSheetMetricsValue,
      metricsAvailable: this.plasmaSheetMetricsValue !== null,
      representation: PLASMA_SHEET_REPRESENTATION,
      limitation: PLASMA_SHEET_LIMITATION,
      sourceFrames: this.stateValue.status === "ready" ? [...this.stateValue.sourceFrames] : [],
      validAt: this.stateValue.status === "ready" ? this.stateValue.structureFrameValidAt : null,
    };
  }

  private rebuildStructures() {
    disposeChildren(this.bowShockGroup);
    disposeChildren(this.magnetosheathGroup);
    disposeChildren(this.magnetopauseProxyGroup);
    disposeChildren(this.magneticStreamlineGroup);
    disposeChildren(this.flowStreamlineGroup);
    disposeChildren(this.flowAdvectionGroup);
    this.flowTracers = [];
    this.flowSpeedRange = null;
    this.sheathThicknessRange = null;
    this.subsolarBowShockRe = null;
    this.subsolarMagnetopauseRe = null;
    this.structureFrameValidAt = null;
    if (!this.bracket) return;
    const definition = this.runtimeBundle.structures;
    const frame = this.bracket.structure.frame;
    if (!definition || !frame.structures) return;
    this.structureFrameValidAt = frame.validAt;

    // The two nose radii on the subsolar ray, straight from the published
    // meridional profiles. They are the storm-compression numbers: the same
    // pair a reader can watch fall across the 48 h replay.
    const subsolarIndex = definition.anglesDegrees.reduce(
      (nearest, angle, index) =>
        Math.abs(angle) < Math.abs(definition.anglesDegrees[nearest] ?? Number.POSITIVE_INFINITY) ? index : nearest,
      0,
    );
    if (Math.abs(definition.anglesDegrees[subsolarIndex] ?? 90) <= 5) {
      const meridional = frame.structures.meridional;
      this.subsolarBowShockRe =
        decodeBoundaryProfile(definition, meridional.bowShockRadiusU16)[subsolarIndex] ?? null;
      this.subsolarMagnetopauseRe =
        decodeBoundaryProfile(definition, meridional.magnetopauseProxyRadiusU16)[subsolarIndex] ?? null;
    }

    if (this.structureDisplayValue === "surface") {
      (["bowShock", "magnetopauseProxy"] as const).forEach((kind) => {
        const geometry = createLoftedBoundaryGeometry(definition, frame.structures!, kind, this.positionForGsm, 40);
        // Drawn at 0.13 opacity the bow shock was in the scene and unfindable;
        // these are the weights at which each surface can actually be seen.
        const material = new THREE.MeshBasicMaterial({
          color: kind === "bowShock" ? GEOSPACE_BOUNDARY_COLORS.bowShock : GEOSPACE_BOUNDARY_COLORS.magnetopauseProxy,
          transparent: true,
          opacity: kind === "bowShock" ? 0.34 : 0.3,
          side: THREE.DoubleSide,
          depthWrite: false,
          wireframe: true,
        });
        const mesh = new THREE.Mesh(geometry, material);
        // The edge of the cap. Without it a translucent shell that simply stops
        // reads, from an oblique camera, as two disconnected patches rather than
        // as one surface with a boundary — which is exactly what Sean saw. A
        // boundary that stops should look like it stops.
        const rim = createBoundaryRimGeometry(definition, frame.structures!, kind, this.positionForGsm);
        if (rim) {
          const rimLine = new THREE.LineLoop(
            rim.geometry,
            new THREE.LineBasicMaterial({
              color: kind === "bowShock" ? GEOSPACE_BOUNDARY_COLORS.bowShock : GEOSPACE_BOUNDARY_COLORS.magnetopauseProxy,
              transparent: true,
              opacity: 0.85,
              depthWrite: false,
            }),
          );
          rimLine.name = `${kind}-published-edge`;
          rimLine.userData = { thetaDegrees: rim.thetaDegrees, why: rim.geometry.userData.why };
          (kind === "bowShock" ? this.bowShockGroup : this.magnetopauseProxyGroup).add(rimLine);
        }
        mesh.name = kind === "bowShock" ? "model-derived-bow-shock-proxy" : "model-derived-magnetopause-proxy";
        mesh.userData = {
          status: "model-derived-two-cut-loft",
          units: "Earth radii (R_E)",
          fullVolume: false,
          region: kind === "bowShock" ? "bowShock" : "magnetopause",
        };
        (kind === "bowShock" ? this.bowShockGroup : this.magnetopauseProxyGroup).add(mesh);
      });

      // The magnetosheath is not a separate model. It is defined as the region
      // between the bow shock and the magnetopause, and both of those are
      // published, so the shell between them is derived rather than invented.
      // It exists only where both profiles are independently supported;
      // missing sectors stay holes.
      const sheath = new THREE.Mesh(
        createMagnetosheathGeometry(definition, frame.structures, this.positionForGsm, 40),
        new THREE.MeshBasicMaterial({
          color: GEOSPACE_BOUNDARY_COLORS.magnetosheath,
          transparent: true,
          opacity: 0.075,
          side: THREE.DoubleSide,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      );
      sheath.name = "model-derived-magnetosheath-region";
      sheath.renderOrder = -1;
      sheath.userData = {
        status: "region-between-two-model-derived-boundaries",
        region: "magnetosheath",
        derivation: "the shell between the published bow-shock and magnetopause profiles",
        notAField: "no plasma quantity is drawn inside it; the cut planes carry the measured fields",
      };
      this.magnetosheathGroup.add(sheath);
    } else {
      this.buildCrossSectionStructures(definition, frame.structures);
    }

    const allSpeeds: number[] = [];
    PLANES.forEach((plane) => {
      if (this.planeValue !== "both" && this.planeValue !== plane) return;
      const structures = frame.structures![plane];
      const magnetic = createProjectedLineSegmentsGeometry(
        definition,
        structures.projectedMagneticStreamlines,
        plane,
        this.positionForPlane,
      );
      const magneticLines = new THREE.LineSegments(
        magnetic,
        new THREE.LineBasicMaterial({ color: 0xbba6ff, transparent: true, opacity: 0.72, depthWrite: false }),
      );
      magneticLines.name = `projected-magnetic-${plane}`;
      magneticLines.userData = {
        plane,
        status: "in-plane-vector-projection",
        fullFieldLine: false,
        region: "magneticField",
      };
      this.magneticStreamlineGroup.add(magneticLines);

      const velocity = createProjectedLineSegmentsGeometry(
        definition,
        structures.projectedFlowStreamlines,
        plane,
        this.positionForPlane,
      );
      const velocityLines = new THREE.LineSegments(
        velocity,
        new THREE.LineBasicMaterial({ color: 0x76e6a5, transparent: true, opacity: 0.46, depthWrite: false }),
      );
      velocityLines.name = `projected-bulk-flow-${plane}`;
      velocityLines.userData = {
        plane,
        status: "in-plane-vector-projection",
        units: "km/s",
        region: "flowStreamlines",
      };
      this.flowStreamlineGroup.add(velocityLines);

      const paths = buildProjectedFlowAdvectionPaths(definition, structures.projectedFlowStreamlines);
      paths.forEach((path) => {
        path.speedKps.forEach((speed) => allSpeeds.push(speed));
        for (let tracerIndex = 0; tracerIndex < 3; tracerIndex += 1) {
          this.flowTracers.push({ path, plane, phase: tracerIndex / 3 });
        }
      });
    });
    if (allSpeeds.length > 0) this.flowSpeedRange = [Math.min(...allSpeeds), Math.max(...allSpeeds)];
    this.buildFlowTracers();
  }

  /**
   * The same three regions, drawn as curves in the planes they were published
   * in rather than as closed shells.
   *
   * This is the geometry every printed cross-section of this system uses, and
   * it is what makes bow shock, magnetosheath and magnetopause read as three
   * separate things instead of one translucent blob.
   */
  private buildCrossSectionStructures(
    definition: GeospaceStructuresDefinition,
    frame: EncodedFrameStructures,
  ) {
    const sheathRange: Array<number> = [];
    PLANES.forEach((plane) => {
      if (this.planeValue !== "both" && this.planeValue !== plane) return;
      (["bowShock", "magnetopauseProxy"] as const).forEach((kind) => {
        const geometry = createBoundaryProfileCurveGeometry(
          definition,
          frame,
          kind,
          plane,
          this.positionForPlane,
        );
        if (!geometry) return;
        const line = new THREE.LineSegments(
          geometry,
          new THREE.LineBasicMaterial({
            color: kind === "bowShock" ? GEOSPACE_BOUNDARY_COLORS.bowShock : GEOSPACE_BOUNDARY_COLORS.magnetopauseProxy,
            transparent: true,
            opacity: kind === "bowShock" ? 0.92 : 0.85,
            depthWrite: false,
          }),
        );
        line.name = kind === "bowShock"
          ? `model-derived-bow-shock-curve-${plane}`
          : `model-derived-magnetopause-curve-${plane}`;
        line.userData = {
          plane,
          region: kind === "bowShock" ? "bowShock" : "magnetopause",
          status: "published-profile-in-its-own-cut-plane",
          angleRangeDegrees: geometry.userData.angleRangeDegrees,
          units: "Earth radii (R_E)",
        };
        (kind === "bowShock" ? this.bowShockGroup : this.magnetopauseProxyGroup).add(line);
      });

      const ribbon = createMagnetosheathRibbonGeometry(definition, frame, plane, this.positionForPlane);
      if (!ribbon) return;
      const thickness = ribbon.getAttribute("sheathThicknessRe");
      for (let index = 0; index < thickness.count; index += 1) sheathRange.push(thickness.getX(index));
      const mesh = new THREE.Mesh(
        ribbon,
        new THREE.MeshBasicMaterial({
          color: GEOSPACE_BOUNDARY_COLORS.magnetosheath,
          transparent: true,
          opacity: 0.2,
          side: THREE.DoubleSide,
          depthWrite: false,
        }),
      );
      mesh.name = `model-derived-magnetosheath-band-${plane}`;
      mesh.renderOrder = -1;
      mesh.userData = {
        plane,
        region: "magnetosheath",
        status: "region-between-two-published-profiles",
        derivation: "published bow-shock radius minus published magnetopause radius, at each published angle",
        notAField: "no plasma quantity is drawn inside it; the cut planes carry the measured fields",
      };
      this.magnetosheathGroup.add(mesh);
    });
    this.sheathThicknessRange = sheathRange.length > 0
      ? [Math.min(...sheathRange), Math.max(...sheathRange)]
      : null;
  }

  private buildFlowTracers() {
    if (this.flowTracers.length === 0) return;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(this.flowTracers.length * 3), 3));
    geometry.setAttribute("flowSpeedKps", new THREE.BufferAttribute(new Float32Array(this.flowTracers.length), 1));
    const material = new THREE.PointsMaterial({
      color: 0x9fefff,
      size: 2.4 * this.pixelRatio,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0.78,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, material);
    points.name = "model-time-advected-bulk-flow-tracers";
    points.frustumCulled = false;
    points.userData = {
      status: "frozen-frame-projected-flow-advection",
      speedUnits: "km/s",
      particleTrajectory: false,
    };
    this.flowAdvectionGroup.add(points);
    this.updateFlowTracers();
  }

  private updateFlowTracers() {
    const points = this.flowAdvectionGroup.children[0] as THREE.Points | undefined;
    const positions = points?.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    const speeds = points?.geometry.getAttribute("flowSpeedKps") as THREE.BufferAttribute | undefined;
    if (!positions || !speeds) return;
    this.flowTracers.forEach((tracer, index) => {
      const sample = sampleProjectedFlowAdvectionPath(
        tracer.path,
        this.advectionModelSeconds + tracer.phase * tracer.path.durationModelSeconds,
      );
      if (!sample) return;
      const position = this.positionForPlane(sample.xRe, sample.crossRe, tracer.plane);
      positions.setXYZ(index, position.x, position.y, position.z);
      speeds.setX(index, sample.speedKps);
    });
    positions.needsUpdate = true;
    speeds.needsUpdate = true;
  }

  private radiationDefinition(): RadiationBeltDefinition | null {
    const definition = this.runtimeBundle.radiationBelt;
    if (
      !definition.pitchCoordinatesSin
      || !definition.pitchAnglesDegrees
      || !definition.pitchResolvedOrdering
      || definition.innerBoundaryRe === undefined
    ) return null;
    return definition as RadiationBeltDefinition;
  }

  /**
   * Everything the rendered radiation geometry actually depends on.
   *
   * RBE is not interpolated between frames the way the cut planes are: the
   * shells are built from the structure frame alone, so the bracket fraction
   * is deliberately absent from this key.
   */
  private radiationGeometryKey(): string | null {
    if (!this.bracket) return null;
    if (!this.radiationDefinition()) return null;
    return [
      this.bracket.structure.frame.validAt,
      this.radiationViewValue,
      this.radiationEnergyValue,
      this.radiationPitchIndexValue,
    ].join("|");
  }

  /**
   * Rebuild the radiation shells, but only when their inputs have changed.
   *
   * setSimulationTime calls this on every accepted time step — every five
   * simulated seconds — while RBE snaps to twenty-minute frames, so almost
   * every call used to dispose and recreate eleven concentric translucent
   * meshes that came out identical. Those meshes are all centred on the
   * origin, so three.js cannot separate them by depth and falls back to
   * object id for transparent draw order; recreating them hands out fresh
   * ids and re-decides that order against every other rebuilt translucent
   * layer in the scene.
   */
  private rebuildRadiation() {
    const key = this.radiationGeometryKey();
    if (key !== null && key === this.radiationGeometryKeyValue) return;
    this.radiationGeometryKeyValue = key;
    disposeChildren(this.radiationGroup);
    this.radiationGroup.userData = {};
    this.radiationVolumeOpacityValue = null;
    if (!this.bracket) return;
    const publishedDefinition = this.radiationDefinition();
    if (!publishedDefinition) return;
    const publishedFrame = this.bracket.structure.frame.radiationBelt;
    // The combined view is folded into a synthetic single-channel artifact
    // here, once, before any presentation looks at it. Every presentation the
    // layer offers therefore draws it by exactly the code path it draws a
    // published channel with, and none of them needs to know the difference.
    let definition = publishedDefinition;
    let sourceFrame = publishedFrame;
    if (isCombinedRadiationEnergy(this.radiationEnergyValue)) {
      if (!publishedFrame.pitchResolvedElectronFluxU16) return;
      const combined = combineRadiationEnergyChannels(
        publishedDefinition,
        {
          coordinatesU16: publishedFrame.coordinatesU16,
          electronFluxU16: publishedFrame.electronFluxU16,
          pitchResolvedElectronFluxU16: publishedFrame.pitchResolvedElectronFluxU16,
        },
        RADIATION_ENERGY_COMBINATION,
      );
      definition = combined.definition;
      sourceFrame = combined.frame;
    }
    // The native equatorial view is a single flat surface, so "all channels" is
    // not a thing it can draw; it falls back to the emphasized channel.
    const emphasisPitchIndex = this.radiationEmphasisPitchIndex;
    if (this.radiationViewValue === "nativeEquatorial") {
      const selected = selectedPitchFrame(
        definition,
        sourceFrame,
        this.radiationEnergyValue,
        emphasisPitchIndex,
      );
      if (!selected) return;
      const geometry = createNativeEquatorialRadiationGeometry(
        selected.definition,
        selected.frame,
        this.radiationEnergyValue,
        this.positionForRadiation,
      );
      const mesh = new THREE.Mesh(geometry, radiationSurfaceMaterial());
      mesh.name = "rbe-model-native-equatorial-flux";
      mesh.frustumCulled = false;
      mesh.userData = {
        ...geometry.userData,
        ...RADIATION_BELT_VIEWS.nativeEquatorial,
        energyKev: this.radiationEnergyValue,
        pitchIndex: emphasisPitchIndex,
        selectedPitch: true,
        sourcePitchChannelCount: definition.pitchCoordinatesSin.length,
        displayedPitchChannelCount: 1,
        fullNative3d: false,
      };
      this.radiationGroup.userData = {
        representation: geometry.userData.representation,
        sourcePitchChannelCount: definition.pitchCoordinatesSin.length,
        displayedPitchChannelCount: 1,
        selectedPitchEmphasized: false,
      };
      this.radiationGroup.add(mesh);
      return;
    }

    if (!sourceFrame.pitchResolvedElectronFluxU16) return;
    const fullFrame: RadiationBeltFrame = {
      coordinatesU16: sourceFrame.coordinatesU16,
      electronFluxU16: sourceFrame.electronFluxU16,
      pitchResolvedElectronFluxU16: sourceFrame.pitchResolvedElectronFluxU16,
    };

    if (this.radiationPitchMode === "omnidirectional") {
      this.buildOmnidirectionalRadiationVolume(definition, fullFrame);
      return;
    }

    if (this.radiationPitchMode === "single") {
      this.buildSingleRadiationPitchShell(definition, fullFrame, emphasisPitchIndex);
      return;
    }

    const reconstruction = createGyrotropicDipoleMappedRadiationShells(
      definition,
      fullFrame,
      this.radiationEnergyValue,
      {
        // Six latitude rows per hemisphere: smoother silhouettes than the
        // original four without tripling the vertex count of twelve stacked
        // translucent shells.
        samplesPerHemisphere: 6,
        pointStride: 1,
        includeMirrorCaps: false,
        positionForGsm: this.positionForRadiation,
      },
    );
    const selectedPitchEmphasized = reconstruction.shells.some(
      (shell) => shell.pitchIndex === emphasisPitchIndex,
    );
    this.radiationGroup.userData = {
      ...reconstruction.metadata,
      pitchMode: "all",
      selectedPitchIndex: emphasisPitchIndex,
      selectedPitchEmphasized,
    };
    const orderedShells = [...reconstruction.shells].sort((first, second) => {
      const firstSelected = first.pitchIndex === emphasisPitchIndex ? 1 : 0;
      const secondSelected = second.pitchIndex === emphasisPitchIndex ? 1 : 0;
      return firstSelected - secondSelected || first.pitchIndex - second.pitchIndex;
    });
    orderedShells.forEach((shell) => {
      const selectedPitch = shell.pitchIndex === emphasisPitchIndex;
      const opacityScale = selectedPitch
        ? 1
        : THREE.MathUtils.clamp(0.18 + 0.36 * Math.sqrt(shell.solidAngleWeight), 0.22, 0.48);
      const mesh = new THREE.Mesh(
        shell.geometry,
        radiationSurfaceMaterial(opacityScale, selectedPitch ? 1 : 0, true),
      );
      mesh.name = `rbe-gyrotropic-dipole-pitch-shell-${shell.pitchIndex}`;
      mesh.frustumCulled = false;
      mesh.renderOrder = selectedPitch ? 20 : 10;
      mesh.userData = {
        ...shell.geometry.userData,
        ...RADIATION_BELT_VIEWS.dipoleMapped3d,
        energyKev: this.radiationEnergyValue,
        pitchIndex: shell.pitchIndex,
        pitchCoordinateSin: shell.equatorialPitchSin,
        pitchAngleDegrees: shell.equatorialPitchAngleDegrees,
        solidAngleWeight: shell.solidAngleWeight,
        mirrorLatitudeDegrees: shell.mirrorLatitudeDegrees,
        selectedPitch,
        opacityScale,
        fullNative3d: false,
      };
      this.radiationGroup.add(mesh);
    });
  }

  /**
   * The shipped mapped-3-D presentation: omnidirectional differential electron
   * flux, rendered volumetrically.
   *
   * This used to extract an iso-surface — the closed envelope of everywhere the
   * integrated flux cleared the display floor. That envelope's reach was set by
   * whichever trapped channel still cleared the floor, so near-loss-cone
   * channels holding half a percent of the solid angle inflated it into a
   * faceted balloon that swallowed the poles and visually closed the slot. Now
   * the field itself is raymarched: opacity tracks the local flux, low-flux
   * regions are simply transparent, and the belts, the slot, and their merging
   * at low energy all emerge from the data instead of from a threshold.
   *
   * A few centered-dipole field lines — the mapping's own assumed geometry —
   * are drawn through the volume for orientation, as the classic Van Allen
   * Probes renderings do.
   */
  private buildOmnidirectionalRadiationVolume(
    definition: RadiationBeltDefinition,
    frame: RadiationBeltFrame,
  ) {
    const { mesh, bake, opacity } = createRadiationVolumeMesh(
      definition,
      frame,
      this.radiationEnergyValue,
      this.positionForRadiation,
    );
    // The floor this view is drawn with was just derived from this dataset's
    // own baked field; the readout quotes exactly that, never the table.
    this.radiationVolumeOpacityValue = opacity;
    this.radiationGroup.userData = {
      ...mesh.userData,
      pitchMode: "omnidirectional",
      displayedPitchChannelCount: bake.integratedPitchChannelCount,
      selectedPitchIndex: OMNIDIRECTIONAL_RADIATION_PITCH,
      selectedPitchEmphasized: false,
    };
    mesh.name = "rbe-omnidirectional-flux-volume";
    mesh.userData = {
      ...mesh.userData,
      ...RADIATION_BELT_VIEWS.dipoleMapped3d,
      label: RADIATION_PITCH_PRESENTATION_LABELS.omnidirectional,
      energyKev: this.radiationEnergyValue,
      selectedPitch: false,
      fullNative3d: false,
    };
    this.radiationGroup.add(mesh);
    this.radiationGroup.add(createRadiationFieldLineGuides(this.positionForRadiation, {
      trappingFloorRe: bake.trappingFloorRe,
    }));
  }

  /**
   * A labelled teaching option, not the default: one bounce shell, one pitch channel.
   *
   * Two differences from a member of the stacked reconstruction, both of which
   * only make sense when nothing is drawn in front of or behind this surface:
   *
   * - the mirror caps are closed, so the shell reads as a trapped volume with a
   *   near and a far wall instead of an open band whose ends float; and
   * - the mirror-latitude alpha fade is off, because it exists to stop stacked
   *   shells from summing into a hard rim, and on a lone shell it just erases
   *   the very edge the viewer needs to see the belt end.
   *
   * The opacity a viewer sees is therefore `0.53 * flux^0.68` — flux alone. No
   * shell-count term survives, which is the whole point of the default.
   */
  private buildSingleRadiationPitchShell(
    definition: RadiationBeltDefinition,
    frame: RadiationBeltFrame,
    pitchIndex: number,
  ) {
    const geometry = createDipoleMappedRadiationGeometry(definition, frame, this.radiationEnergyValue, {
      // Ten latitude rows per hemisphere: at four, the shell's silhouette was
      // visibly polygonal. One shell at this density is still cheap.
      samplesPerHemisphere: 10,
      pointStride: 1,
      includeMirrorCaps: true,
      pitchIndex,
      positionForGsm: this.positionForRadiation,
    });
    const equatorialPitchSin = definition.pitchCoordinatesSin[pitchIndex] ?? 0;
    const solidAngleWeight = gyrotropicPitchBinWeights(definition.pitchCoordinatesSin)[pitchIndex] ?? 0;
    const mirrorLatitudeDegrees = dipoleMirrorLatitudeRadians(equatorialPitchSin) * 180 / Math.PI;
    this.radiationGroup.userData = {
      representation: "single-pitch-centered-dipole-mapped-trapped-flux-shell",
      pitchMode: "single",
      sourcePitchChannelCount: definition.pitchCoordinatesSin.length,
      displayedPitchChannelCount: 1,
      selectedPitchIndex: pitchIndex,
      selectedPitchEmphasized: true,
      energyKev: this.radiationEnergyValue,
      particlePopulation: "RBE model electrons only",
      fullNative3d: false,
      syntheticInnerBelt: false,
      protonPopulation: false,
      displayWindow: geometry.userData.displayWindow,
    };
    const mesh = new THREE.Mesh(geometry, radiationSurfaceMaterial(1, 0, false));
    mesh.name = `rbe-gyrotropic-dipole-pitch-shell-${pitchIndex}`;
    mesh.frustumCulled = false;
    mesh.renderOrder = 20;
    mesh.userData = {
      ...geometry.userData,
      ...RADIATION_BELT_VIEWS.dipoleMapped3d,
      energyKev: this.radiationEnergyValue,
      pitchIndex,
      pitchCoordinateSin: equatorialPitchSin,
      pitchAngleDegrees: definition.pitchAnglesDegrees[pitchIndex] ?? 0,
      solidAngleWeight,
      mirrorLatitudeDegrees,
      selectedPitch: true,
      opacityScale: 1,
      displayedPitchChannelCount: 1,
      sourcePitchChannelCount: definition.pitchCoordinatesSin.length,
      // Same disclosures the stacked shells carry. Drawing one channel changes
      // how much is on screen, never what the surface is allowed to claim.
      representation: "gyrotropic-pitch-bin-centered-dipole-shell",
      gyrotropicAssumption: true,
      northSouthPitchSymmetryAssumption: true,
      particlePopulation: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.particlePopulation,
      syntheticInnerBelt: false,
      protonPopulation: false,
      fullNative3d: false,
    };
    this.radiationGroup.add(mesh);
  }
}
