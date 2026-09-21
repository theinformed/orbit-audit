import { describe, expect, it } from "vitest";
import {
  GEOSPACE_SLICE_DISPLAY_MODES,
  GEOSPACE_SLICE_MASK,
  contourAdaptivePlaneField,
  decodeAdaptivePlaneField,
  prepareAdaptivePlaneField,
} from "../src/geospace-slice-data";
import type { EncodedAdaptivePlaneDefinition, SmoothedAdaptivePlaneField } from "../src/geospace-slice-data";

function encodedBytes(values: number[]) {
  return btoa(String.fromCharCode(...values));
}

function littleEndianU16(values: number[]) {
  const bytes = new Uint8Array(values.length * 2);
  values.forEach((value, index) => {
    bytes[index * 2] = value & 255;
    bytes[index * 2 + 1] = value >>> 8;
  });
  return encodedBytes([...bytes]);
}

function littleEndianI16(values: number[]) {
  return littleEndianU16(values.map((value) => value < 0 ? value + 65536 : value));
}

const definition: EncodedAdaptivePlaneDefinition = {
  count: 9,
  coordinatesI16: littleEndianI16([
    0, 0, 100, 0, 200, 0,
    0, 100, 100, 100, 200, 100,
    0, 200, 100, 200, 200, 200,
  ]),
  boundsRe: [0, 2, 0, 2],
};

const field = {
  valuesU16: littleEndianU16([0, 8192, 16384, 24576, 32768, 40960, 49152, 57344, 65535]),
  masksU8: encodedBytes([GEOSPACE_SLICE_MASK.clippedLow, 0, 0, 0, GEOSPACE_SLICE_MASK.missing, 0, 0, 0, GEOSPACE_SLICE_MASK.clippedHigh]),
};

describe("SWMF adaptive-plane display preparation", () => {
  it("preserves exact native missing and saturation masks", () => {
    const native = decodeAdaptivePlaneField(definition, field);
    expect(native.coordinates[2]).toBe(1);
    expect(Number.isNaN(native.values[4])).toBe(true);
    expect(native.masks[0]).toBe(GEOSPACE_SLICE_MASK.clippedLow);
    expect(native.masks[8]).toBe(GEOSPACE_SLICE_MASK.clippedHigh);
    expect(prepareAdaptivePlaneField(definition, field, { mode: "native" }).mode).toBe("native");
  });

  it("defaults to smooth gap-aware interpolation without creating extrema", () => {
    const prepared = prepareAdaptivePlaneField(definition, field, {
      spacingRe: 0.5,
      maximumSupportDistanceRe: 1.1,
      minimumRadiusRe: 0,
    });
    expect(prepared.mode).toBe("smooth");
    if (prepared.mode !== "smooth") throw new Error("expected smooth field");
    expect([prepared.width, prepared.height]).toEqual([5, 5]);
    expect(Number.isNaN(prepared.values[12])).toBe(true);
    expect(prepared.masks[12]! & GEOSPACE_SLICE_MASK.missing).toBeTruthy();
    const finite = [...prepared.values].filter(Number.isFinite);
    expect(Math.min(...finite)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...finite)).toBeLessThanOrEqual(1);
    expect([...prepared.masks].some((mask) => (mask & GEOSPACE_SLICE_MASK.clippedHigh) !== 0)).toBe(true);
    expect([...prepared.masks].some((mask) => (mask & GEOSPACE_SLICE_MASK.interpolated) !== 0)).toBe(true);
  });

  it("builds contours only through fully supported smooth cells", () => {
    const grid: SmoothedAdaptivePlaneField = {
      mode: "smooth",
      width: 2,
      height: 2,
      boundsRe: [0, 1, 0, 1],
      values: new Float32Array([0, 1, 0, 1]),
      masks: new Uint8Array(4),
    };
    expect(contourAdaptivePlaneField(grid, [0.5])[0]!.coordinates.length).toBe(4);
    grid.masks[0] = GEOSPACE_SLICE_MASK.missing;
    expect(contourAdaptivePlaneField(grid, [0.5])[0]!.coordinates.length).toBe(0);
  });

  it("exposes Smooth as the truthful default and Native grid as opt-in", () => {
    expect(GEOSPACE_SLICE_DISPLAY_MODES.smooth.label).toBe("Smooth");
    expect(GEOSPACE_SLICE_DISPLAY_MODES.native.label).toBe("Native grid");
  });
});
