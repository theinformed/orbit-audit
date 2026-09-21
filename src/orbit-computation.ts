/**
 * Chapter 09 — how the numbers are made.
 *
 * The public, reader-safe telling of the computation story: the daily
 * stateless recount, exact-integer storage, the step-vs-drag statistics, why
 * the arithmetic runs on a graphics card and the zero-disagreement bar it had
 * to clear first, how a shared card is shared politely, and the drift
 * detector's three recorded failures before the fourth design earned a place.
 *
 * Every figure printed here is either imported from the same frozen bundle
 * snapshot chapter 08 pins (VERDICT_SNAPSHOT — single-sourced, test-frozen) or
 * computed in this module from stated constants so the test suite can
 * re-derive it independently (the series' standing rule: arithmetic on screen
 * must not be able to drift from the formula that produced it). Dated
 * measurements are labelled with their dates. No internal infrastructure is
 * named: ideas only.
 *
 * The two animated figures use CSS keyframes inside their own <svg><style>
 * blocks, gated behind (prefers-reduced-motion: no-preference): with motion
 * allowed the trace draws and the lanes run; with reduced motion the finished
 * static picture is shown, complete. That is the same contract the rest of
 * this site honours for motion it starts on its own.
 */
import type { Chapter } from "./satellite-fundamentals";
import { BUNDLE_DATE, BUNDLE_PATH, VERDICT_SNAPSHOT } from "./orbit-verdict";

// ---------------------------------------------------------------------------
// WORKED CONSTANTS — exported so the tests re-derive them independently.
// ---------------------------------------------------------------------------

/** WGS-72 gravitational parameter, km^3/s^2 — the value the catalogue's
 * propagator (SGP4, Spacetrack Report No. 3) is DEFINED against. Deliberately
 * not the WGS-84 value the rest of the series uses for its own geometry:
 * reproducing the catalogue's numbers means using the catalogue's constant. */
export const MU_WGS72 = 398600.8;
/** Mean Earth radius used for the altitude subtraction on the worked line. */
export const R_EARTH_KM = 6378.137;
/** The worked example's mean motion, revolutions per day, as printed. */
export const WORKED_MEAN_MOTION_REV_DAY = 15.44218077;

/** rev/day -> rad/s, then a = (mu / n^2)^(1/3). Exported for the test. */
export function semiMajorAxisKm(meanMotionRevPerDay: number): number {
  const n = meanMotionRevPerDay * 2 * Math.PI / 86400;
  return Math.cbrt(MU_WGS72 / (n * n));
}

const WORKED_A_KM = semiMajorAxisKm(WORKED_MEAN_MOTION_REV_DAY);
const WORKED_A_TEXT = WORKED_A_KM.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const WORKED_ALT_KM = WORKED_A_KM - R_EARTH_KM;

/** Archive scale, counted 12 September 2026 (the same day as the pinned
 * bundle). The object and event counts below come from the bundle itself. */
export const ARCHIVE_ROWS = 216_203_378;

/** The GPU acceptance record, 12 September 2026: both arithmetic paths run
 * side by side over real archive intervals; the required score was zero
 * disagreements, and the measured score was zero. */
export const GPU_ACCEPTANCE = {
  intervals: 1_074_766,
  comparisons: 4_278_167,
  disagreements: 0,
  analysisShare: 92.6,
  readShare: 7.4,
} as const;

/** The drift detector's record, told straight. Separations are payload rate
 * against debris rate — below 1.0 the detector is worse than useless, since
 * debris cannot manoeuvre. Measured on full-2024 runs, 12 September 2026. */
export const DRIFT_RECORD = {
  separations: [0.21, 0.16, 0.4],
  v1SignFast: 509, v1SignSlow: 46,
  v2SignFast: 79, v2SignSlow: 381,
  v4PassiveFlags: 0, v4PassiveObjects: 4107, v4Bound: 0.729,
  v4PayloadCatches: 56, v4Starlink: 51, v4Separation: 10.88,
} as const;

// ---------------------------------------------------------------------------
// FIGURES — same idiom as chapter 08: 900-wide viewBox, INK palette, labels.
// ---------------------------------------------------------------------------

const INK = { cyan: "#29d4e3", coral: "#ff7b78", amber: "#f5c96a", mint: "#76e6a5", muted: "#8da8b3", line: "rgba(132,194,214,.28)", faint: "rgba(132,194,214,.08)" } as const;
const esc = (value: string) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
function label(x: number, y: number, words: string, colour: string = INK.muted, anchor = "start", size = 11): string {
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" style="fill:${colour};font-size:${size}px">${esc(words)}</text>`;
}
function lines(x: number, y: number, words: string[], colour: string = INK.muted, size = 11): string {
  return words.map((row, i) => label(x, y + i * 17, row, colour, "start", size)).join("");
}
function line(x1: number, y1: number, x2: number, y2: number, colour: string = INK.line, width = 1, dash = ""): string {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${colour}" stroke-width="${width}"${dash ? ` stroke-dasharray="${dash}"` : ""}></line>`;
}
function box(x: number, y: number, w: number, h: number, stroke: string, fill = "none", rx = 6): string {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}"></rect>`;
}
function arrow(x1: number, y1: number, x2: number, y2: number, colour: string = INK.muted): string {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = (sign: number) => `${x2 - 9 * Math.cos(angle - sign * 0.42)},${y2 - 9 * Math.sin(angle - sign * 0.42)}`;
  return line(x1, y1, x2, y2, colour, 1.5) + `<polygon points="${x2},${y2} ${head(1)} ${head(-1)}" fill="${colour}"></polygon>`;
}
function svg(letter: string, height: number, title: string, description: string, body: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 ${height}" role="img" aria-labelledby="comp-${letter}-title comp-${letter}-desc" data-computation-figure="${letter}"><title id="comp-${letter}-title">${esc(title)}</title><desc id="comp-${letter}-desc">${esc(description)}</desc>${body}</svg>`;
}

/** A — the daily recount, end to end, with the discard loop that is the point. */
function figureA(): string {
  const stations: [number, string, string[]][] = [
    [30, "PUBLIC CATALOGUE", ["element sets,", "published hourly"]],
    [215, "EXACT INTEGERS", ["every printed digit", "stored losslessly"]],
    [400, "THE DAILY RECOUNT", ["every baseline, residual,", "flag: re-derived"]],
    [585, "THE BLANK CHECK", ["debris cannot manoeuvre;", "its flag rate is measured"]],
    [740, "THE PAGE", ["cards, controls,", "gated wording"]],
  ];
  let body = label(25, 28, "A · NOTHING SURVIVES THE NIGHT", INK.cyan, "start", 14)
    + label(25, 50, "the pipeline is a straight line forward and a deliberate loop back", INK.muted);
  stations.forEach(([x, name, note], i) => {
    body += box(x, 80, 130, 74, i === 2 ? INK.cyan : INK.line, i === 2 ? INK.faint : "none")
      + label(x + 65, 103, name, i === 2 ? INK.cyan : INK.muted, "middle", 11)
      + note.map((row, j) => label(x + 65, 122 + j * 15, row, INK.muted, "middle", 9)).join("");
    if (i < stations.length - 1) body += arrow(x + 132, 117, stations[i + 1]![0] - 4, 117, INK.muted);
  });
  body += label(465, 74, "arithmetic on a graphics card", INK.mint, "middle", 9)
    + `<path d="M 790 158 C 790 225, 120 225, 98 162" fill="none" stroke="${INK.coral}" stroke-width="1.5" stroke-dasharray="5 4"></path>`
    + `<polygon points="98,162 92,176 106,173" fill="${INK.coral}"></polygon>`
    + label(450, 213, "every derived conclusion is discarded — tomorrow starts from the records again", INK.coral, "middle", 11)
    + lines(25, 262, ["Same records in, same verdicts out, every day. A cached conclusion could rot silently; a recomputed one cannot.", "If the code improves, all of history is re-judged under the better code the next morning. No verdict is grandfathered."], INK.muted, 10);
  return svg("A", 292, "The daily recount", "Five stations: the public catalogue, exact integer storage, the daily recount running on a graphics card, the debris blank check, and the page. A dashed loop returns from the page to the integers: every derived conclusion is discarded and recomputed from the records each day.", body);
}

/** B — one printed decimal, stored exactly, becoming a point on an orbit. */
function figureB(): string {
  let body = label(25, 28, "B · THE CATALOGUE SPEAKS IN INTEGERS", INK.cyan, "start", 14)
    + label(25, 50, "one real mean motion, through storage and back, losing nothing", INK.muted)
    + box(40, 78, 240, 56, INK.line)
    + label(160, 100, "printed by the catalogue", INK.muted, "middle", 9)
    + label(160, 122, "15.44218077 rev/day", INK.cyan, "middle", 14)
    + arrow(284, 106, 342, 106)
    + label(313, 96, "×10⁸", INK.muted, "middle", 10)
    + box(346, 78, 240, 56, INK.line)
    + label(466, 100, "stored", INK.muted, "middle", 9)
    + label(466, 122, "1 544 218 077", INK.mint, "middle", 14)
    + arrow(590, 106, 648, 106)
    + label(619, 96, "a = (μ/n²)^⅓", INK.muted, "middle", 10)
    + box(652, 78, 220, 56, INK.line)
    + label(762, 100, "on the card", INK.muted, "middle", 9)
    + label(762, 122, `${WORKED_A_TEXT} km · ≈${Math.round(WORKED_ALT_KM)} km up`, INK.amber, "middle", 12)
    + lines(25, 176, [
      "Scales: mean motion 10⁻⁸ rev/day · eccentricity 10⁻⁸ · angles 10⁻⁴ ° · drag term 10⁻¹² per Earth radius · epoch 1 ms.",
      "Chosen so every value the catalogue can print is stored exactly. When two recounts disagree, it is physics or code — never storage.",
    ], INK.muted, 10);
  return svg("B", 206, "Exact integer storage", "A printed mean motion of 15.44218077 revolutions per day is multiplied by ten to the eighth into the integer 1544218077, stored losslessly, and later becomes a semi-major axis near 6,812 kilometres — about 434 kilometres of altitude — on the card.", body);
}

/** C — ANIMATED. Drag is a slope, a burn is a step, the median refuses to follow. */
function figureC(): string {
  // Geometry: time runs 90..860; altitude-ish axis 120..380. Pre-burn decay,
  // a +38 px step at x=470, then decay continues. The baseline (median over
  // +/-6 five-day blocks) holds its pre-burn line well past the step.
  const pre = "M 90 180 L 470 232";
  const post = "M 470 194 L 860 248";
  const style = `<style>
    @media (prefers-reduced-motion: no-preference) {
      [data-computation-figure="C"] .c9c-trace { stroke-dasharray: 990; stroke-dashoffset: 990; animation: c9cDraw 7s linear infinite; }
      [data-computation-figure="C"] .c9c-flag { animation: c9cPulse 7s linear infinite; }
      @keyframes c9cDraw { 0% { stroke-dashoffset: 990; } 62% { stroke-dashoffset: 0; } 100% { stroke-dashoffset: 0; } }
      @keyframes c9cPulse { 0%, 55% { opacity: 0; } 66%, 92% { opacity: 1; } 100% { opacity: 0; } }
    }
  </style>`;
  let body = style
    + label(25, 28, "C · DRAG IS A SLOPE. A BURN IS A STEP.", INK.cyan, "start", 14)
    + label(25, 50, "semi-major axis against time · the amber median is built to be stubborn", INK.muted)
    + line(90, 380, 860, 380) + line(90, 100, 90, 380)
    + label(875, 384, "time", INK.muted, "end", 10)
    + label(84, 96, "a", INK.muted, "end", 10)
    // kappa band around the baseline, drawn under everything
    + `<path d="M 90 168 L 470 220 L 860 274 L 860 246 L 470 192 L 90 140 Z" fill="${INK.faint}"></path>`
    + label(105, 136, "κ = 8 band: eight times the local noise scale (MAD × 1.4826)", INK.muted, "start", 9)
    // the stubborn median baseline: keeps the pre-burn line through the step
    + `<path d="M 90 154 L 500 210 L 620 196 L 860 229" fill="none" stroke="${INK.amber}" stroke-width="2" stroke-dasharray="7 5"></path>`
    + label(505, 232, "the median needs half its 13 blocks to move —", INK.amber, "start", 10)
    + label(505, 247, "a burn cannot drag its own baseline", INK.amber, "start", 10)
    // block medians: dots every ~30px on the trace's pre line
    + [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => `<circle cx="${100 + i * 31}" cy="${181.4 + i * 4.24}" r="2.5" fill="${INK.muted}"></circle>`).join("")
    + label(100, 205, "five-day block medians: a lone wild fit is outvoted", INK.muted, "start", 9)
    // the animated trace: pre-decay, step, post-decay
    + `<path class="c9c-trace" d="${pre} L 470 194 ${post.slice(2)}" fill="none" stroke="${INK.cyan}" stroke-width="2.5"></path>`
    + `<g class="c9c-flag">`
    + line(470, 165, 470, 240, INK.coral, 1.5, "3 3")
    + label(470, 158, "the step: minutes of thrust", INK.coral, "middle", 10)
    + line(556, 186, 556, 262, INK.mint, 1.5, "3 3")
    + label(560, 280, "still there two days later → believed", INK.mint, "start", 10)
    + `</g>`
    + lines(25, 416, [
      "The trace redraws; the amber median holds its ground through the step, so the residual against it grows past the κ band and flags.",
      "With reduced motion requested, the finished picture is simply shown. Scales are illustrative; the rules drawn are the real ones.",
    ], INK.muted, 10);
  return svg("C", 446, "The step and the stubborn median", "An animated trace of semi-major axis decays gently, steps upward in minutes, then decays again. Dots mark five-day block medians. An amber dashed baseline, the median over thirteen blocks, refuses to follow the step for weeks, so the residual crosses the kappa-equals-eight band and is flagged; a mint marker two days later shows persistence confirming it.", body);
}

/** D — ANIMATED. One worker in a queue versus thousands of lanes at once. */
function figureD(): string {
  const style = `<style>
    @media (prefers-reduced-motion: no-preference) {
      [data-computation-figure="D"] .c9d-cpu { animation: c9dLane 8s linear infinite; }
      [data-computation-figure="D"] .c9d-gpu { animation: c9dLane 1.1s linear infinite; }
      @keyframes c9dLane { 0% { transform: translateX(0); } 100% { transform: translateX(300px); } }
    }
  </style>`;
  let body = style
    + label(25, 28, "D · THE SAME ARITHMETIC, A DIFFERENT SHAPE", INK.cyan, "start", 14)
    + label(25, 50, "each dot is one object's interval checks — identical, tiny, independent", INK.muted)
    + label(70, 92, "ONE PROCESSOR CORE, IN TURN", INK.muted, "start", 11)
    + box(70, 104, 330, 44, INK.line)
    + `<g class="c9d-cpu"><circle cx="85" cy="126" r="6" fill="${INK.coral}"></circle></g>`
    + [0, 1, 2, 3, 4, 5, 6].map((i) => `<circle cx="${430 + i * 24}" cy="126" r="6" fill="none" stroke="${INK.coral}"></circle>`).join("")
    + label(430, 168, "the rest wait their turn — 89 million checks make a long queue", INK.muted, "start", 9)
    + label(70, 214, "A GRAPHICS CARD: THOUSANDS OF LANES AT ONCE", INK.mint, "start", 11);
  for (let laneIndex = 0; laneIndex < 6; laneIndex += 1) {
    const y = 228 + laneIndex * 26;
    body += box(70, y, 330, 18, INK.line, "none", 4)
      + `<g class="c9d-gpu"><circle cx="85" cy="${y + 9}" r="5" fill="${INK.mint}"></circle></g>`;
  }
  body += label(430, 258, "… and thousands more lanes below", INK.muted, "start", 9)
    + lines(430, 290, [
      `${GPU_ACCEPTANCE.analysisShare}% of the recount is this shape;`,
      `the branchy ${"0.26"}% that judges flagged`,
      "changes stays on an ordinary core.",
    ], INK.muted, 10)
    + lines(25, 416, [
      `Before the card was trusted, both versions ran side by side over ${GPU_ACCEPTANCE.intervals.toLocaleString("en-US")} real intervals — ${GPU_ACCEPTANCE.comparisons.toLocaleString("en-US")} comparisons.`,
      `Required score: zero disagreements. Measured score: ${GPU_ACCEPTANCE.disagreements}. The move was allowed only after that.`,
    ], INK.muted, 10);
  return svg("D", 446, "One lane versus thousands", "Animated: a single processor lane moves one dot slowly along a queue of waiting circles, while six graphics-card lanes move their dots simultaneously and far faster, standing in for thousands. Text records that 92.6 percent of the recount has this shape and that the card was trusted only after 4,278,167 side-by-side comparisons produced zero disagreements.", body);
}

/** E — sharing one card: residents keep their memory, guests ask and queue. */
function figureE(): string {
  let body = label(25, 28, "E · THE CARD IS SHARED, SO GUESTS ASK", INK.cyan, "start", 14)
    + box(70, 60, 760, 120, INK.line, "none", 10)
    + label(80, 52, "one graphics card's memory", INK.muted, "start", 10)
    + box(78, 68, 380, 104, INK.line, INK.faint)
    + label(268, 116, "RESIDENT MODELS", INK.cyan, "middle", 12)
    + label(268, 134, "their working memory is never touched", INK.muted, "middle", 9)
    + box(462, 68, 90, 104, INK.amber)
    + label(507, 116, "RESERVE", INK.amber, "middle", 10)
    + label(507, 134, "never granted", INK.amber, "middle", 8)
    + box(556, 68, 266, 104, INK.mint)
    + label(689, 100, "SPARE", INK.mint, "middle", 11)
    + box(572, 118, 110, 38, INK.mint, INK.faint) + label(627, 141, "recount ✓", INK.mint, "middle", 10)
    + arrow(760, 232, 720, 180, INK.muted)
    + box(690, 236, 120, 34, INK.line) + label(750, 257, "next job, queued", INK.muted, "middle", 9)
    + box(690, 278, 120, 34, INK.line) + label(750, 299, "and the next", INK.muted, "middle", 9)
    + lines(70, 232, [
      "Ask, wait, run, release: a guest states an honest size estimate and runs only when the spare region",
      "holds it. If the card is full, it queues — arrival order, with a promotion rule so nothing starves.",
      "A refused job says so out loud and stops. It never runs unqueued and never silently degrades.",
    ], INK.muted, 10);
  return svg("E", 322, "Sharing the card politely", "A graphics card's memory drawn as three regions: resident models whose working memory is never touched, an amber reserve never granted to guests, and a spare region where the daily recount runs. Two queued jobs wait outside with an arrow into the spare region. Text states the rule: ask, wait, run, release, and refusal is loud.", body);
}

/** F — the drift record: three inversions, the sign split, the survivor. */
function figureF(): string {
  const seps = DRIFT_RECORD.separations;
  const barY = (value: number) => 196 - Math.min(value, 1.2) / 1.2 * 96;
  let body = label(25, 28, "F · THREE FAILURES, TOLD STRAIGHT, THEN ONE SURVIVOR", INK.cyan, "start", 14)
    + label(25, 50, "separation = payload rate ÷ debris rate · debris cannot manoeuvre, so below 1.0 is worse than useless", INK.muted)
    + line(60, 196, 420, 196) + line(60, 100, 60, 196)
    + line(60, barY(1), 420, barY(1), INK.amber, 1, "5 4")
    + label(428, barY(1) + 4, "1.0 — the floor of usefulness", INK.amber, "start", 9);
  seps.forEach((separation, i) => {
    const x = 105 + i * 105;
    body += `<rect x="${x - 22}" y="${barY(separation)}" width="44" height="${196 - barY(separation)}" fill="${INK.coral}"></rect>`
      + label(x, 214, `v${i + 1}`, INK.muted, "middle", 10)
      + label(x, barY(separation) - 8, separation.toFixed(2) + "×", INK.coral, "middle", 10);
  });
  body += label(240, 246, "each design flagged debris MORE often than payloads — inverted, three times", INK.coral, "middle", 10)
    + label(60, 292, "THE SIGN SPLIT THAT EXPLAINED IT", INK.cyan, "start", 12)
    + lines(60, 314, [
      `v1's false alarms: ${DRIFT_RECORD.v1SignFast} of ${DRIFT_RECORD.v1SignFast + DRIFT_RECORD.v1SignSlow} were FASTER-than-expected decay — light debris genuinely out-falling its cohort.`,
      `v2's false alarms flipped: ${DRIFT_RECORD.v2SignSlow} of ${DRIFT_RECORD.v2SignFast + DRIFT_RECORD.v2SignSlow} were SLOWER-than-predicted — its drag stand-in importing its own error.`,
      "Both directions poisoned by a different cause. So the fourth design uses no drag model at all.",
    ], INK.muted, 10)
    + box(520, 100, 340, 178, INK.mint, INK.faint, 10)
    + label(690, 128, "V4 · THE SURVIVOR", INK.mint, "middle", 13)
    + lines(538, 154, [
      "Rule: below 800 km, near-circular, nothing",
      "without an engine climbs. Flag sustained",
      "RISING there. No drag model anywhere.",
      "",
      `debris: ${DRIFT_RECORD.v4PassiveFlags} flags on ${DRIFT_RECORD.v4PassiveObjects.toLocaleString("en-US")} objects (bound ${DRIFT_RECORD.v4Bound}/1,000)`,
      `payloads: ${DRIFT_RECORD.v4PayloadCatches} catches — ${DRIFT_RECORD.v4Starlink} from a fleet`,
      "documented to raise its own orbits",
    ], INK.muted, 10)
    + label(690, 296, `separation ${DRIFT_RECORD.v4Separation}× · full-2024 acceptance`, INK.mint, "middle", 11)
    + lines(25, 344, [
      "The failures are part of the method: the free debris control condemned each design before any reader ever saw it,",
      "and nothing was tuned to make a number look better. Counts from the acceptance runs, 12–20 September 2026.",
    ], INK.muted, 10);
  return svg("F", 374, "The drift detector's record", "Three coral bars below the amber usefulness floor show separations of 0.21, 0.16 and 0.40 for three failed drift-detector designs. Text gives the sign split that diagnosed them: 509 of 555 first-design false alarms were faster-than-expected decay, while the second design flipped to 381 of 460 slower-than-predicted. A mint panel describes the surviving fourth design — sustained rising below 800 kilometres — with zero flags on 4,107 debris objects and 56 payload catches, separation 10.88 times.", body);
}

// ---------------------------------------------------------------------------
// THE CHAPTER
// ---------------------------------------------------------------------------

export const CH_COMPUTATION: Chapter = {
  id: "how-the-numbers-are-made",
  index: "09",
  title: "Made from scratch, every day",
  door: `Where every number on every card comes from: ${ARCHIVE_ROWS.toLocaleString("en-US")} public records, re-judged from nothing each day by arithmetic that had to match the old answers ${GPU_ACCEPTANCE.comparisons.toLocaleString("en-US")} times — with zero disagreements — before it was trusted.`,
  covers: [
    "nothing is cached",
    "exact integers",
    "slope versus step",
    "why a graphics card",
    "zero disagreements",
    "polite queueing",
    "three failures, one survivor",
  ],
  lead: `Open any orbit-history card and every number on it was computed this morning, from the public record, from nothing. This chapter is the machinery: how ${ARCHIVE_ROWS.toLocaleString("en-US")} catalogue rows become one defensible sentence about one satellite — and why the arithmetic had to prove itself, answer for answer, before it was allowed to touch the page.`,
  sections: [
    {
      kicker: "THE HABIT",
      title: "Start over, every single day.",
      lead: `The archive holds ${ARCHIVE_ROWS.toLocaleString("en-US")} published element sets across ${VERDICT_SNAPSHOT.objectsScanned.toLocaleString("en-US")} objects, and it grows every hour. The tempting design is to analyse each new row once and remember the conclusions. This site does the opposite: every day, every conclusion is thrown away and recomputed from the raw records.`,
      blocks: [
        {
          kind: "terms",
          items: [
            { term: "Nothing accumulates", body: "A remembered conclusion can rot silently — a bug, a bad fit, a half-applied fix can live forever inside cached state, and nothing would ever error. A recomputed conclusion cannot: the same records in, the same verdicts out, every time. Statelessness here is not a performance choice. It is an honesty mechanism." },
            { term: "The daily recount", body: "One pass re-derives every baseline, every residual, every flag and every control count, then rebuilds the page's data wholesale. If the code improved yesterday, the whole of history is re-judged under the better code today. No verdict is grandfathered in." },
            { term: "What that costs", body: "Re-judging roughly ninety million interval comparisons a day is expensive — which is why the rest of this chapter exists. Exact integers make the recount repeatable to the bit; a graphics card makes it affordable; a queue keeps it polite.", note: "the plan of the chapter" },
          ],
        },
        {
          kind: "facts",
          items: [
            { value: ARCHIVE_ROWS.toLocaleString("en-US"), caption: "published element sets in the archive (12 September 2026)" },
            { value: VERDICT_SNAPSHOT.objectsScanned.toLocaleString("en-US"), caption: "objects scanned by the recount" },
            { value: VERDICT_SNAPSHOT.eventsPublished.toLocaleString("en-US"), caption: `events re-derived, ${BUNDLE_DATE} bundle` },
            { value: "0", caption: "conclusions carried over between runs" },
          ],
        },
        { kind: "figure", svg: figureA(), chip: "schematic", chipNote: "Schematic · the loop is the design, drawn; counts are the 12 September 2026 archive and bundle.", caption: "The pipeline is a straight line forward and a deliberate loop back. The loop is the honesty: everything derived is discarded, so nothing derived can quietly rot." },
      ],
    },
    {
      kicker: "EXACT NUMBERS",
      title: "The catalogue speaks in decimals; the archive answers in integers.",
      lead: "A catalogue row is a handful of printed decimals. The archive stores each one as an integer — mean motion in steps of 10⁻⁸ revolutions per day, angles in 10⁻⁴ degrees, epochs to the millisecond — scales chosen so that every value the catalogue can print is stored exactly, with nothing rounded away.",
      blocks: [
        {
          kind: "equation",
          name: "From a mean motion to a picture",
          tag: "the first derivation on every card",
          formula: "a = ( μ / n² )^⅓",
          where: [
            { symbol: "a", meaning: "semi-major axis — the size of the orbit, and the number drag and engines fight over" },
            { symbol: "μ", meaning: "398,600.8 km³/s² — the WGS-72 value the catalogue's propagator is defined against, kept deliberately (reproducing the catalogue's numbers means using the catalogue's constant, not the modern WGS-84 one)" },
            { symbol: "n", meaning: "mean motion, converted from revolutions per day to radians per second" },
          ],
          worked: [
            `n = ${WORKED_MEAN_MOTION_REV_DAY} rev/day → ${(WORKED_MEAN_MOTION_REV_DAY * 2 * Math.PI / 86400 * 1000).toFixed(4)}×10⁻³ rad/s.`,
            `a = (398,600.8 / n²)^⅓ = ${WORKED_A_TEXT} km — subtract Earth's radius and this satellite flies near ${Math.round(WORKED_ALT_KM)} km.`,
            "Every altitude, period and speed on every card begins exactly here, from exactly these stored digits.",
          ],
        },
        {
          kind: "terms",
          items: [
            { term: "Why integers", body: "Floating point rounds; integers do not. 15.44218077 becomes 1,544,218,077 exactly, and converts back exactly. So when two recounts disagree about an orbit, the difference is physics or code — never storage. That guarantee is what makes a daily recount meaningful rather than noisy." },
            { term: "The scales are below the noise", body: "Each stored step is smaller than the scatter of the orbit fits themselves, so nothing the detector is asked to notice is finer than what storage can represent. The ruler out-resolves the hand that draws.", note: "why exactness is sufficient, not just tidy" },
          ],
        },
        { kind: "figure", svg: figureB(), chip: "model", chipNote: "Model · the axis value is computed in this page's own code from the stated constants, and re-derived independently by the test suite.", caption: "One real mean motion through storage and back, losing nothing, then through the first formula every card uses. The number on the right is computed by this page, not typed into it." },
      ],
    },
    {
      kicker: "THE SHAPE OF A BURN",
      title: "Drag is a slope. A burn is a step.",
      lead: "Drag drains energy continuously: on a plot of orbit size against time it is a slope. An engine adds energy in minutes: a step. The whole step detector is a machine for telling those two shapes apart — built from statistics deliberately too stubborn to be fooled by the thing they measure.",
      blocks: [
        {
          kind: "terms",
          items: [
            { term: "Five-day blocks", body: "Fits arrive one to three times a day, and any single fit can be bad. Each five-day block keeps only its median, so a lone wild fit is simply outvoted before the detector ever sees it." },
            { term: "A baseline that cannot be dragged", body: "The expected value at any moment is the median over ±6 blocks — sixty days. A median moves only when half its inputs move, so a satellite would have to manoeuvre for a month before its own burns became its own normal. The baseline is stubborn on purpose: it is the fixed thing the step is measured against." },
            { term: "The bar: κ = 8", body: "The residual must exceed eight times the local noise scale — the median absolute deviation of the residuals, times 1.4826 so it reads like a standard deviation. Below that bar, the detector says nothing at all." },
            { term: "Two days of persistence", body: "A real burn changes the orbit permanently; a bad fit vanishes with the next one. A candidate must still be present two days later, across several newer fits, or it is discarded and counted as discarded." },
          ],
        },
        { kind: "figure", svg: figureC(), chip: "schematic", chipNote: "Schematic, animated · the rules drawn are the production rules (5-day blocks, ±6-block median, κ = 8, 2-day persistence); the scales are illustrative.", caption: "The trace redraws while the amber median holds its ground through the step; the residual crosses the κ band and, surviving two more days, is believed. With reduced motion requested, the finished picture is shown instead." },
      ],
    },
    {
      kicker: "THE ARITHMETIC'S HOME",
      title: "Ninety million tiny identical sums — and a proof before trust.",
      lead: "The recount's inner loop is a strange workload: each check is tiny, identical in shape to every other, and independent of the rest. That shape has a natural home — a graphics card, hardware built to run one small calculation thousands of times at once. It was given the job only after matching the old arithmetic answer for answer.",
      blocks: [
        {
          kind: "terms",
          items: [
            { term: "The split, measured", body: `${GPU_ACCEPTANCE.analysisShare}% of the recount's time is per-interval arithmetic — residuals, medians, bars. ${GPU_ACCEPTANCE.readShare}% is reading records. The ${GPU_ACCEPTANCE.analysisShare}% is what moved to the card, thousands of objects in each batch, so the lanes stay full.`, note: "measured 11 September 2026" },
            { term: "What stayed behind", body: "Classifying a flagged change and pricing its Δv is branchy, judgement-shaped code — and only about 0.26% of intervals ever reach it. It stays on an ordinary processor core, unchanged, where branches are cheap." },
            { term: "The bar for trust", body: `Before the card's answers counted, both versions ran side by side over ${GPU_ACCEPTANCE.intervals.toLocaleString("en-US")} real archive intervals — ${GPU_ACCEPTANCE.comparisons.toLocaleString("en-US")} individual comparisons. The required score was zero disagreements. The measured score was zero. Not close: identical, because medians and comparisons were kept exact and the card's fast-but-loose arithmetic modes were switched off.`, note: "acceptance, 12 September 2026" },
            { term: "What it bought", body: "While the recount runs it now uses roughly 0.7 of one processor core instead of most of the machine — and the machine's other work, including serving you this page, gets its processor back." },
          ],
        },
        {
          kind: "facts",
          items: [
            { value: `${GPU_ACCEPTANCE.analysisShare}%`, caption: "of the recount is card-shaped arithmetic" },
            { value: GPU_ACCEPTANCE.comparisons.toLocaleString("en-US"), caption: "side-by-side comparisons before trust" },
            { value: String(GPU_ACCEPTANCE.disagreements), caption: "disagreements found — the required score" },
            { value: "≈0.7", caption: "processor cores used while it runs" },
          ],
        },
        { kind: "figure", svg: figureD(), chip: "schematic", chipNote: "Schematic, animated · six lanes stand in for thousands; the shares and the acceptance counts are the 11–12 September 2026 measurements.", caption: "The same arithmetic in two shapes: one worker taking the queue in turn, or thousands of lanes at once. The card earned the job by scoring zero disagreements across 4,278,167 checks." },
      ],
    },
    {
      kicker: "SHARING THE CARD",
      title: "The card is shared, so the jobs queue.",
      lead: "The graphics card is not the recount's alone. Resident models keep their working memory on it around the clock; the recount and jobs like it are guests. Guests ask.",
      blocks: [
        {
          kind: "terms",
          items: [
            { term: "Ask, wait, run, release", body: "Every transient job requests space with an honest size estimate. If the spare memory holds it, it runs; if not, it queues — arrival order, with a promotion rule so nothing waits forever. When it finishes, everything it held is released." },
            { term: "A reserve nobody touches", body: "A fixed margin of the card's memory is never granted to guests at all, so the resident models' own growth is never squeezed by visiting arithmetic." },
            { term: "Refusal is loud", body: "A job that cannot get space in time says so and stops. It never runs unqueued and never silently degrades — a failure you can see is worth more than a success you cannot trust, which is this site's whole theory of operation in one sentence." },
          ],
        },
        { kind: "figure", svg: figureE(), chip: "schematic", chipNote: "Schematic · regions drawn to explain the rule, not to scale.", caption: "Residents keep their memory; a reserve is never granted; guests run in the spare region or wait their turn. Refusal is loud by design." },
      ],
    },
    {
      kicker: "TOLD STRAIGHT",
      title: "Three detectors failed before one earned its place.",
      lead: "The step detector's story reads clean because it survived. The long-arc drift detector did not — three designs running — and the site kept the receipts, because on this page the method is the product.",
      blocks: [
        {
          kind: "terms",
          items: [
            { term: "Three inversions", body: `Debris cannot manoeuvre, which makes it a free lie detector: any drift design can be scored by how often it flags debris versus payloads. Design one scored ${DRIFT_RECORD.separations[0]}× — debris flagged five times more often. Design two, "improved", scored ${DRIFT_RECORD.separations[1]}×. Design three, cleverer still, ${DRIFT_RECORD.separations[2]}×. All inverted, all condemned before any reader saw them.` },
            { term: "The sign said everything", body: `Splitting design one's false alarms by direction: ${DRIFT_RECORD.v1SignFast} of ${DRIFT_RECORD.v1SignFast + DRIFT_RECORD.v1SignSlow} were faster-than-expected decay — light debris genuinely out-falling its neighbours. Design two flipped the split: ${DRIFT_RECORD.v2SignSlow} of ${DRIFT_RECORD.v2SignFast + DRIFT_RECORD.v2SignSlow} slower-than-predicted, its drag model importing its own error. Both directions poisoned, by different causes.` },
            { term: "What earned its place", body: `Below 800 km on near-circular orbits, nothing without an engine climbs — so version four flags only sustained rising there, with no drag model anywhere. Full-2024 acceptance: ${DRIFT_RECORD.v4PassiveFlags} flags on ${DRIFT_RECORD.v4PassiveObjects.toLocaleString("en-US")} debris objects (bound ${DRIFT_RECORD.v4Bound} per 1,000), ${DRIFT_RECORD.v4PayloadCatches} payload catches — ${DRIFT_RECORD.v4Starlink} from a fleet documented to raise its own orbits. Separation ${DRIFT_RECORD.v4Separation}×.`, note: "empirical · acceptance runs, 12–20 September 2026" },
            { term: "Machine-gated wording", body: "None of this is typed onto a page by a person. The words — candidate, manoeuvre, propulsion — are chosen by code reading its own daily control counts, exactly as chapter 08 describes. When a lane's evidence is insufficient, its stronger words are simply unavailable to it, and the page says why." },
          ],
        },
        { kind: "figure", svg: figureF(), chip: "empirical", chipNote: "Empirical · separations and counts from the full-2024 acceptance runs, 12–20 September 2026.", caption: "Three designs below the usefulness floor, the sign split that diagnosed them, and the fourth design that earned its place by giving up drag models entirely." },
        {
          kind: "live",
          body: [
            "Pick any satellite on the globe and press <em>Open orbit history</em>. Every number on that card — the altitude, the residuals, the candidate wording — came out of this chapter's machinery this morning, from the public record, from nothing.",
            "Then read chapter 08 for the gate that chooses the words the machinery is allowed to use.",
          ],
          goto: { label: "Back to the globe to try it", view: "explore" },
        },
      ],
    },
  ],
  sources: [
    { ref: "1", title: `This site's published bundle of ${BUNDLE_DATE} (<code>${BUNDLE_PATH.split("/").pop()}</code>)`, where: "the object, event and control counts quoted through this chapter", url: BUNDLE_PATH },
    { ref: "2", title: "CelesTrak, \"GP Data Formats\"", where: "what each published element means, and the precision the catalogue prints", url: "https://celestrak.org/NORAD/documentation/gp-data-formats.php" },
    { ref: "3", title: "Hoots & Roehrich, <em>Spacetrack Report No. 3</em> (SGP4)", where: "the propagator convention behind μ = 398,600.8 km³/s² — the constant this chapter's worked figure deliberately keeps", url: "https://celestrak.org/NORAD/documentation/spacetrk.pdf" },
    { ref: "4", title: "Rousseeuw & Croux, \"Alternatives to the Median Absolute Deviation\", <em>JASA</em> 88(424), 1993", where: "the MAD and its 1.4826 consistency factor — the noise ruler under κ" },
    { ref: "5", title: "Brown, Cai & DasGupta, \"Interval Estimation for a Binomial Proportion\", <em>Statistical Science</em> 16(2), 2001", where: "the interval behind every per-1,000 bound this chapter quotes" },
    { ref: "6", title: "<code>pipeline/orbit_campaigns.py</code>, <code>pipeline/orbit_sweep_gpu.py</code> and <code>pipeline/orbit_drift.py</code>", where: "the recount, the card arithmetic and the drift rule as code. The code is the authority wherever this page has rotted" },
  ],
};
