import { describe, expect, it } from "vitest";

import {
  COLUMN_LIMITATION,
  GNSS_L1_MHZ,
  MUF_LIMITATION,
  columnPeak,
  gnssRangeErrorM,
  mufMhz,
  plasmaFrequencyMhz,
  profileDerivations,
  profileEvidenceNote,
  sampleProfile,
  verticalTecu,
  type ProfileLevel,
} from "../src/ionosphere-profile";
import type { IonosphereSampler, IonosphereSampleResult } from "../src/ionosphere-volume";

/**
 * A column with a Chapman-ish shape: an E ledge, an F2 peak at 300 km, and a
 * topside that decays. The exact numbers matter below, so they are written out
 * rather than generated.
 */
const COLUMN: ProfileLevel[] = [
  [90, 1e9],
  [110, 1.2e11],
  [150, 2.0e11],
  [200, 4.0e11],
  [300, 1.2e12],
  [400, 8.0e11],
  [600, 2.0e11],
  [1000, 4.0e10],
].map(([altitudeKm, density]) => ({
  altitudeKm: altitudeKm!,
  electronDensityM3: density!,
  plasmaFrequencyMhz: plasmaFrequencyMhz(density!),
}));

describe("the plasma frequency, which is exact physics rather than a fit", () => {
  /**
   * The textbook pair every ionospheric text prints: 1.24e12 m^-3 is a 10 MHz
   * critical frequency. If this drifts, the constant has been retyped wrong and
   * every HF number on the site is wrong with it.
   */
  it("puts a 10 MHz critical frequency at the textbook peak density", () => {
    expect(plasmaFrequencyMhz(1.24e12)).toBeCloseTo(10, 1);
  });

  it("scales as the square root of density, so four times the density is twice the frequency", () => {
    const single = plasmaFrequencyMhz(3e11)!;
    expect(plasmaFrequencyMhz(1.2e12)!).toBeCloseTo(2 * single, 6);
  });

  /**
   * A null density is a hole in the model, and a hole must not become a
   * number. Zero and negative are non-physical and are treated the same way:
   * the readout says nothing rather than saying 0 MHz, which a reader would
   * take to mean "no frequency reflects here" — a real and different claim.
   */
  it("returns nothing for an absent or non-physical density instead of inventing a frequency", () => {
    expect(plasmaFrequencyMhz(null)).toBeNull();
    expect(plasmaFrequencyMhz(0)).toBeNull();
    expect(plasmaFrequencyMhz(-1e11)).toBeNull();
    expect(plasmaFrequencyMhz(Number.NaN)).toBeNull();
  });
});

describe("the secant-law MUF", () => {
  it("is the vertical critical frequency itself for a zero-length path", () => {
    expect(mufMhz(9, 300, 0)).toBeCloseTo(9, 9);
  });

  /**
   * A 1,000 km hop off a 300 km layer: sec(phi) = sqrt(1 + (1000/600)^2) =
   * 1.9437, so a 9 MHz foF2 supports about 17.5 MHz. Worked by hand.
   */
  it("raises the usable frequency on a slanted path by the secant of the incidence angle", () => {
    expect(mufMhz(9, 300, 1_000)).toBeCloseTo(9 * Math.sqrt(1 + (1_000 / 600) ** 2), 6);
    expect(mufMhz(9, 300, 1_000)!).toBeCloseTo(17.49, 1);
  });

  it("rises with path length, because a shallower bounce reflects a higher frequency", () => {
    const short = mufMhz(9, 300, 500)!;
    const long = mufMhz(9, 300, 2_000)!;
    expect(long).toBeGreaterThan(short);
  });

  it("refuses a nonsensical layer height or a negative path rather than returning a number", () => {
    expect(mufMhz(9, 0, 1_000)).toBeNull();
    expect(mufMhz(9, 300, -10)).toBeNull();
    expect(mufMhz(0, 300, 1_000)).toBeNull();
  });

  /** The limitation travels with the number, and names the assumption that bites. */
  it("says out loud that it assumes a flat Earth and is not a propagation prediction", () => {
    expect(MUF_LIMITATION).toMatch(/flat/i);
    expect(MUF_LIMITATION).toMatch(/not a propagation prediction/i);
  });
});

describe("the column integral and what a GNSS receiver pays for it", () => {
  /**
   * A 300 km slab at 1e12 m^-3 is 3e17 electrons per square metre = 30 TECU.
   * Trapezium over a constant column is exact, so this is an arithmetic check
   * with no tolerance to hide behind.
   */
  it("integrates a constant slab to the arithmetic answer", () => {
    const slab: ProfileLevel[] = [200, 350, 500].map((altitudeKm) => ({
      altitudeKm,
      electronDensityM3: 1e12,
      plasmaFrequencyMhz: null,
    }));
    expect(verticalTecu(slab)!.tecu).toBeCloseTo(30, 6);
  });

  /**
   * 30 TECU at L1 is about 4.9 m of range error — the number every GNSS text
   * quotes for a moderately disturbed daytime ionosphere, and the reason
   * single-frequency receivers degrade during storms.
   */
  it("converts TEC to L1 range error at the published first-order constant", () => {
    expect(gnssRangeErrorM(30, GNSS_L1_MHZ)!).toBeCloseTo(4.87, 1);
  });

  it("charges a lower frequency more, as the inverse square of frequency", () => {
    const l1 = gnssRangeErrorM(30, GNSS_L1_MHZ)!;
    const l2 = gnssRangeErrorM(30, 1227.6)!;
    expect(l2 / l1).toBeCloseTo((GNSS_L1_MHZ / 1227.6) ** 2, 6);
  });

  /**
   * A single level is a reading, not an integral. Returning 0 TECU for it
   * would be a claim that the column is empty.
   */
  it("refuses to integrate a column with fewer than two valid levels", () => {
    expect(verticalTecu([{ altitudeKm: 300, electronDensityM3: 1e12, plasmaFrequencyMhz: null }])).toBeNull();
    expect(verticalTecu([])).toBeNull();
  });

  it("reports how many levels it actually used, so a gappy column is visibly weaker", () => {
    const gappy = COLUMN.map((level, index) =>
      index === 3 ? { ...level, electronDensityM3: null } : level);
    expect(verticalTecu(gappy)!.levelsUsed).toBe(COLUMN.length - 1);
    expect(verticalTecu(COLUMN)!.levelsUsed).toBe(COLUMN.length);
  });

  it("states that plasmaspheric content above the grid is not counted", () => {
    expect(COLUMN_LIMITATION).toMatch(/2,655/);
    expect(COLUMN_LIMITATION).toMatch(/NOT counted/);
  });
});

describe("the peak, taken from the grid rather than fitted", () => {
  it("finds the densest published level and reports its own altitude", () => {
    expect(columnPeak(COLUMN)).toEqual({ altitudeKm: 300, electronDensityM3: 1.2e12 });
  });

  it("has no peak to report when every level is a hole", () => {
    expect(columnPeak(COLUMN.map((level) => ({ ...level, electronDensityM3: null })))).toBeNull();
  });

  /**
   * The whole chain on one column: 1.2e12 m^-3 at 300 km is a 9.8 MHz foF2,
   * which is a textbook daytime mid-latitude value. hmF2 must land ON a
   * published altitude — a fitted height the source never resolved would be a
   * precision this data does not have.
   */
  it("derives foF2 and hmF2 that a working ionosphere would actually show", () => {
    const derived = profileDerivations(COLUMN)!;
    expect(derived.foF2Mhz).toBeCloseTo(9.84, 1);
    expect(derived.hmF2Km).toBe(300);
    expect(COLUMN.map((level) => level.altitudeKm)).toContain(derived.hmF2Km);
    expect(derived.verticalTecu).toBeGreaterThan(0);
    expect(derived.gnssRangeErrorL1M).toBeGreaterThan(0);
    expect(derived.integratedFromKm).toBe(90);
    expect(derived.integratedToKm).toBe(1_000);
  });

  it("derives nothing at all from a column the model did not fill", () => {
    expect(profileDerivations(COLUMN.map((level) => ({ ...level, electronDensityM3: null })))).toBeNull();
  });
});

/** A sampler stand-in: the real one decodes base64 frames, which this does not need. */
function samplerReturning(results: (altitudeKm: number) => IonosphereSampleResult): IonosphereSampler {
  return { sample: (input: { altitudeKm: number }) => results(input.altitudeKm) } as unknown as IonosphereSampler;
}

const okAt = (altitudeKm: number, electronDensityM3: number): IonosphereSampleResult => ({
  status: "ok",
  electronDensityM3,
  ionFractions: {},
  location: { latitudeDeg: 0, longitudeDeg: 0, altitudeKm },
  frames: { startValidAt: "2026-08-11T00:00:00Z", endValidAt: "2026-08-11T04:00:00Z", blend: 0.25 },
  method: "trilinear log-density plus linear temporal interpolation",
});

describe("sampling a whole column over one clicked point", () => {
  const altitudes = [90, 150, 300, 600];

  it("walks every published altitude and derives the operational numbers from the column", () => {
    const densities: Record<number, number> = { 90: 1e9, 150: 2e11, 300: 1.2e12, 600: 2e11 };
    const profile = sampleProfile(
      samplerReturning((altitudeKm) => okAt(altitudeKm, densities[altitudeKm]!)),
      altitudes,
      { latitudeDeg: 35, longitudeDeg: -75, time: new Date("2026-08-11T01:00:00Z") },
    );
    expect(profile.levels.map((level) => level.altitudeKm)).toEqual(altitudes);
    expect(profile.derivations!.hmF2Km).toBe(300);
    expect(profile.frames!.blend).toBe(0.25);
    expect(profile.unavailable).toBeNull();
  });

  /**
   * A hole stays a hole. The level is kept with a null so the profile can draw
   * the gap, rather than dropped — a column that silently shortened itself
   * would read as a thinner ionosphere instead of a less-known one.
   */
  it("keeps a level the model could not fill as a visible gap rather than dropping it", () => {
    const profile = sampleProfile(
      samplerReturning((altitudeKm) =>
        altitudeKm === 300
          ? { status: "missing", reason: "A contributing WAM-IPE source cell is missing." }
          : okAt(altitudeKm, 2e11)),
      altitudes,
      { latitudeDeg: 10, longitudeDeg: 20, time: new Date("2026-08-11T01:00:00Z") },
    );
    expect(profile.levels).toHaveLength(altitudes.length);
    expect(profile.levels.find((level) => level.altitudeKm === 300)!.electronDensityM3).toBeNull();
    // The column still has values, so it is not "unavailable" — it is partial.
    expect(profile.unavailable).toBeNull();
    expect(profile.derivations).not.toBeNull();
  });

  it("gives one reason for a column with nothing in it, not one per level", () => {
    const profile = sampleProfile(
      samplerReturning(() => ({
        status: "outside-time",
        reason: "Requested time is outside the published WAM-IPE sequence.",
      })),
      altitudes,
      { latitudeDeg: 10, longitudeDeg: 20, time: new Date("2020-01-01T00:00:00Z") },
    );
    expect(profile.unavailable).toBe("Requested time is outside the published WAM-IPE sequence.");
    expect(profile.derivations).toBeNull();
  });

  it("normalizes the clicked longitude the way the sampler reports it", () => {
    const profile = sampleProfile(
      samplerReturning((altitudeKm) => okAt(altitudeKm, 3e11)),
      altitudes,
      { latitudeDeg: 0, longitudeDeg: -75, time: new Date("2026-08-11T01:00:00Z") },
    );
    expect(profile.longitudeDeg).toBeCloseTo(285, 9);
  });
});

/**
 * The rule this whole file exists under: a model may never wear a
 * measurement's clothes. foF2 from an ionosonde is measured; foF2 from here is
 * not, and the note that says so is part of the product.
 */
describe("the evidence claim these numbers carry", () => {
  it("says the numbers are model-derived and that no instrument measured them", () => {
    const note = profileEvidenceNote();
    expect(note).toMatch(/WAM-IPE/);
    expect(note).toMatch(/not an ionosonde sounding/i);
    expect(note).toMatch(/No instrument measured/i);
  });
});
