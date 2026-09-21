/// <reference types="vite/client" />
/**
 * Loading the *current* published artifacts in a test.
 *
 * Two traps this exists to avoid, both of which bit during development:
 *
 * 1. **`public/data/artifacts/` retains every past release.** There were 44
 *    `catalog-*.json` files in it. An eager glob loads all of them - eighteen
 *    seconds of transform - and then `Object.keys()[0]` hands you an arbitrary
 *    historical one, whose classification and hosted-payload fields predate the
 *    thing you are testing. A test written that way passes or fails according to
 *    which old release sorts first, which is worse than either.
 *
 * 2. **The manifest changes under you.** The release pipeline republished
 *    mid-session and the catalog hash moved. Anything that hardcodes a hash is
 *    correct until the next publish.
 *
 * So: read `manifest.json`, which is the release's own statement of what is
 * current, and load only the artifact it names, lazily.
 */

import type { CatalogBundle, ReleaseManifest } from "../src/types";
import type { LandGeoJson } from "../src/globe";
import manifest from "../public/data/manifest.json";

const artifactLoaders = import.meta.glob<{ default: unknown }>(
  "../public/data/artifacts/*.json",
);

async function loadArtifact<T>(path: string): Promise<T> {
  const key = `../public/data/${path}`;
  const loader = artifactLoaders[key];
  if (!loader) {
    throw new Error(
      `The manifest names ${path}, which is not present in public/data/artifacts. `
      + "Run the release pipeline, or check that the manifest and the artifacts agree.",
    );
  }
  return (await loader()).default as T;
}

export const releaseManifest = manifest as unknown as ReleaseManifest;

export function loadCatalog(): Promise<CatalogBundle> {
  return loadArtifact<CatalogBundle>(releaseManifest.catalog.path);
}

export function loadLand(): Promise<LandGeoJson> {
  return loadArtifact<LandGeoJson>(releaseManifest.land.path);
}
