import { learningCheck } from "./learning-checks";
import { learningSources, WEATHER_SOURCES, sourceLinks, weatherFactProvenance } from "./learning-provenance";
import { weatherLearningFigure } from "./weather-learning-figures";
import { evidenceBadge, evidenceGuide, evidenceNames, EVIDENCE, type Evidence } from "./learning-evidence";
import { withLearningContents } from "./learning-sections";
import type { EventsBundle, HistoricalEvent } from "./types";
import { MECHANISM_ANIMATIONS, mechanismAnimation, mechanismFigure, mechanismLibrarySection, mechanismLibraryRuntime } from "./mechanism-animations";
import { LAYER_PAGE_COUNTS } from "./layer-pages";
import { countWord, countWordCap } from "./count-words";
import { eventObservedClipCount, observedImageryBlock } from "./observed-imagery";

/*
 * orbitLessons() lived here and has been replaced.
 *
 * It was ten .lesson-card blocks, each one paragraph followed by a .diagram
 * div that src/styles.css renders as a 180 px box of radial glow containing
 * three to five words. Sean, 2026-08-21: "There is no content in there
 * whatsoever. That is one of the most important parts of the site and it
 * deserves a really solid treatment."
 *
 * Learning track 01 is now six chapters in src/satellite-fundamentals.ts,
 * routed from main.ts the same way the layer pages are. All ten of the
 * original topics survive inside it, rewritten; CHAPTER_MAP in that file
 * records where each one went and a unit test asserts the map is complete.
 */

// ---------------------------------------------------------------------------
// LEARNING TRACK 02 — SPACE WEATHER
//
// The shape of this track, and why it is this shape.
//
// It used to be one page: a hero, eight cards labelled MODULE that were a
// paragraph and a 180 px glowing box containing five words of monospace, a
// callout, six videos, a seven-part long-form argument, and a methods essay —
// about fourteen thousand pixels of continuous scroll with no signposting and
// nothing a reader could open. Sean's verdict was that it was "some
// haphazardly constructed grouping of random text" with "no flow", and that
// the modules "don't go anywhere".
//
// He was right on both counts, and they are the same defect: a card labelled
// MODULE promises a lesson you can enter, and there was nothing to enter.
//
// So the track is now an INDEX and a set of PAGES:
//
//   weatherLessons()        the index. Hero, a contents spine that names every
//                           destination, the eight module cards, and three
//                           doors to the long-form pages.
//   weatherLessonView(id)   one module. Its clip if it has one, a short "why
//                           it happens" in named beats, a recipe that switches
//                           real layers on, and doors onward.
//   weatherPageView(id)     the three long-form pages: the Dungey cycle, the
//                           mechanism library, and how the picture is built.
//
// TWO RULES HOLD ACROSS ALL OF IT.
//
// 1. Say it once. The eight modules are the SPINE — one idea each, stated,
//    shown, and practised on the globe. The Dungey page and the methods page
//    are where a claim is DERIVED at length. A module that maps onto a Dungey
//    stage states its idea in a sentence and hands the reader a door; it does
//    not reprint the derivation. That is why the module bodies are short on
//    purpose.
//
// 2. Nothing is offered that does not exist. A module shows a clip entry only
//    where a clip has actually been rendered for it, and a "see it live" entry
//    only where a real layer draws the thing. Four of the eight have no clip
//    and one has no layer, and those pages say so rather than growing a dead
//    affordance. An empty globe is a scientific result; so is an absent link.
// ---------------------------------------------------------------------------

/** One named beat of an argument. Short by construction: the wall this track
 *  used to be was made of 200–400 word blocks with no internal structure. */
type Beat = { head: string; body: string };

/** A quantity worth pulling out of the prose and setting as a figure. */
type Fact = { label: string; value: string };

/** A control the reader can actually switch on, named exactly as index.html
 *  names it. `checkbox` is the real element id, so the button works. */
type LiveSwitch = { label: string; checkbox: string };

type WeatherModule = {
  id: string;
  index: string;
  title: string;
  /** The card paragraph. Unchanged from the original eight cards. */
  summary: string;
  /** The five-word mnemonic that used to be alone inside a 180 px glow box. */
  formula: string;
  status: MethodCard["status"];
  chip: string;
  /** id in MECHANISM_ANIMATIONS, where one has been rendered for this idea. */
  clip?: string;
  /** One sentence: the thing to carry away. Set larger than the body. */
  claim: string;
  /**
   * The closer. Two or three sentences restating the claim in the vocabulary
   * the page has just taught, ending on the operational habit.
   *
   * Every module used to end on navigation: the last thing a reader was told
   * was which button to press. The contract on this field is narrow, and is the
   * reason it is a field of its own rather than one more beat — it may not
   * introduce a claim, a number or a term, and it may not soften an evidence
   * class. A closer that teaches is a body section that arrived late.
   */
  close: string;
  /**
   * One sentence above the clip, where the clip's scope is wider than the
   * module's own.
   *
   * Module 01's clip opens on the skip zone and the F2 layer, which are module
   * 05's ground; directly under a claim about flares being light, its heading
   * read as a page break into a different lesson. This is the honesty the
   * evidence chips enforce, applied to scope instead of provenance.
   */
  clipFraming?: string;
  facts?: Fact[];
  why: Beat[];
  /** Rendered verbatim after the beats, for the one contrast that needs to be
   *  seen side by side rather than read in sequence. */
  contrast?: { title: string; left: { head: string; body: string }; right: { head: string; body: string }; close: string };
  live: {
    /** Said plainly when nothing on the globe draws this. */
    gap?: string;
    intro?: string;
    switches?: LiveSwitch[];
    steps?: { title: string; detail: string }[];
  };
  next: { label: string; page?: string; stage?: string; lesson?: string; view?: string }[];
};
export function weatherLessons(): string {
  return `
    <div id="weather-index">
      <header class="content-hero">
        <p class="eyebrow">LEARNING TRACK 02 · SPACE WEATHER</p>
        <h1>Follow energy from the Sun to a system effect.</h1>
        <p>&ldquo;Solar event&rdquo; is not one thing. Light, energetic particles, the ambient solar wind, and coronal mass ejections (CMEs) travel differently and produce different responses.</p>
      </header>
      ${trackMap()}
      <section class="track-section" id="weather-lessons" aria-labelledby="weather-lessons-title">
        <div class="method-section-head">
          <p class="section-kicker">PART ONE · THE EIGHT LESSONS</p>
          <h2 id="weather-lessons-title">Eight ideas, one each. Open any one.</h2>
          <p>They are in the order energy travels: light first, then particles, then the wind, then what the wind does when it arrives, then the layers it acts on, then the systems that fail, then the light you can see, then how to read the pictures. Each opens onto its own page with the animation, the reason, and the layer that shows it.</p>
        </div>
        <div class="lesson-grid">
          ${WEATHER_MODULES.map(moduleCard).join("")}
        </div>
      </section>
      <aside class="teaching-callout"><strong>Read the status label</strong>Evidence classes are ${evidenceNames}. A badge applies to its adjacent object; each number needs its own source and time. A beautiful picture is not automatically a measurement.</aside>
      <section class="track-section" id="weather-deeper" aria-labelledby="weather-deeper-title">
        <div class="method-section-head">
          <p class="section-kicker">PART TWO · THE LONG FORM</p>
          <h2 id="weather-deeper-title">Three pages that derive what the eight lessons assert.</h2>
          <p>The lessons state the ideas and put them on the globe. These are where the arguments are made in full: the one interaction the whole subject falls out of, the six mechanisms drawn frame by frame, and an account of how this picture is built and where it stops knowing things.</p>
        </div>
        <div class="door-grid">
          ${doorCard("dungey", "THE ARGUMENT", "The Dungey cycle, 1961", "One interaction &mdash; a supersonic magnetised plasma running into a planetary dipole &mdash; and the seven structures that follow from it, in the order the wind meets them. Ends with a recipe that assembles the whole cycle on the globe in front of you.", "7 stages &middot; ~15 min")}
          ${doorCard("mechanisms", "THE PICTURES", `${countWordCap(MECHANISM_ANIMATIONS.length)} things no camera has filmed`, "Short animations of the steps this subject is usually asserted in words: reconnection, the Chapman layer, the HF skip and blackout, trapped motion, the South Atlantic Anomaly, and orbital decay. Every one drawn from the geometry or formula named on the frame.", `${MECHANISM_ANIMATIONS.length} clips &middot; ${mechanismLibraryRuntime()}`)}
          ${doorCard("engine", "THE METHOD", "How this picture is built", "What is measured, what is fitted, and what is unknown: two real NOAA cuts, a semi-empirical field pinned to them every frame, a calibration that is allowed to refuse, and the compressed ruler every drawn radius shares.", "4 limits &middot; ~12 min")}
        </div>
      </section>
      <section class="track-section" id="weather-layers" aria-labelledby="weather-layers-title">
        <div class="method-section-head">
          <p class="section-kicker">PART THREE &middot; THE REFERENCE</p>
          <h2 id="weather-layers-title">Every layer this track names, on its own page.</h2>
          <p>The lessons and the long-form pages argue; this one describes. It is where a layer goes when you want to look it up on its own rather than follow it through a chain.</p>
        </div>
        <div class="door-grid door-grid--one">
          ${doorCard("learn-layers", "THE LAYERS", "The layers, one by one", `${countWordCap(LAYER_PAGE_COUNTS.total)} pages: ${countWord(LAYER_PAGE_COUNTS.layers)} space-weather layers, the two lines drawn around a satellite, and the chain that ties four of the layers into one event &mdash; what it is, why an operator cares, and how we know.`, `${LAYER_PAGE_COUNTS.total} pages`, `data-view="learn-layers"`)}
        </div>
      </section>
    </div>
    <div id="weather-page" hidden></div>
  `;
}

/**
 * The contents spine.
 *
 * This is the part the page had none of. A reader arriving could not tell what
 * was on it, how long it was, or where it ended — the only way to find out was
 * to scroll fourteen thousand pixels. Four rows, each naming a real
 * destination and each an actual target: the first scrolls to the grid, the
 * other three open their page.
 */
function trackMap(): string {
  const rows: { kicker: string; title: string; note: string; action: string }[] = [
    { kicker: "01", title: "Eight lessons", note: "One idea each, in the order energy travels. Clip, reason, and the layer that shows it.", action: `data-weather-scroll="weather-lessons"` },
    { kicker: "02", title: "The Dungey cycle", note: "The seven structures the solar wind meets, derived in order, with a recipe to plot them.", action: `data-weather-page="dungey"` },
    { kicker: "03", title: "Mechanism library", note: `${countWordCap(MECHANISM_ANIMATIONS.length)} short animations of steps no instrument returns as a picture.`, action: `data-weather-page="mechanisms"` },
    { kicker: "04", title: "How this picture is built", note: "What is measured, what is fitted, what is unknown &mdash; and the ruler that is not to scale.", action: `data-weather-page="engine"` },
    // The one row that leaves this view. `data-view` inside #weather-index is
    // routed by onWeatherTrackClick() through openContent(), which is how the
    // injected markup on this page reaches a sibling track at all.
    { kicker: "05", title: "The layers, one by one", note: `${countWordCap(LAYER_PAGE_COUNTS.total)} pages: ${countWord(LAYER_PAGE_COUNTS.layers)} space-weather layers, the two lines drawn around a satellite, and the chain that ties four of them into one event.`, action: `data-view="learn-layers"` },
  ];
  return `
    <nav class="track-map" aria-label="What is on this page">
      <p class="section-kicker">WHAT IS ON THIS PAGE</p>
      <ol>
        ${rows.map((row) => `<li><button type="button" ${row.action}><span class="track-map-index">${row.kicker}</span><span><strong>${row.title}</strong><small>${row.note}</small></span><span class="track-map-arrow" aria-hidden="true">&rarr;</span></button></li>`).join("")}
      </ol>
    </nav>
  `;
}

/**
 * One module card on the index.
 *
 * What is gone: `<div class="diagram">`, a 180 px box with a radial glow and a
 * border whose entire content was a five-word monospace caption. It was the
 * visual signature of a placeholder nobody filled, and it appeared eight times
 * on one page. The caption itself was the only content in it and is worth
 * keeping, so it survives as a one-line strapline under the title.
 *
 * What is new: the card says what is inside before you open it, and the whole
 * card is the target. The entry list is built from what the module ACTUALLY
 * has — no clip row where no clip has been rendered, no globe row where no
 * layer draws the thing.
 */
function moduleCard(module: WeatherModule): string {
  const clip = module.clip ? mechanismAnimation(module.clip) : undefined;
  const inside: string[] = [];
  if (clip) inside.push(`<li class="is-clip">Animation &middot; ${clip.runtime}</li>`);
  inside.push(`<li class="is-why">Why it happens &middot; ${module.why.length} steps</li>`);
  inside.push(module.live.gap
    ? `<li class="is-gap">Nothing on the globe draws this</li>`
    : `<li class="is-live">See it on the globe</li>`);
  return `<article class="lesson-card module-card">
    <span class="section-kicker">MODULE ${module.index}</span>
    <h2>${module.title}</h2>
    <p class="module-formula">${module.formula}</p>
    <p>${module.summary}</p>
    <ul class="module-inside">${inside.join("")}</ul>
    <button type="button" class="link-button module-open" data-weather-lesson="${module.id}">Open module ${module.index}<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
  </article>`;
}

/**
 * A door out of the index.
 *
 * `action` exists because one door leaves this view entirely. The three
 * long-form doors open a sibling inside the weather track and carry
 * `data-weather-page`; the layers door is a different track, so it carries
 * `data-view="learn-layers"` and onWeatherTrackClick() routes it through
 * openContent(). Same card, same grammar, different destination - which is the
 * point, because a reader should not have to learn a second shape to find the
 * layer pages now that they are no longer in the top nav.
 */
function doorCard(page: string, kicker: string, title: string, body: string, meta: string, action?: string): string {
  return `<article class="lesson-card door-card">
    <span class="section-kicker">${kicker}</span>
    <h2>${title}</h2>
    <p>${body}</p>
    <p class="door-meta">${meta}</p>
    <button type="button" class="link-button module-open" ${action ?? `data-weather-page="${page}"`}>Open this page<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
  </article>`;
}

/**
 * The eight lessons.
 *
 * `summary` and `formula` are the original card paragraph and the original
 * monospace caption, unchanged: they were never the problem. Everything after
 * them is the lesson that card had been promising and not delivering.
 *
 * The bodies are deliberately short. Where a module's idea is DERIVED at
 * length on the Dungey page or the methods page, the module states it and
 * hands over — printing the derivation twice is the duplication this redesign
 * exists to remove.
 */
const WEATHER_MODULES: WeatherModule[] = [
  {
    id: "photons",
    index: "01",
    title: "Photons arrive first",
    summary: "X-ray and extreme-ultraviolet (EUV) changes reach Earth in about eight minutes and rapidly alter ionization on the sunlit side. A flare is not the same object as a CME &mdash; a coronal mass ejection, an erupted cloud of solar plasma that arrives days later if it arrives at all. A flare is light, and it is already here.",
    formula: "Sun &rarr; light &rarr; ionosphere",
    status: "observed",
    chip: "GOES X-ray flux &middot; measured at geostationary orbit",
    clip: "hf-skip-blackout",
    claim: "A flare is light. It arrives in eight minutes, it acts on the sunlit hemisphere only, and what it changes is the bottom of the ionosphere.",
    close: "You now hold the whole event: a flare is light, so its radio effect is immediate, daylight-only, and finished within the hour &mdash; and nothing about it predicts the storm that may or may not follow in two days. When HF dies in daylight while UHF stands untouched, you can name the region that did it, the hemisphere it is confined to, and the clock it will recover on.",
    clipFraming: "This clip is a radio operator&rsquo;s view. Its first half &mdash; the hop off the F2 layer and the skip zone &mdash; belongs to module 05&rsquo;s ionosphere; watch it here for the second half, where the flare closes the band from the bottom.",
    facts: [
      { label: "Travel time", value: "8 min" },
      { label: "Absorbed in", value: "D region, 60&ndash;90 km" },
      { label: "Hemisphere", value: "Sunlit only" },
      { label: "Recovery", value: "Within the hour" },
    ],
    why: [
      {
        head: "It is absorbed at the bottom, not the top",
        body: "X-rays are absorbed high above the ground but low in the ionosphere &mdash; in the D region between 60 and 90 km, where they ionise the air and turn it from a mirror for shortwave radio into a sponge. That is a radio blackout on the sunlit hemisphere, and it is what the D-region HF absorption layer draws.",
      },
      {
        head: "Absorption is worst at the low end",
        body: "Absorption rises as one over frequency squared, so the usable window closes from the bottom upward. An operator watching a band plan sees the lowest frequencies go first and the highest survive longest &mdash; which is the opposite of the intuition that a stronger event takes everything at once.",
      },
      {
        head: "Half the Earth is untouched",
        body: "Only the sunlit half is affected. A path lying in darkness is unaffected, which is one way to tell a flare from a jammer. It ends when the flare ends: the D region recombines within the hour and the circuit comes back on its own.",
      },
    ],
    contrast: {
      title: "Billiard balls and waves: why a flare tells you nothing about the wind",
      left: {
        head: "Light",
        body: "X-rays are <em>light</em>. A flare&rsquo;s photons leave the Sun and arrive eight minutes later, in a straight line, because they carry no charge and the magnetic field therefore exerts no force on them at all. You detect them only where they are absorbed.",
      },
      right: {
        head: "Matter",
        body: "The solar wind is <em>matter</em>. It is plasma &mdash; protons, alpha particles (helium nuclei stripped of both electrons) and the electrons that keep it neutral &mdash; and it takes one to three days to cross the same distance. Nobody watches it coming: it is caught, at a single point, in situ, when the L1 monitor 1.5 million kilometres upwind runs into it, which at typical speeds is 30 to 60 minutes of warning.",
      },
      close: "The two correlate, because the same active regions produce both, and correlation is not inference. You cannot read the solar-wind speed off the X-ray flux. An X-class flare is a fact about your radios in the next hour and says nothing reliable about whether a geomagnetic storm arrives in two days. One is a wave you only detect where it is absorbed; the other is a stream of billiard balls you can catch and count one at a time.",
    },
    live: {
      intro: "The absorption is a real NOAA nowcast, not an illustration of one.",
      switches: [{ label: "D-region HF absorption", checkbox: "layer-drap" }],
      steps: [
        { title: "D-region HF absorption", detail: "NOAA D-RAP: the highest frequency expected to lose at least 1 dB on a vertical ground&ndash;ionosphere&ndash;ground path, on a global 2&deg; by 4&deg; field. Watch which side of the terminator it sits on." },
        // THE STEP THAT WAS MISSING, and the reason this page is named in the
        // D-region layer's own history. Sean reached the layer from here, on a
        // day the D region was quiet, and found a globe with nothing on it. The
        // two steps either side of this one both promise a spectacle -- watch
        // where it sits, drag across a flare -- and on most days there is no
        // spectacle to watch, because most days are quiet. Saying so here is
        // the difference between a reader learning what a quiet ionosphere
        // looks like and a reader concluding the site is broken.
        { title: "Most days it is nearly empty, and the layer says so", detail: "The D region is quiet far more often than not, and a quiet one absorbs almost nothing: the chip on the layer&rsquo;s card reads QUIET with the peak frequency beside it, and the line under the colour bar gives how much of the globe is drawn and how much of it is affected at 10 and 30 MHz. A bare globe under a QUIET chip is the reading. Only a struck-out colour bar means there is no data at all." },
        { title: "Drag the timeline across a flare", detail: "When the window holds one, the absorption appears and clears on the flare&rsquo;s own clock, minutes not days, and the chip changes to ACTIVE with a much higher peak. Periods with no published frame stay blank rather than holding the last one." },
      ],
    },
    next: [
      { label: "Module 03 &middot; the wind, and the switch it carries", lesson: "wind" },
      { label: "The clip in full, with its sources", page: "mechanisms" },
    ],
  },
  {
    id: "particles",
    index: "02",
    title: "Particles have energies",
    summary: "Energetic protons and electrons can arrive over tens of minutes to hours. Their effects depend on energy, direction, magnetic access, and spacecraft shielding.",
    formula: "SEP flux is not local dose",
    status: "observed",
    chip: "GOES &middot; one spacecraft, at geostationary orbit",
    claim: "The energetic-particle number on this site is one spacecraft&rsquo;s measurement at one place. Solar energetic particles &mdash; SEPs &mdash; do not have a map here, because nobody publishes one; the number is not the dose at your spacecraft.",
    close: "What you take away is a discipline: a proton flux at GOES is one instrument&rsquo;s number at one place, and dose at any other spacecraft needs spectrum, direction, shielding and a transport model this site does not hold. Distrust any display that turns that one number into a global picture &mdash; including, deliberately, this one, which is why the globe is empty here.",
    facts: [
      { label: "Measured at", value: "GOES, geostationary" },
      { label: "Channels", value: "Integral proton + electron" },
      { label: "Arrival spread", value: "Tens of min to hours" },
      { label: "Global map", value: "None published" },
    ],
    why: [
      {
        head: "Arrival is a spread, not an instant",
        body: "Energetic protons and electrons can arrive over tens of minutes to hours rather than at one moment, because they are matter with a range of energies and they follow the field they find. Their effects depend on energy, direction, magnetic access, and spacecraft shielding &mdash; four things, none of which is the flux number.",
      },
      {
        head: "What is actually measured",
        body: "NOAA GOES measures energetic-particle intensity at the observing geostationary spacecraft. Energy channel, flux, spacecraft, and observation time stay attached to the value. It is normalised into the verified weather bundle but does not alter the RBE model field or create a global particle shower &mdash; because one point cannot.",
      },
      {
        head: "Flux is not dose",
        body: "A local geostationary sample cannot establish flux at an arbitrary LEO, MEO or GEO spacecraft. Dose additionally requires spectra, directionality, shielding, material response, and a transport model. This site holds the first of those and none of the rest, so it reports the measurement and stops.",
      },
    ],
    live: {
      gap: "Nothing on the globe draws solar energetic particles, because no upstream this release reads publishes a gridded product for them. There is no shower, no map and no modelled flux volume, and none has been invented to fill the space. What exists is the measured number and the operational scale built from it, both on the Current conditions page.",
      steps: [
        { title: "Current conditions &rarr; S scale", detail: "NOAA&rsquo;s solar radiation storm scale and the S1-or-greater daily probability, formatted with no model in the path. That is the honest extent of what this site knows about energetic particles." },
        { title: "Radiation belts is a different population", detail: "Do not read the belts as this module. Trapped MeV electrons are a resident population inside the magnetosphere; solar energetic particles are an arriving one. Same word, different objects &mdash; module 06 separates the effects they cause." },
      ],
    },
    next: [
      { label: "Current conditions &middot; the measured scales", view: "now" },
      { label: "Module 06 &middot; what the particles actually break", lesson: "systems" },
    ],
  },
  {
    id: "wind",
    index: "03",
    title: "Solar wind carries magnetic field",
    summary: "Plasma measured near L1 carries the interplanetary magnetic field. Speed and density set dynamic pressure; southward Bz can favor magnetic reconnection.",
    formula: "L1 &rarr; tens of minutes &rarr; Earth",
    status: "observed",
    // CORRECTED 2026-09-04, correctness audit. This chip and the beat below
    // said "DSCOVR normally, ACE as the backup". Checked against the two files
    // this site actually reads — rtsw_wind_1m.json and rtsw_mag_1m.json — on
    // 2026-09-04: 2,666 wind records carrying ACE (1,150), SOLAR1 (868) and
    // IMAP (648), and ZERO from DSCOVR; SWPC nominated SOLAR1 active for 810
    // of those minutes and ACE for 266. The site's own methods card and the
    // solar-wind layer page already named SOLAR1, ACE and IMAP, so this track
    // was the only place still teaching the old roster. Written so the point
    // that survives a re-nomination — several monitors, one nominated active —
    // is the load-bearing part rather than a spacecraft name.
    chip: "SWPC&rsquo;s L1 monitors &middot; one point, 30&ndash;60 min upwind",
    clip: "dayside-reconnection",
    claim: "Everything downstream on this site is driven by two numbers and a vector, measured at a single point 1.5 million kilometres upwind.",
    close: "The wind is the carrier and the field it carries is the switch. One spacecraft an hour upwind supplies the two numbers and one vector that drive every layer downstream &mdash; so you now know exactly how much measurement sits underneath this whole picture: that much, and no more.",
    facts: [
      { label: "Where", value: "L1, ~1.5 M km sunward" },
      { label: "Warning", value: "30&ndash;60 min" },
      { label: "Measured", value: "n, V, B vector" },
      { label: "The watched number", value: "IMF Bz" },
    ],
    why: [
      {
        head: "What the monitor reports",
        body: "NOAA&rsquo;s real-time solar-wind feed carries every L1 monitor SWPC is receiving &mdash; SOLAR1, ACE and IMAP as this is written, with one of them nominated active &mdash; parked at the first Lagrange point, where the Sun&rsquo;s and Earth&rsquo;s gravity let a spacecraft hover on the Sun&ndash;Earth line. It reports proton number density in particles per cubic centimetre, bulk speed in kilometres per second, and the interplanetary magnetic field as a vector in nanotesla.",
      },
      {
        head: "Why southward Bz is the number everyone watches",
        body: "Bz is the north&ndash;south component of the interplanetary magnetic field &mdash; the IMF, the Sun&rsquo;s own field carried outward frozen in the wind &mdash; measured in nanotesla in a Sun-referenced frame called GSM. Negative means southward, and southward is the setting that matters. A southward interplanetary field can join Earth&rsquo;s northward field at the nose, and that join is what lets energy in. It does not make the wind stronger. It decides whether the cycle runs fast or idles &mdash; which is why an operator watches the sign of one component rather than the speed.",
      },
      {
        head: "One point is not the wind that arrives",
        body: "The solar wind is structured on scales smaller than the distance from L1 to Earth, and the field direction in particular can differ between the two. The arrival time is estimated from the measured speed rather than observed. That is the actual state of the art in operational space weather, not a shortfall of this site.",
      },
    ],
    live: {
      intro: "The amber shower is the measured wind, and the three colours are three species.",
      switches: [
        { label: "Solar wind &amp; IMF", checkbox: "layer-solar-wind" },
        { label: "Magnetosphere", checkbox: "layer-geospace" },
      ],
      steps: [
        { title: "Solar wind &amp; IMF", detail: "How many particles you can see is the measured proton density; how fast they arrive is the measured bulk speed; the three colours are protons, alpha particles and electrons. One number in that mix is assumed rather than measured, and the methods page names it." },
        { title: "Add the magnetosphere", detail: "With the field layer on, a fraction of the arriving particles is guided along the traced field lines &mdash; down the dayside lines into the cusps, the two funnels over the poles where the field lets particles in and module 07 shows where they land, or tailward over the poles. Which particles enter is a geometric selection; their motion along the line is illustrative." },
      ],
    },
    next: [
      { label: "The Dungey cycle &middot; what the wind runs into", page: "dungey" },
      { label: "Why one upstream sample carries the whole picture&rsquo;s uncertainty", page: "engine" },
    ],
  },
  {
    id: "compression",
    index: "04",
    title: "The dayside usually compresses",
    summary: "Higher solar-wind pressure generally pushes the dayside magnetopause inward. The tail, ring current, plasmasphere, and radiation belts each respond in their own way.",
    formula: "pressure &uarr; &rarr; dayside standoff &darr;",
    status: "empirical",
    chip: "Arithmetic from two measured numbers",
    claim: "The boundary sits where the wind&rsquo;s push equals the field&rsquo;s push, so its distance can be calculated from upstream numbers rather than observed &mdash; and quoted in Earth radii, R&#8853;, about 6,400 km each.",
    close: "One cause, five responses, five clocks &mdash; that is the sentence to keep. The dayside boundary answers in minutes and can be pushed inside geostationary orbit in a severe event; everything else answers on its own delay. A storm is not a moment, it is a sequence, and you now know the order.",
    facts: [
      // CORRECTED 2026-09-04, correctness audit. This row read "Quiet standoff
      // ~13.5 R⊕". 13.5 is not the quiet standoff: it is the MAXIMUM in the
      // site's own driver history (radial-ruler.ts — 1,087 published samples over
      // three days, minimum 7.352 R⊕, median 9.51, maximum 13.52), and it is
      // FURTHER OUT than the ~13 R⊕ bow shock Dungey stage 01 quotes on this same
      // track, which would put the magnetopause outside its own bow shock. The
      // site's own quiet-frame check puts the modelled current layer at 10.25 R⊕
      // against Shue's 10.61 (methods.ts, connections.ts, layer-pages.ts), and
      // Dungey stage 03 already reads "Typical nose 10–11 R⊕" with 13.5
      // reserved for "very quiet". The module now agrees with the stage it
      // hands the reader on to.
      { label: "Typical nose", value: "~10&ndash;11 R&#8853; (Earth radii)" },
      { label: "Storm standoff", value: "~7 R&#8853;" },
      { label: "Geostationary orbit", value: "6.6 R&#8853;" },
      { label: "Inputs", value: "n and V, from L1" },
    ],
    why: [
      {
        head: "Two pushes, one balance",
        body: "Outside, the wind pushes with its dynamic pressure, which goes as density times speed squared. Inside, Earth&rsquo;s field pushes back with magnetic pressure, which rises steeply as you move inward. The boundary is wherever the two are equal, which is why raising the pressure moves it in rather than making it stronger.",
      },
      {
        head: "Not everything responds the same way",
        body: "The dayside compresses first and fastest because it faces the push. The tail loads over the better part of an hour, the ring current builds over hours, the plasmasphere is eroded on its own clock, and the belts can take a day. One cause, five effects, five different response times &mdash; which is what the timeline is for.",
      },
      {
        head: "Why this matters at 6.6 Earth radii",
        body: "In a severe event the boundary can be pushed below geostationary orbit. A spacecraft that normally sits inside the magnetosphere then finds itself outside it, in shocked solar wind, with the charging and surface-potential environment that implies.",
      },
    ],
    live: {
      intro: "The standoff is printed as a live number, and three published fits are drawn over it so you can see them agree or disagree.",
      switches: [
        { label: "Magnetosphere", checkbox: "layer-geospace" },
      ],
      steps: [
        { title: "Magnetosphere", detail: "Its card reports the live STANDOFF in Earth radii. Press the meridional cross-section camera button (⊘) for the textbook cut, Sun on the left." },
        { title: "Annotation: empirical boundary models", detail: "In that layer&rsquo;s own settings, behind the caret beside its toggle. Shue (1998), Nguyen (2022) and Lin (2010) recomputed from the live wind. Where they agree with the model field the arithmetic is holding; where they disagree, that is the lesson." },
        { title: "Drag the timeline back across 48 hours", detail: "Pressure rises, and the boundary and shock move earthward together. This is the step that makes it one system instead of six pictures." },
      ],
    },
    next: [
      { label: "Stage 03 &middot; the magnetopause, derived", page: "dungey", stage: "03" },
      { label: "How the boundary is fitted to NOAA&rsquo;s own curve, every frame", page: "engine" },
    ],
  },
  {
    id: "layers",
    index: "05",
    title: "Ionosphere and thermosphere overlap",
    summary: "D, E, and F are variable ionization regions inside a neutral atmosphere. TEC measures electrons integrated through a column; it cannot locate all three layers vertically.",
    formula: "plasma structure + neutral atmosphere",
    // CORRECTED 2026-09-04, correctness audit. Badged "assimilated" while the
    // chip beside it reads "WAM-IPE model · GloTEC assimilated · two different
    // claims" and the whole module exists to teach that those are different
    // kinds of claim. A single badge asserting the stronger of the two is the
    // exact habit this track tells the reader to distrust. "composite" is the
    // class this file already defines for a mixed card and already uses on
    // modules 06 and 08.
    status: "composite",
    chip: "WAM-IPE model &middot; GloTEC assimilated &middot; two different claims",
    clip: "chapman-layer",
    claim: "The same volume of air is two things at once: a weak plasma that bends radio, and a neutral gas that produces drag. They are measured differently and they fail differently.",
    close: "The same air is two things at once: a plasma that bends and delays radio, and a neutral gas that drags spacecraft. They are measured by different products, they fail on different clocks, and no single number &mdash; least of all a column total &mdash; describes both. That is why this globe draws them as separate layers, and why you read the badge before the picture.",
    facts: [
      { label: "D region", value: "60&ndash;90 km" },
      { label: "E region", value: "~110 km" },
      { label: "F2 peak", value: "~300 km" },
      { label: "TEC", value: "One column number" },
    ],
    why: [
      {
        head: "Why there is a peak at all",
        body: "Ionising light is strongest at the top and is used up on the way down; the air thickens downward. Their product has to peak somewhere in between, and that peak is a Chapman layer. The same argument explains why the peak climbs and weakens as the Sun goes down, and why D and E collapse after dark while F2 does not.",
      },
      {
        head: "Charged and neutral do different damage",
        body: "The charged part drives radio and charging effects: group delay, refraction, Faraday rotation &mdash; the plasma slowly twisting a signal&rsquo;s polarisation &mdash; and scintillation, the rapid flicker in amplitude and phase that plasma irregularities put on a ray. Track 01&rsquo;s spectrum chapter carries the radio side of both. The neutral part produces almost all of the aerodynamic drag. Solar EUV and geomagnetic heating expand the neutral atmosphere upward, which is why a storm can double the density a spacecraft is flying through within hours.",
      },
      {
        head: "A column number cannot locate a layer",
        body: "TEC is electrons integrated through a whole column, so it is one number per ground point with no height information in it. It cannot tell you whether the electrons are in E or in F2, and two very different profiles can produce the same TEC. That is why this site draws the peak surfaces and the column map as separate layers rather than one.",
      },
    ],
    live: {
      intro: "Three layers, three different kinds of claim &mdash; switch them on together and read the badges.",
      switches: [
        { label: "Ionosphere &mdash; electron density", checkbox: "layer-ionosphere" },
        { label: "TEC surface", checkbox: "layer-tec" },
        { label: "Thermosphere height", checkbox: "layer-thermosphere" },
      ],
      steps: [
        { title: "Ionosphere &mdash; electron density", detail: "NOAA WAM-IPE, a genuine three-dimensional model, with the empirical D region beneath it. This one has height in it." },
        { title: "TEC surface", detail: "NOAA GloTEC, assimilated &mdash; observations combined with a numerical background. One integrated number per column, and no height at all." },
        { title: "Thermosphere height", detail: "The neutral density that produces the drag. Same volume of air as the first two, different physics, different consequence." },
      ],
    },
    next: [
      { label: "Module 06 &middot; the systems these two break", lesson: "systems" },
      { label: "Drag makes a spacecraft go faster &mdash; the clip", page: "mechanisms" },
    ],
  },
  {
    id: "systems",
    index: "06",
    title: "Different systems fail differently",
    summary: "HF absorption, satellite-navigation (GNSS) error, satellite charging, single-event effects, drag, aurora, and ground-induced currents come from different parts of the chain.",
    formula: "phenomenon &rarr; environment &rarr; effect",
    status: "composite",
    chip: "Seven effects &middot; seven different causes",
    clip: "eccentric-dipole-saa",
    claim: "There is no such thing as &ldquo;a space weather effect&rdquo;. Each failure has its own cause, its own timescale and its own warning &mdash; and a fix for one is not a fix for another.",
    close: "&ldquo;Space weather effect&rdquo; is not a diagnosis. You can now trace each failure to its messenger &mdash; photons, particles, plasma, or a changing field at the ground &mdash; and each messenger to its own warning time. That is what turns a list of anomalies into a schedule of responses, and it is why the fix for one failure is never the fix for another.",
    facts: [
      { label: "HF blackout", value: "Photons, 8 min" },
      { label: "Single-event upsets", value: "Energetic particles" },
      { label: "Drag error", value: "Neutral density" },
      { label: "Ground currents", value: "Rate of field change" },
    ],
    why: [
      {
        head: "Trace the effect back before you act on it",
        body: "An HF blackout comes from photons in the D region and ends within the hour. A GNSS range error comes from electron content along the ray. Charging and single-event upsets &mdash; a single particle strike flipping a bit or latching a circuit &mdash; come from particles of different energies reaching different depths. Drag comes from the neutral atmosphere. Ground-induced currents come from how fast the field at the surface is changing, not from how strong it is.",
      },
      {
        head: "Geometry decides who gets hit",
        // CORRECTED 2026-09-04, mechanism-clip audit. This read "a surface of
        // equal field strength is a SPHERE around the dipole". A dipole's field
        // at fixed distance is twice as strong over the poles as over the
        // equator, so an iso-B surface is not spherical for any dipole -- that is
        // the wrong geometry, not a simplification of it, on the page whose
        // subject is that the SAA is geometry. What the sentence actually needs
        // is that the surface is centred on the OFFSET dipole rather than the
        // planet, which is what makes one arc of the orbit sit above it. Clip 05
        // carried the same claim in its burned-in caption and was re-rendered.
        body: "The best-fit dipole sits about 610 km from Earth&rsquo;s centre, so a surface of equal field strength rides off centre with the dipole rather than sitting around the planet &mdash; roughly 1&#8239;520 km up on one side and 300 km up on the other. There is no hole in the shielding over Brazil; there is an offset, and the South Atlantic Anomaly is where that offset shows.",
      },
      {
        head: "Which is why an operator schedules around it",
        body: "That region is where a spacecraft collects most of its single-event upsets. Instruments are safed going in and switched back on coming out, so the pass is a scheduled event rather than a surprise. The offset is not fixed either: the anomaly creeps west and deepens from decade to decade, so a mission planned against an old field model is planned against the wrong place.",
      },
    ],
    live: {
      intro: "Four causes, four layers. Switch them on one at a time and watch which parts of the globe each one touches.",
      switches: [
        { label: "D-region HF absorption", checkbox: "layer-drap" },
        { label: "TEC surface", checkbox: "layer-tec" },
        { label: "Radiation belts", checkbox: "layer-radiation" },
        { label: "Ground magnetic perturbation", checkbox: "layer-groundField" },
      ],
      steps: [
        { title: "D-region HF absorption, then TEC surface", detail: "Two radio effects with different causes, different altitudes and different timescales. They do not switch on together and they do not clear together." },
        { title: "Radiation belts", detail: "The trapped MeV electrons that punch through shielding, charge dielectrics and flip bits. Step the energy control: at 1.35 MeV the slot between the belts is unmistakable." },
        { title: "Ground magnetic perturbation", detail: "NOAA SWMF surface d<i>B</i> &mdash; the quantity behind ground-induced currents, and the only one of these four that a power utility rather than a satellite operator cares about." },
      ],
    },
    next: [
      { label: "Module 02 &middot; why flux is not dose", lesson: "particles" },
      { label: "Stage 07 &middot; the belts, derived", page: "dungey", stage: "07" },
    ],
  },
  {
    id: "aurora",
    index: "07",
    title: "Aurora maps particle precipitation",
    summary: "Auroral ovals organize around magnetic rather than geographic poles. NOAA OVATION uses upstream solar-wind and IMF inputs to model precipitating particles and estimate short-term viewing probability; local darkness and cloud still decide whether a person can see it.",
    formula: "solar wind &rarr; precipitation &rarr; auroral oval",
    status: "forecast",
    chip: "NOAA OVATION &middot; a forecast of precipitation, not of a view",
    claim: "The aurora is a map of where charged particles are landing. It is drawn around the magnetic pole, not the geographic one, and the forecast is of precipitation rather than of whether you will see anything.",
    close: "The aurora is a map: where charged particles are landing, drawn around the magnetic pole because the field lines converge there, not at the geographic one. The forecast under it is a forecast of precipitation, not of a view &mdash; darkness, clear sky and a horizon are yours to supply.",
    facts: [
      { label: "Emission height", value: "100&ndash;300 km" },
      { label: "Oxygen green", value: "557.7 nm" },
      { label: "Oxygen red", value: "630.0 nm" },
      { label: "Organised around", value: "The magnetic pole" },
    ],
    why: [
      {
        head: "Particles arrive where field lines lead",
        body: "A charged particle crosses magnetic field lines only with difficulty but travels along them freely. So precipitation is not spread evenly: it lands where the field lines that reach out into the system come back down, which is a ring around each magnetic pole rather than a cap on each geographic one.",
      },
      {
        head: "The light is a discharge lamp",
        body: "At 100 to 300 km the particles collide with atomic oxygen and molecular nitrogen and kick their electrons into excited states; the light is those electrons dropping back. Green at 557.7 nm from atomic oxygen, red at 630.0 nm from oxygen higher up where collisions are rare enough to let the slow transition finish.",
      },
      {
        head: "A forecast of particles is not a forecast of a view",
        body: "OVATION takes upstream solar-wind and IMF inputs and models precipitating particles. Whether a person sees anything additionally needs local darkness, clear sky and a horizon &mdash; none of which this or any precipitation model contains. A high oval probability over an overcast afternoon is still a correct forecast and still nothing to look at.",
      },
    ],
    live: {
      intro: "The oval is a real NOAA forecast product on its own clock; the funnels that feed it belong to a different layer and a different evidence class.",
      switches: [
        { label: "Auroral oval", checkbox: "layer-aurora" },
        { label: "Magnetosphere", checkbox: "layer-geospace" },
        { label: "Annotation: polar cusps", checkbox: "annotate-polar-cusps" },
      ],
      steps: [
        { title: "Auroral oval", detail: "NOAA OVATION. Press the polar camera button (&#8857;) to look straight down at it &mdash; the only view in which the whole ring is in one frame." },
        { title: "Add the magnetosphere", detail: "Then tick <em>Annotation: polar cusps</em> in that layer&rsquo;s own settings &mdash; the funnels are off until you ask for them. The two amber funnels are the model&rsquo;s own cusps, found by searching the summed field for its dayside minima rather than drawn where one ought to be. The far end of that funnel is the oval you just switched on." },
        { title: "Watch a period with no published frame", detail: "The layer disappears and says why. NOAA distributes only the latest native numeric grid, so a selected time outside real coverage produces nothing rather than a frozen or invented oval." },
      ],
    },
    next: [
      { label: "Stage 05 &middot; cusps and aurora, derived", page: "dungey", stage: "05" },
      { label: "Module 03 &middot; the wind that drives the forecast", lesson: "wind" },
    ],
  },
  {
    id: "dimensions",
    index: "08",
    title: "One picture can contain different dimensions",
    summary: "WAM-IPE provides a three-dimensional ionospheric model, GloTEC provides a column-integrated TEC map, D-RAP provides a two-dimensional HF-absorption nowcast, and the live SWMF feed provides two intersecting magnetosphere cuts. Their timestamps, dimensions, and meanings do not become identical when they share one globe.",
    formula: "dimension + valid time + status",
    status: "composite",
    chip: "Four products &middot; four dimensions &middot; four clocks",
    claim: "Sharing a globe does not make two products comparable. Read the dimension, the valid time and the evidence badge before reading the picture.",
    close: "Read the badge, the valid time and the dimension before the picture &mdash; in that order. Two products on one globe are two claims, not one; and the layer that vanishes when its feed runs out is the one to trust, because it is telling you when it stopped knowing.",
    facts: [
      { label: "WAM-IPE", value: "3-D model" },
      { label: "GloTEC", value: "Column, assimilated" },
      { label: "D-RAP", value: "2-D nowcast" },
      { label: "SWMF", value: "Two 2-D cuts" },
    ],
    why: [
      {
        head: "Four different kinds of object",
        body: "WAM-IPE is a genuine three-dimensional ionospheric model. GloTEC is a column-integrated map with no height in it. D-RAP is a two-dimensional absorption nowcast. The live SWMF feed is two intersecting cuts through a three-dimensional simulation. Drawing them in one scene is useful; treating them as one measurement is not.",
      },
      {
        head: "Four different clocks",
        body: "They publish on their own cadences and carry their own valid times, and this site never blends two products into a single false timestamp. Where a product has no frame for the selected time, its layer disappears and says so rather than holding the last one, because a frozen field is indistinguishable by eye from a current one.",
      },
      {
        head: "The badge is the fastest thing to read",
        body: "Observed, assimilated, model, forecast, schematic, empirical, composite. That word is on every layer, every card and every figure, and it tells you what kind of claim you are looking at before you have read a single number. It is the one habit this whole track is trying to build.",
      },
    ],
    live: {
      intro: "Put two different kinds of claim in the same frame on purpose, and read their badges against each other.",
      switches: [
        { label: "TEC surface", checkbox: "layer-tec" },
        { label: "Ionosphere &mdash; electron density", checkbox: "layer-ionosphere" },
      ],
      steps: [
        { title: "TEC surface and Ionosphere together", detail: "One is assimilated and flat; the other is a model and has height. Open the space weather layers panel and compare their two valid times &mdash; they are rarely the same instant." },
        { title: "Move the timeline to a gap", detail: "Whichever product runs out first vanishes and states why. That is the behaviour to trust: a layer that never disappears is a layer that is not telling you when it stopped knowing." },
      ],
    },
    next: [
      { label: "How this picture is built, and what it cannot know", page: "engine" },
      { label: "Data &amp; methods &middot; every layer, one card each", view: "sources" },
    ],
  },
];

/** Every module id, so `main.ts` can bind without importing the data. */
export const WEATHER_MODULE_IDS: readonly string[] = WEATHER_MODULES.map((m) => m.id);

/** The layer checkbox behind every "switch it on" button on this track. */
export const WEATHER_LIVE_SWITCHES: readonly string[] = [
  ...new Set(WEATHER_MODULES.flatMap((m) => (m.live.switches ?? []).map((s) => s.checkbox))),
];

/**
 * One module, as its own page.
 *
 * The order is fixed and is the point: what to carry away, the numbers, the
 * picture, the reason, the thing to go and do, and where to go next. A reader
 * who stops after the claim has still learned the module.
 */
export function weatherLessonView(id: string): string {
  const module = WEATHER_MODULES.find((m) => m.id === id);
  if (!module) return weatherLessons();
  const clip = module.clip ? mechanismAnimation(module.clip) : undefined;
  return `
    <button type="button" class="link-button layer-page-back" data-weather-index>&larr; All eight lessons</button>
    <header class="content-hero layer-page-hero lesson-page-hero">
      <p class="eyebrow">MODULE ${module.index} &middot; LEARNING TRACK 02</p>
      <h1>${module.title}</h1>
      <p>${module.summary}</p>
    </header>
    <section class="lesson-claim" aria-label="The point of this module">
      ${evidenceBadge(module.status)}<span class="layer-status-note">${module.chip}</span>
      <p>${module.claim}</p><div class="method-citation">Claim scope: ${module.chip}. Sources: ${sourceLinks(WEATHER_SOURCES[module.id] ?? [], true)}</div>
      ${module.facts ? `<div class="fact-grid">${module.facts.map((f, index) => `<div><span>${f.label}</span><strong class="is-readout">${f.value}</strong>${weatherFactProvenance(module.id, index)}</div>`).join("")}</div>` : ""}
    </section>
    ${evidenceGuide()}
    ${weatherLearningFigure(module.id)}
    ${clip ? `<section class="lesson-block" aria-labelledby="lesson-clip-title">
      <p class="section-kicker">WATCH IT &middot; ${clip.runtime} &middot; SCHEMATIC</p>
      <h2 id="lesson-clip-title">${clip.question}</h2>
      ${module.clipFraming ? `<p class="lesson-clip-framing">${module.clipFraming}</p>` : ""}
      ${mechanismFigure(clip.id)}
    </section>` : ""}
    <section class="lesson-block" aria-labelledby="lesson-why-title">
      <p class="section-kicker">WHY IT HAPPENS</p>
      <h2 id="lesson-why-title">The reason, in ${module.why.length} steps.</h2>
      <div class="beat-list">
        ${module.why.map((beat, i) => `<section class="beat"><p class="beat-index" aria-hidden="true">${String(i + 1).padStart(2, "0")}</p><div><h3>${beat.head}</h3><p>${beat.body}</p><div class="method-citation">Related sources: ${sourceLinks(WEATHER_SOURCES[module.id] ?? [], true)}</div></div></section>`).join("")}
      </div>
      ${module.contrast ? contrastBlock(module.contrast) : ""}
    </section>
    ${learningSources(WEATHER_SOURCES[module.id] ?? [])}
    ${liveBlock(module)}
    <section class="lesson-block lesson-close" aria-label="What you now know">
      <p class="section-kicker">WHAT YOU NOW KNOW</p>
      <p>${module.close}</p>
    </section>
    <section class="lesson-block lesson-next" aria-labelledby="lesson-next-title">
      <p class="section-kicker">WHERE THIS GOES NEXT</p>
      <h2 id="lesson-next-title">Carry on.</h2>
      <div class="next-grid">
        ${module.next.map(nextLink).join("")}
        <button type="button" class="link-button" data-weather-index>All eight lessons<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
      </div>
    </section>
  `;
}

/**
 * The one contrast on this track that has to be SEEN rather than read.
 *
 * It was a single 250-word `.teaching-callout` at full body width — about 145
 * characters to the line — filed under the Dungey cycle, which is not what it
 * is about. It is about light versus matter, so it belongs to module 01, and
 * two things being contrasted belong in two columns.
 */
function contrastBlock(c: NonNullable<WeatherModule["contrast"]>): string {
  return `
    <aside class="contrast-pair">
      <p class="contrast-title">${c.title}</p>
      <div class="contrast-columns">
        <div><p class="contrast-head">${c.left.head}</p><p>${c.left.body}</p></div>
        <div><p class="contrast-head">${c.right.head}</p><p>${c.right.body}</p></div>
      </div>
      <p class="contrast-close">${c.close}</p>
    </aside>
  `;
}

/**
 * "See it on this site", including the case where the honest answer is that
 * nothing does. A module with no layer gets a stated gap, not a dead button.
 */
function liveBlock(module: WeatherModule): string {
  const { gap, intro, switches, steps } = module.live;
  return `
    <section class="lesson-block processing-ledger" aria-labelledby="lesson-live-title">
      <div>
        <p class="section-kicker">${gap ? "WHAT THE GLOBE CAN AND CANNOT SHOW" : "SEE IT ON THIS SITE"}</p>
        <h2 id="lesson-live-title">${gap ? "Nothing here draws this." : "Go and switch it on."}</h2>
      </div>
      ${gap ? `<p class="lesson-gap">${gap}</p>` : `<p>${intro ?? ""}</p>`}
      ${switches?.length ? `<div class="live-switches">${switches.map((s) => `<button type="button" class="link-button live-switch" data-open-layer="${s.checkbox}">Switch on <em>${s.label}</em><span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>`).join("")}</div>` : ""}
      ${steps?.length ? `<ol class="recipe-steps">${steps.map((s) => recipeStep(s.title, s.detail)).join("")}</ol>` : ""}
    </section>
  `;
}

function nextLink(link: WeatherModule["next"][number]): string {
  const attr = link.lesson ? `data-weather-lesson="${link.lesson}"`
    : link.page ? `data-weather-page="${link.page}"${link.stage ? ` data-weather-stage="${link.stage}"` : ""}`
    : `data-view="${link.view}"`;
  return `<button type="button" class="link-button" ${attr}>${link.label}<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>`;
}

/**
 * The three long-form pages.
 *
 * They were all three stacked below the eight cards on one scroll. Sean:
 * "there is a MOUNTAIN of text after it. That looks just god awful." They are
 * the same text; what has changed is that each is now somewhere a reader
 * chooses to go, arrives at the top of, and can finish.
 */
export function weatherPageView(id: string): string {
  if (id === "dungey") return withLearningContents(dungeyCyclePage() + learningCheck(id) + learningSources(WEATHER_SOURCES.dungey!), "weather-dungey");
  if (id === "mechanisms") return withLearningContents(mechanismLibraryPage() + learningSources(WEATHER_SOURCES.mechanisms!), "weather-mechanisms");
  if (id === "engine") return withLearningContents(physicsEnginePage() + learningCheck(id) + learningSources(WEATHER_SOURCES.engine!), "weather-engine");
  return weatherLessons();
}

function pageBack(): string {
  return `<button type="button" class="link-button layer-page-back" data-weather-index>&larr; Learn space weather</button>`;
}

/**
 * How many of the library's clips are also embedded somewhere in this track.
 *
 * COUNTED, not written down, since 2026-09-04. The hero below used to read
 * "Six things ... Six steps ... Five also sit inside" as three hard-coded
 * words, while the door card on the index computed its own count from
 * MECHANISM_ANIMATIONS.length. Both numbers happen to be right today. The door
 * card carries a comment recording that its runtime went stale for a whole
 * re-render once it was typed rather than computed, and a count a reader can
 * check by scrolling is exactly the kind that must not be typed twice.
 *
 * "the lesson or the stage they belong to" is also a correction: one of the
 * five, trapped-motion, sits inside Dungey stage 06 rather than inside any of
 * the eight modules, so "the lesson they belong to" was not where a reader
 * would find it.
 */
function embeddedMechanismCount(): number {
  const embedded = new Set<string>();
  for (const module of WEATHER_MODULES) if (module.clip) embedded.add(module.clip);
  for (const stage of DUNGEY_STAGES) if (stage.clip) embedded.add(stage.clip);
  return embedded.size;
}

function mechanismLibraryPage(): string {
  const total = MECHANISM_ANIMATIONS.length;
  const embedded = embeddedMechanismCount();
  return `
    ${pageBack()}
    <header class="content-hero layer-page-hero">
      <p class="eyebrow">LEARNING TRACK 02 &middot; THE PICTURES</p>
      <h1>${countWordCap(total)} things no camera has filmed.</h1>
      <p>${countWordCap(total)} steps in this subject are usually asserted in words, because no instrument returns them as a picture &mdash; there is nothing to photograph. Each one is drawn here instead, from the same physics the rest of the site is built on. ${countWordCap(embedded)} also sit inside the lesson or the stage they belong to; this is all ${countWord(total)} in one place.</p>
    </header>
    ${mechanismLibrarySection()}
  `;
}

// ---------------------------------------------------------------------------
// THE DUNGEY CYCLE — its own page since 2026-08-21.
//
// It used to be the fifth thing on a single fourteen-thousand-pixel scroll,
// reached only by scrolling past eight summary cards and six videos, and its
// seven stage cards carried 200–400 word blocks of unbroken prose at 11 px
// across a half-width card — about 88 characters to the line. The writing is
// good. The FORM was the defect, so nothing here has been cut: every sentence
// that was in those blocks is still in one of them.
//
// What changed is the grammar of a stage card:
//
//   claim      one sentence, set large. A reader who stops here has the stage.
//   facts      the quantities pulled out of the prose and set as figures.
//   equation   set as an equation instead of buried mid-sentence.
//   why        the derivation, in named beats of ~60 words.
//   see        the recipe, kept structurally separate from the derivation
//              rather than being a second paragraph of the same colour.
//
// And the grid is one column wide on this page, so the measure is about 66
// characters instead of 88.
// ---------------------------------------------------------------------------

type StageCard = {
  status: MethodCard["status"];
  chip: string;
  index: string;
  title: string;
  summary: string;
  /** One sentence. The thing to carry away if you read nothing else. */
  claim: string;
  facts?: Fact[];
  equation?: { math: string; note: string };
  /** Why the structure has to be there. */
  why: Beat[];
  /** Where it appears on this globe, and what is honestly missing. */
  see: Beat[];
  /** Both halves are labelled, and a limitation card labels them differently. */
  whyKicker?: string;
  seeKicker?: string;
  /** The clip that draws this stage, where one exists. */
  clip?: string;
};

/**
 * The chain from arriving wind to trapped particle, one card per structure.
 * The chip on each card is the evidence class of what THIS SITE can show for
 * it, not of the physics — the physics is settled, the picture is not.
 */
const DUNGEY_STAGES: StageCard[] = [
  {
    status: "model",
    chip: "Model field · the jump is the shock",
    index: "01",
    title: "Bow shock",
    summary: "The first thing the solar wind meets: a standing shock roughly 13 Earth radii sunward of Earth, where the flow abruptly slows, heats and compresses.",
    claim: "The wind outruns its own warning, so it cannot turn gradually. It turns in a layer a few hundred kilometres thick, and what comes out the other side is a different plasma.",
    facts: [
      { label: "Standoff", value: "~13 R&#8853;" },
      { label: "Thickness", value: "A few hundred km" },
      { label: "Downstream", value: "Slower, denser, hotter" },
    ],
    why: [
      {
        head: "Nothing can warn the plasma ahead",
        body: "The solar wind moves faster than any wave that could warn the plasma ahead of the obstacle, so a shock forms — the same reason a supersonic jet has one. In ordinary air that warning travels as sound; in a magnetised plasma it travels as the magnetosonic wave, and the wind outruns it.",
      },
      {
        head: "So the turn is abrupt",
        body: "The flow therefore cannot be turned aside gradually. It is turned abruptly, in a layer a few hundred kilometres thick, and everything downstream of that layer is a different plasma: slower, denser, hotter, and more strongly magnetised than the wind that arrived.",
      },
    ],
    see: [
      {
        head: "Where to find it",
        body: "Switch on <em>Magnetosphere</em>, open its settings with the caret beside the toggle, and tick <em>NOAA MHD cross-section</em>. Colour the plasma field by Speed or Density. The shock is the place where the colours jump.",
      },
      {
        head: "Nobody drew it",
        body: "Nothing draws it — it is a discontinuity in a quantity, which is what a shock is. The model resolves it as a steep ramp about half an Earth radius wide, because that is its grid, not because the real shock is that thick.",
      },
    ],
  },
  {
    status: "model",
    chip: "Model field · a region, not a line",
    index: "02",
    title: "Magnetosheath",
    summary: "The shocked wind: the band of compressed, heated, deflected plasma flowing around Earth between the bow shock and the magnetopause.",
    claim: "The sheath is a region with a real thickness, not a surface — and when a pressure pulse arrives, both of its walls move earthward together and the band narrows with them.",
    why: [
      {
        head: "The flow has to go somewhere",
        body: "Having been slowed below the wave speed at the shock, the flow can now be steered — and it has to go somewhere. It cannot go through the magnetopause, so it goes around, the way water goes around a bridge pier.",
      },
      {
        head: "Its thickness is a real quantity",
        body: "The sheath is not a surface and never was; it is a region with a thickness, and its thickness is a real quantity. When a pressure pulse arrives, both of its walls move earthward together and the band between them narrows with them.",
      },
    ],
    see: [
      {
        head: "The band between the two jumps",
        body: "It is the band of hotter colours between the two jumps in the same NOAA MHD cross-section — the reason the cut is worth looking at at all. Textbook figures draw the sheath as a shaded band because that is exactly what a cross-section through a simulation looks like; this is that cross-section, from NOAA's operational run, not an artist's version of it.",
      },
    ],
  },
  {
    status: "empirical",
    chip: "Arithmetic from two measured numbers",
    index: "03",
    title: "Magnetopause",
    summary: "The boundary itself: the surface where Earth's magnetic field is strong enough to stop the shocked solar wind, typically 10–11 Earth radii out at the nose.",
    claim: "Its distance can be <strong>calculated</strong> from two numbers a spacecraft an hour upstream is already measuring, because it is nothing more than a pressure balance.",
    facts: [
      { label: "Typical nose", value: "10&ndash;11 R&#8853;" },
      { label: "Very quiet", value: "~13.5 R&#8853;" },
      { label: "Storm", value: "~7 R&#8853;" },
      { label: "Geostationary", value: "6.6 R&#8853;" },
    ],
    equation: {
      math: "P<sub>dyn</sub> = 1.6726&times;10<sup>&minus;6</sup> <em>n</em> V<sup>2</sup> nPa &nbsp;=&nbsp; B<sup>2</sup> / 2&mu;<sub>0</sub>",
      note: "Proton density <em>n</em> in cm<sup>&minus;3</sup> and bulk speed V in km s<sup>&minus;1</sup>, both measured at L1. The left-hand side is the wind pushing in; the right-hand side is Earth's field pushing back. The boundary is wherever they are equal.",
    },
    why: [
      {
        head: "Two pressures, one surface",
        body: "Pressure balance, and nothing more complicated than that. Outside, the wind pushes with its dynamic (ram) pressure — mass density times speed squared. Inside, Earth's field pushes back with magnetic pressure, which rises steeply as you move inward. The boundary sits where the two are equal.",
      },
      {
        head: "Which is why it can be calculated rather than observed",
        body: "That is why its standoff distance can be <strong>calculated</strong> from two numbers a spacecraft an hour upstream is already measuring, and why it walks from about 13.5 Earth radii on a very quiet day to about 7 during a storm — and lower still in the severe events, below geostationary orbit at 6.6.",
      },
    ],
    see: [
      {
        head: "The inner edge of the sheath band",
        body: "It is the inner edge of the sheath band in the model cut. The layer's card reports the live STANDOFF in Earth radii.",
      },
      {
        head: "Three published fits, drawn over it",
        body: "Tick <em>Annotation: empirical boundary models</em> to draw the Shue (1998), Nguyen (2022) and Lin (2010) crossing-fit surfaces thinly over the field: three published fits to thousands of real spacecraft crossings, recomputed from the live wind, saying where they think the boundary is. Where they agree with the model field, the arithmetic is holding. Where they disagree, that is the lesson.",
      },
    ],
  },
  {
    status: "model",
    chip: "Field lines drawn · plasma sheet NOT drawn",
    index: "04",
    title: "Magnetotail and plasma sheet",
    summary: "On the night side the field is peeled back into two long lobes with a thin sheet of hot plasma between them — the part of the system that stores energy and then releases it.",
    claim: "This is the cycle proper: flux opened at the nose, parked in the tail, released back earthward, and returned to the dayside to start again.",
    clip: "dayside-reconnection",
    why: [
      {
        head: "Reconnection, defined",
        body: "<strong>Magnetic reconnection</strong> — two oppositely directed magnetic fields pressed together until the field breaks and rejoins across the join, converting stored magnetic energy into particle motion — happens at the dayside nose whenever the interplanetary magnetic field points south while Earth's field there points north.",
      },
      {
        head: "The loop",
        body: "Each newly opened field line is then dragged antisunward over the pole by the flow and parked in a tail lobe. Opened field lines &mdash; magnetic flux &mdash; pile up; the tail stretches; the lobes get stronger. When enough has accumulated the lobes reconnect with each other across the plasma sheet &mdash; the substorm, the tail&rsquo;s own storm cycle &mdash; and the released plasma is fired back earthward. Then the closed field line returns to the dayside and the cycle repeats.",
      },
      {
        head: "Why one number is watched above all others",
        body: "James Dungey published this in 1961; it is why a southward IMF Bz is the single most-watched number in the subject.",
      },
    ],
    see: [
      {
        head: "The tail loads under southward field",
        body: "The open field lines of the magnetosphere layer carry the tail, and their lobe strength is driven by the measured dynamic pressure and IMF Bz, so it visibly loads under southward field.",
      },
      {
        head: "What is deliberately absent",
        body: "The <strong>plasma sheet itself is not drawn</strong>: the NOAA bundle publishes no extraction of it, so there is nothing there and nothing has been invented to fill the gap. An empty region between the lobes is what honest missing data looks like.",
      },
    ],
  },
  {
    status: "forecast",
    chip: "Model funnels + NOAA forecast oval",
    index: "05",
    title: "Cusps and aurora",
    summary: "Two funnels near local noon, one per hemisphere, where the field offers a way in — and the glow where the particles that came in strike the atmosphere.",
    claim: "Particles do not arrive everywhere. They arrive where field lines lead, and the aurora is the fraction of them that follows its line all the way down.",
    facts: [
      { label: "Emission height", value: "100&ndash;300 km" },
      { label: "Oxygen green", value: "557.7 nm" },
      { label: "Oxygen red", value: "630.0 nm" },
    ],
    why: [
      {
        head: "Along the line is easy; across it is not",
        body: "A charged particle can cross magnetic field lines only with difficulty, but it can travel <em>along</em> them freely. So the particles that get in do not arrive everywhere: they arrive where field lines lead, which is the polar funnels on the dayside and the field lines connected to the plasma sheet on the night side.",
      },
      {
        head: "The light is a discharge lamp on a planetary scale",
        body: "The aurora is the fraction of that population which follows its field line all the way down. At 100–300 km it collides with atomic oxygen and molecular nitrogen, kicks their electrons into excited states, and the light is those electrons dropping back — the same physics as a discharge lamp. Green at 557.7 nm from atomic oxygen, red at 630.0 nm from oxygen higher up where collisions are rare enough to let the slow transition finish.",
      },
    ],
    see: [
      {
        head: "The funnels are found, not asserted",
        body: "Tick <em>Annotation: polar cusps</em> in the magnetosphere layer's own settings — they are off until you ask for them, because a large warm surface nobody asked for reads as a bow shock, which is close to its opposite. The two amber funnels are the model's own cusps — <strong>found, not asserted</strong>: the code searches the summed field for its dayside minima and puts the funnels where the field genuinely nearly vanishes.",
      },
      {
        head: "The far end of the funnel",
        body: "Switch on <em>Auroral oval</em> for NOAA's OVATION precipitation forecast and press the polar camera button (⊙) to look straight down at it.",
      },
    ],
  },
  {
    status: "observed",
    chip: "Measured on the ground · one number, no map",
    index: "06",
    title: "Ring current",
    summary: "The lower-energy half of what stayed behind: 10–200 keV ions drifting around Earth between about 2 and 7 Earth radii, carrying several million amperes westward.",
    claim: "Two populations drifting opposite ways do not cancel — they add, into one westward current whose field at the ground is what Dst measures.",
    clip: "trapped-motion",
    facts: [
      { label: "Energies", value: "10&ndash;200 keV ions" },
      { label: "Where", value: "L &asymp; 2&ndash;7" },
      { label: "Current", value: "Several MA, westward" },
      { label: "Measured as", value: "Dst, in nT" },
    ],
    why: [
      {
        head: "Three motions at once",
        body: "In this dipole picture, L labels a whole field line by its equatorial distance from Earth's centre, in Earth radii. L&nbsp;4 reaches 4 Rᴇ from the centre, about 3 Rᴇ above the equatorial surface.</p><p>A trapped particle does three things at once. It spirals tightly around a field line; it bounces between the two hemispheres, turning around where the field gets strong enough to reflect it; and it drifts slowly around Earth, because the field on the inner side of its spiral is stronger than on the outer side.",
      },
      {
        head: "Why the drift does not cancel",
        body: "That third motion depends on the sign of the charge: <strong>ions drift westward, electrons eastward</strong>. Opposite charges moving in opposite directions do not cancel — they add. It is the same current counted twice, and the net is westward.",
      },
      {
        head: "Which is why the ground can see it",
        body: "A westward current encircling Earth produces a magnetic field that opposes Earth's own at the surface, so when the ring current strengthens, magnetometers at low latitudes worldwide read <em>lower</em>. That depression is the Dst index.",
      },
      {
        head: "What Dst can tell us",
        body: "Dst is an observed ground-field index influenced by multiple current systems. The Dessler–Parker–Sckopke relation estimates ring-current energy from that disturbance, to within about a factor of two. This site uses the index and modelled geometry; it does not ingest the in-situ particle measurements that spacecraft also provide.",
      },
    ],
    see: [
      {
        head: "What it IS measured as",
        body: "Dst is one global number and it has no map, so drawing it as a donut would be a picture of arithmetic. When the classifier says a storm is running, a <em>Geomag storm</em> chip appears in the top bar; open it for three separate Dst traces that are never merged — the Kyoto quicklook index, the USGS observed index and NOAA's modelled series — plus the DPS ring-current energy in joules. Three evidence classes, three clocks, one panel.",
      },
      {
        head: "How it FORMS",
        body: "The <em>Plasma sheet &rarr; ring current</em> layer, badged MODEL-DERIVED since 2026-08-19, draws the supply and the destination on one switch, because they are one injection seen at two radii. The drift paths are traced in a standard model of magnetospheric convection &mdash; the steady circulation the Dungey cycle drives inside the boundary &mdash; with its strength set by Kp, the 0-to-9 planetary index of geomagnetic disturbance computed every three hours from ground magnetometers worldwide. The same convection field, at the same measured Kp, is what erodes the model plasmasphere, so the two layers cannot disagree.",
      },
      {
        head: "What the colour and the edge mean",
        body: "Colour is each ion's own kinetic energy, which climbs as L⁻³ as it is carried inward, so a 10 keV plasma-sheet ion carried in from L 8 arrives at L 4 as an 80 keV ring-current ion. The drawn region ENDS at the last drift path that closes on itself: inside it a particle of that energy is trapped, outside it is swept through — and moving the energy selector moves that edge, which is the point.</p><p>Nothing draws that boundary as a curve; the edge of the region is the boundary. No flux, no density and no location for the real ring current is claimed anywhere in it.",
      },
    ],
  },
  {
    status: "model",
    chip: "Coupled NOAA/NASA RBE electron solution",
    index: "07",
    title: "Radiation belts",
    summary: "The higher-energy half of what stayed behind: electrons from hundreds of keV to several MeV, in an inner belt and an outer belt with a slot between them.",
    claim: "Same trap, different tenants. The ring current and the belts are one physics operating on two populations, and the two names suggest two mechanisms that do not exist.",
    facts: [
      { label: "Energies", value: "100s keV &ndash; several MeV" },
      { label: "Species", value: "Electrons" },
      { label: "Slot clearest at", value: "1.35 MeV" },
      { label: "Belts merge at", value: "88 keV" },
    ],
    why: [
      {
        head: "One mechanism, not two",
        body: "Exactly the same trapping physics as the ring current — spiral, bounce, drift — operating on a different population. That is the whole distinction, and it is worth being blunt about it because the two names suggest two mechanisms and there is only one.",
      },
      {
        head: "Different tenants, different consequences",
        body: "The ring current is the <strong>low-energy ion</strong> population whose pressure depresses the surface field; the radiation belts are the <strong>high-energy electron</strong> population that punches through spacecraft shielding, charges dielectrics and flips bits. Same trap, different tenants, different consequences, different name.",
      },
    ],
    see: [
      {
        head: "The volume, not a threshold",
        body: "Switch on <em>Radiation belts</em>. The default view maps NOAA's modelled electron flux along dipole field lines into a volume and renders the volume itself, so the belts and the slot appear because the model has much flux in one place and little in another — no threshold decides a boundary.",
      },
      {
        head: "Step the energy control",
        body: "At 1.35 MeV the slot between the belts is unmistakable; at 88 keV the two belts genuinely merge, and the picture merges with them.",
      },
    ],
  },
];

function stageCard(card: StageCard): string {
  return `<details class="method-card stage-card" data-stage="${card.index}">
    <summary>${evidenceBadge(card.status)}<small class="layer-status-note">${card.chip}</small><strong>${card.index} · ${card.title}</strong><small>${card.summary}</small></summary>
    <div class="method-card-body">
      <p class="stage-claim">${card.claim}</p>
      ${card.facts ? `<div class="fact-grid">${card.facts.map((f) => `<div><span>${f.label}</span><strong class="is-readout">${f.value}</strong></div>`).join("")}</div>` : ""}
      ${card.equation ? `<figure class="stage-equation"><p class="stage-equation-math">${card.equation.math}</p><figcaption>${card.equation.note}</figcaption></figure>` : ""}
      <div class="stage-half">
        <p class="section-kicker">${card.whyKicker ?? "WHY IT IS THERE"}</p>
        <div class="beat-list">
          ${card.why.map((beat, i) => `<section class="beat"><p class="beat-index" aria-hidden="true">${String(i + 1).padStart(2, "0")}</p><div><h4>${beat.head}</h4><p>${beat.body}</p><div class="method-citation">Related sources: ${sourceLinks(WEATHER_SOURCES.dungey ?? [], true)}</div></div></section>`).join("")}
        </div>
      </div>
      ${card.clip ? `<div class="stage-half stage-clip"><p class="section-kicker">WATCH THE MECHANISM</p>${mechanismFigure(card.clip)}</div>` : ""}
      ${card.see.length ? `<div class="stage-half stage-see">
        <p class="section-kicker">${card.seeKicker ?? "SEE IT ON THIS SITE"}</p>
        <div class="beat-list">
          ${card.see.map((beat) => `<section class="beat beat--plain"><div><h4>${beat.head}</h4><p>${beat.body}</p><div class="method-citation">Related sources: ${sourceLinks(WEATHER_SOURCES.dungey ?? [], true)}</div></div></section>`).join("")}
        </div>
      </div>` : ""}
    </div>
  </details>`;
}

function recipeStep(title: string, detail: string): string {
  return `<li><div><strong>${title}</strong><span>${detail}</span></div></li>`;
}

function dungeyCyclePage(): string {
  return `
    ${pageBack()}
    <header class="content-hero layer-page-hero">
      <p class="eyebrow">THE DUNGEY CYCLE · 1961 · AND THE POPULATIONS IT LEAVES BEHIND</p>
      <h1>One interaction, and every structure that follows from it</h1>
      <p>Solar wind and interplanetary magnetic field arrive. A bow shock forms. A magnetosheath flows around. A magnetopause holds the line. The tail stretches and snaps back. Particles are funnelled to the poles. The aurora lights. A fraction of what came in stays trapped, and becomes the ring current and the radiation belts. That is not eight things to memorise.</p>
    </header>
    <section class="track-section" aria-labelledby="dungey-argument-title">
      <div class="content-prose">
        <h2 id="dungey-argument-title" class="prose-lead-in">It is one interaction and its consequences.</h2>
        <p>That interaction is <strong>a supersonic, magnetised plasma running into a planetary dipole</strong>. Every structure in the list above falls out of that single encounter. The circulation it drives — field lines opened at the dayside nose, dragged back over the poles, reconnected in the tail, fired earthward, and returned to the dayside to start again — is the <strong>Dungey cycle</strong>, after James Dungey, who worked it out in 1961. The populations that circulation leaves behind are the ring current and the radiation belts. Learn the one interaction and the eight names stop being a list and become a sequence.</p>
        <p>The step that makes the cycle turn is <strong>magnetic reconnection</strong>: two magnetic fields pointing in opposite directions are pressed together until the field breaks and rejoins across the join, and the energy that was stored in the bent field goes into moving particles.</p>
        <p>On the dayside this happens when the interplanetary magnetic field — the Sun's own field, carried frozen into the solar wind, written IMF — points south while Earth's field at the nose points north. That is the whole reason southward <em>Bz</em> is the most-watched number in this subject. It does not make the wind stronger. It decides whether the wind's field can join Earth's, and therefore whether the cycle runs fast or idles.</p>
      </div>
    </section>
    <section class="track-section" id="dungey-stages" aria-labelledby="dungey-stages-title">
      <div class="method-section-head">
        <p class="section-kicker">SEVEN STAGES · IN THE ORDER THE WIND MEETS THEM</p>
        <h2 id="dungey-stages-title">What the wind runs into, one structure at a time.</h2>
        <p>Each card opens onto the same three things: what it is and why it has to be there, the mechanism where an animation exists for it, and where it appears on this globe — including the places where the honest answer is that it does not.</p>
      </div>
      <div class="method-grid stage-grid">
        ${DUNGEY_STAGES.map(stageCard).join("")}
      </div>
    </section>
    <section class="processing-ledger" aria-labelledby="dungey-recipe-title">
      <div><p class="section-kicker">PLOT IT IN THIS ORDER</p><h2 id="dungey-recipe-title">See the Dungey cycle for yourself.</h2></div>
      <p>Every layer named below is a real toggle in the explorer's layer list, and every camera button is a real button on the globe. Switch them on in this order and the cycle assembles itself in front of you, in the order the physics happens.</p>
      <ol class="recipe-steps">
        ${recipeStep("Solar wind &amp; IMF", "The input to everything else. The amber shower is the measured wind: how many particles you can see is the measured proton density, how fast they arrive is the measured bulk speed, and the three colours are the three species — protons, alpha particles, electrons.")}
        ${recipeStep("Magnetosphere", "The geometry the wind runs into: field lines traced through a driven model, coloured by field strength, cut off at the live boundary. Press the meridional cross-section camera button (⊘) — the textbook cut, Sun on the left.")}
        ${recipeStep("NOAA MHD cross-section", "In that layer's own settings, behind the caret beside its toggle. This is the real NOAA simulation's plasma (an MHD run — magnetohydrodynamics, the plasma treated as one conducting fluid), on its published cut, embedded as a slice through the scene. Bow shock: where the colours jump. Magnetosheath: the band behind it. Magnetopause: the inner edge of that band. Nobody drew any of the three.")}
        ${recipeStep("Switch the Plasma field control", "Density, Speed, Pressure, |B| — the same three structures, four different quantities. Speed makes the shock cleanest; pressure is the most dramatic on a storm-compressed dayside. If a structure survives all four, it is a structure and not a colour-map artefact.")}
        ${recipeStep("Solar-wind flow — projected U + tracers", "The simulation's own bulk-flow lines, with tracers moving at its own local speed. Watch them slow abruptly at the shock and turn aside around the boundary. That is the magnetosheath doing its job.")}
        ${recipeStep("The three annotation overlays", "<em>Annotation: extracted boundary curves</em> is where an algorithm reads the jump you can already see; <em>Annotation: empirical boundary models</em> is where Shue, Nguyen and Lin say the boundary should be, from the live wind; <em>Annotation: polar cusps</em> shades the volume between two of those fits, which is the one way in on the dayside. Thin lines over the field, never instead of it, and each arrives with its own colour-keyed row in the layer's key. Their agreement is a check, and their disagreement is a lesson.")}
        ${recipeStep("Annotation: polar cusps", "Worth its own step, because it is the one thing in this layer that is neither a field line nor a boundary. Two amber funnels over the poles, drawn as the volume between Lin (2010)'s cusp inner boundary and Nguyen (2022)'s current sheet. NOT a bow shock: a bow shock stands about 13 R&#8853; further out and is where the wind is stopped, while a cusp is where it gets in. Switch the solar wind on beside it and watch the guided fraction ride the field lines down into them.")}
        ${recipeStep("Auroral oval, then the polar view (⊙)", "The far end of the funnel: where the particles that got in end up. Then add Radiation belts and Plasma sheet &rarr; ring current for what did not get out again — and for where it came from — the trapped populations, in the same frame as the boundary that traps them. The plasmasphere’s own boundary is a chart at the foot of the Current conditions page, on the same page as the Kp that squeezes it.")}
        ${recipeStep("Drag the timeline back across 48 hours", "This is the step that makes it one system instead of six pictures. Every layer is driven by the same measured wind on the same clock, so scrubbing a storm shows one cause and six effects in sequence: pressure rises, the boundary and shock move earthward, the sheath narrows, the dayside field compresses, the oval pushes equatorward, Dst falls. If a storm is running, the Geomag chip in the top bar also offers <em>Show me this storm on the globe</em>, which switches on the three responding layers at once.")}
      </ol>
      <p>None of that requires being told which shape to look for, and that is the point. Plot the right things in the right order and the Dungey cycle turns up on its own, out of quantities that were measured by somebody else.</p>
    </section>
    <section class="lesson-block lesson-next" aria-labelledby="dungey-next-title">
      <p class="section-kicker">WHERE THIS GOES NEXT</p>
      <h2 id="dungey-next-title">Carry on.</h2>
      <div class="next-grid">
        <button type="button" class="link-button" data-weather-page="engine">How this picture is built, and what it cannot know<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
        <button type="button" class="link-button" data-weather-lesson="compression">Module 04 &middot; the dayside compresses<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
        <button type="button" class="link-button" data-weather-index>All eight lessons<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
      </div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// HOW THIS PICTURE IS BUILT — its own page since 2026-08-21.
//
// This is the "MOUNTAIN of text after it" Sean was looking at. It is the best
// writing on the site and it was the seventh thing on one scroll, below eight
// dead cards, six videos and a seven-part argument, so almost nobody reached
// it. Nothing is cut. It has a contents strip, its four sub-arguments are
// separately titled and separately reachable, the one 163-word paragraph in it
// is broken into beats, and the four limitation cards are one column wide.
// ---------------------------------------------------------------------------

function physicsEnginePage(): string {
  return `
    ${pageBack()}
    <header class="content-hero layer-page-hero">
      <p class="eyebrow">THE PHYSICS ENGINE · WHAT IS MEASURED · WHAT IS FITTED · WHAT IS UNKNOWN</p>
      <h1>How this picture is built, and what it cannot know</h1>
      <p>The magnetosphere on this globe is neither a photograph nor a cartoon. It is a physics model with a small number of measured numbers pushed into it, recalibrated on every frame against the only real simulation output that is published in public. This section says which parts are which — including the parts that are missing.</p>
    </header>
    <nav class="track-map track-map--inline" aria-label="On this page">
      <p class="section-kicker">ON THIS PAGE</p>
      <ol>
        <li><button type="button" data-weather-scroll="engine-measured"><span class="track-map-index">01</span><span><strong>What is actually measured</strong><small>Four kinds of input, and they are not equally strong.</small></span><span class="track-map-arrow" aria-hidden="true">&rarr;</span></button></li>
        <li><button type="button" data-weather-scroll="engine-construction"><span class="track-map-index">02</span><span><strong>Two planes, and how they become a picture</strong><small>What NOAA publishes, and the three citable pieces built on it.</small></span><span class="track-map-arrow" aria-hidden="true">&rarr;</span></button></li>
        <li><button type="button" data-weather-scroll="engine-ruler"><span class="track-map-index">03</span><span><strong>Why the distances are not to scale</strong><small>One compressed radial ruler, in four bands.</small></span><span class="track-map-arrow" aria-hidden="true">&rarr;</span></button></li>
        <li><button type="button" data-weather-scroll="engine-limits"><span class="track-map-index">04</span><span><strong>What it cannot know</strong><small>Four limitations, given the same room as a mechanism.</small></span><span class="track-map-arrow" aria-hidden="true">&rarr;</span></button></li>
      </ol>
    </nav>
    <section class="track-section" id="engine-measured" aria-labelledby="engine-measured-title">
      <div class="content-prose">
        <h2 id="engine-measured-title" class="prose-lead-in">What is actually measured</h2>
        <p>Four kinds of input reach this site, and they are not equally strong.</p>
        <p><strong>Measured in space, by an instrument.</strong> NOAA's real-time solar-wind feed, from the L1 monitors SWPC is receiving — SOLAR1, ACE and IMAP as this is written, one of them nominated active — parked at the first Lagrange point about 1.5 million kilometres sunward of Earth, where the Sun's and Earth's gravity let a spacecraft hover on the Sun–Earth line. It reports proton number density in particles per cubic centimetre, bulk speed in kilometres per second, and the interplanetary magnetic field as a vector in nanotesla. That is <strong>one point in space</strong>, 30 to 60 minutes upwind.</p>
        <p>GOES supplies the soft X-ray irradiance and the energetic-particle channels, measured at geostationary orbit.</p>
        <p><strong>Measured on the ground.</strong> The Dst index — the depression of the horizontal magnetic field at low-latitude magnetometer stations — reaches the site as three separate series that are never merged: the Kyoto quicklook index, the USGS observed index, and NOAA's modelled value. Planetary Kp arrives the same way.</p>
        <p><strong>Assimilated.</strong> Observations combined with a numerical background, as GloTEC does for total electron content — stronger than a pure model, weaker than a measurement, and worth its own word.</p>
        <p><strong>Modelled or forecast.</strong> NOAA's OVATION aurora forecast, the RBE radiation-belt electron solution, the WAM-IPE ionosphere, D-RAP absorption, and the NOAA geospace magnetohydrodynamic run — magnetohydrodynamics, MHD, being the treatment of a plasma as a single electrically conducting fluid. These are somebody's calculation, not somebody's measurement, and the badge on every layer says so.</p>
      </div>
    </section>
    <section class="track-section" id="engine-construction" aria-labelledby="engine-construction-title">
      <div class="content-prose">
        <h2 id="engine-construction-title" class="prose-lead-in">What NOAA's magnetosphere model actually gives us: two planes</h2>
        <p>This is the single most important limitation on the site and it is usually glossed over elsewhere. NOAA runs a coupled configuration of the Space Weather Modeling Framework, with BATS-R-US solving the global MHD problem. That run is genuinely three-dimensional.</p>
        <p>What NOAA <strong>publishes</strong> on its low-latency public tree is not: it is two two-dimensional cross-sections through the volume — the equatorial cut at z = 0 and the noon–midnight meridional cut at y = 0 — plus extracted boundary traces giving the bow-shock and magnetopause radius as a function of angle. Two intersecting sheets and a pair of curves, roughly every twenty minutes — of which this site's own published archive keeps one frame every two hours, to hold the download to a few hundred kilobytes.</p>
        <p>So the site holds two real slices through a real simulation. Everything three-dimensional you see around them is a model of this site's own, and the rest of this section is about being precise about what that model is.</p>
        <h3>How the two planes become a three-dimensional picture</h3>
        <p>The field-line layer is a <strong>semi-empirical vacuum-superposition model</strong> — not MHD, not a Tsyganenko-style empirical field model fitted to decades of spacecraft data — built from three citable pieces, every parameter of which is driven by measured data.</p>
      </div>
      <div class="beat-list beat-list--wide">
        <section class="beat"><p class="beat-index" aria-hidden="true">01</p><div><h3>A tilted centred dipole</h3><p>From the IGRF-13 coefficients: Earth's own field, which is the largest term everywhere inside the boundary. Its tilt against the Sun–Earth line is computed from the date and time, so it breathes with the seasons and the day.</p></div></section>
        <section class="beat"><p class="beat-index" aria-hidden="true">02</p><div><h3>A Chapman–Ferraro image dipole (1931)</h3><p>Placing a mirror-image dipole sunward at twice the standoff distance makes the plane at the standoff a surface no field crosses — which is exactly what the magnetopause currents do, expressed as an equivalent source instead of as a current sheet. It doubles the field at the nose, compresses the dayside lobes, and produces two dayside magnetic nulls for free. Those nulls <strong>are</strong> the polar cusps of this model, and the site finds them by searching the summed field for its minima rather than drawing a funnel where one ought to be — <strong>found, not asserted</strong>.</p></div></section>
        <section class="beat"><p class="beat-index" aria-hidden="true">03</p><div><h3>A Harris (1962) current-sheet tail</h3><p>Derived from a vector potential so that the field it produces is exactly divergence-free — no magnetic monopoles anywhere in the drawn field, including inside the smooth ramp where the tail turns on. The lobe strength is driven, not fixed: it scales with the square root of the measured dynamic pressure, which is pressure balance across the boundary, and it grows under southward IMF Bz, which is the Dungey cycle loading flux into the tail.</p><p>The exact parameterisation is written down in the module and in the layer contracts document, and it is labelled as an illustrative driven approximation because that is what it is.</p></div></section>
      </div>
      <div class="content-prose">
        <p>Field lines are then traced through the summed field with a fourth-order Runge–Kutta integrator — a standard method for following a direction field accurately in small steps — and each line is classified by where it ends: closed if it returns to the surface in the other hemisphere, open if it leaves down the tail, boundary if it runs into the magnetopause.</p>
        <h3>The calibration step, which is the part that matters</h3>
        <p>A driven model still has to be answerable to data, and here is where it is. On every frame the site takes <strong>NOAA's own extracted magnetopause curve for that frame</strong> and fits the Shue et al. (1998) boundary form to it by exact linear least squares in log space — deterministic, no iteration, no initial guess. The fitted standoff r₀ and flaring exponent α then become the boundary the image dipole is pinned to and the surface the traced lines are truncated at.</p>
      </div>
      <figure class="stage-equation stage-equation--wide">
        <p class="stage-equation-math">r(&theta;) = r<sub>0</sub> [ 2 / (1 + cos &theta;) ]<sup>&alpha;</sup></p>
        <figcaption>The Shue et al. (1998) boundary form. r<sub>0</sub> is the standoff distance at the nose and &alpha; is the flaring exponent; fitting both to NOAA's own extracted curve is what pins this site's field to the real model output on every frame.</figcaption>
      </figure>
      <div class="content-prose">
        <p>That is the fusion, stated plainly: <strong>where the real model output exists, this picture is fitted to it; between the constraints, physics with known symmetry governs.</strong> It is not interpolation and it is not invention. It is a fitted model whose fit quality is printed on the layer's own card — <em>NOAA MHD FRAME · FIT RMS 0.xx R⊕</em> — next to the residual the uncalibrated, L1-driven Shue surface would have had, so you can see whether the calibration actually improved anything on this frame.</p>
        <p>It also refuses. If the fit returns a standoff outside 4–18 Earth radii or a flaring exponent outside 0.2–1.1, the calibration is thrown away and the layer falls back to Shue-driven-from-L1, and the card says <em>EMPIRICAL SHUE FROM L1</em> instead. A bad frame is allowed to produce no calibration; it is not allowed to bend the picture.</p>
        <h3>The particles, and the one number that is assumed</h3>
        <p>The amber shower is built from measurements and one stated assumption. Its population and brightness follow the measured proton density; its cadence follows the measured bulk speed. The species split needs the alpha-particle abundance, and <strong>the L1 feed does not publish it</strong> — so the canonical slow-wind ratio of one alpha per twenty-five protons (4%) is assumed, said out loud, and quasi-neutrality then fixes the electrons exactly: one electron per proton plus two per alpha.</p>
        <p>The observed range is roughly 1–5%, rising toward 8% in some fast streams and coronal mass ejections, so this is the number to distrust first. Nothing else in the mix is invented.</p>
        <p>With the magnetosphere layer on, a visible fraction of the arriving particles is guided along the traced field lines themselves — down the boundary-truncated dayside lines into the cusps, or tailward along the open polar-cap lines. The polylines they ride are the field model's own output, but which particles enter is a geometric selection and their motion along the line is illustrative: it is not a solved reconnection rate, and the cadence you see is a display choice, because what the instruments measure is bulk plasma, not individual particles.</p>
      </div>
    </section>
    <section class="track-section" id="engine-ruler" aria-labelledby="engine-ruler-title">
      <div class="content-prose">
        <h2 id="engine-ruler-title" class="prose-lead-in">Why the distances on the globe are not to scale</h2>
        <p>A satellite in low Earth orbit sits 400 km up. Geostationary orbit is 35,786 km. The magnetopause nose is around 70,000 km, and the tail runs out past three million. Drawn at true scale on one screen, the whole of low Earth orbit is a hairline on the edge of the Earth and everything interesting is either invisible or off the page. So every layer that draws a physical radius — satellites, belts, plasmasphere, boundaries, the model cut planes — shares <strong>one compressed radial ruler</strong>, and it works in four bands.</p>
      </div>
      <div class="beat-list beat-list--wide">
        <section class="beat"><p class="beat-index" aria-hidden="true">01</p><div><h3>Surface to geostationary orbit (6.6 Earth radii): logarithmic</h3><p>Each factor of ten in altitude gets roughly equal room on screen, which is the only way the ionosphere&rsquo;s 90 km floor and a 35,786 km orbit can appear in the same picture.</p></div></section>
        <section class="beat"><p class="beat-index" aria-hidden="true">02</p><div><h3>Geostationary orbit to 7.35 Earth radii: the joint</h3><p>The two scales either side of this band magnify radius seven times differently, and for a while they were simply butted together at geostationary radius. That was wrong, and visibly so.</p><p>A ruler that only stretches radius bends any line that crosses it at an angle, and a <em>step</em> in the stretch bends it through a corner — so every highly elliptical orbit, which crosses geostationary radius twice per revolution, was drawn with a hard kink in it, and so were most of the traced magnetic field lines. It was false geometry, not a drawing artifact: no amount of extra detail could smooth it, because the corner was in the ruler.</p><p>Since 2026-08-19 the magnification slides across this band instead of stepping, so the drawn orbit is a curve where the real orbit is a curve. Nothing at or below geostationary orbit moved; the whole cost was paid by the outer scene drawing 4.4% smaller.</p></div></section>
        <section class="beat"><p class="beat-index" aria-hidden="true">03</p><div><h3>7.35 out to 13 Earth radii: linear</h3><p>This band holds the whole dayside boundary system — magnetopause nose, bow-shock nose, the flanks at the terminator — and drawing it linearly means the drawn <em>shape</em> is the true shape. Ratios of radii and directions of motion are exactly right here. When the real boundary flares 1.64 times from nose to flank, it is drawn flaring 1.64 times. This was not always so: an earlier purely logarithmic ruler drew that same flaring as 1.07, and the magnetosphere rendered as a near-sphere no matter how correctly the physics upstream had been computed.</p><p>That exactness has edges. It holds while the whole boundary sits inside this band. In a storm strong enough to push the magnetopause nose below 7.35 Earth radii the drawn flare is understated — by about 1% with the nose at 7.0 and about 5% at 6.6 — and at quiet times it is understated by about 4% for the opposite reason, because with the nose far out at 11.6 the flank passes 13 Earth radii into the tapered band. Neither is a large error on a picture, and neither is hidden here.</p></div></section>
        <section class="beat"><p class="beat-index" aria-hidden="true">04</p><div><h3>Beyond 13 Earth radii: tapered</h3><p>The scale progressively foreshortens, so the far tail and the outer corners of the cut planes fit in frame at all. That foreshortening is the price paid for the dayside being true, and it is a deliberate trade rather than an accident.</p></div></section>
      </div>
      <aside class="teaching-callout"><strong>What follows honestly, and what is preserved</strong>A distance measured with a ruler held against the screen <em>is not proportional to a real distance</em> anywhere on this globe, and the tail is drawn far shorter than it is. What is preserved: order — anything drawn outside something else really is outside it, everywhere, because the ruler is strictly increasing — and, in the 7.35-to-13-Earth-radii band, shape. And every number in every legend, card and readout is the physical value in kilometres or Earth radii, never the drawn one.</aside>
    </section>
    <section class="track-section" id="engine-limits" aria-labelledby="engine-limits-title">
      <div class="method-section-head">
        <p class="section-kicker">FOUR LIMITATIONS · SAME ROOM AS A MECHANISM</p>
        <h2 id="engine-limits-title">What this engine cannot know</h2>
        <p>A limitation deserves the same amount of room as a mechanism, so these are the same cards in the same grammar as the seven Dungey stages.</p>
      </div>
      <div class="method-grid stage-grid">
        ${ENGINE_LIMITS.map(stageCard).join("")}
      </div>
      <aside class="teaching-callout"><strong>Why the limitations are the teaching content, not the disclaimer</strong><p>A product that shows you only what it knows is training you to trust all of it equally. The operational skill — the one that matters when a forecast is an input to a decision — is knowing which parts of a picture are load-bearing measurement and which parts are the model filling in a gap with a defensible guess. Everything above is an attempt to make that separable by eye.</p><p>When any tool tells you the magnetopause is at 7 Earth radii, the useful question is what measured it. On this site the honest answer is: two numbers, from one spacecraft, an hour upstream, put through a published formula, and then fitted to a simulation's own extracted curve — with the residual of that fit printed on the card so you can see how well it went.</p></aside>
    </section>
    <section class="lesson-block lesson-next" aria-labelledby="engine-next-title">
      <p class="section-kicker">WHERE THIS GOES NEXT</p>
      <h2 id="engine-next-title">Carry on.</h2>
      <div class="next-grid">
        <button type="button" class="link-button" data-weather-page="dungey">The Dungey cycle &middot; the physics this engine is a picture of<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
        <button type="button" class="link-button" data-view="sources">Data &amp; methods &middot; every layer, one card each<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
        <button type="button" class="link-button" data-weather-index>All eight lessons<span class="module-open-arrow" aria-hidden="true">&rarr;</span></button>
      </div>
    </section>
  `;
}

/**
 * What the engine cannot know. Same card grammar as the Dungey stages, because
 * a limitation deserves the same amount of room as a mechanism.
 */
const ENGINE_LIMITS: StageCard[] = [
  {
    status: "observed",
    chip: "One point, one hour upstream",
    index: "L1",
    title: "A single upstream sample is not the wind that arrives",
    summary: "Everything downstream inherits the uncertainty of one spacecraft measuring one point 1.5 million kilometres away.",
    claim: "The L1 monitor measures the wind that hits the L1 monitor. Whether that is the wind that hits Earth is an assumption, not an observation.",
    whyKicker: "WHAT IS UNCERTAIN",
    seeKicker: "THE FAILURE MODE WORTH KNOWING",
    why: [
      {
        head: "One point, and the wind is structured",
        body: "The solar wind is structured on scales smaller than the distance from L1 to Earth, and the interplanetary field direction in particular can differ between the two, so the wind that arrives is not exactly the wind that was sampled.",
      },
      {
        head: "The arrival time is estimated, not observed",
        body: "It is computed from the measured speed, which puts tens of minutes of timing uncertainty on every driven layer. This is not a defect of this site — it is the actual state of the art in operational space weather, and it is why a magnetopause standoff quoted to a tenth of an Earth radius should be read as a model output, not a position.",
      },
    ],
    see: [
      {
        head: "A monitor can be wrong while reporting itself healthy",
        body: "During the May 2024 Gannon storm, DSCOVR's Faraday cup reported roughly 475 km s⁻¹ and 2 cm⁻³ while other monitors saw 770–1000 km s⁻¹ and 16–29 cm⁻³, and its own quality flag read <em>nominal</em> for 549 of those minutes.",
      },
      {
        head: "Which would have inverted the picture",
        body: "Because dynamic pressure goes as density times speed squared, that understates the pressure by a factor of about thirty — and a site that trusted the flag would have drawn an expanded magnetosphere during the most severe compression in twenty years, with every honesty label saying the data was fine. This site's publisher therefore corroborates the sample against a different spacecraft and against the magnetometer's own behaviour before publishing it, and a source's self-assessment is treated as evidence, never as proof.",
      },
    ],
  },
  {
    status: "model",
    chip: "Two planes cannot pin what lies between them",
    index: "2D",
    title: "Two cuts are not a volume",
    summary: "The equatorial and meridional slices are real, but nothing constrains the model between them.",
    claim: "A feature that appears on one sheet is not automatically a three-dimensional shell, and this site does not promote it into one.",
    whyKicker: "WHAT IS UNCERTAIN",
    seeKicker: "WHAT WOULD FIX IT",
    why: [
      {
        head: "Each cut is blind to what the other sees",
        body: "The meridional cut sees the noon–midnight plane and cannot see the dawn–dusk difference; the equatorial cut sees the dawn–dusk plane and cannot see the tail's vertical structure. Any asymmetry that lives between the two planes is unconstrained by data.",
      },
      {
        head: "And the construction is symmetric where the real thing is not",
        body: "This site's own construction is symmetric about the noon–midnight plane by design — while the real magnetosphere is not, because an east–west component of the interplanetary field twists the whole system.",
      },
    ],
    see: [
      {
        head: "Full 3-D output exists, on request, elsewhere",
        body: "Full three-dimensional BATS-R-US output does exist publicly, through NASA's Community Coordinated Modeling Center on a runs-on-request basis. It is asynchronous and run-specific, not the low-latency operational feed, so it belongs to a separate historical lane with its own run ID and provenance — not to the live picture. No full-volume control appears on this site until a particular run has actually been acquired and validated.",
      },
    ],
  },
  {
    status: "model",
    chip: "Absent on purpose",
    index: "PS",
    title: "The plasma sheet is not drawn, and other empty regions",
    summary: "Where the published data contains no extraction of a structure, the structure is missing rather than approximated.",
    claim: "An empty globe is a scientific result.",
    whyKicker: "WHAT IS ABSENT",
    seeKicker: "WHY THIS IS A RULE AND NOT A SHORTFALL",
    why: [
      {
        head: "The most consequential region in the system",
        body: "The plasma sheet — the hot layer between the tail lobes, and arguably the most consequential region in the whole system — is not drawn, because the NOAA bundle publishes no extraction of it.",
      },
      {
        head: "And the same rule everywhere else",
        body: "Masked cells in the model cuts stay empty rather than being interpolated across. Selected times outside a product's real coverage make that layer disappear and say why, instead of freezing the current field or inventing a forecast to keep the globe full.",
      },
    ],
    see: [
      {
        head: "A plausible shape is indistinguishable from a constrained one",
        body: "The alternative — a plausible shape drawn where no data exists — is indistinguishable to the eye from the parts that are constrained, and it is exactly the failure that makes teaching visualisations untrustworthy. The site's standing rule is that a driven approximation with its method written down is welcome, and a static or fabricated shape is not. Where the approximation cannot be driven by anything, nothing is drawn.",
      },
    ],
  },
  {
    status: "empirical",
    chip: "Topology is the claim; positions are not",
    index: "FL",
    title: "What a drawn field line does and does not assert",
    summary: "The shape of the system and its response to the drivers are the claim. No individual line is a measurement.",
    claim: "The topology and its response to the drivers are checkable claims. No individual drawn line is.",
    whyKicker: "WHAT IS CLAIMED",
    seeKicker: "WHAT IS NOT CLAIMED",
    why: [
      {
        head: "The shape, and how it responds",
        body: "The model reproduces the topology every reference depiction of the magnetosphere shows — compressed dayside loops, open polar caps, cusp funnels where the dayside lines converge, a stretched two-lobe tail — and its shape responds to the measured drivers in the physically correct direction and by a defensible amount.",
      },
      {
        head: "And the numbers are how you check it",
        body: "That is a real and checkable claim, and the numbers on the card are how you check it: the standoff, where the dayside stops closing, the lowest latitude that is open at midnight, the tail lobe field.",
      },
    ],
    see: [
      {
        head: "Not a measurement, and not an MHD solution",
        body: "No individual drawn line is a measurement or an MHD solution, and nobody has ever measured a magnetopause surface — the empirical boundary models are fits to thousands of individual spacecraft crossings, which is a different and weaker thing than an observed surface.",
      },
      {
        head: "And three more things that are display, not data",
        body: "The alpha-particle abundance in the solar-wind shower is assumed. Particle cadence and count are display encodings of measured bulk quantities, not tracked particles. And the operational MHD model this site calibrates against has a published skill score against ground magnetometers that is moderate rather than excellent — beautiful field lines are not a skill score.",
      },
    ],
  },
];

/*
 * `lesson()` was removed on 2026-08-21.
 *
 * It was learning track 01's card helper and the last thing in this file that
 * emitted `<div class="diagram">` — the 180px radial-glow box holding five
 * words of monospace that Sean pointed at ("What are all those modules at the
 * beginning of it? They don't go anywhere."). Track 01 moved to
 * `src/satellite-fundamentals.ts` while this redesign was in flight, which
 * left the helper unreferenced, so the box is now emitted by nothing at all.
 * The retired rule in `src/styles.css` is kept as the record of what it was.
 */

export function eventsView(bundle: EventsBundle): string {
  return `
    <header class="content-hero">
      <p class="eyebrow">HISTORICAL EVENTS · REPLAYED FROM THE ORIGINAL RECORDS</p>
      <h1>Real storms, replayed from the instruments that watched them.</h1>
      <p>Every event here is a real one, chosen because it teaches something the others cannot. Where this project holds the actual observations you get them — real instrument samples, on a real UTC clock, with the archive they came from named underneath. Where it does not, you get the documented sequence in words and no picture at all, because a drawing that could stand for any storm teaches you nothing about this one.</p>
    </header>
    <div class="event-grid">
      ${bundle.events.map(eventCard).join("")}
    </div>
  `;
}
/*
 * `<div id="event-player" class="event-player" hidden>` used to sit here,
 * between the hero and the grid. openEventPlayer() filled it and called
 * scrollIntoView, which meant that opening the sixth card smooth-scrolled the
 * reader back up past the other five to reach a single player at the top of the
 * page. Sean, 2026-08-21: "it looks like it opens all events and scrolls the
 * page through all of them to the correct one ... This isn't good the way it
 * is." It is exactly one player, filled and scrolled to; there was never more
 * than one event open.
 *
 * The player now lives inside `#event-dialog` in index.html and is opened with
 * showModal(). The grid does not move at all, so closing the replay leaves the
 * reader on the card they clicked.
 */

/**
 * One card in the grid.
 *
 * The card carries a MEDIA LINE: one sentence naming what this event actually
 * has — measured chart, instrument footage, both, or neither — read off the
 * same two sources the replay itself renders from, so it cannot drift from what
 * opening the card shows. This page's standing rule is that an event with no
 * picture says so in words rather than presenting an empty frame, and the rule
 * has to hold on the card as well as inside the replay: `stpatricks-2015` and
 * `bastille-2000` were the two events for which `observedImageryBlock` returned
 * "" and the reader had no way of knowing before clicking.
 */
function eventCard(event: HistoricalEvent): string {
  return `<article class="event-card"><span class="section-kicker">${event.date}</span><h2>${event.title}</h2><p>${event.summary}</p><p class="event-card-media">${eventMediaLine(event)}</p><button data-replay-event="${event.id}">Open guided replay</button></article>`;
}

/** What this event holds, in one sentence, for the card. */
export function eventMediaLine(event: HistoricalEvent): string {
  const chart = Boolean(event.replay);
  const clips = eventObservedClipCount(event.id);
  const parts: string[] = [];
  if (chart) parts.push("a measured chart on a real UTC clock");
  if (clips === 1) parts.push("one clip of instrument footage");
  else if (clips > 1) parts.push(`${clips} clips of instrument footage`);
  if (parts.length === 0) {
    return "Holds: the documented sequence in words, and its sources. No measured chart and no footage are published for it — everything it has is text.";
  }
  const held = parts.length === 2 ? `${parts[0]} and ${parts[1]}` : parts[0];
  const missing = clips === 0
    ? " No footage of the Sun is published for it."
    : chart
      ? ""
      : " No measured chart is published for it yet.";
  return `Holds: ${held}.${missing}`;
}

/**
 * The body of one guided replay.
 *
 * There are two kinds of event on this page and they are drawn differently on
 * purpose. An event this project holds MEASUREMENTS for gets those
 * measurements, animated by `src/event-replay.ts` against a real UTC clock. An
 * event it does not gets the labelled schematic, which claims nothing.
 *
 * STRUCTURE, 2026-09-03. Sean, after the synopsis and the impacts landed:
 * "the historical events pages are still a bit off - there just isn’t any
 * flow for a reader." What he was reading was six blocks at one visual
 * weight -- orientation, an animated chart with its own controls, a list,
 * testimony, footage of the Sun, a moral, links -- each fine alone and none
 * handing off to the next. The player is now a sequence of ACTS: each block
 * opens with a real heading and one connective line that says what the reader
 * is about to meet and why it follows from the block before. Those lines are
 * STRUCTURAL -- they describe what the page is doing, never the storm -- so
 * no new claim about a real event rides in without an attribution. Per-event
 * prose stays where it always was: in `synopsis` (which every event ends by
 * saying what its replay tracks), in the milestones, and in the impacts.
 */
export function eventPlayer(event: HistoricalEvent): string {
  return `
    <div class="event-player-head"><div><span class="section-kicker">${event.status.replaceAll("-", " ").toUpperCase()}</span><h2 id="event-dialog-title">${event.title}</h2></div><button type="button" data-close-event>Close replay</button></div>
    <p class="event-synopsis">${event.synopsis}</p>
    ${event.replay ? eventReplayBody(event) : eventSchematicBody(event)}
    ${eventImpacts(event)}
    ${imageryAct(event.id)}
    <section class="event-act event-closer">
      <aside class="teaching-callout"><strong>Why this case matters</strong>${event.lesson}</aside>
      <h3 class="event-act-head">Go to the record</h3>
      <p class="event-act-lede">The public accounts this page’s story can be checked against.</p>
      <div class="source-grid">${event.sources.map((source) => `<article class="source-card"><a href="${source.url}" target="_blank" rel="noreferrer">${source.label} ↗</a></article>`).join("")}</div>
    </section>
  `;
}

/**
 * What the storm actually did, with every claim attributed.
 *
 * This block is the one Sean asked for by name and the page did not have. The
 * milestone list above it is the SEQUENCE -- shock, turning, ring current --
 * and a reader who only has that comes away knowing the physics ran its
 * course without knowing that six million people lost power, or that
 * thirty-eight spacecraft came down. Those are the facts that make a novice
 * care about the chart, and they were nowhere on the page.
 *
 * The attribution is not decoration. Everything else in the player is drawn
 * from instrument records this project holds; an impact is a claim about the
 * world that no replay can evidence, so it names its source and stays
 * visually distinct from the measured material around it. The act’s lede
 * says that rule out loud, because to a novice an unexplained difference in
 * styling reads as inconsistency rather than as meaning.
 */
function eventImpacts(event: HistoricalEvent): string {
  if (!event.impacts?.length) return "";
  const items = event.impacts
    .map((impact) => `<li><p>${impact.text}</p><p class="event-impact-source">${impact.attribution}</p></li>`)
    .join("");
  return `
    <section class="event-act event-impacts">
      <h3 class="event-act-head">Impacts that were noted at the time</h3>
      <p class="event-act-lede">So far, the physics. These are the consequences — and a consequence is a claim about the world that no replay can evidence, so each one names who reported it.</p>
      <ul>${items}</ul>
    </section>
  `;
}

/**
 * The measured case, told in two acts: watch it, then read it.
 *
 * The replay owns its own clock and scrubber, so the milestone list beside it
 * is static prose rather than a second timeline competing with the first for
 * the same visitor. Each act’s lede is the handoff: the first tells the
 * reader how to drive the chart and to read its badges rather than trust its
 * beauty; the second tells them the list is the same storm at reading speed,
 * so the two blocks are one story twice rather than two exhibits.
 */
function eventReplayBody(event: HistoricalEvent): string {
  const milestones = event.milestones
    .map((milestone) => `<li><strong>${milestone.title}</strong><p>${milestone.description}</p></li>`)
    .join("");
  return `
    <section class="event-act">
      <h3 class="event-act-head">Watch it happen</h3>
      <p class="event-act-lede">What follows runs on the storm’s own clock. Where a line is a measurement, the record it came from is named beneath the picture; anything that is a model or a schematic is badged as one. Press Replay, or drag the slider to hold any moment.</p>
      <div data-event-replay></div>
    </section>
    <section class="event-act">
      <h3 class="event-act-head">What happened, in order</h3>
      <p class="event-act-lede">The replay compresses days into moments. This is the same storm at reading speed, one step per link in the chain.</p>
      <ol class="event-milestones">${milestones}</ol>
    </section>
  `;
}

/**
 * The observed footage, framed. `observedImageryBlock` returns finished
 * figures with their own badges and provenance folds; what it cannot know is
 * why the reader is suddenly looking at the Sun, so the act head and lede
 * supply that handoff here. An event with no clips (québec-1989, where no
 * space-based solar observatory existed) keeps the act container for rhythm
 * but takes no heading: its absence figure already carries its own -- "There
 * is no footage of this one" -- and a second head over it would bury the
 * teaching point under scaffolding.
 */
function imageryAct(eventId: string): string {
  const block = observedImageryBlock(eventId);
  if (!block) return "";
  const framed = eventObservedClipCount(eventId) > 0;
  const head = framed
    ? `<h3 class="event-act-head">The Sun, on camera</h3>
      <p class="event-act-lede">This chain began at the Sun, and instruments were watching. The badge over each clip names which one; the time each frame was taken is burned into the frame at source.</p>`
    : "";
  return `
    <section class="event-act">
      ${head}
      ${block}
    </section>
  `;
}

/**
 * The unmeasured case: the milestone stepper, with the drawing removed.
 *
 * What used to sit here was a schematic whose three moving parts were the same
 * for every event and were driven by numbers nobody measured. A picture that
 * cannot distinguish two events is not teaching either of them, so the picture
 * is gone and the milestones -- which are sourced prose -- carry the sequence
 * until this project holds the observations to animate. The old
 * `.event-no-replay` footnote said as much below the controls; that sentence
 * is now the act’s lede, where the reader meets it before the stepper
 * instead of after.
 */
function eventSchematicBody(event: HistoricalEvent): string {
  return `
    <section class="event-act">
      <h3 class="event-act-head">Step through it</h3>
      <p class="event-act-lede">No measured replay is published for this event yet, so nothing here is drawn as data. The stepper walks the documented sequence; the sources at the bottom are the record.</p>
      <div class="event-player-controls"><button data-event-play>Play</button><input data-event-timeline type="range" min="0" max="${event.milestones.length - 1}" value="0" step="1" aria-label="Event milestone" /><span data-event-step>1 / ${event.milestones.length}</span></div>
      <div class="event-caption"><strong data-event-title></strong><p data-event-description></p></div>
    </section>
  `;
}

export function sourcesView(): string {
  return `
    <header class="content-hero">
      <p class="eyebrow">DATA METHOD · VALID TIMES · LIMITATIONS</p>
      <h1>What you are actually seeing.</h1>
      <p>Each layer below separates its scientific input from the way the browser depicts it. Product times are UTC; animation speed and spatial scale are not literal unless explicitly stated.</p>
    </header>
    <section class="evidence-key" aria-labelledby="evidence-key-title">
      <div><p class="section-kicker" id="evidence-key-title">SCIENTIFIC STATUS</p><h2>Read the badge before the picture.</h2></div>
      <div class="evidence-key-items">
        ${Object.entries(EVIDENCE).map(([key, meaning]) => statusKey(key as Evidence, key, meaning)).join("")}
      </div>
    </section>
    <section class="method-section" aria-labelledby="environment-methods-title">
      <div class="method-section-head"><p class="section-kicker">CURRENT ENVIRONMENT</p><h2 id="environment-methods-title">How every live layer is made</h2><p>Open a layer for the calculation, bigmem reduction, visual encoding, and the inference it cannot support.</p></div>
      <div class="method-grid">
        ${methodCard({
          status: "observed",
          label: "Propagated observations + bounded glyphs",
          title: "Solar wind + IMF",
          id: "method-solar-wind",
          summary: "NOAA's propagated Earth-arrival series drives speed, density, pressure, Bz, and the time-varying Shue boundary; moving marks remain visual encodings.",
          data: "NOAA Geospace propagated solar-wind rows retain both their L1 observation time and propagated Earth-arrival valid time. Proton dynamic pressure uses density n and bulk speed V: Pdyn = 1.6726×10⁻⁶ nV² nPa.",
          processing: "bigmem validates and reduces 48 hours at five-minute spacing. Where a matching SWMF frame exists, tracers follow frozen-frame in-plane BATS-R-US bulk-flow projections and local model speed. Otherwise an explicitly illustrative upstream flow changes prominence with observed speed and density and is turned aside around the magnetopause that is actually drawn — the same live Nguyen, Lin and Shue surfaces, offset outward by a fixed display gap — rather than around a sphere. Each tracer's streak is its own streamline's direction; the streak length is a fixed display length and encodes nothing.",
          limitation: "Neither mode is an individual-ion trajectory, a measured 3-D velocity distribution, or recovered magnetic connectivity. Projected SWMF paths are two-dimensional frozen-frame vectors, while fallback glyph locations are illustrative. The gap between the deflecting surface and the drawn boundary is a display offset, not a computed magnetosheath thickness, and the fallback contains no bow shock, no reconnection and no particle transport. Outside the propagated series the layer reports no data rather than holding the current state.",
          url: "https://www.spaceweather.gov/products/solar-wind",
        })}
        ${methodCard({
          status: "observed",
          label: "Observed single scalar + geometric exposure tint + inbound beam",
          title: "Solar X-rays",
          id: "method-xray",
          summary: "GOES 0.1–0.8 nm irradiance is one number, uniform across near-Earth space; the globe shows which hemisphere is currently sunlit, tinted by that number, and a straight parallel beam arriving into it.",
          data: "The long GOES XRS passband provides full-disk soft-X-ray irradiance in W m⁻² and the familiar A/B/C/M/X class, plus a 48-hour trace at five-minute spacing (the published series is rounded to significant figures, not decimal places, since the earlier fixed-decimal rounding quantised background flux to exactly zero).",
          processing: "This flux is measured uniform to 0.056% from geostationary orbit to the ground, so there is no spatial field to paint from it, and an earlier release's field of photon glyphs scattered through the whole scene was deleted for pretending otherwise. Two things are honestly drawable and both are drawn. The day/night division the site already computes for the globe's own lighting becomes a translucent tint over the sunlit hemisphere, coloured and intensified by the measured flux. And the arrival itself is drawn as a beam: parallel rays, straight from beyond the bow shock to the point where each is absorbed on the sunlit upper-atmosphere shell, with the number of rays and their brightness — nothing else — set by the same measured flux. The rays are laid out straight in the drawn scene rather than pushed through the scene's radial compression, which would bend a physically straight ray by up to 45% of the drawn Earth's radius right where it reaches Earth; straightness is the fact being drawn, and the compression is a display scale the site already tells you not to read quantitatively. A newly selected time is applied immediately, with no invented decay or ring-down.",
          limitation: "Neither the tint nor the beam is a photon track, a dose field, or an attenuation model — nothing in near-Earth space attenuates this flux. It is unchanged until it reaches the D-region at 60–90 km, where the D-RAP layer is the drawn consequence. A ray is not an individual photon and its on-screen speed is display cadence, not the speed of light; what the beam claims is direction, straightness, and where the energy stops. The display encodes one measured passband and disappears where the selected time has no source value.",
          url: "https://www.spaceweather.gov/products/goes-x-ray-flux",
        })}
        ${methodCard({
          status: "assimilated",
          label: "Assimilated column TEC",
          title: "GloTEC ionosphere",
          id: "method-tec",
          summary: "NOAA GloTEC total electron content is painted on an offset shell; the readout also reports the median hmF2.",
          data: "GloTEC combines observations with an ionospheric background. The explorer receives the 5° × 2.5° GeoJSON field with TEC, anomaly, hmF2, and observation-count quality information.",
          processing: "bigmem preserves the grid and quality flag. The browser maps TEC to a globe texture; shell height and thickness are exaggerated so the layer remains visible beside satellite orbits.",
          limitation: "TEC is electrons integrated through a column, not a vertical electron-density profile. The shell cannot locate D, E, or F boundaries; hmF2 is the F2 peak height, not the top or bottom of a layer.",
          url: "https://www.spaceweather.gov/products/glotec",
        })}
        ${methodCard({
          status: "forecast",
          label: "Operational time-varying physics-model forecast",
          title: "WAM-IPE peak height + electron density",
          id: "method-ionosphere",
          summary: "NOAA's five-minute HmF2/NmF2 fields give the F2 peak its height and its electron density, and the full 3-D profile supports distinct E and F1 peaks where they actually exist. Read here a place at a time, with the probe, rather than drawn as whole-Earth shells.",
          data: "The ipe05 product supplies 90-longitude × 91-latitude HmF2 and NmF2 grids every five minutes. The complementary ipe10 files supply 90 × 91 × 58 altitude profiles every ten minutes. Electron density in those profiles is the quasi-neutral sum of O+, H+, He+, N+, NO+, O2+, and N2+ density.",
          processing: "bigmem preserves every five-minute HmF2/NmF2 frame and reduces the roughly 22 MB 3-D frames to a coordinate-preserving profile sequence. These surfaces are no longer drawn on the globe: as whole-Earth shells they crowded the picture without telling a reader what it meant for anywhere in particular, and the rail is deliberately capped. The same column is instead read a place at a time — click anywhere on the globe and the probe reports foF2, the F2 peak height, the maximum usable frequency for a chosen path, total electron content and the GNSS range error that follows from it, at the selected UTC. E and F1 are still emitted only for columns with a distinct supported profile maximum; unsupported columns remain holes rather than becoming fixed textbook shells.",
          limitation: "This is a model forecast, not observed or assimilated electron density. WAM-IPE begins at 90 km, so most D-region height and negative-ion chemistry are absent and are not fabricated. E/F1 profile extraction is conservative; a missing distinct peak means no surface at that column. Radial display distance is compressed, but every legend height remains the modeled kilometer value.",
          url: "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wfs/prod/",
        })}
        ${methodCard({
          status: "model",
          label: "Operational forecast, plus an empirical field everywhere else",
          title: "Thermosphere height and satellite drag",
          id: "method-thermosphere",
          summary: "The neutral air a satellite flies through, drawn as the altitude at which it reaches a fixed density — so a storm lifts the surface toward the satellites instead of merely changing a colour.",
          data: "TWO FIELDS, NEVER BLENDED. NOAA's WAM-IPE Forecast System publishes neutral mass density on a 90-longitude × 91-latitude grid at fixed heights from 100 to 1000 km, every ten minutes, in its public wam_fixed_height product, and this release carries hourly frames across the current cycle — about twelve hours of the site's 120-hour timeline. The other nine tenths are NRLMSIS 2.1, evaluated on the same grid at the same nineteen levels, hour by hour, from the 10.7 cm solar radio flux NOAA SWPC publishes and from ap converted out of the very Kp series this site already draws, through Bartels' standard table. That is why the empirical field exists at every instant: an empirical model is a fit driven by indices, not a forecast integrated from an initial condition. The browser prefers NOAA's field wherever NOAA has one, and the badge names which is on screen — MODEL for WAM, EMPIRICAL for NRLMSIS — so the class of evidence changes under the reader's hand rather than silently.",
          processing: "The empirical field is published in six-hour shards and the browser fetches only the shard the clock is inside — 123 hourly frames are 13 MB, and one shard is 425 kB. Its hours sit on whole UTC hours rather than on offsets from the build, so a shard whose drivers have not changed keeps its content hash and never moves between releases. Nineteen of NOAA's ninety-one levels are published, at 30 km through the LEO band, because the layer draws the ALTITUDE of a density level and that altitude is interpolated between levels. Interpolation is linear in log density, which is near-exact for an atmosphere that falls close to exponentially with height; linear in density would overshoot badly across a 30 km step. The surface is placed with the same radial ruler the satellites use, so a satellite inside it really is flying through air at least that dense. Where the chosen density is not crossed inside the published column there is no surface at all, and the hole is counted rather than clamped to the top or bottom of the grid.",
          limitation: "Neither field is a measurement, and neither is assimilated in the thermosphere. NRLMSIS is an empirical fit that is known to under-respond to storms — during the February 2022 Starlink loss it gave about a 25 percent density increase where Swarm-A and GRACE-FO accelerometers measured roughly a doubling — so the nine tenths of the timeline it covers are the WEAKER of the two, and the badge says so rather than letting the reader assume otherwise. Where the two fields meet there is a visible step in the picture. It is left visible: it is the difference between the models, and smoothing it would be an invented field belonging to neither. F10.7A is NOAA's published 90-day running mean standing in for the 81-day mean centred on the day, which cannot be computed in real time because it needs forty days of the future. The drawn level is a display choice, not a physical boundary. Drag on any particular satellite also depends on its mass, cross-section and drag coefficient, none of which this catalogue holds, so density is shown and a decay rate is only ever quoted for a stated reference body.",
          url: "https://www.spaceweather.gov/products/wam-ipe",
        })}
        ${methodCard({
          status: "empirical",
          label: "Derived lower-ionosphere response",
          title: "D-region effective height + density",
          summary: "Below WAM-IPE's 90 km boundary, a separate Wait–Spies surface changes with local solar zenith and the selected-time GOES 0.1–0.8 nm irradiance.",
          data: "The Wait–Spies profile is Ne(h)=1.43×10¹³ exp(−0.15h′) exp[(β−0.15)(h−h′)] m⁻³. Published quiet daytime/nighttime h′ and β values establish the diurnal response; the observationally constrained Thomson/Schmitter flare relations lower dayside h′ and increase profile sharpness from C1 through X45 forcing.",
          processing: "The browser evaluates solar zenith at every surface vertex for the selected UTC. Geometry is effective VLF reflection height h′; color is derived electron density at 74 km. GOES flux outside the published C1–X45 flare domain is visibly flagged and constrained rather than silently extrapolated.",
          limitation: "Effective reflection height is not a hard D-layer boundary or a global chemistry-model analysis. This approximation does not infer flare spectrum, solar energetic-particle, auroral-electron, cosmic-ray, composition, or transport effects. It is kept separate from WAM-IPE and D-RAP.",
          url: "https://doi.org/10.6028/NBS.TN.300",
        })}
        ${methodCard({
          status: "empirical",
          label: "Empirical nowcast · Advanced layer",
          title: "D-RAP HF absorption",
          id: "method-drap",
          summary: "NOAA's Highest Affected Frequency grid shows where current X-rays and solar protons are expected to enhance D-region HF absorption.",
          data: "The global 2° latitude × 4° longitude field reports 1 dB HAF in MHz: the highest frequency expected to lose at least 1 dB on a vertical ground–ionosphere–ground path. The X-ray component uses one-minute GOES 0.1–0.8 nm flux and the proton component uses five-minute GOES proton flux.",
          processing: "bigmem losslessly retains NOAA's 0.1 MHz values, missing cells, valid time, and status messages. The browser chooses the latest nowcast at or before selected UTC, holds it for up to ninety minutes at the live edge, and never interpolates between times. Smooth is bounded spatial bilinear presentation; Native exposes the 2° × 4° cells. NCEI's official archive supports curated history from September 2009.",
          limitation: "D-RAP is not an absorption observation or outage map. It omits auroral-electron absorption, and its vertical two-pass threshold does not solve an oblique link, antenna, margin, mode, noise, or F-region support. It has no future frames; unavailable selected times remain unavailable.",
          url: "https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap",
        })}
        ${methodCard({
          status: "forecast",
          label: "Observation-driven empirical forecast",
          title: "OVATION aurora",
          id: "method-aurora",
          summary: "One official global numeric frame contains both hemispheres, with separate input-observation and forecast-valid times.",
          data: "NOAA's 360 × 181 one-degree grid supplies integer 0–100% viewing probabilities for 90°S–90°N. Zero is a real value and missingness has a separate bit mask. The North and South are both source data; neither is mirrored from the other.",
          processing: "NOAA publicly distributes only the latest native numeric grid. bigmem therefore accumulates exact five-minute snapshots and reports the real available range, every gap, and whether the requested 48 hours are complete. The latest grid may display briefly before its future valid time only as an explicitly labeled active forecast; historical selection remains strict by forecast-valid time. Smooth is spatial presentation only; Native preserves the one-degree grid.",
          limitation: "The public 24-hour animation archive contains rendered JPEGs, not numeric probabilities, and this site does not reverse-engineer them. History before bigmem accumulation and snapshot gaps remain no data. OVATION is not an optical observation; probability assumes darkness and clear viewing, without clouds, terrain, light pollution, or local geometry.",
          url: "https://www.spaceweather.gov/products/aurora-30-minute-forecast",
        })}
        ${methodCard({
          status: "empirical",
          label: "Live-input empirical boundary",
          title: "Magnetopause and exterior cusp",
          summary: "Three published empirical boundaries are recomputed through time from the propagated solar wind: Nguyen et al. (2022) Model 3 for the magnetopause current sheet, Lin et al. (2010) for the cusp inner boundary, and Shue et al. (1998), which carries the tail.",
          data: "Shue: r(θ) = r₀[2/(1+cos θ)]ᵅ, with r₀ = [10.22+1.29 tanh(0.184(Bz+8.14))]Pdyn⁻¹ᐟ⁶·⁶ and α = (0.58−0.007Bz)[1+0.024 ln(Pdyn)] — a function of solar zenith angle and nothing else, so it has no degrees of freedom for cusps at any level of driving. Nguyen (17,230 spacecraft crossings, doi:10.1029/2021JA029776) and Lin (1,482 crossings, doi:10.1029/2009JA014235) add azimuth and an explicit indentation, and are driven by dynamic plus magnetic pressure, IMF Bz, the IMF clock angle and the geodipole tilt. Distances are in Earth radii.",
          processing: "At selected UTC the browser interpolates NOAA's propagated driver samples, derives the clock angle from the interpolated By and Bz and the magnetic pressure from Bt, computes the dipole tilt from the IGRF-13 dipole and the solar position, and evaluates all three surfaces. The shaded funnel is the volume between Lin's boundary and Nguyen's, built only in the directions where Lin's surface genuinely lies inside Nguyen's — which resolves into two lobes straddling the cusp axes near noon, and nothing on the flanks. Neither cusped model is a tail model, so both stop at 120° solar zenith angle and Shue alone continues to the −50 RE cutoff, truncated by a numerical root solve rather than closed with a false cap. Display distance is compressed only after the physical boundaries are evaluated.",
          limitation: "These are empirical fits to spacecraft crossings — not observations of a surface, which nobody measures, and not MHD. Away from the cusps the two fits still differ by of order an Earth radius, and that difference is model spread, not a funnel; it is reported separately in the legend. Shue additionally omits dawn–dusk asymmetry and all cusp structure. None of the three carries bow shock, magnetosheath physics, connectivity, reconnection or ring current. If the selected time has no IMF vector or no dipole tilt, only Shue is drawn and the legend says so; if the drivers are absent entirely, the surfaces disappear instead of becoming static.",
          url: "https://doi.org/10.1029/2021JA029776",
        })}
        ${methodCard({
          status: "model",
          label: "Operational physics-model output",
          title: "NOAA Geospace plasma",
          id: "method-geospace",
          summary: "Actual BATS-R-US density, speed, pressure, and magnetic-field magnitude on equatorial and noon–midnight meridional cut planes.",
          data: "NOAA's coupled operational SWMF configuration uses BATS-R-US, RIM, RCM, and RBE. The public low-latency NOMADS tree exposes adaptive-grid z=0 x-y and y=0 x-z files—not full 3-D cells. bigmem derives |U| and |B| while preserving missing, clipped-low, and clipped-high masks.",
          processing: "The reduction crops X to −55…+25 RE and cross-plane coordinates to ±35 RE, excludes the inner 2.55 RE, and stores coordinates to 0.01 RE. Smooth mode performs gap-aware local interpolation clamped to its contributors; Native exposes unresampled adaptive samples. Raywise density/pressure/velocity transitions provide a bow-shock proxy; a supported current-density ridge provides a magnetopause proxy. Projected B and U lines remain in their source planes, and U tracers use local model speed.",
          limitation: "These are two real 2-D solutions, not a full 3-D volume. A two-cut loft is an explicitly derived cue, not a native isosurface; unsupported sectors remain open. The cuts cannot recover dawn–dusk structure away from their planes, true 3-D connectivity, classified cusps, reconnection topology, or a species-resolved ring current. Selected times outside the compact model sequence return no data.",
          url: "https://www.spaceweather.gov/products/geospace-magnetosphere-movies",
        })}
        ${methodCard({
          status: "model",
          label: "What am I looking at? · Open on demand",
          title: "Two intersecting GSM model cuts",
          summary: "The live geospace shape is two perpendicular sheets through Earth, not a solid plasma object.",
          data: "In Geocentric Solar Magnetospheric coordinates, +X points approximately toward the Sun. NOAA's z=0 x-y plane is the equatorial cut; its y=0 x-z plane is the noon–midnight meridional cut. They intersect along the Sun–Earth/tail X axis, with the modeled tail extending toward −X.",
          processing: "Color on each sheet represents the selected scalar at NOAA's adaptive source cells or a bounded Smooth presentation. Boundary curves, magnetic projections, and flow projections are derived separately from those same sheets. The card stays collapsed until requested so the map remains uncluttered.",
          limitation: "A feature that appears on one sheet is not automatically a three-dimensional shell. The two cuts do not authorize a movable native plane, volume fill, or an inferred value between planes.",
          url: "https://www.spaceweather.gov/products/geospace-magnetosphere-movies",
        })}
        ${methodCard({
          status: "model",
          label: "Historical research lane · Not live",
          title: "Full 3-D SWMF through NASA CCMC",
          summary: "Full-volume BATS-R-US output is publicly obtainable for asynchronous CCMC research runs, but it is not the low-latency operational feed.",
          data: "NASA CCMC Runs-on-Request can retain or generate three-dimensional adaptive-cell density, pressure, velocity, magnetic-field, and current output for a documented model version and requested cadence.",
          processing: "A future historical-event artifact can be reduced on bigmem after a specific run is acquired, recording run ID, grid, cadence, variables, coordinate system, acknowledgements, masks, and support. That separate lane can extract native-volume surfaces and trace three-dimensional vectors without pretending they came from the live two-cut product.",
          limitation: "CCMC access is asynchronous and run-specific. It is not evidence that NOAA's current NOMADS operational tree publishes a downloadable real-time volume, and no full-volume controls appear until a particular run has been acquired and validated.",
          url: "https://ccmc.gsfc.nasa.gov/ror/requests/RoR_Procedure.php",
        })}
        ${methodCard({
          status: "model",
          label: "Coupled pitch-resolved electron model",
          title: "RBE radiation environment",
          id: "method-radiation",
          summary: "The native view is the modeled equatorial electron solution; an optional, separately labeled view maps its pitch-resolved samples along ideal dipole lines.",
          data: "Each NOAA file contains 51 radial × 48 magnetic-local-time × 12 energy × 12 equatorial pitch coordinates. The payload retains all 12 pitch channels for four representative energies. Coordinates use each block's field-line-mapped equatorial radius and MLT, not the uniform source-grid MLT.",
          processing: "MODEL-NATIVE EQUATORIAL FLUX is a continuous indexed contour surface joining only neighboring 51 × 48 radial/MLT source samples. The default PITCH-RESOLVED DIPOLE-MAPPED ELECTRON VOLUME is raymarched: the omnidirectional flux — every locally trapped pitch channel integrated over solid angle, placed off the equator by r=L cos²(λ) and the dipole mirror condition — is accumulated along each view ray, with opacity tracking the local flux so no threshold draws a boundary. It opens with all four published energies folded into one volume by an energy-weighted trapezoidal integral over the 88 keV–2.32 MeV band, divided by the band width so the result stays in the same units and on the same colour scale as a single channel: that is the view in which the two belts and the slot between them are visible with no interaction. Colour runs one fixed 10¹–10⁵·⁵ ramp in every energy view; only opacity is tuned per energy, and each view draws everything above its own inter-belt minimum. Every single energy, every individual pitch channel — and the stacked reconstruction of all of them, which weights each shell by its solid-angle bin — remains selectable, and the legend states which is drawn. Loss-cone channels that reach the RBE inner boundary are excluded. Both views use the fixed 10⁻²…10⁹ log encoding and compressed display distance.",
          limitation: "The mapped view assumes gyrotropy, north/south pitch symmetry, and a centered ideal dipole. It repeats equatorial differential electron flux along mapped bounce shells for visualization; it is not native three-dimensional RBE output, particle density, a BATS-R-US field-line trace, a measured torus, a proton/inner-belt model, shielding calculation, or dose. GOES local particle measurements remain separate.",
          url: "https://ccmc.gsfc.nasa.gov/models/SWMF~RB%3DRBE~20180525/",
        })}
        ${methodCard({
          status: "model",
          label: "Model-derived · computed in a published field, shape not measured",
          title: "Ring current — how it forms",
          id: "method-ring-current",
          summary: "Drift paths of energetic ions in the plasmasphere simulation's own convection field, coloured by the energy they gain being carried inward. An illustration of a mechanism; no ring-current data product exists in any feed this site fetches.",
          data: "No gridded ring-current product is published by any upstream this release reads. The only ring-current measurement carried here is Dst, and its Dessler–Parker–Sckopke energy — one number, no map. What this layer consumes instead is the Volland–Stern convection amplitude A and the driving Kp of the selected DGCPM plasmasphere frame, read off that published artifact rather than recomputed, so the two layers cannot disagree about the electric field they share.",
          processing: "Each drawn particle mirrors at the magnetic equator and feels two drifts. E×B in the published convection-plus-corotation potential, identical for every species and energy. And gradient/curvature drift, purely azimuthal in a dipole, proportional to energy and opposite in sign for the two charges — ions westward, electrons eastward, which is why the net current is westward and why its field opposes Earth's own at the surface. Conservation of the first adiabatic invariant μ = W/B with B = B₀/L³ sets the energy along a path, W ∝ L⁻³, which is what the colour shows. The motion is everywhere perpendicular to ∇(qΦ + μB), so drift paths are contours of that quantity and it is conserved along them; the trajectories are integrated with fourth-order Runge–Kutta and a test pins the conservation. The drawn region ends exactly at the last closed drift path — the Alfvén layer for the selected energy — found by bisecting the seed radius on the midnight meridian. Nothing draws that boundary as a curve: it is the edge of the region, which is the honest way to show a separatrix. Its zero-energy limit is the last closed equipotential, which is the plasmapause the layer above draws. Drift is integrated in physical time and replayed at a fixed 3,600× — an hour of drift per second, so relative speeds between paths are true.",
          limitation: "It is computed, not measured. No flux, no density, no particle count, and no claim about where the real ring current is. No losses at all — charge exchange with the geocorona, Coulomb drag and wave scattering are what really end a ring-current ion's life, so a drawn closed path overstates how long an ion survives on it. No pitch-angle distribution: every particle mirrors at the equator. No self-consistency: these ions neither shield the convection field they drift in nor feed back into the plasmasphere run. No substorm injection event — the field is the steady field of the selected frame's Kp, while a real injection is a transient dipolarisation front. The boundary comes out WIDEST AT DAWN and pinched at dusk — the opposite way round from the cold plasmapause's dusk bulge, and worth stating because reading the two cards together invites the wrong inference. Both are the same arithmetic. A zero-energy particle feels only corotation and convection, and those can cancel only where convection runs westward, which is dusk; that is the plasmapause bulge. Give the particle energy and its gradient/curvature drift adds a westward term everywhere, which at dusk destroys the balance point altogether and at dawn creates one, far out. Measured on this layer's own integrator at Kp 3: widest L 7.58 at 06 MLT and narrowest L 5.31 at 18 MLT for the 10 keV ion, and the same sense at every energy and Kp the layer offers. It is the pinch at dusk that lets tail plasma reach closest to Earth there, which is the mechanism behind the observed dusk-favoured partial ring current — but nothing in this release measures that asymmetry.",
          url: "https://doi.org/10.1029/2000JA000326",
        })}
        ${methodCard({
          status: "observed",
          label: "Local GEO observations",
          title: "GOES energetic particles",
          summary: "Integral proton and electron channels are retained as time-tagged local measurements; the proton channel appears in the operational readout.",
          data: "NOAA GOES measures energetic-particle intensity at the observing geostationary spacecraft. Energy channel, flux, spacecraft, and observation time remain attached.",
          processing: "The values are normalized into the verified weather bundle but do not alter the RBE model field or create a global particle shower.",
          limitation: "A local GEO sample cannot establish flux at an arbitrary LEO, MEO, or GEO spacecraft. Dose additionally requires spectra, directionality, shielding, material response, and a transport model.",
          url: "https://www.spaceweather.gov/products/goes-electron-flux",
        })}
        ${methodCard({
          status: "observed",
          label: "Published record",
          title: "Ground stations",
          id: "method-ground-stations",
          summary: "Where the antennas are, and which spacecraft their operators say they serve.",
          data: "A hand-authored table of civil, scientific and commercial ground stations, each row carrying the operator publication it came from and a precision class for its coordinate. Three tiers are present and are labeled rather than averaged: survey-grade positions quoted to 3 cm, ordinary published positions good to about a metre, and rows a publisher gave only to degrees and minutes, which are kilometres wide. Where a publisher deliberately reduced a position to protect a home address, that is recorded and never improved upon.",
          processing: "Links are joined to the displayed catalog by NORAD catalog ID. Passes and dwell are SGP4 through satellite.js, bisected to one second at each horizon crossing, on the same geometric elevation mask as the coverage footprint. Deep Space Network positions are the geodetic values from the published handbook, not the geocentric latitudes in NASA's own machine-readable configuration feed, which place every complex about 20 km toward the equator on an ordinary map.",
          limitation: "Not a census of ground stations, and nothing here is inferred: a relationship an operator has not published is absent rather than estimated. Where no position has been published, the station is absent rather than borrowed from a wiki. Pass times are geometric visibility, not scheduled contacts, and are not corrected for terrain, refraction or antenna pattern.",
          url: "https://sean.theinformed.org/space/",
        })}
        ${methodCard({
          status: "forecast",
          label: "Operational NOAA products",
          title: "R / S / G conditions + outlook",
          summary: "Current NOAA scales, rolling 24-hour maxima, recent bulletins, daily event probabilities, Ap probabilities, and three-hour Kp forecasts are formatted without a language model in the data path.",
          data: "bigmem retrieves NOAA's scale JSON, recent-message JSON, plain-language 3-Day Forecast, detailed 3-Day Geomagnetic Forecast, and planetary Kp forecast. Every product retains its own issue or valid time.",
          processing: "A deterministic, tested parser preserves NOAA zeros and nulls, keeps Kp observed/estimated/predicted status, extracts forecaster rationales, and publishes a compact versioned object. Recent bulletin text is retained verbatim and explicitly labeled as not necessarily active.",
          limitation: "Daily R probabilities do not predict an exact flare onset, blackout footprint, duration, or local link outage. Recent messages may be expired, extended, superseded, or canceled. Separately issued NOAA products can briefly disagree and are never silently blended into one false timestamp.",
          url: "https://www.spaceweather.gov/products/3-day-forecast",
        })}
      </div>
    </section>
    <section class="processing-ledger" aria-labelledby="processing-ledger-title">
      <div><p class="section-kicker">COMPUTE BOUNDARY</p><h2 id="processing-ledger-title">Heavy science stays on bigmem.</h2></div>
      <div class="processing-facts">
        <article><strong>≈22 MB</strong><span>Each operational WAM-IPE NetCDF source frame</span></article>
        <article><strong>1.31–1.45 MB</strong><span>Each current NOAA adaptive SWMF cut before reduction</span></article>
        <article><strong>≈60 MB/day</strong><span>Typical official D-RAP daily archive retained on bigmem only</span></article>
        <article><strong>5 min / 20 min / 4 h</strong><span>WAM-IPE peak surfaces / SWMF samples / reduced 3-D profiles</span></article>
      </div>
      <p>bigmem performs discovery, validation, NetCDF and adaptive-grid parsing, cropping, derived-field calculation, mask preservation, quantization, history accumulation, compression, and release assembly. The VPS serves immutable files; a visitor's device lazy-loads, decodes, interpolates only where the data contract permits, and draws the selected compact layer. GPU acceleration can reduce an acquired CCMC volume, but it cannot recover dimensions absent from the live operational product.</p>
    </section>
    <section class="method-section" aria-labelledby="catalog-sources-title">
      <div class="method-section-head"><p class="section-kicker">CATALOG + BASE MAP</p><h2 id="catalog-sources-title">Other authoritative inputs</h2></div>
      <div class="source-grid">
        ${source("Space-Track orbital elements", "Space-Track supplies the OMM mean elements. Browser positions are SGP4 predictions, not telemetry or conjunction-quality ephemerides.", "https://www.space-track.org/documentation")}
        ${source("CelesTrak catalog curation", "Optional operational status and mission/category membership; not the orbital-elements source.", "https://celestrak.org/satcat/")}
        ${source("Natural Earth", "Public-domain 1:110m land geometry used to draw the self-hosted globe without a metered map-tile service.", "https://www.naturalearthdata.com/")}
      </div>
    </section>
    <aside class="teaching-callout"><strong>What is still not a live volume</strong>WAM-IPE is a genuine three-dimensional ionosphere model. The live SWMF product is different: it remains two perpendicular magnetosphere cuts. Bow-shock and magnetopause lofts are visibly labeled two-cut proxies, and there is no fabricated native 3-D cusp, magnetic connectivity, plasmasphere, species-resolved ring-current volume, or proton belt. Full 3-D CCMC research runs belong to separately sourced historical artifacts.</aside>
    <aside class="teaching-callout"><strong>Combined does not mean simultaneous</strong>Solar-wind observations, GloTEC assimilation, OVATION forecasts, SWMF runs, RBE solutions, and orbital elements carry different valid times. Co-display is contextual; inspect the visible timestamps before relating fine-scale structures.</aside>
    <aside class="teaching-callout"><strong>No data is a scientific result</strong>If the selected UTC lies before accumulated history, after a product's usable endpoint, or inside a cache gap, that layer disappears and explains the unavailable interval. The explorer does not freeze today's field, sample a rendered image, or invent a forecast to keep the globe full.</aside>
    <aside class="teaching-callout"><strong>Operational boundary</strong>The site may display current public observations and let users export them, but it is not an official warning service, spacecraft-command system, collision-assessment tool, navigation source, dose calculator, or communications-planning authority. Follow NOAA SWPC and the responsible operational organization for decisions.</aside>
  `;
}

type MethodCard = {
  status: "observed" | "assimilated" | "model" | "empirical" | "composite" | "forecast" | "schematic";
  label: string;
  title: string;
  summary: string;
  data: string;
  processing: string;
  limitation: string;
  url: string;
  /**
   * Anchor for the operational panel's "How this is built" link. A layer whose
   * card carries one can be jumped to directly, which is what lets the layer's
   * essay leave the globe view entirely instead of merely folding up there.
   * `LAYER_METHOD_CARD_IDS` in `main.ts` is the other half of this contract.
   */
  id?: string;
};

function methodCard(card: MethodCard): string {
  return `<details class="method-card"${card.id ? ` id="${card.id}"` : ""}>
    <summary>${evidenceBadge(card.status)}<small class="layer-status-note">${card.label}</small><strong>${card.title}</strong><small>${card.summary}</small></summary>
    <div class="method-card-body">
      <dl>
        <div><dt>Scientific input</dt><dd>${card.data}</dd></div>
        <div><dt>bigmem + display method</dt><dd>${card.processing}</dd></div>
        <div><dt>Do not infer</dt><dd>${card.limitation}</dd></div>
      </dl>
      <a href="${card.url}" target="_blank" rel="noreferrer">Open authoritative source ↗</a>
    </div>
  </details>`;
}

function statusKey(status: MethodCard["status"], _label: string, description: string): string {
  return `<div>${evidenceBadge(status)}<small>${description}</small></div>`;
}

function source(title: string, body: string, url: string): string {
  return `<article class="source-card"><span class="section-kicker">SOURCE</span><h2>${title}</h2><p>${body}</p><a href="${url}" target="_blank" rel="noreferrer">Open authoritative source ↗</a></article>`;
}

/**
 * "Now" — the current space-weather awareness page.
 *
 * The site had all of NOAA's operational material and no single place that
 * answered "what is happening right now, and what is coming". The scales and
 * the three-day outlook were behind a button in the rail; the Kp series — 81
 * three-hourly rows, seven days behind and three ahead — was ingested in full
 * and then collapsed to one number per day. This is the one home for all of it.
 *
 * The shell is markup only. The NOAA panels are MOVED into `#now-swpc-mount`
 * from where they already live rather than copied, which is the same technique
 * the layer cards use for their control panels: one copy in the document, so
 * the two surfaces can never drift apart or disagree, and every listener bound
 * at startup survives the move.
 */
export function currentConditionsView(): string {
  return `
  <!-- The hero is deliberately short. What used to be here was a 74 px
       headline and four lines of preamble, which pushed every published
       number below the fold: the NOAA scales were about fifteen hundred
       pixels down. The headline is now one line, the sentence under it is
       the actual state of the system rather than a description of the page,
       and the board below it starts inside the first screen. -->
  <section class="content-hero now-hero">
    <span class="section-kicker">RIGHT NOW</span>
    <h1>Current space weather</h1>
    <p class="now-verdict" id="now-verdict">Reading the published indices…</p>
  </section>

  <!-- CONDITIONS AT A GLANCE. Three NOAA scales and five drivers, every one
       of them carrying its own evidence badge, and every one of them drawn
       as well as printed. A tile with nothing published draws no line and
       says so; see src/conditions-board.ts for why that rule is absolute. -->
  <section class="now-board" aria-labelledby="now-board-title">
    <h2 class="sr-only" id="now-board-title">Conditions at a glance</h2>
    <div class="now-scales" id="now-scales"></div>
    <p class="now-scale-conflict" id="now-scale-conflict" hidden></p>
    <div class="now-drivers" id="now-drivers"></div>
    <p class="now-board-foot" id="now-board-foot"></p>
  </section>

  <section class="now-section" aria-labelledby="now-kp-title">
    <div class="now-section-head">
      <div><span class="section-kicker">PLANETARY K INDEX &middot; THREE-HOUR</span><h2 id="now-kp-title">Seven days behind, three ahead</h2></div>
      <small id="now-kp-summary">—</small>
    </div>
    <figure class="now-figure">
      <svg id="now-kp-chart" class="now-kp-chart" viewBox="0 0 320 132" role="img" aria-labelledby="now-kp-title" aria-describedby="now-kp-summary"></svg>
      <!-- Two keys, because the bars carry two independent facts. HOW a bar is
           drawn is its evidence class; WHAT COLOUR it is, is its NOAA G level,
           on the same green/amber/red the R S G tiles above use. The old key
           had one list and three cyan swatches, which said observed bars are
           cyan — untrue the moment one reaches G1 and turns amber. -->
      <figcaption>
        <span class="now-key"><i class="now-swatch is-observed"></i>Observed</span>
        <span class="now-key"><i class="now-swatch is-estimated"></i>Estimated</span>
        <span class="now-key"><i class="now-swatch is-predicted"></i>NOAA forecast</span>
        <span class="now-key now-key-levels"><i class="now-key-level g0">G0</i><i class="now-key-level g1">G1-2</i><i class="now-key-level g3">G3+</i></span>
      </figcaption>
    </figure>
    <p class="now-note" id="now-kp-limitation"></p>
  </section>

  <div id="now-swpc-mount" class="now-swpc"></div>

  <section class="now-section">
    <div class="now-section-head"><div><span class="section-kicker">OFFICIAL PRODUCTS</span><h2>Go to the source</h2></div></div>
    <p class="now-note">This page reformats NOAA's published values for reading; it never changes them.
    For an official warning decision, use NOAA SWPC directly.</p>
    <div class="now-links">
      <a href="https://www.spaceweather.gov/products/3-day-forecast" target="_blank" rel="noreferrer">Official 3-day forecast ↗</a>
      <a href="https://www.spaceweather.gov/products/3-day-geomagnetic-forecast" target="_blank" rel="noreferrer">Official geomagnetic forecast ↗</a>
      <a href="https://www.spaceweather.gov/products/planetary-k-index" target="_blank" rel="noreferrer">Planetary K index ↗</a>
      <a href="https://www.spaceweather.gov/products/notifications-timeline" target="_blank" rel="noreferrer">Watches, warnings and alerts ↗</a>
    </div>
  </section>

  <!-- THE CODA, AND WHY IT IS LAST.

       This section spent its life as the SECOND thing on the page, directly
       under the Kp chart and above every NOAA product. That position was
       chosen for a real reason — Kp is what squeezes the plasmapause, so the
       boundary was put beside its driver — but position on a page is a claim
       about importance, and this one could not carry it:

       • Nothing here is acted on. Current conditions answers "what is
         happening and what should I do about it". No watch, warning or alert
         is keyed to the plasmapause, and no decision changes because of it.
         Position two said otherwise.
       • It is the only MODELLED thing on a page of measurements. Everything
         above is NOAA-observed or NOAA-forecast; this is a DGCPM simulation
         run on measured Kp. Ranking our own arithmetic above NOAA's published
         products inverts the page's own evidence order.
       • It still belongs on this page. The grain cloud left the globe on
         2026-08-18 and this chart is now the site's ONLY picture of the
         plasmasphere; the layer page points here for it by name. And the
         teaching link is real: the Kp that erodes the boundary is plotted on
         this same page, which no layer page can reproduce.

       So it stays, at the foot, after the reader has been given the
       operational answer and the official source — marked as a teaching extra
       and as MODEL, so the "this page reformats NOAA's published values"
       sentence above cannot be read as covering it. -->
  <section class="now-section now-coda" aria-labelledby="now-plasmapause-title">
    <div class="now-section-head">
      <div>
        <span class="section-kicker">TEACHING EXTRA &middot; NOT A WARNING PRODUCT</span>
        <h2 id="now-plasmapause-title">What that Kp is doing to the cold plasma <i class="layer-status model">MODEL</i></h2>
      </div>
    </div>
    <p class="now-lede">The plasmasphere is cold plasma that has leaked out of the ionosphere and
    been trapped, corotating with the Earth. Its outer edge — the plasmapause — is squeezed inward by
    the same activity the Kp chart above plots, which is why the two share a page. Nothing else on
    this page depends on it: it is simulation output, not a warning product, and it is here to be
    understood rather than acted on.</p>
    <div id="now-plasmapause"></div>
    <div class="now-links">
      <button type="button" data-plasmapause-layer-page>The plasmasphere, one page &rarr;</button>
    </div>
  </section>`;
}
