/**
 * Browser-side half of the satellite framing guard.
 *
 * The site frames its opening view — and every later re-framing — from
 * `sceneRadiusForActiveLayers()`, which measured every model layer and, until
 * 2026-08-26, no spacecraft at all. Its floor was a 600 km shell, so any fleet
 * above LEO was drawn outside the picture chosen for it: on the shipped build
 * the constellation of the day was MUOS, five spacecraft at 35,800 km, and
 * three of the five were off screen with two clipping a corner.
 *
 * Green unit tests cannot see that. What settles it is where a marker lands in
 * the frame, so this builds the production globe, hands it a fleet through the
 * same two calls the propagator uses, and projects every drawn marker through
 * the production camera. A marker outside normalised device coordinates is a
 * marker the visitor cannot see.
 */
import * as THREE from "three";
import { SpaceGlobe } from "../src/globe";
import type { LandGeoJson } from "../src/globe";
import type { SatelliteRecord } from "../src/types";

/** Enough rows for the widest fleet any probe below asks for. */
const FLEET_CAPACITY = 64;

const satellites = Array.from({ length: FLEET_CAPACITY }, (_, index) => ({
  id: index + 1,
  name: `PROBE ${index + 1}`,
  ownerLabel: "None",
  mission: "other",
} as unknown as SatelliteRecord));

const land: LandGeoJson = { features: [] };

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites,
  land,
  onSelect: () => {},
});

const internals = globe as unknown as Record<string, any>;

export interface FleetMember {
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
}

/**
 * Draw a fleet, exactly the way the running site draws one.
 *
 * `setVisible` is the single door every entry point resolves to — the featured
 * constellation on load, a facet box, a solo button, an orbit-band button, the
 * mode switch — and the propagator's solution follows in `updateSatellites`.
 * Driving both here is what makes this probe a statement about the real path
 * rather than about a method called in isolation.
 */
function drawFleet(members: FleetMember[]) {
  const indices = new Uint32Array(members.map((_, index) => index));
  const states = new Float32Array(members.length * 4);
  const valid = new Uint8Array(members.length).fill(1);
  members.forEach((member, index) => {
    states[index * 4] = THREE.MathUtils.degToRad(member.latitudeDeg);
    states[index * 4 + 1] = THREE.MathUtils.degToRad(member.longitudeDeg);
    states[index * 4 + 2] = member.altitudeKm;
    states[index * 4 + 3] = 3;
  });
  globe.setVisible(new Set(indices));
  // Zero interpolation: the markers land on their stated positions in this
  // call, so the probe below is reading the fleet the test asked for.
  globe.updateSatellites(indices, states, states, valid, valid, 0);
}

/** Where every drawn marker is, in the frame the camera is actually showing. */
function drawnMarkers() {
  const camera = internals.camera as THREE.PerspectiveCamera;
  const group = internals.satelliteFrameGroup as THREE.Group;
  const positions = internals.satellitePositions as THREE.BufferAttribute;
  const renderable = internals.satelliteRenderable as Uint8Array;
  camera.updateMatrixWorld(true);
  group.updateMatrixWorld(true);
  const markers: Array<{ index: number; x: number; y: number; z: number; sceneRadius: number }> = [];
  for (let index = 0; index < renderable.length; index += 1) {
    if (renderable[index] !== 1) continue;
    const world = new THREE.Vector3(
      positions.getX(index),
      positions.getY(index),
      positions.getZ(index),
    ).applyMatrix4(group.matrixWorld);
    const sceneRadius = world.length();
    const ndc = world.clone().project(camera);
    markers.push({ index, x: ndc.x, y: ndc.y, z: ndc.z, sceneRadius });
  }
  return markers;
}

/** The camera's own state, so a test can say what the frame did as well as what it holds. */
function cameraState() {
  const camera = internals.camera as THREE.PerspectiveCamera;
  const controls = internals.controls as { target: THREE.Vector3; maxDistance: number };
  return {
    distance: camera.position.distanceTo(controls.target),
    maxDistance: controls.maxDistance,
    aspect: camera.aspect,
    // The radius the framing rule is currently holding, layers and spacecraft
    // together, so a probe can separate "the frame is wrong" from "the frame
    // is right and the projection is wrong".
    sceneRadius: globe.sceneRadiusForActiveLayers(),
    up: camera.up.toArray(),
    position: camera.position.toArray(),
  };
}

/** Put the camera somewhere deliberate, the way a reader who has dragged the globe has. */
function placeCamera(position: [number, number, number]) {
  internals.cameraDolly = null;
  internals.camera.position.set(...position);
  internals.controls.target.set(0, 0, 0);
  internals.controls.update();
}

/** Switch a globe layer on or off through its real entry point. */
function setLayer(layer: string, visible: boolean) {
  (globe as unknown as { setLayer: (name: string, on: boolean) => void }).setLayer(layer, visible);
}

/** The re-framing move the layer toggles in `main.ts` ask for. */
function frame() {
  globe.frameActiveLayers({ animate: false });
}

/**
 * Whether an eased re-framing move is still in flight.
 *
 * `dollyTo` sets this the moment it decides to move and the render loop clears
 * it on the last frame of the ease, so a test can wait for the camera the site
 * actually arrives at instead of guessing at a duration.
 */
function dollyActive(): boolean {
  return internals.cameraDolly !== null;
}

Object.assign(window as unknown as Record<string, unknown>, {
  framingProbe: { drawFleet, drawnMarkers, cameraState, placeCamera, setLayer, frame, dollyActive },
  framingProbeReady: true,
});
