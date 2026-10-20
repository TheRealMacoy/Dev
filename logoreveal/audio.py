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


# ---- 0–2: blueprint ----
air = lowpass(noise(N), 900) * np.clip(T / 1.2, 0, 1) * np.clip((2.0 - T) / .3, 0, 1)
place(air * .05, 0)
for k, t in enumerate((.5, .75, .92)):
    place(knock(380 + k * 40, .06), t, .5 - k * .12)
place(whoosh(.4), .95, .35, pan=-.2)  # dimension line opens
for i in range(10):
    place(blip(2600 + i * 60, .02), 1.0 + i * .04, .05)
place(whoosh(.55, up=True), 1.45, .45)

# ---- 2–9: groove ----
for b in range(4, 18):
    t = b * BEAT
    place(kick(), t, .8)
    place(hat(), t + .25, .2, pan=.3)
    place(hat(.012), t + .125, .08, pan=-.3)
    place(hat(.012), t + .375, .08, pan=-.3)
    if b % 2 == 1:
        place(clap(), t, .38)
duck = np.ones(N)
for b in range(4, 18):
    i = int(b * BEAT * SR)
    n = int(.3 * SR)
    duck[i:i + n] = np.minimum(duck[i:i + n], 1 - .8 * np.exp(-np.arange(n) / SR / .08))
chords = [(45, (57, 60, 64)), (41, (57, 60, 65)), (48, (55, 60, 64)), (43, (55, 59, 62))]
bass = np.zeros(N)
pad = np.zeros(N)
for k in range(4):
    root, ch = chords[k]
    s, e = int((2 + k * 2) * SR), int((4 + k * 2) * SR)
    e = min(e, int(9 * SR))
    if s >= e:
        continue
    seg = T[s:e] - T[s]
    bass[s:e] += np.tanh(2 * np.sin(2 * np.pi * note(root) * seg))
    for m in ch:
        for d in (-.1, .1):
            pad[s:e] += (2 * ((note(m) * 2 ** (d / 12) * seg) % 1) - 1) / 7
place(lowpass(bass, 230) * duck * .5, 0)
place(np.stack([lowpass(pad, 1300) * (.4 + .6 * duck)] * 2, 1) * .18, 0)
# pencil scribble while each icon draws, a marimba knock as it lands
for k in range(5):
    t = 2.0 + k * BEAT
    n = int(.32 * SR)
    sc = (noise(n) - lowpass(noise(n), 3000)) * (.6 + .4 * np.sin(np.arange(n) / SR * 2 * np.pi * 23)) * np.sin(np.linspace(0, np.pi, n))
    place(sc * .12, t, pan=.2)
    place(pluck(note([69, 72, 76, 74, 79][k]), .25), t, .22, pan=-.2)
place(boom(), 2.0, .55)
# shelving: a wooden clack as each module lands, drawers slide out
place(boom(1.5), 4.5, .45)
for n_ in range(12):
    t0 = 4.55 + n_ * .125
    place(knock(300 + (n_ * 37) % 220, .05), t0 + .13, .4, pan=((n_ % 4) - 1.5) * .3)
for j in range(4):
    t = 5.75 + j * .125
    place(whoosh(.18) * .6, t, .25)
    place(knock(900, .02), t + .17, .2)
place(whoosh(.3), 6.72, .4)
# rapid cuts
place(boom(1.0), 7.0, .5)
for k in range(8):
    place(blip(note(74 + k * 2)), 7.0 + k * .25, .22, pan=(-1) ** k * .4)
    place(knock(600 + k * 50, .03), 7.0 + k * .25, .25)
place(whoosh(.5, up=True), 8.5, .5)

# ---- 9–15: logo build ----
place(boom(2.5), 9.0, .7)
lp = np.zeros(N)
for m in (45, 52, 57, 60, 64, 69):
    for d in (-.08, .08):
        lp += (2 * ((note(m) * 2 ** (d / 12) * T) % 1) - 1)
lp = lowpass(lp / 12, 600 + 1400 * np.clip((T - 9) / 3, 0, 1)) * np.clip((T - 9.0) / 1.2, 0, 1) * np.clip((15 - T) / 2.5, 0, 1)
place(np.stack([lp, np.roll(lp, 700)], 1) * .2, 0)
place(blip(1760, .05), 9.05, .2)
place(whoosh(.6), 9.25, .4)  # rule draws out
place(bell(note(57), 1.6), 9.6, .35)  # circle blooms
n = int(1.5 * SR)
tt = np.arange(n) / SR
place(np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-tt * 6)) / SR) * np.exp(-tt / .6), 9.6, .45)
for i, m in enumerate((69, 72, 76)):  # L A B
    place(pluck(note(m), .4), 10.1 + i * .12, .2, pan=-.2 + i * .2)
for i, m in enumerate((64, 67, 69, 72, 74, 76, 79, 81, 84)):  # F U R N I T U R E, centre out
    place(pluck(note(m), .3), 10.5 + i * .09, .14, pan=np.sin(i) * .5)
for i, m in enumerate((88, 91, 93, 96, 100)):  # Smart
    place(bell(note(m), .6), 11.25 + i * .1, .05)
# the finish: chord + shimmer under the light sweep
place(boom(2.5), 12.0, .45)
for m in (57, 64, 69, 72, 76, 81):
    place(bell(note(m), 2.2), 12.0, .07)
cym_n = int(3 * SR)
cym = (noise(cym_n) - lowpass(noise(cym_n), 6000)) * env(cym_n, .4, 1.0)
place(cym * .12, 11.6)

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
