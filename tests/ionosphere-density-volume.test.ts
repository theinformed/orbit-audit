import { beforeEach, describe, expect, it } from "vitest";

import { EARTH_AIRGLOW_SHELL_SCALE } from "../src/globe";
import { RULER_EARTH_RADIUS_KM, setActiveDistanceScale, sharedDisplayRadius } from "../src/radial-ruler";

import {
  IONOSPHERE_EMPIRICAL_COLOR_HEX,
  IONOSPHERE_EVIDENCE_CODE,
  IONOSPHERE_MODEL_COLOR_HEX,
  IONOSPHERE_VOLUME_ALTITUDE_KM,
  IONOSPHERE_VOLUME_ALTITUDE_SLABS,
  IONOSPHERE_VOLUME_WARP_KM,
  IONOSPHERE_MODEL_DISPLAY_DECADES,
  IONOSPHERE_EMPIRICAL_DISPLAY_DECADES,
  IONOSPHERE_REGION_BANDS,
  bakeIonosphereVolume,
  ionosphereRampHex,
  ionosphereVerticalWarp,
  selectVolumeFrames,
} from "../src/ionosphere-density-volume";
import type { IonosphereVolumeBundle } from "../src/types";

const EARTH_SCENE_RADIUS = 100;
const EARTH_RADIUS_KM = 6371;

function encoded(values: number[]) {
  return btoa(String.fromCharCode(...values));
}

function validityBits(values: boolean[]) {
  const bytes = new Uint8Array(Math.ceil(values.length / 8));
  values.forEach((value, index) => {
    if (value) bytes[index >> 3] = bytes[index >> 3]! | (1 << (index & 7));
  });
  return encoded(Array.from(bytes));
}

/**
 * A two-level, two-column bundle. The published levels straddle the E region
 * so a resample onto the warped axis has something real to interpolate.
 */
function makeBundle(options: { valid?: boolean[]; density?: number[] } = {}): IonosphereVolumeBundle {
  const pointCount = 8; // 2 altitudes x 2 latitudes x 2 longitudes
  const valid = options.valid ?? Array.from({ length: pointCount }, () => true);
  const density = options.density ?? [40, 40, 40, 40, 200, 200, 200, 200];
  return {
    schema: 1,
    generatedAt: "2026-08-19T00:00:00Z",
    status: "forecast",
    model: "NOAA operational WAM-IPE Forecast System (WFS)",
    runAt: "2026-08-19T00:00:00Z",
    coverage: {
      requestedHistoryHours: 48, actualHistoryHours: 48, forecastHours: 48,
      validFrom: "2026-08-19T00:00:00Z", validTo: "2026-08-19T04:00:00Z",
      latestRunAt: "2026-08-19T00:00:00Z", sourceRetentionLimited: false,
    },
    source: {
      name: "NOAA/NCEP NOMADS operational WAM-IPE full-field IPE output",
      url: "https://nomads.ncep.noaa.gov/example",
      sourceCadenceMinutes: 10, publishedCadenceMinutes: 240,
    },
    grid: {
      coordinateSystem: "geographic longitude, latitude, and geometric altitude",
      ordering: "altitude-latitude-longitude",
      longitudesDeg: [0, 180],
      latitudesDeg: [-45, 45],
      altitudesKm: [90, 2655],
      pointCount,
      sourceShape: [58, 91, 90],
      sampling: { longitudeStride: 2, latitudeStride: 2, altitudeSourceIndices: [0, 57] },
    },
    electronDensity: {
      quantity: "electron number density", units: "m⁻³", scale: "log10",
      minimum: 7, maximum: 12.6, storage: "uint8",
    },
    ionComposition: {
      species: ["O+", "H+", "He+", "N+", "NO+", "O2+", "N2+"],
      quantity: "positive-ion fraction", units: "fraction",
      storage: "packed-uint4", maximumCode: 15, packing: "species pairs",
    },
    representation: {
      recommendedDefault: "smooth", native: "Reduced source-grid samples.",
      smooth: "Trilinear interpolation of log10 density.",
    },
    frames: [
      {
        validAt: "2026-08-19T00:00:00Z", runAt: "2026-08-19T00:00:00Z", leadMinutes: 0,
        phase: "history", densityU8: encoded(density), validityBits: validityBits(valid),
        compositionU4: encoded(Array.from({ length: pointCount * 4 }, () => 0x22)),
      },
      {
        validAt: "2026-08-19T04:00:00Z", runAt: "2026-08-19T00:00:00Z", leadMinutes: 240,
        phase: "forecast", densityU8: encoded(density), validityBits: validityBits(valid),
        compositionU4: encoded(Array.from({ length: pointCount * 4 }, () => 0x22)),
      },
    ],
    caveat: "Operational physics-model forecast, not an electron-density observation.",
  } as IonosphereVolumeBundle;
}

const TIME = new Date("2026-08-19T00:00:00Z");

function bake(bundle = makeBundle(), overrides: Record<string, unknown> = {}) {
  return bakeIonosphereVolume(bundle, {
    earthSceneRadius: EARTH_SCENE_RADIUS,
    time: TIME,
    xrayFluxWm2: 2e-6,
    ...overrides,
  });
}

/** Evidence code at one texel of the baked (longitude, latitude, slab) grid. */
function evidenceAtSlab(result: ReturnType<typeof bake>, slab: number) {
  const stride = result.longitudeCount * result.latitudeCount;
  return result.data[(slab * stride) * 2 + 1];
}

function slabAltitudeKm(result: ReturnType<typeof bake>, slab: number) {
  const t = slab / (result.altitudeCount - 1);
  return IONOSPHERE_VOLUME_WARP_KM
    * Math.expm1(result.warpLow + (result.warpHigh - result.warpLow) * t);
}

beforeEach(() => {
  setActiveDistanceScale("teaching");
});

describe("the warped vertical axis", () => {
  /**
   * The reason the axis is warped at all. Everything a reader came to see is
   * in the bottom fifth of a 60-2655 km span, so a uniform axis spends its
   * resolution on the topside and smears the E ledge.
   */
  it("resolves the E region several times finer than a uniform altitude axis would", () => {
    const result = bake();
    const slabs = result.altitudeCount;
    const uniformKmPerSlab = (result.altitudeHighKm - result.altitudeLowKm) / (slabs - 1);

    // Find the two slabs bracketing 90 km and measure the warped spacing there.
    let index = 0;
    while (index < slabs - 2 && slabAltitudeKm(result, index + 1) < 90) index += 1;
    const warpedKmPerSlab = slabAltitudeKm(result, index + 1) - slabAltitudeKm(result, index);

    expect(warpedKmPerSlab).toBeLessThan(5);
    expect(uniformKmPerSlab).toBeGreaterThan(10);
    // The whole point: better than twice the resolution where the layers are.
    expect(uniformKmPerSlab / warpedKmPerSlab).toBeGreaterThan(2);
  });

  /**
   * The warp is a function of ALTITUDE, never of drawn radius, so one bake is
   * correct on both distance scales and switching the ruler does not silently
   * re-map the field onto the wrong heights.
   */
  it("puts the same altitudes on the same texture slabs on both distance scales", () => {
    const teaching = bake();
    setActiveDistanceScale("true-distance");
    const trueDistance = bake();
    expect(trueDistance.warpLow).toBeCloseTo(teaching.warpLow, 12);
    expect(trueDistance.warpHigh).toBeCloseTo(teaching.warpHigh, 12);
    // Only the drawn shell moves.
    expect(trueDistance.sceneRadiusMaximum).not.toBeCloseTo(teaching.sceneRadiusMaximum, 3);
  });

  it("is monotone and matches the ruler's own near-Earth shape constant", () => {
    expect(IONOSPHERE_VOLUME_WARP_KM).toBe(350);
    expect(ionosphereVerticalWarp(60)).toBeLessThan(ionosphereVerticalWarp(90));
    expect(ionosphereVerticalWarp(90)).toBeLessThan(ionosphereVerticalWarp(2655));
    expect(ionosphereVerticalWarp(0)).toBe(0);
  });
});

describe("the shared ruler", () => {
  /**
   * No private curve and no vertical exaggeration. The retired peak surfaces
   * had both, which is why a satellite at the F2 peak altitude drew above the
   * F2 peak surface.
   */
  it("draws its shell exactly where the scene's shared ruler puts those altitudes", () => {
    const result = bake();
    const low = sharedDisplayRadius((EARTH_RADIUS_KM + 60) / EARTH_RADIUS_KM, EARTH_SCENE_RADIUS);
    const high = sharedDisplayRadius((EARTH_RADIUS_KM + 2655) / EARTH_RADIUS_KM, EARTH_SCENE_RADIUS);
    expect(result.sceneRadiusMinimum).toBeCloseTo(low, 9);
    expect(result.sceneRadiusMaximum).toBeCloseTo(high, 9);
    // Sanity against the numbers written in the module header.
    expect(result.sceneRadiusMinimum).toBeCloseTo(104.43, 2);
    expect(result.sceneRadiusMaximum).toBeCloseTo(160.2, 1);
  });
});

describe("the two evidence classes", () => {
  it("marks the D band empirical and the published field model", () => {
    const result = bake();
    let sawEmpirical = false;
    let sawModel = false;
    for (let slab = 0; slab < result.altitudeCount; slab += 1) {
      const altitude = slabAltitudeKm(result, slab);
      const code = evidenceAtSlab(result, slab);
      if (altitude <= IONOSPHERE_VOLUME_ALTITUDE_KM.empiricalHighKm) {
        expect(code).toBe(IONOSPHERE_EVIDENCE_CODE.empirical);
        sawEmpirical = true;
      } else if (altitude >= IONOSPHERE_VOLUME_ALTITUDE_KM.modelLowKm) {
        expect(code).toBe(IONOSPHERE_EVIDENCE_CODE.model);
        sawModel = true;
      }
    }
    expect(sawEmpirical).toBe(true);
    expect(sawModel).toBe(true);
  });

  /**
   * 85-90 km is claimed by neither published model, so it is drawn as nothing
   * rather than bridged. A smooth join there would assert one continuous
   * measured profile across two independent models.
   */
  it("draws nothing in the band neither model claims", () => {
    const result = bake();
    let sawGap = false;
    for (let slab = 0; slab < result.altitudeCount; slab += 1) {
      const altitude = slabAltitudeKm(result, slab);
      if (altitude > IONOSPHERE_VOLUME_ALTITUDE_KM.empiricalHighKm
        && altitude < IONOSPHERE_VOLUME_ALTITUDE_KM.modelLowKm) {
        expect(evidenceAtSlab(result, slab)).toBe(IONOSPHERE_EVIDENCE_CODE.none);
        sawGap = true;
      }
    }
    expect(sawGap).toBe(true);
  });

  it("omits the empirical band entirely when it is switched off, rather than filling it from the model", () => {
    const result = bake(makeBundle(), { includeEmpiricalDRegion: false });
    expect(result.measured.empiricalSampleCount).toBe(0);
    for (let slab = 0; slab < result.altitudeCount; slab += 1) {
      if (slabAltitudeKm(result, slab) < IONOSPHERE_VOLUME_ALTITUDE_KM.modelLowKm) {
        expect(evidenceAtSlab(result, slab)).toBe(IONOSPHERE_EVIDENCE_CODE.none);
      }
    }
  });

  /**
   * The two palettes must not be confusable, because the palette IS the
   * disclosure that the evidence changed. Compared on the red-minus-blue axis,
   * which is what separates warm from cool.
   */
  it("gives the empirical and model ramps opposite warm/cool sense at every stop", () => {
    const warmth = (hex: string) => {
      const value = Number.parseInt(hex.slice(1), 16);
      return ((value >> 16) & 255) - (value & 255);
    };
    expect(IONOSPHERE_EMPIRICAL_COLOR_HEX.length).toBe(IONOSPHERE_MODEL_COLOR_HEX.length);
    IONOSPHERE_EMPIRICAL_COLOR_HEX.forEach((empirical, index) => {
      const model = IONOSPHERE_MODEL_COLOR_HEX[index]!;
      expect(warmth(empirical)).toBeGreaterThan(0);
      expect(warmth(model)).toBeLessThanOrEqual(0);
    });
  });
});

describe("validity", () => {
  /**
   * `validityBits` is a published fact. An unsupported column leaves a hole;
   * it is never filled from a neighbour, and never drawn as low density, which
   * would read as "thin here" instead of "not known here".
   */
  it("leaves an unsupported column as a hole rather than filling it", () => {
    const valid = Array.from({ length: 8 }, () => true);
    valid[0] = false; // the 90 km level of one column
    valid[4] = false; // and its 2655 km level, so the whole column is unsupported
    const result = bake(makeBundle({ valid }));
    const stride = result.longitudeCount * result.latitudeCount;
    // Column 0 is unsupported at every MODEL slab.
    for (let slab = 0; slab < result.altitudeCount; slab += 1) {
      if (slabAltitudeKm(result, slab) < IONOSPHERE_VOLUME_ALTITUDE_KM.modelLowKm) continue;
      expect(result.data[(slab * stride + 0) * 2 + 1]).toBe(IONOSPHERE_EVIDENCE_CODE.none);
      // A supported neighbour is still drawn.
      expect(result.data[(slab * stride + 1) * 2 + 1]).toBe(IONOSPHERE_EVIDENCE_CODE.model);
    }
    expect(result.measured.invalidSampleCount).toBeGreaterThan(0);
  });
});

describe("the display window", () => {
  /**
   * The window is measured from the frame, not taken from the artifact's
   * published 7.0-12.6. The published window is 5.6 decades wide and puts
   * every visible sample in its top quarter, which renders the layer as one
   * flat fog; three decades below the frame's own maximum is what turns the
   * F2 peak back into a shell. The published scale is still the ceiling's
   * upper bound -- the window narrows the DISPLAY, it never invents density
   * the file does not contain.
   */
  it("spans a fixed number of decades below the frame's own maximum", () => {
    const bundle = makeBundle();
    const result = bake(bundle);
    expect(result.logCeiling - result.logFloor).toBeCloseTo(IONOSPHERE_MODEL_DISPLAY_DECADES, 9);
    expect(result.logCeiling).toBeLessThanOrEqual(bundle.electronDensity.maximum + 1e-9);
    expect(result.logCeiling).toBeGreaterThanOrEqual(bundle.electronDensity.minimum);
  });

  it("moves the window when the field moves, instead of clipping a strong frame", () => {
    const quiet = bake(makeBundle({ density: [40, 40, 40, 40, 120, 120, 120, 120] }));
    const active = bake(makeBundle({ density: [40, 40, 40, 40, 250, 250, 250, 250] }));
    expect(active.logCeiling).toBeGreaterThan(quiet.logCeiling);
    // Both keep the same width, so a reader comparing two frames is comparing
    // the same number of decades.
    expect(active.logCeiling - active.logFloor)
      .toBeCloseTo(quiet.logCeiling - quiet.logFloor, 9);
  });

  it("puts the densest published sample at the top of the ramp", () => {
    const result = bake();
    let highest = 0;
    for (let index = 0; index < result.data.length; index += 2) {
      if (result.data[index + 1] === IONOSPHERE_EVIDENCE_CODE.model) {
        highest = Math.max(highest, result.data[index]!);
      }
    }
    expect(highest).toBe(255);
  });

  /**
   * The empirical band is normalized separately, because on the model's window
   * the D region -- genuinely 2-3 decades thinner -- clamps to zero and
   * vanishes. The card quotes both windows so the trade is stated rather than
   * hidden.
   */
  it("gives the empirical band its own window, below the model's", () => {
    const result = bake();
    expect(result.empiricalLogCeiling - result.empiricalLogFloor)
      .toBeCloseTo(IONOSPHERE_EMPIRICAL_DISPLAY_DECADES, 9);
    expect(result.empiricalLogCeiling).toBeLessThan(result.logCeiling);
  });
});

describe("frame selection", () => {
  /**
   * The coverage window is a published fact. Outside it the layer clamps to
   * the nearest published frame instead of extrapolating a forecast the model
   * never made.
   */
  it("clamps outside the published window instead of extrapolating", () => {
    const bundle = makeBundle();
    const before = selectVolumeFrames(bundle, new Date("2026-08-18T00:00:00Z"));
    expect(before).toEqual({ startIndex: 0, endIndex: 0, blend: 0 });
    const after = selectVolumeFrames(bundle, new Date("2026-08-20T00:00:00Z"));
    expect(after).toEqual({ startIndex: 1, endIndex: 1, blend: 0 });
  });

  it("blends linearly between the two bracketing frames", () => {
    const bundle = makeBundle();
    const middle = selectVolumeFrames(bundle, new Date("2026-08-19T02:00:00Z"));
    expect(middle.startIndex).toBe(0);
    expect(middle.endIndex).toBe(1);
    expect(middle.blend).toBeCloseTo(0.5, 6);
  });

  it("reports which frames it drew, so the card never has to guess", () => {
    const result = bake();
    expect(result.frames.startValidAt).toBe("2026-08-19T00:00:00Z");
    expect(result.frames.blend).toBe(0);
  });
});

describe("the bake budget", () => {
  it("keeps the texture within a megabyte or so of the published grid", () => {
    const result = bake();
    expect(result.altitudeCount).toBe(IONOSPHERE_VOLUME_ALTITUDE_SLABS);
    // Two channels, one byte each.
    expect(result.data.length).toBe(result.longitudeCount * result.latitudeCount * result.altitudeCount * 2);
    // The real published grid is 45 x 46; this is the cost that sets.
    expect(45 * 46 * IONOSPHERE_VOLUME_ALTITUDE_SLABS * 2).toBeLessThan(1.2 * 1024 * 1024);
  });
});

describe("Earth's own limb glow against this volume", () => {
  it("is inside the volume on both distance scales, which is why the globe hides it here", () => {
    // The reason `SpaceGlobe.applyAirglowVisibility` exists, pinned as the
    // measurement rather than as the rule.
    //
    // The limb glow is scenery: a fixed multiple of the DRAWN globe, not an
    // altitude on the shared ruler. So it means a different height on each
    // scale, and on both it lands inside the modelled electron density -- at
    // which point a reader isolating a band is looking at two concentric cyan
    // shells with nothing on screen to say which one is the model.
    const airglowDrawn = EARTH_AIRGLOW_SHELL_SCALE;

    setActiveDistanceScale("teaching");
    const teachingKm = (invertDrawn(airglowDrawn) - 1) * RULER_EARTH_RADIUS_KM;
    expect(teachingKm).toBeGreaterThan(95);
    expect(teachingKm).toBeLessThan(105);
    // The altitude picker's E band, and the glow sits inside it.
    const eLowDrawn = sharedDisplayRadius(1 + 90 / RULER_EARTH_RADIUS_KM, 1);
    const eHighDrawn = sharedDisplayRadius(1 + 175 / RULER_EARTH_RADIUS_KM, 1);
    expect(airglowDrawn).toBeGreaterThan(eLowDrawn - 0.002);
    expect(airglowDrawn).toBeLessThan(eHighDrawn);

    setActiveDistanceScale("true-distance");
    // Same drawn radius, a completely different altitude: the F region.
    const trueKm = (airglowDrawn - 1) * RULER_EARTH_RADIUS_KM;
    expect(trueKm).toBeGreaterThan(400);
    // And still inside the volume, whose floor is 60 km.
    expect(airglowDrawn).toBeGreaterThan(
      sharedDisplayRadius(1 + IONOSPHERE_VOLUME_ALTITUDE_KM.low / RULER_EARTH_RADIUS_KM, 1),
    );
    setActiveDistanceScale("teaching");
  });
});

/** Invert the teaching ruler numerically; it is monotone, so bisection is exact enough. */
function invertDrawn(drawn: number): number {
  let low = 1;
  let high = 2;
  for (let i = 0; i < 80; i += 1) {
    const middle = (low + high) / 2;
    if (sharedDisplayRadius(middle, 1) < drawn) low = middle;
    else high = middle;
  }
  return (low + high) / 2;
}

/**
 * The per-region measurement the legend reads, checked against a real bake
 * rather than a stub — because the whole claim being made is "this swatch is
 * the colour the renderer paints that band", and a stub cannot test that.
 */
describe("what each named region actually holds", () => {
  it("finds drawn material in every band the reader can switch on", () => {
    const result = bake();
    for (const band of IONOSPHERE_REGION_BANDS) {
      expect(result.measured.regions[band.region].drawnSampleCount, band.region)
        .toBeGreaterThan(0);
    }
  });

  /**
   * THE DRIFT PROOF. The swatch on a legend row is the ramp evaluated at the
   * measured median of the very byte the fragment shader will feed into that
   * same ramp, through the same function the ramp texture is built from. There
   * is one copy of the colour, so the row and the pixels cannot disagree.
   */
  it("paints each region's swatch out of the renderer's own ramp", () => {
    const result = bake();
    for (const band of IONOSPHERE_REGION_BANDS) {
      const region = result.measured.regions[band.region];
      const ramp = band.region === "D" ? IONOSPHERE_EMPIRICAL_COLOR_HEX : IONOSPHERE_MODEL_COLOR_HEX;
      expect(region.swatchHex, band.region).toBe(ionosphereRampHex(ramp, region.rampPosition));
    }
  });

  /**
   * And the swatch tracks the field rather than being pinned. This fixture's
   * column rises with altitude, so the bands must brighten upward; if the
   * measurement were ignored every row would come out the same colour, which
   * is the failure that makes a four-row key useless.
   *
   * E and F1 both sit at the ramp FLOOR here and that is correct rather than a
   * weak assertion: this fixture publishes only 90 km and 2,655 km, so
   * everything below 200 km falls more than the display window's three decades
   * under the frame maximum and clamps. On the live artifact the measured
   * F2-minus-E gap reaches 2.31 dex at the 95th percentile, inside the window,
   * which is why 3.0 decades is the smallest window this layer can use.
   */
  it("brightens upward when the field does", () => {
    const regions = bake().measured.regions;
    expect(regions.F2.rampPosition).toBeGreaterThan(regions.F1.rampPosition);
    expect(regions.F1.rampPosition).toBeGreaterThanOrEqual(regions.E.rampPosition);
    expect(regions.F2.swatchHex).not.toBe(regions.E.swatchHex);
  });

  /**
   * The genuinely-absent case, reached the only way a real bake can reach it:
   * with the empirical band excluded there is nothing published at D heights,
   * and the legend must be able to tell that from a reader having hidden it.
   */
  it("reports no drawn material at D heights when the empirical band is off", () => {
    const result = bake(makeBundle(), { includeEmpiricalDRegion: false });
    expect(result.measured.regions.D.drawnSampleCount).toBe(0);
    expect(result.measured.regions.F2.drawnSampleCount).toBeGreaterThan(0);
  });
});
