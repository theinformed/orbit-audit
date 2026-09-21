/**
 * The probe's layer section, drawn with the real published artifact.
 *
 * A harness rather than a unit test because the thing being checked is the
 * PICTURE: whether a faint bar reads as faint, whether an absent F1 reads as a
 * statement rather than a hole, and whether the station line is the first thing
 * the eye lands on. None of that is provable by an assertion, and this project
 * has shipped layers that every test passed and that looked wrong.
 */

import "../src/styles.css";
import { compositeProfile, COMPOSITE_IONOSPHERE_METHOD } from "../src/ionosphere-composite";
import { drawLayerLadder, layerRow, networkNote } from "../src/ionosphere-composite-view";
import {
  nearestSounding,
  relevanceNote,
  soundingAgeNote,
  soundingRelevance,
  SOUNDING_EVIDENCE_NOTE,
  type SoundingBundle,
} from "../src/ionosonde-soundings";
import { sampleEmpiricalDRegion } from "../src/d-region-empirical";

interface Case {
  title: string;
  latitudeDeg: number;
  longitudeDeg: number;
  /** WAM-IPE's foF2 over the point, or null to show the no-column case. */
  modelFoF2Mhz: number | null;
  modelHmF2Km: number | null;
}

const CASES: Case[] = [
  // Rome is 180 km from Naples: the only kind of case where a sounding really
  // does describe the reader's point.
  { title: "Naples — 180 km from a sounding", latitudeDeg: 40.8, longitudeDeg: 14.2, modelFoF2Mhz: 7.1, modelHmF2Km: 285 },
  // Daylit, so F1 must be PRESENT and the E layer produced.
  { title: "Boa Vista, Brazil — daylit, F1 present", latitudeDeg: 2.8, longitudeDeg: -60.7, modelFoF2Mhz: 10.1, modelHmF2Km: 300 },
  // 4,673 km from Gakona. The common case, and the one the feature must refuse
  // to dress up.
  { title: "Pearl Harbor — 4,673 km from the nearest sounding", latitudeDeg: 21.3, longitudeDeg: -157.9, modelFoF2Mhz: 8.4, modelHmF2Km: 310 },
  // Mid-Pacific: beyond the range at which soundings say anything at all.
  { title: "Mid-Pacific — no sounding within range", latitudeDeg: -20, longitudeDeg: -140, modelFoF2Mhz: 6.2, modelHmF2Km: 295 },
  // The same place with no model column loaded, which is what a visitor sees
  // before they spend 19 MB.
  { title: "Naples — model column not loaded", latitudeDeg: 40.8, longitudeDeg: 14.2, modelFoF2Mhz: null, modelHmF2Km: null },
];

async function main() {
  const manifest = await fetch("/data/manifest.json").then((r) => r.json());
  const bundle: SoundingBundle = await fetch(`/data/${manifest.ionosondeSoundings.path}`).then((r) => r.json());
  const time = new Date(bundle.observedAt);
  const host = document.getElementById("cases")!;

  for (const testCase of CASES) {
    const point = { latitudeDeg: testCase.latitudeDeg, longitudeDeg: testCase.longitudeDeg };
    const dRegion = sampleEmpiricalDRegion(point.latitudeDeg, point.longitudeDeg, time, 2.1e-6);
    const composite = compositeProfile({
      point,
      time,
      stations: bundle.stations,
      xrayFluxWm2: 2.1e-6,
      modelFoF2Mhz: testCase.modelFoF2Mhz,
      modelHmF2Km: testCase.modelHmF2Km,
      dRegionEffectiveHeightKm: dRegion.effectiveHeightKm,
      dRegionBetaPerKm: dRegion.betaPerKm,
    });

    const panel = document.createElement("aside");
    panel.className = "probe-panel";
    panel.style.position = "static";
    panel.style.maxHeight = "none";
    panel.innerHTML = `
      <div class="probe-head"><div><span class="section-kicker">PROBE</span><strong>${testCase.title}</strong></div></div>
      <div class="probe-body">
        <section class="probe-layers">
          <h3 class="probe-layers-title">Layer structure <span class="layer-status composite">COMPOSITE</span></h3>
          <p class="probe-station"></p>
          <svg class="probe-ladder" viewBox="0 0 232 168" role="img"></svg>
          <p class="probe-note">Bar length is the critical frequency; a faint bar is a layer with no sounding near this point.</p>
          <ul class="probe-layer-list"></ul>
          <p class="probe-note evidence"></p>
          <details class="probe-limits" open>
            <summary>What the layer structure does not cover</summary>
            <p class="probe-note sounding"></p>
            <p class="probe-note network"></p>
            <p class="probe-note limit"></p>
          </details>
        </section>
      </div>`;

    const line = panel.querySelector<HTMLElement>(".probe-station")!;
    const nearest = nearestSounding(point, bundle.stations);
    if (nearest) {
      const relevance = soundingRelevance(nearest.distanceKm);
      line.className = `probe-station ${relevance}`;
      const named = document.createElement("b");
      named.textContent = `${nearest.station.name} · ${Math.round(nearest.distanceKm).toLocaleString()} km`;
      line.replaceChildren(named, document.createTextNode(
        ` · ${soundingAgeNote(nearest.station.ageMinutes)} ${relevanceNote(relevance)}`));
    }

    drawLayerLadder(panel.querySelector(".probe-ladder")!, composite);
    panel.querySelector(".probe-layer-list")!.replaceChildren(...composite.layers.map(layerRow));
    panel.querySelector<HTMLElement>(".evidence")!.textContent = composite.evidenceNote;
    panel.querySelector<HTMLElement>(".sounding")!.textContent = SOUNDING_EVIDENCE_NOTE;
    panel.querySelector<HTMLElement>(".network")!.textContent = networkNote(bundle);
    panel.querySelector<HTMLElement>(".limit")!.textContent = COMPOSITE_IONOSPHERE_METHOD.limitations[0];
    host.append(panel);
  }
  document.body.dataset.ready = "true";
}

void main();
