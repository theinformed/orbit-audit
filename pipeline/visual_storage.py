"""Admission/report for regenerable visual derivatives in the existing hot tree.

Current manifest records protect live files. Existing prune_data.py owns the
24-hour superseded grace and deletion. This module never selects files to delete.
"""
import argparse
import json
from pathlib import Path

WARN_BYTES=4*1024**3
MAX_BYTES=8*1024**3
WARN_FILES=80000
MAX_FILES=100000
_usage={}


def report(root):
    artifacts=Path(root)/'artifacts'
    if not artifacts.is_dir():
        return {'bytes':0,'files':0}
    files=[p for p in artifacts.iterdir() if p.is_file() and p.name.startswith(('plot-object-','plot-index-','static-globe-','static-transit-'))]
    return {'bytes':sum(p.stat().st_size for p in files),'files':len(files)}


def admit(root, additional_bytes, additional_files):
    key=str(Path(root).resolve())
    if key not in _usage:
        _usage[key]=report(root)
    usage=_usage[key]
    # Reserve the entire uncompressed + compressed upper bound before writing.
    if usage['bytes']+additional_bytes>MAX_BYTES or usage['files']+additional_files>MAX_FILES:
        raise ValueError('Visual derivative storage budget exhausted; retain current data and run reference-aware prune dry-run')
    usage['bytes']+=additional_bytes;usage['files']+=additional_files
    if usage['bytes']>WARN_BYTES or usage['files']>WARN_FILES:
        print(f'WARNING: visual derivative budget {usage["bytes"]} bytes / {usage["files"]} files')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('data_root',type=Path)
    args=p.parse_args();print(json.dumps({**report(args.data_root),'warningBytes':WARN_BYTES,'criticalBytes':MAX_BYTES,'warningFiles':WARN_FILES,'criticalFiles':MAX_FILES,'mode':'read-only dry run'}))
