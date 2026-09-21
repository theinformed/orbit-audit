/**
 * Numeric proofs for the amber species shower and the field-guided coupling —
 * the numbers that must hold before any screenshot of them is trusted.
 *
 *   - The species mix follows from ONE measured number (proton density) plus
 *     two stated statements (assumed alpha ratio, quasi-neutrality), and the
 *     drawn PREFIX of the particle buffer keeps that mix at any density,
 *     because the draw range scales with density.
 *   - Guided particles lie ON the traced field-line polylines — distance
 *     zero by construction, measured here anyway — and cusp journeys end at
 *     the line's own footpoint in the cusp latitude band.
 *   - The coupling is additive: magnetosphere layer off means no guided set
 *     and an unchanged deflecting cloud. The BATS-R-US plane tracers draw
 *     only for the MHD cut option, never as the layer's default face.
 */
import { describe, expect, it } from "vitest";

import {
  ALPHA_TO_PROTON_NUMBER_RATIO_ASSUMED,
  LOBE_INFLOW_LEAD_RE,
  SOLAR_WIND_ALPHA_LUMINANCE_GAIN,
  SOLAR_WIND_SPECIES_RELATIVE_LUMINANCE,
  solarWindIntensityEncoding,
  buildGuidancePaths,
  buildTailReturnPaths,
  createIllustrativeUpstreamFlowGeometry,
  createSolarWindVisual,
  sampleGuidedJourney,
  SOLAR_WIND_SPECIES_PRESENTATION,
  solarWindSpeciesForIndex,
  SOLAR_WIND_FACE_FADE,
  SOLAR_WIND_GUIDANCE_CUE,
  SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT,
  solarWindSpeciesBulkEnergyEv,
  solarWindSpeciesKey,
  solarWindSpeciesMix,
  trimToTailX,
} from "../src/solar-input-visuals";
import type { FieldGuidanceLine, GuidancePath } from "../src/solar-input-visuals";
import { traceMagnetosphereFieldLines } from "../src/magnetosphere-field-lines";
import type { FieldLineDrivers } from "../src/magnetosphere-field-lines";

const QUIET: FieldLineDrivers = { dynamicPressureNpa: 1.0, bzGsmNt: 2.0, dipoleTiltRad: 0.15 };

/** A driven tail: strongly southward IMF at a fast, dense wind. */
const DRIVEN: FieldLineDrivers = { dynamicPressureNpa: 4.8, bzGsmNt: -12, dipoleTiltRad: -0.155 };

describe("the species mix", () => {
  it("derives every fraction from the stated alpha ratio and quasi-neutrality", () => {
    const mix = solarWindSpeciesMix();
    expect(mix.assumedAlphaRatio).toBe(ALPHA_TO_PROTON_NUMBER_RATIO_ASSUMED);
    // Per unit np: protons 1, alphas 0.04, electrons 1 + 2*0.04 = 1.08.
    const total = 1 + 0.04 + 1.08;
    expect(mix.protonFraction).toBeCloseTo(1 / total, 9);
    expect(mix.alphaFraction).toBeCloseTo(0.04 / total, 9);
    expect(mix.electronFraction).toBeCloseTo(1.08 / total, 9);
    expect(mix.protonFraction + mix.alphaFraction + mix.electronFraction).toBeCloseTo(1, 12);
    // Sanity against the physics: protons ~96% of IONS by number.
    expect(mix.protonFraction / (mix.protonFraction + mix.alphaFraction)).toBeCloseTo(0.9615, 3);
  });

  it("keeps every drawn prefix on the mix, so density changes never skew the species", () => {
    const mix = solarWindSpeciesMix();
    for (const prefix of [150, 600, 2200]) {
      const counts = { proton: 0, alpha: 0, electron: 0 };
      for (let index = 0; index < prefix; index += 1) counts[solarWindSpeciesForIndex(index, mix)] += 1;
      expect(counts.proton / prefix).toBeCloseTo(mix.protonFraction, 1.7);
      expect(counts.electron / prefix).toBeCloseTo(mix.electronFraction, 1.7);
      expect(Math.abs(counts.alpha / prefix - mix.alphaFraction)).toBeLessThan(0.012);
      // Alphas are rare but must actually appear in a visible population.
      if (prefix >= 600) expect(counts.alpha).toBeGreaterThan(0);
    }
  });

  it("builds the cloud with a species per particle and the counts on the mix", () => {
    const geometry = createIllustrativeUpstreamFlowGeometry({ particleCount: 2200, seed: 20260809 });
    const species = geometry.getAttribute("species");
    expect(species.count).toBe(2200);
    const counts = geometry.userData.speciesCounts as { proton: number; alpha: number; electron: number };
    const mix = solarWindSpeciesMix();
    expect(counts.proton + counts.alpha + counts.electron).toBe(2200);
    expect(counts.proton / 2200).toBeCloseTo(mix.protonFraction, 1.7);
    expect(counts.electron / 2200).toBeCloseTo(mix.electronFraction, 1.7);
    expect(String(geometry.userData.speciesAssignment)).toContain("assumed");
    geometry.dispose();
  });

  /**
   * ## THE LEGEND IS A LIST NOW, AND THE ENERGIES ARE ARITHMETIC
   *
   * The proportion bar was removed on 2026-08-27 after failing twice at its one
   * unique job — 2% of a 290 px bar is 5.5 px, and the square-root easing that
   * fixed the pixels was a declared distortion Sean still read as *"a small
   * sliver to the right"*. What replaced it is his own proposal: a list, with
   * the energy each species carries at the measured wind speed.
   *
   * That energy has to be REAL, because it is now the load-bearing teaching
   * number in this legend, so it is pinned against the textbook value here.
   */
  it("derives each species' bulk energy from the measured speed and nothing else", () => {
    const energies = solarWindSpeciesBulkEnergyEv(259)!;
    // E = 1/2 m v^2 at V 259 km/s. The proton line is the anchor.
    expect(energies.proton).toBeCloseTo(350, 0);
    // The alpha is 4 proton masses on the same speed — the mass ratio the
    // glyph stopped drawing as an area, stated as a number instead.
    expect(energies.alpha / energies.proton).toBeCloseTo(3.97, 2);
    // The electron is 1/1836 of a proton, and its bulk energy says so.
    expect(energies.proton / energies.electron).toBeCloseTo(1836, -1);
    expect(energies.electron).toBeCloseTo(0.19, 2);
    // THE SANITY ANCHOR: at the textbook 440 km/s the proton line reads 1 keV.
    expect(solarWindSpeciesBulkEnergyEv(440)!.proton).toBeCloseTo(1010, -1);
    // It scales as v squared, which is the whole of the claim.
    expect(solarWindSpeciesBulkEnergyEv(518)!.proton / energies.proton).toBeCloseTo(4, 6);
    // No speed, no energy. A legend that invented one would be inventing a
    // measurement.
    expect(solarWindSpeciesBulkEnergyEv(null)).toBeNull();
    expect(solarWindSpeciesBulkEnergyEv(0)).toBeNull();
  });

  /**
   * ## The legend says three species, and still says 2% is 2%
   *
   * Sean, on the shipped legend: *"See how it basically looks like there are
   * only 2 constituents? Perhaps we can have it be some sort of logarithmic
   * scale?"* He was right about the symptom and the instinct pointed at the
   * wrong element. The bar is 290 px, He²⁺ is 1.9% of the plasma, and 1.9% of
   * 290 px is 5.5 px hard against the bar's own border — invisible. But the
   * bar's only meaning is PROPORTION: a log axis would draw 2% at roughly a
   * quarter of the width and three equal segments would draw it at a third,
   * and either one makes the graphic lie about the single thing it exists to
   * say.
   *
   * So the bar keeps proportion and the row beneath it became the key. What is
   * pinned here is both halves of that: the key names all three species with
   * the colours the shower draws them in, AND the bar's alpha segment is still
   * the true 1.9% — no floor, no exaggeration, nothing rescaled.
   */
  it("names all three species in the key, in the colours the shower draws", () => {
    const key = solarWindSpeciesKey();
    expect(key.map((cell) => cell.species)).toEqual(["electron", "proton", "alpha"]);
    for (const cell of key) {
      const presentation = SOLAR_WIND_SPECIES_PRESENTATION[cell.species];
      // The swatch is the renderer's own colour, never a second copy.
      expect(cell.swatch).toBe(presentation.colorHex);
      expect(cell.text.startsWith(presentation.symbol)).toBe(true);
    }
    // The rarest species is on the row at the same rank as the other two.
    expect(key[2]!.text).toContain("He²⁺");
  });

  it("prints the plasma's own numbers, and says which one is not measured", () => {
    const mix = solarWindSpeciesMix();
    const key = solarWindSpeciesKey(mix);
    expect(key[0]!.fraction).toBe(mix.electronFraction);
    expect(key[1]!.fraction).toBe(mix.protonFraction);
    expect(key[2]!.fraction).toBe(mix.alphaFraction);
    expect(key.map((cell) => cell.text)).toEqual(["e⁻ 51%", "H⁺ 47%", "He²⁺ 2% assumed"]);
    // The alpha share is the assumption; the other two follow from a measured
    // density, and neither may be labelled as though it were guessed.
    expect(key[0]!.text).not.toContain("assumed");
    expect(key[1]!.text).not.toContain("assumed");
  });

  /**
   * ## Twenty-one alphas, found without drawing twenty-one more
   *
   * Sean, on the shower: *"you don't really get to see the species overall
   * because e- and H+ dominate... can we exaggerate so that we see all the
   * particles a little more?"*
   *
   * THE NEGATIVE CONTROL FOR EVERYTHING THAT ANSWERED HIM. The answer was to
   * draw the alphas larger and hold them at full brightness for more of their
   * ride — display choices, both of which leave the drawn population alone. If
   * a later change reaches for the other lever and over-samples the species so
   * that it is easier to see, the drawn mix stops matching the mix the legend
   * prints beside it, and this fails. The number that must not move is the
   * ALPHA SHARE OF WHAT IS DRAWN, at every density, because the draw range is
   * a prefix that scales with the measured density.
   */
  it("finds the alphas WITHOUT drawing more of them, at every measured density", () => {
    const mix = solarWindSpeciesMix();
    // globe.ts builds the shower with 2,200 particles; the draw range is the
    // prefix `activeFraction` of them.
    for (const [speed, density] of [[271, 1.9], [400, 5], [350, 0.5], [600, 20]] as const) {
      const encoding = solarWindIntensityEncoding(speed, density);
      const drawn = Math.max(1, Math.round(2200 * encoding.activeFraction));
      const counts = { proton: 0, alpha: 0, electron: 0 };
      for (let index = 0; index < drawn; index += 1) counts[solarWindSpeciesForIndex(index, mix)] += 1;
      // Within a third of a percentage point of the plasma's own share — the
      // low-discrepancy sequence's own accuracy, and nothing more.
      expect(Math.abs(counts.alpha / drawn - mix.alphaFraction)).toBeLessThan(0.003);
      // ...and the quasi-neutral pair keeps its ratio too, so nothing was
      // taken from the electrons to pay for a more visible alpha.
      expect(counts.electron / counts.proton).toBeCloseTo(mix.electronFraction / mix.protonFraction, 1);
    }
    // At the wind blowing when this was written: 1,142 drawn, 21 of them alphas.
    const today = Math.round(2200 * solarWindIntensityEncoding(271, 1.9).activeFraction);
    let alphasToday = 0;
    for (let index = 0; index < today; index += 1) {
      if (solarWindSpeciesForIndex(index, mix) === "alpha") alphasToday += 1;
    }
    expect(today).toBe(1142);
    expect(alphasToday).toBe(21);
  });

  it("orders the glyphs by mass without pretending the area is the ratio, and divides the palette back out", () => {
    const { proton, alpha, electron } = SOLAR_WIND_SPECIES_PRESENTATION;
    // ORDER, NOT RATIO. The alpha drew at exactly four times the proton's AREA
    // — the literal mass ratio — for one day, and Sean read the result as a
    // rendering fault: "I think the blue dots look weird." He was right. An
    // area ratio is not decodable off a three-pixel glyph, and four times the
    // area on a ceiling-pinned brightness put ~3x a proton's light into a
    // species that is 2% of the plasma. The mass ratio moved to the legend as
    // an ENERGY, and the size channel went back to being an ordering.
    //
    // What is pinned here is the ordering and the bounds, not one number: the
    // alpha stays visibly the big one and stops being a blob.
    expect(alpha.pointScale).toBeGreaterThan(proton.pointScale);
    const alphaArea = (alpha.pointScale / proton.pointScale) ** 2;
    expect(alphaArea).toBeGreaterThan(1.6);
    expect(alphaArea).toBeLessThan(2.6);
    // The electron is deliberately OFF any area-by-mass rule: 1/1836 of a
    // proton would draw at 0.023, which is nothing at all. It is smaller than
    // both ions because it is lighter than both, and no smaller than that —
    // it was 0.7, and at 0.7 its halved area cancelled the very lightness
    // advantage that is its only separation from the amber. Sean: "it still
    // looks like there are particles missing."
    expect(electron.pointScale).toBeLessThan(proton.pointScale);
    expect(electron.pointScale).toBeGreaterThan(0.8);

    // The arithmetic that says the rare species was never on equal terms.
    // These are Rec. 709 relative luminances of the three settled hex codes.
    // Since 2026-08-27 the palette is a GOLD FAMILY carrying one cool trace
    // species: the amber H+ anchors it, the pale cream e- is the brighter of
    // the two abundant ones, and the periwinkle He2+ is 1.63x darker than the
    // anchor, so at an equal drawn alpha on an additive sky it emits under two
    // thirds of the anchor's light.
    const { proton: yProton, alpha: yAlpha, electron: yElectron } = SOLAR_WIND_SPECIES_RELATIVE_LUMINANCE;
    expect(yProton).toBeCloseTo(0.4662, 3);
    expect(yElectron).toBeCloseTo(0.7969, 3);
    expect(yAlpha).toBeCloseTo(0.2864, 3);
    expect(yAlpha / yProton).toBeLessThan(0.7);
    // THE CEILING HAS TO STAY OFF THE QUIET WIND. This is the defect that made
    // the alphas read as artifacts: at gain 2.57 the shader's min(1.0, ...)
    // clipped 0.52 x 2.57 = 1.33 back to 1.0, so every alpha sat PINNED at
    // maximum brightness while its amber neighbours sat at 0.52, and none of
    // them modulated with the measured conditions. The correction is only
    // honest if it actually fits, so assert that it fits at the quiet wind's
    // own drawn opacity — this is the guard on the colour choice itself.
    // Sean's own conditions on the day he called the alphas weird: V 259 km/s,
    // n 1.9 cm-3, which the encoding draws at opacity 0.482.
    const quietOpacity = solarWindIntensityEncoding(259, 1.9).opacity;
    expect(quietOpacity).toBeCloseTo(0.482, 3);
    expect(quietOpacity * SOLAR_WIND_ALPHA_LUMINANCE_GAIN).toBeLessThan(1);
    // ...and the defect it replaced, spelled out: the old #6d5cff needed 2.57,
    // which clipped at this very wind.
    expect(quietOpacity * 2.57).toBeGreaterThan(1);
    // THE TARGET IS THE ANCHOR, NOT THE BRIGHTEST. It was the brightest while
    // the two abundant species were within 5% of each other, and it cannot be
    // now: aiming the correction at the cream electron demands a gain of 2.78
    // rather than 1.63, and additive blending CLIPS — the extra gain washes the
    // periwinkle out toward white until it scores 14.7 against the amber where
    // the legibility floor is 25. Anchoring it at the proton keeps that at 28.2.
    // This is the negative control for the choice, so it is asserted rather
    // than explained: the correction must NOT be the brightest-species ratio.
    expect(SOLAR_WIND_ALPHA_LUMINANCE_GAIN).toBeCloseTo(yProton / yAlpha, 9);
    expect(Math.max(yProton, yElectron) / yAlpha).toBeGreaterThan(SOLAR_WIND_ALPHA_LUMINANCE_GAIN * 1.4);
    expect(SOLAR_WIND_ALPHA_LUMINANCE_GAIN).toBeLessThan(1.9);
    expect(SOLAR_WIND_ALPHA_LUMINANCE_GAIN).toBeGreaterThan(1.4);
    // The electron is left alone: being BRIGHTER than the others has never
    // been the failure mode, and dividing it down would dim 51% of the shower.
    expect(yElectron).toBeGreaterThan(yProton);

    const visual = createSolarWindVisual({ particleCount: 64, seed: 7 });
    const shaders = [visual.points, visual.trails, visual.guidedPoints, visual.guidedTrails]
      .map((object) => object.material as unknown as {
        uniforms: Record<string, { value: unknown } | undefined>;
        fragmentShader: string;
        vertexShader: string;
      });
    for (const shader of shaders) {
      expect(shader.uniforms.alphaLuminanceGain?.value).toBe(SOLAR_WIND_ALPHA_LUMINANCE_GAIN);
      // Applied to the ALPHA branch only — `mix(1.0, gain, isAlpha)` is 1.0 for
      // every other species — and clamped, so nothing can be driven past full
      // opacity and the conditions uniform still decides how bright the whole
      // shower is. That clamp binds above about 55% of the drive range, which
      // is the stated cost of the ceiling.
      expect(shader.fragmentShader).toContain("min(1.0, opacity * mix(1.0, alphaLuminanceGain, isAlpha))");
      expect(shader.vertexShader).toContain("isAlpha = species > 0.5 && species < 1.5 ? 1.0 : 0.0;");
    }
    visual.dispose();
  });

  /**
   * ## NOTHING BENDS FOR A REASON THE READER CANNOT SEE
   *
   * The wind now shows its whole repertoire whichever layers are on (Sean,
   * 2026-08-27). The cost of that is a stream hooking toward the poles with
   * the field that bends it switched off — which reads as a rendering fault.
   * So with the magnetosphere layer off the wind draws a cue of the polylines
   * its OWN guided particles are riding, and the two things that must hold are
   * that the cue invents no geometry, and that the traced/schematic split is
   * inked rather than asserted.
   */
  /**
   * How far a point is from the nearest drawn guidance polyline, in Earth
   * radii. Point-to-SEGMENT, not point-to-vertex: see the caller.
   */
  function distanceToNearestGuidancePath(
    paths: readonly { pointsGsmRe: readonly { x: number; y: number; z: number }[] }[],
    at: { x: number; y: number; z: number },
  ): number {
    let best = Number.POSITIVE_INFINITY;
    for (const path of paths) {
      for (let index = 1; index < path.pointsGsmRe.length; index += 1) {
        const from = path.pointsGsmRe[index - 1]!;
        const to = path.pointsGsmRe[index]!;
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const dz = to.z - from.z;
        const lengthSquared = dx * dx + dy * dy + dz * dz;
        const t = lengthSquared > 0
          ? Math.min(1, Math.max(0, ((at.x - from.x) * dx + (at.y - from.y) * dy + (at.z - from.z) * dz) / lengthSquared))
          : 0;
        best = Math.min(best, Math.hypot(
          at.x - (from.x + dx * t),
          at.y - (from.y + dy * t),
          at.z - (from.z + dz * t),
        ));
      }
    }
    return best;
  }

  it("draws a cue for the lines the guided particles ride, only while nothing else draws them", () => {
    const visual = createSolarWindVisual({ particleCount: 256, seed: 3 });
    visual.setConditions(420, 6);
    visual.setFieldGuidance(traceMagnetosphereFieldLines(QUIET)!.lines);
    expect(visual.guidancePaths.length).toBeGreaterThan(0);
    const { traced, schematic } = visual.guidanceCue;
    expect(traced).not.toBeNull();

    // NO NEW GEOMETRY: every cue vertex lies ON a guidance path.
    //
    // Not "is one of its listed vertices": the dashed half cuts the cycle
    // wherever it falls, which is usually inside a tessellation segment. The
    // polyline between two consecutive vertices IS a straight line, so a point
    // interpolated along it is a point of the drawn path and invents nothing.
    // A vertex the cue made up would be off the polyline and this catches it.
    for (const object of [traced, schematic]) {
      if (!object) continue;
      const position = object.geometry.getAttribute("position");
      expect(position.count).toBeGreaterThan(0);
      for (let index = 0; index < Math.min(position.count, 240); index += 1) {
        const distance = distanceToNearestGuidancePath(visual.guidancePaths, {
          x: position.getX(index),
          y: position.getY(index),
          z: position.getZ(index),
        });
        // 1e-4 Earth radii, which is 640 m: the same slack the vertex-key
        // comparison this replaced had, and comfortably above the float32
        // resolution the position buffer stores these in.
        expect(distance, `cue vertex ${index} is ${distance} off every guidance path`).toBeLessThan(1e-4);
      }
    }
    // The schematic stretch is drawn dimmer AND broken, so "nobody measures
    // these trajectories" is a property of the picture and not only of prose.
    expect(SOLAR_WIND_GUIDANCE_CUE.schematicOpacity).toBeLessThan(SOLAR_WIND_GUIDANCE_CUE.tracedOpacity);
    expect(SOLAR_WIND_GUIDANCE_CUE.schematicDashOnRe).toBeGreaterThan(0);
    expect(SOLAR_WIND_GUIDANCE_CUE.schematicDashOffRe).toBeGreaterThan(0);

    // The TRACED half is shown while the wind is coupled and nothing else is
    // drawing those same lines...
    visual.setCouplingActive(true);
    visual.setFieldLinesDrawnElsewhere(false);
    expect(visual.guidanceCueVisible).toBe(true);
    // ...and off the moment the magnetosphere layer draws its own.
    visual.setFieldLinesDrawnElsewhere(true);
    expect(visual.guidanceCueVisible).toBe(false);
    // ...and off when there is no coupled population to explain.
    visual.setFieldLinesDrawnElsewhere(false);
    visual.setCouplingActive(false);
    expect(visual.guidanceCueVisible).toBe(false);

    visual.dispose();
  });

  /**
   * ## THE SCHEMATIC HALF IS NOT THE TRACED HALF, AND MUST NOT COME AND GO
   * ##  WITH IT
   *
   * The traced half comes off when the magnetosphere layer draws those same
   * lines, and that is right — two drawings of one set of lines at two weights
   * is worse than either. The schematic half was suppressed by the same rule,
   * and that was wrong, because NOTHING else on this page draws the Dungey
   * legs: the turn at the neutral line, the earthward injection, the trapped
   * bounce-and-drift wound round the Earth, and the two ways a trapped
   * particle leaves. Suppressing it took the drawn path out from under exactly
   * the part of the journey nobody else draws, and left the tracers on that
   * leg moving through apparently empty space.
   *
   * Sean, on the shipped build with the magnetosphere layer on, 2026-08-27:
   * *"I don't see anything trapped. I don't see anything that really shows
   * particles are bound for the radiation belts or the ring current."*
   *
   * Measured at the time, 1440x900 on an RTX 4080: with the dotted path
   * suppressed, the whole trapped story on screen was 82 pixels — the four
   * tracers lit inside the ring current at that drive, and nothing else. With
   * it drawn, 3,717.
   *
   * This needs guidance that HAS schematic legs, so it builds the tail-return
   * paths rather than the bare traced set the test above uses.
   */
  it("keeps the dotted schematic path drawn even when the magnetosphere layer draws its own lines", () => {
    const visual = createSolarWindVisual({ particleCount: 256, seed: 3 });
    visual.setConditions(420, 6);
    visual.setFieldGuidance(traceMagnetosphereFieldLines(DRIVEN)!.lines, {
      tailReturn: {
        dipoleTiltRad: DRIVEN.dipoleTiltRad,
        innerEdgeRe: 8,
        auroraBranch: true,
        magnetopause: { subsolarStandoffRe: 8.6, flaringAlpha: 0.62 },
      },
    });
    const { schematic } = visual.guidanceCue;
    // There ARE schematic legs to draw, or this test is vacuous.
    expect(schematic).not.toBeNull();
    expect(schematic!.geometry.getAttribute("position").count).toBeGreaterThan(0);

    visual.setCouplingActive(true);
    visual.setFieldLinesDrawnElsewhere(false);
    expect(visual.guidanceCueSchematicVisible).toBe(true);
    expect(schematic!.material.opacity).toBeCloseTo(SOLAR_WIND_GUIDANCE_CUE.schematicOpacity, 6);

    // ...and it STAYS on when the magnetosphere layer draws its own lines,
    // weighted for the curtain it now has to be seen through.
    visual.setFieldLinesDrawnElsewhere(true);
    expect(visual.guidanceCueSchematicVisible).toBe(true);
    expect(schematic!.material.opacity).toBeCloseTo(SOLAR_WIND_GUIDANCE_CUE.schematicOpacityOverField, 6);
    // The two halves are never on screen together, which is what lets the
    // heavier weight be heavier than the traced cue's without the ink between
    // traced and schematic ever being ambiguous to a reader.
    expect(visual.guidanceCueVisible).toBe(false);
    // ...and it still goes when there is no coupled population to explain.
    visual.setCouplingActive(false);
    expect(visual.guidanceCueSchematicVisible).toBe(false);
    visual.dispose();
  });

  /**
   * ## THE BROKEN LINE HAS TO READ AS ONE PATH, NOT AS DEBRIS
   *
   * The schematic half used to be dotted by emitting every third
   * vertex-to-vertex segment. The schematic legs are tessellated from 0.023 to
   * 2.04 Earth radii per segment, so that produced marks of wildly different
   * lengths separated by gaps several times longer than themselves — and Sean,
   * on the deployed site: *"On the right side there are dashed lines and they
   * shouldn't be there. Seems to be some artifact your agents left behind."*
   *
   * What makes a mark read as an object rather than as part of a line is a gap
   * much longer than the mark. So the guard is on the RHYTHM, in the physical
   * units the dash is now defined in: no mark longer than the declared ink, no
   * gap longer than the declared gap, and never a mark with much more space
   * around it than length. It is a regression test for a perceptual defect,
   * pinned to the geometry that caused it.
   */
  it("draws the schematic half at one rhythm, so no mark can read as debris", () => {
    const visual = createSolarWindVisual({ particleCount: 256, seed: 3 });
    visual.setConditions(420, 6);
    visual.setFieldGuidance(traceMagnetosphereFieldLines(DRIVEN)!.lines, {
      tailReturn: {
        dipoleTiltRad: DRIVEN.dipoleTiltRad,
        innerEdgeRe: 8,
        auroraBranch: true,
        magnetopause: { subsolarStandoffRe: 8.6, flaringAlpha: 0.62 },
      },
    });
    const { schematic } = visual.guidanceCue;
    expect(schematic).not.toBeNull();
    const position = schematic!.geometry.getAttribute("position");
    expect(position.count).toBeGreaterThan(0);

    const onRe = SOLAR_WIND_GUIDANCE_CUE.schematicDashOnRe;
    const offRe = SOLAR_WIND_GUIDANCE_CUE.schematicDashOffRe;
    // Float32 slack only — the position buffer stores these as float32, whose
    // resolution at 20 Earth radii is about 2e-6. A mark is allowed to be
    // SHORTER than the ink (a leg can end mid-dash); never longer.
    const slack = 1e-4;
    let inkRe = 0;
    let pathRe = 0;
    let longestMarkRe = 0;
    let longestGapRe = 0;
    let loneMarks = 0;
    const markAt = (segment: number) => {
      const a = segment * 2;
      return {
        from: { x: position.getX(a), y: position.getY(a), z: position.getZ(a) },
        to: { x: position.getX(a + 1), y: position.getY(a + 1), z: position.getZ(a + 1) },
      };
    };
    const span = (u: { x: number; y: number; z: number }, v: { x: number; y: number; z: number }) =>
      Math.hypot(v.x - u.x, v.y - u.y, v.z - u.z);
    // A single dash that runs across a bend in the polyline is emitted as
    // several abutting pieces, because a dash has to follow the path it lies
    // on. Merge the pieces back into the marks a reader actually sees before
    // measuring them: touching pieces are one mark.
    const pieces = position.count / 2;
    const runs: { fromPiece: number; toPiece: number; lengthRe: number }[] = [];
    for (let piece = 0; piece < pieces; piece += 1) {
      const mark = markAt(piece);
      const lengthRe = span(mark.from, mark.to);
      const previous = runs[runs.length - 1];
      const touching = previous !== undefined
        && span(markAt(previous.toPiece).to, mark.from) < slack;
      if (touching) {
        previous.toPiece = piece;
        previous.lengthRe += lengthRe;
      } else {
        runs.push({ fromPiece: piece, toPiece: piece, lengthRe });
      }
    }
    for (const run of runs) {
      inkRe += run.lengthRe;
      longestMarkRe = Math.max(longestMarkRe, run.lengthRe);
    }
    for (let index = 1; index < runs.length; index += 1) {
      const previous = runs[index - 1]!;
      const run = runs[index]!;
      const gap = span(markAt(previous.toPiece).to, markAt(run.fromPiece).from);
      // A jump from the end of one PATH to the start of the next is not a gap
      // in a dash; only gaps inside the declared cycle are the subject here.
      if (gap > onRe + offRe) continue;
      longestGapRe = Math.max(longestGapRe, gap);
      const after = index + 1 < runs.length
        ? span(markAt(run.toPiece).to, markAt(runs[index + 1]!.fromPiece).from)
        : 0;
      // Only a mark isolated INSIDE a path counts. The last mark on a leg has
      // empty space after it because the leg ended, which is the path ending
      // rather than a mark adrift, so a jump wider than the cycle is not a
      // gap for this purpose either side.
      const isolated = gap > 2 * run.lengthRe
        && after > 2 * run.lengthRe
        && after <= onRe + offRe;
      if (run.lengthRe > 0 && isolated) loneMarks += 1;
    }
    for (const path of visual.guidancePaths) {
      const split = path.schematicFromIndex;
      if (split === null) continue;
      for (let index = split + 1; index < path.pointsGsmRe.length; index += 1) {
        pathRe += span(path.pointsGsmRe[index - 1]!, path.pointsGsmRe[index]!);
      }
    }

    expect(longestMarkRe).toBeLessThanOrEqual(onRe + slack);
    expect(longestGapRe).toBeLessThanOrEqual(offRe + slack);
    expect(loneMarks).toBe(0);
    // NEVER SOLID. The drawn ink is about the declared duty cycle of the path
    // it lies on, which is the whole of the traced/schematic distinction being
    // a property of the picture rather than of the prose beside it.
    expect(pathRe).toBeGreaterThan(0);
    const duty = inkRe / pathRe;
    expect(duty).toBeGreaterThan(0.5 * onRe / (onRe + offRe));
    expect(duty).toBeLessThan(0.95);
    visual.dispose();
  });

  /**
   * ## DEPTH CUEING IS OFF UNTIL THE SCENE SAYS WHERE THE CAMERA IS
   *
   * The wind is drawn in four materials and they all have to cue depth the
   * same way, or the streaks detach from their heads at the front of the
   * volume. And a consumer that never tells the visual where the camera is —
   * a headless build, a test, an embedder — has to get the old flat rendering
   * rather than a silently wrong one, which is what the zero default is for.
   */
  it("cues depth in every wind material, against the camera distance the scene hands over", () => {
    const visual = createSolarWindVisual({ particleCount: 64, seed: 7 });
    const materials = [visual.points, visual.trails, visual.guidedPoints, visual.guidedTrails, visual.modelPoints, visual.modelTrails]
      .map((object) => object.material as unknown as {
        uniforms: Record<string, { value: unknown } | undefined>;
        vertexShader: string;
      });
    for (const material of materials) {
      // Nobody has said where the camera is yet.
      expect(material.uniforms.cameraToEarth?.value).toBe(0);
      expect(material.vertexShader).toContain("solarWindNearFade");
    }
    // Heads shrink with distance; streaks are line segments with no gl_PointSize
    // to shrink, so the size term is CALLED only by the point materials. (Both
    // share one GLSL block, so the function is declared in every shader — what
    // is asserted here is the call site, which is the thing that renders.)
    expect((visual.points.material as unknown as { vertexShader: string }).vertexShader)
      .toContain("gl_PointSize = pointSize * scale * solarWindDepthSize(viewDist) * pixelRatio;");
    expect((visual.trails.material as unknown as { vertexShader: string }).vertexShader)
      .not.toContain("gl_PointSize");

    visual.setCameraDistance(42);
    for (const material of materials) expect(material.uniforms.cameraToEarth?.value).toBe(42);
    // Nonsense is refused rather than propagated: a NaN or a negative distance
    // turns the cue off instead of scaling the whole shower by garbage.
    for (const bad of [null, 0, -3, Number.NaN]) {
      visual.setCameraDistance(bad as number | null);
      for (const material of materials) expect(material.uniforms.cameraToEarth?.value).toBe(0);
    }
    visual.dispose();
  });

  /**
   * ## THE FACE THINS WHERE DEFLECTION STOPS, AND ENDS WITHOUT AN EDGE
   *
   * Sean saw a CONE: the emission face is capped at 400 Rₑ of impact
   * parameter, which at a zoomed-out frame reaches inside the picture, so the
   * wind ended at a hard silhouette that reads as the shape of the solar wind.
   *
   * The fix is opacity, and the reason it is honest is measured: past about
   * 40 Rₑ of impact parameter the flow solve deflects a parcel by under 4%,
   * and past 68 Rₑ by 0.3%, so every particle out there is doing the same
   * thing. THE INVARIANT THAT MUST HOLD is that this is opacity and only
   * opacity — the same tracers, in the same places, in the same species
   * proportions. "Make the outer field quieter" is one step from "draw fewer
   * of them out there", and that step would put the picture and the legend in
   * disagreement.
   */
  it("thins and tapers the outer face by opacity alone, on radii the ruler decides", () => {
    const visual = createSolarWindVisual({ particleCount: 512, seed: 11 });
    const before = visual.points.geometry.getAttribute("position").array.slice();
    const speciesBefore = visual.points.geometry.getAttribute("species").array.slice();

    // Nothing has cut a face yet at a known frame, so ask for one.
    visual.setViewFaceRadius(900);
    const radii = visual.faceFadeDrawnRadii;
    // Ordered, and every one of them is a DRAWN radius the ruler produced from
    // an impact parameter in Rₑ — not a number of pixels typed in.
    expect(radii.thinStart).toBeGreaterThan(0);
    expect(radii.thinEnd).toBeGreaterThan(radii.thinStart);
    expect(radii.edgeStart).toBeGreaterThan(0);
    expect(radii.edgeEnd).toBeGreaterThan(radii.edgeStart);
    expect(radii.edgeStart / radii.edgeEnd).toBeCloseTo(1 - SOLAR_WIND_FACE_FADE.edgeTaper, 6);
    // The far field is drawn thinly and never extinguished: the wind carries
    // on out there and a reader must be able to see that it does.
    expect(SOLAR_WIND_FACE_FADE.thinFloor).toBeGreaterThan(0.2);
    expect(SOLAR_WIND_FACE_FADE.thinFloor).toBeLessThan(0.6);

    // Re-cutting the face moves tracers across the face; the fade itself moves
    // NO tracer and changes NO species.
    const speciesAfter = visual.points.geometry.getAttribute("species").array;
    expect(Array.from(speciesAfter)).toEqual(Array.from(speciesBefore));

    // SPECIES-BLIND BY CONSTRUCTION: the fade is a function of POSITION and the
    // species of a tracer is a function of its INDEX. The shader is the place
    // that could break it, so the shader is what is asserted.
    const vertexShader = (visual.points.material as unknown as { vertexShader: string }).vertexShader;
    const fadeBody = vertexShader.slice(
      vertexShader.indexOf("float solarWindFaceFade"),
      vertexShader.indexOf("float solarWindFaceFade") + 400,
    );
    expect(fadeBody).toContain("length(localPosition.yz)");
    expect(fadeBody).not.toContain("species");
    expect(before.length).toBe(visual.points.geometry.getAttribute("position").array.length);
    visual.dispose();
  });

  /**
   * ## MASS READS AS MOTION CHARACTER, AND CHANGES NO COUNT
   *
   * The third channel, after colour and size ran out. The fade ramp along each
   * streak is raised to a per-species exponent: the electron's decays more
   * slowly (a longer, softer streak) and the alpha's faster (a short heavy
   * one). No vertex moves and no count changes — which is the invariant worth
   * pinning, because "make the species more visible" has twice been within one
   * step of "draw more of them".
   */
  it("shapes the streak per species without moving a vertex or a count", () => {
    const { proton, alpha, electron } = SOLAR_WIND_SPECIES_TRAIL_FADE_EXPONENT;
    expect(proton).toBe(1);
    expect(electron).toBeLessThan(proton);
    expect(alpha).toBeGreaterThan(proton);
    const visual = createSolarWindVisual({ particleCount: 64, seed: 7 });
    for (const object of [visual.trails, visual.guidedTrails]) {
      const material = object.material as unknown as {
        uniforms: Record<string, { value: unknown } | undefined>;
        vertexShader: string;
      };
      expect(material.uniforms.protonTrailFade?.value).toBe(proton);
      expect(material.uniforms.alphaTrailFade?.value).toBe(alpha);
      expect(material.uniforms.electronTrailFade?.value).toBe(electron);
      expect(material.vertexShader).toContain("pow(max(trailFade, 0.0), fadeExponent)");
    }
    // The geometry is untouched: still one segment per tracer, still a fade of
    // exactly 1 at the head and 0 at the tail.
    const fade = visual.trails.geometry.getAttribute("trailFade");
    expect(fade.getX(0)).toBe(1);
    expect(fade.getX(1)).toBe(0);
    visual.dispose();
  });

  /**
   * ## The bar is eased, and the trace species is still visibly the trace
   *
   * This test used to pin the opposite — "nobody has quietly given the hairline
   * a floor" — and it was right until Sean looked at the shipped result a second
   * time: *"the solar wind ledgend issue still hasn't been fixed. h+ and e+
   * still dominate. it still is impossible to see much more."* He then
   * authorised the exaggeration: *"It is okay to exagerate ... We need people to
   * see that both cases exist."*
   *
   * So the invariant flips, and what it becomes is the pair of bounds that keep
   * the easing from turning into the two things already rejected. WIDE ENOUGH:
   * the alpha has to clear a few pixels on the 290 px bar, or nothing has been
   * fixed. STILL NARROW ENOUGH: it has to stay several times narrower than
   * either of the others, or the bar is telling a reader that alphas are common,
   * which is the log axis and the equal-thirds bar all over again.
   */
  it("prints the energies on the rows, and prints nothing when there is no speed", () => {
    const mix = solarWindSpeciesMix();
    const withSpeed = solarWindSpeciesKey(mix, 259);
    expect(withSpeed.map((cell) => cell.energyText)).toEqual(["~0.19 eV", "~350 eV", "~1.4 keV"]);
    // The electron row, and only the electron row, has to say that the number
    // it prints is the BULK energy: the thermal jiggle is ~50x larger and a
    // bare 0.19 eV would teach a falsehood.
    expect(withSpeed.map((cell) => cell.energyIsBulkOnly)).toEqual([true, false, false]);
    // And the printed shares are still the measurement, untouched by any of it.
    expect(withSpeed[2]!.fraction).toBeCloseTo(mix.alphaFraction, 12);
    const withoutSpeed = solarWindSpeciesKey(mix);
    expect(withoutSpeed.map((cell) => cell.energyText)).toEqual([null, null, null]);
    expect(withoutSpeed.map((cell) => cell.text)).toEqual(withSpeed.map((cell) => cell.text));
  });
});

function distanceToPolyline(
  point: { xRe: number; yRe: number; zRe: number },
  path: GuidancePath,
): number {
  let best = Number.POSITIVE_INFINITY;
  for (let index = 1; index < path.pointsGsmRe.length; index += 1) {
    const a = path.pointsGsmRe[index - 1]!;
    const b = path.pointsGsmRe[index]!;
    const abX = b.x - a.x;
    const abY = b.y - a.y;
    const abZ = b.z - a.z;
    const lengthSquared = abX * abX + abY * abY + abZ * abZ;
    const t = lengthSquared > 0
      ? Math.min(1, Math.max(0,
        ((point.xRe - a.x) * abX + (point.yRe - a.y) * abY + (point.zRe - a.z) * abZ) / lengthSquared))
      : 0;
    const dx = point.xRe - (a.x + abX * t);
    const dy = point.yRe - (a.y + abY * t);
    const dz = point.zRe - (a.z + abZ * t);
    best = Math.min(best, Math.hypot(dx, dy, dz));
  }
  return best;
}

describe("guidance paths from the traced field-line model", () => {
  const traced = traceMagnetosphereFieldLines(QUIET)!;
  const paths = buildGuidancePaths(traced.lines);

  it("selects cusp funnels in both hemispheres and lobe rides, from real traced lines only", () => {
    const cusp = paths.filter((path) => path.role === "cusp");
    const lobe = paths.filter((path) => path.role === "lobe");
    expect(cusp.length).toBeGreaterThanOrEqual(4);
    expect(lobe.length).toBeGreaterThanOrEqual(2);
    expect(new Set(cusp.map((path) => path.hemisphere))).toEqual(new Set(["north", "south"]));
    // Cusp entries are dayside boundary points; travel ends at the footpoint.
    for (const path of cusp) {
      expect(path.entryGsmRe.x).toBeGreaterThan(0);
      const exit = path.pointsGsmRe.at(-1)!;
      expect(Math.hypot(exit.x, exit.y, exit.z)).toBeLessThan(1.2);
      // The footpoint lands in the cusp latitude band adjacent to the
      // auroral oval — the stated simplification, in numbers.
      expect(Math.abs(path.footpointLatitudeDeg!)).toBeGreaterThan(60);
      expect(Math.abs(path.footpointLatitudeDeg!)).toBeLessThan(85);
    }
    // Lobe rides start away from the planet and run tailward.
    for (const path of lobe) {
      expect(Math.hypot(path.entryGsmRe.x, path.entryGsmRe.y, path.entryGsmRe.z)).toBeGreaterThanOrEqual(5 - 1e-6);
      expect(path.pointsGsmRe.at(-1)!.x).toBeLessThan(path.entryGsmRe.x);
    }
  });

  it("keeps every on-path journey sample exactly on the traced polyline", () => {
    let onPathSamples = 0;
    for (const path of paths) {
      for (let step = 0; step <= 40; step += 1) {
        const sample = sampleGuidedJourney(path, step / 40, 12);
        if (!sample.onPath) {
          // Approach leg: straight sunward ray into the entry point.
          expect(sample.yRe).toBeCloseTo(path.entryGsmRe.y, 9);
          expect(sample.zRe).toBeCloseTo(path.entryGsmRe.z, 9);
          expect(sample.xRe).toBeGreaterThanOrEqual(path.entryGsmRe.x - 1e-9);
          continue;
        }
        onPathSamples += 1;
        expect(distanceToPolyline(sample, path)).toBeLessThan(1e-9);
      }
    }
    expect(onPathSamples).toBeGreaterThan(paths.length * 10);
  });
});

describe("the coupling in the visual, additive and honest", () => {
  it("shows the guided set only when coupling is active AND data exists, on the drawn lines", () => {
    const visual = createSolarWindVisual({ particleCount: 400, seed: 3 });
    const traced = traceMagnetosphereFieldLines(QUIET)!;
    visual.setFieldGuidance(traced.lines);
    // No conditions yet: nothing to draw.
    expect(visual.guidedPoints.visible).toBe(false);
    visual.setConditions(438, 5.9);
    expect(visual.guidedPoints.visible).toBe(false);
    visual.setCouplingActive(true);
    expect(visual.guidedPoints.visible).toBe(true);
    expect(visual.guidedTrails.visible).toBe(true);
    visual.update(2.7);
    // Every guided head is either on its own traced polyline or on its
    // straight approach ray — never anywhere else.
    const positions = visual.guidedPoints.geometry.getAttribute("position")!;
    const guidance = visual.guidancePaths;
    expect(guidance.length).toBeGreaterThan(4);
    let checked = 0;
    for (let index = 0; index < positions.count; index += 1) {
      const point = { xRe: positions.getX(index), yRe: positions.getY(index), zRe: positions.getZ(index) };
      const nearest = Math.min(...guidance.map((path) => distanceToPolyline(point, path)));
      const onApproach = guidance.some((path) =>
        Math.abs(point.yRe - path.entryGsmRe.y) < 1e-6
        && Math.abs(point.zRe - path.entryGsmRe.z) < 1e-6
        && point.xRe >= path.entryGsmRe.x - 1e-6);
      expect(nearest < 1e-6 || onApproach).toBe(true);
      checked += 1;
    }
    expect(checked).toBeGreaterThan(20);
    // Cusp paths dominate the roster: the poles are the point.
    const guidedGeometry = visual.guidedPoints.geometry;
    const meta = guidedGeometry.userData.guidance as { cuspPathCount: number; lobePathCount: number; termination: string };
    expect(meta.cuspPathCount).toBeGreaterThanOrEqual(meta.lobePathCount);
    expect(meta.termination).toContain("footpoint latitude");
    // Species carried through: the guided set is the same wind.
    expect(guidedGeometry.getAttribute("species")!.count).toBe(positions.count);

    // Magnetosphere layer off: the coupling disappears, the cloud does not.
    const cloudCount = visual.points.geometry.getAttribute("position")!.count;
    visual.setCouplingActive(false);
    expect(visual.guidedPoints.visible).toBe(false);
    expect(visual.points.geometry.getAttribute("position")!.count).toBe(cloudCount);
    // Clearing the guidance (field lines gone) empties the set.
    visual.setFieldGuidance(null);
    visual.setCouplingActive(true);
    expect(visual.guidedPoints.visible).toBe(false);
    visual.dispose();
  });

  /**
   * The scene passes `update()` the TOTAL environmental-motion clock, not a
   * per-frame delta. A consumer that accumulated its argument advanced by the
   * whole elapsed time on every frame, so within a few seconds of page load
   * each frame threw the guided particles a full journey further along and the
   * cusp funnelling — the one thing the coupling exists to show — was never
   * visible on the live site. Both halves below are properties of absolute
   * time and neither one holds under an accumulator.
   */
  it("reads its clock as elapsed time, so the funnelling is a steady stream and not a strobe", () => {
    const visual = createSolarWindVisual({ particleCount: 400, seed: 11 });
    visual.setFieldGuidance(traceMagnetosphereFieldLines(QUIET)!.lines);
    visual.setConditions(438, 5.9);
    visual.setCouplingActive(true);
    const heads = () => {
      const p = visual.guidedPoints.geometry.getAttribute("position")!;
      return Array.from({ length: p.count }, (_, i) => [p.getX(i), p.getY(i), p.getZ(i)] as const);
    };
    const stepBetween = (from: readonly (readonly [number, number, number])[], to: typeof from) =>
      Math.max(...from.map(([x, y, z], i) => {
        const [x2, y2, z2] = to[i]!;
        return Math.hypot(x2 - x, y2 - y, z2 - z);
      }));

    // A pure function of the clock: the same time twice is the same picture.
    // An accumulator moves everything on the second call.
    visual.update(5);
    const first = heads();
    visual.update(5);
    expect(stepBetween(first, heads())).toBeLessThan(1e-9);

    // And one frame's motion does not grow with how long the tab has been
    // open. Under the accumulator the late step was larger than the early one
    // by the ratio of the elapsed times — here they match.
    const frame = 1 / 60;
    visual.update(1);
    const earlyBefore = heads();
    visual.update(1 + frame);
    const earlyStep = stepBetween(earlyBefore, heads());
    visual.update(120);
    const lateBefore = heads();
    visual.update(120 + frame);
    const lateStep = stepBetween(lateBefore, heads());
    expect(earlyStep).toBeGreaterThan(0);
    expect(lateStep).toBeCloseTo(earlyStep, 6);
    visual.dispose();
  });

  it("hides the BATS-R-US plane tracers until the MHD cut option asks for them", () => {
    const visual = createSolarWindVisual({ particleCount: 200, seed: 4 });
    expect(visual.modelPoints.visible).toBe(false);
    expect(visual.modelTrails.visible).toBe(false);
    // Asking shows nothing while no model flow is loaded…
    visual.setPlaneTracersVisible(true);
    expect(visual.modelPoints.visible).toBe(false);
    visual.setPlaneTracersVisible(false);
    visual.dispose();
  });
});

/**
 * ## The lobe-to-sheet arrival
 *
 * Sean, on the shipped animation: *"it is hard to see particles feeding the
 * plasma sheet itself ... perhaps it needs to be a bit more stark."* The
 * measurement behind that: the collapse onto the current sheet is about four
 * Earth radii of a fifty-Earth-radii ride, so a return path spends under a
 * tenth of its journey on the one leg that shows the sheet being fed.
 *
 * What is pinned here is that the fix added marks and NOT a claim: the inflow
 * path is a slice of geometry the return paths already draw, it appears in
 * both lobes, it ends on the current sheet rather than short of it, and it
 * carries every species because the charge split belongs at the inner edge and
 * not before it.
 */
describe("the lobe-to-sheet inflow", () => {
  const traced = traceMagnetosphereFieldLines(DRIVEN)!;
  const lobe = buildGuidancePaths(traced.lines).filter((path) => path.role === "lobe");
  const built = buildTailReturnPaths(lobe, {
    dipoleTiltRad: DRIVEN.dipoleTiltRad,
    innerEdgeRe: 8,
    auroraBranch: true,
    magnetopause: { subsolarStandoffRe: 8.6, flaringAlpha: 0.62 },
  });
  const inflow = built.paths.filter((path) => path.role === "inflow");
  const returns = built.paths.filter((path) => path.role === "return");

  it("draws one arrival per extended ride, in BOTH lobes", () => {
    expect(built.report.extendedPathCount).toBeGreaterThan(2);
    expect(inflow).toHaveLength(built.report.inflowPathCount);
    expect(inflow.length).toBe(built.report.extendedPathCount);
    // The shape that reads as feeding rather than as a stream passing by is
    // material arriving from above AND below. One lobe alone would be the
    // defect this work exists to fix.
    expect(new Set(inflow.map((path) => path.hemisphere))).toEqual(new Set(["north", "south"]));
    for (const hemisphere of ["north", "south"] as const) {
      expect(inflow.filter((path) => path.hemisphere === hemisphere).length).toBeGreaterThan(0);
    }
  });

  it("adds no geometry of its own: every vertex is one a return path already draws", () => {
    for (const path of inflow) {
      // Vertex identity is not the claim — the lead-in is cut at a DISTANCE
      // along the traced line, so its first point is interpolated between two
      // of that line's vertices rather than being one of them. The claim is
      // that the whole path lies on a polyline a return ride already draws.
      for (const point of path.pointsGsmRe) {
        const nearest = Math.min(...returns.map((candidate) => distanceToPolyline(
          { xRe: point.x, yRe: point.y, zRe: point.z },
          candidate,
        )));
        expect(nearest).toBeLessThan(1e-6);
      }
    }
  });

  it("runs from the traced lobe line down onto the current sheet and stops there", () => {
    for (const path of inflow) {
      const start = path.pointsGsmRe[0]!;
      const end = path.pointsGsmRe.at(-1)!;
      // Starts up in the lobe, ends at the sheet: the drop crosses toward the
      // midplane in whichever hemisphere it came from.
      expect(Math.abs(end.z)).toBeLessThan(Math.abs(start.z));
      // It stops where the earthward injection begins, at the neutral line —
      // it does not carry on earthward, because the return paths already do.
      expect(end.x).toBeLessThan(-15);
      expect(path.totalLengthRe).toBeGreaterThan(LOBE_INFLOW_LEAD_RE * 0.9);
      expect(path.totalLengthRe).toBeLessThan(LOBE_INFLOW_LEAD_RE * 3);
      // The lead-in is the traced field line; the drop is the schematic.
      expect(path.schematicFromIndex).toBeGreaterThan(1);
      expect(path.schematicFromIndex!).toBeLessThan(path.pointsGsmRe.length);
    }
  });

  it("starts on the traced lobe line rather than at a point nobody drew", () => {
    for (const path of inflow) {
      const lobeLine = lobe.find((candidate) => candidate.hemisphere === path.hemisphere
        && distanceToPolyline(
          { xRe: path.pointsGsmRe[0]!.x, yRe: path.pointsGsmRe[0]!.y, zRe: path.pointsGsmRe[0]!.z },
          candidate,
        ) < 1e-6);
      expect(lobeLine, "the lead-in is the traced line's own geometry").toBeTruthy();
      const trimmed = trimToTailX(lobeLine!.pointsGsmRe, built.report.xLineRe)!;
      expect(trimmed).toBeTruthy();
    }
  });

  it("carries every species, because the charge split belongs at the inner edge", () => {
    for (const path of inflow) {
      expect(path.speciesFilter).toBeNull();
      expect(path.branch).toBeNull();
      expect(path.driftSense).toBeNull();
    }
    // …while the branches downstream of it stay split by charge.
    const ions = returns.filter((path) => path.driftSense === "westward");
    const electrons = returns.filter((path) => path.driftSense === "eastward");
    expect(ions.length).toBeGreaterThan(0);
    expect(electrons.length).toBeGreaterThan(0);
    for (const path of ions) expect(path.speciesFilter).toEqual(["proton", "alpha"]);
    for (const path of electrons) expect(path.speciesFilter).toEqual(["electron"]);
  });

  it("is not drawn at all where the return ride was refused", () => {
    const refused = buildTailReturnPaths(lobe, {
      dipoleTiltRad: DRIVEN.dipoleTiltRad,
      innerEdgeRe: 8,
      auroraBranch: true,
      // No measured boundary: the whole return leg is refused, and the
      // arrival must go with it rather than being drawn on its own.
      magnetopause: null,
    });
    expect(refused.report.extendedPathCount).toBe(0);
    expect(refused.report.inflowPathCount).toBe(0);
    expect(refused.paths.some((path) => path.role === "inflow")).toBe(false);
  });
});

/** A hand-built guidance line, for the pure-path unit checks. */
describe("buildGuidancePaths edge behaviour", () => {
  it("reverses boundary lines and rejects nightside truncations and stubs", () => {
    const lines: FieldGuidanceLine[] = [
      {
        topology: "boundary",
        seedLatitudeDeg: 72,
        seedLongitudeDeg: 0,
        pointsGsmRe: [
          { x: 0.3, y: 0, z: 1.03 },
          { x: 2, y: 0, z: 3 },
          { x: 5, y: 0, z: 5 },
          { x: 8, y: 0, z: 6 },
        ],
      },
      // Nightside truncation: not a cusp funnel.
      {
        topology: "boundary",
        seedLatitudeDeg: 70,
        seedLongitudeDeg: 180,
        pointsGsmRe: [
          { x: -0.3, y: 0, z: 1.03 },
          { x: -4, y: 0, z: 5 },
          { x: -9, y: 0, z: 8 },
          { x: -14, y: 0, z: 9 },
        ],
      },
      // Too short to guide anything.
      { topology: "boundary", seedLatitudeDeg: 71, seedLongitudeDeg: 30, pointsGsmRe: [{ x: 1, y: 0, z: 1 }] },
    ];
    const paths = buildGuidancePaths(lines);
    expect(paths).toHaveLength(1);
    const path = paths[0]!;
    expect(path.role).toBe("cusp");
    // Travel order: boundary entry first, footpoint last.
    expect(path.entryGsmRe).toEqual({ x: 8, y: 0, z: 6 });
    expect(path.pointsGsmRe.at(-1)).toEqual({ x: 0.3, y: 0, z: 1.03 });
    expect(path.footpointLatitudeDeg).toBe(72);
    expect(path.totalLengthRe).toBeGreaterThan(9);
  });
});
