/**
 * Browser-side half of the globe orientation guard.
 *
 * The globe's raster layers are equirectangular maps; everything else on it —
 * satellites, ground tracks, footprints, the graticule, the day/night
 * terminator — is vector geometry placed by geoToSceneVector. If the two
 * disagree, every spacecraft is drawn over the wrong part of the world, and
 * nothing in the interface says so: the graticule is unlabelled.
 *
 * So this renders the production globe over a map whose continents are at
 * longitudes chosen by the test, points the production camera down a known
 * geographic direction, and reads back what colour is actually there.
 */
import * as THREE from "three";
import { SpaceGlobe, calculateSubsolarPoint, equirectangularLayerAzimuth, geoToSceneVector } from "../src/globe";
import type { LandGeoJson } from "../src/globe";
import type { SatelliteRecord } from "../src/types";

/** Continents at exactly these longitude bands, ten degrees wide, on the equator. */
export const LAND_BANDS: Array<[number, number]> = [
  [-100, -90],
  [20, 30],
];

function landPolygons(): LandGeoJson {
  return {
    features: LAND_BANDS.map(([west, east]) => ({
      geometry: {
        type: "Polygon",
        coordinates: [[
          [west, -18], [east, -18], [east, 18], [west, 18], [west, -18],
        ]],
      },
    })),
  };
}

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites: [{ id: 1, name: "PROBE", ownerLabel: "None", mission: "other" } as unknown as SatelliteRecord],
  land: landPolygons(),
  onSelect: () => {},
});

const internals = globe as unknown as Record<string, any>;

/** A UTC instant on a fixed date whose sub-solar point is at this longitude. */
function timeWithSubsolarLongitude(longitudeDeg: number) {
  const day = Date.UTC(2026, 2, 20); // near an equinox, so the sub-solar latitude is ~0
  let best = day;
  let bestError = Infinity;
  for (let minute = 0; minute < 1440; minute += 1) {
    const candidate = day + minute * 60_000;
    const found = calculateSubsolarPoint(new Date(candidate)).longitudeDeg;
    const error = Math.abs(((found - longitudeDeg + 540) % 360) - 180);
    if (error >= bestError) continue;
    bestError = error;
    best = candidate;
  }
  return new Date(best);
}

/**
 * Colour rendered at the centre of the globe when the camera looks straight
 * down the given geographic direction, lit from behind the camera so every
 * probe is compared under identical illumination.
 */
function sampleAtLongitude(longitudeDeg: number, subsolarLongitudeDeg = longitudeDeg) {
  globe.setSimulationTime(timeWithSubsolarLongitude(subsolarLongitudeDeg));
  const direction = geoToSceneVector(0, longitudeDeg, 1);
  internals.camera.position.copy(direction.multiplyScalar(300));
  internals.camera.lookAt(0, 0, 0);
  internals.camera.updateMatrixWorld();
  internals.controls.target.set(0, 0, 0);

  const renderer = internals.renderer as THREE.WebGLRenderer;
  renderer.render(internals.scene, internals.camera);
  const size = new THREE.Vector2();
  renderer.getDrawingBufferSize(size);
  const patch = 8;
  const pixels = new Uint8Array(patch * patch * 4);
  const gl = renderer.getContext();
  gl.readPixels(
    Math.round(size.x / 2 - patch / 2),
    Math.round(size.y / 2 - patch / 2),
    patch, patch, gl.RGBA, gl.UNSIGNED_BYTE, pixels,
  );
  let red = 0;
  let green = 0;
  let blue = 0;
  for (let index = 0; index < patch * patch; index += 1) {
    red += pixels[index * 4]!;
    green += pixels[index * 4 + 1]!;
    blue += pixels[index * 4 + 2]!;
  }
  const count = patch * patch;
  const green_ = green / count;
  const blue_ = blue / count;
  return {
    red: red / count,
    green: green_,
    blue: blue_,
    // Land is painted a greener blue than the ocean gradient. The lights have
    // fixed colours, so this ratio survives the point being in shadow while
    // the raw brightness does not — which is what lets the night side still be
    // identified as land or sea.
    greenOverBlue: blue_ > 0 ? green_ / blue_ : 0,
  };
}

/** Offset, in degrees, between where each raster layer draws a longitude and where the vectors put it. */
function layerAzimuthOffsets(longitudeDeg: number) {
  const earth = (internals.earthFixedGroup as THREE.Group).children.find(
    (child) => child instanceof THREE.Mesh && (child.material as any).map?.image instanceof HTMLCanvasElement,
  ) as THREE.Mesh;
  const layers: Record<string, THREE.Mesh> = {
    earth,
    tec: internals.ionosphere,
    aurora: internals.aurora,
  };
  return Object.fromEntries(
    Object.entries(layers).map(([name, mesh]) => {
      const { azimuthDeg } = equirectangularLayerAzimuth(mesh as any, longitudeDeg);
      return [name, ((((azimuthDeg - longitudeDeg) % 360) + 540) % 360) - 180];
    }),
  );
}

Object.assign(window as unknown as Record<string, unknown>, {
  orientationProbe: { sampleAtLongitude, layerAzimuthOffsets, LAND_BANDS },
  orientationProbeReady: true,
});
