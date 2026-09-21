/**
 * Browser-side half of the ground-perturbation overlay's geography guard.
 *
 * The unit tests pin the arithmetic: the grid decodes, the columns sum, the
 * texture offset is the offset every other map here uses. None of that answers
 * the only question a reader can actually check — is the disturbance drawn over
 * the part of the Earth the numbers put it over?
 *
 * The map is a texture and the field is another texture laid on a second
 * sphere. A rotation, a mirror or a half-cell slip applied to one and not the
 * other is invisible to every numerical test and is the whole of what the
 * reader sees. So this builds the production globe, mounts the overlay through
 * the same `setGroundFieldModel` the site will call, and reads the rendered
 * pixels back against the decoded value at the same latitude and longitude.
 */
import * as THREE from "three";
import { SpaceGlobe, geoToSceneVector } from "../src/globe";
import type { LandGeoJson } from "../src/globe";
import { worldOutlines } from "../src/data/world-outlines";
import {
  GROUND_FIELD_SYSTEM_ORDER,
  groundHorizontalMagnitude,
  selectGroundFieldFrame,
  type GroundCurrentSystemKey,
  type GroundFieldBundle,
} from "../src/ground-perturbation";
import type { SatelliteRecord } from "../src/types";

declare global {
  interface Window {
    groundFieldProbeReady?: boolean;
    groundFieldProbeError?: string;
    groundFieldProbe?: typeof api;
  }
}

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

function renderer(): THREE.WebGLRenderer {
  return internals.renderer as THREE.WebGLRenderer;
}

function draw() {
  renderer().render(internals.scene, internals.camera);
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
  return { red: red / count, green: green / count, blue: blue / count };
}

/**
 * Point the production camera straight down a geographic direction.
 *
 * The Earth-fixed group is rotated by Greenwich sidereal angle for the selected
 * UTC, so a scene azimuth is NOT a geographic longitude. The camera direction
 * therefore has to be carried through the group's own world rotation — the same
 * matrix the coastlines, the graticule and this overlay are all drawn under.
 * Skipping this is how a probe reads pixels from one meridian while quoting
 * numbers from another and calls the agreement a success.
 */
function aimAt(latitudeDeg: number, longitudeDeg: number) {
  const group = internals.earthFixedGroup as THREE.Group;
  group.updateMatrixWorld(true);
  const direction = geoToSceneVector(latitudeDeg, longitudeDeg, 1)
    .applyMatrix4(new THREE.Matrix4().extractRotation(group.matrixWorld));
  internals.camera.position.copy(direction.multiplyScalar(300));
  internals.camera.lookAt(0, 0, 0);
  internals.camera.updateMatrixWorld();
  internals.controls.target.set(0, 0, 0);
}

let bundle: GroundFieldBundle | null = null;
let selectedValidAt = "";

async function load() {
  const manifest = await (await fetch("/data/manifest.json")).json();
  const record = manifest.groundField;
  if (!record) throw new Error("the published manifest carries no groundField record");
  bundle = (await (await fetch(`/data/${record.path}`)).json()) as GroundFieldBundle;
  // The middle of the published window, so the probe is never sitting on an
  // edge frame whose neighbours are absent.
  const middle = bundle.frames[Math.floor(bundle.frames.length / 2)]!;
  selectedValidAt = middle.validAt;
  globe.setSimulationTime(new Date(selectedValidAt));
  globe.setGroundFieldModel(bundle);
  globe.setLayer("groundField", true);
  globe.setSimulationTime(new Date(selectedValidAt));
}

/**
 * One place, two facts: what the model says there, and what is drawn there.
 *
 * `overlayDelta` is the overlay's own contribution — the frame drawn with the
 * layer on minus the frame drawn with it off — so the Earth's own colour, the
 * lighting and the coastline under the probe all cancel out.
 */
function probe(latitudeDeg: number, longitudeDeg: number, system: GroundCurrentSystemKey = "total") {
  if (!bundle) throw new Error("bundle not loaded");
  const selection = selectGroundFieldFrame(bundle, selectedValidAt)!;
  const values = groundHorizontalMagnitude(bundle, selection.frame, system).values;
  const grid = bundle.grid;
  const span = grid.longitudeCount * grid.longitudeStepDeg;
  const column = Math.round(((((longitudeDeg - grid.longitudeStartDeg) % span) + span) % span) / grid.longitudeStepDeg)
    % grid.longitudeCount;
  const row = Math.round((latitudeDeg - grid.latitudeStartDeg) / grid.latitudeStepDeg);
  const cell = row * grid.longitudeCount + column;
  const modelNt = row >= 0 && row < grid.latitudeCount ? values[cell]! : Number.NaN;

  const size = new THREE.Vector2();
  renderer().getDrawingBufferSize(size);
  heldAim = { latitudeDeg, longitudeDeg };
  aimAt(latitudeDeg, longitudeDeg);

  globe.setLayer("groundField", false);
  draw();
  const without = readPatch(size.x / 2, size.y / 2, 8);
  globe.setLayer("groundField", true);
  draw();
  const withLayer = readPatch(size.x / 2, size.y / 2, 8);

  return {
    latitudeDeg,
    longitudeDeg,
    cellLatitudeDeg: grid.latitudeStartDeg + row * grid.latitudeStepDeg,
    cellLongitudeDeg: grid.longitudeStartDeg + column * grid.longitudeStepDeg,
    modelNt,
    without,
    withLayer,
    overlayDelta:
      Math.abs(withLayer.red - without.red)
      + Math.abs(withLayer.green - without.green)
      + Math.abs(withLayer.blue - without.blue),
  };
}

function frameSummary() {
  if (!bundle) throw new Error("bundle not loaded");
  const selection = selectGroundFieldFrame(bundle, selectedValidAt)!;
  const state = globe.getGroundFieldState();
  return {
    validAt: selection.frame.validAt,
    runAt: selection.frame.runAt,
    leadMinutes: selection.frame.leadMinutes,
    extrema: selection.frame.extrema,
    frameCount: bundle.frames.length,
    coverageComplete: bundle.time.coverageComplete,
    status: state?.status ?? "absent",
    systems: [...GROUND_FIELD_SYSTEM_ORDER],
  };
}

/**
 * Camera and system controls the screenshot pass drives.
 *
 * The production globe runs its own animation loop and its own OrbitControls,
 * both of which put the camera back where they think it belongs on the next
 * frame. A single `aimAt` therefore survives a synchronous pixel read but not a
 * screenshot, which waits for the compositor. So the aim is held and re-applied
 * every frame for as long as the screenshot pass wants it.
 */
let heldAim: { latitudeDeg: number; longitudeDeg: number } | null = null;

function holdAim() {
  if (heldAim) {
    internals.controls.enabled = false;
    aimAt(heldAim.latitudeDeg, heldAim.longitudeDeg);
  }
  requestAnimationFrame(holdAim);
}
requestAnimationFrame(holdAim);

function view(latitudeDeg: number, longitudeDeg: number, system: GroundCurrentSystemKey) {
  globe.setGroundFieldSystem(system);
  heldAim = { latitudeDeg, longitudeDeg };
  aimAt(latitudeDeg, longitudeDeg);
  draw();
  return { system, latitudeDeg, longitudeDeg, currentSystem: globe.getGroundFieldState()?.legend.system };
}

/**
 * The strongest and weakest published cells, chosen from the data at run time.
 *
 * Hard-coded probe sites would make this test's contrast depend on how active
 * the Sun happens to be while it runs. Taking the extremes from the frame
 * itself guarantees the contrast exists, and reports the contrast so a flat
 * field fails as "the field is flat" rather than as an unexplained miss.
 */
function extremeCells() {
  if (!bundle) throw new Error("bundle not loaded");
  const selection = selectGroundFieldFrame(bundle, selectedValidAt)!;
  const values = groundHorizontalMagnitude(bundle, selection.frame, "total").values;
  const grid = bundle.grid;
  let strongest = 0;
  let weakest = 0;
  for (let index = 1; index < values.length; index += 1) {
    if (!Number.isFinite(values[index]!)) continue;
    if (values[index]! > values[strongest]!) strongest = index;
    if (values[index]! < values[weakest]!) weakest = index;
  }
  const place = (index: number) => ({
    latitudeDeg: grid.latitudeStartDeg + Math.floor(index / grid.longitudeCount) * grid.latitudeStepDeg,
    longitudeDeg: grid.longitudeStartDeg + (index % grid.longitudeCount) * grid.longitudeStepDeg,
    modelNt: values[index]!,
  });
  return { strongest: place(strongest), weakest: place(weakest) };
}

/** Diagnostics, so a probe that drifted can be caught rather than believed. */
function sceneState() {
  const group = internals.earthFixedGroup as THREE.Group;
  group.updateMatrixWorld(true);
  return {
    earthRotationDeg: (group.rotation.y * 180) / Math.PI,
    simulationTime: (internals.simulationTime as Date).toISOString(),
    selectedValidAt,
    layerVisible: (globe.getGroundFieldState()?.visible ?? null),
    system: globe.getGroundFieldState()?.legend.system ?? null,
  };
}

const api = { probe, frameSummary, view, sceneState, extremeCells, selectedValidAt: () => selectedValidAt };

load()
  .then(() => {
    window.groundFieldProbe = api;
    window.groundFieldProbeReady = true;
  })
  .catch((error: unknown) => {
    window.groundFieldProbeError = String(error);
    window.groundFieldProbeReady = false;
  });
