#!/usr/bin/env python3
"""ffmpeg wrapper for game audio: loudness-normalise, re-encode small, verify.

    python audio_encode.py loudnorm audio/music/*.mp3 -O audio/music_norm          # I=-18, TP=-1.5
    python audio_encode.py reencode audio/music -O audio/music_128 --format ogg     # 128k, 44.1 kHz
    python audio_encode.py reencode audio/wav_src -O audio --format ogg --in-place
    python audio_encode.py probe audio/music
    python audio_encode.py --self-test

Why:
  * music dominates build size -- imported music is often well over half of
    a mobile build, and re-encoding at 128 kbps / 44.1 kHz cuts it by about a
    third with no audible loss on a phone. WAVs of 2-3 MB re-committed on
    every regeneration bloat git history. Ship music as OGG/MP3 at 128k, not
    WAV.
  * tracks from different sources arrive at different loudness; one loudnorm
    pass (I=-18 LUFS, true peak -1.5 dB) lines them up so the Music bus
    slider means the same thing for every track. Leave SFX alone: a quiet
    pickup is deliberate -- trim cues in code instead.
  * loops must be OGG: Godot loops Ogg Vorbis sample-accurately, MP3 cannot
    (MP3 frames add padding at both ends). Encoding a *loop* file to MP3
    prints a warning.

Inputs are files or folders (all audio inside, names kept; --recursive goes
deeper). Every output is checked with ffprobe: its duration must match the
source (within 0.05 s or 1%), and sizes before/after are printed.
loudnorm runs two passes (measure, then apply the measured values) unless
--single-pass.

ffmpeg is found on PATH, in $FFMPEG, or on Windows under
%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\*FFmpeg*\\**\\bin (where winget
puts it without touching PATH for already-open shells).
"""
import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus")
INSTALL_HINT = {"Windows": "winget install Gyan.FFmpeg", "Darwin": "brew install ffmpeg",
                "Linux": "sudo apt install ffmpeg"}


def _find(name):
    env = os.environ.get(name.upper())
    if env and os.path.exists(env):
        return env
    p = shutil.which(name)
    if p:
        return p
    exe = name + (".exe" if os.name == "nt" else "")
    if os.name == "nt":
        roots = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages"),
                 r"C:\ffmpeg", os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "ffmpeg"),
                 os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "apps", "ffmpeg")]
        for root in roots:
            if not os.path.isdir(root):
                continue
            hits = glob.glob(os.path.join(root, "*FFmpeg*", "**", "bin", exe), recursive=True) + \
                glob.glob(os.path.join(root, "**", "bin", exe), recursive=True)
            if hits:
                return sorted(hits)[-1]
    else:
        for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
            if os.path.exists(os.path.join(d, exe)):
                return os.path.join(d, exe)
    return None


def find_ffmpeg():
    return _find("ffmpeg")


def find_ffprobe():
    ff = find_ffmpeg()
    if ff:
        sib = os.path.join(os.path.dirname(ff), "ffprobe" + (".exe" if ff.lower().endswith(".exe") else ""))
        if os.path.exists(sib):
            return sib
    return _find("ffprobe")


def need(tool):
    path = find_ffmpeg() if tool == "ffmpeg" else find_ffprobe()
    if not path:
        raise SystemExit("%s not found. Install it: %s  (then open a new shell, or set $%s)"
                         % (tool, INSTALL_HINT.get(platform.system(), "see ffmpeg.org"), tool.upper()))
    return path


def probe(path):
    """{'duration': s, 'codec': str, 'bitrate': int, 'rate': int, 'channels': int}."""
    r = subprocess.run([need("ffprobe"), "-v", "error", "-show_entries",
                        "format=duration,bit_rate:stream=codec_name,sample_rate,channels",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffprobe failed on %s: %s" % (path, r.stderr.strip()))
    d = json.loads(r.stdout or "{}")
    fmt, st = d.get("format", {}), (d.get("streams") or [{}])[0]
    return {"duration": float(fmt.get("duration", 0) or 0), "codec": st.get("codec_name", "?"),
            "bitrate": int(float(fmt.get("bit_rate", 0) or 0)), "rate": int(st.get("sample_rate", 0) or 0),
            "channels": int(st.get("channels", 0) or 0)}


def collect(inputs, recursive=False):
    out = []
    for item in inputs:
        if os.path.isdir(item):
            pat = os.path.join(item, "**", "*") if recursive else os.path.join(item, "*")
            out += sorted(p for p in glob.glob(pat, recursive=recursive) if p.lower().endswith(AUDIO_EXT))
        elif any(c in item for c in "*?["):
            out += sorted(glob.glob(item))
        else:
            out.append(item)
    return list(dict.fromkeys(out))


def codec_args(fmt, bitrate, rate, channels):
    args = []
    if fmt == "ogg":
        args += ["-c:a", "libvorbis", "-b:a", bitrate]
    elif fmt == "mp3":
        args += ["-c:a", "libmp3lame", "-b:a", bitrate]
    elif fmt == "wav":
        args += ["-c:a", "pcm_s16le"]
    if rate:
        args += ["-ar", str(rate)]
    if channels:
        args += ["-ac", str(channels)]
    return args


def dest_for(src, a, fmt):
    stem = os.path.splitext(os.path.basename(src))[0]
    ext = "." + fmt if fmt != "keep" else os.path.splitext(src)[1]
    if a.in_place:
        return os.path.join(os.path.dirname(src), stem + ext)
    return os.path.join(a.outdir, stem + ext)


def run_ffmpeg(args):
    r = subprocess.run([need("ffmpeg"), "-hide_banner", "-nostdin", "-y"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed: %s" % r.stderr.strip()[-800:])
    return r.stderr


def loudnorm_filter(src, I, TP, LRA, two_pass):
    base = "loudnorm=I=%s:TP=%s:LRA=%s" % (I, TP, LRA)
    if not two_pass:
        return base
    err = run_ffmpeg(["-i", src, "-af", base + ":print_format=json", "-f", "null", "-"])
    j = err[err.rfind("{"):err.rfind("}") + 1]
    try:
        m = json.loads(j)
    except ValueError:
        return base
    return (base + ":measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true"
            % (m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"]))


def process(a, mode):
    files = collect(a.inputs, a.recursive)
    if not files:
        raise SystemExit("no audio files found")
    if not a.in_place and not a.outdir:
        raise SystemExit("give -O OUTDIR (or --in-place)")
    if a.outdir:
        os.makedirs(a.outdir, exist_ok=True)
    tot_in = tot_out = 0
    bad = 0
    for src in files:
        fmt = a.format
        if fmt == "keep":
            fmt_eff = os.path.splitext(src)[1].lstrip(".").lower()
        else:
            fmt_eff = fmt
        dest = dest_for(src, a, fmt)
        if fmt_eff == "mp3" and "loop" in os.path.basename(src).lower():
            print("  WARNING %s: loops should be OGG -- Godot cannot loop MP3 seamlessly" % os.path.basename(src))
        before = probe(src)
        size_in = os.path.getsize(src)
        tmp_dir = tempfile.mkdtemp(prefix="pf_audio_")
        tmp = os.path.join(tmp_dir, "out." + (fmt_eff if fmt_eff in ("ogg", "mp3", "wav", "flac") else "wav"))
        try:
            args = ["-i", src, "-vn", "-map_metadata", "-1"]
            if mode == "loudnorm":
                args += ["-af", loudnorm_filter(src, a.I, a.TP, a.LRA, not a.single_pass)]
                rate = a.rate or before["rate"] or 44100      # loudnorm upsamples to 192k otherwise
            else:
                rate = a.rate
            args += codec_args(fmt_eff, a.bitrate, rate, a.channels)
            run_ffmpeg(args + [tmp])
            after = probe(tmp)
            tol = max(0.05, before["duration"] * 0.01)
            ok = abs(after["duration"] - before["duration"]) <= tol
            if not ok:
                bad += 1
            os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
            shutil.move(tmp, dest)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        size_out = os.path.getsize(dest)
        tot_in += size_in
        tot_out += size_out
        print("  %-32s %7.1f KB -> %7.1f KB  %6.2fs -> %6.2fs  %s %s"
              % (os.path.basename(dest), size_in / 1024, size_out / 1024, before["duration"], after["duration"],
                 after["codec"], "OK" if ok else "DURATION MISMATCH"))
    saved = 100.0 * (1 - tot_out / tot_in) if tot_in else 0
    print("%d file(s): %.2f MB -> %.2f MB (%+.0f%%)" % (len(files), tot_in / 1e6, tot_out / 1e6, -saved))
    if bad:
        raise SystemExit("%d file(s) changed duration -- check them before shipping" % bad)


def self_test():
    if not find_ffmpeg() or not find_ffprobe():
        print("audio_encode self-test SKIPPED: ffmpeg/ffprobe not found (%s)"
              % INSTALL_HINT.get(platform.system(), "see ffmpeg.org"))
        return
    import math
    import struct
    import wave
    d = tempfile.mkdtemp(prefix="pf_audio_test_")
    try:
        src = os.path.join(d, "tone_loop.wav")
        with wave.open(src, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 22050)))
                                   for i in range(22050 * 2)))
        for fmt in ("ogg", "mp3"):
            ns = argparse.Namespace(inputs=[src], recursive=False, outdir=os.path.join(d, fmt), in_place=False,
                                    format=fmt, bitrate="128k", rate=44100, channels=0)
            process(ns, "reencode")
            out = os.path.join(d, fmt, "tone_loop." + fmt)
            p = probe(out)
            assert abs(p["duration"] - 2.0) < 0.06 and p["rate"] == 44100, p
        ns = argparse.Namespace(inputs=[src], recursive=False, outdir=os.path.join(d, "norm"), in_place=False,
                                format="wav", bitrate="128k", rate=0, channels=0, I=-18.0, TP=-1.5, LRA=11.0,
                                single_pass=False)
        process(ns, "loudnorm")
        assert probe(os.path.join(d, "norm", "tone_loop.wav"))["rate"] == 22050
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("audio_encode self-test OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="encode a test tone (skips if ffmpeg is missing)")
    ap.add_argument("--which", action="store_true", help="print where ffmpeg/ffprobe were found")
    sub = ap.add_subparsers(dest="cmd")

    def common(p, default_fmt):
        p.add_argument("inputs", nargs="+", help="files, folders or globs")
        p.add_argument("-O", "--outdir", help="output folder (names kept, extension follows --format)")
        p.add_argument("--in-place", action="store_true", help="write next to the source (same name if same format)")
        p.add_argument("--recursive", action="store_true")
        p.add_argument("--format", choices=["keep", "ogg", "mp3", "wav"], default=default_fmt)
        p.add_argument("--bitrate", default="128k")
        p.add_argument("--rate", type=int, default=44100 if default_fmt != "keep" else 0,
                       help="sample rate (default 44100; 0 = keep)")
        p.add_argument("--channels", type=int, default=0, help="1 = mono, 2 = stereo, 0 = keep")

    ln = sub.add_parser("loudnorm", help="EBU R128 loudness normalise (two-pass)")
    common(ln, "keep")
    ln.add_argument("--I", type=float, default=-18.0, help="integrated loudness target, LUFS (default -18)")
    ln.add_argument("--TP", type=float, default=-1.5, help="true peak ceiling, dBTP (default -1.5)")
    ln.add_argument("--LRA", type=float, default=11.0, help="loudness range target")
    ln.add_argument("--single-pass", action="store_true", help="faster, less exact")
    re_ = sub.add_parser("reencode", help="re-encode to a small shipping format")
    common(re_, "ogg")
    pr = sub.add_parser("probe", help="print duration, codec, bitrate, size")
    pr.add_argument("inputs", nargs="+")
    pr.add_argument("--recursive", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    if a.which:
        print("ffmpeg :", find_ffmpeg() or "NOT FOUND (%s)" % INSTALL_HINT.get(platform.system(), ""))
        print("ffprobe:", find_ffprobe() or "NOT FOUND")
        return
    if a.cmd == "probe":
        for f in collect(a.inputs, a.recursive):
            p = probe(f)
            print("  %-32s %6.2fs  %-9s %4d kbps  %5d Hz  %dch  %7.1f KB"
                  % (os.path.basename(f), p["duration"], p["codec"], p["bitrate"] // 1000, p["rate"],
                     p["channels"], os.path.getsize(f) / 1024))
    elif a.cmd in ("loudnorm", "reencode"):
        process(a, a.cmd)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
