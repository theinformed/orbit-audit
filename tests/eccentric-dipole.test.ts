import { describe, expect, it } from "vitest";

import {
  ECCENTRIC_DIPOLE_LIMITATION,
  IGRF_REFERENCE_RADIUS_KM,
  eccentricDipole,
  eccentricDipoleFieldNt,
  eccentricDipoleLatitudeDeg,
  eccentricDipoleShell,
  eccentricOffsetGeographic,
  eccentricOffsetSm,
  dipoleAxisInSm,
} from "../src/eccentric-dipole";
import { decimalYear } from "../src/dipole-tilt";
import { dipoleAxis } from "../src/dipole-tilt";

const AT_2026 = eccentricDipole(2026.6);

describe("where the dipole actually sits", () => {
  /**
   * The published figure for the modern epoch is a displacement of roughly
   * 550 km. The handoff quotes "roughly 500 km"; either way an implementation
   * that returned 50 km or 5,000 km has the Fraser-Smith algebra wrong, and
   * the SAA would come out in the wrong place or not at all.
   */
  it("puts the dipole a few hundred kilometres off centre, not at the centre", () => {
    expect(AT_2026.offsetMagnitudeKm).toBeGreaterThan(400);
    expect(AT_2026.offsetMagnitudeKm).toBeLessThan(700);
  });

  /**
   * The offset and the tilt are two different quantities and this file must
   * not quietly redefine the second. The axis here has to be the same axis
   * `dipole-tilt.ts` computes, or the belts and the magnetopause would be
   * drawn about two different norths.
   */
  it("points along the same north geomagnetic axis the tilt module uses", () => {
    const [x, y, z] = dipoleAxis(2026.6).geo;
    expect(AT_2026.axis.x).toBeCloseTo(x, 12);
    expect(AT_2026.axis.y).toBeCloseTo(y, 12);
    expect(AT_2026.axis.z).toBeCloseTo(z, 12);
  });

  it("keeps the field strength in the right ballpark for Earth's surface", () => {
    // Roughly 30,000 nT at the magnetic equator and about twice that at the
    // pole is the textbook shape of a dipole field.
    expect(AT_2026.surfaceFieldNt).toBeGreaterThan(28_000);
    expect(AT_2026.surfaceFieldNt).toBeLessThan(32_000);
  });

  it("drifts slowly rather than jumping between epochs", () => {
    const then = eccentricDipole(2020.0);
    expect(Math.abs(AT_2026.offsetMagnitudeKm - then.offsetMagnitudeKm)).toBeLessThan(60);
  });
});

/**
 * The whole point, in Sean's words: "WE NEED users to be able to see the south
 * atlantic anomaly!!!! … it should just fall out of the data!"
 *
 * Nothing in this file names the South Atlantic, places a marker there, or
 * fits anything to it. The tests below search the globe and check where the
 * weak field lands. If the offset is right, it lands over the South Atlantic
 * on its own.
 */
describe("the South Atlantic Anomaly, as a consequence rather than an overlay", () => {
  const ALTITUDE_KM = 500;

  function weakestPoint() {
    let weakest = { latitudeDeg: 0, longitudeDeg: 0, fieldNt: Number.POSITIVE_INFINITY };
    for (let latitudeDeg = -80; latitudeDeg <= 80; latitudeDeg += 2) {
      for (let longitudeDeg = -180; longitudeDeg < 180; longitudeDeg += 2) {
        const fieldNt = eccentricDipoleFieldNt(AT_2026, latitudeDeg, longitudeDeg, ALTITUDE_KM);
        if (fieldNt < weakest.fieldNt) weakest = { latitudeDeg, longitudeDeg, fieldNt };
      }
    }
    return weakest;
  }

  it("finds its weakest surface field over the South Atlantic without being told to", () => {
    const weakest = weakestPoint();
    // The published anomaly centre sits off the Brazilian coast, around
    // 25° S and 45° W. A generous box around it still excludes every other
    // ocean, so this cannot pass by accident.
    expect(weakest.latitudeDeg).toBeGreaterThan(-55);
    expect(weakest.latitudeDeg).toBeLessThan(-5);
    expect(weakest.longitudeDeg).toBeGreaterThan(-90);
    expect(weakest.longitudeDeg).toBeLessThan(10);
  });

  /**
   * And it is a real depression, not a rounding wobble: the anomaly is
   * markedly weaker than the same magnetic latitude on the other side of the
   * world. That contrast is what makes a satellite trip its error counters
   * there and nowhere else on the same orbit.
   */
  it("draws a markedly weaker field there than at the antipodal longitude", () => {
    const anomaly = eccentricDipoleFieldNt(AT_2026, -25, -45, ALTITUDE_KM);
    const opposite = eccentricDipoleFieldNt(AT_2026, -25, 135, ALTITUDE_KM);
    expect(anomaly).toBeLessThan(opposite * 0.8);
  });

  /**
   * A centred dipole cannot produce it. This is the control: the same
   * geometry with the offset removed has no longitudinal structure at all, so
   * the belts drawn on it are the perfect circles Sean objected to.
   */
  it("has no anomaly at all once the offset is taken away", () => {
    const centred = { ...AT_2026, offsetKm: { x: 0, y: 0, z: 0 } };
    const anomaly = eccentricDipoleFieldNt(centred, -25, -45, ALTITUDE_KM);
    const opposite = eccentricDipoleFieldNt(centred, -25, 135, ALTITUDE_KM);
    // Only the ~11° axis tilt remains, which is far too small a variation to
    // read as an anomaly.
    expect(Math.abs(anomaly - opposite) / opposite).toBeLessThan(0.25);
    expect(anomaly / opposite).toBeGreaterThan(0.75);
  });
});

describe("the coordinates a belt is drawn about", () => {
  it("puts the magnetic equator off the geographic one, by about the dipole tilt", () => {
    const atGeographicEquator = eccentricDipoleLatitudeDeg(AT_2026, 0, -45, 500);
    expect(Math.abs(atGeographicEquator)).toBeGreaterThan(2);
    expect(Math.abs(atGeographicEquator)).toBeLessThan(35);
  });

  /**
   * The consequence for the picture, and the actual mechanism of the anomaly:
   * one L shell is NOT one altitude. Because the dipole is displaced toward
   * the western Pacific, the shell's equatorial crossing sits farther from
   * Earth's surface there and closer to it over the South Atlantic — so the
   * trapped population on that shell comes down into the atmosphere on one
   * side of the world and not the other. That lopsidedness is what a belt
   * drawn about the geographic equator erases, and it is why Sean's "so
   * perfect circular" objection was a bug report about the physics.
   */
  it("brings a fixed shell hundreds of kilometres closer to the ground over the South Atlantic", () => {
    // The shell's crossing of the MAGNETIC equator, which is the top of the
    // trapped population's bounce and the altitude that matters. A shell also
    // reaches the ground at mid magnetic latitudes at every longitude, so
    // "lowest point on the shell" is zero everywhere and says nothing.
    const equatorialCrossingAltitude = (longitudeDeg: number, shell: number) => {
      let best = { altitudeKm: Number.NaN, error: Number.POSITIVE_INFINITY };
      for (let latitudeDeg = -60; latitudeDeg <= 60; latitudeDeg += 0.1) {
        if (Math.abs(eccentricDipoleLatitudeDeg(AT_2026, latitudeDeg, longitudeDeg, 0)) > 1) continue;
        for (let altitudeKm = 0; altitudeKm <= 6_000; altitudeKm += 5) {
          const magnetic = Math.abs(eccentricDipoleLatitudeDeg(AT_2026, latitudeDeg, longitudeDeg, altitudeKm));
          if (magnetic > 1) continue;
          const error = Math.abs(eccentricDipoleShell(AT_2026, latitudeDeg, longitudeDeg, altitudeKm) - shell);
          if (error < best.error) best = { altitudeKm, error };
        }
      }
      return best.altitudeKm;
    };
    const anomaly = equatorialCrossingAltitude(-45, 1.5);
    const opposite = equatorialCrossingAltitude(135, 1.5);
    expect(Number.isFinite(anomaly)).toBe(true);
    expect(Number.isFinite(opposite)).toBe(true);
    expect(anomaly).toBeLessThan(opposite);
    // Not a rounding difference — the published anomaly is a descent of
    // several hundred kilometres, which is exactly why it is operationally
    // interesting rather than a curiosity.
    expect(opposite - anomaly).toBeGreaterThan(300);
  });

  it("reduces to the textbook shell value on the magnetic equator", () => {
    // At the magnetic equator L is just r/a, so a point one Earth radius out
    // should be close to 2 whatever longitude it is at.
    for (const longitudeDeg of [-120, -45, 30, 150]) {
      let best = { shell: 0, offset: Number.POSITIVE_INFINITY };
      for (let latitudeDeg = -45; latitudeDeg <= 45; latitudeDeg += 0.5) {
        const magnetic = Math.abs(eccentricDipoleLatitudeDeg(AT_2026, latitudeDeg, longitudeDeg, IGRF_REFERENCE_RADIUS_KM));
        if (magnetic < best.offset) {
          best = { shell: eccentricDipoleShell(AT_2026, latitudeDeg, longitudeDeg, IGRF_REFERENCE_RADIUS_KM), offset: magnetic };
        }
      }
      expect(best.shell).toBeGreaterThan(1.8);
      expect(best.shell).toBeLessThan(2.2);
    }
  });
});

/**
 * The handover to the renderer. The belts are still drawn about the geographic
 * equator; when they are moved onto the dipole, this is the form the offset
 * has to arrive in — the same geographic-direction form `globe.ts` already
 * uses for the dipole AXIS, and in Earth radii because the displacement must
 * happen before the shared radial ruler compresses it.
 */
describe("handing the offset to the renderer", () => {
  it("expresses the offset as a geographic direction and a distance in Earth radii", () => {
    const offset = eccentricOffsetGeographic(AT_2026);
    expect(offset.distanceRe).toBeGreaterThan(0.05);
    expect(offset.distanceRe).toBeLessThan(0.12);
    expect(Math.abs(offset.latitudeDeg)).toBeLessThanOrEqual(90);
    expect(Math.abs(offset.longitudeDeg)).toBeLessThanOrEqual(180);
  });

  /**
   * It must describe the SAME displacement the field calculation uses, or the
   * drawn belts would be lopsided in a different direction from the anomaly
   * the probe reports — the exact class of disagreement this project keeps
   * finding between a picture and its own numbers.
   */
  it("round-trips back to the cartesian offset the field maths uses", () => {
    const offset = eccentricOffsetGeographic(AT_2026);
    const latitude = (offset.latitudeDeg * Math.PI) / 180;
    const longitude = (offset.longitudeDeg * Math.PI) / 180;
    const distanceKm = offset.distanceRe * IGRF_REFERENCE_RADIUS_KM;
    expect(distanceKm * Math.cos(latitude) * Math.cos(longitude)).toBeCloseTo(AT_2026.offsetKm.x, 6);
    expect(distanceKm * Math.cos(latitude) * Math.sin(longitude)).toBeCloseTo(AT_2026.offsetKm.y, 6);
    expect(distanceKm * Math.sin(latitude)).toBeCloseTo(AT_2026.offsetKm.z, 6);
  });

  /**
   * And it points AWAY from the anomaly: the dipole is displaced toward the
   * western Pacific, which is why the field over the South Atlantic — on the
   * far side — is the weak one.
   */
  it("points away from the South Atlantic, which is why that side is the weak one", () => {
    const offset = eccentricOffsetGeographic(AT_2026);
    // Independently reproduced in Python from the same IAGA coefficients on
    // 2026-08-14: 609.5 km toward 22.7° N, 134.8° E — the western Pacific.
    // The anomaly sits very nearly antipodal to that, which is the whole
    // mechanism: displace the dipole one way and the far side is left weak.
    const anomalyLongitude = -45;
    const separation = Math.abs(((offset.longitudeDeg - anomalyLongitude + 540) % 360) - 180);
    expect(separation).toBeGreaterThan(120);
    expect(offset.longitudeDeg).toBeGreaterThan(90);
    expect(offset.latitudeDeg).toBeGreaterThan(0);
  });
});

describe("what a layer drawn on this is allowed to claim", () => {
  it("says it is a dipole fit and not the full IGRF, and refuses dose", () => {
    expect(ECCENTRIC_DIPOLE_LIMITATION).toMatch(/not the full\s+IGRF/i);
    expect(ECCENTRIC_DIPOLE_LIMITATION).toMatch(/dose/i);
  });
});


describe("the offset, expressed where the belts are drawn", () => {
  /**
   * The offset is fixed in geographic space but the belts live in Solar
   * Magnetic coordinates, so the offset sweeps around that frame once a day.
   * That sweep IS the South Atlantic Anomaly: it carries the inner belt down
   * over the South Atlantic and back up again.
   *
   * Every step of GEO -> GEI -> GSM -> SM is a rotation, so length is invariant
   * through the whole chain. These tests lean on that: a wrong step moves the
   * magnitude, and a wrong magnitude is a misplaced anomaly.
   */
  const times = [
    new Date("2026-01-01T00:00:00Z"),
    new Date("2026-03-21T06:00:00Z"),
    new Date("2026-06-21T12:00:00Z"),
    new Date("2026-08-18T18:00:00Z"),
    new Date("2026-12-31T23:00:00Z"),
  ];

  it("takes the dipole axis onto SM z, which is what SM means", () => {
    for (const time of times) {
      const axis = dipoleAxisInSm(time);
      expect(axis).not.toBeNull();
      expect(axis![0]).toBeCloseTo(0, 9);
      expect(axis![1]).toBeCloseTo(0, 9);
      expect(axis![2]).toBeCloseTo(1, 9);
    }
  });

  it("preserves the offset's length at every instant", () => {
    // Compared against the GEO magnitude AT THAT INSTANT, not one fixed number:
    // the IGRF coefficients drift, so the offset itself grows by about 0.6 km
    // across a year. What must be exactly invariant is the ROTATION — the same
    // vector seen from a turning frame — and that is what this checks.
    for (const time of times) {
      const expected = eccentricDipole(decimalYear(time)).offsetMagnitudeKm / 6371.2;
      const offset = eccentricOffsetSm(time);
      expect(offset).not.toBeNull();
      expect(offset!.magnitudeRe).toBeCloseTo(expected, 9);
    }
  });

  it("puts the offset where Fraser-Smith says: about 600 km", () => {
    const offset = eccentricOffsetSm(times[0]!)!;
    const km = offset.magnitudeRe * 6371.2;
    expect(km).toBeGreaterThan(400);
    expect(km).toBeLessThan(700);
  });

  it("sweeps through the frame as the Earth turns", () => {
    // Six hours apart the offset must point somewhere materially different, or
    // the anomaly would sit still and the whole point would be lost.
    const morning = eccentricOffsetSm(new Date("2026-08-18T00:00:00Z"))!;
    const evening = eccentricOffsetSm(new Date("2026-08-18T12:00:00Z"))!;
    const separation = Math.hypot(
      morning.x - evening.x,
      morning.y - evening.y,
      morning.z - evening.z,
    );
    expect(separation).toBeGreaterThan(0.5 * morning.magnitudeRe);
  });

  it("returns null rather than a centred dipole when the time is unusable", () => {
    // A zero offset is not a safe fallback: it is a silently centred dipole,
    // which is the picture this whole correction exists to replace.
    expect(eccentricOffsetSm(new Date(Number.NaN))).toBeNull();
    expect(dipoleAxisInSm(new Date(Number.NaN))).toBeNull();
  });
});
