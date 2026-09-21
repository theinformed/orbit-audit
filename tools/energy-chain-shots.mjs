// Screenshot harness for "Follow the energy", the coupled-chain walkthrough.
//
// It does what a reader does: switch to Space weather, open the walkthrough,
// and press Next seven times. Every shot is the real built site against the
// real published artifacts, and every console error is reported at the end —
// a green build has lied about work on this site before.
//
// Clicks go through `press`, which tries a real user click first and falls
// back to dispatching one. The fallback exists because the globe animates
// continuously and Playwright's actionability wait can sit in
// `scrollIntoViewIfNeeded` forever on a scene that never goes idle — which
// cost a whole eight-step run before this was written. The fallback REPORTS
// itself, so a genuinely unclickable control is still visible in the log
// rather than papered over.
//
// Usage: node shots.mjs <outDir> [baseURL]
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:4173/";
mkdirSync(outDir, { recursive: true });

const errors = [];
const forced = [];
const stalls = [];

/**
 * Click by dispatch, not by Playwright's actionability path.
 *
 * The scene stalls its own main thread for many seconds while a heavy layer is
 * built - measured on the shipped build, `locator.evaluate` itself timed out
 * at 30 s stepping from link 05 to link 06 - and a click that times out mid
 * retry can still have landed, so the fallback path double-advanced the
 * walkthrough and photographed the wrong steps. Dispatching is deterministic.
 * The stall is reported separately rather than hidden.
 */
async function press(page, selector, label) {
  const started = Date.now();
  const ok = await page.evaluate((sel) => {
    const node = document.querySelector(sel);
    if (!node) return false;
    node.click();
    return true;
  }, selector);
  const waited = Date.now() - started;
  if (waited > 2000) stalls.push(`${label ?? selector}: main thread blocked ${waited} ms`);
  if (!ok) forced.push(`${label ?? selector}: no such element`);
}

/**
 * A screenshot survives a stalled main thread.
 *
 * Building the radiation-belt volume has been measured blocking the page for
 * over thirty seconds on a machine running other work, and Playwright's
 * default screenshot timeout is thirty. Losing an eight-step run to that is
 * worse than waiting: the stall is already reported by `press`.
 */
async function shot(page, name) {
  try {
    await page.screenshot({ path: `${outDir}/${name}.png`, timeout: 30_000 });
  } catch {
    stalls.push(`${name}: screenshot needed a second attempt`);
    await page.screenshot({ path: `${outDir}/${name}.png`, timeout: 120_000, animations: "disabled" });
  }
  console.log("shot", name);
}

async function readStep(page) {
  return page.evaluate(() => {
    const panel = document.getElementById("energy-chain-panel");
    if (!panel || panel.hidden) return null;
    const readings = [...panel.querySelectorAll(".chain-walk__readings > dd > strong")].map((n) => n.textContent);
    const labels = [...panel.querySelectorAll(".chain-walk__reading-label")].map((n) => n.firstChild?.textContent?.trim());
    const body = panel.querySelector(".chain-walk__body");
    return {
      index: [...panel.querySelectorAll(".chain-walk__node")].find((n) => n.classList.contains("is-active"))?.textContent,
      role: panel.querySelector(".chain-walk__step-role")?.textContent,
      onTheGlobe: panel.querySelector(".chain-walk__globe")?.textContent?.slice(0, 70) ?? null,
      absent: [...panel.querySelectorAll(".chain-walk__absent")].map((n) => n.textContent.slice(0, 50)),
      clipped: panel.querySelector(".chain-walk__body")?.classList.contains("is-clipped") ?? null,
      hasScale: !!panel.querySelector(".chain-walk__scale-chart"),
      title: panel.querySelector(".chain-walk__step-title")?.textContent,
      badge: panel.querySelector(".chain-walk__step-badge")?.textContent,
      verdict: panel.querySelector(".chain-walk__verdict strong")?.textContent,
      counter: panel.querySelector(".chain-walk__counter")?.textContent,
      missing: panel.querySelector(".chain-walk__missing")?.textContent ?? null,
      handoff: panel.querySelector(".chain-walk__handoff")?.textContent?.slice(0, 120) ?? null,
      hasSpark: !!panel.querySelector(".chain-walk__spark-chart"),
      hasFigure: !!panel.querySelector(".chain-walk__figure"),
      // How much of the card the reader cannot see without scrolling. This is
      // the number the redesign is judged on: a step whose one idea is below
      // the fold has not shown what it intends to show.
      hiddenPx: body ? Math.max(0, body.scrollHeight - body.clientHeight) : null,
      readings: labels.map((label, index) => `${label} = ${readings[index]}`),
      layersOn: [...document.querySelectorAll('#layer-list input[type=checkbox], #layer-drap')]
        .filter((box) => box.checked).map((box) => box.id),
      camera: window.__chainCameraProbe ?? null,
    };
  });
}

async function openRail(page, phone) {
  if (!phone) return;
  const toggle = page.locator("#mobile-panel-toggle");
  if (!(await toggle.isVisible().catch(() => false))) return;
  const open = await page.locator("#control-rail").evaluate((el) => el.classList.contains("is-open"));
  if (!open) { await toggle.click(); await page.waitForTimeout(500); }
}

async function closeRail(page, phone) {
  if (!phone) return;
  const open = await page.locator("#control-rail").evaluate((el) => el.classList.contains("is-open")).catch(() => false);
  if (open) { await page.locator("#mobile-panel-toggle").click(); await page.waitForTimeout(500); }
}

async function run(label, viewport, phone = false) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  page.on("console", (m) => { if (m.type() === "error") errors.push(`[${label}] ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`[${label}] ${String(e)}`));
  await page.addInitScript(() => {
    try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
  });

  await page.goto(baseURL, { waitUntil: "load" });
  const welcome = page.locator("#welcome-dialog");
  if (await welcome.isVisible().catch(() => false)) {
    await page.locator("#welcome-dialog .primary-button").click();
  }
  await page.waitForFunction(() => {
    const status = document.getElementById("data-status");
    return status && (status.classList.contains("is-live") || status.classList.contains("is-stale"));
  }, null, { timeout: 60_000 });
  await page.waitForTimeout(3000);

  await openRail(page, phone);
  await press(page, '[data-explorer-mode="environment"]', "mode:environment");
  await page.waitForTimeout(1500);
  await shot(page, `${label}-00-launcher`);
  // The launcher, wherever it is, framed on its own so the placement decision
  // can be judged rather than guessed at from a full-page shot.
  const launcher = page.locator("#energy-chain-open");
  const box = await launcher.boundingBox().catch(() => null);
  // The launcher's own neighbourhood, so the placement decision can be judged
  // rather than guessed at from a full-page shot. On a phone the rail is a
  // sheet and the button can sit outside the viewport entirely, which is not a
  // failure worth ending a run over.
  const clip = box && {
    x: Math.max(0, Math.min(box.x - 20, viewport.width - 10)),
    y: Math.max(0, Math.min(box.y - 150, viewport.height - 10)),
    width: Math.min(box.width + 40, viewport.width - Math.max(0, box.x - 20)),
    height: Math.min(box.height + 230, viewport.height - Math.max(0, box.y - 150)),
  };
  if (clip && clip.width > 4 && clip.height > 4) {
    await page.screenshot({ path: `${outDir}/${label}-00b-launcher-closeup.png`, clip });
    console.log("shot", `${label}-00b-launcher-closeup`);
  } else {
    console.log("launcher not in view for", label, JSON.stringify(box));
  }

  await press(page, "#energy-chain-open", "launcher");
  await closeRail(page, phone);
  // The panel opens on the click, but the first card is only filled in when
  // the 1.4 MB bundle lands, and that has been measured taking over nine
  // seconds on a machine running three other browsers. Photographing the
  // empty state as if it were the design is the mistake this whole harness
  // exists to prevent.
  await page.waitForTimeout(16000);

  const steps = [];
  for (let index = 0; index < 9; index += 1) {
    if (index > 0) {
      await press(page, ".chain-walk__nav--primary", `next->${index + 1}`);
      // Long enough for the geospace bundle (2.7 MB) to land and for anything
      // that re-frames on arrival to have done so. Shorter waits photographed
      // a camera that the scene then moved.
      await page.waitForTimeout(6000);
    }
    const state = await readStep(page);
    steps.push(state);
    await shot(page, `${label}-${String(index + 1).padStart(2, "0")}-${state?.index ?? "none"}-${(state?.title ?? "step").toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 28)}`);
  }

  await press(page, ".chain-walk__track-item:nth-child(2) .chain-walk__node", "node:02");
  await page.waitForTimeout(3500);
  await shot(page, `${label}-09-jump-back-to-02`);

  await press(page, ".chain-walk__replay", "replay");
  await page.waitForTimeout(5000);
  const replay = await readStep(page);
  await shot(page, `${label}-10-replay-mid`);
  await press(page, ".chain-walk__replay", "replay-stop");
  await page.waitForTimeout(1000);

  await press(page, ".chain-walk__track-item:nth-child(8) .chain-walk__node", "node:X1");
  await page.waitForTimeout(5000);
  const branch = await readStep(page);
  await shot(page, `${label}-11-branch-xray`);

  const before = await page.evaluate(() => [...document.querySelectorAll("#layer-list input[type=checkbox]")].filter((b) => b.checked).map((b) => b.id));
  await press(page, ".chain-walk__close", "close");
  await page.waitForTimeout(2500);
  const after = await page.evaluate(() => ({
    layers: [...document.querySelectorAll("#layer-list input[type=checkbox]")].filter((b) => b.checked).map((b) => b.id),
    offset: document.getElementById("time-slider").value,
    hidden: document.getElementById("energy-chain-panel").hidden,
  }));
  await shot(page, `${label}-12-closed-restored`);

  await press(page, '[data-view="learn-weather"]', "learn-weather").catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, `${label}-13-learn-weather-door`);

  await browser.close();
  return { steps, replay, branch, before, after };
}

const only = process.env.SHOT_ONLY ?? "";
const desktop = only === "phone" ? { steps: [] } : await run("desktop", { width: 1440, height: 900 }, false);
const phone = only === "desktop" ? { steps: [] } : await run("phone", { width: 390, height: 844 }, true);

console.log("\n=== desktop steps ===");
for (const step of desktop.steps) console.log(JSON.stringify(step));
console.log("\n=== phone steps ===");
for (const step of phone.steps) console.log(JSON.stringify({ index: step?.index, title: step?.title, hiddenPx: step?.hiddenPx }));
console.log("\n=== replay frame ===", JSON.stringify(desktop.replay?.readings));
console.log("=== branch ===", JSON.stringify(desktop.branch));
console.log("=== layers before close ===", JSON.stringify(desktop.before));
console.log("=== after close ===", JSON.stringify(desktop.after));
console.log("\n=== clicks that found no element:", forced.length, "===");
for (const f of forced) console.log(" missing:", f);
console.log("=== main-thread stalls over 2 s:", stalls.length, "===");
for (const f of stalls) console.log(" stall:", f);
console.log("\n=== console errors:", errors.length, "===");
for (const error of errors.slice(0, 20)) console.log(error);
