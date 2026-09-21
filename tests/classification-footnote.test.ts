/**
 * THE FOOTNOTE BEHIND THE MARK ON A SPACECRAFT LABEL.
 *
 * Sean, 2026-08-27: "I wouldn't put a ? on the site. I'd put an * and then
 * somewhere on details, like the written details, denote what that * means. We'd
 * want to make sure the flow makes sense and that users understand that caveat -
 * what we are trying to say."
 *
 * So the tests are about the CAVEAT SURVIVING, not about the glyph. The mark got
 * quieter; nothing about what it says was allowed to get quieter with it, and the
 * two ways that could happen are a footnote that softens and a footnote that
 * appears on a card with nothing to explain.
 */
import { describe, expect, it } from "vitest";
import {
  HEDGE_FOOTNOTE_TERM,
  HEDGE_MARK,
  classificationFootnote,
  hedgeFootnoteKey,
  satelliteChips,
} from "../src/main";
import footnoteFile from "../narration/hedge-footnotes.json";

/** The four states the shipped catalog actually holds, measured 2026-08-27 on
 *  public/data/artifacts/catalog-574094c018fc8cd5.json: 1,265 name-pattern, 190
 *  assessed, 39 assessed graded low, and 65 unclassified that draw no chip. */
const YAOGAN = { mission: "earth-observation", facet: "earth-observation", sector: "military",
                 basis: "name-pattern", confidence: "medium" };
const TJS = { mission: "other", facet: "military-other", sector: "military",
              basis: "assessed", confidence: "medium" };
const BARE_COSMOS = { mission: "other", facet: "military-other", sector: "military",
                      basis: "assessed", confidence: "low" };
const NO_CHIP = { mission: "other", facet: "other", sector: "unknown",
                  basis: "unclassified", confidence: "low" };
const STARLINK = { mission: "communications", facet: "commercial-satcom", sector: "commercial",
                   basis: "name-pattern", confidence: "medium", corroboration: "cohort-consistent" };
const SKYNET = { mission: "communications", facet: "milsatcom", sector: "military",
                 basis: "exact-name", confidence: "high" };

describe("the mark", () => {
  it("is an asterisk, because a question mark interrogates the reader", () => {
    expect(HEDGE_MARK).toBe("*");
    expect(HEDGE_FOOTNOTE_TERM).toBe("* on the label above");
  });
});

describe("which footnote a card gets", () => {
  it("keys on the basis for the ordinary uncorroborated card", () => {
    expect(classificationFootnote(YAOGAN)?.key).toBe("name-pattern");
    expect(classificationFootnote(TJS)?.key).toBe("assessed");
  });

  /* A reviewer who read the analysts' work and then wrote down that the answer is
     unsettled has said a second thing, and the 39 cards in that state are owed it.
     Collapsing them into `assessed` would print "named analysts worked it out" and
     drop the part where this release does not consider that settled. */
  it("separates an assessment the release itself grades low", () => {
    expect(classificationFootnote(BARE_COSMOS)?.key).toBe("assessed-low");
    expect(classificationFootnote(BARE_COSMOS)?.text)
      .not.toBe(classificationFootnote(TJS)?.text);
  });

  /* Zero cards today. The key exists because classificationChipEvidence WILL mark
     such a card, and the footnote it would otherwise fall back to says independent
     sources agree — a mark and its own explanation contradicting each other on one
     screen, which is the Tianmu-1 11 defect arriving somewhere new. */
  it("does not tell a low-graded per-object card that sources agree", () => {
    expect(hedgeFootnoteKey("web-corroborated", "low")).toBe("low-confidence");
    expect(hedgeFootnoteKey("norad-id", "low")).toBe("low-confidence");
  });

  it("falls back rather than throwing on a basis this release does not describe", () => {
    expect(hedgeFootnoteKey("some-basis-invented-later", "medium")).toBe("unknown");
    expect(classificationFootnote({ ...YAOGAN, basis: "some-basis-invented-later" })?.key)
      .toBe("unknown");
  });
});

describe("the negative control", () => {
  it("gives a corroborated card no footnote at all", () => {
    expect(satelliteChips(SKYNET).every((chip) => chip.evidence === "corroborated")).toBe(true);
    expect(classificationFootnote(SKYNET)).toBeNull();
  });

  it("gives a fleet-corroborated card no footnote at all", () => {
    expect(classificationFootnote(STARLINK)).toBeNull();
  });

  /* The 65 unclassified objects draw NO chip, because their facet is "other". A
     footnote explaining a mark that is not on the screen is a caveat about nothing,
     and it would be the only place on the card where an absence got a paragraph. */
  it("gives a card with no chip no footnote, however unknown the object is", () => {
    expect(satelliteChips(NO_CHIP)).toHaveLength(0);
    expect(classificationFootnote(NO_CHIP)).toBeNull();
  });
});

describe("what every footnote must say", () => {
  const entries = Object.entries(footnoteFile.footnotes);

  it("covers every key the card can ask for", () => {
    for (const key of ["name-pattern", "source-group", "assessed", "assessed-low",
                       "withdrawn-name-collision", "unclassified", "low-confidence", "unknown"]) {
      expect(footnoteFile.footnotes).toHaveProperty(key);
    }
  });

  /* THE ONE THAT MATTERS. Every one of these footnotes exists to report something
     that was NOT done, so a footnote with no negation left in it has been polished
     into agreement with the label it is supposed to qualify. This is the check that
     catches a pleasant rewrite, whoever writes it — the local model, a later editor,
     or a well-meaning pass over the prose. */
  it("says what has NOT been established", () => {
    for (const [key, entry] of entries) {
      expect(entry.text, key).toMatch(/\b(not|no|nobody|none|never|nothing|without|lacked|lacks)\b/i);
    }
  });

  it("never hedges, and never talks the evidence down either", () => {
    for (const [key, entry] of entries) {
      expect(entry.text, key)
        .not.toMatch(/\b(might|maybe|perhaps|possibly|probably|seems?|appears?|likely|presumably)\b/i);
      expect(entry.text, key).not.toMatch(/\b(guess|meaningless|fabricat)/i);
    }
  });

  /* The mark lives on the chip and the heading over the footnote carries it. A
     second asterisk inside the prose would read as a second footnote. */
  it("does not reprint the mark inside the prose", () => {
    for (const [key, entry] of entries) expect(entry.text, key).not.toContain("*");
  });

  it("records who wrote each one, so a deterministic fallback is never passed off as prose", () => {
    for (const [key, entry] of entries) {
      expect(["local-35b", "deterministic"], key).toContain(entry.source);
    }
  });
});
