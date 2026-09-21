import { describe, expect, it } from "vitest";

import stylesSource from "../src/styles.css?raw";
import indexMarkup from "../index.html?raw";
import mainSource from "../src/main.ts?raw";
import { evidenceBadge, flareClass, scaleTile, signed, sparkline, withMinusSigns } from "../src/conditions-board";
import type { EvidenceClass } from "../src/conditions-board";
import type { SwpcScaleReading, TimeValue } from "../src/types";

/**
 * The conditions board, and the type system it is set in.
 *
 * Each test below pins a REASON, not a rendering. The board exists because a
 * visitor could not tell in one look whether anything was happening, and it is
 * allowed to be redrawn any way at all — as long as it never draws a line for
 * a quantity nobody published, never prints a transformed number as if it were
 * a measured one, and never loses the evidence badge that says which kind of
 * claim a tile is making.
 */

function samples(values: Array<number | null>, stepMinutes = 10): TimeValue[] {
  const start = Date.parse("2026-08-19T00:00:00Z");
  return values.map((value, index) => ({
    time: new Date(start + index * stepMinutes * 60_000).toISOString(),
    value,
  }));
}

describe("a sparkline never invents the part of the box it cannot see", () => {
  it("refuses to draw from a single sample", () => {
    // One sample is a value, not a history. Drawn as a line it would assert a
    // flat hour that nobody measured, which is the exact failure a prettier
    // layout invites: the box looks finished either way.
    expect(sparkline(samples([420]), 220, 40)).toBeNull();
  });

  it("refuses to draw when every published value is null", () => {
    expect(sparkline(samples([null, null, null]), 220, 40)).toBeNull();
  });

  it("skips null samples inside an otherwise real series", () => {
    const spark = sparkline(samples([400, null, 460]), 220, 40);
    expect(spark).not.toBeNull();
    expect(spark!.count).toBe(2);
  });

  it("places x by wall-clock time, so a gap in the feed is visible as one", () => {
    // Ten minutes of samples then a four-hour hole then one more. By index the
    // hole would be one step wide like every other; by time it is most of the
    // box, which is what a reader needs to see before trusting the last point.
    const series: TimeValue[] = [
      { time: "2026-08-19T00:00:00Z", value: 400 },
      { time: "2026-08-19T00:10:00Z", value: 410 },
      { time: "2026-08-19T04:10:00Z", value: 500 },
    ];
    const spark = sparkline(series, 240, 40)!;
    const xs = spark.d.match(/[ML](-?[\d.]+)/g)!.map((token) => Number(token.slice(1)));
    // The first gap is 10 minutes of 250; the second is 240 minutes of 250.
    expect(xs[1]! - xs[0]!).toBeLessThan(20);
    expect(xs[2]! - xs[1]!).toBeGreaterThan(200);
  });

  it("reports the range in published units even when the trace is transformed", () => {
    // The X-ray tile scales by log10 so the flare decades are drawable. Its
    // range line still has to read in W/m2 — "−6.2 to −5.3" is a pair of
    // numbers nobody measured and no operator would recognise.
    const spark = sparkline(samples([1e-7, 1e-6, 5e-6]), 220, 40, {
      transform: (value) => Math.log10(value),
    })!;
    expect(spark.min).toBeCloseTo(1e-7, 12);
    expect(spark.max).toBeCloseTo(5e-6, 12);
  });

  it("marks the zero line only when the drawn range contains zero", () => {
    // Bz south is the whole point of the Bz tile, so the sign has to be
    // visible; a solar-wind speed trace that never approaches zero must not
    // grow a baseline that implies it could.
    expect(sparkline(samples([-4, 2, -6]), 220, 40)!.zeroY).not.toBeNull();
    expect(sparkline(samples([400, 460, 520]), 220, 40)!.zeroY).toBeNull();
  });

  it("honours a fixed domain, so a quiet Kp day is drawn as a quiet day", () => {
    // Auto-scaled, a day that ran between Kp 0 and Kp 1 would fill the box top
    // to bottom and look like a storm.
    const quiet = sparkline(samples([0, 1, 0.5]), 220, 40, { domain: [0, 9] })!;
    const ys = quiet.d.match(/ (-?[\d.]+)/g)!.map((token) => Number(token));
    expect(Math.min(...ys)).toBeGreaterThan(30);
  });
});

describe("a scale tile says what NOAA published and nothing more", () => {
  const reading = (level: number | null, label: string | null = null): SwpcScaleReading =>
    ({ level, label } as SwpcScaleReading);

  it("does not colour an unpublished level as an all-clear", () => {
    // `data-level=""` picks up the muted default in styles.css. Green is
    // reserved for a published zero: "no data" drawn as "all clear" is the
    // single most dangerous thing this board could do.
    const tile = scaleTile("G", "Geomagnetic", reading(null), reading(null));
    expect(tile.level).toBeNull();
    expect(tile.levelText).toBe("G—");
    expect(tile.description).toMatch(/no value/i);
  });

  it("carries the rolling 24-hour maximum, because a quiet instant is not a quiet day", () => {
    const tile = scaleTile("G", "Geomagnetic", reading(0), reading(1, "minor"));
    expect(tile.description).toMatch(/below noaa scale threshold/i);
    expect(tile.dayMax).toMatch(/24 h maximum G1/);
  });
});

describe("numbers are set the way the site sets numbers", () => {
  it("uses a minus sign, not a hyphen", () => {
    expect(signed(-29)).toBe("−29");
    // The classifier's own sentence arrives as published text and is now the
    // largest sentence on the page.
    expect(withMinusSigns("Dst at or below -30 nT and still falling")).toBe(
      "Dst at or below −30 nT and still falling",
    );
  });

  it("leaves hyphenated words alone", () => {
    expect(withMinusSigns("model-derived, mid-latitude")).toBe("model-derived, mid-latitude");
  });

  it("reads GOES flux in flare classes", () => {
    expect(flareClass(9.0e-7)).toBe("B9.0");
    expect(flareClass(1.2e-5)).toBe("M1.2");
    // NOAA publishes no class below A1 and neither does this.
    expect(flareClass(1e-9)).toBe("below A1");
  });
});

describe("the type system is a system, not a suggestion", () => {
  it("defines every role as a custom property", () => {
    for (const token of [
      "--type-kicker:",
      "--type-title:",
      "--type-label:",
      "--type-disclose:",
      "--type-disclose-sub:",
      "--type-body:",
      "--type-readout:",
    ]) {
      expect(stylesSource).toContain(token);
    }
  });

  it("carries both typefaces in the bundle rather than hoping for them", () => {
    // Every rule in styles.css has asked for Inter and IBM Plex Mono since the
    // site was written and neither was ever shipped, so a visitor without them
    // installed read the whole interface in two substituted faces.
    expect(stylesSource).toContain("./fonts/inter-400-700.woff2");
    expect(stylesSource).toContain("./fonts/plex-mono-600.woff2");
    expect(stylesSource).not.toMatch(/@import url\(https:\/\/fonts/);
  });

  it("keeps tracked uppercase monospace for surface names only", () => {
    // The rule that makes the rail readable: a control caption may not be set
    // the same way as the section name two levels above it. `.field-label`
    // used to be uppercase tracked mono, indistinguishable from
    // `.section-kicker` — which is the pair Sean pointed at.
    const label = stylesSource.match(/\n\.field-label \{[^}]*\}/)![0];
    expect(label).toContain("var(--type-label)");
    expect(label).not.toContain("text-transform: uppercase");
  });

  it("gives every rail section one header, never a kicker stacked on a title", () => {
    // "See CATALOG and underneath bigger text saying Satellites ... There is
    // no hierarchy. It looks random and unplanned."
    const railStart = indexMarkup.indexOf('id="control-rail"');
    const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));
    expect(rail).not.toContain("section-kicker");
    // `class="rail-head"` on its own, or `class="rail-head <fold>-summary"`
    // where the header is also the `summary` that folds the section away.
    // Three of the five now fold - Find a satellite, Favorites, Satellites -
    // and folding one must not cost it its header, which is the regression
    // this line is written to catch.
    expect(rail.match(/class="rail-head[ "]/g)?.length ?? 0).toBeGreaterThanOrEqual(4);
  });
});

describe("the board is wired to published data, not to constants", () => {
  it("reads each tile's evidence class from the release's own source list", () => {
    // Hard-coding OBSERVED beside a number would be the site asserting a claim
    // on NOAA's behalf, and would go stale silently the day a feed changed.
    expect(mainSource).toContain("private sourceEvidence(");
    expect(mainSource).toContain('this.weather.sources.find((entry) => entry.product === product)');
  });

  it("prints the same Dst trace the storm classifier used", () => {
    // Three traces, never merged, and they disagree by 10-15 nT at the same
    // instant. A verdict quoting USGS Dst3 above a tile quoting Kyoto is the
    // page contradicting itself in two places a reader sees at once.
    expect(mainSource).toContain('headline?.dstSource === "USGS Dst3"');
    expect(mainSource).toContain('headline?.dstSource === "physics-model nowcast"');
  });

  it("shows the Kp/Dst reconciliation on the same screen as both numbers", () => {
    expect(mainSource).toContain('document.getElementById("now-scale-conflict")');
    expect(indexMarkup.includes('id="now-scale-conflict"') || mainSource.includes("now-scale-conflict")).toBe(true);
  });
});

describe("the badge word and the badge class cannot disagree", () => {
  /**
   * The badge is the board's whole promise. It used to be two independent
   * fields — a hardcoded "OBSERVED" beside an evidence class looked up from
   * the release — so a product the pipeline had reclassified would have been
   * printed with the wrong word in the right colour, and nothing in the suite
   * could have seen it.
   */
  it("derives the word from the class, for every class the board uses", () => {
    const classes: EvidenceClass[] = ["observed", "assimilated", "model", "forecast", "empirical"];
    for (const evidence of classes) {
      const badge = evidenceBadge(evidence);
      expect(badge.evidence).toBe(evidence);
      expect(badge.text).toBe(evidence.toUpperCase());
    }
  });

  /**
   * And the board itself has to go through it. A literal badge word beside a
   * looked-up class is the exact shape of the defect, so it is banned here
   * rather than merely fixed once.
   */
  it("builds every conditions-board badge through evidenceBadge", () => {
    const board = mainSource.slice(mainSource.indexOf("const tiles: DriverTile[] = ["));
    const tiles = board.slice(0, board.indexOf("driversHost.replaceChildren"));
    expect(tiles).toContain("badge: evidenceBadge(");
    expect(tiles).not.toMatch(/badge:\s*\{/);
  });
});
