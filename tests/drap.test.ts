import { describe, expect, it } from "vitest";
import {
  DRAP_DATA_METHOD,
  DRAP_DISPLAY_MODES,
  DRAP_LAYER_POLICY,
  decodeDrapValues,
  drapAbsorptionDbAtFrequency,
  DRAP_FAINT_PEAK_MHZ,
  DRAP_LIVE_EDGE_HOLD_MINUTES,
  drapConditionSentence,
  drapConditionSummary,
  drapCondition,
  drapNowcastEndSentence,
  drapHafColor,
  drapRgbaGrid,
  formatDrapFrameTime,
  resampleDrapValues,
  selectDrapFrame,
  type DrapBundle,
  type DrapFrame,
} from "../src/drap";

function encodeU16(values: readonly number[]): string {
  const bytes = new Uint8Array(values.length * 2);
  const view = new DataView(bytes.buffer);
  values.forEach((value, index) => view.setUint16(index * 2, value, true));
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function frame(validAt: string, encoded: readonly number[]): DrapFrame {
  return {
    validAt,
    valuesU16: encodeU16(encoded),
    maximumHafMhz: 30,
    affectedCellPercent: { "3MHz": 50, "10MHz": 25, "30MHz": 10 },
  };
}

function bundle(): DrapBundle {
  const frames = [
    frame("2026-08-06T20:00:00Z", [0, 30, 100, 65535]),
    frame("2026-08-06T20:05:00Z", [0, 50, 200, 300]),
  ];
  return {
    schemaVersion: "noaa-drap.v1",
    product: "NOAA SWPC D-Region Absorption Predictions (D-RAP 2)",
    status: "model",
    temporalKind: "empirical-nowcast",
    retrievedAt: "2026-08-06T20:06:00Z",
    source: {
      currentData: "https://services.swpc.noaa.gov/text/drap_global_frequencies.txt",
      productPage: "https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap",
      documentation: "https://www.spaceweather.gov/content/global-d-region-absorption-prediction-documentation",
      historicalArchive: "https://www.ncei.noaa.gov/products/space-weather/ionospheric-program/d-region-absorption-prediction",
      historicalFilesApi: "https://www.ncei.noaa.gov/cloud-access/space-weather-portal/api/v1/files",
      inputs: "GOES X-ray and proton flux",
      sourceCadence: "X-ray component 1 minute; proton component 5 minutes",
    },
    grid: {
      longitudeStartDeg: -178,
      longitudeStepDeg: 4,
      longitudeCount: 2,
      latitudeStartDeg: 1,
      latitudeStepDeg: -2,
      latitudeCount: 2,
      order: "latitude-major, north-to-south, west-to-east",
    },
    encoding: { type: "uint16-le-base64", scaleMhz: 0.1, missingValue: 65535 },
    quantity: {
      name: "Highest Affected Frequency",
      shortName: "1 dB HAF",
      units: "MHz",
      definition: "Highest frequency expected to lose at least 1 dB on a vertical two-pass path.",
      pathGeometry: "vertical two-pass",
    },
    time: {
      validFrom: frames[0]!.validAt,
      validTo: frames[1]!.validAt,
      frameCount: frames.length,
      selection: "hold latest frame at or before requested UTC; do not interpolate",
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

describe("D-RAP time semantics", () => {
  it("holds the latest past frame without interpolating into the future", () => {
    const source = bundle();
    expect(selectDrapFrame(source, "2026-08-06T20:03:00Z")?.frame.validAt).toBe("2026-08-06T20:00:00Z");
    expect(selectDrapFrame(source, "2026-08-06T20:03:00Z")?.ageMinutes).toBe(3);
    expect(selectDrapFrame(source, "2026-08-06T19:59:59Z")).toBeNull();
  });

  it("marks a held nowcast stale instead of implying forecast coverage", () => {
    const selection = selectDrapFrame(bundle(), "2026-08-06T20:18:00Z");
    expect(selection?.stale).toBe(true);
    expect(formatDrapFrameTime(selection)).toContain("stale (13 min old)");
  });
});

describe("D-RAP field encoding", () => {
  it("decodes NOAA tenths of MHz and preserves missing cells", () => {
    const source = bundle();
    const values = decodeDrapValues(source, source.frames[0]!);
    expect([...values.slice(0, 3)]).toEqual([0, 3, 10]);
    expect(Number.isNaN(values[3])).toBe(true);
  });

  it("keeps sub-HF and missing cells transparent in the operational texture", () => {
    expect(drapHafColor(2.9)[3]).toBe(0);
    expect(drapHafColor(Number.NaN)[3]).toBe(0);
    expect(drapHafColor(10)[3]).toBeGreaterThan(0);
    const source = bundle();
    const texture = drapRgbaGrid(source, source.frames[0]!, { mode: "native" });
    expect([texture.width, texture.height]).toEqual([2, 2]);
    expect(texture.rgba[3]).toBe(0);
    expect(texture.rgba[7]).toBeGreaterThan(0);
    expect(texture.rgba[15]).toBe(0);
  });

  it("defaults to smooth linear display without new extrema or filled missing cells", () => {
    const source = bundle();
    const decoded = decodeDrapValues(source, source.frames[0]!);
    const smooth = resampleDrapValues(source, decoded);
    expect([smooth.width, smooth.height]).toEqual([8, 4]);
    const finite = [...smooth.values].filter(Number.isFinite);
    expect(Math.min(...finite)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...finite)).toBeLessThanOrEqual(10);
    expect([...smooth.values].some(Number.isNaN)).toBe(true);
    expect(drapRgbaGrid(source, source.frames[0]!).width).toBe(8);
  });

  it("uses NOAA's documented frequency scaling for the same vertical path", () => {
    expect(drapAbsorptionDbAtFrequency(10, 10)).toBeCloseTo(1);
    expect(drapAbsorptionDbAtFrequency(10, 5)).toBeCloseTo(Math.pow(2, 1.5));
    expect(drapAbsorptionDbAtFrequency(10, 0)).toBeNull();
  });
});

describe("D-RAP operational UX contract", () => {
  it("stays off by default and does not claim assumption-driven content", () => {
    expect(DRAP_LAYER_POLICY).toEqual({
      defaultVisible: false,
      menu: "advanced-layers",
      singleCompactLegend: true,
      assumptionDriven: false,
    });
    expect(DRAP_DISPLAY_MODES.smooth.label).toBe("Smooth");
    expect(DRAP_DISPLAY_MODES.native.label).toBe("Native grid");
    expect(DRAP_DATA_METHOD.status).toBe("model");
    expect(DRAP_DATA_METHOD.limitation).toContain("not an absorption measurement");
  });

  it("explains a visually blank quiet field instead of looking broken", () => {
    const quiet = frame("2026-08-06T20:00:00Z", [0, 0, 0, 0]);
    quiet.maximumHafMhz = 0;
    quiet.affectedCellPercent = { "3MHz": 0, "10MHz": 0, "30MHz": 0 };
    expect(drapConditionSummary(quiet)).toContain("below the 3 MHz bottom of the HF band");
    expect(drapCondition(quiet)).toMatchObject({ status: "none", maximumHafMhz: 0, zeroFieldPreserved: true });
    const decoded = decodeDrapValues(bundle(), quiet);
    expect([...decoded]).toEqual([0, 0, 0, 0]);
    const rendered = drapRgbaGrid(bundle(), quiet, { mode: "native" });
    expect(rendered.condition.status).toBe("none");
    expect(rendered.rgba[3]).toBeGreaterThan(0);
    expect(drapConditionSummary(bundle().frames[0]!)).toContain("ACTIVE");
  });

  /**
   * THE DEFECT SEAN READ, as a test. Peak 3.3 MHz over 4.35% of the globe and
   * nothing at all at 10 or 30 MHz is the live 2026-08-26T23:58Z frame: the
   * layer drew it correctly and almost invisibly, then badged it ACTIVE and
   * said nothing whatever about why the globe was bare.
   */
  it("calls a field that is drawn but barely visible quiet, and says so in all three places", () => {
    const faint = frame("2026-08-26T23:58:00Z", [0, 0, 0, 0]);
    faint.maximumHafMhz = 3.3;
    faint.affectedCellPercent = { "3MHz": 4.35, "10MHz": 0, "30MHz": 0 };
    const condition = drapCondition(faint);
    expect(condition.status).toBe("faint");
    // The badge is the only thing a folded card shows, so it carries the number.
    expect(condition.badge).toBe("QUIET · PEAK 3.3 MHz");
    expect(condition.legendLine).toContain("4.3% of the globe");
    expect(condition.legendLine).toContain("nothing at 10 or 30 MHz");
    expect(condition.summary).toContain("3.3 MHz");
    expect(condition.summary).toContain("quiet D region");
    // Nothing was invented to make it look busier: the published numbers are
    // carried through untouched and the field is still exactly what NOAA sent.
    expect(condition.maximumHafMhz).toBe(3.3);
    expect(condition.affectedCellPercent).toEqual({ "3MHz": 4.35, "10MHz": 0, "30MHz": 0 });
    expect(condition.zeroFieldPreserved).toBe(true);
    // ...and the neutral quiet wash still belongs to the all-zero state alone.
    // A faint field has a real 4% signal in it and a wash over the other 96%
    // would bury the one thing there is to see.
    expect(drapRgbaGrid(bundle(), faint, { mode: "native" }).condition.status).toBe("faint");
  });

  it("puts the boundary between faint and active where the legend's own tick is", () => {
    const at = (peak: number, area: number): DrapFrame => {
      const f = frame("2026-08-06T20:00:00Z", [0, 0, 0, 0]);
      f.maximumHafMhz = peak;
      f.affectedCellPercent = { "3MHz": area, "10MHz": 0, "30MHz": 0 };
      return f;
    };
    expect(drapCondition(at(2.9, 0)).status).toBe("none");
    expect(drapCondition(at(3.0, 0.1)).status).toBe("faint");
    expect(drapCondition(at(DRAP_FAINT_PEAK_MHZ - 0.1, 18)).status).toBe("faint");
    expect(drapCondition(at(DRAP_FAINT_PEAK_MHZ, 18)).status).toBe("active");
    // Wide but shallow is not quiet either: the area guard, which no frame in
    // the live artifact needs and which is kept because that is the evidence.
    expect(drapCondition(at(4.0, 40)).status).toBe("active");
    // A frame whose percentages cannot be read falls back to the peak alone,
    // and falls the safe way: a busy map is never badged QUIET · NOTHING DRAWN.
    const unreadable = at(31.5, Number.NaN);
    expect(drapCondition(unreadable).status).toBe("active");
    // ...and it does not then claim the share it could not read is zero.
    expect(drapCondition(unreadable).legendLine).toContain("an unreported share of the globe");
    expect(drapCondition(unreadable).legendLine).not.toContain("none of the globe");
    const unreadableQuiet = at(2.4, Number.NaN);
    expect(drapCondition(unreadableQuiet).status).toBe("none");
  });

  it("quotes NOAA's own status lines, and only over the frame they describe", () => {
    const b = bundle();
    b.messages = {
      estimatedRecovery: "No Estimate",
      xray: "Normal X-ray Background",
      xrayWarning: null,
      proton: "Normal Proton Background",
      protonWarning: null,
    };
    const newest = b.frames.at(-1)!;
    newest.maximumHafMhz = 3.3;
    newest.affectedCellPercent = { "3MHz": 4.35, "10MHz": 0, "30MHz": 0 };
    const said = drapConditionSentence(b, newest);
    expect(said).toContain("“Normal X-ray Background” and “Normal Proton Background”");
    expect(said).toContain("The layer is working; the ionosphere is quiet.");
    // The messages are parsed from the CURRENT D-RAP text only, so attaching
    // them to an older frame would be dating today's feed status to Tuesday.
    const older = b.frames[0]!;
    expect(drapConditionSentence(b, older)).toBe(drapCondition(older).summary);
    expect(drapConditionSentence(b, older)).not.toContain("Normal X-ray Background");
  });

  it("holds the newest frame across NOAA's routine lag, and only that far", () => {
    // The two ends of one rule, stated as one test so neither can be tuned
    // without seeing the other. 90 minutes is past the D region's own recovery
    // time and clear of the 30-60 min upstream publication lag the live-edge
    // fix in `DrapSurfaceLayerController.selectState` exists to accommodate.
    expect(DRAP_LIVE_EDGE_HOLD_MINUTES).toBeGreaterThan(60);
    const b = bundle();
    const newest = b.frames.at(-1)!;
    const newestMs = Date.parse(newest.validAt);
    const inside = selectDrapFrame(b, new Date(newestMs + (DRAP_LIVE_EDGE_HOLD_MINUTES - 1) * 60_000))!;
    expect(inside.ageMinutes).toBeLessThan(DRAP_LIVE_EDGE_HOLD_MINUTES);
    const outside = selectDrapFrame(b, new Date(newestMs + (DRAP_LIVE_EDGE_HOLD_MINUTES + 1) * 60_000))!;
    expect(outside.ageMinutes).toBeGreaterThan(DRAP_LIVE_EDGE_HOLD_MINUTES);
    // `selectDrapFrame` itself still reaches backward and reports the age
    // rather than refusing -- the refusal belongs to the callers, so a caller
    // that wants the raw archive frame can still have it.
    expect(outside.frame.validAt).toBe(newest.validAt);
  });

  it("says the nowcast has run out rather than claiming a future it does not have", () => {
    const said = drapNowcastEndSentence("2026-08-26 23:58 UTC");
    expect(said).toContain("2026-08-26 23:58 UTC");
    expect(said).toContain("no future frames");
    expect(said).toContain("Scrub back");
  });
});
