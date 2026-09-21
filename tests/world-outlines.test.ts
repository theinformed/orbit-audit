import { describe, expect, it } from "vitest";
import {
  decodeOutlineLayer,
  WORLD_OUTLINE_ATTRIBUTION,
  worldOutlines,
} from "../src/data/world-outlines";
import { WORLD_LAND_110M } from "../src/data/world-110m";

/**
 * Even-odd ray casting over every land ring. The 1:110m land layer has no
 * interior holes worth modelling, so parity across all rings is enough to
 * answer "is this coordinate on land".
 */
function onLand(longitudeDeg: number, latitudeDeg: number): boolean {
  let inside = false;
  for (const ring of worldOutlines().land) {
    for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index, index += 1) {
      const [xi, yi] = ring[index]!;
      const [xj, yj] = ring[previous]!;
      if ((yi > latitudeDeg) !== (yj > latitudeDeg)
        && longitudeDeg < ((xj - xi) * (latitudeDeg - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
  }
  return inside;
}

describe("vendored Natural Earth outlines", () => {
  it("decodes without a network request and keeps the payload small", () => {
    const world = worldOutlines();
    expect(world.land.length).toBeGreaterThan(100);
    expect(world.boundaries.length).toBeGreaterThan(200);
    expect(world.lakes.length).toBeGreaterThan(10);
    const landPoints = world.land.reduce((sum, ring) => sum + ring.length, 0);
    expect(landPoints).toBeGreaterThan(3500);
    // A hard ceiling: this asset ships in the JavaScript bundle. If a rebuild
    // ever lands here with the simplification turned off, this fails loudly.
    expect(WORLD_LAND_110M.length).toBeLessThan(20_000);
    expect(WORLD_OUTLINE_ATTRIBUTION).toContain("Natural Earth");
  });

  it("returns the same decoded arrays on repeat calls rather than redecoding", () => {
    expect(worldOutlines()).toBe(worldOutlines());
  });

  it("keeps every coordinate inside the world and never steps across the seam", () => {
    const world = worldOutlines();
    for (const layer of [world.land, world.boundaries, world.lakes]) {
      for (const ring of layer) {
        for (const [index, [longitude, latitude]] of ring.entries()) {
          expect(Number.isFinite(longitude) && Number.isFinite(latitude)).toBe(true);
          expect(Math.abs(longitude)).toBeLessThanOrEqual(180);
          expect(Math.abs(latitude)).toBeLessThanOrEqual(90);
          if (index > 0) {
            // A step wider than half the world means a polyline drawn straight
            // across the map, which is what an unsplit antimeridian looks like.
            expect(Math.abs(longitude - ring[index - 1]![0])).toBeLessThan(180);
          }
        }
      }
    }
  });

  it("puts land where land is and ocean where ocean is", () => {
    // Interior points, chosen well away from any coast so that 1:110m
    // simplification cannot flip the answer.
    const land: Array<[string, number, number]> = [
      ["Sahara", 10, 22],
      ["Cairo", 31.24, 30.04],
      ["Colorado", -104.99, 39.74],
      ["central Australia", 133, -24],
      ["central Siberia", 82.93, 60],
      ["Amazon basin", -60, -3],
      ["Congo basin", 20, -3],
      ["East Antarctica", 0, -80],
    ];
    const ocean: Array<[string, number, number]> = [
      ["central Pacific", -140, 0],
      ["South Atlantic", -30, -20],
      ["central Indian", 80, -30],
      ["South Pacific", -120, -40],
      ["Bay of Bengal", 88, 15],
      ["North Atlantic", -40, 45],
      ["Arctic Ocean", 0, 89],
    ];
    for (const [name, longitude, latitude] of land) {
      expect(`${name}:${onLand(longitude, latitude)}`).toBe(`${name}:true`);
    }
    for (const [name, longitude, latitude] of ocean) {
      expect(`${name}:${onLand(longitude, latitude)}`).toBe(`${name}:false`);
    }
  });

  it("reaches both poles' worth of land only where land actually reaches", () => {
    const latitudes = worldOutlines().land.flatMap((ring) => ring.map(([, latitude]) => latitude));
    // Antarctica is closed along the -90 parallel; nothing is closed over the
    // north pole, where there is no land.
    expect(Math.min(...latitudes)).toBe(-90);
    expect(Math.max(...latitudes)).toBeLessThan(85);
    expect(Math.max(...latitudes)).toBeGreaterThan(80);
  });

  it("rejects a truncated asset rather than drawing nonsense", () => {
    expect(() => decodeOutlineLayer(WORLD_LAND_110M.slice(0, 24))).toThrow(/truncated/);
  });
});
