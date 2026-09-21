import * as THREE from "three";
import { describe, expect, it } from "vitest";
import { sharedDisplayRadius } from "../src/radial-ruler";
import {
  FRONT_TRAVEL_MINUTES,
  HALF_THICKNESS_QUIET_RE,
  HALF_THICKNESS_THICK_RE,
  HALF_THICKNESS_THIN_RE,
  INNER_EDGE_INJECTED_RE,
  INNER_EDGE_LOADED_RE,
  INNER_EDGE_QUIET_RE,
  OUTER_EDGE_RE,
  createInnerPlasmaSheetGeometry,
  dipolarisationFrontRe,
  halfThicknessRe,
  innerEdgeRe,
  sheetCentreZRe,
  MLT_HALF_SPAN_HOURS,
} from "../src/inner-plasma-sheet";
import { shueBoundary, shueRadiusRe } from "../src/magnetopause";
import type { SubstormState } from "../src/substorm-chain";

/**
 * The scene's own mapper at `earthSceneRadius = 1`, so every number here is in
 * DRAWN EARTH RADII and can be turned into pixels by one multiplication.
 */
const positionForGsm = (xRe: number, yRe: number, zRe: number) => {
  const radius = Math.hypot(xRe, yRe, zRe);
  const drawn = sharedDisplayRadius(radius, 1);
  const scale = radius > 0 ? drawn / radius : 0;
  return new THREE.Vector3(xRe * scale, yRe * scale, zRe * scale);
};

/**
 * The globe's drawn radius in CSS pixels, measured off the shipped build at
 * 1440x900 with the ring-current layer on: 46 px. Every pixel figure below is
 * against that, and the whole point of this file is that those figures are
 * large enough to see.
 */
const GLOBE_PX_1440 = 46;
/**
 * The same measurement on the 390-wide phone layout: 40 px. Larger than a
 * naive scaling would suggest, because the phone layout gives the globe most of
 * the viewport instead of sharing it with a rail.
 */
const GLOBE_PX_390 = 40;

function state(loading: number, injection: number, minutesSinceOnset: number | null): SubstormState {
  return {
    phase: injection > 0 ? "expansion" : loading > 0.35 ? "growth" : "quiet",
    loading,
    injection,
    onset: minutesSinceOnset === null
      ? null
      : { atMs: 0, indexNt: -50, dropNt: 800, minimumNt: -900, minimumAtMs: 0 },
    minutesSinceOnset,
    onsetEvidence: minutesSinceOnset === null ? "none" : "observed-electrojet",
    southwardBzNtMinutes: loading * 450,
    bzGsmNt: -5,
  };
}

const drawnRe = (radiusRe: number) => sharedDisplayRadius(radiusRe, 1);

describe("the inner plasma sheet is legible at the scale it actually ships at", () => {
  it("occupies enough of the frame to see, at 1440 and at 390", () => {
    // This is the gate. The plasmasphere had to be pulled off the globe because
    // at L 2-5 it came out as a 26 px annulus whose whole 48-hour plasmapause
    // motion was 5 px. The inner sheet sits in the ruler's LINEAR band, where
    // the gain is 0.332 rather than the log branch's 0.092, and it is a
    // physically enormous object. These are the numbers that justify shipping
    // it where the plasmasphere could not be.
    const quietSpan = (drawnRe(OUTER_EDGE_RE) - drawnRe(INNER_EDGE_QUIET_RE));
    const injectedSpan = (drawnRe(OUTER_EDGE_RE) - drawnRe(INNER_EDGE_INJECTED_RE));
    expect(quietSpan * GLOBE_PX_1440).toBeGreaterThan(30);
    expect(injectedSpan * GLOBE_PX_1440).toBeGreaterThan(90);
    // And on a phone, where everything is smaller and the bar is lower.
    expect(injectedSpan * GLOBE_PX_390).toBeGreaterThan(50);
  });

  it("MOVES enough to see — a layer that is visible but static fails the same way", () => {
    // The second half of the gate, and the one a merely-visible layer flunks.
    const loadedEdge = drawnRe(innerEdgeRe(state(1, 0, null)));
    const injectedEdge = drawnRe(innerEdgeRe(state(1, 1, 4)));
    const travelPx = (loadedEdge - injectedEdge) * GLOBE_PX_1440;
    expect(travelPx).toBeGreaterThan(25);
    expect((loadedEdge - injectedEdge) * GLOBE_PX_390).toBeGreaterThan(14);

    // Quiet to injected is the full sweep.
    const fullPx = (drawnRe(INNER_EDGE_QUIET_RE) - drawnRe(INNER_EDGE_INJECTED_RE)) * GLOBE_PX_1440;
    expect(fullPx).toBeGreaterThan(50);

    // Thickness moves too, and transverse magnification at 10 Re is the same
    // 0.332 the radial gain is, because the ruler is a pure radial map.
    const transverse = drawnRe(10) / 10;
    const thinPx = halfThicknessRe(state(1, 0, null)) * transverse * GLOBE_PX_1440;
    const thickPx = halfThicknessRe(state(1, 1, 4)) * transverse * GLOBE_PX_1440;
    expect(thickPx - thinPx).toBeGreaterThan(15);
  });
});

describe("which way the sheet moves, which is the part that is easy to get backwards", () => {
  it("brings the inner edge EARTHWARD as the tail loads, and much further at injection", () => {
    // Enhanced convection during a growth phase transports plasma sunward, so
    // the measured inner edge comes IN. The first version of this module had it
    // retreating, which is backwards, and the A/B against real Bz is what
    // showed it.
    expect(innerEdgeRe(state(0, 0, null))).toBeCloseTo(INNER_EDGE_QUIET_RE, 6);
    expect(innerEdgeRe(state(1, 0, null))).toBeCloseTo(INNER_EDGE_LOADED_RE, 6);
    expect(innerEdgeRe(state(1, 1, 4))).toBeCloseTo(INNER_EDGE_INJECTED_RE, 6);
    expect(innerEdgeRe(state(1, 0, null))).toBeLessThan(innerEdgeRe(state(0, 0, null)));
    expect(innerEdgeRe(state(1, 1, 4))).toBeLessThan(innerEdgeRe(state(1, 0, null)));
  });

  it("THINS the sheet while the tail loads, and thickens it at onset", () => {
    // The counter-intuitive half: loading a tail makes its current sheet
    // thinner, and that thinning is what ends in reconnection.
    expect(halfThicknessRe(state(0, 0, null))).toBeCloseTo(HALF_THICKNESS_QUIET_RE, 6);
    expect(halfThicknessRe(state(1, 0, null))).toBeCloseTo(HALF_THICKNESS_THIN_RE, 6);
    expect(halfThicknessRe(state(1, 1, 4))).toBeCloseTo(HALF_THICKNESS_THICK_RE, 6);
    expect(halfThicknessRe(state(1, 0, null))).toBeLessThan(halfThicknessRe(state(0, 0, null)));
  });
});

describe("what is measured, what is drawn, and what is refused", () => {
  it("puts the sheet centre off the GSM equator by the dipole tilt, hinged", () => {
    // The magnetic equator plane is x sin(psi) + z cos(psi) = 0, so at
    // x = -10 Re under a 20 degree tilt the centre sits 3.64 Re ABOVE z = 0 —
    // which is why an equatorial cut through this region so often shows the
    // lobe rather than the sheet, and it corroborates NOAA's own solution
    // putting it about 3 Re up.
    const tilt = (20 * Math.PI) / 180;
    expect(sheetCentreZRe(-10, tilt)).toBeCloseTo(10 * Math.tan(tilt), 6);
    expect(sheetCentreZRe(-10, tilt)).toBeCloseTo(3.64, 2);
    // Hinged: it does not run away down the tail.
    expect(sheetCentreZRe(-40, tilt)).toBeCloseTo(sheetCentreZRe(-10, tilt), 6);
    // No tilt, no offset.
    expect(sheetCentreZRe(-10, 0)).toBe(0);
  });

  it("draws no dipolarisation front when no measured onset says there is one", () => {
    // The live case. There is no auroral-electrojet index in any feed this site
    // fetches, so the layer must not draw a snap.
    expect(dipolarisationFrontRe(state(1, 0, null))).toBeNull();
    const noEvidence = { ...state(1, 0.9, 2), onsetEvidence: "none" as const };
    expect(dipolarisationFrontRe(noEvidence)).toBeNull();

    // With a measured onset it travels earthward and then stops existing.
    const early = dipolarisationFrontRe(state(1, 0.5, 1))!;
    const late = dipolarisationFrontRe(state(1, 1, FRONT_TRAVEL_MINUTES - 0.5))!;
    expect(early).toBeGreaterThan(late);
    expect(early).toBeLessThanOrEqual(OUTER_EDGE_RE + 1e-9);
    expect(dipolarisationFrontRe(state(1, 1, FRONT_TRAVEL_MINUTES + 1))).toBeNull();
  });

  it("labels every dimension it draws as empirical, and names what is measured", () => {
    const geometry = createInnerPlasmaSheetGeometry({ positionForGsm }, {
      state: state(1, 0, null),
      dipoleTiltRad: 0.3,
      frontRe: null,
    });
    expect(geometry.userData.evidence).toBe("empirical");
    expect(String(geometry.userData.notMeasured)).toContain("inner edge");
    expect(String(geometry.userData.measured)).toContain("Bz");
    // Colour carries an alpha channel: without it the wedge ends in a straight
    // chord across the sky, which reads as a rendering fault.
    expect(geometry.getAttribute("color").itemSize).toBe(4);
    geometry.dispose();
  });

  it("keeps every vertex outside the Earth and inside the drawn window", () => {
    const geometry = createInnerPlasmaSheetGeometry({ positionForGsm }, {
      state: state(0, 1, 3),
      dipoleTiltRad: (25 * Math.PI) / 180,
      frontRe: 9,
    });
    const position = geometry.getAttribute("position");
    let minimum = Infinity;
    let maximum = 0;
    for (let index = 0; index < position.count; index += 1) {
      const radius = Math.hypot(position.getX(index), position.getY(index), position.getZ(index));
      minimum = Math.min(minimum, radius);
      maximum = Math.max(maximum, radius);
    }
    // Nothing inside the globe, and nothing past the far tail this layer
    // deliberately does not draw.
    expect(minimum).toBeGreaterThan(drawnRe(2));
    expect(maximum).toBeLessThan(drawnRe(OUTER_EDGE_RE + 4));
    geometry.dispose();
  });

  /**
   * THE ONE THAT SHIPPED BROKEN, and the reason this file now knows about the
   * magnetopause at all.
   *
   * The layer went out on 2026-08-20 spanning eight hours of local time either
   * side of midnight. Sean, looking at it: *"the white ring around the ring
   * current that is supposed to be the plasma sheet - it obviously isn't drawn
   * correctly."* Two thirds of the way around the Earth is not a tail
   * structure, and the far corner of that span was not merely inelegant - at
   * 60 degrees from the Sun-Earth line, drawn out to 14 Rₑ, it was OUTSIDE the
   * magnetopause for every driver state this site has measured. There is no
   * plasma sheet on the dayside; there is magnetosheath.
   *
   * So the check is geometric and it is against the boundary rather than
   * against a number somebody liked: every vertex, in the most extended state
   * the layer can draw, must sit inside a Shue (1998) surface evaluated at the
   * most COMPRESSED standoff the published driver envelope has produced here
   * (7.8 Rₑ, from the forecast card on the release this was measured against).
   * If a later change widens the span, or pushes the outer edge out, this goes
   * red before a reader ever sees it.
   */
  it("keeps the whole wedge inside a compressed magnetopause", () => {
    // Nightside only, by construction: four hours either side of midnight puts
    // the flank vertices 120 degrees from the Sun-Earth line.
    expect(MLT_HALF_SPAN_HOURS).toBeLessThanOrEqual(6);
    const geometry = createInnerPlasmaSheetGeometry({ positionForGsm }, {
      // Quiet is the widest the wedge gets: the inner edge sits furthest out
      // and the sheet is at its thickest, so this is the extreme case.
      state: state(0, 0, null),
      dipoleTiltRad: (25 * Math.PI) / 180,
      frontRe: null,
    });
    // In Rₑ, not drawn units, so the comparison is against the physics rather
    // than against the display ruler. Undo the ruler the mapper applied.
    const position = geometry.getAttribute("position");
    // The compressed corner of the driver envelope this site actually measured
    // on the release the defect was found on: 8.99 nPa with Bz −10.22 nT. Taken
    // through the site's own Shue implementation so the standoff and the
    // flaring parameter are a PHYSICAL PAIR - pushing the nose in with a
    // southward Bz also flares the flanks out, and pairing a compressed
    // standoff with a quiet alpha would invent a boundary that cannot occur.
    const compressed = shueBoundary(8.99, -10.22);
    if (!compressed) throw new Error("the compressed corner has to evaluate");
    expect(compressed.subsolarStandoffRe).toBeCloseTo(6.99, 1);
    let worst = 0;
    for (let index = 0; index < position.count; index += 1) {
      const drawn = new THREE.Vector3(position.getX(index), position.getY(index), position.getZ(index));
      const drawnRadius = drawn.length();
      if (drawnRadius === 0) continue;
      // Invert the shared ruler by bisection: it is monotonic in radius.
      let low = 0;
      let high = 200;
      for (let step = 0; step < 60; step += 1) {
        const mid = (low + high) / 2;
        if (sharedDisplayRadius(mid, 1) < drawnRadius) low = mid;
        else high = mid;
      }
      const radiusRe = (low + high) / 2;
      // The scene mapper scales radially, so the DIRECTION survives it intact
      // and the solar zenith angle can be read straight off the drawn vertex.
      const theta = Math.acos(Math.max(-1, Math.min(1, drawn.x / drawnRadius)));
      // Shue is open down-tail and its radius diverges at exactly midnight, so
      // a vertex on the anti-solar axis has no finite boundary to be outside
      // of. Those are the ones furthest from the fault this guards.
      const boundaryRe = shueRadiusRe(theta, compressed.subsolarStandoffRe, compressed.flaringAlpha);
      if (!Number.isFinite(boundaryRe)) continue;
      worst = Math.max(worst, radiusRe / boundaryRe);
    }
    // Strictly inside, with room. The worst vertex measures 0.856 of its own
    // boundary radius - not the 0.77 the flat flank-corner arithmetic gives,
    // because the wedge has thickness and the sheet centre is carried off the
    // GSM equator by the dipole tilt, so the extreme vertex is a corner in z
    // rather than a point in the equatorial plane. 0.9 leaves that headroom and
    // still fails long before anything reaches the boundary.
    expect(worst).toBeLessThan(0.9);
    geometry.dispose();
  });
});
