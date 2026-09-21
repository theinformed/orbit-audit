import * as THREE from "three";

import { sharedDisplayRadius } from "./radial-ruler";

export const RADIATION_BELT_VIEWS = {
  nativeEquatorial: {
    label: "SOURCE GRID — FLAT EQUATORIAL SLICE (2-D)",
    status: "model",
    description: "The unprojected NOAA source grid: RBE publishes differential electron flux only at each field line's equatorial crossing point, so this view is genuinely a flat 2-D slice in the magnetic equatorial plane — it is meant to look flat, because that is the shape of the source. The surface triangulates neighboring native radial/MLT samples; no off-equator extent is implied. Only the trapping region is painted: cells inside L = 1.2 Re, and cells at or below 10^1 differential flux, are omitted rather than drawn as a floor-valued sheet.",
  },
  dipoleMapped3d: {
    label: "PITCH-RESOLVED DIPOLE-MAPPED ELECTRON VOLUME",
    status: "model-derived-mapping",
    description: "The same source flux carried off the equator along an ideal centered dipole, with gyrotropy and north/south pitch symmetry assumed. The pitch control chooses what is drawn. The layer opens on the omnidirectional flux — every locally trapped pitch channel integrated over solid angle — rendered volumetrically: a raymarcher accumulates the field along every view ray, and opacity tracks the local flux, so the belts, the slot between them, and their merging at low energy are all the field's own rather than a drawn boundary. Every individual published channel, plus all of them stacked at once, stays selectable as explicit bounce shells. Any one published energy can be drawn, or all four at once as an energy-weighted integral over the published 88 keV to 2.32 MeV band; the colour scale is the same in every energy view so the channels can be compared by eye, and only opacity is tuned per energy. The legend always names what is on screen. This is not native 3-D RBE or BATS-R-US output, not particle density, and no proton or synthetic inner belt is imposed.",
  },
} as const;

/**
 * What the mapped 3-D presentation is drawing, which is not the same question as
 * which `RADIATION_BELT_VIEWS` entry is selected.
 *
 * - `omnidirectional` integrates every locally trapped pitch channel over solid
 *   angle into one volume. This is the layer's default and the form the audience
 *   already reads elsewhere: AE9/AP9, the GOES particle products and the Van
 *   Allen Probes products all report omnidirectional differential flux.
 * - `single` draws one published pitch channel as one bounce shell.
 * - `all` stacks every published channel as separate translucent shells.
 */
export type RadiationPitchPresentation = "omnidirectional" | "single" | "all";

/**
 * Legend label for each presentation.
 *
 * The word "omnidirectional" is doing real work here and is not decoration: a
 * reader who works with AE9/AP9 should be able to tell from the label alone that
 * this is the pitch-angle-integrated quantity and not one look direction.
 */
export const RADIATION_PITCH_PRESENTATION_LABELS: Record<RadiationPitchPresentation, string> = {
  omnidirectional: "OMNIDIRECTIONAL DIPOLE-MAPPED ELECTRON VOLUME",
  single: "SINGLE-PITCH-CHANNEL DIPOLE-MAPPED BOUNCE SHELL",
  all: "ALL-PITCH-CHANNEL STACKED DIPOLE-MAPPED SHELLS",
};

/**
 * The quantity each presentation puts on the shared log10 colour ramp.
 *
 * The artifact's own `encoding.quantity` describes the near-90-degree channel it
 * publishes as the 2-D surface, so it is the wrong caption for a pitch-integrated
 * volume even though the encoding scale is identical.
 */
export const RADIATION_PITCH_PRESENTATION_QUANTITIES: Record<RadiationPitchPresentation, string> = {
  omnidirectional: "omnidirectional differential electron flux",
  single: "single-pitch-channel differential electron flux",
  all: "per-pitch-channel differential electron flux",
};


/**
 * The energy key of the combined view: every published channel at once.
 *
 * It is a negative number so it can never collide with a real channel, and so
 * `nearestEnergy()`-style snapping has to opt into it deliberately rather than
 * rounding into it by accident.
 */
export const COMBINED_RADIATION_ENERGY_KEV = -1;

/** Label for the combined view, used by the control, the legend and the card. */
export const COMBINED_RADIATION_ENERGY_LABEL = "All energies (combined)";

export function isCombinedRadiationEnergy(energyKev: number) {
  return energyKev === COMBINED_RADIATION_ENERGY_KEV;
}

/**
 * How the four published channels are combined into one volume.
 *
 * RBE publishes DIFFERENTIAL flux — flux per unit energy — at four channel
 * energies (88.349 keV, 452.75 keV, 1345.7 keV, 2320.1 keV; indices 4, 7, 9
 * and 10 of the model's own twelve-point energy grid, see
 * `pipeline/swmf.py:_parse_radiation`). Adding four differential fluxes
 * together is not a physical quantity at all: the channels sit on a
 * logarithmically spaced grid, so the bins they represent are wildly unequal
 * and a plain sum would silently weight 88 keV and 2.32 MeV as if each stood
 * for the same slice of the spectrum.
 *
 * Both supported combinations are therefore INTEGRALS over the published
 * 88 keV - 2.32 MeV band, divided by the width of that band, so the result
 * carries the same units as every single-channel view (model-native
 * differential flux) and can honestly share one colour scale with them.
 *
 * - `numberFlux` is the band-averaged differential flux,
 *   `integral(j dE) / integral(dE)` over the band. This is the number-flux
 *   integral: how many electrons per second cross a square centimetre,
 *   spread back over the band.
 * - `energyWeighted` is `integral(E j dE) / integral(E dE)`. The numerator is
 *   the ENERGY flux the band carries, so this weighting asks how much energy
 *   is here rather than how many particles, which is the quantity that decides
 *   dose behind shielding. It multiplies the relativistic channels up relative
 *   to 88 keV by roughly the ratio of their energies.
 *
 * Both use the trapezoidal rule over the four published channel energies, and
 * both are a coarse quadrature: four nodes over a decade and a half of a
 * steeply falling spectrum, and four of the model's twelve channels. That is
 * disclosed on the layer and in `docs/SCIENTIFIC-LAYERS.md`; it is a display
 * integral over what is published, not a claim to the model's own spectrum.
 */
export type RadiationEnergyCombination = "numberFlux" | "energyWeighted";

/**
 * Which combination the combined view ships with, and why: `energyWeighted`.
 *
 * Both were built and both were measured on the pinned 2026-08-08T23:40Z
 * frame, by marching the layer's own default camera through the real bake,
 * each tuned by the SAME rule (`RADIATION_VOLUME_OPACITY_BY_VIEW`: floor at
 * the view's own inter-belt minimum, extinction chosen for a comparable peak),
 * so the comparison is between the two quantities and not between two tunings.
 *
 * - `numberFlux` band-average: maxima 10^4.08 (L 1.76) and 10^4.34 (L 4.48),
 *   minimum 10^3.44 at L 3.00. Profile 0.600 / 0.423 / 0.550 — a slot 23%
 *   darker than the outer belt, with the inner belt drawn BRIGHTER than the
 *   outer one.
 * - `energyWeighted` band-average: maxima 10^3.18 (L 1.80) and 10^3.65
 *   (L 3.66), minimum 10^2.62 at L 2.74. Profile 0.602 / 0.467 / 0.626 — a
 *   slot 25% darker than the outer belt, with the outer belt the brighter of
 *   the two.
 *
 * The energy-weighted volume wins narrowly on contrast and decisively on
 * physics. The plain number integral is dominated by the 88 keV channel, and
 * the 88 keV electrons are precisely the population that FILLS the slot — at
 * that energy the model's own inter-belt minimum is still 10^4.21, more
 * electrons than sit in the CORE of the outer belt at 2.32 MeV. Weighting by
 * energy asks where the radiation ENERGY is instead of where the particle
 * count is, and the answer keeps the slot, because the energy is carried by
 * the MeV electrons that respect it. It also puts the drawn minimum at L 2.74
 * instead of L 3.00, and makes the outer belt the brighter of the two, both of
 * which match every published rendering of the belts. And it is the quantity
 * that matters operationally: dose behind shielding follows deposited energy,
 * not counts.
 *
 * `numberFlux` stays implemented, tested and one constant away, because the
 * comparison is the evidence for this choice.
 */
export const RADIATION_ENERGY_COMBINATION: RadiationEnergyCombination = "energyWeighted";

/**
 * Trapezoidal quadrature weights for the published channel energies,
 * normalized to sum to one so the result is a band AVERAGE of the differential
 * flux and therefore lands on the same scale as a single channel.
 *
 * Returned in the caller's own channel order, so a caller may pass the
 * artifact's `energiesKev` array as published and index the result with it.
 */
export function radiationChannelIntegrationWeights(
  energiesKev: readonly number[],
  combination: RadiationEnergyCombination = "numberFlux",
): number[] {
  if (energiesKev.length === 0) throw new RangeError("RBE energy grid is empty");
  if (energiesKev.length === 1) return [1];
  const order = energiesKev.map((energy, index) => ({ energy, index }))
    .sort((first, second) => first.energy - second.energy);
  const raw = new Array<number>(energiesKev.length).fill(0);
  for (let position = 0; position < order.length; position += 1) {
    const previous = order[Math.max(position - 1, 0)]!.energy;
    const next = order[Math.min(position + 1, order.length - 1)]!.energy;
    const entry = order[position]!;
    // Half the distance to each neighbour; the two ends see only one side,
    // which is exactly the trapezoidal rule's end weight.
    const width = (next - previous) / 2;
    raw[entry.index] = combination === "energyWeighted" ? width * entry.energy : width;
  }
  const total = raw.reduce((sum, value) => sum + value, 0);
  if (!(total > 0)) throw new RangeError("RBE energy grid has no width to integrate over");
  return raw.map((value) => value / total);
}

function encodeRadiationFlux(normalized: ArrayLike<number>) {
  const bytes = new Uint8Array(normalized.length * 2);
  const view = new DataView(bytes.buffer);
  for (let index = 0; index < normalized.length; index += 1) {
    const value = Math.round(THREE.MathUtils.clamp(normalized[index] ?? 0, 0, 1) * 65535);
    view.setUint16(index * 2, value, true);
  }
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]!);
  return globalThis.btoa(binary);
}

/**
 * Fold every published energy channel into one synthetic single-channel
 * artifact, keyed at `COMBINED_RADIATION_ENERGY_KEV`.
 *
 * The combination happens in PHYSICAL flux — the encoded log10 values are
 * un-quantized, weighted, summed, and re-quantized onto the artifact's own
 * encoding — because a weighted sum of logarithms is a geometric mean, which
 * is not the integral anybody means. Because the energy integral and the
 * pitch-angle solid-angle integral are both linear in flux they commute, so
 * combining here and integrating pitch downstream gives the same volume as
 * the other order, and every presentation the layer offers (volume, single
 * shell, stacked shells, native slice) keeps working unchanged on the result.
 */
export function combineRadiationEnergyChannels(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  combination: RadiationEnergyCombination = "numberFlux",
): { definition: RadiationBeltDefinition; frame: RadiationBeltFrame } {
  const energies = definition.energiesKev;
  if (!energies || energies.length === 0) throw new RangeError("RBE artifact publishes no energies");
  const weights = radiationChannelIntegrationWeights(energies, combination);
  const encoding = definition.encoding;
  const span = encoding.maximum - encoding.minimum;
  if (!Number.isFinite(span) || span <= 0) throw new RangeError("RBE flux encoding range is empty");

  const combineRecord = (record: Record<string, string>, expectedCount: number) => {
    const total = new Float64Array(expectedCount);
    for (let index = 0; index < energies.length; index += 1) {
      const weight = weights[index]!;
      const decoded = decodeRadiationFlux(encodedEnergy(record, energies[index]!), expectedCount);
      for (let point = 0; point < expectedCount; point += 1) {
        total[point] = total[point]! + weight * 10 ** (encoding.minimum + decoded[point]! * span);
      }
    }
    const normalized = new Float64Array(expectedCount);
    for (let point = 0; point < expectedCount; point += 1) {
      const value = total[point]!;
      normalized[point] = value > 0
        ? THREE.MathUtils.clamp((Math.log10(value) - encoding.minimum) / span, 0, 1)
        : 0;
    }
    return encodeRadiationFlux(normalized);
  };

  const key = String(COMBINED_RADIATION_ENERGY_KEV);
  const pitchCount = definition.pitchCoordinatesSin.length;
  const combinedFrame: RadiationBeltFrame = {
    coordinatesU16: frame.coordinatesU16,
    electronFluxU16: { [key]: combineRecord(frame.electronFluxU16, definition.count) },
    pitchResolvedElectronFluxU16: {
      [key]: combineRecord(frame.pitchResolvedElectronFluxU16, definition.count * pitchCount),
    },
  };
  return {
    definition: { ...definition, energiesKev: [COMBINED_RADIATION_ENERGY_KEV] },
    frame: combinedFrame,
  };
}

/**
 * Electron energy the radiation-belt layer opens on: ALL OF THEM.
 *
 * The published RBE grid is 88 keV, 453 keV, 1.35 MeV and 2.32 MeV, and the
 * layer used to open at 1.35 MeV because that is the single channel in which
 * the two-belt structure and the slot both resolve. That was the right choice
 * while there was no way to draw more than one channel at a time, and it was
 * still the wrong first impression: a visitor who switches the radiation layer
 * on and does nothing else got the faintest of the four channels, and the belts
 * this layer exists to show only appeared after they found the energy control.
 * Sean, on exactly that: "you can sort of see the Van Allen belts... you just
 * don't see that when you turn on radiation belts initially."
 *
 * So the layer now opens on the combined view — every published channel folded
 * into one energy-weighted band integral (see `RADIATION_ENERGY_COMBINATION`).
 * It is the view in which the two belts and the slot between them are visible
 * with no interaction at all, and it is also the honest answer to the question
 * a first-time visitor is actually asking, which is "where is the radiation",
 * not "where are the 1.35 MeV electrons".
 *
 * This is a display default, never a claim about the individual channels. The
 * legend states what is drawn, and every one of the four stays one click apart.
 *
 * `GeospaceRuntime` snaps whatever it is handed to the nearest published energy
 * — except the combined key, which is passed through untouched because it is
 * not a channel and must never be rounded into one.
 */
export const DEFAULT_RADIATION_ENERGY_KEV = COMBINED_RADIATION_ENERGY_KEV;

/**
 * Display window for both radiation-belt views.
 *
 * Two facts about the source force this to exist.
 *
 * 1. The RBE grid runs inward to the model's own ionospheric boundary
 *    (about 1.0157 Re, roughly 100 km altitude). Those rows are thermosphere,
 *    not belt. Drawing them wraps the layer onto the rendered globe, puts
 *    translucent geometry a fraction of a scene unit above the Earth sphere,
 *    and produces the equatorial flicker.
 * 2. The published flux is quantized over a fixed log10 window whose floor is
 *    10^-2. Cells sitting at or near that floor are "the model has essentially
 *    nothing here", but they still generate a full translucent surface. Eleven
 *    stacked pitch shells of floor-valued surface is an opaque blanket, and it
 *    buries the slot region, whose contrast against the belt cores is three
 *    decades of flux.
 *
 * Both cuts are hard geometry cuts, not opacity tricks: a cell outside the
 * window contributes no triangle at all. Both are disclosed in the view
 * descriptions above and echoed into geometry userData.
 */
export interface RadiationBeltDisplayWindow {
  /** Smallest equatorial (L) radius drawn, in Earth radii. */
  minimumEquatorialRadiusRe: number;
  /** Smallest radius a mapped bounce shell may reach, in Earth radii. */
  minimumMappedRadiusRe: number;
  /** Smallest log10 differential flux drawn, in the encoding's own units. */
  minimumLog10Flux: number;
}

export const RADIATION_BELT_DISPLAY_WINDOW: RadiationBeltDisplayWindow = {
  minimumEquatorialRadiusRe: 1.2,
  minimumMappedRadiusRe: 1.2,
  minimumLog10Flux: 1,
};

/**
 * Kilometres per Earth radius, matching the value the orbit propagator and the
 * globe's altitude scale already use.
 */
export const EARTH_RADIUS_KM = 6371;

/**
 * Radial display scale for the radiation-belt layer.
 *
 * The globe once drew two different logarithmic radial compressions. Satellites
 * used an altitude scale (`Globe.altitudeDisplayRadius`), which places GEO at
 * about 2.3 Earth radii of screen distance. The geospace context volume —
 * magnetopause, SWMF cut planes, and until now the radiation belts — used a far
 * harsher one, which placed 12 Earth radii at 1.29 screen radii. Under that
 * second scale the whole belt system from 1.2 to 12 Re landed between 1.012 and
 * 1.289 rendered Earth radii: a skin on the globe. That is why the belts
 * rendered as a purple shell wrapped around the Earth instead of two tori, and
 * no amount of geometry work inside this module could undo it.
 *
 * This function is the belt layer's own radial policy: keeping the call sites
 * separately named means a later change to any other layer's compression cannot
 * silently flatten the belts again. It resolves to the scene's one shared
 * ruler in `src/radial-ruler.ts`, whose near-Earth logarithmic branch — where
 * every belt core lives — is the satellite altitude scale unchanged, so a
 * viewer can still compare a belt against the orbit that flies through it.
 */
export function radiationBeltDisplayRadius(radiusRe: number, earthSceneRadius: number) {
  return sharedDisplayRadius(radiusRe, earthSceneRadius);
}

export function resolveRadiationBeltDisplayWindow(
  overrides?: Partial<RadiationBeltDisplayWindow>,
): RadiationBeltDisplayWindow {
  const window = { ...RADIATION_BELT_DISPLAY_WINDOW, ...overrides };
  if (!Number.isFinite(window.minimumEquatorialRadiusRe) || window.minimumEquatorialRadiusRe < 1) {
    throw new RangeError("RBE display window minimumEquatorialRadiusRe must be at least 1 Re");
  }
  if (!Number.isFinite(window.minimumMappedRadiusRe) || window.minimumMappedRadiusRe < 1) {
    throw new RangeError("RBE display window minimumMappedRadiusRe must be at least 1 Re");
  }
  if (!Number.isFinite(window.minimumLog10Flux)) {
    throw new RangeError("RBE display window minimumLog10Flux must be finite");
  }
  return window;
}

export const GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS = {
  particlePopulation: "RBE model electrons only",
  fieldGeometry: "centered ideal dipole",
  pitchDistribution: "gyrotropic about the local magnetic field with north/south pitch symmetry",
  invariant: "first adiabatic invariant used to map equatorial pitch to mirror latitude",
  alongFieldInterpretation: "equatorial differential flux is repeated along each mapped bounce shell for visualization; no transport solution or local particle density is inferred",
  omnidirectionalAlongFieldInterpretation: "RBE publishes flux only at the mapped equatorial crossing point, and nothing here invents an along-field-line source profile. What varies with latitude is which of the published equatorial pitch channels can still be present: a channel contributes at latitude lambda only until it mirrors, and it is weighted by the solid angle its bin occupies in the local field, so the volume thins toward the mirror points because the wide-pitch channels have already turned around. That is bookkeeping on the published equatorial distribution under the stated dipole and first-invariant assumptions; it is not a transport solution, not a diffusion or source-loss calculation, and not local particle density",
  sourceCoverage: "the source is equatorial-only: NOAA RBE publishes differential flux at the field-line-mapped equatorial crossing point (radius, MLT) and no along-field-line profile at all",
  exclusions: "no proton population, synthetic inner belt, drift phase, gyro phase, wave scattering, or native off-equator RBE state",
} as const;

export interface RadiationGridShape {
  radialCount: number;
  magneticLocalTimeCount: number;
}

export interface RadiationBeltDefinition {
  count: number;
  energiesKev: number[];
  pitchCoordinate: number;
  pitchCoordinatesSin: number[];
  pitchAnglesDegrees: number[];
  pitchResolvedOrdering: "equatorial-point-major, pitch-index-minor";
  innerBoundaryRe: number;
  /** Optional explicit source topology. Older bundles can infer it from MLT recurrence. */
  gridShape?: RadiationGridShape;
  encoding: {
    scale: "log10";
    minimum: number;
    maximum: number;
    quantity: string;
    units: string;
  };
}

export interface RadiationBeltFrame {
  coordinatesU16: string;
  /** Highest-published-pitch channel retained as the native 2-D view. */
  electronFluxU16: Record<string, string>;
  /** Source pitch channels, point-major and then pitch-index. */
  pitchResolvedElectronFluxU16: Record<string, string>;
}

export interface RadiationBeltCoordinates {
  equatorialRadiusRe: Float32Array;
  equatorialMagneticLocalTimeHours: Float32Array;
}

export type RadiationPositionMapper = (xRe: number, yRe: number, zRe: number) => THREE.Vector3;

function decodeBase64(encoded: string) {
  const binary = globalThis.atob(encoded);
  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) output[index] = binary.charCodeAt(index);
  return output;
}

function decodeUint16(encoded: string) {
  const bytes = decodeBase64(encoded);
  if (bytes.byteLength % 2 !== 0) throw new RangeError("RBE uint16 payload has an odd byte count");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const values = new Uint16Array(bytes.byteLength / 2);
  for (let index = 0; index < values.length; index += 1) values[index] = view.getUint16(index * 2, true);
  return values;
}

function encodedEnergy(record: Record<string, string>, requestedEnergyKev: number) {
  const match = Object.entries(record).find(([key]) => Math.abs(Number(key) - requestedEnergyKev) < 1e-3);
  if (!match) throw new RangeError(`RBE energy ${requestedEnergyKev} keV is unavailable`);
  return match[1];
}

export function decodeRadiationBeltCoordinates(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
): RadiationBeltCoordinates {
  const encoded = decodeUint16(frame.coordinatesU16);
  if (encoded.length !== definition.count * 2) {
    throw new RangeError(`RBE coordinate payload contains ${encoded.length / 2} points; expected ${definition.count}`);
  }
  const equatorialRadiusRe = new Float32Array(definition.count);
  const equatorialMagneticLocalTimeHours = new Float32Array(definition.count);
  for (let index = 0; index < definition.count; index += 1) {
    equatorialRadiusRe[index] = encoded[index * 2]! * 0.001;
    equatorialMagneticLocalTimeHours[index] = encoded[index * 2 + 1]! * 0.001;
  }
  return { equatorialRadiusRe, equatorialMagneticLocalTimeHours };
}

export function decodeRadiationFlux(encoded: string, expectedCount: number) {
  const values = decodeUint16(encoded);
  if (values.length !== expectedCount) {
    throw new RangeError(`RBE flux payload contains ${values.length} values; expected ${expectedCount}`);
  }
  return Float32Array.from(values, (value) => value / 65535);
}

/**
 * The display window's flux floor expressed on the same 0..1 scale the decoded
 * flux attribute uses, so the cut can be applied without ever un-quantizing.
 */
export function normalizedRadiationFluxFloor(
  encoding: RadiationBeltDefinition["encoding"],
  window: RadiationBeltDisplayWindow = RADIATION_BELT_DISPLAY_WINDOW,
) {
  const span = encoding.maximum - encoding.minimum;
  if (!Number.isFinite(span) || span <= 0) throw new RangeError("RBE flux encoding range is empty");
  const encoded = encoding.scale === "log10" ? window.minimumLog10Flux : 10 ** window.minimumLog10Flux;
  return THREE.MathUtils.clamp((encoded - encoding.minimum) / span, 0, 1);
}

/**
 * The trapped, equatorially mirroring channel: the largest published sin(alpha).
 * Small sin(alpha) channels are loss cone, not belt, so they are never a
 * sensible default. Read by index only after this resolves it, so a future
 * artifact that publishes its pitch grid in another order cannot silently
 * default the display to a precipitating population.
 */
export function trappedPitchIndex(pitchCoordinatesSin: readonly number[]) {
  if (pitchCoordinatesSin.length === 0) throw new RangeError("RBE pitch grid is empty");
  let best = 0;
  for (let index = 1; index < pitchCoordinatesSin.length; index += 1) {
    if (pitchCoordinatesSin[index]! > pitchCoordinatesSin[best]!) best = index;
  }
  return best;
}

/** MLT 0 is midnight, 6 dawn, 12 noon (+X GSM), and 18 dusk (+Y GSM). */
export function equatorialRadiationPosition(radiusRe: number, magneticLocalTimeHours: number) {
  const azimuth = (magneticLocalTimeHours - 12) * Math.PI / 12;
  return new THREE.Vector3(radiusRe * Math.cos(azimuth), radiusRe * Math.sin(azimuth), 0);
}

function circularHoursDistance(first: number, second: number) {
  const difference = Math.abs(first - second) % 24;
  return Math.min(difference, 24 - difference);
}

function mean(values: number[]) {
  return values.reduce((total, value) => total + value, 0) / Math.max(1, values.length);
}

function validateGridShape(shape: RadiationGridShape, pointCount: number) {
  if (
    !Number.isInteger(shape.radialCount)
    || !Number.isInteger(shape.magneticLocalTimeCount)
    || shape.radialCount < 1
    || shape.magneticLocalTimeCount < 1
    || shape.radialCount * shape.magneticLocalTimeCount !== pointCount
  ) {
    throw new RangeError(`RBE grid shape ${shape.radialCount}x${shape.magneticLocalTimeCount} does not contain ${pointCount} points`);
  }
  return shape;
}

/**
 * Resolve the native radial-major, MLT-minor topology. Current artifacts should
 * publish gridShape. The recurrence fallback exists for already-published
 * bundles and chooses the smallest divisor whose next radial row repeats MLT.
 */
export function resolveRadiationGridShape(
  definition: RadiationBeltDefinition,
  coordinates: RadiationBeltCoordinates,
  explicitShape?: RadiationGridShape,
) {
  if (explicitShape) return validateGridShape(explicitShape, definition.count);
  if (definition.gridShape) return validateGridShape(definition.gridShape, definition.count);
  if (definition.count < 6) return { radialCount: 1, magneticLocalTimeCount: definition.count };

  const candidates: Array<RadiationGridShape & { score: number }> = [];
  const maximumMltCount = Math.min(96, Math.floor(definition.count / 2));
  for (let mltCount = 4; mltCount <= maximumMltCount; mltCount += 1) {
    if (definition.count % mltCount !== 0) continue;
    const radialCount = definition.count / mltCount;
    const recurrence: number[] = [];
    for (let index = 0; index + mltCount < definition.count; index += 1) {
      recurrence.push(circularHoursDistance(
        coordinates.equatorialMagneticLocalTimeHours[index]!,
        coordinates.equatorialMagneticLocalTimeHours[index + mltCount]!,
      ));
    }
    const stepErrors: number[] = [];
    const expectedStep = 24 / mltCount;
    for (let radialIndex = 0; radialIndex < radialCount; radialIndex += 1) {
      const rowOffset = radialIndex * mltCount;
      for (let mltIndex = 0; mltIndex < mltCount; mltIndex += 1) {
        const nextMltIndex = (mltIndex + 1) % mltCount;
        const actualStep = (
          coordinates.equatorialMagneticLocalTimeHours[rowOffset + nextMltIndex]!
          - coordinates.equatorialMagneticLocalTimeHours[rowOffset + mltIndex]!
          + 24
        ) % 24;
        stepErrors.push(Math.abs(actualStep - expectedStep));
      }
    }
    candidates.push({ radialCount, magneticLocalTimeCount: mltCount, score: mean(recurrence) + mean(stepErrors) });
  }
  candidates.sort((first, second) => first.score - second.score || first.magneticLocalTimeCount - second.magneticLocalTimeCount);
  const best = candidates[0];
  if (!best || best.score > 24 / best.magneticLocalTimeCount) {
    throw new RangeError("RBE radial/MLT topology cannot be inferred; publish an explicit gridShape");
  }
  return { radialCount: best.radialCount, magneticLocalTimeCount: best.magneticLocalTimeCount };
}

function setSourcePointIndex(geometry: THREE.BufferGeometry, indices: number[]) {
  const maximum = indices.reduce((value, index) => Math.max(value, index), 0);
  geometry.setAttribute(
    "sourcePointIndex",
    maximum <= 65535
      ? new THREE.Uint16BufferAttribute(indices, 1)
      : new THREE.Uint32BufferAttribute(indices, 1),
  );
}

function pushQuad(indices: number[], a: number, b: number, c: number, d: number, reverse = false) {
  if (reverse) indices.push(a, c, b, b, c, d);
  else indices.push(a, b, c, b, d, c);
}

function withoutDegenerateTriangles(positions: ArrayLike<number>, indices: number[]) {
  const filtered: number[] = [];
  for (let index = 0; index < indices.length; index += 3) {
    const a = indices[index]! * 3;
    const b = indices[index + 1]! * 3;
    const c = indices[index + 2]! * 3;
    const abx = positions[b]! - positions[a]!;
    const aby = positions[b + 1]! - positions[a + 1]!;
    const abz = positions[b + 2]! - positions[a + 2]!;
    const acx = positions[c]! - positions[a]!;
    const acy = positions[c + 1]! - positions[a + 1]!;
    const acz = positions[c + 2]! - positions[a + 2]!;
    const crossX = aby * acz - abz * acy;
    const crossY = abz * acx - abx * acz;
    const crossZ = abx * acy - aby * acx;
    if (crossX * crossX + crossY * crossY + crossZ * crossZ > 1e-18) {
      filtered.push(indices[index]!, indices[index + 1]!, indices[index + 2]!);
    }
  }
  return filtered;
}

export interface NativeEquatorialRadiationOptions {
  gridShape?: RadiationGridShape;
  displayWindow?: Partial<RadiationBeltDisplayWindow>;
}

/**
 * Creates a smooth indexed annular surface from the native RBE radial/MLT
 * topology. Every vertex position and flux is a source sample; only the
 * triangles between immediate source-grid neighbors are a display mapping.
 */
export function createNativeEquatorialRadiationGeometry(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  energyKev: number,
  positionForGsm: RadiationPositionMapper = (x, y, z) => new THREE.Vector3(x, y, z),
  options: NativeEquatorialRadiationOptions = {},
) {
  const coordinates = decodeRadiationBeltCoordinates(definition, frame);
  const flux = decodeRadiationFlux(encodedEnergy(frame.electronFluxU16, energyKev), definition.count);
  const shape = resolveRadiationGridShape(definition, coordinates, options.gridShape);
  const displayWindow = resolveRadiationBeltDisplayWindow(options.displayWindow);
  const fluxFloor = normalizedRadiationFluxFloor(definition.encoding, displayWindow);
  const positions = new Float32Array(definition.count * 3);
  const sourcePointIndices = new Array<number>(definition.count);
  const radialIndices = new Uint16Array(definition.count);
  const mltIndices = new Uint16Array(definition.count);
  const drawnSourcePoint = new Uint8Array(definition.count);
  for (let index = 0; index < definition.count; index += 1) {
    const gsm = equatorialRadiationPosition(
      coordinates.equatorialRadiusRe[index]!,
      coordinates.equatorialMagneticLocalTimeHours[index]!,
    );
    positionForGsm(gsm.x, gsm.y, gsm.z).toArray(positions, index * 3);
    sourcePointIndices[index] = index;
    radialIndices[index] = Math.floor(index / shape.magneticLocalTimeCount);
    mltIndices[index] = index % shape.magneticLocalTimeCount;
    drawnSourcePoint[index] = coordinates.equatorialRadiusRe[index]! >= displayWindow.minimumEquatorialRadiusRe
      && flux[index]! >= fluxFloor
      ? 1
      : 0;
  }
  const triangleIndices: number[] = [];
  if (shape.radialCount > 1 && shape.magneticLocalTimeCount > 2) {
    for (let radialIndex = 0; radialIndex < shape.radialCount - 1; radialIndex += 1) {
      for (let mltIndex = 0; mltIndex < shape.magneticLocalTimeCount; mltIndex += 1) {
        const nextMlt = (mltIndex + 1) % shape.magneticLocalTimeCount;
        const inner = radialIndex * shape.magneticLocalTimeCount + mltIndex;
        const innerNext = radialIndex * shape.magneticLocalTimeCount + nextMlt;
        const outer = (radialIndex + 1) * shape.magneticLocalTimeCount + mltIndex;
        const outerNext = (radialIndex + 1) * shape.magneticLocalTimeCount + nextMlt;
        // Every corner of a painted cell must itself be inside the display
        // window, so the drawn edge is the model's own trapping edge and never
        // a half-cell that leaks toward the globe.
        if (!drawnSourcePoint[inner] || !drawnSourcePoint[innerNext] || !drawnSourcePoint[outer] || !drawnSourcePoint[outerNext]) continue;
        pushQuad(triangleIndices, inner, outer, innerNext, outerNext, true);
      }
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("fluxValue", new THREE.BufferAttribute(flux, 1));
  geometry.setAttribute("gridRadialIndex", new THREE.BufferAttribute(radialIndices, 1));
  geometry.setAttribute("gridMltIndex", new THREE.BufferAttribute(mltIndices, 1));
  setSourcePointIndex(geometry, sourcePointIndices);
  const nondegenerateTriangles = withoutDegenerateTriangles(positions, triangleIndices);
  geometry.setIndex(nondegenerateTriangles);
  if (nondegenerateTriangles.length > 0) geometry.computeVertexNormals();
  geometry.userData = {
    representation: "native-equatorial-neighbor-triangulation",
    gridShape: shape,
    fullNative3d: false,
    offEquatorMapping: false,
    sourceFluxPreservedAtVertices: true,
    displayWindow,
    drawnSourcePointCount: drawnSourcePoint.reduce((total, value) => total + value, 0),
  };
  return geometry;
}

/** Ideal centered-dipole field-strength ratio B(lambda) / B_equator. */
export function dipoleFieldRatio(latitudeRadians: number) {
  const sine = Math.sin(latitudeRadians);
  const cosine = Math.cos(latitudeRadians);
  return Math.sqrt(1 + 3 * sine * sine) / Math.max(Math.pow(cosine, 6), 1e-15);
}

/** Equatorially mirroring particles return 0; loss-cone-like channels approach pi/2. */
export function dipoleMirrorLatitudeRadians(equatorialPitchSin: number) {
  const pitchSin = THREE.MathUtils.clamp(equatorialPitchSin, 0, 1);
  if (pitchSin <= 0) return Math.PI / 2;
  if (pitchSin >= 1) return 0;
  const targetRatio = 1 / (pitchSin * pitchSin);
  let low = 0;
  let high = Math.PI / 2 - 1e-6;
  for (let iteration = 0; iteration < 60; iteration += 1) {
    const middle = (low + high) / 2;
    if (dipoleFieldRatio(middle) < targetRatio) low = middle;
    else high = middle;
  }
  return (low + high) / 2;
}

export function dipoleRadiationPosition(
  equatorialRadiusRe: number,
  magneticLocalTimeHours: number,
  latitudeRadians: number,
) {
  const cosineLatitude = Math.cos(latitudeRadians);
  const radius = equatorialRadiusRe * cosineLatitude * cosineLatitude;
  const cylindricalRadius = radius * cosineLatitude;
  const azimuth = (magneticLocalTimeHours - 12) * Math.PI / 12;
  return new THREE.Vector3(
    cylindricalRadius * Math.cos(azimuth),
    cylindricalRadius * Math.sin(azimuth),
    radius * Math.sin(latitudeRadians),
  );
}

function validatedPitchAngles(pitchCoordinatesSin: number[]) {
  if (pitchCoordinatesSin.length === 0) throw new RangeError("RBE pitch grid is empty");
  const angles = pitchCoordinatesSin.map((value) => {
    if (!Number.isFinite(value) || value < 0 || value > 1) {
      throw new RangeError(`RBE pitch coordinate sin(alpha)=${value} lies outside [0, 1]`);
    }
    return Math.asin(value);
  });
  for (let index = 1; index < angles.length; index += 1) {
    if (angles[index]! <= angles[index - 1]!) {
      throw new RangeError("RBE pitch coordinates must be strictly increasing");
    }
  }
  return angles;
}

/**
 * Equatorial pitch-angle bin edges, in radians, for the published pitch grid.
 *
 * Edges sit midway between published pitch angles and close at 0 and pi/2, so
 * the bins tile the hemisphere exactly once with no gap and no overlap.
 */
export function gyrotropicPitchBinEdgeAngles(pitchCoordinatesSin: number[]) {
  const angles = validatedPitchAngles(pitchCoordinatesSin);
  const edges = [0];
  for (let index = 1; index < angles.length; index += 1) {
    edges.push((angles[index - 1]! + angles[index]!) / 2);
  }
  edges.push(Math.PI / 2);
  return edges;
}

/**
 * cos(alpha_local) for a particle whose equatorial pitch angle is
 * `equatorialAngleRadians`, at a place where B/B_eq is `fieldRatio`.
 *
 * The first adiabatic invariant gives sin^2(alpha_local) = fieldRatio *
 * sin^2(alpha_equatorial). A particle whose invariant demands sin^2 > 1 has
 * already mirrored below this point and is simply not there, which is the zero.
 */
export function localPitchCosine(equatorialAngleRadians: number, fieldRatio: number) {
  const sine = Math.sin(equatorialAngleRadians);
  const cosineSquared = 1 - fieldRatio * sine * sine;
  return cosineSquared > 0 ? Math.sqrt(cosineSquared) : 0;
}

/**
 * Solid-angle quadrature weights for a gyrotropic pitch distribution, evaluated
 * in the local field rather than at the equator.
 *
 * The measure for an omnidirectional integral over a gyrotropic distribution is
 * d(cos alpha), so each bin's weight is the span in cos(alpha_local) that the
 * bin covers where it is measured. Mapping the equatorial bin edges through the
 * first invariant gives that span directly, and a bin whose particles have
 * already mirrored collapses to zero width.
 *
 * At `fieldRatio` 1 this is the equatorial case and reduces exactly to
 * cos(lower) - cos(upper) over one hemisphere, summing to one.
 */
export function gyrotropicLocalPitchBinWeights(pitchCoordinatesSin: number[], fieldRatio: number) {
  if (!Number.isFinite(fieldRatio) || fieldRatio < 1) {
    throw new RangeError("local field ratio B/B_eq must be finite and at least 1");
  }
  const edges = gyrotropicPitchBinEdgeAngles(pitchCoordinatesSin);
  const weights: number[] = [];
  for (let index = 0; index + 1 < edges.length; index += 1) {
    weights.push(localPitchCosine(edges[index]!, fieldRatio) - localPitchCosine(edges[index + 1]!, fieldRatio));
  }
  return weights;
}

/**
 * Hemisphere-normalized solid-angle quadrature weights for a gyrotropic pitch
 * distribution. The bin edges are midway between published pitch angles and
 * close at 0 and pi/2, so the returned weights are positive and sum to one.
 */
export function gyrotropicPitchBinWeights(pitchCoordinatesSin: number[]) {
  return gyrotropicLocalPitchBinWeights(pitchCoordinatesSin, 1);
}

function pitchBinWeight(pitchCoordinatesSin: number[], pitchIndex: number) {
  return gyrotropicPitchBinWeights(pitchCoordinatesSin)[pitchIndex]!;
}

/**
 * Highest magnetic latitude a bounce shell of equatorial radius
 * `equatorialRadiusRe` can reach before the ideal dipole field line drops below
 * `trappingFloorRe`. Particles mirroring beyond it are in the loss cone.
 *
 * r = L cos^2(lambda) inverted. This is a function of L, so the loss cone is a
 * function of L: the larger the shell, the more of the pitch grid is trapped.
 */
export function trappingFootpointLatitudeRadians(equatorialRadiusRe: number, trappingFloorRe: number) {
  if (!(equatorialRadiusRe > trappingFloorRe)) return 0;
  return Math.acos(Math.sqrt(trappingFloorRe / equatorialRadiusRe));
}

/**
 * Which published pitch channels are trapped on the shell at
 * `equatorialRadiusRe`: those whose mirror latitude is reached before the field
 * line meets the trapping floor.
 *
 * `mirrorLatitudesRadians` is passed in because the caller computes it once for
 * the whole grid; it is a property of the pitch grid alone, not of the radius.
 */
export function trappedPitchIndicesAtRadius(
  mirrorLatitudesRadians: readonly number[],
  equatorialRadiusRe: number,
  trappingFloorRe: number,
) {
  const footpoint = trappingFootpointLatitudeRadians(equatorialRadiusRe, trappingFloorRe);
  const indices: number[] = [];
  for (let index = 0; index < mirrorLatitudesRadians.length; index += 1) {
    if (mirrorLatitudesRadians[index]! < footpoint) indices.push(index);
  }
  return indices;
}

/**
 * The shared closed-shell topology for every mapped bounce volume: north and
 * south caps at the shell's outermost latitude, and walls wherever the drawn
 * region ends radially (the belt's own inner and outer edges, and any edge the
 * loss-cone or flux cut opens up mid-grid).
 *
 * `vertex(pointIndex, latitudeIndex)` resolves a source point and a latitude row
 * to a vertex; the caller owns the vertex layout, this owns the connectivity, so
 * the single-channel shell and the pitch-integrated volume cannot drift apart.
 */
function bounceShellTriangleIndices(
  shape: RadiationGridShape,
  validSourcePoint: Uint8Array,
  latitudeCount: number,
  vertex: (pointIndex: number, latitudeIndex: number) => number,
  includeMirrorCaps: boolean,
) {
  const triangleIndices: number[] = [];
  const mltCount = shape.magneticLocalTimeCount;
  const radialCount = shape.radialCount;

  // Optional north/south closure at mirror latitude. The stacked multi-pitch
  // display leaves these faces open and fades the boundary in its shader:
  // stacking opaque closure sheets makes a phase-space reconstruction look like
  // fans. A single volume wants them closed, so it reads as a volume.
  if (includeMirrorCaps) {
    for (let radialIndex = 0; radialIndex < radialCount - 1; radialIndex += 1) {
      for (let mltIndex = 0; mltIndex < mltCount; mltIndex += 1) {
        const nextMlt = (mltIndex + 1) % mltCount;
        const inner = radialIndex * mltCount + mltIndex;
        const innerNext = radialIndex * mltCount + nextMlt;
        const outer = (radialIndex + 1) * mltCount + mltIndex;
        const outerNext = (radialIndex + 1) * mltCount + nextMlt;
        if (![inner, innerNext, outer, outerNext].every((point) => validSourcePoint[point] === 1)) continue;
        pushQuad(triangleIndices, vertex(inner, 0), vertex(outer, 0), vertex(innerNext, 0), vertex(outerNext, 0), false);
        const north = latitudeCount - 1;
        pushQuad(triangleIndices, vertex(inner, north), vertex(outer, north), vertex(innerNext, north), vertex(outerNext, north), true);
      }
    }
  }

  // Close the radial boundaries (including a loss-cone-created inner edge).
  for (let radialIndex = 0; radialIndex < radialCount; radialIndex += 1) {
    for (let mltIndex = 0; mltIndex < mltCount; mltIndex += 1) {
      const nextMlt = (mltIndex + 1) % mltCount;
      const point = radialIndex * mltCount + mltIndex;
      const pointNext = radialIndex * mltCount + nextMlt;
      if (!validSourcePoint[point] || !validSourcePoint[pointNext]) continue;
      const previous = radialIndex > 0 ? (radialIndex - 1) * mltCount + mltIndex : -1;
      const previousNext = radialIndex > 0 ? (radialIndex - 1) * mltCount + nextMlt : -1;
      const next = radialIndex + 1 < radialCount ? (radialIndex + 1) * mltCount + mltIndex : -1;
      const nextNext = radialIndex + 1 < radialCount ? (radialIndex + 1) * mltCount + nextMlt : -1;
      const isInnerBoundary = previous < 0 || (!validSourcePoint[previous] && !validSourcePoint[previousNext]);
      const isOuterBoundary = next < 0 || (!validSourcePoint[next] && !validSourcePoint[nextNext]);
      for (let latitudeIndex = 0; latitudeIndex < latitudeCount - 1; latitudeIndex += 1) {
        if (isInnerBoundary) {
          pushQuad(
            triangleIndices,
            vertex(point, latitudeIndex),
            vertex(pointNext, latitudeIndex),
            vertex(point, latitudeIndex + 1),
            vertex(pointNext, latitudeIndex + 1),
            true,
          );
        }
        if (isOuterBoundary) {
          pushQuad(
            triangleIndices,
            vertex(point, latitudeIndex),
            vertex(pointNext, latitudeIndex),
            vertex(point, latitudeIndex + 1),
            vertex(pointNext, latitudeIndex + 1),
            false,
          );
        }
      }
    }
  }
  return triangleIndices;
}

export interface DipoleMappedRadiationOptions {
  samplesPerHemisphere?: number;
  /** Retained for API compatibility; indexed surface geometry requires 1. */
  pointStride?: number;
  pitchIndex?: number;
  includeLossCone?: boolean;
  /** Close the shell at mirror latitude. Disable for layered volume rendering to avoid opaque cap sheets. */
  includeMirrorCaps?: boolean;
  gridShape?: RadiationGridShape;
  positionForGsm?: RadiationPositionMapper;
  displayWindow?: Partial<RadiationBeltDisplayWindow>;
}

/**
 * Builds one closed, pitch-selected 3-D teaching shell from equatorial RBE
 * output. North/south caps and inner/outer walls use only neighboring source
 * cells, so the result reads as a trapped annular volume rather than sampled
 * field-line hairs. The off-equator positions remain an explicit centered-
 * dipole mapping, never native 3-D RBE output.
 */
export function createDipoleMappedRadiationGeometry(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  energyKev: number,
  options: DipoleMappedRadiationOptions = {},
) {
  const coordinates = decodeRadiationBeltCoordinates(definition, frame);
  const shape = resolveRadiationGridShape(definition, coordinates, options.gridShape);
  const pitchCount = definition.pitchCoordinatesSin.length;
  if (pitchCount === 0) throw new RangeError("RBE pitch grid is empty");
  const pitchIndex = THREE.MathUtils.clamp(
    Math.floor(options.pitchIndex ?? trappedPitchIndex(definition.pitchCoordinatesSin)),
    0,
    pitchCount - 1,
  );
  const allFlux = decodeRadiationFlux(
    encodedEnergy(frame.pitchResolvedElectronFluxU16, energyKev),
    definition.count * pitchCount,
  );
  const samplesPerHemisphere = Math.max(1, Math.floor(options.samplesPerHemisphere ?? 4));
  const pointStride = Math.max(1, Math.floor(options.pointStride ?? 1));
  if (pointStride !== 1) throw new RangeError("RBE mapped volume requires pointStride=1 to preserve native grid adjacency");
  const includeLossCone = options.includeLossCone ?? false;
  const includeMirrorCaps = options.includeMirrorCaps ?? true;
  const displayWindow = resolveRadiationBeltDisplayWindow(options.displayWindow);
  const fluxFloor = normalizedRadiationFluxFloor(definition.encoding, displayWindow);
  // The trapping floor, not RBE's ionospheric grid boundary, decides both which
  // cells are loss cone and how far down a field line is traced. RBE's own
  // boundary sits at roughly 100 km altitude; a bounce shell drawn to it lands
  // on the rendered globe.
  const trappingFloorRe = Math.max(definition.innerBoundaryRe, displayWindow.minimumMappedRadiusRe);
  const positionForGsm = options.positionForGsm ?? ((x, y, z) => new THREE.Vector3(x, y, z));
  const latitudeCount = samplesPerHemisphere * 2 + 1;
  const positions: number[] = [];
  const fluxValues: number[] = [];
  const equatorialPitchSinValues: number[] = [];
  const localPitchSinValues: number[] = [];
  const pitchWeights: number[] = [];
  const sourcePointIndices: number[] = [];
  const latitudeFractions: number[] = [];
  const vertexIndices = new Int32Array(definition.count * latitudeCount).fill(-1);
  const validSourcePoint = new Uint8Array(definition.count);
  const equatorialPitchSin = definition.pitchCoordinatesSin[pitchIndex]!;
  const mirrorLatitude = dipoleMirrorLatitudeRadians(equatorialPitchSin);
  const weight = pitchBinWeight(definition.pitchCoordinatesSin, pitchIndex);

  for (let pointIndex = 0; pointIndex < definition.count; pointIndex += 1) {
    const equatorialRadius = coordinates.equatorialRadiusRe[pointIndex]!;
    if (equatorialRadius <= trappingFloorRe) continue;
    const normalizedFlux = allFlux[pointIndex * pitchCount + pitchIndex]!;
    if (normalizedFlux < fluxFloor) continue;
    const footpointLatitude = Math.acos(Math.sqrt(trappingFloorRe / equatorialRadius));
    const trappedBeforeInnerBoundary = mirrorLatitude < footpointLatitude;
    if (!trappedBeforeInnerBoundary && !includeLossCone) continue;
    const maximumLatitude = Math.min(mirrorLatitude, footpointLatitude);
    if (maximumLatitude <= 1e-7) continue;
    validSourcePoint[pointIndex] = 1;
    for (let latitudeIndex = 0; latitudeIndex < latitudeCount; latitudeIndex += 1) {
      const latitudeFraction = latitudeIndex / samplesPerHemisphere - 1;
      const latitude = maximumLatitude * latitudeFraction;
      const gsm = dipoleRadiationPosition(
        equatorialRadius,
        coordinates.equatorialMagneticLocalTimeHours[pointIndex]!,
        latitude,
      );
      const mapped = positionForGsm(gsm.x, gsm.y, gsm.z);
      const vertexIndex = positions.length / 3;
      vertexIndices[pointIndex * latitudeCount + latitudeIndex] = vertexIndex;
      positions.push(mapped.x, mapped.y, mapped.z);
      fluxValues.push(normalizedFlux);
      equatorialPitchSinValues.push(equatorialPitchSin);
      localPitchSinValues.push(Math.min(1, equatorialPitchSin * Math.sqrt(dipoleFieldRatio(latitude))));
      pitchWeights.push(weight);
      sourcePointIndices.push(pointIndex);
      latitudeFractions.push(latitudeFraction);
    }
  }

  const triangleIndices = bounceShellTriangleIndices(
    shape,
    validSourcePoint,
    latitudeCount,
    (pointIndex, latitudeIndex) => vertexIndices[pointIndex * latitudeCount + latitudeIndex]!,
    includeMirrorCaps,
  );

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("fluxValue", new THREE.Float32BufferAttribute(fluxValues, 1));
  geometry.setAttribute("equatorialPitchSin", new THREE.Float32BufferAttribute(equatorialPitchSinValues, 1));
  geometry.setAttribute("localPitchSin", new THREE.Float32BufferAttribute(localPitchSinValues, 1));
  geometry.setAttribute("pitchWeight", new THREE.Float32BufferAttribute(pitchWeights, 1));
  geometry.setAttribute("latitudeFraction", new THREE.Float32BufferAttribute(latitudeFractions, 1));
  setSourcePointIndex(geometry, sourcePointIndices);
  const nondegenerateTriangles = withoutDegenerateTriangles(positions, triangleIndices);
  geometry.setIndex(nondegenerateTriangles);
  if (nondegenerateTriangles.length > 0) geometry.computeVertexNormals();
  geometry.userData = {
    representation: "closed-centered-dipole-mapped-trapped-flux-shell",
    gridShape: shape,
    pitchIndex,
    pitchCoordinateSin: equatorialPitchSin,
    validSourcePointCount: validSourcePoint.reduce((total, value) => total + value, 0),
    sourceFluxPreservedAtVertices: true,
    fullNative3d: false,
    fieldModel: "centered-ideal-dipole",
    forcedBeltCount: false,
    mirrorCapsIncluded: includeMirrorCaps,
    displayWindow,
    trappingFloorRe,
  };
  return geometry;
}

export type GyrotropicDipoleMappedRadiationOptions = Omit<DipoleMappedRadiationOptions, "pitchIndex"> & {
  /** Keep pitch channels with no trapped cells as empty shell records. */
  includeEmptyShells?: boolean;
};

export interface GyrotropicDipoleMappedRadiationShell {
  geometry: THREE.BufferGeometry;
  pitchIndex: number;
  equatorialPitchSin: number;
  equatorialPitchAngleDegrees: number;
  /** Integral of sin(alpha) d-alpha over this pitch bin, normalized over one hemisphere. */
  solidAngleWeight: number;
  mirrorLatitudeDegrees: number;
  validSourcePointCount: number;
}

export interface GyrotropicDipoleMappedRadiationReconstruction {
  shells: GyrotropicDipoleMappedRadiationShell[];
  metadata: {
    representation: "multi-pitch-gyrotropic-centered-dipole-shells";
    energyKev: number;
    sourcePitchChannelCount: number;
    renderedPitchChannelCount: number;
    excludedEmptyPitchIndices: number[];
    particlePopulation: typeof GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.particlePopulation;
    fullNative3d: false;
    nativeEquatorialViewPreserved: true;
    syntheticInnerBelt: false;
    protonPopulation: false;
    pitchQuadrature: "hemisphere-normalized solid-angle bins";
    fluxMeaning: "model-native differential electron flux; shells are not particle-density isosurfaces";
    displayWindow: RadiationBeltDisplayWindow;
    displayWindowMeaning: string;
    assumptions: typeof GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS;
  };
}

/**
 * Reconstruct all published pitch channels as separate nested teaching shells.
 *
 * The source differential electron flux remains attached to its native
 * equatorial radial/MLT sample. Only its off-equator position is reconstructed,
 * using an ideal centered dipole and first-invariant mirror mapping. Rendering
 * the returned geometries with translucent materials gives a pitch-resolved
 * outer-electron-belt volume without fabricating a proton/inner-belt torus.
 */
export function createGyrotropicDipoleMappedRadiationShells(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  energyKev: number,
  options: GyrotropicDipoleMappedRadiationOptions = {},
): GyrotropicDipoleMappedRadiationReconstruction {
  if (definition.pitchAnglesDegrees.length !== definition.pitchCoordinatesSin.length) {
    throw new RangeError("RBE pitch-angle labels do not match the pitch-coordinate grid");
  }
  const weights = gyrotropicPitchBinWeights(definition.pitchCoordinatesSin);
  const displayWindow = resolveRadiationBeltDisplayWindow(options.displayWindow);
  const includeEmptyShells = options.includeEmptyShells ?? false;
  const shells: GyrotropicDipoleMappedRadiationShell[] = [];
  const excludedEmptyPitchIndices: number[] = [];

  for (let pitchIndex = 0; pitchIndex < definition.pitchCoordinatesSin.length; pitchIndex += 1) {
    const geometry = createDipoleMappedRadiationGeometry(definition, frame, energyKev, {
      ...options,
      displayWindow,
      pitchIndex,
    });
    const validSourcePointCount = Number(geometry.userData.validSourcePointCount ?? 0);
    const isEmpty = geometry.getAttribute("position").count === 0 || geometry.index?.count === 0;
    geometry.userData = {
      ...geometry.userData,
      representation: "gyrotropic-pitch-bin-centered-dipole-shell",
      solidAngleWeight: weights[pitchIndex],
      gyrotropicAssumption: true,
      northSouthPitchSymmetryAssumption: true,
      particlePopulation: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.particlePopulation,
      syntheticInnerBelt: false,
      protonPopulation: false,
    };
    if (isEmpty && !includeEmptyShells) {
      excludedEmptyPitchIndices.push(pitchIndex);
      geometry.dispose();
      continue;
    }
    shells.push({
      geometry,
      pitchIndex,
      equatorialPitchSin: definition.pitchCoordinatesSin[pitchIndex]!,
      equatorialPitchAngleDegrees: definition.pitchAnglesDegrees[pitchIndex]!,
      solidAngleWeight: weights[pitchIndex]!,
      mirrorLatitudeDegrees: dipoleMirrorLatitudeRadians(definition.pitchCoordinatesSin[pitchIndex]!) * 180 / Math.PI,
      validSourcePointCount,
    });
  }

  return {
    shells,
    metadata: {
      representation: "multi-pitch-gyrotropic-centered-dipole-shells",
      energyKev,
      sourcePitchChannelCount: definition.pitchCoordinatesSin.length,
      renderedPitchChannelCount: shells.length,
      excludedEmptyPitchIndices,
      particlePopulation: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.particlePopulation,
      fullNative3d: false,
      nativeEquatorialViewPreserved: true,
      syntheticInnerBelt: false,
      protonPopulation: false,
      pitchQuadrature: "hemisphere-normalized solid-angle bins",
      fluxMeaning: "model-native differential electron flux; shells are not particle-density isosurfaces",
      displayWindow,
      displayWindowMeaning: `only the trapping region is drawn: equatorial radius at or above ${displayWindow.minimumEquatorialRadiusRe} Re, bounce shells cut at ${displayWindow.minimumMappedRadiusRe} Re, differential flux at or above 10^${displayWindow.minimumLog10Flux}. Cells outside the window contribute no geometry; nothing is interpolated, filled, or synthesized to replace them.`,
      assumptions: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS,
    },
  };
}

