# LLM-Aligned Pacing (Option C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hold each demo step on screen for as long as its narration actually takes, deriving holds from measured per-sentence audio durations with a local LLM (Ollama) mapping sentences to steps — falling back to today's proportional stretch whenever the LLM is unavailable or unsure.

**Architecture:** `tts_clone.py` writes a per-sentence timing sidecar next to each wav. A new `align.py` extracts the demo's `pace`-delimited sections, asks a local Ollama model to assign each narration sentence to a section, validates the mapping, and prints a per-section hold list. `render.sh` feeds that list into the recording via a new `REC_PACE_LIST` path in `lib/pace.sh`; if `align.py` exits non-zero, render.sh keeps its current proportional `REC_PACE` behavior.

**Tech Stack:** Python 3.12+ (stdlib only for new code — `urllib`, `json`, `re`, `argparse`, `unittest`), Bash, Ollama (`qwen2.5:3b`), existing VHS/ffmpeg pipeline.

## Global Constraints

- **No new pip dependencies.** All new Python code uses the standard library only. `requirements.txt` is NOT modified.
- **Tests use stdlib `unittest`** (no pytest), run with system `python3` (new modules import no heavy deps).
- **Local-only:** the sole network call is `POST http://127.0.0.1:11434/api/generate`. Nothing leaves the machine.
- **Model:** `qwen2.5:3b` (override via `ALIGN_MODEL` env / `--model`).
- **Auto-fallback:** any failure (no Ollama, malformed reply, invalid mapping, zero sections) → render.sh uses the existing proportional stretch. Behavior is never worse than today.
- **Commits:** no `Co-Authored-By` trailer; author is Ram Srinivasan only.
- Alignment applies only to stretched demos (`W > 0`). `PACE_WEIGHT=0` (real-time) demos skip it entirely.

---

### Task 1: Timing helpers module (`timing_util.py`)

Pure, dependency-free functions so tests never import torch/chatterbox.

**Files:**
- Create: `timing_util.py`
- Create: `tests/__init__.py` (empty)
- Test: `tests/test_timing_util.py`

**Interfaces:**
- Produces:
  - `chunk_durations(sample_counts: list[int], gap_samples: int, sr: int, speed: float) -> list[float]`
  - `write_timing(path: str, texts: list[str], durations: list[float]) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_timing_util.py
import json, os, tempfile, unittest
from timing_util import chunk_durations, write_timing


class TimingUtilTest(unittest.TestCase):
    def test_chunk_durations_includes_gap(self):
        # 24000 samples @ sr 24000 = 1.0s; +2400 gap = 0.1s
        self.assertEqual(chunk_durations([24000, 12000], 2400, 24000, 1.0), [1.1, 0.6])

    def test_chunk_durations_speed_scaling(self):
        # speed 2.0 => playback halved
        self.assertEqual(chunk_durations([24000], 0, 24000, 2.0), [0.5])

    def test_chunk_durations_zero_speed_treated_as_one(self):
        self.assertEqual(chunk_durations([24000], 0, 24000, 0.0), [1.0])

    def test_write_timing_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.timing.json")
            write_timing(p, ["a", "b"], [1.0, 2.0])
            with open(p) as f:
                self.assertEqual(json.load(f), [{"text": "a", "dur": 1.0}, {"text": "b", "dur": 2.0}])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_timing_util -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timing_util'`

- [ ] **Step 3: Write minimal implementation**

```python
# timing_util.py
"""Per-sentence narration timing helpers (stdlib only, no torch import)."""
import json


def chunk_durations(sample_counts, gap_samples, sr, speed):
    """Playback seconds per chunk, including its trailing gap, after atempo speed scaling."""
    speed = speed if speed and abs(speed) > 1e-9 else 1.0
    return [round((n + gap_samples) / sr / speed, 4) for n in sample_counts]


def write_timing(path, texts, durations):
    """Write [{text, dur}, ...] JSON sidecar, one entry per narration sentence."""
    data = [{"text": t, "dur": d} for t, d in zip(texts, durations)]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_timing_util -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add timing_util.py tests/__init__.py tests/test_timing_util.py
git commit -m "Add per-sentence timing helpers (timing_util)"
```

---

### Task 2: Emit the timing sidecar from `tts_clone.py`

Wire the helpers into synthesis so each wav gets a `<name>.timing.json`.

**Files:**
- Modify: `tts_clone.py` (imports; per-chunk sample tracking; sidecar write after concat)

**Interfaces:**
- Consumes: `timing_util.chunk_durations`, `timing_util.write_timing`
- Produces: `<out-dir>/<name>.timing.json` alongside `<out-dir>/<name>.wav`

- [ ] **Step 1: Add the import**

In `tts_clone.py`, next to the other imports (after `import soundfile as sf`), add:

```python
from timing_util import chunk_durations, write_timing
```

- [ ] **Step 2: Track per-chunk sample counts during generation**

In `main()`, the per-file loop builds `pieces` from `wav` and `gap`. Record the audio (non-gap) sample count of each chunk. Change the chunk loop so that immediately after `pieces.append(wav)` you capture its length:

```python
        pieces = []
        sample_counts = []
        for i, c in enumerate(chunks, 1):
            print(f"     chunk {i}/{len(chunks)}: {c[:60]}...")
            wav = model.generate(c, audio_prompt_path=args.reference,
                                 exaggeration=args.exaggeration, cfg_weight=args.cfg_weight)
            wav = wav.detach().cpu()
            if wav.dim() == 1:
                wav = wav.unsqueeze(0)
            sample_counts.append(wav.shape[-1])
            pieces.append(wav)
            pieces.append(gap)
```

- [ ] **Step 3: Write the sidecar after the wav is saved**

At the end of the per-file loop (after the `if abs(args.speed - 1.0)...` block that saves `out`, just before `print(f"     saved {out}")`), add:

```python
        gap_samples = int(sr * args.gap_ms / 1000)
        durations = chunk_durations(sample_counts, gap_samples, sr, args.speed)
        write_timing(os.path.splitext(out)[0] + ".timing.json", chunks, durations)
```

- [ ] **Step 4: Byte-compile to confirm no syntax break**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m py_compile tts_clone.py && echo OK`
Expected: `OK` (full run needs the model + venv; that is exercised in the manual smoke test in Task 7).

- [ ] **Step 5: Commit**

```bash
git add tts_clone.py
git commit -m "Write per-sentence timing sidecar during TTS synthesis"
```

---

### Task 3: `REC_PACE_LIST` support in `lib/pace.sh`

Let `pace` consume an explicit per-call hold list, falling back to the weighted rate.

**Files:**
- Modify: `lib/pace.sh` (the `pace()` function body)
- Test: `tests/test_pace.sh`

**Interfaces:**
- Produces: `pace()` honoring, in priority order, `REC_PACE_LIST` (i-th value on the i-th call) then `REC_PACE` (× weight arg); no-op when neither is set.

- [ ] **Step 1: Write the failing test**

```bash
# tests/test_pace.sh — verify pace() timing without real sleeps.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
check() { if [ "$2" = "$3" ]; then echo "ok - $1"; else echo "FAIL - $1: expected [$2] got [$3]"; fail=1; fi; }

# Shim sleep to print its argument instead of sleeping. Command-substitution
# subshells inherit this function, and pace.sh (sourced inside) calls it.
sleep() { printf '%s\n' "$1"; }

out="$( REC_PACE_LIST="1 2 3"; unset PACE_IDX REC_PACE 2>/dev/null; . "$ROOT/lib/pace.sh"; pace; pace; pace )"
check "list mode order" "$(printf '1\n2\n3')" "$out"

out="$( REC_PACE="0.5"; unset REC_PACE_LIST PACE_IDX 2>/dev/null; . "$ROOT/lib/pace.sh"; pace 4 )"
check "weighted mode" "2.00" "$out"

out="$( unset REC_PACE REC_PACE_LIST PACE_IDX 2>/dev/null; . "$ROOT/lib/pace.sh"; pace 5 )"
check "off mode silent" "" "$out"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ram.srinivasan/demo-video-maker && bash tests/test_pace.sh`
Expected: FAIL on "list mode order" (current `pace` ignores `REC_PACE_LIST`; prints `0.00` values or nothing).

- [ ] **Step 3: Replace the `pace()` body**

In `lib/pace.sh`, replace the `pace() { ... }` definition with:

```bash
pace() {
  # Recording-only. Priority: explicit per-call list (REC_PACE_LIST), else the
  # weighted single rate (REC_PACE * weight). No-op when neither is set.
  if [ -n "${REC_PACE_LIST:-}" ]; then
    : "${PACE_IDX:=0}"
    PACE_IDX=$((PACE_IDX + 1))
    local secs
    secs=$(printf '%s\n' $REC_PACE_LIST | sed -n "${PACE_IDX}p")
    [ -n "$secs" ] && { sleep "$secs" 2>/dev/null || true; }
    return 0
  fi
  [ -z "${REC_PACE:-}" ] && return 0
  local secs
  secs=$(awk -v p="$REC_PACE" -v w="${1:-1}" 'BEGIN{printf "%.2f", p*w}')
  sleep "$secs" 2>/dev/null || true
}
```

(Leave the file's leading comment block; only the function body changes. Note `PACE_IDX` is intentionally NOT `local` so it persists across calls within VHS's single `bash demo.sh` process.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ram.srinivasan/demo-video-maker && bash tests/test_pace.sh`
Expected: three `ok -` lines, exit 0.

- [ ] **Step 5: Commit**

```bash
git add lib/pace.sh tests/test_pace.sh
git commit -m "pace: support explicit per-call REC_PACE_LIST holds"
```

---

### Task 4: `align.py` — section extraction

**Files:**
- Create: `align.py`
- Test: `tests/test_align.py`

**Interfaces:**
- Produces: `extract_sections(demo_text: str) -> list[str]` — one label (joined echo text) per `pace` call, for the section printed just before it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_align.py
import unittest
import align

DEMO = '''#!/usr/bin/env bash
source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
type pace >/dev/null 2>&1 || pace() { :; }
echo "Acme CLI tour"
pace 37
echo "$ widget init"
echo "created myapp/"
pace 33
echo "$ widget build"
pace 25
'''


class ExtractSectionsTest(unittest.TestCase):
    def test_one_label_per_pace(self):
        self.assertEqual(
            align.extract_sections(DEMO),
            ["Acme CLI tour", "$ widget init created myapp/", "$ widget build"],
        )

    def test_no_pace_yields_empty(self):
        self.assertEqual(align.extract_sections('echo "hi"\n'), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_align -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'align'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python
"""Map narration sentences to demo steps with a local Ollama model, and print a
per-section hold list for render.sh. Exits non-zero on any failure so render.sh
falls back to proportional pacing. Local-only: talks to 127.0.0.1 Ollama."""
import re

PACE_RE = re.compile(r"^\s*pace\b")
ECHO_RE = re.compile(r"^\s*echo\s+(.*)$")


def extract_sections(demo_text):
    """One label per `pace` call: the echo text printed since the previous pace."""
    sections, buf = [], []
    for line in demo_text.splitlines():
        if PACE_RE.match(line):
            sections.append(" ".join(buf).strip())
            buf = []
            continue
        m = ECHO_RE.match(line)
        if m:
            text = m.group(1).strip().strip('"').strip("'")
            if text:
                buf.append(text)
    return sections
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_align -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add align.py tests/test_align.py
git commit -m "align: extract pace-delimited demo sections"
```

---

### Task 5: `align.py` — parse, validate, compute holds

Three pure functions that turn a model reply into per-section holds.

**Files:**
- Modify: `align.py`
- Test: `tests/test_align.py` (add cases)

**Interfaces:**
- Consumes: `extract_sections` (Task 4)
- Produces:
  - `parse_assignment(raw: str) -> list[int] | None` — pull a JSON int-array out of model output.
  - `validate_assignment(assignment: list[int], n_sentences: int, k: int) -> bool` — length == n, ints in `1..k`, non-decreasing, every section covered.
  - `compute_holds(durations: list[float], assignment: list[int], k: int) -> list[float]` — sum sentence durations per section (rounded to 3dp).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_align.py`:

```python
class ParseValidateHoldsTest(unittest.TestCase):
    def test_parse_plain(self):
        self.assertEqual(align.parse_assignment("[1, 1, 2]"), [1, 1, 2])

    def test_parse_with_prose(self):
        self.assertEqual(align.parse_assignment("Here you go:\n[1,2,2]\nthanks"), [1, 2, 2])

    def test_parse_garbage_is_none(self):
        self.assertIsNone(align.parse_assignment("no array here"))

    def test_validate_good(self):
        self.assertTrue(align.validate_assignment([1, 1, 2, 3], 4, 3))

    def test_validate_wrong_length(self):
        self.assertFalse(align.validate_assignment([1, 2], 4, 3))

    def test_validate_out_of_range(self):
        self.assertFalse(align.validate_assignment([1, 2, 4], 3, 3))

    def test_validate_not_monotonic(self):
        self.assertFalse(align.validate_assignment([1, 3, 2], 3, 3))

    def test_validate_section_uncovered(self):
        self.assertFalse(align.validate_assignment([1, 1, 3], 3, 3))  # section 2 missing

    def test_compute_holds(self):
        self.assertEqual(align.compute_holds([1.0, 2.0, 3.0, 4.0], [1, 1, 2, 3], 3), [3.0, 3.0, 4.0])
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_align -v`
Expected: FAIL — `AttributeError: module 'align' has no attribute 'parse_assignment'`

- [ ] **Step 3: Implement**

Add to `align.py` (add `import json` at top, next to `import re`):

```python
def parse_assignment(raw):
    m = re.search(r"\[[\s\d,]*\]", raw or "")
    if not m:
        return None
    try:
        val = json.loads(m.group(0))
    except ValueError:
        return None
    if isinstance(val, list) and all(isinstance(x, int) for x in val):
        return val
    return None


def validate_assignment(assignment, n_sentences, k):
    if not isinstance(assignment, list) or len(assignment) != n_sentences:
        return False
    if not all(isinstance(x, int) and 1 <= x <= k for x in assignment):
        return False
    if assignment != sorted(assignment):
        return False
    return set(assignment) == set(range(1, k + 1))


def compute_holds(durations, assignment, k):
    holds = [0.0] * k
    for dur, sec in zip(durations, assignment):
        holds[sec - 1] += dur
    return [round(h, 3) for h in holds]
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_align -v`
Expected: PASS (all extract + parse/validate/holds tests)

- [ ] **Step 5: Commit**

```bash
git add align.py tests/test_align.py
git commit -m "align: parse, validate, and sum per-section holds"
```

---

### Task 6: `align.py` — Ollama query, prompt, and `main` (with fallback exits)

**Files:**
- Modify: `align.py` (add `build_prompt`, `query_ollama`, `main`, `__main__` guard)
- Test: `tests/test_align.py` (add `main` tests with mocked `query_ollama`)

**Interfaces:**
- Consumes: all Task 4/5 functions.
- Produces:
  - `build_prompt(sentences: list[str], sections: list[str]) -> str`
  - `query_ollama(prompt: str, model: str, url: str) -> str` (network; not unit-tested directly)
  - `main(argv=None) -> None` — CLI: `--timing`, `--demo`, `--model` (default `qwen2.5:3b`), `--url` (default `http://127.0.0.1:11434/api/generate`). On success prints space-separated holds and exits 0. On any failure `sys.exit(1)`; zero sections `sys.exit(2)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_align.py` (add `import os, tempfile` and `from unittest import mock` at top):

```python
class MainTest(unittest.TestCase):
    def _fixture(self, d):
        timing = os.path.join(d, "demo.timing.json")
        with open(timing, "w") as f:
            f.write('[{"text":"Welcome to the tour.","dur":1.0},'
                    '{"text":"First we init.","dur":2.0},'
                    '{"text":"Then we build.","dur":3.0}]')
        demo = os.path.join(d, "demo.sh")
        with open(demo, "w") as f:
            f.write('echo "tour"\npace 1\necho "init"\npace 1\necho "build"\npace 1\n')
        return timing, demo

    def test_main_success_prints_holds(self):
        with tempfile.TemporaryDirectory() as d:
            timing, demo = self._fixture(d)
            with mock.patch("align.query_ollama", return_value="[1,2,3]"):
                with mock.patch("sys.stdout") as out:
                    with self.assertRaises(SystemExit) as cm:
                        align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 0)
            printed = "".join(c.args[0] for c in out.write.call_args_list)
            self.assertIn("1.0 2.0 3.0", printed)

    def test_main_ollama_unreachable_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            timing, demo = self._fixture(d)
            with mock.patch("align.query_ollama", side_effect=OSError("refused")):
                with self.assertRaises(SystemExit) as cm:
                    align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 1)

    def test_main_malformed_reply_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            timing, demo = self._fixture(d)
            with mock.patch("align.query_ollama", return_value="sorry, no"):
                with self.assertRaises(SystemExit) as cm:
                    align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 1)

    def test_main_no_pace_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            timing, _ = self._fixture(d)
            demo = os.path.join(d, "nopace.sh")
            with open(demo, "w") as f:
                f.write('echo "hi"\n')
            with self.assertRaises(SystemExit) as cm:
                align.main(["--timing", timing, "--demo", demo])
            self.assertEqual(cm.exception.code, 2)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_align -v`
Expected: FAIL — `AttributeError: module 'align' has no attribute 'main'`

- [ ] **Step 3: Implement**

Add to `align.py` (extend the top imports to `import argparse, json, re, sys` and `import urllib.request`):

```python
def build_prompt(sentences, sections):
    s_lines = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1))
    sec_lines = "\n".join(f"{i}. {s}" for i, s in enumerate(sections, 1))
    return (
        "You align a voice-over to a terminal demo.\n"
        f"There are {len(sections)} demo steps, shown in order:\n{sec_lines}\n\n"
        f"There are {len(sentences)} narration sentences, in order:\n{s_lines}\n\n"
        "Assign each narration sentence, in order, to the step it describes. "
        "Assignments must be non-decreasing (step numbers never go backwards) and "
        f"every step from 1 to {len(sections)} must be used at least once.\n"
        f"Reply with ONLY a JSON array of {len(sentences)} integers, e.g. [1,1,2,3]."
    )


def query_ollama(prompt, model, url):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode()).get("response", "")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print per-section hold seconds for render.sh.")
    ap.add_argument("--timing", required=True)
    ap.add_argument("--demo", required=True)
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--url", default="http://127.0.0.1:11434/api/generate")
    args = ap.parse_args(argv)

    with open(args.timing, encoding="utf-8") as f:
        timing = json.load(f)
    sentences = [e["text"] for e in timing]
    durations = [e["dur"] for e in timing]

    with open(args.demo, encoding="utf-8") as f:
        sections = extract_sections(f.read())
    k = len(sections)
    if k == 0:
        sys.exit(2)

    try:
        raw = query_ollama(build_prompt(sentences, sections), args.model, args.url)
    except Exception as e:
        print(f"align: ollama unavailable ({e})", file=sys.stderr)
        sys.exit(1)

    assignment = parse_assignment(raw)
    if assignment is None or not validate_assignment(assignment, len(sentences), k):
        print("align: model reply invalid — falling back", file=sys.stderr)
        sys.exit(1)

    holds = compute_holds(durations, assignment, k)
    print(" ".join(str(h) for h in holds))
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd /Users/ram.srinivasan/demo-video-maker && python3 -m unittest tests.test_align -v`
Expected: PASS (all align tests, including the four `main` cases)

- [ ] **Step 5: Commit**

```bash
git add align.py tests/test_align.py
git commit -m "align: Ollama query, prompt, and main with fallback exit codes"
```

---

### Task 7: Wire alignment into `render.sh`

Run `align.py` per demo; on success record with `REC_PACE_LIST`, else keep proportional pacing. Also warn when a demo has zero `pace` calls.

**Files:**
- Modify: `render.sh` (`build_tape`; per-demo loop)

**Interfaces:**
- Consumes: `align.py` CLI (Task 6); `<name>.timing.json` (Task 2); `REC_PACE_LIST` in `pace.sh` (Task 3).

- [ ] **Step 1: Extend `build_tape` to accept a hold list**

Replace the `build_tape()` function's signature/preamble and the `Type "... bash demo.sh"` line so holds, when present, are injected as `REC_PACE_LIST`:

```bash
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
```

- [ ] **Step 2: In the per-demo loop, warn on zero `pace` calls and attempt alignment**

In the per-demo `for d in "${DEMOS[@]}"; do` loop, immediately after the line that computes `SLEEP=...` and its `echo "    narration=..."`, insert:

```bash
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
```

- [ ] **Step 3: Pass HOLDS into `build_tape`**

Change the existing call `build_tape "$d" "$RP" "$SLEEP"` to:

```bash
  build_tape "$d" "$RP" "$SLEEP" "$HOLDS"
```

- [ ] **Step 4: Syntax-check and lint**

Run: `cd /Users/ram.srinivasan/demo-video-maker && bash -n render.sh && echo "syntax OK"`
Expected: `syntax OK`
Run (if available): `command -v shellcheck >/dev/null && shellcheck -S error render.sh || echo "shellcheck not installed — skipping"`
Expected: no error-level findings (or the skip message).

- [ ] **Step 5: Manual smoke test (documented; needs the full stack)**

The vhs/ffmpeg/Ollama pipeline can't be unit-tested. Verify manually when the environment is set up:

```bash
# With Ollama running + model pulled + a voice sample present:
./render.sh example-demo
# Expect a line like:  aligned holds: 12.3 8.1 5.0 5.0 ...
grep -n "aligned holds\|proportional pacing" build/align.log 2>/dev/null || true

# Fallback path (Ollama stopped): should still produce a video, logging the fallback.
OLLAMA_HOST=127.0.0.1:1 ./render.sh example-demo   # unreachable port -> fallback
```
Expected: first run reports aligned holds and produces `build/video/example-demo.mp4`; the fallback run prints "alignment unavailable — using proportional pacing" and still produces the mp4.

- [ ] **Step 6: Commit**

```bash
git add render.sh
git commit -m "render: use LLM-aligned holds when available, else proportional pacing"
```

---

### Task 8: Optional Ollama setup in `setup.sh` and `install.command`

Detect Ollama and pull the model; never fail the install if it's missing.

**Files:**
- Modify: `setup.sh` (after the venv/pip block, before the final `cat <<'EOT'` summary)
- Modify: `install.command` (inside the `if .venv/bin/pip install -r requirements.txt; then` success branch, before the SUCCESS banner)

**Interfaces:**
- Produces: a pulled `qwen2.5:3b` when Ollama is present; a clear note otherwise.

- [ ] **Step 1: Add the optional-model block to `setup.sh`**

Insert after `deactivate` (end of the pip section), before the closing summary heredoc:

```bash
echo "== checking optional alignment model (Ollama) =="
if command -v ollama >/dev/null; then
  ollama pull qwen2.5:3b || echo "  (couldn't pull qwen2.5:3b now — auto-sync falls back until it's available)"
else
  echo "  (ollama not found — narration/visual auto-sync will fall back to proportional pacing."
  echo "   Optional: install Ollama from https://ollama.com, then: ollama pull qwen2.5:3b)"
fi
```

- [ ] **Step 2: Add the same intent to `install.command`**

Inside the `if .venv/bin/pip install -r requirements.txt; then` branch, before the `SUCCESS!` banner `echo`s, add:

```bash
    echo "--> Checking optional alignment model (Ollama)..."
    if command -v ollama >/dev/null; then
        ollama pull qwen2.5:3b || echo "    (couldn't pull qwen2.5:3b now — auto-sync falls back until available)"
    else
        echo "    (Ollama not found — auto-sync will fall back to proportional pacing."
        echo "     Optional: install from https://ollama.com, then run: ollama pull qwen2.5:3b)"
    fi
```

- [ ] **Step 3: Syntax-check both scripts**

Run: `cd /Users/ram.srinivasan/demo-video-maker && bash -n setup.sh && bash -n install.command && echo "syntax OK"`
Expected: `syntax OK`

- [ ] **Step 4: Manual verification**

Run: `cd /Users/ram.srinivasan/demo-video-maker && ./setup.sh` (or re-run) and confirm it prints either the pull progress or the "ollama not found" note, and still completes without error.

- [ ] **Step 5: Commit**

```bash
git add setup.sh install.command
git commit -m "setup: optionally pull qwen2.5:3b for LLM-aligned pacing"
```

---

### Task 9: Document auto-sync in `README.md`

**Files:**
- Modify: `README.md` (Requirements list; the "How the pacing works" section)

> Note: this branch does not yet contain the separate `ui/placeholders-and-readme` edits. Apply these additions relative to the current `main` content of `README.md`.

- [ ] **Step 1: Add Ollama to the Requirements list**

After the `Python 3.12+` bullet under `## Requirements`, add:

```markdown
- **[Ollama](https://ollama.com)** *(optional)* — enables automatic narration↔visual
  sync via a small local model (`qwen2.5:3b`). Without it, pacing falls back to the
  proportional `pace`-weight method. Runs locally; nothing is uploaded.
```

- [ ] **Step 2: Document auto-sync in "How the pacing works"**

At the end of the `## How the pacing works` section (after the `prep.sh` paragraph), add:

```markdown
**Automatic sync (optional).** If [Ollama](https://ollama.com) is installed with
`qwen2.5:3b` pulled, render.sh measures each narration sentence's spoken length and
uses the model to map sentences to demo steps, holding each step exactly as long as
its narration — so rewording `narration.txt` re-syncs on the next render without
touching your `pace` numbers. The `pace` calls still mark where the steps are; only
the hold lengths become automatic. If Ollama is absent, unreachable, or unsure, it
silently falls back to the proportional method above (never worse than before). The
mapping call is local-only (`127.0.0.1`).
```

- [ ] **Step 3: Verify the Markdown renders sensibly**

Run: `cd /Users/ram.srinivasan/demo-video-maker && grep -n "Automatic sync\|Ollama" README.md`
Expected: the new lines appear in Requirements and in "How the pacing works".

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: describe optional Ollama-based automatic pacing sync"
```

---

## Self-Review

**Spec coverage:**
- Timing sidecar (spec §Components 1) → Tasks 1–2 ✅
- `align.py` extraction/prompt/validate/holds/fallback exits (§Components 2) → Tasks 4–6 ✅
- `lib/pace.sh` `REC_PACE_LIST` (§Components 3) → Task 3 ✅
- `render.sh` align step + no-pace warning + `PACE_WEIGHT=0` skip (§Components 4) → Task 7 ✅
- `setup.sh`/`install.command` optional Ollama pull (§Components 5) → Task 8 ✅
- README docs (§Components 6) → Task 9 ✅
- `requirements.txt` NO CHANGE (§Components) → honored; not touched by any task ✅
- Model `qwen2.5:3b`, local-only, auto-fallback, privacy (§Model/§Privacy) → Global Constraints + Tasks 6–8 ✅
- Testing strategy (§Testing) → unittest for align/timing, bash test for pace, manual e2e for render ✅

**Placeholder scan:** No TBD/TODO; every code step has concrete code; tests include real assertions. ✅

**Type consistency:** `extract_sections`/`parse_assignment`/`validate_assignment`/`compute_holds`/`build_prompt`/`query_ollama`/`main` names and signatures match between their defining task and their use in Task 6's `main` and Task 7's CLI invocation. `REC_PACE_LIST`, `PACE_IDX`, `ALIGN_MODEL`, and `<name>.timing.json` are spelled identically across Tasks 2, 3, 6, and 7. ✅
