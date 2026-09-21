import * as THREE from "three";
import { describe, expect, it } from "vitest";
import {
  DEFAULT_RADIATION_ENERGY_KEV,
  RADIATION_BELT_DISPLAY_WINDOW,
  RADIATION_BELT_VIEWS,
  createDipoleMappedRadiationGeometry,
  createGyrotropicDipoleMappedRadiationShells,
  createNativeEquatorialRadiationGeometry,
  decodeRadiationBeltCoordinates,
  dipoleFieldRatio,
  dipoleMirrorLatitudeRadians,
  dipoleRadiationPosition,
  equatorialRadiationPosition,
  gyrotropicLocalPitchBinWeights,
  gyrotropicPitchBinEdgeAngles,
  gyrotropicPitchBinWeights,
  localPitchCosine,
  normalizedRadiationFluxFloor,
  radiationBeltDisplayRadius,
  resolveRadiationGridShape,
  trappedPitchIndex,
  trappedPitchIndicesAtRadius,
  trappingFootpointLatitudeRadians,
  COMBINED_RADIATION_ENERGY_KEV,
  combineRadiationEnergyChannels,
  decodeRadiationFlux,
  isCombinedRadiationEnergy,
} from "../src/radiation-belt";
import type {
  RadiationBeltDefinition,
  RadiationBeltFrame,
  RadiationGridShape,
} from "../src/radiation-belt";
import {
  RADIATION_VOLUME_TRANSFER,
  bakeOmnidirectionalFluxVolume,
  createRadiationFieldLineGuides,
  createRadiationVolumeMesh,
  describeRadiationMapperFrame,
  resolveRadiationVolumeOpacityForBake,
  sampleBakedVolume,
} from "../src/radiation-belt-volume";

function littleEndianU16(values: number[]) {
  const bytes = new Uint8Array(values.length * 2);
  values.forEach((value, index) => {
    bytes[index * 2] = value & 255;
    bytes[index * 2 + 1] = value >>> 8;
  });
  return btoa(String.fromCharCode(...bytes));
}

function definitionFor(shape: RadiationGridShape, pitchCoordinatesSin = [0.2, 0.8]): RadiationBeltDefinition {
  return {
    count: shape.radialCount * shape.magneticLocalTimeCount,
    energiesKev: [88.349],
    pitchCoordinate: pitchCoordinatesSin.at(-1)!,
    pitchCoordinatesSin,
    pitchAnglesDegrees: pitchCoordinatesSin.map((value) => Math.asin(value) * 180 / Math.PI),
    pitchResolvedOrdering: "equatorial-point-major, pitch-index-minor",
    innerBoundaryRe: 1,
    encoding: {
      scale: "log10",
      minimum: -2,
      maximum: 9,
      quantity: "differential electron flux",
      units: "model-native differential flux",
    },
  };
}

const FIXTURE_FLUX_BASE = 30000;

function gridFrame(
  shape: RadiationGridShape,
  radii = Array.from({ length: shape.radialCount }, (_, index) => index + 2),
  distortMappedMlt = true,
  pitchCount = 2,
): RadiationBeltFrame {
  const coordinateValues: number[] = [];
  const nativeFlux: number[] = [];
  const pitchFlux: number[] = [];
  for (let radialIndex = 0; radialIndex < shape.radialCount; radialIndex += 1) {
    for (let mltIndex = 0; mltIndex < shape.magneticLocalTimeCount; mltIndex += 1) {
      const pointIndex = radialIndex * shape.magneticLocalTimeCount + mltIndex;
      // A small radial-dependent distortion proves topology does not assume circular rings.
      const mlt = (
        mltIndex * 24 / shape.magneticLocalTimeCount
        + (distortMappedMlt ? radialIndex * 0.05 : 0)
      ) % 24;
      coordinateValues.push(Math.round(radii[radialIndex]! * 1000), Math.round(mlt * 1000));
      // Above the default display flux floor (3/11 of the 0..65535 range), so
      // these topology fixtures exercise the same window production uses.
      nativeFlux.push(FIXTURE_FLUX_BASE + pointIndex * 100);
      for (let pitchIndex = 0; pitchIndex < pitchCount; pitchIndex += 1) {
        pitchFlux.push(FIXTURE_FLUX_BASE + pointIndex * 100 + (pitchIndex + 1) * 10);
      }
    }
  }
  return {
    coordinatesU16: littleEndianU16(coordinateValues),
    electronFluxU16: { "88.349": littleEndianU16(nativeFlux) },
    pitchResolvedElectronFluxU16: { "88.349": littleEndianU16(pitchFlux) },
  };
}

function minimumIndexedTriangleAreaSquared(geometry: ReturnType<typeof createNativeEquatorialRadiationGeometry>) {
  const positions = geometry.getAttribute("position");
  const indices = geometry.index!;
  let minimum = Number.POSITIVE_INFINITY;
  for (let index = 0; index < indices.count; index += 3) {
    const a = indices.getX(index);
    const b = indices.getX(index + 1);
    const c = indices.getX(index + 2);
    const ab = [positions.getX(b) - positions.getX(a), positions.getY(b) - positions.getY(a), positions.getZ(b) - positions.getZ(a)];
    const ac = [positions.getX(c) - positions.getX(a), positions.getY(c) - positions.getY(a), positions.getZ(c) - positions.getZ(a)];
    const cross = [
      ab[1]! * ac[2]! - ab[2]! * ac[1]!,
      ab[2]! * ac[0]! - ab[0]! * ac[2]!,
      ab[0]! * ac[1]! - ab[1]! * ac[0]!,
    ];
    minimum = Math.min(minimum, cross.reduce((total, value) => total + value * value, 0) / 4);
  }
  return minimum;
}

describe("RBE equatorial coordinates and native surface", () => {
  it("uses mapped equatorial radius/MLT and the standard GSM MLT orientation", () => {
    const shape = { radialCount: 1, magneticLocalTimeCount: 2 };
    const definition = definitionFor(shape);
    const frame: RadiationBeltFrame = {
      coordinatesU16: littleEndianU16([4000, 12000, 2000, 18000]),
      electronFluxU16: { "88.349": littleEndianU16([0, 65535]) },
      pitchResolvedElectronFluxU16: { "88.349": littleEndianU16([1000, 2000, 3000, 4000]) },
    };
    const coordinates = decodeRadiationBeltCoordinates(definition, frame);
    expect([...coordinates.equatorialRadiusRe]).toEqual([4, 2]);
    expect([...coordinates.equatorialMagneticLocalTimeHours]).toEqual([12, 18]);
    expect(equatorialRadiationPosition(4, 12).toArray()).toEqual([4, 0, 0]);
    expect(equatorialRadiationPosition(4, 0).x).toBeCloseTo(-4);
    expect(equatorialRadiationPosition(4, 6).y).toBeCloseTo(-4);
    expect(equatorialRadiationPosition(4, 18).y).toBeCloseTo(4);
  });

  it("infers radial-major/MLT-minor topology from distorted mapped MLT recurrence", () => {
    const shape = { radialCount: 3, magneticLocalTimeCount: 4 };
    const definition = definitionFor(shape);
    const coordinates = decodeRadiationBeltCoordinates(definition, gridFrame(shape));
    expect(resolveRadiationGridShape(definition, coordinates)).toEqual(shape);
  });

  it("triangulates only adjacent native points into a wrapped annular surface", () => {
    const shape = { radialCount: 3, magneticLocalTimeCount: 4 };
    const definition = definitionFor(shape);
    const geometry = createNativeEquatorialRadiationGeometry(
      definition,
      gridFrame(shape),
      88.349,
      undefined,
      { gridShape: shape },
    );
    expect(geometry.getAttribute("position").count).toBe(12);
    expect(geometry.index?.count).toBe((shape.radialCount - 1) * shape.magneticLocalTimeCount * 6);
    expect([...geometry.getAttribute("sourcePointIndex").array]).toEqual([...Array(12).keys()]);
    expect(geometry.getAttribute("fluxValue").getX(7)).toBeCloseTo((FIXTURE_FLUX_BASE + 700) / 65535);
    expect(geometry.userData).toMatchObject({
      representation: "native-equatorial-neighbor-triangulation",
      fullNative3d: false,
      offEquatorMapping: false,
      sourceFluxPreservedAtVertices: true,
    });
    const position = geometry.getAttribute("position");
    for (let index = 0; index < position.count; index += 1) expect(position.getZ(index)).toBe(0);
    expect(minimumIndexedTriangleAreaSquared(geometry)).toBeGreaterThan(0);
    geometry.dispose();
  });

  it("drops zero-area faces where mapped source rings contain coincident coordinates", () => {
    const shape = { radialCount: 3, magneticLocalTimeCount: 4 };
    const geometry = createNativeEquatorialRadiationGeometry(
      definitionFor(shape),
      gridFrame(shape, [2, 3, 3], false),
      88.349,
      undefined,
      { gridShape: shape },
    );
    expect(geometry.index?.count).toBe(24);
    expect(minimumIndexedTriangleAreaSquared(geometry)).toBeGreaterThan(0);
    geometry.dispose();
  });
});

describe("dipole-mapped RBE trapped-volume shell", () => {
  it("uses r=L cos²(lambda) and preserves the first-invariant mirror relation", () => {
    const latitude = Math.PI / 3;
    const position = dipoleRadiationPosition(4, 12, latitude);
    expect(position.length()).toBeCloseTo(1);
    const equatorialPitchSin = 0.4;
    const mirror = dipoleMirrorLatitudeRadians(equatorialPitchSin);
    expect(equatorialPitchSin ** 2 * dipoleFieldRatio(mirror)).toBeCloseTo(1, 8);
    expect(dipoleMirrorLatitudeRadians(1)).toBe(0);
  });

  it("builds one indexed closed shell, not field-line point hairs or a forced pair of belts", () => {
    const shape = { radialCount: 3, magneticLocalTimeCount: 4 };
    const definition = definitionFor(shape);
    const geometry = createDipoleMappedRadiationGeometry(definition, gridFrame(shape), 88.349, {
      samplesPerHemisphere: 2,
      pitchIndex: 1,
      gridShape: shape,
    });
    expect(geometry.getAttribute("position").count).toBe(definition.count * 5);
    expect(geometry.index?.count).toBe(288);
    expect(geometry.getAttribute("equatorialPitchSin").array.every((value) => Math.abs(value - 0.8) < 1e-6)).toBe(true);
    expect(geometry.userData).toMatchObject({
      representation: "closed-centered-dipole-mapped-trapped-flux-shell",
      validSourcePointCount: definition.count,
      fieldModel: "centered-ideal-dipole",
      fullNative3d: false,
      forcedBeltCount: false,
    });
    const positions = geometry.getAttribute("position");
    const zValues = Array.from({ length: positions.count }, (_, index) => positions.getZ(index));
    expect(Math.min(...zValues)).toBeLessThan(0);
    expect(Math.max(...zValues)).toBeGreaterThan(0);
    expect(minimumIndexedTriangleAreaSquared(geometry)).toBeGreaterThan(0);
    // The selected point/pitch flux is repeated along its mapped shell and never synthesized.
    const sourceIndices = geometry.getAttribute("sourcePointIndex");
    const flux = geometry.getAttribute("fluxValue");
    for (let index = 0; index < flux.count; index += 1) {
      expect(flux.getX(index)).toBeCloseTo((FIXTURE_FLUX_BASE + sourceIndices.getX(index) * 100 + 20) / 65535);
    }
    geometry.dispose();
  });

  it("excludes loss-cone source rows and closes the surviving single volume at that edge", () => {
    const shape = { radialCount: 3, magneticLocalTimeCount: 4 };
    const definition = definitionFor(shape);
    const geometry = createDipoleMappedRadiationGeometry(
      definition,
      gridFrame(shape, [2, 4, 6]),
      88.349,
      { samplesPerHemisphere: 1, pitchIndex: 0, gridShape: shape },
    );
    expect(geometry.userData.validSourcePointCount).toBe(8);
    expect(Math.min(...geometry.getAttribute("sourcePointIndex").array)).toBe(4);
    expect(geometry.index?.count).toBeGreaterThan(0);
    geometry.dispose();
  });

  it("labels native interpolation and the mapped assumptions without claiming a second belt", () => {
    expect(RADIATION_BELT_VIEWS.nativeEquatorial.description).toContain("neighboring native");
    expect(RADIATION_BELT_VIEWS.dipoleMapped3d.label).toBe("PITCH-RESOLVED DIPOLE-MAPPED ELECTRON VOLUME");
    expect(RADIATION_BELT_VIEWS.dipoleMapped3d.description).toContain("not native 3-D");
    expect(RADIATION_BELT_VIEWS.dipoleMapped3d.description).toContain("no proton or synthetic inner belt");
    // The description must not go on claiming every channel is drawn now that
    // the layer opens on one, and it must still say the mapping is idealized.
    expect(RADIATION_BELT_VIEWS.dipoleMapped3d.description).toContain("ideal centered dipole");
    expect(RADIATION_BELT_VIEWS.dipoleMapped3d.description).not.toContain("All published RBE electron pitch channels");
  });

  it("opens on every published channel at once, not on one the visitor has to find", () => {
    // The layer used to open at 1.35 MeV, the one channel in which the slot
    // resolves on its own. That was defensible and it was still the wrong
    // first impression: switching the layer on and doing nothing else showed
    // the faintest of the four channels. The combined view is the one where
    // the two belts are there before any interaction at all.
    expect(DEFAULT_RADIATION_ENERGY_KEV).toBe(COMBINED_RADIATION_ENERGY_KEV);
    expect(isCombinedRadiationEnergy(DEFAULT_RADIATION_ENERGY_KEV)).toBe(true);
    // And it is not one of the published channels wearing a different name.
    for (const energy of [88.349, 452.75, 1345.7, 2320.1]) {
      expect(DEFAULT_RADIATION_ENERGY_KEV).not.toBe(energy);
    }
  });
});

describe("multi-pitch gyrotropic RBE reconstruction", () => {
  it("uses positive solid-angle pitch bins that close exactly over a hemisphere", () => {
    const weights = gyrotropicPitchBinWeights([0.2, 0.6, 0.95]);
    expect(weights).toHaveLength(3);
    expect(weights.every((value) => value > 0)).toBe(true);
    expect(weights.reduce((total, value) => total + value, 0)).toBeCloseTo(1, 12);
    expect(() => gyrotropicPitchBinWeights([0.6, 0.2])).toThrow(/strictly increasing/);
    expect(() => gyrotropicPitchBinWeights([0.2, 1.1])).toThrow(/outside/);
  });

  it("maps every published pitch channel into a separately weighted nested electron shell", () => {
    const shape = { radialCount: 3, magneticLocalTimeCount: 4 };
    const pitchCoordinates = [0.2, 0.6, 0.95];
    const definition = definitionFor(shape, pitchCoordinates);
    const reconstruction = createGyrotropicDipoleMappedRadiationShells(
      definition,
      gridFrame(shape, [4, 5, 6], true, pitchCoordinates.length),
      88.349,
      { samplesPerHemisphere: 2, gridShape: shape },
    );
    expect(reconstruction.shells).toHaveLength(pitchCoordinates.length);
    expect(reconstruction.shells.map((shell) => shell.pitchIndex)).toEqual([0, 1, 2]);
    expect(reconstruction.shells.reduce((total, shell) => total + shell.solidAngleWeight, 0)).toBeCloseTo(1, 12);
    expect(reconstruction.metadata).toMatchObject({
      representation: "multi-pitch-gyrotropic-centered-dipole-shells",
      sourcePitchChannelCount: 3,
      renderedPitchChannelCount: 3,
      particlePopulation: "RBE model electrons only",
      fullNative3d: false,
      nativeEquatorialViewPreserved: true,
      syntheticInnerBelt: false,
      protonPopulation: false,
    });
    expect(reconstruction.metadata.fluxMeaning).toContain("not particle-density");

    const lowPitchPositions = reconstruction.shells[0]!.geometry.getAttribute("position");
    const highPitchPositions = reconstruction.shells[2]!.geometry.getAttribute("position");
    const maximumAbsoluteZ = (positions: typeof lowPitchPositions) => Math.max(
      ...Array.from({ length: positions.count }, (_, index) => Math.abs(positions.getZ(index))),
    );
    expect(maximumAbsoluteZ(lowPitchPositions)).toBeGreaterThan(maximumAbsoluteZ(highPitchPositions));

    reconstruction.shells.forEach((shell) => {
      expect(shell.geometry.userData).toMatchObject({
        representation: "gyrotropic-pitch-bin-centered-dipole-shell",
        gyrotropicAssumption: true,
        northSouthPitchSymmetryAssumption: true,
        syntheticInnerBelt: false,
        protonPopulation: false,
      });
      expect(shell.geometry.userData.solidAngleWeight).toBeCloseTo(shell.solidAngleWeight);
      const sourceIndices = shell.geometry.getAttribute("sourcePointIndex");
      const flux = shell.geometry.getAttribute("fluxValue");
      for (let index = 0; index < flux.count; index += 1) {
        const expected = (FIXTURE_FLUX_BASE + sourceIndices.getX(index) * 100 + (shell.pitchIndex + 1) * 10) / 65535;
        expect(flux.getX(index)).toBeCloseTo(expected);
      }
      shell.geometry.dispose();
    });
  });
});

/**
 * A reduced stand-in for the shipped RBE grid: the same radial-major/MLT-minor
 * topology, the same inward extent into the model's ionospheric boundary, and a
 * radial flux profile with the structure the real MeV channels carry — an inner
 * belt, a slot, and an outer belt. Numbers are normalized 0..1 on the published
 * log10 encoding, so 0.2727 is 10^1 differential flux.
 */
const BELT_MLT_COUNT = 12;
const BELT_RADII = [
  1.04, 1.08, 1.13, 1.2, 1.28, 1.37, 1.5, 1.64, 1.79, 1.95,
  2.12, 2.3, 2.5, 2.72, 2.96, 3.22, 3.5, 3.9, 4.35, 4.85,
  5.4, 6.0, 6.6, 7.2, 7.9, 8.6,
];

/** Inner belt near L = 1.6, slot near L = 2.4, outer belt near L = 4.5. */
function twoBeltNormalizedFlux(radiusRe: number) {
  const inner = 0.62 * Math.exp(-(((radiusRe - 1.6) / 0.34) ** 2));
  const outer = 0.86 * Math.exp(-(((radiusRe - 4.5) / 1.35) ** 2));
  return Math.min(1, 0.02 + inner + outer);
}

function twoBeltDefinition(pitchCoordinatesSin = [0.05, 0.4, 0.75, 0.99]): RadiationBeltDefinition {
  return {
    count: BELT_RADII.length * BELT_MLT_COUNT,
    energiesKev: [1345.7],
    pitchCoordinate: pitchCoordinatesSin.at(-1)!,
    pitchCoordinatesSin,
    pitchAnglesDegrees: pitchCoordinatesSin.map((value) => Math.asin(value) * 180 / Math.PI),
    pitchResolvedOrdering: "equatorial-point-major, pitch-index-minor",
    // The shipped artifact publishes RBE's own ionospheric boundary here.
    innerBoundaryRe: 1.0157,
    gridShape: { radialCount: BELT_RADII.length, magneticLocalTimeCount: BELT_MLT_COUNT },
    encoding: {
      scale: "log10",
      minimum: -2,
      maximum: 9,
      quantity: "differential electron flux",
      units: "model-native differential flux",
    },
  };
}

function twoBeltFrame(pitchCount: number): RadiationBeltFrame {
  const coordinates: number[] = [];
  const native: number[] = [];
  const pitchResolved: number[] = [];
  BELT_RADII.forEach((radius) => {
    for (let mltIndex = 0; mltIndex < BELT_MLT_COUNT; mltIndex += 1) {
      coordinates.push(Math.round(radius * 1000), Math.round(mltIndex * 24 / BELT_MLT_COUNT * 1000));
      const value = Math.round(twoBeltNormalizedFlux(radius) * 65535);
      native.push(value);
      for (let pitchIndex = 0; pitchIndex < pitchCount; pitchIndex += 1) pitchResolved.push(value);
    }
  });
  return {
    coordinatesU16: littleEndianU16(coordinates),
    electronFluxU16: { "1345.7": littleEndianU16(native) },
    pitchResolvedElectronFluxU16: { "1345.7": littleEndianU16(pitchResolved) },
  };
}

/** Contiguous runs of radial rows that actually carry drawn triangles. */
function drawnRadialRuns(rows: Iterable<number>) {
  const sorted = [...new Set(rows)].sort((first, second) => first - second);
  const runs: Array<[number, number]> = [];
  sorted.forEach((row) => {
    const last = runs.at(-1);
    if (last && row === last[1] + 1) last[1] = row;
    else runs.push([row, row]);
  });
  return runs;
}

function nativeDrawnRuns(geometry: THREE.BufferGeometry) {
  const radialIndex = geometry.getAttribute("gridRadialIndex");
  const indices = geometry.index!;
  const rows: number[] = [];
  for (let index = 0; index < indices.count; index += 1) rows.push(radialIndex.getX(indices.getX(index)));
  return drawnRadialRuns(rows);
}

function indexedVertexRadii(geometry: THREE.BufferGeometry) {
  const positions = geometry.getAttribute("position");
  const indices = geometry.index!;
  const radii: number[] = [];
  for (let index = 0; index < indices.count; index += 1) {
    const vertex = indices.getX(index);
    radii.push(Math.hypot(positions.getX(vertex), positions.getY(vertex), positions.getZ(vertex)));
  }
  return radii;
}

describe("radiation-belt radial display scale", () => {
  const earth = 100;

  it("meets the globe at the surface, is strictly increasing, and matches the satellite altitude scale", () => {
    expect(radiationBeltDisplayRadius(1, earth)).toBeCloseTo(earth, 9);
    expect(radiationBeltDisplayRadius(0.5, earth)).toBeCloseTo(earth, 9);
    let previous = radiationBeltDisplayRadius(1, earth);
    for (let radiusRe = 1.01; radiusRe <= 14; radiusRe += 0.01) {
      const current = radiationBeltDisplayRadius(radiusRe, earth);
      expect(current).toBeGreaterThan(previous);
      previous = current;
    }
    // These are the globe's own altitude-scale values, pinned so a change to
    // `Globe.altitudeDisplayRadius` cannot silently desynchronize the belts
    // from the orbits they are meant to be compared against.
    const altitudeScale = (altitudeKm: number) => earth + Math.min(205, 28 * Math.log1p(altitudeKm / 350));
    expect(radiationBeltDisplayRadius(1 + 20200 / 6371, earth)).toBeCloseTo(altitudeScale(20200), 6); // GPS
    expect(radiationBeltDisplayRadius(1 + 35786 / 6371, earth)).toBeCloseTo(altitudeScale(35786), 6); // GEO
    expect(radiationBeltDisplayRadius(1 + 35786 / 6371, earth)).toBeGreaterThan(225);
    // Scale-free: doubling the rendered Earth doubles every belt radius.
    expect(radiationBeltDisplayRadius(4, 2 * earth)).toBeCloseTo(2 * radiationBeltDisplayRadius(4, earth), 9);
  });

  it("keeps the belts clear of the globe and keeps the slot legible", () => {
    // This is the assertion the shipped build fails. Under the geospace
    // compression the belt layer is currently given, 1.2 Re lands 1.24 scene
    // units above a 100-unit Earth and 7 Re lands at 120.6, so the whole belt
    // system renders as a translucent skin wrapped around the planet.
    const geospaceCompression = (radiusRe: number) => earth + 18 * Math.log1p(Math.max(0, radiusRe - 1) / 2.8);
    expect(geospaceCompression(1.2) - earth).toBeLessThan(2);
    expect(geospaceCompression(7) - geospaceCompression(1.2)).toBeLessThan(0.2 * earth);

    // The belt scale must stand the inner edge well off the globe, so nothing
    // is draped on it and nothing sits inside depth-buffer range of it.
    expect(radiationBeltDisplayRadius(1.2, earth) - earth).toBeGreaterThan(0.35 * earth);
    // A slot 0.75 Re wide (1.86 -> 2.61, the real 1.35 MeV gap) must survive.
    expect(radiationBeltDisplayRadius(2.61, earth) - radiationBeltDisplayRadius(1.86, earth))
      .toBeGreaterThan(0.1 * earth);
    // Inner belt and outer belt must not collapse onto each other.
    expect(radiationBeltDisplayRadius(7, earth) - radiationBeltDisplayRadius(1.2, earth))
      .toBeGreaterThan(0.8 * earth);
  });
});

describe("radiation-belt trapped display window", () => {
  it("converts the flux floor onto the published encoding", () => {
    const definition = twoBeltDefinition();
    expect(normalizedRadiationFluxFloor(definition.encoding)).toBeCloseTo(3 / 11, 12);
    expect(normalizedRadiationFluxFloor(definition.encoding, {
      ...RADIATION_BELT_DISPLAY_WINDOW,
      minimumLog10Flux: -2,
    })).toBe(0);
    expect(() => normalizedRadiationFluxFloor({ ...definition.encoding, maximum: -2 })).toThrow(/range is empty/);
  });

  it("draws two separated equatorial lobes and nothing on the globe", () => {
    const definition = twoBeltDefinition();
    const geometry = createNativeEquatorialRadiationGeometry(definition, twoBeltFrame(4), 1345.7);
    const runs = nativeDrawnRuns(geometry);
    expect(runs).toHaveLength(2);
    // Inner belt, then a slot, then the outer belt: the model's own structure.
    expect(BELT_RADII[runs[0]![0]]!).toBeGreaterThanOrEqual(RADIATION_BELT_DISPLAY_WINDOW.minimumEquatorialRadiusRe);
    expect(BELT_RADII[runs[0]![1]]!).toBeLessThan(2.3);
    expect(BELT_RADII[runs[1]![0]]!).toBeGreaterThan(2.6);
    expect(Math.min(...indexedVertexRadii(geometry)))
      .toBeGreaterThanOrEqual(RADIATION_BELT_DISPLAY_WINDOW.minimumEquatorialRadiusRe);
    expect(geometry.userData.displayWindow).toEqual(RADIATION_BELT_DISPLAY_WINDOW);
    geometry.dispose();
  });

  it("keeps every drawn native vertex clear of the rendered Earth under the belt scale", () => {
    const definition = twoBeltDefinition();
    const geometry = createNativeEquatorialRadiationGeometry(
      definition,
      twoBeltFrame(4),
      1345.7,
      (x, y, z) => {
        const radiusRe = Math.max(1e-6, Math.hypot(x, y, z));
        return new THREE.Vector3(x, y, z).multiplyScalar(radiationBeltDisplayRadius(radiusRe, 100) / radiusRe);
      },
    );
    expect(Math.min(...indexedVertexRadii(geometry))).toBeGreaterThan(140);
    geometry.dispose();
  });

  it("cuts the mapped shells at the trapping floor rather than RBE's ionospheric boundary", () => {
    const definition = twoBeltDefinition();
    // Production wiring: every published pitch channel, four latitude samples
    // per hemisphere, mirror caps open.
    const reconstruction = createGyrotropicDipoleMappedRadiationShells(definition, twoBeltFrame(4), 1345.7, {
      samplesPerHemisphere: 4,
      pointStride: 1,
      includeMirrorCaps: false,
    });
    expect(reconstruction.shells.length).toBeGreaterThan(0);
    reconstruction.shells.forEach((shell) => {
      const radii = indexedVertexRadii(shell.geometry);
      expect(radii.length).toBeGreaterThan(0);
      // Nothing at or under the surface, and nothing inside the trapping floor.
      expect(Math.min(...radii)).toBeGreaterThanOrEqual(RADIATION_BELT_DISPLAY_WINDOW.minimumMappedRadiusRe - 1e-9);
      expect(shell.geometry.userData.trappingFloorRe)
        .toBeCloseTo(RADIATION_BELT_DISPLAY_WINDOW.minimumMappedRadiusRe, 9);
      const rows = indexedSourceRows(shell.geometry);
      expect(drawnRadialRuns(rows).length).toBeGreaterThanOrEqual(1);
    });
    expect(reconstruction.metadata.displayWindow).toEqual(RADIATION_BELT_DISPLAY_WINDOW);
    expect(reconstruction.metadata.displayWindowMeaning).toContain("no geometry");
    reconstruction.shells.forEach((shell) => shell.geometry.dispose());
  });

  it("keeps the slot open in the mapped equatorially mirroring channel", () => {
    const definition = twoBeltDefinition();
    const geometry = createDipoleMappedRadiationGeometry(definition, twoBeltFrame(4), 1345.7, {
      samplesPerHemisphere: 4,
      includeMirrorCaps: false,
    });
    // With mirror caps open the shell is drawn as its radial walls, so a pair
    // of belts separated by a slot must produce four walls: the inner and outer
    // edge of the inner belt, then the inner and outer edge of the outer belt.
    const walls = drawnRadialRuns(indexedSourceRows(geometry));
    expect(walls).toHaveLength(4);
    expect(walls.every(([first, last]) => first === last)).toBe(true);
    const wallRadii = walls.map(([row]) => BELT_RADII[row]!);
    expect(wallRadii[0]!).toBeGreaterThanOrEqual(RADIATION_BELT_DISPLAY_WINDOW.minimumEquatorialRadiusRe);
    // The slot: the outer wall of the inner belt and the inner wall of the
    // outer belt must be separated by real model distance, not adjacent rows.
    expect(wallRadii[2]! - wallRadii[1]!).toBeGreaterThan(0.5);
    expect(wallRadii[3]!).toBeGreaterThan(wallRadii[2]!);
    geometry.dispose();
  });

  it("renders nothing rather than a floor-valued sheet when the channel is empty", () => {
    const definition = twoBeltDefinition();
    const frame = twoBeltFrame(4);
    const floorOnly = littleEndianU16(new Array(definition.count).fill(0));
    const geometry = createNativeEquatorialRadiationGeometry(
      definition,
      { ...frame, electronFluxU16: { "1345.7": floorOnly } },
      1345.7,
    );
    expect(geometry.index?.count).toBe(0);
    expect(geometry.userData.drawnSourcePointCount).toBe(0);
    geometry.dispose();
  });

  it("keeps the whole model domain when the window is opened, proving the cut is the only difference", () => {
    const definition = twoBeltDefinition();
    const geometry = createNativeEquatorialRadiationGeometry(definition, twoBeltFrame(4), 1345.7, undefined, {
      displayWindow: { minimumEquatorialRadiusRe: 1, minimumMappedRadiusRe: 1, minimumLog10Flux: -99 },
    });
    expect(nativeDrawnRuns(geometry)).toHaveLength(1);
    expect(Math.min(...indexedVertexRadii(geometry))).toBeCloseTo(BELT_RADII[0]!, 5);
    geometry.dispose();
  });

  it("rejects a window that would place belt geometry inside the Earth", () => {
    expect(() => resolveWindowFor({ minimumEquatorialRadiusRe: 0.5 })).toThrow(/at least 1 Re/);
    expect(() => resolveWindowFor({ minimumMappedRadiusRe: 0 })).toThrow(/at least 1 Re/);
    expect(() => resolveWindowFor({ minimumLog10Flux: Number.NaN })).toThrow(/finite/);
  });
});

describe("default radiation pitch channel", () => {
  it("defaults to the trapped, equatorially mirroring channel and never the loss cone", () => {
    expect(trappedPitchIndex([0.01002, 0.27682, 0.9489, 0.98827])).toBe(3);
    // Order-independent: a differently ordered grid must not default the
    // display to a 0.6-degree precipitating channel.
    expect(trappedPitchIndex([0.98827, 0.9489, 0.01002])).toBe(0);
    expect(() => trappedPitchIndex([])).toThrow(/empty/);

    const definition = twoBeltDefinition();
    const geometry = createDipoleMappedRadiationGeometry(definition, twoBeltFrame(4), 1345.7, {
      samplesPerHemisphere: 2,
      includeMirrorCaps: false,
    });
    expect(geometry.userData.pitchIndex).toBe(definition.pitchCoordinatesSin.length - 1);
    expect(geometry.userData.pitchCoordinateSin).toBeCloseTo(0.99, 9);
    geometry.dispose();
  });
});

function resolveWindowFor(overrides: Partial<typeof RADIATION_BELT_DISPLAY_WINDOW>) {
  return createNativeEquatorialRadiationGeometry(
    twoBeltDefinition(),
    twoBeltFrame(4),
    1345.7,
    undefined,
    { displayWindow: overrides },
  );
}

function indexedSourceRows(geometry: THREE.BufferGeometry) {
  const sourcePointIndex = geometry.getAttribute("sourcePointIndex");
  const indices = geometry.index!;
  const rows: number[] = [];
  for (let index = 0; index < indices.count; index += 1) {
    rows.push(Math.floor(sourcePointIndex.getX(indices.getX(index)) / BELT_MLT_COUNT));
  }
  return rows;
}

/**
 * The pitch grid the shipped RBE artifact actually publishes, so the numbers
 * below are the numbers on screen and not a convenient invention.
 *
 * The last entry is the one the layer used to open on alone: 81.216 degrees
 * equatorial pitch, which mirrors at 4.15 degrees of magnetic latitude.
 */
const PUBLISHED_PITCH_SIN = [
  0.01002, 0.03071, 0.06203, 0.08611, 0.16073, 0.27682,
  0.43083, 0.60149, 0.75379, 0.86379, 0.9489, 0.98827,
];

describe("pitch-angle quadrature in the local field", () => {
  it("reduces to the equatorial hemisphere weights at B/B_eq = 1", () => {
    const equatorial = gyrotropicPitchBinWeights(PUBLISHED_PITCH_SIN);
    const local = gyrotropicLocalPitchBinWeights(PUBLISHED_PITCH_SIN, 1);
    expect(local).toEqual(equatorial);
    expect(local.reduce((total, value) => total + value, 0)).toBeCloseTo(1, 12);
    expect(dipoleFieldRatio(0)).toBe(1);
  });

  it("sums to the span in cos(alpha_local) the bins cover, at every field ratio", () => {
    const edges = gyrotropicPitchBinEdgeAngles(PUBLISHED_PITCH_SIN);
    expect(edges[0]).toBe(0);
    expect(edges.at(-1)).toBe(Math.PI / 2);
    expect(edges).toHaveLength(PUBLISHED_PITCH_SIN.length + 1);
    // The quadrature is a telescoping sum of cos(alpha_local) across the bin
    // edges, so its total is fixed by the two outer edges alone. Both are the
    // same at every field ratio: a field-aligned particle is still field
    // aligned, and the 90-degree edge has either mirrored or is at 90 degrees.
    for (const fieldRatio of [1, 1.5, 4, 38.56, 1000]) {
      const weights = gyrotropicLocalPitchBinWeights(PUBLISHED_PITCH_SIN, fieldRatio);
      const total = weights.reduce((sum, value) => sum + value, 0);
      expect(total).toBeCloseTo(
        localPitchCosine(0, fieldRatio) - localPitchCosine(Math.PI / 2, fieldRatio),
        12,
      );
      expect(total).toBeCloseTo(1, 12);
      expect(weights.every((value) => value >= 0)).toBe(true);
    }
    expect(() => gyrotropicLocalPitchBinWeights(PUBLISHED_PITCH_SIN, 0.5)).toThrow(/at least 1/);
  });

  it("empties a bin exactly where its particles mirror", () => {
    // Channel 11 mirrors at 4.15 degrees; at any field ratio beyond
    // 1 / sin^2(alpha) its whole bin has turned around.
    const mirror = dipoleMirrorLatitudeRadians(0.98827);
    const justBelow = gyrotropicLocalPitchBinWeights(PUBLISHED_PITCH_SIN, dipoleFieldRatio(mirror * 0.5));
    const wellAbove = gyrotropicLocalPitchBinWeights(PUBLISHED_PITCH_SIN, dipoleFieldRatio(mirror * 4));
    expect(justBelow[11]).toBeGreaterThan(0);
    expect(wellAbove[11]).toBe(0);
    // At exactly the mirror condition the local pitch is 90 degrees; past it
    // the bin is gone outright.
    expect(localPitchCosine(Math.asin(0.98827), 1 / 0.98827 ** 2)).toBeLessThan(1e-7);
    expect(localPitchCosine(Math.asin(0.98827), 1.001 / 0.98827 ** 2)).toBe(0);
  });
});

describe("the loss cone is a function of L", () => {
  const mirrorLatitudes = PUBLISHED_PITCH_SIN.map((sine) => dipoleMirrorLatitudeRadians(sine));
  const FLOOR = 1.2;

  it("opens the footpoint latitude as the shell grows", () => {
    // acos(sqrt(floor / L)) exactly, and nothing is trapped at or inside it.
    expect(trappingFootpointLatitudeRadians(2, FLOOR)).toBeCloseTo(Math.acos(Math.sqrt(0.6)), 12);
    expect(trappingFootpointLatitudeRadians(4, FLOOR)).toBeCloseTo(Math.acos(Math.sqrt(0.3)), 12);
    expect(trappingFootpointLatitudeRadians(6, FLOOR)).toBeCloseTo(Math.acos(Math.sqrt(0.2)), 12);
    expect(trappingFootpointLatitudeRadians(1.2, FLOOR)).toBe(0);
    expect(trappingFootpointLatitudeRadians(1, FLOOR)).toBe(0);
    const latitudes = [1.5, 2, 4, 6, 8].map((radius) => trappingFootpointLatitudeRadians(radius, FLOOR));
    latitudes.forEach((latitude, index) => {
      if (index > 0) expect(latitude).toBeGreaterThan(latitudes[index - 1]!);
    });
  });

  it("traps strictly more of the published pitch grid at larger L, and never fewer", () => {
    const atTwo = trappedPitchIndicesAtRadius(mirrorLatitudes, 2, FLOOR);
    const atFour = trappedPitchIndicesAtRadius(mirrorLatitudes, 4, FLOOR);
    const atSix = trappedPitchIndicesAtRadius(mirrorLatitudes, 6, FLOOR);
    // Mirror latitude falls monotonically with channel index, so the trapped
    // set is always a suffix of the grid and growth is set-inclusion.
    expect(atTwo).toEqual([6, 7, 8, 9, 10, 11]);
    expect(atFour).toEqual([4, 5, 6, 7, 8, 9, 10, 11]);
    expect(atSix).toEqual([3, 4, 5, 6, 7, 8, 9, 10, 11]);
    expect(atFour.every((channel) => atSix.includes(channel))).toBe(true);
    expect(atTwo.every((channel) => atFour.includes(channel))).toBe(true);
    // And the outermost trapped mirror latitude therefore rises with L.
    const outermost = (indices: number[]) => Math.max(...indices.map((index) => mirrorLatitudes[index]!));
    expect(outermost(atTwo)).toBeLessThan(outermost(atFour));
    expect(outermost(atFour)).toBeLessThan(outermost(atSix));
    // Nothing is trapped where no field line clears the floor.
    expect(trappedPitchIndicesAtRadius(mirrorLatitudes, 1.2, FLOOR)).toEqual([]);
  });
});

describe("radiation mapper scene frame", () => {
  /** The production radiation mapper: shared radial ruler plus the GSM->scene swizzle. */
  const beltMapper = (x: number, y: number, z: number) => {
    const radius = Math.max(0.001, Math.hypot(x, y, z));
    const scale = radiationBeltDisplayRadius(radius, 100) / radius;
    return new THREE.Vector3(x, z, -y).multiplyScalar(scale);
  };

  it("derives the Earth radius and a round-tripping radial inverse from the mapper alone", () => {
    const frame = describeRadiationMapperFrame(beltMapper);
    expect(frame.earthSceneRadius).toBeCloseTo(100, 6);
    for (const radius of [1.2, 1.6, 2.4, 4.5, 8.6, 14]) {
      const scene = frame.sceneRadiusForRe(radius);
      expect(scene).toBeCloseTo(radiationBeltDisplayRadius(radius, 100), 9);
      expect(frame.radiusReForSceneRadius(scene)).toBeCloseTo(radius, 6);
    }
  });

  it("recovers the GSM axes through the scene swizzle", () => {
    const frame = describeRadiationMapperFrame(beltMapper);
    const toGsm = (x: number, y: number, z: number) =>
      beltMapper(x, y, z).applyMatrix3(frame.gsmFromLocal).normalize();
    expect(toGsm(2, 0, 0).x).toBeCloseTo(1, 9);
    expect(toGsm(0, 2, 0).y).toBeCloseTo(1, 9);
    expect(toGsm(0, 0, 2).z).toBeCloseTo(1, 9);
  });

  it("rejects the magnetosphere mapper's tail stretch, which only acts anti-sunward", () => {
    const stretched = (x: number, y: number, z: number) => {
      const mapped = beltMapper(x, y, z);
      if (x < 0) mapped.x *= 2;
      return mapped;
    };
    expect(() => describeRadiationMapperFrame(stretched)).toThrow(/isotropic/);
  });

  it("rejects a mapper whose scene radius is not strictly increasing", () => {
    const flat = (x: number, y: number, z: number) =>
      new THREE.Vector3(x, z, -y).normalize().multiplyScalar(100);
    expect(() => describeRadiationMapperFrame(flat)).toThrow(/strictly increasing/);
  });
});

describe("raymarched omnidirectional flux volume", () => {
  const beltMapper = (x: number, y: number, z: number) => {
    const radius = Math.max(0.001, Math.hypot(x, y, z));
    const scale = radiationBeltDisplayRadius(radius, 100) / radius;
    return new THREE.Vector3(x, z, -y).multiplyScalar(scale);
  };
  const mapperFrame = describeRadiationMapperFrame(beltMapper);
  const bake = bakeOmnidirectionalFluxVolume(
    twoBeltDefinition(),
    twoBeltFrame(4),
    1345.7,
    mapperFrame,
    { radialCount: 128, mltCount: 32, latitudeCount: 48 },
  );
  const encodingNormalized = (log10Flux: number) => (log10Flux + 2) / 11;
  // At 1.35 MeV the view's opacity floor is the layer's long-declared 10^1,
  // so the shoulder this profile is judged against is that floor — DERIVED
  // from this synthetic bake by the same load-time rule the browser runs,
  // rather than restated here or read out of a table.
  const beltOpacity = resolveRadiationVolumeOpacityForBake(
    1345.7,
    bake,
    twoBeltDefinition().encoding,
    mapperFrame.sceneRadiusForRe,
  );
  const gateStart = encodingNormalized(beltOpacity.opacityFloorLog10Flux);
  const colourCeiling = encodingNormalized(RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux);
  const equatorial = (radiusRe: number) =>
    sampleBakedVolume(bake, mapperFrame.sceneRadiusForRe(radiusRe), 6, 0);

  it("shows two belts and a transparent slot at 1.35 MeV without any boundary being drawn", () => {
    // Inner belt: value only about 0.09 below the per-point fixture flux; the
    // difference is log10 of the trapped solid angle — an integral, never a
    // threshold.
    expect(equatorial(1.6)).toBeGreaterThan(gateStart);
    expect(equatorial(1.6)).toBeCloseTo(0.61, 1);
    // Slot: far below the transparency shoulder, so the raymarcher adds
    // nothing there. The gap is the field's own.
    expect(equatorial(2.4)).toBeLessThan(gateStart);
    expect(equatorial(2.4)).toBeCloseTo(0.10, 1);
    // Outer belt, and above the top of the colour ramp, so it draws in the
    // palette's hot end while the inner belt stays in the cool end.
    expect(equatorial(4.5)).toBeGreaterThan(colourCeiling);
    expect(equatorial(4.5)).toBeCloseTo(0.88, 1);
    // Exactly two contiguous above-shoulder runs along the equatorial profile.
    let runs = 0;
    let inside = false;
    for (let step = 0; step <= 400; step += 1) {
      const sceneRadius = bake.sceneRadiusMinimum
        + (step / 400) * (bake.sceneRadiusMaximum - bake.sceneRadiusMinimum);
      const above = sampleBakedVolume(bake, sceneRadius, 6, 0) >= gateStart;
      if (above && !inside) runs += 1;
      inside = above;
    }
    expect(runs).toBe(2);
  });

  it("integrates linear flux, never the log-encoded attribute", () => {
    // Two channels six decades apart. A sum of fluxes is dominated by the
    // bright one; an average of the log-encoded attribute would land halfway
    // between them, which would be a geometric mean and simply wrong.
    const pitchSin = [0.6, 0.99];
    const encode = (log10Flux: number) => Math.round(((log10Flux + 2) / 11) * 65535);
    const shape = { radialCount: 2, magneticLocalTimeCount: 4 };
    const definition: RadiationBeltDefinition = {
      ...twoBeltDefinition(pitchSin),
      count: shape.radialCount * shape.magneticLocalTimeCount,
      gridShape: shape,
    };
    const coordinates: number[] = [];
    const pitchResolved: number[] = [];
    for (let radialIndex = 0; radialIndex < shape.radialCount; radialIndex += 1) {
      for (let mltIndex = 0; mltIndex < shape.magneticLocalTimeCount; mltIndex += 1) {
        coordinates.push(4000 + radialIndex * 1000, Math.round(mltIndex * 6000));
        pitchResolved.push(encode(0), encode(6));
      }
    }
    const frame: RadiationBeltFrame = {
      coordinatesU16: littleEndianU16(coordinates),
      electronFluxU16: { "1345.7": littleEndianU16(coordinates.map(() => encode(6)).slice(0, definition.count)) },
      pitchResolvedElectronFluxU16: { "1345.7": littleEndianU16(pitchResolved) },
    };
    const uniform = bakeOmnidirectionalFluxVolume(definition, frame, 1345.7, mapperFrame, {
      radialCount: 64, mltCount: 16, latitudeCount: 16,
    });
    const weights = gyrotropicPitchBinWeights(pitchSin);
    const expected = (Math.log10(weights[0]! * 10 ** 0 + weights[1]! * 10 ** 6) + 2) / 11;
    const sampled = sampleBakedVolume(uniform, mapperFrame.sceneRadiusForRe(4.5), 6, 0);
    expect(sampled).toBeCloseTo(expected, 2);
    // The geometric mean of the two channels would sit at 10^3, three decades
    // down, at a normalized value near 0.455 — nowhere near this.
    expect(Math.abs(sampled - 0.455)).toBeGreaterThan(0.2);
  });

  it("thins toward the mirror points and empties beyond the trapped population", () => {
    const at = (radiusRe: number, latitudeDegrees: number) =>
      sampleBakedVolume(bake, mapperFrame.sceneRadiusForRe(radiusRe), 6, latitudeDegrees * Math.PI / 180);
    // Walk up ONE field line (r = L cos^2 lambda at L = 1.5), so the source
    // flux is a constant and any fall-off is pure solid-angle quadrature:
    // the equatorially mirroring channel has turned around below 8 degrees.
    const alongShell = (latitudeDegrees: number) => {
      const latitude = latitudeDegrees * Math.PI / 180;
      return at(1.5 * Math.cos(latitude) ** 2, latitudeDegrees);
    };
    expect(alongShell(0)).toBeGreaterThan(alongShell(8));
    expect(alongShell(8)).toBeGreaterThan(0);
    // A pitch bin survives until its LOWER edge mirrors — the wide bins hold
    // particles below their nominal channel angle — so the honest zero sits
    // beyond every trapped bin's lower-edge mirror latitude. At 1.3 Re and
    // 60 degrees the field line is L = 5.2 and even the field-alignedmost
    // trapped bin's lower edge has turned around; the loss-cone channel is
    // excluded by the trapping rule, so nothing at all remains.
    expect(at(1.3, 60)).toBe(0);
    // A position whose field line leaves the model domain holds nothing.
    expect(at(2, 65)).toBe(0);
  });

  it("carries the source's absences through: no texel outside the model domain holds flux", () => {
    // A precomputed grid is a resampling, and resampling is interpolation.
    // Interpolation must never invent flux where the source had none: below
    // the trapping floor, or on field lines whose equatorial crossing lies
    // beyond the published grid's outer boundary.
    let nonzero = 0;
    for (let latitudeIndex = 0; latitudeIndex < bake.latitudeCount; latitudeIndex += 1) {
      const latitude = ((latitudeIndex + 0.5) / bake.latitudeCount) * bake.latitudeMaximumRadians;
      for (let radialIndex = 0; radialIndex < bake.radialCount; radialIndex += 1) {
        const sceneRadius = bake.sceneRadiusMinimum
          + ((radialIndex + 0.5) / bake.radialCount) * (bake.sceneRadiusMaximum - bake.sceneRadiusMinimum);
        const positionRadius = mapperFrame.radiusReForSceneRadius(sceneRadius);
        const shellRadius = positionRadius / Math.cos(latitude) ** 2;
        for (let mltIndex = 0; mltIndex < bake.mltCount; mltIndex += 1) {
          const value = bake.data[(latitudeIndex * bake.mltCount + mltIndex) * bake.radialCount + radialIndex]!;
          if (value === 0) continue;
          nonzero += 1;
          expect(positionRadius).toBeGreaterThanOrEqual(bake.trappingFloorRe - 1e-5);
          expect(shellRadius).toBeLessThanOrEqual(bake.equatorialRadiusMaximumRe + 1e-5);
        }
      }
    }
    expect(nonzero).toBeGreaterThan(0);
  });

  it("reports the legend's channel count from the same trapping rule the shells use", () => {
    const mirrors = twoBeltDefinition().pitchCoordinatesSin
      .map((sine) => dipoleMirrorLatitudeRadians(sine));
    const expected = trappedPitchIndicesAtRadius(mirrors, 8.6, bake.trappingFloorRe).length;
    expect(bake.integratedPitchChannelCount).toBe(expected);
    expect(expected).toBeGreaterThanOrEqual(3);
  });

  it("builds a raymarched mesh whose disclosures match what it draws", () => {
    const { mesh, bake: meshBake } = createRadiationVolumeMesh(
      twoBeltDefinition(),
      twoBeltFrame(4),
      1345.7,
      beltMapper,
      { radialCount: 64, mltCount: 16, latitudeCount: 16 },
    );
    const material = mesh.material as THREE.ShaderMaterial;
    expect(material.transparent).toBe(true);
    expect(material.depthWrite).toBe(false);
    expect(material.depthTest).toBe(false);
    expect(material.side).toBe(THREE.BackSide);
    expect(material.uniforms.sceneRadiusMinimum!.value).toBeCloseTo(meshBake.sceneRadiusMinimum, 9);
    expect(material.uniforms.sceneRadiusMaximum!.value).toBeCloseTo(meshBake.sceneRadiusMaximum, 9);
    // The colour ramp spans exactly the declared display range, 10^1 to
    // 10^5.5, on the encoding's normalized scale — not the encoding's own 11
    // decades — and it is the same range in every energy view.
    expect(material.uniforms.colourFloor!.value).toBeCloseTo((1 + 2) / 11, 6);
    expect(material.uniforms.colourSpan!.value).toBeCloseTo((5.5 - 1) / 11, 6);
    // The opacity shoulder is this view's own: at 1.35 MeV it sits exactly at
    // the layer's declared 10^1 display floor, so nothing is hidden to make
    // the slot at the energy the layer opens on.
    expect(material.uniforms.opacityFloor!.value).toBeCloseTo((1 + 2) / 11, 6);
    expect(material.uniforms.opacitySpan!.value).toBeCloseTo((5.5 - 1) / 11, 6);
    expect(material.uniforms.minimumTransmittance!.value).toBeCloseTo(0.06, 6);
    expect(material.uniforms.earthSceneRadius!.value).toBeCloseTo(100, 6);
    expect(mesh.userData.volumeRendering).toBe(true);
    expect(mesh.userData.isoSurface).toBe(false);
    expect(mesh.userData.representation).toBe("raymarched-omnidirectional-flux-centered-dipole-volume");
    expect(mesh.userData.transferMeaning).toContain("No threshold decides a boundary");
    expect(mesh.userData.assumptions.sourceCoverage).toContain("equatorial-only");
    expect(mesh.userData.syntheticInnerBelt).toBe(false);
    expect(mesh.userData.protonPopulation).toBe(false);
    // The proxy hull must contain the whole baked domain.
    const hull = mesh.geometry as THREE.SphereGeometry;
    expect(hull.parameters.radius).toBeGreaterThanOrEqual(meshBake.sceneRadiusMaximum);
    // The 3-D texture dies with the material, not with a leak.
    const texture = material.uniforms.fluxVolume!.value as THREE.Data3DTexture;
    let disposed = false;
    texture.addEventListener("dispose", () => { disposed = true; });
    material.dispose();
    expect(disposed).toBe(true);
  });

  it("labels the dipole field-line guides as the mapping's own geometry, not data", () => {
    const guides = createRadiationFieldLineGuides(beltMapper, { trappingFloorRe: 1.2 });
    expect(guides.userData.representation).toBe("centered-dipole-field-line-guides");
    expect(guides.userData.meaning).toContain("not data");
    const material = guides.material as THREE.LineBasicMaterial;
    expect(material.transparent).toBe(true);
    expect(material.opacity).toBeLessThan(0.3);
    expect(material.depthWrite).toBe(false);
    // Every vertex stays inside the belt region: above the trapping floor's
    // scene radius, below the outermost guide shell's.
    const positions = guides.geometry.getAttribute("position");
    expect(positions.count).toBeGreaterThan(100);
    const floor = radiationBeltDisplayRadius(1.2, 100) - 1e-3;
    const ceiling = radiationBeltDisplayRadius(6.5, 100) + 1e-3;
    for (let vertex = 0; vertex < positions.count; vertex += 1) {
      const radius = Math.hypot(positions.getX(vertex), positions.getY(vertex), positions.getZ(vertex));
      expect(radius).toBeGreaterThanOrEqual(floor);
      expect(radius).toBeLessThanOrEqual(ceiling);
    }
  });
});

describe("folding every published energy channel into one combined volume", () => {
  /** The two-belt fixture, republished at four channel energies with a spectrum. */
  function fourChannelArtifact(spectrumDecades: number[]) {
    const base = twoBeltDefinition();
    const energiesKev = [88.349, 452.75, 1345.7, 2320.1];
    const definition: RadiationBeltDefinition = { ...base, energiesKev };
    const single = twoBeltFrame(base.pitchCoordinatesSin.length);
    const span = base.encoding.maximum - base.encoding.minimum;
    const shift = (encoded: string, decades: number, count: number) => {
      const decoded = decodeRadiationFlux(encoded, count);
      const values: number[] = [];
      for (let index = 0; index < count; index += 1) {
        const log10 = base.encoding.minimum + decoded[index]! * span + decades;
        values.push(Math.round(
          Math.max(0, Math.min(1, (log10 - base.encoding.minimum) / span)) * 65535,
        ));
      }
      return littleEndianU16(values);
    };
    const pitchCount = base.pitchCoordinatesSin.length;
    const frame: RadiationBeltFrame = {
      coordinatesU16: single.coordinatesU16,
      electronFluxU16: Object.fromEntries(energiesKev.map((energy, index) =>
        [String(energy), shift(single.electronFluxU16["1345.7"]!, spectrumDecades[index]!, base.count)])),
      pitchResolvedElectronFluxU16: Object.fromEntries(energiesKev.map((energy, index) =>
        [String(energy), shift(single.pitchResolvedElectronFluxU16["1345.7"]!, spectrumDecades[index]!, base.count * pitchCount)])),
    };
    return { definition, frame };
  }

  it("reproduces a flat spectrum exactly, because a band average of one value is that value", () => {
    const { definition, frame } = fourChannelArtifact([0, 0, 0, 0]);
    const combined = combineRadiationEnergyChannels(definition, frame);
    const span = definition.encoding.maximum - definition.encoding.minimum;
    const source = decodeRadiationFlux(frame.electronFluxU16["1345.7"]!, definition.count);
    const folded = decodeRadiationFlux(
      combined.frame.electronFluxU16[String(COMBINED_RADIATION_ENERGY_KEV)]!,
      definition.count,
    );
    for (let index = 0; index < definition.count; index += 1) {
      // Within one quantization step of the artifact's own 16-bit encoding.
      expect(Math.abs(folded[index]! - source[index]!) * span).toBeLessThan(0.001);
    }
  });

  it("is a drop-in single-channel artifact every presentation can already draw", () => {
    const { definition, frame } = fourChannelArtifact([2, 1, 0, -1]);
    const combined = combineRadiationEnergyChannels(definition, frame);
    expect(combined.definition.energiesKev).toEqual([COMBINED_RADIATION_ENERGY_KEV]);
    // Geometry, pitch grid and encoding are untouched: only the flux changed.
    expect(combined.definition.count).toBe(definition.count);
    expect(combined.definition.gridShape).toEqual(definition.gridShape);
    expect(combined.definition.pitchCoordinatesSin).toEqual(definition.pitchCoordinatesSin);
    expect(combined.frame.coordinatesU16).toBe(frame.coordinatesU16);
    expect(Object.keys(combined.frame.pitchResolvedElectronFluxU16))
      .toEqual([String(COMBINED_RADIATION_ENERGY_KEV)]);
    expect(isCombinedRadiationEnergy(combined.definition.energiesKev[0]!)).toBe(true);
    // And it draws: the volume bake accepts it with no special case.
    const beltMapper = (x: number, y: number, z: number) => {
      const radius = Math.max(0.001, Math.hypot(x, y, z));
      return new THREE.Vector3(x, z, -y).multiplyScalar(radiationBeltDisplayRadius(radius, 100) / radius);
    };
    const bake = bakeOmnidirectionalFluxVolume(
      combined.definition,
      combined.frame,
      COMBINED_RADIATION_ENERGY_KEV,
      describeRadiationMapperFrame(beltMapper),
      { radialCount: 48, mltCount: 16, latitudeCount: 16 },
    );
    expect(bake.data.some((value) => value > 0)).toBe(true);
  });

  it("weights a falling spectrum toward the relativistic channels when asked for energy", () => {
    const { definition, frame } = fourChannelArtifact([2, 1, 0, -1]);
    const span = definition.encoding.maximum - definition.encoding.minimum;
    const read = (source: RadiationBeltFrame, key: string) =>
      definition.encoding.minimum
      + decodeRadiationFlux(source.electronFluxU16[key]!, definition.count)[10]! * span;
    const numberFlux = read(
      combineRadiationEnergyChannels(definition, frame, "numberFlux").frame,
      String(COMBINED_RADIATION_ENERGY_KEV),
    );
    const energyWeighted = read(
      combineRadiationEnergyChannels(definition, frame, "energyWeighted").frame,
      String(COMBINED_RADIATION_ENERGY_KEV),
    );
    // The spectrum falls with energy here, so weighting by energy moves the
    // answer DOWN toward the relativistic channels. That is the whole reason
    // the combined view uses it: the soft channel stops dominating.
    expect(energyWeighted).toBeLessThan(numberFlux);
    expect(numberFlux).toBeLessThan(read(frame, "88.349"));
    expect(energyWeighted).toBeGreaterThan(read(frame, "2320.1"));
  });
});
