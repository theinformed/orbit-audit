/**
 * The station overlay has to put antennas on the right part of the world.
 *
 * This project has produced the same defect more than once: a layer drawn a
 * quarter-turn away from the geometry laid over it, passing every numerical
 * test, invisible on screen because the graticule is unlabelled. So these
 * assertions are about geography, not arithmetic. They ask where a station
 * comes out on real Natural Earth coastlines after going through the globe's
 * own transform, and they check that reintroducing the defect breaks them.
 *
 * Three independent things are pinned:
 *
 * 1. **The transform round-trips through the scene.** A station's scene vector,
 *    read back with the globe's own inverse, is the station again.
 * 2. **The result is on land.** Every real antenna is on land, and the vendored
 *    1:110m coastlines say so — with a short, named list of island and coastal
 *    sites where 110m simplification genuinely cannot decide.
 * 3. **The coordinates themselves are not transposed or sign-flipped.** Each
 *    checked station is a stated distance from an independent landmark. A
 *    longitude sign error on Goldstone puts it in China, which is also land;
 *    only the landmark check catches that.
 *
 * And then the negative control: apply the quarter-turn that shipped, and the
 * answers must change. A test that cannot fail is not a guard.
 */
import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  azimuthDifferenceDegrees,
  equirectangularLayerAzimuth,
  sceneAzimuthDegrees,
} from "../src/globe";
import { worldOutlines } from "../src/data/world-outlines";
import {
  STATION_SCENE_RADIUS,
  centralAngleRad,
  stationScenePosition,
} from "../src/ground-stations";
import { EARTH_RADIUS_KM } from "../src/orbit";
import table from "../data/ground_stations.json";
import { MINIMUM_PROBE_MARGIN_KM, RENDER_PROBE_SITES } from "./ground-station-probe-sites";

interface TableStation {
  id: string;
  name: string;
  latitudeDeg: number;
  longitudeDeg: number;
  coordinatePrecision: string;
}

const stations = (table as { stations: TableStation[] }).stations;

/** Even-odd ray casting over every land ring, as in world-outlines.test.ts. */
function onLand(longitudeDeg: number, latitudeDeg: number): boolean {
  let inside = false;
  for (const ring of worldOutlines().land) {
    for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index, index += 1) {
      const [xi, yi] = ring[index]!;
      const [xj, yj] = ring[previous]!;
      if ((yi > latitudeDeg) !== (yj > latitudeDeg)
        && longitudeDeg < ((xj - xi) * (latitudeDeg - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
  }
  return inside;
}

function wrapLongitude(longitudeDeg: number) {
  return ((longitudeDeg + 180) % 360 + 360) % 360 - 180;
}

/**
 * Where the globe actually draws a scene position, read back the way the
 * globe's own picking and footprint code reads it back: azimuth from the
 * scene axes, latitude from the vertical component.
 */
function geographyOf(position: THREE.Vector3) {
  const radius = position.length();
  return {
    latitudeDeg: (Math.asin(THREE.MathUtils.clamp(position.y / radius, -1, 1)) * 180) / Math.PI,
    longitudeDeg: sceneAzimuthDegrees(position),
  };
}

/**
 * Sites where the 1:110m coastline is genuinely too coarse to answer "is this
 * on land" — small islands and points within a cell of the shore. They are
 * still checked against their landmarks and still checked for the quarter-turn.
 * This list is short and named on purpose: it is an exemption from one
 * assertion, not a way to stop testing a station.
 */
const COASTLINE_TOO_COARSE_FOR_110M = new Set<string>([
  "nasa-nsn-mcmurdo",        // Ross Island
  "esa-maspalomas",          // Gran Canaria
  "esa-malindi",             // on the Kenyan shore
  "esa-estrack-santa-maria", // Azores
  // Added 2026-08-08 with the second batch of stations. Every one of these was
  // flagged by this test rather than waved through: the coastline check is what
  // found them, and each was then measured against a landmark before being
  // exempted. One station in the same batch — a Leaf Line marker labelled Jeju
  // that plots 43 km off the north coast of the island it names — failed that
  // second check and was dropped from the table instead of exempted.
  "jaxa-uchinoura-34m",      // Osumi peninsula, on the Pacific shore
  "jaxa-uchinoura-20m",      // the same headland
  "ssc-punta-arenas",        // Strait of Magellan
  "leaf-punta-arenas",       // Strait of Magellan
  "leaf-longwood",           // Saint Helena, an island 110m drops entirely
  "leaf-mon-loisir",         // Mauritius
  "leaf-shetland",           // Unst, the northernmost Shetland island
]);

/**
 * Independent landmarks, with a generous bound. These are ordinary geographic
 * facts a reader could check on any map, and their job is to catch a
 * transposed or sign-flipped coordinate in the table — a failure mode that
 * lands the station on some other continent, which is still land.
 */
const LANDMARKS: Array<{
  stationId: string;
  landmark: string;
  latitudeDeg: number;
  longitudeDeg: number;
  withinKm: number;
}> = [
  { stationId: "nasa-dsn-goldstone-dss14", landmark: "Los Angeles", latitudeDeg: 34.05, longitudeDeg: -118.24, withinKm: 300 },
  { stationId: "nasa-dsn-madrid-dss63", landmark: "Madrid", latitudeDeg: 40.42, longitudeDeg: -3.70, withinKm: 120 },
  { stationId: "nasa-dsn-canberra-dss43", landmark: "Canberra", latitudeDeg: -35.28, longitudeDeg: 149.13, withinKm: 120 },
  { stationId: "ksat-svalsat", landmark: "Longyearbyen", latitudeDeg: 78.22, longitudeDeg: 15.63, withinKm: 60 },
  { stationId: "noaa-wallops-cda", landmark: "Norfolk, Virginia", latitudeDeg: 36.85, longitudeDeg: -76.29, withinKm: 200 },
  { stationId: "noaa-fairbanks-cda", landmark: "Fairbanks, Alaska", latitudeDeg: 64.84, longitudeDeg: -147.72, withinKm: 100 },
  { stationId: "esa-estrack-kourou", landmark: "Cayenne", latitudeDeg: 4.93, longitudeDeg: -52.33, withinKm: 100 },
  { stationId: "esa-estrack-new-norcia", landmark: "Perth", latitudeDeg: -31.95, longitudeDeg: 115.86, withinKm: 150 },
  { stationId: "esa-estrack-cebreros", landmark: "Madrid", latitudeDeg: 40.42, longitudeDeg: -3.70, withinKm: 120 },
  { stationId: "usgs-eros-sioux-falls", landmark: "Sioux Falls", latitudeDeg: 43.55, longitudeDeg: -96.70, withinKm: 60 },
  { stationId: "sansa-hartebeesthoek", landmark: "Johannesburg", latitudeDeg: -26.20, longitudeDeg: 28.05, withinKm: 100 },
  // The four sites the 1:110m coastline cannot adjudicate.
  { stationId: "nasa-nsn-mcmurdo", landmark: "McMurdo Station", latitudeDeg: -77.846, longitudeDeg: 166.669, withinKm: 25 },
  { stationId: "esa-maspalomas", landmark: "Maspalomas, Gran Canaria", latitudeDeg: 27.76, longitudeDeg: -15.58, withinKm: 40 },
  { stationId: "esa-malindi", landmark: "Malindi", latitudeDeg: -3.219, longitudeDeg: 40.117, withinKm: 50 },
  { stationId: "esa-estrack-santa-maria", landmark: "Vila do Porto, Azores", latitudeDeg: 36.94, longitudeDeg: -25.14, withinKm: 30 },
  // The seven exempted by the second batch, plus one inland check per new
  // network so no operator's whole haul rests on the coastline test alone.
  { stationId: "jaxa-uchinoura-34m", landmark: "Kanoya, Kagoshima", latitudeDeg: 31.3833, longitudeDeg: 130.8517, withinKm: 40 },
  { stationId: "jaxa-uchinoura-20m", landmark: "Kanoya, Kagoshima", latitudeDeg: 31.3833, longitudeDeg: 130.8517, withinKm: 40 },
  { stationId: "ssc-punta-arenas", landmark: "Punta Arenas", latitudeDeg: -53.1638, longitudeDeg: -70.9171, withinKm: 40 },
  { stationId: "leaf-punta-arenas", landmark: "Punta Arenas", latitudeDeg: -53.1638, longitudeDeg: -70.9171, withinKm: 40 },
  { stationId: "leaf-longwood", landmark: "Jamestown, Saint Helena", latitudeDeg: -15.9276, longitudeDeg: -5.7168, withinKm: 20 },
  { stationId: "leaf-mon-loisir", landmark: "Port Louis, Mauritius", latitudeDeg: -20.1619, longitudeDeg: 57.4989, withinKm: 40 },
  { stationId: "leaf-shetland", landmark: "Lerwick, Shetland", latitudeDeg: 60.1546, longitudeDeg: -1.1494, withinKm: 90 },
  // The two JAXA deep-space antennas the whole second pass turned on.
  { stationId: "jaxa-usuda-64m", landmark: "Nagano", latitudeDeg: 36.6486, longitudeDeg: 138.1948, withinKm: 70 },
  { stationId: "jaxa-misasa-54m", landmark: "Nagano", latitudeDeg: 36.6486, longitudeDeg: 138.1948, withinKm: 70 },
  // One per commercial network, chosen inland so a whole-network sign error
  // cannot hide behind an island exemption.
  { stationId: "viasat-rte-pendergrass", landmark: "Atlanta, Georgia", latitudeDeg: 33.749, longitudeDeg: -84.388, withinKm: 100 },
  { stationId: "ssc-clewiston", landmark: "West Palm Beach, Florida", latitudeDeg: 26.7153, longitudeDeg: -80.0534, withinKm: 120 },
  { stationId: "telespazio-fucino", landmark: "Rome", latitudeDeg: 41.9028, longitudeDeg: 12.4964, withinKm: 120 },
  { stationId: "leaf-plana", landmark: "Sofia", latitudeDeg: 42.6977, longitudeDeg: 23.3219, withinKm: 40 },
];

function separationKm(
  aLatitude: number,
  aLongitude: number,
  bLatitude: number,
  bLongitude: number,
) {
  return centralAngleRad(aLatitude, aLongitude, bLatitude, bLongitude) * EARTH_RADIUS_KM;
}

/** Distance to the nearest vertex of any land ring, in kilometres. */
function nearestCoastKm(longitudeDeg: number, latitudeDeg: number): number {
  let best = Infinity;
  const cosLatitude = Math.cos((latitudeDeg * Math.PI) / 180);
  for (const ring of worldOutlines().land) {
    for (const [longitude, latitude] of ring) {
      const deltaLatitude = ((latitude - latitudeDeg) * Math.PI) / 180;
      const deltaLongitude = ((((longitude - longitudeDeg + 540) % 360) - 180) * Math.PI / 180) * cosLatitude;
      const distance = Math.hypot(deltaLatitude, deltaLongitude) * EARTH_RADIUS_KM;
      if (distance < best) best = distance;
    }
  }
  return best;
}

describe("ground-station overlay geography", () => {
  it("has a table worth testing", () => {
    expect(stations.length).toBeGreaterThan(20);
  });

  it("round-trips every station through the globe's own scene transform", () => {
    for (const station of stations) {
      const recovered = geographyOf(stationScenePosition(station));
      expect(recovered.latitudeDeg, station.id).toBeCloseTo(station.latitudeDeg, 9);
      expect(
        Math.abs(azimuthDifferenceDegrees(recovered.longitudeDeg, station.longitudeDeg)),
        station.id,
      ).toBeLessThan(1e-9);
      expect(stationScenePosition(station).length()).toBeCloseTo(STATION_SCENE_RADIUS, 9);
    }
  });

  it("draws every pin over land, on real Natural Earth coastlines", () => {
    const ashore: string[] = [];
    for (const station of stations) {
      if (COASTLINE_TOO_COARSE_FOR_110M.has(station.id)) continue;
      const { latitudeDeg, longitudeDeg } = geographyOf(stationScenePosition(station));
      if (!onLand(longitudeDeg, latitudeDeg)) ashore.push(`${station.id} (${station.name})`);
    }
    expect(ashore, "these pins came out in open water").toEqual([]);
  });

  it("pins every exempted island station to a landmark instead", () => {
    // The exemption is from the coastline test, not from being checked. An
    // island small enough that 1:110m drops it entirely is also an island whose
    // nearest modelled coast is a thousand kilometres away, so proximity to a
    // ring is no guard at all. A named landmark is.
    for (const station of stations) {
      if (!COASTLINE_TOO_COARSE_FOR_110M.has(station.id)) continue;
      expect(
        LANDMARKS.some((check) => check.stationId === station.id),
        `${station.id} is exempt from the coastline test and has no landmark either`,
      ).toBe(true);
    }
  });

  it("places each checked station the right distance from an independent landmark", () => {
    for (const check of LANDMARKS) {
      const station = stations.find((candidate) => candidate.id === check.stationId);
      expect(station, `${check.stationId} is not in the table`).toBeTruthy();
      const { latitudeDeg, longitudeDeg } = geographyOf(stationScenePosition(station!));
      const distance = separationKm(latitudeDeg, longitudeDeg, check.latitudeDeg, check.longitudeDeg);
      expect(
        distance,
        `${check.stationId} came out ${Math.round(distance)} km from ${check.landmark}`,
      ).toBeLessThan(check.withinKm);
    }
  });

  it("agrees with the map raster the pins are drawn over", () => {
    // The Earth's map is an equirectangular texture on a 96x64 sphere. Where
    // that texture draws a station's longitude must be where the pin is, to
    // within half a vertex spacing (360/96 = 3.75 degrees).
    const earth = new THREE.Mesh(
      new THREE.SphereGeometry(100, 96, 64),
      new THREE.MeshBasicMaterial(),
    );
    for (const station of stations) {
      const pinAzimuth = sceneAzimuthDegrees(stationScenePosition(station));
      const { azimuthDeg } = equirectangularLayerAzimuth(earth, station.longitudeDeg);
      expect(
        Math.abs(azimuthDifferenceDegrees(azimuthDeg, pinAzimuth)),
        `${station.id}: the map column and the pin are in different places`,
      ).toBeLessThan(360 / 96 / 2 + 1e-9);
    }
  });

  describe("the quarter-turn that shipped, as a negative control", () => {
    /**
     * The defect: the Earth mesh carried `rotation.y = -PI/2` while pins are
     * vector geometry. The map's longitude L is then drawn at azimuth L - 90,
     * so a pin at azimuth A sits over map longitude A + 90.
     */
    const underDefect = (station: TableStation) => {
      const azimuth = sceneAzimuthDegrees(stationScenePosition(station));
      return wrapLongitude(azimuth + 90);
    };

    it("reproduces the defect's own signature exactly", () => {
      const earth = new THREE.Mesh(
        new THREE.SphereGeometry(100, 96, 64),
        new THREE.MeshBasicMaterial(),
      );
      earth.rotation.y = -Math.PI / 2;
      // Longitudes that fall exactly on a vertex of the 96-segment sphere, so
      // the measurement's own quantisation does not blur the signature.
      for (const longitudeDeg of [-180, -135, -90, -45, 0, 45, 90, 135]) {
        const { azimuthDeg } = equirectangularLayerAzimuth(earth, longitudeDeg);
        expect(azimuthDifferenceDegrees(azimuthDeg, longitudeDeg)).toBeCloseTo(-90, 6);
      }
    });

    it("would wash a large share of the network out to sea", () => {
      const drowned = stations.filter((station) => {
        const { latitudeDeg } = geographyOf(stationScenePosition(station));
        return !onLand(underDefect(station), latitudeDeg);
      });
      // Enough that the picture is obviously wrong once you know to look, and
      // few enough that it hid for months when nobody did.
      expect(drowned.length / stations.length).toBeGreaterThan(0.25);
    });

    it("moves these specific antennas into open ocean", () => {
      const mustDrown = [
        "nasa-dsn-goldstone-dss14",
        "nasa-dsn-canberra-dss43",
        "ksat-svalsat",
        "noaa-fairbanks-cda",
        "esa-estrack-new-norcia",
        "ssc-dongara",
      ];
      for (const id of mustDrown) {
        const station = stations.find((candidate) => candidate.id === id);
        expect(station, `${id} is not in the table`).toBeTruthy();
        const { latitudeDeg } = geographyOf(stationScenePosition(station!));
        expect(onLand(underDefect(station!), latitudeDeg), `${id} stayed on land under the defect`).toBe(false);
      }
    });

    it("fails the landmark check too, so neither guard stands alone", () => {
      const goldstone = stations.find((station) => station.id === "nasa-dsn-goldstone-dss14")!;
      const { latitudeDeg } = geographyOf(stationScenePosition(goldstone));
      const distance = separationKm(latitudeDeg, underDefect(goldstone), 34.05, -118.24);
      expect(distance).toBeGreaterThan(1000);
    });

    /**
     * The exemption list is the one place this suite stops asking a station
     * "are you on land". That makes it the obvious place for a bad coordinate
     * to hide, so the replacement guard has to be shown to work: every station
     * excused from the coastline test must have a landmark, and that landmark
     * check must itself break under the quarter-turn. If it did not, the
     * exemption would be an escape hatch rather than a substitution.
     */
    it("breaks the landmark check for every station excused from the coastline test", () => {
      const excused = stations.filter((station) => COASTLINE_TOO_COARSE_FOR_110M.has(station.id));
      expect(excused.length, "the exemption list has drifted away from the table").toBeGreaterThan(9);
      for (const station of excused) {
        const check = LANDMARKS.find((candidate) => candidate.stationId === station.id);
        expect(check, `${station.id} is excused from the coastline test with no landmark`).toBeTruthy();
        const { latitudeDeg } = geographyOf(stationScenePosition(station));
        const distance = separationKm(
          latitudeDeg,
          underDefect(station),
          check!.latitudeDeg,
          check!.longitudeDeg,
        );
        expect(
          distance,
          `${station.id} stayed within ${check!.withinKm} km of ${check!.landmark} under the defect, `
          + "so its landmark check is not a substitute for the coastline test",
        ).toBeGreaterThan(check!.withinKm);
      }
    });
  });

  /**
   * Two operators publishing the same antenna farm under two names is a real
   * failure mode and it arrived with the second batch: Viasat's "Alice Springs"
   * is 0.26 km from the Geoscience Australia pin, SSC's "Siracha" is 0.25 km
   * from GISTDA's, and Viasat's "Pretoria" is 1.02 km from SANSA's
   * Hartebeesthoek. Those are not four stations, they are two, and a map that
   * draws them twice is claiming infrastructure that is not there.
   *
   * So proximity is a hard error unless the table says out loud that the two
   * really are separate antennas. Deep-space complexes genuinely have several
   * dishes a few hundred metres apart, which is why the answer is a declaration
   * rather than a ban.
   */
  describe("stations that are close enough to be the same antenna farm", () => {
    const declared = new Set(
      ((table as { coLocated?: Array<{ stations: string[] }> }).coLocated ?? [])
        .map((entry) => [...entry.stations].sort().join("|")),
    );
    const thresholdKm = (table as { coLocationThresholdKm?: number }).coLocationThresholdKm ?? 3;

    it("makes every close pair declare itself, with a reason", () => {
      const undeclared: string[] = [];
      for (let i = 0; i < stations.length; i += 1) {
        for (let j = i + 1; j < stations.length; j += 1) {
          const gap = separationKm(
            stations[i]!.latitudeDeg, stations[i]!.longitudeDeg,
            stations[j]!.latitudeDeg, stations[j]!.longitudeDeg,
          );
          if (gap >= thresholdKm) continue;
          const key = [stations[i]!.id, stations[j]!.id].sort().join("|");
          if (!declared.has(key)) undeclared.push(`${key} (${gap.toFixed(2)} km)`);
        }
      }
      expect(
        undeclared,
        "these pairs are close enough to be one site entered twice and nothing says otherwise",
      ).toEqual([]);
    });

    it("keeps every declaration honest, with a reason and two stations that exist", () => {
      const entries = (table as { coLocated?: Array<{ stations: string[]; reason: string }> }).coLocated ?? [];
      expect(entries.length, "the declaration list is empty").toBeGreaterThan(0);
      const ids = new Set(stations.map((station) => station.id));
      for (const entry of entries) {
        expect(entry.stations.length, "a declaration names two stations").toBe(2);
        for (const id of entry.stations) expect(ids.has(id), `${id} is not in the table`).toBe(true);
        expect(entry.reason.length, `${entry.stations.join("/")}: a declaration needs a reason`)
          .toBeGreaterThan(24);
      }
    });
  });

  /**
   * The rendered-pixel guard in ground-station-overlay.spec.ts can only read a
   * colour where neither the station nor the point ninety degrees east of it
   * lands on a mixed coastal pixel. Choosing those sites by eye put a station
   * twenty kilometres off Asturias into the "this is open ocean" half of the
   * comparison. So the choice is measured, and it is re-measured here on every
   * run rather than trusted to a comment.
   */
  describe("the sites the rendered-pixel guard probes", () => {
    it("keeps every probe site far from a coast on both sides of the comparison", () => {
      for (const site of RENDER_PROBE_SITES) {
        const station = stations.find((candidate) => candidate.id === site.id);
        expect(station, `${site.id} is not in the table`).toBeTruthy();
        const { latitudeDeg, longitudeDeg } = geographyOf(stationScenePosition(station!));
        const eastward = wrapLongitude(longitudeDeg + 90);

        expect(onLand(longitudeDeg, latitudeDeg), `${site.id} is not on land`).toBe(true);
        expect(onLand(eastward, latitudeDeg), `${site.id}: ninety degrees east is not open water`).toBe(false);

        const margin = Math.min(
          nearestCoastKm(longitudeDeg, latitudeDeg),
          nearestCoastKm(eastward, latitudeDeg),
        );
        expect(margin, `${site.id} has only ${Math.round(margin)} km of clearance`)
          .toBeGreaterThanOrEqual(MINIMUM_PROBE_MARGIN_KM);
        // And the recorded figure has to still be true, so the file cannot
        // drift away from what the coastlines actually say.
        expect(Math.abs(margin - site.marginKm), `${site.id}: recorded margin is stale`)
          .toBeLessThan(15);
      }
    });
  });
});
