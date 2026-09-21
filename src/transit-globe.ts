/**
 * The planner's 3-D view.
 *
 * ## Why this is not `SpaceGlobe`
 *
 * `src/globe.ts` is the site's main scene: star field, magnetosphere, ionosphere
 * volume, radiation belts, aurora, D-region, solar wind, eight thousand
 * satellites and a picking pipeline. The planner needs a globe, a route, a few
 * dozen satellites and their footprints. Instantiating the main scene a second
 * time inside a content panel would have paid for all of that to answer none of
 * it, and that file is owned by another agent.
 *
 * What this module does share, and must never diverge from, is the **coordinate
 * convention**:
 *
 *     x =  r cos(lat) cos(lon)
 *     y =  r sin(lat)
 *     z = -r cos(lat) sin(lon)
 *
 * That is `geoRadiansToVector` in `src/globe.ts`, character for character, and
 * it is also the convention `stateFromEci` in `src/orbit.ts` produces. Anything
 * that lands in this scene goes through `geoToVector` below.
 *
 * ## Coastlines are geometry, not a texture
 *
 * The main globe paints coastlines into an equirectangular canvas and wraps it
 * on a sphere, which means the texture's u axis and the mesh's geometry have to
 * be registered against each other — a 90-degree registration error in exactly
 * that seam was found and fixed in this codebase on 2026-08-07, having hidden
 * for months.
 *
 * This module cannot reproduce that bug, because it does not have that seam.
 * Coastlines are drawn as line geometry through the *same* `geoToVector` that
 * places waypoints, satellites and footprints. If the transform were wrong,
 * every element would be wrong together and the route would still land on the
 * right coast — there is no second coordinate system to drift against. The
 * verification test still renders a known landmark and checks it, because
 * "cannot drift" is an argument and a render is evidence.
 */

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { footprintPoints } from "./orbit";
import type { LandGeoJson } from "./globe";
import { routePolyline, type TransitRoute } from "./transit-route";

export const TRANSIT_GLOBE_RADIUS = 100;

/**
 * The scene transform. Identical to `geoRadiansToVector` in src/globe.ts.
 * Exported so a test can assert the two agree rather than trusting a comment.
 */
export function geoToVector(latitudeDeg: number, longitudeDeg: number, radius: number): THREE.Vector3 {
  const latitude = (latitudeDeg * Math.PI) / 180;
  const longitude = (longitudeDeg * Math.PI) / 180;
  return new THREE.Vector3(
    radius * Math.cos(latitude) * Math.cos(longitude),
    radius * Math.sin(latitude),
    -radius * Math.cos(latitude) * Math.sin(longitude),
  );
}

/**
 * Altitude to scene radius. Logarithmic, so a 550 km orbit and a geostationary
 * one are both visible in one frame. Matches the main globe's `displayRadius`
 * so the two views read at the same visual scale.
 */
export function displayRadius(altitudeKm: number): number {
  return TRANSIT_GLOBE_RADIUS + Math.min(205, 28 * Math.log1p(Math.max(0, altitudeKm) / 350));
}

/**
 * Flat [x,y,z,...] pairs of coastline segment endpoints in scene coordinates.
 *
 * Pure, and exported, so the registration test can assert that the coastline a
 * reader sees really is where `geoToVector` says that coastline is — rather than
 * asserting that a transform round-trips through its own inverse, which proves
 * nothing.
 */
export function coastlineSegmentPositions(land: LandGeoJson, radius: number): number[] {
  const positions: number[] = [];
  for (const feature of land.features) {
    const polygons = feature.geometry.type === "Polygon"
      ? [feature.geometry.coordinates as unknown as number[][][]]
      : feature.geometry.coordinates as unknown as number[][][][];
    for (const polygon of polygons) {
      for (const ring of polygon) {
        for (let index = 1; index < ring.length; index += 1) {
          const previous = ring[index - 1]!;
          const current = ring[index]!;
          const a = geoToVector(previous[1] ?? 0, previous[0] ?? 0, radius);
          const b = geoToVector(current[1] ?? 0, current[0] ?? 0, radius);
          positions.push(a.x, a.y, a.z, b.x, b.y, b.z);
        }
      }
    }
  }
  return positions;
}

export interface TransitGlobeSatellite {
  id: number;
  name: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
  colorHex: number;
  visible: boolean;
}

export interface TransitGlobeState {
  route: TransitRoute;
  selectedWaypointId: string | null;
  currentPosition: { latitudeDeg: number; longitudeDeg: number } | null;
  satellites: readonly TransitGlobeSatellite[];
  showOnlyVisible: boolean;
  /** Draw the footprint of every satellite currently above the mask. */
  showFootprints: boolean;
  maskDeg: number;
}

export interface TransitGlobeOptions {
  container: HTMLElement;
  land: LandGeoJson;
}

export class TransitGlobe {
  private readonly container: HTMLElement;
  private readonly scene = new THREE.Scene();
  private readonly camera: THREE.PerspectiveCamera;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly controls: OrbitControls;
  private readonly dynamicGroup = new THREE.Group();
  private readonly resizeObserver: ResizeObserver;
  private animationFrame = 0;
  private disposed = false;

  constructor({ container, land }: TransitGlobeOptions) {
    this.container = container;
    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight || Math.round(width * 0.62));

    this.camera = new THREE.PerspectiveCamera(38, width / height, 1, 6000);
    this.camera.position.set(0, 120, 360);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.setSize(width, height, false);
    this.renderer.setClearColor(0x03101a, 1);
    this.renderer.domElement.style.width = "100%";
    this.renderer.domElement.style.height = "100%";
    this.renderer.domElement.style.display = "block";
    container.replaceChildren(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 150;
    this.controls.maxDistance = 1400;
    this.controls.enablePan = false;

    this.scene.add(new THREE.AmbientLight(0xffffff, 1.15));
    const key = new THREE.DirectionalLight(0xdff4ff, 0.8);
    key.position.set(1, 0.5, 1);
    this.scene.add(key);

    this.scene.add(this.buildOcean());
    this.scene.add(this.buildGraticule());
    this.scene.add(this.buildCoastlines(land));
    this.scene.add(this.dynamicGroup);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.animate();
  }

  private buildOcean(): THREE.Mesh {
    return new THREE.Mesh(
      new THREE.SphereGeometry(TRANSIT_GLOBE_RADIUS, 96, 64),
      new THREE.MeshStandardMaterial({ color: 0x0a2b3a, roughness: 1, metalness: 0.02 }),
    );
  }

  private buildGraticule(): THREE.Group {
    const group = new THREE.Group();
    const material = new THREE.LineBasicMaterial({ color: 0x3f7f92, transparent: true, opacity: 0.28 });
    const equatorMaterial = new THREE.LineBasicMaterial({ color: 0x63b6c9, transparent: true, opacity: 0.5 });
    for (let latitude = -75; latitude <= 75; latitude += 15) {
      const points: THREE.Vector3[] = [];
      for (let longitude = -180; longitude <= 180; longitude += 3) {
        points.push(geoToVector(latitude, longitude, TRANSIT_GLOBE_RADIUS + 0.2));
      }
      group.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points),
        latitude === 0 ? equatorMaterial : material,
      ));
    }
    for (let longitude = -180; longitude < 180; longitude += 15) {
      const points: THREE.Vector3[] = [];
      for (let latitude = -90; latitude <= 90; latitude += 3) {
        points.push(geoToVector(latitude, longitude, TRANSIT_GLOBE_RADIUS + 0.2));
      }
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material));
    }
    return group;
  }

  /**
   * Coastlines through the same transform as everything else. See the module
   * note: this is what removes the texture-registration failure mode entirely.
   */
  private buildCoastlines(land: LandGeoJson): THREE.Group {
    const group = new THREE.Group();
    const material = new THREE.LineBasicMaterial({ color: 0x74d3db, transparent: true, opacity: 0.85 });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(
        coastlineSegmentPositions(land, TRANSIT_GLOBE_RADIUS + 0.35),
        3,
      ),
    );
    group.add(new THREE.LineSegments(geometry, material));
    return group;
  }

  private resize() {
    if (this.disposed) return;
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight || Math.round(width * 0.62));
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  private animate = () => {
    if (this.disposed) return;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.animationFrame = requestAnimationFrame(this.animate);
  };

  render(state: TransitGlobeState) {
    this.clearDynamic();

    const routeVertices = routePolyline(state.route, 0.75);
    if (routeVertices.length > 1) {
      const points = routeVertices.map((vertex) =>
        geoToVector(vertex.latitudeDeg, vertex.longitudeDeg, TRANSIT_GLOBE_RADIUS + 0.9));
      this.dynamicGroup.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: 0x45eadb, linewidth: 2 }),
      ));
    }

    for (const waypoint of state.route.waypoints) {
      const selected = waypoint.id === state.selectedWaypointId;
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(selected ? 2.6 : 1.9, 16, 12),
        new THREE.MeshBasicMaterial({ color: selected ? 0xffd479 : 0x45eadb }),
      );
      marker.position.copy(geoToVector(waypoint.latitudeDeg, waypoint.longitudeDeg, TRANSIT_GLOBE_RADIUS + 1.2));
      this.dynamicGroup.add(marker);
    }

    if (state.currentPosition) {
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(2.2, 16, 12),
        new THREE.MeshBasicMaterial({ color: 0xffffff }),
      );
      marker.position.copy(geoToVector(
        state.currentPosition.latitudeDeg,
        state.currentPosition.longitudeDeg,
        TRANSIT_GLOBE_RADIUS + 1.6,
      ));
      this.dynamicGroup.add(marker);
    }

    for (const satellite of state.satellites) {
      if (state.showOnlyVisible && !satellite.visible) continue;
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(satellite.visible ? 2.2 : 1.2, 12, 8),
        new THREE.MeshBasicMaterial({
          color: satellite.colorHex,
          transparent: !satellite.visible,
          opacity: satellite.visible ? 1 : 0.3,
        }),
      );
      marker.position.copy(geoToVector(
        satellite.latitudeDeg,
        satellite.longitudeDeg,
        displayRadius(satellite.altitudeKm),
      ));
      this.dynamicGroup.add(marker);

      if (state.showFootprints && satellite.visible) {
        const boundary = footprintPoints(
          satellite.latitudeDeg,
          satellite.longitudeDeg,
          satellite.altitudeKm,
          state.maskDeg,
          96,
        ).map(([longitude, latitude]) => geoToVector(latitude, longitude, TRANSIT_GLOBE_RADIUS + 0.6));
        if (boundary.length > 2) {
          this.dynamicGroup.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(boundary),
            new THREE.LineBasicMaterial({ color: satellite.colorHex, transparent: true, opacity: 0.65 }),
          ));
        }
      }
    }
  }

  /** Point the camera at a geographic position without changing the distance. */
  lookAt(latitudeDeg: number, longitudeDeg: number) {
    const distance = this.camera.position.length();
    this.camera.position.copy(geoToVector(latitudeDeg, longitudeDeg, distance));
    this.controls.update();
  }

  private clearDynamic() {
    this.dynamicGroup.traverse((child) => {
      if (child instanceof THREE.Mesh || child instanceof THREE.Line || child instanceof THREE.LineSegments) {
        child.geometry.dispose();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        for (const material of materials) material.dispose();
      }
    });
    this.dynamicGroup.clear();
  }

  destroy() {
    this.disposed = true;
    cancelAnimationFrame(this.animationFrame);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.clearDynamic();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
