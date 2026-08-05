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
