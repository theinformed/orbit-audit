/**
 * "Where the aurora and the ring current come from" — the chain, end to end.
 *
 * ## Why this page exists and why it is not a layer page
 *
 * Sean: *"Perhaps we should have a learning page that shows the generation of
 * the ring current and aurora and plasma sheet and plasmasphere....?"*
 *
 * Every layer page on this site is about a THING. This one is about a
 * SEQUENCE, and the sequence is the whole content: solar wind arrives, the
 * dayside reconnects, flux is carried over the poles into the tail, the sheet
 * thins, it snaps, and the same one event lights the aurora AND builds the ring
 * current while the cold plasmasphere underneath is eroded by the same
 * convection field. Four populations, one mechanism. Drawn separately they are
 * four unrelated pictures; drawn together they explain each other.
 *
 * ## It assembles rather than builds
 *
 * The two animations here already existed and are reused verbatim through
 * `mechanismFigure`, which returns the same `.layer-figure` markup the layer
 * pages use, so this page introduces no second treatment of a video and no
 * third Manim lane:
 *
 *   - `dayside-reconnection` already runs the spine of this page — northward
 *     Bz with nothing opening, southward Bz, the X-point, tail loading, tail
 *     reconnection, injection, sunward return.
 *   - `trapped-motion` covers gyration, bounce and drift, and the fact that
 *     ions go west while electrons go east, which is why the ring current is a
 *     current at all.
 *
 * Both are badged SCHEMATIC on the frame as well as beside it.
 *
 * ## The correction this page exists partly to make
 *
 * The plasma sheet does not DRIVE the snap-back. It is WHERE the snap-back
 * happens. The driver is dayside reconnection under southward Bz stripping flux
 * into the tail lobes; that loading thins the sheet until it reconnects at a
 * near-Earth neutral line, and only then is the sheet the reservoir that gets
 * flung earthward. Stage 4 says this in those terms, because it is the single
 * most common way to get this chain backwards.
 *
 * ## Nothing here is a wall of text
 *
 * Two sentences per stage, then the evidence. Sean's standing rule: "stop
 * adding filler/fluff text to my site", and "seeing a graphic is much more
 * useful than reading text in most cases". The stage table and the two
 * animations carry the argument; the prose only says which question each one
 * answers.
 */

import "./substorm-chain-page.css";

import { mechanismFigure } from "./mechanism-animations";
import {
  INNER_EDGE_INJECTED_RE,
  INNER_EDGE_QUIET_RE,
  OUTER_EDGE_RE,
} from "./inner-plasma-sheet";
import {
  INJECTION_REFERENCE_DROP_NT,
  LOADING_REFERENCE_NT_MINUTES,
  LOADING_WINDOW_MINUTES,
  SUBSTORM_ONSET_CRITERION,
} from "./substorm-chain";

type Stage = {
  index: string;
  title: string;
  /** Two sentences. A test enforces it. */
  lead: string;
  /** What in this site's published data marks this beat, or the honest "nothing". */
  marker: string;
  /** Where a reader can watch it, on the globe or on this page. */
  seeIt: string;
};

/**
 * The four populations, as the table that makes them one system.
 *
 * The order is by radius, because that is the thing a reader has to hold: the
 * chain runs from the outside in, and the two populations that get confused for
 * each other — the plasma sheet and the plasmasphere — are at opposite ends of
 * it and could not be more different.
 */
const POPULATIONS: Array<{ name: string; where: string; what: string; role: string; drawn: string }> = [
  {
    name: "Plasma sheet",
    where: `10–30 Rₑ down the tail; the site draws its inner end, L ${INNER_EDGE_INJECTED_RE}–${OUTER_EDGE_RE}`,
    what: "Hot, keV. Thin — a fraction of an Earth radius at its centre.",
    role: "The reservoir. It is loaded during southward Bz, and it is WHERE the snap happens.",
    drawn: "Its inner end is on the globe, on the <em>Plasma sheet → ring current</em> layer.",
  },
  {
    name: "Ring current",
    where: "L 2–7",
    what: "Hot, tens to hundreds of keV, drifting westward around the Earth.",
    role: "Where the injected ions end up. Its field opposes Earth's at the ground, which is what Dst measures.",
    drawn: "On the globe, on the same layer, inside the sheet's inner edge.",
  },
  {
    name: "Radiation belts",
    where: "L 1.2–7",
    what: "Relativistic — MeV, not keV. A different population in the same space.",
    role: "Accelerated out of the same source over days, not minutes. Not the ring current.",
    drawn: "Its own globe layer, from NOAA/NASA RBE electron flux.",
  },
  {
    name: "Plasmasphere",
    where: "inside about L 4",
    what: "Cold — about 1 eV, electron-volts being the energy scale of single particles; a keV is a thousand of them, an MeV a million — and dense. Ionospheric plasma, corotating with the Earth.",
    role: "Not part of the injection at all. It is ERODED by the same convection field that drives it.",
    drawn: "As a plan-view chart on Current conditions, because at this scale it is a 26-pixel annulus on the globe.",
  },
];

const STAGES: Stage[] = [
  {
    index: "1",
    title: "The wind arrives, and mostly goes past",
    lead:
      "The solar wind reaches Earth already carrying the Sun's magnetic field frozen into it, and the magnetosphere is an obstacle in that flow rather than a sponge in it. Most of the wind is deflected around the boundary, accelerates down the flanks and streams away downstream — which is what forms the tail.",
    marker:
      "MEASURED. Speed, density and the full IMF vector at L1, propagated to Earth arrival: 586 samples at 5-minute cadence over 48.8 hours in every release.",
    seeIt: "Globe · <em>Solar wind &amp; IMF</em>. Watch the flow wrap the dayside, accelerate down the flanks and stream away downstream.",
  },
  {
    index: "2",
    title: "Southward Bz opens the dayside",
    lead:
      "When the arriving field points south it is antiparallel to Earth's field at the nose, and the two reconnect. Northward Bz does not do this, which is why one number — Bz — decides whether anything happens at all.",
    marker:
      "MEASURED, and it is the number the whole chain turns on. Bz in the standard Sun-referenced frame (GSM), at Earth arrival, in the same driver series.",
    seeIt: "The animation above opens on exactly this, with northward Bz first so the contrast is the point.",
  },
  {
    index: "3",
    title: "Open flux is carried over the poles into the tail",
    lead:
      "Each newly opened field line is dragged antisunward over the polar cap by the flow and stacked into the tail lobes. The lobes gain magnetic flux, the cross-tail current strengthens, and the plasma sheet between them gets THINNER — which is the opposite of what most people expect a loading tail to do.",
    marker:
      `MEASURED, as a time integral. The site sums the southward part of Bz over the last ${LOADING_WINDOW_MINUTES} minutes; ${LOADING_REFERENCE_NT_MINUTES} nT·min — 90 minutes at −5 nT — counts as a full load.`,
    seeIt: `Globe · scrub the clock. The sheet's inner edge comes in from L ${INNER_EDGE_QUIET_RE} and the sheet visibly thins as the integral rises.`,
  },
  {
    index: "4",
    title: "It snaps — at a near-Earth neutral line",
    lead:
      "The thinned sheet reconnects, typically 15–25 Rₑ down the tail, and the stored flux is released. The plasma sheet does not cause this: dayside reconnection under southward Bz is what loaded the tail, and the sheet is simply where the release happens and what gets flung earthward.",
    marker:
      `MEASURED, where the site has the index. A substorm onset IS a sharp negative excursion of the westward auroral electrojet — the concentrated east–west current flowing in the auroral ionosphere near 100 km — a fall of at least ${SUBSTORM_ONSET_CRITERION.minimumDropNt} nT within ${SUBSTORM_ONSET_CRITERION.windowMinutes} minutes, not already falling that fast. On the real May 2024 Gannon SuperMAG record that criterion finds 39 onsets in 120 hours, the deepest a 2,518 nT drop.`,
    seeIt:
      "NOT on the live globe, and the layer card says so. No auroral-electrojet index is published live to this site, so no onset time is claimed for the present.",
  },
  {
    index: "5",
    title: "One injection, two consequences",
    lead:
      "Particles flung earthward follow the field down into the atmosphere at auroral latitudes, and they also drift — ions west, electrons east — into closed paths around the Earth. That is the whole point of this page: the aurora and the ring current are the same event seen at two radii.",
    marker:
      `MEASURED at both ends. OVATION gives the precipitation probability where the particles land; Kyoto Dst gives the ring-current response hourly over seven days. A ${INJECTION_REFERENCE_DROP_NT} nT electrojet drop counts as a fully driven injection.`,
    seeIt:
      `Globe · <em>Auroral oval</em> and <em>Plasma sheet → ring current</em> together. The sheet's inner edge drives in to L ${INNER_EDGE_INJECTED_RE} — inside geostationary orbit, which is why a substorm is felt there.`,
  },
  {
    index: "6",
    title: "And the cold plasma underneath is eroded by the same field",
    lead:
      "The convection field that drives all of the above also strips the outer plasmasphere away, dragging a plume sunward through the afternoon sector. It is the only one of the four populations that is not being injected — it is being taken apart.",
    marker:
      "MODELLED, and coupled. Over 48 hours at Kp 1.67–5.33 the published DGCPM run puts the nightside plasmapause at L 4.39 → 3.55 → 4.39 and grows the plume from 0.19 to 1.69 L, with its peak rotating through eight hours of local time.",
    seeIt:
      "Current conditions · the plasmapause chart, at the foot of the page. On the globe this whole motion is 5 pixels, which is why it is a chart.",
  },
];

function populationRows(): string {
  return POPULATIONS.map((population) => `
      <div>
        <dt>${population.name} <small>${population.where}</small></dt>
        <dd><strong>${population.what}</strong> ${population.role}<br><em>${population.drawn}</em></dd>
      </div>`).join("");
}

function stageCard(stage: Stage): string {
  return `
    <article class="mechanism-entry chain-stage">
      <p class="section-kicker">STAGE ${stage.index}</p>
      <h3>${stage.title}</h3>
      <p>${stage.lead}</p>
      <dl class="chain-stage-evidence">
        <div><dt>What measures this beat</dt><dd>${stage.marker}</dd></div>
        <div><dt>Where to watch it</dt><dd>${stage.seeIt}</dd></div>
      </dl>
    </article>`;
}

/**
 * The page. Static markup, like every other content module here, so it can be
 * asserted on directly by a test without a browser.
 */
export function substormChainPageView(): string {
  return `
    <button type="button" class="link-button layer-page-back" data-layer-index>← All layers</button>
    <header class="content-hero layer-page-hero">
      <p class="eyebrow">THE CHAIN · SOLAR WIND TO AURORA AND RING CURRENT · SIX STAGES</p>
      <h1>Where the aurora and the ring current come from.</h1>
      <p>They come from the same event. A substorm loads the magnetotail, snaps, and throws plasma back at the Earth; what lands in the atmosphere is the aurora and what stays in orbit around it is the ring current. This page follows that from the solar wind to both ends of it, and says at each beat what is measured and what is only drawn.</p>
    </header>

    <section class="method-section">
      <div class="method-section-head">
        <span class="section-kicker">FOUR POPULATIONS, ONE SYSTEM</span>
        <h2>Which plasma is which.</h2>
        <p>Two of these are constantly confused for each other, and they are at opposite ends of the chain. The plasma sheet is hot and thin and far out; the plasmasphere is cold and dense and close in. Nothing about one tells you anything about the other.</p>
      </div>
      <div class="method-grid layer-page-methods">
        <details class="method-card" open>
          <summary><strong>The four populations</strong><small>by distance, because the chain runs from the outside in</small></summary>
          <div class="method-card-body"><dl>${populationRows()}</dl></div>
        </details>
      </div>
    </section>

    <section class="method-section">
      <div class="method-section-head">
        <span class="section-kicker">HOW THE WIND GETS IN</span>
        <h2>Watch it rather than read it.</h2>
        <p>Stages 2 to 5 are this animation. It opens on northward Bz with nothing happening, which is the control.</p>
      </div>
      ${mechanismFigure("dayside-reconnection")}
    </section>

    <section class="method-section">
      <div class="method-section-head">
        <span class="section-kicker">THE SIX STAGES</span>
        <h2>What happens, and what measures it.</h2>
      </div>
      ${STAGES.map(stageCard).join("")}
    </section>

    <section class="method-section">
      <div class="method-section-head">
        <span class="section-kicker">WHY THE RING CURRENT IS A CURRENT</span>
        <h2>Ions west, electrons east — and they add.</h2>
        <p>The last beat of the chain, on its own. Two species drifting opposite ways around the Earth carry current the SAME way, and the field of that current opposes Earth's at the ground. That is what Dst is measuring.</p>
      </div>
      ${mechanismFigure("trapped-motion")}
    </section>

    <aside class="teaching-callout"><strong>The one thing to take away</strong>The aurora and the ring current are not two phenomena that happen to correlate. They are one injection, seen at two radii — and that is why this site draws the plasma sheet and the ring current on a single switch.</aside>
  `;
}
