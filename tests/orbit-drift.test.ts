// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixtures/orbit-drift.json";
import history from "./fixtures/orbit-history-live.json";
import { driftGatePassed, driftControlText, renderDriftCard, loadOrbitDrift, mountDriftControls, type OrbitDriftBundle } from "../src/orbit-drift";
import { mountOrbitHistoryBrowser } from "../src/orbit-history-browser";
import type { OrbitEventsBundle } from "../src/orbit-history";
import { satelliteFundamentalsPageView } from "../src/satellite-fundamentals";

// Emitted by the real Python run() -> publication_bundle() on the offline archive
// fixture: one injected rise, nineteen passive decays, one coverage gap.
const fresh = () => structuredClone(fixture) as unknown as OrbitDriftBundle;
const passing = () => {
  const b = fresh();
  Object.assign(b.controls, { sufficientToLabel: true, separation: 10 });
  Object.assign(b.controls.passive, { objects: 6000, upper95: .0005 });
  Object.assign(b.labelPolicy, { propulsionLabelPermitted: true, blockingReason: null });
  b.objects.find(o => o.norad === 20)!.flag = true;
  return b;
};
const card = (b: OrbitDriftBundle, norad = 20) => renderDriftCard(b, b.objects.find(o => o.norad === norad)!);
afterEach(() => vi.unstubAllGlobals());

describe("the drift lane earns its own wording", () => {
  it("renders a real producer's suppressed rise and its own control numbers", () => {
    const b = fresh();
    const text = card(b).textContent!;
    expect(text).toContain("Resolved positive slope");
    expect(text).toContain("m/day");
    expect(text).toContain("Passive detections 0/19");
    expect(text).toContain("Payload detections 1/1");
    expect(text).toContain("Flags suppressed");
    expect(text).not.toContain("only propulsion");
  });
  it("permits the stronger physical inference only on a passed payload flag", () => {
    const b = passing();
    expect(card(b).textContent).toContain("Sustained orbit-raising over");
    expect(card(b).textContent).toContain("In this regime, only propulsion produces a sustained climb");
    expect(card(b).textContent).toContain("cause remains an inference");
    for (const kind of ["UNKNOWN", "DEBRIS", "ROCKET BODY", "OTHER"]) {
      b.objects.find(o => o.norad === 20)!.objectType = kind;
      expect(card(b).textContent).not.toContain("only propulsion");
    }
  });
  it("does not trust a stale true policy against failing or missing numbers", () => {
    for (const upper of [.001, .002, 0, null, NaN]) {
      const b = passing(); b.controls.passive.upper95 = upper;
      expect(driftGatePassed(b)).toBe(false);
      expect(card(b).textContent).not.toContain("only propulsion");
    }
    for (const separation of [9.999, null, NaN]) {
      const b = passing(); b.controls.separation = separation;
      expect(driftGatePassed(b)).toBe(false);
    }
    const b = passing(); b.controls.restrictedPopulation = true;
    expect(driftGatePassed(b)).toBe(false);
  });
  it("keeps above-gate rises as ambiguity labels even with a passed gate", () => {
    for (const [regime, label] of [["SRP-regime rise", "solar-radiation-pressure regime rise"], ["GEO libration", "GEO libration"], ["HEO lunisolar", "HEO lunisolar"]]) {
      const b = passing();
      Object.assign(b.objects.find(o => o.norad === 20)!, { inGate: false, regime });
      expect(card(b).textContent).toContain(label);
      expect(card(b).textContent).toContain("not a demonstrated cause or a propulsion claim");
      expect(card(b).textContent).not.toContain("only propulsion");
    }
  });
  it("shows gaps and does not interpret a quiet slope as no propulsion", () => {
    expect(card(fresh(), 21).textContent).toContain("Coverage gap: insufficient temporal blocks/coverage");
    expect(card(fresh(), 1).textContent).toContain("Station-keeping and short campaigns can escape");
  });
  it("mounts the card even when the object's step history is unavailable", async () => {
    const host = document.createElement("div");
    document.body.replaceChildren(host);
    const handle = mountOrbitHistoryBrowser(host, {
      bundle: history.bundle as unknown as OrbitEventsBundle,
      initialNorad: 20, loadShard: async () => null, loadDrift: async () => fresh(),
    });
    await vi.waitFor(() => expect(host.textContent).toContain("Long-arc drift"));
    expect(host.querySelector(".orbit-history__drift")?.textContent).toContain("Flags suppressed");
    expect(host.querySelector(".orbit-history__drift")?.getAttribute("style")).toContain("--oh-drift, #57c7b3");
    handle.destroy();
  });
});

describe("artifact fetching and the learn chapter", () => {
  it("loads by content path, caches one artifact and retries failures", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => fresh() });
    vi.stubGlobal("fetch", fetcher);
    await Promise.all([loadOrbitDrift("artifacts/orbit-drift-cache.json"), loadOrbitDrift("artifacts/orbit-drift-cache.json")]);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0]![0])).toContain("/data/artifacts/orbit-drift-cache.json");
    fetcher.mockResolvedValueOnce({ ok: false, status: 404 });
    await expect(loadOrbitDrift("artifacts/orbit-drift-retry.json")).rejects.toThrow("404");
    await expect(loadOrbitDrift("artifacts/orbit-drift-retry.json")).resolves.toHaveProperty("version", 4);
  });
  it("hydrates the real inference page with the current control, with honest absence/failure", async () => {
    const host = document.createElement("div");
    host.innerHTML = satelliteFundamentalsPageView("inference");
    document.body.replaceChildren(host);
    expect(host.textContent).toContain("Three designs failed their blank");
    expect(host.textContent).toContain("120 complete UTC days");
    await mountDriftControls(host);
    expect(host.querySelector("[data-orbit-drift-controls]")?.textContent).toContain("No nightly drift control has been published");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => fresh() }));
    await mountDriftControls(host, "artifacts/orbit-drift-chapter.json");
    expect(host.querySelector("[data-orbit-drift-controls]")?.textContent).toBe(driftControlText(fresh()));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await mountDriftControls(host, "artifacts/orbit-drift-offline.json");
    expect(host.querySelector("[data-orbit-drift-controls]")?.textContent).toContain("could not be loaded");
  });
});
