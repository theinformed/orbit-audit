import { describe, expect, it } from "vitest";
import * as forecastModule from "../src/magnetopause-forecast";
import {
  forecastKpAt,
  magnetopauseNoForecastAt,
  measuredDriverRecord,
  noForecastSentence,
} from "../src/magnetopause-forecast";
import type { ForecastDriverSample, KpForecastRow } from "../src/magnetopause-forecast";
import { shueBoundary } from "../src/magnetopause";
import { keyCardBar, magnetosphereFieldLegendSpec } from "../src/main";

const START = Date.parse("2026-08-18T00:00:00Z");
const HOUR = 3_600_000;

/** 48 hours at 5 minutes, with a stated Bz and pressure envelope. */
function series(): ForecastDriverSample[] {
  const rows: ForecastDriverSample[] = [];
  for (let index = 0; index < 576; index += 1) {
    const at = START + index * 5 * 60_000;
    const phase = index / 576;
    rows.push({
      validAt: new Date(at).toISOString(),
      bzGsmNt: index === 100 ? -10 : index === 200 ? 12 : Math.sin(phase * 6) * 4,
      dynamicPressureNpa: index === 300 ? 9 : index === 400 ? 1.5 : 3.5,
    });
  }
  // Deliberately OUT OF ORDER, and deliberately the newest row: the end of the
  // record has to be found by TIME rather than by array position, and an
  // already-sorted fixture cannot tell the difference.
  rows.push({
    validAt: new Date(START + 576 * 5 * 60_000).toISOString(),
    bzGsmNt: -1,
    dynamicPressureNpa: 4.25,
  });
  rows.splice(5, 0, rows.pop()!);
  return rows;
}

const kpRows: KpForecastRow[] = [
  { time: "2026-08-19T21:00:00Z", kp: 3, status: "observed" },
  { time: "2026-08-20T00:00:00Z", kp: 3.67, status: "estimated" },
  { time: "2026-08-21T00:00:00Z", kp: 4, status: "predicted" },
];

const lastMs = START + 576 * 5 * 60_000;

describe("past the last measurement there is NO forecast magnetosphere, and none is drawn", () => {
  /**
   * THE NEGATIVE CONTROL FOR THE WHOLE CHANGE.
   *
   * The band was built twice (`a0bf46f`, then re-inked in `a810bef`) before
   * Sean ruled it out: *"If we can't get a forecasted magnetosphere, just
   * leave it off."* The way it comes back is somebody re-exporting a geometry
   * builder from here and finding a caller for it, so the absence is asserted
   * rather than assumed. This test fails the moment this module can draw.
   */
  it("exports nothing that can draw a boundary", () => {
    const exported = Object.keys(forecastModule).sort();
    expect(exported).toEqual([
      "forecastKpAt",
      "magnetopauseNoForecastAt",
      "measuredDriverRecord",
      "noForecastSentence",
    ]);
    for (const name of exported) {
      expect(name.toLowerCase()).not.toContain("geometry");
      expect(name.toLowerCase()).not.toContain("band");
    }
  });

  it("reports what was MEASURED, over the window it was measured in", () => {
    const record = measuredDriverRecord(series())!;
    expect(record.minimumBzNt).toBe(-10);
    expect(record.maximumBzNt).toBe(12);
    expect(record.minimumDynamicPressureNpa).toBe(1.5);
    expect(record.maximumDynamicPressureNpa).toBe(9);
    expect(record.sampleCount).toBe(577);
    expect(record.toIso).toBe(new Date(lastMs).toISOString());
  });

  it("refuses to say anything at all without a measured record", () => {
    expect(measuredDriverRecord([])).toBeNull();
    // Bz but no pressure is not enough: both corners need Shue's two numbers.
    expect(measuredDriverRecord([
      { validAt: "2026-08-18T00:00:00Z", bzGsmNt: -4, dynamicPressureNpa: null },
    ])).toBeNull();
    // And with no record the layer's ORDINARY "drivers are missing" state is
    // the true one. Claiming "no forecast" about a feed outage would name the
    // wrong failure.
    expect(magnetopauseNoForecastAt([], kpRows, lastMs + 6 * HOUR)).toBeNull();
  });

  it("stays out of the way on the measured side of the clock", () => {
    expect(magnetopauseNoForecastAt(series(), kpRows, lastMs - HOUR)).toBeNull();
    expect(magnetopauseNoForecastAt(series(), kpRows, lastMs)).toBeNull();
    expect(magnetopauseNoForecastAt(series(), kpRows, lastMs + 60_000)).not.toBeNull();
  });

  it("carries how far the nose actually MOVED while it was watched, as a fact about the past", () => {
    const state = magnetopauseNoForecastAt(series(), kpRows, lastMs + 24 * HOUR)!;
    const record = measuredDriverRecord(series())!;
    // The two corners of the RECORD: southward Bz with high pressure is the
    // most compressed, northward with low pressure the most relaxed.
    expect(state.measuredNoseRangeRe![0]).toBeCloseTo(
      shueBoundary(record.maximumDynamicPressureNpa, record.minimumBzNt)!.subsolarStandoffRe, 10);
    expect(state.measuredNoseRangeRe![1]).toBeCloseTo(
      shueBoundary(record.minimumDynamicPressureNpa, record.maximumBzNt)!.subsolarStandoffRe, 10);
    expect(state.measuredNoseRangeRe![0]).toBeLessThan(state.measuredNoseRangeRe![1]);
    expect(state.hoursPastMeasurement).toBeCloseTo(24, 6);
  });

  it("carries NOAA's forecast Kp as ACTIVITY, and it moves nothing", () => {
    const near = magnetopauseNoForecastAt(series(), kpRows, lastMs + HOUR)!;
    const far = magnetopauseNoForecastAt(series(), kpRows, Date.parse("2026-08-21T02:00:00Z"))!;
    expect(far.forecastKp).toBe(4);
    expect(far.forecastKpIsPredicted).toBe(true);
    // Kp is the response, not a driver, and there is no honest Kp-to-Bz
    // conversion for this site to make. It must not touch a single number the
    // card reports about the boundary.
    expect(far.measuredNoseRangeRe).toEqual(near.measuredNoseRangeRe);

    // Past the published three-day rows there is no forecast Kp, and that is
    // reported as absent rather than held over.
    expect(magnetopauseNoForecastAt(series(), kpRows, Date.parse("2026-08-25T00:00:00Z"))!.forecastKp).toBeNull();
    expect(forecastKpAt(kpRows, Date.parse("2026-08-19T20:00:00Z"))).toBeNull();
  });

  it("says the ruling in words a reader can check", () => {
    const state = magnetopauseNoForecastAt(series(), kpRows, lastMs + 12 * HOUR)!;
    const sentence = noForecastSentence(state);
    expect(sentence).toContain("There is no forecast of the magnetosphere, so nothing is drawn.");
    expect(sentence).toContain("L1");
    expect(sentence).toContain("Arrival time is forecastable days ahead; severity is not.");
    // Kp named as the response rather than the driver, and ENLIL's missing Bz
    // named as the reason a real wind forecast still does not help.
    expect(sentence).toContain("planetary K index");
    expect(sentence).toContain("WSA-ENLIL");
    expect(sentence).toContain("no internal magnetic field");
    // And the measured movement, so the size of the missing thing is on screen.
    expect(sentence).toContain(state.measuredNoseRangeRe![0].toFixed(1));
    expect(sentence).toContain(state.measuredNoseRangeRe![1].toFixed(1));
  });
});

describe("the card and the legend a reader sees past the last measurement", () => {
  const state = magnetopauseNoForecastAt(series(), kpRows, lastMs + 11 * HOUR)!;
  const spec = magnetosphereFieldLegendSpec({
    noForecast: state,
    field: "magneticField",
    fieldMetadata: null,
    structures: null,
    runtimeState: null,
    loading: false,
    empiricalAnnotationOn: false,
    shueNoseRe: null,
    frameDescription: null,
    mhdCutOn: false,
    fieldLineSummary: null,
    formatEndpoint: (value) => value.toFixed(1),
  });

  it("names itself as not forecast, and never as a forecast", () => {
    expect(spec.title).toBe("Magnetosphere — not forecast");
    expect(spec.keyTitle).toBe("Magnetosphere · no forecast");
    expect(spec.badge).toBe("NO FORECAST · LAYER OFF");
    // The chip that used to read FORECAST · A BAND, NOT A BOUNDARY is gone,
    // and so is the legend title "Magnetopause · where it could be" that sat
    // over the drawn wedge.
    expect(spec.badge).not.toBe("FORECAST · A BAND, NOT A BOUNDARY");
    expect(spec.evidence).not.toBe("forecast");
    expect(JSON.stringify(spec)).not.toContain("where it could be");
    expect(JSON.stringify(spec)).not.toContain("A BAND");
  });

  it("is a NO-DATA card with its own reason and a way back into coverage", () => {
    expect(spec.statusState).toBe("no-data");
    expect(spec.unavailable?.headline).toContain("not forecast");
    expect(spec.unavailable?.because).toContain("L1");
    expect(spec.unavailable?.because).toContain("will not fill in");
    // The jump lands INSIDE the measured record, never on its edge and never
    // forward: there is nothing published in the future to land on.
    const landing = Date.parse(spec.unavailable!.jumpToIso!);
    expect(landing).toBeGreaterThanOrEqual(Date.parse(state.measured.fromIso));
    expect(landing).toBeLessThanOrEqual(Date.parse(state.measured.toIso));
    expect(spec.unavailable?.jumpLabel).toMatch(/^Go back to /);
  });

  it("makes the LEGEND itself say there is no forecast", () => {
    // Sean asked for exactly this: "have it turn off and let the legend say as
    // much - no forecast". The shared phrase is "NO DATA AT THIS TIME", which
    // reads as a late frame; this layer is off permanently and says so.
    expect(spec.emptyLabel).toBe("NO FORECAST · NOTHING DRAWN");
    expect(keyCardBar(spec, true)).toEqual({
      kind: "no-data",
      endpoints: ["—", "NO FORECAST · NOTHING DRAWN", "—"],
    });
    // Any other layer keeps the shared phrase.
    expect(keyCardBar({ scale: undefined }, true).endpoints[1]).toBe("NO DATA AT THIS TIME");
  });

  it("keeps a real colour ramp so the card can never degenerate to SHAPE ONLY", () => {
    expect(spec.scale).toBeTruthy();
    expect(keyCardBar(spec, false).kind).toBe("ramp");
  });

  it("gives way to the ordinary missing-driver state when there is no record at all", () => {
    const withoutRecord = magnetosphereFieldLegendSpec({
      noForecast: null,
      field: "magneticField",
      fieldMetadata: null,
      structures: null,
      runtimeState: null,
      loading: false,
      empiricalAnnotationOn: false,
      shueNoseRe: null,
      frameDescription: null,
      mhdCutOn: false,
      fieldLineSummary: null,
      formatEndpoint: (value) => value.toFixed(1),
    });
    // A gap in the feed is a different fact from the end of the record.
    expect(withoutRecord.badge).toBe("AWAITING LIVE DRIVERS");
    expect(withoutRecord.emptyLabel).toBeUndefined();
    expect(withoutRecord.statusState).toBe("no-data");
  });
});
