#!/usr/bin/env bash
# Builds orbit_to_cape_town.mp4: fetch + preprocess data, track the footage,
# render 1440 frames (1080p60), synthesize audio, encode.
# Usage: ./build.sh path/to/cape-town-drone.mov
set -euo pipefail
cd "$(dirname "$0")"
VIDEO="${1:?pass the drone footage}"
WORK="${WORK:-$(mktemp -d)}"
[ -d node_modules/three ] || npm install
python3 prepare.py
mkdir -p data/video
ffmpeg -loglevel error -y -i "$VIDEO" -q:v 2 data/video/v_%04d.jpg
python3 track.py
python3 audio.py "$WORK/soundtrack.wav"
node render.mjs "$WORK/frames" "${WORKERS:-4}"
ffmpeg -loglevel error -y -framerate 60 -i "$WORK/frames/f_%04d.png" -i "$WORK/soundtrack.wav" \
  -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 256k -shortest orbit_to_cape_town.mp4
echo "wrote orbit_to_cape_town.mp4"
