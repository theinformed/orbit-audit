import { describe, expect, it } from "vitest";

import indexMarkup from "../index.html?raw";
import stylesheet from "../src/styles.css?raw";
import contentSource from "../src/content.ts?raw";
import explorerSource from "../src/main.ts?raw";

/**
 * The rail folds, and each fold is the browser's own.
 *
 * Sean, looking at the Satellites mode after Favorites shipped collapsible:
 * "if we made favorites collapsable, shouldn't we also make satellites
 * collapsable?" The answer was yes, and yes again for the search box above it,
 * because the three of them are the same object: a section title with a body
 * under it. Measured at 1440x900 and the Large text size, those three sections
 * are 96 px, 48 px and 536 px of an 832 px rail — 70 % of the column — so the
 * ability to put any of them away is the difference between a rail a reader
 * scrolls and one they read.
 *
 * These pin the REASONS rather than the appearance:
 *
 *  - `details`, so the keyboard and screen-reader behaviour is not ours to
 *    get wrong;
 *  - the one fact worth seeing while shut stays on the summary row;
 *  - the default open state matches what the section is FOR;
 *  - and no new typographic treatment came with any of it.
 */
describe("every foldable rail section folds the same way", () => {
  const railStart = indexMarkup.indexOf('id="control-rail"');
  const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));

  it("folds all three with a details element rather than a bespoke toggle", () => {
    for (const id of ["search-details", "favorites-details", "catalog-details", "environment-details"]) {
      expect(rail, `#${id} is not a details element`).toMatch(
        new RegExp(`<details class="rail-details [^"]*" id="${id}"`),
      );
    }
    // A script-driven fold is the failure mode this rules out: it loses the
    // Enter/Space handling, the ARIA and the find-in-page reveal that
    // `details` gives for free.
    expect(explorerSource).not.toMatch(/catalog-details[^\n]*addEventListener/);
    expect(explorerSource).not.toMatch(/search-details[^\n]*addEventListener/);
  });

  it("keeps the summary on the rail's one section-title shape", () => {
    // TITLE role, one name per section. `.rail-head` is that shape, and a
    // summary that folds is still that shape rather than a seventh treatment.
    for (const summary of ["search-summary", "favorites-summary", "catalog-summary", "environment-summary"]) {
      expect(rail).toContain(`class="rail-head ${summary}"`);
    }
    expect(stylesheet).toContain(".rail-details > summary {");
    // One rule for the three of them, not three rules that drift apart.
    expect(stylesheet).not.toContain(".favorites-details > summary {");
  });

  it("leaves the count on the row that stays visible when shut", () => {
    // Favorites shows whether anything is starred; Satellites shows how many
    // spacecraft the current filters leave drawn. Both are the one fact their
    // section owes a reader who has put it away.
    expect(rail).toMatch(/<summary class="rail-head favorites-summary">.*id="favorites-count".*<\/summary>/);
    expect(rail).toMatch(/<summary class="rail-head catalog-summary">.*id="visible-count".*<\/summary>/);
  });

  it("opens the two primary controls and leaves the usually-empty one shut", () => {
    // Favorites is shut because it is usually EMPTY, which is a fact its
    // summary already states. Satellites is the mode's primary control surface
    // and the search box is its first move, so both open: a mode that opens on
    // a column with nothing to act on has answered the wrong complaint.
    expect(rail).toContain('id="catalog-details" open>');
    expect(rail).toContain('id="search-details" open>');
    expect(rail).toContain('id="environment-details" open>');
    expect(rail).toContain('id="favorites-details">');
  });

  it("counts the drawn layers on the Space weather summary row", () => {
    // Sean: "We are going to have this combined with satellites in some cases.
    // So we need that rail to be clean." Combined mode stacks the catalog and
    // the layers in one column, and a folded Space weather section still owes
    // the reader the number of layers it is drawing.
    expect(rail).toMatch(/<summary class="rail-head environment-summary">.*id="active-layer-count".*<\/summary>/);
    // Written from the same array the map key counts, so the two cannot
    // disagree about how many layers are drawn.
    expect(explorerSource).toContain('document.getElementById("active-layer-count")');
    const mapKey = explorerSource.slice(explorerSource.indexOf("private updateMapKey("));
    expect(mapKey.slice(0, 1600)).toContain("active-layer-count");
  });

  it("keeps the search box reachable by name once its <label> became a summary", () => {
    // The visible name moved into the summary, so the input carries its own
    // accessible name rather than losing one.
    expect(rail).toContain('aria-label="Find a satellite by name or NORAD ID"');
    expect(rail).not.toContain('<label for="satellite-search">');
  });
});

/**
 * Sean: "WHY PUT USELESS REDUNDANT TEXT ON THE RAIL?"
 *
 * The mode picker printed a sentence under it for each of the three modes. Two
 * described the section immediately beneath them — "Find a spacecraft…" over a
 * section titled "Find a satellite" with a search box in it — and the third
 * described a restraint Combined mode does not apply. Nothing was moved,
 * because none of the three carried a fact the controls did not.
 */
describe("the mode picker prints no blurb", () => {
  it("has no host for one", () => {
    expect(indexMarkup).not.toContain('id="mode-description"');
  });

  it("does not write one from the entry point either", () => {
    // The sentences survive in this file only as the comment explaining why
    // they went, so these look for the WRITE rather than the words.
    expect(explorerSource).not.toContain('byId("mode-description")');
    for (const mode of ["satellites", "environment", "combined"]) {
      expect(explorerSource, `${mode} still has a blurb string`).not.toMatch(
        new RegExp(`${mode}: "(Find a spacecraft|Follow current conditions|Compare a restrained)`),
      );
    }
  });
});

/**
 * Sean, by name: "one thing you did remove - the SWPC 'card' that was in the
 * rail previously. It looked good. We can just have it be under 'space
 * weather' as a separate, collapsable entry."
 *
 * It had never been deleted. It unhides itself the moment NOAA's R/S/G scales
 * land and it had been sitting below the fold ever since, which is the same
 * complaint as the rest of this pass rather than a different one. These pin
 * that it is alive, that it folds, and that it did not drag the three fuller
 * NOAA panels back into the rail with it.
 */
describe("the NOAA conditions card is back, folding, and fed", () => {
  const railStart = indexMarkup.indexOf('id="control-rail"');
  const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));

  it("folds, inside Conditions right now", () => {
    expect(rail).toContain('<details class="swpc-summary" id="swpc-summary" hidden open>');
    expect(rail).toContain('<summary class="swpc-summary-head">');
    // It came back under Space weather first and moved once more the same day,
    // when the measured drivers left the Data Explorer: "what is the storm
    // level" and "what are the drivers" are the same question asked twice, and
    // two adjacent folds asking it separately read as two unrelated things.
    const conditions = rail.slice(rail.indexOf('class="rail-section conditions-section"'));
    expect(conditions.slice(0, conditions.indexOf("</section>"))).toContain('id="swpc-summary"');
  });

  it("is fed by the live scales rather than being a decorative shell", () => {
    // A card that looks good and says "—" is worse than no card.
    expect(explorerSource).toContain('byId("swpc-summary").hidden = false');
    expect(explorerSource).toContain('byId("swpc-summary-time").textContent');
    for (const chip of ["swpc-scale-r", "swpc-scale-s", "swpc-scale-g"]) {
      expect(explorerSource, `${chip} is never filled`).toContain(`"${chip}"`);
    }
  });

  it("reads its storm level off three blocks, not off a sentence", () => {
    // The R/S/G strip is the graphic. Nothing in the rail restates it in prose.
    expect(rail).toContain('class="swpc-scale-strip"');
    expect(rail).not.toContain("NOAA OPERATIONAL CONDITIONS");
  });

  it("leaves the three fuller NOAA panels on Current conditions", () => {
    expect(rail).not.toContain("swpc-panel");
  });
});

/**
 * Sean: "the rail looks fucking cluttered still. I think you need to remove
 * the ILLUSTRATION or MODEL + EMPIRICAL chips. They clutter it. And those
 * chips, you can just move them to the data viewer."
 *
 * Eleven of them, one per layer row, each a bordered tracked-caps block in one
 * of five colours, in a column whose content is layer NAMES. They were the
 * loudest thing on every row.
 *
 * THE CONSTRAINT THEY WERE THERE FOR HAS NOT MOVED: a layer may never imply it
 * is a measurement when it is not, and the evidence badge is how that is
 * enforced. What changed is which surface carries it. The rail chip was the
 * one place the badge sat beside a control rather than beside an explanation -
 * a rail row says what to switch on, not what you are looking at - so it was
 * the one place a reader could meet the stamp and learn nothing from it.
 *
 * These pin the trade, both halves of it, because a later change that removes
 * a chip without the card behind it would be the honesty regression this file
 * exists to prevent.
 */
describe("the evidence badge moved to the data viewer, and is still unmissable", () => {
  const railStart = indexMarkup.indexOf('id="control-rail"');
  const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));

  it("carries no evidence chip on any rail row", () => {
    expect(rail).not.toContain("layer-status");
  });

  it("still stamps every layer card, from the layer's own spec", () => {
    // Not a hand-written chip per layer: the class and the words both come off
    // the spec, so a new layer cannot ship without one.
    expect(explorerSource).toContain("badge.textContent = spec.badge;");
    expect(explorerSource).toContain("badge.className = `layer-status ${spec.evidence}`");
  });

  it("puts that stamp where a shut card still shows it", () => {
    const template = indexMarkup.slice(indexMarkup.indexOf('<template id="layer-card-template">'));
    const head = template.slice(0, template.indexOf('<div class="sat-card-body"'));
    expect(head).toContain('class="layer-status" data-card-mission');
  });

  it("opens the panel that holds it, rather than folding it behind a click", () => {
    // The path a reader actually walks: switch a layer on, the panel appears
    // on its own, and the first thing in it is the layer's name and its class.
    expect(explorerSource).toContain("private explorerCollapsed = false;");
    // And on a phone, where there is no window over the globe at all since
    // 2026-08-28: the badge is in the card, the card is in the space weather
    // panel under its own layer's row, and it is drawn OPEN there — the row's
    // caret is the only fold, so one press reaches the stamp.
    expect(explorerSource).toMatch(/if \(card\.parentElement !== slot\) slot\.append\(card\);\s*\n[\s\S]{0,400}?this\.setLayerCardCollapsed\(card, false\);/);
  });

  it("keeps the chips where they explain something: inside the cards", () => {
    // The magnetosphere annotations are labelled MODEL-DERIVED and EMPIRICAL
    // beside prose that says what each one draws. Those live in the layer
    // control panels, which are moved into the layer's card, not in the rail.
    const panels = indexMarkup.slice(indexMarkup.indexOf('id="layer-control-panels"'), railStart);
    expect(panels).toContain('class="layer-status empirical">EMPIRICAL');
    expect(panels).toContain('class="layer-status model">MODEL-DERIVED');
  });
});

/**
 * A RAIL ROW IS A SWITCH, AND ITS LINE IS THE PRODUCT IT DRAWS.
 *
 * Sean, on the site generally: "your added text in some places is a fucking
 * waste of space and distracts humans from what they need to see - graphical
 * representations of data. Stop adding filler/fluff text to my site." And on
 * one line specifically, "the height that climbs in a storm", which explained
 * a layer called Thermosphere height.
 *
 * Measured before this: eleven rows carrying 599 characters between them, in
 * nine different sentence shapes - a source here, a teaching point there, a
 * caveat somewhere else. After: 248 characters, and every one of them the same
 * shape, which is the part that makes the column scannable rather than merely
 * shorter. A reader running an eye down it now reads NOAA GloTEC, NOAA
 * OVATION, NOAA MHD, NOAA/NASA RBE - whose product each layer is, which is the
 * question a METOC officer actually has.
 *
 * NOTHING WAS DELETED. Each removed clause is already stated where it teaches:
 * the D/E/F1/F2-sums-to-TEC relation and the ground-magnetometer sentence are
 * on Learn, the OVATION forecast horizon is in the layer's own Validity block,
 * and the ring current's "its shape is not measured anywhere" is the card's
 * whole second half plus its badge. The plasma-sheet retirement is the
 * precedent and this follows it.
 */
describe("the rail's layer lines are one short clause each", () => {
  const railStart = indexMarkup.indexOf('id="control-rail"');
  const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));
  const lines = [...rail.matchAll(/<small>([\s\S]*?)<\/small>/g)]
    .map((m) => (m[1] ?? "").replace(/<[^>]+>/g, "").replace(/&mdash;/g, "\u2014").replace(/&nbsp;/g, " ").trim());

  it("found the rows, so the counts below mean something", () => {
    expect(lines.length).toBeGreaterThanOrEqual(11);
  });

  it("keeps every one of them short enough to read at a glance", () => {
    // The worst was 107 characters, on the ring current. The bar is set at 45
    // because that is a clause, not a sentence: past it, the line wraps to a
    // second row and the switch stops looking like a switch.
    for (const line of lines) {
      expect(line.length, `"${line}" is ${line.length} characters`).toBeLessThanOrEqual(45);
    }
  });

  it("spends no line explaining what the layer's own name already says", () => {
    // The exact sentences Sean named, and the class they belong to.
    for (const filler of [
      "the height that climbs in a storm",
      "that the TEC surface is the sum of",
      "what a ground magnetometer records",
      "viewing probability",
    ]) {
      expect(rail, `"${filler}" is back on a rail row`).not.toContain(filler);
    }
  });

  it("keeps what it moved, where that text teaches", () => {
    expect(contentSource).toContain("sum of");
    expect(contentSource).toContain("ground magnetometer");
    expect(contentSource).toContain("viewing probability");
  });
});

/**
 * THE SITE OPENS ON A BARE GLOBE.
 *
 * Sean: "Perhaps don't start off with any satellites then. Just a globe
 * without satellites and without any layers." That arrived as the answer to a
 * different complaint - "you need to remove the 'display density' - it is
 * stupid" - and it dissolves that one, because there is no longer an argument
 * about what a sensible default satellite set is. There is no default set.
 *
 * Two things used to draw before anyone asked. The Featured density put 450
 * dots on screen, and `setMode("satellites")` applied the Simple layer preset
 * at startup, which switched the thermosphere on. Presets survive - the owner
 * took back the instruction to delete them the same minute he sent it - they
 * are just something a reader CHOOSES now.
 *
 * The failure mode this guards is not "a layer came back on"; it is an empty
 * globe that looks BROKEN.
 *
 * SUPERSEDED IN PART, 2026-08-20. The layer half stands unchanged. The
 * satellite half does not: the owner moved the catalog off a bare globe and
 * onto a featured constellation — "We should be starting with a satellite or
 * constellation of the day. I say we start with GPS. Have that shown when you
 * load the page" — so the load state is now GPS drawn, with the orbit band
 * unset and no band button lit. What survives from the bare-globe work is the
 * thing that mattered: the drawn set is a pure function of the filter state,
 * and `catalogRequested` — a second gate held over a full selection, which is
 * what made the rail claim "all" over an empty globe — is gone rather than
 * repointed. `tests/browser.spec.ts` drives the model through its transitions.
 */
describe("nothing is drawn until the reader asks for it", () => {
  it("keeps one gate on what is drawn, and that gate is the selection itself", () => {
    // The second gate is DELETED, not renamed. While it existed the facet sets
    // could be full while the globe was empty, and both halves were faithfully
    // reporting their own idea of the state.
    expect(explorerSource).not.toContain("catalogRequested");
    // And no gate has grown back beside it. Explorer Mode was the other thing
    // that could empty the globe over a full facet set — Space Weather mode
    // resolved `filteredIndices` to `[]` no matter what the filters said — and
    // it was retired on 2026-08-28. The drawn set is the filters and the one
    // open spacecraft, and nothing else.
    expect(explorerSource).toContain("const filteredIndices = candidates.map(({ index }) => index);");
    expect(explorerSource).not.toMatch(/filteredIndices[\s\S]{0,120}this\.mode/);
    // Whether the reader has touched a catalog control is still known, but it
    // is wording-only and may never decide what is drawn.
    expect(explorerSource).toContain("private catalogAsked = false;");
    expect(explorerSource).not.toMatch(/filteredIndices[\s\S]{0,120}catalogAsked/);
    // The one listener that records it stays one listener on the section every
    // catalog control lives in, rather than a flag threaded through ten
    // handlers that a later one would forget.
    expect(explorerSource).toContain('catalogSection?.addEventListener("click", askedForCatalog, true)');
    expect(explorerSource).toContain('catalogSection?.addEventListener("change", askedForCatalog, true)');
  });

  it("still draws a satellite picked out of search or favourites", () => {
    // That path goes through the selection, not the filters, and turning the
    // whole catalog on with it would bury the spacecraft just asked for.
    //
    // It used to read `resolveStackVisibility(... this.selectedStack ...)`,
    // which unioned the filtered set with a LIST of pinned spacecraft. The
    // selection became one spacecraft at a time on 2026-08-28, so the union is
    // `resolveVisibleIndices`'s own "the selected object always stays visible"
    // rule and there is nothing left to compose over it. What is being pinned
    // is unchanged: the open spacecraft is drawn whether or not the filters
    // select it.
    expect(explorerSource).toContain("resolveVisibleIndices(");
    // Comments stripped: the tombstone where the wrapper stood names it.
    expect(explorerSource.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")).not.toContain("resolveStackVisibility(");
    const refresh = explorerSource.slice(explorerSource.indexOf("private refreshVisible()"));
    expect(refresh.slice(0, 3200)).toContain("this.selectedIndex");
  });

  it("applies no layer preset at load, and nothing clears the layers behind the reader", () => {
    expect(explorerSource).not.toContain('this.applyLayerPreset("simple", true)');
    expect(explorerSource).not.toContain("this.applyLayerPreset(this.currentPreset);\n    this.refreshVisible");
    // SUPERSEDED, 2026-08-28, and the assertion is inverted rather than
    // deleted. Entering Satellites mode used to CLEAR the layers, on the
    // reasoning that their controls left the rail with them and a field drawn
    // from a panel the reader cannot see is a field they cannot switch off.
    // Sean ruled the clearing out by name: "if you plot an environment layer,
    // it shows up and persists until you X out the layer in the viewer, even if
    // you go back to the satellite panel." The mode is gone, so both halves of
    // the rail are always present and the premise no longer holds — and
    // `hideAllLayers` went with its only caller, so nothing can turn a reader's
    // layers off except the layer viewer's own X.
    // Comments stripped for the same reason as everywhere else in this file:
    // both names survive in the tombstones that say why they went.
    const code = explorerSource.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toContain("hideAllLayers");
    expect(code).not.toContain("setMode");
    // The one place layers are still turned off wholesale is the reader
    // pressing the X on the layer viewer.
    expect(explorerSource).toContain("private closeDataExplorer()");
    // And no preset button reads as selected before one is pressed.
    expect(indexMarkup).not.toContain('<button class="is-active" data-preset="simple">');
  });

  it("tells the truth on the count, and raises no alarm about it", () => {
    // The count reports the drawn population and nothing else — no second
    // vocabulary for "you have not asked yet", which was a distinction only
    // the deleted gate could draw.
    // "to the right 'x Selected'" — Sean set the word on 2026-08-28. The
    // fact it counts is unchanged: the drawn population and nothing else.
    expect(explorerSource).toContain('byId("visible-count").textContent = `${this.visibleIndices.size.toLocaleString()} Selected`');
    expect(explorerSource).not.toContain('"none shown"');
    // AND NO ALARM. There is no longer any function that turns an empty
    // selection into words, and no control offering to undo one. Sean, twice:
    // "Duh. I cleared everything. Why am I getting an error", and "Stop that
    // shit. You keep adding a feature there."
    //
    // Comments are stripped before these three run. Both files carry a
    // tombstone explaining what was removed, and it quotes the removed words —
    // an assertion a comment can satisfy is an assertion that passes both ways.
    const code = explorerSource.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toContain("filterStatusMessage");
    expect(code).not.toContain("nothing selected");
    expect(indexMarkup.replace(/<!--[\s\S]*?-->/g, "")).not.toContain('id="filter-reset"');
  });

  it("has no Display density control left to remove", () => {
    const railStart = indexMarkup.indexOf('id="control-rail"');
    const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));
    expect(rail).not.toContain("data-density");
    expect(rail).not.toContain("density-control");
    expect(explorerSource).not.toContain('[data-density]');
    // The ceiling it used to set survives as a rendering guard: 450 on a
    // desktop, 220 at 820 px or narrower, lifted the moment a facet narrows
    // the population. Deleting the control must not delete that protection.
    expect(explorerSource).toContain("window.innerWidth <= 820 ? 220 : 450");
  });

  it("shows no colour key for a globe with nothing on it", () => {
    // Still the rule — the key is hidden whenever nothing is drawn, which is
    // now the state a reader reaches by clearing rather than the one they
    // arrive in.
    expect(explorerSource).toContain("legend.hidden = this.visibleIndices.size === 0;");
    // main.ts had always set `legend.hidden`; `.legend { display: flex }` beat
    // the UA rule for `[hidden]`, so it stayed on screen. It only became
    // visible as a bug on the day the globe started out empty.
    expect(stylesheet).toContain(".legend[hidden] { display: none; }");
  });
});

/**
 * A FLOATING PANEL LIVES IN THE SCENE, NEVER UNDER THE RAIL.
 *
 * Sean: "I can't resize the data viewer. I can't grab the bottom right
 * corner." And then, which reframes it: "I shouldn't have to drag the data
 * explorer to the left to be able to grab the resize at the bottom. It
 * shouldn't ever overlap with the rail."
 *
 * The grip was never broken. Every clamp measured against `window.innerWidth`
 * and `window.innerHeight`, which include the 390 px rail, so a panel could be
 * dragged or sized until most of it lay under the rail's column - and
 * `.scene-shell` has `overflow: hidden`, so what was under the rail was
 * CLIPPED AWAY rather than merely covered. The bottom-right corner and its
 * grip were not on screen at all. Dragging left first is the workaround that
 * gave the bug away.
 *
 * Measured on the built page, at 1440x900 and at 1100x900, with a position and
 * size deliberately stored from a wider window (left 1350, 900x800):
 *
 *   restored          panel right 1046 vs rail left 1050   grip hit-tests
 *   dragged hard      panel right 1046 vs rail left 1050   grip hit-tests
 *   resized from it   288x123 grew to 368x376, stopped at the scene edge
 *
 * The same rule now governs the satellite stack, which had the same clamp and
 * therefore the same defect. Neither the legend nor the timeline is draggable
 * or resizable - `startCardDrag` and `startExplorerDrag`/`startExplorerResize`
 * are the only drag bindings in the file - and the legend measures inside the
 * scene box, so there was nothing to fix there.
 */
describe("the Data Explorer cannot be put where it cannot be grabbed", () => {
  it("clamps to the scene, not to the window", () => {
    expect(explorerSource).toContain("private sceneBounds()");
    // The exact regression: a clamp that measures the window measures the rail
    // with it. None may survive in the drag, resize or restore paths.
    const paths = ["private dragCard(", "private dragExplorer(", "private applyExplorerPosition(", "private applyExplorerSize(", "private resizeExplorer("];
    for (const start of paths) {
      const from = explorerSource.indexOf(start);
      expect(from, `${start} was not found`).toBeGreaterThan(-1);
      const body = explorerSource.slice(from, explorerSource.indexOf("\n  private ", from + 10));
      expect(body, `${start} still clamps against the window`).not.toContain("window.innerWidth");
      expect(body, `${start} still clamps against the window`).not.toContain("window.innerHeight");
      expect(body, `${start} does not use the scene box`).toContain("this.sceneBounds()");
    }
  });

  it("clamps on restore, so a stored position cannot survive the fix", () => {
    // A position stored from a wider window, or from before this change, is
    // re-clamped when the panel is placed rather than only when it is dragged.
    const from = explorerSource.indexOf("private applyExplorerPosition(");
    const body = explorerSource.slice(from, explorerSource.indexOf("\n  private ", from + 10));
    expect(body).toContain("Math.min(Math.max(4, this.explorerPosition.left), maxLeft)");
    expect(body).toContain("this.sceneBounds()");
  });
});
