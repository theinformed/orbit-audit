/// <reference lib="webworker" />

import { eciToGeodetic, gstime, json2satrec, propagate, type SatRec } from "satellite.js";
import type { OmmRecord } from "./types";

type InitMessage = { type: "init"; records: OmmRecord[] };
type PropagateMessage = { type: "propagate"; at: string; targetAt: string; indices: number[] };
type IncomingMessage = InitMessage | PropagateMessage;

let records: OmmRecord[] = [];
let satrecs: Array<SatRec | undefined> = [];

self.addEventListener("message", (event: MessageEvent<IncomingMessage>) => {
  if (event.data.type === "init") {
    records = event.data.records;
    satrecs = new Array(records.length);
    self.postMessage({ type: "ready", count: records.length });
    return;
  }

  const at = new Date(event.data.at);
  const targetAt = new Date(event.data.targetAt);
  const gmst = gstime(at);
  const targetGmst = gstime(targetAt);
  const states = new Float32Array(event.data.indices.length * 4);
  const targetStates = new Float32Array(event.data.indices.length * 4);
  const valid = new Uint8Array(event.data.indices.length);
  const targetValid = new Uint8Array(event.data.indices.length);
  const indices = Uint32Array.from(event.data.indices);

  event.data.indices.forEach((sourceIndex, outputIndex) => {
    const record = records[sourceIndex];
    if (!record) return;
    const satrec = satrecs[sourceIndex] ?? json2satrec(record);
    satrecs[sourceIndex] = satrec;
    const result = propagate(satrec, at);
    if (!result || typeof result.position === "boolean" || typeof result.velocity === "boolean") return;
    const geodetic = eciToGeodetic(result.position, gmst);
    const offset = outputIndex * 4;
    states[offset] = geodetic.latitude;
    states[offset + 1] = geodetic.longitude;
    states[offset + 2] = geodetic.height;
    states[offset + 3] = Math.hypot(result.velocity.x, result.velocity.y, result.velocity.z);
    valid[outputIndex] = 1;

    if (targetAt.getTime() === at.getTime()) {
      targetStates.set(states.subarray(offset, offset + 4), offset);
      targetValid[outputIndex] = 1;
      return;
    }
    const targetResult = propagate(satrec, targetAt);
    if (!targetResult || typeof targetResult.position === "boolean" || typeof targetResult.velocity === "boolean") return;
    const targetGeodetic = eciToGeodetic(targetResult.position, targetGmst);
    targetStates[offset] = targetGeodetic.latitude;
    targetStates[offset + 1] = targetGeodetic.longitude;
    targetStates[offset + 2] = targetGeodetic.height;
    targetStates[offset + 3] = Math.hypot(targetResult.velocity.x, targetResult.velocity.y, targetResult.velocity.z);
    targetValid[outputIndex] = 1;
  });

  self.postMessage(
    { type: "positions", at: event.data.at, targetAt: event.data.targetAt, indices, states, targetStates, valid, targetValid },
    [indices.buffer, states.buffer, targetStates.buffer, valid.buffer, targetValid.buffer],
  );
});

export {};
