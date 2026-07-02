#!/usr/bin/env bash
# One-time setup: check tools, create the Python venv, install the voice model.
set -euo pipefail
cd "$(dirname "$0")"

echo "== checking tools =="
missing=0
for t in vhs ffmpeg ffprobe python3; do
  if command -v "$t" >/dev/null; then echo "  ok  $t"; else echo "  MISSING  $t"; missing=1; fi
done
if [[ "$missing" -eq 1 ]]; then
  cat <<'EOT'

Install the missing tools, then re-run ./setup.sh:
  macOS (Homebrew):  brew install vhs ffmpeg python
  Linux:             ffmpeg + python3 from your package manager;
                     VHS: https://github.com/charmbracelet/vhs#installation
EOT
  exit 1
fi

echo "== creating Python venv (.venv) =="
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
echo "== installing the local voice model (can take a few minutes) =="
pip install -r requirements.txt
deactivate

cat <<'EOT'

Setup complete.

Next:
  1) Put a 60-90s voice sample in   voice-sample/     (wav/mp3/m4a)
  2) Put your headshot at           assets/presenter.jpg
  3) Try the bundled example:       ./render.sh example-demo
     (the very first run also downloads the voice model weights)

Your video lands in            build/video/example-demo.mp4
EOT
