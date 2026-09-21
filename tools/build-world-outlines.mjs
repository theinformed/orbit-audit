#!/usr/bin/env node
/**
 * Builds the vendored world-outline asset used by the 2-D ground-track map.
 *
 * Source: Natural Earth 1:110m (public domain, no attribution required) —
 * the same edition and the same GitHub mirror the release pipeline already
 * uses for the 3-D globe (pipeline/build_release.py LAND_URL).
 *
 *   ne_110m_land                          -> filled land + coastline
 *   ne_110m_admin_0_boundary_lines_land   -> international boundaries
 *   ne_110m_lakes                         -> inland water
 *
 * This runs ONCE, by hand, and writes src/data/world-110m.ts. Nothing is
 * fetched at run time: the map must render with no network at all.
 *
 * Usage:
 *   node tools/build-world-outlines.mjs <directory-with-the-three-geojson-files>
 *
 * The geojson files come from
 * https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/<name>.geojson
 */
import fs from "node:fs";
import path from "node:path";

const SOURCE_DIRECTORY = process.argv[2];
if (!SOURCE_DIRECTORY) {
  console.error("usage: node tools/build-world-outlines.mjs <geojson-directory>");
  process.exit(2);
}
const OUTPUT = path.resolve(process.argv[3] ?? "src/data/world-110m.ts");

/** 1/16 degree grid: 0.0625 deg is about 7 km, roughly 1/6 of a pixel on the map. */
const SCALE = 16;
/** Douglas-Peucker tolerance in degrees, about a quarter of a rendered pixel. */
const TOLERANCE = 0.08;

function readRings(name) {
  const geojson = JSON.parse(fs.readFileSync(path.join(SOURCE_DIRECTORY, `${name}.geojson`), "utf8"));
  const rings = [];
  for (const feature of geojson.features) {
    const { type, coordinates } = feature.geometry;
    if (type === "LineString") rings.push(coordinates);
    else if (type === "MultiLineString" || type === "Polygon") rings.push(...coordinates);
    else if (type === "MultiPolygon") for (const polygon of coordinates) rings.push(...polygon);
  }
  return rings.map((ring) => ring.map(([lon, lat]) => [lon, lat]));
}

/**
 * Natural Earth's Antarctica ring closes by stepping straight from +180 to
 * -180. Drawn as-is on an equirectangular map that is a line across the whole
 * world. Split at the seam and close each half along the nearer pole.
 */
function splitAtAntimeridian(ring, closeToPole) {
  const pieces = [];
  let current = [ring[0]];
  for (let index = 1; index < ring.length; index += 1) {
    const [previousLon, previousLat] = ring[index - 1];
    const [lon, lat] = ring[index];
    if (Math.abs(lon - previousLon) <= 180) {
      current.push([lon, lat]);
      continue;
    }
    const eastward = lon - previousLon < -180;
    const unwrapped = lon + (eastward ? 360 : -360);
    const boundary = eastward ? 180 : -180;
    // Natural Earth's Antarctica ring steps from exactly +180 to exactly -180,
    // which makes this denominator zero. Without the guard the seam latitude is
    // NaN, the pole test then reads NaN < 0 as false, and the polygon closes
    // over the north pole instead of the south.
    const denominator = unwrapped - previousLon;
    const fraction = denominator === 0 ? 0 : (boundary - previousLon) / denominator;
    const seamLat = previousLat + (lat - previousLat) * fraction;
    current.push([boundary, seamLat]);
    pieces.push(current);
    current = [[-boundary, seamLat], [lon, lat]];
  }
  pieces.push(current);
  // Only a ring that actually crossed the seam was cut open and needs closing.
  // Closing an untouched ring would drag two of its vertices to the pole and
  // draw a spike the full height of the map.
  if (!closeToPole || pieces.length < 2) return pieces;

  const closedRing = ring.length > 2
    && ring[0][0] === ring.at(-1)[0]
    && ring[0][1] === ring.at(-1)[1];
  // A closed ring cut once at the seam is really one strip running from one map
  // edge to the other. Rejoining the two halves in the other order puts both
  // open ends on the map edge, so the closing edge to the pole is hidden at the
  // edge rather than cutting a notch through the middle of the continent.
  const strips = closedRing && pieces.length === 2
    ? [[...pieces[1].slice(0, -1), ...pieces[0]]]
    : pieces;

  const latitudeSum = strips.flat().reduce((sum, [, lat]) => sum + lat, 0);
  if (!Number.isFinite(latitudeSum)) throw new Error("seam split produced a non-finite latitude");
  const pole = latitudeSum < 0 ? -90 : 90;
  return strips.map((piece) => {
    if (piece.length < 2) return piece;
    const first = piece[0];
    const last = piece.at(-1);
    if (Math.abs(first[1] - pole) < 1e-6 && Math.abs(last[1] - pole) < 1e-6) return piece;
    return [[first[0], pole], ...piece, [last[0], pole]];
  });
}

function perpendicularDistance([x, y], [x1, y1], [x2, y2]) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return Math.hypot(x - x1, y - y1);
  const t = Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / lengthSquared));
  return Math.hypot(x - (x1 + t * dx), y - (y1 + t * dy));
}

function simplify(points, tolerance) {
  if (points.length < 3) return points;
  let worst = 0;
  let index = 0;
  for (let i = 1; i < points.length - 1; i += 1) {
    const distance = perpendicularDistance(points[i], points[0], points.at(-1));
    if (distance > worst) {
      worst = distance;
      index = i;
    }
  }
  if (worst <= tolerance) return [points[0], points.at(-1)];
  return [
    ...simplify(points.slice(0, index + 1), tolerance).slice(0, -1),
    ...simplify(points.slice(index), tolerance),
  ];
}

function quantize(ring) {
  const out = [];
  for (const [lon, lat] of ring) {
    const x = Math.round(Math.max(-180, Math.min(180, lon)) * SCALE);
    const y = Math.round(Math.max(-90, Math.min(90, lat)) * SCALE);
    if (out.length === 0 || out.at(-1)[0] !== x || out.at(-1)[1] !== y) out.push([x, y]);
  }
  return out;
}

// --- byte stream: unsigned LEB128 varints, coordinates zigzag-encoded ---
function pushVarint(bytes, value) {
  let remaining = value;
  while (remaining >= 0x80) {
    bytes.push((remaining & 0x7f) | 0x80);
    remaining = Math.floor(remaining / 128);
  }
  bytes.push(remaining);
}
const zigzag = (value) => (value < 0 ? -2 * value - 1 : 2 * value);

function encodeLayer(rings) {
  const bytes = [];
  pushVarint(bytes, rings.length);
  for (const ring of rings) {
    pushVarint(bytes, ring.length);
    pushVarint(bytes, zigzag(ring[0][0]));
    pushVarint(bytes, zigzag(ring[0][1]));
    for (let index = 1; index < ring.length; index += 1) {
      pushVarint(bytes, zigzag(ring[index][0] - ring[index - 1][0]));
      pushVarint(bytes, zigzag(ring[index][1] - ring[index - 1][1]));
    }
  }
  return Buffer.from(bytes).toString("base64");
}

function buildLayer(name, { closeToPole = false, minimumPoints = 2 } = {}) {
  const rings = readRings(name);
  const prepared = [];
  let sourcePoints = 0;
  for (const ring of rings) {
    sourcePoints += ring.length;
    for (const piece of splitAtAntimeridian(ring, closeToPole)) {
      const reduced = quantize(simplify(piece, TOLERANCE));
      if (reduced.length >= minimumPoints) prepared.push(reduced);
    }
  }
  const keptPoints = prepared.reduce((sum, ring) => sum + ring.length, 0);
  const encoded = encodeLayer(prepared);
  console.error(
    `${name.padEnd(38)} ${String(rings.length).padStart(4)} rings -> ${String(prepared.length).padStart(4)}   `
    + `${String(sourcePoints).padStart(5)} pts -> ${String(keptPoints).padStart(5)}   ${(encoded.length / 1024).toFixed(1)} KiB base64`,
  );
  return encoded;
}

const land = buildLayer("ne_110m_land", { closeToPole: true, minimumPoints: 3 });
const borders = buildLayer("ne_110m_admin_0_boundary_lines_land");
const lakes = buildLayer("ne_110m_lakes", { minimumPoints: 3 });

const module = `// GENERATED FILE - do not edit by hand.
// Rebuild with: node tools/build-world-outlines.mjs <geojson-directory>
//
// Natural Earth 1:110m, public domain (no attribution required), the same
// edition the release pipeline already uses for the 3-D globe. Bundled into
// the JavaScript so the ground-track map renders with no network request.
//
// Encoding: base64 of a byte stream. Per layer: ring count, then for each
// ring a point count, an absolute first coordinate, and deltas thereafter.
// Every coordinate is an unsigned LEB128 varint of a zigzagged integer in
// units of 1/${SCALE} degree. Simplified with Douglas-Peucker at ${TOLERANCE} degrees.

export const WORLD_OUTLINE_SCALE = ${SCALE};
export const WORLD_OUTLINE_SOURCE = "Natural Earth 1:110m (public domain)";

export const WORLD_LAND_110M = ${JSON.stringify(land)};
export const WORLD_BOUNDARIES_110M = ${JSON.stringify(borders)};
export const WORLD_LAKES_110M = ${JSON.stringify(lakes)};
`;
fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
fs.writeFileSync(OUTPUT, module);
console.error(`\nwrote ${OUTPUT} (${(fs.statSync(OUTPUT).size / 1024).toFixed(1)} KiB)`);
