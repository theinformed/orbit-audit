/**
 * Browser-side half of the ground-track window control guard.
 *
 * It mounts the shipped map with the shipped propagator: SGP4 through the
 * project's own propagateOmm, the same call src/main.ts makes, so the span
 * control, the window editor and the footprint are exercised over real orbital
 * motion rather than over a stand-in that cannot disagree with anything.
 *
 * The element sets are synthetic but physical — a sun-synchronous low orbit, a
 * geostationary slot, and a low orbit whose track runs over the north pole and
 * across the antimeridian — so the harness carries no upstream catalogue data
 * and makes no network request of any kind.
 */
import { json2satrec } from "satellite.js";
import { mountGroundTrackMap, type GroundTrackWindow } from "../src/ground-track-map";
import { propagateOmm } from "../src/orbit";
import type { OmmRecord } from "../src/types";

const EPOCH = "2026-08-07T12:00:00.000Z";

function elements(overrides: Partial<OmmRecord> & { OBJECT_NAME: string; MEAN_MOTION: number }): OmmRecord {
  return {
    OBJECT_ID: "2026-001A",
    EPOCH,
    ECCENTRICITY: 0.0001,
    INCLINATION: 51.6,
    RA_OF_ASC_NODE: 120,
    ARG_OF_PERICENTER: 90,
    MEAN_ANOMALY: 0,
    EPHEMERIS_TYPE: 0,
    CLASSIFICATION_TYPE: "U",
    NORAD_CAT_ID: 99001,
    ELEMENT_SET_NO: 999,
    REV_AT_EPOCH: 100,
    BSTAR: 0.0001,
    MEAN_MOTION_DOT: 0,
    MEAN_MOTION_DDOT: 0,
    ...overrides,
  };
}

export interface HarnessCase {
  label: string;
  omm: OmmRecord;
  periodMinutes: number;
  window: GroundTrackWindow;
}

const cases: Record<string, HarnessCase> = {
  // 15.19 revolutions a day: a 94.8-minute period, the default in the dialog.
  leo: {
    label: "LEO 94.8 min",
    omm: elements({ OBJECT_NAME: "TEACHING LEO", MEAN_MOTION: 15.1899, INCLINATION: 51.64 }),
    periodMinutes: 94.8,
    window: { kind: "orbital-period", periodMinutes: 94.8 },
  },
  // One revolution per sidereal day, essentially zero inclination: the case
  // where "one orbit" and "24 hours" are the same window.
  geo: {
    label: "GEO 1436 min",
    omm: elements({
      OBJECT_NAME: "TEACHING GEO",
      MEAN_MOTION: 1.00272,
      INCLINATION: 0.04,
      ECCENTRICITY: 0.0002,
      NORAD_CAT_ID: 99002,
    }),
    periodMinutes: 1436,
    window: { kind: "geosynchronous-analemma", hours: 24 },
  },
  // Near-polar, so the footprint swallows the pole, and phased to cross the
  // antimeridian: both flat-map traps in one spacecraft.
  polar: {
    label: "POLAR 100.4 min",
    omm: elements({
      OBJECT_NAME: "TEACHING POLAR",
      MEAN_MOTION: 14.34,
      INCLINATION: 98.7,
      RA_OF_ASC_NODE: 20,
      NORAD_CAT_ID: 99003,
    }),
    periodMinutes: 100.4,
    window: { kind: "orbital-period", periodMinutes: 100.4 },
  },
};

let controller: ReturnType<typeof mountGroundTrackMap> | null = null;
/** What the map last reported about its window, for a caller's caption line. */
let lastWindowDescription = "";

function mount(caseName: keyof typeof cases, atIso: string, minimumElevationDeg: number) {
  const chosen = cases[caseName]!;
  const at = new Date(atIso);
  const satrec = json2satrec(chosen.omm);
  const samples = chosen.periodMinutes >= 1380 ? 288 : 180;
  const points = [];
  for (let index = 0; index <= samples; index += 1) {
    const offsetMinutes = (index / samples - 0.5) * (chosen.periodMinutes >= 1380 ? 1440 : chosen.periodMinutes);
    const sampleTime = new Date(at.getTime() + offsetMinutes * 60000);
    const state = propagateOmm(chosen.omm, sampleTime, satrec);
    if (state) points.push({ longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg, at: sampleTime });
  }
  const current = propagateOmm(chosen.omm, at, satrec);

  controller?.destroy();
  controller = mountGroundTrackMap(document.getElementById("mount")!, {
    points,
    satelliteName: chosen.omm.OBJECT_NAME,
    currentTime: at,
    currentPosition: current
      ? { longitudeDeg: current.longitudeDeg, latitudeDeg: current.latitudeDeg, at }
      : undefined,
    periodMinutes: chosen.periodMinutes,
    footprintMinElevationDeg: minimumElevationDeg,
    sampleAt: (time) => {
      const state = propagateOmm(chosen.omm, time, satrec);
      return state
        ? { longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg, altitudeKm: state.altitudeKm }
        : null;
    },
    onWindowChange: (summary) => {
      lastWindowDescription = summary.description;
    },
    window: chosen.window,
  });
}

/** Mount with no propagator at all — the degraded path, before any wiring. */
function mountWithoutPropagator(caseName: keyof typeof cases, atIso: string) {
  const chosen = cases[caseName]!;
  const at = new Date(atIso);
  const satrec = json2satrec(chosen.omm);
  const points = [];
  for (let index = 0; index <= 180; index += 1) {
    const sampleTime = new Date(at.getTime() + (index / 180 - 0.5) * chosen.periodMinutes * 60000);
    const state = propagateOmm(chosen.omm, sampleTime, satrec);
    if (state) points.push({ longitudeDeg: state.longitudeDeg, latitudeDeg: state.latitudeDeg, at: sampleTime });
  }
  controller?.destroy();
  controller = mountGroundTrackMap(document.getElementById("mount")!, {
    points,
    satelliteName: chosen.omm.OBJECT_NAME,
    currentTime: at,
    window: chosen.window,
  });
}

function selectedTimeIso(): string {
  return controller ? controller.selectedTime.toISOString() : "";
}

function windowDescription(): string {
  return lastWindowDescription;
}

Object.assign(window as unknown as Record<string, unknown>, {
  groundTrackHarness: { mount, mountWithoutPropagator, selectedTimeIso, windowDescription },
  groundTrackHarnessReady: true,
});
