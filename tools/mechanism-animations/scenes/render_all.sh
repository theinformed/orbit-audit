#!/usr/bin/env bash
# Final renders: 1920x1080 at 30 fps. 60 fps doubles the file for no gain on
# line art that mostly holds still.
set -u
cd /home/node/.openclaw/tmp-manim-space/scenes
for spec in \
  "scene_01_reconnection.py Reconnection" \
  "scene_02_chapman.py Chapman" \
  "scene_03_hf.py HF" \
  "scene_04_trapped.py Trapped" \
  "scene_05_saa.py SAA" \
  "scene_06_drag.py Drag" ; do
  set -- $spec
  echo "=== $2"
  manim -r 1920,1080 --fps 30 --disable_caching "$1" "$2" >/dev/null 2>&1 \
    && echo "OK $2" || echo "FAIL $2"
done
echo ALLDONE
