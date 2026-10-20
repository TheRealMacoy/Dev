"""Synthesizes the 15s soundtrack, locked to the same 120 BPM grid as the visuals.

Usage: python3 audio.py out.wav
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 15.0
BEAT = 0.5
N = int(SR * DUR)
rng = np.random.default_rng(3)
mix = np.zeros((N, 2))


def place(sig, t, gain=1.0, pan=0.0):
    """Add a mono or stereo signal at time t (seconds)."""
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l, sig * r], axis=1) * np.sqrt(2)
    mix[i : i + len(sig)] += sig * gain


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def lowpass(x, cutoff):
    """One-pole lowpass; cutoff may be a scalar or a per-sample array."""
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


def kick(punch=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 140 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.22)
    click = noise(n) * env(n, 0.0005, 0.004) * 0.5
    return np.tanh((body + click) * 1.6 * punch)


def hat(decay=0.035):
    n = int(0.15 * SR)
    x = noise(n)
    x = x - lowpass(x, 7000)
    return x * env(n, 0.0005, decay)


def clap():
    n = int(0.35 * SR)
    x = noise(n)
    x = x - lowpass(x, 900)
    e = sum(env(n, 0.0005, 0.012) * (np.arange(n) >= int(d * SR)) for d in (0, 0.011, 0.022))
    tail = env(n, 0.0005, 0.12) * (np.arange(n) >= int(0.03 * SR))
    return x * (e + tail * 0.6)


def boom():
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    f = 32 + 90 * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.7)
    crack = lowpass(noise(n), 2500) * env(n, 0.001, 0.25)
    return np.tanh(sub * 1.5 + crack * 1.2)


def riser(length, up=True):
    n = int(length * SR)
    p = np.linspace(0, 1, n)
    curve = p ** 2 if up else (1 - p) ** 2
    x = lowpass(noise(n), 300 + 9000 * curve)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 1400 * curve) / SR) * 0.15
    return (x * 1.6 + tone) * curve


def whoosh(length=0.4):
    n = int(length * SR)
    p = np.linspace(0, 1, n)
    shape = np.sin(np.pi * p) ** 2
    return lowpass(noise(n), 400 + 5000 * shape) * shape * 2.0


def blip(freq, length=0.09):
    n = int(length * SR)
    t = np.arange(n) / SR
    return np.sign(np.sin(2 * np.pi * freq * t)) * env(n, 0.001, 0.03) * 0.5


def pluck(freq, length=0.25):
    n = int(length * SR)
    t = np.arange(n) / SR
    saw = 2 * ((freq * t) % 1) - 1
    return lowpass(saw, 600 + 3500 * np.exp(-t * 25)) * env(n, 0.002, 0.09)


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


# ---- drums ----
for b in range(30):
    t = b * BEAT
    if t in (1.0, 1.25):
        continue
    if t < 1.5:
        # the bouncing dot: soft kicks on its landings
        continue
    place(kick(), t, 0.9)
for t in (0.5, 0.75, 0.9):
    place(kick(0.6), t, 0.55)
for b in range(3, 30):
    t = b * BEAT
    if 1.5 <= t < 13.5:
        place(hat(), t + 0.25, 0.22, pan=0.3)
        if t >= 3.5:
            place(hat(0.015), t + 0.125, 0.1, pan=-0.3)
            place(hat(0.015), t + 0.375, 0.1, pan=-0.3)
        if t >= 3.5 and (b % 2 == 1):
            place(clap(), t, 0.45)

# ---- sub bass + chords: Am F C G, one bar (2s) each ----
prog = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])]
t_all = np.arange(N) / SR
bass = np.zeros(N)
pad = np.zeros(N)
for bar in range(8):
    root, chord = prog[bar % 4]
    s, e = int((1.5 + bar * 2) * SR), int((3.5 + bar * 2) * SR)
    if s >= N:
        break
    e = min(e, int(13.5 * SR))
    seg = t_all[s:e] - t_all[s]
    bass[s:e] += np.tanh(2 * np.sin(2 * np.pi * note(root) * seg))
    for m in chord:
        for det in (-0.12, 0.12):
            ph = note(m) * 2 ** (det / 12) * seg
            pad[s:e] += (2 * (ph % 1) - 1) / 6
# sidechain: duck to the kick
duck = np.ones(N)
for b in range(3, 27):
    i = int(b * BEAT * SR)
    n = int(0.3 * SR)
    duck[i : i + n] = np.minimum(duck[i : i + n], 1 - 0.85 * np.exp(-np.arange(n) / SR / 0.08))
bass = lowpass(bass, 220) * duck
pad = lowpass(pad, 1400) * (0.35 + 0.65 * duck)
place(bass, 0, 0.55)
place(np.stack([pad, np.roll(pad, int(0.012 * SR))], axis=1), 0, 0.28)

# ---- arp through the particle and 3D sections ----
for k in range(int((9.5 - 5.5) / 0.125)):
    t = 5.5 + k * 0.125
    bar = int((t - 1.5) // 2)
    _, chord = prog[bar % 4]
    m = chord[k % 3] + 12 * (1 + (k // 3) % 2)
    place(pluck(note(m)), t, 0.22, pan=0.5 * np.sin(k * 0.9))

# ---- transitions & hits ----
place(riser(1.2), 0.3, 0.25)
for h in (1.5, 3.5, 5.5, 7.5, 9.5, 11.5):
    place(riser(0.9), h - 0.9, 0.3)
    place(boom(), h, 0.55)
for h, length in ((3.05, 0.45), (5.18, 0.32), (13.05, 0.45)):
    place(whoosh(length), h, 0.5)
place(whoosh(0.3), 1.0, 0.35)  # dot stretches to a line
place(whoosh(0.25), 2.5, 0.3, pan=-0.4)  # red wipe
# rapid-fire cuts: a rising blip on each
for k in range(8):
    place(blip(note(76 + k * 2)), 9.5 + k * 0.25, 0.25, pan=(-1) ** k * 0.4)
    place(hat(0.06), 9.5 + k * 0.25, 0.25)
# typing ticks in the intro
for i in range(18):
    place(hat(0.006), 0.15 + i * 0.039, 0.12, pan=0.2)
# end card: big hit, the dot's bounce, a final chord
place(boom(), 13.5, 0.75)
place(kick(1.2), 13.5, 0.9)
for t, g in ((14.05, 0.6), (14.27, 0.3), (14.38, 0.15)):
    place(blip(note(88), 0.06), t, g)
end_n = N - int(13.5 * SR)
seg = np.arange(end_n) / SR
chord_end = sum(np.sin(2 * np.pi * note(m) * seg) for m in (57, 64, 69, 72, 76)) / 5
place(chord_end * np.exp(-seg / 0.9) * np.minimum(1, seg / 0.01), 13.5, 0.35)

# ---- simple stereo reverb-ish delay and master ----
wet = np.zeros_like(mix)
for d, g in ((0.083, 0.3), (0.127, 0.22), (0.191, 0.15), (0.263, 0.1)):
    s = int(d * SR)
    wet[s:, 0] += mix[:-s, 1] * g
    wet[s:, 1] += mix[:-s, 0] * g
out = mix + wet * 0.5
out /= np.max(np.abs(out)) + 1e-9
out = np.tanh(out * 1.1) / np.tanh(1.1) * 0.89
fade = int(0.25 * SR)
out[-fade:] *= np.linspace(1, 0, fade)[:, None]

with wave.open(sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote soundtrack")
