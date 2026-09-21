// Reproduces the coordinator's production check exactly: 1440x900, only the
// ionosphere layer on, the DEFAULT camera the site opens with -- no custom
// framing, no hidden chrome. Then the same view with TEC, and a hard zoom on
// the limb to look for banding.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2];
const baseURL = process.argv[3] ?? "http://127.0.0.1:5401/";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.addInitScript(() => {
  try { window.localStorage.setItem("space-explorer-hide-welcome-v1", "1"); } catch { /* ignore */ }
});
await page.route("**/assets/index-*.js", async (route) => {
  const source = await fetch(route.request().url()).then((r) => r.text());
  const body = source.replace(
    "new ExplorerApp(manifest, catalog, weather, events, land);",
    "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);",
  );
  if (body === source) throw new Error("patch point not found");
  await route.fulfill({ body, contentType: "text/javascript" });
});
page.setDefaultTimeout(240000);
await page.goto(baseURL, { waitUntil: "domcontentloaded", timeout: 240000 });
await page.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 150000 });
await page.waitForTimeout(9000);
await page.locator('[data-explorer-mode="environment"]').click();
await page.waitForTimeout(2500);

const setLayers = async (on) => page.evaluate(async (wanted) => {
  const ids = ["layer-ionosphere", "layer-tec", "layer-drap", "layer-aurora",
    "layer-thermosphere", "layer-geospace", "layer-solar-wind", "layer-photons", "layer-radiation"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.checked !== wanted.includes(id)) { el.click(); await new Promise((r) => setTimeout(r, 160)); }
  }
}, on);

await setLayers(["layer-ionosphere"]);
await page.waitForTimeout(20000);

const shot = async (name, clip, settle = 2500) => {
  await page.waitForTimeout(settle);
  await page.screenshot({ path: `${outDir}/${name}.png`, ...(clip ? { clip } : {}) });
  console.log("shot", name);
};

const picker = await page.evaluate(() => {
  const c = document.getElementById("ionosphere-subcontrols");
  const sel = document.getElementById("ionosphere-altitude-range");
  const r = c.getBoundingClientRect();
  return { ariaHidden: c.getAttribute("aria-hidden"), isVisible: c.classList.contains("is-visible"),
           height: Math.round(r.height), options: [...sel.options].map((o) => o.value) };
});
console.log("BAND PICKER", JSON.stringify(picker));

// 1. Exactly what the coordinator saw: default view, full page.
await shot("01-default-view-full");

// 2. How much of the black background is tinted? Sample corner pixels.
const tint = await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const gl = globe.renderer.getContext();
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  globe.renderer.render(globe.scene, globe.camera);
  const read = (x, y) => {
    const p = new Uint8Array(4);
    gl.readPixels(x, h - 1 - y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, p);
    return [p[0], p[1], p[2]];
  };
  return {
    topLeft: read(4, 4), topRight: read(w - 5, 4),
    bottomLeft: read(4, h - 5), bottomRight: read(w - 5, h - 5),
    midLeft: read(4, Math.round(h / 2)),
    size: [w, h],
  };
});
console.log("BACKGROUND TINT", JSON.stringify(tint));

// 3. Hard zoom on the limb, looking for concentric banding.
await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  const cam = globe.camera;
  cam.position.set(0, 0, 260);
  globe.controls.target.set(0, 0, 0);
  cam.updateProjectionMatrix();
  globe.controls.update();
});
await shot("02-limb-zoom", { x: 120, y: 120, width: 620, height: 620 });

// 4. Same, band-isolated to the F2 shell, where rings would be most visible.
await page.evaluate(() => {
  const el = document.getElementById("ionosphere-altitude-range");
  el.value = "200:800";
  el.dispatchEvent(new Event("change", { bubbles: true }));
});
await shot("03-limb-zoom-f2-band", { x: 120, y: 120, width: 620, height: 620 });
await page.evaluate(() => {
  const el = document.getElementById("ionosphere-altitude-range");
  el.value = "60:2655";
  el.dispatchEvent(new Event("change", { bubbles: true }));
});

// 5. With TEC, default view.
await page.evaluate(() => {
  const globe = globalThis.__app.globe;
  globe.camera.position.set(0, 70, 330);
  globe.controls.target.set(0, 0, 0);
  globe.camera.updateProjectionMatrix();
  globe.controls.update();
});
await setLayers(["layer-ionosphere", "layer-tec"]);
await shot("04-with-tec");

writeFileSync(`${outDir}/tint.json`, JSON.stringify({ tint, errors }, null, 2));
console.log("ERRORS", errors.length, errors.slice(0, 6));
await browser.close();
