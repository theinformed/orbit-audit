import { describe, expect, it } from "vitest";
import events from "../data/events.json";
import {
  INJECTION_REFERENCE_DROP_NT,
  LOADING_REFERENCE_NT_MINUTES,
  SUBSTORM_ONSET_CRITERION,
  detectRingCurrentInjections,
  detectSubstormOnsets,
  southwardBzIntegral,
  substormStateAt,
} from "../src/substorm-chain";
import type { IndexSample } from "../src/substorm-chain";

/**
 * The real May 2024 Gannon SuperMAG SML record the events bundle carries: 720
 * samples at 10 minutes over 120 hours. This is the series the criterion is
 * argued against, and running the detector on it is the whole point — a
 * criterion tuned only against synthetic steps proves nothing about a storm.
 */
const gannon = (events as { events: Array<Record<string, any>> }).events
  .find((event) => event.id === "gannon-2024")!;
const replayStartMs = Date.parse(gannon.replay.startsAt as string);
const sml: IndexSample[] = (gannon.replay.driver.points as Array<[number, number]>)
  .map(([hours, valueNt]) => ({ atMs: replayStartMs + hours * 3_600_000, valueNt }));

describe("substorm onset criterion, on the record it will actually run on", () => {
  it("reads the Gannon SML series the events bundle publishes", () => {
    expect(sml).toHaveLength(720);
    // 10-minute cadence, and the hours column is rounded to three decimals, so
    // the sample spacing is 600 s to within a couple of seconds rather than
    // exactly 600. A criterion stated in minutes has to tolerate that.
    expect((sml[1]!.atMs - sml[0]!.atMs) / 60_000).toBeCloseTo(10, 1);
    expect(gannon.replay.driver.peak).toBeCloseTo(-4057.6, 1);
    expect(gannon.replay.driver.peakAt).toBe("2024-05-10T19:48:00Z");
  });

  it("finds the storm's substorms, and the deepest drop is the one the storm is known for", () => {
    const onsets = detectSubstormOnsets(sml);
    // Measured on this record with the shipped thresholds. Pinned as a range
    // rather than a single number so a cadence change does not fail this for
    // the wrong reason, but tight enough that a broken criterion cannot pass.
    expect(onsets.length).toBeGreaterThanOrEqual(30);
    expect(onsets.length).toBeLessThanOrEqual(50);

    const deepest = onsets.reduce((best, onset) => (onset.dropNt > best.dropNt ? onset : best));
    expect(deepest.dropNt).toBeGreaterThan(2000);
    expect(deepest.minimumNt).toBeLessThan(-3000);

    // Every onset obeys all three rules.
    for (let index = 0; index < onsets.length; index += 1) {
      expect(onsets[index]!.dropNt).toBeGreaterThanOrEqual(SUBSTORM_ONSET_CRITERION.minimumDropNt);
      if (index > 0) {
        const gapMinutes = (onsets[index]!.atMs - onsets[index - 1]!.atMs) / 60_000;
        expect(gapMinutes).toBeGreaterThanOrEqual(SUBSTORM_ONSET_CRITERION.refractoryMinutes);
      }
    }
  });

  it("does not fire on a quiet index, and stays sane where the storm has not arrived", () => {
    // A flat index has no onsets. This is the floor: a criterion that fires
    // here is measuring its own arithmetic.
    const flat: IndexSample[] = Array.from({ length: 200 }, (_, index) => ({
      atMs: replayStartMs + index * 600_000,
      valueNt: -30,
    }));
    expect(detectSubstormOnsets(flat)).toHaveLength(0);

    // Noise that never falls far enough has none either.
    const wobble: IndexSample[] = Array.from({ length: 200 }, (_, index) => ({
      atMs: replayStartMs + index * 600_000,
      valueNt: -30 + 40 * Math.sin(index / 3),
    }));
    expect(detectSubstormOnsets(wobble)).toHaveLength(0);

    // The first 24 hours of the real record, before the storm: the index only
    // ever reaches -260 nT, and the criterion reports a handful of ordinary
    // small substorms rather than a storm. Quiet days DO have substorms, so
    // the honest expectation is "a few", not "none".
    const preStorm = sml.filter((sample) => sample.atMs < replayStartMs + 24 * 3_600_000);
    const values = preStorm.map((sample) => sample.valueNt as number);
    expect(Math.min(...values)).toBeGreaterThan(-400);
    const quietOnsets = detectSubstormOnsets(preStorm);
    expect(quietOnsets.length).toBeGreaterThanOrEqual(1);
    expect(quietOnsets.length).toBeLessThanOrEqual(6);
    for (const onset of quietOnsets) expect(onset.dropNt).toBeLessThan(400);
  });

  it("reports the START of an expansion, not every sample on the way down", () => {
    // Rule 2. A single monotone 600 nT collapse over two hours is ONE onset.
    // Without the "was it already falling" guard it reports as a run of them.
    const collapse: IndexSample[] = Array.from({ length: 40 }, (_, index) => ({
      atMs: replayStartMs + index * 600_000,
      valueNt: index < 6 ? -20 : Math.max(-620, -20 - (index - 6) * 50),
    }));
    const onsets = detectSubstormOnsets(collapse);
    expect(onsets).toHaveLength(1);
    // And it is the first sample of the fall, not the bottom of it.
    expect(onsets[0]!.indexNt).toBeGreaterThan(-120);
    expect(onsets[0]!.minimumNt).toBeLessThan(-300);
  });
});

describe("what the site knows about the onset time, and what it refuses to claim", () => {
  it("draws no injection at all when no electrojet index covers the instant", () => {
    // This is the live case: there is no auroral-electrojet index in any feed
    // this site fetches, and SuperMAG's mirror here covers one week in 2024.
    // The layer must therefore not draw the sheet snapping.
    const bz: IndexSample[] = Array.from({ length: 40 }, (_, index) => ({
      atMs: replayStartMs + index * 300_000,
      valueNt: -8,
    }));
    const state = substormStateAt({ bz }, replayStartMs + 39 * 300_000);
    expect(state.onsetEvidence).toBe("none");
    expect(state.injection).toBe(0);
    expect(state.onset).toBeNull();
    // But the LOADING is measured and is drawn, because Bz is measured.
    expect(state.loading).toBeGreaterThan(0.9);
    expect(state.phase).toBe("growth");
  });

  it("labels a Dst-derived episode as a ring-current response, never as an onset", () => {
    const dst: IndexSample[] = Array.from({ length: 24 }, (_, index) => ({
      atMs: replayStartMs + index * 3_600_000,
      valueNt: index < 6 ? -10 : Math.max(-120, -10 - (index - 6) * 12),
    }));
    const episodes = detectRingCurrentInjections(dst);
    expect(episodes.length).toBeGreaterThanOrEqual(1);
    const state = substormStateAt({ bz: [], dst }, replayStartMs + 12 * 3_600_000);
    expect(state.onsetEvidence).toBe("ring-current-response");
    // An electrojet series, where present, always wins.
    const withSml = substormStateAt({ bz: [], dst, electrojet: sml }, Date.parse("2024-05-11T09:00:00Z"));
    expect(withSml.onsetEvidence).toBe("observed-electrojet");
  });

  it("measures loading as the southward-Bz integral, and reports null where nothing is measured", () => {
    const bz: IndexSample[] = Array.from({ length: 40 }, (_, index) => ({
      atMs: replayStartMs + index * 300_000,
      valueNt: -5,
    }));
    // 90 minutes of -5 nT is 450 nT-minutes, which is the reference.
    const integral = southwardBzIntegral(bz, replayStartMs + 39 * 300_000);
    expect(integral).toBeCloseTo(LOADING_REFERENCE_NT_MINUTES, -1);

    // Northward Bz contributes nothing rather than unloading.
    const north = bz.map((sample) => ({ ...sample, valueNt: 5 }));
    expect(southwardBzIntegral(north, replayStartMs + 39 * 300_000)).toBe(0);

    // Forward of the record there is no measurement, and that is not zero.
    expect(southwardBzIntegral(bz, replayStartMs + 40 * 86_400_000)).toBeNull();
    const unmeasured = substormStateAt({ bz }, replayStartMs + 40 * 86_400_000);
    expect(unmeasured.southwardBzNtMinutes).toBeNull();
    // And an unmeasured window draws NOTHING, rather than drawing a loaded
    // tail by default. This is the assertion that catches a hard-coded load.
    expect(unmeasured.loading).toBe(0);
    expect(unmeasured.phase).toBe("quiet");

    // Loading is proportional to the measured integral, not a flag. Half the
    // reference southward field is half the load, and northward is none.
    const half = substormStateAt(
      { bz: bz.map((sample) => ({ ...sample, valueNt: -2.5 })) },
      replayStartMs + 39 * 300_000,
    );
    expect(half.loading).toBeGreaterThan(0.4);
    expect(half.loading).toBeLessThan(0.6);
    expect(substormStateAt({ bz: north }, replayStartMs + 39 * 300_000).loading).toBe(0);
  });

  it("scales the drawn injection by how hard the measured onset actually was", () => {
    const small = substormStateAt(
      { bz: [], electrojet: [
        { atMs: replayStartMs, valueNt: -20 },
        { atMs: replayStartMs + 600_000, valueNt: -140 },
        { atMs: replayStartMs + 1_200_000, valueNt: -150 },
        { atMs: replayStartMs + 1_800_000, valueNt: -140 },
      ] },
      replayStartMs + 600_000,
    );
    const big = substormStateAt({ bz: [], electrojet: sml }, Date.parse("2024-05-11T08:50:00Z"));
    expect(small.injection).toBeGreaterThan(0);
    expect(big.injection).toBeGreaterThan(small.injection);
    // A drop at or past the reference saturates rather than running away.
    expect(big.injection).toBeLessThanOrEqual(1);
    expect(INJECTION_REFERENCE_DROP_NT).toBeGreaterThan(0);
  });
});
