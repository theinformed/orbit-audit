#!/usr/bin/env python3
"""Analysis-only, uncapped GEO-capable full-archive GPU census.

Input is a frozen SQLite backup, never a production write. The positive
mean-motion <=2 screen is deliberately broader than the GEO detector branch.
Every selected object's entire history is re-detected with current code.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import orbit_campaigns as oc, orbit_events as oe, orbit_sweep_gpu as gpu
from tools.eol_policy_probe import RAISE, NSK, epoch, digest


class RequiredGPU(gpu.Execution):
    def fallback(self, reason):
        raise RuntimeError(f"GPU required; no fallback: {reason}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--selected', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--registration', type=Path, required=True)
    args = p.parse_args()
    if not args.archive.is_file() or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        p.error('Existing snapshot and broker-assigned CUDA_VISIBLE_DEVICES required')
    start, cpu = time.monotonic(), time.process_time()
    hashes = {str(Path(m.__file__).relative_to(ROOT)): digest(Path(m.__file__))
              for m in (oc, oe, gpu, oc.orbit_history)}
    ids = json.loads(args.selected.read_text())
    db = oc.open_archive_for_reading(args.archive)
    assert db.execute('PRAGMA query_only').fetchone()[0] == 1
    facts = {r[0]: dict(zip(('name','objectType','launchDate','country'),r[1:]))
             for r in db.execute('SELECT norad,name,object_type,launch_date,country FROM object')}
    expected = db.execute('SELECT SUM(rows),COUNT(*) FROM object_rollup').fetchone()
    expectations = oc.Expectations.load()
    counts, raise_types = Counter(), Counter()
    read = 0
    # Dedicated analysis ledger; no release, state, cache or timer writes.
    gpu._USAGE_LEDGER = Path(str(args.output)+'.gpu-usage.jsonl')
    with RequiredGPU((0,), 320) as device, gzip.open(args.output, 'xt') as out:
        for position, norad in enumerate(ids):
            groups = list(oc.stream_object_rows(db, only=[norad], page_rows=8192))
            rows = [r for _, group in groups for r in group]
            read += len(rows)
            fact = facts.get(norad, {})
            name, kind = fact.get('name') or f'OBJECT {norad}', fact.get('objectType') or 'UNKNOWN'
            iv = oc.intervals_from_rows(norad, name, kind, rows)
            # Screen retained objects again with the exact branch, after constructing
            # all intervals. Never truncate histories to GEO-only intervals.
            geo = any(i.regime in ('GEO','near-GEO') for i in iv)
            events = oc.detect_object_events(iv, kappa=32, expectations=expectations,
                                             gpu_executor=device) if geo else []
            compact = []
            for e in events:
                d = e.as_dict()
                compact.append({k:d[k] for k in ('norad','name','objectType','startAt','endAt',
                    'signature','inclinationDeg','deltaV','regime','tests','perigeeAltitudeKm',
                    'apogeeAltitudeKm','confidence')})
                compact[-1]['controlBasis'] = 'self-history'
                counts[e.signature] += 1
                if e.signature == RAISE:
                    raise_types[kind] += 1
            months = defaultdict(list)
            for r in rows:
                months[datetime.fromtimestamp(r[0]/1000, timezone.utc).strftime('%Y-%m')].append(r[3])
            rec = dict(norad=norad, name=name, objectType=kind, facts=fact,
                       rows=len(rows), geoCapable=geo,
                       rowsSha256=hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest(),
                       firstEpoch=rows[0][0] if rows else None, lastEpoch=rows[-1][0] if rows else None,
                       events=compact,
                       intervals=[[i.start_ms,i.end_ms] for i in iv] if geo else [],
                       monthlyInclination={k:statistics.median(v) for k,v in sorted(months.items())} if geo else {})
            out.write(json.dumps(rec,separators=(',',':'),allow_nan=False)+'\n')
            if (position+1)%25 == 0:
                out.flush()
                print(json.dumps(dict(objects=position+1,of=len(ids),rows=read,
                    raises=dict(raise_types),wallSeconds=round(time.monotonic()-start))),flush=True)
        report = device.report()
    db.close()
    for f, h in hashes.items():
        if digest(ROOT/f) != h:
            raise RuntimeError(f'Source changed during run: {f}')
    receipt = dict(complete=True, archive=str(args.archive), archiveRows=expected[0],
                   archiveObjects=expected[1], prefilterObjects=len(ids), selectedRows=read,
                   eventCounts=dict(counts), raiseFlagsByType=dict(raise_types), gpu=report,
                   sourceHashes=hashes, analysisSourceSha256=digest(Path(__file__)),
                   registrationSha256=digest(args.registration), selectedSha256=digest(args.selected),
                   extractionSha256=digest(args.output), wallSeconds=time.monotonic()-start,
                   cpuSeconds=time.process_time()-cpu,
                   completedAt=datetime.now(timezone.utc).isoformat())
    Path(str(args.output)+'.receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt),flush=True)


if __name__ == '__main__':
    main()
