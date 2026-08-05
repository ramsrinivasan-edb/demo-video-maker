#!/usr/bin/env bash
# demo-video-maker — turn a terminal demo into a narrated video, in your own
# cloned voice, with your photo badged in a corner, paced so the on-screen action
# tracks the narration. Everything runs locally; nothing is uploaded.
#
#   ./render.sh                 build every demo under demos/
#   ./render.sh example-demo    build one demo (by folder name under demos/)
#   ./render.sh --no-tts NAME   skip voice synthesis, reuse build/audio/NAME.wav
#
# A demo lives in demos/<name>/ and provides:
#   demo.sh        the demo. Source lib/pace.sh and call `pace <weight>` between
#                  steps (weight ~= words of narration for the step just shown).
#   narration.txt  the script, in your words.
#   demo.conf      optional: BADGE_CORNER=top-right|top-left|bottom-right|bottom-left
#                            PACE_WEIGHT=<n>   (else auto-summed from `pace N` lines)
#   prep.sh        optional: slow/off-topic setup, run OFF-camera before recording.
#
# Output: build/video/<name>.mp4
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
DEMOS_DIR="$ROOT/demos"
OUT="$ROOT/build"

DO_TTS=1
[[ "${1:-}" == "--no-tts" ]] && { DO_TTS=0; shift; }

mkdir -p "$OUT/audio" "$OUT/silent" "$OUT/video" "$OUT/tapes" assets

# --- which demos ------------------------------------------------------------
if [[ $# -gt 0 ]]; then
  DEMOS=("$@")
else
  DEMOS=()
  for p in "$DEMOS_DIR"/*/; do [[ -f "${p}demo.sh" ]] && DEMOS+=("$(basename "$p")"); done
fi
[[ ${#DEMOS[@]} -eq 0 ]] && { echo "No demos found in $DEMOS_DIR/. See README.md."; exit 1; }

# --- tools ------------------------------------------------------------------
for t in vhs ffmpeg ffprobe; do
  command -v "$t" >/dev/null || { echo "!! '$t' not on PATH. Run ./setup.sh or install it."; exit 1; }
done

# --- voice sample -----------------------------------------------------------
REF="$(find voice-sample -type f \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.m4a' -o -iname '*.aiff' \) 2>/dev/null | head -1 || true)"
if [[ "$DO_TTS" -eq 1 && -z "$REF" ]]; then
  echo "!! No voice sample in voice-sample/. Drop a 60-90s clip there (see voice-sample/README.md),"
  echo "   or run with --no-tts to reuse an existing build/audio/*.wav."
  exit 1
fi

# --- presenter photo -> circular badge (built once) -------------------------
PHOTO="$(ls assets/presenter.* 2>/dev/null | grep -viE 'badge' | head -1 || true)"
[[ -z "$PHOTO" ]] && PHOTO="$(find assets -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) ! -iname 'badge.png' 2>/dev/null | head -1 || true)"
BADGE="assets/badge.png"
if [[ -n "$PHOTO" && ( ! -f "$BADGE" || "$PHOTO" -nt "$BADGE" ) ]]; then
  echo "== building presenter badge from $PHOTO =="
  # centre-crop to a square (biased slightly up for faces), scale, circular alpha,
  # then sit it on a white disc for a clean ring.
  ffmpeg -y -loglevel error -i "$PHOTO" -filter_complex \
    "[0:v]crop='min(iw,ih)':'min(iw,ih)':(iw-min(iw\,ih))/2:(ih-min(iw\,ih))/6,scale=200:200,format=rgba,\
geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(gt((X-100)*(X-100)+(Y-100)*(Y-100),100*100),0,255)'[pic];\
color=white:s=210x210,format=rgba,\
geq=r=255:g=255:b=255:a='if(gt((X-105)*(X-105)+(Y-105)*(Y-105),105*105),0,255)'[ring];\
[ring][pic]overlay=5:5,format=rgba[out]" \
    -map "[out]" -frames:v 1 "$BADGE"
fi
[[ -z "$PHOTO" ]] && echo "(no photo in assets/ — rendering without a badge; add assets/presenter.jpg to include one)"

overlay_expr() {  # $1 = corner  (margin 28px)
  case "$1" in
    top-left)     echo "28:28" ;;
    bottom-right) echo "W-w-28:H-h-28" ;;
    bottom-left)  echo "28:H-h-28" ;;
    *)            echo "W-w-28:28" ;;   # top-right (default)
  esac
}

# --- QR end card ------------------------------------------------------------
# OUTRO_URL defaults to this repo's own GitHub remote, so the QR "just works".
# Set OUTRO_URL="" to disable the end card, or to any URL to override.
if [[ -z "${OUTRO_URL+x}" ]]; then
  OUTRO_URL="$(git remote get-url origin 2>/dev/null | sed -E 's#git@github.com:#https://github.com/#; s#\.git$##')"
fi
ENDCARD="$OUT/endcard.png"
if [[ -n "${OUTRO_URL:-}" && ! -f "$ENDCARD" ]]; then
  PY="$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo "${PYTHON:-python3}" )"
  if "$PY" -c "import qrcode, PIL" 2>/dev/null; then
    echo "== building QR end card for $OUTRO_URL =="
    "$PY" make_endcard.py --url "$OUTRO_URL" --out "$ENDCARD"
  else
    echo "(qrcode/PIL unavailable — skipping QR end card; run ./setup.sh or: pip install 'qrcode[pil]')"
  fi
fi

# Append a few seconds of the end card to a finished video (in place).
append_endcard() {  # $1 = video (mp4, has v+a)   $2 = endcard png
  local vid="$1" card="$2" tmp="${1%.mp4}.outro.mp4"
  ffmpeg -y -loglevel error -i "$vid" -loop 1 -t 4 -i "$card" -f lavfi -t 4 -i anullsrc=r=44100:cl=stereo \
    -filter_complex \
      "[0:v]scale=1440:810,setsar=1,fps=30,format=yuv420p[v0];\
[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];\
[1:v]scale=1440:810,setsar=1,fps=30,format=yuv420p[v1];\
[v0][a0][v1][2:a]concat=n=2:v=1:a=1[v][a]" \
    -map "[v]" -map "[a]" -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart "$tmp" \
  && mv "$tmp" "$vid"
}

# --- 1. synthesize voice-over (model loads once for all demos) ---------------
if [[ "$DO_TTS" -eq 1 ]]; then
  echo "== synthesizing voice-over from $REF =="
  # shellcheck disable=SC1091
  source .venv/bin/activate 2>/dev/null || { echo "!! No .venv — run ./setup.sh first."; exit 1; }
  jobs=()
  for d in "${DEMOS[@]}"; do
    n="$DEMOS_DIR/$d/narration.txt"
    [[ -f "$n" ]] || { echo "!! missing $n"; exit 1; }
    jobs+=("$n")
  done
  python tts_clone.py --reference "$REF" --speed "${NARRATION_SPEED:-0.92}" --out-dir "$OUT/audio" "${jobs[@]}"
  deactivate || true
fi

# --- 2. build a VHS tape paced to the narration -----------------------------
build_tape() {  # $1 demo  $2 REC_PACE  $3 sleep-seconds  $4 holds (optional)
  local d="$1" rp="$2" slp="$3" holds="${4:-}"
  local pace_env="REC_PACE=$rp"
  [[ -n "$holds" ]] && pace_env="REC_PACE_LIST='$holds'"
  cat > "$OUT/tapes/$d.tape" <<EOF
Output "$OUT/silent/$d.mp4"
Set Shell bash
Set FontSize 16
Set Width 1440
Set Height 810
Set Theme "Dracula"
Set Padding 20
Set WindowBar Colorful
Hide
Type "cd '$DEMOS_DIR/$d'" Enter
Type "clear" Enter
Show
Sleep 1s
Type "PACE_LIB='$ROOT/lib/pace.sh' $pace_env bash demo.sh" Enter
Sleep ${slp}s
Sleep 2s
EOF
}

# --- 3. mux voice-over + badge onto the recording ---------------------------
mux() {  # $1 demo  $2 target-seconds  $3 corner
  local d="$1" target="$2" corner="$3"
  local v="$OUT/silent/$1.mp4" a="$OUT/audio/$1.wav" out="$OUT/video/$1.mp4"
  local vdur adur
  vdur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$v")
  adur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$a")
  echo "   mux: video=${vdur}s audio=${adur}s -> target=${target}s"
  if [[ -f "$BADGE" ]]; then
    ffmpeg -y -loglevel error -i "$v" -i "$a" -loop 1 -i "$BADGE" -filter_complex \
      "[0:v]tpad=stop_mode=clone:stop_duration=${target}[vp];\
[vp][2:v]overlay=$(overlay_expr "$corner")[vo];\
[1:a]adelay=800|800,apad[a]" \
      -map "[vo]" -map "[a]" -t "${target}" \
      -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart "$out"
  else
    ffmpeg -y -loglevel error -i "$v" -i "$a" -filter_complex \
      "[0:v]tpad=stop_mode=clone:stop_duration=${target}[v];[1:a]adelay=800|800,apad[a]" \
      -map "[v]" -map "[a]" -t "${target}" \
      -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart "$out"
  fi
}

# --- per-demo render --------------------------------------------------------
for d in "${DEMOS[@]}"; do
  demo_sh="$DEMOS_DIR/$d/demo.sh"
  [[ -f "$demo_sh" ]] || { echo "!! no $demo_sh — skipping"; continue; }
  audio="$OUT/audio/$d.wav"
  [[ -f "$audio" ]] || { echo "!! no $audio (run without --no-tts) — skipping $d"; continue; }

  # config: corner + pace weight (weight auto-summed from `pace N` lines if unset)
  BADGE_CORNER="top-right"; unset PACE_WEIGHT
  [[ -f "$DEMOS_DIR/$d/demo.conf" ]] && source "$DEMOS_DIR/$d/demo.conf"
  W="${PACE_WEIGHT:-$(grep -oE 'pace[[:space:]]+[0-9]+' "$demo_sh" | awk '{s+=$2} END{print s+0}')}"

  D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$audio")

  # optional off-camera setup (run before measuring AND before recording, so any
  # state the demo consumes is fresh for the take)
  run_prep() { [[ -f "$DEMOS_DIR/$d/prep.sh" ]] && ( cd "$DEMOS_DIR/$d" && bash prep.sh >/dev/null 2>&1 ) || true; }

  echo "=== $d: measuring base runtime ==="
  run_prep
  t0=$(date +%s.%N); ( cd "$DEMOS_DIR/$d" && env PACE_LIB="$ROOT/lib/pace.sh" REC_PACE= bash demo.sh >/dev/null 2>&1 ); t1=$(date +%s.%N)
  B=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')
  run_prep

  # REC_PACE so paced runtime ~= narration end (0.8s lead). W=0 -> no stretch.
  RP=$(awk -v D="$D" -v B="$B" -v W="$W" 'BEGIN{ if(W<=0){print 0} else {p=(D+0.8-B)/W; if(p<0)p=0; printf "%.4f", p} }')
  PACED=$(awk -v B="$B" -v RP="$RP" -v W="$W" 'BEGIN{printf "%.1f", B+RP*W}')
  SLEEP=$(awk -v D="$D" -v P="$PACED" 'BEGIN{m=(D>P)?D:P; printf "%d", m+6}')
  echo "    narration=${D}s base=${B}s weight=${W} corner=${BADGE_CORNER} -> REC_PACE=${RP} paced=${PACED}s"

  # Warn if the demo has no pace points — sync is impossible, video may freeze.
  NPACE=$(grep -cE '^[[:space:]]*pace\b' "$demo_sh" 2>/dev/null || echo 0)
  [[ "$NPACE" -eq 0 ]] && echo "!! $d: no 'pace' calls in demo.sh — narration/visual sync disabled (video may freeze). See README."

  # Try LLM alignment (stretched demos only). Empty HOLDS => fall back to REC_PACE.
  HOLDS=""
  if [[ "${W%.*}" -gt 0 ]] 2>/dev/null && [[ -f "$OUT/audio/$d.timing.json" ]]; then
    PYA="$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo "${PYTHON:-python3}" )"
    if HOLDS=$("$PYA" align.py --timing "$OUT/audio/$d.timing.json" --demo "$demo_sh" \
                --model "${ALIGN_MODEL:-qwen2.5:3b}" 2>>"$OUT/align.log"); then
      echo "    aligned holds: $HOLDS"
      SLEEP=$(awk -v D="$D" 'BEGIN{printf "%d", D+6}')
    else
      HOLDS=""
      echo "    (alignment unavailable — using proportional pacing; see $OUT/align.log)"
    fi
  fi

  build_tape "$d" "$RP" "$SLEEP" "$HOLDS"
  echo "=== $d: recording terminal (vhs) ==="
  vhs "$OUT/tapes/$d.tape"

  # Stretched demos (W>0) end with the narration -> trim trailing idle.
  # Non-stretch demos (W=0) may run past the narration -> keep the video length.
  VD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/silent/$d.mp4")
  if [[ "${W%.*}" -gt 0 ]] 2>/dev/null; then
    TARGET=$(awk -v a="$D" 'BEGIN{printf "%.2f", a+0.8+1}')
  else
    TARGET=$(awk -v v="$VD" -v a="$D" 'BEGIN{a=a+0.8; m=(v>a)?v:a; printf "%.2f", m+1}')
  fi
  echo "=== $d: muxing voice-over + badge ==="
  mux "$d" "$TARGET" "$BADGE_CORNER"
  if [[ -f "$ENDCARD" ]]; then
    echo "=== $d: appending QR end card ==="
    append_endcard "$OUT/video/$d.mp4" "$ENDCARD"
  fi
  echo "=== $d: done -> $OUT/video/$d.mp4 ==="
done

echo
echo "Finished. Videos in $OUT/video/:"
ls -lh "$OUT"/video/*.mp4 2>/dev/null || true
