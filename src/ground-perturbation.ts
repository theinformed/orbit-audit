import * as THREE from "three";

/**
 * The geomagnetic storm as it is felt at the ground.
 *
 * Every other magnetosphere layer on this site draws the storm out in space —
 * the compressed magnetopause, the stretched tail, the belts. This one draws
 * the thing a magnetometer actually records: the perturbation, in nanotesla,
 * that the model's current systems produce at the Earth's surface. It is the
 * quantity that defines a geomagnetic storm index, and its rate of change is
 * what drives geomagnetically induced currents in long conductors.
 *
 * WHAT THE FIVE CHOICES MEAN, AND WHERE THE MODEL STOPS
 * -----------------------------------------------------
 * NOAA's mag_grid file does not only give the total. It gives the model's own
 * attribution of that total to four current systems, and they sum to it exactly:
 *
 *   total = magnetospheric + fieldAligned + hall + pedersen
 *
 * `fieldAligned` is the Birkeland current sheets. `hall` is their ionospheric
 * Hall closure — at auroral latitudes, the electrojets. `pedersen` is the rest
 * of that ionospheric closure.
 *
 * `magnetospheric` is a LUMP. It contains the ring current, the cross-tail
 * current sheet and the magnetopause (Chapman–Ferraro) currents together, and
 * the file does not separate them. Nothing in this module calls it the ring
 * current, and nothing should: the ring current is not separately extracted by
 * this run at all.
 *
 * And none of the four is a measurement. A magnetometer measures one number.
 * Splitting that number across current systems is something only a model can
 * do, and this split is this model's.
 *
 * COORDINATES
 * -----------
 * The grid is GEOGRAPHIC — Earth-fixed latitude and longitude, unlike the GSM
 * cut planes. It belongs on the same Earth-fixed group as the coastlines, and
 * its texture is offset by exactly the formula every other equirectangular
 * layer here uses. `groundFieldTextureOffsetX` exists so that formula is
 * written once and can be asserted against the globe's own vector transform;
 * this project has already shipped a layer a quarter-turn out of position.
 */

export type GroundCurrentSystemKey =
  | "total"
  | "magnetospheric"
  | "fieldAligned"
  | "hall"
  | "pedersen";

export type GroundComponentKey = "north" | "east" | "down";

export type GroundFieldDisplayMode = "smooth" | "native";

export interface GroundFieldEncoding {
  scale: "linear";
  minimum: number;
  maximum: number;
  units: string;
  quantity?: string;
}

export interface GroundFieldGrid {
  longitudeCount: number;
  latitudeCount: number;
  longitudeStartDeg: number;
  longitudeStepDeg: number;
  latitudeStartDeg: number;
  latitudeStepDeg: number;
  cellCount: number;
  ordering: string;
  polarCaps: string;
}

export interface GroundCurrentSystemDefinition {
  key: GroundCurrentSystemKey;
  sourceColumn?: string;
  label: string;
  meaning: string;
}

export interface GroundFieldFrame {
  validAt: string;
  runAt: string;
  leadMinutes: number;
  fieldsU16: Record<GroundCurrentSystemKey, Record<GroundComponentKey, string>>;
  fieldMasksU8: Record<GroundCurrentSystemKey, Record<GroundComponentKey, string>>;
  extrema: {
    maximumHorizontalNt: number;
    maximumHorizontalLatitudeDeg: number;
    maximumHorizontalLongitudeDeg: number;
    maximumVerticalNt: number;
    unusableCellCount: number;
  };
}

export interface GroundFieldBundle {
  schema: 1;
  product: string;
  status: "model";
  evidence: string;
  model: string;
  coordinateSystem: string;
  quantity: { name: string; units: string; components: string; meaning: string };
  grid: GroundFieldGrid;
  currentSystems: GroundCurrentSystemDefinition[];
  attribution: string;
  fieldEncoding: GroundFieldEncoding;
  fieldMaskEncoding: {
    storage: string;
    flags: { missing: number; clippedLow: number; clippedHigh: number };
    meaning: string;
  };
  source: { name: string; url: string; cadence: string };
  time: {
    requestedFrom: string;
    requestedTo: string;
    coverageComplete: boolean;
    noDataIntervals: Array<{ validAt: string; reason: string }>;
    selectedFrameCount: number;
  };
  history: { archived: boolean; meaning: string };
  displayModes: Record<string, string>;
  frames: GroundFieldFrame[];
  caveat: string;
}

/** Public constants the walkthrough and the legend both read rather than restate. */
export const GROUND_FIELD_SYSTEM_ORDER: readonly GroundCurrentSystemKey[] = [
  "total",
  "magnetospheric",
  "fieldAligned",
  "hall",
  "pedersen",
];

export const GROUND_FIELD_LAYER_POLICY = {
  defaultVisible: false,
  menu: "advanced-layers",
  loadOnDemand: true,
} as const;

export const GROUND_FIELD_DATA_METHOD = {
  status: "model",
  label: "NOAA physics simulation",
  title: "Ground magnetic perturbation",
  summary:
    "What the storm does at the ground: the disturbance, in nanotesla, that the model's current systems produce at the Earth's surface.",
  data:
    "NOAA's operational Geospace SWMF run writes a 5° geographic grid of ground perturbation every minute, in North-East-Down components, split by the current system responsible for it.",
  processing:
    "bigmem downloads only the frames this bundle publishes, checks the file's declared grid against the rows it actually carries, and stores each component as uint16 over ±5,000 nT with a separate validity mask. The browser snaps to the nearest published frame and never interpolates between them.",
  limitation:
    "This is physics-simulation output, not a magnetometer reading and not an assimilation of one. Each frame is valid after the run that produced it, so it is guidance. The per-current-system split is the model's own attribution; the 'magnetospheric' field lumps the ring current, the cross-tail current sheet and the magnetopause currents together and is none of them individually. The grid stops short of the poles and nothing is extrapolated across the caps.",
  url: "https://www.swpc.noaa.gov/products/geospace-ground-magnetic-perturbation-maps",
} as const;

export const GROUND_FIELD_DISPLAY_MODES = {
  smooth: {
    label: "Smooth",
    description: "Bilinear display of the published 5° cells; cannot create a new extremum.",
  },
  native: {
    label: "Native grid",
    description: "The unresampled 5° geographic source cells.",
  },
} as const satisfies Record<GroundFieldDisplayMode, { label: string; description: string }>;

/**
 * A frame is refused rather than drawn with holes past this fraction.
 *
 * The same 2% the radiation-belt reducer uses. A handful of unusable cells is a
 * hole to be shown as a hole; a field that is mostly holes is a broken frame,
 * and drawing it would put a plausible-looking but largely absent picture in
 * front of someone deciding whether a storm matters.
 */
export const GROUND_FIELD_MAXIMUM_MISSING_FRACTION = 0.02;

const MASK_MISSING = 1;

const EARTH_MEAN_RADIUS_KM = 6_371;
const DEFAULT_EARTH_SCENE_RADIUS = 100;
/**
 * The quantity is at the ground. This lift exists only so the depth buffer can
 * separate the overlay from the Earth sphere and its coastlines; 6 km is under
 * a tenth of a percent of the globe's radius and is not a claimed altitude.
 */
const GROUND_FIELD_SEPARATION_KM = 6;

/** Frames arrive 20 minutes apart, so a selected UTC snaps at most 10 minutes. */
export const GROUND_FIELD_SNAP_MINUTES = 10;

export interface GroundFieldSample {
  latitudeDeg: number;
  longitudeDeg: number;
  cellIndex: number;
  /** null where the source cell is missing. Never zero as a stand-in. */
  systems: Record<GroundCurrentSystemKey, { north: number | null; east: number | null; down: number | null; horizontal: number | null }>;
}

export interface DecodedGroundComponent {
  values: Float32Array;
  mask: Uint8Array;
}

export interface GroundFieldRgbaGrid {
  width: number;
  height: number;
  rgba: Uint8ClampedArray;
  missingCellCount: number;
  maximumDisplayedNt: number;
}

export interface GroundFieldRenderOptions {
  system?: GroundCurrentSystemKey;
  mode?: GroundFieldDisplayMode;
  opacity?: number;
}

/**
 * Colour by magnitude of the horizontal perturbation.
 *
 * Alpha never reaches zero for a cell that carries a value, so a verified quiet
 * field is visibly a covered, quiet field rather than a blank one. Missing
 * cells are the only fully transparent cells there are, and they are counted.
 */
const COLOR_STOPS: ReadonlyArray<readonly [number, number, number, number, number]> = [
  [0, 18, 42, 62, 22],
  [20, 26, 84, 140, 78],
  [50, 32, 132, 168, 116],
  [100, 56, 176, 152, 152],
  [200, 168, 200, 88, 182],
  [400, 240, 176, 56, 206],
  [700, 238, 108, 56, 226],
  [1000, 226, 60, 76, 240],
  [1500, 176, 44, 140, 248],
];

export const GROUND_FIELD_LEGEND_TICKS_NT = [0, 50, 100, 200, 400, 700, 1000, 1500];

export function groundPerturbationColor(horizontalNt: number): [number, number, number, number] {
  if (!Number.isFinite(horizontalNt)) return [0, 0, 0, 0];
  const magnitude = Math.max(0, horizontalNt);
  const first = COLOR_STOPS[0]!;
  if (magnitude <= first[0]) return [first[1], first[2], first[3], first[4]];
  for (let index = 1; index < COLOR_STOPS.length; index += 1) {
    const previous = COLOR_STOPS[index - 1]!;
    const current = COLOR_STOPS[index]!;
    if (magnitude <= current[0]) {
      const amount = (magnitude - previous[0]) / (current[0] - previous[0]);
      return [
        Math.round(mix(previous[1], current[1], amount)),
        Math.round(mix(previous[2], current[2], amount)),
        Math.round(mix(previous[3], current[3], amount)),
        Math.round(mix(previous[4], current[4], amount)),
      ];
    }
  }
  const last = COLOR_STOPS[COLOR_STOPS.length - 1]!;
  return [last[1], last[2], last[3], last[4]];
}

/**
 * Where an equirectangular texture built from this grid must be sampled.
 *
 * A DataTexture's texel centre for column j is u = (j + 0.5) / width, and
 * column j holds longitude start + j·step. SphereGeometry gives longitude L the
 * coordinate u = (L + 180) / 360. Equating the two gives this offset. It is the
 * identical expression the D-RAP and aurora layers use; it is written here so a
 * test can assert the two agree rather than trusting that they do.
 */
export function groundFieldTextureOffsetX(grid: GroundFieldGrid): number {
  return (-grid.longitudeStartDeg + grid.longitudeStepDeg / 2 - 180) / 360;
}

/**
 * How the published rows are laid into a texture that stops where they stop.
 *
 * The source grid ends at ±85°. A texture of exactly 35 rows, sampled with
 * ClampToEdge, paints the ±85° row's colour over both polar caps — which is an
 * extrapolation into the one part of the Earth where a geomagnetic disturbance
 * is most interesting and where this model publishes nothing at all.
 *
 * So one fully transparent guard row is added at each end, and the vertical
 * mapping is stretched so the published rows still land at their own latitudes.
 * Everything poleward of half a cell past the last published row then samples
 * the guard row and draws as absent. That half-cell is the same nearest-cell
 * rule the rest of the grid uses; past it there is nothing, and nothing is
 * exactly what appears.
 */
export function groundFieldTextureLayout(grid: GroundFieldGrid): {
  guardRows: number;
  height: number;
  repeatY: number;
  offsetY: number;
} {
  const guardRows = 1;
  const height = grid.latitudeCount + 2 * guardRows;
  const repeatY = 180 / (height * grid.latitudeStepDeg);
  const offsetY = (guardRows + 0.5) / height - (repeatY * (grid.latitudeStartDeg + 90)) / 180;
  return { guardRows, height, repeatY, offsetY };
}

/** The latitude a sampled texture coordinate resolves to. Inverse of the above. */
export function groundFieldLatitudeAtTextureV(grid: GroundFieldGrid, sampledV: number): number {
  const { repeatY, offsetY } = groundFieldTextureLayout(grid);
  return ((sampledV - offsetY) / repeatY) * 180 - 90;
}

/** Longitude, in degrees, held by a column of the published grid. */
export function groundFieldColumnLongitude(grid: GroundFieldGrid, column: number): number {
  return grid.longitudeStartDeg + column * grid.longitudeStepDeg;
}

/** Latitude, in degrees, held by a row of the published grid. */
export function groundFieldRowLatitude(grid: GroundFieldGrid, row: number): number {
  return grid.latitudeStartDeg + row * grid.latitudeStepDeg;
}

/**
 * The grid column a geographic longitude falls in, or -1 outside the grid.
 *
 * Longitude wraps; latitude does not. The source grid stops short of both poles
 * and a location beyond its last row has no published value at all.
 */
export function groundFieldColumnFor(grid: GroundFieldGrid, longitudeDeg: number): number {
  if (!Number.isFinite(longitudeDeg)) return -1;
  const span = grid.longitudeCount * grid.longitudeStepDeg;
  const offset = (((longitudeDeg - grid.longitudeStartDeg) % span) + span) % span;
  const column = Math.round(offset / grid.longitudeStepDeg) % grid.longitudeCount;
  return column;
}

export function groundFieldRowFor(grid: GroundFieldGrid, latitudeDeg: number): number {
  if (!Number.isFinite(latitudeDeg)) return -1;
  const row = Math.round((latitudeDeg - grid.latitudeStartDeg) / grid.latitudeStepDeg);
  return row < 0 || row >= grid.latitudeCount ? -1 : row;
}

export function decodeGroundComponent(
  bundle: GroundFieldBundle,
  frame: GroundFieldFrame,
  system: GroundCurrentSystemKey,
  component: GroundComponentKey,
): DecodedGroundComponent {
  const encoding = bundle.fieldEncoding;
  if (encoding.scale !== "linear") throw new Error(`Unsupported ground-field scale: ${String(encoding.scale)}`);
  const encoded = frame.fieldsU16?.[system]?.[component];
  const maskEncoded = frame.fieldMasksU8?.[system]?.[component];
  if (typeof encoded !== "string" || typeof maskEncoded !== "string") {
    throw new Error(`Ground-field frame is missing ${system}.${component}`);
  }
  const cellCount = bundle.grid.longitudeCount * bundle.grid.latitudeCount;
  const bytes = decodeBase64(encoded);
  const mask = decodeBase64(maskEncoded);
  if (bytes.byteLength !== cellCount * 2) {
    throw new Error(`Ground-field ${system}.${component} has ${bytes.byteLength} bytes; expected ${cellCount * 2}`);
  }
  if (mask.byteLength !== cellCount) {
    throw new Error(`Ground-field ${system}.${component} mask has ${mask.byteLength} bytes; expected ${cellCount}`);
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const span = encoding.maximum - encoding.minimum;
  const values = new Float32Array(cellCount);
  for (let index = 0; index < cellCount; index += 1) {
    if ((mask[index]! & MASK_MISSING) !== 0) {
      // NaN, never 0. A cell the model did not produce and a cell the model
      // produced as quiet are different facts and must stay different numbers.
      values[index] = Number.NaN;
      continue;
    }
    values[index] = encoding.minimum + (view.getUint16(index * 2, true) / 65535) * span;
  }
  return { values, mask };
}

/** Horizontal magnitude, the quantity a magnetogram's H trace deviates by. */
export function groundHorizontalMagnitude(
  bundle: GroundFieldBundle,
  frame: GroundFieldFrame,
  system: GroundCurrentSystemKey,
): DecodedGroundComponent {
  const north = decodeGroundComponent(bundle, frame, system, "north");
  const east = decodeGroundComponent(bundle, frame, system, "east");
  const values = new Float32Array(north.values.length);
  const mask = new Uint8Array(north.values.length);
  for (let index = 0; index < values.length; index += 1) {
    const combined = north.mask[index]! | east.mask[index]!;
    mask[index] = combined;
    values[index] = (combined & MASK_MISSING) !== 0
      ? Number.NaN
      : Math.hypot(north.values[index]!, east.values[index]!);
  }
  return { values, mask };
}

export function groundFieldMissingCellCount(decoded: DecodedGroundComponent): number {
  let missing = 0;
  for (let index = 0; index < decoded.values.length; index += 1) {
    if (!Number.isFinite(decoded.values[index]!)) missing += 1;
  }
  return missing;
}

/** True when a frame carries enough cells to be worth drawing at all. */
export function groundFieldFrameUsable(bundle: GroundFieldBundle, frame: GroundFieldFrame): boolean {
  try {
    const decoded = groundHorizontalMagnitude(bundle, frame, "total");
    const cellCount = bundle.grid.longitudeCount * bundle.grid.latitudeCount;
    return groundFieldMissingCellCount(decoded) <= cellCount * GROUND_FIELD_MAXIMUM_MISSING_FRACTION;
  } catch {
    return false;
  }
}

export function groundPerturbationRgba(
  bundle: GroundFieldBundle,
  frame: GroundFieldFrame,
  options: GroundFieldRenderOptions = {},
): GroundFieldRgbaGrid {
  const system = options.system ?? "total";
  const decoded = groundHorizontalMagnitude(bundle, frame, system);
  const width = bundle.grid.longitudeCount;
  const height = bundle.grid.latitudeCount;
  const opacity = clamp(options.opacity ?? 1, 0, 1);
  const rgba = new Uint8ClampedArray(width * height * 4);
  let missingCellCount = 0;
  let maximumDisplayedNt = 0;
  for (let index = 0; index < decoded.values.length; index += 1) {
    const destination = index * 4;
    const value = decoded.values[index]!;
    if (!Number.isFinite(value)) {
      missingCellCount += 1;
      rgba[destination] = 0;
      rgba[destination + 1] = 0;
      rgba[destination + 2] = 0;
      rgba[destination + 3] = 0;
      continue;
    }
    if (value > maximumDisplayedNt) maximumDisplayedNt = value;
    const color = groundPerturbationColor(value);
    rgba[destination] = color[0];
    rgba[destination + 1] = color[1];
    rgba[destination + 2] = color[2];
    rgba[destination + 3] = Math.round(color[3] * opacity);
  }
  return { width, height, rgba, missingCellCount, maximumDisplayedNt };
}

/** The same grid with a transparent row above and below the published band. */
export function withPolarGuardRows(
  rendered: GroundFieldRgbaGrid,
  grid: GroundFieldGrid,
): GroundFieldRgbaGrid {
  const { guardRows, height } = groundFieldTextureLayout(grid);
  const padded = new Uint8ClampedArray(rendered.width * height * 4);
  padded.set(rendered.rgba, rendered.width * guardRows * 4);
  return { ...rendered, height, rgba: padded };
}

/** Every component of every current system at one place, for the data viewer. */
export function sampleGroundPerturbation(
  bundle: GroundFieldBundle,
  frame: GroundFieldFrame,
  latitudeDeg: number,
  longitudeDeg: number,
): GroundFieldSample | null {
  const row = groundFieldRowFor(bundle.grid, latitudeDeg);
  const column = groundFieldColumnFor(bundle.grid, longitudeDeg);
  if (row < 0 || column < 0) return null;
  const cellIndex = row * bundle.grid.longitudeCount + column;
  const systems = {} as GroundFieldSample["systems"];
  for (const system of GROUND_FIELD_SYSTEM_ORDER) {
    const north = decodeGroundComponent(bundle, frame, system, "north").values[cellIndex]!;
    const east = decodeGroundComponent(bundle, frame, system, "east").values[cellIndex]!;
    const down = decodeGroundComponent(bundle, frame, system, "down").values[cellIndex]!;
    const finite = Number.isFinite(north) && Number.isFinite(east);
    systems[system] = {
      north: Number.isFinite(north) ? north : null,
      east: Number.isFinite(east) ? east : null,
      down: Number.isFinite(down) ? down : null,
      horizontal: finite ? Math.hypot(north, east) : null,
    };
  }
  return {
    latitudeDeg: groundFieldRowLatitude(bundle.grid, row),
    longitudeDeg: groundFieldColumnLongitude(bundle.grid, column),
    cellIndex,
    systems,
  };
}

export interface GroundFieldSelection {
  frame: GroundFieldFrame;
  ageMinutes: number;
  /** True when the nearest frame is further away than the snap radius allows. */
  outsideSnapRadius: boolean;
}

export function selectGroundFieldFrame(
  bundle: GroundFieldBundle,
  requestedAt: Date | string | number,
): GroundFieldSelection | null {
  const requestedMs = toTimeMs(requestedAt);
  if (requestedMs === null) return null;
  let best: GroundFieldFrame | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const frame of bundle.frames) {
    const validMs = Date.parse(frame.validAt);
    if (!Number.isFinite(validMs)) continue;
    const distance = Math.abs(validMs - requestedMs);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = frame;
    }
  }
  if (!best) return null;
  return {
    frame: best,
    ageMinutes: (requestedMs - Date.parse(best.validAt)) / 60_000,
    outsideSnapRadius: bestDistance / 60_000 > GROUND_FIELD_SNAP_MINUTES,
  };
}

export type GroundFieldNoDataReason =
  | "invalid-time"
  | "no-frames"
  | "outside-coverage"
  | "invalid-frame";

export interface GroundFieldLegend {
  product: string;
  title: string;
  subtitle: string;
  units: string;
  minimum: number;
  maximum: number;
  ticks: number[];
  minimumLabel: string;
  maximumLabel: string;
  sourceUrl: string;
  sourceStatus: "model";
  evidence: string;
  system: GroundCurrentSystemKey;
  systemLabel: string;
  systemMeaning: string;
  attribution: string;
  displayMode: GroundFieldDisplayMode;
  validAt: string | null;
  runAt: string | null;
  leadMinutes: number | null;
  maximumHorizontalNt: number | null;
  maximumHorizontalAt: { latitudeDeg: number; longitudeDeg: number } | null;
  missingCellCount: number | null;
  latitudeLimitDeg: number;
  sourceRange: { validFrom: string | null; validTo: string | null; frameCount: number; coverageComplete: boolean };
}

interface GroundFieldStateBase {
  requestedAt: string | null;
  visible: boolean;
  legend: GroundFieldLegend;
}

export interface GroundFieldReadyState extends GroundFieldStateBase {
  status: "ready";
  validAt: string;
  ageMinutes: number;
  held: boolean;
}

export interface GroundFieldNoDataState extends GroundFieldStateBase {
  status: "no-data";
  reason: GroundFieldNoDataReason;
  message: string;
  previousValidAt: string | null;
  nextValidAt: string | null;
}

export type GroundFieldState = GroundFieldReadyState | GroundFieldNoDataState;

export interface GroundFieldLayerOptions {
  earthSceneRadius?: number;
  enabled?: boolean;
  system?: GroundCurrentSystemKey;
  widthSegments?: number;
  heightSegments?: number;
}

/**
 * The globe overlay.
 *
 * Self-contained rather than a subclass of the D-RAP/aurora base, because the
 * legend this layer owes its reader — which current system, what the split
 * does and does not separate, how far the frame leads its run — is not the
 * legend those two share. The texture mathematics is deliberately identical and
 * is asserted to be, in `tests/ground-perturbation.test.ts`.
 */
export class GroundPerturbationLayer {
  readonly mesh: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  private bundle: GroundFieldBundle;
  private systemValue: GroundCurrentSystemKey;
  private displayMode: GroundFieldDisplayMode = "smooth";
  private currentFrame: GroundFieldFrame | null = null;
  private currentStateValue: GroundFieldState;
  private enabledValue: boolean;
  private textureValue: THREE.DataTexture | null = null;
  private requestedAtValue: Date | string | number | null = null;
  private missingCellCountValue: number | null = null;
  private disposed = false;

  constructor(bundle: GroundFieldBundle, options: GroundFieldLayerOptions = {}) {
    this.bundle = bundle;
    this.systemValue = options.system ?? "total";
    this.enabledValue = options.enabled ?? false;
    const earthRadius = options.earthSceneRadius ?? DEFAULT_EARTH_SCENE_RADIUS;
    if (!Number.isFinite(earthRadius) || earthRadius <= 0) throw new RangeError("Earth scene radius must be positive");
    const geometry = new THREE.SphereGeometry(
      earthRadius * (1 + GROUND_FIELD_SEPARATION_KM / EARTH_MEAN_RADIUS_KM),
      options.widthSegments ?? 96,
      options.heightSegments ?? 64,
    );
    const material = new THREE.MeshBasicMaterial({
      transparent: true,
      depthTest: true,
      depthWrite: false,
      side: THREE.FrontSide,
      toneMapped: false,
    });
    this.mesh = new THREE.Mesh(geometry, material);
    // No orienting rotation, for the same reason the D-RAP and aurora shells
    // carry none: the texture offset already puts longitude where
    // geoToSceneVector puts it, and a rotation here would slide this layer off
    // the coastlines drawn under it.
    this.mesh.renderOrder = 3;
    this.currentStateValue = this.noDataState(null, "no-frames", "No ground-perturbation frame has been selected.", null, null);
    this.applyState(this.currentStateValue);
  }

  get state(): GroundFieldState { return this.currentStateValue; }
  get texture(): THREE.DataTexture | null { return this.textureValue; }
  get enabled(): boolean { return this.enabledValue; }
  get system(): GroundCurrentSystemKey { return this.systemValue; }
  get mode(): GroundFieldDisplayMode { return this.displayMode; }
  get frame(): GroundFieldFrame | null { return this.currentFrame; }

  setEnabled(enabled: boolean): GroundFieldState {
    this.assertActive();
    this.enabledValue = enabled;
    this.applyState(this.currentStateValue);
    return this.currentStateValue;
  }

  setCurrentSystem(system: GroundCurrentSystemKey): GroundFieldState {
    this.assertActive();
    if (!GROUND_FIELD_SYSTEM_ORDER.includes(system)) {
      throw new RangeError(`Unknown ground current system: ${String(system)}`);
    }
    if (system === this.systemValue) return this.currentStateValue;
    this.systemValue = system;
    return this.reapply();
  }

  setDisplayMode(mode: GroundFieldDisplayMode): GroundFieldState {
    this.assertActive();
    if (mode !== "smooth" && mode !== "native") throw new RangeError(`Unsupported ground-field display mode: ${String(mode)}`);
    if (mode === this.displayMode) return this.currentStateValue;
    this.displayMode = mode;
    return this.reapply();
  }

  setSimulationTime(requestedAt: Date | string | number): GroundFieldState {
    this.assertActive();
    this.requestedAtValue = requestedAt;
    const requestedMs = toTimeMs(requestedAt);
    if (requestedMs === null) {
      this.clear();
      this.currentStateValue = this.noDataState(null, "invalid-time", "The selected simulation time is invalid.", null, null);
      this.applyState(this.currentStateValue);
      return this.currentStateValue;
    }
    const requestedIso = new Date(requestedMs).toISOString();
    const selection = selectGroundFieldFrame(this.bundle, requestedMs);
    const bounds = this.bounds(requestedMs);
    if (!selection) {
      this.clear();
      this.currentStateValue = this.noDataState(
        requestedIso,
        "no-frames",
        "No NOAA ground-perturbation frames are loaded.",
        null,
        null,
      );
      this.applyState(this.currentStateValue);
      return this.currentStateValue;
    }
    if (selection.outsideSnapRadius) {
      // Held frames are not shown. A quiet-looking field from 40 minutes ago is
      // exactly the comfortable lie this layer must not tell.
      this.clear();
      this.currentStateValue = this.noDataState(
        requestedIso,
        "outside-coverage",
        `No NOAA ground-perturbation frame is within ${GROUND_FIELD_SNAP_MINUTES} minutes of this UTC; nothing stale is held.`,
        bounds.previous?.validAt ?? null,
        bounds.next?.validAt ?? null,
      );
      this.applyState(this.currentStateValue);
      return this.currentStateValue;
    }
    if (!groundFieldFrameUsable(this.bundle, selection.frame)) {
      this.clear();
      this.currentStateValue = this.noDataState(
        requestedIso,
        "invalid-frame",
        "The NOAA ground-perturbation frame at this UTC has too many unusable cells to draw.",
        bounds.previous?.validAt ?? null,
        bounds.next?.validAt ?? null,
      );
      this.applyState(this.currentStateValue);
      return this.currentStateValue;
    }
    this.currentFrame = selection.frame;
    this.installTexture(selection.frame);
    this.currentStateValue = {
      status: "ready",
      requestedAt: requestedIso,
      visible: this.enabledValue,
      validAt: selection.frame.validAt,
      ageMinutes: selection.ageMinutes,
      held: false,
      legend: this.legend(selection.frame),
    };
    this.applyState(this.currentStateValue);
    return this.currentStateValue;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.clear();
    this.mesh.removeFromParent();
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
    this.mesh.visible = false;
  }

  legend(frame: GroundFieldFrame | null = this.currentFrame): GroundFieldLegend {
    const definition = this.bundle.currentSystems.find((entry) => entry.key === this.systemValue);
    const validTimes = this.bundle.frames
      .map((entry) => entry.validAt)
      .filter((value) => Number.isFinite(Date.parse(value)))
      .sort((left, right) => Date.parse(left) - Date.parse(right));
    const grid = this.bundle.grid;
    return {
      product: this.bundle.product,
      title: "Ground magnetic perturbation",
      subtitle: `${this.bundle.model} · horizontal disturbance`,
      units: this.bundle.quantity.units,
      minimum: 0,
      maximum: GROUND_FIELD_LEGEND_TICKS_NT[GROUND_FIELD_LEGEND_TICKS_NT.length - 1]!,
      ticks: [...GROUND_FIELD_LEGEND_TICKS_NT],
      minimumLabel: "0 nT · no modeled disturbance",
      maximumLabel: `${GROUND_FIELD_LEGEND_TICKS_NT[GROUND_FIELD_LEGEND_TICKS_NT.length - 1]!} nT and above`,
      sourceUrl: this.bundle.source.url,
      sourceStatus: "model",
      evidence: this.bundle.evidence,
      system: this.systemValue,
      systemLabel: definition?.label ?? this.systemValue,
      systemMeaning: definition?.meaning ?? "",
      attribution: this.bundle.attribution,
      displayMode: this.displayMode,
      validAt: frame?.validAt ?? null,
      runAt: frame?.runAt ?? null,
      leadMinutes: frame?.leadMinutes ?? null,
      maximumHorizontalNt: frame?.extrema.maximumHorizontalNt ?? null,
      maximumHorizontalAt: frame
        ? {
            latitudeDeg: frame.extrema.maximumHorizontalLatitudeDeg,
            longitudeDeg: frame.extrema.maximumHorizontalLongitudeDeg,
          }
        : null,
      missingCellCount: frame ? this.missingCellCountValue : null,
      latitudeLimitDeg: Math.abs(grid.latitudeStartDeg + (grid.latitudeCount - 1) * grid.latitudeStepDeg),
      sourceRange: {
        validFrom: validTimes[0] ?? null,
        validTo: validTimes[validTimes.length - 1] ?? null,
        frameCount: validTimes.length,
        coverageComplete: this.bundle.time.coverageComplete,
      },
    };
  }

  private reapply(): GroundFieldState {
    if (this.requestedAtValue === null) {
      this.currentStateValue = { ...this.currentStateValue, legend: this.legend(null) };
      this.applyState(this.currentStateValue);
      return this.currentStateValue;
    }
    return this.setSimulationTime(this.requestedAtValue);
  }

  private bounds(requestedMs: number): { previous: GroundFieldFrame | null; next: GroundFieldFrame | null } {
    let previous: GroundFieldFrame | null = null;
    let next: GroundFieldFrame | null = null;
    for (const frame of this.bundle.frames) {
      const validMs = Date.parse(frame.validAt);
      if (!Number.isFinite(validMs)) continue;
      if (validMs <= requestedMs) previous = frame;
      else if (!next) next = frame;
    }
    return { previous, next };
  }

  private installTexture(frame: GroundFieldFrame): void {
    const source = groundPerturbationRgba(this.bundle, frame, { system: this.systemValue, mode: this.displayMode });
    if (source.rgba.length !== source.width * source.height * 4) {
      throw new Error("Ground-perturbation RGBA grid dimensions are invalid");
    }
    this.missingCellCountValue = source.missingCellCount;
    const rendered = withPolarGuardRows(source, this.bundle.grid);
    const layout = groundFieldTextureLayout(this.bundle.grid);
    const texture = new THREE.DataTexture(
      rendered.rgba,
      rendered.width,
      rendered.height,
      THREE.RGBAFormat,
      THREE.UnsignedByteType,
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.minFilter = this.displayMode === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.magFilter = this.displayMode === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.generateMipmaps = false;
    // NOAA writes this grid south to north; a DataTexture's V origin is at the
    // bottom, so those rows are already in the right order and must not be
    // flipped. The sign is read from the bundle rather than assumed.
    texture.flipY = this.bundle.grid.latitudeStepDeg < 0;
    texture.offset.x = groundFieldTextureOffsetX(this.bundle.grid);
    texture.repeat.y = layout.repeatY;
    texture.offset.y = layout.offsetY;
    texture.needsUpdate = true;
    texture.userData = {
      product: this.bundle.product,
      validAt: frame.validAt,
      currentSystem: this.systemValue,
      displayMode: this.displayMode,
      temporalInterpolation: false,
      longitudeStartDegrees: this.bundle.grid.longitudeStartDeg,
      longitudeStepDegrees: this.bundle.grid.longitudeStepDeg,
      latitudeRowOrder: this.bundle.grid.latitudeStepDeg < 0 ? "north-to-south" : "south-to-north",
      missingCellCount: source.missingCellCount,
      polarGuardRows: layout.guardRows,
      publishedLatitudeLimitDeg: Math.abs(
        this.bundle.grid.latitudeStartDeg + (this.bundle.grid.latitudeCount - 1) * this.bundle.grid.latitudeStepDeg,
      ),
    };
    const previous = this.textureValue;
    this.textureValue = texture;
    this.mesh.material.map = texture;
    this.mesh.material.needsUpdate = true;
    previous?.dispose();
  }

  private clear(): void {
    this.currentFrame = null;
    this.missingCellCountValue = null;
    const previous = this.textureValue;
    this.textureValue = null;
    this.mesh.material.map = null;
    this.mesh.material.needsUpdate = true;
    previous?.dispose();
  }

  private noDataState(
    requestedAt: string | null,
    reason: GroundFieldNoDataReason,
    message: string,
    previousValidAt: string | null,
    nextValidAt: string | null,
  ): GroundFieldNoDataState {
    return {
      status: "no-data",
      requestedAt,
      visible: false,
      reason,
      message,
      previousValidAt,
      nextValidAt,
      legend: this.legend(null),
    };
  }

  private applyState(state: GroundFieldState): void {
    this.mesh.visible = this.enabledValue && state.status === "ready" && this.textureValue !== null;
    this.currentStateValue = { ...state, visible: this.mesh.visible };
    this.mesh.userData.groundFieldState = this.currentStateValue;
  }

  private assertActive(): void {
    if (this.disposed) throw new Error("Ground-perturbation layer has been disposed");
  }
}

function decodeBase64(encoded: string): Uint8Array {
  const binary = globalThis.atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

function toTimeMs(value: Date | string | number): number | null {
  const result = value instanceof Date ? value.getTime() : typeof value === "number" ? value : Date.parse(value);
  return Number.isFinite(result) ? result : null;
}

function mix(start: number, end: number, amount: number): number {
  return start + (end - start) * amount;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
