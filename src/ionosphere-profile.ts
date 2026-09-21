/**
 * The vertical electron-density profile over one point, and the operational
 * numbers that fall out of it.
 *
 * The site has been drawing three peak surfaces from an artifact that holds
 * the whole column all along: 30 altitudes from 90 km to 2,655 km at every
 * grid point (`ionosphere-volume.ts`). Nothing here is a new data source and
 * nothing here is fitted. Given electron density, the critical frequency is
 * exact plasma physics, the column integral is arithmetic, and the two
 * consequences a Space Cadre or METOC officer actually plans against — which
 * HF frequencies reflect, and how much range error a GNSS receiver eats —
 * follow from those two.
 *
 * The evidence class does NOT improve on the way through. WAM-IPE is a model,
 * so every number in here is model-derived, and `profileEvidenceNote()` is the
 * sentence that says so wherever a value from this file is shown. A reader who
 * takes foF2 from this page as a measured sounding has been misled, and this
 * project's whole contract is that it never lets that happen.
 */

import type { IonosphereSampler, IonosphereSampleResult } from "./ionosphere-volume";

/**
 * foF2 = 8.98e-6 * sqrt(Ne), for Ne in m^-3 and foF2 in MHz.
 *
 * The plasma frequency, which is exact: it is where the refractive index of a
 * cold electron plasma reaches zero, so a vertically incident wave below it
 * reflects and one above it escapes. The constant is sqrt(e^2 / (4 pi^2
 * epsilon0 me)) carried to the units this site prints in.
 */
export const PLASMA_FREQUENCY_MHZ_COEFFICIENT = 8.98e-6;

/** One rung of the sampled column. */
export interface ProfileLevel {
  altitudeKm: number;
  /** Null where the model publishes no valid value for that cell. */
  electronDensityM3: number | null;
  /** Plasma frequency of this level, MHz. Null wherever density is null. */
  plasmaFrequencyMhz: number | null;
}

export interface ProfileDerivations {
  /** F2 critical frequency, MHz: the plasma frequency of the densest level. */
  foF2Mhz: number;
  /** Height of that densest level, km. Sampled resolution, not a fitted peak. */
  hmF2Km: number;
  /**
   * Vertical total electron content over the sampled column, TECU
   * (1 TECU = 1e16 electrons per square metre).
   */
  verticalTecu: number;
  /**
   * Zenith GNSS range error at L1, metres, from the column integral.
   * 40.3 / f^2 * TEC, the first-order ionospheric delay.
   */
  gnssRangeErrorL1M: number;
  /**
   * The column integral only covers what the model publishes. WAM-IPE's grid
   * starts at 90 km and stops at 2,655 km, so plasmaspheric content above the
   * top of the grid is NOT in this number and the caller must say so.
   */
  integratedFromKm: number;
  integratedToKm: number;
}

/** GNSS L1, MHz. The band the range-error figure is quoted for. */
export const GNSS_L1_MHZ = 1575.42;

/**
 * First-order ionospheric group delay constant, m * MHz^2 / TECU.
 *
 * 40.3 / f^2 * TEC with TEC in electrons/m^2 and f in Hz gives metres; folded
 * to TECU and MHz this is the number to divide by f_MHz^2.
 */
const GNSS_DELAY_CONSTANT = 40.3 * 1e16 / 1e12;

/**
 * Plasma frequency of an electron density, MHz. Returns null for a density
 * that is absent or non-physical rather than propagating a NaN into a readout.
 */
export function plasmaFrequencyMhz(electronDensityM3: number | null): number | null {
  if (electronDensityM3 === null || !Number.isFinite(electronDensityM3) || electronDensityM3 <= 0) return null;
  return PLASMA_FREQUENCY_MHZ_COEFFICIENT * Math.sqrt(electronDensityM3);
}

/**
 * Maximum usable frequency for a path of a given length, MHz.
 *
 * The secant law: MUF = foF2 * sec(phi), where phi is the angle of incidence
 * at the reflecting layer. Given a ground range D and a reflection height h,
 * a flat-Earth secant is sqrt(1 + (D/2h)^2), which is the standard classroom
 * form and is what this returns. It is deliberately NOT corrected for Earth
 * curvature, ray bending or a tilted layer, so it overstates the MUF on long
 * paths; `MUF_LIMITATION` states that wherever the number is shown.
 *
 * A zero-length path returns foF2 itself, which is the vertical case and is
 * exactly right.
 */
export function mufMhz(foF2Mhz: number, hmF2Km: number, groundRangeKm: number): number | null {
  if (!Number.isFinite(foF2Mhz) || foF2Mhz <= 0) return null;
  if (!Number.isFinite(hmF2Km) || hmF2Km <= 0) return null;
  if (!Number.isFinite(groundRangeKm) || groundRangeKm < 0) return null;
  return foF2Mhz * Math.sqrt(1 + (groundRangeKm / (2 * hmF2Km)) ** 2);
}

/**
 * Zenith GNSS range error from vertical TEC, metres, at a chosen frequency.
 * First order only — the higher-order terms are well under a centimetre and
 * are not what a planner is being warned about here.
 */
export function gnssRangeErrorM(verticalTecu: number, frequencyMhz = GNSS_L1_MHZ): number | null {
  if (!Number.isFinite(verticalTecu) || verticalTecu < 0) return null;
  if (!Number.isFinite(frequencyMhz) || frequencyMhz <= 0) return null;
  return (GNSS_DELAY_CONSTANT * verticalTecu) / frequencyMhz ** 2;
}

/**
 * Vertical TEC of a sampled column, TECU, by the trapezium rule over the
 * levels that carry a value.
 *
 * A gap in the middle of the column is bridged by the trapezium across it,
 * which is an interpolation and is why `levelsUsed` is reported: a column that
 * integrated over half its levels is a weaker number than one that used all
 * thirty, and the caller shows that count rather than hiding it. Fewer than
 * two valid levels is not an integral at all and returns null.
 */
export function verticalTecu(levels: readonly ProfileLevel[]): { tecu: number; levelsUsed: number } | null {
  const valid = levels.filter((level): level is ProfileLevel & { electronDensityM3: number } =>
    level.electronDensityM3 !== null && Number.isFinite(level.electronDensityM3));
  if (valid.length < 2) return null;
  let electronsPerSquareMetre = 0;
  for (let index = 1; index < valid.length; index += 1) {
    const lower = valid[index - 1]!;
    const upper = valid[index]!;
    // Altitudes are km; the integral wants metres.
    const thicknessM = (upper.altitudeKm - lower.altitudeKm) * 1_000;
    electronsPerSquareMetre += 0.5 * (lower.electronDensityM3 + upper.electronDensityM3) * thicknessM;
  }
  return { tecu: electronsPerSquareMetre / 1e16, levelsUsed: valid.length };
}

/**
 * The peak of a sampled column: the densest level and its height.
 *
 * This is the grid's densest LEVEL, not a fitted parabolic peak, so hmF2 lands
 * on a published altitude and is only as precise as the vertical sampling. The
 * honest thing is to report it that way rather than to interpolate a smoother
 * height the source never resolved.
 */
export function columnPeak(levels: readonly ProfileLevel[]): { altitudeKm: number; electronDensityM3: number } | null {
  let peak: { altitudeKm: number; electronDensityM3: number } | null = null;
  for (const level of levels) {
    if (level.electronDensityM3 === null || !Number.isFinite(level.electronDensityM3)) continue;
    if (!peak || level.electronDensityM3 > peak.electronDensityM3) {
      peak = { altitudeKm: level.altitudeKm, electronDensityM3: level.electronDensityM3 };
    }
  }
  return peak;
}

/** Everything derivable from one sampled column, or null if it holds too little. */
export function profileDerivations(levels: readonly ProfileLevel[]): ProfileDerivations | null {
  const peak = columnPeak(levels);
  const integral = verticalTecu(levels);
  if (!peak || !integral) return null;
  const foF2 = plasmaFrequencyMhz(peak.electronDensityM3);
  if (foF2 === null) return null;
  const rangeError = gnssRangeErrorM(integral.tecu);
  if (rangeError === null) return null;
  const used = levels.filter((level) => level.electronDensityM3 !== null);
  return {
    foF2Mhz: foF2,
    hmF2Km: peak.altitudeKm,
    verticalTecu: integral.tecu,
    gnssRangeErrorL1M: rangeError,
    integratedFromKm: used[0]!.altitudeKm,
    integratedToKm: used.at(-1)!.altitudeKm,
  };
}

export interface SampledProfile {
  latitudeDeg: number;
  longitudeDeg: number;
  levels: ProfileLevel[];
  derivations: ProfileDerivations | null;
  /** Frame times the column was interpolated between, for the validity row. */
  frames: { startValidAt: string; endValidAt: string; blend: number } | null;
  /** Why a column came back empty, in the sampler's own words. */
  unavailable: string | null;
}

/**
 * Samples the whole published column over one point.
 *
 * Takes a live `IonosphereSampler` rather than a bundle on purpose: the
 * sampler caches decoded frames, and building one per level would decode a
 * 62,100-point frame thirty times for a single click.
 *
 * Levels the model does not publish stay null. They are not interpolated
 * across and they are not dropped — a reader looking at the profile should be
 * able to see where the model has nothing, which is the same rule the surfaces
 * already follow.
 */
export function sampleProfile(
  sampler: IonosphereSampler,
  altitudesKm: readonly number[],
  input: { latitudeDeg: number; longitudeDeg: number; time: Date },
): SampledProfile {
  const levels: ProfileLevel[] = [];
  let frames: SampledProfile["frames"] = null;
  let unavailable: string | null = null;
  for (const altitudeKm of altitudesKm) {
    const result: IonosphereSampleResult = sampler.sample({
      latitudeDeg: input.latitudeDeg,
      longitudeDeg: input.longitudeDeg,
      altitudeKm,
      time: input.time,
    });
    if (result.status === "ok") {
      frames ??= result.frames;
      levels.push({
        altitudeKm,
        electronDensityM3: result.electronDensityM3,
        plasmaFrequencyMhz: plasmaFrequencyMhz(result.electronDensityM3),
      });
      continue;
    }
    // One reason for the whole column, and the first one wins: a click outside
    // the published time is outside it for every level, and repeating that
    // thirty times says nothing more than saying it once.
    unavailable ??= result.reason;
    levels.push({ altitudeKm, electronDensityM3: null, plasmaFrequencyMhz: null });
  }
  return {
    latitudeDeg: input.latitudeDeg,
    longitudeDeg: ((input.longitudeDeg % 360) + 360) % 360,
    levels,
    derivations: profileDerivations(levels),
    frames,
    unavailable: levels.some((level) => level.electronDensityM3 !== null) ? null : unavailable,
  };
}

/**
 * The sentence that has to travel with every number this file produces.
 *
 * WAM-IPE is a physics model run forward from an assimilated state, not a
 * sounding. foF2 from a real ionosonde is a measurement; foF2 from here is a
 * model's opinion about the same quantity, and the two are not interchangeable
 * for anything a planner would sign.
 */
export function profileEvidenceNote(): string {
  return "Derived from the NOAA WAM-IPE model column over this point — plasma physics applied to "
    + "modelled density, not an ionosonde sounding. No instrument measured any value shown here.";
}

/** What the MUF figure is and is not, shown wherever it is. */
export const MUF_LIMITATION = "Secant-law maximum usable frequency for a single hop of the stated "
  + "ground range, from the modelled F2 peak over the MIDPOINT of that path only. It assumes a flat "
  + "Earth and a level, untilted layer, so it overstates the usable frequency on long paths, and it "
  + "is not a propagation prediction: it says nothing about absorption, take-off angle, or whether "
  + "the path has enough power to close.";

/** What the TEC and range-error figures cover, shown wherever they are. */
export const COLUMN_LIMITATION = "Integrated over the model's published 90–2,655 km column only. "
  + "Plasmaspheric electrons above the top of that grid are real and are NOT counted here, so the "
  + "true TEC and range error over this point are both somewhat larger.";
