// T16b: the propagator bridge.
//
// This programme propagates orbits with satellite.js -- the SGP4
// implementation behind every object on the site's globe (src/orbit-worker.ts,
// src/ground-stations.ts, src/transit-solve.ts). The truth-set measurement
// uses the same propagator rather than a second one, so that what it measures
// is the error a consumer of this archive actually suffers.
//
// Input (stdin, JSON): { jobs: [ { id, omm: {...}, samples: [ { t, gmstMs } ] } ] }
//   omm      a GP/OMM record built from this archive's own stored elements
//   t        a label echoed back (the UTC millisecond of the comparison)
//   gmstMs   UTC millisecond shifted by UT1-UTC, so that the TEME -> PEF
//            rotation is evaluated at UT1 and not at UTC
//
// Output (stdout, JSON): { results: [ { id, t, pef: [x, y, z] km, ok } ] }
// Positions come back in the pseudo-Earth-fixed frame; the caller applies
// polar motion, which satellite.js does not model.

import { readFileSync } from "node:fs";
import { eciToEcf, gstime, json2satrec, propagate } from "satellite.js";

const input = JSON.parse(readFileSync(0, "utf8"));
const results = [];

for (const job of input.jobs) {
  let satrec = null;
  let initError = null;
  try {
    satrec = json2satrec(job.omm);
  } catch (err) {
    initError = String(err && err.message ? err.message : err);
  }
  for (const sample of job.samples) {
    if (!satrec) {
      results.push({ id: job.id, t: sample.t, ok: false, reason: initError });
      continue;
    }
    const when = new Date(sample.t);
    let state = null;
    try {
      state = propagate(satrec, when);
    } catch (err) {
      results.push({ id: job.id, t: sample.t, ok: false, reason: String(err) });
      continue;
    }
    if (!state || !state.position || satrec.error) {
      results.push({
        id: job.id,
        t: sample.t,
        ok: false,
        reason: `sgp4 error code ${satrec.error}`,
      });
      continue;
    }
    const gmst = gstime(new Date(sample.gmstMs));
    const pef = eciToEcf(state.position, gmst);
    results.push({ id: job.id, t: sample.t, ok: true, pef: [pef.x, pef.y, pef.z] });
  }
}

process.stdout.write(JSON.stringify({ results }));
