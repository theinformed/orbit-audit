import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  // WSL Chromium uses SwiftShader for WebGL. The full production teaching
  // flow now exercises several on-demand scientific fields; software WebGL
  // can exceed three minutes even though hardware-backed browsers are fast.
  timeout: 240_000,
  fullyParallel: false,
  reporter: "line",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    {
      // The tablet layout, at the width it has always been tested at, but
      // without the emulation that made it unclickable.
      //
      // This used to spread `devices["iPad Pro 11"]` and force
      // deviceScaleFactor to 1. That descriptor is 834x1194 at scale 2 with
      // isMobile set, and overriding only the scale leaves Chromium applying a
      // 1.30x page scale: the layout viewport came out 1084x1552 while the
      // device stayed 834 wide. Layout and input then disagree. Playwright
      // computes a click point from getBoundingClientRect, in layout pixels,
      // and the browser hit-tests it in the visual viewport, so the pointer
      // lands somewhere else entirely -- measured on the ground-track dialog's
      // close button, which held ONE position across 40 consecutive frames,
      // was never covered (elementFromPoint returned the button itself), and
      // still could not be clicked. Activating it directly closed the dialog,
      // and the same interaction at a plain 834x1194 viewport worked first
      // time, which is what proved the site was never at fault.
      //
      // So the effective 1084x1552 is now stated outright rather than arrived
      // at by accident. Keeping that size keeps every tablet expectation on the
      // breakpoints it was written against; dropping isMobile is what makes the
      // two viewports one. Touch stays on, because the touch contract is the
      // reason this project exists.
      name: "tablet",
      use: {
        browserName: "chromium",
        viewport: { width: 1084, height: 1552 },
        deviceScaleFactor: 1,
        hasTouch: true,
        isMobile: false,
      },
    },
    {
      name: "mobile",
      use: {
        ...devices["iPhone 13"],
        browserName: "chromium",
        // WSL headless Chromium renders WebGL in software. Keep the iPhone
        // layout/touch contract without multiplying that software canvas 3×.
        deviceScaleFactor: 1,
      },
    },
  ],
  webServer: [
    {
      // EVERY public asset index.html REFERENCES must be copied in by hand here.
      // `publicDir: false` (below) is what stops the ~77 GB data tree being
      // copied, and it stops everything else in public/ too. index.html loads
      // ./feedback-widget.js, ./icon-512.png, ./apple-touch-icon.png and
      // ./social-card.png; only favicon.svg was ever copied, so every run
      // produced four 404s, and `browser.spec.ts` asserts an EMPTY console-error
      // array. That single missing file made the whole browser lane unpassable
      // for any agent using the documented verification config -- red from
      // 2026-08-26 to 2026-08-29, during which six separate agents each
      // correctly reported it as "pre-existing, not mine" and moved on. A lane
      // that cannot go green catches nothing, so nobody was gated by it either.
      //
      // If you add an asset reference to index.html, add it to the copy list.
      //
      // NEVER the default build here: public/data is a real ~77 GB directory
      // on the main tree and the default config copies it into dist — the
      // webServer then dies at its own timeout mid-copy (observed: 23 GB of
      // partial copy). Build with the verify config (publicDir off), then
      // symlink the served /data to the real directory.
      command: "npx tsc -b && npx vite build --config vite.verify.config.ts --emptyOutDir && cp public/favicon.svg public/feedback-widget.js public/icon-512.png public/apple-touch-icon.png public/social-card.png dist/ && ln -sfn \"$PWD/public/data\" dist/data && npm run preview -- --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      // The rendering guards drive small harness pages that instantiate the
      // globe on its own. They are served in dev so they stay out of the
      // production build and are never deployed.
      command: "npm run dev -- --port 4174 --strictPort",
      url: "http://127.0.0.1:4174/tests/footprint-fill.harness.html",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
