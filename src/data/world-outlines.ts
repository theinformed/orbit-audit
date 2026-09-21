/**
 * Decoder for the vendored Natural Earth 1:110m outlines in `world-110m.ts`.
 *
 * The asset is bundled into the JavaScript rather than fetched, so the map
 * draws real coastlines with no network request of any kind. Decoding is done
 * once, lazily, the first time a map is drawn, and cached.
 */
import {
  WORLD_BOUNDARIES_110M,
  WORLD_LAKES_110M,
  WORLD_LAND_110M,
  WORLD_OUTLINE_SCALE,
  WORLD_OUTLINE_SOURCE,
} from "./world-110m";

/** A single outline: [longitudeDeg, latitudeDeg] pairs in drawing order. */
export type Outline = ReadonlyArray<readonly [number, number]>;

export interface WorldOutlines {
  /** Closed land polygons; fill these and their edge is the coastline. */
  readonly land: readonly Outline[];
  /** International boundaries on land; open polylines. */
  readonly boundaries: readonly Outline[];
  /** Inland water bodies; closed polygons. */
  readonly lakes: readonly Outline[];
}

export const WORLD_OUTLINE_ATTRIBUTION = WORLD_OUTLINE_SOURCE;

function decodeBase64(encoded: string): Uint8Array {
  // atob is a global in browsers, in jsdom, and in Node 16 and later, which
  // covers both the app and the test runner.
  if (typeof atob !== "function") throw new Error("base64 decoding is unavailable in this environment");
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

/** Unsigned LEB128 varints holding zigzagged signed integers. */
export function decodeOutlineLayer(encoded: string, scale = WORLD_OUTLINE_SCALE): Outline[] {
  const bytes = decodeBase64(encoded);
  let cursor = 0;
  const readVarint = (): number => {
    let result = 0;
    let shift = 1;
    for (;;) {
      const byte = bytes[cursor];
      cursor += 1;
      if (byte === undefined) throw new Error("world outline asset is truncated");
      result += (byte & 0x7f) * shift;
      if ((byte & 0x80) === 0) return result;
      shift *= 128;
    }
  };
  const readSigned = (): number => {
    const value = readVarint();
    return value % 2 === 0 ? value / 2 : -(value + 1) / 2;
  };

  const ringCount = readVarint();
  const rings: Outline[] = [];
  for (let ring = 0; ring < ringCount; ring += 1) {
    const pointCount = readVarint();
    const points: Array<readonly [number, number]> = [];
    let x = readSigned();
    let y = readSigned();
    points.push([x / scale, y / scale]);
    for (let index = 1; index < pointCount; index += 1) {
      x += readSigned();
      y += readSigned();
      points.push([x / scale, y / scale]);
    }
    rings.push(points);
  }
  return rings;
}

let cached: WorldOutlines | null = null;

export function worldOutlines(): WorldOutlines {
  if (cached) return cached;
  cached = {
    land: decodeOutlineLayer(WORLD_LAND_110M),
    boundaries: decodeOutlineLayer(WORLD_BOUNDARIES_110M),
    lakes: decodeOutlineLayer(WORLD_LAKES_110M),
  };
  return cached;
}
