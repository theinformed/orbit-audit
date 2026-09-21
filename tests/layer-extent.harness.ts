/**
 * Browser-side half of the vertical-extent verification.
 *
 * The question this answers is not "what altitude does the constant say" but
 * "how far up does the glow actually reach on screen", which is the thing a
 * reader sees. It draws the production globe with the real published
 * thermosphere and WAM-IPE artifacts, pins the camera on the +Z axis looking
 * at the origin, hides the starfield and the airglow shell (both of which
 * would otherwise be counted as lit pixels), and exposes the renderer's own
 * projection so a measured pixel radius can be converted back to scene units
 * exactly rather than by assuming an orthographic camera.
 */
import * as THREE from "three";
import { SpaceGlobe } from "../src/globe";
import { decodeThermosphereFrame, type ThermosphereBundle } from "../src/thermosphere";
import type { IonosphereVolumeBundle, SatelliteRecord } from "../src/types";

declare global {
  interface Window {
    __ready: boolean;
    __lastError: string | null;
    /** Pixel position of a scene point, in CSS pixels relative to the canvas. */
    __project: (x: number, y: number, z: number) => { x: number; y: number };
    __setLayers: (thermosphere: boolean, ionosphere: boolean) => void;
    __setTopside: (kneeDecades: number, densityIndex: number) => void;
    __setTime: (iso: string) => void;
    __canvasBox: () => { width: number; height: number };
  }
}

window.__ready = false;
window.__lastError = null;

const PINNED_TIME = new Date("2026-08-19T21:00:00Z");
const CAMERA_DISTANCE = 620;

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites: [] as SatelliteRecord[],
  land: { features: [] },
  onSelect: () => {},
});
const internals = globe as unknown as Record<string, any>;

function pinCamera() {
  internals.starField.visible = false;
  if (internals.airglowShell) internals.airglowShell.visible = false;
  internals.cameraDolly = null;
  internals.camera.position.set(0, 0, CAMERA_DISTANCE);
  internals.camera.up.set(0, 1, 0);
  internals.controls.target.set(0, 0, 0);
  internals.controls.update();
}

async function main() {
  const manifest = await fetch("/data/manifest.json").then((r) => r.json());

  const thermosphere = await fetch(`/data/${manifest.thermosphere.path}`)
    .then((r) => r.json()) as ThermosphereBundle;
  const ionosphere = await fetch(`/data/${manifest.ionosphereModel.path}`)
    .then((r) => r.json()) as IonosphereVolumeBundle;

  // The frame nearest the pinned instant, chosen the way main.ts chooses it.
  let best = thermosphere.frames[0]!;
  let bestGap = Number.POSITIVE_INFINITY;
  for (const frame of thermosphere.frames) {
    const gap = Math.abs(Date.parse(frame.validAt) - PINNED_TIME.getTime());
    if (gap < bestGap) { bestGap = gap; best = frame; }
  }
  globe.setThermosphereFrame(decodeThermosphereFrame(best));
  globe.setIonosphereModel(ionosphere);
  globe.setIonosphereRegionsEnabled({ D: true, E: true, F1: true, F2: true });
  globe.setIonosphereDataAvailable(true);
  globe.setSimulationTime(PINNED_TIME);

  pinCamera();

  window.__setLayers = (thermo, iono) => {
    globe.setLayer("thermosphere", thermo);
    globe.setLayer("ionosphere", iono);
    pinCamera();
  };

  // Live sweep of the topside floor, without a rebake: both are uniforms.
  window.__setTopside = (kneeDecades, densityIndex) => {
    internals.scene.traverse((object: any) => {
      const uniforms = object?.material?.uniforms;
      if (!uniforms || !uniforms.topsideKneeDecades) return;
      uniforms.topsideKneeDecades.value = kneeDecades;
      uniforms.topsideDensityIndex.value = densityIndex;
    });
  };

  // A different published frame, to show the floor is not tuned to one hour.
  window.__setTime = (iso) => {
    globe.setSimulationTime(new Date(iso));
    pinCamera();
  };

  window.__project = (x, y, z) => {
    const canvas = internals.renderer.domElement as HTMLCanvasElement;
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector3(x, y, z).project(internals.camera as THREE.Camera);
    return {
      x: ((ndc.x + 1) / 2) * rect.width,
      y: ((1 - ndc.y) / 2) * rect.height,
    };
  };

  window.__canvasBox = () => {
    const rect = (internals.renderer.domElement as HTMLCanvasElement).getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  };

  globe.setLayer("thermosphere", false);
  globe.setLayer("ionosphere", false);
  await new Promise((resolve) => setTimeout(resolve, 500));
  window.__ready = true;
}

main().catch((error) => {
  window.__lastError = String(error?.stack ?? error);
});
