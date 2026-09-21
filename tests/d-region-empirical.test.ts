import { describe, expect, it } from "vitest";
import {
  D_REGION_EMPIRICAL_METHOD,
  EmpiricalDRegionLayer,
  dRegionIllumination,
  flareHeightLoweringKm,
  sampleEmpiricalDRegion,
  waitSpiesElectronDensityM3,
} from "../src/d-region-empirical";

const at = new Date("2026-03-20T12:00:00Z");
const subsolar = { latitudeDeg: 0, longitudeDeg: 0 };

describe("empirical D-region model", () => {
  it("uses the published Wait–Spies density equation", () => {
    const expected = 1.43e13 * Math.exp(-0.15 * 70) * Math.exp((0.34 - 0.15) * 4);
    expect(waitSpiesElectronDensityM3(74, 70, 0.34)).toBeCloseTo(expected, 8);
    expect(waitSpiesElectronDensityM3(75, 70, 0.34))
      .toBeGreaterThan(waitSpiesElectronDensityM3(70, 70, 0.34));
  });

  it("moves the effective height and density through the day-night cycle", () => {
    const noon = sampleEmpiricalDRegion(0, 0, at, 1e-7, subsolar);
    const midnight = sampleEmpiricalDRegion(0, 180, at, 1e-7, subsolar);
    expect(noon.effectiveHeightKm).toBeCloseTo(70, 6);
    expect(midnight.effectiveHeightKm).toBeCloseTo(84, 6);
    expect(noon.betaPerKm).toBeCloseTo(0.34, 6);
    expect(midnight.betaPerKm).toBeCloseTo(0.63, 6);
    expect(noon.electronDensityAt74KmM3).toBeGreaterThan(midnight.electronDensityAt74KmM3 * 100);
  });

  it("lowers only the sunlit D-region as observed X-ray flux rises", () => {
    const quiet = sampleEmpiricalDRegion(0, 0, at, 1e-6, subsolar);
    const x5 = sampleEmpiricalDRegion(0, 0, at, 5e-4, subsolar);
    const darkX5 = sampleEmpiricalDRegion(0, 180, at, 5e-4, subsolar);
    expect(x5.effectiveHeightKm).toBeGreaterThan(57);
    expect(x5.effectiveHeightKm).toBeLessThan(59);
    expect(x5.betaPerKm).toBeGreaterThan(quiet.betaPerKm);
    expect(x5.electronDensityAt74KmM3).toBeGreaterThan(quiet.electronDensityAt74KmM3);
    expect(darkX5.effectiveHeightKm).toBeCloseTo(84, 6);
    expect(darkX5.flareHeightLoweringKm).toBe(0);
  });

  it("constrains rather than silently extrapolates the published flare domain", () => {
    expect(flareHeightLoweringKm(4.5e-3)).toBeCloseTo(17, 6);
    expect(flareHeightLoweringKm(1)).toBeCloseTo(17, 6);
    expect(sampleEmpiricalDRegion(0, 0, at, 1, subsolar).fluxDomain).toBe("above-validated");
    expect(sampleEmpiricalDRegion(0, 0, at, 1e-8, subsolar).fluxDomain).toBe("below-validated");
  });

  it("uses Schmitter's 94-degree illumination boundary", () => {
    expect(dRegionIllumination(0)).toBeCloseTo(1);
    expect(dRegionIllumination(90)).toBeGreaterThan(0);
    expect(dRegionIllumination(94)).toBe(0);
    expect(dRegionIllumination(120)).toBe(0);
  });

  it("builds a smooth indexed surface with evidence and live state metadata", () => {
    const layer = new EmpiricalDRegionLayer(100, 12, 6);
    layer.setSimulationTime(at);
    layer.setXrayFlux(1e-5);
    expect(layer.mesh.geometry.index?.count).toBe(12 * 6 * 6);
    expect(layer.mesh.geometry.userData.method.evidence).toBe("empirical");
    expect(layer.getState().effectiveHeightRangeKm[0])
      .toBeLessThan(layer.getState().effectiveHeightRangeKm[1]);
    expect(layer.getState().densityAt74KmRangeM3[1])
      .toBeGreaterThan(layer.getState().densityAt74KmRangeM3[0]);
    layer.dispose();
  });

  it("publishes the primary equations and limitations instead of hiding approximation", () => {
    expect(D_REGION_EMPIRICAL_METHOD.sources.map((source) => source.doi)).toContain(
      "https://doi.org/10.5194/angeo-31-765-2013",
    );
    expect(D_REGION_EMPIRICAL_METHOD.limitations.join(" ")).toContain("not a hard physical top");
    expect(D_REGION_EMPIRICAL_METHOD.limitations.join(" ")).toContain("GOES long-channel");
  });
});

