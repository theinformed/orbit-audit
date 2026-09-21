export type GeospaceSliceDisplayMode = "smooth" | "native";

export const GEOSPACE_SLICE_MASK = {
  missing: 1,
  clippedLow: 2,
  clippedHigh: 4,
  interpolated: 8,
} as const;

export const GEOSPACE_SLICE_DISPLAY_MODES = {
  smooth: {
    label: "Smooth",
    description: "Default gap-aware interpolation; source masks remain visible and local source extrema are preserved.",
  },
  native: {
    label: "Native grid",
    description: "Unresampled NOAA adaptive-grid samples.",
  },
} as const satisfies Record<GeospaceSliceDisplayMode, { label: string; description: string }>;

export interface EncodedAdaptivePlaneDefinition {
  count: number;
  coordinatesI16: string;
  boundsRe: [number, number, number, number];
}

export interface EncodedAdaptivePlaneField {
  valuesU16: string;
  masksU8: string;
}

export interface DecodedAdaptivePlaneField {
  mode: "native";
  /** Interleaved model-plane x/cross coordinates in Earth radii. */
  coordinates: Float32Array;
  /** Source-range-normalized values. A missing source value is NaN. */
  values: Float32Array;
  /** Exact source mask bits; see GEOSPACE_SLICE_MASK. */
  masks: Uint8Array;
  boundsRe: [number, number, number, number];
}

export interface SmoothedAdaptivePlaneField {
  mode: "smooth";
  width: number;
  height: number;
  boundsRe: [number, number, number, number];
  /** Row-major normalized values, x varying fastest. Unsupported cells are NaN. */
  values: Float32Array;
  /** Source mask bits ORed across support, plus interpolated or missing. */
  masks: Uint8Array;
}

export type PreparedAdaptivePlaneField = DecodedAdaptivePlaneField | SmoothedAdaptivePlaneField;

export interface SmoothAdaptivePlaneOptions {
  mode?: GeospaceSliceDisplayMode;
  /** Regular display-grid spacing. The NOAA samples remain the scientific source. */
  spacingRe?: number;
  /** Maximum distance to the nearest source sample before a cell remains missing. */
  maximumSupportDistanceRe?: number;
  /** Do not interpolate inside the cropped model's inner boundary. */
  minimumRadiusRe?: number;
  coordinateScaleRe?: number;
}

export interface GeospaceContourSegments {
  level: number;
  /** Consecutive x0, cross0, x1, cross1 model-plane segments. */
  coordinates: Float32Array;
}

function decodeBase64(encoded: string) {
  const binary = globalThis.atob(encoded);
  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) output[index] = binary.charCodeAt(index);
  return output;
}

function decodeLittleEndianInt16(encoded: string) {
  const bytes = decodeBase64(encoded);
  if (bytes.byteLength % 2 !== 0) throw new RangeError("Adaptive-grid coordinate encoding has an odd byte count");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const values = new Int16Array(bytes.byteLength / 2);
  for (let index = 0; index < values.length; index += 1) values[index] = view.getInt16(index * 2, true);
  return values;
}

function decodeLittleEndianUint16(encoded: string) {
  const bytes = decodeBase64(encoded);
  if (bytes.byteLength % 2 !== 0) throw new RangeError("Adaptive-grid field encoding has an odd byte count");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const values = new Uint16Array(bytes.byteLength / 2);
  for (let index = 0; index < values.length; index += 1) values[index] = view.getUint16(index * 2, true);
  return values;
}

export function decodeAdaptivePlaneField(
  definition: EncodedAdaptivePlaneDefinition,
  field: EncodedAdaptivePlaneField,
  coordinateScaleRe = 0.01,
): DecodedAdaptivePlaneField {
  const encodedCoordinates = decodeLittleEndianInt16(definition.coordinatesI16);
  const encodedValues = decodeLittleEndianUint16(field.valuesU16);
  const masks = decodeBase64(field.masksU8);
  if (encodedCoordinates.length !== definition.count * 2) {
    throw new RangeError(`Adaptive-grid coordinates contain ${encodedCoordinates.length / 2} points; expected ${definition.count}`);
  }
  if (encodedValues.length !== definition.count || masks.length !== definition.count) {
    throw new RangeError("Adaptive-grid values and masks must match the declared point count");
  }
  const coordinates = new Float32Array(encodedCoordinates.length);
  const values = new Float32Array(encodedValues.length);
  for (let index = 0; index < definition.count; index += 1) {
    coordinates[index * 2] = (encodedCoordinates[index * 2] ?? 0) * coordinateScaleRe;
    coordinates[index * 2 + 1] = (encodedCoordinates[index * 2 + 1] ?? 0) * coordinateScaleRe;
    values[index] = (masks[index]! & GEOSPACE_SLICE_MASK.missing) !== 0
      ? Number.NaN
      : encodedValues[index]! / 65535;
  }
  return { mode: "native", coordinates, values, masks, boundsRe: definition.boundsRe };
}

function bucketKey(x: number, cross: number, size: number) {
  return `${Math.floor(x / size)},${Math.floor(cross / size)}`;
}

/**
 * Reduces adaptive display samples to a regular contour grid. It refuses to
 * bridge unsupported areas, propagates every contributing saturation flag,
 * and clamps each weighted result to its local contributors. The smoothing is
 * a display operation, not a reconstruction of NOAA's full finite-volume mesh.
 */
export function smoothAdaptivePlaneField(
  source: DecodedAdaptivePlaneField,
  spacingRe = 0.5,
  maximumSupportDistanceRe = 1.2,
  minimumRadiusRe = 0,
): SmoothedAdaptivePlaneField {
  if (!(spacingRe > 0) || !(maximumSupportDistanceRe > 0) || minimumRadiusRe < 0) {
    throw new RangeError("Adaptive-grid smoothing distances must be positive");
  }
  const [minimumX, maximumX, minimumCross, maximumCross] = source.boundsRe;
  const width = Math.floor((maximumX - minimumX) / spacingRe + 0.5) + 1;
  const height = Math.floor((maximumCross - minimumCross) / spacingRe + 0.5) + 1;
  const values = new Float32Array(width * height);
  values.fill(Number.NaN);
  const masks = new Uint8Array(width * height);
  masks.fill(GEOSPACE_SLICE_MASK.missing | GEOSPACE_SLICE_MASK.interpolated);

  const bucketSize = Math.max(maximumSupportDistanceRe, spacingRe);
  const buckets = new Map<string, number[]>();
  for (let index = 0; index < source.values.length; index += 1) {
    const x = source.coordinates[index * 2]!;
    const cross = source.coordinates[index * 2 + 1]!;
    const key = bucketKey(x, cross, bucketSize);
    const bucket = buckets.get(key);
    if (bucket) bucket.push(index);
    else buckets.set(key, [index]);
  }

  const bucketRadius = Math.ceil(maximumSupportDistanceRe / bucketSize);
  for (let row = 0; row < height; row += 1) {
    const cross = Math.min(maximumCross, minimumCross + row * spacingRe);
    for (let column = 0; column < width; column += 1) {
      const x = Math.min(maximumX, minimumX + column * spacingRe);
      if (Math.hypot(x, cross) < minimumRadiusRe) continue;
      const xBucket = Math.floor(x / bucketSize);
      const crossBucket = Math.floor(cross / bucketSize);
      const candidates: Array<{ index: number; distanceSquared: number }> = [];
      for (let yOffset = -bucketRadius; yOffset <= bucketRadius; yOffset += 1) {
        for (let xOffset = -bucketRadius; xOffset <= bucketRadius; xOffset += 1) {
          const bucket = buckets.get(`${xBucket + xOffset},${crossBucket + yOffset}`) ?? [];
          bucket.forEach((index) => {
            const deltaX = source.coordinates[index * 2]! - x;
            const deltaCross = source.coordinates[index * 2 + 1]! - cross;
            const distanceSquared = deltaX * deltaX + deltaCross * deltaCross;
            if (distanceSquared <= maximumSupportDistanceRe * maximumSupportDistanceRe) {
              candidates.push({ index, distanceSquared });
            }
          });
        }
      }
      candidates.sort((a, b) => a.distanceSquared - b.distanceSquared);
      const nearest = candidates[0];
      const destination = row * width + column;
      if (!nearest || (source.masks[nearest.index]! & GEOSPACE_SLICE_MASK.missing) !== 0) continue;
      if (nearest.distanceSquared < 1e-10) {
        values[destination] = source.values[nearest.index]!;
        masks[destination] = source.masks[nearest.index]!;
        continue;
      }

      const support = candidates
        .filter((candidate) => (source.masks[candidate.index]! & GEOSPACE_SLICE_MASK.missing) === 0)
        .slice(0, 6);
      if (support.length < 3) continue;
      let weightSum = 0;
      let weightedValue = 0;
      let sourceMask = 0;
      let localMinimum = Number.POSITIVE_INFINITY;
      let localMaximum = Number.NEGATIVE_INFINITY;
      support.forEach(({ index, distanceSquared }) => {
        const value = source.values[index]!;
        const weight = 1 / Math.max(distanceSquared, 1e-8);
        weightSum += weight;
        weightedValue += value * weight;
        sourceMask |= source.masks[index]!;
        localMinimum = Math.min(localMinimum, value);
        localMaximum = Math.max(localMaximum, value);
      });
      values[destination] = Math.max(localMinimum, Math.min(localMaximum, weightedValue / weightSum));
      masks[destination] = sourceMask | GEOSPACE_SLICE_MASK.interpolated;
    }
  }
  return { mode: "smooth", width, height, boundsRe: source.boundsRe, values, masks };
}

export function prepareAdaptivePlaneField(
  definition: EncodedAdaptivePlaneDefinition,
  field: EncodedAdaptivePlaneField,
  options: SmoothAdaptivePlaneOptions = {},
): PreparedAdaptivePlaneField {
  const native = decodeAdaptivePlaneField(definition, field, options.coordinateScaleRe);
  if ((options.mode ?? "smooth") === "native") return native;
  return smoothAdaptivePlaneField(
    native,
    options.spacingRe ?? 0.5,
    options.maximumSupportDistanceRe ?? 1.2,
    options.minimumRadiusRe ?? 2.55,
  );
}

function edgeIntersection(
  first: readonly [number, number, number],
  second: readonly [number, number, number],
  level: number,
): [number, number] | null {
  const firstBelow = first[2] < level;
  const secondBelow = second[2] < level;
  if (firstBelow === secondBelow || first[2] === second[2]) return null;
  const fraction = (level - first[2]) / (second[2] - first[2]);
  return [
    first[0] + (second[0] - first[0]) * fraction,
    first[1] + (second[1] - first[1]) * fraction,
  ];
}

/** Marching-squares line segments over the gap-aware smooth grid. */
export function contourAdaptivePlaneField(
  grid: SmoothedAdaptivePlaneField,
  levels: readonly number[],
): GeospaceContourSegments[] {
  const [minimumX, maximumX, minimumCross, maximumCross] = grid.boundsRe;
  const xStep = grid.width > 1 ? (maximumX - minimumX) / (grid.width - 1) : 0;
  const crossStep = grid.height > 1 ? (maximumCross - minimumCross) / (grid.height - 1) : 0;
  return levels.map((level) => {
    const coordinates: number[] = [];
    for (let row = 0; row < grid.height - 1; row += 1) {
      for (let column = 0; column < grid.width - 1; column += 1) {
        const indices = [
          row * grid.width + column,
          row * grid.width + column + 1,
          (row + 1) * grid.width + column + 1,
          (row + 1) * grid.width + column,
        ];
        if (indices.some((index) => (grid.masks[index]! & GEOSPACE_SLICE_MASK.missing) !== 0)) continue;
        const x0 = minimumX + column * xStep;
        const x1 = x0 + xStep;
        const cross0 = minimumCross + row * crossStep;
        const cross1 = cross0 + crossStep;
        const corners = [
          [x0, cross0, grid.values[indices[0]!]!],
          [x1, cross0, grid.values[indices[1]!]!],
          [x1, cross1, grid.values[indices[2]!]!],
          [x0, cross1, grid.values[indices[3]!]!],
        ] as const;
        const intersections = [
          edgeIntersection(corners[0], corners[1], level),
          edgeIntersection(corners[1], corners[2], level),
          edgeIntersection(corners[2], corners[3], level),
          edgeIntersection(corners[3], corners[0], level),
        ];
        const present = intersections
          .map((point, edge) => ({ point, edge }))
          .filter((item): item is { point: [number, number]; edge: number } => item.point !== null);
        if (present.length === 2) {
          coordinates.push(...present[0]!.point, ...present[1]!.point);
        } else if (present.length === 4) {
          // Resolve the saddle from the bilinear cell-center value. Both paths
          // remain within the four source values and do not invent an extremum.
          const centerAbove = corners.reduce((sum, corner) => sum + corner[2], 0) / 4 >= level;
          const pairs: Array<readonly [number, number]> = centerAbove
            ? [[0, 1], [2, 3]]
            : [[0, 3], [1, 2]];
          pairs.forEach(([first, second]) => {
            coordinates.push(...present[first]!.point, ...present[second]!.point);
          });
        }
      }
    }
    return { level, coordinates: new Float32Array(coordinates) };
  });
}
