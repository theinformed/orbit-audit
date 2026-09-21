/**
 * Browser-side half of the radiation-volume verification.
 *
 * Instantiates the production globe, loads a pinned real RBE frame, enables
 * the radiation layer in its shipped default presentation (mapped 3-D,
 * omnidirectional) and exposes camera positioning hooks so the spec can
 * screenshot the raymarched belts from the four viewpoints that matter:
 * the default framing, oblique, edge-on, and down the pole.
 */
import * as THREE from "three";
import { SpaceGlobe } from "../src/globe";
import { createRadiationVolumeMesh } from "../src/radiation-belt-volume";
import {
  RADIATION_ENERGY_COMBINATION,
  combineRadiationEnergyChannels,
  isCombinedRadiationEnergy,
} from "../src/radiation-belt";
import type { RadiationBeltDefinition, RadiationBeltFrame } from "../src/radiation-belt";
import type { SatelliteRecord } from "../src/types";
import type { GeospaceBundle } from "../src/types";

declare global {
  interface Window {
    __ready: boolean;
    __setView: (view: "default" | "oblique" | "edge" | "pole", energyKev: number) => void;
    __measureFps: (frames?: number) => Promise<number>;
    __measureBake: (energyKev: number) => number;
    __lastError: string | null;
  }
}

window.__ready = false;
window.__lastError = null;

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites: [{ id: 1, name: "PROBE", ownerLabel: "None", mission: "other" } as unknown as SatelliteRecord],
  land: { features: [] },
  onSelect: () => {},
});
const internals = globe as unknown as Record<string, any>;

function pointCamera(direction: THREE.Vector3, distance: number, up: THREE.Vector3) {
  internals.cameraDolly = null;
  internals.camera.position.copy(direction.normalize().multiplyScalar(distance));
  internals.camera.up.copy(up);
  internals.controls.target.set(0, 0, 0);
  internals.controls.update();
}

async function main() {
  // The pinned fixture by default. `?fixture=` and `?frame=` let the same
  // harness be pointed at a live published bundle — which is the only way to
  // see what the load-time opacity-floor derivation does on a frame other
  // than the one the shipped fallback table was measured on.
  const parameters = new URLSearchParams(window.location.search);
  const fixtureUrl = parameters.get("fixture") ?? "/tests/data/geospace-volume-fixture.json";
  const response = await fetch(fixtureUrl);
  const bundle = (await response.json()) as GeospaceBundle;
  globe.setGeospaceModel(bundle);
  globe.setRadiationView("dipoleMapped3d");
  globe.setLayer("radiation", true);
  const published = (bundle as unknown as { frames: Array<{ validAt: string; radiationBelt?: unknown }> })
    .frames.filter((entry) => entry.radiationBelt);
  const requestedFrame = Number(parameters.get("frame") ?? 0);
  const frameIndex = Number.isFinite(requestedFrame) && requestedFrame >= 0
    ? Math.min(Math.floor(requestedFrame), published.length - 1)
    : 0;
  const validAt = published[frameIndex]!.validAt;
  globe.setSimulationTime(new Date(validAt));

  window.__setView = (view, energyKev) => {
    globe.setRadiationEnergy(energyKev);
    globe.setSimulationTime(new Date(validAt));
    const distance = 700;
    internals.sunFrameGroup.updateMatrixWorld(true);
    const quaternion = internals.sunFrameGroup.quaternion as THREE.Quaternion;
    // Scene directions of the GSM axes, through the same swizzle the mapper
    // uses (scene Y is GSM Z, scene -Z is GSM Y).
    const gsmNorth = new THREE.Vector3(0, 1, 0).applyQuaternion(quaternion).normalize();
    const gsmSunward = new THREE.Vector3(1, 0, 0).applyQuaternion(quaternion).normalize();
    if (view === "default") {
      // Whatever the production reset gives: the framing a first-time visitor sees.
      globe.focusRadiationObliqueView();
    } else if (view === "oblique") {
      const direction = gsmSunward.clone().multiplyScalar(0.8)
        .add(gsmNorth.clone().multiplyScalar(0.55))
        .add(new THREE.Vector3().crossVectors(gsmNorth, gsmSunward).multiplyScalar(0.6));
      pointCamera(direction, distance, gsmNorth);
    } else if (view === "edge") {
      pointCamera(gsmSunward.clone(), distance, gsmNorth);
    } else {
      pointCamera(gsmNorth.clone(), distance, gsmSunward);
    }
  };

  const definition = (bundle as unknown as { radiationBelt: RadiationBeltDefinition }).radiationBelt;
  const frame = (published[frameIndex] as unknown as { radiationBelt: RadiationBeltFrame }).radiationBelt;
  const mapper = (x: number, y: number, z: number) =>
    (internals.modelRadiationPosition as (a: number, b: number, c: number) => THREE.Vector3).call(globe, x, y, z);

  window.__measureBake = (energyKev) => {
    const started = performance.now();
    // The combined view costs the energy fold PLUS the bake, which is the
    // number that matters: it is what the runtime pays when it is selected.
    const source = isCombinedRadiationEnergy(energyKev)
      ? combineRadiationEnergyChannels(definition, frame, RADIATION_ENERGY_COMBINATION)
      : { definition, frame };
    const { mesh } = createRadiationVolumeMesh(source.definition, source.frame, energyKev, mapper);
    const elapsed = performance.now() - started;
    mesh.geometry.dispose();
    (mesh.material as THREE.Material).dispose();
    return elapsed;
  };

  window.__measureFps = (frames = 90) => new Promise<number>((resolve) => {
    const samples: number[] = [];
    let last = performance.now();
    const tick = () => {
      const now = performance.now();
      samples.push(now - last);
      last = now;
      if (samples.length < frames) requestAnimationFrame(tick);
      else {
        samples.sort((a, b) => a - b);
        resolve(samples[Math.floor(samples.length / 2)]!);
      }
    };
    requestAnimationFrame(tick);
  });

  // A few frames so async texture upload and the first raymarch settle.
  await new Promise((resolve) => setTimeout(resolve, 300));
  window.__ready = true;
}

main().catch((error) => {
  window.__lastError = String(error?.stack ?? error);
});
