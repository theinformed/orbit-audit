#!/usr/bin/env python3
"""v2 registration section 8.2: the v1 reproduction proof.

Compare a fresh v1 artifact to the committed one after removing exactly three
fields, and report the first differing path if any other field moved.
"""
import hashlib
import json
import sys

EXCLUDED = ("inputs.toolSha256", "wallSeconds", "artifactSha256")


def strip(obj):
    o = json.loads(json.dumps(obj))
    o.pop("wallSeconds", None)
    o.pop("artifactSha256", None)
    if isinstance(o.get("inputs"), dict):
        o["inputs"].pop("toolSha256", None)
    return o


def diffs(a, b, path=""):
    out = []
    if type(a) is not type(b):
        return [f"{path}: type {type(a).__name__} vs {type(b).__name__}"]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: missing on the left")
            elif k not in b:
                out.append(f"{path}.{k}: missing on the right")
            else:
                out += diffs(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += diffs(x, y, f"{path}[{i}]")
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}")
    return out


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    committed = json.loads(open(sys.argv[1]).read())
    fresh = json.loads(open(sys.argv[2]).read())
    a, b = strip(committed), strip(fresh)
    d = diffs(a, b, "$")
    print("excluded fields:", ", ".join(EXCLUDED))
    print("committed artifactSha256:", committed["artifactSha256"])
    print("fresh     artifactSha256:", fresh["artifactSha256"])
    print("committed toolSha256:    ", committed["inputs"]["toolSha256"])
    print("fresh     toolSha256:    ", fresh["inputs"]["toolSha256"])
    print("committed wallSeconds:   ", committed["wallSeconds"])
    print("fresh     wallSeconds:   ", fresh["wallSeconds"])
    print("reduced sha256 committed:", hashlib.sha256(canon(a)).hexdigest())
    print("reduced sha256 fresh:    ", hashlib.sha256(canon(b)).hexdigest())
    print("identical after exclusion:", not d)
    for line in d[:40]:
        print("  DIFF", line)
    return 0 if not d else 1


if __name__ == "__main__":
    raise SystemExit(main())
