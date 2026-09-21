"""Offline display derivatives. No network, inference, averaging, or archive queries.

Vertical-error RDP on every plotted channel retains original samples. Global extrema,
event brackets, missing-value boundaries and original temporal gaps are protected.
The internal tolerance is 0.5 pixel; the multi-channel union bound is 1 pixel
on a 96-pixel-high normal-zoom panel. Zoom requires full resolution. A noisy curve may retain more points: fidelity wins over budget.
"""
from __future__ import annotations

import bisect
import json
import math
from pathlib import Path

VERSION = 1
MAX_GAP = 3 * 86400000
PIXEL_ERROR = 0.5
PANEL_HEIGHT = 96
MAX_OBJECT_BYTES = 4 * 1024 * 1024


def finite(v):
    return isinstance(v, (float, int)) and math.isfinite(v)


def residuals(samples):
    if not samples:
        return []
    xs = [(s['t'] - samples[0]['t']) / 86400000 for s in samples]
    ys = [s['semiMajorAxisKm'] for s in samples]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    variance = sum((x-mx)**2 for x in xs)
    slope = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / variance if variance and len(xs) >= 3 else 0
    return [(y-(my-slope*mx+slope*x))*1000 for x,y in zip(xs,ys)]


def reduce_object(record, full_path):
    samples = record['samples']
    n = len(samples)
    ts = [s['t'] for s in samples]
    if any(b < a for a,b in zip(ts, ts[1:])):
        raise ValueError('Unsorted history')
    detrended = residuals(samples)
    channels = [[s.get(k) for s in samples] for k in ('perigeeKm','apogeeKm','inclinationDeg')]
    channels += [detrended, [math.log10(s['bstar']) if finite(s.get('bstar')) and s['bstar'] > 0 else None for s in samples]]
    keep = {0, n-1} if n else set()
    breaks = {i for i in range(1,n) if ts[i]-ts[i-1] > MAX_GAP}
    for i in breaks:
        keep.update((i-1,i))
    # Retain both sides of every published event, independent of classification.
    from datetime import datetime
    for event in record.get('events',[]):
        for key in ('startAt','endAt'):
            if not event.get(key):
                continue
            t = datetime.fromisoformat(event[key].replace('Z','+00:00')).timestamp()*1000
            i = bisect.bisect_left(ts,t)
            keep.update(j for j in (i-1,i,i+1) if 0 <= j < n)
    for values in channels:
        valid = [i for i,v in enumerate(values) if finite(v)]
        if not valid:
            continue
        lo, hi = min(valid,key=lambda i:values[i]), max(valid,key=lambda i:values[i])
        keep.update((lo,hi))
        tolerance = (values[hi]-values[lo])*PIXEL_ERROR/PANEL_HEIGHT
        # Split at missing values as well as original gaps; never close holes.
        runs=[]; start=None
        for i in range(n):
            if not finite(values[i]) or i in breaks:
                if start is not None:
                    runs.append((start,i-1)); keep.update((start,i-1)); start=None
                if not finite(values[i]):
                    if i == 0 or i == n-1 or finite(values[i-1]) or (i+1 < n and finite(values[i+1])):
                        keep.add(i)
                    continue
            if start is None:
                start=i
        if start is not None:
            runs.append((start,n-1)); keep.update((start,n-1))
        for a,b in runs:
            # Partition at protected points so the bound also holds after their
            # insertion into the final polyline.
            anchors=sorted({a,b} | {i for i in keep if a <= i <= b})
            stack=list(zip(anchors,anchors[1:]))
            while stack:
                left,right=stack.pop()
                if right-left < 2:
                    continue
                dt=ts[right]-ts[left]
                worst=-1; split=left
                for i in range(left+1,right):
                    fraction=(ts[i]-ts[left])/dt if dt else 0
                    error=abs(values[i]-(values[left]+fraction*(values[right]-values[left])))
                    if error > worst:
                        worst,split=error,i
                if worst > tolerance:
                    keep.add(split); stack.extend(((left,split),(split,right)))
    # Adding another channel's anchors can at most double a channel's error.
    # Thus the declared bound is 1 pixel, not the internal 0.5-pixel threshold.
    indices=sorted(keep)
    out=[]
    for j,i in enumerate(indices):
        previous=indices[j-1] if j else -1
        joined = j > 0 and not any(previous < b <= i for b in breaks)
        s=samples[i]
        out.append([s['t'],s['perigeeKm'],s['apogeeKm'],s['semiMajorAxisKm'],
                    s['inclinationDeg'],s['eccentricity'],s.get('bstar'),s['tier'],detrended[i],joined])
    # Full evidence records stay reachable in the original; lightweight markers
    # retain their evidence/permission fields, never invent a manoeuvre verdict.
    marker_keys=('startAt','endAt','signature','signatureLabel','deltaVMetresPerSecond','confidence','eventKey','manoeuvreLabelPermitted','controlBasis','controlStratum')
    return {'schema':1,'norad':record['norad'],'points':out,
            'events':[{k:e[k] for k in marker_keys if k in e} for e in record.get('events',[])],
            'display':{'method':'vertical-error-extrema-v1','originalPoints':n,'displayPoints':len(out),
                       'maxErrorPixels':1,'panelHeight':PANEL_HEIGHT,'fullPath':full_path,
                       'evidenceNote':'Event markers retained; full evidence cards and element sets are in the full-resolution archive.'}}


def index_path(full_digest):
    return f'artifacts/plot-index-v{VERSION}-{full_digest[:16]}.json'


def publish_shard(root, shard, full_path, full_digest, writer):
    """Called once by the existing offline shard writer; immutable siblings."""
    index = root / index_path(full_digest)
    if index.exists():
        existing=json.loads(index.read_text())
        if all((root / r['path']).is_file() for r in existing['objects']):
            return
    from pipeline.visual_storage import admit
    refs=[]
    for obj in shard['objects']:
        view=reduce_object(obj,full_path)
        size=len(json.dumps(view,separators=(',',':')).encode())
        if size > MAX_OBJECT_BYTES:
            raise ValueError(f"Plot view {obj['norad']} exceeds 4 MiB; never weaken fidelity silently")
        admit(root, size*2+4096, 2)
        path,digest=writer(root,f"plot-object-{obj['norad']}",view)
        refs.append({'norad':obj['norad'],'path':path,'sha256':digest})
    from pipeline.build_release import atomic_write, canonical_json
    raw=canonical_json({'schema':VERSION,'sourceSha256':full_digest,'objects':refs})
    admit(root,len(raw),1)
    atomic_write(index,raw)


def manifest_views(root: Path, history: dict):
    """Read only small indexes during the frequent publish; never scan history."""
    import hashlib
    objects=[]; indexes=[]
    for shard in history.get('shards',[]):
        path=index_path(shard['sha256'])
        try:
            raw=(root/path).read_bytes(); index=json.loads(raw)
        except FileNotFoundError:
            continue  # Older archive: UI declares view unavailable, no large fallback.
        if index['sourceSha256'] != shard['sha256']:
            raise ValueError('Plot/source mismatch')
        objects.extend(index['objects'])
        indexes.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest()})
    if len(objects)>20000:
        raise ValueError('Plot manifest exceeds 20,000-object budget')
    return {'schema':VERSION,'generatedAt':history.get('generatedAt'),'objects':objects,'indexes':indexes}
