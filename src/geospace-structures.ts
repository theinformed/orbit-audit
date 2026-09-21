import * as THREE from "three";

export type GeospaceStructurePlane = "equatorial" | "meridional";
export type GeospaceBoundaryKind = "bowShock" | "magnetopauseProxy";

export interface GeospaceStructuresDefinition {
  status: "model-derived-proxies";
  coordinateSystem: "GSM";
  anglesDegrees: number[];
  radiusEncoding: {
    storage: string;
    scaleRe: number;
    missingValue: number;
  };
  streamlineEncoding: {
    storage: string;
    scaleRe: number;
    flowSpeedScaleKps?: number;
  };
}

export interface EncodedProjectedStreamlines {
  lineCount: number;
  pointCount: number;
  coordinatesI16: string;
  offsetsU16: string;
  /** Present for BATS-R-US bulk-flow lines and aligned with every point. */
  speedU16?: string;
}

export interface ProjectedAdvectionPath {
  points: Array<[number, number]>;
  speedKps: Float32Array;
  /** Frozen-frame travel time using local BATS-R-US speed magnitude. */
  elapsedModelSeconds: Float32Array;
  durationModelSeconds: number;
}

export interface ProjectedAdvectionSample {
  xRe: number;
  crossRe: number;
  speedKps: number;
}

export interface EncodedPlaneStructures {
  bowShockRadiusU16: string;
  magnetopauseProxyRadiusU16: string;
  projectedMagneticStreamlines: EncodedProjectedStreamlines;
  projectedFlowStreamlines: EncodedProjectedStreamlines;
}

export type EncodedFrameStructures = Record<GeospaceStructurePlane, EncodedPlaneStructures>;
export type GsmPositionMapper = (xRe: number, yRe: number, zRe: number) => THREE.Vector3;
export type PlanePositionMapper = (
  xRe: number,
  crossRe: number,
  plane: GeospaceStructurePlane,
) => THREE.Vector3;

function decodeLittleEndianUint16(encoded: string) {
  const binary = globalThis.atob(encoded);
  const values = new Uint16Array(binary.length / 2);
  for (let index = 0; index < values.length; index += 1) {
    values[index] = binary.charCodeAt(index * 2) | (binary.charCodeAt(index * 2 + 1) << 8);
  }
  return values;
}

function decodeLittleEndianInt16(encoded: string) {
  const unsigned = decodeLittleEndianUint16(encoded);
  const values = new Int16Array(unsigned.length);
  unsigned.forEach((value, index) => {
    values[index] = value > 32767 ? value - 65536 : value;
  });
  return values;
}

export function decodeBoundaryProfile(
  definition: GeospaceStructuresDefinition,
  encoded: string,
): Array<number | null> {
  return Array.from(decodeLittleEndianUint16(encoded), (value) =>
    value === definition.radiusEncoding.missingValue
      ? null
      : value * definition.radiusEncoding.scaleRe,
  );
}

export function decodeProjectedStreamlines(
  definition: GeospaceStructuresDefinition,
  encoded: EncodedProjectedStreamlines,
): Array<Array<[number, number]>> {
  const coordinates = decodeLittleEndianInt16(encoded.coordinatesI16);
  const offsets = decodeLittleEndianUint16(encoded.offsetsU16);
  if (
    coordinates.length !== encoded.pointCount * 2
    || offsets.length !== encoded.lineCount + 1
    || offsets[0] !== 0
    || offsets[offsets.length - 1] !== encoded.pointCount
  ) return [];
  const lines: Array<Array<[number, number]>> = [];
  for (let lineIndex = 0; lineIndex < encoded.lineCount; lineIndex += 1) {
    const start = offsets[lineIndex] ?? 0;
    const end = offsets[lineIndex + 1] ?? start;
    const line: Array<[number, number]> = [];
    for (let pointIndex = start; pointIndex < end; pointIndex += 1) {
      line.push([
        (coordinates[pointIndex * 2] ?? 0) * definition.streamlineEncoding.scaleRe,
        (coordinates[pointIndex * 2 + 1] ?? 0) * definition.streamlineEncoding.scaleRe,
      ]);
    }
    if (line.length >= 2) lines.push(line);
  }
  return lines;
}

function segmentMinimumRadius(first: [number, number], second: [number, number]) {
  const deltaX = second[0] - first[0];
  const deltaCross = second[1] - first[1];
  const lengthSquared = deltaX * deltaX + deltaCross * deltaCross;
  if (lengthSquared <= 0) return Math.hypot(...first);
  const fraction = THREE.MathUtils.clamp(
    -(first[0] * deltaX + first[1] * deltaCross) / lengthSquared,
    0,
    1,
  );
  return Math.hypot(first[0] + fraction * deltaX, first[1] + fraction * deltaCross);
}

/**
 * Prepares frozen-frame particle paths from BATS-R-US Ux/Uy/Uz projections.
 * Direction comes from the traced velocity vector and travel time from the
 * source speed magnitude. No line is accepted if a segment bridges the model's
 * inner boundary or makes an implausibly large encoded jump.
 */
export function buildProjectedFlowAdvectionPaths(
  definition: GeospaceStructuresDefinition,
  encoded: EncodedProjectedStreamlines,
  options: { minimumRadiusRe?: number; maximumSegmentRe?: number } = {},
): ProjectedAdvectionPath[] {
  if (!encoded.speedU16 || !definition.streamlineEncoding.flowSpeedScaleKps) return [];
  const lines = decodeProjectedStreamlines(definition, encoded);
  const offsets = decodeLittleEndianUint16(encoded.offsetsU16);
  const speedCodes = decodeLittleEndianUint16(encoded.speedU16);
  if (lines.length !== encoded.lineCount || speedCodes.length !== encoded.pointCount) return [];
  const minimumRadiusRe = options.minimumRadiusRe ?? 2.55;
  const maximumSegmentRe = options.maximumSegmentRe ?? 0.75;
  const earthRadiusKm = 6371;
  const paths: ProjectedAdvectionPath[] = [];
  lines.forEach((points, lineIndex) => {
    const start = offsets[lineIndex] ?? 0;
    const end = offsets[lineIndex + 1] ?? start;
    const speeds = Float32Array.from(
      speedCodes.slice(start, end),
      (value) => value * definition.streamlineEncoding.flowSpeedScaleKps!,
    );
    if (speeds.length !== points.length || points.some((point) => Math.hypot(...point) < minimumRadiusRe)) return;
    const elapsed = new Float32Array(points.length);
    for (let index = 1; index < points.length; index += 1) {
      const first = points[index - 1]!;
      const second = points[index]!;
      const distanceRe = Math.hypot(second[0] - first[0], second[1] - first[1]);
      const averageSpeed = (speeds[index - 1]! + speeds[index]!) / 2;
      if (
        distanceRe <= 0
        || distanceRe > maximumSegmentRe
        || averageSpeed <= 0
        || segmentMinimumRadius(first, second) < minimumRadiusRe
      ) return;
      elapsed[index] = elapsed[index - 1]! + distanceRe * earthRadiusKm / averageSpeed;
    }
    const durationModelSeconds = elapsed.at(-1) ?? 0;
    if (durationModelSeconds > 0) {
      paths.push({ points, speedKps: speeds, elapsedModelSeconds: elapsed, durationModelSeconds });
    }
  });
  return paths;
}

export function sampleProjectedFlowAdvectionPath(
  path: ProjectedAdvectionPath,
  elapsedModelSeconds: number,
  loop = true,
): ProjectedAdvectionSample | null {
  if (path.points.length < 2 || !(path.durationModelSeconds > 0) || !Number.isFinite(elapsedModelSeconds)) return null;
  const time = loop
    ? ((elapsedModelSeconds % path.durationModelSeconds) + path.durationModelSeconds) % path.durationModelSeconds
    : THREE.MathUtils.clamp(elapsedModelSeconds, 0, path.durationModelSeconds);
  let endIndex = 1;
  while (endIndex < path.elapsedModelSeconds.length - 1 && path.elapsedModelSeconds[endIndex]! < time) {
    endIndex += 1;
  }
  const startIndex = endIndex - 1;
  const startTime = path.elapsedModelSeconds[startIndex]!;
  const endTime = path.elapsedModelSeconds[endIndex]!;
  const fraction = endTime === startTime ? 0 : (time - startTime) / (endTime - startTime);
  const start = path.points[startIndex]!;
  const end = path.points[endIndex]!;
  return {
    xRe: THREE.MathUtils.lerp(start[0], end[0], fraction),
    crossRe: THREE.MathUtils.lerp(start[1], end[1], fraction),
    speedKps: THREE.MathUtils.lerp(path.speedKps[startIndex]!, path.speedKps[endIndex]!, fraction),
  };
}

function encodedBoundaryKey(kind: GeospaceBoundaryKind) {
  return kind === "bowShock" ? "bowShockRadiusU16" : "magnetopauseProxyRadiusU16";
}

function sampleProfile(
  angles: number[],
  values: Array<number | null>,
  targetAngle: number,
): number | null {
  if (angles.length !== values.length || angles.length === 0) return null;
  if (targetAngle <= (angles[0] ?? 0)) return values[0] ?? null;
  const lastIndex = angles.length - 1;
  if (targetAngle >= (angles[lastIndex] ?? 0)) return values[lastIndex] ?? null;
  for (let index = 0; index < lastIndex; index += 1) {
    const startAngle = angles[index] ?? 0;
    const endAngle = angles[index + 1] ?? startAngle;
    if (targetAngle < startAngle || targetAngle > endAngle) continue;
    const startValue = values[index];
    const endValue = values[index + 1];
    if (startValue === null || startValue === undefined || endValue === null || endValue === undefined) {
      return null;
    }
    const fraction = endAngle === startAngle ? 0 : (targetAngle - startAngle) / (endAngle - startAngle);
    return startValue + (endValue - startValue) * fraction;
  }
  return null;
}

function decodedProfiles(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  kind: GeospaceBoundaryKind,
) {
  const key = encodedBoundaryKey(kind);
  return {
    equatorial: decodeBoundaryProfile(definition, frame.equatorial[key]),
    meridional: decodeBoundaryProfile(definition, frame.meridional[key]),
  };
}

function loftRadius(
  definition: GeospaceStructuresDefinition,
  profiles: ReturnType<typeof decodedProfiles>,
  thetaDegrees: number,
  azimuth: number,
) {
  if (thetaDegrees === 0) {
    const equatorial = sampleProfile(definition.anglesDegrees, profiles.equatorial, 0);
    const meridional = sampleProfile(definition.anglesDegrees, profiles.meridional, 0);
    return equatorial === null || meridional === null ? null : (equatorial + meridional) / 2;
  }
  const cosine = Math.cos(azimuth);
  const sine = Math.sin(azimuth);
  const equatorialWeight = Math.abs(cosine);
  const meridionalWeight = Math.abs(sine);
  const equatorialAngle = cosine >= 0 ? thetaDegrees : -thetaDegrees;
  const meridionalAngle = sine >= 0 ? thetaDegrees : -thetaDegrees;
  const equatorial = equatorialWeight < 1e-6
    ? 0
    : sampleProfile(definition.anglesDegrees, profiles.equatorial, equatorialAngle);
  const meridional = meridionalWeight < 1e-6
    ? 0
    : sampleProfile(definition.anglesDegrees, profiles.meridional, meridionalAngle);
  if (equatorial === null || meridional === null) return null;
  return (
    equatorialWeight * equatorial
    + meridionalWeight * meridional
  ) / (equatorialWeight + meridionalWeight);
}

function boundaryRings(definition: GeospaceStructuresDefinition) {
  return [...new Set(definition.anglesDegrees.map(Math.abs))].sort((a, b) => a - b);
}

export function createLoftedBoundaryGeometry(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  kind: GeospaceBoundaryKind,
  positionForGsm: GsmPositionMapper = (x, y, z) => new THREE.Vector3(x, y, z),
  azimuthSegments = 32,
) {
  const profiles = decodedProfiles(definition, frame, kind);
  const rings = boundaryRings(definition);
  const positions = new Float32Array(rings.length * azimuthSegments * 3);
  const valid = new Uint8Array(rings.length * azimuthSegments);
  rings.forEach((thetaDegrees, ringIndex) => {
    const theta = THREE.MathUtils.degToRad(thetaDegrees);
    for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
      const azimuth = (azimuthIndex / azimuthSegments) * Math.PI * 2;
      const radius = loftRadius(definition, profiles, thetaDegrees, azimuth);
      const vertexIndex = ringIndex * azimuthSegments + azimuthIndex;
      if (radius === null || !Number.isFinite(radius)) continue;
      const crossRadius = radius * Math.sin(theta);
      positionForGsm(
        radius * Math.cos(theta),
        crossRadius * Math.cos(azimuth),
        crossRadius * Math.sin(azimuth),
      ).toArray(positions, vertexIndex * 3);
      valid[vertexIndex] = 1;
    }
  });

  const indices: number[] = [];
  for (let ringIndex = 0; ringIndex < rings.length - 1; ringIndex += 1) {
    for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
      const nextAzimuth = (azimuthIndex + 1) % azimuthSegments;
      const a = ringIndex * azimuthSegments + azimuthIndex;
      const b = ringIndex * azimuthSegments + nextAzimuth;
      const c = (ringIndex + 1) * azimuthSegments + nextAzimuth;
      const d = (ringIndex + 1) * azimuthSegments + azimuthIndex;
      if (valid[a] && valid[b] && valid[c]) indices.push(a, b, c);
      if (valid[a] && valid[c] && valid[d]) indices.push(a, c, d);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

export function createMagnetosheathGeometry(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  positionForGsm: GsmPositionMapper = (x, y, z) => new THREE.Vector3(x, y, z),
  azimuthSegments = 32,
) {
  const outerProfiles = decodedProfiles(definition, frame, "bowShock");
  const innerProfiles = decodedProfiles(definition, frame, "magnetopauseProxy");
  const rings = boundaryRings(definition);
  const surfaceVertexCount = rings.length * azimuthSegments;
  const positions = new Float32Array(surfaceVertexCount * 2 * 3);
  const valid = new Uint8Array(surfaceVertexCount);
  const writeSurface = (
    profiles: ReturnType<typeof decodedProfiles>,
    surfaceOffset: number,
  ) => {
    rings.forEach((thetaDegrees, ringIndex) => {
      const theta = THREE.MathUtils.degToRad(thetaDegrees);
      for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
        const azimuth = (azimuthIndex / azimuthSegments) * Math.PI * 2;
        const radius = loftRadius(definition, profiles, thetaDegrees, azimuth);
        const localIndex = ringIndex * azimuthSegments + azimuthIndex;
        if (radius === null || !Number.isFinite(radius)) continue;
        const crossRadius = radius * Math.sin(theta);
        positionForGsm(
          radius * Math.cos(theta),
          crossRadius * Math.cos(azimuth),
          crossRadius * Math.sin(azimuth),
        ).toArray(positions, (surfaceOffset + localIndex) * 3);
        valid[localIndex] = (valid[localIndex] ?? 0) + 1;
      }
    });
  };
  writeSurface(outerProfiles, 0);
  writeSurface(innerProfiles, surfaceVertexCount);

  const indices: number[] = [];
  for (let ringIndex = 0; ringIndex < rings.length - 1; ringIndex += 1) {
    for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
      const nextAzimuth = (azimuthIndex + 1) % azimuthSegments;
      const a = ringIndex * azimuthSegments + azimuthIndex;
      const b = ringIndex * azimuthSegments + nextAzimuth;
      const c = (ringIndex + 1) * azimuthSegments + nextAzimuth;
      const d = (ringIndex + 1) * azimuthSegments + azimuthIndex;
      if (valid[a] === 2 && valid[b] === 2 && valid[c] === 2) {
        indices.push(a, b, c, a + surfaceVertexCount, c + surfaceVertexCount, b + surfaceVertexCount);
      }
      if (valid[a] === 2 && valid[c] === 2 && valid[d] === 2) {
        indices.push(a, c, d, a + surfaceVertexCount, d + surfaceVertexCount, c + surfaceVertexCount);
      }
    }
  }
  // Close only the angular edge where both independently supported profiles
  // exist. Missing current-layer sectors remain holes rather than symmetry fill.
  const lastRing = rings.length - 1;
  for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
    const nextAzimuth = (azimuthIndex + 1) % azimuthSegments;
    const a = lastRing * azimuthSegments + azimuthIndex;
    const b = lastRing * azimuthSegments + nextAzimuth;
    if (valid[a] !== 2 || valid[b] !== 2) continue;
    indices.push(a, a + surfaceVertexCount, b + surfaceVertexCount, a, b + surfaceVertexCount, b);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

/**
 * One published boundary as a curve in the plane it was extracted from.
 *
 * The lofted surfaces above interpolate the two cuts into a closed shell, and
 * a closed translucent shell seen from outside reads as a single blob: you are
 * always looking through its near and far walls at once, so the bow shock, the
 * sheath and the magnetopause pile into one wash of colour. Every textbook
 * draws this system as a cross-section instead, and the reason is that the
 * regions only separate when the shell is cut.
 *
 * This is also the closer reading of the artifact. The profiles are published
 * per plane; the loft is a construction on top of them, and the curve is not.
 * It stops where the extraction stops — the published sweep is +/-70 degrees of
 * solar zenith angle, so there is no tail here and none is drawn.
 */
export function boundaryProfileCurve(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  kind: GeospaceBoundaryKind,
  plane: GeospaceStructurePlane,
): { points: Array<[number, number]>; angleRangeDegrees: [number, number] } | null {
  const radii = decodeBoundaryProfile(definition, frame[plane][encodedBoundaryKey(kind)]);
  const points: Array<[number, number]> = [];
  let minimumAngle = Number.POSITIVE_INFINITY;
  let maximumAngle = Number.NEGATIVE_INFINITY;
  definition.anglesDegrees.forEach((angleDegrees, index) => {
    const radius = radii[index];
    if (radius === null || radius === undefined || !Number.isFinite(radius) || radius <= 0) return;
    const angle = THREE.MathUtils.degToRad(angleDegrees);
    points.push([radius * Math.cos(angle), radius * Math.sin(angle)]);
    minimumAngle = Math.min(minimumAngle, angleDegrees);
    maximumAngle = Math.max(maximumAngle, angleDegrees);
  });
  if (points.length < 2) return null;
  return { points, angleRangeDegrees: [minimumAngle, maximumAngle] };
}

export function createBoundaryProfileCurveGeometry(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  kind: GeospaceBoundaryKind,
  plane: GeospaceStructurePlane,
  positionForPlane: PlanePositionMapper,
) {
  const curve = boundaryProfileCurve(definition, frame, kind, plane);
  if (!curve) return null;
  const positions = new Float32Array((curve.points.length - 1) * 2 * 3);
  let offset = 0;
  for (let index = 0; index < curve.points.length - 1; index += 1) {
    const current = curve.points[index]!;
    const next = curve.points[index + 1]!;
    positionForPlane(current[0], current[1], plane).toArray(positions, offset);
    positionForPlane(next[0], next[1], plane).toArray(positions, offset + 3);
    offset += 6;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.userData.angleRangeDegrees = curve.angleRangeDegrees;
  geometry.userData.status = "published-profile-in-its-own-cut-plane";
  return geometry;
}

/**
 * The magnetosheath as the band between the two published curves.
 *
 * It is derived, not modelled: the shell exists exactly where both profiles
 * exist at the same angle, and its width at every angle is the published
 * bow-shock radius minus the published magnetopause radius. Where either
 * profile is missing there is no band, and nothing is drawn inside the band —
 * the shocked density, speed and temperature are on the cut planes.
 */
export function createMagnetosheathRibbonGeometry(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  plane: GeospaceStructurePlane,
  positionForPlane: PlanePositionMapper,
) {
  const outer = decodeBoundaryProfile(definition, frame[plane].bowShockRadiusU16);
  const inner = decodeBoundaryProfile(definition, frame[plane].magnetopauseProxyRadiusU16);
  const positions: number[] = [];
  const thickness: number[] = [];
  const indices: number[] = [];
  let previousBase = -1;
  definition.anglesDegrees.forEach((angleDegrees, index) => {
    const outerRadius = outer[index];
    const innerRadius = inner[index];
    if (
      outerRadius === null || outerRadius === undefined
      || innerRadius === null || innerRadius === undefined
      || !(outerRadius > innerRadius)
    ) {
      previousBase = -1;
      return;
    }
    const angle = THREE.MathUtils.degToRad(angleDegrees);
    const base = positions.length / 3;
    positionForPlane(innerRadius * Math.cos(angle), innerRadius * Math.sin(angle), plane)
      .toArray(positions, base * 3);
    positionForPlane(outerRadius * Math.cos(angle), outerRadius * Math.sin(angle), plane)
      .toArray(positions, (base + 1) * 3);
    thickness.push(outerRadius - innerRadius, outerRadius - innerRadius);
    if (previousBase >= 0) {
      indices.push(previousBase, previousBase + 1, base + 1, previousBase, base + 1, base);
    }
    previousBase = base;
  });
  if (indices.length === 0) return null;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(Float32Array.from(positions), 3));
  geometry.setAttribute("sheathThicknessRe", new THREE.BufferAttribute(Float32Array.from(thickness), 1));
  geometry.setIndex(indices);
  geometry.userData.status = "region-between-two-published-profiles";
  geometry.userData.thicknessUnits = "Earth radii (R_E)";
  return geometry;
}

export function createProjectedLineSegmentsGeometry(
  definition: GeospaceStructuresDefinition,
  encoded: EncodedProjectedStreamlines,
  plane: GeospaceStructurePlane,
  positionForPlane: PlanePositionMapper,
) {
  const lines = decodeProjectedStreamlines(definition, encoded);
  const segmentCount = lines.reduce((total, line) => total + Math.max(0, line.length - 1), 0);
  const positions = new Float32Array(segmentCount * 2 * 3);
  let offset = 0;
  lines.forEach((line) => {
    for (let index = 0; index < line.length - 1; index += 1) {
      const current = line[index];
      const next = line[index + 1];
      if (!current || !next) continue;
      positionForPlane(current[0], current[1], plane).toArray(positions, offset);
      positionForPlane(next[0], next[1], plane).toArray(positions, offset + 3);
      offset += 6;
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  return geometry;
}


/**
 * The edge of the cap, as a closed loop.
 *
 * The published extraction runs only from -70 to +70 degrees of polar angle, so
 * these boundaries are a CAP around the subsolar point: no flanks, no tail. A
 * real bow shock flares open and trails downstream indefinitely, and drawing a
 * translucent shell that simply stops made the near and far halves read as two
 * disconnected patches from an oblique camera rather than as one surface with
 * an edge.
 *
 * So the edge is drawn. A boundary that stops should look like it stops: the
 * rim says "the published surface ends here", which is true, where a fading
 * translucent hem said "this might continue", which is not.
 *
 * Returns null when the outermost ring has no valid radii at all, rather than a
 * collapsed loop at the origin.
 */
export function createBoundaryRimGeometry(
  definition: GeospaceStructuresDefinition,
  frame: EncodedFrameStructures,
  kind: GeospaceBoundaryKind,
  positionForGsm: GsmPositionMapper = (x, y, z) => new THREE.Vector3(x, y, z),
  azimuthSegments = 64,
): { geometry: THREE.BufferGeometry; thetaDegrees: number } | null {
  const profiles = decodedProfiles(definition, frame, kind);
  const rings = boundaryRings(definition);
  const thetaDegrees = rings[rings.length - 1];
  if (thetaDegrees === undefined) return null;
  const theta = THREE.MathUtils.degToRad(thetaDegrees);

  const points: number[] = [];
  for (let azimuthIndex = 0; azimuthIndex < azimuthSegments; azimuthIndex += 1) {
    const azimuth = (azimuthIndex / azimuthSegments) * Math.PI * 2;
    const radius = loftRadius(definition, profiles, thetaDegrees, azimuth);
    if (radius === null || !Number.isFinite(radius)) continue;
    const crossRadius = radius * Math.sin(theta);
    const point = positionForGsm(
      radius * Math.cos(theta),
      crossRadius * Math.cos(azimuth),
      crossRadius * Math.sin(azimuth),
    );
    points.push(point.x, point.y, point.z);
  }
  // A rim needs enough of the ring to read as one. Below that it would be a
  // scattering of arcs implying an edge that was never resolved.
  if (points.length < 3 * Math.floor(azimuthSegments / 2)) return null;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  geometry.userData = {
    representation: "outer edge of the published boundary extraction",
    thetaDegrees,
    why: "the extraction stops here; the surface is a dayside cap, not a closed shell",
  };
  return { geometry, thetaDegrees };
}
