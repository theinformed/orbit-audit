/**
 * Does the shipped route sail on water?
 *
 * The planner shipped a default transit that went straight through Oahu and
 * Kauai. Sean: "this is supposed to be a Navy program. Your default path has a
 * ship sailing straight through continents." Nothing had ever checked it — the
 * route was hand-typed pier to pier and looked fine at world scale, which is
 * exactly the resolution at which a 200 km error is invisible.
 *
 * So this file checks it, against the SAME published Natural Earth 1:110m land
 * artifact the map and the globe draw (`manifest.land`), not against a copy or
 * a memory of one. A preset that crosses land, or squeaks past a coast by less
 * than `MINIMUM_COAST_CLEARANCE_KM`, fails here and cannot ship.
 *
 * The regression test re-runs the OLD default and asserts it would have failed,
 * so the check cannot quietly stop working.
 */

import { describe, expect, it } from "vitest";
import { loadLand } from "./transit-fixtures";
import {
  MINIMUM_COAST_CLEARANCE_KM,
  buildLandIndex,
  isOnLand,
  minimumCoastClearanceKm,
  routeLandCrossings,
} from "../src/transit-land";
import {
  DEFAULT_PRESET_ID,
  PRESET_SPEED_KNOTS,
  TRANSIT_PRESETS,
  presetById,
  routeFromPreset,
} from "../src/transit-presets";
import { buildLegs, type TransitRoute } from "../src/transit-route";

const land = await loadLand();
const index = buildLandIndex(land);

let sequence = 0;
const nextId = () => `wp-${(sequence += 1)}`;
const departure = Date.parse("2026-09-01T06:00:00Z");

function routeOf(id: string): TransitRoute {
  return routeFromPreset(presetById(id)!, departure, nextId);
}

describe("the land check itself", () => {
  it("knows the middle of a continent from the middle of an ocean", () => {
    expect(isOnLand(index, 133, -24)).toBe(true);
    expect(isOnLand(index, 12, 24)).toBe(true);
    expect(isOnLand(index, -98, 38)).toBe(true);
    expect(isOnLand(index, -145, 25)).toBe(false);
    expect(isOnLand(index, -35, 20)).toBe(false);
    expect(isOnLand(index, 90, -50)).toBe(false);
  });

  it("does not read the antimeridian as a coastline", () => {
    // Every point on this line is open Pacific. A ring that straddles the date
    // line — Wrangel Island, Fiji, Russia — would make crossing-counting across
    // the seam meaningless, which is why those edges are dropped.
    for (let latitude = -60; latitude <= 60; latitude += 5) {
      expect(isOnLand(index, 180, latitude), `180E ${latitude}`).toBe(false);
      expect(isOnLand(index, -180, latitude), `180W ${latitude}`).toBe(false);
    }
  });

  it("measures a clearance that grows as you leave the coast", () => {
    // Due west of Portugal, three distances offshore.
    const near = minimumCoastClearanceKm(index, {
      trackModel: "great-circle",
      waypoints: [
        { id: "a", label: "a", latitudeDeg: 39, longitudeDeg: -9.9, timeMs: 0 },
        { id: "b", label: "b", latitudeDeg: 39, longitudeDeg: -9.9, timeMs: 1 },
      ],
    }).km;
    const far = minimumCoastClearanceKm(index, {
      trackModel: "great-circle",
      waypoints: [
        { id: "a", label: "a", latitudeDeg: 39, longitudeDeg: -13, timeMs: 0 },
        { id: "b", label: "b", latitudeDeg: 39, longitudeDeg: -13, timeMs: 1 },
      ],
    }).km;
    expect(far).toBeGreaterThan(near);
  });
});

describe("the route this page ships", () => {
  it("is a preset, so it is one of the routes checked below", () => {
    expect(presetById(DEFAULT_PRESET_ID)).toBeDefined();
  });

  it("REGRESSION: the route this replaced crossed land, and this check catches it", () => {
    // Pearl Harbor pier -> Midway -> Yokosuka pier, the shipped default until
    // 2026-08-19. If this ever comes back clean, the check has broken, not the
    // history.
    const old: TransitRoute = {
      trackModel: "great-circle",
      waypoints: [
        { id: "a", label: "Pearl Harbor", latitudeDeg: 21.35, longitudeDeg: -157.95, timeMs: departure },
        { id: "b", label: "Midway", latitudeDeg: 28.2, longitudeDeg: -177.35, timeMs: departure + 60 * 3_600_000 },
        { id: "c", label: "Yokosuka", latitudeDeg: 35.28, longitudeDeg: 139.67, timeMs: departure + 168 * 3_600_000 },
      ],
    };
    expect(routeLandCrossings(index, old).length).toBeGreaterThan(0);
  });
});

describe("every shipped preset", () => {
  for (const preset of TRANSIT_PRESETS) {
    it(`${preset.label} never crosses land`, () => {
      const crossings = routeLandCrossings(index, routeOf(preset.id));
      expect(
        crossings.map((crossing) =>
          `leg ${crossing.legIndex + 1} at ${crossing.latitudeDeg.toFixed(2)}, ${crossing.longitudeDeg.toFixed(2)}`),
      ).toEqual([]);
    });

    it(`${preset.label} clears the coastline by at least ${MINIMUM_COAST_CLEARANCE_KM} km`, () => {
      const closest = minimumCoastClearanceKm(index, routeOf(preset.id));
      expect(
        closest.km,
        `closest approach ${closest.km.toFixed(1)} km at ${closest.latitudeDeg.toFixed(2)}, ${closest.longitudeDeg.toFixed(2)}`,
      ).toBeGreaterThan(MINIMUM_COAST_CLEARANCE_KM);
    });

    it(`${preset.label} implies a speed a ship can make`, () => {
      // Times are derived from distance at PRESET_SPEED_KNOTS, so every leg has
      // to come back at that speed. A preset that claims 40 knots across the
      // Pacific is a preset nobody checked.
      for (const leg of buildLegs(routeOf(preset.id))) {
        expect(leg.speedKnots, `${preset.label} leg ${leg.index + 1}`).toBeCloseTo(PRESET_SPEED_KNOTS, 0);
      }
    });

    it(`${preset.label} runs forward in time`, () => {
      const route = routeOf(preset.id);
      expect(route.waypoints.length).toBeGreaterThanOrEqual(2);
      for (let step = 1; step < route.waypoints.length; step += 1) {
        expect(route.waypoints[step]!.timeMs).toBeGreaterThan(route.waypoints[step - 1]!.timeMs);
      }
    });
  }

  it("keeps every transit inside the public build's element-age horizon", () => {
    // The public build refuses to answer more than 14 days past the catalog's
    // own vintage. A preset that cannot be solved on the day it ships shows an
    // error instead of a lesson.
    for (const preset of TRANSIT_PRESETS) {
      const route = routeOf(preset.id);
      const days = (route.waypoints.at(-1)!.timeMs - route.waypoints[0]!.timeMs) / 86_400_000;
      expect(days, preset.label).toBeLessThan(10);
    }
  });

  it("labels every waypoint as a position at sea, never as a berth", () => {
    // A pier is inside the coastline. Naming one is how the old default ended
    // up drawn across an island.
    for (const preset of TRANSIT_PRESETS) {
      for (const waypoint of preset.waypoints) {
        expect(isOnLand(index, waypoint.longitudeDeg, waypoint.latitudeDeg), `${preset.label}: ${waypoint.label}`)
          .toBe(false);
      }
    }
  });
});
