import { describe, expect, it } from "vitest";
import { gstime } from "satellite.js";
import { propagateOmm } from "../src/orbit";
import {
  GROUND_TRACK_MAX_GAP_DEG,
  groundSeparationDeg,
  groundTrackExtent,
  normalizeGroundTrackPoints,
  sampleGroundTrack,
  segmentGroundTrack,
  shouldShowCompactGeosynchronousInset,
  type GroundTrackPoint,
} from "../src/ground-track-map";
import type { OmmRecord } from "../src/types";

/**
 * Does the polyline we draw actually match SGP4, or are we drawing our own
 * artifacts?
 *
 * The question came from a real observation: the sub-satellite trace of an
 * inclined geosynchronous spacecraft visibly wobbles. Either that is the
 * genuine analemma — inclination gives a twice-a-day east-west swing,
 * eccentricity a once-a-day one — or it is straight-line interpolation between
 * widely spaced samples, an antimeridian unwrapping mistake, or a frame error.
 *
 * These are the numbers that separate those cases. They are pinned so that
 * coarsening the sampling, or breaking the ECI-to-Earth-fixed conversion, fails
 * a test instead of quietly changing the physics on a teaching site.
 *
 * Elements: CelesTrak OMM for SKYTERRA 1 (NORAD 37218), taken verbatim from the
 * cached mirror at runtime/celestrak-mirror/gp-active.json. Inlined so the test
 * does not depend on runtime data or on any network access.
 */
const SKYTERRA_1: OmmRecord = {
  OBJECT_NAME: "SKYTERRA 1",
  OBJECT_ID: "2010-061A",
  EPOCH: "2026-08-07T13:54:09.581184",
  MEAN_MOTION: 1.00271242,
  ECCENTRICITY: 0.0001801,
  INCLINATION: 5.2303,
  RA_OF_ASC_NODE: 50.7409,
  ARG_OF_PERICENTER: 41.2701,
  MEAN_ANOMALY: 331.2984,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 37218,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 5771,
  BSTAR: 0,
  MEAN_MOTION_DOT: -1.21e-6,
  MEAN_MOTION_DDOT: 0,
} as unknown as OmmRecord;

const CENTRE = new Date("2026-08-07T19:38:15Z");
/** What ExplorerApp.openGroundTrackMap() builds for a geosynchronous object. */
const WINDOW_MINUTES = 24 * 60;
const SAMPLES = 288;

function subpoint(offsetMinutes: number) {
  const at = new Date(CENTRE.getTime() + offsetMinutes * 60_000);
  const state = propagateOmm(SKYTERRA_1, at);
  if (!state) throw new Error(`SGP4 returned nothing at ${at.toISOString()}`);
  return { longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg, at };
}

function drawnSamples(): GroundTrackPoint[] {
  return Array.from({ length: SAMPLES + 1 }, (_, index) =>
    subpoint((index / SAMPLES - 0.5) * WINDOW_MINUTES));
}

function unwrap(longitudes: readonly number[]): number[] {
  const out = [longitudes[0]!];
  for (let index = 1; index < longitudes.length; index += 1) {
    let value = longitudes[index]!;
    while (value - out[index - 1]! > 180) value -= 360;
    while (value - out[index - 1]! < -180) value += 360;
    out.push(value);
  }
  return out;
}

/** Least-squares amplitude at k cycles across the whole window. */
function harmonicAmplitude(values: readonly number[], cyclesPerWindow: number): number {
  const count = values.length - 1;
  let cosine = 0;
  let sine = 0;
  for (let index = 0; index < count; index += 1) {
    const angle = (2 * Math.PI * cyclesPerWindow * index) / count;
    cosine += values[index]! * Math.cos(angle);
    sine += values[index]! * Math.sin(angle);
  }
  return Math.hypot((2 * cosine) / count, (2 * sine) / count);
}

describe("SKYTERRA 1 ground-track fidelity", () => {
  const drawn = drawnSamples();
  const normalized = normalizeGroundTrackPoints(drawn);
  const longitudes = unwrap(normalized.map((point) => point.longitudeDeg));
  const latitudes = normalized.map((point) => point.latitudeDeg);
  const longitudeSpan = Math.max(...longitudes) - Math.min(...longitudes);
  const latitudeSpan = Math.max(...latitudes) - Math.min(...latitudes);

  it("produces the analemma the orbital elements predict", () => {
    // Latitude amplitude is the inclination, 5.2303 deg, carried up slightly by
    // the geodetic latitude conversion.
    expect(latitudeSpan).toBeGreaterThan(2 * SKYTERRA_1.INCLINATION);
    expect(latitudeSpan).toBeLessThan(2 * SKYTERRA_1.INCLINATION * 1.02);
    expect(latitudeSpan).toBeCloseTo(10.501, 2);

    // The east-west swing is real, and it is small: a quarter of a degree.
    expect(longitudeSpan).toBeCloseTo(0.263, 3);

    // 40 times taller than wide. This is why it looks like a straight line with
    // a wobble on it rather than a figure of eight.
    expect(latitudeSpan / longitudeSpan).toBeGreaterThan(35);
  });

  it("puts the east-west swing at twice a day, as inclination requires", () => {
    const twicePerDay = harmonicAmplitude(longitudes, 2);
    const oncePerDay = harmonicAmplitude(longitudes, 1);

    // Closed-form inclination term for a near-circular geosynchronous orbit:
    // amplitude = i^2 / 4 radians.
    const inclination = (SKYTERRA_1.INCLINATION * Math.PI) / 180;
    const predicted = ((inclination ** 2 / 4) * 180) / Math.PI;
    // The closed form is first order in inclination, so agreement to better
    // than one percent is the strongest claim that can honestly be made.
    expect(Math.abs(twicePerDay - predicted) / predicted).toBeLessThan(0.01);
    expect(twicePerDay).toBeCloseTo(0.1199, 3);

    // The once-a-day term is the eccentricity term, 2e radians, an order of
    // magnitude smaller.
    expect(oncePerDay).toBeLessThan(twicePerDay / 4);
    expect(oncePerDay).toBeCloseTo(0.0217, 3);

    // Nothing faster survives. If a high-frequency term ever appeared here it
    // would be numerical, not physical.
    for (let cycles = 3; cycles <= 24; cycles += 1) {
      expect(harmonicAmplitude(longitudes, cycles)).toBeLessThan(twicePerDay / 100);
    }

    // Latitude is a clean once-a-day sinusoid.
    expect(harmonicAmplitude(latitudes, 1)).toBeGreaterThan(5.2);
    expect(harmonicAmplitude(latitudes, 2)).toBeLessThan(0.05);
  });

  it("draws straight chords that stay far below one pixel from the true curve", () => {
    // The polyline is straight lines between the drawn samples. Compare the
    // chord against SGP4 at four points inside every interval.
    let worstLongitude = 0;
    let worstLatitude = 0;
    for (let index = 0; index < normalized.length - 1; index += 1) {
      const startMinutes = (index / SAMPLES - 0.5) * WINDOW_MINUTES;
      const endMinutes = ((index + 1) / SAMPLES - 0.5) * WINDOW_MINUTES;
      for (const fraction of [0.2, 0.4, 0.6, 0.8]) {
        const truth = subpoint(startMinutes + (endMinutes - startMinutes) * fraction);
        const chordLongitude = longitudes[index]!
          + (longitudes[index + 1]! - longitudes[index]!) * fraction;
        const chordLatitude = latitudes[index]!
          + (latitudes[index + 1]! - latitudes[index]!) * fraction;
        let trueLongitude = truth.longitudeDeg;
        while (trueLongitude - chordLongitude > 180) trueLongitude -= 360;
        while (trueLongitude - chordLongitude < -180) trueLongitude += 360;
        worstLongitude = Math.max(worstLongitude, Math.abs(trueLongitude - chordLongitude));
        worstLatitude = Math.max(worstLatitude, Math.abs(truth.latitudeDeg - chordLatitude));
      }
    }
    expect(worstLongitude).toBeLessThan(1e-4);
    expect(worstLatitude).toBeLessThan(1e-3);

    // Stated as a fraction of the feature it could corrupt: interpolation
    // error is under one part in a thousand of the real east-west swing, so
    // the swing on screen is physics, not sampling.
    expect(worstLongitude / longitudeSpan).toBeLessThan(0.001);

    // And under a hundredth of a pixel at the size the map is drawn.
    const plotWidth = 960 - 44 - 18;
    expect((worstLongitude / 360) * plotWidth).toBeLessThan(0.01);
  });

  it("stays in one segment: this track never touches the antimeridian", () => {
    expect(segmentGroundTrack(normalized)).toHaveLength(1);
    for (const [index, longitude] of longitudes.entries()) {
      if (index === 0) continue;
      expect(Math.abs(longitude - longitudes[index - 1]!)).toBeLessThan(0.02);
    }
  });

  it("converts from inertial to Earth-fixed with the right sidereal angle", () => {
    // Longitude must equal right ascension minus Greenwich sidereal time. If
    // the frames were mixed, or GMST were wrong, this is where it shows.
    const state = propagateOmm(SKYTERRA_1, CENTRE)!;
    const gmst = ((gstime(CENTRE) % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
    // Reconstruct right ascension from the Earth-fixed longitude and check it
    // lands back on the same instantaneous position after a whole sidereal day.
    expect(state.longitudeDeg).toBeCloseTo(-101.28, 2);
    expect((gmst * 180) / Math.PI).toBeCloseTo(250.9, 1);

    const siderealDayMs = 86_164_090.5;
    const later = propagateOmm(SKYTERRA_1, new Date(CENTRE.getTime() + siderealDayMs))!;
    expect(Math.abs(later.longitudeDeg - state.longitudeDeg)).toBeLessThan(0.05);
  });

  it("hands the map a track the global view cannot resolve, so the inset fires", () => {
    const extent = groundTrackExtent(normalized)!;
    const plotWidth = 960 - 44 - 18;
    expect((extent.longitudeSpanDeg / 360) * plotWidth).toBeLessThan(1);
    expect(shouldShowCompactGeosynchronousInset(
      normalized,
      { kind: "geosynchronous-analemma", hours: 24 },
    )).toBe(true);
  });
});

/**
 * The eccentric case, which is where the drawing broke.
 *
 * Five spacecraft were reported as looking wrong on the site — THEMIS D,
 * IMAGE, ASBM-1, Meridian-7 and by extension every Molniya — and the single
 * property they share is a large eccentricity. The propagation was never at
 * fault: SGP4 returns apogee and perigee altitudes matching those implied by
 * each object's own elements to within a few km. What was wrong is that the
 * track was sampled at a fixed 180 evenly spaced TIMES per orbit.
 *
 * Kepler's second law makes that uneven on the ground: near perigee the
 * sub-satellite point crosses a great deal of ground per minute, near apogee
 * almost none. For THEMIS D the largest gap between two consecutive drawn
 * points was 37 degrees of arc — about 4,100 km rendered as one straight line,
 * which is precisely the "kink" that was reported.
 */
const THEMIS_D: OmmRecord = {
  OBJECT_NAME: "THEMIS D",
  OBJECT_ID: "2007-004D",
  EPOCH: "2026-08-05T13:40:18.584",
  MEAN_MOTION: 0.87589303,
  ECCENTRICITY: 0.8320927,
  INCLINATION: 8.0114,
  RA_OF_ASC_NODE: 77.8495,
  ARG_OF_PERICENTER: 238.8253,
  MEAN_ANOMALY: 10.8238,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 30797,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 4150,
  BSTAR: 0,
  MEAN_MOTION_DOT: -5.5e-6,
  MEAN_MOTION_DDOT: 0,
} as unknown as OmmRecord;

describe("an eccentric ground track is sampled by distance, not by the clock", () => {
  const centre = new Date("2026-08-09T06:00:00Z");
  const periodMinutes = 1440 / THEMIS_D.MEAN_MOTION;
  const sample = (when: Date) => {
    const state = propagateOmm(THEMIS_D, when);
    return state ? { longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg } : null;
  };
  const maxGap = (points: readonly GroundTrackPoint[]) => {
    let worst = 0;
    for (let index = 1; index < points.length; index += 1) {
      worst = Math.max(worst, groundSeparationDeg(points[index - 1]!, points[index]!));
    }
    return worst;
  };

  it("reproduces the defect when refinement is disabled", () => {
    // maxGapDeg enormous == the old fixed-cadence behaviour, kept so the
    // regression is demonstrated rather than described.
    const coarse = sampleGroundTrack({
      at: centre, spanMinutes: periodMinutes, baseSamples: 180, sample, maxGapDeg: 1e9,
    });
    expect(coarse.length).toBe(181);
    expect(maxGap(coarse)).toBeGreaterThan(30);
  });

  it("closes every gap to the tolerance once refinement is on", () => {
    const refined = sampleGroundTrack({
      at: centre, spanMinutes: periodMinutes, baseSamples: 180, sample,
    });
    expect(maxGap(refined)).toBeLessThanOrEqual(GROUND_TRACK_MAX_GAP_DEG + 1e-6);
    expect(refined.length).toBeGreaterThan(181);
  });

  it("still spans one whole orbital period, and stays in time order", () => {
    const refined = sampleGroundTrack({
      at: centre, spanMinutes: periodMinutes, baseSamples: 180, sample,
    });
    const times = refined.map((p) => new Date(p.at as Date).getTime());
    expect(times).toEqual([...times].sort((a, b) => a - b));
    const spanMs = times[times.length - 1]! - times[0]!;
    expect(spanMs / 60000).toBeCloseTo(periodMinutes, 0);
  });

  it("costs a circular orbit nothing", () => {
    // The refinement must be free where it is not needed, or every LEO track
    // pays for the one eccentric case.
    const circular = (when: Date) => {
      const state = propagateOmm(SKYTERRA_1, when);
      return state ? { longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg } : null;
    };
    const points = sampleGroundTrack({
      at: CENTRE, spanMinutes: WINDOW_MINUTES, baseSamples: SAMPLES, sample: circular,
    });
    expect(points.length).toBe(SAMPLES + 1);
  });

  it("cannot be made to hang by a pathological orbit", () => {
    // Every sample lands somewhere new and far away: refinement can never
    // satisfy the tolerance, so the budget has to be what stops it.
    let call = 0;
    const adversarial = () => {
      call += 1;
      return { latitudeDeg: (call * 37) % 170 - 85, longitudeDeg: (call * 91) % 360 - 180 };
    };
    const points = sampleGroundTrack({
      at: centre, spanMinutes: periodMinutes, baseSamples: 20, sample: adversarial, budget: 500,
    });
    expect(call).toBeLessThanOrEqual(500);
    expect(points.length).toBeGreaterThan(0);
  });

  it("skips times the propagator cannot answer for, without dropping the rest", () => {
    let call = 0;
    const flaky = (when: Date) => {
      call += 1;
      return call % 7 === 0 ? null : sample(when);
    };
    const points = sampleGroundTrack({
      at: centre, spanMinutes: periodMinutes, baseSamples: 60, sample: flaky,
    });
    expect(points.length).toBeGreaterThan(40);
    expect(points.every((p) => Number.isFinite(p.latitudeDeg) && Number.isFinite(p.longitudeDeg))).toBe(true);
  });
});

describe("ground separation is measured on the sphere, not in longitude", () => {
  it("matches a known quarter of the equator", () => {
    expect(groundSeparationDeg(
      { latitudeDeg: 0, longitudeDeg: 0 }, { latitudeDeg: 0, longitudeDeg: 90 },
    )).toBeCloseTo(90, 6);
  });

  it("is zero for a repeated point", () => {
    expect(groundSeparationDeg(
      { latitudeDeg: 51.6, longitudeDeg: -0.1 }, { latitudeDeg: 51.6, longitudeDeg: -0.1 },
    )).toBeCloseTo(0, 9);
  });

  it("does not inflate a large longitude change close to the pole", () => {
    // 90 degrees of longitude at 89.5 N is about 0.9 degrees of ground. A
    // longitude-difference test would subdivide a polar orbit needlessly hard,
    // which is why IMAGE at 94 degrees inclination is measured this way.
    const separation = groundSeparationDeg(
      { latitudeDeg: 89.5, longitudeDeg: 0 }, { latitudeDeg: 89.5, longitudeDeg: 90 },
    );
    expect(separation).toBeLessThan(1);
  });
});
