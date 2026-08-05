# demo-video-maker

Turn a terminal demo into a **narrated video — in your own voice, with your face
badged in a corner**, paced so the on-screen action tracks what you're saying.

Everything runs **locally**. Your voice sample, your photo, and the finished
videos never leave your machine — nothing is uploaded to any service.

> New here and want the "why"? Read [`docs/why-this-exists.md`](docs/why-this-exists.md).

```
your voice sample  ─┐
your headshot       ├──►  ./render.sh my-demo  ──►  build/video/my-demo.mp4
demos/my-demo/      ┘        (voice + face + paced action)
```

---


## Quick Start (macOS)
> ⚠️ **First Time Opening on macOS?**
> macOS may block downloaded scripts on the first attempt.
>
> **Option A (System Settings):** If blocked, go to **System Settings > Privacy & Security**, scroll down to the **Security** section, and click **"Open Anyway"**.
> 
> **Option B (Terminal Fix):** Open Terminal in the project folder and run: `xattr -cr .`

If you downloaded this project as a ZIP or cloned it to your Mac:

1. **First-time setup:** Double-click **`Install.command`** in Finder. Wait until the terminal window displays `SUCCESS!`.
2. **Run the App:** Double-click **`Start VideoMaker.command`** to launch the interface!

### Quick Start Windows:
1. Double-click **`Install.bat`** in File Explorer (Wait for `SUCCESS!`).
2. Double-click **`Start VideoMaker.bat`** to launch!

---

## What it does

For each demo, one command produces an MP4 that:

- **Narrates in your own cloned voice**, synthesized from a ~1 minute sample.
- **Overlays your headshot** as a clean circular "presenter" badge.
- **Paces the demo to the narration** — each step stays on screen while you talk about it, instead of racing ahead and freezing at the end.
- **Is fully repeatable** — change the demo or the script, re-run, done.

---

## Requirements

- **[VHS](https://github.com/charmbracelet/vhs)** — records the terminal
- **ffmpeg** — muxes voice + badge
- **Python 3.12+** — runs the local voice model (tested up to Python 3.14 on Apple Silicon)
- **[Ollama](https://ollama.com)** *(optional)* — enables automatic narration↔visual
  sync via a small local model (`qwen2.5:3b`). Without it, pacing falls back to the
  proportional `pace`-weight method. Runs locally; nothing is uploaded.

> **Note for modern environments:** If you are running Python 3.12 to 3.14+ on Apple Silicon, your environment dependencies are fully managed and automatically patched out-of-the-box by our `requirements.txt`.

macOS:

```bash
brew install vhs ffmpeg python3
```

(Linux: install ffmpeg + python3 from your package manager; get VHS from its
[releases](https://github.com/charmbracelet/vhs#installation).)

---

## One-time setup (Command-Line)

```bash
./setup.sh
```

This checks your tools, creates an isolated virtual environment (`.venv`), and installs the voice model. 

> **Important:** Whenever you need to manually run or test the Python files directly, make sure to activate the environment first:
> ```bash
> source .venv/bin/activate
> ```

1. Drop a **60–90s voice sample** in [`voice-sample/`](voice-sample/README.md)
   (wav/mp3/m4a).
2. Put **your headshot** at `assets/presenter.jpg`
   (see [`assets/`](assets/README.md)).

---

## Launch the UI or Make your first video

### Running the App Interface:
```bash
python3 demovideomaker.py
```

### Running via Terminal Script:
The repo ships with a small, dependency-free example:

```bash
./render.sh example-demo
```

The first run also downloads the voice-model weights (one time). When it finishes:

```
build/video/example-demo.mp4
```

Open it — that's your voice, your face, and paced action, end to end.

> A sample of the finished output is checked in at
> [`docs/example-output.mp4`](docs/example-output.mp4) (voice + photo + a QR end
> card pointing back to this repo).

---

## Make it your own demo

A demo is just a folder under `demos/`:

```
demos/
  my-demo/
    demo.sh        # required — the demo (prints to the terminal)
    narration.txt  # required — the script, in your words
    demo.conf      # optional — badge corner, pace weight override
    prep.sh        # optional — slow/off-topic setup, run off-camera
```

**1. Copy the example and edit the demo:**

```bash
cp -r demos/example-demo demos/my-demo
```

Replace the `echo`s in `demos/my-demo/demo.sh` with your real demo — a CLI, a
`psql` session, an API walkthrough, anything that prints to a terminal.

**2. Add pacing.** Keep these two lines near the top of `demo.sh`:

```bash
source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
type pace >/dev/null 2>&1 || pace() { :; }
```

Then drop `pace <weight>` calls **between sections**. The weight is roughly the
number of narration words spent on the section that just appeared:

```bash
run_step_one
pace 40      # ~40 words of narration cover step one

run_step_two
pace 25      # ~25 words cover step two
```

`pace` does nothing when you run the demo yourself — it only kicks in while
recording. So your normal `bash demo.sh` is unaffected.

**3. Write the narration** in `narration.txt` — plain text, written in your natural speech patterns. Rough guide: ~150 words per minute of video.

> **Note on text formatting:** Keep the narration script entirely clean. Avoid markdown syntax, emojis, or bracketed sound cues (like `[laughs]`), as the local text-to-speech engine will attempt to vocalize them literally.

**4. Render:**

```bash
./render.sh my-demo          # just this one
./render.sh                  # everything under demos/
```

---

## How the pacing works

Terminal demos finish in seconds; narration takes a minute. render.sh measures
both, then sizes the `pace` holds so the demo **stretches to match the voice-over
and ends with it** — no dead freeze at the end. Because each hold is weighted by
its narration length, the on-screen action tracks the story.

**Real-time demos** (something that already runs *longer* than its narration —
e.g. a live rebuild) shouldn't be stretched. Set `PACE_WEIGHT=0` in `demo.conf`
and render.sh plays your voice over the live action instead.

**Slow setup?** If your demo needs minutes of setup that shouldn't be on camera
(building containers, seeding data), put it in `prep.sh`. render.sh runs it
off-camera before recording, so only the payoff is captured.

**Automatic sync (optional).** If [Ollama](https://ollama.com) is installed with
`qwen2.5:3b` pulled, render.sh measures each narration sentence's spoken length and
uses the model to map sentences to demo steps, holding each step exactly as long as
its narration — so rewording `narration.txt` re-syncs on the next render without
touching your `pace` numbers. The `pace` calls still mark where the steps are; only
the hold lengths become automatic. If Ollama is absent, unreachable, or unsure, it
silently falls back to the proportional method above (never worse than before). The
mapping call is local-only (`127.0.0.1`).

---

## The QR end card

Each video ends with a card showing a **QR code + URL** so viewers can go make
their own. By default the URL is your repo's own GitHub remote, so it just works:

- Override or disable it: `OUTRO_URL="https://example.com" ./render.sh` (or
  `OUTRO_URL="" ./render.sh` to turn it off).
- Slightly slower narration reads better: `NARRATION_SPEED` is `0.92` by default;
  set e.g. `NARRATION_SPEED=1.0` for full speed.

The end card is appended as a cheap post-step, so changing the URL doesn't require
re-recording anything.

---

## Configuration (`demo.conf`, all optional)

| Key | Values | Default | Meaning |
|-----|--------|---------|---------|
| `BADGE_CORNER` | `top-right`, `top-left`, `bottom-right`, `bottom-left` | `top-right` | Where the photo badge sits |
| `PACE_WEIGHT` | integer | auto-summed from `pace N` lines | Override the total; `0` disables stretching |

---

## Layout

```
Install.command      one-click installer shortcut for macOS
Start VideoMaker.command double-click app launcher shortcut
demovideomaker.py    desktop UI application
render.sh            orchestrator: synth voice -> record -> mux
tts_clone.py         local voice cloning (Chatterbox)
setup.sh             one-time environment setup
lib/pace.sh          the `pace` helper your demos source
assets/              your headshot (presenter.jpg) + generated badge
voice-sample/        your voice clip
demos/<name>/        one folder per demo
build/               all output (git-ignored): audio/, silent/, video/
docs/                the write-up
```

---

## Troubleshooting

### "python not found" or broken virtual environment
If you source your `.venv` and running scripts throws errors or claims `python` cannot be found, your system's underlying global Python package manager likely updated (breaking internal environment symlinks). 

You can completely reset the environment back to a healthy state without losing any of your saved assets or configuration:

```bash
deactivate
rm -rf .venv
./setup.sh
```
*(Or simply double-click `Install.command` again).*

---

## Tips

- **Approve the voice on one short clip first**, then batch the rest.
- **Eyeball a few frames** of the finished video, not just the terminal output —
  recording quirks hide there.
- Everything is text and lives next to the demo, so anyone can tweak a sentence
  and regenerate. No "where's the source for that video?" six months later.

---

*Built to be shared. If you improve it, send the change back so everyone gets it.*