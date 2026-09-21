import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import stylesheet from "../src/styles.css?raw";
import { describe, expect, it } from "vitest";

import {
  KP_LIMITATION,
  kpChartGeometry,
  kpChartSummary,
  kpStormLabel,
  kpStormLevel,
  type KpRow,
} from "../src/kp-forecast";
import { currentConditionsView } from "../src/content";

const at = (hour: number) => new Date(Date.UTC(2026, 7, 10, hour)).toISOString();
const series: KpRow[] = [
  { time: at(0), kp: 0, status: "observed" },
  { time: at(3), kp: 1.67, status: "observed" },
  { time: at(6), kp: 4.33, status: "observed" },
  { time: at(9), kp: 5.33, status: "observed" },
  { time: at(12), kp: 7.67, status: "estimated" },
  { time: at(15), kp: 3.0, status: "predicted" },
  { time: at(18), kp: 2.33, status: "predicted" },
];

describe("the G scale, which is what a Kp number means operationally", () => {
  it("starts at Kp 5 and tops out at G5", () => {
    expect(kpStormLevel(4.99)).toBe(0);
    expect(kpStormLevel(5)).toBe(1);
    expect(kpStormLevel(6)).toBe(2);
    expect(kpStormLevel(7)).toBe(3);
    expect(kpStormLevel(8)).toBe(4);
    expect(kpStormLevel(9)).toBe(5);
  });

  /** Below G1 there is no storm, and saying "G0" would invent a category. */
  it("gives no storm label below the threshold", () => {
    expect(kpStormLabel(4.67)).toBeNull();
    expect(kpStormLabel(5)).toBe("G1 Minor");
    expect(kpStormLabel(9)).toBe("G5 Extreme");
    expect(kpStormLabel(null)).toBeNull();
  });
});

describe("drawing the series", () => {
  it("draws one bar per published row and keeps them in order", () => {
    const { bars } = kpChartGeometry(series);
    expect(bars).toHaveLength(series.length);
    for (let i = 1; i < bars.length; i += 1) expect(bars[i]!.x).toBeGreaterThan(bars[i - 1]!.x);
  });

  /**
   * The axis is always the full 0–9 range. Rescaling to the observed maximum
   * would draw a quiet week exactly like a severe storm — same bar heights,
   * different meaning — which is the most misleading thing this chart could do.
   */
  it("keeps the axis at the full 0-9 range regardless of what happened", () => {
    const quiet = kpChartGeometry(series.map((row) => ({ ...row, kp: 1 })));
    const stormy = kpChartGeometry(series.map((row) => ({ ...row, kp: 8 })));
    expect(quiet.bars[0]!.height).toBeLessThan(stormy.bars[0]!.height / 3);
  });

  /**
   * Kp 0 is a real, common, meaningful reading — a very quiet field — and it
   * must not look like a missing bar. The renderer floors the drawn height at
   * one unit; the geometry reports the true zero so the two stay honest.
   */
  it("reports a true zero for Kp 0 rather than dropping the row", () => {
    const { bars, skipped } = kpChartGeometry(series);
    expect(bars[0]!.kp).toBe(0);
    expect(bars[0]!.height).toBe(0);
    expect(skipped).toBe(0);
  });

  /** A gap is a gap: the row keeps its slot so later bars do not shift left. */
  it("counts an unpublished row as skipped and holds its place", () => {
    const gapped = [...series];
    gapped[2] = { ...gapped[2]!, kp: null };
    const { bars, skipped } = kpChartGeometry(gapped);
    expect(skipped).toBe(1);
    expect(bars).toHaveLength(series.length - 1);
    // The bar after the gap sits where it always sat, not one slot earlier.
    const full = kpChartGeometry(series);
    expect(bars[2]!.x).toBeCloseTo(full.bars[3]!.x, 6);
  });

  /**
   * The single most important line on this chart. Observed, estimated and
   * predicted are three different claims and the drawn bar says which; the
   * boundary marks where measurement stops.
   */
  it("marks where measurement stops and forecast begins", () => {
    const { bars, forecastBoundaryX } = kpChartGeometry(series);
    expect(forecastBoundaryX).not.toBeNull();
    const firstPredicted = bars.find((bar) => bar.status === "predicted")!;
    expect(forecastBoundaryX!).toBeLessThanOrEqual(firstPredicted.x);
    expect(new Set(bars.map((bar) => bar.status))).toEqual(new Set(["observed", "estimated", "predicted"]));
  });

  it("carries the storm level on each bar so a G-level bar can be drawn as one", () => {
    const { bars } = kpChartGeometry(series);
    expect(bars.find((bar) => bar.kp === 4.33)!.level).toBe(0);
    expect(bars.find((bar) => bar.kp === 5.33)!.level).toBe(1);
    expect(bars.find((bar) => bar.kp === 7.67)!.level).toBe(3);
  });

  /**
   * The value axis used to be labelled ONLY at the G thresholds, and G1 begins
   * at Kp 5 — the top 45% of a 0–9 box. On a quiet week every drawn bar sat in
   * the unlabelled 55% underneath, so the chart carried a scale exactly where
   * it had no data. Kp 0 and Kp 3 are now reference rows for that half.
   */
  it("labels the half of the axis the bars actually live in", () => {
    const { valueTicks } = kpChartGeometry(series);
    expect(valueTicks.map((tick) => tick.kp)).toEqual([0, 3, 5, 6, 7, 8, 9]);
    // Higher Kp is higher on the chart, so its y is smaller.
    for (let i = 1; i < valueTicks.length; i += 1) {
      expect(valueTicks[i]!.y).toBeLessThan(valueTicks[i - 1]!.y);
    }
    // Kp on the left, the G band it opens on the right; the reference rows
    // below the storm threshold name no band, because there is not one.
    expect(valueTicks.filter((tick) => tick.gLabel !== null).map((tick) => tick.gLabel))
      .toEqual(["G1", "G2", "G3", "G4", "G5"]);
    expect(valueTicks.find((tick) => tick.kp === 3)!.gLabel).toBeNull();
    expect(valueTicks.find((tick) => tick.kp === 0)!.level).toBe(0);
  });

  /**
   * The chart was captioned "seven days behind, three ahead" and carried not
   * one date: `dayTicks` was computed here and thrown away by the renderer.
   */
  it("puts a dated tick on every UTC midnight", () => {
    const days: KpRow[] = [];
    for (let hour = 0; hour < 24 * 4; hour += 3) {
      days.push({ time: new Date(Date.UTC(2026, 7, 10, hour)).toISOString(), kp: 2, status: "observed" });
    }
    const { dayTicks } = kpChartGeometry(days, null, 900, 270);
    expect(dayTicks.map((tick) => tick.iso.slice(0, 10)))
      .toEqual(["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"]);
    // The month is named once, then the day of month carries it.
    expect(dayTicks.map((tick) => tick.label)).toEqual(["10 Aug", "11", "12", "13"]);
    for (const tick of dayTicks) expect(tick.labelled).toBe(true);
  });

  /**
   * A tick too close to the last labelled one keeps its rule and loses its
   * text; overlapping dates are worse than fewer dates.
   */
  it("drops a date label rather than overprinting the one before it", () => {
    const days: KpRow[] = [];
    for (let hour = 0; hour < 24 * 10; hour += 3) {
      days.push({ time: new Date(Date.UTC(2026, 7, 10, hour)).toISOString(), kp: 2, status: "observed" });
    }
    const wide = kpChartGeometry(days, null, 1000, 300);
    const narrow = kpChartGeometry(days, null, 320, 190);
    expect(wide.dayTicks).toHaveLength(narrow.dayTicks.length);
    expect(narrow.dayTicks.filter((tick) => tick.labelled).length)
      .toBeLessThan(wide.dayTicks.filter((tick) => tick.labelled).length);
  });

  /**
   * The forecast boundary is not "now". It falls at the START of the first
   * predicted period, and the last MEASURED period can still be open: on the
   * release this was written against the two were three hours apart, so a
   * reader taking the boundary for the clock was reading it three hours late.
   */
  it("marks the clock inside its own three-hour period, not at the forecast boundary", () => {
    const nowIso = new Date(Date.UTC(2026, 7, 10, 13, 30)).toISOString();
    const { nowX, nowLabel, forecastBoundaryX, bars } = kpChartGeometry(series, nowIso, 900, 270);
    expect(nowX).not.toBeNull();
    expect(nowLabel).toBe("13:30Z");
    // 13:30 is half way through the 12:00 period, so the line lands between
    // that bar and the next one — and strictly before the forecast boundary.
    const openPeriod = bars.find((bar) => bar.timeIso.startsWith("2026-08-10T12"))!;
    expect(nowX!).toBeGreaterThan(openPeriod.x);
    expect(nowX!).toBeLessThan(forecastBoundaryX!);
  });

  /** A clock outside the drawn window draws no line rather than a clamped one. */
  it("draws no clock line when the clock is off the chart", () => {
    expect(kpChartGeometry(series, new Date(Date.UTC(2026, 7, 4)).toISOString()).nowX).toBeNull();
    expect(kpChartGeometry(series, null).nowX).toBeNull();
    expect(kpChartGeometry(series, "not a time").nowX).toBeNull();
  });

  /**
   * The geometry is built at the container's own pixel width so one viewBox
   * unit is one rendered pixel. Before this the viewBox was a fixed 320 units
   * against a 1,018 px render and the axis type, declared once at 5 px, came
   * out 15.9 px on a desktop and 5.2 px on a phone.
   */
  it("reports the box it was built for, and fits its plot inside it", () => {
    const geometry = kpChartGeometry(series, null, 1018, 300);
    expect(geometry.width).toBe(1018);
    expect(geometry.height).toBe(300);
    expect(geometry.plot.left).toBeGreaterThan(0);
    expect(geometry.plot.right).toBeLessThan(1018);
    expect(geometry.plot.bottom).toBeLessThan(300);
    for (const bar of geometry.bars) {
      expect(bar.x).toBeGreaterThanOrEqual(geometry.plot.left);
      expect(bar.x + bar.width).toBeLessThanOrEqual(geometry.plot.right + 0.01);
      expect(bar.y).toBeGreaterThanOrEqual(geometry.plot.top - 0.01);
      expect(bar.y + bar.height).toBeLessThanOrEqual(geometry.plot.bottom + 0.01);
    }
    // The value axis spans the whole plot, floor to ceiling.
    expect(geometry.valueTicks[0]!.y).toBeCloseTo(geometry.plot.bottom, 6);
    expect(geometry.valueTicks[geometry.valueTicks.length - 1]!.y).toBeCloseTo(geometry.plot.top, 6);
  });

  it("draws nothing from an empty release rather than an empty axis", () => {
    expect(kpChartGeometry([]).bars).toEqual([]);
    expect(kpChartSummary([])).toMatch(/No planetary K index rows/);
  });
});

describe("what the chart says about itself", () => {
  it("states the counts and the peak, with its storm level", () => {
    const summary = kpChartSummary(series);
    expect(summary).toMatch(/4 observed/);
    expect(summary).toMatch(/2 forecast/);
    expect(summary).toMatch(/7\.67/);
    expect(summary).toMatch(/G3 Strong/);
  });

  it("says plainly that it is not an aurora forecast for anywhere in particular", () => {
    expect(KP_LIMITATION).toMatch(/not a local measurement/i);
    expect(KP_LIMITATION).toMatch(/not an aurora forecast/i);
  });

  /**
   * The note used to end by saying the forecast bars are a prediction drawn
   * differently for it. The chart now SHADES the forecast region, outlines
   * those bars, and keys both — so the sentence described a picture printed
   * directly above it. Drawn beats written, and the drawing is asserted here
   * so deleting the sentence cannot quietly delete the fact with it.
   */
  it("draws the forecast claim instead of writing it", () => {
    expect(KP_LIMITATION).not.toMatch(/drawn differently/i);
    expect(explorerSource).toContain("now-kp-lead");
    expect(explorerSource).toContain("now-kp-boundary");
    expect(stylesheet).toMatch(/\.now-kp-bar\.is-predicted[^}]*stroke-dasharray/);
    expect(currentConditionsView()).toMatch(/NOAA forecast/);
  });
});

/**
 * The page. This codebase has shipped features that every unit test passed
 * over and no entry point reached, so the wiring is asserted too.
 */
describe("the awareness page is reachable and is the one home for NOAA's material", () => {
  it("ships a nav entry for it", () => {
    expect(indexMarkup).toMatch(/data-view="now"[^>]*data-mobile-label="Now"/);
  });

  /**
   * Sean: "It should be green yellow and red. Like if you look at the graphs
   * above, those shades of green yellow and red that match the site are
   * great." Those shades are the tokens the R/S/G tiles already use, at the
   * same NOAA breaks. Pinned so the chart cannot drift back to a hex literal
   * or to the cyan it used below the storm threshold.
   */
  it("colours the bars with the same severity tokens the R/S/G tiles use", () => {
    for (const [selector, token] of [
      [".now-scale[data-level=\"0\"]", "--mint"],
      [".now-scale[data-level=\"1\"], .now-scale[data-level=\"2\"]", "--amber"],
      [".now-scale[data-level=\"3\"], .now-scale[data-level=\"4\"], .now-scale[data-level=\"5\"]", "--coral"],
    ] as const) {
      expect(stylesheet).toContain(`${selector} { --scale-accent: var(${token}); }`);
    }
    expect(stylesheet).toContain(".now-kp-bar { --kp: var(--mint); fill: var(--kp); }");
    expect(stylesheet).toContain(".now-kp-bar.g1, .now-kp-bar.g2 { --kp: var(--amber); }");
    expect(stylesheet).toContain(".now-kp-bar.g3, .now-kp-bar.g4, .now-kp-bar.g5 { --kp: var(--coral); }");
    // No hex literal may reappear on a BAR rule; the two storm colours used to
    // be #f5c96a and #ff7b78 written out, which is how they drift.
    const bars = stylesheet.slice(stylesheet.indexOf(".now-kp-bar {"), stylesheet.indexOf(".now-kp-lead"));
    expect(bars).not.toMatch(/#[0-9a-f]{6}/i);
    expect(bars).not.toMatch(/var\(--cyan/);
  });

  /**
   * The key answers two independent questions and used to answer only one.
   * Three cyan swatches captioned Observed / Estimated / NOAA forecast said
   * observed bars are cyan, which stopped being true the moment a bar reached
   * G1 and turned amber. Evidence class is the TREATMENT; colour is the level.
   */
  it("keys the evidence class and the severity colour separately", () => {
    const html = currentConditionsView();
    for (const treatment of ["is-observed", "is-estimated", "is-predicted"]) {
      expect(html).toContain(`now-swatch ${treatment}`);
    }
    for (const level of ["g0", "g1", "g3"]) {
      expect(html).toContain(`now-key-level ${level}`);
    }
    expect(stylesheet).toContain(".now-key-level.g0 { background: var(--mint); }");
    expect(stylesheet).toContain(".now-key-level.g1 { background: var(--amber); }");
    expect(stylesheet).toContain(".now-key-level.g3 { background: var(--coral); }");
  });

  /**
   * This page prints TWO planetary K values from two NOAA products — the
   * 1-minute running estimate on the driver tile and the three-hour index on
   * the chart — and while a three-hour period is open they can be a whole band
   * apart. The site never merges its three Dst traces and names each on the
   * tile; the same rule applies here.
   */
  it("names which planetary K product each surface is showing", () => {
    expect(explorerSource).toContain("NOAA's 1-minute running estimate");
    expect(currentConditionsView()).toContain("PLANETARY K INDEX &middot; THREE-HOUR");
  });

  it("renders a shell with the chart and its legend", () => {
    const html = currentConditionsView();
    expect(html).toContain('id="now-kp-chart"');
    expect(html).toContain('id="now-swpc-mount"');
    expect(html).toMatch(/Observed/);
    expect(html).toMatch(/NOAA forecast/);
  });

  /**
   * The NOAA panels are MOVED into the page, never copied. One copy in the
   * document means the page and any other surface cannot state different
   * numbers, and it is the same rule the layer cards follow for their controls.
   */
  it("borrows the NOAA panels rather than duplicating them", () => {
    for (const id of ["swpc-panel-conditions", "swpc-panel-forecast", "swpc-panel-geomagnetic"]) {
      expect(indexMarkup.split(`id="${id}"`).length - 1).toBe(1);
      expect(explorerSource).toContain(id);
    }
    expect(explorerSource).toContain("private mountCurrentConditions()");
    expect(explorerSource).toContain("private returnOutlookPanels()");
    expect(indexMarkup).toContain('id="swpc-dialog-panels"');
  });

  it("points the rail's outlook button at the page instead of the retired dialog", () => {
    expect(explorerSource).toMatch(/swpc-outlook-open"\)\.addEventListener\("click", \(\) => this\.openContent\("now"\)\)/);
    expect(explorerSource).not.toContain("private openSwpcOutlook()");
  });
});
