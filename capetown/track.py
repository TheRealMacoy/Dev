"""Tracks landmark anchors through the drone footage with patch phase correlation.

Usage: python3 track.py   (reads data/video/v_*.jpg, writes data/tracks.json)
"""
import glob
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
# Anchor positions picked on the first frame (1920x1080)
ANCHORS = {
    "table": (1040, 232), "lion": (1604, 286), "devil": (588, 250),
    "signal": (1290, 430), "stadium": (737, 712), "waterfront": (150, 655),
}
P = 72  # half patch size in px


def gray(path):
    return np.asarray(Image.open(path).convert("L"), np.float32)


def shift(a, b):
    """Translation that moves patch a onto patch b."""
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    A, B = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = np.fft.ifft2(B * np.conj(A) / (np.abs(B * np.conj(A)) + 1e-6)).real
    y, x = np.unravel_index(np.argmax(r), r.shape)
    def sub(v, n, axis):
        # parabolic sub-pixel refinement
        l, c, rr = (r[(y - 1) % r.shape[0], x], r[y, x], r[(y + 1) % r.shape[0], x]) if axis == 0 else \
                   (r[y, (x - 1) % r.shape[1]], r[y, x], r[y, (x + 1) % r.shape[1]])
        d = (l - rr) / (2 * (l - 2 * c + rr) + 1e-9)
        v = v + d
        return v - n if v > n / 2 else v
    return sub(x, r.shape[1], 1), sub(y, r.shape[0], 0)


frames = sorted(glob.glob(os.path.join(HERE, "data/video/v_*.jpg")))
tracks = {k: [list(v)] for k, v in ANCHORS.items()}
prev = gray(frames[0])
for f in frames[1:]:
    cur = gray(f)
    for k, tr in tracks.items():
        x, y = tr[-1]
        xi, yi = int(round(x)), int(round(y))
        x0, y0 = max(0, xi - P), max(0, yi - P)
        x1, y1 = min(cur.shape[1], xi + P), min(cur.shape[0], yi + P)
        dx, dy = shift(prev[y0:y1, x0:x1], cur[y0:y1, x0:x1])
        tr.append([x + dx, y + dy])
    prev = cur
# light smoothing to remove sub-pixel jitter
out = {}
for k, tr in tracks.items():
    a = np.array(tr)
    ker = np.ones(5) / 5
    sm = np.stack([np.convolve(np.pad(a[:, i], 2, mode="edge"), ker, "valid") for i in range(2)], 1)
    out[k] = np.round(sm, 2).tolist()
    print(k, a[0].round(1), "->", a[-1].round(1))
json.dump(out, open(os.path.join(HERE, "data/tracks.json"), "w"))
