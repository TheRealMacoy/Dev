# Smart Furniture Lab: Logo Reveal

A 15-second, 1080p60 motion reel that ends on the Smart Furniture Lab logo,
made in code with a synthesized soundtrack on a 120 BPM grid.

**Watch:** [`smart_furniture_lab_reveal.mp4`](smart_furniture_lab_reveal.mp4)

| Time | What happens |
| --- | --- |
| 0:00 | Blueprint grid draws on; the green dot falls and bounces; the dot floods the screen green |
| 0:01.8 | Solid pine: a log cross-section grows its rings, then is sawn into planks that stretch into a board wall |
| 0:03.8 | One bed, morphing on the beat: single → double → queen (a dimension line tracks the width) |
| 0:05.3 | It becomes a bunk bed (a second tier rises, the ladder builds), then strips back to the headboard |
| 0:06.8 | Isometric pine storage drawers assemble, and the drawers slide out in a wave |
| 0:08.8 | The range in eight cuts: SINGLE, DOUBLE, QUEEN, BUNK, STORAGE, HEADBOARDS, SOLID, PINE |
| 0:09.8 | Logo build: the rule, the circle, LAB, FURNITURE, Smart; light sweep; product line underneath |

The pine grain is procedural (growth rings, knots), so every plank and drawer
front gets its own patch of wood.

The logo is rebuilt as vectors (Inter and Inter Display, condensed) from the
reference image. Swap in the original artwork for exact letterforms.

```sh
python3 audio.py soundtrack.wav
node render.mjs frames 4
ffmpeg -framerate 60 -i frames/f_%04d.png -i soundtrack.wav -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -shortest smart_furniture_lab_reveal.mp4
```
