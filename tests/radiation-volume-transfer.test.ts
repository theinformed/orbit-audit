/**
 * What the radiation-belt volume LOOKS like, as a number, in EVERY energy view.
 *
 * The layer's acceptance question has always been perceptual — "do two belts
 * and a dark slot read from the camera a visitor actually has" — and the
 * answer had been decided by looking at screenshots. It shipped as one
 * uniform purple donut anyway, twice, because the two things that decide the
 * answer are not visible in the source: the ray-integrated opacity profile
 * across the picture, and where the drawn flux lands on the colour ramp.
 *
 * So both are measured here, against a pinned real RBE frame, by marching
 * rays through the real bake with the real transfer constants. The march is a
 * transcription of the fragment shader, so the test also asserts that the
 * shader still contains the expressions it is transcribing — if the shader is
 * rewritten, this test fails loudly rather than quietly measuring a fiction.
 *
 * Since 2026-08-09 there are five views, not one: the four published channels
 * and the combined band integral. They share ONE colour scale — that is pinned
 * here, because it was an explicit instruction and a per-energy "improvement"
 * would quietly break comparability between channels. They do NOT share an
 * opacity setting, and the table of per-view settings in
 * `src/radiation-belt-volume.ts` is pinned against the profile each one
 * actually produces.
 */
import * as THREE from "three";
import { radiusFromSharedDisplayRadius, sharedDisplayRadius } from "../src/radial-ruler";
import { describe, expect, it } from "vitest";

import fixtureSource from "./data/geospace-volume-fixture.json?raw";

import {
  RADIATION_INNER_COLOR_HEX,
  RADIATION_OUTER_COLOR_HEX,
  smFromGsmMatrix,
  shaderReFromDrawn,
  shaderDrawnFromRe,
  RADIATION_VOLUME_RAMP_TEXELS,
  RADIATION_VOLUME_FLOOR_DERIVATION,
  RADIATION_VOLUME_OPACITY_BY_VIEW,
  RADIATION_VOLUME_TRANSFER,
  bakeOmnidirectionalFluxVolume,
  createRadiationVolumeMesh,
  deriveRadiationVolumeOpacityFloor,
  describeRadiationMapperFrame,
  resolveRadiationVolumeOpacity,
  resolveRadiationVolumeOpacityForBake,
  sampleBakedVolume,
  RADIATION_BELT_HUE_SPLIT,
} from "../src/radiation-belt-volume";
import type { RadiationVolumeBake } from "../src/radiation-belt-volume";
import {
  COMBINED_RADIATION_ENERGY_KEV,
  RADIATION_ENERGY_COMBINATION,
  combineRadiationEnergyChannels,
  radiationBeltDisplayRadius,
  radiationChannelIntegrationWeights,
} from "../src/radiation-belt";
import type { RadiationBeltDefinition, RadiationBeltFrame } from "../src/radiation-belt";

const EARTH_SCENE_RADIUS = 100;
const RELATIVISTIC_KEV = 1345.7;

const mapper = (x: number, y: number, z: number) => {
  const radius = Math.max(1e-9, Math.hypot(x, y, z));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  return new THREE.Vector3(x * scale, y * scale, z * scale);
};

const fixture = JSON.parse(fixtureSource) as {
  radiationBelt: RadiationBeltDefinition;
  frames: Array<{ validAt: string; radiationBelt: RadiationBeltFrame }>;
};
const definition = fixture.radiationBelt;
const frame = fixture.frames[0]!.radiationBelt;
const mapperFrame = describeRadiationMapperFrame(mapper);

const encoding = definition.encoding;
const encodingSpan = encoding.maximum - encoding.minimum;
const normalized = (log10Flux: number) =>
  THREE.MathUtils.clamp((log10Flux - encoding.minimum) / encodingSpan, 0, 1);
/** The colour coordinate: one range, shared by every view, by instruction. */
const colourFloor = normalized(RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux);
const colourSpan = normalized(RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux) - colourFloor;
const minimumTransmittance = 1 - RADIATION_VOLUME_TRANSFER.maximumAccumulatedOpacity;

/** The bake resolution every recorded profile in the shipped table was measured at. */
const BAKE = { radialCount: 128, mltCount: 32, latitudeCount: 56 } as const;

const combined = combineRadiationEnergyChannels(definition, frame, RADIATION_ENERGY_COMBINATION);

/** One bake per shipped view, keyed by the energy the table is keyed by. */
const bakes = new Map<number, RadiationVolumeBake>(
  RADIATION_VOLUME_OPACITY_BY_VIEW.map((view) => [
    view.energyKev,
    view.energyKev === COMBINED_RADIATION_ENERGY_KEV
      ? bakeOmnidirectionalFluxVolume(combined.definition, combined.frame, view.energyKev, mapperFrame, BAKE)
      : bakeOmnidirectionalFluxVolume(definition, frame, view.energyKev, mapperFrame, BAKE),
  ]),
);

/**
 * The layer's own default camera, from `globe.focusRadiationObliqueView()`:
 * GSM (0.8, 0.6, 0.55) with GSM north up. Rays are cast parallel, scanning
 * horizontally across the middle of the picture — the line a reader's eye
 * runs along when asking whether there are two belts.
 */
const camera = new THREE.Vector3(0.8, 0.6, 0.55).normalize().multiplyScalar(1600);
const forward = camera.clone().negate().normalize();
const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 0, 1)).normalize();

interface RayResult {
  /** Accumulated opacity, exactly what the shader writes to gl_FragColor.a. */
  alpha: number;
  /** Opacity-weighted mean position on the SHARED colour ramp along the ray. */
  colourMean: number;
}

function marchRay(
  bake: RadiationVolumeBake,
  impactParameter: number,
  opacityFloorLog10Flux: number,
  extinctionPerSceneUnit: number,
): RayResult {
  const opacityFloor = normalized(opacityFloorLog10Flux);
  const opacitySpan = Math.max(
    1e-6,
    normalized(RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux) - opacityFloor,
  );
  const origin = camera.clone().addScaledVector(right, impactParameter);
  const b = origin.dot(forward);
  const c = origin.dot(origin) - bake.sceneRadiusMaximum ** 2;
  const discriminant = b * b - c;
  if (discriminant < 0) return { alpha: 0, colourMean: 0 };
  const root = Math.sqrt(discriminant);
  const tNear = Math.max(-b - root, 0);
  let tFar = -b + root;
  const earthC = origin.dot(origin) - mapperFrame.earthSceneRadius ** 2;
  const earthDiscriminant = b * b - earthC;
  if (earthDiscriminant >= 0) {
    const earthRoot = Math.sqrt(earthDiscriminant);
    if (-b + earthRoot > 0 && -b - earthRoot < tFar) tFar = Math.max(-b - earthRoot, tNear);
  }
  if (tFar - tNear < 1e-4) return { alpha: 0, colourMean: 0 };

  const steps = 160;
  const stepLength = (tFar - tNear) / steps;
  let transmittance = 1;
  let weighted = 0;
  for (let step = 0; step < steps; step += 1) {
    const t = tNear + stepLength * (step + 0.5);
    const point = origin.clone().addScaledVector(forward, t);
    const radius = point.length();
    if (radius < bake.sceneRadiusMinimum || radius > bake.sceneRadiusMaximum) continue;
    const latitude = Math.abs(Math.asin(THREE.MathUtils.clamp(point.z / radius, -1, 1)));
    if (latitude >= bake.latitudeMaximumRadians) continue;
    const magneticLocalTime = ((Math.atan2(point.y, point.x) / (2 * Math.PI) + 0.5) * 24) % 24;
    const value = sampleBakedVolume(bake, radius, magneticLocalTime, latitude);
    const colourCoordinate = THREE.MathUtils.clamp((value - colourFloor) / colourSpan, 0, 1);
    const opacityCoordinate = THREE.MathUtils.clamp((value - opacityFloor) / opacitySpan, 0, 1);
    if (opacityCoordinate <= 0) continue;
    const sigma = extinctionPerSceneUnit
      * opacityCoordinate ** RADIATION_VOLUME_TRANSFER.opacityCurveExponent;
    const sampleAlpha = 1 - Math.exp(-sigma * stepLength);
    weighted += transmittance * sampleAlpha * colourCoordinate;
    transmittance *= 1 - sampleAlpha;
    if (transmittance < minimumTransmittance + 0.008) break;
  }
  const alpha = 1 - Math.max(transmittance, minimumTransmittance);
  return { alpha, colourMean: alpha > 0 ? weighted / alpha : 0 };
}

interface ScanRow { l: number; alpha: number; colourMean: number }

function scanView(
  bake: RadiationVolumeBake,
  opacityFloorLog10Flux: number,
  extinctionPerSceneUnit: number,
): ScanRow[] {
  const rows: ScanRow[] = [];
  for (let offset = mapperFrame.earthSceneRadius; offset <= bake.sceneRadiusMaximum; offset += 2) {
    const { alpha, colourMean } = marchRay(bake, offset, opacityFloorLog10Flux, extinctionPerSceneUnit);
    rows.push({ l: mapperFrame.radiusReForSceneRadius(offset), alpha, colourMean });
  }
  return rows;
}

const between = (rows: ScanRow[], low: number, high: number) =>
  rows.filter((row) => row.l >= low && row.l < high);
const brightest = (rows: ScanRow[]) =>
  rows.reduce((best, row) => (row.alpha > best.alpha ? row : best), rows[0]!);
const darkest = (rows: ScanRow[]) =>
  rows.reduce((worst, row) => (row.alpha < worst.alpha ? row : worst), rows[0]!);

/**
 * The three features of the picture, found the way a reader's eye finds them:
 * the brightest ray inside the inner belt's L range, the darkest ray between
 * the belts, and the brightest ray on the outer belt. The windows are wide
 * enough that the answer is found rather than assumed.
 */
function features(rows: ScanRow[]) {
  return {
    inner: brightest(between(rows, 1.2, 1.9)),
    slot: darkest(between(rows, 1.9, 3.0)),
    outer: brightest(between(rows, 3.0, 5.5)),
    peak: brightest(rows),
  };
}

/**
 * The floor each view is DRAWN with: derived from that view's own bake at
 * load time, exactly as the browser derives it. Nothing here reads a floor out
 * of the shipped table — that table is only the fallback, and the equivalence
 * between the two on this frame is itself asserted below.
 */
const resolved = new Map(
  RADIATION_VOLUME_OPACITY_BY_VIEW.map((view) => [
    view.energyKev,
    resolveRadiationVolumeOpacityForBake(
      view.energyKev,
      bakes.get(view.energyKev)!,
      encoding,
      mapperFrame.sceneRadiusForRe,
    ),
  ]),
);

/**
 * The inter-belt minimum, found by this test's own loop rather than by the
 * function under test, so the derivation is checked against an independent
 * reading of the same bake and not against itself.
 */
function independentInterBeltMinimum(bake: RadiationVolumeBake) {
  let minimum = Number.POSITIVE_INFINITY;
  for (let magneticLocalTime = 0; magneticLocalTime < 24; magneticLocalTime += 0.5) {
    for (let l = 2.0; l <= 3.6 + 1e-9; l += 0.02) {
      const value = sampleBakedVolume(bake, mapperFrame.sceneRadiusForRe(l), magneticLocalTime, 0)
        * encodingSpan + encoding.minimum;
      if (value < minimum) minimum = value;
    }
  }
  return minimum;
}

const scans = new Map<number, ScanRow[]>(
  RADIATION_VOLUME_OPACITY_BY_VIEW.map((view) => [
    view.energyKev,
    scanView(
      bakes.get(view.energyKev)!,
      resolved.get(view.energyKev)!.opacityFloorLog10Flux,
      view.extinctionPerSceneUnit,
    ),
  ]),
);

describe("the belt volume's ray-integrated opacity, from the layer's own default camera", () => {
  it.each(RADIATION_VOLUME_OPACITY_BY_VIEW.map((view) => [view.label, view] as const))(
    "%s produces exactly the profile its shipped tuning claims",
    (_label, view) => {
      const { inner, slot, outer } = features(scans.get(view.energyKev)!);
      const claimed = view.measuredProfile;
      // The table is documentation that has to stay true. Every number in it
      // is re-derived here from the real bake; a tuning change that forgets to
      // update the table fails this, and a table edited without re-measuring
      // fails it too.
      expect(inner.alpha).toBeCloseTo(claimed.innerAlpha, 2);
      expect(slot.alpha).toBeCloseTo(claimed.slotAlpha, 2);
      expect(outer.alpha).toBeCloseTo(claimed.outerAlpha, 2);
      expect(inner.l).toBeCloseTo(claimed.innerL, 1);
      expect(slot.l).toBeCloseTo(claimed.slotL, 1);
      expect(outer.l).toBeCloseTo(claimed.outerL, 1);
    },
  );

  it("lets no view sit on the opacity ceiling, which is what washed the Earth out at 88 keV", () => {
    for (const view of RADIATION_VOLUME_OPACITY_BY_VIEW) {
      const rows = scans.get(view.energyKev)!;
      for (const row of rows) {
        // A ray pinned at the cap is a ray whose brightness the flux no longer
        // decides. Before this pass, 88 keV pinned EVERY ray at the cap.
        expect(row.alpha).toBeLessThan(RADIATION_VOLUME_TRANSFER.maximumAccumulatedOpacity - 0.15);
      }
    }
  });

  it("keeps the peak, the slot and the peak at 1.35 MeV — not one plateau", () => {
    const { inner, slot, outer } = features(scans.get(RELATIVISTIC_KEV)!);
    expect(slot.alpha).toBeLessThan(inner.alpha);
    expect(slot.alpha).toBeLessThan(outer.alpha);
    expect(inner.l).toBeLessThan(1.75);
    expect(outer.l).toBeGreaterThan(2.4);
    // A ray aimed at the slot still crosses the outer belt in front of it and
    // behind it, so the slot can never go black from outside; what has to
    // survive is a real gap. The shipped build once managed 11% below the
    // inner belt and it read as one uniform donut.
    expect(1 - slot.alpha / outer.alpha).toBeGreaterThan(0.3);
    expect(1 - slot.alpha / inner.alpha).toBeGreaterThan(0.1);
  });

  it("keeps the peak, the slot and the peak in the combined volume too", () => {
    const { inner, slot, outer } = features(scans.get(COMBINED_RADIATION_ENERGY_KEV)!);
    expect(slot.alpha).toBeLessThan(inner.alpha);
    expect(slot.alpha).toBeLessThan(outer.alpha);
    // Both belts land where the model's own two-belt structure is.
    expect(inner.l).toBeLessThan(1.9);
    expect(outer.l).toBeGreaterThan(2.9);
    // And the slot is a real gap, not a rounding difference.
    expect(1 - slot.alpha / outer.alpha).toBeGreaterThan(0.20);
    expect(1 - slot.alpha / inner.alpha).toBeGreaterThan(0.15);
  });

  it("never puts a view's DRAWN floor above that view's own inter-belt minimum", () => {
    // The rule every floor is set by, re-derived here from the bakes and
    // checked against the floor the shader is actually given: the floor may
    // only remove flux BELOW the bottom of the slot. If it ever rises above
    // that minimum, the darkness between the belts stops being the model's and
    // starts being the threshold's — which is the one thing this layer exists
    // not to do. This is checked against the DERIVED floor, not against a
    // table, so it now guards the mechanism instead of five constants.
    for (const view of RADIATION_VOLUME_OPACITY_BY_VIEW) {
      const minimum = independentInterBeltMinimum(bakes.get(view.energyKev)!);
      const drawn = resolved.get(view.energyKev)!.opacityFloorLog10Flux;
      const allowed = Math.max(RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux, minimum);
      expect(drawn).toBeLessThanOrEqual(allowed + 1e-9);
      // ...and it is not needlessly far below it either, or the floor stops
      // doing the job the per-energy tuning exists for. One quantum of the
      // rounding rule, plus the clamp at the declared floor, is the whole gap.
      expect(drawn).toBeGreaterThan(allowed - RADIATION_VOLUME_FLOOR_DERIVATION.quantumDecades - 1e-9);
    }
  });

  it("draws no inner belt at 2.32 MeV, because the model has none there", () => {
    const { inner, slot, outer } = features(scans.get(2320.1)!);
    // The model's 2.32 MeV inner belt peaks at 10^0.84, below the layer's
    // 10^1 display floor. The honest picture is an outer belt and nothing
    // else, and the number that says so is that the inner ray and the slot
    // ray are the same to within a few percent.
    expect(Math.abs(1 - inner.alpha / slot.alpha)).toBeLessThan(0.1);
    expect(outer.alpha).toBeGreaterThan(1.6 * slot.alpha);
  });
});


/**
 * One row of the two-row colour ramp, read out of the texture the shader
 * actually samples rather than trusted from the palette constant. Half a texel
 * of sampler offset is why the endpoints are read directly.
 */
function readRow(material: THREE.ShaderMaterial, row: 0 | 1): string[] {
  const texture = material.uniforms.colourRamp!.value as THREE.DataTexture;
  const texels = texture.image.data as Uint8Array;
  const width = RADIATION_VOLUME_RAMP_TEXELS;
  const palette = row === 0 ? RADIATION_INNER_COLOR_HEX : RADIATION_OUTER_COLOR_HEX;
  return palette.map((_hex, index) => {
    const texel = row * width + Math.round((index / (palette.length - 1)) * (width - 1));
    return `#${[0, 1, 2]
      .map((channel) => texels[texel * 4 + channel]!.toString(16).padStart(2, "0"))
      .join("")}`;
  });
}

describe("the colour scale, which is the same in every energy view", () => {
  it("gives every view the same two endpoints and the same ramp", () => {
    const uniforms = RADIATION_VOLUME_OPACITY_BY_VIEW.map((view) => {
      const source = view.energyKev === COMBINED_RADIATION_ENERGY_KEV
        ? combined
        : { definition, frame };
      const { mesh } = createRadiationVolumeMesh(
        source.definition,
        source.frame,
        view.energyKev,
        mapper,
        { radialCount: 32, mltCount: 16, latitudeCount: 16 },
      );
      const material = mesh.material as THREE.ShaderMaterial;
      const record = {
        colourFloor: material.uniforms.colourFloor!.value as number,
        colourSpan: material.uniforms.colourSpan!.value as number,
        // Read the colour the SHADER would show at each stop's own position,
        // out of the lookup it samples, rather than trusting a uniform to hold
        // what the palette says. Half a texel of sampler offset is why the
        // first and last texel are read directly.
        // Two rows: v=0 the inner belt, v=1 the outer. Read BOTH, because the
        // shader samples both and a test that only read row 0 would not notice
        // the outer belt losing its ramp.
        stops: readRow(material, 0),
        outerStops: readRow(material, 1),
        opacityFloor: material.uniforms.opacityFloor!.value as number,
        extinction: material.uniforms.extinction!.value as number,
      };
      material.dispose();
      mesh.geometry.dispose();
      return record;
    });
    const first = uniforms[0]!;
    for (const entry of uniforms) {
      expect(entry.colourFloor).toBeCloseTo(first.colourFloor, 9);
      expect(entry.colourSpan).toBeCloseTo(first.colourSpan, 9);
      expect(entry.stops).toEqual([...RADIATION_INNER_COLOR_HEX]);
      expect(entry.outerStops).toEqual([...RADIATION_OUTER_COLOR_HEX]);
    }
    // ...and the endpoints are the declared ones, not the encoding's own.
    expect(first.colourFloor).toBeCloseTo(colourFloor, 9);
    expect(first.colourSpan).toBeCloseTo(colourSpan, 9);
    // The per-view knobs really are per view: at least two distinct floors and
    // two distinct extinctions ship, or the "tuned per energy" claim is false.
    expect(new Set(uniforms.map((entry) => entry.opacityFloor)).size).toBeGreaterThan(1);
    expect(new Set(uniforms.map((entry) => entry.extinction)).size).toBeGreaterThan(1);
  });

  it("colour-separates the two belts at 1.35 MeV instead of painting both the same midtone", () => {
    const { inner, outer } = features(scans.get(RELATIVISTIC_KEV)!);
    expect(inner.colourMean).toBeGreaterThan(0.05);
    // Keyed to the encoding's eleven decades instead of the displayed range,
    // these two came out 0.09 apart, which is why the whole layer once
    // rendered in one lavender midtone.
    expect(outer.colourMean - inner.colourMean).toBeGreaterThan(0.15);
  });

  it("puts the low-energy channels higher on the ramp than the relativistic ones", () => {
    // This is the entire point of holding the scale constant: colour then
    // carries the comparison between channels. 88 keV really does hold about
    // a hundred times the flux 2.32 MeV holds, and it has to look like it.
    const colourAt = (energyKev: number) => brightest(scans.get(energyKev)!).colourMean;
    expect(colourAt(88.349)).toBeGreaterThan(colourAt(452.75));
    expect(colourAt(452.75)).toBeGreaterThan(colourAt(RELATIVISTIC_KEV));
    expect(colourAt(RELATIVISTIC_KEV)).toBeGreaterThan(colourAt(2320.1));
  });
});

describe("the guard bites", () => {
  it("fails the 88 keV view if the pre-2026-08-09 single global tuning is restored", () => {
    // The setting every view used to share: the layer's 10^1 floor and
    // extinction 0.010. At 88 keV that is what produced "if I go to 88 keV the
    // entire earth is washed out" — every ray pinned at the opacity cap.
    const rows = scanView(bakes.get(88.349)!, 1.0, 0.010);
    const saturated = rows.filter(
      (row) => row.alpha >= RADIATION_VOLUME_TRANSFER.maximumAccumulatedOpacity - 0.15,
    );
    expect(saturated.length).toBeGreaterThan(rows.length / 2);
    const { inner, slot, outer } = features(rows);
    expect(1 - slot.alpha / outer.alpha).toBeLessThan(0.05);
    expect(1 - slot.alpha / inner.alpha).toBeLessThan(0.05);
  });

  it("fails the combined view if the colour ceiling is dropped back to 10^4", () => {
    // A ceiling at 10^4 cannot describe the 88 keV channel, which reaches
    // 10^5.33, so the top of the ramp would be unreachable in some views and
    // saturated in others — the two belts would still be drawn but the scale
    // would stop meaning one thing.
    const ceiling = RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux;
    let occupiedAboveOldCeiling = 0;
    for (const raw of bakes.get(88.349)!.data) {
      if (raw === 0) continue;
      if ((raw / 255) * encodingSpan + encoding.minimum > 4.0) occupiedAboveOldCeiling += 1;
    }
    expect(occupiedAboveOldCeiling).toBeGreaterThan(10_000);
    expect(ceiling).toBeGreaterThan(4.0);
  });

  it("admits when an energy has no measured tuning instead of pretending it does", () => {
    // Not a refusal: an untuned picture beats a blank layer if NOAA reprofiles
    // the RBE energy grid. But it must never claim to be measured. Only the
    // EXTINCTION is inherited now — the floor is derived from whatever field
    // is loaded, whatever energy it is published at.
    const inherited = resolveRadiationVolumeOpacity(700);
    expect(inherited.tuned).toBe(false);
    expect(inherited.reason).toContain("no measured tuning for 700 keV");
    // Nearest in LOG energy, which for 700 keV is the 453 keV channel.
    expect(inherited.extinctionPerSceneUnit)
      .toBe(resolveRadiationVolumeOpacity(452.75).extinctionPerSceneUnit);
    expect(inherited.fallbackFloorLog10Flux)
      .toBe(resolveRadiationVolumeOpacity(452.75).fallbackFloorLog10Flux);
    for (const view of RADIATION_VOLUME_OPACITY_BY_VIEW) {
      expect(resolveRadiationVolumeOpacity(view.energyKev).tuned).toBe(true);
    }
    // An untuned energy still gets a floor read off its own data, and says so.
    const untuned = resolveRadiationVolumeOpacityForBake(
      700, bakes.get(452.75)!, encoding, mapperFrame.sceneRadiusForRe,
    );
    expect(untuned.floorSource).toBe("derived-from-loaded-data");
    expect(untuned.reason).toContain("derived from this frame's own field");
    expect(untuned.reason).toContain("no measured extinction for 700 keV");
  });
});

describe("the combined volume's energy integral", () => {
  it("weights the four channels by their trapezoidal share of the published band", () => {
    const numberFlux = radiationChannelIntegrationWeights(definition.energiesKev, "numberFlux");
    // Trapezoid weights on a logarithmically spaced grid: 88 keV stands for
    // only the half-gap up to 453 keV, so it carries 8% of the band, not 25%.
    // That is exactly why a plain sum of the four channels is not a quantity.
    expect(numberFlux.reduce((sum, value) => sum + value, 0)).toBeCloseTo(1, 12);
    expect(numberFlux[0]).toBeCloseTo(0.0816, 3);
    expect(numberFlux[2]).toBeCloseTo(0.4184, 3);

    const energyWeighted = radiationChannelIntegrationWeights(definition.energiesKev, "energyWeighted");
    expect(energyWeighted.reduce((sum, value) => sum + value, 0)).toBeCloseTo(1, 12);
    // Weighting by energy multiplies the relativistic channels up: 88 keV
    // falls from 8% of the band to 0.6%, and the two MeV channels take 89%.
    expect(energyWeighted[0]).toBeCloseTo(0.0060, 3);
    expect(energyWeighted[2]! + energyWeighted[3]!).toBeCloseTo(0.888, 2);
    for (let index = 0; index < numberFlux.length; index += 1) {
      expect(energyWeighted[index]! / numberFlux[index]!)
        .toBeCloseTo(definition.energiesKev[index]! / 1204.4, 1);
    }
  });

  it("combines in physical flux, so the result is an integral and not a geometric mean", () => {
    // A weighted sum of the ENCODED values would be a weighted sum of
    // logarithms, which is a geometric mean — always below the true integral,
    // and by more the wider the spectrum. The combined channel must land
    // above the geometric mean of the four and below their weighted maximum.
    const weights = radiationChannelIntegrationWeights(definition.energiesKev, RADIATION_ENERGY_COMBINATION);
    const combinedBake = bakes.get(COMBINED_RADIATION_ENERGY_KEV)!;
    const channelBakes = definition.energiesKev.map((energy) => bakes.get(energy)!);
    const sceneRadius = mapperFrame.sceneRadiusForRe(4.0);
    const log10 = (bake: RadiationVolumeBake) =>
      sampleBakedVolume(bake, sceneRadius, 12, 0) * encodingSpan + encoding.minimum;
    const combinedLog10 = log10(combinedBake);
    const perChannel = channelBakes.map(log10);
    const geometricMean = perChannel.reduce((sum, value, index) => sum + weights[index]! * value, 0);
    const integral = Math.log10(
      perChannel.reduce((sum, value, index) => sum + weights[index]! * 10 ** value, 0),
    );
    expect(combinedLog10).toBeGreaterThan(geometricMean);
    expect(combinedLog10).toBeCloseTo(integral, 1);
    expect(combinedLog10).toBeLessThan(Math.max(...perChannel));
  });
});

describe("the march", () => {
  it("marches the same arithmetic the shader does", () => {
    const { mesh, opacity } = createRadiationVolumeMesh(definition, frame, RELATIVISTIC_KEV, mapper, {
      radialCount: 32, mltCount: 16, latitudeCount: 16,
    });
    const material = mesh.material as THREE.ShaderMaterial;
    expect(material.fragmentShader)
      .toContain("float colourCoordinate = clamp((value - colourFloor) / colourSpan, 0.0, 1.0);");
    expect(material.fragmentShader)
      .toContain("float opacityCoordinate = clamp((value - opacityFloor) / opacitySpan, 0.0, 1.0);");
    expect(material.fragmentShader)
      .toContain("float sigma = extinction * pow(opacityCoordinate, opacityCurveExponent);");
    // Colour takes a second coordinate: which belt the sample is in, from its
    // L about the dipole. Brightness is still the flux and nothing else.
    //
    // The L matters and this test used to pin the opposite of what its own
    // comment said: `smoothstep(..., dipoleRe)` compares two thresholds named
    // in L against the sample's LOCAL radius. r = L cos^2(latitude), so on the
    // L 3.6 shell the comparison crosses the inner-belt threshold at 39 degrees
    // of magnetic latitude and the outer belt's mirroring horns were painted in
    // the inner belt's hue. Pin the conversion, not just the call.
    expect(material.fragmentShader)
      .toContain("float shellRe = dipoleRe / max(cos(latitude) * cos(latitude), 1e-3);");
    expect(material.fragmentShader)
      .toContain("float belt = smoothstep(beltHueInnerL, beltHueOuterL, shellRe);");
    // The two disagree wherever the sample is off the magnetic equator, which
    // is the whole reason the shader cannot use the local radius: a point on
    // the outer belt's L 3.6 shell sits at 2.2 Re by 38.6 degrees of latitude.
    const shellRe = 3.6;
    const latitudeRad = Math.acos(Math.sqrt(RADIATION_BELT_HUE_SPLIT.innerL / shellRe));
    expect((latitudeRad * 180) / Math.PI).toBeCloseTo(38.58, 2);
    expect(material.fragmentShader)
      .toContain("accumulated += transmittance * sampleAlpha * fluxColor(colourCoordinate, belt);");
    const tuning = resolveRadiationVolumeOpacity(RELATIVISTIC_KEV);
    expect(material.uniforms.colourFloor!.value).toBeCloseTo(colourFloor, 9);
    expect(material.uniforms.colourSpan!.value).toBeCloseTo(colourSpan, 9);
    // The uniform carries the DERIVED floor the mesh reports, and on this
    // frame that is the same 10^1 the table falls back to.
    expect(material.uniforms.opacityFloor!.value)
      .toBeCloseTo(normalized(opacity.opacityFloorLog10Flux), 9);
    expect(opacity.opacityFloorLog10Flux).toBe(tuning.fallbackFloorLog10Flux);
    expect(opacity.floorSource).toBe("derived-from-loaded-data");
    expect(material.uniforms.extinction!.value).toBe(tuning.extinctionPerSceneUnit);
    expect(material.uniforms.opacityCurveExponent!.value)
      .toBe(RADIATION_VOLUME_TRANSFER.opacityCurveExponent);
    material.dispose();
    mesh.geometry.dispose();
  });
});

/**
 * The load-time floor derivation: the "value checker" Sean asked for.
 *
 * > "can we just have it drawn so that the van allen belts are just a little
 * > better shown? Like each time we load a dataset there should be some value
 * > checker which helps adjust the scale so that we see the belts just a
 * > little more clearly."
 *
 * The rule did not change — each view draws above its own deepest inter-belt
 * minimum, rounded down to the next 0.05 decade, never below 10^1 — but it now
 * runs against whatever field is loaded instead of having been run by hand
 * once. Two things therefore have to be true at the same time: it must produce
 * exactly the shipped numbers on the frame those numbers were measured on (so
 * the picture Sean approved does not move), and it must refuse, out loud, on
 * data it cannot read.
 */
describe("the opacity floor is derived from the data that is loaded", () => {
  it("reproduces every shipped floor on the frame the table was measured on", () => {
    // The equivalence that proves this pass changes no picture: the live
    // derivation, run on the pinned 2026-08-08T23:40Z frame, returns the same
    // five floors the static table shipped with.
    for (const view of RADIATION_VOLUME_OPACITY_BY_VIEW) {
      const derived = resolved.get(view.energyKev)!;
      expect(derived.opacityFloorLog10Flux).toBeCloseTo(view.fallbackFloorLog10Flux, 10);
      expect(derived.floorSource).toBe("derived-from-loaded-data");
      expect(derived.derivation.fallbackReason).toBeNull();
    }
  });

  it("reads the same field the same way at the browser's own bake resolution", () => {
    // A floor that moved with the texture size would make the picture a
    // function of the machine. The browser bakes 192x64x88; every other guard
    // here bakes 128x32x56; both must read the same field the same way.
    //
    // "The same way" is to within ONE quantum, not exactly, and that is the
    // honest bar rather than a relaxed one. The rule rounds the inter-belt
    // minimum DOWN to a 0.05 decade step, so two resolutions that read the same
    // minimum a few thousandths apart can still land on different sides of a
    // step. Four views agree exactly; the combined view reads 10^2.6278 at this
    // file's resolution and 10^2.6588 at the browser's, which straddles 2.65,
    // so it derives 2.60 here and 2.65 there. That started when the ruler's
    // geostationary joint became C1 on 2026-08-19 and the bake's radial grid
    // re-spaced with it — the minima themselves barely moved, the quantum
    // boundary was simply sitting between them. What must never happen is a
    // floor that moves by more than one step, or one that rises above the
    // minimum it was derived from; both are checked.
    const quantum = RADIATION_VOLUME_FLOOR_DERIVATION.quantumDecades;
    for (const view of RADIATION_VOLUME_OPACITY_BY_VIEW) {
      const source = view.energyKev === COMBINED_RADIATION_ENERGY_KEV ? combined : { definition, frame };
      const production = bakeOmnidirectionalFluxVolume(
        source.definition, source.frame, view.energyKev, mapperFrame,
        { radialCount: 192, mltCount: 64, latitudeCount: 88 },
      );
      const derived = resolveRadiationVolumeOpacityForBake(
        view.energyKev, production, encoding, mapperFrame.sceneRadiusForRe,
      );
      expect(Math.abs(derived.opacityFloorLog10Flux - view.fallbackFloorLog10Flux))
        .toBeLessThanOrEqual(quantum + 1e-9);
      // The property the floor exists to keep, at the resolution the browser
      // actually draws: nothing inside the view's own slot is ever removed.
      // Only where the FIELD decided the floor: at 1.35 and 2.32 MeV the slot
      // is already below the layer's declared 10^1 floor, so the declared one
      // stands and there is nothing inside the slot for it to remove.
      const minimum = derived.derivation.interBeltMinimumLog10Flux;
      if (minimum !== null && derived.derivation.status === "derived") {
        expect(derived.opacityFloorLog10Flux).toBeLessThanOrEqual(minimum);
      }
    }
  }, 180_000);

  it("says on every view where the floor came from and what the minimum was", () => {
    // Whatever it decides, it has to be sayable in the reader's own units.
    for (const view of RADIATION_VOLUME_OPACITY_BY_VIEW) {
      const derived = resolved.get(view.energyKev)!;
      expect(derived.reason).toContain("derived from this frame's own field");
      expect(derived.derivation.interBeltMinimumLog10Flux).not.toBeNull();
      expect(derived.derivation.interBeltMinimumL).toBeGreaterThanOrEqual(2.0);
      expect(derived.derivation.interBeltMinimumL).toBeLessThanOrEqual(3.6);
      expect(derived.derivation.occupiedFraction).toBeGreaterThan(0.9);
      // The two relativistic channels are dark between the belts on their own
      // terms, so the rule stops at the layer's declared floor and says so.
      const clamped = view.fallbackFloorLog10Flux === RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux;
      expect(derived.derivation.status).toBe(clamped ? "declared-floor" : "derived");
      if (clamped) expect(derived.reason).toContain("nothing at all is hidden");
    }
  });
});

/**
 * A field whose answer is known before the code runs.
 *
 * These bakes are written by hand, one texel level at a time, so the expected
 * floor is arithmetic rather than a re-measurement: a plateau at uint8 level
 * 105 on the artifact's own -2..9 encoding is exactly 10^2.5294, and the rule
 * rounds that down to 10^2.50.
 */
describe("the derivation, against synthetic fields with known answers", () => {
  const SYNTHETIC_ENCODING = {
    scale: "log10" as const,
    minimum: -2,
    maximum: 9,
    quantity: "synthetic differential electron flux",
    units: "model-native differential flux",
  };
  const level = (log10Flux: number) => Math.round(((log10Flux + 2) / 11) * 255);
  const fluxOfLevel = (byteLevel: number) => (byteLevel / 255) * 11 - 2;
  const SLOT_LEVEL = 105;
  const RADIAL_COUNT = 160;
  const MLT_COUNT = 16;
  const LATITUDE_COUNT = 8;
  const INNER_RE = 1.2;
  const OUTER_RE = 6.6;

  /** A bake whose equatorial profile is whatever `profile(L)` says it is. */
  function syntheticBake(
    profile: (l: number) => number,
    options: { occupiedMltFraction?: number } = {},
  ): RadiationVolumeBake {
    const sceneRadiusMinimum = mapperFrame.sceneRadiusForRe(INNER_RE);
    const sceneRadiusMaximum = mapperFrame.sceneRadiusForRe(OUTER_RE);
    const data = new Uint8Array(RADIAL_COUNT * MLT_COUNT * LATITUDE_COUNT);
    const occupiedMlt = Math.round(MLT_COUNT * (options.occupiedMltFraction ?? 1));
    for (let radial = 0; radial < RADIAL_COUNT; radial += 1) {
      const sceneRadius = sceneRadiusMinimum
        + ((radial + 0.5) / RADIAL_COUNT) * (sceneRadiusMaximum - sceneRadiusMinimum);
      const value = profile(mapperFrame.radiusReForSceneRadius(sceneRadius));
      for (let mlt = 0; mlt < MLT_COUNT; mlt += 1) {
        if (mlt >= occupiedMlt) continue;
        for (let latitude = 0; latitude < LATITUDE_COUNT; latitude += 1) {
          data[(latitude * MLT_COUNT + mlt) * RADIAL_COUNT + radial] = value;
        }
      }
    }
    return {
      data,
      radialCount: RADIAL_COUNT,
      mltCount: MLT_COUNT,
      latitudeCount: LATITUDE_COUNT,
      sceneRadiusMinimum,
      sceneRadiusMaximum,
      latitudeMaximumRadians: 1.0,
      trappingFloorRe: INNER_RE,
      equatorialRadiusMaximumRe: OUTER_RE,
      integratedPitchChannelCount: 4,
      displayWindow: { minimumEquatorialRadiusRe: 1.2, minimumMappedRadiusRe: 1.2, minimumLog10Flux: 1 },
    };
  }

  /** Two belts and a flat-bottomed slot: inner peak, plateau, outer peak. */
  const twoBeltProfile = (
    slotLevel = SLOT_LEVEL,
    innerLevel = level(4.0),
    outerLevel = level(5.0),
  ) => (l: number) => {
    if (l < 1.4) return Math.round(innerLevel * 0.75);
    if (l < 1.8) return innerLevel;
    if (l < 2.4) return Math.round(innerLevel + (slotLevel - innerLevel) * ((l - 1.8) / 0.6));
    if (l <= 3.0) return slotLevel;
    if (l < 3.8) return Math.round(slotLevel + (outerLevel - slotLevel) * ((l - 3.0) / 0.8));
    if (l < 4.6) return outerLevel;
    return Math.round(outerLevel * 0.7);
  };

  const derive = (bake: RadiationVolumeBake, fallbackFloor = 2.45) =>
    deriveRadiationVolumeOpacityFloor(bake, SYNTHETIC_ENCODING, mapperFrame.sceneRadiusForRe, fallbackFloor);

  it("puts the floor exactly one rounding step under a known inter-belt minimum", () => {
    const result = derive(syntheticBake(twoBeltProfile()));
    expect(result.status).toBe("derived");
    // The plateau is level 105, which on this encoding is 10^2.5294...
    expect(result.interBeltMinimumLog10Flux).toBeCloseTo(fluxOfLevel(SLOT_LEVEL), 6);
    // ...and the rule rounds DOWN to the next 0.05 decade, never up.
    expect(result.floorLog10Flux).toBe(2.5);
    expect(result.floorLog10Flux).toBeLessThan(result.interBeltMinimumLog10Flux!);
    expect(result.interBeltMinimumL).toBeGreaterThanOrEqual(2.4);
    expect(result.interBeltMinimumL).toBeLessThanOrEqual(3.0);
    expect(result.innerMaximumLog10Flux).toBeCloseTo(4.0, 1);
    expect(result.outerMaximumLog10Flux).toBeCloseTo(5.0, 1);
    expect(result.fallbackReason).toBeNull();
  });

  it("moves the floor with the field, which is the whole point of deriving it", () => {
    // The same shaped field with a deeper slot must draw deeper, and there is
    // no constant anywhere in the loop that could hold it still.
    const shallow = derive(syntheticBake(twoBeltProfile(level(3.2))));
    const deep = derive(syntheticBake(twoBeltProfile(level(1.7))));
    expect(shallow.floorLog10Flux).toBeGreaterThan(deep.floorLog10Flux);
    // Level 121 is 10^3.2196, level 86 is 10^1.7098; each rounds down to its
    // own 0.05 decade, and neither number appears anywhere in the source.
    expect(shallow.floorLog10Flux).toBeCloseTo(3.2, 6);
    expect(deep.floorLog10Flux).toBeCloseTo(1.7, 6);
  });

  it("stops at the layer's declared 10^1 floor and never goes below it", () => {
    const result = derive(syntheticBake(twoBeltProfile(level(0.3))));
    expect(result.status).toBe("declared-floor");
    expect(result.interBeltMinimumLog10Flux).toBeLessThan(1);
    expect(result.floorLog10Flux).toBe(RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux);
  });

  it("falls back, and says so, on an empty view", () => {
    const result = derive(syntheticBake(() => 0));
    expect(result.status).toBe("fallback");
    expect(result.floorLog10Flux).toBe(2.45);
    expect(result.fallbackReason).toContain("no flux at all between L 2 and L 3.6");
    expect(result.interBeltMinimumLog10Flux).toBeNull();
  });

  it("falls back, and says so, when there is no two-belt structure", () => {
    // A field that only falls outward has a lowest point in the window, but it
    // is the bottom of a slope, not a slot. Reading a floor off it would put
    // the floor at the outer edge of the drawn belt and cut the belt in half.
    const monotonic = derive(syntheticBake((l) => Math.max(0, Math.round(level(5.0) - (l - 1.2) * 22))));
    expect(monotonic.status).toBe("fallback");
    expect(monotonic.fallbackReason).toContain("no two-belt structure");
    expect(monotonic.floorLog10Flux).toBe(2.45);
    // A single flat sheet has no structure either.
    const flat = derive(syntheticBake(() => SLOT_LEVEL));
    expect(flat.status).toBe("fallback");
    expect(flat.fallbackReason).toContain("no two-belt structure");
  });

  it("falls back, and says so, when most of the frame carries no flux", () => {
    // This is how a NaN-heavy frame arrives here: non-finite flux never
    // reaches the texture, it leaves the texel empty. A quarter of the clock
    // is not a field to read a minimum from.
    const sparse = derive(syntheticBake(twoBeltProfile(), { occupiedMltFraction: 0.25 }));
    expect(sparse.status).toBe("fallback");
    expect(sparse.fallbackReason).toContain("too little of the field");
    expect(sparse.floorLog10Flux).toBe(2.45);
    // Three quarters of it still is.
    const mostly = derive(syntheticBake(twoBeltProfile(), { occupiedMltFraction: 0.75 }));
    expect(mostly.status).toBe("derived");
    expect(mostly.floorLog10Flux).toBeCloseTo(2.5, 6);
  });

  it("falls back rather than derive a floor that would erase the view", () => {
    // A field whose SLOT is already brighter than the top of the colour scale.
    // The rule would put the floor at 10^6, above the ramp's 10^5.5 ceiling,
    // and the view would go blank; the fallback keeps a picture and says why.
    const saturated = derive(syntheticBake(twoBeltProfile(level(6.0), level(7.0), level(8.0))));
    expect(saturated.status).toBe("fallback");
    expect(saturated.fallbackReason).toContain("top of the colour scale");
    expect(saturated.floorLog10Flux).toBe(2.45);
  });

  it("never returns a floor below the declared one, even on a fallback", () => {
    // The fallback is a clamp, not an escape hatch.
    const result = deriveRadiationVolumeOpacityFloor(
      syntheticBake(() => 0), SYNTHETIC_ENCODING, mapperFrame.sceneRadiusForRe, -3,
    );
    expect(result.floorLog10Flux).toBe(RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux);
  });
});

describe("a degenerate dataset, end to end through the mesh the layer draws", () => {
  it("draws with the shipped fallback and discloses it in the mesh's own readout", () => {
    // The whole artifact, republished with a flux payload of zeros: every
    // texel lands under the encoding floor, so the bake is empty and the rule
    // has nothing to read. The layer must still draw, must use the shipped
    // number, and must never present that number as if it came from this data.
    const zeroed: RadiationBeltFrame = {
      coordinatesU16: frame.coordinatesU16,
      electronFluxU16: frame.electronFluxU16,
      pitchResolvedElectronFluxU16: Object.fromEntries(
        Object.entries(frame.pitchResolvedElectronFluxU16).map(([key, value]) => [
          key,
          globalThis.btoa(String.fromCharCode(0).repeat(globalThis.atob(value).length)),
        ]),
      ),
    };
    const { mesh, opacity } = createRadiationVolumeMesh(definition, zeroed, RELATIVISTIC_KEV, mapper, {
      radialCount: 48, mltCount: 24, latitudeCount: 24,
    });
    const table = resolveRadiationVolumeOpacity(RELATIVISTIC_KEV);
    expect(opacity.floorSource).toBe("shipped-fallback-table");
    expect(opacity.opacityFloorLog10Flux).toBe(table.fallbackFloorLog10Flux);
    expect(opacity.reason).toContain("FLOOR NOT DERIVED FROM THIS DATA");
    expect(opacity.reason).toContain("no flux at all between L 2 and L 3.6");
    expect(mesh.userData.opacityFloorSource).toBe("shipped-fallback-table");
    expect(String(mesh.userData.transferMeaning)).toContain("NOT derived from this dataset");
    const material = mesh.material as THREE.ShaderMaterial;
    expect(material.uniforms.opacityFloor!.value)
      .toBeCloseTo(normalized(table.fallbackFloorLog10Flux), 9);
    // ...and the colour scale is untouched by any of it.
    expect(material.uniforms.colourFloor!.value).toBeCloseTo(colourFloor, 9);
    expect(material.uniforms.colourSpan!.value).toBeCloseTo(colourSpan, 9);
    material.dispose();
    mesh.geometry.dispose();
  });
});

/**
 * The proof that the SHADER is given a number this dataset produced.
 *
 * Every other check here runs on the pinned frame, where the derived floor and
 * the shipped fallback are the same value by construction — which is the point,
 * but it means none of them can tell a live derivation from a lookup. So this
 * one publishes a DIFFERENT dataset: the same field with every flux divided by
 * ten. The whole picture moves down one decade, and the floor has to move with
 * it or the layer is still reading a table.
 */
describe("a dataset the shipped table was never measured on", () => {
  /** The fixture's own flux, one decade fainter, re-encoded on its own scale. */
  function oneDecadeFainter(frameToShift: RadiationBeltFrame): RadiationBeltFrame {
    const decade = Math.round(65535 / (encoding.maximum - encoding.minimum));
    const shift = (encoded: string) => {
      const binary = globalThis.atob(encoded);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      const view = new DataView(bytes.buffer);
      for (let index = 0; index * 2 < bytes.length; index += 1) {
        view.setUint16(index * 2, Math.max(0, view.getUint16(index * 2, true) - decade), true);
      }
      let out = "";
      for (let index = 0; index < bytes.length; index += 1) out += String.fromCharCode(bytes[index]!);
      return globalThis.btoa(out);
    };
    return {
      coordinatesU16: frameToShift.coordinatesU16,
      electronFluxU16: Object.fromEntries(
        Object.entries(frameToShift.electronFluxU16).map(([key, value]) => [key, shift(value)])),
      pitchResolvedElectronFluxU16: Object.fromEntries(
        Object.entries(frameToShift.pitchResolvedElectronFluxU16).map(([key, value]) => [key, shift(value)])),
    };
  }

  it("hands the shader the floor IT produced, not the one the table remembers", () => {
    const fainter = oneDecadeFainter(frame);
    const { mesh, opacity } = createRadiationVolumeMesh(definition, fainter, 88.349, mapper, {
      radialCount: 128, mltCount: 32, latitudeCount: 56,
    });
    const table = resolveRadiationVolumeOpacity(88.349);
    // The pinned frame's 88 keV inter-belt minimum is 10^4.21 and its shipped
    // floor 10^4.20. One decade fainter, the minimum is 10^3.21 and the floor
    // has to follow it down. A build that still read the table would draw this
    // dataset a full decade into its own slot.
    expect(opacity.derivation.interBeltMinimumLog10Flux).toBeCloseTo(3.21, 1);
    expect(opacity.opacityFloorLog10Flux).toBeCloseTo(3.2, 6);
    expect(opacity.opacityFloorLog10Flux).not.toBe(table.fallbackFloorLog10Flux);
    expect(opacity.floorSource).toBe("derived-from-loaded-data");
    const material = mesh.material as THREE.ShaderMaterial;
    expect(material.uniforms.opacityFloor!.value)
      .toBeCloseTo(normalized(opacity.opacityFloorLog10Flux), 9);
    // The colour scale does not move with it. It never moves.
    expect(material.uniforms.colourFloor!.value).toBeCloseTo(colourFloor, 9);
    expect(material.uniforms.colourSpan!.value).toBeCloseTo(colourSpan, 9);
    material.dispose();
    mesh.geometry.dispose();
  });
});

describe("the belts hang off the dipole, not off GSM z", () => {
  /**
   * GSM's z axis is not the magnetic axis: the dipole lies in the GSM x-z plane
   * tilted by the geodipole tilt, which swings through roughly +-34 degrees over
   * a day and a year. The belt bake is organised by magnetic latitude, so
   * sampling it in GSM mislabels every latitude by that whole angle — the
   * largest single geometric error the layer had.
   */
  it("is the identity when the dipole is upright", () => {
    const matrix = smFromGsmMatrix(0);
    const elements = matrix.elements;
    const identity = new THREE.Matrix3().elements;
    for (let index = 0; index < 9; index += 1) {
      expect(elements[index]).toBeCloseTo(identity[index]!, 12);
    }
  });

  it("rotates about y, so it can never change a radius", () => {
    // The honesty property. A rotation moves where a sample is looked up and
    // cannot alter the flux stored there, which is what makes correcting the
    // geometry safe: the numbers are untouched by construction.
    for (const tilt of [-0.6, -0.2, 0, 0.35, 0.59]) {
      const matrix = smFromGsmMatrix(tilt);
      for (const vector of [
        new THREE.Vector3(3, 0, 0),
        new THREE.Vector3(0, 2, 1),
        new THREE.Vector3(1.5, -2.5, 4),
      ]) {
        const rotated = vector.clone().applyMatrix3(matrix);
        expect(rotated.length()).toBeCloseTo(vector.length(), 10);
      }
      // y is the rotation axis and must come through untouched.
      const alongAxis = new THREE.Vector3(0, 1, 0).applyMatrix3(matrix);
      expect(alongAxis.x).toBeCloseTo(0, 12);
      expect(alongAxis.y).toBeCloseTo(1, 12);
      expect(alongAxis.z).toBeCloseTo(0, 12);
    }
  });

  it("takes the tilted dipole axis onto SM z", () => {
    // In GSM the dipole axis is (sin psi, 0, cos psi). After the rotation it
    // must be (0, 0, 1) — that is the whole definition of Solar Magnetic
    // coordinates, and the reason magnetic latitude means what the bake assumed.
    for (const psi of [-0.59, -0.25, 0.12, 0.59]) {
      const axisInGsm = new THREE.Vector3(Math.sin(psi), 0, Math.cos(psi));
      const inSm = axisInGsm.applyMatrix3(smFromGsmMatrix(psi));
      expect(inSm.x).toBeCloseTo(0, 10);
      expect(inSm.y).toBeCloseTo(0, 10);
      expect(inSm.z).toBeCloseTo(1, 10);
    }
  });

  it("moves a sample by the tilt angle, which is the error being corrected", () => {
    // A point on the GSM equator is 34 degrees off the magnetic equator when
    // the dipole is tilted that far. If this ever returns ~0 the correction is
    // not happening and the belts are back where they were.
    const psi = 34 * (Math.PI / 180);
    const onGsmEquator = new THREE.Vector3(4, 0, 0);
    const inSm = onGsmEquator.clone().applyMatrix3(smFromGsmMatrix(psi));
    const magneticLatitude = Math.asin(inSm.z / inSm.length()) * (180 / Math.PI);
    expect(Math.abs(magneticLatitude)).toBeCloseTo(34, 4);
  });
});


describe("the shader's copy of the radial ruler", () => {
  /**
   * The belt shader applies the eccentric-dipole offset in physical space, so
   * it converts drawn radius to Earth radii and back inside the raymarch. It
   * does that in CLOSED FORM rather than with a lookup table, which is only
   * legitimate if the closed form really agrees with the site's one shared
   * ruler across the whole belt domain.
   *
   * This is that check. It is the load-bearing test for the South Atlantic
   * Anomaly: if the two rulers disagree anywhere, the anomaly is drawn in the
   * wrong place, confidently.
   */
  const EARTH_SCENE_RADIUS = 100;

  it("agrees with the shared ruler everywhere the belts are drawn", () => {
    for (let radiusRe = 1.05; radiusRe <= 12; radiusRe += 0.05) {
      const shared = sharedDisplayRadius(radiusRe, EARTH_SCENE_RADIUS);
      const shader = shaderDrawnFromRe(radiusRe, EARTH_SCENE_RADIUS);
      // Relative, because the drawn radius spans two orders of magnitude.
      expect(Math.abs(shader - shared) / shared).toBeLessThan(1e-6);
    }
  });

  it("inverts itself exactly", () => {
    for (let radiusRe = 1.05; radiusRe <= 12; radiusRe += 0.05) {
      const drawn = shaderDrawnFromRe(radiusRe, EARTH_SCENE_RADIUS);
      expect(shaderReFromDrawn(drawn, EARTH_SCENE_RADIUS)).toBeCloseTo(radiusRe, 6);
    }
  });

  it("agrees with the shared ruler's own inverse", () => {
    for (let radiusRe = 1.2; radiusRe <= 10; radiusRe += 0.1) {
      const drawn = sharedDisplayRadius(radiusRe, EARTH_SCENE_RADIUS);
      const shared = radiusFromSharedDisplayRadius(drawn, EARTH_SCENE_RADIUS);
      const shader = shaderReFromDrawn(drawn, EARTH_SCENE_RADIUS);
      expect(Math.abs(shader - shared)).toBeLessThan(1e-4);
    }
  });

  it("shows why the offset cannot be applied in scene units", () => {
    // The number that forced this design. Near the surface the ruler magnifies
    // enormously, so one rigid scene-space shift cannot represent a rigid
    // physical shift: the same 0.096 Re offset spans very different drawn
    // distances at the inner belt and at the outer belt.
    const offsetRe = 0.096;
    const drawnAtInner = shaderDrawnFromRe(1.5 + offsetRe, EARTH_SCENE_RADIUS)
      - shaderDrawnFromRe(1.5, EARTH_SCENE_RADIUS);
    const drawnAtOuter = shaderDrawnFromRe(5 + offsetRe, EARTH_SCENE_RADIUS)
      - shaderDrawnFromRe(5, EARTH_SCENE_RADIUS);
    expect(drawnAtInner / drawnAtOuter).toBeGreaterThan(2);
  });
});
