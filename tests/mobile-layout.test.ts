import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import stylesSource from "../src/styles.css?raw";
import { describe, expect, it } from "vitest";

/**
 * The phone layout.
 *
 * Measured on a live iPhone 13 (390 x 664) on 2026-08-14 before any of this
 * was written: floating panels covered 84% of the viewport, and with one layer
 * switched on the globe was COMPLETELY hidden. The Data Explorer could not be
 * opened at all. These tests pin the fixes, because every one of them is
 * invisible from a desktop browser and none of them would be noticed again
 * until somebody picked up a phone.
 */
describe("the Data Explorer can be opened on a phone", () => {
  /**
   * The defect, exactly: `startExplorerDrag` returns immediately at the mobile
   * breakpoint — dragging a panel around a phone screen is not a thing — and
   * the fold/unfold lived at the END of that same drag lifecycle, in
   * `endExplorerDrag`, which returns early when there is no drag state. So
   * disabling the drag silently disabled the only way to expand the panel, and
   * a phone visitor could tap "DATA EXPLORER · 2 layers" forever with nothing
   * happening. No layer readings were reachable on mobile at all.
   *
   * Reproduced on the live site AND on commit 88237d6, so it long predates the
   * simplification work.
   */
  it("binds a plain tap on the head, not only the drag lifecycle", () => {
    const bind = explorerSource.slice(explorerSource.indexOf("private bindExplorerDrag()"));
    const body = bind.slice(0, bind.indexOf("\n  private startExplorerDrag"));
    expect(body).toMatch(/head\.addEventListener\("click"/);
    // And that tap must be the mobile path only, or the desktop head would
    // toggle twice per click — once from the drag end, once from the click.
    const click = body.slice(body.indexOf('head.addEventListener("click"'));
    expect(click).toMatch(/mobileCardLayoutQuery\.matches/);
    expect(click).toMatch(/setExplorerCollapsed\(!this\.explorerCollapsed\)/);
  });

  it("still refuses to treat a tap on the close button as a fold", () => {
    const bind = explorerSource.slice(explorerSource.indexOf('head.addEventListener("click"'));
    expect(bind.slice(0, 400)).toMatch(/closest\("button"\)/);
  });
});

describe("the globe keeps a real share of a phone screen", () => {
  /**
   * The layer sheet was `min(72svh, 670px)`. On a 664 px phone that is 478 px,
   * and with the Data Explorer's strip above it the globe had nothing left —
   * so a visitor toggling a layer could not see what the toggle did.
   */
  /**
   * The tablet breakpoint's own `min(72svh, 670px)` is deliberately left
   * alone — it is fine on an iPad — so this asserts the phone override exists
   * and comes later in the sheet, which is what makes it win the cascade.
   * The rendered result is measured for real in `mobile-audit.mjs`; a regex
   * over a stylesheet cannot tell you what a browser actually laid out.
   */
  it("bounds the layer sheet so the globe stays visible behind it", () => {
    expect(stylesSource).toMatch(/\.control-rail\s*\{\s*height:\s*min\(58svh,\s*520px\)/);
    expect(stylesSource.lastIndexOf("min(58svh, 520px)"))
      .toBeGreaterThan(stylesSource.indexOf("min(72svh, 670px)"));
  });

  it("gives the probe a phone-shaped sheet instead of a corner card", () => {
    const mobile = stylesSource.slice(stylesSource.lastIndexOf("The phone layout, rebuilt"));
    const probe = mobile.slice(mobile.indexOf(".probe-panel {"));
    const block = probe.slice(0, probe.indexOf("}"));
    expect(block).toMatch(/left:\s*12px/);
    expect(block).toMatch(/right:\s*12px/);
    expect(block).toMatch(/max-height:\s*46svh/);
    // and it must not land on top of the Data Explorer's collapsed strip
    expect(mobile).toMatch(/:has\(#data-viewer:not\(\[hidden\]\)\)\s*\.probe-panel/);
  });
});

describe("things a finger has to hit", () => {
  /** Seven controls were sharing a 206 px row — about 29 px each. */
  it("gives the view controls a 44 px touch target", () => {
    const mobile = stylesSource.slice(stylesSource.lastIndexOf("The phone layout, rebuilt"));
    expect(mobile).toMatch(/\.scene-tools button\s*\{[^}]*min-height:\s*44px/);
    expect(mobile).toMatch(/\.probe-close\s*\{[^}]*min-height:\s*44px/);
  });
});

describe("one sheet at a time", () => {
  /**
   * Measured on an iPhone 13 before this rule existed: with the layer sheet
   * open AND the readings expanded, the two panels together covered more than
   * the entire viewport and the globe was gone. A desktop can hold two windows
   * side by side; 390 px cannot. After the rule, expanding the readings drops
   * coverage from 66% to 44% and hands the globe back the majority of the
   * screen.
   */
  it("folds the layer sheet away when the readings are opened on a phone", () => {
    const fn = explorerSource.slice(explorerSource.indexOf("private setExplorerCollapsed("));
    const body = fn.slice(0, fn.indexOf("\n  private "));
    expect(body).toMatch(/!collapsed && this\.mobileCardLayoutQuery\.matches/);
    expect(body).toMatch(/closeMobilePanel\(\)/);
  });

  /**
   * The fold moved out of the click handler and into `openMobilePanel` on
   * 2026-08-20, when the phone gained a second door into the same sheet: both
   * doors have to fold the readings away, so the rule cannot live in either
   * button's listener. The invariant is unchanged - it is asserted where it now
   * lives.
   */
  /**
   * THERE IS NO READINGS WINDOW OVER THE GLOBE ON A PHONE ANY MORE, so there
   * is nothing for the panel to fold away. Sean, 2026-08-28: "only on
   * mobile... no more layer info window inside the viewing area. i want it on
   * the panel under the layer." What replaced the fold is a move: the same
   * card node goes into the space weather panel, under the row of the layer it
   * belongs to, behind that row's own caret.
   */
  it("moves each layer's card into the panel rather than over the globe", () => {
    const open = explorerSource.slice(explorerSource.indexOf("private updateDataViewer("));
    const body = open.slice(0, open.indexOf("\n  private ", 1));
    expect(body).toContain("const phone = this.phoneChromeQuery.matches;");
    expect(body).toContain("viewer.hidden = !active || phone;");
    expect(body).toContain("this.placeLayerCardsInRail(");
    // ...and the caret is the fold, on the row, only while the layer is on.
    expect(explorerSource).toContain('caret.className = "layer-card-caret";');
    expect(explorerSource).toContain("this.drawLayerCaret(layer, this.phoneLayerCardOpen.has(layer));");
  });

  /**
   * The grip used to be hidden below 430 px only, while the drag and resize it
   * belongs to are switched off below 600 px and the phone's fixed-strip
   * layout starts at 820 px — so between 431 and 600 px a reader was given a
   * resize corner on a panel that could not be resized. The whole panel is out
   * of the layout on a phone now, which settles the grip with it.
   */
  it("draws no readings window, and so no resize corner, on a phone", () => {
    // Sliced at the two doors, which is the block that carries the phone's
    // chrome — the 820 px one, not the 600 px one the older assertion here
    // reached for. The grip rule that used to be asserted lived below 430 px,
    // which is why it never covered the 431-600 px band it was written for.
    const phone = stylesSource.slice(stylesSource.indexOf(".mobile-tabs { order: 3"));
    const block = phone.slice(0, phone.indexOf("\n@media"));
    expect(block).toMatch(/\.data-viewer\s*\{\s*display:\s*none/);
    expect(block).toMatch(/\.layer-card-slot\[hidden\]\s*\{\s*display:\s*none/);
  });
});

describe("the narrow navigation is readable", () => {
  /**
   * Six equal columns on 390 px is 65 px each. "Fundamentals" and
   * "Connections" overran their cells and printed over their neighbours, so
   * the bar read "OrbitsWeather" / "ConnectTransit" as one smear.
   */
  /**
   * THE 390 px BUDGET THIS TEST USED TO ASSERT NO LONGER DESCRIBED ANYTHING.
   *
   * It was written when the nav ran as equal columns across the full width of a
   * phone screen, and it divided 390 px by however many destinations existed.
   * Sean's ruling of 2026-08-20 took the nav off the phone altogether —
   * `.topnav { display: none }` below 821 px, replaced by the two full-width
   * doors — so no `data-mobile-label` has been rendered at 390 px since. The
   * stale budget was still binding real decisions, though: it capped every
   * label at 7 characters and so forbade the 8-character noun "Explorer", which
   * is the label that lets the top nav carry the way back now that the floating
   * "Back to explorer" button is gone from the desktop layout.
   *
   * So the rule is restated against the band where these labels actually render
   * — 821 px, the narrowest width at which the nav is drawn at all — and as the
   * measurement that matters, which is whether the WHOLE ROW fits, not whether
   * each label is short. Measured on the built page at a 821 px viewport
   * (.agent-scratch-backbtn/navmeasure.mjs): the brand ends at 202 px, the
   * About button begins at 744 px, and each cell is 16 px of padding plus
   * 7.44 px per character of 11 px IBM Plex Mono at .04em tracking. That leaves
   * the row about 514 px to live in once the topbar's own 14 px gaps are taken
   * off each end.
   *
   * THE ROW IS NEARLY FULL. Eight destinations and fifty characters of label
   * come to 500 px of the 514 available — about two characters of slack for the
   * whole bar, not per label. A ninth destination, or one longer label, needs a
   * fresh measurement rather than a guess; this test is what will say so.
   */
  it("keeps the whole narrow nav row inside the space the topbar leaves it", () => {
    const labels = [...indexMarkup.matchAll(/data-mobile-label="([^"]+)"/g)].map((m) => m[1]!);
    expect(labels.length).toBeGreaterThanOrEqual(6);
    const CELL_PADDING = 16;
    const PX_PER_CHAR = 7.44;
    const AVAILABLE = 514;
    const rowWidth = labels.reduce((total, label) => total + CELL_PADDING + label.length * PX_PER_CHAR, 0);
    expect(rowWidth).toBeLessThanOrEqual(AVAILABLE);
  });

  /**
   * ...AND EXACTLY ONE LABEL IS PRINTED PER ITEM, WHICH IS NOT WHAT USED TO
   * HAPPEN.
   *
   * Between 821 and 1050 px the bar read "ExploreExplore", "NowCurrent
   * conditions", "EventsHistorical events", and pushed Transit off the
   * right-hand edge. The 1560 px rule sets `font-size: 0` on the nav item so
   * the long label collapses while `::before` prints the short one; the 1050 px
   * rule below it then set `font-size: 11px` on that same selector and brought
   * the long label back, so both rendered at once. Neither rule was wrong on
   * its own, which is why this went unnoticed for so long — so what is asserted
   * here is the collision, not either rule.
   */
  it("prints one label per nav item in the band where both rules apply", () => {
    const start = stylesSource.indexOf("@media (max-width: 1050px)");
    expect(start).toBeGreaterThan(-1);
    const block = stylesSource.slice(start, stylesSource.indexOf("@media", start + 10));
    expect(block).toMatch(/\.topnav \.nav-item \{[^}]*padding-inline/);
    expect(block).not.toMatch(/\.topnav \.nav-item \{[^}]*font-size/);
  });

  /**
   * Sean, on a handset, 2026-08-20: "Right now I have no way of finding
   * satellites or adding space weather layers." Both existed; both were behind
   * one 86 px button in the top-right corner that wrapped onto the nav's line
   * and read as a label stuck to it. The nav is not drawn on a phone any more
   * and its row carries two named doors instead, so this pins the three things
   * that made the old arrangement unfindable:
   *
   *   - the nav is display:none below 820 px, not merely shrunk;
   *   - there are two doors, and one of them names space weather;
   *   - the space-weather door cannot open onto a hidden panel - and since
   *     2026-08-28 it cannot, because nothing hides a rail section any more.
   */
  it("draws no top nav on a phone, and two named doors in its place", () => {
    // EVERY 820 px block, not the first one. The sheet carries four of them
    // now — the reading pages narrowed their card grids at the same
    // breakpoint, and one of those was inserted ABOVE the phone layout, so
    // `indexOf` started returning `.door-grid { grid-template-columns: 1fr }`
    // and this test failed describing a block it had never meant. The phone
    // layout is whatever all of them jointly say.
    const block = [...stylesSource.matchAll(/@media \(max-width: 820px\) \{/g)]
      .map((match) => {
        const rest = stylesSource.slice(match.index!);
        const end = rest.indexOf("\n@media");
        return end === -1 ? rest : rest.slice(0, end);
      })
      .join("\n");
    expect(block).toMatch(/\.topnav \{ display: none; \}/);
    expect(block).toMatch(/\.mobile-tabs \{[^}]*grid-template-columns: 1fr 1fr/);
    expect(indexMarkup).toContain('id="mobile-panel-toggle"');
    expect(indexMarkup).toContain('id="mobile-weather-toggle"');
    // A finger-sized target, not the 36 px strip the single toggle had.
    expect(block).toMatch(/\.mobile-panel-toggle \{[^}]*min-height: 42px/);
  });

  it("opens either door without unhiding a panel or switching anything off", () => {
    const open = explorerSource.slice(explorerSource.indexOf("private openMobilePanel("));
    const body = open.slice(0, open.indexOf("\n  private "));
    // THE HAZARD IS REMOVED RATHER THAN HANDLED, so these assertions are
    // inverted rather than deleted.
    //
    // This used to force Combined mode on the way in, never the section's own
    // mode, for two reasons: the asked-for half of the rail could be `hidden`
    // by the mode, and entering Satellites mode called `hideAllLayers()`, so
    // the satellites door threw away layers the reader had switched on. Sean,
    // 2026-08-28, ruled that second behaviour out by name - "going into the
    // space weather rail on desktop or panel in mobile doesn't take the
    // satellite off or a plotted orbit off" - and Explorer Mode was retired
    // with it.
    //
    // So: no mode call to get right, and no section left `hidden` for one to
    // unhide. A reintroduced `hidden` on a rail section would now be invisible
    // for ever, which is why the markup is checked here and not only the code.
    expect(body).not.toContain("setMode");
    expect(body).not.toContain("sectionHidden");
    expect(body).not.toMatch(/querySelector[\s\S]*data-mode-panel/);
    expect(explorerSource).not.toContain("private setMode(");
    expect(indexMarkup).not.toMatch(/data-mode-panel="[a-z]+" hidden/);
    // ...and it still lands the reader at the top of the rail they asked for.
    expect(body).toMatch(/scrollTop/);
  });

  it("keeps every nav destination labelled, with no duplicates", () => {
    const views = [...indexMarkup.matchAll(/data-view="([^"]+)"[^>]*data-mobile-label/g)].map((m) => m[1]!);
    const labels = [...indexMarkup.matchAll(/data-mobile-label="([^"]+)"/g)].map((m) => m[1]!);
    expect(views.length).toBe(labels.length);
    expect(new Set(views).size).toBe(views.length);
  });
});
