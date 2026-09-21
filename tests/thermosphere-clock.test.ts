import { describe, expect, test } from "vitest";

import {
  THERMOSPHERE_DISPLAY_LOG10,
  bakeThermosphereVolume,
} from "../src/thermosphere-volume";
import {
  selectThermosphereFrame,
  type DecodedFrame,
  type ThermosphereFrame,
} from "../src/thermosphere";

/**
 * The thermosphere layer has been reported static four times and declared
 * fixed twice. Both of those all-clears came from reading pixels, and all three
 * readings were invalid: a crop that included the globe changed because the
 * Earth turns with the clock; a crop outside the glow was identical black in
 * every frame; and a `canvas.getImageData` readback after `drawImage` measured
 * nothing at all, because the WebGL context is not created with
 * `preserveDrawingBuffer` and the readback is entirely black.
 *
 * So this file deliberately does NOT assert on pixels. It asserts on the two
 * things a rotating picture and a badly chosen crop cannot fake:
 *
 *   - WHICH FRAME is chosen for an instant, including the instants where the
 *     honest answer is "none";
 *   - whether the BAKED TEXTURE responds to more air, which is the physical
 *     change the layer exists to show.
 *
 * The browser-level half of this — that the frame identity on screen changes
 * with the clock and matches the selected time — is `thermosphere-clock.spec.ts`.
 */

function frameAt(validAt: string): ThermosphereFrame {
  return {
    validAt,
    grid: { altitudeKm: [120], latitudeDeg: [0], longitudeDeg: [0] },
    encoding: { bits: 8, logFloor: -17, logCeiling: -5.5, quantumDex: 0.045 },
    codes: "",
    codesDtype: "uint8",
    validMask: "",
    validFraction: 1,
  };
}

const HOURLY = {
  cadenceMinutes: 60,
  frames: ["2026-08-19T18:40:00Z", "2026-08-19T19:40:00Z", "2026-08-19T20:40:00Z"].map(frameAt),
};

describe("choosing the frame for an instant", () => {
  test("picks the nearest published frame inside the window", () => {
    expect(selectThermosphereFrame(HOURLY, new Date("2026-08-19T19:41:00Z"))?.validAt)
      .toBe("2026-08-19T19:40:00Z");
    // Nearest, not first: the bug this layer shipped with was a card that
    // quoted frames[0] forever, which reads exactly like a static layer.
    expect(selectThermosphereFrame(HOURLY, new Date("2026-08-19T20:20:00Z"))?.validAt)
      .toBe("2026-08-19T20:40:00Z");
  });

  test("half a cadence is the edge, and it is inclusive", () => {
    expect(selectThermosphereFrame(HOURLY, new Date("2026-08-19T18:10:00Z"))?.validAt)
      .toBe("2026-08-19T18:40:00Z");
    expect(selectThermosphereFrame(HOURLY, new Date("2026-08-19T18:09:59Z"))).toBeNull();
  });

  /**
   * The one that matters. The timeline reaches 48 hours back and 72 forward and
   * a WAM release covers five or six, so this branch is what a reader meets
   * across roughly 95% of the slider. Returning the nearest frame anyway — or,
   * as the caller used to, returning early and leaving the previous frame drawn
   * — is a picture that claims to be an hour it is not.
   */
  test("outside the published window there is no frame, not the closest one", () => {
    expect(selectThermosphereFrame(HOURLY, new Date("2026-08-19T06:00:00Z"))).toBeNull();
    expect(selectThermosphereFrame(HOURLY, new Date("2026-08-21T12:00:00Z"))).toBeNull();
    expect(selectThermosphereFrame({ cadenceMinutes: 60, frames: [] }, new Date())).toBeNull();
  });
});

/**
 * A uniform column, so a "storm" is exactly one thing: more air everywhere.
 * Density falls one decade per 150 km, which is the right order for the real
 * thermosphere and keeps the expected byte values checkable by hand.
 */
function uniformFrame(liftDex: number): DecodedFrame {
  const altitudeKm = new Float64Array([120, 300, 500, 700, 1000]);
  const latitudeDeg = new Float64Array([-90, -45, 0, 45, 90]);
  const longitudeDeg = new Float64Array([0, 90, 180, 270]);
  const logDensity = new Float64Array(altitudeKm.length * latitudeDeg.length * longitudeDeg.length);
  let index = 0;
  for (let a = 0; a < altitudeKm.length; a += 1) {
    for (let b = 0; b < latitudeDeg.length; b += 1) {
      for (let c = 0; c < longitudeDeg.length; c += 1) {
        // A day/night bulge, so the anomaly channel has something real to
        // carry and this is not a degenerate field.
        const bulge = 0.2 * Math.cos((longitudeDeg[c]! * Math.PI) / 180);
        logDensity[index] = -8 - (altitudeKm[a]! - 120) / 150 + bulge + liftDex;
        index += 1;
      }
    }
  }
  return { validAt: "2026-08-19T18:40:00Z", altitudeKm, latitudeDeg, longitudeDeg, logDensity };
}

describe("the bake has to be able to show a storm", () => {
  const options = { earthSceneRadius: 100, altitudeSlabs: 24, longitudeCount: 24, latitudeCount: 12 };

  test("the display scale is fixed, so the same density is the same byte at every hour", () => {
    const quiet = bakeThermosphereVolume(uniformFrame(0), options);
    const storm = bakeThermosphereVolume(uniformFrame(0.3), options);
    expect(quiet.logFloor).toBe(THERMOSPHERE_DISPLAY_LOG10.floor);
    expect(quiet.logCeiling).toBe(THERMOSPHERE_DISPLAY_LOG10.ceiling);
    expect(storm.logFloor).toBe(quiet.logFloor);
    expect(storm.logCeiling).toBe(quiet.logCeiling);
  });

  /**
   * The regression this file exists for. `bakeThermosphereVolume` used to
   * normalise each frame against its OWN minimum and maximum log density and
   * stretch that to fill the byte range. Under that rule the two bakes below
   * are byte-for-byte identical: the stretch cancels the lift exactly. Thirteen
   * hourly frames drew one picture, and every report of "the thermosphere is
   * static" was literally correct about the pixels.
   */
  test("more air everywhere is more opacity everywhere", () => {
    const quiet = bakeThermosphereVolume(uniformFrame(0), options);
    const storm = bakeThermosphereVolume(uniformFrame(0.3), options);
    const span = THERMOSPHERE_DISPLAY_LOG10.ceiling - THERMOSPHERE_DISPLAY_LOG10.floor;
    // 0.3 dex on an 8.4 dex display range is 9.1 byte codes. Asserted as a
    // range rather than an exact value because the sample grid is resampled.
    const expected = (0.3 / span) * 255;
    let compared = 0;
    for (let index = 0; index < quiet.data.length; index += 2) {
      const before = quiet.data[index]!;
      const after = storm.data[index]!;
      if (before === 0 || before === 255 || after === 255) continue;
      expect(after).toBeGreaterThan(before);
      expect(after - before).toBeGreaterThan(expected - 2);
      expect(after - before).toBeLessThan(expected + 2);
      compared += 1;
    }
    // A test that compared nothing would pass silently — the empty-crop
    // mistake, in unit-test form.
    expect(compared).toBeGreaterThan(1000);
  });

  /**
   * And the other half of the honest answer, asserted rather than assumed.
   *
   * The green channel is the per-altitude-slab anomaly and it drives COLOUR. It
   * is deliberately relative, because that is what makes the day/night bulge
   * legible against a field that falls 6.7 decades with height. The cost is
   * exact: a change that lifts a whole slab by the same amount cancels in it,
   * so colour alone can never show a storm. Opacity is the channel that has to
   * carry that, which is why the fixed display range above is not optional.
   */
  test("the colour channel cannot show a uniform lift, by construction", () => {
    const quiet = bakeThermosphereVolume(uniformFrame(0), options);
    const storm = bakeThermosphereVolume(uniformFrame(0.3), options);
    let compared = 0;
    let worst = 0;
    for (let index = 1; index < quiet.data.length; index += 2) {
      worst = Math.max(worst, Math.abs(storm.data[index]! - quiet.data[index]!));
      compared += 1;
    }
    // One code, not zero, and only from rounding the slab normalisation at a
    // shifted origin. Against the opacity channel's nine codes for the same
    // lift, that is the cancellation stated as a measurement.
    expect(worst).toBeLessThanOrEqual(1);
    expect(compared).toBeGreaterThan(1000);
  });
});
