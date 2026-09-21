import * as THREE from "three";

import { RULER_EARTH_RADIUS_KM, sharedDisplayRadius } from "./radial-ruler";

/**
 * Lightweight empirical D-region view. The effective reflection height it
 * reports spans 53–84 km: 84 km at night, 70 km in quiet daylight, and down
 * to 53 km at the X45 top of the published flare domain. (It said "60–85 km"
 * until 2026-09-08, which is neither end of what the equations below can
 * return, and the ionosphere ladder had been clamped to that wrong floor.)
 *
 * This is deliberately separate from WAM-IPE.  WAM-IPE's public ipe10 grid
 * begins at 90 km, while the equations below describe the lower ionosphere.
 * It is not valid to linearly extend WAM-IPE below its lower boundary.
 */
export const D_REGION_EMPIRICAL_METHOD = {
  title: "Empirical D-region effective height and electron density",
  evidence: "empirical" as const,
  model: "Wait–Spies profile with Schmitter/Thomson flare response",
  equations: {
    electronDensity:
      "Ne(h)=1.43×10^13 exp(-0.15 h′) exp[(β-0.15)(h-h′)] m^-3",
    quietDiurnal:
      "h′ and β interpolate between published day (70 km, 0.34 km^-1) and night (84 km, 0.63 km^-1) values using cos(SZA×90/94) on the illuminated side",
    flareHeight:
      "dayside h′ lowering is log-linear in GOES 0.1–0.8 nm irradiance over the published C1–X45 observational domain",
    flareSharpness:
      "β=βd+(βmax-βd)[1-exp(-Δh′/6.67 km)], βmax=0.55 km^-1",
  },
  sources: [
    {
      citation: "Wait and Spies (1964), NBS Technical Note 300",
      doi: "https://doi.org/10.6028/NBS.TN.300",
    },
    {
      citation: "Schmitter (2013), Annales Geophysicae 31, 765–773",
      doi: "https://doi.org/10.5194/angeo-31-765-2013",
    },
    {
      citation: "Thomson et al. (2005), JGR Space Physics 110, A06306",
      doi: "https://doi.org/10.1029/2005JA011008",
    },
  ],
  limitations: [
    "h′ is an effective VLF reflection height, not a hard physical top or bottom of the D region.",
    "The flare-height relation is constrained by daylight VLF paths and GOES 0.1–0.8 nm flux from about C1 through X45; it is not a global chemistry-model analysis.",
    "GOES long-channel irradiance alone does not determine the flare spectrum. SEP, auroral-electron, latitude-dependent cosmic-ray, composition, and transport effects are not estimated here.",
    "Published path-to-path variability is structural uncertainty; this view does not claim a pointwise confidence interval.",
  ],
} as const;

const DAY_HEIGHT_KM = 70;
const NIGHT_HEIGHT_KM = 84;
const DAY_BETA_PER_KM = 0.34;
const NIGHT_BETA_PER_KM = 0.63;
const BETA_MAX_PER_KM = 0.55;
const WAIT_SCALE_HEIGHT_KM = 1 / 0.15;
const WAIT_DENSITY_NORMALIZATION_M3 = 1.43e13;
const FLARE_BASELINE_W_M2 = 1e-6; // C1: lower edge of the Thomson et al. fit domain.
const FLARE_UPPER_W_M2 = 4.5e-3; // X45 peak reported by Thomson et al. (2005).
const FLARE_HEIGHT_DROP_AT_UPPER_KM = 17; // Published lowering from ~70 km to ~53 km at X45.
const FLARE_KM_PER_DECADE = FLARE_HEIGHT_DROP_AT_UPPER_KM
  / Math.log10(FLARE_UPPER_W_M2 / FLARE_BASELINE_W_M2);

export interface GeographicPoint {
  latitudeDeg: number;
  longitudeDeg: number;
}

export interface DRegionSample {
  latitudeDeg: number;
  longitudeDeg: number;
  solarZenithDeg: number;
  illumination: number;
  effectiveHeightKm: number;
  betaPerKm: number;
  electronDensityAt74KmM3: number;
  flareHeightLoweringKm: number;
  xrayFluxWm2: number | null;
  fluxDomain: "missing" | "below-validated" | "validated" | "above-validated";
  evidence: "empirical";
}

export interface DRegionSurfaceState {
  validAt: string;
  xrayFluxWm2: number | null;
  effectiveHeightRangeKm: [number, number];
  densityAt74KmRangeM3: [number, number];
  fluxDomain: DRegionSample["fluxDomain"];
  evidence: "empirical";
  limitation: string;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function normalizeLongitude(longitudeDeg: number) {
  return ((longitudeDeg + 180) % 360 + 360) % 360 - 180;
}

/** Compact solar-coordinate calculation suitable for the interactive timeline. */
export function dRegionSubsolarPoint(date: Date): GeographicPoint {
  const timestamp = date.getTime();
  if (!Number.isFinite(timestamp)) throw new RangeError("D-region simulation time must be valid");
  const julianDate = timestamp / 86_400_000 + 2_440_587.5;
  const daysSinceJ2000 = julianDate - 2_451_545;
  const normalize = (degrees: number) => ((degrees % 360) + 360) % 360;
  const meanLongitude = normalize(280.46 + 0.9856474 * daysSinceJ2000);
  const meanAnomaly = THREE.MathUtils.degToRad(normalize(357.528 + 0.9856003 * daysSinceJ2000));
  const eclipticLongitude = THREE.MathUtils.degToRad(normalize(
    meanLongitude + 1.915 * Math.sin(meanAnomaly) + 0.02 * Math.sin(2 * meanAnomaly),
  ));
  const obliquity = THREE.MathUtils.degToRad(23.439 - 0.0000004 * daysSinceJ2000);
  const rightAscension = Math.atan2(
    Math.cos(obliquity) * Math.sin(eclipticLongitude),
    Math.cos(eclipticLongitude),
  );
  const declination = Math.asin(Math.sin(obliquity) * Math.sin(eclipticLongitude));
  const greenwichSiderealDeg = normalize(280.46061837 + 360.98564736629 * daysSinceJ2000);
  return {
    latitudeDeg: THREE.MathUtils.radToDeg(declination),
    longitudeDeg: normalizeLongitude(THREE.MathUtils.radToDeg(rightAscension) - greenwichSiderealDeg),
  };
}

export function solarZenithAngleDeg(point: GeographicPoint, subsolar: GeographicPoint) {
  const latitude = THREE.MathUtils.degToRad(point.latitudeDeg);
  const subsolarLatitude = THREE.MathUtils.degToRad(subsolar.latitudeDeg);
  const longitudeDifference = THREE.MathUtils.degToRad(
    normalizeLongitude(point.longitudeDeg - subsolar.longitudeDeg),
  );
  const cosine = Math.sin(latitude) * Math.sin(subsolarLatitude)
    + Math.cos(latitude) * Math.cos(subsolarLatitude) * Math.cos(longitudeDifference);
  return THREE.MathUtils.radToDeg(Math.acos(clamp(cosine, -1, 1)));
}

/**
 * Schmitter's 94° illumination limit accounts for sunlight reaching the
 * approximately 70 km reflection region beyond the ground terminator.
 */
export function dRegionIllumination(solarZenithDeg: number) {
  if (!Number.isFinite(solarZenithDeg)) throw new RangeError("Solar zenith angle must be finite");
  if (solarZenithDeg >= 94) return 0;
  return clamp(Math.cos(THREE.MathUtils.degToRad(solarZenithDeg * 90 / 94)), 0, 1);
}

export function waitSpiesElectronDensityM3(altitudeKm: number, effectiveHeightKm: number, betaPerKm: number) {
  if (![altitudeKm, effectiveHeightKm, betaPerKm].every(Number.isFinite)) {
    throw new RangeError("Wait–Spies inputs must be finite");
  }
  return WAIT_DENSITY_NORMALIZATION_M3
    * Math.exp(-0.15 * effectiveHeightKm)
    * Math.exp((betaPerKm - 0.15) * (altitudeKm - effectiveHeightKm));
}

export function dRegionFluxDomain(xrayFluxWm2: number | null): DRegionSample["fluxDomain"] {
  if (xrayFluxWm2 === null || !Number.isFinite(xrayFluxWm2) || xrayFluxWm2 <= 0) return "missing";
  if (xrayFluxWm2 < FLARE_BASELINE_W_M2) return "below-validated";
  if (xrayFluxWm2 > FLARE_UPPER_W_M2) return "above-validated";
  return "validated";
}

/**
 * Observationally constrained daylight height response.  The coefficient is
 * not a free visual constant: it is the log-linear slope implied by Thomson
 * et al.'s published endpoints (70 km at C1/background; 53 km at X45).
 */
export function flareHeightLoweringKm(xrayFluxWm2: number | null) {
  if (xrayFluxWm2 === null || !Number.isFinite(xrayFluxWm2) || xrayFluxWm2 <= FLARE_BASELINE_W_M2) return 0;
  const constrainedFlux = clamp(xrayFluxWm2, FLARE_BASELINE_W_M2, FLARE_UPPER_W_M2);
  return FLARE_KM_PER_DECADE * Math.log10(constrainedFlux / FLARE_BASELINE_W_M2);
}

export function sampleEmpiricalDRegion(
  latitudeDeg: number,
  longitudeDeg: number,
  at: Date,
  xrayFluxWm2: number | null,
  subsolar = dRegionSubsolarPoint(at),
): DRegionSample {
  const solarZenithDeg = solarZenithAngleDeg({ latitudeDeg, longitudeDeg }, subsolar);
  const illumination = dRegionIllumination(solarZenithDeg);
  const quietHeightKm = THREE.MathUtils.lerp(NIGHT_HEIGHT_KM, DAY_HEIGHT_KM, illumination);
  const quietBeta = THREE.MathUtils.lerp(NIGHT_BETA_PER_KM, DAY_BETA_PER_KM, illumination);
  const daylightLoweringKm = flareHeightLoweringKm(xrayFluxWm2);
  const localLoweringKm = daylightLoweringKm * illumination;
  const effectiveHeightKm = quietHeightKm - localLoweringKm;
  // Schmitter Eq. 11, limited to the illuminated fraction where flare X-rays act.
  const flareSharpnessIncrease = illumination * (BETA_MAX_PER_KM - DAY_BETA_PER_KM)
    * (1 - Math.exp(-daylightLoweringKm / WAIT_SCALE_HEIGHT_KM));
  const betaPerKm = quietBeta + flareSharpnessIncrease;
  return {
    latitudeDeg,
    longitudeDeg,
    solarZenithDeg,
    illumination,
    effectiveHeightKm,
    betaPerKm,
    electronDensityAt74KmM3: waitSpiesElectronDensityM3(74, effectiveHeightKm, betaPerKm),
    flareHeightLoweringKm: localLoweringKm,
    xrayFluxWm2,
    fluxDomain: dRegionFluxDomain(xrayFluxWm2),
    evidence: "empirical",
  };
}

/**
 * Scene radius for the empirical D-region surface, on the scene's shared ruler.
 *
 * CORRECTNESS FIX 2026-09-04. The teaching branch used to be a private curve,
 * `earthSceneRadius + 2.6 + (altitudeKm - 60) * 0.09`, documented as an
 * "Exaggerated scene radius". It exaggerated nothing — it DEPRESSED the layer
 * relative to the ruler every other near-Earth consumer is drawn on:
 *
 *      h'      private curve      shared ruler     private curve reads as
 *     53 km       101.97             103.95              25.5 km
 *     70 km       103.50             105.11              46.6 km
 *     84 km       104.76             106.02              64.9 km
 *
 * — so the daytime 70 km reflection height was drawn where the ruler puts
 * 47 km, and the band was 1.35x too thick on top of that (0.09 scene units per
 * km against the ruler's 0.067 at these heights). Its own docstring made the
 * argument against itself: "a private exaggeration would put the absorbing
 * layer above satellites that physically fly over it". A private DEPRESSION
 * puts it below layers it physically sits inside, which is the same defect
 * with the sign flipped.
 *
 * This mesh is a fallback — `globe.ts` draws it only when the density volume is
 * absent — but it is live code on that path, and `rebuildRadialGeometry`
 * re-runs it on every scale switch.
 *
 * Legends and samples always report physical km, on either scale.
 */
export function dRegionDisplayRadius(altitudeKm: number, earthSceneRadius = 100) {
  return sharedDisplayRadius(1 + Math.max(0, altitudeKm) / RULER_EARTH_RADIUS_KM, earthSceneRadius);
}

function densityColor(logDensity: number) {
  const amount = clamp((logDensity - 6) / 5, 0, 1);
  const low = new THREE.Color(0x172a55);
  const middle = new THREE.Color(0x20c6dc);
  const high = new THREE.Color(0xffb85c);
  return amount < 0.58
    ? low.lerp(middle, amount / 0.58)
    : middle.lerp(high, (amount - 0.58) / 0.42);
}

export class EmpiricalDRegionLayer {
  readonly mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  private readonly latSegments: number;
  private readonly lonSegments: number;
  private readonly earthSceneRadius: number;
  private simulationTime = new Date();
  private xrayFluxWm2: number | null = null;
  private stateValue: DRegionSurfaceState;

  constructor(earthSceneRadius = 100, lonSegments = 72, latSegments = 36) {
    this.earthSceneRadius = earthSceneRadius;
    this.lonSegments = lonSegments;
    this.latSegments = latSegments;
    const vertexCount = (lonSegments + 1) * (latSegments + 1);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(vertexCount * 3), 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(vertexCount * 3), 3));
    const indices: number[] = [];
    for (let row = 0; row < latSegments; row += 1) {
      for (let column = 0; column < lonSegments; column += 1) {
        const a = row * (lonSegments + 1) + column;
        const b = a + lonSegments + 1;
        indices.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
    geometry.setIndex(indices);
    geometry.userData.kind = "empirical-d-region-effective-height-surface";
    geometry.userData.method = D_REGION_EMPIRICAL_METHOD;
    const material = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.14,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.NormalBlending,
    });
    this.mesh = new THREE.Mesh(geometry, material);
    this.mesh.name = "empirical-d-region-smooth-surface";
    this.mesh.renderOrder = 4;
    this.stateValue = {
      validAt: this.simulationTime.toISOString(),
      xrayFluxWm2: null,
      effectiveHeightRangeKm: [DAY_HEIGHT_KM, NIGHT_HEIGHT_KM],
      densityAt74KmRangeM3: [0, 0],
      fluxDomain: "missing",
      evidence: "empirical",
      limitation: D_REGION_EMPIRICAL_METHOD.limitations[0],
    };
    this.updateSurface();
  }

  setSimulationTime(date: Date) {
    if (!Number.isFinite(date.getTime())) throw new RangeError("D-region simulation time must be valid");
    this.simulationTime = new Date(date);
    this.updateSurface();
  }

  setXrayFlux(fluxWm2: number | null) {
    this.xrayFluxWm2 = fluxWm2 !== null && Number.isFinite(fluxWm2) && fluxWm2 > 0 ? fluxWm2 : null;
    this.updateSurface();
  }

  getState() {
    return this.stateValue;
  }

  private updateSurface() {
    const positions = this.mesh.geometry.getAttribute("position") as THREE.BufferAttribute;
    const colors = this.mesh.geometry.getAttribute("color") as THREE.BufferAttribute;
    const subsolar = dRegionSubsolarPoint(this.simulationTime);
    let minimumHeight = Number.POSITIVE_INFINITY;
    let maximumHeight = Number.NEGATIVE_INFINITY;
    let minimumDensity = Number.POSITIVE_INFINITY;
    let maximumDensity = Number.NEGATIVE_INFINITY;
    let index = 0;
    for (let row = 0; row <= this.latSegments; row += 1) {
      const latitudeDeg = -90 + row * 180 / this.latSegments;
      const latitude = THREE.MathUtils.degToRad(latitudeDeg);
      for (let column = 0; column <= this.lonSegments; column += 1) {
        const longitudeDeg = -180 + column * 360 / this.lonSegments;
        const longitude = THREE.MathUtils.degToRad(longitudeDeg);
        const sample = sampleEmpiricalDRegion(
          latitudeDeg,
          longitudeDeg,
          this.simulationTime,
          this.xrayFluxWm2,
          subsolar,
        );
        const radius = dRegionDisplayRadius(sample.effectiveHeightKm, this.earthSceneRadius);
        const horizontal = radius * Math.cos(latitude);
        positions.setXYZ(
          index,
          horizontal * Math.cos(longitude),
          radius * Math.sin(latitude),
          -horizontal * Math.sin(longitude),
        );
        const color = densityColor(Math.log10(Math.max(1, sample.electronDensityAt74KmM3)));
        colors.setXYZ(index, color.r, color.g, color.b);
        minimumHeight = Math.min(minimumHeight, sample.effectiveHeightKm);
        maximumHeight = Math.max(maximumHeight, sample.effectiveHeightKm);
        minimumDensity = Math.min(minimumDensity, sample.electronDensityAt74KmM3);
        maximumDensity = Math.max(maximumDensity, sample.electronDensityAt74KmM3);
        index += 1;
      }
    }
    positions.needsUpdate = true;
    colors.needsUpdate = true;
    this.mesh.geometry.computeVertexNormals();
    this.mesh.geometry.computeBoundingSphere();
    this.stateValue = {
      validAt: this.simulationTime.toISOString(),
      xrayFluxWm2: this.xrayFluxWm2,
      effectiveHeightRangeKm: [minimumHeight, maximumHeight],
      densityAt74KmRangeM3: [minimumDensity, maximumDensity],
      fluxDomain: dRegionFluxDomain(this.xrayFluxWm2),
      evidence: "empirical",
      limitation: D_REGION_EMPIRICAL_METHOD.limitations[0],
    };
    this.mesh.userData.dRegionState = this.stateValue;
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
  }
}
