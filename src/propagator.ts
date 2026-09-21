import type { OmmRecord } from "./types";

interface PositionMessage {
  type: "positions";
  at: string;
  targetAt: string;
  indices: Uint32Array;
  states: Float32Array;
  targetStates: Float32Array;
  valid: Uint8Array;
  targetValid: Uint8Array;
}

export class OrbitPropagator {
  private readonly worker = new Worker(new URL("./orbit-worker.ts", import.meta.url), { type: "module" });
  private ready = false;
  private pendingTime: Date | null = null;
  private pendingLookaheadMs = 0;
  private inFlight = false;
  private onPositions: ((message: PositionMessage) => void) | null = null;
  private indices: number[];

  constructor(records: OmmRecord[], callback: (message: PositionMessage) => void) {
    this.indices = records.map((_, index) => index);
    this.onPositions = callback;
    this.worker.addEventListener("message", (event: MessageEvent<PositionMessage | { type: "ready" }>) => {
      if (event.data.type === "ready") {
        this.ready = true;
        this.flush();
        return;
      }
      this.inFlight = false;
      this.onPositions?.(event.data);
      this.flush();
    });
    this.worker.postMessage({ type: "init", records });
  }

  propagate(at: Date, lookaheadMs = 5000) {
    this.pendingTime = at;
    this.pendingLookaheadMs = Math.max(0, lookaheadMs);
    this.flush();
  }

  private flush() {
    if (!this.ready || this.inFlight || !this.pendingTime) return;
    const at = this.pendingTime;
    const lookaheadMs = this.pendingLookaheadMs;
    this.pendingTime = null;
    this.inFlight = true;
    this.worker.postMessage({
      type: "propagate",
      at: at.toISOString(),
      targetAt: new Date(at.getTime() + lookaheadMs).toISOString(),
      indices: this.indices,
    });
  }

  setIndices(indices: Iterable<number>) {
    this.indices = Array.from(indices);
  }

  destroy() {
    this.worker.terminate();
    this.onPositions = null;
  }
}
