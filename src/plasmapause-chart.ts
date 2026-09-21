/**
 * The plasmapause: the moving edge of the cold plasma, drawn as a curve.
 *
 * Why this exists. The plasmasphere layer draws a cloud of grains seeded from
 * a rotationally symmetric distribution and then rigidly rotated, and rotating
 * a symmetric cloud about its own symmetry axis returns an identical picture.
 * Measured on live artifacts 2026-08-14: at L = 2, the bright core, density
 * varies 1.16× across all 24 h of local time and 1.10× between frames — about
 * 1% of the colour ramp either way. The owner's reaction to the layer was that
 * it "looks like a static field that rotates", and in its brightest region it
 * provably is one.
 *
 * What is NOT the problem: the colour ramp. It spans 1–3,000 cm⁻³ and the data
 * occupies 87% of it. Rescaling would buy nothing.
 *
 * What IS happening, and is being thrown away: **the plasmapause moves.** On
 * the 25-frame window published 2026-08-14, with Kp never exceeding 2.89, the
 * midnight boundary ranged over L 4.14–4.51 — **2,319 km** of travel — and dusk
 * sat consistently further out than midnight (4.55 against 4.43 in a sampled
 * frame), which is the dusk bulge every textbook draws. Those figures are dated
 * because the feed republishes every two hours and they move with it; an
 * earlier reading of the same window gave 1,930 km. What does not move is the
 * conclusion: this is kilometres of boundary motion on a QUIET window, none of
 * it legible in a cloud of grains and all of it legible as a curve.
 *
 * `plasmapauseMotion()` therefore computes the range from whatever frames are
 * published rather than carrying a constant, and the tests pin it against a
 * synthetic ring so a live feed drifting cannot turn them red.
 *
 * The artifact publishes it directly: `plasmapauseLByMlt` (48 values, one per
 * half-hour of magnetic local time) per frame, with `steepestGradientLByMlt`
 * beside it as the independent check the pipeline computes on purpose.
 * Nothing here fits, smooths or invents anything.
 */

export interface PlasmapauseFrame {
  validAt: string;
  kp: number;
  /**
   * 48 values, MLT 0 (midnight) increasing eastward in half-hour steps. The
   * publisher's own type allows nulls — a local time where no crossing of the
   * contour was found — and a null must break the ring rather than be drawn
   * as L 0, which would spike the boundary into the Earth.
   */
  plasmapauseLByMlt: (number | null)[];
  /** The independent check published beside it. */
  steepestGradientLByMlt?: (number | null)[];
  plume?: { present: boolean; peakMltHours: number; peakL: number };
  totalContentPerWb?: number;
}

export interface PlasmapausePoint {
  mltHours: number;
  lRe: number;
  x: number;
  y: number;
}

export interface PlasmapauseRingGeometry {
  /** The boundary, as a closed polygon in view coordinates. */
  boundary: PlasmapausePoint[];
  /** The steepest-gradient check, where published. */
  check: PlasmapausePoint[];
  /** Circles of constant L, for reading a radius off the picture. */
  rings: Array<{ lRe: number; radius: number }>;
  centre: { x: number; y: number };
  /**
   * The L at the rim of the plot. Everything the chart draws is inside it, and
   * the outermost `rings` entry sits on it, so no mark is ever outside a ruler.
   */
  rimL: number;
  /** Earth, at L 1 on this plot's own scale, so the renderer keeps no second copy. */
  earthRadius: number;
  /** Where the plume peaks, when the frame has one. */
  plume: { x: number; y: number; lRe: number; mltHours: number } | null;
  minimumL: number;
  maximumL: number;
}

/** Radius of the drawn L, in view units. Linear in L — this is a plot, not the globe. */
function radiusFor(lRe: number, rimL: number, extent: number): number {
  return (Math.max(0, lRe) / rimL) * extent;
}

/** Constant-L circles are drawn every 2 L, which is the ruler this plot reads by. */
const L_SHELL_STEP = 2;

/**
 * HOW FAR OUT THE PLOT HAS TO REACH — measured from the frame, not assumed.
 *
 * This was a hard-coded `maximumL = 7`, and on the real published artifact that
 * put a drawn mark OUTSIDE the picture's own ruler. The steepest-gradient check
 * saturates at L 7.95 — the second-from-last node of the model's L 2.0–8.0 grid
 * — somewhere in the pre-midnight sector on all 25 frames published 2026-08-26,
 * while the 50 cm⁻³ boundary beside it never leaves L 4.3–4.9. At a rim of 7
 * that lobe was drawn past the outermost L ring, past the extent, and (since
 * the SVG carries `overflow: visible` for the dial labels) outside the plot box
 * altogether, over the 18 MLT tick. A reader has no radius to read it against,
 * and it lands exactly where the lede has just told them to look for the dusk
 * bulge.
 *
 * So the rim is derived from what will actually be drawn — boundary, check and
 * plume — rounded up to the next 2 L so the ring set stays a whole-number
 * ruler, with a floor of 6 so a quiet frame is not zoomed into meaninglessness.
 */
export function plasmapauseRimL(frame: PlasmapauseFrame): number {
  const drawn: number[] = [];
  for (const value of frame.plasmapauseLByMlt) if (value !== null && Number.isFinite(value)) drawn.push(value);
  for (const value of frame.steepestGradientLByMlt ?? []) if (value !== null && Number.isFinite(value)) drawn.push(value);
  if (frame.plume?.present && Number.isFinite(frame.plume.peakL)) drawn.push(frame.plume.peakL);
  const needed = drawn.length > 0 ? Math.max(...drawn) : 0;
  return Math.max(6, Math.ceil(needed / L_SHELL_STEP) * L_SHELL_STEP);
}

/**
 * Where a magnetic local time sits on the dial, at a given radius.
 *
 * EXPORTED so the ring and the labels that name its quadrants cannot drift
 * apart — because they already had. `plasmapauseRingGeometry` was corrected to
 * noon-up / midnight-down and its comment records the bug it was corrected
 * FROM: a −π/2 phase with a negated cosine, which puts every quadrant
 * backwards. The MLT tick labels drawn beside it in main.ts still carried that
 * original formula, so the live page drew a boundary with midnight at the
 * bottom underneath a label reading "00 MLT" at the TOP, and the dusk bulge on
 * the left underneath a "18" on the right. Every quadrant of the picture was
 * named backwards, which on a plasmapause chart teaches the opposite of the
 * physics: the bulge is a DUSK feature and the label said dawn.
 *
 * Found 2026-08-26 while sizing the chart down — at 1,018 px the labels were
 * far enough from the curve to read as decoration. One formula, one export,
 * one test that checks the label and the curve agree at all four cardinals.
 */
export function plasmapauseDialPoint(
  mltHours: number,
  radius: number,
  centre: { x: number; y: number },
): { x: number; y: number } {
  // Screen y grows downward, so midnight (theta = 0) is +r in y — the bottom.
  const theta = (mltHours / 24) * Math.PI * 2;
  return { x: centre.x + radius * Math.sin(theta), y: centre.y + radius * Math.cos(theta) };
}

/**
 * The boundary in the equatorial plane, looking down from magnetic north.
 *
 * **Midnight at the bottom, noon at the top, dusk to the left.** That is the
 * convention every magnetospheric figure uses, and putting the Sun at the top
 * is what makes the dusk bulge appear on the side a reader expects it.
 */
export function plasmapauseRingGeometry(
  frame: PlasmapauseFrame,
  size = 240,
  rimL = plasmapauseRimL(frame),
): PlasmapauseRingGeometry {
  const centre = { x: size / 2, y: size / 2 };
  const extent = size / 2 - 18;
  const project = (mltHours: number, lRe: number): PlasmapausePoint => {
    // The standard magnetic-local-time dial seen from magnetic north: noon at
    // the top, midnight at the bottom, dusk to the LEFT and dawn to the right.
    // Screen y grows downward, so midnight (theta = 0) is +r in y.
    //   x = cx + r sin(theta),  y = cy + r cos(theta)
    // The first version of this used a −pi/2 phase with a negated cosine and
    // put every quadrant backwards — midnight at the top, dusk on the dawn
    // side. Its own tests caught it; the arithmetic is spelled out here so the
    // next reader can check it against the four cardinal times rather than
    // trusting the phase.
    const radius = radiusFor(lRe, rimL, extent);
    return { mltHours, lRe, ...plasmapauseDialPoint(mltHours, radius, centre) };
  };
  const step = 24 / Math.max(1, frame.plasmapauseLByMlt.length);
  const projectAll = (source: readonly (number | null)[]) => source.flatMap((lRe, index) =>
    lRe === null || !Number.isFinite(lRe) ? [] : [project(index * step, lRe)]);
  const boundary = projectAll(frame.plasmapauseLByMlt);
  const check = projectAll(frame.steepestGradientLByMlt ?? []);
  const values = frame.plasmapauseLByMlt.filter((value): value is number => value !== null && Number.isFinite(value));
  return {
    boundary,
    check,
    rings: Array.from(
      { length: Math.floor(rimL / L_SHELL_STEP) },
      (_, index) => (index + 1) * L_SHELL_STEP,
    ).map((l) => ({ lRe: l, radius: radiusFor(l, rimL, extent) })),
    centre,
    rimL,
    earthRadius: radiusFor(1, rimL, extent),
    plume: frame.plume?.present
      ? { ...project(frame.plume.peakMltHours, frame.plume.peakL), lRe: frame.plume.peakL, mltHours: frame.plume.peakMltHours }
      : null,
    minimumL: values.length ? Math.min(...values) : 0,
    maximumL: values.length ? Math.max(...values) : 0,
  };
}

/** An SVG path for a closed ring of projected points. */
export function ringPath(points: readonly PlasmapausePoint[]): string {
  if (points.length < 3) return "";
  return `${points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ")} Z`;
}

/**
 * How far the boundary moved across the published window, at the two local
 * times that matter: midnight, where the plasmapause is sharpest and erosion
 * shows first, and dusk, where the bulge lives.
 */
export function plasmapauseMotion(frames: readonly PlasmapauseFrame[]): {
  midnight: { minimumL: number; maximumL: number; travelKm: number };
  dusk: { minimumL: number; maximumL: number; travelKm: number };
  kp: { minimum: number; maximum: number };
} | null {
  const usable = frames.filter((frame) => frame.plasmapauseLByMlt.length > 0);
  if (usable.length < 2) return null;
  const EARTH_RADIUS_KM = 6371;
  const at = (frame: PlasmapauseFrame, mltHours: number) => {
    const index = Math.round((mltHours / 24) * frame.plasmapauseLByMlt.length) % frame.plasmapauseLByMlt.length;
    const value = frame.plasmapauseLByMlt[index];
    return value === null || value === undefined || !Number.isFinite(value) ? null : value;
  };
  const span = (mltHours: number) => {
    const values = usable.map((frame) => at(frame, mltHours)).filter((v): v is number => v !== null);
    if (values.length === 0) return { minimumL: 0, maximumL: 0, travelKm: 0 };
    const minimumL = Math.min(...values);
    const maximumL = Math.max(...values);
    return { minimumL, maximumL, travelKm: (maximumL - minimumL) * EARTH_RADIUS_KM };
  };
  const kps = usable.map((frame) => frame.kp).filter((value) => Number.isFinite(value));
  return {
    midnight: span(0),
    dusk: span(18),
    kp: { minimum: Math.min(...kps), maximum: Math.max(...kps) },
  };
}

/** One sentence stating what the picture shows, for the label and the caption. */
export function plasmapauseSummary(frames: readonly PlasmapauseFrame[]): string {
  const motion = plasmapauseMotion(frames);
  if (!motion) return "No plasmapause boundary is published in this release.";
  return `Plasmapause across ${frames.length} published frames: midnight L ${motion.midnight.minimumL.toFixed(2)}`
    + `–${motion.midnight.maximumL.toFixed(2)} (${Math.round(motion.midnight.travelKm).toLocaleString("en-US")} km of travel), `
    + `dusk L ${motion.dusk.minimumL.toFixed(2)}–${motion.dusk.maximumL.toFixed(2)}, over Kp `
    + `${motion.kp.minimum.toFixed(2)}–${motion.kp.maximum.toFixed(2)}.`;
}

/**
 * WHAT THE VIOLET CURVE IS DOING OUT THERE, SAID OUT LOUD.
 *
 * The check is drawn because it is published and because hiding a disagreement
 * between two methods is the one thing a chart offering an "independent check"
 * must not do. But on the live artifact the disagreement is enormous and it is
 * in the worst possible place: the check runs to the outer edge of the model's
 * traced grid in the pre-midnight sector — the same sector the reader has just
 * been told to look at for the dusk bulge — while the boundary stays near
 * L 4.5. Drawn silently, that lobe reads as the bulge, or as a plume, and is
 * neither. Out there the gradient search has reached the edge of the domain
 * rather than found a plasmapause.
 *
 * Returns null when the two curves are within 1 L of each other, because then
 * there is nothing a reader could misread and a sentence about it would be
 * noise. `domainMaxL` is the outermost shell of the publisher's own grid, read
 * from the bundle rather than assumed; without it the note still states the
 * separation, it just does not name the cause.
 */
export function plasmapauseCheckNote(frame: PlasmapauseFrame, domainMaxL: number | null = null): string | null {
  const check = frame.steepestGradientLByMlt ?? [];
  const step = 24 / Math.max(1, check.length);
  let peakL = -Infinity;
  let peakMlt = 0;
  for (let index = 0; index < check.length; index += 1) {
    const value = check[index];
    if (value === null || value === undefined || !Number.isFinite(value)) continue;
    if (value > peakL) { peakL = value; peakMlt = index * step; }
  }
  if (!Number.isFinite(peakL)) return null;
  const boundary = frame.plasmapauseLByMlt.filter((v): v is number => v !== null && Number.isFinite(v));
  if (boundary.length === 0) return null;
  const widest = Math.max(...boundary);
  if (peakL - widest < 1) return null;
  const mlt = Number.isInteger(peakMlt) ? String(peakMlt) : peakMlt.toFixed(1);
  const atDomainEdge = domainMaxL !== null && Number.isFinite(domainMaxL) && peakL >= domainMaxL - L_SHELL_STEP / 4;
  return `The two curves do not agree everywhere. On this frame the steepest-gradient check runs out to L ${peakL.toFixed(2)} `
    + `near ${mlt} MLT, while the 50 cm⁻³ boundary stays inside L ${widest.toFixed(2)}. `
    + (atDomainEdge
      ? `That far out the gradient search has reached the outer edge of the model's own grid (L ${domainMaxL!.toFixed(1)}) `
        + `rather than located a plasmapause, so the wide violet lobe is neither a second boundary nor a plume. It is drawn anyway, `
        + `because where two methods disagree the disagreement is the finding.`
      : `Where they separate that far the check is no longer tracking the same boundary, and the cyan curve is the one this chart calls the plasmapause.`);
}

export const PLASMAPAUSE_LIMITATION =
  "The boundary is the outermost crossing of the 50 cm⁻³ contour in the DGCPM simulation, "
  + "interpolated in log density between shells; the steepest-gradient curve is published beside it "
  + "as an independent check on the same frame. It is simulation output driven by measured Kp, not a "
  + "spacecraft crossing, and no in-situ plasmapause measurement exists in any feed this site reads.";

/**
 * WHICH FRAME THE CURRENT-CONDITIONS CHART DRAWS, AND WHY IT IS NOT "NOW".
 *
 * This chart used to ask the globe for the plasmasphere field at the selected
 * instant and refuse to draw unless a published frame lay within half a cadence
 * (60 minutes) of it. On the Current conditions page the selected instant is
 * NOW — and the newest published frame is never at now. The pipeline anchors
 * frames to a fixed two-hourly UTC grid (`frame_times` floors the build clock
 * to that grid), so the last frame is between 0 and 120 minutes old the moment
 * it is published. A symmetric ±60-minute tolerance therefore threw the series
 * away for at least half of every two-hour cycle.
 *
 * Measured on the live site 2026-08-26, one hour apart, no code changed in
 * between: at 15:55 UTC the newest published frame was 14:00 UTC (115 minutes
 * old) and the page read "Not drawable at this time"; at 16:06 UTC the newest
 * frame was 16:00 UTC and the same page drew the ring. That is the whole of
 * the defect the owner saw as "the diagram isn't loading".
 *
 * A nearest-frame-within-half-a-cadence rule is CORRECT for the globe, where a
 * reader scrubs a 48-hour timeline and "which frame is nearest this instant" is
 * a real question with a wrong answer. It is the wrong question here: this
 * chart is a statement about the published window — where the boundary is, and
 * how far it moved across the frames — not about one instant. So the page draws
 * the NEWEST published frame and prints that frame's own valid time and age
 * beside it, rather than silently claiming it is "now".
 */

/** How old a published frame is, in whole minutes; negative if it leads the clock. */
export function plasmapauseFrameAgeMinutes(frame: PlasmapauseFrame, now: Date): number | null {
  const validAt = Date.parse(frame.validAt);
  if (!Number.isFinite(validAt)) return null;
  return Math.round((now.getTime() - validAt) / 60_000);
}

/**
 * The age past which this chart stops calling the newest published frame
 * current and refuses to draw it.
 *
 * Six hours is three publish cycles. Inside it the boundary is the present one
 * to any reading a person would give the word; past it the artifact has stopped
 * being refreshed, and drawing a six-hour-old boundary under a heading about
 * current conditions would be presenting stale output as the present.
 */
export const PLASMAPAUSE_MAX_FRAME_AGE_MINUTES = 360;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2 h 6 min old", "12 min old", or "the current frame" when it does not trail the clock. */
export function describeFrameAge(ageMinutes: number): string {
  if (ageMinutes <= 0) return "the current frame";
  if (ageMinutes < 60) return `${ageMinutes} min old`;
  const hours = Math.floor(ageMinutes / 60);
  const minutes = ageMinutes % 60;
  return minutes === 0 ? `${hours} h old` : `${hours} h ${minutes} min old`;
}

/**
 * A published frame's own valid time, in words: "26 Aug 16:00 UTC". Exported so
 * the stamp under the picture and the sentence that refuses to draw a stale one
 * name the same instant the same way, rather than one of them printing a raw
 * ISO string at a reader.
 */
export function plasmapauseFrameClock(frame: PlasmapauseFrame): string {
  const at = new Date(Date.parse(frame.validAt));
  if (!Number.isFinite(at.getTime())) return frame.validAt;
  return `${String(at.getUTCDate()).padStart(2, "0")} ${MONTHS[at.getUTCMonth()]} `
    + `${String(at.getUTCHours()).padStart(2, "0")}:${String(at.getUTCMinutes()).padStart(2, "0")} UTC`;
}

/**
 * The stamp printed beside the ring: which published frame this is, how old it
 * is, and the Kp that drove it — the same Kp the chart above this one plots,
 * which is the whole reason the two live on one page.
 */
export function plasmapauseFrameStamp(frame: PlasmapauseFrame, now: Date): string {
  const clock = plasmapauseFrameClock(frame);
  const age = plasmapauseFrameAgeMinutes(frame, now);
  const kp = Number.isFinite(frame.kp) ? ` · Kp ${frame.kp.toFixed(2)}` : "";
  return age === null
    ? `Published frame ${clock}${kp}`
    : `Published frame ${clock} · ${describeFrameAge(age)}${kp}`;
}

