"""Synthesizes the 15s soundtrack for the Smart Furniture Lab reveal (120 BPM).

Usage: python3 audio.py out.wav
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 15.0
BEAT = 0.5
N = int(SR * DUR)
T = np.arange(N) / SR
rng = np.random.default_rng(9)
mix = np.zeros((N, 2))


def place(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l, sig * r], axis=1) * np.sqrt(2)
    mix[i:i + len(sig)] += sig * gain


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def lowpass(x, cutoff):
    cutoff = np.broadcast_to(cutoff, x.shape)
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def noise(n):
    return rng.uniform(-1, 1, n)


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def knock(freq=420, decay=.05):
    """Wood block: a damped inharmonic pair with a click."""
    n = int(.25 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * freq * t) + .5 * np.sin(2 * np.pi * freq * 2.76 * t)
    click = (noise(n) - lowpass(noise(n), 2000)) * env(n, .0003, .003)
    return body * env(n, .0008, decay) + click * .6


def kick():
    n = int(.4 * SR)
    t = np.arange(n) / SR
    return np.tanh(np.sin(2 * np.pi * np.cumsum(46 + 120 * np.exp(-t * 30)) / SR) * env(n, .001, .2) * 1.6)


def hat(decay=.03):
    n = int(.12 * SR)
    x = noise(n)
    return (x - lowpass(x, 7000)) * env(n, .0005, decay)


def clap():
    n = int(.3 * SR)
    x = noise(n)
    x = x - lowpass(x, 1000)
    e = sum(env(n, .0005, .01) * (np.arange(n) >= int(d * SR)) for d in (0, .011, .022))
    return x * (e + env(n, .0005, .1) * .5 * (np.arange(n) >= int(.03 * SR)))


def boom(length=2.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(32 + 85 * np.exp(-t * 9)) / SR) * env(n, .002, .6)
    return np.tanh(sub * 1.5 + lowpass(noise(n), 2500) * env(n, .001, .18))


def whoosh(length, up=False):
    n = int(length * SR)
    p = np.linspace(0, 1, n)
    shape = p ** 3 if up else np.sin(np.pi * p) ** 2
    return lowpass(noise(n), 400 + 7000 * shape) * shape * 1.8


def pluck(freq, decay=.35):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    saw = 2 * ((freq * t) % 1) - 1
    return lowpass(saw, 500 + 4000 * np.exp(-t * 18)) * env(n, .002, decay)


def bell(freq, decay=1.2):
    n = int(3 * SR)
    t = np.arange(n) / SR
    return sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / (decay / r ** .5))
               for r, a in ((1, 1), (2.0, .5), (3.01, .25), (4.2, .12))) * np.minimum(1, t / .003)


def blip(freq, length=.08):
    n = int(length * SR)
    t = np.arange(n) / SR
    return np.sign(np.sin(2 * np.pi * freq * t)) * env(n, .001, .025) * .5


# ---- 0–1.8: blueprint ----
air = lowpass(noise(N), 900) * np.clip(T / 1.2, 0, 1) * np.clip((1.8 - T) / .3, 0, 1)
place(air * .05, 0)
for k, t in enumerate((.5, .75, .92)):
    place(knock(380 + k * 40, .06), t, .5 - k * .12)
place(whoosh(.4), .9, .35, pan=-.2)
place(whoosh(.5, up=True), 1.3, .45)

# ---- 1.8–9.8: groove (beats on 1.8 + 0.5k) ----
G0 = 1.8
beats = [G0 + b * BEAT for b in range(16)]
for b, t in enumerate(beats):
    place(kick(), t, .8)
    place(hat(), t + .25, .2, pan=.3)
    if t >= 3.8:
        place(hat(.012), t + .125, .08, pan=-.3)
        place(hat(.012), t + .375, .08, pan=-.3)
    if b % 2 == 1:
        place(clap(), t, .38)
duck = np.ones(N)
for t in beats:
    i = int(t * SR)
    n = int(.3 * SR)
    duck[i:i + n] = np.minimum(duck[i:i + n], 1 - .8 * np.exp(-np.arange(n) / SR / .08))
chords = [(45, (57, 60, 64)), (41, (57, 60, 65)), (48, (55, 60, 64)), (43, (55, 59, 62))]
bass = np.zeros(N)
pad = np.zeros(N)
for k in range(4):
    root, ch = chords[k]
    s0, e0 = int((G0 + k * 2) * SR), int(min(G0 + k * 2 + 2, 9.8) * SR)
    seg = T[s0:e0] - T[s0]
    bass[s0:e0] += np.tanh(2 * np.sin(2 * np.pi * note(root) * seg))
    for m in ch:
        for d in (-.1, .1):
            pad[s0:e0] += (2 * ((note(m) * 2 ** (d / 12) * seg) % 1) - 1) / 7
place(lowpass(bass, 230) * duck * .5, 0)
place(np.stack([lowpass(pad, 1300) * (.4 + .6 * duck)] * 2, 1) * .18, 0)

# solid pine: a deep wooden bloom as the log grows, rings ticking, then the saw
place(boom(), 1.8, .55)
place(knock(140, .25), 1.8, .5)
for i in range(18):
    place(knock(900 + i * 40, .012), 1.86 + i * .022, .05, pan=np.sin(i))
n = int(.5 * SR)
tt = np.arange(n) / SR
saw = np.sign(np.sin(2 * np.pi * 95 * tt + 3 * np.sin(2 * np.pi * 7 * tt))) * .3 + (noise(n) - lowpass(noise(n), 1500)) * .7
place(saw * np.sin(np.linspace(0, np.pi, n)) ** .5 * .22, 2.8, pan=.1)
for j in range(7):
    place(knock(250 + j * 30, .04), 3.3 + j * .02, .25, pan=(j - 3) * .15)
place(whoosh(.4), 3.4, .4)

# beds: a pluck and a wooden thunk on every change
place(boom(1.5), 3.8, .45)
for i, (t, m) in enumerate(((3.8, 69), (4.3, 72), (4.8, 76), (5.3, 74), (6.3, 79))):
    place(pluck(note(m), .3), t, .22, pan=-.2)
    place(knock(220 + i * 25, .08), t + .05, .35)
for i in range(4):  # bed parts landing
    place(knock(500 + i * 90, .03), 3.82 + i * .1, .2)
place(knock(180, .12), 4.15, .3)  # mattress drops
for i in range(6):  # ladder rungs
    place(knock(1100 + i * 80, .02), 5.8 + i * .06, .12)
place(whoosh(.35), 6.5, .4)

# storage: a wooden clack as each drawer unit lands, drawers slide in a wave
place(boom(1.2), 6.8, .45)
for n_ in range(9):
    place(knock(300 + (n_ * 37) % 220, .05), 6.85 + n_ * .085 + .14, .4, pan=((n_ % 3) - 1) * .4)
for j in range(5):
    place(whoosh(.18) * .6, 7.55 + j * .08, .22)
    place(knock(900, .02), 7.72 + j * .08, .18)
for j in range(4):
    place(knock(700, .02), 8.4 + j * .03, .15)
place(whoosh(.3), 8.55, .4)

# the range: eight cuts
place(boom(.8), 8.8, .45)
for k in range(8):
    place(blip(note(74 + k * 2)), 8.8 + k * .125, .2, pan=(-1) ** k * .4)
    place(knock(600 + k * 50, .03), 8.8 + k * .125, .22)
place(whoosh(.45, up=True), 9.35, .5)

# ---- 9.8–15: logo build ----
L0 = 0.8
place(boom(2.5), 9.8, .7)
lp = np.zeros(N)
for m in (45, 52, 57, 60, 64, 69):
    for d in (-.08, .08):
        lp += (2 * ((note(m) * 2 ** (d / 12) * T) % 1) - 1)
lp = lowpass(lp / 12, 600 + 1400 * np.clip((T - 9.8) / 3, 0, 1)) * np.clip((T - 9.8) / 1.2, 0, 1) * np.clip((15 - T) / 2.2, 0, 1)
place(np.stack([lp, np.roll(lp, 700)], 1) * .2, 0)
place(blip(1760, .05), 9.05 + L0, .2)
place(whoosh(.6), 9.25 + L0, .4)
place(bell(note(57), 1.6), 9.6 + L0, .35)
n = int(1.5 * SR)
tt = np.arange(n) / SR
place(np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-tt * 6)) / SR) * np.exp(-tt / .6), 9.6 + L0, .45)
for i, m in enumerate((69, 72, 76)):
    place(pluck(note(m), .4), 10.1 + L0 + i * .12, .2, pan=-.2 + i * .2)
for i, m in enumerate((64, 67, 69, 72, 74, 76, 79, 81, 84)):
    place(pluck(note(m), .3), 10.5 + L0 + i * .09, .14, pan=np.sin(i) * .5)
for i, m in enumerate((88, 91, 93, 96, 100)):
    place(bell(note(m), .6), 11.25 + L0 + i * .1, .05)
place(boom(2.2), 12.0 + L0, .45)
for m in (57, 64, 69, 72, 76, 81):
    place(bell(note(m), 2.0), 12.0 + L0, .07)
cym_n = int(2.2 * SR)
cym = (noise(cym_n) - lowpass(noise(cym_n), 6000)) * env(cym_n, .4, 1.0)
place(cym * .12, 12.4)
for i in range(3):
    place(knock(1400 - i * 200, .03), 12.9 + i * .12, .1)

# ---- master ----
wet = np.zeros_like(mix)
for d, g in ((.087, .3), (.131, .22), (.199, .15), (.283, .1), (.4, .06)):
    s = int(d * SR)
    wet[s:, 0] += mix[:-s, 1] * g
    wet[s:, 1] += mix[:-s, 0] * g
out = mix + wet * .5
out /= np.max(np.abs(out)) + 1e-9
out = np.tanh(out * 1.1) / np.tanh(1.1) * .89
fo = int(.6 * SR)
out[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote soundtrack")
