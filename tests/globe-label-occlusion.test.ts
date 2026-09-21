import { describe, expect, it } from "vitest";
import {
  collectLabelOccluderRects,
  elementHidesGlobe,
  labelPlacementIsOccluded,
  paintedBackgroundAlpha,
  screenRectContains,
  screenRectsOverlap,
  type LabelOccluderCandidate,
  type LabelOccluderStyle,
  type ScreenRect,
} from "../src/globe";

const transparent: LabelOccluderStyle = {
  display: "block",
  visibility: "visible",
  opacity: "1",
  backgroundColor: "rgba(0, 0, 0, 0)",
  backdropFilter: "none",
};

/**
 * A stand-in for a DOM element. Only the surface collectLabelOccluderRects
 * actually reads is modelled; the browser supplies the same shape.
 */
class FakeElement implements LabelOccluderCandidate {
  readonly children: FakeElement[] = [];
  readonly attributes = new Set<string>();

  constructor(
    readonly name: string,
    private readonly rect: ScreenRect,
    readonly style: LabelOccluderStyle = transparent,
  ) {}

  getBoundingClientRect() {
    return this.rect;
  }

  append(...children: FakeElement[]) {
    this.children.push(...children);
    return this;
  }

  contains(other: FakeElement): boolean {
    return this === other || this.children.some((child) => child.contains(other));
  }
}

const opaquePanel = (backgroundColor: string): LabelOccluderStyle => ({ ...transparent, backgroundColor });

function scan(root: FakeElement, viewport: ScreenRect, globe: FakeElement) {
  return collectLabelOccluderRects(root, viewport, {
    readStyle: (element) => (element as FakeElement).style,
    isGlobeSurface: (element) =>
      element === globe || (element as FakeElement).attributes.has("data-globe-label-clear"),
    containsGlobeSurface: (element) => (element as FakeElement).contains(globe),
    isDeclaredOccluder: (element) => (element as FakeElement).attributes.has("data-globe-label-occluder"),
  });
}

describe("background alpha parsing", () => {
  it("reads the alpha channel of computed background colours", () => {
    expect(paintedBackgroundAlpha("rgba(2, 10, 16, 0.88)")).toBeCloseTo(0.88);
    expect(paintedBackgroundAlpha("rgb(20, 56, 66)")).toBe(1);
    expect(paintedBackgroundAlpha("rgba(0, 0, 0, 0)")).toBe(0);
    expect(paintedBackgroundAlpha("transparent")).toBe(0);
    expect(paintedBackgroundAlpha("")).toBe(0);
  });

  it("treats an unparseable colour as painting nothing rather than hiding labels", () => {
    expect(paintedBackgroundAlpha("color(srgb 0.1 0.2 0.3)")).toBe(0);
    expect(paintedBackgroundAlpha("oklch(0.5 0.1 200)")).toBe(0);
  });
});

describe("does an element hide the globe", () => {
  it("counts the site's real panel backgrounds", () => {
    expect(elementHidesGlobe(opaquePanel("rgba(2, 10, 16, 0.9)"), 0.25)).toBe(true);
    expect(elementHidesGlobe(opaquePanel("rgba(2, 10, 16, 0.68)"), 0.25)).toBe(true);
  });

  it("counts a blurred backdrop even without a solid fill", () => {
    expect(elementHidesGlobe({ ...transparent, backdropFilter: "blur(7px)" }, 0.25)).toBe(true);
  });

  it("ignores transparent wrappers, hidden nodes and near-invisible overlays", () => {
    expect(elementHidesGlobe(transparent, 0.25)).toBe(false);
    expect(elementHidesGlobe({ ...opaquePanel("rgb(0, 0, 0)"), visibility: "hidden" }, 0.25)).toBe(false);
    expect(elementHidesGlobe({ ...opaquePanel("rgb(0, 0, 0)"), opacity: "0.1" }, 0.25)).toBe(false);
    expect(elementHidesGlobe(opaquePanel("rgba(2, 10, 16, 0.1)"), 0.25)).toBe(false);
  });
});

describe("occluder discovery from the live document", () => {
  const viewport: ScreenRect = { left: 0, top: 74, right: 1114, bottom: 970 };

  function buildDocument() {
    const globe = new FakeElement("#scene", viewport);
    const mapKey = new FakeElement("#environment-legend", { left: 680, top: 90, right: 1094, bottom: 440 }, opaquePanel("rgba(2, 10, 16, 0.9)"));
    mapKey.append(new FakeElement("head", { left: 690, top: 95, right: 1084, bottom: 130 }, opaquePanel("rgb(0, 0, 0)")));
    const clock = new FakeElement(".clock-block", { left: 18, top: 92, right: 220, bottom: 140 }, opaquePanel("rgba(2, 10, 16, 0.68)"));
    const hud = new FakeElement(".scene-hud", { left: 18, top: 92, right: 1096, bottom: 140 }).append(clock);
    const shell = new FakeElement(".scene-shell", viewport).append(globe, hud, mapKey);
    const rail = new FakeElement("#control-rail", { left: 1114, top: 74, right: 1500, bottom: 970 }, opaquePanel("rgb(6, 18, 26)"));
    // The page background is opaque, and it contains the globe.
    const body = new FakeElement("body", { left: 0, top: 0, right: 1500, bottom: 970 }, opaquePanel("rgb(4, 12, 18)"))
      .append(shell, rail);
    return { body, globe, mapKey, clock, rail, shell, hud };
  }

  it("finds the panels that float over the globe", () => {
    const { body, globe, mapKey, clock } = buildDocument();
    const rects = scan(body, viewport, globe);
    expect(rects).toContainEqual(mapKey.getBoundingClientRect());
    expect(rects).toContainEqual(clock.getBoundingClientRect());
  });

  it("never treats an ancestor of the globe as an occluder, however opaque", () => {
    const { body, globe, shell } = buildDocument();
    const rects = scan(body, viewport, globe);
    expect(rects).not.toContainEqual(body.getBoundingClientRect());
    expect(rects).not.toContainEqual(shell.getBoundingClientRect());
  });

  it("stops descending once an element is known to cover the globe", () => {
    const { body, globe, mapKey } = buildDocument();
    const rects = scan(body, viewport, globe);
    expect(rects.filter((rect) => screenRectsOverlap(rect, mapKey.getBoundingClientRect()))).toHaveLength(1);
  });

  it("skips anything sitting beside the canvas rather than over it", () => {
    const { body, globe, rail } = buildDocument();
    expect(scan(body, viewport, globe)).not.toContainEqual(rail.getBoundingClientRect());
  });

  it("clamps reported rectangles to the canvas", () => {
    const { body, globe, mapKey } = buildDocument();
    const wide = new FakeElement("wide", { left: -400, top: 0, right: 2000, bottom: 200 }, opaquePanel("rgb(0, 0, 0)"));
    body.append(wide);
    const rects = scan(body, viewport, globe);
    expect(rects).toContainEqual({ left: 0, top: 74, right: 1114, bottom: 200 });
    expect(mapKey.getBoundingClientRect().right).toBeLessThan(viewport.right);
  });

  it("honours the opt-in and opt-out attributes a panel can declare", () => {
    const { body, globe } = buildDocument();
    const invisibleButBlocking = new FakeElement("declared", { left: 100, top: 700, right: 300, bottom: 800 });
    invisibleButBlocking.attributes.add("data-globe-label-occluder");
    const opaqueButAllowed = new FakeElement("opted-out", { left: 400, top: 700, right: 600, bottom: 800 }, opaquePanel("rgb(0, 0, 0)"));
    opaqueButAllowed.attributes.add("data-globe-label-clear");
    body.append(invisibleButBlocking, opaqueButAllowed);
    const rects = scan(body, viewport, globe);
    expect(rects).toContainEqual(invisibleButBlocking.getBoundingClientRect());
    expect(rects).not.toContainEqual(opaqueButAllowed.getBoundingClientRect());
  });

  it("stops after the visit budget instead of walking an unbounded document", () => {
    const { globe } = buildDocument();
    const deep = new FakeElement("root", viewport);
    let tail = deep;
    for (let index = 0; index < 50; index += 1) {
      const next = new FakeElement(`level-${index}`, viewport);
      tail.append(next);
      tail = next;
    }
    const rects = collectLabelOccluderRects(deep, viewport, {
      readStyle: (element) => (element as FakeElement).style,
      isGlobeSurface: (element) => element === globe,
      containsGlobeSurface: () => false,
      maximumVisited: 5,
    });
    expect(rects).toHaveLength(0);
  });
});

describe("label placement", () => {
  const viewport: ScreenRect = { left: 0, top: 74, right: 1114, bottom: 970 };
  const mapKey: ScreenRect = { left: 680, top: 90, right: 1094, bottom: 440 };

  it("shows a label over open globe", () => {
    expect(labelPlacementIsOccluded({ left: 300, top: 600, right: 420, bottom: 640 }, viewport, [mapKey])).toBe(false);
  });

  it("suppresses a label that runs under a panel, even by its corner", () => {
    expect(labelPlacementIsOccluded({ left: 640, top: 400, right: 760, bottom: 440 }, viewport, [mapKey])).toBe(true);
    expect(labelPlacementIsOccluded({ left: 1090, top: 430, right: 1110, bottom: 470 }, viewport, [mapKey])).toBe(true);
  });

  it("suppresses a label that leaves the canvas for the control rail", () => {
    expect(labelPlacementIsOccluded({ left: 1060, top: 600, right: 1180, bottom: 640 }, viewport, [])).toBe(true);
    expect(labelPlacementIsOccluded({ left: 300, top: 940, right: 420, bottom: 980 }, viewport, [])).toBe(true);
  });

  it("treats a label that only touches a panel edge as clear", () => {
    expect(labelPlacementIsOccluded({ left: 560, top: 400, right: 680, bottom: 440 }, viewport, [mapKey])).toBe(false);
  });

  it("agrees with its own rectangle helpers", () => {
    expect(screenRectContains(viewport, { left: 10, top: 80, right: 100, bottom: 120 })).toBe(true);
    expect(screenRectContains(viewport, { left: 10, top: 10, right: 100, bottom: 120 })).toBe(false);
    expect(screenRectsOverlap(mapKey, { left: 1093, top: 439, right: 1200, bottom: 500 })).toBe(true);
    expect(screenRectsOverlap(mapKey, { left: 1094, top: 440, right: 1200, bottom: 500 })).toBe(false);
  });
});
