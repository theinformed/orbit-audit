// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import {
  orbitMethodsPageView,
  mountOrbitMethods,
  ORBIT_METHODS_CLIPS,
} from "../src/orbit-methods";

const html = orbitMethodsPageView();
const doc = new DOMParser().parseFromString(html, "text/html");

describe("orbit methods page", () => {
  it("renders the five-step arc with numbered sections", () => {
    const sections = [...doc.querySelectorAll("section.om-section")];
    expect(sections).toHaveLength(5);
    expect(doc.querySelectorAll(".om-step").length).toBeGreaterThanOrEqual(5);
    for (const id of ["orbit", "step", "arithmetic", "gate", "earning"]) {
      expect(doc.getElementById(`om-${id}`)).not.toBeNull();
    }
  });

  it("gives every figure clip-ready data-beat layers", () => {
    const figures = [...doc.querySelectorAll("figure.om-figure svg")];
    expect(figures).toHaveLength(5);
    for (const svg of figures) {
      expect(svg.querySelectorAll("[data-beat]").length).toBeGreaterThan(2);
      // a base layer (beat 0) must exist so nothing is ever fully hidden
      expect(svg.querySelector('[data-beat="0"]')).not.toBeNull();
    }
  });

  it("carries the verified measured numbers", () => {
    for (const n of [
      "216,203,378", "15.44218077", "398,600.8", "434", "92.6", "7.4",
      "4,278,167", "0.162", "2.95", "18.19", "10.88", "40,300", "4,107",
    ]) {
      expect(html).toContain(n);
    }
  });

  it("keeps the honesty language and never weakens the hedge", () => {
    const text = doc.body.textContent ?? "";
    expect(text).toContain("lower bound");
    expect(text).toContain("candidate");
    expect(text).toMatch(/ten times|10 times|18\.19 times/);
    // the gate wording must be present and framed as a rule, not a boast
    expect(text).toMatch(/only when.*separation|separation.*clears/i);
  });

  it("holds prose blocks to a readable length (<=100 words each)", () => {
    for (const p of [...doc.querySelectorAll("section.om-section p, .om-lede")]) {
      const words = (p.textContent ?? "").trim().split(/\s+/).filter(Boolean).length;
      expect(words).toBeLessThanOrEqual(100);
    }
  });

  it("has a clip slot declared for every roster entry", () => {
    expect(ORBIT_METHODS_CLIPS).toHaveLength(5);
    for (const clip of ORBIT_METHODS_CLIPS) {
      const slot = doc.querySelector(`[data-clip="${clip.id}"]`);
      expect(slot).not.toBeNull();
    }
  });

  it("upgrades an available clip slot to a captioned video on click", () => {
    // Synthesize the markup an available clip would emit, and prove the mount
    // builds a <video> with a captions <track> from the slot's data-*.
    document.body.innerHTML = `
      <div class="om-clip-slot" data-clip="x"
        data-src="/media/orbit-methods/x.mp4" data-captions="/media/orbit-methods/x.vtt">
        <button type="button" class="om-play" aria-expanded="false">play</button>
      </div>`;
    mountOrbitMethods(document);
    const button = document.querySelector<HTMLButtonElement>("button.om-play")!;
    button.click();
    const video = document.querySelector("video");
    expect(video).not.toBeNull();
    expect(video?.getAttribute("src")).toBe("/media/orbit-methods/x.mp4");
    const track = video?.querySelector("track");
    expect(track?.getAttribute("kind")).toBe("captions");
    expect(track?.getAttribute("src")).toBe("/media/orbit-methods/x.vtt");
    expect(button.getAttribute("aria-expanded")).toBe("true");
  });

  it("offers all five narrated clips with media, captions and posters wired", () => {
    // every clip is rendered and live: five slots, zero pending notes
    expect(doc.querySelectorAll(".om-clip-pending").length).toBe(0);
    const slots = [...doc.querySelectorAll<HTMLElement>(".om-clip-slot")];
    expect(slots).toHaveLength(5);
    for (const slot of slots) {
      expect(slot.dataset.src).toMatch(/\.mp4$/);
      // Vite inlines sub-4KB caption files as data: URIs; either form is a
      // valid <track src>. A dev server hands back the raw .vtt path instead.
      expect(slot.dataset.captions).toMatch(/(^data:text\/vtt|\.vtt$)/);
      expect(slot.dataset.poster).toMatch(/poster\.png$/);
    }
  });
});
