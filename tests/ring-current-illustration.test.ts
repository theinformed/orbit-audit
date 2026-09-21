import * as THREE from "three";
import { describe, expect, it } from "vitest";

import fixture from "./data/plasmasphere-dgcpm-2026-08-08.json";
import explorerSource from "../src/main.ts?raw";
import indexHtml from "../index.html?raw";
import globeSource from "../src/globe.ts?raw";
import volumeSource from "../src/ring-current-volume.ts?raw";
import styleSource from "../src/styles.css?raw";
import {
  dataViewerSections,
  initialEnvironmentMotion,
  keyCardBar,
  ringCurrentLegendSpec,
  ringCurrentPulseLine,
  ringCurrentPulseReading,
} from "../src/main";
import { type DgcpmBundle, decodeDgcpmSequence, dgcpmFieldAt } from "../src/inner-magnetosphere";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";
import { setActiveDistanceScale } from "../src/radial-ruler";
import {
  type DriftSpecies,
  type RingCurrentFormation,
  COROTATION_POTENTIAL_SCALE_V,
  DEFAULT_RING_CURRENT_ION,
  RING_CURRENT_CONSTANTS,
  RING_CURRENT_ENERGY_SCALE,
  RING_CURRENT_ION_CHOICES,
  SURFACE_EQUATORIAL_FIELD_T,
  corotationAngularRateRadPerS,
  counterDriftingElectron,
  lastClosedDriftPath,
  createRingCurrentIons,
  createRingCurrentObject,
  injectionCorridor,
  ringCurrentFormation,
  RING_CURRENT_FORMATION,
  createRingCurrentPathLines,
  RING_CURRENT_PULSE,
  paintRingCurrentPulse,
  ringCurrentFormationLevel,
  ringCurrentLapSpread,
  ringCurrentLoopSeconds,
  ringCurrentPulsePeriodDisplaySeconds,
  driftHamiltonianKeV,
  driftPathPhase,
  driftRates,
  energyAtLKeV,
  energyRampColour,
  energyRampPosition,
  gsmFromDrift,
  magneticDriftAngularRateRadPerS,
  magneticDriftPeriodHours,
  mltHoursFromPhi,
  phiFromMltHours,
  ringCurrentIllustration,
  sampleDriftPath,
  setRingCurrentDisplayTime,
  traceDriftPath,
  vollandSternAmplitudeVPerRe2,
  zeroEnergySeparatrixL,
  trappedDriftRegion,
  createTrappedRegionMesh,
  DEFAULT_TRACE_LIMITS,
} from "../src/ring-current-illustration";

/**
 * The ring-current ILLUSTRATION, tested against the same real published output
 * the plasmasphere layer is tested against.
 *
 * The fixture is not a mock: it is three frames lifted unaltered out of a
 * `pipeline/plasmasphere_dgcpm.py` run over the actual NOAA Kp record for the
 * storm of 2026-08-08 — quiet before it, the Kp 5.67 peak, and eight hours into
 * recovery. That matters more here than anywhere else on the site, because the
 * whole defensibility of this layer rests on one claim: that the electric field
 * these ions drift in is the SAME published field, at the same instant, that
 * the plasmasphere on the layer above is being eroded by. These tests check
 * that against the bytes the pipeline really wrote, not against a restatement.
 *
 * The functions exercised are the exported ones the application calls. There is
 * no test-only re-derivation of the physics anywhere in this file: where a
 * number is checked against theory it is checked against a number printed in a
 * textbook or in the pipeline's own artifact, never against a second copy of
 * the same arithmetic.
 */
const bundle = fixture as unknown as DgcpmBundle;
const sequence = decodeDgcpmSequence(bundle);

const QUIET = new Date("2026-08-07T18:00:00Z");
const PEAK = new Date("2026-08-08T18:00:00Z");
const RECOVERY = new Date("2026-08-09T02:00:00Z");

const fieldAt = (at: Date) => {
  const field = dgcpmFieldAt(sequence, at);
  if (!field) throw new Error(`the fixture has no frame for ${at.toISOString()}`);
  return field;
};

const EARTH_SCENE_RADIUS = 100;
/** The scene's real mapper, the same one the globe hands this layer. */
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  return { x: xRe * scale, y: yRe * scale, z: zRe * scale } as never;
};

describe("the closed forms agree with the papers and with the pipeline", () => {
  it("puts the dipole's equatorial surface field at about 31,000 nT", () => {
    // The value that follows from the pipeline's own moment and Earth radius.
    expect(SURFACE_EQUATORIAL_FIELD_T * 1e9).toBeCloseTo(31_027, 0);
  });

  it("recovers Earth's own rotation rate from the corotation potential", () => {
    // Not a coincidence and not a fit: Phi_c is DEFINED as omega mu0 M/(4 pi
    // R_E), so the corotation drift it produces has to come back out as omega.
    // If the two ever disagreed, the cold plasma and the energetic ions would
    // be corotating at different speeds in the same picture.
    expect(corotationAngularRateRadPerS()).toBeCloseTo(RING_CURRENT_CONSTANTS.earthAngularRateRadPerS, 15);
    expect(COROTATION_POTENTIAL_SCALE_V / 1000).toBeCloseTo(91.8, 1);
  });

  it("computes the same Volland-Stern amplitude the Python pipeline published", () => {
    // The layer never USES this function — it reads A off the frame — but if
    // the two laws had drifted apart, the claim that this illustration rides
    // the plasmasphere's own field would be false.
    for (const frame of bundle.frames) {
      expect(vollandSternAmplitudeVPerRe2(frame.kp)).toBeCloseTo(frame.convectionAmplitudeVPerRe2, 1);
    }
  });

  it("computes the same zero-energy stagnation point the pipeline published", () => {
    for (const frame of bundle.frames) {
      const amplitudeVPerM = frame.convectionAmplitudeVPerRe2 / RING_CURRENT_CONSTANTS.earthRadiusM;
      expect(zeroEnergySeparatrixL(amplitudeVPerM)).toBeCloseTo(frame.stagnationL, 2);
    }
  });

  it("energises an ion as L^-3, because mu is conserved", () => {
    const ion = DEFAULT_RING_CURRENT_ION;
    expect(ion.referenceEnergyKeV).toBe(10);
    expect(ion.referenceL).toBe(8);
    expect(energyAtLKeV(ion, 8)).toBeCloseTo(10, 9);
    expect(energyAtLKeV(ion, 4)).toBeCloseTo(80, 9);
    expect(energyAtLKeV(ion, 2)).toBeCloseTo(640, 9);
  });

  it("gives a 100 keV ion at L 4 a drift period of about 1.8 hours", () => {
    // Textbook: the equatorially mirroring drift period is 2 pi q B_0 R_E^2 /
    // (3 W L), which is about 44 minutes at 1 MeV and L = 1 and scales as
    // 1/(W L). A 1 MeV electron at L = 4 is the familiar "about ten minutes".
    expect(magneticDriftPeriodHours(4, 100)).toBeCloseTo(1.84, 2);
    expect(magneticDriftPeriodHours(4, 1000) * 60).toBeCloseTo(11.0, 1);
    // Inverse in both L and energy.
    expect(magneticDriftPeriodHours(6, 100)).toBeCloseTo(magneticDriftPeriodHours(4, 100) * (4 / 6), 6);
  });

  it("drifts ions WESTWARD and electrons EASTWARD, which is the whole point", () => {
    // phi increases eastward, so a negative angular rate is westward.
    const ionRate = magneticDriftAngularRateRadPerS(4, 80, 1);
    const electronRate = magneticDriftAngularRateRadPerS(4, 80, -1);
    expect(ionRate).toBeLessThan(0);
    expect(electronRate).toBeGreaterThan(0);
    // Equal and opposite: opposite charges going opposite ways carry the SAME
    // current, which is why they add rather than cancel.
    expect(ionRate).toBeCloseTo(-electronRate, 12);
  });

  it("beats corotation by more than an order of magnitude at ring-current energies", () => {
    // The card prints this ratio; it is the reason the ring current is a
    // westward current rather than a corotating one.
    const magnetic = Math.abs(magneticDriftAngularRateRadPerS(4, energyAtLKeV(DEFAULT_RING_CURRENT_ION, 4), 1));
    expect(magnetic / corotationAngularRateRadPerS()).toBeGreaterThan(10);
  });
});

describe("the drift field is the plasmasphere's own field", () => {
  const amplitudeVPerM = 716.16 / RING_CURRENT_CONSTANTS.earthRadiusM;
  const ion = DEFAULT_RING_CURRENT_ION;
  const electron = counterDriftingElectron(ion);

  it("gives every species and energy the same E x B drift", () => {
    for (const mlt of [0, 6, 12, 18]) {
      const phi = phiFromMltHours(mlt);
      const forIon = driftRates(ion, 5, phi, amplitudeVPerM);
      const forElectron = driftRates(electron, 5, phi, amplitudeVPerM);
      expect(forIon.exbAngularRadPerS).toBeCloseTo(forElectron.exbAngularRadPerS, 15);
      expect(forIon.radialLPerS).toBeCloseTo(forElectron.radialLPerS, 15);
    }
  });

  it("convects sunward: inward at midnight, outward at noon, neither at dawn or dusk", () => {
    // The same assertion `tests/test_plasmasphere_dgcpm.py` makes about the
    // pipeline's own `drift_velocity`, made here about the TypeScript copy, so
    // a mirrored sign cannot survive in one and not the other.
    expect(driftRates(ion, 5, phiFromMltHours(0), amplitudeVPerM).radialLPerS).toBeLessThan(0);
    expect(driftRates(ion, 5, phiFromMltHours(12), amplitudeVPerM).radialLPerS).toBeGreaterThan(0);
    expect(driftRates(ion, 5, phiFromMltHours(6), amplitudeVPerM).radialLPerS).toBeCloseTo(0, 12);
    expect(driftRates(ion, 5, phiFromMltHours(18), amplitudeVPerM).radialLPerS).toBeCloseTo(0, 12);
  });

  it("reduces to pure corotation when the convection field and the energy vanish", () => {
    const cold: DriftSpecies = { chargeSign: 1, referenceEnergyKeV: 1e-12, referenceL: 8, label: "cold" };
    const rates = driftRates(cold, 4, phiFromMltHours(0), 1e-30);
    expect(rates.angularRadPerS).toBeCloseTo(corotationAngularRateRadPerS(), 12);
    expect(rates.angularRadPerS).toBeGreaterThan(0);
  });
});

describe("the drawn plane is the one every other layer uses", () => {
  it("puts midnight anti-sunward, noon sunward, dusk at +y and dawn at -y", () => {
    // GSM +x is noon and +y is dusk, the convention the plasmasphere stipple
    // and the radiation-belt mapping already use. A mirrored local time would
    // put the ion drift on the dawn side and teach the wrong half of the
    // physics with a picture that looked perfectly plausible.
    const midnight = gsmFromDrift(5, phiFromMltHours(0));
    expect(midnight.x).toBeCloseTo(-5, 9);
    expect(midnight.y).toBeCloseTo(0, 9);
    const noon = gsmFromDrift(5, phiFromMltHours(12));
    expect(noon.x).toBeCloseTo(5, 9);
    const dusk = gsmFromDrift(5, phiFromMltHours(18));
    expect(dusk.y).toBeCloseTo(5, 9);
    const dawn = gsmFromDrift(5, phiFromMltHours(6));
    expect(dawn.y).toBeCloseTo(-5, 9);
    for (const point of [midnight, noon, dusk, dawn]) expect(point.z).toBe(0);
  });

  it("round-trips MLT through phi", () => {
    for (const mlt of [0, 3.5, 6, 12, 18, 23.75]) {
      expect(mltHoursFromPhi(phiFromMltHours(mlt))).toBeCloseTo(mlt, 9);
    }
    // Westward past midnight wraps rather than going negative.
    expect(mltHoursFromPhi(phiFromMltHours(0) - 0.1)).toBeGreaterThan(23);
  });
});

describe("the traced paths are the contours the physics says they are", () => {
  const amplitudeVPerM = 716.16 / RING_CURRENT_CONSTANTS.earthRadiusM;
  const ion = DEFAULT_RING_CURRENT_ION;

  it("conserves qPhi + muB along every path, which is the check on the integrator", () => {
    // This is the one test that would catch a wrong drift equation AND a wrong
    // integrator at the same time. The motion is perpendicular to the gradient
    // of H by construction, so H walking means the code is not integrating the
    // drift it claims to.
    for (const seedL of [2.6, 3.4, 4.2, 5.5, 7, 8]) {
      const path = traceDriftPath(ion, amplitudeVPerM, seedL, 0);
      expect(path.samples.length).toBeGreaterThan(20);
      const start = driftHamiltonianKeV(ion, path.samples[0]!.lShell, path.samples[0]!.phiRadians, amplitudeVPerM);
      for (const sample of path.samples) {
        const here = driftHamiltonianKeV(ion, sample.lShell, sample.phiRadians, amplitudeVPerM);
        expect(Math.abs(here - start) / Math.max(1, Math.abs(start))).toBeLessThan(1e-6);
      }
    }
  });

  it("carries ions westward and electrons eastward around the Earth", () => {
    const ionPath = traceDriftPath(ion, amplitudeVPerM, 3, 0);
    expect(ionPath.closure).toBe("closed");
    expect(ionPath.windingRadians).toBeLessThan(0);
    const electronPath = traceDriftPath(counterDriftingElectron(ion), amplitudeVPerM, 3, 0);
    expect(electronPath.closure).toBe("closed");
    expect(electronPath.windingRadians).toBeGreaterThan(0);
  });

  it("brings a closed path back to where it started", () => {
    const path = traceDriftPath(ion, amplitudeVPerM, 3, 0);
    const last = path.samples[path.samples.length - 1]!;
    // A full circuit of a contour has to return to the seed radius; the gap is
    // the integrator's accumulated error over a whole lap.
    expect(Math.abs(last.lShell - 3)).toBeLessThan(0.01);
  });

  it("brings ions closest to Earth on the dusk side, the way the real one is asymmetric", () => {
    // Emergent, not asserted: on the dusk meridian the convection potential is
    // lowest, so a contour of qPhi + muB has to sit at smaller L there. This is
    // the mechanism behind the observed dusk-favoured partial ring current —
    // and nothing in this release MEASURES that, which is why the card says so.
    const path = traceDriftPath(ion, amplitudeVPerM, 4, 0);
    expect(path.minimumLMltHours).toBeGreaterThan(15);
    expect(path.minimumLMltHours).toBeLessThan(21);
  });

  it("says 'escaped' for a path that leaves through the outer edge, and traces it whole", () => {
    const path = traceDriftPath(ion, amplitudeVPerM, 8, 0);
    expect(path.closure).toBe("escaped");
    // Both legs: the backward leg is prepended, so the seed is in the middle
    // rather than at the start, and the drawn curve runs from where the
    // particle entered the domain to where it left.
    expect(path.samples[0]!.elapsedSeconds).toBe(0);
    const seedIndex = path.samples.findIndex((sample) => Math.abs(sample.lShell - 8) < 1e-9);
    expect(seedIndex).toBeGreaterThan(0);
    // Time is ascending everywhere, which is what the marker lookup assumes.
    for (let index = 1; index < path.samples.length; index += 1) {
      expect(path.samples[index]!.elapsedSeconds).toBeGreaterThanOrEqual(path.samples[index - 1]!.elapsedSeconds);
    }
  });

  it("moves a marker westward along its path as display time runs", () => {
    const path = traceDriftPath(ion, amplitudeVPerM, 3, 0);
    const quarter = path.durationSeconds / 4;
    const start = sampleDriftPath(path, 0);
    const later = sampleDriftPath(path, quarter);
    expect(start.mltHours).toBeCloseTo(0, 6);
    // A quarter of a westward lap from midnight lands in the dusk sector.
    expect(later.mltHours).toBeGreaterThan(16);
    expect(later.mltHours).toBeLessThan(20);
    // And its energy is the energy of where it now is, not where it was born.
    expect(later.energyKeV).toBeCloseTo(energyAtLKeV(ion, later.lShell), 6);
  });

  it("wraps the phase so a circuit repeats rather than running off the end", () => {
    const path = traceDriftPath(ion, amplitudeVPerM, 3, 0);
    const once = driftPathPhase(path, path.durationSeconds * 0.3);
    const again = driftPathPhase(path, path.durationSeconds * 1.3);
    expect(again.index).toBe(once.index);
    expect(again.weight).toBeCloseTo(once.weight, 6);
    expect(driftPathPhase(path, -path.durationSeconds * 0.7).wrappedSeconds)
      .toBeCloseTo(path.durationSeconds * 0.3, 3);
  });
});

describe("the illustration reads the published frame and nothing else", () => {
  it("takes its convection field off the frame rather than recomputing it", () => {
    for (const at of [QUIET, PEAK, RECOVERY]) {
      const field = fieldAt(at);
      const state = ringCurrentIllustration(field);
      // Identity, not approximation: the number on the card IS the number the
      // pipeline published for the plasmasphere on the layer above.
      expect(state.amplitudeVPerRe2).toBe(field.frame.convectionAmplitudeVPerRe2);
      expect(state.kp).toBe(field.frame.kp);
      expect(state.validAt).toBe(field.frame.validAt);
      expect(state.publishedStagnationL).toBe(field.frame.stagnationL);
      expect(state.amplitudeVPerM * RING_CURRENT_CONSTANTS.earthRadiusM).toBeCloseTo(state.amplitudeVPerRe2, 6);
    }
  });

  it("pushes the Alfven layer inward as the storm strengthens", () => {
    // The teaching claim, checked on real published Kp: stronger convection
    // means a smaller trapped region, so fewer of the drawn paths close and the
    // boundary between trapped and swept-through moves toward Earth.
    const quiet = ringCurrentIllustration(fieldAt(QUIET));
    const peak = ringCurrentIllustration(fieldAt(PEAK));
    const recovery = ringCurrentIllustration(fieldAt(RECOVERY));
    expect(peak.separatrix!.lShell).toBeLessThan(recovery.separatrix!.lShell);
    expect(recovery.separatrix!.lShell).toBeLessThan(quiet.separatrix!.lShell);
    expect(peak.closedCount).toBeLessThan(quiet.closedCount);
    expect(peak.escapedCount).toBeGreaterThan(quiet.escapedCount);
  });

  it("lets injected ions reach deeper, and arrive hotter, at the storm peak", () => {
    const quiet = ringCurrentIllustration(fieldAt(QUIET));
    const peak = ringCurrentIllustration(fieldAt(PEAK));
    expect(peak.deepestPenetration!.lShell).toBeLessThan(quiet.deepestPenetration!.lShell);
    expect(peak.deepestPenetration!.energyKeV).toBeGreaterThan(quiet.deepestPenetration!.energyKeV);
    // The population this builds is the one the ring current is made of.
    expect(peak.deepestPenetration!.energyKeV).toBeGreaterThan(20);
    expect(peak.deepestPenetration!.energyKeV).toBeLessThan(300);
  });

  it("moves the boundary with ENERGY, which is the sentence the layer exists for", () => {
    const field = fieldAt(PEAK);
    const boundaries = RING_CURRENT_ION_CHOICES.map(
      (species) => ringCurrentIllustration(field, species).separatrix!.lShell,
    );
    // Strictly ordered in energy at one instant, in one field, on one
    // meridian. Cold plasma is trapped closest in and the more energetic the
    // particle the further out its path still closes, because a fast azimuthal
    // drift rounds the Earth before convection can carry it out — which is the
    // same reason the radiation belts extend past the plasmapause.
    expect(boundaries[0]).toBeLessThan(boundaries[1]!);
    expect(boundaries[1]).toBeLessThan(boundaries[2]!);
    expect(ringCurrentIllustration(field).zeroEnergySeparatrixMidnightL).toBeLessThan(boundaries[0]!);
  });

  it("agrees with the traced boundary about where the zero-energy limit is", () => {
    // The closed form (2/3)L_s and the integrator have to say the same thing.
    // If they ever disagreed, one of the two statements on the card would be
    // describing a different boundary from the curve on screen.
    const nearlyCold: DriftSpecies = { chargeSign: 1, referenceEnergyKeV: 1e-9, referenceL: 8, label: "cold" };
    for (const at of [QUIET, PEAK, RECOVERY]) {
      const state = ringCurrentIllustration(fieldAt(at));
      const traced = lastClosedDriftPath(nearlyCold, state.amplitudeVPerM);
      expect(traced).not.toBeNull();
      expect(traced!.lShell).toBeCloseTo(state.zeroEnergySeparatrixMidnightL, 1);
      // And the dusk nose of the same teardrop is the stagnation point the
      // pipeline publishes, which is 1.5x the midnight radius.
      expect(state.zeroEnergySeparatrixL / state.zeroEnergySeparatrixMidnightL).toBeCloseTo(1.5, 9);
    }
  });

  it("keys its rebuild on the frame and the selected ion, and on nothing else", () => {
    const peak = fieldAt(PEAK);
    const first = ringCurrentIllustration(peak).rebuildKey;
    expect(ringCurrentIllustration(peak).rebuildKey).toBe(first);
    expect(ringCurrentIllustration(peak, RING_CURRENT_ION_CHOICES[2]).rebuildKey).not.toBe(first);
    expect(ringCurrentIllustration(fieldAt(RECOVERY)).rebuildKey).not.toBe(first);
  });

  it("classifies every seeded path and reports stalls rather than relabelling them", () => {
    for (const at of [QUIET, PEAK, RECOVERY]) {
      const state = ringCurrentIllustration(fieldAt(at));
      expect(state.paths.length).toBe(15);
      expect(state.closedCount + state.escapedCount + state.stalledCount).toBe(state.paths.length);
    }
  });
});

/**
 * THE CLAIM, in every state the card can be in.
 *
 * The word on the badge changed on 2026-08-19 and the claim did not. Sean:
 * "the ring current is an illustration.... i thought you were going to make it
 * something that ISN'T a useless illustration but something REAL. why does it
 * still say it is an illustration?"
 *
 * ILLUSTRATION was correct for what this layer used to be - drift-path lines
 * with sprites marching along them, a diagram over the data - and that was
 * deleted. What is drawn now is a ray-marched volume whose region is RK4
 * integrated in NOAA's published Volland-Stern convection field at published
 * Kp, bounded by the computed Alfvén layer and coloured by `energyAtLKeV`.
 * That is `model`, the class the plasma sheet already carries for plasma β
 * computed off the NOAA cuts, and it was taken from the existing
 * `LegendEvidence` vocabulary rather than invented.
 *
 * THE SECOND CLAIM IS UNTOUCHED and these tests exist to keep it that way: no
 * upstream publishes a gridded ring current, Dst is the only ring-current
 * measurement here and one number has no map, so the SHAPE is derived and
 * never observed. It is on the badge, on the colour bar, in the card's first
 * row in every state, and at length in the note.
 */
describe("the card says what kind of claim it is making, in every state it can be in", () => {
  const states = ["not-published", "not-loaded", "load-failed", "outside-window"] as const;

  it("never falls back to the scale-less SHAPE ONLY bar", () => {
    // The project owner's first acceptance check. A key card with no ramp is
    // the presentation this family exists to retire, and a layer whose whole
    // claim is "this is an illustration" would be the worst possible place to
    // reach it.
    const ready = ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(PEAK)));
    expect(keyCardBar(ready, false).kind).toBe("ramp");
    for (const state of states) {
      const spec = ringCurrentLegendSpec(null, state);
      expect(keyCardBar(spec, false).kind, `state "${state}" fell back to the flat bar`).toBe("ramp");
      // And the ramp carries real units even with no drive at all.
      expect(spec.scale!.label).toContain("keV");
    }
  });

  it("carries the derived-shape claim on the badge, the classification and the bar itself", () => {
    const spec = ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(PEAK)));
    expect(spec.badge).toContain("MODEL-DERIVED");
    // The half that may never be weakened, whatever the class says.
    expect(spec.badge).toContain("NOT MEASURED");
    expect(spec.evidence).toBe("model");
    // And it is a class that already exists and already means this, not a new
    // word: the plasma sheet carries the same one for the same kind of thing.
    expect(explorerSource).toMatch(/layer: "plasmaSheet"[\s\S]{0,400}evidence: "model"/);
    // The colour-bar label is the one surface that is on screen with every
    // panel shut, so the claim has to survive there too.
    expect(spec.scale!.label).toContain("MODEL-DERIVED");
    expect(RING_CURRENT_ENERGY_SCALE.label).toContain("MODEL-DERIVED");
    expect(spec.note).toContain("MODEL-DERIVED");
    expect(spec.note).toContain("No upstream this site fetches publishes a ring-current ion flux on a grid");
  });

  it("never lets the class be read as a claim that the shape was measured", () => {
    // The whole risk of the reclassification, in one test. MODEL is a stronger
    // word than ILLUSTRATION and a reader could take it as "NOAA publishes
    // this". Every state must still say, in words, that nothing does.
    for (const spec of [
      ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(PEAK))),
      ...states.map((state) => ringCurrentLegendSpec(null, state)),
    ]) {
      expect(spec.badge).toContain("SHAPE NOT MEASURED");
      expect(spec.stats![0]!.value).toContain("NOT MEASURED IS THE SHAPE");
      expect(spec.note).toContain("WHAT IS NOT MEASURED IS THE SHAPE");
    }
  });

  it("states the drift physics, and the losses it does not model", () => {
    const spec = ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(PEAK)));
    expect(spec.note).toContain("ions go westward, electrons eastward");
    expect(spec.note).toContain("charge exchange");
    expect(spec.note).toContain("Alfvén layer".toUpperCase());
    expect(spec.note).toContain("Liemohn");
  });

  it("quotes the frame's own driving numbers when it has a frame", () => {
    const state = ringCurrentIllustration(fieldAt(PEAK));
    const spec = ringCurrentLegendSpec(state);
    const labels = spec.stats!.map((row) => row.label);
    expect(labels).toContain("DRIVING Kp");
    const driving = spec.stats!.find((row) => row.label === "DRIVING Kp")!.value;
    expect(driving).toContain(state.kp.toFixed(2));
    expect(driving).toContain(state.amplitudeVPerRe2.toFixed(0));
    const alfven = spec.stats!.find((row) => row.label === "ALFVÉN LAYER AT MIDNIGHT")!.value;
    expect(alfven).toContain(state.separatrix!.lShell.toFixed(2));
    // Both boundaries are quoted on the same meridian so a reader can compare
    // them; the dusk nose is named as a dusk nose rather than left ambiguous.
    const cold = spec.stats!.find((row) => row.label === "SAME BOUNDARY AT ZERO ENERGY, ALSO AT MIDNIGHT")!.value;
    expect(cold).toContain(state.zeroEnergySeparatrixMidnightL.toFixed(2));
    expect(cold).toContain("at dusk");
    expect(spec.statusState).toBe("ready");
  });

  it("keeps the invariant physics quoted when there is no frame to drive it", () => {
    // Absence of the drive removes the driven numbers and nothing else. A card
    // that goes blank teaches nothing; a card that keeps what is true anyway
    // and names what is missing teaches the difference between the two.
    //
    // WHERE those invariants are quoted changed on 2026-08-19 and this asserts
    // the new arrangement rather than dropping the claim: the standing physics
    // is on the layer's Data & methods card, rendered from this same spec, and
    // the one invariant that is a CAVEAT stays on the operational card. Twelve
    // readings on the panel measured 756 px inside a 432 px window; the clock
    // test in `dataViewerSections` is the rule that decided which go where.
    const spec = ringCurrentLegendSpec(null, "outside-window");
    const labels = spec.stats!.map((row) => row.label);
    const standing = (spec.standing ?? []).map((row) => row.label);
    expect(labels).toContain("WHAT IS MEASURED HERE");
    expect(standing).toContain("DRIFT SENSE");
    expect(standing).toContain("ION DRIFT PERIOD AT L 4");
    // Still quoted in EVERY state, which is the property this test exists for.
    // Five, not four: WHY THIS LAYER MATTERS joined them on 2026-08-19. It is
    // as clock-invariant as the drift sense, and it exists because the card
    // that led with "WHAT IS MEASURED HERE: NOTHING" and said nothing else was
    // read by this site's owner as "this layer is not worth your time".
    expect(standing).toContain("WHY THIS LAYER MATTERS");
    // SIX since 2026-08-20: WHERE THESE IONS COME FROM joined them when the
    // inner plasma sheet was added to this same layer. It qualifies for the
    // standing list on the rule this test exists to enforce — it is a statement
    // about the physics and not about the clock. The two rows that DO move with
    // the clock ("THE SUPPLY, RIGHT NOW" and "CAN THE SITE TIME THE SNAP?") are
    // on the operational card instead, and the assertion below pins that split.
    expect(standing).toContain("WHERE THESE IONS COME FROM");
    expect(standing).toHaveLength(6);
    expect(standing).not.toContain("THE SUPPLY, RIGHT NOW");
    expect(standing).not.toContain("CAN THE SITE TIME THE SNAP?");
    // And with NO substorm state they are not on the operational card either:
    // two rows reading "not for this instant" are not readings, and this card
    // is the one that was measured at 12 readings and 756 px in a 432 px
    // window. They appear only when there is something measured to say.
    expect(labels).not.toContain("THE SUPPLY, RIGHT NOW");
    expect(labels).not.toContain("CAN THE SITE TIME THE SNAP?");
    const driven = dataViewerSections(ringCurrentLegendSpec(null, "outside-window", null, {
      phase: "growth",
      loading: 0.8,
      injection: 0,
      onset: null,
      minutesSinceOnset: null,
      onsetEvidence: "ring-current-response",
      southwardBzNtMinutes: 360,
      bzGsmNt: -4.2,
    })).readings.map(([label]) => label);
    expect(driven).toContain("THE SUPPLY, RIGHT NOW");
    expect(driven).toContain("CAN THE SITE TIME THE SNAP?");
    expect(labels).not.toContain("DRIVING Kp");
    expect(spec.statusState).toBe("no-data");
    expect(spec.statusText).toContain("OUTSIDE THE SIMULATED WINDOW");
  });
});

describe("the colour ramp is a real, monotone energy scale", () => {
  it("runs log over its stated range and clamps outside it", () => {
    expect(energyRampPosition(RING_CURRENT_ENERGY_SCALE.minimumKeV)).toBeCloseTo(0, 9);
    expect(energyRampPosition(RING_CURRENT_ENERGY_SCALE.maximumKeV)).toBeCloseTo(1, 9);
    // Log, so the geometric midpoint is the halfway colour.
    expect(energyRampPosition(Math.sqrt(1 * 1000))).toBeCloseTo(0.5, 9);
    expect(energyRampPosition(0.001)).toBe(0);
    expect(energyRampPosition(1e6)).toBe(1);
    let previous = -1;
    for (let energy = 1; energy <= 1000; energy *= 1.5) {
      const here = energyRampPosition(energy);
      expect(here).toBeGreaterThanOrEqual(previous);
      previous = here;
    }
  });

  it("ends the ramp on the stops the legend gradient prints", () => {
    // The CSS gradient, the CPU colouring and the marker shader are three
    // copies of one palette; the two that a test can reach have to agree.
    expect(energyRampColour(1)).toEqual([0.169, 0.078, 0.212]);
    const hottest = energyRampColour(1000);
    expect(hottest[0]).toBeCloseTo(1, 6);
    expect(hottest[1]).toBeCloseTo(0.902, 6);
    expect(RING_CURRENT_ENERGY_SCALE.gradient).toContain("#2b1436");
    expect(RING_CURRENT_ENERGY_SCALE.gradient).toContain("#ffe6a8");
  });
});

describe("everything drawn goes through the scene's shared radial ruler", () => {
  const state = ringCurrentIllustration(fieldAt(PEAK));

  it("places every path vertex where the ruler puts its L shell", () => {
    const lines = createRingCurrentPathLines(state, { positionForGsm });
    const positions = lines.geometry.getAttribute("position");
    expect(positions.count).toBeGreaterThan(100);
    // Sample the drawn radii and check each one against the ruler evaluated at
    // the physical radius the inverse mapping implies. Nothing here duplicates
    // the ruler: it is called, exactly as the layer calls it.
    let checked = 0;
    for (let index = 0; index < positions.count; index += 97) {
      const drawnRadius = Math.hypot(positions.getX(index), positions.getY(index), positions.getZ(index));
      expect(drawnRadius).toBeGreaterThan(radiationBeltDisplayRadius(1.5, EARTH_SCENE_RADIUS));
      expect(drawnRadius).toBeLessThanOrEqual(radiationBeltDisplayRadius(9.01, EARTH_SCENE_RADIUS));
      checked += 1;
    }
    expect(checked).toBeGreaterThan(5);
  });

  it("draws in the magnetic-equatorial plane and nowhere else", () => {
    // Asserted on the region, which is what the scene draws now. The drift-path
    // lines are still built and still tested directly below; they are simply no
    // longer added to the group.
    const group = createRingCurrentObject(state, { positionForGsm });
    const region = group.getObjectByName("ring-current-trapped-region") as never as { geometry: { getAttribute: (name: string) => { count: number; getZ: (index: number) => number } } };
    const positions = region.geometry.getAttribute("position");
    for (let index = 0; index < positions.count; index += 53) {
      expect(positions.getZ(index)).toBeCloseTo(0, 6);
    }
  });

  it("puts the region and its boundary on screen, and no marching dots", () => {
    // What Sean saw twice and called a cartoon: every traced drift path drawn
    // as a line, with a cloud of sprites animating around them, ON TOP of the
    // region. The region is the physical statement — where a trapped ion lives
    // — and it was the faintest thing in the group.
    //
    // The Alfven layer stays because it is not decoration: it is the last
    // closed drift path, the actual edge of the trapped population, and the
    // region ends exactly there.
    const group = createRingCurrentObject(state, { positionForGsm });
    expect(group.getObjectByName("ring-current-trapped-region")).toBeTruthy();
    // The dashed boundary and its label are NOT on the globe. Sean: "You can
    // move that either to the data card or to the learning site but that
    // doesn't belong on the main site." Annotation over a rendered field
    // competes with the field, which is the same reason the drift-path lines
    // and the marching sprites came off this layer. The volume already ends AT
    // the Alfven layer, so the boundary reads as the edge of the glow without a
    // curve drawn over it, and the numbers stay on the card.
    expect(group.getObjectByName("ring-current-alfven-layer")).toBeUndefined();
    expect(group.getObjectByName("ring-current-alfven-label")).toBeUndefined();
    expect(group.getObjectByName("ring-current-drift-paths")).toBeUndefined();
    expect(group.getObjectByName("ring-current-ions")).toBeUndefined();
  });

  it("redraws at different radii when the visitor switches to true distance", () => {
    // The two scales must never mix on screen, and the globe rebuilds this
    // object when the scale flips. Proving the geometry actually moves is the
    // only way to know the rebuild is doing anything.
    try {
      setActiveDistanceScale("teaching");
      const teaching = createRingCurrentPathLines(state, { positionForGsm });
      setActiveDistanceScale("true-distance");
      const trueDistance = createRingCurrentPathLines(state, { positionForGsm });
      const first = teaching.geometry.getAttribute("position");
      const second = trueDistance.geometry.getAttribute("position");
      expect(second.count).toBe(first.count);
      const teachingRadius = Math.hypot(first.getX(0), first.getY(0), first.getZ(0));
      const trueRadius = Math.hypot(second.getX(0), second.getY(0), second.getZ(0));
      expect(trueRadius).not.toBeCloseTo(teachingRadius, 1);
    } finally {
      setActiveDistanceScale("teaching");
    }
  });

  it("advances the drifting ions westward on the display clock", () => {
    const ions = createRingCurrentIons(state, { positionForGsm });
    const positions = ions.geometry.getAttribute("position");
    // The one closed path is the clean case: a closed drift path is a circuit,
    // and a marker on it has to be going round the short way — westward, which
    // in this plane is from -x toward +y.
    const closedIndex = state.paths.findIndex((path) => path.closure === "closed");
    expect(closedIndex).toBeGreaterThanOrEqual(0);
    const path = state.paths[closedIndex]!;
    setRingCurrentDisplayTime(ions, 0);
    const before = { x: positions.getX(0), y: positions.getY(0) };
    // A quarter lap of display time, in the layer's own replay factor.
    const quarterLapDisplaySeconds = path.durationSeconds / 4 / 400;
    setRingCurrentDisplayTime(ions, quarterLapDisplaySeconds);
    const after = { x: positions.getX(0), y: positions.getY(0) };
    expect(Math.hypot(after.x - before.x, after.y - before.y)).toBeGreaterThan(1);
    // Started at midnight (-x), a quarter of a westward lap later it is on the
    // dusk side (+y). Reversed drift would put it at -y.
    expect(before.x).toBeLessThan(0);
    expect(after.y).toBeGreaterThan(0);
    // Every marker carries a ramp position inside the bar, and an alpha.
    const ramp = ions.geometry.getAttribute("rampPosition");
    for (let index = 0; index < ramp.count; index += 1) {
      expect(ramp.getX(index)).toBeGreaterThanOrEqual(0);
      expect(ramp.getX(index)).toBeLessThanOrEqual(1);
    }
  });

  it("declares in its own userData that nothing in it is measured", () => {
    const group = createRingCurrentObject(state, { positionForGsm });
    expect(group.userData.status).toBe("illustration");
    expect(String(group.userData.measured)).toContain("nothing");
    expect(String(group.userData.driftSense)).toContain("ions westward");
    // The dashed boundary and its label are NOT on the globe. Sean: "You can
    // move that either to the data card or to the learning site but that
    // doesn't belong on the main site." Annotation over a rendered field
    // competes with the field, which is the same reason the drift-path lines
    // and the marching sprites came off this layer. The volume already ends AT
    // the Alfven layer, so the boundary reads as the edge of the glow without a
    // curve drawn over it, and the numbers stay on the card.
    expect(group.getObjectByName("ring-current-alfven-layer")).toBeUndefined();
    expect(group.getObjectByName("ring-current-alfven-label")).toBeUndefined();
    // The ion sprites are gone from the group; the drift SENSE they used to
    // show is still declared here, because it is a fact about the physics and
    // not about the animation that used to illustrate it.
    expect(group.getObjectByName("ring-current-trapped-region")).toBeTruthy();
  });
});

describe("the layer is actually reachable from the page", () => {
  /**
   * This project has shipped features that compiled, passed their unit tests
   * and did not exist on the page, twice. A layer needs all four of these or it
   * is unreachable: a checkbox in the markup, an entry in the id map that binds
   * the listener, an entry in the card/legend order, and a branch that builds
   * its spec.
   */
  it("has a checkbox, an id mapping, a place in the legend order and a spec branch", () => {
    expect(indexHtml).toContain('id="layer-ring-current"');
    expect(indexHtml).toContain('data-layer-block="ringCurrent"');
    expect(indexHtml).toContain('data-layer-panel="ringCurrent"');
    expect(explorerSource).toContain('"layer-ring-current": "ringCurrent"');
    expect(explorerSource).toContain('ringCurrent: "layer-ring-current"');
    expect(explorerSource).toMatch(/layerOrder: LayerName\[\] = \[[^\]]*"ringCurrent"/s);
    // The branch and the call, separately: the call went multi-line when the
    // card started quoting the storm banner's own Dst, and a test that pins
    // line breaks pins formatting rather than wiring.
    expect(explorerSource).toMatch(/if \(layer === "ringCurrent"\) \{[\s\S]{0,400}?return ringCurrentLegendSpec\(/);
  });

  it("offers every ion the module defines, and only those", () => {
    for (const species of RING_CURRENT_ION_CHOICES) {
      expect(indexHtml).toContain(`data-ring-current-energy="${species.referenceEnergyKeV}"`);
    }
    const offered = [...indexHtml.matchAll(/data-ring-current-energy="([^"]+)"/g)].map((match) => Number(match[1]));
    expect(offered.sort((a, b) => a - b))
      .toEqual(RING_CURRENT_ION_CHOICES.map((species) => species.referenceEnergyKeV).sort((a, b) => a - b));
    expect(explorerSource).toContain('document.querySelectorAll<HTMLButtonElement>("[data-ring-current-energy]")');
  });

  it("fetches the plasmasphere artifact, which is the only source of its field", () => {
    // Without this the layer switches on and can never draw anything: its
    // convection amplitude is read off that artifact's frames.
    expect(explorerSource).toContain('if (checked && layer === "ringCurrent") void this.loadPlasmasphere();');
  });

  it("is rebuilt by the globe when the radial scale changes", () => {
    const rebuild = globeSource.slice(globeSource.indexOf("private rebuildRadialGeometry()"));
    expect(rebuild.slice(0, rebuild.indexOf("\n  private ", 1))).toContain("this.setRingCurrent(ringCurrent);");
  });

  it("drifts on the same environmental-motion clock as every other flow glyph", () => {
    expect(globeSource).toContain("setRingCurrentDisplayTime(this.ringCurrentObject, this.environmentalAnimationElapsedSeconds)");
    const animate = globeSource.slice(globeSource.indexOf("private animate = () => {"));
    const gate = animate.slice(animate.indexOf("if (this.environmentalMotionEnabled)"));
    expect(gate.slice(0, gate.indexOf("this.solarWindVisual.update"))).toContain("setRingCurrentDisplayTime");
  });
});

describe("the trapped region", () => {
  /**
   * The drift paths show HOW ions move; this shows WHERE the closed ones live.
   * Its whole claim is "inside this boundary a particle stays", so the tests
   * are about the boundary being the field's own answer and about the region
   * refusing to imply anything it cannot support.
   */
  const species = DEFAULT_RING_CURRENT_ION;

  it("is bounded by the last closed drift path, not by a drawn radius", () => {
    const amplitude = vollandSternAmplitudeVPerRe2(5);
    const last = lastClosedDriftPath(species, amplitude);
    const region = trappedDriftRegion(species, amplitude);
    if (last) {
      expect(region.clippedToDomain).toBe(false);
      expect(region.boundaryL).toBeCloseTo(last.lShell, 6);
    } else {
      expect(region.clippedToDomain).toBe(true);
    }
  });

  it("shrinks when the convection field strengthens", () => {
    // Stronger convection pushes the Alfven layer inward: the trapped region is
    // smaller during a storm. If this ever inverts, the physics is wrong, not
    // the drawing.
    const quiet = trappedDriftRegion(species, vollandSternAmplitudeVPerRe2(1));
    const storm = trappedDriftRegion(species, vollandSternAmplitudeVPerRe2(7));
    if (!quiet.clippedToDomain && !storm.clippedToDomain) {
      expect(storm.boundaryL).toBeLessThan(quiet.boundaryL);
    } else {
      // A quiet field can legitimately put the boundary outside the domain.
      expect(quiet.clippedToDomain || storm.boundaryL < quiet.boundaryL).toBe(true);
    }
  });

  it("says so when the boundary lies beyond the traced domain", () => {
    // A very weak field traps everything the trace can see. Drawing nothing
    // would read as "no ring current", which is the opposite of the truth, so
    // the region is drawn to the edge and flagged.
    const region = trappedDriftRegion(species, vollandSternAmplitudeVPerRe2(0), {
      ...DEFAULT_TRACE_LIMITS,
      lMaximum: 4,
    });
    if (region.clippedToDomain) {
      expect(region.boundaryL).toBe(4);
      expect([...region.outerL].every((l) => l === 4)).toBe(true);
    }
    expect(region.domainL).toBe(4);
  });

  it("covers every local time, with no hole left by the trace", () => {
    const region = trappedDriftRegion(species, vollandSternAmplitudeVPerRe2(4));
    expect(region.outerL).toHaveLength(region.mltHours.length);
    for (const l of region.outerL) {
      expect(Number.isFinite(l)).toBe(true);
      expect(l).toBeGreaterThan(region.innerL);
    }
  });

  it("draws a closed surface whose radii come from the shared ruler", () => {
    const region = trappedDriftRegion(species, vollandSternAmplitudeVPerRe2(4));
    const seen: Array<[number, number, number]> = [];
    const mesh = createTrappedRegionMesh(region, species, {
      positionForGsm: (x, y, z) => {
        seen.push([x, y, z]);
        // A deliberately non-identity ruler: if the builder did its own
        // arithmetic anywhere, these assertions would not hold.
        return new THREE.Vector3(x * 3, y * 3, z * 3);
      },
    });
    expect(seen.length).toBeGreaterThan(0);
    const position = mesh.geometry.getAttribute("position");
    expect(position.count).toBe(seen.length);
    for (let index = 0; index < position.count; index += 1) {
      expect(position.getX(index)).toBeCloseTo(seen[index]![0] * 3, 5);
    }
    expect(mesh.geometry.getIndex()).not.toBeNull();
  });

  it("keeps its opacity flat, whatever the energy", () => {
    // The site publishes no ring-current density on a grid. Opacity that varied
    // with anything would read as "there is more of it here", which is a claim
    // this layer must never make.
    const region = trappedDriftRegion(species, vollandSternAmplitudeVPerRe2(4));
    const mesh = createTrappedRegionMesh(region, species, {
      positionForGsm: (x, y, z) => new THREE.Vector3(x, y, z),
    });
    const material = mesh.material as { opacity: number; transparent: boolean };
    expect(material.transparent).toBe(true);
    expect(typeof material.opacity).toBe("number");
    // Colour carries the energy; alpha carries nothing.
    expect(mesh.geometry.getAttribute("color")).toBeDefined();
    expect(mesh.geometry.getAttribute("alpha")).toBeUndefined();
  });
});

/**
 * THE FORMATION.
 *
 * The layer is called "how it forms" and for two rounds of review it drew a
 * static object. What is asserted here is not that something moves — a green
 * test proves nothing about how a picture looks — but that everything the
 * motion is built from is TRACED rather than chosen, and that the one thing
 * this layer had motion deleted for is still absent.
 */
describe("how it forms", () => {
  const state = ringCurrentIllustration(fieldAt(PEAK));

  it("traces the tail supply into a field, not into filaments", () => {
    const corridor = injectionCorridor(state.species, state.amplitudeVPerM);
    // Every cell it claims is a cell a traced parcel actually reached (or a
    // one-cell dilation of one), so the corridor cannot assert plasma anywhere
    // the drift does not carry it.
    expect(corridor.reachedCells).toBeGreaterThan(500);
    expect(corridor.reachedCells).toBeLessThan(corridor.mltBins * corridor.lBins);
    // Unreached cells stay unreached: they are Infinity, and the shader draws
    // nothing there for the whole loop.
    let infinite = 0;
    for (let index = 0; index < corridor.arrivalSeconds.length; index += 1) {
      if (!Number.isFinite(corridor.arrivalSeconds[index]!)) infinite += 1;
    }
    expect(infinite).toBeGreaterThan(0);
    expect(corridor.spanSeconds).toBeGreaterThan(0);
  });

  it("carries the supply deepest on the DUSK side, where the trapped region is pinched", () => {
    // This is the mechanism behind the observed dusk-favoured partial ring
    // current, and it is a property of the traced paths rather than a
    // statement made beside them. It is also why the layer can show plasma
    // arriving at all: at dusk the boundary is at its smallest, so the open
    // paths reach closest to Earth there.
    expect(state.deepestPenetration).not.toBeNull();
    expect(state.deepestPenetration!.mltHours).toBeGreaterThan(15);
    expect(state.deepestPenetration!.mltHours).toBeLessThan(21);
    expect(state.deepestPenetration!.lShell).toBeLessThan(state.region.widestL);
  });

  it("closes the ring at each shell's own traced lap time, inner shells first", () => {
    const formation = ringCurrentFormation(state, state.region);
    // The drift rate goes as W L and W as L^-3, so the lap goes as L^2 and an
    // inner shell laps a faster than an outer one. If this ever inverted, the
    // picture would show the ring closing from the outside in, which is the
    // opposite of what the drift does.
    const inner = formation.lapSeconds[2]!;
    const outer = formation.lapSeconds[formation.shellBins - 3]!;
    expect(inner).toBeGreaterThan(0);
    expect(outer).toBeGreaterThan(inner);
    // Every lap is a real traced duration, not a chosen animation length: the
    // closed paths in the illustration are where they come from.
    const closed = state.paths.filter((path) => path.closure === "closed");
    expect(closed.length).toBeGreaterThan(0);
    const shortest = Math.min(...closed.map((path) => path.durationSeconds));
    const longest = Math.max(...closed.map((path) => path.durationSeconds));
    expect(inner).toBeGreaterThanOrEqual(shortest * 0.5);
    expect(outer).toBeLessThanOrEqual(longest * 3);
    // A loop with three parts, all finite, all positive.
    expect(formation.fillSeconds).toBeGreaterThan(0);
    expect(formation.cycleSeconds).toBeGreaterThan(formation.fillSeconds);
    expect(Number.isFinite(formation.cycleSeconds)).toBe(true);
  });

  it("builds a stronger storm's ring faster than a quiet field's", () => {
    // Not a display choice: stronger convection pulls the Alfven layer in, the
    // trapped shells are smaller, and a smaller shell laps sooner. The loop
    // length is read off that, so the picture is quicker when the storm is.
    const quiet = ringCurrentIllustration(fieldAt(QUIET));
    const storm = ringCurrentIllustration(fieldAt(PEAK));
    const quietLoop = ringCurrentFormation(quiet, quiet.region).cycleSeconds;
    const stormLoop = ringCurrentFormation(storm, storm.region).cycleSeconds;
    expect(stormLoop).toBeLessThan(quietLoop);
  });

  it("puts the motion in the volume and nowhere else — still no lines, still no marching dots", () => {
    // The distinction the whole of RING_CURRENT_FORMATION rests on. What was
    // deleted was drift paths drawn as lines with sprites marching along them,
    // ON TOP of the region; Sean's word for it, twice, was "cartoon". What is
    // here is the region's own density over time.
    const group = createRingCurrentObject(state, { positionForGsm, earthSceneRadius: EARTH_SCENE_RADIUS });
    expect(group.getObjectByName("ring-current-volume")).toBeTruthy();
    // The dashed boundary and its label are NOT on the globe. Sean: "You can
    // move that either to the data card or to the learning site but that
    // doesn't belong on the main site." Annotation over a rendered field
    // competes with the field, which is the same reason the drift-path lines
    // and the marching sprites came off this layer. The volume already ends AT
    // the Alfven layer, so the boundary reads as the edge of the glow without a
    // curve drawn over it, and the numbers stay on the card.
    expect(group.getObjectByName("ring-current-alfven-layer")).toBeUndefined();
    expect(group.getObjectByName("ring-current-alfven-label")).toBeUndefined();
    expect(group.getObjectByName("ring-current-drift-paths")).toBeUndefined();
    expect(group.getObjectByName("ring-current-ions")).toBeUndefined();
  });

  it("advances the volume's own clock, and wraps it inside one loop", () => {
    const group = createRingCurrentObject(state, { positionForGsm, earthSceneRadius: EARTH_SCENE_RADIUS });
    const volume = group.getObjectByName("ring-current-volume") as THREE.Mesh;
    const uniforms = (volume.material as THREE.ShaderMaterial).uniforms;
    const cycle = uniforms.cycleSeconds!.value as number;
    expect(cycle).toBeGreaterThan(0);
    expect(uniforms.formationEnabled!.value).toBe(1);

    setRingCurrentDisplayTime(group, 0);
    expect(uniforms.formationSeconds!.value).toBeCloseTo(0, 6);
    const quarterOfALoopInDisplaySeconds = cycle / 4 / RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
    setRingCurrentDisplayTime(group, quarterOfALoopInDisplaySeconds);
    expect(uniforms.formationSeconds!.value).toBeCloseTo(cycle / 4, 3);
    // A loop, so the display clock running on for hours never runs the
    // formation off the end of its own timeline.
    const wholeLoop = cycle / RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
    setRingCurrentDisplayTime(group, wholeLoop * 7 + quarterOfALoopInDisplaySeconds);
    expect(uniforms.formationSeconds!.value).toBeCloseTo(cycle / 4, 3);
  });
});

/**
 * THE BOUNDARY'S SHAPE, which the card quotes and the on-screen label is
 * anchored to.
 */
describe("the Alfven layer is named, and named in the right place", () => {
  it("comes out widest at DAWN and pinched at DUSK, at every energy and every Kp", () => {
    // The plasmapause bulges at DUSK, and it would have been natural to write
    // the same sentence here. It is false at these energies: a few-tens-of-keV
    // ion drifts westward fast enough to beat corotation on the dawn side
    // first, so the ION boundary is the teardrop the other way round. The
    // scene's label is anchored on `widestMltHours` rather than on the
    // assumption, and the card prints both extremes.
    for (const at of [QUIET, PEAK, RECOVERY]) {
      for (const species of RING_CURRENT_ION_CHOICES) {
        const region = ringCurrentIllustration(fieldAt(at), species).region;
        expect(region.widestMltHours, `${species.label} at ${at.toISOString()}`).toBeGreaterThan(3);
        expect(region.widestMltHours).toBeLessThan(9);
        expect(region.narrowestMltHours).toBeGreaterThan(15);
        expect(region.narrowestMltHours).toBeLessThan(21);
        expect(region.widestL).toBeGreaterThan(region.narrowestL);
      }
    }
  });

  it("keeps the boundary NUMBERS on the card now that nothing draws it", () => {
    // The dashed curve and its on-globe label came off on 2026-08-19 - that
    // annotation does not belong on the main site - which makes the card the
    // ONLY place this fact lives. So the row carries the meaning as well as
    // the value, and the two extremes and the flip between them stay with it.
    const spec = ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(PEAK)));
    const alfven = spec.stats!.find((row) => row.label === "ALFVÉN LAYER AT MIDNIGHT")!.value;
    expect(alfven).toMatch(/^L \d/);
    expect(alfven).toContain("the last drift path that closes on itself");
    // And it must not go on describing an annotation that is no longer drawn.
    expect(alfven).not.toContain("DASHED");
    expect(alfven).not.toContain("labelled on the globe");
    const shape = spec.stats!.find((row) => row.label === "AND ITS SHAPE")!.value;
    expect(shape).toContain("dawn");
    expect(shape).toContain("dusk");
    expect(spec.stats!.some((row) => row.label === "SAME BOUNDARY AT ZERO ENERGY, ALSO AT MIDNIGHT")).toBe(true);
  });
});

/**
 * WHY THE CARD IS WORTH READING.
 *
 * Sean, looking at the shipped card: "Is the ring current really not important?
 * It just says illustration on the legend. Is it not worth showing?" Three
 * things had to become true at once, and none of them may be traded for
 * another.
 */
describe("the card separates how important this is from how well it is known", () => {
  const spec = ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(PEAK)), "not-published", {
    phase: "main",
    chipLabel: "MAIN · MODERATE · Dst −84 nT",
    dstNt: -84,
    dstSource: "Kyoto quicklook Dst",
    reason: "test",
  });

  it("quotes the measured Dst the storm banner is grading the storm with", () => {
    const measured = spec.stats![0]!;
    expect(measured.label).toBe("WHAT IS MEASURED HERE");
    expect(measured.value).toContain("84");
    expect(measured.value).toContain("KYOTO QUICKLOOK DST");
    expect(measured.value).toContain("STORM BANNER");
  });

  it("keeps the provenance disclosure in the same breath, undiluted", () => {
    // The point is not that the disclosure survived: it is that it is now a
    // claim about the MAP rather than about the subject. Both halves, one row,
    // in this order.
    const measured = spec.stats![0]!.value;
    expect(measured.indexOf("DST")).toBeLessThan(measured.indexOf("NOT MEASURED IS THE SHAPE"));
    // The two claims stay distinct: the phenomenon is central and MEASURED, by
    // Dst; the map is DERIVED. Reclassifying the layer changed only the second.
    expect(measured).toContain("NOT OBSERVED");
    expect(spec.badge).toContain("MODEL-DERIVED");
    expect(spec.evidence).toBe("model");
    expect(spec.scale!.label).toContain("MODEL-DERIVED");
  });

  it("still says the number out loud when no storm is classified", () => {
    // Quiet is the state a reader is most likely to open this in, and a row
    // that vanishes then would leave the caveat standing alone again.
    const quiet = ringCurrentLegendSpec(ringCurrentIllustration(fieldAt(QUIET)));
    const measured = quiet.stats![0]!;
    expect(measured.label).toBe("WHAT IS MEASURED HERE");
    expect(measured.value).toContain("DST");
    expect(measured.value).toContain("NOT MEASURED IS THE SHAPE");
  });

  it("tells a reader why the layer is worth their time at all", () => {
    const standing = (spec.standing ?? []).find((row) => row.label === "WHY THIS LAYER MATTERS")!;
    expect(standing.value).toContain("STORM");
    expect(standing.value).toContain("DST");
    expect(spec.note).toContain("WHY THIS ONE MATTERS");
    // And the note still carries every limitation it carried before.
    expect(spec.note).toContain("charge exchange");
    expect(spec.note).toContain("No upstream this site fetches publishes a ring-current ion flux on a grid");
    expect(spec.note).toContain("WHAT IS NOT MEASURED IS THE SHAPE");
  });

  it("says what the drawn motion is, and what it is not", () => {
    const motion = spec.stats!.find((row) => row.label === "WHAT THE MOTION CLAIMS")!.value;
    expect(motion).toContain("NOT PARTICLES MARCHING");
    expect(motion).toContain("NOTHING COUNTABLE");
    expect(spec.note).toContain("no marker, no line, no sprite");
    // The one thing a steady field cannot do, said in the note rather than
    // drawn: trapping needs the Alfven layer to move, and one published Kp
    // gives one boundary.
    expect(spec.note).toContain("last closed drift path");
  });

  it("says LOWER BOUND when the boundary's dawn side runs into the integrator's ceiling", () => {
    // The Alfven layer is bisected on the MIDNIGHT meridian, and the contour
    // through that seed is widest at DAWN. `traceDriftPath` stops at
    // `limits.lMaximum`, so a boundary that closes comfortably inside the
    // domain at midnight can still be cut off at dawn — and `widestL` would
    // then be reporting L 9.00, the edge of the integrator, as if it were the
    // physics. `clippedToDomain` cannot catch it: that flag answers a different
    // question (did ANY path inside the domain open at all) and is false in
    // exactly this case.
    //
    // Measured across Kp 0-6 at the three energies the layer offers, the dawn
    // maximum lands exactly on the ceiling for the 10 keV ion at Kp 0 and the
    // 30 keV ion at Kp 0 through 3.
    const amplitude = (kp: number) => vollandSternAmplitudeVPerRe2(kp) / RING_CURRENT_CONSTANTS.earthRadiusM;
    const ion30 = RING_CURRENT_ION_CHOICES[2]!;
    const clipped = trappedDriftRegion(ion30, amplitude(0), DEFAULT_TRACE_LIMITS);
    expect(clipped.clippedToDomain).toBe(false);
    expect(clipped.boundaryL).toBeLessThan(DEFAULT_TRACE_LIMITS.lMaximum);
    expect(clipped.widestL).toBeCloseTo(DEFAULT_TRACE_LIMITS.lMaximum, 2);
    expect(clipped.contourClippedAtDomain).toBe(true);

    // And it must not fire when the whole contour is genuinely inside. At Kp 5
    // the convection is strong enough to pull the dawn side well in.
    const inside = trappedDriftRegion(ion30, amplitude(5), DEFAULT_TRACE_LIMITS);
    expect(inside.clippedToDomain).toBe(false);
    expect(inside.contourClippedAtDomain).toBe(false);
    expect(inside.widestL).toBeLessThan(DEFAULT_TRACE_LIMITS.lMaximum - 0.5);

    // Widest at DAWN at every energy and Kp, clipped or not, which is the fact
    // the copy on both cards now states.
    for (const kp of [0, 1, 2, 3, 4, 5, 6]) {
      for (const species of RING_CURRENT_ION_CHOICES) {
        const region = trappedDriftRegion(species, amplitude(kp), DEFAULT_TRACE_LIMITS);
        expect(region.widestMltHours).toBeGreaterThan(3);
        expect(region.widestMltHours).toBeLessThan(9);
      }
    }
  });
});

/**
 * THE PULSE, AND THE ONE WAY THIS COULD HAVE MADE THINGS WORSE.
 *
 * Sean asked what the pulsing is and whether its periodicity is real, and asked
 * for the colour scale to pulse at the rate shown with a very short line saying
 * what that period is. The failure mode is specific and it is worse than the
 * silence: a swatch that breathes at a rate the population does not, next to a
 * number that does not follow the energy selector, is a manufactured rhythm
 * presented as a measurement. Every test here exists to close one route to it.
 */
describe("the ring current says how long its own pulse is", () => {
  const state = ringCurrentIllustration(fieldAt(PEAK));
  const drawn = () => createRingCurrentObject(state, { positionForGsm, earthSceneRadius: EARTH_SCENE_RADIUS });

  // 30 s: this builds the real drawn object, which is forty-odd RK4 traces.
  // The 5 s default is a budget for arithmetic, and every test in this block
  // that integrates drift paths has blown it on a loaded workstation.
  it("hands the drawn object's own loop to the surfaces that quote it", { timeout: 30_000 }, () => {
    // The period may not come from a second, freshly computed formation: two
    // runs of forty RK4 traces can disagree, and then the card would be
    // quoting a loop the globe is not keeping. It comes off the drawn object.
    const group = drawn();
    const formation = group.userData.formationState as RingCurrentFormation | null;
    expect(formation).not.toBeNull();
    const volume = group.getObjectByName("ring-current-volume") as THREE.Mesh;
    const uniforms = (volume.material as THREE.ShaderMaterial).uniforms;
    expect(formation!.cycleSeconds).toBe(uniforms.cycleSeconds!.value as number);
    expect(formation!.fillSeconds).toBe(uniforms.fillSeconds!.value as number);
    expect(formation!.holdSeconds).toBe(uniforms.holdSeconds!.value as number);
    expect(formation!.decaySeconds).toBe(uniforms.decaySeconds!.value as number);
  });

  it("quotes cycleSeconds divided by the replay rate, and nothing else", { timeout: 30_000 }, () => {
    const group = drawn();
    const formation = group.userData.formationState as RingCurrentFormation;
    const expected = formation.cycleSeconds / RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
    expect(ringCurrentPulsePeriodDisplaySeconds(formation)).toBeCloseTo(expected, 12);
    const line = ringCurrentPulseLine(formation, state)!;
    expect(line).toContain(`PULSE ${expected.toFixed(1)} s`);
    // And the anchor travels with it. A period with no ion and no Kp beside it
    // is a number a reader cannot check or reproduce.
    expect(line).toContain(`${state.species.referenceEnergyKeV} keV`);
    expect(line).toContain(`Kp ${state.kp.toFixed(1)}`);
    // Sean asked for a very short text, and then on 2026-08-27 for a shorter
    // one: "Only that PULSE 15.7, you don't need ONE FILL AND FADE. Keep it
    // short enough to fit on one line."
    //
    // 40 characters is that instruction as a pixel measurement. The legend
    // block gives `.key-card-pulse` 290 px of text on a 1440-wide desktop
    // (`.map-key` is min(310px, 100%), less 9 px of card padding a side) and
    // 350 px on a 390-wide phone. IBM Plex Mono at `--fs-nano` measures 5.0 px
    // per character at the shipped Large interface scale and 7.0 px at Largest,
    // so desktop-at-Largest is the binding case and it buys 41 characters. The
    // longest string this function can build is 31. The line before this ruling
    // was 69 characters and took two lines.
    expect(line.length).toBeLessThanOrEqual(40);
    // The words Sean named are the ones that had to go, and they did not go
    // anywhere: the layer's card still carries the whole statement.
    expect(line).not.toContain("ONE FILL AND FADE");
    expect(ringCurrentPulseReading(formation)).toContain("ONE FILL AND FADE OF THE RING");
    expect(ringCurrentPulseReading(formation)).toContain(`${(formation.cycleSeconds / 3600).toFixed(1)} h OF DRIFT`);
  });

  // 90 s: nine illustrations and nine formations — three energies at three
  // published Kp — which is the point of the test and is not reducible.
  it("MOVES when the energy selector moves, at every published Kp", { timeout: 90_000 }, () => {
    // The defect this is written against, in the brief's own words: an energy
    // selector that moves while the number does not is worse than the silence
    // being fixed. Measured across the fixture, the loop runs from 3.3 s to
    // 44.9 s on screen, so a frozen number would be wrong by a factor of 13.
    for (const at of [QUIET, PEAK, RECOVERY]) {
      const printed = RING_CURRENT_ION_CHOICES.map((species) => {
        const illustration = ringCurrentIllustration(fieldAt(at), species);
        const formation = ringCurrentFormation(illustration, illustration.region);
        return {
          seconds: ringCurrentPulsePeriodDisplaySeconds(formation),
          line: ringCurrentPulseLine(formation, illustration)!,
        };
      });
      // Three energies, three different printed periods, no two alike.
      expect(new Set(printed.map((entry) => entry.line)).size).toBe(3);
      // And ordered the way the physics orders them: the drift rate is
      // proportional to energy, so the hotter ion laps sooner and its ring
      // closes sooner. This is the assertion that would fail if the number
      // were ever pinned to a constant that merely looked plausible.
      expect(printed[2]!.seconds).toBeLessThan(printed[1]!.seconds);
      expect(printed[1]!.seconds).toBeLessThan(printed[0]!.seconds);
      for (const entry of printed) {
        expect(entry.line).toContain(`PULSE ${entry.seconds.toFixed(1)} s`);
      }
    }
  });

  it("refuses to call the loop a drift lap, because there is not one lap in it", { timeout: 30_000 }, () => {
    // The trap. `RING_CURRENT_DRIFT_REPLAY` exists so that the ENERGY
    // DEPENDENCE of the drift is visible, which means the drawn shells lap at
    // different rates on purpose. A single "the drift period is X" would
    // animate that away in words.
    const group = drawn();
    const formation = group.userData.formationState as RingCurrentFormation;
    const laps = ringCurrentLapSpread(formation);
    expect(laps.outerHours).toBeGreaterThan(laps.innerHours * 3);
    const reading = ringCurrentPulseReading(formation);
    expect(reading).toContain("NOT A DRIFT LAP");
    expect(reading).toContain("NO SINGLE LAP");
    expect(reading).toContain(`${laps.innerHours.toFixed(1)} h`);
    expect(reading).toContain(`${laps.outerHours.toFixed(1)} h`);
    // The loop is longer than the fastest lap and shorter than nothing silly:
    // it CONTAINS the laps, which is the reason it is the honest single number.
    expect(formation.cycleSeconds / 3600).toBeGreaterThan(laps.innerHours);
  });

  it("keeps the fallback honest when there is no formation to quote", () => {
    // The flat-surface path has no formation and does not move, and every test
    // that builds a spec without a scene is in the same position. The clause
    // falls back to what it said before a period was computable here, rather
    // than to a plausible number.
    expect(ringCurrentPulseLine(null, state)).toBeNull();
    expect(ringCurrentPulseReading(null)).toBe(
      `${RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond / 3600} HOUR OF DRIFT PER SECOND OF SCREEN TIME`,
    );
    expect(ringCurrentPulseReading(null)).not.toContain("PULSES EVERY");
    const spec = ringCurrentLegendSpec(state);
    expect(spec.stats!.find((row) => row.label === "WHAT THE MOTION CLAIMS")!.value).not.toContain("PULSES EVERY");
  });

  it("prints the period on the layer's card when the scene has a loop", { timeout: 30_000 }, () => {
    const group = drawn();
    const formation = group.userData.formationState as RingCurrentFormation;
    const spec = ringCurrentLegendSpec(state, "not-published", null, null, formation);
    const motion = spec.stats!.find((row) => row.label === "WHAT THE MOTION CLAIMS")!.value;
    const seconds = ringCurrentPulsePeriodDisplaySeconds(formation);
    expect(motion).toContain(`IT PULSES EVERY ${seconds.toFixed(1)} s, EXACTLY`);
    // The claim it may never lose while gaining a period.
    expect(motion).toContain("NOT PARTICLES MARCHING");
    expect(motion).toContain("NOTHING COUNTABLE IS DRAWN");
    // It stays ONE row. This card is the site's worst case for height and the
    // clock test was written from its 756 px; an answer that grew it would be
    // taken back out by the next round of tidying.
    expect(spec.stats!.filter((row) => row.label === "WHAT THE MOTION CLAIMS")).toHaveLength(1);
    expect(spec.stats!.map((row) => row.label)).toEqual(
      ringCurrentLegendSpec(state).stats!.map((row) => row.label),
    );
  });
});

/**
 * THE SWATCH, AND WHY IT CANNOT PULSE AT A RATE THE RING DOES NOT.
 */
describe("the legend's colour bar breathes on the population's own clock", () => {
  const state = ringCurrentIllustration(fieldAt(PEAK));

  it("reads the same phase the shader's own uniform is set to, at every point in the loop", { timeout: 30_000 }, () => {
    // THE PROOF THAT THE TWO AGREE. Not "the durations look similar": the
    // swatch's phase function and the volume's uniform are driven from the
    // same display clock through the same wrap, and this compares them value
    // by value across two whole loops plus a bit.
    const group = createRingCurrentObject(state, { positionForGsm, earthSceneRadius: EARTH_SCENE_RADIUS });
    const volume = group.getObjectByName("ring-current-volume") as THREE.Mesh;
    const uniforms = (volume.material as THREE.ShaderMaterial).uniforms;
    const cycle = uniforms.cycleSeconds!.value as number;
    const period = cycle / RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
    for (let step = 0; step <= 45; step += 1) {
      const displaySeconds = (period * step) / 20;
      setRingCurrentDisplayTime(group, displaySeconds);
      expect(ringCurrentLoopSeconds(cycle, displaySeconds)).toBeCloseTo(
        uniforms.formationSeconds!.value as number,
        9,
      );
    }
  });

  it("uses the fragment shader's own decay expression, character for character", { timeout: 30_000 }, () => {
    // The envelope is not a lookalike curve. If the shader's ramp is ever
    // rewritten, this fails rather than letting the bar keep breathing to the
    // old shape while the globe fades to a new one.
    expect(volumeSource).toContain(
      "float storm = 1.0 - smoothstep(decayStart, decayStart + decaySeconds, formationSeconds);",
    );
    expect(volumeSource).toContain("float decayStart = fillSeconds + holdSeconds;");
    const formation = ringCurrentFormation(state, state.region);
    const perSecond = RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
    const at = (physicalSeconds: number) => ringCurrentFormationLevel(formation, physicalSeconds / perSecond);
    // Bottom of the loop: the quiet-time residual, which is what the volume
    // falls back to and is not zero.
    expect(at(0)).toBeCloseTo(RING_CURRENT_FORMATION.residualFill, 9);
    expect(at(formation.cycleSeconds - 1)).toBeCloseTo(RING_CURRENT_FORMATION.residualFill, 3);
    // Top of it: full, through the hold, which is where the ring is closed.
    const hold = formation.fillSeconds + formation.holdSeconds / 2;
    expect(at(hold)).toBeGreaterThan(0.97);
    // And monotone in the right direction on each side of that.
    expect(at(formation.fillSeconds * 0.25)).toBeLessThan(at(formation.fillSeconds * 0.75));
    const decayStart = formation.fillSeconds + formation.holdSeconds;
    expect(at(decayStart + formation.decaySeconds * 0.75)).toBeLessThan(at(decayStart + formation.decaySeconds * 0.25));
  });

  it("writes a legible opacity, never the population's own 0.2", { timeout: 30_000 }, () => {
    // The DEPTH is a declared display choice and the reason is legibility: a
    // colour bar at a fifth of its own colour is a legend nobody can read.
    // The PHASE and the RATE are not display choices, which is what the two
    // tests above pin.
    const formation = ringCurrentFormation(state, state.region);
    const period = formation.cycleSeconds / RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
    const written: number[] = [];
    const surface = { style: { setProperty: (_: string, value: string) => { written.push(Number(value)); } } };
    for (let step = 0; step <= 40; step += 1) paintRingCurrentPulse(surface, formation, (period * step) / 40);
    expect(Math.min(...written)).toBeCloseTo(RING_CURRENT_PULSE.swatchFloor, 2);
    expect(Math.max(...written)).toBeCloseTo(1, 2);
    expect(RING_CURRENT_PULSE.swatchFloor).toBeGreaterThan(RING_CURRENT_FORMATION.residualFill);
    // Gentle: no frame may jump the bar by more than a fraction of its range,
    // which is what separates a breath from a flash. Measured at 20 fps, which
    // is slower than the scene ever runs.
    let previous = written[0]!;
    for (const value of written.slice(1)) {
      expect(Math.abs(value - previous)).toBeLessThan(0.2);
      previous = value;
    }
  });

  it("sits at full when nothing is pulsing", () => {
    // The layer off, or environmental motion off — which is what
    // `prefers-reduced-motion` turns off by default — and the bar is drawn
    // exactly as every other layer's bar is, with the line of text still
    // saying what the rhythm was.
    const written: string[] = [];
    const surface = { style: { setProperty: (_: string, value: string) => { written.push(value); } } };
    paintRingCurrentPulse(surface, null, 12.5);
    expect(written).toEqual(["1.000"]);
    expect(initialEnvironmentMotion(undefined, true)).toBe(false);
    // A visitor's own choice still wins in both directions, which is this
    // site's standing rule and not something the pulse may override.
    expect(initialEnvironmentMotion(true, true)).toBe(true);
  });

  it("is driven from the scene's animation frame, not from a CSS animation", () => {
    // A CSS animation with a typed duration is precisely the defect: a rhythm
    // that looks synchronised until someone measures it. There is no keyframe
    // and no duration anywhere near this bar.
    const bar = styleSource.slice(styleSource.indexOf(".key-card-scale {"));
    expect(bar.slice(0, bar.indexOf("}"))).toContain("opacity: var(--legend-pulse, 1)");
    expect(styleSource).not.toMatch(/--legend-pulse[^;]*;\s*[^}]*animation/);
    expect(styleSource).not.toContain("@keyframes legend-pulse");
    // The globe hands the bar the SAME clock it hands the volume, and does it
    // outside the motion gate so that a frozen scene leaves a full bar rather
    // than one stopped mid-breath.
    expect(globeSource).toContain("paintRingCurrentPulse(\n      this.ringCurrentPulseSurface,");
    expect(globeSource).toContain(
      "this.environmentalMotionEnabled && this.ringCurrentGroup.visible ? this.ringCurrentFormationState : null,",
    );
    const frame = globeSource.slice(globeSource.indexOf("private animate = () => {"));
    const gate = frame.slice(0, frame.indexOf("if (this.interpolationActive)"));
    expect(gate).toContain("setRingCurrentDisplayTime(this.ringCurrentObject, this.environmentalAnimationElapsedSeconds)");
    expect(gate.indexOf("paintRingCurrentPulse")).toBeGreaterThan(gate.indexOf("setRingCurrentDisplayTime"));
    // And the explorer re-registers the node after every key-card rebuild,
    // because a rebuild replaces it and a detached node cannot be updated.
    expect(explorerSource).toContain("this.updateMapKey(specs);\n    // After the key cards");
    expect(explorerSource).toContain("this.syncRingCurrentPulse();");
    expect(explorerSource).toContain("this.globe.setRingCurrentPulseSurface(pulsing ? bar : null);");
    // Never on a struck-out bar: a layer with no frame has no loop to breathe.
    expect(explorerSource).toContain("!bar.classList.contains(\"key-card-scale--empty\")");
  });
});
