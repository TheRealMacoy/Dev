# Smart Furniture Lab: Logo Reveal

A 15-second, 1080p60 motion reel that ends on the Smart Furniture Lab logo,
made in code with a synthesized soundtrack on a 120 BPM grid.

**Watch:** [`smart_furniture_lab_reveal.mp4`](smart_furniture_lab_reveal.mp4)

| Time | What happens |
| --- | --- |
| 0:00 | Blueprint grid draws on; the green dot falls and bounces; a dimension line opens; the dot wipes into green |
| 0:02 | Line-drawn chair, table, lamp, sofa and shelf, one per beat |
| 0:04.5 | Isometric modular shelving assembles; green drawers slide out |
| 0:07 | Eight cuts: MODULAR, CRAFTED, CONNECTED, ERGONOMIC, SUSTAINABLE, SMART, FURNITURE, LAB |
| 0:09 | Logo build: the rule draws out, the circle blooms, LAB rises, FURNITURE drops in, Smart settles |
| 0:12 | Light sweep across the finished mark, then a clean hold |

The logo is rebuilt as vectors (Inter and Inter Display, condensed) from the
reference image. Swap in the original artwork for exact letterforms.

```sh
python3 audio.py soundtrack.wav
node render.mjs frames 4
ffmpeg -framerate 60 -i frames/f_%04d.png -i soundtrack.wav -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -shortest smart_furniture_lab_reveal.mp4
```
