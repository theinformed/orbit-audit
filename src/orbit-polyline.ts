/**
 * Where to put the vertices of a drawn orbit line.
 *
 * ## What was wrong
 *
 * The selected spacecraft's orbit used to be 180 samples spaced evenly in
 * TIME. That is the right rule for a near-circular orbit and the wrong rule
 * for every other one, because a satellite does not cover ground evenly. On
 * MERIDIAN 9 (Molniya, e = 0.684) 180 even samples left 38.7 scene units
 * between two vertices near perigee — where the spacecraft is fastest — and
 * 2.19 near apogee, an 18x spread, and the drawn line turned up to 10.9
 * degrees at a single vertex at 2,436 km altitude. On THEMIS D the same rule
 * turned 23.7 degrees at one vertex. That is what a reader sees as "weird
 * kinks": a smooth curve rendered as a polygon on the side of the orbit
 * nearest the Earth. Refining to 11,520 even samples drove that same turn to
 * 0.17 degrees, which is the measurement that proves the corner belonged to
 * the sampler and not to the orbit.
 *
 * Sampling evenly in mean or eccentric anomaly would fix most of it for a
 * Keplerian ellipse, but the scene does not draw a Keplerian ellipse: it draws
 * an SGP4 path through a steeply NON-LINEAR radial ruler
 * (`src/radial-ruler.ts`), and either of those can concentrate drawn curvature
 * somewhere an anomaly does not know about. So this refines against what is
 * actually drawn.
 *
 * ## The rule
 *
 * Seed a coarse even-in-time polyline, then repeatedly split whichever segment
 * departs furthest from the true path, until no segment's midpoint sits more
 * than `toleranceSceneUnits` off its own chord. That is a bound on the drawn
 * error itself, so it holds for any propagator, any eccentricity and either
 * distance scale, and it spends vertices only where the picture needs them.
 *
 * ## Choosing the tolerance
 *
 * The camera frames a drawn reach R from about 1.06 * R / tan(21 degrees) =
 * 2.76 * R away, which makes the visible frame roughly 2.1 * R tall; on a
 * 900-pixel-tall view one pixel is therefore near R / 420.
 * `orbitPathTolerance` asks for R / 1200, about a third of a pixel at that
 * framing, so the line still reads as smooth after roughly three stops of zoom
 * past it. Measured at that tolerance: 129 vertices for the ISS, 117 for
 * MERIDIAN 9, 107 for CLUSTER II-FM7, and 2 to 8 ms to build the whole path —
 * against a 2-second floor on how often a moving selection is rebuilt.
 *
 * ## Why a chord bound is not enough on its own
 *
 * A chord bound says how far the drawn line strays from the drawn path. It
 * does not say how the line LOOKS, and those come apart wherever the drawn
 * curvature is concentrated: two segments can meet at 14 degrees with every
 * point of both inside a third of a pixel of the truth. That is exactly what
 * happens where the shared ruler's geostationary joint ramps its slope from
 * 0.1422 to 1 between 6.617 and 7.35 Re (`src/radial-ruler.ts`). The drawn
 * curve there is smooth but tight — measured radius of curvature 13.8 scene
 * units on THEMIS A against 72.5 for the tightest bend anywhere else on that
 * same line — and a tolerance scaled to the orbit's whole reach steps straight
 * over it. Measured with the chord bound alone: 14.2 degrees at one vertex on
 * THEMIS A and 26.7 on CLUSTER II-FM7, against 4.5 and 4.8 for their own
 * medians.
 *
 * So there is a second bound, `maxVertexTurnDeg`, applied after the chord
 * bound is satisfied: no vertex may turn more than 6 degrees. It costs almost
 * nothing, because a closed loop of N vertices already averages 360/N degrees
 * per vertex — 2.8 at the ISS's 129 — so the cap only ever bites where
 * curvature concentrates. Measured cost at 6 degrees, with the C1 ruler: the
 * ISS and a geostationary circle are untouched at 129 vertices, MERIDIAN 9 is
 * untouched at 115, THEMIS A goes 112 to 129 and CLUSTER II-FM7 107 to 142,
 * and the worst vertex turn on any of them falls to 5.9 degrees.
 *
 * ## The floor under the turn cap, which is not an optimisation
 *
 * A turn cap must never be allowed to refine INTO a tangent discontinuity, and
 * this was measured rather than assumed. Run against the ruler as it was
 * before 2026-08-19 — slope STEPPING 7.03x at geostationary radius, so a
 * crossing orbit had a true corner of about 21.7 degrees — an unfloored
 * 6-degree cap "converged" on MERIDIAN 9 at 187 vertices with a worst turn of
 * 5.0. It had not smoothed anything: it had packed 70 vertices into a
 * 0.03-scene-unit neighbourhood of the corner, where consecutive segments are
 * 0.001 to 0.026 units long and the angle between two sub-pixel chords means
 * nothing. The corner was still on screen and the metric no longer saw it.
 *
 * So a segment is never split below `toleranceSceneUnits` in drawn length: at
 * that size the chord bound is already satisfied by an order of magnitude and
 * no further vertex can change a pixel. With that floor the cap reports
 * honestly on a discontinuous map — it stops, and the corner still measures
 * what it is — and does real work on a C1 one, which is the only kind this
 * scene now has.
 */

/** A drawn scene position. Deliberately not a THREE.Vector3: this module is pure. */
export interface DrawnPosition {
  x: number;
  y: number;
  z: number;
}

export interface AdaptiveOrbitPathOptions<Sample> {
  /** The instant the drawn span is centred on. */
  centre: Date;
  /** How much of the orbit to draw. One full period draws a closed orbit. */
  spanMinutes: number;
  /** The propagator. Returning null drops that instant rather than the line. */
  sampleAt: (at: Date) => Sample | null;
  /** Where the scene would draw that sample, on whichever ruler is live. */
  drawnPosition: (sample: Sample) => DrawnPosition;
  /** The largest drawn departure from the true path any segment may have. */
  toleranceSceneUnits: number;
  /**
   * The largest direction change allowed at any vertex, degrees. Refined after
   * the chord bound is met, and never by splitting a segment already shorter
   * than the tolerance — see the header on why that floor is load-bearing.
   */
  maxVertexTurnDeg?: number;
  /** The even-in-time starting polyline. Must be fine enough to find the shape. */
  seedVertices?: number;
  /** The ceiling on refinement, so a pathological orbit cannot stall a frame. */
  maxVertices?: number;
}

interface Vertex<Sample> {
  timeMs: number;
  sample: Sample;
  drawn: DrawnPosition;
}

interface Segment<Sample> {
  /** The candidate vertex: the true path at the segment's midpoint in time. */
  midpoint: Vertex<Sample> | null;
  /** How far that midpoint sits off the chord, in scene units. */
  error: number;
}

/**
 * The drawn tolerance for an orbit whose outermost drawn radius is `reach`.
 * A ratio rather than a constant, so a 400 km LEO and a 172,000 km apogee are
 * held to the same fraction of a frame instead of the same absolute distance.
 */
export function orbitPathTolerance(drawnReachSceneUnits: number): number {
  return Math.max(0.02, drawnReachSceneUnits / 1200);
}

/**
 * The default vertex-turn cap, degrees. Six is below the angle at which a
 * polyline reads as faceted and above the 2.8 degrees a 129-vertex closed loop
 * already turns per vertex, so it costs nothing on an ordinary orbit and only
 * spends vertices where the drawn curvature is concentrated.
 */
export const ORBIT_PATH_MAX_VERTEX_TURN_DEG = 6;

/** Direction change at B, degrees, for the drawn polyline A-B-C. */
function vertexTurnDegrees(a: DrawnPosition, b: DrawnPosition, c: DrawnPosition): number {
  const backX = b.x - a.x;
  const backY = b.y - a.y;
  const backZ = b.z - a.z;
  const forwardX = c.x - b.x;
  const forwardY = c.y - b.y;
  const forwardZ = c.z - b.z;
  const backLength = Math.hypot(backX, backY, backZ);
  const forwardLength = Math.hypot(forwardX, forwardY, forwardZ);
  if (backLength < 1e-9 || forwardLength < 1e-9) return 0;
  const cosine = (backX * forwardX + backY * forwardY + backZ * forwardZ) / (backLength * forwardLength);
  return (Math.acos(Math.max(-1, Math.min(1, cosine))) * 180) / Math.PI;
}

/** Drawn length of the segment AB. */
function segmentLength(a: DrawnPosition, b: DrawnPosition): number {
  return Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
}

/** Distance from a point to the segment AB, both in drawn scene units. */
function distanceToChord(point: DrawnPosition, a: DrawnPosition, b: DrawnPosition): number {
  const abx = b.x - a.x;
  const aby = b.y - a.y;
  const abz = b.z - a.z;
  const lengthSquared = abx * abx + aby * aby + abz * abz;
  const apx = point.x - a.x;
  const apy = point.y - a.y;
  const apz = point.z - a.z;
  if (lengthSquared <= 0) return Math.hypot(apx, apy, apz);
  const t = Math.max(0, Math.min(1, (apx * abx + apy * aby + apz * abz) / lengthSquared));
  return Math.hypot(apx - t * abx, apy - t * aby, apz - t * abz);
}

export function adaptiveOrbitPath<Sample>(options: AdaptiveOrbitPathOptions<Sample>): Sample[] {
  const {
    centre,
    spanMinutes,
    sampleAt,
    drawnPosition,
    toleranceSceneUnits,
    maxVertexTurnDeg = ORBIT_PATH_MAX_VERTEX_TURN_DEG,
    seedVertices = 64,
    maxVertices = 900,
  } = options;
  if (!(spanMinutes > 0) || !Number.isFinite(centre.getTime())) return [];
  const seed = Math.max(8, Math.floor(seedVertices));
  const budget = Math.max(seed + 1, Math.floor(maxVertices));
  const spanMs = spanMinutes * 60000;
  const startMs = centre.getTime() - spanMs / 2;

  const evaluate = (timeMs: number): Vertex<Sample> | null => {
    const sample = sampleAt(new Date(timeMs));
    if (!sample) return null;
    return { timeMs, sample, drawn: drawnPosition(sample) };
  };

  const vertices: Array<Vertex<Sample>> = [];
  for (let index = 0; index <= seed; index += 1) {
    const vertex = evaluate(startMs + (index / seed) * spanMs);
    if (vertex) vertices.push(vertex);
  }
  if (vertices.length < 3) return vertices.map((vertex) => vertex.sample);

  const measure = (index: number): Segment<Sample> => {
    const a = vertices[index];
    const b = vertices[index + 1];
    if (!a || !b) return { midpoint: null, error: 0 };
    const midpoint = evaluate((a.timeMs + b.timeMs) / 2);
    // A propagator that will not answer for an instant is a gap in knowledge,
    // not a shape: leave the chord alone rather than inventing a vertex.
    if (!midpoint) return { midpoint: null, error: 0 };
    return { midpoint, error: distanceToChord(midpoint.drawn, a.drawn, b.drawn) };
  };

  const segments: Array<Segment<Sample>> = [];
  for (let index = 0; index + 1 < vertices.length; index += 1) segments.push(measure(index));

  while (vertices.length < budget) {
    let worst = -1;
    let worstError = toleranceSceneUnits;
    for (let index = 0; index < segments.length; index += 1) {
      const segment = segments[index];
      if (segment && segment.error > worstError) {
        worstError = segment.error;
        worst = index;
      }
    }
    if (worst < 0) break;
    const midpoint = segments[worst]?.midpoint;
    if (!midpoint) break;
    vertices.splice(worst + 1, 0, midpoint);
    segments.splice(worst, 1, measure(worst), measure(worst + 1));
  }

  // Second bound: no vertex may turn like a facet. Split the LONGER of the two
  // segments meeting at the worst offending vertex, and never one already
  // shorter than the tolerance — a shorter one cannot move a pixel, and
  // chasing a tangent discontinuity below that size hides it instead of
  // smoothing it (see the header).
  if (maxVertexTurnDeg > 0) {
    while (vertices.length < budget) {
      let worst = -1;
      let worstTurn = maxVertexTurnDeg;
      for (let index = 1; index + 1 < vertices.length; index += 1) {
        const before = vertices[index - 1]!;
        const here = vertices[index]!;
        const after = vertices[index + 1]!;
        if (Math.max(segmentLength(before.drawn, here.drawn), segmentLength(here.drawn, after.drawn))
          <= toleranceSceneUnits) continue;
        const turn = vertexTurnDegrees(before.drawn, here.drawn, after.drawn);
        if (turn > worstTurn) {
          worstTurn = turn;
          worst = index;
        }
      }
      if (worst < 0) break;
      const before = vertices[worst - 1]!;
      const here = vertices[worst]!;
      const after = vertices[worst + 1]!;
      const splitLeft = segmentLength(before.drawn, here.drawn) >= segmentLength(here.drawn, after.drawn);
      const midpoint = splitLeft
        ? evaluate((before.timeMs + here.timeMs) / 2)
        : evaluate((here.timeMs + after.timeMs) / 2);
      // A propagator that will not answer is a gap in knowledge here too.
      if (!midpoint) break;
      vertices.splice(splitLeft ? worst : worst + 1, 0, midpoint);
    }
  }

  return vertices.map((vertex) => vertex.sample);
}
