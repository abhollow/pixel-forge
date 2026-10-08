#!/usr/bin/env python3
"""Placeholder music from a small JSON song spec: soft pads, a plucked
arpeggio with echo, a bass on the downbeats, an optional flute-like melody
and hand percussion -- one seamless loop.

    python synth_music.py --list
    python synth_music.py --demo adventure -o audio/music_adventure.ogg
    python synth_music.py --example adventure > audio/songs/adventure.json     # start from a built-in
    python synth_music.py audio/songs/adventure.json -o audio/music_adventure.ogg --peak -12 --rms -25

Why: the game needs music under it while you decide whether it needs
commissioned or generated music at all. For a "retro, but subtle" brief --
the sound effects carry the game, the music sits under them -- four tracks
like these can do that job for a whole build.

Song spec (JSON):

    {
      "bpm": 84,
      "bars_per_chord": 2,                       (4/4 bars)
      "chords": ["Am", "F", "C", "G"],           (symbols, or [root_midi, [tone midis]])
      "arp": [0, 1, 2, 1, 0, 1, 2, 3, null, ...],  (chord-tone index per eighth note; null = rest;
                                                  3 = first tone an octave up; tiled across the chord)
      "melody": [[0, "A4", 1.5], [1.5, "B4", 0.5]],   ([beat from loop start, note, beats])
      "drums": "D.s.d.s.",                       (8 eighths per bar: D drum, d soft, s shaker, . rest;
                                                  or {"pattern": ..., "gain": 0.5})
      "levels": {"pad": 0.06, "arp": 0.05, "bass": 0.22, "melody": 0.09},
      "bass_octave": 36, "seed": 13
    }

Seamless loop: everything rings on past the end into a tail, and the tail is
folded back onto the head. Loudness: --peak caps the peak (dBFS) and --rms
sets the target RMS (dBFS); the gain used is the SMALLER of the two, and the
result reports both (a good starting point: -12 dBFS peak, about -25 dB RMS,
with the Music bus at 50%). --limit soft-clips instead so the RMS target is
met. Writes WAV, or OGG/MP3 (128k) through ffmpeg when -o ends in .ogg/.mp3
(no ffmpeg: a .wav is written instead, with a warning). Ship music
compressed, not as WAV: 2-3 MB WAVs re-committed on every regeneration
bloat git history.
"""
import argparse
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import synth_sfx as sx  # noqa: E402

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
QUALITY = {"": [0, 4, 7], "m": [0, 3, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
           "sus2": [0, 2, 7], "sus4": [0, 5, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10],
           "maj7": [0, 4, 7, 11], "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "add9": [0, 4, 7, 14]}

# Four built-in songs, as specs: menu, calm, adventure, journey.
DEMOS = {
    "menu": {"bpm": 64, "seed": 7, "chords": [[43, [59, 62, 67]], [40, [59, 64, 67]], [48, [60, 64, 67]], [50, [62, 66, 69]],
                                              [43, [59, 62, 67]], [47, [59, 62, 66]], [48, [60, 64, 67]], [50, [62, 66, 69]]],
             "arp": [0, None, 1, 2, None, 1, None, None, 0, None, 2, None, 3, None, 1, None],
             "melody": [[0, 71, 2], [2, 74, 2], [4, 79, 4], [8, 78, 2], [10, 76, 2], [12, 74, 4], [16, 72, 2], [18, 71, 2],
                        [20, 69, 4], [24, 71, 3], [27, 74, 1], [28, 74, 4], [64, 71, 2], [66, 74, 2], [68, 76, 4], [72, 78, 2],
                        [74, 79, 2], [76, 81, 4], [80, 79, 2], [82, 78, 2], [84, 76, 4], [88, 74, 6]],
             "_note": "G major, warm and a touch wistful"},
    "calm": {"bpm": 68, "seed": 3, "chords": [[50, [62, 65, 69]], [48, [60, 64, 67]], [50, [62, 65, 69]], [43, [59, 62, 67]],
                                               [45, [60, 64, 69]], [43, [59, 62, 67]], [41, [60, 65, 69]], [48, [60, 64, 67]]],
              "arp": [0, None, 1, None, 2, None, 1, None, 0, None, None, 2, None, 1, None, None],
              "melody": [[32, 74, 2], [34, 72, 1], [35, 69, 1], [36, 67, 3], [40, 69, 2], [42, 72, 2], [44, 74, 4],
                         [96, 76, 2], [98, 74, 1], [99, 72, 1], [100, 69, 4], [106, 67, 2], [108, 69, 3]],
              "_note": "D dorian, unhurried (mellow level music)"},
    "adventure": {"bpm": 84, "seed": 13, "chords": ["Am", "F", "C", "G", "Am", "F", "G", "E"],
              "arp": [0, 1, 2, 1, 0, 1, 2, 3, 0, 1, 2, 1, 0, None, 2, 1],
              "melody": [[0, 69, 1.5], [1.5, 71, 0.5], [2, 72, 1], [3, 74, 1], [4, 76, 3], [8, 77, 1.5], [9.5, 76, 0.5],
                         [10, 74, 2], [12, 72, 3], [16, 72, 1.5], [17.5, 74, 0.5], [18, 76, 1], [19, 79, 1], [20, 79, 3],
                         [24, 74, 1.5], [25.5, 72, 0.5], [26, 71, 2], [28, 68, 3], [64, 76, 1.5], [65.5, 77, 0.5],
                         [66, 76, 1], [67, 74, 1], [68, 72, 3], [72, 72, 1], [73, 74, 1], [74, 76, 2], [76, 81, 3],
                         [80, 79, 1.5], [81.5, 77, 0.5], [82, 76, 2], [84, 74, 3], [88, 72, 1], [89, 71, 1], [90, 68, 2],
                         [92, 69, 4]],
              "drums": {"pattern": "D.s.d.s.", "gain": 0.5, "seed": 17},
              "_note": "A aeolian into C: a steady walking pulse"},
    "journey": {"bpm": 96, "seed": 19, "chords": [[50, [62, 66, 69]], [48, [60, 64, 67]], [43, [59, 62, 67]],
                                                  [50, [62, 66, 69]], [47, [59, 62, 66]], [48, [60, 64, 67]],
                                                  [43, [59, 62, 67]], [45, [61, 64, 69]]],
                "arp": [0, 2, 1, 2, 0, 2, 1, 3, 0, 2, 1, 2, 3, 2, 1, None],
                "melody": [[0, 74, 1], [1, 76, 0.5], [1.5, 78, 0.5], [2, 81, 2], [4, 79, 1], [5, 78, 1], [6, 76, 2],
                           [8, 72, 1], [9, 74, 0.5], [9.5, 76, 0.5], [10, 79, 2], [12, 78, 4], [16, 74, 1], [17, 76, 0.5],
                           [17.5, 78, 0.5], [18, 81, 1], [19, 83, 1], [20, 81, 3], [24, 79, 1], [25, 78, 1], [26, 76, 2],
                           [28, 73, 1], [29, 76, 1], [30, 74, 2], [64, 83, 1], [65, 81, 1], [66, 79, 2], [68, 78, 1],
                           [69, 76, 1], [70, 74, 2], [72, 72, 1], [73, 76, 1], [74, 79, 2], [76, 78, 4], [80, 79, 1],
                           [81, 81, 1], [82, 83, 2], [84, 81, 2], [86, 79, 2], [88, 76, 1], [89, 78, 1], [90, 74, 6]],
                "drums": {"pattern": "D.ssd.s.", "gain": 0.55, "seed": 23},
                "_note": "D mixolydian, the brightest, still soft"},
}


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12.0)


def note_num(v):
    """69, "A4", "C#5", "Bb3" -> midi number."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(-?\d)\s*", str(v))
    if not m:
        raise SystemExit("bad note %r (use 69 or A4 / C#5 / Bb3)" % v)
    pc = NOTE[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)
    return float(pc + 12 * (int(m.group(3)) + 1))


def chord_tones(sym, bass_octave=36):
    """'Am' -> (root midi for the bass, close voicing between G#3 and G4)."""
    if isinstance(sym, (list, tuple)):
        return int(sym[0]), [int(note_num(t)) for t in sym[1]]
    m = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(.*?)\s*", str(sym))
    if not m or m.group(3) not in QUALITY:
        raise SystemExit("bad chord %r (try Am, F#m7, Bb, Gsus4, Cmaj7)" % sym)
    pc = (NOTE[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)) % 12
    tones = []
    for iv in QUALITY[m.group(3)]:
        p = (pc + iv) % 12
        n = 48 + p
        while n < 56:
            n += 12
        while n > 67:
            n -= 12
        tones.append(n)
    return pc + bass_octave, sorted(tones)


def tri(f, t):
    return 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))


def pulse(f, t, duty=0.25):
    return np.where((f * t) % 1.0 < duty, 1.0, -1.0)


def env(n, attack, release):
    t = np.arange(n) / sx.SR
    dur = n / sx.SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.minimum(1, (dur - t) / max(release, 1e-4))


def echo(x, delay_s, fb, n=4):
    out = x.copy()
    d = int(delay_s * sx.SR)
    g = fb
    for k in range(1, n + 1):
        if k * d >= len(x):
            break
        out[k * d:] += x[:len(x) - k * d] * g
        g *= fb
    return out


def render(spec):
    SR = sx.SR
    rng = np.random.default_rng(spec.get("seed", 1))
    bpm = float(spec["bpm"])
    beat = 60.0 / bpm
    bpc = int(spec.get("bars_per_chord", 2))
    bass_oct = int(spec.get("bass_octave", 36))
    chords = [chord_tones(c, bass_oct) for c in spec["chords"]]
    lv = {"pad": 0.06, "arp": 0.05, "bass": 0.22, "melody": 0.09}
    lv.update(spec.get("levels", {}))
    bars = len(chords) * bpc
    total = bars * 4 * beat
    n = int(total * SR) + SR * 2
    pad, arp, bass, mel = (np.zeros(n) for _ in range(4))
    steps = bpc * 8
    pattern = spec.get("arp") or [0, 1, 2, 1]
    for ci, (root, tones) in enumerate(chords):
        t0 = ci * bpc * 4 * beat
        dur = bpc * 4 * beat
        m = int((dur + 1.5) * SR)
        t = np.arange(m) / SR
        sig = np.zeros(m)
        for tone in tones:                         # detuned triangle pairs, swelling
            f = midi(tone)
            sig += tri(f, t) + 0.6 * tri(f * 1.003, t)
        sx.place(pad, t0, sig * env(m, 1.6, 1.8) * lv["pad"])
        mm = int(beat * 2.5 * SR)
        tt = np.arange(mm) / SR
        for b in range(bpc):                       # bass on each bar's downbeat
            sx.place(bass, t0 + b * 4 * beat,
                     tri(midi(root % 12 + bass_oct), tt) * np.exp(-tt * 1.4) * env(mm, 0.02, 0.3) * lv["bass"])
        mm = int(beat * 0.9 * SR)
        tt = np.arange(mm) / SR
        for step in range(steps):                  # plucked narrow pulse on eighths
            deg = pattern[step % len(pattern)]
            if deg is None:
                continue
            f = midi(tones[deg % len(tones)] + 12 * (deg // len(tones)))
            note = pulse(f, tt, 0.125) * np.exp(-tt * 5.0) * env(mm, 0.005, 0.05)
            sx.place(arp, t0 + step * beat / 2, note * lv["arp"] * (0.8 + 0.4 * rng.random()))
    for b, note, beats in spec.get("melody", []):
        f = midi(note_num(note))
        mm = int(beats * beat * SR)
        tt = np.arange(mm) / SR
        vib = 1 + 0.005 * np.sin(2 * np.pi * 5.0 * tt) * np.minimum(1, tt / 0.4)
        ph = np.cumsum(f * vib) / SR
        tone = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * ph)) + 0.15 * np.sin(4 * np.pi * ph)
        sx.place(mel, b * beat, (tone + rng.standard_normal(mm) * 0.03) * env(mm, 0.08, 0.25) * lv["melody"])
    arp = sx.lowpass(echo(arp, beat * 0.75, 0.45), 2600)
    mel = sx.lowpass(echo(mel, beat * 1.5, 0.3, 3), 3000)
    x = sx.lowpass(pad, 1800) + arp + bass + mel
    drums = spec.get("drums")
    if drums:
        d = drums if isinstance(drums, dict) else {"pattern": drums}
        x[:] += percussion(bpm, bars, d["pattern"], d.get("seed", 11), n) * float(d.get("gain", 0.5))
    head = int(total * SR)                         # fold the tail onto the head: seamless loop
    tail = x[head:]
    x = x[:head].copy()
    x[:len(tail)] += tail
    return x


def percussion(bpm, bars, pattern, seed, n):
    SR = sx.SR
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    x = np.zeros(n)
    nd, ns = int(0.25 * SR), int(0.08 * SR)
    td, ts = np.arange(nd) / SR, np.arange(ns) / SR
    for b in range(bars):
        for k, c in enumerate(pattern):
            at = (b * len(pattern) + k) * beat / 2
            if c in "Dd":
                hit = np.sin(2 * np.pi * (110 - 50 * td / 0.25) * td) * np.exp(-td * 14) + \
                    rng.standard_normal(nd) * np.exp(-td * 70) * 0.15
                sx.place(x, at, hit * (0.22 if c == "D" else 0.12))
            elif c == "s":
                sh = rng.standard_normal(ns)
                sh = sh - sx.lowpass(sh, 4000)
                sx.place(x, at, sh * np.exp(-ts * 40) * 0.05 * (0.8 + 0.4 * rng.random()))
    return x


def db(v):
    return 20 * np.log10(max(v, 1e-12))


def loudness(x, peak_db=-12.0, rms_db=None, limit=False):
    """Gain to hit the RMS target without passing the peak ceiling."""
    peak = np.abs(x).max() + 1e-12
    rms = np.sqrt((x ** 2).mean()) + 1e-12
    g_peak = 10 ** (peak_db / 20) / peak
    if rms_db is None:
        return x * g_peak
    g_rms = 10 ** (rms_db / 20) / rms
    if limit and g_rms > g_peak:
        c = 10 ** (peak_db / 20)
        y = x * g_rms
        return c * np.tanh(y / c)
    return x * min(g_peak, g_rms)


def self_test():
    sx.SR = 22050
    for name, spec in DEMOS.items():
        x = render(dict(spec, chords=spec["chords"][:2], melody=[m for m in spec["melody"] if m[0] < 16]))
        y = loudness(x, -12, -25)
        assert np.isfinite(y).all()
        assert db(np.abs(y).max()) <= -12 + 0.01, name
        assert db(np.sqrt((y ** 2).mean())) <= -25 + 0.01, name
        jump = abs(y[0] - y[-1])
        assert jump < 10 * np.abs(np.diff(y)).mean() + 1e-3, (name, jump)
    assert chord_tones("Am")[1] == [57, 60, 64] and chord_tones("E")[1] == [56, 59, 64], chord_tones("E")
    assert note_num("A4") == 69 and note_num("C#5") == 73 and note_num("Bb3") == 58
    lim = loudness(np.sin(np.linspace(0, 400, 20000)) * np.linspace(0, 1, 20000) ** 4, -12, -14, limit=True)
    assert db(np.abs(lim).max()) <= -12 + 0.01
    print("synth_music self-test OK (%d demos)" % len(DEMOS))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="song spec JSON")
    ap.add_argument("-o", "--output", help="output .wav / .ogg / .mp3")
    ap.add_argument("--demo", help="render a built-in song instead of a spec (see --list)")
    ap.add_argument("--example", help="print a built-in song's spec as JSON, to copy and edit")
    ap.add_argument("--list", action="store_true", help="list built-in songs")
    ap.add_argument("--peak", type=float, default=-12.0, help="peak ceiling, dBFS (default -12)")
    ap.add_argument("--rms", type=float, default=-25.0, help="RMS target, dBFS (default -25; 0 = peak only)")
    ap.add_argument("--limit", action="store_true", help="soft-clip to reach the RMS target under the peak")
    ap.add_argument("--rate", type=int, default=44100, help="sample rate (22050 halves a WAV's size)")
    ap.add_argument("--repeat", type=int, default=1, help="write the loop N times (for listening)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.list:
        for k, v in DEMOS.items():
            print("  %-10s %3d bpm  %s" % (k, v["bpm"], v.get("_note", "")))
        return
    if a.example:
        if a.example not in DEMOS:
            ap.error("unknown song %r; see --list" % a.example)
        print(json.dumps({k: v for k, v in DEMOS[a.example].items() if not k.startswith("_")}, indent=1))
        return
    if a.demo:
        if a.demo not in DEMOS:
            ap.error("unknown song %r; see --list" % a.demo)
        spec = DEMOS[a.demo]
    elif a.spec:
        with open(a.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
    else:
        ap.error("give a spec JSON, --demo NAME, --example NAME or --list")
    if not a.output:
        ap.error("give -o OUTPUT")
    sx.SR = a.rate
    x = render(spec)
    y = loudness(x, a.peak, a.rms or None, a.limit)
    if a.repeat > 1:
        y = np.tile(y, a.repeat)
    written = sx.save(y, a.output, a.rate)
    pk, rms = db(np.abs(y).max()), db(np.sqrt((y ** 2).mean()))
    note = ""
    if a.rms and rms < a.rms - 0.5:
        note = "  (RMS target %.0f not reached: the peak ceiling wins; --limit to squash)" % a.rms
    print("wrote %s  %.1fs loop, peak %.1f dBFS, RMS %.1f dBFS%s" % (written, len(x) / a.rate, pk, rms, note))


if __name__ == "__main__":
    main()
