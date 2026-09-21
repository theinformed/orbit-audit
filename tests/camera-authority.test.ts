import { describe, expect, it } from "vitest";

/**
 * WHO IS ALLOWED TO MOVE THE READER'S CAMERA.
 *
 * Four layer toggles used to answer their own switch by flying the camera to a
 * preset: the radiation belts to an oblique three-quarter view, the solar wind
 * and the plasma field to the oblique magnetosphere view, and the ring current
 * straight down the dipole axis. Sean, on the shipped build: *"When we put the
 * plasma sheet and ring current on, the projection changes to polar. And it
 * makes navigating really difficult. Can you have an agent disable that? I
 * don't like it."*
 *
 * The rule that replaced them is a distinction, not a ban. A layer may WIDEN
 * the view — `frameActiveLayers()` dollies out along the line the reader is
 * already looking down, and only when what is drawn does not fit, so a layer
 * that would otherwise be entirely off screen still becomes visible. A layer
 * may not ROTATE it, because rotation replaces the viewpoint the reader chose
 * and they have to find their place again. That is the whole of the complaint.
 *
 * The preset views are still there and still reachable: they are the three
 * camera buttons under the globe. This pins the boundary — every call to one
 * of them in `main.ts` must be a reader pressing a button — because the defect
 * is not a wrong number anywhere, it is a call in the wrong place, and nothing
 * else in the suite can see that.
 */

const sources = Object.fromEntries(
  Object.entries(
    import.meta.glob("../src/*.ts", { eager: true, query: "?raw", import: "default" }),
  ).map(([key, value]) => [key.replace(/^\.\.\//, ""), value as string]),
) as Record<string, string>;

/** The camera moves that REPLACE the reader's viewpoint rather than widening it. */
const REORIENTING_VIEWS = [
  "focusPolarView",
  "focusMeridionalCrossSection",
  "focusSunEarthSideView",
  "focusMagnetosphereObliqueView",
  "focusRadiationObliqueView",
];

/**
 * THE ONE SANCTIONED EXCEPTION, and the guards that keep it one.
 *
 * Sean, 2026-08-27: "I know we took the cusps off, but when we pull up
 * magnetosphere it should be oriented so that the sun is on the left of the
 * page, just like we had it before." Both of his complaints are real and they
 * are about DIFFERENT events. Pulling a layer up is a reader asking for a
 * picture; being mid-navigation with the layer already up is not. So exactly
 * one reorienting call is allowed outside a camera button, and only where the
 * guards below hold it to the narrow case: the magnetosphere layer's own
 * checkbox, switched ON, synchronously in its own change handler, first
 * pull-up of the session or else only while the reader has not turned the
 * globe by hand since the site last set the angle.
 *
 * This is deliberately pinned by NAME and by GUARD rather than waived. A
 * second call, a call from another layer, or this one with its guards taken
 * off, all fail — which is the difference between an exception and a hole.
 */
const SANCTIONED_PULL_UP = {
  view: "focusMagnetosphereObliqueView",
  method: "private orientMagnetosphereOnPullUp() {",
  guards: ["magnetosphereOrientSpent", "this.cameraTurnedByHand()"],
  caller: 'if (checked && layer === "geospace" && event.isTrusted) this.orientMagnetosphereOnPullUp();',
};

/** The character span of the sanctioned method's body, or null if it is gone. */
function sanctionedMethodSpan(source: string): { start: number; end: number } | null {
  const start = source.indexOf(SANCTIONED_PULL_UP.method);
  if (start < 0) return null;
  const end = source.indexOf("\n  }", start);
  if (end < 0) return null;
  return { start, end };
}

describe("camera authority", () => {
  it("only lets a reader's own button reorient the globe", () => {
    const source = sources["src/main.ts"] ?? "";
    expect(source, "src/main.ts was not readable, so nothing here was checked").toBeTruthy();

    const span = sanctionedMethodSpan(source);
    const offenders: string[] = [];
    let offset = 0;
    source.split("\n").forEach((line, index) => {
      const lineStart = offset;
      offset += line.length + 1;
      const called = REORIENTING_VIEWS.find((view) => line.includes(`${view}(`));
      if (!called) return;
      // A definition or a mention in prose is not a call; a call goes through
      // the globe instance.
      if (!line.includes(`this.globe.${called}(`)) return;
      // The three camera buttons under the globe, which is a reader asking.
      if (/byId\("[a-z-]*view"\)\.addEventListener/.test(line)) return;
      // The one sanctioned pull-up, and only from inside its own guarded
      // method — the same call anywhere else in the file still fails.
      if (called === SANCTIONED_PULL_UP.view && span && lineStart > span.start && lineStart < span.end) return;
      offenders.push(`src/main.ts:${index + 1}  ${line.trim()}`);
    });

    expect(
      offenders,
      "these lines reorient the globe without the reader asking; a layer may widen the view "
      + "(globe.frameActiveLayers) but must never rotate it",
    ).toEqual([]);
  });

  /**
   * The sanctioned exception is still the narrow thing it was argued for.
   *
   * Its method exists, it still carries both guards, and it is still reached
   * from one place: the magnetosphere checkbox, switched ON. Take any of that
   * away and this is no longer an exception, it is the defect 71b1437 removed.
   */
  it("keeps the magnetosphere pull-up guarded and reachable from one place", () => {
    const source = sources["src/main.ts"] ?? "";
    const span = sanctionedMethodSpan(source);
    expect(span, `${SANCTIONED_PULL_UP.method} is gone; the pull-up framing is unguarded or unwired`).not.toBeNull();
    const body = source.slice(span!.start, span!.end);
    SANCTIONED_PULL_UP.guards.forEach((guard) => {
      expect(
        body.includes(guard),
        `orientMagnetosphereOnPullUp lost its "${guard}" guard, so it can now rotate the globe under a reader`,
      ).toBe(true);
    });
    expect(
      body.includes(`this.globe.${SANCTIONED_PULL_UP.view}()`),
      "the sanctioned method no longer takes the Sun-on-the-left view Sean asked for",
    ).toBe(true);
    const callers = source.split("\n").filter((line) => line.includes("this.orientMagnetosphereOnPullUp()"));
    expect(
      callers.map((line) => line.trim()),
      "the magnetosphere pull-up framing must be reached from exactly one place: its own checkbox, switched on",
    ).toEqual([SANCTIONED_PULL_UP.caller]);
  });

  /**
   * And the widening path is still wired, because "stop moving the camera" is
   * only half the answer: a layer whose subject is entirely off screen must
   * still come into view, or the toggle appears to do nothing.
   */
  it("still makes room for a layer that does not fit", () => {
    const source = sources["src/main.ts"] ?? "";
    expect(
      source.includes("this.globe.frameActiveLayers()"),
      "nothing in main.ts asks the view to make room for what a layer draws",
    ).toBe(true);
  });
});
