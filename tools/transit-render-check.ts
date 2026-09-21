/**
 * Render-side verification of the planner globe's coordinate registration.
 *
 * Mounts the real `TransitGlobe` with the real published land artifact, points
 * the camera at a landmark, renders, and then reads the framebuffer back to ask
 * whether coastline pixels are where `geoToVector` says that landmark is.
 *
 * The unit test in tests/transit-globe-registration.test.ts checks the geometry.
 * This checks the picture. The two together are what "verify a known position
 * lands on the correct coastline in a real render" means, and the reason both
 * exist is that this codebase shipped a 90-degree texture-versus-geometry
 * registration error that survived months of green tests.
 */

import * as THREE from "three";
import { TransitGlobe, TRANSIT_GLOBE_RADIUS, geoToVector } from "../src/transit-globe";
import type { LandGeoJson } from "../src/globe";
import type { ReleaseManifest } from "../src/types";

interface LandmarkResult {
  name: string;
  latitudeDeg: number;
  longitudeDeg: number;
  expectCoast: boolean;
  screenX: number;
  screenY: number;
  coastlinePixels: number;
  passed: boolean;
}

declare global {
  interface Window {
    transitRenderCheck?: {
      ready: boolean;
      results: LandmarkResult[];
      allPassed: boolean;
      error?: string;
    };
  }
}

const LANDMARKS: Array<[string, number, number, boolean]> = [
  ["Pearl Harbor", 21.35, -157.95, true],
  ["Yokosuka", 35.28, 139.67, true],
  ["Cape Town", -33.92, 18.42, true],
  ["Norfolk, Virginia", 36.85, -76.29, true],
  ["Gibraltar", 36.14, -5.35, true],
  ["Point Nemo (open ocean)", -48.88, -123.39, false],
  ["Central North Pacific (open ocean)", 30, -160, false],
];

/** The coastline line material colour, 0x74d3db, is what we look for. */
function isCoastlinePixel(r: number, g: number, b: number): boolean {
  // Generous, because the line is antialiased over a dark ocean: a coastline
  // pixel is markedly brighter and more cyan than the 0x0a2b3a ocean.
  return g > 90 && b > 110 && g < 255 && r < g && b >= g - 20;
}

async function main() {
  const stage = document.getElementById("stage")!;
  const manifest: ReleaseManifest = await (await fetch("/public/data/manifest.json")).json();
  const land: LandGeoJson = await (await fetch(`/public/data/${manifest.land.path}`)).json();

  const globe = new TransitGlobe({ container: stage, land });
  globe.render({
    route: { trackModel: "great-circle", waypoints: [] },
    selectedWaypointId: null,
    currentPosition: null,
    satellites: [],
    showOnlyVisible: false,
    showFootprints: false,
    maskDeg: 5,
  });

  const canvas = stage.querySelector("canvas") as HTMLCanvasElement;
  const results: LandmarkResult[] = [];

  for (const [name, latitudeDeg, longitudeDeg, expectCoast] of LANDMARKS) {
    // Put the camera directly over the landmark so it renders near the centre,
    // well away from the limb where the sphere foreshortens to nothing.
    globe.lookAt(latitudeDeg, longitudeDeg);
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

    const camera = (globe as unknown as { camera: THREE.PerspectiveCamera }).camera;
    const renderer = (globe as unknown as { renderer: THREE.WebGLRenderer }).renderer;
    camera.updateMatrixWorld(true);

    const world = geoToVector(latitudeDeg, longitudeDeg, TRANSIT_GLOBE_RADIUS + 0.35);
    const projected = world.clone().project(camera);
    const width = canvas.width;
    const height = canvas.height;
    const screenX = Math.round(((projected.x + 1) / 2) * width);
    const screenY = Math.round(((1 - projected.y) / 2) * height);

    // Read a patch around the projected point. 26 device pixels is about 2.5
    // degrees of arc at this camera distance - the same tolerance the unit test
    // allows for Natural Earth's 110m generalisation.
    const half = 13;
    const x = Math.max(0, Math.min(width - 1, screenX - half));
    const y = Math.max(0, Math.min(height - 1, screenY - half));
    const size = half * 2;
    const pixels = new Uint8Array(size * size * 4);
    const context = renderer.getContext();
    // WebGL's origin is bottom-left; the projected y above is top-left.
    context.readPixels(x, height - y - size, size, size, context.RGBA, context.UNSIGNED_BYTE, pixels);

    let coastlinePixels = 0;
    for (let index = 0; index < pixels.length; index += 4) {
      if (isCoastlinePixel(pixels[index]!, pixels[index + 1]!, pixels[index + 2]!)) coastlinePixels += 1;
    }

    results.push({
      name,
      latitudeDeg,
      longitudeDeg,
      expectCoast,
      screenX,
      screenY,
      coastlinePixels,
      passed: expectCoast ? coastlinePixels > 0 : coastlinePixels === 0,
    });
  }

  window.transitRenderCheck = {
    ready: true,
    results,
    allPassed: results.every((result) => result.passed),
  };
  console.table(results);
}

main().catch((error) => {
  window.transitRenderCheck = { ready: true, results: [], allPassed: false, error: String(error) };
  console.error(error);
});
