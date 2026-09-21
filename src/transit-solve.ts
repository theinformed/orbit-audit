/**
 * The solver core, deliberately outside the worker.
 *
 * `src/transit-worker.ts` is a thin message pump around this file. Everything
 * that decides an answer lives here, so a test can call exactly the code the
 * browser runs. This project has a documented history of green tests sitting
 * over a production path that never executed; keeping the arithmetic out of the
 * worker's message handler is the structural fix for that, not a habit.
 */

import { eciToGeodetic, gstime, json2satrec, propagate, type SatRec } from "satellite.js";
import type { OmmRecord } from "./types";
import { elementAgeDays } from "./orbit";
import { positionAt, routeSpanMs, type TransitRoute } from "./transit-route";
import {
  elevationDeg,
  extractWindows,
  rangeKm,
  recommendedStepSeconds,
  type ElevationSample,
  type VisibilityWindow,
} from "./transit-visibility";

export interface SolveSatelliteInput {
  id: number;
  periodMinutes: number;
  omm: OmmRecord;
}

/**
 * How far past its element epoch an SGP4 propagation is still worth showing.
 *
 * This is a physics bound, not a policy one. SGP4 propagates *mean* elements
 * fitted to observations near a single epoch. The fit carries no knowledge of
 * what the spacecraft does next: an unmodelled station-keeping burn, a drag
 * campaign, or a repositioning simply is not in the numbers. Error grows without
 * any bound the elements themselves can tell you about, and public guidance on
 * general-perturbations elements is consistent that they are intended for use
 * near epoch rather than as a two-month ephemeris.
 *
 * Fourteen days is the point past which this planner refuses to answer at all.
 * It is a round number in the right region rather than a threshold derived from
 * a covariance — there is no published covariance on these elements, which is
 * itself the reason a hard cap is the honest instrument. Below the cap, age is
 * shown per satellite rather than hidden, because a window built from two-week-
 * old elements and one built from yesterday's look identical otherwise.
 */
export const MAXIMUM_ELEMENT_AGE_DAYS = 14;

/** Element ages are banded so the list can say something rather than print a float. */
export type ElementAgeBand = "fresh" | "aging" | "stale" | "beyond-bound";

export function elementAgeBand(ageDays: number): ElementAgeBand {
  const age = Math.abs(ageDays);
  if (age <= 2) return "fresh";
  if (age <= 7) return "aging";
  if (age <= MAXIMUM_ELEMENT_AGE_DAYS) return "stale";
  return "beyond-bound";
}

export interface SolveOptions {
  maskDeg: number;
  /** Observer height above the ellipsoid, km. An antenna on a mast, not the sea. */
  observerAltitudeKm: number;
  /** Bisection tolerance for a window edge, seconds. */
  edgeToleranceSeconds: number;
}

export interface SatelliteVisibilityResult {
  satelliteId: number;
  windows: VisibilityWindow[];
  /** The grid this satellite was actually solved on. Reported, never hidden. */
  gridStepSeconds: number;
  propagationFailures: number;
  /** SGP4 evaluations spent on this satellite, grid plus edge refinement. */
  evaluations: number;
  /**
   * Age of this satellite's orbital elements, in days, at the *end* of the
   * transit — the worst case over the answer, not a flattering average.
   * Negative where the transit is entirely before the element epoch.
   */
  elementAgeDaysAtEnd: number;
  elementAgeBand: ElementAgeBand;
  /** ISO epoch of the elements used, so the age can be re-derived. */
  elementEpoch: string;
}

export function subsatellitePoint(satrec: SatRec, timeMs: number) {
  const at = new Date(timeMs);
  const result = propagate(satrec, at);
  if (!result || typeof result.position === "boolean") return null;
  const geodetic = eciToGeodetic(result.position, gstime(at));
  const latitudeDeg = (geodetic.latitude * 180) / Math.PI;
  const longitudeDeg = (geodetic.longitude * 180) / Math.PI;
  if (!Number.isFinite(latitudeDeg) || !Number.isFinite(longitudeDeg) || !Number.isFinite(geodetic.height)) {
    return null;
  }
  return { latitudeDeg, longitudeDeg, altitudeKm: geodetic.height };
}

/**
 * Estimated SGP4 evaluations for a solve, before any of them are spent.
 *
 * The planner asks for this first so an impossible request is refused with a
 * number the reader can act on ("that is 41 million propagations") instead of
 * by locking up a tab. Edge refinement is not counted: it is proportional to the
 * number of windows found, which is small next to the grid.
 */
export function estimateEvaluations(
  satellites: readonly Pick<SolveSatelliteInput, "periodMinutes">[],
  durationSeconds: number,
): number {
  let total = 0;
  for (const satellite of satellites) {
    total += Math.ceil(durationSeconds / recommendedStepSeconds(satellite.periodMinutes)) + 1;
  }
  return total;
}

/**
 * Visibility windows for one satellite over one route.
 *
 * Both the observer and the satellite move. The observer's motion is the point
 * of the whole feature — a ship crossing the Pacific rides out from under one
 * geostationary satellite and in under another without either satellite doing
 * anything — so the observer position is recomputed at every grid time from the
 * route, never held fixed at a waypoint.
 */
export function solveSatelliteVisibility(
  satellite: SolveSatelliteInput,
  route: TransitRoute,
  options: SolveOptions,
): SatelliteVisibilityResult {
  const stepSeconds = recommendedStepSeconds(satellite.periodMinutes);
  const span = routeSpanMs(route);
  const elementEpoch = String(satellite.omm.EPOCH ?? "");
  const ageAtEnd = span ? elementAgeDays(elementEpoch, new Date(span.endMs)) : Number.NaN;
  const ageFields = {
    elementAgeDaysAtEnd: ageAtEnd,
    elementAgeBand: Number.isFinite(ageAtEnd) ? elementAgeBand(ageAtEnd) : ("beyond-bound" as const),
    elementEpoch,
  };
  if (!span) {
    return { satelliteId: satellite.id, windows: [], gridStepSeconds: stepSeconds, propagationFailures: 0, evaluations: 0, ...ageFields };
  }

  let satrec: SatRec;
  try {
    satrec = json2satrec(satellite.omm);
  } catch {
    return { satelliteId: satellite.id, windows: [], gridStepSeconds: stepSeconds, propagationFailures: 1, evaluations: 0, ...ageFields };
  }

  let propagationFailures = 0;
  let evaluations = 0;

  const measure = (timeMs: number): ElevationSample | null => {
    const observer = positionAt(route, timeMs);
    const subpoint = subsatellitePoint(satrec, timeMs);
    evaluations += 1;
    if (!observer || !subpoint) {
      propagationFailures += 1;
      return null;
    }
    return {
      timeMs,
      elevationDeg: elevationDeg(
        observer.latitudeDeg,
        observer.longitudeDeg,
        options.observerAltitudeKm,
        subpoint.latitudeDeg,
        subpoint.longitudeDeg,
        subpoint.altitudeKm,
      ),
      rangeKm: rangeKm(
        observer.latitudeDeg,
        observer.longitudeDeg,
        options.observerAltitudeKm,
        subpoint.latitudeDeg,
        subpoint.longitudeDeg,
        subpoint.altitudeKm,
      ),
    };
  };

  const samples: ElevationSample[] = [];
  const stepMs = stepSeconds * 1000;
  for (let timeMs = span.startMs; timeMs < span.endMs; timeMs += stepMs) {
    const measured = measure(timeMs);
    if (measured) samples.push(measured);
  }
  // The grid rarely lands on arrival. Add it, or a window running to the end of
  // the transit gets clipped by up to one grid step and reported as shorter
  // than it is.
  const final = measure(span.endMs);
  if (final) samples.push(final);

  const windows = extractWindows(satellite.id, samples, {
    maskDeg: options.maskDeg,
    gridStepSeconds: stepSeconds,
    edgeToleranceSeconds: options.edgeToleranceSeconds,
    elevationAt: (timeMs: number) => {
      const observer = positionAt(route, timeMs);
      const subpoint = subsatellitePoint(satrec, timeMs);
      evaluations += 1;
      if (!observer || !subpoint) return Number.NEGATIVE_INFINITY;
      return elevationDeg(
        observer.latitudeDeg,
        observer.longitudeDeg,
        options.observerAltitudeKm,
        subpoint.latitudeDeg,
        subpoint.longitudeDeg,
        subpoint.altitudeKm,
      );
    },
  });

  return {
    satelliteId: satellite.id,
    windows,
    gridStepSeconds: stepSeconds,
    propagationFailures,
    evaluations,
    ...ageFields,
  };
}

/**
 * Which satellites are above the mask at a single instant.
 *
 * This is the "show only what can see me right now" toggle and the waypoint
 * dimming interaction. It is a separate, much cheaper path than the window
 * solve: one propagation per satellite instead of thousands, so it can run
 * synchronously while the time scrubber moves.
 */
export function visibleAtInstant(
  satellites: readonly SolveSatelliteInput[],
  observerLatitudeDeg: number,
  observerLongitudeDeg: number,
  observerAltitudeKm: number,
  timeMs: number,
  maskDeg: number,
  satrecCache?: Map<number, SatRec | null>,
): Array<{ satelliteId: number; elevationDeg: number; azimuthDeg: number; rangeKm: number }> {
  const above: Array<{ satelliteId: number; elevationDeg: number; azimuthDeg: number; rangeKm: number }> = [];
  for (const satellite of satellites) {
    let satrec = satrecCache?.get(satellite.id);
    if (satrec === undefined) {
      try {
        satrec = json2satrec(satellite.omm);
      } catch {
        satrec = null;
      }
      satrecCache?.set(satellite.id, satrec);
    }
    if (!satrec) continue;
    const subpoint = subsatellitePoint(satrec, timeMs);
    if (!subpoint) continue;
    const elevation = elevationDeg(
      observerLatitudeDeg,
      observerLongitudeDeg,
      observerAltitudeKm,
      subpoint.latitudeDeg,
      subpoint.longitudeDeg,
      subpoint.altitudeKm,
    );
    if (elevation < maskDeg) continue;
    above.push({
      satelliteId: satellite.id,
      elevationDeg: elevation,
      azimuthDeg: azimuthDeg(
        observerLatitudeDeg,
        observerLongitudeDeg,
        subpoint.latitudeDeg,
        subpoint.longitudeDeg,
      ),
      rangeKm: rangeKm(
        observerLatitudeDeg,
        observerLongitudeDeg,
        observerAltitudeKm,
        subpoint.latitudeDeg,
        subpoint.longitudeDeg,
        subpoint.altitudeKm,
      ),
    });
  }
  return above.sort((a, b) => b.elevationDeg - a.elevationDeg);
}

/** True bearing from observer to sub-satellite point, degrees 0-360. */
function azimuthDeg(
  observerLatitudeDeg: number,
  observerLongitudeDeg: number,
  targetLatitudeDeg: number,
  targetLongitudeDeg: number,
): number {
  const DEG = Math.PI / 180;
  const latitudeA = observerLatitudeDeg * DEG;
  const latitudeB = targetLatitudeDeg * DEG;
  const deltaLongitude = (targetLongitudeDeg - observerLongitudeDeg) * DEG;
  const y = Math.sin(deltaLongitude) * Math.cos(latitudeB);
  const x = Math.cos(latitudeA) * Math.sin(latitudeB)
    - Math.sin(latitudeA) * Math.cos(latitudeB) * Math.cos(deltaLongitude);
  return (Math.atan2(y, x) / DEG + 360) % 360;
}
