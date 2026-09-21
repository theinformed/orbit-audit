/**
 * Transit presets: real, navigable routes a Navy reader recognises.
 *
 * ## Why this file exists
 *
 * The shipped default sailed through Oahu. Sean, on the page: "this is supposed
 * to be a Navy program. Your default path has a ship sailing straight through
 * continents." Measured against the release's own Natural Earth 1:110m land
 * artifact, the old default (Pearl Harbor pier → Midway → Yokosuka pier) put
 * eleven sampled track positions on land: it left the pier across Oahu, crossed
 * Kauai, and arrived over the Miura peninsula. It was never checked against a
 * coastline, only eyeballed.
 *
 * ## The rule these routes are built to
 *
 * Every waypoint is a position a ship can actually be in, and every leg is
 * open water. `tests/transit-route-land.test.ts` samples each leg of every
 * preset against the shipped coastline and fails if any sample falls on land or
 * within `MINIMUM_COAST_CLEARANCE_KM` of it. The shipped presets clear by 18 km
 * at the tightest, which is the departure box off Pearl Harbor.
 *
 * ## What a waypoint is NOT
 *
 * It is not a berth. A pier is inside the coastline and a route drawn to one is
 * a route drawn across land, which is exactly the bug this file fixes. Every
 * endpoint here is an approach or departure position offshore of its port, and
 * is labelled as one. Nothing here is a routing product: there is no traffic
 * separation, no depth, no set and drift, and no navigational clearance. It is a
 * plausible track for a visibility calculation and it says so.
 *
 * Positions are read off the port's own approaches to the nearest few minutes of
 * arc. They are teaching positions, not charted waypoints.
 */

import type { TransitRoute, Waypoint } from "./transit-route";
import { buildLegs } from "./transit-route";

/** Nautical miles per kilometre denominator, matching `transit-route.ts`. */
const KM_PER_NAUTICAL_MILE = 1.852;

/**
 * Speed of advance for a preset, in knots.
 *
 * 18 knots is an ordinary independent-steaming SOA for a surface combatant. It
 * is chosen so the implied speed the planner reports back is a number a reader
 * recognises rather than one that falls out of arbitrary times.
 */
export const PRESET_SPEED_KNOTS = 18;

export interface PresetWaypoint {
  label: string;
  latitudeDeg: number;
  longitudeDeg: number;
}

export interface TransitPreset {
  id: string;
  /** Short enough for a chip. */
  label: string;
  /** One line: which fleet's water this is, and what the transit is for. */
  note: string;
  waypoints: PresetWaypoint[];
}

export const TRANSIT_PRESETS: TransitPreset[] = [
  {
    id: "pearl-yokosuka",
    label: "Pearl Harbor → Yokosuka",
    note: "3rd Fleet into 7th Fleet, west of the Hawaiian chain and south of Midway.",
    waypoints: [
      { label: "Pearl Harbor approaches", latitudeDeg: 21.05, longitudeDeg: -158.05 },
      { label: "West of Niihau", latitudeDeg: 21.0, longitudeDeg: -161.5 },
      { label: "South of Midway", latitudeDeg: 27.5, longitudeDeg: -178.0 },
      { label: "Tokyo Bay approaches", latitudeDeg: 34.7, longitudeDeg: 139.95 },
    ],
  },
  {
    id: "sandiego-pearl",
    label: "San Diego → Pearl Harbor",
    note: "The 3rd Fleet crossing, passing south of Maui.",
    waypoints: [
      { label: "San Diego approaches", latitudeDeg: 32.55, longitudeDeg: -117.35 },
      { label: "South of Maui", latitudeDeg: 20.2, longitudeDeg: -156.6 },
      { label: "Pearl Harbor approaches", latitudeDeg: 21.05, longitudeDeg: -158.05 },
    ],
  },
  {
    id: "yokosuka-guam",
    label: "Yokosuka → Guam",
    note: "Inside 7th Fleet the whole way, and short enough to solve quickly.",
    waypoints: [
      { label: "Tokyo Bay approaches", latitudeDeg: 34.7, longitudeDeg: 139.95 },
      { label: "Apra Harbor approaches", latitudeDeg: 13.4, longitudeDeg: 144.55 },
    ],
  },
  {
    id: "norfolk-rota",
    label: "Norfolk → Rota",
    note: "The Atlantic crossing into 6th Fleet water, entering the Gulf of Cadiz.",
    waypoints: [
      { label: "Chesapeake approaches", latitudeDeg: 36.95, longitudeDeg: -75.7 },
      { label: "West of Cape St Vincent", latitudeDeg: 36.6, longitudeDeg: -9.6 },
      { label: "Rota approaches", latitudeDeg: 36.4, longitudeDeg: -6.7 },
    ],
  },
  {
    id: "norfolk-keflavik",
    label: "Norfolk → Keflavik",
    // NOT "where geostationary coverage runs out", which is what this said
    // until 2026-09-08 and which the tool itself contradicts: at 64.1 N a
    // geostationary satellite on your meridian is still 17.6 degrees up, so
    // every GEO system on the page covers this transit at the default 5
    // degree mask. What is true is that the margin is nearly gone - raise
    // the mask past about 18 degrees and the whole geostationary half of the
    // list drops out at once, which is the thing this route is for showing.
    note: "Up through the GIUK gap to 64 N, where a geostationary satellite is barely 18 degrees above the horizon. Raise the mask and watch which systems survive.",
    waypoints: [
      { label: "Chesapeake approaches", latitudeDeg: 36.95, longitudeDeg: -75.7 },
      { label: "East of Nantucket", latitudeDeg: 40.5, longitudeDeg: -66.5 },
      { label: "Grand Banks east", latitudeDeg: 44.5, longitudeDeg: -49.0 },
      { label: "Irminger Sea", latitudeDeg: 60.0, longitudeDeg: -30.0 },
      { label: "Keflavik approaches", latitudeDeg: 64.1, longitudeDeg: -23.6 },
    ],
  },
];

export const DEFAULT_PRESET_ID = "pearl-yokosuka";

/**
 * Turn a preset into a route, timing every waypoint from the leg distance at
 * `PRESET_SPEED_KNOTS`.
 *
 * Times are DERIVED, never typed in. The planner reports the implied speed of
 * every leg back to the reader, and a hand-typed time is how a preset ends up
 * claiming 40 knots across the Pacific without anybody noticing.
 */
export function routeFromPreset(
  preset: TransitPreset,
  departureMs: number,
  nextId: () => string,
): TransitRoute {
  const waypoints: Waypoint[] = preset.waypoints.map((waypoint) => ({
    id: nextId(),
    label: waypoint.label,
    latitudeDeg: waypoint.latitudeDeg,
    longitudeDeg: waypoint.longitudeDeg,
    timeMs: departureMs,
  }));
  const route: TransitRoute = { trackModel: "great-circle", waypoints };
  // buildLegs reads the great-circle separation, which does not depend on the
  // (as yet meaningless) times, so one pass is enough.
  let timeMs = departureMs;
  buildLegs(route).forEach((leg) => {
    const hours = leg.greatCircleKm / KM_PER_NAUTICAL_MILE / PRESET_SPEED_KNOTS;
    timeMs += Math.round(hours * 3_600_000);
    waypoints[leg.index + 1]!.timeMs = timeMs;
  });
  return route;
}

export function presetById(id: string): TransitPreset | undefined {
  return TRANSIT_PRESETS.find((preset) => preset.id === id);
}
