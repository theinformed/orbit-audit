/**
 * Measured ionosonde soundings, and the rules for when one is allowed to speak
 * about a place it is not standing in.
 *
 * These are the only ionospheric layer parameters on this site that an
 * instrument actually observed. An ionosonde sweeps a radio pulse upward
 * through the HF band and times the echo; the frequency at which the echo
 * stops returning is that layer's critical frequency, and the delay gives its
 * height. Scaling the resulting ionogram yields foF2/hmF2, foE/hmE and, in
 * daylight, foF1/hmF1. That is a measurement, so everything in this file
 * carries the `observed` evidence class - and, exactly because of that, none
 * of it may be quietly spread across the globe. `ionosphere-composite.ts` is
 * where these values are allowed to influence a drawn layer, under a
 * `composite` badge and a distance-dependent weight.
 *
 * The three ways a sounding can mislead, and what this module does about each
 * --------------------------------------------------------------------------
 * 1. DISTANCE. Area-weighted over the globe on 2026-08-19 the nearest sounding
 *    less than three hours old had a median distance of 2,643 km, and only
 *    3.8% of Earth's surface was within 500 km of one. The far case is the
 *    COMMON case, so `soundingRelevance` exists to grade it and the UI states
 *    the distance next to the station's name every single time.
 * 2. AGE. The upstream feed is a last-known-value roster with no expiry: of
 *    101 stations, 74 had not sounded in over a day and the oldest was 11
 *    years stale. The pipeline drops anything older than three hours before it
 *    reaches the browser, and what survives still shows its age.
 * 3. ABSENCE READ AS A GAP. A null foF1 at night means there is no F1 layer,
 *    which is a fact about the ionosphere and not a fault in the data. Every
 *    consumer of this module must distinguish the two, and `LayerReading`
 *    forces the question by making the absent case carry a reason.
 */

import type { GeographicPoint } from "./d-region-empirical";

/** One station's most recent scaled ionogram. Shape matches the pipeline artifact. */
export interface Sounding {
  code: string;
  name: string;
  latitudeDeg: number;
  longitudeDeg: number;
  soundedAt: string;
  ageMinutes: number;
  foF2Mhz: number | null;
  hmF2Km: number | null;
  foF1Mhz: number | null;
  hmF1Km: number | null;
  foEMhz: number | null;
  hmEKm: number | null;
  /**
   * True when the upstream reported the autoscaler's nominal 110.0 km rather
   * than a scaled height. 23 of 101 records carried exactly 110.0 while every
   * other height occurred once, so this is a placeholder and is not drawn as a
   * measured peak height.
   */
  eHeightIsNominal: boolean;
  /** Sporadic E. A thin irregular patch, NOT the regular E layer - kept apart deliberately. */
  foEsMhz: number | null;
  confidence: number | null;
  upstreamSource: string | null;
}

export interface SoundingBundle {
  schemaVersion: number;
  observedAt: string;
  evidence: "observed";
  freshLimitMinutes: number;
  stations: Sounding[];
  upstreamStationCount: number;
  staleStationCount: number;
  unreadableRecordCount: number;
  withFoF2: number;
  withFoE: number;
  withFoF1: number;
  attribution: string;
  sourceNote: string;
  sourceUrl: string;
}

const EARTH_RADIUS_KM = 6_371;

/**
 * Great-circle distance, via the haversine form.
 *
 * Haversine rather than the spherical law of cosines because the law of
 * cosines loses precision for small separations - and small separations are
 * exactly the case that decides whether a sounding is allowed to describe the
 * reader's point.
 */
export function greatCircleDistanceKm(a: GeographicPoint, b: GeographicPoint): number {
  const toRad = (degrees: number) => (degrees * Math.PI) / 180;
  const dLat = toRad(b.latitudeDeg - a.latitudeDeg);
  const dLon = toRad(b.longitudeDeg - a.longitudeDeg);
  const lat1 = toRad(a.latitudeDeg);
  const lat2 = toRad(b.latitudeDeg);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * How much a sounding this far away is allowed to claim about the reader's
 * point. The boundaries are the measured decorrelation of foF2 residuals
 * between station pairs (see ANCHOR_EFOLD_KM in `ionosphere-composite.ts`):
 * below 500 km a pair differs by 11% of the unrelated-pair level, by
 * 3,000-5,000 km it has reached 92% and there is nothing left to borrow.
 */
export type SoundingRelevance = "here" | "regional" | "distant" | "unrelated";

export function soundingRelevance(distanceKm: number): SoundingRelevance {
  if (!Number.isFinite(distanceKm) || distanceKm < 0) return "unrelated";
  if (distanceKm <= 500) return "here";
  if (distanceKm <= 2_000) return "regional";
  // 3,000 km, not 5,000, so this agrees with ANCHOR_IGNORE_KM. The two were
  // set independently at first and the panel ended up saying a sounding
  // carried "very little information" in the same breath as reporting that it
  // was beyond the range where soundings relate to each other at all. A band
  // boundary that contradicts the arithmetic it describes is worse than no
  // band at all.
  if (distanceKm <= 3_000) return "distant";
  return "unrelated";
}

/**
 * What the distance means, as a sentence.
 *
 * The station's name, its distance and its age are printed by the caller, so
 * this returns only the judgement. Building the name and distance in here as
 * well forced the one caller to strip them back out again, which is a fragile
 * way to say something this function should simply not have said.
 */
export function relevanceNote(relevance: SoundingRelevance): string {
  switch (relevance) {
    case "here":
      return "Close enough that this sounding describes the ionosphere over your point.";
    case "regional":
      return "A regional sounding, not a measurement over your point - the layers here can differ from it.";
    case "distant":
      return "At that range a sounding carries very little information about your point. Read it as the "
        + "nearest observation that exists, not as a description of here.";
    case "unrelated":
      return "That is beyond the range at which two soundings tell you anything about each other, so no "
        + "measured layer structure is available for this point.";
  }
}

/**
 * A layer's value at a station, with absence separated from ignorance.
 *
 * The union is the point of this type. `absent` means the layer is not there -
 * F1 at night, E after sunset - which is a real result. `unscaled` means the
 * ionogram existed but nobody could read that parameter off it, usually
 * because absorption or interference blanketed the trace. Rendering those two
 * the same way would teach a reader that the ionosphere has gaps in it, which
 * it does not.
 */
export type LayerReading =
  | { state: "measured"; criticalFrequencyMhz: number; peakHeightKm: number | null; heightIsNominal: boolean }
  | { state: "absent"; reason: string }
  | { state: "unscaled"; reason: string };

/**
 * Read one layer off a sounding.
 *
 * `solarZenithDeg` decides between `absent` and `unscaled`, because the feed
 * itself cannot: a null foF1 is just a null. Only the sun's angle tells you
 * whether the layer should have been there. The threshold is the measured one
 * - no station in the network reported an F1 layer above 72.5 deg.
 */
export function readLayer(
  station: Sounding,
  layer: "E" | "F1" | "F2",
  solarZenithDeg: number,
): LayerReading {
  const value = layer === "E" ? station.foEMhz : layer === "F1" ? station.foF1Mhz : station.foF2Mhz;
  const height = layer === "E" ? station.hmEKm : layer === "F1" ? station.hmF1Km : station.hmF2Km;

  if (value !== null) {
    return {
      state: "measured",
      criticalFrequencyMhz: value,
      peakHeightKm: height,
      heightIsNominal: layer === "E" ? station.eHeightIsNominal : false,
    };
  }

  if (layer === "F1" && solarZenithDeg > 72.5) {
    return {
      state: "absent",
      reason: "No F1 layer - it is a daytime-only layer and the sun is too low here.",
    };
  }
  if (layer === "E" && solarZenithDeg >= 95) {
    return {
      state: "absent",
      reason: "No measurable E layer - it is produced by sunlight and recombines after sunset.",
    };
  }
  return {
    state: "unscaled",
    reason: layer === "F2"
      ? "The F2 trace could not be scaled from this ionogram."
      : `The sounding was taken but the ${layer} layer could not be scaled from it, usually because `
        + "absorption or interference blanketed the trace.",
  };
}

/** The nearest station to a point, or null when the network is empty. */
export function nearestSounding(
  point: GeographicPoint,
  stations: readonly Sounding[],
): { station: Sounding; distanceKm: number } | null {
  let best: { station: Sounding; distanceKm: number } | null = null;
  for (const station of stations) {
    const distanceKm = greatCircleDistanceKm(point, station);
    if (best === null || distanceKm < best.distanceKm) best = { station, distanceKm };
  }
  return best;
}

/** Plain-language age, because "312" is not a sounding age a reader can use. */
export function soundingAgeNote(ageMinutes: number): string {
  if (!Number.isFinite(ageMinutes) || ageMinutes < 0) return "Sounding time unknown.";
  if (ageMinutes < 1) return "Sounded less than a minute ago.";
  if (ageMinutes < 90) return `Sounded ${Math.round(ageMinutes)} minutes ago.`;
  return `Sounded ${(ageMinutes / 60).toFixed(1)} hours ago.`;
}

export const SOUNDING_EVIDENCE_NOTE =
  "OBSERVED: these are scaled ionograms from real ionosondes - a radio pulse swept upward "
  + "and its echo timed. No model produced any value in this panel. The site read them from "
  + "the prop.kc2g.com aggregator, which republishes soundings distributed by the Lowell GIRO "
  + "Data Center and INGV on behalf of the observatories that operate the instruments.";
