#!/usr/bin/env python3
"""
Emit a per-clip timing-marks file beside each mechanism mp4.

WHY THIS IS NOT HAND-TIMED
--------------------------
Every mechanism scene already writes `scenes/scripts/<Scene>.json` at render
time: each caption and the second at which it becomes legible, taken from
Manim's own clock rather than from anyone watching the output. This script
turns that record into the marks shape the site already uses for the Quebec
1989 GIC schematic (`media/quebec-1989-gic-chain.marks.json`) so a narration
lane meets one format across the whole site.

One section per visual beat. A beat runs from the instant its caption becomes
legible to the instant the next one does; the first section is the title card,
which carries no caption and is labelled as the title card. `label` is what is
on the screen during the beat, which for these pieces is the burned-in caption
itself -- so a writer who cannot see the clip can still say something true
about that moment.

    python3 emit_marks.py            # writes media/mechanisms/<stem>.marks.json
    python3 emit_marks.py --check    # fails if any file on disk is out of date
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Scene class -> published file stem. Same table as narrate_mux.py; the two
# disagreeing would put a mark file beside the wrong clip.
STEMS = {
    "Reconnection": "dayside-reconnection",
    "Chapman": "chapman-layer",
    "HF": "hf-skip-blackout",
    "Trapped": "trapped-motion",
    "SAA": "eccentric-dipole-saa",
    "Drag": "drag-orbit-decay",
}

SCENE_FILES = {
    "Reconnection": "scene_01_reconnection.py",
    "Chapman": "scene_02_chapman.py",
    "HF": "scene_03_hf.py",
    "Trapped": "scene_04_trapped.py",
    "SAA": "scene_05_saa.py",
    "Drag": "scene_06_drag.py",
}


def scene_text(scenes: Path, scene: str) -> dict[str, str]:
    """TITLE / KICKER / SUB / TAKEAWAY, read out of the scene itself.

    Copying these into a table here is how a marks file ends up describing a
    card the clip no longer shows. They are parsed from the source instead, so
    editing a title edits the marks in the same change.
    """
    src = (scenes / SCENE_FILES[scene]).read_text()
    out = {}
    for key in ("TITLE", "KICKER", "SUB", "TAKEAWAY", "MARK"):
        m = re.search(rf'^\s+{key} = "(.*)"$', src, re.M)
        if not m:
            raise SystemExit(f"{scene}: no {key} in {SCENE_FILES[scene]}")
        out[key] = m.group(1)
    return out


def probe(path: Path, entries: str) -> list[str]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries,
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return out.stdout.split()


def build(scene: str, stem: str, scripts: Path, scenes: Path, media: Path) -> dict:
    caps = json.loads((scripts / f"{scene}.json").read_text())
    txt = scene_text(scenes, scene)
    mp4 = media / f"{stem}.mp4"
    w, h = probe(mp4, "stream=width,height")[:2]
    duration = float(probe(mp4, "format=duration")[0])

    lines = caps["lines"]
    title = (f'Title card: "{txt["TITLE"]}" - {txt["SUB"]} '
             f'Kicker {txt["KICKER"]}, {txt["MARK"]} badge.')
    beats: list[tuple[float, str]] = [(0.0, title)]
    beats += [(float(l["t"]), l["text"]) for l in lines]
    # The end card is the last beat: it begins when the final caption is
    # cleared, which is the scene's own recorded duration minus the end card.
    # The scene never logs it, so it is derived from the two things that ARE
    # recorded -- the last caption and the total -- and only when there is room.
    sections = []
    for i, (start, label) in enumerate(beats):
        end = beats[i + 1][0] if i + 1 < len(beats) else round(duration, 3)
        if end - start < 0.05:
            continue
        sections.append({
            "id": f"{stem}-{len(sections) + 1:02d}",
            "start": round(start, 3),
            "end": round(end, 3),
            "durationSeconds": round(end - start, 3),
            "label": label,
        })
    # Name the last beat for what it is. The final caption stays on screen while
    # the diagram fades and the end card lands, so the last section covers both.
    if sections:
        sections[-1]["label"] += (
            f'  |  then the end card: "{txt["TAKEAWAY"]}"')

    return {
        "stem": stem,
        "durationSeconds": round(duration, 3),
        "width": int(w),
        "height": int(h),
        "loop": False,
        "beatsFrom": f"tools/mechanism-animations/scripts/{scene}.json",
        "note": ("One section per caption change, taken from the scene's own render-time "
                 "clock. `label` is the caption burned into the frame during that beat. "
                 "`label` is here so a line can be written to go WITH the caption: say its "
                 "point, then extend it with what it had no room for. The old house rule said "
                 "the voice must never read the caption and that the rest was silence on "
                 "purpose; it was retired 2026-08-27 after it left three clips silent past "
                 "their halfway mark. A line may span several of these sections."),
        "sections": sections,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", type=Path,
                    default=REPO / "tools/mechanism-animations/scripts")
    ap.add_argument("--scenes", type=Path,
                    default=REPO / "tools/mechanism-animations/scenes")
    ap.add_argument("--media", type=Path, default=REPO / "media/mechanisms")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit non-zero if any file is stale")
    args = ap.parse_args()

    stale = 0
    for scene, stem in STEMS.items():
        doc = build(scene, stem, args.scripts, args.scenes, args.media)
        text = json.dumps(doc, indent=1) + "\n"
        path = args.media / f"{stem}.marks.json"
        if args.check:
            current = path.read_text() if path.is_file() else ""
            if current != text:
                print(f"STALE {path}", file=sys.stderr)
                stale += 1
            continue
        path.write_text(text)
        # The output directory is a build directory during packaging and the
        # repo during a re-derive, so the pretty path is best-effort.
        try:
            shown = path.relative_to(REPO)
        except ValueError:
            shown = path
        print(f"{shown}  {len(doc['sections']):2d} beats  "
              f"{doc['durationSeconds']:6.2f}s")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
