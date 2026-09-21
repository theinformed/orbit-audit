/**
 * Browser-side half of the ground-station overlay's geography guard.
 *
 * The unit tests pin the arithmetic and the coastline point-in-polygon. This
 * builds the production globe over the real vendored Natural Earth coastlines,
 * adds the real station overlay from `data/ground_stations.json`, points the
 * production camera straight down a station's own geographic direction, and
 * reads back the rendered pixels: is the pin drawn where the camera is
 * pointing, and is the map underneath it land?
 *
 * That is the question the quarter-turn defect got wrong for months, and no
 * amount of correct arithmetic answers it — the map is a texture and the pin
 * is vector geometry, so only a render compares the two.
 */
import * as THREE from "three";
import { SpaceGlobe, calculateSubsolarPoint, geoToSceneVector } from "../src/globe";
import type { LandGeoJson } from "../src/globe";
import { GroundStationLayer, type GroundStation } from "../src/ground-stations";
import { worldOutlines } from "../src/data/world-outlines";
import type { SatelliteRecord } from "../src/types";
import table from "../data/ground_stations.json";

const stations = (table as { stations: GroundStation[] }).stations;

/** The real 1:110m coastlines, in the shape SpaceGlobe paints its map from. */
function realWorld(): LandGeoJson {
  return {
    features: worldOutlines().land.map((ring) => ({
      geometry: {
        type: "Polygon",
        coordinates: [ring.map(([longitude, latitude]) => [longitude, latitude])],
      },
    })),
  };
}

const globe = new SpaceGlobe({
  container: document.getElementById("scene")!,
  satellites: [{ id: 1, name: "PROBE", ownerLabel: "None", mission: "other" } as unknown as SatelliteRecord],
  land: realWorld(),
  onSelect: () => {},
});

const internals = globe as unknown as Record<string, any>;

// The overlay goes on the Earth-fixed group, exactly as the wiring patch in
// docs/ground-stations-design.md describes it.
const layer = new GroundStationLayer({ stations, markerSizePx: 14 });
(internals.earthFixedGroup as THREE.Group).add(layer.group);
layer.setVisible(true);

/** A UTC instant whose sub-solar point is at this longitude, near an equinox. */
function timeWithSubsolarLongitude(longitudeDeg: number) {
  const day = Date.UTC(2026, 2, 20);
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

function renderer(): THREE.WebGLRenderer {
  return internals.renderer as THREE.WebGLRenderer;
}

/** Mean colour of a patch of the drawing buffer, in buffer pixels. */
function readPatch(centreX: number, centreY: number, patch: number) {
  const gl = renderer().getContext();
  const pixels = new Uint8Array(patch * patch * 4);
  gl.readPixels(
    Math.round(centreX - patch / 2),
    Math.round(centreY - patch / 2),
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
    // Land is painted a greener blue (#143842) than the ocean gradient
    // (#061a25 to #0b2c3a). The lights have fixed colours, so this ratio
    // survives a probe being at grazing incidence while raw brightness does
    // not — which matters here because half these stations are inside the
    // Arctic Circle and are lit edge-on even at their own local noon.
    greenOverBlue: blue_ > 0 ? green_ / blue_ : 0,
  };
}

/** Point the production camera down a geographic direction, lit from its meridian. */
function aimAt(latitudeDeg: number, longitudeDeg: number, subsolarLongitudeDeg = longitudeDeg) {
  globe.setSimulationTime(timeWithSubsolarLongitude(subsolarLongitudeDeg));
  const direction = geoToSceneVector(latitudeDeg, longitudeDeg, 1);
  internals.camera.position.copy(direction.multiplyScalar(320));
  internals.camera.lookAt(0, 0, 0);
  internals.camera.updateMatrixWorld();
  internals.controls.target.set(0, 0, 0);
}

function draw() {
  renderer().render(internals.scene, internals.camera);
}

/**
 * The whole proof for one station, in one call.
 *
 * Aims the camera straight down the station's geographic direction, so the
 * station belongs at the exact centre of the frame. Then:
 *
 *  - `pinOffsetPx`   — how far the pin's projected position is from the centre.
 *                      Zero means the pin agrees with the camera's frame.
 *  - `mapUnderPin`   — the map's own colour there, pins hidden. Land or sea.
 *  - `pinDrawn`      — the colour with pins shown. It has to differ, or the
 *                      overlay is not being rendered at all and every other
 *                      number here is meaningless.
 *  - `mapNinetyEast` — the map 90 degrees east, under matched lighting: what
 *                      the reader would have been shown under the defect.
 */
function probeStation(stationId: string) {
  const station = stations.find((candidate) => candidate.id === stationId);
  if (!station) throw new Error(`no station ${stationId}`);
  const size = new THREE.Vector2();
  renderer().getDrawingBufferSize(size);
  const centreX = size.x / 2;
  const centreY = size.y / 2;

  aimAt(station.latitudeDeg, station.longitudeDeg);

  // Where the overlay actually puts the pin, in drawing-buffer pixels.
  const projected = layer
    .scenePosition(stations.indexOf(station))!
    .applyMatrix4((internals.earthFixedGroup as THREE.Group).matrixWorld)
    .project(internals.camera);
  const pinX = ((projected.x + 1) / 2) * size.x;
  const pinY = ((projected.y + 1) / 2) * size.y;

  layer.setVisible(false);
  draw();
  const mapUnderPin = readPatch(centreX, centreY, 6);

  layer.setVisible(true);
  draw();
  const pinDrawn = readPatch(centreX, centreY, 6);

  // The same geographic latitude, ninety degrees east: where the map would
  // have been drawn under the quarter-turn.
  layer.setVisible(false);
  const ninetyEast = ((station.longitudeDeg + 90 + 180) % 360 + 360) % 360 - 180;
  aimAt(station.latitudeDeg, ninetyEast);
  draw();
  const mapNinetyEast = readPatch(centreX, centreY, 6);
  layer.setVisible(true);

  return {
    id: station.id,
    name: station.name,
    latitudeDeg: station.latitudeDeg,
    longitudeDeg: station.longitudeDeg,
    pinOffsetPx: Math.hypot(pinX - centreX, pinY - centreY),
    mapUnderPin,
    pinDrawn,
    mapNinetyEast,
  };
}

/** Ids the spec can iterate without hard-coding the table. */
function stationIds() {
  return stations.map((station) => station.id);
}

/**
 * Put the quarter-turn back.
 *
 * The defect that shipped was `rotation.y = -PI/2` on the Earth mesh while the
 * pins stayed vector geometry. Reintroducing it here, on the real mesh, lets
 * the spec prove that these probes actually catch it — rather than asserting
 * that correct code is correct, which is what the previous version of this
 * class of test did right up until someone looked at the globe.
 */
function setDefect(enabled: boolean) {
  const earth = (internals.earthFixedGroup as THREE.Group).children.find(
    (child) => child instanceof THREE.Mesh
      && (child.material as { map?: { image?: unknown } }).map?.image instanceof HTMLCanvasElement,
  ) as THREE.Mesh | undefined;
  if (!earth) throw new Error("could not find the Earth mesh");
  earth.rotation.y = enabled ? -Math.PI / 2 : 0;
  earth.updateMatrixWorld(true);
}

Object.assign(window as unknown as Record<string, unknown>, {
  groundStationProbe: { probeStation, stationIds, setDefect },
  groundStationProbeReady: true,
});
