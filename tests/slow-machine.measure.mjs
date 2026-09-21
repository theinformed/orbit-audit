/**
 * Measure the site on a slow machine before deciding what to build for one.
 *
 * Sean's instruction was measure first: a prefetch button, pre-baked binary
 * artifacts and any other slow-machine work should be aimed at whatever this
 * script says is actually slow, not at a guess. So this reports numbers and
 * asserts nothing. It is not part of the spec suite and no deploy depends on
 * it.
 *
 * What it emulates, and why those numbers:
 *   - CPU throttled 6x. Chrome's own mobile-tier default, and a fair stand-in
 *     for an eight-year-old locked-down desktop that is also running an EDR
 *     agent and a full-disk-encryption filter driver.
 *   - A constrained network: 1.5 Mbit down, 384 kbit up, 300 ms round trip.
 *     Not 3G - a government LAN behind a busy proxy, which is the realistic
 *     case for a METOC watch floor.
 *   - Software WebGL, because SwiftShader is what a machine with no usable GPU
 *     driver falls back to, and that is the population this is about.
 *
 * Usage, against an already-running preview server:
 *   node tests/slow-machine.measure.mjs [url] [--cpu 6] [--fast-network]
 *
 * Every duration is milliseconds measured from the action, and every one is
 * wall clock as the visitor would experience it.
 */
import { chromium } from "@playwright/test";

const url = process.argv.find((a) => a.startsWith("http")) ?? "http://127.0.0.1:4173/";
const cpuIndex = process.argv.indexOf("--cpu");
const cpuRate = cpuIndex > -1 ? Number(process.argv[cpuIndex + 1]) : 6;
const fastNetwork = process.argv.includes("--fast-network");

// The heavy layers, in the order a visitor meets them. Each is switched on
// alone, timed until its key card stops saying it is working, and switched off
// again, so the numbers do not accumulate on top of each other.
// `layer` is the app's own LayerName, which is what the key card is tagged
// with; the control id is not derivable from it (solarWind is
// `layer-solar-wind`, and `magnetosphere` is a boundary annotation with no
// layer- prefix at all), so both are written out.
const LAYERS = [
  { id: "layer-aurora", layer: "aurora", label: "aurora" },
  { id: "layer-ionosphere", layer: "ionosphere", label: "ionosphere" },
  { id: "layer-radiation", layer: "radiation", label: "radiation belts" },
  { id: "layer-geospace", layer: "geospace", label: "magnetosphere field lines" },
  { id: "layer-plasmasphere", layer: "plasmasphere", label: "plasmasphere" },
  { id: "layer-solar-wind", layer: "solarWind", label: "solar wind" },
  { id: "layer-drap", layer: "drap", label: "D-region absorption" },
];

const round = (value) => Math.round(value);

async function main() {
  const browser = await chromium.launch({
    args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader-webgl"],
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const client = await context.newCDPSession(page);
  await client.send("Emulation.setCPUThrottlingRate", { rate: cpuRate });
  await client.send("Network.enable");

  // Counted off the wire rather than from content-length: the preview server
  // replies chunked, so the header is absent and a header-based count silently
  // reports zero bytes for a site that just transferred megabytes.
  let bytes = 0;
  let requests = 0;
  client.on("Network.requestWillBeSent", () => { requests += 1; });
  client.on("Network.loadingFinished", (event) => { bytes += event.encodedDataLength ?? 0; });

  if (!fastNetwork) {
    await client.send("Network.emulateNetworkConditions", {
      offline: false,
      downloadThroughput: (1.5 * 1024 * 1024) / 8,
      uploadThroughput: (384 * 1024) / 8,
      latency: 300,
    });
  }

  const report = { url, cpuThrottle: cpuRate, network: fastNetwork ? "unthrottled" : "1.5 Mbit / 300 ms", layers: {} };

  const start = Date.now();
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 300_000 });
  report.domContentLoadedMs = round(Date.now() - start);

  // The welcome dialog is the first thing a visitor sees, so time to *that* is
  // the number that decides whether the site feels dead on arrival.
  await page.locator("#welcome-dialog").waitFor({ state: "visible", timeout: 300_000 });
  report.welcomeVisibleMs = round(Date.now() - start);
  await page.locator("#welcome-dialog .primary-button").click();

  // Satellites plotted: the site's own readiness signal.
  await page
    .locator("#visible-count")
    .filter({ hasText: /shown/ })
    .waitFor({ state: "visible", timeout: 300_000 });
  report.satellitesPlottedMs = round(Date.now() - start);
  report.satellitesShown = (await page.locator("#visible-count").textContent())?.trim();

  const firstPaint = await page.evaluate(() => {
    const entry = performance.getEntriesByName("first-contentful-paint")[0];
    return entry ? Math.round(entry.startTime) : null;
  });
  report.firstContentfulPaintMs = firstPaint;

  // One layer at a time, from cold. Nothing has to be switched into first:
  // Explorer Mode was retired on 2026-08-28 and the layer controls are always
  // in the document.
  const advanced = page.locator("details.advanced-environment-details");
  if (await advanced.count()) await advanced.evaluate((element) => { element.open = true; });

  for (const layer of LAYERS) {
    const toggle = page.locator(`#${layer.id}`);
    if (!(await toggle.count())) {
      report.layers[layer.label] = { skipped: "control not present" };
      continue;
    }
    const began = Date.now();
    await toggle.check();
    // A layer is ready when its key card exists and is no longer empty: the
    // card is written from the same data the scene draws, so it cannot report
    // ready before the field is there.
    const card = page.locator(`#key-cards .key-card[data-layer="${layer.layer}"]`);
    const ready = await card
      .first()
      .waitFor({ state: "visible", timeout: 120_000 })
      .then(() => true)
      .catch(() => false);
    report.layers[layer.label] = {
      readyMs: ready ? round(Date.now() - began) : null,
      timedOut: !ready,
    };
    await toggle.uncheck().catch(() => {});
  }

  // Interaction cost: how many frames the globe manages while being dragged.
  const frames = await page.evaluate(async () => {
    let count = 0;
    const until = performance.now() + 3000;
    return await new Promise((resolve) => {
      const tick = () => {
        count += 1;
        if (performance.now() < until) requestAnimationFrame(tick);
        else resolve(count);
      };
      requestAnimationFrame(tick);
    });
  });
  report.idleFramesPerSecond = round(frames / 3);

  report.requests = requests;
  report.bytesOverTheWire = bytes;
  report.megabytesOverTheWire = Math.round((bytes / (1024 * 1024)) * 10) / 10;
  report.totalMs = round(Date.now() - start);

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
