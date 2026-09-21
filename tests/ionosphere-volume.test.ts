import { describe, expect, it } from "vitest";
import {
  IonosphereVolumeLayer,
  IonosphereSampler,
  IonospherePeakSampler,
  IONOSPHERE_RENDERING_LABELS,
  buildIonospherePositions,
  decodeIonosphereDensity,
  decodeIonosphereValidity,
  ionosphereDensityFromCode,
  ionosphereDisplayRadius,
  resampleIonosphereFrame,
  sampleIonospherePeakHeight,
  selectIonosphereFrames,
} from "../src/ionosphere-volume";
import type { IonosphereVolumeBundle } from "../src/types";

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

function equalComposition(pointCount: number) {
  return encoded(Array.from({ length: pointCount }, () => [0x22, 0x22, 0x22, 0x02]).flat());
}

function encodedU16(values: number[]) {
  const bytes = new Uint8Array(values.length * 2);
  const view = new DataView(bytes.buffer);
  values.forEach((value, index) => view.setUint16(index * 2, value, true));
  return encoded(Array.from(bytes));
}

const bundle: IonosphereVolumeBundle = {
  schema: 1,
  generatedAt: "2026-08-06T20:00:00Z",
  status: "forecast",
  model: "NOAA operational WAM-IPE Forecast System (WFS)",
  runAt: "2026-08-06T18:00:00Z",
  coverage: {
    requestedHistoryHours: 48,
    actualHistoryHours: 48,
    forecastHours: 48,
    validFrom: "2026-08-06T20:00:00Z",
    validTo: "2026-08-07T00:00:00Z",
    latestRunAt: "2026-08-06T18:00:00Z",
    sourceRetentionLimited: false,
  },
  source: {
    name: "NOAA/NCEP NOMADS operational WAM-IPE full-field IPE output",
    url: "https://nomads.ncep.noaa.gov/example",
    sourceCadenceMinutes: 10,
    publishedCadenceMinutes: 240,
  },
  grid: {
    coordinateSystem: "geographic longitude, latitude, and geometric altitude",
    ordering: "altitude-latitude-longitude",
    longitudesDeg: [0, 90],
    latitudesDeg: [0],
    altitudesKm: [90, 200],
    pointCount: 4,
    sourceShape: [58, 91, 90],
    sampling: { longitudeStride: 2, latitudeStride: 2, altitudeSourceIndices: [0, 16] },
  },
  electronDensity: {
    quantity: "electron number density",
    units: "m⁻³",
    scale: "log10",
    minimum: 7,
    maximum: 12,
    storage: "uint8",
  },
  ionComposition: {
    species: ["O+", "H+", "He+", "N+", "NO+", "O2+", "N2+"],
    quantity: "positive-ion fraction",
    units: "fraction",
    storage: "packed-uint4",
    maximumCode: 15,
    packing: "species pairs in low then high nibble",
  },
  representation: {
    recommendedDefault: "smooth",
    native: "Reduced source-grid samples.",
    smooth: "Trilinear interpolation of log10 density.",
  },
  frames: [
    {
      validAt: "2026-08-06T20:00:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 120,
      phase: "forecast", densityU8: encoded([0, 64, 128, 255]), validityBits: validityBits([true, true, true, true]),
      compositionU4: equalComposition(4),
    },
    {
      validAt: "2026-08-06T22:00:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 240,
      phase: "forecast", densityU8: encoded([255, 128, 64, 0]), validityBits: validityBits([true, true, true, true]),
      compositionU4: equalComposition(4),
    },
    {
      validAt: "2026-08-07T00:00:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 360,
      phase: "forecast", densityU8: encoded([32, 96, 160, 224]), validityBits: validityBits([true, true, true, true]),
      compositionU4: equalComposition(4),
    },
  ],
  caveat: "Forecast model with a 90 km lower boundary.",
};

function bundleWithExactPeaks(): IonosphereVolumeBundle {
  return {
    ...bundle,
    peakSurface: {
      sourceProduct: "NOAA/NCEP WFS ipe05",
      sourceVariables: ["HmF2", "NmF2"],
      sourceCadenceMinutes: 5,
      publishedCadenceMinutes: 5,
      pointCount: 2,
      altitudeEncoding: { scaleKm: 0.1 },
      frames: [
        {
          validAt: "2026-08-06T20:00:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 120,
          phase: "forecast", altitudeU16: encodedU16([2500, 3000]), densityU8: encoded([90, 140]),
          validityBits: validityBits([true, true]),
        },
        {
          validAt: "2026-08-06T20:05:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 125,
          phase: "forecast", altitudeU16: encodedU16([3500, 4000]), densityU8: encoded([120, 180]),
          validityBits: validityBits([true, true]),
        },
        {
          validAt: "2026-08-06T20:10:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 130,
          phase: "forecast", altitudeU16: encodedU16([4500, 5000]), densityU8: encoded([150, 210]),
          validityBits: validityBits([true, true]),
        },
      ],
    },
  } as IonosphereVolumeBundle;
}

// A 3x3 horizontal peak grid (unlike bundleWithExactPeaks' 2-point fixture,
// which is too small for a real neighbor-to-neighbor gradient) for testing
// relief shading, height exaggeration, and hole preservation together.
function bundleForReliefTest(options: { uniform?: boolean; unsupportedIndex?: number } = {}): IonosphereVolumeBundle {
  const longitudesDeg = [0, 120, 240];
  const latitudesDeg = [-30, 0, 30];
  const altitudesKm = [90, 200, 400];
  const pointCount = longitudesDeg.length * latitudesDeg.length * altitudesKm.length;
  const altitudeRawKmTimesTen = options.uniform
    ? new Array(9).fill(3000)
    : [2500, 3000, 3500, 2500, 3000, 3500, 2500, 3000, 3500];
  const density = [100, 110, 120, 100, 110, 120, 100, 110, 120];
  const valid = new Array(9).fill(true);
  if (options.unsupportedIndex !== undefined) valid[options.unsupportedIndex] = false;
  return {
    ...bundle,
    grid: { ...bundle.grid, longitudesDeg, latitudesDeg, altitudesKm, pointCount },
    frames: [
      {
        validAt: "2026-08-06T20:00:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 120,
        phase: "forecast",
        densityU8: encoded(new Array(pointCount).fill(0)),
        validityBits: validityBits(new Array(pointCount).fill(false)),
        compositionU4: equalComposition(pointCount),
      },
    ],
    peakSurface: {
      sourceProduct: "NOAA/NCEP WFS ipe05",
      sourceVariables: ["HmF2", "NmF2"],
      sourceCadenceMinutes: 5,
      publishedCadenceMinutes: 5,
      pointCount: 9,
      altitudeEncoding: { scaleKm: 0.1 },
      frames: [
        {
          validAt: "2026-08-06T20:00:00Z", runAt: "2026-08-06T18:00:00Z", leadMinutes: 120,
          phase: "forecast",
          altitudeU16: encodedU16(altitudeRawKmTimesTen),
          densityU8: encoded(density),
          validityBits: validityBits(valid),
        },
      ],
    },
  } as IonosphereVolumeBundle;
}

describe("WAM-IPE frame selection", () => {
  it("clamps outside the model window and interpolates within it", () => {
    expect(selectIonosphereFrames(bundle, new Date("2026-08-06T19:00:00Z"))).toEqual({
      startIndex: 0, endIndex: 0, blend: 0, state: "before",
    });
    expect(selectIonosphereFrames(bundle, new Date("2026-08-06T21:00:00Z"))).toEqual({
      startIndex: 0, endIndex: 1, blend: 0.5, state: "within",
    });
    expect(selectIonosphereFrames(bundle, new Date("2026-08-07T01:00:00Z"))).toEqual({
      startIndex: 2, endIndex: 2, blend: 0, state: "after",
    });
  });
});

describe("WAM-IPE volume encoding", () => {
  it("validates frames and converts the logarithmic scale back to source units", () => {
    expect(Array.from(decodeIonosphereDensity(bundle.frames[0]!.densityU8, 4))).toEqual([0, 64, 128, 255]);
    expect(Array.from(decodeIonosphereValidity(bundle.frames[0]!.validityBits, 4))).toEqual([255, 255, 255, 255]);
    expect(() => decodeIonosphereDensity(bundle.frames[0]!.densityU8, 5)).toThrow(RangeError);
    expect(ionosphereDensityFromCode(bundle, 0)).toBeCloseTo(1e7);
    expect(ionosphereDensityFromCode(bundle, 255)).toBeCloseTo(1e12);
  });

  it("preserves altitude-major source ordering in compressed scene coordinates", () => {
    const { positions, altitudes } = buildIonospherePositions(bundle);
    const lowerRadius = ionosphereDisplayRadius(90);
    const upperRadius = ionosphereDisplayRadius(200);
    expect(Array.from(altitudes)).toEqual([90, 90, 200, 200]);
    expect(positions[0]).toBeCloseTo(lowerRadius);
    expect(positions[1]).toBeCloseTo(0);
    expect(positions[2]).toBeCloseTo(0);
    expect(positions[3]).toBeCloseTo(0);
    expect(positions[5]).toBeCloseTo(-lowerRadius);
    expect(positions[6]).toBeCloseTo(upperRadius);
  });

  it("uses exact five-minute HmF2 for radius and NmF2 for surface color", () => {
    const layer = new IonosphereVolumeLayer(bundleWithExactPeaks(), { spatialMode: "native" });
    layer.setSimulationTime(new Date("2026-08-06T20:02:30Z"));
    const geometry = layer.surfaces.f2.geometry;
    expect(Array.from(geometry.getAttribute("altitudeA").array)).toEqual([250, 300]);
    expect(Array.from(geometry.getAttribute("altitudeB").array)).toEqual([350, 400]);
    expect(Array.from(geometry.getAttribute("densityA").array)).toEqual([90, 140]);
    expect(layer.surfaces.f2.material.uniforms.blendAmount!.value).toBe(0.5);
    expect(layer.getSurfaceState().regions.f2).toMatchObject({
      source: "NOAA ipe05 HmF2/NmF2",
      altitudeRangeKm: [300, 350],
      supportedColumnPercent: 100,
    });
    expect(layer.points.userData.pointCloud).toBe(false);
    layer.dispose();
  });

  it("reuses a peak mesh within one source-frame pair and rebuilds at the next pair", () => {
    const layer = new IonosphereVolumeLayer(bundleWithExactPeaks(), { spatialMode: "native" });
    layer.setSimulationTime(new Date("2026-08-06T20:01:00Z"));
    const firstPair = layer.surfaces.f2.geometry;
    layer.setSimulationTime(new Date("2026-08-06T20:04:00Z"));
    expect(layer.surfaces.f2.geometry).toBe(firstPair);
    expect(layer.surfaces.f2.material.uniforms.blendAmount!.value).toBe(0.8);
    layer.setSimulationTime(new Date("2026-08-06T20:07:00Z"));
    expect(layer.surfaces.f2.geometry).not.toBe(firstPair);
    expect(Array.from(layer.surfaces.f2.geometry.getAttribute("densityA").array)).toEqual([120, 180]);
    layer.dispose();
  });

  it("defaults to a smooth continuous surface and retains a native horizontal mesh opt-in", () => {
    const layer = new IonosphereVolumeLayer(bundleWithExactPeaks());
    expect(layer.getSpatialMode()).toBe("smooth");
    expect(layer.surfaces.f2.geometry.getAttribute("densityA").count).toBeGreaterThan(2);
    expect(IONOSPHERE_RENDERING_LABELS.smooth).toContain("PEAK SURFACES");
    layer.setSpatialMode("native");
    expect(layer.surfaces.f2.geometry.getAttribute("densityA").count).toBe(2);
    layer.dispose();
  });

  it("preserves trilinear density and missing-cell semantics in the optimized smooth path", () => {
    const volumeBundle: IonosphereVolumeBundle = {
      ...bundle,
      grid: {
        ...bundle.grid,
        longitudesDeg: [0, 180],
        latitudesDeg: [-30, 30],
        altitudesKm: [100, 300],
        pointCount: 8,
      },
      frames: bundle.frames.map((frame) => ({
        ...frame,
        densityU8: encoded([0, 10, 20, 30, 80, 90, 100, 110]),
        validityBits: validityBits([true, true, true, true, true, true, true, true]),
        compositionU4: equalComposition(8),
      })),
    };
    const target = {
      longitudesDeg: [90], latitudesDeg: [0], altitudesKm: [200], pointCount: 1,
    };
    const density = decodeIonosphereDensity(volumeBundle.frames[0]!.densityU8, 8);
    const allValid = decodeIonosphereValidity(volumeBundle.frames[0]!.validityBits, 8);
    const result = resampleIonosphereFrame(volumeBundle, density, allValid, target);
    expect(Array.from(result.density)).toEqual([55]);
    expect(Array.from(result.validity)).toEqual([255]);

    const oneMissing = decodeIonosphereValidity(validityBits([true, true, true, true, true, true, true, false]), 8);
    const masked = resampleIonosphereFrame(volumeBundle, density, oneMissing, target);
    expect(Array.from(masked.validity)).toEqual([0]);
  });

  it("discloses a bounded height exaggeration and an isohypse interval per region, without altering reported physical values", () => {
    const layer = new IonosphereVolumeLayer(bundleWithExactPeaks(), { spatialMode: "native" });
    layer.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    const regions = layer.getSurfaceState().regions;
    for (const region of ["e", "f1", "f2"] as const) {
      expect(regions[region].displayExaggeration.factor).toBeGreaterThan(1);
      expect(regions[region].displayExaggeration.maxSceneUnits).toBeGreaterThan(0);
      expect(regions[region].contourIntervalKm).toBeGreaterThan(0);
    }
    // F2's published height range is wider than E/F1's, so its contour
    // spacing is coarser -- otherwise it would be a wall of lines.
    expect(regions.f2.contourIntervalKm).toBeGreaterThan(regions.e.contourIntervalKm);
    // altitudeA at t=20:00:00Z is the exact frame-0 HmF2: [250, 300] km.
    expect(regions.f2.meanAltitudeKm).toBeCloseTo(275);
    layer.dispose();
  });

  it("exaggerates each vertex's natural log-radius deviation from the surface mean, bounded, and never dips into the Earth", () => {
    const layer = new IonosphereVolumeLayer(bundleWithExactPeaks(), { spatialMode: "native" });
    layer.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    const geometry = layer.surfaces.f2.geometry;
    const position = geometry.getAttribute("position").array as Float32Array;
    const altitude = geometry.getAttribute("altitudeA").array as Float32Array;
    expect(Array.from(altitude)).toEqual([250, 300]); // physical km reported to the sampler/state is untouched
    const maxSceneUnits = layer.getSurfaceState().regions.f2.displayExaggeration.maxSceneUnits;

    const meanAltitudeKm = 275; // mean of the two supported columns above
    const meanRadius = ionosphereDisplayRadius(meanAltitudeKm);
    for (let index = 0; index < 2; index += 1) {
      const naturalRadius = ionosphereDisplayRadius(altitude[index]!);
      const naturalDeviation = naturalRadius - meanRadius;
      const renderedRadius = Math.hypot(position[index * 3]!, position[index * 3 + 1]!, position[index * 3 + 2]!);
      const renderedDeviation = renderedRadius - meanRadius;
      expect(Math.sign(renderedDeviation)).toBe(Math.sign(naturalDeviation));
      expect(Math.abs(renderedDeviation)).toBeGreaterThan(Math.abs(naturalDeviation));
      // position/positionB are Float32Array-backed BufferAttributes, so allow
      // for float32 rounding on top of the double-precision bound math.
      expect(Math.abs(renderedDeviation)).toBeLessThanOrEqual(maxSceneUnits + 1e-3);
      expect(renderedRadius).toBeGreaterThan(100); // earthSceneRadius default
    }
    layer.dispose();
  });

  it("shades F2 relief from its own height gradient, bounded, and stays neutral when a region is genuinely flat", () => {
    const undulating = new IonosphereVolumeLayer(bundleForReliefTest(), { spatialMode: "native" });
    undulating.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    const relief = Array.from(undulating.surfaces.f2.geometry.getAttribute("reliefA").array as Float32Array);
    expect(relief).toHaveLength(9);
    for (const value of relief) {
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(1);
    }
    // Row 0, column 1 sits between a lower column to its west (250 km) and a
    // higher one to its east (350 km) -- it must not read as flat.
    expect(relief[1]).not.toBeCloseTo(0.5, 5);
    undulating.dispose();

    const flat = new IonosphereVolumeLayer(bundleForReliefTest({ uniform: true }), { spatialMode: "native" });
    flat.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    const flatRelief = Array.from(flat.surfaces.f2.geometry.getAttribute("reliefA").array as Float32Array);
    for (const value of flatRelief) expect(value).toBeCloseTo(0.5, 5);
    flat.dispose();
  });

  it("keeps an unsupported peak column a hole after adding relief/exaggeration attributes", () => {
    const layer = new IonosphereVolumeLayer(bundleForReliefTest({ unsupportedIndex: 4 }), { spatialMode: "native" });
    layer.setSimulationTime(new Date("2026-08-06T20:00:00Z"));
    const state = layer.getSurfaceState().regions.f2;
    expect(state.supportedColumnPercent).toBeCloseTo((8 / 9) * 100);
    const indices = Array.from(layer.surfaces.f2.geometry.getIndex()!.array);
    expect(indices).not.toContain(4);
    layer.dispose();
  });
});

describe("IonospherePeakSampler (orbit-curtain support)", () => {
  it("bilinearly interpolates HmF2 height/density across longitude and blends across time", () => {
    const sampler = new IonospherePeakSampler(bundleWithExactPeaks());
    const exact = sampler.sample("f2", { latitudeDeg: 0, longitudeDeg: 0, time: new Date("2026-08-06T20:02:30Z") });
    expect(exact.status).toBe("ok");
    if (exact.status !== "ok") return;
    expect(exact.altitudeKm).toBeCloseTo(300); // lerp(250, 350, 0.5)
    expect(exact.source).toBe("NOAA ipe05 HmF2/NmF2");
    expect(exact.frames.blend).toBeCloseTo(0.5);

    const midLongitude = sampleIonospherePeakHeight(bundleWithExactPeaks(), "f2", {
      latitudeDeg: 0, longitudeDeg: 45, time: new Date("2026-08-06T20:02:30Z"),
    });
    expect(midLongitude.status).toBe("ok");
    if (midLongitude.status !== "ok") return;
    // Halfway between the lon-0 column (300 km) and the lon-90 column (350 km).
    expect(midLongitude.altitudeKm).toBeCloseTo(325);
  });

  it("reports outside-time and unsupported without inventing a height", () => {
    const sampler = new IonospherePeakSampler(bundleWithExactPeaks());
    const early = sampler.sample("f2", { latitudeDeg: 0, longitudeDeg: 0, time: new Date("2026-08-06T19:00:00Z") });
    expect(early.status).toBe("outside-time");

    // This fixture has no F1 regionSurfaces and only a 90/200 km ipe10 grid,
    // so the derived F1 profile has no interior local maximum anywhere: the
    // column must stay an honest hole, not a fabricated height.
    const noPeak = sampler.sample("f1", { latitudeDeg: 0, longitudeDeg: 0, time: new Date("2026-08-06T20:00:00Z") });
    expect(noPeak.status).toBe("unsupported");
  });
});

describe("WAM-IPE interpolation and satellite sampling", () => {
  it("interpolates log density through space and time and reports quantized ion fractions", () => {
    const sample = new IonosphereSampler(bundle).sample({
      latitudeDeg: 0,
      longitudeDeg: 45,
      altitudeKm: 145,
      time: new Date("2026-08-06T21:00:00Z"),
    });
    expect(sample.status).toBe("ok");
    if (sample.status !== "ok") return;
    expect(sample.electronDensityM3).toBeCloseTo(ionosphereDensityFromCode(bundle, 111.75));
    expect(Object.values(sample.ionFractions).reduce((sum, value) => sum + value, 0)).toBeCloseTo(1);
    expect(sample.frames.blend).toBe(0.5);
  });

  it("honors cyclic longitude and distinguishes outside-grid, outside-time, and missing", () => {
    const sampler = new IonosphereSampler(bundle);
    expect(sampler.sample({ latitudeDeg: 0, longitudeDeg: -270, altitudeKm: 90, time: new Date("2026-08-06T20:00:00Z") }).status).toBe("ok");
    expect(sampler.sample({ latitudeDeg: 0, longitudeDeg: 0, altitudeKm: 80, time: new Date("2026-08-06T20:00:00Z") }).status).toBe("outside-grid");
    expect(sampler.sample({ latitudeDeg: 0, longitudeDeg: 0, altitudeKm: 90, time: new Date("2026-08-06T19:00:00Z") }).status).toBe("outside-time");

    const maskedBundle: IonosphereVolumeBundle = {
      ...bundle,
      frames: bundle.frames.map((frame, index) => ({
        ...frame,
        validityBits: index === 0 ? validityBits([false, true, true, true]) : frame.validityBits,
      })),
    };
    expect(new IonosphereSampler(maskedBundle).sample({
      latitudeDeg: 0, longitudeDeg: 0, altitudeKm: 90, time: new Date("2026-08-06T20:00:00Z"),
    }).status).toBe("missing");
    const reduced = resampleIonosphereFrame(
      maskedBundle,
      decodeIonosphereDensity(maskedBundle.frames[0]!.densityU8, 4),
      decodeIonosphereValidity(maskedBundle.frames[0]!.validityBits, 4),
    );
    expect(reduced.validity[0]).toBe(0);
  });
});
