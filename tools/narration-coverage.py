#!/usr/bin/env python3
"""
How much of each narrated clip actually has a voice on it.

WHY THIS EXISTS
---------------
The narration was missing from parts of the delivered videos -- in one of them
the voice did not start until halfway through. Every
manifest on the site said the opposite: narration-alignment.json reported every
line "fits": true, and docs/MEDIA-AND-NARRATION.md called the mechanism lane
"complete". Both were telling the truth about the wrong question. They check
that each line lands on the caption it was anchored to, and it does. Neither
checks whether the finished clip has a voice on it for more than a fifth of its
length, and that is the only thing a reader actually hears.

So this measures the delivered file rather than the intent behind it. It runs
ffmpeg's silencedetect over the real audio -- the muxed mp4 or the standalone
bed, whichever the page serves -- and reports duration, the second the first
word arrives, how many separate stretches of speech there are, the total time
spent talking, and the longest silence in the middle. Nothing here is read from
a manifest, because the manifests are what got it wrong.

THE NUMBER THAT MATTERS
-----------------------
speechFraction and firstOnsetSeconds, read together, against Quebec. The Quebec
GIC chain is the reference clip, the one that works: it opens at
0.00 s, talks for 77% of its length, and never goes quiet for more than 2.1 s.
A clip scoring far below that is not a clip with sparse narration. It is a clip
a reader concludes is broken, turns off, and does not come back to.

USAGE
    python3 tools/narration-coverage.py --table media/mechanisms/*.mp4
    python3 tools/narration-coverage.py --loud media/narration-layers/*.mp3
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

# -60 dBFS would catch room tone the clone does not produce; -40 sits below the
# quietest breath in the delivered set and above the mp3 coder's noise floor.
NOISE_FLOOR = "-40dB"
# Shorter than this is a pause inside a sentence, not a hole in the narration.
MIN_SILENCE_SECONDS = "0.35"
# The gap Quebec never exceeds. Longer than this reads as the audio having died.
QUEBEC_WORST_GAP_SECONDS = 2.11


def _ffprobe(path: Path, entries: str) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries,
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True)
    return out.stdout.strip()


def _ffmpeg_stderr(path: Path, afilter: str) -> str:
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", afilter, "-f", "null", "-"],
        capture_output=True, text=True).stderr


def speech_spans(path: Path, duration: float) -> list:
    """Stretches of the file that are NOT silence, from silencedetect's inverse.

    silencedetect reports the holes; the speech is what is left between them.
    Spans under 0.15 s are dropped: at this noise floor they are plosives and
    mouth noise either side of a real pause, not words.
    """
    err = _ffmpeg_stderr(path, "silencedetect=noise=%s:d=%s" % (NOISE_FLOOR, MIN_SILENCE_SECONDS))
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", err)]

    spans = []
    cursor = 0.0
    for i, silence_start in enumerate(starts):
        silence_start = max(0.0, silence_start)
        if silence_start > cursor + 0.01:
            spans.append((cursor, min(silence_start, duration)))
        cursor = duration if i >= len(ends) else ends[i]
    if cursor < duration - 0.01:
        spans.append((cursor, duration))
    return [(a, b) for a, b in spans if b - a > 0.15]


def loudness(path: Path) -> dict:
    """Integrated loudness, range and true peak, from ebur128's summary block."""
    err = _ffmpeg_stderr(path, "ebur128=peak=true")
    tail = err[err.rfind("Integrated loudness"):] if "Integrated loudness" in err else ""

    def grab(pattern):
        m = re.search(pattern, tail)
        return float(m.group(1)) if m else None

    return {
        "I_LUFS": grab(r"I:\s+(-?[\d.]+) LUFS"),
        "LRA_LU": grab(r"LRA:\s+(-?[\d.]+) LU"),
        "truePeak_dBFS": grab(r"Peak:\s+(-?[\d.]+) dBFS"),
    }


def measure(path: Path, want_loudness: bool = False) -> dict:
    if not path.is_file():
        return {"clip": path.name, "error": "missing"}
    duration = float(_ffprobe(path, "format=duration") or 0.0)
    if "audio" not in _ffprobe(path, "stream=codec_type").splitlines():
        return {"clip": path.name, "durationSeconds": round(duration, 2),
                "error": "NO AUDIO STREAM"}

    spans = speech_spans(path, duration)
    talking = sum(b - a for a, b in spans)
    gaps = [round(spans[i + 1][0] - spans[i][1], 2) for i in range(len(spans) - 1)]

    row = {
        "clip": path.name,
        "durationSeconds": round(duration, 2),
        "firstOnsetSeconds": round(spans[0][0], 2) if spans else None,
        "onsetFractionOfClip": round(spans[0][0] / duration, 3) if spans and duration else None,
        "speechSpanCount": len(spans),
        "speechSeconds": round(talking, 2),
        "speechFraction": round(talking / duration, 3) if duration else None,
        "trailingSilenceSeconds": round(duration - spans[-1][1], 2) if spans else None,
        "longestInternalGapSeconds": max(gaps) if gaps else 0.0,
        "worseThanQuebecGap": bool(gaps and max(gaps) > QUEBEC_WORST_GAP_SECONDS),
        "spans": [[round(a, 2), round(b, 2)] for a, b in spans],
    }
    if want_loudness:
        row.update(loudness(path))
    return row


HEAD = "%-28s %7s %7s %6s %7s %6s %7s" % (
    "clip", "dur", "onset", "spans", "talk", "talk%", "maxgap")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--loud", action="store_true", help="also measure EBU R128 loudness")
    ap.add_argument("--table", action="store_true", help="human-readable table instead of JSON")
    args = ap.parse_args()

    rows = [measure(p, args.loud) for p in args.paths]
    if not args.table:
        print(json.dumps(rows, indent=1))
        return 0

    print(HEAD)
    print("-" * len(HEAD))
    for r in rows:
        if r.get("error"):
            print("%-28s %s" % (r["clip"], r["error"]))
            continue
        flag = "  <-- gap worse than Quebec" if r["worseThanQuebecGap"] else ""
        print("%-28s %7.2f %7.2f %6d %7.2f %5.1f%% %7.2f%s" % (
            r["clip"], r["durationSeconds"], r["firstOnsetSeconds"],
            r["speechSpanCount"], r["speechSeconds"],
            r["speechFraction"] * 100, r["longestInternalGapSeconds"], flag))
        if args.loud:
            print("%-28s   I=%s LUFS  LRA=%s LU  peak=%s dBFS" % (
                "", r.get("I_LUFS"), r.get("LRA_LU"), r.get("truePeak_dBFS")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
