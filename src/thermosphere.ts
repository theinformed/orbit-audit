/**
 * The neutral atmosphere a satellite flies through.
 *
 * The ionosphere layer draws the ionised minority of this same gas; this one
 * draws the neutral mass density, because it is the neutral air, not the
 * electrons, that produces drag. At 300 km a typical daytime F2 electron
 * density of 1e12 m^-3 sits inside a neutral gas of roughly 7e14 m^-3 — about
 * one particle in seven hundred.
 *
 * What this exists to show: during a geomagnetic storm the high-latitude
 * thermosphere is heated, the whole atmosphere expands, and air that was well
 * below a satellite is suddenly at its altitude. Drag rises with it. Rather
 * than draw density on a fixed shell — where a huge change looks like a colour
 * shift — this draws the ALTITUDE at which a chosen density occurs, so the
 * storm makes the surface visibly climb toward the satellites.
 *
 * Everything here is pure and decodes what NOAA published. Nothing interpolates
 * across a gap in time: a missing frame stays missing.
 */

/** One published frame, exactly as `pipeline/thermosphere.py` writes it. */
export interface ThermosphereFrame {
  validAt: string;
  grid: { altitudeKm: number[]; latitudeDeg: number[]; longitudeDeg: number[] };
  encoding: { bits: number; logFloor: number; logCeiling: number; quantumDex: number };
  codes: string;
  codesDtype: string;
  validMask: string;
  validFraction: number;
  /**
   * Present on empirical frames only: the indices this hour was evaluated from,
   * carried ON the frame so the reader is told what drove the field they are
   * looking at rather than what drove the release.
   */
  drivers?: { f107: number; f107a: number; kp: number; ap: number; apHistory: number[]; apStatus: string; f107Status: string; aheadOfBuild?: boolean };
  /** Present on empirical frames only. See `DriverStatus`. */
  driverStatus?: DriverStatus;
}

/** The published artifact, as `pipeline/thermosphere.py` writes it. */
export interface ThermosphereBundle {
  generatedAt: string;
  cycleStart: string;
  validFrom: string;
  validTo: string;
  cadenceMinutes: number;
  model: {
    model: string;
    modelLabel: string;
    modelStatus: string;
    modelShortName?: string;
    representation: string;
    fallbackApplied: boolean;
    reason: string;
  };
  source: { product: string; status: string; url?: string };
  frames: ThermosphereFrame[];
  /** Frames NOAA published that this release could not read. Never silent. */
  skipped: { validAt: string; reason: string }[];
  publishedAltitudesKm: number[];
}

export interface DecodedFrame {
  validAt: string;
  altitudeKm: Float64Array;
  latitudeDeg: Float64Array;
  longitudeDeg: Float64Array;
  /** log10(density in kg m^-3), C-order (altitude, latitude, longitude); NaN where absent. */
  logDensity: Float64Array;
}

/**
 * The density level whose altitude the surface draws, and why this one.
 *
 * 1e-12 kg m^-3 sits at roughly 400 km in quiet conditions — the shell that
 * carries the ISS, most Earth-observation satellites and the Starlink insertion
 * orbits, which is to say the altitudes where storm-time drag actually decides
 * outcomes. It is a display choice, not a physical boundary, and the layer says
 * so wherever it appears.
 */
export const DEFAULT_ISOPYCNIC_KG_M3 = 1e-12;

/** Selectable levels, spanning the drag-relevant band. */
export const ISOPYCNIC_LEVELS_KG_M3 = [1e-11, 1e-12, 1e-13] as const;

export const THERMOSPHERE_LIMITATION =
  "Neither field is a measurement. NOAA WAM is a physics forecast and is not assimilated "
  + "in the thermosphere; NRLMSIS 2.1, which covers every hour NOAA's WAM release does not, "
  + "is an empirical fit driven by F10.7 and by ap derived from the Kp series on this site, "
  + "and it is known to under-respond to storms. The two are never blended: the badge names "
  + "the one on screen, and the picture changes where they meet. The heights quoted are the "
  + "altitude of a chosen density, which is a display choice and not a physical boundary.";

export const DRAG_LIMITATION =
  "Drag on a particular satellite also depends on its mass, cross-section and drag "
  + "coefficient, none of which this catalogue holds. Density is what is shown; a decay "
  + "rate is only ever quoted for a stated reference body.";

function decodeBase64(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

/**
 * Undo the pipeline's quantisation. Code 0 means "no value" at both widths, so a
 * hole decodes to NaN and can never be mistaken for the lowest density on the
 * scale — which, on a log axis spanning eleven decades, would read as a vacuum.
 */
export function decodeThermosphereFrame(frame: ThermosphereFrame): DecodedFrame {
  const { altitudeKm, latitudeDeg, longitudeDeg } = frame.grid;
  const expected = altitudeKm.length * latitudeDeg.length * longitudeDeg.length;
  const bytes = decodeBase64(frame.codes);
  const bits = frame.encoding.bits;
  if (bits !== 8 && bits !== 16) throw new Error(`unsupported thermosphere code width ${bits}`);

  const codes = bits === 8
    ? bytes
    : new Uint16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
  if (codes.length !== expected) {
    throw new Error(`thermosphere frame declares ${expected} samples but carries ${codes.length}`);
  }

  const span = (1 << bits) - 1;
  const { logFloor, logCeiling } = frame.encoding;
  const logDensity = new Float64Array(expected);
  for (let index = 0; index < expected; index += 1) {
    const code = codes[index]!;
    logDensity[index] = code === 0
      ? Number.NaN
      : logFloor + ((code - 1) / (span - 1)) * (logCeiling - logFloor);
  }

  return {
    validAt: frame.validAt,
    altitudeKm: Float64Array.from(altitudeKm),
    latitudeDeg: Float64Array.from(latitudeDeg),
    longitudeDeg: Float64Array.from(longitudeDeg),
    logDensity,
  };
}

/**
 * The published frame to draw for one instant, or null when the release does
 * not cover it.
 *
 * Nearest frame, and never one further away than half the publishing cadence:
 * frames are an hour apart, so a frame thirty-one minutes away is a different
 * atmosphere, and drawing it would put the wrong hour under the reader's hand.
 *
 * Returning NULL is why this is a function rather than three lines inside the
 * caller. The caller used to `return` on the out-of-coverage branch, which left
 * whatever frame it last chose standing in the scene with nothing said about
 * it. Measured on the shipped build, thermosphere alone, satellites hidden: at
 * 2026-08-19 06:00Z -- twelve and a half hours before this release's first
 * frame -- the glow was still drawn at full strength (mean sky-annulus
 * brightness 40.9, against 43.3 at a covered instant) and the card still read
 * MODEL. The timeline spans 120 hours and a WAM release covers five or six of
 * them, so that stale picture is what a reader saw across roughly 95% of the
 * slider, and the thermosphere never changes when I move the clock is the
 * correct description of it.
 */
export function selectThermosphereFrame(
  bundle: Pick<ThermosphereBundle, "frames" | "cadenceMinutes">,
  at: Date,
): ThermosphereFrame | null {
  const wanted = at.getTime();
  if (!Number.isFinite(wanted)) return null;
  let best: ThermosphereFrame | null = null;
  let bestGap = Number.POSITIVE_INFINITY;
  for (const frame of bundle.frames) {
    const gap = Math.abs(Date.parse(frame.validAt) - wanted);
    if (!Number.isFinite(gap) || gap >= bestGap) continue;
    bestGap = gap;
    best = frame;
  }
  const halfCadenceMs = ((bundle.cadenceMinutes ?? 60) * 60_000) / 2;
  return best && bestGap <= halfCadenceMs ? best : null;
}

/** Index of the sample at or below `value`, for an ascending axis. */
function lowerIndex(axis: Float64Array, value: number): number {
  let low = 0;
  let high = axis.length - 1;
  if (value <= axis[0]!) return 0;
  if (value >= axis[high]!) return high - 1;
  while (high - low > 1) {
    const mid = (low + high) >> 1;
    if (axis[mid]! <= value) low = mid; else high = mid;
  }
  return low;
}

/** Longitudes wrap; latitudes do not. Both axes are ascending as published. */
function horizontalWeights(axis: Float64Array, value: number, wrap: boolean) {
  const first = axis[0]!;
  const last = axis[axis.length - 1]!;
  if (wrap) {
    const period = 360;
    let target = value;
    while (target < first) target += period;
    while (target > last + (period - (last - first))) target -= period;
    if (target > last) {
      // Between the last sample and the first, the long way round the seam.
      const gap = first + period - last;
      return { a: axis.length - 1, b: 0, t: (target - last) / gap };
    }
    const index = lowerIndex(axis, target);
    const gap = axis[index + 1]! - axis[index]!;
    return { a: index, b: index + 1, t: gap === 0 ? 0 : (target - axis[index]!) / gap };
  }
  const clamped = Math.min(Math.max(value, first), last);
  const index = lowerIndex(axis, clamped);
  const gap = axis[index + 1]! - axis[index]!;
  return { a: index, b: index + 1, t: gap === 0 ? 0 : (clamped - axis[index]!) / gap };
}

function sampleLog(frame: DecodedFrame, level: number, lat: number, lon: number): number {
  const nLat = frame.latitudeDeg.length;
  const nLon = frame.longitudeDeg.length;
  return frame.logDensity[(level * nLat + lat) * nLon + lon]!;
}

/**
 * log10 density at a point on one published level, bilinear in latitude and
 * longitude. Returns NaN if any corner is missing rather than filling from the
 * corners that are present: a partly-missing cell is a gap, not a soft value.
 */
export function logDensityOnLevel(
  frame: DecodedFrame,
  levelIndex: number,
  latitudeDeg: number,
  longitudeDeg: number,
): number {
  const lat = horizontalWeights(frame.latitudeDeg, latitudeDeg, false);
  const lon = horizontalWeights(frame.longitudeDeg, longitudeDeg, true);
  const c00 = sampleLog(frame, levelIndex, lat.a, lon.a);
  const c01 = sampleLog(frame, levelIndex, lat.a, lon.b);
  const c10 = sampleLog(frame, levelIndex, lat.b, lon.a);
  const c11 = sampleLog(frame, levelIndex, lat.b, lon.b);
  if (!Number.isFinite(c00) || !Number.isFinite(c01) || !Number.isFinite(c10) || !Number.isFinite(c11)) {
    return Number.NaN;
  }
  const top = c00 + (c01 - c00) * lon.t;
  const bottom = c10 + (c11 - c10) * lon.t;
  return top + (bottom - top) * lat.t;
}

/**
 * Neutral mass density at a point in space, kg m^-3.
 *
 * Interpolation is linear in log density against altitude, which is the honest
 * choice: density falls close to exponentially with height, so log-linear is
 * near-exact over one published step while linear-in-density would overshoot
 * badly between levels 30 km apart.
 */
export function densityKgM3(
  frame: DecodedFrame,
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
): number | null {
  const axis = frame.altitudeKm;
  if (altitudeKm < axis[0]! || altitudeKm > axis[axis.length - 1]!) return null;
  const index = lowerIndex(axis, altitudeKm);
  const lower = logDensityOnLevel(frame, index, latitudeDeg, longitudeDeg);
  const upper = logDensityOnLevel(frame, index + 1, latitudeDeg, longitudeDeg);
  if (!Number.isFinite(lower) || !Number.isFinite(upper)) return null;
  const gap = axis[index + 1]! - axis[index]!;
  const t = gap === 0 ? 0 : (altitudeKm - axis[index]!) / gap;
  return 10 ** (lower + (upper - lower) * t);
}

/**
 * The altitude at which density equals `level` — the number this layer draws.
 *
 * Searches downward from the top so the first crossing found is the outermost
 * one, which is the surface a satellite meets on the way in. Returns null when
 * the level is not crossed inside the published column, and the caller must say
 * so rather than clamping to the top or bottom of the grid: a clamped surface
 * would look like a real altitude.
 */
export function isopycnicAltitudeKm(
  frame: DecodedFrame,
  latitudeDeg: number,
  longitudeDeg: number,
  level: number = DEFAULT_ISOPYCNIC_KG_M3,
): number | null {
  const target = Math.log10(level);
  const axis = frame.altitudeKm;
  let upperLog = logDensityOnLevel(frame, axis.length - 1, latitudeDeg, longitudeDeg);
  for (let index = axis.length - 2; index >= 0; index -= 1) {
    const lowerLog = logDensityOnLevel(frame, index, latitudeDeg, longitudeDeg);
    if (Number.isFinite(lowerLog) && Number.isFinite(upperLog)) {
      const low = Math.min(lowerLog, upperLog);
      const high = Math.max(lowerLog, upperLog);
      if (target >= low && target <= high) {
        const span = upperLog - lowerLog;
        const t = span === 0 ? 0 : (target - lowerLog) / span;
        return axis[index]! + (axis[index + 1]! - axis[index]!) * t;
      }
    }
    upperLog = lowerLog;
  }
  return null;
}

/** Circular orbital speed at an altitude, m s^-1. Mirrors the pipeline. */
export function circularOrbitalSpeedMs(altitudeKm: number): number {
  const mu = 3.986004418e14;
  const radius = 6378137 + altitudeKm * 1000;
  return Math.sqrt(mu / radius);
}

/**
 * Drag deceleration, m s^-2, for a stated ballistic coefficient.
 *
 * `ballisticCoefficientKgM2` is mass / (drag coefficient x area). The catalogue
 * does not hold it for real objects, which is exactly why it is a required
 * argument here: a caller has to supply a reference body and name it, rather
 * than have a plausible-looking number appear for a satellite whose true value
 * is unknown.
 */
export function dragDecelerationMs2(
  densityKg: number,
  speedMs: number,
  ballisticCoefficientKgM2: number,
): number {
  if (ballisticCoefficientKgM2 <= 0) throw new Error("ballistic coefficient must be positive");
  return (0.5 * densityKg * speedMs * speedMs) / ballisticCoefficientKgM2;
}

/**
 * How much denser the air is at `altitudeKm` in one frame than another — the
 * single number this whole layer is built to deliver. Null unless both frames
 * have real values there.
 */
export function densityRatio(
  quiet: DecodedFrame,
  storm: DecodedFrame,
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
): number | null {
  const before = densityKgM3(quiet, latitudeDeg, longitudeDeg, altitudeKm);
  const after = densityKgM3(storm, latitudeDeg, longitudeDeg, altitudeKm);
  if (before === null || after === null || before <= 0) return null;
  return after / before;
}

/**
 * ONE SIX-HOUR SHARD of the empirical field, as `build_msis_bundle` writes it.
 *
 * NRLMSIS is published across the whole 120-hour slider because, unlike a
 * forecast integrated from an initial condition, an empirical model is defined
 * at every instant its drivers reach. That is 123 hourly frames and 13.2 MB of
 * JSON, so it is shipped in six-hour pieces and the browser fetches the one the
 * clock is inside — 425 kB — rather than the timeline.
 */
export interface EmpiricalThermosphereShard {
  validFrom: string;
  validTo: string;
  cadenceMinutes: number;
  frameCount: number;
  driverStatus: DriverStatus;
  frames: ThermosphereFrame[];
}

/**
 * Whether an hour was driven by the OBSERVED geomagnetic record or by NOAA's
 * forecast of it.
 *
 * This is the whole reason a FORECAST claim can be made honestly for part of
 * this layer and must not be made for the rest. It rides on the frame, from the
 * pipeline that chose the drivers, so no code downstream re-derives it by
 * comparing a timestamp with the clock and gets a different answer.
 */
export type DriverStatus = "observed" | "predicted" | "mixed";

/** Which of the two published models a drawn frame came from, and what it claims. */
export interface ThermosphereSelection {
  frame: ThermosphereFrame;
  model: "wamNeutral" | "nrlmsis21";
  /**
   * True when the numbers were produced before the time they describe: a WAM
   * frame valid after its cycle was initialised, or an MSIS hour driven by
   * NOAA's Kp forecast rather than the observed record.
   */
  forecast: boolean;
  /** One sentence naming the model and why it is the one on screen. */
  because: string;
}

/**
 * The frame to draw at one instant, across BOTH published models.
 *
 * The rule, and it is deliberately blunt: NOAA WAM wherever NOAA WAM has a
 * frame, NRLMSIS everywhere else, and NOTHING BLENDED. The two fields are
 * never averaged, faded between or interpolated across the boundary. A reader
 * scrubbing over it sees the picture change and the badge change in the same
 * instant, which is the honest presentation of "you are now looking at a
 * different kind of evidence" — and a visible seam is the point, not a defect
 * to be smoothed away.
 *
 * WAM wins inside its coverage because it is a physics forecast that resolves
 * auroral heating, and MSIS is a statistical fit that is known to under-respond
 * to storms. Outside it, MSIS is not a consolation prize: it is what operational
 * drag work uses, and it is the only one of the two that exists at all.
 */
export function chooseThermosphereFrame(
  wam: (Pick<ThermosphereBundle, "frames" | "cadenceMinutes"> & { cycleStart?: string }) | null,
  empirical: Pick<EmpiricalThermosphereShard, "frames" | "cadenceMinutes"> | null,
  at: Date,
): ThermosphereSelection | null {
  const fromWam = wam ? selectThermosphereFrame(wam, at) : null;
  if (fromWam) {
    // A WFS cycle produces nothing for times before it was initialised, so
    // every frame it publishes is a forecast — issued at `cycleStart`, valid
    // later. Derived from the two timestamps rather than asserted, so if NOAA
    // ever publishes an analysis frame the claim follows the data.
    const issued = wam?.cycleStart ? Date.parse(wam.cycleStart) : Number.NaN;
    const forecast = Number.isFinite(issued) && Date.parse(fromWam.validAt) >= issued;
    return {
      frame: fromWam,
      model: "wamNeutral",
      forecast,
      because: forecast
        ? "NOAA's WAM-IPE forecast covers this hour; it was issued before the hour it describes."
        : "NOAA's WAM-IPE run covers this hour.",
    };
  }
  const fromMsis = empirical ? selectThermosphereFrame(empirical, at) : null;
  if (!fromMsis) return null;
  const forecast = fromMsis.driverStatus === "predicted";
  return {
    frame: fromMsis,
    model: "nrlmsis21",
    forecast,
    because: `No NOAA WAM frame covers this hour. NRLMSIS is evaluated here from ${describeDrivers(fromMsis)}`,
  };
}

/**
 * WHICH driver is a forecast, in words — because "FORECAST" on an hour that
 * has already happened is otherwise just confusing.
 *
 * It happens routinely and it is not a bug. NOAA publishes the day's F10.7 at
 * 20:00 UT, so at 03:00 UT today's flux is genuinely still a prediction even
 * though the hour is in the past, while the geomagnetic index for the same hour
 * has already been observed. A field driven by a predicted number is a forecast
 * of that field whatever the clock says, and the honest thing is to name the
 * half that is predicted rather than let the chip stand there unexplained.
 */
function describeDrivers(frame: ThermosphereFrame): string {
  const drivers = frame.drivers;
  if (!drivers) {
    return frame.driverStatus === "predicted"
      ? "NOAA's forecast of the solar and geomagnetic indices."
      : "the observed solar and geomagnetic indices.";
  }
  // NOAA labels the whole current UT day `estimated`, including intervals that
  // have not happened yet, so the label alone would call tonight's Kp an
  // estimate of something. `aheadOfBuild` is what the pipeline measured against
  // its own clock, and it wins.
  const geomagnetic = drivers.apStatus === "predicted"
    ? "NOAA's forecast Kp"
    : drivers.aheadOfBuild
      ? "NOAA's estimate of Kp for an hour that has not happened yet"
      : drivers.apStatus === "estimated"
        ? "the estimated Kp"
        : "the observed Kp";
  const solar = drivers.f107Status === "predicted"
    ? "NOAA's 27-day forecast of F10.7"
    : "the observed F10.7";
  return `${geomagnetic} (ap ${drivers.ap}) and ${solar} (${drivers.f107.toFixed(0)} sfu).`;
}

/**
 * The chip the card wears, and the evidence class that colours it.
 *
 * Kept beside `chooseThermosphereFrame` and pure, because the one failure this
 * layer keeps having is a badge that describes a different frame from the one
 * on screen. Sean, on the shipped card: "is MODEL the only chip that layer
 * should carry, since we don't have a forecast?" — the data says the opposite.
 * Every frame in a WAM release is a forecast: the 18Z cycle publishes hours
 * 23:40Z through 11:30Z, all of them issued before the hour they describe. And
 * forward of the last observed Kp interval the empirical field is driven by
 * NOAA's forecast too, so FORECAST is earned there and only there.
 */
export function thermosphereBadge(
  selection: ThermosphereSelection | null,
): { badge: string; evidence: "model" | "empirical" } {
  if (!selection) return { badge: "NO DATA", evidence: "model" };
  if (selection.model === "wamNeutral") {
    return {
      badge: selection.forecast ? "NOAA MODEL · FORECAST" : "NOAA MODEL",
      evidence: "model",
    };
  }
  return {
    badge: selection.forecast ? "EMPIRICAL · FORECAST" : "EMPIRICAL",
    evidence: "empirical",
  };
}

/**
 * Every shard that could hold the frame nearest one instant.
 *
 * Not "the shard containing the clock", and the difference is a real hole. A
 * shard runs [validFrom, validTo) and carries the hours inside it; at 05:45 the
 * nearest published hour is 06:00, which lives in the NEXT shard. Fetching only
 * the containing shard would leave the layer with a 05:00 frame 45 minutes away
 * — further than half a cadence — and it would draw NO DATA for the last
 * fifteen minutes of every six-hour block, twenty times across the timeline.
 *
 * So the window is widened by half a cadence at each end and every shard it
 * touches is returned. The caller loads them all and selects across the union,
 * which is the same rule `selectThermosphereFrame` applies to a single bundle.
 */
export function shardsNear<T extends { validFrom: string; validTo: string }>(
  shards: readonly T[],
  at: Date,
  toleranceMs: number,
): T[] {
  const wanted = at.getTime();
  if (!Number.isFinite(wanted)) return [];
  const found: T[] = [];
  for (const shard of shards) {
    const from = Date.parse(shard.validFrom);
    const to = Date.parse(shard.validTo);
    if (!Number.isFinite(from) || !Number.isFinite(to)) continue;
    if (wanted >= from - toleranceMs && wanted < to + toleranceMs) found.push(shard);
  }
  return found;
}

/**
 * Where one published span sits on the timeline, as two percentages.
 *
 * The slider spans 120 hours and NOAA's WAM covers about twelve of them, so
 * "the assimilated-grade field is HERE and the empirical one is everywhere
 * else" is a fact about a 10% sliver that no amount of card text makes
 * findable. Returning null when the span does not intersect the slider is the
 * point: a band drawn at 0%-0% would be a mark on the timeline claiming
 * coverage that is not there.
 */
export function coverageBandPercent(
  span: { validFrom: string; validTo: string },
  window: { startMs: number; endMs: number },
): { startPercent: number; endPercent: number } | null {
  const from = Date.parse(span.validFrom);
  const to = Date.parse(span.validTo);
  const width = window.endMs - window.startMs;
  if (!Number.isFinite(from) || !Number.isFinite(to) || !(width > 0) || to <= from) return null;
  const start = Math.max(from, window.startMs);
  const end = Math.min(to, window.endMs);
  if (end <= start) return null;
  return {
    startPercent: ((start - window.startMs) / width) * 100,
    endPercent: ((end - window.startMs) / width) * 100,
  };
}
