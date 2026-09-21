import { describe, expect, it } from "vitest";

/**
 * Is the feature actually *in the site*?
 *
 * This project has now shipped two features that compiled, passed their unit
 * tests, and did not exist on the page: the transit planner, and then the
 * cusped magnetopause and the storm panel. In both cases every module was
 * correct and nothing imported it, so the bundler dropped it and the deployed
 * site kept drawing the old thing. A green test suite was not merely
 * insufficient evidence of reachability — it was zero evidence, because a unit
 * test imports the module itself and therefore proves nothing about whether the
 * application does.
 *
 * So this file tests the one thing those suites could not: that a module is
 * reachable by following real `import` statements from the entry point the
 * browser actually loads. It is deliberately crude — a regex over source text,
 * not a resolver — because a subtle graph walker is a thing that can be wrong
 * in the same silent direction as the bug.
 *
 * It is still not a substitute for looking at the built bundle or at the page.
 * A module can be imported and never called. What it does catch is the exact
 * failure that has now happened twice, and it catches it in CI rather than in
 * front of the owner.
 */

/** Source text, keyed by repository-relative path. No node builtins needed. */
const sources = Object.fromEntries(
  Object.entries(
    import.meta.glob("../src/**/*.ts", { eager: true, query: "?raw", import: "default" }),
  )
    .map(([key, value]) => [key.replace(/^\.\.\//, ""), value as string])
    // Ambient declaration files are never imported by anything — that is what
    // ambient means — so they are not modules this test can reason about, and
    // listing one as an orphan would be a false positive rather than a finding.
    .filter(([key]) => !String(key).endsWith(".d.ts")),
) as Record<string, string>;

const html = Object.values(
  import.meta.glob("../index.html", { eager: true, query: "?raw", import: "default" }),
)[0] as string;

// The flag-enabled build replaces the document body with this actual template.
// Walk both shipped variants; this is an entry point, not an orphan exemption.
const deliveryTemplate = Object.values(
  import.meta.glob("../tools/delivery-build.ts", { eager: true, query: "?raw", import: "default" }),
)[0] as string;

/** Every relative specifier in one source file. */
function relativeImports(source: string): string[] {
  const specifiers: string[] = [];
  const patterns = [
    /\bimport\s+[^;]*?\bfrom\s*["']([^"']+)["']/g,
    /\bimport\s*["']([^"']+)["']/g,
    /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g,
    /\bexport\s+[^;]*?\bfrom\s*["']([^"']+)["']/g,
    /new\s+URL\s*\(\s*["']([^"']+)["']/g,
  ];
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) specifiers.push(match[1]!);
  }
  return specifiers.filter((specifier) => specifier.startsWith("."));
}

/** Resolve `./foo` relative to `src/globe.ts` into `src/foo.ts`, if that exists. */
function resolveModule(fromFile: string, specifier: string): string | null {
  const parts = fromFile.split("/").slice(0, -1);
  for (const segment of specifier.split("/")) {
    if (segment === "." || segment === "") continue;
    if (segment === "..") parts.pop();
    else parts.push(segment);
  }
  const base = parts.join("/");
  for (const candidate of [base, `${base}.ts`, `${base}/index.ts`]) {
    if (candidate in sources) return candidate;
  }
  // CSS, worker assets and anything outside src/ fall through: they are
  // reachable by definition once the module importing them is.
  return null;
}

function reachableFromEntry(): Set<string> {
  // Every module entry the page loads, not only the first: the energy-chain
  // walkthrough is deliberately its own <script type="module"> so its failure
  // can never take down the globe, and rooting the walk at one entry would
  // report its whole subtree as orphaned.
  const entries = [...`${html}\n${deliveryTemplate}`.matchAll(/<script[^>]*type="module"[^>]*src="([^"]+)"/g)]
    .map((match) => match[1]!.replace(/^\//, ""));
  expect(entries.length, "index.html must load a module entry point").toBeGreaterThan(0);
  const seen = new Set<string>();
  const queue = [...entries];
  while (queue.length) {
    const file = queue.pop()!;
    if (seen.has(file) || !(file in sources)) continue;
    seen.add(file);
    for (const specifier of relativeImports(sources[file]!)) {
      const resolved = resolveModule(file, specifier);
      if (resolved && !seen.has(resolved)) queue.push(resolved);
    }
  }
  return seen;
}

describe("every source module is reachable from the page the browser loads", () => {
  const reachable = reachableFromEntry();

  it("starts from the entry point index.html actually names", () => {
    expect(reachable.has("src/main.ts")).toBe(true);
    expect(reachable.size).toBeGreaterThan(20);
  });

  it("reaches the entrance that the constrained-delivery build actually emits", () => {
    expect(reachable.has("src/delivery-entry.ts")).toBe(true);
    expect(reachable.has("src/delivery-policy.ts")).toBe(true);
  });

  // The modules that were merged, tested, deployed and absent. Three more
  // joined the list on 2026-08-09: the ground-station overlay and the
  // orbit-manoeuvre browser with its data layer, all of which had been sitting
  // built and unreachable behind the same bottleneck — the two files every
  // feature needs its last two lines in.
  for (const file of [
    "magnetopause-surfaces.ts",
    "dipole-tilt.ts",
    "storm-panel.ts",
    "storm-indices.ts",
    "ground-stations.ts",
    "orbit-history-browser.ts",
    "orbit-history.ts",
  ]) {
    it(`reaches src/${file}`, () => {
      expect(
        reachable.has(`src/${file}`),
        `src/${file} is not reachable by any import chain from the entry point, so the `
        + "bundler will drop it and the feature will not exist on the site.",
      ).toBe(true);
    });
  }

  it("names every unreachable module, so a new orphan is visible rather than silent", () => {
    /*
     * ⚠️ These are not exemptions. Every name below is a module that is built,
     * tested and **not on the site** — found by this test on the day it was
     * written, while wiring the previous two. They are listed rather than
     * silently ignored so the count can only go down, and so a newly orphaned
     * module fails this test on the commit that orphans it.
     *
     * The list may only shrink. It went from four to one on 2026-08-09 when
     * `ground-stations.ts`, `orbit-history-browser.ts` and `orbit-history.ts`
     * were wired; each is now asserted reachable above, so re-orphaning one
     * fails this file twice rather than quietly re-earning a place here.
     *
     *   methods.ts   the "how this was built" content view. Still dark, and
     *                still not this task's: `src/content.ts` already renders a
     *                Data & methods view that the rail links to, so what
     *                `methods.ts` should replace or become is a question about
     *                the site rather than a missing import.
     */
    const allowed = new Set([
      "src/methods.ts",
    ]);
    const orphans = Object.keys(sources)
      .filter((file) => !reachable.has(file) && !allowed.has(file))
      .sort();
    expect(orphans).toEqual([]);
  });
});
