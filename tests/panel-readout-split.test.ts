import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import stylesSource from "../src/styles.css?raw";
import * as THREE from "three";
import { describe, expect, it } from "vitest";
import type { EnvironmentLegendSpec } from "../src/main";
import { coverageLandingNotice, coverageLandingTarget, dataViewerSections, keyCardBar, layerCardIsOpen, layerCoverageNotice, layerDetailIsOpen, ringCurrentLegendSpec, standingReadings, splitLeadSentence, utcMinuteLabel } from "../src/main";
import { kpDstReconciliation, stormHeadline } from "../src/storm-panel";
import {
  DEFAULT_VIEW_SCENE_RADIUS,
  EARTH_SCENE_RADIUS,
  VIEW_EDGE_MARGIN_FRACTION,
  boundingRadiusFromOrigin,
  distanceToFrameSceneRadius,
  satelliteDisplayRadius,
  shouldReframeView,
} from "../src/globe";

/**
 * These exercise the exported rules the running interface calls, not copies of
 * them: ExplorerApp.layerDetailOpen delegates to layerDetailIsOpen,
 * ExplorerApp.layerUnavailable delegates to layerCoverageNotice, and
 * Globe.frameActiveLayers delegates to shouldReframeView. This codebase has a
 * documented history of green tests over code that never runs, so the decision
 * logic was pulled out specifically so a test can reach the real path.
 */

/**
 * The settings rule USED to be "open when this is the only layer on screen",
 * on the reading that one layer cannot crowd anything. Measured on the built
 * bundle, that reading was wrong, and these assertions now pin the reason
 * rather than the old behaviour: with only the magnetosphere switched on, its
 * thirteen controls occupied 746 px of the Data Explorer — 3.9x the 193 px of
 * readings in the same card, and more than the whole 432 px window the panel
 * gets on a 900 px screen. The reader asked for a field and was handed a
 * settings dialog.
 */
describe("which layer detail starts open", () => {
  it("keeps settings folded even when the layer is the only one on screen, because one layer's settings can be thirteen controls", () => {
    expect(layerDetailIsOpen(undefined)).toBe(false);
  });

  it("keeps them folded at every layer count, so no count is the crowded one", () => {
    expect(layerDetailIsOpen(undefined)).toBe(false);
  });

  it("always honours a remembered choice, in both directions", () => {
    expect(layerDetailIsOpen(true)).toBe(true);
    expect(layerDetailIsOpen(false)).toBe(false);
  });
});

/**
 * Sean, given a screenshot of the panel with one layer on: "On the data
 * explorer - I should only see a rectangle for Thermosphere height and a box
 * that says NOAA MODEL + FORECAST when I have the thermosphere height
 * plotted."
 *
 * So every card opens SHUT, and that overrules the rule this suite used to
 * pin. The old rule expanded the layer switched on most recently and folded
 * the rest, which was written against a real measurement - cards all open cost
 * 1,403 px of content at one layer, 2,423 px at two and 2,773 px at three, in
 * a 432 px window - and solved it by making the panel one sprawl and two
 * stubs. Three layers on is three rectangles of equal rank.
 *
 * What makes shutting them safe is that the evidence badge is in the card's
 * HEAD: shut, the rectangle still states the class of claim the layer makes.
 * Since the rail's chips went, this is the ONLY surface that does, which is
 * why the assertion below is about honesty and not about layout.
 */
describe("which layer card starts expanded", () => {
  it("opens none of them, however many layers are on", () => {
    expect(layerCardIsOpen(undefined)).toBe(false);
  });

  it("always honours a card the reader opened or shut by hand", () => {
    expect(layerCardIsOpen(false)).toBe(false);
    expect(layerCardIsOpen(true)).toBe(true);
  });

  it("keeps the badge in the head, which is what a shut card is allowed to be", () => {
    // The whole justification for a shut card in one assertion: the head is
    // outside the body the collapse hides.
    const template = indexMarkup.slice(indexMarkup.indexOf('<template id="layer-card-template">'));
    const head = template.slice(0, template.indexOf('<div class="sat-card-body"'));
    expect(head).toContain("data-card-mission");
    expect(stylesSource).toContain(".sat-card.is-collapsed .sat-card-body { display: none; }");
  });

  it("opens the panel itself expanded, or the badge would be one click away", () => {
    // A folded panel and a shut card together would mean a reader can draw a
    // MODEL layer and never be told it is one. The storage key is v2 so a
    // stored "collapsed" from before this change cannot reintroduce that.
    expect(explorerSource).toContain('private explorerCollapsed = false;');
    expect(explorerSource).toContain('storageGet("local", "space-explorer-data-explorer-collapsed-v2") === "1"');
    expect(explorerSource).not.toContain("data-explorer-collapsed-v1");
  });
});

/**
 * THE CLOCK TEST, which is what the Data Explorer is for.
 *
 * Sean, with the magnetosphere, the ring current and the solar wind on: "See
 * how the data explorer is extremely crammed and full of information... It is
 * just way too complicated and overwhelming." He was right, and the panel had
 * 2,773 px of content in a 432 px window to prove it. The rule that came out of
 * it: a value that cannot move when the clock moves is not a reading, so it is
 * printed on Data & methods instead — rendered from this same spec, so it stays
 * a computed figure rather than being frozen into prose.
 *
 * These drive `ringCurrentLegendSpec` because that card was the worst case: 12
 * readings, 756 px, on a layer whose whole point is that nothing in it is
 * measured.
 */
describe("the clock test: what the Data Explorer prints and what Learn prints", () => {
  const spec = ringCurrentLegendSpec(null);
  const readings = dataViewerSections(spec).readings.map(([label]) => label);
  const standing = standingReadings(spec).map(([label]) => label);

  it("keeps only clock-driven numbers, plus the caveat, on the operational card", () => {
    // With no drive there is one driven row to report — the reason there is no
    // drive — so the card is the caveat and that row, and nothing else.
    expect(readings[0]).toBe("WHAT IS MEASURED HERE");
    expect(readings.length).toBeLessThanOrEqual(2);
  });

  it("NEVER moves the caveat, however standing it is", () => {
    // "NOTHING · DST IS THE ONLY RING-CURRENT MEASUREMENT THIS SITE CARRIES"
    // is as clock-invariant as anything in this card and it stays, because a
    // panel is not made simpler by moving the sentence that says what it does
    // not know. This is the assertion that stops the next round of tidying
    // from taking a caveat with it.
    expect(dataViewerSections(spec).readings[0]![1]).toContain("NOTHING");
    expect(standing).not.toContain("WHAT IS MEASURED HERE");
  });

  it("moves the standing physics rather than deleting it", () => {
    expect(standing).toContain("DRIFT SENSE");
    expect(standing).toContain("ENERGISATION BY INWARD TRANSPORT");
    expect(standing).toContain("ION DRIFT PERIOD AT L 4");
    expect(standing).toContain("COROTATION vs GRADIENT DRIFT AT L 4");
  });

  it("keeps the standing figures computed, not retyped, so they still carry their numbers", () => {
    const energisation = standingReadings(spec).find(([label]) => label === "ENERGISATION BY INWARD TRANSPORT")![1];
    // 10 keV at L 8 becomes 80 keV at L 4 because mu is conserved and B goes
    // as L^-3. If this were prose in content.ts it would freeze at the default
    // ion and stop following the energy selector.
    expect(energisation).toContain("keV at L 4");
    expect(energisation).toContain("L⁻³");
  });

  it("gives every standing figure a door out of the panel it left", () => {
    // The layer's card carries a "How this is built" button only when the
    // layer is mapped to a method card on Data & methods. A layer that moved
    // readings off its card without one would have deleted them as far as any
    // reader is concerned.
    expect(explorerSource).toContain("ringCurrent: \"method-ring-current\"");
    expect(explorerSource).toContain("mountLayerStandingReadings");
  });

  it("prints no value in both places", () => {
    for (const label of standing) expect(readings).not.toContain(label);
  });
});

/**
 * The evidence badge is on screen whether a card is open or shut. That is the
 * condition on which folding a card is allowed at all: this site's rule is that
 * a layer may never imply it is a measurement when it is not, and a folded card
 * showing only "Ring current — how it forms" would do exactly that.
 */
describe("a folded layer card still states its evidence class", () => {
  it("puts the badge in the card head, not the body", () => {
    const head = indexMarkup.slice(indexMarkup.indexOf("layer-card-template"));
    const headBlock = head.slice(head.indexOf("sat-card-head"), head.indexOf("sat-card-body"));
    expect(headBlock).toContain("data-card-mission");
    expect(headBlock).toContain("layer-status");
  });

  it("styles it as the evidence stamp, so the class shows in its own colour", () => {
    expect(explorerSource).toContain("badge.className = `layer-status ${spec.evidence}`");
    expect(stylesSource).toContain(".data-card[data-layer-card] .sat-card-head .layer-status");
  });

  it("keeps the head visible when the card is collapsed", () => {
    // Only the body is hidden by the collapse rule; if that ever became
    // `.sat-card.is-collapsed { display: none }` the badge would go with it.
    expect(stylesSource).toContain(".sat-card.is-collapsed .sat-card-body { display: none; }");
  });
});

/**
 * Readings before settings. The reader came for the number; a control is
 * something they go looking for.
 */
describe("the order of a layer card's sections", () => {
  // index.html holds more than one <template>, so the end of this one is found
  // from the start of this one, not from the start of the document.
  const from = indexMarkup.indexOf("layer-card-template");
  const template = indexMarkup.slice(from, from + indexMarkup.slice(from).indexOf("</template>"));

  it("has a layer card template to read at all", () => {
    expect(from).toBeGreaterThan(-1);
    expect(template).toContain("data-card-readings");
  });

  it("puts readings above settings", () => {
    expect(template.indexOf("data-card-section=\"readings\"")).toBeGreaterThan(-1);
    expect(template.indexOf("data-card-section=\"readings\"")).toBeLessThan(template.indexOf("data-card-controls"));
  });

  it("ships the settings section folded", () => {
    const controls = template.slice(template.indexOf("data-card-section=\"controls\""));
    expect(controls.slice(0, controls.indexOf(">"))).not.toContain(" open");
  });
});

/**
 * Sean: "what are those triangles that show up on the right side of each
 * layer? they make the data viewer pop up. I don't like that."
 *
 * The caret was a shortcut from a layer's rail row into that layer's card in
 * the Data Explorer. It was a second door to a panel that already appears the
 * moment a layer is drawn, and it was not an obvious one - a bare glyph whose
 * only label was an aria-label. It is gone, and so is the policy function that
 * decided when to show it. What replaces it is nothing: a layer's settings are
 * inside that layer's card, beside that layer's readings.
 *
 * These assert the removal rather than the behaviour, because a shortcut is
 * exactly the kind of thing a later change reintroduces "for convenience".
 */
describe("a layer row has no second control on it", () => {
  const railStart = indexMarkup.indexOf('id="control-rail"');
  const rail = indexMarkup.slice(railStart, indexMarkup.indexOf("</aside>", railStart));

  it("draws no caret on any layer row", () => {
    expect(rail).not.toContain("layer-caret");
    expect(rail).not.toContain("data-layer-caret");
  });

  it("keeps no machinery for one either", () => {
    expect(explorerSource).not.toContain("applyLayerCarets");
    expect(explorerSource).not.toContain("revealLayerControls");
    expect(explorerSource).not.toContain("Open this layer's settings in the data viewer");
    expect(stylesSource).not.toContain(".layer-caret");
  });

  it("leaves every layer's settings reachable, in that layer's own card", () => {
    // The route the caret used to short-circuit, which was always the real one.
    expect(indexMarkup).toContain('data-card-controls-slot');
    expect(explorerSource).toContain("slot.append(panel)");
  });
});

describe("the no-data notice", () => {
  // The real coupled geospace run published on 2026-08-07 covered 100 minutes.
  const geospace = {
    validFrom: "2026-08-07T22:00:00Z",
    validTo: "2026-08-07T23:40:00Z",
    sourceLabel: "The coupled NOAA geospace run",
  };

  it("says what is missing, why, and offers the nearest covered time", () => {
    const notice = layerCoverageNotice({
      title: "RBE electron belt · multi-pitch mapped volume",
      // -455 minutes from 23:59Z, the exact case in Sean's screenshots.
      selectedAtIso: "2026-08-07T16:44:00Z",
      window: geospace,
    });
    expect(notice.headline).toBe("No rbe electron belt · multi-pitch mapped volume for 2026-08-07 16:44 UTC.");
    // Before the archive starts: nobody is late, the history simply does not
    // reach back that far, and the words must not imply a feed is overdue.
    expect(notice.because).toContain("only goes back to 2026-08-07 22:00 UTC");
    expect(notice.because).not.toContain("has not published");
    // A minute inside the window, not on its boundary.
    expect(notice.jumpToIso).toBe("2026-08-07T22:01:00.000Z");
    expect(notice.jumpLabel).toBe("Go to 2026-08-07 22:01 UTC");
  });

  it("points forward to the end of the window when the selected time is past it", () => {
    const notice = layerCoverageNotice({
      title: "D-region HF absorption",
      selectedAtIso: "2026-08-08T09:00:00Z",
      window: geospace,
    });
    // Past the end is the ordinary case and the honest words for it are that
    // the upstream feed has not published yet. Sean asked for exactly this:
    // "If they scroll into the present just put a message on then that says
    // NOAA hasn't published yet." Measured the day he asked, NOAA's OVATION
    // product had published nothing for 2.09 hours and our newest frame was
    // identical to theirs — so a blank layer with no reason reads as our bug
    // when it is not one.
    expect(notice.because).toContain("stops at 2026-08-07 23:40 UTC");
    expect(notice.because).toContain("the next frame has not arrived yet");
    // The label is a noun phrase naming a RECORD, so the verb must belong to a
    // record. "…history has not published…" used the same verb twice and made
    // the record the publisher.
    expect(notice.because).not.toMatch(/published[^.]*has not published/);
    expect(notice.jumpToIso).toBe("2026-08-07T23:39:00.000Z");
  });

  it("does not blame the feed for a time before the archive begins", () => {
    // The two directions are different situations and only one of them is
    // anybody's fault. Getting this backwards would tell a reader that NOAA
    // was late for a moment in 2019.
    const past = layerCoverageNotice({
      title: "Aurora viewing probability",
      selectedAtIso: "2026-08-01T00:00:00Z",
      window: geospace,
    });
    const future = layerCoverageNotice({
      title: "Aurora viewing probability",
      selectedAtIso: "2026-08-09T00:00:00Z",
      window: geospace,
    });
    expect(past.because).toContain("only goes back to");
    expect(future.because).toContain("stops at");
    expect(past.because).not.toContain("stops at");
    expect(future.because).not.toContain("only goes back to");
  });

  it("never uses the jargon that made the old five-box state unreadable", () => {
    const notice = layerCoverageNotice({
      title: "Aurora viewing probability",
      selectedAtIso: "2026-08-06T08:02:00Z",
      window: { validFrom: "2026-08-06T22:43:00Z", validTo: "2026-08-08T00:33:00Z", sourceLabel: "NOAA's published OVATION history" },
    });
    const wording = `${notice.headline} ${notice.because}`;
    expect(wording).not.toMatch(/BEFORE COVERAGE|AFTER COVERAGE|HIDDEN|NO DATA FOR SELECTED UTC/);
    // The honesty has to survive the plain language.
    expect(wording).toContain("Rather than draw a nearby frame and call it this one, the layer is left off.");
  });

  it("still says something useful when the layer publishes no window at all", () => {
    const notice = layerCoverageNotice({
      title: "Solar wind and IMF",
      selectedAtIso: "2026-08-06T08:02:00Z",
      window: null,
    });
    expect(notice.headline).toContain("2026-08-06 08:02 UTC");
    expect(notice.jumpToIso).toBeUndefined();
  });

  it("degrades honestly rather than printing Invalid Date", () => {
    expect(utcMinuteLabel("not a time")).toBe("an unknown time");
    const notice = layerCoverageNotice({
      title: "Total electron content",
      selectedAtIso: "2026-08-07T16:44:00Z",
      window: { validFrom: "nonsense", validTo: "nonsense", sourceLabel: "The GloTEC field" },
    });
    expect(notice.jumpToIso).toBeUndefined();
    expect(notice.because).toContain("does not cover the time you picked");
  });
});

describe("making room for a layer instead of shifting the globe sideways", () => {
  const base = { autoFrameDistance: 367, targetOffCentre: false };

  it("pulls back whenever the layer would not fit in the current view", () => {
    expect(shouldReframeView({ ...base, wantedDistance: 900, currentDistance: 367 })).toBe(true);
  });

  it("pulls back even after a manual zoom, because otherwise the layer is invisible", () => {
    expect(shouldReframeView({ ...base, wantedDistance: 900, currentDistance: 200 })).toBe(true);
  });

  it("does not creep back out to a framing the visitor deliberately zoomed past", () => {
    // Solar wind was switched off, so the layers need less room than before —
    // but the visitor is at 200 by choice, so leave them there.
    expect(shouldReframeView({ autoFrameDistance: 900, targetOffCentre: false, wantedDistance: 367, currentDistance: 200 })).toBe(false);
  });

  it("does come back in when the visitor has not touched the zoom", () => {
    expect(shouldReframeView({ autoFrameDistance: 900, targetOffCentre: false, wantedDistance: 367, currentDistance: 900 })).toBe(true);
  });

  it("re-frames unconditionally when the orbit target has drifted off Earth's centre", () => {
    expect(shouldReframeView({ ...base, wantedDistance: 367, currentDistance: 367, targetOffCentre: true })).toBe(true);
  });

  it("does nothing at all when the framing is already right", () => {
    expect(shouldReframeView({ ...base, wantedDistance: 367, currentDistance: 367.4 })).toBe(false);
  });

  it("obeys the reset control even when it would otherwise leave the view alone", () => {
    expect(shouldReframeView({ ...base, wantedDistance: 367, currentDistance: 200, force: true })).toBe(true);
  });
});

describe("the framing radius", () => {
  it("opens on Earth plus the shell the ionospheric surfaces are drawn in", () => {
    expect(DEFAULT_VIEW_SCENE_RADIUS).toBeCloseTo(satelliteDisplayRadius(600), 6);
    // "Not much, but just a touch" wider than the globe itself.
    expect(DEFAULT_VIEW_SCENE_RADIUS).toBeGreaterThan(EARTH_SCENE_RADIUS);
    expect(DEFAULT_VIEW_SCENE_RADIUS).toBeLessThan(EARTH_SCENE_RADIUS * 1.4);
  });

  it("measures how far a layer reaches from Earth's centre, not how big it is", () => {
    // A slab sitting far out on the Sun-Earth line: framing has to hold its far
    // edge, because Earth stays in the middle of the picture.
    const box = new THREE.Box3(new THREE.Vector3(200, -20, -20), new THREE.Vector3(480, 20, 20));
    expect(boundingRadiusFromOrigin(box)).toBeCloseTo(Math.hypot(480, 20, 20), 6);
  });

  it("reports nothing for an empty box rather than a misleading zero-radius hit", () => {
    expect(boundingRadiusFromOrigin(new THREE.Box3())).toBe(0);
  });
});

/**
 * The site's camera is a 42-degree vertical FOV; the desktop scene beside the
 * rail measures 1050x832 and a 390 px phone in portrait is taller than it is
 * wide. `occupiedFraction` is the measurement Sean's complaint is about: what
 * share of the frame's short side a shell of `radius`, centred on Earth,
 * actually draws across at a given camera distance — through the sphere's
 * TANGENT cone, which is what a camera sees, and not through its equator.
 */
const FOV_DEGREES = 42;
const occupiedFraction = (radius: number, distance: number, aspect: number) => {
  const halfVertical = THREE.MathUtils.degToRad(FOV_DEGREES) / 2;
  const halfHorizontal = Math.atan(Math.tan(halfVertical) * aspect);
  const halfAngle = Math.min(halfVertical, halfHorizontal);
  return Math.tan(Math.asin(radius / distance)) / Math.tan(halfAngle);
};

describe("the padding the framing leaves around what is drawn", () => {
  const desktopAspect = 1050 / 832;
  const phoneAspect = 390 / 428;

  it("leaves the declared band clear on each edge, on desktop and on a phone", () => {
    for (const aspect of [desktopAspect, phoneAspect]) {
      const radius = DEFAULT_VIEW_SCENE_RADIUS;
      const distance = distanceToFrameSceneRadius(radius, FOV_DEGREES, aspect);
      expect(occupiedFraction(radius, distance, aspect))
        .toBeCloseTo(1 - 2 * VIEW_EDGE_MARGIN_FRACTION, 6);
    }
  });

  it("does not measure the sphere across its equator, which is the bug this fixes", () => {
    // The old rule was (radius * 1.1) / tan(halfAngle) — a 10% margin on
    // paper. What it actually left was 1.7%: the thermosphere shell, whose
    // drawn edge sits exactly at the framed radius, was measured at 96.5% of
    // the 832 px desktop scene, 13 px of sky above it. Pinned so nobody
    // re-derives the tangent version and calls the number a margin again.
    const radius = DEFAULT_VIEW_SCENE_RADIUS;
    const halfAngle = THREE.MathUtils.degToRad(FOV_DEGREES) / 2;
    const oldRuleDistance = (radius * 1.1) / Math.tan(halfAngle);
    expect(occupiedFraction(radius, oldRuleDistance, desktopAspect)).toBeGreaterThan(0.96);
    expect(occupiedFraction(radius, distanceToFrameSceneRadius(radius, FOV_DEGREES, desktopAspect), desktopAspect))
      .toBeLessThan(0.91);
  });

  it("is a fraction of the frame, so the globe and the magnetotail are padded alike", () => {
    // A 128-unit shell and a 740-unit cut corner are a factor of six apart on
    // the shared ruler. A fixed padding readable around one is invisible
    // around the other; this one leaves the same band around both.
    const near = distanceToFrameSceneRadius(128, FOV_DEGREES, desktopAspect);
    const far = distanceToFrameSceneRadius(740, FOV_DEGREES, desktopAspect);
    expect(far / near).toBeCloseTo(740 / 128, 6);
    expect(occupiedFraction(128, near, desktopAspect))
      .toBeCloseTo(occupiedFraction(740, far, desktopAspect), 6);
  });

  it("stays a small correction rather than a re-scale of the whole scene", () => {
    // Sean asked for "some padding", not a smaller globe: "it isn't
    // unacceptable but it is close enough that the user will have to zoom out
    // a little". One press of the zoom-out control is 1.28x. The correction
    // has to be a fraction of that, or the fix costs more of the globe than
    // the crowding did.
    const radius = DEFAULT_VIEW_SCENE_RADIUS;
    const halfAngle = THREE.MathUtils.degToRad(FOV_DEGREES) / 2;
    const oldRuleDistance = (radius * 1.1) / Math.tan(halfAngle);
    const ratio = distanceToFrameSceneRadius(radius, FOV_DEGREES, desktopAspect) / oldRuleDistance;
    expect(ratio).toBeGreaterThan(1);
    expect(ratio).toBeLessThan(1.1);
  });

  it("never drives the camera to infinity if the margin is ever set past half the frame", () => {
    expect(Number.isFinite(distanceToFrameSceneRadius(128, FOV_DEGREES, desktopAspect, 0.5))).toBe(true);
    expect(Number.isFinite(distanceToFrameSceneRadius(128, FOV_DEGREES, desktopAspect, 0.9))).toBe(true);
  });

  it("keeps the deepest drawn point inside the dolly limit the controls allow", () => {
    // The SWMF cut-plane corner draws near 740 scene units on the teaching
    // ruler, and the controls stop at 2,500. If framing it cost more than
    // that the deepest layer would frame against the limit, not against the
    // rule, and the margin would silently stop being the margin.
    expect(distanceToFrameSceneRadius(740, FOV_DEGREES, desktopAspect)).toBeLessThan(2500);
    expect(distanceToFrameSceneRadius(740, FOV_DEGREES, phoneAspect)).toBeLessThan(2500);
    // True distance: the same corner at 65.2 Re draws at 6,520, against a
    // 21,800 limit.
    expect(distanceToFrameSceneRadius(6520, FOV_DEGREES, desktopAspect)).toBeLessThan(21800);
    expect(distanceToFrameSceneRadius(6520, FOV_DEGREES, phoneAspect)).toBeLessThan(21800);
  });
});

describe("the satellite description in the left-hand card", () => {
  it("leads with the honesty disclosure and folds the reasoning behind it", () => {
    const { lead, rest } = splitLeadSentence(
      "Its purpose has not been independently verified for this object: the positioning, navigation, or timing"
      + " label comes from a programme-name pattern, not from a source checked against this spacecraft."
      + " What is established is its orbit: a medium Earth orbit, the band used by navigation constellations"
      + " and some data relay.",
    );
    expect(lead).toBe(
      "Its purpose has not been independently verified for this object: the positioning, navigation, or timing"
      + " label comes from a programme-name pattern, not from a source checked against this spacecraft.",
    );
    expect(rest).toBe(
      "What is established is its orbit: a medium Earth orbit, the band used by navigation constellations"
      + " and some data relay.",
    );
  });

  it("keeps taking sentences until the lead is worth reading on its own", () => {
    const { lead, rest } = splitLeadSentence("A GPS satellite. It broadcasts the navigation signal used for positioning and timing worldwide.");
    expect(lead).toBe("A GPS satellite. It broadcasts the navigation signal used for positioning and timing worldwide.");
    expect(rest).toBe("");
  });

  it("never drops text: lead and rest always reconstruct the description", () => {
    const source = "One. Two sentence here. Three sentence there. Four to finish the paragraph off.";
    const { lead, rest } = splitLeadSentence(source);
    expect([lead, rest].filter(Boolean).join(" ")).toBe(source);
  });

  it("leaves a single-sentence description with nothing folded away", () => {
    const { lead, rest } = splitLeadSentence("A low-Earth-orbit spacecraft in SpaceX's Starlink constellation, relaying broadband internet traffic.");
    expect(rest).toBe("");
    expect(lead).toContain("Starlink");
  });

  it("survives an empty description without inventing a disclosure control", () => {
    expect(splitLeadSentence("   ")).toEqual({ lead: "", rest: "" });
  });
});

/**
 * The legend, the data viewer, and the rail.
 *
 * The complaint these answer: the key over the globe was carrying a colour
 * ramp, a solar-wind strip, six derived readouts, a validity stamp and a mode
 * line all at once, while the rail beside it explained the same layer again.
 * A legend now carries only a ramp and its units; everything else moved into a
 * data viewer that is off until it is asked for.
 */
describe("how a layer's facts divide between the legend and the data viewer", () => {
  // The worked example this rule came from was the WAM-IPE peak-surface spec in
  // Sean's screenshots. Those surfaces left the rail for the learning pages on
  // 2026-08-18, so the example is now the layer that leads the site: real
  // values, read off the live legend on the day it shipped. The rule under test
  // is unchanged and does not depend on which layer it is applied to.
  const ionosphere: EnvironmentLegendSpec = {
    layer: "thermosphere",
    title: "Thermosphere height",
    badge: "MODEL",
    evidence: "model",
    scale: { gradient: "linear-gradient(90deg, #152a5e, #276b8f, #3fa07d, #e0b23f)", minimum: "250 km", label: "ALTITUDE OF 1e-12 kg m⁻³", maximum: "600 km and above" },
    stats: [
      { label: "LOWEST", value: "423 km" },
      { label: "HIGHEST", value: "512 km" },
      { label: "SPREAD", value: "89 km" },
      { label: "MODEL", value: "NOAA" },
    ],
    note: "The surface is the altitude at which the neutral air reaches that density, drawn on the same ruler as the satellites.",
    validAt: "2026-08-17T11:00:00Z",
    source: "NOAA/NCEP WAM-IPE",
    coverage: "13 frames, 08:10Z–20:00Z",
  };

  it("keeps every derived readout out of the legend and in the viewer's readings", () => {
    const { readings } = dataViewerSections(ionosphere);
    const labels = readings.map(([label]) => label);
    expect(labels).toContain("LOWEST");
    expect(labels).toContain("HIGHEST");
    expect(labels).toContain("SPREAD");
  });

  /**
   * The reverse of what this test used to assert, and deliberately so.
   *
   * The viewer used to repeat the ramp's endpoints and units on the reading
   * that the legend shows only where a colour sits. Both surfaces are on
   * screen together, so what a visitor actually saw was `SCALE 1.6 to 53.9 /
   * UNITS GloTEC vertical TEC · TECU` in the viewer and `1.6 … GloTEC vertical
   * TEC · TECU … 53.9` in the legend a few inches below it — the same three
   * values, twice, on the operational page. The legend owns the range now.
   */
  it("leaves the ramp's range to the legend instead of printing it twice on one screen", () => {
    const { readings } = dataViewerSections(ionosphere);
    const labels = readings.map(([label]) => label);
    expect(labels).not.toContain("Scale");
    expect(labels).not.toContain("Units");
    // The legend still carries them, from the same spec — the value did not
    // disappear from the page, it stopped having two homes.
    expect(keyCardBar(ionosphere, false).endpoints).toEqual(["250 km", "ALTITUDE OF 1e-12 kg m⁻³", "600 km and above"]);
  });

  it("collects validity where it can be read, not stamped over the globe", () => {
    const { validity } = dataViewerSections(ionosphere);
    expect(validity).toContainEqual(["Valid at", "2026-08-17 11:00 UTC"]);
    expect(validity).toContainEqual(["Published coverage", "13 frames, 08:10Z–20:00Z"]);
  });

  it("always says what the evidence badge is claiming, because MODEL is not ASSIMILATED", () => {
    const modelled = dataViewerSections(ionosphere).provenance;
    expect(modelled).toContainEqual(["Source", "NOAA/NCEP WAM-IPE"]);
    expect(modelled.find(([label]) => label === "How it is classified")?.[1])
      .toContain("No measurement fixes any individual value");

    const assimilated = dataViewerSections({ ...ionosphere, evidence: "assimilated", badge: "ASSIMILATED" }).provenance;
    expect(assimilated.find(([label]) => label === "How it is classified")?.[1])
      .toContain("Measurements combined with a model");
  });

  it("returns empty sections for a layer that publishes nothing, so none is drawn empty", () => {
    const bare: EnvironmentLegendSpec = { layer: "regions", title: "Regions", badge: "SCHEMATIC", evidence: "schematic", note: "" };
    const sections = dataViewerSections(bare);
    expect(sections.readings).toEqual([]);
    expect(sections.validity).toEqual([]);
    // Provenance is never empty: a card that names no evidence class is the
    // thing this site exists not to publish.
    expect(sections.provenance.length).toBeGreaterThan(0);
  });

  it("degrades honestly rather than printing Invalid Date into a card", () => {
    const { validity } = dataViewerSections({ ...ionosphere, validAt: "nonsense" });
    expect(validity).toContainEqual(["Valid at", "an unknown time"]);
  });
});

/**
 * Three times in this project a feature has been built, tested and merged
 * while no application entry point referenced it, so it was never on the site.
 * These assertions are cheap and they fail loudly if that happens again here.
 */
describe("the data viewer is actually wired into the page", () => {
  const markup = indexMarkup;
  const source = explorerSource;

  it("loads the one entry point that builds it", () => {
    expect(markup).toContain('<script type="module" src="/src/main.ts">');
  });

  it("carries every element the viewer is built from", () => {
    for (const id of ["data-viewer", "data-viewer-head", "data-viewer-title", "data-viewer-cards", "data-viewer-close", "data-viewer-resize", "layer-card-template"]) {
      expect(markup, `index.html is missing #${id}`).toContain(`id="${id}"`);
    }
  });

  it("has the running interface reach for each of them by name", () => {
    for (const id of ["data-viewer", "data-viewer-head", "data-viewer-title", "data-viewer-cards", "data-viewer-close", "data-viewer-resize", "layer-card-template"]) {
      expect(source, `main.ts never touches #${id}`).toContain(`"${id}"`);
    }
    // The card is cloned from the satellite card's template shape rather than
    // re-implemented, which is what keeps the two looking like one thing.
    expect(source).toContain("fillLayerCard");
    expect(source).toContain("dataViewerSections");
  });

  /**
   * Sean: "The data viewer would be its own separate window probably in the top
   * right of the screen, sort of like we have for satellites when we select
   * one." Stacked in the legend's column the two read as one panel, and the
   * legend carried the viewer's own hide link at its foot, which is what made
   * them look welded together. These pin the separation structurally, because
   * that is the part a later change could quietly undo.
   */
  it("is a window of its own rather than a section of the legend column", () => {
    const column = markup.indexOf('class="map-keys"');
    const columnEnd = markup.indexOf("</div>\n          </div>", column);
    const viewer = markup.indexOf('id="data-viewer"');
    expect(column).toBeGreaterThan(-1);
    expect(viewer).toBeGreaterThan(-1);
    // Outside the legend column entirely, and a sibling of the satellite list
    // it is modelled on rather than a child of the readout stack.
    expect(viewer > columnEnd, "the data viewer is still inside .map-keys").toBe(true);
    expect(markup).toMatch(/<aside class="data-viewer is-collapsed" id="data-viewer"/);
  });

  /**
   * Sean: "Take the toggle away and just put it in the top right of the page,
   * but collapsed so it is one line that just says Data Explorer, and users
   * can expand it down if they want." There is no switch anywhere any more —
   * `explorerCollapsed` defaults `true` and nothing in `bindControls` wires a
   * checkbox to it, which these pin structurally rather than trusting a
   * screenshot to catch a regression back to an always-open panel.
   */
  it("ships EXPANDED by default, with no switch left to open it", () => {
    expect(markup).not.toContain('id="data-viewer-toggle"');
    expect(markup).not.toContain("data-viewer-control");
    expect(source).not.toContain('"data-viewer-toggle"');
    // It used to ship collapsed to its one-line head, and that was defensible
    // while the rail carried an evidence chip on every layer row: the claim
    // was on screen either way. The chips have gone, so this panel is the only
    // surface that states a layer's evidence class, and a panel that opens
    // folded would let a reader draw a MODEL layer and never be told it is
    // one. Read the exact guard the constructor runs; nothing stored yet
    // ("=== \"1\"") reads as expanded, and the key is v2 so a stored
    // "collapsed" from before this change cannot reopen the hole.
    expect(source).toContain('storageGet("local", "space-explorer-data-explorer-collapsed-v2") === "1"');
    expect(source).toContain("private explorerCollapsed = false;");
    expect(source).not.toContain("data-explorer-collapsed-v1");
  });

  /**
   * Sean: "always present when a data layer is on ... absent when no layer is
   * on ... you have to have it visible if you plot data." There is no
   * separate open/closed preference any more, so this is read directly off
   * the render function rather than a copy of its reasoning.
   */
  it("computes its own presence from the active layer count, not a remembered preference", () => {
    const body = source.slice(source.indexOf("private updateDataViewer("));
    const method = body.slice(0, body.indexOf("\n  private ", 1));
    expect(method).toContain("const active = specs.length > 0;");
    // The one exception is the surface that does not have this window at all:
    // on a phone the cards live in the space weather panel, under their own
    // layer rows, and this shell would be a title bar counting them twice.
    expect(method).toContain("viewer.hidden = !active || phone;");
  });

  /**
   * Sean: "if they close it with the X in the right hand side of it, all the
   * toggles go off." The close handler has to reach every real checkbox and
   * drive it with `.click()`, not a synthetic `checked = false`, because a
   * synthetic assignment fires no `change` listener and so trips none of the
   * cascades a manual uncheck would — the geospace layer dropping its
   * empirical-boundary annotation with it, most concretely.
   *
   * It has to be `layerCheckboxIds`, the full map, not `layerOrder`, the
   * shorter list that builds cards and the legend: `groundField` is a real,
   * independently plottable layer with a rail toggle but no card in this
   * panel, and a screenshot with it switched on caught the exact regression —
   * every other toggle went dark and "Ground magnetic perturbation" stayed
   * lit, because the narrower list never looked at it.
   */
  it("closes by driving every real layer checkbox through a real click, not only the ones with a card", () => {
    const body = source.slice(source.indexOf("private closeDataExplorer()"));
    const method = body.slice(0, body.indexOf("\n  private ", 1));
    // Values, not keys: the map is partial now, because a legend identity is
    // not the same thing as a rail layer. What matters to this test is
    // unchanged — every REAL control is driven through a real click.
    expect(method).toContain("Object.values(ExplorerApp.layerCheckboxIds)");
    expect(method).not.toContain("ExplorerApp.layerOrder");
    expect(method).toContain("checkbox.click()");
    expect(method).not.toMatch(/checkbox\.checked\s*=\s*false/);
    expect(source).toContain('byId("data-viewer-close").addEventListener("click", () => this.closeDataExplorer());');
  });

  /**
   * Sean: "See how it is compact and I can't scroll or resize or move it?
   * That is a problem." Expanded, the panel is bounded and scrolls inside
   * itself; collapsed, the body is removed from layout outright rather than
   * merely shrunk, so the panel's whole height IS its one-line head. A reader
   * can also drag the head to move it and the corner grip to resize it past
   * these defaults — `bindExplorerDrag` wires both, pinned separately below.
   */
  it("bounds the expanded height and scrolls inside it, and collapses to the head alone", () => {
    const bodyRule = stylesSource.slice(stylesSource.indexOf(".data-viewer-body {"), stylesSource.indexOf(".data-viewer-body {") + 300);
    expect(bodyRule).toMatch(/overflow-y:\s*auto/);
    const expandedRule = stylesSource.slice(stylesSource.indexOf(".data-viewer:not(.is-collapsed) {"), stylesSource.indexOf(".data-viewer:not(.is-collapsed) {") + 200);
    const maxHeight = /max-height:\s*min\((\d+)vh,\s*(\d+)px\)/.exec(expandedRule);
    expect(maxHeight, `no parseable expanded max-height in: ${expandedRule}`).not.toBeNull();
    expect(Number(maxHeight![1])).toBeLessThanOrEqual(60);
    expect(Number(maxHeight![2])).toBeLessThanOrEqual(600);
    expect(stylesSource).toContain(".data-viewer.is-collapsed .data-viewer-body, .data-viewer.is-collapsed .data-viewer-resize { display: none; }");
    // Still a discreet width at rest, the shrink from the earlier pass. It is
    // a token now rather than a literal, because the 821-1050 px band caps
    // BOTH widths against the satellite stack by moving one cap.
    const widthRule = stylesSource.slice(stylesSource.indexOf(".data-viewer {"), stylesSource.indexOf(".data-viewer {") + 400);
    const width = /--viewer-width:\s*calc\((\d+)px \* var\(--interface-scale\)\)/.exec(widthRule);
    expect(width, `no parseable rest width in: ${widthRule}`).not.toBeNull();
    expect(Number(width![1])).toBeLessThanOrEqual(280);
    expect(widthRule).toContain("width: min(var(--viewer-width), var(--viewer-width-cap));");
  });

  /**
   * AND IT GROWS WHEN A LAYER CARD IS OPENED, which is a different state from
   * "the panel is unfolded".
   *
   * Sean, 2026-08-26: "when I expand the layer in the window, the window
   * doesn't enlarge at all to show enough. It needs to expand vertically and a
   * bit horizontally, to accommodate enough." Measured at 1440x900 with one
   * layer on and its card opened, the panel stood at 288x432 holding 519 px of
   * content — 125 px unreachable except by scrolling, above 216 px of empty
   * scene.
   *
   * "A bit" is the load-bearing word on the width, and the ceiling still has to
   * bound the panel to the scene, so both ends are pinned here.
   */
  it("grows when a layer card is opened, and stays bounded", () => {
    const openRule = /\.data-viewer:not\(\.is-collapsed\):has\(\.data-card:not\(\.is-collapsed\)\) \{([^}]*)\}/.exec(stylesSource);
    expect(openRule, "no opened-card rule at all — an opened card gets no more room than a shut one").not.toBeNull();
    const ceiling = /max-height:\s*min\((\d+)vh,\s*(\d+)px/.exec(openRule![1]!);
    expect(ceiling, `no parseable opened-card ceiling in: ${openRule![1]}`).not.toBeNull();
    // Taller than the folded ceiling — otherwise nothing was fixed...
    expect(Number(ceiling![2])).toBeGreaterThan(480);
    // ...and still bounded to the scene rather than to the document.
    expect(Number(ceiling![1])).toBeLessThanOrEqual(80);
    expect(Number(ceiling![2])).toBeLessThanOrEqual(640);
    // The third term is the live gap to the LEGEND below, written by
    // updateExplorerHeadroom. Without it a tall panel covers the legend's own
    // fold toggle, which is the one control that would make room for it.
    expect(openRule![1]).toContain("var(--viewer-headroom");
    expect(source).toContain("private updateExplorerHeadroom()");
    expect(source).toContain('explorer.style.setProperty("--viewer-headroom"');

    const openWidth = /--viewer-open-width:\s*calc\((\d+)px \* var\(--interface-scale\)\)/.exec(stylesSource);
    expect(openWidth, "no opened-card width token").not.toBeNull();
    const restWidth = /--viewer-width:\s*calc\((\d+)px \* var\(--interface-scale\)\)/.exec(stylesSource);
    expect(Number(openWidth![1])).toBeGreaterThan(Number(restWidth![1]));
    // "A bit". A panel that takes half the scene when a card opens is a
    // different complaint, not a fix for this one.
    expect(Number(openWidth![1]) - Number(restWidth![1])).toBeLessThanOrEqual(80);
  });

  it("can be dragged by its head and resized from its corner", () => {
    expect(source).toContain("private startExplorerDrag(event: PointerEvent)");
    expect(source).toContain("private dragExplorer(event: PointerEvent)");
    expect(source).toContain("private startExplorerResize(event: PointerEvent)");
    expect(source).toContain("private resizeExplorer(event: PointerEvent)");
    // A click (no meaningful pointer movement) folds or unfolds the panel
    // instead of starting a drag — the head does both jobs.
    expect(source).toContain("this.setExplorerCollapsed(!this.explorerCollapsed);");
  });

  it("leaves the legend with no way to open or close it, because there is no switch anywhere", () => {
    const legend = markup.indexOf('id="map-key"');
    const legendEnd = markup.indexOf("</section>", legend);
    const legendMarkup = markup.slice(legend, legendEnd);
    expect(legendMarkup).not.toContain("map-key-data");
    expect(legendMarkup).not.toContain("data viewer");
    expect(source, "main.ts still reaches for the legend's removed hide link").not.toContain('"map-key-data"');
  });

  it("no longer explains the same layer twice, in the rail and over the globe", () => {
    expect(markup).not.toContain("data-layer-notes");
    expect(source).not.toContain("renderLayerNotes");
  });
});

/**
 * The header card's "Measured drivers" repeat a number a switched-on layer's
 * own card already carries in more detail — solar wind speed and IMF Bz
 * against the solar-wind layer, GOES X-ray class against the photon layer, F2
 * peak against the ionosphere layer. Sean: "no duplicated information between
 * the header card and per-layer cards." `updateMeasuredDriversDedupe` is the
 * function the render path actually calls; these exercise its policy through
 * the markup's own attributes rather than a copy of the reasoning.
 */
describe("the header card defers to a layer's own card instead of repeating it", () => {
  const markup = indexMarkup;
  const source = explorerSource;

  it("marks exactly the rows a layer's own card would otherwise repeat", () => {
    const readout = markup.slice(markup.indexOf('id="weather-readout"'), markup.indexOf("</div>", markup.indexOf('id="weather-readout"')));
    const marked = [...readout.matchAll(/data-drivers-dedupe="([a-zA-Z]+)"/g)].map((match) => match[1]);
    expect(marked.sort()).toEqual(["ionosphere", "photons", "solarWind", "solarWind"].sort());
    // Kp, GOES protons and the aurora percentage have no layer card restating
    // them, so they carry no dedupe attribute and always show.
    expect(readout).toContain('<article><span>Planetary Kp</span>');
    expect(readout).toContain('<article><span>GOES protons</span>');
    expect(readout).toContain('<article><span>Aurora max</span>');
  });

  it("hides a marked row only while its layer is active, driven off the same active-layer list every other panel reads", () => {
    const body = source.slice(source.indexOf("private updateMeasuredDriversDedupe("));
    const method = body.slice(0, body.indexOf("\n  private ", 1));
    expect(method).toContain("row.hidden = active.includes(row.dataset.driversDedupe as LayerName);");
    expect(source).toContain("this.updateMeasuredDriversDedupe(specs.map((entry) => entry.layer));");
  });
});

/**
 * The storm indicator.
 *
 * Sean, on the old treatment: "it looks sort of crazy there especially when we
 * are not having one." So the two things that matter are what it does when
 * there is a storm, and what it does when there is not.
 */
describe("the top-bar storm indicator", () => {
  const phase = {
    label: "main" as const,
    intensity: "weak" as const,
    rule: "Dst at or below −30 nT and still falling",
    reason: "Dst is at −38 nT and still falling",
    minimumNt: -41,
    minimumAt: "2026-08-08T14:00:00Z",
  };
  const trace = (series: Array<{ at: string; dstNt: number }>) => ({
    label: "trace", series, citation: "", forwardLeadMinutes: 0,
  });
  const at = new Date("2026-08-08T17:00:00Z");
  const sample = (dstNt: number) => [{ at: "2026-08-08T17:00:00Z", dstNt }];
  const storm = {
    kind: "geomagnetic-storm-indices",
    status: "ok",
    validAt: "2026-08-08T17:00:00Z",
    drivers: null,
    derived: null,
    dst: {
      modelled: trace(sample(-54)),
      observed: trace(sample(-33.7)),
      kyoto: trace(sample(-38)),
      separationNote: "",
    },
    ringCurrent: {} as never,
    phase,
    limitations: [],
  } as never;

  it("says the state and the one number that defines it, and nothing else", () => {
    const headline = stormHeadline(storm, undefined, at);
    expect(headline?.chipLabel).toBe("MAIN · WEAK · Dst −38 nT");
  });

  it("quotes an observed index over the model nowcast, and names which", () => {
    // The modelled trace reads −54 nT here and runs ahead of real time. Putting
    // that on a chip would publish a simulation as a measurement.
    expect(stormHeadline(storm, undefined, at)?.dstSource).toBe("Kyoto quicklook Dst");
    expect(stormHeadline(storm, undefined, at)?.dstNt).toBe(-38);
  });

  it("shows nothing at all in quiet conditions, rather than a calm chip", () => {
    const quiet = { ...(storm as object), phase: { ...phase, label: "quiet", intensity: null } } as never;
    expect(stormHeadline(quiet, undefined, at)).toBeNull();
    expect(stormHeadline(null, undefined, at)).toBeNull();
    // An unclassifiable field is not an occasion to shout either.
    const unknown = { ...(storm as object), phase: { ...phase, label: "unknown", intensity: null } } as never;
    expect(stormHeadline(unknown, undefined, at)).toBeNull();
  });

  it("still reports a storm whose Dst is missing, without inventing a number", () => {
    const noDst = {
      ...(storm as object),
      dst: { modelled: trace([]), observed: trace([]), kyoto: trace([]), separationNote: "" },
    } as never;
    const headline = stormHeadline(noDst, undefined, at);
    expect(headline?.chipLabel).toBe("MAIN · WEAK");
    expect(headline?.dstNt).toBeNull();
    expect(headline?.dstSource).toBeNull();
  });
});

/**
 * The site was stating G0 two inches above a MAIN · WEAK classification with
 * nothing between them. Both are true; they measure different things. A reader
 * given both and no reconciliation concludes the page is broken, and this is a
 * page whose entire value is being trusted.
 */
describe("reconciling the NOAA G-scale with Dst", () => {
  it("explains the disagreement in terms of what each index measures", () => {
    const text = kpDstReconciliation({ kpIndex: 2, gLevel: 0, dstNt: -38, dstSource: "Kyoto quicklook Dst" });
    expect(text).toContain("G0");
    expect(text).toContain("Kp, which is 2.0");
    expect(text).toContain("−38 nT");
    expect(text).toContain("three-hour planetary average");
    expect(text).toContain("Kp cannot resolve storm onset");
  });

  it("says nothing when there is nothing to reconcile", () => {
    // No storm-grade Dst to disagree with.
    expect(kpDstReconciliation({ kpIndex: 2, gLevel: 0, dstNt: null, dstSource: null })).toBeNull();
    // The G-scale has caught up, so the two now agree.
    expect(kpDstReconciliation({ kpIndex: 5, gLevel: 1, dstNt: -80, dstSource: "Kyoto quicklook Dst" })).toBeNull();
    // No G reading published at all.
    expect(kpDstReconciliation({ kpIndex: 2, gLevel: null, dstNt: -38, dstSource: null })).toBeNull();
  });

  it("degrades rather than printing a null Kp into a sentence", () => {
    const text = kpDstReconciliation({ kpIndex: null, gLevel: 0, dstNt: -38, dstSource: null });
    expect(text).toContain("below the storm threshold");
    expect(text).not.toContain("null");
  });
});

describe("the storm indicator is wired into the page", () => {
  const markup = indexMarkup;
  const source = explorerSource;

  it("carries the chip, its dropdown and the layer action", () => {
    // `weather-brief-conflict` is NOT in this list any more, and its absence is
    // the assertion below. It was a bordered panel of its own inside Current
    // Analysis, in a third text size, written on a different update path from
    // the summary it qualifies. The same fact is now one sentence inside that
    // summary's own first paragraph, written by the same method — so it is
    // asserted on the composer rather than on an element.
    for (const id of ["storm-chip", "storm-chip-label", "storm-dropdown", "storm-dropdown-close", "storm-reconcile", "storm-show", "swpc-scale-conflict"]) {
      expect(markup, `index.html is missing #${id}`).toContain(`id="${id}"`);
      expect(source, `main.ts never touches #${id}`).toContain(`"${id}"`);
    }
  });

  it("says the Kp/Dst disagreement inside Current Analysis, not as a panel of its own", () => {
    // ONE MESSAGE, TWO PARAGRAPHS, ONE SIZE. Sean, on the four blocks this
    // replaced: "It has three different text sizes and three different colors.
    // Can we get one cohesive message? Two paragraphs max?"
    const shipped = markup.replace(/<!--[\s\S]*?-->/g, "");
    expect(shipped).not.toContain('id="weather-brief-conflict"');
    expect(shipped).not.toContain('id="weather-brief-kind"');
    expect(shipped).not.toContain('id="weather-time-status"');
    expect(shipped).not.toContain("storm-reconcile--brief");
    expect(shipped).toContain("<summary>Current Analysis</summary>");
    // Exactly two paragraphs in the fold, both on the same class, so they
    // cannot drift into different sizes again.
    const fold = /<details class="card-section weather-brief"[\s\S]*?<\/details>/.exec(shipped)?.[0] ?? "";
    expect(fold.length).toBeGreaterThan(0);
    const paragraphs = fold.match(/<p\b[^>]*>/g) ?? [];
    expect(paragraphs).toHaveLength(2);
    paragraphs.forEach((tag) => expect(tag).toContain('class="weather-brief-line"'));
    // …and the controls stayed controls.
    expect(fold).toContain('class="brief-actions"');
    // ONE WRITER for both paragraphs and for the caveat inside the first.
    expect(source).toContain("private renderCurrentAnalysis()");
    expect(source).toContain("this.kpDstDisagreement = reconciliation !== null;");
    expect(source).not.toContain('byId("weather-brief-conflict")');
  });

  it("keeps the validity time reachable after the jargon line went", () => {
    // Sean, on `PROPAGATED SOLAR WIND · GOES X-RAY · …`: "I don't really get
    // what that is." The TIME is the fact — the seven numbers move with the
    // time slider — so it moved to the fold's own summary row, in the grammar
    // Favorites and Satellites already use there.
    const shipped = markup.replace(/<!--[\s\S]*?-->/g, "");
    expect(shipped).toContain('<summary class="driver-summary">Measured drivers<b class="weather-valid-time" id="weather-valid-time">');
    expect(source).toContain('const valid = byId("weather-valid-time");');
    // Nothing was destroyed: the fuller statement is on the row as a tooltip.
    expect(source).toContain("valid.title = available");
  });

  it("puts the indicator in the top bar beside the data-freshness pill, not in the rail", () => {
    const topbarEnd = markup.indexOf("</header>");
    expect(markup.indexOf('id="storm-chip"')).toBeLessThan(topbarEnd);
    expect(markup.indexOf('id="storm-panel"')).toBeLessThan(topbarEnd);
    // The rail must no longer host it.
    expect(markup).not.toContain('class="storm-panel-host" hidden');
  });

  it("turns on layers through the same path the presets use, not by reaching into a layer module", () => {
    expect(source).toContain("showStormOnGlobe");
    expect(source).toContain("ExplorerApp.layerCheckboxIds[layer]");
  });

  it("has nothing left that can wipe the layers it just switched on", () => {
    // THE HAZARD THIS TEST WAS WRITTEN FOR IS GONE, so the assertion states
    // that rather than checking an order that no longer exists.
    //
    // What shipped broken on 2026-08-08: `setMode` re-applied the current layer
    // preset, and the Simple preset is one layer, so enabling
    // aurora/magnetosphere/radiation and THEN calling `setMode` switched all
    // three straight back off. Sean clicked the button and got a legend reading
    // "1 LAYER". The fix was an ORDER — mode first, layers second — and this
    // test pinned the order, because the two tests above only ask whether the
    // code exists.
    //
    // Explorer Mode was retired on 2026-08-28, so there is no mode call in here
    // to be ordered against, and no code path anywhere between this method and
    // the globe that un-ticks a layer. That is a stronger property than the
    // ordering was, and it is what is asserted now.
    const body = source.slice(source.indexOf("private showStormOnGlobe()"));
    const method = body.slice(0, body.indexOf("\n  private ", 1));
    // Comments stripped. The method keeps a tombstone naming what was removed,
    // and an assertion a comment can satisfy is an assertion that passes both
    // ways.
    const code = method.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toContain("setMode");
    expect(code).not.toContain("applyLayerPreset");
    expect(code.indexOf("this.applyGlobeLayer(layer, true)"),
      "showStormOnGlobe no longer enables the layers").toBeGreaterThan(-1);
    expect(source).not.toContain("private setMode(");
  });

  it("keeps the Simple preset a deliberate one-layer choice, not an accident", () => {
    // This used to be the reason the ordering above mattered. The ordering is
    // gone; the preset is still a reader's CHOICE and still narrow, and a
    // change to it is now a design change rather than a latent wipe.
    expect(source).toContain('simple: ["thermosphere"]');
  });
});

describe("the tab title follows the storm and then gets out of the way", () => {
  const markup = indexMarkup;
  const source = explorerSource;

  it("keeps the plain title in the document, and the storm mark only in code", () => {
    expect(markup).toContain("<title>Space Environment Explorer</title>");
    expect(markup).not.toContain("⚡");
  });

  it("restores the plain title whenever there is no headline", () => {
    // The single assignment has both arms, so a quiet field cannot leave a
    // storm mark stranded in a background tab.
    expect(source).toContain("document.title = headline");
    expect(source).toContain(": BASE_TITLE;");
  });

  it("keeps the favicon relative, because the site is served from /space/", () => {
    expect(markup).toContain('href="./favicon.svg"');
  });
});

/**
 * Sean: "I just want to make sure the right panel doesn't get insanely busy.
 * It should be the cleanest thing we keep because once you start doing the
 * combined space weather and satellites it can quickly become overwhelming."
 *
 * So the rail is a constraint, not an outcome. These assert the rule rather
 * than the appearance: nothing that reports a value lives in it.
 */
describe("the control rail carries controls and nothing else", () => {
  const markup = indexMarkup;
  const source = explorerSource;
  const railStart = markup.indexOf('id="control-rail"');
  const railEnd = markup.indexOf("</aside>", railStart);
  const rail = markup.slice(railStart, railEnd);

  it("was found at all, so the slice below is meaningful", () => {
    expect(railStart).toBeGreaterThan(-1);
    expect(railEnd).toBeGreaterThan(railStart);
  });

  it("has no PER-LAYER readout host left in it", () => {
    // The rule is narrower than it was, by the owner's decision on 2026-08-19,
    // and the line it draws is not "no numbers" but WHOSE numbers. A layer's
    // readings belong to that layer and live on its card; what is true of the
    // whole SCENE - the measured drivers, the plain-language summary, NOAA's
    // R/S/G scales - is not a layer's business and used to sit at the top of
    // the Data Explorer, above any layer card. Sean, opening it: "Why does it
    // start with 'measured drivers'? What the fuck is that?" So that block is
    // a rail section now and these ids stay out: `storm-panel` and `key-cards`
    // are the full Current conditions surfaces, `weather-readout`'s SIBLINGS
    // in the panel were per-layer.
    for (const id of ["storm-panel", "key-cards"]) {
      expect(rail, `#${id} is a whole page's worth of readout and is still in the rail`).not.toContain(`id="${id}"`);
    }
    // And the exception is exactly one section, not a licence.
    expect(rail).toContain('id="conditions-details"');
    const conditions = rail.slice(rail.indexOf('class="rail-section conditions-section"'));
    const conditionsEnd = conditions.indexOf("</section>");
    for (const id of ["weather-readout", "weather-brief-text", "weather-note", "swpc-summary"]) {
      expect(conditions.slice(0, conditionsEnd), `#${id} left the one section it is allowed in`).toContain(`id="${id}"`);
    }
  });

  it("leaves the Data Explorer as one rectangle per layer and nothing above them", () => {
    // Item 14, in one assertion: the panel body holds the card host and no
    // standing card of its own.
    const viewer = markup.slice(markup.indexOf('id="data-viewer-body"'), markup.indexOf('id="data-viewer-resize"'));
    expect(viewer).not.toContain('id="key-conditions"');
    expect(viewer).toContain('id="data-viewer-cards"');
    expect(viewer.replace(/<!--[\s\S]*?-->/g, "")).not.toContain("<article");
  });

  it("no longer carries the long-form method essays beside the controls", () => {
    for (const id of ["ionosphere-model-note", "aurora-note", "drap-note", "geospace-note"]) {
      expect(rail, `#${id} is provenance and is still in the rail`).not.toContain(`id="${id}"`);
    }
    expect(rail).not.toContain("layer-explainer");
  });

  it("still carries every control it is responsible for", () => {
    for (const id of ["layer-thermosphere", "layer-tec", "layer-aurora", "layer-radiation", "swpc-outlook-open"]) {
      expect(rail, `#${id} is a control and must stay in the rail`).toContain(`id="${id}"`);
    }
    expect(rail).toContain('data-preset="simple"');
  });

  /**
   * The Data Explorer used to have a switch here, immediately above the
   * layers. Sean: "Take the toggle away... put it in the top right of the
   * page." There is no replacement control in the rail for it — the panel's
   * presence follows the layers now, so removing the row gives its space back
   * to them, which strengthens this suite's whole "controls and nothing else"
   * rule rather than weakening it.
   */
  it("carries no switch for the Data Explorer any more", () => {
    expect(rail).not.toContain("data-viewer-toggle");
    expect(rail).not.toContain("data-viewer-control");
    expect(rail).not.toContain("Data viewer</strong>");
  });

  /**
   * Sean, seeing the rail after the first pass: "The last screenshot shows a
   * ton of nested data and selection options within the right-hand panel - not
   * what I asked for. That should all be in the data viewer."
   *
   * So a layer row is a toggle, a name, a badge and one line. Every setting
   * that used to fold out underneath one is in that layer's card in the data
   * viewer, and this asserts it by name, because "no per-layer control in the
   * rail" is the kind of rule a later layer quietly breaks by adding one.
   */
  it("carries no per-layer setting at all", () => {
    for (const id of ["ionosphere-region-d", "ionosphere-profile-pick", "magnetopause-cut", "radiation-pitch-select", "model-subcontrols", "ionosphere-subcontrols", "aurora-subcontrols"]) {
      expect(rail, `#${id} is a per-layer setting and belongs in the data viewer`).not.toContain(`id="${id}"`);
    }
    for (const hook of ["data-model-field", "data-model-plane", "data-radiation-view", "data-radiation-energy", "data-layer-panel"]) {
      expect(rail, `${hook} is a per-layer setting and belongs in the data viewer`).not.toContain(hook);
    }
  });

  it("keeps every one of those settings in exactly one place, still bound", () => {
    const host = markup.slice(markup.indexOf('id="layer-control-panels"'));
    const panels = host.slice(0, host.indexOf('<template id="layer-card-template"'));
    for (const id of ["ionosphere-region-d", "ionosphere-region-e", "ionosphere-region-f1", "ionosphere-region-f2", "ionosphere-profile-pick", "magnetopause-cut", "radiation-pitch-select"]) {
      expect(panels, `#${id} went missing on the way out of the rail`).toContain(`id="${id}"`);
      // One copy in the document, or the ids collide and main.ts binds the
      // wrong node — the failure this move was most likely to introduce.
      expect(markup.split(`id="${id}"`).length - 1, `#${id} exists twice`).toBe(1);
    }
    // The running interface moves the node rather than rebuilding it, which is
    // what keeps the listeners main.ts attached at startup alive.
    expect(source).toContain("data-card-controls-slot");
    expect(source).toContain("slot.append(panel)");
  });

  it("keeps no second door to a layer's settings on its row", () => {
    // There used to be a caret here that opened the Data Explorer at this
    // layer's card. Sean: "what are those triangles that show up on the right
    // side of each layer? they make the data viewer pop up. I don't like
    // that." The panel appears on its own the moment a layer is drawn, and the
    // settings are inside that layer's card, so the shortcut was a second
    // non-obvious door to a room the reader is already standing in.
    expect(rail).not.toContain("data-layer-caret");
    expect(source).not.toContain("revealLayerControls");
  });

  /**
   * Sean: "nothing would appear in the right hand panel except the layers and
   * the NOAA data that we have always had there." The layer list and the NOAA
   * operational block are the two things the space-weather column is for; the
   * data viewer's own contents are not in it, and neither is the walkthrough's
   * old bordered promo card.
   */
  it("keeps the space-weather column to the layers and the NOAA block", () => {
    const section = rail.slice(rail.indexOf('class="rail-section environment-section"'));
    expect(section).toContain('id="layer-list"');
    // The NOAA block is still in the rail, in "Conditions right now" with the
    // measured drivers: the storm level and the drivers are the same question
    // asked twice and read as one block. This section is the LAYERS.
    expect(rail).toContain('id="swpc-summary"');
    expect(section).not.toContain('id="swpc-summary"');
    // The walkthrough's rail door is injected by energy-chain-view.ts, so it is
    // never written into this file — a card hard-coded here would be the one
    // thing that could put it back above the layers.
    expect(section).not.toContain("Follow the energy");
    expect(section).not.toContain("chain-walk__launch");
  });
});

/**
 * ONE SPACECRAFT, AND THE PANEL IS JUST ITS CARD.
 *
 * This suite pinned a three-cell segmented control — View Selected / View All /
 * Clear Selected — that Sean asked for in place of a big "hide all other
 * satellites" switch: "I think Selected Satellites should [be] Selected
 * satellites then one of those square selector boxes like you have for
 * all/leo/geo/meo/heo where the options are selected/all and a button next to
 * it to clear." The point of it was that the site already had a vocabulary for
 * choosing between a few named options.
 *
 * SUPERSEDED, 2026-08-28, by the thing the control was scoping. Sean: "no
 * multiple satellites selected ... one at a time. that lets you get rid of the
 * 'x # satellites selected' line at the top with the X, as well as the View
 * Selected, View All, Clear Selected line. you'll just have the card for the
 * satellite." One spacecraft cannot be scoped against itself and a count that
 * only ever reads 1 is not a fact, so all three controls were deleted rather
 * than reduced. The assertions are inverted rather than removed, because the
 * failure this suite is now for is any of them coming back.
 */
describe("the selection panel is the card, and nothing above it", () => {
  const markup = indexMarkup;
  const source = explorerSource;

  it("has no count row, no panel-level clear, and no scope control", () => {
    expect(markup).not.toContain('class="segmented stack-scope"');
    expect(markup).not.toContain("data-satellite-scope");
    expect(markup).not.toContain('id="satellite-stack-clear"');
    expect(markup).not.toContain('id="satellite-stack-count"');
    expect(markup).not.toContain('id="satellite-stack-close"');
    expect(markup).not.toContain('id="satellite-stack-controls"');
    // ...and none of the older shapes either. The switch-plus-paragraph block
    // the segmented control replaced must not come back through the gap.
    expect(markup).not.toContain('class="isolate-control"');
    expect(markup).not.toContain('id="satellite-solo"');
    expect(source).not.toContain('"satellite-solo"');
  });

  it("keeps the panel itself, holding exactly one card", () => {
    // The window stays: it is dragged, it remembers where it was put, it is a
    // globe-label occluder, and the stylesheet tiles it against the layer
    // viewer. None of that was ever about how many cards were inside it.
    expect(markup).toContain('id="satellite-stack"');
    expect(markup).toContain('id="satellite-stack-cards"');
    // But the collections are gone, not capped: a set capped at one is still a
    // set, and the next thing to iterate it grows the stack back for free.
    // Comments are stripped, because the field that replaced them names both of
    // them in explaining why neither survived.
    const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toContain("selectedStack");
    expect(code).not.toContain("stackCards");
    expect(source).toContain("private selectedCard: HTMLElement | null = null;");
  });

  it("drops the hide-others flag with the control that set it", () => {
    // "Selected" was the state the old switch called "Hide all other
    // satellites". There is nothing left to hide from: the drawn set is the
    // filters plus the one open spacecraft.
    expect(source).not.toContain("hideOtherSatellites");
    expect(source).toContain("resolveVisibleIndices(filteredIndices, this.selectedIndex, false)");
  });

  it("gives the panel its drag handle back on the card's own head", () => {
    // The deleted count row was `#satellite-stack-handle`. Keeping it as an
    // empty grab rail would put back the row Sean asked to delete, so the
    // handle is the card head — and it is bound per card, because the card
    // element is rebuilt every time a different spacecraft is opened.
    expect(markup).not.toContain('id="satellite-stack-handle"');
    expect(source).toContain("private bindCardDragHandle(handle: HTMLElement)");
    expect(source).toMatch(/querySelector<HTMLElement>\("\.sat-card-head"\)[\s\S]{0,120}bindCardDragHandle/);
    // Scoped to the satellite panel in CSS: `.sat-card-head` is also every
    // LAYER card's head inside the data viewer, which has its own drag.
    expect(stylesSource).toContain(".satellite-stack .sat-card-head { cursor: grab; touch-action: none; }");
  });

  it("keeps the card's own two buttons, and keeps them independent", () => {
    // The star outlives the card; the X drops the drawn geometry and closes the
    // card without touching the star. Both were already true of the per-card
    // controls, and both have to survive the list going away.
    const template = markup.slice(markup.indexOf('id="satellite-card-template"'));
    expect(template.slice(0, template.indexOf("</template>"))).toContain("data-card-favorite");
    expect(template.slice(0, template.indexOf("</template>"))).toContain("data-card-remove");
    const close = source.slice(source.indexOf("private closeSelectedCard()"));
    const body = close.slice(0, close.indexOf("\n  private ", 1));
    expect(body).toContain("this.globe.clearSelectedGeometry();");
    expect(body).not.toContain("favorite");
    expect(body).not.toContain("this.favorites");
  });
});

/**
 * Switching a layer on must not leave an empty globe.
 *
 * Sean asked for two behaviours and only one of them shipped. The message when
 * a reader scrubs into a gap works (above). The other half — "I just don't
 * want people to turn on a layer and not have it show up" — did not, and the
 * measurement is what says why: switching the aurora layer on at 16:33 UTC on
 * 2026-08-19, against a release whose OVATION history stopped at 13:59 UTC,
 * moved the clock not at all. #time-slider took ZERO input events and its
 * value stayed "0". The key card still drew its 0-100% ramp at +0 ms after the
 * toggle and only flipped to NO DATA at +150 ms, when the fetch landed — so at
 * the instant the checkbox flipped there was no coverage window to read, no
 * jump target, and nothing for the landing to do.
 *
 * These pin the rules that replaced it, and the shape that keeps the decision
 * where the answer exists.
 */
describe("landing the clock on a layer that has nothing to draw", () => {
  // The real release measured on 2026-08-19: NOAA had published no OVATION
  // frame for 2.09 hours and our newest frame was identical to theirs.
  const auroraLandsAt = "2026-08-19T13:58:00.000Z";
  const nowMs = Date.parse("2026-08-19T16:33:00Z");

  it("moves the clock back to the layer's newest published frame", () => {
    const target = coverageLandingTarget({
      selectedAtMs: nowMs,
      readerActionCount: 0,
      candidates: [{ layer: "aurora", jumpToIso: auroraLandsAt, armedAtActionCount: 0 }],
    });
    expect(target?.layer).toBe("aurora");
  });

  it("never moves the clock forward", () => {
    // Not a stylistic preference. Every feed here has history and it is the
    // present that has holes, so there is nothing published ahead to land on —
    // and a forward jump would take every OTHER switched-on layer out of its
    // own coverage to fix one.
    const target = coverageLandingTarget({
      selectedAtMs: Date.parse("2026-08-19T10:00:00Z"),
      readerActionCount: 0,
      candidates: [{ layer: "aurora", jumpToIso: auroraLandsAt, armedAtActionCount: 0 }],
    });
    expect(target).toBeNull();
  });

  it("lands once, because the earliest candidate is a fixed point", () => {
    // Two layers short of coverage at two different times is the ordinary
    // case: aurora stops at 13:59 and the ring current's convection field
    // stops earlier. Taking the NEAREST landing would satisfy aurora, leave
    // the ring current empty, and hand this same rule a second jump to make —
    // a clock walking backwards in steps under the reader.
    const candidates = [
      { layer: "aurora", jumpToIso: auroraLandsAt, armedAtActionCount: 0 },
      { layer: "ringCurrent", jumpToIso: "2026-08-19T11:20:00.000Z", armedAtActionCount: 0 },
    ];
    const first = coverageLandingTarget({ selectedAtMs: nowMs, readerActionCount: 0, candidates });
    expect(first?.layer).toBe("ringCurrent");
    // And from where it landed, nothing asks to move again. That is the whole
    // reason the earliest wins rather than the nearest.
    const second = coverageLandingTarget({
      selectedAtMs: Date.parse(first!.jumpToIso!),
      readerActionCount: 0,
      candidates,
    });
    expect(second).toBeNull();
  });

  it("drops a landing the reader overtook by moving the clock themselves", () => {
    // The layer was switched on while the reader's clock-action count was 0
    // and its artifact arrived after they had moved the clock. Yanking time
    // out from under somebody who has just chosen a moment is worse than an
    // empty layer; that reader gets the message instead.
    const target = coverageLandingTarget({
      selectedAtMs: nowMs,
      readerActionCount: 1,
      candidates: [{ layer: "aurora", jumpToIso: auroraLandsAt, armedAtActionCount: 0 }],
    });
    expect(target).toBeNull();
  });

  it("has nothing to land on for a layer that publishes no window", () => {
    const target = coverageLandingTarget({
      selectedAtMs: nowMs,
      readerActionCount: 0,
      candidates: [{ layer: "solarWind", armedAtActionCount: 0 }],
    });
    expect(target).toBeNull();
  });

  it("says where the clock went, whose publishing stopped, and how to get back", () => {
    const note = coverageLandingNotice({
      landedAtIso: auroraLandsAt,
      sourceLabel: "NOAA's published OVATION history",
    });
    expect(note).toContain("2026-08-19 13:58 UTC");
    expect(note).toContain("NOAA's published OVATION history");
    expect(note).toContain("Return to now");
    // Silence would be the other failure: a reader who was looking at "now"
    // finds themselves two and a half hours earlier with nothing saying why,
    // and the honest reading of that is that the site jumped.
    expect(note).toContain("holding");
    // And it must not borrow the no-data wording, which says the layer is off.
    // The landing exists precisely so that it is ON.
    expect(note).not.toContain("the layer is left off");
    expect(note).not.toContain("NO DATA");
  });

  it("takes a source label of any shape without printing broken English", () => {
    // Every label here is written to OPEN a sentence, and they are phrases of
    // all shapes: "The coupled NOAA geospace run", "NOAA's published OVATION
    // history", and the ring current's, which ends in a relative clause. Made
    // the subject of a verb, that last one printed "…frames, which supply the
    // convection field has nothing newer than that" in a real browser — a
    // plural subject with a singular verb. The sentence cannot know the shape,
    // so it does not make the label its subject.
    const note = coverageLandingNotice({
      landedAtIso: "2026-08-19T15:59:00.000Z",
      sourceLabel: "This release's DGCPM plasmasphere frames, which supply the convection field",
    });
    expect(note).toContain("There is nothing newer in this release's DGCPM plasmasphere frames, which supply the convection field.");
    expect(note).not.toContain("field has nothing");
    // A label that is already a possessive keeps its capital, because it is a
    // name: lowering "NOAA's" would be a different mistake.
    expect(coverageLandingNotice({ landedAtIso: "2026-08-19T13:58:00.000Z", sourceLabel: "NOAA's published OVATION history" }))
      .toContain("There is nothing newer in NOAA's published OVATION history.");
    expect(coverageLandingNotice({ landedAtIso: "2026-08-19T13:58:00.000Z", sourceLabel: "The coupled NOAA geospace run" }))
      .toContain("There is nothing newer in the coupled NOAA geospace run.");
  });

  it("counts the notice as rendered content, or it is never drawn", () => {
    // The key cards are rebuilt only when their content signature changes —
    // deliberately, because rebuilding them 4.3 times a second made the jump
    // button unclickable. Anything they draw that is in NO SPEC is therefore
    // invisible to the signature, and the rebuild that would have carried it is
    // skipped as "no change".
    //
    // The no-data notice is exactly that, and it was found the hard way. It is
    // written from the selected instant — which minute, and which EDGE of the
    // window was passed — and the spec either side of a move through the gap is
    // identical, so the legend card froze on the first gap message it drew.
    // Measured on the built bundle: scrubbed from sixteen hours before the
    // thermosphere release to a day and a half after it, the card still read
    // "only goes back to 2026-08-19 20:00 UTC" and still offered a jump to the
    // start of the window.
    const mapKey = explorerSource.slice(
      explorerSource.indexOf("private updateMapKey("),
      explorerSource.indexOf("private updateMapKey(") + 4200,
    );
    expect(mapKey).toContain("this.layerUnavailable(layer, spec)]),");
  });

  it("draws the clock-landing sentence on the layer card, which needs no signature", () => {
    // The same trap caught the landing note when it lived on the legend card:
    // measured on the built bundle, the clock jumped two and a half hours, the
    // aurora came back on screen, and the legend said nothing at all, because
    // the specs either side of the landing were identical.
    //
    // Sean moved the sentence to the layer viewer on 2026-08-27 ("The
    // description is too long. That should go in the layer viewer."), and the
    // trap does not follow it: the layer cards are KEPT AND REFILLED on every
    // environment update rather than rebuilt on a signature. So the assertion
    // that matters now is that the refilling surface is the one that writes it,
    // and that the legend no longer does.
    const fill = explorerSource.slice(
      explorerSource.indexOf("private fillLayerCard("),
      explorerSource.indexOf("private fillLayerCard(") + 5400,
    );
    expect(fill).toContain('card.querySelector<HTMLElement>("[data-card-landed]")');
    expect(fill).toContain("this.coverageLanding.note");
    const keyCard = explorerSource.slice(
      explorerSource.indexOf("private renderKeyCard("),
      explorerSource.indexOf("private layerCard("),
    );
    expect(keyCard).not.toContain("this.coverageLanding.note");
    // ...and the refill really is unconditional, which is the whole reason the
    // sentence needs no signature entry of its own.
    const viewer = explorerSource.slice(
      explorerSource.indexOf("private updateDataViewer("),
      explorerSource.indexOf("private updateMeasuredDriversDedupe("),
    );
    expect(viewer).toContain("specs.forEach(({ layer, spec }) => this.fillLayerCard(this.layerCard(layer), layer, spec));");
  });

  it("decides where the layer's data arrives, not where the checkbox flips", () => {
    // The bug was a hook in the wrong place, and this is the assertion that
    // would have caught it. `applyGlobeLayer` runs while the artifact is still
    // in flight — the layer reports "loading", has no coverage window, and
    // cannot answer — so all it may do is record the intent.
    const toggle = explorerSource.slice(
      explorerSource.indexOf("private applyGlobeLayer("),
      explorerSource.indexOf("private applyGlobeLayer(") + 1400,
    );
    expect(toggle).toContain("this.pendingCoverageLanding.set(layer, this.readerClockActions)");
    expect(toggle).not.toContain("this.landOnCoverage(");
    // And the answer is taken from the one call every asynchronous artifact
    // loader makes when its bundle lands.
    // THE WHOLE METHOD, not its first 900 characters. A fixed character
    // budget is an assertion about how much comment sits above the call: three
    // unrelated commits on 2026-08-21 added a line each near the top of
    // `updateEnvironmentLegend` and pushed the call to offset 898, so this
    // failed by two characters while the code it describes had not moved.
    const legendStart = explorerSource.indexOf("private updateEnvironmentLegend()");
    const legend = explorerSource.slice(
      legendStart,
      explorerSource.indexOf("\n  private ", legendStart + 10),
    );
    expect(legend).toContain("this.landOnCoverage(specs)");
    // A layer still fetching keeps waiting rather than being answered "no".
    const landing = explorerSource.slice(
      explorerSource.indexOf("private landOnCoverage("),
      explorerSource.indexOf("private landOnCoverage(") + 2600,
    );
    expect(landing).toContain('if (spec.statusState === "loading") continue;');
  });

  it("holds the clock where it landed", () => {
    // The landing instant is a minute inside the window on purpose. A clock
    // still running at real time would carry the reader back out of coverage
    // about sixty seconds later and the layer they had just switched on would
    // go blank again — the defect, restored on a timer.
    const seek = explorerSource.slice(
      explorerSource.indexOf("private seekToUtc("),
      explorerSource.indexOf("private seekToUtc(") + 1600,
    );
    expect(seek).toContain("this.pausedAt = hold ? new Date(Math.min(Math.max(target, Date.now() + minimum * 60_000), Date.now() + maximum * 60_000)) : null;");
    // And held at the instant the card names, not at the rounded minute the
    // slider can express: measured, the clock read 13:57:32 under a card
    // announcing a move to 13:58 UTC, which is the card describing a time the
    // site is not showing.
    expect(seek).not.toContain("new Date(Date.now() + clamped * 60_000)");
    expect(explorerSource).toContain("this.seekToUtc(target.jumpToIso, true);");
  });
});


/**
 * THE HEAD SAYS WHAT THE PANEL IS, ONCE, AND THE PANEL IS AS TALL AS ITS CARDS.
 *
 * Sean, on plotting his first overlay: "Don't call it Data Explorer. That is
 * cheesy. Just say '# Space Weather Layers' and the X on the other side. See
 * how it starts very large even though there is only one entry? Fix that too.
 * That is wasted space."
 *
 * Two defects in one sentence, and only one of them was cosmetic.
 *
 * The head printed a "DATA EXPLORER" kicker AND a "1 layer" chip, so the count
 * had two homes in a strip 34px tall. It is one line now, in the same shape the
 * satellite list opposite already prints ("# Satellite(s) Selected"), with the
 * close button held against the far edge.
 *
 * The wasted space was never CSS. `styles.css` sets a max-height on this panel
 * and nothing else, and a max-height cannot stretch a flex column — measured on
 * the built bundle with a clean profile, one card gives a 121px panel. What
 * made Sean's 432px window was `applyExplorerSize` restoring a remembered
 * corner-drag as an inline `height`, and an inline height is a floor as well as
 * a ceiling: a browser that had ever been resized reopened at that height
 * however little was in it. The remembered size is applied as an inline
 * `max-height` now, which is why the assertion below is that no path in this
 * file writes a height at all.
 */
describe("the space weather layers panel names itself once and fits its contents", () => {
  const markup = indexMarkup;
  const source = explorerSource;

  it("prints the count and the noun in one line, with nothing left printing it twice", () => {
    expect(markup).toContain('<strong class="data-viewer-title" id="data-viewer-title">');
    expect(markup, "the count chip is back beside the title").not.toContain('id="data-viewer-count"');
    expect(markup, "the old kicker is back in the head").not.toContain('<span class="section-kicker">DATA EXPLORER</span>');
    expect(source).toContain('byId("data-viewer-title").textContent');
    expect(source, "main.ts still writes to an element that no longer exists").not.toContain('"data-viewer-count"');
  });

  it("gets the singular right, because one layer is the commonest state this panel is in", () => {
    expect(source).toContain('`${specs.length} Space Weather ${specs.length === 1 ? "Layer" : "Layers"}`');
  });

  it("says the same thing to a screen reader as it does to a sighted reader", () => {
    // A defect on its own: hearing "Data Explorer" while reading "Space Weather
    // Layers" is two panels, not one.
    const aside = markup.slice(markup.indexOf('<aside class="data-viewer'), markup.indexOf('id="data-viewer-body"'));
    expect(aside).toContain('aria-label="Space weather layers: readings for every layer switched on"');
    expect(aside).toMatch(/id="data-viewer-close" aria-label="[^"]*space weather layer[^"]*"/);
    expect(aside.toLowerCase(), "an assistive string still says Data Explorer").not.toContain("data explorer");
  });

  it("never writes a height, so a remembered resize cannot prop it open past its cards", () => {
    for (const start of ["private applyExplorerSize(", "private resizeExplorer("]) {
      const from = source.indexOf(start);
      expect(from, `${start} was not found`).toBeGreaterThan(-1);
      const body = source.slice(from, source.indexOf("\n  private ", from + 10));
      expect(body, `${start} sets an inline height again`).not.toMatch(/style\.height\s*=/);
      expect(body, `${start} no longer applies the reader's ceiling`).toContain("style.maxHeight = ");
    }
    // And the restore path clears any height an older bundle left on the node.
    const apply = source.slice(source.indexOf("private applyExplorerSize("));
    expect(apply.slice(0, apply.indexOf("\n  private ", 10))).toContain('explorer.style.removeProperty("height")');
  });

  it("keeps the stylesheet's own ceiling, so eight layers cannot outgrow the window", () => {
    // The reader's ceiling overrides this one; nothing else does.
    expect(stylesSource).toMatch(/\.data-viewer:not\(\.is-collapsed\) \{ max-height: min\(48vh, 480px\); \}/);
    expect(stylesSource, "no rule may set a height on this panel").not.toMatch(/\.data-viewer[^-{}]*\{[^}]*[^-]height: \d/);
    // The opened-card ceiling is the one exception to the 480 px above and it
    // is a max-height too. Every .data-viewer rule in the sheet is checked
    // here rather than by one regex over the whole file, because a pattern
    // loose enough to find them all is loose enough to run across a rule
    // boundary and read some other selector's height as this panel's.
    const panelRules = [...stylesSource.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
      .filter(([, selector]) => /(^|[\s,>])\.data-viewer(?![-\w])/.test(selector!))
      .map(([, selector, body]) => [selector!.trim(), body!] as const);
    expect(panelRules.length, "no .data-viewer rules found — this check is not reaching the stylesheet").toBeGreaterThan(3);
    for (const [selector, body] of panelRules) {
      expect(body, `${selector} sets a height, which is a floor as well as a ceiling`).not.toMatch(/(^|[;{\s])height:/);
    }
  });
});
