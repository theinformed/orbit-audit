// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import fixture from "./fixtures/orbit-history-live.json";
import { mountOrbitHistoryBrowser } from "../src/orbit-history-browser";
import {
  ARCHIVE_OFFLINE,
  type OrbitEventsBundle,
  type OrbitHistoryShard,
  type OrbitShardResult,
} from "../src/orbit-history";

/**
 * THE DOM TEST `docs/orbit-browser-wiring.md` §3 SAYS IS MISSING, AND WHY IT
 * COULD NOT BE WRITTEN AGAINST THE TYPES.
 *
 * Wiring this module into the page on 2026-08-09 produced, in that document's
 * words, "a browser that loaded, rendered and lied". Four names the browser
 * dereferenced were not the names the pipeline publishes:
 *
 *   1. `maturity.observationSpanDays` — the artifact carries
 *      `longestSingleObjectDays`. The status tile read "Archive watching for
 *      —", and the `undefined` went on to seed a `Math.max` inside
 *      `selectPopulation`, so `longestObserved` was `NaN`, every
 *      `NaN < requirement` was false, and THE MATURITY GATE SWITCHED ITSELF
 *      OFF. Silently, and in the direction of answering questions the archive
 *      could not answer.
 *   2. `groundTruth.inArchiveWindow` — the artifact carries `scorable`.
 *   3. `bundle.events` is not `OrbitEventRecord[]`; `_slim()` strips `card`,
 *      `deltaV`, `drag`, `spaceWeather`, `expectation` and `tests`, so the
 *      no-shard fallback would have thrown inside the dialog.
 *   4. `shardCount` was read off the bundle, which has never carried one.
 *
 * The document names the reason all four survived: there was no DOM test over
 * this module, only `tests/orbit-history.test.ts` over the data layer beneath
 * it. A test written against `src/orbit-history.ts`'s interfaces could not have
 * caught any of them, because the interfaces were the thing that was wrong —
 * TypeScript checks the browser against the DECLARATION, and every one of the
 * four was a declaration that no artifact matched.
 *
 * So the fixture is not written to the types. `tests/fixtures/
 * orbit-history-live.json` is trimmed out of the artifacts
 * `sean.theinformed.org/space` was actually serving on 2026-09-03 — real key
 * names, real values, six real objects — and the assertions below are that the
 * rendered PAGE carries the published numbers. Rename a field in the pipeline
 * without renaming it here and these fail; declare a field the pipeline does
 * not publish and the `undefined`/`NaN` sweep at the bottom fails.
 */

const LIVE_SHARD = fixture.shard as unknown as OrbitHistoryShard;
const LIVE_BUNDLE = fixture.bundle as unknown as OrbitEventsBundle;

/** The six objects the fixture holds, and the branch each one covers. */
const DECAYING_WITH_BOUND = 46080; // STARLINK-1568, -20.64 m/day, 12,591.6 d
const RISING = 61696; // STARLINK-11341, +5.19 m/day
const FALLING_AT_GEO = 44800; // TIBA-1, -138.74 m/day at 35,775.6 km perigee
const NO_CLUSTERS = 63488; // POSAT 2, decaying, no repeating correction
const NO_EVENTS = 67584; // STARLINK-36419, decaying, nothing detected yet
const OLD_MARKER_SHARD = 40960; // LINGQIAO VIDEO B, pre-2026-08-09 shard shape

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

interface MountOptions {
  bundle?: OrbitEventsBundle;
  shard?: OrbitShardResult;
  shardCount?: number | undefined;
  passShardCount?: boolean;
}

/**
 * Mount the real module against the real fixture and wait for the shard fetch.
 *
 * `select()` returns void and starts an async fetch, exactly as it does in the
 * page, so the wait is for the DOM rather than for a promise the caller does
 * not hold.
 */
async function open(norad: number, options: MountOptions = {}) {
  const host = document.createElement("div");
  document.body.replaceChildren(host);
  const shard = options.shard === undefined ? clone(LIVE_SHARD) : options.shard;
  const handle = mountOrbitHistoryBrowser(host, {
    bundle: options.bundle ?? clone(LIVE_BUNDLE),
    ...(options.passShardCount === false ? {} : { shardCount: options.shardCount ?? LIVE_SHARD.shardCount }),
    loadShard: async (index) => (index === LIVE_SHARD.shard ? shard : null),
  });
  handle.select(norad);
  await settle();
  return { host, handle, detail: host.querySelector<HTMLElement>(".orbit-history__detail")! };
}

async function settle(): Promise<void> {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    if (!document.body.textContent?.includes("Loading history…")) return;
  }
}

function text(node: Element | null | undefined): string {
  return (node?.textContent ?? "").replace(/\s+/g, " ").trim();
}

describe("the decay trend, drawn on the page", () => {
  /**
   * The published figures for STARLINK-1568, read off the artifact:
   * `metresPerDay: -20.64`, `perigeeAltitudeKm: 379.8`,
   * `upperBoundDaysToReentry: 12591.6`. Every one of them has to appear, in the
   * unit the block promises, or the block is reading a name that is not there.
   */
  it("prints the object's own median rate, perigee and upper bound", async () => {
    const { detail } = await open(DECAYING_WITH_BOUND);
    const block = detail.querySelector(".orbit-history__decay");
    expect(block).not.toBeNull();
    const body = text(block);
    expect(body).toContain("Where this orbit is going");
    expect(body).toContain("coming down");
    expect(body).toContain("-20.6 m");
    expect(body).toContain("380 km");
    // 12,591.6 days is 34.5 years. The page used to print the days verbatim,
    // which reads as a forecast to the tenth of a day and is not one.
    expect(body).toContain("Altitude left, at most");
    expect(body).toContain("34 years");
    expect(body).not.toContain("12591.6");
    // The module's own caveat travels with the number it qualifies.
    expect(body).toContain("UPPER bound");
  });

  /**
   * A rising median was rendered as silence before this block existed: the old
   * panel was gated on `decaying`, which requires a NEGATIVE median. Drag only
   * ever removes energy, so an orbit whose median rate is upward is the more
   * interesting of the two and it was the one that showed nothing.
   */
  it("says an orbit is gaining semi-major axis, and does not call that decay", async () => {
    const { detail } = await open(RISING);
    const body = text(detail.querySelector(".orbit-history__decay"));
    expect(body).toContain("gaining semi-major axis");
    expect(body).toContain("+5.2 m");
    expect(body).not.toContain("coming down");
    // No remaining-life figure: `decay_trend` offers one only on a falling
    // orbit below 600 km, and the page never manufactures one.
    expect(body).not.toContain("Altitude left");
  });

  /**
   * TIBA-1 loses 138.74 m of semi-major axis a day and is not decaying: its
   * perigee is 35,775.6 km, where drag is not the dominant term. Publishing the
   * rate without the altitude that disqualifies it would read as a re-entry
   * warning on a geostationary satellite.
   */
  it("separates falling from decaying, and names the altitude that separates them", async () => {
    const { detail } = await open(FALLING_AT_GEO);
    const body = text(detail.querySelector(".orbit-history__decay"));
    expect(body).toContain("NOT being called decay");
    expect(body).toContain("35776 km");
    expect(body).toContain("-138.7 m");
    expect(body).not.toContain("Altitude left");
  });

  /**
   * "We could not measure it" is not a finding about the orbit. `decay_trend`
   * returns `metresPerDay: null` when no interval was long enough to form a
   * rate, and the block draws nothing rather than drawing a zero.
   */
  it("draws nothing when the object has no measured rate", async () => {
    const unmeasured = clone(LIVE_BUNDLE);
    for (const row of unmeasured.objects) {
      row.decay = { metresPerDay: null, note: "no usable intervals" };
    }
    const { detail } = await open(DECAYING_WITH_BOUND, { bundle: unmeasured });
    expect(detail.querySelector(".orbit-history__decay")).toBeNull();
    expect(text(detail)).not.toContain("Where this orbit is going");
  });

  it("draws nothing when the bundle carries no decay key at all", async () => {
    const older = clone(LIVE_BUNDLE);
    for (const row of older.objects) delete row.decay;
    const { detail } = await open(DECAYING_WITH_BOUND, { bundle: older });
    expect(detail.querySelector(".orbit-history__decay")).toBeNull();
  });

  /**
   * The trend comes from the events bundle, not from the history shard, so it
   * survives the failure that took every plot off the site on 2026-08-27 — when
   * all 256 shards 404ed while the bundle beside them was fine. A block that
   * needs no shard must not disappear with one.
   */
  it("still answers 'where is this going' when the shard cannot be fetched", async () => {
    const { detail } = await open(DECAYING_WITH_BOUND, { shard: null });
    expect(detail.querySelector(".orbit-history__decay")).not.toBeNull();
    expect(text(detail)).toContain("could not be loaded");
  });

  it("still answers it when the archive machine is offline", async () => {
    const { detail } = await open(DECAYING_WITH_BOUND, { shard: ARCHIVE_OFFLINE });
    expect(detail.querySelector(".orbit-history__decay")).not.toBeNull();
  });
});

describe("the repeating corrections, drawn on the page", () => {
  /**
   * `repeatClusters` is ABSENT when no cadence was found and never empty —
   * "does not repeat itself" and "we did not look" are different statements —
   * so the two cases below are the whole contract for this block.
   */
  it("renders the cluster block from the shard's own repeatClusters", async () => {
    const { detail } = await open(DECAYING_WITH_BOUND);
    const block = detail.querySelector(".orbit-history__clusters");
    expect(block).not.toBeNull();
    const body = text(block);
    expect(body).toContain("Corrections this object repeats");
    expect(body).toContain("Each one costs");
    expect(body).toContain("Repeats every");
    // The cluster count on the card is the published `count`, not the number
    // of events the shard happens to carry.
    const cluster = (LIVE_SHARD.objects.find((entry) => entry.norad === DECAYING_WITH_BOUND)
      ?.repeatClusters ?? [])[0];
    expect(cluster).toBeDefined();
    expect(body).toContain(`${cluster!.count} ×`);
    // Still stops short of naming a cause.
    expect(body).not.toContain("station-keeping");
  });

  it("renders no cluster block when the key is absent, and still renders the decay block", async () => {
    const { detail } = await open(NO_CLUSTERS);
    expect(detail.querySelector(".orbit-history__clusters")).toBeNull();
    expect(text(detail)).not.toContain("Corrections this object repeats");
    // The two blocks are independent: one missing must not take the other with
    // it, which is the failure mode a single combined "insights" section has.
    expect(detail.querySelector(".orbit-history__decay")).not.toBeNull();
  });

  it("renders no cluster block on a shard published before the key existed", async () => {
    const { detail } = await open(OLD_MARKER_SHARD);
    expect(detail.querySelector(".orbit-history__clusters")).toBeNull();
    expect(detail.querySelector(".orbit-history__decay")).not.toBeNull();
  });
});

/**
 * THE DEFECT CLASS THIS FILE EXISTS FOR.
 *
 * Every one of the four 2026-08-09 mismatches rendered rather than threw. That
 * is what made them survive: `undefined` prints as "undefined" or vanishes into
 * a template, and `NaN` compares false against every bound it is tested
 * against, so the page went on looking finished while the maturity gate was
 * open and the ground-truth tile read "none in window" forever.
 *
 * A page that has printed `undefined`, `NaN`, `null` or `[object Object]` at a
 * reader is a page that has already lied, whatever else is on it. The sweep
 * below is therefore over the WHOLE rendered subtree rather than over a field
 * anyone thought to check, and it is run against the live fixture with each of
 * the four historic holes reopened one at a time.
 */
describe("a name the bundle does not carry fails loudly", () => {
  // NO WORD BOUNDARIES, and that is not laziness.
  //
  // `textContent` concatenates sibling nodes with nothing between them, so a
  // dt/dd pair renders as "Perigee nowundefined km" -- and `\bundefined\b`
  // does not match that, because the character before the u is a w. Written
  // with boundaries, this sweep sat green through a deliberately planted
  // `decay.perigeeKm` that put "undefined" on the page, which is exactly the
  // failure it exists to catch. Verified by putting it back.
  const FORBIDDEN = /NaN|undefined|\[object Object\]|Infinity/;

  async function render(mutate: (bundle: OrbitEventsBundle) => void, options: MountOptions = {}) {
    const bundle = clone(LIVE_BUNDLE);
    mutate(bundle);
    return open(DECAYING_WITH_BOUND, { ...options, bundle });
  }

  it("prints no NaN or undefined anywhere on an intact live bundle", async () => {
    for (const norad of [DECAYING_WITH_BOUND, RISING, FALLING_AT_GEO, NO_CLUSTERS, NO_EVENTS, OLD_MARKER_SHARD]) {
      const { host } = await open(norad);
      expect(text(host), `object ${norad}`).not.toMatch(FORBIDDEN);
    }
  });

  /**
   * MISMATCH 1, AND THE ONLY ASSERTION IN THIS FILE THAT CATCHES IT.
   *
   * The `undefined`/`NaN` sweep does NOT catch this one, and that is worth
   * saying rather than hiding: reintroducing the bug — reading
   * `observationSpanDays`, and dropping the finite check on the `Math.max`
   * seed — leaves the sweep green, because `formatDays` guards its own input
   * and renders "—", and because `haveDays` is only printed on a view that has
   * already decided it is unavailable. The damage was never a visible
   * `undefined`. It was a `NaN` that compared false against a bound, opened a
   * gate, and left a finished-looking page behind it.
   *
   * So this asserts the number itself. The status tile must carry the figure
   * the artifact publishes under the name the artifact publishes it under:
   * `longestSingleObjectDays`, 15,317.07 days in this release. Read
   * `observationSpanDays` instead — a name no published bundle has ever had —
   * and the tile reads "—" and this fails.
   */
  it("reads the maturity figure under the name the artifact publishes it under", async () => {
    const { host } = await open(DECAYING_WITH_BOUND);
    const published = (LIVE_BUNDLE.maturity as unknown as { longestSingleObjectDays?: number })
      .longestSingleObjectDays;
    expect(typeof published).toBe("number");
    const body = text(host);
    expect(body).toContain("Longest object watched for");
    expect(body).toContain(`${Number(published).toFixed(1)} days`);
  });

  /**
   * And the gate itself, driven the way the defect drove it.
   *
   * A young archive on a view that needs 21 days must say which day it starts
   * working, not render a table. Under the 2026-08-09 wiring it rendered the
   * table: the seed was `undefined`, `Math.max(undefined, n)` is `NaN`,
   * `NaN < 21` is false, and the gate was gone. Both halves of the fix are
   * under this — the name, and the finite check on the seed — because with the
   * name restored and the check removed, deleting the key puts `NaN` straight
   * back into the reduce.
   */
  async function clickView(host: HTMLElement, label: string): Promise<void> {
    const button = [...host.querySelectorAll("button")]
      .find((candidate) => candidate.textContent === label);
    expect(button, `no view button labelled ${label}`).toBeDefined();
    button!.click();
    await settle();
  }

  it("keeps the 21-day gate SHUT on a young archive, rather than silently opening it", async () => {
    const young = clone(LIVE_BUNDLE);
    (young.maturity as unknown as Record<string, number>).longestSingleObjectDays = 3;
    for (const row of young.objects) row.observedDays = 3;
    const { host } = await open(DECAYING_WITH_BOUND, { bundle: young });
    await clickView(host, "Same correction repeatedly");
    expect(text(host)).toContain("Not enough archive yet for this question");
    expect(host.querySelectorAll("tbody tr").length).toBe(0);
    expect(text(host)).not.toMatch(FORBIDDEN);
  });

  it("keeps it shut when the maturity key is missing entirely", async () => {
    const young = clone(LIVE_BUNDLE);
    delete (young.maturity as unknown as Record<string, unknown>).longestSingleObjectDays;
    for (const row of young.objects) row.observedDays = 3;
    const { host } = await open(DECAYING_WITH_BOUND, { bundle: young });
    await clickView(host, "Same correction repeatedly");
    expect(text(host)).toContain("Not enough archive yet for this question");
    expect(host.querySelectorAll("tbody tr").length).toBe(0);
  });

  it("opens the gate on the archive as published, which has the days behind it", async () => {
    const { host } = await open(DECAYING_WITH_BOUND);
    await clickView(host, "Same correction repeatedly");
    expect(text(host)).not.toContain("Not enough archive yet for this question");
    expect(host.querySelectorAll("tbody tr").length).toBeGreaterThan(0);
  });

  /** Mismatch 2, reopened: the artifact's name is `scorable`, never `inArchiveWindow`. */
  it("survives groundTruth.scorable going missing", async () => {
    const { host } = await render((bundle) => {
      delete (bundle.groundTruth as Record<string, unknown>).scorable;
    });
    expect(text(host)).not.toMatch(FORBIDDEN);
    expect(text(host)).toContain("none in window");
  });

  /**
   * Mismatch 3, reopened, and the fixture holds the real thing rather than a
   * mutation: object 40960's shard events are cut back to the seven marker keys
   * a shard carried before 2026-08-09, so `full` is empty and the browser must
   * fall back to the bundle's `_slim()`ed headline list — a DIFFERENT shape,
   * whose events have no `card`, `deltaV`, `drag`, `spaceWeather`,
   * `expectation` or `tests`. Handing one of those to `renderEvidenceCard`
   * throws on `event.card.headline`.
   */
  it("renders the slimmed headline shape without reaching for the stripped fields", async () => {
    const { detail } = await open(OLD_MARKER_SHARD);
    const body = text(detail);
    expect(body).not.toMatch(FORBIDDEN);
    expect(detail.querySelectorAll(".orbit-history__card").length).toBeGreaterThan(0);
    // It renders the headline event's published Δv, which is on the slim shape.
    const headline = LIVE_BUNDLE.events.find((event) => event.norad === OLD_MARKER_SHARD);
    expect(headline).toBeDefined();
    expect(body).toContain(headline!.signatureLabel);
  });

  /** Mismatch 4, reopened: the bundle has never carried a shard count. */
  it("survives shardCount not being passed at all", async () => {
    const { host, detail } = await open(DECAYING_WITH_BOUND, { passShardCount: false });
    expect(text(host)).not.toMatch(FORBIDDEN);
    // 46080 % 256 === 0, so the 256 fallback still finds it — the point is that
    // the number is not read off a bundle that does not have one.
    expect(detail.querySelector(".orbit-history__decay")).not.toBeNull();
  });

  /**
   * And the general case: a field invented on the browser side, which is what
   * all four originally were. `decay.metresPerDay` renamed in the artifact must
   * take the block off the page, not put a hole in it.
   */
  it("drops the block rather than printing a hole when a decay field is renamed", async () => {
    const { host, detail } = await render((bundle) => {
      for (const row of bundle.objects) {
        const decay = row.decay as unknown as Record<string, unknown>;
        if (!decay) continue;
        decay.metresPerDayRenamed = decay.metresPerDay;
        delete decay.metresPerDay;
      }
    });
    expect(detail.querySelector(".orbit-history__decay")).toBeNull();
    expect(text(host)).not.toMatch(FORBIDDEN);
  });
});

/* ------------------------------------------------------------------------ */
/* mixedCalibration                                                          */
/* ------------------------------------------------------------------------ */

/**
 * TWO CALIBRATIONS OF ONE DETECTOR, IN ONE RELEASE — AND WHAT THE READER IS
 * OWED WHEN THAT HAPPENS.
 *
 * Two detectors run over the archive and they are calibrated separately.
 * `pipeline/orbit_release.py` measures each one's false-alarm rate against
 * objects that physically cannot manoeuvre, and publishes a lane-by-lane
 * verdict in `labelPolicy.byBasis`:
 *
 *   - `cohort` — an object judged against its neighbours at the same altitude
 *     and inclination over the same hours. The only control available for an
 *     object the archive has only just met.
 *   - `selfHistory` — an object judged against its own past, from the campaign
 *     scan. Deeper, and the one a cadence question needs.
 *
 * When those two bits DISAGREE the release is in the mixed state:
 * `_label_policy()` shuts the whole-bundle `manoeuvreLabelPermitted` bit
 * (an old consumer that reads only that bit must fail conservatively rather
 * than borrow the calibrated lane's permission for the other lane's events),
 * and permission travels per event instead, on `manoeuvreLabelPermitted`.
 * `src/orbit-history-browser.ts:480` calls this `mixedCalibration`.
 *
 * It matters to a reader because the published events then come from two
 * different calibrations, and results from one are NOT directly comparable
 * with results from the other: on the same page, one card's flag stands on a
 * false-alarm bound inside the design target and the next card's does not.
 *
 * `tests/fixtures/orbit-history-live.json` was trimmed from artifacts published
 * BEFORE the detector gained the second lane — its `labelPolicy` carries no
 * `byBasis` at all — so `mixedCalibration` was dead on every branch here and
 * this whole state had zero render coverage. The `mixedCalibration` case in the
 * fixture closes that: its controls, its policy sentences and every one of its
 * evidence cards were generated by the publisher's own functions
 * (`orbit_events.control_rates`, `orbit_campaigns.control_rates_by_object`,
 * `orbit_release._label_policy` / `._controls_for` / `._control_basis` /
 * `._event_label_permitted` / `._slim`, `orbit_narrative.describe`), so it is
 * what a release in this state would actually serve rather than a shape
 * invented here.
 */

const MIXED_BUNDLE = fixture.mixedCalibration.bundle as unknown as OrbitEventsBundle;
const MIXED_SHARD = fixture.mixedCalibration.shard as unknown as OrbitHistoryShard;

/** TIBA-1. Both its events tripped on the self-history lane, which IS calibrated. */
const SELF_HISTORY_LANE = 44800;
/** STARLINK-11341. Both its events tripped on the cohort lane, which is NOT. */
const COHORT_LANE = 61696;

async function openMixed(
  norad: number,
  bundle: OrbitEventsBundle = clone(MIXED_BUNDLE),
  shard: OrbitHistoryShard = clone(MIXED_SHARD),
) {
  const host = document.createElement("div");
  document.body.replaceChildren(host);
  const handle = mountOrbitHistoryBrowser(host, {
    bundle,
    shardCount: MIXED_SHARD.shardCount,
    loadShard: async (index) => (index === MIXED_SHARD.shard ? shard : null),
  });
  handle.select(norad);
  await settle();
  return {
    host,
    handle,
    status: host.querySelector<HTMLElement>(".orbit-history__status")!,
    detail: host.querySelector<HTMLElement>(".orbit-history__detail")!,
  };
}

/** The event records for one object, in the order the shard publishes them. */
function mixedRecords(norad: number) {
  const object = MIXED_SHARD.objects.find((entry) => entry.norad === norad);
  expect(object, `fixture has no shard object ${norad}`).toBeDefined();
  return (object!.events ?? []) as unknown as {
    signatureLabel: string;
    controlBasis?: string;
    manoeuvreLabelPermitted?: boolean;
    card: { headline: string; honesty: string };
  }[];
}

describe("mixedCalibration: two calibrations of one detector, in one release", () => {
  it("reads matched control on the card and keeps a failed stratum a candidate despite a pooled pass", async () => {
    const bundle = clone(MIXED_BUNDLE);
    bundle.labelPolicy.byBasis = {
      cohort: false, selfHistory: false,
      byStratum: { "pre-2013": { "800-1500": { manoeuvreLabelPermitted: false, gap: "not separated" } },
                   "2021+": { "800-1500": { manoeuvreLabelPermitted: true, gap: null } } },
    };
    const shard = clone(MIXED_SHARD);
    for (const object of shard.objects) {
      if (object.norad !== SELF_HISTORY_LANE) continue;
      for (const event of object.events ?? []) {
        event.controlStratum = { era: "pre-2013", band: "800-1500" };
        event.manoeuvreLabelPermitted = false;
      }
    }
    const { detail, status } = await openMixed(SELF_HISTORY_LANE, bundle, shard);
    expect(text(status)).toContain("Detector calibration depends on era and perigee band");
    const card = detail.querySelector(":scope > article.orbit-history__card")!;
    expect(text(card)).toContain("pre-2013 · 800-1500 km perigee");
    expect(text(card.querySelector(".orbit-history__wording"))).toContain("candidate");
  });

  /**
   * THE GUARD THAT KEEPS EVERY TEST BELOW FROM GOING QUIETLY VACUOUS.
   *
   * Every assertion under this heading is about a state the FIXTURE has to be
   * in. Regenerate the fixture from a release where both lanes agree and the
   * renders below would still pass their "no exception" halves while testing
   * nothing at all — which is the exact shape of the hole this file is closing.
   * So the state is asserted first, against the controls it was computed from.
   */
  it("the fixture is really in the mixed state, and the live bundle really is not", () => {
    const policy = MIXED_BUNDLE.labelPolicy;
    expect(policy.byBasis).toBeDefined();
    expect(policy.byBasis!.cohort).toBe(false);
    expect(policy.byBasis!.selfHistory).toBe(true);
    // The lane bits agree with the controls the publisher derived them from.
    expect(MIXED_BUNDLE.controls.sufficientToLabel).toBe(false);
    expect(MIXED_BUNDLE.controls.selfHistory).toBeDefined();
    expect(MIXED_BUNDLE.controls.selfHistory!.sufficientToLabel).toBe(true);
    // And the whole-bundle compatibility bit stays SHUT, because one lane failed.
    expect(policy.manoeuvreLabelPermitted).toBe(false);
    // The two lanes were calibrated at different kappa: that is the recalibration.
    expect(MIXED_BUNDLE.controls.selfHistory!.kappa).not.toBe(MIXED_BUNDLE.controls.kappa);
    // The hole itself: the live bundle predates the second lane entirely.
    expect(LIVE_BUNDLE.labelPolicy.byBasis).toBeUndefined();
  });

  it("says so in the status heading, instead of reporting one calibration for the release", async () => {
    const { status } = await openMixed(SELF_HISTORY_LANE);
    const heading = status.querySelector("h3");
    expect(heading).not.toBeNull();
    expect(text(heading)).toBe("Detector calibration is lane-specific");
  });

  /**
   * The heading alone is a label, not an explanation. The reader also has to be
   * told WHICH lane earned the word, which one did not, and why not — otherwise
   * "lane-specific" is a phrase they cannot act on.
   */
  it("names the calibrated lane, the uncalibrated one, and the reason it failed", async () => {
    const { status } = await openMixed(SELF_HISTORY_LANE);
    const body = text(status);
    expect(body).toContain("The self-history detector is calibrated");
    expect(body).toContain("Events judged only by the cohort detector remain candidates");
    // The cohort lane's own blocking reason, quoted rather than paraphrased.
    expect(MIXED_BUNDLE.controls.blockingReason).not.toBeNull();
    expect(body).toContain(MIXED_BUNDLE.controls.blockingReason!);
    expect(body).toContain("not below the design target");
  });

  /**
   * And the wording line has to tell the reader that permission is per
   * DETECTOR, not per release — the sentence that makes a plain card and a
   * "(candidate)" card on the same page intelligible rather than inconsistent.
   */
  it("tells the reader the manoeuvre word is earned per detector", async () => {
    const { status } = await openMixed(SELF_HISTORY_LANE);
    expect(text(status)).toContain(
      "An event is called a manoeuvre only when the passive control for the detector that judged it",
    );
  });

  /**
   * Both calibrations' false-alarm counts, on the page, side by side. This is
   * the only place a reader can see that the two lanes are measured on
   * different amounts of evidence — 63 flags in 24,318 intervals against
   * 41,206 in 89,017,283 — and therefore why one of them earned the word.
   *
   * Concatenated without a separator on purpose: `appendNumber` puts the label
   * and the value in sibling nodes, so `textContent` runs them together, and an
   * assertion written with a space between them passes on a page that prints
   * neither.
   */
  it("publishes both lanes' passive controls, so the two calibrations can be compared", async () => {
    const { status } = await openMixed(SELF_HISTORY_LANE);
    const body = text(status);
    const cohort = MIXED_BUNDLE.controls.passiveControl;
    const self = MIXED_BUNDLE.controls.selfHistory!.passive;
    expect(body).toContain(
      `Cohort false alarms on objects that cannot manoeuvre${cohort.flags} / ${cohort.intervals}`,
    );
    expect(body).toContain(
      `Self-history false alarms on objects that cannot manoeuvre${self.flags} / ${self.intervals}`,
    );
    expect(body).not.toMatch(/NaN|undefined|\[object Object\]|Infinity/);
  });

  /**
   * The negative half. A heading that reads "lane-specific" whatever the bundle
   * says is not coverage of anything, so each of the three states is driven
   * through the real module and asserted to produce its own heading.
   */
  it("does not claim lane-specific calibration when the two lanes agree", async () => {
    const bothShut = await openMixed(SELF_HISTORY_LANE, clone(LIVE_BUNDLE));
    expect(text(bothShut.status.querySelector("h3"))).toBe(
      "Detector not yet calibrated — nothing here is called a manoeuvre",
    );

    const agreed = clone(MIXED_BUNDLE);
    agreed.labelPolicy.byBasis = { cohort: true, selfHistory: true };
    agreed.labelPolicy.manoeuvreLabelPermitted = true;
    const bothOpen = await openMixed(SELF_HISTORY_LANE, agreed);
    expect(text(bothOpen.status.querySelector("h3"))).toBe("Detector calibrated");
  });

  /** And the mirror image of the fixture's mix, so neither lane is privileged. */
  it("reports the mixed state whichever lane is the calibrated one", async () => {
    const mirrored = clone(MIXED_BUNDLE);
    mirrored.labelPolicy.byBasis = { cohort: true, selfHistory: false };
    const { status } = await openMixed(SELF_HISTORY_LANE, mirrored);
    expect(text(status.querySelector("h3"))).toBe("Detector calibration is lane-specific");
  });

  /**
   * WHAT THE MIXED STATE DOES TO THE EVENTS THEMSELVES.
   *
   * The whole-bundle bit is shut, so a browser that read only that bit would
   * mark every event on both objects a candidate — including the ones the
   * calibrated lane found, which have earned the word. Permission travels per
   * event instead, and the two objects below prove the browser reads it: the
   * same release, the same page, two different nouns.
   */
  it("keeps the calibrated lane's word on its own events", async () => {
    const records = mixedRecords(SELF_HISTORY_LANE);
    expect(records.length).toBeGreaterThan(0);
    expect(records.every((event) => event.controlBasis === "self-history")).toBe(true);
    expect(records.every((event) => event.manoeuvreLabelPermitted === true)).toBe(true);

    const { detail } = await openMixed(SELF_HISTORY_LANE);
    // ":scope > article" on purpose. Two other things wear
    // .orbit-history__card: the object header, which is a direct-child div, and
    // the repeat-cluster block's own cards, which are nested. Neither carries an
    // event kicker, so a looser selector returns cards whose kicker text is "" --
    // and "" contains no "(candidate)", so the assertion passes while testing
    // nothing. Verified by watching it do exactly that.
    const cards = [...detail.querySelectorAll(":scope > article.orbit-history__card")];
    expect(cards.length).toBe(records.length);
    const kickers = cards.map((card) => text(card.querySelector(".orbit-history__wording")));
    for (const kicker of kickers) {
      expect(kicker).not.toBe("");
      expect(kicker).not.toContain("(candidate)");
    }
    expect(text(detail)).toContain(records[0]!.signatureLabel);
  });

  it("withholds it from the uncalibrated lane's events, in the same release", async () => {
    const records = mixedRecords(COHORT_LANE);
    expect(records.length).toBeGreaterThan(0);
    expect(records.every((event) => event.controlBasis === "cohort")).toBe(true);
    expect(records.every((event) => event.manoeuvreLabelPermitted === false)).toBe(true);

    const { detail } = await openMixed(COHORT_LANE);
    const cards = [...detail.querySelectorAll(":scope > article.orbit-history__card")];
    expect(cards.length).toBe(records.length);
    const kickers = cards.map((card) => text(card.querySelector(".orbit-history__wording")));
    for (const kicker of kickers) {
      expect(kicker).toContain(`${records[0]!.signatureLabel} (candidate)`);
    }
  });

  /**
   * And each card quotes ITS OWN lane's false-alarm measurement rather than the
   * release's. Quoting the cohort's numbers under an event the self-history
   * detector found would be citing a measurement of a different instrument —
   * the quiet inconsistency `_controls_for()` exists to prevent — and it would
   * be invisible to every other assertion in this file.
   */
  it("quotes each event against the control that actually judged it", async () => {
    const selfCard = mixedRecords(SELF_HISTORY_LANE)[0]!;
    const cohortCard = mixedRecords(COHORT_LANE)[0]!;
    const self = MIXED_BUNDLE.controls.selfHistory!.passive;
    const cohort = MIXED_BUNDLE.controls.passiveControl;

    expect(selfCard.card.honesty).toContain(
      `flagged ${self.flags} intervals out of ${self.intervals}`,
    );
    expect(cohortCard.card.honesty).toContain(
      `flagged ${cohort.flags} intervals out of ${cohort.intervals}`,
    );
    // The calibrated lane's card says the word; the other one says candidate.
    expect(selfCard.card.honesty).toContain("This is a manoeuvre inferred from public elements");
    expect(cohortCard.card.honesty).toContain("This is a candidate");

    const onSelf = text((await openMixed(SELF_HISTORY_LANE)).detail);
    expect(onSelf).toContain(selfCard.card.honesty);
    expect(onSelf).not.toContain(`flagged ${cohort.flags} intervals out of ${cohort.intervals}`);

    const onCohort = text((await openMixed(COHORT_LANE)).detail);
    expect(onCohort).toContain(cohortCard.card.honesty);
    expect(onCohort).not.toContain(`flagged ${self.flags} intervals out of ${self.intervals}`);
  });

  /** The usual sweep, over the state that had never been rendered at all. */
  it("prints no NaN or undefined anywhere in the mixed state", async () => {
    for (const norad of [SELF_HISTORY_LANE, COHORT_LANE]) {
      const { host } = await openMixed(norad);
      expect(text(host), `object ${norad}`).not.toMatch(
        /NaN|undefined|\[object Object\]|Infinity/,
      );
    }
  });

  /**
   * OPEN GAP, DOCUMENTED RATHER THAN ASSERTED — NOT A TEST THAT IS ALLOWED TO
   * FAIL QUIETLY.
   *
   * `controlBasis` is published on every event record (`_HEADLINE_FIELDS` in
   * `pipeline/orbit_release.py` carries it onto the slimmed headline rows too)
   * and is declared three times in `src/orbit-history.ts`. Nothing in `src/`
   * ever reads it. Grep for it: the only hits are the type declarations and the
   * pipeline that writes it.
   *
   * So in the mixed state the reader gets the status heading above — the
   * release's calibration is lane-specific — and then two cards, one plainly
   * titled and one marked "(candidate)", with nothing on either card saying
   * which detector judged it. The false-alarm figures differ by four orders of
   * magnitude between the two cards and the page never says why. The one fact
   * that would join the heading to the cards is published, typed, and dropped.
   *
   * The card now names its lane and its matched stratum. Select an EVENT
   * article here: the object summary also carries the card CSS class.
   */
  it("names the detector lane on the card, so a reader can tell the two apart", async () => {
    const { detail } = await openMixed(COHORT_LANE);
    const card = detail.querySelector(":scope > article.orbit-history__card");
    expect(card).not.toBeNull();
    expect(text(card)).toMatch(/cohort|its own history|self-history/i);
  });
});
