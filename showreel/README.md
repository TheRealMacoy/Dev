# Motion Reel

A 15-second, 1080p60 motion graphics showreel, made entirely in code: no
After Effects, no stock footage, no samples. Every frame is a pure function of
time drawn on a 2D canvas, and the soundtrack is synthesized from scratch on the
same 120 BPM grid, so every cut, hit and bounce lands on the beat.

**Watch:** [`showreel.mp4`](showreel.mp4)

| Time | Chapter | What's going on |
| --- | --- | --- |
| 0:00 | Intro | A dot pops in, bounces with squash & stretch, stretches into a line that opens into the next scene |
| 0:01.5 | Kinetic type | Masked, staggered letter reveals, a colour-flip wipe, tracking-out, iris transition |
| 0:03.5 | Shape & rhythm | One path morphing circle → square → triangle → star on each beat, with radial arrays that tick in alternating directions |
| 0:05.5 | Particles | ~4,000 particles spiral out, converge on points sampled from the glyphs of "CLAUDE", then explode |
| 0:07.5 | 3D space | 400 instanced columns rippling to the kick, an orbiting perspective camera, a fly-through exit |
| 0:09.5 | Edit & pace | Eight cuts in two seconds, each with its own pattern, slam-in type and glitch slices |
| 0:11.5 | Fluid | Gooey metaballs (blur → contrast threshold → gradient tint) that merge and swallow the frame |
| 0:13.5 | End card | Name reveal; the dot from the first frame drops back in as the full stop |

## Build

Needs Node with Playwright (Chromium), Python 3 with NumPy, and ffmpeg.

```sh
./build.sh            # renders frames in parallel, synthesizes audio, encodes showreel.mp4
```

Open `index.html` in a browser for a live, looping preview.

- `index.html`: the renderer (`renderFrame(frame)`), all eight scenes plus the HUD, grain and vignette
- `render.mjs`: drives headless Chromium across several workers and saves each frame as a PNG
- `audio.py`: kick, claps, hats, sidechained sub bass, chord pad, arpeggio, risers, impacts
