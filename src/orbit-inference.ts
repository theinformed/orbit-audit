/**
 * INFERRING MANOEUVRES — chapter 07 of the satellite-fundamentals track.
 *
 * Sean, 2026-09-04: "designing a clear and concise page that describes how we
 * are doing all of these calculations. It would be a learning page and you'd
 * need some excellent diagrams and some sample cases with math that shows how
 * we do this. and on the limitations. we also need to make sure we are
 * explaining that lower bound method - what we are inferring."
 *
 * WHAT THIS CHAPTER IS. The orbit-history browser on every satellite card
 * publishes candidate changes and, where the event's own control has earned
 * the word, inferred manoeuvres with a Δv figure. This chapter is the method
 * behind those figures: what the public record actually contains, how nature
 * is subtracted before an operator is charged, why every published cost is a
 * floor rather than an estimate, how a step is separated from fit noise, how
 * often the detector is wrong and how we know, why a repeating cluster can
 * speak more firmly than one detection, and what the method cannot see at all.
 *
 * THE METHOD IS THE CODE. Every formula, constant and gate described here is
 * quoted from `pipeline/orbit_events.py` and `pipeline/orbit_campaigns.py` —
 * the channel thresholds, the two-day persistence horizon, the return-to-trend
 * veto, the apogee-speed plane-change bound, and the larger-of-the-in-plane-pair
 * rule. If
 * this page and that code ever disagree, the code is right and this page has
 * rotted; tests/orbit-inference.test.ts recomputes the worked examples from
 * closed forms to keep the printed arithmetic honest, but the prose is guarded
 * only by review.
 *
 * MEASURED NUMBERS ARE A DATED SNAPSHOT. Unlike the six chapters before it,
 * this one quotes measurements — control counts, cluster statistics, the ISS
 * ground-truth comparison — because the method cannot be explained honestly
 * without them. The archive re-publishes after each completed sweep and these
 * figures drift, so
 * every one carries its bundle date (4 September 2026) and the chapter says,
 * where it matters, that the orbit-history browser carries today's values.
 * The figures themselves are schematics drawn from those dated records, and
 * carry the SCHEMATIC chip like every other drawing on the track.
 *
 * WHY THIS FILE IS SEPARATE. src/satellite-fundamentals.ts is 2,900 lines and
 * shared; this chapter adds ~900 more. It imports only the `Chapter` TYPE from
 * there (erased at compile time), so there is no runtime import cycle even
 * though satellite-fundamentals.ts imports this module's chapter object. The
 * INK palette below is therefore a deliberate second copy of the one in
 * satellite-fundamentals.ts, which is itself a documented hand-mirror of
 * :root in src/styles.css — see the comment on the original.
 */

import type { Chapter } from "./satellite-fundamentals";

// ---------------------------------------------------------------------------
// CONSTANTS AND ARITHMETIC
//
// The pipeline fits SGP4, and SGP4 is defined over WGS-72, so the worked
// examples here use the WGS-72 gravitational parameter the pipeline itself
// uses (MU_WGS72 in pipeline/orbit_events.py) rather than the WGS-84 value
// the rest of the track quotes. The difference is in the sixth significant
// figure and invisible at page precision; using the pipeline's own constant
// means the worked ISS number reproduces the published detection exactly.
// ---------------------------------------------------------------------------

/** Earth's gravitational parameter, km³/s² — WGS-72, as SGP4 defines it. */
export const MU_WGS72 = 398600.8;
/** Earth's equatorial radius, km — WGS-72, matching the pipeline. */
export const R_WGS72 = 6378.135;

/** Mean motion, rad/s, for a semi-major axis in km. */
export function meanMotion(aKm: number): number {
  return Math.sqrt(MU_WGS72 / aKm ** 3);
}

/**
 * The along-track floor: the cheapest Δv (m/s) that changes the semi-major
 * axis of a near-circular orbit by `daMetres`. From da = 2·dv/n.
 */
export function tangentialFloor(aKm: number, daMetres: number): number {
  return 0.5 * meanMotion(aKm) * Math.abs(daMetres);
}

/** Speed at apogee, m/s, from vis-viva — where a plane change is cheapest. */
export function apogeeSpeed(aKm: number, eccentricity: number): number {
  const apogeeKm = aKm * (1 + eccentricity);
  return Math.sqrt(Math.max(MU_WGS72 * (2 / apogeeKm - 1 / aKm), 0)) * 1000;
}

/** The plane-change floor, m/s: dv = 2·V·sin(di/2) evaluated at apogee. */
export function planeFloor(aKm: number, eccentricity: number, diDeg: number): number {
  return 2 * apogeeSpeed(aKm, eccentricity) * Math.sin((Math.abs(diDeg) * Math.PI) / 360);
}

/** The eccentricity floor, m/s: de = 2·dv/V at an apsis, so dv = V·de/2. */
export function eccentricityFloor(aKm: number, deltaE: number): number {
  return 0.5 * Math.sqrt(MU_WGS72 / aKm) * 1000 * Math.abs(deltaE);
}

/**
 * The combination rule, exactly as the pipeline applies it: the LARGER of the
 * two in-plane floors (one tangential burn changes a and e together, so
 * summing them double-counts a single burn), combined with the out-of-plane
 * floor in quadrature, because the two directions are orthogonal.
 */
export function combinedFloor(tangential: number, eccentricity: number, plane: number): number {
  return Math.hypot(Math.max(Math.abs(tangential), Math.abs(eccentricity)), plane);
}

/**
 * The Delta-v a slow spiral spends climbing between two near-circular orbits,
 * in m/s. A low-thrust spiral thrusts along the track the whole way, so the
 * cost is just the difference in circular speed: there is no impulsive
 * transfer term, because there is no coast between two impulses.
 */
export function spiralCost(fromAKm: number, toAKm: number): number {
  return Math.abs(Math.sqrt(MU_WGS72 / fromAKm) - Math.sqrt(MU_WGS72 / toAKm)) * 1000;
}

/**
 * STARLINK-32254 — the low-thrust blind spot, on real published numbers.
 *
 * The archive holds 966 consecutive-fit intervals for this spacecraft over 521
 * observed days, across which its semi-major axis climbed from 6,653.5 km to
 * 6,840.9 km on krypton Hall thrusters. The detector flagged NOT ONE event on
 * it, and was right not to: the climb is a smooth trend in the fits, and there
 * is no step anywhere in it. Quoted from the object's own history shard in the
 * 4 September 2026 bundle. This is the sharpest limitation figure the chapter
 * has, so it is pinned here and recomputed by tests/orbit-inference.test.ts
 * rather than typed into the prose as a bare number.
 */
export const STARLINK_SPIRAL = {
  norad: 60427,
  name: "STARLINK-32254",
  fromAKm: 6653.5,
  toAKm: 6840.9,
  intervals: 966,
  observedDays: 520.993,
  eventsFlagged: 0,
} as const;

/** A repeating cluster's annual cost, m/s per year, from its median rhythm. */
export function annualCadenceCost(medianDvMs: number, medianDaysBetween: number): number {
  return (medianDvMs * 365.25) / medianDaysBetween;
}

// ---------------------------------------------------------------------------
// THE WORKED RECORDS — real published detections, quoted with their dates.
//
// These are copied from the 4 September 2026 bundle (data/manifest.json →
// orbitEvents, and the per-object history shards), not invented. The unit
// suite recomputes each printed figure from the closed forms above and these
// inputs, so the arithmetic on screen cannot drift from the formula. The
// RECORDS can still age — that is what the bundle date on the page is for.
// ---------------------------------------------------------------------------

/**
 * The ISS reboost of 19 November 2025 — the ground-truth anchor.
 *
 * NASA's PIMS group publishes each reboost with the Δv the vehicle actually
 * delivered, measured on board. The detector, working only from Space-Track's
 * fitted elements, saw the semi-major axis rise 2,709.6 m beyond what nature
 * could do and priced the cheapest explanation. The two figures agree to 0.8%.
 */
export const ISS_REBOOST = {
  perigeeAltitudeKm: 414.4,
  apogeeAltitudeKm: 420.1,
  /** Observed Δa minus the drag prediction, metres — from the event record. */
  propulsiveDeltaAMetres: 2709.64,
  /** What drag was predicted to do over the same interval, metres. */
  dragDeltaAMetres: -74.4,
  /** NASA's published on-board figure, m/s. */
  nasaPublishedDvMs: 1.54,
} as const;

/** Semi-major axis for the ISS worked example, km. */
export function issSemiMajorAxisKm(): number {
  return R_WGS72 + (ISS_REBOOST.perigeeAltitudeKm + ISS_REBOOST.apogeeAltitudeKm) / 2;
}

/** The detector's floor for that reboost, m/s. Prints as 1.527. */
export function issReboostFloor(): number {
  return tangentialFloor(issSemiMajorAxisKm(), ISS_REBOOST.propulsiveDeltaAMetres);
}

/**
 * KOREASAT 5's east-west station-keeping cluster — the cadence example.
 * From the object's repeat-cluster record in the 4 September 2026 bundle:
 * 70 near-identical corrections since August 2007, still accumulating.
 */
export const KOREASAT5_EAST_WEST = {
  norad: 29349,
  cosparId: "2006-034A",
  count: 70,
  medianDvMs: 0.0521,
  medianDaysBetween: 34.957,
  dvSpreadMs: 0.0125,
  firstAt: "22 August 2007",
  lastAt: "27 August 2026",
} as const;

/**
 * TERRA's orbit-lowering event of 12 October 2022. It survives the final
 * detector sweep and demonstrates the larger-not-sum rule on real numbers:
 * one change moved a and e together, and the dearer floor is counted once.
 */
export const TERRA_COMBINED_SAMPLE_EVENT = {
  norad: 25994,
  startedAt: "12 October 2022",
  tangentialMs: 1.456029851,
  eccentricityMs: 1.110203632,
  planeMs: 0,
  publishedTotalMs: 1.456029851,
} as const;

/** GEO's circular speed in m/s — for the north-south budget check. */
export function geoSpeedMs(): number {
  return Math.sqrt(MU_WGS72 / 42164.17) * 1000;
}

/** What cancelling GEO's natural plane drift costs per year, m/s. */
export function geoNorthSouthAnnualCost(driftDegPerYear: number): number {
  return planeFloor(42164.17, 0, driftDegPerYear);
}

// ---------------------------------------------------------------------------
// FIGURES
//
// Same rules as every figure on this track: separate panels for separate
// questions, every label horizontal, semantic ink declared in a key, hardware
// and axes in neutral ink, and the SCHEMATIC chip on all of them. Ink is
// semantic and consistent across all four figures in this chapter:
// cyan = the fitted elements (what we can see), amber = the inferred burn and
// its price floor (what we claim), coral = false alarms and noise, mint = a
// corroborated repeating cadence, violet = out-of-plane.
// ---------------------------------------------------------------------------

const INK = {
  cyan: "#29d4e3",
  cyanBright: "#5ce8f1",
  amber: "#f5c96a",
  coral: "#ff7b78",
  violet: "#a98cff",
  mint: "#76e6a5",
  line: "rgba(132,194,214,.28)",
  faint: "rgba(132,194,214,.12)",
  muted: "#8da8b3",
} as const;

/** Arrowheads, ids namespaced so they cannot collide with other figures. */
function arrowDefs(id: string): string {
  const heads = [
    ["cyan", INK.cyan], ["amber", INK.amber], ["coral", INK.coral],
    ["mint", INK.mint], ["violet", INK.violet], ["muted", INK.muted],
  ] as const;
  return `<defs>${heads.map(([name, colour]) => `
    <marker id="${id}-${name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="${colour}"></path>
    </marker>`).join("")}</defs>`;
}

/**
 * FIGURE 1 — the step, and the stories that fit inside it.
 *
 * Top panel: what the archive actually holds around the 19 November 2025 ISS
 * reboost — element sets as dots, the fit scatter, the gap between the last
 * fit before and the first fit after, and the step. Bottom panel: four thrust
 * histories that are all consistent with that step, ordered by cost, with the
 * cheapest one being the number the site publishes. This is the lower-bound
 * idea drawn rather than stated.
 */
function figureStep(): string {
  // Time axis: 5 days across x = 70..860 (158 px/day). The burn window is the
  // real one: 21.7 h between the bracketing fits, drawn to scale.
  const x = (day: number) => 70 + day * 158;
  const yBefore = 218;
  const yAfter = 128;
  // Element sets before (day 0..2.3) and after (day 3.2..5), jitter ±4 px.
  // Jitter is hand-placed, not random, so the figure is stable and reviewable.
  const before = [
    [0.05, 2], [0.55, -3], [1.02, 4], [1.55, -2], [2.02, 3], [2.28, -1],
  ].map(([d, j]) => `<circle cx="${x(d!).toFixed(0)}" cy="${yBefore + j!}" r="3.4" fill="${INK.cyan}"></circle>`).join("");
  const after = [
    [3.2, -3], [3.6, 2], [4.05, -4], [4.5, 1], [4.8, 3], [4.98, -2],
  ].map(([d, j]) => `<circle cx="${x(d!).toFixed(0)}" cy="${yAfter + j!}" r="3.4" fill="${INK.cyan}"></circle>`).join("");
  // Four candidate thrust histories, one mini-strip each.
  const strip = (x0: number, label: string, verdict: string, verdictInk: string, profile: string) => `
    <line x1="${x0}" y1="518" x2="${x0 + 180}" y2="518" stroke="${INK.line}" stroke-width="1"></line>
    ${profile}
    <text x="${x0 + 90}" y="544" text-anchor="middle">${label}</text>
    <text x="${x0 + 90}" y="560" text-anchor="middle" class="fund-svg-small" style="fill:${verdictInk}">${verdict}</text>`;
  return `
<svg viewBox="0 0 900 580" role="img" aria-label="Two panels. Top: element sets drawn as dots around the ISS reboost of 19 November 2025 — a flat band of fits, a 22-hour gap shaded as the burn window, then a flat band 2.7 kilometres higher, with the step marked. Bottom: four thrust histories that all fit that step — one short burn, two smaller burns, hours of gentle thrust, and a burn aimed off the velocity direction — labelled from the cheapest, which is the published floor, to the costlier ones.">
  ${arrowDefs("stp")}
  <text x="40" y="26" class="fund-svg-key">WHAT THE ARCHIVE HOLDS</text>
  <text x="40" y="44" class="fund-svg-small">the ISS reboost of 19 Nov 2025, as Space-Track published it · <tspan style="fill:${INK.cyan};font-weight:600">CYAN</tspan> = fitted element sets · <tspan style="fill:${INK.amber};font-weight:600">AMBER</tspan> = what we infer</text>

  <!-- Axes, neutral ink -->
  <line x1="70" y1="60" x2="70" y2="290" stroke="${INK.line}" stroke-width="1"></line>
  <line x1="70" y1="290" x2="860" y2="290" stroke="${INK.line}" stroke-width="1"></line>
  <text x="78" y="70" class="fund-svg-small">semi-major axis</text>
  <text x="852" y="308" text-anchor="end" class="fund-svg-small">five days</text>
  <text x="66" y="${yBefore + 4}" text-anchor="end" class="fund-svg-small">6,795.4 km</text>
  <text x="66" y="${yAfter + 4}" text-anchor="end" class="fund-svg-small">+2.7 km</text>

  <!-- The burn window: the real 21.7 h between the bracketing fits -->
  <rect x="${x(2.3).toFixed(0)}" y="60" width="${(0.9 * 158).toFixed(0)}" height="230" fill="${INK.faint}"></rect>
  <line x1="${x(2.3).toFixed(0)}" y1="60" x2="${x(2.3).toFixed(0)}" y2="290" stroke="${INK.amber}" stroke-width="1" stroke-dasharray="5 4"></line>
  <line x1="${x(3.2).toFixed(0)}" y1="60" x2="${x(3.2).toFixed(0)}" y2="290" stroke="${INK.amber}" stroke-width="1" stroke-dasharray="5 4"></line>
  <text x="${x(2.75).toFixed(0)}" y="86" text-anchor="middle" class="fund-svg-warm">THE BURN IS IN HERE</text>
  <text x="${x(2.75).toFixed(0)}" y="102" text-anchor="middle" class="fund-svg-small">somewhere in these</text>
  <text x="${x(2.75).toFixed(0)}" y="116" text-anchor="middle" class="fund-svg-small">21.7 hours</text>

  <!-- The fits -->
  ${before}${after}
  <text x="${x(0.05).toFixed(0)}" y="${yBefore + 34}" class="fund-svg-small">element sets, about two a day —</text>
  <text x="${x(0.05).toFixed(0)}" y="${yBefore + 48}" class="fund-svg-small">each one a fit, not a position</text>
  <line x1="${x(1.0).toFixed(0)}" y1="${yBefore + 12}" x2="${x(1.0).toFixed(0)}" y2="${yBefore - 12}" stroke="${INK.line}" stroke-width="1"></line>
  <text x="${x(2.2).toFixed(0)}" y="${yBefore - 18}" text-anchor="end" class="fund-svg-small">fit scatter = this object's own noise floor</text>

  <!-- The step -->
  <line x1="${x(3.55).toFixed(0)}" y1="${yBefore}" x2="${x(3.55).toFixed(0)}" y2="${yAfter}" stroke="${INK.amber}" stroke-width="1.8" marker-start="url(#stp-amber)" marker-end="url(#stp-amber)"></line>
  <text x="${x(3.66).toFixed(0)}" y="${(yBefore + yAfter) / 2 - 2}" class="fund-svg-warm">Δa = +2,709.6 m</text>
  <text x="${x(3.66).toFixed(0)}" y="${(yBefore + yAfter) / 2 + 14}" class="fund-svg-small">drag's −74.4 m already subtracted</text>

  <!-- Divider -->
  <line x1="40" y1="340" x2="860" y2="340" stroke="${INK.faint}" stroke-width="1"></line>
  <text x="40" y="368" class="fund-svg-key">FOUR STORIES THAT ALL FIT THAT STEP</text>
  <text x="40" y="386" class="fund-svg-small">thrust against time between the two fits — the archive cannot tell these apart, but no story is cheaper than the first</text>

  <!-- 1: one short burn -->
  ${strip(60, "one short burn", "the cheapest — the published floor", INK.amber, `
    <rect x="140" y="438" width="10" height="80" fill="${INK.amber}"></rect>`)}
  <!-- 2: two smaller burns -->
  ${strip(262, "two smaller burns", "at least the floor", INK.muted, `
    <rect x="322" y="470" width="9" height="48" fill="${INK.amber}" opacity=".55"></rect>
    <rect x="384" y="474" width="9" height="44" fill="${INK.amber}" opacity=".55"></rect>`)}
  <!-- 3: hours of gentle thrust -->
  ${strip(464, "hours of gentle thrust", "costs more", INK.muted, `
    <path d="M478 518 L490 500 L618 500 L630 518 Z" fill="${INK.amber}" opacity=".55"></path>`)}
  <!-- 4: a tilted burn. Taller than strip 1 on purpose: only the part of it
       that lies along the track moves the semi-major axis, so producing the
       same step off-axis means burning harder. The dashed rule is strip 1's
       height, carried across, so the comparison is drawn and not asserted. -->
  ${strip(666, "a burn aimed off the track", "costs more", INK.muted, `
    <rect x="748" y="418" width="11" height="100" fill="${INK.amber}" opacity=".38"></rect>
    <rect x="748" y="438" width="11" height="80" fill="${INK.amber}" opacity=".7"></rect>
    <line x1="736" y1="438" x2="800" y2="438" stroke="${INK.amber}" stroke-width="1" stroke-dasharray="4 3"></line>
    <text x="800" y="442" class="fund-svg-small">only this part</text>
    <text x="800" y="456" class="fund-svg-small">is along-track</text>`)}
</svg>`;
}

/**
 * FIGURE 2 — pricing the step: three questions, three panels.
 *
 * Panel A: the two in-plane channels and why they are not summed. Panel B:
 * the plane-change vector triangle and why it is evaluated at apogee. Panel C:
 * the quadrature combination as the right triangle it literally is.
 */
function figurePricing(): string {
  // Panel B vector triangle: two speed vectors of length 190 at ±10° about
  // horizontal from a common origin; the chord between the tips is the burn.
  // cos10° = 0.9848, sin10° = 0.1736 — evaluated so the markup is stable.
  const oxB = 480; const oyB = 250;
  const tipX = (oxB + 190 * 0.9848).toFixed(1);
  const tipHi = (oyB - 190 * 0.1736).toFixed(1);
  const tipLo = (oyB + 190 * 0.1736).toFixed(1);
  return `
<svg viewBox="0 0 900 684" role="img" aria-label="Three panels. A: a circular orbit and, dashed over it, the orbit produced by one along-track burn — unchanged at the burn point, lifted on the far side, so the same single burn grows the semi-major axis and the eccentricity together and the dearer of the two floors is counted once. B: two velocity vectors of equal length separated by the plane-change angle, with the connecting chord labelled two V sine delta-i over two, and a note that the bound uses apogee, where V is smallest. C: a right triangle whose legs are the in-plane floor and the plane-change floor and whose hypotenuse is the published total.">
  ${arrowDefs("prc")}
  <text x="40" y="26" class="fund-svg-key">PRICING THE STEP — THE CHEAPEST EXPLANATION, CHANNEL BY CHANNEL</text>
  <text x="40" y="44" class="fund-svg-small"><tspan style="fill:${INK.amber};font-weight:600">AMBER</tspan> = the burn being priced · <tspan style="fill:${INK.violet};font-weight:600">VIOLET</tspan> = out-of-plane · <tspan style="fill:${INK.mint};font-weight:600">MINT</tspan> = in-plane · geometry not to scale, shapes exaggerated to be drawable</text>

  <!-- Panel A: in-plane -->
  <text x="40" y="86" class="fund-svg-num">A · IN PLANE</text>
  <!-- The orbit after the burn: perigee pinned at the burn point, apogee
       lifted on the far side. Earth at (235,215), circular orbit r = 70, so
       the burn point is (305,215); the new apogee radius is 180, giving
       a = 125 and c = 55, hence rx = 125, ry = sqrt(125^2-55^2) = 112.2 about
       a centre at x = 180. Exaggerated, and the chip says so. -->
  <ellipse cx="180" cy="215" rx="125" ry="112.2" fill="none" stroke="${INK.mint}" stroke-width="1.7" stroke-dasharray="7 5"></ellipse>
  <circle cx="235" cy="215" r="70" fill="none" stroke="${INK.muted}" stroke-width="1.3"></circle>
  <circle cx="235" cy="215" r="20" fill="${INK.faint}" stroke="${INK.muted}" stroke-width="1"></circle>
  <text x="235" y="219" text-anchor="middle" class="fund-svg-small">EARTH</text>
  <circle cx="305" cy="215" r="4" fill="${INK.amber}"></circle>
  <line x1="305" y1="215" x2="305" y2="161" stroke="${INK.amber}" stroke-width="2" marker-end="url(#prc-amber)"></line>
  <text x="318" y="176" class="fund-svg-warm">along-track burn</text>
  <text x="318" y="192" class="fund-svg-small">one impulse, along the track</text>
  <text x="318" y="212" class="fund-svg-small">the orbit is unchanged here —</text>
  <text x="318" y="226" class="fund-svg-small">this point stays where it was</text>
  <line x1="70" y1="344" x2="70" y2="276" stroke="${INK.muted}" stroke-width="1"></line>
  <text x="40" y="360" class="fund-svg-small" style="fill:${INK.mint}">the far side lifts instead: a grows, and the</text>
  <text x="40" y="374" class="fund-svg-small" style="fill:${INK.mint}">loop stops being round — so e grows with it</text>
  <text x="40" y="394" class="fund-svg-small">ONE burn, BOTH in-plane elements,</text>
  <text x="40" y="408" class="fund-svg-small">so the dearer floor is counted, once</text>

  <!-- Panel B: out-of-plane -->
  <text x="470" y="86" class="fund-svg-num">B · ROTATING THE PLANE</text>
  <line x1="${oxB}" y1="${oyB}" x2="${tipX}" y2="${tipHi}" stroke="${INK.cyan}" stroke-width="1.8" marker-end="url(#prc-cyan)"></line>
  <line x1="${oxB}" y1="${oyB}" x2="${tipX}" y2="${tipLo}" stroke="${INK.cyan}" stroke-width="1.8" marker-end="url(#prc-cyan)"></line>
  <line x1="${tipX}" y1="${tipHi}" x2="${tipX}" y2="${tipLo}" stroke="${INK.violet}" stroke-width="2" marker-start="url(#prc-violet)" marker-end="url(#prc-violet)"></line>
  <text x="575" y="200" text-anchor="middle" class="fund-svg-small" style="fill:${INK.cyan}">speed before, V</text>
  <text x="575" y="302" text-anchor="middle" class="fund-svg-small" style="fill:${INK.cyan}">speed after, V</text>
  <text x="${(oxB - 12).toFixed(0)}" y="${oyB + 4}" text-anchor="end" class="fund-svg-small">Δi</text>
  <text x="600" y="340" text-anchor="middle" style="fill:${INK.violet};font-weight:600">Δv = 2·V·sin(Δi/2)</text>
  <text x="470" y="394" class="fund-svg-small">rotating the plane is cheapest where V is smallest,</text>
  <text x="470" y="408" class="fund-svg-small">so the bound is priced at apogee — a true floor</text>

  <!-- Panel C: the combination, on its own row so every side gets a label -->
  <line x1="40" y1="436" x2="860" y2="436" stroke="${INK.faint}" stroke-width="1"></line>
  <text x="40" y="470" class="fund-svg-num">C · PUT TOGETHER</text>
  <path d="M340 634 L580 634 L580 504 Z" fill="${INK.faint}"></path>
  <line x1="340" y1="634" x2="580" y2="634" stroke="${INK.mint}" stroke-width="2"></line>
  <line x1="580" y1="634" x2="580" y2="504" stroke="${INK.violet}" stroke-width="2"></line>
  <line x1="340" y1="634" x2="580" y2="504" stroke="${INK.amber}" stroke-width="2.4"></line>
  <rect x="564" y="618" width="14" height="14" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
  <text x="400" y="544" text-anchor="middle" class="fund-svg-warm">published Δv</text>
  <text x="400" y="560" text-anchor="middle" class="fund-svg-small">the hypotenuse</text>
  <text x="594" y="574" class="fund-svg-small" style="fill:${INK.violet}">plane-change floor</text>
  <text x="460" y="658" text-anchor="middle" class="fund-svg-small" style="fill:${INK.mint}">in-plane floor — the larger of the a and e figures</text>
  <text x="620" y="612" class="fund-svg-small">orthogonal parts combine like the sides</text>
  <text x="620" y="626" class="fund-svg-small">of a right triangle (quadrature)</text>
</svg>`;
}

/**
 * FIGURE 3 — the blank: debris referees the detector.
 *
 * Each detector gets its own pair of rate strips. They answer different
 * questions and may reach different label decisions, so neither is averaged
 * into the other. Counts make the normalisation explicit; the strict design
 * target is drawn where it lives, uncomfortably close to zero.
 */
export const CONTROL_SNAPSHOT = {
  cohort: {
    name: "COHORT κ = 8 — compared with neighbouring orbits over the same hours",
    kappa: 8,
    payloadFlags: 10_501,
    payloadIntervals: 248_728,
    passiveFlags: 2_314,
    passiveIntervals: 98_707,
    passiveUpper: 0.0244,
    z: 26.481,
    boundRatio: 1.35,
    requiredRatio: 10,
    permitted: false,
  },
  selfHistory: {
    name: "SELF-HISTORY κ = 32 — compared with this object's own recent behaviour",
    kappa: 32,
    payloadFlags: 190_877,
    payloadIntervals: 62_566_722,
    passiveFlags: 39_920,
    passiveIntervals: 89_179_650,
    passiveUpper: 0.0004520421461884916,
    z: 403.734,
    // THE GATE IS SHUT, and this figure said otherwise until 2026-09-08.
    //
    // The false-alarm half PASSES: 0.452 per 1,000 is well inside the strict
    // 1-per-1,000 target. What fails is the second half, added the same day --
    // the payload rate must stand ten times clear of the passive floor, bound
    // against bound, and it stands 6.7 times clear. Reporting only the first
    // half is how a figure ends up rendering GATE PASSED for a lane the
    // published bundle calls shut.
    boundRatio: 6.719,
    requiredRatio: 10,
    permitted: false,
  },
} as const;

function figureBlank(): string {
  const barX = 190; const barW = 670; const maxRate = 0.05;
  const width = (flags: number, intervals: number) =>
    Math.max(1, Math.min(barW, barW * flags / intervals / maxRate)).toFixed(1);
  const count = (value: number) => value.toLocaleString("en-GB");
  const rate = (flags: number, intervals: number) =>
    (flags / intervals * 1000).toFixed(3);
  const targetX = barX + barW * 0.001 / maxRate;
  const lane = (
    y: number,
    item: typeof CONTROL_SNAPSHOT.cohort | typeof CONTROL_SNAPSHOT.selfHistory,
  ) => `
    <text x="40" y="${y}" class="fund-svg-num">${item.name}</text>
    <text x="40" y="${y + 31}" class="fund-svg-small">payloads</text>
    <rect x="${barX}" y="${y + 15}" width="${barW}" height="24" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
    <rect x="${barX + 1}" y="${y + 16}" width="${width(item.payloadFlags, item.payloadIntervals)}" height="22" fill="${INK.cyan}" opacity=".85"></rect>
    <text x="${barX + 8}" y="${y + 32}" class="fund-svg-key">${count(item.payloadFlags)} / ${count(item.payloadIntervals)} · ${rate(item.payloadFlags, item.payloadIntervals)} per 1,000</text>
    <text x="40" y="${y + 75}" class="fund-svg-small">debris + spent stages</text>
    <rect x="${barX}" y="${y + 59}" width="${barW}" height="24" fill="none" stroke="${INK.line}" stroke-width="1"></rect>
    <rect x="${barX + 1}" y="${y + 60}" width="${width(item.passiveFlags, item.passiveIntervals)}" height="22" fill="${INK.coral}" opacity=".9"></rect>
    <line x1="${targetX.toFixed(1)}" y1="${y + 56}" x2="${targetX.toFixed(1)}" y2="${y + 87}" stroke="${INK.amber}" stroke-width="1.4"></line>
    <text x="${barX + 8}" y="${y + 76}" class="fund-svg-hot">${count(item.passiveFlags)} / ${count(item.passiveIntervals)} · ${rate(item.passiveFlags, item.passiveIntervals)} per 1,000 — all false</text>
    <text x="${barX}" y="${y + 105}" class="fund-svg-small">95% upper bound ${(item.passiveUpper * 1000).toFixed(3)} per 1,000 · payload stands ${item.boundRatio.toFixed(1)}× clear (${item.requiredRatio}× required)</text>
    <rect x="${barX + 520}" y="${y + 90}" width="150" height="25" fill="none" stroke="${item.permitted ? INK.mint : INK.coral}" stroke-width="1.2"></rect>
    <text x="${barX + 595}" y="${y + 107}" text-anchor="middle" style="fill:${item.permitted ? INK.mint : INK.coral};font-weight:600">${item.permitted ? "GATE PASSED" : "GATE CLOSED"}</text>`;
  return `
<svg viewBox="0 0 900 520" role="img" aria-label="Two independent detectors compare payload flags with flags on debris and spent stages. The cohort lane's passive upper bound is ${(CONTROL_SNAPSHOT.cohort.passiveUpper * 1000).toFixed(3)} per thousand and its gate is ${CONTROL_SNAPSHOT.cohort.permitted ? "open" : "closed"}. The self-history lane's passive upper bound is ${(CONTROL_SNAPSHOT.selfHistory.passiveUpper * 1000).toFixed(3)} per thousand and its gate is ${CONTROL_SNAPSHOT.selfHistory.permitted ? "open" : "closed"}. Only payload events judged by an open lane may use the word manoeuvre.">
  ${arrowDefs("blk")}
  <text x="${barX}" y="26" class="fund-svg-key">THE BLANK — OBJECTS THAT CANNOT MANOEUVRE REFEREE THE DETECTOR</text>
  <text x="${barX}" y="44" class="fund-svg-small"><tspan style="fill:${INK.cyan};font-weight:600">CYAN</tspan> = payload flags · <tspan style="fill:${INK.coral};font-weight:600">CORAL</tspan> = flags false by construction · <tspan style="fill:${INK.amber};font-weight:600">AMBER LINE</tspan> = strict 1-per-1,000 target</text>

  ${lane(82, CONTROL_SNAPSHOT.cohort)}
  <line x1="40" y1="215" x2="860" y2="215" stroke="${INK.faint}" stroke-width="1"></line>
  ${lane(255, CONTROL_SNAPSHOT.selfHistory)}

  <!-- The consequence -->
  <line x1="40" y1="390" x2="860" y2="390" stroke="${INK.faint}" stroke-width="1"></line>
  <text x="40" y="422" class="fund-svg-num">THE CONSEQUENCE IS ATTACHED TO THE EVENT, NOT BORROWED ACROSS LANES</text>
  <text x="40" y="450" class="fund-svg-small">cohort-only payload event → <tspan style="fill:${CONTROL_SNAPSHOT.cohort.permitted ? INK.mint : INK.coral};font-weight:600">${CONTROL_SNAPSHOT.cohort.permitted ? "MANOEUVRE" : "CANDIDATE"}</tspan></text>
  <text x="40" y="474" class="fund-svg-small">self-history payload event → <tspan style="fill:${CONTROL_SNAPSHOT.selfHistory.permitted ? INK.mint : INK.coral};font-weight:600">${CONTROL_SNAPSHOT.selfHistory.permitted ? "MANOEUVRE — inferred, not confirmed" : "CANDIDATE"}</tspan></text>
  <text x="40" y="500" class="fund-svg-small">debris or spent stage → <tspan style="fill:${INK.coral};font-weight:600">FALSE ALARM</tspan> — on the strength of the catalogue, regardless of either gate</text>
</svg>`;
}

/**
 * FIGURE 4 — a cadence corroborates itself, and stops being paid for.
 *
 * Panel A: one year of KOREASAT 5's east-west corrections at their measured
 * rhythm, against a strip of what fit noise looks like. Panel B: the same
 * satellite's north-south story — a six-event detected cluster ends in July
 * 2024 and the fitted inclination begins the climb nature had been sending
 * the bill for all along. Both are drawn from the object's own published
 * records in the 4 September 2026 bundle.
 */
function figureCadence(): string {
  // Panel A: 365 days across x = 60..860, ticks every 34.957 days.
  const ticksA: string[] = [];
  for (let day = 3; day < 365; day += KOREASAT5_EAST_WEST.medianDaysBetween) {
    const px = 60 + (day / 365) * 800;
    ticksA.push(`<line x1="${px.toFixed(1)}" y1="150" x2="${px.toFixed(1)}" y2="106" stroke="${INK.mint}" stroke-width="2"></line>`);
  }
  // Noise strip: irregular spacings and sizes, hand-placed.
  const noise = [
    [40, 26], [96, 12], [113, 30], [258, 8], [300, 22], [488, 34], [520, 10], [704, 16], [838, 27],
  ].map(([day, h]) => {
    const px = 60 + (day! / 900) * 800;
    return `<line x1="${px.toFixed(1)}" y1="236" x2="${px.toFixed(1)}" y2="${236 - h!}" stroke="${INK.coral}" stroke-width="2" opacity=".8"></line>`;
  }).join("");
  // Panel B: Jan 2014 → Sep 2026 across x = 60..860. The last event in the
  // six-member north-south cluster is July 2024; inclination then rises from
  // 0.0481° to 1.980° in the final snapshot.
  const xB = (yearFrac: number) => 60 + ((yearFrac - 2014) / 12.67) * 800;
  const stopX = xB(2024.53);
  const ticksB = [2014.96, 2015.0, 2024.42, 2024.46, 2024.49, 2024.56]
    .map((t) => `<line x1="${xB(t).toFixed(1)}" y1="500" x2="${xB(t).toFixed(1)}" y2="462" stroke="${INK.violet}" stroke-width="2"></line>`);
  const iY = (deg: number) => 500 - (deg / 2.2) * 130;
  return `
<svg viewBox="0 0 900 570" role="img" aria-label="Two panels for KOREASAT 5. A: one year of east-west corrections drawn as an evenly spaced comb — 0.0521 metres per second every 35.0 days — above a strip of irregular spikes labelled as what fit noise looks like. B: a 2014-to-2026 timeline showing the six-event north-south cluster ending in July 2024, after which the fitted inclination climbs from 0.0481 to 1.980 degrees by September 2026, the natural drift no longer being cancelled.">
  ${arrowDefs("cad")}
  <text x="40" y="26" class="fund-svg-key">A · ONE YEAR OF KOREASAT 5, EAST-WEST</text>
  <text x="40" y="44" class="fund-svg-small">drawn at the cluster's measured rhythm · <tspan style="fill:${INK.mint};font-weight:600">MINT</tspan> = the repeating correction · <tspan style="fill:${INK.coral};font-weight:600">CORAL</tspan> = fit noise · <tspan style="fill:${INK.violet};font-weight:600">VIOLET</tspan> = north-south</text>

  <line x1="60" y1="150" x2="860" y2="150" stroke="${INK.line}" stroke-width="1"></line>
  ${ticksA.join("")}
  <text x="60" y="86" class="fund-svg-small" style="fill:${INK.mint}">0.0521 m/s, every 35.0 days — 70 from Aug 2007 to Aug 2026</text>
  <text x="60" y="170" class="fund-svg-small">one year — the measured spread between corrections is 0.0125 m/s</text>

  <line x1="60" y1="236" x2="860" y2="236" stroke="${INK.line}" stroke-width="1"></line>
  ${noise}
  <text x="60" y="262" class="fund-svg-small" style="fill:${INK.coral}">what noise looks like: no schedule, no common size. One tick alone could be noise — a drumbeat cannot</text>

  <line x1="40" y1="296" x2="860" y2="296" stroke="${INK.faint}" stroke-width="1"></line>
  <text x="40" y="326" class="fund-svg-key">B · THE SAME SATELLITE, NORTH-SOUTH — WHEN THE DRUMBEAT STOPS</text>
  <text x="40" y="344" class="fund-svg-small">six clustered corrections · median 2.1454 m/s · last one 22 July 2024 — then the unpaid bill appears</text>

  <line x1="60" y1="500" x2="860" y2="500" stroke="${INK.line}" stroke-width="1"></line>
  ${ticksB.join("")}
  <line x1="${stopX.toFixed(1)}" y1="356" x2="${stopX.toFixed(1)}" y2="500" stroke="${INK.muted}" stroke-width="1" stroke-dasharray="5 4"></line>
  <text x="${(stopX + 10).toFixed(1)}" y="370" class="fund-svg-small">last north-south correction · July 2024</text>
  <path d="M${stopX.toFixed(1)} ${iY(0.0481).toFixed(1)} L${xB(2026.67).toFixed(1)} ${iY(1.980).toFixed(1)}" fill="none" stroke="${INK.cyan}" stroke-width="2"></path>
  <text x="845" y="458" text-anchor="end" class="fund-svg-small" style="fill:${INK.cyan}">fitted inclination, climbing 0.913°/yr</text>
  <text x="${xB(2026.64).toFixed(1)}" y="${(iY(1.980) - 12).toFixed(1)}" text-anchor="end" class="fund-svg-small" style="fill:${INK.cyan}">1.980° by 3 Sep 2026</text>
  <text x="60" y="530" class="fund-svg-small">2014</text>
  <text x="852" y="530" text-anchor="end" class="fund-svg-small">Sep 2026</text>
  <text x="60" y="556" class="fund-svg-small">luni-solar gravity tips the plane whether anyone pays or not — after the final detected correction, the inclination climbs</text>
</svg>`;
}

// ---------------------------------------------------------------------------
// THE CHAPTER
// ---------------------------------------------------------------------------

const BUNDLE_DATE = "4 September 2026";

export const CH_INFERENCE: Chapter = (() => {
  const issFloor = issReboostFloor();
  const issAgreement = ((1 - issFloor / ISS_REBOOST.nasaPublishedDvMs) * 100);
  const ewAnnual = annualCadenceCost(KOREASAT5_EAST_WEST.medianDvMs, KOREASAT5_EAST_WEST.medianDaysBetween);
  const nsAnnual = geoNorthSouthAnnualCost(0.85);
  return {
    id: "inference",
    index: "07",
    title: "Inferring manoeuvres",
    door: "Nobody tells us when a satellite burns. This chapter is how the orbit-history browser reads a manoeuvre out of the public record anyway — and what it refuses to claim.",
    covers: [
      "fitted elements, not positions", "subtracting nature", "the lower-bound Δv",
      "the debris control", "when the word manoeuvre is earned", "cadence clusters", "what we cannot see",
    ],
    lead: "Every orbit-history card on this site prices a change it was never told about, from data that never says \"burn\". This chapter is the whole method, honestly: what the record contains, how nature is billed before any operator, why every Δv is a floor, how often the detector is wrong, and what it cannot see at all. The measured numbers here are a snapshot of the " + BUNDLE_DATE + " bundle; the browser always carries today's.",
    sections: [
      {
        kicker: "WHAT WE ACTUALLY HAVE",
        title: "A burn never appears. A step in a fit does.",
        lead: "Space-Track publishes element sets: the parameters of an SGP4 model orbit fitted to tracking observations. Nothing in one is a measurement of where a satellite was, and nothing in the stream announces a manoeuvre. Everything this site claims begins as a difference between two fits.",
        blocks: [
          {
            kind: "terms",
            items: [
              { term: "Element set", note: "TLE / GP", body: "One published fit: the orbit that best matches recent tracking of this object, expressed in the elements of chapter 03. It is a claim about an arc of time, not a snapshot of a position.", operational: "\"Elsets\" arrive a few times a day for a tracked object, and each replaces the last." },
              { term: "Mean elements", body: "SGP4 averages away the wiggles J₂ and drag put into a real orbit, so its elements move smoothly. They only mean anything inside SGP4 — comparing them to another model's elements, or to truth, without care is the classic trap.", operational: "This is why the site propagates with SGP4 and nothing else." },
              { term: "Interval", body: "One consecutive pair of element sets for one object. Every claim on this site starts as: between these two fits, an element moved by this much. The median object here gets about two element sets a day, so an interval is usually about half a day wide." },
              { term: "Step", body: "A burn — however it was actually flown — shows up only as a change from one fit to the next. The detector finds steps in fitted elements. It never sees a burn, and this chapter never forgets the difference." },
            ],
          },
          {
            kind: "facts",
            items: [
              { value: "≈ 2 / day", caption: `element sets for the median object in this archive (1.9 measured, ${BUNDLE_DATE})` },
              { value: "≈ ½ day", caption: "how closely a typical step can be placed in time — the gap between the two fits that bracket it" },
              { value: "8,421", caption: "objects with a published history in this release, earliest element set January 1959" },
              { value: "216 M", caption: "element-set rows directly counted in the calibration snapshot; its maintained summary still reported 182 M" },
            ],
          },
          {
            kind: "figure",
            svg: figureStep(),
            chip: "schematic",
            chipNote: `Schematic · drawn from the real ISS reboost record of 19 Nov 2025, ${BUNDLE_DATE} bundle`,
            caption: "Top: what the archive holds around a real reboost — fits, scatter, a gap, a step. The burn can only be placed somewhere inside the gap. Bottom: four thrust histories that all produce the same step. The record cannot distinguish them; what it can do is put a price on the cheapest, and that is the number this site publishes.",
          },
        ],
      },
      {
        kicker: "BEFORE ANYONE IS CHARGED",
        title: "Nature moves orbits for free, and gets billed first.",
        lead: "Most element change needs no propellant. Drag lowers orbits, luni-solar gravity tips planes, Earth's lumpy equator swings geostationary satellites about two stable longitudes. Every figure this site publishes is built from the residual after the natural change is subtracted — never from the raw difference.",
        blocks: [
          {
            kind: "terms",
            items: [
              { term: "The drag prediction", body: "Each object's expected decay is measured, not modelled: the median decay rate of its altitude neighbours over the same hours — the atmosphere the shell actually flew through — scaled by this object's own ballistic coefficient. The cohort uses a median so a manoeuvring neighbour cannot pollute the atmosphere estimate.", operational: "The ISS record below shows it working: −74.4 m of drag subtracted before +2,709.6 m was charged to propulsion." },
              { term: "Nothing is tested against zero", body: "Luni-solar gravity tips a geostationary plane about 0.85° a year. Tested against zero, that free drift is a seventeen-sigma \"manoeuvre\" on every geostationary object, every day — the first run of this pipeline duly reported exactly that. Every element is tested against its expected natural drift instead.", operational: "Charging an operator for the luni-solar wander of a satellite dead since the 1970s is the specific mistake this rule prevents." },
              { term: "The natural floor", body: "For each element, the largest change that needs no propulsion at all: the catalogue's measured fit scatter, the luni-solar plane drift, and the geostationary libration, whichever dominates for this orbit. A step has to clear the floor before it is anything." },
            ],
          },
        ],
      },
      {
        kicker: "THE LOWER-BOUND METHOD",
        title: "Every Δv on this site is a floor: the truth cost at least this.",
        lead: "For each residual the detector asks one question: what is the cheapest possible manoeuvre consistent with this change? A real burn in any other direction, at any other point in the orbit, or spread over an arc costs more. So \"at least 0.05 m/s\" is not a hedge — it is a floor under what the operator actually spent.",
        blocks: [
          {
            kind: "equation",
            name: "The along-track floor",
            tag: "cheapest way to change a",
            formula: "Δv  =  n · Δa / 2",
            where: [
              { symbol: "Δa", meaning: "the change in semi-major axis left over after the drag prediction is subtracted, in metres" },
              { symbol: "n", meaning: "the orbit's mean motion √(μ/a³), in radians per second — how fast it sweeps angle" },
              { symbol: "Δv", meaning: "the smallest burn that produces Δa: a single impulse along the velocity vector" },
            ],
            worked: [
              `The ISS reboost of 19 Nov 2025, from the real record: a = ${issSemiMajorAxisKm().toFixed(1)} km, so n = ${(meanMotion(issSemiMajorAxisKm()) * 1000).toFixed(4)} mrad/s. The drag-corrected step was Δa = +2,709.6 m.`,
              `Δv = ½ × ${(meanMotion(issSemiMajorAxisKm()) * 1000).toFixed(4)}×10⁻³ × 2,709.6 = ${issFloor.toFixed(3)} m/s.`,
              `NASA measured that reboost on board and published ${ISS_REBOOST.nasaPublishedDvMs.toFixed(2)} m/s. The floor sits ${Math.abs(issAgreement).toFixed(1)}% under it — below it, as a floor should be, and close, because a reboost really is nearly the ideal single along-track burn.`,
            ],
          },
          {
            kind: "equation",
            name: "The plane-rotation and eccentricity floors",
            tag: "the other two channels",
            formula: "Δv  =  2 · V · sin(Δψ / 2)        Δv  =  V · Δe / 2",
            where: [
              { symbol: "Δψ", meaning: "the smallest residual rotation of the orbital plane, reconstructed from inclination and node after predicted J₂ nodal drift is removed" },
              { symbol: "V", meaning: "the orbital speed where the burn is assumed to happen — apogee, deliberately, because rotating the plane is cheapest where the orbit is slowest, which keeps the figure a true floor" },
              { symbol: "Δe", meaning: "the residual change in eccentricity; a tangential burn at an apsis changes e by 2·Δv/V" },
            ],
            worked: [
              `Scale, at geostationary altitude: V = ${geoSpeedMs().toFixed(0)} m/s, and cancelling the natural 0.85°/yr plane drift costs 2 × ${geoSpeedMs().toFixed(0)} × sin(0.425°) = ${nsAnnual.toFixed(1)} m/s a year. That single number is why north-south keeping dominates every geostationary propellant budget — and why giving it up (section on cadence, below) is such a visible decision.`,
            ],
          },
          {
            kind: "equation",
            name: "Putting the channels together",
            tag: "why not just add them",
            formula: "in-plane  =  max(|Δv_a|, |Δv_e|)\ntotal     =  √(in-plane² + Δv_plane²)",
            where: [
              { symbol: "max, not sum", meaning: "one tangential burn changes a and e together, so adding their floors would charge one burn twice; the dearer channel is counted, once" },
              { symbol: "quadrature", meaning: "in-plane and out-of-plane pushes are at right angles, so they combine like the sides of a right triangle" },
            ],
            worked: [
              `A real one that survives the final scan, TERRA on 12 Oct 2022: the along-track floor was ${TERRA_COMBINED_SAMPLE_EVENT.tangentialMs.toFixed(4)} m/s and the eccentricity floor ${TERRA_COMBINED_SAMPLE_EVENT.eccentricityMs.toFixed(4)} m/s. Published: ${combinedFloor(TERRA_COMBINED_SAMPLE_EVENT.tangentialMs, TERRA_COMBINED_SAMPLE_EVENT.eccentricityMs, TERRA_COMBINED_SAMPLE_EVENT.planeMs).toFixed(4)} m/s — the larger, not the ${(TERRA_COMBINED_SAMPLE_EVENT.tangentialMs + TERRA_COMBINED_SAMPLE_EVENT.eccentricityMs).toFixed(4)} a naive sum would claim.`,
            ],
          },
          {
            kind: "figure",
            svg: figurePricing(),
            chip: "schematic",
            chipNote: "Schematic · geometry not to scale, shapes and angles exaggerated to be drawable",
            caption: "The three channels and the two combination rules. Panel A: one along-track burn moves semi-major axis and eccentricity together, which is why their floors are never added. Panel B: the plane-change vector triangle — the same rotation costs least where the orbit is slowest, so the bound is evaluated at apogee. Panel C: the in-plane and out-of-plane floors are orthogonal, and the published total is literally the hypotenuse.",
          },
          {
            kind: "facts",
            items: [
              { value: "1.527 vs 1.54", caption: "detector floor vs NASA's on-board Δv, ISS reboost of 19 Nov 2025 — 0.8% under" },
              { value: "0.985 vs 1.00", caption: "the same comparison for the 14 Aug 2025 reboost — 1.5% under" },
              { value: "1.093 vs 1.09", caption: "16 Jul 2025 reboost — 0.3% over the on-board figure; a lower-bound construction is only as exact as its drag subtraction" },
              { value: "18 of 27", caption: `scorable operator-published manoeuvres found (ISS and Terra) — the positive control beside the debris blank, ${BUNDLE_DATE}` },
            ],
          },
        ],
      },
      {
        kicker: "SEPARATING BURNS FROM NOISE",
        title: "Three gates, and every one is a physical statement.",
        lead: "A step must clear three tests before it is published, and each is a sentence about how orbits and propellant behave. The gate design was first measured on a fixed 203,719-interval debris sample; today's complete-archive control is shown separately below.",
        blocks: [
          {
            kind: "terms",
            items: [
              { term: "Clear your own noise floor", body: "The scatter of an object's own recent fits is measured, and a step must stand above both that object's noise floor and the catalogue-wide minimum. A loosely tracked tumbling fragment therefore gets a loose floor of its own, instead of being held to a payload's tight one and flagged constantly. This release uses κ = 32 for self-history; the independent cohort lane remains at κ = 8. Both values are printed with their measured controls below." },
              { term: "Still be there two days later", body: "Propellant does not un-burn. A manoeuvre moves the orbit and the orbit stays moved; a loose fit moves one element set and the next fits put it back. The residual is accumulated forward for two days and half of it must survive.", operational: "A change in the last two days of coverage has nothing after it to persist into, and is declined rather than guessed at. The newest claims being the least tested would be the wrong way round." },
              { term: "Not be a return to trend", body: "A single loose fit makes two apparent steps: the excursion and the return. The forward test rejects the excursion — the return cancels it — but would accept the return, so there is a veto: a step whose preceding element set moved the same amount the other way is the fit coming home, not a burn. Propellant cannot produce that pattern." },
              { term: "What the gates are applied to", body: "Six numbers fix an orbit. Five describe shape and orientation: semi-major axis, eccentricity, inclination, right ascension of the ascending node, and argument of perigee. Self-history screens the first three. Its node and apse-line channels were built and measured, but remain disabled after false flags on debris. The cohort detector independently retains its node screen. Mean anomaly only locates the satellite along the loop and gets no channel: a lasting shift changes the period, which semi-major axis already measures.", operational: "Which channels judged the event in front of you is printed on the event card, with each one’s z-score. Trust the card over this paragraph." },
              { term: "Why the self-history node channel is disabled", body: "Earth’s oblateness swings the node daily without propellant. A historical experiment used observed node change minus predicted J₂ drift, excluded orbits within one degree of the equator, converted the residual into true plane rotation, and required 1.5 times the ordinary threshold. It still tripped 63,190 passive intervals. The predeclared rule keeps self-history node detection off. That experiment is not part of the current snapshot; the separately controlled cohort node screen remains enabled." },
            ],
          },
          {
            kind: "facts",
            items: [
              { value: "13.9 → 8.4", caption: "historical κ = 8 calibration: false flags per 1,000 debris intervals, catalogue-wide floor → each object's own floor" },
              { value: "8.4 → 3.4", caption: "historical calibration: adding the two-day persistence test — the single most effective gate in that experiment" },
              { value: "3.4 → 1.83", caption: "historical calibration: adding the return-to-trend veto; κ stayed fixed at 8 throughout that ladder" },
              { value: "not today's rate", caption: "that ladder is one dated 203,719-interval experiment. The current complete-archive lanes below use cohort κ = 8 and self-history κ = 32" },
            ],
          },
        ],
      },
      {
        kicker: "HOW OFTEN WE ARE WRONG",
        title: "Debris cannot manoeuvre, so it referees the detector.",
        lead: "Spent stages and fragments have no engines, so a flag on one is a false alarm — on the strength of the catalogue that says what they are. That is the one soft spot in an otherwise free, always-on blank sample: a fragment cannot burn, but a catalogue entry can be wrong or out of date. The honest false-alarm rate is whatever the detector does to the blank, and it is remeasured on every complete sweep, not assumed.",
        blocks: [
          {
            kind: "figure",
            svg: figureBlank(),
            chip: "schematic",
            chipNote: `Schematic · both control lanes measured on the ${BUNDLE_DATE} archive snapshot`,
            caption: "The two blanks, drawn separately. Each detector compares its payload flags with objects that cannot manoeuvre, and each opens only its own vocabulary gate. A passing self-history control cannot lend certainty to a cohort-only event; debris can never inherit either gate.",
          },
          {
            // One item, so it takes the full width rather than leaving an
            // empty cell beside itself in the two-column grid.
            kind: "terms",
            single: true,
            items: [
              { term: "Two blanks, and they do not agree — on purpose", body: `Each detector keeps its own blank. At κ = ${CONTROL_SNAPSHOT.cohort.kappa}, the cohort screen flagged ${CONTROL_SNAPSHOT.cohort.passiveFlags.toLocaleString("en-GB")} of ${CONTROL_SNAPSHOT.cohort.passiveIntervals.toLocaleString("en-GB")} impossible intervals: ${(CONTROL_SNAPSHOT.cohort.passiveFlags / CONTROL_SNAPSHOT.cohort.passiveIntervals * 1000).toFixed(3)} per 1,000, with a ${(CONTROL_SNAPSHOT.cohort.passiveUpper * 1000).toFixed(3)} upper bound. Its gate is closed. At κ = ${CONTROL_SNAPSHOT.selfHistory.kappa}, self-history flagged ${CONTROL_SNAPSHOT.selfHistory.passiveFlags.toLocaleString("en-GB")} of ${CONTROL_SNAPSHOT.selfHistory.passiveIntervals.toLocaleString("en-GB")}: ${(CONTROL_SNAPSHOT.selfHistory.passiveFlags / CONTROL_SNAPSHOT.selfHistory.passiveIntervals * 1000).toFixed(3)} per 1,000, with a ${(CONTROL_SNAPSHOT.selfHistory.passiveUpper * 1000).toFixed(3)} upper bound. Its gate passes. Different instruments may disagree.`, operational: "Nearly every event card you will open quotes the self-history figure, because that is the lane almost all of them are judged on. A page that averaged the two into one tidy number would be hiding which control did the work." },
            ],
          },
          {
            kind: "terms",
            single: true,
            items: [
              { term: "Why the word belongs to a lane", body: "The site could sound more certain at zero cost — nothing stops the word \"manoeuvre\" appearing. What stops or permits it is the blank for the detector that actually judged this event. A payload event earns the word only when that lane's passive upper bound sits below 1 per 1,000 and its payload rate stands ten times clear of that floor. The second test matters because significance alone is nearly free here: a detector tightened until it flags almost nothing would pass it. Otherwise the event stays a candidate.", operational: "The threshold is a measured design target, not a mood. Even when the word is earned, the cause remains an inference and the Δv remains a lower bound." },
            ],
          },
        ],
      },
      {
        kicker: "WHEN ONE DETECTION IS WEAK BUT 70 ARE STRONG",
        title: "Noise does not keep a drumbeat.",
        lead: "A single 0.05 m/s step on one geostationary satellite sits uncomfortably close to the noise the blank measures. But the archive holds objects that repeat the same step, the same size, on the same rhythm, for years — and randomness does not do that. Repetition is corroboration the single event can never have.",
        blocks: [
          {
            kind: "figure",
            svg: figureCadence(),
            chip: "schematic",
            chipNote: `Schematic · rhythms, sizes and dates from KOREASAT 5's published cluster records, ${BUNDLE_DATE} bundle`,
            caption: "Panel A: one year of KOREASAT 5's east-west keeping at its measured rhythm — 70 corrections with a 0.0521 m/s median floor and 35.0-day median spacing, from August 2007 through August 2026, against a strip of what fit noise looks like. Panel B: its six-event north-south cluster ends on 22 July 2024; fitted inclination then climbs from 0.0481° to 1.980° by 3 September 2026, 0.913° per year.",
          },
          {
            kind: "equation",
            name: "From cadence to an annual budget",
            tag: "a number a reader can check",
            formula: "Δv per year  =  median Δv  ×  365.25 / median days between",
            where: [
              { symbol: "median Δv", meaning: `${KOREASAT5_EAST_WEST.medianDvMs.toFixed(4)} m/s — the cluster's per-correction floor; its measured spread is ${KOREASAT5_EAST_WEST.dvSpreadMs.toFixed(4)} m/s across ${KOREASAT5_EAST_WEST.count} corrections` },
              { symbol: "median spacing", meaning: `${KOREASAT5_EAST_WEST.medianDaysBetween.toFixed(1)} days, measured only inside continuous coverage — never across an archive gap` },
            ],
            worked: [
              `KOREASAT 5, east-west: ${KOREASAT5_EAST_WEST.medianDvMs.toFixed(4)} × 365.25 / ${KOREASAT5_EAST_WEST.medianDaysBetween.toFixed(1)} = ${ewAnnual.toFixed(2)} m/s per year.`,
              "Published east-west station-keeping budgets for geostationary satellites run about 2 m/s a year, varying with longitude. This 0.54 m/s/year figure is smaller, as a floor should be: it counts only the corrections that survive the detector and prices each at the cheapest compatible burn.",
            ],
          },
          {
            kind: "live",
            body: [
              "Pick any satellite on the globe and open its card — the archive surfaces there. Press <em>Open orbit history</em>: the dialog titled <em>How this orbit has changed</em> draws this object's element history, its candidate events or control-qualified manoeuvres with the Δv floors priced exactly as this chapter describes, and its repeat clusters when it has them.",
              "Read one event card top to bottom. Every sentence of it — the observation, the drag subtraction, the floor, the candidate causes, the lane-specific false-alarm honesty — is this chapter's method, applied to the object in front of you with today's numbers.",
            ],
            goto: { label: "Back to the globe to try it", view: "explore" },
          },
        ],
      },
      {
        kicker: "LONG-ARC DRIFT",
        title: "A sustained climb asks a different question.",
        lead: "The nightly v4 lane fits semi-major-axis slopes over the trailing 120 complete UTC days, using five-day blocks of daily medians. It catches sustained raising that a step detector can miss. A positive slope must exceed five times its robust scatter-per-span floor, and every raw fit must have perigee below 800 km and eccentricity below 0.05. Within that regime, drag removes energy; propulsion by elimination is an inference whose warrant also requires this window’s own passive control.",
        blocks: [
          { kind: "terms", items: [
            { term: "Three designs failed their blank", body: "First, subtracting a neighbouring band’s median drift confused different ballistic responses with propulsion. Second, regressing on B* still flagged passive objects more often than payloads: B* is a fitted catalogue parameter, not a measured ballistic coefficient. Third, predicting from an object’s own trailing slope again failed separation and could absorb thrust already under way. Those full-catalogue failures motivated v4’s narrower positive-slope question; they did not justify retuning a threshold until the same archive passed." },
            { term: "A gate earned on this window", body: "Propulsion wording requires the passive exact one-sided 95% upper bound below 1 per 1,000 object-windows AND payload rate divided by that bound at least 10×. Otherwise flags are suppressed and the blocking reason is shown. The historical 2024 acceptance numbers cannot authorize a different window. This is a bound-aware comparison, not a joint confidence bound on the ratio; correlated debris families and catalogue errors can weaken its assumptions." },
            { term: "What this lane cannot establish", body: "Station-keeping can leave no climb; lowering is drag-ambiguous. Above-gate rises retain solar-radiation-pressure, GEO libration or HEO lunisolar ambiguity labels, never propulsion claims. GEO relocations need another channel. Short campaigns can disappear in a 120-day fit; coverage gaps prevent an answer. The optional preceding 240 days supply context only. Neither exact campaign timing, Δv, independent per-object propulsion truth nor recall over a labelled raising population follows from this slope." },
          ] },
          { kind: "live", body: ['<span data-orbit-drift-controls aria-live="polite">The current release’s own drift control loads here. Until it is available, no propulsion label is warranted.</span>'] },
          { kind: "live", body: ['<a href="#orbit-history-rising-now" data-orbit-rising-open>Open Rising now →</a> Read the latest fitted climbs, coverage gaps and the drift lane’s own label warrant.'] },
        ],
      },
      {
        kicker: "WHAT WE CANNOT SEE",
        title: "The misses, named.",
        lead: "A method is only honest if its blind spots are on the page in the same ink as its successes. These are structural — they follow from what the input is, not from bugs — and the detector marks the ones it can detect itself. Where one of them has an answer, the answer is never a better step detector. It is a different question.",
        blocks: [
          {
            kind: "terms",
            items: [
              { term: "Continuous low thrust has no step", body: `Electric propulsion spreads its Δv over weeks, so the fits absorb it as a smooth trend. ${STARLINK_SPIRAL.name} climbed from ${STARLINK_SPIRAL.fromAKm.toLocaleString("en-GB")} km to ${STARLINK_SPIRAL.toAKm.toLocaleString("en-GB")} km — ${Math.round(STARLINK_SPIRAL.toAKm - STARLINK_SPIRAL.fromAKm)} kilometres and about ${spiralCost(STARLINK_SPIRAL.fromAKm, STARLINK_SPIRAL.toAKm).toFixed(0)} m/s — on krypton Hall thrusters, across ${STARLINK_SPIRAL.intervals.toLocaleString("en-GB")} intervals and ${STARLINK_SPIRAL.observedDays.toFixed(3)} observed days. Yet the step detector flagged ${STARLINK_SPIRAL.eventsFlagged} events: a hundred metres per second spent in plain sight. There is no step in those fits for it to see.`, operational: `Numbers from the ${BUNDLE_DATE} bundle — the spacecraft’s own climb is drawn on its card.` },
              { term: "So the site asks a different question", body: "The long-arc drift lane above asks whether an orbit sustains a positive slope within the drag regime. Drag takes energy out and cannot put it back, but catalogue fits can be wrong: the physical argument needs the lane’s own measured control before it earns propulsion wording. Its 120-day fit can miss shorter campaigns.", operational: "Above the gate or without coverage, we cannot tell here. A missing drift flag is not evidence that the spacecraft is not thrusting." },
              { term: "Small burns hide under the floor", body: "A correction smaller than the active channel's measured noise threshold is indistinguishable from fit scatter, one event at a time. Some of them come back as a cluster — the repetition lane above exists partly for exactly this — but a small, irregular, one-off burn is simply below this instrument's resolution, and the site does not pretend otherwise." },
              { term: "Storms mask thrust in LEO", body: "During a geomagnetic storm the thermosphere swells and drag on a whole shell surges — precisely when interesting behaviour is likeliest. When the drag correction's own uncertainty swallows the step, the detector refuses to apportion it and publishes the event with its honest signature: drag-and-thrust-not-separable. \"We cannot tell\" is a result, and it is shown as one." },
              { term: "The newest changes are the ones we decline", body: "A step has to still be there two days later, so a change in the last two days of an object’s coverage — or immediately before a gap in it — has nothing to persist into, and is refused rather than guessed at. A reboost flown on the archive’s final day is therefore missed. It is the right way round: the alternative is a detector whose newest and most eye-catching claims are its least tested ones.", operational: "The same rule governs the archive’s own gap. Nothing is interpolated across it, and an operator-published manoeuvre inside it is recorded as unscorable rather than as one the detector missed." },
            ],
          },
          {
            kind: "live",
            body: [
              "Everything measured in this chapter — the control counts, the cluster rhythms, the ISS comparisons — was copied from the bundle published on " + BUNDLE_DATE + " and will drift as the archive grows. The method does not drift with it: the browser prices, gates and labels every event exactly as described here, with the latest completed sweep's numbers.",
            ],
          },
        ],
      },
    ],
    sources: [
      { ref: "1", title: "Space-Track.org, 18th Space Defense Squadron", where: "the element sets themselves — general perturbations data, the only orbital-elements source this site uses" },
      { ref: "2", title: "Hoots & Roehrich, Spacetrack Report No. 3 (1980); Vallado, Crawford, Hujsak & Kelso, \"Revisiting Spacetrack Report #3\", AIAA 2006-6753", where: "SGP4, the meaning of fitted mean elements, and the WGS-72 constants (μ = 398600.8 km³/s²) the pipeline and this chapter's worked examples use", url: "https://arc.aiaa.org/doi/10.2514/6.2006-6753" },
      { ref: "3", title: "NASA Glenn Research Center, PIMS ISS reboost records", where: "the on-board Δv figures the worked ISS comparison quotes; reboost-by-reboost documents", url: "https://gipoc.grc.nasa.gov/wp/pims/handbook/" },
      { ref: "4", title: "Vallado, Fundamentals of Astrodynamics and Applications, 4th ed.", where: "vis-viva, the small-impulse element relations behind the three floors (Gauss's variational equations, ch. 9), and the plane-change geometry (ch. 6)" },
      { ref: "5", title: "Soop, Handbook of Geostationary Orbits (Kluwer, 1994)", where: "geostationary station-keeping: luni-solar inclination drift of 0.75–0.95°/yr, north-south budgets near 50 m/s per year, east-west budgets of a few m/s per year" },
      { ref: "6", title: "pipeline/orbit_events.py and pipeline/orbit_campaigns.py, this repository", where: "the method itself: the drag cohort, the natural floors, the three gates with their measured false-alarm ladder, the lower-bound Δv decomposition, and the label policy. The code is the authority wherever this page might have rotted" },
      { ref: "7", title: `This site's published bundle of ${BUNDLE_DATE} (data/manifest.json → orbitEvents and the per-object history shards)`, where: "every measured count on this page: the control rates, the ISS ground-truth table, the KOREASAT 5 cluster records, the coverage statistics. Re-published after each completed sweep; the browser carries the current values" },
    ],
  };
})();
