import { describe, expect, it } from "vitest";

import fixture from "./data/plasmasphere-dgcpm-2026-08-08.json";
import { dgcpmCoverageNotice, dgcpmLegendSpec, plasmasphereLegendSpec, ringCurrentLegendSpec } from "../src/main";
import {
  type DgcpmBundle,
  DGCPM_NOWCAST_CLOCK_SLACK_MINUTES,
  DGCPM_NOWCAST_HOLD_CADENCES,
  PLASMASPHERE_DENSITY_SCALE,
  PLASMASPHERE_DGCPM,
  createPlasmasphereFieldGeometry,
  decodeDgcpmSequence,
  dgcpmFieldAt,
  dgcpmNowcastLine,
  duskBulgeL,
  plasmasphereFieldAt,
} from "../src/inner-magnetosphere";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";

/**
 * The browser half of the DGCPM plasmasphere.
 *
 * The fixture is REAL published output, not a mock: three frames lifted
 * unaltered out of a `pipeline/plasmasphere_dgcpm.py` run against the actual
 * NOAA Kp record for the storm of 2026-08-08 — quiet before it, the Kp 5.67
 * peak, and eight hours into the recovery. That means these tests check the
 * pipeline-to-browser contract on bytes the pipeline really wrote, and the
 * plume the Python side measured is the plume this side has to find.
 */
const bundle = fixture as unknown as DgcpmBundle;

const EARTH_SCENE_RADIUS = 100;
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  return { x: xRe * scale, y: yRe * scale, z: zRe * scale, length: () => radius * scale } as never;
};

const QUIET = new Date("2026-08-07T18:00:00Z");
const PEAK = new Date("2026-08-08T18:00:00Z");
const RECOVERY = new Date("2026-08-09T02:00:00Z");

describe("the published DGCPM sequence decodes to the field the pipeline computed", () => {
  const sequence = decodeDgcpmSequence(bundle);

  it("carries the grid it declares", () => {
    expect(sequence.lValues.length).toBe(bundle.grid.lCount);
    expect(sequence.mltHours.length).toBe(bundle.grid.mltCount);
    for (const block of sequence.logDensity) {
      expect(block.length).toBe(bundle.grid.lCount * bundle.grid.mltCount);
    }
  });

  it("refuses a bundle whose payload and grid disagree", () => {
    const broken = { ...bundle, grid: { ...bundle.grid, lCount: 5, lValues: [2, 3, 4, 5, 6] } };
    expect(() => decodeDgcpmSequence(broken as unknown as DgcpmBundle)).toThrow();
  });

  it("refuses an unknown schema rather than guessing at it", () => {
    const future = { ...bundle, schemaVersion: "dgcpm-plasmasphere.v9" };
    expect(() => decodeDgcpmSequence(future as unknown as DgcpmBundle)).toThrow(/schema/);
  });

  it("reads the same density the encoder wrote, to the quantiser's precision", () => {
    // Decode one grid point by hand from the base64 and compare it against the
    // field's own bilinear sample at exactly that point, where bilinear is an
    // identity.
    const frame = bundle.frames[1]!;
    const binary = atob(frame.densityU16);
    const mltCount = bundle.grid.mltCount;
    const lIndex = 20;
    const mltIndex = 32;
    const offset = (lIndex * mltCount + mltIndex) * 2;
    const raw = (binary.charCodeAt(offset) & 0xff) | ((binary.charCodeAt(offset + 1) & 0xff) << 8);
    const encoding = bundle.fieldEncodings.electronDensity;
    const expected = 10 ** (encoding.minimum + (raw / 65535) * (encoding.maximum - encoding.minimum));
    const field = dgcpmFieldAt(sequence, PEAK)!;
    const actual = field.densityAt(bundle.grid.lValues[lIndex]!, bundle.grid.mltHours[mltIndex]!)!;
    // Within float32, which is what the decoded grid is stored as.
    expect(actual / expected).toBeCloseTo(1, 5);
  });

  it("draws nothing outside the simulated L range", () => {
    const field = dgcpmFieldAt(sequence, PEAK)!;
    const [inner, outer] = field.validLRange;
    expect(field.densityAt(inner - 0.01, 12)).toBeNull();
    expect(field.densityAt(outer + 0.01, 12)).toBeNull();
    expect(field.densityAt(inner, 12)).not.toBeNull();
    expect(field.densityAt(outer, 12)).not.toBeNull();
  });

  it("wraps in magnetic local time instead of stopping at midnight", () => {
    const field = dgcpmFieldAt(sequence, PEAK)!;
    expect(field.densityAt(4, 0)).toBeCloseTo(field.densityAt(4, 24)!, 9);
    expect(field.densityAt(4, -0.5)).toBeCloseTo(field.densityAt(4, 23.5)!, 9);
  });

  it("selects the nearest published frame and refuses times it does not reach", () => {
    const nearPeak = dgcpmFieldAt(sequence, new Date("2026-08-08T18:40:00Z"))!;
    expect(nearPeak.validAt).toBe("2026-08-08T18:00:00Z");
    expect(nearPeak.frameOffsetMinutes).toBe(40);
    // More than half a cadence away from any frame: the sequence says nothing.
    expect(dgcpmFieldAt(sequence, new Date("2026-08-08T06:00:00Z"))).toBeNull();
    expect(dgcpmFieldAt(sequence, new Date("2026-09-01T00:00:00Z"))).toBeNull();
  });
});

describe("the storm is visible in the decoded frames, not only in the pipeline", () => {
  const sequence = decodeDgcpmSequence(bundle);
  const quiet = dgcpmFieldAt(sequence, QUIET)!;
  const peak = dgcpmFieldAt(sequence, PEAK)!;
  const recovery = dgcpmFieldAt(sequence, RECOVERY)!;

  it("erodes: the plasmasphere is smaller and thinner at the storm peak", () => {
    const midnight = (field: typeof peak) =>
      field.plasmapauseByMlt.find((point) => point.mltHours < 0.3)!.lRe!;
    // The night side is where the convection field pushes the boundary in.
    expect(midnight(peak)).toBeLessThan(midnight(quiet) - 1.0);
    expect(peak.plasmapauseLRe).toBeLessThan(quiet.plasmapauseLRe - 0.5);
    // And the density at a fixed shell in the eroded region collapses.
    const before = quiet.densityAt(4.5, 0)!;
    const during = peak.densityAt(4.5, 0)!;
    expect(during).toBeLessThan(before / 5);
  });

  it("holds the dusk boundary out while the night side collapses", () => {
    const at = (field: typeof peak, mlt: number) =>
      field.plasmapauseByMlt.find((point) => Math.abs(point.mltHours - mlt) < 0.3)!.lRe!;
    const nightLoss = at(quiet, 0) - at(peak, 0);
    const duskLoss = at(quiet, 18) - at(peak, 18);
    expect(nightLoss).toBeGreaterThan(1.0);
    expect(duskLoss).toBeLessThan(nightLoss / 3);
  });

  it("grows a dusk-side bulge that the empirical profile cannot have", () => {
    expect(duskBulgeL(peak)!).toBeGreaterThan(0.5);
    // The empirical model is axisymmetric inside the plasmapause by
    // construction, so its dusk and midnight densities are identical.
    const empirical = plasmasphereFieldAt(
      [{ at: "2026-08-08T17:00:00Z", dstNt: -60 }, { at: "2026-08-08T18:00:00Z", dstNt: -60 }],
      PEAK,
    )!;
    expect(empirical.densityAt(3, 18)).toBeCloseTo(empirical.densityAt(3, 0)!, 9);
  });

  it("carries a drainage plume at the peak and in recovery, and none when quiet", () => {
    expect(quiet.plume.present).toBe(false);
    expect(peak.plume.present).toBe(true);
    expect(peak.plume.extentL!).toBeGreaterThan(1);
    expect(peak.plume.peakMltHours!).toBeGreaterThanOrEqual(14);
    expect(peak.plume.peakMltHours!).toBeLessThanOrEqual(20);
    // The plume rotates toward later local times as the convection relaxes,
    // which is what a real plume observed by IMAGE EUV does.
    expect(recovery.plume.present).toBe(true);
    expect(recovery.plume.peakMltHours!).toBeGreaterThan(peak.plume.peakMltHours!);
  });

  it("shows the plume as a real density protrusion, not only as a metric", () => {
    // At L = 4.6 — outside the eroded night boundary — the dusk sector must
    // hold plasmaspheric-grade density while midnight is in the trough.
    const dusk = peak.densityAt(4.6, peak.plume.peakMltHours!)!;
    const midnight = peak.densityAt(4.6, 0)!;
    expect(dusk).toBeGreaterThan(50);
    expect(midnight).toBeLessThan(dusk / 5);
  });
});

describe("what the reader is told about the simulation", () => {
  const sequence = decodeDgcpmSequence(bundle);
  const peak = dgcpmFieldAt(sequence, PEAK)!;

  it("is badged as a simulation, never as an observation", () => {
    const spec = dgcpmLegendSpec(peak);
    expect(spec.badge).toBe("PHYSICS SIMULATION");
    expect(spec.evidence).toBe("model");
    expect(spec.scale).toBeTruthy();
    expect(spec.statusState).toBe("ready");
  });

  it("routes through the shared layer spec, so the card cannot diverge", () => {
    expect(plasmasphereLegendSpec(peak)).toEqual(dgcpmLegendSpec(peak));
  });

  it("cites the model and the electric field, with dois", () => {
    const spec = dgcpmLegendSpec(peak);
    expect(spec.note).toContain(PLASMASPHERE_DGCPM.doi);
    expect(spec.note).toContain(PLASMASPHERE_DGCPM.electricFieldDoi);
    expect(spec.note).toContain("Maynard & Chen");
    expect(spec.note).toContain("Volland-Stern");
  });

  it("answers the coupling question in words, in both directions", () => {
    const note = dgcpmLegendSpec(peak).note;
    expect(note).toContain("solar wind");
    expect(note).toContain("ring current");
    expect(note).toContain("does not feed back");
    expect(note).toContain("WHAT IS NOT MODELLED");
  });

  it("prints the plume and the drive it came from", () => {
    const stats = dgcpmLegendSpec(peak).stats!;
    const plume = stats.find((entry) => entry.label.includes("PLUME"))!;
    expect(plume.value).toContain("MLT");
    const drive = stats.find((entry) => entry.label.includes("Kp"))!;
    expect(drive.value).toContain(peak.frame.kp.toFixed(2));
    expect(drive.value).toContain(String(Math.round(peak.frame.convectionAmplitudeVPerRe2)));
  });
});

/**
 * The first-click camera tests lived here until 2026-08-18.
 *
 * They pinned that switching the plasmasphere on evaluated its field before
 * pointing the camera at it, so the first click never dollied in to a bare
 * globe. That behaviour is gone with the control: the grain cloud left the rail
 * — Sean, on the stipple: "right now it looks fake" — and the boundary moved to
 * the Current conditions page, which has no camera to move.
 *
 * The decoding and limit tests below are untouched. The simulation is still
 * loaded and still feeds the ring current's convection field; only the cloud
 * stopped being drawn.
 */

describe("the stipple is built against the simulation's own limits", () => {
  const sequence = decodeDgcpmSequence(bundle);
  const quiet = dgcpmFieldAt(sequence, QUIET)!;
  const peak = dgcpmFieldAt(sequence, PEAK)!;
  const recovery = dgcpmFieldAt(sequence, RECOVERY)!;

  it("places no grain outside the published L range", () => {
    const geometry = createPlasmasphereFieldGeometry(peak, { positionForGsm, sampleCount: 4000 });
    const shells = geometry.getAttribute("shellL");
    const [inner, outer] = peak.validLRange;
    for (let index = 0; index < shells.count; index += 1) {
      expect(shells.getX(index)).toBeGreaterThanOrEqual(inner - 1e-6);
      expect(shells.getX(index)).toBeLessThanOrEqual(outer + 1e-6);
    }
    expect(geometry.userData.source).toBe("dgcpm");
    expect(geometry.userData.validLRange).toEqual([inner, outer]);
  });

  // 30 s timeout: this test builds three full stipple geometries; under the
  // 5 s default it times out whenever the machine is loaded (observed at
  // load-average 25 with agents building) and reads as a false failure.
  it("puts measurably more drawn brightness at dusk than at dawn, and more of it as the storm relaxes", { timeout: 30_000 }, () => {
    // The picture, in the units a viewer actually integrates: the shader's own
    // alpha, summed over the grains a ray down the dipole axis crosses, inside
    // the L band the plume occupies. Numbers, before any screenshot.
    const minimumLog = Math.log10(PLASMASPHERE_DENSITY_SCALE.minimumCm3);
    const maximumLog = Math.log10(PLASMASPHERE_DENSITY_SCALE.maximumCm3);
    const brightnessRatio = (field: typeof peak) => {
      const geometry = createPlasmasphereFieldGeometry(field, { positionForGsm, sampleCount: 60_000 });
      const positions = geometry.getAttribute("position");
      const logDensity = geometry.getAttribute("logDensity");
      const edgeFade = geometry.getAttribute("edgeFade");
      const shells = geometry.getAttribute("shellL");
      let dusk = 0;
      let dawn = 0;
      for (let index = 0; index < logDensity.count; index += 1) {
        const shell = shells.getX(index);
        if (shell < 4 || shell > 6) continue;
        const t = Math.min(1, Math.max(0, (logDensity.getX(index) - minimumLog) / (maximumLog - minimumLog)));
        const alpha = (0.002 + 0.6 * t ** 2.4) * edgeFade.getX(index);
        // GSM +x is noon, +y is dusk, so MLT = 12 + atan2(y, x) in hours.
        const mlt = (((12 + (Math.atan2(positions.getY(index), positions.getX(index)) * 12) / Math.PI) % 24) + 24) % 24;
        if (mlt >= 15 && mlt < 21) dusk += alpha;
        if (mlt >= 3 && mlt < 9) dawn += alpha;
      }
      return dusk / dawn;
    };
    const quietRatio = brightnessRatio(quiet);
    const peakRatio = brightnessRatio(peak);
    const recoveryRatio = brightnessRatio(recovery);
    expect(quietRatio).toBeLessThan(1.8);
    expect(peakRatio).toBeGreaterThan(2.0);
    expect(recoveryRatio).toBeGreaterThan(peakRatio);
  });

  it("gives the dusk sector more high-density grains than midnight at the peak", () => {
    // The picture, measured. A plume is only real if the grains that carry
    // plasmaspheric density are actually placed on the dusk side.
    const geometry = createPlasmasphereFieldGeometry(peak, { positionForGsm, sampleCount: 60_000 });
    const positions = geometry.getAttribute("position");
    const shells = geometry.getAttribute("shellL");
    const logDensity = geometry.getAttribute("logDensity");
    let dusk = 0;
    let dawn = 0;
    for (let index = 0; index < shells.count; index += 1) {
      const shell = shells.getX(index);
      if (shell < 4.2 || shell > 5.4) continue;
      if (logDensity.getX(index) < Math.log10(50)) continue;
      // GSM +y is dusk, -y is dawn; the mapper preserves the sign of y.
      if (positions.getY(index) > 0) dusk += 1;
      else dawn += 1;
    }
    expect(dusk).toBeGreaterThan(dawn * 2);
  });
});

/**
 * THE NEWEST FRAME, READ AS THE PRESENT — and the line that is still not crossed.
 *
 * The rule under test: past the newest published frame the layer draws that
 * frame and prints its age, for one publishing cadence; a clock in the FUTURE
 * is refused exactly as before; and past one cadence the successor is overdue
 * and the layer goes off. See `DGCPM_NOWCAST_HOLD_CADENCES` in
 * src/inner-magnetosphere.ts for why the symmetric half-cadence rule alone left
 * the ring current dark for half of every publishing cycle.
 */
describe("the newest published frame is the nowcast, and says how old it is", () => {
  const sequence = decodeDgcpmSequence(bundle);
  const NEWEST_MS = Date.parse("2026-08-09T02:00:00Z");
  const CADENCE_MINUTES = 120;
  const at = (minutesPastNewest: number) => new Date(NEWEST_MS + minutesPastNewest * 60_000);

  it("holds the newest frame 21 minutes past itself and labels the age", () => {
    const clock = at(21);
    const field = dgcpmFieldAt(sequence, clock, clock)!;
    expect(field.validAt).toBe("2026-08-09T02:00:00Z");
    expect(field.nowcast).not.toBeNull();
    expect(field.nowcast!.ageMinutes).toBe(21);
    // 21 minutes is inside the old half-cadence window, so it drew before this
    // change too. What it did NOT do was say it was 21 minutes old.
    expect(field.nowcast!.held).toBe(false);
    expect(dgcpmNowcastLine(field.nowcast!, "this density field is the newest published frame"))
      .toContain("21 min old");
  });

  it("draws at 90 minutes past the newest frame, where it used to refuse", () => {
    const clock = at(90);
    // The rule as it was: nearest frame within half a cadence, and nothing else.
    expect(dgcpmFieldAt(sequence, clock)).toBeNull();
    const field = dgcpmFieldAt(sequence, clock, clock)!;
    expect(field.validAt).toBe("2026-08-09T02:00:00Z");
    expect(field.nowcast!.held).toBe(true);
    expect(field.nowcast!.ageMinutes).toBe(90);
    const line = dgcpmNowcastLine(field.nowcast!, "these drift paths are traced in the newest published frame");
    // Loud, because the reader is looking at a picture the site would have
    // refused to draw before, and the age is now the size of a Kp interval.
    expect(line).toContain("AGEING");
    expect(line).toContain("1 h 30 min old");
  });

  it("refuses past one publishing cadence, where the successor is overdue", () => {
    expect(DGCPM_NOWCAST_HOLD_CADENCES).toBe(1);
    const stillHeld = at(CADENCE_MINUTES);
    expect(dgcpmFieldAt(sequence, stillHeld, stillHeld)).not.toBeNull();
    const overdue = at(CADENCE_MINUTES + 1);
    expect(dgcpmFieldAt(sequence, overdue, overdue)).toBeNull();
    const longDead = at(CADENCE_MINUTES * 6);
    expect(dgcpmFieldAt(sequence, longDead, longDead)).toBeNull();
  });

  /**
   * THE LINE THAT IS NOT CROSSED. Sean, on a forecast magnetosphere: "what the
   * fuck am I seeing in the future? If we can't get a forecasted magnetosphere,
   * just leave it off." A held frame is a statement about NOW. Scrub the clock
   * forward and it is a statement about a time nothing has simulated, and the
   * layer refuses exactly as it did before.
   */
  it("never holds a frame for a clock scrubbed into the future", () => {
    const now = at(10);
    // Every one of these would be drawn if the clock were at now, and none of
    // them is drawn when the clock is ahead of it. The hold is a claim about
    // the present and it will not be made about a time that has not happened.
    expect(dgcpmFieldAt(sequence, at(70), at(70))).not.toBeNull();
    expect(dgcpmFieldAt(sequence, at(70), now)).toBeNull();
    expect(dgcpmFieldAt(sequence, at(119), now)).toBeNull();
    expect(dgcpmFieldAt(sequence, new Date(NEWEST_MS + 26 * 60 * 60_000), now)).toBeNull();
  });

  it("allows only the clock tick's worth of slack on the hold, not a look ahead", () => {
    expect(DGCPM_NOWCAST_CLOCK_SLACK_MINUTES).toBe(2);
    // A minute past the clock is the 4 Hz tick, and the hold still applies.
    expect(dgcpmFieldAt(sequence, at(61), at(60))).not.toBeNull();
    // Three is a look ahead, and it is refused.
    expect(dgcpmFieldAt(sequence, at(63), at(60))).toBeNull();
    // The rule the hold did NOT touch: inside half a cadence of the newest
    // frame the nearest-frame rule answers, and it always did, ahead of the
    // clock or behind it. That is unchanged by this work and is stated here so
    // the boundary being tested above is not mistaken for a wider one.
    expect(dgcpmFieldAt(sequence, at(33), at(30))).not.toBeNull();
    expect(dgcpmFieldAt(sequence, at(33))).not.toBeNull();
  });

  it("never papers over a hole between two published frames", () => {
    // The fixture has a 24-hour gap between its first and second frames. An
    // instant 90 minutes past the FIRST one is 90 minutes past a frame that
    // has a published successor, which is a different fact from being past the
    // newest frame, and it stays refused.
    const insideGap = new Date(Date.parse("2026-08-07T18:00:00Z") + 90 * 60_000);
    expect(dgcpmFieldAt(sequence, insideGap, insideGap)).toBeNull();
    expect(dgcpmFieldAt(sequence, insideGap, new Date(NEWEST_MS + 30 * 60_000))).toBeNull();
  });

  it("claims no nowcast while the reader is scrubbing history", () => {
    const now = at(30);
    const historic = dgcpmFieldAt(sequence, PEAK, now)!;
    expect(historic.validAt).toBe("2026-08-08T18:00:00Z");
    expect(historic.nowcast).toBeNull();
    expect(dgcpmLegendSpec(historic).conditionLine).toBeUndefined();
  });

  it("puts the age on the legend, where a reader has it without opening anything", () => {
    const clock = at(45);
    const field = dgcpmFieldAt(sequence, clock, clock)!;
    const spec = dgcpmLegendSpec(field);
    expect(spec.statusState).toBe("ready");
    expect(spec.conditionLine).toContain("45 min old");
    // ...and on the card's FRAME row, for the reader who did open it.
    const frameRow = spec.stats?.find((row) => row.label === "FRAME");
    expect(frameRow?.value).toContain("HELD AS THE NOWCAST");
  });

  /**
   * THE NUMBER SEAN ASKED FOR. Sweep a whole publishing cycle a minute at a
   * time and count the minutes the layer can draw, before and after.
   */
  it("draws for the whole publishing cycle instead of half of it", () => {
    let before = 0;
    let after = 0;
    for (let minute = 0; minute <= CADENCE_MINUTES; minute += 1) {
      const clock = at(minute);
      if (dgcpmFieldAt(sequence, clock) !== null) before += 1;
      if (dgcpmFieldAt(sequence, clock, clock) !== null) after += 1;
    }
    expect(before).toBe(61);
    expect(after).toBe(121);
  });
});

describe("an empty ring current says which of the two things is wrong", () => {
  const sequence = decodeDgcpmSequence(bundle);
  const NEWEST_MS = Date.parse("2026-08-09T02:00:00Z");
  const notice = (selectedMs: number, nowMs: number) => dgcpmCoverageNotice({
    title: "Ring current",
    selectedAtMs: selectedMs,
    nowMs,
    frameTimesMs: sequence.times,
    cadenceMinutes: sequence.cadenceMinutes,
  });

  it("says nobody forecasts it when the reader has scrubbed forward", () => {
    const because = notice(NEWEST_MS + 6 * 60 * 60_000, NEWEST_MS + 30 * 60_000)!.because;
    expect(because).toContain("nobody publishes a forecast");
    // The old sentence promised a frame that is coming. Nothing is coming.
    expect(because).not.toContain("has not arrived yet");
  });

  it("says the replacement is overdue when the feed is late", () => {
    const late = NEWEST_MS + 5 * 60 * 60_000;
    const because = notice(late, late)!.because;
    expect(because).toContain("overdue");
    expect(because).toContain("2026-08-09 02:00 UTC");
    expect(because).not.toContain("nobody publishes a forecast");
  });

  it("offers a landing inside the window it can actually draw", () => {
    const late = NEWEST_MS + 5 * 60 * 60_000;
    const landing = Date.parse(notice(late, late)!.jumpToIso!);
    const held = dgcpmFieldAt(sequence, new Date(landing), new Date(landing));
    expect(held).not.toBeNull();
  });

  it("names the hole rather than the edge when the gap is an internal one", () => {
    const insideGap = Date.parse("2026-08-07T18:00:00Z") + 12 * 60 * 60_000;
    const because = notice(insideGap, NEWEST_MS + 30 * 60_000)!.because;
    expect(because).toContain("hole in its plasmasphere frames");
  });

  it("stays quiet when the frames do cover the instant", () => {
    expect(notice(NEWEST_MS + 30 * 60_000, NEWEST_MS + 30 * 60_000)).toBeNull();
  });
});

/**
 * A LAYER STILL FETCHING ITS ARTIFACT IS NOT A LAYER WITH NO DATA.
 *
 * `landOnCoverage` answers a no-data layer by seeking the reader's clock back
 * into that layer's window and holding it there, and it waits only on a layer
 * that says "loading". The ring current said "no-data" for the second or two
 * its DGCPM fetch takes, so switching it on at live now moved the clock back
 * to a minute inside the manifest's window and paused it there — one minute
 * BEFORE the newest published frame, which is not a nowcast and carries no
 * age. Measured on the built bundle before this line existed.
 */
describe("the ring current says loading while its artifact is in flight", () => {
  it("is loading before the bundle arrives and no-data only once it has", () => {
    expect(ringCurrentLegendSpec(null, "not-loaded").statusState).toBe("loading");
    // The frames are in hand and genuinely do not reach the instant. That is a
    // real refusal and keeps every no-data behaviour, jump button included.
    expect(ringCurrentLegendSpec(null, "outside-window").statusState).toBe("no-data");
    expect(ringCurrentLegendSpec(null, "load-failed").statusState).toBe("no-data");
    expect(ringCurrentLegendSpec(null, "not-published").statusState).toBe("no-data");
  });
});
