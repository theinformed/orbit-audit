/**
 * "How this was built" content view.
 *
 * Four things live here, and none of them belong on the per-layer Data & methods page:
 *   1. provenance — the named product behind each layer, its cadence, its latency, its real
 *      coverage window, and the sentence saying what it is not;
 *   2. the architecture decisions, with the measurement that forced each one;
 *   3. the notebook — defects found, and what each one turned out to be teaching;
 *   4. a dated corrections log, including claims this site has withdrawn.
 *
 * Data & methods (`sourcesView()` in src/content.ts) holds the full scientific contract for each
 * layer; Connections (`connectionsView()` in src/connections.ts) holds the physics links and the
 * scientific credit. This module deliberately does not repeat either. Every number below was taken
 * from a measurement recorded in this repository — the commit that made the fix, the audit that
 * counted it, or the design document that pinned the source — and figures quoted from published
 * papers are restated exactly as src/connections.ts carries them, against the same DOIs.
 *
 * Static markup only. No runtime data, no new CSS, no imports. Every class used here already
 * exists in src/styles.css: content-hero, eyebrow, teaching-callout, method-section,
 * method-section-head, section-kicker, method-grid, method-card, method-card-body, layer-status,
 * processing-facts, source-grid, source-card.
 *
 * WIRING — three lines, exactly as src/connections.ts was wired, in files this module does not
 * touch:
 *
 *   index.html, in the <nav> beside the other .nav-item buttons:
 *     <button class="nav-item" data-view="methods" data-mobile-label="Build">How this was built</button>
 *
 *   src/main.ts, with the other content-view imports:
 *     import { methodsView } from "./methods";
 *
 *   src/main.ts, inside ExplorerApp.openContent(), beside the other view branches:
 *     else if (view === "methods") body.innerHTML = methodsView();
 *
 * Note for whoever wires it: the [data-view] click handler is bound once at start-up, so a
 * data-view button injected into #content-body by this module would never fire. That is why this
 * page refers to the other views by name in prose rather than linking to them with a button.
 */

type EvidenceClass = "observed" | "assimilated" | "model" | "empirical" | "forecast" | "schematic";

type Card = {
  status: EvidenceClass;
  chip: string;
  title: string;
  summary: string;
  rows: { term: string; detail: string }[];
  link?: { label: string; url: string };
};

/* ------------------------------------------------------------------ 1. PROVENANCE */

const PROVENANCE: Card[] = [
  {
    status: "observed",
    chip: "Observed at L1 · propagated to Earth by a model step",
    title: "Solar wind and interplanetary magnetic field",
    summary:
      "Measured a million and a half kilometres upstream, then moved to Earth arrival by a calculation — so every row carries two different times.",
    rows: [
      {
        term: "Product and cadence",
        detail:
          "NOAA SWPC real-time solar wind. The two files the site reads — rtsw_wind_1m.json and rtsw_mag_1m.json — carry every L1 monitor SWPC is receiving, not only the one it has nominated active; on 2026-08-08 that was SOLAR1, ACE and IMAP, three independent platforms, at a 60-second median cadence per spacecraft.",
      },
      {
        term: "Latency",
        detail:
          "4.4 to 6.4 minutes behind the wall clock, measured. NOAA's propagated Earth-arrival series adds its own model step on top of that, which is why each row keeps both an L1 observation time and a propagated valid time. They are different on purpose and the readout shows both.",
      },
      {
        term: "What is done to it here",
        detail:
          "48 hours are validated and reduced to five-minute spacing on bigmem. Proton dynamic pressure is computed as Pdyn = 1.6726×10⁻⁶ n V² nPa and feeds the magnetopause boundary. Nothing is published until it clears the corroboration guard described in the notebook below.",
      },
      {
        term: "Coverage you can actually scrub",
        detail:
          "A rolling 48 hours. If the guard fires, the plotted history is truncated at the fault onset and the derived quantities are withheld rather than carried forward from the last healthy row.",
      },
      {
        term: "What it does not establish",
        detail:
          "Nothing here observes the Sun. This layer starts at NOAA's already-propagated series; no coronal mass ejection is propagated from the Sun on this site. The moving marks are not tracked ions and imply no gyro-orbit.",
      },
    ],
    link: { label: "NOAA real-time solar wind ↗", url: "https://www.swpc.noaa.gov/products/real-time-solar-wind" },
  },
  {
    status: "observed",
    chip: "Observed · one instrument, one passband",
    title: "GOES soft X-ray irradiance",
    summary: "A single measured number per minute, which is why it is the most trustworthy thing on the globe.",
    rows: [
      {
        term: "Product and cadence",
        detail: "GOES XRS 0.1–0.8 nm full-disk irradiance in W m⁻², one-minute upstream, retained here at five-minute spacing.",
      },
      { term: "Latency", detail: "Minutes. X-rays cross 1 AU in about eight, so this layer is close to the shortest possible chain between an event and a picture." },
      {
        term: "What is done to it here",
        detail:
          "A logarithmic sample at the selected UTC drives glyph count, opacity and the dayside upper-atmosphere response, and it is the same sample that drives the empirical D-region surface. The class letter is derived from that flux, not fetched separately.",
      },
      { term: "Coverage", detail: "A rolling 48 hours. There are no future frames; a selected time past the newest sample simply has no value." },
      {
        term: "What it does not establish",
        detail:
          "Glyphs are irradiance cues, not detected photons, trajectories or a dose field. One passband is not a spectrum, and irradiance is not a blackout map — that is a different layer with a different evidence class.",
      },
    ],
    link: { label: "GOES X-ray flux ↗", url: "https://www.spaceweather.gov/products/goes-x-ray-flux" },
  },
  {
    status: "forecast",
    chip: "Forecast · a physics model, four cycles a day",
    title: "WAM-IPE ionospheric peaks",
    summary: "The E, F1 and F2 surfaces are a numerical model's opinion, and the schedule that produces them is visible in the data.",
    rows: [
      {
        term: "Product and cadence",
        detail:
          "NOAA/NCEP's Whole Atmosphere Model–Ionosphere Plasmasphere Electrodynamics forecast system. The ipe05 peak product supplies 90 × 91 HmF2 and NmF2 grids every five minutes; ipe10 supplies 90 × 91 × 58 ion-density profiles every ten minutes. The system runs four cycles a day, each producing 51 hours of output.",
      },
      {
        term: "Latency",
        detail:
          "About 3¼ hours between a cycle's nominal time and its files appearing. That is the model's own schedule, not a slow download, and it is the same lag the thermosphere products carry.",
      },
      {
        term: "What is done to it here",
        detail:
          "Electron density is the quasi-neutral sum of seven published positive-ion densities. Roughly 22 MB per 3-D frame is reduced to a coordinate-preserving 45 × 46 × 30 sample with a separate validity mask. E and F1 surfaces are published only where a genuine distinct profile maximum exists; the published E/F1 frames are selected at four-hour cadence from a much larger sequence, so they move far more slowly than F2.",
      },
      {
        term: "Coverage",
        detail: "Accumulated history plus the current cycle's forecast endpoint. The browser interpolates only between bracketing model frames and hides the surface outside them.",
      },
      {
        term: "What it does not establish",
        detail:
          "This is neither observed nor assimilated electron density. Quasi-neutral summation is itself a modelling assumption, and there is no published negative-ion field. The model begins at 90 km, so the D region below it is a separate, explicitly empirical surface rather than a downward extrapolation.",
      },
    ],
    link: { label: "NOAA WFS operational tree ↗", url: "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wfs/prod/" },
  },
  {
    status: "assimilated",
    chip: "Assimilated · observations on a background model",
    title: "GloTEC total electron content",
    summary: "The only layer here that is genuinely observations and a model combined — and the only one whose absence stops the whole publish.",
    rows: [
      { term: "Product and cadence", detail: "NOAA GloTEC, a 5° × 2.5° GeoJSON field carrying TEC, anomaly, hmF2 and an observation-count quality flag. Frames arrive on a ten-minute grid." },
      { term: "Latency", detail: "Minutes. It is an operational assimilative nowcast, not a forecast." },
      { term: "What is done to it here", detail: "The grid and the quality flag are preserved unchanged; layer opacity is modulated by source quality so thinly-observed regions look thinly observed." },
      {
        term: "Coverage",
        detail:
          "Rolling. One honest wart: NOAA has twice served a literal empty index (both on 2026-08-07), and an empty GloTEC index currently aborts the entire publish cycle — blocking fresh satellite, magnetosphere, aurora and absorption data that were all perfectly good. Aurora and D-RAP degrade gracefully instead. Making GloTEC behave like its siblings changes what the site publishes when a layer is missing, which is a scientific presentation decision and not a bug fix, so it is written down rather than quietly changed.",
      },
      {
        term: "What it does not establish",
        detail:
          "TEC is electrons integrated through a whole column. It cannot locate the D, E or F boundaries, cannot give a vertical profile, and cannot give electron density at a spacecraft. Three layers on this globe answer three different questions about the ionosphere and their legends are deliberately not interchangeable.",
      },
    ],
    link: { label: "NOAA GloTEC ↗", url: "https://www.spaceweather.gov/products/glotec" },
  },
  {
    status: "empirical",
    chip: "Empirical nowcast · exact frames only",
    title: "D-RAP HF absorption",
    summary: "A published empirical relationship between measured flux and expected radio absorption — not a report of what any radio actually did.",
    rows: [
      { term: "Product and cadence", detail: "NOAA D-RAP, the 1 dB Highest Affected Frequency in MHz on a 2° latitude × 4° longitude grid. Its X-ray component uses one-minute GOES flux; its proton component uses five-minute GOES protons." },
      { term: "Latency", detail: "Minutes, and it is a nowcast: there are no future frames at all." },
      // CORRECTNESS FIX 2026-09-04: "at most 12 minutes" has not been the
      // live-edge rule since `DRAP_LIVE_EDGE_HOLD_MINUTES = 90` landed. The
      // artifact's 12-minute staleness now only fires when a NEWER frame
      // exists — a cache gap — and at the live edge, which is where a reader
      // normally is, the newest frame is held for up to 90 minutes to ride out
      // NOAA's routine 30-60 minute publication lag. Both numbers are
      // deliberate; only one of them was written down.
      { term: "What is done to it here", detail: "NOAA's 0.1 MHz values, missing cells, valid time and status messages are retained losslessly. The browser selects an exact frame at or before the selected UTC and never interpolates between times. Across a gap with a newer frame on the far side it holds a frame for at most 12 minutes; at the live edge it holds the newest frame for up to 90 minutes, which rides out NOAA's routine publication lag, and then the layer goes empty rather than stale." },
      {
        term: "Coverage",
        detail:
          "Accumulated frames only. NCEI's official archive would support history back to September 2009, but it runs to roughly 60 MB a day and ordinary releases do not download it, so times before this site's own accumulation are a gap and are drawn as one.",
      },
      {
        term: "What it does not establish",
        detail:
          "It is not an absorption measurement and not an outage map. It solves a vertical ground–ionosphere–ground path, so it says nothing about a specific oblique link, antenna, mode, margin or noise floor, and it omits auroral-electron absorption entirely.",
      },
    ],
    link: { label: "NOAA D-RAP ↗", url: "https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap" },
  },
  {
    status: "forecast",
    chip: "Forecast · read this badge before you read the picture",
    title: "OVATION auroral oval",
    summary:
      "The green oval is the layer visitors most often mistake for an observation. It is a forecast of viewing probability, and in May 2024 this class of model was beaten by the public.",
    rows: [
      {
        term: "Product and cadence",
        detail:
          "NOAA OVATION 2020. One numeric frame is a 360 × 181 one-degree global grid holding integer 0–100% viewing probability for both hemispheres at once — neither oval is mirrored from the other. Two times are preserved separately: the upstream observation time and the forecast-valid time at Earth. Snapshots are taken every five minutes.",
      },
      { term: "Latency", detail: "The product is valid ahead of its inputs by construction. Selection here is strictly by forecast-valid time." },
      {
        term: "What is done to it here",
        detail:
          "NOAA's public numeric endpoint is latest-only, so bigmem accumulates exact snapshots to build any history at all. NOAA's 24-hour animations are rendered JPEGs; this site does not read numbers back out of pictures. A 1% product floor is drawn transparent so it does not cover half the globe, and genuine higher-probability cells in both hemispheres stay visible.",
      },
      {
        term: "Coverage",
        detail:
          "History begins where this site's own accumulation began, and every snapshot gap is a real gap. There is no aurora data here for May 2024 or any other past storm, and the site says so rather than showing the newest frame at a historical time.",
      },
      {
        term: "What it does not establish",
        detail:
          "It is not an observation of light in the sky. Probability assumes dark, clear skies and represents no cloud, daylight, terrain or light pollution. Grandin et al. (2024) turned 696 public reports into a citable result showing aurora at geomagnetic latitudes between 30 and 60 degrees in May 2024 — significantly further equatorward than the oval models predicted.",
      },
    ],
    link: { label: "Grandin et al. 2024, Geosci. Commun. 7, 297–316 ↗", url: "https://doi.org/10.5194/gc-7-297-2024" },
  },
  {
    status: "empirical",
    chip: "Empirical · an equation fitted to past boundary crossings",
    title: "Shue magnetopause",
    summary: "Two published expressions, evaluated on live drivers. It is neither a measurement nor a simulation, and it is the layer with the largest gap between how convincing it looks and what it knows.",
    rows: [
      { term: "Product and cadence", detail: "Shue et al. (1998), evaluated at every selected time from NOAA's propagated proton dynamic pressure and GSM IMF Bz on a five-minute driver series." },
      { term: "Latency", detail: "Whatever the solar-wind layer's is. This surface has no independent source." },
      {
        term: "What is done to it here",
        detail:
          "r₀ and the flaring exponent are recomputed from the bracketed driver sample, the surface is revolved in physical Earth radii, and only then is display compression applied. The open tail is truncated where XGSM reaches about −50 RE with no false cap, and the magnetotail carries a further disclosed display stretch to stay legible.",
      },
      { term: "Coverage", detail: "It disappears when drivers are absent, or when the corroboration guard withholds them. It never freezes at its last value." },
      {
        term: "What it does not establish",
        detail:
          "It is axisymmetric. It has no cusps, no dawn–dusk asymmetry, no bow shock, no magnetosheath and no ring current — and dawn–dusk asymmetry is exactly what was measured in the May 2024 electron dropouts. A quiet-frame cross-check against a magnetohydrodynamic run's own current layer agreed to 3.4%; under compression the two should diverge, and that divergence is the teaching content rather than a defect.",
      },
    ],
    link: { label: "Shue et al. 1998, JGR 103, 17691 ↗", url: "https://doi.org/10.1029/98JA01103" },
  },
  {
    status: "model",
    chip: "Model · two planes and a phase-space solution",
    title: "NOAA geospace cuts and the radiation-belt model",
    summary: "The magnetosphere product is two perpendicular sheets through Earth. The belts are a model's electron phase space, mapped onto ideal dipole shells for display.",
    rows: [
      {
        term: "Product and cadence",
        detail:
          "NOAA's operational Space Weather Modeling Framework configuration: BATS-R-US z = 0 and y = 0 GSM cuts, with the coupled Radiation Belt Environment solution on a 51 radial × 48 magnetic-local-time × 12 energy × 12 pitch grid. Common model frames arrive about every 20 minutes.",
      },
      { term: "Latency", detail: "Operational, minutes to tens of minutes. RBE snaps to the nearer surrounding frame and never interpolates through time, even while the retained scalar cuts can blend — so the legend reports the RBE frame time, not the blend time." },
      {
        term: "What is done to it here",
        detail:
          "The cuts are cropped, masked and reduced; the public checkbox for them is currently hidden. Four representative energies are retained (about 88 keV, 453 keV, 1.35 MeV and 2.32 MeV) with all 12 pitch channels each. Both belt views cut at a disclosed display window — L ≥ 1.2 RE and differential flux ≥ 10¹ — because the model's grid reaches inward to its own ionospheric boundary at 1.0157 RE, which is thermosphere and not belt.",
      },
      { term: "Coverage", detail: "The published sequence only. Outside it, both layers report before- or after-coverage and hide." },
      {
        term: "What it does not establish",
        detail:
          "Two cut planes are not a volume, and anything that looks like a surface between them is an explicitly derived cue. The filled belt view repeats equatorial differential flux along mapped bounce shells under stated assumptions — an ideal centred dipole, gyrotropy, north–south symmetry. It is a way of seeing where the flux would be. It is not a measured torus, not a proton model, and not dose.",
      },
    ],
    link: { label: "NOAA geospace model ↗", url: "https://www.spaceweather.gov/products/geospace-magnetosphere-movies" },
  },
  {
    status: "model",
    chip: "Model · fitted parameters, not telemetry",
    title: "Orbital elements, and why every satellite here is a prediction",
    summary:
      "This is the thing most satellite maps let you assume. Nothing on this globe is tracking a spacecraft. Every dot is an analytic propagator run forward from a set of fitted numbers.",
    rows: [
      {
        term: "Product and cadence",
        detail:
          "Mean orbital elements in Orbit Mean-Elements Message form from space-track.org, filtered by CelesTrak's SATCAT operational curation. Elements are collected hourly, at minute :17 to :23 — the upstream requires a minute that is neither the top nor the bottom of the hour — and the catalogue metadata once a day after 1700Z.",
      },
      {
        term: "Latency",
        detail:
          "About four hours between a fitted epoch and its arrival in the catalogue. Element sets do not arrive smoothly: roughly 25,000 a day, delivered in bursts. In one measured 24-hour snapshot only 40 objects carried an epoch under three hours old, against 12,420 in the four-to-seven-hour bin.",
      },
      {
        term: "What is done to it here",
        detail:
          "15,680 objects are reduced to the 8,000 the teaching catalogue carries, and every position you see is computed by SGP4 in your own browser at the time you selected. Nothing is precomputed. The redistribution position is settled: USSPACECOM grants express blanket approval for transfer of basic Space Situational Awareness data conditioned on appropriate citation, and names these products as such, so the citation travels with the data.",
      },
      {
        term: "Coverage",
        detail:
          "Current elements are always available; the site's own element-history archive began in August 2026, so it holds nothing from May 2024 or any earlier storm and cannot re-derive anyone else's published numbers.",
      },
      {
        term: "What it does not establish",
        detail:
          "A mean element set is not a measurement of where anything is. It is a set of parameters fitted so that one specific analytic propagator reproduces tracking data — so the elements and the propagator are a matched pair, and using either alone is meaningless. Prediction error grows with epoch age, fastest for low perigees during a storm, which is precisely the effect that makes decaying orbits a density instrument. Read the epoch age on the card. This is not a conjunction-assessment or operations ephemeris. Median epoch age is the statistic worth quoting: a couple of deep highly-elliptical objects legitimately carry forward-dated epochs, which makes a naive \"newest age\" read negative.",
      },
    ],
    link: { label: "CelesTrak GP data formats ↗", url: "https://celestrak.org/NORAD/documentation/gp-data-formats.php" },
  },
];

/* --------------------------------------------------------------- 2. ARCHITECTURE */

const ARCHITECTURE: Card[] = [
  {
    status: "model",
    chip: "Measured · 0.8 MB against 138 MB",
    title: "Orbits are propagated in your browser because elements are a compact complete representation",
    summary: "Not a compute argument. SGP4 is cheap on any machine. It is a representation argument, and the numbers are decisive.",
    rows: [
      {
        term: "The measurement",
        detail:
          "0.8 MB gzipped carries all 8,000 objects at <em>any</em> instant. Precomputing positions instead costs 138 MB per publish cycle at five-minute sampling and 691 MB at one-minute — and every byte of it would have to be regenerated every five minutes, forever.",
      },
      {
        term: "The part that settles it",
        detail:
          "Precomputed positions also kill the time scrubber. Scrubbing needs positions at arbitrary times on demand, not at whichever times a server happened to sample. A compact complete representation answers any time; a large sampled one answers only the times someone chose in advance.",
      },
      {
        term: "The consequence you can see",
        detail:
          "Your device does real orbital mechanics. That is why the epoch-age warning matters, why a mobile device propagates a reduced subset, and why the whole catalogue survives a five-minute republish without a reload — the new bundle is fetched before the one in hand is discarded, so a transient network failure leaves a working layer untouched.",
      },
    ],
  },
  {
    status: "observed",
    chip: "A legal boundary, enforced in code",
    title: "Two upstreams, two machines, and neither script will run on the wrong one",
    summary: "The split is not a preference or a performance choice. Crossing the wires would put a personal credential behind a commercial entity.",
    rows: [
      {
        term: "The boundary",
        detail:
          "space-track.org is reached only from the home workstation, under a personal account held by a serving officer, with credentials at mode 0600 that are never in git and never on the server. CelesTrak is reached only from the public server, which operates under a company. Both ingest scripts refuse to run on the wrong host, and the guard has been verified in both directions.",
      },
      {
        term: "Why it is written down here",
        detail:
          "Because the obvious optimisation — fetch everything from one place — is the one change that must never be made, and a future maintainer who does not know why will make it. The rate discipline has the same shape: exceeding a published per-dataset rate suspends an account, and recovering from that would cost a trip through a chain of command.",
      },
      {
        term: "The other half of the boundary",
        detail:
          "The heavy science stays on the workstation: discovery, validation, NetCDF and adaptive-grid parsing, cropping, derived fields, mask preservation, quantisation, history accumulation and compression. The public server holds immutable, content-addressed files and serves them. A visitor's browser decodes and draws, and interpolates only where the data contract permits.",
      },
    ],
  },
  {
    status: "observed",
    chip: "2,608 dead spacecraft, removed",
    title: "\"PAYLOAD\" is not \"working\"",
    summary: "The registry field that looks like it means operational does not mean operational, and taking it at face value fills a teaching catalogue with the 1960s.",
    rows: [
      {
        term: "What went wrong",
        detail:
          "The catalogue's OBJECT_TYPE = PAYLOAD includes spacecraft dead for sixty years — VANGUARD 1, TIROS 1, MOLNIYA 2-14. Shipped unfiltered, 2,608 of them displaced operational satellites from the teaching catalogue, and 2,168 of those could not be classified at all.",
      },
      {
        term: "What fixed it",
        detail:
          "CelesTrak's SATCAT carries an operational-status code and lists only operational objects. That curation is the reason this project still fetches SATCAT at all, and it is why the object-type field alone is never used to decide what a visitor sees.",
      },
      {
        term: "The general lesson",
        detail:
          "A registry establishes who registered an object, when it launched, what type it is, and where it is. It does not establish what a spacecraft is <em>for</em> or who commercially operates it — and those are exactly the two fields a visitor most wants, and exactly the two this site has got wrong before.",
      },
    ],
  },
  {
    status: "observed",
    chip: "Banned once · the rule that keeps you out of the firewall",
    title: "Stop on any error and tell a human",
    summary: "The orbital elements come from a volunteer-run, donation-funded server. This project got itself blocked by it, and the cause was not volume.",
    rows: [
      {
        term: "What happened",
        detail:
          "Error responses were ignored. A set of group queries that had never once succeeded retried on every five-minute cycle, forever. The published policy is explicit that the rule which keeps you out of the firewall is to stop on a non-200 and involve a person.",
      },
      {
        term: "What changed",
        detail:
          "Every upstream fetch in this project now halts on error rather than retrying, and respects the published cadence. Any new fetch added anywhere must do the same. Access is also restricted to one host regardless, and must not be rerouted to work around anything.",
      },
      {
        term: "Why it belongs on a public page",
        detail:
          "Because the infrastructure that makes an open-data project possible is often one person's server, and the failure mode of a well-meaning automated site is to hammer it politely to death. Naming the incident is more useful than a thank-you.",
      },
    ],
  },
];

/* ------------------------------------------------------------------- 3. NOTEBOOK */

const NOTEBOOK: Card[] = [
  {
    status: "observed",
    chip: "Geometry · flat triangles cannot follow a sphere",
    title: "The coverage footprint tore holes in itself, and the reason is a chord",
    summary: "A satellite's coverage cap was drawn 0.78 scene units above the globe. Parts of it sank inside the Earth.",
    rows: [
      {
        term: "The mechanism",
        detail:
          "A triangle is flat and the Earth is not. A flat triangle spanning an angular step s across a sphere of radius R dips R(1 − cos(s/2)) below the surface it is meant to follow. The cap used seven rings whatever its size, spaced by normalised linear interpolation, which for a geostationary cap bunched the step to about 14 degrees. That sag is larger than the 0.78 units of lift, so the cap's own triangles passed inside the opaque Earth and the Earth won the depth test in bands.",
      },
      {
        term: "How it was measured",
        detail:
          "In a real browser against the real production class, by counting pixels that should have been filled and were not: 5,709 missing for a geostationary satellite at a 0-degree elevation mask, 42,983 at 60,000 km. The bands appeared to crawl because the cap is rebuilt from the live position twenty times a second.",
      },
      {
        term: "The fix, and the general form",
        detail:
          "Rings are now placed at a uniform angular step along great circles, and the ring count is solved from the cap's own angular radius so that the worst chord sag still leaves 0.6 units of clearance. Zero missing pixels afterwards at every altitude, mask, camera distance and viewing angle probed. The same defect shape — thin geometry within a fraction of a unit of a faceted sphere, at or below depth-buffer resolution — turned up independently in the radiation belts.",
      },
    ],
  },
  {
    status: "observed",
    chip: "Orientation · hidden by a multiple of 15",
    title: "Every satellite was drawn 90 degrees from where it belonged",
    summary: "The map was 90 degrees west of everything laid over it, for months, in plain sight.",
    rows: [
      {
        term: "The mechanism",
        detail:
          "The Earth mesh, the total-electron-content canvas, the aurora canvas and the environmental surface layers each carried a −π/2 rotation about the polar axis, while satellites, ground tracks, footprints, the graticule and the day/night terminator are vector geometry placed straight from geographic coordinates. The sphere geometry already draws texture u = 0.5 on the +X axis, which is exactly where longitude 0 is placed — so the rotation introduced the error rather than cancelling one.",
      },
      {
        term: "Why nobody saw it",
        detail:
          "The graticule is unlabelled at 15-degree spacing, and 90 is a multiple of 15. A rotated globe with unlabelled gridlines looks exactly like an unrotated one. It was found from the ground up: a geostationary spacecraft whose sub-point was 101.279° W was drawn at 11.28° W, over the Gulf of Guinea, and at the same instant the sub-solar point was 113.12° W while Africa was drawn in daylight at 19:38 UTC.",
      },
      {
        term: "What it cost, and what it bought",
        detail:
          "Confirmed four independent ways before a line was changed, including a direct measurement against the installed geometry that read a constant −90.000 degrees at every longitude and 0.000 with the rotation removed. The regression test asserts geography rather than arithmetic: it paints continents at known longitudes, points the production camera down a known geographic direction, and reads back whether land or sea is there.",
      },
    ],
  },
  {
    status: "forecast",
    chip: "Upstream artefact · shown as missing, not as zero",
    title: "The aurora appeared over the equator",
    summary: "A green line across Indonesia, in a screenshot. It was real data, and it was not aurora.",
    rows: [
      {
        term: "What it actually was",
        detail:
          "NOAA's global grid carries a numerical seam where its two hemispheric solutions meet the 0-degree geographic latitude row. Across 198 five-minute grids cached over a full day, the seam never left the rows from 2°S to the equator, roughly doubled per degree toward the equator (0.9%, 1.8%, 3.5% mean at 2°S, 1°S and 0° in one frame), reached 1–4%, and sat 37 to 45 rows of <em>exactly zero</em> probability away from the nearest real signal. That is not aurora in either location or shape.",
      },
      {
        term: "Why a threshold could not remove it",
        detail:
          "The seam reaches 4% while genuinely quiet polar probability occupies the same 2–10% range. No probability threshold separates them. The distinguishing feature is not the value; it is that the seam is an isolated island of signal separated from the real oval by tens of rows of exact zero.",
      },
      {
        term: "How it is handled",
        detail:
          "The decoder clears the validity bits for those cells, so they read as <strong>missing</strong> rather than as a modelled zero, and NOAA's probability bytes are left byte-for-byte unchanged. Two guards must both hold before anything is withdrawn: the run of probability-bearing rows never leaves 5 degrees of the equator, and it is separated from every other such row by at least 10 degrees. A real storm-time equatorward expansion stays continuous with the oval, fails both guards, and is drawn in full — which matters, because equatorward expansion is the single most interesting thing an aurora layer can show.",
      },
    ],
  },
  {
    status: "observed",
    chip: "Text matching · \"DSP\" sits inside \"RIGIDSPHERE\"",
    title: "A 1971 aluminium sphere was published as a missile-warning spacecraft",
    summary: "The site described a 1.11 m solid metal ball with no power and no sensors as a strategic early-warning satellite, at high confidence, on a card ranked into the default view.",
    rows: [
      {
        term: "The mechanism",
        detail:
          "Classification used raw substring containment. \"DSP\" is a substring of \"RIGIDSPHERE\", so a radar-calibration sphere launched in 1971 acquired a Defense Support Program description, a U.S. Space Force operator, a military sector and — because the override path hard-coded it — <strong>high</strong> confidence, regardless of how weakly the entry matched. The same rule turned SKYTERRA 1, a commercial mobile-communications spacecraft, into a NASA Earth-observing mission, because \"TERRA\" is inside \"SKYTERRA\".",
      },
      {
        term: "The scale of it",
        detail:
          "An offline audit found 289 claims resting on a coincidental substring. 35 were outright contradictions with the offending fragment identified; roughly 17 of those were factually wrong on a field the visitor could read, and the rest were <em>right by coincidence</em> — which is not a defence, because the same mechanism produced both. After the fix: 0. Objects carrying any contradiction fell from 46 to 10 out of 8,000. One name-based agency rule was attached to nine objects and wrong on six; it was deleted rather than patched.",
      },
      {
        term: "What could not be fixed by better matching",
        detail:
          "Token boundaries killed that class and cannot kill the next one. The Hubble <em>Network</em> is a Bluetooth connectivity constellation on commercial buses, and HUBBLE is a genuine, whole, correctly-bounded token in every one of its names — two unrelated programmes chose the same word. No string rule separates them. Three things do: an orbit-versus-claim contradiction check, a hard requirement that no description ships without a source URL, and hand-verification of a random sample, which is how this one was found. Expect more of these.",
      },
      {
        term: "What is published instead of a guess",
        detail:
          "Where an object's own orbit contradicts its name-derived mission, the site now publishes both — the claim, the counter-evidence, and each attributed — rather than silently withdrawing the label. 162 objects carry such an annotation. A student learns more from a claim shown next to evidence that does not fit it than from a card that quietly says nothing.",
      },
    ],
  },
  {
    status: "model",
    chip: "Display scale · the picture contradicted the physics",
    title: "The radiation belts looked like a skin on the planet",
    summary: "A display transform compressed the entire trapped-particle region into a shell less than a third of the Earth's own drawn radius.",
    rows: [
      {
        term: "The mechanism",
        detail:
          "The belt layer inherited the magnetosphere's radial display transform, 100 + 18·ln(1 + (r − 1)/2.8). That maps the model's whole belt domain, about 1.02 to 12.1 Earth radii, onto scene radii 100.1 to 128.9 around a 100-unit Earth. Under that transform the belts cannot be anything but a coating on the globe, and the slot region — whose entire meaning is a three-decade drop in flux between two belts — has nowhere to exist.",
      },
      {
        term: "The second, larger version of the same problem",
        detail:
          "Satellites used one altitude scale while the magnetopause and the model cuts used a much harsher one. A geostationary satellite, physically well inside the magnetopause, was drawn at scene radius 229.8 with the magnetopause nose at 125.1 — apparently orbiting outside the boundary that contains it. No code anywhere made that claim; the picture made it. Every layer now goes through one radial transform, so \"is this satellite inside the magnetopause\" and \"is a navigation satellite inside the outer belt\" are answerable by eye.",
      },
      {
        term: "Two other causes in the same layer",
        detail:
          "Everything the model published was being drawn, including its grid's inward extension to its own ionospheric boundary at 1.0157 RE — thermosphere, not belt — and cells sitting at the encoding's flux floor, which still produced full translucent surfaces. Eleven stacked floor-valued shells is a purple blanket, and it buried the slot. An opacity floor in the shader made eleven shells read as uniform haze. Both are gone, and the display window is disclosed rather than silent.",
      },
      {
        term: "The standing caveat",
        detail:
          // CORRECTNESS FIX 2026-09-04. Three stale claims in one sentence.
          // The near-Earth branch of the ruler MAGNIFIES altitude (a 100 km
          // layer draws where 450 km belongs) and only compresses past
          // 4,795 km. The drawn column's floor is 60 km, not 90. And the
          // exaggerated peak surfaces are not in the scene: `globe.ts` sets
          // `layer.points.visible = false` and the layer page marks them
          // retired.
          "Radial distance on this globe is not linear: near-Earth heights are stretched — a 100 km layer draws where 450 km belongs — and distances past about 4,800 km are compressed, so that the ionosphere's 60 km floor and a geostationary orbit can be read on one picture. Every legend and every sampled value reports true, unexaggerated kilometres. Geometric intersection can never be judged from the 3-D view — which is why the honest answer to \"does my satellite pass through that layer\" is a strip chart of altitude against modelled peak height along the orbit, not a picture.",
      },
    ],
  },
  {
    status: "observed",
    chip: "The instrument said it was fine",
    title: "A spacecraft's own quality flag read nominal while it was wrong by a factor of two",
    summary:
      "During the May 2024 storm, a monitor at L1 reported roughly 475 km/s and 2 cm⁻³ while another reported 770–1000 km/s and 16–29 cm⁻³. Its overall quality flag read 0 — nominal — throughout.",
    rows: [
      {
        term: "Why this is the worst possible failure for this site",
        detail:
          "Dynamic pressure goes as n V², and magnetopause standoff goes as Pdyn to the power −1/6.6. Taking the faulty sample at face value would have drawn an <strong>expanded</strong> magnetosphere during the most severe compression in twenty years, with every honesty label on the page reporting that the data was nominal. A confident wrong number is worse than a gap precisely because the labels are all still green.",
      },
      {
        term: "Why bounds do not help",
        detail:
          "Absurdity bounds were set wide enough that no real event is clipped — speed 200–2500 km/s, density 0.01–200 cm⁻³, |B| 0.1–200 nT. The faulted samples sat comfortably inside every one of them. That is the point: physical plausibility is necessary and nowhere near sufficient.",
      },
      {
        term: "What actually catches it",
        detail:
          "Corroboration by a <em>different spacecraft</em> — and no second monitor was reporting at the moment of onset, so the check that carries it alone is coherence between instruments on the same spacecraft. Across any magnetohydrodynamic discontinuity that changes the bulk plasma appreciably, the magnetic field magnitude changes with it. A plasma instrument that drops density eightfold and speed by 37% while its own magnetometer moves 2% is not observing a structure in the solar wind. Rate of change is never on its own a rejection: a genuine shock is a real step, and at the real 2024-05-10 17:05 shock arrival the field stepped by far more than 10%, so the rule stays silent there by construction.",
      },
      {
        term: "What the site does when sources disagree",
        detail:
          "It never silently picks one. Two disagreeing readings with no third to break the tie is <em>disputed</em>, and disputed withholds speed, density, temperature, dynamic pressure and the magnetopause standoff — and truncates the plotted history at the fault onset rather than presenting a healthy reading from an hour ago as the current state. A single disagreeing witness never overrides the primary, because with two readings there is no basis for deciding which instrument is at fault; two mutually agreeing witnesses do. An honest \"disputed\" beats a confident wrong number.",
      },
    ],
  },
  {
    status: "observed",
    chip: "Provenance · three doors onto one dataset is not three measurements",
    title: "The most repeated number for the May 2024 storm exists in two versions, and neither is final",
    summary: "Storm severity is quoted from indices. The indices are revised, the real-time version is explicitly not for scientific use, and several apparently independent routes lead to the same file.",
    rows: [
      {
        term: "Two numbers, both correct",
        detail:
          "Papers on this storm quote a minimum disturbance index of −412 nT; a pipeline fetching the provisional archive today gets −406 nT. Both are right — they are different products. The first is the real-time quicklook value, and the producing centre's own version document says of it that artificial noise and baseline offsets are not removed and that the real-time index is intended for monitoring purposes only and not for scientific analysis. They quantify the eventual revision themselves: for one earlier year, a discrepancy of about 20–30 nT between provisional and final values, caused by a baseline drawn from a storm-depressed month, which underestimates the storm's strength.",
      },
      {
        term: "The part that catches everyone",
        detail:
          "The May 2024 index will not be <em>final</em> until roughly 2029. Any site that labels today's value \"final\" is wrong, and any site that shows one without saying which product it is has published an unreproducible number.",
      },
      {
        term: "The independence trap",
        detail:
          "The one-minute companion index can be retrieved through three separate services with three separate interfaces. They are three doors onto one dataset. Drawing them as three agreeing sources would manufacture corroboration out of nothing — the same error, in a different costume, as trusting a spacecraft's opinion of itself.",
      },
      {
        term: "One more, from the same audit",
        detail:
          "HTTP 200 is not success. Five separate recorded cases from these upstreams: a service returning 200 with the body ERROR: Invalid username; a query returning 200 with all-null data; two archives returning 200 with a single bogus record dated years outside the request; a directory returning 200 with a zero-byte body; and the plasma instrument above returning 200 with a nominal quality flag on data wrong by a factor of nearly two. Every fetcher in this project validates content, not status.",
      },
    ],
  },
  {
    status: "model",
    chip: "Verification · four ways a green test can mean nothing",
    title: "The tests passed. The code had never run.",
    summary: "This codebase has produced four distinct defect classes that a full green test suite sat directly on top of, and one deployment that reported success and changed nothing.",
    rows: [
      {
        term: "A test suite that never touched production",
        detail:
          "The live-refresh controller stored the global fetch function on the instance and called it as a method, which browsers reject outright. Every unit test injected its own replacement, so the only code path that actually runs in production had never once been exercised. The symptom in the wild was an open tab showing a layer as permanently unavailable; the fix carries a regression test that fails if the binding is removed.",
      },
      {
        term: "An audit that examined nothing",
        detail:
          "The catalogue audit reads the classification rules out of the production source with a syntax-tree walk, deliberately, so that restating them cannot drift. During development that walk handled only plain assignments — and one rule table is an annotated assignment, so the check silently returned zero fragments and reported a clean result. A check that looks like it ran and inspected nothing is the same defect class as the one above.",
      },
      {
        term: "The other two shapes",
        detail:
          "Cache keys that invalidate themselves, and rounded buckets that are unstable exactly where the real data sits — a value hovering on a bucket boundary flips category on noise, so the output changes while the input has not meaningfully moved. Both had green tests. Assume there are more of the same shape.",
      },
      {
        term: "A deploy that succeeded and did nothing",
        detail:
          "The documented release procedure — stage the built site, swap it atomically, recreate the service — is incomplete, because the build is copied <em>into</em> the container image rather than mounted. Swapping the files on the host left the container serving its previous build; the health check passed and the site looked fine. Found the hard way: the swap reported success and the public bundle hash never changed. Verification that does not check the artefact the public actually receives is not verification.",
      },
      {
        term: "A typing error caught by its own guard",
        detail:
          "Hand-writing catalogue identifiers removes the substring failure mode and introduces a typing one. One curated entry was written against an identifier belonging to an entirely different spacecraft. Every hand-keyed entry is now stamped with the registry name it was resolved from, and a test re-checks each identifier against the mirror. The point is not that a typo happened; it is that a curated dataset needs a guard aimed at the failure mode curation introduces.",
      },
    ],
  },
];

/* --------------------------------------------------------------- 4. CORRECTIONS */

type Correction = {
  status: EvidenceClass;
  kind: string;
  date: string;
  title: string;
  summary: string;
  rows: { term: string; detail: string }[];
  link?: { label: string; url: string };
};

const CORRECTIONS: Correction[] = [
  {
    status: "model",
    kind: "WITHDRAWN",
    date: "2026-08-08",
    title: "A validation claim about the thermosphere, because the thing being validated against was a model",
    summary:
      "The site said an atmospheric density reduction here had been checked against an observed six-fold density enhancement during the May 2024 storm. That six-fold figure is model output. The comparison was model against model.",
    rows: [
      {
        term: "What was published",
        detail:
          "That the thermospheric density reduction computed for this project had been validated against an observed enhancement of up to six times the baseline at 400 km during the storm.",
      },
      {
        term: "What is actually the case",
        detail:
          "Parker and Linares (2024) state that figure as NRLMSISE-00 model output — the model's own density field, evaluated before and after. The <em>observation</em> in that paper is the change in orbital decay rate of a spacecraft: about 38 metres per day before the storm, rising to 180 during it. Comparing a model reduction against a model field establishes nothing about either.",
      },
      {
        term: "What replaces it",
        detail:
          "The sound reference is the open multi-mission assessment of thermosphere models across 151 storms from 2001 to 2023, which finds that MSIS models systematically underestimate density by about 20–30% during storm main and recovery phases and recommends replacing MSIS as the standard reference for storm-time drag. That is a published, quantified statement about how a model behaves — which is the kind of thing a model comparison can actually be checked against.",
      },
      {
        term: "What survives",
        detail:
          "The separate check against a genuine measurement stands: an independent reduction of the operational atmosphere model for 8–13 May 2024 gives a global-mean density at 400 km falling to 0.64 times its pre-storm baseline by 21:00 UT on 12 May, agreeing in sign, magnitude class and day with a published Swarm-C observation of a −23% depletion. It is stated as corroboration of direction, not a match, because a global mean and a single northern-polar satellite track are different quantities.",
      },
    ],
    link: { label: "Wang et al. 2026, Space Weather 24, e2025SW004782 ↗", url: "https://doi.org/10.1029/2025SW004782" },
  },
  {
    status: "model",
    kind: "CORRECTED",
    date: "2026-08-08",
    title: "The skill score quoted for the magnetosphere model was too flattering",
    summary: "A correlation of 0.4–0.6 was quoted for global magnetosphere models against ground magnetometers. The published range is 0.21 to 0.65.",
    rows: [
      {
        term: "The corrected figure",
        detail:
          "Wilkerson et al. (2026) assembled measured geomagnetically induced currents from 47 sites and magnetometer data from 17 sites for the May 2024 storm and scored three global models against them. Across the twelve magnetometer sites where all three models produced output, the horizontal magnetic-field perturbation correlated with the measurements at r between <strong>0.21 and 0.65</strong>. In their comparison one model over-predicts the disturbance and the operational framework this site displays under-predicts it.",
      },
      {
        term: "Why the difference matters",
        detail:
          "0.4–0.6 sounds like a model that is roughly right with scatter. 0.21 at the low end is a model that, at some sites, is barely tracking the quantity at all. Narrowing a published range inward flatters the model, and it is the specific way an honest number becomes a dishonest one.",
      },
      {
        term: "Where it now appears",
        detail: "Beside any ground quantity derived from that model, on the Connections page. Beautiful field lines are not a skill score.",
      },
    ],
    link: { label: "Wilkerson et al. 2026, Space Weather 24, e2025SW004758 ↗", url: "https://doi.org/10.1029/2025SW004758" },
  },
  {
    status: "empirical",
    kind: "CORRECTED",
    date: "2026-08-08",
    title: "A magnetopause compression figure that had no source",
    summary: "A range of 3.7–5.0 Earth radii was carried in project material for the May 2024 standoff. It could not be traced to any publication, and it has been replaced with figures that can.",
    rows: [
      {
        term: "What is published, and by whom",
        detail:
          "Tulasi Ram et al. (2024) report the dayside magnetopause below geostationary orbit at 6.6 Earth radii for about six continuous hours on 10–11 May 2024, with the bow shock briefly following it in, and magnetohydrodynamic models placing the boundary as low as 3.3 Earth radii. Fu et al. (2025) determined the compression directly — from beyond 10 Earth radii down to about 5 — by combining in-situ measurements from multiple spacecraft with ground magnetometer data.",
      },
      {
        term: "What the unsourced range was doing",
        detail:
          "Acting as a validation gate. An extraction of the boundary from a physics run was to be checked against it. A gate with no citation behind it is not a gate; it is a number that has acquired authority by being written down repeatedly.",
      },
      {
        term: "The check that remains, stated properly",
        detail:
          "On a quiet pre-storm frame, the empirical boundary computed from a model run's own upstream drivers agreed with that run's magnetopause current layer to 0.36 Earth radii, or 3.4% — 10.61 against 10.25. That is an anchor, not a finding. Under compression the two <em>should</em> diverge, because an axisymmetric fit to past crossings cannot reproduce a compressed asymmetric boundary.",
      },
    ],
    link: { label: "Fu et al. 2025, Geophys. Res. Lett. 52, e2024GL114040 ↗", url: "https://doi.org/10.1029/2024GL114040" },
  },
  {
    status: "observed",
    kind: "NARROWED",
    date: "2026-08-08",
    title: "An exact storm-index minimum, reduced to what can be defended",
    summary: "The site's published wording for the storm's minimum one-minute disturbance index is now \"below −500 nT\". The exact value and minute are not stated.",
    rows: [
      {
        term: "Why",
        detail:
          "An exact minute-resolution minimum could not be independently pinned. The retrieval routes that return it are, as described in the notebook above, three interfaces onto a single dataset rather than three measurements — and the index in question is not final and will not be for years. \"Below −500 nT\" is true, is enough to establish that this was an extreme storm, and does not imply a precision the source does not support.",
      },
      {
        term: "The general rule this follows",
        detail:
          "Where a figure cannot be independently confirmed, the site publishes the weaker claim it can defend rather than the stronger claim it found. That is a worse headline and a better site.",
      },
    ],
  },
  {
    status: "observed",
    kind: "CORRECTED",
    date: "2026-08-07",
    title: "Facts on satellite cards that rested on coincidental text matching",
    summary: "289 displayed claims across the catalogue had no evidence behind them beyond a substring. All are gone; the mechanism that produced them was removed rather than patched.",
    rows: [
      {
        term: "The measured before and after",
        detail:
          "Same upstream data, same 8,000 objects, old pipeline against corrected pipeline: substring over-matches 289 → 0; objects carrying a contradiction 46 → 10; total audit findings 488 → 193. The 193 that remain are, in full, genuine disagreements <em>between</em> the two registries the site reads, launch dates differing by a day or two, geostationary imagers queued for a human look, and co-branded spacecraft. None is a wrong fact invented here.",
      },
      {
        term: "What was fixed on the visitor's side",
        detail:
          "Cards in the default view carrying a source-cited description went from 0 to 414 of 450; all 311 objects asserting a military attribution now carry a public citation where none did before; and a description can no longer ship at all without a source URL — the release refuses to build.",
      },
      {
        term: "The honest remainder",
        detail:
          "Several families were deliberately left with their plain orbit-derived default because no operator citation could be established within the working session, and a different guess is not better than none. Opaque national-security designators are not inferred from public sources at all.",
      },
    ],
  },
  {
    status: "forecast",
    kind: "CORRECTED",
    date: "2026-08-07",
    title: "Aurora drawn over the equator",
    summary: "An upstream grid seam was rendered as auroral probability across the tropics. Those cells are now published as missing, with the source bytes untouched.",
    rows: [
      { term: "What a visitor saw", detail: "A continuous green line across Indonesia, at 1–4% probability, in a screenshot." },
      {
        term: "The correction",
        detail:
          "The cells are withdrawn by clearing their validity bits at decode time, on the single path every consumer uses, so they read as <em>missing</em> rather than as a modelled zero. The upstream probability bytes are unchanged, the reduction stays lossless, and the artifact itself now publishes the rule that was applied to it.",
      },
      { term: "Verified against", detail: "All 200 cached frames: the seam is present in every one, never spans beyond 2°S to 0°, and no cell outside those rows loses validity in any frame." },
    ],
  },
  {
    status: "observed",
    kind: "CORRECTED",
    date: "2026-08-07",
    title: "Every satellite drawn 90 degrees from its true longitude",
    summary: "The base map was rotated a quarter-turn relative to every vector object placed on it. Both are now on one geographic frame, and the whole scene is on one radial ruler.",
    rows: [
      {
        term: "What was wrong",
        detail: "A rotation applied to the Earth mesh and the raster layers put the map texture out of register with satellites, ground tracks, footprints, the graticule and the terminator. The day/night line was on the wrong continents at the same time, for the same reason.",
      },
      {
        term: "What it means for anything read off the globe before then",
        detail:
          "Any longitude judged by eye from this site before 2026-08-07 was wrong by 90 degrees. Coverage footprints, ground tracks and the terminator are correct now, and a browser regression test pins them to painted continents rather than to arithmetic.",
      },
      {
        term: "The scale correction that shipped with it",
        detail:
          "Layers previously used two different radial transforms, so a geostationary satellite was drawn apparently outside a magnetopause that physically contains it. All layers now share one transform. No code ever asserted that the satellite was outside the boundary — the picture did, which is the harder kind of wrong claim to find.",
      },
    ],
  },
];

/* ------------------------------------------------------------------- 5. CREDIT */

type CreditEntry = { title: string; body: string; url: string };

const ENGINEERING_CREDIT: CreditEntry[] = [
  {
    title: "NOAA's machine-readable endpoints, and NOMADS",
    body: "Almost every live layer here is a NOAA Space Weather Prediction Center product retrieved from a documented JSON or NetCDF endpoint, with no key, no registration, no quota and no terms to negotiate — including the operational model tree on NOMADS that carries the ionosphere and magnetosphere fields. The scientific credit belongs on the Connections page; what belongs here is the engineering fact that a public agency publishing parseable files on a schedule is the single reason a small site can show live physics at all.",
    url: "https://nomads.ncep.noaa.gov/",
  },
  {
    title: "NASA's data services — CCMC, ISWA and CDAWeb HAPI",
    body: "The Community Coordinated Modeling Center runs other people's models on request and keeps the results; its ISWA and the Space Physics Data Facility's CDAWeb both expose HAPI, a common time-series interface, so one parser reaches decades of archived indices and spacecraft measurements. Storm-replay work in this project reads through those interfaces rather than scraping.",
    url: "https://ccmc.gsfc.nasa.gov/",
  },
  {
    title: "USGS Geomagnetism Program",
    body: "A one-minute observed disturbance index at roughly four-minute latency, US public domain, served with permissive cross-origin headers so a browser can read it directly. Their service is also the reason this project could tell a modelled index from a measured one instead of drawing a single line and calling it the truth. Two traps worth passing on: the element channel names are case-sensitive, and the data endpoint answers 404 to a HEAD request and 200 to a GET.",
    url: "https://geomag.usgs.gov/",
  },
  {
    title: "USSPACECOM, for a redistribution position stated in plain language",
    body: "Express blanket approval for transfer and redistribution of basic Space Situational Awareness data, conditioned on appropriate citation, with the relevant products named. That one sentence is why the orbital elements behind this site can reach your browser, and why a citation travels with every download. An earlier reading of the governing statute in this project was far too rigid; the correction is recorded here rather than buried.",
    url: "https://www.space-track.org/",
  },
  {
    title: "CelesTrak, and Dr T. S. Kelso",
    body: "A donation-funded server, run for decades by one person, whose curated catalogue is what lets this site tell an operational spacecraft from an object dead since the 1960s — a distinction the raw registry field does not make. This project was blocked by it once, deservedly, for retrying failed queries in a loop. Naming that is more useful than thanking them.",
    url: "https://celestrak.org/",
  },
  {
    title: "Natural Earth — Tom Patterson and Nathaniel Vaughn Kelso",
    body: "Public-domain 1:110m coastlines, given away by cartographers who explicitly renounced any claim on them. Their terms say crediting the authors is unnecessary. It is necessary here, because a self-hosted globe with no metered tile service is the only reason this site is free to run and free to visit.",
    url: "https://www.naturalearthdata.com/",
  },
  {
    title: "The open-source stack this runs on",
    body: "three.js for the scene; satellite.js, which is the SGP4 propagator every dot on this globe is computed with; suncalc for solar geometry; Vite and TypeScript for the build; Vitest and Playwright for the tests that drive the real application against real artifacts rather than mocks. The pipeline is Python's standard library on a system interpreter — SQLite for the element archive included — which is a constraint, and which has kept the dependency surface honest.",
    url: "https://github.com/shashwatak/satellite-js",
  },
  {
    title: "Data providers with conditions worth honouring, not just citing",
    body: "The world magnetic-index centres publish under terms that require acknowledgement, carry data DOIs, and in some cases exclude commercial use — which is a live question for any site, not a formality. Delft's open accelerometer-derived thermosphere densities and the citizen-science aurora catalogue released under a Creative Commons licence are what make model claims checkable by anyone. Where a licence is non-commercial, that constraint is recorded against the layer rather than assumed away.",
    url: "https://intermagnet.org/",
  },
];

/* ---------------------------------------------------------------------- RENDER */

export function methodsView(): string {
  return `
    <header class="content-hero">
      <p class="eyebrow">PROVENANCE · ARCHITECTURE · THE NOTEBOOK · CORRECTIONS</p>
      <h1>How this was built, and what we found doing it.</h1>
      <p>Every layer on this site came from somewhere, arrived late, covered less than it appears to, and had to be argued with. This page says where each product comes from and what it is not; why the system is shaped the way it is, with the measurement behind each decision; what broke and what each break turned out to be teaching; and — dated, in public — the claims this site has corrected or withdrawn.</p>
    </header>

    <aside class="teaching-callout"><strong>Where this page sits</strong><em>Data &amp; methods</em> holds the full scientific contract for each layer — the exact variable, the reduction, the permitted display transformations, the inference it cannot support. <em>Connections</em> holds the physics links between layers and credits the published work they rest on. This page holds the engineering: provenance and timing, the architecture arguments, the defect notebook, and the corrections log. It does not repeat the other two.</aside>

    <section class="method-section" aria-labelledby="provenance-title">
      <div class="method-section-head">
        <p class="section-kicker">PROVENANCE, LAYER BY LAYER</p>
        <h2 id="provenance-title">Named product, cadence, latency, real coverage — and the sentence each one needs</h2>
        <p>The badge on each card is the layer's evidence class. The row that matters most is the last one: what the product does <em>not</em> establish, stated before you have a chance to assume otherwise.</p>
      </div>
      <div class="method-grid">
        ${PROVENANCE.map(detailCard).join("")}
      </div>
    </section>

    <aside class="teaching-callout"><strong>The globe's radius is not a distance</strong>Physical radial distance is drawn on a logarithmic near-Earth curve that STRETCHES low altitudes and compresses high ones — a 100 km layer draws where 450 km belongs, the crossover is near 4,800 km, and geostationary orbit draws at under a quarter of its true height — so that the ionosphere's 60 km floor and a 36,000 km geostationary orbit can be read in one picture. Every legend, every satellite sample and every reported altitude is the true, unexaggerated physical value. Nothing about geometric intersection can be judged by eye from the 3-D view.</aside>

    <aside class="teaching-callout"><strong>A modelled index is not a measured index</strong>The operational geospace run that draws the magnetosphere on this site also publishes a one-minute storm index — and it runs about 73 minutes <em>into the future</em>, because it is a model estimate rather than a measurement. The observed versions of the same quantity arrive later and from different instruments: a one-minute observed index at about four minutes' latency, and the hourly index the world quotes at about fifty. When that layer ships, the three will be drawn as three distinct series with three evidence classes and never merged into one line, because the disagreement between them is the lesson.</aside>

    <aside class="teaching-callout"><strong>Scrub back far enough and layers start disappearing. That is correct.</strong>Several upstreams publish only their latest numeric frame, so this site's history begins where its own accumulation began and every collection gap is a real gap. The element archive began in August 2026. There is no data here from May 2024 — every figure from that storm on this site is cited to someone else's published work. A layer outside its coverage disappears and reports the gap; it does not freeze the current field, sample a rendered image, or invent a forecast to keep the globe full. An empty globe is a scientific result.</aside>

    <section class="method-section" aria-labelledby="architecture-title">
      <div class="method-section-head">
        <p class="section-kicker">WHY IT IS SHAPED THIS WAY</p>
        <h2 id="architecture-title">Four decisions, and the measurement that forced each one</h2>
        <p>Each of these looks like an arbitrary implementation choice from the outside, and each one is load-bearing. Three of them would be undone by an obvious-looking optimisation.</p>
      </div>
      <div class="processing-facts">
        <article><strong>0.8 MB</strong><span>Gzipped, covering all 8,000 objects at any instant, because elements are a compact complete representation</span></article>
        <article><strong>138 MB</strong><span>Per five-minute publish cycle if positions were precomputed instead, at five-minute sampling — and it would still not answer an arbitrary time</span></article>
        <article><strong>2,608</strong><span>Spacecraft dead since the 1960s that a single misread registry field put in front of visitors, displacing operational ones</span></article>
        <article><strong>289 → 0</strong><span>Displayed facts resting on a coincidental substring, before and after the classification rewrite</span></article>
      </div>
      <div class="method-grid">
        ${ARCHITECTURE.map(detailCard).join("")}
      </div>
    </section>

    <section class="method-section" aria-labelledby="notebook-title">
      <div class="method-section-head">
        <p class="section-kicker">THE NOTEBOOK</p>
        <h2 id="notebook-title">What broke, how it was caught, and what it was teaching</h2>
        <p>These are the defects worth publishing, because in every case the bug turned out to be a piece of physics, geometry or epistemology that the site now explains on purpose. Each one hid behind something that looked correct: a passing test, an unlabelled gridline, a nominal quality flag, a value inside every plausible bound.</p>
      </div>
      <div class="method-grid">
        ${NOTEBOOK.map(detailCard).join("")}
      </div>
    </section>

    <section class="method-section" aria-labelledby="corrections-title">
      <div class="method-section-head">
        <p class="section-kicker">CORRECTIONS AND WITHDRAWALS</p>
        <h2 id="corrections-title">Claims this site has changed or taken back, with dates</h2>
        <p>A corrections log is not an apology. It is the mechanism by which a claim becomes trustworthy: a site that has never corrected anything has either published nothing interesting or is not checking. Each entry says what was published, what is actually the case, and what replaced it.</p>
      </div>
      <div class="method-grid">
        ${CORRECTIONS.map(correctionCard).join("")}
      </div>
      <aside class="teaching-callout"><strong>The shape of the worst one</strong>The withdrawn thermosphere claim is the most instructive entry here, because nothing about it was careless. The figure was real, published, and correctly quoted. The error was one level up: it was read as an observation when the paper states it as model output, and it was then used to validate a model. Model-versus-model comparisons look exactly like validations and establish nothing. The only defence is to check what evidence class a number is before deciding what it can be used for — which is why every layer on this site carries a badge.</aside>
    </section>

    <section class="method-section" aria-labelledby="credit-title">
      <div class="method-section-head">
        <p class="section-kicker">THE ENGINEERING SIDE OF THE CREDIT</p>
        <h2 id="credit-title">Open data, public models, and volunteer-run services</h2>
        <p>The scientific credit — the people who measured this storm, and the model builders whose equations this site evaluates — is on the <em>Connections</em> page, twenty-nine entries, and is not repeated here. What follows is the infrastructure half: the organisations that publish machine-readable data openly, the licences that made it usable, and the software this runs on.</p>
      </div>
      <div class="source-grid">
        ${ENGINEERING_CREDIT.map(
          (entry) =>
            `<article class="source-card"><span class="section-kicker">CREDIT</span><h2>${entry.title}</h2><p>${entry.body}</p><a href="${entry.url}" target="_blank" rel="noreferrer">Open source ↗</a></article>`,
        ).join("")}
      </div>
      <aside class="teaching-callout"><strong>What this site costs to run, and why that is a scientific fact</strong>No metered map tiles, no commercial data feeds, no per-request API billing. Every input is either a public-domain government product, a public-domain dataset, or an open-source library. That is why a teaching site under a non-profit can show live space physics at all — and it is also why the constraints above are worth honouring rather than routing around. The whole thing rests on a small number of institutions and individuals choosing to publish parseable files on a schedule.</aside>
      <aside class="teaching-callout"><strong>Operational boundary</strong>This is a teaching site under a non-profit. It is not a warning service, a collision-assessment tool, a navigation source, a dose calculator, or a communications-planning authority. For anything that matters operationally, follow NOAA SWPC and the responsible organisation.</aside>
    </section>
  `;
}

function detailCard(card: Card): string {
  return `<details class="method-card">
    <summary><span class="layer-status ${card.status}">${card.chip}</span><strong>${card.title}</strong><small>${card.summary}</small></summary>
    <div class="method-card-body">
      <dl>
        ${card.rows.map((row) => `<div><dt>${row.term}</dt><dd>${row.detail}</dd></div>`).join("")}
      </dl>
      ${card.link ? `<a href="${card.link.url}" target="_blank" rel="noreferrer">${card.link.label}</a>` : ""}
    </div>
  </details>`;
}

function correctionCard(card: Correction): string {
  return `<details class="method-card">
    <summary><span class="layer-status ${card.status}">${card.kind} · ${card.date}</span><strong>${card.title}</strong><small>${card.summary}</small></summary>
    <div class="method-card-body">
      <dl>
        ${card.rows.map((row) => `<div><dt>${row.term}</dt><dd>${row.detail}</dd></div>`).join("")}
      </dl>
      ${card.link ? `<a href="${card.link.url}" target="_blank" rel="noreferrer">${card.link.label}</a>` : ""}
    </div>
  </details>`;
}
