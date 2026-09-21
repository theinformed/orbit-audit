import * as THREE from "three";
import { activeDistanceScale } from "./radial-ruler";
import type { IonosphereVolumeBundle } from "./types";

export type IonosphereSpatialMode = "smooth" | "native";

export const IONOSPHERE_RENDERING_LABELS: Record<IonosphereSpatialMode, string> = {
  smooth: "SMOOTH · CONTINUOUS DATA-DERIVED PEAK SURFACES",
  native: "NATIVE · REDUCED HORIZONTAL PEAK MESH",
};

export type IonosphereRegion = "e" | "f1" | "f2";

interface EncodedIonosphereSurface {
  altitudeU16: string;
  densityU8: string;
  validityBits: string;
  validColumnCount?: number;
}

interface IonospherePeakFrame extends EncodedIonosphereSurface {
  validAt: string;
  runAt: string;
  leadMinutes: number;
  phase: "history" | "forecast";
}

interface EnhancedIonosphereBundle extends IonosphereVolumeBundle {
  peakSurface?: {
    sourceProduct: string;
    sourceVariables: ["HmF2", "NmF2"];
    sourceCadenceMinutes: number;
    publishedCadenceMinutes: number;
    pointCount: number;
    altitudeEncoding: { scaleKm: number };
    frames: IonospherePeakFrame[];
  };
  profileRegionSurfaces?: {
    dRegion?: { available: false; reason: string };
  };
}

type EnhancedVolumeFrame = IonosphereVolumeBundle["frames"][number] & {
  regionSurfaces?: Partial<Record<"e" | "f1", EncodedIonosphereSurface>>;
};

interface DecodedSurface {
  altitudeKm: Float32Array;
  density: Uint8Array;
  validity: Uint8Array;
}

export interface IonosphereSurfaceRegionState {
  region: IonosphereRegion;
  source: "NOAA ipe05 HmF2/NmF2" | "derived from NOAA ipe10 3-D profile";
  validAt: { start: string; end: string; blend: number };
  supportedColumnPercent: number;
  altitudeRangeKm: [number, number] | null;
  densityRangeM3: [number, number] | null;
  /** Mean physical altitude (km) over supported columns; null when nothing is supported. */
  meanAltitudeKm: number | null;
  /**
   * Disclosure for the bounded display-only height exaggeration applied to
   * this region's rendered radius (see HEIGHT_EXAGGERATION_FACTOR/MAX_
   * SCENE_UNITS). Never affects altitudeRangeKm, densityRangeM3, or any
   * sampler output -- those remain true physical values.
   */
  displayExaggeration: { factor: number; maxSceneUnits: number };
  /** Isohypse spacing (km) drawn on this region's surface. */
  contourIntervalKm: number;
}

export interface IonosphereSurfaceState {
  requestedAt: string | null;
  regions: Record<IonosphereRegion, IonosphereSurfaceRegionState>;
  dRegion: {
    available: false;
    lowerBoundaryKm: 90;
    reason: string;
  };
}

export interface IonosphereFrameSelection {
  startIndex: number;
  endIndex: number;
  blend: number;
  state: "before" | "within" | "after";
}

export interface IonosphereSampleInput {
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
  time: Date;
}

export type IonosphereSampleResult =
  | {
      status: "ok";
      electronDensityM3: number;
      ionFractions: Record<string, number>;
      location: { latitudeDeg: number; longitudeDeg: number; altitudeKm: number };
      frames: { startValidAt: string; endValidAt: string; blend: number };
      method: "trilinear log-density plus linear temporal interpolation";
    }
  | {
      status: "outside-grid" | "outside-time" | "missing";
      reason: string;
    };

interface VolumeGrid {
  longitudesDeg: number[];
  latitudesDeg: number[];
  altitudesKm: number[];
  pointCount: number;
}

interface DecodedFrame {
  density: Uint8Array;
  validity: Uint8Array;
  composition?: Uint8Array;
}

interface SpatialSample {
  densityCode: number;
  ionFractions: number[];
}

interface AxisBracket {
  low: number;
  high: number;
  blend: number;
}

const bundleFrameTimes = new WeakMap<IonosphereVolumeBundle, number[]>();

function validatedFrameTimes(bundle: IonosphereVolumeBundle) {
  const cached = bundleFrameTimes.get(bundle);
  if (cached) return cached;
  if (bundle.frames.length === 0) throw new RangeError("WAM-IPE bundle has no frames");
  const times = bundle.frames.map((frame) => Date.parse(frame.validAt));
  if (times.some((value) => !Number.isFinite(value))) throw new RangeError("WAM-IPE bundle contains an invalid frame time");
  bundleFrameTimes.set(bundle, times);
  return times;
}

function decodeBytes(encoded: string, expectedCount: number, label: string) {
  const binary = globalThis.atob(encoded);
  if (binary.length !== expectedCount) {
    throw new RangeError(`WAM-IPE ${label} has ${binary.length} bytes; expected ${expectedCount}`);
  }
  const values = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) values[index] = binary.charCodeAt(index);
  return values;
}

export function decodeIonosphereDensity(encoded: string, expectedCount: number) {
  return decodeBytes(encoded, expectedCount, "density frame");
}

export function decodeIonosphereValidity(encoded: string, expectedCount: number) {
  const packed = decodeBytes(encoded, Math.ceil(expectedCount / 8), "validity mask");
  const values = new Uint8Array(expectedCount);
  for (let index = 0; index < expectedCount; index += 1) {
    values[index] = ((packed[index >> 3]! >> (index & 7)) & 1) === 1 ? 255 : 0;
  }
  return values;
}

export function decodeIonosphereComposition(
  encoded: string,
  pointCount: number,
  speciesCount: number,
) {
  return decodeBytes(encoded, pointCount * Math.ceil(speciesCount / 2), "ion-composition frame");
}

export function selectIonosphereFrames(bundle: IonosphereVolumeBundle, time: Date): IonosphereFrameSelection {
  const requested = time.getTime();
  if (!Number.isFinite(requested)) throw new RangeError("Ionosphere simulation time must be a valid Date");
  const times = validatedFrameTimes(bundle);
  if (requested < times[0]!) return { startIndex: 0, endIndex: 0, blend: 0, state: "before" };
  const lastIndex = times.length - 1;
  if (requested > times[lastIndex]!) {
    return { startIndex: lastIndex, endIndex: lastIndex, blend: 0, state: "after" };
  }
  if (requested === times[0]!) return { startIndex: 0, endIndex: 0, blend: 0, state: "within" };
  if (requested === times[lastIndex]!) {
    return { startIndex: lastIndex, endIndex: lastIndex, blend: 0, state: "within" };
  }

  let low = 0;
  let high = lastIndex;
  while (high - low > 1) {
    const middle = Math.floor((low + high) / 2);
    if (times[middle]! <= requested) low = middle;
    else high = middle;
  }
  if (requested === times[low]!) return { startIndex: low, endIndex: low, blend: 0, state: "within" };
  const span = times[high]! - times[low]!;
  return {
    startIndex: low,
    endIndex: high,
    blend: span > 0 ? THREE.MathUtils.clamp((requested - times[low]!) / span, 0, 1) : 0,
    state: "within",
  };
}

export function ionosphereDensityFromCode(bundle: IonosphereVolumeBundle, code: number) {
  const normalized = THREE.MathUtils.clamp(code, 0, 255) / 255;
  const exponent = THREE.MathUtils.lerp(
    bundle.electronDensity.minimum,
    bundle.electronDensity.maximum,
    normalized,
  );
  return 10 ** exponent;
}

/**
 * The ionosphere's own gentler compression (18 vs the shared ruler's 28 per
 * log-altitude, capped) keeps the D/E/F shells separable on the teaching
 * scale. On the true-distance scale that private curve would put a shell
 * ABOVE a satellite at the same physical altitude — exactly the mixed-scale
 * lie the scene-wide toggle forbids — so there the layer draws at k * true
 * radius like every other consumer, and the whole ionosphere honestly
 * collapses into a thin skin on the globe.
 */
export function ionosphereDisplayRadius(altitudeKm: number, earthSceneRadius = 100) {
  if (activeDistanceScale() === "true-distance") {
    return earthSceneRadius * (1 + Math.max(0, altitudeKm) / 6371);
  }
  return earthSceneRadius + Math.min(145, 18 * Math.log1p(Math.max(0, altitudeKm) / 350));
}

function validateGrid(grid: VolumeGrid) {
  const expectedCount = grid.altitudesKm.length * grid.latitudesDeg.length * grid.longitudesDeg.length;
  if (expectedCount !== grid.pointCount) throw new RangeError("WAM-IPE grid dimensions do not match its point count");
  for (const axis of [grid.longitudesDeg, grid.latitudesDeg, grid.altitudesKm]) {
    if (axis.length === 0 || axis.some((value, index) => !Number.isFinite(value) || (index > 0 && value <= axis[index - 1]!))) {
      throw new RangeError("WAM-IPE coordinates must be finite and strictly increasing");
    }
  }
}

function buildPositions(grid: VolumeGrid, earthSceneRadius = 100) {
  validateGrid(grid);
  const positions = new Float32Array(grid.pointCount * 3);
  const altitudes = new Float32Array(grid.pointCount);
  let outputIndex = 0;
  grid.altitudesKm.forEach((altitudeKm) => {
    const radius = ionosphereDisplayRadius(altitudeKm, earthSceneRadius);
    grid.latitudesDeg.forEach((latitudeDeg) => {
      const latitude = THREE.MathUtils.degToRad(latitudeDeg);
      const horizontal = radius * Math.cos(latitude);
      const y = radius * Math.sin(latitude);
      grid.longitudesDeg.forEach((longitudeDeg) => {
        const longitude = THREE.MathUtils.degToRad(longitudeDeg);
        positions[outputIndex * 3] = horizontal * Math.cos(longitude);
        positions[outputIndex * 3 + 1] = y;
        positions[outputIndex * 3 + 2] = -horizontal * Math.sin(longitude);
        altitudes[outputIndex] = altitudeKm;
        outputIndex += 1;
      });
    });
  });
  return { positions, altitudes };
}

export function buildIonospherePositions(bundle: IonosphereVolumeBundle, earthSceneRadius = 100) {
  if (bundle.grid.ordering !== "altitude-latitude-longitude") {
    throw new RangeError("WAM-IPE grid ordering is unsupported");
  }
  return buildPositions(bundle.grid, earthSceneRadius);
}

function linearAxis(values: number[], requested: number): AxisBracket | undefined {
  if (requested < values[0]! || requested > values.at(-1)!) return undefined;
  if (values.length === 1 || requested === values[0]!) return { low: 0, high: 0, blend: 0 };
  const last = values.length - 1;
  if (requested === values[last]!) return { low: last, high: last, blend: 0 };
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = Math.floor((low + high) / 2);
    if (values[middle]! <= requested) low = middle;
    else high = middle;
  }
  return { low, high, blend: (requested - values[low]!) / (values[high]! - values[low]!) };
}

function longitudeAxis(values: number[], requested: number): AxisBracket {
  if (!Number.isFinite(requested)) throw new RangeError("Ionosphere longitude must be finite");
  if (values.length === 1) return { low: 0, high: 0, blend: 0 };
  const first = values[0]!;
  const normalized = ((requested - first) % 360 + 360) % 360 + first;
  const lastIndex = values.length - 1;
  const last = values[lastIndex]!;
  if (normalized > last) {
    return { low: lastIndex, high: 0, blend: (normalized - last) / (first + 360 - last) };
  }
  return linearAxis(values, normalized)!;
}

function axisTerms(bracket: AxisBracket): Array<[number, number]> {
  if (bracket.low === bracket.high || bracket.blend <= 0) return [[bracket.low, 1]];
  if (bracket.blend >= 1) return [[bracket.high, 1]];
  return [[bracket.low, 1 - bracket.blend], [bracket.high, bracket.blend]];
}

function spatialSample(
  bundle: IonosphereVolumeBundle,
  frame: DecodedFrame,
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
): SpatialSample | "outside-grid" | "missing" {
  const latitude = linearAxis(bundle.grid.latitudesDeg, latitudeDeg);
  const altitude = linearAxis(bundle.grid.altitudesKm, altitudeKm);
  if (!latitude || !altitude) return "outside-grid";
  const longitude = longitudeAxis(bundle.grid.longitudesDeg, longitudeDeg);
  const longitudeCount = bundle.grid.longitudesDeg.length;
  const latitudeCount = bundle.grid.latitudesDeg.length;
  const speciesCount = bundle.ionComposition.species.length;
  const packedBytes = Math.ceil(speciesCount / 2);
  const ionFractions = new Array<number>(speciesCount).fill(0);
  let densityCode = 0;

  for (const [altitudeIndex, altitudeWeight] of axisTerms(altitude)) {
    for (const [latitudeIndex, latitudeWeight] of axisTerms(latitude)) {
      for (const [longitudeIndex, longitudeWeight] of axisTerms(longitude)) {
        const weight = altitudeWeight * latitudeWeight * longitudeWeight;
        if (weight <= 1e-12) continue;
        const pointIndex = (altitudeIndex * latitudeCount + latitudeIndex) * longitudeCount + longitudeIndex;
        if (frame.validity[pointIndex] !== 255) return "missing";
        densityCode += frame.density[pointIndex]! * weight;
        if (frame.composition) {
          const offset = pointIndex * packedBytes;
          const codes = new Array<number>(speciesCount);
          let codeSum = 0;
          for (let speciesIndex = 0; speciesIndex < speciesCount; speciesIndex += 1) {
            const packed = frame.composition[offset + (speciesIndex >> 1)]!;
            const code = (packed >> (4 * (speciesIndex & 1))) & 0x0f;
            codes[speciesIndex] = code;
            codeSum += code;
          }
          if (codeSum > 0) {
            for (let speciesIndex = 0; speciesIndex < speciesCount; speciesIndex += 1) {
              ionFractions[speciesIndex] = ionFractions[speciesIndex]! + (codes[speciesIndex]! / codeSum) * weight;
            }
          }
        }
      }
    }
  }
  return { densityCode, ionFractions };
}

function normalizeFractions(values: number[]) {
  const total = values.reduce((sum, value) => sum + value, 0);
  return total > 0 ? values.map((value) => value / total) : values;
}

export class IonosphereSampler {
  private readonly decodedFrames = new Map<number, DecodedFrame>();

  constructor(private readonly bundle: IonosphereVolumeBundle) {
    validateGrid(bundle.grid);
  }

  private frame(index: number) {
    const cached = this.decodedFrames.get(index);
    if (cached) return cached;
    const source = this.bundle.frames[index];
    if (!source) throw new RangeError(`WAM-IPE frame ${index} is unavailable`);
    const decoded = {
      density: decodeIonosphereDensity(source.densityU8, this.bundle.grid.pointCount),
      validity: decodeIonosphereValidity(source.validityBits, this.bundle.grid.pointCount),
      composition: decodeIonosphereComposition(
        source.compositionU4,
        this.bundle.grid.pointCount,
        this.bundle.ionComposition.species.length,
      ),
    };
    this.decodedFrames.set(index, decoded);
    return decoded;
  }

  sample(input: IonosphereSampleInput): IonosphereSampleResult {
    if (![input.latitudeDeg, input.longitudeDeg, input.altitudeKm].every(Number.isFinite)) {
      return { status: "outside-grid", reason: "Satellite coordinates must be finite." };
    }
    const selection = selectIonosphereFrames(this.bundle, input.time);
    if (selection.state !== "within") {
      return { status: "outside-time", reason: "Requested time is outside the published WAM-IPE sequence." };
    }
    const start = spatialSample(
      this.bundle,
      this.frame(selection.startIndex),
      input.latitudeDeg,
      input.longitudeDeg,
      input.altitudeKm,
    );
    if (start === "outside-grid") {
      return {
        status: "outside-grid",
        reason: `Requested location is outside the published ${this.bundle.grid.altitudesKm[0]}–${this.bundle.grid.altitudesKm.at(-1)} km WAM-IPE grid.`,
      };
    }
    if (start === "missing") return { status: "missing", reason: "A contributing WAM-IPE source cell is missing." };
    let densityCode = start.densityCode;
    let ionFractions = start.ionFractions;
    if (selection.endIndex !== selection.startIndex && selection.blend > 0) {
      const end = spatialSample(
        this.bundle,
        this.frame(selection.endIndex),
        input.latitudeDeg,
        input.longitudeDeg,
        input.altitudeKm,
      );
      if (end === "outside-grid") return { status: "outside-grid", reason: "Requested location is outside the model grid." };
      if (end === "missing") return { status: "missing", reason: "A contributing WAM-IPE source cell is missing." };
      densityCode = THREE.MathUtils.lerp(start.densityCode, end.densityCode, selection.blend);
      ionFractions = start.ionFractions.map((value, index) =>
        THREE.MathUtils.lerp(value, end.ionFractions[index]!, selection.blend),
      );
    }
    ionFractions = normalizeFractions(ionFractions);
    return {
      status: "ok",
      electronDensityM3: ionosphereDensityFromCode(this.bundle, densityCode),
      ionFractions: Object.fromEntries(
        this.bundle.ionComposition.species.map((species, index) => [species, ionFractions[index] ?? 0]),
      ),
      location: {
        latitudeDeg: input.latitudeDeg,
        longitudeDeg: ((input.longitudeDeg % 360) + 360) % 360,
        altitudeKm: input.altitudeKm,
      },
      frames: {
        startValidAt: this.bundle.frames[selection.startIndex]!.validAt,
        endValidAt: this.bundle.frames[selection.endIndex]!.validAt,
        blend: selection.blend,
      },
      method: "trilinear log-density plus linear temporal interpolation",
    };
  }
}

export function sampleIonosphereAt(bundle: IonosphereVolumeBundle, input: IonosphereSampleInput) {
  return new IonosphereSampler(bundle).sample(input);
}

export interface IonospherePeakSampleInput {
  latitudeDeg: number;
  longitudeDeg: number;
  time: Date;
}

export type IonospherePeakSampleResult =
  | {
      status: "ok";
      region: IonosphereRegion;
      altitudeKm: number;
      electronDensityM3: number;
      source: IonosphereSurfaceRegionState["source"];
      frames: { startValidAt: string; endValidAt: string; blend: number };
    }
  | {
      status: "outside-grid" | "outside-time" | "unsupported";
      region: IonosphereRegion;
      reason: string;
    };

/**
 * Samples a region's peak height/density surface (the same data the F2/E/F1
 * meshes are built from) at a lat/lon/time, independent of any rendered
 * layer. Intended for building an orbit-vs-HmF2 strip chart: combine this
 * with `IonosphereSampler`/`sampleIonosphereAt` (electron density at the
 * satellite's actual altitude) to get both curves along a ground track.
 * Caches decoded surfaces per source frame, so repeated calls along one
 * orbit pass (typically hitting the same one or two bracketing frames) are
 * cheap. Unsupported columns (no distinct peak in that frame) report
 * "unsupported" rather than inventing a height -- holes stay holes here too.
 */
export class IonospherePeakSampler {
  private readonly nativeFrames = new Map<number, DecodedFrame>();
  private readonly profileSurfaces = new Map<string, DecodedSurface>();
  private readonly peakSurfaces = new Map<number, DecodedSurface>();

  constructor(private readonly bundle: IonosphereVolumeBundle) {
    validateGrid(bundle.grid);
  }

  private nativeFrame(index: number) {
    const cached = this.nativeFrames.get(index);
    if (cached) return cached;
    const source = this.bundle.frames[index];
    if (!source) throw new RangeError(`WAM-IPE frame ${index} is unavailable`);
    const decoded = {
      density: decodeIonosphereDensity(source.densityU8, this.bundle.grid.pointCount),
      validity: decodeIonosphereValidity(source.validityBits, this.bundle.grid.pointCount),
    };
    this.nativeFrames.set(index, decoded);
    return decoded;
  }

  private profileSurface(index: number, region: IonosphereRegion) {
    const key = `${region}:${index}`;
    const cached = this.profileSurfaces.get(key);
    if (cached) return cached;
    const frame = this.bundle.frames[index] as EnhancedVolumeFrame | undefined;
    if (!frame) throw new RangeError(`WAM-IPE frame ${index} is unavailable`);
    const encoded = region === "f2" ? undefined : frame.regionSurfaces?.[region];
    const pointCount = this.bundle.grid.longitudesDeg.length * this.bundle.grid.latitudesDeg.length;
    const surface = encoded
      ? {
          altitudeKm: decodeSurfaceAltitude(encoded.altitudeU16, pointCount, 0.1),
          density: decodeIonosphereDensity(encoded.densityU8, pointCount),
          validity: decodeIonosphereValidity(encoded.validityBits, pointCount),
        }
      : deriveProfileSurface(this.bundle, this.nativeFrame(index), region);
    this.profileSurfaces.set(key, surface);
    return surface;
  }

  private peakSurface(index: number) {
    const cached = this.peakSurfaces.get(index);
    if (cached) return cached;
    const peak = (this.bundle as EnhancedIonosphereBundle).peakSurface;
    const frame = peak?.frames[index];
    if (!peak || !frame) throw new RangeError(`WAM-IPE HmF2/NmF2 frame ${index} is unavailable`);
    const pointCount = this.bundle.grid.longitudesDeg.length * this.bundle.grid.latitudesDeg.length;
    if (peak.pointCount !== pointCount) throw new RangeError("WAM-IPE HmF2/NmF2 grid does not match the 3-D profile grid");
    const surface = {
      altitudeKm: decodeSurfaceAltitude(frame.altitudeU16, pointCount, peak.altitudeEncoding.scaleKm),
      density: decodeIonosphereDensity(frame.densityU8, pointCount),
      validity: decodeIonosphereValidity(frame.validityBits, pointCount),
    };
    this.peakSurfaces.set(index, surface);
    return surface;
  }

  private bilinearSurfaceSample(surface: DecodedSurface, latitude: AxisBracket, longitude: AxisBracket) {
    const width = this.bundle.grid.longitudesDeg.length;
    let altitudeValue = 0;
    let densityValue = 0;
    for (const [latitudeIndex, latitudeWeight] of axisTerms(latitude)) {
      for (const [longitudeIndex, longitudeWeight] of axisTerms(longitude)) {
        const weight = latitudeWeight * longitudeWeight;
        if (weight <= 1e-12) continue;
        const index = latitudeIndex * width + longitudeIndex;
        if (surface.validity[index] !== 255) return undefined;
        altitudeValue += surface.altitudeKm[index]! * weight;
        densityValue += surface.density[index]! * weight;
      }
    }
    return { altitudeKm: altitudeValue, densityCode: densityValue };
  }

  sample(region: IonosphereRegion, input: IonospherePeakSampleInput): IonospherePeakSampleResult {
    if (![input.latitudeDeg, input.longitudeDeg].every(Number.isFinite)) {
      return { status: "outside-grid", region, reason: "Satellite coordinates must be finite." };
    }
    const latitude = linearAxis(this.bundle.grid.latitudesDeg, input.latitudeDeg);
    if (!latitude) {
      return {
        status: "outside-grid",
        region,
        reason: `Requested latitude is outside the published ${this.bundle.grid.latitudesDeg[0]}–${this.bundle.grid.latitudesDeg.at(-1)}° WAM-IPE grid.`,
      };
    }
    const longitude = longitudeAxis(this.bundle.grid.longitudesDeg, input.longitudeDeg);

    const peak = (this.bundle as EnhancedIonosphereBundle).peakSurface;
    const usePeak = region === "f2" && !!peak?.frames.length;
    const selection = usePeak
      ? selectTimedSurfaceFrames(peak!.frames, input.time)
      : selectIonosphereFrames(this.bundle, input.time);
    if (selection.state !== "within") {
      return { status: "outside-time", region, reason: "Requested time is outside the published WAM-IPE sequence." };
    }

    const start = usePeak ? this.peakSurface(selection.startIndex) : this.profileSurface(selection.startIndex, region);
    const startSample = this.bilinearSurfaceSample(start, latitude, longitude);
    if (!startSample) {
      return { status: "unsupported", region, reason: "That column has no distinct peak in this WAM-IPE frame." };
    }
    let altitudeKm = startSample.altitudeKm;
    let densityCode = startSample.densityCode;
    if (selection.endIndex !== selection.startIndex && selection.blend > 0) {
      const end = usePeak ? this.peakSurface(selection.endIndex) : this.profileSurface(selection.endIndex, region);
      const endSample = this.bilinearSurfaceSample(end, latitude, longitude);
      if (!endSample) {
        return { status: "unsupported", region, reason: "That column has no distinct peak in the bracketing WAM-IPE frame." };
      }
      altitudeKm = THREE.MathUtils.lerp(altitudeKm, endSample.altitudeKm, selection.blend);
      densityCode = THREE.MathUtils.lerp(densityCode, endSample.densityCode, selection.blend);
    }
    const frames = usePeak ? peak!.frames : this.bundle.frames;
    return {
      status: "ok",
      region,
      altitudeKm,
      electronDensityM3: ionosphereDensityFromCode(this.bundle, densityCode),
      source: usePeak ? "NOAA ipe05 HmF2/NmF2" : "derived from NOAA ipe10 3-D profile",
      frames: {
        startValidAt: frames[selection.startIndex]!.validAt,
        endValidAt: frames[selection.endIndex]!.validAt,
        blend: selection.blend,
      },
    };
  }
}

export function sampleIonospherePeakHeight(
  bundle: IonosphereVolumeBundle,
  region: IonosphereRegion,
  input: IonospherePeakSampleInput,
) {
  return new IonospherePeakSampler(bundle).sample(region, input);
}

function linspace(start: number, end: number, count: number, includeEnd = true) {
  if (count <= 1) return [start];
  const divisor = includeEnd ? count - 1 : count;
  return Array.from({ length: count }, (_, index) => start + ((end - start) * index) / divisor);
}

export function buildSmoothIonosphereGrid(bundle: IonosphereVolumeBundle): VolumeGrid {
  const longitudeCount = Math.max(bundle.grid.longitudesDeg.length, Math.min(72, Math.ceil(bundle.grid.longitudesDeg.length * 1.6)));
  const latitudeCount = bundle.grid.latitudesDeg.length === 1
    ? 1
    : Math.max(bundle.grid.latitudesDeg.length, Math.min(61, Math.ceil(bundle.grid.latitudesDeg.length * 1.35)));
  const altitudeCount = bundle.grid.altitudesKm.length === 1
    ? 1
    : Math.max(bundle.grid.altitudesKm.length, Math.min(45, Math.ceil(bundle.grid.altitudesKm.length * 1.5)));
  const longitudeStart = bundle.grid.longitudesDeg[0]!;
  const altitudeStart = bundle.grid.altitudesKm[0]!;
  const altitudeEnd = bundle.grid.altitudesKm.at(-1)!;
  const altitudesKm = linspace(Math.log(altitudeStart), Math.log(altitudeEnd), altitudeCount).map(Math.exp);
  const grid = {
    longitudesDeg: linspace(longitudeStart, longitudeStart + 360, longitudeCount, false),
    latitudesDeg: linspace(bundle.grid.latitudesDeg[0]!, bundle.grid.latitudesDeg.at(-1)!, latitudeCount),
    altitudesKm,
    pointCount: longitudeCount * latitudeCount * altitudeCount,
  };
  validateGrid(grid);
  return grid;
}

function interpolateDensityCode(
  density: Uint8Array,
  validity: Uint8Array,
  longitudeCount: number,
  latitudeCount: number,
  longitude: AxisBracket,
  latitude: AxisBracket,
  altitude: AxisBracket,
) {
  const altitudeTerms = altitude.low === altitude.high ? 1 : 2;
  const latitudeTerms = latitude.low === latitude.high ? 1 : 2;
  const longitudeTerms = longitude.low === longitude.high ? 1 : 2;
  let densityCode = 0;
  for (let altitudeTerm = 0; altitudeTerm < altitudeTerms; altitudeTerm += 1) {
    const altitudeIndex = altitudeTerm === 0 ? altitude.low : altitude.high;
    const altitudeWeight = altitudeTerms === 1 ? 1 : altitudeTerm === 0 ? 1 - altitude.blend : altitude.blend;
    for (let latitudeTerm = 0; latitudeTerm < latitudeTerms; latitudeTerm += 1) {
      const latitudeIndex = latitudeTerm === 0 ? latitude.low : latitude.high;
      const latitudeWeight = latitudeTerms === 1 ? 1 : latitudeTerm === 0 ? 1 - latitude.blend : latitude.blend;
      for (let longitudeTerm = 0; longitudeTerm < longitudeTerms; longitudeTerm += 1) {
        const longitudeIndex = longitudeTerm === 0 ? longitude.low : longitude.high;
        const longitudeWeight = longitudeTerms === 1 ? 1 : longitudeTerm === 0 ? 1 - longitude.blend : longitude.blend;
        const weight = altitudeWeight * latitudeWeight * longitudeWeight;
        if (weight <= 1e-12) continue;
        const pointIndex = (altitudeIndex * latitudeCount + latitudeIndex) * longitudeCount + longitudeIndex;
        if (validity[pointIndex] !== 255) return undefined;
        densityCode += density[pointIndex]! * weight;
      }
    }
  }
  return densityCode;
}

export function resampleIonosphereFrame(
  bundle: IonosphereVolumeBundle,
  density: Uint8Array,
  validity: Uint8Array,
  target = buildSmoothIonosphereGrid(bundle),
) {
  if (density.length !== bundle.grid.pointCount || validity.length !== bundle.grid.pointCount) {
    throw new RangeError("WAM-IPE source frame does not match its native grid");
  }
  const outputDensity = new Uint8Array(target.pointCount);
  const outputValidity = new Uint8Array(target.pointCount);
  const longitudes = target.longitudesDeg.map((value) => longitudeAxis(bundle.grid.longitudesDeg, value));
  const latitudes = target.latitudesDeg.map((value) => linearAxis(bundle.grid.latitudesDeg, value));
  const altitudes = target.altitudesKm.map((value) => linearAxis(bundle.grid.altitudesKm, value));
  const longitudeCount = bundle.grid.longitudesDeg.length;
  const latitudeCount = bundle.grid.latitudesDeg.length;
  let outputIndex = 0;
  for (const altitude of altitudes) {
    for (const latitude of latitudes) {
      for (const longitude of longitudes) {
        if (altitude && latitude) {
          const sampled = interpolateDensityCode(
            density,
            validity,
            longitudeCount,
            latitudeCount,
            longitude,
            latitude,
            altitude,
          );
          if (sampled !== undefined) {
            outputDensity[outputIndex] = Math.round(THREE.MathUtils.clamp(sampled, 0, 255));
            outputValidity[outputIndex] = 255;
          }
        }
        outputIndex += 1;
      }
    }
  }
  return { density: outputDensity, validity: outputValidity, grid: target };
}

interface SurfaceGrid {
  longitudesDeg: number[];
  latitudesDeg: number[];
  pointCount: number;
}

// Peak surfaces are context layers, not opaque atmospheric shells, so they
// still brighten toward the limb where physical height is most legible.
// Sean rejected an earlier version of this tradeoff that made the map-facing
// portion nearly invisible (2026-08, "don't really show up except... around
// the edges"): the face-on floor below, plus gradient-based relief shading
// and physical-height contour lines, are the fix. The Earth stays legible
// through transparency and the density-driven color ramp, not through
// starving the face-on view of opacity.
const REGION_OPACITY: Record<IonosphereRegion, number> = { e: 0.26, f1: 0.18, f2: 0.32 };

// Face-on opacity floor. The fragment shader multiplies opacityScale by
// mix(FACE_ON_OPACITY_FLOOR, 1.0, limb), so limb=0 (looking straight down at
// the surface) now renders at 85% of a region's base opacity instead of 12%.
// A first pass at 45% was tuned against face-on screenshots and was still too
// faint over lower-density (darker-colored) columns to read as structure, so
// it was raised further: 85% still leaves a visible (if modest) brightening
// toward the limb via the `limb` mix below, while making density/relief/
// contour structure legible face-on without the surface becoming an opaque
// shell that hides the globe under it.
const FACE_ON_OPACITY_FLOOR = 0.85;

// Hillshade-style relief shading, derived purely from the surface's own
// height field (finite difference between horizontal neighbors), NOT from
// any new data source. It is a rendering cue only -- see RELIEF_SHADE_MIN/
// MAX_MULTIPLIER below -- and never changes the color ramp's density
// encoding or the physical altitude/density values reported in state.
const RELIEF_LIGHT_DIRECTION = { longitude: -0.7, latitude: 0.7 } as const;
// Neighbor-to-neighbor height difference (km) that fully saturates the
// shading cue. Smaller = more contrast for subtle undulation.
const RELIEF_GRADIENT_SATURATION_KM = 6;
const RELIEF_SHADE_MIN_MULTIPLIER = 0.78;
const RELIEF_SHADE_MAX_MULTIPLIER = 1.22;

// Physical-height exaggeration (isohypse relief). HmF2 varies roughly
// 250-350 km, which the scene's logarithmic display radius compresses to a
// few scene units -- nearly invisible. We exaggerate each vertex's *natural*
// log-radius deviation from its surface's own mean altitude by this factor,
// clamped to a bounded number of scene units so the undulation can never
// cross into a neighboring shell or dip into the solid Earth. This changes
// ONLY the rendered radius: altitudeKm attributes, state ranges, and the
// satellite sampler all keep reporting unexaggerated physical kilometres.
// Disclosed to the UI via IonosphereSurfaceRegionState.displayExaggeration.
const HEIGHT_EXAGGERATION_FACTOR = 8;
const HEIGHT_EXAGGERATION_MAX_SCENE_UNITS = 4;

// Isohypse (constant-height contour) spacing, exactly like geopotential-
// height contours on a weather map. F2 is given a coarser interval because
// its published height range is wider than E/F1's. Disclosed to the UI via
// IonosphereSurfaceRegionState.contourIntervalKm.
const CONTOUR_INTERVAL_KM: Record<IonosphereRegion, number> = { e: 5, f1: 5, f2: 20 };
const CONTOUR_LINE_COLOR = { r: 0.02, g: 0.04, b: 0.08 };
const CONTOUR_LINE_HALF_WIDTH_PX = 1.1;

function decodeSurfaceAltitude(encoded: string, expectedCount: number, scaleKm: number) {
  const bytes = decodeBytes(encoded, expectedCount * 2, "surface altitude");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const values = new Float32Array(expectedCount);
  for (let index = 0; index < expectedCount; index += 1) {
    values[index] = view.getUint16(index * 2, true) * scaleKm;
  }
  return values;
}

function selectTimedSurfaceFrames(
  frames: ReadonlyArray<{ validAt: string }>,
  time: Date,
): IonosphereFrameSelection {
  if (frames.length === 0) throw new RangeError("WAM-IPE peak surface has no frames");
  const requested = time.getTime();
  if (!Number.isFinite(requested)) throw new RangeError("Ionosphere simulation time must be a valid Date");
  const times = frames.map((frame) => Date.parse(frame.validAt));
  if (times.some((value) => !Number.isFinite(value))) throw new RangeError("WAM-IPE peak surface has an invalid frame time");
  if (requested < times[0]!) return { startIndex: 0, endIndex: 0, blend: 0, state: "before" };
  const last = times.length - 1;
  if (requested > times[last]!) return { startIndex: last, endIndex: last, blend: 0, state: "after" };
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = Math.floor((low + high) / 2);
    if (times[middle]! <= requested) low = middle;
    else high = middle;
  }
  if (requested === times[low]! || low === high) return { startIndex: low, endIndex: low, blend: 0, state: "within" };
  if (requested === times[high]!) return { startIndex: high, endIndex: high, blend: 0, state: "within" };
  return {
    startIndex: low,
    endIndex: high,
    blend: (requested - times[low]!) / (times[high]! - times[low]!),
    state: "within",
  };
}

function surfaceGrid(bundle: IonosphereVolumeBundle, mode: IonosphereSpatialMode): SurfaceGrid {
  if (mode === "native") {
    return {
      longitudesDeg: bundle.grid.longitudesDeg,
      latitudesDeg: bundle.grid.latitudesDeg,
      pointCount: bundle.grid.longitudesDeg.length * bundle.grid.latitudesDeg.length,
    };
  }
  const longitudeCount = Math.max(bundle.grid.longitudesDeg.length, Math.min(72, bundle.grid.longitudesDeg.length * 2));
  const latitudeCount = bundle.grid.latitudesDeg.length === 1
    ? 1
    : Math.max(bundle.grid.latitudesDeg.length, Math.min(61, bundle.grid.latitudesDeg.length * 2 - 1));
  return {
    longitudesDeg: linspace(bundle.grid.longitudesDeg[0]!, bundle.grid.longitudesDeg[0]! + 360, longitudeCount, false),
    latitudesDeg: linspace(bundle.grid.latitudesDeg[0]!, bundle.grid.latitudesDeg.at(-1)!, latitudeCount),
    pointCount: longitudeCount * latitudeCount,
  };
}

function profilePeakIndex(
  density: Uint8Array,
  validity: Uint8Array,
  altitudeIndices: number[],
  latitudeIndex: number,
  longitudeIndex: number,
  latitudeCount: number,
  longitudeCount: number,
  maximumAltitudeKm: number | undefined,
  altitudesKm: number[],
) {
  const valueAt = (altitudeIndex: number) => {
    const point = (altitudeIndex * latitudeCount + latitudeIndex) * longitudeCount + longitudeIndex;
    return validity[point] === 255 ? density[point]! : undefined;
  };
  const candidates: Array<[number, number]> = [];
  for (let position = 1; position < altitudeIndices.length - 1; position += 1) {
    const index = altitudeIndices[position]!;
    if (maximumAltitudeKm !== undefined && altitudesKm[index]! >= maximumAltitudeKm) continue;
    const value = valueAt(index);
    const previous = valueAt(altitudeIndices[position - 1]!);
    const next = valueAt(altitudeIndices[position + 1]!);
    if (value === undefined || previous === undefined || next === undefined || value < previous || value < next) continue;
    if (value === previous && value === next) continue;
    let leftMinimum = 255;
    let rightMinimum = 255;
    for (let offset = 0; offset < position; offset += 1) {
      const candidate = valueAt(altitudeIndices[offset]!);
      if (candidate === undefined) { leftMinimum = 256; break; }
      leftMinimum = Math.min(leftMinimum, candidate);
    }
    for (let offset = position + 1; offset < altitudeIndices.length; offset += 1) {
      const candidate = valueAt(altitudeIndices[offset]!);
      if (candidate === undefined) { rightMinimum = 256; break; }
      rightMinimum = Math.min(rightMinimum, candidate);
    }
    if (value - Math.max(leftMinimum, rightMinimum) >= 1) candidates.push([value, index]);
  }
  candidates.sort((left, right) => right[0] - left[0]);
  return candidates[0]?.[1];
}

function deriveProfileSurface(
  bundle: IonosphereVolumeBundle,
  frame: DecodedFrame,
  region: IonosphereRegion,
): DecodedSurface {
  const longitudeCount = bundle.grid.longitudesDeg.length;
  const latitudeCount = bundle.grid.latitudesDeg.length;
  const pointCount = longitudeCount * latitudeCount;
  const altitudeKm = new Float32Array(pointCount);
  const density = new Uint8Array(pointCount);
  const validity = new Uint8Array(pointCount);
  const regionIndices = bundle.grid.altitudesKm
    .map((altitude, index) => ({ altitude, index }))
    .filter(({ altitude }) => region === "e"
      ? altitude >= 90 && altitude <= 170
      : region === "f1"
        ? altitude >= 160 && altitude <= 230
        : altitude >= 160 && altitude <= 1000)
    .map(({ index }) => index);
  const fIndices = bundle.grid.altitudesKm
    .map((altitude, index) => ({ altitude, index }))
    .filter(({ altitude }) => altitude >= 160 && altitude <= 1000)
    .map(({ index }) => index);

  for (let latitudeIndex = 0; latitudeIndex < latitudeCount; latitudeIndex += 1) {
    for (let longitudeIndex = 0; longitudeIndex < longitudeCount; longitudeIndex += 1) {
      const output = latitudeIndex * longitudeCount + longitudeIndex;
      const valueAt = (altitudeIndex: number) => {
        const point = (altitudeIndex * latitudeCount + latitudeIndex) * longitudeCount + longitudeIndex;
        return frame.validity[point] === 255 ? frame.density[point]! : undefined;
      };
      let selected: number | undefined;
      if (region === "f2") {
        const candidates = fIndices
          .map((index) => ({ index, value: valueAt(index) }))
          .filter((item): item is { index: number; value: number } => item.value !== undefined);
        if (candidates.length !== fIndices.length || candidates.length < 3) continue;
        const maximum = candidates.reduce((best, item) => item.value > best.value ? item : best);
        const position = fIndices.indexOf(maximum.index);
        if (position > 0 && position < fIndices.length - 1) selected = maximum.index;
      } else if (region === "e") {
        // A distinct E-layer local maximum is not present in every modeled
        // column.  The strongest supported value inside the published E band
        // is still a useful data-derived height/density surface and avoids a
        // checkerboard of artificial holes.  F1 remains conservative: it is
        // shown only when the 3-D profile contains a distinct secondary peak.
        const candidates = regionIndices
          .map((index) => ({ index, value: valueAt(index) }))
          .filter((item): item is { index: number; value: number } => item.value !== undefined);
        if (candidates.length === regionIndices.length && candidates.length > 0) {
          selected = candidates.reduce((best, item) => item.value > best.value ? item : best).index;
        }
      } else {
        let maximumAltitude: number | undefined;
        if (region === "f1") {
          const fCandidates = fIndices
            .map((index) => ({ index, value: valueAt(index) }))
            .filter((item): item is { index: number; value: number } => item.value !== undefined);
          if (fCandidates.length !== fIndices.length || fCandidates.length < 3) continue;
          const f2 = fCandidates.reduce((best, item) => item.value > best.value ? item : best);
          maximumAltitude = bundle.grid.altitudesKm[f2.index]! - 10;
        }
        selected = profilePeakIndex(
          frame.density,
          frame.validity,
          regionIndices,
          latitudeIndex,
          longitudeIndex,
          latitudeCount,
          longitudeCount,
          maximumAltitude,
          bundle.grid.altitudesKm,
        );
      }
      if (selected === undefined) continue;
      const sourcePoint = (selected * latitudeCount + latitudeIndex) * longitudeCount + longitudeIndex;
      altitudeKm[output] = bundle.grid.altitudesKm[selected]!;
      density[output] = frame.density[sourcePoint]!;
      validity[output] = 255;
    }
  }
  return { altitudeKm, density, validity };
}

function resampleSurface(
  bundle: IonosphereVolumeBundle,
  source: DecodedSurface,
  target: SurfaceGrid,
): DecodedSurface {
  const sourceWidth = bundle.grid.longitudesDeg.length;
  const sourceHeight = bundle.grid.latitudesDeg.length;
  const expected = sourceWidth * sourceHeight;
  if (source.altitudeKm.length !== expected || source.density.length !== expected || source.validity.length !== expected) {
    throw new RangeError("WAM-IPE peak surface does not match its horizontal grid");
  }
  if (target.longitudesDeg === bundle.grid.longitudesDeg && target.latitudesDeg === bundle.grid.latitudesDeg) return source;
  const altitudeKm = new Float32Array(target.pointCount);
  const density = new Uint8Array(target.pointCount);
  const validity = new Uint8Array(target.pointCount);
  let output = 0;
  for (const latitudeDeg of target.latitudesDeg) {
    const latitude = linearAxis(bundle.grid.latitudesDeg, latitudeDeg);
    for (const longitudeDeg of target.longitudesDeg) {
      const longitude = longitudeAxis(bundle.grid.longitudesDeg, longitudeDeg);
      if (latitude) {
        let altitudeValue = 0;
        let densityValue = 0;
        let supported = true;
        for (const [latitudeIndex, latitudeWeight] of axisTerms(latitude)) {
          for (const [longitudeIndex, longitudeWeight] of axisTerms(longitude)) {
            const weight = latitudeWeight * longitudeWeight;
            if (weight <= 1e-12) continue;
            const sourceIndex = latitudeIndex * sourceWidth + longitudeIndex;
            if (source.validity[sourceIndex] !== 255) { supported = false; break; }
            altitudeValue += source.altitudeKm[sourceIndex]! * weight;
            densityValue += source.density[sourceIndex]! * weight;
          }
          if (!supported) break;
        }
        if (supported) {
          altitudeKm[output] = altitudeValue;
          density[output] = Math.round(THREE.MathUtils.clamp(densityValue, 0, 255));
          validity[output] = 255;
        }
      }
      output += 1;
    }
  }
  return { altitudeKm, density, validity };
}

function smoothSurfaceForDisplay(source: DecodedSurface, grid: SurfaceGrid, passes = 3): DecodedSurface {
  const width = grid.longitudesDeg.length;
  const height = grid.latitudesDeg.length;
  let altitudeKm = Float32Array.from(source.altitudeKm);
  let density = Uint8Array.from(source.density);
  const validity = Uint8Array.from(source.validity);
  const kernel = [1, 2, 1] as const;
  for (let pass = 0; pass < passes; pass += 1) {
    const nextAltitude = Float32Array.from(altitudeKm);
    const nextDensity = Uint8Array.from(density);
    for (let row = 0; row < height; row += 1) {
      for (let column = 0; column < width; column += 1) {
        const center = row * width + column;
        if (validity[center] !== 255) continue;
        let altitudeTotal = 0;
        let densityTotal = 0;
        let weightTotal = 0;
        for (let rowOffset = -1; rowOffset <= 1; rowOffset += 1) {
          const neighborRow = THREE.MathUtils.clamp(row + rowOffset, 0, height - 1);
          for (let columnOffset = -1; columnOffset <= 1; columnOffset += 1) {
            const neighborColumn = (column + columnOffset + width) % width;
            const neighbor = neighborRow * width + neighborColumn;
            if (validity[neighbor] !== 255) continue;
            const weight = kernel[rowOffset + 1]! * kernel[columnOffset + 1]!;
            altitudeTotal += altitudeKm[neighbor]! * weight;
            densityTotal += density[neighbor]! * weight;
            weightTotal += weight;
          }
        }
        if (weightTotal > 0) {
          nextAltitude[center] = altitudeTotal / weightTotal;
          nextDensity[center] = Math.round(densityTotal / weightTotal);
        }
      }
    }
    altitudeKm = nextAltitude;
    density = nextDensity;
  }
  return { altitudeKm, density, validity };
}

/** Mean altitude over columns with a supported peak, or undefined if none. */
function meanValidAltitudeKm(surface: DecodedSurface): number | undefined {
  let total = 0;
  let count = 0;
  for (let index = 0; index < surface.validity.length; index += 1) {
    if (surface.validity[index] !== 255) continue;
    total += surface.altitudeKm[index]!;
    count += 1;
  }
  return count > 0 ? total / count : undefined;
}

/**
 * Bounded hillshade cue from the surface's own height field: a finite
 * difference between horizontal neighbors, lit from a fixed synthetic
 * direction. 0.5 is flat/neutral; values push toward 0 or 1 with slope.
 * Purely illustrative rendering -- see RELIEF_* constants above.
 */
function computeReliefShade(grid: SurfaceGrid, altitudeKm: Float32Array, validity: Uint8Array): Float32Array {
  const width = grid.longitudesDeg.length;
  const height = grid.latitudesDeg.length;
  const shade = new Float32Array(width * height).fill(0.5);
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      const index = row * width + column;
      if (validity[index] !== 255) continue;
      const leftIndex = row * width + ((column - 1 + width) % width);
      const rightIndex = row * width + ((column + 1) % width);
      const upIndex = Math.min(row + 1, height - 1) * width + column;
      const downIndex = Math.max(row - 1, 0) * width + column;
      const left = validity[leftIndex] === 255 ? altitudeKm[leftIndex]! : altitudeKm[index]!;
      const right = validity[rightIndex] === 255 ? altitudeKm[rightIndex]! : altitudeKm[index]!;
      const up = validity[upIndex] === 255 ? altitudeKm[upIndex]! : altitudeKm[index]!;
      const down = validity[downIndex] === 255 ? altitudeKm[downIndex]! : altitudeKm[index]!;
      const signal = THREE.MathUtils.clamp(
        ((right - left) * RELIEF_LIGHT_DIRECTION.longitude + (up - down) * RELIEF_LIGHT_DIRECTION.latitude)
          / RELIEF_GRADIENT_SATURATION_KM,
        -1,
        1,
      );
      shade[index] = 0.5 + 0.5 * signal;
    }
  }
  return shade;
}

function surfacePositions(
  grid: SurfaceGrid,
  altitudesKm: Float32Array,
  earthSceneRadius: number,
  meanAltitudeKm?: number,
) {
  const positions = new Float32Array(grid.pointCount * 3);
  const meanRadius = meanAltitudeKm !== undefined ? ionosphereDisplayRadius(meanAltitudeKm, earthSceneRadius) : undefined;
  let index = 0;
  for (const latitudeDeg of grid.latitudesDeg) {
    const latitude = THREE.MathUtils.degToRad(latitudeDeg);
    for (const longitudeDeg of grid.longitudesDeg) {
      const naturalRadius = ionosphereDisplayRadius(altitudesKm[index]!, earthSceneRadius);
      let radius = naturalRadius;
      if (meanRadius !== undefined) {
        const exaggeratedDeviation = THREE.MathUtils.clamp(
          (naturalRadius - meanRadius) * HEIGHT_EXAGGERATION_FACTOR,
          -HEIGHT_EXAGGERATION_MAX_SCENE_UNITS,
          HEIGHT_EXAGGERATION_MAX_SCENE_UNITS,
        );
        // Never let exaggeration push the surface below the solid Earth,
        // regardless of how the tuning constants above are set.
        radius = Math.max(earthSceneRadius + 0.5, meanRadius + exaggeratedDeviation);
      }
      const longitude = THREE.MathUtils.degToRad(longitudeDeg);
      const horizontal = radius * Math.cos(latitude);
      positions[index * 3] = horizontal * Math.cos(longitude);
      positions[index * 3 + 1] = radius * Math.sin(latitude);
      positions[index * 3 + 2] = -horizontal * Math.sin(longitude);
      index += 1;
    }
  }
  return positions;
}

function surfaceGeometry(
  grid: SurfaceGrid,
  start: DecodedSurface,
  end: DecodedSurface,
  earthSceneRadius: number,
) {
  const geometry = new THREE.BufferGeometry();
  const meanStartAltitudeKm = meanValidAltitudeKm(start);
  const meanEndAltitudeKm = meanValidAltitudeKm(end);
  geometry.setAttribute("position", new THREE.BufferAttribute(surfacePositions(grid, start.altitudeKm, earthSceneRadius, meanStartAltitudeKm), 3));
  geometry.setAttribute("positionB", new THREE.BufferAttribute(surfacePositions(grid, end.altitudeKm, earthSceneRadius, meanEndAltitudeKm), 3));
  geometry.setAttribute("densityA", new THREE.BufferAttribute(start.density, 1, true));
  geometry.setAttribute("densityB", new THREE.BufferAttribute(end.density, 1, true));
  geometry.setAttribute("altitudeA", new THREE.BufferAttribute(start.altitudeKm, 1));
  geometry.setAttribute("altitudeB", new THREE.BufferAttribute(end.altitudeKm, 1));
  geometry.setAttribute("reliefA", new THREE.BufferAttribute(computeReliefShade(grid, start.altitudeKm, start.validity), 1));
  geometry.setAttribute("reliefB", new THREE.BufferAttribute(computeReliefShade(grid, end.altitudeKm, end.validity), 1));
  const width = grid.longitudesDeg.length;
  const height = grid.latitudesDeg.length;
  const indices: number[] = [];
  const supported = (index: number) => start.validity[index] === 255 && end.validity[index] === 255;
  for (let latitudeIndex = 0; latitudeIndex < height - 1; latitudeIndex += 1) {
    for (let longitudeIndex = 0; longitudeIndex < width; longitudeIndex += 1) {
      const nextLongitude = (longitudeIndex + 1) % width;
      const lowerLeft = latitudeIndex * width + longitudeIndex;
      const lowerRight = latitudeIndex * width + nextLongitude;
      const upperLeft = (latitudeIndex + 1) * width + longitudeIndex;
      const upperRight = (latitudeIndex + 1) * width + nextLongitude;
      if (supported(lowerLeft) && supported(upperLeft) && supported(lowerRight)) {
        indices.push(lowerLeft, upperLeft, lowerRight);
      }
      if (supported(lowerRight) && supported(upperLeft) && supported(upperRight)) {
        indices.push(lowerRight, upperLeft, upperRight);
      }
    }
  }
  geometry.setIndex(indices);
  geometry.computeBoundingSphere();
  geometry.userData = {
    kind: "wam-ipe-data-derived-peak-surface",
    horizontalVertexCount: grid.pointCount,
    heightExaggeration: { factor: HEIGHT_EXAGGERATION_FACTOR, maxSceneUnits: HEIGHT_EXAGGERATION_MAX_SCENE_UNITS },
  };
  return geometry;
}

function surfaceMaterial(bundle: IonosphereVolumeBundle, region: IonosphereRegion) {
  return new THREE.ShaderMaterial({
    uniforms: {
      blendAmount: { value: 0 },
      minimumAltitudeKm: { value: bundle.grid.altitudesKm[0] ?? 90 },
      maximumAltitudeKm: { value: bundle.grid.altitudesKm.at(-1) ?? 2655 },
      opacityScale: { value: REGION_OPACITY[region] },
      contourIntervalKm: { value: CONTOUR_INTERVAL_KM[region] },
    },
    transparent: true,
    depthTest: true,
    depthWrite: false,
    side: THREE.FrontSide,
    blending: THREE.NormalBlending,
    toneMapped: false,
    vertexShader: `
      attribute vec3 positionB;
      attribute float densityA;
      attribute float densityB;
      attribute float altitudeA;
      attribute float altitudeB;
      attribute float reliefA;
      attribute float reliefB;
      uniform float blendAmount;
      varying float densityValue;
      varying float altitudeKm;
      varying float limb;
      varying float relief;
      void main() {
        vec3 displaced = mix(position, positionB, blendAmount);
        densityValue = mix(densityA, densityB, blendAmount);
        altitudeKm = mix(altitudeA, altitudeB, blendAmount);
        relief = mix(reliefA, reliefB, blendAmount);
        vec3 viewNormal = normalize(normalMatrix * normalize(displaced));
        limb = pow(1.0 - abs(viewNormal.z), 1.55);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
      }
    `,
    fragmentShader: `
      uniform float minimumAltitudeKm;
      uniform float maximumAltitudeKm;
      uniform float opacityScale;
      uniform float contourIntervalKm;
      varying float densityValue;
      varying float altitudeKm;
      varying float limb;
      varying float relief;
      void main() {
        if (altitudeKm < minimumAltitudeKm || altitudeKm > maximumAltitudeKm) discard;
        float value = clamp(densityValue, 0.0, 1.0);
        vec3 lowColor = vec3(0.25, 0.12, 0.52);
        vec3 middleColor = vec3(0.04, 0.70, 0.82);
        vec3 highColor = vec3(1.0, 0.78, 0.22);
        vec3 color = value < 0.56
          ? mix(lowColor, middleColor, value / 0.56)
          : mix(middleColor, highColor, (value - 0.56) / 0.44);
        float densityWeight = mix(0.55, 1.0, smoothstep(0.18, 0.92, value));
        float opacity = opacityScale * mix(${FACE_ON_OPACITY_FLOOR}, 1.0, limb) * densityWeight;
        float reliefLit = mix(${RELIEF_SHADE_MIN_MULTIPLIER}, ${RELIEF_SHADE_MAX_MULTIPLIER}, relief);
        vec3 lit = color * mix(0.72, 1.08, limb) * reliefLit;

        // Isohypses: constant-physical-height contour lines, exactly like
        // geopotential-height lines on a weather map. altitudeKm is always
        // the true, unexaggerated value -- contours are drawn in physical
        // space regardless of the exaggerated display radius above.
        float phase = altitudeKm / max(contourIntervalKm, 0.001);
        float fractional = phase - floor(phase);
        float distanceKm = min(fractional, 1.0 - fractional) * contourIntervalKm;
        float pixelKm = fwidth(altitudeKm) * ${CONTOUR_LINE_HALF_WIDTH_PX} + 0.0005;
        float contourLine = 1.0 - smoothstep(0.0, pixelKm, distanceKm);
        vec3 contourColor = vec3(${CONTOUR_LINE_COLOR.r}, ${CONTOUR_LINE_COLOR.g}, ${CONTOUR_LINE_COLOR.b});
        vec3 finalColor = mix(lit, contourColor, contourLine * 0.85);
        float finalOpacity = clamp(opacity + contourLine * 0.35, 0.0, 1.0);
        gl_FragColor = vec4(finalColor, finalOpacity);
      }
    `,
  });
}

function surfaceSummary(
  bundle: IonosphereVolumeBundle,
  region: IonosphereRegion,
  source: IonosphereSurfaceRegionState["source"],
  start: DecodedSurface,
  end: DecodedSurface,
  selection: IonosphereFrameSelection,
  frameTimes: ReadonlyArray<{ validAt: string }>,
): IonosphereSurfaceRegionState {
  let supported = 0;
  let minimumAltitude = Number.POSITIVE_INFINITY;
  let maximumAltitude = Number.NEGATIVE_INFINITY;
  let altitudeTotal = 0;
  let minimumDensity = Number.POSITIVE_INFINITY;
  let maximumDensity = Number.NEGATIVE_INFINITY;
  for (let index = 0; index < start.validity.length; index += 1) {
    if (start.validity[index] !== 255 || end.validity[index] !== 255) continue;
    supported += 1;
    const altitude = THREE.MathUtils.lerp(start.altitudeKm[index]!, end.altitudeKm[index]!, selection.blend);
    const densityCode = THREE.MathUtils.lerp(start.density[index]!, end.density[index]!, selection.blend);
    const density = ionosphereDensityFromCode(bundle, densityCode);
    minimumAltitude = Math.min(minimumAltitude, altitude);
    maximumAltitude = Math.max(maximumAltitude, altitude);
    altitudeTotal += altitude;
    minimumDensity = Math.min(minimumDensity, density);
    maximumDensity = Math.max(maximumDensity, density);
  }
  return {
    region,
    source,
    validAt: {
      start: frameTimes[selection.startIndex]?.validAt ?? "",
      end: frameTimes[selection.endIndex]?.validAt ?? "",
      blend: selection.blend,
    },
    supportedColumnPercent: start.validity.length > 0 ? (supported / start.validity.length) * 100 : 0,
    altitudeRangeKm: supported ? [minimumAltitude, maximumAltitude] : null,
    densityRangeM3: supported ? [minimumDensity, maximumDensity] : null,
    meanAltitudeKm: supported ? altitudeTotal / supported : null,
    displayExaggeration: { factor: HEIGHT_EXAGGERATION_FACTOR, maxSceneUnits: HEIGHT_EXAGGERATION_MAX_SCENE_UNITS },
    contourIntervalKm: CONTOUR_INTERVAL_KM[region],
  };
}

export class IonosphereVolumeLayer {
  /** Compatibility name retained for GlobeController; this is now a surface group, never a point cloud. */
  readonly points = new THREE.Group();
  readonly surfaces: Record<IonosphereRegion, THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>>;
  private readonly decodedFrames = new Map<number, DecodedFrame>();
  private readonly profileSurfaces = new Map<string, DecodedSurface>();
  private readonly peakSurfaces = new Map<number, DecodedSurface>();
  private readonly framePairs: Record<IonosphereRegion, string> = { e: "", f1: "", f2: "" };
  private readonly earthSceneRadius: number;
  private currentTime: Date;
  private spatialMode: IonosphereSpatialMode;
  private stateValue: IonosphereSurfaceState;

  constructor(
    private readonly bundle: IonosphereVolumeBundle,
    options: { earthSceneRadius?: number; pixelRatio?: number; spatialMode?: IonosphereSpatialMode } = {},
  ) {
    this.earthSceneRadius = options.earthSceneRadius ?? 100;
    this.spatialMode = options.spatialMode ?? bundle.representation.recommendedDefault;
    this.currentTime = new Date(bundle.frames[0]?.validAt ?? Number.NaN);
    this.surfaces = {
      e: new THREE.Mesh(new THREE.BufferGeometry(), surfaceMaterial(bundle, "e")),
      f1: new THREE.Mesh(new THREE.BufferGeometry(), surfaceMaterial(bundle, "f1")),
      f2: new THREE.Mesh(new THREE.BufferGeometry(), surfaceMaterial(bundle, "f2")),
    };
    (Object.keys(this.surfaces) as IonosphereRegion[]).forEach((region, index) => {
      const mesh = this.surfaces[region];
      mesh.frustumCulled = false;
      mesh.renderOrder = 2 + index;
      mesh.name = `wam-ipe-${region}-peak-surface`;
      mesh.userData = { region, sourceGeometry: true, fixedTeachingShell: false };
      this.points.add(mesh);
    });
    this.points.name = "wam-ipe-data-derived-ionosphere-surfaces";
    this.points.userData = { kind: "wam-ipe-peak-surfaces", pointCloud: false, dRegionAvailable: false };
    void options.pixelRatio;
    this.stateValue = this.emptyState();
    this.setSimulationTime(this.currentTime);
  }

  private emptyState(): IonosphereSurfaceState {
    const noRegion = (region: IonosphereRegion): IonosphereSurfaceRegionState => ({
      region,
      source: region === "f2" && (this.bundle as EnhancedIonosphereBundle).peakSurface
        ? "NOAA ipe05 HmF2/NmF2"
        : "derived from NOAA ipe10 3-D profile",
      validAt: { start: "", end: "", blend: 0 },
      supportedColumnPercent: 0,
      altitudeRangeKm: null,
      densityRangeM3: null,
      meanAltitudeKm: null,
      displayExaggeration: { factor: HEIGHT_EXAGGERATION_FACTOR, maxSceneUnits: HEIGHT_EXAGGERATION_MAX_SCENE_UNITS },
      contourIntervalKm: CONTOUR_INTERVAL_KM[region],
    });
    const enhanced = this.bundle as EnhancedIonosphereBundle;
    return {
      requestedAt: null,
      regions: { e: noRegion("e"), f1: noRegion("f1"), f2: noRegion("f2") },
      dRegion: {
        available: false,
        lowerBoundaryKm: 90,
        reason: enhanced.profileRegionSurfaces?.dRegion?.reason
          ?? "The operational WAM-IPE full-field grid begins at 90 km; most of the D region is unavailable.",
      },
    };
  }

  private nativeFrame(index: number) {
    const cached = this.decodedFrames.get(index);
    if (cached) return cached;
    const source = this.bundle.frames[index];
    if (!source) throw new RangeError(`WAM-IPE frame ${index} is unavailable`);
    const decoded = {
      density: decodeIonosphereDensity(source.densityU8, this.bundle.grid.pointCount),
      validity: decodeIonosphereValidity(source.validityBits, this.bundle.grid.pointCount),
    };
    this.decodedFrames.set(index, decoded);
    return decoded;
  }

  private profileSurface(index: number, region: IonosphereRegion) {
    const key = `${region}:${index}`;
    const cached = this.profileSurfaces.get(key);
    if (cached) return cached;
    const frame = this.bundle.frames[index] as EnhancedVolumeFrame | undefined;
    if (!frame) throw new RangeError(`WAM-IPE frame ${index} is unavailable`);
    const encoded = region === "f2" ? undefined : frame.regionSurfaces?.[region];
    const pointCount = this.bundle.grid.longitudesDeg.length * this.bundle.grid.latitudesDeg.length;
    const surface = encoded
      ? {
          altitudeKm: decodeSurfaceAltitude(encoded.altitudeU16, pointCount, 0.1),
          density: decodeIonosphereDensity(encoded.densityU8, pointCount),
          validity: decodeIonosphereValidity(encoded.validityBits, pointCount),
        }
      : deriveProfileSurface(this.bundle, this.nativeFrame(index), region);
    this.profileSurfaces.set(key, surface);
    while (this.profileSurfaces.size > 18) this.profileSurfaces.delete(this.profileSurfaces.keys().next().value!);
    return surface;
  }

  private peakSurface(index: number) {
    const cached = this.peakSurfaces.get(index);
    if (cached) return cached;
    const peak = (this.bundle as EnhancedIonosphereBundle).peakSurface;
    const frame = peak?.frames[index];
    if (!peak || !frame) throw new RangeError(`WAM-IPE HmF2/NmF2 frame ${index} is unavailable`);
    const pointCount = this.bundle.grid.longitudesDeg.length * this.bundle.grid.latitudesDeg.length;
    if (peak.pointCount !== pointCount) throw new RangeError("WAM-IPE HmF2/NmF2 grid does not match the 3-D profile grid");
    const surface = {
      altitudeKm: decodeSurfaceAltitude(frame.altitudeU16, pointCount, peak.altitudeEncoding.scaleKm),
      density: decodeIonosphereDensity(frame.densityU8, pointCount),
      validity: decodeIonosphereValidity(frame.validityBits, pointCount),
    };
    this.peakSurfaces.set(index, surface);
    while (this.peakSurfaces.size > 12) this.peakSurfaces.delete(this.peakSurfaces.keys().next().value!);
    return surface;
  }

  private installSurface(
    region: IonosphereRegion,
    key: string,
    start: DecodedSurface,
    end: DecodedSurface,
    blend: number,
  ) {
    const mesh = this.surfaces[region];
    if (key !== this.framePairs[region]) {
      const grid = surfaceGrid(this.bundle, this.spatialMode);
      const resampledStart = resampleSurface(this.bundle, start, grid);
      const resampledEnd = resampleSurface(this.bundle, end, grid);
      const displayStart = this.spatialMode === "smooth" ? smoothSurfaceForDisplay(resampledStart, grid) : resampledStart;
      const displayEnd = this.spatialMode === "smooth" ? smoothSurfaceForDisplay(resampledEnd, grid) : resampledEnd;
      const previous = mesh.geometry;
      mesh.geometry = surfaceGeometry(grid, displayStart, displayEnd, this.earthSceneRadius);
      previous.dispose();
      this.framePairs[region] = key;
      mesh.visible = (mesh.geometry.getIndex()?.count ?? 0) > 0;
    }
    mesh.material.uniforms.blendAmount!.value = blend;
  }

  getSpatialMode() {
    return this.spatialMode;
  }

  getSurfaceState() {
    return this.stateValue;
  }

  setSpatialMode(mode: IonosphereSpatialMode) {
    if (mode === this.spatialMode) return;
    this.spatialMode = mode;
    this.framePairs.e = "";
    this.framePairs.f1 = "";
    this.framePairs.f2 = "";
    this.setSimulationTime(this.currentTime);
  }

  setSimulationTime(time: Date) {
    this.currentTime.setTime(time.getTime());
    const profileSelection = selectIonosphereFrames(this.bundle, time);
    const profileStart = this.bundle.frames[profileSelection.startIndex];
    const profileEnd = this.bundle.frames[profileSelection.endIndex];
    if (!profileStart || !profileEnd) throw new RangeError("WAM-IPE profile frame selection is unavailable");
    const regionStates = {} as Record<IonosphereRegion, IonosphereSurfaceRegionState>;
    for (const region of ["e", "f1"] as const) {
      const start = this.profileSurface(profileSelection.startIndex, region);
      const end = this.profileSurface(profileSelection.endIndex, region);
      this.installSurface(
        region,
        `${this.spatialMode}:profile:${profileSelection.startIndex}:${profileSelection.endIndex}`,
        start,
        end,
        profileSelection.blend,
      );
      regionStates[region] = surfaceSummary(
        this.bundle,
        region,
        "derived from NOAA ipe10 3-D profile",
        start,
        end,
        profileSelection,
        this.bundle.frames,
      );
    }

    const peak = (this.bundle as EnhancedIonosphereBundle).peakSurface;
    if (peak?.frames.length) {
      const peakSelection = selectTimedSurfaceFrames(peak.frames, time);
      const start = this.peakSurface(peakSelection.startIndex);
      const end = this.peakSurface(peakSelection.endIndex);
      this.installSurface(
        "f2",
        `${this.spatialMode}:peak:${peakSelection.startIndex}:${peakSelection.endIndex}`,
        start,
        end,
        peakSelection.blend,
      );
      regionStates.f2 = surfaceSummary(
        this.bundle,
        "f2",
        "NOAA ipe05 HmF2/NmF2",
        start,
        end,
        peakSelection,
        peak.frames,
      );
    } else {
      const start = this.profileSurface(profileSelection.startIndex, "f2");
      const end = this.profileSurface(profileSelection.endIndex, "f2");
      this.installSurface(
        "f2",
        `${this.spatialMode}:profile:${profileSelection.startIndex}:${profileSelection.endIndex}`,
        start,
        end,
        profileSelection.blend,
      );
      regionStates.f2 = surfaceSummary(
        this.bundle,
        "f2",
        "derived from NOAA ipe10 3-D profile",
        start,
        end,
        profileSelection,
        this.bundle.frames,
      );
    }
    this.stateValue = {
      ...this.emptyState(),
      requestedAt: Number.isFinite(time.getTime()) ? time.toISOString() : null,
      regions: regionStates,
    };
    this.points.userData.ionosphereSurfaceState = this.stateValue;
    return profileSelection;
  }

  setAltitudeRange(minimumKm: number, maximumKm: number) {
    const low = Math.min(minimumKm, maximumKm);
    const high = Math.max(minimumKm, maximumKm);
    for (const mesh of Object.values(this.surfaces)) {
      mesh.material.uniforms.minimumAltitudeKm!.value = low;
      mesh.material.uniforms.maximumAltitudeKm!.value = high;
    }
  }

  setRendering(pixelRatio: number, pointSize = 1) {
    const scale = THREE.MathUtils.clamp(pixelRatio, 0.5, 2) * THREE.MathUtils.clamp(pointSize, 0.6, 2.2);
    for (const region of Object.keys(this.surfaces) as IonosphereRegion[]) {
      this.surfaces[region].material.uniforms.opacityScale!.value = REGION_OPACITY[region] * THREE.MathUtils.clamp(scale, 0.85, 1.15);
    }
  }

  dispose() {
    for (const mesh of Object.values(this.surfaces)) {
      mesh.geometry.dispose();
      mesh.material.dispose();
      mesh.removeFromParent();
    }
    this.decodedFrames.clear();
    this.profileSurfaces.clear();
    this.peakSurfaces.clear();
    this.points.clear();
  }
}
