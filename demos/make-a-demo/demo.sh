#!/usr/bin/env bash
# make-a-demo — a self-referential tutorial. It teaches demo-video-maker by
# showing the tool's OWN real files and commands on screen, while the narration
# (your cloned voice) explains each step. Docker-free; only reads the repo.
set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"          # the demo-video-maker repo root

# Pacing: holds between sections so the action tracks the narration. No-op when
# you run this yourself; render.sh activates it while recording.
source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
type pace >/dev/null 2>&1 || pace() { :; }

hr()  { printf '=%.0s' $(seq 1 62); echo; }
sub() { sed 's/^/    /'; }         # indent whatever is piped in

# --- beat 1: title ----------------------------------------------------------
clear
hr
echo "   demo-video-maker"
echo "   Make a narrated demo - in your own voice, with your face"
hr
pace 49   # narration: intro

# --- beat 2: the idea + the real project layout -----------------------------
clear
echo "# You bring 3 things:  your VOICE,  your PHOTO,  your DEMO."
echo "# The tool does the rest. Here is the actual project:"
echo
echo "\$ ls"
( cd "$ROOT" && ls -1 | grep -vE '^(\.|\.venv|\.git|build|docs|README\.md)$' ) | sub
pace 41   # narration: the idea

# --- beat 3: step 1 - get the tool ------------------------------------------
clear
echo "STEP 1  -  Get the tool"
echo
echo "\$ git clone https://github.com/ramsrinivasan-edb/demo-video-maker"
echo "\$ cd demo-video-maker"
echo "\$ ./setup.sh"
echo
echo "# setup.sh installs (requirements.txt):"
grep -vE '^\s*#|^\s*$' "$ROOT/requirements.txt" | sub
pace 37   # narration: step one

# --- beat 4: step 2 - add your voice ----------------------------------------
clear
echo "STEP 2  -  Add your voice   (a 60-90 second clip of you talking)"
echo
echo "\$ cp my_voice.wav voice-sample/"
echo "\$ ls voice-sample/"
( cd "$ROOT" && ls -1 voice-sample | grep -viE 'readme|gitkeep' ) | sub
pace 34   # narration: step two

# --- beat 5: step 3 - add your photo ----------------------------------------
clear
echo "STEP 3  -  Add your photo"
echo
echo "\$ cp headshot.jpg assets/presenter.jpg"
echo "\$ ls assets/"
( cd "$ROOT" && ls -1 assets | grep -viE 'readme|gitkeep' ) | sub
echo
echo "# presenter.jpg  ->  auto-cropped into the circular badge.png"
pace 36   # narration: step three

# --- beat 6: step 4 - build your demo (show the REAL example files) ----------
clear
echo "STEP 4  -  Build your demo   (copy the example, make it yours)"
echo
echo "\$ cp -r demos/example-demo demos/my-demo"
echo
echo "# demos/example-demo/demo.sh - your commands + a 'pace' per step:"
sed -n '18,28p' "$ROOT/demos/example-demo/demo.sh" | sub
echo
echo "# demos/example-demo/narration.txt - what you say, in plain words:"
sed -n '3p' "$ROOT/demos/example-demo/narration.txt" | fold -s -w 68 | sub
pace 77   # narration: step four

# --- beat 7: step 5 - render ------------------------------------------------
clear
echo "STEP 5  -  Render"
echo
echo "# usage (from render.sh):"
sed -n '6,8p' "$ROOT/render.sh" | sed -E 's/^#[[:space:]]?//' | sub
echo
echo "\$ ./render.sh my-demo"
echo "    clone your voice  ->  record terminal  ->  pace  ->  badge + voice"
echo
echo "\$ ls build/video/"
( cd "$ROOT" && ls -1 build/video 2>/dev/null ) | sub
echo "    ^ your finished MP4"
pace 55   # narration: step five

# --- beat 8: close ----------------------------------------------------------
clear
hr
echo "   That's it - the video you're watching was made this way."
echo
echo "   Make your own:"
( git -C "$ROOT" remote get-url origin 2>/dev/null \
    | sed -E 's#git@github.com:#https://github.com/#; s#\.git$##' \
    || echo "https://github.com/ramsrinivasan-edb/demo-video-maker" ) | sub
hr
pace 58   # narration: close
