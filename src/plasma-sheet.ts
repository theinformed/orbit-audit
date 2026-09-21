import * as THREE from "three";
import { GEOSPACE_SLICE_MASK } from "./geospace-slice-data";
import type { PreparedAdaptivePlaneField, SmoothedAdaptivePlaneField } from "./geospace-slice-data";

/**
 * The plasma sheet, from the two fields NOAA already publishes.
 *
 * ## What this layer is, and what it is not
 *
 * The plasma sheet is the hot, dense sheet of plasma that fills the middle of
 * the magnetotail. It is the reservoir that feeds the ring current and the
 * aurora, and it is the object a student has to be able to see before the
 * Dungey cycle means anything. NOAA's operational Geospace run does NOT
 * publish a plasma-sheet product, and this project does not invent one.
 *
 * What the run does publish, on its two GSM cut planes, is BATS-R-US thermal
 * pressure `p` in nPa and magnetic-field magnitude `|B|` in nT at every point
 * of the same adaptive grid. Their ratio is the plasma beta
 *
 *     beta = p / (B^2 / 2 mu0)
 *
 * — the standard dimensionless measure of which of the two pressures is in
 * charge. beta << 1 is a magnetically dominated region: the tail lobes, the
 * dayside cavity, the inner magnetosphere. beta >= 1 is a plasma-dominated
 * region: the shocked magnetosheath, the solar wind, and — between the two
 * lobes, inside the magnetopause — the plasma sheet.
 *
 * So this layer draws beta as a FIELD over the published cut, on a ramp
 * centred on beta = 1, and measures the sheet from it. Nothing here is an
 * outline, and nothing is drawn where the model published nothing.
 *
 * ## The honesty boundary
 *
 * Two claims have to be kept apart and the key card keeps them apart:
 *
 *  - beta itself is a straight ratio of two published model values. It is as
 *    good as the model output it comes from, and no better.
 *  - "beta = 1 is the edge of the plasma sheet" is a CONVENTION. It is the
 *    threshold the literature uses, it is not a published boundary, and it is
 *    a threshold on a simulation rather than a measured crossing. The layer
 *    says so, and the measured numbers are labelled as what they are: the
 *    extent of the beta >= 1 region in a stated window of the tail.
 *
 * A third caveat is measured per frame rather than asserted. Both source
 * fields have finite encoding ranges (p down to 10^-3 nPa, |B| up to 10^3 nT),
 * and where a source value sat on its own endpoint the ratio is a BOUND, not a
 * value. Those cells are counted and reported rather than quietly coloured.
 */

/** Vacuum permeability, SI. */
const MU0 = 4e-7 * Math.PI;

/**
 * Magnetic pressure in nPa from a field magnitude in nT: p_mag = k * B^2.
 *
 * The constant is 1/(2 mu0) carried through the two unit conversions the
 * published fields force — B is nT (1e-9 T) and the answer is wanted in nPa
 * (1e-9 Pa) — so it is written as the arithmetic rather than as a magic
 * number. It works out to 3.9789e-4 nPa per nT^2: a 50 nT field carries about
 * 0.99 nPa, which is the number to sanity-check this against.
 */
export const MAGNETIC_PRESSURE_NPA_PER_NT_SQUARED = (1e-9 * 1e-9) / (2 * MU0) / 1e-9;

/** Magnetic pressure in nPa for a field magnitude in nT. */
export function magneticPressureNPa(magneticFieldNt: number): number {
  if (!Number.isFinite(magneticFieldNt)) return Number.NaN;
  return MAGNETIC_PRESSURE_NPA_PER_NT_SQUARED * magneticFieldNt * magneticFieldNt;
}

/**
 * Plasma beta from the two published quantities.
 *
 * Returns NaN rather than Infinity where the magnetic pressure is zero: a cell
 * with no field is a cell where beta is undefined, and an infinity would paint
 * the ramp's hot end over a hole. The drawn field treats NaN as missing.
 */
export function plasmaBeta(thermalPressureNPa: number, magneticFieldNt: number): number {
  if (!Number.isFinite(thermalPressureNPa) || thermalPressureNPa < 0) return Number.NaN;
  const magnetic = magneticPressureNPa(magneticFieldNt);
  if (!Number.isFinite(magnetic) || magnetic <= 0) return Number.NaN;
  return thermalPressureNPa / magnetic;
}

/** The conventional plasma-sheet threshold. Thermal pressure equals magnetic. */
export const PLASMA_SHEET_BETA_THRESHOLD = 1;

/**
 * The drawn range of log10 beta.
 *
 * Measured against the published live frames: the tail lobes bottom out near
 * 10^-3, the sheet peaks between 10^0.4 and 10^1.7, and the magnetosheath sits
 * around 10^0.5. Five decades hold all of that with the interesting decade —
 * the one either side of beta = 1 — well inside the ramp rather than jammed
 * against an end.
 */
export const PLASMA_SHEET_BETA_LOG_RANGE: readonly [number, number] = [-3, 2];

/**
 * Where beta = 1 falls on the 0..1 normalized ramp, given the range above.
 *
 * The colour ramp's middle stop is pinned HERE rather than at 0.5, because the
 * middle stop is the whole point: it marks the surface where the two pressures
 * are equal, which is the boundary this layer exists to show. A ramp whose
 * visual midpoint sat at beta = 10^-0.5 would put the pale band a
 * half-decade inside the lobe and quietly widen the drawn sheet.
 */
export const PLASMA_SHEET_BETA_PIVOT =
  (0 - PLASMA_SHEET_BETA_LOG_RANGE[0]) / (PLASMA_SHEET_BETA_LOG_RANGE[1] - PLASMA_SHEET_BETA_LOG_RANGE[0]);

/**
 * Magnetic blue at the low end, pale at beta = 1, plasma red at the high end.
 *
 * Diverging on purpose, and diverging about a physically meaningful value
 * rather than about the middle of the data: which side of pale a colour is on
 * is a statement about which pressure is in charge there.
 */
export const PLASMA_SHEET_PALETTE: readonly [number, number, number] = [0x172a63, 0xf2ede0, 0xd9482a];

/** The same ramp as CSS, with the pivot stop where the shader puts it. */
export const PLASMA_SHEET_GRADIENT_CSS =
  `linear-gradient(90deg, #172a63, #f2ede0 ${(PLASMA_SHEET_BETA_PIVOT * 100).toFixed(0)}%, #d9482a)`;

/** Bits this module adds beyond the source mask bits it propagates. */
export const PLASMA_SHEET_MASK = {
  /** beta rests on a source value that sat on its own encoding endpoint. */
  sourceBounded: 16,
  /** beta fell outside the drawn ramp and is painted at an endpoint. */
  displayClamped: 32,
} as const;

export interface PlasmaFieldEncoding {
  scale: "linear" | "log10";
  minimum: number;
  maximum: number;
  units: string;
}

/**
 * The physical value behind one normalized 0..1 sample.
 *
 * The artifact stores every plane field as a uint16 fraction of its declared
 * encoding range, and the decoder in `geospace-slice-data.ts` hands back that
 * fraction. Turning it back into nPa or nT is this one line, and it lives here
 * so the beta arithmetic and the tests share exactly one copy of it.
 */
export function physicalFromNormalized(normalized: number, encoding: PlasmaFieldEncoding): number {
  if (!Number.isFinite(normalized)) return Number.NaN;
  const value = encoding.minimum + normalized * (encoding.maximum - encoding.minimum);
  return encoding.scale === "log10" ? 10 ** value : value;
}

export interface PlasmaBetaCounts {
  /** Cells where both sources published a value and beta is defined. */
  valid: number;
  /** Cells where either source was masked missing, or beta is undefined. */
  missing: number;
  /** Valid cells whose beta is a bound because a source hit its encoding end. */
  sourceBounded: number;
  /** Valid cells painted at a ramp endpoint because beta left the drawn range. */
  displayClamped: number;
  /** Valid cells carrying a display-grid interpolation flag from either source. */
  interpolated: number;
  /** Valid cells at or above the conventional beta = 1 threshold. */
  aboveThreshold: number;
}

export interface PlasmaBetaPlaneField {
  /** Ramp position 0..1 of log10 beta. NaN where beta is not defined. */
  values: Float32Array;
  /** log10 beta itself, unclamped, for measurement. NaN where undefined. */
  log10Beta: Float32Array;
  /** Source mask bits, ORed, plus this module's own two bits. */
  masks: Uint8Array;
  counts: PlasmaBetaCounts;
}

function emptyCounts(): PlasmaBetaCounts {
  return { valid: 0, missing: 0, sourceBounded: 0, displayClamped: 0, interpolated: 0, aboveThreshold: 0 };
}

const SOURCE_CLIPPED = GEOSPACE_SLICE_MASK.clippedLow | GEOSPACE_SLICE_MASK.clippedHigh;

/**
 * beta at every sample of one cut plane, from the plane's own pressure and
 * |B| samples.
 *
 * The two inputs are the SAME plane prepared two ways, so they share a point
 * ordering and a grid: index i is one place in space in both. That is what
 * makes a cell-by-cell ratio legitimate here and it is asserted rather than
 * assumed — a length mismatch returns null instead of silently pairing
 * unrelated points.
 *
 * On the smoothed display grid the smoothing has already happened, in each
 * field's own log-normalized space, before the division. That ordering matters
 * and it is the honest one: smoothing log p and log B and then dividing is a
 * geometric mean of neighbouring betas, which cannot manufacture a beta
 * outside the range its contributors occupied. Dividing first and smoothing
 * after could.
 */
export function plasmaBetaPlaneField(
  pressure: { values: ArrayLike<number>; masks: ArrayLike<number> },
  magneticField: { values: ArrayLike<number>; masks: ArrayLike<number> },
  encodings: { pressure: PlasmaFieldEncoding; magneticField: PlasmaFieldEncoding },
): PlasmaBetaPlaneField | null {
  const count = pressure.values.length;
  if (
    count === 0
    || magneticField.values.length !== count
    || pressure.masks.length !== count
    || magneticField.masks.length !== count
  ) return null;

  const [logLow, logHigh] = PLASMA_SHEET_BETA_LOG_RANGE;
  const span = logHigh - logLow;
  const values = new Float32Array(count);
  const log10Beta = new Float32Array(count);
  const masks = new Uint8Array(count);
  const counts = emptyCounts();

  for (let index = 0; index < count; index += 1) {
    const pressureMask = pressure.masks[index]! & 0xff;
    const magneticMask = magneticField.masks[index]! & 0xff;
    const combined = pressureMask | magneticMask;
    const beta = plasmaBeta(
      physicalFromNormalized(pressure.values[index]!, encodings.pressure),
      physicalFromNormalized(magneticField.values[index]!, encodings.magneticField),
    );
    if ((combined & GEOSPACE_SLICE_MASK.missing) !== 0 || !Number.isFinite(beta) || beta <= 0) {
      values[index] = Number.NaN;
      log10Beta[index] = Number.NaN;
      masks[index] = combined | GEOSPACE_SLICE_MASK.missing;
      counts.missing += 1;
      continue;
    }
    const logBeta = Math.log10(beta);
    const normalized = (logBeta - logLow) / span;
    let mask = combined;
    if ((combined & SOURCE_CLIPPED) !== 0) {
      mask |= PLASMA_SHEET_MASK.sourceBounded;
      counts.sourceBounded += 1;
    }
    if (normalized < 0 || normalized > 1) {
      mask |= PLASMA_SHEET_MASK.displayClamped;
      counts.displayClamped += 1;
    }
    if ((combined & GEOSPACE_SLICE_MASK.interpolated) !== 0) counts.interpolated += 1;
    if (beta >= PLASMA_SHEET_BETA_THRESHOLD) counts.aboveThreshold += 1;
    values[index] = Math.min(1, Math.max(0, normalized));
    log10Beta[index] = logBeta;
    masks[index] = mask;
    counts.valid += 1;
  }
  return { values, log10Beta, masks, counts };
}

/** A regular display grid of log10 beta: the shape the measurements need. */
export interface PlasmaBetaGrid {
  width: number;
  height: number;
  /** [minimumX, maximumX, minimumCross, maximumCross] in Earth radii. */
  boundsRe: readonly [number, number, number, number];
  /** Row-major, x varying fastest, matching `SmoothedAdaptivePlaneField`. */
  log10Beta: Float32Array;
}

export interface PlasmaSheetWindow {
  /** Tailward end of the measured window, in GSM x. */
  minimumXRe: number;
  /**
   * Earthward end. The sheet is only a sheet down-tail of the inner
   * magnetosphere; inside about 8 Re the same high-beta test picks up the ring
   * current and the inner edge, which are different objects with different
   * names, so the measurement stops there rather than renaming them.
   */
  maximumXRe: number;
  /**
   * How far off the cut's centre line to look. Wide enough to contain the
   * warped sheet in every published frame (it sits 3-4 Re off centre under
   * August's dipole tilt) and narrow enough to stay inside the lobes: the
   * magnetopause and the shocked sheath outside it are ALSO high beta, and a
   * window that reached them would measure the magnetosphere's whole width and
   * call it a plasma sheet.
   */
  maximumCrossRe: number;
}

export const PLASMA_SHEET_MEASUREMENT_WINDOW: PlasmaSheetWindow = {
  minimumXRe: -40,
  maximumXRe: -8,
  maximumCrossRe: 12,
};

/** Where the sheet's thickness is quoted on the key card. */
export const PLASMA_SHEET_REFERENCE_X_RE = -15;

/**
 * What this layer claims, and what it refuses to claim, in one place.
 *
 * ONE copy, imported by both the runtime (which stamps it into the layer's
 * metadata) and the key card (which prints it, including in the states where
 * no metadata exists yet). A second copy would be a sentence that could drift
 * out of agreement with the code, and the caveat is the part that must not.
 */
export const PLASMA_SHEET_REPRESENTATION =
  "Plasma β = thermal pressure / magnetic pressure, formed point by point from the NOAA BATS-R-US "
  + "pressure and |B| samples of the same published cut. No third quantity enters it.";

export const PLASMA_SHEET_LIMITATION =
  "β = 1 is the CONVENTIONAL plasma-sheet edge, applied here to simulation output: it is a threshold this "
  + "site draws, not a boundary NOAA publishes, and it is a model result rather than a measured crossing. "
  + "β alone does not identify the sheet either — the shocked magnetosheath outside the magnetopause and "
  + "the solar wind beyond it are high-β too. The plasma sheet is the high-β region BETWEEN the two lobes, "
  + "which is why the thickness above is measured only inside a stated tail window and never on the dayside.";

export interface PlasmaSheetColumn {
  xRe: number;
  /** Cross-plane coordinate of the beta maximum: the sheet's centre here. */
  centreCrossRe: number;
  peakBeta: number;
  /** Half the contiguous beta >= 1 run through the centre, in Re. */
  halfThicknessRe: number | null;
  lowerEdgeCrossRe: number | null;
  upperEdgeCrossRe: number | null;
  /**
   * The beta >= 1 run reached the edge of the measured window, so the
   * thickness above is a LOWER BOUND on the real one. Reported, never hidden.
   */
  truncated: boolean;
}

function gridSteps(grid: PlasmaBetaGrid) {
  const [minimumX, maximumX, minimumCross, maximumCross] = grid.boundsRe;
  return {
    minimumX,
    minimumCross,
    xStep: grid.width > 1 ? (maximumX - minimumX) / (grid.width - 1) : 0,
    crossStep: grid.height > 1 ? (maximumCross - minimumCross) / (grid.height - 1) : 0,
  };
}

/**
 * Scan each tail column of the display grid for the beta >= 1 sheet.
 *
 * Column by column: find the beta maximum inside the window, walk outward from
 * it until beta drops below 1 in each direction, and interpolate the crossing
 * linearly in log10 beta between the two straddling rows so the edge is not
 * quantized to the half-Re display grid. A column whose maximum never reaches
 * beta = 1 yields a centre and a peak but no thickness — that is a real state
 * (a thin or absent sheet at that distance) and it is reported as null rather
 * than as zero.
 *
 * The walk stops at the first missing cell as well as at the first sub-unity
 * one, so a run can never jump a hole in the published grid.
 */
export function plasmaSheetColumns(
  grid: PlasmaBetaGrid,
  window: PlasmaSheetWindow = PLASMA_SHEET_MEASUREMENT_WINDOW,
): PlasmaSheetColumn[] {
  if (grid.width < 2 || grid.height < 3) return [];
  const { minimumX, minimumCross, xStep, crossStep } = gridSteps(grid);
  if (!(xStep > 0) || !(crossStep > 0)) return [];
  const columns: PlasmaSheetColumn[] = [];
  const logThreshold = Math.log10(PLASMA_SHEET_BETA_THRESHOLD);

  for (let column = 0; column < grid.width; column += 1) {
    const xRe = minimumX + column * xStep;
    if (xRe < window.minimumXRe || xRe > window.maximumXRe) continue;
    let firstRow = -1;
    let lastRow = -1;
    let peakRow = -1;
    let peakLog = Number.NEGATIVE_INFINITY;
    for (let row = 0; row < grid.height; row += 1) {
      const cross = minimumCross + row * crossStep;
      if (Math.abs(cross) > window.maximumCrossRe) continue;
      if (firstRow < 0) firstRow = row;
      lastRow = row;
      const value = grid.log10Beta[row * grid.width + column]!;
      if (!Number.isFinite(value)) continue;
      if (value > peakLog) {
        peakLog = value;
        peakRow = row;
      }
    }
    if (peakRow < 0) continue;
    const centreCrossRe = minimumCross + peakRow * crossStep;
    const peakBeta = 10 ** peakLog;
    if (peakLog < logThreshold) {
      columns.push({
        xRe,
        centreCrossRe,
        peakBeta,
        halfThicknessRe: null,
        lowerEdgeCrossRe: null,
        upperEdgeCrossRe: null,
        truncated: false,
      });
      continue;
    }

    /** Walk from the peak toward `step` until beta drops below the threshold. */
    const edge = (step: -1 | 1) => {
      let row = peakRow;
      while (true) {
        const next = row + step;
        if (next < firstRow || next > lastRow) return { cross: minimumCross + row * crossStep, truncated: true };
        const value = grid.log10Beta[next * grid.width + column]!;
        if (!Number.isFinite(value)) return { cross: minimumCross + row * crossStep, truncated: true };
        if (value < logThreshold) {
          const inside = grid.log10Beta[row * grid.width + column]!;
          const fraction = (inside - logThreshold) / (inside - value);
          return { cross: minimumCross + (row + step * fraction) * crossStep, truncated: false };
        }
        row = next;
      }
    };
    const lower = edge(-1);
    const upper = edge(1);
    columns.push({
      xRe,
      centreCrossRe,
      peakBeta,
      halfThicknessRe: (upper.cross - lower.cross) / 2,
      lowerEdgeCrossRe: lower.cross,
      upperEdgeCrossRe: upper.cross,
      truncated: lower.truncated || upper.truncated,
    });
  }
  return columns;
}

export interface PlasmaSheetMetrics {
  /** Columns of the display grid inside the measured window. */
  columnCount: number;
  /** Of those, the ones where beta reaches the threshold at all. */
  resolvedColumnCount: number;
  /** Largest beta anywhere in the measured window. */
  peakBeta: number | null;
  /** Where the two numbers below are quoted, in GSM x. */
  referenceXRe: number;
  halfThicknessRe: number | null;
  centreCrossRe: number | null;
  /** Whether the quoted thickness is a lower bound (the run hit the window). */
  referenceTruncated: boolean;
  /** How far the sheet's centre wanders across the measured window, in Re. */
  centreRangeRe: [number, number] | null;
  /**
   * Whether the z = 0 plane — the equatorial cut this site also publishes —
   * lies inside the beta >= 1 sheet at the reference distance. Under a tilted
   * dipole it very often does NOT, and a reader who assumed the equatorial cut
   * shows the plasma sheet would be reading the lobe. Null when the reference
   * column resolves no sheet at all.
   */
  equatorialCutInsideSheet: boolean | null;
  window: PlasmaSheetWindow;
}

/** Nearest resolved column to a requested x, or null when none resolves. */
function columnAt(columns: readonly PlasmaSheetColumn[], xRe: number) {
  let best: PlasmaSheetColumn | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const column of columns) {
    const distance = Math.abs(column.xRe - xRe);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = column;
    }
  }
  return best;
}

/**
 * The handful of numbers the key card quotes, from the column scan.
 *
 * Every one of them is a measurement of the published model output inside a
 * stated window, not a fitted or assumed value, and each is null rather than
 * substituted when the frame does not support it.
 */
export function plasmaSheetMetrics(
  columns: readonly PlasmaSheetColumn[],
  referenceXRe: number = PLASMA_SHEET_REFERENCE_X_RE,
  window: PlasmaSheetWindow = PLASMA_SHEET_MEASUREMENT_WINDOW,
): PlasmaSheetMetrics {
  const resolved = columns.filter((column) => column.halfThicknessRe !== null);
  const peakBeta = columns.length === 0
    ? null
    : columns.reduce((highest, column) => Math.max(highest, column.peakBeta), Number.NEGATIVE_INFINITY);
  const reference = columnAt(resolved, referenceXRe);
  const centres = resolved.map((column) => column.centreCrossRe);
  const insideSheet = reference === null || reference.halfThicknessRe === null
    ? null
    : reference.lowerEdgeCrossRe! <= 0 && reference.upperEdgeCrossRe! >= 0;
  return {
    columnCount: columns.length,
    resolvedColumnCount: resolved.length,
    peakBeta: peakBeta === null || !Number.isFinite(peakBeta) ? null : peakBeta,
    referenceXRe,
    halfThicknessRe: reference?.halfThicknessRe ?? null,
    centreCrossRe: reference?.centreCrossRe ?? null,
    referenceTruncated: reference?.truncated ?? false,
    centreRangeRe: centres.length === 0 ? null : [Math.min(...centres), Math.max(...centres)],
    equatorialCutInsideSheet: insideSheet,
    window,
  };
}

/**
 * The beta field as a `SmoothedAdaptivePlaneField`, so the shared
 * marching-squares contour tracer can draw the beta = 1 curve without a second
 * implementation of it. The values it carries are ramp positions, which is
 * exactly what the contour level below is expressed in.
 */
export function betaContourSource(
  prepared: SmoothedAdaptivePlaneField,
  beta: PlasmaBetaPlaneField,
): SmoothedAdaptivePlaneField {
  return {
    mode: "smooth",
    width: prepared.width,
    height: prepared.height,
    boundsRe: prepared.boundsRe,
    values: beta.values,
    masks: beta.masks,
  };
}

/** Where beta = 1 sits on the normalized ramp; the contour level to trace. */
export const PLASMA_SHEET_CONTOUR_LEVEL = PLASMA_SHEET_BETA_PIVOT;

/**
 * The diverging beta surface.
 *
 * A near-copy of the plasma cut's own surface material, with one deliberate
 * difference: the middle colour is placed at `pivot` rather than at the ramp's
 * halfway point, because the middle colour here is not decoration but the
 * beta = 1 surface itself. Opacity is flat for the same reason the plasma cut
 * made it flat — the low half of a value-keyed alpha ramp fades the tail lobes
 * into the black sky, and a lobe is data, not absence.
 */
export function plasmaBetaSurfaceMaterial(pivot: number = PLASMA_SHEET_BETA_PIVOT) {
  return new THREE.ShaderMaterial({
    uniforms: {
      lowColor: { value: new THREE.Color(PLASMA_SHEET_PALETTE[0]) },
      middleColor: { value: new THREE.Color(PLASMA_SHEET_PALETTE[1]) },
      highColor: { value: new THREE.Color(PLASMA_SHEET_PALETTE[2]) },
      pivot: { value: Math.min(0.999, Math.max(0.001, pivot)) },
    },
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    vertexShader: `
      attribute float fieldValue;
      attribute float dataValid;
      varying float valueForColor;
      varying float validForColor;
      void main() {
        valueForColor = fieldValue;
        validForColor = dataValid;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 lowColor;
      uniform vec3 middleColor;
      uniform vec3 highColor;
      uniform float pivot;
      varying float valueForColor;
      varying float validForColor;
      void main() {
        if (validForColor < 0.999) discard;
        float value = clamp(valueForColor, 0.0, 1.0);
        vec3 color = value < pivot
          ? mix(lowColor, middleColor, value / pivot)
          : mix(middleColor, highColor, (value - pivot) / (1.0 - pivot));
        gl_FragColor = vec4(color, 0.84);
      }
    `,
  });
}

/** The same ramp for the native adaptive samples, drawn as points. */
export function plasmaBetaPointMaterial(
  pointSize: number,
  pixelRatio: number,
  pivot: number = PLASMA_SHEET_BETA_PIVOT,
) {
  return new THREE.ShaderMaterial({
    uniforms: {
      lowColor: { value: new THREE.Color(PLASMA_SHEET_PALETTE[0]) },
      middleColor: { value: new THREE.Color(PLASMA_SHEET_PALETTE[1]) },
      highColor: { value: new THREE.Color(PLASMA_SHEET_PALETTE[2]) },
      pivot: { value: Math.min(0.999, Math.max(0.001, pivot)) },
      pointSize: { value: pointSize },
      pixelRatio: { value: Math.max(0.25, pixelRatio) },
    },
    transparent: true,
    depthWrite: false,
    vertexShader: `
      attribute float fieldValue;
      attribute float dataValid;
      uniform float pointSize;
      uniform float pixelRatio;
      varying float valueForColor;
      varying float validForColor;
      void main() {
        valueForColor = fieldValue;
        validForColor = dataValid;
        gl_PointSize = dataValid > 0.5 ? pointSize * pixelRatio : 0.0;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 lowColor;
      uniform vec3 middleColor;
      uniform vec3 highColor;
      uniform float pivot;
      varying float valueForColor;
      varying float validForColor;
      void main() {
        if (validForColor < 0.5) discard;
        float radius = length(gl_PointCoord - vec2(0.5));
        if (radius > 0.5) discard;
        float value = clamp(valueForColor, 0.0, 1.0);
        vec3 color = value < pivot
          ? mix(lowColor, middleColor, value / pivot)
          : mix(middleColor, highColor, (value - pivot) / (1.0 - pivot));
        gl_FragColor = vec4(color, 1.0 - smoothstep(0.34, 0.5, radius));
      }
    `,
  });
}

/** The traced beta = 1 curve, and the sheet's measured centre line. */
export const PLASMA_SHEET_LINE_COLORS = {
  /** The conventional boundary. Pale, matching the ramp's pivot colour. */
  boundary: 0xfff3d8,
  /** The locus of maximum beta: where the sheet's middle actually is. */
  centre: 0xff9d5c,
} as const;

/**
 * Whether a prepared field is on the regular display grid. Only that form can
 * be column-scanned, and the measurement refuses rather than approximates on
 * the native adaptive samples.
 */
export function isSmoothPlaneField(
  prepared: PreparedAdaptivePlaneField | null,
): prepared is SmoothedAdaptivePlaneField {
  return prepared !== null && prepared.mode === "smooth";
}
