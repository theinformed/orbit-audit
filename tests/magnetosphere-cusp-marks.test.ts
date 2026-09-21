import { describe, expect, it } from "vitest";
import indexMarkup from "../index.html?raw";
import stylesSource from "../src/styles.css?raw";
import { magnetosphereFieldLegendSpec } from "../src/main";
import type { MagnetosphereFieldSpecInput } from "../src/main";
import { EXTERIOR_CUSP_COLOR, MAGNETOPAUSE_MODEL_COLORS } from "../src/globe";
import { GEOSPACE_BOUNDARY_COLORS } from "../src/geospace-runtime";
import type { FieldLineSummary } from "../src/magnetosphere-field-lines";

/**
 * THE ORANGE THING HAS TO SAY WHAT IT IS.
 *
 * Sean, 2026-08-26, on the shipped build: "On the magnetosphere, we still draw
 * the bow shocks in orange, but we don't label that anywhere on the page."
 *
 * He was right that nothing named them, and wrong about what they are, and the
 * second half is the worse defect. Proven by removing exactly one mesh from the
 * built bundle — `field-line-context-exterior-cusp`, the funnel added beside
 * the traced lines in `globe.ts` — and re-shooting the layer: every orange
 * pixel in the picture went with it. The layer's only other content is the
 * traced field lines, whose vertex colours come from the |B| ramp (dark violet
 * -> violet -> cyan; `FIELD_PALETTES.magneticField`), which has no orange in
 * it at all. So the orange IS the exterior cusp and nothing else.
 *
 * A bow shock is close to the opposite thing: it stands about 13 R⊕ upstream
 * and is where the solar wind is STOPPED; the cusp is the one place on the
 * dayside where it gets IN. The layer's own construction "contains no bow
 * shock" (src/content.ts), and the extracted bow-shock curve is an
 * off-by-default annotation in this layer's settings.
 *
 * So these guard three things:
 *   1. the funnels are NAMED whenever they are drawn, with their evidence class;
 *   2. they are NOT named when they are not drawn — the negative control, which
 *      is the same defect pointing the other way;
 *   3. the swatch is the colour the renderer actually uses, read from the one
 *      constant both sides share, so the row cannot drift off the thing it
 *      points at.
 */

const formatEndpoint = (value: number, scale: "linear" | "log10") =>
  scale === "log10" ? `10^${value}` : String(value);

const fieldLineSummary: FieldLineSummary = {
  standoffRe: 10.4,
  closedNoseXRe: 9.8,
  firstOpenMidnightLatitudeDeg: 72.1,
  tailFieldNt: 21,
  boundarySource: "shue-l1",
  calibration: null,
} as unknown as FieldLineSummary;

/** The layer's DEFAULT face: the driven 3-D field lines, not the MHD cut. */
function drivenInput(overrides: Partial<MagnetosphereFieldSpecInput> = {}): MagnetosphereFieldSpecInput {
  return {
    field: "magneticField",
    fieldMetadata: null,
    structures: null,
    runtimeState: null,
    loading: false,
    empiricalAnnotationOn: false,
    shueNoseRe: 10.4,
    frameDescription: null,
    formatEndpoint,
    mhdCutOn: false,
    fieldLineSummary,
    ...overrides,
  };
}

describe("the magnetosphere layer names its amber cusp funnels", () => {
  it("names them, with their evidence class, whenever they are drawn", () => {
    const spec = magnetosphereFieldLegendSpec(drivenInput({ cuspFunnelsDrawn: true }));
    expect(spec.marks, "the drawn funnels produced no legend row at all").toBeTruthy();
    expect(spec.marks).toHaveLength(1);
    const [mark] = spec.marks!;
    expect(mark!.name.toLowerCase()).toContain("cusp");
    expect(mark!.evidence).toBe("empirical");
    // The whole point: the row has to CORRECT the misreading, not merely fill
    // a gap. A row that named them and left "bow shock" a live reading would
    // pass a presence check and fail the reader.
    expect(`${mark!.name} ${mark!.what}`.toLowerCase()).toContain("not a bow shock");
  });

  it("does NOT name them when the drivers cannot support them", () => {
    // `cuspedDrivers` refuses without a dipole tilt, an IMF clock angle and a
    // magnetic pressure, and the globe then draws no funnel. The negative
    // control: a swatch for a surface that is not on screen is exactly as
    // wrong as the surface with no swatch.
    expect(magnetosphereFieldLegendSpec(drivenInput({ cuspFunnelsDrawn: false })).marks ?? [])
      .toHaveLength(0);
    // ...and an older spec construction that says nothing at all means "not
    // drawn", never "drawn".
    expect(magnetosphereFieldLegendSpec(drivenInput()).marks ?? []).toHaveLength(0);
  });

  it("uses the colour the renderer actually draws the funnels in", () => {
    const [mark] = magnetosphereFieldLegendSpec(drivenInput({ cuspFunnelsDrawn: true })).marks!;
    expect(mark!.swatch).toBe(`#${EXTERIOR_CUSP_COLOR.toString(16).padStart(6, "0")}`);
    // And that colour is NOT the bow shock's, which is the neighbouring warm
    // colour this layer draws when the extracted-boundary annotation is on.
    // Two warm surfaces one click apart is the whole reason the names matter.
    expect(EXTERIOR_CUSP_COLOR).not.toBe(GEOSPACE_BOUNDARY_COLORS.bowShock);
  });

  it("says polar cusp in the card's own prose, not only in the swatch", () => {
    // The swatch is a glance; the note is what a reader reads when they want
    // the answer. The shipped note called them "empirical exterior cusps" four
    // sentences into the folded half of the description, which is where Sean
    // did not find them.
    const note = magnetosphereFieldLegendSpec(drivenInput({ cuspFunnelsDrawn: true })).note.toLowerCase();
    expect(note).toContain("polar cusps");
    expect(note).toContain("not a bow shock");
  });

  it("actually hides that row list when there is nothing to name", () => {
    // `fillLayerCard` sets `marks.hidden = true` for the eight layers whose
    // whole picture is on their own colour ramp. The UA sheet's
    // `[hidden] { display: none }` loses to ANY author `display`, and the list
    // is `display: grid`, so without this rule the flag is a flag the page
    // ignores: an empty grid and its 8 px top margin, on every one of those
    // cards, under the opening sentence. This site has already paid for that
    // exact cascade once — see the note on `.legend` in the stylesheet, a
    // satellite colour key that stayed on screen over a globe with no
    // satellites — which is why it is pinned here rather than eyeballed.
    expect(stylesSource).toContain(".card-marks[hidden] { display: none; }");
  });

  it("gives the card somewhere to put those rows", () => {
    // The renderer fills `[data-card-marks]`; without the element the rows are
    // built and dropped, and every check above still passes.
    expect(indexMarkup).toContain('<ul class="card-marks" data-card-marks hidden></ul>');
  });
});

/**
 * ...AND IT ONLY DRAWS THEM WHEN THE READER ASKS.
 *
 * Sean, 2026-08-26, once the funnels were named: "I see the polar cusps, but I
 * think what we should do is hide them, but have them able to be toggled in
 * the layer browser. Like you can click into that layer's info and there is a
 * toggle to show them. The cusps would only be shown in the legend and on the
 * screen if the user wants to see them."
 *
 * The globe half of that (`setCuspFunnelsEnabled` gating both the field-line
 * context funnel and the empirical annotation's shaded volume) needs a WebGL
 * context and is measured in the browser instead — 156 amber pixels with the
 * tick off, 241,501 with it on, 156 again after unticking, in the same frame.
 * What is pinned here is everything that can be: that the control exists, that
 * it ships OFF, and that the card's correction survives in both states.
 */
describe("the polar cusps are an opt-in annotation of the magnetosphere layer", () => {
  it("ships a tick for them, off, beside the layer's other annotations", () => {
    const at = indexMarkup.indexOf('id="annotate-polar-cusps"');
    expect(at, "no control for the polar cusps in the layer's settings").toBeGreaterThan(-1);
    const tick = indexMarkup.slice(indexMarkup.lastIndexOf("<label", at), indexMarkup.indexOf("</label>", at) + 8);
    // OFF BY DEFAULT is the whole request. A `checked` attribute here would
    // put the funnels back on every first visit and nothing else would notice.
    expect(tick).not.toContain("checked");
    // Beside the two boundary annotations, in the magnetosphere layer's own
    // panel — not a rail row, not a layer, not a new grammar. Sliced to the
    // NEXT panel rather than to a `</div>`, because this panel nests them.
    const panelStart = indexMarkup.indexOf('<div class="layer-panel" data-layer-panel="geospace">');
    expect(panelStart).toBeGreaterThan(-1);
    const panelEnd = indexMarkup.indexOf('<div class="layer-panel"', panelStart + 1);
    const panel = indexMarkup.slice(panelStart, panelEnd === -1 ? undefined : panelEnd);
    expect(panel).toContain('id="annotate-polar-cusps"');
    expect(panel).toContain('id="annotate-empirical-boundaries"');
    // Plain words, and the correction where the reader decides, not only after
    // they have already switched it on.
    expect(tick!.toLowerCase()).toContain("not a bow shock");
  });

  it("keeps the correction in the card whether they are drawn or not", () => {
    for (const drawn of [true, false]) {
      const note = magnetosphereFieldLegendSpec(drivenInput({ cuspFunnelsDrawn: drawn })).note.toLowerCase();
      expect(note, `cuspFunnelsDrawn=${drawn} lost the correction`).toContain("not a bow shock");
      expect(note).toContain("polar cusps");
    }
    // ...and when they are NOT drawn the card has to say where the switch is,
    // or the correction is an answer to a question the picture never raises.
    const offNote = magnetosphereFieldLegendSpec(drivenInput({ cuspFunnelsDrawn: false })).note;
    expect(offNote).toContain("Annotation: polar cusps");
  });
});

/**
 * THE OTHER ANNOTATIONS ON THIS LAYER HAD NO COLOUR KEY AT ALL.
 *
 * The bow-shock curve is `#f5c96a` and the cusp funnels are `#ffb257`: one tick
 * apart, and one click apart in the same settings panel. So the misreading this
 * whole family of fixes answers was re-armed the moment a reader opened the
 * neighbouring annotation, which named its surfaces in prose and never said
 * which colour was which.
 */
describe("every annotation this layer draws gets a colour-keyed row", () => {
  const names = (input: Parameters<typeof magnetosphereFieldLegendSpec>[0]) =>
    (magnetosphereFieldLegendSpec(input).marks ?? []).map((mark) => mark.name);
  const swatches = (input: Parameters<typeof magnetosphereFieldLegendSpec>[0]) =>
    (magnetosphereFieldLegendSpec(input).marks ?? []).map((mark) => mark.swatch);

  it("keys the extracted curves in the colours the renderer uses", () => {
    const marks = magnetosphereFieldLegendSpec(drivenInput({ extractedAnnotationOn: true })).marks ?? [];
    expect(marks).toHaveLength(2);
    expect(marks.map((mark) => mark.swatch)).toEqual([
      `#${GEOSPACE_BOUNDARY_COLORS.bowShock.toString(16).padStart(6, "0")}`,
      `#${GEOSPACE_BOUNDARY_COLORS.magnetopauseProxy.toString(16).padStart(6, "0")}`,
    ]);
    expect(marks[0]!.name.toLowerCase()).toContain("bow shock");
    // The trap, stated where the two rows meet: this is the layer's ONLY bow
    // shock, and it is the cusps' near neighbour in colour and their opposite
    // in physics.
    expect(marks[0]!.what.toLowerCase()).toContain("stopped");
  });

  it("puts the cusp row and the bow-shock row together, in different colours", () => {
    const both = magnetosphereFieldLegendSpec(drivenInput({
      cuspFunnelsDrawn: true,
      extractedAnnotationOn: true,
    })).marks!;
    const cusp = both.find((mark) => /cusp/i.test(mark.name))!;
    const shock = both.find((mark) => /bow shock/i.test(mark.name))!;
    expect(cusp, "the cusps lost their row when the neighbour annotation came on").toBeTruthy();
    expect(shock).toBeTruthy();
    expect(cusp.swatch).not.toBe(shock.swatch);
  });

  it("names only the empirical fits that were actually drawn", () => {
    // Without a full IMF vector and a dipole tilt the boundary pass draws Shue
    // alone, so a list of three would be three swatches for one surface.
    expect(names(drivenInput({ empiricalAnnotationOn: true, empiricalModelsDrawn: ["shue1998"] })))
      .toEqual(["Shue (1998) magnetopause fit"]);
    expect(swatches(drivenInput({ empiricalAnnotationOn: true, empiricalModelsDrawn: ["shue1998"] })))
      .toEqual([`#${MAGNETOPAUSE_MODEL_COLORS.shue1998.toString(16).padStart(6, "0")}`]);
    // ...and the tick off means no rows, whatever the boundary pass drew.
    expect(names(drivenInput({ empiricalAnnotationOn: false, empiricalModelsDrawn: ["shue1998", "nguyen2022"] })))
      .toEqual([]);
    // All three, each in its own constant's colour.
    expect(swatches(drivenInput({
      empiricalAnnotationOn: true,
      empiricalModelsDrawn: ["nguyen2022", "lin2010", "shue1998"],
    }))).toEqual([
      `#${MAGNETOPAUSE_MODEL_COLORS.nguyen2022.toString(16).padStart(6, "0")}`,
      `#${MAGNETOPAUSE_MODEL_COLORS.lin2010.toString(16).padStart(6, "0")}`,
      `#${MAGNETOPAUSE_MODEL_COLORS.shue1998.toString(16).padStart(6, "0")}`,
    ]);
  });

  it("carries the same rows on the NOAA MHD cut's own card", () => {
    // The cut is a slice THROUGH the scene: the field lines and anything
    // annotated over them stay on screen behind it, so this face owes the same
    // key. It used to carry none at all, which is how a drawn cusp funnel
    // could lose its row by the reader ticking an unrelated box.
    const cut = magnetosphereFieldLegendSpec(drivenInput({
      mhdCutOn: true,
      cuspFunnelsDrawn: true,
      extractedAnnotationOn: true,
    }));
    expect(cut.marks?.map((mark) => mark.name)).toEqual([
      "Polar cusps — north and south",
      "Bow shock — extracted curve",
      "Magnetopause proxy — extracted curve",
    ]);
  });

  it("draws no rows at all when nothing extra is on screen", () => {
    // The negative control for the whole list, not only for the cusps.
    expect(magnetosphereFieldLegendSpec(drivenInput()).marks).toBeUndefined();
    expect(magnetosphereFieldLegendSpec(drivenInput({ mhdCutOn: true })).marks).toBeUndefined();
  });
});
