import { evidenceBadge, type Evidence } from './learning-evidence';
import referenceUrl from './learning-reference.json?url';

export const LEARNING_SOURCES = {
  wam: ['NOAA WAM-IPE product and model', 'https://www.spaceweather.gov/products/wam-ipe'],
  tec: ['NOAA GloTEC product and assimilation', 'https://www.spaceweather.gov/products/glotec'],
  drap: ['NOAA D-RAP: definition, model and archive', 'https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap'],
  aurora: ['NOAA OVATION: model, validation and viewing limits', 'https://www.spaceweather.gov/products/aurora-30-minute-forecast'],
  wind: ['NOAA solar-wind instruments and products', 'https://www.spaceweather.gov/products/solar-wind'],
  xray: ['NOAA GOES X-ray flux', 'https://www.spaceweather.gov/products/goes-x-ray-flux'],
  proton: ['NOAA GOES proton flux', 'https://www.spaceweather.gov/products/goes-proton-flux'],
  electron: ['NOAA GOES electron flux and alert definition', 'https://www.spaceweather.gov/products/goes-electron-flux'],
  swmf: ['NOAA SWMF magnetosphere cuts and model limits', 'https://www.spaceweather.gov/products/geospace-magnetosphere-movies'],
  rbe: ['NASA CCMC Radiation Belt Environment model', 'https://ccmc.gsfc.nasa.gov/models/SWMF~RB%3DRBE~20180525/'],
  convection: ['Liemohn et al. (2001): inner-magnetosphere modelling', 'https://doi.org/10.1029/2000JA000326'],
  nguyen: ['Nguyen et al. (2022): near-cusp boundary fit', 'https://doi.org/10.1029/2021JA029776'],
  shue: ['Shue et al. (1998): magnetopause size and shape', 'https://doi.org/10.1029/98JA01103'],
  gannon: ['Tulasi Ram et al. (2024): Gannon storm, six-hour compression', 'https://doi.org/10.1029/2024SW004126'],
  weiler: ['Weiler et al. (2025): May 2024 sub-L1 observation and prediction', 'https://doi.org/10.1029/2024SW004260'],
  cirbe: ['Li et al. (2025): CIRBE belts after 10 May 2024', 'https://doi.org/10.1029/2024JA033504'],
  thomson: ['Thomson et al. (2005): effective D-region reflection height', 'https://doi.org/10.1029/2005JA011008'],
  assessment: ['Wang et al. (2026): 151-storm CCMC model assessment', 'https://doi.org/10.1029/2025SW004782'],
  he: ['He et al. (2023): February 2022 density comparison', 'https://pure.tudelft.nl/ws/portalfiles/portal/160425445/Space_Weather_2023_He_Comparison_of_Empirical_and_Theoretical_Models_of_the_Thermospheric_Density_Enhancement_During.pdf'],
  wilkerson: ['Wilkerson et al. (2026): May 2024 solar-wind input comparison', 'https://doi.org/10.1029/2025SW004758'],
  dst: ['Kyoto Dst: index definition and archived values', 'https://wdc.kugi.kyoto-u.ac.jp/dstdir/'],
  rbspice: ['RBSPICE instrument: in-situ ring-current particles', 'https://doi.org/10.1007/s11214-013-9965-x'],
  igrf: ['IAGA IGRF coefficients and model', 'https://www.ncei.noaa.gov/products/international-geomagnetic-reference-field'],
  dungey: ['Dungey (1961): interplanetary field and auroral zones', 'https://doi.org/10.1103/PhysRevLett.6.47'],
  chapman: ['Chapman (1931): absorption and ionisation', 'https://doi.org/10.1088/0959-5309/43/1/305'],
  wait: ['Wait & Spies (1964), NBS Technical Note 300', 'https://doi.org/10.6028/NBS.TN.300'],
  local: ['Teaching calculations and declared provenance gaps', referenceUrl],
} as const;
export type SourceId = keyof typeof LEARNING_SOURCES;
export function sourceLinks(ids: readonly SourceId[], compact = false): string {
  return ids.map(id => {
    const [label, url] = LEARNING_SOURCES[id];
    return `<a href="${url}" target="_blank" rel="noopener" aria-label="${label}">${compact ? id.toUpperCase() : label}</a>`;
  }).join(' · ');
}
export const LAYER_SOURCES: Record<string, SourceId[]> = {
  thermosphere: ['wam', 'he', 'assessment', 'local'], ionosphere: ['wam', 'tec', 'wait', 'local'],
  plasmasphere: ['convection', 'local'], 'radiation-belts': ['rbe', 'electron', 'igrf', 'cirbe', 'local'],
  'ring-current': ['convection', 'dst', 'rbspice', 'local'], magnetopause: ['shue', 'nguyen', 'gannon', 'local'],
  'solar-wind': ['wind', 'wilkerson', 'weiler', 'local'], 'peak-surfaces': ['wam', 'local'],
  'd-region': ['drap', 'wait', 'thomson', 'local'], 'ground-track-footprint': ['local'],
  'substorm-chain': ['dungey', 'convection', 'dst', 'aurora', 'local'],
};
export const WEATHER_SOURCES: Record<string, SourceId[]> = {
  photons: ['xray', 'drap'], particles: ['proton', 'rbe'], wind: ['wind', 'dungey'],
  compression: ['shue', 'nguyen', 'gannon'], layers: ['wam', 'tec', 'drap'],
  systems: ['drap', 'he', 'electron'], aurora: ['aurora'], dimensions: ['wam', 'tec', 'drap', 'swmf'],
  dungey: ['dungey', 'shue', 'convection', 'dst', 'aurora'], engine: ['swmf', 'nguyen', 'local'],
  mechanisms: ['dungey', 'chapman', 'drap', 'convection', 'igrf', 'dst', 'local'],
};
export function learningSources(ids: readonly SourceId[]): string {
  return `<section class="learning-sources"><h2>Sources and scope</h2><p>Product links explain the quantity and method; they do not verify an undated sample. Worked values and historical examples are not live readings. Individual provenance notes identify missing epochs or supporting records.</p><ul>${ids.map(id => `<li>${sourceLinks([id])}</li>`).join('')}</ul></section>`;
}

type FactProvenance = { evidence: Evidence; source: SourceId; context: string };
const fact = (evidence: Evidence, source: SourceId, context: string): FactProvenance => ({ evidence, source, context });
// Explicit per fact, never inherited from the page's heterogeneous media badge.
export const LAYER_FACTS: Record<string, FactProvenance[]> = {
  thermosphere: [
    fact('model', 'local', 'Fixed worked calculation; quiet-time reference density, no observation epoch.'),
    fact('model', 'local', 'Gannon, May 2024. Exact WAM frame and averaging record not retained here; quoted ratio is not independently reproducible from this page.'),
    fact('model', 'local', 'Undated site model sample; frame and location record missing. Do not treat as a current global spread.'),
    fact('observed', 'he', 'Historical outcome: launch on 3 February 2022; not a current loss forecast.'),
  ],
  ionosphere: [fact('model','local','Cold-plasma calculation at GPS L1; not a measured link error.'), fact('model','local','Plasma-frequency relationship; Nₑ in m⁻³, no event epoch.'), fact('schematic','drap','Qualitative teaching rule; frequency, path and conditions still matter.'), fact('model','wam','Site integration extent; product domain, not the physical edge of plasma.')],
  plasmasphere: [fact('model','local','Volland–Stern teaching comparison, Kp 2 to 8; no event epoch.'), fact('model','local','Site sample recorded 14 August 2026: 25 frames, Kp ≤ 2.89. The original frame series is not retained here; date comes from the chart’s contemporaneous source note.'), fact('model','local','Chosen density contour; not a universal measured boundary.'), fact('schematic','rbe','Mechanism summary; no event-specific flux prediction.')],
  'radiation-belts': [fact('observed','electron','Operational alert threshold for a local observed channel; not a flux measured now.'), fact('model','local','IGRF calculation at 500 km; field epoch and minimisation record not retained here.'), fact('model','igrf','Eccentric-dipole approximation; coefficient epoch must accompany a precise recalculation.'), fact('observed','cirbe','CIRBE after 10 May 2024; Li et al. (2025), Figures 1–3 and section 3.2. Local spacecraft samples, not a directly measured global belt.')],
  'ring-current': [fact('observed','dst','Index series since 1957; no particular current sample shown.'), fact('model','local','Approximate DPS inference; the quoted accuracy has no validation dataset attached here.'), fact('model','local','Worked adiabatic example: 10 × (8/4)³ = 80 keV.'), fact('schematic','rbspice','Illustrative composition; not a universal ratio or a current instrument reading.')],
  magnetopause: [fact('empirical','local','Quiet/strong-driving worked comparison; exact input pair not retained here.'), fact('model','local','Geosynchronous orbital radius from Earth’s centre, rounded; not altitude.'), fact('empirical','gannon','10–11 May 2024; boundary inference in the published event study, not a directly imaged global surface.'), fact('observed','nguyen','Historical crossing sample used for the 2022 empirical fit; not a current surface.')],
  'solar-wind': [fact('observed','local','Undated site latency sample; measurement interval is missing. Not a latency guarantee.'), fact('model','local','Proton dynamic pressure: n in cm⁻³ and V in km/s; helium contribution excluded.'), fact('schematic','dungey','Coupling rule of thumb; southward Bz is not the only coupling parameter.'), fact('composite','weiler','10 May 2024: observed STEREO-A shock lead, plus a retrospective Dst prediction comparison. The 8% is this event’s result, not general forecast skill.')],
  'peak-surfaces': [fact('model','wam','Peak-height definition; no current height supplied.'), fact('model','local','Plasma-frequency relationship, not a live sounding.'), fact('schematic','local','Site display comparison, not an atmospheric measurement.'), fact('model','wam','Description of retained model statistics; no value at a selected time.')],
  'd-region': [fact('empirical','drap','Published absorption relationship; f and HAF in the same frequency units.'), fact('empirical','local','Worked ratio: (20/5)^1.5 = 8, same HAF and path convention.'), fact('empirical','drap','Band/threshold definition. Below 1 dB is not zero absorption.'), fact('empirical','thomson','4 November 2003 flare: VLF-inferred effective reflection height h′, not a physical D-layer edge. The site uses these as response-model endpoints.')],
  'ground-track-footprint': [fact('model','local','Worked 94-minute circular example; not a selected spacecraft pass.'), fact('model','local','Ideal orbital-plane geometry; prograde/retrograde convention as stated.'), fact('model','local','Spherical calculation at h=500 km, masks 0° and 10°; not an antenna coverage model.'), fact('schematic','local','Line-of-sight interpretation; no link-budget claim.')],
};
export function factProvenance(page: string, index: number): string {
  const p = LAYER_FACTS[page]?.[index];
  if (!p) throw new Error(`Missing fact provenance: ${page}/${index}`);
  return `<div class="fact-provenance">${evidenceBadge(p.evidence)}<p>${p.context}</p>${sourceLinks([p.source], true)}</div>`;
}

const WEATHER_FACTS: Record<string, FactProvenance[]> = {
  photons: [fact('model','local','Sun–Earth light travel time, rounded; not advance notice after the light is observed.'), fact('schematic','drap','Typical absorbing-region heights; conditions and frequency matter.'), fact('schematic','drap','Flare-driven absorption is on the daylit side; polar proton absorption is a separate mechanism.'), fact('schematic','drap','Simplified recovery example, not a guaranteed restoration time; use the event product.')],
  particles: [fact('observed','proton','Instrument location; no current flux shown.'), fact('observed','electron','Instrument channel description; no current flux shown.'), fact('schematic','proton','Typical arrival range; not an event forecast.'), fact('schematic','local','No measured global SEP field is ingested by this site; this does not deny the existence of scientific models.')],
  wind: [fact('schematic','wind','Rounded observing location, not an exact spacecraft position.'), fact('model','wind','Typical propagation estimate; variable speed and geometry change the lead time.'), fact('observed','wind','Measured quantities at the instrument; no sample at a stated time shown here.'), fact('schematic','dungey','Coupling mnemonic; other solar-wind parameters matter too.')],
  compression: [fact('empirical','shue','Typical inferred dayside radius, not a current boundary.'), fact('empirical','shue','Illustrative storm value; events differ and can compress further.'), fact('model','local','Rounded orbital radius from Earth’s centre, not altitude.'), fact('observed','wind','Input quantity names, not a current reading. IMF also affects the fitted boundary.')],
  layers: [fact('schematic','drap','Typical heights; not fixed boundaries.'), fact('schematic','wam','Typical peak height; not a current sounding.'), fact('schematic','wam','Typical peak height; not a current sounding.'), fact('assimilated','tec','Description of the column product; no current TEC value.')],
  systems: [fact('schematic','drap','Mechanism and approximate travel time, not an outage forecast.'), fact('schematic','rbe','Mechanism only; shielding and device response determine risk.'), fact('schematic','he','Mechanism only; ballistic properties determine orbit response.'), fact('schematic','wilkerson','Mechanism only; ground conductivity and network geometry also matter.')],
  aurora: [fact('schematic','aurora','Representative emission range; not a measured height now.'), fact('observed','aurora','Oxygen emission-line identification, not a brightness measurement or forecast.'), fact('observed','aurora','Oxygen emission-line identification, not a brightness measurement or forecast.'), fact('schematic','aurora','Magnetic organisation, not a location forecast.')],
  dimensions: [fact('model','wam','Product geometry; forecast values require their own issue and valid times.'), fact('assimilated','tec','Product geometry; no vertical density profile inferred from this total.'), fact('empirical','drap','Product geometry and nowcast method, not a direct absorption measurement.'), fact('model','swmf','Published cut geometry; no measured 3-D field.')],
};
export function weatherFactProvenance(page: string, index: number): string {
  const p = WEATHER_FACTS[page]?.[index];
  if (!p) throw new Error(`Missing weather fact provenance: ${page}/${index}`);
  return `<div class="fact-provenance">${evidenceBadge(p.evidence)}<p>${p.context}</p>${sourceLinks([p.source], true)}</div>`;
}
