import eventsSource from "../data/events.json?raw";
import buildReleaseSource from "../pipeline/build_release.py?raw";
import replaySource from "../src/event-replay.ts?raw";
import replayStyleSource from "../src/event-replay.css?raw";
import contentSource from "../src/content.ts?raw";
import indexSource from "../index.html?raw";
import { eventMediaLine, eventsView } from "../src/content";
import { EVENT_MEDIA, eventObservedClipCount } from "../src/observed-imagery";
import imagerySource from "../src/observed-imagery.ts?raw";
import narrationManifest from "../media/narration/manifest.json";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * The historical-events page, checked at the only place it can be checked
 * cheaply: the artifact the browser is handed, and the source that draws it.
 *
 * Two of these guards exist because of things that actually went wrong.
 *
 * THE KIND GUARD. `mountEventReplay` dispatches on `replay.kind` and returns
 * null for a kind it does not know, and the page then renders the milestone
 * prose with an EMPTY box where the chart belongs. That is not a crash and no
 * test caught it: the data publishes on its own five-minute timer while the
 * frontend ships in a Docker image, so an artifact carrying a new kind reaches
 * real visitors before the code that can draw it. This test fails the build on
 * bigmem the moment those two disagree, which is the earliest point anyone can
 * see it.
 *
 * THE RETIRED-FIELDS GUARD. Every milestone used to carry `solarWind`,
 * `magnetosphereCompression`, `ionosphere` and `radiation` -- four
 * hand-authored numbers between 0 and 1 that drove a blob, a line and a
 * saturation filter. The picture is gone. If those names come back, someone is
 * re-inventing unmeasured data for a drawing, and that is the one thing this
 * page exists not to do.
 */
const bundle = JSON.parse(eventsSource) as {
  schema: number;
  events: Array<Record<string, any>>;
};

const RETIRED = ["solarWind", "magnetosphereCompression", "ionosphere", "radiation"];

describe("the historical events artifact", () => {
  it("gives every event the things a card and a player both need", () => {
    expect(bundle.events.length).toBeGreaterThanOrEqual(4);
    for (const event of bundle.events) {
      for (const field of ["id", "title", "shortTitle", "date", "status", "summary", "lesson"]) {
        expect(typeof event[field], `${event.id}.${field}`).toBe("string");
        expect(event[field].length, `${event.id}.${field}`).toBeGreaterThan(0);
      }
      // Two sources is the house grammar: one that frames the event, one that
      // shows what the instruments saw. A citation that is not a link is not a
      // citation anyone can check.
      expect(event.sources.length, `${event.id} sources`).toBeGreaterThanOrEqual(2);
      for (const source of event.sources) {
        expect(source.label.length).toBeGreaterThan(0);
        expect(source.url).toMatch(/^https:\/\//);
      }
    }
  });

  it("keeps every milestone traceable and in order, with no retired display numbers", () => {
    for (const event of bundle.events) {
      expect(event.milestones.length, `${event.id} milestones`).toBeGreaterThanOrEqual(3);
      let previous = -Infinity;
      for (const milestone of event.milestones) {
        expect(Number.isFinite(milestone.offsetMinutes), `${event.id} offsetMinutes`).toBe(true);
        expect(milestone.offsetMinutes, `${event.id} milestones out of order`).toBeGreaterThan(previous);
        previous = milestone.offsetMinutes;
        expect(milestone.title.length).toBeGreaterThan(0);
        expect(milestone.description.length).toBeGreaterThan(20);
        for (const dead of RETIRED) {
          expect(milestone, `${event.id} carries the retired ${dead}`).not.toHaveProperty(dead);
        }
      }
    }
  });

  it("never publishes a replay kind the renderer cannot draw", () => {
    const drawable = new Set(
      [...replaySource.matchAll(/case "([a-z-]+)":/g)].map((match) => match[1]));
    expect(drawable.size).toBeGreaterThan(0);
    for (const event of bundle.events) {
      if (!event.replay) continue;
      expect(drawable, `${event.id} publishes kind "${event.replay.kind}"`)
        .toContain(event.replay.kind);
    }
  });

  it("draws each event from measurements or draws nothing, and says which", () => {
    // The rule the page is built on. An event with a replay carries a status
    // and a provenance block; an event without one is allowed, and gets the
    // labelled milestone prose instead of a picture that could be anyone's.
    for (const event of bundle.events) {
      if (!event.replay) continue;
      expect(event.replay.status, `${event.id} replay status`).toBeTruthy();
      expect(Object.keys(event.replay.provenance ?? {}).length,
             `${event.id} replay provenance`).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("the three-clocks charts", () => {
  const charts = bundle.events.filter((event) => event.replay?.kind === "three-clocks");

  it("has more than one, because one cannot teach that the spacing varies", () => {
    expect(charts.length).toBeGreaterThanOrEqual(2);
  });

  it("puts real samples in time order inside the axis it declares", () => {
    for (const event of charts) {
      const replay = event.replay;
      expect(replay.lanes.length).toBe(3);
      for (const lane of replay.lanes) {
        expect(lane.evidence).toBe("measurement");
        expect(lane.points.length, `${event.id}/${lane.id}`).toBeGreaterThan(10);
        let previous = -Infinity;
        for (const [minutes, value] of lane.points) {
          expect(minutes).toBeGreaterThan(previous);
          previous = minutes;
          expect(Number.isFinite(value)).toBe(true);
        }
      }
      let previous = -Infinity;
      for (const arrival of replay.arrivals) {
        expect(arrival.minutes, `${event.id} arrivals out of order`).toBeGreaterThanOrEqual(previous);
        previous = arrival.minutes;
        expect(arrival.minutes).toBeLessThanOrEqual(replay.maxMinutes);
        expect(arrival.note.length).toBeGreaterThan(40);
      }
    }
  });
});

/**
 * The play loop, and the captions it stops at.
 *
 * Sean, 2026-08-26, on the Starlink replay: "The animation doesn't seem to
 * flow steadily. it sort of jumps." It had two separate reasons to, and these
 * are the guards against either coming back.
 */
describe("how the replays play", () => {
  it("never drives an animation from a fixed-step interval again", () => {
    // `setInterval(..., 32)` plus a fixed increment gives an animation whose
    // speed is whatever the main thread had left over: a tick that arrives
    // late still advances the same distance. Measured on the built page, the
    // Starlink replay's 32 ms interval was arriving every ~385 ms and the same
    // play ran between 8 and 66 event-hours per second. Every loop in this
    // file now integrates rate x elapsed on requestAnimationFrame.
    const code = replaySource.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g, "");
    expect(code).not.toMatch(/setInterval/);
    expect(code).toMatch(/requestAnimationFrame/);
  });

  it("never steps the playback rate, and eases it instead", () => {
    // The orbit-decay loop used to quadruple its speed the instant the cursor
    // passed hour 336, at a moment nothing on the chart marks.
    expect(replaySource).not.toContain("this.cursor < 336 ? 3 : 12");
    expect(replaySource).toContain("DECAY_SLOW_HOURS_PER_SECOND");
    expect(replaySource).toContain("DECAY_FAST_HOURS_PER_SECOND");
    // A smoothstep between the two, so no frame advances further than the one
    // before it by more than the easing allows.
    expect(replaySource).toMatch(/along \* along \* \(3 - 2 \* along\)/);
  });

  it("asks whether the visitor wants less movement", () => {
    expect(replaySource).toContain("prefers-reduced-motion");
    expect(replaySource).toMatch(/this\.reduced = prefersReducedMotion\(\)/);
  });
});

/**
 * The caption plate.
 *
 * Sean: "add some text boxes to the animation that show what is happening ...
 * You'd need to make sure the text boxes don't overlap anything."
 */
describe("the replay captions", () => {
  it("is laid out in the flow, which is why it cannot overlap anything", () => {
    // The plate sits between the picture and the scrubber as an ordinary grid
    // item. There is no position to get wrong at any width. If a future change
    // floats it over the canvas, it acquires the whole class of bugs this
    // avoided -- covering traces, colliding with in-chart labels, and hiding
    // the plot entirely on a 390 px phone.
    const rule = replayStyleSource.slice(
      replayStyleSource.indexOf(".replay-captions {"),
      replayStyleSource.indexOf("}", replayStyleSource.indexOf(".replay-captions {")));
    expect(rule.length).toBeGreaterThan(0);
    expect(rule).not.toMatch(/position:\s*(absolute|fixed|sticky)/);
    // A reserved height, so a short caption does not move the controls up and
    // a long one does not push them down.
    expect(rule).toMatch(/min-height/);
    expect(replaySource).toContain('${CAPTIONS}\n  <div class="replay-controls">');
  });

  it("announces itself to a screen reader as it changes", () => {
    expect(replaySource).toContain('role="status" aria-live="polite"');
  });

  it("actually hides the plate when a replay has nothing to say", () => {
    // MEASURED DEFECT, 2026-08-26. The plate ships in every replay's markup
    // carrying the `hidden` attribute, and `.replay-captions` sets
    // `display: grid`. A class selector beats the user agent's own
    // `[hidden] { display: none }`, so the attribute did nothing: all five
    // uncaptioned replays drew an empty 96 px box with a lit cyan edge between
    // the picture and the scrubber. Confirmed in a real browser at 96 px tall
    // before this rule, 0 px after. Every other hideable component in this
    // project states the same rule; this one had missed it.
    expect(replayStyleSource).toMatch(/\.replay-captions\[hidden\]\s*\{[^}]*display:\s*none/);
  });

  it("serves captions only to the replay that asked for them", () => {
    // Sean, having seen the first captioned build: "most of the historical
    // events are great, it is just the starlink one that I want to fix." A
    // caption holds the picture still while it is read, so switching them on
    // for every replay turned events he already liked into much longer ones --
    // St Patrick 4.35 s to 21.6 s, Halloween 4.36 s to 36.9 s, measured on the
    // capture harness. The stops are still WORKED OUT everywhere and SERVED
    // only where wanted. If this gate is ever removed, that regression returns
    // silently, because nothing about it is visible in a still screenshot.
    expect(replaySource).toContain("protected captionsEnabled(): boolean { return false; }");
    expect(replaySource).toContain(
      "new CaptionTrack(root, this.captionsEnabled() ? this.captionStops() : [])");
    // ...and a track built with no stops must stay entirely inert: no plate,
    // no hold on the clock, so a view that returns false plays exactly as it
    // did before any of this landed.
    expect(replaySource).toMatch(/this\.box = stops\.length > 0 \? .* : null;/);
  });

  it("quotes the sourced prose rather than writing its own", () => {
    // Captions are milestone text, arrival notes and mark details -- all of it
    // already printed in full under the picture -- shortened only by taking
    // whole sentences off the front. Nothing in a caption is a sentence this
    // renderer composed.
    expect(replaySource).toMatch(/function firstSentences/);
    expect(replaySource).toMatch(/text: firstSentences\(milestone\.description/);
    expect(replaySource).toMatch(/text: firstSentences\(arrival\.note/);
    expect(replaySource).toMatch(/text: firstSentences\(mark\.note/);
  });

  it("never HOLDS the Starlink replay on a frame it has not drawn anything on", () => {
    // MEASURED DEFECT, 2026-08-26. Sean, on the deployed page: "the starlink
    // video doesn't play now." It was playing. The first caption stop is at
    // hour 0 and the catalogue publishes no element set for any of these
    // objects until hour 64.2, so pressing Play held a completely empty plot
    // for the first caption's dwell, and then held the SAME empty plot for the
    // second caption's dwell at hour 9. Measured on this repository's capture
    // harness: the canvas was pixel-identical for 6.68 s after Play and the
    // first trace was not drawn until 14.1 s. A picture that stands still for
    // six seconds the instant you press Play is indistinguishable from a
    // broken one.
    //
    // The hold is now a SWEEP of the same length: stops that fall before the
    // first published element set are shown as the sweep passes them, and the
    // run-up is crossed at whatever rate covers it in the time that first hold
    // used to take. After: first repaint 264 ms, first trace 8.27 s. If either
    // half of that is removed -- the `hold: false` on the early stops, or the
    // rate that makes them readable -- the picture stands still again and
    // nothing about it is visible in a screenshot.
    expect(replaySource).toContain("hold?: boolean;");
    expect(replaySource).toContain("hold: stop.hold !== false");
    expect(replaySource).toContain("...(at < this.firstDrawnHour ? { hold: false } : {})");
    expect(replaySource).toContain("if (stop && (stop.hold || this.reduced))");
    expect(replaySource).toContain("private openingRate(hours: number): number {");
    // A reader who asked for reduced motion still gets every hold: there is no
    // motion to protect and the dwell is their only time to read.
    expect(replaySource).toMatch(/stop\.hold \|\| this\.reduced/);
    // ...and the stops this applies to really are over an empty plot.
    const event = bundle.events.find((candidate) => candidate.id === "starlink-2022");
    const firstSampleHour = Math.min(...event!.replay.objects
      .map((object: any) => object.samples[0][0]));
    expect(firstSampleHour, "starlink now draws from the first hour; the opening sweep is moot")
      .toBeGreaterThan(24);
  });

  it("does not time the Starlink captions from milestone offsets, because they are on a different clock", () => {
    // THIS TEST IS A TRIPWIRE, not a preference. `offsetMinutes` counts from
    // each event's own narrative origin. For starlink-2022 that origin is not
    // the start of the replay window: the third milestone sits at 21 h and the
    // catalogue publishes no element set for any of these objects until 64 h,
    // so timing the captions off the offsets would show two of the four over
    // an empty chart. `OrbitDecayView.captionStops()` anchors them to the
    // chart's own landmarks instead. If the offsets are ever corrected to the
    // replay's clock, this test fails -- and the anchoring should be revisited
    // rather than the test relaxed.
    const event = bundle.events.find((candidate) => candidate.id === "starlink-2022");
    expect(event).toBeDefined();
    const firstSampleHour = Math.min(...event!.replay.objects
      .map((object: any) => object.samples[0][0]));
    const lastOffsetHours = event!.milestones[event!.milestones.length - 1].offsetMinutes / 60;
    expect(lastOffsetHours,
      "starlink milestone offsets now reach past the first published element set; " +
      "recheck OrbitDecayView.captionStops()").toBeLessThan(firstSampleHour);
    expect(replaySource).toContain("private captionStops(): ReplayCaption[] {");
    expect(replaySource).toContain("this.peakDriverHour()");
  });
});

/**
 * Two three-clock charts, and why a reader must be able to tell them apart.
 *
 * Sean, 2026-08-26: "can you get an agent to look at the halloween and bastille
 * day events? They seem to have the same animation. I think there is some sort
 * of error there." There is not: the measurements differ. But on a logarithmic
 * axis from half a minute to five days, a proton onset at 40 minutes and one at
 * 2 h 22 min are a centimetre apart, and the contrast is the entire reason the
 * second chart exists. It is now stated in numbers under each picture.
 */
describe("telling the two three-clock events apart", () => {
  const charts = bundle.events.filter((event) => event.replay?.kind === "three-clocks");
  const gap = (event: any, id: string) => {
    const light = event.replay.arrivals.find((arrival: any) => arrival.id === "light");
    const target = event.replay.arrivals.find((arrival: any) => arrival.id === id);
    return target && light ? target.minutes - light.minutes : null;
  };

  it("prints the separations rather than leaving them to be measured off the axis", () => {
    expect(replaySource).toContain("private sinceLight(");
    expect(replaySource).toContain("private separations(");
    expect(replaySource).toContain("${this.separations()}");
  });

  it("has a light-to-particles separation for every such chart, and they are not alike", () => {
    const gaps = charts.map((event) => gap(event, "protons"));
    for (const value of gaps) expect(value).not.toBeNull();
    const smallest = Math.min(...(gaps as number[]));
    const largest = Math.max(...(gaps as number[]));
    // Halloween 2003: 142 minutes. Bastille 2000: 40. A reader should not have
    // to do arithmetic to see that, so the number is on the page -- but if two
    // charts ever DID have the same separation, the second one would have
    // nothing to teach and this test should be the thing that says so.
    expect(largest / smallest).toBeGreaterThan(2);
  });

  it("can compute all three separations for every such chart", () => {
    for (const event of charts) {
      for (const id of ["flarePeak", "protons", "fieldMin"]) {
        expect(gap(event, id), `${event.id} has no ${id} arrival`).not.toBeNull();
        expect(gap(event, id)).toBeGreaterThan(0);
      }
    }
  });
});

describe("the southward-turning chart", () => {
  const event = bundle.events.find((candidate) => candidate.replay?.kind === "southward-turning");

  it("is on the page", () => {
    expect(event).toBeDefined();
  });

  it("carries a band that is a real range around a real sample", () => {
    for (const lane of event!.replay.lanes) {
      expect(lane.points.length + lane.emptyBins, `${lane.id} bins`).toBe(lane.binCount);
      let previous = -Infinity;
      for (const point of lane.points) {
        expect(point.length, `${lane.id} point shape`).toBe(4);
        const [minutes, value, low, high] = point;
        expect(minutes).toBeGreaterThan(previous);
        previous = minutes;
        expect(minutes).toBeGreaterThanOrEqual(0);
        expect(minutes).toBeLessThanOrEqual(event!.replay.spanMinutes);
        // The drawn sample is one of the samples the band was taken over, so
        // it cannot sit outside it. If it ever does, something averaged.
        expect(low, `${lane.id} at ${minutes}`).toBeLessThanOrEqual(value);
        expect(high, `${lane.id} at ${minutes}`).toBeGreaterThanOrEqual(value);
      }
    }
  });

  it("marks extrema that are inside the window and in time order", () => {
    let previous = -Infinity;
    for (const mark of event!.replay.marks) {
      expect(mark.minutes).toBeGreaterThanOrEqual(previous);
      previous = mark.minutes;
      expect(mark.minutes).toBeLessThanOrEqual(event!.replay.spanMinutes);
      expect(Date.parse(mark.at)).toBeGreaterThan(0);
      expect(mark.note.length).toBeGreaterThan(40);
    }
  });

  it("says SYM/H is SYM/H and not Dst", () => {
    // Papers on this storm quote Dst -223 nT and the one-minute index reads
    // -234. Both are right; a page that printed one and named the other would
    // be wrong in the way that is hardest to notice.
    expect(event!.replay.provenance.symh).toMatch(/SYM\/H/);
    expect(event!.replay.provenance.symh).toMatch(/not Dst|NOT Dst/);
  });
});

describe("the page header", () => {
  it("says what the page is rather than setting a mood", () => {
    const header = contentSource.slice(contentSource.indexOf("export function eventsView"));
    const hero = header.slice(0, header.indexOf("</header>"));
    expect(hero).not.toContain("Watch the chain unfold");
    expect(hero).not.toContain("IMMUTABLE TEACHING BUNDLES");
    // The nav button says "Historical events"; the reader has to land
    // somewhere that reads like the place they clicked into.
    expect(hero.toUpperCase()).toContain("HISTORICAL EVENTS");
  });
});

/*
 * The withhold.
 *
 * `REPLAY_WITHHOLDS` in pipeline/build_release.py strips a `replay` block out
 * of the PUBLISHED artifact without touching this source bundle. It exists
 * because the data ships on a five-minute timer and the frontend ships in a
 * Docker image, so an event with a new replay kind reaches visitors before the
 * code that draws it.
 *
 * These two tests are what stop the withhold from doing damage on its way to
 * being removed. The first says the data is still here — a withhold must thin
 * the copy that is published and never the record. The second says a withhold
 * has to name a real event, so a rename cannot leave a live one pointing at
 * nothing.
 */
describe("the publish-time replay withhold", () => {
  const releaseSource = buildReleaseSource;
  // From the top of the comment, not from the dict: the comment IS the part
  // that has to survive, because it carries the date and the removal test.
  const block = releaseSource.slice(
    releaseSource.indexOf("# TEMPORARY: replays held back from the published artifact"),
    releaseSource.indexOf("def withhold_undeployable_replays"));
  const withheld = [...block.matchAll(/^\s{4}"([a-z0-9-]+)":/gm)].map((match) => match[1]);

  it("never withholds an event that is not on the page", () => {
    const ids = new Set(bundle.events.map((event) => event.id));
    for (const id of withheld) {
      expect(ids, `REPLAY_WITHHOLDS names ${id}, which no event has`).toContain(id);
    }
  });

  it("thins only the published copy, never the source bundle", () => {
    // The point of holding a replay back is that it is READY and the frontend
    // is not. If the data went missing here, the withhold would have destroyed
    // the very thing it is protecting.
    for (const id of withheld) {
      const event = bundle.events.find((candidate) => candidate.id === id);
      expect(event?.replay, `${id} is withheld from publication but has no replay to restore`)
        .toBeTruthy();
    }
  });

  it("says why, and how to remove itself", () => {
    if (withheld.length === 0) return;
    expect(block).toMatch(/ADDED \d{4}-\d{2}-\d{2}/);
    expect(block).toMatch(/REMOVE BY SETTING THIS DICT TO \{\}/);
    expect(block).toMatch(/WHAT MUST BE TRUE TO REMOVE IT/);
  });
});

/*
 * HOW A REPLAY OPENS.
 *
 * Sean, 2026-08-21: "when you click to open the event, it looks like it opens
 * all events and scrolls the page through all of them to the correct one ...
 * This isn't good the way it is."
 *
 * Only one event was ever open. `eventsView()` rendered a hidden
 * `<div id="event-player">` ABOVE the grid and `openEventPlayer()` filled it,
 * unhid it and called `scrollIntoView({ behavior: "smooth" })` — so opening the
 * last card smooth-scrolled the whole grid past the reader to reach a panel at
 * the top of the page. The player is now the body of a modal <dialog> and
 * nothing scrolls.
 *
 * These are source guards, not behaviour: the behaviour lives in
 * tests/browser.spec.ts, which drives the real dialog. What they protect is the
 * shape that made the behaviour possible, because every part of it is one line
 * away from being written back by accident.
 */
describe("the replay opens in a dialog, not in the page", () => {
  it("does not put a player back inside the events page", () => {
    // Rendered, not grepped: the comment above eventsView() quotes the markup
    // it removed, and a source grep would read that as the markup coming back.
    const rendered = eventsView({ events: bundle.events } as never);
    expect(rendered, "the player belongs in #event-dialog, not above the grid")
      .not.toContain("event-player");
    expect(rendered).toContain("event-grid");
  });

  it("keeps the player inside the dialog in index.html", () => {
    const dialog = indexSource.slice(
      indexSource.indexOf('<dialog class="site-dialog event-dialog"'),
      indexSource.indexOf('<dialog class="site-dialog swpc-dialog"'));
    expect(dialog).toContain('id="event-dialog"');
    expect(dialog).toContain('id="event-player"');
    // The one thing that must never be added. Every other dialog on this site
    // wraps its body in <form method="dialog">; this one carries a Play button
    // and a range input, and inside such a form a default-type button submits
    // and Enter on the slider submits — either would close the replay the
    // reader had just started.
    expect(dialog, "a dialog form would let Play close the replay")
      .not.toContain('<form method="dialog">');
  });

});

/*
 * WHAT EACH CARD SAYS IT HOLDS.
 *
 * Sean, same message: "some don't have any media." Two events had none —
 * `observedImageryBlock` returned "" for `bastille-2000` and `stpatricks-2015`
 * — and, worse than the missing clip, the card gave the reader no way to know
 * before opening it. This page's standing rule is that an event without a
 * picture says so in words, and the rule has to hold on the card too.
 */
describe("the media line on a card", () => {
  const line = (id: string, replay: unknown) =>
    eventMediaLine({ id, replay } as never);

  it("names both kinds when an event holds both", () => {
    expect(line("gannon-2024", { kind: "thermosphere-inflation" }))
      .toBe("Holds: a measured chart on a real UTC clock and 2 clips of instrument footage.");
  });

  it("says outright when there is no footage", () => {
    expect(eventObservedClipCount("quebec-1989")).toBe(0);
    expect(line("quebec-1989", { kind: "gic-chain" })).toContain("No footage of the Sun is published");
  });

  it("says outright when there is no chart, which is the withheld case", () => {
    // While REPLAY_WITHHOLDS holds stpatricks-2015 back, a live visitor's
    // bundle has no `replay` for it. The card must say that rather than
    // promise a chart the page will not draw, and must flip back on its own
    // when the withhold is lifted.
    expect(line("stpatricks-2015", undefined))
      .toBe("Holds: one clip of instrument footage. No measured chart is published for it yet.");
  });

  it("never presents an empty frame for an event holding nothing", () => {
    expect(line("no-such-event", undefined)).toContain("No measured chart and no footage");
  });

  it("gives every event on the page a line", () => {
    for (const event of bundle.events) {
      expect(line(event.id, event.replay).length, `${event.id} has no media line`)
        .toBeGreaterThan(20);
    }
  });

  it("counts only instrument footage, never a generated illustration", () => {
    // starlink-2022 carries one observed clip and one badged illustration. The
    // card must not offer the illustration as evidence about the event.
    const clips = EVENT_MEDIA["starlink-2022"]?.clips ?? [];
    expect(clips.some((clip) => clip.evidence === "illustration")).toBe(true);
    expect(eventObservedClipCount("starlink-2022")).toBe(1);
  });
});

/**
 * No event picture carries a voice player, and none of the renders were thrown away.
 *
 * Sean, 2026-08-26, on St Patrick's: "there is only one video that has my voice and it is
 * weird. It is a video you can play by itself and a short audio file where I talk... It is
 * oddly placed." Then Bastille Day, then Halloween, then the rule: "basically all the audio
 * with my voice except the quebec blackout are like 10 second audio clips that sort of are
 * weirdly placed."
 *
 * A single 9-14 s render bolted ALONGSIDE a silent video has no relationship to that clip's
 * timeline. The Quebec mechanism clip is the pattern that works and the reason this is a
 * presentation defect rather than a narration one: its lines are timed against the
 * animation's own clock and muxed into the picture.
 */
describe("the voice on the event pictures", () => {
  it("puts no standalone player beside a silent clip", () => {
    for (const [id, media] of Object.entries(EVENT_MEDIA)) {
      for (const clip of media.clips) {
        expect(Object.keys(clip), `${id}/${clip.stem} has a narration stem again`)
          .not.toContain("narration");
      }
    }
    // and the renderer has no way to emit one, so it cannot come back by data alone
    expect(imagerySource).not.toContain("narrationBlock(clip.narration)");
  });

  it("leaves the Quebec absence line alone, because it stands beside no picture", () => {
    // There is no footage of the 1989 storm -- that absence IS the teaching point -- so this
    // voice is not out of step with anything. Sean named the Quebec blackout as the one that
    // works, and it was left exactly as it was.
    expect(EVENT_MEDIA["quebec-1989"]?.absence?.narration).toBe("quebec-1989-no-imagery");
    expect(imagerySource).toContain("narrationBlock(absence.narration)");
  });

  it("still has every render on disk, and every word still written down", () => {
    // These are paid ElevenLabs renders in Sean's cloned voice, loudness-matched, and a
    // future TIMED treatment wants them. Deleting them to tidy up costs money to undo.
    const ids = (narrationManifest.lines as Array<{ id: string; text: string }>).map((l) => l.id);
    expect(ids.length).toBeGreaterThanOrEqual(8);
    for (const id of ids) {
      const mp3 = fileURLToPath(new URL(`../media/narration/${id}.mp3`, import.meta.url));
      expect(existsSync(mp3), `${id}.mp3 was deleted; it is a paid render`).toBe(true);
    }
  });

  it("keeps on the page the three facts that lived only in a transcript", () => {
    // Everything else those lines said is printed elsewhere on the page. These three were
    // not, and they went into the caption under the picture rather than out with the player.
    const gannon = EVENT_MEDIA["gannon-2024"]!.clips;
    expect(gannon[0]!.caption).toMatch(/hundred and fifty million kilometres/);
    expect(gannon[0]!.caption).toMatch(/thousand kilometres a second/);
    expect(gannon[1]!.caption).toMatch(/fifteen\s+Earth diameters/);
    expect(EVENT_MEDIA["halloween-2003"]!.clips[0]!.caption).toMatch(/two-year design life/);
  });
});
