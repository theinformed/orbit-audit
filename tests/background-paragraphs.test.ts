import { describe, expect, it } from "vitest";
import { backgroundParagraphs } from "../src/main";

/**
 * What the Satellite Background section is allowed to print.
 *
 * Sean, 2026-08-27, having been shown one of the SHORT ones: "on the site, I want max 2
 * paragraphs, and max just a few lines per paragraph. It is fine if some only have 1
 * paragraph and it can be longer if so, with a max of maybe 6-8 lines." And: "I definitely
 * don't want it to get crowded and crazy."
 *
 * The count is the part a test can hold. The character ceilings behind it are enforced
 * where the text is produced -- narration/build_shaped_purposes.py for a shortened opening,
 * tests/test_background_shape.py for a fleet paragraph -- because those are the two places
 * that can still do something about a violation. By the time it reaches this function, the
 * only honest move left is to print less.
 */
const LONG = "A researched description that runs on for a while. ".repeat(20);

describe("backgroundParagraphs", () => {
  it("prints the description whole when nothing shortened it", () => {
    const shape = backgroundParagraphs(LONG, null, null);
    expect(shape.paragraphs).toEqual([LONG.trim()]);
    expect(shape.shortened).toBe(false);
    // No remainder means no disclosure. An empty fold is worse than no fold, which is what
    // Sean said about the two-sentence one this card used to carry: "the drop down is
    // incredibly short".
    expect(shape.rest).toBe("");
  });

  it("prints the shortened opening and keeps the whole description behind it", () => {
    const shape = backgroundParagraphs(LONG, ["An opening.", "A second paragraph."], null);
    expect(shape.paragraphs).toEqual(["An opening.", "A second paragraph."]);
    expect(shape.shortened).toBe(true);
    expect(shape.rest).toBe(LONG.trim());
  });

  it("adds the fleet paragraph as the second one, never inside the first", () => {
    const shape = backgroundParagraphs("A Starlink.", null, "The fleet flies in shells.");
    expect(shape.paragraphs).toEqual(["A Starlink.", "The fleet flies in shells."]);
    expect(shape.shortened).toBe(false);
  });

  it("never prints three paragraphs, and drops the FLEET note rather than the object's own", () => {
    const shape = backgroundParagraphs(LONG, ["One.", "Two."], "The fleet.");
    expect(shape.paragraphs).toEqual(["One.", "Two."]);
  });

  it("ignores a shortening that is not actually shorter", () => {
    // Printing it would put the same words on the card twice -- once on the face and once
    // inside a disclosure claiming to hold what was left out -- and hide the upstream bug.
    const shape = backgroundParagraphs("Short.", ["Short but longer than the original."], null);
    expect(shape.paragraphs).toEqual(["Short."]);
    expect(shape.shortened).toBe(false);
    expect(shape.rest).toBe("");
  });

  it("renders nothing at all when there is nothing to say", () => {
    expect(backgroundParagraphs("", null, null).paragraphs).toEqual([]);
    expect(backgroundParagraphs("   ", [], "").paragraphs).toEqual([]);
  });

  it("drops empty and whitespace-only paragraphs from a shortening", () => {
    const shape = backgroundParagraphs(LONG, ["An opening.", "   "], null);
    expect(shape.paragraphs).toEqual(["An opening."]);
  });
});
