/**
 * The ionosphere's four named regions: the band table, the presence rules, and
 * the proof that a legend swatch cannot drift from the pixels.
 *
 * Sean, on the shipped build of 2026-08-26: "when I plot the ionosphere, I see
 * what I think is the D layer in orange. but it isn't indicated anywhere. It
 * should be in the legend. And I thought we were going to find a way to show
 * the d, e, f1 and f2 layers somewhere." He read the picture correctly and the
 * layer never named what it drew. These are the tests for the naming.
 */
import { describe, expect, it } from "vitest";

import { ionosphereRegionMarks } from "../src/main";
import { compositeProfile } from "../src/ionosphere-composite";
import {
  IONOSPHERE_EMPIRICAL_COLOR_HEX,
  IONOSPHERE_MODEL_COLOR_HEX,
  IONOSPHERE_REGION_BANDS,
  IONOSPHERE_VOLUME_ALTITUDE_KM,
  allIonosphereRegionsOn,
  ionosphereRampHex,
  ionosphereRegionAt,
  regionEnabledVector,
  type IonosphereRegionId,
  type IonosphereVolumeBake,
} from "../src/ionosphere-density-volume";

/**
 * A bake stub carrying only what the marks read. Deliberately hand-built: the
 * point of these cases is the PRESENCE RULES, and a real bake always has
 * material in all four bands, so the "nothing published at those heights" case
 * could not be reached from one.
 */
function bakeWith(
  overrides: Partial<Record<IonosphereRegionId, { drawnSampleCount: number; swatchHex: string }>> = {},
): IonosphereVolumeBake {
  const regions = {} as IonosphereVolumeBake["measured"]["regions"];
  for (const band of IONOSPHERE_REGION_BANDS) {
    const override = overrides[band.region];
    regions[band.region] = {
      drawnSampleCount: override?.drawnSampleCount ?? 1000,
      rampPosition: 0.5,
      brightLog10: 11,
      swatchHex: override?.swatchHex ?? "#123456",
    };
  }
  return { measured: { regions } } as unknown as IonosphereVolumeBake;
}

const ALL_ON = allIonosphereRegionsOn();

describe("the four named regions", () => {
  /**
   * The band table and the composite profile must name the same four things.
   * They are typed separately so the render path does not drag the sounding
   * network in behind it, and this is what stops the two lists drifting apart
   * in silence — the failure that would let the legend name a region the
   * profile has never heard of.
   */
  it("names exactly the four layers the composite profile produces", () => {
    const composite = compositeProfile({
      point: { latitudeDeg: 0, longitudeDeg: 0 },
      time: new Date("2026-08-19T12:00:00Z"),
      stations: [],
      xrayFluxWm2: 2e-6,
      modelFoF2Mhz: 8,
      modelHmF2Km: 300,
      dRegionEffectiveHeightKm: 74,
      dRegionBetaPerKm: 0.35,
    });
    expect(IONOSPHERE_REGION_BANDS.map((band) => band.region))
      .toEqual(composite.layers.map((layer) => layer.layer));
  });

  /**
   * Four, and exactly four, because the fragment shader carries the mask as a
   * vec4. A fifth region added to this table would silently never be drawable.
   */
  it("fits the shader's four-component mask", () => {
    expect(IONOSPHERE_REGION_BANDS).toHaveLength(4);
    const vector = regionEnabledVector({ D: true, E: false, F1: false, F2: true });
    expect([vector.x, vector.y, vector.z, vector.w]).toEqual([1, 0, 0, 1]);
  });

  /**
   * The bands tile the drawn column exactly. This is what makes "all four on"
   * bit-for-bit the whole-column picture the layer has always opened on, so
   * naming the regions changed nothing about the default view.
   */
  it("tiles the whole drawn column with no gap and no overlap", () => {
    expect(IONOSPHERE_REGION_BANDS[0]!.lowKm).toBe(IONOSPHERE_VOLUME_ALTITUDE_KM.low);
    expect(IONOSPHERE_REGION_BANDS.at(-1)!.highKm).toBe(IONOSPHERE_VOLUME_ALTITUDE_KM.high);
    for (let index = 1; index < IONOSPHERE_REGION_BANDS.length; index += 1) {
      expect(IONOSPHERE_REGION_BANDS[index]!.lowKm).toBe(IONOSPHERE_REGION_BANDS[index - 1]!.highKm);
    }
  });

  it("puts each region's own peak height inside its own band", () => {
    // The heights the composite profile actually uses: hmE 110 km, hmF1 190 km,
    // the D region's effective height around 74 km, and an hmF2 of 300 km.
    expect(ionosphereRegionAt(74)).toBe("D");
    expect(ionosphereRegionAt(110)).toBe("E");
    expect(ionosphereRegionAt(190)).toBe("F1");
    expect(ionosphereRegionAt(300)).toBe("F2");
  });

  it("claims nothing below the drawn column or above the topside", () => {
    expect(ionosphereRegionAt(59)).toBeNull();
    expect(ionosphereRegionAt(2656)).toBeNull();
    expect(ionosphereRegionAt(2655)).toBe("F2");
  });
});

describe("the legend swatches", () => {
  /**
   * THE SINGLE-SOURCING PROOF, and the reason it is worth a test: a swatch that
   * repeats a hex string is a second copy of a colour, and the first person to
   * retune a ramp makes the legend name a colour the renderer no longer paints.
   * The swatch here goes through the same interpolation the ramp texture is
   * built from, at the same position the shader samples, so it cannot.
   */
  it("interpolates the renderer's own ramp constants, ends included", () => {
    expect(ionosphereRampHex(IONOSPHERE_MODEL_COLOR_HEX, 0))
      .toBe(IONOSPHERE_MODEL_COLOR_HEX[0]);
    expect(ionosphereRampHex(IONOSPHERE_MODEL_COLOR_HEX, 1))
      .toBe(IONOSPHERE_MODEL_COLOR_HEX.at(-1));
    expect(ionosphereRampHex(IONOSPHERE_EMPIRICAL_COLOR_HEX, 0))
      .toBe(IONOSPHERE_EMPIRICAL_COLOR_HEX[0]);
    expect(ionosphereRampHex(IONOSPHERE_EMPIRICAL_COLOR_HEX, 1))
      .toBe(IONOSPHERE_EMPIRICAL_COLOR_HEX.at(-1));
  });

  /**
   * And the two ramps share no hue, which is the whole reason the D band is
   * legible as a different KIND of evidence rather than as the bottom of the
   * model field. Red beats blue in the warm ramp and the reverse in the cool
   * one, at every position.
   */
  it("keeps the empirical band warm and the model band cool at every stop", () => {
    for (const position of [0.25, 0.5, 0.75, 1]) {
      const warm = ionosphereRampHex(IONOSPHERE_EMPIRICAL_COLOR_HEX, position);
      const cool = ionosphereRampHex(IONOSPHERE_MODEL_COLOR_HEX, position);
      const red = (hex: string) => Number.parseInt(hex.slice(1, 3), 16);
      const blue = (hex: string) => Number.parseInt(hex.slice(5, 7), 16);
      expect(red(warm), `warm ramp at ${position}`).toBeGreaterThan(blue(warm));
      expect(blue(cool), `cool ramp at ${position}`).toBeGreaterThan(red(cool));
    }
  });

  it("takes each row's swatch from the bake rather than from a literal", () => {
    const bake = bakeWith({
      D: { drawnSampleCount: 500, swatchHex: "#aa5511" },
      F2: { drawnSampleCount: 500, swatchHex: "#eef8ff" },
    });
    const { marks } = ionosphereRegionMarks({
      bake, enabled: ALL_ON, f1CriterionPercent: 0, hmF2Km: 310,
    });
    expect(marks[0]!.swatch).toBe("#aa5511");
    expect(marks.at(-1)!.swatch).toBe("#eef8ff");
  });
});

describe("drawn, switched off, and genuinely absent", () => {
  it("names all four when all four are drawn", () => {
    const { marks, switchedOff, notDrawn } = ionosphereRegionMarks({
      bake: bakeWith(), enabled: ALL_ON, f1CriterionPercent: 0, hmF2Km: 300,
    });
    expect(marks.map((mark) => mark.name)).toEqual([
      "D region · 60–90 km",
      "E region · 90–150 km",
      "F1 region · 150–200 km",
      "F2 region · 200 km and above",
    ]);
    expect(switchedOff).toEqual([]);
    expect(notDrawn).toEqual([]);
  });

  /**
   * The evidence classes are not decoration and they are not all the same. The
   * D band is the empirical Wait–Spies fit driven by a measured X-ray flux; the
   * three above it are WAM-IPE. That difference is why the D band has its own
   * palette, and naming it is the thing Sean was missing.
   */
  it("badges the D band EMPIRICAL and the model bands MODEL", () => {
    const { marks } = ionosphereRegionMarks({
      bake: bakeWith(), enabled: ALL_ON, f1CriterionPercent: 0, hmF2Km: 300,
    });
    expect(marks.map((mark) => mark.evidence)).toEqual(["empirical", "model", "model", "model"]);
  });

  /**
   * NEVER claim a sounding's authority over pixels no sounding touched. E and
   * F1 badge COMPOSITE in the vertical profile, where they really are Chapman
   * shapes anchored to instruments that sounded them — but the volume paints
   * the model there, so the legend must not, and it has to send the reader to
   * the place where the anchored version lives.
   */
  it("sends the reader to the profile for the anchored E and F1 layers", () => {
    const { marks } = ionosphereRegionMarks({
      bake: bakeWith(), enabled: ALL_ON, f1CriterionPercent: 0, hmF2Km: 300,
    });
    const [, e, f1] = marks;
    expect(e!.what).toContain("ionosondes");
    expect(e!.what).toContain("vertical profile");
    expect(f1!.what).toContain("vertical profile");
    for (const mark of marks) expect(mark.evidence).not.toBe("composite");
  });

  /**
   * The E row must NOT quote `supportedColumnPercent`. That number counts
   * columns where the extractor's peak criterion returned a value — 90% of the
   * globe on the live artifact — while the same artifact's E ledge has a median
   * prominence of 0.02 dex and a negative prominence on the dayside. Both are
   * true and they measure different things, and quoting the first as the reason
   * the model does not resolve E is a sentence at war with itself. The row
   * cites the prominence, which is the measurement that settles it.
   */
  it("argues E from the ledge prominence, not from a column count", () => {
    const { marks } = ionosphereRegionMarks({
      bake: bakeWith(), enabled: ALL_ON, f1CriterionPercent: 12.4, hmF2Km: 300,
    });
    expect(marks[1]!.what).toContain("0.02 dex");
    expect(marks[1]!.what).toContain("negative");
    expect(marks[1]!.what).not.toContain("% of columns");
    expect(marks[2]!.what).toContain("12% of columns");
  });

  /** A region the reader hid gets no row, and the card says who hid it. */
  it("drops a switched-off region from the key and reports it as hidden", () => {
    const { marks, switchedOff, notDrawn } = ionosphereRegionMarks({
      bake: bakeWith(),
      enabled: { ...ALL_ON, E: false, F1: false },
      f1CriterionPercent: 0, hmF2Km: 300,
    });
    expect(marks.map((mark) => mark.name)).toEqual([
      "D region · 60–90 km",
      "F2 region · 200 km and above",
    ]);
    expect(switchedOff).toEqual(["E", "F1"]);
    expect(notDrawn).toEqual([]);
  });

  /**
   * And a region that is switched ON but has nothing published at its heights
   * is a DIFFERENT fact, reported differently. Collapsing the two would leave a
   * reader unable to tell "you hid this" from "this is not there", which is
   * exactly the confusion an isolate control introduces if nobody guards it.
   */
  it("keeps 'you hid it' and 'nothing is there' in separate lists", () => {
    const { marks, switchedOff, notDrawn } = ionosphereRegionMarks({
      bake: bakeWith({ D: { drawnSampleCount: 0, swatchHex: "#000000" } }),
      enabled: { ...ALL_ON, F1: false },
      f1CriterionPercent: 0, hmF2Km: 300,
    });
    expect(marks.map((mark) => mark.name)).toEqual([
      "E region · 90–150 km",
      "F2 region · 200 km and above",
    ]);
    expect(switchedOff).toEqual(["F1"]);
    expect(notDrawn).toEqual(["D"]);
  });

  /** Nothing baked, nothing named. Four rows over an empty scene would be worse than silence. */
  it("names nothing before there is a bake to read", () => {
    const { marks, switchedOff, notDrawn } = ionosphereRegionMarks({
      bake: null, enabled: ALL_ON, f1CriterionPercent: null, hmF2Km: null,
    });
    expect(marks).toEqual([]);
    expect(switchedOff).toEqual([]);
    expect(notDrawn).toEqual([]);
  });
});
