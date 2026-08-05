#!/usr/bin/env python
"""Map narration sentences to demo steps with a local Ollama model, and print a
per-section hold list for render.sh. Exits non-zero on any failure so render.sh
falls back to proportional pacing. Local-only: talks to 127.0.0.1 Ollama."""
import json
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
