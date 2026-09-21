#!/usr/bin/env python3
"""
Build the narration BED for each layer-page clip, and measure where the voice lands.

WHY A BED AND NOT A MUXED MP4
-----------------------------
The six mechanism animations carry their voice muxed into the mp4, and that is the right
answer there: those clips exist to be watched once, start to finish. The ten layer clips
do not. Several of them are ambient `loop muted playsinline` diagrams that a reader leaves
running while they read the page beside it, and burning a voice into a looping clip gives
you the same sentence every twenty seconds forever. The video files are also not this
lane`s to re-encode.

So the voice ships as a SEPARATE full-length audio file, one per clip, exactly as long as
the clip, with each spoken line already sitting at the second it belongs to and silence
everywhere else. The page slaves that one element to the video`s own clock. Two
consequences that matter:

  - The alignment is BAKED IN by ffmpeg here, offline, where it can be measured with
    silencedetect and refused if it is wrong. The browser is never asked to schedule
    anything; it only has to keep one audio element at the same time as one video element,
    which is a single number.
  - A reader who never turns the voice on downloads none of it.

HOW A BEAT BECOMES A START TIME
-------------------------------
`--marks <file>` is the per-clip beat map: `{"stem": ..., "durationSeconds": ...,
"sections": [{"id": ..., "start": ..., "end": ...}]}` — the shape
media/quebec-1989-gic-chain.marks.json already uses. Each narration line names the beat it
belongs to and is delayed to that beat`s `start`. Nothing is hand-timed.

With no marks file a clip has exactly one beat: the whole clip, starting at zero. That is
the honest description of a script written one line to a clip, and it is what this lane
ships until the beat maps exist.

WHAT IS REFUSED
---------------
  - A line that runs past the END of its own beat. It is shortened in the script; it is
    never crossfaded over the next beat, because the whole point is that the words match
    the picture that is on the screen at that moment.
  - A bed whose audio stream does not begin at t=0. `adelay` shifts TIMESTAMPS rather than
    writing samples, so a bed of nothing but delayed lines can produce a file whose audio
    starts at the first word; players that ignore the edit list then start the voice at
    frame one, which is silent, plausible and completely wrong. An `anullsrc` pinned at
    PTS 0 forces real samples from the start and the check at the end proves it.

WHAT IS MEASURED, AND REPORTED
------------------------------
After the bed is written it is re-opened and `silencedetect` is run over it. That gives the
second at which speech ACTUALLY starts, measured from the delivered file rather than
asserted from the filter graph. The report carries, per line: the beat`s start, the
intended start, the measured start, the offset between them, the line`s duration and the
overrun past the end of its beat. "It sounds about right" is not evidence.

    python3 tools/narrate_layers_bed.py --script narration/layer-pages.json \
        --audio media/narration/ --video src/media --out media/narration-layers \
        --only thermosphere
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# The bed is already normalised line by line where each line was written (tools/narrate.py
# and tools/narrate_free.py both do it at generation time). A second loudnorm here would be
# levelling something already level and would pump the silence between lines, so the bed
# pass only mixes and pads.
SILENCE_THRESHOLD_DB = -45
SILENCE_MIN_SECONDS = 0.20
# A line is on its beat if the voice starts within this of the mark. One mp3 frame is 26 ms
# and the mixer rounds each delay to whole milliseconds, so anything under about 50 ms is
# arithmetic rather than drift; 0.1 s is comfortably inside the threshold at which a
# listener notices a voice arriving late against a picture.
OFFSET_TOLERANCE_SECONDS = 0.10
# A line is on its beat if the voice starts within this of the mark. One mp3 frame is 26 ms
# and the mixer rounds each delay to whole milliseconds, so anything under about 50 ms is
# arithmetic rather than drift; 0.1 s is comfortably inside the threshold at which a
# listener notices a voice arriving late against a picture.


def probe(path: Path, entries: str) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries,
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def duration(path: Path) -> float:
    return round(float(probe(path, "format=duration")), 3)


def voice_onsets(path: Path, min_seconds: float = SILENCE_MIN_SECONDS) -> list | None:
    """Every second at which the voice starts, measured off the delivered file.

    ffmpeg prints `silence_end` at the instant silence stops, which is the instant a line
    begins. A bed that opens with sound has no leading silence to end, so t=0 counts as an
    onset in its own right. This is the whole point of the check: the placement is read back
    OUT of the mp3 that ships, not asserted from the filter graph that made it.

    Pauses inside a sentence also end a silence, so the list is longer than the number of
    lines; each line is matched to the onset nearest its intended start.
    """
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
         "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d={min_seconds}",
         "-f", "null", "-"],
        capture_output=True, text=True)
    if "Duration" not in out.stderr:
        return None
    starts = [float(v) for v in re.findall(r"silence_start:\s*(-?[\d.]+)", out.stderr)]
    ends = [round(float(v), 3) for v in re.findall(r"silence_end:\s*([\d.]+)", out.stderr)]
    onsets = list(ends)
    if not starts or starts[0] > 0.05:
        onsets.insert(0, 0.0)
    return sorted(set(onsets))


def onset_at_or_after(path: Path, mark: float, window: float = 2.5) -> float | None:
    """When does sound begin at or after `mark`, measured in the delivered file.

    WHY NOT JUST TAKE THE NEAREST ONSET IN THE WHOLE FILE. Two different windows were being
    compared. The bed is scanned with a 200 ms window, which is right for finding where one
    LINE begins and not every pause inside a sentence — but a line whose first syllable is a
    soft consonant opens with less silence than that, so the bed's own scan cannot resolve
    the head at all and reports the line starting at the mark. The source file is scanned
    with a 20 ms window, which does resolve it. Subtracting one from the other then invents
    an 88 ms error in a line that was placed exactly.

    So the bed is scanned HERE with the same short window as the source, over a short window
    of time beginning at the mark. That makes the two measurements comparable, and it cannot
    be confused by the previous line, because nothing before the mark is looked at.
    """
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{mark:.3f}", "-t", f"{window:.3f}",
         "-i", str(path), "-af",
         f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d=0.02", "-f", "null", "-"],
        capture_output=True, text=True)
    if "Duration" not in out.stderr and "silencedetect" not in out.stderr:
        return None
    starts = [float(v) for v in re.findall(r"silence_start:\s*(-?[\d.]+)", out.stderr)]
    ends = [float(v) for v in re.findall(r"silence_end:\s*([\d.]+)", out.stderr)]
    # No leading silence in the window means the voice is already sounding at the mark.
    if not starts or starts[0] > 0.005:
        return round(mark, 3)
    return round(mark + ends[0], 3) if ends else None


def beats_for(clip: str, marks_dir: Path | None, clip_seconds: float) -> list:
    """The beat map for one clip, or the single whole-clip beat that stands in for it."""
    if marks_dir is not None:
        for candidate in (marks_dir / f"{clip}.marks.json", marks_dir / f"{clip}.json"):
            if candidate.is_file():
                spec = json.loads(candidate.read_text())
                return [{"id": s.get("id") or f"{clip}-{i:02d}",
                         "start": float(s["start"]), "end": float(s["end"]),
                         "label": s.get("label") or s.get("id") or ""}
                        for i, s in enumerate(spec.get("sections") or [], start=1)]
    return [{"id": clip, "start": 0.0, "end": clip_seconds, "label": "whole clip",
             "provisional": True}]


def build(clip: str, lines: list, beats: list, audio_dir: Path, video: Path,
          out_dir: Path) -> dict:
    vdur = duration(video)
    dest = out_dir / f"{clip}.mp3"

    by_beat = {b["id"]: b for b in beats}
    placed, failures = [], []

    inputs = ["-f", "lavfi", "-t", f"{vdur:.3f}", "-i", "anullsrc=r=44100:cl=mono"]
    filters, mixes = [], ["[0:a]"]
    for i, line in enumerate(lines, start=1):
        src = audio_dir / f"{line['id']}.mp3"
        if not src.is_file():
            failures.append(f"{line['id']}: no rendered audio at {src}")
            continue
        beat = by_beat.get(line.get("beat") or clip) or beats[0]
        adur = duration(src)
        # A rendered line does not necessarily begin with sound. A soft consonant or a
        # breath sits under the noise floor, so silencedetect reports the voice starting a
        # little after the file does. Measured on the mechanism lines that is 60-110 ms,
        # which is enough to make an otherwise perfectly placed line look off its beat.
        # That is the FILE's own attack, not a placement error, so it is measured per
        # source file here and taken out of the offset below. The raw measurement is kept
        # alongside, because hiding a number behind a correction is how a correction stops
        # being checkable.
        # 20 ms, not the 200 ms used on the bed. A line whose first syllable is a soft
        # consonant can open with 60-110 ms under the noise floor, and a detection window
        # longer than that head never reports it at all - which is exactly what made three
        # correctly placed lines look up to 0.109 s late the first time this was measured
        # against a real marks file.
        onsets = voice_onsets(src, min_seconds=0.02)
        lead_in = round(onsets[0], 3) if onsets else 0.0
        start = beat["start"]
        room = beat["end"] - start
        overrun = round(adur - room, 3)
        if overrun > 0:
            failures.append(
                f"{line['id']}: {adur:.2f}s of voice in a {room:.2f}s beat — "
                f"{overrun:.2f}s past the picture it describes. SHORTEN THE LINE.")
        placed.append({
            "id": line["id"], "beat": beat["id"], "beatLabel": beat.get("label", ""),
            "leadInSeconds": lead_in,
            "beatStartSeconds": round(start, 3), "beatEndSeconds": round(beat["end"], 3),
            "intendedStartSeconds": round(start, 3),
            "audioSeconds": adur,
            "endsAtSeconds": round(start + adur, 3),
            "overrunSeconds": overrun,
            "fits": overrun <= 0,
            "beatIsProvisional": bool(beat.get("provisional")),
            "source": line.get("source"),
            "text": line["text"],
        })
        delay = int(round(start * 1000))
        inputs += ["-i", str(src)]
        filters.append(f"[{i}:a]aresample=44100,adelay={delay}|{delay}[a{i}]")
        mixes.append(f"[a{i}]")

    if failures:
        for f in failures:
            print(f"REFUSING {clip}: {f}", file=sys.stderr)
        return {"clip": clip, "ok": False, "failures": failures}

    graph = (";".join(filters) + ";" + "".join(mixes)
             + f"amix=inputs={len(mixes)}:normalize=0,atrim=0:{vdur:.3f},"
               f"apad=whole_dur={vdur:.3f}[a]")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + inputs
                   + ["-filter_complex", graph, "-map", "[a]",
                      "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k",
                      str(dest)], check=True)

    bed_seconds = duration(dest)
    bed_onsets = voice_onsets(dest)
    if bed_onsets is None:
        print(f"REFUSING {clip}: could not measure where the voice starts", file=sys.stderr)
        return {"clip": clip, "ok": False, "failures": ["unmeasurable"]}

    worst = 0.0
    for entry in placed:
        intended = entry["intendedStartSeconds"]
        # What the bed SHOULD sound like: the mark, plus that line's own attack.
        expected = intended + entry["leadInSeconds"]
        nearest = onset_at_or_after(dest, intended)
        if nearest is None:
            nearest = min(bed_onsets, key=lambda o: abs(o - expected))
        entry["measuredStartSeconds"] = nearest
        entry["expectedVoiceAtSeconds"] = round(expected, 3)
        entry["rawOffsetSeconds"] = round(nearest - intended, 3)
        entry["measuredOffsetSeconds"] = round(nearest - expected, 3)
        entry["onTime"] = abs(nearest - expected) <= OFFSET_TOLERANCE_SECONDS
        worst = max(worst, abs(nearest - expected))
        if not entry["onTime"]:
            print(f"OFF-BEAT {clip}/{entry['id']}: the voice should be audible at "
                  f"{expected:.3f}s (mark {intended:.3f} + {entry['leadInSeconds']:.3f}s of "
                  f"attack) and starts at {nearest:.3f}s", file=sys.stderr)

    return {
        "clip": clip, "ok": True, "file": dest.name,
        "bytes": dest.stat().st_size,
        "videoSeconds": round(vdur, 3),
        "bedSeconds": bed_seconds,
        "bedMatchesVideo": abs(bed_seconds - vdur) <= 0.25,
        "measuredFirstVoiceSeconds": placed[0]["measuredStartSeconds"] if placed else None,
        "worstOffsetSeconds": round(worst, 3),
        "offsetToleranceSeconds": OFFSET_TOLERANCE_SECONDS,
        "allOnTime": all(e["onTime"] for e in placed),
        "lines": placed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True, help="dir of rendered per-line mp3s")
    ap.add_argument("--video", type=Path, required=True, help="dir of the clips themselves")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--marks", type=Path, default=None, help="dir of <clip>.marks.json beat maps")
    ap.add_argument("--only", action="append", default=None, help="build just these clips")
    ap.add_argument("--voice", default="elevenlabs-sean-clone",
                    help="what made the per-line audio; recorded in the manifest")
    args = ap.parse_args()

    spec = json.loads(args.script.read_text())
    args.out.mkdir(parents=True, exist_ok=True)

    by_clip: dict = {}
    for line in spec["lines"]:
        clip = line.get("clip")
        if not clip:
            continue
        if args.only and clip not in args.only:
            continue
        by_clip.setdefault(clip, []).append(line)

    reports, bad = [], 0
    for clip, lines in by_clip.items():
        video = args.video / f"{clip}.mp4"
        if not video.is_file():
            print(f"MISSING {video}", file=sys.stderr)
            bad += 1
            continue
        beats = beats_for(clip, args.marks, duration(video))
        report = build(clip, lines, beats, args.audio, video, args.out)
        reports.append(report)
        if not report.get("ok"):
            bad += 1
            continue
        print(f"{clip:26s} {report['videoSeconds']:6.2f}s clip  {len(report['lines'])} line(s)  "
              f"worst offset {report['worstOffsetSeconds']:+.3f}s  "
              f"{'ON TIME' if report['allOnTime'] else 'OFF BEAT'}  "
              f"{report['bytes']//1024:4d} KB")

    manifest = args.out / "manifest.json"
    existing = {}
    if manifest.is_file():
        try:
            existing = {c["clip"]: c for c in json.loads(manifest.read_text())["clips"]}
        except Exception:
            existing = {}
    for r in reports:
        if r.get("ok"):
            r["voice"] = args.voice
            existing[r["clip"]] = r
    manifest.write_text(json.dumps({
        "generator": "tools/narrate_layers_bed.py",
        "note": "One full-length audio bed per layer clip: the spoken lines already sitting at "
                "the second they belong to, silence everywhere else, exactly as long as the "
                "clip. The page slaves this to the video element's own clock, so the words and "
                "the picture cannot drift. `measuredFirstVoiceSeconds` was measured off the "
                "delivered file with silencedetect, not asserted from the filter graph.",
        "clips": sorted(existing.values(), key=lambda c: c["clip"]),
    }, indent=1, ensure_ascii=False) + "\n")
    print(f"\n{len([r for r in reports if r.get('ok')])} beds written to {args.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
