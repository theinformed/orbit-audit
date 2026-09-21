import { describe, expect, it } from "vitest";
import { calculateSubsolarPoint } from "../src/globe";

function wrappedLongitudeDifference(to: number, from: number) {
  return ((to - from + 540) % 360) - 180;
}

describe("subsolar-point geometry", () => {
  it("tracks the seasonal solar declination", () => {
    expect(calculateSubsolarPoint(new Date("2024-03-20T03:06:00Z")).latitudeDeg).toBeCloseTo(0, 1);
    expect(calculateSubsolarPoint(new Date("2024-06-20T20:51:00Z")).latitudeDeg).toBeCloseTo(23.44, 1);
    expect(calculateSubsolarPoint(new Date("2024-12-21T09:21:00Z")).latitudeDeg).toBeCloseTo(-23.44, 1);
  });

  it("moves west by about 90 degrees over six hours", () => {
    const noon = calculateSubsolarPoint(new Date("2024-03-20T12:00:00Z"));
    const evening = calculateSubsolarPoint(new Date("2024-03-20T18:00:00Z"));
    expect(noon.longitudeDeg).toBeCloseTo(1.83, 1);
    expect(wrappedLongitudeDifference(evening.longitudeDeg, noon.longitudeDeg)).toBeCloseTo(-90, 0);
  });

  it("rejects an invalid simulation time", () => {
    expect(() => calculateSubsolarPoint(new Date(Number.NaN))).toThrow(RangeError);
  });
});
