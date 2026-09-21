import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import stylesSource from "../src/styles.css?raw";
import { describe, expect, it } from "vitest";

/**
 * THE RAIL CHROME, on both surfaces, from Sean's 2026-08-28 reading of the
 * site on a desktop and on a handset.
 *
 * Desktop: "i want the rails for satellites and space weather to be two tabs
 * on the right that if clicked expand the rail and if clicked again collapse
 * it, where the site starts with them collapsed."
 *
 * Phone: "there's two buttons at the top of the page... but what it is
 * bringing up is a combined rail in both cases. let's just make independent
 * ones."
 *
 * Every one of these is invisible from a passing glance at either surface —
 * a rail that opens by default still looks right, and a door that opens the
 * wrong half of one column still looks right — so they are pinned here.
 */
describe("the desktop rail is a drawer behind two tabs", () => {
  it("puts both tabs in the page, as buttons that say whether they are open", () => {
    expect(indexMarkup).toContain('id="rail-tab-satellites" data-rail-tab="satellites" aria-controls="control-rail" aria-expanded="false"');
    expect(indexMarkup).toContain('id="rail-tab-environment" data-rail-tab="environment" aria-controls="control-rail" aria-expanded="false"');
    // Written closed in the markup, because the site loads closed. A tab that
    // shipped `aria-expanded="true"` would announce a rail nobody had opened.
    expect(indexMarkup).not.toContain('data-rail-tab="satellites" aria-controls="control-rail" aria-expanded="true"');
  });

  it("gives the drawer its own grid track, at zero until a tab is pressed", () => {
    expect(stylesSource).toContain("grid-template-columns: minmax(0, 1fr) auto var(--rail-column)");
    expect(stylesSource).toContain(".workspace { --rail-column: 0px;");
    expect(stylesSource).toContain(".workspace[data-rail-open] { --rail-column: var(--rail-width); }");
  });

  /**
   * A COLLAPSED DRAWER MUST NOT BE TABBABLE. At zero width the rail's search
   * box, thirteen layer switches and the whole catalog filter set are still in
   * the tab order and still in the accessibility tree, which is a keyboard
   * reader walking through controls that are not on screen. `visibility` is
   * the one property that takes them out of both.
   */
  it("takes the collapsed drawer out of the tab order, not merely off screen", () => {
    const desktop = stylesSource.slice(stylesSource.indexOf("@media (min-width: 821px) {\n  .workspace:not([data-rail-open])"));
    expect(desktop.slice(0, desktop.indexOf("}"))).toMatch(/\.control-rail\s*\{\s*visibility:\s*hidden/);
  });
});

describe("each rail holds only its own sections", () => {
  it("marks every section with the rail it belongs to", () => {
    const rail = indexMarkup.slice(indexMarkup.indexOf('id="control-rail"'));
    const body = rail.slice(0, rail.indexOf("</aside>"));
    expect(body).toMatch(/class="rail-section conditions-section" data-rail-panel="environment"/);
    expect(body).toMatch(/class="rail-section environment-section" data-rail-panel="environment"/);
    expect(body).toMatch(/class="rail-section search-section"[^>]*data-rail-panel="satellites"/);
    expect(body).toMatch(/class="rail-section favorites-section"[^>]*data-rail-panel="satellites"/);
  });

  it("draws only the open rail's sections, on both surfaces", () => {
    expect(stylesSource).toContain('.control-rail[data-open-panel="satellites"] .rail-section:not([data-rail-panel="satellites"]),');
    expect(stylesSource).toContain('.control-rail[data-open-panel="environment"] .rail-section:not([data-rail-panel="environment"]) { display: none; }');
  });

  /**
   * ONE FIELD BEHIND FOUR CONTROLS. Each of them owns one rail: pressing it
   * over its own rail closes it, pressing it over the other switches. The
   * defect this replaces had `#mobile-panel-toggle` closing whatever was open,
   * so the Satellites door read "Close panel" over an open space weather
   * panel — a button claiming to close something it had not opened.
   */
  it("gives every control one rail of its own", () => {
    expect(explorerSource).toMatch(/railControls[\s\S]{0,320}\["mobile-panel-toggle", "satellites"\][\s\S]{0,320}\["rail-tab-environment", "environment"\]/);
    expect(explorerSource).toContain("if (this.mobilePanelSection === section) this.closeMobilePanel();");
    expect(explorerSource).toContain('button.textContent = open ? "Close panel" : name;');
  });
});

/**
 * WHAT A PHONE DOES NOT CARRY. Sean found this as unreachable page: "there is
 * content below the viewing area, but i can't move the contents of the screen
 * to get to it. it looks like it starts off with 'radio propagation and
 * advanced fields'." It was unreachable because a stray `</div>` in the layer
 * list had closed `#app`, leaving those nodes as children of <body> below a
 * viewport that is `overflow: hidden` at this breakpoint.
 */
describe("the phone page is pared down, and by removal", () => {
  it("keeps the rail's own tail inside the rail", () => {
    const rail = indexMarkup.slice(indexMarkup.indexOf('id="control-rail"'));
    const body = rail.slice(0, rail.indexOf("</aside>"));
    expect(body).toContain('class="advanced-environment-details"');
    expect(body).toContain('class="method-link"');
    expect(body).toContain('class="rail-footer"');
  });

  it("takes the phone's three off the page rather than hiding them", () => {
    const strip = explorerSource.slice(explorerSource.indexOf("private applyPhonePageStrip()"));
    const body = strip.slice(0, strip.indexOf("\n  private ", 1));
    expect(body).toContain('"#control-rail .advanced-environment-details"');
    expect(body).toContain('"#control-rail .method-link"');
    expect(body).toContain('"#control-rail .rail-footer"');
    expect(body).toContain("node.replaceWith(anchor);");
    // ...and puts them back on the way into landscape, which crosses 820 px
    // into the desktop layout. A mobile-only removal that a rotation cannot
    // undo is a deletion.
    expect(body).toContain("anchor.replaceWith(node)");
  });

  /**
   * The two switches inside the advanced fold are the document's only copies.
   * `hideAllLayers()` reads every id in `layerCheckboxIds` through `byId`, and
   * the guided energy-chain walkthrough drives them by clicking them, so a
   * removal that took them with it would throw on the next layer reset.
   */
  it("keeps the advanced fold's two checkboxes attached", () => {
    const strip = explorerSource.slice(explorerSource.indexOf("private applyPhonePageStrip()"));
    const body = strip.slice(0, strip.indexOf("\n  private ", 1));
    expect(body).toContain('["layer-drap", "layer-groundField"].forEach');
    expect(body).toContain('holder.id = "phone-stripped-controls"');
  });
});
