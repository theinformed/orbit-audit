import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import * as THREE from "three";
import { describe, expect, it } from "vitest";

import { formatGeographicPoint, profileChartGeometry } from "../src/main";
import { EARTH_SCENE_RADIUS, geoToSceneVector, sceneVectorToGeo } from "../src/globe";
import { plasmaFrequencyMhz, type ProfileLevel } from "../src/ionosphere-profile";

/**
 * The geographic inverse is the one primitive the probe needed that this
 * codebase did not have, and a quarter-turn registration bug has already
 * shipped here once (`globe-texture-alignment.test.ts` exists because of it).
 * So this asserts against `geoToSceneVector` — the function the whole scene
 * draws with — rather than re-deriving the trigonometry a second time and
 * agreeing with itself.
 */
describe("recovering a place from a point in the scene", () => {
  const places: Array<[string, number, number]> = [
    ["the equator at Greenwich", 0, 0],
    ["Norfolk, Virginia", 36.85, -76.29],
    ["Yokosuka, Japan", 35.28, 139.67],
    ["the South Atlantic Anomaly's heart", -26, -45],
    ["the north pole", 89.9, 0],
    ["the antimeridian", 12, 180],
  ];

  it.each(places)("round-trips %s through the scene and back", (_name, latitudeDeg, longitudeDeg) => {
    const recovered = sceneVectorToGeo(geoToSceneVector(latitudeDeg, longitudeDeg, EARTH_SCENE_RADIUS));
    expect(recovered.latitudeDeg).toBeCloseTo(latitudeDeg, 6);
    // 180 and -180 are the same meridian; compare as a direction rather than
    // as a number so the antimeridian does not fail on its sign.
    expect(Math.cos((recovered.longitudeDeg * Math.PI) / 180)).toBeCloseTo(Math.cos((longitudeDeg * Math.PI) / 180), 6);
    expect(Math.sin((recovered.longitudeDeg * Math.PI) / 180)).toBeCloseTo(Math.sin((longitudeDeg * Math.PI) / 180), 6);
  });

  /** Any radius is the same direction: a click lands on a shell, not a point. */
  it("reads the same place at any radius, because the direction carries the geography", () => {
    const near = sceneVectorToGeo(geoToSceneVector(41.5, -70, EARTH_SCENE_RADIUS));
    const far = sceneVectorToGeo(geoToSceneVector(41.5, -70, EARTH_SCENE_RADIUS * 4.2));
    expect(far.latitudeDeg).toBeCloseTo(near.latitudeDeg, 9);
    expect(far.longitudeDeg).toBeCloseTo(near.longitudeDeg, 9);
  });

  it("refuses a zero-length vector rather than returning the equator at Greenwich", () => {
    expect(() => sceneVectorToGeo(new THREE.Vector3(0, 0, 0))).toThrow(/no geographic direction/);
  });
});

describe("how a clicked place is written", () => {
  it("uses hemisphere letters and folds longitude to the ±180 a chart is read in", () => {
    expect(formatGeographicPoint(36.85, -76.29)).toBe("36.9° N, 76.3° W");
    expect(formatGeographicPoint(-33.9, 151.2)).toBe("33.9° S, 151.2° E");
  });

  /**
   * The sampler reports longitude as 0–360 and this is the surface a reader
   * sees, so 285° has to come back as 75° W or the probe is quietly writing
   * coordinates in a convention no chart uses.
   */
  it("folds a 0–360 longitude back to the western hemisphere", () => {
    expect(formatGeographicPoint(0, 285)).toBe("0.0° N, 75.0° W");
  });
});

const level = (altitudeKm: number, electronDensityM3: number | null): ProfileLevel => ({
  altitudeKm,
  electronDensityM3,
  plasmaFrequencyMhz: plasmaFrequencyMhz(electronDensityM3),
});

describe("drawing the column", () => {
  const full = [level(90, 1e9), level(150, 2e11), level(300, 1.2e12), level(600, 2e11)];

  it("draws one continuous line through a column the model filled", () => {
    const { segments } = profileChartGeometry({ levels: full });
    expect(segments).toHaveLength(1);
    expect(segments[0]!.split(" ")).toHaveLength(4);
  });

  /**
   * A hole in the model must read as a hole. Bridging it would draw a
   * confident line through altitudes where WAM-IPE published nothing, which is
   * the same invention this site refuses everywhere else.
   */
  it("breaks the line at a level the model did not publish instead of bridging it", () => {
    const gapped = [level(90, 1e9), level(150, 2e11), level(300, null), level(600, 2e11), level(1000, 4e10)];
    const { segments } = profileChartGeometry({ levels: gapped });
    expect(segments).toHaveLength(2);
    expect(segments[0]!.split(" ")).toHaveLength(2);
    expect(segments[1]!.split(" ")).toHaveLength(2);
  });

  it("marks the peak on the row the densest level actually sits at", () => {
    const { peakY } = profileChartGeometry({ levels: full }, 220, 240);
    // 300 km of a 90–600 km column, drawn with y increasing downward.
    const expected = 240 - 24 - ((300 - 90) / (600 - 90)) * (240 - 48);
    expect(peakY).toBeCloseTo(expected, 6);
  });

  it("draws nothing at all from a column with fewer than two published levels", () => {
    expect(profileChartGeometry({ levels: [level(300, 1.2e12)] }).segments).toEqual([]);
    expect(profileChartGeometry({ levels: [level(300, null)] }).peakY).toBeNull();
  });
});

/**
 * This codebase has repeatedly shipped features that every unit test passed
 * over and no entry point reached — seven of them in one release. So the probe
 * asserts its own wiring: the markup it draws into, and the click path that
 * reaches it.
 */
describe("the probe is actually wired into the page", () => {
  it("ships the panel, the chart, the readings and the path-length control", () => {
    expect(indexMarkup).toContain('id="probe-panel"');
    expect(indexMarkup).toContain('id="probe-chart"');
    expect(indexMarkup).toContain('id="probe-readings"');
    expect(indexMarkup).toContain('id="probe-range"');
    expect(indexMarkup).toContain('id="probe-close"');
  });

  it("offers an empty click to the pins first and the globe second", () => {
    expect(explorerSource).toMatch(/if \(this\.pickGroundStation\(clientX, clientY\)\) return;\s*\n\s*this\.probeAt\(clientX, clientY\);/);
  });

  /**
   * The column is a 19 MB artifact and a click on the globe is easy to make by
   * accident. Spending that much of someone's phone data on a stray click is
   * the kind of thing this site should not do quietly, so the probe asks and
   * names the cost.
   */
  it("asks before spending 19 MB, rather than fetching the column on a stray click", () => {
    expect(indexMarkup).toContain('id="probe-load"');
    expect(indexMarkup).toMatch(/Load the ionosphere column \(19 MB\)/);
    expect(explorerSource).toContain("private loadProbeColumn()");
    // probeAt itself must not reach for the network.
    const probeAt = explorerSource.slice(explorerSource.indexOf("private probeAt("));
    expect(probeAt.slice(0, probeAt.indexOf("\n  }"))).not.toContain("loadIonosphereModel");
  });

  it("keeps one sampler for the bundle rather than decoding a frame per level", () => {
    expect(explorerSource).toContain("this.ionosphereSampler ??= new IonosphereSampler(bundle)");
    // And drops it when a new release lands, or the probe answers from the
    // frames of the artifact that was just replaced.
    expect(explorerSource).toContain("this.ionosphereSampler = null;");
  });

  /**
   * The probe is where the South Atlantic Anomaly becomes a number a visitor
   * can read off, rather than a shape somebody drew: click over Brazil and the
   * field is plainly weaker than at the same latitude on the far side of the
   * world. That is also what keeps `eccentric-dipole.ts` an imported module
   * rather than an orphan.
   */
  it("reports the field and the shell over the clicked place", () => {
    expect(explorerSource).toContain("eccentricDipoleFieldNt");
    expect(explorerSource).toContain("eccentricDipoleShell");
    expect(explorerSource).toContain("Field at 500 km");
    expect(explorerSource).toContain("L shell at 500 km");
    expect(indexMarkup).toContain('id="probe-field-limit"');
  });

  it("replaces each layer's essay with one link to where it is written", () => {
    expect(indexMarkup).toContain("data-card-build-link");
    expect(explorerSource).toContain("LAYER_METHOD_CARD_IDS");
    expect(explorerSource).toMatch(/How \$\{spec\.title\} is built/);
  });
});
