/**
 * "Connections" content view.
 *
 * Three things live here, deliberately together:
 *   1. links between phenomena that a visitor moving one layer at a time would miss;
 *   2. credit to the people, missions and institutions whose work makes those links knowable;
 *   3. a plain statement of where this site is wrong, thin, or not yet built.
 *
 * Every numeric claim below was checked against the cited source before it was written.
 * Nothing here is generated at runtime; this module returns static markup and reuses the
 * classes already defined in src/styles.css. It adds no new CSS and imports nothing.
 */

type EvidenceClass = "observed" | "assimilated" | "model" | "empirical" | "forecast" | "schematic";

type Connection = {
  /** Evidence class of the weakest link in the chain, not the strongest. */
  status: EvidenceClass;
  /** Free-text chip. Says what kind of claim this connection is. */
  chip: string;
  index: string;
  title: string;
  /** One sentence, visible without opening the card. */
  summary: string;
  mechanism: string;
  evidence: string;
  onSite: string;
  limit: string;
  sources: { label: string; url: string }[];
};

const CONNECTIONS: Connection[] = [
  {
    status: "observed",
    chip: "Observed on both ends · one Sun, two clocks",
    index: "01",
    title: "The blackout and the storm are the same active region, days apart",
    summary:
      "A flare and a coronal mass ejection can leave the Sun together and arrive at Earth about a day and a half apart, so their effects look like unrelated events.",
    mechanism:
      "X-rays travel at c and reach Earth in about eight minutes. They ionise the D region on the sunlit hemisphere within minutes, and the D region is where HF radio is absorbed rather than reflected — so the first symptom of a big flare is a daylight-side shortwave blackout. The coronal mass ejection launched by the same active region is plasma, not light. It crosses 1 AU in roughly one to three days, and only when its embedded magnetic field turns southward does it couple efficiently to Earth's field and drive a geomagnetic storm. Same source region, two arrivals, two entirely different affected systems.",
    evidence:
      "May 2024 shows both halves cleanly. Tulasi Ram et al. (2024) report an HF radio blackout across the 2–12 MHz band caused by strong D- and E-region ionisation from a solar flare that occurred before the storm, and then a storm that pushed the dayside magnetopause below geostationary orbit for about six continuous hours. Weiler et al. (2025) traced the storm to five interacting coronal mass ejections and measured the shock 2.57 hours earlier at STEREO-A, at 0.956 AU, than at L1 — a direct demonstration that the plasma leg of the chain has a travel time you can put a number on.",
    onSite:
      "Turn on Solar X-ray flux and D-region HF absorption together, then Solar wind &amp; IMF. The X-ray glyphs and the D-RAP absorption field respond to the same GOES irradiance sample at the selected time; the solar-wind readout carries a separate observation time and a propagated Earth-arrival time. Those two timestamps are different on purpose.",
    limit:
      "D-RAP is a nowcast of the highest affected frequency on a vertical path, not an outage map, and it omits auroral-electron absorption entirely. The X-ray layer's inbound rays are irradiance cues, not detected photons. Nothing on this site propagates a CME from the Sun; the solar-wind layer starts at NOAA's already-propagated Earth-arrival series.",
    sources: [
      { label: "Tulasi Ram et al. 2024, Space Weather 22, e2024SW004126", url: "https://doi.org/10.1029/2024SW004126" },
      { label: "Weiler et al. 2025, Space Weather 23, e2024SW004260", url: "https://doi.org/10.1029/2024SW004260" },
    ],
  },
  {
    status: "empirical",
    chip: "Measured boundary, measured loss · mechanism is inference",
    index: "02",
    title: "A boundary moved, so a radiation belt emptied",
    summary:
      "Trapped electrons did not decay away during the May 2024 storm. The outer wall of the trap moved inside their orbits and they left.",
    mechanism:
      "Outer-belt electrons drift in closed paths around Earth on shells labelled by L. Those paths are closed only as long as the magnetopause — the boundary between Earth's field and the shocked solar wind — stays outside them. Raise the solar-wind dynamic pressure and turn the interplanetary field southward and the dayside magnetopause moves inward. When it crosses a drift shell, electrons on that shell reach the boundary on their next orbit and are simply lost into the magnetosheath. This is called magnetopause shadowing. It is worth being precise about what it is not: no wave scattered these particles, no field line broke. The container changed shape.",
    evidence:
      "For 10–11 May 2024 all three steps were measured separately. Tulasi Ram et al. (2024) found the dayside magnetopause compressed below geostationary orbit at 6.6 Earth radii for about six continuous hours, with the bow shock briefly below it too, and magnetohydrodynamic models placing the boundary as low as 3.3 Earth radii. Fu et al. (2025) used in-situ measurements from multiple spacecraft together with ground magnetometers to determine the compression directly: from beyond 10 Earth radii down to 5. Sun et al. (2026) then looked at what happened to the particles, using GOES-16 on the dayside, GOES-18 at dawn and FY-4B at midnight: on the dayside and dawn flank, magnetopause shadowing produced rapid, dispersionless electron dropouts. Boundary in, particles gone, same hours.",
    onSite:
      "Switch on Magnetopause and Radiation belts together and watch the standoff distance in the legend as the interplanetary Bz reading goes negative. The Shue boundary is recomputed from the live propagated dynamic pressure and Bz at every selected time, so the surface you are looking at is doing the arithmetic of this connection continuously.",
    limit:
      "The Shue surface on this site is an empirical fit to observed magnetopause crossings, and it is axisymmetric — it has no dawn–dusk asymmetry, which is exactly the asymmetry Sun et al. measured in the dropouts. The radiation-belt layer is a coupled model solution, not a measurement, and it does not solve magnetopause loss. The site can show you the boundary moving and it can show you a modelled belt. It cannot show you one causing the other.",
    sources: [
      { label: "Tulasi Ram et al. 2024, Space Weather 22, e2024SW004126", url: "https://doi.org/10.1029/2024SW004126" },
      { label: "Fu et al. 2025, Geophys. Res. Lett. 52, e2024GL114040", url: "https://doi.org/10.1029/2024GL114040" },
      { label: "Sun et al. 2026, JGR Space Physics 131, e2026JA035141", url: "https://doi.org/10.1029/2026JA035141" },
      { label: "Shue et al. 1998, JGR 103, 17691 — the boundary model itself", url: "https://doi.org/10.1029/98JA01103" },
    ],
  },
  {
    status: "forecast",
    chip: "Observed aurora vs modelled oval · the model lost",
    index: "03",
    title: "The aurora went further south than the oval model said it would",
    summary:
      "In May 2024 people photographed aurora from latitudes where every operational oval model said there should be none, and that gap is a published result rather than an anecdote.",
    mechanism:
      "As the ring current builds during a storm, the magnetosphere's night-side field stretches and the region of open and stretched field lines grows. The auroral oval is the ionospheric footprint of the precipitating particles on those field lines, so it expands equatorward — the oval is not a fixed ring at high latitude but a boundary that moves with the storm. Auroral-oval models are fitted to past behaviour, and an event outside the range they were fitted to is an event they extrapolate into.",
    evidence:
      "Grandin et al. (2024) collected 696 citizen-science reports from more than 30 countries plus 186 observations from the Skywarden catalogue for the night of 10 May 2024. Aurora was widely seen from geomagnetic latitudes between 30 and 60 degrees, with a few reports from lower still — in their words, significantly further equatorward than predicted by auroral oval models. It is one of the few results in space physics where the measurement that beat the model came from the public.",
    onSite:
      "The Auroral oval layer is NOAA OVATION, which is exactly the class of model that fell short. Read its badge: FORECAST. It gives a viewing probability under dark, clear skies for a specific forecast-valid time, computed from upstream solar-wind and interplanetary field inputs. It is guidance, not an observation of light in the sky.",
    limit:
      "This site holds no aurora data for May 2024. NOAA publishes only the latest numeric OVATION grid, so the site's history begins where its own accumulation began; earlier times are a genuine gap and are shown as one. The 24-hour animations NOAA publishes are rendered images, and this site does not read numbers back out of pictures.",
    sources: [
      { label: "Grandin et al. 2024, Geoscience Communication 7, 297–316", url: "https://doi.org/10.5194/gc-7-297-2024" },
      { label: "Newell, Sotirelis &amp; Wing 2009, JGR 114 — OVATION Prime precipitation budget", url: "https://doi.org/10.1029/2009JA014326" },
      { label: "Newell et al. 2010, Space Weather 8 — predictive skill of four oval models", url: "https://doi.org/10.1029/2010SW000604" },
    ],
  },
  {
    status: "observed",
    chip: "Observed · the satellite is the instrument",
    index: "04",
    title: "A decaying orbit is a density measurement, and the spacecraft cancels out",
    summary:
      "Atmospheric drag makes an orbit shrink at a rate proportional to the local air density, so the ratio of two decay rates for the same object is the ratio of two densities — no accelerometer required.",
    mechanism:
      "Drag removes orbital energy at a rate set by the density of the neutral gas the spacecraft is flying through, its cross-sectional area, its mass and its drag coefficient. Those last three are folded into one number, the ballistic coefficient, which is usually the hardest thing to know. But for a single object over days it does not change — so if you take its decay rate during a storm and divide by its own quiet-time decay rate, the ballistic coefficient cancels exactly and what is left is the density ratio. The consequence is that a public catalogue of orbital elements is, quietly, a global thermospheric density instrument. The physics that de-orbits satellites is the physics that lets you measure why.",
    evidence:
      "Parker and Linares (2024) tracked drag decay across the LEO catalogue through the May 2024 storm. KANOPUS-V 3 had been decaying at roughly 38 metres per day before the storm; during it, the rate rose to 180 metres per day — a factor of about 4.7, and, by the argument above, a measured density enhancement. Oliveira, Zesta and Garcia-Sage (2025) followed 523 Starlink re-entries across 2020–2024 and showed that satellites re-enter faster when geomagnetic activity is higher and that re-entry-prediction error grows with it. Their sharpest case: Starlink-2601 crossed 276 km at 19:30 UT on 10 May 2024 and reached the Karman line at 16:09 UT on 12 May — 176 km of altitude in 1.86 days, and eleven days ahead of the prediction made from its last pre-storm elements.",
    onSite:
      "Every satellite here is propagated in your browser from public mean orbital elements. Select a low-perigee object and read the element epoch and its age: the further the prediction has marched from the fitted elements, the more the real atmosphere has had a chance to disagree with the model inside the propagator. That divergence is the same effect, seen from the other side.",
    limit:
      "This site does not yet have a thermospheric density layer, and its own archive of orbital elements began in August 2026 — so it holds nothing from May 2024 and cannot re-derive any of the numbers above. They are cited, not measured here. The propagator used in the browser is SGP4 on public mean elements: fine for teaching geometry, not an ephemeris for conjunction assessment or operations.",
    sources: [
      { label: "Parker &amp; Linares 2024, J. Spacecraft and Rockets 61(5), 1412–1416", url: "https://doi.org/10.2514/1.A36164" },
      { label: "Oliveira, Zesta &amp; Garcia-Sage 2025, Front. Astron. Space Sci. 12, 1572313", url: "https://doi.org/10.3389/fspas.2025.1572313" },
      { label: "He et al. 2023, Space Weather 21, e2023SW003521 — the February 2022 Starlink loss", url: "https://doi.org/10.1029/2023SW003521" },
    ],
  },
  {
    status: "observed",
    chip: "Observed depletion · chemistry doing the braking",
    index: "05",
    title: "After the storm the air was thinner than before it, and nitric oxide is why",
    summary:
      "A geomagnetic storm is not a spike in atmospheric density. It is a spike followed by a hole, and the hole is a chemistry result.",
    mechanism:
      "Storm energy deposited at high latitude heats the thermosphere and it expands, which is what raises density at a fixed altitude and drags satellites down. The same energy also drives nitrogen chemistry that produces nitric oxide. NO radiates strongly at 5.3 micrometres, straight out to space, and it is the upper atmosphere's most effective thermostat. Once the driving stops, that radiator keeps running — and it overshoots. The atmosphere cools past where it started and the post-storm thermosphere ends up less dense than the pre-storm thermosphere. A chemist will recognise the shape of this immediately: a fast exothermic input, a product that is itself the dominant loss channel, and a relaxation that undershoots its initial state.",
    evidence:
      "Ranjan et al. (2024) measured it for this storm. Swarm-C observed a thermospheric density depletion of about −23% on 12 May 2024 in the northern hemisphere relative to pre-storm conditions on 9 May — and this happened despite solar EUV flux at 24–36 nm being continuously enhanced throughout the event, which should have pushed density the other way. They report NO radiative cooling flux reaching 11.84 erg cm⁻² s⁻¹, an all-time high in the record they compare against, including the October 2003 Halloween storms.",
    onSite:
      "Not yet a layer. This one is honest homework rather than something you can switch on. The reason it is here is that it changes how you should read a drag or density curve anywhere else: if a model reproduces the peak and stops, it will be wrong in the opposite direction for days afterwards, and orbit predictions made during the recovery inherit that error.",
    limit:
      "This project's own reduction of NOAA's Whole Atmosphere Model for the same days shows a global-mean density at 400 km falling to 0.64 times the pre-storm baseline by 21:00 UT on 12 May — the same sign, on the same day. That is a consistency check, not a match: a global mean and a northern-polar single-satellite track are different quantities, and it should be read as corroboration of direction, nothing more.",
    sources: [
      { label: "Ranjan et al. 2024, JGR Space Physics 129, e2024JA033148", url: "https://doi.org/10.1029/2024JA033148" },
      { label: "Liu &amp; Lühr 2005, JGR 110 — CHAMP density during the Halloween storms", url: "https://doi.org/10.1029/2004JA010908" },
    ],
  },
  {
    status: "observed",
    chip: "Observed · one spacecraft, four links, one loop",
    index: "06",
    title: "The satellite built to measure the radiation belts missed the storm, found two new belts, and was then de-orbited by it",
    summary:
      "CIRBE is the whole causal chain compressed into one small spacecraft, and no diagram makes the point as well.",
    mechanism:
      "Follow the chain to its end and it closes on itself. The storm creates new trapped particle populations in the inner magnetosphere. The same storm heats and expands the thermosphere. A spacecraft in low Earth orbit is inside the second effect while trying to observe the first. Given enough expansion, the atmosphere that is the subject of one half of the story removes the instrument observing the other half.",
    evidence:
      "CIRBE — the Colorado Inner Radiation Belt Experiment, a 3U CubeSat built at the Laboratory for Atmospheric and Space Physics at the University of Colorado Boulder, carrying the REPTile-2 particle telescope, and flown through NASA's CubeSat Launch Initiative — was purpose-built to measure radiation-belt electrons. It went quiet on 15 April 2024 after an anomaly, twenty-five days before the storm, and observed none of it. It resumed measurements in mid-June and found two radiation belts that had formed while it was down: 1.3–5 MeV electrons around L = 2.5–3.5, a region normally swept clean of relativistic electrons by wave–particle scattering, and 6.8–20 MeV protons around L = 2. The electron belt was still there, apparently undisturbed, until a magnetic storm on 28 June perturbed the region; the proton belt looks more stable still. Then, in October 2024, CIRBE re-entered. NASA's own account of the mission states the cause plainly: the solar storm increased atmospheric drag on the CubeSat, which caused its orbit to decrease prematurely.",
    onSite:
      "Nothing on this site shows the 2024 belts. The Radiation belts layer here is a coupled model solution for the current environment, and it is not CIRBE data. The connection is on this page because it is the clearest single demonstration that the magnetospheric layers and the atmospheric layers are describing one system.",
    limit:
      "It is also the clearest demonstration of how thinly this storm was observed where it mattered most. The Van Allen Probes ended in 2019. For May 2024 there is no equatorial, pitch-angle-resolved, well-calibrated MeV electron dataset of that quality — what exists is a geostationary point, a few sweeping spacecraft, and a constellation at around L = 4.2. Everything between those samples is interpolation, and any picture of a smooth belt for those days is a model's opinion.",
    sources: [
      { label: "Li et al. 2025, JGR Space Physics 130, e2024JA033504", url: "https://doi.org/10.1029/2024JA033504" },
      { label: "NASA — CubeSat finds new radiation belts after the May 2024 solar storm", url: "https://science.nasa.gov/science-research/heliophysics/nasa-cubesat-finds-new-radiation-belts-after-may-2024-solar-storm/" },
    ],
  },
];

type CreditGroup = {
  kicker: string;
  heading: string;
  intro: string;
  entries: { title: string; body: string; url: string }[];
};

const CREDITS: CreditGroup[] = [
  {
    kicker: "PEOPLE WHO MEASURED THIS STORM",
    heading: "The published work these connections rest on",
    intro:
      "Every connection above exists because someone did the measurement and published it with enough detail to be checked. Named here in the order the links appear.",
    entries: [
      {
        title: "S. Tulasi Ram, B. Veenadhari and colleagues",
        body: "Established that the dayside magnetopause sat below geostationary orbit for roughly six continuous hours on 10–11 May 2024, that the bow shock briefly followed it in, and that a flare before the storm produced an HF blackout across the 2–12 MHz band. Space Weather 22, e2024SW004126 (2024).",
        url: "https://doi.org/10.1029/2024SW004126",
      },
      {
        title: "W. D. Fu, H. S. Fu, W. Z. Zhang, Y. Yu and J. B. Cao",
        body: "Beihang University. Determined the magnetopause compression directly, from beyond 10 to 5 Earth radii, by combining in-situ measurements from multiple spacecraft with ground magnetometer data. Geophysical Research Letters 52, e2024GL114040 (2025).",
        url: "https://doi.org/10.1029/2024GL114040",
      },
      {
        title: "Xiaojing Sun, Yixin Hao, Dianjun Zhang and colleagues",
        body: "Used GOES-16, GOES-18 and FY-4B simultaneously to resolve the geostationary environment by magnetic local time, and attributed the rapid dispersionless electron dropouts on the dayside and dawn flank to magnetopause shadowing. JGR Space Physics 131, e2026JA035141 (2026).",
        url: "https://doi.org/10.1029/2026JA035141",
      },
      {
        title: "Xinlin Li, Zheng Xiang, Yang Mei, Declan O'Brien, David Brennan, Hong Zhao, Daniel N. Baker and Michael A. Temerin",
        body: "Identified the two new radiation belts in CIRBE/REPTile-2 data after the spacecraft recovered. Xinlin Li leads the group at the Laboratory for Atmospheric and Space Physics and the Department of Aerospace Engineering Sciences at CU Boulder, where CIRBE was designed and built. JGR Space Physics 130, e2024JA033504 (2025).",
        url: "https://doi.org/10.1029/2024JA033504",
      },
      {
        title: "M. Grandin, E. Bruus, V. E. Ledvina and twelve co-authors",
        body: "Turned 696 public aurora reports from more than 30 countries into a citable scientific result, and showed the oval reached geomagnetic latitudes the operational models did not predict. It also names the storm: two names were proposed, the Mother's Day Storm and, in memory of Dr Jennifer Gannon, the Gannon Storm. Geoscience Communication 7, 297–316 (2024).",
        url: "https://doi.org/10.5194/gc-7-297-2024",
      },
      {
        title: "William E. Parker and Richard Linares",
        body: "MIT. Used the public two-line-element catalogue as a drag instrument through the storm and reported KANOPUS-V 3's decay rate rising from about 38 to 180 metres per day. They also showed the geomagnetic ap forecast under-predicted the onset badly at every lead time. Journal of Spacecraft and Rockets 61(5), 1412–1416 (2024).",
        url: "https://doi.org/10.2514/1.A36164",
      },
      {
        title: "Denny M. Oliveira, Eftyhia Zesta and Katherine Garcia-Sage",
        body: "NASA Goddard and the University of Maryland Baltimore County. Superposed-epoch analysis of 523 Starlink re-entries across the rising phase of solar cycle 25, including the Starlink-2601 case. Frontiers in Astronomy and Space Sciences 12, 1572313 (2025).",
        url: "https://doi.org/10.3389/fspas.2025.1572313",
      },
      {
        title: "Alok Kumar Ranjan, Dayakrishna Nailwal, M. V. Sunil Krishna, Akash Kumar and Sumanta Sarkhel",
        body: "IIT Roorkee. Measured the post-storm thermospheric overcooling with Swarm-C and tied it to record nitric-oxide radiative cooling, using TIMED/SABER for the emission. JGR Space Physics 129, e2024JA033148 (2024).",
        url: "https://doi.org/10.1029/2024JA033148",
      },
      {
        title: "Jianhui He, Elvira Astafyeva and ten co-authors",
        body: "Established what Swarm-A and GRACE-FO actually observed during the February 2022 storm that destroyed 38 of 49 newly launched Starlink satellites: neutral mass density up 110% and 120% respectively — and that six models' simulated enhancements for the same event differed from each other by up to 70%. Space Weather 21, e2023SW003521 (2023).",
        url: "https://doi.org/10.1029/2023SW003521",
      },
      {
        title: "Dr Jennifer L. Gannon, for whom the storm is named",
        body: "The May 2024 superstorm carries her name. Denny M. Oliveira, Mirko Piersanti, Maria-Theresia Walach and their co-editors dedicated the research collection on this storm to her, writing that her work established essential connections between magnetospheric physics and the protection of technological infrastructure on Earth — geomagnetically induced currents and ground magnetic disturbance, which is to say the last link in the chain, where space weather stops being an abstraction. Front. Astron. Space Sci. 12, 1742847 (2025).",
        url: "https://doi.org/10.3389/fspas.2025.1742847",
      },
      {
        title: "H. Liu and H. Lühr",
        body: "GFZ Potsdam. The CHAMP accelerometer analysis of the October 2003 Halloween storms that set the reference for what an extreme thermospheric density enhancement looks like. JGR 110, A09S29 (2005).",
        url: "https://doi.org/10.1029/2004JA010908",
      },
      {
        title: "E. Weiler, C. Möstl, E. E. Davies, A. M. Veronig and co-authors",
        body: "Showed that STEREO-A, at 0.956 AU, saw the storm's shock 2.57 hours before L1 did, and that geomagnetic indices derived from its beacon data would have forecast the storm's severity to within 8% — an argument for a monitor sunward of L1, made with a spacecraft that happened to be in the right place. Space Weather 23, e2024SW004260 (2025).",
        url: "https://doi.org/10.1029/2024SW004260",
      },
    ],
  },
  {
    kicker: "MODEL AND INSTRUMENT BUILDERS",
    heading: "The equations this site evaluates in your browser",
    intro:
      "Several layers here are somebody's published model, evaluated on live inputs. They are named in the method cards; the original papers are named here.",
    entries: [
      {
        title: "J.-H. Shue, P. Song, C. T. Russell and eight co-authors",
        body: "The 1998 magnetopause model. The Magnetopause layer on this site is their equation, nothing more: two published expressions for standoff distance and flaring, evaluated at every selected time from the current dynamic pressure and interplanetary Bz. It is a fit to observed boundary crossings — neither the truth nor a simulation. JGR 103, 17691–17700 (1998).",
        url: "https://doi.org/10.1029/98JA01103",
      },
      {
        title: "P. T. Newell, T. Sotirelis and S. Wing",
        body: "Johns Hopkins University Applied Physics Laboratory. OVATION Prime, built on years of DMSP particle precipitation data, is the basis of the operational auroral forecast this site draws. JGR 114, A09207 (2009); skill assessment in Space Weather 8 (2010).",
        url: "https://doi.org/10.1029/2009JA014326",
      },
      {
        title: "Gábor Tóth, Tamas I. Gombosi and the Center for Space Environment Modeling",
        body: "University of Michigan. The Space Weather Modeling Framework and its BATS-R-US magnetohydrodynamic core, with the solution-adaptive scheme of Kenneth G. Powell, Philip L. Roe, Timur J. Linde, Gombosi and Darren L. De Zeeuw. NOAA's operational geospace product is a configuration of this code. JGR 110, A12226 (2005); J. Comput. Phys. 154, 284–309 (1999).",
        url: "https://doi.org/10.1029/2005JA011126",
      },
      {
        title: "Frank Toffoletto, Stanislav Sazykin, Robert Spiro and Richard Wolf",
        body: "Rice University. The Rice Convection Model supplies the inner-magnetosphere and ring-current physics coupled into that operational framework. Space Science Reviews 107, 175–196 (2003).",
        url: "https://doi.org/10.1023/A:1025532008047",
      },
      {
        title: "A. J. Ridley, T. I. Gombosi and D. L. De Zeeuw",
        body: "The ionospheric electrodynamics solver that closes field-aligned currents in the same framework — the component that decides how the magnetosphere and the ionosphere talk to each other. Annales Geophysicae 22, 567–584 (2004).",
        url: "https://doi.org/10.5194/angeo-22-567-2004",
      },
      {
        title: "M.-C. Fok, A. Glocer, Q. Zheng, R. B. Horne, N. P. Meredith, J. M. Albert and T. Nagai",
        body: "NASA Goddard and the British Antarctic Survey. The Radiation Belt Environment model, whose electron phase-space solution is what the Radiation belts layer here displays. J. Atmos. Sol.-Terr. Phys. 73, 1435–1443 (2011).",
        url: "https://doi.org/10.1016/j.jastp.2010.09.033",
      },
      {
        title: "James R. Wait and Kenneth P. Spies",
        body: "National Bureau of Standards, 1964. Their exponential D-region profile — two parameters, a reflection height and a sharpness — is still how the lower ionosphere is described sixty years later, and it is what the D-region surface on this site evaluates. NBS Technical Note 300.",
        url: "https://doi.org/10.6028/NBS.TN.300",
      },
      {
        title: "E. D. Schmitter, and Neil R. Thomson, Craig J. Rodger and Mark A. Clilverd",
        body: "The flare response inside that D-region surface is not tuned for appearance. Its endpoints come from Thomson, Rodger and Clilverd's measurements of large flares and from Schmitter's VLF/LF amplitude and phase observations at a midlatitude site. Ann. Geophys. 31, 765–773 (2013); JGR 110, A06306 (2005).",
        url: "https://doi.org/10.5194/angeo-31-765-2013",
      },
      {
        title: "Jack C. Wang, Jia Yue, Sean Bruinsma, Masha Kuznetsova and colleagues",
        body: "NASA Goddard's Community Coordinated Modeling Center, with CNES and TU Delft. The open, multi-mission assessment of thermosphere models across 151 storms from 2001 to 2023 that this project used to choose what to trust. It finds DTM2020 best overall, followed by JB2008, and that MSIS models systematically underestimate density by about 20–30% during storm main and recovery phases — and recommends replacing MSIS as the standard reference for storm-time drag. Space Weather 24, e2025SW004782 (2026).",
        url: "https://doi.org/10.1029/2025SW004782",
      },
      {
        title: "L. A. Wilkerson, R. S. Weigel, A. Pulkkinen and co-authors",
        body: "George Mason University, NOAA, NCAR, NASA Goddard, the University of Cape Town and CIRES. Assembled measured geomagnetically induced currents from 47 sites and magnetometer data from 17 sites for this storm and scored three global magnetosphere models against them. Their numbers are quoted below, in the limits section, because they apply directly to a model this site displays. Space Weather 24, e2025SW004758 (2026).",
        url: "https://doi.org/10.1029/2025SW004758",
      },
    ],
  },
  {
    kicker: "THE UNGLAMOROUS HALF",
    heading: "Infrastructure that is cited far less often than it is used",
    intro:
      "None of the above works without a long-running observation stream, a catalogue, or a base map — maintained by people who are rarely named in the paper that uses their output.",
    entries: [
      {
        title: "Magnetic observatory operators, and INTERMAGNET",
        body: "Every geomagnetic index on this site — Kp, Dst, SYM-H, the storm scales — is a reduction of readings from ground magnetometers that individual institutes have kept calibrated and running, in some cases for over a century, through funding cycles and weather. INTERMAGNET is the consortium that makes their data interoperable and defines the definitive one-minute standard the storm papers above depend on.",
        url: "https://intermagnet.org/",
      },
      {
        title: "World Data Center for Geomagnetism, Kyoto",
        body: "Kyoto University produces and maintains Dst and SYM-H, the indices by which every storm since 1957 is ranked and compared. Every statement of the form 'the largest storm in twenty years' is a statement about their time series.",
        url: "https://wdc.kugi.kyoto-u.ac.jp/",
      },
      {
        title: "GFZ Helmholtz Centre for Geosciences, Potsdam",
        body: "Producers of the Kp index and its higher-cadence Hp successors, derived from a distributed network of observatories. Kp is the input that drives most empirical thermosphere models, including the ones this project measured against.",
        url: "https://www.gfz.de/en/section/geomagnetism/data-products-services/geomagnetic-kp-index",
      },
      {
        title: "NOAA Space Weather Prediction Center",
        body: "Nearly every live layer here — solar wind, GOES X-rays and particles, GloTEC, WAM-IPE, D-RAP, OVATION, the geospace model output, the scales and forecasts — is a NOAA SWPC product, published openly and free of charge, on a schedule, by forecasters who work shifts. This site is a viewer for their work.",
        url: "https://www.swpc.noaa.gov/",
      },
      {
        title: "NASA Community Coordinated Modeling Center",
        body: "The CCMC at Goddard Space Flight Center runs other people's models on request, for anyone, and keeps the results. It is the reason a model that would otherwise live on one research group's cluster can be evaluated, compared and reproduced by someone else — including the thermosphere assessment cited above.",
        url: "https://ccmc.gsfc.nasa.gov/",
      },
      {
        title: "CelesTrak, and Dr T. S. Kelso",
        body: "The orbital elements this site propagates come from CelesTrak, which Dr Kelso has run for decades and which is funded by donations. CelesTrak's curated catalogue is also what lets this site tell an operational spacecraft from an object that has been dead since the 1960s — a distinction the raw object type does not make. It is a small server doing work the field takes for granted; treat it accordingly.",
        url: "https://celestrak.org/",
      },
      {
        title: "Natural Earth — Tom Patterson and Nathaniel Vaughn Kelso",
        body: "The coastlines on the globe are Natural Earth, built and given to the public domain by cartographers who explicitly renounced any claim on it. Their terms say crediting the authors is unnecessary. It is necessary here, because a self-hosted globe with no metered tile service is the only reason this site can be free to run.",
        url: "https://www.naturalearthdata.com/",
      },
      {
        title: "The spacecraft, and the people who fly them",
        body: "DSCOVR and ACE at L1 and STEREO-A ahead of Earth for the solar wind; the GOES series for X-rays and energetic particles; ESA's Swarm, NASA and GFZ's GRACE-FO and GFZ's CHAMP for the accelerometer densities the drag models are scored against; JAXA's Arase, NASA and APL's Van Allen Probes and NASA's MMS for the inner magnetosphere; TIMED/SABER for the infrared cooling. Operations teams keep these running for years past their design lives, which is the only reason storm comparisons across decades are possible at all.",
        url: "https://www.nasa.gov/heliophysics/",
      },
    ],
  },
];

export function connectionsView(): string {
  return `
    <header class="content-hero">
      <p class="eyebrow">CONNECTIONS · CREDIT · WHAT THIS SITE CANNOT DO</p>
      <h1>The links you would otherwise miss.</h1>
      <p>Each layer on this site answers one question. The interesting physics is in how they constrain each other — a boundary that moves and empties a radiation belt, an atmosphere that expands and removes the spacecraft measuring it. This page states those links, names the people who made them knowable, and says plainly which ones this site can actually show you.</p>
    </header>

    <aside class="teaching-callout"><strong>One chain, seven measurable steps</strong>Southward interplanetary magnetic field → efficient coupling to Earth's field → dayside magnetopause compressed inward → ring current builds and Dst falls → auroral oval pushes equatorward → outer radiation belt drops out → thermosphere heats, expands, and drags satellites down. Every step has been measured independently. Most are already layers here. The connections below are the joints between them.</aside>

    <section class="method-section" aria-labelledby="connections-title">
      <div class="method-section-head">
        <p class="section-kicker">SIX CONNECTIONS</p>
        <h2 id="connections-title">Mechanism, evidence, and what you can see here</h2>
        <p>Open a card for the physics, the published measurement behind it, where it appears in the explorer, and what it still does not prove. The chip on each card describes the weakest link in that connection, not the strongest.</p>
      </div>
      <div class="method-grid">
        ${CONNECTIONS.map(connectionCard).join("")}
      </div>
    </section>

    <section class="processing-ledger" aria-labelledby="validation-title">
      <div><p class="section-kicker">CHECKED, WITH NUMBERS</p><h2 id="validation-title">What was verified behind this site, and what came back.</h2></div>
      <div class="processing-facts">
        <article><strong>0.64×</strong><span>Modelled global-mean density at 400 km by 12 May 21 UTC, against its pre-storm baseline — the post-storm hole, same sign and day as the Swarm-C measurement</span></article>
        <article><strong>2.5×</strong><span>Largest disagreement between two forecast cycles of the same atmosphere model at the same valid time, during storm recovery</span></article>
        <article><strong>3.4%</strong><span>Gap between the magnetopause standoff extracted from a physics run and the Shue boundary computed from that run's own drivers, on a quiet frame</span></article>
        <article><strong>0.21–0.65</strong><span>Correlation of three global magnetosphere models against measured ground magnetic disturbance for the May 2024 storm</span></article>
      </div>
      <p>Validation on a teaching site usually means nothing was checked. These are the checks that were actually run, with the results as they came out. Two of them are unflattering, which is why they are here rather than in a footnote. Where a check applies to a layer that has not shipped yet, the card says so.</p>
      <div class="method-grid">
        ${VALIDATIONS.map(methodCard).join("")}
      </div>
    </section>

    ${CREDITS.map(creditGroup).join("")}

    <section class="method-section" aria-labelledby="limits-title">
      <div class="method-section-head">
        <p class="section-kicker">WHERE THIS SITE IS WRONG, THIN, OR NOT BUILT</p>
        <h2 id="limits-title">Which links are measured, which are modelled, which are inference</h2>
        <p>The site labels every layer by evidence class. A page about connections is the right place to say the same thing about the connections themselves.</p>
      </div>
      <aside class="teaching-callout"><strong>The chain is real; this site's version of it is not one calculation</strong>Nothing here computes the chain end to end. Each link is a separate product with its own source, its own valid time, and its own evidence class, drawn on one globe because that is where they belong in space — not because a single model produced them. Co-display is context. Check the timestamps before relating fine structure between two layers.</aside>
      <aside class="teaching-callout"><strong>The model that draws the magnetosphere has a measured skill score, and it is moderate</strong>NOAA's operational geospace product is a configuration of the Space Weather Modeling Framework. For this exact storm, Wilkerson et al. (2026) scored it and two other global models against ground magnetometers: the horizontal magnetic-field perturbation correlated with the measurements at r between 0.21 and 0.65 across the twelve magnetometer sites where all three models produced output, and in their comparison MAGE over-predicts the disturbance while SWMF under-predicts it. Beautiful field lines are not a skill score. This number belongs beside any ground quantity derived from that model.</aside>
      <aside class="teaching-callout"><strong>A widely repeated number for this storm is a model output, not a measurement</strong>Parker and Linares' figure of density enhancements up to six times the baseline twelve hours prior, at 400 km, is stated in their paper as NRLMSISE-00 model output — it is the model's own field, mapped before and after. The observation in that paper is the decay-rate change of KANOPUS-V 3. This project originally treated the six-fold figure as an observed density and used it to validate a model reduction against, and that comparison was model against model. The claim has been withdrawn from this site rather than quietly restated.</aside>
      <aside class="teaching-callout"><strong>Two cut planes are not a volume, and a mapped shell is not a measurement</strong>The live magnetosphere model product is two perpendicular slices through Earth, not a solid object; anything that looks like a surface between them is an explicitly derived cue. The radiation-belt view that fills space is equatorial model flux repeated along ideal dipole field lines under stated assumptions — gyrotropy, north–south symmetry, a centred dipole. It is a way of seeing where the flux would be, not a measured torus, and it is not dose.</aside>
      <aside class="teaching-callout"><strong>Where a connection has no data here, it says so instead of drawing something</strong>This site holds nothing from May 2024: its aurora archive, its element archive and its atmospheric archive all began later. Every May 2024 number on this page is cited to someone else's published work. If a selected time falls outside a layer's real coverage, that layer disappears and reports the gap — it does not freeze the current field, sample a rendered image, or invent a forecast to keep the globe full. An empty globe is a scientific result.</aside>
      <aside class="teaching-callout"><strong>Operational boundary</strong>This is a teaching site under a non-profit. It is not a warning service, a collision-assessment tool, a navigation source, a dose calculator, or a communications-planning authority. For anything that matters operationally, follow NOAA SWPC and the responsible organisation.</aside>
    </section>
  `;
}

type MethodCardModel = {
  status: EvidenceClass;
  label: string;
  title: string;
  summary: string;
  rows: { term: string; detail: string }[];
  linkLabel: string;
  url: string;
};

const VALIDATIONS: MethodCardModel[] = [
  {
    status: "observed",
    label: "Check passed · corroborated by an independent measurement",
    title: "The post-storm density hole reproduces",
    summary:
      "An independent reduction of NOAA's Whole Atmosphere Model for 8–13 May 2024 shows the same undershoot Swarm-C measured, on the same day.",
    rows: [
      {
        term: "What was compared",
        detail:
          "Global-mean neutral mass density at 400 km from NOAA's archived Whole Atmosphere Model fields, reduced here, against Ranjan et al.'s published Swarm-C observation of a −23% post-storm depletion on 12 May 2024 in the northern hemisphere.",
      },
      {
        term: "Result",
        detail:
          "The reduced global mean falls to 0.64 times its pre-storm baseline by 21:00 UT on 12 May, and rises abruptly on the storm's timescale beforehand — 1.18× at 18:00 UT on 10 May, 1.75× three hours later, peaking at 2.63× at 16:00 UT on 11 May, roughly a day after the shock rather than at it.",
      },
      {
        term: "How far this goes",
        detail:
          "A cosine-latitude-weighted global mean and a single-satellite northern-polar track are different quantities. This is agreement in sign, magnitude class and timing — corroboration, not a match. The peak enhancement is quoted as a global mean because two independent computations of the field's local maximum disagreed here, most likely from a zero-denominator artifact near the poles, and an unresolved statistic should not be published as a result.",
      },
    ],
    linkLabel: "Ranjan et al. 2024 ↗",
    url: "https://doi.org/10.1029/2024JA033148",
  },
  {
    status: "model",
    label: "Check produced a limit, not a pass",
    title: "The atmosphere model disagrees with itself during recovery",
    summary:
      "Comparing forecast cycles that cover the same valid time turns the model's own storm-time error into a number, for free.",
    rows: [
      {
        term: "What was compared",
        detail:
          "NOAA's Whole Atmosphere Model runs four forecast cycles a day, each covering 51 hours, so most valid times are covered by more than one run. The freshest cycle's analysis frame was compared against the previous cycle's six-hour forecast for the same valid time, at 400 km global mean, across 9–13 May 2024.",
      },
      {
        term: "Result",
        detail:
          "In quiet conditions the two cycles agree to better than 2%. Through the storm and its recovery they separate, and at 12:00 UT on 12 May they differ by a factor of 2.5. Each cycle is internally smooth — this is not a spin-up artifact but two clean, continuous, mutually contradictory trajectories. The disagreement tracks where the geomagnetic driver forecast was wrong, and it is largest in recovery rather than at the peak.",
      },
      {
        term: "What follows from it",
        detail:
          "Any density figure from this archive has to state which cycle produced it, and averaging the cycles would manufacture a trajectory neither run produced. The honest presentation is the freshest cycle as the estimate and the cross-cycle spread as a visible band. This is the natural place to say that such a layer is a model and not an assimilation.",
      },
    ],
    linkLabel: "NOAA Whole Atmosphere Model ↗",
    url: "https://www.swpc.noaa.gov/products/wam-ipe",
  },
  {
    status: "empirical",
    label: "Cross-check between two independent methods",
    title: "An empirical boundary and a physics run agree in quiet conditions",
    summary:
      "The Shue boundary this site draws was tested against a magnetohydrodynamic run's own current layer, driven by the same solar wind.",
    rows: [
      {
        term: "What was compared",
        detail:
          "Along the Sun–Earth line in an archived physics run, the magnetopause current layer was located from the peak in current density, required to coincide with a drop in field magnitude and a rise in density, using a tolerance that scales with the local adaptive cell size. The Shue standoff was then computed from that same run's own upstream solar-wind conditions.",
      },
      {
        term: "Result",
        detail:
          "Model current layer at 10.25 Earth radii; Shue standoff 10.61. A gap of 0.36 Earth radii, or 3.4%. The bow shock came out at 13.25 Earth radii, consistent with a value obtained earlier by a different method. The frame is quiet and pre-storm, and both methods say so.",
      },
      {
        term: "What it does not establish",
        detail:
          "Agreement on a quiet frame is the anchor, not the finding. Under compression the two should diverge, and that divergence is the teaching content: an axisymmetric fit to past crossings cannot reproduce what a compressed, asymmetric boundary does. There is a hard external gate on the storm frames — published observations put the boundary inside about 5 Earth radii, so an extraction that does not go there is broken rather than interesting.",
      },
    ],
    linkLabel: "Shue et al. 1998 ↗",
    url: "https://doi.org/10.1029/98JA01103",
  },
  {
    status: "model",
    label: "Estimator validated against published rates · not against real elements",
    title: "Recovering a density ratio from orbital decay alone",
    summary:
      "The code that will turn a catalogue of orbits into a density measurement was tested against the published decay rates from this storm.",
    rows: [
      {
        term: "What was tested",
        detail:
          "The population estimator computes each object's own quiet-time decay rate, then reports the ratio to its storm-time rate. Because decay is linear in density and the ballistic coefficient is identical in numerator and denominator, the shell median of that ratio is a density enhancement, measured with satellites.",
      },
      {
        term: "Result",
        detail:
          "Against a synthetic population of thirty objects built to reproduce Parker and Linares' published KANOPUS-V 3 decay rates at that altitude, the estimator recovers 4.7 ± 0.3, and returns 1.0 ± 0.15 over a quiet period. It also refuses any interval shorter than three complete revolutions, because neutral density varies by roughly a factor of two between the day and night sides and a before-and-after comparison twelve hours apart measures the time of day rather than the storm.",
      },
      {
        term: "What it is not",
        detail:
          "This validates the arithmetic, not a measurement of May 2024. The synthetic population was constructed to the published rates, so recovering them is a test of the estimator, not independent confirmation of the physics. This project holds no orbital elements from May 2024 and will not fetch them; the real test is the next storm the archive sees. The layer is not live.",
      },
    ],
    linkLabel: "Parker &amp; Linares 2024 ↗",
    url: "https://doi.org/10.2514/1.A36164",
  },
];

function connectionCard(card: Connection): string {
  return `<details class="method-card">
    <summary><span class="layer-status ${card.status}">${card.chip}</span><strong>${card.index} · ${card.title}</strong><small>${card.summary}</small></summary>
    <div class="method-card-body">
      <dl>
        <div><dt>Mechanism</dt><dd>${card.mechanism}</dd></div>
        <div><dt>Evidence</dt><dd>${card.evidence}</dd></div>
        <div><dt>See it on this site</dt><dd>${card.onSite}</dd></div>
        <div><dt>What it still does not show</dt><dd>${card.limit}</dd></div>
      </dl>
      ${card.sources.map((source) => `<a href="${source.url}" target="_blank" rel="noreferrer">${source.label} ↗</a>`).join("<br />")}
    </div>
  </details>`;
}

function methodCard(card: MethodCardModel): string {
  return `<details class="method-card">
    <summary><span class="layer-status ${card.status}">${card.label}</span><strong>${card.title}</strong><small>${card.summary}</small></summary>
    <div class="method-card-body">
      <dl>
        ${card.rows.map((row) => `<div><dt>${row.term}</dt><dd>${row.detail}</dd></div>`).join("")}
      </dl>
      <a href="${card.url}" target="_blank" rel="noreferrer">${card.linkLabel}</a>
    </div>
  </details>`;
}

function creditGroup(group: CreditGroup): string {
  return `<section class="method-section">
    <div class="method-section-head">
      <p class="section-kicker">${group.kicker}</p>
      <h2>${group.heading}</h2>
      <p>${group.intro}</p>
    </div>
    <div class="source-grid">
      ${group.entries
        .map(
          (entry) =>
            `<article class="source-card"><span class="section-kicker">CREDIT</span><h2>${entry.title}</h2><p>${entry.body}</p><a href="${entry.url}" target="_blank" rel="noreferrer">Open source ↗</a></article>`,
        )
        .join("")}
    </div>
  </section>`;
}
