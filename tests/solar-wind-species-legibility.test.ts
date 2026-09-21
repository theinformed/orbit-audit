/**
 * The species palette has to stay legible, and that is arithmetic, not taste.
 *
 * Three species are drawn in one shower and the reader has to be able to tell
 * them apart — including a reader who cannot use the hue. That claim was
 * measured once, in the commit that chose the colours, and a number in a
 * commit message is not a guard: the next well-meaning change to
 * `SOLAR_WIND_SPECIES_PRESENTATION` can quietly put two species back in one
 * family and nothing would say so. The scheme this file guards had exactly
 * that defect before it was fixed — H⁺ against He²⁺ sat 13.7 apart under
 * simulated deuteranopia, which is the arithmetic of why nobody could see the
 * split the transport goes to the trouble of drawing.
 *
 * So the separation is asserted here instead, and asserted in the vision types
 * it actually has to survive. Nothing below names a colour: swap the palette
 * for a different one and these tests still say whether it is legible.
 *
 * Two invariants:
 *
 *   1. EVERY PAIR OF SPECIES separates in normal vision AND in simulated
 *      protanopia, deuteranopia and tritanopia. Measured on the shipped
 *      palette the worst pair is 37.5 (H⁺/He²⁺ under deuteranopia) against a
 *      floor of 25, so there is real headroom; the floor is set below the
 *      measurement on purpose, because this is a guard against a family
 *      collapse, not a lock on one particular set of hex values.
 *
 *   2. The ELECTRON stays away from the X-ray layer's photon streaks. That
 *      layer's whole teaching point is that light does not deflect and
 *      everything in this shower does. An electron that looked like a photon
 *      would undo it. Measured worst case 24.2, under tritanopia, against a
 *      floor of 18.
 *
 * The distance is plain CIELAB ΔE (D65), and the dichromat simulation is
 * Viénot, Brettel & Mollon (1999) in LMS. Neither is exotic and both are
 * short enough to read, which is why they are written out here rather than
 * pulled in: a test nobody can check is not evidence either.
 */
import { describe, expect, it } from "vitest";
import {
  SOLAR_WIND_ALPHA_LUMINANCE_GAIN,
  SOLAR_WIND_SPECIES_PRESENTATION,
  XRAY_PHOTON_STREAK_COLOR_HEX,
  type SolarWindSpecies,
} from "../src/solar-input-visuals";

type Triple = [number, number, number];

const toLinear = (channel: number) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
const toSrgb = (channel: number) => channel <= 0.0031308 ? 12.92 * channel : 1.055 * Math.max(channel, 0) ** (1 / 2.4) - 0.055;

function hexToLinear(hex: string): Triple {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((offset) => toLinear(parseInt(value.slice(offset, offset + 2), 16) / 255)) as Triple;
}

/** Linear sRGB → CIELAB, D65. */
function toLab(linear: Triple): Triple {
  const [r, g, b] = linear;
  const x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375;
  const y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750;
  const z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041;
  const f = (t: number) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;
  const [fx, fy, fz] = [f(x / 0.95047), f(y), f(z / 1.08883)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

const RGB_TO_LMS = [
  [0.31399022, 0.63951294, 0.04649755],
  [0.15537241, 0.75789446, 0.08670142],
  [0.01775239, 0.10944209, 0.87256922],
];
const LMS_TO_RGB = [
  [5.47221206, -4.6419601, 0.16963708],
  [-1.1252419, 2.29317094, -0.1678952],
  [0.02980165, -0.19318073, 1.16364789],
];
/** Viénot, Brettel & Mollon (1999) dichromat projections in LMS. */
const DICHROMAT: Record<string, number[][]> = {
  protanopia: [[0, 1.05118294, -0.05116099], [0, 1, 0], [0, 0, 1]],
  deuteranopia: [[1, 0, 0], [0.9513092, 0, 0.04866992], [0, 0, 1]],
  tritanopia: [[1, 0, 0], [0, 1, 0], [-0.86744736, 1.86727089, 0]],
};
const apply = (matrix: number[][], v: Triple): Triple =>
  matrix.map((row) => row[0]! * v[0] + row[1]! * v[1] + row[2]! * v[2]) as Triple;

/** The colour as a reader of the named vision type sees it, in CIELAB. */
function seenAs(hex: string, vision: string): Triple {
  const linear = hexToLinear(hex);
  if (vision === "normal") return toLab(linear);
  const projected = apply(LMS_TO_RGB, apply(DICHROMAT[vision]!, apply(RGB_TO_LMS, linear)));
  // Back through the sRGB transfer and in again, so out-of-gamut projections
  // are clamped the way a screen clamps them rather than scored as if a
  // monitor could show them.
  const clamped = projected.map((c) => toLinear(toSrgb(Math.min(1, Math.max(0, c))))) as Triple;
  return toLab(clamped);
}

const distance = (a: Triple, b: Triple) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

const VISION = ["normal", "protanopia", "deuteranopia", "tritanopia"] as const;
const SPECIES = Object.keys(SOLAR_WIND_SPECIES_PRESENTATION) as SolarWindSpecies[];
const PAIRS: Array<[SolarWindSpecies, SolarWindSpecies]> = [];
for (let i = 0; i < SPECIES.length; i += 1) {
  for (let j = i + 1; j < SPECIES.length; j += 1) PAIRS.push([SPECIES[i]!, SPECIES[j]!]);
}

/** Below about 15, two colours read as the same colour. 25 is a real gap. */
const SPECIES_FLOOR = 25;
/** The electron against the photons is a softer requirement: it only has to be visibly not-that. */
const PHOTON_FLOOR = 18;

describe("the species palette stays legible", () => {
  for (const vision of VISION) {
    for (const [a, b] of PAIRS) {
      it(`separates ${SOLAR_WIND_SPECIES_PRESENTATION[a].symbol} from ${SOLAR_WIND_SPECIES_PRESENTATION[b].symbol} in ${vision}`, () => {
        const measured = distance(
          seenAs(SOLAR_WIND_SPECIES_PRESENTATION[a].colorHex, vision),
          seenAs(SOLAR_WIND_SPECIES_PRESENTATION[b].colorHex, vision),
        );
        expect(measured, `${a} vs ${b} in ${vision} is ΔE ${measured.toFixed(1)}`).toBeGreaterThan(SPECIES_FLOOR);
      });
    }
  }

  for (const vision of VISION) {
    it(`keeps the electron from looking like an X-ray photon in ${vision}`, () => {
      const measured = distance(
        seenAs(SOLAR_WIND_SPECIES_PRESENTATION.electron.colorHex, vision),
        seenAs(XRAY_PHOTON_STREAK_COLOR_HEX, vision),
      );
      expect(measured, `electron vs photon streak in ${vision} is ΔE ${measured.toFixed(1)}`).toBeGreaterThan(PHOTON_FLOOR);
    });
  }

  it("carries mass on a second channel, so the split never rests on hue alone", () => {
    // An alpha is four proton masses and an electron is next to nothing. The
    // sizes have to say so, or a reader who cannot use the hue at all has
    // nothing left. This is the negative control for the tests above: they
    // would all still pass on a palette that had thrown the size channel away.
    const { proton, alpha, electron } = SOLAR_WIND_SPECIES_PRESENTATION;
    expect(alpha.pointScale).toBeGreaterThan(proton.pointScale);
    expect(proton.pointScale).toBeGreaterThan(electron.pointScale);
    expect(alpha.pointScale / electron.pointScale).toBeGreaterThan(1.5);
  });

  /**
   * ## THE SAME MEASUREMENT, ON THE COLOUR THAT REACHES THE SCREEN
   *
   * The tests above score the hex codes. The shader does not draw the hex
   * codes: it draws them through `SOLAR_WIND_ALPHA_LUMINANCE_GAIN`, which
   * multiplies the rare species' opacity so its glyph emits as much light as
   * the anchor's. On an additive sky that is a multiply in LINEAR light, and a
   * multiply in linear light CLIPS — past the top of the gamut a dark
   * saturated colour loses its hue toward white.
   *
   * That matters more than it sounds, and it was found the hard way while the
   * palette was being moved back into gold on 2026-08-27: the correction
   * removes LIGHTNESS as a channel by construction, so whatever separation the
   * palette had in L* is not there on screen. A palette can pass every test
   * above and still draw as two colours. So it is scored again, as drawn.
   */
  const drawnAs = (species: SolarWindSpecies) => {
    const hex = SOLAR_WIND_SPECIES_PRESENTATION[species].colorHex;
    const gain = species === "alpha" ? SOLAR_WIND_ALPHA_LUMINANCE_GAIN : 1;
    const scaled = hexToLinear(hex).map((channel) => Math.min(1, Math.max(0, channel * gain)));
    return "#" + scaled
      .map((channel) => Math.round(toSrgb(channel) * 255).toString(16).padStart(2, "0"))
      .join("");
  };

  for (const vision of VISION) {
    for (const [a, b] of PAIRS) {
      it(`separates ${SOLAR_WIND_SPECIES_PRESENTATION[a].symbol} from ${SOLAR_WIND_SPECIES_PRESENTATION[b].symbol} AS DRAWN in ${vision}`, () => {
        const measured = distance(seenAs(drawnAs(a), vision), seenAs(drawnAs(b), vision));
        expect(measured, `${a} vs ${b} as drawn in ${vision} is ΔE ${measured.toFixed(1)}`)
          .toBeGreaterThan(SPECIES_FLOOR);
      });
    }
  }

  it("scores a gain aimed at the BRIGHTEST species as illegible, so the anchor rule is known to bite", () => {
    // The negative control for the target of the correction. Lifting the
    // indigo to the pale cream electron rather than to the amber anchor is a
    // gain of 4.4 instead of 2.6, and it washes the indigo out until it scores
    // 14.6 against the amber under tritanopia. If a future edit ever makes
    // that pass, `SOLAR_WIND_ALPHA_LUMINANCE_GAIN`'s target has stopped
    // meaning anything.
    const luminance = (hex: string) => {
      const [r, g, b] = hexToLinear(hex);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const { proton, alpha, electron } = SOLAR_WIND_SPECIES_PRESENTATION;
    const brightest = Math.max(luminance(proton.colorHex), luminance(electron.colorHex));
    const overGain = brightest / luminance(alpha.colorHex);
    expect(overGain).toBeGreaterThan(SOLAR_WIND_ALPHA_LUMINANCE_GAIN * 1.4);
    const washed = hexToLinear(alpha.colorHex).map((channel) => Math.min(1, channel * overGain));
    const washedHex = "#" + washed
      .map((channel) => Math.round(toSrgb(channel) * 255).toString(16).padStart(2, "0"))
      .join("");
    const worst = Math.min(...VISION.flatMap((vision) => [
      distance(seenAs(washedHex, vision), seenAs(proton.colorHex, vision)),
      distance(seenAs(washedHex, vision), seenAs(electron.colorHex, vision)),
    ]));
    expect(worst).toBeLessThan(SPECIES_FLOOR);
  });

  it("scores the family it replaced as illegible, so the floor is known to bite", () => {
    // The negative control. All three species used to sit in the amber family
    // (#f2a648 / #e06d1f / #ffe4ab) and the H⁺/He²⁺ pair measured 13.7 under
    // deuteranopia. If a future edit ever makes that palette pass, the floor
    // above has stopped meaning anything.
    const wasIllegible = distance(seenAs("#f2a648", "deuteranopia"), seenAs("#e06d1f", "deuteranopia"));
    expect(wasIllegible).toBeLessThan(SPECIES_FLOOR);
  });
});
