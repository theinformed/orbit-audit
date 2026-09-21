export const DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS = 5 * 60_000;

export const DEFAULT_REFRESHED_ARTIFACT_KEYS = [
  "spaceWeather",
  "geospace",
  "ionosphereModel",
  "ionosondeSoundings",
  "drap",
  "aurora",
  // The DGCPM plasmasphere frames drive two layers (the plasmasphere stipple
  // and the ring current, which is drift traced in that same field) and
  // publish only every two hours, so a tab open for one cycle was reading
  // frames two hours older than the manifest it was quoting. See the
  // `plasmasphere` case in `hotSwapArtifact`.
  "plasmasphere",
] as const;

export type RefreshedArtifactKey = (typeof DEFAULT_REFRESHED_ARTIFACT_KEYS)[number];

export interface ArtifactRecord {
  path: string;
  sha256?: string;
  hash?: string;
  [key: string]: unknown;
}

export type RefreshManifest = object;

export interface ArtifactChange {
  key: string;
  previous?: ArtifactRecord;
  current?: ArtifactRecord;
}

export interface ArtifactRefreshUpdate<TManifest extends RefreshManifest> {
  manifest: TManifest;
  previousManifest: TManifest | null;
  changes: ArtifactChange[];
  signal: AbortSignal;
}

export type ArtifactRefreshPhase =
  | "checking"
  | "unchanged"
  | "updated"
  | "error"
  // Running and armed, but no check has happened yet in this visit because the
  // caller supplied the manifest it had already loaded. Distinct from "paused",
  // which means the tab is hidden and nothing is scheduled at all.
  | "scheduled"
  | "paused"
  | "stopped";

export interface ArtifactRefreshStatus<TManifest extends RefreshManifest> {
  phase: ArtifactRefreshPhase;
  checkedAt: number;
  lastKnownGood: TManifest | null;
  error?: Error;
}

export type ArtifactRefreshResult =
  | { phase: "unchanged" }
  | { phase: "updated"; changes: ArtifactChange[] }
  | { phase: "error"; error: Error }
  | { phase: "paused" }
  | { phase: "stopped" };

export interface ArtifactRefreshVisibilitySource {
  readonly hidden: boolean;
  addEventListener(type: "visibilitychange", listener: EventListener): void;
  removeEventListener(type: "visibilitychange", listener: EventListener): void;
}

export interface ArtifactRefreshOptions<TManifest extends RefreshManifest> {
  manifestUrl?: string | URL;
  baseUrl?: string | URL;
  intervalMs?: number;
  artifactKeys?: readonly string[];
  initialManifest?: TManifest | null;
  fetchImpl?: typeof fetch;
  visibilitySource?: ArtifactRefreshVisibilitySource | null;
  onArtifactsChanged?: (update: ArtifactRefreshUpdate<TManifest>) => void | Promise<void>;
  onStatus?: (status: ArtifactRefreshStatus<TManifest>) => void;
  now?: () => number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function artifactRecord(value: unknown): ArtifactRecord | undefined {
  if (!isRecord(value) || typeof value.path !== "string" || value.path.length === 0) return undefined;
  const sha256 = typeof value.sha256 === "string" ? value.sha256 : undefined;
  const hash = typeof value.hash === "string" ? value.hash : undefined;
  return { ...value, path: value.path, ...(sha256 ? { sha256 } : {}), ...(hash ? { hash } : {}) };
}

function artifactIdentity(record: ArtifactRecord | undefined): string | null {
  if (!record) return null;
  return `${record.path}\u0000${record.sha256 ?? ""}\u0000${record.hash ?? ""}`;
}

function manifestValue(manifest: RefreshManifest | null, key: string): unknown {
  return manifest ? (manifest as Record<string, unknown>)[key] : undefined;
}

export function changedArtifactRecords(
  previousManifest: RefreshManifest | null,
  currentManifest: RefreshManifest,
  artifactKeys: readonly string[] = DEFAULT_REFRESHED_ARTIFACT_KEYS,
): ArtifactChange[] {
  return artifactKeys.flatMap((key) => {
    const previous = artifactRecord(manifestValue(previousManifest, key));
    const current = artifactRecord(manifestValue(currentManifest, key));
    if (artifactIdentity(previous) === artifactIdentity(current)) return [];
    return [{ key, ...(previous ? { previous } : {}), ...(current ? { current } : {}) }];
  });
}

function resolveManifestUrl(manifestUrl: string | URL, baseUrl: string | URL | undefined, nonce: number) {
  const fallbackBase = typeof document === "undefined" ? undefined : document.baseURI;
  let url: URL;
  try {
    url = new URL(manifestUrl, baseUrl ?? fallbackBase);
  } catch {
    throw new Error("A baseUrl is required when artifact refresh uses a relative manifest URL outside a browser");
  }
  url.searchParams.set("artifact-refresh", String(nonce));
  return url;
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}

export class ArtifactRefreshController<TManifest extends RefreshManifest> {
  private readonly manifestUrl: string | URL;
  private readonly baseUrl?: string | URL;
  private readonly intervalMs: number;
  private readonly artifactKeys: readonly string[];
  private readonly fetchImpl: typeof fetch;
  private readonly visibilitySource: ArtifactRefreshVisibilitySource | null;
  private readonly onArtifactsChanged?: ArtifactRefreshOptions<TManifest>["onArtifactsChanged"];
  private readonly onStatus?: ArtifactRefreshOptions<TManifest>["onStatus"];
  private readonly now: () => number;
  private lastKnownGood: TManifest | null;
  private running = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private controller: AbortController | null = null;
  private inFlight: Promise<ArtifactRefreshResult> | null = null;
  private refreshWhenIdle = false;
  private requestSequence = 0;

  private readonly handleVisibilityChange = () => {
    if (!this.running) return;
    if (this.isHidden()) {
      this.clearTimer();
      this.refreshWhenIdle = false;
      this.controller?.abort();
      this.emitStatus("paused");
      return;
    }
    if (this.inFlight) {
      this.refreshWhenIdle = true;
      return;
    }
    void this.refresh();
  };

  constructor(options: ArtifactRefreshOptions<TManifest> = {}) {
    this.manifestUrl = options.manifestUrl ?? "data/manifest.json";
    this.baseUrl = options.baseUrl;
    this.intervalMs = options.intervalMs ?? DEFAULT_ARTIFACT_REFRESH_INTERVAL_MS;
    if (!Number.isFinite(this.intervalMs) || this.intervalMs <= 0) {
      throw new RangeError("artifact refresh intervalMs must be a positive finite number");
    }
    this.artifactKeys = options.artifactKeys ?? DEFAULT_REFRESHED_ARTIFACT_KEYS;
    // `fetch` must keep its original receiver. Storing the bare global on the
    // instance and calling it as `this.fetchImpl(...)` makes the browser reject
    // it with "Illegal invocation", which no unit test can see because every
    // test injects its own fetchImpl.
    this.fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
    this.visibilitySource = options.visibilitySource === undefined
      ? (typeof document === "undefined" ? null : document)
      : options.visibilitySource;
    this.onArtifactsChanged = options.onArtifactsChanged;
    this.onStatus = options.onStatus;
    this.now = options.now ?? Date.now;
    this.lastKnownGood = options.initialManifest ?? null;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.visibilitySource?.addEventListener("visibilitychange", this.handleVisibilityChange);
    if (this.isHidden()) {
      this.emitStatus("paused");
      return;
    }
    if (this.inFlight) {
      this.refreshWhenIdle = true;
      return;
    }
    // A caller that already holds the manifest has handed us our baseline, and
    // re-fetching it immediately compares a file against itself. Every visitor
    // paid for that: the page loads data/manifest.json to boot, and the
    // controller loaded it again a moment later under its cache-busting query.
    // With a baseline in hand the first real question is whether a NEWER
    // manifest exists, and that is worth asking one interval from now.
    if (this.lastKnownGood) {
      this.emitStatus("scheduled");
      this.scheduleNextRefresh();
      return;
    }
    void this.refresh();
  }

  stop(): void {
    if (!this.running && !this.inFlight) return;
    this.running = false;
    this.refreshWhenIdle = false;
    this.clearTimer();
    this.visibilitySource?.removeEventListener("visibilitychange", this.handleVisibilityChange);
    this.controller?.abort();
    this.emitStatus("stopped");
  }

  refresh(): Promise<ArtifactRefreshResult> {
    if (this.inFlight) return this.inFlight;
    if (!this.running) return Promise.resolve({ phase: "stopped" });
    if (this.isHidden()) {
      this.emitStatus("paused");
      return Promise.resolve({ phase: "paused" });
    }

    this.clearTimer();
    const controller = new AbortController();
    this.controller = controller;
    this.emitStatus("checking");
    const request = this.performRefresh(controller);
    this.inFlight = request;
    void request.finally(() => {
      if (this.inFlight !== request) return;
      this.inFlight = null;
      if (this.controller === controller) this.controller = null;
      if (!this.running || this.isHidden()) return;
      if (this.refreshWhenIdle) {
        this.refreshWhenIdle = false;
        void this.refresh();
        return;
      }
      this.scheduleNextRefresh();
    });
    return request;
  }

  getLastKnownGood(): TManifest | null {
    return this.lastKnownGood;
  }

  isRefreshing(): boolean {
    return this.inFlight !== null;
  }

  private async performRefresh(controller: AbortController): Promise<ArtifactRefreshResult> {
    try {
      const url = resolveManifestUrl(
        this.manifestUrl,
        this.baseUrl,
        this.now() * 1_000 + this.requestSequence++,
      );
      const response = await this.fetchImpl(url, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(`manifest refresh failed with HTTP ${response.status}`);
      const value: unknown = await response.json();
      if (!isRecord(value)) throw new Error("manifest refresh returned a non-object JSON value");
      const manifest = value as TManifest;
      if (controller.signal.aborted || !this.running || this.isHidden()) {
        return { phase: this.running ? "paused" : "stopped" };
      }
      const changes = changedArtifactRecords(this.lastKnownGood, manifest, this.artifactKeys);
      if (changes.length > 0 && this.onArtifactsChanged) {
        await this.onArtifactsChanged({
          manifest,
          previousManifest: this.lastKnownGood,
          changes,
          signal: controller.signal,
        });
      }
      if (controller.signal.aborted || !this.running || this.isHidden()) {
        return { phase: this.running ? "paused" : "stopped" };
      }
      this.lastKnownGood = manifest;
      if (changes.length === 0) {
        this.emitStatus("unchanged");
        return { phase: "unchanged" };
      }
      this.emitStatus("updated");
      return { phase: "updated", changes };
    } catch (caught) {
      if (controller.signal.aborted || isAbortError(caught)) {
        return { phase: this.running ? "paused" : "stopped" };
      }
      const error = asError(caught);
      this.emitStatus("error", error);
      return { phase: "error", error };
    }
  }

  private isHidden(): boolean {
    return this.visibilitySource?.hidden ?? false;
  }

  private emitStatus(phase: ArtifactRefreshPhase, error?: Error): void {
    try {
      this.onStatus?.({
        phase,
        checkedAt: this.now(),
        lastKnownGood: this.lastKnownGood,
        ...(error ? { error } : {}),
      });
    } catch {
      // Status observers must not break refresh scheduling or accepted data.
    }
  }

  private scheduleNextRefresh(): void {
    this.clearTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.refresh();
    }, this.intervalMs);
  }

  private clearTimer(): void {
    if (this.timer === null) return;
    clearTimeout(this.timer);
    this.timer = null;
  }
}
