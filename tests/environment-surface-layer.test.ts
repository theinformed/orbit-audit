import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { DRAP_LAYER_POLICY, type DrapBundle, type DrapFrame } from "../src/drap";
import type { AuroraBundle, AuroraFrame } from "../src/aurora-time";
import {
  AuroraSurfaceLayerController,
  DrapSurfaceLayerController,
} from "../src/environment-surface-layer";
import { ovationBundle, REAL_OVATION_FRAME } from "./ovation-real-frame";
import { azimuthDifferenceDegrees, equirectangularLayerAzimuth } from "../src/globe";
import { RULER_EARTH_RADIUS_KM, sharedDisplayRadius } from "../src/radial-ruler";

function base64(bytes: number[]) {
  return globalThis.btoa(String.fromCharCode(...bytes));
}

function u16Base64(values: number[]) {
  return base64(values.flatMap((value) => [value & 0xff, (value >> 8) & 0xff]));
}

function drapFrame(validAt: string, values = [30, 100, 65535, 300]): DrapFrame {
  return {
    validAt,
    valuesU16: u16Base64(values),
    maximumHafMhz: 30,
    affectedCellPercent: { "3MHz": 75, "10MHz": 50, "30MHz": 25 },
  };
}

function drapBundle(frames: DrapFrame[]): DrapBundle {
  return {
    schemaVersion: "noaa-drap.v1",
    product: "NOAA SWPC D-Region Absorption Predictions (D-RAP 2)",
    status: "model",
    temporalKind: "empirical-nowcast",
    retrievedAt: "2026-08-06T20:10:00Z",
    source: {
      currentData: "https://services.swpc.noaa.gov/text/drap_global_frequencies.txt",
      productPage: "product",
      documentation: "documentation",
      historicalArchive: "archive",
      historicalFilesApi: "api",
      inputs: "GOES",
      sourceCadence: "1/5 minutes",
    },
    grid: {
      longitudeStartDeg: -178,
      longitudeStepDeg: 4,
      longitudeCount: 2,
      latitudeStartDeg: 89,
      latitudeStepDeg: -2,
      latitudeCount: 2,
      order: "latitude-major, north-to-south, west-to-east",
    },
    encoding: { type: "uint16-le-base64", scaleMhz: 0.1, missingValue: 65535 },
    quantity: {
      name: "Highest Affected Frequency",
      shortName: "1 dB HAF",
      units: "MHz",
      definition: "vertical path",
      pathGeometry: "vertical two-pass",
    },
    time: {
      validFrom: frames[0]?.validAt ?? "2026-08-06T20:00:00Z",
      validTo: frames.at(-1)?.validAt ?? "2026-08-06T20:00:00Z",
      frameCount: frames.length,
      selection: "hold latest at or before requested UTC",
      staleAfterMinutes: 12,
      futureAvailable: false,
    },
    legend: {
      title: "D-region HF absorption",
      subtitle: "1 dB HAF · MHz",
      minimumDisplayedMhz: 3,
      maximumDisplayedMhz: 30,
      ticksMhz: [3, 5, 10, 15, 20, 25, 30],
      belowMinimumLabel: "<3 MHz · below HF band",
      aboveMaximumLabel: "≥30 MHz",
    },
    messages: { estimatedRecovery: null, xray: null, xrayWarning: null, proton: null, protonWarning: null },
    frames,
    limitations: [],
    operationalDisplay: DRAP_LAYER_POLICY,
  };
}

function auroraFrame(validAt: string, observedAt = "2026-08-06T19:30:00Z"): AuroraFrame {
  return {
    observedAt,
    validAt,
    leadMinutes: (Date.parse(validAt) - Date.parse(observedAt)) / 60_000,
    probabilityU8: base64([20, 30, 70, 90]),
    validityBits: base64([0b00001110]),
    validCellCount: 3,
    missingCellCount: 1,
    maximumProbabilityPercent: 90,
    hemispheres: {
      south: { validCellCount: 1, maximumProbabilityPercent: 30 },
      north: { validCellCount: 2, maximumProbabilityPercent: 90 },
    },
  };
}

function auroraBundle(frames: AuroraFrame[]): AuroraBundle {
  return {
    schemaVersion: "noaa-ovation-history.v1",
    product: "NOAA SWPC OVATION 2020 Aurora Forecast",
    status: "model",
    temporalKind: "observation-driven forecast",
    retrievedAt: "2026-08-06T20:10:00Z",
    source: {
      currentNumericGrid: "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json",
      productPage: "product",
      wmoProductPage: "wmo",
      northImageHistoryManifest: "north",
      southImageHistoryManifest: "south",
      nceiProductInventory: "inventory",
      model: "OVATION 2020",
      inputs: "L1 solar wind",
      sourceCadenceMinutes: 5,
    },
    sourceAvailability: {
      publicNumericDistribution: "latest grid only",
      publicRenderedImageHistoryHours: 24,
      publicNumericHistoryHours: 0,
      historyMethod: "exact snapshots",
      notUsed: "images",
      inventoryCheckedAt: "2026-08-06T20:10:00Z",
    },
    grid: {
      longitudeStartDeg: 0,
      longitudeStepDeg: 1,
      longitudeCount: 2,
      // One southern and one northern auroral row. Equator-straddling rows
      // would be withdrawn as NOAA's equatorial seam.
      latitudeStartDeg: -70,
      latitudeStepDeg: 140,
      latitudeCount: 2,
      order: "latitude-major, south-to-north, west-to-east",
      longitudeConvention: "0 <= east longitude < 360",
      sourceCoordinateOrder: "longitude-major",
    },
    encoding: {
      probability: "uint8-base64",
      validity: "bitset-lsb-first-base64",
      validRangePercent: [0, 100],
      missingRepresentation: "mask",
    },
    quantity: { name: "Aurora viewing probability", units: "%", definition: "model probability" },
    time: {
      requestedHistoryHours: 48,
      requestedFrom: "2026-08-04T20:00:00Z",
      requestedTo: "2026-08-06T20:00:00Z",
      availableFrom: frames[0]?.validAt ?? "2026-08-06T20:00:00Z",
      availableTo: frames.at(-1)?.validAt ?? "2026-08-06T20:00:00Z",
      frameCount: frames.length,
      coverageComplete: false,
      noDataIntervals: [],
      selection: "hold for 12 minutes; do not interpolate",
      staleAfterMinutes: 12,
      forecastLead: "per frame",
    },
    display: {
      defaultMode: "smooth",
      nativeModeAvailable: true,
      smoothing: "spatial only",
      hemispheres: ["north", "south"],
    },
    frames,
    limitations: [],
  };
}

function texturePixels(layer: DrapSurfaceLayerController | AuroraSurfaceLayerController) {
  const image = layer.texture?.image as { data: Uint8ClampedArray; width: number; height: number } | undefined;
  if (!image) throw new Error("texture missing");
  return image;
}

describe("DrapSurfaceLayerController", () => {
  it("exposes a verified quiet condition while keeping the decoded HAF field zero", () => {
    const quiet = drapFrame("2026-08-06T20:00:00Z", [0, 0, 0, 0]);
    quiet.maximumHafMhz = 0;
    quiet.affectedCellPercent = { "3MHz": 0, "10MHz": 0, "30MHz": 0 };
    const layer = new DrapSurfaceLayerController(drapBundle([quiet]), { widthSegments: 8, heightSegments: 4 });
    const state = layer.setSimulationTime("2026-08-06T20:00:00Z");
    expect(state.legend.condition).toMatchObject({
      status: "none",
      maximumHafMhz: 0,
      zeroFieldPreserved: true,
    });
    expect(state.legend.condition?.summary).toContain("QUIET");
    expect(state.legend.condition?.badge).toBe("QUIET · NOTHING DRAWN");
    expect(texturePixels(layer).data[3]).toBeGreaterThan(0);
    layer.dispose();
  });

  /**
   * The state the layer never had. Peak 3.3 MHz over 4.35% of the globe is the
   * live 2026-08-26T23:58Z frame -- drawn, correct, and so nearly invisible
   * that the owner read it as a broken layer while the card said ACTIVE.
   */
  it("carries a faint frame's own words through to the legend the card is built from", () => {
    const faint = drapFrame("2026-08-06T20:00:00Z", [33, 0, 0, 0]);
    faint.maximumHafMhz = 3.3;
    faint.affectedCellPercent = { "3MHz": 4.35, "10MHz": 0, "30MHz": 0 };
    const layer = new DrapSurfaceLayerController(drapBundle([faint]), { widthSegments: 8, heightSegments: 4 });
    const state = layer.setSimulationTime("2026-08-06T20:00:00Z");
    expect(state.status).toBe("ready");
    expect(state.legend.condition?.status).toBe("faint");
    expect(state.legend.condition?.badge).toBe("QUIET · PEAK 3.3 MHz");
    expect(state.legend.condition?.legendLine).toContain("nothing at 10 or 30 MHz");
    layer.dispose();
  });

  /**
   * THE EXPIRED STATE, which is the same missing state pointing the other way.
   * The slider runs to +72 h; D-RAP publishes no future frames at all, and the
   * layer used to keep drawing its last map there under a live legend.
   */
  it("goes off past the end of the nowcast instead of drawing the last map at +72 h", () => {
    const frame = drapFrame("2026-08-06T20:00:00Z");
    const layer = new DrapSurfaceLayerController(drapBundle([frame]), { widthSegments: 8, heightSegments: 4 });
    // Inside the hold window the newest frame is still drawn, and says its age
    // -- NOAA's own publication lag routinely runs past the 12-minute
    // staleness threshold and hiding the layer for that was the older defect.
    const held = layer.setSimulationTime("2026-08-06T21:00:00Z");
    expect(held.status).toBe("ready");
    // Past it, the layer is off and names the frame the record stops at.
    const expired = layer.setSimulationTime("2026-08-09T20:00:00Z");
    expect(expired.status).toBe("stale");
    if (expired.status !== "stale") throw new Error("unreachable");
    expect(expired.visible).toBe(false);
    expect(expired.reason).toBe("after-coverage");
    expect(expired.lastValidAt).toBe("2026-08-06T20:00:00Z");
    expect(expired.legend.condition).toBeUndefined();
    layer.dispose();
  });

  it("renders an exact eligible frame and exposes its compact legend and source range", () => {
    const frame = drapFrame("2026-08-06T20:00:00Z");
    const layer = new DrapSurfaceLayerController(drapBundle([frame]), { widthSegments: 8, heightSegments: 4 });
    const state = layer.setSimulationTime("2026-08-06T20:05:00Z");

    expect(state.status).toBe("ready");
    expect(state.visible).toBe(true);
    expect(layer.mesh.visible).toBe(true);
    expect(state.legend).toMatchObject({
      title: "D-region HF absorption",
      units: "MHz",
      minimum: 3,
      maximum: 30,
      validAt: frame.validAt,
      sourceRange: { validFrom: frame.validAt, validTo: frame.validAt, frameCount: 1 },
    });
    expect(layer.texture?.userData.temporalInterpolation).toBe(false);
    expect(layer.texture?.flipY).toBe(true);
    expect(layer.texture?.offset.x).toBeCloseTo(0, 8);
    layer.dispose();
  });

  it("mipmaps and anisotropically filters the smooth-mode texture, so the poleward pinch of the equirectangular grid does not alias into stair-stepped blocks", () => {
    // Reproduces the mechanism behind the reported pole pixelation: near the
    // poles an equirectangular grid's longitude columns converge, so a
    // screen pixel there covers many source texels (minification). Without
    // a mip chain the GPU has nothing to average across that collapse. The
    // Earth basemap already carries this exact fix (`buildEarthTexture`,
    // `renderer.capabilities.getMaxAnisotropy()`); this pins the aurora/
    // D-RAP overlays to the same policy via the `maxAnisotropy` option
    // `globe.ts` now threads through from the renderer.
    const layer = new DrapSurfaceLayerController(
      drapBundle([drapFrame("2026-08-06T20:00:00Z")]),
      { widthSegments: 8, heightSegments: 4, maxAnisotropy: 8 },
    );
    layer.setSimulationTime("2026-08-06T20:00:00Z");
    expect(layer.texture?.generateMipmaps).toBe(true);
    expect(layer.texture?.minFilter).toBe(THREE.LinearMipmapLinearFilter);
    expect(layer.texture?.anisotropy).toBe(8);

    // Native mode is meant to expose the raw source cells: no mip chain, no
    // anisotropic averaging, plain nearest sampling — unchanged by this fix.
    layer.setDisplayMode("native");
    expect(layer.texture?.generateMipmaps).toBe(false);
    expect(layer.texture?.minFilter).toBe(THREE.NearestFilter);
    expect(layer.texture?.anisotropy).toBe(1);
    layer.dispose();
  });

  it("defaults smooth-mode anisotropy to 1 when the caller omits maxAnisotropy, rather than leaving it unset", () => {
    const layer = new AuroraSurfaceLayerController(
      auroraBundle([auroraFrame("2026-08-06T20:00:00Z")]),
      { widthSegments: 8, heightSegments: 4 },
    );
    layer.setSimulationTime("2026-08-06T20:05:00Z");
    expect(layer.texture?.generateMipmaps).toBe(true);
    expect(layer.texture?.minFilter).toBe(THREE.LinearMipmapLinearFilter);
    expect(layer.texture?.anisotropy).toBe(1);
    layer.dispose();
  });

  it("switches smooth/native textures, preserves the source null mask, and disposes replacements", () => {
    const layer = new DrapSurfaceLayerController(drapBundle([drapFrame("2026-08-06T20:00:00Z")]), { widthSegments: 8, heightSegments: 4 });
    layer.setSimulationTime("2026-08-06T20:00:00Z");
    const smoothTexture = layer.texture!;
    const dispose = vi.spyOn(smoothTexture, "dispose");

    const state = layer.setDisplayMode("native");
    const pixels = texturePixels(layer);
    expect(state.legend.displayMode).toBe("native");
    expect([pixels.width, pixels.height]).toEqual([2, 2]);
    expect(pixels.data[2 * 4 + 3]).toBe(0);
    expect(dispose).toHaveBeenCalledOnce();
    layer.dispose();
  });

  it("distinguishes an internal no-data gap, which stays hidden, from the live edge of coverage, which draws with its age disclosed", () => {
    const layer = new DrapSurfaceLayerController(drapBundle([
      drapFrame("2026-08-06T20:00:00Z"),
      drapFrame("2026-08-06T21:00:00Z"),
    ]), { widthSegments: 8, heightSegments: 4 });
    layer.setSimulationTime("2026-08-06T20:05:00Z");
    const visibleTexture = layer.texture!;
    const dispose = vi.spyOn(visibleTexture, "dispose");

    // A known newer frame (21:00) exists past this gap: holding the 20:00
    // frame across it would misrepresent the timeline, so it stays hidden.
    const gap = layer.setSimulationTime("2026-08-06T20:30:00Z");
    expect(gap).toMatchObject({ status: "no-data", reason: "gap", visible: false });
    expect(layer.mesh.visible).toBe(false);
    expect(layer.texture).toBeNull();
    expect(dispose).toHaveBeenCalledOnce();

    // Past the newest frame bigmem has ever captured, with nothing newer to
    // silently skip over: this is the live edge, not a gap. NOAA's own D-RAP
    // nowcast does not publish on a strict cadence, so a 30-minute-old
    // newest frame at live-now must draw, not refuse (see
    // DrapSurfaceLayerController.selectState).
    const live = layer.setSimulationTime("2026-08-06T21:30:00Z");
    expect(live).toMatchObject({ status: "ready", validAt: "2026-08-06T21:00:00Z", held: true, ageMinutes: 30, visible: true });
    expect(layer.mesh.visible).toBe(true);
    layer.dispose();
  });
});

describe("AuroraSurfaceLayerController", () => {
  it("renders both native hemispheres at auroral altitude while preserving NOAA's missing mask", () => {
    const layer = new AuroraSurfaceLayerController(
      auroraBundle([auroraFrame("2026-08-06T20:00:00Z")]),
      { widthSegments: 8, heightSegments: 4 },
    );
    layer.setDisplayMode("native");
    const state = layer.setSimulationTime("2026-08-06T20:05:00Z");
    const pixels = texturePixels(layer);

    expect(state).toMatchObject({ status: "ready", observedAt: "2026-08-06T19:30:00Z", held: true });
    expect(state.legend).toMatchObject({
      title: "Aurora viewing probability",
      units: "%",
      minimum: 0,
      maximum: 100,
      sourceRange: { frameCount: 1, coverageComplete: false },
    });
    expect(pixels.data[3]).toBe(0);
    expect(pixels.data[1 * 4 + 3]).toBeGreaterThan(0);
    expect(pixels.data[2 * 4 + 3]).toBeGreaterThan(0);
    expect(pixels.data[3 * 4 + 3]).toBeGreaterThan(0);
    expect(layer.texture?.flipY).toBe(false);
    expect(layer.texture?.offset.x).toBeCloseTo(-179.5 / 360, 8);
    expect(layer.texture?.userData).toMatchObject({
      longitudeStartDegrees: 0,
      longitudeStepDegrees: 1,
      latitudeRowOrder: "south-to-north",
    });
    // CORRECTNESS FIX 2026-09-04: the shell goes through the SHARED ruler now,
    // not the private true-distance formula this used to pin. `100 * (1 + 110 /
    // 6371)` is 101.727, and on the teaching scale — the one the site opens on
    // — that radius reads as 22 km: five scene units BELOW the 60 km floor of
    // the ionospheric column the oval is physically inside. Asserting the
    // arithmetic the code happened to run is exactly the kind of test that
    // cannot see a layer drawn at the wrong height.
    layer.mesh.geometry.computeBoundingSphere();
    expect(layer.mesh.geometry.boundingSphere?.radius)
      .toBeCloseTo(sharedDisplayRadius(1 + 110 / RULER_EARTH_RADIUS_KM, 100), 4);
    layer.dispose();
  });

  it("returns explicit no-data/stale states, respects enablement, and disposes safely", () => {
    const layer = new AuroraSurfaceLayerController(
      auroraBundle([auroraFrame("2026-08-06T20:00:00Z")]),
      { widthSegments: 8, heightSegments: 4 },
    );
    expect(layer.setSimulationTime("2026-08-06T19:00:00Z")).toMatchObject({ status: "no-data", reason: "before-coverage" });
    expect(layer.setSimulationTime("2026-08-06T20:05:00Z").status).toBe("ready");
    expect(layer.setEnabled(false).visible).toBe(false);
    expect(layer.mesh.visible).toBe(false);
    expect(layer.setEnabled(true).visible).toBe(true);

    const texture = layer.texture!;
    const dispose = vi.spyOn(texture, "dispose");
    expect(layer.setSimulationTime("2026-08-06T20:30:00Z")).toMatchObject({ status: "stale", visible: false });
    expect(layer.texture).toBeNull();
    expect(dispose).toHaveBeenCalledOnce();

    layer.dispose();
    layer.dispose();
    expect(() => layer.setSimulationTime("2026-08-06T20:00:00Z")).toThrow(/disposed/);
  });
});

describe("AuroraSurfaceLayerController against a real NOAA grid", () => {
  it("keeps the equatorial seam off the shell in both display modes and records the withdrawal", () => {
    // Drives the same controller the globe instantiates, with the exact NOAA
    // frame that painted a green line across Indonesia on 2026-08-07.
    for (const mode of ["smooth", "native"] as const) {
      const layer = new AuroraSurfaceLayerController(ovationBundle(), { widthSegments: 8, heightSegments: 4 });
      layer.setDisplayMode(mode);
      const state = layer.setSimulationTime(REAL_OVATION_FRAME.validAt);
      expect(state.status).toBe("ready");

      const image = texturePixels(layer);
      const rowsPerDegree = (image.height - 1) / 180;
      let equatorialAlpha = 0;
      let auroralAlpha = 0;
      for (let row = 0; row < image.height; row += 1) {
        const latitude = REAL_OVATION_FRAME.latitudeStartDeg + row / rowsPerDegree;
        for (let column = 0; column < image.width; column += 1) {
          const alpha = image.data[(row * image.width + column) * 4 + 3]!;
          if (Math.abs(latitude) <= 5) equatorialAlpha = Math.max(equatorialAlpha, alpha);
          if (Math.abs(latitude) >= 50) auroralAlpha = Math.max(auroralAlpha, alpha);
        }
      }
      expect(equatorialAlpha).toBe(0);
      expect(auroralAlpha).toBeGreaterThan(0);
      expect(layer.texture?.userData.equatorialSeamWithdrawn).toMatchObject({
        fromLatitudeDeg: -2,
        toLatitudeDeg: 0,
        maximumProbabilityPercent: 4,
      });
      layer.dispose();
    }
  });
});

describe("environmental surface layers face the same way as the globe", () => {
  // Longitudes on an exact vertex of the 96-segment sphere these layers use.
  const longitudes = [-180, -135, -90, -45, 0, 45, 90, 135];

  it("draws D-RAP over the geography it belongs to", () => {
    const layer = new DrapSurfaceLayerController(drapBundle([drapFrame("2026-08-06T20:00:00Z")]));
    layer.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    for (const longitudeDeg of longitudes) {
      const { azimuthDeg, textureCoordinateError } = equirectangularLayerAzimuth(layer.mesh, longitudeDeg);
      expect(textureCoordinateError).toBeLessThan(1e-6);
      expect(Math.abs(azimuthDifferenceDegrees(azimuthDeg, longitudeDeg))).toBeLessThan(1e-6);
    }
    layer.dispose();
  });

  it("draws the aurora history over the geography it belongs to", () => {
    const layer = new AuroraSurfaceLayerController(auroraBundle([auroraFrame("2026-08-06T20:00:00Z")]));
    layer.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    for (const longitudeDeg of longitudes) {
      const { azimuthDeg } = equirectangularLayerAzimuth(layer.mesh, longitudeDeg);
      expect(Math.abs(azimuthDifferenceDegrees(azimuthDeg, longitudeDeg))).toBeLessThan(1e-6);
    }
    layer.dispose();
  });
});
