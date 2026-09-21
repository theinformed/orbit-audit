import { EVIDENCE } from "../src/learning-evidence";
/**
 * The composite ionosphere, and the rules that keep it honest.
 *
 * Every test here pins a REASON. The numbers in the expectations are either
 * exact physics, or they are re-derived from the constants rather than pasted,
 * so a test failing means a claim changed rather than a digit drifting.
 */

import { describe, expect, it } from "vitest";
import indexMarkup from "../index.html?raw";
import explorerSource from "../src/main.ts?raw";
import stylesheet from "../src/styles.css?raw";
import {
  ANCHOR_EFOLD_KM,
  ANCHOR_IGNORE_KM,
  CHAPMAN_EXPONENT,
  COMPOSITE_IONOSPHERE_METHOD,
  F1_MAX_SOLAR_ZENITH_DEG,
  LADDER_FULL_SCALE_MHZ,
  LADDER_MIN_KM,
  anchorWeight,
  blendTowardAnchor,
  chapmanCriticalFrequencyMhz,
  chapmanDensityM3,
  compositeProfile,
  criticalFrequencyToDensityM3,
  fitOverheadCriticalFrequencyMhz,
  ladderGeometry,
  nearestWith,
} from "../src/ionosphere-composite";
import {
  greatCircleDistanceKm,
  readLayer,
  soundingRelevance,
  type Sounding,
} from "../src/ionosonde-soundings";
import { PLASMA_FREQUENCY_MHZ_COEFFICIENT } from "../src/ionosphere-profile";

function station(overrides: Partial<Sounding> = {}): Sounding {
  return {
    code: "TEST1", name: "Test Station", latitudeDeg: 0, longitudeDeg: 0,
    soundedAt: "2026-08-19T12:00:00Z", ageMinutes: 10,
    foF2Mhz: 8, hmF2Km: 300, foF1Mhz: null, hmF1Km: null,
    foEMhz: null, hmEKm: null, eHeightIsNominal: false, foEsMhz: null,
    confidence: 100, upstreamSource: "giro", ...overrides,
  };
}

describe("the plasma relation, inverted", () => {
  /**
   * The site already turns density into a critical frequency. This turns a
   * MEASURED critical frequency back into a density, and the two must be exact
   * inverses or a measured foE and a modelled foF2 would sit on two different
   * conventions in the same picture.
   */
  it("round-trips the site's own plasma-frequency constant", () => {
    const density = criticalFrequencyToDensityM3(10)!;
    expect(PLASMA_FREQUENCY_MHZ_COEFFICIENT * Math.sqrt(density)).toBeCloseTo(10, 9);
  });

  it("refuses a non-physical critical frequency rather than returning a density", () => {
    expect(criticalFrequencyToDensityM3(0)).toBeNull();
    expect(criticalFrequencyToDensityM3(-3)).toBeNull();
    expect(criticalFrequencyToDensityM3(null)).toBeNull();
  });
});

describe("the Chapman layer, which is where the E and F1 shapes come from", () => {
  /** By definition the layer peaks at Nm at h = hm; z = 0 makes the exponent 0.5*(1-0-1) = 0. */
  it("peaks at exactly the peak density, at exactly the peak height", () => {
    expect(chapmanDensityM3(110, 1e11, 110, 8)).toBeCloseTo(1e11, 3);
  });

  /**
   * The asymmetry is the physical content: above the peak the layer decays
   * with the scale height, below it production runs out and it falls away far
   * faster. A symmetric profile would be a Gaussian bump, not an ionised layer.
   */
  it("falls away far more steeply below the peak than above it", () => {
    const above = chapmanDensityM3(126, 1e11, 110, 8)!;
    const below = chapmanDensityM3(94, 1e11, 110, 8)!;
    expect(below).toBeLessThan(above);
    expect(below / above).toBeLessThan(0.2);
  });

  /**
   * exp(-z) overflows for a point far below the peak. The density there is
   * zero to any precision that matters, and an Infinity would poison every
   * consumer downstream.
   */
  it("returns zero rather than an overflow far below the peak", () => {
    const value = chapmanDensityM3(0, 1e11, 300, 8);
    expect(value).toBe(0);
    expect(Number.isFinite(value!)).toBe(true);
  });

  /**
   * Chapman theory says peak density goes as cos(chi), so a critical frequency
   * goes as cos(chi)^0.25. Fitting a free power law to every sounding in the
   * network with a scaled foE and the sun up (n=33, 2026-08-19) gave an
   * exponent of 0.268 against theory's 0.25 — a 7% agreement, which is why the
   * constant here is theory's value rather than that afternoon's fit.
   */
  it("uses Chapman's exponent, which the network's own soundings confirmed", () => {
    expect(CHAPMAN_EXPONENT).toBe(0.25);
    const overhead = chapmanCriticalFrequencyMhz(4, 0)!;
    const sixtyDeg = chapmanCriticalFrequencyMhz(4, 60)!;
    // cos(60) = 0.5 exactly, so the ratio is 0.5^0.25 by construction.
    expect(sixtyDeg / overhead).toBeCloseTo(0.5 ** 0.25, 9);
  });

  /**
   * A layer produced by sunlight has no Chapman value in darkness. Returning 0
   * would read as "measured, and nothing there", which is a different and
   * stronger claim than "not produced here".
   */
  it("returns nothing below the horizon instead of a zero frequency", () => {
    expect(chapmanCriticalFrequencyMhz(4, 91)).toBeNull();
    expect(chapmanCriticalFrequencyMhz(4, 120)).toBeNull();
  });
});

describe("how far a sounding is allowed to speak", () => {
  /**
   * Measured, not chosen: taking every pair of fresh stations and comparing
   * their foF2 residuals about a common solar baseline (26 stations, 325 pairs,
   * 2026-08-19), the RMS pair difference was 11% of the unrelated-pair level
   * below 500 km and 92% at 3,000-5,000 km. The weight has to be near 1 where
   * a sounding tells you nearly everything and near 0 where it tells you
   * nothing, and these two assertions are that statement.
   */
  it("believes a sounding 500 km away almost completely", () => {
    expect(anchorWeight(500)).toBeGreaterThan(0.9);
  });

  it("stops believing one entirely past the range where soundings relate at all", () => {
    expect(anchorWeight(ANCHOR_IGNORE_KM)).toBe(0);
    expect(anchorWeight(ANCHOR_IGNORE_KM + 1)).toBe(0);
  });

  /** Gaussian, so the fall-off is flat close in and steep at the e-folding distance. */
  it("falls off as a Gaussian rather than an exponential", () => {
    expect(anchorWeight(ANCHOR_EFOLD_KM)).toBeCloseTo(Math.exp(-1), 6);
    // Flat close in: the first 500 km costs less than the next 500.
    const firstHalf = anchorWeight(0) - anchorWeight(500);
    const secondHalf = anchorWeight(500) - anchorWeight(1_000);
    expect(firstHalf).toBeLessThan(secondHalf);
  });

  /**
   * The bands and the arithmetic must agree. They were set independently at
   * first and the panel ended up calling a sounding "very little information"
   * in the same breath as reporting it beyond the range where soundings relate
   * to each other at all.
   */
  it("grades distance on the same boundary the anchor arithmetic stops at", () => {
    expect(soundingRelevance(ANCHOR_IGNORE_KM)).toBe("distant");
    expect(soundingRelevance(ANCHOR_IGNORE_KM + 1)).toBe("unrelated");
    expect(anchorWeight(ANCHOR_IGNORE_KM + 1)).toBe(0);
  });

  /** Haversine, so a short separation keeps its precision. Rome to Naples. */
  it("measures a short great-circle distance to the kilometre", () => {
    const km = greatCircleDistanceKm(
      { latitudeDeg: 41.8, longitudeDeg: 12.5 },
      { latitudeDeg: 40.8, longitudeDeg: 14.2 },
    );
    expect(km).toBeGreaterThan(160);
    expect(km).toBeLessThan(200);
  });
});

describe("blending a model toward a measurement", () => {
  it("returns the model untouched when nothing is near", () => {
    expect(blendTowardAnchor(7, 9, 0)).toBe(7);
  });

  it("returns the measurement when a station is on top of the point", () => {
    expect(blendTowardAnchor(7, 9, 1)).toBe(9);
  });

  /**
   * A measured value with no model to blend into is the "column not loaded"
   * case. Requiring weight exactly 1 meant a station 180 km away — weight
   * 0.996 — rendered as "not available" directly beneath a sentence naming it.
   */
  it("stands a nearby measurement on its own when there is no model to combine it with", () => {
    expect(blendTowardAnchor(null, 9, 0.996)).toBe(9);
  });

  /** But not a distant one: that would present a far sounding as this point's value. */
  it("refuses to let a distant measurement stand in for an absent model", () => {
    expect(blendTowardAnchor(null, 9, 0.3)).toBeNull();
  });
});

describe("fitting the layer strength to today's network", () => {
  /**
   * This is what makes the composite driven by today rather than by a table:
   * each station's own measurement is projected to overhead sun and the median
   * is taken. A single station measuring foE = 3 with the sun overhead must
   * imply an overhead value of 3.
   */
  it("recovers the overhead value from a station under an overhead sun", () => {
    const fit = fitOverheadCriticalFrequencyMhz(
      [station({ latitudeDeg: 0, longitudeDeg: 0, foEMhz: 3 }),
       station({ code: "B", latitudeDeg: 1, longitudeDeg: 0, foEMhz: 3 }),
       station({ code: "C", latitudeDeg: -1, longitudeDeg: 0, foEMhz: 3 })],
      { latitudeDeg: 0, longitudeDeg: 0 },
      (s) => s.foEMhz,
    )!;
    expect(fit.overheadMhz).toBeCloseTo(3, 2);
    expect(fit.contributingStations).toBe(3);
  });

  /**
   * The median, not the mean, because on 2026-08-19 only 5 fresh stations in
   * the entire network had a scaled foE. With a sample that small one
   * mis-scaled ionogram drags a mean badly and a median barely at all.
   */
  it("ignores one wildly mis-scaled station, which a mean would not", () => {
    const good = [3, 3.1, 2.9, 3.05];
    const stations = [...good, 40].map((foEMhz, index) =>
      station({ code: `S${index}`, latitudeDeg: 0, longitudeDeg: 0, foEMhz }));
    const fit = fitOverheadCriticalFrequencyMhz(stations, { latitudeDeg: 0, longitudeDeg: 0 }, (s) => s.foEMhz)!;
    expect(fit.overheadMhz).toBeLessThan(4);
  });

  /**
   * Too few stations means no amplitude, and no amplitude must mean no layer
   * rather than a guessed one. A drawn layer with an invented strength is the
   * exact failure this feature exists not to commit.
   */
  it("returns nothing rather than an amplitude when too few stations contribute", () => {
    expect(fitOverheadCriticalFrequencyMhz(
      [station({ foEMhz: 3 })], { latitudeDeg: 0, longitudeDeg: 0 }, (s) => s.foEMhz,
    )).toBeNull();
  });

  /**
   * A station at grazing incidence divides by a small cosine, turning a routine
   * scaling error into a large amplitude error, so it does not get a vote.
   */
  it("does not let a station at grazing incidence set the network amplitude", () => {
    const grazing = [0, 1, 2].map((i) =>
      station({ code: `G${i}`, latitudeDeg: 85 + i * 0.1, longitudeDeg: 0, foEMhz: 3 }));
    expect(fitOverheadCriticalFrequencyMhz(grazing, { latitudeDeg: 0, longitudeDeg: 0 }, (s) => s.foEMhz)).toBeNull();
  });
});

describe("absence is a fact, not a gap", () => {
  /**
   * The threshold is measured: across the whole network the largest solar
   * zenith angle at which any station reported an F1 layer was 72.5 deg, and
   * F1 was present in 0% of records taken above 80 deg.
   */
  it("puts the F1 cut-off where the network's own soundings put it", () => {
    expect(F1_MAX_SOLAR_ZENITH_DEG).toBe(72.5);
  });

  it("reports a night F1 as the layer being absent, never as data missing", () => {
    const reading = readLayer(station({ foF1Mhz: null }), "F1", 110);
    expect(reading.state).toBe("absent");
    expect(reading.state === "absent" && reading.reason).toMatch(/daytime-only/i);
  });

  /**
   * The same null in daylight is a DIFFERENT result: the layer should be there
   * and the ionogram could not be scaled. Rendering these two the same way
   * would teach a reader that the ionosphere has holes in it.
   */
  it("distinguishes an unscaled daytime F1 from an absent night one", () => {
    const reading = readLayer(station({ foF1Mhz: null }), "F1", 30);
    expect(reading.state).toBe("unscaled");
  });

  it("reports a night composite F1 as absent, with the reason in the panel", () => {
    const profile = compositeProfile({
      point: { latitudeDeg: 51, longitudeDeg: 0 },
      // Local midnight over Greenwich in December: unambiguously dark.
      time: new Date("2026-12-21T00:00:00Z"),
      stations: [station({ foF1Mhz: 5 })],
      xrayFluxWm2: 1e-7, modelFoF2Mhz: 6, modelHmF2Km: 300,
      dRegionEffectiveHeightKm: 84, dRegionBetaPerKm: 0.63,
    });
    const f1 = profile.layers.find((layer) => layer.layer === "F1")!;
    expect(f1.criticalFrequencyMhz).toBeNull();
    expect(f1.absentReason).toMatch(/being absent, not a gap/i);
  });
});

describe("the composite as a whole", () => {
  const near = station({ latitudeDeg: 41.8, longitudeDeg: 12.5, name: "Rome", foF2Mhz: 9, foEMhz: 3, foF1Mhz: 4.5 });
  const far = station({ code: "FAR", name: "Far", latitudeDeg: -40, longitudeDeg: 175, foF2Mhz: 4 });

  function profileAt(latitudeDeg: number, longitudeDeg: number, stations: Sounding[]) {
    return compositeProfile({
      point: { latitudeDeg, longitudeDeg },
      time: new Date("2026-06-21T11:00:00Z"),
      stations,
      xrayFluxWm2: 2e-6, modelFoF2Mhz: 7, modelHmF2Km: 300,
      dRegionEffectiveHeightKm: 70, dRegionBetaPerKm: 0.34,
    });
  }

  it("always describes four layers, so none can silently vanish", () => {
    const layers = profileAt(40.8, 14.2, [near, far]).layers.map((layer) => layer.layer);
    expect(layers).toEqual(["D", "E", "F1", "F2"]);
  });

  /**
   * Requirement: a reader must be able to see that F2 is NOAA's model, E is a
   * physical shape pinned to real soundings, and D is an empirical fit driven
   * by a measured flux. That is per-layer provenance, and it is not optional.
   */
  it("gives every layer its own plain-language source", () => {
    for (const layer of profileAt(40.8, 14.2, [near, far]).layers) {
      expect(layer.plainSource.length).toBeGreaterThan(30);
    }
  });

  /**
   * The D region can never be anchored, and saying so is a teaching point
   * rather than an omission: an ionosonde's pulse passes straight through it,
   * and it appears on an ionogram only as the echo it absorbed.
   */
  it("never claims a sounding measured the D region", () => {
    const d = profileAt(40.8, 14.2, [near, far]).layers.find((layer) => layer.layer === "D")!;
    expect(d.anchorStationCode).toBeNull();
    expect(d.criticalFrequencyMhz).toBeNull();
    expect(d.plainSource).toMatch(/no ionosonde can measure the D region/i);
  });

  /**
   * The whole point of the distance rule. The same model column with the same
   * nearby measurement must move toward it when the station is close and not
   * move at all when it is not.
   */
  it("pulls F2 toward a nearby sounding and leaves it alone when none is near", () => {
    const close = profileAt(40.8, 14.2, [near]).layers.find((l) => l.layer === "F2")!;
    const alone = profileAt(-20, -140, [far]).layers.find((l) => l.layer === "F2")!;
    expect(close.criticalFrequencyMhz!).toBeGreaterThan(8);
    expect(alone.criticalFrequencyMhz).toBe(7);
    expect(alone.anchorWeight).toBe(0);
  });

  /**
   * Requirement 3: where the network is thin the anchoring must visibly weaken.
   * Anchor weight is what the renderer turns into opacity, so this is the test
   * that the picture fades over an ocean.
   */
  it("drops the anchor weight to zero where no station is within range", () => {
    for (const layer of profileAt(-20, -140, [far]).layers) {
      expect(layer.anchorWeight).toBe(layer.layer === "D" ? 0 : 0);
    }
  });

  it("names the nearest station and its distance, always", () => {
    const profile = profileAt(40.8, 14.2, [near, far]);
    expect(profile.nearestStationName).toBe("Rome");
    expect(profile.nearestStationKm!).toBeLessThan(200);
  });

  /** The claim in the sentence has to change with the distance behind it. */
  it("weakens the evidence sentence as the nearest sounding recedes", () => {
    expect(profileAt(40.8, 14.2, [near, far]).evidenceNote).toMatch(/constrains the layers over this point/i);
    expect(profileAt(-20, -140, [far]).evidenceNote).toMatch(/beyond the range|barely constrains/i);
  });

  /**
   * The nearest station overall is often not the nearest one that scaled the
   * layer in question. Falling back to the nearest station's other parameters
   * would put one station's name against another station's number.
   */
  it("anchors each layer to the nearest station that actually scaled THAT layer", () => {
    const withoutE = station({ code: "NOE", name: "No E", latitudeDeg: 41, longitudeDeg: 13, foEMhz: null });
    const result = nearestWith({ latitudeDeg: 40.8, longitudeDeg: 14.2 }, [withoutE, near], (s) => s.foEMhz);
    expect(result!.station.name).toBe("Rome");
  });
});

describe("the ladder, which is the picture", () => {
  const layers = compositeProfile({
    point: { latitudeDeg: 40.8, longitudeDeg: 14.2 },
    time: new Date("2026-06-21T11:00:00Z"),
    stations: [station({ latitudeDeg: 41.8, longitudeDeg: 12.5, foF2Mhz: 9, foEMhz: 3, foF1Mhz: 4.5 })],
    xrayFluxWm2: 2e-6, modelFoF2Mhz: 7, modelHmF2Km: 300,
    dRegionEffectiveHeightKm: 70, dRegionBetaPerKm: 0.34,
  }).layers;

  /** Height is the axis, so a higher layer must draw higher on the page. */
  it("draws a higher layer higher up", () => {
    const geometry = ladderGeometry(layers);
    const byLayer = Object.fromEntries(geometry.bars.map((bar) => [bar.layer, bar.y]));
    expect(byLayer.F2!).toBeLessThan(byLayer.F1!);
    expect(byLayer.F1!).toBeLessThan(byLayer.E!);
    expect(byLayer.E!).toBeLessThan(byLayer.D!);
  });

  /**
   * The ticks and the layer names both live in the left margin, and at the
   * original 30 units "300" sat on top of "F2" whenever the F2 peak landed
   * near a tick — which it does on most days.
   */
  it("keeps the altitude ticks clear of the layer names", () => {
    expect(ladderGeometry(layers).axisX).toBeGreaterThanOrEqual(44);
  });

  /**
   * Bar length is the critical frequency, so the full scale has to sit above
   * every foF2 the network reports. The maximum on the measured frame was
   * 10.35 MHz at Boa Vista.
   */
  it("scales bars so a normal day never clips", () => {
    expect(LADDER_FULL_SCALE_MHZ).toBeGreaterThan(10.35);
  });

  /**
   * A layer with no critical frequency must not draw as a bar of length zero.
   * The D region is the permanent case, and a 2 px stub at the axis read as
   * "nothing is here" when the true statement is "something is here that this
   * axis cannot show".
   */
  it("gives the non-reflecting D region a visible band rather than a stub", () => {
    const d = ladderGeometry(layers).bars.find((bar) => bar.layer === "D")!;
    expect(d.width).toBeGreaterThan(20);
    expect(d.valueText).toMatch(/absorbs/i);
  });
});

describe("the badge, and the wiring", () => {
  /**
   * It is not OBSERVED — most of the globe has no sounding within thousands of
   * kilometres — and it is not MODEL, because the E and F1 amplitudes come from
   * instruments that sounded in the last three hours. Claiming either would be
   * wrong in a different direction.
   */
  it("is badged COMPOSITE and says why in the evidence sentence", () => {
    expect(COMPOSITE_IONOSPHERE_METHOD.evidence).toBe("composite");
    const note = compositeProfile({
      point: { latitudeDeg: 0, longitudeDeg: 0 }, time: new Date("2026-06-21T11:00:00Z"),
      stations: [station()], xrayFluxWm2: 1e-6, modelFoF2Mhz: 7, modelHmF2Km: 300,
      dRegionEffectiveHeightKm: 70, dRegionBetaPerKm: 0.34,
    }).evidenceNote;
    expect(note).toMatch(/^COMPOSITE: not a measurement and not a single model/);
  });

  /** The class has to sit in the same table as the others or it can be paraphrased away. */
  it("puts COMPOSITE in the shared evidence vocabulary, not beside it", () => {
    expect(explorerSource).toContain('type LegendEvidence = Evidence;');
    expect(explorerSource).toContain('const EVIDENCE_MEANINGS: Record<LegendEvidence, string> = EVIDENCE;');
    expect(EVIDENCE.composite).toContain('each component must state its own class');
    expect(stylesheet).toContain(".layer-status.composite");
  });

  /**
   * This project has repeatedly shipped features that every unit test passed
   * over and no entry point reached, so the panel asserts its own wiring.
   */
  it("ships the markup the renderer writes into", () => {
    for (const id of ["probe-layers", "probe-station", "probe-ladder", "probe-layer-list",
                      "probe-composite-evidence", "probe-network-note", "probe-model-section"]) {
      expect(indexMarkup).toContain(`id="${id}"`);
    }
  });

  it("reaches the renderer from the probe's own render path", () => {
    expect(explorerSource).toContain("this.renderCompositeLayers(point");
    expect(explorerSource).toContain("private renderCompositeLayers(");
    expect(explorerSource).toContain("private loadSoundings()");
  });

  /**
   * The soundings artifact is about 9 KB. Gating four measured critical
   * frequencies behind the 19 MB model column would be a cost with no reason
   * behind it, so the layer section must be drawn BEFORE the column is checked.
   */
  it("draws the measured layers without waiting for the 19 MB column", () => {
    const render = explorerSource.slice(explorerSource.indexOf("private renderProbe("));
    const body = render.slice(0, render.indexOf("\n  }"));
    // `load.hidden = false` is the branch that asks the visitor to spend the
    // 19 MB. The layer section must already have been drawn by the time that
    // branch is reached, or a reader who declines the download sees nothing.
    expect(body).toContain("load.hidden = false");
    expect(body.indexOf("this.renderCompositeLayers(")).toBeGreaterThan(-1);
    expect(body.indexOf("this.renderCompositeLayers(")).toBeLessThan(body.indexOf("load.hidden = false"));
  });

  /** A refreshed release must not leave the probe showing the previous ages. */
  it("redraws an open probe when a new release lands", () => {
    expect(explorerSource).toContain('case "ionosondeSoundings"');
  });
});

describe("the ladder's axis reaches every height its own rows print", () => {
  /**
   * The D bar is placed at the layer's own `peakHeightKm`, and the row beside
   * it prints that same height in words. `yFor` clamps to LADDER_MIN_KM, so
   * any height the D-region model can produce below the floor is a drawing
   * that disagrees with its own caption.
   *
   * The floor was 60 km. The Wait-Spies effective reflection height comes DOWN
   * under a flare — the model's published domain runs to X45, where it reaches
   * 53 km — so from about X1.4 in full daylight the row said one number and
   * the bar sat at another. This pins the axis against the model rather than
   * against a remembered value.
   */
  it("puts the flare-depressed D region on the axis rather than at the floor", () => {
    const flareHeightKm = 53;
    expect(LADDER_MIN_KM).toBeLessThan(flareHeightKm);

    const layers = compositeProfile({
      point: { latitudeDeg: 0, longitudeDeg: 0 },
      time: new Date("2026-06-21T12:00:00Z"),
      stations: [station({ latitudeDeg: 1, longitudeDeg: 1, foF2Mhz: 9, foEMhz: 3, foF1Mhz: 4.5 })],
      xrayFluxWm2: 4.5e-3,
      modelFoF2Mhz: 7,
      modelHmF2Km: 300,
      dRegionEffectiveHeightKm: flareHeightKm,
      dRegionBetaPerKm: 0.55,
    }).layers;

    const dLayer = layers.find((layer) => layer.layer === "D")!;
    expect(dLayer.peakHeightKm).toBe(flareHeightKm);

    const geometry = ladderGeometry(layers);
    const drawn = geometry.bars.find((bar) => bar.layer === "D")!;
    const atFloor = ladderGeometry(layers.map((layer) =>
      layer.layer === "D" ? { ...layer, peakHeightKm: LADDER_MIN_KM } : layer))
      .bars.find((bar) => bar.layer === "D")!;
    // Drawn ABOVE the floor position on the page means a smaller y is wrong:
    // the floor is the bottom of the box, so a 53 km bar must be at the floor's
    // y only if 53 IS the floor. It is not, so the two must differ.
    expect(drawn.y).toBeLessThan(atFloor.y);
    // And it must still be below the E layer, which is the ordering the whole
    // picture rests on.
    const e = geometry.bars.find((bar) => bar.layer === "E")!;
    expect(drawn.y).toBeGreaterThan(e.y);
  });
});
