"""Bounded offline SVG derivatives of published catalog/land, no WebGL."""
import gzip
import hashlib
import json
import subprocess
from pathlib import Path


def publish(root, catalog, land, generated_at):
    from pipeline.build_release import atomic_write
    renderer=Path(__file__).resolve().parents[1]/'tools/render-static-figures.mjs'
    result=subprocess.run(['node','--max-old-space-size=256',str(renderer)],
        input=json.dumps({'catalog':catalog,'land':land,'generatedAt':generated_at}),
        text=True,capture_output=True,timeout=60,check=True)
    figures=json.loads(result.stdout)
    refs=[]
    for kind in ('globe','transit'):
        raw=figures[kind].encode()
        if len(raw)>1024*1024:
            raise ValueError('Static figure exceeds 1 MiB')
        digest=hashlib.sha256(raw).hexdigest()
        path=f'artifacts/static-{kind}-{digest[:16]}.svg'
        if not (root/path).exists():
            from pipeline.visual_storage import admit
            admit(root,len(raw)*2+4096,2)
            atomic_write(root/path,raw)
            atomic_write(root/(path+'.gz'),gzip.compress(raw,mtime=0))
        refs.append({'kind':kind,'path':path,'sha256':digest,'bytes':len(raw)})
    return {'generatedAt':generated_at,'figures':refs}
