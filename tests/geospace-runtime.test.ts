import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { GEOSPACE_SLICE_MASK } from "../src/geospace-slice-data";
import {
  ALL_RADIATION_PITCH_CHANNELS,
  GeospaceRuntime,
  OMNIDIRECTIONAL_RADIATION_PITCH,
} from "../src/geospace-runtime";
import {
  EARTH_SCENE_RADIUS,
  altitudeFromSatelliteDisplayRadius,
  satelliteDisplayRadius,
} from "../src/globe";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";
import type { GeospaceBundle, GeospaceField, GeospacePlane } from "../src/types";

function encodedBytes(values: number[]) {
  return btoa(String.fromCharCode(...values));
}

function littleEndianU16(values: number[]) {
  const bytes = new Uint8Array(values.length * 2);
  values.forEach((value, index) => {
    bytes[index * 2] = value & 255;
    bytes[index * 2 + 1] = value >>> 8;
  });
  return encodedBytes([...bytes]);
}

function littleEndianI16(values: number[]) {
  return littleEndianU16(values.map((value) => value < 0 ? value + 65536 : value));
}

const fields = ["density", "speed", "pressure", "magneticField"] as const satisfies readonly GeospaceField[];
const planes = ["equatorial", "meridional"] as const satisfies readonly GeospacePlane[];

function encodedPlane(values: number[], masks: number[]) {
  return {
    fieldsU16: Object.fromEntries(fields.map((field) => [field, littleEndianU16(values)])),
    fieldMasksU8: Object.fromEntries(fields.map((field) => [field, encodedBytes(masks)])),
  };
}

function encodedLines() {
  return {
    lineCount: 1,
    pointCount: 3,
    coordinatesI16: littleEndianI16([300, -30, 350, -20, 400, -10]),
    offsetsU16: littleEndianU16([0, 3]),
    speedU16: littleEndianU16([4000, 3000, 2000]),
  };
}

function encodedStructures(offset: number) {
  const plane = {
    bowShockRadiusU16: littleEndianU16([1200 + offset, 1100 + offset, 1000 + offset]),
    magnetopauseProxyRadiusU16: littleEndianU16([950 + offset, 900 + offset, 850 + offset]),
    projectedMagneticStreamlines: encodedLines(),
    projectedFlowStreamlines: encodedLines(),
  };
  return { equatorial: plane, meridional: plane };
}

function radiationFrame(offset: number) {
  const coordinates: number[] = [];
  const nativeFlux: number[] = [];
  const pitchResolvedFlux: number[] = [];
  [4, 5].forEach((radiusRe, radialIndex) => {
    [0, 6, 12, 18].forEach((mltHours, mltIndex) => {
      const pointIndex = radialIndex * 4 + mltIndex;
      coordinates.push(radiusRe * 1000, mltHours * 1000);
      // Above the radiation-belt display flux floor (10^1 on the published
      // log10 encoding, 3/11 of the uint16 range), so this fixture exercises
      // the same trapped-region window production draws with.
      nativeFlux.push(20000 + pointIndex * 1000 + offset);
      pitchResolvedFlux.push(
        20000 + pointIndex * 1000 + offset,
        21000 + pointIndex * 1000 + offset,
      );
    });
  });
  return {
    coordinatesU16: littleEndianU16(coordinates),
    electronFluxU16: { "100": littleEndianU16(nativeFlux) },
    pitchResolvedElectronFluxU16: {
      "100": littleEndianU16(pitchResolvedFlux),
    },
  };
}

function bundle(): GeospaceBundle {
  const valuesAtStart = [0, 16384, 32768, 65535];
  const valuesAtEnd = [65535, 49152, 32768, 0];
  const masksAtStart = [GEOSPACE_SLICE_MASK.clippedLow, 0, 0, GEOSPACE_SLICE_MASK.missing];
  const masksAtEnd = [GEOSPACE_SLICE_MASK.clippedHigh, 0, 0, 0];
  const frame = (
    validAt: string,
    values: number[],
    masks: number[],
    offset: number,
  ) => ({
    validAt,
    runAt: "2026-08-06T00:00:00Z",
    leadMinutes: offset === 0 ? 0 : 20,
    planes: Object.fromEntries(planes.map((plane) => [plane, encodedPlane(values, masks)])),
    structures: encodedStructures(offset),
    radiationBelt: radiationFrame(offset),
  });
  return {
    schema: 1,
    generatedAt: "2026-08-06T00:21:00Z",
    status: "model",
    model: "test SWMF",
    coordinateSystem: "GSM for MHD planes; magnetic local time/L shell for RBE",
    source: { name: "NOAA test", url: "https://example.test", cadence: "20 minutes" },
    planes: Object.fromEntries(planes.map((plane) => [plane, {
      count: 4,
      coordinatesI16: littleEndianI16([300, -100, 600, -100, 300, 100, 600, 100]),
      boundsRe: [3, 6, -1, 1],
    }])),
    fieldEncodings: {
      density: { scale: "log10", minimum: -3, maximum: 2, units: "amu/cm³" },
      speed: { scale: "linear", minimum: 0, maximum: 2000, units: "km/s" },
      pressure: { scale: "log10", minimum: -5, maximum: 4, units: "nPa" },
      magneticField: { scale: "log10", minimum: -1, maximum: 4, units: "nT" },
    },
    fieldMaskEncoding: {
      storage: "uint8 base64",
      flags: { missing: 1, clippedLow: 2, clippedHigh: 4 },
    },
    displayModes: { default: "smooth", smooth: "gap aware", native: "source points" },
    structures: {
      status: "model-derived-proxies",
      coordinateSystem: "GSM",
      anglesDegrees: [-20, 0, 20],
      radiusEncoding: { storage: "uint16", scaleRe: 0.01, missingValue: 65535 },
      streamlineEncoding: { storage: "compact", scaleRe: 0.01, flowSpeedScaleKps: 0.1 },
    },
    radiationBelt: {
      count: 8,
      energiesKev: [100],
      pitchCoordinate: 0.8,
      pitchCoordinatesSin: [0.2, 0.8],
      pitchAnglesDegrees: [11.537, 53.13],
      pitchResolvedOrdering: "equatorial-point-major, pitch-index-minor",
      innerBoundaryRe: 1.0157,
      gridShape: { radialCount: 2, magneticLocalTimeCount: 4 },
      encoding: {
        scale: "log10",
        minimum: -2,
        maximum: 9,
        quantity: "differential electron flux",
        units: "cm⁻² s⁻¹ sr⁻¹ MeV⁻¹",
      },
    },
    frames: [
      frame("2026-08-06T00:00:00Z", valuesAtStart, masksAtStart, 0),
      frame("2026-08-06T00:20:00Z", valuesAtEnd, masksAtEnd, 20),
    ],
    caveat: "test",
  } as unknown as GeospaceBundle;
}

describe("GeospaceRuntime simulation-time field selection", () => {
  it("interpolates only within coverage and preserves missing and saturation masks", () => {
    const parent = new THREE.Group();
    const runtime = new GeospaceRuntime({ bundle: bundle(), parent, displayMode: "native", field: "pressure", plane: "both" });
    const state = runtime.setSimulationTime(new Date("2026-08-06T00:10:00Z"));
    expect(state).toMatchObject({ status: "ready", interpolationFraction: 0.5 });
    expect(parent.children).toContain(runtime.group);
    expect(runtime.cutGroup.children).toHaveLength(2);

    const points = runtime.cutGroup.children[0] as THREE.Points;
    const values = [...points.geometry.getAttribute("fieldValue").array];
    const masks = [...points.geometry.getAttribute("sourceMask").array];
    expect(values[0]).toBeCloseTo(0.5);
    expect(masks[0]! & GEOSPACE_SLICE_MASK.clippedLow).toBeTruthy();
    expect(masks[0]! & GEOSPACE_SLICE_MASK.clippedHigh).toBeTruthy();
    expect(masks[0]! & GEOSPACE_SLICE_MASK.interpolated).toBeTruthy();
    expect(Number.isNaN(values[3])).toBe(true);
    expect(masks[3]! & GEOSPACE_SLICE_MASK.missing).toBeTruthy();

    const legend = runtime.getLegendMetadata();
    expect(legend.field.range).toMatchObject({
      scale: "log10",
      encodedMinimum: -5,
      units: "nPa",
    });
    expect(legend.field.range.physicalMinimum).toBeCloseTo(1e-5);
    expect(legend.field.missingCount).toBe(2);
    expect(legend.field.clippedLowCount).toBe(2);
    expect(legend.field.clippedHighCount).toBe(2);
    expect(legend.field.representation).toContain("never a fabricated full volume");

    expect(runtime.setSimulationTime(new Date("2026-08-05T23:59:00Z"))).toMatchObject({
      status: "no-data",
      reason: "before-coverage",
    });
    expect(runtime.cutGroup.children).toHaveLength(0);
    expect(runtime.radiationGroup.children).toHaveLength(0);
    runtime.dispose();
  });

  it("opens on mass density, the field whose cut separates shock, sheath and cavity at one glance", () => {
    // Decided against the live 2026-08-09 frames, not by argument: on the
    // speed ramp the sheath and the cavity are both slow, so the two regions
    // merge and the magnetopause disappears. Density shows the shock jump,
    // the bright compressed sheath band, and the sharp cavity edge as three
    // distinct features — the textbook cross-section's own anatomy.
    const runtime = new GeospaceRuntime({ bundle: bundle() });
    expect(runtime.field).toBe("density");
    runtime.dispose();
  });

  it("opens on the meridional cut, and actually draws only that plane", () => {
    // The noon-midnight plane is the view every textbook figure of this
    // system uses — the reference cross-section the field-first layer exists
    // to reproduce from real data. Two cuts at once read as an X of
    // intersecting sheets, so "both" is a choice, never the default. This
    // asserts what is drawn, not just what the property says.
    const runtime = new GeospaceRuntime({ bundle: bundle(), displayMode: "native" });
    expect(runtime.plane).toBe("meridional");
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    expect(runtime.cutGroup.children).toHaveLength(1);
    expect(runtime.cutGroup.children[0]!.userData.plane).toBe("meridional");
    runtime.dispose();
  });

  it("makes unsupported temporal gaps explicit rather than holding a stale frame", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), maximumInterpolationGapMs: 5 * 60_000 });
    expect(runtime.setSimulationTime(new Date("2026-08-06T00:10:00Z"))).toMatchObject({
      status: "no-data",
      reason: "frame-gap",
    });
    runtime.dispose();
  });

  it("holds the latest operational frame briefly and reports its exact age", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), operationalEdgeHoldMs: 30 * 60_000 });
    expect(runtime.setSimulationTime(new Date("2026-08-06T00:27:00Z"))).toMatchObject({
      status: "ready",
      sourceFrames: ["2026-08-06T00:20:00Z", "2026-08-06T00:20:00Z"],
      edgeHoldMinutes: 7,
    });
    expect(runtime.setSimulationTime(new Date("2026-08-06T00:51:00Z"))).toMatchObject({
      status: "no-data",
      reason: "after-coverage",
    });
    runtime.dispose();
  });

  it("switches independently between a smooth supported field and the native source grid", () => {
    const runtime = new GeospaceRuntime({
      bundle: bundle(),
      displayMode: "smooth",
      plane: "equatorial",
      smoothing: { spacingRe: 1, maximumSupportDistanceRe: 4, minimumRadiusRe: 0 },
    });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    expect(runtime.cutGroup.children).toHaveLength(1);
    expect(runtime.cutGroup.children[0]!.name).toContain("smooth");
    expect(runtime.getLegendMetadata().field.interpolatedCount).toBeGreaterThan(0);
    runtime.setDisplayMode("native");
    expect(runtime.cutGroup.children[0]!.name).toContain("native");
    expect((runtime.cutGroup.children[0] as THREE.Points).geometry.getAttribute("position").count).toBe(4);
    runtime.setPlane("meridional");
    expect(runtime.cutGroup.children[0]!.userData.plane).toBe("meridional");
    runtime.dispose();
  });

  it("draws the smoothed field as a filled surface and the native grid as its own points", () => {
    // The point-cloud presentation hid the one thing the plasma field shows
    // on its own: a discontinuity. As separated dots the bow shock's density
    // and speed jump reads as texture; as a filled surface it reads as the
    // boundary it is. The native adaptive grid stays a point cloud, because
    // there the sample positions themselves are the data.
    const runtime = new GeospaceRuntime({
      bundle: bundle(),
      displayMode: "smooth",
      plane: "equatorial",
      smoothing: { spacingRe: 1, maximumSupportDistanceRe: 4, minimumRadiusRe: 0 },
    });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    const mesh = runtime.cutGroup.children[0] as THREE.Mesh;
    expect(mesh.type).toBe("Mesh");
    const index = mesh.geometry.getIndex();
    expect(index).not.toBeNull();
    expect(index!.count).toBeGreaterThan(0);
    // A triangle exists only where all three corners are supported samples: a
    // masked cell is a hole in the surface, never an interpolation.
    const validity = mesh.geometry.getAttribute("dataValid");
    for (let corner = 0; corner < index!.count; corner += 1) {
      expect(validity.getX(index!.getX(corner))).toBe(1);
    }
    runtime.setDisplayMode("native");
    expect(runtime.cutGroup.children[0]!.type).toBe("Points");
    runtime.dispose();
  });
});

describe("GeospaceRuntime structures and corrected RBE views", () => {
  it("keeps boundary proxies and projected vector paths explicitly separate from native cuts", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), displayMode: "native", plane: "both" });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    // Each named region of the textbook cross-section is its own group, so a
    // caller can show the bow shock without the cut planes it used to be
    // welded to.
    // The default is the cross-section: one curve per published cut plane,
    // because a closed loft seen from outside reads as a single blob and hides
    // the three regions it is made of.
    expect(runtime.structureDisplay).toBe("cross-section");
    expect(runtime.bowShockGroup.children.map((child) => child.name)).toEqual([
      "model-derived-bow-shock-curve-equatorial",
      "model-derived-bow-shock-curve-meridional",
    ]);
    expect(runtime.magnetopauseProxyGroup.children.map((child) => child.name)).toEqual([
      "model-derived-magnetopause-curve-equatorial",
      "model-derived-magnetopause-curve-meridional",
    ]);
    expect(runtime.magnetosheathGroup.children.map((child) => child.name)).toEqual([
      "model-derived-magnetosheath-band-equatorial",
      "model-derived-magnetosheath-band-meridional",
    ]);
    expect(runtime.bowShockGroup.children[0]!.userData).toMatchObject({
      status: "published-profile-in-its-own-cut-plane",
      region: "bowShock",
    });
    expect(runtime.magnetosheathGroup.children[0]!.userData).toMatchObject({
      status: "region-between-two-published-profiles",
    });

    runtime.setStructureDisplay("surface");
    // Each cap now carries its own rim as well as its shell. The published
    // extraction stops at 70 degrees either side of the subsolar point, and a
    // translucent shell that simply stopped read as two disconnected patches
    // from an oblique camera. The edge is drawn so the surface looks like what
    // it is: a dayside cap, not a closed boundary.
    expect(runtime.bowShockGroup.children.map((child) => child.name).sort())
      .toEqual(["bowShock-published-edge", "model-derived-bow-shock-proxy"]);
    expect(runtime.magnetopauseProxyGroup.children.map((child) => child.name).sort())
      .toEqual(["magnetopauseProxy-published-edge", "model-derived-magnetopause-proxy"]);
    expect(runtime.magnetosheathGroup.children.map((child) => child.name))
      .toEqual(["model-derived-magnetosheath-region"]);
    expect(runtime.bowShockGroup.children.find((child) => child.name.endsWith("proxy"))!.userData)
      .toMatchObject({
      status: "model-derived-two-cut-loft",
      fullVolume: false,
    });
    runtime.setStructureDisplay("cross-section");
    expect(runtime.magneticStreamlineGroup.children).toHaveLength(2);
    expect(runtime.flowStreamlineGroup.children).toHaveLength(2);
    expect(runtime.flowAdvectionGroup.children).toHaveLength(1);
    const tracers = runtime.flowAdvectionGroup.children[0] as THREE.Points;
    const before = [...tracers.geometry.getAttribute("position").array];
    runtime.setModelAdvectionTime(10);
    const after = [...tracers.geometry.getAttribute("position").array];
    expect(after).not.toEqual(before);
    expect(tracers.geometry.getAttribute("flowSpeedKps").count).toBeGreaterThan(0);
    expect(runtime.getLegendMetadata().structures).toMatchObject({
      boundaryStatus: "model-derived-proxies",
      flowSpeedUnits: "km/s",
    });
    expect(runtime.getLegendMetadata().structures.flowSpeedRange).toEqual([200, 400]);
    runtime.dispose();
  });

  it("exposes pitch-resolved native-equatorial and explicitly dipole-mapped views", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationPitchIndex: 1 });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    expect(runtime.radiationChoices).toMatchObject({
      energiesKev: [100],
      pitchCoordinatesSin: [0.2, 0.8],
    });
    expect(runtime.radiationGroup.children[0]!.name).toBe("rbe-model-native-equatorial-flux");
    expect(runtime.radiationGroup.children[0]).toBeInstanceOf(THREE.Mesh);
    const native = runtime.radiationGroup.children[0] as THREE.Mesh;
    expect(native.geometry.getAttribute("position").count).toBe(8);
    expect(native.geometry.getAttribute("fluxValue").getX(0)).toBeCloseTo(21020 / 65535);
    runtime.setRadiationPitchIndex(0);
    runtime.setRadiationView("dipoleMapped3d");
    // One selected channel means exactly one shell. Stacking every channel is
    // what buried the belts, so it may never happen by default.
    expect(runtime.radiationGroup.children).toHaveLength(1);
    expect(runtime.radiationGroup.children.map((child) => child.name)).toEqual([
      "rbe-gyrotropic-dipole-pitch-shell-0",
    ]);
    const mapped = runtime.radiationGroup.children[0] as THREE.Mesh;
    expect(mapped.userData).toMatchObject({
      status: "model-derived-mapping",
      fullNative3d: false,
      selectedPitch: true,
      particlePopulation: "RBE model electrons only",
    });
    expect(mapped.geometry.getAttribute("position").count).toBeGreaterThan(8);
    // The lone shell carries no highlight tint and no shell-count opacity term.
    expect((mapped.material as THREE.ShaderMaterial).uniforms.highlightStrength!.value).toBe(0);
    expect((mapped.material as THREE.ShaderMaterial).uniforms.opacityScale!.value).toBe(1);
    expect((mapped.material as THREE.ShaderMaterial).uniforms.fadeMirrorEdges!.value).toBe(0);
    expect(runtime.getLegendMetadata().radiation).toMatchObject({
      energyKev: 100,
      pitchIndex: 0,
      pitchCoordinateSin: 0.2,
      view: "dipoleMapped3d",
      viewLabel: "SINGLE-PITCH-CHANNEL DIPOLE-MAPPED BOUNCE SHELL",
      title: "single-pitch-channel differential electron flux",
      viewStatus: "model-derived-mapping",
      sourcePitchChannelCount: 2,
      displayedPitchChannelCount: 1,
      pitchMode: "single",
      selectedPitchEmphasized: true,
      particlePopulation: "RBE model electrons only",
    });
    runtime.dispose();
    expect(runtime.group.parent).toBeNull();
    expect(runtime.group.children).toHaveLength(0);
  });

  // Two regressions this guards, both of which have shipped. Stacking every
  // channel buried the belts, because superimposed translucent shells fill the
  // volume whatever each one's shape is. Opening on the single near-90-degree
  // channel replaced that with a flat annulus, because that channel mirrors at
  // 4.15 degrees. Neither may come back as the default.
  it("opens the mapped view on the omnidirectional integration, not one channel and not a stack", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));

    expect(runtime.radiationPitchMode).toBe("omnidirectional");
    expect(runtime.radiationPitchIndex).toBe(OMNIDIRECTIONAL_RADIATION_PITCH);
    // The raymarched volume plus its dipole field-line guides, which must say
    // they are the mapping's own geometry rather than data.
    expect(runtime.radiationGroup.children).toHaveLength(2);
    expect(runtime.radiationGroup.children[0]!.name).toBe("rbe-omnidirectional-flux-volume");
    expect(runtime.radiationGroup.children[0]!.userData.volumeRendering).toBe(true);
    expect(runtime.radiationGroup.children[1]!.name).toBe("rbe-dipole-field-line-guides");
    expect(runtime.radiationGroup.children[1]!.userData.meaning).toContain("not data");
    expect(runtime.getLegendMetadata().radiation).toMatchObject({
      pitchMode: "omnidirectional",
      viewLabel: "OMNIDIRECTIONAL DIPOLE-MAPPED ELECTRON VOLUME",
      title: "omnidirectional differential electron flux",
      sourcePitchChannelCount: 2,
      // The emphasized channel still names a real published channel, so no
      // legend field goes blank in a mode that selects none of them.
      pitchIndex: 1,
      pitchCoordinateSin: 0.8,
      selectedPitchEmphasized: false,
    });
    // The equatorial-only limitation survives the change and is carried, not
    // dropped, and it says what the latitude variation is and is not.
    const radiation = runtime.getLegendMetadata().radiation!;
    expect(radiation.sourceCoverage).toContain("equatorial-only");
    expect(radiation.alongFieldInterpretation).toContain("not a transport solution");
    runtime.dispose();
  });

  it("keeps one published channel reachable as its own bounce shell", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    // 0.8 is the largest published sin(alpha) in this fixture: the trapped,
    // near-90-degree channel, not the loss-cone one at index 0.
    runtime.setRadiationPitchIndex(1);

    expect(runtime.radiationPitchMode).toBe("single");
    expect(runtime.radiationGroup.children).toHaveLength(1);
    expect(runtime.radiationGroup.children[0]!.name).toBe("rbe-gyrotropic-dipole-pitch-shell-1");
    expect(runtime.getLegendMetadata().radiation).toMatchObject({
      pitchMode: "single",
      displayedPitchChannelCount: 1,
      sourcePitchChannelCount: 2,
      pitchIndex: 1,
      pitchCoordinateSin: 0.8,
    });
    runtime.dispose();
  });

  it("keeps the stacked all-channel reconstruction reachable, and says so in the legend", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    runtime.setRadiationPitchIndex(ALL_RADIATION_PITCH_CHANNELS);

    expect(runtime.radiationPitchMode).toBe("all");
    expect(runtime.radiationGroup.children.length).toBeGreaterThan(1);
    expect(runtime.getLegendMetadata().radiation).toMatchObject({
      pitchMode: "all",
      displayedPitchChannelCount: 2,
      // Even with no single channel selected, the legend still names the
      // emphasized one rather than going blank.
      pitchIndex: 1,
      pitchCoordinateSin: 0.8,
      selectedPitchEmphasized: true,
    });
    runtime.dispose();
  });

  it("falls back to the omnidirectional integration for an unusable selection", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationPitchIndex: 97 });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    expect(runtime.radiationPitchIndex).toBe(OMNIDIRECTIONAL_RADIATION_PITCH);
    runtime.setRadiationPitchIndex(Number.NaN);
    expect(runtime.radiationPitchIndex).toBe(OMNIDIRECTIONAL_RADIATION_PITCH);
    runtime.setRadiationPitchIndex(-7);
    expect(runtime.radiationPitchIndex).toBe(OMNIDIRECTIONAL_RADIATION_PITCH);
    runtime.dispose();
  });

  // A documented earlier defect: an alpha floor made every surface partly
  // opaque, so accumulated haze rather than flux decided what the viewer saw.
  // In the raymarched volume the equivalent guarantee is that extinction is
  // multiplied by a gate that is exactly zero below the transparency shoulder,
  // and nothing adds an alpha floor on top of the accumulated result.
  it("lets flux alone set opacity — no floor, no shell-count term", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    const material = (runtime.radiationGroup.children[0] as THREE.Mesh).material as THREE.ShaderMaterial;
    expect(material.uniforms.opacityFloor!.value).toBeGreaterThan(0);
    expect(material.fragmentShader).toContain("float opacityCoordinate = clamp((value - opacityFloor) / opacitySpan, 0.0, 1.0);");
    expect(material.fragmentShader).toContain("float sigma = extinction * pow(opacityCoordinate, opacityCurveExponent);");
    expect(material.fragmentShader).not.toMatch(/alpha\s*=\s*max\(/);
    runtime.dispose();
  });
});

describe("radiation geometry is rebuilt only when its inputs change", () => {
  const firstFrame = new Date("2026-08-06T00:02:00Z");
  const laterInSameFrame = new Date("2026-08-06T00:07:00Z");
  const secondFrame = new Date("2026-08-06T00:19:00Z");

  it("keeps the same meshes across simulation steps inside one RBE frame", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(firstFrame);
    const built = [...runtime.radiationGroup.children];
    expect(built.length).toBeGreaterThan(0);

    // Five simulated seconds at a time is what the globe feeds in; RBE only
    // changes every twenty minutes, so none of these may recreate anything.
    for (let step = 1; step <= 12; step += 1) {
      runtime.setSimulationTime(new Date(firstFrame.getTime() + step * 5_000));
      expect(runtime.radiationGroup.children).toEqual(built);
    }
    runtime.setSimulationTime(laterInSameFrame);
    expect(runtime.radiationGroup.children).toEqual(built);
    runtime.dispose();
  });

  it("still rebuilds when the structure frame, energy, pitch or view changes", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(firstFrame);
    const built = runtime.radiationGroup.children[0];

    runtime.setSimulationTime(secondFrame);
    const afterFrameChange = runtime.radiationGroup.children[0];
    expect(afterFrameChange).not.toBe(built);

    // The bundle's published pitch coordinate selects index 1 by default, so
    // move to the other channel to make this a real change.
    runtime.setRadiationPitchIndex(0);
    const afterPitchChange = runtime.radiationGroup.children[0];
    expect(afterPitchChange).not.toBe(afterFrameChange);

    // Re-selecting what is already selected must not recreate anything.
    runtime.setRadiationPitchIndex(0);
    expect(runtime.radiationGroup.children[0]).toBe(afterPitchChange);

    runtime.setRadiationView("nativeEquatorial");
    expect(runtime.radiationGroup.children[0]).not.toBe(afterPitchChange);
    expect(runtime.radiationGroup.children).toHaveLength(1);
    runtime.dispose();
  });

  it("rebuilds after the visuals have been cleared by leaving coverage", () => {
    const runtime = new GeospaceRuntime({ bundle: bundle(), radiationView: "dipoleMapped3d" });
    runtime.setSimulationTime(firstFrame);
    expect(runtime.radiationGroup.children.length).toBeGreaterThan(0);

    runtime.setSimulationTime(new Date("2026-08-05T23:00:00Z"));
    expect(runtime.radiationGroup.children).toHaveLength(0);

    runtime.setSimulationTime(firstFrame);
    expect(runtime.radiationGroup.children.length).toBeGreaterThan(0);
    runtime.dispose();
  });
});

describe("one radial ruler for the whole scene", () => {
  it("draws a geostationary satellite inside the magnetopause nose", () => {
    const geo = satelliteDisplayRadius(35786);
    const magnetopauseNose = radiationBeltDisplayRadius(9.5, EARTH_SCENE_RADIUS);
    expect(geo).toBeLessThan(magnetopauseNose);
    // The regression: the geospace compression that shipped put the nose at
    // 125.1 scene units, inside a geostationary orbit drawn at 229.8.
    expect(EARTH_SCENE_RADIUS + 18 * Math.log1p((9.5 - 1) / 2.8)).toBeLessThan(geo);
  });

  it("puts satellites and the geospace layers on the same curve", () => {
    for (const radiusRe of [1.5, 2, 4, 6.6, 9.5, 20, 50]) {
      const altitudeKm = (radiusRe - 1) * 6371;
      expect(radiationBeltDisplayRadius(radiusRe, EARTH_SCENE_RADIUS))
        .toBeCloseTo(satelliteDisplayRadius(altitudeKm), 6);
    }
  });

  it("keeps the whole modelled volume inside the camera's reach", () => {
    // The SWMF reduction crops to -55..+25 Re along X and +/-35 Re across it,
    // and the Shue tail is cut at -50 Re along X, a physical radius near 56 Re.
    // There is no longer any per-axis stretch: the ruler alone decides reach.
    const corner = radiationBeltDisplayRadius(Math.hypot(55, 35), EARTH_SCENE_RADIUS);
    const tail = radiationBeltDisplayRadius(56, EARTH_SCENE_RADIUS);
    // Framing a radius costs distance = 1.1 * radius / tan(21 deg) ~ 2.87x, and
    // the orbit limit is controls.maxDistance = 2,200: the viewer must be able
    // to pull back far enough to hold the whole drawn volume.
    const framingDistance = (Math.max(corner, tail) * 1.1) / Math.tan((21 * Math.PI) / 180);
    expect(framingDistance).toBeLessThan(2200);
  });

  it("round-trips a satellite radius back to its altitude", () => {
    for (const altitudeKm of [0, 420, 20200, 35786]) {
      expect(altitudeFromSatelliteDisplayRadius(satelliteDisplayRadius(altitudeKm)))
        .toBeCloseTo(altitudeKm, 6);
    }
  });
});

describe("GeospaceRuntime archived history frames", () => {
  /**
   * The published sequence now carries bigmem-archived frames in front of the
   * live NOAA window. Those frames deliberately omit the BATS-R-US cut-plane
   * fields, which only feed the hidden `layer-geospace` control and are about
   * 70% of a frame's bytes. `preparedField()` indexes `frame.planes[plane]`
   * without guarding `frame.planes`, so the archive publishes an empty planes
   * object rather than dropping the key; these tests pin that contract, because
   * getting it wrong takes the visible radiation-belt layer down too.
   */
  function withArchivedHistory() {
    const live = bundle();
    const archived = live.frames.map((frame, index) => ({
      ...frame,
      validAt: index === 0 ? "2026-08-05T22:00:00Z" : "2026-08-06T00:00:00Z",
      planes: {},
    })).slice(0, 1);
    return { ...live, frames: [...archived, ...live.frames] } as unknown as GeospaceBundle;
  }

  it("draws the radiation belt at an archived time and draws no cut plane", () => {
    const runtime = new GeospaceRuntime({ bundle: withArchivedHistory() });
    const state = runtime.setSimulationTime(new Date("2026-08-05T22:00:00Z"));
    expect(state.status).toBe("ready");
    expect(runtime.radiationGroup.children.length).toBeGreaterThan(0);
    expect(runtime.cutGroup.children).toHaveLength(0);
    // And the legend can say WHY there is no field, instead of publishing a
    // zero count with no explanation: the archive omitted the planes.
    expect(runtime.getLegendMetadata().field.fieldPublished).toBe(false);
    runtime.dispose();
  });

  it("reports the archived frame's own valid time rather than blanking it", () => {
    const runtime = new GeospaceRuntime({ bundle: withArchivedHistory() });
    runtime.setSimulationTime(new Date("2026-08-05T22:00:00Z"));
    expect(runtime.getLegendMetadata().radiation?.validAt).toBe("2026-08-05T22:00:00Z");
    runtime.dispose();
  });

  it("still refuses a time before the archive begins", () => {
    const runtime = new GeospaceRuntime({ bundle: withArchivedHistory() });
    const state = runtime.setSimulationTime(new Date("2026-08-05T12:00:00Z"));
    expect(state).toMatchObject({ status: "no-data", reason: "before-coverage" });
    expect(runtime.radiationGroup.children).toHaveLength(0);
    runtime.dispose();
  });

  it("keeps the live window's cut planes working", () => {
    const runtime = new GeospaceRuntime({ bundle: withArchivedHistory(), displayMode: "native", plane: "both" });
    runtime.setSimulationTime(new Date("2026-08-06T00:20:00Z"));
    expect(runtime.cutGroup.children).toHaveLength(2);
    expect(runtime.getLegendMetadata().field.fieldPublished).toBe(true);
    runtime.dispose();
  });
});
