// @vitest-environment jsdom
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { BUNDLE_DATE, BUNDLE_PATH, CH_VERDICT, GATE_AXIS, VERDICT_SAMPLE, VERDICT_SNAPSHOT, gateX } from "../src/orbit-verdict";
import { CHAPTERS, satelliteFundamentalsIndexView, satelliteFundamentalsPageView } from "../src/satellite-fundamentals";

// Offline, content-addressed input. This test never consults the current manifest,
// and it deliberately does not read public/data/artifacts/ either: that directory is
// rotated by deploy/prune_data.py, and the bundle chapter 08 first froze against was
// pruned out from under it -- taking this test (ENOENT) and the chapter's citation
// link (404) with it. An immutable input belongs in a committed fixture, so the
// bundle lives here gzipped, and its content address is verified below so the fixture
// itself cannot drift. The SITE citation still points at /data/artifacts/...: readers
// download the live copy, which deploy/prune_data.py now pins.
const BUNDLE_SHA256 = "f0aee9b89f1c200fdc040dd6a0f8bc851d5021b6b9e693b3003262f966fc1d42";
const bundleBytes = gunzipSync(readFileSync(resolve("tests/fixtures/orbit-verdict-bundle-f0aee9b89f1c200f.json.gz")));
const bundle = JSON.parse(bundleBytes.toString("utf8"));
const page = satelliteFundamentalsPageView("earning-the-word");
const document = new DOMParser().parseFromString(page, "text/html");
const figures = [...document.querySelectorAll<SVGSVGElement>("svg[data-verdict-figure]")];
const text = (html: string) => new DOMParser().parseFromString(html, "text/html").body.textContent!.trim();

/** Every field the chapter froze has to equal the bundle's, key for key.
 * The bundle is allowed to carry MORE than the chapter quotes -- the self-history
 * control blocks gained per-channel `breakdown` tables after the first freeze, and
 * a chapter that quoted counts and bounds has no business copying those -- so this
 * checks each frozen key against the bundle and refuses any key the bundle lacks,
 * which is the direction that would let an invented number through. */
function matchesBundle(frozen: Record<string, unknown>, source: Record<string, unknown>): void {
  expect(Object.keys(frozen).length).toBeGreaterThan(0);
  for (const key of Object.keys(frozen)) {
    expect(Object.keys(source), key).toContain(key);
    expect(frozen[key], key).toEqual(source[key]);
  }
}

describe("chapter 08 and its immutable drafted words", () => {
  it("registers the eighth chapter immediately after inference and connects both pagers", () => {
    // Chapter 09 added 2026-09-20; counts below moved 8 -> 9 deliberately.
    expect(CHAPTERS).toHaveLength(9);
    expect(CHAPTERS.map(c => c.index)).toEqual(["01", "02", "03", "04", "05", "06", "07", "08", "09"]);
    expect(CHAPTERS.at(-2)).toBe(CH_VERDICT);
    expect(CH_VERDICT.sections).toHaveLength(7);
    expect(satelliteFundamentalsIndexView()).toContain('data-fundamentals-page="earning-the-word"');
    expect(satelliteFundamentalsIndexView()).toContain("Nine chapters");
    expect(satelliteFundamentalsPageView("inference")).toContain('data-fundamentals-page="earning-the-word"');
    expect(document.querySelector('.fund-pager [data-fundamentals-page="inference"]')).not.toBeNull();
    expect(page).toContain("All nine chapters");
    expect(page).toContain("CHAPTER 08 OF 9");
  });

  it("keeps all 58 drafted paragraphs verbatim, including hedges and figure captions", () => {
    const prose = [CH_VERDICT.lead];
    for (const section of CH_VERDICT.sections) {
      if (section.lead) prose.push(section.lead);
      for (const block of section.blocks) {
        if (block.kind === "terms") for (const item of block.items) {
          prose.push(item.body);
          if (item.operational) prose.push(item.operational);
        }
        if (block.kind === "equation") prose.push(...block.where.map(row => row.meaning), ...block.worked ?? []);
        if (block.kind === "live") prose.push(...block.body);
        if (block.kind === "figure") prose.push(block.caption);
      }
    }
    expect(prose).toHaveLength(58);
    // SHA-256 of the sorted, emphasis-stripped > blocks in the authoritative design.
    // Sorting accommodates the design placing all figure captions after its sections.
    // Moved once, on 2026-09-12, when the chapter re-froze onto the bundle named by
    // BUNDLE_SHA256: the sentences that quote bundle counts carry the new counts. Every
    // sentence that quotes nothing from the bundle is still the draft, word for word.
    //
    // Moved again, deliberately, on 2026-09-21: the label-gate flip (self-history
    // separation cleared 10x on 2026-09-20; the bundle-wide bit is still false because
    // the cohort lane remains closed) made `lead`'s opening sentence -- "Every card...
    // says candidate" -- a present-tense false claim about the live browser, which now
    // shows most cards earning the word. The fix is a dated frame, not a rewrite: "says"
    // -> "said", plus "in the {BUNDLE_DATE} bundle -- most now earn the word instead",
    // consistent with how this same lead already dates its measured numbers two
    // sentences later. No bundle-quoted number changed, so nothing else in this hash
    // moved. This re-freeze is intentionally the only way to pass this test, per the
    // comment on the test's own name: it exists to force exactly this deliberateness.
    //
    // Moved a third time, deliberately, on 2026-09-21: a hostile physics review (F2)
    // established that "no single impulse can change a bound orbit by more than twice
    // its perigee speed" is false -- the true single-impulse ceiling is (1 + sqrt 2)
    // times perigee speed, about 2.414x, because what must stay below escape is the
    // FINAL speed, not the impulse. Twice perigee speed is a conservative SCREEN the
    // pipeline keeps deliberately inside that true ceiling (pipeline/orbit_events.py,
    // "THE PHYSICAL SCREEN, AND WHAT IT IS NOT", corrected the same day in aee7ed8).
    // "The ceiling" term's body is rewritten to say that truthfully -- the screen sits
    // safely inside the true ~2.4x ceiling -- while keeping its actual story unchanged:
    // the self-history lane once priced five events above the screen, and a bound
    // computed but not applied is a page that lies politely. No other frozen paragraph
    // changed, so nothing else in this hash moved.
    expect(createHash("sha256").update(prose.map(text).sort().join("\n")).digest("hex"))
      .toBe("b358f2e44bdc5c73122856097f3e3255ff3a5401d33c450a37857a56c570f83b");
  });

  it("keeps every rendered prose block within 100 words, including evidence notes", () => {
    const blocks = page.replace(/<svg[\s\S]*?<\/svg>/g, " ")
      .split(/<\/(?:p|dd|li|figcaption|h1|h2|span|strong)>|<span class="fund-operational">/)
      .map(part => text(part).replace(/\s+/g, " ")).filter(Boolean);
    for (const block of blocks) expect(block.split(" ").length, block).toBeLessThanOrEqual(100);
  });

  it("uses the real live controls and closes with sources and explorer navigation", () => {
    const markup = readFileSync(resolve("src/main.ts"), "utf8")
      + readFileSync(resolve("index.html"), "utf8");
    for (const em of document.querySelectorAll(".fund-live em")) expect(markup).toContain(em.textContent);
    expect(document.querySelector('[data-fundamentals-goto="explore"]')).not.toBeNull();
    expect(CH_VERDICT.sources).toHaveLength(8);
    expect(page).toContain(BUNDLE_PATH);
  });
});

describe("dated bundle provenance, never the cohort kappa masquerading as self-history", () => {
  const s = VERDICT_SNAPSHOT;
  it("reads the frozen bundle from a committed fixture at its published content address", () => {
    expect(createHash("sha256").update(bundleBytes).digest("hex")).toBe(BUNDLE_SHA256);
    // The page cites the same bundle by content address; the two must name one file.
    expect(BUNDLE_PATH).toBe(`/data/artifacts/orbit-events-${BUNDLE_SHA256.slice(0, 16)}.json`);
  });

  it("pins both lanes to their own exact inputs and label policy", () => {
    expect(s.generatedAt).toBe(bundle.generatedAt);
    expect(s.generatedAt).toBe("2026-09-12T08:52:41Z");
    expect(s.targetRate).toBe(bundle.controls.designTarget);
    expect(s.selfHistory.kappa).toBe(bundle.controls.selfHistory.kappa);
    expect(s.selfHistory.kappa).toBe(32);
    expect(s.cohort.kappa).toBe(bundle.controls.kappa);
    expect(s.cohort.kappa).toBe(8);
    expect(s.selfHistory.kappa).not.toBe(bundle.kappa);
    matchesBundle(s.selfHistory.passive, bundle.controls.selfHistory.passive);
    matchesBundle(s.selfHistory.payload, bundle.controls.selfHistory.payload);
    matchesBundle(s.cohort.passive, bundle.controls.passiveControl);
    matchesBundle(s.cohort.payload, bundle.controls.payloadPopulation);
    expect(s.selfHistory.permitted).toBe(bundle.labelPolicy.byBasis.selfHistory);
    expect(s.cohort.permitted).toBe(bundle.labelPolicy.byBasis.cohort);
    expect(page).toContain(BUNDLE_DATE);
  });

  it("recomputes the rates, bound ratios, safety margin and significance independently", () => {
    const sh = s.selfHistory, co = s.cohort;
    const passive = sh.passive.flags / sh.passive.intervals;
    const payload = sh.payload.flags / sh.payload.intervals;
    expect(passive).toBe(sh.passive.ratePerInterval);
    expect(payload).toBe(sh.payload.ratePerInterval);
    expect(payload / passive).toBeCloseTo(sh.pointRatio, 12);
    const pooled = (sh.passive.flags + sh.payload.flags) / (sh.passive.intervals + sh.payload.intervals);
    const z = (payload - passive) / Math.sqrt(pooled * (1 - pooled) * (1 / sh.passive.intervals + 1 / sh.payload.intervals));
    expect(z).toBeCloseTo(sh.z, 3);
    const boundRatio = sh.payload.jeffreys95[0] / sh.passive.jeffreys95[1];
    expect(boundRatio).toBeCloseTo(sh.boundRatio, 3);
    expect(co.payload.interval95[0] / co.passive.interval95[1]).toBeCloseTo(co.boundRatio, 3);
    for (const printed of [(passive * 1000).toFixed(2), (co.passive.flags / co.passive.intervals * 1000).toFixed(1),
      (sh.passive.jeffreys95[1] * 1000).toFixed(3), (sh.payload.jeffreys95[0] * 1000).toFixed(3),
      boundRatio.toFixed(2), (payload / passive).toFixed(1), (s.targetRate / sh.passive.jeffreys95[1]).toFixed(1)]) {
      expect(page).toContain(printed);
    }
    for (const lane of [
      { upper: sh.passive.jeffreys95[1], lower: sh.payload.jeffreys95[0], required: sh.requiredRatio, permitted: sh.permitted },
      { upper: co.passive.interval95[1], lower: co.payload.interval95[0], required: co.requiredRatio, permitted: co.permitted },
    ]) expect(lane.permitted).toBe(lane.upper < s.targetRate && lane.lower >= lane.required * lane.upper);
    expect(figures[2]!.textContent).toContain("(i) PASS · (ii) FAIL — 6.8 of 10");
    expect(figures[2]!.textContent).toContain("(i) FAIL · (ii) FAIL");
  });

  it("recounts the population, event lanes, eras and independent ground truth", () => {
    type Event = { startAt: string; controlBasis: string; objectType: string; expectationVerdict: string };
    const events = bundle.events as Event[];
    expect(s.objectsScanned).toBe(bundle.maturity.objectsScanned);
    expect(s.objectsWithBaseline).toBe(bundle.maturity.objectsWithBaseline);
    expect(s.eventsPublished).toBe(bundle.eventsPublished.total);
    expect(s.headlineEvents).toBe(events.length);
    const intervals = s.selfHistory.passive.intervals + s.selfHistory.payload.intervals;
    expect(page).toContain((intervals / 1e6).toFixed(1) + " M");
    expect(page).toContain((s.selfHistory.passive.intervals / 1e6).toFixed(1) + " M");
    expect(page).toContain((s.selfHistory.payload.intervals / 1e6).toFixed(1) + " M");
    for (const [basis, count] of Object.entries(s.headlineByBasis)) expect(count).toBe(events.filter(e => e.controlBasis === basis).length);
    const eraCounts = [0, 0, 0];
    for (const e of events) eraCounts[Number(e.startAt.slice(0, 4)) < 2013 ? 0 : Number(e.startAt.slice(0, 4)) < 2021 ? 1 : 2]! += 1;
    expect(s.headlineByEra).toEqual(eraCounts);
    expect(eraCounts.map(n => Math.round(n / events.length * 100))).toEqual([11, 20, 69]);
    expect(Math.round((eraCounts[1]! + eraCounts[2]!) / events.length * 100)).toBe(89);
    expect(events.filter(e => e.objectType !== "PAYLOAD")).toHaveLength(s.passiveHeadlineEvents);
    // "Impossible for class" is the blank showing its work, so it may only ever land on
    // an object the catalogue calls debris. A non-payload the catalogue cannot classify
    // gets no expectation at all rather than borrowing the debris verdict.
    const impossible = events.filter(e => e.expectationVerdict === "impossible-for-class");
    expect(impossible).toHaveLength(s.impossibleForClassEvents);
    expect(impossible.every(e => e.objectType === "DEBRIS")).toBe(true);
    expect(events.filter(e => e.objectType === "PAYLOAD").some(e => e.expectationVerdict === "impossible-for-class")).toBe(false);
    for (const [key, count] of Object.entries(s.groundTruth)) expect(count).toBe(bundle.groundTruth[key]);
    expect(s.groundTruth.detected + s.groundTruth.notDetected).toBe(s.groundTruth.scorable);
    expect(s.iss).toEqual(bundle.groundTruth.matches.find((m: { occurredAt: string }) => m.occurredAt === s.iss.occurredAt));
    expect(((1 - s.iss.detectedDeltaVMetresPerSecond / s.iss.publishedDeltaVMetresPerSecond) * 100).toFixed(1)).toBe("0.8");
  });
});

describe("figures: scaled geometry, declared evidence, no invented missing data", () => {
  it("renders exactly four labelled accessible schematics", () => {
    expect(figures).toHaveLength(4);
    for (const figure of figures) {
      expect(figure.getAttribute("role")).toBe("img");
      for (const id of figure.getAttribute("aria-labelledby")!.split(" ")) expect(document.getElementById(id)?.textContent!.length).toBeGreaterThan(10);
      expect(figure.closest("figure")!.textContent).toContain("SCHEMATIC");
      expect(figure.closest("figure")!.textContent).toContain("not yet in the published bundle");
      expect(figure.parentElement!.getAttribute("tabindex")).toBe("0");
      expect(figure.outerHTML).not.toMatch(/NaN|Infinity|undefined/);
    }
  });

  it("positions all C and D rates with a shared four-decade logarithmic scale", () => {
    expect(gateX(0.01)).toBe(GATE_AXIS.left);
    expect(gateX(100)).toBe(GATE_AXIS.right);
    const decadeWidth = (GATE_AXIS.right - GATE_AXIS.left) / 4;
    for (const figure of figures.slice(2)) for (const mark of figure.querySelectorAll("[data-rate]")) {
      const rate = Number(mark.getAttribute("data-rate"));
      const expected = GATE_AXIS.left + (Math.log10(rate) + 2) * decadeWidth;
      expect(Number(mark.querySelector("circle")!.getAttribute("cx"))).toBeCloseTo(expected, 10);
    }
    for (const value of [0.01, 0.1, 1, 10]) expect(gateX(value * 10) - gateX(value)).toBeCloseTo(decadeWidth, 10);
    const overflow = figures[2]!.querySelector('[data-off-scale="true"]')!;
    expect(Number(overflow.getAttribute("data-gate-target"))).toBeCloseTo(239.6, 8);
    expect(Number(overflow.querySelector("line")!.getAttribute("x2"))).toBe(GATE_AXIS.right);
    expect(figures[2]!.textContent).toContain("240 (off scale)");
  });

  it("recomputes every ladder ratio and labels the channel and persistence qualifier", () => {
    const fig = figures[2]!.textContent!;
    VERDICT_SAMPLE.kappa.forEach((_, i) => {
      const passive = VERDICT_SAMPLE.passivePerThousand[i]!, payload = VERDICT_SAMPLE.payloadPerThousand[i]!;
      expect(fig).toContain((payload / passive).toFixed(1) + "×");
      expect(fig).toContain(String(passive));
      expect(fig).toContain(String(payload));
    });
    expect(fig).toContain("Semi-major-axis channel, before the persistence test");
    expect(fig).toContain("1-in-25 debris / 1-in-75 payload");
  });

  it("shows unavailable era bounds as missing and discloses the source's ratio inconsistency", () => {
    expect(VERDICT_SAMPLE.eras.every(era => era.bounds === null)).toBe(true);
    expect(figures[3]!.textContent!.match(/95% bounds: missing/g)).toHaveLength(3);
    expect(figures[3]!.textContent).toContain("Sample verdicts, not released labels");
    // The ratios are NOT inconsistent with the point rates: they are
    // bound-to-bound (payload lower bound over passive upper bound), which is
    // necessarily smaller than the quotient of the point rates. The caption has
    // to say WHICH statistic it is showing, or a reader checking the arithmetic
    // concludes the page cannot do division.
    expect(figures[3]!.textContent).toContain("bound-to-bound");
    expect(figures[3]!.textContent).not.toContain("differ from the quotients");
    // Report, do not silently repair: the source ratios cannot be re-derived from these rates.
    expect(VERDICT_SAMPLE.eras.map(e => (e.payload / e.passive).toFixed(1))).toEqual(["1.7", "13.8", "92.8"]);
    expect(VERDICT_SAMPLE.eras.map(e => e.reportedRatio)).toEqual([1.7, 13.2, 86.7]);
    // A bound ratio can never exceed the point quotient. If it ever does, the
    // two numbers did not come from the same measurement.
    for (const era of VERDICT_SAMPLE.eras) {
      expect(era.reportedRatio).toBeLessThanOrEqual(era.payload / era.passive + 0.05);
    }
    expect(VERDICT_SAMPLE.eras[0].passive / VERDICT_SAMPLE.eras[2].passive).toBeCloseTo(18, 0);
    for (const [i, rect] of [...figures[3]!.querySelectorAll("[data-headline-count]")].entries()) {
      const count = VERDICT_SNAPSHOT.headlineByEra[i]!;
      expect(Number(rect.getAttribute("data-headline-count"))).toBe(count);
      expect(Number(rect.getAttribute("width"))).toBeCloseTo(count / 1031 * 150, 10);
    }
  });
});
