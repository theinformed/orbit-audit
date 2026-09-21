import { describe, expect, it } from "vitest";

import {
  classificationBasisEvidence,
  classificationChipEvidence,
  satelliteChips,
} from "../src/main";

/**
 * The first chip, or a failure that names the input.
 *
 * `const [chip] = satelliteChips(...)` types `chip` as possibly undefined, and
 * four `chip.label` reads after it broke `tsc -b` from 2026-08-27 until this
 * was fixed. That mattered more than a type error usually does: `tsc -b` gates
 * the Playwright webServer, so a compile error in ONE test file silently took
 * the whole browser lane out of service. Six agents in a row reported it as
 * "pre-existing, not mine" and worked around it, each of them correctly.
 *
 * Silencing it with `chip!` would have been one character and the wrong fix:
 * `satelliteChips` returning nothing IS a defect, and the non-null assertion
 * would have surfaced it as a confusing property error three lines later
 * instead of saying what happened.
 */
function firstChip(input: Parameters<typeof satelliteChips>[0]) {
  const [chip] = satelliteChips(input);
  if (!chip) throw new Error(`satelliteChips returned no chip for ${JSON.stringify(input)}`);
  return chip;
}

/**
 * WHEN A FLEET VOUCHES FOR ITS MEMBERS, AND WHEN IT MUST NOT.
 *
 * Sean, looking at STARLINK-11600: "I don't like that ?", and "it looks
 * ridiculous on the display". He was right, and the count agreed — 6,288 of
 * 8,000 cards rested on `name-pattern` and drew the dashed, dimmed,
 * question-marked chip, so a mark built to warn about Tianmu-1 11 was firing on
 * four thousand Starlinks and had stopped carrying information.
 *
 * The repair distinguishes two claims the site had been treating as one. The
 * 18th Space Defense Squadron's naming inside a launch really is provisional —
 * LitSat-1 and LituanicaSat-1 were transposed until Doppler measurements sorted
 * them out — so IDENTITY is genuinely uncertain. But transposing two names
 * inside a Starlink batch leaves both objects Starlinks, so the MISSION CLASS,
 * which is what the chip states, survives exactly that error.
 *
 * This file pins both directions: the fleet finding lifts the mark, and it is
 * never allowed to lift it for the things the mark is actually for.
 */
describe("mission corroboration from the fleet", () => {
  it("draws a solid chip on a name-pattern object its fleet vouched for", () => {
    expect(classificationChipEvidence("name-pattern", "medium", "cohort-consistent"))
      .toBe("corroborated");
  });

  it("still draws claimed on a name-pattern object with no fleet finding", () => {
    // The negative control. If this ever returns "corroborated" the field has
    // stopped being read and every name match is silently being promoted.
    expect(classificationChipEvidence("name-pattern", "medium")).toBe("claimed");
    expect(classificationChipEvidence("name-pattern", "medium", null)).toBe("claimed");
  });

  it("REFUSES to promote 'assessed', whatever the fleet says", () => {
    // TJS, Blagovest and Garpun. Nobody has published what these spacecraft are
    // for, and no amount of cohort agreement can manufacture that. The pipeline
    // does not put them in a passing cohort today; this is the guard for the
    // day something changes and it does.
    expect(classificationChipEvidence("assessed", "medium")).toBe("claimed");
  });

  it("keeps the low-confidence veto above the fleet finding", () => {
    // "I checked, and I am still not sure" outranks "your neighbours agree".
    expect(classificationChipEvidence("name-pattern", "low", "cohort-consistent"))
      .toBe("claimed");
  });

  it("ignores a corroboration value this release does not describe", () => {
    expect(classificationChipEvidence("name-pattern", "medium", "cohort-vibes"))
      .toBe("claimed");
  });

  it("says the fleet agreed, and says what that does NOT establish", () => {
    const why = classificationBasisEvidence("name-pattern", "cohort-consistent");
    expect(why).toMatch(/fleet agrees with it/i);
    // The half that keeps the sentence honest. Without it this reads as the
    // operator confirming the spacecraft, which nobody did.
    expect(why).toMatch(/not which unit of the fleet it is/i);
  });

  it("does not downgrade a card whose own evidence is stronger than its cohort's", () => {
    // A rule written for this catalogue number beats "your neighbours agree",
    // and explaining it as the weaker fact would be a downgrade wearing the
    // clothes of an explanation.
    const why = classificationBasisEvidence("norad-id", "cohort-consistent");
    expect(why).toMatch(/written for this catalog number/i);
    expect(why).not.toMatch(/fleet agrees/i);
  });

  it("carries the finding onto the chip the card actually draws", () => {
    const chip = firstChip({
      mission: "communications",
      facet: "commercial-satcom",
      sector: "commercial",
      basis: "name-pattern",
      confidence: "medium",
      corroboration: "cohort-consistent",
    });
    expect(chip.label).toBe("Commercial SATCOM");
    expect(chip.evidence).toBe("corroborated");
    expect(chip.why).toMatch(/not which unit of the fleet it is/i);
  });

  it("leaves the same card hedged when the fleet did not vouch for it", () => {
    const chip = firstChip({
      mission: "communications",
      facet: "commercial-satcom",
      sector: "commercial",
      basis: "name-pattern",
      confidence: "medium",
    });
    expect(chip.evidence).toBe("claimed");
  });
});
