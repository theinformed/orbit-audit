import { describe, expect, it } from "vitest";

import explorerSource from "../src/main.ts?raw";
import { currentConditionsView } from "../src/content";
import fixture from "./data/plasmasphere-dgcpm-2026-08-08.json";
import {
  PLASMAPAUSE_LIMITATION,
  PLASMAPAUSE_MAX_FRAME_AGE_MINUTES,
  describeFrameAge,
  plasmapauseCheckNote,
  plasmapauseFrameAgeMinutes,
  plasmapauseDialPoint,
  plasmapauseRimL,
  plasmapauseFrameStamp,
  plasmapauseMotion,
  plasmapauseRingGeometry,
  plasmapauseSummary,
  ringPath,
  type PlasmapauseFrame,
} from "../src/plasmapause-chart";

/** A boundary with a dusk bulge, which is the shape the real one has. */
const ring = (base: number, bulge: number) =>
  Array.from({ length: 48 }, (_, index) => {
    const mlt = index * 0.5;
    // Widest around 18 h (dusk), narrowest around 06 h.
    return base + bulge * Math.cos(((mlt - 18) / 24) * Math.PI * 2);
  });

const frames: PlasmapauseFrame[] = [
  { validAt: "2026-08-12T04:00:00Z", kp: 0.33, plasmapauseLByMlt: ring(4.40, 0.30), plume: { present: false, peakMltHours: 18, peakL: 4.7 } },
  { validAt: "2026-08-13T04:00:00Z", kp: 2.89, plasmapauseLByMlt: ring(4.16, 0.30) },
  { validAt: "2026-08-14T04:00:00Z", kp: 1.10, plasmapauseLByMlt: ring(4.46, 0.30), steepestGradientLByMlt: ring(4.70, 0.30) },
];

describe("the boundary, drawn where a magnetospheric figure puts it", () => {
  /**
   * Midnight at the bottom, noon at the top, dusk to the left. Getting this
   * wrong would put the dusk bulge on the dawn side and quietly teach the
   * opposite of the physics.
   */
  it("puts midnight at the bottom and noon at the top", () => {
    const geometry = plasmapauseRingGeometry(frames[0]!, 240, 7);
    const midnight = geometry.boundary[0]!;
    const noon = geometry.boundary.find((point) => point.mltHours === 12)!;
    expect(midnight.y).toBeGreaterThan(geometry.centre.y);
    expect(noon.y).toBeLessThan(geometry.centre.y);
    expect(midnight.x).toBeCloseTo(geometry.centre.x, 6);
  });

  /**
   * THE LABELS AND THE CURVE, CHECKED AGAINST EACH OTHER.
   *
   * They disagreed on the live site until 2026-08-26: the ring was drawn from
   * the corrected projection while the MLT tick labels in main.ts still carried
   * the −π/2-phase-with-negated-cosine version the geometry had been fixed away
   * from, so "00 MLT" was printed at the TOP over a midnight drawn at the
   * BOTTOM and "18" on the right over a dusk bulge drawn on the left. Both now
   * call plasmapauseDialPoint(), and this pins that they agree at all four
   * cardinal times rather than merely that each is internally consistent.
   */
  it("labels each quadrant where the curve actually puts it", () => {
    const geometry = plasmapauseRingGeometry(frames[0]!, 240, 7);
    // A label must lie on the RAY from centre through the curve point it names,
    // which is the whole claim and is not satisfied by a sign check alone.
    const direction = (point: { x: number; y: number }) => {
      const dx = point.x - geometry.centre.x;
      const dy = point.y - geometry.centre.y;
      const length = Math.hypot(dx, dy);
      return [dx / length, dy / length] as const;
    };
    for (const mlt of [0, 6, 12, 18]) {
      const onCurve = geometry.boundary.find((point) => point.mltHours === mlt)!;
      const label = plasmapauseDialPoint(mlt, 111, geometry.centre);
      expect(direction(label)[0]).toBeCloseTo(direction(onCurve)[0], 6);
      expect(direction(label)[1]).toBeCloseTo(direction(onCurve)[1], 6);
    }
    // And explicitly, in words: midnight below, noon above, dusk left.
    expect(plasmapauseDialPoint(0, 111, geometry.centre).y).toBeGreaterThan(geometry.centre.y);
    expect(plasmapauseDialPoint(12, 111, geometry.centre).y).toBeLessThan(geometry.centre.y);
    expect(plasmapauseDialPoint(18, 111, geometry.centre).x).toBeLessThan(geometry.centre.x);
    expect(plasmapauseDialPoint(6, 111, geometry.centre).x).toBeGreaterThan(geometry.centre.x);
  });

  /** And the renderer must use that export, not a second copy of the maths. */
  it("draws the tick labels from the shared projection", () => {
    const fn = explorerSource.slice(explorerSource.indexOf("private buildPlasmapauseSvg("));
    const body = fn.slice(0, fn.indexOf("\n  private ", 10));
    expect(body).toContain("plasmapauseDialPoint(mlt, radius, geometry.centre)");
    expect(body).not.toContain("Math.PI");
  });

  it("puts dusk to the left and dawn to the right", () => {
    const geometry = plasmapauseRingGeometry(frames[0]!, 240, 7);
    const dusk = geometry.boundary.find((point) => point.mltHours === 18)!;
    const dawn = geometry.boundary.find((point) => point.mltHours === 6)!;
    expect(dusk.x).toBeLessThan(geometry.centre.x);
    expect(dawn.x).toBeGreaterThan(geometry.centre.x);
  });

  /** The bulge is the teaching point: dusk sits further out than midnight. */
  it("draws the dusk bulge further from Earth than the midnight boundary", () => {
    const geometry = plasmapauseRingGeometry(frames[0]!, 240, 7);
    const radius = (mlt: number) => {
      const p = geometry.boundary.find((point) => point.mltHours === mlt)!;
      return Math.hypot(p.x - geometry.centre.x, p.y - geometry.centre.y);
    };
    expect(radius(18)).toBeGreaterThan(radius(0));
  });

  it("carries the published steepest-gradient check when the frame has one", () => {
    expect(plasmapauseRingGeometry(frames[2]!).check).toHaveLength(48);
    expect(plasmapauseRingGeometry(frames[1]!).check).toEqual([]);
  });

  it("marks a plume only when the frame says one is present", () => {
    expect(plasmapauseRingGeometry(frames[0]!).plume).toBeNull();
    const withPlume = plasmapauseRingGeometry(
      { ...frames[0]!, plume: { present: true, peakMltHours: 19, peakL: 4.72 } },
    );
    expect(withPlume.plume?.lRe).toBeCloseTo(4.72, 6);
  });

  /**
   * The publisher's own type allows a null at a local time where no crossing
   * of the contour was found. Drawing that as L 0 would spike the boundary
   * into the Earth and invent a plasmapause that touches the surface, so the
   * point is dropped and the ring simply has one fewer vertex.
   */
  it("drops a local time with no published crossing instead of drawing it at L 0", () => {
    const gapped: PlasmapauseFrame = {
      ...frames[0]!,
      plasmapauseLByMlt: frames[0]!.plasmapauseLByMlt.map((value, index) => (index === 10 ? null : value)),
    };
    const geometry = plasmapauseRingGeometry(gapped);
    expect(geometry.boundary).toHaveLength(47);
    expect(geometry.boundary.every((point) => point.lRe > 1)).toBe(true);
    // and the reported range ignores the hole rather than reading 0 as a minimum
    expect(geometry.minimumL).toBeGreaterThan(3);
  });

  it("closes the ring, and refuses to draw one from too few points", () => {
    expect(ringPath(plasmapauseRingGeometry(frames[0]!).boundary)).toMatch(/ Z$/);
    expect(ringPath([])).toBe("");
  });
});

describe("how far the boundary actually moves", () => {
  /**
   * The quantity that answers "does it move?", pinned against a SYNTHETIC span
   * chosen to match a real reading (L 4.16–4.46, about 1,930 km, taken from the
   * live artifact on 2026-08-14). Deliberately synthetic: the feed republishes
   * every two hours and that same window later read 4.14–4.51, so an assertion
   * against live values would be a test of the calendar. The real fixture is
   * exercised for PROPERTIES further down.
   */
  it("reports the travel in kilometres, not just in L", () => {
    const motion = plasmapauseMotion(frames)!;
    expect(motion.midnight.minimumL).toBeCloseTo(4.16, 2);
    expect(motion.midnight.maximumL).toBeCloseTo(4.46, 2);
    expect(motion.midnight.travelKm).toBeGreaterThan(1_800);
    expect(motion.midnight.travelKm).toBeLessThan(2_000);
  });

  it("reports the driving Kp range beside it, because that is the cause", () => {
    const motion = plasmapauseMotion(frames)!;
    expect(motion.kp.minimum).toBeCloseTo(0.33, 2);
    expect(motion.kp.maximum).toBeCloseTo(2.89, 2);
  });

  it("says nothing rather than something from a single frame", () => {
    expect(plasmapauseMotion([frames[0]!])).toBeNull();
    expect(plasmapauseSummary([])).toMatch(/No plasmapause boundary is published/);
  });

  it("states the travel and the Kp in one sentence", () => {
    const summary = plasmapauseSummary(frames);
    expect(summary).toMatch(/midnight L 4\.16–4\.46/);
    expect(summary).toMatch(/km of travel/);
    expect(summary).toMatch(/Kp 0\.33–2\.89/);
  });
});

describe("what the boundary is allowed to claim", () => {
  it("says it is simulation output and not a spacecraft crossing", () => {
    expect(PLASMAPAUSE_LIMITATION).toMatch(/simulation output driven by measured Kp/);
    expect(PLASMAPAUSE_LIMITATION).toMatch(/not a\s+spacecraft crossing/);
  });
});

/**
 * Against the real published fixture, which is how every other test of this
 * layer works (`tests/plasmasphere-dgcpm.test.ts` drives the same file). The
 * assertions are PROPERTIES rather than literals: the feed republishes every
 * two hours and the boundary genuinely moves, so pinning a number here would
 * make a passing test a matter of when it was written.
 */
describe("against the published DGCPM fixture", () => {
  const frames = (fixture as { frames: PlasmapauseFrame[] }).frames;

  it("reads all 48 local-time bins from every published frame", () => {
    expect(frames.length).toBeGreaterThanOrEqual(3);
    for (const frame of frames) {
      expect(frame.plasmapauseLByMlt).toHaveLength(48);
      expect(plasmapauseRingGeometry(frame).boundary.length).toBeGreaterThan(40);
    }
  });

  /**
   * The dusk bulge is a STORM feature, not a permanent one — asserting it on
   * every frame was wrong, and the fixture says so plainly:
   *
   *   Kp 0.33 → L 4.26–4.81, widest 22.0h, midnight 4.73, dusk 4.62
   *   Kp 5.67 → L 3.29–5.02, widest 16.0h, midnight 3.45, dusk 4.57
   *   Kp 2.44 → L 3.26–4.89, widest 18.5h, midnight 3.77, dusk 4.84
   *
   * Quiet, the boundary is nearly round and its widest point sits pre-midnight.
   * Disturbed, midnight erodes hard and the dusk sector stands off. That
   * contrast is the thing worth drawing, so it is the thing pinned here.
   */
  const disturbed = frames.filter((frame) => frame.kp >= 2);
  const quiet = frames.filter((frame) => frame.kp < 1);

  it("shows the dusk bulge on the disturbed frames", () => {
    expect(disturbed.length).toBeGreaterThan(0);
    for (const frame of disturbed) {
      const dusk = frame.plasmapauseLByMlt[36] as number;
      const midnight = frame.plasmapauseLByMlt[0] as number;
      expect(dusk).toBeGreaterThan(midnight);
      // and the widest point of the whole boundary lies in the dusk sector
      const values = frame.plasmapauseLByMlt.map((v) => (v === null ? -Infinity : v));
      const widestMlt = values.indexOf(Math.max(...values)) * 0.5;
      expect(widestMlt).toBeGreaterThanOrEqual(15);
      expect(widestMlt).toBeLessThanOrEqual(21);
    }
  });

  it("draws a rounder boundary when the field is quiet", () => {
    expect(quiet.length).toBeGreaterThan(0);
    const spread = (frame: PlasmapauseFrame) => {
      const values = frame.plasmapauseLByMlt.filter((v): v is number => v !== null);
      return Math.max(...values) - Math.min(...values);
    };
    for (const frame of quiet) expect(spread(frame)).toBeLessThan(1);
    for (const frame of disturbed) expect(spread(frame)).toBeGreaterThan(1);
  });

  /** Erosion: the night side is dragged inward as the drive rises. */
  it("erodes the midnight boundary as Kp rises", () => {
    const byKp = [...frames].sort((a, b) => a.kp - b.kp);
    const calmest = byKp[0]!.plasmapauseLByMlt[0] as number;
    const stormiest = byKp[byKp.length - 1]!.plasmapauseLByMlt[0] as number;
    expect(stormiest).toBeLessThan(calmest);
  });

  /** The boundary is inside the model's own L 2–8 grid, always. */
  it("keeps the boundary inside the published shell range", () => {
    for (const frame of frames) {
      for (const value of frame.plasmapauseLByMlt) {
        if (value === null) continue;
        expect(value).toBeGreaterThan(2);
        expect(value).toBeLessThan(8);
      }
    }
  });

  it("reports real motion across the fixture's frames, in kilometres", () => {
    const motion = plasmapauseMotion(frames)!;
    expect(motion.midnight.travelKm).toBeGreaterThan(0);
    expect(motion.midnight.maximumL).toBeGreaterThan(motion.midnight.minimumL);
    // Sanity: a boundary that moved more than three Earth radii between frames
    // would mean the decode is wrong, not that a storm was violent.
    expect(motion.midnight.travelKm).toBeLessThan(3 * 6371);
  });
});

/**
 * Wiring. This codebase has shipped features that every unit test passed over
 * and no entry point reached — seven in one release — so the chart asserts it
 * is actually mounted, and that it is exempt from the rule that hides a card
 * section with no fact grid in it.
 */
describe("the chart is actually on the Current conditions page", () => {
  it("is filled from fillLayerCard, the way the X-ray trace is", () => {
    // The grain cloud left the rail on 2026-08-18 and the boundary moved to the
    // Current conditions page, on the same page as the Kp series that squeezes
    // it — at the FOOT of it since 2026-08-26. So the chart is mounted from the
    // page, not from a layer card that no longer exists — and it still loads
    // its own bundle, which is what makes it real rather than dependent on some
    // other layer having been switched on first.
    expect(explorerSource).toContain("private mountPlasmapause()");
    expect(explorerSource).toMatch(/void this\.loadPlasmasphere\(\)\.then\(\(\) => this\.mountPlasmapause\(\)\);/);
    expect(explorerSource).toContain("private fillPlasmapauseSection(");
  });

  /**
   * PLACEMENT IS PART OF THE CLAIM. The section spent its life second on the
   * page, above every NOAA product, and a simulation ranked above the official
   * measurement is a claim the page cannot support. It now sits last, after
   * "Go to the source", and it is labelled MODEL so the "this page reformats
   * NOAA's published values" sentence cannot be read as covering it.
   *
   * Asserted on ORDER rather than on prose, because prose is the part that
   * gets rewritten and order is the part that carries the meaning.
   */
  it("sits below the official NOAA products, not above them", () => {
    const markup = currentConditionsView();
    expect(markup.indexOf("now-plasmapause")).toBeGreaterThan(markup.indexOf("OFFICIAL PRODUCTS"));
    expect(markup.indexOf("now-plasmapause")).toBeGreaterThan(markup.indexOf("now-swpc-mount"));
    expect(markup).toContain("now-coda");
    expect(markup).toMatch(/class="layer-status model">MODEL</);
  });

  /** And the coda hands the reader on rather than trailing off. */
  it("ends with a bound route to the plasmasphere layer page", () => {
    expect(currentConditionsView()).toContain("data-plasmapause-layer-page");
    expect(explorerSource).toContain('document.querySelector<HTMLButtonElement>("[data-plasmapause-layer-page]")');
    expect(explorerSource).toContain('layerPageView("plasmasphere")');
  });

  /**
   * An SVG is neither a `.fact-grid` nor an `.ephemeris`, and `fillLayerCard`
   * hides any section without one. Without this exemption the chart would be
   * built correctly and hidden on every refill — invisible, and green.
   */
  it("is exempt from the empty-section rule that would hide an SVG", () => {
    expect(explorerSource).toMatch(/section\.dataset\.cardSection === "plasmapause"\) return;/);
  });

  /**
   * IT DRAWS THE NEWEST PUBLISHED FRAME, NOT "THE FRAME NEAREST NOW".
   *
   * This is the fix for the defect the owner reported as "the diagram isn't
   * loading". The page used to ask the globe for the field at the selected
   * instant, which on this page is NOW, and the globe refuses unless a frame
   * lies within half a cadence. The newest published frame is NEVER at now —
   * the pipeline floors the build clock onto a two-hourly UTC grid — so the
   * chart went dark for at least half of every cycle. Measured live on
   * 2026-08-26: dark at 15:55 UTC (newest frame 14:00 UTC), drawn at 16:06 UTC
   * (newest frame 16:00 UTC), no code changed in between.
   *
   * The regression guard is that the render path must NOT be reading the
   * globe's evaluated field any more.
   */
  it("draws the newest published frame and never asks the globe for one", () => {
    const fn = explorerSource.slice(explorerSource.indexOf("private fillPlasmapauseSection("));
    const body = fn.slice(0, fn.indexOf("\n  /** The boundary ring"));
    expect(body).toContain("this.plasmasphereSequence?.bundle.frames");
    expect(body).toContain("frames[frames.length - 1]");
    // Comments stripped: the function EXPLAINS what it stopped calling, and a
    // check that reads its own explanation as evidence proves nothing.
    const code = body.split("\n").filter((line) => !line.trim().startsWith("//")).join("\n");
    expect(code).not.toContain("getPlasmasphereField");
  });

  /** Absence is three different facts, and it says which one in words. */
  it("states in words why it cannot draw, and never leaves an empty box", () => {
    const fn = explorerSource.slice(explorerSource.indexOf("private fillPlasmapauseSection("));
    const body = fn.slice(0, fn.indexOf("\n  /** The boundary ring"));
    expect(body).toMatch(/publishes no plasmasphere simulation/);
    expect(body).toMatch(/could not be loaded/);
    expect(body).toMatch(/past the/);
    expect(body).toContain("plasmapause-chart--empty");
  });

  /** The picture says which frame it is, so "now" is never implied. */
  it("stamps the drawn frame with its own valid time", () => {
    expect(explorerSource).toContain("plasmapauseFrameStamp(frame, new Date())");
  });
});

/**
 * NOTHING IS DRAWN OUTSIDE THE RULER.
 *
 * Found 2026-08-26 by looking at the built page against the live artifact, which
 * is the only way it could have been found: every test in this file passed, the
 * typecheck passed, and the picture was wrong.
 *
 * The plot's rim was the constant 7. The published steepest-gradient check
 * saturates at L 7.95 — the second-from-last node of the model's own L 2.0–8.0
 * grid — in the pre-midnight sector on ALL 25 frames live that day and on 2 of
 * the 3 in this fixture, while the 50 cm⁻³ boundary never leaves L 4.3–5.1. So
 * the chart drew a violet lobe past its outermost L ring, past the plot extent,
 * and — because the SVG carries `overflow: visible` so the dial labels are not
 * clipped — outside the plot box entirely, across the 18 MLT tick. Three Earth
 * radii of unlabelled mark, in the exact sector the lede tells the reader to
 * look at for the dusk bulge.
 *
 * The rim is now derived from what will be drawn. These are the assertions that
 * would have caught it, and the last one is the negative control: at the old
 * constant they FAIL on this fixture, so they have teeth.
 */
describe("the plot reaches as far as the marks it draws", () => {
  const published = (fixture as { frames: PlasmapauseFrame[] }).frames;

  const outermost = (geometry: ReturnType<typeof plasmapauseRingGeometry>) =>
    Math.max(...geometry.rings.map((ring) => ring.radius));
  const furthest = (geometry: ReturnType<typeof plasmapauseRingGeometry>) =>
    Math.max(...[...geometry.boundary, ...geometry.check, ...(geometry.plume ? [geometry.plume] : [])]
      .map((point) => Math.hypot(point.x - geometry.centre.x, point.y - geometry.centre.y)));

  it("keeps every published mark inside the outermost L ring", () => {
    for (const frame of published) {
      const geometry = plasmapauseRingGeometry(frame, 240);
      // A tenth of a pixel of tolerance: the furthest mark is allowed to sit ON
      // the rim ring, which is what a derived rim means, but never beyond it.
      expect(furthest(geometry)).toBeLessThanOrEqual(outermost(geometry) + 0.1);
    }
  });

  it("would have drawn outside it at the old constant rim of 7", () => {
    const escaping = published.filter((frame) => {
      const geometry = plasmapauseRingGeometry(frame, 240, 7);
      return furthest(geometry) > outermost(geometry) + 0.1;
    });
    expect(escaping.length).toBeGreaterThan(0);
  });

  it("rounds the rim up to a whole 2 L step, with a floor of 6", () => {
    // The real shape of the problem: a check that saturates near the grid edge.
    expect(plasmapauseRimL({ ...frames[0]!, steepestGradientLByMlt: ring(7.0, 0.95) })).toBe(8);
    // A quiet frame is not zoomed in on until the boundary fills the box.
    expect(plasmapauseRimL(frames[0]!)).toBe(6);
    expect(plasmapauseRimL({ ...frames[0]!, plasmapauseLByMlt: ring(6.2, 0.3) })).toBe(8);
  });

  /** And the Earth is drawn at L 1 on whatever scale the rim sets, from one place. */
  it("hands the renderer the Earth's radius rather than a second copy of the scale", () => {
    const geometry = plasmapauseRingGeometry(frames[0]!, 240);
    const lTwo = geometry.rings.find((ring) => ring.lRe === 2)!;
    expect(geometry.earthRadius).toBeCloseTo(lTwo.radius / 2, 6);
    expect(explorerSource).toContain("geometry.earthRadius.toFixed(2)");
    expect(explorerSource).not.toContain("((size / 2 - 18) / 7)");
  });
});

/**
 * AND THE READER IS TOLD WHAT THE LOBE IS.
 *
 * Fitting the check inside the ruler stops it escaping the box; it does not
 * stop it being read as a plume or as the dusk bulge, because it is enormous
 * and it is in the dusk-to-midnight sector where the bulge belongs. It is not
 * a boundary out there — it is the gradient search reaching the edge of the
 * traced domain. The curve stays drawn, because a chart that offers an
 * independent check may not hide the check when it disagrees.
 */
describe("what the chart says about the two curves disagreeing", () => {
  const published = (fixture as { frames: PlasmapauseFrame[] }).frames;
  const domainMaxL = 8;

  it("names the separation, the local time, and the grid edge that caused it", () => {
    const note = plasmapauseCheckNote(published[0]!, domainMaxL)!;
    expect(note).toMatch(/steepest-gradient check runs out to L 7\.\d\d/);
    expect(note).toMatch(/MLT/);
    expect(note).toMatch(/50 cm⁻³ boundary stays inside L 4\.\d\d/);
    expect(note).toMatch(/outer edge of the model's own grid \(L 8\.0\)/);
    expect(note).toMatch(/neither a second boundary nor a plume/);
  });

  it("says nothing when the two curves agree, rather than filling space", () => {
    // frames[2] carries a check 0.24 L outside its boundary: close agreement,
    // nothing a reader could misread, no sentence.
    expect(plasmapauseCheckNote(frames[2]!, domainMaxL)).toBeNull();
    // and a frame with no published check has nothing to say either way
    expect(plasmapauseCheckNote(frames[1]!, domainMaxL)).toBeNull();
  });

  it("still states the separation when the publisher's grid is unknown", () => {
    const note = plasmapauseCheckNote(published[0]!)!;
    expect(note).toMatch(/runs out to L 7\./);
    expect(note).not.toMatch(/edge of the model's own grid/);
  });

  /** Wiring: the page must actually pass the bundle's own grid, not a guess. */
  it("is built from the published grid and reaches the caption", () => {
    expect(explorerSource).toContain("this.plasmasphereSequence?.bundle.grid.lValues");
    expect(explorerSource).toContain("plasmapauseCaption(frames, plasmapauseCheckNote(newest, domainMaxL))");
  });
});

/**
 * The frame stamp, which is what lets the chart draw a frame that is not "now"
 * without claiming that it is.
 */
describe("how old the drawn frame is", () => {
  const frame: PlasmapauseFrame = {
    validAt: "2026-08-26T16:00:00Z",
    kp: 2.44,
    plasmapauseLByMlt: ring(4.4, 0.3),
  };

  it("measures the age of a published frame in whole minutes", () => {
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T16:06:00Z"))).toBe(6);
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T17:55:00Z"))).toBe(115);
    // A frame can lead the clock: the pipeline publishes the grid instant at or
    // after the build time, so this is a real state and not an error.
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T15:56:00Z"))).toBe(-4);
    expect(plasmapauseFrameAgeMinutes({ ...frame, validAt: "not a time" }, new Date())).toBeNull();
  });

  it("says how old in words a reader would use", () => {
    expect(describeFrameAge(6)).toBe("6 min old");
    expect(describeFrameAge(115)).toBe("1 h 55 min old");
    expect(describeFrameAge(120)).toBe("2 h old");
    expect(describeFrameAge(0)).toBe("the current frame");
    expect(describeFrameAge(-4)).toBe("the current frame");
  });

  /**
   * The exact pair of live readings that identified the defect. At 15:55 UTC
   * the newest frame was 14:00 UTC and the old ±60-minute rule rejected it; the
   * chart now draws it and says it is 1 h 55 min old.
   */
  it("stamps the frame that the old tolerance would have thrown away", () => {
    const stale = { ...frame, validAt: "2026-08-26T14:00:00Z", kp: 0.33 };
    const stamp = plasmapauseFrameStamp(stale, new Date("2026-08-26T15:55:00Z"));
    expect(stamp).toContain("26 Aug 14:00 UTC");
    expect(stamp).toContain("1 h 55 min old");
    expect(stamp).toContain("Kp 0.33");
    expect(plasmapauseFrameAgeMinutes(stale, new Date("2026-08-26T15:55:00Z"))!).toBeGreaterThan(60);
  });

  /**
   * There is still a floor. Six hours is three publish cycles; past it the
   * artifact has stopped being refreshed and drawing it under a heading about
   * current conditions would present stale output as the present.
   */
  it("keeps a staleness bound of three publish cycles", () => {
    expect(PLASMAPAUSE_MAX_FRAME_AGE_MINUTES).toBe(360);
    // Five hours after the frame: old, said so, still drawn.
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T21:00:00Z"))!).toBe(300);
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T21:00:00Z"))!)
      .toBeLessThan(PLASMAPAUSE_MAX_FRAME_AGE_MINUTES);
    // Seven hours after it: the pipeline has stopped, and the chart refuses.
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T23:00:00Z"))!).toBe(420);
    expect(plasmapauseFrameAgeMinutes(frame, new Date("2026-08-26T23:00:00Z"))!)
      .toBeGreaterThan(PLASMAPAUSE_MAX_FRAME_AGE_MINUTES);
  });
});
