import { describe, expect, it } from "vitest";
import globeSource from "../src/globe.ts?raw";
import mainSource from "../src/main.ts?raw";
import indexMarkup from "../index.html?raw";
import openWork from "../docs/OPEN-WORK.md?raw";

/**
 * Can anything on the site actually reach this layer?
 *
 * Three features on this project have been built, tested, merged, and found to
 * be referenced by zero entry points. A passing unit test proves a module
 * works; it proves nothing about whether the running page ever calls it. These
 * assertions walk the reference chain as text, from the module out to the
 * page, and stop where it stops.
 *
 * The chain is:
 *
 *   src/ground-perturbation.ts   the layer
 *     <- src/globe.ts            mounts it, exposes setLayer("groundField")
 *       <- src/main.ts           fetches manifest.groundField and mounts it
 *         <- index.html          the checkbox a visitor can press
 *
 * The last two links are a patch for the agent who owns those files. Until
 * they land, the layer is dark, and the honest thing is to say so where a
 * future session will read it — which is what the final assertion enforces.
 */

describe("the ground-perturbation layer's reference chain", () => {
  const globe = globeSource;

  it("is imported and constructed by the globe, not merely exported", () => {
    expect(globe).toContain(`from "./ground-perturbation"`);
    expect(globe).toContain("new GroundPerturbationLayer(");
  });

  it("is added to the Earth-fixed group, where the coastlines are", () => {
    // A geographic grid on the Sun-fixed group would rotate against the map.
    const mount = globe.slice(globe.indexOf("setGroundFieldModel"), globe.indexOf("setGroundFieldSystem"));
    expect(mount).toContain("this.earthFixedGroup.add(layer.mesh)");
    expect(mount).not.toContain("sunFrameGroup");
  });

  it("is driven by the same public toggle every other layer uses", () => {
    expect(globe).toContain(`layer === "groundField"`);
    expect(globe).toMatch(/setLayer\([^)]*"groundField"/s);
  });

  it("follows the selected UTC and the smooth/native setting", () => {
    expect(globe).toContain("this.groundField?.setSimulationTime(date)");
    expect(globe).toContain("this.groundField?.setDisplayMode(mode)");
  });

  it("is disposed when the globe is destroyed, so a reload cannot leak a texture", () => {
    expect(globe).toContain("this.groundField?.dispose()");
  });

  it("is either reachable from the page, or recorded as unreachable in the open-work log", () => {
    const wired = mainSource.includes("setGroundFieldModel") && indexMarkup.includes("layer-groundField");
    if (wired) {
      // Whoever wires it must wire all of it: the fetch, the mount and the
      // toggle, or the checkbox is a switch attached to nothing.
      expect(mainSource).toContain("manifest.groundField");
      expect(mainSource).toContain("setGroundFieldModel");
      expect(mainSource).toContain(`"groundField"`);
      expect(indexMarkup).toContain("layer-groundField");
    } else {
      expect(openWork).toContain("src/ground-perturbation.ts");
      expect(openWork).toContain("zero entry points");
    }
  });

  /**
   * The chain above proves the toggle fetches and mounts the layer on the
   * globe. It does not prove the toggle's effect ever reaches the legend or
   * the Data Explorer — those are built by walking `layerOrder` and calling
   * `environmentLegendSpec(layer)` for each entry, and a layer absent from
   * `layerOrder` is switched on, fetched, and drawn, yet never appears
   * anywhere a reader looks for it. That was live in production: the rail
   * toggle was on, the overlay was mounted, and the legend still listed only
   * four layers with groundField missing from all of them. A green result on
   * every test above coexisted with that bug the whole time, which is
   * exactly the "presence test, not a behaviour test" trap this project has
   * already paid for once (`tests/module-reachability.test.ts`'s own
   * history). These assertions pin the two facts that closed it.
   */
  it("is listed in layerOrder, so activeLayers()/updateEnvironmentLegend() ever consider it", () => {
    const start = mainSource.indexOf("private static readonly layerOrder");
    expect(start).toBeGreaterThan(-1);
    const layerOrderLiteral = mainSource.slice(start, mainSource.indexOf("];", start));
    expect(layerOrderLiteral).toContain(`"groundField"`);
  });

  it("gets a real environmentLegendSpec case that always carries a scale, never the retired scale-less presentation", () => {
    const specStart = mainSource.indexOf("private environmentLegendSpec(layer: LayerName)");
    expect(specStart).toBeGreaterThan(-1);
    const caseStart = mainSource.indexOf('if (layer === "groundField")', specStart);
    expect(caseStart).toBeGreaterThan(-1);
    const nextCase = mainSource.indexOf('if (layer === "aurora")', caseStart);
    const groundFieldCase = mainSource.slice(caseStart, nextCase);
    // Present unconditionally, not `scale: bundle ? {...} : undefined` — the
    // fixed 0-1500 nT ramp does not depend on a frame having loaded yet, so
    // this card must never fall through to keyCardBar's "SHAPE ONLY" branch.
    expect(groundFieldCase).toContain("scale: {");
    expect(groundFieldCase).not.toContain("scale: undefined");
  });
});
