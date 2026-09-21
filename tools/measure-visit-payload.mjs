// What one cold visit actually costs the VPS's egress allowance.
//
// Measures WIRE bytes, not decoded bytes. That distinction is the whole point:
// artifacts are served with Content-Encoding: gzip, so a first measurement that
// totalled decoded response bodies reported 13.97 MB for a visit that really
// costs about 3 MB. Reporting the decoded figure would have overstated the cost
// of hosting this site by more than fourfold and sent someone optimising a
// number that was never being billed.
//
// `request.sizes()` reports what came off the socket; `response.body()` reports
// what the browser handed the page after decompressing. Only the first one is
// traffic.
//
// Usage: node tools/measure-visit-payload.mjs [url]
import { chromium } from "@playwright/test";

const url = process.argv[2] ?? "https://sean.theinformed.org/space/";
// Hetzner's stated egress allowance for this VPS. Used only to turn bytes into
// a number of visits, which is the form the question is usually asked in.
const EGRESS_ALLOWANCE_BYTES = 3e12;

const browser = await chromium.launch();
// A fresh context every run: a warm cache would measure a return visit, and the
// number worth knowing is what a first-time reader costs.
const context = await browser.newContext();
const page = await context.newPage();

let wire = 0;
let decoded = 0;
const byKind = new Map();

function classify(pathname) {
  if (pathname.includes("/artifacts/")) {
    const name = pathname.split("/artifacts/")[1].replace(/-[0-9a-f]+\.json.*/, "");
    return name.startsWith("orbit-history") ? "artifact: orbit-history (shards)" : `artifact: ${name}`;
  }
  if (pathname.endsWith("manifest.json")) return "manifest";
  if (pathname.endsWith(".js")) return "javascript";
  if (pathname.endsWith(".css")) return "css";
  return "other";
}

page.on("response", async (response) => {
  try {
    const { responseBodySize, responseHeadersSize } = await response.request().sizes();
    const bytes = responseBodySize + responseHeadersSize;
    wire += bytes;
    decoded += (await response.body()).length;
    const kind = classify(new URL(response.url()).pathname);
    byKind.set(kind, (byKind.get(kind) ?? 0) + bytes);
  } catch {
    // A response whose body is gone by the time we ask (redirects, aborted
    // preloads) contributes nothing rather than crashing the measurement.
  }
});

await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
// The globe keeps fetching after networkidle: layers resolve, the worker warms
// up. Twelve seconds is empirically past the point where new requests stop.
await page.waitForTimeout(12000);

for (const [kind, bytes] of [...byKind].sort((a, b) => b[1] - a[1])) {
  console.log(`${(bytes / 1e6).toFixed(2).padStart(9)} MB  ${kind}`);
}
console.log("-".repeat(52));
console.log(`${(wire / 1e6).toFixed(2).padStart(9)} MB  TOTAL on the wire, one cold visit`);
console.log(`${(decoded / 1e6).toFixed(2).padStart(9)} MB  (decoded, for comparison -- NOT what is billed)`);
console.log(`${(EGRESS_ALLOWANCE_BYTES / wire).toLocaleString(undefined, { maximumFractionDigits: 0 }).padStart(9)}     such visits fit in the 3 TB egress allowance`);

// Hand the figure to the operations page. Written to a file of its own rather
// than into runtime/bandwidth/ledger.jsonl on purpose: this is not traffic that
// happened, it is a measurement of what one visit WOULD cost, taken by driving
// a browser deliberately. Adding a synthetic visit to a period total would make
// the act of measuring change the thing measured.
//
// `at` is when it was taken, and the page prints it, because a payload figure
// from three months ago is a different claim from one from this morning.
const out = process.env.SPACE_EXPLORER_VISIT_JSON
  ?? "runtime/bandwidth/visit-payload.json";
const { mkdir, writeFile } = await import("node:fs/promises");
const { dirname } = await import("node:path");
await mkdir(dirname(out), { recursive: true });
await writeFile(out, JSON.stringify({
  schema: 1,
  at: Date.now() / 1000,
  url,
  state: process.env.SPACE_EXPLORER_VISIT_STATE ?? "default (first-time visitor, cold cache)",
  wireBytes: wire,
  decodedBytes: decoded,
  byKind: Object.fromEntries(byKind),
  method: "Playwright request.sizes(): responseBodySize + responseHeadersSize, "
    + "which is what came off the socket. NOT response.body().length, which is "
    + "the decompressed length the page sees and overstates this fourfold.",
}, null, 2) + "\n");
console.log(`\nwrote ${out}`);

await browser.close();
