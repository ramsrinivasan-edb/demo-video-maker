#!/usr/bin/env python
"""Map narration sentences to demo steps with a local Ollama model, and print a
per-section hold list for render.sh. Exits non-zero on any failure so render.sh
falls back to proportional pacing. Local-only: talks to 127.0.0.1 Ollama."""
import argparse
import json
import re
import sys
import urllib.request

PACE_RE = re.compile(r"^\s*pace\b")
ECHO_RE = re.compile(r"^\s*echo\s+(.*)$")


def extract_sections(demo_text):
    """One label per `pace` call: the echo text printed since the previous pace.

    Assumes a linear demo: one runtime `pace` execution per textual `pace` line.
    `pace` inside loops or conditionals will desync the returned sections from
    the runtime REC_PACE_LIST — use a flat script to guarantee alignment."""
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
