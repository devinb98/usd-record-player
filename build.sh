#!/usr/bin/env bash
# One-shot rebuild: assets -> stage -> render -> open the GIF.
# Usage:
#   ./build.sh                       # defaults (24 frames, 800px)
#   ./build.sh --frames 48 --width 1000   # extra flags pass through to render.py
set -e
cd "$(dirname "$0")"

.venv/bin/python src/build_assets.py
.venv/bin/python src/build_stage.py     # static layout
.venv/bin/python src/choreograph.py     # animation on top (arm, handoff, spin)
.venv/bin/python src/render.py "$@"

echo "done -> renders/turntable.gif"
open renders/turntable.gif
