#!/usr/bin/env python3
"""Offline bounded measurement of ONE manifest shard (default 77), never a sweep.

Default is dry-run/stdout. --out writes a disposable report plus one original
shard and three object views, capped at 64 MiB; refuse a nonempty output directory.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.plot_views import reduce_object, residuals


def parse_ms(path):
    code="""const fs=require('fs');const s=fs.readFileSync(process.argv[1],'utf8');
    const times=[];for(let i=0;i<12;i++){global.gc();const t=performance.now();const v=JSON.parse(s);times.push(performance.now()-t);if(!v)throw Error();}
    times.sort((a,b)=>a-b);console.log(JSON.stringify({medianMs:times[6],minMs:times[0],maxMs:times.at(-1),runs:12,node:process.version}));"""
    return json.loads(subprocess.check_output(['node','--expose-gc','--max-old-space-size=512','-e',code,str(path)],text=True))


def pixel_errors(original, view):
    samples=original['samples']; index={s['t']:i for i,s in enumerate(samples)}
    channels=[(k,[s[k] for s in samples]) for k in ('perigeeKm','apogeeKm','inclinationDeg')]
    channels += [('residualMetres',residuals(samples)),('log10Bstar',[math.log10(s['bstar']) if s['bstar'] and s['bstar']>0 else None for s in samples])]
    errors={}
    for name,ys in channels:
        finite=[y for y in ys if y is not None]
        span=max(finite)-min(finite) if finite else 0
        worst=0
        for a,b in zip(view['points'],view['points'][1:]):
            if not b[9]:continue
            left,right=index[a[0]],index[b[0]]
            if ys[left] is None or ys[right] is None:continue
            for i in range(left+1,right):
                if ys[i] is None:raise ValueError('Missing data was joined')
                ratio=(samples[i]['t']-a[0])/(b[0]-a[0])
                estimate=ys[left]+ratio*(ys[right]-ys[left])
                worst=max(worst,abs(ys[i]-estimate)/(span or 1)*96)
        if worst>1.000001:raise ValueError(f'{name} exceeds declared visual error: {worst}')
        errors[name]=worst
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-root',type=Path,default=Path('public/data'));p.add_argument('--shard',type=int,default=77);p.add_argument('--out',type=Path)
    args=p.parse_args(); m=json.loads((args.data_root/'manifest.json').read_bytes()); ref=next(s for s in m['orbitHistory']['shards'] if s['shard']==args.shard)
    raw=(args.data_root/ref['path']).read_bytes()
    if len(raw)>48*1024*1024: raise ValueError('Single-shard measurement budget exceeded')
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']: raise ValueError('Source hash mismatch')
    if args.out:
        args.out.mkdir(parents=True,exist_ok=True)
        if any(args.out.iterdir()): raise ValueError('Use a new, empty output directory')
    with tempfile.TemporaryDirectory(prefix='space-plot-measure-') as scratch:
        root=args.out or Path(scratch); full=root/'full-shard.json';full.write_bytes(raw)
        shard=json.loads(raw)
        report={'release':m['release'],'shard':ref,'before':{'bytes':len(raw),'gzipBytes':len(gzip.compress(raw,mtime=0)),'points':sum(len(o['samples']) for o in shard['objects']),'objects':len(shard['objects']),'parse':parse_ms(full)},'views':[]}
        for obj in sorted(shard['objects'],key=lambda o:len(o['samples']),reverse=True)[:3]:
            start=time.monotonic(); view=reduce_object(obj,ref['path']); elapsed=time.monotonic()-start
            encoded=json.dumps(view,separators=(',',':'),ensure_ascii=False,sort_keys=True).encode();path=root/f"plot-{obj['norad']}.json";path.write_bytes(encoded)
            report['views'].append({'norad':obj['norad'],'sourceObjectBytes':len(json.dumps(obj,separators=(',',':')).encode()),'originalPoints':len(obj['samples']),'displayPoints':len(view['points']),'bytes':len(encoded),'gzipBytes':len(gzip.compress(encoded,mtime=0)),'reduceSeconds':elapsed,'verifiedMaxVerticalErrorPixelsAt96px':pixel_errors(obj,view),'parse':parse_ms(path)})
        report['measurementNote']='Node JSON.parse only, 12 GC-separated parses per file; local gzip-9, not public wire or weak-device timings. Selected three largest objects in one shard, not an archive-wide guarantee.'
        if args.out: (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
if __name__=='__main__':main()
