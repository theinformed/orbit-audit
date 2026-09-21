import { describe, expect, it } from "vitest";

import fixture from "./fixtures/thermosphere-frame.json";
import {
  DEFAULT_ISOPYCNIC_KG_M3,
  circularOrbitalSpeedMs,
  decodeThermosphereFrame,
  densityKgM3,
  densityRatio,
  dragDecelerationMs2,
  isopycnicAltitudeKm,
  logDensityOnLevel,
  type ThermosphereFrame,
} from "../src/thermosphere";

/**
 * The fixture is written by the REAL Python encoder in pipeline/thermosphere.py,
 * over an atmosphere whose answer is known in closed form: an exponential with a
 * 50 km scale height and 1e-9 kg m^-3 at 200 km. So these tests check the
 * TypeScript decoder against arithmetic, and against the other language, rather
 * than against a second copy of the same assumptions.
 *
 * One cell — level 1 (300 km), latitude -60, longitude 0 — is deliberately
 * absent, to pin what happens at a hole.
 */

const SCALE_HEIGHT_KM = 50;
const DENSITY_AT_200_KM = 1e-9;
const expected = (altitudeKm: number) =>
  DENSITY_AT_200_KM * Math.exp(-(altitudeKm - 200) / SCALE_HEIGHT_KM);

const frame = decodeThermosphereFrame(fixture as unknown as ThermosphereFrame);

describe("decoding what the pipeline published", () => {
  it("reproduces the published densities to the quantum the encoder promises", () => {
    // 16-bit over the encoder's domain is 0.000145 dex, so agreement to five
    // significant figures is the contract, not a coincidence.
    for (const altitude of [200, 300, 400, 500]) {
      const level = frame.altitudeKm.indexOf(altitude);
      const value = 10 ** logDensityOnLevel(frame, level, 0, 90);
      expect(value / expected(altitude)).toBeCloseTo(1, 3);
    }
  });

  it("decodes a hole to NaN, never to the bottom of the scale", () => {
    // The bottom of the encoder's domain is 1e-17, which on a log axis spanning
    // eleven decades would read as a vacuum rather than as missing data.
    const level = frame.altitudeKm.indexOf(300);
    expect(logDensityOnLevel(frame, level, -60, 0)).toBeNaN();
  });

  it("refuses a frame whose declared grid and payload disagree", () => {
    const broken = JSON.parse(JSON.stringify(fixture)) as ThermosphereFrame;
    broken.grid.altitudeKm = [...broken.grid.altitudeKm, 600];
    expect(() => decodeThermosphereFrame(broken)).toThrow(/samples but carries/);
  });
});

describe("density between published levels", () => {
  it("is log-linear, which is near-exact for an exponential atmosphere", () => {
    // 350 km sits midway between two published levels 100 km apart. Linear
    // interpolation in density would overshoot by about 6% here; log-linear is
    // exact for this atmosphere, so the tolerance can be tight.
    const value = densityKgM3(frame, 0, 90, 350);
    expect(value).not.toBeNull();
    expect(value! / expected(350)).toBeCloseTo(1, 3);
  });

  it("returns null outside the published column rather than extrapolating", () => {
    expect(densityKgM3(frame, 0, 90, 150)).toBeNull();
    expect(densityKgM3(frame, 0, 90, 900)).toBeNull();
  });

  it("returns null when any corner of the cell is missing", () => {
    // A partly-missing cell is a gap. Filling it from the corners that survive
    // would invent a value precisely where the data says it has none.
    expect(densityKgM3(frame, -60, 0, 300)).toBeNull();
  });

  it("wraps across the longitude seam instead of clamping at it", () => {
    // 350 deg lies between the last published longitude (270) and the first (0).
    // Clamping would silently return the 270 deg column.
    const value = densityKgM3(frame, 0, 350, 400);
    expect(value).not.toBeNull();
    expect(value! / expected(400)).toBeCloseTo(1, 3);
  });
});

describe("the altitude of a density level, which is what the layer draws", () => {
  it("finds the closed-form altitude", () => {
    // rho = 1e-11 at 200 + 50 * ln(1e-9 / 1e-11) = 430.26 km.
    const altitude = isopycnicAltitudeKm(frame, 0, 90, 1e-11);
    expect(altitude).not.toBeNull();
    expect(altitude!).toBeCloseTo(430.26, 0);
  });

  it("returns null when the level is not crossed in the column", () => {
    // Denser than anything published: the surface is below the grid, and saying
    // so is the only honest answer. Clamping to 200 km would draw a real-looking
    // altitude that the data never supports.
    expect(isopycnicAltitudeKm(frame, 0, 90, 1e-6)).toBeNull();
    expect(isopycnicAltitudeKm(frame, 0, 90, 1e-20)).toBeNull();
  });

  it("resolves the default level inside the published column", () => {
    // For this fixture's atmosphere the closed-form answer is
    // 200 + 50 * ln(1e-9 / 1e-12) = 545.4 km.
    //
    // The band that motivated the default is a fact about the real field, not
    // about this fixture: measured on the NOAA WAM frame for 2026-08-17,
    // median density is 2.9e-12 at 400 km and 5.4e-13 at 500 km, so 1e-12 lands
    // between them — the shell carrying the ISS, most Earth-observation
    // satellites and the Starlink insertion orbits.
    const altitude = isopycnicAltitudeKm(frame, 0, 90, DEFAULT_ISOPYCNIC_KG_M3);
    expect(altitude).not.toBeNull();
    expect(altitude!).toBeCloseTo(545.4, 0);
    expect(altitude!).toBeGreaterThan(frame.altitudeKm[0]!);
    expect(altitude!).toBeLessThan(frame.altitudeKm[frame.altitudeKm.length - 1]!);
  });
});

describe("drag, stated honestly", () => {
  it("matches the pipeline's own formula", () => {
    // 0.5 * rho * v^2 / B, the same expression as drag_deceleration_m_s2.
    const density = 1e-12;
    const speed = circularOrbitalSpeedMs(400);
    const ballistic = 100;
    expect(dragDecelerationMs2(density, speed, ballistic))
      .toBeCloseTo((0.5 * density * speed * speed) / ballistic, 18);
  });

  it("puts circular speed at 400 km near 7.67 km/s", () => {
    expect(circularOrbitalSpeedMs(400) / 1000).toBeCloseTo(7.67, 1);
  });

  it("will not quote drag without a stated reference body", () => {
    // The catalogue holds no mass or cross-section, so the ballistic
    // coefficient cannot be defaulted into existence.
    expect(() => dragDecelerationMs2(1e-12, 7670, 0)).toThrow(/ballistic coefficient/);
  });

  it("reports the storm ratio, or nothing", () => {
    expect(densityRatio(frame, frame, 0, 90, 400)).toBeCloseTo(1, 9);
    expect(densityRatio(frame, frame, -60, 0, 300)).toBeNull();
  });
});
