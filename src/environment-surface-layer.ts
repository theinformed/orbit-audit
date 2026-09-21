import * as THREE from "three";
import {
  auroraRgbaGrid,
  selectAuroraFrame,
  type AuroraBundle,
  type AuroraDisplayMode,
  type AuroraEquatorialSeam,
  type AuroraFrame,
} from "./aurora-time";
import { sharedDisplayRadius } from "./radial-ruler";
import {
  DRAP_LIVE_EDGE_HOLD_MINUTES,
  drapCondition,
  drapRgbaGrid,
  selectDrapFrame,
  type DrapBundle,
  type DrapCondition,
  type DrapDisplayMode,
  type DrapFrame,
} from "./drap";

const EARTH_MEAN_RADIUS_KM = 6_371;
const DEFAULT_EARTH_SCENE_RADIUS = 100;

/**
 * CORRECTNESS FIX 2026-09-04: 70 km, not 35, and drawn through the shared
 * ruler rather than a private one.
 *
 * The absorbing layer is the D region. This site says so in four places and
 * gives D-RAP's own reference heights while it is at it — `layer-pages.ts`,
 * the D-region page: "The reference heights are the ones its empirical
 * Wait–Spies D region uses: about 70 km by day, about 84 km at night", with
 * `extent: "60 – 90 km"`; `content.ts` twice more, "D region, 60–90 km". A
 * single shell has to pick one number and the daytime one is the honest
 * choice, because HF absorption is overwhelmingly a sunlit-hemisphere
 * phenomenon and 70 km is where D-RAP's own scaling is anchored.
 *
 * 35 km was in the stratosphere, matched nothing the site says, and was
 * declared nowhere a reader can see. It appears to have been picked for
 * z-ordering — the only mention of it in writing is a stacking comment in
 * `globe.ts`. Moving it up does not disturb that order: the TEC wash is still
 * the lowest thing on the globe at 100.06.
 */
const DRAP_SURFACE_ALTITUDE_KM = 70;

/**
 * Auroral emission peaks near here, and the constant was already right. What
 * was wrong was how it reached the screen — see `surfaceSceneRadius`.
 */
const AURORA_EMISSION_ALTITUDE_KM = 110;

/**
 * Where a surface layer's altitude is drawn.
 *
 * CORRECTNESS FIX 2026-09-04. This used to be `earthRadius * (1 + altitudeKm /
 * EARTH_MEAN_RADIUS_KM)`, computed once in the constructor and never revisited.
 * That is the TRUE-DISTANCE curve written out by hand, so on the scale the site
 * actually opens on — the teaching ruler — the drawn shell meant something else
 * entirely. Read back through `radiusFromSharedDisplayRadius`:
 *
 *              named      drawn      teaching ruler reads it as
 *   D-RAP      35 km      100.549    6.9 km
 *   aurora    110 km      101.727    22.3 km
 *
 * So the auroral oval, which is physically inside the E region, was drawn five
 * scene units BELOW the bottom of the ionospheric column the site draws through
 * the shared ruler (60 km lands at 104.43), and the same drawn shell claimed
 * two altitudes 4.4x apart depending on a Display setting. That is precisely
 * the failure `globe.ts` diagnoses at length for the old TEC shell and that the
 * shared ruler exists to prevent: "a layer that lifts itself onto a private
 * height curve will disagree with everything drawn on the shared one".
 *
 * Both layers were also missing from `rebuildRadialGeometry`, so even a correct
 * radius would have been frozen at the scale that was live when the bundle
 * loaded. `rebuildForDistanceScale` is the other half of this fix.
 */
function surfaceSceneRadius(altitudeKm: number, earthSceneRadius: number) {
  return sharedDisplayRadius(1 + Math.max(0, altitudeKm) / EARTH_MEAN_RADIUS_KM, earthSceneRadius);
}

export type EnvironmentSurfaceDisplayMode = "smooth" | "native";
export type EnvironmentSurfaceNoDataReason = "invalid-time" | "no-frames" | "before-coverage" | "gap" | "invalid-frame";

export interface EnvironmentSurfaceSourceRange {
  validFrom: string | null;
  validTo: string | null;
  frameCount: number;
  coverageComplete: boolean | null;
}

export interface EnvironmentSurfaceLegend {
  product: string;
  title: string;
  subtitle: string;
  units: string;
  minimum: number;
  maximum: number;
  ticks: number[];
  minimumLabel: string;
  maximumLabel: string;
  sourceUrl: string;
  sourceStatus: "model";
  displayMode: EnvironmentSurfaceDisplayMode;
  validAt: string | null;
  observedAt: string | null;
  sourceRange: EnvironmentSurfaceSourceRange;
  /**
   * The D-RAP layer's reading of its own frame -- how much of it is on the map,
   * and the words for that in each of the three places a reader can see them.
   * Carried whole rather than copied field by field, so the card, the legend
   * and the badge cannot come to say different things about one frame.
   */
  condition?: DrapCondition;
}

interface EnvironmentSurfaceStateBase {
  requestedAt: string | null;
  visible: boolean;
  legend: EnvironmentSurfaceLegend;
}

export interface EnvironmentSurfaceReadyState extends EnvironmentSurfaceStateBase {
  status: "ready";
  validAt: string;
  observedAt: string | null;
  ageMinutes: number;
  held: boolean;
}

export interface EnvironmentSurfaceNoDataState extends EnvironmentSurfaceStateBase {
  status: "no-data";
  reason: EnvironmentSurfaceNoDataReason;
  message: string;
  previousValidAt: string | null;
  nextValidAt: string | null;
}

export interface EnvironmentSurfaceStaleState extends EnvironmentSurfaceStateBase {
  status: "stale";
  reason: "after-coverage";
  message: string;
  lastValidAt: string;
  ageMinutes: number;
}

export type EnvironmentSurfaceState =
  | EnvironmentSurfaceReadyState
  | EnvironmentSurfaceNoDataState
  | EnvironmentSurfaceStaleState;

export interface EnvironmentSurfaceLayerOptions {
  earthSceneRadius?: number;
  enabled?: boolean;
  widthSegments?: number;
  heightSegments?: number;
  /**
   * `renderer.capabilities.getMaxAnisotropy()`, the same value the Earth
   * basemap texture already uses (`globe.ts`'s `buildEarthTexture`) to fix
   * the identical class of artefact: an equirectangular texture minifies
   * heavily along the longitude axis near the poles, where many source
   * columns collapse into a handful of screen pixels. Left at the default of
   * 1, that minification aliases into stair-stepped blocks — visible on the
   * OVATION oval's poleward edge. Omit only in tests that do not exercise a
   * WebGL context.
   */
  maxAnisotropy?: number;
}

interface FrameBounds<TFrame> {
  previous: TFrame | null;
  next: TFrame | null;
  previousIndex: number;
}

abstract class EnvironmentSurfaceLayerController<TBundle, TFrame, TMode extends EnvironmentSurfaceDisplayMode> {
  readonly mesh: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  protected bundle: TBundle;
  protected displayMode: TMode = "smooth" as TMode;
  protected currentFrame: TFrame | null = null;
  protected currentStateValue: EnvironmentSurfaceState;
  private enabledValue: boolean;
  private textureValue: THREE.DataTexture | null = null;
  private disposed = false;
  private readonly maxAnisotropy: number;
  /** The physical altitude this surface stands for, kept so the ruler can be re-read. */
  private altitudeKmValue = 0;
  private earthSceneRadiusValue = DEFAULT_EARTH_SCENE_RADIUS;
  private sphereSegments: [number, number] = [96, 64];

  protected constructor(
    bundle: TBundle,
    altitudeKm: number,
    options: EnvironmentSurfaceLayerOptions = {},
  ) {
    this.bundle = bundle;
    this.enabledValue = options.enabled ?? true;
    this.maxAnisotropy = options.maxAnisotropy ?? 1;
    const earthRadius = options.earthSceneRadius ?? DEFAULT_EARTH_SCENE_RADIUS;
    if (!Number.isFinite(earthRadius) || earthRadius <= 0) throw new RangeError("Earth scene radius must be positive");
    this.altitudeKmValue = altitudeKm;
    this.earthSceneRadiusValue = earthRadius;
    this.sphereSegments = [options.widthSegments ?? 96, options.heightSegments ?? 64];
    const geometry = new THREE.SphereGeometry(
      surfaceSceneRadius(altitudeKm, earthRadius),
      this.sphereSegments[0],
      this.sphereSegments[1],
    );
    const material = new THREE.MeshBasicMaterial({
      transparent: true,
      depthTest: true,
      depthWrite: false,
      side: THREE.FrontSide,
      toneMapped: false,
    });
    this.mesh = new THREE.Mesh(geometry, material);
    // No orienting rotation. installFrameTexture shifts the source grid so the
    // sampled coordinate is u = (longitude + 180) / 360, and three.js
    // SphereGeometry already draws u = 0.5 on +X — the same direction the
    // globe's geoToSceneVector gives longitude 0. A rotation here would move
    // this layer away from the satellites and coastlines drawn under it.
    this.mesh.renderOrder = 4;
    this.currentStateValue = this.noDataState(null, "no-frames", "No environmental frame has been selected.", null, null);
    this.applyState(this.currentStateValue);
  }

  get state(): EnvironmentSurfaceState {
    return this.currentStateValue;
  }

  get texture(): THREE.DataTexture | null {
    return this.textureValue;
  }

  get enabled(): boolean {
    return this.enabledValue;
  }

  get mode(): TMode {
    return this.displayMode;
  }

  /** The altitude this shell stands for, kilometres. The ruler decides where it is drawn. */
  get altitudeKm(): number {
    return this.altitudeKmValue;
  }

  /**
   * Redraw this shell through the live ruler.
   *
   * `SpaceGlobe.rebuildRadialGeometry` calls this when the visitor switches
   * between the teaching scale and true distance. Without it the two scales
   * would mix on screen: every other layer would move and this one would not.
   * The texture, the state and the material are untouched — only the radius the
   * sphere is built at changes — so a scale switch does not cost a decode.
   */
  rebuildForDistanceScale(): void {
    this.assertActive();
    const radius = surfaceSceneRadius(this.altitudeKmValue, this.earthSceneRadiusValue);
    const previous = this.mesh.geometry;
    this.mesh.geometry = new THREE.SphereGeometry(radius, this.sphereSegments[0], this.sphereSegments[1]);
    previous.dispose();
  }

  setEnabled(enabled: boolean): EnvironmentSurfaceState {
    this.assertActive();
    this.enabledValue = enabled;
    this.applyVisibility();
    this.currentStateValue = { ...this.currentStateValue, visible: this.mesh.visible };
    this.mesh.userData.environmentSurfaceState = this.currentStateValue;
    return this.currentStateValue;
  }

  setDisplayMode(mode: TMode): EnvironmentSurfaceState {
    this.assertActive();
    if (mode !== "smooth" && mode !== "native") throw new RangeError(`Unsupported environmental display mode: ${String(mode)}`);
    if (mode === this.displayMode) return this.currentStateValue;
    this.displayMode = mode;
    if (this.currentFrame && this.currentStateValue.status === "ready") {
      this.installFrameTexture(this.currentFrame);
      this.currentStateValue = {
        ...this.currentStateValue,
        legend: this.legend(this.currentStateValue.validAt, this.currentStateValue.observedAt),
      };
      this.applyState(this.currentStateValue);
    } else {
      this.currentStateValue = {
        ...this.currentStateValue,
        legend: this.legend(null, null),
      };
      this.applyState(this.currentStateValue);
    }
    return this.currentStateValue;
  }

  setSimulationTime(requestedAt: Date | string | number): EnvironmentSurfaceState {
    this.assertActive();
    const requested = parseRequestedTime(requestedAt);
    if (!requested) {
      this.clearTexture();
      this.currentFrame = null;
      this.currentStateValue = this.noDataState(null, "invalid-time", "The selected simulation time is invalid.", null, null);
      this.applyState(this.currentStateValue);
      return this.currentStateValue;
    }
    const state = this.selectState(requestedAt, requested);
    if (state.status === "ready") {
      const selected = this.selectedFrame(requestedAt);
      if (!selected) {
        this.clearTexture();
        this.currentFrame = null;
        this.currentStateValue = this.noDataState(requested.iso, "invalid-frame", "The selected source frame could not be decoded.", null, null);
      } else {
        if (selected !== this.currentFrame || !this.textureValue) this.installFrameTexture(selected);
        this.currentFrame = selected;
        this.currentStateValue = state;
      }
    } else {
      // A stale or missing field must not remain resident on the visible shell.
      this.currentFrame = null;
      this.clearTexture();
      this.currentStateValue = state;
    }
    this.applyState(this.currentStateValue);
    return this.currentStateValue;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.clearTexture();
    this.mesh.removeFromParent();
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
    this.mesh.visible = false;
  }

  protected abstract frames(): TFrame[];
  protected abstract frameValidAt(frame: TFrame): string;
  protected abstract frameObservedAt(frame: TFrame): string | null;
  protected abstract sourceRange(): EnvironmentSurfaceSourceRange;
  protected abstract legend(validAt: string | null, observedAt: string | null): EnvironmentSurfaceLegend;
  protected abstract selectedFrame(requestedAt: Date | string | number): TFrame | null;
  protected abstract selectState(requestedAt: Date | string | number, requested: ParsedTime): EnvironmentSurfaceState;
  protected abstract rgba(frame: TFrame): { width: number; height: number; rgba: Uint8ClampedArray; equatorialSeam?: AuroraEquatorialSeam | null };
  protected abstract latitudeStepDegrees(): number;
  protected abstract longitudeStartDegrees(): number;
  protected abstract longitudeStepDegrees(): number;

  protected bounds(requestedMs: number): FrameBounds<TFrame> {
    let previous: TFrame | null = null;
    let next: TFrame | null = null;
    let previousIndex = -1;
    for (let index = 0; index < this.frames().length; index += 1) {
      const frame = this.frames()[index]!;
      const validMs = Date.parse(this.frameValidAt(frame));
      if (!Number.isFinite(validMs)) continue;
      if (validMs <= requestedMs) {
        previous = frame;
        previousIndex = index;
      } else {
        next = frame;
        break;
      }
    }
    return { previous, next, previousIndex };
  }

  protected readyState(requested: ParsedTime, frame: TFrame, ageMinutes: number): EnvironmentSurfaceReadyState {
    const validAt = this.frameValidAt(frame);
    const observedAt = this.frameObservedAt(frame);
    return {
      status: "ready",
      requestedAt: requested.iso,
      visible: this.enabledValue,
      validAt,
      observedAt,
      ageMinutes,
      held: ageMinutes > 0,
      legend: this.legend(validAt, observedAt),
    };
  }

  protected noDataState(
    requestedAt: string | null,
    reason: EnvironmentSurfaceNoDataReason,
    message: string,
    previousValidAt: string | null,
    nextValidAt: string | null,
  ): EnvironmentSurfaceNoDataState {
    return {
      status: "no-data",
      requestedAt,
      visible: false,
      reason,
      message,
      previousValidAt,
      nextValidAt,
      legend: this.legend(null, null),
    };
  }

  protected staleState(requested: ParsedTime, frame: TFrame, ageMinutes: number): EnvironmentSurfaceStaleState {
    const validAt = this.frameValidAt(frame);
    return {
      status: "stale",
      requestedAt: requested.iso,
      visible: false,
      reason: "after-coverage",
      message: `Latest exact source frame is ${Math.floor(ageMinutes)} minutes older than the selected UTC.`,
      lastValidAt: validAt,
      ageMinutes,
      legend: this.legend(null, null),
    };
  }

  private installFrameTexture(frame: TFrame): void {
    const rendered = this.rgba(frame);
    if (rendered.width <= 0 || rendered.height <= 0 || rendered.rgba.length !== rendered.width * rendered.height * 4) {
      throw new Error("Environmental RGBA grid dimensions are invalid");
    }
    const texture = new THREE.DataTexture(
      rendered.rgba,
      rendered.width,
      rendered.height,
      THREE.RGBAFormat,
      THREE.UnsignedByteType,
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
    // Native mode is meant to expose the raw source cells, so it keeps plain
    // nearest sampling and no mip chain. Smooth mode's honest failure was
    // that it stopped at a single GPU-side bilinear tap: near the poles, an
    // equirectangular grid's longitude columns converge, so one screen pixel
    // there covers many source texels — a minification case, not the
    // magnification anisotropic filtering is sometimes mistaken for (see the
    // Earth basemap's own `buildEarthTexture`, which already carries this
    // fix). Without mipmaps the GPU had nothing to average across that
    // collapse and aliased it into the stair-stepped blocks visible on the
    // oval's poleward edge. Mipmapping plus anisotropy sample and average
    // more of the true field there; neither invents a value outside it.
    texture.minFilter = this.displayMode === "smooth" ? THREE.LinearMipmapLinearFilter : THREE.NearestFilter;
    texture.magFilter = this.displayMode === "smooth" ? THREE.LinearFilter : THREE.NearestFilter;
    texture.generateMipmaps = this.displayMode === "smooth";
    texture.anisotropy = this.displayMode === "smooth" ? this.maxAnisotropy : 1;
    // NOAA products use opposite latitude row orders. DataTexture has a
    // bottom-left UV origin, so north-to-south source rows require Y flipping.
    texture.flipY = this.latitudeStepDegrees() < 0;
    const step = this.longitudeStepDegrees();
    texture.offset.x = (-this.longitudeStartDegrees() + step / 2 - 180) / 360;
    texture.needsUpdate = true;
    texture.userData = {
      product: this.legend(null, null).product,
      validAt: this.frameValidAt(frame),
      displayMode: this.displayMode,
      temporalInterpolation: false,
      longitudeStartDegrees: this.longitudeStartDegrees(),
      longitudeStepDegrees: step,
      latitudeRowOrder: this.latitudeStepDegrees() < 0 ? "north-to-south" : "south-to-north",
      // Present only when the source frame carried a disconnected equatorial
      // seam. Those cells are drawn as missing, never as a modeled zero.
      equatorialSeamWithdrawn: rendered.equatorialSeam ?? null,
    };

    const previous = this.textureValue;
    this.textureValue = texture;
    this.mesh.material.map = texture;
    this.mesh.material.needsUpdate = true;
    previous?.dispose();
  }

  private clearTexture(): void {
    const previous = this.textureValue;
    this.textureValue = null;
    this.mesh.material.map = null;
    this.mesh.material.needsUpdate = true;
    previous?.dispose();
  }

  private applyState(state: EnvironmentSurfaceState): void {
    this.currentStateValue = state;
    this.applyVisibility();
    if (state.visible !== this.mesh.visible) this.currentStateValue = { ...state, visible: this.mesh.visible };
    this.mesh.userData.environmentSurfaceState = this.currentStateValue;
  }

  private applyVisibility(): void {
    this.mesh.visible = this.enabledValue && this.currentStateValue.status === "ready" && this.textureValue !== null;
  }

  private assertActive(): void {
    if (this.disposed) throw new Error("Environmental surface layer has been disposed");
  }
}

export class DrapSurfaceLayerController extends EnvironmentSurfaceLayerController<DrapBundle, DrapFrame, DrapDisplayMode> {
  constructor(bundle: DrapBundle, options: EnvironmentSurfaceLayerOptions = {}) {
    super(bundle, DRAP_SURFACE_ALTITUDE_KM, options);
  }

  protected frames(): DrapFrame[] { return this.bundle.frames; }
  protected frameValidAt(frame: DrapFrame): string { return frame.validAt; }
  protected frameObservedAt(_frame: DrapFrame): string | null { return null; }
  protected latitudeStepDegrees(): number { return this.bundle.grid.latitudeStepDeg; }
  protected longitudeStartDegrees(): number { return this.bundle.grid.longitudeStartDeg; }
  protected longitudeStepDegrees(): number { return this.bundle.grid.longitudeStepDeg; }

  protected sourceRange(): EnvironmentSurfaceSourceRange {
    const releaseTime = this.bundle.time as DrapBundle["time"] & { coverageComplete?: boolean };
    return frameSourceRange(
      this.bundle.frames,
      (frame) => frame.validAt,
      typeof releaseTime.coverageComplete === "boolean" ? releaseTime.coverageComplete : null,
    );
  }

  protected legend(validAt: string | null, observedAt: string | null): EnvironmentSurfaceLegend {
    const frame = validAt ? this.bundle.frames.find((candidate) => candidate.validAt === validAt) : undefined;
    const condition = frame ? drapCondition(frame) : undefined;
    return {
      product: this.bundle.product,
      title: this.bundle.legend.title,
      subtitle: this.bundle.legend.subtitle,
      units: this.bundle.quantity.units,
      minimum: this.bundle.legend.minimumDisplayedMhz,
      maximum: this.bundle.legend.maximumDisplayedMhz,
      ticks: [...this.bundle.legend.ticksMhz],
      minimumLabel: this.bundle.legend.belowMinimumLabel,
      maximumLabel: this.bundle.legend.aboveMaximumLabel,
      sourceUrl: this.bundle.source.currentData,
      sourceStatus: "model",
      displayMode: this.displayMode,
      validAt,
      observedAt,
      sourceRange: this.sourceRange(),
      condition,
    };
  }

  protected selectedFrame(requestedAt: Date | string | number): DrapFrame | null {
    return selectDrapFrame(this.bundle, requestedAt)?.frame ?? null;
  }

  protected selectState(requestedAt: Date | string | number, requested: ParsedTime): EnvironmentSurfaceState {
    const selection = selectDrapFrame(this.bundle, requestedAt);
    const bounds = this.bounds(requested.ms);
    if (!selection) {
      if (this.bundle.frames.length === 0) return this.noDataState(requested.iso, "no-frames", "No exact NOAA D-RAP frames are loaded.", null, null);
      return this.noDataState(
        requested.iso,
        bounds.previous ? "invalid-frame" : "before-coverage",
        bounds.previous ? "The D-RAP source frame at this UTC is invalid." : "No exact NOAA D-RAP frame exists before this UTC.",
        bounds.previous ? this.frameValidAt(bounds.previous) : null,
        bounds.next ? this.frameValidAt(bounds.next) : null,
      );
    }
    // `selection.stale` alone used to hide the layer past 12 minutes' age,
    // unconditionally. That is right for a genuine internal gap — a known
    // newer frame is being silently skipped, and holding the old one across
    // it would misrepresent the timeline. It is wrong at the live edge: when
    // `bounds.next` is empty there is no newer frame to skip, this is simply
    // the newest thing bigmem has ever captured, and NOAA's own D-RAP nowcast
    // does not publish on a strict cadence (manifest.drap records real,
    // ordinary gaps of 30-60+ minutes; a 45-minute-old newest frame at
    // live-now is routine upstream behaviour, not a pipeline failure). Under
    // the old rule that routine lag hid the layer far more often than the
    // 12-minute threshold implies. Draw the newest frame and disclose its
    // age via `held`/`ageMinutes` instead of refusing — the same honesty
    // pattern the aurora layer's active-forecast path already gives a live
    // viewer: show the latest verified thing, state how old it is, never
    // interpolate across what is actually missing.
    if (selection.stale && bounds.next) {
      return this.noDataState(
        requested.iso,
        "gap",
        "No exact NOAA D-RAP frame covers this cache gap; stale values are hidden.",
        selection.frame.validAt,
        bounds.next.validAt,
      );
    }
    // ...AND THE OTHER END OF THAT SAME ARGUMENT, which the live-edge fix
    // above left open. Holding the newest frame across NOAA's routine
    // publication lag is right; holding it across the slider's whole +72 h
    // forward reach is not. D-RAP publishes no future frames -- `futureAvailable`
    // is `false` in every bundle -- so past the record there is nothing to be
    // late, and a layer that keeps drawing there is telling the reader that a
    // three-day-old absorption map is a statement about Friday. It is the same
    // missing state as the quiet one: the layer had no way to say it had run
    // out. `staleState` is what the aurora layer already does past its own
    // coverage, so this is the sibling behaviour rather than a new one.
    if (!bounds.next && selection.ageMinutes > DRAP_LIVE_EDGE_HOLD_MINUTES) {
      return this.staleState(requested, selection.frame, selection.ageMinutes);
    }
    return this.readyState(requested, selection.frame, selection.ageMinutes);
  }

  protected rgba(frame: DrapFrame) {
    return drapRgbaGrid(this.bundle, frame, { mode: this.displayMode });
  }
}

export class AuroraSurfaceLayerController extends EnvironmentSurfaceLayerController<AuroraBundle, AuroraFrame, AuroraDisplayMode> {
  constructor(bundle: AuroraBundle, options: EnvironmentSurfaceLayerOptions = {}) {
    super(bundle, AURORA_EMISSION_ALTITUDE_KM, options);
  }

  protected frames(): AuroraFrame[] { return this.bundle.frames; }
  protected frameValidAt(frame: AuroraFrame): string { return frame.validAt; }
  protected frameObservedAt(frame: AuroraFrame): string | null { return frame.observedAt; }
  protected latitudeStepDegrees(): number { return this.bundle.grid.latitudeStepDeg; }
  protected longitudeStartDegrees(): number { return this.bundle.grid.longitudeStartDeg; }
  protected longitudeStepDegrees(): number { return this.bundle.grid.longitudeStepDeg; }

  protected sourceRange(): EnvironmentSurfaceSourceRange {
    return frameSourceRange(this.bundle.frames, (frame) => frame.validAt, this.bundle.time.coverageComplete);
  }

  protected legend(validAt: string | null, observedAt: string | null): EnvironmentSurfaceLegend {
    return {
      product: this.bundle.product,
      title: "Aurora viewing probability",
      subtitle: "NOAA OVATION 2020 · probability",
      units: this.bundle.quantity.units,
      minimum: 0,
      maximum: 100,
      ticks: [0, 10, 25, 50, 75, 100],
      minimumLabel: "0% · no modeled viewing probability",
      maximumLabel: "100%",
      sourceUrl: this.bundle.source.currentNumericGrid,
      sourceStatus: "model",
      displayMode: this.displayMode,
      validAt,
      observedAt,
      sourceRange: this.sourceRange(),
    };
  }

  protected selectedFrame(requestedAt: Date | string | number): AuroraFrame | null {
    const selection = selectAuroraFrame(this.bundle, requestedAt);
    return selection.available ? selection.frame : null;
  }

  protected selectState(requestedAt: Date | string | number, requested: ParsedTime): EnvironmentSurfaceState {
    const selection = selectAuroraFrame(this.bundle, requestedAt);
    if (selection.available) return this.readyState(requested, selection.frame, selection.ageMinutes);
    const bounds = this.bounds(requested.ms);
    if (selection.reason === "after-coverage" && bounds.previous) {
      const ageMinutes = (requested.ms - Date.parse(bounds.previous.validAt)) / 60_000;
      return this.staleState(requested, bounds.previous, ageMinutes);
    }
    const reason: EnvironmentSurfaceNoDataReason = selection.reason === "invalid-time"
      ? "invalid-time"
      : selection.reason === "before-coverage"
        ? (this.bundle.frames.length ? "before-coverage" : "no-frames")
        : "gap";
    return this.noDataState(
      requested.iso,
      reason,
      selection.message,
      bounds.previous ? bounds.previous.validAt : null,
      bounds.next ? bounds.next.validAt : null,
    );
  }

  protected rgba(frame: AuroraFrame) {
    return auroraRgbaGrid(this.bundle, frame, { mode: this.displayMode });
  }
}

interface ParsedTime { ms: number; iso: string }

function parseRequestedTime(value: Date | string | number): ParsedTime | null {
  const ms = value instanceof Date ? value.getTime() : typeof value === "number" ? value : Date.parse(value);
  return Number.isFinite(ms) ? { ms, iso: new Date(ms).toISOString() } : null;
}

function frameSourceRange<TFrame>(
  frames: TFrame[],
  validAt: (frame: TFrame) => string,
  coverageComplete: boolean | null,
): EnvironmentSurfaceSourceRange {
  const validTimes = frames
    .map((frame) => validAt(frame))
    .filter((value) => Number.isFinite(Date.parse(value)))
    .sort((left, right) => Date.parse(left) - Date.parse(right));
  return {
    validFrom: validTimes[0] ?? null,
    validTo: validTimes.at(-1) ?? null,
    frameCount: validTimes.length,
    coverageComplete,
  };
}
