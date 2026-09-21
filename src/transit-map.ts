/**
 * The planner's 2-D view: an equirectangular SVG map you can click on.
 *
 * ## Why this is not `src/ground-track-map.ts`
 *
 * That module draws one satellite's ground track and is deliberately read-only,
 * with its own generalised coastline constant. This one has to accept clicks,
 * drag waypoints, draw a route, draw many satellites and their footprints, and
 * carry boundary overlays. Bolting all of that onto a display component would
 * have made both jobs worse, and that file is under active work by another
 * agent. The two share the projection convention and the UTC labelling
 * convention, which is the part that has to agree.
 *
 * ## Coastlines
 *
 * The real published Natural Earth land artifact the release already ships
 * (`manifest.land`), the same one the globe uses — not the eight generalised
 * polygons in `ground-track-map.ts`. A planner that draws a waypoint 200 km
 * inland because the coast is a straight line between two hand-typed vertices is
 * worse than no map.
 *
 * ## Projection
 *
 * Plate carrée: x is linear in longitude, y is linear in latitude. Chosen
 * because it is the one projection where "click here" and "this is the latitude
 * and longitude" are the same statement, and because the planner's job is
 * reading times off a track rather than measuring areas. It badly distorts
 * high-latitude distance, so the map says so and the great-circle track is drawn
 * densified, which is what makes the distortion legible instead of hidden.
 *
 * ## Zoom
 *
 * The world is drawn once at 1000x500 and a transform on one group does all the
 * zooming and panning, so nothing is reprojected and a click at 16x resolves to
 * the same latitude and longitude it resolves to at 1x. Strokes carry
 * `non-scaling-stroke` and markers are divided by the scale, so a coastline
 * stays a hairline and a waypoint pip stays a pip.
 */

import type { LandGeoJson } from "./globe";
import { normalizeLongitudeDeg, routePolyline, type TransitRoute, type Waypoint } from "./transit-route";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

export interface MapPadding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

const DEFAULT_PADDING: MapPadding = { top: 10, right: 10, bottom: 10, left: 10 };

export interface TransitMapOptions {
  container: HTMLElement;
  land: LandGeoJson;
  width?: number;
  height?: number;
  onMapClick?: (latitudeDeg: number, longitudeDeg: number) => void;
  onWaypointClick?: (waypointId: string) => void;
  onWaypointDrag?: (waypointId: string, latitudeDeg: number, longitudeDeg: number) => void;
}

export interface SatelliteMarker {
  id: number;
  name: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
  colorHex: string;
  /** Above the mask from the current route position. */
  visible: boolean;
}

export interface BoundaryOverlay {
  id: string;
  label: string;
  colorHex: string;
  /** Rings of [longitude, latitude] pairs. */
  rings: ReadonlyArray<ReadonlyArray<readonly [number, number]>>;
  labelAt: readonly [number, number] | null;
  /**
   * Sides whose limit the source named as a landmark or an approximation rather
   * than as a line — "the Kuril Islands in the North", "approximately half of
   * the Atlantic Ocean". Those edges are drawn open and faded, because a solid
   * line there would assert a boundary nobody published.
   */
  indefiniteEdges: readonly string[];
}

export interface TransitMapState {
  route: TransitRoute;
  selectedWaypointId: string | null;
  /** Route position at the scrubbed time, if the time is inside the transit. */
  currentPosition: { latitudeDeg: number; longitudeDeg: number; timeMs: number } | null;
  satellites: readonly SatelliteMarker[];
  /** Footprint boundary rings for satellites, already computed by the caller. */
  footprints: ReadonlyArray<{ id: number; colorHex: string; points: Array<[number, number]> }>;
  boundaries: readonly BoundaryOverlay[];
  showOnlyVisible: boolean;
}

/**
 * Longitude for PROJECTION, which is not the same thing as longitude on a sphere.
 *
 * `normalizeLongitudeDeg` sends +180 to -180. That is right on a globe, where
 * they are one meridian, and wrong on a sheet, where they are its two opposite
 * edges. Every projected point used to go through the sphere's normaliser, so
 * the +180 vertices `splitAtAntimeridian` inserts at a date-line crossing were
 * drawn on the WESTERN edge — and the segment reaching them was drawn straight
 * back across the whole map.
 *
 * Measured on the shipped page before the fix: the Pearl Harbor transit was
 * drawn as a line from x=10 to x=988 through Africa and Asia; Wrangel Island
 * (71 N) and Fiji (17 S), the two land polygons in Natural Earth 1:110m that
 * straddle the date line, each drew a horizontal band the full width of the
 * map; and the U.S. 7th Fleet area, whose published eastern limit IS the
 * International Date Line, was drawn inside out, covering the Atlantic instead
 * of the western Pacific.
 *
 * Anything already inside [-180, 180] is returned untouched, so this changes
 * nothing except which edge the seam lands on.
 */
export function projectionLongitudeDeg(longitudeDeg: number): number {
  if (longitudeDeg >= -180 && longitudeDeg <= 180) return longitudeDeg;
  return normalizeLongitudeDeg(longitudeDeg);
}

export function projectToMap(
  longitudeDeg: number,
  latitudeDeg: number,
  width: number,
  height: number,
  padding: MapPadding = DEFAULT_PADDING,
): { x: number; y: number } {
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  return {
    x: padding.left + ((projectionLongitudeDeg(longitudeDeg) + 180) / 360) * plotWidth,
    y: padding.top + ((90 - latitudeDeg) / 180) * plotHeight,
  };
}

export function unprojectFromMap(
  x: number,
  y: number,
  width: number,
  height: number,
  padding: MapPadding = DEFAULT_PADDING,
): { latitudeDeg: number; longitudeDeg: number } {
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const longitudeDeg = ((x - padding.left) / plotWidth) * 360 - 180;
  const latitudeDeg = 90 - ((y - padding.top) / plotHeight) * 180;
  return {
    latitudeDeg: Math.max(-90, Math.min(90, latitudeDeg)),
    longitudeDeg: normalizeLongitudeDeg(longitudeDeg),
  };
}

/**
 * Break a lon/lat path wherever it jumps the antimeridian, inserting the
 * crossing point on both sides so nothing is drawn straight across the map.
 *
 * This is the same failure `segmentGroundTrack` exists to prevent in
 * `ground-track-map.ts`; a planner draws far more paths than that module does,
 * so it needs its own.
 */
export function splitAtAntimeridian(
  points: ReadonlyArray<readonly [number, number]>,
): Array<Array<[number, number]>> {
  if (points.length === 0) return [];
  // `projectionLongitudeDeg`, NOT `normalizeLongitudeDeg`: the latter sends +180
  // to -180, so a shape whose published limit IS the Date Line — the U.S. 7th
  // Fleet area, whose eastern edge is a column of +180 vertices — had a
  // crossing inserted at every one of them and was cut into pieces that spanned
  // the whole map. Nothing else in the range moves.
  const segments: Array<Array<[number, number]>> = [[[projectionLongitudeDeg(points[0]![0]), points[0]![1]]]];
  for (let index = 1; index < points.length; index += 1) {
    const previous = segments.at(-1)!.at(-1)!;
    const rawLongitude = projectionLongitudeDeg(points[index]![0]);
    const latitude = points[index]![1];
    const delta = rawLongitude - previous[0];
    if (Math.abs(delta) <= 180) {
      segments.at(-1)!.push([rawLongitude, latitude]);
      continue;
    }
    const crossesEast = delta < -180;
    const unwrapped = rawLongitude + (crossesEast ? 360 : -360);
    const boundary = crossesEast ? 180 : -180;
    const span = unwrapped - previous[0];
    const fraction = Math.abs(span) < 1e-12 ? 0 : (boundary - previous[0]) / span;
    const crossingLatitude = previous[1] + (latitude - previous[1]) * fraction;
    segments.at(-1)!.push([boundary, crossingLatitude]);
    segments.push([[-boundary, crossingLatitude], [rawLongitude, latitude]]);
  }
  return segments.filter((segment) => segment.length > 1);
}

/**
 * The same split, for a CLOSED ring that is going to be filled.
 *
 * A ring that straddles the date line is cut into three pieces: the run up to
 * the first crossing, the piece on the far side, and the run back from the
 * second crossing to where the ring started. The first and third are the same
 * piece of land — the ring is closed, so its end joins its start — and leaving
 * them as two open subpaths makes SVG close each one with a straight chord back
 * to its own first point. That chord is a diagonal band across the interior:
 * measured on the shipped page, one ran from central Siberia to the Bering
 * Strait, right across Russia.
 *
 * Joining them puts both ends of every piece on the SAME map edge, where the
 * implicit closing line runs along the edge and fills correctly.
 */
export function splitRingAtAntimeridian(
  ring: ReadonlyArray<readonly [number, number]>,
): Array<Array<[number, number]>> {
  const pieces = splitAtAntimeridian(ring);
  if (pieces.length < 2) return pieces;
  const first = ring[0]!;
  const last = ring[ring.length - 1]!;
  const isClosed = Math.abs(projectionLongitudeDeg(first[0]) - projectionLongitudeDeg(last[0])) < 1e-9
    && Math.abs(first[1] - last[1]) < 1e-9;
  if (!isClosed) return pieces;
  const head = pieces[0]!;
  const tail = pieces[pieces.length - 1]!;
  // The tail ends where the head begins, so drop the repeated vertex.
  const joined = [...tail, ...head.slice(1)];
  return [joined, ...pieces.slice(1, -1)];
}

function element<K extends keyof SVGElementTagNameMap>(
  tagName: K,
  attributes: Record<string, string> = {},
  text?: string,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NAMESPACE, tagName);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

const round = (value: number) => Math.round(value * 100) / 100;

/**
 * Zoom limits. 1 is the whole world; 16 puts a strait across the panel, which is
 * the scale at which "does this leg clear that headland" is a question a map can
 * answer. Above that the 1:110m coastline is generalised past the point where a
 * closer look tells the truth, so the tool stops rather than pretending.
 */
export const MINIMUM_MAP_SCALE = 1;
export const MAXIMUM_MAP_SCALE = 16;

/**
 * Pan/zoom state, as a transform on the world group.
 *
 * Kept in world units rather than screen pixels so it survives a resize: the SVG
 * has a fixed 1000x500 viewBox and scales itself to whatever box CSS gives it.
 */
export interface MapView {
  scale: number;
  translateX: number;
  translateY: number;
}

/** Keep the panned world covering the frame, so no zoom can expose the void. */
export function clampView(view: MapView, width: number, height: number): MapView {
  const scale = Math.max(MINIMUM_MAP_SCALE, Math.min(MAXIMUM_MAP_SCALE, view.scale));
  const minimumX = width - width * scale;
  const minimumY = height - height * scale;
  return {
    scale,
    translateX: Math.max(minimumX, Math.min(0, view.translateX)),
    translateY: Math.max(minimumY, Math.min(0, view.translateY)),
  };
}

export class TransitMap {
  private readonly svg: SVGSVGElement;
  private readonly wrapper: HTMLElement;
  private readonly width: number;
  private readonly height: number;
  private readonly padding = DEFAULT_PADDING;
  private readonly world = element("g", { "data-layer": "world" });
  private readonly staticLayer: SVGGElement;
  private readonly boundaryLayer = element("g", { "data-layer": "boundaries" });
  private readonly footprintLayer = element("g", { "data-layer": "footprints" });
  private readonly satelliteLayer = element("g", { "data-layer": "satellites" });
  private readonly routeLayer = element("g", { "data-layer": "route" });
  private readonly scaleReadout: HTMLElement;
  private readonly options: TransitMapOptions;
  private draggingWaypointId: string | null = null;
  private view: MapView = { scale: 1, translateX: 0, translateY: 0 };
  private lastState: TransitMapState | null = null;
  /** Live pointers, so a two-finger pinch can be told from a one-finger pan. */
  private readonly pointers = new Map<number, { x: number; y: number }>();
  private panFrom: { x: number; y: number; translateX: number; translateY: number } | null = null;
  private pinchFrom: { distance: number; scale: number } | null = null;
  private pointerTravel = 0;

  constructor(options: TransitMapOptions) {
    this.options = options;
    this.width = options.width ?? 1000;
    this.height = options.height ?? 500;
    this.svg = element("svg", {
      viewBox: `0 0 ${this.width} ${this.height}`,
      preserveAspectRatio: "xMidYMid meet",
      role: "application",
      "aria-label": "Transit route map. Click to place a waypoint, drag a waypoint to move it, "
        + "scroll or pinch to zoom, drag the map to pan.",
      tabindex: "0",
      class: "transit-map-svg",
    });

    this.svg.append(element("rect", {
      x: "0", y: "0", width: String(this.width), height: String(this.height),
      fill: "#061a25", rx: "10",
    }));

    this.staticLayer = element("g", { "data-layer": "static" });
    this.drawGraticule();
    this.drawLand(options.land);
    this.world.append(
      this.staticLayer,
      this.boundaryLayer,
      this.footprintLayer,
      this.satelliteLayer,
      this.routeLayer,
    );
    this.svg.append(this.world);

    this.svg.addEventListener("pointerdown", this.handlePointerDown);
    this.svg.addEventListener("pointermove", this.handlePointerMove);
    this.svg.addEventListener("pointerup", this.handlePointerUp);
    this.svg.addEventListener("pointercancel", this.handlePointerUp);
    this.svg.addEventListener("wheel", this.handleWheel, { passive: false });
    this.svg.addEventListener("dblclick", this.handleDoubleClick);
    this.svg.addEventListener("keydown", this.handleKeyDown);

    this.wrapper = document.createElement("div");
    this.wrapper.className = "transit-map-wrap";
    this.wrapper.append(this.svg, this.buildZoomControls());
    this.scaleReadout = this.wrapper.querySelector<HTMLElement>("[data-map-scale]")!;
    options.container.replaceChildren(this.wrapper);
    this.applyView();
  }

  get element(): SVGSVGElement {
    return this.svg;
  }

  // -------------------------------------------------------------------------
  // Zoom and pan
  //
  // Sean, on the shipped page: "The map isn't zoomable. Why?" It had no zoom
  // affordance of any kind — a fixed 0 0 1000 500 viewBox and nothing that could
  // change it, so a Pacific transit was drawn 12 px wide and the reader could
  // not check a single leg against a coast. The geometry is unchanged; only the
  // transform on the world group moves, so a waypoint dropped at zoom 12 lands
  // on exactly the latitude and longitude it looks like it lands on.
  // -------------------------------------------------------------------------

  private buildZoomControls(): HTMLElement {
    const bar = document.createElement("div");
    bar.className = "transit-map-zoom";
    bar.innerHTML = `
      <button type="button" data-map-zoom="in" aria-label="Zoom in">+</button>
      <button type="button" data-map-zoom="out" aria-label="Zoom out">\u2212</button>
      <span class="transit-map-scale" data-map-scale aria-live="polite">1\u00d7</span>
      <button type="button" data-map-zoom="reset">Whole world</button>`;
    bar.querySelectorAll<HTMLButtonElement>("[data-map-zoom]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const action = button.dataset.mapZoom;
        if (action === "reset") this.setView({ scale: 1, translateX: 0, translateY: 0 });
        else {
          const anchor = this.focusPoint();
          this.zoomAbout(anchor.x, anchor.y, action === "in" ? 1.6 : 1 / 1.6);
        }
      });
    });
    return bar;
  }

  /**
   * What the zoom buttons zoom TOWARD.
   *
   * The centre of a plate carrée sheet is 0 N 0 E — the Gulf of Guinea — and
   * zooming a Pacific transit toward it lands the reader in empty ocean six
   * thousand miles from anything they are looking at. The anchor is the ship's
   * scrubbed position if there is one, else the first waypoint, else the middle
   * of the map. Wheel and pinch anchor on the pointer, which is its own answer
   * to the same question.
   */
  private focusPoint(): { x: number; y: number } {
    const state = this.lastState;
    const position = state?.currentPosition ?? state?.route.waypoints[0];
    if (!position) return { x: this.width / 2, y: this.height / 2 };
    const projected = this.point(position.longitudeDeg, position.latitudeDeg);
    // In world units the anchor has to be expressed where it currently DRAWS.
    return {
      x: projected.x * this.view.scale + this.view.translateX,
      y: projected.y * this.view.scale + this.view.translateY,
    };
  }

  /** Zoom keeping the world point under (x, y) in local units under it still. */
  private zoomAbout(x: number, y: number, factor: number) {
    const next = Math.max(MINIMUM_MAP_SCALE, Math.min(MAXIMUM_MAP_SCALE, this.view.scale * factor));
    const ratio = next / this.view.scale;
    this.setView({
      scale: next,
      translateX: x - (x - this.view.translateX) * ratio,
      translateY: y - (y - this.view.translateY) * ratio,
    });
  }

  private setView(view: MapView) {
    const clamped = clampView(view, this.width, this.height);
    if (clamped.scale === this.view.scale
      && clamped.translateX === this.view.translateX
      && clamped.translateY === this.view.translateY) return;
    this.view = clamped;
    this.applyView();
    // Markers carry their size in world units, so they have to be redrawn at the
    // new scale or a waypoint pip becomes a dinner plate at 16x.
    if (this.lastState) this.render(this.lastState);
  }

  private applyView() {
    this.world.setAttribute(
      "transform",
      `translate(${round(this.view.translateX)},${round(this.view.translateY)}) scale(${round(this.view.scale)})`,
    );
    if (this.scaleReadout) {
      this.scaleReadout.textContent = `${this.view.scale < 10 ? this.view.scale.toFixed(1) : Math.round(this.view.scale)}\u00d7`;
    }
    this.wrapper?.classList.toggle("is-zoomed", this.view.scale > 1.001);
  }

  /** Screen point to the SVG's own local units, before the world transform. */
  private localPoint(event: { clientX: number; clientY: number }): { x: number; y: number } | null {
    const matrix = this.svg.getScreenCTM();
    if (!matrix) return null;
    const point = this.svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    return { x: local.x, y: local.y };
  }

  private handleWheel = (event: WheelEvent) => {
    const local = this.localPoint(event);
    if (!local) return;
    event.preventDefault();
    this.zoomAbout(local.x, local.y, Math.exp(-event.deltaY * 0.0016));
  };

  private handleDoubleClick = (event: MouseEvent) => {
    const local = this.localPoint(event);
    if (!local) return;
    event.preventDefault();
    this.zoomAbout(local.x, local.y, event.shiftKey ? 1 / 2 : 2);
  };

  private handleKeyDown = (event: KeyboardEvent) => {
    const step = 60 / this.view.scale;
    const anchor = this.focusPoint();
    if (event.key === "+" || event.key === "=") this.zoomAbout(anchor.x, anchor.y, 1.6);
    else if (event.key === "-") this.zoomAbout(anchor.x, anchor.y, 1 / 1.6);
    else if (event.key === "0") this.setView({ scale: 1, translateX: 0, translateY: 0 });
    else if (event.key === "ArrowLeft") this.setView({ ...this.view, translateX: this.view.translateX + step });
    else if (event.key === "ArrowRight") this.setView({ ...this.view, translateX: this.view.translateX - step });
    else if (event.key === "ArrowUp") this.setView({ ...this.view, translateY: this.view.translateY + step });
    else if (event.key === "ArrowDown") this.setView({ ...this.view, translateY: this.view.translateY - step });
    else return;
    event.preventDefault();
  };

  /** Convert a pointer event to geographic coordinates via the world group's CTM. */
  private eventToGeographic(event: PointerEvent): { latitudeDeg: number; longitudeDeg: number } | null {
    const matrix = this.world.getScreenCTM();
    if (!matrix) return null;
    const point = this.svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    return unprojectFromMap(local.x, local.y, this.width, this.height, this.padding);
  }

  private handlePointerDown = (event: PointerEvent) => {
    this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const target = event.target as Element;
    const waypointId = target.closest("[data-waypoint-id]")?.getAttribute("data-waypoint-id");
    if (waypointId && this.pointers.size === 1) {
      this.draggingWaypointId = waypointId;
      this.svg.setPointerCapture(event.pointerId);
      this.options.onWaypointClick?.(waypointId);
      event.preventDefault();
      return;
    }
    if (this.pointers.size === 2) {
      this.panFrom = null;
      this.pinchFrom = { distance: this.pointerSpread(), scale: this.view.scale };
      return;
    }
    // A press on the map is only a waypoint once the pointer comes up without
    // having travelled: the same gesture has to be able to pan, and adding a
    // waypoint every time somebody dragged the map would be unusable.
    const local = this.localPoint(event);
    if (!local) return;
    this.pointerTravel = 0;
    this.panFrom = { x: local.x, y: local.y, translateX: this.view.translateX, translateY: this.view.translateY };
    this.svg.setPointerCapture(event.pointerId);
  };

  private pointerSpread(): number {
    const [a, b] = [...this.pointers.values()];
    if (!a || !b) return 0;
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  private pointerMidpoint(): { clientX: number; clientY: number } | null {
    const [a, b] = [...this.pointers.values()];
    if (!a || !b) return null;
    return { clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 };
  }

  private handlePointerMove = (event: PointerEvent) => {
    if (this.pointers.has(event.pointerId)) {
      this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    }
    if (this.pinchFrom && this.pointers.size === 2) {
      const spread = this.pointerSpread();
      if (spread <= 0 || this.pinchFrom.distance <= 0) return;
      const midpoint = this.pointerMidpoint();
      const local = midpoint ? this.localPoint(midpoint) : null;
      if (!local) return;
      const wanted = this.pinchFrom.scale * (spread / this.pinchFrom.distance);
      this.zoomAbout(local.x, local.y, wanted / this.view.scale);
      return;
    }
    if (this.draggingWaypointId) {
      const geographic = this.eventToGeographic(event);
      if (!geographic) return;
      this.options.onWaypointDrag?.(this.draggingWaypointId, geographic.latitudeDeg, geographic.longitudeDeg);
      return;
    }
    if (!this.panFrom) return;
    const local = this.localPoint(event);
    if (!local) return;
    this.pointerTravel += Math.hypot(local.x - this.panFrom.x, local.y - this.panFrom.y);
    // The translate is in the SVG's OWN units, on the outside of the scale:
    // a world point w draws at s*w + t, so holding w under the pointer means
    // t moves by exactly the pointer's travel in those units. Multiplying that
    // travel by the scale — which this did until 2026-09-08 — made the map
    // slide `scale` times faster than the finger, so at 16x a drag of a few
    // pixels threw the view straight to whichever edge `clampView` allowed and
    // the strait the reader had zoomed in on was gone. `zoomAbout` above solves
    // the same equation and has always had it right.
    this.setView({
      scale: this.view.scale,
      translateX: this.panFrom.translateX + (local.x - this.panFrom.x),
      translateY: this.panFrom.translateY + (local.y - this.panFrom.y),
    });
  };

  private handlePointerUp = (event: PointerEvent) => {
    this.pointers.delete(event.pointerId);
    if (this.svg.hasPointerCapture(event.pointerId)) this.svg.releasePointerCapture(event.pointerId);
    if (this.pointers.size < 2) this.pinchFrom = null;
    if (this.draggingWaypointId) {
      this.draggingWaypointId = null;
      this.panFrom = null;
      return;
    }
    // Under 4 local units of travel is a click, not a pan.
    if (this.panFrom && this.pointerTravel < 4) {
      const geographic = this.eventToGeographic(event);
      if (geographic) this.options.onMapClick?.(geographic.latitudeDeg, geographic.longitudeDeg);
    }
    this.panFrom = null;
    this.pointerTravel = 0;
  };

  private point(longitudeDeg: number, latitudeDeg: number) {
    return projectToMap(longitudeDeg, latitudeDeg, this.width, this.height, this.padding);
  }

  /** World units per screen unit: what a marker has to divide by to hold its size. */
  private get markerScale(): number {
    return 1 / this.view.scale;
  }

  private pathFrom(points: ReadonlyArray<readonly [number, number]>): string {
    return this.pathPieces(splitAtAntimeridian(points));
  }

  /** Same, for a closed ring that will be filled. See splitRingAtAntimeridian. */
  private ringPathFrom(points: ReadonlyArray<readonly [number, number]>): string {
    return this.pathPieces(splitRingAtAntimeridian(points), true);
  }

  private pathPieces(pieces: Array<Array<[number, number]>>, close = false): string {
    return pieces
      .map((segment) => segment
        .map(([longitude, latitude], index) => {
          const projected = this.point(longitude, latitude);
          return `${index === 0 ? "M" : "L"}${round(projected.x)},${round(projected.y)}`;
        })
        .join(" ") + (close ? " Z" : ""))
      .join(" ");
  }

  private drawGraticule() {
    for (let longitude = -180; longitude <= 180; longitude += 30) {
      const top = this.point(longitude, 90);
      const bottom = this.point(longitude, -90);
      this.staticLayer.append(element("line", {
        x1: String(round(top.x)), y1: String(round(top.y)),
        x2: String(round(bottom.x)), y2: String(round(bottom.y)),
        stroke: "#2c4d5e", "stroke-width": "0.6", opacity: "0.6",
        "vector-effect": "non-scaling-stroke",
      }));
    }
    for (let latitude = -60; latitude <= 60; latitude += 30) {
      const left = this.point(-180, latitude);
      const right = this.point(180, latitude);
      this.staticLayer.append(element("line", {
        x1: String(round(left.x)), y1: String(round(left.y)),
        x2: String(round(right.x)), y2: String(round(right.y)),
        stroke: "#2c4d5e", "stroke-width": latitude === 0 ? "1" : "0.6",
        opacity: latitude === 0 ? "0.8" : "0.6",
        "vector-effect": "non-scaling-stroke",
      }));
    }
  }

  private drawLand(land: LandGeoJson) {
    for (const feature of land.features) {
      const polygons = feature.geometry.type === "Polygon"
        ? [feature.geometry.coordinates as unknown as number[][][]]
        : feature.geometry.coordinates as unknown as number[][][][];
      for (const polygon of polygons) {
        for (const ring of polygon) {
          const points = ring.map((coordinate) => [coordinate[0] ?? 0, coordinate[1] ?? 0] as [number, number]);
          const path = this.ringPathFrom(points);
          if (!path) continue;
          this.staticLayer.append(element("path", {
            d: path,
            fill: "#12313d",
            stroke: "#3d6d7d",
            "stroke-width": "0.7",
            "fill-rule": "evenodd",
            "vector-effect": "non-scaling-stroke",
          }));
        }
      }
    }
  }

  render(state: TransitMapState) {
    this.lastState = state;
    this.renderBoundaries(state.boundaries);
    this.renderFootprints(state);
    this.renderSatellites(state);
    this.renderRoute(state);
  }

  private renderBoundaries(boundaries: readonly BoundaryOverlay[]) {
    this.boundaryLayer.replaceChildren();
    for (const boundary of boundaries) {
      // Any indefinite edge softens the whole outline, and the fill is what
      // carries the area. Drawing three crisp sides and one faded one reads as a
      // rendering glitch; a uniformly softer outline plus the per-edge note in
      // the panel reads as what it is - an area whose limits are partly unstated.
      const anyIndefinite = boundary.indefiniteEdges.length > 0;
      for (const ring of boundary.rings) {
        const path = this.ringPathFrom(ring);
        if (!path) continue;
        this.boundaryLayer.append(element("path", {
          d: path,
          fill: boundary.colorHex,
          "fill-opacity": anyIndefinite ? "0.05" : "0.09",
          stroke: boundary.colorHex,
          "stroke-width": anyIndefinite ? "1.1" : "1.6",
          "stroke-dasharray": anyIndefinite ? "3 6" : "9 4",
          "stroke-opacity": anyIndefinite ? "0.55" : "0.9",
          "vector-effect": "non-scaling-stroke",
        }));
      }
      if (boundary.labelAt) {
        const at = this.point(boundary.labelAt[0], boundary.labelAt[1]);
        const k = this.markerScale;
        this.boundaryLayer.append(element("text", {
          x: String(round(at.x)), y: String(round(at.y)),
          fill: boundary.colorHex,
          "font-family": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          "font-size": String(round(11 * k)), "font-weight": "700", "letter-spacing": "0.07em",
          "text-anchor": "middle",
          style: `paint-order:stroke;stroke:#061a25;stroke-width:${round(3.5 * k)}px;stroke-linejoin:round`,
        }, anyIndefinite ? `${boundary.label} ·` : boundary.label));
      }
    }
  }

  private renderFootprints(state: TransitMapState) {
    this.footprintLayer.replaceChildren();
    for (const footprint of state.footprints) {
      const path = this.ringPathFrom(footprint.points);
      if (!path) continue;
      this.footprintLayer.append(element("path", {
        d: path,
        fill: footprint.colorHex,
        "fill-opacity": "0.09",
        stroke: footprint.colorHex,
        "stroke-width": "1",
        "stroke-opacity": "0.55",
        "vector-effect": "non-scaling-stroke",
      }));
    }
  }

  private renderSatellites(state: TransitMapState) {
    this.satelliteLayer.replaceChildren();
    const k = this.markerScale;
    for (const satellite of state.satellites) {
      if (state.showOnlyVisible && !satellite.visible) continue;
      const at = this.point(satellite.longitudeDeg, satellite.latitudeDeg);
      const marker = element("g", { "data-satellite-id": String(satellite.id) });
      marker.append(
        element("circle", {
          cx: String(round(at.x)), cy: String(round(at.y)),
          r: String(round((satellite.visible ? 4.2 : 2.6) * k)),
          fill: satellite.colorHex,
          "fill-opacity": satellite.visible ? "1" : "0.32",
          stroke: "#04131c",
          "stroke-width": String(round((satellite.visible ? 1.4 : 0.7) * k)),
        }),
        element("title", {}, `${satellite.name} — ${satellite.visible ? "above your mask" : "below your mask"}`),
      );
      this.satelliteLayer.append(marker);
    }
  }

  private renderRoute(state: TransitMapState) {
    this.routeLayer.replaceChildren();
    const k = this.markerScale;
    const vertices = routePolyline(state.route);
    if (vertices.length > 1) {
      const path = this.pathFrom(vertices.map((vertex) => [vertex.longitudeDeg, vertex.latitudeDeg] as [number, number]));
      this.routeLayer.append(
        element("path", { d: path, fill: "none", stroke: "#04131c", "stroke-width": "6", "stroke-linecap": "round", "stroke-linejoin": "round", opacity: "0.75", "vector-effect": "non-scaling-stroke" }),
        element("path", { d: path, fill: "none", stroke: "#45eadb", "stroke-width": "2.6", "stroke-linecap": "round", "stroke-linejoin": "round", "vector-effect": "non-scaling-stroke" }),
      );
    }

    state.route.waypoints.forEach((waypoint, index) => {
      const at = this.point(waypoint.longitudeDeg, waypoint.latitudeDeg);
      const selected = waypoint.id === state.selectedWaypointId;
      const marker = element("g", {
        "data-waypoint-id": waypoint.id,
        role: "button",
        tabindex: "0",
        "aria-label": `Waypoint ${index + 1}, ${describeWaypoint(waypoint)}`,
        style: "cursor:grab",
      });
      marker.append(
        element("circle", {
          cx: String(round(at.x)), cy: String(round(at.y)),
          r: String(round((selected ? 9 : 6.5) * k)),
          fill: selected ? "#ffd479" : "#0b2a38",
          stroke: selected ? "#ffffff" : "#45eadb",
          "stroke-width": String(round((selected ? 2.6 : 2) * k)),
        }),
        element("text", {
          x: String(round(at.x)), y: String(round(at.y + 3.6 * k)),
          "text-anchor": "middle",
          fill: selected ? "#08202b" : "#d7edf4",
          "font-family": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          "font-size": String(round(9.5 * k)), "font-weight": "700",
          style: "pointer-events:none",
        }, String(index + 1)),
        element("title", {}, describeWaypoint(waypoint)),
      );
      this.routeLayer.append(marker);
    });

    if (state.currentPosition) {
      const at = this.point(state.currentPosition.longitudeDeg, state.currentPosition.latitudeDeg);
      this.routeLayer.append(
        element("circle", {
          cx: String(round(at.x)), cy: String(round(at.y)), r: String(round(10 * k)),
          fill: "none", stroke: "#ffffff", "stroke-width": String(round(1.6 * k)), opacity: "0.6",
        }),
        element("circle", {
          cx: String(round(at.x)), cy: String(round(at.y)), r: String(round(4.5 * k)),
          fill: "#ffffff", stroke: "#45eadb", "stroke-width": String(round(2 * k)),
        }),
      );
    }
  }

  destroy() {
    this.svg.removeEventListener("pointerdown", this.handlePointerDown);
    this.svg.removeEventListener("pointermove", this.handlePointerMove);
    this.svg.removeEventListener("pointerup", this.handlePointerUp);
    this.svg.removeEventListener("pointercancel", this.handlePointerUp);
    this.svg.removeEventListener("wheel", this.handleWheel);
    this.svg.removeEventListener("dblclick", this.handleDoubleClick);
    this.svg.removeEventListener("keydown", this.handleKeyDown);
    this.wrapper.remove();
  }
}

export function describeWaypoint(waypoint: Waypoint): string {
  return `${waypoint.label}: ${formatLatitude(waypoint.latitudeDeg)} ${formatLongitude(waypoint.longitudeDeg)} at ${formatUtc(waypoint.timeMs)}`;
}

export function formatLatitude(latitudeDeg: number): string {
  const degrees = Math.abs(latitudeDeg);
  const whole = Math.floor(degrees);
  const minutes = (degrees - whole) * 60;
  return `${String(whole).padStart(2, "0")}°${minutes.toFixed(1).padStart(4, "0")}'${latitudeDeg >= 0 ? "N" : "S"}`;
}

export function formatLongitude(longitudeDeg: number): string {
  const normalized = normalizeLongitudeDeg(longitudeDeg);
  const degrees = Math.abs(normalized);
  const whole = Math.floor(degrees);
  const minutes = (degrees - whole) * 60;
  return `${String(whole).padStart(3, "0")}°${minutes.toFixed(1).padStart(4, "0")}'${normalized >= 0 ? "E" : "W"}`;
}

export function formatUtc(timeMs: number): string {
  const iso = new Date(timeMs).toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}Z`;
}
