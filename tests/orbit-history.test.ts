import { describe, expect, it } from "vitest";
import {
  MAX_JOINABLE_GAP_MS,
  VIEW_REQUIREMENTS,
  detrendSemiMajorAxis,
  eventLabelPermitted,
  eventNoun,
  formatDeltaV,
  formatMetres,
  selectPopulation,
  shardFor,
  toSegments,
  type ObjectSummary,
  type OrbitSample,
} from "../src/orbit-history";

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

function sample(t: number, semiMajorAxisKm = 6928): OrbitSample {
  return {
    t,
    perigeeKm: semiMajorAxisKm - 6378.135 - 3,
    apogeeKm: semiMajorAxisKm - 6378.135 + 3,
    semiMajorAxisKm,
    inclinationDeg: 53.16,
    eccentricity: 0.0004,
    bstar: 1e-4,
    tier: "full",
  };
}

function summary(overrides: Partial<ObjectSummary>): ObjectSummary {
  return {
    norad: 1,
    name: "TEST",
    objectType: "PAYLOAD",
    regime: "LEO",
    perigeeAltitudeKm: 550,
    apogeeAltitudeKm: 556,
    inclinationDeg: 53.16,
    sunSynchronous: false,
    mission: null,
    sector: null,
    constellation: null,
    intervals: 1,
    observedDays: 1,
    events: 0,
    deltaVMetresPerSecond: 0,
    medianDeltaAMetresPerDay: -5,
    repeatedSignature: null,
    outOfFamily: false,
    decaying: true,
    purposeLanguagePermitted: true,
    ...overrides,
  };
}

describe("toSegments — never interpolate across a gap", () => {
  it("joins points that are hours apart", () => {
    const { runs, isolated } = toSegments([sample(0), sample(6 * HOUR), sample(12 * HOUR)]);
    expect(runs).toHaveLength(1);
    expect(runs[0]).toHaveLength(3);
    expect(isolated).toHaveLength(0);
  });

  it("breaks the line across a gap longer than the detector's own bound", () => {
    const { runs } = toSegments([
      sample(0),
      sample(6 * HOUR),
      sample(6 * HOUR + MAX_JOINABLE_GAP_MS + 1),
      sample(6 * HOUR + MAX_JOINABLE_GAP_MS + 1 + HOUR),
    ]);
    expect(runs).toHaveLength(2);
    expect(runs[0]).toHaveLength(2);
    expect(runs[1]).toHaveLength(2);
  });

  it("keeps a point that no line can reach, rather than dropping it", () => {
    // An element set standing alone is still an observation. Dropping it hides
    // data; joining it to a neighbour four days away invents some.
    const { runs, isolated } = toSegments([sample(0), sample(4 * DAY), sample(9 * DAY)]);
    expect(runs).toHaveLength(0);
    expect(isolated).toHaveLength(3);
  });

  it("handles an empty and a single-point series", () => {
    expect(toSegments([])).toEqual({ runs: [], isolated: [] });
    expect(toSegments([sample(0)]).isolated).toHaveLength(1);
  });
});

describe("detrendSemiMajorAxis — the panel where steps live", () => {
  it("removes a pure linear decay to within floating-point noise", () => {
    const samples = Array.from({ length: 20 }, (_, index) =>
      sample(index * DAY, 6928 - index * 0.01),
    );
    for (const point of detrendSemiMajorAxis(samples)) {
      expect(Math.abs(point.residualMetres)).toBeLessThan(1e-6);
    }
  });

  it("leaves a step visible after the trend is removed", () => {
    const samples = [
      ...Array.from({ length: 10 }, (_, index) => sample(index * DAY, 6928 - index * 0.01)),
      ...Array.from({ length: 10 }, (_, index) =>
        sample((10 + index) * DAY, 6928 - (10 + index) * 0.01 + 0.5),
      ),
    ];
    const residuals = detrendSemiMajorAxis(samples).map((point) => point.residualMetres);
    expect(Math.max(...residuals) - Math.min(...residuals)).toBeGreaterThan(300);
  });

  it("does not lose precision fitting against raw millisecond epochs", () => {
    // Regression guard: fitting against epochs near 1.7e12 squares to 3e24 and
    // loses most of a double's mantissa, which shows up as a visibly wrong
    // slope. Times are reduced to days from the first sample before fitting.
    const base = 1_754_000_000_000;
    const samples = Array.from({ length: 30 }, (_, index) =>
      sample(base + index * DAY, 6928 - index * 0.01),
    );
    for (const point of detrendSemiMajorAxis(samples)) {
      expect(Math.abs(point.residualMetres)).toBeLessThan(1e-3);
    }
  });

  it("degrades honestly with fewer than three points", () => {
    const result = detrendSemiMajorAxis([sample(0, 6928), sample(DAY, 6929)]);
    expect(result).toHaveLength(2);
    expect(result[0]!.residualMetres).toBeCloseTo(-500, 3);
    expect(result[1]!.residualMetres).toBeCloseTo(500, 3);
  });
});

describe("selectPopulation — a view that cannot be answered says so", () => {
  const rows = [
    summary({ norad: 1, name: "BIG SPENDER", deltaVMetresPerSecond: 3.2, events: 1 }),
    summary({ norad: 2, name: "SMALL", deltaVMetresPerSecond: 0.01, events: 1 }),
    summary({ norad: 3, name: "FALLING", medianDeltaAMetresPerDay: -400, decaying: true }),
    summary({
      norad: 4,
      name: "ODD ONE",
      outOfFamily: true,
      deltaVMetresPerSecond: 0.5,
      events: 1,
    }),
    summary({
      norad: 5,
      name: "REGULAR",
      // A real repeat cluster needs the object's own history behind it, so the
      // fixture carries the coverage that would have produced it. Before the
      // 2004-2025 back-fill this row would have been impossible; a fixture that
      // still claimed four repeats from one day of coverage was asserting
      // something the pipeline can no longer produce.
      observedDays: 400,
      events: 4,
      repeatedSignature: { signature: "geo-east-west-keeping", count: 4 },
      repeatClusters: [
        {
          signature: "geo-east-west-keeping",
          count: 4,
          medianDeltaVMetresPerSecond: 0.14,
          deltaVSpreadMetresPerSecond: 0.01,
          medianDaysBetween: 14.2,
          spacingScaleDays: 0.9,
          firstAt: "2024-01-04T00:00:00Z",
          lastAt: "2024-02-15T00:00:00Z",
          totalDeltaVMetresPerSecond: 0.56,
        },
      ],
      cadence: {
        corrections: 4,
        spacingsUsed: 3,
        medianDaysBetween: 14.2,
        spacingScaleDays: 0.9,
        regularity: 0.06,
        correctionsPerYear: 25.7,
        observedDays: 400,
        note: "",
      },
    }),
  ];

  it("refuses the cadence question when no object has been watched long enough", () => {
    const hoursOld = rows.map((row) => ({
      ...row,
      observedDays: 0.04,
      cadence: null,
      repeatClusters: undefined,
    }));
    const result = selectPopulation(hoursOld, {
      view: "most-corrections",
      search: "",
      regime: null,
      minimumObservedDays: 0,
    }, 0.04);
    expect(result.rows).toHaveLength(0);
    expect(result.unavailable).not.toBeNull();
    expect(result.unavailable!.needs).toContain("week");
    // `haveDays` reports the best coverage any OBJECT has, not the archive-wide
    // capture ledger. After the back-fill the ledger read a few hours while the
    // archive held a year, and every longitudinal view stayed switched off in
    // front of the data that answers it.
    expect(result.unavailable!.haveDays).toBe(0.04);
  });

  it("gates each row on its own coverage, not on the archive's", () => {
    // REGULAR has four hundred days; every other row has one. The view is
    // answerable because REGULAR can answer it, and the one-day rows are still
    // excluded, because a three-week cadence cannot be measured in a day.
    const result = selectPopulation(rows, {
      view: "repeated",
      search: "",
      regime: null,
      minimumObservedDays: 0,
    }, 0.04);
    expect(result.unavailable).toBeNull();
    expect(result.rows.map((row) => row.name)).toEqual(["REGULAR"]);
  });

  it("answers the delta-v question immediately, because one pair is enough", () => {
    expect(VIEW_REQUIREMENTS["delta-v"].days).toBe(0);
    const result = selectPopulation(rows, {
      view: "delta-v",
      search: "",
      regime: null,
      minimumObservedDays: 0,
    }, 0.04);
    expect(result.unavailable).toBeNull();
    expect(result.rows[0]!.name).toBe("BIG SPENDER");
  });

  it("sorts the deorbiting view by fastest fall, not by magnitude", () => {
    const result = selectPopulation(rows, {
      view: "decaying",
      search: "",
      regime: null,
      minimumObservedDays: 0,
    }, 1);
    expect(result.rows[0]!.name).toBe("FALLING");
  });

  it("finds the out-of-family objects", () => {
    const result = selectPopulation(rows, {
      view: "out-of-family",
      search: "",
      regime: null,
      minimumObservedDays: 0,
    }, 1);
    expect(result.rows.map((row) => row.name)).toEqual(["ODD ONE"]);
  });

  it("requires three weeks before claiming a repeated cadence", () => {
    const filter = { view: "repeated" as const, search: "", regime: null, minimumObservedDays: 0 };
    const thin = rows.map((row) => ({ ...row, observedDays: 5, repeatClusters: undefined }));
    expect(selectPopulation(thin, filter, 5).unavailable).not.toBeNull();
    expect(selectPopulation(rows, filter, 30).rows.map((row) => row.name)).toEqual(["REGULAR"]);
  });

  it("searches by name and by catalog number", () => {
    const filter = { view: "all" as const, search: "falling", regime: null, minimumObservedDays: 0 };
    expect(selectPopulation(rows, filter, 1).rows).toHaveLength(1);
    expect(
      selectPopulation(rows, { ...filter, search: "4" }, 1).rows.map((row) => row.norad),
    ).toEqual([4]);
  });
});

describe("eventNoun — the browser never decides that something is established", () => {
  const event = {
    signature: "along-track-raise",
    signatureLabel: "in-plane raise",
    confidence: "candidate",
  };

  it("marks an event as a candidate while the label is not permitted", () => {
    expect(eventNoun(event, false)).toBe("in-plane raise (candidate)");
  });

  it("drops the qualifier only when the pipeline says the controls support it", () => {
    expect(eventNoun(event, true)).toBe("in-plane raise");
  });

  it("never calls decay a manoeuvre, whatever the label policy says", () => {
    expect(eventNoun({ ...event, signature: "drag-decay" }, true)).toBe("orbital decay");
    expect(eventNoun({ ...event, signature: "re-entry-decay" }, true)).toBe("re-entry decay");
    expect(eventNoun({ ...event, signature: "drag-and-thrust-not-separable" }, true)).toBe(
      "unattributed change",
    );
  });
});

describe("eventLabelPermitted — independent controls never lend each other certainty", () => {
  it("lets an event-specific refusal override a globally calibrated bundle", () => {
    expect(eventLabelPermitted({ manoeuvreLabelPermitted: false }, true)).toBe(false);
  });

  it("lets a calibrated event speak even if another lane keeps the bundle mixed", () => {
    expect(eventLabelPermitted({ manoeuvreLabelPermitted: true }, false)).toBe(true);
  });

  it("uses the bundle bit for older events that predate lane-specific permission", () => {
    expect(eventLabelPermitted({}, true)).toBe(true);
  });

  it("never lets legacy passive records borrow a bundle-wide permission", () => {
    expect(eventLabelPermitted({ objectType: "DEBRIS" }, true)).toBe(false);
    expect(eventLabelPermitted({ objectType: "ROCKET BODY" }, true)).toBe(false);
  });

  it("keeps the unproven thrust-excess lane at candidate", () => {
    expect(eventLabelPermitted({ objectType: "PAYLOAD", signature: "thrust-excess" }, true))
      .toBe(false);
  });
});

describe("formatting and sharding", () => {
  it("shows small costs in the units that make them readable", () => {
    expect(formatDeltaV(0.0006)).toBe("0.6 mm/s");
    expect(formatDeltaV(0.0766)).toBe("7.7 cm/s");
    expect(formatDeltaV(3.2085)).toBe("3.21 m/s");
    expect(formatDeltaV(null)).toBe("—");
  });

  it("shows lengths in the units that make them readable", () => {
    expect(formatMetres(-5843.5)).toBe("-5.843 km");
    expect(formatMetres(149)).toBe("+149.0 m");
    expect(formatMetres(0.12)).toBe("+12.0 cm");
    expect(formatMetres(229.5, false)).toBe("229.5 m");
  });

  it("agrees with the pipeline's norad % 256 sharding", () => {
    expect(shardFor(53168, 256)).toBe(53168 % 256);
    expect(shardFor(0, 256)).toBe(0);
    expect(shardFor(255, 256)).toBe(255);
    expect(shardFor(256, 256)).toBe(0);
  });
});
