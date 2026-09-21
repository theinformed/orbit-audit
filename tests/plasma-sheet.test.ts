import { describe, expect, it } from "vitest";
import * as THREE from "three";
import fixture from "./data/geospace-meridional-tail-crop.json";
import {
  MAGNETIC_PRESSURE_NPA_PER_NT_SQUARED,
  PLASMA_SHEET_BETA_LOG_RANGE,
  PLASMA_SHEET_BETA_PIVOT,
  PLASMA_SHEET_BETA_THRESHOLD,
  PLASMA_SHEET_GRADIENT_CSS,
  PLASMA_SHEET_MASK,
  PLASMA_SHEET_MEASUREMENT_WINDOW,
  magneticPressureNPa,
  physicalFromNormalized,
  plasmaBeta,
  plasmaBetaPlaneField,
  plasmaSheetColumns,
  plasmaSheetMetrics,
} from "../src/plasma-sheet";
import type { PlasmaBetaGrid, PlasmaFieldEncoding } from "../src/plasma-sheet";
import { GEOSPACE_SLICE_MASK, prepareAdaptivePlaneField } from "../src/geospace-slice-data";
import type { SmoothedAdaptivePlaneField } from "../src/geospace-slice-data";
import { GeospaceRuntime } from "../src/geospace-runtime";
import type { GeospaceBundle } from "../src/types";

/**
 * The plasma sheet is derived, not published, so the arithmetic that derives it
 * is the whole claim. These tests exist to make that arithmetic checkable
 * against numbers a reader can look up, and to prove the sheet is really there
 * in NOAA's own output rather than only in a synthetic case built to find it.
 *
 * Two halves:
 *
 *  1. the pure physics — the magnetic-pressure constant, beta itself, the
 *     encoding round-trip, the mask propagation, and the column scan against a
 *     Harris sheet whose thickness and centre are known exactly because they
 *     were put there;
 *  2. the same code against a cropped, unmodified slab of the operational
 *     BATS-R-US meridional cut, where the answers are not known in advance and
 *     the test asserts the physics instead: a high-beta sheet exists in the
 *     tail, it is thin, it sits off the equatorial plane, and the lobes above
 *     and below it are magnetically dominated by three orders of magnitude.
 */

const PRESSURE_ENCODING: PlasmaFieldEncoding = { scale: "log10", minimum: -3, maximum: 1.3, units: "nPa" };
const MAGNETIC_ENCODING: PlasmaFieldEncoding = { scale: "log10", minimum: 0, maximum: 3, units: "nT" };

/** Inverse of the artifact's encoding: a physical value back to 0..1. */
function normalize(physical: number, encoding: PlasmaFieldEncoding) {
  const value = encoding.scale === "log10" ? Math.log10(physical) : physical;
  return (value - encoding.minimum) / (encoding.maximum - encoding.minimum);
}

describe("magnetic pressure and plasma beta", () => {
  it("puts B^2 / 2 mu0 in nPa, checkable against the 50 nT textbook value", () => {
    // B^2 / (2 mu0) for B = 50 nT is 2.5e-15 / (2 * 4pi e-7) Pa = 9.947e-10 Pa
    // = 0.9947 nPa. Any unit slip in the constant moves this by 1e+/-9.
    expect(magneticPressureNPa(50)).toBeCloseTo(0.9947, 4);
    expect(MAGNETIC_PRESSURE_NPA_PER_NT_SQUARED).toBeCloseTo(3.9789e-4, 8);
    // Quadratic, and zero field carries zero pressure.
    expect(magneticPressureNPa(100) / magneticPressureNPa(50)).toBeCloseTo(4, 10);
    expect(magneticPressureNPa(0)).toBe(0);
  });

  it("is exactly 1 where the two pressures are equal, and scales with each", () => {
    const magneticFieldNt = 30;
    const balance = magneticPressureNPa(magneticFieldNt);
    expect(plasmaBeta(balance, magneticFieldNt)).toBeCloseTo(1, 12);
    expect(plasmaBeta(2 * balance, magneticFieldNt)).toBeCloseTo(2, 12);
    // Halving the field quadruples beta at fixed thermal pressure.
    expect(plasmaBeta(balance, magneticFieldNt / 2)).toBeCloseTo(4, 12);
  });

  it("refuses rather than returning an infinity where the field vanishes", () => {
    // An infinity would paint the hot end of the ramp over a cell that has no
    // answer. NaN is treated as missing everywhere downstream.
    expect(plasmaBeta(1, 0)).toBeNaN();
    expect(plasmaBeta(1, Number.NaN)).toBeNaN();
    expect(plasmaBeta(Number.NaN, 10)).toBeNaN();
    expect(plasmaBeta(-1, 10)).toBeNaN();
  });

  it("recovers physical values from the artifact's normalized storage", () => {
    expect(physicalFromNormalized(0, PRESSURE_ENCODING)).toBeCloseTo(1e-3, 12);
    expect(physicalFromNormalized(1, PRESSURE_ENCODING)).toBeCloseTo(10 ** 1.3, 10);
    expect(physicalFromNormalized(normalize(0.25, PRESSURE_ENCODING), PRESSURE_ENCODING)).toBeCloseTo(0.25, 10);
    expect(physicalFromNormalized(normalize(120, MAGNETIC_ENCODING), MAGNETIC_ENCODING)).toBeCloseTo(120, 8);
    expect(physicalFromNormalized(0.5, { scale: "linear", minimum: 0, maximum: 1000, units: "km/s" })).toBe(500);
  });
});

describe("the beta ramp is pinned to beta = 1, and its CSS cannot drift from its shader", () => {
  it("places beta = 1 at the pivot rather than at the bar's halfway point", () => {
    const [low, high] = PLASMA_SHEET_BETA_LOG_RANGE;
    expect(PLASMA_SHEET_BETA_PIVOT).toBeCloseTo((0 - low) / (high - low), 12);
    // Not 0.5: if it ever becomes 0.5 the pale band has silently moved a half
    // decade into the lobe and the drawn sheet has silently widened.
    expect(PLASMA_SHEET_BETA_PIVOT).not.toBeCloseTo(0.5, 3);
  });

  it("writes the same pivot into the key card's gradient", () => {
    const stop = /#f2ede0\s+(\d+)%/.exec(PLASMA_SHEET_GRADIENT_CSS);
    expect(stop, "the middle stop must carry an explicit position").not.toBeNull();
    expect(Number(stop![1])).toBe(Math.round(PLASMA_SHEET_BETA_PIVOT * 100));
  });
});

describe("the beta field carries every source caveat forward", () => {
  const encodings = { pressure: PRESSURE_ENCODING, magneticField: MAGNETIC_ENCODING };

  /** Four cells: balanced, plasma-dominated, magnetically dominated, missing. */
  function sample() {
    const balanced = magneticPressureNPa(30);
    return {
      pressure: {
        values: Float32Array.from([
          normalize(balanced, PRESSURE_ENCODING),
          normalize(balanced * 10, PRESSURE_ENCODING),
          normalize(balanced / 100, PRESSURE_ENCODING),
          0,
        ]),
        masks: Uint8Array.from([0, 0, 0, GEOSPACE_SLICE_MASK.missing]),
      },
      magneticField: {
        values: Float32Array.from([
          normalize(30, MAGNETIC_ENCODING),
          normalize(30, MAGNETIC_ENCODING),
          normalize(30, MAGNETIC_ENCODING),
          normalize(30, MAGNETIC_ENCODING),
        ]),
        masks: Uint8Array.from([0, 0, 0, 0]),
      },
    };
  }

  it("puts a balanced cell exactly on the ramp's pivot", () => {
    const { pressure, magneticField } = sample();
    const beta = plasmaBetaPlaneField(pressure, magneticField, encodings)!;
    expect(beta).not.toBeNull();
    expect(beta.log10Beta[0]).toBeCloseTo(0, 6);
    expect(beta.values[0]).toBeCloseTo(PLASMA_SHEET_BETA_PIVOT, 6);
    expect(beta.log10Beta[1]).toBeCloseTo(1, 6);
    expect(beta.log10Beta[2]).toBeCloseTo(-2, 6);
    // Only the beta = 10 cell counts. The exactly-balanced cell round-trips
    // through the artifact's float32 normalization as 0.999999..., so it lands
    // an epsilon BELOW the threshold — which is the honest state of affairs for
    // a cell sitting exactly on a boundary and is why the card reports this
    // count as a population rather than as a boundary position.
    expect(beta.counts.aboveThreshold).toBe(1);
  });

  it("keeps a missing source cell missing instead of dividing through it", () => {
    const { pressure, magneticField } = sample();
    const beta = plasmaBetaPlaneField(pressure, magneticField, encodings)!;
    expect(Number.isNaN(beta.values[3]!)).toBe(true);
    expect(Number.isNaN(beta.log10Beta[3]!)).toBe(true);
    expect(beta.masks[3]! & GEOSPACE_SLICE_MASK.missing).toBeTruthy();
    expect(beta.counts.missing).toBe(1);
    expect(beta.counts.valid).toBe(3);
  });

  it("flags a cell whose beta is only a bound because a source hit its encoding end", () => {
    const { pressure, magneticField } = sample();
    pressure.masks[1] = GEOSPACE_SLICE_MASK.clippedLow;
    magneticField.masks[2] = GEOSPACE_SLICE_MASK.clippedHigh;
    const beta = plasmaBetaPlaneField(pressure, magneticField, encodings)!;
    expect(beta.counts.sourceBounded).toBe(2);
    expect(beta.masks[1]! & PLASMA_SHEET_MASK.sourceBounded).toBeTruthy();
    expect(beta.masks[2]! & PLASMA_SHEET_MASK.sourceBounded).toBeTruthy();
    expect(beta.masks[0]! & PLASMA_SHEET_MASK.sourceBounded).toBe(0);
  });

  it("flags, rather than hides, a beta outside the drawn ramp", () => {
    const { pressure, magneticField } = sample();
    // 10^-3 nPa against a 1000 nT field: log10 beta near -8.6, far below the
    // ramp floor. It is still drawn, at the ramp's cold end, and counted.
    pressure.values[0] = 0;
    magneticField.values[0] = 1;
    const beta = plasmaBetaPlaneField(pressure, magneticField, encodings)!;
    expect(beta.log10Beta[0]!).toBeLessThan(PLASMA_SHEET_BETA_LOG_RANGE[0]);
    expect(beta.values[0]).toBe(0);
    expect(beta.masks[0]! & PLASMA_SHEET_MASK.displayClamped).toBeTruthy();
    expect(beta.counts.displayClamped).toBe(1);
  });

  it("refuses to pair two planes that are not the same plane", () => {
    const { pressure, magneticField } = sample();
    expect(plasmaBetaPlaneField(
      pressure,
      { values: magneticField.values.slice(0, 3), masks: magneticField.masks.slice(0, 3) },
      encodings,
    )).toBeNull();
    expect(plasmaBetaPlaneField(
      { values: new Float32Array(0), masks: new Uint8Array(0) },
      { values: new Float32Array(0), masks: new Uint8Array(0) },
      encodings,
    )).toBeNull();
  });
});

/**
 * A Harris-like current sheet on the display grid: beta peaks on a centre line
 * that can be offset from z = 0, and falls off with a chosen scale height. The
 * half-thickness where beta = 1 is then known in closed form, so the column
 * scan can be checked against arithmetic rather than against itself.
 */
function harrisGrid(options: {
  centreCrossRe: number;
  peakBeta: number;
  scaleHeightRe: number;
  minimumX?: number;
  maximumX?: number;
  maximumCross?: number;
  step?: number;
}): PlasmaBetaGrid {
  const step = options.step ?? 0.5;
  const minimumX = options.minimumX ?? -40;
  const maximumX = options.maximumX ?? -6;
  const maximumCross = options.maximumCross ?? 14;
  const width = Math.round((maximumX - minimumX) / step) + 1;
  const height = Math.round((2 * maximumCross) / step) + 1;
  const log10Beta = new Float32Array(width * height);
  for (let row = 0; row < height; row += 1) {
    const cross = -maximumCross + row * step;
    for (let column = 0; column < width; column += 1) {
      const offset = (cross - options.centreCrossRe) / options.scaleHeightRe;
      log10Beta[row * width + column] = Math.log10(options.peakBeta) - offset * offset;
    }
  }
  return { width, height, boundsRe: [minimumX, maximumX, -maximumCross, maximumCross], log10Beta };
}

describe("measuring the sheet from a grid whose answer is known", () => {
  // log10 beta = log10(peak) - u^2 with u = (z - centre)/h, so beta = 1 where
  // u = sqrt(log10(peak)) and the half-thickness is h * sqrt(log10 peak).
  const peakBeta = 100;
  const scaleHeightRe = 1.5;
  const expectedHalfThickness = scaleHeightRe * Math.sqrt(Math.log10(peakBeta));

  it("recovers the centre and the half-thickness of an offset sheet", () => {
    const grid = harrisGrid({ centreCrossRe: 3, peakBeta, scaleHeightRe });
    const columns = plasmaSheetColumns(grid);
    expect(columns.length).toBeGreaterThan(20);
    for (const column of columns) {
      // The centre is a grid row, so it lands within half a cell of 3.
      expect(Math.abs(column.centreCrossRe - 3)).toBeLessThanOrEqual(0.25);
      expect(column.peakBeta).toBeGreaterThan(50);
      expect(column.halfThicknessRe).not.toBeNull();
      // Linear interpolation of a parabola in log space: close, not exact.
      expect(column.halfThicknessRe!).toBeCloseTo(expectedHalfThickness, 1);
      expect(column.truncated).toBe(false);
      expect(column.lowerEdgeCrossRe!).toBeLessThan(3);
      expect(column.upperEdgeCrossRe!).toBeGreaterThan(3);
    }
  });

  it("only measures inside the stated tail window", () => {
    const grid = harrisGrid({ centreCrossRe: 0, peakBeta, scaleHeightRe, minimumX: -60, maximumX: 20 });
    const columns = plasmaSheetColumns(grid);
    expect(columns.length).toBeGreaterThan(0);
    for (const column of columns) {
      expect(column.xRe).toBeGreaterThanOrEqual(PLASMA_SHEET_MEASUREMENT_WINDOW.minimumXRe);
      expect(column.xRe).toBeLessThanOrEqual(PLASMA_SHEET_MEASUREMENT_WINDOW.maximumXRe);
    }
    // The dayside, where the same high-beta test would pick up the shocked
    // magnetosheath, is never visited.
    expect(columns.some((column) => column.xRe > 0)).toBe(false);
  });

  it("reports no thickness at all where beta never reaches 1", () => {
    const grid = harrisGrid({ centreCrossRe: 0, peakBeta: 0.2, scaleHeightRe });
    const columns = plasmaSheetColumns(grid);
    expect(columns.length).toBeGreaterThan(0);
    for (const column of columns) {
      expect(column.halfThicknessRe).toBeNull();
      expect(column.peakBeta).toBeCloseTo(0.2, 6);
    }
    const metrics = plasmaSheetMetrics(columns);
    expect(metrics.resolvedColumnCount).toBe(0);
    expect(metrics.halfThicknessRe).toBeNull();
    expect(metrics.equatorialCutInsideSheet).toBeNull();
  });

  it("says so when the beta >= 1 run runs off the measured window", () => {
    // A sheet far thicker than the window: every run hits the edge, so every
    // thickness is a lower bound and must be labelled one.
    const grid = harrisGrid({ centreCrossRe: 0, peakBeta: 1e6, scaleHeightRe: 40, maximumCross: 6 });
    const columns = plasmaSheetColumns(grid);
    expect(columns.length).toBeGreaterThan(0);
    expect(columns.every((column) => column.truncated)).toBe(true);
    expect(plasmaSheetMetrics(columns).referenceTruncated).toBe(true);
  });

  it("answers the question the equatorial cut raises, both ways", () => {
    // Centred on z = 0: the equatorial cut goes straight through the sheet.
    const centred = plasmaSheetMetrics(plasmaSheetColumns(harrisGrid({
      centreCrossRe: 0, peakBeta, scaleHeightRe,
    })));
    expect(centred.equatorialCutInsideSheet).toBe(true);
    // Warped 3 Re north of it, as a tilted dipole warps it: the same cut is in
    // the LOBE. This is the trap the layer exists to expose, so it is asserted.
    const warped = plasmaSheetMetrics(plasmaSheetColumns(harrisGrid({
      centreCrossRe: 3, peakBeta, scaleHeightRe,
    })));
    expect(warped.equatorialCutInsideSheet).toBe(false);
    expect(warped.centreCrossRe).toBeGreaterThan(2.5);
    expect(warped.halfThicknessRe!).toBeLessThan(3);
  });

  it("never lets a hole in the grid be walked across", () => {
    const grid = harrisGrid({ centreCrossRe: 0, peakBeta, scaleHeightRe });
    const centreRow = Math.round((0 + 14) / 0.5);
    // Punch out the row just above the centre, everywhere.
    for (let column = 0; column < grid.width; column += 1) {
      grid.log10Beta[(centreRow + 1) * grid.width + column] = Number.NaN;
    }
    for (const column of plasmaSheetColumns(grid)) {
      expect(column.truncated).toBe(true);
      // The run stopped at the hole rather than resuming beyond it.
      expect(column.upperEdgeCrossRe!).toBeLessThanOrEqual(0.5);
    }
  });
});

describe("the same code against an unmodified crop of NOAA's own meridional cut", () => {
  const definition = {
    count: fixture.plane.count,
    coordinatesI16: fixture.plane.coordinatesI16,
    boundsRe: fixture.plane.boundsRe as [number, number, number, number],
  };
  const encodings = {
    pressure: fixture.fieldEncodings.pressure as PlasmaFieldEncoding,
    magneticField: fixture.fieldEncodings.magneticField as PlasmaFieldEncoding,
  };
  const prepare = (field: "pressure" | "magneticField") => prepareAdaptivePlaneField(
    definition,
    fixture.fields[field],
    { mode: "smooth", minimumRadiusRe: 0 },
  ) as SmoothedAdaptivePlaneField;

  const pressure = prepare("pressure");
  const magneticField = prepare("magneticField");
  const beta = plasmaBetaPlaneField(pressure, magneticField, encodings)!;
  const grid: PlasmaBetaGrid = {
    width: pressure.width,
    height: pressure.height,
    boundsRe: pressure.boundsRe,
    log10Beta: beta.log10Beta,
  };
  const columns = plasmaSheetColumns(grid);
  const metrics = plasmaSheetMetrics(columns);

  it("finds a real high-beta sheet in the tail", () => {
    expect(beta).not.toBeNull();
    expect(beta.counts.valid).toBeGreaterThan(1000);
    expect(beta.counts.aboveThreshold).toBeGreaterThan(0);
    expect(metrics.resolvedColumnCount).toBeGreaterThan(10);
    // The published frame's own peak: tens, not a marginal excursion past 1.
    expect(metrics.peakBeta!).toBeGreaterThan(10);
  });

  it("measures it as a thin sheet, not a filled tail", () => {
    expect(metrics.halfThicknessRe).not.toBeNull();
    expect(metrics.halfThicknessRe!).toBeGreaterThan(0.1);
    // Anything approaching the 12 Re window would mean the measurement had
    // escaped into the lobes or the magnetopause and was no longer a sheet.
    expect(metrics.halfThicknessRe!).toBeLessThan(4);
  });

  it("finds the sheet ABOVE the equatorial plane, which is the whole warning", () => {
    // August, northern summer, dipole tilted sunward: NOAA's own solution puts
    // the tail's high-beta sheet a few Re north of z = 0, so the equatorial cut
    // this site also publishes is cutting the LOBE at this distance. Nothing
    // about that is assumed here — it is read off the published numbers.
    expect(metrics.centreCrossRe!).toBeGreaterThan(1);
    expect(metrics.equatorialCutInsideSheet).toBe(false);
    expect(metrics.centreRangeRe![0]).toBeGreaterThan(0);
  });

  it("shows the lobes as magnetically dominated by orders of magnitude", () => {
    // The teaching contrast: the sheet is not merely brighter than its
    // surroundings, it is on the other side of beta = 1 by three decades.
    const [minimumX, , minimumCross, maximumCross] = grid.boundsRe;
    const xStep = (grid.boundsRe[1] - minimumX) / (grid.width - 1);
    const crossStep = (maximumCross - minimumCross) / (grid.height - 1);
    const lobe: number[] = [];
    for (let row = 0; row < grid.height; row += 1) {
      const cross = minimumCross + row * crossStep;
      if (Math.abs(cross) < 8 || Math.abs(cross) > 12) continue;
      for (let column = 0; column < grid.width; column += 1) {
        const x = minimumX + column * xStep;
        if (x > -12 || x < -30) continue;
        const value = grid.log10Beta[row * grid.width + column]!;
        if (Number.isFinite(value)) lobe.push(value);
      }
    }
    expect(lobe.length).toBeGreaterThan(50);
    const median = lobe.sort((a, b) => a - b)[Math.floor(lobe.length / 2)]!;
    expect(median).toBeLessThan(-2);
    expect(Math.log10(metrics.peakBeta!) - median).toBeGreaterThan(3);
  });

  it("counts the cells whose beta is only a bound, because this frame has them", () => {
    // 1,439 of the 6,128 cropped source samples sat on the pressure floor of
    // 10^-3 nPa. The card prints this count; a frame where it silently became
    // zero would mean the flag had stopped being propagated.
    expect(beta.counts.sourceBounded).toBeGreaterThan(0);
    expect(beta.counts.sourceBounded).toBeLessThan(beta.counts.valid);
  });

  it("keeps the threshold at the published convention", () => {
    expect(PLASMA_SHEET_BETA_THRESHOLD).toBe(1);
  });
});

/**
 * The layer inside the runtime that actually draws it.
 *
 * The numbers above are proven on real NOAA output, but this project has
 * shipped green suites over code no entry point reaches and over defaults that
 * were never executed. So this block drives `GeospaceRuntime` itself: the
 * derivation gate, the group it fills, its refusal on an archived frame, and —
 * the one that matters most on this site — that every drawn vertex went
 * through the injected position mapper, which is where the shared radial ruler
 * lives.
 */
function tinyBundle(options: { withPlasmaFields?: boolean } = {}): GeospaceBundle {
  const withPlasmaFields = options.withPlasmaFields ?? true;
  const u16 = (values: number[]) => {
    const bytes = new Uint8Array(values.length * 2);
    values.forEach((value, index) => {
      bytes[index * 2] = value & 255;
      bytes[index * 2 + 1] = value >>> 8;
    });
    return btoa(String.fromCharCode(...bytes));
  };
  const i16 = (values: number[]) => u16(values.map((value) => (value < 0 ? value + 65536 : value)));
  const bytes = (values: number[]) => btoa(String.fromCharCode(...values));
  const allFields = ["density", "speed", "pressure", "magneticField"] as const;
  const plasmaFields = withPlasmaFields ? allFields : (["density", "speed"] as const);
  const planeFrame = (values: number[]) => ({
    fieldsU16: Object.fromEntries(plasmaFields.map((field) => [field, u16(values)])),
    fieldMasksU8: Object.fromEntries(plasmaFields.map((field) => [field, bytes([0, 0, 0, 0])])),
  });
  const frame = (validAt: string, values: number[]) => ({
    validAt,
    runAt: "2026-08-11T00:00:00Z",
    leadMinutes: 0,
    planes: {
      equatorial: planeFrame(values),
      meridional: planeFrame(values),
    },
    radiationBelt: { coordinatesU16: u16([4000, 0]), electronFluxU16: { "100": u16([30000]) } },
  });
  const planeDefinition = {
    count: 4,
    coordinatesI16: i16([-2000, -100, -1000, -100, -2000, 100, -1000, 100]),
    boundsRe: [-20, -10, -1, 1],
  };
  return {
    schema: 1,
    generatedAt: "2026-08-11T00:00:00Z",
    status: "model",
    model: "test SWMF",
    coordinateSystem: "GSM",
    source: { name: "NOAA test", url: "https://example.test", cadence: "20 minutes" },
    planes: { equatorial: planeDefinition, meridional: planeDefinition },
    fieldEncodings: {
      density: { scale: "log10", minimum: -2, maximum: 1.7, units: "amu cm⁻³" },
      speed: { scale: "linear", minimum: 0, maximum: 1000, units: "km s⁻¹" },
      pressure: { scale: "log10", minimum: -3, maximum: 1.3, units: "nPa" },
      magneticField: { scale: "log10", minimum: 0, maximum: 3, units: "nT" },
    },
    fieldMaskEncoding: { storage: "uint8 base64", flags: { missing: 1, clippedLow: 2, clippedHigh: 4 } },
    displayModes: { default: "smooth", smooth: "gap aware", native: "source points" },
    radiationBelt: {
      count: 1,
      energiesKev: [100],
      pitchCoordinate: 0.8,
      pitchCoordinatesSin: [0.8],
      pitchAnglesDegrees: [53.13],
      innerBoundaryRe: 1.0157,
      gridShape: { radialCount: 1, magneticLocalTimeCount: 1 },
      encoding: { scale: "log10", minimum: -2, maximum: 9, quantity: "flux", units: "flux" },
    },
    frames: [
      frame("2026-08-11T00:00:00Z", [20000, 30000, 40000, 50000]),
      frame("2026-08-11T00:20:00Z", [25000, 35000, 45000, 55000]),
    ],
    caveat: "test",
  } as unknown as GeospaceBundle;
}

describe("the runtime only derives beta when the layer asks for it", () => {
  it("draws nothing, and measures nothing, while the layer is off", () => {
    // The default, and the one that must stay cheap: deriving beta is four
    // resamplings of the adaptive grid per frame change (measured at ~230 ms
    // on the published meridional plane), and a reader who never opens this
    // layer must not pay it on every timeline step.
    const runtime = new GeospaceRuntime({ bundle: tinyBundle(), displayMode: "native" });
    runtime.setSimulationTime(new Date("2026-08-11T00:10:00Z"));
    expect(runtime.plasmaSheetEnabled).toBe(false);
    expect(runtime.plasmaSheetGroup.children).toHaveLength(0);
    expect(runtime.getPlasmaSheetLegendMetadata().counts).toBeNull();
    expect(runtime.getPlasmaSheetLegendMetadata().betaPublished).toBe(false);
    runtime.dispose();
  });

  it("fills the group in the same call that switches it on", () => {
    // Not on the next timeline step: the visitor clicked the toggle, and an
    // empty layer until they happen to scrub is indistinguishable from a
    // broken one.
    const runtime = new GeospaceRuntime({ bundle: tinyBundle(), displayMode: "native" });
    runtime.setSimulationTime(new Date("2026-08-11T00:10:00Z"));
    runtime.setPlasmaSheetEnabled(true);
    expect(runtime.plasmaSheetGroup.children.length).toBeGreaterThan(0);
    const metadata = runtime.getPlasmaSheetLegendMetadata();
    expect(metadata.betaPublished).toBe(true);
    expect(metadata.counts!.valid).toBeGreaterThan(0);
    expect(metadata.plane).toBe("meridional");
    runtime.dispose();
  });

  it("puts every drawn vertex through the injected position mapper", () => {
    // This is the shared-ruler guarantee at its only seam. `positionForPlane`
    // is where SpaceGlobe hands the layer the scene's one radial ruler; a
    // vertex that did not come from it would be drawn on a scale of its own.
    const seen: Array<[number, number, string]> = [];
    const runtime = new GeospaceRuntime({
      bundle: tinyBundle(),
      displayMode: "native",
      plasmaSheetEnabled: true,
      positionForPlane: (xRe, crossRe, plane) => {
        seen.push([xRe, crossRe, plane]);
        // A deliberately absurd mapping: nothing could produce these numbers
        // by accident, so matching them proves the route.
        return new THREE.Vector3(xRe * 7, crossRe * 7, 13);
      },
    });
    runtime.setSimulationTime(new Date("2026-08-11T00:10:00Z"));
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every(([, , plane]) => plane === "meridional")).toBe(true);
    const drawn = runtime.plasmaSheetGroup.children.find((child) => child.name.startsWith("plasma-beta-"));
    expect(drawn).toBeDefined();
    const positions = (drawn as THREE.Points).geometry.getAttribute("position");
    for (let index = 0; index < positions.count; index += 1) {
      expect(positions.getZ(index)).toBe(13);
      expect(positions.getX(index) / 7).toBeCloseTo(seen[index]![0], 6);
    }
    runtime.dispose();
  });

  it("refuses on a frame that publishes no pressure or |B| at all", () => {
    // The archived replay frames are exactly this: boundary curves kept, full
    // field dropped. There is nothing to divide, so nothing is drawn and the
    // metadata says so rather than reporting zero cells as a measurement.
    const runtime = new GeospaceRuntime({
      bundle: tinyBundle({ withPlasmaFields: false }),
      displayMode: "native",
      plasmaSheetEnabled: true,
    });
    runtime.setSimulationTime(new Date("2026-08-11T00:10:00Z"));
    expect(runtime.plasmaSheetGroup.children).toHaveLength(0);
    expect(runtime.getPlasmaSheetLegendMetadata().betaPublished).toBe(false);
    expect(runtime.getPlasmaSheetLegendMetadata().counts).toBeNull();
    runtime.dispose();
  });

  it("switches cut plane without disturbing the magnetosphere layer's own", () => {
    const runtime = new GeospaceRuntime({
      bundle: tinyBundle(),
      displayMode: "native",
      plane: "meridional",
      plasmaSheetEnabled: true,
    });
    runtime.setSimulationTime(new Date("2026-08-11T00:10:00Z"));
    runtime.setPlasmaSheetPlane("equatorial");
    expect(runtime.plasmaSheetPlane).toBe("equatorial");
    expect(runtime.plane).toBe("meridional");
    expect(runtime.getPlasmaSheetLegendMetadata().plane).toBe("equatorial");
    expect(runtime.plasmaSheetGroup.children.some((child) => child.name.includes("equatorial"))).toBe(true);
    expect(runtime.plasmaSheetGroup.children.some((child) => child.name.includes("plasma-beta-meridional"))).toBe(false);
    runtime.dispose();
  });

  it("clears itself rather than holding a stale frame outside coverage", () => {
    const runtime = new GeospaceRuntime({
      bundle: tinyBundle(),
      displayMode: "native",
      plasmaSheetEnabled: true,
    });
    runtime.setSimulationTime(new Date("2026-08-11T00:10:00Z"));
    expect(runtime.plasmaSheetGroup.children.length).toBeGreaterThan(0);
    const state = runtime.setSimulationTime(new Date("2020-01-01T00:00:00Z"));
    expect(state.status).toBe("no-data");
    expect(runtime.plasmaSheetGroup.children).toHaveLength(0);
    expect(runtime.getPlasmaSheetLegendMetadata().counts).toBeNull();
    runtime.dispose();
  });
});
