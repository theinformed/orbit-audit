/**
 * HOW THE NUMBERS ARE MADE — the flagship methods page.
 *
 * Sean, 2026-09-20: "make a page on the space site that clearly and concisely
 * explains all this ... STEM folks with mixed backgrounds ... start with the
 * basics and then work your way towards how all this works ... show the
 * orbital characteristics and the corresponding equations ... the GPU work ...
 * our confidence in our labels. Make a really excellent page that lets us be
 * proud of our work."
 *
 * One page, one arc, five figures, told for a smart reader who is NOT already
 * an orbital mechanic: an orbit is six numbers -> what a burn looks like in the
 * data -> why a graphics card does the arithmetic -> how debris grades us for
 * free -> the three failures and the flip that earned the word "manoeuvre".
 *
 * EVERY NUMBER IS MEASURED. Each figure is a verified inline SVG whose elements
 * carry data-beat="n"; the same figure is the base for a narrated clip, revealed
 * as a pure function of time (the site's shipped clips lane). The video slot is
 * declared per clip; when the rendered mp4+captions are present the slot plays,
 * otherwise the static figure stands on its own. Numbers verified against
 * public/ops/computation-methods.html and
 * docs/orbit-phase2b-corroboration-20260920.md on 2026-09-20.
 */

export interface OrbitClip {
  /** matches data-clip on the figure and the narration scene id */
  readonly id: string;
  readonly title: string;
  /** true once media/orbit-methods/<id>.mp4 + .vtt are rendered and served */
  readonly available: boolean;
  /** runtime URL of the muxed mp4, resolved by the mount */
  readonly src?: string;
  /** runtime URL of the WebVTT caption track */
  readonly captions?: string;
  /** runtime URL of the poster frame (the fully revealed figure) */
  readonly poster?: string;
  /** seconds, for the caption line under the button */
  readonly seconds?: number;
}

/**
 * The clip roster. `available` is false until the narrated renders land; the
 * page is COMPLETE either way because every figure reads statically. Flipping a
 * clip to available (and adding its mp4/vtt) lights its player with no other
 * change — that is the finish step gated on Sean's voice approval.
 */
// mp4/png ride Vite's dynamic new URL glob (built-in asset types); .vtt does
// not — dynamic URLs for it are left unresolved — so captions import statically.
import orbitBasicsVtt from "../media/orbit-methods/orbit-basics.vtt";
import theStepVtt from "../media/orbit-methods/the-step.vtt";
import theArithmeticVtt from "../media/orbit-methods/the-arithmetic.vtt";
import theGateVtt from "../media/orbit-methods/the-gate.vtt";
import earningItVtt from "../media/orbit-methods/earning-it.vtt";
const clipSrc = (stem: string) => new URL(`../media/orbit-methods/${stem}.mp4`, import.meta.url).href;
const clipPoster = (stem: string) => new URL(`../media/orbit-methods/${stem}-poster.png`, import.meta.url).href;

export const ORBIT_METHODS_CLIPS: readonly OrbitClip[] = [
  { id: "orbit-basics", title: "An orbit is six numbers", available: true,
    src: clipSrc("orbit-basics"), captions: orbitBasicsVtt,
    poster: clipPoster("orbit-basics"), seconds: 50 },
  { id: "the-step", title: "What a burn looks like", available: true,
    src: clipSrc("the-step"), captions: theStepVtt,
    poster: clipPoster("the-step"), seconds: 47 },
  { id: "the-arithmetic", title: "Why a graphics card", available: true,
    src: clipSrc("the-arithmetic"), captions: theArithmeticVtt,
    poster: clipPoster("the-arithmetic"), seconds: 51 },
  { id: "the-gate", title: "Debris grades us for free", available: true,
    src: clipSrc("the-gate"), captions: theGateVtt,
    poster: clipPoster("the-gate"), seconds: 46 },
  { id: "earning-it", title: "Three failures, then the flip", available: true,
    src: clipSrc("earning-it"), captions: earningItVtt,
    poster: clipPoster("earning-it"), seconds: 47 },
];

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const clipById = new Map(ORBIT_METHODS_CLIPS.map((c) => [c.id, c]));

/** The play affordance under a figure. Present but honest when media is pending. */
function clipSlot(id: string): string {
  const clip = clipById.get(id);
  if (!clip) return "";
  if (clip.available && clip.src) {
    return `<div class="om-clip-slot" data-clip="${esc(id)}"
        data-src="${esc(clip.src)}" data-captions="${esc(clip.captions ?? "")}"
        data-poster="${esc(clip.poster ?? "")}">
      <button type="button" class="om-play" aria-expanded="false">
        <span aria-hidden="true">&#9654;</span> Narrated walkthrough${
          clip.seconds ? ` &middot; ${Math.round(clip.seconds)}s` : ""}
      </button>
    </div>`;
  }
  return `<p class="om-clip-pending" data-clip="${esc(id)}">A narrated walkthrough of
    this figure, in Sean's own voice, is being rendered; the diagram above tells the
    whole story without sound.</p>`;
}

/** One numbered section: figure (scrollable) + its clip slot + prose blocks. */
function section(n: number, id: string, heading: string, figure: string, clipId: string,
                 blocks: string[]): string {
  return `<section class="fund-section om-section" id="om-${esc(id)}" aria-labelledby="om-${esc(id)}-h">
    <p class="om-step">STEP ${n} OF 5</p>
    <h2 id="om-${esc(id)}-h">${heading}</h2>
    <figure class="fund-figure-scroll om-figure" data-clip="${esc(clipId)}">
      ${figure}
    </figure>
    ${clipSlot(clipId)}
    ${blocks.map((b) => `<p>${b}</p>`).join("\n    ")}
  </section>`;
}

/* --------------------------------------------------------------------------
 * FIGURES. Each is a self-contained, theme-aware inline SVG. Elements that a
 * narrated clip reveals in sequence carry data-beat="n" (0 = base layer, always
 * shown). The site's fund-svg-* classes carry the theme colours.
 * ------------------------------------------------------------------------ */

const FIG_ORBIT = `<svg viewBox="0 0 720 380" class="om-svg" role="img"
  aria-label="An elliptical orbit around Earth with its six defining elements labelled.">
  <title>An orbit is six numbers</title>
  <ellipse cx="330" cy="190" rx="250" ry="150" class="fund-svg-small" fill="none" stroke-width="2"/>
  <circle cx="470" cy="190" r="34" class="fund-svg-key" data-beat="0"/>
  <text x="470" y="195" text-anchor="middle" class="om-lab" data-beat="0">Earth</text>
  <line x1="80" y1="190" x2="580" y2="190" class="fund-svg-num" stroke-width="1.5" data-beat="1"/>
  <text x="120" y="178" class="om-lab" data-beat="1">semi-major axis a</text>
  <path d="M470 190 L610 96" class="fund-svg-warm" stroke-width="1.5" data-beat="2"/>
  <text x="560" y="120" class="om-lab" data-beat="2">eccentricity e</text>
  <path d="M330 40 A 40 40 0 0 1 410 60" fill="none" class="fund-svg-hot" stroke-width="1.5" data-beat="3"/>
  <text x="345" y="30" class="om-lab" data-beat="3">inclination i</text>
  <circle cx="90" cy="190" r="5" class="fund-svg-hot" data-beat="4"/>
  <text x="60" y="215" class="om-lab" data-beat="4">RAAN &#937;, argp &#969;, anomaly &#957;</text>
  <circle cx="150" cy="112" r="6" class="fund-svg-warm" data-beat="5"/>
  <text x="150" y="100" text-anchor="middle" class="om-lab" data-beat="5">a satellite</text>
</svg>`;

const FIG_STEP = `<svg viewBox="0 0 720 360" class="om-svg" role="img"
  aria-label="Semi-major axis over time: a gentle drag decay, a sudden step where a burn happens, and a median baseline that refuses to follow the step.">
  <title>What a burn looks like</title>
  <line x1="70" y1="30" x2="70" y2="320" class="fund-svg-num" stroke-width="1.5"/>
  <line x1="70" y1="320" x2="690" y2="320" class="fund-svg-num" stroke-width="1.5"/>
  <text x="18" y="180" class="om-lab" transform="rotate(-90 18 180)">semi-major axis</text>
  <text x="360" y="350" text-anchor="middle" class="om-lab">time (element sets, one to three a day)</text>
  <path d="M70 120 L340 176" class="fund-svg-small" fill="none" stroke-width="2.5" data-beat="0"/>
  <path d="M340 96 L690 150" class="fund-svg-small" fill="none" stroke-width="2.5" data-beat="1"/>
  <line x1="340" y1="176" x2="340" y2="96" class="fund-svg-hot" stroke-width="2" stroke-dasharray="5 4" data-beat="1"/>
  <text x="352" y="120" class="om-lab" data-beat="1">the burn: a step, held</text>
  <path d="M70 128 L340 184 L690 158" class="fund-svg-warm" fill="none" stroke-width="1.5"
    stroke-dasharray="2 5" data-beat="2"/>
  <text x="470" y="205" class="om-lab" data-beat="2">median baseline &#8212; will not chase one point</text>
  <rect x="300" y="150" width="80" height="52" class="fund-svg-key" opacity="0.18" data-beat="3"/>
  <text x="392" y="238" class="om-lab" data-beat="3">flag only if the step clears &#954; &#215; the noise, and stays two days</text>
</svg>`;

const FIG_GPU = `<svg viewBox="0 0 720 360" class="om-svg" role="img"
  aria-label="One slow CPU lane versus many parallel GPU lanes, with the ninety-three to seven split between arithmetic and reading.">
  <title>Why a graphics card</title>
  <text x="60" y="52" class="om-lab" data-beat="0">one core, one object at a time</text>
  <rect x="60" y="64" width="120" height="26" class="fund-svg-warm" opacity="0.5" data-beat="0"/>
  <path d="M188 77 L250 77" class="fund-svg-num" stroke-width="1.5" marker-end="url(#omArrow)" data-beat="0"/>
  <text x="60" y="150" class="om-lab" data-beat="1">a graphics card, thousands at once</text>
  ${Array.from({ length: 6 }, (_v, i) =>
    `<rect x="60" y="${164 + i * 20}" width="120" height="14" class="fund-svg-key" opacity="0.5" data-beat="1"/>`
  ).join("")}
  <text x="330" y="150" class="om-lab" data-beat="2">92.6% is identical small arithmetic &#8212; the card's shape</text>
  <text x="330" y="176" class="om-lab" data-beat="2">7.4% is reading; 0.26% is branchy judgement &#8212; kept on the CPU</text>
  <text x="330" y="240" class="om-lab" data-beat="3">checked answer-for-answer:</text>
  <text x="330" y="266" class="fund-svg-hot om-big" data-beat="3">4 278 167 comparisons</text>
  <text x="330" y="292" class="om-lab" data-beat="3">zero disagreements before it was trusted</text>
  <defs><marker id="omArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
    <path d="M0 0 L6 3 L0 6 z" class="fund-svg-num"/></marker></defs>
</svg>`;

const FIG_GATE = `<svg viewBox="0 0 720 360" class="om-svg" role="img"
  aria-label="Two rates as bars with confidence bounds: the false-alarm floor from debris, far below the payload rate, separated by more than ten times.">
  <title>Debris grades us for free</title>
  <line x1="70" y1="30" x2="70" y2="300" class="fund-svg-num" stroke-width="1.5"/>
  <line x1="70" y1="300" x2="690" y2="300" class="fund-svg-num" stroke-width="1.5"/>
  <text x="360" y="336" text-anchor="middle" class="om-lab">flags per 1,000 intervals (log)</text>
  <rect x="70" y="250" width="70" height="30" class="fund-svg-key" data-beat="0"/>
  <text x="150" y="270" class="om-lab" data-beat="0">debris (cannot manoeuvre): 0.162 &#8212; the free blank</text>
  <line x1="120" y1="245" x2="180" y2="245" class="fund-svg-num" stroke-width="1.5" data-beat="1"/>
  <text x="188" y="242" class="om-lab" data-beat="1">95% upper bound &#8212; the honest ceiling</text>
  <rect x="70" y="150" width="360" height="30" class="fund-svg-warm" data-beat="2"/>
  <text x="440" y="170" class="om-lab" data-beat="2">payloads: 2.95 &#8212; what real satellites do</text>
  <line x1="70" y1="110" x2="690" y2="110" class="fund-svg-hot" stroke-width="2" stroke-dasharray="6 4" data-beat="3"/>
  <text x="80" y="102" class="om-lab" data-beat="3">the gate: say "manoeuvre" only past 10&#215; separation</text>
  <text x="80" y="60" class="fund-svg-hot om-big" data-beat="4">18.19&#215;</text>
  <text x="230" y="60" class="om-lab" data-beat="4">measured separation &#8212; earned, not assumed</text>
</svg>`;

const FIG_FLIP = `<svg viewBox="0 0 720 340" class="om-svg" role="img"
  aria-label="A timeline of separation: three failed drift designs below the ten-times line, then v4 above it, then the jump to eighteen.">
  <title>Three failures, then the flip</title>
  <line x1="70" y1="40" x2="70" y2="290" class="fund-svg-num" stroke-width="1.5"/>
  <line x1="70" y1="290" x2="690" y2="290" class="fund-svg-num" stroke-width="1.5"/>
  <text x="18" y="165" class="om-lab" transform="rotate(-90 18 165)">separation (&#215;)</text>
  <line x1="70" y1="150" x2="690" y2="150" class="fund-svg-hot" stroke-width="1.5" stroke-dasharray="6 4" data-beat="0"/>
  <text x="600" y="142" class="om-lab" data-beat="0">10&#215; gate</text>
  <circle cx="150" cy="268" r="6" class="fund-svg-warm" data-beat="1"/>
  <text x="150" y="288" text-anchor="middle" class="om-lab" data-beat="1">0.21&#215;</text>
  <circle cx="250" cy="272" r="6" class="fund-svg-warm" data-beat="1"/>
  <text x="250" y="292" text-anchor="middle" class="om-lab" data-beat="1">0.16&#215;</text>
  <circle cx="350" cy="258" r="6" class="fund-svg-warm" data-beat="1"/>
  <text x="350" y="248" text-anchor="middle" class="om-lab" data-beat="1">0.40&#215; &#8212; inverted, all rejected</text>
  <circle cx="470" cy="120" r="7" class="fund-svg-key" data-beat="2"/>
  <text x="470" y="108" text-anchor="middle" class="om-lab" data-beat="2">v4: 10.88&#215;</text>
  <path d="M500 120 L610 66" class="fund-svg-num" stroke-width="1.5" marker-end="url(#omArrow2)" data-beat="3"/>
  <circle cx="620" cy="60" r="8" class="fund-svg-hot" data-beat="3"/>
  <text x="620" y="46" text-anchor="middle" class="fund-svg-hot om-big" data-beat="3">18.19&#215;</text>
  <defs><marker id="omArrow2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
    <path d="M0 0 L6 3 L0 6 z" class="fund-svg-num"/></marker></defs>
</svg>`;

const STYLE = `<style>
  .orbit-methods { max-width: 62rem; }
  .om-hero { margin: 0 0 1.5rem; }
  .om-hero h1 { line-height: 1.15; }
  .om-lede { font-size: 1.08rem; color: var(--text); }
  .om-map { border: 1px solid var(--line); border-radius: 8px; padding: 0.4rem 1rem;
    margin: 1.2rem 0; color: var(--muted); }
  .om-map li { margin: 0.3rem 0; }
  .om-section { margin: 2.4rem 0; }
  .om-step { font: 600 0.72rem/1 var(--mono, ui-monospace, monospace); letter-spacing: 0.14em;
    color: var(--accent, var(--muted)); margin: 0 0 0.2rem; }
  .om-figure { margin: 0.8rem 0 0.4rem; }
  .om-svg { width: 100%; height: auto; max-width: 720px; }
  .om-lab { font: 500 13px/1.2 var(--sans, system-ui, sans-serif); fill: var(--text); }
  .om-big { font: 700 22px/1 var(--sans, system-ui, sans-serif); }
  .om-clip-slot { margin: 0.2rem 0 0.6rem; }
  .om-play { font: 600 0.9rem/1 inherit; padding: 0.5rem 0.9rem; border-radius: 6px;
    border: 1px solid var(--line-strong, var(--line)); background: var(--surface, transparent);
    color: var(--text); cursor: pointer; }
  .om-play:hover { border-color: var(--accent, var(--line-strong)); }
  .om-clip-pending { font-size: 0.86rem; color: var(--muted); font-style: italic;
    margin: 0.1rem 0 0.6rem; }
  .om-video { width: 100%; max-width: 720px; border-radius: 8px; display: block; margin: 0.4rem 0; }
  .om-formula { font-size: 1.15rem; text-align: center; margin: 1rem 0; color: var(--text); }
  .om-worked { border-left: 3px solid var(--line-strong, var(--line)); padding: 0.2rem 0 0.2rem 1rem;
    color: var(--muted); margin: 0.8rem 0; }
  .om-close { border-top: 1px solid var(--line); margin-top: 2.6rem; padding-top: 1.2rem; color: var(--muted); }
  .om-close h2 { color: var(--text); }
</style>`;

export function orbitMethodsPageView(): string {
  const sections = [
    section(1, "orbit", "An orbit is six numbers", FIG_ORBIT, "orbit-basics", [
      `A satellite's whole future is pinned by six numbers &#8212; the size and stretch of its
       ellipse, how the ellipse is tilted and turned in space, and where along it the craft is
       right now. The government catalogue publishes these, refreshed for tens of thousands of
       objects several times a day. Everything on this site starts from that daily stream.`,
      `The one we watch hardest is the size, the <em>semi-major axis</em>. It hides inside a
       number the catalogue actually reports, the mean motion &#8212; how many laps a day the
       object turns. A little arithmetic converts one to the other:`,
      `<span class="om-formula"><i>a</i> = (<i>&#956;</i> / <i>n</i>&#178;)<sup>1/3</sup></span>`,
      `<span class="om-worked">Worked, for a real low-orbit satellite: <i>n</i> = 15.44218077 laps
       a day, and Earth's gravitational constant <i>&#956;</i> = 398,600.8&nbsp;km&#179;/s&#178;,
       give <i>a</i> = 6,811.8&nbsp;km &#8212; about 434&nbsp;km above the ground. Every figure
       we publish is exact to the last digit the catalogue supplies, because the numbers are
       stored as whole integers, never rounded on the way in.</span>`,
    ]),
    section(2, "step", "What a burn looks like in the data", FIG_STEP, "the-step", [
      `Left to itself, a low orbit sinks: the thin upper air drags on it and the curve slides
       gently downward, day after day. That decay is not noise to be removed &#8212; it is a
       measurement of the atmosphere, and the spacecraft is the instrument.`,
      `A manoeuvre is different. It is a <em>step</em>: the size jumps and then stays at the new
       value. To catch a step without being fooled by a single bad fit, we compare each point
       to a <em>median</em> of the two months around it. A median cannot be dragged by one
       outlier &#8212; and, importantly, a burst of thrust cannot become its own baseline.`,
      `We raise a flag only when the step clears a firm multiple of that object's own scatter,
       and only when it is <em>still there</em> two days later. Every published figure is a
       lower bound: the least a real operator could have spent to make the change we see.`,
    ]),
    section(3, "arithmetic", "Why a graphics card does the arithmetic", FIG_GPU, "the-arithmetic", [
      `We do not keep yesterday's answer and patch it. Every day the detector re-reads all
       216,203,378 catalogue records and works the whole thing out from scratch. That is a
       deliberate honesty choice: the same input always gives the same answer, with nothing
       carried forward that could quietly rot.`,
      `Done from scratch, that is a mountain of arithmetic &#8212; but arithmetic of a very
       particular shape: tens of millions of identical little calculations, all independent.
       That shape is exactly what a graphics card is built for. We measured the split: 92.6% of
       the work is that repetitive arithmetic, which moved to the card; 7.4% is reading the data;
       and a mere 0.26% is the branchy judgement of naming what kind of change it was, which stays
       on the ordinary processor where branchy work belongs.`,
      `Moving math to a graphics card is only safe if it gives the <em>same</em> answer. Before
       we trusted it we ran both machines side by side and compared every result: 4,278,167
       comparisons, zero disagreements. Only then did the card take over &#8212; handing roughly
       a dozen processor cores back to the rest of the machine, which also serves the weather
       site next door.`,
    ]),
    section(4, "gate", "How debris grades our confidence, for free", FIG_GATE, "the-gate", [
      `Here is the part we are proudest of. How do you know a manoeuvre detector is honest?
       You test it on things that <em>cannot</em> manoeuvre. Dead rocket bodies and debris have
       no engines, so every flag the detector raises on one of them is, by definition, a false
       alarm. That gives us a free, always-on measure of how often we cry wolf.`,
      `That false-alarm rate is now 0.162 flags per 1,000 intervals &#8212; and we read it at its
       statistical ceiling, not its rosiest estimate. Real payloads flag far more often, at 2.95.
       The distance between "what things with engines do" and "what engineless junk does" is the
       whole ballgame, and we require it to be a wide margin before we will use a strong word.`,
      `The rule is fixed and public: the site may print the word <em>manoeuvre</em> only when
       that separation clears ten times. It is measured today at 18.19 times. Until it crossed,
       every event said <em>candidate</em> instead &#8212; the site refusing to flatter itself.
       That wording is wired to the measured number; no one types it by hand.`,
    ]),
    section(5, "earning", "Told straight: three failures, then the flip", FIG_FLIP, "earning-it", [
      `Good science includes what did not work. Our long-arc drift detector &#8212; the one that
       looks for slow, gradual climbs rather than sudden steps &#8212; failed its own debris test
       three times, each design flagging junk <em>more</em> often than satellites: separations of
       0.21, 0.16, and 0.40 times, all rejected.`,
      `The fix came from physics, not a bigger computer. Below 800&nbsp;km the air drags
       everything down, so nothing without an engine can sustain a climb there. Trusting only
       sustained climbs in that region turned the fourth design from useless to sharp: 10.88
       times separation, zero false alarms across 4,107 pieces of debris, and the real climbers
       it caught were overwhelmingly the constellations known to be raising.`,
      `A sister insight fixed the step detector the same week. A real change of orbit costs
       energy, so a tilt change with no matching energy change is noise &#8212; and three
       quarters of its remaining false alarms were exactly that. Requiring corroboration took the
       separation from 6.90 to 18.19 times in a single change, while leaving every real
       geostationary station-keeping catch untouched and counting all 40,300 of the newly
       withheld judgements out loud. That is the day the site earned the word.`,
    ]),
  ].join("\n");

  return `<div class="orbit-methods fundamentals-page">
  ${STYLE}
  <header class="om-hero">
    <p class="om-step">HOW THE NUMBERS ARE MADE</p>
    <h1>From two million numbers a day to one honest sentence about a satellite</h1>
    <p class="om-lede">This site watches tens of thousands of spacecraft and, for each one, tries
      to answer a hard question honestly: did it fire its engine? Here is the whole chain &#8212;
      the orbital basics, the arithmetic, the graphics cards that make it fast, and the discipline
      that decides what we are allowed to claim. No prior orbital mechanics assumed; every number
      on this page is measured.</p>
    <ul class="om-map">
      <li>An orbit is six numbers &#8212; and one equation ties them to the sky.</li>
      <li>A manoeuvre is a step in the data; drag is a slow slide; a median tells them apart.</li>
      <li>216 million records, re-worked from scratch daily &#8212; on graphics cards, proven exact.</li>
      <li>Debris cannot manoeuvre, so it grades our false-alarm rate for free.</li>
      <li>Three failures, told straight, and the insight that earned the word "manoeuvre".</li>
    </ul>
  </header>
  ${sections}
  <footer class="om-close">
    <h2>What we do and do not claim</h2>
    <p>Every cost we print is a <em>lower bound</em>. An event is a <em>candidate</em> unless the
      measured separation clears the gate. The drift detector is blind to satellites that hold
      their station continuously, to orbit-lowering, and to anything above the drag regime &#8212;
      limits we state rather than hide. You can watch all of this live in the orbit-history
      browser, rebuilt from the raw catalogue every few hours. Figures verified 20 September 2026.</p>
  </footer>
</div>`;
}

/**
 * Wire the narrated-clip buttons. Static figures need no JavaScript; this only
 * upgrades a slot to a player when its media is present. Safe to call on a page
 * with no available clips (it simply binds nothing).
 */
export function mountOrbitMethods(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>(".om-clip-slot").forEach((slot) => {
    const button = slot.querySelector<HTMLButtonElement>("button.om-play");
    const src = slot.dataset.src;
    if (!button || !src) return;
    button.addEventListener("click", () => {
      if (slot.querySelector("video")) return; // already open
      const video = document.createElement("video");
      video.className = "om-video";
      video.controls = true;
      video.playsInline = true;
      video.preload = "none";
      const poster = slot.dataset.poster;
      if (poster) video.poster = poster;
      video.src = src;
      const captions = slot.dataset.captions;
      if (captions) {
        const track = document.createElement("track");
        track.kind = "captions";
        track.src = captions;
        track.default = true;
        track.srclang = "en";
        track.label = "English";
        video.appendChild(track);
      }
      slot.appendChild(video);
      button.setAttribute("aria-expanded", "true");
      button.hidden = true;
      // Playback is optional: some environments (and test runners) do not
      // implement media playback. The reader can always press play.
      try {
        const started = video.play();
        if (started && typeof started.catch === "function") started.catch(() => {});
      } catch { /* reader can press play */ }
    });
  });
}
