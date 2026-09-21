import indexMarkup from "../index.html?raw";
import viewSource from "../src/energy-chain-view.ts?raw";
import mainSource from "../src/main.ts?raw";
import globeSource from "../src/globe.ts?raw";
import { describe, expect, it } from "vitest";
import {
  CHAIN_LAYER_CHECKBOX,
  CHAIN_MANAGED_LAYERS,
  chainLength,
  chainLinks,
  chainVerdict,
  drawableXraySeries,
  radioBlackoutLevel,
  snapshotNote,
  standoffVerdict,
} from "../src/energy-chain";
import type { SpaceWeatherBundle } from "../src/types";
import type { StormDriverSample, StormIndices } from "../src/storm-indices";

/**
 * These exercise the exported rules the walkthrough actually calls. The panel
 * is a renderer over `chainLinks()`; nothing it says is decided in the DOM
 * module, so nothing here is a copy of production logic written for a test.
 */

const AT = new Date("2026-08-08T17:30:00Z");

function driver(overrides: Partial<StormDriverSample> = {}): StormDriverSample {
  return {
    validAt: "2026-08-08T17:29:00Z",
    observedAt: "2026-08-08T16:29:00Z",
    speedKps: 364.6,
    densityCm3: 22.78,
    bzGsmNt: -13.97,
    bxNt: -2.62,
    byNt: -2.32,
    btNt: 14.45,
    dynamicPressureNpa: 5.065,
    magneticPressureNpa: 0.08308,
    clockAngleDeg: 189.4,
    newellCoupling: 15108.7,
    subsolarStandoffRe: 7.195,
    flaringAlpha: 0.70418,
    ...overrides,
  };
}

const STORM: StormIndices = {
  kind: "geomagnetic-storm-indices",
  status: "model-and-observed",
  validAt: "2026-08-08T17:31:56Z",
  drivers: null,
  derived: {
    clockAngleDeg: 189.4,
    transverseImfNt: 14.161,
    newellCoupling: 15108.7,
    newellUnits: "(km/s)^(4/3) nT^(2/3), unnormalised as published",
    newellCitation: "Newell et al. (2007) JGR 112 A01206",
    newellCalibration: [
      { label: "very quiet", value: 0, representativeBzNt: 3 },
      { label: "quiet", value: 4773, representativeBzNt: -2 },
      { label: "moderate", value: 10123, representativeBzNt: -5 },
      { label: "storm", value: 27421, representativeBzNt: -15 },
    ],
    newellCalibrationNote: "A band scale of representative disturbed conditions.",
    epsilonGw: 1483.771,
    epsilonNote: "Historical context only.",
    boyleCpcpKv: 180.1,
    boyleSaturationKv: 250,
    boyleNote: "The Boyle regression is linear.",
    speedKps: 364.6,
  },
  dst: {
    modelled: {
      status: "model", label: "MODELLED Dst", source: "NOAA Geospace SWMF", url: "",
      cadenceMinutes: 1, latestNt: -87.28, latestAt: "2026-08-08T18:20:00Z",
      forwardLeadMinutes: 48.1,
      series: [{ at: "2026-08-08T17:30:00Z", dstNt: -80 }],
    },
    observed: {
      status: "observed", label: "OBSERVED Dst3", source: "USGS", url: "",
      cadenceMinutes: 1, latestNt: -29.34, latestAt: "2026-08-08T17:29:00Z",
      note: "Dst3 uses a USGS-only station set.",
      series: [
        { at: "2026-08-08T16:30:00Z", dstNt: -22 },
        { at: "2026-08-08T17:29:00Z", dstNt: -29.34 },
      ],
    },
    kyoto: {
      status: "observed", label: "Kyoto quicklook Dst", source: "WDC Kyoto", url: "",
      cadenceMinutes: 60, latestNt: -38, latestAt: "2026-08-08T16:00:00Z",
      citation: "doi:10.17593/14515-74000",
      statusNote: "Quicklook: for monitoring only.",
      series: [{ at: "2026-08-08T16:00:00Z", dstNt: -38 }],
    },
    separationNote: "Three series, three evidence classes, never merged.",
  },
  ringCurrent: {
    status: "model-derived",
    energyJoules: 1.14168e15,
    energySourceSeries: "usgs-dst3-observed",
    energyDstNt: -29.34,
    method: "Dessler-Parker-Sckopke.",
    joulesPerNt: 3.8918788723e13,
    dipoleExternalFieldEnergyJ: 7.8097e17,
    relation: "Reading Dst IS reading the ring current.",
    uncertainty: "Good to about a factor of two.",
    pressureCorrectedDst: { obrienMcPherronNt: -34.67, burtonNt: -44.89 },
    pressureCorrectionNote: "Two standard corrections, side by side.",
    compositionModel: "Fixed 80% H+ / 20% O+.",
    compositionReality: "O+ exceeds 50% in great storms.",
  },
  phase: {
    label: "main",
    rule: "Deterministic classification of the Dst trace.",
    reason: "Dst at or below -30 nT and still falling",
    minimumNt: -41,
    minimumAt: "2026-08-08T14:00:00Z",
    intensity: "weak",
  },
  limitations: ["The modelled series is a physics-model estimate."],
};

function bundle(overrides: Partial<SpaceWeatherBundle> = {}): SpaceWeatherBundle {
  return {
    schema: 1,
    sources: [],
    solarWind: { observedAt: "2026-08-08T17:25:00", sourceSpacecraft: "SOLAR1", speedKps: 364.6, densityCm3: 22.78, temperatureK: 188966, dynamicPressureNpa: 5.065, series: [] },
    imf: { observedAt: "2026-08-08T17:25:00", sourceSpacecraft: "SOLAR1", btNt: 14.45, bzGsmNt: -13.97, series: [] },
    geomagnetic: { observedAt: "2026-08-08T17:26:00", kp: 2, series: [] },
    xray: { observedAt: "2026-08-08T17:27:00Z", fluxWm2: 2.533e-7, class: "B2.5", series: [] },
    particles: { protonObservedAt: "", protonFlux: 0.19, protonEnergy: ">=10 MeV", electronObservedAt: "", electronFlux: 224.7, electronEnergy: ">=2 MeV" },
    ionosphere: { observedAt: "2026-08-08T17:05:00Z", status: "assimilated", gridDegrees: { lon: 5, lat: 2.5 }, tecRange: [1.2, 43.8], medianHmF2Km: 318, points: [] },
    aurora: { observedAt: "2026-08-08T17:21:00Z", forecastAt: "2026-08-08T18:33:00Z", status: "forecast", model: "NOAA OVATION 2020", maximumProbability: 65, points: [], caveat: "Model-derived aurora viewing probability." },
    magnetopause: {
      status: "model",
      model: "Shue et al. (1998) empirical magnetopause boundary",
      subsolarStandoffRe: 7.2,
      flaringAlpha: 0.7042,
      caveat: "An axisymmetric empirical boundary.",
      driverSeries: [driver({ validAt: "2026-08-06T18:00:00Z", subsolarStandoffRe: 14.112, bzGsmNt: -1.37 }), driver()],
      cuspedBoundaries: {
        status: "empirical",
        note: "The Shue surface has no cusps by construction.",
        exteriorCusp: "The gap between them is the exterior cusp.",
        models: [
          { id: "nguyen2022", label: "Nguyen et al. (2022) Model 3", surface: "magnetopause current sheet", doi: "10.1029/2021JA029776", fittedTo: "17,230 magnetopause crossings", drivers: ["dynamicPressureNpa", "clockAngleDeg"] },
          { id: "lin2010", label: "Lin et al. (2010)", surface: "cusp inner boundary (the funnel wall)", doi: "10.1029/2009JA014235", fittedTo: "1,482 magnetopause crossings", drivers: ["dynamicPressureNpa", "bzGsmNt"] },
        ],
      },
    },
    storm: STORM,
    ...overrides,
  };
}

describe("the chain is seven links and the photon branch is not in it", () => {
  it("returns every link even when nothing has loaded", () => {
    const links = chainLinks({ weather: null, at: AT });
    expect(links).toHaveLength(9);
    // A link with no data still has to be able to say it has no data.
    expect(links.every((link) => link.missing !== null || link.readings.length > 0)).toBe(true);
  });

  it("numbers the chain 01 to 07 and the photon path as a branch beside it", () => {
    const links = chainLinks({ weather: bundle(), at: AT });
    expect(links.slice(0, 7).map((link) => link.index)).toEqual(["01", "02", "03", "04", "05", "06", "07"]);
    expect(links.slice(0, 7).every((link) => link.partOfChain)).toBe(true);
    // Two branch cards, not one. They make two separate claims - light is not
    // deflected, and where it lands the HF band closes - and one card carrying
    // both ran 871 px past the bottom of the panel at 1440x900.
    const [contrast, consequence] = links.slice(7);
    expect(contrast!.id).toBe("xray");
    expect(contrast!.index).toBe("X1");
    expect(contrast!.partOfChain).toBe(false);
    expect(consequence!.id).toBe("dregion");
    expect(consequence!.index).toBe("X2");
    expect(consequence!.partOfChain).toBe(false);
    // The whole reason the branch exists on this site.
    expect(contrast!.what).toContain("eight minutes");
    expect(contrast!.what).toContain("not deflected");
  });

  /**
   * The counter counts the CHAIN. The branch used to be numbered "8 of 8" by a
   * card whose own first line read "not part of the chain", which is a
   * contradiction a reader has no way to settle, and adding the second branch
   * card would have made it "9 of 9".
   */
  it("counts only the chain, so the branch is never numbered into it", () => {
    const links = chainLinks({ weather: bundle(), at: AT });
    expect(chainLength(links)).toBe(7);
  });

  it("gives every link a limit, because a step with no stated limit is a claim", () => {
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      expect(link.limit.length, `${link.id} has no stated limit`).toBeGreaterThan(20);
    }
  });

  /**
   * Sean: each step "needs to look good and show what it intends to show".
   * Half the failures were not the picture but the missing caption. The
   * ring-current step drives the PLASMASPHERE, because one number has no map,
   * and a reader who is not told that is looking at a cloud and calling it the
   * ring current. Every step now names what is drawn, including the steps
   * where the honest answer is that the subject itself is not.
   */
  it("names what is actually on the globe, on every step without exception", () => {
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      expect(link.onTheGlobe.length, `${link.id} does not say what the reader is looking at`).toBeGreaterThan(40);
    }
    const ring = chainLinks({ weather: bundle(), at: AT })[3]!;
    expect(ring.onTheGlobe).toContain("Not the ring current");
    expect(ring.onTheGlobe).toContain("plasmasphere");
  });

  it("hands off from each link to the next, and stops at the end of the chain", () => {
    const links = chainLinks({ weather: bundle(), at: AT });
    for (const link of links.slice(0, 6)) {
      expect(link.handoff, `${link.id} does not say what it does to the next link`).toBeTruthy();
    }
    // The ground is where the chain ends.
    expect(links[6]!.handoff).toBeNull();
    // The branch's first card hands off to its second - the photons land, and
    // the D region is what happens where they do - and the second ends it.
    expect(links[7]!.handoff).toBeTruthy();
    expect(links[8]!.handoff).toBeNull();
  });
});

/**
 * What the photon branch is FOR, now that it is not a rail layer.
 *
 * Sean, on the retired layer: "for xray flux, I really don't know what to
 * show... I don't know if it is useful." The number was never the problem -
 * it is a data product and it lives on Current conditions with a sparkline.
 * The globe visual is a CONTRAST, and a contrast needs both halves in frame:
 * the charged wind turned aside at the boundary, and the uncharged light going
 * straight through it. Drawn on its own, at ordinary quiet-Sun flux, it is a
 * near-transparent tint and some streaks - which is exactly what he reported
 * seeing. These assertions are what keep the step from decaying back into that.
 */
describe("the photon branch shows a contrast rather than a scalar", () => {
  it("puts the wind and the boundary on beside the beam, because that IS the lesson", () => {
    const branch = chainLinks({ weather: bundle(), at: AT })[7]!;
    expect(branch.layersOn).toContain("photons");
    expect(branch.layersOn).toContain("solarWind");
    expect(branch.layersOn).toContain("magnetosphere");
  });

  it("frames the Sun to one side, so the beam is seen crossing the boundary", () => {
    // The reset camera put the terminator on the limb and the dayside facing
    // away: a picture of the night side, on the card about what the Sun does
    // to the day side.
    expect(chainLinks({ weather: bundle(), at: AT })[7]!.camera).toBe("sun-earth");
  });

  it("says outright that nothing deflects it, which is the fact the picture carries", () => {
    const branch = chainLinks({ weather: bundle(), at: AT })[7]!;
    const deflection = branch.readings.find((reading) => reading.label === "Deflected by the magnetosphere");
    expect(deflection?.value).toBe("not at all");
    expect(deflection?.note).toContain("carry no charge");
  });

  it("sends the reader to the trace rather than pretending it can draw one", () => {
    // The published 7-day series rounds to five decimals and background flux
    // is of order 1e-7, so every value quantises to zero. The card says so and
    // names where the real trace is, instead of drawing a rounding rule.
    const branch = chainLinks({ weather: bundle(), at: AT })[7]!;
    expect(branch.limit).toContain("Current conditions");
  });
});

/**
 * Sean's screenshot of his first click on "Follow the energy" was "sad": a
 * fresh page load, the rail link, and the reader landed on a tiny Earth and a
 * handful of tracer dots lost in a mostly empty frame. The cause was the
 * camera, not the content — `focusSunEarthSideView()` in `globe.ts` always
 * pulls back far enough to hold the whole magnetotail (nose to tail) so a
 * later step's boundary is never cropped, and step 01 was drawing nothing
 * for that pullback to frame. These two assertions are what stand between a
 * regression and that screenshot happening again: the fix is that step 01
 * itself draws the boundary the wide camera is already composing for.
 */
describe("the first frame a fresh visitor sees", () => {
  it("frames the switch against the boundary it is about to cross, not an empty scene", () => {
    const [first] = chainLinks({ weather: bundle(), at: AT });
    expect(first!.id).toBe("driver");
    expect(first!.camera).toBe("sun-earth");
    expect(first!.layersOn).toContain("solarWind");
    // The boundary is a client-side Shue evaluation of the same driver sample
    // this step already reads — no extra fetch, so it costs nothing to draw
    // from the very first frame, and it is what fills the wide establishing
    // shot the sun-earth camera always composes.
    expect(first!.layersOn).toContain("magnetosphere");
  });

  it("still switches on only that, even with nothing loaded", () => {
    // The camera and layer choice for step 01 cannot depend on the bundle
    // having arrived, because the walkthrough opens `applyStep()` before its
    // own fetch is guaranteed to have resolved.
    const [first] = chainLinks({ weather: null, at: AT });
    expect(first!.camera).toBe("sun-earth");
    expect(first!.layersOn).toEqual(["solarWind", "magnetosphere"]);
  });
});

describe("the live numbers", () => {
  it("leads the first link with the sign of Bz, because that is the switch", () => {
    const [driverLink] = chainLinks({ weather: bundle(), at: AT });
    const bz = driverLink!.readings[0]!;
    expect(bz.label).toBe("IMF Bz (GSM)");
    expect(bz.value).toContain("-13.97");
    expect(bz.value).toContain("southward");
    expect(bz.evidence).toBe("observed");
  });

  it("says the switch is off, and still teaches, when Bz turns northward", () => {
    const quiet = bundle({
      magnetopause: {
        ...bundle().magnetopause,
        driverSeries: [driver({ bzGsmNt: 4.2, subsolarStandoffRe: 10.6, newellCoupling: 900 })],
      },
    });
    const [driverLink] = chainLinks({ weather: quiet, at: AT });
    expect(driverLink!.readings[0]!.value).toContain("northward");
    expect(driverLink!.handoff).toContain("gate is closed");
    const verdict = chainVerdict({ weather: quiet, at: AT });
    expect(verdict.state).toBe("relaxing");
    // "Walk the links anyway" is true once, at the top of the walk. It used to
    // live in `detail`, which the panel reprints above every card - so link 06
    // invited a reader who had already walked five of them to start. It is its
    // own field now and the view shows it on the first step only.
    expect(verdict.invitation).toContain("Walk the links anyway");
    expect(verdict.detail).not.toContain("Walk the links anyway");
  });

  it("carries the L1 travel time, so the reader knows what they are looking at is an hour old", () => {
    const [driverLink] = chainLinks({ weather: bundle(), at: AT });
    const travel = driverLink!.readings.find((reading) => reading.label === "L1 to Earth");
    expect(travel?.value).toBe("60 min");
  });

  it("measures the boundary against the nominal and against geostationary orbit", () => {
    const [, boundary] = chainLinks({ weather: bundle(), at: AT });
    const standoff = boundary!.readings.find((reading) => reading.label === "Subsolar standoff");
    expect(standoff?.value).toBe("7.20 R⊕");
    expect(standoff?.note).toContain("closer than the nominal");
    expect(boundary!.readings.some((reading) => reading.label === "Range over the published 48 h")).toBe(true);
  });

  it("reads Dst as the ring current rather than as a correlate of it", () => {
    const ring = chainLinks({ weather: bundle(), at: AT })[3]!;
    expect(ring.handoff).toContain("Reading Dst IS reading the ring current");
    expect(ring.readings.some((reading) => reading.label === "Ring-current energy")).toBe(true);
    expect(ring.limit).toContain("factor of two");
  });

  it("never merges the three Dst traces, and labels the modelled one as a model", () => {
    const ring = chainLinks({ weather: bundle(), at: AT })[3]!;
    const modelled = ring.readings.find((reading) => reading.label === "Modelled Dst (SWMF)");
    const observed = ring.readings.find((reading) => reading.label === "OBSERVED Dst3");
    expect(modelled?.evidence).toBe("model");
    expect(observed?.evidence).toBe("observed");
  });
});

describe("refusing to draw what is not published", () => {
  it("says so rather than inventing a cusp when the release has no cusped boundaries", () => {
    const older = bundle();
    delete (older.magnetopause as { cuspedBoundaries?: unknown }).cuspedBoundaries;
    const cusp = chainLinks({ weather: older, at: AT })[2]!;
    expect(cusp.missing).toContain("no cusped boundary models");
    expect(cusp.readings).toEqual([]);
  });

  it("refuses a driver sample from outside its tolerance instead of holding the last one", () => {
    const links = chainLinks({ weather: bundle(), at: new Date("2026-08-09T12:00:00Z") });
    expect(links[0]!.missing).toContain("No propagated solar-wind sample");
    expect(links[1]!.missing).toContain("no driver sample");
  });

  it("names the layers that are not built, rather than leaving the reader to wonder", () => {
    const links = chainLinks({ weather: bundle(), at: AT });
    const absent = links.flatMap((link) => link.layersNotBuilt.map((entry) => entry.label));
    // The bow shock used to be an honest absence on these cards and is drawn
    // now, from the published NOAA cuts via the coupled-structures layer, so
    // the card must no longer confess to a gap that closed.
    expect(absent).not.toContain("Bow shock surface");
    expect(absent).not.toContain("Ring current");
    // The obstacle step shows the shock where it lives now: as a colour jump
    // in the plasma-field layer, not as the retired curves-as-a-layer set.
    expect(links[1]!.layersOn).toContain("geospace");
    // The ring current has no layer to switch on and never will: the DPS
    // relation yields one number, the trace on this very card IS that number
    // over time, and the torus that used to stand in for it has been deleted.
    // The step must therefore drive the plasmasphere and nothing else, or the
    // walkthrough would be reaching for a checkbox the rail no longer has.
    expect(links[3]!.layersOn).toEqual(["ringCurrent"]);
    expect(links[3]!.limit).toContain("removed");
    expect(links[3]!.series?.unit).toBe("nT");
    // Without a cusp control on the page, the cusp step still refuses to let
    // the reader believe the shape beside its numbers is the one they
    // describe; the probe finding `data-magnetopause-surface="cusped"` on the
    // live page is what clears it.
    expect(absent).toContain("The cusped surfaces");
    const drawn = chainLinks({ weather: bundle(), at: AT, cuspLayerDrawn: true })[2]!;
    expect(drawn.layersNotBuilt).toEqual([]);
    // The neutral density used to be listed here as the thing that actually
    // drags a spacecraft and was not published. It is published and drawn now,
    // so the chain must NOT still be telling a reader it is missing: a
    // limitation that has been lifted is simply a false claim, and this is the
    // one a reader would check the globe against.
    expect(absent).not.toContain("Neutral thermosphere density");
    expect(CHAIN_MANAGED_LAYERS).toContain("thermosphere");
  });

  it("says which of its numbers do not follow the timeline", () => {
    // A reader scrubbing to yesterday still sees the aurora oval and the TEC
    // surface move, because those have archives — but the headline numbers in
    // this bundle are the newest sample and nothing else.
    const yesterday = new Date("2026-08-07T10:00:00Z");
    const links = chainLinks({ weather: bundle(), at: yesterday });
    const aurora = links[5]!;
    const ground = links[6]!;
    const branch = links[7]!;
    expect(aurora.timeNote).toContain("2026-08-07 10:00 UTC");
    expect(aurora.timeNote).toContain("does follow the timeline");
    expect(ground.timeNote).toContain("GloTEC headline");
    expect(branch.timeNote).toContain("rounded to zero");
    // The links that do resolve at the selected time never carry the caution.
    expect(links[0]!.timeNote).toBeNull();
    expect(links[3]!.timeNote).toBeNull();
  });

  it("stays quiet about the timeline when the snapshot is the selected time", () => {
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      expect(link.timeNote, `${link.id} warns about a drift that is not there`).toBeNull();
    }
    expect(snapshotNote(AT, "2026-08-08T17:21:00Z", "x", "y")).toBeNull();
    // An hour and a half out is a scrub, not a publish lag.
    expect(snapshotNote(AT, "2026-08-08T15:00:00Z", "the aurora headline", "y")).toContain("the aurora headline");
    expect(snapshotNote(AT, null, "x", "y")).toBeNull();
    expect(snapshotNote(AT, "nonsense", "x", "y")).toBeNull();
  });

  it("drops the X-ray trace when the publisher has rounded it to zero", () => {
    // The live defect: build_release.py rounds series to five decimals and the
    // flux is of order 1e-7, so every published value is exactly 0.0.
    const flat = Array.from({ length: 12 }, (_unused, index) => ({ time: `2026-08-08T0${index % 10}:00:00Z`, value: 0 }));
    expect(drawableXraySeries(flat)).toBeNull();
    const branch = chainLinks({ weather: bundle({ xray: { ...bundle().xray, series: flat } }), at: AT })[7]!;
    expect(branch.series).toBeNull();
    expect(branch.readings.some((reading) => reading.value === "not drawable from this release")).toBe(true);
  });

  it("draws the X-ray trace again the moment the values rise above the rounding floor", () => {
    const real = [
      { time: "2026-08-08T16:00:00Z", value: 2.5e-7 },
      { time: "2026-08-08T16:05:00Z", value: 4.1e-5 },
      { time: "2026-08-08T16:10:00Z", value: 0 },
    ];
    const series = drawableXraySeries(real);
    expect(series?.points).toHaveLength(3);
    // The zero is a hole, not a data point: log10(0) is not a number.
    expect(series?.points[2]!.value).toBeNull();
  });
});

describe("the scales that translate a number into an operational fact", () => {
  it("reports no radio blackout below M1, which is most of the time", () => {
    expect(radioBlackoutLevel(2.533e-7)).toEqual({ level: 0, label: "none" });
    expect(radioBlackoutLevel(null)).toEqual({ level: 0, label: "none" });
  });

  it("uses NOAA's published R thresholds, not one decade per step", () => {
    expect(radioBlackoutLevel(1e-5).level).toBe(1);
    expect(radioBlackoutLevel(5e-5).level).toBe(2);
    expect(radioBlackoutLevel(1e-4).level).toBe(3);
    expect(radioBlackoutLevel(1e-3).level).toBe(4);
    expect(radioBlackoutLevel(2e-3).level).toBe(5);
  });

  it("reads a nominal boundary as nominal rather than as a failure to be compressed", () => {
    expect(standoffVerdict(10.4)).toContain("about the nominal");
    expect(standoffVerdict(7.2)).toContain("closer than the nominal");
    expect(standoffVerdict(6.1)).toContain("inside geostationary orbit");
    expect(standoffVerdict(13.9)).toContain("further out");
    expect(standoffVerdict(null)).toBeNull();
  });
});

describe("what the walkthrough is allowed to touch", () => {
  it("only drives layers that exist in the page", () => {
    for (const key of CHAIN_MANAGED_LAYERS) {
      const id = CHAIN_LAYER_CHECKBOX[key];
      expect(id, `${key} has no checkbox id`).toBeTruthy();
      expect(indexMarkup, `index.html has no #${id}`).toContain(`id="${id}"`);
    }
  });

  it("never asks for a layer it has not declared as managed", () => {
    const managed = new Set(CHAIN_MANAGED_LAYERS);
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      for (const layer of link.layersOn) expect(managed.has(layer), `${link.id} wants unmanaged ${layer}`).toBe(true);
    }
  });

  it("shows one interaction at a time: no step turns on more than three layers", () => {
    // Two was the cap when every step showed one object against one context.
    // The obstacle step now shows the interaction itself — wind, boundary and
    // shock are three parts of one picture and hiding any of them re-breaks
    // the lesson — so the cap is three, and it is still a cap.
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      expect(link.layersOn.length, `${link.id} switches on ${link.layersOn.length} layers`).toBeLessThanOrEqual(3);
    }
  });
});

/**
 * Three times in this project a feature has been built, tested and merged
 * while no application entry point referenced it, so it was never on the site.
 * The walkthrough deliberately has its own `<script type="module">` rather
 * than a mount inside `src/main.ts`, and these assertions are what prove that
 * line is still there.
 */
/**
 * The design rules the redesign of 2026-08-19 rests on.
 *
 * Sean sent this feature back twice in two sentences: "each step in it needs
 * to look good and show what it intends to show", and "the Follow the Energy
 * card is quite busy and hard to follow. It needs a design eye to look at it."
 * Every assertion below pins a specific measured cause of one of those, so a
 * later change that reintroduces it fails here rather than in a screenshot.
 */
describe("a step shows what it intends to show", () => {
  it("draws the boundary's one number on an axis, not only as a printed value", () => {
    // "9.64 R-earth" means nothing to a reader who does not already carry 6.6
    // and 10-11 in their head. Geostationary orbit and the nominal quiet
    // standoff go on the same line as the live value, and nothing on the axis
    // is a number the card does not also state.
    const boundary = chainLinks({ weather: bundle(), at: AT })[1]!;
    const scale = boundary.scale;
    expect(scale).not.toBeNull();
    expect(scale!.live?.at).toBeCloseTo(7.195, 3);
    expect(scale!.marks.map((mark) => mark.at)).toContain(6.6);
    expect(scale!.band).toEqual({ from: 10, to: 11, label: "nominal" });
    // The evidence class travels with the drawing. A Shue evaluation drawn as
    // a clean axis must not read as a measured position.
    expect(scale!.evidence).toBe("empirical");
  });

  it("refuses to draw the axis when there is no live value for it", () => {
    const boundary = chainLinks({ weather: bundle(), at: new Date("2026-08-09T12:00:00Z") })[1]!;
    expect(boundary.scale).toBeNull();
  });

  it("gives the belts step a measured number, not three rows of release metadata", () => {
    // Before this, link 05 carried "Model", "Published coverage" and "Selected
    // time" and not one quantity a reader could act on - the first of them
    // labelled MODEL with a MODEL badge beside it. GOES counts electrons at
    // geostationary orbit and this site already publishes that count, so the
    // step shows what one spacecraft measures beside what the coupled run
    // models everywhere, which is the honest shape of the whole subject.
    const belts = chainLinks({ weather: bundle(), at: AT })[4]!;
    const measured = belts.readings.find((reading) => reading.evidence === "observed");
    expect(measured, "the belts step has no measured reading at all").toBeTruthy();
    expect(measured!.label).toContain("GOES electron flux");
    expect(measured!.note).toContain("1,000");
    // A point measurement is not the belt, and the card has to say so.
    expect(measured!.note).toContain("one place");
  });

  it("looks at the cusp edge-on, because a fold into a dome is invisible from outside it", () => {
    // Three presentations were photographed at 1440x900 on the live build
    // before this was settled: the polar camera hides the fold behind the
    // boundary's own near wall; the surfaces cut open on the meridian are
    // hairlines and came out as two thin arcs in an empty frame; the closed
    // shell edge-on fills the frame and its silhouette carries the dent.
    const cusp = chainLinks({ weather: bundle(), at: AT })[2]!;
    expect(cusp.camera).toBe("cross-section");
    // The wind, because it is the plasma the funnel admits, arriving into it
    // in the same frame.
    expect(cusp.layersOn).toContain("solarWind");
    expect(cusp.onTheGlobe).toContain("edge-on");
  });

  it("looks down the pole at the oval, because an oval seen edge-on is an arc", () => {
    expect(chainLinks({ weather: bundle(), at: AT })[5]!.camera).toBe("polar");
  });

  it("never prints a pipeline field name at a reader", () => {
    // The cusp card was published reading "Driven here by dynamicPressureNpa,
    // magneticPressureNpa". Every driver identifier the artifact carries is
    // translated; one without a translation falls through unchanged, so a new
    // driver in a future release is ugly here rather than invisible.
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      for (const reading of link.readings) {
        const text = `${reading.label} ${reading.value} ${reading.note ?? ""}`;
        expect(text, `${link.id} leaks a field name`).not.toMatch(/[a-z]+(Npa|Kps|Cm3|GsmNt|Deg|Re)\b/);
      }
    }
  });

  it("sets a value that is a word apart from a value that is a number", () => {
    // Both were going into the readout face - monospace, tabular, cyan - and
    // "magnetopause current sheet" set that way reads as a measurement whose
    // units have gone missing. See --type-answer in styles.css.
    const cusp = chainLinks({ weather: bundle(), at: AT })[2]!;
    const surface = cusp.readings.find((reading) => reading.value.includes("current sheet"));
    expect(surface?.kind).toBe("name");
    const boundary = chainLinks({ weather: bundle(), at: AT })[1]!;
    const standoff = boundary.readings.find((reading) => reading.label === "Subsolar standoff");
    expect(standoff?.kind).toBeUndefined();
  });

  it("keeps the one idea short enough to be read before anything else", () => {
    // Link 04's `what` ran six sentences and 1,518 px past the bottom of the
    // panel: the reader saw one sixth of the card and never reached the Dst
    // trace, which IS the ring current. Two of those sentences were about
    // what the globe is drawing and now have their own place to be said.
    for (const link of chainLinks({ weather: bundle(), at: AT })) {
      expect(link.what.length, `${link.id} opens with a wall of text`).toBeLessThan(420);
    }
  });
});

describe("the walkthrough is actually wired into the page", () => {
  it("is loaded by index.html as its own entry point", () => {
    expect(indexMarkup).toContain('<script type="module" src="/src/energy-chain-view.ts">');
  });

  it("drives the explorer only through controls index.html really has", () => {
    for (const id of ["sun-earth-view", "reset-view", "time-slider", "data-status", "scene"]) {
      expect(viewSource, `the walkthrough never reaches for #${id}`).toContain(`"${id}"`);
      expect(indexMarkup, `index.html has no #${id}`).toContain(`id="${id}"`);
    }
    expect(indexMarkup).toContain('data-mode-panel="environment"');
    // NOT `data-explorer-mode="environment"`. The walkthrough used to click that
    // button on the way in, so this suite made the page own one; the mode was
    // retired on 2026-08-28 and the click went with it. Asserting the button is
    // ABSENT is what keeps the two from drifting back apart — a reintroduced
    // click on a control index.html does not have is exactly what this
    // describe block exists to catch.
    expect(indexMarkup).not.toContain("data-explorer-mode");
    // Comments are stripped: this module's tombstone quotes the selector it no
    // longer clicks, and an assertion a comment can satisfy passes both ways.
    expect(viewSource.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")).not.toContain("data-explorer-mode");
    expect(indexMarkup).toContain('data-view="learn-weather"');
  });

  it("puts the reader's own layers back when it closes", () => {
    expect(viewSource).toContain("restoreLayers");
    expect(viewSource).toContain("restoreOffsetMinutes");
    // The boundary presentation is not a managed layer, so it does not come
    // back with them unless the close path says so - at the reader's value,
    // not the walkthrough's.
    expect(viewSource).toContain("restoreMagnetopauseCut");
    expect(viewSource).toContain('this.setSetting("magnetopause-cut", this.restoreMagnetopauseCut)');
  });

  /**
   * The camera the step asks for has to survive the explorer's own
   * housekeeping. `globe.ts` calls `frameActiveLayers()` when the geospace
   * bundle finishes arriving - its comment says so outright - and that bundle
   * is 2.7 MB, so a single command issued at +60 ms was thrown away. Measured
   * at 1440x900: link 02 asks for the meridional cross-section and was
   * photographed in the oblique magnetosphere frame in every one of six runs,
   * so the card that teaches from a face-on cut never showed one.
   */
  it("holds its camera against the layer bundle that lands seconds later", () => {
    expect(viewSource).toContain("cameraTimers");
    // Immediately, and then repeatedly for several seconds. One beat is what
    // failed; how many there are is tuning, but the last of them has to be
    // late enough to outlast a 2.7 MB fetch on a loaded machine.
    const schedule = viewSource.match(/this\.cameraTimers = \[([\d, ]+)\]/)?.[1];
    expect(schedule, "the camera is no longer re-asserted on a schedule").toBeTruthy();
    const beats = schedule!.split(",").map((beat) => Number(beat.trim()));
    expect(beats[0]).toBeLessThanOrEqual(100);
    expect(beats.length).toBeGreaterThanOrEqual(4);
    expect(Math.max(...beats)).toBeGreaterThanOrEqual(6000);
    // And gives it up the instant the reader touches the scene.
    expect(viewSource).toContain("readerMovedCamera");
  });

  /**
   * Sean: "for magnetosphere - the follow the energy link placement doesn't
   * make sense in the rail. perhaps we have that in the card somewhere?"
   * Loose between two layer rows the launcher belonged to nothing, and which
   * layer it appeared to belong to changed with the preset. The magnetosphere
   * layer is the right owner because it is the only layer on this site whose
   * subject is the COUPLING rather than one field: links 02 to 05 are all
   * views of it.
   */
  it("opens from the magnetosphere's DATA-EXPLORER card, not from the rail at any nesting", () => {
    // Sean asked for this twice. First: "the follow the energy link placement
    // doesn't make sense in the rail. perhaps we have that in the card
    // somewhere?" That was read as "put it inside the magnetosphere's rail
    // ROW", which is still the rail, and he said so again in blunter terms.
    //
    // The rail is a control surface — switches for fields drawn over the globe
    // — and a guided walkthrough is not a switch. The card is where a reader
    // has already chosen that layer and is reading about it, which is the
    // moment the offer means anything.
    expect(viewSource).toContain("chain-walk__launch--card");
    expect(viewSource).toContain("#data-viewer-cards");
    // The card is built when the layer comes on, so the mount waits for it.
    expect(viewSource).toContain("MutationObserver");
    // And the old fallback that put the button back in the rail is gone: a
    // wrong home that ships is worse than a door that appears a moment later.
    expect(viewSource).not.toContain('[data-layer-block="geospace"]');
  });

  /**
   * The X-ray visual lost its standing rail row on 2026-08-19 and became the
   * branch card. The control it is driven by stays in the document, hidden -
   * the arrangement `layer-regions` already uses - because `applyLayerPreset`
   * in main.ts calls `byId` on every entry of its checkbox map and a missing
   * element throws on load. That exact bug shipped when the plasma sheet was
   * retired.
   */
  it("keeps a control for the retired X-ray layer, so the walkthrough can still drive it", () => {
    expect(indexMarkup).toContain('<input type="checkbox" id="layer-photons" hidden />');
    // Gone from the visible list, and gone from every preset.
    expect(indexMarkup).not.toContain('data-layer-block="photons"');
    expect(mainSource).toContain('"layer-photons": "photons"');
    expect(mainSource).toContain('photons: "layer-photons"');
    expect(mainSource).not.toMatch(/standard: \[[^\]]*"photons"/);
    expect(mainSource).not.toMatch(/full: \[[^\]]*"photons"/);
    // The D-region layer's flare response reads the measured flux directly and
    // must not have been wired through the retired layer's visibility.
    expect(globeSource).toContain("this.dRegionEmpirical.setXrayFlux(fluxWm2)");
  });
});
