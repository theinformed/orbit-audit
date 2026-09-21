// ONE RULE, WRITTEN THREE TIMES, AND THIS IS WHAT KEEPS IT ONE RULE.
//
// The orbit class a visitor reads on a card comes from the PYTHON classifier:
// `derive_orbit` in pipeline/build_release.py stamps it into the catalog
// artifact at build time. The TypeScript `classifyOrbit` in src/orbit.ts is the
// same rule again, and `regime_from_elements` in pipeline/catalog_audit.py is a
// third copy, deliberately independent because an audit that imports the thing
// it audits audits nothing.
//
// If those drift apart nothing on the page says so. The artifact would publish
// one class, the client would compute another, and the disagreement would show
// up only as a card that says one thing and a filter that behaves as though it
// said another. That is a silent split-brain, and the fix is not to trust three
// authors to keep three copies in step -- it is to make the drift fail a test.
//
// tests/fixtures/orbit-classifier-cases.json is the shared table. This file
// checks it from the TypeScript side and tests/test_orbit_classifier_parity.py
// checks it from the Python side, both of them against the SAME expectations.
// Add a class or move a threshold in one language and the other two go red.
import { describe, expect, it } from "vitest";
import cases from "./fixtures/orbit-classifier-cases.json";
import { deriveOrbit } from "../src/orbit";

describe("orbit classifier parity", () => {
  it("agrees with the shared cross-language case table", () => {
    for (const row of cases.cases) {
      const { regime } = deriveOrbit(row.meanMotion, row.eccentricity, row.inclinationDeg);
      expect(regime, row.why).toBe(row.expect);
    }
  });

  /** Every class the union can hold is exercised, so the table cannot quietly
   *  stop covering one -- an untested branch is how a rule drifts unnoticed. */
  it("covers every orbit class the site can publish", () => {
    const covered = new Set(cases.cases.map((row) => row.expect));
    for (const regime of ["LEO", "MEO", "GEO", "IGSO", "HEO", "OTHER"]) {
      expect(covered.has(regime), `no case expects ${regime}`).toBe(true);
    }
  });
});
