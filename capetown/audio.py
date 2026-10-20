"""Synthesizes the soundtrack, cued to the reel's timeline.

0–13s: space drone, orbital-sunrise swell, lock-on beeps, wind and rumble on the dive
13s+:  impact into a 122 BPM afro-house groove under the drone footage

Usage: python3 audio.py out.wav
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 13.0 + 330 / (30000 / 1001)
N = int(SR * DUR)
T = np.arange(N) / SR
rng = np.random.default_rng(5)
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


def window(t0, t1, fade_in, fade_out):
    return np.clip((T - t0) / fade_in, 0, 1) * np.clip((t1 - T) / fade_out, 0, 1)


# ---------------- space ----------------
# drone: A minor, slowly breathing
drone = np.zeros(N)
for m, g in ((33, 1.0), (40, .6), (45, .5), (52, .25), (57, .18)):
    f = note(m)
    drone += g * (np.sin(2 * np.pi * f * T) + .3 * np.sin(2 * np.pi * f * 1.003 * T + 1))
drone *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * T)) * window(0.0, 13.3, 2.5, 0.6)
place(lowpass(drone, 900) * .16, 0)

# shimmer: high partials twinkling
shim = np.zeros(N)
for k in range(14):
    f = note(81 + [0, 3, 7, 10, 12, 15, 19][k % 7] + 12 * (k // 7))
    trem = np.clip(np.sin(2 * np.pi * (0.2 + rng.random() * .5) * T + rng.random() * 6), 0, 1) ** 3
    shim += np.sin(2 * np.pi * f * T) * trem
shim *= window(0.4, 7.5, 2.0, 1.5)
place(np.stack([shim, np.roll(shim, 900)], 1) * .012, 0)

# space air
air = lowpass(noise(N), 500 + 300 * np.sin(2 * np.pi * .07 * T) ** 2)
place(air * window(0, 7.5, 1.5, 1.5) * .05, 0)

# orbital sunrise: reverse swell into a bright chord bloom
sw_n = int(1.6 * SR)
p = np.linspace(0, 1, sw_n)
swell = lowpass(noise(sw_n), 300 + 8000 * p ** 3) * p ** 3
place(swell * .35, 2.0 - 1.6)
bloom_n = int(5.5 * SR)
bt = np.arange(bloom_n) / SR
bloom = sum(np.sin(2 * np.pi * note(m) * bt) * (1 + .4 * np.sin(2 * np.pi * 5 * bt))
            for m in (57, 64, 69, 72, 76, 81)) / 6
bloom *= np.minimum(1, bt / .05) * np.exp(-bt / 2.2)
place(np.stack([bloom, np.roll(bloom, 700)], 1) * .22, 2.0)
boom_n = int(3 * SR)
bb = np.arange(boom_n) / SR
place(np.sin(2 * np.pi * np.cumsum(30 + 50 * np.exp(-bb * 4)) / SR) * np.exp(-bb / 1.1) * .45, 2.0)


def blip(freq, length=0.07, square=False):
    n = int(length * SR)
    t = np.arange(n) / SR
    w = np.sin(2 * np.pi * freq * t)
    if square:
        w = np.sign(w) * .6
    return w * env(n, .002, length / 3)


# scanning ticks and lock-on
for i in range(16):
    place(blip(2400, .03), 3.3 + i * .1, .08, pan=np.sin(i))
lock_times = []
t, gap = 4.6, .22
while t < 5.65:
    lock_times.append(t)
    t += gap
    gap = max(.05, gap * .8)
for lt in lock_times:
    place(blip(1760, .05, True), lt, .12)
place(blip(1320, .14), 5.7, .25)
place(blip(1980, .3), 5.84, .25)
for i in range(9):  # label typing
    place(blip(3000 + 200 * (i % 3), .015), 5.6 + i * .033, .05)

# ---------------- descent ----------------
dn = int(6.4 * SR)
dp = np.linspace(0, 1, dn)
wind = lowpass(noise(dn), 200 + 5200 * np.sin(np.pi * np.clip(dp * 1.12, 0, 1)) ** 2)
wenv = np.interp(dp, [0, .35, .43, .55, .75, 1], [0, .5, 1, .6, .35, 0])
place(np.stack([wind, np.roll(wind, 1300)], 1) * wenv[:, None] * .5, 6.9)
rumble = lowpass(noise(dn), 90) * np.interp(dp, [0, .4, .7, 1], [0, 1, .8, 0]) * 3
place(rumble * .5, 6.9)
riser_n = int(2.6 * SR)
rp = np.linspace(0, 1, riser_n)
riser = np.sin(2 * np.pi * np.cumsum(110 + 500 * rp ** 2) / SR) * rp ** 2 * .3
place(riser, 7.0)
# accelerating sub heartbeat
t, gap = 7.0, .55
while t < 9.6:
    n = int(.25 * SR)
    tt = np.arange(n) / SR
    place(np.sin(2 * np.pi * np.cumsum(55 + 40 * np.exp(-tt * 30)) / SR) * env(n, .002, .12), t, .45)
    t += gap
    gap = max(.16, gap * .86)
# cloud punch-through whoosh
wn = int(1.2 * SR)
wp = np.linspace(0, 1, wn)
whoosh = lowpass(noise(wn), 500 + 7000 * np.sin(np.pi * wp) ** 2) * np.sin(np.pi * wp) ** 2
place(whoosh * .7, 9.65 - .6, pan=-.2)
# approach: a held chord that builds into the drop
an = int(2.2 * SR)
at = np.arange(an) / SR
appr = sum((2 * ((note(m) * at) % 1) - 1) for m in (45, 52, 57, 60, 64)) / 5
appr = lowpass(appr, 300 + 2500 * (at / at[-1]) ** 2) * (at / at[-1]) ** 1.5
place(np.stack([appr, np.roll(appr, 600)], 1) * .22, 10.8)
rv_n = int(1.0 * SR)
rv = lowpass(noise(rv_n), 2000 + 9000 * np.linspace(0, 1, rv_n) ** 2) * np.linspace(0, 1, rv_n) ** 4
place(rv * .4, 12.0)

# ---------------- landing groove (122 BPM) ----------------
BEAT = 60 / 122
START = 13.0


def kick():
    n = int(.4 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(48 + 110 * np.exp(-t * 30)) / SR) * env(n, .001, .2)
    return np.tanh(body * 1.7)


def shaker(accent=1.0):
    n = int(.07 * SR)
    x = noise(n)
    x = x - lowpass(x, 6000)
    return x * env(n, .004, .018) * accent


def clap():
    n = int(.3 * SR)
    x = noise(n)
    x = x - lowpass(x, 1100)
    e = sum(env(n, .0005, .01) * (np.arange(n) >= int(d * SR)) for d in (0, .01, .021))
    return x * (e + env(n, .0005, .1) * .5 * (np.arange(n) >= int(.028 * SR)))


def conga(freq):
    n = int(.25 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(freq * (1 + .4 * np.exp(-t * 40))) / SR) * env(n, .001, .07)


def marimba(freq):
    n = int(.6 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + .25 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 20)) * env(n, .001, .18)


def boom():
    n = int(2.5 * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(30 + 80 * np.exp(-t * 8)) / SR) * env(n, .002, .8)
    crack = lowpass(noise(n), 3000) * env(n, .001, .2)
    return np.tanh(sub * 1.6 + crack)


place(boom(), START, .75)
progression = [(45, (57, 60, 64, 67)), (41, (53, 57, 60, 64)), (48, (55, 60, 64, 67)), (43, (55, 59, 62, 67))]
beats = int((DUR - START) / BEAT) + 1
duck = np.ones(N)
for b in range(beats):
    t = START + b * BEAT
    if t > DUR - .6:
        break
    place(kick(), t, .85)
    i = int(t * SR)
    n = int(.25 * SR)
    duck[i:i + n] = np.minimum(duck[i:i + n], 1 - .8 * np.exp(-np.arange(min(n, N - i)) / SR / .07))
    if b % 2 == 1:
        place(clap(), t, .35)
    for s in range(4):
        place(shaker(1.0 if s == 2 else .55), t + s * BEAT / 4, .16, pan=.35)
    # syncopated congas
    if b % 4 in (1, 3):
        place(conga(220), t + BEAT * .75, .22, pan=-.4)
    if b % 4 == 2:
        place(conga(330), t + BEAT * .5, .2, pan=-.3)
        place(conga(250), t + BEAT * .75, .18, pan=-.3)
# bass and chords, one bar per chord
bass = np.zeros(N)
pad = np.zeros(N)
bar = 4 * BEAT
for k in range(int((DUR - START) / bar) + 1):
    root, chord = progression[k % 4]
    s0 = START + k * bar
    for step, (off, length) in enumerate(((0, .4), (1.5, .3), (2.5, .3), (3.25, .5))):
        i0 = int((s0 + off * BEAT) * SR)
        n = int(length * BEAT * SR * 1.4)
        if i0 >= N:
            continue
        n = min(n, N - i0)
        tt = np.arange(n) / SR
        f = note(root + (12 if step == 2 else 0))
        bass[i0:i0 + n] += np.tanh(2.2 * np.sin(2 * np.pi * f * tt)) * env(n, .004, .25)
    i0, i1 = int(s0 * SR), min(N, int((s0 + bar) * SR))
    tt = T[i0:i1] - s0
    for m in chord:
        for det in (-.1, .1):
            pad[i0:i1] += (2 * ((note(m) * 2 ** (det / 12) * tt) % 1) - 1) / 8
    # marimba figure
    for j, off in enumerate((0, .75, 1.5, 2, 2.75, 3.5)):
        place(marimba(note(chord[j % 4] + 12)), s0 + off * BEAT, .16, pan=.5 * np.sin(j * 1.3))
bass = lowpass(bass, 260) * duck
pad = lowpass(pad, 1600) * (.35 + .65 * duck) * window(START, DUR, .4, .8)
place(bass, 0, .5)
place(np.stack([pad, np.roll(pad, 500)], 1), 0, .2)
# landmark pops
for t in (14.1, 14.45, 14.75, 15.05, 15.35, 15.65):
    place(blip(1568, .06) + blip(2093, .06) * .5, t, .14, pan=.3)
# title: riser into a hit
tn = int(.6 * SR)
tp = np.linspace(0, 1, tn)
place(lowpass(noise(tn), 800 + 9000 * tp ** 2) * tp ** 3 * .45, 18.95 - .6)
place(boom(), 18.95, .45)
cn = int(3.0 * SR)
ct = np.arange(cn) / SR
cym = (noise(cn) - lowpass(noise(cn), 5000)) * env(cn, .002, 1.1)
place(cym * .18, 18.95, pan=.1)

# ---------------- master ----------------
wet = np.zeros_like(mix)
for d, g in ((.091, .32), (.137, .24), (.211, .16), (.297, .1), (.41, .06)):
    s = int(d * SR)
    wet[s:, 0] += mix[:-s, 1] * g
    wet[s:, 1] += mix[:-s, 0] * g
out = mix + wet * .45
out /= np.max(np.abs(out)) + 1e-9
out = np.tanh(out * 1.15) / np.tanh(1.15) * .89
fi, fo = int(.3 * SR), int(.8 * SR)
out[:fi] *= np.linspace(0, 1, fi)[:, None]
out[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2

with wave.open(sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote soundtrack", round(DUR, 3), "s")
