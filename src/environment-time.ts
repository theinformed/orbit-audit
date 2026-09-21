import type { TimeValue } from "./types";
import { magneticPressureNpa, shueBoundary } from "./magnetopause";

export { shueBoundary } from "./magnetopause";

export interface MagnetopauseDriverSample {
  validAt: string;
  observedAt: string;
  speedKps: number;
  densityCm3: number;
  bzGsmNt: number;
  dynamicPressureNpa: number;
  subsolarStandoffRe: number;
  flaringAlpha: number;
  /**
   * The rest of the upstream IMF vector, carried through the same
   * interpolation as Bz.
   *
   * Shue needs only `Pd` and `Bz`, which is why this sample used to stop
   * there. The cusped boundaries (Nguyen 2022, Lin 2010) additionally need the
   * IMF **clock angle** and the upstream **magnetic pressure**, so `By` and
   * `Bt` have to survive the walk from the published series to the renderer.
   * They are nullable because older artifacts published neither, and a boundary
   * model must never be handed a fabricated component: with these null the
   * scene falls back to Shue and says so.
   */
  byNt: number | null;
  btNt: number | null;
  /** `Bt^2 / 2 mu0`, recomputed from the interpolated `Bt`. */
  magneticPressureNpa: number | null;
}

type DriverPoint =
  Omit<MagnetopauseDriverSample, "subsolarStandoffRe" | "flaringAlpha" | "byNt" | "btNt" | "magneticPressureNpa">
  & {
    subsolarStandoffRe: number | null;
    flaringAlpha: number | null;
    byNt?: number | null;
    btNt?: number | null;
    magneticPressureNpa?: number | null;
  };

function bracketingIndices(times: number[], target: number, edgeToleranceMs = 0): [number, number] | null {
  if (times.length === 0) return null;
  if (target < times[0]!) return times[0]! - target <= edgeToleranceMs ? [0, 0] : null;
  if (target > times.at(-1)!) {
    const last = times.length - 1;
    return target - times[last]! <= edgeToleranceMs ? [last, last] : null;
  }
  let low = 0;
  let high = times.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (times[middle]! < target) low = middle + 1;
    else high = middle;
  }
  return [Math.max(0, low - 1), low];
}

export function sampleMagnetopauseDriver(
  series: DriverPoint[],
  at: Date,
  maximumGapMinutes = 20,
): MagnetopauseDriverSample | null {
  const target = at.getTime();
  const times = series.map((point) => Date.parse(point.validAt));
  const bracket = bracketingIndices(times, target);
  if (!bracket) return null;
  const [leftIndex, rightIndex] = bracket;
  const left = series[leftIndex];
  const right = series[rightIndex];
  if (!left || !right) return null;
  const leftTime = times[leftIndex]!;
  const rightTime = times[rightIndex]!;
  if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime) || rightTime - leftTime > maximumGapMinutes * 60_000) return null;
  const amount = rightTime === leftTime ? 0 : (target - leftTime) / (rightTime - leftTime);
  const interpolate = (a: number, b: number) => a + (b - a) * amount;
  const speedKps = interpolate(left.speedKps, right.speedKps);
  const densityCm3 = interpolate(left.densityCm3, right.densityCm3);
  const bzGsmNt = interpolate(left.bzGsmNt, right.bzGsmNt);
  const dynamicPressureNpa = 1.6726e-6 * densityCm3 * speedKps ** 2;
  const boundary = shueBoundary(dynamicPressureNpa, bzGsmNt);
  if (!boundary) return null;
  // A component is interpolated only when both ends actually published it. A
  // half-present pair would otherwise silently become the value of whichever
  // end happened to be non-null, which is a fabricated IMF component.
  const optional = (a: number | null | undefined, b: number | null | undefined) =>
    (typeof a === "number" && Number.isFinite(a) && typeof b === "number" && Number.isFinite(b)
      ? interpolate(a, b)
      : null);
  const byNt = optional(left.byNt, right.byNt);
  const btNt = optional(left.btNt, right.btNt);
  return {
    validAt: at.toISOString(),
    observedAt: amount < 0.5 ? left.observedAt : right.observedAt,
    speedKps,
    densityCm3,
    bzGsmNt,
    dynamicPressureNpa,
    byNt,
    btNt,
    // Recomputed from the interpolated magnitude rather than interpolated from
    // the two published pressures: Pm is quadratic in Bt, so interpolating it
    // linearly and interpolating Bt linearly are different numbers, and only
    // one of them is consistent with the Bt this sample reports.
    magneticPressureNpa: btNt === null ? null : magneticPressureNpa(btNt),
    ...boundary,
  };
}

export function sampleLogTimeValue(series: TimeValue[], at: Date, maximumGapMinutes = 15): number | null {
  const target = at.getTime();
  const times = series.map((point) => Date.parse(point.time));
  const bracket = bracketingIndices(times, target);
  if (!bracket) return null;
  const [leftIndex, rightIndex] = bracket;
  const left = series[leftIndex];
  const right = series[rightIndex];
  if (!left || !right) return null;
  if (left.value === null || right.value === null) return null;
  const leftTime = times[leftIndex]!;
  const rightTime = times[rightIndex]!;
  if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime) || rightTime - leftTime > maximumGapMinutes * 60_000) return null;
  const amount = rightTime === leftTime ? 0 : (target - leftTime) / (rightTime - leftTime);
  if (left.value <= 0 || right.value <= 0) return left.value + (right.value - left.value) * amount;
  const logarithm = Math.log10(left.value) + (Math.log10(right.value) - Math.log10(left.value)) * amount;
  return 10 ** logarithm;
}

export function goesXrayClass(fluxWm2: number | null): string {
  if (fluxWm2 === null || !Number.isFinite(fluxWm2) || fluxWm2 <= 0) return "—";
  const bands: Array<[string, number]> = [["X", 1e-4], ["M", 1e-5], ["C", 1e-6], ["B", 1e-7], ["A", 1e-8]];
  const [letter, threshold] = bands.find(([, minimum]) => fluxWm2 >= minimum) ?? ["A", 1e-8];
  return `${letter}${(fluxWm2 / threshold).toFixed(1)}`;
}
