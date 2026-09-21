import indexMarkup from "../index.html?raw";
import { describe, expect, it } from "vitest";
import { keyCardBar, magnetosphereFieldLegendSpec, plasmaSheetLegendSpec } from "../src/main";
import type { MagnetosphereFieldSpecInput, PlasmaSheetSpecInput } from "../src/main";
import type {
  GeospaceFieldLegendMetadata,
  GeospaceRuntimeReadyState,
  GeospaceStructureLegendMetadata,
} from "../src/geospace-runtime";

/**
 * "Shape only is the worst part of this." — Sean, on the night every
 * magnetosphere layer was an outline with nothing inside it.
 *
 * The magnetosphere family is now one layer — the NOAA MHD plasma field —
 * plus off-by-default annotations that are settings of that layer, not layers.
 * The acceptance criterion is that the flat SHAPE ONLY key-card bar is
 * unreachable from this family: the field layer's spec must carry a real
 * colour ramp with units in EVERY state it can be in, and the retired
 * curves-as-a-layer rows must not exist to produce a bar of their own.
 *
 * These tests drive `magnetosphereFieldLegendSpec` and `keyCardBar`, the
 * exact functions `environmentLegendSpec` and `renderKeyCard` call, per this
 * project's rule that a guard must fail on the real path.
 */

const formatEndpoint = (value: number, scale: "linear" | "log10") =>
  scale === "log10" ? `10^${value}` : String(value);

function fieldMetadata(overrides: Partial<GeospaceFieldLegendMetadata> = {}): GeospaceFieldLegendMetadata {
  return {
    kind: "swmf-cut",
    field: "speed",
    title: "Bulk plasma speed",
    coordinateSystem: "GSM",
    range: {
      scale: "linear",
      encodedMinimum: 0,
      encodedMaximum: 1000,
      physicalMinimum: 0,
      physicalMaximum: 1000,
      units: "km s⁻¹",
      endpointMeaning: "endpoints",
    },
    displayMode: "smooth",
    plane: "meridional",
    sourceFrames: ["2026-08-09T10:20:00Z"],
    validCount: 17000,
    missingCount: 600,
    clippedLowCount: 0,
    clippedHighCount: 4,
    interpolatedCount: 120,
    representation: "representation",
    fieldPublished: true,
    ...overrides,
  };
}

function structuresMetadata(): GeospaceStructureLegendMetadata {
  return {
    kind: "swmf-structure-proxies",
    coordinateSystem: "GSM",
    boundaryStatus: "model-derived-proxies",
    boundaryUnits: "Earth radii (R_E)",
    flowSpeedUnits: "km/s",
    flowSpeedRange: [40, 620],
    sheathThicknessRangeRe: [2.9, 8.4],
    subsolarBowShockRe: 14.75,
    subsolarMagnetopauseRe: 11.25,
    structureDisplay: "cross-section",
    representation: "representation",
    limitation: "limitation",
    validAt: "2026-08-09T10:20:00Z",
  };
}

const readyState: GeospaceRuntimeReadyState = {
  status: "ready",
  requestedAt: "2026-08-09T10:25:00Z",
  sourceFrames: ["2026-08-09T10:20:00Z", "2026-08-09T10:40:00Z"],
  interpolationFraction: 0.25,
  structureFrameValidAt: "2026-08-09T10:20:00Z",
  runAt: "2026-08-09T04:00:00Z",
  leadMinutes: 0,
  edgeHoldMinutes: 0,
};

/** A traced-field summary as the globe would report it under live drivers. */
const fieldLineSummary = {
  standoffRe: 10.4,
  tailFieldNt: 15,
  closedNoseXRe: 10.1,
  lastClosedNoonLatitudeDeg: 75.5,
  firstOpenMidnightLatitudeDeg: 77.5,
  closedCount: 98,
  openCount: 8,
  boundaryCount: 40,
  meanOpenTailReachXRe: -40,
};

function specInput(overrides: Partial<MagnetosphereFieldSpecInput> = {}): MagnetosphereFieldSpecInput {
  return {
    field: "speed",
    fieldMetadata: fieldMetadata(),
    structures: structuresMetadata(),
    runtimeState: readyState,
    loading: false,
    empiricalAnnotationOn: false,
    shueNoseRe: null,
    frameDescription: "RUN 04:00Z · VALID 10:20Z",
    source: "NOAA SWPC · GSM",
    coverage: "29 source frames",
    formatEndpoint,
    // The cut-on mode is what the pre-existing states below exercise; the
    // 3-D default mode has its own states added alongside them.
    mhdCutOn: true,
    fieldLineSummary,
    ...overrides,
  };
}

/** Every state the layer can be in, by name, so a failure names the state. */
const STATES: Record<string, MagnetosphereFieldSpecInput> = {
  "not loaded yet": specInput({ fieldMetadata: null, structures: null, runtimeState: null, loading: false, frameDescription: null }),
  "loading": specInput({ fieldMetadata: null, structures: null, runtimeState: null, loading: true, frameDescription: null }),
  "ready with the field": specInput(),
  "archived frame without the field": specInput({ fieldMetadata: fieldMetadata({ fieldPublished: false, validCount: 0 }) }),
  "no data for the selected time": specInput({
    fieldMetadata: fieldMetadata(),
    runtimeState: {
      status: "no-data",
      requestedAt: "2026-08-05T00:00:00Z",
      reason: "before-coverage",
      coverage: { validFrom: "2026-08-07T12:00:00Z", validTo: "2026-08-09T12:00:00Z" },
    },
    frameDescription: "BEFORE COVERAGE",
  }),
  "annotation on": specInput({ empiricalAnnotationOn: true, shueNoseRe: 9.6 }),
  // The layer's default face: the driven 3-D field lines, no MHD cut. The
  // ramp is the construction's own |B| along the traced lines.
  "3-D field lines with live drivers": specInput({ mhdCutOn: false }),
  "3-D field lines, drivers missing": specInput({ mhdCutOn: false, fieldLineSummary: null }),
  "3-D field lines before the bundle ever loads": specInput({
    mhdCutOn: false,
    fieldMetadata: null,
    structures: null,
    runtimeState: null,
  }),
};

describe("SHAPE ONLY is unreachable from the magnetosphere family", () => {
  it("gives the field layer a real colour ramp in every state it can be in", () => {
    for (const [name, input] of Object.entries(STATES)) {
      const spec = magnetosphereFieldLegendSpec(input);
      expect(spec.scale, `state "${name}" lost its colour ramp`).toBeDefined();
      // Through the same decision renderKeyCard makes. `unavailable` mirrors
      // layerUnavailable: only a no-data/stale statusState can trigger it,
      // and that renders the struck-out bar, never the flat one.
      const unavailable = spec.statusState === "no-data" || spec.statusState === "stale";
      expect(keyCardBar(spec, unavailable).kind, `state "${name}" fell back to the flat bar`).not.toBe("shape-only");
    }
  });

  it("keeps units on the ramp whenever the model has loaded", () => {
    const spec = magnetosphereFieldLegendSpec(specInput());
    expect(spec.scale!.label).toContain("km s⁻¹");
    expect(spec.scale!.minimum).toBe("0");
    expect(spec.scale!.maximum).toBe("1000");
  });

  it("covers the derived plasma-sheet layer too, in every state it can be in", () => {
    // The plasma sheet joined this family on 2026-08-11 as a layer of its own.
    // It is a field — plasma β over the same published cuts — so the same
    // acceptance criterion applies, and it is checked HERE as well as in
    // tests/plasma-sheet-legend.test.ts so that adding a magnetosphere-family
    // layer without a ramp fails the family's own guard.
    const base: PlasmaSheetSpecInput = {
      metadata: null,
      runtimeState: null,
      loading: false,
      frameDescription: null,
      formatEndpoint,
    };
    const states: PlasmaSheetSpecInput[] = [
      base,
      { ...base, loading: true },
      { ...base, runtimeState: readyState },
      {
        ...base,
        runtimeState: {
          status: "no-data",
          requestedAt: "2026-08-05T00:00:00Z",
          reason: "before-coverage",
          coverage: { validFrom: "2026-08-09T16:00:00Z", validTo: "2026-08-11T16:00:00Z" },
        },
      },
    ];
    states.forEach((input, index) => {
      const spec = plasmaSheetLegendSpec(input);
      expect(spec.scale, `plasma-sheet state ${index} lost its colour ramp`).toBeDefined();
      const unavailable = spec.statusState === "no-data" || spec.statusState === "stale";
      expect(keyCardBar(spec, unavailable).kind, `plasma-sheet state ${index} fell back to the flat bar`)
        .not.toBe("shape-only");
    });
  });

  it("still proves the flat bar exists for a genuinely scale-less layer, so this guard bites", () => {
    // Ground-station pins are categorical and legitimately shape-only. If this
    // ever stops returning "shape-only", the two tests above stop guarding.
    expect(keyCardBar({ scale: undefined }, false).kind).toBe("shape-only");
    expect(keyCardBar({ scale: undefined }, false).endpoints[1]).toBe("SHAPE ONLY");
  });

  it("carries the subsolar compression numbers whenever the run is ready", () => {
    const withField = magnetosphereFieldLegendSpec(specInput());
    const labels = (withField.stats ?? []).map((stat) => stat.label);
    expect(labels).toContain("BOW-SHOCK NOSE");
    expect(labels).toContain("MAGNETOPAUSE NOSE");
    // Including the archived frames, where those curves are the only
    // magnetosphere data published — the replay's compression story.
    const archived = magnetosphereFieldLegendSpec(specInput({ fieldMetadata: fieldMetadata({ fieldPublished: false, validCount: 0 }) }));
    const archivedLabels = (archived.stats ?? []).map((stat) => stat.label);
    expect(archivedLabels).toContain("BOW-SHOCK NOSE");
    expect(archived.statusText).toContain("ARCHIVED REPLAY FRAME");
  });

  it("names the empirical Shue nose only when that annotation is on", () => {
    const off = magnetosphereFieldLegendSpec(specInput());
    expect((off.stats ?? []).map((stat) => stat.label)).not.toContain("SHUE NOSE (EMPIRICAL)");
    const on = magnetosphereFieldLegendSpec(specInput({ empiricalAnnotationOn: true, shueNoseRe: 9.6 }));
    const stat = (on.stats ?? []).find((entry) => entry.label === "SHUE NOSE (EMPIRICAL)");
    expect(stat?.value).toBe("9.6 R⊕");
  });
});

describe("the field is the layer; every curve is an off-by-default setting", () => {
  const railStart = indexMarkup.indexOf('id="layer-list"');
  // Ends at the advanced fold rather than at the NOAA card, which moved out
  // of this section into "Conditions right now" on 2026-08-19.
  const railEnd = indexMarkup.indexOf("advanced-environment-details");
  const rail = indexMarkup.slice(railStart, railEnd);
  const panelsStart = indexMarkup.indexOf('id="layer-control-panels"');
  const panels = indexMarkup.slice(panelsStart, indexMarkup.indexOf('<template id="layer-card-template"'));

  it("has retired the curves-as-a-layer row entirely", () => {
    expect(indexMarkup).not.toContain("layer-coupled-structures");
    expect(indexMarkup).not.toContain("Bow shock, magnetosheath &amp; field lines");
  });

  it("puts the 3-D magnetosphere row in the rail as THE magnetosphere layer", () => {
    expect(rail).toContain('id="layer-geospace"');
    expect(rail).toContain("Magnetosphere");
  });

  it("legends the 3-D default with the construction's own quantity and drivers", () => {
    const spec = magnetosphereFieldLegendSpec(specInput({ mhdCutOn: false }));
    expect(spec.scale!.label).toContain("nT");
    expect(spec.scale!.label).toContain("DRIVEN FIELD MODEL");
    const labels = (spec.stats ?? []).map((stat) => stat.label);
    expect(labels).toContain("STANDOFF");
    expect(labels).toContain("OPEN ABOVE (MIDNIGHT)");
    // The boundary's provenance is named on the card in BOTH regimes: the
    // summary above carries no MHD calibration, so this is the L1 fallback…
    const boundary = (spec.stats ?? []).find((stat) => stat.label === "BOUNDARY");
    expect(boundary?.value).toBe("EMPIRICAL SHUE FROM L1");
    expect(spec.note).toContain("Chapman–Ferraro");
    expect(spec.note).toContain("Not an MHD solution");
    // …and the drawn-element key names each component. The plasma sheet is
    // still NOT part of this construction — a driven dipole-plus-Harris field
    // has no sheet in it — but since 2026-08-11 the site does show one, as its
    // own layer derived from the NOAA pressure and |B| cuts, so this note now
    // has to point at it rather than say the site cannot draw it.
    expect(spec.note).toContain("plasma sheet");
    expect(spec.note).toContain("not part of this construction");
    expect(spec.note).toContain("Plasma sheet & tail lobes");
    // The cusp/oval relationship is stated so the (correct) poleward offset
    // between the funnels and the OVATION oval is never mistaken for the
    // registration bug it once was: cusp ≈ 77–80° magnetic, oval ≈ 65–75°.
    expect(spec.note).toContain("POLEWARD of the oval");
    expect(spec.note).toContain("77–80°");
  });

  it("labels the boundary as MHD-calibrated, with its residual, when a frame drove it", () => {
    const spec = magnetosphereFieldLegendSpec(specInput({
      mhdCutOn: false,
      fieldLineSummary: {
        ...fieldLineSummary,
        boundarySource: "noaa-mhd-frame",
        calibration: {
          standoffRe: 10.6,
          flaringAlpha: 0.52,
          rmsResidualRe: 0.31,
          referenceRmsResidualRe: 0.87,
          noseResidualRe: -0.15,
          sampleCount: 56,
          frameValidAt: "2026-08-09T10:20:00Z",
          source: "noaa-mhd-frame",
        },
      },
    }));
    const boundary = (spec.stats ?? []).find((stat) => stat.label === "BOUNDARY");
    expect(boundary?.value).toContain("NOAA MHD FRAME");
    expect(boundary?.value).toContain("0.31");
    expect(spec.note).toContain("calibrated to the NOAA MHD frame");
    expect(spec.note).toContain("0.87");
    expect(spec.statusText).toContain("MHD-calibrated");
  });

  it("keeps every boundary curve out of the rail and unchecked by default", () => {
    for (const id of ["annotate-empirical-boundaries", "annotate-extracted-boundaries", "geospace-field-lines", "geospace-flow-lines", "magnetopause-cut", "geospace-mhd-cut"]) {
      expect(rail, `#${id} is an annotation and must not be a rail row`).not.toContain(`id="${id}"`);
      expect(panels, `#${id} went missing from the field layer's settings`).toContain(`id="${id}"`);
      const tag = panels.slice(panels.indexOf(`id="${id}"`) - 200, panels.indexOf(`id="${id}"`) + 60);
      expect(tag, `#${id} must start unchecked: the default picture is the field alone`).not.toContain("checked");
    }
  });

  it("defaults the controls to the textbook view: density, meridional", () => {
    expect(panels).toContain('class="is-active" data-model-field="density"');
    expect(panels).toContain('class="is-active" data-model-plane="meridional"');
    expect(panels.split("is-active").length - 1).toBeGreaterThanOrEqual(2);
  });
});
