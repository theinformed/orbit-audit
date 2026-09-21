import * as THREE from "three";

import type { SubstormState } from "./substorm-chain";

/**
 * The INNER plasma sheet — the part of the tail that delivers, drawn on the
 * globe.
 *
 * ## Why only the inner part
 *
 * Sean: *"you don't need to draw all of it, just the portion where particles
 * are drawn back into the earth, right?"* That is the right crop twice over.
 *
 * Pedagogically, the far tail is where flux is STORED and the inner sheet is
 * where it is DELIVERED, and delivery is what has consequences — the aurora and
 * the ring current. Optically, it is the only part of the tail the scene's
 * shared ruler renders honestly. `radial-ruler.ts` is logarithmic below
 * geostationary orbit, LINEAR from 6.6 to 13 Re, and tapering beyond, so:
 *
 *   feature                       drawn extent at 1440, Earth radius 68 px
 *   ------------------------------------------------------------------
 *   inner plasma sheet 6-12 Re     117 px, from 154 px to 271 px out
 *   its inner edge, 10 -> 6.6 Re    70 px of travel
 *   its half-thickness 0.7-2 Re     16 to 45 px
 *   ---- for comparison, what had to be pulled ----
 *   plasmasphere L 2-5              26 px annulus
 *   plasmapause over 48 h            5 px of travel
 *
 * The plasmasphere failed because L 4 is deep in the log branch, where the
 * ruler's gain is 0.092. The inner sheet sits almost entirely in the linear
 * band, gain 0.332, and it is a physically enormous object. It reads.
 *
 * ## What is measured and what is drawn
 *
 * **Drawn — EMPIRICAL.** Every dimension here. Nobody measures the plasma
 * sheet's three-dimensional shape continuously, and this does not pretend to:
 * the inner edge, the cross-tail extent, the thickness and the way they change
 * are a standard empirical description of a substorm, not a fit to anything
 * this site fetches. The card says so and the badge says so.
 *
 * **Measured — the timing and the intensity.** Every one of them comes from
 * `substorm-chain.ts`, which takes them from published series: southward Bz at
 * Earth arrival for the loading, an auroral-electrojet index for the onset
 * where the site has one, Dst for the ring-current response. The sheet thins
 * because Bz measurably turned south. It snaps because SML measurably dropped.
 * If neither is available for the instant being drawn, `injection` is zero and
 * nothing snaps.
 *
 * ## The one number here that IS a measurement
 *
 * The sheet's centre is not at z = 0. With the dipole tilted by psi the
 * magnetic equator plane satisfies `x sin(psi) + z cos(psi) = 0`, so at
 * x = -10 Re the sheet centre sits at `z = +10 tan(psi)` — about 3.6 Re above
 * the GSM equator at a 20 degree tilt. NOAA's own operational solution puts it
 * about 3 Re up under a tilted dipole, which is the corroboration, and it is
 * the reason the equatorial cut through this region so often shows the LOBE
 * rather than the sheet. Beyond `HINGE_DISTANCE_RE` the real sheet flattens
 * back toward the GSM equator rather than following the dipole out forever,
 * and the hinge is applied here rather than left off.
 */

/**
 * Where the drawn region stops, down-tail. The far tail is not this layer.
 *
 * 14 rather than 12, and the reason is measured. The near-Earth neutral line
 * forms out around 15-25 Re, so anywhere in 12-15 is defensibly the outer end
 * of the INJECTION region rather than the storage tail. What decided it was
 * what a fully loaded growth phase has left to draw: with the outer edge at 12
 * and the loaded inner edge at 11, the whole sheet collapses to a 23-pixel
 * sliver at 1440 and the growth phase becomes invisible - which is the phase a
 * reader most needs to watch, because it is the one that ends in the snap. At
 * 14 the loaded sheet is 67 pixels deep and the expanded one 159, and the inner
 * edge still travels 92 pixels between them.
 */
export const OUTER_EDGE_RE = 14;

/**
 * How far earthward the inner edge of the hot population comes, in Earth radii.
 *
 * The inner edge moves EARTHWARD through the whole cycle, and it is worth being
 * careful about that, because the first version of this module had it retreating
 * during the growth phase and that is backwards. Enhanced convection during a
 * growth phase transports plasma sunward, so the measured inner edge of the
 * plasma sheet comes IN; at onset it jumps in much further, which is precisely
 * why a substorm is felt at geostationary orbit as an injection.
 *
 * What the growth phase does do is THIN the near-Earth current sheet, and that
 * is the counter-intuitive half a reader needs told: the tail is being loaded
 * and the sheet is getting thinner, not fatter, until it reconnects.
 */
export const INNER_EDGE_QUIET_RE = 11;
export const INNER_EDGE_LOADED_RE = 9;
export const INNER_EDGE_INJECTED_RE = 6.6;

/**
 * Half-thickness at the outer edge, in Earth radii.
 *
 * Quiet is moderately thick; a loaded growth phase thins it — that thinning is
 * what ends in reconnection; onset thickens it as the field dipolarises.
 */
export const HALF_THICKNESS_QUIET_RE = 1.8;
export const HALF_THICKNESS_THIN_RE = 0.7;
export const HALF_THICKNESS_THICK_RE = 2.4;

/** Where the current sheet stops following the tilted dipole equator. */
export const HINGE_DISTANCE_RE = 10;

/**
 * How far round the flanks the drawn wedge reaches, in hours of magnetic local
 * time either side of midnight.
 *
 * WHY IT IS NOT EIGHT ANY MORE. Sean, looking at the shipped layer on
 * 2026-08-20: *"the white ring around the ring current that is supposed to be
 * the plasma sheet - it obviously isn't drawn correctly ... right now it looks
 * contrived."* It was a ring, and it was drawn as one on purpose without anyone
 * checking where the ring ended up.
 *
 * Eight hours either side of midnight is 240 degrees of azimuth: 16 MLT round
 * to 08 MLT, two thirds of the way around the Earth, which is why it read as an
 * annulus enclosing the ring current rather than as a structure in the tail.
 * That is a presentation complaint with a physics fault underneath it. Take the
 * far corner of the old span, 8 h from midnight: the vertex sits at
 * `x = +0.5 r`, i.e. 60 degrees from the Sun-Earth line on the DAYSIDE. Shue
 * (1998) puts the magnetopause there at `r0 * (2/(1+cos 60))^alpha`, which for
 * this site's own measured envelope - a subsolar standoff between 7.8 and
 * 11.1 Rₑ on the release this was measured against - is 9.2 to 13.1 Rₑ. The
 * wedge is drawn out to `OUTER_EDGE_RE` = 14. So the old span put plasma-sheet
 * material OUTSIDE the magnetopause, on the dayside, in every driver state the
 * site has recorded. There is no plasma sheet there; there is magnetosheath.
 *
 * Four hours reaches 20 and 04 MLT - the substorm injection sector, which is
 * the answer to the question that put this layer on the site in the first
 * place: *"you don't need to draw all of it, just the portion where particles
 * are drawn back into the earth, right?"* The far corner is then 120 degrees
 * from the Sun-Earth line, well behind the terminator, where Shue evaluated at
 * the most COMPRESSED corner of the measured driver envelope (Dp 8.99 nPa,
 * Bz −10.22 nT, giving a 6.99 Rₑ standoff) puts the boundary at 18.1 Rₑ. The
 * wedge reaches 14. So the whole of it stays inside the magnetopause even when
 * the magnetopause is as far in as this site has ever recorded it, with 4 Rₑ to
 * spare, and `tests/inner-plasma-sheet.test.ts` holds it there against the
 * boundary rather than against a number somebody liked.
 *
 * Five hours was checked first and rejected: it comes out at 13.8 Rₑ against a
 * 14 Rₑ outer edge, which is inside the boundary by less than the width of the
 * line it would be drawn with.
 */
export const MLT_HALF_SPAN_HOURS = 4;

export interface InnerPlasmaSheetOptions {
  /** The scene's shared GSM mapper. Every vertex goes through it. */
  positionForGsm: (xRe: number, yRe: number, zRe: number) => THREE.Vector3;
  /** Samples across local time and across radius. */
  azimuthSegments?: number;
  radialSegments?: number;
}

/** Where the sheet's centre plane sits, in GSM z, for a given GSM x. */
export function sheetCentreZRe(xRe: number, dipoleTiltRad: number): number {
  // The magnetic equator plane is x sin(psi) + z cos(psi) = 0, so z = -x tan(psi).
  // Hinged: it follows that plane out to HINGE_DISTANCE_RE and then holds,
  // rather than running away down the tail.
  const hinged = Math.max(-HINGE_DISTANCE_RE, Math.min(HINGE_DISTANCE_RE, xRe));
  return -hinged * Math.tan(dipoleTiltRad);
}

/**
 * The drawn inner edge, in Earth radii.
 *
 * Earthward through the whole cycle: convection brings it in during loading,
 * and injection brings it in much further and much faster.
 */
export function innerEdgeRe(state: Pick<SubstormState, "loading" | "injection">): number {
  const loaded = INNER_EDGE_QUIET_RE
    - (INNER_EDGE_QUIET_RE - INNER_EDGE_LOADED_RE) * clamp01(state.loading);
  return loaded - (loaded - INNER_EDGE_INJECTED_RE) * clamp01(state.injection);
}

/**
 * Half-thickness at the outer edge, in Earth radii.
 *
 * Loading THINS it and onset thickens it. That is the direction a reader will
 * not guess, and it is the whole mechanism: the sheet thins until it
 * reconnects.
 */
export function halfThicknessRe(state: Pick<SubstormState, "loading" | "injection">): number {
  const thinned = HALF_THICKNESS_QUIET_RE
    - (HALF_THICKNESS_QUIET_RE - HALF_THICKNESS_THIN_RE) * clamp01(state.loading);
  return thinned + (HALF_THICKNESS_THICK_RE - thinned) * clamp01(state.injection);
}

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

/** Hermite ramp, matching the one every other layer here fades with. */
function smoothstep(edge0: number, edge1: number, value: number) {
  const t = clamp01((value - edge0) / (edge1 - edge0 || 1e-6));
  return t * t * (3 - 2 * t);
}

/** Local half-thickness: the sheet is thinnest at its earthward edge. */
function thicknessAtRe(radiusRe: number, inner: number, outerHalfThickness: number) {
  const span = Math.max(0.001, OUTER_EDGE_RE - inner);
  const along = clamp01((radiusRe - inner) / span);
  // Flares from a third of the outer value at the inner edge. Drawing it
  // uniform would make the sheet a slab, and the flare is what makes the
  // earthward edge read as an edge.
  return outerHalfThickness * (0.34 + 0.66 * along);
}

export interface InnerPlasmaSheetGeometryInput {
  state: Pick<SubstormState, "loading" | "injection" | "phase">;
  dipoleTiltRad: number;
  /**
   * Where the dipolarisation front has reached, in Earth radii, or null when
   * nothing is propagating. Drawn as a bright band, and it exists only while a
   * measured onset is recent.
   */
  frontRe: number | null;
}

/**
 * The wedge, as one indexed mesh with vertex colours.
 *
 * Rebuilt rather than deformed. Every vertex is placed through the scene's
 * shared radial ruler, which is non-linear, so scaling the geometry in a shader
 * would draw distances the ruler never authorised. The mesh is about 2,400
 * vertices, which is cheap enough to rebuild on the clock.
 */
export function createInnerPlasmaSheetGeometry(
  options: InnerPlasmaSheetOptions,
  input: InnerPlasmaSheetGeometryInput,
): THREE.BufferGeometry {
  const azimuthSegments = Math.max(8, Math.floor(options.azimuthSegments ?? 56));
  const radialSegments = Math.max(4, Math.floor(options.radialSegments ?? 22));
  const inner = innerEdgeRe(input.state);
  const outerHalfThickness = halfThicknessRe(input.state);

  const positions: number[] = [];
  // Four components: the alpha channel is what stops the wedge ending in a
  // straight chord across the sky. The drawn region has to fade out at the
  // flanks and at both rims, because the real inner plasma sheet has no edge
  // there - it thins into the flank and into the tail - and a hard cut reads as
  // a rendering fault rather than as a boundary.
  const colours: number[] = [];
  const indices: number[] = [];

  // A saturated blue, not the pale 0x4a7fb5 this shipped with. The mesh is a
  // closed body under additive blending, so a ray crosses at least two faces
  // and sums them; a desaturated ink sums toward white, which is exactly the
  // "white ring" Sean saw, and no reduction in opacity changes the HUE it
  // washes to. This one stays blue as it accumulates.
  const quiet = new THREE.Color(0x2f6ec4);
  const hot = new THREE.Color(0xffa24d);

  const rowLength = azimuthSegments + 1;
  for (let side = 0; side < 2; side += 1) {
    const sign = side === 0 ? 1 : -1;
    for (let radial = 0; radial <= radialSegments; radial += 1) {
      const radius = inner + ((OUTER_EDGE_RE - inner) * radial) / radialSegments;
      const half = thicknessAtRe(radius, inner, outerHalfThickness);
      for (let azimuth = 0; azimuth <= azimuthSegments; azimuth += 1) {
        // Magnetic local time, hours from midnight, negative toward dusk.
        const mltOffset = -MLT_HALF_SPAN_HOURS + (2 * MLT_HALF_SPAN_HOURS * azimuth) / azimuthSegments;
        const phi = (mltOffset / 24) * Math.PI * 2;
        // Midnight is anti-sunward: GSM -x.
        // CORRECTNESS FIX 2026-09-04: y is NEGATIVE sin(phi), the convention
        // every other layer in this scene uses — dusk is GSM +y. `phi` counts
        // from midnight toward dawn, so `+sin` put MLT 20 (dusk) at y = -0.87r,
        // which `gsmFromDrift` and `equatorialRadiationPosition` both call
        // dawn. The wedge is symmetric about midnight and its heat and flank
        // fade both read |mltOffset|, so nothing on screen moves today; the
        // moment anyone gives this wedge a dawn-dusk asymmetry it would have
        // been drawn on the wrong flank, beside a ring current whose partial
        // ring is dusk-sided.
        const xRe = -radius * Math.cos(phi);
        const yRe = -radius * Math.sin(phi);
        const centreZ = sheetCentreZRe(xRe, input.dipoleTiltRad);
        const zRe = centreZ + sign * half;
        const point = options.positionForGsm(xRe, yRe, zRe);
        positions.push(point.x, point.y, point.z);

        // Colour: how hot this parcel is. The base is the phase, and the front
        // is a travelling band on top of it.
        let heat = 0.12 + 0.5 * clamp01(input.state.injection);
        if (input.frontRe !== null) {
          const distance = Math.abs(radius - input.frontRe);
          heat += 0.75 * Math.exp(-((distance / 0.9) ** 2));
        }
        // The flanks are cooler: injections are a nightside phenomenon and the
        // wedge should not read as a uniform disc.
        const flankFraction = Math.abs(mltOffset) / MLT_HALF_SPAN_HOURS;
        const flank = 1 - 0.55 * flankFraction ** 2;
        const colour = quiet.clone().lerp(hot, clamp01(heat) * flank);
        // Fade out toward the flanks, and over a thin band at each rim.
        //
        // From 0.5 rather than 0.62: the sheet has no edge at the flanks - it
        // thins into them - so the drawn extent should trail off well before
        // the last vertex. Starting the fade at 0.62 of a span left the outer
        // third at most of full alpha and then stopped, which is the "ends in a
        // chord across the sky" failure the alpha channel exists to prevent,
        // and it is half of why this read as a ring with two cut ends.
        const flankFade = 1 - smoothstep(0.5, 1, flankFraction);
        const radialFraction = radial / radialSegments;
        const rimFade = smoothstep(0, 0.09, radialFraction) * (1 - smoothstep(0.86, 1, radialFraction));
        colours.push(colour.r, colour.g, colour.b, flankFade * (0.25 + 0.75 * rimFade));
      }
    }
  }

  const sideStride = rowLength * (radialSegments + 1);
  for (let side = 0; side < 2; side += 1) {
    const base = side * sideStride;
    for (let radial = 0; radial < radialSegments; radial += 1) {
      for (let azimuth = 0; azimuth < azimuthSegments; azimuth += 1) {
        const a = base + radial * rowLength + azimuth;
        const b = a + 1;
        const c = a + rowLength;
        const d = c + 1;
        if (side === 0) indices.push(a, c, d, a, d, b);
        else indices.push(a, d, c, a, b, d);
      }
    }
  }
  // Close the earthward and tailward rims so the wedge is a body and not two
  // loose sheets: an open edge reads as a rendering fault from a low angle.
  for (const radial of [0, radialSegments]) {
    for (let azimuth = 0; azimuth < azimuthSegments; azimuth += 1) {
      const top = radial * rowLength + azimuth;
      const bottom = sideStride + top;
      indices.push(top, bottom, bottom + 1, top, bottom + 1, top + 1);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 4));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.userData = {
    kind: "inner-plasma-sheet-wedge",
    evidence: "empirical",
    representation: "an empirical description of the inner plasma sheet, shaped by measured drivers",
    measured: "the timing and the intensity only: southward Bz for the loading, an auroral-electrojet index for the onset, Dst for the ring-current response",
    notMeasured: "every dimension drawn here — the inner edge, the cross-tail span, the thickness and the front",
    innerEdgeRe: inner,
    outerEdgeRe: OUTER_EDGE_RE,
    halfThicknessRe: outerHalfThickness,
    sheetCentreZRe: sheetCentreZRe(-OUTER_EDGE_RE, input.dipoleTiltRad),
    phase: input.state.phase,
  };
  return geometry;
}

/**
 * Where the dipolarisation front has reached, or null.
 *
 * The front is the visible snap: at onset a reconnection site near the inner
 * tail launches flow bursts earthward, and the drawn band is where that
 * disturbance has got to. It is drawn only while a MEASURED onset is recent,
 * so a window with no electrojet index never shows one.
 *
 * The propagation time is display shaping, not a measured speed. Real
 * bursty-bulk-flow fronts cross this distance in a few minutes; eight minutes
 * is chosen so that a reader scrubbing the site's one-minute clock can see it
 * move rather than find it already arrived.
 */
export const FRONT_TRAVEL_MINUTES = 8;

export function dipolarisationFrontRe(state: SubstormState): number | null {
  if (state.onsetEvidence === "none") return null;
  if (state.minutesSinceOnset === null || state.minutesSinceOnset < 0) return null;
  if (state.minutesSinceOnset > FRONT_TRAVEL_MINUTES) return null;
  const progress = clamp01(state.minutesSinceOnset / FRONT_TRAVEL_MINUTES);
  const inner = innerEdgeRe(state);
  return OUTER_EDGE_RE - (OUTER_EDGE_RE - inner) * progress;
}

/** The drawn layer: geometry plus the material it is drawn with. */
export class InnerPlasmaSheet {
  readonly group = new THREE.Group();
  private mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial> | null = null;
  private lastKey = "";

  constructor(private readonly options: InnerPlasmaSheetOptions) {
    this.group.name = "inner-plasma-sheet";
    this.group.visible = false;
  }

  /**
   * Set the drawn state from a substorm state and the dipole tilt.
   *
   * Rebuilds only when something visible changed, keyed on the quantities the
   * geometry actually depends on. Without the key this rebuilds 2,400 vertices
   * four times a second for a picture that has not moved.
   */
  setState(state: SubstormState, dipoleTiltRad: number) {
    const frontRe = dipolarisationFrontRe(state);
    const key = [
      state.loading.toFixed(3),
      state.injection.toFixed(3),
      state.phase,
      dipoleTiltRad.toFixed(4),
      frontRe === null ? "none" : frontRe.toFixed(2),
    ].join("|");
    if (key === this.lastKey && this.mesh) return;
    this.lastKey = key;

    const geometry = createInnerPlasmaSheetGeometry(this.options, {
      state,
      dipoleTiltRad,
      frontRe,
    });
    if (this.mesh) {
      this.mesh.geometry.dispose();
      this.mesh.geometry = geometry;
    } else {
      const material = new THREE.MeshBasicMaterial({
        vertexColors: true,
        transparent: true,
        // Overwritten immediately below by the injection ramp; this is only the
        // value the material is constructed with.
        opacity: 0.18,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      this.mesh = new THREE.Mesh(geometry, material);
      this.mesh.name = "inner-plasma-sheet-wedge";
      this.mesh.frustumCulled = false;
      this.group.add(this.mesh);
    }
    // Brighter while injecting: the layer's whole job is to make the moment of
    // delivery visible, and opacity is the honest channel for "more of it"
    // when no flux is being claimed.
    //
    // The floor came down from 0.22 to 0.16. Quiet is where this layer spends
    // most of its life - the release this was measured on read GEOMAG STORM ·
    // RECOVERY · WEAK, so `injection` was near zero - and at 0.22 through a
    // closed body the quiet state was the most prominent thing in the frame, a
    // solid pale band around a ring current it is supposed to be feeding. The
    // ratio between quiet and injecting is what carries the meaning, and it is
    // wider now (0.16 to 0.50) than it was (0.22 to 0.60), and the quiet state is a
    // defined tongue in the tail rather than a band around the planet.
    this.mesh.material.opacity = 0.16 + 0.34 * Math.min(1, Math.max(0, state.injection));
    this.group.userData.state = geometry.userData;
  }

  setVisible(visible: boolean) {
    this.group.visible = visible;
  }

  dispose() {
    if (this.mesh) {
      this.mesh.geometry.dispose();
      this.mesh.material.dispose();
    }
    this.group.clear();
    this.mesh = null;
  }
}
