/**
 * THE NUMBERS ON THE LAYER PAGES, CHECKED AGAINST THE ARITHMETIC THAT PRODUCES
 * THEM.
 *
 * Written 2026-09-04 after a correctness audit of src/layer-pages.ts found six
 * substantive errors that 2,168 passing tests had not touched, because every one
 * of those tests asked whether the markup rendered and none asked whether the
 * sentence was true. The worst of them — "thinning by five orders of magnitude"
 * against three published densities spanning 6.7 decades, printed two lines
 * below it in the same page — would have been caught by a single line of
 * arithmetic at any point in the three weeks it was live.
 *
 * So the rule for this file: an assertion earns its place only if the expected
 * value is COMPUTED, or read from the artifact or module the page is quoting.
 * `expect(html).toContain("22.0° → 14.0°")` on its own is a spelling test. The
 * same line is a correctness test when the string beside it came out of
 * `footprintAngularRadius()`, because then an edit that changes the geometry and
 * an edit that changes the sentence must agree or the suite goes red.
 *
 * Where a claim genuinely cannot be recomputed here — a published measurement, a
 * cited paper — it is NOT asserted, and the audit report says so rather than
 * this file pretending to a check it did not make.
 */

import { describe, expect, it } from "vitest";
import { layerPageView } from "../src/layer-pages";
import { EARTH_RADIUS_KM, footprintAngularRadius } from "../src/orbit";
import { drapAbsorptionDbAtFrequency } from "../src/drap";
import { RING_CURRENT_DRIFT_REPLAY, RING_CURRENT_FORMATION } from "../src/ring-current-illustration";
import dgcpm from "./data/plasmasphere-dgcpm-2026-08-08.json";

const EARTH_MU_KM3_S2 = 398_600.4418;
const degrees = (radians: number) => (radians * 180) / Math.PI;

/** "10⁻¹²" and friends. The pages print exponents as superscript glyphs. */
const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";
function exponent(glyphs: string): number {
  return Number(
    glyphs.replace(/⁻/g, "-").replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, (c) => String(SUPERSCRIPT.indexOf(c))),
  );
}

describe("thermosphere: the stated thinning is the thinning the page's own three values give", () => {
  const html = layerPageView("thermosphere");

  /** The three published WAM values the video caption marks on its curve. */
  const profile = html.match(
    /([\d.]+)×10(⁻[⁰¹²³⁴⁵⁶⁷⁸⁹]+) kg m⁻³ at 120 km, ([\d.]+)×10(⁻[⁰¹²³⁴⁵⁶⁷⁸⁹]+) at 420 km, ([\d.]+)×10(⁻[⁰¹²³⁴⁵⁶⁷⁸⁹]+) at 1,000 km/,
  );

  it("finds the three densities it is going to reason about", () => {
    expect(profile).not.toBeNull();
  });

  it("says the number of decades those densities actually span", () => {
    const [, lowMantissa, lowExp, , , highMantissa, highExp] = profile!;
    const at120 = Number(lowMantissa) * 10 ** exponent(lowExp!);
    const at1000 = Number(highMantissa) * 10 ** exponent(highExp!);
    const decades = Math.log10(at120 / at1000);

    // 1.67e-8 / 3.07e-15 = 5.4e6, which is 6.74 decades. src/thermosphere-volume.ts
    // reports the same field as falling "6.7 decades across that range".
    expect(decades).toBeGreaterThan(6.5);
    expect(decades).toBeLessThan(7);

    expect(html).toContain("nearly seven orders of magnitude");
    // The retracted claim, by name, so a revert is loud rather than quiet.
    expect(html).not.toContain("five orders of magnitude");
  });

  it("quotes a drag acceleration that its own density and ballistic coefficient give", () => {
    const [, , , mantissa420, exp420] = profile!;
    const densityAt420 = Number(mantissa420) * 10 ** exponent(exp420!);

    // a = ½ ρ v² / B, circular speed at the same 420 km the page names, and the
    // ballistic coefficient of 100 kg m⁻² it names beside it.
    const speedMs = Math.sqrt(EARTH_MU_KM3_S2 / (EARTH_RADIUS_KM + 420)) * 1000;
    const ballisticCoefficient = 100;
    const acceleration = (0.5 * densityAt420 * speedMs * speedMs) / ballisticCoefficient;

    expect((acceleration * 1e7).toFixed(1)).toBe("7.3");
    expect(html).toContain("7.3×10⁻⁷ m s⁻²");
    expect(html).toContain("ballistic coefficient 100 kg m⁻²");
  });

  it("does not present the published field's floor as the base of the thermosphere", () => {
    expect(html).toContain("The published field, not the atmosphere");
    expect(html).toContain("mesopause");
  });
});

describe("ionosphere: the frequency and range-error constants are the standard ones", () => {
  const html = layerPageView("ionosphere");

  it("quotes the GPS L1 range error one TECU actually produces", () => {
    // Δρ = 40.3 · TEC / f², TEC in electrons m⁻², f in Hz. One TECU is 1e16 m⁻².
    const l1Hz = 1_575.42e6;
    const metresPerTecu = (40.3 * 1e16) / (l1Hz * l1Hz);
    expect(Math.round(metresPerTecu * 100)).toBe(16);
    expect(html).toContain("16 cm");
  });

  it("quotes the plasma-frequency constant that turns a peak density into foF2", () => {
    // fp = 8.98 √Ne Hz with Ne in m⁻³, so in MHz the coefficient is 8.98e-6.
    const coefficientMhz = 8.98e-6;
    const nmF2 = 1e12; // m⁻³, an ordinary F2 peak
    expect(coefficientMhz * Math.sqrt(nmF2)).toBeCloseTo(8.98, 6);
    expect(html).toContain("8.98×10⁻⁶ √Nₑ");
  });

  it("says the 2,655 km top is where the model stops, not where the plasma does", () => {
    expect(html).toContain("model column stops rather than where the plasma does");
  });
});

describe("plasmasphere: the extent is the published grid's extent", () => {
  const html = layerPageView("plasmasphere");
  const lValues = dgcpm.grid.lValues as number[];

  it("declares the L range the artifact actually publishes", () => {
    // This read "L 2 – 6" while the page's own headline fact put the quiet
    // plasmapause at 7.2 Re — outside the range the page claimed for itself.
    expect(html).toContain(`L ${lValues[0]} – ${lValues.at(-1)}`);
  });

  it("puts the belt's inward reach on the constellation it actually reaches", () => {
    // Geostationary is L 6.6, inside the outer belt's own L 3–7 on the next page.
    // A slot that fills brings the belt toward the GNSS shells, not toward GEO.
    expect(html).toContain("GNSS shells near L 4.2");
    expect(html).not.toContain("reaches inward toward geostationary");
  });

  it("puts the quiet plasmapause inside the extent it declares", () => {
    const quiet = Number(html.match(/([\d.]+) → [\d.]+ Rᴇ/)![1]);
    expect(quiet).toBeGreaterThan(lValues[0]!);
    expect(quiet).toBeLessThan(lValues.at(-1)!);
  });
});

describe("plasmapause: 7.2 → 3.3 Rᴇ is what the published Volland–Stern arithmetic gives", () => {
  // The closed form pipeline/plasmasphere_dgcpm.py integrates against, with its
  // own constants: the dusk stagnation point L = (Φc / (2 A R_E))^(1/3), where
  // A = 7.05e-6 / (1 − 0.159 Kp + 0.0093 Kp²)³ V m⁻¹ (Maynard & Chen 1975) and
  // Φc = Ω μ₀ M / (4π R_E) is the corotation scale, about 91.8 kV.
  const EARTH_RADIUS_M = 6.378e6;
  const DIPOLE_MOMENT_A_M2 = 8.05e22;
  const VACUUM_PERMEABILITY = 4 * Math.PI * 1e-7;
  const EARTH_ANGULAR_RATE_RAD_S = (2 * Math.PI) / 86_400;

  const corotationScaleV =
    (EARTH_ANGULAR_RATE_RAD_S * VACUUM_PERMEABILITY * DIPOLE_MOMENT_A_M2) / (4 * Math.PI * EARTH_RADIUS_M);
  const amplitudeVPerM = (kp: number) => 7.05e-6 / (1 - 0.159 * kp + 0.0093 * kp * kp) ** 3;
  const stagnationL = (kp: number) =>
    (corotationScaleV / (2 * amplitudeVPerM(kp) * EARTH_RADIUS_M)) ** (1 / 3);

  it("reproduces the stagnation L the published frames carry", () => {
    // The transcription above is checked against the artifact rather than trusted:
    // every frame publishes both the Kp it was driven by and the stagnation L the
    // pipeline computed from it.
    for (const frame of dgcpm.frames as Array<{ kp: number; stagnationL: number }>) {
      expect(stagnationL(frame.kp)).toBeCloseTo(frame.stagnationL, 2);
    }
  });

  it("is the pair of numbers the page prints", () => {
    const html = layerPageView("plasmasphere");
    const quiet = stagnationL(2).toFixed(1);
    const stormy = stagnationL(8).toFixed(1);
    expect(html).toContain(`${quiet} → ${stormy} Rᴇ`);
    expect(html).toContain("as Kp goes from 2 to 8");
  });
});

describe("ring current: the drift replay's clock is the drift replay's clock", () => {
  const html = layerPageView("ring-current");
  const drift = RING_CURRENT_DRIFT_REPLAY.physicalSecondsPerDisplaySecond;
  const formation = RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;

  it("keeps the two rates apart, because they are two different animations", () => {
    expect(drift).not.toBe(formation);
    expect(html).toContain(`${drift}×`);
    expect(html).toContain(`${formation.toLocaleString("en-US")}×`);
    // The merged sentence this replaced: 400× is not an hour a second.
    expect(html).not.toContain(`${drift}×, one hour of drift per second`);
  });

  it("says how much drift a second of the drift replay is", () => {
    expect(Math.floor(drift / 60)).toBe(6);
    expect(drift % 60).toBe(40);
    expect(html).toContain("six minutes and forty seconds of drift in every second");
  });

  it("attaches 'an hour a second' to the rate that is one", () => {
    expect(formation / 3600).toBe(1);
    expect(html).toContain(`${formation.toLocaleString("en-US")}×, an hour a second`);
  });

  it("still describes the drift replay's speed-up to the right order", () => {
    // "two and a half orders of magnitude" is log10(400) = 2.60, not log10(3600).
    expect(Math.log10(drift)).toBeGreaterThan(2.5);
    expect(Math.log10(drift)).toBeLessThan(2.75);
    expect(html).toContain("two and a half orders of magnitude");
  });

  it("gets the adiabatic energisation from L 8 to L 4 right", () => {
    // μ = W/B conserved and B ∝ L⁻³, so W ∝ L⁻³.
    expect(10 * (8 / 4) ** 3).toBe(80);
    expect(html).toContain("10 keV → 80 keV");
    expect(html).toContain("energy goes as L⁻³");
  });
});

describe("magnetopause: the bow shock stands 13 Rᴇ from Earth, not 13 Rᴇ from the magnetopause", () => {
  const html = layerPageView("magnetopause");

  it("does not put the shock thirteen Earth radii beyond the boundary", () => {
    // The page's own methods row measures 13.25 Rᴇ for the shock against 10.25 Rᴇ
    // for the current layer on the same quiet frame — a gap of three, not thirteen.
    const shock = Number(html.match(/bow shock came out at ([\d.]+) Rᴇ/)![1]);
    const boundary = Number(html.match(/modelled current layer at ([\d.]+) Rᴇ/)![1]);
    expect(shock - boundary).toBeLessThan(4);
    expect(html).not.toContain("stands about 13 Earth radii sunward of it");
  });

  it("declares the same compressed standoff in the extent and in the fact", () => {
    const [, extentLow, extentHigh] = html.match(/nose ([\d.]+) – ([\d.]+) Rᴇ/)!;
    const [, factQuiet, factStormy] = html.match(/([\d.]+) → ([\d.]+) Rᴇ<\/strong>/)!;
    expect(extentLow).toBe(factStormy);
    expect(extentHigh).toBe(factQuiet);
  });

  it("quotes an agreement percentage that is the difference it names", () => {
    const shue = Number(html.match(/against Shue's ([\d.]+) Rᴇ/)![1]);
    const model = Number(html.match(/modelled current layer at ([\d.]+) Rᴇ/)![1]);
    const gap = Number(html.match(/a difference of ([\d.]+) Rᴇ/)![1]);
    expect(gap).toBeCloseTo(shue - model, 2);
    expect(((gap / shue) * 100).toFixed(1)).toBe("3.4");
    expect(html).toContain("or 3.4%");
  });
});

describe("solar wind: the dynamic-pressure constant is the proton mass in those units", () => {
  it("is 1.6726×10⁻⁶ nPa per cm⁻³ per (km s⁻¹)²", () => {
    const protonMassKg = 1.67262192e-27;
    // n cm⁻³ → m⁻³ is ×1e6; V km s⁻¹ → m s⁻¹ squared is ×1e6; Pa → nPa is ×1e9.
    const constantNpa = protonMassKg * 1e6 * 1e6 * 1e9;
    expect(constantNpa.toExponential(4)).toBe("1.6726e-6");
    expect(layerPageView("solar-wind")).toContain("1.6726×10⁻⁶ n V²");
  });
});

describe("D region: the absorption arithmetic is D-RAP's arithmetic", () => {
  const html = layerPageView("d-region");

  it("gets the 5 MHz against 20 MHz ratio from the published scaling", () => {
    const haf = 7.5; // any HAF: the ratio is scale-free at the ^1.5 exponent
    const ratio = drapAbsorptionDbAtFrequency(haf, 5)! / drapAbsorptionDbAtFrequency(haf, 20)!;
    expect(ratio).toBeCloseTo(8, 10);
    expect(html).toContain("×8");
    expect(html).toContain("more absorption at 5 MHz than at 20 MHz");
  });

  it("calls HAF what NOAA and the rest of this site call it", () => {
    expect(html).not.toContain("maximum affected frequency");
    expect(html).toContain("the highest affected frequency is the one number D-RAP publishes");
  });

  it("does not claim a quiet band is untouched, only that it is under the threshold", () => {
    // The index is defined at 1 dB, so a HAF below 3 MHz means under a decibel
    // across the band — not nothing.
    expect(drapAbsorptionDbAtFrequency(2.9, 3)!).toBeLessThan(1);
    expect(html).not.toContain("nothing in the band is touched at all");
    expect(html).toContain("loses even the one decibel the index is defined at");
  });
});

describe("ground track and footprint: the geometry the page quotes is the geometry it draws with", () => {
  const html = layerPageView("ground-track-footprint");

  it("prints the half-angles footprintAngularRadius() returns at 500 km", () => {
    const wide = footprintAngularRadius(500, 0);
    const narrow = footprintAngularRadius(500, 10);
    expect(degrees(wide).toFixed(1)).toBe("22.0");
    expect(degrees(narrow).toFixed(1)).toBe("14.0");
    expect(html).toContain("22.0° → 14.0°");
  });

  it("prints the area those two circles actually leave", () => {
    // Spherical cap area goes as (1 − cos λ).
    const survives =
      (1 - Math.cos(footprintAngularRadius(500, 10))) / (1 - Math.cos(footprintAngularRadius(500, 0)));
    expect(Math.round(survives * 100)).toBe(41);
    expect(html).toContain("about 41% of the area survives");
  });

  it("does not tell a reader a retrograde track reaches its own inclination", () => {
    // The site draws sun-synchronous spacecraft; a track at 98.2° tops out at 81.8°.
    expect(180 - 98.2).toBeCloseTo(81.8, 6);
    expect(html).toContain("98.2° tops out at 81.8°");
    expect(html).not.toContain("and nothing else sets it");
    expect(html).not.toContain("simply the inclination");
  });
});

describe("radiation belts: the ranges, and the dipole relation the video is drawn from", () => {
  const html = layerPageView("radiation-belts");

  it("keeps the inner and outer belts as two ranges, never one", () => {
    // The failure mode this whole audit was commissioned over: one belt's range
    // printed as though it covered both.
    expect(html).toContain("inner L 1.2 – 2 · outer L 3 – 7");
    expect(html).toContain("an inner belt of protons at L 1.2 to 2");
    expect(html).toContain("an outer belt of electrons at L 3 to 7");
  });

  it("puts geostationary inside the outer belt, which is why the slot page may not aim there", () => {
    const [, innerLow, innerHigh] = html.match(/inner L ([\d.]+) – ([\d.]+)/)!;
    const [, outerLow, outerHigh] = html.match(/outer L ([\d.]+) – ([\d.]+)/)!;
    const geostationaryL = 42_164.17 / EARTH_RADIUS_KM;
    expect(geostationaryL).toBeGreaterThan(Number(outerLow));
    expect(geostationaryL).toBeLessThan(Number(outerHigh));
    // And the slot really does sit between the two belts.
    expect(Number(innerHigh)).toBeLessThan(Number(outerLow));
    expect(Number(innerLow)).toBeLessThan(Number(innerHigh));
  });

  it("places the CIRBE belt in the slot it says it is in", () => {
    const [, newLow, newHigh] = html.match(/L ([\d.]+) – ([\d.]+)<\/strong><span>where CIRBE/)!;
    const [, , innerHigh] = html.match(/inner L ([\d.]+) – ([\d.]+)/)!;
    const [, outerLow] = html.match(/outer L ([\d.]+) – ([\d.]+)/)!;
    expect(Number(newLow)).toBeGreaterThanOrEqual(Number(innerHigh));
    expect(Number(newHigh)).toBeLessThanOrEqual(Number(outerLow) + 0.5);
  });
});
