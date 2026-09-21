import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  GROUND_FIELD_SYSTEM_ORDER,
  GroundPerturbationLayer,
  decodeGroundComponent,
  groundFieldColumnFor,
  groundFieldColumnLongitude,
  groundFieldRowFor,
  groundFieldRowLatitude,
  groundFieldLatitudeAtTextureV,
  groundFieldTextureLayout,
  groundFieldTextureOffsetX,
  groundHorizontalMagnitude,
  withPolarGuardRows,
  groundPerturbationColor,
  groundPerturbationRgba,
  sampleGroundPerturbation,
  selectGroundFieldFrame,
  type GroundComponentKey,
  type GroundCurrentSystemKey,
  type GroundFieldBundle,
  type GroundFieldFrame,
  type GroundFieldGrid,
} from "../src/ground-perturbation";
import { azimuthDifferenceDegrees, equirectangularLayerAzimuth, geoToSceneVector } from "../src/globe";

/**
 * Proofs for the ground magnetic perturbation overlay.
 *
 * The three things that can go wrong here without anyone noticing are all
 * geometric, and all three have precedent on this globe: a field drawn a
 * quarter-turn out, a field drawn upside down, and a missing value drawn as a
 * comfortable zero. Every assertion below is an arithmetic identity over a
 * fixture whose values are deliberately asymmetric, so a transpose, a mirror
 * or a rotation cannot pass by coincidence.
 */

const MINIMUM_NT = -5000;
const MAXIMUM_NT = 5000;
const QUANTUM_NT = (MAXIMUM_NT - MINIMUM_NT) / 65535;

/** The operational grid: 72 longitudes at 5°, 35 latitudes from -85° to +85°. */
const GRID: GroundFieldGrid = {
  longitudeCount: 72,
  latitudeCount: 35,
  longitudeStartDeg: 0,
  longitudeStepDeg: 5,
  latitudeStartDeg: -85,
  latitudeStepDeg: 5,
  cellCount: 72 * 35,
  ordering: "longitude cycles fastest; latitude runs south to north",
  polarCaps: "The source grid stops at the last row it publishes; nothing is extrapolated across the caps.",
};

const CELL_COUNT = GRID.longitudeCount * GRID.latitudeCount;

function encodeU16(values: number[]): string {
  const bytes = new Uint8Array(values.length * 2);
  const view = new DataView(bytes.buffer);
  for (let index = 0; index < values.length; index += 1) {
    const clamped = Math.min(1, Math.max(0, (values[index]! - MINIMUM_NT) / (MAXIMUM_NT - MINIMUM_NT)));
    view.setUint16(index * 2, Math.round(clamped * 65535), true);
  }
  return toBase64(bytes);
}

function encodeU8(values: number[]): string {
  return toBase64(Uint8Array.from(values));
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return globalThis.btoa(binary);
}

/** Distinct per system, component and cell, so a mix-up cannot cancel out. */
function cellValue(system: number, component: number, row: number, column: number): number {
  const seed = (system * 13 + component * 5 + row * 3 + column) % 89;
  return (seed - 44) * 4 + row * 0.5 - column * 0.25;
}

interface FixtureOptions {
  validAt?: string;
  missingCells?: number[];
  zeroEverything?: boolean;
}

function buildFrame(options: FixtureOptions = {}): GroundFieldFrame {
  const missing = new Set(options.missingCells ?? []);
  const fieldsU16 = {} as GroundFieldFrame["fieldsU16"];
  const fieldMasksU8 = {} as GroundFieldFrame["fieldMasksU8"];
  const componentValues = new Map<string, number[]>();
  GROUND_FIELD_SYSTEM_ORDER.forEach((system, systemIndex) => {
    fieldsU16[system] = {} as Record<GroundComponentKey, string>;
    fieldMasksU8[system] = {} as Record<GroundComponentKey, string>;
    (["north", "east", "down"] as GroundComponentKey[]).forEach((component, componentIndex) => {
      const values: number[] = [];
      const masks: number[] = [];
      for (let index = 0; index < CELL_COUNT; index += 1) {
        const row = Math.floor(index / GRID.longitudeCount);
        const column = index % GRID.longitudeCount;
        // "total" is the exact sum of the four sources, as the source file is.
        const value = options.zeroEverything
          ? 0
          : system === "total"
            ? [1, 2, 3, 4].reduce((sum, source) => sum + cellValue(source, componentIndex, row, column), 0)
            : cellValue(systemIndex, componentIndex, row, column);
        values.push(missing.has(index) ? 0 : value);
        masks.push(missing.has(index) ? 1 : 0);
      }
      componentValues.set(`${system}.${component}`, values);
      fieldsU16[system][component] = encodeU16(values);
      fieldMasksU8[system][component] = encodeU8(masks);
    });
  });
  const north = componentValues.get("total.north")!;
  const east = componentValues.get("total.east")!;
  let strongest = -1;
  let strongestIndex = 0;
  for (let index = 0; index < CELL_COUNT; index += 1) {
    if (missing.has(index)) continue;
    const horizontal = Math.hypot(north[index]!, east[index]!);
    if (horizontal > strongest) {
      strongest = horizontal;
      strongestIndex = index;
    }
  }
  return {
    validAt: options.validAt ?? "2026-08-08T18:00:00Z",
    runAt: "2026-08-08T17:03:00Z",
    leadMinutes: 57,
    fieldsU16,
    fieldMasksU8,
    extrema: {
      maximumHorizontalNt: strongest,
      maximumHorizontalLatitudeDeg: groundFieldRowLatitude(GRID, Math.floor(strongestIndex / GRID.longitudeCount)),
      maximumHorizontalLongitudeDeg: groundFieldColumnLongitude(GRID, strongestIndex % GRID.longitudeCount),
      maximumVerticalNt: 0,
      unusableCellCount: missing.size,
    },
  };
}

function buildBundle(frames: GroundFieldFrame[]): GroundFieldBundle {
  return {
    schema: 1,
    product: "swmf-ground-magnetic-perturbation",
    status: "model",
    evidence: "Model (physics simulation), published as forecast guidance",
    model: "NOAA operational Geospace SWMF: BATS-R-US + RIM ground magnetometer grid",
    coordinateSystem: "geographic (GEO) latitude/longitude, Earth-fixed",
    quantity: { name: "ground magnetic perturbation", units: "nT", components: "north, east, down", meaning: "" },
    grid: GRID,
    currentSystems: [
      { key: "total", label: "Total", meaning: "" },
      { key: "magnetospheric", sourceColumn: "Mhd", label: "Magnetospheric currents (lumped)", meaning: "ring current, cross-tail and magnetopause currents together" },
      { key: "fieldAligned", sourceColumn: "Fac", label: "Field-aligned (Birkeland) currents", meaning: "" },
      { key: "hall", sourceColumn: "Hal", label: "Hall currents (auroral electrojets)", meaning: "" },
      { key: "pedersen", sourceColumn: "Ped", label: "Pedersen currents", meaning: "" },
    ],
    attribution: "The four per-source fields are the model's own attribution. No instrument separates them.",
    fieldEncoding: { scale: "linear", minimum: MINIMUM_NT, maximum: MAXIMUM_NT, units: "nT" },
    fieldMaskEncoding: { storage: "", flags: { missing: 1, clippedLow: 2, clippedHigh: 4 }, meaning: "" },
    source: { name: "NOAA/NCEP NOMADS operational SWMF output, GM/IO2 mag_grid", url: "https://nomads.ncep.noaa.gov/", cadence: "" },
    time: {
      requestedFrom: frames[0]?.validAt ?? "",
      requestedTo: frames[frames.length - 1]?.validAt ?? "",
      coverageComplete: true,
      noDataIntervals: [],
      selectedFrameCount: frames.length,
    },
    history: { archived: false, meaning: "" },
    displayModes: { default: "smooth" },
    frames,
    caveat: "Physics-simulation output on a geographic grid, not a magnetometer measurement.",
  };
}

describe("the published grid, decoded", () => {
  const bundle = buildBundle([buildFrame()]);
  const frame = bundle.frames[0]!;

  it("decodes exactly one value per declared cell, for every system and component", () => {
    for (const system of GROUND_FIELD_SYSTEM_ORDER) {
      for (const component of ["north", "east", "down"] as GroundComponentKey[]) {
        const decoded = decodeGroundComponent(bundle, frame, system, component);
        expect(decoded.values.length).toBe(bundle.grid.longitudeCount * bundle.grid.latitudeCount);
        expect(decoded.mask.length).toBe(decoded.values.length);
      }
    }
  });

  it("refuses an array whose length does not match the declared grid", () => {
    const broken = structuredClone(frame);
    broken.fieldsU16.total.north = encodeU16([1, 2, 3]);
    expect(() => decodeGroundComponent(bundle, broken, "total", "north")).toThrow(/expected/);
  });

  it("keeps the four current systems summing to the total, cell by cell", () => {
    for (const component of ["north", "east", "down"] as GroundComponentKey[]) {
      const total = decodeGroundComponent(bundle, frame, "total", component).values;
      const parts = (["magnetospheric", "fieldAligned", "hall", "pedersen"] as GroundCurrentSystemKey[])
        .map((system) => decodeGroundComponent(bundle, frame, system, component).values);
      let worst = 0;
      for (let index = 0; index < total.length; index += 1) {
        const sum = parts.reduce((running, part) => running + part[index]!, 0);
        worst = Math.max(worst, Math.abs(sum - total[index]!));
      }
      // Four independently rounded numbers against one rounded total.
      expect(worst).toBeLessThanOrEqual(4 * QUANTUM_NT);
    }
  });

  it("computes the horizontal magnitude as the hypotenuse it claims to be", () => {
    const north = decodeGroundComponent(bundle, frame, "hall", "north").values;
    const east = decodeGroundComponent(bundle, frame, "hall", "east").values;
    const horizontal = groundHorizontalMagnitude(bundle, frame, "hall").values;
    for (let index = 0; index < horizontal.length; index += 7) {
      const expected = Math.hypot(north[index]!, east[index]!);
      // Stored as float32, so the identity holds to float32 precision and no
      // further. Six decimal places would be asserting a lie about the storage.
      expect(Math.abs(horizontal[index]! - expected)).toBeLessThanOrEqual(1e-6 * Math.max(1, expected));
    }
  });
});

describe("a value that is not there", () => {
  const missingCells = [0, 17, 900, CELL_COUNT - 1];
  const bundle = buildBundle([buildFrame({ missingCells })]);
  const frame = bundle.frames[0]!;

  it("decodes as NaN, never as zero", () => {
    const decoded = decodeGroundComponent(bundle, frame, "total", "north");
    for (const index of missingCells) {
      expect(Number.isNaN(decoded.values[index]!)).toBe(true);
      expect(decoded.values[index]).not.toBe(0);
    }
  });

  it("propagates through the horizontal magnitude rather than becoming a quiet cell", () => {
    const horizontal = groundHorizontalMagnitude(bundle, frame, "total");
    for (const index of missingCells) expect(Number.isNaN(horizontal.values[index]!)).toBe(true);
  });

  it("draws as fully transparent, and is counted", () => {
    const rendered = groundPerturbationRgba(bundle, frame);
    expect(rendered.missingCellCount).toBe(missingCells.length);
    for (const index of missingCells) expect(rendered.rgba[index * 4 + 3]).toBe(0);
  });

  it("is distinguishable from a verified quiet cell, which is drawn", () => {
    // The whole point. A field the model says is 0 nT and a field the model
    // did not produce must not paint the same pixels.
    const quiet = buildBundle([buildFrame({ zeroEverything: true })]);
    const rendered = groundPerturbationRgba(quiet, quiet.frames[0]!);
    expect(rendered.missingCellCount).toBe(0);
    expect(groundPerturbationColor(0)[3]).toBeGreaterThan(0);
    for (let index = 0; index < CELL_COUNT; index += 137) {
      expect(rendered.rgba[index * 4 + 3]!).toBeGreaterThan(0);
    }
  });

  it("reports a sampled point as null rather than as zero", () => {
    const sample = sampleGroundPerturbation(bundle, frame, GRID.latitudeStartDeg, GRID.longitudeStartDeg);
    expect(sample).not.toBeNull();
    expect(sample!.cellIndex).toBe(0);
    expect(sample!.systems.total.north).toBeNull();
    expect(sample!.systems.total.horizontal).toBeNull();
  });
});

describe("geographic coordinates, round-tripped", () => {
  const bundle = buildBundle([buildFrame()]);

  /**
   * Boulder, Colorado — the USGS magnetometer BOU, 40.137°N 254.764°E.
   *
   * A real place with a real instrument, chosen so a wrong answer is obviously
   * wrong: the nearest published cell is 40°N 255°E, in North America. A
   * quarter-turn error would put it in the Pacific.
   */
  const BOULDER = { latitudeDeg: 40.137, longitudeDeg: 254.764 };

  it("puts a landmark in the cell that holds it, and gives that cell back", () => {
    const column = groundFieldColumnFor(GRID, BOULDER.longitudeDeg);
    const row = groundFieldRowFor(GRID, BOULDER.latitudeDeg);
    expect(column).toBe(51);
    expect(row).toBe(25);
    expect(groundFieldColumnLongitude(GRID, column)).toBe(255);
    expect(groundFieldRowLatitude(GRID, row)).toBe(40);
    // Half a cell is 2.5°, and the landmark is inside that of the cell centre.
    expect(Math.abs(groundFieldColumnLongitude(GRID, column) - BOULDER.longitudeDeg)).toBeLessThanOrEqual(2.5);
    expect(Math.abs(groundFieldRowLatitude(GRID, row) - BOULDER.latitudeDeg)).toBeLessThanOrEqual(2.5);
  });

  it("wraps longitude the same whether it is given east or negative", () => {
    expect(groundFieldColumnFor(GRID, 254.764 - 360)).toBe(groundFieldColumnFor(GRID, 254.764));
    expect(groundFieldColumnFor(GRID, 357.6)).toBe(0);
    expect(groundFieldColumnFor(GRID, -2.4)).toBe(0);
  });

  it("refuses a latitude the source grid does not publish, rather than clamping to its edge", () => {
    expect(groundFieldRowFor(GRID, 89)).toBe(-1);
    expect(groundFieldRowFor(GRID, -89)).toBe(-1);
    expect(groundFieldRowFor(GRID, 85)).toBe(GRID.latitudeCount - 1);
  });

  it("draws the cell holding the landmark at the landmark's own longitude", () => {
    // The full chain: source column -> texel centre -> sampled u -> longitude.
    // u_sampled = (longitude + 180)/360 + offset, and the texel centre of
    // column c is (c + 0.5)/width. Solving for the longitude drawn at column c
    // must return that column's own longitude.
    const offset = groundFieldTextureOffsetX(GRID);
    const column = groundFieldColumnFor(GRID, BOULDER.longitudeDeg);
    const texelCentre = (column + 0.5) / GRID.longitudeCount;
    const drawnAt = 360 * (texelCentre - offset) - 180;
    expect(azimuthDifferenceDegrees(drawnAt, groundFieldColumnLongitude(GRID, column))).toBeCloseTo(0, 9);
  });

  it("uses the identical offset the D-RAP and aurora shells use", () => {
    // Written out longhand rather than imported, so a change to either copy
    // shows up here as a disagreement instead of moving both at once.
    const expected = (-GRID.longitudeStartDeg + GRID.longitudeStepDeg / 2 - 180) / 360;
    expect(groundFieldTextureOffsetX(GRID)).toBeCloseTo(expected, 12);
  });

  it("draws every longitude at the azimuth the globe's own vector transform gives it", () => {
    const layer = new GroundPerturbationLayer(bundle);
    layer.setSimulationTime(bundle.frames[0]!.validAt);
    for (const longitudeDeg of [-180, -135, -90, -45, 0, 45, 90, 135]) {
      const { azimuthDeg, textureCoordinateError } = equirectangularLayerAzimuth(layer.mesh, longitudeDeg);
      expect(textureCoordinateError).toBeLessThan(1e-6);
      expect(Math.abs(azimuthDifferenceDegrees(azimuthDeg, longitudeDeg))).toBeLessThan(1e-6);
      expect(azimuthDifferenceDegrees(
        azimuthDeg,
        (Math.atan2(
          -geoToSceneVector(0, longitudeDeg, 100).z,
          geoToSceneVector(0, longitudeDeg, 100).x,
        ) * 180) / Math.PI,
      )).toBeCloseTo(0, 6);
    }
    layer.dispose();
  });

  it("is not mirrored: the north of the texture is the north of the sphere", () => {
    const layer = new GroundPerturbationLayer(bundle);
    layer.setSimulationTime(bundle.frames[0]!.validAt);
    const texture = layer.texture;
    expect(texture).not.toBeNull();
    // South-to-north source rows on a bottom-origin DataTexture must NOT flip.
    expect(texture!.flipY).toBe(false);

    // And the geometry agrees: uv.y is the latitude's own fraction of the
    // sphere, so texture row r covers latitude start + r*step and nothing else.
    const uv = layer.mesh.geometry.getAttribute("uv");
    const position = layer.mesh.geometry.getAttribute("position");
    const radius = Math.hypot(position.getX(0), position.getY(0), position.getZ(0));
    let checked = 0;
    for (let index = 0; index < uv.count; index += 37) {
      const latitudeDeg = (Math.asin(position.getY(index) / radius) * 180) / Math.PI;
      expect(uv.getY(index)).toBeCloseTo((latitudeDeg + 90) / 180, 6);
      // Round-trip through the exact mapping the shipped texture uses: the
      // latitude a vertex sits at is the latitude the texture gives it back.
      const layout = groundFieldTextureLayout(GRID);
      const sampled = uv.getY(index) * layout.repeatY + layout.offsetY;
      // Four places: geometry attributes are float32, so a tighter assertion
      // would be a claim about the buffer's precision, not about the mapping.
      expect(groundFieldLatitudeAtTextureV(GRID, sampled)).toBeCloseTo(latitudeDeg, 4);
      checked += 1;
    }
    expect(checked).toBeGreaterThan(10);
    layer.dispose();
  });

  it("puts every published row back at its own latitude after the guard rows are added", () => {
    const layout = groundFieldTextureLayout(GRID);
    expect(layout.height).toBe(GRID.latitudeCount + 2);
    for (let row = 0; row < GRID.latitudeCount; row += 1) {
      const latitudeDeg = groundFieldRowLatitude(GRID, row);
      // The sampled coordinate three.js computes: uv.y * repeat + offset, with
      // uv.y the sphere's own (latitude + 90) / 180.
      const sampled = ((latitudeDeg + 90) / 180) * layout.repeatY + layout.offsetY;
      // must land exactly on the texel centre of the padded row.
      expect(sampled).toBeCloseTo((row + layout.guardRows + 0.5) / layout.height, 12);
      expect(groundFieldLatitudeAtTextureV(GRID, sampled)).toBeCloseTo(latitudeDeg, 9);
    }
  });

  it("samples a transparent guard row over the caps the model does not publish", () => {
    const layout = groundFieldTextureLayout(GRID);
    const rendered = withPolarGuardRows(groundPerturbationRgba(buildBundle([buildFrame()]), buildFrame()), GRID);
    expect(rendered.height).toBe(layout.height);
    // Both guard rows are fully transparent, all the way across.
    for (let column = 0; column < GRID.longitudeCount; column += 1) {
      expect(rendered.rgba[column * 4 + 3]).toBe(0);
      expect(rendered.rgba[((layout.height - 1) * GRID.longitudeCount + column) * 4 + 3]).toBe(0);
    }
    // And the pole itself samples inside one of them.
    for (const poleLatitude of [90, -90]) {
      const sampled = ((poleLatitude + 90) / 180) * layout.repeatY + layout.offsetY;
      const row = Math.floor(sampled * layout.height);
      expect(row === 0 || row === layout.height - 1).toBe(true);
    }
  });

  it("stops extrapolating exactly half a cell past the last published row", () => {
    const layout = groundFieldTextureLayout(GRID);
    const limit = Math.abs(GRID.latitudeStartDeg + (GRID.latitudeCount - 1) * GRID.latitudeStepDeg);
    // The boundary between the last published row and the guard row.
    const boundaryV = (layout.height - layout.guardRows) / layout.height;
    expect(groundFieldLatitudeAtTextureV(GRID, boundaryV)).toBeCloseTo(limit + GRID.latitudeStepDeg / 2, 9);
    const southBoundaryV = layout.guardRows / layout.height;
    expect(groundFieldLatitudeAtTextureV(GRID, southBoundaryV)).toBeCloseTo(-limit - GRID.latitudeStepDeg / 2, 9);
  });

  it("wires those numbers into the texture the layer actually installs", () => {
    const layer = new GroundPerturbationLayer(bundle, { enabled: true });
    layer.setSimulationTime(bundle.frames[0]!.validAt);
    const layout = groundFieldTextureLayout(GRID);
    expect(layer.texture!.image.height).toBe(layout.height);
    expect(layer.texture!.repeat.y).toBeCloseTo(layout.repeatY, 12);
    expect(layer.texture!.offset.y).toBeCloseTo(layout.offsetY, 12);
    expect(layer.texture!.repeat.x).toBe(1);
    expect(layer.texture!.userData.publishedLatitudeLimitDeg).toBe(85);
    layer.dispose();
  });

  it("carries no orienting rotation of its own", () => {
    const layer = new GroundPerturbationLayer(bundle);
    expect(layer.mesh.rotation.x).toBe(0);
    expect(layer.mesh.rotation.y).toBe(0);
    expect(layer.mesh.rotation.z).toBe(0);
    layer.dispose();
  });
});

describe("choosing a frame", () => {
  const frames = [0, 20, 40].map((minutes) =>
    buildFrame({ validAt: new Date(Date.UTC(2026, 7, 8, 18, minutes)).toISOString() }));
  const bundle = buildBundle(frames);

  it("snaps to the nearest published frame and never between them", () => {
    const selection = selectGroundFieldFrame(bundle, "2026-08-08T18:09:00Z");
    expect(selection!.frame.validAt).toBe(frames[0]!.validAt);
    expect(selection!.outsideSnapRadius).toBe(false);
    const later = selectGroundFieldFrame(bundle, "2026-08-08T18:11:00Z");
    expect(later!.frame.validAt).toBe(frames[1]!.validAt);
  });

  it("reports a time beyond the snap radius as outside coverage", () => {
    const selection = selectGroundFieldFrame(bundle, "2026-08-08T19:30:00Z");
    expect(selection!.outsideSnapRadius).toBe(true);
  });

  it("hides the shell and drops the texture rather than holding a stale field", () => {
    const layer = new GroundPerturbationLayer(bundle, { enabled: true });
    const ready = layer.setSimulationTime("2026-08-08T18:20:00Z");
    expect(ready.status).toBe("ready");
    expect(layer.mesh.visible).toBe(true);
    expect(layer.texture).not.toBeNull();

    const gone = layer.setSimulationTime("2026-08-08T22:00:00Z");
    expect(gone.status).toBe("no-data");
    expect(gone.status === "no-data" && gone.reason).toBe("outside-coverage");
    expect(layer.mesh.visible).toBe(false);
    expect(layer.texture).toBeNull();
    expect(layer.mesh.material.map).toBeNull();
    layer.dispose();
  });

  it("refuses a frame whose cells are mostly missing instead of drawing the holes", () => {
    const holed = buildFrame({
      validAt: "2026-08-08T18:00:00Z",
      missingCells: Array.from({ length: Math.ceil(CELL_COUNT * 0.5) }, (_value, index) => index),
    });
    const layer = new GroundPerturbationLayer(buildBundle([holed]), { enabled: true });
    const state = layer.setSimulationTime("2026-08-08T18:00:00Z");
    expect(state.status).toBe("no-data");
    expect(state.status === "no-data" && state.reason).toBe("invalid-frame");
    expect(layer.mesh.visible).toBe(false);
    layer.dispose();
  });

  it("stays hidden while switched off even with a valid frame", () => {
    const layer = new GroundPerturbationLayer(bundle, { enabled: false });
    const state = layer.setSimulationTime("2026-08-08T18:00:00Z");
    expect(state.status).toBe("ready");
    expect(layer.mesh.visible).toBe(false);
    expect(layer.setEnabled(true).visible).toBe(true);
    expect(layer.mesh.visible).toBe(true);
    layer.dispose();
  });
});

describe("switching current system", () => {
  const bundle = buildBundle([buildFrame()]);

  it("redraws from the chosen system's own numbers", () => {
    const layer = new GroundPerturbationLayer(bundle, { enabled: true });
    layer.setSimulationTime("2026-08-08T18:00:00Z");
    const total = layer.texture!.image.data as Uint8ClampedArray;
    const totalCopy = Uint8ClampedArray.from(total);
    layer.setCurrentSystem("hall");
    const hall = layer.texture!.image.data as Uint8ClampedArray;
    expect(layer.system).toBe("hall");
    expect(Array.from(hall)).not.toEqual(Array.from(totalCopy));
    expect(layer.texture!.userData.currentSystem).toBe("hall");
    layer.dispose();
  });

  it("refuses a system the bundle does not publish", () => {
    const layer = new GroundPerturbationLayer(bundle);
    expect(() => layer.setCurrentSystem("ringCurrent" as GroundCurrentSystemKey)).toThrow(RangeError);
    layer.dispose();
  });

  it("names the lumped magnetospheric field without calling it the ring current", () => {
    const layer = new GroundPerturbationLayer(bundle);
    layer.setCurrentSystem("magnetospheric");
    const legend = layer.legend(null);
    expect(legend.systemLabel.toLowerCase()).not.toContain("ring current");
    expect(legend.attribution.toLowerCase()).toContain("no instrument");
    layer.dispose();
  });

  it("tells the reader how far the frame leads the run that produced it", () => {
    const layer = new GroundPerturbationLayer(bundle, { enabled: true });
    layer.setSimulationTime("2026-08-08T18:00:00Z");
    const legend = layer.legend();
    expect(legend.leadMinutes).toBe(57);
    expect(Date.parse(legend.validAt!) - Date.parse(legend.runAt!)).toBe(57 * 60_000);
    expect(legend.sourceStatus).toBe("model");
    expect(legend.latitudeLimitDeg).toBe(85);
    layer.dispose();
  });
});

describe("the colour scale", () => {
  it("never decreases with magnitude", () => {
    let previousAlpha = -1;
    for (let nt = 0; nt <= 2000; nt += 25) {
      const alpha = groundPerturbationColor(nt)[3];
      expect(alpha).toBeGreaterThanOrEqual(previousAlpha);
      previousAlpha = alpha;
    }
  });

  it("gives a non-finite magnitude no colour at all", () => {
    expect(groundPerturbationColor(Number.NaN)).toEqual([0, 0, 0, 0]);
  });

  it("clamps above the top stop instead of wrapping round to a quiet colour", () => {
    const top = groundPerturbationColor(1500);
    expect(groundPerturbationColor(9000)).toEqual(top);
    expect(groundPerturbationColor(1e6)).toEqual(top);
  });
});

describe("the layer's place in the scene", () => {
  it("sits on a sphere barely above the Earth, not at an altitude it claims", () => {
    const layer = new GroundPerturbationLayer(buildBundle([buildFrame()]), { earthSceneRadius: 100 });
    const parameters = layer.mesh.geometry.parameters as THREE.SphereGeometry["parameters"];
    expect(parameters.radius).toBeGreaterThan(100);
    // Under a tenth of a percent: a depth-buffer separation, not an altitude.
    expect(parameters.radius).toBeLessThan(100.11);
    layer.dispose();
  });

  it("throws rather than silently drawing at a nonsense radius", () => {
    expect(() => new GroundPerturbationLayer(buildBundle([buildFrame()]), { earthSceneRadius: 0 })).toThrow(RangeError);
  });

  it("cannot be used after disposal", () => {
    const layer = new GroundPerturbationLayer(buildBundle([buildFrame()]));
    layer.dispose();
    expect(() => layer.setSimulationTime("2026-08-08T18:00:00Z")).toThrow(/disposed/);
  });
});
