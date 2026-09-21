import { describe, expect, it } from "vitest";
import {
  IGRF_DIPOLE_EPOCH_YEAR,
  decimalYear,
  dipoleAxis,
  dipoleTilt,
  modifiedJulianDate,
  solarPosition,
} from "../src/dipole-tilt";

/**
 * These tests are written as physics identities rather than pinned outputs,
 * because a pinned output only proves the code still does what it did. Each
 * one below would fail for a different real mistake: a sign flip in the dipole
 * axis, a GEO/GEI rotation the wrong way, a sidereal-time term folded into the
 * wrong epoch, or a coefficient table edited without thinking.
 */
describe("geodipole axis", () => {
  it("puts the north geomagnetic pole where the IGRF epoch says it is", () => {
    const axis = dipoleAxis(IGRF_DIPOLE_EPOCH_YEAR);
    // IGRF-13 2020.0: about 80.6 N, 72.7 W. A sign error on the axis would put
    // it in the southern hemisphere or in Siberia instead of northern Canada.
    expect(axis.poleLatitudeDeg).toBeCloseTo(80.59, 1);
    expect(axis.poleLongitudeDeg).toBeCloseTo(-72.68, 1);
    expect(axis.surfaceFieldNt).toBeCloseTo(29806, -1);
  });

  it("returns a unit vector at every epoch it is asked for", () => {
    for (const year of [2015, 2020, 2026, 2030]) {
      const axis = dipoleAxis(year);
      const length = Math.hypot(...axis.geo);
      expect(length).toBeCloseTo(1, 12);
    }
  });

  it("drifts the pole slowly rather than jumping", () => {
    const start = dipoleAxis(2020);
    const end = dipoleAxis(2030);
    const shift = Math.hypot(
      end.poleLatitudeDeg - start.poleLatitudeDeg,
      (end.poleLongitudeDeg - start.poleLongitudeDeg) * Math.cos((start.poleLatitudeDeg * Math.PI) / 180),
    );
    expect(shift).toBeGreaterThan(0);
    expect(shift).toBeLessThan(1.5);
  });
});

describe("solar position", () => {
  it("has MJD 51544.5 at J2000", () => {
    expect(modifiedJulianDate(new Date("2000-01-01T12:00:00Z"))).toBeCloseTo(51544.5, 9);
  });

  it("returns a unit Sun vector whose declination follows the season", () => {
    const june = solarPosition(new Date("2026-06-21T12:00:00Z"));
    const december = solarPosition(new Date("2026-12-21T12:00:00Z"));
    expect(Math.hypot(...june.gei)).toBeCloseTo(1, 12);
    const juneDeclination = (Math.asin(june.gei[2]) * 180) / Math.PI;
    const decemberDeclination = (Math.asin(december.gei[2]) * 180) / Math.PI;
    expect(juneDeclination).toBeCloseTo(23.4, 0);
    expect(decemberDeclination).toBeCloseTo(-23.4, 0);
  });

  it("advances sidereal time by slightly more than 360 degrees per solar day", () => {
    const first = solarPosition(new Date("2026-03-01T00:00:00Z")).greenwichSiderealTimeDeg;
    const second = solarPosition(new Date("2026-03-02T00:00:00Z")).greenwichSiderealTimeDeg;
    const advance = (((second - first) % 360) + 360) % 360;
    expect(advance).toBeCloseTo(0.9856, 2);
  });

  it("counts the decimal year across a leap year", () => {
    expect(decimalYear(new Date("2024-01-01T00:00:00Z"))).toBeCloseTo(2024, 9);
    expect(decimalYear(new Date("2024-07-02T00:00:00Z"))).toBeCloseTo(2024.5, 2);
  });
});

describe("dipole tilt", () => {
  it("reaches the seasonal extremes the obliquity and the pole offset imply", () => {
    // Maximum tilt is the obliquity (23.44 deg) plus the dipole's own
    // colatitude (about 9.4 deg for the current epoch), and it is symmetric
    // between the solstices. Anything much larger means the two contributions
    // are being added twice; anything near 23 alone means the dipole offset is
    // being dropped.
    let minimum = Number.POSITIVE_INFINITY;
    let maximum = Number.NEGATIVE_INFINITY;
    for (let day = 0; day < 366; day += 1) {
      for (let hour = 0; hour < 24; hour += 1) {
        const time = new Date(Date.UTC(2026, 0, 1 + day, hour));
        const tilt = dipoleTilt(time)!;
        minimum = Math.min(minimum, tilt.degrees);
        maximum = Math.max(maximum, tilt.degrees);
      }
    }
    expect(maximum).toBeGreaterThan(32);
    expect(maximum).toBeLessThan(34);
    expect(minimum).toBeLessThan(-32);
    expect(minimum).toBeGreaterThan(-34);
  });

  it("swings diurnally by twice the dipole colatitude", () => {
    // On any one day the tilt traces a sinusoid whose amplitude is the dipole
    // colatitude, because the pole rotates about the geographic axis once a
    // day. A GEO-to-GEI rotation applied backwards keeps the amplitude but
    // reverses the phase, which this test would not catch alone - the next one
    // does.
    const day = "2026-06-21";
    let minimum = Number.POSITIVE_INFINITY;
    let maximum = Number.NEGATIVE_INFINITY;
    for (let minute = 0; minute < 24 * 60; minute += 10) {
      const time = new Date(`${day}T00:00:00Z`);
      time.setUTCMinutes(minute);
      const tilt = dipoleTilt(time)!;
      minimum = Math.min(minimum, tilt.degrees);
      maximum = Math.max(maximum, tilt.degrees);
    }
    expect((maximum - minimum) / 2).toBeCloseTo(9.4, 0);
  });

  it("peaks when the dipole meridian faces the Sun, not twelve hours later", () => {
    // The north geomagnetic pole is at about 72.7 W, so its meridian faces the
    // Sun near 17 UT and the June tilt maximum sits there. Rotating GEO to GEI
    // the wrong way moves this to about 05 UT, which is exactly the daily
    // minimum - so this is the test that catches a reversed rotation.
    let best = Number.NEGATIVE_INFINITY;
    let bestHour = -1;
    for (let hour = 0; hour < 24; hour += 1) {
      const value = dipoleTilt(new Date(Date.UTC(2026, 5, 21, hour)))!.degrees;
      if (value > best) {
        best = value;
        bestHour = hour;
      }
    }
    expect(bestHour).toBeGreaterThanOrEqual(16);
    expect(bestHour).toBeLessThanOrEqual(18);
  });

  it("crosses zero near the equinoxes", () => {
    // At equinox the tilt still swings by the dipole colatitude over the day,
    // so it must pass through zero rather than sit at it.
    const values: number[] = [];
    for (let hour = 0; hour < 24; hour += 1) {
      values.push(dipoleTilt(new Date(Date.UTC(2026, 2, 20, hour)))!.degrees);
    }
    expect(Math.min(...values)).toBeLessThan(0);
    expect(Math.max(...values)).toBeGreaterThan(0);
  });

  it("refuses an invalid time instead of returning an untilted dipole", () => {
    // Zero tilt is a real, common value, so it must never double as a failure.
    expect(dipoleTilt(new Date(Number.NaN))).toBeNull();
  });
});
