import { describe, expect, test } from "vitest";

import {
  chooseThermosphereFrame,
  coverageBandPercent,
  shardsNear,
  thermosphereBadge,
  type ThermosphereFrame,
} from "../src/thermosphere";

/**
 * TWO MODELS ON ONE TIMELINE, and the rules that keep them separable.
 *
 * The defect this file was written against, measured on the live release of
 * 2026-08-20: NOAA WAM published 13 hourly frames covering 2026-08-19T23:40Z to
 * 2026-08-20T11:30Z — 11.8 hours against a slider spanning 120 — so 90% of the
 * timeline had no thermosphere at all. NRLMSIS now covers the whole of it,
 * because an empirical model is defined wherever its drivers reach.
 *
 * What must be true, and none of it is about pixels:
 *
 *   - WAM wins inside WAM's coverage. It is a physics forecast that resolves
 *     auroral heating; the empirical fit is known to under-respond to storms.
 *   - Outside it the empirical field is drawn, and NOTHING is blended, faded or
 *     interpolated across the boundary.
 *   - The badge changes at the same instant the field does, and it says
 *     FORECAST exactly where a forecast is what is on screen.
 */

function frameAt(validAt: string, extra: Partial<ThermosphereFrame> = {}): ThermosphereFrame {
  return {
    validAt,
    grid: { altitudeKm: [120], latitudeDeg: [0], longitudeDeg: [0] },
    encoding: { bits: 8, logFloor: -17, logCeiling: -5.5, quantumDex: 0.045 },
    codes: "",
    codesDtype: "uint8",
    validMask: "",
    validFraction: 1,
    ...extra,
  };
}

// The shape of the real release: a WAM cycle issued at 18Z publishing hours
// that all lie after it, and an empirical field on whole hours either side.
const WAM = {
  cycleStart: "2026-08-19T18:00:00Z",
  cadenceMinutes: 60,
  frames: ["2026-08-19T23:40:00Z", "2026-08-20T00:40:00Z", "2026-08-20T01:40:00Z"].map((t) => frameAt(t)),
};

const EMPIRICAL = {
  cadenceMinutes: 60,
  frames: [
    frameAt("2026-08-19T21:00:00Z", { driverStatus: "observed" }),
    frameAt("2026-08-19T22:00:00Z", { driverStatus: "observed" }),
    frameAt("2026-08-20T00:00:00Z", { driverStatus: "observed" }),
    frameAt("2026-08-20T01:00:00Z", { driverStatus: "observed" }),
    frameAt("2026-08-20T02:00:00Z", { driverStatus: "observed" }),
    frameAt("2026-08-20T03:00:00Z", { driverStatus: "observed" }),
    frameAt("2026-08-22T12:00:00Z", { driverStatus: "predicted" }),
  ],
};

describe("which model draws which hour", () => {
  test("NOAA WAM wins wherever NOAA WAM has a frame", () => {
    const chosen = chooseThermosphereFrame(WAM, EMPIRICAL, new Date("2026-08-20T00:35:00Z"));
    expect(chosen?.model).toBe("wamNeutral");
    expect(chosen?.frame.validAt).toBe("2026-08-20T00:40:00Z");
  });

  test("the empirical field draws the hours WAM does not reach", () => {
    // 21:00Z is two and a half hours before the WAM release begins. Before this
    // shipped the layer drew nothing here — and before e4502f8 it drew the
    // wrong hour and called it MODEL.
    const chosen = chooseThermosphereFrame(WAM, EMPIRICAL, new Date("2026-08-19T21:05:00Z"));
    expect(chosen?.model).toBe("nrlmsis21");
    expect(chosen?.frame.validAt).toBe("2026-08-19T21:00:00Z");
  });

  test("WAM's own gaps fall through to the empirical field, not to nothing", () => {
    // A frame NOAA published that the build could not read is a real state —
    // the release counts them in `skippedCount`. With 00:40Z missing, 00:00Z is
    // 20 minutes from 23:40Z and WAM still wins; but 00:50Z is 70 minutes from
    // the one before and 50 from the one after, so WAM has nothing honest to
    // offer and the empirical field covers the hole instead of the layer
    // blanking inside its own advertised window.
    const holed = { ...WAM, frames: [WAM.frames[0]!, WAM.frames[2]!] };
    expect(chooseThermosphereFrame(holed, EMPIRICAL, new Date("2026-08-20T00:00:00Z"))?.model)
      .toBe("wamNeutral");
    const chosen = chooseThermosphereFrame(holed, EMPIRICAL, new Date("2026-08-20T00:50:00Z"));
    expect(chosen?.model).toBe("nrlmsis21");
    expect(chosen?.frame.validAt).toBe("2026-08-20T01:00:00Z");
  });

  test("nothing is drawn where neither model published", () => {
    // 2026-08-21 is inside the slider and outside both series. The honest
    // answer is null, and the card falls to NO DATA on it.
    expect(chooseThermosphereFrame(WAM, EMPIRICAL, new Date("2026-08-21T09:00:00Z"))).toBeNull();
    expect(chooseThermosphereFrame(null, null, new Date("2026-08-20T00:00:00Z"))).toBeNull();
  });

  test("the empirical field alone still draws, when a release carries no WAM", () => {
    const chosen = chooseThermosphereFrame(null, EMPIRICAL, new Date("2026-08-20T03:00:00Z"));
    expect(chosen?.model).toBe("nrlmsis21");
  });
});

describe("the chip says what the frame on screen actually claims", () => {
  test("a WAM frame issued before the hour it describes is a FORECAST", () => {
    // Sean: is MODEL the only chip that layer should carry, "since we don't
    // have a forecast"? Every frame in the release is one: the cycle was
    // initialised at 18:00Z and publishes 23:40Z onward.
    const chosen = chooseThermosphereFrame(WAM, EMPIRICAL, new Date("2026-08-20T00:35:00Z"));
    expect(chosen?.forecast).toBe(true);
    expect(thermosphereBadge(chosen)).toEqual({ badge: "NOAA MODEL · FORECAST", evidence: "model" });
  });

  test("a WAM frame valid before its cycle was initialised is not", () => {
    const analysis = { ...WAM, cycleStart: "2026-08-20T06:00:00Z" };
    const chosen = chooseThermosphereFrame(analysis, EMPIRICAL, new Date("2026-08-20T00:35:00Z"));
    expect(chosen?.forecast).toBe(false);
    expect(thermosphereBadge(chosen).badge).toBe("NOAA MODEL");
  });

  test("the empirical field is EMPIRICAL behind the observed Kp record", () => {
    const chosen = chooseThermosphereFrame(WAM, EMPIRICAL, new Date("2026-08-19T21:05:00Z"));
    expect(thermosphereBadge(chosen)).toEqual({ badge: "EMPIRICAL", evidence: "empirical" });
  });

  test("and EMPIRICAL · FORECAST ahead of it", () => {
    // The one place a FORECAST claim is earned on this side: forward of the
    // last observed Kp interval the drivers are NOAA's forecast of Kp and
    // F10.7, and the frame carries that fact from the pipeline.
    const chosen = chooseThermosphereFrame(WAM, EMPIRICAL, new Date("2026-08-22T12:10:00Z"));
    expect(chosen?.forecast).toBe(true);
    expect(thermosphereBadge(chosen)).toEqual({ badge: "EMPIRICAL · FORECAST", evidence: "empirical" });
  });

  test("no frame is NO DATA, never a stale model name", () => {
    expect(thermosphereBadge(null)).toEqual({ badge: "NO DATA", evidence: "model" });
  });
});

describe("fetching only the shard the clock needs", () => {
  const SHARDS = [
    { validFrom: "2026-08-20T00:00:00Z", validTo: "2026-08-20T06:00:00Z" },
    { validFrom: "2026-08-20T06:00:00Z", validTo: "2026-08-20T12:00:00Z" },
    { validFrom: "2026-08-20T12:00:00Z", validTo: "2026-08-20T18:00:00Z" },
  ];

  test("one shard in the middle of a block", () => {
    expect(shardsNear(SHARDS, new Date("2026-08-20T03:00:00Z"), 1_800_000).map((s) => s.validFrom))
      .toEqual(["2026-08-20T00:00:00Z"]);
  });

  test("both shards near a boundary, because the nearest hour is over it", () => {
    // 05:45Z. The containing shard's last hour is 05:00Z, 45 minutes away and
    // therefore refused; the frame the layer should draw is 06:00Z, in the next
    // shard. Fetching only the containing shard leaves the last quarter of
    // every six-hour block drawing NO DATA — twenty holes across the timeline.
    expect(shardsNear(SHARDS, new Date("2026-08-20T05:45:00Z"), 1_800_000).map((s) => s.validFrom))
      .toEqual(["2026-08-20T00:00:00Z", "2026-08-20T06:00:00Z"]);
  });

  test("nothing outside the published set", () => {
    expect(shardsNear(SHARDS, new Date("2026-08-19T00:00:00Z"), 1_800_000)).toEqual([]);
    expect(shardsNear(SHARDS, new Date("nonsense"), 1_800_000)).toEqual([]);
  });
});

describe("where the assimilated-grade span sits on the timeline", () => {
  // A 120-hour window, the site's own: 48 hours back and 72 forward.
  const WINDOW = {
    startMs: Date.parse("2026-08-18T03:00:00Z"),
    endMs: Date.parse("2026-08-23T03:00:00Z"),
  };

  test("the real release covers under a tenth of the slider", () => {
    const band = coverageBandPercent(
      { validFrom: "2026-08-19T23:40:00Z", validTo: "2026-08-20T11:30:00Z" },
      WINDOW,
    );
    expect(band).not.toBeNull();
    expect(band!.endPercent - band!.startPercent).toBeCloseTo(9.83, 1);
  });

  test("a span reaching past the slider is clipped to it, not drawn beyond it", () => {
    const band = coverageBandPercent(
      { validFrom: "2026-08-10T00:00:00Z", validTo: "2026-08-30T00:00:00Z" },
      WINDOW,
    );
    expect(band).toEqual({ startPercent: 0, endPercent: 100 });
  });

  test("a span outside the slider is no band at all, not a zero-width mark", () => {
    // A mark at 0%-0% is a claim about the first instant of the timeline.
    expect(coverageBandPercent(
      { validFrom: "2026-08-01T00:00:00Z", validTo: "2026-08-02T00:00:00Z" },
      WINDOW,
    )).toBeNull();
  });
});
