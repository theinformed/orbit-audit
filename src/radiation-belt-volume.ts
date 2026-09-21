import { activeDistanceScale } from "./radial-ruler";
import * as THREE from "three";
import {
  COMBINED_RADIATION_ENERGY_KEV,
  COMBINED_RADIATION_ENERGY_LABEL,
  GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS,
  RADIATION_BELT_DISPLAY_WINDOW,
  dipoleMirrorLatitudeRadians,
  dipoleRadiationPosition,
  decodeRadiationBeltCoordinates,
  decodeRadiationFlux,
  dipoleFieldRatio,
  gyrotropicPitchBinEdgeAngles,
  isCombinedRadiationEnergy,
  localPitchCosine,
  resolveRadiationBeltDisplayWindow,
  resolveRadiationGridShape,
  trappingFootpointLatitudeRadians,
} from "./radiation-belt";
import type {
  RadiationBeltDefinition,
  RadiationBeltDisplayWindow,
  RadiationBeltFrame,
  RadiationPositionMapper,
} from "./radiation-belt";

/**
 * Volumetric rendering of the omnidirectional RBE electron flux field.
 *
 * The previous presentation extracted an iso-surface: it drew the closed
 * envelope of "everywhere the integrated flux clears the display floor". An
 * envelope's shape is decided entirely by wherever that threshold happens to
 * fall, so channels holding half a percent of the trapped solid angle — real,
 * above-floor, and mirroring at 60-76 degrees — inflated the surface into a
 * faceted balloon that swallowed the poles and visually closed the slot.
 *
 * This module renders the field itself instead. The flux at every point of the
 * dipole-mapped volume is baked into a 3-D texture, and a raymarching shader
 * accumulates colour and opacity along each view ray, with opacity driven by
 * the local flux. Nothing decides a boundary: the slot is dark because the
 * model has little there, the belts are bright because it has much, and the
 * volume fades at exactly the rate the pitch quadrature says the population
 * thins. Where the belts genuinely merge at low energy, the picture merges,
 * because there is no shape left to disagree with the data.
 *
 * What is baked is the same integral the previous surface computed, unchanged:
 * at each equatorial radius, MLT and magnetic latitude, every published pitch
 * channel that is still locally present (not yet mirrored, and trapped above
 * the display floor's trapping radius) contributes its equatorial differential
 * flux weighted by the solid angle its bin occupies in the local field. The
 * disclosed assumptions are also unchanged: centered ideal dipole, gyrotropy,
 * north/south symmetry, equatorial-only source, no transport solution, no
 * proton or synthetic inner belt.
 */

/** One scene-space frame derived from the layer's position mapper. */
export interface RadiationMapperFrame {
  earthSceneRadius: number;
  /** Rows are the local-space directions of GSM +X, +Y, +Z. */
  gsmFromLocal: THREE.Matrix3;
  sceneRadiusForRe: (radiusRe: number) => number;
  /** Numerical inverse of sceneRadiusForRe over [1, maximumRe]. */
  radiusReForSceneRadius: (sceneRadius: number) => number;
}

/**
 * Derive the scene frame the shader needs by probing the layer's own position
 * mapper, instead of duplicating the radial ruler's constants. The volume
 * therefore follows whatever the shared ruler is at bake time; a change to the
 * compression curve changes this bake with it and cannot silently diverge.
 *
 * The probe also verifies the two properties the raymarcher depends on: the
 * mapper must scale radially (identical scene radius in every direction, so a
 * scene sphere is a physical sphere) and monotonically (so the inverse exists).
 * The magnetosphere mapper's anti-sunward tail stretch would fail this check,
 * which is deliberate: this volume must only ever be driven by the radiation
 * mapper, which applies no stretch.
 */
export function describeRadiationMapperFrame(
  mapper: RadiationPositionMapper,
  maximumRe = 20,
): RadiationMapperFrame {
  const alongX = (r: number) => mapper(r, 0, 0);
  const earthSceneRadius = alongX(1).length();
  if (!Number.isFinite(earthSceneRadius) || earthSceneRadius <= 0) {
    throw new RangeError("radiation mapper does not place the Earth at a positive scene radius");
  }
  const axisX = alongX(1).normalize();
  const axisY = mapper(0, 1, 0).normalize();
  const axisZ = mapper(0, 0, 1).normalize();
  const tolerance = 1e-6;
  if (
    Math.abs(axisX.dot(axisY)) > tolerance
    || Math.abs(axisX.dot(axisZ)) > tolerance
    || Math.abs(axisY.dot(axisZ)) > tolerance
  ) {
    throw new RangeError("radiation mapper axes are not orthogonal; the volume cannot invert it");
  }
  let previous = 0;
  for (const radius of [1, 1.5, 2, 3, 5, 8, 12, maximumRe]) {
    const x = alongX(radius).length();
    const probes = [
      mapper(-radius, 0, 0),
      mapper(0, radius, 0),
      mapper(0, -radius, 0),
      mapper(0, 0, radius),
      mapper(0, 0, -radius),
    ];
    // Negative axes matter: the magnetosphere mapper's anti-sunward tail
    // stretch only acts on x < 0, so probing the positive axes alone would
    // accept exactly the mapper this check exists to reject.
    if (probes.some((probe) => Math.abs(probe.length() - x) > tolerance * x)) {
      throw new RangeError(
        "radiation mapper is not radially isotropic (a tail stretch or per-axis scale is present); "
        + "the raymarched belt volume requires the radiation mapper, not the magnetosphere mapper",
      );
    }
    if (x <= previous) {
      throw new RangeError("radiation mapper scene radius is not strictly increasing");
    }
    previous = x;
  }
  const sceneRadiusForRe = (radiusRe: number) => alongX(Math.max(radiusRe, 1e-3)).length();
  const radiusReForSceneRadius = (sceneRadius: number) => {
    let low = 1e-3;
    let high = maximumRe;
    if (sceneRadius <= sceneRadiusForRe(low)) return low;
    if (sceneRadius >= sceneRadiusForRe(high)) return high;
    for (let iteration = 0; iteration < 64; iteration += 1) {
      const middle = (low + high) / 2;
      if (sceneRadiusForRe(middle) < sceneRadius) low = middle;
      else high = middle;
    }
    return (low + high) / 2;
  };
  const gsmFromLocal = new THREE.Matrix3().set(
    axisX.x, axisX.y, axisX.z,
    axisY.x, axisY.y, axisY.z,
    axisZ.x, axisZ.y, axisZ.z,
  );
  return { earthSceneRadius, gsmFromLocal, sceneRadiusForRe, radiusReForSceneRadius };
}

/**
 * The transfer function, in the units the audience already reads: log10 of
 * model-native differential flux.
 *
 * It has two halves that are deliberately NOT the same knob.
 *
 * ## Colour is one constant scale for every energy view (2026-08-09)
 *
 * `colourFloorLog10Flux` and `colourCeilingLog10Flux` are fixed across all
 * five views — the four published channels and the combined one. A given flux
 * is the same colour in every view, so a reader can compare 88 keV against
 * 2.32 MeV by colour alone and see that the low channel really does carry a
 * hundred times the flux. That was a direct instruction and it is not
 * negotiable by a per-energy tweak.
 *
 * The endpoints come from the union of what the channels occupy on the pinned
 * 2026-08-08T23:40Z frame: the highest sample anywhere is 10^5.33 (88 keV),
 * the lowest interesting one is the layer's long-declared 10^1 display floor,
 * so the ramp runs 10^1 to 10^5.5. Occupied maxima per channel, measured:
 * 88 keV 10^5.33, 453 keV 10^4.43, 1.35 MeV 10^3.65, 2.32 MeV 10^3.00,
 * combined 10^3.65. Above the ceiling the colour saturates; the flux is still
 * reported honestly in the readouts.
 *
 * ## Opacity is tuned per view, and only opacity
 *
 * Each view draws nothing below its own opacity floor, and accumulates its own
 * `extinctionPerSceneUnit` (density per scene unit of ray length) above it.
 * The floor is DERIVED from the loaded field on every bake
 * (`deriveRadiationVolumeOpacityFloor`); the extinction, and the floor used
 * when a field cannot be read, come from `RADIATION_VOLUME_OPACITY_BY_VIEW`.
 * Nothing in either half can change what colour a flux is.
 *
 * - `opacityCurveExponent` shapes density against the opacity coordinate. It
 *   is 1 — opacity simply proportional to flux above the view's own floor —
 *   and that is a measured choice, not a default. Raising it was tried as an
 *   alternative to per-view floors and it fails in both directions: at 88 keV
 *   an exponent of 8 was needed to reach the contrast a floor at 10^4.25
 *   reaches, and at 1.35 MeV any exponent above 1 buries the inner belt,
 *   which sits only 0.7 of a decade above the floor while the outer core sits
 *   2.6 above it.
 * - `maximumAccumulatedOpacity` caps what any single ray may reach. It is a
 *   display ceiling of last resort, not a data statement; with the tuned table
 *   below, no view's brightest ray comes within 0.15 of it.
 *
 * The ray-integrated profile that each view produces from the layer's own
 * default camera is recorded in the table and pinned by
 * `tests/radiation-volume-transfer.test.ts`.
 */
export const RADIATION_VOLUME_TRANSFER = {
  colourFloorLog10Flux: 1.0,
  colourCeilingLog10Flux: 5.5,
  opacityCurveExponent: 1.0,
  maximumAccumulatedOpacity: 0.94,
} as const;

/** Ray-integrated opacity a view produces, from the layer's own default camera. */
export interface RadiationVolumeMeasuredProfile {
  /** Brightest ray whose impact parameter lands on the inner belt. */
  innerAlpha: number;
  innerL: number;
  /** Darkest ray between the belts. */
  slotAlpha: number;
  slotL: number;
  /** Brightest ray on the outer belt. */
  outerAlpha: number;
  outerL: number;
}

export interface RadiationVolumeOpacitySetting {
  /** Published channel energy, or `COMBINED_RADIATION_ENERGY_KEV`. */
  energyKev: number;
  label: string;
  /**
   * The floor this view falls back to when the loaded data cannot be read.
   *
   * Since 2026-08-09 this is NOT what normally ships on screen: every load
   * derives its own floor from its own field by the rule in
   * `deriveRadiationVolumeOpacityFloor`. This number is that same rule's answer
   * on the pinned 2026-08-08T23:40Z frame, kept as the last resort for an empty
   * view, a field with no two-belt structure, or a frame whose flux is mostly
   * absent — and it is disclosed on the card whenever it is what gets used.
   */
  fallbackFloorLog10Flux: number;
  extinctionPerSceneUnit: number;
  measuredProfile: RadiationVolumeMeasuredProfile;
  /** Why the fallback number is what it is, in one sentence, for the readout. */
  reason: string;
}

/**
 * Per-view opacity: the extinction each view ships with, and the floor each
 * view falls back to when its own data cannot be read.
 *
 * The reason the floor has to move at all is that the four channels do not
 * occupy remotely the same range. At 88 keV the model's electrons fill every
 * cell from L 1.25 to the grid edge at 10^3 and above, so a floor at 10^1
 * makes every ray cross six decades of material and every ray saturates: the
 * picture is a solid ball, which is exactly the complaint that started this
 * pass ("if I go to 88 keV the entire earth is washed out"). At 2.32 MeV the
 * same floor draws a thin outer shell and nothing else, because there is
 * nothing else. One floor cannot serve both.
 *
 * ## The rule, so that no floor is a taste
 *
 * **Each view's opacity floor is its own deepest inter-belt minimum, rounded
 * DOWN to the next 0.05 decade, and never below the layer's long-declared
 * 10^1 display floor.**
 *
 * The minimum is found by reading the baked volume's equatorial profile at
 * every MLT between L 2 and L 3.6 and taking the smallest value anywhere.
 * Setting the floor just under it means the floor removes only the diffuse
 * skirt BELOW the belt system: everything from the bottom of the slot upward
 * is drawn, and the slot is therefore dark because the model has little
 * there, never because a threshold cut it out. That was the layer's founding
 * promise and this rule is what keeps it while still letting each energy be
 * legible.
 *
 * **Since 2026-08-09 that rule RUNS, per dataset, at load time.** Every bake —
 * every dataset, every frame, every energy view — reads its own field and
 * derives its own floor from it (`deriveRadiationVolumeOpacityFloor`), so a
 * quiet frame and a storm frame are each drawn against their own slot rather
 * than against a table measured once in August. Sean asked for exactly that:
 * "each time we load a dataset there should be some value checker which helps
 * adjust the scale so that we see the belts just a little more clearly."
 * The numbers below are what that same rule returned on the pinned
 * 2026-08-08T23:40Z frame; they remain here as the fallback for data the rule
 * cannot read, and `tests/radiation-volume-transfer.test.ts` pins that the
 * live derivation still reproduces every one of them on that frame.
 *
 * Extinction is NOT derived and is deliberately left static per view. It is
 * the one number in this layer that was chosen by rendering and looking —
 * high enough that the belt reads as a solid object, low enough that no ray
 * approaches the opacity cap — and there is no statable property of the data
 * that fixes it (1.35 MeV and the combined view occupy the same maximum,
 * 10^3.65, and want different extinctions). Calling it derived would be a
 * fabricated rule; it stays a disclosed display judgement.
 *
 * Measured on the pinned 2026-08-08T23:40Z frame:
 *
 * | view     | inner peak    | inter-belt min | outer peak    | floor   |
 * |----------|---------------|----------------|---------------|---------|
 * | 88 keV   | 10^5.07 L1.88 | 10^4.21 L3.30  | 10^5.33 L4.48 | 10^4.20 |
 * | 453 keV  | 10^3.90 L1.76 | 10^2.49 L3.02  | 10^4.43 L4.02 | 10^2.45 |
 * | 1.35 MeV | 10^1.67 L1.56 | 10^0.93 L2.08  | 10^3.65 L3.30 | 10^1.00 |
 * | 2.32 MeV | 10^0.84 L1.56 | 10^-0.40 L2.04 | 10^3.00 L3.02 | 10^1.00 |
 * | combined | 10^3.18 L1.80 | 10^2.63 L2.76  | 10^3.65 L3.66 | 10^2.60 |
 *
 * The minima column was re-measured on 2026-08-19, when the shared ruler's
 * geostationary joint became C1 and the bake's radial grid — which is laid
 * uniformly in DRAWN radius — re-spaced with it. It barely moved, and it could
 * not have moved much: every one of these features sits below L 4.5, where the
 * ruler is untouched, so only the bake's own sampling of them shifted. The
 * FLUX values are unchanged to the digit shown; three of the L positions moved
 * by one 0.02 sampling step. The ray-integrated opacities below are the ones
 * that genuinely moved, because a ray crosses the whole volume including the
 * part that re-spaced.
 *
 * At both relativistic channels the minimum is already below 10^1, so the
 * floor does not move at all: the slot there is empty in the model's own
 * terms, which is why 1.35 MeV was the energy the layer opened on.
 *
 * Extinction is then the one free number per view, chosen by rendering and
 * LOOKING: high enough that the belt is a solid object, low enough that no
 * ray approaches the opacity cap, since a capped ray is a ray whose
 * brightness the flux no longer decides. The resulting ray-integrated profile
 * from the layer's own default camera, at the bake resolution the guard test
 * uses (128 x 32 x 56):
 *
 * | view     | extinction | inner | slot  | outer | slot vs outer |
 * |----------|------------|-------|-------|-------|---------------|
 * | 88 keV   | 0.008      | 0.742 | 0.543 | 0.676 | 20% darker    |
 * | 453 keV  | 0.008      | 0.606 | 0.413 | 0.521 | 21% darker    |
 * | 1.35 MeV | 0.016      | 0.509 | 0.441 | 0.733 | 40% darker    |
 * | 2.32 MeV | 0.020      | 0.310 | 0.325 | 0.624 | 48% darker    |
 * | combined | 0.020      | 0.596 | 0.458 | 0.626 | 27% darker    |
 *
 * Re-measured 2026-08-19 with the ruler's C1 geostationary joint. Every ray
 * lost about 1.5% of its accumulated opacity — the outer scene draws 4.41%
 * closer in, so the grid the ray marches through is slightly denser and its
 * outer reach slightly shorter. NO extinction was retuned to compensate and no
 * floor moved: the free parameter per view is exactly what it was, and these
 * are the numbers the same tuning now produces. The structure the tuning was
 * chosen for is intact and marginally better — the slot reads 1 to 2 points
 * DARKER against the outer belt in every view.
 *
 * The floor is a DISPLAY floor and it is disclosed on the layer, the same way
 * the single 10^1 floor always was. It never changes a colour, it never moves
 * a boundary, and opacity stays monotonic in flux inside every view: more
 * flux is always more opaque.
 */
export const RADIATION_VOLUME_OPACITY_BY_VIEW: readonly RadiationVolumeOpacitySetting[] = [
  {
    energyKev: 88.349,
    label: "88 keV",
    // The model puts 10^3 to 10^5.3 electrons everywhere from the trapping
    // floor to the grid edge at this energy, so the honest statement is that
    // the 88 keV population fills the whole volume: its own deepest inter-belt
    // minimum is still 10^4.21. Drawing everything above that shows the two
    // flux maxima that are genuinely there — 10^5.07 at L 1.88 and 10^5.33 at
    // L 4.48 — and lets the Earth stay visible inside them. Everything the
    // floor removes lies BELOW the bottom of this channel's own slot.
    fallbackFloorLog10Flux: 4.20,
    extinctionPerSceneUnit: 0.008,
    measuredProfile: { innerAlpha: 0.742, innerL: 1.61, slotAlpha: 0.543, slotL: 2.90, outerAlpha: 0.676, outerL: 3.94 },
    reason: "the 88 keV population fills the whole trapped volume and its own inter-belt minimum is still 10^4.21, "
      + "so the floor sits just under that; the belts do not separate at this energy, they only shoulder",
  },
  {
    energyKev: 452.75,
    label: "453 keV",
    // The slot is opening here but not empty: 10^3.90 at L 1.76, down to
    // 10^2.49 at L 3.00, back up to 10^4.43 at L 4.02. The floor sits under
    // the 10^2.49 minimum, so every electron the model puts in the slot is
    // still drawn and the slot reads as partly filled — which it is.
    fallbackFloorLog10Flux: 2.45,
    extinctionPerSceneUnit: 0.008,
    measuredProfile: { innerAlpha: 0.606, innerL: 1.57, slotAlpha: 0.413, slotL: 2.76, outerAlpha: 0.521, outerL: 3.55 },
    reason: "at 453 keV the slot is opening but not empty; its own minimum is 10^2.49 and the floor sits under it, "
      + "so what fills the slot on screen is the model's own electrons",
  },
  {
    energyKev: 1345.7,
    label: "1.35 MeV",
    // The layer's opening view, and the one that already worked. The floor
    // stays at the layer's long-declared 10^1 because this channel's own
    // inter-belt minimum, 10^0.94, is already below it: the darkness there is
    // the model's and the rule has nothing to remove. Extinction rose from
    // 0.010 to 0.016 only to hold the previously shipped brightness after the
    // colour ceiling moved from 10^4 to 10^5.5.
    fallbackFloorLog10Flux: 1.0,
    extinctionPerSceneUnit: 0.016,
    measuredProfile: { innerAlpha: 0.509, innerL: 1.45, slotAlpha: 0.441, slotL: 1.90, outerAlpha: 0.733, outerL: 3.04 },
    reason: "at 1.35 MeV the slot's own minimum, 10^0.94, is already below the layer's declared 10^1 floor, "
      + "so nothing at all is hidden to make it",
  },
  {
    energyKev: 2320.1,
    label: "2.32 MeV",
    // Outer belt only, and that is the model's answer, not a display choice:
    // the inner belt at 2.32 MeV peaks at 10^0.84, below the 10^1 floor. The
    // measured inner and slot rays are equal to within 2%, which is the
    // number that says "there is no inner belt here".
    fallbackFloorLog10Flux: 1.0,
    extinctionPerSceneUnit: 0.020,
    measuredProfile: { innerAlpha: 0.310, innerL: 1.84, slotAlpha: 0.325, slotL: 1.90, outerAlpha: 0.624, outerL: 3.04 },
    reason: "2.32 MeV is an outer belt and nothing else; the model's inner belt peaks at 10^0.84, below the display floor",
  },
  {
    energyKev: COMBINED_RADIATION_ENERGY_KEV,
    label: COMBINED_RADIATION_ENERGY_LABEL,
    // The energy-weighted band average peaks at 10^3.18 (L 1.80) and 10^3.65
    // (L 3.66) with a 10^2.63 minimum at L 2.76 between them. The floor sits
    // just under that minimum, so the slot on screen is dark because the
    // combined field is thin there and not because anything inside it was cut.
    //
    // This is the one view whose derived floor now depends on the bake
    // resolution, and it is worth knowing why. The rule rounds the minimum DOWN
    // to a 0.05 decade quantum. Since the C1 ruler change re-spaced the bake,
    // the guard's 128x32x56 bake reads the minimum at 10^2.6278 and the
    // browser's 192x64x88 bake reads it at 10^2.6588, which straddle 2.65: the
    // guard resolution derives 2.60 and the browser derives 2.65. Both are
    // below their own bake's minimum, which is the property that matters — the
    // floor never removes anything from inside the slot. The number kept here
    // is the one the guard's bake produces, and
    // `tests/radiation-volume-transfer.test.ts` now pins that the two
    // resolutions agree to within one quantum rather than exactly.
    fallbackFloorLog10Flux: 2.60,
    extinctionPerSceneUnit: 0.020,
    measuredProfile: { innerAlpha: 0.596, innerL: 1.61, slotAlpha: 0.458, slotL: 2.41, outerAlpha: 0.626, outerL: 3.20 },
    reason: "the combined volume's own minimum between the belts is 10^2.62 and the floor sits just under it, "
      + "so every electron the model puts in the slot is still drawn",
  },
];

/**
 * The static half of a view's opacity settings: its extinction, and the floor
 * it falls back to if its own data cannot be read.
 *
 * Matched by VALUE against the published channel energies, never by index, so
 * an artifact that publishes its channels in another order cannot silently
 * hand 88 keV the relativistic tuning.
 *
 * If NOAA ever republishes RBE on a different energy grid, the nearest tuned
 * channel in log-energy is inherited rather than the layer going blank or
 * throwing — an untuned picture beats no picture — and the result says
 * `tuned: false` so the readout can admit that the extinction was measured for
 * a neighbouring channel. (The FLOOR does not need the table on a new grid: it
 * is derived from whatever field is loaded. Only extinction is inherited.)
 */
export function resolveRadiationVolumeOpacity(
  energyKev: number,
): RadiationVolumeOpacitySetting & { tuned: boolean } {
  const exact = RADIATION_VOLUME_OPACITY_BY_VIEW
    .find((entry) => Math.abs(entry.energyKev - energyKev) < 1e-3);
  if (exact) return { ...exact, tuned: true };
  const channels = RADIATION_VOLUME_OPACITY_BY_VIEW
    .filter((entry) => entry.energyKev > 0);
  const target = Math.log10(Math.max(energyKev, 1e-6));
  const nearest = channels.reduce((best, entry) =>
    Math.abs(Math.log10(entry.energyKev) - target) < Math.abs(Math.log10(best.energyKev) - target)
      ? entry
      : best);
  return {
    ...nearest,
    tuned: false,
    reason: `${nearest.reason} (inherited from the ${nearest.label} channel; `
      + `this build has no measured tuning for ${energyKev} keV)`,
  };
}

/**
 * The constants the load-time floor derivation reads the field with.
 *
 * The L window is the slot region the layer has always quoted. The sampling
 * steps are deliberately FIXED rather than tied to the texel grid: the bake
 * runs at 192x64x88 in the browser and at smaller sizes in tests and harnesses,
 * and a floor that moved with the texture resolution would make the picture a
 * function of the machine. Sampling the baked field on its own fixed grid gives
 * the same answer at every bake size (verified at both resolutions in
 * `tests/radiation-volume-transfer.test.ts`).
 */
export const RADIATION_VOLUME_FLOOR_DERIVATION = {
  /** Inner edge of the inter-belt window, in Earth radii of equatorial L. */
  interBeltInnerL: 2.0,
  /** Outer edge of the inter-belt window. */
  interBeltOuterL: 3.6,
  /** L sampling step, both inside the window and across the full profile. */
  radialStepL: 0.02,
  /** MLT sampling step, in hours; 48 profiles around the clock. */
  magneticLocalTimeStepHours: 0.5,
  /** The floor is rounded DOWN to a multiple of this many decades. */
  quantumDecades: 0.05,
  /** Below this occupied fraction of the window, the field is not readable. */
  minimumOccupiedFraction: 0.5,
  /** ...and this many occupied samples are needed at all. */
  minimumOccupiedSamples: 24,
  /**
   * How much higher than the minimum the field must rise on BOTH sides for the
   * minimum to be an inter-belt minimum rather than the bottom of a slope.
   * 0.1 decade is a 26% rise; the four published channels clear it by between
   * 0.9 and 2.6 decades on real frames, so this only ever catches data with no
   * two-belt structure at all.
   */
  beltContrastDecades: 0.1,
} as const;

/** How a view's opacity floor was arrived at on the data that is loaded. */
export type RadiationVolumeFloorStatus =
  /** The rule ran and the view's own inter-belt minimum set the floor. */
  | "derived"
  /** The rule ran; the minimum was below 10^1, so the declared floor stands. */
  | "declared-floor"
  /** The rule could not run on this data; the shipped table was used. */
  | "fallback";

export interface RadiationVolumeFloorDerivation {
  floorLog10Flux: number;
  status: RadiationVolumeFloorStatus;
  /** Deepest inter-belt minimum found, or null when the rule could not run. */
  interBeltMinimumLog10Flux: number | null;
  interBeltMinimumL: number | null;
  interBeltMinimumMagneticLocalTimeHours: number | null;
  /** Highest flux inward and outward of that minimum, along the same MLT. */
  innerMaximumLog10Flux: number | null;
  outerMaximumLog10Flux: number | null;
  /**
   * Fraction of magnetic local times whose L 2 - 3.6 profile is hole-free, and
   * therefore readable. 1 on every real frame measured so far.
   */
  occupiedFraction: number;
  /** Set only when `status` is `fallback`; plain enough to print on the card. */
  fallbackReason: string | null;
}

/** Round down to the next whole 0.05 decade, without binary-fraction drift. */
function roundDownToQuantum(value: number, quantumDecades: number) {
  const steps = Math.floor(value / quantumDecades + 1e-9);
  return Math.round(steps * quantumDecades * 1000) / 1000;
}

/**
 * Derive this view's opacity floor from the field that was actually loaded.
 *
 * The rule, unchanged from the one the shipped table was set by: **the floor is
 * this view's own deepest inter-belt minimum — read off the baked volume's
 * equatorial profile at every MLT between L 2 and L 3.6 — rounded DOWN to the
 * next 0.05 decade, and never below the layer's long-declared 10^1 display
 * floor.** What changed on 2026-08-09 is that it now runs on every load
 * instead of having been run once by hand, so a dataset whose belts sit
 * somewhere else is drawn against its own slot.
 *
 * The floor can therefore only ever remove flux BELOW the bottom of the slot:
 * everything from the slot's own floor upward is drawn, and the dark band
 * between the belts is the model's, never the threshold's.
 *
 * Three kinds of data cannot be read this way, and all three take the shipped
 * fallback and SAY SO rather than inventing a floor:
 *
 * - an empty view, or one where fewer than half the magnetic local times carry
 *   a hole-free profile across the window (which is also how a NaN-heavy frame
 *   arrives here — non-finite flux never reaches the texture, it leaves the
 *   texel empty);
 * - a field with no identifiable two-belt structure, i.e. no interior minimum
 *   in L 2 - 3.6 with higher flux on both sides of it;
 * - a field whose derived floor would land at or above the colour ceiling, so
 *   that applying it would erase the view.
 */
export function deriveRadiationVolumeOpacityFloor(
  bake: RadiationVolumeBake,
  encoding: RadiationBeltDefinition["encoding"],
  sceneRadiusForRe: (radiusRe: number) => number,
  fallbackFloorLog10Flux: number,
): RadiationVolumeFloorDerivation {
  const declaredFloor = RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux;
  const settings = RADIATION_VOLUME_FLOOR_DERIVATION;
  const empty = {
    interBeltMinimumLog10Flux: null,
    interBeltMinimumL: null,
    interBeltMinimumMagneticLocalTimeHours: null,
    innerMaximumLog10Flux: null,
    outerMaximumLog10Flux: null,
  };
  const fallback = (
    fallbackReason: string,
    occupiedFraction: number,
    detail: Partial<RadiationVolumeFloorDerivation> = {},
  ): RadiationVolumeFloorDerivation => ({
    ...empty,
    floorLog10Flux: Math.max(declaredFloor, fallbackFloorLog10Flux),
    status: "fallback",
    occupiedFraction,
    fallbackReason,
    ...detail,
  });

  const span = encoding.maximum - encoding.minimum;
  if (!Number.isFinite(span) || span <= 0) {
    return fallback("this artifact publishes an empty flux encoding range, so no flux value can be read from it", 0);
  }
  if (
    !Number.isFinite(bake.sceneRadiusMinimum)
    || !Number.isFinite(bake.sceneRadiusMaximum)
    || bake.sceneRadiusMaximum <= bake.sceneRadiusMinimum
  ) {
    return fallback("this frame's baked volume has no radial extent to read a profile from", 0);
  }

  const innerL = Math.max(settings.interBeltInnerL, bake.trappingFloorRe);
  const outerL = Math.min(settings.interBeltOuterL, bake.equatorialRadiusMaximumRe);
  if (!(outerL > innerL)) {
    return fallback("this frame's grid does not reach across the L 2 to L 3.6 inter-belt window", 0);
  }

  // Which MLT columns of the texture carry a complete, hole-free profile across
  // the inter-belt window. A sample taken beside a hole is a blend of flux and
  // absence, and its low value is the interpolation's, not the model's — so the
  // scan below refuses to read a minimum out of one. This is measured on the
  // RAW texels, which is the only place absence is still distinguishable.
  const latitudeRows = bake.latitudeCount > 1 ? [0, 1] : [0];
  const columnComplete = new Uint8Array(bake.mltCount).fill(1);
  const radialSpan = bake.sceneRadiusMaximum - bake.sceneRadiusMinimum;
  // The texel window the inter-belt samples read from, with one texel of margin
  // on each side because that is how far a trilinear stencil reaches.
  const texelOf = (l: number) =>
    ((sceneRadiusForRe(l) - bake.sceneRadiusMinimum) / radialSpan) * bake.radialCount - 0.5;
  const firstRadial = Math.max(0, Math.floor(texelOf(innerL)) - 1);
  const lastRadial = Math.min(bake.radialCount - 1, Math.ceil(texelOf(outerL)) + 1);
  const bandTexelCount = Math.max(0, lastRadial - firstRadial + 1);
  for (let radial = firstRadial; radial <= lastRadial; radial += 1) {
    for (let mlt = 0; mlt < bake.mltCount; mlt += 1) {
      for (const latitude of latitudeRows) {
        if (bake.data[(latitude * bake.mltCount + mlt) * bake.radialCount + radial] === 0) {
          columnComplete[mlt] = 0;
        }
      }
    }
  }
  let completeColumns = 0;
  for (let mlt = 0; mlt < bake.mltCount; mlt += 1) completeColumns += columnComplete[mlt]!;
  const occupiedFraction = bake.mltCount > 0 && bandTexelCount > 0 ? completeColumns / bake.mltCount : 0;
  if (completeColumns === 0 || occupiedFraction < settings.minimumOccupiedFraction) {
    return fallback(
      completeColumns === 0
        ? "this frame draws no flux at all between L 2 and L 3.6, so it has no inter-belt minimum to read"
        : `only ${Math.round(occupiedFraction * 100)}% of this frame's L 2 to L 3.6 band carries flux at every `
          + "magnetic local time, which is too little of the field to read an inter-belt minimum from",
      occupiedFraction,
    );
  }

  // One equatorial profile per MLT, across the whole drawn radial range, so the
  // window minimum can be tested against what lies inward and outward of it.
  const profileL: number[] = [];
  for (
    let l = bake.trappingFloorRe;
    l <= bake.equatorialRadiusMaximumRe + 1e-9;
    l += settings.radialStepL
  ) {
    profileL.push(l);
  }
  const unoccupied = encoding.minimum + 1e-6;

  let minimumValue = Number.POSITIVE_INFINITY;
  let minimumL = 0;
  let minimumMlt = 0;
  let minimumProfileIndex = -1;
  let minimumProfile: number[] = [];
  let occupied = 0;
  let nonFinite = false;

  for (
    let mlt = 0;
    mlt < 24 - 1e-9;
    mlt += settings.magneticLocalTimeStepHours
  ) {
    // The trilinear stencil in MLT spans these two columns; both have to be
    // hole-free for the sample to be a reading of the field.
    const v = (((mlt / 24) % 1 + 1) % 1) * bake.mltCount - 0.5;
    const lower = ((Math.floor(v) % bake.mltCount) + bake.mltCount) % bake.mltCount;
    const upper = (lower + 1) % bake.mltCount;
    if (!columnComplete[lower] || !columnComplete[upper]) continue;
    const profile = profileL.map((l) =>
      sampleBakedVolume(bake, sceneRadiusForRe(l), mlt, 0) * span + encoding.minimum);
    for (let index = 0; index < profile.length; index += 1) {
      const l = profileL[index]!;
      if (l < innerL || l > outerL) continue;
      const value = profile[index]!;
      if (!Number.isFinite(value)) { nonFinite = true; continue; }
      if (value <= unoccupied) continue;
      occupied += 1;
      if (value < minimumValue) {
        minimumValue = value;
        minimumL = l;
        minimumMlt = mlt;
        minimumProfileIndex = index;
        minimumProfile = profile;
      }
    }
  }

  if (nonFinite) {
    return fallback(
      "this frame's flux field contains values that are not numbers, so its inter-belt minimum cannot be read",
      occupiedFraction,
    );
  }
  if (occupied < settings.minimumOccupiedSamples) {
    return fallback(
      "this frame draws too few flux samples between L 2 and L 3.6 to read an inter-belt minimum from",
      occupiedFraction,
    );
  }

  // Is this minimum INTERIOR — a slot between two belts — or just the bottom of
  // a slope running off the edge of the window? The field has to rise above it
  // on both sides, along the same MLT the minimum was found at.
  let innerMaximum = Number.NEGATIVE_INFINITY;
  let outerMaximum = Number.NEGATIVE_INFINITY;
  for (let index = 0; index < minimumProfile.length; index += 1) {
    const value = minimumProfile[index]!;
    if (value <= unoccupied) continue;
    if (index < minimumProfileIndex && value > innerMaximum) innerMaximum = value;
    if (index > minimumProfileIndex && value > outerMaximum) outerMaximum = value;
  }
  const structured = innerMaximum >= minimumValue + settings.beltContrastDecades
    && outerMaximum >= minimumValue + settings.beltContrastDecades;
  const found = {
    interBeltMinimumLog10Flux: minimumValue,
    interBeltMinimumL: minimumL,
    interBeltMinimumMagneticLocalTimeHours: minimumMlt,
    innerMaximumLog10Flux: Number.isFinite(innerMaximum) ? innerMaximum : null,
    outerMaximumLog10Flux: Number.isFinite(outerMaximum) ? outerMaximum : null,
  };
  if (!structured) {
    return fallback(
      "this frame shows no two-belt structure between L 2 and L 3.6 — the field does not rise on both sides "
      + "of its lowest point there — so there is no inter-belt minimum to set a floor by",
      occupiedFraction,
      found,
    );
  }

  const rounded = roundDownToQuantum(minimumValue, settings.quantumDecades);
  if (rounded >= RADIATION_VOLUME_TRANSFER.colourCeilingLog10Flux) {
    return fallback(
      `this frame's inter-belt minimum, 10^${minimumValue.toFixed(2)}, is at or above the top of the colour `
      + "scale, so drawing only above it would leave the view empty",
      occupiedFraction,
      found,
    );
  }

  return {
    ...found,
    floorLog10Flux: Math.max(declaredFloor, rounded),
    status: rounded <= declaredFloor ? "declared-floor" : "derived",
    occupiedFraction,
    fallbackReason: null,
  };
}

/**
 * Everything the shader and the readout need to know about one view's opacity,
 * with the floor derived from the data that is actually loaded.
 */
export interface RadiationVolumeOpacityResolution {
  energyKev: number;
  label: string;
  /** What the shader uses: the derived floor, or the disclosed fallback. */
  opacityFloorLog10Flux: number;
  extinctionPerSceneUnit: number;
  /** False when the extinction was measured for a neighbouring channel. */
  tuned: boolean;
  /** Where the floor on screen came from. */
  floorSource: "derived-from-loaded-data" | "shipped-fallback-table" | "explicit-override";
  derivation: RadiationVolumeFloorDerivation;
  /** One sentence, in the reader's units, for the card and the userData. */
  reason: string;
}

/**
 * Resolve one view's opacity against a real bake: extinction from the table,
 * floor from the data.
 *
 * The sentence this returns is the one the layer card prints after "DRAWN
 * ABOVE", so it always says which of the two happened. A fallback is never
 * silent.
 */
export function resolveRadiationVolumeOpacityForBake(
  energyKev: number,
  bake: RadiationVolumeBake,
  encoding: RadiationBeltDefinition["encoding"],
  sceneRadiusForRe: (radiusRe: number) => number,
): RadiationVolumeOpacityResolution {
  const setting = resolveRadiationVolumeOpacity(energyKev);
  const derivation = deriveRadiationVolumeOpacityFloor(
    bake,
    encoding,
    sceneRadiusForRe,
    setting.fallbackFloorLog10Flux,
  );
  const at = derivation.interBeltMinimumL !== null && derivation.interBeltMinimumMagneticLocalTimeHours !== null
    ? ` at L ${derivation.interBeltMinimumL.toFixed(2)}, MLT ${
      derivation.interBeltMinimumMagneticLocalTimeHours.toFixed(1)}`
    : "";
  const reason = derivation.status === "fallback"
    ? `FLOOR NOT DERIVED FROM THIS DATA: ${derivation.fallbackReason}. The shipped ${setting.label} floor of `
      + `10^${setting.fallbackFloorLog10Flux.toFixed(2)}, measured by the same rule on the 2026-08-08T23:40Z `
      + "frame, is being used instead"
    : derivation.status === "declared-floor"
      ? `derived from this frame's own field: its deepest inter-belt minimum, 10^${
        derivation.interBeltMinimumLog10Flux!.toFixed(2)}${at}, is already below the layer's declared `
        + `10^${RADIATION_VOLUME_TRANSFER.colourFloorLog10Flux} display floor, so nothing at all is hidden `
        + "to make the slot"
      : `derived from this frame's own field: its deepest inter-belt minimum is 10^${
        derivation.interBeltMinimumLog10Flux!.toFixed(2)}${at}, and the floor is that minimum rounded down to `
        + `the next ${RADIATION_VOLUME_FLOOR_DERIVATION.quantumDecades} decade, so the floor can only remove `
        + "the skirt BELOW the belt system and everything from the bottom of the slot upward is still drawn";
  return {
    energyKev,
    label: setting.label,
    opacityFloorLog10Flux: derivation.floorLog10Flux,
    extinctionPerSceneUnit: setting.extinctionPerSceneUnit,
    tuned: setting.tuned,
    floorSource: derivation.status === "fallback" ? "shipped-fallback-table" : "derived-from-loaded-data",
    derivation,
    reason: setting.tuned
      ? reason
      : `${reason}; extinction ${setting.extinctionPerSceneUnit} is inherited from the ${setting.label} channel, `
        + `because this build has no measured extinction for ${energyKev} keV`,
  };
}

/**
 * GSM -> SM as a rotation about the GSM y axis by the geodipole tilt.
 *
 * In GSM the dipole axis lies in the x-z plane at angle psi from z, so undoing
 * that tilt is a rotation of -psi about y. The result is Solar Magnetic
 * coordinates, which is the frame radiation belts are actually organised in:
 * z along the dipole, so magnetic latitude means what the bake assumed.
 *
 * Being a pure rotation matters for honesty as much as for geometry. It moves
 * where a sample is looked up and can never change what flux is stored there,
 * so the picture gains the right shape without the numbers being touched.
 */
export function smFromGsmMatrix(tiltRadians: number): THREE.Matrix3 {
  const cos = Math.cos(-tiltRadians);
  const sin = Math.sin(-tiltRadians);
  // Row-major, matching THREE.Matrix3.set.
  return new THREE.Matrix3().set(
    cos, 0, sin,
    0, 1, 0,
    -sin, 0, cos,
  );
}

/**
 * Point the belts at the dipole for this instant.
 *
 * `null` means the tilt could not be computed, and the caller must hide the
 * layer rather than fall back to an untilted belt — an untilted belt is not a
 * degraded picture, it is a differently wrong one, and 0 degrees of tilt is a
 * real and common value that must never double as the failure mode.
 */
/**
 * The shader's ruler arithmetic, mirrored exactly, so it can be tested.
 *
 * The GLSL above applies the eccentric offset in PHYSICAL space, which means it
 * has to convert drawn radius to Earth radii and back inside the raymarch. It
 * does that in closed form rather than with a lookup table, which is only
 * legitimate if the closed form really does agree with the site's one shared
 * ruler across the whole belt domain.
 *
 * These two functions are that arithmetic, character for character, exported
 * for `tests/radiation-volume-transfer.test.ts` to check against
 * `sharedDisplayRadius` and `radiusFromSharedDisplayRadius`. If the ruler is
 * ever reshaped — a different anchor, a taper that starts inside the belts —
 * the test fails here rather than the anomaly silently sliding across the map.
 */
export const SHADER_RULER_A = 18.202857142857143;
export const SHADER_RULER_ANCHOR_RE = 6.6170146;
/** Where the geostationary joint's slope ramp ends. `RADIAL_RULER.noseRampEndRe`. */
export const SHADER_RULER_RAMP_END_RE = 7.35;
/**
 * The log branch's own slope at the anchor, where the ramp starts. A literal
 * because GLSL constants cannot call functions; `tests/radial-ruler.test.ts`
 * and the ruler-agreement guards below are what prove it still matches
 * `sharedRulerLocalSlope` at the anchor.
 */
export const SHADER_RULER_ANCHOR_SLOPE = 0.1421227773;

function shaderLogBranchDrawn(radiusRe: number): number {
  return 1 + 0.28 * Math.log(1 + SHADER_RULER_A * Math.max(0, radiusRe - 1));
}

export function shaderDrawnFromRe(
  radiusRe: number,
  earthSceneRadius: number,
  trueDistance = false,
): number {
  if (trueDistance) return earthSceneRadius * Math.max(1, radiusRe);
  if (radiusRe <= SHADER_RULER_ANCHOR_RE) return earthSceneRadius * shaderLogBranchDrawn(radiusRe);
  const anchorDrawn = shaderLogBranchDrawn(SHADER_RULER_ANCHOR_RE);
  const rampLn = Math.log(SHADER_RULER_RAMP_END_RE / SHADER_RULER_ANCHOR_RE);
  const rise = 1 - SHADER_RULER_ANCHOR_SLOPE;
  if (radiusRe < SHADER_RULER_RAMP_END_RE) {
    const t = Math.log(radiusRe / SHADER_RULER_ANCHOR_RE) / rampLn;
    return earthSceneRadius * anchorDrawn
      * Math.exp(rampLn * (SHADER_RULER_ANCHOR_SLOPE * t + (rise * t * t) / 2));
  }
  const rampEndDrawn = anchorDrawn * Math.exp(rampLn * (SHADER_RULER_ANCHOR_SLOPE + rise / 2));
  return earthSceneRadius * rampEndDrawn * (radiusRe / SHADER_RULER_RAMP_END_RE);
}

export function shaderReFromDrawn(
  drawn: number,
  earthSceneRadius: number,
  trueDistance = false,
): number {
  const x = drawn / earthSceneRadius;
  if (trueDistance) return Math.max(1, x);
  const anchorDrawn = shaderLogBranchDrawn(SHADER_RULER_ANCHOR_RE);
  if (x <= anchorDrawn) return 1 + (Math.exp((x - 1) / 0.28) - 1) / SHADER_RULER_A;
  const rampLn = Math.log(SHADER_RULER_RAMP_END_RE / SHADER_RULER_ANCHOR_RE);
  const rise = 1 - SHADER_RULER_ANCHOR_SLOPE;
  const rampEndDrawn = anchorDrawn * Math.exp(rampLn * (SHADER_RULER_ANCHOR_SLOPE + rise / 2));
  if (x >= rampEndDrawn) return (SHADER_RULER_RAMP_END_RE * x) / rampEndDrawn;
  // Inside the ramp the drawn radius is exponential in a QUADRATIC, so the
  // inverse is the positive root rather than a search.
  const integral = Math.log(x / anchorDrawn) / rampLn;
  const t = (Math.sqrt(SHADER_RULER_ANCHOR_SLOPE * SHADER_RULER_ANCHOR_SLOPE + 2 * rise * integral)
    - SHADER_RULER_ANCHOR_SLOPE) / rise;
  return SHADER_RULER_ANCHOR_RE * Math.exp(rampLn * t);
}

export function setRadiationVolumeDipoleOffset(
  mesh: THREE.Mesh,
  offset: { x: number; y: number; z: number } | null,
): void {
  const material = mesh.material as THREE.ShaderMaterial;
  const uniform = material.uniforms?.dipoleOffsetSmRe;
  if (!uniform) return;
  // A null offset is a CENTRED dipole, which is the picture this correction
  // exists to replace, so the caller hides the layer instead. Zeroing here
  // would quietly restore the old, wrong geometry.
  (uniform.value as THREE.Vector3).set(offset?.x ?? 0, offset?.y ?? 0, offset?.z ?? 0);
}

export function setRadiationVolumeDipoleTilt(mesh: THREE.Mesh, tiltRadians: number): void {
  const material = mesh.material as THREE.ShaderMaterial;
  const uniform = material.uniforms?.smFromGsm;
  if (!uniform) return;
  (uniform.value as THREE.Matrix3).copy(smFromGsmMatrix(tiltRadians));
}

/**
 * The palette, as CSS hex, lowest flux first. Exported so the legend's colour
 * bar and the shader's lookup texture are generated from the same stops and
 * the two can never disagree about what a given flux looks like.
 *
 * Nine stops, not four, and the reason is measured rather than aesthetic. The
 * three things a reader is meant to tell apart sit at 10^2.62 (the slot),
 * 10^3.18 (the inner belt) and 10^3.65 (the outer belt), which is 36%, 48% and
 * 59% of the displayed range. The previous four stops ran dark navy, purple,
 * orange, cream — and purple to orange is one straight interpolation between
 * two nearly opposite hues, so it passes close to grey. Chroma along that ramp
 * went 70.8 at 30%, 21.2 at 50%, 60.1 at 65%: the inner belt landed in the
 * trough and rendered #976980, a washed mauve, the dullest colour in the
 * picture, with a vivid slot on one side and a vivid outer belt on the other.
 * The feature that matters most was drawn the faintest.
 *
 * Interpolating the SAME four stops perceptually does not fix it — in Oklab
 * the trough gets worse, 16.7, because that chord passes nearer neutral still.
 * What fixes it is routing the leg through magenta, which holds the trough at
 * 51.7 while the closest pair of features stays dE 30 apart (10 already reads
 * as a different colour).
 *
 * Both endpoints are unchanged, so everything written elsewhere about the ramp
 * running #181436 to #fff0cf across 10^1 to 10^5.5 is still true, and lightness
 * still rises monotonically, L* 8.7 to 95.2 — a sequential ramp that dips in
 * lightness draws a boundary the data does not contain.
 */
export const RADIATION_VOLUME_COLOR_HEX = [
  "#181436", "#3a2a8f", "#5b47c4", "#8f45b8", "#c04a94",
  "#dd5f5c", "#e0932f", "#f0c375", "#fff0cf",
] as const;

/**
 * One hue per belt, because "which belt am I looking at?" is the first question
 * and the flux ramp could not answer it.
 *
 * The belts are not distinguished by how bright they are — they overlap in
 * flux — but by WHERE they are, and a single ramp keyed on flux therefore drew
 * both of them in the same colours and left a reader to infer the boundary from
 * a dark gap. Sean asked for "one belt sort of more blue and the other more
 * red", which is exactly the right instinct: hue should carry belt identity.
 *
 * So hue is position and lightness is flux. That is honest as long as the
 * legend says it, because neither fact is being invented — L shell is
 * geometry, computed about the eccentric dipole like everything else here, and
 * the flux is still the measurement it always was. What a reader must never be
 * able to do is read a COLOUR as a number, and they cannot: the number is the
 * brightness, and it runs the same way on both ramps.
 *
 * Both ramps rise monotonically in lightness across the same range, so a given
 * flux is the same lightness in either belt and the two can be compared by eye.
 */
export const RADIATION_INNER_COLOR_HEX = [
  "#1a0a12", "#4a0f22", "#84172c", "#b52d2c", "#dc5a2c",
  "#f0913f", "#ffc877", "#fff0d0", "#fffaf0",
] as const;

export const RADIATION_OUTER_COLOR_HEX = [
  "#08111f", "#0f2a4a", "#164a78", "#1d70a4", "#2b9cc4",
  "#5ac4d8", "#a0e2ea", "#daf5fa", "#f2fdff",
] as const;

/**
 * Where one belt stops reading as the other, in L — the equatorial radius of
 * the field line a sample sits on, not the sample's own distance from centre.
 *
 * The slot between the belts sits near L 2-3 and moves with activity, so this
 * is a blend and not a line: nothing on screen should look like a wall at a
 * radius the physics does not put a wall at. Inside L 2.2 the hue is fully the
 * inner belt's, outside L 3.6 fully the outer's, and the slot carries the
 * crossfade — which is also where the flux is lowest and least visible.
 *
 * CORRECTNESS FIX 2026-09-08. These two numbers are named in L and were being
 * compared against `dipoleRe`, the sample's LOCAL radius. The two agree only on
 * the magnetic equator: off it, r = L cos^2(latitude), so a point on the L 3.6
 * shell falls below the 2.2 threshold at 38.6 degrees of magnetic latitude and
 * below 1.5 Re by 50 degrees. The bake reaches about 65 degrees, so the outer
 * belt's high-latitude horns — the part of it that mirrors down toward the
 * atmosphere, which is the part a reader is being shown when they are told the
 * belt is not a torus — were painted in the inner belt's warm hue all the way
 * along. The bake's own loop does this conversion two lines from where it
 * writes the texel (`shellRadiusRe = positionRadiusRe / cosineSquared`); the
 * shader simply was not doing it.
 */
export const RADIATION_BELT_HUE_SPLIT = { innerL: 2.2, outerL: 3.6 } as const;

/**
 * Texels in the shader's colour lookup: 32 per segment plus the closing one, so
 * however many stops the palette carries, each lands on a texel of its own with
 * no rounding. That is what lets a test assert the shader's lookup holds the
 * declared colours exactly instead of within some tolerance nobody can justify.
 */
export const RADIATION_VOLUME_RAMP_TEXELS = (RADIATION_VOLUME_COLOR_HEX.length - 1) * 32 + 1;

function hexBytes(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ];
}

/**
 * The stops sampled into RGBA bytes, evenly spaced across the displayed range,
 * exactly as the legend's CSS gradient interpolates them. Pure and exported so
 * a test can read the colour of a given flux without a GL context.
 *
 * A hardware lookup samples texel `u * width - 0.5`, so a colour can be up to
 * half a texel from where these bytes place it — 0.2% of the ramp, about 0.005
 * decades of flux. That is far below anything a reader can see, and it is the
 * price of the shader not caring how many stops there are.
 */
export function radiationRampTexels(
  stops: readonly string[] = RADIATION_VOLUME_COLOR_HEX,
  width = RADIATION_VOLUME_RAMP_TEXELS,
): Uint8Array {
  const data = new Uint8Array(width * 4);
  const segments = stops.length - 1;
  for (let index = 0; index < width; index += 1) {
    const position = width === 1 ? 0 : index / (width - 1);
    const scaled = THREE.MathUtils.clamp(position, 0, 1) * segments;
    const segment = Math.min(Math.floor(scaled), segments - 1);
    const fraction = scaled - segment;
    const low = hexBytes(stops[segment]!);
    const high = hexBytes(stops[segment + 1]!);
    for (let channel = 0; channel < 3; channel += 1) {
      data[index * 4 + channel] = Math.round(low[channel]! + (high[channel]! - low[channel]!) * fraction);
    }
    data[index * 4 + 3] = 255;
  }
  return data;
}

let sharedRampTexture: THREE.DataTexture | null = null;

/**
 * One texture for every energy view. Shared rather than per-mesh so that "the
 * same colour means the same flux at 88 keV as at 2.32 MeV" is structural and
 * cannot drift, and declared sRGB so the shader receives the same linear values
 * a THREE.Color built from these hexes used to supply.
 */
function radiationRampTexture(): THREE.DataTexture {
  if (sharedRampTexture === null) {
    // Two rows: v=0 is the inner belt, v=1 the outer. LinearFilter across v is
    // what makes the slot a crossfade rather than a seam, and it costs one
    // texture rather than two samplers and a mix in the inner loop.
    const inner = radiationRampTexels(RADIATION_INNER_COLOR_HEX);
    const outer = radiationRampTexels(RADIATION_OUTER_COLOR_HEX);
    const both = new Uint8Array(inner.length + outer.length);
    both.set(inner, 0);
    both.set(outer, inner.length);
    sharedRampTexture = new THREE.DataTexture(
      both,
      RADIATION_VOLUME_RAMP_TEXELS,
      2,
      THREE.RGBAFormat,
    );
    sharedRampTexture.colorSpace = THREE.SRGBColorSpace;
    sharedRampTexture.minFilter = THREE.LinearFilter;
    sharedRampTexture.magFilter = THREE.LinearFilter;
    sharedRampTexture.wrapS = THREE.ClampToEdgeWrapping;
    sharedRampTexture.wrapT = THREE.ClampToEdgeWrapping;
    sharedRampTexture.needsUpdate = true;
  }
  return sharedRampTexture;
}

/**
 * The legend gradient, from the shader's own stops — now two bars, because the
 * shader draws two ramps and a single bar would misdescribe the picture.
 *
 * Inner belt above, outer below, each running the same flux range left to
 * right. A reader can therefore check both things the colours encode: which
 * belt a hue belongs to, and what a brightness is worth. Written as a full
 * background shorthand because the stylesheet assigns it to `background`.
 */
export const RADIATION_VOLUME_GRADIENT_CSS =
  `linear-gradient(90deg, ${RADIATION_INNER_COLOR_HEX.join(", ")}) 0 0 / 100% 50% no-repeat, `
  + `linear-gradient(90deg, ${RADIATION_OUTER_COLOR_HEX.join(", ")}) 0 100% / 100% 50% no-repeat`;

export interface RadiationVolumeBakeOptions {
  /** Radial texels, uniform in scene radius (the display ruler's own spacing). */
  radialCount?: number;
  /** MLT texels around the full 24 hours. */
  mltCount?: number;
  /** Latitude texels from the equator to the widest trapped latitude. */
  latitudeCount?: number;
  displayWindow?: Partial<RadiationBeltDisplayWindow>;
}

export interface RadiationVolumeBake {
  /** Normalized log10 omnidirectional flux, R8, radial-major, then MLT, then latitude. */
  data: Uint8Array<ArrayBuffer>;
  radialCount: number;
  mltCount: number;
  latitudeCount: number;
  sceneRadiusMinimum: number;
  sceneRadiusMaximum: number;
  latitudeMaximumRadians: number;
  trappingFloorRe: number;
  equatorialRadiusMaximumRe: number;
  /** Channels integrated on the widest shell; the legend's channel count. */
  integratedPitchChannelCount: number;
  displayWindow: RadiationBeltDisplayWindow;
}

interface EquatorialChannelTable {
  values: Float32Array;
  radialCount: number;
  mltCount: number;
  pitchCount: number;
}

/**
 * Resample the native curvilinear equatorial grid onto a regular
 * (scene radius, MLT) table, one normalized log10 flux per pitch channel.
 *
 * The native grid is mapped: each column's equatorial radius and MLT are the
 * model's own field-line-mapped coordinates, and at large radius the columns
 * warp in both. Each column is interpolated along its own radii first, then
 * the columns are interpolated around the circle at their own interpolated
 * MLT, which is bilinear interpolation along the grid's own axes — the same
 * interpolation the triangulated native surface has always drawn, sampled
 * onto a regular table instead of a mesh. Interpolation happens in the
 * normalized (log10) attribute, matching how the GPU interpolated the same
 * quantity across the native triangles.
 */
function buildEquatorialChannelTable(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  energyKev: number,
  radiusReForSceneRadius: (sceneRadius: number) => number,
  sceneRadiusMinimum: number,
  sceneRadiusMaximum: number,
  radialCount: number,
  mltCount: number,
): EquatorialChannelTable {
  const coordinates = decodeRadiationBeltCoordinates(definition, frame);
  const shape = resolveRadiationGridShape(definition, coordinates);
  const pitchCount = definition.pitchCoordinatesSin.length;
  const encodedEntry = Object.entries(frame.pitchResolvedElectronFluxU16)
    .find(([key]) => Math.abs(Number(key) - energyKev) < 1e-3);
  if (!encodedEntry) throw new RangeError(`RBE energy ${energyKev} keV is unavailable`);
  const flux = decodeRadiationFlux(encodedEntry[1], definition.count * pitchCount);

  const values = new Float32Array(radialCount * mltCount * pitchCount);
  const columnMlt = new Float64Array(shape.magneticLocalTimeCount);
  const columnFlux = new Float64Array(shape.magneticLocalTimeCount * pitchCount);
  const columnPresent = new Uint8Array(shape.magneticLocalTimeCount);

  for (let radialIndex = 0; radialIndex < radialCount; radialIndex += 1) {
    const sceneRadius = sceneRadiusMinimum
      + ((radialIndex + 0.5) / radialCount) * (sceneRadiusMaximum - sceneRadiusMinimum);
    const radiusRe = radiusReForSceneRadius(sceneRadius);

    // Interpolate every native column along its own (monotonic) radii.
    for (let column = 0; column < shape.magneticLocalTimeCount; column += 1) {
      columnPresent[column] = 0;
      let lower = -1;
      for (let row = 0; row < shape.radialCount - 1; row += 1) {
        const inner = coordinates.equatorialRadiusRe[row * shape.magneticLocalTimeCount + column]!;
        const outer = coordinates.equatorialRadiusRe[(row + 1) * shape.magneticLocalTimeCount + column]!;
        if (radiusRe >= inner && radiusRe <= outer && outer > inner) {
          lower = row;
          break;
        }
      }
      if (lower < 0) continue;
      const innerPoint = lower * shape.magneticLocalTimeCount + column;
      const outerPoint = (lower + 1) * shape.magneticLocalTimeCount + column;
      const innerRadius = coordinates.equatorialRadiusRe[innerPoint]!;
      const outerRadius = coordinates.equatorialRadiusRe[outerPoint]!;
      const fraction = (radiusRe - innerRadius) / (outerRadius - innerRadius);
      const innerMlt = coordinates.equatorialMagneticLocalTimeHours[innerPoint]!;
      const outerMlt = coordinates.equatorialMagneticLocalTimeHours[outerPoint]!;
      let mltStep = outerMlt - innerMlt;
      if (mltStep > 12) mltStep -= 24;
      if (mltStep < -12) mltStep += 24;
      columnMlt[column] = (innerMlt + fraction * mltStep + 24) % 24;
      for (let channel = 0; channel < pitchCount; channel += 1) {
        columnFlux[column * pitchCount + channel] = THREE.MathUtils.lerp(
          flux[innerPoint * pitchCount + channel]!,
          flux[outerPoint * pitchCount + channel]!,
          fraction,
        );
      }
      columnPresent[column] = 1;
    }

    // Interpolate around the circle at the columns' own MLT positions.
    const present: number[] = [];
    for (let column = 0; column < shape.magneticLocalTimeCount; column += 1) {
      if (columnPresent[column]) present.push(column);
    }
    if (present.length === 0) continue;
    const ordered = [...present].sort((a, b) => columnMlt[a]! - columnMlt[b]!);
    for (let mltIndex = 0; mltIndex < mltCount; mltIndex += 1) {
      const targetMlt = ((mltIndex + 0.5) / mltCount) * 24;
      let after = ordered.findIndex((column) => columnMlt[column]! >= targetMlt);
      let beforeColumn: number;
      let afterColumn: number;
      if (after < 0) {
        beforeColumn = ordered[ordered.length - 1]!;
        afterColumn = ordered[0]!;
      } else {
        afterColumn = ordered[after]!;
        beforeColumn = ordered[(after - 1 + ordered.length) % ordered.length]!;
      }
      let gap = columnMlt[afterColumn]! - columnMlt[beforeColumn]!;
      if (gap <= 0) gap += 24;
      let offset = targetMlt - columnMlt[beforeColumn]!;
      if (offset < 0) offset += 24;
      const fraction = gap > 1e-9 ? THREE.MathUtils.clamp(offset / gap, 0, 1) : 0;
      const base = (radialIndex * mltCount + mltIndex) * pitchCount;
      for (let channel = 0; channel < pitchCount; channel += 1) {
        values[base + channel] = THREE.MathUtils.lerp(
          columnFlux[beforeColumn * pitchCount + channel]!,
          columnFlux[afterColumn * pitchCount + channel]!,
          fraction,
        );
      }
    }
  }
  return { values, radialCount, mltCount, pitchCount };
}

/**
 * Bake the omnidirectional flux field into a position-indexed 3-D texture.
 *
 * Texture axes are the position's scene radius (uniform in the display
 * ruler's own compressed spacing, so texels are spent where the ruler spends
 * screen space), MLT, and absolute magnetic latitude. The shader samples it
 * with three dot products and one length; every physical decision — which
 * channels are trapped at the field line's radius, which have mirrored below
 * the sample's latitude, and each bin's local solid angle — is made here on
 * the CPU with the same shared quadrature the shell presentations use.
 */
export function bakeOmnidirectionalFluxVolume(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  energyKev: number,
  mapperFrame: RadiationMapperFrame,
  options: RadiationVolumeBakeOptions = {},
): RadiationVolumeBake {
  const pitchCount = definition.pitchCoordinatesSin.length;
  if (pitchCount === 0) throw new RangeError("RBE pitch grid is empty");
  const displayWindow = resolveRadiationBeltDisplayWindow(options.displayWindow);
  const trappingFloorRe = Math.max(definition.innerBoundaryRe, displayWindow.minimumMappedRadiusRe);
  const coordinates = decodeRadiationBeltCoordinates(definition, frame);
  let equatorialRadiusMaximumRe = 0;
  for (let index = 0; index < coordinates.equatorialRadiusRe.length; index += 1) {
    const radius = coordinates.equatorialRadiusRe[index]!;
    if (radius > equatorialRadiusMaximumRe) equatorialRadiusMaximumRe = radius;
  }
  if (equatorialRadiusMaximumRe <= trappingFloorRe) {
    throw new RangeError("RBE grid does not reach past the trapping floor");
  }

  const radialCount = Math.max(16, Math.floor(options.radialCount ?? 192));
  const mltCount = Math.max(8, Math.floor(options.mltCount ?? 64));
  const latitudeCount = Math.max(8, Math.floor(options.latitudeCount ?? 88));

  const sceneRadiusMinimum = mapperFrame.sceneRadiusForRe(trappingFloorRe);
  const sceneRadiusMaximum = mapperFrame.sceneRadiusForRe(equatorialRadiusMaximumRe);
  const latitudeMaximumRadians = trappingFootpointLatitudeRadians(
    equatorialRadiusMaximumRe,
    trappingFloorRe,
  );

  const table = buildEquatorialChannelTable(
    definition,
    frame,
    energyKev,
    mapperFrame.radiusReForSceneRadius,
    sceneRadiusMinimum,
    sceneRadiusMaximum,
    Math.max(radialCount, 256),
    Math.max(mltCount, 96),
  );

  const encoding = definition.encoding;
  const span = encoding.maximum - encoding.minimum;
  if (!Number.isFinite(span) || span <= 0) throw new RangeError("RBE flux encoding range is empty");

  const mirrorLatitudes = definition.pitchCoordinatesSin.map((sine) => dipoleMirrorLatitudeRadians(sine));
  const edgeAngles = gyrotropicPitchBinEdgeAngles(definition.pitchCoordinatesSin);
  const edgeCosines = new Float64Array(edgeAngles.length);
  const channelWeights = new Float64Array(pitchCount);

  const data = new Uint8Array(radialCount * mltCount * latitudeCount);
  let integratedPitchChannelCount = 0;

  const sceneSpan = sceneRadiusMaximum - sceneRadiusMinimum;
  const tableRadialScale = table.radialCount;
  const tableMltScale = table.mltCount;

  for (let latitudeIndex = 0; latitudeIndex < latitudeCount; latitudeIndex += 1) {
    const latitude = ((latitudeIndex + 0.5) / latitudeCount) * latitudeMaximumRadians;
    const cosineSquared = Math.cos(latitude) ** 2;
    const fieldRatio = dipoleFieldRatio(latitude);
    for (let edge = 0; edge < edgeAngles.length; edge += 1) {
      edgeCosines[edge] = localPitchCosine(edgeAngles[edge]!, fieldRatio);
    }
    for (let radialIndex = 0; radialIndex < radialCount; radialIndex += 1) {
      const sceneRadius = sceneRadiusMinimum + ((radialIndex + 0.5) / radialCount) * sceneSpan;
      const positionRadiusRe = mapperFrame.radiusReForSceneRadius(sceneRadius);
      if (positionRadiusRe < trappingFloorRe) continue;
      const shellRadiusRe = positionRadiusRe / cosineSquared;
      if (shellRadiusRe > equatorialRadiusMaximumRe) continue;
      const footpoint = trappingFootpointLatitudeRadians(shellRadiusRe, trappingFloorRe);
      let trappedCount = 0;
      for (let channel = 0; channel < pitchCount; channel += 1) {
        const trapped = mirrorLatitudes[channel]! < footpoint;
        const weight = trapped ? edgeCosines[channel]! - edgeCosines[channel + 1]! : 0;
        channelWeights[channel] = weight > 0 ? weight : 0;
        if (trapped) trappedCount += 1;
      }
      if (trappedCount === 0) continue;
      if (trappedCount > integratedPitchChannelCount) integratedPitchChannelCount = trappedCount;

      // Fractional position of the field line's equatorial radius on the table.
      const shellSceneRadius = mapperFrame.sceneRadiusForRe(shellRadiusRe);
      const tableRow = THREE.MathUtils.clamp(
        ((shellSceneRadius - sceneRadiusMinimum) / sceneSpan) * tableRadialScale - 0.5,
        0,
        tableRadialScale - 1,
      );
      const rowBelow = Math.floor(tableRow);
      const rowAbove = Math.min(rowBelow + 1, tableRadialScale - 1);
      const rowFraction = tableRow - rowBelow;

      for (let mltIndex = 0; mltIndex < mltCount; mltIndex += 1) {
        const tableMlt = ((mltIndex + 0.5) / mltCount) * tableMltScale - 0.5;
        const mltBelow = ((Math.floor(tableMlt) % tableMltScale) + tableMltScale) % tableMltScale;
        const mltAbove = (mltBelow + 1) % tableMltScale;
        const mltFraction = tableMlt - Math.floor(tableMlt);
        let integral = 0;
        for (let channel = 0; channel < pitchCount; channel += 1) {
          const weight = channelWeights[channel]!;
          if (weight <= 0) continue;
          const v00 = table.values[(rowBelow * tableMltScale + mltBelow) * pitchCount + channel]!;
          const v01 = table.values[(rowBelow * tableMltScale + mltAbove) * pitchCount + channel]!;
          const v10 = table.values[(rowAbove * tableMltScale + mltBelow) * pitchCount + channel]!;
          const v11 = table.values[(rowAbove * tableMltScale + mltAbove) * pitchCount + channel]!;
          const normalized = THREE.MathUtils.lerp(
            THREE.MathUtils.lerp(v00, v01, mltFraction),
            THREE.MathUtils.lerp(v10, v11, mltFraction),
            rowFraction,
          );
          integral += weight * 10 ** (encoding.minimum + normalized * span);
        }
        if (integral <= 0) continue;
        const normalizedIntegral = THREE.MathUtils.clamp(
          (Math.log10(integral) - encoding.minimum) / span,
          0,
          1,
        );
        data[(latitudeIndex * mltCount + mltIndex) * radialCount + radialIndex] = Math.round(normalizedIntegral * 255);
      }
    }
  }

  return {
    data,
    radialCount,
    mltCount,
    latitudeCount,
    sceneRadiusMinimum,
    sceneRadiusMaximum,
    latitudeMaximumRadians,
    trappingFloorRe,
    equatorialRadiusMaximumRe,
    integratedPitchChannelCount,
    displayWindow,
  };
}

/** CPU trilinear sample of a bake, mirroring the shader's lookup, for tests and diagnostics. */
export function sampleBakedVolume(
  bake: RadiationVolumeBake,
  sceneRadius: number,
  magneticLocalTimeHours: number,
  latitudeRadians: number,
) {
  const u = ((sceneRadius - bake.sceneRadiusMinimum)
    / (bake.sceneRadiusMaximum - bake.sceneRadiusMinimum)) * bake.radialCount - 0.5;
  const v = (((magneticLocalTimeHours / 24) % 1 + 1) % 1) * bake.mltCount - 0.5;
  const w = (Math.abs(latitudeRadians) / bake.latitudeMaximumRadians) * bake.latitudeCount - 0.5;
  if (u < -0.5 || u > bake.radialCount - 0.5) return 0;
  if (w < -0.5 || w > bake.latitudeCount - 0.5) return 0;
  const read = (radial: number, mlt: number, latitude: number) => {
    const clampedRadial = THREE.MathUtils.clamp(radial, 0, bake.radialCount - 1);
    const clampedLatitude = THREE.MathUtils.clamp(latitude, 0, bake.latitudeCount - 1);
    const wrappedMlt = ((mlt % bake.mltCount) + bake.mltCount) % bake.mltCount;
    return bake.data[(clampedLatitude * bake.mltCount + wrappedMlt) * bake.radialCount + clampedRadial]! / 255;
  };
  const u0 = Math.floor(u);
  const v0 = Math.floor(v);
  const w0 = Math.floor(w);
  const uf = u - u0;
  const vf = v - v0;
  const wf = w - w0;
  let value = 0;
  for (let du = 0; du <= 1; du += 1) {
    for (let dv = 0; dv <= 1; dv += 1) {
      for (let dw = 0; dw <= 1; dw += 1) {
        const weight = (du ? uf : 1 - uf) * (dv ? vf : 1 - vf) * (dw ? wf : 1 - wf);
        if (weight > 0) value += weight * read(u0 + du, v0 + dv, w0 + dw);
      }
    }
  }
  return value;
}

const VOLUME_VERTEX_SHADER = `
  varying vec3 vLocalPosition;
  void main() {
    vLocalPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const VOLUME_FRAGMENT_SHADER = `
  precision highp float;
  precision highp sampler3D;
  uniform sampler3D fluxVolume;
  uniform vec3 cameraLocalPosition;
  uniform mat3 gsmFromLocal;
  // GSM -> SM. GSM's z axis is NOT the dipole axis: the dipole lies in the GSM
  // x-z plane, tilted from z by the geodipole tilt, which swings through about
  // +-34 degrees over a day and a year. Belts are organised by the DIPOLE, so
  // sampling them in GSM mislabels magnetic latitude by that whole angle. This
  // rotation is the difference, and it is a rotation, so it moves the geometry
  // and cannot alter a flux.
  uniform mat3 smFromGsm;
  // The eccentric-dipole offset, in SM, in Earth radii. The dipole is not at
  // Earth's centre: it sits about 610 km toward the western Pacific, so the
  // belts are centred there too and come closest to the surface on the far
  // side — over the South Atlantic. Fixed in geographic space, so in this
  // Sun-and-dipole frame it sweeps round once a day.
  uniform vec3 dipoleOffsetSmRe;
  // 1 when the visitor has chosen true distance, 0 for the teaching scale.
  uniform float rulerTrueDistance;
  uniform float sceneRadiusMinimum;
  uniform float sceneRadiusMaximum;
  uniform float latitudeMaximum;
  uniform float earthSceneRadius;
  uniform float colourFloor;
  uniform float colourSpan;
  uniform float opacityFloor;
  uniform float opacitySpan;
  uniform float opacityCurveExponent;
  uniform float extinction;
  uniform float minimumTransmittance;
  uniform sampler2D colourRamp;
  uniform float beltHueInnerL;
  uniform float beltHueOuterL;
  varying vec3 vLocalPosition;

  const int MAX_STEPS = 160;
  const float RULER_A = 18.202857142857143;      // km per Earth radius / 350
  const float RULER_ANCHOR_RE = 6.6170146;       // 1 + 35786 / 6371, geostationary
  const float RULER_RAMP_END_RE = 7.35;          // where the GEO joint's slope reaches 1
  const float RULER_ANCHOR_SLOPE = 0.1421227773; // the log branch's slope at the anchor
  const float TWO_PI = 6.28318530717958647692;

  // The shared radial ruler, and its inverse.
  //
  // The offset has to be applied in PHYSICAL space, never in scene units. The
  // teaching ruler is steeply nonlinear exactly where the anomaly matters: near
  // the surface 0.1 Earth radii of altitude is drawn as 0.29 drawn Earth radii,
  // so a rigid scene-space shift would misplace the anomaly by tens of percent.
  //
  // No lookup table is needed, because the ruler is still closed-form
  // invertible across the whole belt domain. Below the geostationary anchor it
  // is the logarithmic branch. From the anchor to 7.35 Earth radii the log-log
  // slope ramps LINEARLY from the log branch's value to 1 — the joint that used
  // to be a step, and that used to draw a hard corner into every curve crossing
  // geostationary radius — which makes the drawn radius exponential in a
  // QUADRATIC, so its inverse is a square root and not a search. Above
  // 7.35 Earth radii the slope is exactly 1 until the tail taper begins at 13,
  // far outside any belt, so that stretch is simply linear in radius.
  float logBranchDrawn(float r) {
    return 1.0 + 0.28 * log(1.0 + RULER_A * max(0.0, r - 1.0));
  }

  float drawnFromRe(float r) {
    if (rulerTrueDistance > 0.5) return earthSceneRadius * max(1.0, r);
    if (r <= RULER_ANCHOR_RE) return earthSceneRadius * logBranchDrawn(r);
    float anchorDrawn = logBranchDrawn(RULER_ANCHOR_RE);
    float rampLn = log(RULER_RAMP_END_RE / RULER_ANCHOR_RE);
    float rise = 1.0 - RULER_ANCHOR_SLOPE;
    if (r < RULER_RAMP_END_RE) {
      float t = log(r / RULER_ANCHOR_RE) / rampLn;
      return earthSceneRadius * anchorDrawn
        * exp(rampLn * (RULER_ANCHOR_SLOPE * t + rise * t * t * 0.5));
    }
    float rampEndDrawn = anchorDrawn * exp(rampLn * (RULER_ANCHOR_SLOPE + rise * 0.5));
    return earthSceneRadius * rampEndDrawn * (r / RULER_RAMP_END_RE);
  }

  float reFromDrawn(float drawn) {
    float x = drawn / earthSceneRadius;
    if (rulerTrueDistance > 0.5) return max(1.0, x);
    float anchorDrawn = logBranchDrawn(RULER_ANCHOR_RE);
    if (x <= anchorDrawn) return 1.0 + (exp((x - 1.0) / 0.28) - 1.0) / RULER_A;
    float rampLn = log(RULER_RAMP_END_RE / RULER_ANCHOR_RE);
    float rise = 1.0 - RULER_ANCHOR_SLOPE;
    float rampEndDrawn = anchorDrawn * exp(rampLn * (RULER_ANCHOR_SLOPE + rise * 0.5));
    if (x >= rampEndDrawn) return RULER_RAMP_END_RE * x / rampEndDrawn;
    float integral = log(x / anchorDrawn) / rampLn;
    float t = (sqrt(RULER_ANCHOR_SLOPE * RULER_ANCHOR_SLOPE + 2.0 * rise * integral)
      - RULER_ANCHOR_SLOPE) / rise;
    return RULER_ANCHOR_RE * exp(rampLn * t);
  }

  // Entry/exit distances of a ray against an origin-centered sphere.
  vec2 sphereIntersect(vec3 origin, vec3 direction, float radius) {
    float b = dot(origin, direction);
    float c = dot(origin, origin) - radius * radius;
    float disc = b * b - c;
    if (disc < 0.0) return vec2(1.0, -1.0);
    float root = sqrt(disc);
    return vec2(-b - root, -b + root);
  }

  // One fetch into the palette, evenly spaced across the DISPLAYED flux range,
  // so a decade of real flux is a visible change of hue and the slot, the inner
  // belt and the outer belt can be told apart without moving the camera. The
  // ramp lives in a texture rather than in stop uniforms so that how many stops
  // it takes to avoid a washed-out middle is a palette question, not a shader
  // one — see RADIATION_VOLUME_COLOR_HEX for what was measured.
  // u is the flux, v is which belt. The ramp texture is two rows and the
  // hardware blends between them, so the slot crossfades instead of seaming.
  vec3 fluxColor(float displayed, float belt) {
    return texture(colourRamp, vec2(clamp(displayed, 0.0, 1.0), clamp(belt, 0.0, 1.0))).rgb;
  }

  float hash(vec2 seed) {
    return fract(sin(dot(seed, vec2(12.9898, 78.233))) * 43758.5453);
  }

  void main() {
    vec3 direction = normalize(vLocalPosition - cameraLocalPosition);
    vec2 outer = sphereIntersect(cameraLocalPosition, direction, sceneRadiusMaximum);
    if (outer.x > outer.y) discard;
    float tNear = max(outer.x, 0.0);
    float tFar = outer.y;
    // Rays that meet the Earth stop at its surface; the globe is opaque.
    vec2 earth = sphereIntersect(cameraLocalPosition, direction, earthSceneRadius);
    if (earth.x <= earth.y && earth.y > 0.0 && earth.x < tFar) {
      tFar = max(earth.x, tNear);
    }
    if (tFar - tNear < 1e-4) discard;

    float span = tFar - tNear;
    float stepLength = span / float(MAX_STEPS);
    float t = tNear + stepLength * hash(gl_FragCoord.xy);
    float transmittance = 1.0;
    vec3 accumulated = vec3(0.0);
    float radialSpan = sceneRadiusMaximum - sceneRadiusMinimum;

    for (int step = 0; step < MAX_STEPS; step += 1) {
      if (t >= tFar) break;
      vec3 samplePosition = cameraLocalPosition + direction * t;
      float sceneRadius = length(samplePosition);
      if (sceneRadius >= sceneRadiusMinimum && sceneRadius <= sceneRadiusMaximum) {
        vec3 sm = smFromGsm * (gsmFromLocal * samplePosition);
        // Into physical space, shift to the dipole's true centre, and read the
        // belt coordinates from THERE. This is the whole of the eccentricity:
        // the flux table is untouched, the place it is read from moves.
        vec3 physical = normalize(sm) * reFromDrawn(sceneRadius);
        vec3 aboutDipole = physical - dipoleOffsetSmRe;
        float dipoleRe = length(aboutDipole);
        float latitude = abs(asin(clamp(aboutDipole.z / dipoleRe, -1.0, 1.0)));
        if (latitude < latitudeMaximum) {
          float u = (drawnFromRe(dipoleRe) - sceneRadiusMinimum) / radialSpan;
          float v = atan(aboutDipole.y, aboutDipole.x) / TWO_PI + 0.5;
          float w = latitude / latitudeMaximum;
          float value = texture(fluxVolume, vec3(u, v, w)).r;
          // Two coordinates, on purpose. Colour rides one range that never
          // changes between energy views, so the same flux is always the same
          // colour. Opacity rides this view's own range, so each energy can be
          // made legible without ever repainting what a number means.
          float colourCoordinate = clamp((value - colourFloor) / colourSpan, 0.0, 1.0);
          float opacityCoordinate = clamp((value - opacityFloor) / opacitySpan, 0.0, 1.0);
          if (opacityCoordinate > 0.0) {
            float sigma = extinction * pow(opacityCoordinate, opacityCurveExponent);
            float sampleAlpha = 1.0 - exp(-sigma * stepLength);
            // L, not r: the thresholds are shell labels. r = L cos^2(lat), so
            // the same conversion the bake uses to index the flux table.
            float shellRe = dipoleRe / max(cos(latitude) * cos(latitude), 1e-3);
            float belt = smoothstep(beltHueInnerL, beltHueOuterL, shellRe);
            accumulated += transmittance * sampleAlpha * fluxColor(colourCoordinate, belt);
            transmittance *= 1.0 - sampleAlpha;
            if (transmittance < minimumTransmittance + 0.008) break;
          }
        }
      }
      t += stepLength;
    }

    // The opacity ceiling: however deep the accumulated field, the ray never
    // fully occludes what is behind it, so the Earth stays locatable inside a
    // merged low-energy belt. Colour keeps its true accumulation weighting.
    float alpha = 1.0 - max(transmittance, minimumTransmittance);
    if (alpha < 0.002) discard;
    gl_FragColor = vec4(accumulated, alpha);
  }
`;

export interface RadiationVolumeMeshOptions extends RadiationVolumeBakeOptions {
  transfer?: Partial<typeof RADIATION_VOLUME_TRANSFER>;
  /**
   * Override the opacity the view would otherwise resolve to. Absent — which
   * is the shipped path — the floor is DERIVED from the bake and the
   * extinction comes from the per-view table. An override is disclosed as an
   * override in the readout; it is for harnesses and experiments, not display.
   */
  opacity?: Partial<Pick<RadiationVolumeOpacityResolution, "opacityFloorLog10Flux" | "extinctionPerSceneUnit">>;
}

export interface RadiationVolumeMeshResult {
  mesh: THREE.Mesh;
  bake: RadiationVolumeBake;
  /** What the shader was given, and where the floor on screen came from. */
  opacity: RadiationVolumeOpacityResolution;
}

/**
 * Build the raymarched omnidirectional flux volume as a single mesh.
 *
 * The mesh is the back faces of a bounding sphere; the fragment shader marches
 * each view ray through the baked field, so the camera can sit outside or
 * inside the belts. Depth testing is off because the volume must both appear
 * in front of the globe and terminate on it; the Earth cut is analytic in the
 * shader instead, against the same scene radius the mapper places the globe at.
 */
export function createRadiationVolumeMesh(
  definition: RadiationBeltDefinition,
  frame: RadiationBeltFrame,
  energyKev: number,
  mapper: RadiationPositionMapper,
  options: RadiationVolumeMeshOptions = {},
): RadiationVolumeMeshResult {
  const mapperFrame = describeRadiationMapperFrame(mapper);
  const bake = bakeOmnidirectionalFluxVolume(definition, frame, energyKev, mapperFrame, options);
  const transfer = { ...RADIATION_VOLUME_TRANSFER, ...options.transfer };
  // The floor is read off THIS bake, so every dataset, frame and energy is
  // drawn against its own slot rather than against a table measured in August.
  const derived = resolveRadiationVolumeOpacityForBake(
    energyKev,
    bake,
    definition.encoding,
    mapperFrame.sceneRadiusForRe,
  );
  const overridden = options.opacity !== undefined
    && (options.opacity.opacityFloorLog10Flux !== undefined
      || options.opacity.extinctionPerSceneUnit !== undefined);
  const opacity: RadiationVolumeOpacityResolution = overridden
    ? {
        ...derived,
        ...options.opacity,
        floorSource: options.opacity?.opacityFloorLog10Flux !== undefined
          ? "explicit-override"
          : derived.floorSource,
        reason: options.opacity?.opacityFloorLog10Flux !== undefined
          ? `the caller set this floor explicitly, overriding the value derived from the data (${derived.reason})`
          : derived.reason,
      }
    : derived;

  const texture = new THREE.Data3DTexture(bake.data, bake.radialCount, bake.mltCount, bake.latitudeCount);
  texture.format = THREE.RedFormat;
  texture.type = THREE.UnsignedByteType;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.wrapR = THREE.ClampToEdgeWrapping;
  texture.unpackAlignment = 1;
  texture.needsUpdate = true;

  const encoding = definition.encoding;
  const span = encoding.maximum - encoding.minimum;
  const normalized = (log10Flux: number) => THREE.MathUtils.clamp((log10Flux - encoding.minimum) / span, 0, 1);

  const material = new THREE.ShaderMaterial({
    uniforms: {
      fluxVolume: { value: texture },
      cameraLocalPosition: { value: new THREE.Vector3() },
      gsmFromLocal: { value: mapperFrame.gsmFromLocal },
      smFromGsm: { value: new THREE.Matrix3() },
      dipoleOffsetSmRe: { value: new THREE.Vector3() },
      rulerTrueDistance: { value: activeDistanceScale() === "true-distance" ? 1 : 0 },
      sceneRadiusMinimum: { value: bake.sceneRadiusMinimum },
      sceneRadiusMaximum: { value: bake.sceneRadiusMaximum },
      latitudeMaximum: { value: bake.latitudeMaximumRadians },
      earthSceneRadius: { value: mapperFrame.earthSceneRadius },
      colourFloor: { value: normalized(transfer.colourFloorLog10Flux) },
      colourSpan: { value: Math.max(1e-6, normalized(transfer.colourCeilingLog10Flux) - normalized(transfer.colourFloorLog10Flux)) },
      opacityFloor: { value: normalized(opacity.opacityFloorLog10Flux) },
      opacitySpan: { value: Math.max(1e-6, normalized(transfer.colourCeilingLog10Flux) - normalized(opacity.opacityFloorLog10Flux)) },
      opacityCurveExponent: { value: transfer.opacityCurveExponent },
      extinction: { value: opacity.extinctionPerSceneUnit },
      minimumTransmittance: { value: 1 - transfer.maximumAccumulatedOpacity },
      colourRamp: { value: radiationRampTexture() },
      beltHueInnerL: { value: RADIATION_BELT_HUE_SPLIT.innerL },
      beltHueOuterL: { value: RADIATION_BELT_HUE_SPLIT.outerL },
    },
    vertexShader: VOLUME_VERTEX_SHADER,
    fragmentShader: VOLUME_FRAGMENT_SHADER,
    transparent: true,
    depthWrite: false,
    depthTest: false,
    side: THREE.BackSide,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.OneFactor,
    blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
  });
  material.addEventListener("dispose", () => texture.dispose());

  const geometry = new THREE.SphereGeometry(bake.sceneRadiusMaximum * 1.002, 48, 32);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.renderOrder = 30;
  mesh.onBeforeRender = (_renderer, _scene, camera) => {
    mesh.updateWorldMatrix(true, false);
    (material.uniforms.cameraLocalPosition!.value as THREE.Vector3)
      .copy(camera.position)
      .applyMatrix4(mesh.matrixWorld.clone().invert());
  };
  mesh.userData = {
    representation: "raymarched-omnidirectional-flux-centered-dipole-volume",
    quantity: isCombinedRadiationEnergy(energyKev)
      ? "omnidirectional differential electron flux, energy-weighted band average over 88 keV - 2.32 MeV"
      : "omnidirectional differential electron flux",
    energyKev,
    energyLabel: opacity.label,
    volumeRendering: true,
    isoSurface: false,
    transfer,
    opacityTuning: opacity,
    combinedEnergyView: isCombinedRadiationEnergy(energyKev),
    transferMeaning:
      `Colour runs one fixed ramp in every energy view — 10^${transfer.colourFloorLog10Flux} to `
      + `10^${transfer.colourCeilingLog10Flux} model flux units, the union of what the four published channels occupy — `
      + `so a given flux is the same colour at 88 keV as it is at 2.32 MeV and the channels can be compared by eye. `
      + `Opacity is tuned per view and only opacity: this view draws nothing below 10^${opacity.opacityFloorLog10Flux.toFixed(2)} `
      + `and accumulates ${opacity.extinctionPerSceneUnit} of extinction per scene unit above it, because `
      + `${opacity.reason}. That floor is ${opacity.floorSource === "derived-from-loaded-data" ? "derived at load time from this dataset's own field" : "NOT derived from this dataset"}; `
      + `opacity stays proportional to flux above it, so more flux is always more opaque. `
      + `Accumulated opacity is capped at ${transfer.maximumAccumulatedOpacity} per ray so the Earth stays locatable `
      + `inside a merged low-energy belt; with this tuning no view's brightest ray comes near that cap. `
      + `No threshold decides a boundary; the belts, the slot between them, and their merging at low energy are all the field's own.`,
    displayRangeLog10Flux: [transfer.colourFloorLog10Flux, transfer.colourCeilingLog10Flux],
    opacityFloorLog10Flux: opacity.opacityFloorLog10Flux,
    opacityFloorSource: opacity.floorSource,
    opacityFloorDerivation: opacity.derivation,
    integratedPitchChannelCount: bake.integratedPitchChannelCount,
    trappingFloorRe: bake.trappingFloorRe,
    displayWindow: bake.displayWindow,
    displayInterpolation:
      "bilinear along the native grid's own radial and MLT axes, then trilinear in the baked texture; "
      + "the same class of interpolation the triangulated native surface has always drawn between neighboring samples",
    fieldModel: "centered-ideal-dipole",
    fullNative3d: false,
    sourceFluxPreservedAtVertices: false,
    syntheticInnerBelt: false,
    protonPopulation: false,
    forcedBeltCount: false,
    particlePopulation: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS.particlePopulation,
    assumptions: GYROTROPIC_DIPOLE_MAPPING_ASSUMPTIONS,
  };
  return { mesh, bake, opacity };
}

export interface RadiationFieldLineGuideOptions {
  shellsRe?: number[];
  mltCount?: number;
  pointsPerLine?: number;
  trappingFloorRe?: number;
  color?: number;
  opacity?: number;
}

/**
 * A few centered-dipole field lines threading the volume, as orientation
 * guides. They are the mapping's own geometry — the same r = L cos^2(lambda)
 * every bounce shell already assumes — drawn explicitly so a reader can see
 * why the belts arch toward the poles. They are not data and are labelled so.
 */
export function createRadiationFieldLineGuides(
  mapper: RadiationPositionMapper,
  options: RadiationFieldLineGuideOptions = {},
) {
  const shellsRe = options.shellsRe ?? [1.6, 2.2, 3, 4, 5, 6.5];
  const mltCount = Math.max(1, Math.floor(options.mltCount ?? 12));
  const pointsPerLine = Math.max(8, Math.floor(options.pointsPerLine ?? 64));
  const trappingFloorRe = options.trappingFloorRe ?? RADIATION_BELT_DISPLAY_WINDOW.minimumMappedRadiusRe;
  const positions: number[] = [];
  for (const shellRe of shellsRe) {
    const footpoint = trappingFootpointLatitudeRadians(shellRe, trappingFloorRe);
    if (footpoint <= 0) continue;
    for (let mltIndex = 0; mltIndex < mltCount; mltIndex += 1) {
      const mlt = (mltIndex + 0.5) * 24 / mltCount;
      let previous: THREE.Vector3 | null = null;
      for (let step = 0; step <= pointsPerLine; step += 1) {
        const latitude = footpoint * (2 * step / pointsPerLine - 1);
        const gsm = dipoleRadiationPosition(shellRe, mlt, latitude);
        const mapped = mapper(gsm.x, gsm.y, gsm.z);
        if (previous) positions.push(previous.x, previous.y, previous.z, mapped.x, mapped.y, mapped.z);
        previous = mapped;
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  const material = new THREE.LineBasicMaterial({
    color: options.color ?? 0x7d95d9,
    transparent: true,
    opacity: options.opacity ?? 0.16,
    depthWrite: false,
  });
  const lines = new THREE.LineSegments(geometry, material);
  lines.name = "rbe-dipole-field-line-guides";
  lines.frustumCulled = false;
  lines.renderOrder = 29;
  lines.userData = {
    representation: "centered-dipole-field-line-guides",
    meaning: "the mapping's own assumed field geometry (r = L cos^2 lambda), drawn for orientation; not data",
    shellsRe,
  };
  return lines;
}
