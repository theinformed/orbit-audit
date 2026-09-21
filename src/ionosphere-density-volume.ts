import * as THREE from "three";

import { RULER_EARTH_RADIUS_KM, activeDistanceScale, sharedDisplayRadius } from "./radial-ruler";
import {
  dRegionSubsolarPoint,
  sampleEmpiricalDRegion,
  type GeographicPoint,
} from "./d-region-empirical";
import type { IonosphereVolumeBundle } from "./types";

/**
 * The ionosphere drawn as electron density everywhere it is published, instead
 * of as three peak surfaces with nothing between them.
 *
 * ## What this replaced, and why the old picture could not answer Sean
 *
 * Sean, looking at the TEC surface: "we can't combine the height of the
 * ionosphere with the TEC surface at all? ... there is no way to have that
 * show up so we can sort of see the D/E/F layers?"
 *
 * TEC is the vertical integral of electron density. The site was drawing the
 * integral as a surface and the field itself as three thin skins at the E, F1
 * and F2 peak altitudes, so the one relationship a reader most needs — the
 * column that the TEC number is a sum OF — was never drawn. This layer draws
 * the column.
 *
 * ## Why the peak surfaces were not enough, measured
 *
 * A peak surface can only exist where a peak exists. Measured on the live
 * bundle (frame 2026-08-19T07:40Z, 46 x 45 columns), taking the E-region
 * maximum in 90-170 km and the F2 maximum above it:
 *
 *     E peak altitude    median 150 km    range 100-167
 *     F2 peak altitude   median 341 km    range 204-700
 *     F2 minus E         median 0.68 dex  p95 2.31 dex
 *
 * and the number that decided this module's whole design, the PROMINENCE of
 * the E ledge above the valley separating it from F2:
 *
 *     median 0.02 dex, p95 0.54 dex
 *     above 0.1 dex in 40.7% of columns, above 0.3 dex in 19.9%
 *
 * 0.02 dex on the published 5.6-decade scale is 0.4% of the ramp: ONE code of
 * the artifact's own uint8. So no transfer function of absolute density can
 * make the E layer appear over most of the globe, because over most of the
 * globe at a given instant there is no distinct E maximum in the field to
 * show — the p5 prominence is negative, meaning the profile simply climbs
 * monotonically into F2 with no ledge at all.
 *
 * That is why the peak surfaces are KEPT rather than retired (see
 * `ionosphere-volume.ts`): they carry the artifact's own published criterion
 * — "largest interior local maximum with at least 0.02 dex two-sided
 * prominence" — and where the criterion fails they leave a hole, which is the
 * true statement "there is no separate E layer over this column right now".
 * The volume cannot say that; the surfaces can. What changed is that they are
 * now drawn on the shared ruler at their true altitudes, riding on this
 * volume's own bright shell, instead of at 8x height exaggeration floating
 * above a field that was not drawn.
 *
 * ## Why it is legible without exaggeration
 *
 * The shared radial ruler is logarithmic below geostationary, so this band is
 * strongly expanded already. Measured against a globe drawn at 100 units:
 *
 *      60 km -> +4.4     90 km -> +6.4     150 km -> +10.0
 *     341 km (median hmF2) -> +19.1        700 km -> +30.8
 *     2655 km (field top) -> +60.2
 *
 * So the published hmF2 range 204-700 km spans 112.9 to 130.8 — nearly 18
 * scene units of relief on a 100-unit globe. The F2 peak is not an invisible
 * skin on this ruler, and the 8x exaggeration the peak surfaces used to apply
 * was never needed. It is gone, and nothing here replaces it: a declared
 * shared ruler is not a per-layer fudge, and a private one is.
 *
 * ## The vertical texture axis is warped, and that is not a fudge either
 *
 * A 3D texture samples uniformly in its third axis. The field spans 60 to
 * 2,655 km, and everything a reader came to see — D at 60-85, E at 90-170,
 * F1 near 200, F2 at 204-700 — is in the bottom fifth of that. Uniform slabs
 * spend 80% of the texture on the topside and leave the E ledge 3 codes wide.
 *
 * So the axis is uniform in s = ln(1 + altitude/350 km), which is the shape of
 * the ruler's own near-Earth branch written as a pure function of altitude.
 * With 256 slabs that resolves
 *
 *      90 km ->  4.6 km per slab     300 km ->  6.7 km
 *     1000 km -> 10.5 km             2655 km -> 23 km
 *
 * which puts about 13 slabs across the E region and 3.4 km at its base. It is
 * written as a function of ALTITUDE rather than of drawn radius on purpose:
 * the same bake is then correct on both distance scales, so switching to the
 * true-distance ruler moves the drawn shell without re-baking the field.
 *
 * Resampling interpolates LOG density linearly in altitude, which is the
 * physically right interpolation between published levels and the same one
 * the bundle's own sampler documents.
 *
 * ## Two evidence classes in one picture, and the seam between them
 *
 * Sean expected four layers: "I thought you'd have D, E, F1 and F2....". The
 * site can show all four, but not from one source, and the difference is part
 * of the lesson rather than an inconvenience:
 *
 *     D          Wait-Spies empirical profile, driven by solar zenith angle
 *                and the MEASURED GOES 0.1-0.8 nm flux        EMPIRICAL
 *     E, F1, F2  NOAA WAM-IPE operational full-field output   MODEL/FORECAST
 *
 * They are the same quantity in the same units, so they share one density
 * scale and one ruler. They do NOT share a colour ramp. Below 85 km the
 * volume is drawn in the empirical ramp — warm ochre — and at and above 90 km
 * in the model ramp — cool blue to white. The hue change AT the boundary is
 * the seam, drawn rather than smoothed, because a reader must be able to see
 * that the bottom band is an empirical fit to a measured flux while the
 * layers above are a physics forecast.
 *
 * The two models disagree across that seam, and the picture shows that too.
 * Measured at 90 km on the same live frame:
 *
 *     WAM-IPE          p5 7.92   median 9.57   p95 10.71   log10 m^-3
 *     Wait-Spies day                    10.25
 *     Wait-Spies night                   8.93
 *
 * about half a decade of disagreement, which is an honest thing for a reader
 * to see two independent models do at their shared boundary.
 *
 * ## Why the bands stop at 85 and start at 90
 *
 * Neither model claims 85-90 km. `d-region-empirical.ts` states its own range
 * as 60-85 km — h' is an effective VLF reflection height, and the exponential
 * is not meant to be read up into the E region; extrapolated to 90 km under an
 * X1 flare it returns log10 Ne = 13.0, above the published artifact's own
 * 12.6 ceiling, which is the fit leaving its domain rather than a measurement.
 * The IPE full-field grid begins at 90 km. So the empirical band ends at 85
 * and the model band begins at 90, and the 5 km between them is drawn as
 * nothing because nothing is published there. On the shared ruler that gap is
 * 0.38 scene units — sub-pixel — so it reads as the seam it is, not as a hole.
 *
 * ## Validity
 *
 * `validityBits` is honoured per sample. An unsupported point is written with
 * evidence code 0 and the march skips it, so a missing corner leaves a hole
 * rather than being filled from its neighbours.
 */

/**
 * The drawn altitude band, and the two model domains inside it.
 *
 * `empiricalHighKm` and `modelLowKm` are deliberately different numbers. See
 * the header: the 5 km between them belongs to neither published model.
 */
export const IONOSPHERE_VOLUME_ALTITUDE_KM = {
  low: 60,
  empiricalHighKm: 85,
  modelLowKm: 90,
  high: 2655,
} as const;

/**
 * The four named regions of the ionosphere, as ALTITUDE BANDS of this drawn
 * column, ordered from the ground up and tiling it exactly.
 *
 * What these numbers are, and — more important — what they are not.
 *
 * The EDGES are the conventional nomenclature boundaries of the D, E, F1 and
 * F2 regions. They are not measured here and this module must never imply they
 * are: nothing in the WAM-IPE artifact marks a surface at 150 km, and the
 * whole reason this site assembles a composite profile at all is that the
 * operational field resolves F2 and genuinely does NOT resolve a distinct E or
 * F1 maximum (see `ionosphere-composite.ts`, which measured that rather than
 * assuming it). What IS measured is each region's PEAK HEIGHT — the E layer's
 * 110 km, the F1 layer's 190 km, and hmF2 straight out of the model — and
 * those are the numbers the card quotes. The edges here do one job: they say
 * which slice of the column a reader has asked to see.
 *
 * They tile without gaps on purpose. With all four switched on the drawn
 * volume is bit-for-bit the whole column, which is what this layer has always
 * opened on, so naming the regions changes nothing about the default picture.
 *
 * The ids are exactly the composite profile's `LayerId` values. They are typed
 * here rather than imported so that the render path does not pull the sounding
 * network in behind it; `tests/ionosphere-regions.test.ts` asserts the two
 * lists are identical, so they cannot drift apart in silence.
 */
export type IonosphereRegionId = "D" | "E" | "F1" | "F2";

export const IONOSPHERE_REGION_BANDS = [
  { region: "D", lowKm: 60, highKm: 90 },
  { region: "E", lowKm: 90, highKm: 150 },
  { region: "F1", lowKm: 150, highKm: 200 },
  { region: "F2", lowKm: 200, highKm: 2655 },
] as const satisfies ReadonlyArray<{ region: IonosphereRegionId; lowKm: number; highKm: number }>;

export const IONOSPHERE_REGION_IDS = IONOSPHERE_REGION_BANDS.map((band) => band.region);

/**
 * Where in a region's own distribution the legend swatch is read.
 *
 * 0.95 rather than 0.5, for the reason set out on `measured.regions`: a median
 * summarises a band's bulk and this volume is drawn optically thin, so what a
 * reader sees at the limb is the densest material along the ray. 0.95 rather
 * than 1.0 because a single hot voxel is not what a region looks like either;
 * this is the band at its own characteristic brightest, not its extreme.
 */
export const IONOSPHERE_REGION_SWATCH_PERCENTILE = 0.95;

/** Every region on — the picture this layer opens on, and the default everywhere. */
export function allIonosphereRegionsOn(): Record<IonosphereRegionId, boolean> {
  return { D: true, E: true, F1: true, F2: true };
}

/**
 * The region mask as the shader wants it: one component per band, in the band
 * table's own order, so the uniform and the checkboxes cannot fall out of step.
 */
export function regionEnabledVector(enabled: Record<IonosphereRegionId, boolean>): THREE.Vector4 {
  const [d, e, f1, f2] = IONOSPHERE_REGION_BANDS.map((band) => (enabled[band.region] ? 1 : 0));
  return new THREE.Vector4(d, e, f1, f2);
}

/**
 * Which band an altitude falls in, or null above the drawn column.
 *
 * Lower edge inclusive, upper edge exclusive except at the very top, so a
 * sample belongs to exactly one region and the counts below add up.
 */
export function ionosphereRegionAt(altitudeKm: number): IonosphereRegionId | null {
  for (const band of IONOSPHERE_REGION_BANDS) {
    if (altitudeKm < band.lowKm) return null;
    if (altitudeKm < band.highKm) return band.region;
  }
  return altitudeKm === IONOSPHERE_REGION_BANDS[IONOSPHERE_REGION_BANDS.length - 1]!.highKm
    ? "F2"
    : null;
}

/**
 * Uniform slabs on the warped vertical axis. 256 costs 45 x 46 x 256 x 2 bytes
 * = 1.06 MB of texture and resolves the E region at 4.6 km per slab; 96, the
 * thermosphere's count, would give 12 km there and smear the E ledge into the
 * F1 valley.
 */
export const IONOSPHERE_VOLUME_ALTITUDE_SLABS = 256;

/**
 * The warp constant, in km. This is the ruler's own near-Earth scale height
 * (`logBranch` uses `log1p(altitudeKm / 350)`), reused here so the texture
 * spends its resolution the same way the picture spends its scene units.
 */
export const IONOSPHERE_VOLUME_WARP_KM = 350;

/**
 * How many decades of density each ramp spans, measured DOWN from the field's
 * own maximum in that frame rather than fixed at the artifact's published
 * 7.0-12.6.
 *
 * The published window is 5.6 decades and using it directly is what made the
 * first build render as one flat teal fog. Two measurements say why.
 *
 * The visible material all sits in the top quarter of that window, so only the
 * top quarter of the ramp was ever reached and every part of the picture came
 * out the same cyan. And the topside is not thin: from 700 to 2,655 km the
 * field is still 10^10-10^11, over a 2,000 km path, so its integral swamps the
 * 100 km-thick F2 peak it has to be seen against. Normalized on the published
 * window the F2 peak reads 0.81 against the topside's 0.63 -- a 4.8x opacity
 * ratio at the curve's exponent, against a path-length ratio running the other
 * way. Normalized on 3 decades below the maximum the same two points read 0.66
 * and 0.32, a 74x ratio, and the peak becomes a shell instead of a fog.
 *
 * 3.0 is the smallest window that still holds the whole E-to-F2 structure: the
 * measured F2-minus-E gap reaches 2.31 dex at the 95th percentile, so a
 * narrower window would clip the E ledge to zero exactly where it is most
 * distinct.
 */
export const IONOSPHERE_MODEL_DISPLAY_DECADES = 3.0;

/**
 * The empirical band gets its OWN window, and that is a deliberate trade.
 *
 * The D region really does hold 2-3 decades fewer electrons than the F2 peak,
 * so on the model's window it clamps to zero and disappears. Drawing it on its
 * own window means the two bands' COLOURS are not comparable in absolute
 * density -- which is why they are not the same ramp, and why the card quotes
 * both windows as numbers. What stays true across the seam is the geometry:
 * both bands are on the shared ruler at their real heights.
 */
export const IONOSPHERE_EMPIRICAL_DISPLAY_DECADES = 3.0;

export function ionosphereVerticalWarp(altitudeKm: number): number {
  return Math.log1p(Math.max(0, altitudeKm) / IONOSPHERE_VOLUME_WARP_KM);
}

/**
 * Evidence codes carried in the texture's SECOND channel.
 *
 * The thermosphere volume spends its second channel on a per-altitude density
 * anomaly, because there the horizontal structure would otherwise be crushed
 * by the vertical falloff. That trick would not rescue this field — the
 * measurement in the header shows the E ledge is 0.02 dex, one code, and an
 * anomaly channel cannot amplify what is not there — so the channel is spent
 * on something the reader needs more: WHERE THE NUMBER CAME FROM.
 *
 * 0 is reserved for "nothing published here", which is how `validityBits` and
 * the 85-90 km gap both reach the shader.
 */
export const IONOSPHERE_EVIDENCE_CODE = {
  none: 0,
  empirical: 64,
  model: 192,
} as const;

/**
 * The model ramp: cool, and running dark -> blue -> cyan -> white with
 * density. White is the F2 peak; the topside trails off through blue into
 * nothing. Ordered low -> high density.
 */
export const IONOSPHERE_MODEL_COLOR_HEX = [
  "#04070f", "#0a1836", "#12315f", "#1a5486", "#1d7ea6",
  "#2eaebd", "#68d3cb", "#b6ecdf", "#f2fbff",
] as const;

/**
 * The empirical ramp: warm, and deliberately sharing no hue with the model
 * ramp, so the D band cannot be mistaken for the bottom of the IPE field.
 * Ordered low -> high density.
 */
export const IONOSPHERE_EMPIRICAL_COLOR_HEX = [
  "#0d0703", "#2a1405", "#4d2408", "#78380b", "#a24f10",
  "#c46c1c", "#dd8f34", "#eeb45e", "#fbdb9b",
] as const;

export const IONOSPHERE_RAMP_TEXELS = (IONOSPHERE_MODEL_COLOR_HEX.length - 1) * 32 + 1;

/**
 * The transfer function, and the measurement that inverted my first guess.
 *
 * `extinctionPerSceneUnit` is LOW, and that is the whole reason the layers are
 * visible. The first tuning pass raised it -- 0.7, then 1.5, then 4.0 -- on the
 * assumption that a denser-looking volume would show its structure better. It
 * does the opposite, and the reason is geometry rather than taste.
 *
 * At the limb, which is the only place vertical structure can read, a ray
 * integrates everything ABOVE its tangent altitude. If the volume is optically
 * thick the ray saturates on the first material it meets and the accumulated
 * colour becomes a monotone function of tangent height: no rings, ever, at any
 * exponent. Measured on the rendered canvas, reading pixel luminance out along
 * a radial line and converting each pixel back to altitude through the ruler,
 * extinction 1.5 at exponent 9 gave
 *
 *     101 km 122.6    222 km 118.5    376 km 120.3    570 km 112.0
 *
 * which is flat -- a fog, with the F2 peak nowhere in it.
 *
 * Held OPTICALLY THIN the same integral is dominated by the tangent region,
 * because that is where the path is long and the density is highest, so the
 * limb brightness tracks the LOCAL density at the tangent altitude. This is
 * why real airglow limb photographs show the F layer as a band. At extinction
 * 0.015 the same measurement gives
 *
 *     101 km 46.4     222 km 66.1     376 km 89.6     570 km 64.2     817 km 14.8
 *
 * a clean single maximum at 376-420 km, against a published hmF2 median of
 * 341 km -- the limb integral biases slightly high, exactly as it should. 0.022
 * is that regime with enough brightness to read on a dark globe.
 *
 * `opacityCurveExponent` at 3.0 is gentle for the same reason: the display
 * window already does the work of separating the F2 peak from the topside (see
 * IONOSPHERE_MODEL_DISPLAY_DECADES), and a steep curve on top of it only
 * crushes the profile back toward saturation.
 *
 * `maximumAccumulatedOpacity` is a guard rather than a tuning knob now. At this
 * extinction the accumulated alpha does not approach it, which is the point:
 * satellites fly inside this volume and it must stay a veil.
 *
 * `topsideKneeDecades` and `topsideDensityIndex` are the TOPSIDE FLOOR, and
 * they exist because the display window above has a bottom while the field does
 * not.
 *
 * Sean, looking at the two atmospheric layers together: "why does the ionosphere
 * exist higher up than the thermosphere? Is that right?" It is: the thermosphere
 * is a temperature layer of the NEUTRAL gas and ends at the thermopause, roughly
 * 500-1,000 km; the ionosphere is the ionised fraction of that same air and its
 * topside keeps going as the plasma thins, merging into the plasmasphere
 * thousands of kilometres up. Same air, two descriptions, two different tops.
 * The picture was not showing that, and the reason was not the domain -- this
 * volume has always been baked over 60-2,655 km, which draws to 160.2 scene
 * units against the thermosphere's 137.8 -- it was that the topside was too
 * faint to read. Measured on the rendered canvas (900 px, globe at 100 scene
 * units, frame 2026-08-19T21:00Z, outermost pixel more than 2 codes above the
 * bare globe, 99.9th percentile over 720 azimuths):
 *
 *     thermosphere volume    139.6 scene units   = 1,091 km
 *     ionosphere volume      142.8-143.9         = 1,264-1,326 km
 *
 * Three to four scene units apart on a hundred-unit globe (the range is two
 * runs of the same probe; it resolves about one scene unit). The two layers appeared to
 * share a ceiling, which is the one thing about them that is false.
 *
 * The cause is `pow(density, opacityCurveExponent)` with `density` normalized
 * over IONOSPHERE_MODEL_DISPLAY_DECADES. On the median column that curve is
 * 0.005 at 1,055 km, 2.5e-4 at 1,590 km and exactly ZERO at 2,397 km, where the
 * field falls below the window's floor -- so the layer stopped dead at a display
 * threshold and drew an edge the atmosphere does not have. The thermosphere
 * volume's own header states the rule this breaks: a layer must not invent a
 * boundary.
 *
 * So below the knee the opacity stops being a power of the normalized LOG
 * density and becomes a power law in electron density, matched in value at the
 * knee so the curve is continuous:
 *
 *     u <= knee     opacity = ((D - u) / D)^exponent          (unchanged)
 *     u >  knee     opacity = ((D - knee) / D)^exponent
 *                             * 10^(-index * (u - knee))
 *
 * with u = decades below the frame maximum and D = the display window.
 *
 * The knee is 1.5 decades because that is what leaves the picture Sean already
 * has. Everything within 1.5 decades of the frame maximum -- which on this frame
 * is the whole D/E/F1/F2 structure and the F2 shell, the bright material out to
 * about 700 km on the sunlit side -- goes through the untouched branch. Measured
 * against the shipped build over the whole 900 x 900 frame -- one build, one
 * frame, one camera, the shipped curve reproduced by pushing the knee to the
 * window's own width so the floor branch is unreachable -- the worst
 * per-channel change ANYWHERE is 3 codes out of 255, and 0.19% of subpixels
 * move by more than 2. A knee of 1.2 was measured too and rejected:
 * it reaches 2,190 km but moves 13,068 subpixels inside 120 units, which is the
 * F2 shell itself.
 *
 * The index, 0.28, is a DISPLAY FLOOR and not a physical statement -- the same
 * admission `empiricalOpacityScale` below makes, for the same kind of reason.
 * Opacity here was never proportional to anything physical; it is a cube of a
 * normalized logarithm, chosen so the F2 peak reads as a shell. 0.28 continues
 * that display choice into the topside at the gentlest slope that gets the
 * plasma read against a dark globe. What it buys, measured the same way:
 *
 *     ionosphere volume, topside floor on    152.3-152.8 = 1,917-1,961 km
 *
 * and the same pair measured on a frame eighteen hours earlier, 2026-08-19T03:00Z,
 * moves the same way: 144.4 before, 152.8 after. Against the thermosphere's
 * 139.6 / 1,091 km that is thirteen scene units clear, and
 * the ionosphere now visibly reaches about twice as high in altitude. Nothing
 * about the geometry changed to get there. The ruler is the shared one, the
 * domain is the published one, and no exaggeration factor exists anywhere in
 * this file -- what changed is only which of the published electrons are bright
 * enough to see.
 *
 * `empiricalOpacityScale` is NOT a physical statement, which is why it is named
 * separately. The D region genuinely holds two to three decades fewer electrons
 * than the F2 peak and its band is 25 km thick against the F region's several
 * hundred, so on equal terms it renders as nothing. That it is nearly nothing
 * in an electron-density picture is TRUE, and it is the same reason the D
 * region is invisible to a TEC measurement while dominating HF absorption --
 * which is the D-RAP layer's whole subject, and why these two layers are
 * complementary rather than duplicative. The scale lifts the band to where it
 * can be seen as a band; the card says the window it is drawn on.
 */
export const IONOSPHERE_VOLUME_TRANSFER = {
  opacityCurveExponent: 3.0,
  extinctionPerSceneUnit: 0.022,
  maximumAccumulatedOpacity: 0.85,
  empiricalOpacityScale: 6.0,
  topsideKneeDecades: 1.5,
  topsideDensityIndex: 0.28,
} as const;

export interface IonosphereVolumeBakeOptions {
  earthSceneRadius: number;
  /** The instant to draw. Selects/blends the published frames and drives the D-region solar geometry. */
  time: Date;
  /**
   * Measured GOES 0.1-0.8 nm irradiance, for the D region's flare response.
   * `null` means the site has no measurement right now, and the D band is then
   * drawn from solar geometry alone rather than from an assumed flux.
   */
  xrayFluxWm2?: number | null;
  altitudeSlabs?: number;
  /** Set false to draw only the published IPE field, with no empirical band. */
  includeEmpiricalDRegion?: boolean;
}

export interface IonosphereVolumeBake {
  data: Uint8Array<ArrayBuffer>;
  longitudeCount: number;
  latitudeCount: number;
  altitudeCount: number;
  altitudeLowKm: number;
  altitudeHighKm: number;
  /** log10 electron density at byte 0 and byte 255 for the MODEL ramp, measured from this frame. */
  logFloor: number;
  logCeiling: number;
  /** The same pair for the EMPIRICAL ramp, which is normalized separately. */
  empiricalLogFloor: number;
  empiricalLogCeiling: number;
  warpLow: number;
  warpHigh: number;
  sceneRadiusMinimum: number;
  sceneRadiusMaximum: number;
  /** What the bake actually found, so the card quotes it instead of re-deriving it. */
  measured: {
    modelSampleCount: number;
    empiricalSampleCount: number;
    invalidSampleCount: number;
    modelMaxLog10: number;
    /** log10 density at 90 km (model) and 85 km (empirical), for the seam disclosure. */
    modelFloorMedianLog10: number;
    empiricalTopMedianLog10: number;
    /**
     * What each named region actually holds in THIS frame, measured off the
     * bytes the shader will sample rather than re-derived from the physics.
     *
     * `drawnSampleCount` is how many drawn voxels fall in the band — zero means
     * there is nothing of that region in the picture, which is how the legend
     * can refuse to name a region that is not there rather than printing a row
     * for an empty slab.
     *
     * `rampPosition` is a HIGH PERCENTILE of the very byte the fragment shader
     * feeds into the colour ramp, so `swatchHex` below is not a colour chosen
     * to describe the region: it is the colour the renderer paints that region
     * where the region is ITSELF.
     *
     * It was the median first, and the live artifact said no. Measured on the
     * page: the median gave the D row #0d0703 — the ramp floor, near black,
     * for the band a reader sees as ORANGE — and gave F2 #102c56, DARKER than
     * the E row's #195283, which is backwards. Both failures have one cause. A
     * median describes a band's BULK, and a band's bulk is not what anybody
     * sees: over half the globe the D region is dark because the sun is not
     * up, and the F2 band is 2,455 km of thin topside wrapped around a 100 km
     * peak, so its middle sample is topside every time. This volume is drawn
     * deliberately OPTICALLY THIN (see IONOSPHERE_VOLUME_TRANSFER), which means
     * limb brightness tracks the densest material along the ray — so the
     * percentile is the honest summary of what a region looks like, and the
     * median is a summary of what it mostly is.
     *
     * With the percentile the ordering comes out as the physics: a warm D, a
     * dim blue E, a brighter F1, and a near-white F2 peak. The two-decade
     * density difference between the E heights and the F2 peak lands in the
     * legend for free.
     */
    regions: Record<IonosphereRegionId, {
      drawnSampleCount: number;
      rampPosition: number;
      brightLog10: number;
      swatchHex: string;
    }>;
  };
  frames: { startValidAt: string; endValidAt: string; blend: number };
}

function altitudeToRadiusRe(altitudeKm: number): number {
  return (RULER_EARTH_RADIUS_KM + altitudeKm) / RULER_EARTH_RADIUS_KM;
}

function decodeBase64Bytes(encoded: string): Uint8Array {
  const binary = globalThis.atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function median(values: number[]): number {
  if (values.length === 0) return Number.NaN;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = sorted.length >> 1;
  return sorted.length % 2 === 0 ? (sorted[middle - 1]! + sorted[middle]!) / 2 : sorted[middle]!;
}

/**
 * Which two published frames bracket the requested instant, and how far
 * between them it falls. Clamps at both ends rather than extrapolating: the
 * bundle's coverage window is a published fact and this layer does not draw
 * outside it.
 */
export function selectVolumeFrames(bundle: IonosphereVolumeBundle, time: Date) {
  const times = bundle.frames.map((frame) => Date.parse(frame.validAt));
  if (times.length === 0) throw new RangeError("WAM-IPE bundle has no frames");
  const wanted = time.getTime();
  if (!Number.isFinite(wanted)) throw new RangeError("Ionosphere volume time must be valid");
  if (wanted <= times[0]!) return { startIndex: 0, endIndex: 0, blend: 0 };
  const last = times.length - 1;
  if (wanted >= times[last]!) return { startIndex: last, endIndex: last, blend: 0 };
  let index = 0;
  while (index < last && times[index + 1]! <= wanted) index += 1;
  const span = times[index + 1]! - times[index]!;
  return {
    startIndex: index,
    endIndex: index + 1,
    blend: span > 0 ? (wanted - times[index]!) / span : 0,
  };
}

interface ColumnProfile {
  /** log10 electron density on the published altitude levels; NaN where unsupported. */
  values: Float32Array;
}

/**
 * Decode the two bracketing frames onto a uniform warped (longitude,
 * latitude, altitude) byte grid, then lay the empirical D band underneath it.
 *
 * The byte is normalized log10 density on the artifact's own published scale,
 * never linear density: the field spans 5.6 decades and a linear byte would
 * put everything below the F2 peak into the bottom two codes.
 */
function waitSpiesLog10(altitudeKm: number, effectiveHeightKm: number, betaPerKm: number) {
  const density = 1.43e13
    * Math.exp(-0.15 * effectiveHeightKm)
    * Math.exp((betaPerKm - 0.15) * (altitudeKm - effectiveHeightKm));
  return density > 0 ? Math.log10(density) : Number.NaN;
}

export function bakeIonosphereVolume(
  bundle: IonosphereVolumeBundle,
  options: IonosphereVolumeBakeOptions,
): IonosphereVolumeBake {
  const altitudeCount = options.altitudeSlabs ?? IONOSPHERE_VOLUME_ALTITUDE_SLABS;
  const longitudeCount = bundle.grid.longitudesDeg.length;
  const latitudeCount = bundle.grid.latitudesDeg.length;
  const levels = bundle.grid.altitudesKm;
  const levelCount = levels.length;
  const publishedFloor = bundle.electronDensity.minimum;
  const publishedCeiling = bundle.electronDensity.maximum;
  const publishedSpan = Math.max(1e-6, publishedCeiling - publishedFloor);

  const selection = selectVolumeFrames(bundle, options.time);
  const startFrame = bundle.frames[selection.startIndex]!;
  const endFrame = bundle.frames[selection.endIndex]!;
  const pointCount = longitudeCount * latitudeCount * levelCount;

  const startDensity = decodeBase64Bytes(startFrame.densityU8);
  const endDensity = decodeBase64Bytes(endFrame.densityU8);
  const startValidity = decodeBase64Bytes(startFrame.validityBits);
  const endValidity = decodeBase64Bytes(endFrame.validityBits);
  if (startDensity.length < pointCount || endDensity.length < pointCount) {
    throw new RangeError("WAM-IPE density frame is shorter than the published grid");
  }

  const validAt = (bits: Uint8Array, index: number) =>
    ((bits[index >> 3] ?? 0) & (1 << (index & 7))) !== 0;

  const low = IONOSPHERE_VOLUME_ALTITUDE_KM.low;
  const high = Math.min(IONOSPHERE_VOLUME_ALTITUDE_KM.high, levels[levelCount - 1]!);
  const warpLow = ionosphereVerticalWarp(low);
  const warpHigh = ionosphereVerticalWarp(high);
  const warpSpan = warpHigh - warpLow;

  // Where each warped slab falls in physical altitude, and which published
  // levels bracket it. Precomputed once because every column reuses it.
  const slabAltitudeKm = new Float32Array(altitudeCount);
  const slabLowerLevel = new Int32Array(altitudeCount);
  const slabLevelBlend = new Float32Array(altitudeCount);
  // Which named region each slab belongs to, as an index into
  // IONOSPHERE_REGION_BANDS, or -1 for a slab outside the drawn column. Same
  // precompute as the altitudes because every column reuses it.
  const slabRegionIndex = new Int32Array(altitudeCount);
  for (let k = 0; k < altitudeCount; k += 1) {
    const t = altitudeCount === 1 ? 0 : k / (altitudeCount - 1);
    const altitude = IONOSPHERE_VOLUME_WARP_KM * Math.expm1(warpLow + warpSpan * t);
    slabAltitudeKm[k] = altitude;
    const region = ionosphereRegionAt(altitude);
    slabRegionIndex[k] = region === null
      ? -1
      : IONOSPHERE_REGION_BANDS.findIndex((band) => band.region === region);
    let lower = 0;
    while (lower < levelCount - 2 && levels[lower + 1]! <= altitude) lower += 1;
    slabLowerLevel[k] = lower;
    const gap = levels[lower + 1]! - levels[lower]!;
    slabLevelBlend[k] = gap > 0 ? (altitude - levels[lower]!) / gap : 0;
  }

  const blend = selection.blend;
  const slab = longitudeCount * latitudeCount;

  // ---- Pre-pass: measure the two display windows ------------------------
  //
  // Both ramps are normalized against the field's OWN maximum in this frame,
  // not against the artifact's published 7.0-12.6. See the DISPLAY_DECADES
  // constants for the measurement that forced this; briefly, the published
  // window puts every visible sample in its top quarter and renders the whole
  // layer as one flat fog.
  //
  // Cheap on purpose: the model maximum is taken over the PUBLISHED levels
  // rather than over the resampled slabs, and that is exact enough in the only
  // direction that matters -- resampling interpolates linearly between levels,
  // so no slab can exceed the levels that bracket it.
  const includeEmpiricalPre = options.includeEmpiricalDRegion !== false;
  const subsolarPre: GeographicPoint | null = includeEmpiricalPre ? dRegionSubsolarPoint(options.time) : null;
  const xrayFluxWm2 = options.xrayFluxWm2 ?? null;

  let modelCeiling = Number.NEGATIVE_INFINITY;
  for (let index = 0; index < pointCount; index += 1) {
    if (!validAt(startValidity, index) || !validAt(endValidity, index)) continue;
    const a = publishedFloor + (publishedSpan * startDensity[index]!) / 255;
    const b = publishedFloor + (publishedSpan * endDensity[index]!) / 255;
    const value = a + (b - a) * blend;
    if (value > modelCeiling) modelCeiling = value;
  }
  // A frame with nothing supported in it must not produce a zero-width scale.
  if (!Number.isFinite(modelCeiling)) modelCeiling = publishedCeiling;
  const modelFloor = modelCeiling - IONOSPHERE_MODEL_DISPLAY_DECADES;
  const modelSpan = Math.max(1e-6, modelCeiling - modelFloor);

  // The empirical band's own window. Wait-Spies rises monotonically with
  // altitude for every published beta, so the band's maximum is at its top.
  const dRegionSamples = subsolarPre
    ? Array.from({ length: slab }, (_unused, cell) => {
      const j = Math.floor(cell / longitudeCount);
      const i = cell - j * longitudeCount;
      return sampleEmpiricalDRegion(
        bundle.grid.latitudesDeg[j]!,
        bundle.grid.longitudesDeg[i]!,
        options.time,
        xrayFluxWm2,
        subsolarPre,
      );
    })
    : null;
  let empiricalCeiling = Number.NEGATIVE_INFINITY;
  const empiricalTopSamples: number[] = [];
  if (dRegionSamples) {
    for (const sample of dRegionSamples) {
      const top = waitSpiesLog10(
        IONOSPHERE_VOLUME_ALTITUDE_KM.empiricalHighKm,
        sample.effectiveHeightKm,
        sample.betaPerKm,
      );
      if (!Number.isFinite(top)) continue;
      empiricalTopSamples.push(top);
      if (top > empiricalCeiling) empiricalCeiling = top;
    }
  }
  if (!Number.isFinite(empiricalCeiling)) empiricalCeiling = modelCeiling;
  const empiricalFloor = empiricalCeiling - IONOSPHERE_EMPIRICAL_DISPLAY_DECADES;
  const empiricalSpan = Math.max(1e-6, empiricalCeiling - empiricalFloor);
  const data = new Uint8Array(new ArrayBuffer(altitudeCount * slab * 2));

  let modelSampleCount = 0;
  let empiricalSampleCount = 0;
  let invalidSampleCount = 0;
  let modelMaxLog10 = Number.NEGATIVE_INFINITY;
  const modelFloorSamples: number[] = [];
  // One 256-bin histogram per region over the RAMP BYTE, not over the density.
  // A histogram rather than a sample list because there are half a million
  // voxels and the byte is already quantized to 256 levels — the resolution
  // the ramp texture is sampled at — so the histogram median is the exact
  // median of what gets drawn, at a fixed 4 KB.
  const regionHistogram = IONOSPHERE_REGION_BANDS.map(() => new Uint32Array(256));
  const regionDrawnCount = new Uint32Array(IONOSPHERE_REGION_BANDS.length);

  const column: ColumnProfile = { values: new Float32Array(levelCount) };

  for (let j = 0; j < latitudeCount; j += 1) {
    for (let i = 0; i < longitudeCount; i += 1) {

      // The published column, temporally blended in LOG density — the same
      // interpolation the bundle's own sampler documents, and the right one:
      // within a scale height log density is near-linear.
      for (let level = 0; level < levelCount; level += 1) {
        const index = level * slab + j * longitudeCount + i;
        if (!validAt(startValidity, index) || !validAt(endValidity, index)) {
          column.values[level] = Number.NaN;
          continue;
        }
        const a = publishedFloor + (publishedSpan * startDensity[index]!) / 255;
        const b = publishedFloor + (publishedSpan * endDensity[index]!) / 255;
        column.values[level] = a + (b - a) * blend;
      }

      const floorValue = column.values[0]!;
      if (Number.isFinite(floorValue)) modelFloorSamples.push(floorValue);

      // The empirical D profile for this column, from the pre-pass. Its two
      // shape parameters do not vary with altitude, so the whole band comes
      // from one sample.
      const dRegion = dRegionSamples ? dRegionSamples[j * longitudeCount + i]! : null;

      for (let k = 0; k < altitudeCount; k += 1) {
        const altitude = slabAltitudeKm[k]!;
        const target = (k * slab + j * longitudeCount + i) * 2;

        if (altitude < IONOSPHERE_VOLUME_ALTITUDE_KM.modelLowKm) {
          // Below the IPE grid: the empirical band, or nothing at all in the
          // 85-90 km strip that neither model claims.
          if (!dRegion || altitude > IONOSPHERE_VOLUME_ALTITUDE_KM.empiricalHighKm) {
            data[target] = 0;
            data[target + 1] = IONOSPHERE_EVIDENCE_CODE.none;
            invalidSampleCount += 1;
            continue;
          }
          const log10 = waitSpiesLog10(altitude, dRegion.effectiveHeightKm, dRegion.betaPerKm);
          if (!Number.isFinite(log10)) {
            data[target] = 0;
            data[target + 1] = IONOSPHERE_EVIDENCE_CODE.none;
            invalidSampleCount += 1;
            continue;
          }
          const normalized = (log10 - empiricalFloor) / empiricalSpan;
          const byte = Math.max(0, Math.min(255, Math.round(normalized * 255)));
          data[target] = byte;
          data[target + 1] = IONOSPHERE_EVIDENCE_CODE.empirical;
          empiricalSampleCount += 1;
          const empiricalRegion = slabRegionIndex[k]!;
          if (empiricalRegion >= 0) {
            const counts = regionHistogram[empiricalRegion]!;
            counts[byte] = (counts[byte] ?? 0) + 1;
            regionDrawnCount[empiricalRegion] = (regionDrawnCount[empiricalRegion] ?? 0) + 1;
          }
          continue;
        }

        const lower = slabLowerLevel[k]!;
        const a = column.values[lower]!;
        const b = column.values[lower + 1]!;
        if (!Number.isFinite(a) || !Number.isFinite(b)) {
          data[target] = 0;
          data[target + 1] = IONOSPHERE_EVIDENCE_CODE.none;
          invalidSampleCount += 1;
          continue;
        }
        const log10 = a + (b - a) * slabLevelBlend[k]!;
        if (log10 > modelMaxLog10) modelMaxLog10 = log10;
        const normalized = (log10 - modelFloor) / modelSpan;
        const byte = Math.max(0, Math.min(255, Math.round(normalized * 255)));
        data[target] = byte;
        data[target + 1] = IONOSPHERE_EVIDENCE_CODE.model;
        modelSampleCount += 1;
        const modelRegion = slabRegionIndex[k]!;
        if (modelRegion >= 0) {
          const counts = regionHistogram[modelRegion]!;
          counts[byte] = (counts[byte] ?? 0) + 1;
          regionDrawnCount[modelRegion] = (regionDrawnCount[modelRegion] ?? 0) + 1;
        }
      }
    }
  }

  // Turn each histogram into the one colour that region is painted with. The
  // D band reads the EMPIRICAL window and everything above it the MODEL window,
  // which is the same choice the shader makes from the evidence channel — the
  // two windows are not comparable in absolute density and this must not
  // quietly mix them.
  const regions = {} as IonosphereVolumeBake["measured"]["regions"];
  IONOSPHERE_REGION_BANDS.forEach((band, index) => {
    const counts = regionHistogram[index]!;
    const drawnSampleCount = regionDrawnCount[index]!;
    const empirical = band.region === "D";
    if (drawnSampleCount === 0) {
      regions[band.region] = {
        drawnSampleCount: 0,
        rampPosition: Number.NaN,
        brightLog10: Number.NaN,
        swatchHex: ionosphereRampHex(
          empirical ? IONOSPHERE_EMPIRICAL_COLOR_HEX : IONOSPHERE_MODEL_COLOR_HEX,
          0,
        ),
      };
      return;
    }
    let seen = 0;
    let brightByte = 0;
    const target = drawnSampleCount * IONOSPHERE_REGION_SWATCH_PERCENTILE;
    for (let byte = 0; byte < 256; byte += 1) {
      seen += counts[byte]!;
      if (seen >= target) { brightByte = byte; break; }
    }
    const rampPosition = brightByte / 255;
    regions[band.region] = {
      drawnSampleCount,
      rampPosition,
      brightLog10: empirical
        ? empiricalFloor + empiricalSpan * rampPosition
        : modelFloor + modelSpan * rampPosition,
      swatchHex: ionosphereRampHex(
        empirical ? IONOSPHERE_EMPIRICAL_COLOR_HEX : IONOSPHERE_MODEL_COLOR_HEX,
        rampPosition,
      ),
    };
  });

  return {
    data,
    longitudeCount,
    latitudeCount,
    altitudeCount,
    altitudeLowKm: low,
    altitudeHighKm: high,
    logFloor: modelFloor,
    logCeiling: modelCeiling,
    empiricalLogFloor: empiricalFloor,
    empiricalLogCeiling: empiricalCeiling,
    warpLow,
    warpHigh,
    sceneRadiusMinimum: sharedDisplayRadius(altitudeToRadiusRe(low), options.earthSceneRadius),
    sceneRadiusMaximum: sharedDisplayRadius(altitudeToRadiusRe(high), options.earthSceneRadius),
    measured: {
      modelSampleCount,
      empiricalSampleCount,
      invalidSampleCount,
      modelMaxLog10: Number.isFinite(modelMaxLog10) ? modelMaxLog10 : Number.NaN,
      modelFloorMedianLog10: median(modelFloorSamples),
      empiricalTopMedianLog10: median(empiricalTopSamples),
      regions,
    },
    frames: {
      startValidAt: startFrame.validAt,
      endValidAt: endFrame.validAt,
      blend,
    },
  };
}

let sharedRampTexture: THREE.DataTexture | null = null;

/**
 * One texture, two rows: row 0 empirical, row 1 model. The shader picks the
 * row from the evidence channel, so a sample can never be drawn in the ramp
 * belonging to the other model.
 */
/**
 * The one interpolation both the texture and the legend swatch go through.
 *
 * Written once and called from both places on purpose. A swatch that names a
 * colour by repeating a hex string is a second copy that can drift from the
 * pixels the moment anyone edits a ramp, and this layer has four regions whose
 * whole point is that the reader can match a name to a colour on screen.
 */
export function ionosphereRampColor(hexes: readonly string[], position: number): THREE.Color {
  const stops = hexes.map((hex) => new THREE.Color(hex));
  const t = Math.min(1, Math.max(0, position));
  const scaled = t * (stops.length - 1);
  const lower = Math.min(stops.length - 1, Math.floor(scaled));
  const upper = Math.min(stops.length - 1, lower + 1);
  return stops[lower]!.clone().lerp(stops[upper]!, scaled - lower);
}

/**
 * The same colour, as the CSS the legend needs.
 *
 * `getHexString(SRGBColorSpace)` rather than `getHexString()` because the ramp
 * is interpolated in the renderer's linear working space and the browser wants
 * sRGB — the conversion is the same one the renderer's output pass applies, so
 * the swatch and the painted pixel are the same colour and not merely similar.
 */
export function ionosphereRampHex(hexes: readonly string[], position: number): string {
  return `#${ionosphereRampColor(hexes, position).getHexString(THREE.SRGBColorSpace)}`;
}

function ionosphereRampTexture(): THREE.DataTexture {
  if (!sharedRampTexture) {
    const texels = IONOSPHERE_RAMP_TEXELS;
    const data = new Uint8Array(texels * 2 * 4);
    const rows = [IONOSPHERE_EMPIRICAL_COLOR_HEX, IONOSPHERE_MODEL_COLOR_HEX];
    rows.forEach((hexes, row) => {
      for (let i = 0; i < texels; i += 1) {
        const t = i / (texels - 1);
        const colour = ionosphereRampColor(hexes, t);
        const offset = (row * texels + i) * 4;
        data[offset] = Math.round(colour.r * 255);
        data[offset + 1] = Math.round(colour.g * 255);
        data[offset + 2] = Math.round(colour.b * 255);
        data[offset + 3] = 255;
      }
    });
    sharedRampTexture = new THREE.DataTexture(data, texels, 2);
    sharedRampTexture.needsUpdate = true;
  }
  return sharedRampTexture;
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
  uniform sampler3D densityVolume;
  uniform sampler2D colourRamp;
  uniform vec3 cameraLocalPosition;
  uniform float rulerTrueDistance;
  uniform float earthSceneRadius;
  uniform float sceneRadiusMinimum;
  uniform float sceneRadiusMaximum;
  uniform float warpLow;
  uniform float warpHigh;
  uniform float clipLowKm;
  uniform float clipHighKm;
  // One component per named region, in the order of IONOSPHERE_REGION_BANDS:
  // 1.0 for a region the reader has switched on, 0.0 for one switched off. A
  // vec4 because there are exactly four regions and there is no fifth; the
  // unit suite asserts the band table's length so this cannot silently rot.
  uniform vec4 regionEnabled;
  const vec4 REGION_LOW_KM = vec4(${IONOSPHERE_REGION_BANDS.map((band) => band.lowKm.toFixed(1)).join(", ")});
  const vec4 REGION_HIGH_KM = vec4(${IONOSPHERE_REGION_BANDS.map((band) => band.highKm.toFixed(1)).join(", ")});
  uniform float opacityCurveExponent;
  uniform float displayDecades;
  uniform float topsideKneeDecades;
  uniform float topsideDensityIndex;
  uniform float extinction;
  uniform float minimumTransmittance;
  uniform float empiricalOpacityScale;
  varying vec3 vLocalPosition;

  const int MAX_STEPS = 192;
  const float RULER_A = 18.202857142857143;
  const float RULER_ANCHOR_RE = 6.6170146;
  const float EARTH_RADIUS_KM = 6371.0;
  const float WARP_KM = 350.0;
  const float PI = 3.14159265358979323846;
  const float TWO_PI = 6.28318530717958647692;

  // The shared radial ruler's inverse. Altitude must be recovered in PHYSICAL
  // space: the ruler is steeply nonlinear through this band, so treating scene
  // units as proportional to altitude would put the 2,655 km top of the field
  // at about 400 km and stack the whole topside onto the F2 peak.
  float logBranchDrawn(float r) {
    return 1.0 + 0.28 * log(1.0 + RULER_A * max(0.0, r - 1.0));
  }

  float reFromDrawn(float drawn) {
    float x = drawn / earthSceneRadius;
    if (rulerTrueDistance > 0.5) return max(1.0, x);
    float anchorDrawn = logBranchDrawn(RULER_ANCHOR_RE);
    if (x <= anchorDrawn) return 1.0 + (exp((x - 1.0) / 0.28) - 1.0) / RULER_A;
    return RULER_ANCHOR_RE * x / anchorDrawn;
  }

  vec2 sphereIntersect(vec3 origin, vec3 direction, float radius) {
    float b = dot(origin, direction);
    float c = dot(origin, origin) - radius * radius;
    float disc = b * b - c;
    if (disc < 0.0) return vec2(1.0, -1.0);
    float root = sqrt(disc);
    return vec2(-b - root, -b + root);
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

    // The globe is opaque: a ray that reaches Earth stops there, so the far
    // side of the ionosphere never shows through the planet.
    vec2 earth = sphereIntersect(cameraLocalPosition, direction, earthSceneRadius);
    if (earth.x <= earth.y && earth.y > 0.0 && earth.x < tFar) {
      tFar = max(earth.x, tNear);
    }
    if (tFar - tNear < 1e-4) discard;

    float span = tFar - tNear;
    float stepLength = span / float(MAX_STEPS);
    // Jitter the first sample so the fixed step count does not draw itself as
    // concentric rings across the limb.
    float offset = hash(gl_FragCoord.xy) * stepLength;

    vec3 accumulated = vec3(0.0);
    float transmittance = 1.0;

    for (int i = 0; i < MAX_STEPS; i += 1) {
      float t = tNear + offset + float(i) * stepLength;
      if (t > tFar) break;
      vec3 samplePosition = cameraLocalPosition + direction * t;
      float drawn = length(samplePosition);
      if (drawn < sceneRadiusMinimum || drawn > sceneRadiusMaximum) continue;

      float altitudeKm = (reFromDrawn(drawn) - 1.0) * EARTH_RADIUS_KM;
      // The texture's vertical axis is uniform in log(1 + altitude/350 km),
      // not in altitude. See the module header: it buys 4.6 km per slab at the
      // E region instead of 12.
      // The altitude bands the reader asked for. Clipping happens HERE, in
      // physical kilometres, rather than by fading the ramp: a region that is
      // switched off is not drawn faintly, it is not drawn.
      //
      // Four independent bands rather than one window, because the interesting
      // comparisons are the DISJOINT ones — D and F2 together with the E and F1
      // heights between them empty is the picture that shows how far apart the
      // absorbing bottom and the reflecting top of this thing are.
      if (altitudeKm < clipLowKm || altitudeKm > clipHighKm) continue;
      vec4 inBand = step(REGION_LOW_KM, vec4(altitudeKm)) * step(vec4(altitudeKm), REGION_HIGH_KM);
      if (dot(inBand * regionEnabled, vec4(1.0)) < 0.5) continue;
      float w = (log(1.0 + altitudeKm / WARP_KM) - warpLow) / (warpHigh - warpLow);
      if (w < 0.0 || w > 1.0) continue;

      vec3 unit = samplePosition / drawn;
      // Geographic frame: this mesh is parented to the Earth-fixed group, so
      // local coordinates ARE geographic — y is the polar axis and theta is
      // longitude, matching every other geographic layer in the scene.
      float latitude = asin(clamp(unit.y, -1.0, 1.0));
      float longitude = atan(-unit.z, unit.x);
      float u = fract(longitude / TWO_PI);
      float v = (latitude + PI * 0.5) / PI;

      vec2 sampled = texture(densityVolume, vec3(u, v, w)).rg;
      float density = sampled.r;
      float evidence = sampled.g;
      // Evidence code 0 is "nothing published here" — an unsupported column,
      // or the 85-90 km strip between the two models' domains. It leaves a
      // hole rather than being filled.
      if (evidence < 0.125) continue;

      float isModel = step(0.5, evidence);
      // The shaped curve, unchanged: a power of the normalized log density.
      float shaped = pow(density, opacityCurveExponent);
      // The TOPSIDE FLOOR, model band only. Above the knee this is not
      // reached and the shaped curve is used exactly as before; below it the
      // opacity becomes a power law in electron density, so the thinning
      // plasma keeps drawing instead of stopping dead at the display floor.
      // See IONOSPHERE_VOLUME_TRANSFER for the measurement behind the two
      // numbers, and for why the empirical band is deliberately excluded.
      float kneeDensity = max(0.0, 1.0 - topsideKneeDecades / displayDecades);
      float topside = pow(kneeDensity, opacityCurveExponent)
        * exp(-topsideDensityIndex * 2.302585093 * displayDecades
              * max(0.0, kneeDensity - density));
      float modelOpacity = density >= kneeDensity ? shaped : topside;
      float opacity = mix(shaped * empiricalOpacityScale, modelOpacity, isModel);
      // Row 0 of the ramp is the empirical palette, row 1 the model palette.
      vec3 colour = texture(colourRamp, vec2(density, mix(0.25, 0.75, isModel))).rgb;
      float absorbed = 1.0 - exp(-opacity * extinction * stepLength);
      accumulated += transmittance * absorbed * colour;
      transmittance *= 1.0 - absorbed;
      if (transmittance < minimumTransmittance) break;
    }

    float alpha = 1.0 - transmittance;
    if (alpha <= 0.002) discard;
    gl_FragColor = vec4(accumulated, alpha);
  }
`;

export interface IonosphereVolumeMeshOptions extends IonosphereVolumeBakeOptions {
  transfer?: Partial<typeof IONOSPHERE_VOLUME_TRANSFER>;
  /** The altitude band to draw, in km. Outside it nothing is drawn at all. */
  clipLowKm?: number;
  clipHighKm?: number;
  /** Which named regions to draw. Omitted means all four, the layer's default. */
  regionsEnabled?: Record<IonosphereRegionId, boolean>;
}

export interface IonosphereVolumeMeshResult {
  mesh: THREE.Mesh<THREE.SphereGeometry, THREE.ShaderMaterial>;
  bake: IonosphereVolumeBake;
}

export function createIonosphereVolumeMesh(
  bundle: IonosphereVolumeBundle,
  options: IonosphereVolumeMeshOptions,
): IonosphereVolumeMeshResult {
  const bake = bakeIonosphereVolume(bundle, options);
  const transfer = { ...IONOSPHERE_VOLUME_TRANSFER, ...options.transfer };

  const texture = new THREE.Data3DTexture(
    bake.data,
    bake.longitudeCount,
    bake.latitudeCount,
    bake.altitudeCount,
  );
  texture.format = THREE.RGFormat;
  texture.type = THREE.UnsignedByteType;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  // Longitude wraps and latitude does not; the altitude axis must clamp so the
  // empirical D band can never wrap round onto the topside.
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.wrapR = THREE.ClampToEdgeWrapping;
  texture.unpackAlignment = 1;
  texture.needsUpdate = true;

  const material = new THREE.ShaderMaterial({
    uniforms: {
      densityVolume: { value: texture },
      colourRamp: { value: ionosphereRampTexture() },
      cameraLocalPosition: { value: new THREE.Vector3() },
      rulerTrueDistance: { value: activeDistanceScale() === "true-distance" ? 1 : 0 },
      earthSceneRadius: { value: options.earthSceneRadius },
      sceneRadiusMinimum: { value: bake.sceneRadiusMinimum },
      sceneRadiusMaximum: { value: bake.sceneRadiusMaximum },
      warpLow: { value: bake.warpLow },
      warpHigh: { value: bake.warpHigh },
      clipLowKm: { value: options.clipLowKm ?? IONOSPHERE_VOLUME_ALTITUDE_KM.low },
      clipHighKm: { value: options.clipHighKm ?? IONOSPHERE_VOLUME_ALTITUDE_KM.high },
      regionEnabled: { value: regionEnabledVector(options.regionsEnabled ?? allIonosphereRegionsOn()) },
      opacityCurveExponent: { value: transfer.opacityCurveExponent },
      displayDecades: { value: IONOSPHERE_MODEL_DISPLAY_DECADES },
      topsideKneeDecades: { value: transfer.topsideKneeDecades },
      topsideDensityIndex: { value: transfer.topsideDensityIndex },
      extinction: { value: transfer.extinctionPerSceneUnit },
      minimumTransmittance: { value: 1 - transfer.maximumAccumulatedOpacity },
      empiricalOpacityScale: { value: transfer.empiricalOpacityScale },
    },
    vertexShader: VOLUME_VERTEX_SHADER,
    fragmentShader: VOLUME_FRAGMENT_SHADER,
    transparent: true,
    depthWrite: false,
    // Depth testing is OFF, and this is not a preference. The proxy geometry
    // is a BackSide sphere at 160 scene units, so its drawn fragments are on
    // the FAR side of the volume -- further from the camera than the opaque
    // Earth at 100. With depth testing on, the Earth rejects every fragment
    // over its own silhouette and the layer can only ever draw in the limb
    // annulus: measured on the first build, the entire globe-facing column
    // was missing and only a thin rim glowed.
    //
    // Nothing is lost by switching it off, because the occlusion this layer
    // actually needs is already done analytically in the shader: a ray that
    // reaches the globe stops at the Earth intersection, so the far side never
    // shows through the planet. Satellites stay visible because they are
    // transparent at renderOrder 0 and this volume is at -3, so they are
    // painted after it rather than tested against it.
    depthTest: false,
    side: THREE.BackSide,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.OneFactor,
    blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
  });
  material.addEventListener("dispose", () => texture.dispose());

  const geometry = new THREE.SphereGeometry(bake.sceneRadiusMaximum * 1.002, 64, 40);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  // Drawn BEFORE the satellites and the TEC shell, both of which are
  // transparent at renderOrder 0 and write no depth. At a higher order this
  // volume would composite over every spacecraft flying inside it, which is
  // the opposite of the point; here they paint on top of it, and the additive
  // TEC glow lands over the column it is the integral of.
  mesh.renderOrder = -3;
  mesh.name = "ionosphere-electron-density-volume";
  mesh.onBeforeRender = (_renderer, _scene, camera) => {
    mesh.updateWorldMatrix(true, false);
    (material.uniforms.cameraLocalPosition!.value as THREE.Vector3)
      .copy(camera.position)
      .applyMatrix4(mesh.matrixWorld.clone().invert());
  };
  mesh.userData = {
    representation: "raymarched-electron-density-volume",
    quantity: "electron number density",
    units: "m-3",
    volumeRendering: true,
    altitudeLowKm: bake.altitudeLowKm,
    altitudeHighKm: bake.altitudeHighKm,
    log10DensityFloor: bake.logFloor,
    log10DensityCeiling: bake.logCeiling,
    verticalExaggeration: 1,
    evidence: {
      model: "NOAA WAM-IPE operational full-field output, 90 km and above",
      empirical: "Wait-Spies D-region profile driven by solar zenith angle and measured GOES X-ray flux, 60-85 km",
      unpublished: "85-90 km is claimed by neither model and is drawn as nothing",
    },
  };
  return { mesh, bake };
}

/**
 * The scene layer.
 *
 * It owns only the volume. The published E/F1/F2 peak surfaces stay in
 * `ionosphere-volume.ts` and are drawn alongside this, because they carry the
 * artifact's own peak criterion and its holes — information this volume
 * cannot express. See the module header for the measurement behind that
 * split.
 */
export class IonosphereDensityVolumeLayer {
  private readonly group = new THREE.Group();
  private mesh: THREE.Mesh<THREE.SphereGeometry, THREE.ShaderMaterial> | null = null;
  private bakeValue: IonosphereVolumeBake | null = null;
  private time: Date;
  private xrayFluxWm2: number | null = null;
  private pendingRebake = false;
  private clipLowKm: number = IONOSPHERE_VOLUME_ALTITUDE_KM.low;
  private clipHighKm: number = IONOSPHERE_VOLUME_ALTITUDE_KM.high;
  private regionsEnabledValue: Record<IonosphereRegionId, boolean> = allIonosphereRegionsOn();

  constructor(
    private readonly bundle: IonosphereVolumeBundle,
    private readonly earthSceneRadius: number,
  ) {
    this.group.name = "ionosphere-density-volume";
    this.group.visible = false;
    this.time = new Date(bundle.frames[0]?.validAt ?? Date.now());
  }

  object3d(): THREE.Group {
    return this.group;
  }

  setEnabled(visible: boolean): void {
    this.group.visible = visible;
    // A hidden layer does not pay for a bake; the deferred one lands when it
    // is switched back on.
    if (visible && this.pendingRebake) this.rebake();
  }

  lastBake(): IonosphereVolumeBake | null {
    return this.bakeValue;
  }

  setSimulationTime(time: Date): void {
    if (time.getTime() === this.time.getTime()) return;
    this.time = new Date(time);
    this.invalidate();
  }

  /**
   * Draw only this altitude band.
   *
   * This is the layer's answer to "show me the D region", and it is the
   * honest one. Measured on the rendered canvas, boosting the D band's opacity
   * until it dominates does not work and cannot: at the limb every ray that
   * reaches 75 km has already crossed the entire F region twice, so the D
   * contribution is diluted no matter what it is multiplied by -- pushing the
   * empirical scale from 6 to 300 moved the sampled colour at 75 km only from
   * rgb(17,69,69) to rgb(31,60,57), and what little it did was mostly the D
   * band OCCULTING the F region behind it.
   *
   * So the band is isolated instead of amplified. Asking for 60-90 km draws
   * the D region alone, at its real height, on the real ruler, with nothing
   * exaggerated -- and the F region is absent because it was not asked for,
   * not because it was faded out.
   *
   * No rebake: the band is a shader clip in physical kilometres, so switching
   * bands costs nothing and the field itself is untouched.
   */
  /**
   * Draw exactly these named regions.
   *
   * Replaces the single contiguous altitude window this layer used to expose
   * as a dropdown. Four independent switches can express what one window
   * cannot — D and F2 with the heights between them empty — and, more to the
   * point, they say the region's NAME rather than a pair of kilometre numbers
   * the reader has to already know how to read.
   *
   * All four on is the default and reproduces the old whole-column picture
   * exactly, because the bands tile the column without gaps.
   *
   * No rebake, same as the window it replaces: this is a shader test in
   * physical kilometres and the field itself is untouched, so switching a
   * region costs nothing and the measured density windows on the card do not
   * move when the reader hides a band.
   */
  setRegionsEnabled(enabled: Record<IonosphereRegionId, boolean>): void {
    this.regionsEnabledValue = { ...enabled };
    const uniforms = this.mesh?.material.uniforms;
    if (!uniforms) return;
    (uniforms.regionEnabled!.value as THREE.Vector4).copy(regionEnabledVector(this.regionsEnabledValue));
  }

  get regionsEnabled(): Record<IonosphereRegionId, boolean> {
    return { ...this.regionsEnabledValue };
  }

  setAltitudeRange(minimumKm: number, maximumKm: number): void {
    this.clipLowKm = Math.min(minimumKm, maximumKm);
    this.clipHighKm = Math.max(minimumKm, maximumKm);
    const uniforms = this.mesh?.material.uniforms;
    if (!uniforms) return;
    uniforms.clipLowKm!.value = this.clipLowKm;
    uniforms.clipHighKm!.value = this.clipHighKm;
  }

  /** Measured GOES 0.1-0.8 nm irradiance, or null when the site has none. */
  setXrayFlux(fluxWm2: number | null): void {
    const next = fluxWm2 !== null && Number.isFinite(fluxWm2) && fluxWm2 > 0 ? fluxWm2 : null;
    if (next === this.xrayFluxWm2) return;
    this.xrayFluxWm2 = next;
    this.invalidate();
  }

  private invalidate(): void {
    if (!this.group.visible) {
      this.pendingRebake = true;
      return;
    }
    this.rebake();
  }

  private rebake(): void {
    this.pendingRebake = false;
    const { mesh, bake } = createIonosphereVolumeMesh(this.bundle, {
      earthSceneRadius: this.earthSceneRadius,
      time: this.time,
      xrayFluxWm2: this.xrayFluxWm2,
      clipLowKm: this.clipLowKm,
      clipHighKm: this.clipHighKm,
      regionsEnabled: this.regionsEnabledValue,
    });
    this.dispose();
    this.mesh = mesh;
    this.bakeValue = bake;
    this.group.add(mesh);
  }

  dispose(): void {
    if (!this.mesh) return;
    this.group.remove(this.mesh);
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
    this.mesh = null;
  }
}
