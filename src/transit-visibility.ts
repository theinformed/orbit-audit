/**
 * Visibility geometry and the interval algebra built on top of it.
 *
 * ## The one assumption that decides the answer
 *
 * A satellite is "visible" from a point on the Earth when its elevation above
 * the local horizon exceeds a **mask angle**. Everything else in this module is
 * bookkeeping; the mask is the physics-facing assumption, and it moves the
 * answer more than any other input.
 *
 * At 0 degrees the satellite is on the geometric horizon: no terminal works
 * there. Real shipboard terminals have a keel-hauled minimum look angle set by
 * superstructure blockage, mast shadowing, sea state and the antenna's own
 * mechanical limits, and the number a planner uses is an operational input, not
 * a constant of nature. So the mask is a first-class, user-settable control with
 * a wide range, not a hidden default. Raise it from 0 to 10 degrees and a
 * geostationary satellite low on the horizon simply leaves the answer.
 *
 * ## How elevation is computed
 *
 * Rigorously, on the WGS-84 ellipsoid, using `satellite.js`'s own
 * `geodeticToEcf` / `ecfToLookAngles`. The observer's geodetic position becomes
 * an Earth-centred Earth-fixed vector; so does the satellite's; the look angle
 * is taken in the observer's local topocentric frame. This is the same library
 * that propagates the orbits, so no new orbital mechanics is introduced here.
 *
 * A spherical-Earth alternative is also provided, `sphericalElevationDeg`,
 * because it is the exact inverse of `footprintAngularRadius()` in
 * `src/orbit.ts` — the function that draws the footprint circle on the globe.
 * Keeping both, and testing them against each other, is what lets the planner
 * state honestly where the drawn circle and the computed answer differ. They
 * disagree by up to roughly a fifth of a degree of elevation, because geodetic
 * and geocentric latitude differ by up to 0.19 degrees. That is small next to a
 * 5-degree mask and large next to a 0-degree one, which is another reason not to
 * plan at 0.
 *
 * ## Windows
 *
 * A coarse time grid finds sign changes of (elevation - mask); each crossing is
 * then refined by bisection against the caller's own elevation function. That
 * puts window edges to whatever tolerance is asked for without paying for a fine
 * grid everywhere, and it is why the grid step can be chosen per orbit regime.
 *
 * The grid can still *miss* a pass entirely if the pass is shorter than the
 * step. That is a real limitation, not a rounding error, so `gridStepSeconds`
 * travels with every result and the planner shows it.
 */

import { ecfToLookAngles, geodeticToEcf } from "satellite.js";
import { EARTH_RADIUS_KM, footprintAngularRadius } from "./orbit";

const DEG = Math.PI / 180;

export interface GeodeticPoint {
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
}

/**
 * Elevation of a satellite above an observer's local horizon, in degrees, on the
 * WGS-84 ellipsoid. Negative below the horizon.
 */
export function elevationDeg(
  observerLatitudeDeg: number,
  observerLongitudeDeg: number,
  observerAltitudeKm: number,
  satelliteLatitudeDeg: number,
  satelliteLongitudeDeg: number,
  satelliteAltitudeKm: number,
): number {
  const observerGd = {
    latitude: observerLatitudeDeg * DEG,
    longitude: observerLongitudeDeg * DEG,
    height: observerAltitudeKm,
  };
  const satelliteEcf = geodeticToEcf({
    latitude: satelliteLatitudeDeg * DEG,
    longitude: satelliteLongitudeDeg * DEG,
    height: satelliteAltitudeKm,
  });
  return ecfToLookAngles(observerGd, satelliteEcf).elevation / DEG;
}

/** Range from observer to satellite in kilometres, WGS-84. */
export function rangeKm(
  observerLatitudeDeg: number,
  observerLongitudeDeg: number,
  observerAltitudeKm: number,
  satelliteLatitudeDeg: number,
  satelliteLongitudeDeg: number,
  satelliteAltitudeKm: number,
): number {
  const observerGd = {
    latitude: observerLatitudeDeg * DEG,
    longitude: observerLongitudeDeg * DEG,
    height: observerAltitudeKm,
  };
  const satelliteEcf = geodeticToEcf({
    latitude: satelliteLatitudeDeg * DEG,
    longitude: satelliteLongitudeDeg * DEG,
    height: satelliteAltitudeKm,
  });
  return ecfToLookAngles(observerGd, satelliteEcf).rangeSat;
}

/**
 * Spherical-Earth elevation from the central angle between observer and
 * sub-satellite point. This is the model the drawn footprint circle uses.
 *
 * Derivation: place the observer and the satellite in the plane containing both
 * and the Earth's centre. With central angle g and satellite geocentric radius
 * r, the elevation above the observer's horizon satisfies
 *
 *     tan(el) = (cos g - Re/r) / sin g
 *
 * so el = 0 exactly when cos g = Re/r, which is `footprintAngularRadius(alt, 0)`.
 */
export function sphericalElevationDeg(centralAngle: number, satelliteAltitudeKm: number): number {
  const radius = EARTH_RADIUS_KM + Math.max(0, satelliteAltitudeKm);
  const sinAngle = Math.sin(centralAngle);
  if (Math.abs(sinAngle) < 1e-12) return 90;
  return Math.atan2(Math.cos(centralAngle) - EARTH_RADIUS_KM / radius, sinAngle) / DEG;
}

/**
 * The spherical visibility test the footprint circle draws: true exactly when
 * the observer lies inside `footprintPoints(..., maskDeg)`.
 */
export function withinFootprint(
  centralAngle: number,
  satelliteAltitudeKm: number,
  maskDeg: number,
): boolean {
  return centralAngle <= footprintAngularRadius(satelliteAltitudeKm, maskDeg);
}

export interface VisibilityWindow {
  satelliteId: number;
  /** UTC epoch milliseconds. */
  startMs: number;
  endMs: number;
  /** True when the window is cut by the start or end of the transit, not by geometry. */
  truncatedAtStart: boolean;
  truncatedAtEnd: boolean;
  /** Best elevation seen on the grid inside this window, degrees. */
  peakElevationDeg: number;
  peakAtMs: number;
  /** Elevation at the moment of peak is the useful one; range there too. */
  peakRangeKm: number;
}

export interface WindowExtractionOptions {
  maskDeg: number;
  /** Coarse grid step actually used, carried through for honest reporting. */
  gridStepSeconds: number;
  /** Bisection tolerance for window edges, seconds. */
  edgeToleranceSeconds?: number;
  /**
   * Continuous elevation at an arbitrary time, used only to refine edges. When
   * omitted, edges are linearly interpolated between grid samples instead.
   */
  elevationAt?: (timeMs: number) => number;
}

export interface ElevationSample {
  timeMs: number;
  elevationDeg: number;
  rangeKm: number;
}

/**
 * Turn a time-ordered elevation series into windows above the mask.
 *
 * Edges are refined by bisection when `elevationAt` is supplied and by linear
 * interpolation otherwise. Linear interpolation is good to a few seconds for a
 * geostationary satellite and poor for a fast low-orbit rise, which is why the
 * planner supplies the real function.
 */
export function extractWindows(
  satelliteId: number,
  samples: readonly ElevationSample[],
  options: WindowExtractionOptions,
): VisibilityWindow[] {
  const { maskDeg } = options;
  const tolerance = (options.edgeToleranceSeconds ?? 1) * 1000;
  const windows: VisibilityWindow[] = [];
  if (samples.length === 0) return windows;

  let open: {
    startMs: number;
    truncatedAtStart: boolean;
    peakElevationDeg: number;
    peakAtMs: number;
    peakRangeKm: number;
  } | null = null;

  const crossing = (before: ElevationSample, after: ElevationSample): number => {
    if (options.elevationAt) {
      return bisectCrossing(options.elevationAt, maskDeg, before.timeMs, after.timeMs, tolerance);
    }
    const span = after.elevationDeg - before.elevationDeg;
    if (Math.abs(span) < 1e-12) return before.timeMs;
    const fraction = (maskDeg - before.elevationDeg) / span;
    return before.timeMs + (after.timeMs - before.timeMs) * Math.max(0, Math.min(1, fraction));
  };

  for (let index = 0; index < samples.length; index += 1) {
    const sample = samples[index]!;
    const above = sample.elevationDeg >= maskDeg;
    if (above && !open) {
      const previous = index > 0 ? samples[index - 1] : undefined;
      open = {
        startMs: previous ? crossing(previous, sample) : sample.timeMs,
        truncatedAtStart: !previous,
        peakElevationDeg: sample.elevationDeg,
        peakAtMs: sample.timeMs,
        peakRangeKm: sample.rangeKm,
      };
    } else if (above && open) {
      if (sample.elevationDeg > open.peakElevationDeg) {
        open.peakElevationDeg = sample.elevationDeg;
        open.peakAtMs = sample.timeMs;
        open.peakRangeKm = sample.rangeKm;
      }
    } else if (!above && open) {
      const previous = samples[index - 1]!;
      windows.push({
        satelliteId,
        startMs: open.startMs,
        endMs: crossing(previous, sample),
        truncatedAtStart: open.truncatedAtStart,
        truncatedAtEnd: false,
        peakElevationDeg: open.peakElevationDeg,
        peakAtMs: open.peakAtMs,
        peakRangeKm: open.peakRangeKm,
      });
      open = null;
    }
  }
  if (open) {
    windows.push({
      satelliteId,
      startMs: open.startMs,
      endMs: samples.at(-1)!.timeMs,
      truncatedAtStart: open.truncatedAtStart,
      truncatedAtEnd: true,
      peakElevationDeg: open.peakElevationDeg,
      peakAtMs: open.peakAtMs,
      peakRangeKm: open.peakRangeKm,
    });
  }
  return windows;
}

/**
 * Bisect for the time at which elevation crosses the mask. Assumes the mask is
 * crossed exactly once in the bracket, which is what the grid told us; a grid
 * too coarse for the satellite can violate that, and the fix is a finer grid,
 * not a cleverer root finder.
 */
export function bisectCrossing(
  elevationAt: (timeMs: number) => number,
  maskDeg: number,
  bracketStartMs: number,
  bracketEndMs: number,
  toleranceMs: number,
): number {
  let low = bracketStartMs;
  let high = bracketEndMs;
  const lowAbove = elevationAt(low) >= maskDeg;
  // 40 iterations halves a 1-day bracket to well under a microsecond; the
  // tolerance check exits long before that in every realistic case.
  for (let iteration = 0; iteration < 40 && high - low > toleranceMs; iteration += 1) {
    const middle = (low + high) / 2;
    if ((elevationAt(middle) >= maskDeg) === lowAbove) low = middle;
    else high = middle;
  }
  return (low + high) / 2;
}

// ---------------------------------------------------------------------------
// Interval algebra. This is where "which constellations cover the whole transit"
// is actually answered.
// ---------------------------------------------------------------------------

export interface Interval {
  startMs: number;
  endMs: number;
}

export function mergeIntervals(intervals: readonly Interval[]): Interval[] {
  const sorted = [...intervals]
    .filter((interval) => interval.endMs > interval.startMs)
    .sort((a, b) => a.startMs - b.startMs);
  const merged: Interval[] = [];
  for (const interval of sorted) {
    const last = merged.at(-1);
    if (last && interval.startMs <= last.endMs) {
      last.endMs = Math.max(last.endMs, interval.endMs);
    } else {
      merged.push({ ...interval });
    }
  }
  return merged;
}

/** Complement of `intervals` inside [startMs, endMs] — the coverage gaps. */
export function complementIntervals(
  intervals: readonly Interval[],
  startMs: number,
  endMs: number,
): Interval[] {
  const merged = mergeIntervals(intervals);
  const gaps: Interval[] = [];
  let cursor = startMs;
  for (const interval of merged) {
    if (interval.endMs <= startMs) continue;
    if (interval.startMs >= endMs) break;
    const clippedStart = Math.max(startMs, interval.startMs);
    if (clippedStart > cursor) gaps.push({ startMs: cursor, endMs: clippedStart });
    cursor = Math.max(cursor, Math.min(endMs, interval.endMs));
  }
  if (cursor < endMs) gaps.push({ startMs: cursor, endMs });
  return gaps;
}

export function intervalsTotalMs(intervals: readonly Interval[]): number {
  return mergeIntervals(intervals).reduce((total, interval) => total + (interval.endMs - interval.startMs), 0);
}

export function clipIntervals(
  intervals: readonly Interval[],
  startMs: number,
  endMs: number,
): Interval[] {
  return mergeIntervals(intervals)
    .map((interval) => ({
      startMs: Math.max(startMs, interval.startMs),
      endMs: Math.min(endMs, interval.endMs),
    }))
    .filter((interval) => interval.endMs > interval.startMs);
}

export function coversEntirely(
  intervals: readonly Interval[],
  startMs: number,
  endMs: number,
  /**
   * Gaps at or below this are treated as closed. Defaults to zero: a gap is a
   * gap. The planner exposes it because an edge refined to +/-1 s can otherwise
   * leave a 1 s hole between two satellites of the same constellation handing
   * over, and reporting that as "not continuous" would be a lie told by
   * arithmetic.
   */
  toleranceMs = 0,
): boolean {
  const gaps = complementIntervals(intervals, startMs, endMs);
  return gaps.every((gap) => gap.endMs - gap.startMs <= toleranceMs);
}

export interface CoverageSummary {
  /** Merged union of every contributing window, clipped to the transit. */
  covered: Interval[];
  gaps: Interval[];
  coveredMs: number;
  transitMs: number;
  coveredFraction: number;
  continuous: boolean;
  longestGapMs: number;
}

export function summarizeCoverage(
  intervals: readonly Interval[],
  startMs: number,
  endMs: number,
  toleranceMs = 0,
): CoverageSummary {
  const transitMs = Math.max(0, endMs - startMs);
  const covered = clipIntervals(intervals, startMs, endMs);
  const rawGaps = complementIntervals(covered, startMs, endMs);
  const gaps = rawGaps.filter((gap) => gap.endMs - gap.startMs > toleranceMs);
  const coveredMs = intervalsTotalMs(covered);
  return {
    covered,
    gaps,
    coveredMs,
    transitMs,
    coveredFraction: transitMs > 0 ? coveredMs / transitMs : 0,
    continuous: gaps.length === 0,
    longestGapMs: gaps.reduce((longest, gap) => Math.max(longest, gap.endMs - gap.startMs), 0),
  };
}

/**
 * Recommended coarse grid step for an orbit, in seconds.
 *
 * The binding constraint is not accuracy — bisection fixes the edges — it is
 * *not missing a pass at all*. A pass is missed when it is shorter than the
 * step, so the step has to be a fraction of the shortest pass the orbit can
 * produce, which is a grazing pass at the mask.
 *
 * For a circular orbit of period P, a grazing pass at mask m subtends a small
 * central angle and lasts a small fraction of P. Rather than model the grazing
 * case exactly, this uses a conservative fraction of the orbital period, capped
 * so that a geostationary satellite is not sampled pointlessly often and a low
 * orbit is not sampled too rarely to see a pass.
 */
export function recommendedStepSeconds(periodMinutes: number): number {
  if (!Number.isFinite(periodMinutes) || periodMinutes <= 0) return 30;
  // 1/180 of a revolution: two degrees of mean anomaly. A 95-minute low orbit
  // gets ~32 s, a 12-hour orbit gets ~4 min, geostationary gets the 300 s cap.
  const step = (periodMinutes * 60) / 180;
  return Math.max(10, Math.min(300, step));
}
