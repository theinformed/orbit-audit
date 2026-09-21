import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import stylesSource from "../src/styles.css?raw";
import { describe, expect, it } from "vitest";
import { factValueVoice, factValueSpansRow, FACT_PROSE_CHARACTERS, FACT_HALF_COLUMN_CHARACTERS } from "../src/main";

/**
 * THE CARDS' TYPE HIERARCHY, MEASURED RATHER THAN ASSERTED.
 *
 * Sean, on the satellite card: "it has three drop downs and two links and it
 * just feels like it doesn't really flow right." Measured on the built bundle
 * at the shipped interface scale, the reason was that three levels of the
 * hierarchy were one size:
 *
 *   card name           12.76 px   the card's own title
 *   section summary     12.76 px   a fold INSIDE the card
 *   nested summary      12.76 px   a fold inside THAT
 *
 * and the reading below them was 11.60 px against a 10.44 px label — a 1.16 px
 * step — with every value, number or sentence, set identically at weight 700 in
 * the brightest colour on the card.
 *
 * The rule these pin: TWO ROLES THAT ARE WITHIN 1.5 px OF EACH OTHER ARE NOT
 * DISTINGUISHABLE BY SIZE, so they must differ in at least two of family,
 * weight and colour. Roles are read out of the stylesheet's own token block
 * rather than restated here, so a token that moves moves these with it.
 */

/**
 * The `--fs-*` ladder, in base px before the interface scale multiplies it.
 *
 * The tokens read `max(8px, calc(8px * ...))` since 2026-08-30, when the phone
 * stylesheet gained a density multiplier and the `max()` became the legibility
 * floor under it. The FIRST length in either form is the base rung, which is
 * what this ladder has always meant, so both spellings are accepted and the
 * plain `calc(` form is still read for any token that has not moved.
 */
function scaleStep(name: string): number {
  const match = stylesSource.match(new RegExp(`--fs-${name}: (?:max\\(|calc\\()(\\d+(?:\\.\\d+)?)px`));
  if (!match) throw new Error(`no --fs-${name} in styles.css`);
  return Number(match[1]);
}

/**
 * One `--type-*` token, resolved to base px. A role states its size either as
 * a rung of the `--fs-*` ladder or, for TITLE, as its own `calc()` — both are
 * read here so a role cannot escape the comparison by being written the other
 * way.
 */
function role(name: string): { px: number; weight: number; family: "sans" | "mono" } {
  const match = stylesSource.match(new RegExp(`--type-${name}: (\\d+) (var\\(--fs-([a-z]+)\\)|calc\\((\\d+(?:\\.\\d+)?)px)[^;]*var\\(--font-(sans|mono)\\)`));
  if (!match) throw new Error(`no --type-${name} in styles.css`);
  const px = match[3] ? scaleStep(match[3]) : Number(match[4]);
  return { px, weight: Number(match[1]), family: match[5] as "sans" | "mono" };
}

const SHIPPED_SCALE = 1.16;
const INDISTINGUISHABLE_PX = 1.5;

describe("the roles a data card uses are distinguishable from one another", () => {
  const roles = {
    name: role("title"),
    summary: role("disclose"),
    nested: role("disclose-sub"),
    readout: role("readout"),
    answer: role("answer"),
    body: role("body"),
    label: role("label"),
  };

  it("puts the card's own name above every fold inside it", () => {
    // The fault this replaces: name 12.76, summary 12.76, nested 12.76.
    expect(roles.name.px).toBeGreaterThan(roles.summary.px);
    expect((roles.name.px - roles.summary.px) * SHIPPED_SCALE).toBeGreaterThanOrEqual(INDISTINGUISHABLE_PX);
  });

  it("makes a nested fold both smaller AND quieter than the fold containing it", () => {
    // The stylesheet's own paragraph on DISCLOSE says SUB is "always smaller
    // AND quieter, never one or the other". It was only ever quieter.
    expect(roles.nested.px).toBeLessThan(roles.summary.px);
    expect(roles.nested.weight).toBeLessThan(roles.summary.weight);
  });

  /**
   * SECTION, added 2026-08-20. Sean, on the satellite card: the section
   * headings "should be made a little smaller than it is now so headings read
   * as clearly subordinate to the satellite title. The satellite title is the
   * only thing at its size."
   */
  it("sets a card's section headings below both the card title and the DISCLOSE role", () => {
    const section = role("section");
    expect(section.px).toBeLessThan(roles.name.px);
    expect((roles.name.px - section.px) * SHIPPED_SCALE).toBeGreaterThanOrEqual(INDISTINGUISHABLE_PX);
    // "A little smaller than it is now" — it was DISCLOSE.
    expect(section.px).toBeLessThan(roles.summary.px);
    // 7px until 2026-08-31, when Sean asked for collapsed folds to be tight.
    // The number is pinned because the rule it belongs to is what keeps a
    // section heading distinguishable from the card title above it; the
    // assertion below is the one that actually guards that.
    expect(stylesSource).toContain(".card-section summary { padding: 3px 0; font: var(--type-section);");
  });

  it("keeps READOUT and ANSWER at one rank, as the type system says they are", () => {
    // They drifted apart when READOUT moved a step down in e90050c, leaving a
    // word-valued reading outranking a measured one in the same grid.
    expect(roles.answer.px).toBe(roles.readout.px);
    // One rank, two voices: the difference is mono against sans, which is what
    // this stylesheet reserves monospace for.
    expect(roles.readout.family).toBe("mono");
    expect(roles.answer.family).toBe("sans");
  });

  it("separates a reading from the caption above it by more than colour", () => {
    expect(roles.readout.px).toBeGreaterThan(roles.label.px);
    expect(roles.readout.family).not.toBe(roles.label.family);
  });

  it("never leaves two roles within 1.5 px that also share family and weight", () => {
    const entries = Object.entries(roles);
    for (const [aName, a] of entries) {
      for (const [bName, b] of entries) {
        if (aName >= bName) continue;
        const apart = Math.abs(a.px - b.px) * SHIPPED_SCALE;
        if (apart >= INDISTINGUISHABLE_PX) continue;
        const differs = (a.family !== b.family ? 1 : 0) + (a.weight !== b.weight ? 1 : 0);
        expect(differs, `${aName} and ${bName} are ${apart.toFixed(2)}px apart and share family and weight`).toBeGreaterThan(0);
      }
    }
  });
});

/**
 * A fact grid holds measurements, names and sentences, and used to set all
 * three identically — so a forty-word explanation of an Alfven layer was
 * typographically a measurement, at weight 700, in the brightest colour on the
 * card. `factCell` calls these, so this drives the shipped rule.
 */
describe("which voice a reading's value is given", () => {
  it("sets a measurement in the readout voice", () => {
    expect(factValueVoice("568 km/s")).toBe("readout");
    expect(factValueVoice("L 6.26")).toBe("readout");
    expect(factValueVoice("53.2°")).toBe("readout");
  });

  it("sets a value that is a word in the answer voice, because a name is not a number", () => {
    expect(factValueVoice("Independent")).toBe("answer");
    expect(factValueVoice("NORTH + SOUTH")).toBe("answer");
  });

  it("sets a value that has become a sentence as prose", () => {
    const sentence = "IONS WESTWARD · ELECTRONS EASTWARD · THEY ADD, AND THE NET CURRENT IS WESTWARD";
    expect(sentence.length).toBeGreaterThan(FACT_PROSE_CHARACTERS);
    expect(factValueVoice(sentence)).toBe("prose");
  });

  it("gives anything past a half column the whole row", () => {
    // "LEO · 951 km now · 103.9 min period" is 34 characters and was wrapping
    // to three lines in a 150 px column under a label that had wrapped to two.
    // That string is history — the satellite card states the class, the
    // altitude and the period as three cells now — but the LENGTH RULE it
    // measured is still the rule, so it is still what the rule is tested on.
    expect(factValueSpansRow("LEO · 951 km now · 103.9 min period")).toBe(true);
    expect(factValueSpansRow("568 km/s")).toBe(false);
    expect(FACT_HALF_COLUMN_CHARACTERS).toBeLessThan(FACT_PROSE_CHARACTERS);
  });

  /**
   * THE LENGTH RULE IS A CLIFF, and a value that carries several facts falls
   * off it for a reason that has nothing to do with any of them. This is the
   * measured defect behind the orbit row's split on 2026-08-27: the same row
   * on two spacecraft, identical in structure and certainty, one side of 44
   * characters each.
   */
  it("classifies a multi-fact string by its length, which is why one is never used", () => {
    expect(factValueVoice("HEO · 38,987 km now · 717.9 min period")).toBe("readout");
    expect(factValueVoice("Other GSO / near-GEO · 35,699 km now · 1436.1 min period")).toBe("prose");
    // Each fact on its own is a measurement on both cards, which is the point.
    for (const value of ["38,987 km", "35,699 km", "717.9 min", "1436.1 min"]) {
      expect(factValueVoice(value), value).toBe("readout");
    }
  });

  it("has a stylesheet rule for each of the three, and a row-spanning cell", () => {
    expect(stylesSource).toContain(".fact-grid strong.is-readout");
    expect(stylesSource).toContain(".fact-grid strong.is-prose");
    expect(stylesSource).toContain(".fact-grid div.has-prose { grid-column: 1 / -1; }");
    // The row a cell claims by its LABEL rather than by its value's length.
    // The rule stays even though the satellite grid no longer produces a
    // full-width cell: splitting perigee from apogee made that grid even
    // (Sean, 2026-08-31), but `factValueSpansRow` still promotes any value
    // long enough to need the width, on this card and on the layer cards.
    expect(stylesSource).toContain(".fact-grid div.spans-row { grid-column: 1 / -1; }");
  });
});

/**
 * The satellite card, regrouped. Sean: "Is the information to split up? Is it
 * grouped right? Is there information that we aren't showing that is
 * important?" — the last of which turned out to be a ranking question, not a
 * data one: inclination, apogee and perigee were all published and all on the
 * card, at the bottom of a shut provenance list in the smallest type on it.
 */
describe("how the satellite card is grouped", () => {
  const from = indexMarkup.indexOf("satellite-card-template");
  const template = indexMarkup.slice(from, from + indexMarkup.slice(from).indexOf("</template>"));

  it("has a satellite card template to read", () => {
    expect(from).toBeGreaterThan(-1);
    expect(template).toContain("data-card-orbit");
  });

  it("opens on the details and keeps the provenance folded", () => {
    const details = template.slice(template.indexOf('data-card-section="details"'));
    expect(details.slice(0, details.indexOf(">"))).toContain(" open");
    const provenance = template.slice(template.indexOf('data-card-section="ephemeris"'));
    expect(provenance.slice(0, provenance.indexOf(">"))).not.toContain(" open");
  });

  /** The order Sean specified, top to bottom. "Ground Data" was removed on
   *  2026-08-21: its only universal content was one button, so a heading and a
   *  shut disclosure stood between the reader and a single action. The button
   *  moved into Satellite Details and the published station list went with it. */
  it("runs details, then background, then provenance, with no ground fold", () => {
    const order = ["details", "background", "ephemeris"]
      .map((name) => template.indexOf(`data-card-section="${name}"`));
    expect(order.every((at) => at > -1)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(template).not.toContain('data-card-section="ground"');
  });

  it("names each group for the question it answers", () => {
    // Sean, on the heading this replaces: "'What is it and who runs it' sounds
    // really dumb." Who runs it and where it is are one question about one
    // object, and they are one section now.
    expect(template).toContain("<summary>Satellite Details</summary>");
    expect(template).toContain("<summary>Satellite Background</summary>");
    expect(template).not.toContain("<summary>Ground Data</summary>");
    expect(template).toContain("<summary>Data Sources</summary>");
    expect(template).not.toContain("<summary>What it is and who runs it</summary>");
    expect(template).not.toContain("<summary>Where it is</summary>");
    expect(template).not.toContain("<summary>Satellite facts</summary>");
  });

  /**
   * THE FOLD INSIDE THE DESCRIPTION IS BACK, AND ONLY FOR THE CASE IT WAS REMOVED
   * FOR NOT BEING. Both of Sean's rulings are in this test, because they point
   * opposite ways and the difference between them is what the fold now depends on.
   *
   * Removing it, on Suomi NPP: the lead sentence is good and the fold under it is
   * "incredibly short", so the fold earned nothing. That is still true, and the
   * old "More about this description" fold is still gone -- it split every
   * description at its first full stop, whatever was behind it.
   *
   * Re-adding it, 2026-08-27: "max 2 paragraphs, and max just a few lines per
   * paragraph ... with a max of maybe 6-8 lines". 835 cards carry 800 to 2,425
   * characters as one unbroken block, and the only way to obey that ruling without
   * DELETING researched, cited prose is to open with a shortened version and keep
   * the rest one click below. What is behind this fold is the part that did not
   * fit, and `buildStackCard` hides it entirely unless a shortening actually
   * happened -- which is most cards, where the description is printed whole and
   * there is no fold at all.
   */
  it("folds the rest of the description only when a shortening left a rest", () => {
    expect(template).not.toContain("More about this description");
    expect(template).toContain("Read the full description");
    expect(template).toContain("data-card-purpose-more");
    expect(template).toContain("data-card-purpose-rest");
    // The template ships it hidden, and exactly one line un-hides it.
    const fold = template.slice(template.indexOf("data-card-purpose-more"));
    expect(fold.slice(0, fold.indexOf(">"))).toContain("hidden");
    expect(explorerSource).toContain("more.hidden = !shape.shortened");
  });

  /** At most two paragraphs on the face of the card, whatever the data says. */
  it("has exactly two paragraph slots in the description, and no third", () => {
    const background = template.slice(
      template.indexOf('data-card-section="background"'),
      template.indexOf('data-card-section="ephemeris"'),
    );
    expect(background).toContain("data-card-purpose");
    expect(background).toContain("data-card-purpose-second");
    expect(background).not.toContain("data-card-purpose-third");
    // The fleet paragraph gets its OWN citation, because it comes from a different
    // page than the sentence above it. One Source link under two paragraphs from
    // two sources is a card vouching for something nobody checked.
    expect(background).toContain("data-card-purpose-source");
    expect(background).toContain("data-card-fleet-source");
  });

  /** The category and operator class are chips in the head, above the identifiers. */
  it("puts the evidence chips between the name and the NORAD/COSPAR line", () => {
    const head = template.slice(template.indexOf("sat-card-head"), template.indexOf("sat-card-body"));
    expect(head).toContain("data-card-chips");
    expect(head.indexOf("data-card-name")).toBeLessThan(head.indexOf("data-card-chips"));
    expect(head.indexOf("data-card-chips")).toBeLessThan(head.indexOf("data-card-identity"));
  });

  it("puts the identifiers beside the name instead of opening the provenance list with them", () => {
    const head = template.slice(template.indexOf("sat-card-head"), template.indexOf("sat-card-body"));
    expect(head).toContain("data-card-identity");
    // The mission is a chip now, not an <em> class line.
    expect(head).not.toContain("data-card-mission");
  });

  /**
   * An action sits with the facts it acts on, not in a stack of buttons at the
   * foot of the card. Sean: the OMM download goes at the end of Satellite
   * Details and the orbit archive goes "under the orbit data" in the same
   * section. The 2-D map used to be the whole of a "Ground Data" fold; since
   * 2026-08-21 it is a row above the OMM download, and since 2026-08-27 the
   * orbit archive is the row above IT, so the section ends with three matched
   * full-width actions and the published station list sits above them.
   *
   * The order is Sean's, given on 2026-08-27: "we just move it down to its own
   * box like we had it before, right between the grid of values and the 2d
   * ground track box."
   */
  it("puts each action inside the section whose facts it acts on", () => {
    const details = template.slice(
      template.indexOf('data-card-section="details"'),
      template.indexOf('data-card-section="background"'),
    );
    expect(details).toContain("data-card-orbit-history");
    expect(details).toContain("data-card-export");
    expect(details).toContain("data-card-ground-track");
    expect(details).toContain("data-card-stations");
    expect(details.indexOf("data-card-details")).toBeLessThan(details.indexOf("data-card-orbit-history"));
    // The archive, then the map, then the download: one set of three.
    expect(details.indexOf("data-card-orbit-history")).toBeLessThan(details.indexOf("data-card-ground-track"));
    expect(details.indexOf("data-card-ground-track")).toBeLessThan(details.indexOf("data-card-export"));
    expect(details.indexOf("data-card-stations")).toBeLessThan(details.indexOf("data-card-orbit-history"));
  });

  /**
   * REVERSED DELIBERATELY, 2026-08-27. Between 08-21 and 08-27 the orbit
   * archive was a CELL of the fact grid, written in the grammar of "Launched"
   * beside it — a grey label over a value — and this test asserted exactly
   * that. It read well as a fact and it cost the grid its shape: the cell held
   * a control, an arrow and a sentence, so it never sat like the tabular values
   * around it, and the full row it forced left a visible hole in the column of
   * readings. Sean, on STARLINK-11600: "see how the grid of blue text values
   * has sort of a gap in it? I wonder if we can move the orbit history back
   * down to its own box, below where it is, in the same style as the other two
   * boxes."
   *
   * So it wears the 2-D map's box, and the fact grid holds nothing but facts.
   */
  it("gives the orbit archive the same box as the other two actions", () => {
    const details = template.slice(
      template.indexOf('data-card-section="details"'),
      template.indexOf('data-card-section="background"'),
    );
    // The same class the ground-track box wears, so the three are one set and
    // cannot drift apart. Nothing of the grid cell survives.
    expect(details).toContain('class="ground-track-open orbit-history-open" data-card-orbit-history');
    expect(details).not.toContain("data-card-orbit-history-cell");
    expect(details).not.toContain("fact-orbit-history-open");
    expect(stylesSource).not.toContain(".fact-orbit-history-open");
    expect(stylesSource).not.toContain("fact-grid-action");
    // The grid is facts only now: nothing is left inside it for the render to
    // lift out and put back.
    expect(details).toContain('<div class="fact-grid" data-card-details></div>');
    // The state still has a place to be written, and the box still says what
    // it does before it says anything about the archive.
    expect(details).toContain('data-card-orbit-history-value');
    expect(details).toMatch(/data-card-orbit-history hidden>Open orbit history</);
  });

  /**
   * A number that has not been measured must not appear. The count comes off a
   * history shard the browser already holds; when it does not hold one, the
   * box says so in words — or, for the ordinary "nobody has downloaded it yet"
   * case, says nothing about the contents at all — and still opens the archive.
   */
  it("never invents the element-set count", () => {
    expect(explorerSource).toContain('text = "History not loaded"');
    expect(explorerSource).toContain('text = "History unavailable"');
    expect(explorerSource).toContain('? "No stored elements"');
    // Read from what is already downloaded. No fetch is started to fill a card.
    expect(explorerSource).toContain("this.orbitShardCache.get(shardFor(norad, shardCount))");
  });

  /**
   * The geometry controls left the card for Display settings, and the footprint
   * essay left the site for the Learn section's footprint page. What may NOT
   * leave is the claim that the fade inside the footprint is decorative: that
   * is a caveat on what is drawn, and it stays beside the control that draws it.
   */
  it("has moved the geometry and mask controls into Display settings", () => {
    expect(indexMarkup).not.toContain("satellite-geometry-template");
    expect(indexMarkup).not.toContain("geometry-explainer");
    expect(template).not.toContain("data-card-geometry-slot");
    const display = indexMarkup.slice(
      indexMarkup.indexOf('id="display-settings"'),
      indexMarkup.indexOf('id="satellite-stack"'),
    );
    expect(display).toContain('data-geometry="footprint"');
    expect(display).toContain('data-footprint-elevation="10"');
    expect(display).toContain("not signal strength");
  });
});
