import indexMarkup from "../index.html?raw";
import contentSource from "../src/content.ts?raw";
import { describe, expect, it } from "vitest";
import { keyCardBar, dataViewerSections, plasmaSheetLegendSpec } from "../src/main";
import type { PlasmaSheetSpecInput } from "../src/main";
import {
  PLASMA_SHEET_LIMITATION,
  PLASMA_SHEET_MEASUREMENT_WINDOW,
  PLASMA_SHEET_REPRESENTATION,
} from "../src/plasma-sheet";
import type {
  GeospaceRuntimeReadyState,
  PlasmaSheetLegendMetadata,
} from "../src/geospace-runtime";

/**
 * "Shape only is the worst part of this." — the same acceptance criterion the
 * magnetosphere family already carries, applied to the layer added beside it.
 *
 * The plasma sheet is a FIELD: plasma beta over the published cut, on a ramp
 * whose pale band is beta = 1. So its key card must carry a real ramp in every
 * state it can be in — before the bundle loads, while it loads, on an archived
 * frame that publishes no plasma field, and outside the published window — and
 * it must never print a number the frame on screen did not yield.
 *
 * These tests drive `plasmaSheetLegendSpec`, `keyCardBar` and
 * `dataViewerSections`: the exact functions `environmentLegendSpec`,
 * `renderKeyCard` and `updateDataViewer` call.
 */

const formatEndpoint = (value: number, scale: "linear" | "log10") =>
  scale === "log10" ? `10^${value}` : String(value);

const readyState: GeospaceRuntimeReadyState = {
  status: "ready",
  requestedAt: "2026-08-11T14:25:00Z",
  sourceFrames: ["2026-08-11T14:20:00Z", "2026-08-11T14:40:00Z"],
  interpolationFraction: 0.25,
  structureFrameValidAt: "2026-08-11T14:20:00Z",
  runAt: "2026-08-11T12:19:00Z",
  leadMinutes: 121,
  edgeHoldMinutes: 0,
};

/** The numbers the real runtime measured from the published 14:20Z frame. */
function metadata(overrides: Partial<PlasmaSheetLegendMetadata> = {}): PlasmaSheetLegendMetadata {
  return {
    kind: "swmf-derived-plasma-beta",
    coordinateSystem: "GSM for MHD planes",
    betaPublished: true,
    plane: "meridional",
    displayMode: "smooth",
    logRange: [-3, 2],
    threshold: 1,
    units: "dimensionless",
    counts: {
      valid: 3904,
      missing: 16,
      sourceBounded: 949,
      displayClamped: 218,
      interpolated: 3904,
      aboveThreshold: 393,
    },
    metrics: {
      columnCount: 64,
      resolvedColumnCount: 64,
      peakBeta: 23.09,
      referenceXRe: -15,
      halfThicknessRe: 0.74,
      centreCrossRe: 3.25,
      referenceTruncated: false,
      centreRangeRe: [2.25, 3.75],
      equatorialCutInsideSheet: false,
      window: PLASMA_SHEET_MEASUREMENT_WINDOW,
    },
    metricsAvailable: true,
    representation: PLASMA_SHEET_REPRESENTATION,
    limitation: PLASMA_SHEET_LIMITATION,
    sourceFrames: ["2026-08-11T14:20:00Z", "2026-08-11T14:40:00Z"],
    validAt: "2026-08-11T14:20:00Z",
    ...overrides,
  };
}

function specInput(overrides: Partial<PlasmaSheetSpecInput> = {}): PlasmaSheetSpecInput {
  return {
    metadata: metadata(),
    runtimeState: readyState,
    loading: false,
    frameDescription: "RUN 12:19Z · VALID 14:20Z",
    source: "NOAA/NCEP NOMADS operational SWMF output · pressure ÷ magnetic pressure · GSM",
    coverage: "30 source frames",
    formatEndpoint,
    ...overrides,
  };
}

/** Every state the layer can be in, by name, so a failure names the state. */
const STATES: Record<string, PlasmaSheetSpecInput> = {
  "not loaded yet": specInput({ metadata: null, runtimeState: null, loading: false, frameDescription: null }),
  "loading": specInput({ metadata: null, runtimeState: null, loading: true, frameDescription: null }),
  "ready with the field": specInput(),
  "ready, equatorial cut": specInput({ metadata: metadata({ plane: "equatorial" }) }),
  "ready, both cuts": specInput({ metadata: metadata({ plane: "both" }) }),
  "ready, native grid": specInput({ metadata: metadata({ displayMode: "native", metrics: null, metricsAvailable: false }) }),
  "archived frame without pressure or |B|": specInput({
    metadata: metadata({ betaPublished: false, counts: null, metrics: null, metricsAvailable: false }),
  }),
  "no sheet resolved in the window": specInput({
    metadata: metadata({
      metrics: {
        columnCount: 64,
        resolvedColumnCount: 0,
        peakBeta: 0.4,
        referenceXRe: -15,
        halfThicknessRe: null,
        centreCrossRe: null,
        referenceTruncated: false,
        centreRangeRe: null,
        equatorialCutInsideSheet: null,
        window: PLASMA_SHEET_MEASUREMENT_WINDOW,
      },
    }),
  }),
  "no data for the selected time": specInput({
    runtimeState: {
      status: "no-data",
      requestedAt: "2026-08-05T00:00:00Z",
      reason: "before-coverage",
      coverage: { validFrom: "2026-08-09T16:00:00Z", validTo: "2026-08-11T16:00:00Z" },
    },
    frameDescription: "BEFORE COVERAGE",
  }),
};

describe("SHAPE ONLY is unreachable from the plasma-sheet layer", () => {
  it("gives the layer a real colour ramp in every state it can be in", () => {
    for (const [name, input] of Object.entries(STATES)) {
      const spec = plasmaSheetLegendSpec(input);
      expect(spec.scale, `state "${name}" lost its colour ramp`).toBeDefined();
      // Through the same decision renderKeyCard makes.
      const unavailable = spec.statusState === "no-data" || spec.statusState === "stale";
      expect(keyCardBar(spec, unavailable).kind, `state "${name}" fell back to the flat bar`).not.toBe("shape-only");
    }
  });

  it("names the quantity and where beta = 1 sits on the bar, in every state", () => {
    for (const [name, input] of Object.entries(STATES)) {
      const spec = plasmaSheetLegendSpec(input);
      expect(spec.scale!.label, `state "${name}" stopped naming the quantity`).toContain("PLASMA β");
      // Beta has no units, so the one thing the label owes the reader is the
      // position of the threshold. Losing it turns the bar into decoration.
      expect(spec.scale!.label, `state "${name}" stopped naming the threshold`).toContain("β = 1");
      expect(spec.scale!.minimum).toBe("10^-3");
      expect(spec.scale!.maximum).toBe("10^2");
    }
  });

  it("says which cut is drawn, because the answer changes what is on screen", () => {
    expect(plasmaSheetLegendSpec(STATES["ready with the field"]!).scale!.label).toContain("NOON–MIDNIGHT CUT");
    expect(plasmaSheetLegendSpec(STATES["ready, equatorial cut"]!).scale!.label).toContain("EQUATORIAL CUT");
    expect(plasmaSheetLegendSpec(STATES["ready, both cuts"]!).scale!.label).toContain("BOTH CUTS");
    expect(plasmaSheetLegendSpec(STATES["ready, native grid"]!).scale!.label).toContain("NATIVE GRID");
  });
});

describe("the card reports measurements, never assumptions", () => {
  const labels = (input: PlasmaSheetSpecInput) =>
    (plasmaSheetLegendSpec(input).stats ?? []).map((stat) => stat.label);
  const value = (input: PlasmaSheetSpecInput, label: string) =>
    (plasmaSheetLegendSpec(input).stats ?? []).find((stat) => stat.label === label)?.value;

  it("quotes the measured half-thickness at the stated distance, with its sign convention", () => {
    const input = STATES["ready with the field"]!;
    expect(labels(input)).toContain("HALF-THICKNESS AT X -15 R⊕");
    expect(value(input, "HALF-THICKNESS AT X -15 R⊕")).toBe("0.74 R⊕");
    expect(value(input, "SHEET CENTRE THERE")).toBe("Z +3.25 R⊕");
    expect(value(input, "PEAK β IN THE TAIL WINDOW")).toBe("23.1");
    expect(value(input, "TAIL COLUMNS RESOLVING β ≥ 1")).toBe("64 OF 64");
    // Both of those rows say "tail window", so the window itself must be on
    // the card: it is a choice this site made about where to measure, not a
    // region NOAA published, and a statistic over an unstated region is not a
    // statistic a reader can check.
    expect(value(input, "MEASURED TAIL WINDOW")).toBe("X -40 TO -8 R⊕ · |Z| ≤ 12 R⊕");
  });

  it("marks a thickness that ran off the measured window as a lower bound", () => {
    const truncated = specInput({
      metadata: metadata({
        metrics: { ...metadata().metrics!, referenceTruncated: true },
      }),
    });
    expect(value(truncated, "HALF-THICKNESS AT X -15 R⊕")).toContain("LOWER BOUND");
  });

  it("answers the equatorial-cut question out loud, both ways", () => {
    // The trap this layer exists to expose: with the dipole tilted, the z = 0
    // cut this site also publishes is in the LOBE, not the sheet. The card is
    // required to say which, because a reader who assumes wrongly is reading a
    // different region and would never know.
    expect(value(STATES["ready with the field"]!, "EQUATORIAL PLANE (Z = 0)")).toBe("IN THE LOBE, NOT THE SHEET");
    const through = specInput({
      metadata: metadata({ metrics: { ...metadata().metrics!, equatorialCutInsideSheet: true } }),
    });
    expect(value(through, "EQUATORIAL PLANE (Z = 0)")).toBe("INSIDE THE β ≥ 1 SHEET");
  });

  it("prints the count of cells whose beta is only a bound", () => {
    // 949 of the 3,904 drawn cells rest on a source value that sat on its own
    // encoding endpoint. Dropping this row would let a bound pass as a value.
    expect(value(STATES["ready with the field"]!, "β BOUNDED BY A SOURCE LIMIT")).toBe("949");
    expect(value(STATES["ready with the field"]!, "β CELLS ABOVE 1")).toBe("393");
  });

  it("refuses instead of guessing when nothing in the window reaches beta = 1", () => {
    const input = STATES["no sheet resolved in the window"]!;
    expect(value(input, "SHEET MEASUREMENT")).toBe("NO β ≥ 1 COLUMN IN THE MEASURED TAIL WINDOW");
    expect(labels(input)).not.toContain("HALF-THICKNESS AT X -15 R⊕");
  });

  it("says the measurement needs the smoothed grid rather than faking it on the native one", () => {
    expect(value(STATES["ready, native grid"]!, "SHEET MEASUREMENT")).toBe("NEEDS THE SMOOTHED DISPLAY GRID");
  });

  it("names the archived replay frame instead of printing zeros", () => {
    const input = STATES["archived frame without pressure or |B|"]!;
    const spec = plasmaSheetLegendSpec(input);
    expect(value(input, "PRESSURE & |B|")).toBe("NOT IN THIS ARCHIVED FRAME");
    expect(spec.statusText).toContain("ARCHIVED REPLAY FRAME");
    expect(labels(input)).not.toContain("β CELLS DRAWN");
  });

  it("hides everything and says so outside the published window", () => {
    const spec = plasmaSheetLegendSpec(STATES["no data for the selected time"]!);
    expect(spec.statusState).toBe("no-data");
    expect(spec.badge).toBe("NO DATA");
    expect(spec.statusText).toContain("no stale frame is held");
    expect((spec.stats ?? []).map((stat) => stat.label)).toContain("SELECTED UTC");
  });
});

describe("the note draws the honesty boundary the layer depends on", () => {
  const note = plasmaSheetLegendSpec(specInput()).note;

  it("carries the single-sourced caveat in EVERY state, not only when data arrived", () => {
    // The caveat is one exported string, shared with the runtime's metadata,
    // so it cannot drift — and it is printed even before the bundle loads,
    // because a reader can read the ramp before the first frame lands.
    for (const [name, input] of Object.entries(STATES)) {
      expect(plasmaSheetLegendSpec(input).note, `state "${name}" dropped the caveat`)
        .toContain(PLASMA_SHEET_LIMITATION);
      expect(plasmaSheetLegendSpec(input).note, `state "${name}" dropped the derivation`)
        .toContain(PLASMA_SHEET_REPRESENTATION);
    }
  });

  it("says beta = 1 is a convention rather than a published boundary", () => {
    expect(PLASMA_SHEET_LIMITATION).toContain("CONVENTIONAL");
    expect(PLASMA_SHEET_LIMITATION).toContain("not a boundary NOAA publishes");
    expect(PLASMA_SHEET_LIMITATION).toContain("rather than a measured crossing");
    expect(note).toContain("not a boundary NOAA publishes");
  });

  it("warns that the magnetosheath is high-beta too, so beta alone is not the sheet", () => {
    expect(note).toContain("magnetosheath");
    expect(note).toContain("BETWEEN the two lobes");
  });

  it("states the derivation in terms of the two published quantities only", () => {
    expect(PLASMA_SHEET_REPRESENTATION).toContain("thermal pressure / magnetic pressure");
    expect(PLASMA_SHEET_REPRESENTATION).toContain("No third quantity enters it");
  });

  it("explains what the two drawn curves are", () => {
    expect(note).toContain("β = 1 curve");
    expect(note).toContain("locus of maximum β");
    expect(note).toContain("NOT the z = 0 plane");
  });

  it("names the teaching consequence: this is what feeds the ring current and the aurora", () => {
    expect(note).toContain("ring current");
    expect(note).toContain("aurora");
    expect(note).toContain("LOBES");
  });
});

describe("the data viewer carries the same facts as the card", () => {
  it("splits the readings, the validity and the provenance, leaving the range to the legend", () => {
    const spec = plasmaSheetLegendSpec(specInput());
    const sections = dataViewerSections(spec);
    expect(sections.readings.map(([label]) => label)).toContain("HALF-THICKNESS AT X -15 R⊕");
    // The units row moved out: the legend prints the ramp's label and ends,
    // and printing them here as well put the same value in two places on one
    // screen. The layer's OWN readings stay here.
    expect(sections.readings.map(([label]) => label)).not.toContain("Units");
    expect(keyCardBar(spec, false).endpoints[1]).toBe(spec.scale!.label);
    expect(sections.validity.map(([label]) => label)).toContain("Valid at");
    expect(sections.provenance.map(([, value]) => value)).toContain(
      "NOAA/NCEP NOMADS operational SWMF output · pressure ÷ magnetic pressure · GSM",
    );
  });
});

describe("the layer is off the main rail, and its teaching lives in Learn", () => {
  const railStart = indexMarkup.indexOf('id="layer-list"');
  // Ends at the advanced fold rather than at the NOAA card, which moved out
  // of this section into "Conditions right now" on 2026-08-19.
  const railEnd = indexMarkup.indexOf("advanced-environment-details");
  const rail = indexMarkup.slice(railStart, railEnd);

  it("is not a rail layer any more", () => {
    // Sean, twice: the cut plane is useless on the main page. "Unless you can
    // use it for a better visualization that is 3d and not a cross section it
    // is useless." It was a meridional slice through a 3D scene, sitting in the
    // rail beside layers that draw the whole globe, and it was in no preset -
    // so it never switched itself on and only ever added a row to read past.
    //
    // The physics did not go anywhere. It is a cut of the same NOAA geospace
    // field the magnetosphere layer draws, and that layer still draws it.
    expect(rail).not.toContain('id="layer-plasma-sheet"');
    expect(rail).not.toContain('data-layer-block="plasmaSheet"');
  });

  it("keeps every word of the explanation, on the Learn page", () => {
    // Retiring a visual must never quietly retire what it taught. These are the
    // sections that carry it, including the one whose whole subject is that the
    // sheet is NOT drawn - which is the honest statement about missing data
    // that this site is built on.
    expect(contentSource).toContain("Magnetotail and plasma sheet");
    expect(contentSource).toContain("The plasma sheet is not drawn");
  });

  it("still builds a legend spec, because the Learn page quotes it", () => {
    // The module stays reachable and tested; only the rail row is gone.
    expect(typeof plasmaSheetLegendSpec).toBe("function");
  });
});
