/**
 * Chapter 08 — authoritative draft: /home/sdegan/LEARNING-PAGE-DESIGN.md,
 * 9 September 2026. Drafted prose is transcribed, not rewritten.
 * Bundle figures are pinned below; no live requests or archive scans occur here.
 * The pinned bundle is frozen byte-for-byte in
 * tests/fixtures/orbit-verdict-bundle-f0aee9b89f1c200f.json.gz, because an
 * immutable input must not live in a rotated directory: the previous freeze
 * cited orbit-events-b3112145df7493d8.json out of public/data/artifacts/, which
 * the data rotation then pruned, breaking both this chapter's citation and its
 * test. BUNDLE_PATH below stays a live /data/artifacts URL on purpose -- that is
 * the copy a reader downloads -- and deploy/prune_data.py pins it against the
 * same rotation.
 * Sample measurements are explicitly separate and must not become bundle claims.
 * See tests/orbit-verdict.test.ts for provenance, arithmetic and drawing checks.
 */
import type { Chapter } from "./satellite-fundamentals";

export const BUNDLE_DATE = "12 September 2026";
export const BUNDLE_PATH = "/data/artifacts/orbit-events-f0aee9b89f1c200f.json";
export const SAMPLE_NOTE = "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle";

export const VERDICT_SNAPSHOT = {
  "generatedAt": "2026-09-12T08:52:41Z",
  "targetRate": 0.001,
  "selfHistory": {
    "kappa": 32.0,
    "passive": {
      "flaggedObjects": 6255,
      "flags": 39927,
      "intervals": 89240016,
      "jeffreys95": [
        0.0004430400028558874,
        0.00045181518982656543
      ],
      "objectDays": 76919795.2,
      "objects": 12482,
      "ratePerInterval": 0.0004474113944578405,
      "ratePerObjectYear": 0.18959146625616374
    },
    "payload": {
      "flags": 192740,
      "intervals": 62708245,
      "jeffreys95": [
        0.0030599212961957027,
        0.0030873226031244427
      ],
      "objectDays": 41399666.7,
      "objects": 18764,
      "ratePerInterval": 0.0030735990139733617,
      "ratePerObjectYear": 1.7004553580772475
    },
    "boundRatio": 6.773,
    "requiredRatio": 10.0,
    "pointRatio": 6.86973790128402,
    "z": 407.599,
    "permitted": false
  },
  "cohort": {
    "kappa": 8.0,
    "windowDays": 7.0,
    "windowFrom": "2026-09-05T08:19:29Z",
    "windowTo": "2026-09-12T08:19:29Z",
    "passive": {
      "flags": 1326,
      "interval95": [
        0.02154,
        0.02396
      ],
      "intervals": 58344,
      "rate": 0.02273
    },
    "payload": {
      "flags": 6469,
      "interval95": [
        0.04194,
        0.04399
      ],
      "intervals": 150588,
      "rate": 0.04296
    },
    "boundRatio": 1.75,
    "requiredRatio": 10.0,
    "permitted": false
  },
  "objectsScanned": 68657,
  "objectsWithBaseline": 61249,
  "eventsPublished": 100748,
  "headlineEvents": 1500,
  "headlineByBasis": {
    "self-history": 1421,
    "cohort": 79
  },
  "headlineByEra": [
    162,
    307,
    1031
  ],
  "passiveHeadlineEvents": 3,
  "impossibleForClassEvents": 2,
  "groundTruth": {
    "detected": 18,
    "scorable": 27,
    "notDetected": 9,
    "pending": 7
  },
  "iss": {
    "agreementRatio": 0.992,
    "detectedDeltaVMetresPerSecond": 1.527,
    "detectedEndAt": "2025-11-20T05:19:55Z",
    "detectedSignature": "along-track-raise",
    "detectedStartAt": "2025-11-19T07:39:24Z",
    "norad": 25544,
    "object": "ISS (ZARYA)",
    "occurredAt": "2025-11-19T13:04:00Z",
    "publishedDeltaVMetresPerSecond": 1.54,
    "source": "https://gipoc.grc.nasa.gov/wp/pims/handbook/",
    "type": "reboost"
  }
} as const;

/** Sample tables transcribed from DETECTOR-DESIGN.md §§0.1, 1.1–1.3, F1, App. A.
 * Payloads were sampled 1 in 75; the shorthand “1-in-25 sample” names the debris sample.
 * Era ratios are the source's REPORTED ratios, not quotients of its rounded rates.
 * It supplies no per-era bounds. Do not manufacture them or a future era × band grid.
 */
export const VERDICT_SAMPLE = {
  kappa: [4, 8, 16, 32, 64, 128],
  passivePerThousand: [12.30, 3.92, 1.34, 0.46, 0.18, 0.093],
  payloadPerThousand: [28.6, 16.0, 9.1, 4.2, 1.7, 0.85],
  eras: [
    { name: "PRE-2013", passive: 0.885, payload: 1.53, reportedRatio: 1.7, passiveIntervals: 1645680, payloadIntervals: 282761, bounds: null },
    { name: "2013–2020", passive: 0.117, payload: 1.61, reportedRatio: 13.2, passiveIntervals: 986814, payloadIntervals: 199244, bounds: null },
    { name: "2021+", passive: 0.050, payload: 4.64, reportedRatio: 86.7, passiveIntervals: 993232, payloadIntervals: 410604, bounds: null },
  ],
  inclination: { quantum: 0.0001, scatter: 0.00006, reportedSigma: 0.00017, illustrativeTailSigma: 0.002, tailLow: 0.005, tailHigh: 0.05, median: 0.012, p10: 0.0064, p90: 0.036 },
} as const;

const INK = { cyan: "#29d4e3", coral: "#ff7b78", amber: "#f5c96a", mint: "#76e6a5", muted: "#8da8b3", line: "rgba(132,194,214,.28)", faint: "rgba(132,194,214,.08)" } as const;
const esc = (value: string) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
function label(x: number, y: number, words: string, colour: string = INK.muted, anchor = "start", size = 11): string {
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" style="fill:${colour};font-size:${size}px">${esc(words)}</text>`;
}
function lines(x: number, y: number, words: string[], colour: string = INK.muted, size = 11): string {
  return words.map((words, i) => label(x, y + i * 17, words, colour, "start", size)).join("");
}
function line(x1: number, y1: number, x2: number, y2: number, colour: string = INK.line, width = 1, dash = ""): string {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${colour}" stroke-width="${width}"${dash ? ` stroke-dasharray="${dash}"` : ""}></line>`;
}
function svg(letter: string, height: number, title: string, description: string, body: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 ${height}" role="img" aria-labelledby="verdict-${letter}-title verdict-${letter}-desc" data-verdict-figure="${letter}"><title id="verdict-${letter}-title">${esc(title)}</title><desc id="verdict-${letter}-desc">${esc(description)}</desc>${body}</svg>`;
}
function bracket(from: number, to: number, y: number, colour: string = INK.amber): string {
  return line(from, y, to, y, colour, 2) + line(from, y - 5, from, y + 5, colour, 2) + line(to, y - 5, to, y + 5, colour, 2);
}

/** Both gate drawings use precisely the same log transform and domain. */
export const GATE_AXIS = { minimum: 0.01, maximum: 100, left: 95, right: 665 } as const;
export function gateX(perThousand: number): number {
  return GATE_AXIS.left + Math.log10(perThousand / GATE_AXIS.minimum) / 4 * (GATE_AXIS.right - GATE_AXIS.left);
}
function gateGrid(top: number, bottom: number): string {
  return [0.01, 0.1, 1, 10, 100].map(value =>
    line(gateX(value), top, gateX(value), bottom, value === 1 ? INK.amber : INK.line, value === 1 ? 2 : 1, value === 1 ? "5 4" : "")
    + label(gateX(value), top - 10, String(value), value === 1 ? INK.amber : INK.muted, "middle")
  ).join("");
}
function tick(value: number, y: number, kind: "passive" | "payload"): string {
  const x = gateX(value), colour = kind === "passive" ? INK.coral : INK.cyan;
  return `<g data-rate-kind="${kind}" data-rate="${value}">${line(x, y - 12, x, y + 12, colour, 3)}<circle cx="${x}" cy="${y}" r="4" fill="${colour}"></circle></g>`;
}
function status(x: number, y: number, words: string, pass = false): string {
  const colour = pass ? INK.mint : INK.coral;
  return `<rect x="${x}" y="${y - 17}" width="${words.length * 7 + 22}" height="28" rx="4" fill="${INK.faint}" stroke="${colour}"></rect>` + label(x + 11, y + 1, words, colour);
}

function figureA(): string {
  const panels = [
    { title: "THE ATMOSPHERE", scale: ["Δa residual · 0.02–0.10", "m/s equivalent · 11 Oct 2024"], levels: [0, 0, 0, 1, 1, 1, 1, 1], verdict: ["ten debris flags in one", "day, all raises · declined", "by the planned shell", "correction"], colour: INK.coral },
    { title: "THE FITTER", scale: ["Δinclination · 0.012°", "legacy-debris medians"], levels: [0, 0, 0, 1, 1, 1, 1, 1], verdict: ["flagged today at 40 σ", "the σ was one printed", "digit — Section 3"], colour: INK.coral },
    { title: "THE CATALOGUE", scale: ["Δa · +1,755 / −1,755 km", "DELTA 1 R/B(2)"], levels: [0, 0, 1, 1, 1, 1, 0, 0], verdict: ["survived the persistence", "test · undone on the", "fourth fit · a swap"], colour: INK.coral },
    { title: "THE BURN", scale: ["Δa residual · +2,709.6 m", "ISS · 19 Nov 2025"], levels: [0, 0, 0, 1, 1, 1, 1, 1], verdict: ["flagged · NASA published", "1.54 m/s · agreed to 0.8 %"], colour: INK.mint },
  ];
  let body = label(25, 28, "A · ONE STEP, FOUR AUTHORS", INK.cyan, "start", 14)
    + label(25, 52, "CYAN = published fits · CORAL = impostors · MINT = independently corroborated", INK.muted)
    + label(25, 73, "Separate y-scales. Fit positions are hand-placed; dots do not fill unobserved intervals.", INK.muted);
  panels.forEach((panel, index) => {
    const x = 25 + index * 220;
    body += `<rect x="${x}" y="96" width="205" height="340" rx="6" fill="${INK.faint}" stroke="${INK.line}"></rect>`
      + label(x + 10, 119, panel.title, panel.colour)
      + lines(x + 10, 142, panel.scale, INK.muted, 10)
      + line(x + 14, 245, x + 190, 245);
    panel.levels.forEach((level, fit) => {
      const px = x + 18 + fit * 24, py = 237 - level * 57;
      body += `<circle cx="${px}" cy="${py}" r="3.5" fill="${INK.cyan}"></circle>`;
    });
    body += label(x + 10, 263, "consecutive fitted values →", INK.muted, "start", 10);
    if (index === 0) {
      body += label(x + 10, 284, "B* in the same fits:", INK.muted, "start", 10);
      body += `<path d="M${x + 18},299 h48 m24,15 h96" fill="none" stroke="${INK.coral}" stroke-width="1.5"></path>`;
      body += label(x + 100, 298, "−75–79%", INK.coral, "start", 10);
    } else if (index === 1) body += lines(x + 10, 286, ["printing quantum 0.0001°", "reported floor 0.00017°"], INK.muted, 10);
    else if (index === 2) body += lines(x + 10, 286, ["holds two observed days", "returns four fits later"], INK.muted, 10);
    else body += lines(x + 10, 286, ["drag's −74.4 m subtracted", "floor 1.527 m/s"], INK.muted, 10);
    body += line(x + 10, 329, x + 195, 329) + lines(x + 10, 351, panel.verdict, panel.colour, 10);
  });
  body += lines(25, 463, ["First three cases: sample-measured, not yet in the published bundle.", "ISS Δv: 12 September bundle; Δa and drag: Chapter 07's cited 4 September worked record."], INK.muted, 10);
  return svg("A", 500, "One step, four authors", "Four separate scales and schematic sequences of fits. Storm drag correction, a quantised inclination fit, and a catalogue identity swap resemble the independently published ISS reboost. Dots are illustrative fitted values; intervening observations are not supplied.", body);
}

function figureB(): string {
  const s = VERDICT_SAMPLE.inclination;
  const x = (deg: number) => 155 + Math.log10(deg / 0.00001) / 4 * 690;
  const kappa = VERDICT_SNAPSHOT.selfHistory.kappa;
  let body = label(25, 28, "B · THE RULER THAT MEASURED THE NOISE", INK.cyan, "start", 14)
    + label(25, 52, "Positions: sample-measured · bar heights: drawn shape, not counts", INK.muted)
    + label(25, 73, "Not yet in the published bundle. Zero is separate: it cannot sit on a logarithmic axis.", INK.muted);
  for (const deg of [0.00001, 0.0001, 0.001, 0.01, 0.1]) {
    body += line(x(deg), 215, x(deg), 380) + label(x(deg), 399, String(deg) + "°", INK.muted, "middle", 10);
  }
  body += `<rect x="48" y="209" width="31" height="171" fill="${INK.muted}" opacity=".65"></rect>`
    + label(63, 399, "0", INK.muted, "middle") + lines(25, 423, ["same printed", "value"], INK.muted, 10)
    + line(108, 218, 108, 380, INK.muted, 1, "3 5");
  for (const [deg, height] of [[s.quantum, 130], [2 * s.quantum, 62]] as const) {
    body += `<rect x="${x(deg) - 8}" y="${380 - height}" width="16" height="${height}" fill="${INK.muted}" opacity=".65"></rect>`;
  }
  body += `<rect x="${x(s.tailLow)}" y="339" width="${x(s.tailHigh) - x(s.tailLow)}" height="41" fill="${INK.coral}" opacity=".35"></rect>`
    + line(x(s.median), 313, x(s.median), 381, INK.coral, 2)
    + label(x(s.median), 301, "median 0.012°", INK.coral, "middle", 10)
    + bracket(x(s.p10), x(s.p90), 420, INK.muted)
    + label((x(s.p10) + x(s.p90)) / 2, 443, "p10 0.0064° · p90 0.036°", INK.muted, "middle", 10)
    + line(x(s.reportedSigma), 216, x(s.reportedSigma), 380, INK.coral, 2)
    + line(x(s.illustrativeTailSigma), 216, x(s.illustrativeTailSigma), 380, INK.mint, 2)
    + label(155, 103, "CORAL · what the estimator reported as σ: 0.00017°", INK.coral)
    + bracket(x(s.reportedSigma), x(kappa * s.reportedSigma), 126, INK.coral)
    + label(x(s.reportedSigma), 148, "κ = 32 bar, as computed: 0.0054°", INK.coral, "start", 10)
    + label(155, 176, "MINT · what the tail says σ is: about 0.002°", INK.mint)
    + bracket(x(s.illustrativeTailSigma), x(kappa * s.illustrativeTailSigma), 195, INK.mint)
    + label(x(s.illustrativeTailSigma), 231, "κ = 32 bar: about 0.06°", INK.mint, "start", 10)
    + lines(155, 478, ["|Δinclination| between consecutive fits · logarithmic degrees", "true fit scatter below GEO ≈ 0.00006° — smaller than the last printed digit"], INK.muted, 10);
  return svg("B", 520, "The ruler that measured the noise", "An illustrative distribution, not a counted histogram. Zero is separate from the logarithmic axis. The reported sigma is 0.00017 degrees; its 32-times bar is 0.00544. An illustrative tail-aware sigma of 0.002 places the bar at 0.064. Sample tail percentiles are marked; no missing counts are invented.", body);
}

function figureC(): string {
  const snapshot = VERDICT_SNAPSHOT;
  const rows = [
    { name: `SELF-HISTORY · κ = ${snapshot.selfHistory.kappa}`, upper: snapshot.selfHistory.passive.jeffreys95[1] * 1000, lower: snapshot.selfHistory.payload.jeffreys95[0] * 1000, ratio: snapshot.selfHistory.boundRatio, required: snapshot.selfHistory.requiredRatio, y: 205, digits: 3 },
    { name: `COHORT · κ = ${snapshot.cohort.kappa} · ${snapshot.cohort.windowDays}-day window`, upper: snapshot.cohort.passive.interval95[1] * 1000, lower: snapshot.cohort.payload.interval95[0] * 1000, ratio: snapshot.cohort.boundRatio, required: snapshot.cohort.requiredRatio, y: 365, digits: 1 },
  ];
  let body = label(25, 28, "C · THE GATE, DRAWN TO SCALE", INK.cyan, "start", 14)
    + label(25, 53, "CORAL = debris upper95 · CYAN = payload lower95 · AMBER = required reach", INK.muted)
    + label(25, 75, `${BUNDLE_DATE} bundle · flags per 1,000 intervals · logarithmic axis`, INK.muted)
    + label(gateX(1), 100, "(i) target: 1", INK.amber, "middle")
    + gateGrid(129, 401);
  rows.forEach(row => {
    const target = row.upper * row.required;
    const offScale = target > GATE_AXIS.maximum;
    const endpoint = gateX(Math.min(target, GATE_AXIS.maximum));
    const firstPass = row.upper < snapshot.targetRate * 1000;
    const secondPass = row.lower / row.upper >= row.required;
    body += label(25, row.y - 57, row.name, INK.cyan)
      + `<g data-gate-target="${target}" data-off-scale="${offScale}">${bracket(gateX(row.upper), endpoint, row.y - 27)}</g>`
      + tick(row.upper, row.y, "passive") + tick(row.lower, row.y, "payload");
    if (offScale) {
      body += `<path d="M${endpoint - 7},${row.y - 33} l9,6 l-9,6" fill="none" stroke="${INK.amber}" stroke-width="2"></path>`
        + lines(685, row.y - 34, [`→ ${Math.round(target)} (off scale)`, "payload lower bound", "must reach here"], INK.amber, 10)
        + label(gateX(row.upper) - 9, row.y + 30, row.upper.toFixed(row.digits), INK.coral, "end")
        + label(gateX(row.lower) + 9, row.y + 30, row.lower.toFixed(row.digits), INK.cyan);
    } else {
      body += label(gateX(row.upper), row.y - 37, `payload lower bound must reach here → ${target.toFixed(2)}`, INK.amber, "start", 10)
        + label(gateX(row.upper), row.y + 30, row.upper.toFixed(row.digits), INK.coral, "middle")
        + label(gateX(row.lower), row.y + 30, row.lower.toFixed(row.digits), INK.cyan, "middle");
    }
    const margin = firstPass ? ` — ${row.ratio.toFixed(1)} of ${row.required}` : "";
    body += status(25, row.y + 64, `(i) ${firstPass ? "PASS" : "FAIL"} · (ii) ${secondPass ? "PASS" : "FAIL"}${margin}`, firstPass && secondPass)
      + label(510, row.y + 65, `bound ratio ${row.ratio.toFixed(2)} · candidate`, INK.coral);
  });
  body += line(25, 462, 875, 462)
    + label(25, 492, "WHY NOT JUST RAISE κ", INK.cyan, "start", 14)
    + lines(25, 515, ["κ ladder: 1-in-25 debris / 1-in-75 payload sample · 9 September 2026", "Semi-major-axis channel, before the persistence test — not yet in the published bundle."], INK.muted, 10);
  const x = (i: number) => 95 + i * 142;
  const y = (rate: number) => 755 - Math.log10(rate / 0.05) / Math.log10(100 / 0.05) * 172;
  for (const rate of [0.1, 1, 10, 100]) {
    body += line(95, y(rate), 805, y(rate)) + label(82, y(rate) + 4, String(rate), INK.muted, "end", 10);
  }
  for (const [rates, colour] of [[VERDICT_SAMPLE.passivePerThousand, INK.coral], [VERDICT_SAMPLE.payloadPerThousand, INK.cyan]] as const) {
    body += `<polyline points="${rates.map((rate, i) => `${x(i)},${y(rate)}`).join(" ")}" fill="none" stroke="${colour}" stroke-width="2"></polyline>`;
    rates.forEach((rate, i) => {
      body += `<circle cx="${x(i)}" cy="${y(rate)}" r="4" fill="${colour}"></circle>`
        + label(x(i), y(rate) + (colour === INK.cyan ? -10 : 18), String(rate), colour, "middle", 10);
    });
  }
  VERDICT_SAMPLE.kappa.forEach((kappa, i) => {
    const ratio = VERDICT_SAMPLE.payloadPerThousand[i]! / VERDICT_SAMPLE.passivePerThousand[i]!;
    body += label(x(i), 570, ratio.toFixed(1) + "×", INK.amber, "middle")
      + label(x(i), 787, String(kappa), INK.muted, "middle");
  });
  body += label(25, 570, "ratio", INK.amber, "start", 10)
    + label(842, 787, "κ", INK.muted)
    + lines(25, 818, ["Rates per 1,000 · lines connect only the six measured thresholds.", "ratio flattens near nine; payload flags fall 28.6 → 0.85 per 1,000 — a detector that finds nothing"], INK.muted, 10);
  return svg("C", 862, "The two-half gate, drawn to scale, and the kappa ladder", "Shared logarithmic axis from 0.01 to 100 flags per thousand. Self-history debris upper bound 0.452, payload lower bound 3.060, required reach 4.52: first half passes, second fails. Cohort upper 24.0 and lower 41.9 fail both halves; its 240 target is explicitly off scale. Below are sample rates in the semi-major-axis channel before persistence; the ratio levels off near nine as both rates fall.", body);
}

function figureD(): string {
  let body = label(25, 28, "D · THREE ERAS, ONE DETECTOR", INK.cyan, "start", 14)
    + lines(25, 53, ["CORAL = debris point rate · CYAN = payload point rate · AMBER = 10× debris / 1‰ target", "Sample rates, not bounds; not yet in the published bundle. Counts at right: 9 September bundle."], INK.muted, 10)
    + gateGrid(124, 535)
    + label(708, 100, "HEADLINE EVENTS", INK.muted, "start", 10);
  VERDICT_SAMPLE.eras.forEach((era, i) => {
    const y = 182 + i * 151;
    const count = VERDICT_SNAPSHOT.headlineByEra[i]!;
    const passFirst = era.passive < 1;
    const passSecond = era.reportedRatio >= 10;
    body += label(25, y - 37, era.name, INK.cyan)
      + bracket(gateX(era.passive), gateX(era.passive * 10), y - 18)
      + tick(era.passive, y, "passive") + tick(era.payload, y, "payload")
      + label(gateX(era.passive) - 7, y + 29, era.passive.toFixed(3), INK.coral, "end")
      + label(gateX(era.payload) + 7, y + 29, era.payload.toFixed(2), INK.cyan)
      + status(25, y + 60, `(i) ${passFirst ? "pass" : "FAIL"} · (ii) ${passSecond ? "pass" : "FAIL"}`, passFirst && passSecond)
      + label(390, y + 61, `reported ratio ${era.reportedRatio}`, passSecond ? INK.mint : INK.coral)
      + `<rect data-headline-count="${count}" x="708" y="${y - 13}" width="${count / Math.max(...VERDICT_SNAPSHOT.headlineByEra) * 150}" height="17" fill="${INK.muted}"></rect>`
      + label(708, y + 29, count.toLocaleString("en-US"), INK.muted)
      + `<rect x="708" y="${y + 43}" width="154" height="26" rx="3" fill="none" stroke="${INK.muted}" stroke-dasharray="3 4"></rect>`
      + label(716, y + 60, "95% bounds: missing", INK.muted, "start", 10);
  });
  body += lines(25, 595, ["Flags per 1,000 intervals · same logarithmic axis as Figure C. Sample verdicts, not released labels.", "Reported ratios are bound-to-bound — the payload rate's lower bound against the passive rate's upper — so each sits below the quotient of the point rates beside it. That conservative comparison is the one the gate itself uses.", "Era-by-altitude calibration is not yet published. No predicted pass grid is drawn."], INK.muted, 10);
  return svg("D", 655, "Three eras of the same detector, with unpublished bounds shown missing", "Point rates from the sample, not confidence bounds. Pre-2013: debris 0.885, payload 1.53, reported ratio 1.7, separation fails. 2013 to 2020: 0.117, 1.61, reported ratio 13.2. From 2021: 0.050, 4.64, reported ratio 86.7. Later rows are sample passes, not permission to relabel events. Headline counts are 162, 307 and 1031. All era confidence bounds are missing; no era-by-altitude grid is invented.", body);
}


export const CH_VERDICT: Chapter = {
  "id": "earning-the-word",
  "index": "08",
  "title": "Earning the word",
  "door": `Every orbit-history card said candidate where you might expect manoeuvre, in the ${BUNDLE_DATE} bundle — most now earn the word instead. This chapter is what it takes to earn that word from public data, how the site measures its own mistakes, and why 2024 may earn it while 2005 may not.`,
  "covers": [
    "why open elements matter",
    "four authors of one step",
    "the broken ruler",
    "the blank",
    "the two-part gate",
    "what candidate means",
    "eras and strata",
    "what the word will still not mean"
  ],
  "lead": `Every card in the orbit-history browser said <em>candidate</em> where you might expect <em>manoeuvre</em>, in the ${BUNDLE_DATE} bundle — most now earn the word instead. This chapter is why. What it takes to earn that word from nothing but public element sets; how the site measures its own error rate; how the instrument that measured that error was itself broken for a while; and why a 2024 event may earn the word while the identical signature from 2005 never will. The measured numbers are a snapshot of the ${BUNDLE_DATE} bundle. The browser always carries today's.`,
  "sections": [
    {
      "kicker": "WHY THIS IS WORTH DOING",
      "title": "An orbit is public. Intent is not.",
      "lead": "Every tracked object's orbit is published several times a day by a catalogue anyone can read. Nothing in it says who fired an engine, when, or why. Reading a burn out of that stream is a small intelligence capability built from open data alone — and it is worth understanding exactly how much it can say, and how much it cannot.",
      "blocks": [
        {
          "kind": "terms",
          "items": [
            {
              "term": "What a card can say",
              "body": "Between these two published fits, this object's orbit changed by more than nature explains, and the cheapest burn that produces that change costs at least this much. The date is a window — the gap between the two fits, usually about half a day. The cost is a floor. The direction is the cheapest one.",
              "operational": "\"At least 7.6 m/s along the track, between 24 and 26 September 2024\" is a defensible sentence about GEESAT 3-10. \"A 7.6 m/s burn on 25 September\" is not: the record cannot place it that finely, and the true spend is above the floor by an amount nobody can read from the elements."
            },
            {
              "term": "What it never says",
              "body": "Why. Whether it was planned, commanded, successful, or even noticed by the operator. Which thruster; whether one burn or several; which way the engine pointed beyond in-plane or out-of-plane. The elements record the orbit that resulted, not the decision that produced it.",
              "operational": "Purpose language on a card — \"expected for class\", \"larger than typical\" — comes from what objects of this kind usually do. The detection did not learn it. A raise on a communications payload is expected; the step told the site nothing about intent."
            },
            {
              "term": "Why a floor is still worth having",
              "body": "A lower bound that lands within 1 per cent of the operator's own on-board figure — the ISS reboost of 19 November 2025, 1.527 m/s against NASA's 1.54 — is a floor you can plan against. It is honest about which way it can be wrong: the truth sits above it, never below."
            }
          ]
        },
        {
          "kind": "facts",
          "items": [
            {
              "value": "68,657",
              "caption": "objects scanned in this bundle; 61,249 with enough of their own history for a baseline"
            },
            {
              "value": "151.9 M",
              "caption": "consecutive-fit intervals judged by the self-history lane — 89.2 M on debris and stages, 62.7 M on payloads"
            },
            {
              "value": "100,748",
              "caption": "changes found across the archive; 1,500 in the headline list, every one also in its object's own shard"
            },
            {
              "value": "18 of 27",
              "caption": "operator-published manoeuvres detected where the archive could see them; 9 missed, 7 in a gap it cannot see"
            }
          ]
        }
      ]
    },
    {
      "kicker": "WHY IT IS HARD",
      "title": "You never see a burn. You see a step in someone else's fit.",
      "lead": "The catalogue publishes fitted model orbits, not measurements. A burn appears only as a difference between two fits — and so does a poorly tracked fragment, a geomagnetic storm, a catalogue mix-up and a fitter having a bad arc. Four authors, one signature. Telling them apart, at a measured error rate, is the whole job.",
      "blocks": [
        {
          "kind": "figure",
          "svg": figureA(),
          "chip": "schematic",
          "chipNote": "Schematic · four real records (11 Oct 2024 storm day, legacy-debris inclination medians, DELTA 1 R/B(2), ISS 19 Nov 2025); traces drawn to the stated sizes, not sampled from the shards. measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle.",
          "caption": "Four steps that look alike. One is the fitter carrying a storm; one is the catalogue printing inclination more coarsely than it scatters; one is two objects swapped and swapped back; one is a burn NASA measured on board. The persistence test alone catches none of the first three. The verdict under each panel is what the site does about it today."
        },
        {
          "kind": "terms",
          "items": [
            {
              "term": "The atmosphere",
              "body": "A storm swells the upper atmosphere and every object in a shell decays faster. On 11 October 2024 (Ap 116) the debris sample produced ten flags in one day — all raises, all with the drag term re-solved 75–79 per cent lower in the same fit. That is not the sky lifting debris. It is the fitter carrying storm drag into one fit and correcting it in the next, catalogue-wide.",
              "operational": "A storm bends every object in a shell; a burn bends one. The planned correction subtracts what the whole shell did that day, rather than gating on a storm index — a storm gate was measured and cost 15 per cent of genuine payload flags, because modern payloads raise through storms on purpose.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "The fitter",
              "body": "A fragment tracked on sparse arcs gets a fit that jumps. Published inclinations of legacy debris step by a median 0.012° — 1.3 m/s if it were a burn — at altitudes where nothing natural moves inclination by that much. The catalogue's description moved. The orbit did not. This is the single largest source of false alarms, and the next section is about it.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "The catalogue",
              "body": "Objects get swapped. DELTA 1 R/B(2) rose 1,755 km and fell 1,755 km four fits later. A FREGAT stage \"changed plane\" by 0.51°, which would be 81 m/s on an empty tank. Identity mistakes inside breakup clouds produce steps that persist for days, exactly as a burn would — the persistence test cannot catch a swap that lasts.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "The burn",
              "body": "And sometimes an operator did fire. The detector's job is not to find steps — that is easy — but to refuse the three impostors at a rate it has measured, and to print that rate beside every claim. Where it cannot separate them, it says so: \"cause not separable\" is a published result, in its own colour."
            },
            {
              "term": "And the direction is unknown",
              "body": "A step in semi-major axis says the orbit gained energy, not which way the engine pointed. Chapter 07 prices the cheapest burn that fits. Every dearer story — off-axis, split into two, spread over hours — is also consistent with the same step. So every cost is a floor, and the floor is the only number the record can honestly support.",
              "operational": "Most of what modern electric propulsion does is smeared across several fits: 72.6 per cent of payload along-track flags are the front edge of a ramp, not a single impulse. The step detector catches the edge and prices that. The rest of the climb is the thrust-excess lane's business.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            }
          ]
        },
        {
          "kind": "facts",
          "items": [
            {
              "value": "1 in 10²²⁴",
              "caption": "what pure fit scatter would produce at κ = 32. Measured on debris: 0.46 per 1,000 before persistence. No false alarm is noise; every one is a real change in the published numbers (1-in-25 sample, 9 September 2026)"
            },
            {
              "value": "5.9% vs 1.1%",
              "caption": "share of debris flags, then payload flags, that sit in the first interval after a tracking gap of three days or more — the fit is on a new arc (1-in-25 sample, 9 September 2026)"
            },
            {
              "value": "8.9%",
              "caption": "of debris semi-major-axis flags are undone by an equal-and-opposite step two to eight fits later: a swap or a re-fit, coming home (1-in-25 sample, 9 September 2026)"
            },
            {
              "value": "17% vs 2.4%",
              "caption": "share of debris, then payload, flags on high-eccentricity transfer and HEO orbits, where near-identical spent stages get confused with each other (1-in-25 sample, 9 September 2026)"
            }
          ]
        }
      ]
    },
    {
      "kicker": "THE INSTRUMENT WAS BROKEN",
      "title": "The ruler that measured the noise was the noise.",
      "lead": "The detector asks whether a step is large compared with this object's own fit scatter, and that scatter is measured, not assumed. For inclination on old debris the measurement was wrong — wrong in the flattering direction, so the detector saw forty-sigma events that were nothing. Sixty-nine per cent of all false alarms trace to this one defect.",
      "blocks": [
        {
          "kind": "terms",
          "items": [
            {
              "term": "The last printed digit",
              "body": "The catalogue prints inclination to 0.0001°. Below geostationary altitude the true fit-to-fit scatter is about 0.00006° — smaller than the last digit. So most consecutive fits differ by exactly zero, or by one digit. An estimator built on the typical difference sees one digit and reports that as the noise.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "Why that is a lie",
              "body": "A poorly tracked fragment has two behaviours: months of fits that agree to the last digit, then a jump of 0.005–0.05° when the fitter gets a sparse or contaminated arc. The typical difference cannot see the rare jump. It reports a floor of 0.00017°, and the jumps then stand forty to sixty \"sigmas\" tall. Sigma was one printing quantum.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "The fix, and why it is deliberately narrow",
              "body": "Measure the floor from the tail — the 95th percentile of the differences, rescaled — but only for inclination, and only below geostationary altitude, where the catalogue floor sits at the printing quantum. Applied to semi-major axis or eccentricity the same rule would erase 71 per cent of genuine payload flags, because a manoeuvring payload's tail <em>is</em> its burns.",
              "operational": "Predicted from the sample: debris flags fall 60.7 per cent, payload flags 5.9 per cent, and the separation ratio rises from 6.8 to about 16. The acceptance test is the whole-archive sweep, not the sample. As of this bundle the sweep has not run, and the page will say so until it has.",
              "note": "Planned / predicted from the sample — not yet in the published bundle"
            },
            {
              "term": "The teaching point",
              "body": "Every \"how confident are we\" figure rests on an estimate of noise. If the noise estimate is broken, the confidence is fiction — and this kind fails in the flattering direction, making the detector look sharper than it is. The blank caught it. Without objects that cannot manoeuvre, nobody would have known the ruler was bent.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            }
          ]
        },
        {
          "kind": "figure",
          "svg": figureB(),
          "chip": "schematic",
          "chipNote": "Schematic · positions from the 1-in-25 debris sample, 9 September 2026; bar heights drawn to show the shape, not counted. measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle.",
          "caption": "The estimator measured the typical fit-to-fit difference in inclination and found one printed digit, because the true scatter is smaller than the catalogue prints. So its κ = 32 bar sat at 0.005°, and every one of the fitter's 0.005–0.05° jumps cleared it. A floor read from the tail sits ten times higher, and the jumps sit under it. Bar heights are drawn, not counted."
        }
      ]
    },
    {
      "kicker": "THE BLANK",
      "title": "Objects with no engine grade the detector.",
      "lead": "There is no answer key for manoeuvres; operators rarely publish them. What the archive does hold is 12,482 pieces of debris and spent stages that cannot burn. Run the detector on them and every flag is a known error, measured on the same fits, the same outages and the same weather as the payloads it judges. Chapter 07 introduced this blank; here is what it decides.",
      "blocks": [
        {
          "kind": "terms",
          "items": [
            {
              "term": "Two detectors, two blanks",
              "body": "Self-history compares an object with its own past, needs years of it, requires the step to survive two observed days, and uses κ = 32. Cohort compares an object with its neighbours over the same seven days, cannot wait for persistence, and uses κ = 8. Different questions, different error rates, never averaged. The card names which one judged the event."
            },
            {
              "term": "Why their rates are so different",
              "body": "Self-history flagged 39,927 of 89,240,016 debris intervals: 0.45 per 1,000. Cohort flagged 1,326 of 58,344: 22.7 per 1,000. Cohort is the new-object lane, for things with no history yet; it judged 79 of the 1,500 headline events, and each of those says so. Nothing cohort-judged is called a manoeuvre in this bundle."
            },
            {
              "term": "What \"candidate\" does not mean",
              "body": "Not \"probably noise\". Payload intervals are flagged 6.9 times as often as debris intervals, so at most one payload flag in seven could be the same kind of error. Candidate means: a real change in the published orbit, priced as a floor, found by a detector that has not yet proved its error rate small enough to name a cause."
            },
            {
              "term": "The soft spot, declared",
              "body": "That a fragment cannot burn is physics. That a given object <em>is</em> a fragment is the catalogue talking, and an entry can be wrong or stale. So a debris flag is \"false by the catalogue's own account\", not \"false with certainty\". The refusal to call it a manoeuvre is absolute either way; only its warrant is stated honestly."
            }
          ]
        },
        {
          "kind": "equation",
          "name": "The two halves of the gate",
          "tag": "both must pass, per detector",
          "formula": "(i)   upper95( debris rate )   &lt;   1 per 1,000\n(ii)  lower95( payload rate )  ≥   10 × upper95( debris rate )",
          "where": [
            {
              "symbol": "upper95, lower95",
              "meaning": "Jeffreys 95 per cent bounds, not point estimates. At zero flags a naive interval reports a false-alarm rate of exactly zero, which no blank can support."
            },
            {
              "symbol": "1 per 1,000",
              "meaning": "The design target, written into the design document before any measurement existed, and never moved. If the measurement does not reach it, the plots ship and the label does not."
            },
            {
              "symbol": "10 ×",
              "meaning": "If the same error acts on both classes, its share of payload flags is at most debris rate over payload rate; ten times holds that share under one in ten. Fixed before the data. A threshold chosen to pass today's numbers would have been about two."
            }
          ],
          "worked": [
            "Self-history, 12 September 2026. Debris upper bound 0.452 per 1,000 — half (i) passes with a factor-2.2 margin. Payload lower bound 3.060 per 1,000; 3.060 ÷ 0.452 = 6.77, against the 10 required — half (ii) fails. Every self-history event is therefore a candidate, and the gap is the number the engineering is aimed at.",
            "Cohort, same bundle: debris upper bound 24.0 per 1,000, so half (i) fails by a factor of 24, and the ratio is 1.75. Cohort-judged events are candidates and are expected to stay so; a seven-day window cannot carry a persistence test.",
            "Why not a significance test. Against 89 million and 63 million intervals the two-proportion z is 408, and the same test stays \"significant\" for a rate ratio of 1.001. It measures the size of the archive, not the quality of the detector — and would let a detector tightened until it finds almost nothing declare victory. Until 8 September 2026 that is what half (ii) was."
          ]
        },
        {
          "kind": "figure",
          "svg": figureC(),
          "chip": "schematic",
          "chipNote": "Schematic · both lanes from the 12 September 2026 bundle's control block; κ ladder from the 1-in-25 sample, semi-major-axis channel, before the persistence test. measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle.",
          "caption": "Both halves of the gate, to scale. Self-history clears the 1-per-1,000 line with room to spare and still fails: its payload rate is 6.8 times its debris rate, not 10. Cohort fails both. Below, the reason the fix is not simply a higher threshold: raising κ divides both rates, the ratio flattens near nine, and the payload flags it keeps dwindle toward nothing."
        }
      ]
    },
    {
      "kicker": "WHAT THE PAGE SHOWS",
      "title": "Reading a card: what each line is allowed to claim.",
      "lead": "A card is built from the evidence outward, and every sentence on it is generated from computed numbers — none is typed. Here is what each part is, which evidence class it belongs to, and the claim it is permitted to make.",
      "blocks": [
        {
          "kind": "terms",
          "items": [
            {
              "term": "The observation",
              "body": "\"Between fit A and fit B, semi-major axis rose 2,709.6 m; drag predicted −74.4 m.\" A statement about two published fits and a measured neighbourhood decay rate. It is the only line on the card that is observed rather than inferred — and even it is about fits, not positions.",
              "note": "observed"
            },
            {
              "term": "The cost",
              "body": "\"At least 1.53 m/s.\" The cheapest burn consistent with the residual. A floor in every case: the true spend is above it by an amount the elements do not contain.",
              "note": "inferred, lower bound"
            },
            {
              "term": "The signature",
              "body": "\"Along-track raise (candidate).\" The shape of the element change, in the reader's words. The colour says what the elements moved like; it never says an operator did it. The bracket is the gate's verdict for this event's own detector, and it changes only when that detector earns it.",
              "note": "classification of the shape"
            },
            {
              "term": "The alternatives",
              "body": "Drag, fit noise, re-acquisition after a gap, a storm — each listed with what the evidence says about it. The card does not pick one. \"Cause not separable\" is published as a result in its own colour, not hidden; \"we cannot tell\" and \"it is not thrusting\" are different statements and never ship as the same one."
            },
            {
              "term": "The control that judged it",
              "body": "The blank for this event's own detector: counts, bounds, and the gate's verdict. Since 8 September 2026 the lane is named on the card. Before that the field was published and read by nothing — a bound computed and not applied, which is the defect class this whole subsystem keeps rediscovering."
            },
            {
              "term": "The class expectation",
              "body": "\"Expected for class\", \"larger than typical\", \"impossible for class\". Where purpose language comes from: what objects of this kind usually do, not what this detection revealed. Two headline events in this bundle are on debris and read \"impossible for class\", and a third is on an object the catalogue does not classify at all. They are the blank, showing its work in public.",
              "note": "empirical"
            },
            {
              "term": "Missing is drawn missing",
              "body": "A gap in the archive is a gap on the plot. Nothing is interpolated across it, no cadence is measured across it, and a manoeuvre an operator published inside it is scored <em>unscorable</em>, never <em>missed</em>. The largest is the hole between the end of the bulk bundles and the start of live capture: 31 December 2025 to 7 August 2026."
            },
            {
              "term": "The ceiling",
              "body": "The screen at twice perigee speed sits safely inside the true single-impulse ceiling of about 2.4 times perigee speed. Until 8 September 2026 the self-history lane priced five events above that screen and, because the page sorts by cost, they were its top five rows. A bound that is computed but not applied is a page that lies politely."
            }
          ]
        },
        {
          "kind": "live",
          "body": [
            "Open any satellite's card and press <em>Open orbit history</em>. In the dialog titled <em>How this orbit has changed</em>, read the control block at the top: both blanks, both payload rates, and each lane's verdict, with today's numbers. Then open one event and find the line that names which detector judged it."
          ]
        }
      ]
    },
    {
      "kicker": "NOT ALL YEARS ARE EQUAL",
      "title": "Why 2024 may earn the word and 2005 may not.",
      "lead": "The pooled numbers above hide something. Run the same detector, at the same κ, on debris from three eras: the false-alarm rate is 0.885 per 1,000 before 2013, 0.117 for 2013–2020, and 0.050 from 2021. Payload rates go the other way. The detector did not change between those years. The catalogue did.",
      "blocks": [
        {
          "kind": "figure",
          "svg": figureD(),
          "chip": "schematic",
          "chipNote": "Schematic · era rates from the 1-in-25 sample, 9 September 2026, today's detector — rates, not bounds; not yet in the published bundle. Event counts from the bundle.",
          "caption": "The same detector, the same κ, three eras of the same catalogue. Debris false alarms fall eighteen-fold from the first row to the last; payload flags rise threefold; the ratio goes from 1.7 to 87. The pooled figure of 6.8 is the average of a row that cannot pass and two that pass easily. Rates from a sample, not bounds; the bundle will carry the bounds."
        },
        {
          "kind": "terms",
          "items": [
            {
              "term": "What changed — declared as inference",
              "body": "Before 2013 the catalogue's fits on small fragments jump more, cross-tags inside breakup clouds are commoner, and tracking gaps are longer; the debris say so. The site reads the boundaries off that curve. It does not claim to know which sensor, software or practice change caused it, and the page will not pretend to.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "Why not average",
              "body": "Averaged, the archive reports a ratio of 6.8 and fails. Stratified, the ratio is 1.7 before 2013, 13 for 2013–2020, and 87 from 2021: two eras pass comfortably and one never will. The pooled number is a comfortable lie in both directions — too kind to 2005, too harsh to 2024. Honesty is treating them apart.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "What the reader will see",
              "body": "The same signature, the same cost, on the same kind of satellite: a 2024 event may say <em>manoeuvre — inferred</em>; a 2005 event will say <em>candidate</em>. That looks inconsistent. It is the opposite. Each event is judged by the blank that saw the same catalogue it came from, and the card will name the era and altitude band that judged it.",
              "operational": "89 per cent of the headline events are from 2013 or later. Once the inclination fix lands and the strata ship, roughly nine events in ten sit in a stratum that can pass. Even then the word is not automatic: every stratum must clear both halves on the whole archive, with a margin — a ratio of 12, because a pass at 10.3 is a coin flip.",
              "note": "Planned / predicted from the sample — not yet in the published bundle"
            },
            {
              "term": "Where the word may never be earnable",
              "body": "Pre-2013 debris shells at 500–1,500 km, where the ratio is about 3 whatever is modelled; and high-eccentricity rocket-body orbits in every era, where near-identical spent stages get confused and the ratio sits near 5. There the two populations are the same fitting process looking at similar objects. A detector that claimed otherwise would be claiming to see through the catalogue.",
              "note": "measured on a 1-in-25 sample, 9 September 2026 — not yet in the published bundle"
            },
            {
              "term": "The rules, fixed before the sweep",
              "body": "Era boundaries read off the debris curve before the acceptance run, never adjusted after it. Five altitude bands — the noise floor's own. A stratum with fewer than 200,000 debris intervals publishes \"not calibrated\", never a pass. All fifteen strata are published, the failing ones included, so a pooled pass can never hide a stratum that fails.",
              "note": "Planned / predicted from the sample — not yet in the published bundle"
            }
          ]
        },
        {
          "kind": "facts",
          "items": [
            {
              "value": "162 / 307 / 1,031",
              "caption": "headline events from before 2013, 2013–2020, and 2021 onward — the eras carry 11, 20 and 69 per cent of what a reader opens"
            },
            {
              "value": "0.885 → 0.050",
              "caption": "debris false alarms per 1,000 intervals, before 2013 and from 2021 — an 18-fold change with κ fixed at 32 (1-in-25 sample, 9 September 2026)"
            },
            {
              "value": "1.7 / 13 / 87",
              "caption": "payload-to-debris bound ratio by era, against the 10 required — today's detector, before any fix (same sample) (1-in-25 sample, 9 September 2026 — not yet in the published bundle)"
            },
            {
              "value": "1,500–30,000 km",
              "caption": "the perigee band that passes in no era: ratios 5.0 and 5.4 where it can be measured at all (1-in-25 sample, 9 September 2026 — not yet in the published bundle)"
            }
          ]
        }
      ]
    },
    {
      "kicker": "WHAT THE WORD WILL STILL NOT MEAN",
      "title": "Earned is not confirmed.",
      "lead": "When a stratum passes and a card says <em>manoeuvre</em>, the word means this: a detector whose false-alarm rate is bounded below one in a thousand, and whose payload rate stands ten times clear of it, found a persistent step on a payload. It does not mean the site knows what happened.",
      "blocks": [
        {
          "kind": "terms",
          "items": [
            {
              "term": "Still an inference",
              "body": "The cause is inferred from the shape of the element change and the class expectation. The Δv is a floor. The direction is the cheapest one. The time is a window. The exact wording is <em>manoeuvre — inferred, not confirmed</em>; <em>confirmed</em> is reserved for events an operator independently published, cited on the card."
            },
            {
              "term": "The floor under the floor",
              "body": "After every fix in the design, about one debris flag remains per 100,000–200,000 intervals — one per five hundred object-years. Those are the catalogue re-fitting on a changed arc, indistinguishable from a burn in the elements alone. That is the limit of this data source, not of this detector. A second source would move it. Nothing else will.",
              "note": "Predicted from the sample — not yet in the published bundle"
            },
            {
              "term": "How to explain a card to a colleague",
              "body": "Say four things. This orbit changed by more than nature explains, between these two dates. The cheapest burn that does that costs at least this much. The detector that found it is wrong this often on objects that cannot burn — measured this month, printed beside the claim. And whether it earns the word depends on the era and altitude it came from, because the catalogue was not the same instrument in 2005 as in 2024."
            }
          ]
        },
        {
          "kind": "live",
          "body": [
            "Everything measured in this chapter was copied from the bundle published on 12 September 2026 and will move as sweeps complete: the inclination fix, the tracking-gap rule and the era strata are each behind a flag with a failing acceptance test in front of it, and each sweep changes exactly one. The browser carries the latest verdict. Go and read one."
          ],
          "goto": {
            "label": "Go and read one →",
            "view": "explore"
          }
        }
      ]
    }
  ],
  "sources": [
    {
      "ref": "1",
      "title": "Space-Track.org, 18th Space Defense Squadron",
      "where": "the element sets; the only orbital-elements source this site uses"
    },
    {
      "ref": "2",
      "title": "<code>docs/orbit-history-design.md</code> §3.7",
      "where": "the 1-per-1,000 design target, set before measurement"
    },
    {
      "ref": "3",
      "title": "<code>docs/orbit-browser-wiring.md</code>, 2026-09-08 and 2026-09-04 entries",
      "where": "the two-part gate, why significance was replaced by an effect size, the 2V ceiling, the allowlist, and the \"by construction\" correction"
    },
    {
      "ref": "4",
      "title": "<code>DETECTOR-DESIGN.md</code>, 2026-09-09",
      "where": "the characterisation of the passive tail: the inclination floor defect, the storm, gap, cross-tag and ramp measurements, the era strata and the κ ladder (1-in-25 / 1-in-75 sample of the archive)"
    },
    {
      "ref": "5",
      "title": "This site's published bundle of 12 September 2026 (<code>orbit-events-f0aee9b89f1c200f.json</code> → <code>controls</code>, <code>labelPolicy</code>, <code>groundTruth</code>, <code>maturity</code>, <code>eventsPublished</code>)",
      "where": "every bundle count on this page",
      "url": "/data/artifacts/orbit-events-f0aee9b89f1c200f.json"
    },
    {
      "ref": "6",
      "title": "NASA Glenn PIMS ISS reboost records",
      "where": "the on-board Δv the ground-truth comparison quotes"
    },
    {
      "ref": "7",
      "title": "Brown, Cai & DasGupta, \"Interval Estimation for a Binomial Proportion\", <em>Statistical Science</em> 16(2), 2001",
      "where": "why Jeffreys rather than Wald at small counts"
    },
    {
      "ref": "8",
      "title": "<code>pipeline/orbit_campaigns.py</code> (<code>control_rates_by_object</code>, <code>detect_object_events</code>) and <code>pipeline/orbit_release.py</code> (<code>_event_label_permitted</code>)",
      "where": "the gate as code. The code is the authority wherever this page has rotted"
    }
  ]
};
