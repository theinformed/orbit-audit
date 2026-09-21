import * as THREE from "three";

import { RULER_EARTH_RADIUS_KM, sharedDisplayRadius } from "./radial-ruler";
import {
  DEFAULT_ISOPYCNIC_KG_M3,
  type DecodedFrame,
  isopycnicAltitudeKm,
} from "./thermosphere";

/**
 * The thermosphere drawn as a surface: the altitude at which the air reaches a
 * chosen density.
 *
 * Why a surface of constant density rather than a shell coloured by density.
 * The teaching point is that a storm makes the atmosphere SWELL — air that was
 * far below a satellite arrives at its altitude. On a fixed shell that story is
 * a colour change, which reads as "a number got bigger". Drawn as the altitude
 * of a density level, the same event lifts the surface toward the satellites,
 * which are already drawn at their true altitude on the same ruler. The
 * comparison is then geometric and needs no explanation.
 *
 * The ruler matters more than anything else here. Satellite altitudes are
 * placed by `sharedDisplayRadius`, and this surface uses the identical call, so
 * "is the satellite inside it?" is answered by the picture rather than by two
 * scales that happen to look similar.
 */

/**
 * The altitude domain the colour ramp spans, fixed rather than per-frame.
 *
 * A ramp normalised to each frame's own range would paint a quiet day in the
 * same colours as a storm — the classic over-claim, where relative scaling
 * turns "nothing happening" into a vivid picture. Fixed endpoints mean a rising
 * surface genuinely changes colour, and a calm one stays where it was.
 *
 * The endpoints are 400-600 km because that is where this surface actually
 * lives. The first version spanned 250-600, chosen before there was any real
 * data to look at; measured on production the quiet surface runs 434-512 km,
 * which is 22% of that ramp and lands entirely inside one teal — so the whole
 * globe drew as a single flat colour and the day/night structure was invisible.
 * On 400-600 the same spread uses about 40% of the ramp and the bulge reads,
 * while a storm still has headroom before it saturates at the warm end.
 */
export const SURFACE_ALTITUDE_DOMAIN_KM = { low: 400, high: 600 } as const;

/**
 * Cool and low to warm and high, holding chroma across the middle. Built the
 * same way as the radiation ramp after that one was measured: a straight
 * interpolation between two near-opposite hues crosses close to grey, and the
 * feature in the middle then reads as faded rather than as different.
 */
export const SURFACE_COLOR_HEX = ["#152a5e", "#276b8f", "#3fa07d", "#e0b23f"] as const;

export interface IsopycnicSurfaceOptions {
  /** Scene units for one Earth radius, from the globe. */
  earthSceneRadius: number;
  /** Density level whose altitude is drawn, kg m^-3. */
  level?: number;
  /** Grid resolution of the drawn mesh, in degrees. */
  latitudeStepDeg?: number;
  longitudeStepDeg?: number;
}

export interface IsopycnicSurface {
  positions: Float32Array;
  colors: Float32Array;
  indices: Uint32Array;
  /** Per-vertex altitude, NaN where the level is not crossed. */
  altitudeKm: Float64Array;
  latitudeCount: number;
  longitudeCount: number;
  minAltitudeKm: number;
  maxAltitudeKm: number;
  missingVertices: number;
  totalVertices: number;
}

function hexToRgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [
    Number.parseInt(value.slice(0, 2), 16) / 255,
    Number.parseInt(value.slice(2, 4), 16) / 255,
    Number.parseInt(value.slice(4, 6), 16) / 255,
  ];
}

/** Colour for an altitude, on the fixed domain. */
export function surfaceColor(altitudeKm: number): [number, number, number] {
  const { low, high } = SURFACE_ALTITUDE_DOMAIN_KM;
  const position = Math.min(Math.max((altitudeKm - low) / (high - low), 0), 1);
  const segments = SURFACE_COLOR_HEX.length - 1;
  const scaled = position * segments;
  const index = Math.min(Math.floor(scaled), segments - 1);
  const t = scaled - index;
  const a = hexToRgb(SURFACE_COLOR_HEX[index]!);
  const b = hexToRgb(SURFACE_COLOR_HEX[index + 1]!);
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

/**
 * Build the mesh for one frame.
 *
 * A quad is emitted only when all four of its corners resolved. Where the
 * density level is not crossed inside the published column there is simply no
 * surface, and the hole is counted so the caller can say how much of the globe
 * is missing rather than presenting a partial surface as a whole one.
 */
export function buildIsopycnicSurface(
  frame: DecodedFrame,
  options: IsopycnicSurfaceOptions,
): IsopycnicSurface {
  const level = options.level ?? DEFAULT_ISOPYCNIC_KG_M3;
  const latStep = options.latitudeStepDeg ?? 3;
  const lonStep = options.longitudeStepDeg ?? 3;
  const latitudeCount = Math.floor(180 / latStep) + 1;
  const longitudeCount = Math.floor(360 / lonStep) + 1;
  const total = latitudeCount * longitudeCount;

  const positions = new Float32Array(total * 3);
  const colors = new Float32Array(total * 3);
  const altitudeKm = new Float64Array(total);
  let missing = 0;
  let minAltitude = Number.POSITIVE_INFINITY;
  let maxAltitude = Number.NEGATIVE_INFINITY;

  for (let latIndex = 0; latIndex < latitudeCount; latIndex += 1) {
    const latitude = -90 + latIndex * latStep;
    const phi = (90 - latitude) * (Math.PI / 180);
    for (let lonIndex = 0; lonIndex < longitudeCount; lonIndex += 1) {
      const longitude = lonIndex * lonStep;
      const vertex = latIndex * longitudeCount + lonIndex;
      const altitude = isopycnicAltitudeKm(frame, latitude, longitude, level);
      altitudeKm[vertex] = altitude ?? Number.NaN;
      if (altitude === null) {
        missing += 1;
        continue;
      }
      if (altitude < minAltitude) minAltitude = altitude;
      if (altitude > maxAltitude) maxAltitude = altitude;

      const radiusRe = (RULER_EARTH_RADIUS_KM + altitude) / RULER_EARTH_RADIUS_KM;
      const radius = sharedDisplayRadius(radiusRe, options.earthSceneRadius);
      const theta = longitude * (Math.PI / 180);
      positions[vertex * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[vertex * 3 + 1] = radius * Math.cos(phi);
      positions[vertex * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);

      const [r, g, b] = surfaceColor(altitude);
      colors[vertex * 3] = r;
      colors[vertex * 3 + 1] = g;
      colors[vertex * 3 + 2] = b;
    }
  }

  const indices: number[] = [];
  for (let latIndex = 0; latIndex < latitudeCount - 1; latIndex += 1) {
    for (let lonIndex = 0; lonIndex < longitudeCount - 1; lonIndex += 1) {
      const a = latIndex * longitudeCount + lonIndex;
      const b = a + 1;
      const c = a + longitudeCount;
      const d = c + 1;
      if (!Number.isFinite(altitudeKm[a]!) || !Number.isFinite(altitudeKm[b]!)
        || !Number.isFinite(altitudeKm[c]!) || !Number.isFinite(altitudeKm[d]!)) {
        continue;
      }
      indices.push(a, c, b, b, c, d);
    }
  }

  return {
    positions,
    colors,
    indices: Uint32Array.from(indices),
    altitudeKm,
    latitudeCount,
    longitudeCount,
    minAltitudeKm: Number.isFinite(minAltitude) ? minAltitude : Number.NaN,
    maxAltitudeKm: Number.isFinite(maxAltitude) ? maxAltitude : Number.NaN,
    missingVertices: missing,
    totalVertices: total,
  };
}

/**
 * Iso-altitude lines on the surface, so its SHAPE is readable.
 *
 * The colour ramp alone could not do this. The surface spans about 80 km of
 * height across the whole globe, which on a compressed radial ruler is a very
 * small geometric difference, and at the low opacity the layer needs in order
 * not to bury the Earth the colour gradient across that range is too faint to
 * read. So the picture showed a smooth shell and the day/night bulge — the
 * thing worth seeing — was invisible.
 *
 * Contours fix that without inventing anything: each line is the set of places
 * where the surface is at exactly one stated altitude, which is a fact about
 * the field rather than shading chosen to look three-dimensional. Where the
 * lines bunch, the surface is steep; where they open out, it is flat; and a
 * storm lifting one hemisphere shows as the lines migrating across it.
 *
 * Marching squares over the same grid the surface is built from, so a contour
 * cannot disagree with the surface it is drawn on. Cells touching a hole are
 * skipped rather than closed across it.
 */
export const CONTOUR_INTERVAL_KM = 25;

export function buildIsopycnicContours(
  surface: IsopycnicSurface,
  options: { intervalKm?: number } = {},
): Float32Array {
  const interval = Math.max(1, options.intervalKm ?? CONTOUR_INTERVAL_KM);
  const { altitudeKm, positions, latitudeCount, longitudeCount } = surface;
  if (!Number.isFinite(surface.minAltitudeKm) || !Number.isFinite(surface.maxAltitudeKm)) {
    return new Float32Array(0);
  }

  const points: number[] = [];
  const first = Math.ceil(surface.minAltitudeKm / interval) * interval;
  const vertexAt = (lat: number, lon: number) => lat * longitudeCount + lon;

  // Nudged out along its own radius so the line sits ON the surface rather than
  // fighting it for the same depth.
  const push = (indexA: number, indexB: number, t: number) => {
    for (let axis = 0; axis < 3; axis += 1) {
      const a = positions[indexA * 3 + axis]!;
      const b = positions[indexB * 3 + axis]!;
      points.push((a + (b - a) * t) * 1.0015);
    }
  };

  for (let level = first; level <= surface.maxAltitudeKm; level += interval) {
    for (let lat = 0; lat < latitudeCount - 1; lat += 1) {
      for (let lon = 0; lon < longitudeCount - 1; lon += 1) {
        const corners = [
          vertexAt(lat, lon),
          vertexAt(lat, lon + 1),
          vertexAt(lat + 1, lon + 1),
          vertexAt(lat + 1, lon),
        ];
        const values = corners.map((index) => altitudeKm[index]!);
        if (values.some((value) => !Number.isFinite(value))) continue;

        // Crossings on the four edges of the cell, in order round it.
        const crossings: Array<[number, number, number]> = [];
        for (let edge = 0; edge < 4; edge += 1) {
          const a = corners[edge]!;
          const b = corners[(edge + 1) % 4]!;
          const valueA = values[edge]!;
          const valueB = values[(edge + 1) % 4]!;
          if ((valueA < level) === (valueB < level)) continue;
          const span = valueB - valueA;
          crossings.push([a, b, span === 0 ? 0 : (level - valueA) / span]);
        }
        // Two crossings is one segment. Four is a saddle: joined in order round
        // the cell, which is the standard resolution and never leaves a gap.
        for (let index = 0; index + 1 < crossings.length; index += 2) {
          const [a1, b1, t1] = crossings[index]!;
          const [a2, b2, t2] = crossings[index + 1]!;
          push(a1, b1, t1);
          push(a2, b2, t2);
        }
      }
    }
  }
  return Float32Array.from(points);
}

/** The scene object, kept thin: all the reasoning above is in the builder. */
export class ThermosphereSurfaceLayer {
  private readonly group = new THREE.Group();
  private mesh: THREE.Mesh | null = null;
  private contours: THREE.LineSegments | null = null;
  private level = DEFAULT_ISOPYCNIC_KG_M3;
  private frame: DecodedFrame | null = null;
  private summary: IsopycnicSurface | null = null;

  constructor(private readonly earthSceneRadius: number) {
    this.group.name = "thermosphere-surface";
    this.group.visible = false;
  }

  object3d(): THREE.Group {
    return this.group;
  }

  setEnabled(visible: boolean): void {
    this.group.visible = visible;
  }

  setLevel(level: number): void {
    if (level === this.level) return;
    this.level = level;
    if (this.frame) this.setFrame(this.frame);
  }

  currentLevel(): number {
    return this.level;
  }

  lastSurface(): IsopycnicSurface | null {
    return this.summary;
  }

  setFrame(frame: DecodedFrame): IsopycnicSurface {
    this.frame = frame;
    const surface = buildIsopycnicSurface(frame, {
      earthSceneRadius: this.earthSceneRadius,
      level: this.level,
    });
    this.summary = surface;

    this.dispose();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(surface.positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(surface.colors, 3));
    geometry.setIndex(new THREE.BufferAttribute(surface.indices, 1));
    geometry.computeVertexNormals();
    const material = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      // Flat opacity on purpose. Varying it with altitude would make the
      // surface look thicker where it is higher, which is not a thing the data
      // says: the field has no thickness, only a height.
      //
      // 0.22 and front faces only. At 0.42 with both faces drawn the shell was
      // painting itself twice over every sightline and desaturating the globe
      // underneath, so the coastlines went muddy and the satellites inside it
      // were hard to pick out — which is the one comparison this layer exists
      // to support. Drawing only the near hemisphere leaves the far side clear.
      opacity: 0.22,
      side: THREE.FrontSide,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(geometry, material);
    this.group.add(this.mesh);

    const contourPoints = buildIsopycnicContours(surface);
    if (contourPoints.length >= 6) {
      const contourGeometry = new THREE.BufferGeometry();
      contourGeometry.setAttribute("position", new THREE.BufferAttribute(contourPoints, 3));
      this.contours = new THREE.LineSegments(
        contourGeometry,
        new THREE.LineBasicMaterial({
          color: 0xbfe9ff,
          transparent: true,
          // Brighter than the surface on purpose: the lines ARE the shape, and
          // at the surface's own weight they disappeared into it.
          opacity: 0.5,
          depthWrite: false,
        }),
      );
      this.contours.name = "thermosphere-iso-altitude";
      this.contours.userData = { intervalKm: CONTOUR_INTERVAL_KM };
      this.group.add(this.contours);
    }
    return surface;
  }

  dispose(): void {
    if (this.contours) {
      this.group.remove(this.contours);
      this.contours.geometry.dispose();
      (this.contours.material as THREE.Material).dispose();
      this.contours = null;
    }
    if (!this.mesh) return;
    this.group.remove(this.mesh);
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.mesh = null;
  }
}
