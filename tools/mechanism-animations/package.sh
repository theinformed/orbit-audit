#!/usr/bin/env bash
# Re-encode the Manim masters for the web, cut a poster for each, and lay the
# narration on.
#
#   x264 CRF 29, -tune animation: flat colour and thin bright strokes on black
#   survive it without mosquito noise (checked at 1:1 on a text-heavy frame),
#   and it is roughly a third of the size of Manim's own output.
#
# The video is encoded ONCE, silent, into <stem>.silent.mp4. narrate_mux.py then
# copies that video stream unchanged and adds the AAC track, so the voice costs
# no picture quality and re-timing the narration never re-encodes a frame.
#
# WHERE THIS RUNS. Renders happen on bigmem-PC, not the VPS: Manim is CPU-heavy
# and that machine has the cores. Manim 0.20.1 lives in /home/sdegan/manimenv
# there. The defaults below are bigmem's; everything is still overridable, and
# the OpenClaw gateway container on the VPS remains a working fallback.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SRC=${SRC:-$HOME/space-manim-render/videos}
OUT=${OUT:-$HOME/space-manim-render/out}
SCRIPTS=${SCRIPTS:-$HERE/scenes/scripts}
AUDIO=${AUDIO:?set AUDIO to the narration mp3 directory}
SCRIPT_JSON=${SCRIPT_JSON:?set SCRIPT_JSON to narration/mechanisms.json}
mkdir -p "$OUT"
pack () {  # <scene-dir> <SceneName> <stem> <poster-seconds>
  local m="$SRC/$1/1080p30/$2.mp4"
  [ -f "$m" ] || { echo "MISSING $m"; return 1; }
  ffmpeg -y -loglevel error -i "$m" \
    -c:v libx264 -crf 29 -preset slower -tune animation -profile:v high \
    -pix_fmt yuv420p -movflags +faststart -an "$OUT/$3.silent.mp4"
  # The poster is the ONLY byte a visitor pays for on page load, because every
  # clip is preload="none". It is cut at 1280x720 rather than the master's
  # 1920x1080: at the ~350 CSS px these play at on a phone, and ~700 at 1440,
  # the extra pixels are invisible and cost twice the bytes.
  ffmpeg -y -loglevel error -ss "$4" -i "$m" -frames:v 1 -vf scale=1280:-2 -q:v 6 "$OUT/$3.jpg"
}
pack scene_01_reconnection Reconnection dayside-reconnection 22
pack scene_02_chapman      Chapman      chapman-layer        23
pack scene_03_hf           HF           hf-skip-blackout     22
pack scene_04_trapped      Trapped      trapped-motion       17
pack scene_05_saa          SAA          eccentric-dipole-saa 50
pack scene_06_drag         Drag         drag-orbit-decay     36

python3 "$HERE/narrate_mux.py" --scripts "$SCRIPTS" --audio "$AUDIO" \
        --script "$SCRIPT_JSON" --video "$OUT"

rm -f "$OUT"/*.silent.mp4

# The caption maps this render just dumped become the committed ones. Skipping
# this is how scripts/ and the clips drift apart, and every marks file and every
# narration anchor is derived from scripts/.
cp "$SCRIPTS"/*.json "$HERE/scripts/"

# The marks are re-derived here, from the caption times this render just wrote,
# so a clip and its timing marks can never be published out of step. --check in
# CI then fails loudly if anyone edits one without the other.
python3 "$HERE/emit_marks.py" --scripts "$SCRIPTS" --media "$OUT" || true

for f in "$OUT"/*.mp4; do
  s=$(basename "$f" .mp4)
  printf '%-26s %8s KB video  %6s KB poster  %ss\n' "$s" \
    "$(( $(stat -c%s "$f") / 1024 ))" \
    "$(( $(stat -c%s "$OUT/$s.jpg") / 1024 ))" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" | cut -d. -f1)"
done
echo "TOTAL $(du -sk "$OUT" | cut -f1) KB"
