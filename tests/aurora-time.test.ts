import { describe, expect, it } from "vitest";
import {
  AURORA_DATA_METHOD,
  AURORA_DISPLAY_MODES,
  auroraProbabilityColor,
  auroraRgbaGrid,
  decodeAuroraFrame,
  formatAuroraSelection,
  resampleAuroraFrame,
  selectAuroraFrame,
  type AuroraBundle,
  type AuroraFrame,
} from "../src/aurora-time";
import {
  latitudeRow,
  ovationBundle,
  realOvationProbabilityBytes,
  REAL_OVATION_FRAME,
} from "./ovation-real-frame";

function encodeBytes(values: readonly number[]): string {
  let binary = "";
  for (const value of values) binary += String.fromCharCode(value);
  return btoa(binary);
}

function frame(validAt: string, observedAt: string, probability: readonly number[]): AuroraFrame {
  return {
    observedAt,
    validAt,
    leadMinutes: (Date.parse(validAt) - Date.parse(observedAt)) / 60_000,
    probabilityU8: encodeBytes(probability),
    validityBits: encodeBytes([0b10_1111]),
    validCellCount: 5,
    missingCellCount: 1,
    maximumProbabilityPercent: 100,
    hemispheres: {
      north: { validCellCount: 1, maximumProbabilityPercent: 100 },
      south: { validCellCount: 2, maximumProbabilityPercent: 20 },
    },
  };
}

function bundle(): AuroraBundle {
  const frames = [
    frame("2026-08-06T21:30:00Z", "2026-08-06T20:30:00Z", [0, 20, 40, 60, 80, 100]),
    frame("2026-08-06T21:35:00Z", "2026-08-06T20:02:00Z", [5, 25, 45, 65, 85, 95]),
  ];
  return {
    schemaVersion: "noaa-ovation-history.v1",
    product: "NOAA SWPC OVATION 2020 Aurora Forecast",
    status: "model",
    temporalKind: "observation-driven forecast",
    retrievedAt: "2026-08-06T20:05:00Z",
    source: {
      currentNumericGrid: "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json",
      productPage: "https://www.spaceweather.gov/products/aurora-30-minute-forecast",
      wmoProductPage: "https://www.spaceweather.gov/content/wmo/auroral-activity",
      northImageHistoryManifest: "north",
      southImageHistoryManifest: "south",
      nceiProductInventory: "ncei",
      model: "OVATION 2020",
      inputs: "L1 solar wind and IMF",
      sourceCadenceMinutes: 5,
    },
    sourceAvailability: {
      publicNumericDistribution: "latest grid only",
      publicRenderedImageHistoryHours: 24,
      publicNumericHistoryHours: 0,
      historyMethod: "exact NOAA frames accumulated on bigmem",
      notUsed: "image reconstruction",
      inventoryCheckedAt: "2026-08-06T20:05:00Z",
    },
    grid: {
      longitudeStartDeg: 0,
      longitudeStepDeg: 1,
      longitudeCount: 2,
      // Auroral latitudes on purpose. A synthetic grid pinned to the equator
      // would be withdrawn as NOAA's equatorial seam and would hide every
      // other assertion in this file.
      latitudeStartDeg: -60,
      latitudeStepDeg: 60,
      latitudeCount: 3,
      order: "latitude-major, south-to-north, west-to-east",
      longitudeConvention: "0 <= east longitude < 360",
      sourceCoordinateOrder: "longitude-major, south-to-north within each longitude",
    },
    encoding: {
      probability: "uint8-base64",
      validity: "bitset-lsb-first-base64",
      validRangePercent: [0, 100],
      missingRepresentation: "validity bit 0",
    },
    quantity: { name: "Aurora viewing probability", units: "%", definition: "Probability under dark, clear conditions" },
    time: {
      requestedHistoryHours: 48,
      requestedFrom: "2026-08-04T20:05:00Z",
      requestedTo: frames[1]!.validAt,
      availableFrom: frames[0]!.validAt,
      availableTo: frames[1]!.validAt,
      frameCount: frames.length,
      coverageComplete: false,
      noDataIntervals: [{ from: "2026-08-04T20:05:00Z", to: frames[0]!.validAt, reason: "before-bigmem-accumulation" }],
      selection: "hold source frame",
      staleAfterMinutes: 12,
      forecastLead: "per frame",
      activeForecast: {
        sourceObservedAt: frames[1]!.observedAt,
        forecastValidAt: frames[1]!.validAt,
        feedRetrievedAt: "2026-08-06T20:05:00Z",
        selectionWindowMinutes: 12,
        definition: "latest feed only",
      },
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

describe("OVATION time selection", () => {
  it("selects by forecast-valid time and exposes the actual source lead", () => {
    const selection = selectAuroraFrame(bundle(), "2026-08-06T21:33:00Z");
    expect(selection.available).toBe(true);
    if (!selection.available) throw new Error(selection.message);
    expect(selection.frame.validAt).toBe("2026-08-06T21:30:00Z");
    expect(selection.sourceLeadMinutes).toBe(60);
    expect(selection.ageMinutes).toBe(3);
    expect(selection.selectionBasis).toBe("forecast-valid-time");
    expect(formatAuroraSelection(selection)).toContain("60 min lead");
  });

  it("shows the exact active latest forecast near now before its future valid time", () => {
    const selection = selectAuroraFrame(bundle(), "2026-08-06T20:08:00Z");
    expect(selection.available).toBe(true);
    if (!selection.available) throw new Error(selection.message);
    expect(selection.frame.validAt).toBe("2026-08-06T21:35:00Z");
    expect(selection.selectionBasis).toBe("active-latest-forecast");
    expect(selection.forecastMinutesUntilValid).toBe(87);
    expect(selection.held).toBe(false);
    expect(formatAuroraSelection(selection)).toContain("Active latest forecast");
    expect(formatAuroraSelection(selection)).toContain("input observed 2026-08-06 20:02 UTC");
    expect(formatAuroraSelection(selection)).toContain("forecast valid 2026-08-06 21:35 UTC");
    expect(formatAuroraSelection(selection)).toContain("feed retrieved 2026-08-06 20:05 UTC");
  });

  it("returns explicit states before coverage, inside gaps, and after coverage", () => {
    expect(selectAuroraFrame(bundle(), "2026-08-06T21:00:00Z")).toMatchObject({ available: false, reason: "before-coverage" });
    expect(selectAuroraFrame(bundle(), "2026-08-06T20:25:00Z")).toMatchObject({ available: false, reason: "before-coverage" });

    const source = bundle();
    source.frames[1] = frame("2026-08-06T22:00:00Z", "2026-08-06T21:00:00Z", [5, 25, 45, 65, 85, 95]);
    expect(selectAuroraFrame(source, "2026-08-06T21:45:00Z")).toMatchObject({ available: false, reason: "gap" });
    expect(selectAuroraFrame(bundle(), "2026-08-06T21:48:00Z")).toMatchObject({ available: false, reason: "after-coverage" });
    expect(selectAuroraFrame(bundle(), "not-a-time")).toMatchObject({ available: false, reason: "invalid-time" });
  });
});

describe("OVATION native data and presentation", () => {
  it("does not turn NOAA's isolated 1% equatorial floor into a visible oval", () => {
    expect(auroraProbabilityColor(1)[3]).toBe(0);
    expect(auroraProbabilityColor(2)[3]).toBeGreaterThan(0);
    expect(auroraProbabilityColor(16)[3]).toBeGreaterThan(auroraProbabilityColor(2)[3]);
    expect(auroraProbabilityColor(100)[3]).toBeGreaterThan(auroraProbabilityColor(16)[3]);
  });

  it("decodes zeros, both hemispheres, and the exact missing mask", () => {
    const source = bundle();
    const decoded = decodeAuroraFrame(source, source.frames[0]!);
    expect([...decoded.probabilityPercent]).toEqual([0, 20, 40, 60, 80, 100]);
    expect([...decoded.valid]).toEqual([1, 1, 1, 1, 0, 1]);
    // First and last latitude rows correspond to the synthetic south and north.
    expect(decoded.valid.slice(0, 2)).toEqual(new Uint8Array([1, 1]));
    expect(decoded.valid.slice(4, 6)).toEqual(new Uint8Array([0, 1]));
  });

  it("smooths only in space without new extrema or filling masked source areas", () => {
    const source = bundle();
    const decoded = decodeAuroraFrame(source, source.frames[0]!);
    const smooth = resampleAuroraFrame(source, decoded);
    expect([smooth.width, smooth.height]).toEqual([4, 5]);
    const visible = [...smooth.probabilityPercent].filter((_, index) => smooth.valid[index]);
    expect(Math.min(...visible)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...visible)).toBeLessThanOrEqual(100);
    expect([...smooth.valid]).toContain(0);

    const native = resampleAuroraFrame(source, decoded, "native");
    expect([...native.probabilityPercent]).toEqual([...decoded.probabilityPercent]);
    expect([...native.valid]).toEqual([...decoded.valid]);
    expect(auroraRgbaGrid(source, source.frames[0]!, { mode: "native" }).rgba[4 * 4 + 3]).toBe(0);
  });
});

describe("NOAA's equatorial grid seam", () => {
  const OVAL_ROW_SOUTH = latitudeRow(-56);
  const OVAL_ROW_NORTH = latitudeRow(60);

  function rowValues(values: Uint8Array, latitudeDeg: number): number[] {
    const start = latitudeRow(latitudeDeg) * REAL_OVATION_FRAME.longitudeCount;
    return [...values.slice(start, start + REAL_OVATION_FRAME.longitudeCount)];
  }

  it("still contains the seam in the source bytes this regression is written against", () => {
    // If NOAA ever stops publishing the artifact, or the fixture is replaced,
    // this fails first so the masking below is never a test of nothing.
    const source = realOvationProbabilityBytes();
    expect(Math.max(...rowValues(source, -2))).toBe(1);
    expect(Math.max(...rowValues(source, -1))).toBe(2);
    expect(Math.max(...rowValues(source, 0))).toBe(4);
    // The seam brightens toward the equator, the opposite of a real oval,
    // and is separated from the nearest real probability by 42 degrees.
    for (let latitude = 1; latitude <= 41; latitude += 1) {
      expect(Math.max(...rowValues(source, latitude))).toBe(0);
    }
    for (let latitude = -43; latitude <= -3; latitude += 1) {
      expect(Math.max(...rowValues(source, latitude))).toBe(0);
    }
    expect(Math.max(...rowValues(source, -56))).toBe(23);
  });

  it("withdraws the seam as missing during decoding without rewriting a source byte", () => {
    const source = ovationBundle();
    const decoded = decodeAuroraFrame(source, source.frames[0]!);

    expect(decoded.equatorialSeam).toEqual({
      fromLatitudeDeg: -2,
      toLatitudeDeg: 0,
      latitudeRowCount: 3,
      cellCount: 3 * REAL_OVATION_FRAME.longitudeCount,
      maximumProbabilityPercent: 4,
      isolationDeg: 42,
    });
    for (const latitude of [-2, -1, 0]) {
      expect(rowValues(decoded.valid, latitude).every((flag) => flag === 0)).toBe(true);
    }
    // Missing, not zero: NOAA's bytes are still exactly what NOAA published.
    expect(rowValues(decoded.probabilityPercent, 0)).toEqual(rowValues(realOvationProbabilityBytes(), 0));
    expect(Math.max(...rowValues(decoded.probabilityPercent, 0))).toBe(4);
    // Everything outside the seam keeps its validity, including both ovals.
    expect(rowValues(decoded.valid, -56).every((flag) => flag === 1)).toBe(true);
    expect(rowValues(decoded.valid, 60).every((flag) => flag === 1)).toBe(true);
    expect([...decoded.valid].filter(Boolean).length).toBe(
      REAL_OVATION_FRAME.longitudeCount * REAL_OVATION_FRAME.latitudeCount - 3 * REAL_OVATION_FRAME.longitudeCount,
    );
  });

  it("paints nothing within five degrees of the equator while both real ovals stay visible", () => {
    const source = ovationBundle();
    for (const mode of ["native", "smooth"] as const) {
      const grid = auroraRgbaGrid(source, source.frames[0]!, { mode });
      // Native keeps NOAA's 181 rows; smooth doubles the 180 intervals to 361.
      const rowsPerDegree = (grid.height - 1) / 180;
      let equatorialAlpha = 0;
      let auroralAlpha = 0;
      for (let row = 0; row < grid.height; row += 1) {
        const latitude = REAL_OVATION_FRAME.latitudeStartDeg + row / rowsPerDegree;
        for (let column = 0; column < grid.width; column += 1) {
          const alpha = grid.rgba[(row * grid.width + column) * 4 + 3]!;
          if (Math.abs(latitude) <= 5) equatorialAlpha = Math.max(equatorialAlpha, alpha);
          if (Math.abs(latitude) >= 50) auroralAlpha = Math.max(auroralAlpha, alpha);
        }
      }
      expect(equatorialAlpha).toBe(0);
      expect(auroralAlpha).toBeGreaterThan(0);
      expect(grid.equatorialSeam?.maximumProbabilityPercent).toBe(4);
    }
  });

  it("leaves a genuine equatorward expansion alone because it is continuous with the oval", () => {
    // A storm-time field that reaches the equator from the southern oval is
    // one connected structure, so neither guard can withdraw it.
    const probability = new Uint8Array(
      REAL_OVATION_FRAME.longitudeCount * REAL_OVATION_FRAME.latitudeCount,
    );
    for (let row = 0; row <= latitudeRow(0); row += 1) {
      const value = row >= OVAL_ROW_SOUTH ? 40 : 60;
      probability.fill(value, row * REAL_OVATION_FRAME.longitudeCount, (row + 1) * REAL_OVATION_FRAME.longitudeCount);
    }
    const source = ovationBundle(probability);
    const decoded = decodeAuroraFrame(source, source.frames[0]!);
    expect(decoded.equatorialSeam).toBeNull();
    expect(rowValues(decoded.valid, 0).every((flag) => flag === 1)).toBe(true);
    expect(auroraRgbaGrid(source, source.frames[0]!, { mode: "native" }).rgba[latitudeRow(0) * REAL_OVATION_FRAME.longitudeCount * 4 + 3]).toBeGreaterThan(0);
  });

  it("refuses to withdraw an isolated blob that sits outside the equatorial band", () => {
    // Ten degrees north is far below any auroral latitude, but it is outside
    // what the seam has ever occupied, so it is shown rather than removed.
    const probability = new Uint8Array(
      REAL_OVATION_FRAME.longitudeCount * REAL_OVATION_FRAME.latitudeCount,
    );
    probability.fill(9, latitudeRow(10) * REAL_OVATION_FRAME.longitudeCount, (latitudeRow(10) + 1) * REAL_OVATION_FRAME.longitudeCount);
    probability.fill(9, OVAL_ROW_NORTH * REAL_OVATION_FRAME.longitudeCount, (OVAL_ROW_NORTH + 1) * REAL_OVATION_FRAME.longitudeCount);
    const source = ovationBundle(probability);
    const decoded = decodeAuroraFrame(source, source.frames[0]!);
    expect(decoded.equatorialSeam).toBeNull();
    expect(rowValues(decoded.valid, 10).every((flag) => flag === 1)).toBe(true);
  });

  it("withdraws a seam that touches the equator from the north with the same guards", () => {
    // The seam has only ever appeared on the southern side, so prove the rule
    // is written about geometry rather than about one observed sign.
    const probability = new Uint8Array(
      REAL_OVATION_FRAME.longitudeCount * REAL_OVATION_FRAME.latitudeCount,
    );
    for (const latitude of [0, 1, 2]) {
      probability.fill(3, latitudeRow(latitude) * REAL_OVATION_FRAME.longitudeCount, (latitudeRow(latitude) + 1) * REAL_OVATION_FRAME.longitudeCount);
    }
    probability.fill(9, OVAL_ROW_NORTH * REAL_OVATION_FRAME.longitudeCount, (OVAL_ROW_NORTH + 1) * REAL_OVATION_FRAME.longitudeCount);
    const source = ovationBundle(probability);
    const decoded = decodeAuroraFrame(source, source.frames[0]!);
    expect(decoded.equatorialSeam).toMatchObject({ fromLatitudeDeg: 0, toLatitudeDeg: 2, latitudeRowCount: 3 });
    expect(rowValues(decoded.valid, 1).every((flag) => flag === 0)).toBe(true);
    expect(rowValues(decoded.valid, 60).every((flag) => flag === 1)).toBe(true);
  });
});

describe("OVATION disclosure contract", () => {
  it("labels smooth versus native display and the latest-only numeric boundary", () => {
    expect(AURORA_DISPLAY_MODES.smooth.description).toContain("presentation");
    expect(AURORA_DISPLAY_MODES.native.label).toContain("Native");
    expect(AURORA_DATA_METHOD.history).toContain("latest numeric grid");
    expect(bundle().sourceAvailability.publicNumericHistoryHours).toBe(0);
    expect(bundle().time.coverageComplete).toBe(false);
  });
});
