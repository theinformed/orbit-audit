import * as THREE from "three";
import { RULER_EARTH_RADIUS_KM, activeDistanceScale, sharedDisplayRadius } from "./radial-ruler";
import { DEFAULT_ISOPYCNIC_KG_M3, densityKgM3, type DecodedFrame } from "./thermosphere";
import { buildIsopycnicSurface, type IsopycnicSurface } from "./thermosphere-surface";

/**
 * The thermosphere drawn as what it is: air that thins out, with no edge.
 *
 * ## Why this replaced a surface
 *
 * The first attempt drew one isopycnic surface — the altitude where density
 * equals a chosen value — as a solid shell. Two things were wrong with it, and
 * the second is the serious one.
 *
 * It was invisible. Measured on live NOAA WAM data the 1e-12 kg/m3 surface
 * spans 434-512 km, which is 78 km of relief on a 6,371 km globe: 1.2% of the
 * radius. Drawn true, that is about a pixel, so it rendered as a featureless
 * ball.
 *
 * And it invented a boundary. Picking one density and drawing it as a surface
 * says "the atmosphere stops here", which is false — density falls off roughly
 * exponentially and never stops. A student reading that picture would conclude
 * satellites orbit above the atmosphere, when the truth this layer exists to
 * teach is the opposite: they orbit INSIDE it, and that is why they decay.
 *
 * So the shell is gone and the field is rendered volumetrically instead:
 * opaque and warm where the air is thick, trailing to fully transparent as it
 * thins, with no boundary drawn anywhere. What a viewer sees is a glow that
 * fades out, satellites sitting inside it, and the glow swelling when a storm
 * heats the atmosphere. Nothing about that picture is exaggerated — see the
 * ruler note below.
 *
 * ## Why it is legible without any exaggeration
 *
 * The scene's shared radial ruler is logarithmic below geostationary, so this
 * band is already expanded relative to true scale. Measured against a globe
 * drawn at 100 scene units:
 *
 *     120 km -> +8.3      420 km (ISS) -> +22.1      1000 km -> +37.8
 *     geostationary -> +129.8
 *
 * The shell is 29.5 units thick on a 100-unit globe — a 2.14x gain over true
 * scale — so LEO sits visibly inside the glow and geostationary sits far
 * outside it, using the same ruler every other layer already uses. No vertical
 * exaggeration is applied here, and none is needed; the honesty rule for this
 * site is that a layer may never imply it is a measurement when it is not, and
 * a declared shared ruler is not a per-layer fudge.
 *
 * ## The published field
 *
 * NOAA WAM operational neutral density, 19 altitude levels from 120 to 1000 km
 * on a 46 x 45 latitude/longitude grid, stored as log10 density. Measured on a
 * live frame the field falls 6.7 decades across that range:
 *
 *     120 km  1.67e-08 kg/m3        420 km  2.50e-12        1000 km  3.07e-15
 *
 * At a fixed altitude the horizontal spread is real structure, not noise: at
 * 420 km the thinnest and thickest longitudes differ by 0.67 dex, a factor of
 * 4.7 in density and therefore in drag. That spread is what makes the day/night
 * bulge and the storm response visible.
 */

/** The published field's altitude range. Nothing is drawn outside it. */
export const THERMOSPHERE_VOLUME_ALTITUDE_KM = { low: 120, high: 1000 } as const;

/**
 * How many uniform altitude slabs the bake resamples onto.
 *
 * The published levels are NOT uniformly spaced — 30 km apart low down, then
 * 40, 50 and finally 200 km steps up to 1000. A 3D texture samples uniformly in
 * its third axis, so feeding the raw levels in would silently stretch the top
 * of the atmosphere over the bottom. Resampling onto a uniform grid fixes the
 * axis, and it is done by interpolating LOG density linearly in altitude, which
 * is the physically right interpolation: within a scale height log density is
 * near-linear in altitude, which is exactly why the raw levels can be coarse up
 * high without losing anything.
 */
export const THERMOSPHERE_VOLUME_ALTITUDE_SLABS = 96;

/**
 * The fixed log10 density range the opacity channel is drawn against, kg/m3.
 *
 * Fixed, never per-frame: see `bakeThermosphereVolume`. The same density must
 * be the same brightness at every hour or the layer cannot show a storm.
 */
export const THERMOSPHERE_DISPLAY_LOG10 = { floor: -15.6, ceiling: -7.2 } as const;


/**
 * Dense and warm at the bottom, cold and gone at the top.
 *
 * Ordered thin -> thick, because that is the direction the shader's normalized
 * density runs. The warm end reads as "air you can feel"; the cold end is never
 * actually seen as a colour because its opacity has already reached zero, and
 * it exists so the ramp does not clip.
 */
export const THERMOSPHERE_VOLUME_COLOR_HEX = [
  "#0b1030", "#231a4a", "#42307d", "#7a3f86", "#c1567a",
  "#ec7f52", "#ffb168", "#ffe0a8", "#fff8e6",
] as const;

export const THERMOSPHERE_VOLUME_RAMP_TEXELS = (THERMOSPHERE_VOLUME_COLOR_HEX.length - 1) * 32 + 1;

/**
 * The transfer function, and why each number is where it is.
 *
 * `logFloor`/`logCeiling` bracket the displayed density range, and are FIXED
 * (`THERMOSPHERE_DISPLAY_LOG10`) rather than measured per frame. They used to be
 * set from the field's own published extremes at bake time, which sounds like
 * the careful choice and is the opposite: a storm that lifts the whole column
 * lifts the extremes with it, the stretch cancels, and every hour draws the
 * same picture.
 *
 * `opacityCurveExponent` above 1 keeps the thin upper air from accumulating
 * into a milky haze over the whole globe: a long ray through very thin air
 * would otherwise integrate to something visible, which would put a false edge
 * back into the picture at the top of the march.
 *
 * `extinctionPerSceneUnit` and `maximumAccumulatedOpacity` are set by what the
 * layer is FOR, and were lowered after looking at it. The first tuning drew a
 * handsome solid orange band that hid every satellite inside it — which is a
 * picture that says the opposite of the lesson, since the whole point is to see
 * that LEO flies inside this air and geostationary does not. The atmosphere has
 * to read as a veil you can see through, not a shell you cannot, so the ceiling
 * is deliberately well below full opacity: even looking straight down the
 * thickest possible ray, the air never becomes a wall.
 */
export const THERMOSPHERE_VOLUME_TRANSFER = {
  opacityCurveExponent: 2.6,
  extinctionPerSceneUnit: 0.030,
  maximumAccumulatedOpacity: 0.66,
} as const;

export interface ThermosphereVolumeBakeOptions {
  earthSceneRadius: number;
  altitudeSlabs?: number;
  /** Sample counts for the horizontal axes; defaults follow the published grid. */
  longitudeCount?: number;
  latitudeCount?: number;
}

export interface ThermosphereVolumeBake {
  data: Uint8Array<ArrayBuffer>;
  longitudeCount: number;
  latitudeCount: number;
  altitudeCount: number;
  altitudeLowKm: number;
  altitudeHighKm: number;
  /**
   * log10 density at byte 0 and at byte 255. The FIXED display range, the same
   * for every frame — see `bakeThermosphereVolume`. What this frame actually
   * holds is `measured` below, which is a different question and used to be
   * confused with this one.
   */
  logFloor: number;
  logCeiling: number;
  sceneRadiusMinimum: number;
  sceneRadiusMaximum: number;
  /** Density actually found, for the card to quote without re-deriving it. */
  measured: { minLog10: number; maxLog10: number; sampleCount: number };
}

function altitudeToRadiusRe(altitudeKm: number): number {
  return (RULER_EARTH_RADIUS_KM + altitudeKm) / RULER_EARTH_RADIUS_KM;
}

/**
 * Decode the frame onto a uniform (longitude, latitude, altitude) byte grid.
 *
 * The byte is normalized log10 density, never linear density: a linear byte
 * would spend almost its whole range on the bottom 30 km and leave the entire
 * satellite band — 6 decades of it — inside one or two codes.
 */
export function bakeThermosphereVolume(
  frame: DecodedFrame,
  options: ThermosphereVolumeBakeOptions,
): ThermosphereVolumeBake {
  const altitudeCount = options.altitudeSlabs ?? THERMOSPHERE_VOLUME_ALTITUDE_SLABS;
  const longitudeCount = options.longitudeCount ?? 72;
  const latitudeCount = options.latitudeCount ?? 46;
  const low = THERMOSPHERE_VOLUME_ALTITUDE_KM.low;
  const high = THERMOSPHERE_VOLUME_ALTITUDE_KM.high;

  // First pass: gather log10 density, and the true extremes to scale against.
  const logs = new Float32Array(longitudeCount * latitudeCount * altitudeCount);
  let minLog = Number.POSITIVE_INFINITY;
  let maxLog = Number.NEGATIVE_INFINITY;
  let sampleCount = 0;

  for (let k = 0; k < altitudeCount; k += 1) {
    const altitude = altitudeCount === 1
      ? low
      : low + ((high - low) * k) / (altitudeCount - 1);
    for (let j = 0; j < latitudeCount; j += 1) {
      const latitude = latitudeCount === 1 ? 0 : -90 + (180 * j) / (latitudeCount - 1);
      for (let i = 0; i < longitudeCount; i += 1) {
        const longitude = (360 * i) / longitudeCount;
        const density = densityKgM3(frame, latitude, longitude, altitude);
        const index = k * latitudeCount * longitudeCount + j * longitudeCount + i;
        if (density === null || !Number.isFinite(density) || density <= 0) {
          logs[index] = Number.NaN;
          continue;
        }
        const log10 = Math.log10(density);
        logs[index] = log10;
        if (log10 < minLog) minLog = log10;
        if (log10 > maxLog) maxLog = log10;
        sampleCount += 1;
      }
    }
  }

  // A frame with nothing in it has no extremes to report, and must not report
  // a pair of finite numbers that were never measured.
  if (sampleCount === 0) {
    minLog = Number.NaN;
    maxLog = Number.NaN;
  }

  // THE DISPLAY SCALE IS FIXED: the same density is the same brightness at
  // every hour, or the layer cannot show a storm at all.
  //
  // It used to be measured from the frame being drawn -- min and max over that
  // hour's own field, stretched to fill the byte range. Under that rule a storm
  // that lifts the whole column produces a MATHEMATICALLY IDENTICAL opacity
  // channel, because the stretch cancels exactly the change the layer exists to
  // show. The size of what was lost, measured on a live 13-frame WAM bundle
  // (2026-08-19, quiet): the global mean log density moved 0.012 dex across the
  // release, which on this fixed 8.4-dex range is 0.4 of 255 codes and under
  // per-frame normalisation is exactly zero. A real storm is nearer 0.3 dex --
  // 9 codes here, still zero there.
  //
  // Being honest about what this change did NOT do, because it was made while
  // hunting a "the thermosphere is static" report and is not the fix for it.
  // Measured over the whole canvas at 1440x900, thermosphere alone, satellites
  // hidden, between 19:40Z and 23:40Z: mean per-pixel difference 34.7/765 with
  // per-frame normalisation and 35.3/765 with this fixed range. On a quiet
  // bundle the two rules draw almost the same pictures, because the visible
  // hour-to-hour motion is carried by the COLOUR channel below -- the day/night
  // bulge migrating across the geographic grid -- and not by the amount of air.
  // This range is what makes the amount visible when there is a storm to see.
  //
  // The bounds bracket the published field with room to spare. Measured on a
  // live NOAA WAM frame: 1.67e-8 kg/m3 at 120 km (log -7.78 mean, -7.49 max)
  // falling to 3.07e-15 at 1000 km (log -14.51 mean, -15.22 min). A storm
  // raises the whole column, so the ceiling is set above the quiet maximum
  // rather than at it.
  //
  // `minLog`/`maxLog` are left holding what was actually FOUND in this frame,
  // and are reported as `measured` below. The two must not be the same numbers:
  // the display scale is what the picture is drawn against, and the measurement
  // is what the card is entitled to quote about the air.
  const displayFloor = THERMOSPHERE_DISPLAY_LOG10.floor;
  const displayCeiling = THERMOSPHERE_DISPLAY_LOG10.ceiling;

  // Two channels, because this field carries two different facts and encoding
  // only one of them is what made the first version read as a featureless ball.
  //
  // Density falls 6.7 decades from 120 to 1000 km. The structure a reader
  // actually needs to see — the day/night bulge, the storm response — is the
  // variation at a FIXED altitude, and that is about 0.67 dex, roughly a tenth
  // of the vertical range. Normalized against the whole column it is a 10%
  // wobble on a ramp dominated by height, which is invisible: the layer drew as
  // a smooth uniform shell and Sean's word for it was "a perfect storm",
  // meaning it looked the same everywhere.
  //
  //   R: absolute log density, spanning the whole column. Drives OPACITY, so
  //      the air still thins out with height and still trails to nothing.
  //   G: the anomaly at THIS altitude — how this sample compares with the
  //      lightest and densest air on its own slab. Drives COLOUR, so the bulge
  //      and the storm show as hue instead of being crushed by the falloff.
  //
  // Separating them is what lets one picture say both "there is less air up
  // here" and "there is more air over there", which are the two things the
  // layer exists to teach.
  //
  // The exact cost of making G relative, since it is the obvious suspect the
  // next time this layer reads as static: a change that lifts a whole slab by
  // the same amount CANCELS in it. Measured on synthetic frames half a decade
  // apart (`tests/thermosphere-clock.test.ts`), a uniform 0.3 dex lift moves R
  // by 9 codes and moves G by at most 1, which is rounding. So colour can never
  // show a storm; only opacity can, and only on a fixed scale. What G does
  // carry, and carries well, is the pattern: measured across a live bundle,
  // consecutive hourly frames differ by a mean of 23 to 56 codes in G against
  // 1.5 to 4.3 in R, because the day/night bulge moves 15 degrees of longitude
  // an hour and that is a genuine change in the field's shape.
  const span = displayCeiling - displayFloor;
  const slab = longitudeCount * latitudeCount;
  const data = new Uint8Array(new ArrayBuffer(logs.length * 2));
  for (let k = 0; k < altitudeCount; k += 1) {
    let slabMin = Number.POSITIVE_INFINITY;
    let slabMax = Number.NEGATIVE_INFINITY;
    for (let s = 0; s < slab; s += 1) {
      const value = logs[k * slab + s]!;
      if (!Number.isFinite(value)) continue;
      if (value < slabMin) slabMin = value;
      if (value > slabMax) slabMax = value;
    }
    // A slab with no spread must not divide by zero, and must not be given a
    // fake one: flat air is drawn flat, in the middle of the ramp.
    const slabSpan = Number.isFinite(slabMin) && slabMax - slabMin > 1e-6 ? slabMax - slabMin : 0;
    for (let s = 0; s < slab; s += 1) {
      const index = k * slab + s;
      const log10 = logs[index]!;
      if (!Number.isFinite(log10)) {
        data[index * 2] = 0;
        data[index * 2 + 1] = 0;
        continue;
      }
      const absolute = (log10 - displayFloor) / span;
      const anomaly = slabSpan === 0 ? 0.5 : (log10 - slabMin) / slabSpan;
      data[index * 2] = Math.max(0, Math.min(255, Math.round(absolute * 255)));
      data[index * 2 + 1] = Math.max(0, Math.min(255, Math.round(anomaly * 255)));
    }
  }

  return {
    data,
    longitudeCount,
    latitudeCount,
    altitudeCount,
    altitudeLowKm: low,
    altitudeHighKm: high,
    logFloor: displayFloor,
    logCeiling: displayCeiling,
    sceneRadiusMinimum: sharedDisplayRadius(altitudeToRadiusRe(low), options.earthSceneRadius),
    sceneRadiusMaximum: sharedDisplayRadius(altitudeToRadiusRe(high), options.earthSceneRadius),
    measured: { minLog10: minLog, maxLog10: maxLog, sampleCount },
  };
}

let sharedRampTexture: THREE.DataTexture | null = null;

function thermosphereRampTexture(): THREE.DataTexture {
  if (!sharedRampTexture) {
    const texels = THERMOSPHERE_VOLUME_RAMP_TEXELS;
    const data = new Uint8Array(texels * 4);
    const stops = THERMOSPHERE_VOLUME_COLOR_HEX.map((hex) => new THREE.Color(hex));
    for (let i = 0; i < texels; i += 1) {
      const t = i / (texels - 1);
      const scaled = t * (stops.length - 1);
      const lower = Math.min(stops.length - 1, Math.floor(scaled));
      const upper = Math.min(stops.length - 1, lower + 1);
      const colour = stops[lower]!.clone().lerp(stops[upper]!, scaled - lower);
      data[i * 4] = Math.round(colour.r * 255);
      data[i * 4 + 1] = Math.round(colour.g * 255);
      data[i * 4 + 2] = Math.round(colour.b * 255);
      data[i * 4 + 3] = 255;
    }
    sharedRampTexture = new THREE.DataTexture(data, texels, 1);
    sharedRampTexture.needsUpdate = true;
  }
  return sharedRampTexture;
}

const VOLUME_VERTEX_SHADER = `
  varying vec3 vLocalPosition;
  void main() {
    vLocalPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const VOLUME_FRAGMENT_SHADER = `
  precision highp float;
  precision highp sampler3D;
  uniform sampler3D densityVolume;
  uniform sampler2D colourRamp;
  uniform vec3 cameraLocalPosition;
  uniform float rulerTrueDistance;
  uniform float earthSceneRadius;
  uniform float sceneRadiusMinimum;
  uniform float sceneRadiusMaximum;
  uniform float altitudeLowKm;
  uniform float altitudeHighKm;
  uniform float opacityCurveExponent;
  uniform float extinction;
  uniform float minimumTransmittance;
  varying vec3 vLocalPosition;

  const int MAX_STEPS = 128;
  const float RULER_A = 18.202857142857143;
  const float RULER_ANCHOR_RE = 6.6170146;
  const float EARTH_RADIUS_KM = 6371.0;
  const float PI = 3.14159265358979323846;
  const float TWO_PI = 6.28318530717958647692;

  // The shared radial ruler's inverse. Altitude has to be recovered in PHYSICAL
  // space: the ruler is steeply nonlinear here, so treating scene units as
  // proportional to altitude would put the 1000 km top of the field at about
  // 350 km and drown every satellite in it.
  float logBranchDrawn(float r) {
    return 1.0 + 0.28 * log(1.0 + RULER_A * max(0.0, r - 1.0));
  }

  float reFromDrawn(float drawn) {
    float x = drawn / earthSceneRadius;
    if (rulerTrueDistance > 0.5) return max(1.0, x);
    float anchorDrawn = logBranchDrawn(RULER_ANCHOR_RE);
    if (x <= anchorDrawn) return 1.0 + (exp((x - 1.0) / 0.28) - 1.0) / RULER_A;
    return RULER_ANCHOR_RE * x / anchorDrawn;
  }

  vec2 sphereIntersect(vec3 origin, vec3 direction, float radius) {
    float b = dot(origin, direction);
    float c = dot(origin, origin) - radius * radius;
    float disc = b * b - c;
    if (disc < 0.0) return vec2(1.0, -1.0);
    float root = sqrt(disc);
    return vec2(-b - root, -b + root);
  }

  float hash(vec2 seed) {
    return fract(sin(dot(seed, vec2(12.9898, 78.233))) * 43758.5453);
  }

  void main() {
    vec3 direction = normalize(vLocalPosition - cameraLocalPosition);
    vec2 outer = sphereIntersect(cameraLocalPosition, direction, sceneRadiusMaximum);
    if (outer.x > outer.y) discard;
    float tNear = max(outer.x, 0.0);
    float tFar = outer.y;

    // The globe is opaque: a ray that reaches Earth stops there, so the far
    // side of the atmosphere never shows through the planet.
    vec2 earth = sphereIntersect(cameraLocalPosition, direction, earthSceneRadius);
    if (earth.x <= earth.y && earth.y > 0.0 && earth.x < tFar) {
      tFar = max(earth.x, tNear);
    }
    if (tFar - tNear < 1e-4) discard;

    float span = tFar - tNear;
    float stepLength = span / float(MAX_STEPS);
    // Jitter the first sample so the fixed step count does not draw itself as
    // concentric rings across the limb.
    float offset = hash(gl_FragCoord.xy) * stepLength;

    vec3 accumulated = vec3(0.0);
    float transmittance = 1.0;

    for (int i = 0; i < MAX_STEPS; i += 1) {
      float t = tNear + offset + float(i) * stepLength;
      if (t > tFar) break;
      vec3 samplePosition = cameraLocalPosition + direction * t;
      float drawn = length(samplePosition);
      if (drawn < sceneRadiusMinimum || drawn > sceneRadiusMaximum) continue;

      float altitudeKm = (reFromDrawn(drawn) - 1.0) * EARTH_RADIUS_KM;
      float w = (altitudeKm - altitudeLowKm) / (altitudeHighKm - altitudeLowKm);
      if (w < 0.0 || w > 1.0) continue;

      vec3 unit = samplePosition / drawn;
      // Geographic frame: y is the polar axis and theta is longitude, matching
      // how every other geographic layer in this scene is built.
      float latitude = asin(clamp(unit.y, -1.0, 1.0));
      float longitude = atan(unit.z, unit.x);
      float u = fract(longitude / TWO_PI);
      float v = (latitude + PI * 0.5) / PI;

      vec2 sampled = texture(densityVolume, vec3(u, v, w)).rg;
      float absolute = sampled.r;
      float anomaly = sampled.g;
      if (absolute <= 0.0) continue;

      // How much air there is sets how much it hides; how unusual that air is
      // for its altitude sets what colour it is.
      float opacity = pow(absolute, opacityCurveExponent);
      float absorbed = 1.0 - exp(-opacity * extinction * stepLength);
      vec3 colour = texture(colourRamp, vec2(anomaly, 0.5)).rgb;
      accumulated += transmittance * absorbed * colour;
      transmittance *= 1.0 - absorbed;
      if (transmittance < minimumTransmittance) break;
    }

    float alpha = 1.0 - transmittance;
    if (alpha <= 0.002) discard;
    gl_FragColor = vec4(accumulated, alpha);
  }
`;

export interface ThermosphereVolumeMeshOptions extends ThermosphereVolumeBakeOptions {
  transfer?: Partial<typeof THERMOSPHERE_VOLUME_TRANSFER>;
}

export interface ThermosphereVolumeMeshResult {
  mesh: THREE.Mesh;
  bake: ThermosphereVolumeBake;
}

export function createThermosphereVolumeMesh(
  frame: DecodedFrame,
  options: ThermosphereVolumeMeshOptions,
): ThermosphereVolumeMeshResult {
  const bake = bakeThermosphereVolume(frame, options);
  const transfer = { ...THERMOSPHERE_VOLUME_TRANSFER, ...options.transfer };

  const texture = new THREE.Data3DTexture(
    bake.data,
    bake.longitudeCount,
    bake.latitudeCount,
    bake.altitudeCount,
  );
  texture.format = THREE.RGFormat;
  texture.type = THREE.UnsignedByteType;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  // Longitude wraps and latitude does not; the altitude axis must clamp so the
  // dense bottom of the atmosphere can never wrap round onto the thin top.
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.wrapR = THREE.ClampToEdgeWrapping;
  texture.unpackAlignment = 1;
  texture.needsUpdate = true;

  const material = new THREE.ShaderMaterial({
    uniforms: {
      densityVolume: { value: texture },
      colourRamp: { value: thermosphereRampTexture() },
      cameraLocalPosition: { value: new THREE.Vector3() },
      rulerTrueDistance: { value: activeDistanceScale() === "true-distance" ? 1 : 0 },
      earthSceneRadius: { value: options.earthSceneRadius },
      sceneRadiusMinimum: { value: bake.sceneRadiusMinimum },
      sceneRadiusMaximum: { value: bake.sceneRadiusMaximum },
      altitudeLowKm: { value: bake.altitudeLowKm },
      altitudeHighKm: { value: bake.altitudeHighKm },
      opacityCurveExponent: { value: transfer.opacityCurveExponent },
      extinction: { value: transfer.extinctionPerSceneUnit },
      minimumTransmittance: { value: 1 - transfer.maximumAccumulatedOpacity },
    },
    vertexShader: VOLUME_VERTEX_SHADER,
    fragmentShader: VOLUME_FRAGMENT_SHADER,
    transparent: true,
    depthWrite: false,
    // Depth testing is OFF, and the reason satellites stay visible is the
    // render order below rather than the depth buffer.
    //
    // This used to read depthTest: true, to keep the glow off spacecraft
    // flying in front of it. It did that, and it also removed the layer from
    // the entire globe-facing column: the proxy geometry is a BackSide sphere
    // at the top of the volume, so every fragment it draws is on the FAR side
    // of the atmosphere, further from the camera than the opaque Earth at
    // radius 100. The depth test rejected all of them over the disc, and the
    // layer could only ever draw in the limb ring. Measured on the shipped
    // build, at 1440 with the layer alone, as warm excess (mean R minus B,
    // the glow being warm and the globe teal): -28.2 at r/R 0-0.3, -29.2 at
    // 0.3-0.6, -25.9 at 0.6-0.9 -- no glow anywhere over the disc -- against
    // +53.4 in the ring at r/R 1.00-1.15. The whole layer was in the ring.
    //
    // Nothing is lost by switching the test off, because the occlusion this
    // layer needs is already done analytically in the fragment shader: a ray
    // that reaches the globe stops at the Earth intersection, so the far side
    // never shows through the planet. Satellites stay visible because they are
    // transparent at renderOrder 0 and write no depth, and this volume now
    // draws before them; see the render order below. This is the same
    // arrangement ionosphere-density-volume.ts arrived at for the same
    // BackSide-proxy geometry.
    depthTest: false,
    side: THREE.BackSide,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.OneFactor,
    blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
  });
  material.addEventListener("dispose", () => texture.dispose());

  const geometry = new THREE.SphereGeometry(bake.sceneRadiusMaximum * 1.002, 64, 40);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  // Drawn BEFORE the satellites, which are transparent at renderOrder 0 and
  // write no depth, so they paint on top of the glow instead of being tested
  // against it -- which is how a spacecraft in the thick air stays visible now
  // that the depth test is off. At the old order of 12 the volume composited
  // over every satellite inside it, which is the opposite of the point of the
  // layer. -4 rather than the ionosphere volume's -3 so that when both are on,
  // the neutral air is the ground the electron density is drawn against.
  mesh.renderOrder = -4;
  mesh.onBeforeRender = (_renderer, _scene, camera) => {
    mesh.updateWorldMatrix(true, false);
    (material.uniforms.cameraLocalPosition!.value as THREE.Vector3)
      .copy(camera.position)
      .applyMatrix4(mesh.matrixWorld.clone().invert());
  };
  mesh.userData = {
    representation: "raymarched-neutral-density-volume",
    quantity: "neutral mass density",
    units: "kg m-3",
    volumeRendering: true,
    altitudeLowKm: bake.altitudeLowKm,
    altitudeHighKm: bake.altitudeHighKm,
    log10DensityFloor: bake.logFloor,
    log10DensityCeiling: bake.logCeiling,
    verticalExaggeration: 1,
  };
  return { mesh, bake };
}

/**
 * The scene layer, with the same surface API the isopycnic layer had.
 *
 * It still computes the isopycnic altitude, because that number is worth
 * showing — "the 1e-12 kg/m3 level is at 486 km tonight, and 41 km higher than
 * it was this morning" is exactly the storm story. What changed is that the
 * number is now TEXT on the card instead of a shell in the scene: a quantity
 * this small relative to the globe is legible as a figure and illegible as
 * geometry, and drawing it as geometry also drew a boundary that is not there.
 */
export class ThermosphereVolumeLayer {
  private readonly group = new THREE.Group();
  private mesh: THREE.Mesh | null = null;
  private level = DEFAULT_ISOPYCNIC_KG_M3;
  private frame: DecodedFrame | null = null;
  private summary: IsopycnicSurface | null = null;
  private bake: ThermosphereVolumeBake | null = null;

  constructor(private readonly earthSceneRadius: number) {
    this.group.name = "thermosphere-volume";
    this.group.visible = false;
  }

  object3d(): THREE.Group {
    return this.group;
  }

  setEnabled(visible: boolean): void {
    this.group.visible = visible;
  }

  /**
   * Follow a different density level.
   *
   * Only the SUMMARY is rebuilt, never the volume: the raymarched field draws
   * every density in the published column and does not depend on which one the
   * reader is asking the height of. This used to call `setFrame`, which re-baked
   * the whole 72x46x96 texture -- about 85 ms of work -- to change three
   * numbers on a card.
   */
  setLevel(level: number): void {
    if (level === this.level) return;
    this.level = level;
    if (!this.frame) return;
    this.summary = buildIsopycnicSurface(this.frame, {
      earthSceneRadius: this.earthSceneRadius,
      level: this.level,
    });
  }

  currentLevel(): number {
    return this.level;
  }

  lastSurface(): IsopycnicSurface | null {
    return this.summary;
  }

  lastBake(): ThermosphereVolumeBake | null {
    return this.bake;
  }

  /**
   * Draw nothing, because the release does not cover the selected instant.
   *
   * The frame, the summary and the bake all go with the mesh. Leaving any of
   * them behind is how a card goes on quoting a height for an hour that is not
   * being drawn -- and `lastSurface()` returning null is exactly what makes the
   * legend fall to its no-data state instead.
   */
  clear(): void {
    this.dispose();
    this.frame = null;
    this.summary = null;
    this.bake = null;
  }

  setFrame(frame: DecodedFrame): IsopycnicSurface {
    this.frame = frame;
    this.dispose();

    const { mesh, bake } = createThermosphereVolumeMesh(frame, {
      earthSceneRadius: this.earthSceneRadius,
    });
    this.mesh = mesh;
    this.bake = bake;
    this.group.add(mesh);

    // Kept for the card, not for the scene.
    this.summary = buildIsopycnicSurface(frame, {
      earthSceneRadius: this.earthSceneRadius,
      level: this.level,
    });
    return this.summary;
  }

  private dispose(): void {
    if (!this.mesh) return;
    this.group.remove(this.mesh);
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.mesh = null;
  }
}
