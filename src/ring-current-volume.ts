import * as THREE from "three";
import { activeDistanceScale, sharedDisplayRadius } from "./radial-ruler";
import {
  ENERGY_RAMP_STOPS,
  RING_CURRENT_ENERGY_SCALE,
  RING_CURRENT_FORMATION,
  energyAtLKeV,
  energyRampPosition,
  type DriftSpecies,
  type InjectionCorridor,
  type RingCurrentFormation,
  type TrappedRegion,
} from "./ring-current-illustration";

/**
 * The ring current as a glowing torus that FORMS, rather than a translucent lid
 * that sits there.
 *
 * ## Why this exists
 *
 * The trapped-drift region was drawn as a SURFACE: one skin stretched over the
 * region's outer edge, flat-shaded, in the equatorial plane. It is the right
 * region and it is bounded by the right physics, and it still read as a grey
 * teardrop sitting under the Earth. Sean's reference for what this should look
 * like is the NASA inner-magnetosphere rendering: a fat luminous doughnut with
 * structure inside it, the belts nested within, everything soft-edged and
 * layered. His words: "I really wanted to see that develop the ring current."
 *
 * A surface cannot do that. A surface has no inside, so it cannot show that the
 * population is denser in the middle of the region than at its edges, it cannot
 * fade at the boundary, and anything drawn behind it is simply behind it. The
 * belts are already ray-marched volumes and read as objects; this now uses the
 * same machinery.
 *
 * ## What is drawn, and what is claimed
 *
 * Nothing here is measured, and the layer's badge has always said so: there is
 * no gridded ring-current product in any feed this site fetches. What IS
 * measured about this population is Dst — the number in the site's own storm
 * banner — and Dst is one number with no map, which is exactly why the SHAPE
 * has to be reconstructed and the card says so in those words.
 *
 * What IS computed, and what the volume shows, is drift physics in the same
 * Volland-Stern convection + corotation field the plasmasphere is eroded by:
 *
 *   - WHERE the population can live: bounded below by the inner edge and above
 *     by the Alfven layer, the last closed drift path, which is computed per
 *     local time and is why the region is a teardrop and not a ring.
 *   - HOW ENERGETIC it is at a given place: `energyAtLKeV`, the same
 *     (referenceL / L)^3 the markers and the legend already use, so the colour
 *     of a point in the volume means exactly what the legend bar means.
 *   - HOW IT FILLS: the supply arriving from the tail and the westward drift
 *     closing the ring behind it, both read off traced drift paths. See
 *     `RING_CURRENT_FORMATION` in `ring-current-illustration.ts` for what that
 *     motion claims and, more importantly, what it does not.
 *
 * The one thing added here that is not in the drift solution is the FILLING
 * PROFILE: how the population thins toward both edges and away from the
 * equator. That is a declared display profile, not a measurement, and it is
 * deliberately the simplest thing that is not a lie — smooth, monotone toward
 * each edge, and carrying no numbers a reader could misread. It is documented
 * on `RING_CURRENT_VOLUME_PROFILE` and named in the card's userData.
 */

/**
 * The filling profile. Every number here is a display choice and none is a
 * measurement, which is why they are collected in one exported place rather
 * than scattered through the shader.
 */
export const RING_CURRENT_VOLUME_PROFILE = {
  /**
   * Where the population is brightest between the inner edge and the Alfven
   * layer, as a fraction of the way across. Slightly inside the middle because
   * the drift shells crowd inward as they close.
   */
  radialPeak: 0.40,
  /**
   * The width of that bright core, in the same fraction-across units.
   *
   * Wide on purpose. The first version used `sin(pi * across)^3.4`, which is a
   * narrow annulus with a hole in the middle and nothing at either edge, and
   * that is what put a thin red ring on screen instead of a fat doughnut: with
   * only the middle of the region drawn, only the middle of the ENERGY range
   * was drawn too, so the whole object came out one colour. Across the region
   * as a whole the ion energy runs a factor of thirty (L^-3 over L 2 to 6), and
   * drawing the whole region is what lets the ramp actually show: violet at the
   * outer edge, orange-white in the deep core.
   */
  radialCoreWidth: 0.34,
  /** How much of the region's brightness is flat fill rather than the core. */
  radialBaseFill: 0.42,
  /** How fast the population fades in at the inner edge, fraction across. */
  innerSoftness: 0.22,
  /** And out at the Alfven layer. Wider: the boundary is where it thins away. */
  outerSoftness: 0.34,
  /**
   * The half-thickness in magnetic latitude, degrees. Ring-current ions are
   * near-equatorially mirroring, so the population is a fat ring rather than a
   * shell, but it is NOT a flat disc and drawing it as one is what made the
   * surface version read as a lid.
   */
  latitudeHalfWidthDeg: 15,
  /**
   * The supply from the tail is drawn fatter in latitude than the trapped
   * population, because the plasma sheet IS thicker than the near-equatorial
   * population it feeds. A display choice in its magnitude, not in its sign.
   */
  supplyLatitudeHalfWidthDeg: 13,
  /** How dense the drawn supply is against the trapped population. */
  supplyDensity: 0.62,
  /**
   * How much of the supply's outer edge is faded out, as a fraction of the
   * drawn corridor.
   *
   * The traced domain stops at L 9 and the plasma sheet does not: cutting the
   * supply off there drew a clean arc across space, which reads as a rendering
   * wall rather than as the edge of what was computed. Faded, the picture says
   * what is true — this is as far out as the drift was integrated.
   */
  supplyOuterFade: 0.16,
  /**
   * Emission brightness at the bottom and the top of the energy ramp.
   *
   * Hue still means exactly what the legend bar says; this scales how much
   * light a sample of that hue emits, so the hot deep core reads as hot instead
   * of being averaged into the cool outer edge by the ray march. A display
   * choice, declared here rather than buried in the shader.
   */
  emissionAtRampFloor: 0.55,
  emissionAtRampCeiling: 1.75,
  extinctionPerSceneUnit: 0.030,
  maximumAccumulatedOpacity: 0.62,
} as const;

/** Texels in the energy ramp lookup the shader samples. */
export const RING_CURRENT_RAMP_TEXELS = 257;

function rampTexels(): Uint8Array {
  const data = new Uint8Array(new ArrayBuffer(RING_CURRENT_RAMP_TEXELS * 4));
  for (let index = 0; index < RING_CURRENT_RAMP_TEXELS; index += 1) {
    const t = index / (RING_CURRENT_RAMP_TEXELS - 1);
    // Walk the module's own stops, so the volume, the legend bar and any marker
    // can never disagree about what a colour means.
    let colour: readonly [number, number, number] = ENERGY_RAMP_STOPS[0]!.colour;
    for (let stop = 1; stop < ENERGY_RAMP_STOPS.length; stop += 1) {
      const lower = ENERGY_RAMP_STOPS[stop - 1]!;
      const upper = ENERGY_RAMP_STOPS[stop]!;
      if (t <= upper.at || stop === ENERGY_RAMP_STOPS.length - 1) {
        const span = upper.at - lower.at;
        const local = span <= 0 ? 0 : Math.min(1, Math.max(0, (t - lower.at) / span));
        colour = [
          lower.colour[0] + (upper.colour[0] - lower.colour[0]) * local,
          lower.colour[1] + (upper.colour[1] - lower.colour[1]) * local,
          lower.colour[2] + (upper.colour[2] - lower.colour[2]) * local,
        ];
        break;
      }
    }
    data[index * 4] = Math.round(colour[0] * 255);
    data[index * 4 + 1] = Math.round(colour[1] * 255);
    data[index * 4 + 2] = Math.round(colour[2] * 255);
    data[index * 4 + 3] = 255;
  }
  return data;
}

let sharedRamp: THREE.DataTexture | null = null;

function ringCurrentRampTexture(): THREE.DataTexture {
  if (!sharedRamp) {
    sharedRamp = new THREE.DataTexture(rampTexels(), RING_CURRENT_RAMP_TEXELS, 1, THREE.RGBAFormat);
    sharedRamp.colorSpace = THREE.SRGBColorSpace;
    sharedRamp.minFilter = THREE.LinearFilter;
    sharedRamp.magFilter = THREE.LinearFilter;
    sharedRamp.wrapS = THREE.ClampToEdgeWrapping;
    sharedRamp.needsUpdate = true;
  }
  return sharedRamp;
}

/**
 * The Alfven layer as a texture the shader can read per local time.
 *
 * The boundary is genuinely different at every magnetic local time — that
 * asymmetry IS the teardrop, and it is the whole reason the plasmapause bulges
 * at dusk — so it cannot be collapsed to one radius without throwing away the
 * shape the layer exists to show.
 */
function boundaryTexture(region: TrappedRegion, maximumL: number): THREE.DataTexture {
  const count = region.mltHours.length;
  const data = new Uint8Array(new ArrayBuffer(count * 4));
  for (let index = 0; index < count; index += 1) {
    const normalized = Math.min(1, Math.max(0, region.outerL[index]! / maximumL));
    const quantized = Math.round(normalized * 65535);
    // 16 bits across two channels: one byte of L over a domain this wide is a
    // 0.04 Re step, which is visible as terracing on a smooth boundary.
    data[index * 4] = quantized & 0xff;
    data[index * 4 + 1] = (quantized >> 8) & 0xff;
    data[index * 4 + 3] = 255;
  }
  const texture = new THREE.DataTexture(data, count, 1, THREE.RGBAFormat);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  // Local time wraps: midnight is adjacent to midnight.
  texture.wrapS = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

/**
 * The arrival map: when the tail supply reaches each cell of a (MLT, L) grid.
 *
 * ONE byte for the time, not two. The boundary above needs sixteen bits because
 * a 0.04 Re step in a drawn radius is a visible terrace; this drives a soft
 * front that is feathered over several percent of the loop anyway, so a 1/256
 * step in it cannot be seen. One byte also means the texture can be linearly
 * filtered, which a two-byte split cannot: interpolating across a carry between
 * the low and high byte produces a value from neither side.
 */
function corridorTexture(corridor: InjectionCorridor): THREE.DataTexture {
  const data = new Uint8Array(new ArrayBuffer(corridor.mltBins * corridor.lBins * 4));
  for (let index = 0; index < corridor.mltBins * corridor.lBins; index += 1) {
    const seconds = corridor.arrivalSeconds[index]!;
    const normalized = Number.isFinite(seconds) ? Math.min(1, Math.max(0, seconds / corridor.spanSeconds)) : 1;
    data[index * 4] = Math.round(normalized * 255);
    data[index * 4 + 1] = Math.round(Math.min(1, Math.max(0, corridor.weight[index]!)) * 255);
    data[index * 4 + 3] = 255;
  }
  const texture = new THREE.DataTexture(data, corridor.mltBins, corridor.lBins, THREE.RGBAFormat);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return texture;
}

/** Per-shell lap time and supply-arrival time, the two clocks the fill runs on. */
function shellTexture(formation: RingCurrentFormation): THREE.DataTexture {
  const count = formation.shellBins;
  const data = new Uint8Array(new ArrayBuffer(count * 4));
  for (let index = 0; index < count; index += 1) {
    data[index * 4] = Math.round(Math.min(1, formation.lapSeconds[index]! / formation.lapSpanSeconds) * 255);
    data[index * 4 + 1] = Math.round(Math.min(1, formation.seedSeconds[index]! / formation.corridor.spanSeconds) * 255);
    data[index * 4 + 3] = 255;
  }
  const texture = new THREE.DataTexture(data, count, 1, THREE.RGBAFormat);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return texture;
}

const VERTEX_SHADER = `
  varying vec3 vLocalPosition;
  void main() {
    vLocalPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;
  uniform sampler2D energyRamp;
  uniform sampler2D boundary;
  uniform sampler2D corridorMap;
  uniform sampler2D shellMap;
  uniform vec3 cameraLocalPosition;
  uniform float rulerTrueDistance;
  uniform float earthSceneRadius;
  uniform float sceneRadiusMaximum;
  uniform float innerL;
  uniform float boundaryMaximumL;
  uniform float referenceEnergyKeV;
  uniform float referenceL;
  uniform float energyLogMinimum;
  uniform float energyLogSpan;
  uniform float radialPeak;
  uniform float radialCoreWidth;
  uniform float radialBaseFill;
  uniform float innerSoftness;
  uniform float outerSoftness;
  uniform float latitudeHalfWidth;
  uniform float supplyLatitudeHalfWidth;
  uniform float supplyDensity;
  uniform float supplyOuterFade;
  uniform float emissionFloor;
  uniform float emissionCeiling;
  uniform float extinction;
  uniform float minimumTransmittance;

  // The formation clock and the two computed fields it reads.
  uniform float formationEnabled;
  uniform float formationSeconds;
  uniform float fillSeconds;
  uniform float holdSeconds;
  uniform float decaySeconds;
  uniform float residualFill;
  uniform float fillFeatherRadians;
  uniform float injectionHalfAngle;
  uniform float frontDispersion;
  uniform float frontFeatherSeconds;
  uniform float corridorLMinimum;
  uniform float corridorLSpan;
  uniform float corridorSpanSeconds;
  uniform float shellLMinimum;
  uniform float shellLSpan;
  uniform float shellLapSpanSeconds;

  varying vec3 vLocalPosition;

  // 112, the same as the surface-replacing version shipped with: the drawn
  // domain grew by only 3% in radius when the supply was added (the ruler
  // compresses L 7 to L 9 into almost nothing), so the step count did not need
  // to grow with it, and the jittered start offset hides the banding a coarse
  // march would otherwise show.
  const int MAX_STEPS = 112;
  const float RULER_A = 18.202857142857143;
  const float RULER_ANCHOR_RE = 6.6170146;
  // CORRECTNESS FIX 2026-09-04: the joint ramp, which this copy of the ruler
  // did not have. See reFromDrawn below.
  const float RULER_RAMP_END_RE = 7.35;
  const float RULER_ANCHOR_SLOPE = 0.1421227773;
  const float TWO_PI = 6.28318530717958647692;

  float logBranchDrawn(float r) {
    return 1.0 + 0.28 * log(1.0 + RULER_A * max(0.0, r - 1.0));
  }

  /**
   * Physical radius from a drawn one, the exact inverse of the scene's shared
   * ruler.
   *
   * CORRECTNESS FIX 2026-09-04. This used to hand back RULER_ANCHOR_RE * x /
   * anchorDrawn above the anchor — straight proportionality, which is the
   * ruler as it stood BEFORE the 2026-08-19 joint ramp. radial-ruler.ts now
   * ramps its log-log slope from the log branch's 0.1422 up to 1 between the
   * geostationary anchor and 7.35 Re, and states the cost of that ramp in its
   * own header: "EVERYTHING above 7.35 Re draws 4.41% closer in". This shader
   * was still reading the old map, so measured against sharedDisplayRadius:
   *
   *     true 7.00 Re  ->  drawn 234.70  ->  this shader read 6.757  (-3.47%)
   *     true 7.35 Re  ->  drawn 244.05  ->  this shader read 7.026  (-4.41%)
   *     true 9.00 Re  ->  drawn 298.84  ->  this shader read 8.603  (-4.41%)
   *
   * Two live consequences, and the second is the visible one. The Alfven layer
   * routinely sits above the anchor — L 7.58 at Kp 3 and L 9.00 at Kp 0 for the
   * 10 keV ion this layer opens on — so everything painted out there was drawn
   * where the shared ruler puts a radius 4.4% larger, i.e. the ring current
   * drew OUTSIDE layers physically at the same L. And the containing mesh is a
   * sphere at sharedDisplayRadius(9), which this shader read as L 8.60, so
   * the supply fade — which exists precisely because "cutting the supply off
   * there drew a clean arc across space, which reads as a rendering wall" —
   * was terminated at 29% brightness on that sphere. The wall was back.
   *
   * The closed form is the one radiation-belt-volume.ts already carries: the
   * ramp's slope is linear in log radius, so the drawn radius is exponential in
   * a quadratic and the inverse is a square root, not a search. Below the
   * anchor nothing changes — GEO, the belts' cores and the plasmasphere were
   * never affected.
   */
  float reFromDrawn(float drawn) {
    float x = drawn / earthSceneRadius;
    if (rulerTrueDistance > 0.5) return max(1.0, x);
    float anchorDrawn = logBranchDrawn(RULER_ANCHOR_RE);
    if (x <= anchorDrawn) return 1.0 + (exp((x - 1.0) / 0.28) - 1.0) / RULER_A;
    float rampLn = log(RULER_RAMP_END_RE / RULER_ANCHOR_RE);
    float rise = 1.0 - RULER_ANCHOR_SLOPE;
    float rampEndDrawn = anchorDrawn * exp(rampLn * (RULER_ANCHOR_SLOPE + rise * 0.5));
    if (x >= rampEndDrawn) return RULER_RAMP_END_RE * x / rampEndDrawn;
    float integral = log(x / anchorDrawn) / rampLn;
    float t = (sqrt(RULER_ANCHOR_SLOPE * RULER_ANCHOR_SLOPE + 2.0 * rise * integral)
      - RULER_ANCHOR_SLOPE) / rise;
    return RULER_ANCHOR_RE * exp(rampLn * t);
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

    // The globe is opaque.
    vec2 earth = sphereIntersect(cameraLocalPosition, direction, earthSceneRadius);
    if (earth.x <= earth.y && earth.y > 0.0 && earth.x < tFar) tFar = max(earth.x, tNear);
    if (tFar - tNear < 1e-4) discard;

    // The storm envelope, once per ray: the whole population dims back toward
    // its quiet-time residual at the end of the loop. A DISPLAY ramp, not a
    // computed loss — no loss is modelled anywhere in this layer.
    float decayStart = fillSeconds + holdSeconds;
    float storm = 1.0 - smoothstep(decayStart, decayStart + decaySeconds, formationSeconds);
    // The supply switches off as the ring closes, which is the part of a storm
    // this steady field cannot draw: injection ends, and what is inside the
    // Alfven layer when it does is what stays.
    float supplyOn = (1.0 - smoothstep(fillSeconds * 0.70, fillSeconds * 0.98, formationSeconds))
      * smoothstep(0.0, frontFeatherSeconds, formationSeconds);
    if (formationEnabled < 0.5) {
      storm = 1.0;
      supplyOn = 0.0;
    }

    float stepLength = (tFar - tNear) / float(MAX_STEPS);
    float offset = hash(gl_FragCoord.xy) * stepLength;
    vec3 accumulated = vec3(0.0);
    float transmittance = 1.0;

    for (int i = 0; i < MAX_STEPS; i += 1) {
      float t = tNear + offset + float(i) * stepLength;
      if (t > tFar) break;
      vec3 samplePosition = cameraLocalPosition + direction * t;
      float drawn = length(samplePosition);
      if (drawn < earthSceneRadius || drawn > sceneRadiusMaximum) continue;

      // Physical space, then dipole coordinates. GSM z is the dipole axis here,
      // the same centred-dipole convention the drift paths are computed in.
      float radiusRe = reFromDrawn(drawn);
      vec3 unit = samplePosition / drawn;
      // The scene frame is NOT GSM: gsmSceneAxes maps (x, y, z) -> (x, z, -y),
      // so the dipole axis is scene Y and GSM y is scene -z. Reading z as the
      // axis drew the torus in the wrong plane entirely - a vertical column
      // hugging the globe instead of a doughnut around its equator.
      float sinLatitude = clamp(unit.y, -1.0, 1.0);
      float latitude = asin(sinLatitude);
      float cosLatitude = max(0.08, cos(latitude));
      // The dipole L shell: the equatorial crossing radius of the field line
      // through this point. A ring-current ion lives on a shell, not at a
      // radius, which is why the volume is fat at the equator and pinched
      // toward the poles rather than being a spherical shell.
      float lShell = radiusRe / (cosLatitude * cosLatitude);
      if (lShell <= innerL) continue;

      // phi from midnight, as a fraction of a full turn. Midnight is 0, dawn
      // 0.25, noon 0.5, dusk 0.75 — the module's own convention.
      float localTime = fract(atan(-unit.z, unit.x) / TWO_PI + 0.5);
      vec4 packed = texture2D(boundary, vec2(localTime, 0.5));
      float outerL = (packed.r * 255.0 + packed.g * 255.0 * 256.0) / 65535.0 * boundaryMaximumL;

      float density = 0.0;
      if (lShell < outerL) {
        // INSIDE the Alfven layer: the trapped population, which is the ring
        // current itself.
        float across = (lShell - innerL) / max(1e-4, outerL - innerL);
        float band = smoothstep(0.0, innerSoftness, across)
          * (1.0 - smoothstep(1.0 - outerSoftness, 1.0, across));
        float offsetFromPeak = (across - radialPeak) / radialCoreWidth;
        float core = exp(-offsetFromPeak * offsetFromPeak);
        float shaped = band * (radialBaseFill + (1.0 - radialBaseFill) * core);
        // Away from the equator: near-equatorially mirroring, so a fat ring.
        float latitudeFall = exp(-(latitude * latitude) / (latitudeHalfWidth * latitudeHalfWidth));
        float here = shaped * latitudeFall;

        // How much of this shell has been filled by the westward drift. Ions
        // go WESTWARD — midnight to dusk to noon to dawn — so the ring closes
        // in that direction and not the other, and each shell closes at its own
        // traced lap time, inner shells first.
        float level = 1.0;
        if (formationEnabled > 0.5) {
          float shellAt = clamp((lShell - shellLMinimum) / shellLSpan, 0.0, 1.0);
          vec4 shell = texture2D(shellMap, vec2(shellAt, 0.5));
          float lap = max(1.0, shell.r * shellLapSpanSeconds);
          float seeded = shell.g * corridorSpanSeconds;
          float swept = TWO_PI * max(0.0, formationSeconds - seeded) / lap;
          // Westward from midnight: 0 at midnight, a quarter turn at DUSK, half
          // at noon, three quarters at dawn. Ions go this way; electrons go the
          // other way; the two do not cancel, they add, and the sum is the
          // westward current whose field at the ground is Dst.
          float westwardAngle = fract(1.0 - localTime) * TWO_PI;
          // The sector around midnight the supply is delivered into is fed from
          // the start; everywhere else waits for the front to arrive from the
          // dusk end of it.
          float fromSource = westwardAngle > (TWO_PI - injectionHalfAngle)
            ? 0.0
            : max(0.0, westwardAngle - injectionHalfAngle);
          float feather = fillFeatherRadians + frontDispersion * swept;
          float arrived = smoothstep(0.0, feather, swept - fromSource);
          level = mix(residualFill, mix(residualFill, 1.0, arrived), storm);
        }
        density = here * level;
      } else if (lShell < corridorLMinimum + corridorLSpan && supplyOn > 0.0) {
        // OUTSIDE it: the supply from the tail, on open drift paths, drawn as
        // the field of arrival times those paths trace out. No line, no marker.
        float row = clamp((lShell - corridorLMinimum) / corridorLSpan, 0.0, 1.0);
        vec4 cell = texture2D(corridorMap, vec2(localTime, row));
        float arrival = cell.r * corridorSpanSeconds;
        float reached = cell.g;
        float front = smoothstep(arrival, arrival + frontFeatherSeconds, formationSeconds);
        float latitudeFall = exp(-(latitude * latitude) / (supplyLatitudeHalfWidth * supplyLatitudeHalfWidth));
        // Faded toward the traced domain edge, so the outer limit of what was
        // computed is a limit rather than a wall.
        float edgeFall = 1.0 - smoothstep(1.0 - supplyOuterFade, 1.0, row);
        density = reached * front * supplyOn * supplyDensity * latitudeFall * edgeFall;
      }
      if (density <= 0.0012) continue;

      // Colour is the ion energy at this L, on the legend's own log ramp.
      float energy = referenceEnergyKeV * pow(referenceL / lShell, 3.0);
      float rampAt = clamp((log2(max(energy, 1e-6)) * 0.30103 - energyLogMinimum) / energyLogSpan, 0.0, 1.0);
      vec3 colour = texture2D(energyRamp, vec2(rampAt, 0.5)).rgb;
      float emission = mix(emissionFloor, emissionCeiling, rampAt);

      float absorbed = 1.0 - exp(-density * extinction * stepLength);
      accumulated += transmittance * absorbed * colour * emission;
      transmittance *= 1.0 - absorbed;
      if (transmittance < minimumTransmittance) break;
    }

    float alpha = 1.0 - max(transmittance, minimumTransmittance);
    if (alpha <= 0.002) discard;
    gl_FragColor = vec4(accumulated, alpha);
  }
`;

export interface RingCurrentVolumeOptions {
  earthSceneRadius: number;
  species: DriftSpecies;
  region: TrappedRegion;
  /**
   * The formation. Absent, the volume draws the fully formed population and
   * stands still, which is what a caller with no illustration to trace from
   * gets.
   */
  formation?: RingCurrentFormation;
}

/**
 * The ray-marched ring current. The mesh is a sphere at the widest drawn
 * radius; everything inside is decided in the shader.
 */
export function createRingCurrentVolumeMesh(options: RingCurrentVolumeOptions): THREE.Mesh {
  const { region, species, earthSceneRadius, formation } = options;
  let widestL = region.innerL;
  for (let index = 0; index < region.outerL.length; index += 1) {
    if (region.outerL[index]! > widestL) widestL = region.outerL[index]!;
  }
  // The sphere has to enclose the SUPPLY as well as the trapped region, or the
  // plasma arriving from the tail would be clipped off at the Alfven layer —
  // which is precisely the part of the picture that shows where it comes from.
  const outermostL = Math.max(widestL, formation?.corridor.lMaximum ?? widestL);
  const sceneRadiusMaximum = sharedDisplayRadius(Math.max(outermostL, region.innerL + 0.1), earthSceneRadius);
  const logMinimum = Math.log10(RING_CURRENT_ENERGY_SCALE.minimumKeV);
  const logMaximum = Math.log10(RING_CURRENT_ENERGY_SCALE.maximumKeV);

  const corridor = formation ? corridorTexture(formation.corridor) : new THREE.DataTexture(new Uint8Array(4), 1, 1, THREE.RGBAFormat);
  const shells = formation ? shellTexture(formation) : new THREE.DataTexture(new Uint8Array(4), 1, 1, THREE.RGBAFormat);
  corridor.needsUpdate = true;
  shells.needsUpdate = true;

  const material = new THREE.ShaderMaterial({
    uniforms: {
      energyRamp: { value: ringCurrentRampTexture() },
      boundary: { value: boundaryTexture(region, Math.max(widestL, 1)) },
      corridorMap: { value: corridor },
      shellMap: { value: shells },
      cameraLocalPosition: { value: new THREE.Vector3() },
      rulerTrueDistance: { value: activeDistanceScale() === "true-distance" ? 1 : 0 },
      earthSceneRadius: { value: earthSceneRadius },
      sceneRadiusMaximum: { value: sceneRadiusMaximum },
      innerL: { value: region.innerL },
      boundaryMaximumL: { value: Math.max(widestL, 1) },
      referenceEnergyKeV: { value: species.referenceEnergyKeV },
      referenceL: { value: species.referenceL },
      energyLogMinimum: { value: logMinimum },
      energyLogSpan: { value: logMaximum - logMinimum },
      radialPeak: { value: RING_CURRENT_VOLUME_PROFILE.radialPeak },
      radialCoreWidth: { value: RING_CURRENT_VOLUME_PROFILE.radialCoreWidth },
      radialBaseFill: { value: RING_CURRENT_VOLUME_PROFILE.radialBaseFill },
      innerSoftness: { value: RING_CURRENT_VOLUME_PROFILE.innerSoftness },
      outerSoftness: { value: RING_CURRENT_VOLUME_PROFILE.outerSoftness },
      latitudeHalfWidth: { value: (RING_CURRENT_VOLUME_PROFILE.latitudeHalfWidthDeg * Math.PI) / 180 },
      supplyLatitudeHalfWidth: { value: (RING_CURRENT_VOLUME_PROFILE.supplyLatitudeHalfWidthDeg * Math.PI) / 180 },
      supplyDensity: { value: RING_CURRENT_VOLUME_PROFILE.supplyDensity },
      supplyOuterFade: { value: RING_CURRENT_VOLUME_PROFILE.supplyOuterFade },
      emissionFloor: { value: RING_CURRENT_VOLUME_PROFILE.emissionAtRampFloor },
      emissionCeiling: { value: RING_CURRENT_VOLUME_PROFILE.emissionAtRampCeiling },
      extinction: { value: RING_CURRENT_VOLUME_PROFILE.extinctionPerSceneUnit },
      minimumTransmittance: { value: 1 - RING_CURRENT_VOLUME_PROFILE.maximumAccumulatedOpacity },
      formationEnabled: { value: formation ? 1 : 0 },
      formationSeconds: { value: 0 },
      fillSeconds: { value: formation?.fillSeconds ?? 1 },
      holdSeconds: { value: formation?.holdSeconds ?? 1 },
      decaySeconds: { value: formation?.decaySeconds ?? 1 },
      cycleSeconds: { value: formation?.cycleSeconds ?? 1 },
      residualFill: { value: RING_CURRENT_FORMATION.residualFill },
      fillFeatherRadians: { value: RING_CURRENT_FORMATION.fillFeatherRadians },
      injectionHalfAngle: {
        value: (RING_CURRENT_FORMATION.injectionHalfWidthMltHours * Math.PI) / 12,
      },
      frontDispersion: { value: RING_CURRENT_FORMATION.frontDispersionPerRadian },
      frontFeatherSeconds: {
        value: (formation?.fillSeconds ?? 1) * RING_CURRENT_FORMATION.frontFeatherFraction,
      },
      corridorLMinimum: { value: formation?.corridor.lMinimum ?? region.innerL },
      corridorLSpan: {
        value: formation ? formation.corridor.lMaximum - formation.corridor.lMinimum : 1,
      },
      corridorSpanSeconds: { value: formation?.corridor.spanSeconds ?? 1 },
      shellLMinimum: { value: formation?.shellLMinimum ?? region.innerL },
      shellLSpan: {
        value: formation ? Math.max(1e-3, formation.shellLMaximum - formation.shellLMinimum) : 1,
      },
      shellLapSpanSeconds: { value: formation?.lapSpanSeconds ?? 1 },
    },
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    side: THREE.BackSide,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.OneFactor,
    blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
  });
  material.addEventListener("dispose", () => {
    (material.uniforms.boundary!.value as THREE.DataTexture).dispose();
    (material.uniforms.corridorMap!.value as THREE.DataTexture).dispose();
    (material.uniforms.shellMap!.value as THREE.DataTexture).dispose();
  });

  const geometry = new THREE.SphereGeometry(sceneRadiusMaximum * 1.002, 48, 32);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = "ring-current-volume";
  mesh.frustumCulled = false;
  mesh.renderOrder = 14;
  mesh.onBeforeRender = (_renderer, _scene, camera) => {
    mesh.updateWorldMatrix(true, false);
    (material.uniforms.cameraLocalPosition!.value as THREE.Vector3)
      .copy(camera.position)
      .applyMatrix4(mesh.matrixWorld.clone().invert());
  };
  mesh.userData = {
    representation: "raymarched drift-bounded ring-current population, filling as the traced drift fills it",
    measured: "nothing on this map; what IS measured about this population is Dst, one number with no map, which is why the shape is reconstructed",
    quantity: "ion kinetic energy",
    unit: "keV",
    profile: RING_CURRENT_VOLUME_PROFILE,
    formation: formation
      ? {
        supplySeeds: formation.corridor.seedCount,
        corridorSpanSeconds: formation.corridor.spanSeconds,
        fillSeconds: formation.fillSeconds,
        cycleSeconds: formation.cycleSeconds,
        replay: RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond,
      }
      : null,
  };
  return mesh;
}

/**
 * Advance the formation to this much display time.
 *
 * The clock handed in is the scene's shared environmental-motion clock, so the
 * formation freezes with every other flow glyph when a visitor turns
 * environmental motion off.
 */
export function setRingCurrentVolumeTime(object: THREE.Object3D, elapsedDisplaySeconds: number): void {
  const material = (object as THREE.Mesh).material as THREE.ShaderMaterial | undefined;
  const uniforms = material?.uniforms;
  if (!uniforms?.formationSeconds || !uniforms.cycleSeconds) return;
  const cycle = uniforms.cycleSeconds.value as number;
  if (!(cycle > 0)) return;
  const physical = elapsedDisplaySeconds * RING_CURRENT_FORMATION.physicalSecondsPerDisplaySecond;
  uniforms.formationSeconds.value = ((physical % cycle) + cycle) % cycle;
}

/** The energy at the region's two edges, for the card to quote. */
export function ringCurrentEdgeEnergies(region: TrappedRegion, species: DriftSpecies) {
  let widestL = region.innerL;
  for (let index = 0; index < region.outerL.length; index += 1) {
    if (region.outerL[index]! > widestL) widestL = region.outerL[index]!;
  }
  return {
    innerKeV: energyAtLKeV(species, region.innerL),
    outerKeV: energyAtLKeV(species, widestL),
    innerRampPosition: energyRampPosition(energyAtLKeV(species, region.innerL)),
  };
}
