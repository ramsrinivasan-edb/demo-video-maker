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
