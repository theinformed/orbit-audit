// Is the new card prose REACHABLE by a reader? This project has shipped
// features that compiled, passed their unit tests and did not exist on the
// page, twice. Drives the real page and reads the real DOM.
import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
p.setDefaultTimeout(300000);
await p.addInitScript(() => { try { window.localStorage.setItem("space-explorer-hide-welcome-v1","1"); } catch {} });
await p.route("**/src/main.ts*", async (route) => {
  const s = await fetch(route.request().url()).then((r) => r.text());
  await route.fulfill({ body: s.replace("new ExplorerApp(manifest, catalog, weather, events, land);", "globalThis.__app = new ExplorerApp(manifest, catalog, weather, events, land);"), contentType: "text/javascript" });
});
await p.goto(process.argv[2] ?? "http://127.0.0.1:5317/", { waitUntil: "domcontentloaded" });
await p.waitForFunction(() => Boolean(globalThis.__app), null, { timeout: 300000 });
await p.waitForTimeout(11000);
await p.evaluate(() => { const el = document.querySelector('[data-explorer-mode="environment"]'); if (el) el.click(); });
await p.waitForTimeout(4000);
await p.evaluate(async () => {
  for (const id of ["layer-geospace","layer-solar-wind","layer-ring-current","layer-radiation"]) {
    const el = document.getElementById(id);
    if (el && !el.checked) { el.click(); await new Promise((r)=>setTimeout(r,300)); }
  }
});
await p.waitForTimeout(9000);
await p.evaluate(() => { for (const c of document.querySelectorAll("#data-viewer-cards > *")) { const t = c.querySelector("button"); if (t) t.click(); } });
await p.waitForTimeout(3000);
// The prose lives one level deeper, behind "More about this description".
await p.evaluate(() => { for (const el of document.querySelectorAll("button, summary")) { if ((el.textContent || "").toLowerCase().includes("more about")) el.click(); } });
await p.waitForTimeout(2500);
const info = await p.evaluate(() => ({
  bodyLen: document.body.innerText.length,
  cards: [...document.querySelectorAll("#data-viewer-cards > *")].map((c) => c.innerText.slice(0, 60)),
  solarWind: [...document.querySelectorAll("#data-viewer-cards > *")]
    .map((c) => c.innerText).find((t) => t.includes("Solar wind")) ?? null,
}));
console.log("bodyLen", info.bodyLen);
console.log("=== SOLAR WIND CARD ===");
console.log(info.solarWind);
console.log("=== END ===");
const text = await p.evaluate(() => document.body.innerText);
for (const probe of ["antisunward over the polar cap","TWO EVIDENCE CLASSES","WHAT A PARTICLE IS DECIDES",
  "AND THE RADIATION BELTS?","AND THEN IT IS TRAPPED","AND THEN IT LEAVES","one part in 214",
  "fifteen times slower","IMAGE and TWINS","Magnetopause shadowing","Coulomb drag",
  "WHAT YOU CAN SEE instead","A BUILD, THEN A LONGER RECOVERY","PULSE"]) {
  console.log((text.includes(probe) ? "REACHABLE  " : "MISSING    ") + probe);
}
await b.close();
