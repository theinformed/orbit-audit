import { describe, expect, it } from "vitest";
import { geospaceSuccessorIndex, glotecQualityOpacity, longitudeTextureX } from "../src/globe";

describe("geospace frame sequencing", () => {
  it("interpolates forward but holds the final frame instead of blending backward", () => {
    expect(geospaceSuccessorIndex(0, 6)).toBe(1);
    expect(geospaceSuccessorIndex(4, 6)).toBe(5);
    expect(geospaceSuccessorIndex(5, 6)).toBe(5);
  });
});

describe("GloTEC quality encoding", () => {
  it("uses a restrained monotonic observation-count emphasis", () => {
    const opacities = [0, 1, 2, 3, 4, 5].map(glotecQualityOpacity);
    expect(opacities[0]).toBeCloseTo(0.3);
    expect(opacities[5]).toBeCloseTo(0.48);
    expect(opacities.every((value, index) => index === 0 || value > opacities[index - 1]!)).toBe(true);
  });

  it("clamps missing and out-of-range flags conservatively", () => {
    expect(glotecQualityOpacity(null)).toBeCloseTo(0.3);
    expect(glotecQualityOpacity(-1)).toBeCloseTo(0.3);
    expect(glotecQualityOpacity(99)).toBeCloseTo(0.48);
  });
});

describe("global field longitude encoding", () => {
  it("maps NOAA 0–359 degree longitudes across the full texture", () => {
    expect(longitudeTextureX(0, 720)).toBeCloseTo(360);
    expect(longitudeTextureX(179, 720)).toBeCloseTo(718);
    expect(longitudeTextureX(180, 720)).toBeCloseTo(0);
    expect(longitudeTextureX(359, 720)).toBeCloseTo(358);
    expect(longitudeTextureX(-180, 720)).toBeCloseTo(0);
  });
});
