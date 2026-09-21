import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ArtifactRefreshController,
  DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS,
  changedArtifactRecords,
  type ArtifactRefreshStatus,
  type ArtifactRefreshUpdate,
} from "../src/artifact-refresh";

interface TestManifest {
  release: string;
  spaceWeather: { path: string; sha256: string };
  geospace?: { path: string; sha256: string };
  ionosphereModel?: { path: string; sha256: string };
  drap?: { path: string; sha256: string };
  aurora?: { path: string; sha256: string };
}

const initialManifest: TestManifest = {
  release: "one",
  spaceWeather: { path: "artifacts/weather-one.json", sha256: "weather-one" },
  geospace: { path: "artifacts/geospace-one.json", sha256: "geospace-one" },
  ionosphereModel: { path: "artifacts/ionosphere-one.json", sha256: "ionosphere-one" },
  drap: { path: "artifacts/drap-one.json", sha256: "drap-one" },
  aurora: { path: "artifacts/aurora-one.json", sha256: "aurora-one" },
};

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

class FakeVisibilitySource extends EventTarget {
  hidden = false;

  setHidden(hidden: boolean) {
    this.hidden = hidden;
    this.dispatchEvent(new Event("visibilitychange"));
  }
}

async function settle() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe("artifact identity comparison", () => {
  it("detects additions, removals, path changes, and hash changes only for tracked artifacts", () => {
    const next: TestManifest = {
      ...initialManifest,
      release: "metadata-only-change",
      spaceWeather: { ...initialManifest.spaceWeather },
      geospace: { path: "artifacts/geospace-two.json", sha256: "geospace-one" },
      ionosphereModel: { path: initialManifest.ionosphereModel!.path, sha256: "ionosphere-two" },
      drap: undefined,
      aurora: { ...initialManifest.aurora! },
    };
    expect(changedArtifactRecords(initialManifest, next).map((change) => change.key))
      .toEqual(["geospace", "ionosphereModel", "drap"]);
  });
});

describe("ArtifactRefreshController", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-06T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("cache-busts the manifest and applies a changed artifact set atomically", async () => {
    const next: TestManifest = {
      ...initialManifest,
      release: "two",
      geospace: { path: "artifacts/geospace-two.json", sha256: "geospace-two" },
      aurora: { path: "artifacts/aurora-two.json", sha256: "aurora-two" },
    };
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(next));
    const onArtifactsChanged = vi.fn(async (_update: ArtifactRefreshUpdate<TestManifest>) => undefined);
    const statuses: ArtifactRefreshStatus<TestManifest>[] = [];
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "data/manifest.json",
      baseUrl: "https://example.test/app/",
      initialManifest,
      fetchImpl,
      onArtifactsChanged,
      onStatus: (status) => statuses.push(status),
    });

    controller.start();
    await controller.refresh();

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(String(url)).toMatch(/^https:\/\/example\.test\/app\/data\/manifest\.json\?artifact-refresh=\d+$/);
    expect(init).toMatchObject({ cache: "no-store" });
    expect(init?.signal).toBeInstanceOf(AbortSignal);
    expect(onArtifactsChanged).toHaveBeenCalledTimes(1);
    expect(onArtifactsChanged.mock.calls[0]?.[0].changes.map((change) => change.key))
      .toEqual(["geospace", "aurora"]);
    expect(controller.getLastKnownGood()).toEqual(next);
    expect(statuses.at(-1)?.phase).toBe("updated");
    controller.stop();
  });

  it("does not reload unchanged artifacts and polls again after about five minutes", async () => {
    const metadataOnly: TestManifest = { ...initialManifest, release: "two" };
    const fetchImpl = vi.fn(async () => jsonResponse(metadataOnly));
    const onArtifactsChanged = vi.fn();
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      initialManifest,
      fetchImpl,
      onArtifactsChanged,
    });

    controller.start();
    await controller.refresh();
    expect(onArtifactsChanged).not.toHaveBeenCalled();
    expect(controller.getLastKnownGood()).toEqual(metadataOnly);

    await vi.advanceTimersByTimeAsync(DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS - 1);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    controller.stop();
  });

  it("does not refetch a manifest the caller already loaded", async () => {
    // The page fetches data/manifest.json to boot and hands that object to the
    // controller. Re-fetching it on start compared a file against itself, which
    // every visitor paid for — twice the manifest, once under a cache-busting
    // query. With a baseline in hand the first check belongs one interval away.
    const fetchImpl = vi.fn(async () => jsonResponse(initialManifest));
    const onStatus = vi.fn();
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      initialManifest,
      fetchImpl,
      onStatus,
    });

    controller.start();
    await settle();
    expect(fetchImpl).not.toHaveBeenCalled();
    // Armed, not paused: the tooltip must not tell a visitor with a visible tab
    // that live updates have stopped.
    expect(onStatus.mock.calls.at(-1)?.[0].phase).toBe("scheduled");

    await vi.advanceTimersByTimeAsync(DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    controller.stop();
  });

  it("still fetches immediately when it was given no baseline", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(initialManifest));
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      fetchImpl,
    });

    controller.start();
    await settle();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    controller.stop();
  });

  it("keeps the last-known-good manifest and reports fetch or apply errors", async () => {
    const networkError = new Error("offline");
    const statuses: ArtifactRefreshStatus<TestManifest>[] = [];
    const fetchImpl = vi.fn(async () => {
      throw networkError;
    });
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      initialManifest,
      fetchImpl,
      onStatus: (status) => statuses.push(status),
    });

    controller.start();
    // start() no longer fetches when it was handed a baseline, so the error
    // path is reached by the scheduled check rather than by starting.
    await vi.advanceTimersByTimeAsync(DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS);
    await settle();

    expect(controller.getLastKnownGood()).toBe(initialManifest);
    expect(statuses.at(-1)).toMatchObject({
      phase: "error",
      error: networkError,
      lastKnownGood: initialManifest,
    });
    controller.stop();

    const changed = { ...initialManifest, spaceWeather: { path: "new.json", sha256: "new" } };
    const applyController = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      initialManifest,
      fetchImpl: vi.fn(async () => jsonResponse(changed)),
      onArtifactsChanged: async () => {
        throw new Error("artifact validation failed");
      },
    });
    applyController.start();
    await vi.advanceTimersByTimeAsync(DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS);
    await settle();
    expect(applyController.getLastKnownGood()).toBe(initialManifest);
    applyController.stop();
  });

  it("pauses while hidden and refreshes immediately whenever the page becomes visible", async () => {
    const visibilitySource = new FakeVisibilitySource();
    visibilitySource.hidden = true;
    const fetchImpl = vi.fn(async () => jsonResponse(initialManifest));
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      initialManifest,
      fetchImpl,
      visibilitySource,
    });

    controller.start();
    await vi.advanceTimersByTimeAsync(DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS * 2);
    expect(fetchImpl).not.toHaveBeenCalled();

    visibilitySource.setHidden(false);
    await settle();
    expect(fetchImpl).toHaveBeenCalledTimes(1);

    visibilitySource.setHidden(true);
    await vi.advanceTimersByTimeAsync(DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS * 2);
    expect(fetchImpl).toHaveBeenCalledTimes(1);

    visibilitySource.setHidden(false);
    await settle();
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    controller.stop();
  });

  it("shares one in-flight request instead of overlapping refreshes", async () => {
    let resolveFetch: ((response: Response) => void) | undefined;
    const fetchImpl = vi.fn(() => new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    }));
    const controller = new ArtifactRefreshController<TestManifest>({
      manifestUrl: "https://example.test/data/manifest.json",
      initialManifest,
      fetchImpl,
    });

    controller.start();
    const first = controller.refresh();
    const second = controller.refresh();
    expect(first).toBe(second);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(controller.isRefreshing()).toBe(true);

    resolveFetch?.(jsonResponse(initialManifest));
    await first;
    expect(controller.isRefreshing()).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    controller.stop();
  });
});

describe("default fetch implementation", () => {
  it("calls the ambient fetch with its own receiver, not the controller", async () => {
    // Regression guard for "Illegal invocation": browsers reject the global
    // fetch when it is invoked as a method of another object. Every other test
    // injects a fetchImpl, so only this one exercises the default path.
    const originalFetch = globalThis.fetch;
    const receivers: unknown[] = [];
    const manifest = { spaceWeather: { path: "a.json", sha256: "1" } };
    globalThis.fetch = function (this: unknown) {
      receivers.push(this);
      return Promise.resolve(
        new Response(JSON.stringify(manifest), { status: 200, headers: { "content-type": "application/json" } }),
      );
    } as unknown as typeof fetch;
    try {
      const controller = new ArtifactRefreshController({
        manifestUrl: "https://example.test/data/manifest.json",
        visibilitySource: null,
      });
      controller.start();
      await controller.refresh();
      controller.stop();
      expect(receivers.length).toBeGreaterThan(0);
      for (const receiver of receivers) {
        expect(receiver === controller).toBe(false);
      }
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
