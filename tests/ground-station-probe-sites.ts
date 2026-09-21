/**
 * The stations the rendered-pixel guard probes, and why these ones.
 *
 * The render probe asks a question about colour: is the map under this pin
 * land, and is the map ninety degrees east — where the quarter-turn would have
 * put it — sea? That only works where neither point sits on a mixed pixel. The
 * painted map is 2048 px wide, so one pixel is about 19 km at the equator, and
 * a station a few kilometres inland reads as part coast and part sea.
 *
 * Choosing by eye got this wrong twice. Dongara and Svalbard are within a few
 * kilometres of a shore; Sioux Falls looks like the middle of a continent but
 * the point ninety degrees east of it is twenty kilometres off the coast of
 * Asturias. Both produced a land reading and a sea reading that overlapped.
 *
 * So the list is chosen by measurement, and `ground-stations-geography.test.ts`
 * re-measures it from the vendored coastlines on every run. `marginKm` is the
 * smaller of the two clearances — station to coast, and antipode-east to coast
 * — and every entry has enough of it to cover the probe patch several times.
 * Add a station here only with its measured margin.
 */
export interface RenderProbeSite {
  id: string;
  /** Why it is unambiguous, for a reader who does not want to run the test. */
  note: string;
  /** Smaller of (station to coast) and (ninety degrees east to coast), in km. */
  marginKm: number;
}

/**
 * Margin floor. At roughly 19 km per painted pixel this is about ten pixels of
 * clear water and clear land on either side of every reading.
 */
export const MINIMUM_PROBE_MARGIN_KM = 200;

export const RENDER_PROBE_SITES: RenderProbeSite[] = [
  { id: "ga-alice-springs", note: "the centre of Australia; ninety east is the South Pacific", marginKm: 895 },
  { id: "nasa-nsn-white-sands-ws1", note: "the New Mexico desert; ninety east is the mid-Atlantic", marginKm: 620 },
  { id: "ccmeo-prince-albert", note: "the Saskatchewan interior; ninety east is the Norwegian Sea", marginKm: 423 },
  { id: "isro-shadnagar", note: "the Deccan plateau; ninety east is the Pacific", marginKm: 260 },
  { id: "nasa-nsn-alaska-as1", note: "interior Alaska; ninety east is the Labrador Sea", marginKm: 242 },
  { id: "nasa-dsn-goldstone-dss14", note: "the Mojave desert; ninety east is the mid-Atlantic", marginKm: 216 },
];

export const RENDER_PROBE_IDS = RENDER_PROBE_SITES.map((site) => site.id);
