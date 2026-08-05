# Narrated demo videos — in your own voice, with your face in the corner (100% offline)

*How I turned a set of plain terminal demos into polished, narrated videos — voiced by me, badged with my photo — without a microphone, a studio, or uploading anything to the cloud. And how you can do the same for your demos this afternoon.*

---

## The problem

We all build great demos. Then we try to *share* them and hit the usual walls:

- **Live demos don't scale.** You can't be on every call, in every timezone, forever.
- **Recording narration is painful.** Booking a quiet room, re-recording every time a number changes, hating your own "um"s.
- **Screen recordings alone are flat.** A wall of terminal output with no voice and no face is hard to follow and easy to ignore.

I wanted something that felt personal — *my* voice, *my* face — but that I could regenerate in one command whenever the demo changed. And because our demos touch real product internals, I wanted it to run **entirely on my laptop**, with nothing sent to any third-party service.

Here's what I ended up with, and the recipe so you can reuse it.

---

## What you get

For each demo, a single command produces an MP4 that:

- **Narrates in your own cloned voice** — synthesized from a ~1 minute sample of you talking.
- **Puts your headshot in the corner** as a clean circular "presenter" badge, so it feels like *you* are walking the viewer through it.
- **Paces the on-screen action to the narration** — the demo doesn't race ahead and freeze; each step stays on screen while you talk about it.
- **Is fully repeatable** — change the demo or the script, re-run, done. No studio, no re-shoot.

Same personality every time, zero microphone anxiety.

---

## The ingredients

Everything here is free and runs locally.

| Purpose | Tool | Notes |
|---|---|---|
| Record the terminal | **VHS** (charmbracelet) | Drives a terminal from a small "tape" script and outputs an MP4 |
| Clone your voice | **Chatterbox TTS** (MIT) | Local voice-cloning model, runs in a Python venv |
| Stitch it together | **ffmpeg** | Muxes the voice-over onto the video and overlays your photo |
| Run the demo | **Docker** | Only because my demos happen to use it; not required in general |

Plus two personal assets you provide once:

1. **A voice sample** — about 60–90 seconds of you speaking naturally (a mono `.wav`/`.m4a` is fine). Read anything; content doesn't matter, tone does. Speak the way you'd narrate.
2. **A headshot** — any clean photo. A plain background crops best into a circle.

> **Privacy note:** the voice model and everything else run on your machine. Your voice sample, your photo, and the demo output never leave your laptop. That was a hard requirement for me and it's worth calling out to your own stakeholders.

---

## How it works — three stages

Think of it as an assembly line. A short script glues the three stages together, but conceptually:

### 1. Write the narration, then synthesize it in your voice
You write the script as plain text — one file per demo. The voice-cloning model reads your text and your voice sample and produces a `.wav` that sounds like you reading it. Long scripts get split into sentence-sized chunks so the delivery stays steady, then joined back together.

Rewrite a sentence? Re-synthesize in seconds. No booth, no retakes.

### 2. Record the terminal, paced to the narration
A tiny VHS "tape" launches the demo and records the terminal to a silent MP4. The trick that makes it look intentional: **the demo holds between sections so the action lines up with what you're saying.** More on that below — it's the single biggest quality lever.

### 3. Mux the voice + badge onto the video
ffmpeg lays the voice-over onto the recording (with a small lead-in so it doesn't start cold) and composites your circular photo badge into a corner. Out comes the final MP4.

---

## The touches that make it look professional

Anyone can slap audio on a screen recording. A few small decisions are what make it feel produced:

**Pace the demo to the voice, not the other way around.**
Terminal demos finish in seconds; narration takes a minute. If you just glue them together, the demo blasts through and then freezes for 45 seconds while you're still talking — it looks broken. The fix is to insert deliberate *holds* between demo sections, sized so each section stays on screen for as long as you spend narrating it. I weight each hold by how many words the narration spends on that section, so the on-screen action tracks the story ("weighted sync"). The holds only exist while recording — the demo still runs full-speed in normal use.

**Keep the boring setup off-camera.**
One of my demos spent its first minute building a database before the interesting part. That minute has no business being in the video. So the setup runs *before* recording starts, and only the payoff is captured. If your demo has a slow warm-up, hide it.

**A circular badge beats a rectangle.**
A round headshot with a thin white ring in a corner reads as "presenter," not "someone pasted a photo on a slide." Top-right tends to stay clear of terminal output, which flows from the top-left.

**Match the final length to the narration.**
Trim the trailing dead air so the video ends when you stop talking (unless the demo genuinely needs to keep running).

---

## Lessons learned (so you don't repeat my afternoon)

- **Approve the voice on one short clip first.** Generate a single video, listen, confirm it sounds like you — *then* batch the rest. Don't synthesize an hour of audio before you've heard 30 seconds.
- **The voice sample quality is everything.** A clean, natural 60–90s sample beats a long, noisy one. Speak in your narrating voice.
- **Automate the timing math.** Let the script measure how long the demo runs and how long the narration is, and compute the pacing itself. Hand-tuning sleep values per demo is a rabbit hole.
- **Small automation bugs hide in the recording, not the terminal.** I had a pacing bug that behaved fine when run by hand but silently froze inside the recorder. Always eyeball a few frames of the finished video, not just the terminal output.
- **Everything is text and reproducible.** Narration scripts, tapes, and the render script all live next to the demo. Anyone can tweak a sentence and regenerate — no "where's the source file for that video?" six months later.

---

## Want to try it on your demo?

You need surprisingly little:

1. Install VHS, ffmpeg, and set up the voice model in a Python venv (one-time).
2. Drop in your **voice sample** and your **headshot**.
3. Write a short **narration** for your demo (a paragraph or two).
4. Point the render script at your demo and run it.

That's it. The first video takes an afternoon to wire up; every one after that is a single command.

I'm happy to share the exact scripts and walk anyone through it — the pipeline is demo-agnostic, so it works just as well for a CLI tool, an API walkthrough, or a UI click-through as it did for mine. If a few of us adopt this, we could have a **consistent, personal, self-serve library of product demos** that any of us can regenerate the moment the product changes.

Reach out and I'll get you started.

*— Ramalingam Srinivasan*
