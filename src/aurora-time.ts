export interface AuroraGrid {
  longitudeStartDeg: number;
  longitudeStepDeg: number;
  longitudeCount: number;
  latitudeStartDeg: number;
  latitudeStepDeg: number;
  latitudeCount: number;
  order: "latitude-major, south-to-north, west-to-east";
  longitudeConvention: string;
  sourceCoordinateOrder: string;
}

export interface AuroraFrame {
  observedAt: string;
  validAt: string;
  leadMinutes: number;
  probabilityU8: string;
  validityBits: string;
  validCellCount: number;
  missingCellCount: number;
  maximumProbabilityPercent: number;
  hemispheres: {
    north: AuroraHemisphereSummary;
    south: AuroraHemisphereSummary;
  };
}

export interface AuroraHemisphereSummary {
  validCellCount: number;
  maximumProbabilityPercent: number | null;
}

export interface AuroraNoDataInterval {
  from: string;
  to: string;
  reason: "before-bigmem-accumulation" | "snapshot-gap" | "after-latest-frame";
}

export interface AuroraActiveForecastWindow {
  sourceObservedAt: string;
  forecastValidAt: string;
  feedRetrievedAt: string;
  selectionWindowMinutes: number;
  definition: string;
}

export interface AuroraBundle {
  schemaVersion: "noaa-ovation-history.v1";
  product: string;
  status: "model";
  temporalKind: "observation-driven forecast";
  retrievedAt: string;
  source: {
    currentNumericGrid: string;
    productPage: string;
    wmoProductPage: string;
    northImageHistoryManifest: string;
    southImageHistoryManifest: string;
    nceiProductInventory: string;
    model: "OVATION 2020";
    inputs: string;
    sourceCadenceMinutes: number;
  };
  sourceAvailability: {
    publicNumericDistribution: "latest grid only";
    publicRenderedImageHistoryHours: 24;
    publicNumericHistoryHours: 0;
    historyMethod: string;
    notUsed: string;
    inventoryCheckedAt: string;
  };
  grid: AuroraGrid;
  encoding: {
    probability: "uint8-base64";
    validity: "bitset-lsb-first-base64";
    validRangePercent: [0, 100];
    missingRepresentation: string;
  };
  quantity: {
    name: string;
    units: "%";
    definition: string;
  };
  time: {
    requestedHistoryHours: number;
    requestedFrom: string;
    requestedTo: string;
    availableFrom: string;
    availableTo: string;
    frameCount: number;
    coverageComplete: boolean;
    noDataIntervals: AuroraNoDataInterval[];
    selection: string;
    staleAfterMinutes: number;
    forecastLead: string;
    activeForecast?: AuroraActiveForecastWindow;
  };
  display: {
    defaultMode: "smooth";
    nativeModeAvailable: true;
    smoothing: string;
    hemispheres: ["north", "south"];
    /** Absent from artifacts published before the seam was characterized. */
    equatorialSeam?: {
      observed: string;
      handling: string;
      bandLatitudeDeg: number;
      isolationLatitudeDeg: number;
      guard: string;
      sourceBytesModified: false;
    };
  };
  frames: AuroraFrame[];
  limitations: string[];
}

export interface DecodedAuroraFrame {
  probabilityPercent: Uint8Array;
  valid: Uint8Array;
  equatorialSeam: AuroraEquatorialSeam | null;
}

/**
 * One removed equatorial-seam artifact, reported so the masking is auditable
 * instead of silent. `maximumProbabilityPercent` is the largest source value
 * that was withdrawn; the source bytes themselves are never rewritten.
 */
export interface AuroraEquatorialSeam {
  fromLatitudeDeg: number;
  toLatitudeDeg: number;
  latitudeRowCount: number;
  cellCount: number;
  maximumProbabilityPercent: number;
  isolationDeg: number;
}

export interface AvailableAuroraSelection {
  available: true;
  frame: AuroraFrame;
  ageMinutes: number;
  held: boolean;
  sourceLeadMinutes: number;
  selectionBasis: "forecast-valid-time" | "active-latest-forecast";
  forecastMinutesUntilValid: number;
  feedRetrievedAt: string | null;
  coverage: AuroraCoverageSummary;
}

export interface MissingAuroraSelection {
  available: false;
  reason: "invalid-time" | "before-coverage" | "gap" | "after-coverage";
  message: string;
  coverage: AuroraCoverageSummary;
}

export type AuroraTimeSelection = AvailableAuroraSelection | MissingAuroraSelection;

export interface AuroraCoverageSummary {
  availableFrom: string | null;
  availableTo: string | null;
  frameCount: number;
  complete: boolean;
}

export type AuroraDisplayMode = "smooth" | "native";

export interface ResampledAuroraGrid extends DecodedAuroraFrame {
  width: number;
  height: number;
}

export interface AuroraRgbaGrid {
  width: number;
  height: number;
  rgba: Uint8ClampedArray;
  equatorialSeam: AuroraEquatorialSeam | null;
}

/**
 * NOAA's global OVATION grid carries a numerical seam where its two
 * hemispheric solutions meet the 0 degree geographic latitude row. Measured
 * over 198 consecutive five-minute grids (2026-08-06 22:43Z to 2026-08-07
 * 22:28Z) the seam occupied at most the rows from 2 degrees south to the
 * equator, grew monotonically toward the equator (0.9%, 1.8%, 3.5% mean at
 * 2S/1S/0), reached 1-4%, and was always separated from the real southern oval
 * by 37 to 45 latitude rows of exactly zero probability. A real auroral oval
 * cannot be disconnected from the polar cap, and it cannot brighten as it
 * approaches the equator, so those cells carry no auroral information.
 *
 * They are withdrawn as MISSING rather than rewritten to zero, and only when
 * both guards hold: the run of probability-bearing rows never leaves the
 * equatorial band, and it is separated from every other probability-bearing
 * row by at least the isolation distance. A genuine equatorward expansion is
 * spatially continuous with the oval, so it fails both guards and is drawn
 * untouched — including the historic extremes, which reached roughly 20
 * degrees geographic latitude, four times the band bound.
 */
export const AURORA_EQUATORIAL_SEAM_GUARDS = {
  /** Half-width of the band a seam artifact must never leave, in degrees. */
  bandLatitudeDeg: 5,
  /** Degrees of probability-free latitude that must separate it from real signal. */
  isolationLatitudeDeg: 10,
} as const;

export const AURORA_DISPLAY_MODES = {
  smooth: {
    label: "Smooth",
    description: "Default spatial interpolation for presentation. It preserves NOAA's missing mask and cannot create probabilities outside source-cell extrema.",
  },
  native: {
    label: "Native 1° grid",
    description: "Unresampled NOAA probabilities for both hemispheres.",
  },
} as const satisfies Record<AuroraDisplayMode, { label: string; description: string }>;

export const AURORA_DATA_METHOD = {
  status: "model",
  label: "NOAA OVATION 2020 forecast",
  title: "Aurora viewing probability",
  summary: "A global empirical forecast driven by L1 solar-wind and interplanetary-magnetic-field measurements, with a Kp fallback when those inputs are unavailable.",
  processing: "bigmem snapshots each exact public NOAA numeric grid. History selects by NOAA forecast-valid time; only the current latest grid may appear briefly before that time as a clearly labeled active forecast. The source mask is preserved, and missing history is never filled or interpolated.",
  history: "NOAA publicly exposes only the latest numeric grid; its 24-hour north/south loops are rendered images. Numeric history therefore begins when bigmem accumulation starts.",
  limitation: "This is model probability under dark, clear conditions—not an optical observation. Daylight, clouds, terrain, and light pollution can prevent viewing.",
  url: "https://www.spaceweather.gov/products/aurora-30-minute-forecast",
} as const;

/**
 * Selects strict history by forecast-valid time. The sole exception is the
 * latest grid during its short, near-live feed window: it may be shown before
 * its future valid time as an explicitly labeled active forecast, never as an
 * observation or a reconstructed historical value.
 */
export function selectAuroraFrame(bundle: AuroraBundle, requestedAt: Date | string | number): AuroraTimeSelection {
  const coverage = auroraCoverage(bundle);
  const requestedMs = toTimeMs(requestedAt);
  if (requestedMs === null) {
    return { available: false, reason: "invalid-time", message: "Invalid UTC selection.", coverage };
  }

  const chronological = bundle.frames
    .map((frame) => ({ frame, validMs: Date.parse(frame.validAt) }))
    .filter((entry) => Number.isFinite(entry.validMs))
    .sort((a, b) => a.validMs - b.validMs);
  if (chronological.length === 0) {
    return { available: false, reason: "before-coverage", message: "No valid NOAA OVATION frames are loaded.", coverage };
  }
  const first = chronological[0]!;
  const last = chronological.at(-1)!;
  const activeForecast = selectActiveLatestForecast(bundle, chronological, requestedMs);
  if (activeForecast) return activeForecast;
  if (requestedMs < first.validMs) {
    return {
      available: false,
      reason: "before-coverage",
      message: `No native OVATION grid is available before ${formatUtc(first.frame.validAt)}; bigmem accumulation does not reconstruct NOAA's image history.`,
      coverage,
    };
  }

  let lower = 0;
  let upper = chronological.length - 1;
  let selectedIndex = 0;
  while (lower <= upper) {
    const middle = Math.floor((lower + upper) / 2);
    if (chronological[middle]!.validMs <= requestedMs) {
      selectedIndex = middle;
      lower = middle + 1;
    } else {
      upper = middle - 1;
    }
  }
  const selected = chronological[selectedIndex]!;
  const ageMinutes = (requestedMs - selected.validMs) / 60_000;
  if (ageMinutes > bundle.time.staleAfterMinutes) {
    const afterLast = requestedMs > last.validMs;
    return {
      available: false,
      reason: afterLast ? "after-coverage" : "gap",
      message: afterLast
        ? `Latest native OVATION grid is ${Math.floor(ageMinutes)} minutes older than this selection.`
        : `No native OVATION grid covers this cache gap; the preceding frame is ${Math.floor(ageMinutes)} minutes old.`,
      coverage,
    };
  }
  return {
    available: true,
    frame: selected.frame,
    ageMinutes,
    held: ageMinutes > 0,
    sourceLeadMinutes: selected.frame.leadMinutes,
    selectionBasis: "forecast-valid-time",
    forecastMinutesUntilValid: 0,
    feedRetrievedAt: null,
    coverage,
  };
}

export function decodeAuroraFrame(bundle: AuroraBundle, frame: AuroraFrame): DecodedAuroraFrame {
  if (bundle.encoding.probability !== "uint8-base64" || bundle.encoding.validity !== "bitset-lsb-first-base64") {
    throw new Error("Unsupported OVATION probability encoding");
  }
  const expectedCells = bundle.grid.longitudeCount * bundle.grid.latitudeCount;
  const probabilityPercent = decodeBase64(frame.probabilityU8);
  const validityBits = decodeBase64(frame.validityBits);
  if (probabilityPercent.length !== expectedCells) {
    throw new Error(`OVATION probability grid has ${probabilityPercent.length} cells; expected ${expectedCells}`);
  }
  if (validityBits.length !== Math.ceil(expectedCells / 8)) {
    throw new Error(`OVATION validity mask has ${validityBits.length} bytes; expected ${Math.ceil(expectedCells / 8)}`);
  }
  const valid = new Uint8Array(expectedCells);
  for (let index = 0; index < expectedCells; index += 1) {
    valid[index] = (validityBits[index >> 3]! >> (index & 7)) & 1;
    if (valid[index] && probabilityPercent[index]! > 100) {
      throw new Error(`OVATION probability ${probabilityPercent[index]} is outside 0–100%`);
    }
  }
  // Every consumer decodes through here, so the seam withdrawal cannot be
  // bypassed by a future sampler, legend, or renderer.
  const equatorialSeam = withdrawEquatorialSeam(bundle.grid, probabilityPercent, valid);
  return { probabilityPercent, valid, equatorialSeam };
}

/**
 * Detects NOAA's equatorial grid seam and clears its validity bits in place.
 * Source probability bytes are left byte-for-byte unchanged, so the cells read
 * as missing rather than as a modeled zero. Returns null when no run of
 * probability-bearing rows satisfies both guards, which is the ordinary case
 * for any real auroral field.
 */
function withdrawEquatorialSeam(
  grid: AuroraGrid,
  probabilityPercent: Uint8Array,
  valid: Uint8Array,
): AuroraEquatorialSeam | null {
  const width = grid.longitudeCount;
  const height = grid.latitudeCount;
  const step = grid.latitudeStepDeg;
  if (!Number.isFinite(step) || step === 0 || width <= 0 || height <= 0) return null;
  const latitudeOf = (row: number) => grid.latitudeStartDeg + row * step;

  const bearing = new Uint8Array(height);
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      const index = row * width + column;
      if (valid[index] && probabilityPercent[index]! > 0) {
        bearing[row] = 1;
        break;
      }
    }
  }

  // Walk the maximal runs of consecutive probability-bearing rows once.
  const runs: Array<{ start: number; end: number }> = [];
  for (let row = 0; row < height; row += 1) {
    if (!bearing[row]) continue;
    const start = row;
    while (row + 1 < height && bearing[row + 1]) row += 1;
    runs.push({ start, end: row });
  }

  const { bandLatitudeDeg, isolationLatitudeDeg } = AURORA_EQUATORIAL_SEAM_GUARDS;
  for (let position = 0; position < runs.length; position += 1) {
    const run = runs[position]!;
    const first = latitudeOf(run.start);
    const last = latitudeOf(run.end);
    // Guard one: the run never leaves the equatorial band.
    if (Math.max(Math.abs(first), Math.abs(last)) > bandLatitudeDeg) continue;
    // Guard two: no other probability-bearing row lies within the isolation
    // distance, so the run cannot be part of a continuous auroral structure.
    const previous = runs[position - 1];
    const following = runs[position + 1];
    const gapBefore = previous ? Math.abs(first - latitudeOf(previous.end)) : Number.POSITIVE_INFINITY;
    const gapAfter = following ? Math.abs(latitudeOf(following.start) - last) : Number.POSITIVE_INFINITY;
    const isolation = Math.min(gapBefore, gapAfter);
    if (isolation < isolationLatitudeDeg) continue;

    let cellCount = 0;
    let maximumProbabilityPercent = 0;
    for (let row = run.start; row <= run.end; row += 1) {
      for (let column = 0; column < width; column += 1) {
        const index = row * width + column;
        if (!valid[index]) continue;
        if (probabilityPercent[index]! > maximumProbabilityPercent) maximumProbabilityPercent = probabilityPercent[index]!;
        valid[index] = 0;
        cellCount += 1;
      }
    }
    return {
      fromLatitudeDeg: Math.min(first, last),
      toLatitudeDeg: Math.max(first, last),
      latitudeRowCount: run.end - run.start + 1,
      cellCount,
      maximumProbabilityPercent,
      isolationDeg: Number.isFinite(isolation) ? isolation : Math.abs(step) * height,
    };
  }
  return null;
}

/** Spatial smoothing only. Source probabilities and validity bytes are never mutated. */
export function resampleAuroraFrame(
  bundle: AuroraBundle,
  decoded: DecodedAuroraFrame,
  mode: AuroraDisplayMode = "smooth",
  smoothFactor = 2,
): ResampledAuroraGrid {
  const sourceWidth = bundle.grid.longitudeCount;
  const sourceHeight = bundle.grid.latitudeCount;
  const expectedCells = sourceWidth * sourceHeight;
  if (decoded.probabilityPercent.length !== expectedCells || decoded.valid.length !== expectedCells) {
    throw new Error(`OVATION decoded grid must contain ${expectedCells} cells`);
  }
  if (mode === "native") {
    return {
      width: sourceWidth,
      height: sourceHeight,
      probabilityPercent: decoded.probabilityPercent.slice(),
      valid: decoded.valid.slice(),
      equatorialSeam: decoded.equatorialSeam,
    };
  }
  if (!Number.isInteger(smoothFactor) || smoothFactor < 1 || smoothFactor > 8) {
    throw new Error("OVATION smooth factor must be an integer from 1 to 8");
  }

  const width = sourceWidth * smoothFactor;
  const height = (sourceHeight - 1) * smoothFactor + 1;
  const probabilityPercent = new Uint8Array(width * height);
  const valid = new Uint8Array(width * height);
  for (let y = 0; y < height; y += 1) {
    const sourceY = y / smoothFactor;
    const y0 = Math.floor(sourceY);
    const y1 = Math.min(y0 + 1, sourceHeight - 1);
    const nearestY = Math.min(Math.round(sourceY), sourceHeight - 1);
    const yAmount = sourceY - y0;
    for (let x = 0; x < width; x += 1) {
      const sourceX = x / smoothFactor;
      const x0 = Math.floor(sourceX) % sourceWidth;
      const x1 = (x0 + 1) % sourceWidth;
      const nearestX = Math.round(sourceX) % sourceWidth;
      const xAmount = sourceX - Math.floor(sourceX);
      const nearestIndex = nearestY * sourceWidth + nearestX;
      const destination = y * width + x;

      // A nearest-cell mask prevents interpolation from painting through a
      // missing source area. Touching a missing corner falls back to the exact
      // nearest source value rather than manufacturing a boundary value.
      if (!decoded.valid[nearestIndex]) continue;
      const indices = [
        y0 * sourceWidth + x0,
        y0 * sourceWidth + x1,
        y1 * sourceWidth + x0,
        y1 * sourceWidth + x1,
      ];
      if (!indices.every((index) => decoded.valid[index])) {
        probabilityPercent[destination] = decoded.probabilityPercent[nearestIndex]!;
        valid[destination] = 1;
        continue;
      }
      const top = mix(decoded.probabilityPercent[indices[0]!]!, decoded.probabilityPercent[indices[1]!]!, xAmount);
      const bottom = mix(decoded.probabilityPercent[indices[2]!]!, decoded.probabilityPercent[indices[3]!]!, xAmount);
      probabilityPercent[destination] = Math.round(mix(top, bottom, yAmount));
      valid[destination] = 1;
    }
  }
  return { width, height, probabilityPercent, valid, equatorialSeam: decoded.equatorialSeam };
}

export function auroraRgbaGrid(
  bundle: AuroraBundle,
  frame: AuroraFrame,
  options: { mode?: AuroraDisplayMode; smoothFactor?: number; opacity?: number } = {},
): AuroraRgbaGrid {
  const grid = resampleAuroraFrame(
    bundle,
    decodeAuroraFrame(bundle, frame),
    options.mode ?? "smooth",
    options.smoothFactor ?? 2,
  );
  const rgba = new Uint8ClampedArray(grid.probabilityPercent.length * 4);
  const opacity = clamp(options.opacity ?? 1, 0, 1);
  for (let index = 0; index < grid.probabilityPercent.length; index += 1) {
    if (!grid.valid[index]) continue;
    const color = auroraProbabilityColor(grid.probabilityPercent[index]!);
    const destination = index * 4;
    rgba[destination] = color[0];
    rgba[destination + 1] = color[1];
    rgba[destination + 2] = color[2];
    rgba[destination + 3] = Math.round(color[3] * opacity);
  }
  return { width: grid.width, height: grid.height, rgba, equatorialSeam: grid.equatorialSeam };
}

export function auroraProbabilityColor(probabilityPercent: number): readonly [number, number, number, number] {
  if (!Number.isFinite(probabilityPercent) || probabilityPercent <= 0 || probabilityPercent > 100) return [0, 0, 0, 0];
  const value = clamp(probabilityPercent, 0, 100);
  const amount = value / 100;
  // NOAA's global grid carries a broad 1% skirt tens of degrees equatorward of
  // the oval — measured across 40-56N and 39-46S on 2026-08-07 — which is the
  // lowest quantized bin rather than a resolved probability. Painting it makes
  // the quiet-time map read as aurora over most of the mid-latitudes. Keep the
  // source byte unchanged and reserve visible alpha for values above it. This
  // is a floor only; the disconnected equatorial seam is withdrawn as missing
  // during decoding, because it reaches 4% and no alpha floor can separate it
  // from genuinely quiet polar probability.
  const alpha = value <= 1
    ? 0
    : Math.round(32 + 193 * Math.sqrt((value - 1) / 99));
  if (amount < 0.5) {
    const phase = amount / 0.5;
    return [Math.round(mix(35, 247, phase)), Math.round(mix(216, 226, phase)), Math.round(mix(111, 75, phase)), alpha];
  }
  const phase = (amount - 0.5) / 0.5;
  return [Math.round(mix(247, 229, phase)), Math.round(mix(226, 57, phase)), Math.round(mix(75, 53, phase)), alpha];
}

export function auroraCoverage(bundle: AuroraBundle): AuroraCoverageSummary {
  return {
    availableFrom: bundle.frames[0]?.validAt ?? null,
    availableTo: bundle.frames.at(-1)?.validAt ?? null,
    frameCount: bundle.frames.length,
    complete: bundle.time.coverageComplete,
  };
}

export function formatAuroraSelection(selection: AuroraTimeSelection): string {
  if (!selection.available) return selection.message;
  const forecast = formatUtc(selection.frame.validAt);
  const observed = formatUtc(selection.frame.observedAt);
  if (selection.selectionBasis === "active-latest-forecast") {
    const retrieved = selection.feedRetrievedAt ? formatUtc(selection.feedRetrievedAt) : "unknown";
    return `Active latest forecast · input observed ${observed} · forecast valid ${forecast} (in ${Math.ceil(selection.forecastMinutesUntilValid)} min) · feed retrieved ${retrieved}`;
  }
  const held = selection.held ? ` · held ${Math.floor(selection.ageMinutes)} min` : "";
  return `${forecast} forecast valid · observed ${observed} · ${selection.sourceLeadMinutes} min lead${held}`;
}

function selectActiveLatestForecast(
  bundle: AuroraBundle,
  chronological: Array<{ frame: AuroraFrame; validMs: number }>,
  requestedMs: number,
): AvailableAuroraSelection | null {
  const metadata = bundle.time.activeForecast;
  if (!metadata) return null;
  const retrievedMs = Date.parse(metadata.feedRetrievedAt);
  const observedMs = Date.parse(metadata.sourceObservedAt);
  const validMs = Date.parse(metadata.forecastValidAt);
  const windowMinutes = metadata.selectionWindowMinutes;
  if (
    !Number.isFinite(retrievedMs)
    || !Number.isFinite(observedMs)
    || !Number.isFinite(validMs)
    || !Number.isFinite(windowMinutes)
    || windowMinutes <= 0
    || requestedMs < observedMs
    || requestedMs >= validMs
  ) return null;
  const allowanceMs = windowMinutes * 60_000;
  // This symmetric allowance covers a client clock captured just before the
  // artifact fetch and a briefly held latest feed. It cannot reach historical
  // gaps elsewhere on the 48-hour timeline.
  if (Math.abs(requestedMs - retrievedMs) > allowanceMs) return null;
  const entry = chronological.find(({ frame }) => (
    frame.validAt === metadata.forecastValidAt
    && frame.observedAt === metadata.sourceObservedAt
  ));
  if (!entry) return null;
  return {
    available: true,
    frame: entry.frame,
    ageMinutes: 0,
    held: false,
    sourceLeadMinutes: entry.frame.leadMinutes,
    selectionBasis: "active-latest-forecast",
    forecastMinutesUntilValid: (entry.validMs - requestedMs) / 60_000,
    feedRetrievedAt: metadata.feedRetrievedAt,
    coverage: auroraCoverage(bundle),
  };
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

function formatUtc(value: string): string {
  return `${value.slice(0, 16).replace("T", " ")} UTC`;
}

function mix(start: number, end: number, amount: number): number {
  return start + (end - start) * clamp(amount, 0, 1);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}
