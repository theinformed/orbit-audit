/// <reference lib="webworker" />

/**
 * The transit planner's compute lane — a message pump, and nothing else.
 *
 * Every decision lives in `src/transit-solve.ts` so tests exercise the same code
 * the browser runs. This file only schedules it, reports progress, and honours
 * cancellation.
 *
 * ## Why a second worker rather than a change to src/orbit-worker.ts
 *
 * That worker answers "where is everything right now", once per animation
 * frame, and must stay latency-bound and tiny. This one answers "over the next
 * several days, when can a moving observer see each of these satellites", once
 * per plan, and is throughput-bound and large. Sharing one worker would have
 * made the globe stutter for as long as a plan took to solve. Both call the same
 * `satellite.js` SGP4 on the same OMM records, so no orbital mechanics is
 * duplicated — only the scheduling around it.
 */

import {
  estimateEvaluations,
  solveSatelliteVisibility,
  type SatelliteVisibilityResult,
  type SolveSatelliteInput,
} from "./transit-solve";
import { routeSpanMs, type TransitRoute } from "./transit-route";

type SolveMessage = {
  type: "solve";
  requestId: number;
  satellites: SolveSatelliteInput[];
  route: TransitRoute;
  maskDeg: number;
  observerAltitudeKm: number;
  edgeToleranceSeconds: number;
  /** Hard ceiling on SGP4 evaluations. The solve refuses rather than hangs. */
  evaluationBudget: number;
};

type CancelMessage = { type: "cancel"; requestId: number };
type IncomingMessage = SolveMessage | CancelMessage;

let cancelledRequestId = -1;

self.addEventListener("message", (event: MessageEvent<IncomingMessage>) => {
  if (event.data.type === "cancel") {
    cancelledRequestId = event.data.requestId;
    return;
  }
  runSolve(event.data);
});

function runSolve(message: SolveMessage) {
  const startedAt = performance.now();
  const span = routeSpanMs(message.route);
  if (!span) {
    self.postMessage({
      type: "error",
      requestId: message.requestId,
      message: "The route has no positive duration, so there is nothing to solve.",
    });
    return;
  }

  const durationSeconds = (span.endMs - span.startMs) / 1000;
  const estimated = estimateEvaluations(message.satellites, durationSeconds);
  if (estimated > message.evaluationBudget) {
    self.postMessage({
      type: "over-budget",
      requestId: message.requestId,
      estimatedEvaluations: estimated,
      budget: message.evaluationBudget,
      satelliteCount: message.satellites.length,
      durationSeconds,
    });
    return;
  }

  const results: SatelliteVisibilityResult[] = [];
  let evaluations = 0;
  const options = {
    maskDeg: message.maskDeg,
    observerAltitudeKm: message.observerAltitudeKm,
    edgeToleranceSeconds: message.edgeToleranceSeconds,
  };

  for (const [ordinal, satellite] of message.satellites.entries()) {
    if (cancelledRequestId === message.requestId) return;
    const result = solveSatelliteVisibility(satellite, message.route, options);
    evaluations += result.evaluations;
    results.push(result);
    if ((ordinal + 1) % 20 === 0 || ordinal === message.satellites.length - 1) {
      self.postMessage({
        type: "progress",
        requestId: message.requestId,
        completed: ordinal + 1,
        total: message.satellites.length,
        evaluations,
      });
    }
  }

  if (cancelledRequestId === message.requestId) return;
  self.postMessage({
    type: "solved",
    requestId: message.requestId,
    results,
    evaluations,
    estimatedEvaluations: estimated,
    elapsedMs: performance.now() - startedAt,
    startMs: span.startMs,
    endMs: span.endMs,
  });
}

export {};
