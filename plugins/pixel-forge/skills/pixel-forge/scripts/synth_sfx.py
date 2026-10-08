#!/usr/bin/env python3
"""Placeholder sound effects and ambience beds, synthesised from noise and
tones -- so every mechanic is audible from day one, before real sounds exist.

    python synth_sfx.py --list
    python synth_sfx.py --preset rain-loop -o audio/rain_loop.ogg
    python synth_sfx.py --preset tone -o audio/tap.wav --freq 660 --seconds 0.12
    python synth_sfx.py --all audio/placeholder --format ogg
    python synth_sfx.py wind-loop -o audio/wind_loop.ogg          # positional form works too
    python synth_sfx.py --self-test

Why synthesise: a placeholder that already SOUNDS like the thing keeps
playtests meaningful and shows WHERE sound belongs before anything is paid
for. Wind is band-passed noise with a moving centre frequency, not hiss;
thunder is a crack plus a roll balanced by measured RMS, not raw brown noise
(a phone speaker cannot play sub-bass). Filenames are the contract: drop a
real recording in under the same name and no code changes. Keep the most
frequent cue plain (a hit that fires dozens of times a level grates if it has
character -- keep it synthetic and short).

One library of weather, ambience, UI, feedback, world and celebration sounds
(--list shows each preset's group). Loops are seamless (the tail is cross-faded into the head, equal-power for
noise beds) -- set the loop flag in code, not in .import (easy to lose).
Loops should ship as OGG (Godot loops Ogg sample-accurately; MP3 cannot).
.ogg/.mp3 output needs ffmpeg (found like audio_encode.py does); without it a
.wav is written instead, with a warning. .wav needs nothing.

Filters are vectorised: scipy.signal.lfilter when scipy is present, an FFT
convolution with the filter's impulse response otherwise.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import wave
from collections import OrderedDict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SR = 44100

_lfilter = None
_lf_checked = False


def _get_lfilter():
    """scipy.signal.lfilter if available (imported lazily, once), else None."""
    global _lfilter, _lf_checked
    if not _lf_checked:
        _lf_checked = True
        if os.environ.get("PIXEL_FORGE_NO_SCIPY", "") in ("", "0"):
            try:
                from scipy.signal import lfilter
                _lfilter = lfilter
            except Exception:
                _lfilter = None
    return _lfilter


# ---------------------------------------------------------------------------
# DSP primitives (vectorised)
# ---------------------------------------------------------------------------

def t_of(seconds):
    return np.arange(int(SR * seconds)) / SR


def norm(x, peak_db):
    return x / (np.abs(x).max() + 1e-12) * (10 ** (peak_db / 20.0))


def _fft_conv(x, ir):
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)
    return y[:len(x)]


def one_pole(x, a, gain):
    """y[n] = a*y[n-1] + gain*x[n] (causal, zero initial state)."""
    x = np.asarray(x, np.float64)
    lf = _get_lfilter()
    if lf is not None:
        return lf([gain], [1.0, -a], x)
    length = int(min(len(x), np.ceil(np.log(1e-7) / np.log(max(a, 1e-9))) + 1)) if a > 0 else 1
    ir = gain * a ** np.arange(max(1, length))
    return _fft_conv(x, ir)


def lowpass(x, hz):
    a = np.exp(-2 * np.pi * hz / SR)
    return one_pole(x, a, 1 - a)


def highpass(x, hz):
    return x - lowpass(x, hz)


def white(n, rng):
    return rng.uniform(-1.0, 1.0, n)


def brown(n, rng, leak=0.995, scale=0.03):
    """Leaky-integrated noise: lots of low-frequency energy (rumble)."""
    return one_pole(white(n, rng), leak, scale)


def moving_bandpass(noise, centre_hz, damping=0.9, frame=2048, hop=512):
    """Band-pass noise whose centre frequency moves per sample (wind).

    Done in the STFT domain: each windowed frame is shaped by a resonant
    band-pass response centred where the curve is at that moment, then
    overlap-added. Equivalent to a per-sample state-variable filter for
    noise input, and vectorised."""
    n = len(noise)
    pad = np.concatenate([np.zeros(frame), noise, np.zeros(frame)])
    win = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(frame) / frame)
    starts = np.arange(0, n + frame, hop)
    idx = starts[:, None] + np.arange(frame)[None, :]
    spec = np.fft.rfft(pad[idx] * win, axis=1)
    freqs = np.fft.rfftfreq(frame, 1.0 / SR)
    centre = np.interp(np.clip(starts + frame // 2 - frame, 0, n - 1), np.arange(n), centre_hz)
    q = 1.0 / max(damping, 1e-3)
    ratio = np.maximum(freqs[None, :], 1.0) / centre[:, None]
    h = 1.0 / np.sqrt(1.0 + q * q * (ratio - 1.0 / ratio) ** 2)
    frames = np.fft.irfft(spec * h, frame, axis=1) * win
    out = np.zeros(len(pad))
    wsum = np.zeros(len(pad))
    for k, s in enumerate(starts):
        out[s:s + frame] += frames[k]
        wsum[s:s + frame] += win * win
    out = out / np.maximum(wsum, 1e-6)
    return out[frame:frame + n]


def loop_seam(x, fade_s=0.5, curve="equal"):
    """Blend the tail into the head so the file loops without a click.
    Returns len(x) - fade samples. 'equal' = equal-power (for noise beds),
    'linear' = a plain linear cross-fade (for tonal material)."""
    f = int(SR * fade_s)
    if f <= 0 or 2 * f >= len(x):
        return x
    r = np.linspace(0, 1, f)
    a, b = (np.sin(r * np.pi / 2), np.cos(r * np.pi / 2)) if curve == "equal" else (r, 1 - r)
    y = x.copy()
    y[:f] = x[:f] * a + x[-f:] * b
    return y[:-f]


def place(buf, start_s, sig):
    i = int(start_s * SR)
    j = min(len(buf), i + len(sig))
    if 0 <= i < len(buf):
        buf[i:j] += sig[:j - i]


# --- chiptune primitives (envelope over the note's fraction) ----------------

def _env(n, attack, release):
    t = np.arange(n) / max(1, n)
    a = np.minimum(1.0, t / attack) if attack > 0 else np.ones(n)
    return a * np.exp(-t / release)


def chip_tone(freq, dur, wave_fn="square", release=0.35, amp=0.5, sweep=None):
    n = int(SR * dur)
    i = np.arange(n)
    f = freq if sweep is None else freq + (sweep - freq) * (i / n)
    phase = (i * f / SR) % 1.0
    if wave_fn == "square":
        v = np.where(phase < 0.5, 1.0, -1.0)
    elif wave_fn == "saw":
        v = 2.0 * phase - 1.0
    else:
        v = np.sin(2 * np.pi * f * i / SR)
    return v * _env(n, 0.005, release) * amp


def chip_noise(dur, release=0.3, amp=0.5, smooth=0.0, rng=None):
    n = int(SR * dur)
    v = white(n, rng)
    if smooth > 0:
        v = one_pole(v, smooth, 1 - smooth)
    return v * _env(n, 0.002, release) * amp


def mix(*layers):
    n = max(len(l) for l in layers)
    out = np.zeros(n)
    for l in layers:
        out[:len(l)] += l
    return out


def seq(*parts):
    return np.concatenate(parts)


def chip_arp(freqs, note_dur, release=0.25, amp=0.45, wave_fn="square"):
    return seq(*[chip_tone(f, note_dur, wave_fn, release, amp) for f in freqs])


# ---------------------------------------------------------------------------
# preset registry
# ---------------------------------------------------------------------------

PRESETS = OrderedDict()


def preset(name, desc, group, loop=False, peak=-6.0, variants=1):
    def reg(fn):
        PRESETS[name] = {"fn": fn, "desc": desc, "group": group, "loop": loop, "peak": peak,
                         "variants": variants}
        return fn
    return reg


# --- wind and tones ---------------------------------------------------------

@preset("wind-loop", "seamless wind bed: band-passed noise, moving centre", "weather", loop=True, peak=-10)
def _wind_loop(rng, seconds=None, **_):
    seconds = seconds or 8.0
    n = int(SR * seconds)
    t = np.arange(n) / SR
    centre = 420 + 160 * np.sin(2 * np.pi * t / seconds) + 70 * np.sin(2 * np.pi * 3 * t / seconds + 1.3)
    x = moving_bandpass(rng.standard_normal(n), centre, 0.9)
    x *= 0.75 + 0.25 * np.sin(2 * np.pi * 2 * t / seconds + 0.4)
    return loop_seam(x, 0.6)


@preset("gust", "a whoosh: pitch rises into the gust and falls away", "weather", peak=-4)
def _gust(rng, seconds=None, **_):
    seconds = seconds or 2.4
    p = np.linspace(0, 1, int(SR * seconds))
    centre = 280 + 720 * np.sin(np.pi * p) ** 1.5
    x = moving_bandpass(rng.standard_normal(len(p)), centre, 0.7)
    return x * np.sin(np.pi * p) ** 1.8


@preset("horn", "ship's horn: two brassy notes a fifth apart", "world", peak=-4.5)
def _horn(rng, seconds=None, **_):
    seconds = seconds or 1.8
    t = t_of(seconds)
    x = np.zeros_like(t)
    for f0, gain in ((98.0, 1.0), (147.0, 0.7)):
        for k in range(1, 9):
            x += gain * np.sin(2 * np.pi * f0 * k * t) / k
    x *= 1.0 + 0.03 * np.sin(2 * np.pi * 5.5 * t)
    return x * np.minimum(1.0, t / 0.12) * np.minimum(1.0, (seconds - t) / 0.45)


@preset("tone", "plain decaying sine (--freq, --seconds): taps, UI", "ui", peak=-6)
def _tone(rng, seconds=None, freq=None, **_):
    t = t_of(seconds or 0.2)
    return np.sin(2 * np.pi * (freq or 220.0) * t) * np.exp(-t * 18.0)


# --- chiptune feedback ------------------------------------------------------

@preset("hit", "noise thud + falling saw: you lost something (keep it plain)", "feedback", peak=-3)
def _hit(rng, **_):
    return mix(chip_noise(0.38, 0.16, 0.55, 0.55, rng), chip_tone(240, 0.38, "saw", 0.22, 0.4, sweep=70))


@preset("blip", "tiny square blip: menu move, tick", "ui", peak=-9)
def _blip(rng, freq=None, **_):
    return chip_tone(freq or 880, 0.06, "square", 0.3, 0.5)


@preset("coin", "two-note square pickup (B5 -> E6)", "feedback", peak=-8)
def _coin(rng, **_):
    return seq(chip_tone(987.77, 0.07, "square", 2.0, 0.45), chip_tone(1318.5, 0.28, "square", 0.35, 0.45))


@preset("purchase-arp", "rising square arpeggio over a low sine: buying gear", "feedback", peak=-4)
def _purchase(rng, **_):
    return mix(chip_arp([392, 523, 659, 784, 1046], 0.08, 0.5, 0.32), chip_tone(196, 0.45, "sine", 0.7, 0.22))


@preset("sparkle-arp", "fast high sine arpeggio: a delivery, a bonus", "feedback", peak=-6)
def _sparkle(rng, **_):
    return chip_arp([1046, 1318, 1568, 2093, 2637], 0.045, 0.22, 0.34, "sine")


@preset("spoil", "soft noise + sagging saw: something went off", "feedback", peak=-8)
def _spoil(rng, **_):
    return mix(chip_noise(0.26, 0.2, 0.3, 0.82, rng), chip_tone(180, 0.26, "saw", 0.25, 0.25, sweep=95))


@preset("complete", "major arpeggio into a held note: level complete", "feedback", peak=-3)
def _complete(rng, **_):
    return mix(seq(chip_arp([523, 659, 784], 0.11, 0.4, 0.34), chip_tone(1046, 0.55, "square", 0.9, 0.4)),
               chip_tone(262, 0.9, "sine", 1.1, 0.22))


# --- storm and crowd ambience -----------------------------------------------

@preset("storm-loop", "storm rain bed: high hiss + body + slow-breathing rumble", "weather", loop=True, peak=-2.9)
def _storm(rng, seconds=None, **_):
    n = int(SR * (seconds or 12.0))
    i = np.arange(n)
    hiss = highpass(white(n, rng), 900.0)
    body = lowpass(white(n, rng), 5200.0)
    rumble = brown(n, rng, 0.9992, 0.02)
    gust = 0.82 + 0.18 * np.sin(2 * np.pi * 0.07 * i / SR + 1.1) + 0.08 * np.sin(2 * np.pi * 0.23 * i / SR)
    return loop_seam((hiss * 0.55 + body * 0.35 + rumble * 2.2) * gust, 1.5)


_THUNDER = [(3.4, 0.55), (4.2, 0.30), (2.6, 0.80)]


@preset("thunder-roll", "crack + long uneven roll, RMS-balanced for phone speakers (3 variants)",
        "weather", peak=-1.4, variants=3)
def _thunder_roll(rng, variant=1, **_):
    dur, crack = _THUNDER[(variant - 1) % 3]
    n = int(SR * dur)
    i = np.arange(n)
    t = i / n
    rumble = lowpass(brown(n, rng, 0.9997, 0.05), 420.0)
    body = lowpass(highpass(white(n, rng), 160.0), 1300.0)
    snap = lowpass(white(n, rng), 3200.0)
    crack_env = np.exp(-t * 34.0) * crack
    roll = np.exp(-t * 2.4) * (0.75 + 0.25 * np.sin(2 * np.pi * 1.7 * i / SR + variant * 13))
    # gains set by measured RMS: brown noise is ~6x hotter than the mid band,
    # and the mid `body` layer is what a phone speaker can actually play
    out = rumble * 2.4 * roll + body * roll * 2.2 + snap * crack_env * 1.5
    fin = int(SR * 0.004)
    out[:fin] *= np.arange(fin) / fin
    return out


@preset("crowd-loop", "muffled crowd babble through a wall (no words)", "ambience", loop=True, peak=-4.4)
def _crowd(rng, seconds=None, **_):
    n = int(SR * (seconds or 14.0))
    i = np.arange(n)
    acc = lowpass(brown(n, rng, 0.9995, 0.03), 180.0) * 0.30
    for k in range(7):
        band = lowpass(highpass(white(n, rng), 180.0 + k * 90.0), 900.0 + k * 260.0)
        rate, phase, wob = 3.0 + rng.random() * 4.0, rng.random() * 6.283, 0.5 + rng.random() * 0.5
        env = 0.45 + 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * rate * i / SR + phase))
        acc += band * env * wob * 0.60
    return loop_seam(lowpass(acc, 1400.0), 1.5)


_YELLS = [(0.75, 190), (0.55, 240), (0.90, 155), (0.62, 275)]


@preset("yell", "a distant shout, low-passed so no words (4 variants)", "ambience", peak=-3.1, variants=4)
def _yell(rng, variant=1, **_):
    dur, base = _YELLS[(variant - 1) % 4]
    n = int(SR * dur)
    i = np.arange(n)
    t = i / n
    breath = lowpass(white(n, rng), 1100.0)
    f = base * (1.0 + 0.30 * np.sin(np.pi * t) - 0.12 * t) * (1.0 + 0.02 * np.sin(2 * np.pi * 5.5 * i / SR))
    ph = 2 * np.pi * f * i / SR
    v = np.sin(ph) * 0.6 + np.sin(ph * 2.0) * 0.25 + np.sin(ph * 3.0) * 0.12
    env = np.minimum(1.0, t / 0.12) * np.exp(-np.maximum(0.0, t - 0.25) * 4.5)
    return lowpass((v * 0.8 + breath * 0.35) * env, 750.0)


# --- nature, work and celebration ------------------------------------------

@preset("rain-loop", "light rain: high-passed patter + individual drops", "weather", loop=True, peak=-12)
def _rain(rng, seconds=None, **_):
    seconds = seconds or 6.0
    n = int(SR * seconds)
    hiss = rng.standard_normal(n)
    hiss = hiss - lowpass(hiss, 900)
    drops = np.zeros(n)
    k = np.arange(400)
    for _ in range(int(seconds * 90)):
        i = rng.integers(0, n - 400)
        drops[i:i + 400] += rng.uniform(0.3, 1.0) * np.exp(-k / 40) * rng.standard_normal(400)
    return loop_seam(0.6 * hiss + drops, 0.5)


@preset("crickets-loop", "two crickets chirping now and then, quiet gaps", "ambience", loop=True, peak=-20)
def _crickets(rng, seconds=None, **_):
    seconds = seconds or 12.0
    x = np.zeros(int(SR * seconds))
    pulse = t_of(0.016)
    env = np.sin(np.pi * pulse / 0.016) ** 2
    for hi, lo, gain in ((4500, 3800, 1.0), (4100, 3450, 0.6)):
        at = rng.uniform(0.2, 1.5)
        while at < seconds - 0.8:
            for k, f in enumerate((hi, hi, hi, lo, lo, lo)):
                place(x, at + k * 0.045 + (0.06 if k >= 3 else 0.0), gain * env * np.sin(2 * np.pi * f * pulse))
            at += rng.uniform(1.6, 3.8)
    return loop_seam(lowpass(x, 7000), 0.3)


@preset("crackle-loop", "campfire: low roar + pops", "ambience", loop=True, peak=-10)
def _crackle(rng, seconds=None, **_):
    seconds = seconds or 5.0
    n = int(SR * seconds)
    roar = lowpass(rng.standard_normal(n), 300) * 0.5
    pops = np.zeros(n)
    k = np.arange(200)
    for _ in range(int(seconds * 40)):
        i = rng.integers(0, n - 200)
        pops[i:i + 200] += rng.uniform(0.2, 1.0) * np.exp(-k / 15) * rng.choice([-1, 1])
    return loop_seam(roar + pops, 0.5)


@preset("thunder", "close thunder: crack + wobbling rumble", "weather", peak=-3)
def _thunder(rng, seconds=None, **_):
    t = t_of(seconds or 3.2)
    crack = rng.standard_normal(len(t)) * np.exp(-t * 18)
    rumble = lowpass(rng.standard_normal(len(t)), 120) * np.exp(-t * 1.2) * 6
    return crack + rumble * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))


@preset("rumble", "low earth rumble swelling and fading (quake)", "weather", peak=-8)
def _rumble(rng, seconds=None, **_):
    seconds = seconds or 2.5
    t = t_of(seconds)
    return lowpass(rng.standard_normal(len(t)), 90) * np.sin(np.pi * t / seconds) ** 1.5


@preset("chime", "rising C-major arpeggio, bell-like", "feedback", peak=-9)
def _chime(rng, seconds=None, **_):
    t = t_of(seconds or 1.4)
    x = np.zeros_like(t)
    for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
        s = t - k * 0.09
        on = s >= 0
        x[on] += np.sin(2 * np.pi * f * s[on]) * np.exp(-s[on] * 4.5)
    return x


@preset("pop", "a soft burst with sparkle", "feedback", peak=-6)
def _pop(rng, seconds=None, **_):
    t = t_of(seconds or 0.5)
    bang = rng.standard_normal(len(t)) * np.exp(-t * 30)
    sparkle = rng.standard_normal(len(t)) * (rng.random(len(t)) > 0.995) * np.exp(-t * 5)
    return lowpass(bang, 2500) + sparkle * 0.6


@preset("howl", "a wolf howl: rising then falling sine with vibrato", "world", peak=-9)
def _howl(rng, seconds=None, **_):
    seconds = seconds or 2.6
    t = t_of(seconds)
    f = 320 + 240 * np.sin(np.pi * np.clip(t / 1.2, 0, 1)) ** 0.7 - 120 * np.clip((t - 1.2) / 1.4, 0, 1)
    f = f * (1 + 0.012 * np.sin(2 * np.pi * 5.5 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.3 * np.sin(2 * ph)
    return x * np.minimum(1, t / 0.3) * np.minimum(1, (seconds - t) / 0.8)


@preset("chirp", "three quick bird tweets", "world", peak=-14)
def _chirp(rng, seconds=None, **_):
    x = np.zeros(int(SR * (seconds or 0.35)))
    for k in range(3):
        s = t_of(0.07)
        f = 3200 + 1800 * s / 0.07 + rng.uniform(-200, 200)
        place(x, k * 0.1, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * s / 0.07))
    return x


@preset("grain", "grain pouring into a store, two-note chime as it settles", "world", peak=-8)
def _grain(rng, seconds=None, **_):
    seconds = seconds or 1.7
    t = t_of(seconds)
    x = np.zeros_like(t)
    density = np.interp(t, [0, 0.3, 1.0, 1.35, seconds], [0, 1, 1, 0.15, 0])
    tick_len = int(SR * 0.006)
    k = np.arange(tick_len)
    for i in np.nonzero(rng.random(len(t)) < density * 0.012)[0]:
        if i + tick_len < len(x):
            x[i:i + tick_len] += rng.uniform(0.3, 1.0) * rng.standard_normal(tick_len) * np.exp(-k / 40)
    x = x - lowpass(x, 1800)
    hiss = lowpass(rng.standard_normal(len(t)), 3000) * density * 0.25
    chime = np.zeros_like(t)
    for f, at in ((659.25, 1.05), (987.77, 1.17)):
        s = t - at
        on = s >= 0
        chime[on] += np.sin(2 * np.pi * f * s[on]) * np.exp(-s[on] * 5.0) * 0.5
    return x + hiss + chime


@preset("logs", "logs landing on a pile: hollow knocks, warm chime", "world", peak=-8)
def _logs(rng, seconds=None, **_):
    t = t_of(seconds or 1.4)
    x = np.zeros_like(t)
    for k in range(7):
        s = t - (0.12 + k * 0.11 + rng.uniform(-0.03, 0.03))
        on = s >= 0
        f = rng.uniform(170, 260)
        x[on] += (np.sin(2 * np.pi * f * s[on]) + 0.5 * np.sin(2 * np.pi * f * 2.3 * s[on])) * np.exp(-s[on] * 30) * (1 - k * 0.08)
    for f, at in ((392.0, 0.95), (587.33, 1.06)):
        s = t - at
        on = s >= 0
        x[on] += np.sin(2 * np.pi * f * s[on]) * np.exp(-s[on] * 5.0) * 0.4
    return x


@preset("stones", "stones landing: bright clacks, gravel rattle, chime", "world", peak=-8)
def _stones(rng, seconds=None, **_):
    seconds = seconds or 1.4
    t = t_of(seconds)
    x = np.zeros_like(t)
    L = int(SR * 0.03)
    s = np.arange(L) / SR
    for k in range(14):
        i = int(SR * (0.1 + k * 0.055 + rng.uniform(-0.02, 0.02)))
        if i + L < len(t):
            f = rng.uniform(1400, 2600)
            x[i:i + L] += (np.sin(2 * np.pi * f * s) * 0.6 + rng.standard_normal(L) * 0.5) * np.exp(-s * 160) * (1 - k * 0.04)
    rattle = rng.standard_normal(len(t)) * np.interp(t, [0, 0.15, 0.8, 1.0, seconds], [0, 0.25, 0.2, 0, 0])
    x += rattle - lowpass(rattle, 1500)
    for f, at in ((523.25, 0.95), (783.99, 1.06)):
        ss = t - at
        on = ss >= 0
        x[on] += np.sin(2 * np.pi * f * ss[on]) * np.exp(-ss[on] * 5.0) * 0.4
    return x


@preset("tick", "a light two-partial tick", "ui", peak=-10)
def _tick(rng, seconds=None, **_):
    t = t_of(seconds or 0.25)
    return sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 25) for f in (880, 1320))


@preset("chop", "axe into wood: hard knock, hollow body", "world", peak=-8)
def _chop(rng, seconds=None, **_):
    t = t_of(seconds or 0.3)
    knock = lowpass(rng.standard_normal(len(t)), 3000) * np.exp(-t * 60)
    body = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((190, 28), (410, 40), (760, 55)))
    return knock + 0.5 * body


@preset("hammer", "mallet on a peg: brighter and shorter than chop", "world", peak=-9)
def _hammer(rng, seconds=None, **_):
    t = t_of(seconds or 0.22)
    knock = lowpass(rng.standard_normal(len(t)), 5000) * np.exp(-t * 90)
    body = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 45) for f in (520, 1170))
    return knock + 0.4 * body


@preset("flutter", "wings taking off: noise bursts at a falling wingbeat", "world", peak=-12)
def _flutter(rng, seconds=None, **_):
    seconds = seconds or 0.7
    t = t_of(seconds)
    rate = 22 - 10 * t / seconds
    beat = np.maximum(0, np.sin(2 * np.pi * np.cumsum(rate) / SR)) ** 3
    x = rng.standard_normal(len(t))
    return (x - lowpass(x, 700)) * beat * np.exp(-t * 2.5)


@preset("festival-loop", "festival: pentatonic flute over frame drum and drone, 16 beats", "ambience", loop=True, peak=-9)
def _festival(rng, **_):
    beat = 60.0 / 112.0
    n_beats = 16
    seconds = beat * n_beats
    n_loop = int(seconds * SR)
    x = np.zeros(n_loop + SR)            # a tail, folded onto the head below
    nd = int(0.22 * SR)
    tt = np.arange(nd) / SR
    for b in range(n_beats * 2):
        hit = (1.0 if b % 2 == 0 else 0.45) * (1.0 if b % 8 != 6 else 0.7)
        body = np.sin(2 * np.pi * (95 - 40 * tt / 0.22) * tt) * np.exp(-tt * 18)
        skin = rng.standard_normal(nd) * np.exp(-tt * 60) * 0.3
        place(x, b * beat / 2, (body + skin) * hit * 0.5)
    scale = [587.33, 659.25, 739.99, 880.0, 987.77, 1174.66]
    tune = [0, 2, 3, 2, 4, 3, 2, 0, 1, 2, 3, 5, 4, 3, 2, 1, 0, 2, 3, 4, 5, 4, 3, 2, 3, 2, 1, 2, 0, 1, 0, 0]
    half = beat / 2
    for i, deg in enumerate(tune):
        dur = half * (2 if i % 8 == 7 else 1)
        n = int(dur * SR)
        tn = np.arange(n) / SR
        f = scale[deg] * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * tn))
        env = np.minimum(1, tn / 0.03) * np.exp(-tn * 1.5) * np.minimum(1, (dur - tn) / 0.04)
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.2 * np.sin(4 * np.pi * np.cumsum(f) / SR)
        place(x, i * half, (tone + rng.standard_normal(n) * 0.05) * env * 0.32)
    # seamless: notes ringing past the end continue at the start, and the
    # drone gets a whole number of cycles per loop (otherwise it clicks)
    out = x[:n_loop].copy()
    out[:len(x) - n_loop] += x[n_loop:]
    t = np.arange(n_loop) / SR
    root = round(146.83 * n_loop / SR) * SR / n_loop
    fifth = round(146.83 * 1.5 * n_loop / SR) * SR / n_loop
    out += 0.10 * (np.sin(2 * np.pi * root * t) + 0.6 * np.sin(2 * np.pi * fifth * t)) * \
        (0.8 + 0.2 * np.sin(2 * np.pi * t * SR / n_loop))
    return out


@preset("splash", "water poured from a bucket", "world", peak=-14)
def _splash(rng, seconds=None, **_):
    t = t_of(seconds or 0.5)
    x = rng.standard_normal(len(t))
    return (lowpass(x, 1800) - lowpass(x, 300)) * np.minimum(1, t / 0.05) * np.exp(-t * 6)


@preset("fanfare", "festive brass pickup into a held chord, drum roll, bells", "event", peak=-6)
def _fanfare(rng, **_):
    t = t_of(2.6)
    x = np.zeros_like(t)

    def brass(f, at, dur, amp):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        saw = 2 * ((f * tt) % 1.0) - 1 + 0.5 * (2 * ((2 * f * tt) % 1.0) - 1)
        env = np.minimum(1, tt / 0.03) * np.minimum(1, (dur - tt) / 0.12)
        place(x, at, lowpass(saw, 2200) * env * amp)

    for f, at in [(392.0, 0.0), (523.25, 0.13), (659.25, 0.26)]:
        brass(f, at, 0.14, 0.5)
    for f in (523.25, 659.25, 783.99, 1046.5):
        brass(f, 0.4, 1.9, 0.32)
    roll = rng.standard_normal(len(t)) * (np.sin(2 * np.pi * 28 * t) > 0.2)
    x += lowpass(roll, 2500) * np.where(t < 0.4, t / 0.4, np.exp(-(t - 0.4) * 2.5)) * 0.25
    x += np.sin(2 * np.pi * (90 - 40 * np.minimum(1, (t - 0.4) / 0.3)) * t) * np.exp(-np.maximum(0, t - 0.4) * 9) * (t >= 0.4) * 0.6
    nb = int(0.9 * SR)
    tt = np.arange(nb) / SR
    for k, f in enumerate([1567.98, 2093.0, 1760.0, 2349.3, 1975.5, 2637.0, 2093.0]):
        bell = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.76 * tt)) * np.exp(-tt * 5)
        place(x, 0.42 + k * 0.17 + rng.random() * 0.05, bell * 0.12)
    return x


@preset("whistle", "a rocket going up: thin rising whistle and sparks", "event", peak=-14)
def _whistle(rng, seconds=None, **_):
    seconds = seconds or 0.6
    t = t_of(seconds)
    f = 900 + 1700 * (t / seconds) ** 1.5
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35
    hiss = (rng.standard_normal(len(t)) - lowpass(rng.standard_normal(len(t)), 2000)) * 0.25
    return (tone + hiss) * np.minimum(1, t / 0.05) * np.minimum(1, (seconds - t) / 0.08)


@preset("bang", "a firework burst: thump, crack, thinning crackle", "event", peak=-6)
def _bang(rng, seconds=None, **_):
    seconds = seconds or 1.6
    t = t_of(seconds)
    thump = np.sin(2 * np.pi * (70 - 30 * np.minimum(1, t / 0.4)) * t) * np.exp(-t * 6) * 0.9
    crack = rng.standard_normal(len(t)) * np.exp(-t * 30) * 0.8
    crackle = np.zeros_like(t)
    n6 = int(0.006 * SR)
    for _ in range(70):
        at = 0.08 + rng.random() ** 1.6 * (seconds - 0.2)
        place(crackle, at, rng.standard_normal(n6) * (1.0 - at / seconds) * 0.5)
    return thump + lowpass(crack, 3000) + crackle


# ---------------------------------------------------------------------------
# render / save
# ---------------------------------------------------------------------------

def render(name, seconds=None, freq=None, seed=None, variant=1, peak=None):
    p = PRESETS[name]
    rng = np.random.default_rng(seed if seed is not None else (sum(map(ord, name)) * 7 + variant))
    x = np.asarray(p["fn"](rng, seconds=seconds, freq=freq, variant=variant), np.float64)
    return norm(x, p["peak"] if peak is None else peak)


def write_wav(path, x, rate=None):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate or SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def save(x, path, rate=None):
    """.wav directly; .ogg / .mp3 through ffmpeg (128k). Without ffmpeg an
    .ogg/.mp3 request writes <name>.wav instead and says so. Returns the path
    actually written."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        write_wav(path, x, rate)
        return path
    from audio_encode import find_ffmpeg, INSTALL_HINT
    import platform
    ff = find_ffmpeg()
    if not ff:
        alt = os.path.splitext(path)[0] + ".wav"
        write_wav(alt, x, rate)
        print("WARNING: %s needs ffmpeg (%s); wrote %s instead -- encode it later with audio_encode.py"
              % (ext, INSTALL_HINT.get(platform.system(), "see ffmpeg.org"), alt))
        return alt
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        write_wav(tmp, x, rate)
        codec = ["-c:a", "libvorbis", "-b:a", "128k"] if ext == ".ogg" else ["-c:a", "libmp3lame", "-b:a", "128k"]
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", tmp] + codec + [path], check=True)
    finally:
        os.remove(tmp)
    return path


def self_test():
    global _lfilter
    rng = np.random.default_rng(1)
    x = rng.standard_normal(20000)
    if _get_lfilter() is not None:
        ref = lowpass(x, 300)
        keep, _lfilter = _lfilter, None
        try:
            alt = lowpass(x, 300)
        finally:
            _lfilter = keep
        assert np.abs(ref - alt).max() < 1e-4, "FFT fallback differs from lfilter"
    count = 0
    for name, p in PRESETS.items():
        for v in range(1, p["variants"] + 1):
            y = render(name, variant=v)
            assert np.isfinite(y).all() and len(y) > SR * 0.03, name
            pk = 20 * np.log10(np.abs(y).max())
            assert abs(pk - p["peak"]) < 0.05, (name, pk)
            rms = 20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-12)
            assert rms > -60, (name, rms)
            if p["loop"]:
                jump = abs(y[0] - y[-1])
                typical = np.abs(np.diff(y)).mean()
                assert jump < 8 * typical + 1e-3, (name, jump, typical)
            count += 1
    print("synth_sfx self-test OK (%d sounds, %d presets; filters: %s)"
          % (count, len(PRESETS), "scipy lfilter + FFT fallback checked" if _lfilter is not None else "FFT fallback"))


def main():
    global SR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", nargs="?", help="preset name (same as --preset)")
    ap.add_argument("--preset", help="preset name (see --list)")
    ap.add_argument("-o", "--output", help="output .wav / .ogg / .mp3")
    ap.add_argument("--list", action="store_true", help="list the presets")
    ap.add_argument("--all", metavar="OUTDIR", help="render every preset into OUTDIR (variants as name_1..)")
    ap.add_argument("--format", choices=["wav", "ogg", "mp3"], default="wav", help="for --all (default wav)")
    ap.add_argument("--seconds", type=float, default=None, help="length, for presets that take one")
    ap.add_argument("--freq", type=float, default=None, help="pitch, for tone / blip")
    ap.add_argument("--seed", type=int, default=None, help="random seed (another take of the same sound)")
    ap.add_argument("--variant", type=int, default=1, help="for presets with variants (thunder-roll, yell)")
    ap.add_argument("--peak", type=float, default=None, help="override the preset's peak, dBFS")
    ap.add_argument("--rate", type=int, default=44100, help="sample rate (default 44100)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    SR = a.rate
    if a.self_test:
        self_test()
        return
    if a.list:
        for name, p in PRESETS.items():
            print("  %-14s %-5s %-9s %s" % (name, "loop" if p["loop"] else "", p["group"], p["desc"]))
        return
    if a.all:
        os.makedirs(a.all, exist_ok=True)
        for name, p in PRESETS.items():
            for v in range(1, p["variants"] + 1):
                fname = name.replace("-", "_") + ("" if p["variants"] == 1 else "_%d" % v) + "." + a.format
                x = render(name, None, None, a.seed, v)
                save(x, os.path.join(a.all, fname), a.rate)
                print("  %-22s %5.2fs" % (fname, len(x) / SR))
        print("wrote %d presets to %s" % (len(PRESETS), a.all))
        return
    name = a.preset or a.kind
    if not name:
        ap.error("give --preset NAME (or --list, --all DIR, --self-test)")
    if name not in PRESETS:
        ap.error("unknown preset %r; see --list" % name)
    if not a.output:
        ap.error("give -o OUTPUT")
    x = render(name, a.seconds, a.freq, a.seed, a.variant, a.peak)
    out = save(x, a.output, a.rate)
    print(f"wrote {out}  ({len(x) / SR:.2f}s, {name}{' loop' if PRESETS[name]['loop'] else ''})")


if __name__ == "__main__":
    main()
