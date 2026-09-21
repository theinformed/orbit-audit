import { describe, expect, it } from "vitest";

import {
  RADIATION_VOLUME_COLOR_HEX,
  RADIATION_VOLUME_RAMP_TEXELS,
  RADIATION_VOLUME_TRANSFER,
  radiationRampTexels,
} from "../src/radiation-belt-volume";

/**
 * The belt palette is pinned by what it has to DO, not by its hex codes, so a
 * later hand can restyle it freely and still be stopped from reintroducing the
 * defect it was built to remove.
 *
 * That defect: the four stops this replaced ran dark navy, purple, orange,
 * cream, and purple to orange is one straight interpolation between two nearly
 * opposite hues, so it passed close to grey. The inner belt — the single most
 * important feature in the picture — landed in the trough at 48% of the ramp
 * and rendered #976980, a washed mauve, with a vivid slot on one side and a
 * vivid outer belt on the other. Separation was never the problem; the three
 * features were already dE 42 apart. Dullness was.
 */

const CHANNEL_MAXIMUM = 255;

/** sRGB byte triple to CIE Lab, D65. Local to the test on purpose: the thing
 *  under test is the palette, so the yardstick must not come from the palette's
 *  own module. */
function lab(bytes: readonly [number, number, number]): [number, number, number] {
  const linear = bytes.map((byte) => {
    const channel = byte / CHANNEL_MAXIMUM;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  const [r, g, b] = linear;
  const x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047;
  const y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750;
  const z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883;
  const f = (value: number) => (value > 216 / 24389 ? Math.cbrt(value) : (841 / 108) * value + 4 / 29);
  const [fx, fy, fz] = [f(x), f(y), f(z)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

const chroma = (value: readonly number[]) => Math.hypot(value[1]!, value[2]!);
const distance = (a: readonly number[], b: readonly number[]) =>
  Math.hypot(a[0]! - b[0]!, a[1]! - b[1]!, a[2]! - b[2]!);

const texels = radiationRampTexels();

/** The colour the shader's lookup holds at a fraction of the displayed range. */
function colourAt(position: number): [number, number, number] {
  const index = Math.round(position * (RADIATION_VOLUME_RAMP_TEXELS - 1));
  return [texels[index * 4]!, texels[index * 4 + 1]!, texels[index * 4 + 2]!];
}

/** Where a log10 flux sits along the ramp. */
function positionOf(log10Flux: number): number {
  const { colourFloorLog10Flux: floor, colourCeilingLog10Flux: ceiling } = RADIATION_VOLUME_TRANSFER;
  return (log10Flux - floor) / (ceiling - floor);
}

/** Occupied maxima measured from the loaded fields, quoted in the module. */
const FEATURES = [
  { name: "the slot", log10Flux: 2.62 },
  { name: "the inner belt", log10Flux: 3.18 },
  { name: "the outer belt", log10Flux: 3.65 },
] as const;

describe("the radiation belt colour ramp", () => {
  it("holds every declared stop exactly, with no rounding", () => {
    expect(texels).toHaveLength(RADIATION_VOLUME_RAMP_TEXELS * 4);
    RADIATION_VOLUME_COLOR_HEX.forEach((hex, index) => {
      const position = index / (RADIATION_VOLUME_COLOR_HEX.length - 1);
      const [red, green, blue] = colourAt(position);
      const rendered = `#${[red, green, blue]
        .map((channel) => channel.toString(16).padStart(2, "0"))
        .join("")}`;
      expect(rendered).toBe(hex);
    });
  });

  it("is fully opaque, so the transfer function alone decides what shows through", () => {
    for (let index = 0; index < RADIATION_VOLUME_RAMP_TEXELS; index += 1) {
      expect(texels[index * 4 + 3]).toBe(255);
    }
  });

  it("keeps the endpoints every other page quotes", () => {
    expect(RADIATION_VOLUME_COLOR_HEX[0]).toBe("#181436");
    expect(RADIATION_VOLUME_COLOR_HEX[RADIATION_VOLUME_COLOR_HEX.length - 1]).toBe("#fff0cf");
  });

  it("never dips in lightness by anything a reader could see", () => {
    // A sequential ramp that goes darker as the value rises draws a boundary
    // that is not in the data — a reader sees an edge where the flux is smooth.
    //
    // Not "never dips at all", because the lookup is 8-bit and the three
    // channels round independently, so a stop boundary can lose a hundredth of
    // an L*. Measured on this palette: two such steps, 0.013 and 0.054 L*,
    // against a total rise of 86.5 and a single 8-bit step of 0.39 L* near
    // mid-grey. The threshold sits under one quantisation step, so rounding
    // noise passes and a ramp that genuinely turns over — which costs whole
    // L* units — still fails.
    const INVISIBLE_L = 0.2;
    let previous = -Infinity;
    let worst = 0;
    let worstAt = 0;
    for (let index = 0; index < RADIATION_VOLUME_RAMP_TEXELS; index += 1) {
      const lightness = lab(colourAt(index / (RADIATION_VOLUME_RAMP_TEXELS - 1)))[0];
      if (previous - lightness > worst) {
        worst = previous - lightness;
        worstAt = index;
      }
      previous = lightness;
    }
    expect(worst, `largest drop ${worst.toFixed(4)} L* at texel ${worstAt}`)
      .toBeLessThan(INVISIBLE_L);
    expect(lab(colourAt(0))[0]).toBeLessThan(15);
    expect(lab(colourAt(1))[0]).toBeGreaterThan(90);
  });

  it("does not pass through grey where the belts actually live", () => {
    // 10^2 to 10^4 is where the loaded fields sit. The retired ramp troughed at
    // chroma 21 inside this span and put the inner belt in the trough.
    const from = positionOf(2);
    const to = positionOf(4);
    let trough = Infinity;
    let troughAt = 0;
    for (let step = 0; step <= 200; step += 1) {
      const position = from + ((to - from) * step) / 200;
      const value = chroma(lab(colourAt(position)));
      if (value < trough) {
        trough = value;
        troughAt = position;
      }
    }
    expect(trough, `trough ${trough.toFixed(1)} at ${(troughAt * 100).toFixed(0)}% of the ramp`)
      .toBeGreaterThan(40);
  });

  it("draws no feature markedly duller than its neighbours", () => {
    // The specific failure being guarded: it is not enough for the ramp to be
    // colourful on average. The inner belt sat between two vivid neighbours at
    // a third of their chroma, so it read as faded rather than as different.
    const chromas = FEATURES.map((feature) => ({
      name: feature.name,
      value: chroma(lab(colourAt(positionOf(feature.log10Flux)))),
    }));
    const weakest = chromas.reduce((low, entry) => (entry.value < low.value ? entry : low));
    const strongest = chromas.reduce((high, entry) => (entry.value > high.value ? entry : high));
    expect(
      weakest.value / strongest.value,
      `${weakest.name} is the dullest at chroma ${weakest.value.toFixed(1)} against `
        + `${strongest.name} at ${strongest.value.toFixed(1)}`,
    ).toBeGreaterThan(0.6);
  });

  it("still tells the three features apart", () => {
    // Guards the other direction: a ramp could hold its chroma by flattening the
    // features together, which would be a worse picture, not a better one.
    // About 2.3 is a just-noticeable difference and 10 reads as another colour.
    for (let i = 0; i < FEATURES.length; i += 1) {
      for (let j = i + 1; j < FEATURES.length; j += 1) {
        const first = FEATURES[i]!;
        const second = FEATURES[j]!;
        const separation = distance(
          lab(colourAt(positionOf(first.log10Flux))),
          lab(colourAt(positionOf(second.log10Flux))),
        );
        expect(separation, `${first.name} against ${second.name}`).toBeGreaterThan(20);
      }
    }
  });
});
