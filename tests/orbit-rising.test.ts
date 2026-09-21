// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixtures/orbit-drift.json";
import history from "./fixtures/orbit-history-live.json";
import { renderRisingNow } from "../src/orbit-rising";
import { driftObjectText, type DriftObject, type OrbitDriftBundle } from "../src/orbit-drift";
import { mountOrbitHistoryBrowser } from "../src/orbit-history-browser";
import type { OrbitEventsBundle } from "../src/orbit-history";
import { satelliteFundamentalsPageView } from "../src/satellite-fundamentals";

const fresh = () => structuredClone(fixture) as unknown as OrbitDriftBundle;
const row = (norad: number, overrides: Partial<DriftObject> = {}): DriftObject => ({
  norad, objectType: "PAYLOAD", inGate: true, raising: true, flag: true,
  regime: "drag regime", slopeMetresPerDay: 20, spanDays: 115, gap: null, ...overrides,
});
function populated(open = false): OrbitDriftBundle {
  const b = fresh();
  b.objects = [row(2), row(1, { slopeMetresPerDay: 50 }),
    row(3, { inGate: false, objectType: "DEBRIS", regime: "SRP-regime rise" }),
    row(4, { inGate: false, regime: "GEO libration" }),
    row(5, { inGate: false, regime: "HEO lunisolar" }),
    row(6, { raising: false, flag: false, gap: "insufficient temporal blocks/coverage", slopeMetresPerDay: null, spanDays: null })];
  if (open) {
    Object.assign(b.controls, { sufficientToLabel: true, separation: 10, acceptance: "controls pass" });
    Object.assign(b.controls.passive, { objects: 6000, upper95: .0005 });
    Object.assign(b.labelPolicy, { propulsionLabelPermitted: true, blockingReason: null });
  }
  return b;
}
// Flat-record shape and control values of the 2026-09-20 published artifact.
// Kept in TS: no live fetches and no new pipeline/JSON fixture dependencies.
function liveZero(): OrbitDriftBundle {
  const b = fresh();
  b.generatedAt = "2026-09-20T05:45:21.377953+00:00";
  b.method.windows = [[20356, 20596], [20596, 20716]];
  Object.assign(b.controls, { objectsWithGap: 68711, separation: null });
  b.controls.passive = { objects: 0, flags: 0, upper95: null };
  b.controls.payload = { objects: 0, flags: 0 };
  b.objects = Array.from({ length: 68711 }, (_, i) => row(i + 4, {
    objectType: "UNKNOWN", raising: false, flag: false, inGate: null, regime: null,
    slopeMetresPerDay: null, spanDays: null, gap: "insufficient temporal blocks/coverage",
  }));
  return b;
}
const names = new Map([[1, "Fast payload"], [2, "Slow payload"], [3, "Passive debris"]]);
const render = (b: OrbitDriftBundle) => renderRisingNow(b, names, vi.fn());
afterEach(() => { document.body.replaceChildren(); vi.unstubAllGlobals(); });

describe("Rising now earns its wording from the drift lane", () => {
  it.each([false, true])("populates both lists and the measurement section; gate open=%s", open => {
    const b = populated(open);
    const panel = render(b);
    const groups = panel.querySelectorAll(".orbit-history__rising-group");
    expect(groups[0]!.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(groups[1]!.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(panel.querySelector(".orbit-history__rising-coverage")?.textContent).toContain("6 objects evaluated; 5 fitted trends; 1 coverage gaps");
    expect([...groups[0]!.querySelectorAll("tbody a")].map(a => a.textContent)).toEqual(["Fast payload · 1", "Slow payload · 2"]);
    const cells = groups[0]!.querySelectorAll("tbody tr:first-child td");
    expect(cells[1]!.textContent).toBe("+50.00");
    expect(cells[2]!.textContent).toBe("115.0");
    expect(groups[0]!.textContent?.includes("only propulsion")).toBe(open);
    expect(groups[0]!.textContent).toContain(open ? "cause remains an inference" : "no propulsion claim");
    expect(groups[1]!.textContent).not.toContain("only propulsion");
    for (const label of ["solar-radiation-pressure regime rise", "GEO libration", "HEO lunisolar"]) expect(groups[1]!.textContent).toContain(label);
    expect(groups[1]!.textContent).toContain("not a demonstrated cause or a propulsion claim");
    for (const object of b.objects.filter(o => o.raising)) {
      for (const paragraph of driftObjectText(b, object)) expect(panel.textContent).toContain(paragraph);
    }
    for (const p of panel.querySelectorAll("p")) expect(p.textContent!.trim().split(/\s+/).length).toBeLessThanOrEqual(100);
  });
  it("fails closed on stale permission, invalid controls and missing record warrants", () => {
    const mutations: ((b: OrbitDriftBundle) => void)[] = [
      b => { b.labelPolicy.propulsionLabelPermitted = false; },
      b => { b.controls.passive.upper95 = null; },
      b => { b.controls.separation = 9.99; },
      b => { b.controls.restrictedPopulation = true; },
      b => { b.objects.forEach(o => { o.flag = false; }); },
      b => { b.objects.forEach(o => { o.objectType = "DEBRIS"; }); },
      b => { b.objects.forEach(o => { o.gap = "missing fit"; }); },
    ];
    for (const mutate of mutations) {
      const b = populated(true); mutate(b);
      expect(render(b).textContent).not.toContain("only propulsion");
    }
  });
  it("keeps unknown labels and gaps, with a generic ambiguity fallback", () => {
    const b = populated(true);
    b.objects = [row(10, { inGate: false, regime: "published ambiguity label" }),
      row(11, { inGate: false, regime: null }), row(12, { inGate: false, gap: "coverage gap from producer" })];
    const text = render(b).textContent;
    expect(text).toContain("published ambiguity label");
    expect(text).toContain("Above-gate rise");
    expect(text).toContain("coverage gap from producer");
    expect(text).not.toContain("only propulsion");
  });
  it("shows today's real-shape zero as accumulating coverage, not measured quiet", () => {
    const b = liveZero();
    const panel = render(b);
    expect(panel.textContent).toContain("68,711 objects evaluated; 0 fitted trends; 68,711 coverage gaps");
    expect(panel.textContent).toContain(b.generatedAt);
    expect(panel.textContent).toContain("controls failed or unmeasurable");
    expect(panel.textContent).toContain("Coverage is accumulating");
    expect(panel.textContent).not.toContain("none currently sustains");
    expect(panel.textContent).not.toContain("lane measured 68,711");
    expect(panel.querySelectorAll("tbody tr")).toHaveLength(0);
  });
  it("counts actual measured trends for a resolved empty result", () => {
    const b = populated(true); b.objects.forEach(o => { o.raising = false; o.flag = false; });
    expect(render(b).textContent).toContain("lane measured 5 objects in this artifact; none currently sustains a resolved climb");
    expect(render(b).textContent).toContain("coverage gap is not a measured absence");
  });
});

describe("reader reachability and asynchronous lifetime", () => {
  it("mounts beside the summaries, joins catalogue names and opens object history", async () => {
    const host = document.createElement("div"); document.body.append(host);
    const onSelect = vi.fn();
    const handle = mountOrbitHistoryBrowser(host, { bundle: history.bundle as unknown as OrbitEventsBundle,
      catalogNames: names, loadDrift: async () => populated(), loadShard: async () => null, onSelect });
    await vi.waitFor(() => expect(host.querySelector(".orbit-history__rising")).not.toBeNull());
    expect(host.querySelector(".orbit-history__status")?.nextElementSibling?.className).toBe("orbit-history__rising-slot");
    const link = host.querySelector<HTMLAnchorElement>('a[href="#orbit-history-object-1"]')!;
    expect(link.textContent).toContain("Fast payload"); link.click();
    await vi.waitFor(() => expect(host.querySelector(".orbit-history__detail .orbit-history__drift")).not.toBeNull());
    expect(onSelect).toHaveBeenCalledWith(1);
    expect(document.activeElement?.id).toBe("orbit-history-object-1");
    handle.destroy();
  });
  it("keeps absent, failed, and disposed artifacts distinct from empty measurements", async () => {
    const host = document.createElement("div");
    const base = { bundle: history.bundle as unknown as OrbitEventsBundle, loadShard: async () => null };
    let handle = mountOrbitHistoryBrowser(host, base);
    expect(host.textContent).toContain("no drift artifact has been published"); handle.destroy();
    handle = mountOrbitHistoryBrowser(host, { ...base, loadDrift: async () => { throw Error("offline"); } });
    await vi.waitFor(() => expect(host.textContent).toContain("Rising now could not be loaded")); handle.destroy();
    let resolve!: (b: OrbitDriftBundle) => void;
    handle = mountOrbitHistoryBrowser(host, { ...base, loadDrift: () => new Promise(r => { resolve = r; }) });
    handle.destroy(); resolve(populated()); await Promise.resolve();
    expect(host.children).toHaveLength(0);
  });
  it("links the drift lesson to the wired browser using the manifest artifact", () => {
    const host = document.createElement("div"); host.innerHTML = satelliteFundamentalsPageView("inference");
    expect(host.querySelector("[data-orbit-rising-open]")?.getAttribute("href")).toBe("#orbit-history-rising-now");
    const main = readFileSync("src/main.ts", "utf8");
    expect(main).toContain('body.querySelectorAll<HTMLAnchorElement>("[data-orbit-rising-open]")');
    expect(main).toContain("void this.openOrbitHistory(true)");
    expect(main).toContain("loadOrbitDrift(this.manifest.orbitDrift!.path)");
    expect(main).toContain("catalogNames: new Map(this.catalog.satellites.map(object => [object.id, object.name]))");
  });
});
