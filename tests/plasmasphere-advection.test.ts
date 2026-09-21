import * as THREE from "three";
import { describe, expect, it } from "vitest";

import globeSource from "../src/globe.ts?raw";
import fixture from "./data/plasmasphere-dgcpm-2026-08-08.json";
import {
  dgcpmLegendSpec,
  initialEnvironmentMotion,
  plasmasphereLegendSpec,
  plasmasphereMotionNote,
} from "../src/main";
import {
  type DgcpmBundle,
  type PlasmasphereDensityField,
  PLASMASPHERE_COROTATION,
  PLASMASPHERE_COROTATION_SPEEDUP,
  advectedGrainPosition,
  advectedMltHours,
  createPlasmasphereDensityTexture,
  createPlasmasphereFieldGeometry,
  createPlasmasphereFieldObject,
  decodeDgcpmSequence,
  dgcpmFieldAt,
  plasmasphereAdvectionRadians,
  plasmasphereFieldAt,
  samplePlasmasphereLogDensity,
  setPlasmasphereDisplayTime,
} from "../src/inner-magnetosphere";
import { radiationBeltDisplayRadius } from "../src/radiation-belt";

/**
 * The plasmasphere's grains stream; its envelope does not.
 *
 * The layer drew a fixed cloud of density samples, and the site's owner read
 * exactly that off the screen: "since the dots of the plasmasphere don't
 * change, it makes it look like a static thing." The physics he was given, and
 * which this file pins:
 *
 * - The drawn PATTERN (dusk bulge, drainage plume) is SUN-FIXED. It is the
 *   shape of the drift geometry and the drift geometry is set by where the Sun
 *   is; Earth turns underneath it.
 * - The cold plasma MATERIAL corotates with Earth, flowing THROUGH that
 *   standing shape.
 *
 * So three things have to be true at once, and each has a test here: grains
 * move eastward with Earth, the density envelope they move through is exactly
 * the one that was there before and does not move with them, and the whole
 * thing stops when a visitor asks for no environmental motion.
 */

const EARTH_SCENE_RADIUS = 100;
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.max(0.001, Math.hypot(xRe, yRe, zRe));
  const scale = radiationBeltDisplayRadius(radius, EARTH_SCENE_RADIUS) / radius;
  return new THREE.Vector3(xRe, zRe, -yRe).multiplyScalar(scale);
};

const bundle = fixture as unknown as DgcpmBundle;
const sequence = decodeDgcpmSequence(bundle);
const simulated = dgcpmFieldAt(sequence, new Date("2026-08-08T18:00:00Z"))!;

/** A storm day of Dst, so the empirical fallback has a boundary to place. */
const empiricalSeries = Array.from({ length: 48 }, (_, index) => ({
  at: new Date(Date.parse("2026-08-08T23:00:00Z") - (47 - index) * 3_600_000).toISOString(),
  dstNt: index < 24 ? 4 : -12 - index,
}));
const empirical = plasmasphereFieldAt(empiricalSeries, new Date("2026-08-08T23:00:00Z"))!;

const models: [string, PlasmasphereDensityField][] = [
  ["the DGCPM simulation", simulated],
  ["the Carpenter & Anderson fallback", empirical],
];

// ---------------------------------------------------------------------------
// The direction of the flow, against the physics rather than against the sign
// that was easier to write
// ---------------------------------------------------------------------------

describe("the grains flow the way corotating plasma flows", () => {
  it("carries a parcel toward LATER magnetic local time, because that is what corotation is", () => {
    // A point on the ground reads its own clock forward: noon, then afternoon,
    // then dusk, then midnight, then dawn. Plasma corotating with the Earth
    // does the same thing in the sun-fixed frame, so MLT increases. This is
    // also the pipeline's convention, whose docstring reads "phi is measured
    // from midnight and increases eastward (toward dawn)" — midnight 0 h to
    // dawn 6 h is the same statement.
    const quarterTurn = Math.PI / 2;
    expect(advectedMltHours(12, quarterTurn)).toBeCloseTo(18, 10); // noon -> dusk
    expect(advectedMltHours(18, quarterTurn)).toBeCloseTo(0, 10);  // dusk -> midnight
    expect(advectedMltHours(0, quarterTurn)).toBeCloseTo(6, 10);   // midnight -> dawn
  });

  it("moves a drawn grain from noon toward the DUSK side of the scene", () => {
    // GSM +x is noon and GSM +y is dusk. A quarter turn of corotation must
    // take a grain drawn at noon to exactly where a grain at dusk on the same
    // shell is drawn — which pins the rotation's sign, its axis, and the claim
    // that rotating the DRAWN point is the same as drawing the rotated point.
    const noon = positionForGsm(4, 0, 0);
    const dusk = positionForGsm(0, 4, 0);
    const moved = advectedGrainPosition(noon, Math.PI / 2);
    expect(moved.x).toBeCloseTo(dusk.x, 6);
    expect(moved.y).toBeCloseTo(dusk.y, 6);
    expect(moved.z).toBeCloseTo(dusk.z, 6);
    // And it is dusk, not dawn: dusk is GSM +y, which the scene draws at -z.
    expect(moved.z).toBeLessThan(-1);
  });

  it("is a rotation, so it preserves radius exactly and touches no radial mapping", () => {
    // The whole reason the advection can live in the vertex shader without
    // knowing anything about the ruler: the scene's radial map depends only on
    // |r|, and a rotation does not change |r|. A distance-scale change
    // elsewhere in the scene therefore cannot desynchronise this.
    const point = positionForGsm(5.5, -2.1, 1.3);
    const before = Math.hypot(point.x, point.y, point.z);
    for (const radians of [0.3, 1.9, 4.4, 12.7]) {
      const moved = advectedGrainPosition(point, radians);
      expect(Math.hypot(moved.x, moved.y, moved.z)).toBeCloseTo(before, 9);
      expect(moved.y).toBe(point.y); // out of the equatorial plane: unchanged
    }
  });

  it("runs at the stated display cadence and nowhere near real time", () => {
    const revolution = PLASMASPHERE_COROTATION.displaySecondsPerRevolution;
    expect(plasmasphereAdvectionRadians(revolution)).toBeCloseTo(2 * Math.PI, 12);
    expect(plasmasphereAdvectionRadians(0)).toBe(0);
    // The quoted speed-up is the real ratio, not a number typed into prose.
    const exact = PLASMASPHERE_COROTATION.siderealRotationSeconds / revolution;
    expect(Math.abs(PLASMASPHERE_COROTATION_SPEEDUP - exact) / exact).toBeLessThan(0.02);
    // A day of corotation really is invisible at 1x: pinning that keeps anyone
    // from "fixing" the cadence back to real time and shipping a still image.
    expect(exact).toBeGreaterThan(1000);
  });
});

// ---------------------------------------------------------------------------
// The envelope is invariant: the shape stays put while the grains cross it
// ---------------------------------------------------------------------------

describe.each(models)("the density envelope of %s does not move with the grains", (_name, field) => {
  const sampled = createPlasmasphereDensityTexture(field);

  it("draws the model's own density at every point of the sun-fixed frame", () => {
    // The texture the shader reads IS the field. For the published simulation
    // it is literally the published grid; for the analytic profile it is that
    // profile sampled finely enough that interpolating it is not an
    // approximation of anything the model says.
    const [inner, outer] = field.validLRange;
    let worst = 0;
    for (let index = 0; index < 400; index += 1) {
      const lRe = inner + ((outer - inner) * ((index * 37) % 400)) / 400;
      const mlt = ((index * 11) % 96) * 0.25;
      const model = field.densityAt(lRe, mlt);
      if (model === null || model <= 0) continue;
      worst = Math.max(worst, Math.abs(samplePlasmasphereLogDensity(sampled, lRe, mlt) - Math.log10(model)));
    }
    // 0.02 in log10 is 5% in density — far below the ramp's own resolution and
    // dominated by the plasmapause knee, where the field falls a decade in a
    // tenth of an L.
    expect(worst).toBeLessThan(0.02);
  });

  it("keeps the fixed probe reading the same density however far the grains have travelled", () => {
    // THE test for "the shape must not move". Watch a fixed point of the sun
    // frame and ask what the grains passing through it are drawn at. The
    // answer has to be the model's value there, at every display time.
    const probeL = (field.validLRange[0] + field.validLRange[1]) / 2;
    for (const probeMlt of [0, 6, 12, 18]) {
      const model = Math.log10(field.densityAt(probeL, probeMlt)!);
      for (const radians of [0, Math.PI / 3, Math.PI, (5 * Math.PI) / 3, 9.4]) {
        // What a grain that has drifted INTO the probe is drawn at: it was
        // born that much earlier in local time, and it reads the field where
        // it has arrived.
        const born = advectedMltHours(probeMlt, -radians);
        const drawn = samplePlasmasphereLogDensity(sampled, probeL, advectedMltHours(born, radians));
        expect(drawn).toBeCloseTo(model, 2);
      }
    }
  });

  it("never crowds grains together or spreads them apart, at any elapsed time", () => {
    // The layer's construction depends on grain density being FLAT so that
    // brightness carries the physics and nothing else. A sheared angular flow
    // — which is what including the Volland-Stern convection drift in the
    // grain motion would give — piles grains up wherever it slows and empties
    // wherever it speeds up, permanently so at a stagnation point, and would
    // grow a bright dusk clump that is not in the density field.
    //
    // Rigid corotation cannot do that, and this measures it exactly rather
    // than asserting it: the spacings between neighbouring grains around the
    // circle are the same multiset before and after, so the sample is moved,
    // never stretched.
    const geometry = createPlasmasphereFieldGeometry(field, { positionForGsm, sampleCount: 20_000 });
    const mlt = geometry.getAttribute("mltHours");
    const gapsAt = (radians: number) => {
      const hours = Array.from({ length: mlt.count }, (_, index) => advectedMltHours(mlt.getX(index), radians));
      hours.sort((a, b) => a - b);
      const gaps = hours.map((value, index) => (index === 0 ? value + 24 - hours[hours.length - 1]! : value - hours[index - 1]!));
      gaps.sort((a, b) => a - b);
      return gaps;
    };
    const rest = gapsAt(0);
    for (const radians of [Math.PI / 3, Math.PI, 5.0, 31.4]) {
      const moved = gapsAt(radians);
      expect(moved.length).toBe(rest.length);
      let worst = 0;
      for (let index = 0; index < rest.length; index += 1) {
        worst = Math.max(worst, Math.abs(moved[index]! - rest[index]!));
      }
      expect(worst).toBeLessThan(1e-4);
    }
  });
});

// ---------------------------------------------------------------------------
// A grain tracks the density where it IS
// ---------------------------------------------------------------------------

describe.each(models)("a grain of %s reads the field at its current position", (_name, field) => {
  const sampled = createPlasmasphereDensityTexture(field);
  const geometry = createPlasmasphereFieldGeometry(field, { positionForGsm, sampleCount: 20_000 });

  it("is drawn at its birth density when the display clock reads zero", () => {
    // The baked `logDensity` attribute is what a dozen existing tests read as
    // "what is drawn". The shader no longer reads it — a moving grain reads
    // the texture — so this is what keeps those tests true.
    const baked = geometry.getAttribute("logDensity");
    const shells = geometry.getAttribute("shellL");
    const mlt = geometry.getAttribute("mltHours");
    let worst = 0;
    for (let index = 0; index < baked.count; index += 7) {
      const drawn = samplePlasmasphereLogDensity(sampled, shells.getX(index), mlt.getX(index));
      worst = Math.max(worst, Math.abs(drawn - baked.getX(index)));
    }
    expect(worst).toBeLessThan(0.02);
  });

  it("brightens and dims as it is carried through the shape", () => {
    const shells = geometry.getAttribute("shellL");
    const mlt = geometry.getAttribute("mltHours");
    let worst = 0;
    let moved = 0;
    for (let index = 0; index < shells.count; index += 11) {
      for (const radians of [0.7, 2.6, 5.9]) {
        const nowAt = advectedMltHours(mlt.getX(index), radians);
        const model = field.densityAt(shells.getX(index), nowAt);
        if (model === null || model <= 0) continue;
        const drawn = samplePlasmasphereLogDensity(sampled, shells.getX(index), nowAt);
        worst = Math.max(worst, Math.abs(drawn - Math.log10(model)));
        if (Math.abs(drawn - shells.getX(index)) > 0) moved += 1;
      }
    }
    expect(moved).toBeGreaterThan(0);
    expect(worst).toBeLessThan(0.02);
  });

  it("changes what SOME grain is drawn at as the display clock runs — the layer is not static", () => {
    // The complaint, as a number. Fixed grains would give a zero here.
    const shells = geometry.getAttribute("shellL");
    const mlt = geometry.getAttribute("mltHours");
    let changed = 0;
    for (let index = 0; index < shells.count; index += 1) {
      const before = samplePlasmasphereLogDensity(sampled, shells.getX(index), mlt.getX(index));
      const after = samplePlasmasphereLogDensity(
        sampled,
        shells.getX(index),
        advectedMltHours(mlt.getX(index), Math.PI / 2),
      );
      if (Math.abs(after - before) > 0.05) changed += 1;
    }
    // The empirical profile is axisymmetric inside the plasmapause, so its
    // interior grains genuinely do not change brightness; only the trough and
    // the knee width carry local time there. The simulation changes far more.
    // Either way the layer must not be uniformly frozen.
    expect(changed).toBeGreaterThan(200);
  });
});

// ---------------------------------------------------------------------------
// The drawn object, and stopping it
// ---------------------------------------------------------------------------

describe("the drawn stipple advances only with the environmental-motion clock", () => {
  it("turns the display clock into the rotation the shader applies", () => {
    const points = createPlasmasphereFieldObject(simulated, { positionForGsm, sampleCount: 2_000 });
    const material = points.material as THREE.ShaderMaterial;
    expect(material.uniforms.advectionRadians!.value).toBe(0);
    setPlasmasphereDisplayTime(points, PLASMASPHERE_COROTATION.displaySecondsPerRevolution / 4);
    expect(material.uniforms.advectionRadians!.value).toBeCloseTo(Math.PI / 2, 9);
    expect((material.uniforms.advectionCosSin!.value as THREE.Vector2).x).toBeCloseTo(0, 9);
    expect((material.uniforms.advectionCosSin!.value as THREE.Vector2).y).toBeCloseTo(1, 9);
    expect(material.uniforms.advectionMltHours!.value).toBeCloseTo(6, 9);
    points.geometry.dispose();
    material.dispose();
  });

  it("freezes where it is when the clock stops advancing, and does not reset", () => {
    // "Environmental motion" off does not zero the clock; the scene simply
    // stops adding to it. So calling with the same accumulated value again —
    // which is exactly what every subsequent frame does — must not move a
    // single grain.
    const points = createPlasmasphereFieldObject(simulated, { positionForGsm, sampleCount: 2_000 });
    const material = points.material as THREE.ShaderMaterial;
    setPlasmasphereDisplayTime(points, 31.5);
    const frozen = (material.uniforms.advectionCosSin!.value as THREE.Vector2).clone();
    const frozenMlt = material.uniforms.advectionMltHours!.value;
    for (let frame = 0; frame < 30; frame += 1) setPlasmasphereDisplayTime(points, 31.5);
    expect((material.uniforms.advectionCosSin!.value as THREE.Vector2).equals(frozen)).toBe(true);
    expect(material.uniforms.advectionMltHours!.value).toBe(frozenMlt);
    // ...and it is a real, non-zero position, not the origin of the motion.
    expect(frozenMlt).toBeGreaterThan(0);
    points.geometry.dispose();
    material.dispose();
  });

  it("is driven from inside the scene's environmental-motion gate", () => {
    // A behaviour test cannot reach the render loop without WebGL, so this
    // reads the loop's own structure: the call must sit INSIDE the
    // `if (this.environmentalMotionEnabled)` block, alongside every other flow
    // glyph, because that block's accumulator is what freezes. Moving the call
    // one line below the closing brace would keep the grains running with the
    // setting off, and would fail here.
    const opening = globeSource.indexOf("if (this.environmentalMotionEnabled) {");
    expect(opening).toBeGreaterThan(0);
    let depth = 0;
    let end = opening;
    for (let index = globeSource.indexOf("{", opening); index < globeSource.length; index += 1) {
      const character = globeSource[index];
      if (character === "{") depth += 1;
      else if (character === "}") {
        depth -= 1;
        if (depth === 0) { end = index; break; }
      }
    }
    const gated = globeSource.slice(opening, end);
    expect(gated).toContain("setPlasmasphereDisplayTime(this.plasmasphereObject");
    expect(gated).toContain("this.environmentalAnimationElapsedSeconds += delta;");
    // And nothing outside the gate advances it: the only other call is the
    // one that re-applies the accumulated angle to a freshly rebuilt stipple.
    const calls = globeSource.split("setPlasmasphereDisplayTime(").length - 1;
    expect(calls).toBe(2); // the rebuild and the gated frame call (the import has no paren)
  });

  it("keeps a rebuilt stipple at the angle the old one had reached", () => {
    // Stepping to the next published frame rebuilds 130,000 grains. If the new
    // stipple started at zero the whole cloud would snap back to noon every
    // two model hours, which would read as a glitch rather than as flow.
    expect(globeSource).toContain("setPlasmasphereDisplayTime(points, this.environmentalAnimationElapsedSeconds)");
  });
});

// ---------------------------------------------------------------------------
// Saying so
// ---------------------------------------------------------------------------

describe("the card says what the motion is", () => {
  it("states the display cadence, the sun-fixed shape and how to stop it", () => {
    const note = plasmasphereMotionNote(7.24);
    expect(note).toContain("THE GRAINS MOVE; THE SHAPE DOES NOT");
    expect(note).toContain(`one drawn revolution every ${PLASMASPHERE_COROTATION.displaySecondsPerRevolution} seconds`);
    expect(note).toContain("× real time");
    expect(note).toContain("Environmental motion");
    // The part of the drift that is NOT drawn is named, with the frame's own
    // number for how big it is.
    expect(note).toContain("Volland-Stern convection");
    expect(note).toContain("L 7.24");
  });

  it("does not claim a convection field the empirical profile does not have", () => {
    const note = plasmasphereMotionNote(null);
    expect(note).not.toContain("Volland-Stern");
    expect(note).toContain("axisymmetric");
    expect(note).toContain("subtle");
  });

  it("reaches both layer cards, whichever model is driving", () => {
    const simulatedCard = dgcpmLegendSpec(simulated);
    expect(simulatedCard.note).toContain("THE GRAINS MOVE; THE SHAPE DOES NOT");
    expect(simulatedCard.stats?.some((stat) => stat.label === "GRAIN MOTION")).toBe(true);
    const empiricalCard = plasmasphereLegendSpec(empirical);
    expect(empiricalCard.note).toContain("THE GRAINS MOVE; THE SHAPE DOES NOT");
    expect(empiricalCard.stats?.some((stat) => stat.label === "GRAIN MOTION")).toBe(true);
  });
});

describe("a visitor who has asked for less motion gets less motion", () => {
  it("defaults environmental motion off under prefers-reduced-motion, and never overrides a choice", () => {
    expect(initialEnvironmentMotion(undefined, false)).toBe(true);
    expect(initialEnvironmentMotion(undefined, true)).toBe(false);
    // A stored choice is a choice, in both directions.
    expect(initialEnvironmentMotion(true, true)).toBe(true);
    expect(initialEnvironmentMotion(false, false)).toBe(false);
  });
});
