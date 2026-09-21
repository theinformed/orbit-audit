import { learningCheck } from "./learning-checks";
import { evidenceBadge, evidenceGuide, type Evidence } from "./learning-evidence";
import { withLearningContents } from "./learning-sections";
/**
 * SATELLITE FUNDAMENTALS — Learning track 01, rebuilt as six chapters.
 *
 * Sean, 2026-08-21: "get an agent on the Satellite Fundamentals site. There is
 * no content in there whatsoever. That is one of the most important parts of
 * the site and it deserves a really solid treatment. We need all the
 * fundamentals, from the difference between the user, terminal, uplink, etc.
 * terminology, to orbits and Vmax and hohmann transfers to payloads and bus
 * and drag and interactions with solar wind and IMF and xrays and what they do
 * to satellites. We need it all."
 *
 * WHAT WAS HERE. `orbitLessons()` in src/content.ts: a hero and ten
 * `.lesson-card`s, each one kicker, one heading, ONE paragraph, and a
 * `.diagram` div. src/styles.css:1254 renders that div as a 180 px box of
 * radial glow whose entire contents are three to five words of monospace —
 * "GSO ⊃ geostationary", "4+ pseudoranges → x, y, z, clock". So the page was
 * ten summaries and ten placeholders that were never filled, which is exactly
 * why the owner says there is no content in it.
 *
 * The ten TOPICS were good bones and all ten survive, rewritten, inside the
 * chapters below. None was dropped. See CHAPTER_MAP at the foot of this file
 * for where each one landed — that map is asserted by the unit suite, so a
 * later edit cannot quietly lose one.
 *
 * THE SHAPE, and why it is this shape.
 *
 * It is the shape src/layer-pages.ts already uses, because these are two
 * halves of one learning system and a reader must not meet two different
 * navigation patterns inside one site: an INDEX of cards, each card a door,
 * each door opening a page that replaces the body and carries a way back.
 * The buttons are bound by ExplorerApp.mountSatelliteFundamentals() after this
 * markup is injected, for the same reason layer-pages binds its own: the
 * `[data-view]` sweep in main.ts runs once at start-up and cannot see a
 * button that did not exist yet.
 *
 * Six chapters rather than one scroll, because the owner has already ruled on
 * the sibling track that a "MOUNTAIN of text" on one page "looks just god
 * awful". Each chapter is one sitting.
 *
 * INSIDE A CHAPTER, prose is not allowed to run. The instruments are a term
 * grid, an equation card, a drawn figure, a numbers strip, and a "see it live"
 * recipe — and the longest single block any of them can hold is a few
 * sentences. tests/satellite-fundamentals.test.ts measures that rather than
 * trusting it.
 *
 * ACCURACY. Every constant, equation and figure below is either (a) computed
 * in this file's own arithmetic, recomputed independently by the unit suite
 * from the published constants, and therefore checkable; or (b) quoted from a
 * source listed at the foot of the chapter that uses it. Where the textbook
 * definition of a term and the way it is used on an operations floor differ,
 * both are given and the difference is marked — that difference is the part a
 * reader who works in this field will check first.
 *
 * NOTHING ON THIS PAGE IS A MEASUREMENT. Every figure here is a schematic
 * drawn from the geometry it describes, and every one says so with the same
 * chip the rest of the site uses. The measurements are on the globe, and the
 * "see it live" recipes are how a reader gets to them.
 */

import "./satellite-fundamentals.css";
import { worldOutlines } from "./data/world-outlines";
// Chapter 07 lives in its own module (it imports only its Chapter TYPE,
// so there is no runtime cycle); see the header comment there for why.
import { CH_INFERENCE } from "./orbit-inference";
import { CH_VERDICT } from "./orbit-verdict";
import { CH_COMPUTATION } from "./orbit-computation";

// ---------------------------------------------------------------------------
// CONSTANTS
//
// One place, published values, each with the document it comes from. Every
// number quoted anywhere in this module is derived from these and nothing
// else, so there is no second copy of Earth's gravitational parameter to drift
// away from the first.
// ---------------------------------------------------------------------------

/** Earth's gravitational parameter, km³/s². WGS-84 (NIMA TR8350.2, 3rd ed.). */
export const MU_EARTH = 398600.4418;
/** Earth's equatorial radius, km. WGS-84 semi-major axis a = 6378137 m. */
export const R_EARTH = 6378.137;
/** Second zonal harmonic. WGS-84/EGM96 DYNAMIC value J₂ = −√5·C̄₂,₀ = 1.0826267×10⁻³.
 *  Not the 1.0826300×10⁻³ geometric value also printed in TR8350.2 — orbit
 *  determination uses the dynamic one, and the difference shows up in the
 *  fourth significant figure of every regression rate below. */
export const J2 = 1.0826267e-3;
/** Mean sidereal day, SI seconds. IERS Conventions; 23 h 56 m 04.0905 s. */
export const SIDEREAL_DAY = 86164.0905;
/** Speed of light in vacuum, km/s. Exact by definition (SI, 1983). */
export const C_KM_S = 299792.458;
/** Standard gravity, m/s². Exact by definition (CGPM 1901). */
export const G0 = 9.80665;

/** Circular orbital speed at radius r (km), in km/s. */
export function circularSpeed(r: number): number {
  return Math.sqrt(MU_EARTH / r);
}

/** Orbital period for semi-major axis a (km), in seconds. */
export function orbitalPeriod(a: number): number {
  return 2 * Math.PI * Math.sqrt((a * a * a) / MU_EARTH);
}

/** Vis-viva: speed at radius r on an orbit of semi-major axis a. Both km. */
export function visViva(r: number, a: number): number {
  return Math.sqrt(MU_EARTH * (2 / r - 1 / a));
}

/** Geostationary radius, km: the a whose period is one sidereal day. */
export const GEO_RADIUS = Math.cbrt(MU_EARTH * (SIDEREAL_DAY / (2 * Math.PI)) ** 2);
/** Geostationary altitude above the WGS-84 equator, km. */
export const GEO_ALTITUDE = GEO_RADIUS - R_EARTH;

/**
 * A two-burn Hohmann transfer between circular orbits, worked in full.
 *
 * Returned rather than hard-coded because the numbers printed on the page are
 * these numbers: the unit suite calls this function with the same arguments
 * the page uses and compares against the strings the page renders, so a figure
 * on screen cannot drift from the formula that produced it.
 */
export function hohmann(r1: number, r2: number): {
  v1: number; vPerigee: number; burn1: number;
  vApogee: number; v2: number; burn2: number;
  total: number; transferHours: number; eccentricity: number;
} {
  const aTransfer = (r1 + r2) / 2;
  const v1 = circularSpeed(r1);
  const v2 = circularSpeed(r2);
  const vPerigee = visViva(r1, aTransfer);
  const vApogee = visViva(r2, aTransfer);
  return {
    v1, vPerigee, burn1: vPerigee - v1,
    vApogee, v2, burn2: v2 - vApogee,
    total: (vPerigee - v1) + (v2 - vApogee),
    transferHours: orbitalPeriod(aTransfer) / 2 / 3600,
    eccentricity: (r2 - r1) / (r2 + r1),
  };
}

/** Simple plane change of Δi degrees at speed v (km/s), in km/s. */
export function planeChange(v: number, deltaIncDeg: number): number {
  return 2 * v * Math.sin((deltaIncDeg * Math.PI) / 180 / 2);
}

/** A burn that changes speed and direction at once: law of cosines. */
export function combinedBurn(vFrom: number, vTo: number, deltaIncDeg: number): number {
  const di = (deltaIncDeg * Math.PI) / 180;
  return Math.sqrt(vFrom * vFrom + vTo * vTo - 2 * vFrom * vTo * Math.cos(di));
}

/** Propellant mass fraction required for Δv (km/s) at a given Isp (s). */
export function propellantFraction(deltaVKmS: number, ispSeconds: number): number {
  return 1 - Math.exp(-deltaVKmS / ((ispSeconds * G0) / 1000));
}

/**
 * Sun-synchronous inclination for a circular orbit at the given altitude.
 *
 * Sets the J₂ nodal regression rate equal to Earth's mean motion about the
 * Sun, 360°/365.2421897 d = 0.9856°/day, and solves for i.
 */
export function sunSynchronousInclination(altitudeKm: number): number {
  const a = R_EARTH + altitudeKm;
  const n = Math.sqrt(MU_EARTH / (a * a * a));
  const target = (2 * Math.PI) / 365.2421897 / 86400; // rad/s
  const cosI = -target / (1.5 * n * J2 * (R_EARTH / a) ** 2);
  return (Math.acos(cosI) * 180) / Math.PI;
}

/** Geometric radio-horizon half-angle seen from altitude h, in degrees. */
export function horizonHalfAngle(altitudeKm: number): number {
  return (Math.acos(R_EARTH / (R_EARTH + altitudeKm)) * 180) / Math.PI;
}

/** Fraction of Earth's surface inside that horizon, as a percentage. */
export function horizonSurfacePercent(altitudeKm: number): number {
  return ((1 - R_EARTH / (R_EARTH + altitudeKm)) / 2) * 100;
}

// ---------------------------------------------------------------------------
// PAGE MODEL
// ---------------------------------------------------------------------------

/** The chip classes that already have a treatment in src/styles.css. */

type Term = {
  term: string;
  /** The abbreviation, unit, or band an operator would actually say. */
  note?: string;
  /** One to three short sentences. Never a paragraph. */
  body: string;
  /**
   * Where the operational usage and the textbook definition part company.
   *
   * This field exists because it is the single most useful thing a page like
   * this can carry for someone who works in the field, and the thing most
   * reference pages get wrong by flattening.
   */
  operational?: string;
};

type Source = { ref: string; title: string; where: string; url?: string };

type Block =
  | { kind: "terms"; single?: boolean; items: Term[] }
  | {
      kind: "equation";
      name: string;
      tag: string;
      formula: string;
      where: { symbol: string; meaning: string }[];
      /** The number that comes out, and the assumptions it rests on. */
      worked?: string[];
    }
  | { kind: "figure"; svg: string; chip: Evidence; chipNote: string; caption: string }
  | { kind: "facts"; items: { value: string; caption: string }[] }
  | {
      kind: "live";
      body: string[];
      /** A door into the explorer or another track, by nav view name. */
      goto?: { label: string; view: string };
    };

type Section = { kicker: string; title: string; lead?: string; blocks: Block[] };

export type Chapter = {
  id: string;
  index: string;
  /** The name on the door and at the top of the chapter. */
  title: string;
  /** One sentence on the index card. */
  door: string;
  /** Two sentences at the top of the chapter itself. */
  lead: string;
  /** What is inside, printed on the door so a reader can choose. */
  covers: string[];
  sections: Section[];
  sources: Source[];
};

// ---------------------------------------------------------------------------
// RENDERERS
// ---------------------------------------------------------------------------

function chip(evidence: Evidence, label: string): string {
  return `${evidenceBadge(evidence)}`
    + `<small class="layer-status-note">${label}</small>`;
}

function renderTerms(block: Extract<Block, { kind: "terms" }>): string {
  const rows = block.items.map((item) => {
    const note = item.note ? `<small>${item.note}</small>` : "";
    const operational = item.operational
      ? `<span class="fund-operational"><b>On an operations floor</b>${item.operational}</span>`
      : "";
    return `<div><dt>${item.term}${note}</dt><dd>${item.body}${operational}</dd></div>`;
  }).join("");
  return `<dl class="fund-terms${block.single ? " is-single" : ""}">${rows}</dl>`;
}

function renderEquation(block: Extract<Block, { kind: "equation" }>): string {
  const where = block.where
    .map((row) => `<div><dt>${row.symbol}</dt><dd>${row.meaning}</dd></div>`)
    .join("");
  const worked = block.worked?.length
    ? `<div class="fund-worked"><b>Worked, with its assumptions</b>${block.worked.map((line) => `<p>${line}</p>`).join("")}</div>`
    : "";
  return `
    <div class="fund-equation">
      <div class="fund-equation-head"><strong>${block.name}</strong><span>${block.tag}</span></div>
      <pre class="fund-formula">${block.formula}</pre>
      <dl class="fund-where">${where}</dl>
      ${worked}
    </div>`;
}

function renderFigure(block: Extract<Block, { kind: "figure" }>): string {
  const end = block.svg.indexOf('</svg>') + 6;
  const diagram = block.svg.slice(0, end);
  const reading = block.svg.slice(end);
  // The SVG gets its own scroll box and the caption stays outside it.
  //
  // A 900-unit viewBox scaled into a 390 px phone renders an 11 px label at
  // 4.8 px, which is not a small diagram, it is an unreadable one. Below the
  // narrow breakpoint the figure therefore keeps a floor width and scrolls
  // sideways inside this element instead — the same treatment this project's
  // house rules give any wide table or code block. The page itself must never
  // scroll sideways, and a browser test asserts that at every viewport.
  return `
    <figure class="fund-figure">
      <div class="fund-figure-scroll" tabindex="0" role="group" aria-label="Diagram, scrolls sideways on a narrow screen">
      ${diagram}
      </div>
      <button type="button" class="figure-full-size" data-figure-enlarge aria-pressed="false">Enlarge diagram labels</button>
      ${reading}
      <figcaption class="fund-figcaption">
        <p class="layer-evidence">${chip(block.chip, block.chipNote)}</p>
        <p>${block.caption}</p>
      </figcaption>
    </figure>`;
}

/** Values stay readable without scaling the SVG or moving its true marks. */
function figureReading(title: string, rows: [string, string][], note: string): string {
  return `<section class="figure-reading"><h3>${title}</h3><dl>${rows.map(([name, value]) => `<div><dt>${name}</dt><dd>${value}</dd></div>`).join("")}</dl><p>${note}</p></section>`;
}

function renderFacts(block: Extract<Block, { kind: "facts" }>): string {
  return `<div class="processing-facts">${block.items
    .map((fact) => `<article><strong>${fact.value}</strong><span>${fact.caption}</span></article>`)
    .join("")}</div>`;
}

function renderLive(block: Extract<Block, { kind: "live" }>): string {
  const goto = block.goto
    ? `<button type="button" class="link-button" data-fundamentals-goto="${block.goto.view}">${block.goto.label}</button>`
    : "";
  return `<aside class="fund-live"><b>See it live in this explorer</b>${block.body
    .map((line) => `<p>${line}</p>`)
    .join("")}${goto}</aside>`;
}

function renderBlock(block: Block): string {
  switch (block.kind) {
    case "terms": return renderTerms(block);
    case "equation": return renderEquation(block);
    case "figure": return renderFigure(block);
    case "facts": return renderFacts(block);
    case "live": return renderLive(block);
  }
}

function renderSection(section: Section): string {
  return `
    <section class="fund-section">
      <span class="section-kicker">${section.kicker}</span>
      <h2>${section.title}</h2>
      ${section.lead ? `<p>${section.lead}</p>` : ""}
      ${section.blocks.map(renderBlock).join("")}
    </section>`;
}

function renderSources(chapter: Chapter): string {
  const items = chapter.sources.map((source) => {
    const link = source.url ? ` <a href="${source.url}" target="_blank" rel="noopener">${source.url}</a>` : "";
    return `<li id="fund-src-${chapter.id}-${source.ref}"><cite>${source.title}</cite> — ${source.where}.${link}</li>`;
  }).join("");
  return `
    <section class="fund-sources">
      <h2>Sources for this chapter</h2>
      <p>Every constant, equation and quoted figure above comes from one of these. Figures marked <em>worked</em> are computed in the page's own source module from the cited constants and recomputed independently by the test suite, so the arithmetic on the page and the arithmetic in the code cannot disagree.</p>
      <ol>${items}</ol>
    </section>`;
}

// ---------------------------------------------------------------------------
// FIGURES
//
// These replace the 180 px boxes of glow. Every one is inline SVG built from
// the geometry it describes; none is a photograph, a render or a data plot,
// so each carries the SCHEMATIC chip.
//
// Colours are literal hex rather than var(--cyan) because a CSS custom
// property inside an SVG *presentation attribute* is not reliably resolved,
// and a figure that silently loses its ink on one browser is worse than one
// that cannot follow a later palette change. They mirror :root in
// src/styles.css exactly; if that palette moves, these move with it by hand.
// ---------------------------------------------------------------------------

const INK = {
  cyan: "#29d4e3",
  cyanBright: "#5ce8f1",
  amber: "#f5c96a",
  coral: "#ff7b78",
  violet: "#a98cff",
  mint: "#76e6a5",
  line: "#7898a6",
  faint: "rgba(132,194,214,.12)",
  muted: "#8da8b3",
} as const;

/** Arrowhead definitions, one per ink, reused by every figure that needs one. */
function arrowDefs(id: string): string {
  const heads = [
    ["cyan", INK.cyan], ["amber", INK.amber], ["coral", INK.coral],
    ["mint", INK.mint], ["violet", INK.violet],
  ] as const;
  return `<defs>${heads.map(([name, colour]) => `
    <marker id="${id}-${name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="${colour}"></path>
    </marker>`).join("")}</defs>`;
}

/**
 * The end-to-end link, with every name Sean asked for on the thing it names.
 *
 * Two panels, because the two pairs of names answer two different questions
 * and the old drawing made them fight over one band of sky. The top panel is
 * the geometry: two earth stations, the spacecraft, four hops named by
 * DIRECTION, and the crosslink. The bottom strip regroups the same four hops
 * by JOB — forward and return drawn as whole paths, each visibly containing
 * one uplink and one downlink, which is the point readers most often miss.
 * Ink is semantic: amber = uplink, cyan = downlink, coral = forward,
 * mint = return, violet = crosslink; hardware is drawn in neutral ink so the
 * colour always means a signal, never a box.
 */
function figureLinkGeometry(): string {
  const S = INK.muted; // structure ink: hardware, not signals
  // One spacecraft, drawn once: a bus with a depth cue, solar wings on yoked
  // hinges tilted a few degrees toward the sun, and a nadir dish that visibly
  // points at Earth (the same crescent idiom as the gateway dish below). The
  // second satellite is this same drawing scaled down, so both read as the
  // same class of object; `sw` compensates stroke width for the group scale.
  const spacecraft = (sw: number): string => `
    <path d="M430 64 L438 56 L478 56 L470 64 Z" fill="none" stroke="${S}" stroke-width="${(1.2 * sw).toFixed(2)}"></path>
    <path d="M470 64 L478 56 L478 90 L470 98 Z" fill="none" stroke="${S}" stroke-width="${(1.2 * sw).toFixed(2)}"></path>
    <rect x="430" y="64" width="40" height="34" rx="2" fill="none" stroke="${S}" stroke-width="${(1.5 * sw).toFixed(2)}"></rect>
    <rect x="436" y="70" width="12" height="8" fill="none" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></rect>
    <line x1="430" y1="84" x2="470" y2="84" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
    <g transform="rotate(6 416 80)">
      <line x1="416" y1="80" x2="430" y2="80" stroke="${S}" stroke-width="${(1.2 * sw).toFixed(2)}"></line>
      <circle cx="416" cy="80" r="1.6" fill="${S}"></circle>
      <rect x="344" y="70" width="72" height="20" fill="none" stroke="${S}" stroke-width="${(1.2 * sw).toFixed(2)}"></rect>
      <line x1="362" y1="70" x2="362" y2="90" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
      <line x1="380" y1="70" x2="380" y2="90" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
      <line x1="398" y1="70" x2="398" y2="90" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
      <line x1="344" y1="80" x2="416" y2="80" stroke="${INK.line}" stroke-width="${(0.75 * sw).toFixed(2)}"></line>
    </g>
    <g transform="rotate(-6 486 80)">
      <line x1="478" y1="80" x2="486" y2="80" stroke="${S}" stroke-width="${(1.2 * sw).toFixed(2)}"></line>
      <circle cx="486" cy="80" r="1.6" fill="${S}"></circle>
      <rect x="486" y="70" width="72" height="20" fill="none" stroke="${S}" stroke-width="${(1.2 * sw).toFixed(2)}"></rect>
      <line x1="504" y1="70" x2="504" y2="90" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
      <line x1="522" y1="70" x2="522" y2="90" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
      <line x1="540" y1="70" x2="540" y2="90" stroke="${INK.line}" stroke-width="${(1 * sw).toFixed(2)}"></line>
      <line x1="486" y1="80" x2="558" y2="80" stroke="${INK.line}" stroke-width="${(0.75 * sw).toFixed(2)}"></line>
    </g>
    <path d="M437 108 Q450 95 463 108 Q450 101 437 108 Z" fill="${S}"></path>
    <line x1="450" y1="104" x2="450" y2="117" stroke="${S}" stroke-width="${(1.1 * sw).toFixed(2)}"></line>
    <circle cx="450" cy="119" r="2" fill="none" stroke="${S}" stroke-width="${(1.1 * sw).toFixed(2)}"></circle>`;
  return `
<svg viewBox="0 0 900 604" role="img" aria-label="A satellite link drawn end to end, in two panels. Top panel: a handheld user terminal on the left and a gateway dish on the right, one satellite above them with solar wings and a dish pointed at Earth, an uplink and a downlink at each end, and a dashed crosslink to a second satellite that never touches the ground. Bottom panel: the same four hops regrouped into two jobs. The forward link runs gateway to satellite to user terminal; the return link runs user terminal to satellite to gateway; each contains one uplink and one downlink.">
  ${arrowDefs("lnk")}

  <!-- Direction key -->
  <text x="40" y="26" class="fund-svg-small">NAMED BY DIRECTION</text>
  <text x="40" y="44" class="fund-svg-small"><tspan style="fill:${INK.amber};font-weight:600">UPLINK</tspan> = Earth → space · <tspan style="fill:${INK.cyan};font-weight:600">DOWNLINK</tspan> = space → Earth</text>
  <text x="40" y="60" class="fund-svg-small">every ground station has both</text>

  <!-- The satellite: bus, solar wings, nadir horn -->
  <text x="450" y="36" text-anchor="middle" class="fund-svg-num">SPACE SEGMENT</text>
  <text x="450" y="50" text-anchor="middle" class="fund-svg-small">payload + bus</text>
  <g>${spacecraft(1)}</g>

  <!-- Second satellite and the crosslink -->
  <text x="778" y="30" text-anchor="middle" class="fund-svg-small" style="fill:${INK.violet}">SECOND SATELLITE</text>
  <g transform="translate(553 17) scale(0.5)">${spacecraft(1.45)}</g>
  <line x1="564" y1="70" x2="719" y2="55" stroke="${INK.violet}" stroke-width="1.6" stroke-dasharray="7 4" marker-start="url(#lnk-violet)" marker-end="url(#lnk-violet)"></line>
  <text x="648" y="48" text-anchor="middle" style="fill:${INK.violet};font-weight:600">CROSSLINK / ISL</text>
  <text x="648" y="90" text-anchor="middle" class="fund-svg-small">never touches the ground</text>

  <!-- User side: the radio the user holds -->
  <g>
    <rect x="106" y="286" width="26" height="44" rx="4" fill="none" stroke="${S}" stroke-width="1.5"></rect>
    <rect x="111" y="293" width="16" height="11" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
    <line x1="111" y1="312" x2="127" y2="312" stroke="${INK.line}" stroke-width="1"></line>
    <line x1="111" y1="318" x2="127" y2="318" stroke="${INK.line}" stroke-width="1"></line>
    <line x1="111" y1="324" x2="127" y2="324" stroke="${INK.line}" stroke-width="1"></line>
    <line x1="126" y1="286" x2="136" y2="252" stroke="${S}" stroke-width="1.5"></line>
    <circle cx="136" cy="252" r="2" fill="${S}"></circle>
  </g>
  <text x="120" y="352" text-anchor="middle" class="fund-svg-num">USER TERMINAL</text>
  <text x="120" y="368" text-anchor="middle" class="fund-svg-small">the radio the user holds</text>

  <!-- Gateway side: a dish on a pedestal, aimed at the spacecraft -->
  <g>
    <g transform="translate(770 330) scale(1.35) translate(-770 -330)">
      <path d="M760 330 L768 296 M780 330 L768 296" fill="none" stroke="${S}" stroke-width="1.1"></path>
      <g transform="rotate(-40 762 288)">
        <path d="M738 288 Q762 308 786 288 Q762 296 738 288 Z" fill="${S}"></path>
        <line x1="762" y1="298" x2="762" y2="276" stroke="${S}" stroke-width="0.9"></line>
        <circle cx="762" cy="273" r="2.5" fill="none" stroke="${S}" stroke-width="0.9"></circle>
      </g>
    </g>
  </g>
  <text x="762" y="352" text-anchor="middle" class="fund-svg-num">GATEWAY / TELEPORT</text>
  <text x="762" y="368" text-anchor="middle" class="fund-svg-small">the operator's earth station</text>

  <!-- The four hops, named by direction, labels horizontal -->
  <line x1="142" y1="264" x2="420" y2="110" stroke="${INK.amber}" stroke-width="1.8" marker-end="url(#lnk-amber)"></line>
  <text x="252" y="188" text-anchor="middle" class="fund-svg-warm">UPLINK</text>
  <line x1="428" y1="124" x2="148" y2="284" stroke="${INK.cyan}" stroke-width="1.8" marker-end="url(#lnk-cyan)"></line>
  <line x1="296" y1="233" x2="288" y2="206" stroke="${INK.line}" stroke-width="1"></line>
  <text x="300" y="246" text-anchor="middle" class="fund-svg-key">DOWNLINK</text>

  <line x1="742" y1="272" x2="482" y2="112" stroke="${INK.amber}" stroke-width="1.8" marker-end="url(#lnk-amber)"></line>
  <text x="652" y="198" text-anchor="middle" class="fund-svg-warm">UPLINK</text>
  <line x1="474" y1="126" x2="726" y2="281" stroke="${INK.cyan}" stroke-width="1.8" marker-end="url(#lnk-cyan)"></line>
  <line x1="608" y1="235" x2="616" y2="214" stroke="${INK.line}" stroke-width="1"></line>
  <text x="600" y="248" text-anchor="middle" class="fund-svg-key">DOWNLINK</text>

  <!-- Ground -->
  <line x1="40" y1="330" x2="860" y2="330" stroke="${INK.line}" stroke-width="1"></line>
  <text x="450" y="346" text-anchor="middle" class="fund-svg-small">EARTH'S SURFACE</text>

  <!-- Lower strip: the same four hops, regrouped by job -->
  <line x1="40" y1="384" x2="860" y2="384" stroke="${INK.line}" stroke-width="1"></line>
  <text x="40" y="406" class="fund-svg-small">NAMED BY WHOSE TRAFFIC IT IS — the same four hops, regrouped into two jobs</text>

  <rect x="40" y="418" width="820" height="64" fill="${INK.coral}" opacity=".05"></rect>
  <rect x="40" y="418" width="820" height="64" fill="none" stroke="${INK.coral}" stroke-width="1.3"></rect>
  <text x="56" y="444" class="fund-svg-hot">FORWARD LINK</text>
  <text x="56" y="460" class="fund-svg-small">the network's traffic to the user</text>
  <rect x="288" y="432" width="130" height="28" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="353" y="450" text-anchor="middle">GATEWAY</text>
  <line x1="426" y1="446" x2="490" y2="446" stroke="${INK.amber}" stroke-width="1.6" marker-end="url(#lnk-amber)"></line>
  <text x="458" y="436" text-anchor="middle" class="fund-svg-small" style="fill:${INK.amber}">UPLINK</text>
  <rect x="498" y="432" width="130" height="28" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="563" y="450" text-anchor="middle">SATELLITE</text>
  <line x1="636" y1="446" x2="700" y2="446" stroke="${INK.cyan}" stroke-width="1.6" marker-end="url(#lnk-cyan)"></line>
  <text x="668" y="436" text-anchor="middle" class="fund-svg-small" style="fill:${INK.cyan}">DOWNLINK</text>
  <rect x="708" y="432" width="130" height="28" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="773" y="450" text-anchor="middle">USER TERMINAL</text>

  <rect x="40" y="496" width="820" height="64" fill="${INK.mint}" opacity=".05"></rect>
  <rect x="40" y="496" width="820" height="64" fill="none" stroke="${INK.mint}" stroke-width="1.3"></rect>
  <text x="56" y="522" style="fill:${INK.mint};font-weight:600">RETURN LINK</text>
  <text x="56" y="538" class="fund-svg-small">the user's traffic to the network</text>
  <rect x="288" y="510" width="130" height="28" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="353" y="528" text-anchor="middle">USER TERMINAL</text>
  <line x1="426" y1="524" x2="490" y2="524" stroke="${INK.amber}" stroke-width="1.6" marker-end="url(#lnk-amber)"></line>
  <text x="458" y="514" text-anchor="middle" class="fund-svg-small" style="fill:${INK.amber}">UPLINK</text>
  <rect x="498" y="510" width="130" height="28" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="563" y="528" text-anchor="middle">SATELLITE</text>
  <line x1="636" y1="524" x2="700" y2="524" stroke="${INK.cyan}" stroke-width="1.6" marker-end="url(#lnk-cyan)"></line>
  <text x="668" y="514" text-anchor="middle" class="fund-svg-small" style="fill:${INK.cyan}">DOWNLINK</text>
  <rect x="708" y="510" width="130" height="28" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="773" y="528" text-anchor="middle">GATEWAY</text>

  <text x="40" y="588" class="fund-svg-small">Each job contains one uplink and one downlink. “Which way is it going?” and “whose traffic is it?” are different questions.</text>
</svg>`;
}

/** What the satellite does with what it receives: the payload's one decision. */
function figurePayloadKinds(): string {
  return `
<svg viewBox="0 0 900 330" role="img" aria-label="Two payload architectures side by side. A bent-pipe transponder receives, filters, shifts frequency, amplifies and retransmits. A regenerative payload additionally demodulates to bits, routes them, and remodulates.">
  ${arrowDefs("pay")}
  <g>
    <text x="30" y="30" class="fund-svg-key">BENT PIPE — a transponder</text>
    <text x="30" y="48" class="fund-svg-small">the signal stays a signal from end to end</text>
    <rect x="30" y="66" width="840" height="78" fill="none" stroke="${INK.line}"></rect>
    ${["RECEIVE", "FILTER", "SHIFT ƒ", "AMPLIFY", "TRANSMIT"].map((label, i) => `
      <rect x="${48 + i * 166}" y="84" width="128" height="42" fill="none" stroke="${INK.cyan}" stroke-width="1.3"></rect>
      <text x="${112 + i * 166}" y="110" text-anchor="middle" class="fund-svg-key">${label}</text>
      ${i < 4 ? `<line x1="${176 + i * 166}" y1="105" x2="${212 + i * 166}" y2="105" stroke="${INK.cyan}" stroke-width="1.4" marker-end="url(#pay-cyan)"></line>` : ""}`).join("")}
    <text x="30" y="164" class="fund-svg-small">Noise picked up on the uplink is amplified along with the signal and arrives on the downlink. The satellite never learns what it is carrying.</text>
  </g>
  <g>
    <text x="30" y="214" style="fill:${INK.amber};font-weight:600">REGENERATIVE / PROCESSED — an on-board modem</text>
    <text x="30" y="232" class="fund-svg-small">the signal becomes bits on board, and starts again</text>
    <rect x="30" y="250" width="840" height="60" fill="none" stroke="${INK.line}"></rect>
    ${["RECEIVE", "DEMODULATE", "DECODE / ROUTE", "REMODULATE", "TRANSMIT"].map((label, i) => `
      <rect x="${48 + i * 166}" y="262" width="128" height="36" fill="none" stroke="${INK.amber}" stroke-width="1.3"></rect>
      <text x="${112 + i * 166}" y="285" text-anchor="middle" class="fund-svg-warm" style="font-size:10px">${label}</text>
      ${i < 4 ? `<line x1="${176 + i * 166}" y1="280" x2="${212 + i * 166}" y2="280" stroke="${INK.amber}" stroke-width="1.4" marker-end="url(#pay-amber)"></line>` : ""}`).join("")}
  </g>
</svg>`;
}

/**
 * The band ladder: one logarithmic frequency axis, the IEEE radar letters
 * above it, and what satellite people actually put in each band below.
 *
 * Drawn on a log axis because the letters are not equal-width and a linear
 * axis makes L band invisible beside Ka.
 */
function figureBandLadder(): string {
  const fMin = Math.log10(0.1); // 100 MHz
  const fMax = Math.log10(60);  // 60 GHz
  const x = (ghz: number) => 52 + ((Math.log10(ghz) - fMin) / (fMax - fMin)) * 800;
  const bands: { label: string; lo: number; hi: number }[] = [
    { label: "UHF", lo: 0.3, hi: 1 },
    { label: "L", lo: 1, hi: 2 },
    { label: "S", lo: 2, hi: 4 },
    { label: "C", lo: 4, hi: 8 },
    { label: "X", lo: 8, hi: 12 },
    { label: "Ku", lo: 12, hi: 18 },
    { label: "K", lo: 18, hi: 27 },
    { label: "Ka", lo: 27, hi: 40 },
    { label: "V", lo: 40, hi: 60 },
  ];
  const uses: { label: string; lo: number; hi: number; ink: string; row: number }[] = [
    { label: "military UHF SATCOM  0.24–0.32", lo: 0.24, hi: 0.32, ink: INK.coral, row: 0 },
    { label: "GNSS  1.16–1.61", lo: 1.16, hi: 1.61, ink: INK.mint, row: 1 },
    { label: "mobile satellite (Inmarsat, Iridium)  1.5–1.7", lo: 1.5, hi: 1.7, ink: INK.amber, row: 0 },
    { label: "C-band fixed satellite  3.4–6.7", lo: 3.4, hi: 6.7, ink: INK.cyan, row: 1 },
    { label: "military X-band  7.2–8.4", lo: 7.2, hi: 8.4, ink: INK.coral, row: 0 },
    { label: "Ku fixed + broadcast  10.7–14.5", lo: 10.7, hi: 14.5, ink: INK.cyan, row: 1 },
    { label: "Ka broadband  17.7–31", lo: 17.7, hi: 31, ink: INK.violet, row: 0 },
    { label: "V/Q feeder  37.5–51.4", lo: 37.5, hi: 51.4, ink: INK.violet, row: 1 },
  ];
  const ticks = [0.1, 0.3, 1, 3, 10, 30, 60];
  return `
<svg viewBox="0 0 900 376" role="img" aria-label="A logarithmic frequency axis from 100 megahertz to 60 gigahertz. Above it, the IEEE radar band letters UHF, L, S, C, X, Ku, K, Ka and V with their boundaries. Below it, the satellite services that actually occupy each region.">
  <text x="52" y="26" class="fund-svg-key">IEEE Std 521-2019 LETTER BANDS</text>
  ${bands.map((band) => `
    <rect x="${x(band.lo)}" y="40" width="${x(band.hi) - x(band.lo)}" height="34" fill="none" stroke="${INK.cyanBright}" stroke-width="1.2"></rect>
    <text x="${(x(band.lo) + x(band.hi)) / 2}" y="62" text-anchor="middle" class="fund-svg-num">${band.label}</text>`).join("")}
  <line x1="52" y1="104" x2="852" y2="104" stroke="${INK.line}" stroke-width="1.2"></line>
  ${ticks.map((tick) => `
    <line x1="${x(tick)}" y1="98" x2="${x(tick)}" y2="110" stroke="${INK.line}"></line>
    <text x="${x(tick)}" y="126" text-anchor="middle" class="fund-svg-small">${tick < 1 ? `${tick * 1000} MHz` : `${tick} GHz`}</text>`).join("")}
  <text x="52" y="160" class="fund-svg-warm">WHAT SATELLITE SERVICES ACTUALLY USE (GHz)</text>
  ${uses.map((use, i) => {
    const y = 178 + i * 22;
    const left = x(use.lo);
    const width = Math.max(3, x(use.hi) - x(use.lo));
    // Label to the right of the bar where it fits inside the frame, otherwise
    // to the left of it, right-aligned. Measured at 9.5 px IBM Plex Mono, one
    // character is about 5.5 px wide; a label placed without that check runs
    // straight over its own bar, which is what the first draft did.
    const runsOff = left + width + 8 + use.label.length * 5.5 > 856;
    return `
    <rect x="${left}" y="${y}" width="${width}" height="12" fill="${use.ink}" opacity=".26"></rect>
    <rect x="${left}" y="${y}" width="${width}" height="12" fill="none" stroke="${use.ink}" stroke-width="1"></rect>
    <text x="${runsOff ? left - 8 : left + width + 8}" y="${y + 10}" text-anchor="${runsOff ? "end" : "start"}" class="fund-svg-small" style="fill:${use.ink}">${use.label}</text>`;
  }).join("")}
  <text x="52" y="368" class="fund-svg-small">Wavelength runs the other way: 1 m at UHF, 2.5 cm at Ka. Antenna size, beam width, bandwidth and rain sensitivity all follow from that one fact.</text>
</svg>${figureReading("Read the bands and service ranges", [
  ...bands.map(b => [b.label, `${b.lo}–${b.hi} GHz`] as [string, string]),
  ...uses.map(u => [u.label, `${u.lo}–${u.hi} GHz`] as [string, string]),
], "The axis is logarithmic. Letter bands and service allocations are different schemes. Service ranges are approximate; they do not authorise a frequency assignment.")}`;
}

/**
 * The ellipse: the elements that shape it, and the speeds around it.
 *
 * Drawn true, and the caption's numbers are the drawing's numbers: e = 0.74
 * (a Molniya orbit's), Earth at the focus the geometry puts it at, the true
 * anomaly measured from the perigee direction — the first draft measured it
 * from apogee, which is exactly the mistake the label exists to prevent —
 * and the two speed arrows sharing one scale, so the (1+e)/(1−e) ratio is
 * visible rather than asserted. Perigee sits on the right, as the standard
 * orbital-elements diagram draws it.
 */
function figureEllipse(): string {
  const a = 300;
  const e = 0.74;
  const b = a * Math.sqrt(1 - e * e); // 201.8
  const c = a * e; // 222
  const cx = 450;
  const cy = 215;
  const focusX = cx + c; // Earth, at the right-hand focus: 672
  // Spacecraft at true anomaly 60°: r = a(1−e²)/(1+e·cos ν).
  const nu = 60 * (Math.PI / 180);
  const r = (a * (1 - e * e)) / (1 + e * Math.cos(nu)); // 99.1
  const scX = focusX + r * Math.cos(nu); // 721.5
  const scY = cy - r * Math.sin(nu); // 129.2
  // Speed arrows to one scale: v_perigee / v_apogee = (1+e)/(1−e) = 6.69.
  const ratio = (1 + e) / (1 - e);
  const perigeeArrow = 67;
  const apogeeArrow = perigeeArrow / ratio; // 10.0
  return `
<svg viewBox="0 0 900 458" role="img" aria-label="An elliptical orbit of eccentricity 0.74 with Earth at the right-hand focus and the empty focus marked on the left. Perigee is at the right, apogee at the left, each with a speed arrow drawn to the same scale — the perigee arrow is 6.7 times longer. The semi-major axis is measured from the centre to a vertex, and the true anomaly of the spacecraft is drawn at the occupied focus, measured from the perigee direction.">
  ${arrowDefs("ell")}
  <ellipse cx="${cx}" cy="${cy}" rx="${a}" ry="${b.toFixed(1)}" fill="none" stroke="${INK.cyanBright}" stroke-width="1.8"></ellipse>
  <line x1="${cx - a}" y1="${cy}" x2="${cx + a}" y2="${cy}" stroke="${INK.line}" stroke-dasharray="5 5"></line>

  <!-- Earth at the occupied focus -->
  <circle cx="${focusX}" cy="${cy}" r="24" fill="none" stroke="${INK.mint}" stroke-width="1.6"></circle>
  <circle cx="${focusX}" cy="${cy}" r="3" fill="${INK.mint}"></circle>
  <text x="${focusX}" y="290" text-anchor="middle" style="fill:${INK.mint};font-weight:600">EARTH</text>
  <text x="${focusX}" y="306" text-anchor="middle" class="fund-svg-small">at ONE focus</text>

  <!-- The empty focus, and the semi-major axis measured centre to vertex -->
  <line x1="${cx - a}" y1="${cy}" x2="${cx}" y2="${cy}" stroke="${INK.violet}" stroke-width="1.4" marker-start="url(#ell-violet)" marker-end="url(#ell-violet)"></line>
  <line x1="${cx}" y1="${cy - 7}" x2="${cx}" y2="${cy + 7}" stroke="${INK.muted}" stroke-width="1.2"></line>
  <text x="${cx}" y="${cy + 21}" text-anchor="middle" class="fund-svg-small">centre</text>
  <text x="300" y="${cy + 27}" text-anchor="middle" style="fill:${INK.violet};font-weight:600">a — semi-major axis</text>
  <text x="300" y="${cy + 43}" text-anchor="middle" class="fund-svg-small">sets the PERIOD, and nothing else does</text>
  <circle cx="${cx - c}" cy="${cy}" r="3.5" fill="none" stroke="${INK.muted}" stroke-width="1.2"></circle>
  <text x="${cx - c}" y="${cy - 29}" text-anchor="middle" class="fund-svg-small">empty focus —</text>
  <text x="${cx - c}" y="${cy - 15}" text-anchor="middle" class="fund-svg-small">nothing is there</text>

  <!-- Apogee, left, with the smaller speed arrow -->
  <circle cx="${cx - a}" cy="${cy}" r="6" fill="${INK.amber}"></circle>
  <text x="${cx - a - 8}" y="${cy - 23}" text-anchor="end" class="fund-svg-warm">APOGEE</text>
  <text x="${cx - a - 8}" y="${cy - 8}" text-anchor="end" class="fund-svg-small">furthest · SLOWEST</text>
  <line x1="${cx - a}" y1="${cy + 8}" x2="${cx - a}" y2="${(cy + 8 + apogeeArrow).toFixed(1)}" stroke="${INK.amber}" stroke-width="2.4" marker-end="url(#ell-amber)"></line>
  <text x="${cx - a - 8}" y="${cy + 55}" text-anchor="end" class="fund-svg-warm">v is smallest here</text>

  <!-- Perigee, right, with the larger arrow: same scale, so the ratio shows -->
  <circle cx="${cx + a}" cy="${cy}" r="6" fill="${INK.coral}"></circle>
  <text x="${cx + a + 8}" y="${cy + 25}" class="fund-svg-hot">PERIGEE</text>
  <text x="${cx + a + 8}" y="${cy + 40}" class="fund-svg-small">closest · FASTEST</text>
  <line x1="${cx + a}" y1="${cy - 8}" x2="${cx + a}" y2="${(cy - 8 - perigeeArrow).toFixed(1)}" stroke="${INK.coral}" stroke-width="2.4" marker-end="url(#ell-coral)"></line>
  <text x="856" y="78" text-anchor="end" class="fund-svg-hot">v is largest here</text>
  <text x="856" y="92" text-anchor="end" class="fund-svg-small">${ratio.toFixed(1)}× the apogee speed</text>

  <!-- The spacecraft: radius from the occupied focus, ν from perigee -->
  <circle cx="${scX.toFixed(1)}" cy="${scY.toFixed(1)}" r="5" fill="${INK.cyanBright}"></circle>
  <text x="733" y="124" class="fund-svg-small">spacecraft</text>
  <line x1="${focusX}" y1="${cy}" x2="${scX.toFixed(1)}" y2="${scY.toFixed(1)}" stroke="${INK.cyan}" stroke-width="1.3"></line>
  <text x="640" y="170" text-anchor="end" class="fund-svg-key">r — the radius right now</text>
  <line x1="648" y1="166" x2="699" y2="163" stroke="${INK.line}" stroke-width="1"></line>
  <path d="M ${focusX + 40} ${cy} A 40 40 0 0 0 ${(focusX + 40 * Math.cos(nu)).toFixed(1)} ${(cy - 40 * Math.sin(nu)).toFixed(1)}" fill="none" stroke="${INK.cyan}" stroke-width="1.2"></path>
  <text x="716" y="192" class="fund-svg-key">ν</text>
  <text x="600" y="256" text-anchor="middle" class="fund-svg-key">ν — true anomaly</text>
  <text x="600" y="272" text-anchor="middle" class="fund-svg-small">measured from perigee, in the direction of flight</text>

  <text x="450" y="446" text-anchor="middle" class="fund-svg-small">e — eccentricity — decides how far these two ends are apart. e = 0 is a circle, and then every speed on this page is the same speed.</text>
</svg>`;
}

/**
 * The altitude ladder. Log scale, because LEO and GEO cannot share a linear
 * axis without one of them becoming a line.
 *
 * Each occupant is one line of text tied to its rung by a dot and, where the
 * log scale squeezes the LEO rungs closer than a line of type, a short
 * leader — the rungs stay at their true heights and the labels give way, not
 * the other way round. The belts are drawn as what they are: two of them,
 * the inner proton belt LEO transfers climb through, and the outer electron
 * belt that GNSS lives inside and GEO grazes.
 */
function figureAltitudeLadder(): string {
  const lo = Math.log10(150);
  const hi = Math.log10(50000);
  const y = (km: number) => 380 - ((Math.log10(km) - lo) / (hi - lo)) * 320;
  const marks: { km: number; label: string; note: string; ink: string; textY: number }[] = [
    { km: 400, label: "ISS · 400 km", note: "7.669 km/s · 92.6 min · reboosted, or it comes down", ink: INK.mint, textY: 340 },
    { km: 550, label: "Starlink shell · 550 km", note: "7.585 km/s · 95.6 min · low enough to clear itself", ink: INK.cyan, textY: 322 },
    { km: 700, label: "sun-synchronous imaging · ~700 km", note: `i = ${sunSynchronousInclination(700).toFixed(2)}° · same local solar time every pass`, ink: INK.cyan, textY: 291 },
    { km: 20183, label: "GNSS · 20,184 km", note: "3.874 km/s · 11 h 58 m · two orbits per sidereal day", ink: INK.violet, textY: 106 },
    { km: 35786, label: "GEO · 35,786 km", note: "3.075 km/s · 23 h 56 m 04 s · one orbit per sidereal day", ink: INK.amber, textY: 73 },
  ];
  return `
<svg viewBox="0 0 900 430" role="img" aria-label="A logarithmic altitude ladder from 150 kilometres to 50,000 kilometres. Low Earth orbit reaches 2,000 kilometres and holds the ISS, the Starlink shell and sun-synchronous imagers. The inner proton belt sits roughly between 1,000 and 6,000 kilometres, the outer electron belt roughly between 13,000 and 45,000 — with the GNSS shell inside it and geostationary orbit near its outer edge.">
  <line x1="230" y1="52" x2="230" y2="380" stroke="${INK.line}" stroke-width="1.2"></line>
  ${[150, 500, 2000, 10000, 35786, 50000].map((tick) => `
    <line x1="224" y1="${y(tick).toFixed(1)}" x2="236" y2="${y(tick).toFixed(1)}" stroke="${INK.line}"></line>
    <text x="216" y="${(y(tick) + 4).toFixed(1)}" text-anchor="end" class="fund-svg-small">${tick.toLocaleString("en-GB")} km</text>`).join("")}

  <rect x="240" y="${y(2000).toFixed(1)}" width="620" height="${(y(150) - y(2000)).toFixed(1)}" fill="${INK.cyan}" opacity=".07"></rect>
  <text x="852" y="256" text-anchor="end" class="fund-svg-key">LOW EARTH ORBIT — surface to 2,000 km</text>
  <text x="852" y="270" text-anchor="end" class="fund-svg-small">where drag lives, and where the debris rules bite</text>

  <rect x="240" y="${y(6000).toFixed(1)}" width="620" height="${(y(1000) - y(6000)).toFixed(1)}" fill="${INK.coral}" opacity=".07"></rect>
  <text x="852" y="210" text-anchor="end" class="fund-svg-hot">INNER BELT — protons — roughly 1,000–6,000 km</text>
  <text x="852" y="225" text-anchor="end" class="fund-svg-small">a transfer climbs through it; nothing parks in it by choice</text>

  <rect x="240" y="${y(45000).toFixed(1)}" width="620" height="${(y(13000) - y(45000)).toFixed(1)}" fill="${INK.coral}" opacity=".07"></rect>
  <text x="852" y="95" text-anchor="end" class="fund-svg-hot">OUTER BELT — electrons — roughly 13,000–45,000 km</text>
  <text x="852" y="126" text-anchor="end" class="fund-svg-small">it swells and shrinks with the driving; GNSS lives inside it, GEO grazes its edge</text>

  ${marks.map((mark) => {
    const rungY = y(mark.km);
    const needsLeader = Math.abs(mark.textY - 4 - rungY) > 9;
    return `
    <line x1="240" y1="${rungY.toFixed(1)}" x2="860" y2="${rungY.toFixed(1)}" stroke="${mark.ink}" stroke-width="1.3" stroke-dasharray="4 4"></line>
    <circle cx="240" cy="${rungY.toFixed(1)}" r="4" fill="${mark.ink}"></circle>
    ${needsLeader ? `<line x1="246" y1="${rungY.toFixed(1)}" x2="246" y2="${(mark.textY - 4).toFixed(1)}" stroke="${mark.ink}" stroke-width="1" opacity=".7"></line>` : ""}
    <text x="252" y="${mark.textY}"><tspan style="fill:${mark.ink};font-weight:600">${mark.label}</tspan><tspan class="fund-svg-small" dx="8">${mark.note}</tspan></text>`;
  }).join("")}
  <text x="30" y="30" class="fund-svg-small">Every speed and period on this ladder is computed from the same two constants: μ = 398,600.4418 km³/s² and R⊕ = 6,378.137 km.</text>
  <text x="30" y="412" class="fund-svg-small">Altitude is above the WGS-84 equatorial radius. The vertical axis is logarithmic — GEO is not four times higher than the ISS, it is ninety times.</text>
</svg>${figureReading("Read the altitude ladder", marks.map(m => [m.label, m.note]),
  "Altitude is above the WGS-84 equatorial radius; the vertical axis is logarithmic. Inner belt roughly 1,000–6,000 km; outer belt roughly 13,000–45,000 km. These are illustrative ranges, not fixed measured boundaries.")}`;
}

/**
 * Why successive passes land west of the last one.
 *
 * Drawn as a real equirectangular map — the vendored Natural Earth coastlines,
 * clipped to ±62° — with four successive passes of a 400 km, 51.6° track
 * computed point by point from the orbital period, Earth's rotation
 * subtracted. The first draft drew four sinusoids marching EAST across an
 * empty frame, with one pass-width standing in for 23.2° of longitude: the
 * one thing the caption promises — the westward march — was the one thing
 * the drawing did not show.
 */
function figureGroundTrack(): string {
  const inclinationDeg = 51.6;
  const periodS = orbitalPeriod(R_EARTH + 400);
  const periodMin = periodS / 60;
  const shiftDeg = 360 * (periodS / SIDEREAL_DAY);
  const shiftKm = shiftDeg * ((2 * Math.PI * R_EARTH) / 360);
  // Frame: all 360° of longitude, latitude clipped at ±62° so the ±51.6°
  // peaks keep some air. Equirectangular: one px-per-degree both ways.
  const left = 60;
  const width = 800;
  const latMax = 62;
  const pxPerDeg = width / 360;
  const top = 46;
  const bottom = top + 2 * latMax * pxPerDeg;
  const px = (lon: number) => left + (lon + 180) * pxPerDeg;
  const py = (lat: number) => top + (latMax - lat) * pxPerDeg;
  const rad = Math.PI / 180;
  const inc = inclinationDeg * rad;
  // Land, decoded once and cached by world-outlines. Points closer than a
  // pixel to the last kept point are dropped: at 800 px for the whole world
  // most of the 1:110m detail is sub-pixel and would only bloat the page.
  const land = worldOutlines().land.map((outline) => {
    const commands: string[] = [];
    let keptX = NaN;
    let keptY = NaN;
    for (const [lon, lat] of outline) {
      const x = px(lon);
      const y = py(Math.max(-latMax, Math.min(latMax, lat)));
      if (commands.length > 0 && Math.abs(x - keptX) + Math.abs(y - keptY) < 1.1) continue;
      commands.push(`${commands.length === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
      keptX = x;
      keptY = y;
    }
    return commands.length > 2 ? `<path d="${commands.join("")}Z"></path>` : "";
  }).join("");
  // One pass. u is the argument of latitude — uniform in time on a circular
  // orbit — and longitude is the in-plane angle projected onto the equator
  // minus what Earth rotated in the elapsed fraction of the period. Split
  // into segments where the track crosses the date line.
  const firstNodeLon = 40;
  const nodeLon = (k: number) => firstNodeLon - k * shiftDeg;
  const passPath = (k: number): string => {
    let segment: string[] = [];
    const segments: string[][] = [segment];
    let previousLon = 0;
    for (let u = 0; u <= 360; u += 2) {
      const latitude = Math.asin(Math.sin(inc) * Math.sin(u * rad)) / rad;
      let lonRel = Math.atan2(Math.cos(inc) * Math.sin(u * rad), Math.cos(u * rad)) / rad;
      if (u > 180) lonRel += 360;
      const lon = nodeLon(k) + lonRel - shiftDeg * (u / 360);
      const wrapped = ((((lon + 180) % 360) + 360) % 360) - 180;
      if (u > 0 && Math.abs(wrapped - previousLon) > 180) {
        segment = [];
        segments.push(segment);
      }
      segment.push(`${px(wrapped).toFixed(1)},${py(latitude).toFixed(1)}`);
      previousLon = wrapped;
    }
    return segments.filter((s) => s.length > 1).map((s) => `M${s.join(" L")}`).join(" ");
  };
  // The peak of pass k, for its label: u = 90°, a quarter period in.
  const peakLon = (k: number) => nodeLon(k) + 90 - shiftDeg / 4;
  // A short arrowhead riding pass 1 to show the direction of flight.
  const dirAt = (u: number): [number, number] => {
    const latitude = Math.asin(Math.sin(inc) * Math.sin(u * rad)) / rad;
    const lonRel = Math.atan2(Math.cos(inc) * Math.sin(u * rad), Math.cos(u * rad)) / rad;
    return [px(nodeLon(0) + lonRel - shiftDeg * (u / 360)), py(latitude)];
  };
  const [dirX1, dirY1] = dirAt(44);
  const [dirX2, dirY2] = dirAt(50);
  const lonTicks = [-180, -120, -60, 0, 60, 120, 180];
  const lonLabel = (lon: number) => (lon === 0 ? "0°" : Math.abs(lon) === 180 ? "180°" : `${Math.abs(lon)}°${lon < 0 ? "W" : "E"}`);
  const nodeInks = [INK.cyanBright, INK.cyan, INK.cyan, INK.cyan];
  return `
<svg viewBox="0 0 900 392" role="img" aria-label="An equirectangular world map with real coastlines and four successive ground tracks of a 400 kilometre, 51.6 degree orbit, computed from the orbital period. The tracks run eastward and peak at 51.6 degrees each way. Each pass crosses the equator northbound 23.2 degrees of longitude west of the pass before, marked by an arrow between the first two crossings, because Earth turned that far underneath the orbit.">
  ${arrowDefs("gt")}
  <text x="60" y="30" class="fund-svg-key">The orbit did not move. Earth turned ${shiftDeg.toFixed(2)}° during the ${periodMin.toFixed(2)} minutes the spacecraft took to come round.</text>
  <clipPath id="gt-frame"><rect x="${left}" y="${top}" width="${width}" height="${(bottom - top).toFixed(1)}"></rect></clipPath>
  <g clip-path="url(#gt-frame)" fill="${INK.faint}">${land}</g>
  <rect x="${left}" y="${top}" width="${width}" height="${(bottom - top).toFixed(1)}" fill="none" stroke="${INK.line}"></rect>
  <line x1="${left}" y1="${py(0).toFixed(1)}" x2="${left + width}" y2="${py(0).toFixed(1)}" stroke="${INK.line}"></line>
  <line x1="${left}" y1="${py(inclinationDeg).toFixed(1)}" x2="${left + width}" y2="${py(inclinationDeg).toFixed(1)}" stroke="${INK.line}" stroke-dasharray="3 5" opacity=".6"></line>
  <line x1="${left}" y1="${py(-inclinationDeg).toFixed(1)}" x2="${left + width}" y2="${py(-inclinationDeg).toFixed(1)}" stroke="${INK.line}" stroke-dasharray="3 5" opacity=".6"></line>
  <text x="52" y="${(py(inclinationDeg) + 4).toFixed(1)}" text-anchor="end" class="fund-svg-small">+51.6°</text>
  <text x="52" y="${(py(0) + 4).toFixed(1)}" text-anchor="end" class="fund-svg-small">0°</text>
  <text x="52" y="${(py(-inclinationDeg) + 4).toFixed(1)}" text-anchor="end" class="fund-svg-small">−51.6°</text>
  ${lonTicks.map((lon) => `
  <line x1="${px(lon).toFixed(1)}" y1="${bottom.toFixed(1)}" x2="${px(lon).toFixed(1)}" y2="${(bottom + 5).toFixed(1)}" stroke="${INK.line}"></line>
  <text x="${px(lon).toFixed(1)}" y="${(bottom + 18).toFixed(1)}" text-anchor="middle" class="fund-svg-small">${lonLabel(lon)}</text>`).join("")}
  <g clip-path="url(#gt-frame)">
  ${[0, 1, 2, 3].map((k) => `<path d="${passPath(k)}" fill="none" stroke="${k === 0 ? INK.cyanBright : INK.cyan}" stroke-width="${k === 0 ? 2 : 1.4}" opacity="${1 - k * 0.2}"></path>`).join("")}
  </g>
  <line x1="${dirX1.toFixed(1)}" y1="${dirY1.toFixed(1)}" x2="${dirX2.toFixed(1)}" y2="${dirY2.toFixed(1)}" stroke="${INK.cyanBright}" stroke-width="2" marker-end="url(#gt-cyan)"></line>
  <text x="${(dirX2 + 10).toFixed(1)}" y="${(dirY2 + 12).toFixed(1)}" class="fund-svg-small">direction of flight</text>
  ${[0, 1, 2, 3].map((k) => `
  <circle cx="${px(nodeLon(k)).toFixed(1)}" cy="${py(0).toFixed(1)}" r="3.5" fill="${nodeInks[k]}" opacity="${1 - k * 0.15}"></circle>
  <text x="${px(peakLon(k)).toFixed(1)}" y="${(py(inclinationDeg) - 8).toFixed(1)}" text-anchor="middle" class="fund-svg-small" style="${k === 0 ? `fill:${INK.cyanBright};font-weight:600` : ""}">pass ${k + 1}</text>`).join("")}
  <line x1="${px(nodeLon(0)).toFixed(1)}" y1="${(py(0) + 5).toFixed(1)}" x2="${px(nodeLon(0)).toFixed(1)}" y2="352" stroke="${INK.line}" stroke-dasharray="3 3"></line>
  <line x1="${px(nodeLon(1)).toFixed(1)}" y1="${(py(0) + 5).toFixed(1)}" x2="${px(nodeLon(1)).toFixed(1)}" y2="352" stroke="${INK.line}" stroke-dasharray="3 3"></line>
  <line x1="${px(nodeLon(0)).toFixed(1)}" y1="346" x2="${(px(nodeLon(1)) + 2).toFixed(1)}" y2="346" stroke="${INK.amber}" stroke-width="1.4" marker-end="url(#gt-amber)"></line>
  <text x="${((px(nodeLon(0)) + px(nodeLon(1))) / 2).toFixed(1)}" y="370" text-anchor="middle" class="fund-svg-warm">${shiftDeg.toFixed(2)}° west per orbit = ${Math.round(shiftKm).toLocaleString("en-GB")} km at the equator</text>
  <text x="64" y="${(py(inclinationDeg) - 8).toFixed(1)}" class="fund-svg-small">peaks at i = ${inclinationDeg}°</text>
</svg>`;
}

/** The Hohmann transfer, with the numbers this module computes for it. */
function figureHohmann(): string {
  const transfer = hohmann(R_EARTH + 400, GEO_RADIUS);
  const f = (value: number) => value.toFixed(3);
  return `
<svg viewBox="0 0 900 428" role="img" aria-label="A Hohmann transfer from a 400 kilometre circular orbit to geostationary orbit. A first burn at perigee raises apogee to geostationary radius; a coast of 5.29 hours follows; a second burn at apogee circularises. Both burn arrows point along the direction of travel.">
  ${arrowDefs("hoh")}
  <circle cx="250" cy="210" r="22" fill="none" stroke="${INK.mint}" stroke-width="1.5"></circle>
  <text x="250" y="214" text-anchor="middle" style="fill:${INK.mint};font-weight:600">EARTH</text>
  <circle cx="250" cy="210" r="40" fill="none" stroke="${INK.cyanBright}" stroke-width="1.8"></circle>
  <text x="280" y="122" text-anchor="middle" class="fund-svg-key">400 km circular</text>
  <text x="280" y="136" text-anchor="middle" class="fund-svg-small">${f(transfer.v1)} km/s</text>
  <line x1="280" y1="141" x2="258" y2="164" stroke="${INK.line}" stroke-width="1"></line>
  <circle cx="250" cy="210" r="176" fill="none" stroke="${INK.amber}" stroke-width="1.6"></circle>
  <text x="250" y="18" text-anchor="middle" class="fund-svg-warm">GEO — 35,786 km — ${f(transfer.v2)} km/s</text>
  <!-- the transfer ellipse: perigee at the small circle, apogee at the big one -->
  <ellipse cx="182" cy="210" rx="108" ry="86" fill="none" stroke="${INK.coral}" stroke-width="1.8" stroke-dasharray="6 4"></ellipse>
  <text x="120" y="210" text-anchor="middle" class="fund-svg-hot">transfer</text>
  <text x="120" y="226" text-anchor="middle" class="fund-svg-hot">ellipse</text>
  <text x="120" y="242" text-anchor="middle" class="fund-svg-small">e = ${transfer.eccentricity.toFixed(3)}</text>

  <!-- Burns drawn along the velocity: tangent to the orbit, not radial.
       At the rightmost point of a counter-clockwise orbit the velocity is
       straight up; at the leftmost, straight down. -->
  <line x1="290" y1="204" x2="290" y2="158" stroke="${INK.coral}" stroke-width="2.6" marker-end="url(#hoh-coral)"></line>
  <line x1="74" y1="216" x2="74" y2="262" stroke="${INK.amber}" stroke-width="2.6" marker-end="url(#hoh-amber)"></line>

  <g>
    <rect x="420" y="46" width="450" height="106" fill="none" stroke="${INK.coral}" stroke-width="1.2"></rect>
    <text x="440" y="72" class="fund-svg-hot">BURN 1 — at perigee, along the velocity</text>
    <text x="440" y="94" class="fund-svg-num">${f(transfer.vPerigee)} − ${f(transfer.v1)} = ${f(transfer.burn1)} km/s</text>
    <text x="440" y="116" class="fund-svg-small">Raises apogee from 400 km to geostationary radius.</text>
    <text x="440" y="134" class="fund-svg-small">Nothing about the plane or the perigee changes.</text>
  </g>
  <g>
    <rect x="420" y="166" width="450" height="66" fill="none" stroke="${INK.line}"></rect>
    <text x="440" y="192" class="fund-svg-key">COAST — half the transfer ellipse</text>
    <text x="440" y="216" class="fund-svg-num">${transfer.transferHours.toFixed(2)} hours</text>
  </g>
  <g>
    <rect x="420" y="246" width="450" height="106" fill="none" stroke="${INK.amber}" stroke-width="1.2"></rect>
    <text x="440" y="272" class="fund-svg-warm">BURN 2 — at apogee, along the velocity</text>
    <text x="440" y="294" class="fund-svg-num">${f(transfer.v2)} − ${f(transfer.vApogee)} = ${f(transfer.burn2)} km/s</text>
    <text x="440" y="316" class="fund-svg-small">Without it the spacecraft falls back to a 400 km perigee</text>
    <text x="440" y="334" class="fund-svg-small">every 10.5 hours, forever. The second burn is the orbit.</text>
  </g>
  <text x="440" y="382" class="fund-svg-num">TOTAL ${f(transfer.total)} km/s</text>
  <text x="440" y="400" class="fund-svg-small">Ideal, impulsive, coplanar, two-body.</text>
  <text x="440" y="416" class="fund-svg-small">A real launch adds the plane change — see below.</text>
</svg>`;
}

/** Payload and bus: what a satellite is for, and what carries it. */
function figurePayloadBus(): string {
  const subsystems: { name: string; job: string }[] = [
    { name: "STRUCTURE", job: "holds it together through launch" },
    { name: "POWER (EPS)", job: "arrays, batteries, regulation" },
    { name: "THERMAL", job: "radiators, heaters, coatings" },
    { name: "ADCS / GNC", job: "knows and controls where it points" },
    { name: "PROPULSION", job: "the only thing that changes the orbit" },
    { name: "C&DH", job: "the computer, and the data bus" },
    { name: "TT&C", job: "the link that flies the spacecraft" },
    { name: "MECHANISMS", job: "deploys arrays, antennas, covers" },
  ];
  return `
<svg viewBox="0 0 900 340" role="img" aria-label="A spacecraft divided into payload and bus. The payload is the reason for the mission. The bus is eight subsystems that keep the payload alive, pointed, powered and in contact.">
  <rect x="40" y="46" width="300" height="256" fill="${INK.amber}" opacity=".07"></rect>
  <rect x="40" y="46" width="300" height="256" fill="none" stroke="${INK.amber}" stroke-width="1.5"></rect>
  <text x="60" y="76" class="fund-svg-warm">PAYLOAD</text>
  <text x="60" y="96" class="fund-svg-small">The reason the mission exists.</text>
  <text x="60" y="132" class="fund-svg-num">transponders and antennas</text>
  <text x="60" y="154" class="fund-svg-num">an imager or a radar</text>
  <text x="60" y="176" class="fund-svg-num">a navigation clock</text>
  <text x="60" y="198" class="fund-svg-num">a science instrument</text>
  <text x="60" y="236" class="fund-svg-small">Change the payload and you have a</text>
  <text x="60" y="252" class="fund-svg-small">different mission on the same bus.</text>
  <text x="60" y="276" class="fund-svg-small">This is what the customer buys.</text>

  <rect x="380" y="46" width="480" height="256" fill="none" stroke="${INK.cyanBright}" stroke-width="1.5"></rect>
  <text x="400" y="76" class="fund-svg-key">BUS — the platform</text>
  <text x="400" y="96" class="fund-svg-small">Everything the payload needs in order to work at all.</text>
  ${subsystems.map((subsystem, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 400 + col * 232;
    const yy = 122 + row * 44;
    return `<rect x="${x}" y="${yy}" width="216" height="34" fill="none" stroke="${INK.line}"></rect>
      <text x="${x + 10}" y="${yy + 15}" class="fund-svg-key" style="font-size:10px">${subsystem.name}</text>
      <text x="${x + 10}" y="${yy + 28}" class="fund-svg-small">${subsystem.job}</text>`;
  }).join("")}
  <text x="40" y="330" class="fund-svg-small">The split matters commercially as well as technically: buses are reused across missions, payloads generally are not.</text>
</svg>`;
}

/**
 * Why "a solar event" is not one thing.
 *
 * A log time axis from one minute to one week, with the three arrivals on it.
 * This is the single most important picture on the environment chapter and it
 * is the one a linear axis cannot draw: eight minutes and four days do not
 * share a linear scale.
 */
function figureArrivalTimeline(): string {
  const lo = Math.log10(1 / 60);      // 1 minute, in hours
  const hi = Math.log10(24 * 7);      // one week, in hours
  const x = (hours: number) => 70 + ((Math.log10(hours) - lo) / (hi - lo)) * 790;
  const ticks: { hours: number; label: string }[] = [
    { hours: 1 / 60, label: "1 min" },
    { hours: 10 / 60, label: "10 min" },
    { hours: 1, label: "1 hour" },
    { hours: 6, label: "6 h" },
    { hours: 24, label: "1 day" },
    { hours: 96, label: "4 days" },
    { hours: 168, label: "1 week" },
  ];
  const arrivals: { label: string; what: string; lo: number; hi: number; ink: string; row: number }[] = [
    { label: "X-RAYS AND EUV", what: "light. 8 min 19 s, and it is not negotiable", lo: 499.005 / 3600, hi: 499.005 / 3600, ink: INK.amber, row: 0 },
    { label: "ENERGETIC PARTICLES (SEP)", what: "tens of minutes to hours, along the field line", lo: 0.3, hi: 10, ink: INK.coral, row: 1 },
    { label: "CME PLASMA AND ITS SHOCK", what: "typically 1–4 days; extremes under a day", lo: 15, hi: 96, ink: INK.violet, row: 2 },
  ];
  return `
<svg viewBox="0 0 900 322" role="img" aria-label="A logarithmic time axis from one minute to one week after a solar eruption. Photons arrive at 8 minutes 19 seconds, energetic particles over tens of minutes to hours, and coronal mass ejection plasma over one to four days.">
  <text x="70" y="30" class="fund-svg-key">TIME SINCE THE ERUPTION ON THE SUN</text>
  ${arrivals.map((arrival) => {
    const y = 62 + arrival.row * 62;
    const width = Math.max(4, x(arrival.hi) - x(arrival.lo));
    return `
    <rect x="${x(arrival.lo)}" y="${y}" width="${width}" height="16" fill="${arrival.ink}" opacity=".3"></rect>
    <rect x="${x(arrival.lo)}" y="${y}" width="${width}" height="16" fill="none" stroke="${arrival.ink}" stroke-width="1.3"></rect>
    <text x="${x(arrival.lo)}" y="${y - 8}" style="fill:${arrival.ink};font-weight:600">${arrival.label}</text>
    <text x="${x(arrival.lo)}" y="${y + 30}" class="fund-svg-small">${arrival.what}</text>`;
  }).join("")}
  <line x1="70" y1="256" x2="860" y2="256" stroke="${INK.line}" stroke-width="1.2"></line>
  ${ticks.map((tick) => `
    <line x1="${x(tick.hours)}" y1="250" x2="${x(tick.hours)}" y2="262" stroke="${INK.line}"></line>
    <text x="${x(tick.hours)}" y="278" text-anchor="middle" class="fund-svg-small">${tick.label}</text>`).join("")}
  <text x="70" y="300" class="fund-svg-small">Three messengers, three arrival times, three different things broken.</text>
  <text x="70" y="316" class="fund-svg-small">A warning that says only "solar event" has not told an operator which one is coming.</text>
</svg>${figureReading("Read the three arrival times", arrivals.map(a => [a.label, a.what]),
  "Time since eruption uses a logarithmic axis. SEP and CME arrival ranges vary; these are teaching ranges, not a forecast for a particular event.")}`;
}

// ---------------------------------------------------------------------------
// CHAPTER 03 — READING AN ORBIT
//
// Absorbs old modules 01 (GSO vs geostationary), 02 (free fall), 03 (ground
// trace vs orbit), 04 (footprint definitions), 05 (ephemeris and SGP4) and
// 06 (GPS pseudoranges). Every figure quoted below is computed by the
// functions at the top of this file and re-derived independently in
// tests/satellite-fundamentals.test.ts.
// ---------------------------------------------------------------------------

const CH_ORBITS: Chapter = {
  id: "orbits",
  index: "03",
  title: "Reading an orbit",
  door: "Six numbers describe where a spacecraft is and will be. This is what each one does, why speed changes around an ellipse, and what each orbit regime is actually for.",
  lead: "An orbit is not a place, it is a trajectory, and six numbers fix it. Learn what each of the six controls and the rest of this site — ground tracks, footprints, revisit, coverage, the ionosphere a link crosses — stops being a list of separate facts.",
  covers: [
    "free fall and why nothing is weightless",
    "the six classical elements",
    "vis-viva, and what \"Vmax\" means",
    "period, altitude and the regimes",
    "inclination, coverage and footprint",
    "nodal regression and sun-synchronous orbits",
    "ground track and repeat cycles",
    "ephemeris, SGP4 and element age",
    "how GNSS turns four ranges into a position",
  ],
  sections: [
    {
      kicker: "THE ONE IDEA",
      title: "An orbit is falling, arranged so you keep missing.",
      lead: "A spacecraft in orbit is in continuous free fall towards Earth. What keeps it up is not an absence of gravity — gravity at 400 km is still 89% of its value at the surface — but sideways speed: it falls, and the curved surface falls away underneath it at the same rate.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Nothing in orbit is weightless",
              body: "Everything on board is falling at the same rate, so nothing presses on anything else. The correct term is free fall, or microgravity; “zero gravity” describes the sensation and misdescribes the physics.",
            },
            {
              term: "Speed, not height, is what an orbit costs",
              note: "the reason spaceplanes are hard",
              body: "Reaching 400 km altitude is a small fraction of the energy. Staying there needs 7.669 km/s sideways, which is where nearly all the launch energy goes.",
              operational: "It is also why an orbit cannot be “held” by burning fuel continuously the way an aircraft holds altitude. There is no lift, so there is nothing to trim.",
            },
            {
              term: "Two bodies, then everything else",
              note: "the model, and its edges",
              body: "The closed-form orbit on this page is the two-body problem: one point mass, one spacecraft. Everything that makes real operations interesting — Earth's oblateness, the Sun and Moon, radiation pressure, drag — is a perturbation added on top of it.",
            },
            {
              term: "Escape velocity",
              note: "11.180 km/s at the surface",
              body: "The speed at which the orbit is no longer closed. Nothing on this site is anywhere near it; every object in this catalogue is bound to Earth.",
            },
          ],
        },
      ],
    },
    {
      kicker: "THE SIX NUMBERS",
      title: "What each classical element actually controls.",
      lead: "Two of them set the shape of the ellipse, three set how that ellipse is oriented in space, and one says where on it the spacecraft is right now. Nothing else is needed to propagate a two-body orbit.",
      blocks: [
        { kind: "figure", svg: figureEllipse(), chip: "schematic", chipNote: "Drawn from the geometry, not from an element set", caption: "The ellipse is drawn true: Earth sits at one focus, the other focus is empty, and the two speed arrows share one scale. The eccentricity here is 0.74 — a Molniya orbit's, a real communications orbit, not an exaggeration for the diagram." },
        {
          kind: "terms",
          items: [
            {
              term: "a — semi-major axis",
              note: "SIZE · sets the period",
              body: "Half the long axis of the ellipse. It alone fixes the orbital period, which is why two orbits of wildly different shape can come round in exactly the same time.",
              operational: "This is the number a manoeuvre changes when you want to move in longitude at GEO: raise a and the spacecraft drifts west, lower it and it drifts east.",
            },
            {
              term: "e — eccentricity",
              note: "SHAPE · 0 is a circle",
              body: "How far from circular. e = 0 is a circle; e approaching 1 is a long thin ellipse that skims Earth at one end.",
            },
            {
              term: "i — inclination",
              note: "TILT · degrees from the equator",
              body: "The angle between the orbit plane and the equator. It sets the highest latitude the spacecraft ever passes over: an orbit at i = 51.6° never crosses above 51.6° north or south.",
              operational: "i > 90° is retrograde — the spacecraft travels against Earth's rotation. Every sun-synchronous orbit is retrograde, at about 98°, and that is not an error in the element set.",
            },
            {
              term: "Ω — right ascension of the ascending node",
              note: "SWIVEL · where the plane cuts the equator",
              body: "Which way the orbital plane is turned about Earth's axis, measured against the stars rather than against the ground. It is the element that separates the planes of a constellation.",
            },
            {
              term: "ω — argument of perigee",
              note: "SPIN · where the low point sits",
              body: "Where the closest point of the ellipse sits within the plane. On a circular orbit it is meaningless and the element set will contain an arbitrary value for it.",
              operational: "For a Molniya orbit this is the element that must not drift, because it is what keeps apogee — and therefore the long dwell — over the northern hemisphere.",
            },
            {
              term: "ν or M — true or mean anomaly",
              note: "WHERE, RIGHT NOW",
              body: "Position along the orbit at the stated epoch. True anomaly is the real geometric angle from perigee; mean anomaly is a uniformly increasing fiction that is easier to propagate and is what a two-line element set actually carries.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Select any spacecraft in the rail and open its card. The <em>Details</em> grid prints the element set this site is propagating, and <em>Download OMM + derived orbit JSON</em> hands you the raw mean elements the six names above refer to.",
            "Then set the geometry control to <em>Orbit</em> and switch the reference frame between <em>Inertial</em> and <em>Earth-fixed</em>. The ellipse is fixed in the inertial frame; it is Earth that turns. That single toggle is the whole of the next section.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
    {
      kicker: "SPEED",
      title: "Vis-viva: the speed at every point on the orbit.",
      lead: "One equation gives the speed anywhere on any Keplerian orbit from just two numbers: how far out you are now, and the size of the orbit. Everything about transfers, rendezvous and Doppler follows from it.",
      blocks: [
        {
          kind: "equation",
          name: "The vis-viva equation",
          tag: "Exact for two-body motion",
          formula: "v² = μ ( 2/r − 1/a )",
          where: [
            { symbol: "v", meaning: "speed at this instant, km/s" },
            { symbol: "r", meaning: "distance from Earth's centre now, km" },
            { symbol: "a", meaning: "semi-major axis of the orbit, km" },
            { symbol: "μ", meaning: "398,600.4418 km³/s² for Earth (WGS-84)" },
          ],
          worked: [
            "For a circular orbit r = a, so it collapses to v = √(μ/r). At 400 km altitude, r = 6,778.137 km and <code>v = 7.669 km/s</code>. At geostationary radius 42,164.170 km, <code>v = 3.075 km/s</code>.",
            "A geostationary satellite is therefore travelling at less than half the speed of the ISS, and takes 264 times as long to go round, because its orbit is 6.2 times larger.",
          ],
        },
        {
          kind: "terms",
          single: true,
          items: [
            {
              term: "“Vmax” — reading one: the speed maximum at perigee",
              note: "the textbook meaning",
              body: "On an ellipse r is smallest at perigee, so vis-viva makes v largest there and smallest at apogee. The spread is not small. A Molniya orbit with a 600 km perigee and a 39,767 km apogee runs at <b>9.962 km/s</b> at perigee and <b>1.506 km/s</b> at apogee — a factor of 6.6 around one orbit.",
              operational: "It is the reason a highly elliptical orbit is useful at all. The spacecraft races through the part of the orbit nobody wants and loiters over the part somebody paid for — a Molniya spends roughly two thirds of its twelve-hour period above 30,000 km.",
            },
            {
              term: "“Vmax” — reading two: the maximum line-of-sight rate on a pass",
              note: "what a terminal operator means",
              body: "For anyone pointing an antenna, the number that matters is not the orbital speed but the fastest the target ever moves relative to the dish. That maximum occurs at the horizon, not overhead, and it equals R⊕·v/r — for a 550 km orbit, <b>6.98 km/s</b> of pure range rate.",
              operational: "That is where the Doppler budget comes from: 6.98 km/s is ±51 kHz at S-band 2.2 GHz and ±37 kHz at L-band 1.6 GHz. The angular rate peaks at the opposite end of the pass — directly overhead, at roughly 0.8°/s for a 550 km pass — which is why an overhead pass is the one a slow pedestal drops.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Pick a LEO spacecraft and a GEO spacecraft in turn with the orbit-class control (<em>LEO</em> / <em>GEO</em>), leave the geometry on <em>Orbit</em>, and watch the two draw at their real relative rates. Nothing is exaggerated: the ratio you see is 7.669 to 3.075.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
    {
      kicker: "THE REGIMES",
      title: "Altitude buys period, coverage and trouble.",
      lead: "There are only a handful of orbits in routine use, and each exists because it solves one problem well enough to pay for what it costs. The boundaries between them are conventions, and the conventions disagree.",
      blocks: [
        { kind: "figure", svg: figureAltitudeLadder(), chip: "schematic", chipNote: "Log altitude scale · speeds and periods computed, belts indicative", caption: "Speeds and periods on this ladder are computed from μ and R⊕. The radiation-belt bands are indicative only: the belts move with the driving, which is exactly what the Radiation belts layer on the globe is for." },
        {
          kind: "terms",
          items: [
            {
              term: "LEO — up to 2,000 km",
              note: "IADC Region A",
              body: "Short range, low latency, small footprint, high revisit — and 90-minute periods, so any one spacecraft is over you for minutes at a time. Coverage therefore needs a constellation, not a satellite.",
              operational: "The 2,000 km ceiling is a real definition, not a convention: it is the top of the IADC protected region, and it is what the disposal rules attach to.",
            },
            {
              term: "MEO — 2,000 km to GEO",
              note: "the definitions disagree here",
              body: "Home of GNSS at 20,184 km, where a 12-hour period means two orbits per sidereal day and a repeating ground track. NASA and the debris community use “2,000 km to 35,786 km”; the ITU describes MEO as “mainly between 8,000 and 20,000 km”. Both are in current use.",
            },
            {
              term: "GEO — 35,786 km",
              note: "one sidereal day",
              body: "The altitude at which the period equals one sidereal day, 23 h 56 m 04.09 s. A single spacecraft sees 42.4% of Earth's surface and never sets, which is why one satellite can be a service.",
            },
            {
              term: "IGSO — GSO is not automatically geostationary",
              note: "the distinction that catches people",
              body: "Geosynchronous means the period matches Earth's rotation. Geostationary is the subset that is also near-circular <em>and</em> near-equatorial. An inclined GSO spacecraft returns to the same longitude each day but traces a figure-of-eight in latitude — it is synchronous and it is not stationary. That is what the catalog cards on this site call <strong>IGSO</strong>, and it is a destination rather than a leftover: BeiDou, India's NavIC and Japan's QZSS all fly it deliberately, because tilting the orbit puts a navigation satellite high overhead at mid-latitudes where a satellite on the equator sits low.",
              operational: "Inclined GSO is not a fault. Operators deliberately stop north-south station-keeping at end of life to stretch the propellant, accepting a growing figure-of-eight that only a tracking antenna can follow.",
            },
            {
              term: "HEO — and say which one you mean",
              note: "two different expansions",
              body: "“Highly elliptical orbit” (large e, low perigee, high apogee) and “high Earth orbit” (apogee above GEO) are both written HEO and no standards body settles it. Molniya and Tundra orbits are the classic highly elliptical cases.",
            },
            {
              term: "Molniya — 63.4°, twelve hours",
              note: "a = 26,562 km, e ≈ 0.74",
              body: "Half a sidereal day, apogee parked over the northern hemisphere, and an inclination chosen so the apogee stays there. Built for high-latitude coverage that a GEO spacecraft on the equator cannot give, because from 65° north a geostationary satellite is close to the horizon.",
            },
            {
              term: "Sun-synchronous — about 98°",
              note: "a retrograde LEO",
              body: "An orbit whose plane precesses eastward at exactly the rate Earth goes round the Sun, 0.9856° per day, so it crosses every latitude at the same local solar time on every pass. At 700 km that requires an inclination of 98.19°.",
              operational: "It is what makes change detection possible: two images of the same place have the same sun angle and the same shadows, so a difference between them is a difference on the ground.",
            },
            {
              term: "GTO — the waiting room",
              note: "not a destination",
              body: "Geostationary transfer orbit: a long ellipse with perigee in LEO and apogee at geostationary radius. Nothing operates there. It is the half-orbit between the launch and the circularisation burn, and it is covered in the next chapter.",
            },
          ],
        },
        {
          kind: "facts",
          items: [
            { value: "3.97%", caption: "of Earth's surface inside the geometric horizon of a 550 km spacecraft" },
            { value: "38.0%", caption: "from GNSS altitude, 20,184 km" },
            { value: "42.4%", caption: "from GEO — one satellite, most of a hemisphere" },
            { value: "81.3°", caption: "horizon half-angle at GEO, measured at Earth's centre" },
          ],
        },
      ],
    },
    {
      kicker: "COVERAGE",
      title: "A footprint needs a definition before it means anything.",
      lead: "Everyone draws a circle under a satellite and calls it the footprint. Which circle depends entirely on what question is being asked, and the answers differ by hundreds of kilometres.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Geometric horizon",
              note: "0° elevation · this site's default",
              body: "Everywhere the spacecraft is above the mathematical horizon. It is the largest honest circle and the one that assumes nothing about the payload.",
              operational: "Nobody works a link at 0° elevation. Terrain, buildings, ground noise and atmospheric path length all make the last few degrees unusable, which is why operators quote a mask.",
            },
            {
              term: "Elevation-masked coverage",
              note: "5°, 10°, 25°",
              body: "The horizon circle shrunk to the lowest elevation the link will actually close at. The mask is a system choice, so two operators can honestly publish different footprints for the same spacecraft.",
            },
            {
              term: "Instrument or antenna footprint",
              note: "what the payload can really see",
              body: "Field of view, boresight, spacecraft attitude and the antenna pattern, not geometry alone. A sensor with a 15° field of view sees a small patch inside a vast horizon circle.",
            },
            {
              term: "Beam and spot beam",
              note: "the useful subdivision",
              body: "A beam is one antenna pattern on the ground. A spot beam is a narrow one covering a small area at high gain, so the same spacecraft can put far more power and far more capacity into a given place.",
              operational: "Spot beams are also how frequency reuse works: two beams far enough apart can use the same frequency, and total capacity stops being set by bandwidth alone.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Set the geometry control to <em>Footprint</em> and pick a LEO spacecraft, then a GEO one. The site draws the geometric radio horizon by default and says so on the card; the elevation control beside it re-cuts the same circle at a mask, and the number moves a long way.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
    {
      kicker: "THE GROUND",
      title: "The ground track is not the orbit.",
      lead: "The orbit is a fixed ellipse in inertial space. The ground track is the moving point beneath the spacecraft on a planet that is turning underneath it — two different objects, and confusing them is the most common mistake on any orbit display.",
      blocks: [
        { kind: "figure", svg: figureGroundTrack(), chip: "schematic", chipNote: "Track computed from the orbital period; Natural Earth coastlines", caption: "Four successive passes of a 92.56-minute orbit. Each track lies 23.20° of longitude west of the last because Earth turned by that much while the spacecraft went round once. The sinusoid's amplitude is the inclination." },
        {
          kind: "equation",
          name: "Westward shift per revolution",
          tag: "First order — ignores nodal regression",
          formula: "Δλ  ≈  360° × T / 86,164.0905 s",
          where: [
            { symbol: "Δλ", meaning: "longitude the next pass lands west by" },
            { symbol: "T", meaning: "orbital period, seconds" },
            { symbol: "86,164.0905", meaning: "the sidereal day — Earth's real rotation period" },
          ],
          worked: [
            "At 400 km, T = 92.56 min, so <code>Δλ = 23.20°</code> — about <code>2,583 km</code> at the equator. That is why a low-orbit spacecraft does not pass over the same place on consecutive orbits, and why a single LEO satellite cannot give continuous coverage of anywhere.",
            "The full expression is Δλ = (ω⊕ − Ω̇)·T with Ω̇ the nodal regression from the next section, which matters when the repeat cycle has to close exactly.",
          ],
        },
        {
          kind: "terms",
          items: [
            {
              term: "Repeat ground track",
              note: "j revolutions in k days",
              body: "Choose the altitude so that a whole number of orbits fits a whole number of nodal days and the track closes exactly, then repeats forever. Earth-observation missions live on these so that every image can be compared with the last one over the same ground.",
            },
            {
              term: "Sidereal, not solar",
              note: "23 h 56 m 04.09 s",
              body: "The 86,164 s in the formula is Earth's rotation against the stars, not the 86,400 s solar day. The four-minute difference compounds: use the wrong one and a ground track prediction is a degree out within a day.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Set geometry to <em>Ground trace</em> and open <em>Open 2D ground-track map →</em> on a LEO spacecraft. Successive traces march west by the amount the formula above predicts. Switch the frame to <em>Inertial</em> and the same orbit stops moving — which is the point: only one of these two pictures is the orbit.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
    {
      kicker: "THE PLANE DRIFTS",
      title: "Earth is not a sphere, and the orbit knows.",
      lead: "Earth's equatorial bulge — the J₂ term — pulls the orbital plane round and rotates the ellipse within it. Both effects are large enough to be exploited, and two of the most useful orbits in existence are built on them.",
      blocks: [
        {
          kind: "equation",
          name: "Nodal regression from J₂",
          tag: "Secular, first-order",
          formula: "Ω̇  =  − ( 3 n J₂ R⊕² / 2 a² (1−e²)² ) · cos i",
          where: [
            { symbol: "Ω̇", meaning: "rate the plane swivels, rad/s" },
            { symbol: "n", meaning: "mean motion √(μ/a³)" },
            { symbol: "J₂", meaning: "1.0826267×10⁻³ (WGS-84 dynamic)" },
            { symbol: "i", meaning: "inclination" },
          ],
          worked: [
            "A prograde orbit (i < 90°) has cos i > 0, so Ω̇ is negative and the plane drifts west. The ISS at 420 km and 51.6° regresses about <code>5.0° per day</code>, which is why its plane relative to the Sun changes week by week.",
            "Set i above 90° and cos i flips sign, so the plane drifts <em>east</em>. Tune it until that eastward drift equals Earth's 0.9856°/day motion about the Sun and the orbit is sun-synchronous: at 700 km, <code>i = 98.19°</code>.",
          ],
        },
        {
          kind: "equation",
          name: "Apsidal drift, and the critical inclination",
          tag: "Why 63.4° is not arbitrary",
          formula: "ω̇  =  ( 3 n J₂ R⊕² / 4 a² (1−e²)² ) · ( 5 cos² i − 1 )",
          where: [
            { symbol: "ω̇", meaning: "rate the ellipse rotates in its own plane" },
            { symbol: "5 cos² i − 1", meaning: "the whole story: it can be zero" },
          ],
          worked: [
            "The bracket vanishes when cos² i = 1/5, that is at <code>i = 63.435°</code> (or its retrograde partner 116.565°). At that inclination perigee does not drift, so apogee stays where it was put.",
            "That is the entire reason Molniya and Tundra orbits are flown at 63.4°. Fly the same ellipse at any other inclination and apogee walks out of the northern hemisphere, taking the coverage with it.",
          ],
        },
      ],
    },
    {
      kicker: "KNOWING WHERE IT IS",
      title: "An ephemeris is a claim about a time, not a fact about now.",
      lead: "Nothing on this site measures a satellite's position directly. It takes published mean elements, propagates them with the model those elements were fitted for, and reports how old the fit is — because the age is part of the answer.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Ephemeris",
              body: "Time-tagged information from which position and velocity can be determined or predicted. It is always <em>as of</em> an epoch, and it is always the output of a fit to observations rather than an observation itself.",
            },
            {
              term: "Mean elements and SGP4",
              note: "OMM / TLE",
              body: "The elements published for most objects are <em>mean</em> elements: averaged quantities that only make sense inside the propagator they were fitted for. Feeding a TLE to a general-purpose two-body propagator gives a plausible, wrong answer.",
              operational: "This is the trap worth remembering: SGP4 elements and osculating elements are different objects wearing the same six names. They are not interchangeable and no error message tells you.",
            },
            {
              term: "Element age",
              note: "the number to look at first",
              body: "Accuracy decays with time since epoch, quickly in low orbit where drag is doing the work. A day-old element set on a decaying object can be kilometres out along-track.",
            },
            {
              term: "Along-track error dominates",
              body: "Prediction error appears mostly as “where along the orbit”, not “which orbit”. That is why a pass can arrive a few seconds early or late while the geometry is essentially right.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Every satellite card on this site prints the element epoch and its age. That is deliberate, and it is the honest form of the claim: the site is not telling you where a spacecraft is, it is telling you where a fit of a certain age says it will be.",
          ],
          goto: { label: "How every layer here is built →", view: "learn-layers" },
        },
      ],
    },
    {
      kicker: "PNT",
      title: "How four ranges become a position and a clock.",
      lead: "A GNSS receiver does not measure its position. It measures how long several coded signals took to arrive, and solves for the only four unknowns that could explain all of them at once.",
      blocks: [
        {
          kind: "equation",
          name: "The pseudorange",
          tag: "Why four satellites, not three",
          formula: "ρᵢ = |sᵢ − u| + c·δt",
          where: [
            { symbol: "ρᵢ", meaning: "measured pseudorange to satellite i" },
            { symbol: "sᵢ", meaning: "that satellite's position, from its broadcast ephemeris" },
            { symbol: "u", meaning: "receiver position — three unknowns" },
            { symbol: "c·δt", meaning: "receiver clock error — the fourth unknown" },
          ],
          worked: [
            "The receiver's clock is far too cheap to be right, so every range is biased by the same unknown offset. Three ranges would fix a position if the clock were perfect; the fourth is what lets the receiver solve for the clock error instead of assuming it away.",
            "The by-product is that any GNSS receiver is also a precise timing device, which is why the T in PNT is load-bearing: power grids, financial timestamping and telecommunications networks take time from GNSS, not position.",
          ],
        },
        {
          kind: "terms",
          items: [
            {
              term: "Geometry matters as much as ranging",
              note: "dilution of precision",
              body: "Four satellites bunched in one part of the sky give a poorly conditioned solution however good each range is. Spread them out and the same measurements give a far better fix.",
            },
            {
              term: "The ionosphere is the largest environmental term",
              body: "Free electrons along the path delay the code and advance the carrier, and the size of that depends on total electron content and on frequency. Dual-frequency receivers estimate and remove most of it; single-frequency receivers use a broadcast model and keep the residual.",
              operational: "This is the direct link between space weather and PNT accuracy, and it is measurable on this site — the probe reports a GNSS L1 range error for the column you click on.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Select <em>MEO</em> on the orbit-class control, then open <em>Mission Types</em> and tick <em>navigation</em>. Switch between GPS, Galileo, BeiDou and GLONASS. Compare the plane counts and inclinations — four different answers to the same coverage problem.",
            "Then click bare globe to open the probe and press <em>Load the ionosphere column (19 MB) →</em>. It reports foF2, hmF2, MUF, TEC and the GNSS L1 range error for that place, all of it labelled model-derived, because WAM-IPE is a model and not an ionosonde.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
  ],
  sources: [
    { ref: "1", title: "NIMA TR8350.2, Department of Defense World Geodetic System 1984, 3rd ed.", where: "μ = 3986004.418×10⁸ m³/s², a = 6378137.0 m, C̄₂,₀ giving dynamic J₂ = 1.0826267×10⁻³, sidereal day 86164.0905 s", url: "https://earth-info.nga.mil/php/download.php?file=coord-wgs84" },
    { ref: "2", title: "Vallado, Fundamentals of Astrodynamics and Applications, 4th ed.", where: "vis-viva, the classical element set, J₂ secular rates for Ω̇ and ω̇, repeat ground tracks (chs. 1, 9, 11)" },
    { ref: "3", title: "IADC-02-01 Rev. 2, IADC Space Debris Mitigation Guidelines", where: "LEO protected Region A defined as surface to 2,000 km altitude; geostationary altitude 35,786 km", url: "https://orbitaldebris.jsc.nasa.gov/library/iadc-space-debris-guidelines-revision-2.pdf" },
    { ref: "4", title: "ITU, Satellite regulation: LEO, MEO, GEO", where: "MEO described as lying mainly between 8,000 and 20,000 km — the source of the definitional disagreement noted above", url: "https://www.itu.int/hub/2023/01/satellite-regulation-leo-geo-wrs/" },
    { ref: "5", title: "NASA Earth Observatory, Catalog of Earth Satellite Orbits", where: "geostationary radius 42,164 km and period 23 h 56 m 04 s; Molniya inclination 63.4°", url: "https://science.nasa.gov/earth/earth-observatory/catalog-of-earth-satellite-orbits" },
    { ref: "6", title: "Paek & Sung, ISSFD 2019, Optimal design of sun-synchronous orbits", where: "closed-form sun-synchronous inclination; 700 km → 98.19°", url: "https://issfd.org/ISSFD_2019/ISSFD_2019_AIAC18_Paek-Sung_Wook_2.pdf" },
    { ref: "7", title: "Hoots & Roehrich, Spacetrack Report No. 3; CelesTrak, Revisiting Spacetrack Report No. 3", where: "SGP4 mean elements are only valid inside the SGP4 propagator", url: "https://celestrak.org/publications/AIAA/2006-6753/" },
    { ref: "8", title: "US Space Force, NAVSTAR GPS Space Segment / Navigation User Interfaces, IS-GPS-200", where: "pseudorange observable and the four-unknown navigation solution", url: "https://www.gps.gov/technical/icwg/" },
  ],
};

// ---------------------------------------------------------------------------
// CHAPTER 01 — THE LINK, END TO END
//
// The vocabulary Sean named first, and the one most reference pages skip
// straight past. Where a term has a formal definition in the Radio
// Regulations or an ETSI/3GPP standard, that definition is quoted and cited.
// Where a term is universal in the industry and has NO standardised
// definition — "teleport", "user terminal", "transponder" all fall in this
// group — the page says so rather than inventing an authority for it.
// ---------------------------------------------------------------------------

const CH_LINK: Chapter = {
  id: "link",
  index: "01",
  title: "The link, end to end",
  door: "User, terminal, gateway, uplink, downlink, crosslink, forward and return. The words are used loosely everywhere, and half of them mean something specific.",
  lead: "A satellite link has two ends on the ground and at least one in space, and almost every term for its parts is used more loosely in conversation than in the standards. This chapter fixes the vocabulary, then shows what the spacecraft in the middle actually does with what it receives.",
  covers: [
    "user, user terminal, gateway, teleport",
    "uplink, downlink, crosslink / ISL",
    "forward link vs return link",
    "feeder link vs service link",
    "bent-pipe vs regenerative payloads",
    "transponder, beam, spot beam",
    "frequency reuse and colours",
    "latency, and the figure everyone quotes wrongly",
  ],
  sections: [
    {
      kicker: "THE PICTURE",
      title: "Every name, on the thing it names.",
      lead: "Two ends on the ground, one or more spacecraft in between, and four different words for the same piece of radio depending on which way it is going and who is at each end.",
      blocks: [
        { kind: "figure", svg: figureLinkGeometry(), chip: "schematic", chipNote: "Naming diagram · geometry not to scale", caption: "Uplink and downlink are named by direction. Forward and return are named by <em>whose traffic it is</em>: both of them contain an uplink and a downlink. The crosslink never touches the ground at all." },
      ],
    },
    {
      kicker: "THE TWO ENDS",
      title: "Who is at each end, and what the standards call them.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "User",
              body: "The person or system the service exists for. Not a piece of equipment — this is the distinction that makes the next row worth having.",
            },
            {
              term: "User terminal",
              note: "no standardised definition",
              body: "The radio at the user's end of the link: a handset, a manpack, a ship's antenna, a flat panel on a roof. It is universal industry usage and it is <em>not</em> defined in the Radio Regulations, which speak only of earth stations.",
              operational: "3GPP calls it the UE; DVB-RCS2 calls it the RCST; ITU-R S.725 calls a small one a VSAT. Four names, one box, and specifications that use them interchangeably.",
            },
            {
              term: "Gateway / teleport / hub",
              note: "the operator's end",
              body: "The large earth station that connects the satellite to terrestrial networks. DVB-RCS2 defines a gateway as the entity that receives the return-link signals and provides the next-hop network interface; “teleport” is a commercial term with no standards definition at all.",
              operational: "A teleport is usually a site with many antennas serving many spacecraft and many customers, while a gateway is a function within a specific network. The words are used as synonyms and mostly get away with it.",
            },
            {
              term: "Earth station · space station",
              note: "ITU RR 1.63 · 1.64",
              body: "The formal terms. Everything on the ground is an earth station whether it is a handheld radio or a 32-metre dish, and everything on the spacecraft is a space station.",
            },
          ],
        },
      ],
    },
    {
      kicker: "DIRECTIONS",
      title: "Uplink and downlink name a direction. Forward and return name a job.",
      lead: "This is the pair that gets stated backwards most often, including in otherwise careful documents, because the two pairs of words are not answering the same question.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Uplink",
              note: "ITU: Earth-to-space",
              body: "Ground to spacecraft. One link, one direction, nothing about who sent it.",
            },
            {
              term: "Downlink",
              note: "ITU: space-to-Earth",
              body: "Spacecraft to ground. The Radio Regulations allocate spectrum by these two directions and never by band letter.",
            },
            {
              term: "Forward link",
              note: "gateway → satellite → user",
              body: "The whole path carrying traffic <em>towards</em> the user. It contains an uplink (gateway to spacecraft) and a downlink (spacecraft to terminal), so calling it “the uplink” is wrong in both halves.",
              operational: "The rule that makes it memorable: forward always points at the remote end. ETSI's DVB-RCS2, NASA's Space Network user guide and CCSDS all agree on this, in that order of formality — the common claim that NASA uses it backwards is simply false.",
            },
            {
              term: "Return link",
              note: "user → satellite → gateway",
              body: "The whole path carrying traffic back from the user. Also one uplink and one downlink, in the other order.",
              operational: "Forward and return capacity are usually wildly asymmetric, and the return link is normally the one that runs out first — the user end has the small antenna and the small power amplifier.",
            },
            {
              term: "Feeder link · service link",
              note: "ITU RR 1.115 · 3GPP TR 38.811",
              body: "Feeder link is the gateway-to-spacecraft leg; service link is the spacecraft-to-user leg. These name the <em>segments</em>, where forward and return name the end-to-end paths built from them.",
              operational: "Feeder links usually sit in a higher band than the service link — Ka feeders for a UHF or L-band service — because a gateway can afford the antenna and the rain-fade margin that a handheld cannot.",
            },
            {
              term: "Crosslink / inter-satellite link (ISL)",
              note: "ITU RR 1.22 defines the service",
              body: "A link between spacecraft that never touches the ground. It can be radio or optical, and it requires a payload that can do something with the traffic rather than merely relay it.",
              operational: "This is what lets a constellation serve a user who is nowhere near a gateway — over an ocean, over the poles, or over territory where no gateway can be built.",
            },
          ],
        },
      ],
    },
    {
      kicker: "THE PAYLOAD'S DECISION",
      title: "Does the satellite understand what it is carrying?",
      lead: "There are two answers, and everything else about a communications payload follows from which one it gives.",
      blocks: [
        { kind: "figure", svg: figurePayloadKinds(), chip: "schematic", chipNote: "Block diagram · 3GPP TR 38.811 definitions", caption: "The bent pipe is deliberately stupid, and that is a design strength: it is transparent to waveform, so the ground can change modulation and coding for twenty years without touching the spacecraft." },
        {
          kind: "terms",
          items: [
            {
              term: "Bent-pipe / transparent payload",
              note: "3GPP TR 38.811, verbatim",
              body: "“Payload that changes the frequency carrier of the uplink RF signal, filters and amplifies it before transmitting it on the downlink.” It never demodulates, so it never learns anything about the traffic.",
              operational: "The consequence that bites: uplink noise and interference are amplified and retransmitted with the signal. A jammer on the uplink is delivered to every downlink user, at gain.",
            },
            {
              term: "Regenerative / processed payload",
              note: "3GPP TR 38.811, verbatim",
              body: "Adds “digital processing that may include demodulation, decoding, re-encoding, re-modulation and/or filtering.” The link is broken into two independent links that can have different waveforms, different rates and different error budgets.",
              operational: "Because the uplink is demodulated, uplink noise does not reach the downlink — the noise budget stops accumulating. The cost is that the spacecraft now contains a modem it will fly with for its whole life.",
            },
            {
              term: "Transponder",
              note: "no standardised definition",
              body: "One receive-amplify-transmit chain through a bent-pipe payload, usually described by its bandwidth — “a 36 MHz transponder”. Capacity on a classic FSS spacecraft is sold in these units.",
            },
            {
              term: "Beam",
              body: "One antenna pattern on the ground. A global or regional beam covers everything the spacecraft can see, at correspondingly modest gain.",
            },
            {
              term: "Spot beam",
              note: "the whole HTS idea",
              body: "A narrow, high-gain beam covering a small area. Narrower means more gain for the same power, so a spot beam delivers far more capacity to a given place than a wide beam can.",
            },
            {
              term: "Frequency reuse and “colours”",
              note: "Report ITU-R S.2461-0",
              body: "Beams far enough apart can use the same frequency without interfering, so total capacity stops being limited by bandwidth. A frequency-and-polarization pair is called a colour, and adjacent beams must not share one.",
              operational: "This is why a high-throughput satellite is described by beam count as much as by bandwidth, and why coverage maps look like a honeycomb rather than a circle.",
            },
          ],
        },
      ],
    },
    {
      kicker: "TIME OF FLIGHT",
      title: "The distance is the latency, and the famous number is not the propagation.",
      lead: "Radio travels at the speed of light and there is no arguing with the geometry, so the orbit chosen sets a floor under the delay before any equipment is switched on.",
      blocks: [
        {
          kind: "facts",
          items: [
            { value: "119.4 ms", caption: "GEO, straight up: 35,786 km at c, one way" },
            { value: "238.7 ms", caption: "GEO ground–satellite–ground, sub-satellite point" },
            { value: "278.1 ms", caption: "the same trip at 0° elevation — slant range 41,679 km" },
            { value: "1.8 ms", caption: "550 km LEO, straight up, one way" },
          ],
        },
        {
          kind: "terms",
          single: true,
          items: [
            {
              term: "The “500 ms round trip” figure is not propagation delay",
              body: "Propagation alone is 238–278 ms for one ground-to-ground hop through GEO. The larger numbers in circulation fold in payload, modem and ground-segment processing, and usually describe a user-to-user path with two slant legs rather than one.",
              operational: "Worth being precise about, because the two numbers lead to different conclusions: a protocol problem caused by 250 ms of propagation cannot be engineered away, and one caused by 250 ms of processing sometimes can.",
            },
            {
              term: "Latency at LEO is not just smaller, it is variable",
              body: "A 550 km spacecraft is 1.8 ms away overhead and about 9 ms away at the horizon — a factor of five within a single pass, changing continuously.",
              operational: "Handover between spacecraft, and the jitter it produces, is often the harder engineering problem than the raw delay.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Turn on <em>Ground stations</em> in the layer list and select a GEO spacecraft, then a LEO one. The site draws the real geometry — the same slant ranges the numbers above come from — and the LEO footprint sweeps while the GEO one sits still.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
  ],
  sources: [
    { ref: "1", title: "ITU Radio Regulations, Edition of 2024, Article 1", where: "No. 1.63 earth station, 1.64 space station, 1.113 satellite link (“comprises one up-link and one down-link”), 1.114 multi-satellite link, 1.115 feeder link, 1.22 inter-satellite service, 1.161 e.i.r.p.", url: "https://www.itu.int/pub/R-REG-RR" },
    { ref: "2", title: "ETSI EN 301 545-2 V1.4.1 (DVB-RCS2), clause 3.1", where: "forward link = “satellite link from the NCC and feeder to the RCSTs”; return link = “satellite link from the RCSTs to the gateway”; gateway definition", url: "https://www.etsi.org/deliver/etsi_en/301500_301599/30154502/01.04.01_60/en_30154502v010401p.pdf" },
    { ref: "3", title: "NASA 450-SNUG, Space Network Users' Guide, Rev. 10 §3.2, and CCSDS 910.4-B-1 §1.6.2", where: "forward service originates at the control centre and terminates at the platform; return service the reverse — the same convention as ETSI" },
    { ref: "4", title: "3GPP TR 38.811 V15.1.0, clause 3.1", where: "verbatim definitions of bent-pipe and regenerative payloads; feeder link and service link; ISL", url: "https://www.3gpp.org/ftp/Specs/archive/38_series/38.811/" },
    { ref: "5", title: "Report ITU-R S.2461-0 (07/2019)", where: "spot-beam frequency reuse, cluster factor, and the frequency-plus-polarization “colour”", url: "https://www.itu.int/pub/R-REP-S.2461" },
    { ref: "6", title: "ITU-R S.725, VSAT network characteristics", where: "VSAT and star-network terminology" },
    { ref: "7", title: "FCC DA 21-34 (8 January 2021), SAT-MOD-20200417-00037", where: "the 550 km Starlink shell used for the LEO latency arithmetic", url: "https://docs.fcc.gov/public/attachments/DA-21-34A1.pdf" },
    { ref: "8", title: "ESA, Types of orbits; NIST/CODATA", where: "geostationary altitude 35,786 km; c = 299,792,458 m/s exact. Latency figures above are computed from these two.", url: "https://www.esa.int/Enabling_Support/Space_Transportation/Types_of_orbits" },
  ],
};

// ---------------------------------------------------------------------------
// CHAPTER 02 — THE SPECTRUM AND THE LINK BUDGET
//
// Absorbs old modules 07 (the spectrum) and 08 (UHF through the ionosphere).
// The band-letter mismatch table is the part of this chapter most worth
// having: satcom shorthand and the IEEE letters agree only for L and S, and
// almost every published "band table" quietly pretends otherwise.
// ---------------------------------------------------------------------------

const CH_SPECTRUM: Chapter = {
  id: "spectrum",
  index: "02",
  title: "Spectrum and the link budget",
  door: "What the band letters mean, why satcom's letters disagree with the radar standard's, and the arithmetic that decides whether a link closes.",
  lead: "Frequency choice decides antenna size, beam width, available bandwidth, rain sensitivity and how much the ionosphere interferes — so it is the first architectural decision, not a detail. Then the link budget decides whether the choice works.",
  covers: [
    "the IEEE letter bands, exactly",
    "why satcom's letters do not match them",
    "what each band is actually used for",
    "military UHF SATCOM and MUOS",
    "EIRP and G/T",
    "free-space path loss and C/N₀",
    "link margin and rain fade",
    "polarization, XPD and Faraday rotation",
  ],
  sections: [
    {
      kicker: "ONE PHYSICS",
      title: "Radio, infrared, visible, X-rays: all the same thing.",
      lead: "Everything on the electromagnetic spectrum is the same phenomenon at a different frequency, travelling at the same speed, and none of it is a stream of charged particles. That distinction matters on this site more than most, because the other half of it <em>is</em> about charged particles, and they behave nothing alike.",
      blocks: [
        {
          kind: "equation",
          name: "Frequency and wavelength",
          tag: "The reason band choice is architecture",
          formula: "λ = c / f",
          where: [
            { symbol: "λ", meaning: "wavelength" },
            { symbol: "f", meaning: "frequency" },
            { symbol: "c", meaning: "299,792,458 m/s exactly — in vacuum" },
          ],
          worked: [
            "At UHF 300 MHz, λ = 1.0 m. At Ka 30 GHz, λ = 1.0 cm. Antenna gain for a given physical size goes as (D/λ)², so the same dish is a hundred times more directive at Ka than at UHF.",
            "That single ratio explains most of the trade: low bands give wide beams, forgiving pointing, penetration and small bandwidth; high bands give narrow beams, enormous bandwidth, and no tolerance for rain or for a terminal that cannot point.",
          ],
        },
      ],
    },
    {
      kicker: "THE LETTERS",
      title: "The band letters, and the trap inside them.",
      lead: "There is exactly one standard for the letters — IEEE Std 521 — and the satellite industry does not follow it. Both usages are correct within their own community, and a document that mixes them without saying so is a source of real errors.",
      blocks: [
        { kind: "figure", svg: figureBandLadder(), chip: "schematic", chipNote: "IEEE 521-2019 letters · ITU/NTIA allocations below", caption: "The top row is the IEEE radar standard. The bottom rows are what satellite services actually occupy. Read the two together and the mismatch in the next table is visible: “Ka-band 30/20” has a downlink that is not in IEEE Ka at all." },
        {
          kind: "terms",
          items: [
            {
              term: "“C-band” 6/4 GHz",
              note: "uplink 5.925–6.425 · downlink 3.7–4.2",
              body: "The original workhorse fixed-satellite band. Rugged in rain, needs a large dish, and shares spectrum with terrestrial services almost everywhere.",
              operational: "Only the uplink is IEEE C. The 3.7–4.0 GHz part of the downlink is IEEE <em>S</em> band.",
            },
            {
              term: "“Ku-band” 14/12 GHz",
              note: "uplink 14.0–14.5 worldwide",
              body: "Television, VSAT, maritime and aeronautical broadband. Smaller antennas than C, meaningful rain fade, and downlink allocations that differ by ITU Region.",
              operational: "The uplink is IEEE Ku; the 10.7–12.0 GHz downlink is IEEE <em>X</em>.",
            },
            {
              term: "“Ka-band” 30/20 GHz",
              note: "uplink 27.5–30.0 · downlink 17.7–20.2",
              body: "The high-throughput band: wide allocations, small terminals, tight spot beams. Rain fade is the design driver rather than a footnote.",
              operational: "No part of the 17.7–21.2 GHz downlink is in IEEE Ka (27–40 GHz). It is IEEE K, and partly Ku. Military Ka is a separate slice at 30.0–31.0 up / 20.2–21.2 down.",
            },
            {
              term: "Military “X-band” 8/7 GHz",
              note: "down 7.25–7.75 · up 7.9–8.4",
              body: "Government and military fixed-satellite service — WGS and its allies' equivalents. Chosen partly because it is not a commercial band, so the interference environment is controlled.",
              operational: "Most of it is not IEEE X. 7.25–8.0 GHz is IEEE C; only 8.0–8.4 GHz is IEEE X.",
            },
            {
              term: "L-band MSS",
              note: "1.525–1.559 down · 1.6265–1.6605 up",
              body: "Mobile satellite service — Inmarsat's pairing. Iridium sits nearby at 1616–1626.5 MHz. Small omnidirectional-ish antennas, modest data rates, works from a moving platform without pointing.",
              operational: "L and S are the only two satcom band names that sit entirely inside their IEEE letter.",
            },
            {
              term: "S-band",
              note: "2.025–2.110 up · 2.200–2.290 down",
              body: "Space operations and space research: the band most spacecraft are actually flown on. US MSS allocations at 2000–2020/2180–2200 MHz are narrower than the ITU's 1980–2010/2170–2200.",
            },
            {
              term: "Q/V band",
              note: "37.5–42.5 down · 42.5–51.4 up",
              body: "Feeder links for high-throughput constellations, moving gateway traffic out of the bands the users need. Severe rain fade, handled with gateway diversity rather than with margin.",
              operational: "“Q” is not an IEEE letter at all — it is a waveguide convention. The 37.5–42.5 GHz range straddles IEEE Ka and V.",
            },
          ],
        },
        {
          kind: "terms",
          single: true,
          items: [
            {
              term: "Military UHF SATCOM: narrow, crowded, and irreplaceable",
              note: "MIL-STD-188-181 · 243–270 down / 291–318 up",
              body: "Transmit tunable in 5 kHz increments over 291.000–318.000 MHz; receive over 243.000–270.000 MHz. A UHF Follow-On spacecraft carries 39 channels totalling 555 kHz — the entire payload has less bandwidth than a single Wi-Fi channel.",
              operational: "It survives because a 1 m wavelength does what Ka cannot: it works through foliage, from a manpack, on the move, with an antenna nobody has to point. Demand for those channels has always exceeded supply, and that scarcity is a UHF SATCOM fact of life rather than a temporary shortage.",
            },
            {
              term: "MUOS: two payloads on one spacecraft",
              note: "legacy 292–318 / 244–270 · WCDMA 300–320 up, 360–380 down",
              body: "The legacy payload mirrors the UFO plan so existing radios keep working. Alongside it, a WCDMA payload carries four 5 MHz channels each way, reused across 16 beams — 64 channels per spacecraft. Feeder links are at Ka, to four ground stations.",
              operational: "This is the clearest example on the page of why the band choice is architecture: the same spacecraft is deliberately both a 1990s bent-pipe and a 3G cellular network, because the user radios could not all be replaced at once.",
            },
          ],
        },
      ],
    },
    {
      kicker: "THE BUDGET",
      title: "Does the link close? Add up decibels until you find out.",
      lead: "A link budget is one sum: everything that adds power, minus everything that takes it away, compared with what the receiver needs. If the answer is positive, the link closes, and the amount by which it is positive is the margin.",
      blocks: [
        {
          kind: "equation",
          name: "EIRP — how loud the transmitter is",
          tag: "ITU RR 1.161",
          formula: "EIRP (dBW) = P (dBW) + G (dBi)",
          where: [
            { symbol: "P", meaning: "power supplied to the antenna" },
            { symbol: "G", meaning: "antenna gain in the direction of interest" },
          ],
          worked: [
            "“The product of the power supplied to the antenna and the antenna gain in a given direction relative to an isotropic antenna” — the Radio Regulations' own words. It is the number that says how loud you are <em>towards one place</em>, which is why a spot beam can be loud without the spacecraft being powerful.",
            "Do not confuse it with e.r.p. (RR 1.162), which is referred to a half-wave dipole and is 2.15 dB different.",
          ],
        },
        {
          kind: "equation",
          name: "G/T — how good the receiver is",
          tag: "IEEE Std 145 · ITU-R S.733-2",
          formula: "G/T (dB/K) = G (dBi) − 10 log₁₀ T (K)",
          where: [
            { symbol: "G", meaning: "receive antenna gain" },
            { symbol: "T", meaning: "system noise temperature, kelvin" },
          ],
          worked: [
            "One number for a whole receiving station, because gain alone is not the story: a big antenna pointed at hot ground can be worse than a small one pointed at cold sky.",
            "The subtlety worth getting right: G/T is <em>invariant</em> under a change of reference plane, provided G and T are referred to the same plane — a loss ahead of the plane lowers G and raises T by the same factor. The real error is quoting G at the feed and T at the receiver input.",
          ],
        },
        {
          kind: "equation",
          name: "Free-space path loss",
          tag: "ITU-R P.525-5",
          formula: "L (dB) = 92.45 + 20 log₁₀ f(GHz) + 20 log₁₀ d(km)",
          where: [
            { symbol: "f", meaning: "frequency, GHz" },
            { symbol: "d", meaning: "path length, km" },
            { symbol: "92.45", meaning: "the exact constant for these units" },
          ],
          worked: [
            "ITU-R P.525-5 prints the MHz-and-km form as <code>32.4 + 20 log f(MHz) + 20 log d(km)</code>. Computed exactly from c, the constant is 32.4478, so the widely copied “32.44” is a truncation and is wrong in the second decimal place; the km-and-GHz constant is <code>92.4478</code>.",
            "A GEO downlink at 12 GHz over 38,000 km loses <code>92.45 + 21.6 + 91.6 = 205.6 dB</code>. That is a factor of 3.6×10²⁰, and it is why every other term in the budget is fought over.",
            "Note what this loss is <em>not</em>: nothing is absorbed. It is spreading — the same power over an ever-larger sphere. Absorption by rain and atmosphere is a separate term added on top.",
          ],
        },
        {
          kind: "equation",
          name: "Carrier to noise density",
          tag: "ITU Handbook on Satellite Communications",
          formula: "C/N₀ = EIRP + G/T − L + 228.6",
          where: [
            { symbol: "C/N₀", meaning: "carrier power over noise power density, dB·Hz" },
            { symbol: "L", meaning: "all losses on the path, dB" },
            { symbol: "228.6", meaning: "−10 log₁₀ k, with k = 1.380649×10⁻²³ J/K" },
          ],
          worked: [
            "Boltzmann's constant has been exact by SI definition since 2019, and 10 log₁₀ k = −228.599 dBW/K/Hz, so the familiar 228.6 is right to a thousandth of a decibel.",
            "From here, <code>C/N = C/N₀ − 10 log B</code> for a bandwidth B, and <code>C/N₀ = Eb/N₀ + 10 log R</code> for a data rate R. Those three relations are most of practical link design.",
          ],
        },
        {
          kind: "terms",
          items: [
            {
              term: "Link margin",
              note: "not a safety factor",
              body: "The decibels by which the received C/N₀ exceeds what the waveform needs for its required error rate. It is a statistical statement about availability, not a fudge.",
              operational: "The “3 dB rule of thumb” comes from S- and X-band deep-space practice and does not carry to Ku, Ka or optical, where the fade statistics have far longer tails. NASA's Deep Space Network sizes to 2σ on the downlink and 3σ on the uplink instead.",
            },
            {
              term: "Rain fade",
              note: "ITU-R P.838-3, P.618-14",
              body: "Specific attenuation γ = k·R^α dB per kilometre, with k and α tabulated per frequency and polarization. It rises steeply with frequency, which is why Ka systems are engineered around weather rather than despite it.",
              operational: "At 30 mm/h and 30° elevation, specific attenuation runs about 1.2 dB/km at 12 GHz, 3.0 at 20 GHz and 5.6 at 30 GHz. Any single “Ku loses X dB” figure is meaningless without a site and an elevation angle: ITU's method needs local rain statistics, rain height, latitude and elevation before it produces a number.",
            },
            {
              term: "Gateway diversity",
              body: "Two gateways far enough apart that the same storm cannot be over both. It is how V-band feeder links are made to work at all, because no achievable margin covers those fades.",
            },
          ],
        },
      ],
    },
    {
      kicker: "POLARIZATION",
      title: "Which way the wave is oriented, and what the ionosphere does to it.",
      lead: "Polarization is a free doubling of capacity when it holds, and the single most instructive failure on this site when it does not — because what breaks it is the same plasma the explorer draws.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Linear and circular",
              body: "Linear polarization holds a fixed orientation, so two orthogonal linear signals can share a frequency. Circular polarization rotates as it propagates and comes in right-hand and left-hand senses, which also form an orthogonal pair.",
            },
            {
              term: "XPD and XPI",
              note: "ITU-R P.310-11 · not synonyms",
              body: "Cross-polar discrimination is the ratio of wanted to unwanted polarization for <em>one</em> transmitted signal. Cross-polar isolation is the ratio when two orthogonal signals are transmitted at the same frequency and power — which is what a frequency-reuse pair actually is.",
              operational: "The industry uses the two interchangeably. They are answers to different questions, and only XPI describes an operating dual-polarization link.",
            },
            {
              term: "Faraday rotation",
              note: "goes as 1/f²",
              body: "Free electrons in the ionosphere, threaded by Earth's magnetic field, rotate the plane of a linearly polarized wave. The rotation is proportional to total electron content and inversely proportional to the square of the frequency.",
              operational: "This is why links below roughly 3 GHz that must cross the ionosphere use circular polarization. Circular polarization is unaffected in orientation — the rotation moves a linear wave off the receiving antenna, but a circular wave is still circular.",
            },
            {
              term: "You cannot fix it by rotating the feed",
              note: "ITU-R P.618-14",
              body: "Seen from the earth station, the plane rotates in the <em>same</em> direction on the uplink and the downlink. So if one antenna does both, no mechanical rotation of the feed can compensate for both at once.",
            },
          ],
        },
        {
          kind: "equation",
          name: "Faraday rotation",
          tag: "ITU-R P.531-16, eq. 4",
          formula: "θ = 2.36 × 10⁻¹⁴ · B_av · N_T / f²",
          where: [
            { symbol: "θ", meaning: "rotation angle, radians" },
            { symbol: "B_av", meaning: "average field along the path, tesla (≈50 µT)" },
            { symbol: "N_T", meaning: "total electron content, electrons per m²" },
            { symbol: "f", meaning: "frequency, GHz" },
          ],
          worked: [
            "ITU-R P.531-16 tabulates a maximum of <b>108° at 1 GHz</b> for a 30° elevation path and a vertical TEC of 10¹⁸ el/m². Scaling that same row by 1/f² gives roughly <b>1,200°</b> at 300 MHz — more than three complete rotations — and about <b>0.27°</b> at 20 GHz.",
            "So the answer to “does Faraday rotation matter?” is entirely a question of band. At military UHF it is catastrophic for a linear link and the band uses circular polarization throughout. At Ka it is a rounding error.",
            "The polarization loss follows as <code>XPD = −20 log₁₀(tan θ)</code>: one degree of rotation costs 35 dB of discrimination, 45° costs all of it.",
          ],
        },
        {
          kind: "terms",
          items: [
            {
              term: "Group delay and the TEC/f² term",
              body: "The same free electrons delay the modulation. The first-order delay is proportional to TEC and to 1/f², which is exactly why dual-frequency GNSS receivers can measure and remove most of it and single-frequency ones cannot.",
            },
            {
              term: "Scintillation",
              note: "the one margin cannot always fix",
              body: "Small-scale irregularities in the plasma make the amplitude and phase of a signal fluctuate rapidly. It is worst near the magnetic equator after sunset and at high latitudes during disturbed conditions.",
              operational: "Deep amplitude fades can break a receiver's carrier lock even when the average signal level is healthy, so a link with plenty of margin can still drop. This is the failure mode that most often gets reported as “equipment fault” and is not one.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Switch on <em>Ionosphere — electron density</em> and <em>TEC surface</em> in the layer list. TEC is the quantity in both equations above — the number that sets Faraday rotation and the number that sets GNSS delay — and it is being drawn from an assimilated model on the globe in front of you.",
            "Then switch on <em>D-region HF absorption</em>. That layer is the same physics one storey lower and one band down: the D region absorbs rather than refracts, and it is what takes HF away during a flare.",
          ],
          goto: { label: "Open the layer pages →", view: "learn-layers" },
        },
      ],
    },
  ],
  sources: [
    { ref: "1", title: "IEEE Std 521-2019, Letter Designations for Radar-Frequency Bands", where: "HF 3–30 MHz through mm 110–300 GHz. Note IEEE has no Q band, and defines mm as 110–300 GHz where popular usage says 30–300", url: "https://standards.ieee.org/standard/521-2019.html" },
    { ref: "2", title: "ITU Radio Regulations, Edition of 2024, Article 5 and 47 CFR §25.202", where: "the FSS/MSS allocations quoted for C, X, Ku, Ka, L, S and Q/V. The ITU allocates by frequency and direction and never by band letter", url: "https://www.law.cornell.edu/cfr/text/47/25.202" },
    { ref: "3", title: "MIL-STD-188-181A, Interoperability Standard for Single Access 5-kHz and 25-kHz UHF Satellite Communications Channels", where: "§5.1.1.5 / §5.1.2.2: transmit 291.000–318.000 MHz, receive 243.000–270.000 MHz, 5 kHz increments" },
    { ref: "4", title: "NTIA Compendium, 225–328.6 MHz", where: "FLTSATCOM/UFO channel plan; UFO 39 channels totalling 555 kHz; MUOS bands 243.525–270.05 and 280–320 MHz", url: "https://www.ntia.gov/files/ntia/publications/compendium/0225.00-0328.60_01DEC15.pdf" },
    { ref: "5", title: "Oetting & Jen, The Mobile User Objective System, Johns Hopkins APL Technical Digest 30(2), 2011", where: "MUOS legacy payload 292–318/244–270 MHz; WCDMA payload 300–320 MHz up, 360–380 MHz down, four 5 MHz channels over 16 beams; Ka feeder links to four radio access facilities", url: "https://www.jhuapl.edu/sites/default/files/2024-09/30-02-Oetting.pdf" },
    { ref: "6", title: "ITU-R P.525-5 (11/2024), Calculation of free-space attenuation", where: "eq. (6). The exact constants are 32.4478 (MHz, km) and 92.4478 (GHz, km)", url: "https://www.itu.int/rec/R-REC-P.525/en" },
    { ref: "7", title: "ITU Handbook on Satellite Communications, 3rd ed. (R-HDB-42, 2002), §2.3", where: "the C/N₀ link equations and the 228.6 term", url: "https://www.itu.int/dms_pub/itu-r/opb/hdb/R-HDB-42-2002-PDF-E.pdf" },
    { ref: "8", title: "NIST/CODATA (SI, 2019)", where: "k = 1.380649×10⁻²³ J/K exactly, giving −228.599 dBW/K/Hz" },
    { ref: "9", title: "ITU-R P.838-3 and ITU-R P.618-14 (08/2023)", where: "γR = k·R^α; rain attenuation and XPD prediction, valid 6–55 GHz", url: "https://www.itu.int/rec/R-REC-P.618/en" },
    { ref: "10", title: "ITU-R P.531-16 (09/2025), Ionospheric propagation data and prediction methods", where: "eq. (4) Faraday rotation with f in GHz; eq. (5) XPD = −20 log(tan θ); Table 3, 108° at 1 GHz for TEC 10¹⁸ el/m² at 30° elevation", url: "https://www.itu.int/rec/R-REC-P.531/en" },
    { ref: "11", title: "ITU-R P.310-11 (09/2025)", where: "the formal and different definitions of XPD and XPI" },
    { ref: "12", title: "Cheung, The Role of Margin in Link Design and Optimization, NASA/JPL", where: "margin as a statistical availability statement; the 3 dB rule of thumb does not extend to Ku/Ka/optical; DSN 2σ downlink, 3σ uplink" },
  ],
};

// ---------------------------------------------------------------------------
// CHAPTER 04 — CHANGING AN ORBIT
//
// Every Δv on this page is computed by hohmann(), planeChange() and
// combinedBurn() above, at render time, from μ and R⊕. None is typed in.
// tests/satellite-fundamentals.test.ts re-derives the same numbers from the
// closed-form expressions and fails if the rendered strings disagree.
// ---------------------------------------------------------------------------

/** Built at render time so the prose and the diagram cannot disagree. */
function manoeuvreNumbers() {
  const r1 = R_EARTH + 400;
  const transfer = hohmann(r1, GEO_RADIUS);
  const simpleAtGeo = planeChange(transfer.v2, 28.5);
  const combinedAtApogee = combinedBurn(transfer.vApogee, transfer.v2, 28.5);
  const combinedFromKourou = combinedBurn(transfer.vApogee, transfer.v2, 5.2);
  return {
    transfer,
    simpleAtGeo,
    combinedAtApogee,
    combinedFromKourou,
    separate: transfer.burn2 + simpleAtGeo,
    saving: transfer.burn2 + simpleAtGeo - combinedAtApogee,
    totalFromCape: transfer.burn1 + combinedAtApogee,
    totalFromKourou: transfer.burn1 + combinedFromKourou,
    planeChangeInLeo: planeChange(transfer.v1, 28.5),
  };
}

const CH_MANOEUVRE: Chapter = (() => {
  const n = manoeuvreNumbers();
  const f3 = (value: number) => value.toFixed(3);
  return {
    id: "manoeuvre",
    index: "04",
    title: "Changing an orbit",
    door: "Delta-v is the currency and propellant is the bank balance. Hohmann transfers with the arithmetic shown, why plane changes are so expensive, and what actually ends a satellite's life.",
    lead: "There is no steering in orbit — only burns, and each one is paid for out of a tank that is never refilled. This chapter is the arithmetic of what a manoeuvre costs and why the propellant budget, not the hardware, usually decides how long a spacecraft lives.",
    covers: [
      "delta-v as the currency",
      "the rocket equation, and what Isp buys",
      "the Hohmann transfer, computed in full",
      "bi-elliptic transfers, and when they win",
      "plane changes, and why they hurt",
      "why launch latitude is worth money",
      "GEO station-keeping, north-south and east-west",
      "disposal, graveyard orbits and the five-year rule",
    ],
    sections: [
      {
        kicker: "THE CURRENCY",
        title: "Delta-v is the only thing a spacecraft spends.",
        lead: "Every orbit change is a change of velocity, and the sum of all the velocity changes a mission will ever need is its delta-v budget. It is decided before launch, and nothing after launch can add to it.",
        blocks: [
          {
            kind: "equation",
            name: "The Tsiolkovsky rocket equation",
            tag: "The whole economics, in one line",
            formula: "Δv = Iₛₚ · g₀ · ln( m₀ / m_f )",
            where: [
              { symbol: "Δv", meaning: "velocity change achieved, m/s" },
              { symbol: "Iₛₚ", meaning: "specific impulse, seconds" },
              { symbol: "g₀", meaning: "9.80665 m/s², exactly, by definition" },
              { symbol: "m₀ / m_f", meaning: "mass before the burn over mass after" },
            ],
            worked: [
              "The logarithm is the cruelty in it. Doubling the propellant does not double the Δv; it adds one more factor of e's worth. Wanting more Δv from the same engine means the mass ratio has to grow exponentially.",
              `To find <code>1.5 km/s</code> of Δv: a hydrazine monopropellant system at Iₛₚ ≈ 220 s must be <code>${(propellantFraction(1.5, 220) * 100).toFixed(0)}%</code> propellant by mass. A bipropellant apogee engine at 320 s needs <code>${(propellantFraction(1.5, 320) * 100).toFixed(0)}%</code>. A Hall-effect thruster at 1,600 s needs <code>${(propellantFraction(1.5, 1600) * 100).toFixed(0)}%</code>, and a gridded ion engine at 3,000 s needs <code>${(propellantFraction(1.5, 3000) * 100).toFixed(0)}%</code>.`,
              "That is the entire case for electric propulsion, and also its entire cost: the same Δv for a fifth of the mass, delivered over months of thrusting at millinewtons instead of minutes at kilonewtons.",
            ],
          },
          {
            kind: "terms",
            items: [
              { term: "Chemical monopropellant", note: "Iₛₚ ≈ 220–235 s", body: "Hydrazine over a catalyst bed. Simple, reliable, immediate, and thirsty. Still the standard for attitude control and small corrections." },
              { term: "Bipropellant apogee engine", note: "Iₛₚ ≈ 317–320 s", body: "MMH and nitrogen tetroxide, the classic GEO circularisation engine. One big burn, once, at apogee." },
              { term: "Hall-effect thruster", note: "Iₛₚ ≈ 1,600 s", body: "Electric. Around 80 mN of thrust at a few kilowatts, so a GEO transfer takes months instead of hours — and the spacecraft crosses the radiation belts slowly on the way, which is a real design cost." },
              { term: "Gridded ion", note: "Iₛₚ ≈ 1,900–4,190 s", body: "Higher exhaust velocity again, lower thrust again. NSTAR flew at 1,900–3,100 s; NEXT reaches 4,190 s." },
            ],
          },
        ],
      },
      {
        kicker: "THE STANDARD MOVE",
        title: "The Hohmann transfer, worked in full.",
        lead: "Two burns, half an ellipse between them, and it is the cheapest two-impulse path between circular orbits over the range of ratios that covers almost every real mission.",
        blocks: [
          { kind: "figure", svg: figureHohmann(), chip: "schematic", chipNote: "Δv figures computed from μ; orbit radii not to scale", caption: "Both burn figures are computed at page-render time from vis-viva and the WGS-84 μ. The circles are not to scale — at true scale, the 400 km orbit would be indistinguishable from Earth." },
          {
            kind: "equation",
            name: "The two burns",
            tag: "Coplanar, circular to circular",
            formula: "Δv₁ = √(μ/r₁) · ( √(2r₂/(r₁+r₂)) − 1 )\nΔv₂ = √(μ/r₂) · ( 1 − √(2r₁/(r₁+r₂)) )",
            where: [
              { symbol: "r₁", meaning: "starting circular radius" },
              { symbol: "r₂", meaning: "target circular radius" },
              { symbol: "Δv₁", meaning: "raise apogee to r₂" },
              { symbol: "Δv₂", meaning: "circularise there" },
            ],
            worked: [
              `From a 400 km circular orbit (r₁ = 6,778.137 km) to geostationary radius (r₂ = 42,164.170 km): <code>Δv₁ = ${f3(n.transfer.burn1)} km/s</code>, <code>Δv₂ = ${f3(n.transfer.burn2)} km/s</code>, total <code>${f3(n.transfer.total)} km/s</code>, with a coast of <code>${n.transfer.transferHours.toFixed(2)} hours</code>.`,
              "Assumptions, stated because they matter: two-body gravity only, impulsive burns, both orbits circular and in the same plane, no drag, no oblateness. A real GTO mission adds finite-burn losses and, above all, the plane change below.",
              "The transfer ellipse has e = " + n.transfer.eccentricity.toFixed(3) + ". Without the second burn the spacecraft returns to a 400 km perigee every 10.5 hours indefinitely — the first burn does not put anything in geostationary orbit, it only makes the spacecraft <em>visit</em> that altitude.",
            ],
          },
          {
            kind: "terms",
            single: true,
            items: [
              {
                term: "The bi-elliptic transfer, and where it beats Hohmann",
                note: "three burns, one of them absurdly far out",
                body: "Go far <em>past</em> the target, change the orbit cheaply where the speed is tiny, then come back down. It sounds wasteful and for large radius ratios it is not: Hohmann is always cheaper for r₂/r₁ below 11.94, bi-elliptic is always cheaper above 15.58, and in between the answer depends on how far out the intermediate apogee is put.",
                operational: "LEO to GEO is a ratio of about 6.2, so it is firmly Hohmann territory. Bi-elliptic pays for lunar-distance transfers and for large plane changes, where the cheap-plane-change-at-low-speed trick is the real prize — and it costs days or weeks of transfer time to collect it.",
              },
            ],
          },
        ],
      },
      {
        kicker: "THE EXPENSIVE ONE",
        title: "Changing the plane costs more than changing the orbit.",
        lead: "Raising an orbit adds to the speed you already have. Turning an orbit has to remove the velocity you had and replace it with a differently pointed one of the same size, and vector arithmetic is unforgiving about that.",
        blocks: [
          {
            kind: "equation",
            name: "A simple plane change",
            tag: "Same speed, different direction",
            formula: "Δv = 2 v · sin( Δi / 2 )",
            where: [
              { symbol: "v", meaning: "orbital speed where the burn happens" },
              { symbol: "Δi", meaning: "angle the plane is turned through" },
            ],
            worked: [
              `A 28.5° plane change at geostationary speed (${f3(n.transfer.v2)} km/s) costs <code>${f3(n.simpleAtGeo)} km/s</code>. The same 28.5° down in a 400 km orbit, where the speed is ${f3(n.transfer.v1)} km/s, costs <code>${f3(n.planeChangeInLeo)} km/s</code> — comparable to the entire Hohmann transfer to GEO.`,
              "The lesson is in the v out front: <em>turn where you are slow</em>. Δv for a plane change is directly proportional to the speed at which you attempt it, which is why the manoeuvre is done at apogee and never at perigee.",
            ],
          },
          {
            kind: "equation",
            name: "Doing both at once",
            tag: "One vector, not two",
            formula: "Δv = √( v_a² + v_c² − 2 v_a v_c cos Δi )",
            where: [
              { symbol: "v_a", meaning: "speed at transfer apogee, before the burn" },
              { symbol: "v_c", meaning: "circular speed at the target, after" },
              { symbol: "Δi", meaning: "plane change performed in the same burn" },
            ],
            worked: [
              `Circularising and turning 28.5° in a single apogee burn costs <code>${f3(n.combinedAtApogee)} km/s</code>. Doing the two separately costs ${f3(n.transfer.burn2)} + ${f3(n.simpleAtGeo)} = <code>${f3(n.separate)} km/s</code> — the combined burn saves <b>${f3(n.saving)} km/s</b>.`,
              `A realistic total from a Cape Canaveral-latitude parking orbit to geostationary is therefore about <code>${f3(n.totalFromCape)} km/s</code>: ${f3(n.transfer.burn1)} at perigee plus ${f3(n.combinedAtApogee)} at apogee.`,
              `Launch from 5.2° north instead and the same apogee burn costs ${f3(n.combinedFromKourou)} km/s. That is worth <b>${f3(n.totalFromCape - n.totalFromKourou)} km/s</b> of a GEO spacecraft's budget — which, through the rocket equation, is a large fraction of a tonne of propellant it does not have to launch. Launch-site latitude is not a geographical footnote; it is a line in the business case.`,
            ],
          },
        ],
      },
      {
        kicker: "STAYING PUT",
        title: "A geostationary slot is a place you have to keep paying for.",
        lead: "Nothing about geostationary orbit is stable. Left alone, a spacecraft drifts out of its longitude box and its inclination grows by roughly a degree a year, so “stationkeeping” is a continuous, budgeted expense.",
        blocks: [
          {
            kind: "terms",
            items: [
              {
                term: "North-south: fighting the Sun and Moon",
                note: "≈ 45–50 m/s per year",
                body: "Lunar and solar gravity pull the orbit plane away from the equator at about 0.75–0.95° per year. Correcting it is roughly 95% of the whole station-keeping budget.",
                operational: "It is also the first thing an operator gives up. Stop north-south keeping and a spacecraft can serve tracking-antenna customers for years longer on the propellant saved — as an inclined GSO satellite tracing a growing figure-of-eight.",
              },
              {
                term: "East-west: fighting the shape of the Earth",
                note: "a few m/s per year",
                body: "Earth's equator is slightly elliptical, so a geostationary spacecraft is pulled towards one of two stable longitudes at 75.3° E and 105.3° W. The two unstable points are 165.3° E and 14.7° W.",
                operational: "A satellite that runs out of propellant does not stay in its slot. It drifts, oscillating about the nearest stable point — which is why those two longitudes are the busiest places in the graveyard as well as in the operational belt.",
              },
              {
                term: "This project has measured one",
                note: "from its own element archive",
                body: "Streaming the whole orbit archive, this site's manoeuvre detector recovered a repeating cluster of <b>16 east-west corrections of 0.041 m/s every 14.5 days</b> on INTELSAT 33E — <b>5.6 m/s per year</b>, from published element sets alone.",
                operational: "It sits above the pure triaxiality figure because a real east-west budget also carries eccentricity control against solar radiation pressure. The point is that the budget is recoverable from public data: the spacecraft's housekeeping is visible in its own ephemeris.",
              },
            ],
          },
          {
            kind: "facts",
            items: [
              { value: "≈50 m/s/yr", caption: "GEO north-south station keeping — most of the budget" },
              { value: "0.041 m/s", caption: "one measured INTELSAT 33E east-west correction" },
              { value: "14.5 days", caption: "the interval between them, recovered from elements" },
              { value: "5.6 m/s/yr", caption: "that spacecraft's measured east-west budget" },
            ],
          },
        ],
      },
      {
        kicker: "THE END",
        title: "Propellant is the real design life, and disposal is now a rule.",
        lead: "Solar arrays degrade and electronics accumulate dose, but the thing that usually ends a mission is an empty tank — and what happens next is no longer left to the operator.",
        blocks: [
          {
            kind: "terms",
            items: [
              {
                term: "The GEO graveyard",
                note: "IADC: 235 km + 1000·C_R·A/m",
                body: "A retiring geostationary spacecraft must raise its perigee by at least that amount above the protected region and leave eccentricity below 0.003. The 235 km is 200 km of protected region plus 35 km of allowance for how far lunisolar and geopotential effects can push it back down.",
                operational: "The manoeuvre has to be planned while there is still propellant to do it, which means an operator has to decide to end a working satellite's revenue-earning life early. That tension is exactly why the requirement is written down.",
              },
              {
                term: "LEO disposal: 25 years, then five",
                note: "IADC/ISO 24113, then FCC 22-74",
                body: "The long-standing guideline was a residual orbital lifetime of 25 years or less, with 90% disposal reliability. The FCC adopted a five-year rule on 29 September 2022; it applies to spacecraft launched after 29 September 2024.",
              },
              {
                term: "Or let drag do it",
                note: "the altitude ladder",
                body: "Below about 600 km the atmosphere disposes of a spacecraft without help: roughly a day at 200 km, a month at 300 km, a year at 400 km, a decade at 500 km, and a century at 700 km — strongly dependent on mass-to-area and on where the solar cycle is.",
                operational: "This is the real reason large constellations are flown low. At 550 km, compliance is a property of the altitude rather than a manoeuvre that has to work at end of life.",
              },
              {
                term: "Passivation",
                body: "Vent the tanks, discharge the batteries, disable the pressure vessels. Most catalogued debris-generating events are explosions of retired hardware, not collisions, and passivation is what prevents them.",
              },
            ],
          },
          {
            kind: "live",
            body: [
              "Choose <em>GEO</em> on the orbit-class control, then the <em>Other GSO</em> sub-filter. What separates those spacecraft from the <em>Geostationary</em> set is largely the propellant question above: inclination that is no longer being paid for.",
              "The satellite card also carries this project's orbit archive for objects it holds history on — the same archive the INTELSAT 33E figures above came out of.",
            ],
            goto: { label: "Back to the explorer →", view: "explore" },
          },
        ],
      },
    ],
    sources: [
      { ref: "1", title: "NIMA TR8350.2 (WGS-84)", where: "μ = 398,600.4418 km³/s², R⊕ = 6,378.137 km — the only two inputs to every Δv on this page" },
      { ref: "2", title: "Vallado, Fundamentals of Astrodynamics and Applications, 4th ed., ch. 6", where: "Hohmann and bi-elliptic transfer formulations; the 11.94 and 15.58 radius-ratio thresholds; simple and combined plane changes" },
      { ref: "3", title: "CGPM 1901", where: "g₀ = 9.80665 m/s², exact by definition" },
      { ref: "4", title: "Goebel & Katz, Fundamentals of Electric Propulsion, JPL/DESCANSO", where: "SPT-100 Hall thruster ≈1,600 s at 300 V; NSTAR 1,900–3,100 s; NEXT to 4,190 s", url: "https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel_09_Chap9_Flight.pdf" },
      { ref: "5", title: "Soop, Handbook of Geostationary Orbits (ESA/Kluwer)", where: "north-south ≈45–50 m/s/yr from lunisolar perturbation; east-west from J₂₂ triaxiality; stable longitudes 75.3° E and 105.3° W, unstable 165.3° E and 14.7° W" },
      { ref: "6", title: "IADC-02-01 Rev. 2, §5.3.1–5.3.2", where: "GEO disposal perigee raise of 235 km + (1000 × C_R × A/m) with e ≤ 0.003; LEO residual lifetime ≤ 25 years with ≥90% disposal reliability", url: "https://orbitaldebris.jsc.nasa.gov/library/iadc-space-debris-guidelines-revision-2.pdf" },
      { ref: "7", title: "FCC 22-74, Second Report and Order, IB Docket Nos. 22-271 and 18-313", where: "five-year post-mission disposal, adopted 29 September 2022; applies to spacecraft launched after 29 September 2024", url: "https://docs.fcc.gov/public/attachments/FCC-22-74A1.pdf" },
      { ref: "8", title: "Australian Space Weather Service, Satellite Orbital Decay Calculations", where: "the order-of-magnitude lifetime ladder from 200 km to 900 km, which scales with mass-to-area ratio and solar activity", url: "https://www.sws.bom.gov.au/Category/Educational/Space%20Weather/Space%20Weather%20Effects/SatelliteOrbitalDecayCalculations.pdf" },
      { ref: "9", title: "This project's own orbit-manoeuvre archive", where: "INTELSAT 33E: 33 corrections in 336 days including a repeat cluster of 16 east-west burns at 0.041 m/s every 14.5 days, 5.6 m/s/yr, recovered from published element sets. Method and false-alarm rate in docs/orbit-history-design.md" },
    ],
  };
})();

// ---------------------------------------------------------------------------
// CHAPTER 05 — THE SPACECRAFT ITSELF
//
// Absorbs old module 10 (constellation trades), which belongs here: a
// constellation is a fleet-level answer to the same coverage question one
// spacecraft's design answers at the unit level.
//
// Two terminology traps are stated rather than smoothed over: ECSS has no
// "bus" (its word is platform, or service module), and SMAD does not list
// propulsion among the subsystems in its subsystems chapter. The familiar
// seven-item list is a convention, not a normative one, and saying so is
// cheaper than being caught by someone who has the standards open.
// ---------------------------------------------------------------------------

const CH_SPACECRAFT: Chapter = {
  id: "spacecraft",
  index: "05",
  title: "Payload and bus",
  door: "What a satellite is for, and everything that exists only to keep that working. The subsystems, the budgets they fight over, and what actually decides design life.",
  lead: "Every spacecraft splits into the part that does the mission and the part that keeps the first part alive, pointed, powered and in contact. Almost every engineering argument on a programme is about how much of the second the first can afford.",
  covers: [
    "payload vs bus, and what ECSS calls them",
    "all the bus subsystems, one at a time",
    "mass and power budgets",
    "eclipse, and why batteries are sized by it",
    "what really ends a mission",
    "constellation trades",
  ],
  sections: [
    {
      kicker: "THE SPLIT",
      title: "One part is the reason. The rest is the price.",
      blocks: [
        { kind: "figure", svg: figurePayloadBus(), chip: "schematic", chipNote: "Organisational diagram · subsystem list is conventional", caption: "The eight boxes on the right are the conventional list. There is no single normative one: ECSS calls the whole right-hand side the <em>platform</em> or service module and has no term “bus” at all, and SMAD's subsystems chapter does not include propulsion." },
        {
          kind: "terms",
          items: [
            {
              term: "Payload",
              note: "ECSS-S-ST-00-01C: “performs the user mission”",
              body: "The transponders and antennas, the imager, the radar, the navigation clock, the science instrument. Change it and you have a different mission on the same platform.",
              operational: "It is also the commercial boundary. Buses are reused across many missions and amortised; payloads generally are not.",
            },
            {
              term: "Bus / platform / service module",
              body: "Everything else. It exists entirely to deliver power, temperature, pointing, orbit and a link to the payload, and its own success criterion is that nobody notices it.",
            },
            {
              term: "How much of the spacecraft is the payload?",
              note: "28.7% of dry mass, σ = 6.2%",
              body: "Measured across 17 large GEO, navigation and observation satellites of roughly 500–2,000 kg dry mass. Navigation spacecraft run low at 20–23%; observation spacecraft run high at 31–41%.",
              operational: "Turned round: dry mass ≈ 3.5 × payload mass. Add a kilogram of instrument and you have committed to about three and a half kilograms of spacecraft before propellant.",
            },
          ],
        },
      ],
    },
    {
      kicker: "THE SUBSYSTEMS",
      title: "What each one is for, and what it is fighting.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Structure and mechanisms",
              body: "Carries launch loads — the most violent minutes of the spacecraft's life — then deploys arrays, antennas and instrument covers once. Deployments are single-shot, untestable in full gravity, and a recurring cause of total mission loss.",
            },
            {
              term: "Electrical power (EPS)",
              note: "arrays, batteries, regulation",
              body: "Triple-junction solar cells reach about 29–31% at beginning of life under AM0. The array is sized for the <em>end</em> of life, after radiation has taken its cut, so it is oversized for most of the mission.",
              operational: "Measured on-orbit GEO degradation is 0.44–1.03%/yr for gallium arsenide and 0.71–1.69%/yr for silicon. The old “25% over ten years” design rule is conservative for silicon and not a measurement.",
            },
            {
              term: "Thermal control",
              body: "There is no air, so heat leaves only by radiation. Radiators, multilayer insulation, coatings, heat pipes and heaters hold every box inside its qualified range through full sun and full eclipse.",
              operational: "Thermal is usually the subsystem that constrains where things can be mounted, and it is why a spacecraft's outside is mostly a decision about what faces the Sun.",
            },
            {
              term: "Attitude determination and control (ADCS)",
              body: "Knows which way it is pointing — star trackers, sun sensors, gyros, magnetometers — and changes it with reaction wheels, magnetic torquers or thrusters. Pointing accuracy is usually a payload requirement flowed down.",
              operational: "Reaction wheels saturate and must be desaturated against something external, so an ADCS design is partly a propellant question.",
            },
            {
              term: "Propulsion",
              body: "The only thing that can change the orbit. Chemical for speed, electric for efficiency, and the subject of the previous chapter.",
            },
            {
              term: "Command and data handling (C&DH)",
              body: "The onboard computer, the data bus and the mass memory. It runs the timeline, collects telemetry, and has to keep working in an environment that flips its memory bits.",
            },
            {
              term: "TT&C — telemetry, tracking and command",
              note: "usually S-band",
              body: "The link that flies the spacecraft, kept deliberately separate from the payload link so that a payload failure does not cost control. It is also how ranging is done for orbit determination.",
              operational: "It is designed to work when everything else has failed: omnidirectional low-gain antennas, low rates, and a safe mode that points the arrays at the Sun and waits.",
            },
            {
              term: "Guidance and navigation",
              body: "Where the spacecraft is, as opposed to which way it is facing. On most LEO spacecraft this is now a GNSS receiver, which makes the previous chapter's PNT material part of the bus.",
            },
          ],
        },
      ],
    },
    {
      kicker: "THE BUDGETS",
      title: "Mass, power and the worst orbit night of the year.",
      lead: "Everything on a spacecraft is traded against everything else through two ledgers that must both balance, and the harder of the two is usually decided by eclipse.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "The mass budget",
              body: "Launch capacity to a given orbit is fixed and bought in advance, so mass is a hard ceiling with margin held centrally and released as the design matures. Growth is normal, expected, and planned for.",
            },
            {
              term: "The power budget",
              body: "Array output at end of life, in the worst Sun geometry, must cover every load that can be on at once — with the battery covering everything that must run through eclipse.",
            },
            {
              term: "GEO eclipse seasons",
              note: "≈45 days, twice a year",
              body: "Around each equinox — roughly 26 February to 12 April and 31 August to 16 October — a geostationary spacecraft passes through Earth's shadow once a day, about 90 times a year in all.",
              operational: "The worst case is <b>69.6 minutes</b> of umbra, or <b>71.5 minutes</b> including penumbra. NOAA quotes “up to 72 minutes” for GOES as an operator's round number. That single worst night, at end of life, after the battery has aged, sizes the battery for the whole mission.",
            },
            {
              term: "The solar constant",
              note: "1,366.1 W/m² for engineering",
              body: "ASTM E490 fixes the AM0 engineering value at 1,366.1 W/m². The best physical measurement of total solar irradiance is lower — 1,360.8 ± 0.5 W/m² — and the difference is instrument scattered light, not a change in the Sun.",
              operational: "Solar-cell datasheets normalise to different AM0 constants, so two efficiency figures are not directly comparable until you check which constant each one used.",
            },
          ],
        },
      ],
    },
    {
      kicker: "LIFETIME",
      title: "What actually ends a mission.",
      lead: "Three candidates compete: the tank, the arrays and batteries, and accumulated radiation dose. For the class of spacecraft where there is good evidence, the answer is usually the tank.",
      blocks: [
        {
          kind: "terms",
          single: true,
          items: [
            {
              term: "Propellant, for geostationary communications satellites",
              body: "The defensible version of the claim, and it has an existence proof: an entire commercial sector — life-extension servicing — is built on spacecraft that are “still functional but lost the ability to modify or maintain orbit due to propellant exhaustion”. MEV-1 docked with Intelsat 901 in February 2020 and undocked in April 2025, having flown a satellite whose only problem was an empty tank.",
              operational: "Propellant gauging error at end of life can be worth months of remaining life, which is why the disposal manoeuvre is planned with margin nobody wants to spend.",
            },
            {
              term: "Total ionizing dose, for the electronics",
              body: "Dose accumulates for the whole mission and its effects are “mainly an issue at end of life… often preceded by gradual degradation”. It sets the parts list on day one and is not a thing that can be fixed later.",
            },
            {
              term: "Arrays and batteries — a sizing driver, not usually the executioner",
              body: "Because they are sized to close the budget at end of life, degradation is designed for rather than survived. It becomes the limiter when a mission is extended past its design life, which is common.",
            },
            {
              term: "Do not over-rank these",
              note: "an honest gap",
              body: "There is no standards document that ranks the three across all spacecraft classes, and this page will not invent one. The GEO communications case above is the one with clear published evidence behind it.",
            },
          ],
        },
      ],
    },
    {
      kicker: "FLEETS",
      title: "A constellation is one answer to a question a single satellite cannot answer.",
      lead: "Coverage, revisit and latency are geometry problems, and past a certain point the only way to solve them is more spacecraft in more planes — which converts a spacecraft design problem into a manufacturing and replenishment problem.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Planes and phasing",
              body: "How many orbital planes, how they are spread in right ascension, and where each spacecraft sits within its plane. Those three choices set continuity of coverage far more than the total count does.",
            },
            {
              term: "Altitude buys coverage and costs everything else",
              body: "Higher means each spacecraft sees more, so fewer are needed — and means more path loss, more latency, more radiation and a disposal problem that drag will not solve for you.",
            },
            {
              term: "Replenishment is part of the design",
              note: "the trade most often left out",
              body: "A constellation of hundreds of short-lived spacecraft is a production line and a launch cadence as much as a spacecraft. A constellation of four long-lived ones is a very different business with a very different failure mode.",
              operational: "PNT, broadband LEO, weather and missile warning make almost opposite trades here, and each of them is right for its own requirement.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Open the <em>Mission Types</em> list, tick <em>navigation</em>, and switch between GPS, Galileo, BeiDou and GLONASS — four answers to one coverage problem, with visibly different plane counts and inclinations. Then clear the filter and select Starlink, and the trade goes the other way entirely.",
            "Leave geometry on <em>Orbit</em> for the plane structure, then switch to <em>Footprint</em> to see why the counts differ so much.",
          ],
          goto: { label: "Back to the explorer →", view: "explore" },
        },
      ],
    },
  ],
  sources: [
    { ref: "1", title: "ECSS-S-ST-00-01C Rev. 1 (2023), Glossary of terms", where: "payload defined as the “set of instruments or equipment which performs the user mission”; ECSS uses platform / service module rather than “bus”", url: "https://ecss.nl/" },
    { ref: "2", title: "NASA, Basics of Space Flight, ch. 11; Wertz & Larson, Space Mission Analysis and Design, 3rd ed., ch. 11 and ch. 17", where: "the subsystem list. Note SMAD places propulsion in ch. 17, outside its subsystems chapter — the seven-subsystem list is a convention", url: "https://science.nasa.gov/learn/basics-of-space-flight/chapter11-1/" },
    { ref: "3", title: "Zandbergen, Spacecraft mass and power budgets, TU Delft AE1222-II Reader 1222 (2013–14), Table 1", where: "payload mass fraction 28.7% ± 6.2% of dry mass over 17 large spacecraft; dry mass ≈ 3.48 × payload" },
    { ref: "4", title: "Spectrolab XTJ Prime, AZUR 3G30C-Advanced and Rocket Lab ZTJ datasheets; Front. Phys. 8:631925 (2020)", where: "triple-junction AM0 efficiencies 29.0–30.7% at beginning of life. Datasheets normalise to different AM0 constants" },
    { ref: "5", title: "ASTM E490-00a(2019); Kopp & Lean (2011), Geophys. Res. Lett. 38, L01706", where: "engineering solar constant 1,366.1 W/m² (AM0); measured total solar irradiance 1,360.8 ± 0.5 W/m²" },
    { ref: "6", title: "Lohmeyer, Aniceto, Cahoy & Carlton (2018), Int. J. Space Science and Engineering 5(1), 61–81", where: "measured on-orbit GEO array degradation: GaAs 0.44–1.03%/yr, Si 0.71–1.69%/yr across 11 spacecraft" },
    { ref: "7", title: "Maral, Bousquet & Sun, Satellite Communications Systems, 5th ed., §2.2 and §2.3.4.8", where: "GEO eclipse seasons 26 Feb–12 Apr and 31 Aug–16 Oct, ~90 per year, maximum 69.6 min umbral / 71.5 min with penumbra; north-south 43–48 m/s/yr vs east-west 1–5 m/s/yr" },
    { ref: "8", title: "NOAA OSPO, GOES eclipse operations", where: "the operator's round figure of “up to 72 minutes” of battery operation" },
    { ref: "9", title: "NASA, In-space Servicing, Assembly and Manufacturing State of Play 2025 (NTRS 20250008988)", where: "life-extension clients are “still functional but lost the ability to modify or maintain orbit due to propellant exhaustion”; MEV-1 / Intelsat 901, Feb 2020 – Apr 2025", url: "https://ntrs.nasa.gov/citations/20250008988" },
    { ref: "10", title: "ISWAT review, Adv. Space Res. (2024), doi:10.1016/j.asr.2024.04.018", where: "total ionizing dose as an end-of-life limiter, “often preceded by gradual degradation”" },
  ],
};

// ---------------------------------------------------------------------------
// CHAPTER 06 — THE ENVIRONMENT, AND WHAT IT DOES TO SPACECRAFT
//
// Absorbs old module 09 (plasma does not cause most orbital drag), which was
// the best of the ten and is now a section rather than a sentence.
//
// This is the chapter the rest of the site exists to support, so it carries
// the most "see it live" recipes: nearly every claim here has a layer on the
// globe that shows it being measured or modelled right now.
//
// Three corrections that this chapter deliberately gets right, because the
// commonly repeated version of each is wrong:
//   - light time is 8 min 19 s (499.005 s), not 8 min 20 s;
//   - 38 Starlink satellites were lost in February 2022, not 40 — 40 was
//     SpaceX's own forward-looking estimate at the time;
//   - SpaceX's "50%" was a DRAG increase measured by onboard GPS, not a
//     modelled density increase. The peer-reviewed density figures at the
//     210 km insertion altitude are separate, and lower.
// ---------------------------------------------------------------------------

const CH_ENVIRONMENT: Chapter = {
  id: "environment",
  index: "06",
  title: "The environment, and what it does",
  door: "Drag, solar wind and IMF, flare X-rays, energetic particles, charging, the belts and the South Atlantic Anomaly — four different messengers that break four different things.",
  lead: "Space is not empty and it is not steady. This chapter follows each thing the Sun sends, in the order it arrives, to the specific failure it causes on a specific spacecraft — and every one of them has a layer on this site's globe showing it being measured or modelled right now.",
  covers: [
    "why a solar event is not one thing",
    "X-rays, EUV, and HF radio blackout",
    "neutral drag and thermospheric expansion",
    "the February 2022 Starlink loss, in full",
    "solar wind, IMF and southward Bz",
    "SEPs and single-event effects",
    "total ionizing dose and displacement damage",
    "surface vs deep dielectric charging",
    "the radiation belts and the SAA",
    "atomic oxygen",
  ],
  sections: [
    {
      kicker: "THE FIRST IDEA",
      title: "Four messengers, four arrival times, four different things broken.",
      lead: "“There was a solar event” is not an operationally useful sentence. Light, energetic particles and coronal mass ejections leave together and arrive days apart, and the damage each one does has almost nothing in common with the others.",
      blocks: [
        { kind: "figure", svg: figureArrivalTimeline(), chip: "schematic", chipNote: "Log time axis · arrival windows from NOAA SWPC and NWS", caption: "The horizontal axis is logarithmic and has to be: eight minutes and four days cannot share a linear scale. By the time a CME arrives, the radio blackout it was launched with has been over for three days." },
        {
          kind: "facts",
          items: [
            { value: "8 min 19 s", caption: "photons: 499.005 s at 1 AU, from the exact AU and defined c" },
            { value: "½ h – hours", caption: "energetic protons, guided along the field line" },
            { value: "15–96 h", caption: "CME plasma and its shock, per NOAA SWPC" },
            { value: "15–60 min", caption: "the warning L1 actually gives you about the CME" },
          ],
        },
      ],
    },
    {
      kicker: "LIGHT",
      title: "X-rays and EUV: the part you cannot be warned about.",
      lead: "A flare's X-rays travel at the speed of light, so the flare and its first effect are simultaneous as far as anyone on Earth is concerned. The instrument that sees it and the ionosphere that responds to it are reacting to the same photons.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "The GOES flare classes",
              note: "peak W/m² in 0.1–0.8 nm",
              body: "A = 10⁻⁸, B = 10⁻⁷, C = 10⁻⁶, M = 10⁻⁵, X = 10⁻⁴ W/m², with a linear sub-class — M5 is 5×10⁻⁵. Each letter is ten times the last, so the scale is far steeper than it looks.",
              operational: "A recalibration worth knowing about: the 0.7 scaling factor SWPC applied to GOES 8–15 was removed for GOES-16 onwards, so divide the old operational XRS-B value by 0.7, increasing it by about 43%. An old GOES-15 “X2.5” is a GOES-R X3.6. Comparing flare magnitudes across that boundary without correcting is a real error.",
            },
            {
              term: "Sudden ionospheric disturbance and HF blackout",
              note: "NOAA R-scale",
              body: "X-rays ionize the dense, low D region, where collisions are frequent, so HF waves lose energy instead of refracting. The result is absorption, not reflection — the band goes quiet rather than noisy.",
              operational: "R1 (M1) is minor degradation; R3 (X1) is a wide-area blackout of the sunlit side for about an hour; R5 (X20) is complete loss of HF on the entire sunlit side for hours. It affects roughly 3–30 MHz, and it is over as quickly as it began.",
            },
            {
              term: "EUV heats the thermosphere",
              note: "tracked by F10.7",
              body: "Extreme ultraviolet is absorbed higher up and deposits heat rather than knocking out communications. The atmosphere expands, so the density at any fixed altitude rises — which is the subject of the next section.",
              operational: "The 10.7 cm solar radio flux is the standard proxy, running from below 50 to above 300 solar flux units across a cycle. It is not the EUV, it tracks it, and every drag model in operational use is driven by it.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Switch on <em>D-region HF absorption</em>. That layer is a nowcast of exactly this effect: where on the sunlit hemisphere HF is being absorbed right now, and how badly.",
            "Beside it, <em>Ionosphere — electron density</em> and <em>TEC surface</em> show the F-region response to the same photons — the region that refracts rather than absorbs, and the one GNSS has to cross.",
          ],
          goto: { label: "Open the layer pages →", view: "learn-layers" },
        },
      ],
    },
    {
      kicker: "DRAG",
      title: "The atmosphere reaches orbit, and it is not the plasma that slows you down.",
      lead: "This is the correction most worth making on the whole page. Low Earth orbit sits inside both the ionosphere and the thermosphere, and it is the neutral thermosphere — ordinary uncharged atoms and molecules — that produces essentially all the aerodynamic drag.",
      blocks: [
        {
          kind: "equation",
          name: "Drag acceleration",
          tag: "ρ here is the NEUTRAL mass density",
          formula: "a_d = − ½ ρ C_D (S/m) V²",
          where: [
            { symbol: "ρ", meaning: "neutral atmospheric mass density, kg/m³" },
            { symbol: "C_D", meaning: "drag coefficient — around 2.2 by convention, fitted in practice" },
            { symbol: "S/m", meaning: "cross-section over mass — the spacecraft's exposure" },
            { symbol: "V", meaning: "velocity relative to the atmosphere" },
          ],
          worked: [
            "Charged particles do plenty to a spacecraft — charging, single-event effects, radio propagation — but not this. Ionospheric plasma density at these altitudes is “typically an order of magnitude (or more) lower than the atmospheric neutral gas density”, so ion drag is a secondary term.",
            "The ballistic coefficient B = m/(C_D·S) collects the spacecraft's own contribution. Typical LEO values run roughly 24–120 kg/m²; an operator-measured example, the Capella “Whitney” SAR spacecraft, is 11.8 kg/m² with a fitted C_D of 2.7 rather than the 2.2 default.",
            "Watch the convention: the inverse form C_B = C_D·S/m in m²/kg is equally common in the literature, so two published “ballistic coefficients” may be reciprocals of one another.",
          ],
        },
        {
          kind: "terms",
          items: [
            {
              term: "The solar cycle moves the density by an order of magnitude",
              note: "at 400 km",
              body: "An NRLMSIS 2.0 run at equinox, quiet conditions, global mean gives 7.3×10⁻¹³ kg/m³ at solar minimum and 7.8×10⁻¹² at solar maximum — a factor of <b>10.7</b>. At 210 km the same comparison gives only <b>2.2</b>.",
              operational: "So the altitude at which a spacecraft is “safe” from drag is a function of where the cycle is, and a constellation designed at solar minimum meets a different atmosphere later.",
            },
            {
              term: "Storms heat it from underneath",
              note: "Joule heating",
              body: "Solar-wind-driven currents flowing in the high-latitude ionosphere dissipate energy through ion-neutral collisions. Averaged over 1975–2003 the budget is 464 GW of solar EUV, 95 GW of Joule heating and 36 GW of particle precipitation.",
              operational: "Joule heating is deposited low — peaking below 150 km — and the upwelling takes about six hours to show as increased density at 400 km. That delay is why a drag event is not simultaneous with the storm that caused it.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Switch on <em>Thermosphere height</em>. That is the layer this section is about: the neutral atmosphere, drawn at the altitude where it matters, expanding and contracting with the driving.",
            "It is deliberately a <em>different</em> layer from <em>Ionosphere — electron density</em>, and comparing the two is the fastest way to see that they are not the same atmosphere. One of them slows spacecraft down; the other bends radio.",
          ],
          goto: { label: "Open the layer pages →", view: "learn-layers" },
        },
      ],
    },
    {
      kicker: "THE WORKED EXAMPLE",
      title: "February 2022: a modest storm took 38 spacecraft.",
      lead: "The Starlink loss is the clearest demonstration in the record that the environment is an operational risk rather than a scientific curiosity — and that it does not take a great storm to be one.",
      blocks: [
        {
          kind: "terms",
          single: true,
          items: [
            {
              term: "What happened",
              note: "3 February 2022, 13:13 EST",
              body: "SpaceX launched 49 Starlink satellites to a deliberately low insertion with a perigee of approximately 210 km — low on purpose, so that any spacecraft failing checkout is disposed of by drag rather than by a manoeuvre. A geomagnetic storm was in progress.",
            },
            {
              term: "What SpaceX said, exactly",
              body: "“Onboard GPS suggests the escalation speed and severity of the storm caused atmospheric drag to increase up to 50 percent higher than during previous launches”, and “up to 40 of the satellites will reenter”. The spacecraft were commanded to fly edge-on to reduce drag, and most could not climb out.",
              operational: "Two precisions that matter. The 50% is an increase in <em>drag</em> measured by onboard GPS, not a modelled density increase. And 40 was a forward-looking estimate: the number actually lost was <b>38 of 49</b>.",
            },
            {
              term: "The storm was not a large one",
              note: "Kp 5.33, Dst −66 nT",
              body: "Peak planetary Kp was 5.333 — a G1 — and provisional Dst reached only −66 nT. This is a storm that would not have made the news on its own.",
              operational: "That is the whole lesson. The event was not extreme; the exposure was. A very low insertion, a low mass-to-area ratio, and a storm on the day combined into a total loss.",
            },
            {
              term: "What the models said afterwards",
              body: "WAM-IPE reproduced a 50–125% density enhancement between 200 and 400 km. Independent analyses put the increase at the 210 km insertion altitude at 20–30% against the preceding nine days, with regional peaks above 60%. NRLMSIS 2.0 predicted under 25%.",
              operational: "The operational conclusion drawn in the literature is not “the models are useless” but that empirical climatology under-predicted a storm-time response at an altitude nobody had needed it to be accurate at before.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "This site holds a <em>measured</em> replay of this event. Open <em>Historical events</em> and select the February 2022 Starlink loss: it draws real observations, not an illustration, and the Gannon 2024 event beside it carries Swarm-C accelerometer density against the model sampled along Swarm-C's own track.",
          ],
          goto: { label: "Open the historical events →", view: "events" },
        },
      ],
    },
    {
      kicker: "THE WIND",
      title: "Solar wind and the interplanetary magnetic field.",
      lead: "The Sun's outer atmosphere is not gravitationally bound, so it flows past Earth continuously, dragging its magnetic field with it. What that field is doing when it arrives decides how much of it gets in.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "What is typical",
              note: "OMNI hourly means, 1963–2016",
              body: "Speed 436 km/s, proton density 6.8 cm⁻³, field magnitude 6.28 nT. The observed ranges are enormous — 156 to 1,189 km/s, 0.4 to 62 nT — so “typical” is a weak statement about a bimodal distribution.",
              operational: "Fast wind from coronal holes runs 500–800 km/s; slow equatorial wind runs 300–500. The recurrent 27-day pattern in geomagnetic activity is coronal holes rotating back into view.",
            },
            {
              term: "Dynamic pressure sets the size of the magnetosphere",
              body: "Density times speed squared. When it rises, the dayside boundary is pushed inward, and it has on occasion been pushed inside geostationary orbit — leaving GEO spacecraft briefly outside the magnetosphere, in the shocked solar wind.",
            },
            {
              term: "Southward Bz is the switch",
              note: "Dungey (1961)",
              body: "When the arriving field points south, opposite to Earth's field at the dayside, the two can reconnect and energy and plasma are transferred into the magnetosphere. Northward Bz mostly does not.",
              operational: "It is why a fast, dense CME can arrive and do almost nothing, while a modest one with a long southward field causes a major storm. The speed is not the story on its own.",
            },
            {
              term: "L1 gives you 15 to 60 minutes",
              note: "1.5 million km upstream",
              body: "ACE and DSCOVR measure the wind about 1.5×10⁶ km sunward of Earth. At 400 km/s that is 62 minutes of warning; at 800 km/s it is 31.",
              operational: "It is the only genuine forecast in the chain — and it is a measurement of what is about to arrive, not a prediction. Everything upstream of L1 is modelling.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Switch on <em>Solar wind &amp; IMF</em>. The site draws the live NOAA measurement, including Bz, and the flow is drawn as a flow — fastest at the flanks, stagnating at the nose — rather than as a conveyor belt, because that is what a potential flow around an obstacle does.",
            "Then add <em>Magnetosphere</em> and watch the standoff distance on the card move with the dynamic pressure. That number is computed from two measured quantities, not drawn from a picture.",
          ],
          goto: { label: "Read the Dungey cycle in track 02 →", view: "learn-weather" },
        },
      ],
    },
    {
      kicker: "PARTICLES",
      title: "Energetic particles, and the four ways they break electronics.",
      lead: "A single particle can flip a bit, latch a device, or degrade a solar array permanently. Which of those happens depends on the particle's energy, what it hits, and how much aluminium is in the way.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Solar energetic particles (SEPs)",
              note: "NOAA S-scale, ≥10 MeV protons",
              body: "Protons accelerated at the flare site or by the CME shock, arriving from half an hour to several hours after the eruption. S1 begins at 10 particle flux units, S5 at 10⁵.",
              operational: "The scale is written in operational consequences: S2 “infrequent single-event upsets possible”, S3 “single-event upsets, noise in imaging systems”, S5 “satellites may be rendered useless”. Outside the belts, SEPs are the dominant radiation risk.",
            },
            {
              term: "Single event upset (SEU)",
              note: "non-destructive",
              body: "One ion changes the state of a latched logic cell. The device is undamaged and the value can be rewritten — but if nothing notices, the wrong value is used.",
              operational: "Which is why the mitigation is architectural rather than material: error-detecting memory, redundant voting, watchdogs, scrubbing.",
            },
            {
              term: "Single event transient (SET)",
              body: "A voltage spike at a node in a logic or linear circuit caused by one particle strike. Harmless if it lands between clock edges, an incorrect command if it does not.",
            },
            {
              term: "Single event latch-up (SEL)",
              note: "potentially destructive",
              body: "A parasitic thyristor structure inside a CMOS device is triggered, creating a low-impedance high-current path. Unless power is removed quickly, the part destroys itself.",
              operational: "This is the one that justifies latch-up protection circuits that cycle power on a current excursion — a design decision made years before the particle arrives.",
            },
            {
              term: "Total ionizing dose (TID)",
              note: "gray, or rad(Si)",
              body: "Cumulative ionization over the whole mission, shifting CMOS threshold voltages and raising leakage. One gray is one joule per kilogram and equals 100 rad; always state the target material, because dose in silicon is not dose in glass.",
            },
            {
              term: "Displacement damage dose (DDD)",
              body: "Non-ionizing energy that knocks atoms out of the crystal lattice. It is what degrades solar cells, CCDs and optocouplers, and it is why an array's end-of-life output is a radiation calculation rather than a wear estimate.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Switch on <em>Radiation belts</em> and use the energy-channel control. The channels are separated because the energy is the whole story: the population that causes surface charging and the population that causes deep dielectric discharge are different particles in different places.",
          ],
          goto: { label: "Open the layer pages →", view: "learn-layers" },
        },
      ],
    },
    {
      kicker: "CHARGING",
      title: "Two different problems that share a word.",
      lead: "A spacecraft is an isolated conductor in a plasma, so it floats to whatever potential balances the currents. That is surface charging. Separately, electrons energetic enough to get <em>inside</em> can bury charge in insulators, and that is a different failure with a different cure.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Surface charging",
              note: "electrons roughly 0–50 keV",
              body: "Charge accumulates on the outside — “on areas that can be seen and touched”. Differential charging between materials produces an arc across a surface.",
              operational: "DMSP spacecraft in the auroral zone have been measured charging to as much as −4,000 V. The mitigation is conductive surfaces and a single grounded reference, which is a materials and layout decision.",
            },
            {
              term: "Internal / deep dielectric charging",
              note: "electrons roughly 100 keV – 3 MeV",
              body: "Higher-energy electrons penetrate the structure and deposit charge in insulators “very close to a victim site”, where a discharge couples straight into the electronics. Also called buried charging.",
              operational: "The word “dielectric” under-describes it: ungrounded internal <em>conductors</em> are an equally real threat. And 30 mils of aluminium — a Faraday-cage design — is what excludes electrons above about 500 keV and protons above 10 MeV.",
            },
            {
              term: "LEO is its own case",
              note: "NASA-STD-4005A",
              body: "There is a separate standard for LEO charging of high-voltage power systems above 55 V, up to 2,000 km and between ±50° latitude, because “such power systems, particularly solar arrays, are the proximate cause of spacecraft charging in LEO”.",
            },
            {
              term: "It has taken whole spacecraft",
              note: "documented cases",
              body: "ADEOS-II in October 2003 was a total failure attributed to spacecraft charging — a sustained arc between primary power cables. Anik E1 and E2 both failed on 20–21 January 1994 after relativistic electrons from a coronal-hole stream charged them internally. Telstar 401 was lost in January 1997 during a substorm.",
              operational: "Galaxy 15 in April 2010 followed a substorm by 48 minutes, and NOAA's own review names “surface or internal” charging without choosing between them. That “or” is in the source and is left in here rather than resolved for narrative tidiness.",
            },
          ],
        },
      ],
    },
    {
      kicker: "THE BELTS",
      title: "Trapped radiation, and the place where it comes down to meet you.",
      lead: "Earth's field traps charged particles into two nested regions. Where they sit, and how far down they reach, is set by the geometry of the field itself — which is not centred on the planet.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "Inner belt",
              note: "below about L = 2",
              body: "Dominated by protons reaching hundreds of MeV, and comparatively stable. Energetic enough to penetrate shielding, which is what makes it a total-dose and single-event problem rather than a charging one.",
            },
            {
              term: "Outer belt",
              note: "above about L = 3, peaking near L = 4",
              body: "Electrons from hundreds of keV to several MeV, and enormously variable — it can change by orders of magnitude in hours. This is the population responsible for deep dielectric charging at geostationary orbit.",
            },
            {
              term: "The slot region",
              note: "2 < L < 3",
              body: "A gap between the belts, kept empty by VLF whistler-mode hiss inside the plasmasphere scattering electrons into the atmospheric loss cone.",
              operational: "It is not permanent. Strong storms fill it — the Halloween 2003 storm is the standard example — and a spacecraft designed for a quiet slot suddenly finds itself in a belt.",
            },
            {
              term: "Belt boundaries are energy-dependent",
              body: "There is no single altitude at which a belt starts. The L-shells quoted here are representative values for representative energies, and the standard AP-8/AE-8 models carry a stated uncertainty of about a factor of two.",
            },
            {
              term: "The South Atlantic Anomaly",
              note: "0.20°/yr west, 0.11°/yr south",
              body: "Earth's field is best described as a dipole that is both tilted and offset from the centre, so over the South Atlantic the field is unusually weak and the inner belt reaches unusually low. LEO spacecraft fly through the trapped population there.",
              operational: "Operators respond by switching things off. Swift disables gamma-ray-burst triggering on about seven passes a day; GEDI's detectors “blip” and its power board resets monthly; ISS spacewalks are scheduled around it.",
            },
            {
              term: "This project derives the SAA rather than drawing it",
              note: "src/eccentric-dipole.ts",
              body: "The site computes the eccentric dipole from IGRF-13 degree 1 and 2 coefficients using the Fraser-Smith closed form. The dipole comes out about 550 km off centre, and the anomaly then falls out of the arithmetic — nothing in that module names the South Atlantic.",
              operational: "The negative control is the convincing part: remove the offset and the anomaly disappears entirely. It is a property of the field's geometry, not a feature anyone drew on a map.",
            },
          ],
        },
        {
          kind: "live",
          body: [
            "Switch on <em>Radiation belts</em>. The belts are drawn from a pitch-angle-resolved model rather than as two decorative doughnuts, and the energy channels are separable for the reason given above.",
            "Add <em>Ground magnetic perturbation</em> and <em>Auroral oval</em> to see the other end of the same system — where the particles that are not trapped end up.",
          ],
          goto: { label: "Open the layer pages →", view: "learn-layers" },
        },
      ],
    },
    {
      kicker: "THE LAST ONE",
      title: "Atomic oxygen: the environment that eats the spacecraft.",
      lead: "Between about 180 and 650 km the dominant species is single oxygen atoms, produced when solar ultraviolet splits O₂. A spacecraft runs into them at orbital velocity, and the collision has enough energy to break chemical bonds.",
      blocks: [
        {
          kind: "terms",
          items: [
            {
              term: "4.5 eV, on the ram face",
              note: "at 400 km",
              body: "Average impact energy is 4.5 ± 1 eV at a 400 km orbit, from orbital velocity plus atmospheric co-rotation and thermal motion. That is comfortably enough to break the bonds in most polymers.",
            },
            {
              term: "Kapton is the ruler",
              note: "3.0×10⁻²⁴ cm³ per atom",
              body: "The erosion yield of Kapton H is so well characterised that atomic-oxygen fluence — in orbit and in ground test facilities — is <em>defined</em> by the mass loss of a Kapton witness sample.",
            },
            {
              term: "Undercutting is the failure mode",
              body: "A protective coating with a crack or a pinhole does not merely fail locally: oxygen gets underneath and erodes the polymer sideways beneath an intact-looking surface. This was observed on LDEF and is why coating quality matters more than coating thickness.",
              operational: "Erosion products also redeposit on optics and thermal surfaces, so the damage is not confined to the part being eroded.",
            },
            {
              term: "Always state the altitude",
              body: "Atomic-oxygen flux varies by orders of magnitude across the 180–650 km band and across the solar cycle. A flux quoted without an altitude and an epoch is not a usable number.",
            },
          ],
        },
      ],
    },
  ],
  sources: [
    { ref: "1", title: "NOAA SWPC / NWS, Types of Space Weather Storms; Space Weather 101", where: "photons “8 minutes from Sun to Earth”; SEPs “a half hour to several hours”; CMEs “15 to 96 hours”", url: "https://www.weather.gov/safety/space-storm-types" },
    { ref: "2", title: "IAU 2012 Resolution B2; NIST/CODATA", where: "1 AU = 149,597,870,700 m exactly and c = 299,792,458 m/s exactly, giving 499.005 s = 8 min 19 s" },
    { ref: "3", title: "GOES-R XRS Level 2 Data User's Guide §2.2, NOAA/NASA; NOAA SWPC NOAA Space Weather Scales", where: "A–X flare classes in 0.1–0.8 nm; the removal of the 0.7 XRS-B scaling for GOES-16 onwards (divide old operational XRS-B values by 0.7, increasing them by about 43%); R1–R5 thresholds and effects", url: "https://www.swpc.noaa.gov/noaa-scales-explanation" },
    { ref: "4", title: "NOAA SWPC, Solar Flares (Radio Blackouts); F10.7 cm Radio Emissions", where: "D-region absorption of 3–30 MHz; F10.7 as the EUV proxy, below 50 to above 300 s.f.u.", url: "https://www.swpc.noaa.gov/phenomena/solar-flares-radio-blackouts" },
    { ref: "5", title: "Oliveira & Zesta (2019), Space Weather 17, 1510–1533, doi:10.1029/2019SW002287", where: "the drag acceleration equation with ρ explicitly the neutral mass density" },
    { ref: "6", title: "Lam et al. (2023), Acta Astronautica 212, 370–386", where: "ionospheric plasma density “typically an order of magnitude (or more) lower than the atmospheric neutral gas density”" },
    { ref: "7", title: "NRLMSIS 2.0 (Emmert et al. 2021, Earth Space Sci. 8, e2020EA001321), run at equinox, Ap = 4, global mean", where: "400 km: 7.3×10⁻¹³ → 7.8×10⁻¹² kg/m³ solar min to max, a factor of 10.7; 210 km: a factor of 2.2. Model output, not an observation" },
    { ref: "8", title: "Knipp, Tobiska & Emery (2004), Solar Physics 224, 495–505; Huang et al. (2012), JGR 117", where: "1975–2003 energy budget of 464 GW EUV / 95 GW Joule / 36 GW particles; Joule deposition below 150 km with a ~6 h response at 400 km" },
    { ref: "9", title: "Shambaugh (2024), 4S Symposium, arXiv:2406.08342", where: "Capella “Whitney” ballistic coefficient 0.085 m²/kg (11.8 kg/m²) with fitted C_D = 2.7; typical LEO range", url: "https://arxiv.org/abs/2406.08342" },
    { ref: "10", title: "SpaceX, Geomagnetic Storm and Recently Deployed Starlink Satellites, 8 February 2022", where: "49 satellites launched 3 February 2022 13:13 EST to ~210 km perigee; drag “up to 50 percent higher” from onboard GPS; “up to 40 … will reenter”", url: "https://web.archive.org/web/20220210233638/https://www.spacex.com/updates/" },
    { ref: "11", title: "Fang et al. (2022) doi:10.1029/2022SW003193; Berger et al. (2023) doi:10.1029/2022SW003330; Kataoka et al. (2022) doi:10.1051/swsc/2022034; Dang et al. (2022) doi:10.1029/2022SW003152; Baruah et al. (2024) doi:10.1029/2023SW003716", where: "38 of 49 lost; WAM-IPE 50–125% density enhancement 200–400 km; ≥20–30% at 210 km; NRLMSIS 2.0 under 25%; regional peaks above 60%" },
    { ref: "12", title: "GFZ Potsdam Kp/ap series; WDC Kyoto Dst (provisional)", where: "peak Kp 5.333 on 3 and 4 February 2022; Dst minimum −66 nT at 11 UT on 3 February", url: "https://kp.gfz.de/en/" },
    { ref: "13", title: "Venzmer & Bothmer (2018), A&A 611, A36; Verscharen, Klein & Maruca (2019), Living Rev. Sol. Phys. 16, 5", where: "OMNI 1963–2016 hourly means |B| 6.28 nT, V 436 km/s, n 6.8 cm⁻³; bimodal fast 500–800 and slow 300–500 km/s" },
    { ref: "14", title: "Dungey (1961), Phys. Rev. Lett. 6, 47–48, doi:10.1103/PhysRevLett.6.47; NOAA SWPC, Geomagnetic Storms", where: "dayside reconnection under southward IMF" },
    { ref: "15", title: "NOAA SWPC ACE Real-Time Solar Wind; NOAA NESDIS DSCOVR", where: "L1 at about 1.5 million km, giving 15 to 60 minutes of advance measurement" },
    { ref: "16", title: "ESCC Basic Specification No. 25100 Issue 2 (2014) §3; JEDEC JESD57", where: "verbatim definitions of SEU (non-destructive), SET (voltage spike) and SEL (potentially destructive latch-up)", url: "https://escies.org/" },
    { ref: "17", title: "ECSS-E-ST-10-12C (2008, Corr. 1 2017) §3.2.1, §3.2.38, §7.1", where: "TID in gray, 1 Gy = 100 rad, reported against a target material; displacement damage dose and NIEL" },
    { ref: "18", title: "NASA-HDBK-4002A w/Change 1, Mitigating In-Space Charging Effects", where: "§4.1 surface charging correlated with 0 to ~50 keV electrons, internal charging with 100 keV to 3 MeV; §4.2 shielding thresholds; ADEOS-II and DMSP cases", url: "https://standards.nasa.gov/standard/nasa/nasa-hdbk-4002" },
    { ref: "19", title: "NASA-STD-4005A w/Change 1 (2021) §1.1", where: "LEO spacecraft charging design standard for power systems above 55 V, to 2,000 km, ±50° latitude" },
    { ref: "20", title: "Baker et al. (1994), Eos, doi:10.1029/94EO01038; Saiz, Cid & Guerrero (2018), Space Weather 16(11); NOAA Galaxy 15 Tiger Team report (1 June 2010)", where: "Anik E1/E2 January 1994; Telstar 401 January 1997; Galaxy 15 April 2010, described as “surface or internal” charging" },
    { ref: "21", title: "Reeves et al. (2016), JGR Space Physics 121(1), 397–412; Li & Hudson (2019), JGR 124, 8319–8351; ESA SPENVIS trapped-radiation documentation", where: "inner belt below L = 2 and outer above L = 3 with peaks near L = 1.5 and L = 4; slot region 2 < L < 3 maintained by plasmaspheric hiss and refilled in storms; AP-8/AE-8 coverage and factor-of-two uncertainty" },
    { ref: "22", title: "Jones et al. (2017), Space Weather 15, 44, doi:10.1002/2016SW001525 (SAMPEX)", where: "SAA drift 0.20 ± 0.04° per year west and 0.11 ± 0.01° per year south at 400–600 km over solar cycles 22–24" },
    { ref: "23", title: "NASA (Swift technical appendix; GEDI instrument notes)", where: "SAA passages on about seven orbits a day disabling Swift BAT triggering; GEDI detector blips and monthly power-board resets" },
    { ref: "24", title: "NASA-HDBK-6024, Spacecraft Polymers Atomic Oxygen Durability Handbook", where: "atomic oxygen dominant 180–650 km; average impact energy 4.5 ± 1 eV at 400 km; Kapton H erosion yield 3.0×10⁻²⁴ cm³/atom as the fluence standard; undercutting observed on LDEF", url: "https://standards.nasa.gov/standard/nasa/nasa-hdbk-6024" },
    { ref: "25", title: "This project: src/eccentric-dipole.ts and its tests", where: "IGRF-13 degree 1+2 with the Fraser-Smith (1987) closed form; the dipole sits ~610 km off centre and the SAA falls out of it, disappearing when the offset is removed" },
  ],
};

// ---------------------------------------------------------------------------
// THE TRACK
// ---------------------------------------------------------------------------

/** Reading order. It is also the order of the numbers on the doors. */
export const CHAPTERS: Chapter[] = [
  CH_LINK, CH_SPECTRUM, CH_ORBITS, CH_MANOEUVRE, CH_SPACECRAFT, CH_ENVIRONMENT, CH_INFERENCE, CH_VERDICT, CH_COMPUTATION,
];

/**
 * Where each of the ten original modules went.
 *
 * All ten were kept — none was dropped — and this map is asserted by
 * tests/satellite-fundamentals.test.ts so that a later edit cannot quietly
 * lose one of them. The left-hand string is the heading the old card carried
 * in src/content.ts before this module replaced it.
 */
export const CHAPTER_MAP: { was: string; nowIn: string; note: string }[] = [
  { was: "GSO is not automatically stationary", nowIn: "orbits", note: "rewritten and expanded, with the end-of-life reason inclined GSO exists" },
  { was: "Why satellites keep missing Earth", nowIn: "orbits", note: "rewritten as the opening section, with the free-fall vocabulary corrected" },
  { was: "Ground trace is not the orbit", nowIn: "orbits", note: "rewritten, with the westward-shift arithmetic and a drawn figure" },
  { was: "A footprint needs a definition", nowIn: "orbits", note: "rewritten and extended to elevation masks, beams and spot beams" },
  { was: "What an ephemeris actually says", nowIn: "orbits", note: "rewritten, with the mean-vs-osculating element trap made explicit" },
  { was: "How GPS solves position and time", nowIn: "orbits", note: "rewritten as an equation card with the fourth-unknown argument" },
  { was: "The spectrum is mission architecture", nowIn: "spectrum", note: "rewritten as the whole opening of the spectrum chapter" },
  { was: "UHF crosses a variable plasma", nowIn: "spectrum", note: "rewritten with the ITU Faraday rotation formula and real magnitudes" },
  { was: "Plasma does not cause most orbital drag", nowIn: "environment", note: "rewritten as the drag section, with the drag equation and the neutral-density evidence" },
  { was: "Constellations trade coverage for complexity", nowIn: "spacecraft", note: "rewritten as the fleet-level section of the spacecraft chapter" },
];

/** One card on the index: a number, a name, a summary, a contents list, a door. */
function indexCard(chapter: Chapter): string {
  const covers = chapter.covers.map((item) => `<span>${item}</span>`).join(" · ");
  return `
      <article class="lesson-card fund-index-card">
        <span class="section-kicker">CHAPTER ${chapter.index}</span>
        <h2>${chapter.title}</h2>
        <p>${chapter.door}</p>
        <p class="fund-index-covers"><b>Inside</b>${covers}</p>
        <button type="button" class="link-button" data-fundamentals-page="${chapter.id}">Open chapter ${chapter.index} →</button>
      </article>`;
}

/**
 * The index. This is what the "Satellite fundamentals" nav button opens.
 *
 * Eight doors, in reading order, and the whole page fits on one screen and a
 * bit rather than being the material itself. That separation is the point:
 * the index is for choosing, the chapters are for reading.
 */
export function satelliteFundamentalsIndexView(): string {
  return `
    <div class="fundamentals-index">
      <header class="content-hero">
        <p class="eyebrow">LEARNING TRACK 01 · SATELLITE FUNDAMENTALS</p>
        <h1>From the vocabulary to the vacuum.</h1>
        <p>Nine chapters, each one sitting. Start with what the words mean, then the orbit, then how to change it, then the machine, then the environment it has to survive, then how this site reads other operators’ manoeuvres out of the public record, then how that arithmetic is made and checked from scratch every day — and at every step, a way to go and look at the thing on the globe.</p>
      </header>
      <div class="lesson-grid">${CHAPTERS.map(indexCard).join("")}</div>
      <aside class="teaching-callout"><strong>Every number here is traceable</strong>Each chapter ends with its sources. Figures marked <em>worked</em> are computed in the page's own code from published constants and re-derived independently by the test suite, so the arithmetic on screen cannot drift from the formula that produced it. Dated archive measurements are labelled as such; live values remain on the globe, and each chapter says how to reach them.</aside>
    </div>
  `;
}

/** The foot of a chapter: forward, back, and home. */
function pager(chapter: Chapter): string {
  const position = CHAPTERS.findIndex((candidate) => candidate.id === chapter.id);
  const previous = position > 0 ? CHAPTERS[position - 1] : undefined;
  const next = position >= 0 && position < CHAPTERS.length - 1 ? CHAPTERS[position + 1] : undefined;
  const buttons: string[] = [];
  if (previous) buttons.push(`<button type="button" class="link-button" data-fundamentals-page="${previous.id}">← ${previous.index} · ${previous.title}</button>`);
  if (next) buttons.push(`<button type="button" class="link-button" data-fundamentals-page="${next.id}">${next.index} · ${next.title} →</button>`);
  buttons.push(`<button type="button" class="link-button" data-fundamentals-index>All nine chapters</button>`);
  return `<nav class="fund-pager" aria-label="Satellite fundamentals chapters">${buttons.join("")}</nav>`;
}

/** One chapter. An unknown id falls back to the index rather than to an error. */
export function satelliteFundamentalsPageView(id: string): string {
  const chapter = CHAPTERS.find((candidate) => candidate.id === id);
  if (!chapter) return satelliteFundamentalsIndexView();
  return withLearningContents(`
    <div class="fundamentals-page">
      <button type="button" class="link-button fund-page-back" data-fundamentals-index>← All nine chapters</button>
      <header class="content-hero">
        <p class="eyebrow">LEARNING TRACK 01 · CHAPTER ${chapter.index} OF ${CHAPTERS.length}</p>
        <h1>${chapter.title}</h1>
        <p>${chapter.lead}</p>
      </header>
      ${evidenceGuide()}
      ${chapter.sections.map(renderSection).join("")}
      ${learningCheck(chapter.id)}
      ${renderSources(chapter)}
      ${pager(chapter)}
    </div>
  `, `fund-${id}`);
}
