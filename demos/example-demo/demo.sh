#!/usr/bin/env bash
# Example demo — a tiny, dependency-free "product tour" that shows how pacing works.
# Copy this folder to start your own demo. Replace the echoes with your real demo
# (a CLI, a psql session, an API call — anything that prints to a terminal).
set -uo pipefail
cd "$(dirname "$0")"

# Pacing: holds between sections so the action tracks the narration. This is a
# no-op when you run the demo yourself; render.sh activates it while recording.
source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
type pace >/dev/null 2>&1 || pace() { :; }

echo "############################################"
echo "#   Acme Widget CLI  —  60-second tour     #"
echo "############################################"
pace 37   # narration: intro

echo
echo "$ widget init myapp"
echo "  created myapp/ with sensible defaults"
echo "  config written to myapp/widget.toml"
pace 33   # narration: the init step

echo
echo "$ widget build"
echo "  -> compiling 42 modules ..."
echo "  build complete in 1.2s   (artifacts in ./dist)"
pace 25   # narration: the build step

echo
echo "$ widget deploy --env prod"
echo "  -> uploading ..."
echo "  live at https://myapp.example.com"
pace 25   # narration: the deploy step

echo
echo "That's the whole loop:  init  ->  build  ->  deploy."
pace 25   # narration: the close
