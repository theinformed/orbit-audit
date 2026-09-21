import { describe, expect, it } from "vitest";
import { goesXrayClass, sampleLogTimeValue, sampleMagnetopauseDriver } from "../src/environment-time";

describe("time-selected environment drivers", () => {
  it("interpolates propagated solar-wind inputs and recomputes the nonlinear Shue boundary", () => {
    const sample = sampleMagnetopauseDriver([
      { validAt: "2026-08-06T00:00:00Z", observedAt: "2026-08-05T23:20:00Z", speedKps: 400, densityCm3: 4, bzGsmNt: 2, dynamicPressureNpa: 1.07, subsolarStandoffRe: 10, flaringAlpha: 0.6 },
      { validAt: "2026-08-06T00:10:00Z", observedAt: "2026-08-05T23:30:00Z", speedKps: 600, densityCm3: 8, bzGsmNt: -8, dynamicPressureNpa: 4.82, subsolarStandoffRe: 8, flaringAlpha: 0.7 },
    ], new Date("2026-08-06T00:05:00Z"));
    expect(sample?.speedKps).toBe(500);
    expect(sample?.densityCm3).toBe(6);
    expect(sample?.bzGsmNt).toBe(-3);
    expect(sample?.dynamicPressureNpa).toBeCloseTo(2.5089, 3);
    expect(sample?.subsolarStandoffRe).toBeGreaterThan(8);
    expect(sample?.subsolarStandoffRe).toBeLessThan(11);
  });

  it("does not hold a stale environment outside its coverage", () => {
    expect(sampleMagnetopauseDriver([
      { validAt: "2026-08-06T00:00:00Z", observedAt: "2026-08-05T23:20:00Z", speedKps: 400, densityCm3: 4, bzGsmNt: 2, dynamicPressureNpa: 1, subsolarStandoffRe: 10, flaringAlpha: 0.6 },
    ], new Date("2026-08-05T23:59:00Z"))).toBeNull();
  });

  it("interpolates X-ray irradiance logarithmically and formats GOES class", () => {
    const flux = sampleLogTimeValue([
      { time: "2026-08-06T00:00:00Z", value: 1e-7 },
      { time: "2026-08-06T00:10:00Z", value: 1e-5 },
    ], new Date("2026-08-06T00:05:00Z"));
    expect(flux).toBeCloseTo(1e-6, 10);
    expect(goesXrayClass(flux)).toBe("C1.0");
  });
});
