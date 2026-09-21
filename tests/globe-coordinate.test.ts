import { describe, expect, it } from "vitest";
import { gsmSceneAxes } from "../src/globe";

describe("GSM-to-scene coordinate mapping", () => {
  it("maps equatorial GSM +Y to scene -Z", () => {
    expect(gsmSceneAxes(0, 1, 0).toArray()).toEqual([0, 0, -1]);
  });

  it("maps meridional GSM +Z to scene +Y while preserving Sunward +X", () => {
    expect(gsmSceneAxes(1, 0, 1).toArray()).toEqual([1, 1, 0]);
  });
});
