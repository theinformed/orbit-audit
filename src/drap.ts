export interface DrapGrid {
  longitudeStartDeg: number;
  longitudeStepDeg: number;
  longitudeCount: number;
  latitudeStartDeg: number;
  latitudeStepDeg: number;
  latitudeCount: number;
  order: "latitude-major, north-to-south, west-to-east";
}

export interface DrapFrame {
  validAt: string;
  valuesU16: string;
  maximumHafMhz: number;
  affectedCellPercent: Record<"3MHz" | "10MHz" | "30MHz", number>;
}

export interface DrapBundle {
  schemaVersion: "noaa-drap.v1";
  product: string;
  status: "model";
  temporalKind: "empirical-nowcast";
  retrievedAt: string;
  source: {
    currentData: string;
    productPage: string;
    documentation: string;
    historicalArchive: string;
    historicalFilesApi: string;
    inputs: string;
    sourceCadence: string;
  };
  grid: DrapGrid;
  encoding: {
    type: "uint16-le-base64";
    scaleMhz: number;
    missingValue: number;
  };
  quantity: {
    name: "Highest Affected Frequency";
    shortName: "1 dB HAF";
    units: "MHz";
    definition: string;
    pathGeometry: "vertical two-pass";
  };
  time: {
    validFrom: string;
    validTo: string;
    frameCount: number;
    selection: string;
    staleAfterMinutes: number;
    futureAvailable: false;
  };
  legend: DrapLegend;
  messages: {
    estimatedRecovery: string | null;
    xray: string | null;
    xrayWarning: string | null;
    proton: string | null;
    protonWarning: string | null;
  };
  frames: DrapFrame[];
  limitations: string[];
  operationalDisplay: typeof DRAP_LAYER_POLICY;
}

export interface DrapLegend {
  title: string;
  subtitle: string;
  minimumDisplayedMhz: number;
  maximumDisplayedMhz: number;
  ticksMhz: number[];
  belowMinimumLabel: string;
  aboveMaximumLabel: string;
}

export interface DrapFrameSelection {
  frame: DrapFrame;
  ageMinutes: number;
  stale: boolean;
}

export interface DrapRgbaGrid {
  width: number;
  height: number;
  rgba: Uint8ClampedArray;
  condition: DrapCondition;
}

/**
 * HOW MUCH OF THIS FRAME IS ACTUALLY ON THE MAP.
 *
 * Three states, not two, because two was the defect. `none` and `active` were
 * the only answers the layer had, and `none` means *nothing reaches 3 MHz* --
 * which on the live artifact is true of 49 frames out of 446. The other 397
 * were all badged ACTIVE, including the 218 whose entire signal sits in the
 * bottom two megahertz of a 3-30 MHz scale over under a fifth of the globe and
 * is, correctly, almost invisible. Sean read one of those (peak 3.3 MHz, 4.35%
 * of cells, nothing whatever at 10 or 30 MHz) as a broken layer, and a badge
 * reading ACTIVE over an empty globe is why. `faint` is the missing word.
 */
export type DrapConditionStatus = "none" | "faint" | "active";

export interface DrapCondition {
  status: DrapConditionStatus;
  /** The card's opening sentence. Leads with the status token, then the numbers. */
  summary: string;
  /** One line under the legend's colour bar, which is the surface that is never folded away. */
  legendLine: string;
  /** The chip in the card head -- the ONLY thing a folded card shows. */
  badge: string;
  maximumHafMhz: number;
  affectedCellPercent: DrapFrame["affectedCellPercent"];
  zeroFieldPreserved: true;
}

export type DrapDisplayMode = "smooth" | "native";

export interface DrapRenderOptions {
  mode?: DrapDisplayMode;
  opacity?: number;
  smoothResolutionDegrees?: number;
  quietStateBackdrop?: boolean;
}

export const DRAP_LAYER_POLICY = {
  defaultVisible: false,
  menu: "advanced-layers",
  singleCompactLegend: true,
  assumptionDriven: false,
} as const;

export const DRAP_DISPLAY_MODES = {
  smooth: {
    label: "Smooth",
    description: "Default 1° bilinear display; preserves source missing masks and cannot create new HAF extrema.",
  },
  native: {
    label: "Native grid",
    description: "Unresampled NOAA 2° latitude × 4° longitude cells.",
  },
} as const satisfies Record<DrapDisplayMode, { label: string; description: string }>;

export const DRAP_DATA_METHOD = {
  status: "model",
  label: "NOAA empirical nowcast",
  title: "D-RAP HF absorption",
  summary: "NOAA's Highest Affected Frequency maps where current X-rays and solar energetic protons are expected to enhance D-region HF absorption.",
  data: "The operational 2° × 4° global grid reports the highest frequency expected to lose at least 1 dB on a vertical ground–ionosphere–ground path. It is driven by one-minute GOES X-ray and five-minute GOES proton inputs.",
  processing: "bigmem validates the complete NOAA ASCII grid, preserves its valid time and status messages, and losslessly stores the source's 0.1 MHz values as compact uint16 frames. The browser holds the latest frame at or before the selected UTC and never interpolates between nowcasts.",
  limitation: "D-RAP is empirical model guidance, not an absorption measurement or outage map. It omits auroral-electron absorption, and the vertical two-pass threshold does not represent a particular oblique link, antenna, mode, noise environment, or F-region reflection condition. NOAA validation recommends treating it as a qualitative indicator during highly disturbed conditions.",
  url: "https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap",
} as const;

/**
 * The peak below which a drawn D-RAP field is `faint` rather than `active`.
 *
 * 5 MHz is the legend's second tick and the frequency this layer already works
 * its example absorption at, so it is the site's own idea of "the low end".
 * Measured across the 446 frames of the live 2026-08-25/26 artifact, the peak
 * and the painted area move together and monotonically: peak under 5 MHz never
 * paints more than 18% of the globe and NEVER reaches 1 dB at 10 MHz anywhere,
 * while peak over 15 MHz paints 42-62% and takes up to 44% of the globe with
 * it at 10 MHz. The cut is where a map stops being a picture and starts being
 * a number that needs saying in words.
 */
export const DRAP_FAINT_PEAK_MHZ = 5;

/**
 * ...with an area guard, so a hypothetical wide-but-shallow field is not
 * called faint merely because its peak is low. Redundant on every frame in the
 * live artifact (see above) and kept because the redundancy is the evidence,
 * not the rule.
 */
export const DRAP_FAINT_AREA_PERCENT = 25;

/**
 * How long past its own newest frame the layer will hold that frame.
 *
 * D-RAP HAS NO FUTURE. `time.futureAvailable` is `false` in every bundle: it
 * is computed from X-ray and proton flux measured minutes ago, and nobody
 * publishes a forecast of it. Without a ceiling here the layer drew its last
 * map at +72 h on a slider that runs three days forward, wearing a live legend
 * -- the logged defect. With one, it goes off past the record and says so.
 *
 * 90 minutes, for two reasons that agree. The D region recombines within the
 * hour (this site's own flare lesson says so), so a map much older than that
 * has stopped being a statement about the selected instant at all. And 90 min
 * is clear of the routine 30-60 min upstream publication lag that
 * `selectState` deliberately accommodates below, so the live edge behaves
 * exactly as it does today.
 */
export const DRAP_LIVE_EDGE_HOLD_MINUTES = 90;

const COLOR_STOPS: ReadonlyArray<readonly [number, number, number, number, number]> = [
  [3, 35, 188, 199, 45],
  [5, 61, 181, 222, 92],
  [10, 243, 208, 82, 145],
  [15, 247, 151, 55, 178],
  [20, 235, 78, 62, 207],
  [25, 188, 51, 109, 229],
  [30, 137, 43, 177, 242],
];

/** Selects a source frame without inventing time interpolation. */
export function selectDrapFrame(bundle: DrapBundle, requestedAt: Date | string | number): DrapFrameSelection | null {
  const requestedMs = toTimeMs(requestedAt);
  if (requestedMs === null || bundle.frames.length === 0) return null;
  let lower = 0;
  let upper = bundle.frames.length - 1;
  let selected: DrapFrame | null = null;
  while (lower <= upper) {
    const middle = Math.floor((lower + upper) / 2);
    const candidate = bundle.frames[middle]!;
    const candidateMs = Date.parse(candidate.validAt);
    if (!Number.isFinite(candidateMs)) return null;
    if (candidateMs <= requestedMs) {
      selected = candidate;
      lower = middle + 1;
    } else {
      upper = middle - 1;
    }
  }
  if (!selected) return null;
  const ageMinutes = (requestedMs - Date.parse(selected.validAt)) / 60_000;
  return {
    frame: selected,
    ageMinutes,
    stale: ageMinutes > bundle.time.staleAfterMinutes,
  };
}

export function decodeDrapValues(bundle: DrapBundle, frame: DrapFrame): Float32Array {
  if (bundle.encoding.type !== "uint16-le-base64") throw new Error(`Unsupported D-RAP encoding: ${String(bundle.encoding.type)}`);
  const bytes = decodeBase64(frame.valuesU16);
  const expectedValues = bundle.grid.longitudeCount * bundle.grid.latitudeCount;
  if (bytes.byteLength !== expectedValues * 2) {
    throw new Error(`D-RAP frame has ${bytes.byteLength} bytes; expected ${expectedValues * 2}`);
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const values = new Float32Array(expectedValues);
  for (let index = 0; index < expectedValues; index += 1) {
    const encoded = view.getUint16(index * 2, true);
    values[index] = encoded === bundle.encoding.missingValue
      ? Number.NaN
      : encoded * bundle.encoding.scaleMhz;
  }
  return values;
}

/** Produces a small RGBA texture; cells below 3 MHz remain numerically quiet. */
export function drapRgbaGrid(
  bundle: DrapBundle,
  frame: DrapFrame,
  options: DrapRenderOptions = {},
): DrapRgbaGrid {
  const sourceValues = decodeDrapValues(bundle, frame);
  const mode = options.mode ?? "smooth";
  const resampled = resampleDrapValues(bundle, sourceValues, mode, options.smoothResolutionDegrees ?? 1);
  const values = resampled.values;
  const rgba = new Uint8ClampedArray(values.length * 4);
  const opacityScale = clamp(options.opacity ?? 1, 0, 1);
  const condition = drapCondition(frame);
  const showQuietBackdrop = (options.quietStateBackdrop ?? true) && condition.status === "none";
  for (let index = 0; index < values.length; index += 1) {
    const color = drapHafColor(values[index]!);
    const destination = index * 4;
    if (showQuietBackdrop && Number.isFinite(values[index])) {
      // A neutral, low-alpha status wash distinguishes a verified all-zero
      // nowcast from a failed/blank layer. It is not on the HAF color scale;
      // decoded and resampled values remain exactly zero.
      rgba[destination] = 20;
      rgba[destination + 1] = 54;
      rgba[destination + 2] = 72;
      rgba[destination + 3] = Math.round(24 * opacityScale);
    } else {
      rgba[destination] = color[0];
      rgba[destination + 1] = color[1];
      rgba[destination + 2] = color[2];
      rgba[destination + 3] = Math.round(color[3] * opacityScale);
    }
  }
  return {
    width: resampled.width,
    height: resampled.height,
    rgba,
    condition,
  };
}

export function resampleDrapValues(
  bundle: DrapBundle,
  sourceValues: Float32Array,
  mode: DrapDisplayMode = "smooth",
  smoothResolutionDegrees = 1,
): { width: number; height: number; values: Float32Array } {
  const sourceWidth = bundle.grid.longitudeCount;
  const sourceHeight = bundle.grid.latitudeCount;
  if (sourceValues.length !== sourceWidth * sourceHeight) {
    throw new Error(`D-RAP source grid has ${sourceValues.length} values; expected ${sourceWidth * sourceHeight}`);
  }
  if (mode === "native") {
    return { width: sourceWidth, height: sourceHeight, values: sourceValues.slice() };
  }
  if (!Number.isFinite(smoothResolutionDegrees) || smoothResolutionDegrees <= 0) {
    throw new Error("D-RAP smooth resolution must be positive");
  }

  const longitudeFactor = Math.max(1, Math.round(Math.abs(bundle.grid.longitudeStepDeg) / smoothResolutionDegrees));
  const latitudeFactor = Math.max(1, Math.round(Math.abs(bundle.grid.latitudeStepDeg) / smoothResolutionDegrees));
  const width = sourceWidth * longitudeFactor;
  const height = sourceHeight * latitudeFactor;
  const values = new Float32Array(width * height);
  const longitudeStep = bundle.grid.longitudeStepDeg / longitudeFactor;
  const latitudeStep = bundle.grid.latitudeStepDeg / latitudeFactor;

  for (let y = 0; y < height; y += 1) {
    const latitude = bundle.grid.latitudeStartDeg + (y - (latitudeFactor - 1) / 2) * latitudeStep;
    const sourceY = (latitude - bundle.grid.latitudeStartDeg) / bundle.grid.latitudeStepDeg;
    const y0 = clampInteger(Math.floor(sourceY), 0, sourceHeight - 1);
    const y1 = clampInteger(y0 + 1, 0, sourceHeight - 1);
    const nearestY = clampInteger(Math.round(sourceY), 0, sourceHeight - 1);
    const yAmount = clamp(sourceY - Math.floor(sourceY), 0, 1);
    for (let x = 0; x < width; x += 1) {
      const longitude = bundle.grid.longitudeStartDeg + (x - (longitudeFactor - 1) / 2) * longitudeStep;
      const sourceX = (longitude - bundle.grid.longitudeStartDeg) / bundle.grid.longitudeStepDeg;
      const floorX = Math.floor(sourceX);
      const x0 = positiveModulo(floorX, sourceWidth);
      const x1 = positiveModulo(floorX + 1, sourceWidth);
      const nearestX = positiveModulo(Math.round(sourceX), sourceWidth);
      const xAmount = clamp(sourceX - floorX, 0, 1);
      const nearest = sourceValues[nearestY * sourceWidth + nearestX]!;
      const destination = y * width + x;

      // The nearest-cell mask prevents smoothing from painting across a source
      // null. At valid cells touching a null, fall back to the source value.
      if (!Number.isFinite(nearest)) {
        values[destination] = Number.NaN;
        continue;
      }
      const topLeft = sourceValues[y0 * sourceWidth + x0]!;
      const topRight = sourceValues[y0 * sourceWidth + x1]!;
      const bottomLeft = sourceValues[y1 * sourceWidth + x0]!;
      const bottomRight = sourceValues[y1 * sourceWidth + x1]!;
      if (![topLeft, topRight, bottomLeft, bottomRight].every(Number.isFinite)) {
        values[destination] = nearest;
        continue;
      }
      const top = mix(topLeft, topRight, xAmount);
      const bottom = mix(bottomLeft, bottomRight, xAmount);
      values[destination] = mix(top, bottom, yAmount);
    }
  }
  return { width, height, values };
}

export function drapHafColor(hafMhz: number): readonly [number, number, number, number] {
  if (!Number.isFinite(hafMhz) || hafMhz < COLOR_STOPS[0]![0]) return [0, 0, 0, 0];
  for (let index = 1; index < COLOR_STOPS.length; index += 1) {
    const previous = COLOR_STOPS[index - 1]!;
    const next = COLOR_STOPS[index]!;
    if (hafMhz <= next[0]) {
      const amount = (hafMhz - previous[0]) / (next[0] - previous[0]);
      return [
        Math.round(mix(previous[1], next[1], amount)),
        Math.round(mix(previous[2], next[2], amount)),
        Math.round(mix(previous[3], next[3], amount)),
        Math.round(mix(previous[4], next[4], amount)),
      ];
    }
  }
  const final = COLOR_STOPS.at(-1)!;
  return [final[1], final[2], final[3], final[4]];
}

/** NOAA's documented HAF scaling for the same vertical two-pass path. */
export function drapAbsorptionDbAtFrequency(hafMhz: number, frequencyMhz: number): number | null {
  if (!Number.isFinite(hafMhz) || hafMhz < 0 || !Number.isFinite(frequencyMhz) || frequencyMhz <= 0) return null;
  return Math.pow(hafMhz / frequencyMhz, 1.5);
}

export function formatDrapFrameTime(selection: DrapFrameSelection | null): string {
  if (!selection) return "No D-RAP frame at this UTC";
  const valid = selection.frame.validAt.slice(0, 16).replace("T", " ");
  return selection.stale
    ? `${valid} UTC · stale (${Math.floor(selection.ageMinutes)} min old)`
    : `${valid} UTC · held source frame`;
}

export function drapConditionSummary(frame: DrapFrame): string {
  return drapCondition(frame).summary;
}

/** `4.4%`, `62%`, `none`. Two significant places at the bottom, where the
 * difference between 0.1 and 4.4 is the whole of what is being said. */
function areaLabel(percent: number): string {
  // NOT REPORTED IS NOT NONE. The degradation path above can reach these with
  // an unreadable percentage, and "over none of the globe" for a field that is
  // visibly drawn would be the confident version of the same mistake.
  if (!Number.isFinite(percent)) return "an unreported share of the globe";
  if (percent <= 0) return "none of the globe";
  return `${percent >= 10 ? percent.toFixed(0) : percent.toFixed(1)}% of the globe`;
}

/** The same share with the noun left off, for the second and third time it
 * is said in one sentence. `62% of the globe; 44% at 10 MHz, 1.1% at 30 MHz.` */
function shareLabel(percent: number): string {
  if (!Number.isFinite(percent)) return "an unreported share";
  if (percent <= 0) return "none";
  return `${percent >= 10 ? percent.toFixed(0) : percent.toFixed(1)}%`;
}

function peakLabel(mhz: number): string {
  return `${mhz.toFixed(1)} MHz`;
}

/**
 * WHAT THIS FRAME SAYS, in the three places a reader can see it.
 *
 * The rule this exists to satisfy is the site's standing one: what it knows,
 * it says. The layer had a working renderer, a correct 3-30 MHz scale, a real
 * NOAA nowcast behind it and no way at all of telling a reader that the reason
 * the globe is bare is that the ionosphere is quiet. Every number below comes
 * off the published frame; none of them is rescaled, floored lower, or made
 * to look busier than it is.
 */
export function drapCondition(frame: DrapFrame): DrapCondition {
  const peak = frame.maximumHafMhz;
  const area = frame.affectedCellPercent["3MHz"];
  const at10 = frame.affectedCellPercent["10MHz"];
  const at30 = frame.affectedCellPercent["30MHz"];
  // Nothing is drawn below 3 MHz -- `drapHafColor` returns a transparent
  // pixel there -- so `affectedCellPercent["3MHz"]` is literally the share of
  // the globe that gets any colour at all.
  //
  // THE PEAK DECIDES AND THE AREA ONLY REFINES, in that order, so that a frame
  // missing its percentages degrades toward saying too little rather than too
  // much. An unreadable area with a 31.5 MHz peak has to come out ACTIVE; the
  // other way round the badge would read QUIET · NOTHING DRAWN over half a
  // painted globe, which is a worse lie than the one this whole change exists
  // to remove.
  const areaKnown = Number.isFinite(area);
  const status: DrapConditionStatus = peak < 3 || (areaKnown && area <= 0)
    ? "none"
    : peak < DRAP_FAINT_PEAK_MHZ && (!areaKnown || area < DRAP_FAINT_AREA_PERCENT)
      ? "faint"
      : "active";

  if (status === "none") {
    return {
      status,
      summary: `QUIET · The strongest absorption anywhere on Earth reaches ${peakLabel(peak)}, below the 3 MHz `
        + "bottom of the HF band, so not one cell on the globe is drawn — an empty map is the reading here, "
        + "not a failure.",
      legendLine: `Quiet — the peak is ${peakLabel(peak)}, below the 3 MHz floor of this scale. Nothing is drawn.`,
      badge: "QUIET · NOTHING DRAWN",
      maximumHafMhz: peak,
      affectedCellPercent: { ...frame.affectedCellPercent },
      zeroFieldPreserved: true,
    };
  }
  if (status === "faint") {
    return {
      status,
      summary: `QUIET · The strongest absorption anywhere on Earth reaches ${peakLabel(peak)}, over `
        + `${areaLabel(area)}, and no cell anywhere loses 1 dB at 10 MHz or at 30 MHz — so the whole of this `
        + "nowcast sits in the bottom two megahertz of a 3–30 MHz scale and is very nearly invisible, which is "
        + "what a quiet D region looks like.",
      legendLine: `Quiet — peak ${peakLabel(peak)} over ${areaLabel(area)}; nothing at 10 or 30 MHz. `
        + "A nearly empty map is the reading.",
      badge: `QUIET · PEAK ${peakLabel(peak)}`,
      maximumHafMhz: peak,
      affectedCellPercent: { ...frame.affectedCellPercent },
      zeroFieldPreserved: true,
    };
  }
  return {
    status,
    summary: `ACTIVE · The strongest absorption anywhere on Earth reaches ${peakLabel(peak)}, drawn over `
      + `${areaLabel(area)}; ${shareLabel(at10)} of it loses at least 1 dB at 10 MHz and ${shareLabel(at30)} at 30 MHz.`,
    legendLine: `Peak ${peakLabel(peak)} over ${areaLabel(area)}; ${shareLabel(at10)} at 10 MHz, `
      + `${shareLabel(at30)} at 30 MHz.`,
    badge: `ACTIVE · PEAK ${peakLabel(peak)}`,
    maximumHafMhz: peak,
    affectedCellPercent: { ...frame.affectedCellPercent },
    zeroFieldPreserved: true,
  };
}

/**
 * The condition, and then NOAA's own words for why it is that condition.
 *
 * The status lines are parsed from the CURRENT D-RAP text only (`pipeline/
 * drap.py`), so they describe the newest frame and no other. Quoting them over
 * a frame scrubbed back two days would be attributing today's feed status to
 * Tuesday, so they are attached to the newest frame and nowhere else. They are
 * quoted verbatim rather than paraphrased: "Normal X-ray Background" is NOAA's
 * sentence, and a reader who wants to check it can.
 */
export function drapConditionSentence(bundle: DrapBundle, frame: DrapFrame): string {
  const condition = drapCondition(frame);
  const newest = bundle.frames.at(-1);
  const isNewest = newest !== undefined && newest.validAt === frame.validAt;
  if (!isNewest) return condition.summary;
  const lines = [bundle.messages.xrayWarning ?? bundle.messages.xray, bundle.messages.protonWarning ?? bundle.messages.proton]
    .filter((line): line is string => typeof line === "string" && line.trim().length > 0)
    .map((line) => `“${line.trim()}”`);
  if (lines.length === 0) return condition.summary;
  const quoted = lines.length === 2 ? `${lines[0]} and ${lines[1]}` : lines[0]!;
  const driversNote = condition.status === "active"
    ? "Those two fluxes are the whole of what D-RAP is computed from."
    : "Those two fluxes are the whole of what D-RAP is computed from, so this is the map they currently support. "
      + "The layer is working; the ionosphere is quiet.";
  return `${condition.summary} NOAA's own status lines for this nowcast read ${quoted}. ${driversNote}`;
}

/**
 * The words past the end of the record, written here beside the numbers they
 * are about -- the same arrangement `noForecastSentence` uses for the
 * magnetosphere, which is the layer this one is now matching.
 */
export function drapNowcastEndSentence(newestFrameLabel: string): string {
  return "NOAA computes this map from X-ray and proton flux measured in the last few minutes, so it exists up to "
    + `now and no further; this release's record stops at ${newestFrameLabel}. Nobody publishes a forecast of `
    + "D-region absorption, and the bundle says so itself — it carries no future frames at all. Rather than hold "
    + "the last map and label it a time it says nothing about, the layer is off. Scrub back and it comes straight back.";
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
  return start + (end - start) * clamp(amount, 0, 1);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function clampInteger(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, Math.trunc(value)));
}

function positiveModulo(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}
