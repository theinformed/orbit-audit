import { describe, expect, it } from "vitest";
import { footprintPoints } from "../src/orbit";
import { resolveVisibleIndices } from "../src/globe";
import { fleetFactValue, operatorFact } from "../src/main";

function angularSeparationDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (degrees: number) => (degrees * Math.PI) / 180;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const deltaPhi = toRad(lat2 - lat1);
  const deltaLambda = toRad(lon2 - lon1);
  const haversine = Math.sin(deltaPhi / 2) ** 2
    + Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) ** 2;
  return (2 * Math.asin(Math.min(1, Math.sqrt(haversine))) * 180) / Math.PI;
}

/** The footprint boundary is (approximately) a spherical cap around the
 * sub-satellite point; its angular radius is the largest angular distance
 * from center to any boundary sample. */
function footprintAngularExtentDeg(
  latitudeDeg: number,
  longitudeDeg: number,
  altitudeKm: number,
  minimumElevationDeg: number,
): number {
  const boundary = footprintPoints(latitudeDeg, longitudeDeg, altitudeKm, minimumElevationDeg, 96);
  return Math.max(
    ...boundary.map(([pointLongitude, pointLatitude]) =>
      angularSeparationDeg(latitudeDeg, longitudeDeg, pointLatitude, pointLongitude)),
  );
}

describe("footprint minimum-elevation mask geometry", () => {
  it("strictly shrinks the coverage cap as the mask angle rises through 0°/5°/10°", () => {
    const latitudeDeg = 28.5;
    const longitudeDeg = -80.6;
    const altitudeKm = 780;
    const radiusHorizon = footprintAngularExtentDeg(latitudeDeg, longitudeDeg, altitudeKm, 0);
    const radiusFive = footprintAngularExtentDeg(latitudeDeg, longitudeDeg, altitudeKm, 5);
    const radiusTen = footprintAngularExtentDeg(latitudeDeg, longitudeDeg, altitudeKm, 10);
    expect(radiusFive).toBeLessThan(radiusHorizon);
    expect(radiusTen).toBeLessThan(radiusFive);
  });

  it("still returns a well-formed closed boundary at every link-planner mask angle", () => {
    for (const minimumElevationDeg of [0, 5, 10]) {
      const boundary = footprintPoints(51.6, 12.3, 420, minimumElevationDeg, 64);
      expect(boundary.length).toBeGreaterThan(2);
      expect(boundary[0]?.[0]).toBeCloseTo(boundary.at(-1)?.[0] ?? 0, 6);
      expect(boundary[0]?.[1]).toBeCloseTo(boundary.at(-1)?.[1] ?? 0, 6);
    }
  });
});

describe("Solo override on the satellite visibility pipeline", () => {
  it("passes the filtered set through unchanged when Solo is off", () => {
    const filtered = [1, 4, 9, 22];
    const result = resolveVisibleIndices(filtered, 4, false);
    expect([...result].sort((a, b) => a - b)).toEqual([1, 4, 9, 22]);
  });

  it("collapses to only the selected satellite when Solo is on", () => {
    const filtered = [1, 4, 9, 22];
    const result = resolveVisibleIndices(filtered, 9, true);
    expect([...result]).toEqual([9]);
  });

  it("keeps the selected satellite visible even if the filters would exclude it", () => {
    const filtered = [1, 4, 22];
    const result = resolveVisibleIndices(filtered, 9, false);
    expect(result.has(9)).toBe(true);
    expect(result.has(1)).toBe(true);
    expect(result.has(4)).toBe(true);
    expect(result.has(22)).toBe(true);
  });

  it("does nothing when Solo is checked but nothing is selected", () => {
    const filtered = [1, 4, 9];
    const result = resolveVisibleIndices(filtered, null, true);
    expect([...result].sort((a, b) => a - b)).toEqual([1, 4, 9]);
  });

  it("restores exactly the previous filtered state when Solo toggles back off", () => {
    const filtered = [2, 5, 8, 11];
    const soloOn = resolveVisibleIndices(filtered, 5, true);
    const soloOff = resolveVisibleIndices(filtered, 5, false);
    expect([...soloOn]).toEqual([5]);
    expect([...soloOff].sort((a, b) => a - b)).toEqual(filtered);
  });
});

/**
 * ONE OPEN SPACECRAFT, ADDED TO WHATEVER THE FILTERS ALLOW.
 *
 * These six cases were written against `resolveStackVisibility(filtered, stack,
 * active, hideOthers)`, which unioned the filtered set with a LIST of pinned
 * spacecraft and could hide every marker outside that list. Sean retired both
 * on 2026-08-28 - "no multiple satellites selected ... one at a time", and with
 * it the View Selected / View All control that set `hideOthers` - so the
 * wrapper reduced to `resolveVisibleIndices(filtered, active, false)` exactly
 * and was deleted rather than left standing as a second name for the same rule.
 *
 * The behaviour being pinned is unchanged, and is restated here against the
 * function that survives: the open spacecraft is drawn whether or not the
 * filters select it, it is never drawn twice, and nothing is drawn once its
 * card is closed. The one case that could not be restated is "keeps every
 * chosen spacecraft visible, not only the active one" - there is no longer a
 * second chosen spacecraft for it to be about.
 */
describe("the one open spacecraft, against the filtered set", () => {
  it("adds the open spacecraft to the filtered set", () => {
    const visible = resolveVisibleIndices([1, 2, 3], 9, false);
    expect([...visible].sort((a, b) => a - b)).toEqual([1, 2, 3, 9]);
  });

  it("never duplicates an open spacecraft the filters already include", () => {
    const visible = resolveVisibleIndices([1, 2, 3], 2, false);
    expect([...visible].sort((a, b) => a - b)).toEqual([1, 2, 3]);
  });

  it("shows the open spacecraft even when the filters match nothing", () => {
    // This is the state Sean hit: every constellation cleared, so the filtered
    // set is empty and the only marker left is the one he had opened.
    const visible = resolveVisibleIndices([], 12, false);
    expect([...visible]).toEqual([12]);
  });

  it("draws nothing at all once the card is closed", () => {
    const visible = resolveVisibleIndices([], null, false);
    expect(visible.size).toBe(0);
  });

  it("still draws the filtered set when nothing is open", () => {
    const visible = resolveVisibleIndices([3, 6], null, false);
    expect([...visible].sort((a, b) => a - b)).toEqual([3, 6]);
  });
});

// The "naming the facet that emptied the globe" suite lived here while the
// interface blamed the visitor for empty filter combinations. That warning is
// gone — the filters heal themselves instead — and its replacement invariants
// are pinned in tests/catalog-filter-healing.test.ts.

describe("what the satellite card is entitled to assert", () => {
  it("names the fleet when the object has one", () => {
    expect(fleetFactValue("Starlink", "checked")).toBe("Starlink");
  });

  it("asserts the negative only when the build actually checked", () => {
    expect(fleetFactValue(null, "checked")).toBe("No named fleet identified");
  });

  it("reports an unchecked build as an absence, not a finding", () => {
    // Every object in the current release publishes "checked", so this branch
    // is never taken in production data — which is exactly why it is tested
    // directly rather than through a rendered card.
    expect(fleetFactValue(null, "unavailable")).toBe("Fleet data not available in this build");
  });

  it("keeps the fleet name even when the fleet check was unavailable", () => {
    expect(fleetFactValue("GPS", "unavailable")).toBe("GPS");
  });

  it("falls back to the checked wording for a release that predates the field", () => {
    expect(fleetFactValue(null, undefined)).toBe("No named fleet identified");
  });

  it("shows an operator that is genuinely an operator", () => {
    expect(operatorFact("NASA / ESA", "United States")).toBe("NASA / ESA");
    expect(operatorFact("U.S. Space Force", "United States")).toBe("U.S. Space Force");
  });

  it("drops the operator row when it only restates the registry country", () => {
    expect(operatorFact("People's Republic of China", "People's Republic of China")).toBeNull();
    expect(operatorFact("  Japan ", "Japan")).toBeNull();
    expect(operatorFact("SES", "ses")).toBeNull();
  });

  it("drops the operator row when the field is absent", () => {
    expect(operatorFact("", "United States")).toBeNull();
    expect(operatorFact("   ", "United States")).toBeNull();
  });
});
