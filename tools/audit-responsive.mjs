import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const targets = [
  { name: "rp33", url: "https://sean.theinformed.org/not-pc-imat/" },
  { name: "skewt", url: "https://sean.theinformed.org/skew-t/" },
  { name: "space", url: "http://127.0.0.1:4173/" },
];

const viewports = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "ipad-portrait", width: 820, height: 1180 },
  { name: "ipad-landscape", width: 1180, height: 820 },
  { name: "iphone", width: 390, height: 844 },
];

const outputDirectory = process.argv[2] ?? "/tmp/space-responsive-audit";
await mkdir(outputDirectory, { recursive: true });

const browser = await chromium.launch({ headless: true });
const report = [];

for (const target of targets) {
  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport });
    page.setDefaultTimeout(60_000);
    await page.route("**/*", async (route) => {
      if (route.request().resourceType() === "font") {
        await route.abort();
        return;
      }
      await route.continue();
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });

    const response = await page.goto(target.url, {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    if (target.name === "space") {
      await page.locator("#visible-count").filter({ hasText: "shown" }).waitFor({ timeout: 35_000 });
    } else {
      await page.waitForTimeout(4_000);
    }

    const metrics = await page.evaluate(() => {
      const visible = (element) => {
        if (!(element instanceof HTMLElement)) return false;
        const style = getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      };
      const candidates = [
        "header",
        "nav",
        "aside",
        "#control-rail",
        "#satellite-card",
        "#mobile-panel-toggle",
        ".drawer",
        ".sidebar",
        ".bottom-sheet",
      ];
      const regions = candidates.flatMap((selector) =>
        [...document.querySelectorAll(selector)].filter(visible).map((element) => {
          const box = element.getBoundingClientRect();
          return {
            selector,
            id: element.id,
            classes: element.className,
            x: Math.round(box.x),
            y: Math.round(box.y),
            width: Math.round(box.width),
            height: Math.round(box.height),
          };
        }),
      );
      return {
        title: document.title,
        viewport: { width: innerWidth, height: innerHeight },
        page: {
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          clientHeight: document.documentElement.clientHeight,
          scrollHeight: document.documentElement.scrollHeight,
        },
        visibleButtons: [...document.querySelectorAll("button")].filter(visible).length,
        regions,
      };
    });

    const screenshot = `${outputDirectory}/${target.name}-${viewport.name}.png`;
    await page.screenshot({
      path: screenshot,
      fullPage: false,
      animations: "disabled",
      timeout: 60_000,
    });
    report.push({
      target: target.name,
      url: target.url,
      viewport: viewport.name,
      status: response?.status(),
      errors,
      screenshot,
      metrics,
    });
    await page.close();
  }
}

await browser.close();
await writeFile(`${outputDirectory}/report.json`, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
