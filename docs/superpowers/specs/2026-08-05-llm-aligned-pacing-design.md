# LLM-Aligned Pacing (Option C) — Design

**Date:** 2026-08-05
**Status:** Approved, ready for implementation planning

## Problem

Sync between the terminal visuals and the voice-over is driven entirely by the
manual `pace N` weights in `demo.sh`. Those weights are a static, hand-authored
guess at "words of narration per section." When the author rewords
`narration.txt` without re-tuning the weights, the total length still
auto-matches (no end freeze), but the *per-section* holds no longer track where
words are actually spent — so the visuals advance while the narration is still on
the previous step. This is mid-video drift, and it is the reported symptom.

Worst case (UI scratchpad with no `pace` calls, `W=0`): no stretching at all, so
the action finishes in seconds and the last frame freezes for the rest of the
narration.

## Goal

Automatically hold each demo step for as long as its narration actually takes,
robust to rewording, with **no new manual syntax** for the author (no markers, no
weight tuning). Degrade to today's behavior whenever the aligner is unavailable —
never worse than current.

## Approach: measured timing + local LLM alignment

Derive each on-screen hold from *measured per-sentence narration duration*, using
a small local LLM (via Ollama) to decide which narration sentence belongs to
which demo step. The demo's existing `pace` calls are the step boundaries; the
text each section prints is the anchor.

### Data flow (per demo)

```
narration.txt ─► tts_clone.py ─► <name>.wav  +  <name>.timing.json  (per-sentence: text, dur)
demo.sh       ─► extract K sections (text between `pace` calls)
                        │
      timing.json + sections ─► align.py ──(Ollama, local 127.0.0.1)──► holds = [h1..hK]
                        │                       │
                        │                  invalid / no Ollama / low-confidence
                        ▼                       ▼
   REC_PACE_LIST="h1 h2 …"  ◄─────────────  (fallback) current REC_PACE proportional stretch
                        │
              VHS records demo.sh; pace consumes one hold per call ─► mux ─► mp4
```

## Components

Each unit has one purpose and a narrow interface.

### 1. `tts_clone.py` — emit timing sidecar
- Already splits narration into sentence chunks and knows each chunk's audio.
- **Add:** write `<out-dir>/<name>.timing.json` next to the wav:
  `[{ "text": "<sentence>", "dur": <seconds> }, ...]`.
- `dur` is the chunk's rendered duration **after** the `--speed` atempo scaling
  (i.e. what actually plays), plus the inter-chunk gap accounted consistently.
- Stdlib `json` only.

### 2. `align.py` — NEW, the aligner
- **Inputs:** `--timing <name>.timing.json`, `--demo <path/to/demo.sh>`,
  optional `--model qwen2.5:3b`.
- **Extract sections:** parse `demo.sh`, split on `pace` calls into K sections;
  collect each section's printed text (echo args / literal lines, boilerplate
  stripped) as its label. K = number of `pace` calls.
- **Prompt Ollama** (`POST http://127.0.0.1:11434/api/generate`, stdlib `urllib`)
  with the ordered narration sentences and the ordered section labels; ask for a
  **monotonic non-decreasing** assignment mapping each sentence to a section
  index `1..K`. Expect strict JSON (array of ints).
- **Compute holds:** sum sentence `dur` per section → `holds[i]`. Holds are
  approximately the per-section narration duration (section base runtime is
  negligible — echoes are ~instant — and any small cumulative overshoot is
  absorbed by render.sh's existing end-trim).
- **Output:** print `REC_PACE_LIST` space-separated holds to stdout on success.
- **Fallback signal:** exit non-zero (and print nothing usable) if Ollama is
  unreachable, the reply is malformed, or the assignment fails validation
  (not non-decreasing, wrong length, doesn't cover `1..K`). Validation *is* the
  confidence gate — no separate score.

### 3. `lib/pace.sh` — per-call holds
- **Add branch:** if `REC_PACE_LIST` is set, keep a call counter and `sleep` the
  i-th value on the i-th `pace` call. State persists because VHS runs
  `bash demo.sh` as a single process.
- Else fall through to the current `REC_PACE × weight` behavior.
- Still a no-op when neither var is set (author running the demo normally).

### 4. `render.sh` — wire in the align step
- After TTS, before building the VHS tape, run `align.py` for the demo.
- On success: export `REC_PACE_LIST` into the tape's `bash demo.sh` invocation.
- On non-zero exit: unchanged — compute `REC_PACE` proportionally as today.
- Skip alignment entirely when `PACE_WEIGHT=0` (real-time demo, no stretch).
- **Freebie:** when a demo has zero `pace` calls, print a "no `pace` calls → no
  sync" warning (addresses the UI-scratchpad worst case).

### 5. `setup.sh` / `install.command` — optional dependency
- Detect `ollama` on PATH. If present, `ollama pull qwen2.5:3b`.
- **Non-fatal:** if `ollama` is missing, print a note that auto-sync will fall
  back to proportional pacing, and continue. The tool still works without it.

### 6. `README.md`
- Document auto-sync and Ollama as an *optional* local dependency (privacy note:
  `127.0.0.1` only, nothing uploaded).

### `requirements.txt` — NO CHANGE
- `align.py` uses stdlib `urllib`/`json`; the timing sidecar uses stdlib `json`.
- Ollama is a system tool (like `vhs`/`ffmpeg`), installed outside pip; the model
  is fetched via `ollama pull`, not a Python package. The venv footprint is
  identical to today.

## Model

`qwen2.5:3b` — small, fast, reliable at short structured-JSON tasks.

## Privacy

The only network call is to `http://127.0.0.1:11434` (local Ollama). Consistent
with the rest of the tool: nothing leaves the machine.

## Testing

- **`align.py`** unit tests with a canned `timing.json` + demo sections and a
  **mocked Ollama reply**: valid monotonic map → expected holds; malformed reply
  and unreachable server → non-zero exit (fallback path).
- **`lib/pace.sh`** test: with `REC_PACE_LIST="1 2 3"`, successive `pace` calls
  sleep the listed values in order; with only `REC_PACE` set, current behavior.
- **Section extraction** test: `demo.sh` with K `pace` calls → K labeled sections.
- End-to-end video rendering is **not** unit-tested (needs the full vhs/ffmpeg/
  Ollama stack); the alignment logic is tested in isolation.

## Out of scope

- The confirmed README rewrite (Gradio Studio description + layout line) and the
  UI placeholder/blank-name-guard changes ship as a **separate, already-approved
  change**, independent of this feature.
- No changes to the mux/badge/end-card stages.
