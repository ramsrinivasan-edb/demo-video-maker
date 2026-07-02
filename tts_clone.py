#!/usr/bin/env python
"""Offline voice-over synthesis with Chatterbox, cloning your voice sample.

Each positional argument is a narration text file. The output wav is named after
the file's PARENT DIRECTORY, so:

    demos/my-demo/narration.txt  ->  <out-dir>/my-demo.wav

Long scripts are split into sentence-sized chunks (Chatterbox is tuned for short
utterances) and concatenated with a small pause, so a whole paragraph comes out
steady. Runs entirely on your machine; nothing is uploaded.
"""
import argparse
import os
import re
import subprocess

# Let unsupported Apple-Silicon (MPS) ops fall back to CPU instead of crashing.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
import torchaudio
from chatterbox.tts import ChatterboxTTS


def split_sentences(text, max_chars=280):
    """Sentence-ish chunks under max_chars, so each generate() stays short."""
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    chunks, cur = [], ""
    for p in parts:
        if not p:
            continue
        if len(cur) + len(p) + 1 <= max_chars:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def out_name(path):
    """Name the wav after the narration file's parent directory."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    return parent or os.path.splitext(os.path.basename(path))[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", required=True, help="your voice sample (wav/mp3/m4a)")
    ap.add_argument("--out-dir", default="build/audio")
    ap.add_argument("--device", default="mps", choices=["mps", "cpu", "cuda"])
    ap.add_argument("--exaggeration", type=float, default=0.5)
    ap.add_argument("--cfg-weight", type=float, default=0.5)
    ap.add_argument("--gap-ms", type=int, default=280, help="silence between chunks")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="playback tempo, pitch-preserved (e.g. 0.92 = slightly slower)")
    ap.add_argument("narration", nargs="+", help="one or more narration .txt files")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    print(f">> loading Chatterbox on {args.device} (first run downloads the model)")
    try:
        model = ChatterboxTTS.from_pretrained(device=args.device)
    except Exception as e:
        print(f"!! {args.device} load failed ({e}); falling back to cpu")
        model = ChatterboxTTS.from_pretrained(device="cpu")
    sr = model.sr
    gap = torch.zeros(1, int(sr * args.gap_ms / 1000))

    for path in args.narration:
        name = out_name(path)
        out = os.path.join(args.out_dir, name + ".wav")
        text = open(path, encoding="utf-8").read().strip()
        if not text:
            print(f"!! {path} is empty — skipping")
            continue
        chunks = split_sentences(text)
        print(f">> [{name}] {len(chunks)} chunks -> {out}")
        pieces = []
        for i, c in enumerate(chunks, 1):
            print(f"     chunk {i}/{len(chunks)}: {c[:60]}...")
            wav = model.generate(c, audio_prompt_path=args.reference,
                                 exaggeration=args.exaggeration, cfg_weight=args.cfg_weight)
            wav = wav.detach().cpu()
            if wav.dim() == 1:
                wav = wav.unsqueeze(0)
            pieces.append(wav)
            pieces.append(gap)
        full = torch.cat(pieces, dim=1)
        if abs(args.speed - 1.0) > 1e-3:
            # Slow (or speed) the delivery without changing pitch, via ffmpeg atempo.
            tmp = out + ".tmp.wav"
            torchaudio.save(tmp, full, sr)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp,
                            "-filter:a", f"atempo={args.speed}", out], check=True)
            os.remove(tmp)
        else:
            torchaudio.save(out, full, sr)
        print(f"     saved {out}")
    print(">> done. wavs in", args.out_dir)


if __name__ == "__main__":
    main()
