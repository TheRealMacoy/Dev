#!/usr/bin/env bash
# Renders the reel: 900 frames (1080p60) + synthesized soundtrack -> showreel.mp4
set -euo pipefail
cd "$(dirname "$0")"
WORK="${WORK:-$(mktemp -d)}"
python3 audio.py "$WORK/soundtrack.wav"
node render.mjs "$WORK/frames" "${WORKERS:-4}"
ffmpeg -loglevel error -y -framerate 60 -i "$WORK/frames/f_%04d.png" -i "$WORK/soundtrack.wav" \
  -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 256k -shortest showreel.mp4
echo "wrote showreel.mp4"
