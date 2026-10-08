#!/usr/bin/env python3
"""Tests for the Pixel Forge Python tools (plugins/pixel-forge/skills/pixel-forge/scripts).

    python -I tests/run_tests.py            # everything
    python -I tests/run_tests.py -k slice   # tests whose name contains "slice"
    python -I tests/run_tests.py --keep     # keep the temp folder for a look

No pytest: plain Python, so it runs anywhere the scripts run (Pillow + numpy;
scipy optional -- the cutters are also run with PIXEL_FORGE_NO_SCIPY=1 to
exercise the numpy fallback). It builds synthetic images (a magenta sheet with
three sprites whose rows overlap, a drop shadow, an enclosed key pocket, a
speck and a purple spill band; a pink subject on green; a tinted sprite),
runs every script's main paths through subprocess with this interpreter,
asserts on the outputs (counts, sizes, no key colour left, palette
membership), runs every --self-test, and checks that every script's --help
works. Things that need ffmpeg or git are skipped (and say so) when absent.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import wave
import zipfile

import numpy as np
from PIL import Image, ImageDraw

sys.dont_write_bytecode = True      # never leave __pycache__ in the skill folder
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "pixel-forge", "skills", "pixel-forge", "scripts")
PY = [sys.executable, "-I", "-B"]
TMP = None
TESTS = []
SKIPS = []


def test(fn):
    TESTS.append(fn)
    return fn


class Skip(Exception):
    pass


def run(script, *args, expect=0, env=None, cwd=None, timeout=300, stdin=None):
    cmd = PY + [os.path.join(SCRIPTS, script)] + [str(a) for a in args]
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or TMP, env=e, timeout=timeout, input=stdin)
    if expect is not None and r.returncode != expect:
        raise AssertionError("%s %s -> exit %d (wanted %d)\n--- stdout\n%s\n--- stderr\n%s"
                             % (script, " ".join(str(a) for a in args), r.returncode, expect,
                                r.stdout[-1500:], r.stderr[-2500:]))
    return r


def p(*parts):
    path = os.path.join(TMP, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def rgba(path):
    return np.array(Image.open(path).convert("RGBA"))


def opaque(arr):
    return arr[arr[..., 3] > 0][:, :3].astype(int)


def magenta_left(arr):
    px = opaque(arr)
    if not len(px):
        return 0
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    return int(((r > 90) & (b > 90) & (g < 0.62 * r) & (g < 0.62 * b)).sum()
               + ((r > g + 40) & (b > g + 40)).sum())


def green_left(arr):
    px = opaque(arr)
    if not len(px):
        return 0
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    return int(((g > r + 40) & (g > b + 40)).sum())


def ffmpeg_path():
    sys.path.insert(0, SCRIPTS)
    try:
        from audio_encode import find_ffmpeg, find_ffprobe
        return find_ffmpeg() if find_ffprobe() else None
    finally:
        sys.path.remove(SCRIPTS)


# ---------------------------------------------------------------------------
# synthetic images
# ---------------------------------------------------------------------------

KEY = (252, 52, 252)      # off-key magenta, as generated sheets often measure


def make_overlap_sheet(path):
    """Three sprites; C's rows overlap A's (profile mode merges B and C);
    a darker-magenta drop shadow, a pure-key pocket enclosed in A, a speck,
    and a purple spill band on B."""
    im = Image.new("RGB", (640, 420), KEY)
    d = ImageDraw.Draw(im)
    d.ellipse([140, 200, 205, 236], fill=(150, 30, 150))          # drop shadow (darker magenta)
    d.rectangle([40, 40, 160, 220], fill=(20, 20, 20))             # A outline
    d.rectangle([46, 46, 154, 214], fill=(150, 110, 70))           # A fill
    d.rectangle([80, 100, 100, 120], fill=KEY)                     # pocket of key inside A
    d.rectangle([260, 60, 380, 170], fill=(20, 20, 20))            # B
    d.rectangle([266, 66, 374, 164], fill=(90, 120, 60))
    d.rectangle([266, 66, 374, 74], fill=(110, 60, 110))           # purple spill band
    d.rectangle([220, 200, 330, 350], fill=(20, 20, 20))           # C (overlaps A's rows, B's columns)
    d.rectangle([226, 206, 324, 344], fill=(60, 80, 140))
    d.rectangle([560, 395, 561, 396], fill=(30, 30, 30))           # speck
    im.save(path)
    return path


def make_grid_sheet(path):
    """Three sprites in two clean rows (profile mode territory)."""
    im = Image.new("RGB", (400, 300), (255, 0, 255))
    d = ImageDraw.Draw(im)
    for x0, y0, c in ((30, 20, (200, 60, 40)), (230, 30, (40, 160, 60)), (120, 170, (40, 60, 200))):
        d.rectangle([x0, y0, x0 + 90, y0 + 100], fill=(10, 10, 10))
        d.rectangle([x0 + 5, y0 + 5, x0 + 85, y0 + 95], fill=c)
    im.save(path)
    return path


def make_pink_on_green(path):
    im = Image.new("RGB", (300, 240), (0, 255, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([60, 40, 240, 200], fill=(25, 20, 25))
    d.ellipse([66, 46, 234, 194], fill=(255, 105, 180))
    d.ellipse([66, 46, 234, 60], fill=(150, 200, 140))             # green spill on the rim
    im.save(path)
    return path


def make_walk_strip(path, frames=4):
    """Animation strip: same body, legs of different length -> shared box."""
    im = Image.new("RGB", (frames * 120, 160), (255, 0, 255))
    d = ImageDraw.Draw(im)
    for i in range(frames):
        x = i * 120 + 30
        d.rectangle([x, 20, x + 50, 90], fill=(15, 15, 15))
        d.rectangle([x + 4, 24, x + 46, 86], fill=(220, 130, 50))  # orange body
        leg = 30 + (i % 2) * 20
        d.rectangle([x + 8, 90, x + 16, 90 + leg], fill=(15, 15, 15))
        d.rectangle([x + 34, 90, x + 42, 90 + (50 - leg) + 30], fill=(15, 15, 15))
        if i == 2:
            d.rectangle([x + 55, 100, x + 85, 140], fill=(200, 180, 120))   # dust kicked up
    im.save(path)
    return path


def make_sprite(path, size=(24, 24), body=(200, 120, 60)):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w, h = size
    d.rectangle([w // 3, 2, 2 * w // 3, int(h * 0.6)], fill=body + (255,))
    d.rectangle([w // 3, int(h * 0.6) + 1, w // 3 + 2, h - 1], fill=(40, 40, 90, 255))
    d.rectangle([2 * w // 3 - 2, int(h * 0.6) + 1, 2 * w // 3, h - 1], fill=(40, 40, 90, 255))
    d.rectangle([2 * w // 3 + 1, h // 3, min(w - 1, 2 * w // 3 + 5), h // 3 + 2], fill=(90, 60, 30, 255))
    im.save(path)
    return path


def write_palette(path, cols):
    with open(path, "w") as fh:
        fh.write("\n".join(cols) + "\n")
    return path


# ---------------------------------------------------------------------------
# tests: self-tests and --help
# ---------------------------------------------------------------------------

@test
def help_for_every_script():
    bad = []
    for f in sorted(glob.glob(os.path.join(SCRIPTS, "*.py"))):
        r = run(os.path.basename(f), "--help", expect=None)
        if r.returncode != 0 or "usage" not in r.stdout.lower():
            bad.append("%s (exit %d) %s" % (os.path.basename(f), r.returncode, r.stderr.strip()[-200:]))
    assert not bad, "--help failed for: " + "; ".join(bad)


@test
def self_tests():
    for script in ("forge_ndimage.py", "forge_image.py", "despill.py", "recolor.py", "synth_sfx.py",
                   "synth_music.py", "audio_encode.py"):
        r = run(script, "--self-test")
        assert "OK" in r.stdout or "SKIPPED" in r.stdout, (script, r.stdout)
        if "SKIPPED" in r.stdout:
            SKIPS.append("%s --self-test: %s" % (script, r.stdout.strip()))
    for script in ("forge_ndimage.py", "forge_image.py", "synth_sfx.py"):
        run(script, "--self-test", env={"PIXEL_FORGE_NO_SCIPY": "1"})


# ---------------------------------------------------------------------------
# cutting
# ---------------------------------------------------------------------------

@test
def slice_blob_overlapping_rows():
    sheet = make_overlap_sheet(p("raw", "overlap.png"))
    sizes = "40x60,40x40,36x48"
    r = run("slice_sheet.py", sheet, "--mode", "blob", "--prefix", "ov", "--sizes", sizes, "--despill",
            "--out-dir", os.path.join(TMP, "cut"), "--debug-sheet", p("cut", "dbg_overlap.png"), "--report", p("cut", "ov.json"))
    assert "Found 3 sprites" in r.stdout and "ignored 1 speck" in r.stdout and "enclosed" in r.stdout, r.stdout
    rep = json.load(open(p("cut", "ov.json")))
    assert len(rep["sprites"]) == 3
    want = [(40, 60), (40, 40), (36, 48)]
    for i, (w, h) in enumerate(want):
        a = rgba(p("cut", "ov_%02d.png" % i))
        assert a.shape[:2] == (h, w), (i, a.shape)
        assert magenta_left(a) == 0, ("magenta left in", i, magenta_left(a))
        assert set(np.unique(a[..., 3])) <= {0, 255}, "alpha not hard"
    # reading order A (brown), B (green), C (blue)
    means = [opaque(rgba(p("cut", "ov_%02d.png" % i))).mean(0) for i in range(3)]
    assert means[0][0] > means[0][2] and means[1][1] > means[1][2] and means[2][2] > means[2][0], means
    # the enclosed pocket in A is transparent, not magenta
    a = rgba(p("cut", "ov_00.png"))
    assert (a[..., 3] == 0).sum() > 0
    assert os.path.exists(p("cut", "dbg_overlap.png"))


@test
def slice_blob_numpy_fallback_matches():
    sheet = make_overlap_sheet(p("raw", "overlap.png"))
    run("slice_sheet.py", sheet, "--mode", "blob", "--prefix", "s", "--sizes", "40x60,40x40,36x48",
        "--out-dir", p("cut", "sp"))
    run("slice_sheet.py", sheet, "--mode", "blob", "--prefix", "n", "--sizes", "40x60,40x40,36x48",
        "--out-dir", p("cut", "np"), env={"PIXEL_FORGE_NO_SCIPY": "1"})
    for i in range(3):
        a, b = rgba(p("cut", "sp", "s_%02d.png" % i)), rgba(p("cut", "np", "n_%02d.png" % i))
        assert (a == b).all(), "numpy fallback differs on sprite %d" % i


@test
def slice_profile_merges_overlap_and_count_asserts():
    sheet = make_overlap_sheet(p("raw", "overlap.png"))
    r = run("slice_sheet.py", sheet, "--prefix", "pm", "--sizes", "40x60,40x40,36x48",
            "--out-dir", p("cut", "pm"), expect=None)
    assert r.returncode != 0 and "found 2 sprites, 3 expected" in (r.stdout + r.stderr), r.stderr[-400:]
    assert "--mode blob" in r.stderr


@test
def slice_profile_rows():
    sheet = make_grid_sheet(p("raw", "grid.png"))
    r = run("slice_sheet.py", "--src", sheet, "--prefix", "g", "--sizes", "20x20", "--rows", "2",
            "--out-dir", p("cut", "g"), "--clean-fringe", "--palette",
            write_palette(p("pal", "g.hex"), ["0a0a0a", "c83c28", "28a03c", "283cc8", "ffffff"]))
    assert "Found 3 sprites" in r.stdout, r.stdout
    pal = [(10, 10, 10), (200, 60, 40), (40, 160, 60), (40, 60, 200), (255, 255, 255)]
    for i in range(3):
        a = rgba(p("cut", "g", "g_%02d.png" % i))
        assert a.shape[:2] == (20, 20)
        assert magenta_left(a) == 0
        assert {tuple(c) for c in opaque(a)} <= set(pal), "off-palette colours"


@test
def slice_green_key_pink_subject():
    src = make_pink_on_green(p("raw", "pink.png"))
    for key in ("green", "auto"):
        r = run("slice_sheet.py", src, "--key", key, "--prefix", "pk_" + key, "--sizes", "30x30", "--despill",
                "--out-dir", p("cut", "pink"))
        assert "key green" in r.stdout, r.stdout
        a = rgba(p("cut", "pink", "pk_%s_00.png" % key))
        px = opaque(a)
        pink = ((px[:, 0] > 200) & (px[:, 1] < 150) & (px[:, 2] > 140)).sum()
        assert pink > 100, "the pink subject was eaten (%d pink px)" % pink
        assert green_left(a) == 0, "green left: %d" % green_left(a)


@test
def slice_shared_box_and_scale_by_colour():
    strip = make_walk_strip(p("raw", "walk.png"))
    run("slice_sheet.py", strip, "--prefix", "wk", "--sizes", "24x32", "--shared-box", "--anchor", "top",
        "--out-dir", p("cut", "walk"), "--clean-fringe")
    frames = [rgba(f) for f in sorted(glob.glob(p("cut", "walk", "wk_*.png")))]
    assert len(frames) == 4 and len({f.shape for f in frames}) == 1
    r = run("slice_sheet.py", strip, "--prefix", "sc", "--sizes", "40x60",
            "--scale-by", "colour:dc8232:30", "--feature-px", "20", "--out-dir", p("cut", "scale", "x"))
    assert "Found 4 sprites" in r.stdout and "overflows" not in r.stdout, r.stdout
    for f in sorted(glob.glob(os.path.join(TMP, "cut", "scale", "x", "sc_*.png"))):
        a = rgba(f)
        px = a[..., :3].astype(int)
        orange = (np.abs(px - [220, 130, 50]).sum(-1) < 60) & (a[..., 3] > 0)
        xs = np.nonzero(orange.any(0))[0]
        assert abs((xs.max() - xs.min() + 1) - 20) <= 1, (f, xs.max() - xs.min() + 1)
    r = run("check_cycle.py", p("cut", "walk", "wk_*.png"), "--json")
    res = json.loads(r.stdout)
    assert res["frames"] == 4 and len(res["steps"]) == 4


@test
def despill_cli():
    im = Image.new("RGB", (60, 60), (255, 0, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([8, 8, 52, 52], fill=(20, 20, 20))         # outline
    d.rectangle([10, 10, 50, 50], fill=(100, 50, 100))     # purple cast inside it
    d.rectangle([14, 14, 46, 46], fill=(120, 80, 50))      # brown core
    d.ellipse([52, 40, 59, 50], fill=(150, 30, 150))       # drop shadow touching the background
    src = p("raw", "spill.png")
    im.save(src)
    run("despill.py", src, "-o", p("cut", "spill_clean.png"))
    a = rgba(p("cut", "spill_clean.png"))
    assert tuple(a[30, 30, :3]) == (120, 80, 50), a[30, 30]
    assert abs(int(a[11, 11, 0]) - int(a[11, 11, 2])) <= 1 and a[11, 11, 0] <= 55, a[11, 11]
    assert tuple(a[2, 2, :3]) == (255, 0, 255), "the key itself must stay"
    assert tuple(a[45, 56, :3]) == (150, 30, 150), "drop shadows must stay key-coloured for the cutter"
    # alpha mode: only inside the kept alpha
    b = np.zeros((4, 4, 4), np.uint8)
    b[...] = (100, 50, 100, 0)
    b[1:3, 1:3] = (100, 50, 100, 255)
    Image.fromarray(b, "RGBA").save(p("raw", "spill_alpha.png"))
    run("despill.py", p("raw", "spill_alpha.png"), "-O", os.path.join(TMP, "cut", "despilled"))
    c = rgba(os.path.join(TMP, "cut", "despilled", "spill_alpha.png"))
    assert tuple(c[1, 1]) == (50, 50, 50, 255) and tuple(c[0, 0]) == (100, 50, 100, 0), (c[1, 1], c[0, 0])


@test
def cut_boxes_modes():
    im = Image.new("RGB", (600, 300), (90, 40, 55))           # icon side: flat dark rose
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 120, 120], fill=(180, 150, 90))
    d.rectangle([300, 0, 599, 299], fill=(255, 0, 255))        # FX side: magenta
    d.ellipse([340, 60, 440, 160], fill=(200, 200, 210))       # cloud
    for x in (350, 380, 410):
        d.rectangle([x, 190, x + 6, 210], fill=(80, 110, 200))  # rain drops (loose bits)
    d.ellipse([480, 60, 560, 140], fill=(255, 150, 255))       # pink glow
    d.ellipse([505, 85, 535, 115], fill=(255, 240, 200))
    sheet = p("raw", "boxes_sheet.png")
    im.save(sheet)
    boxes = {"defaults": {"mode": "body"}, "items": {
        "icon": {"sheet": sheet, "box": [0, 0, 150, 150], "size": "16x16", "key": "corner", "corner_at": [4, 4]},
        "cloud_body": {"sheet": sheet, "box": [320, 40, 470, 230], "size": "30x30"},
        "cloud_all": {"sheet": sheet, "box": [320, 40, 470, 230], "size": "30x30", "mode": "all"},
        "glow": {"sheet": sheet, "box": [470, 50, 570, 150], "size": "20x20", "mode": "glow", "pad": True}}}
    bj = p("boxes", "b.json")
    json.dump(boxes, open(bj, "w"))
    run("cut_boxes.py", bj, "--out-dir", p("cut", "boxes"), "--report", p("cut", "boxes.json"))
    icon = rgba(p("cut", "boxes", "icon.png"))
    assert max(icon.shape[:2]) == 16 and (icon[..., 3] > 0).all(), "icon should be one solid tan block"
    body, allp = rgba(p("cut", "boxes", "cloud_body.png")), rgba(p("cut", "boxes", "cloud_all.png"))
    blue = lambda a: ((opaque(a)[:, 2] > opaque(a)[:, 0] + 60)).sum()
    assert blue(body) == 0 and blue(allp) > 0, ("body keeps the rain?", blue(body), blue(allp))
    g = rgba(p("cut", "boxes", "glow.png"))
    assert g.shape[:2] == (20, 20) and magenta_left(g) == 0
    px = opaque(g)
    assert ((px[:, 0] >= px[:, 1]) & (px[:, 1] >= px[:, 2])).mean() > 0.95, "glow not warm white"
    run("cut_boxes.py", bj, "--out-dir", p("cut", "boxes2x"), "--density", "2", "--only", "icon")
    assert max(rgba(p("cut", "boxes2x", "icon.png")).shape[:2]) == 32


@test
def pixelize_size_rules():
    src = p("raw", "tall.png")
    Image.new("RGBA", (64, 128), (120, 90, 60, 255)).save(src)
    r = run("pixelize.py", src, "-o", p("px", "x.png"), expect=None)
    assert r.returncode == 2 and "LONGEST" in r.stderr, r.stderr
    r = run("pixelize.py", src, "-o", p("px", "x.png"), "--target", "0", expect=None)
    assert r.returncode == 2
    run("pixelize.py", src, "-o", p("px", "t32.png"), "--target", "32", "--no-pad")
    assert Image.open(p("px", "t32.png")).size == (16, 32), "--target is the LONG side"
    run("pixelize.py", src, "-o", p("px", "t32pad.png"), "--target", "32")
    assert Image.open(p("px", "t32pad.png")).size == (32, 32)
    pal = write_palette(p("pal", "px.hex"), ["000000", "7f5f3f", "ffffff"])
    run("pixelize.py", src, "-O", p("px", "keep"), "--keep-size", "--palette", pal)
    a = rgba(p("px", "keep", "tall.png"))
    assert a.shape[:2] == (128, 64) and {tuple(c) for c in opaque(a)} <= {(0, 0, 0), (127, 95, 63), (255, 255, 255)}
    run("pixelize.py", src, "-o", p("px", "det.png"), "--detect")


@test
def remap_reserved_cli():
    im = Image.new("RGBA", (20, 10), (45, 37, 29, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 4, 9], fill=(140, 37, 25, 255))        # reserved red 8c2519
    d.rectangle([15, 0, 19, 9], fill=(234, 107, 93, 255))     # reserved ea6b5d
    src = p("px", "title.png")
    im.save(src)
    r = run("remap_reserved.py", src, "--reserved", "8c2519,ea6b5d", "--to", "2d251d", "-o", p("px", "title_ok.png"))
    assert "100 reserved px" in r.stdout, r.stdout
    a = rgba(p("px", "title_ok.png"))
    assert {tuple(c) for c in opaque(a)} == {(45, 37, 29)}
    run("remap_reserved.py", src, "--hue", "340-16", "--min-sat", "0.35", "--to", "2d251d",
        "--x-range", "0-0.5", "-o", p("px", "title_half.png"))
    a = rgba(p("px", "title_half.png"))
    assert tuple(a[5, 2, :3]) == (45, 37, 29) and tuple(a[5, 17, :3]) == (234, 107, 93)


@test
def palette_build_and_coverage():
    pj = p("pal", "palettes.json")
    if os.path.exists(pj):
        os.remove(pj)
    run("palette_build.py", "init", pj)
    out = p("pal", "built", "x")
    run("palette_build.py", "build", pj, "--out-dir", os.path.dirname(out))
    d = os.path.dirname(out)
    for f in ("palette.hex", "palette.png", "palette_preview.png", "palette_world.hex", "palette_all.hex"):
        assert os.path.exists(os.path.join(d, f)), f
    world = open(os.path.join(d, "palette_world.hex")).read().split()
    allp = open(os.path.join(d, "palette_all.hex")).read().split()
    assert "8c2519" not in world and "8c2519" in allp, "reserved colours must leave art sub-palettes"
    ref = Image.new("RGB", (100, 100), (244, 246, 240))
    ImageDraw.Draw(ref).rectangle([0, 0, 49, 99], fill=(200, 40, 200))   # 50% far from the palette
    ref.save(p("pal", "ref.png"))
    r = run("palette_build.py", "coverage", p("pal", "ref.png"), "--palette", os.path.join(d, "palette.hex"),
            "--suggest", "2", "--json", "--miss-map", p("pal", "miss.png"))
    res = json.loads(r.stdout[r.stdout.index("{"):])
    assert 45 < res["miss_percent"] < 55, res
    assert any(abs(int(s["hex"][:2], 16) - 200) < 20 for s in res["suggest"]), res["suggest"]
    assert res["miss_after_percent"] < 1, res


@test
def make_palette_modes():
    ref = Image.new("RGB", (40, 40), (10, 10, 10))
    d = ImageDraw.Draw(ref)
    d.rectangle([0, 0, 19, 39], fill=(200, 50, 50))
    d.rectangle([20, 0, 39, 19], fill=(50, 200, 50))
    ref.save(p("pal", "mp_ref.png"))
    run("make_palette.py", "extract", p("pal", "mp_ref.png"), "-n", "3", "-o", p("pal", "mp_ex"))
    assert len(open(p("pal", "mp_ex.hex")).read().split()) == 3
    run("make_palette.py", "ramp", "--hues", "10,120", "--steps", "3", "-o", p("pal", "mp_ramp"))
    assert len(open(p("pal", "mp_ramp.hex")).read().split()) == 8


# ---------------------------------------------------------------------------
# post passes, recolour, maps
# ---------------------------------------------------------------------------

@test
def soften_edges_inward_and_idempotent():
    src = p("px", "tree.png")
    im = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([2, 2, 9, 9], fill=(30, 60, 30, 255))
    im.save(src)
    run("soften_edges.py", src, "--ground", "5f7a4c", "-o", p("px", "tree_soft.png"))
    a = rgba(p("px", "tree_soft.png"))
    assert a[2, 2, 3] == 150 and a[5, 5, 3] == 255 and a[1, 1, 3] == 0, "rim alpha / inward only"
    assert (a[..., 3] > 0).sum() == 64, "soften must never add pixels outside"
    run("soften_edges.py", p("px", "tree_soft.png"), "--ground", "5f7a4c", "-o", p("px", "tree_soft2.png"))
    assert (rgba(p("px", "tree_soft2.png")) == a).all(), "second run changed the sprite"


@test
def recolor_cli():
    im = Image.new("RGB", (20, 10), (118, 118, 64))
    ImageDraw.Draw(im).rectangle([10, 0, 19, 9], fill=(107, 80, 59))
    im.save(p("px", "meadow.png"))
    run("recolor.py", p("px", "meadow.png"), "-o", p("px", "meadow_spring.png"))
    a = rgba(p("px", "meadow_spring.png"))
    assert a[5, 2, 1] > a[5, 2, 0] + 10 and tuple(a[5, 15, :3]) == (107, 80, 59), (a[5, 2], a[5, 15])


@test
def stitch_map_dither():
    cols = [(200, 0, 0), (0, 200, 0), (0, 0, 200)]
    args = []
    for i, c in enumerate(cols):
        f = p("map", "s%d.png" % i)
        Image.new("RGB", (100, 60), c).save(f)
        args.append("%d:%s" % (i * 40, f))
    run("stitch_map.py", "--sections", *args, "--width", "50", "--section-size", "60", "-o", p("map", "map.png"))
    a = np.array(Image.open(p("map", "map.png")).convert("RGB")).astype(int)
    assert a.shape == (140, 50, 3)
    assert (a[:40, :, 0] == 200).all() and (a[100:, :, 2] == 200).all()
    ov = a[40:60]
    assert (ov[..., 0] == 200).any() and (ov[..., 1] == 200).any(), "overlap should dither both sections"
    assert not ((ov != [200, 0, 0]).all(-1) & (ov != [0, 200, 0]).all(-1)).any(), "dither, not cross-fade"


@test
def fit_ratio_round_trip_and_paste_keep():
    src = p("map", "plan.png")
    im = Image.new("RGB", (96, 216), (50, 120, 50))
    ImageDraw.Draw(im).rectangle([90, 0, 95, 215], fill=(10, 10, 200))
    im.save(src)
    run("fit_ratio.py", "pad", src, "-o", p("map", "plan_pad.png"))
    meta = json.load(open(p("map", "plan_pad.json")))
    assert meta["ratio"] == "9:16" and meta["padded"] == [122, 216], meta
    pad = np.array(Image.open(p("map", "plan_pad.png")))
    assert (pad[:, 96:] == [10, 10, 200]).all(), "the pad must carry the edge colour"
    Image.open(p("map", "plan_pad.png")).resize((61, 108)).save(p("map", "painted.png"))  # 'model output'
    run("fit_ratio.py", "crop", p("map", "painted.png"), "--meta", p("map", "plan_pad.json"), "-o", p("map", "back.png"))
    assert Image.open(p("map", "back.png")).size == (96, 216)
    Image.new("RGB", (100, 100), (0, 0, 0)).save(p("map", "base.png"))
    Image.new("RGB", (100, 100), (255, 255, 255)).save(p("map", "src.png"))
    mask = Image.new("L", (100, 100), 0)
    ImageDraw.Draw(mask).rectangle([20, 20, 79, 79], fill=255)
    mask.save(p("map", "keep.png"))
    for env in (None, {"PIXEL_FORGE_NO_SCIPY": "1"}):
        run("fit_ratio.py", "paste-keep", p("map", "base.png"), "--source", p("map", "src.png"),
            "--mask", p("map", "keep.png"), "--feather", "8", "-o", p("map", "kept.png"), env=env)
        k = np.array(Image.open(p("map", "kept.png")))[..., 0]
        assert (k[35:65, 35:65] == 255).all() and (k[:15] == 0).all(), "core kept, outside untouched"
        edge = k[20:24, 20:80]
        assert 0 < (edge == 255).mean() < 1, "the feather should be dithered"


# ---------------------------------------------------------------------------
# animation
# ---------------------------------------------------------------------------

@test
def walk_and_sway_frames():
    src = make_sprite(p("anim", "walker.png"))
    run("make_walk_frames.py", "--src", src, "--prefix", "w", "--out-dir", p("anim", "out"))
    fr = [rgba(p("anim", "out", "w_f%d.png" % i)) for i in range(4)]
    assert len({f.shape for f in fr}) == 1 and not (fr[0] == fr[1]).all()
    r = run("make_walk_frames.py", "--src", src, "--prefix", "m", "--mirror-a", "--pair", "--out-dir", p("anim", "out"))
    assert "f0..f1" in r.stdout, r.stdout
    a, b = rgba(p("anim", "out", "m_f0.png")), rgba(p("anim", "out", "m_f1.png"))
    assert (a[:, ::-1] == b).all()
    run("make_sway_frames.py", "--src", src, "--prefix", "s", "--amp", "2", "--out-dir", p("anim", "out"))
    sw = [rgba(p("anim", "out", "s_f%d.png" % i)) for i in range(4)]
    assert all((f[-3:] == sw[0][-3:]).all() for f in sw), "the base must stay planted"
    assert not (sw[1][:4] == sw[0][:4]).all(), "the top should move"


@test
def check_cycle_flags_duplicates():
    src = make_sprite(p("anim", "dup.png"))
    shutil.copy(src, p("anim", "dup2.png"))
    r = run("check_cycle.py", src, p("anim", "dup2.png"), "--strict", expect=1)
    assert "near-duplicate" in r.stdout and "mirror" in r.stdout, r.stdout
    big = Image.new("RGBA", (24, 24), (200, 120, 60, 255))
    big.save(p("anim", "ghost.png"))
    r = run("check_cycle.py", src, p("anim", "ghost.png"), "--json", "--strict", expect=1)
    assert any("opaque pixels" in f for f in json.loads(r.stdout)["flags"])
    Image.new("RGBA", (10, 10)).save(p("anim", "small.png"))
    r = run("check_cycle.py", src, p("anim", "small.png"), expect=None)
    assert r.returncode != 0 and "shared box" in r.stderr


@test
def water_frames_and_sway_mask():
    bg = Image.new("RGB", (360, 640), (230, 210, 160))
    d = ImageDraw.Draw(bg)
    d.rectangle([0, 0, 359, 120], fill=(200, 215, 230))           # sky
    d.rectangle([0, 400, 359, 639], fill=(40, 110, 150))          # sea
    for y in range(400, 640, 8):
        d.line([0, y, 359, y], fill=(70, 140, 170))
    d.ellipse([40, 60, 120, 140], fill=(40, 100, 50))             # tree foliage
    d.rectangle([200, 20, 230, 40], fill=(230, 40, 40))           # a kite
    bg.save(p("bg", "level.png"))
    run("make_water_frames.py", "--src", p("bg", "level.png"), "--prefix", "water", "--width", "180",
        "--height", "320", "--water-top", "196", "--out-dir", p("bg", "water"))
    fr = sorted(glob.glob(p("bg", "water", "water_*.png")))
    assert len(fr) == 8 and Image.open(fr[0]).size == (180, 124)
    assert not (np.array(Image.open(fr[0])) == np.array(Image.open(fr[2]))).all()
    for env in (None, {"PIXEL_FORGE_NO_SCIPY": "1"}):
        r = run("make_sway_mask.py", "--src", p("bg", "level.png"), "--out", p("bg", "sway.png"),
                "--below", "200", "--sky", "60", env=env)
        m = np.array(Image.open(p("bg", "sway.png")))
        assert m[100, 80] > 200 and m[30, 215] > 200 and m[500, 100] == 0, (m[100, 80], m[30, 215])


# ---------------------------------------------------------------------------
# small sprites, atlases, hues, decision images
# ---------------------------------------------------------------------------

@test
def prep_sprite_and_atlas():
    big = Image.new("RGBA", (300, 150), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse([20, 20, 280, 130], fill=(180, 90, 40, 200))
    big.save(p("prep", "big.png"))
    run("prep_sprite.py", p("prep", "big.png"), "-o", p("prep", "small.png"), "-s", "24x24")
    a = rgba(p("prep", "small.png"))
    assert a.shape[:2] == (24, 24) and set(np.unique(a[..., 3])) <= {0, 255}
    pal = write_palette(p("pal", "prep.hex"), ["#b45a28 orange", "000000"])
    run("prep_sprite.py", p("prep", "big.png"), "-o", p("prep", "grid"), "-s", "12x12", "--cols", "2",
        "--palette", pal)
    cells = sorted(glob.glob(p("prep", "grid", "*.png")))
    assert len(cells) == 2 and {tuple(c) for c in opaque(rgba(cells[0]))} <= {(180, 90, 40), (0, 0, 0)}
    for i in range(3):
        make_sprite(p("prep", "atlas_src", "a%d.png" % i), (16, 16))
    run("build_atlas.py", p("prep", "atlas_src"), "-o", p("prep", "atlas.png"), "--cell", "16")
    man = json.load(open(p("prep", "atlas.json")))
    assert Image.open(p("prep", "atlas.png")).size == (32, 32) and len(man["frames"]) == 3
    run("build_atlas.py", p("prep", "atlas_src", "*.png"), "-o", p("prep", "strip.png"), "--cell", "17x20", "--row")
    assert Image.open(p("prep", "strip.png")).size == (51, 20)
    run("build_atlas.py", p("prep", "atlas_src"), "-o", p("prep", "bad.png"), "--cell", "8", expect=1)


@test
def measure_hues_clusters():
    import colorsys
    for i in range(2):
        im = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for hue, box in ((54, [0, 0, 9, 19]), (68, [10, 0, 19, 19])):
            c = tuple(int(v * 255) for v in colorsys.hsv_to_rgb(hue / 360, 0.8, 0.85)) + (255,)
            d.rectangle(box, fill=c)
        im.save(p("hues", "t%d.png" % i))
    r = run("measure_hues.py", p("hues", "t*.png"), "--json", "--plot", p("hues", "plot.png"))
    cl = json.loads(r.stdout)["clusters"]
    assert len(cl) == 2, cl
    for want in (54, 68):
        assert any(c["from_deg"] <= want <= c["to_deg"] for c in cl), (want, cl)
    assert all(not (c["from_deg"] <= 61 <= c["to_deg"]) for c in cl), "the two hues must not merge"


@test
def contact_sheet_modes():
    os.makedirs(p("raw", "enemy", "x"), exist_ok=True)
    for i, c in enumerate([(220, 110, 40), (200, 90, 30), (230, 140, 60)], 1):
        im = Image.new("RGB", (400, 300), (255, 0, 255))
        d = ImageDraw.Draw(im)
        d.ellipse([100, 80, 300, 220], fill=(20, 20, 20))
        d.ellipse([106, 86, 294, 214], fill=c)
        im.save(p("raw", "enemy", "enemy_option_%d.png" % i))
    ref = make_sprite(p("raw", "hero.png"), (12, 24))
    Image.new("RGB", (360, 640), (230, 210, 160)).save(p("raw", "ground.png"))
    r = run("contact_sheet.py", "--subject", p("raw", "enemy"), "--game-width", "18", "--reference", ref,
            "--background", p("raw", "ground.png"), "--letters")
    out = p("raw", "enemy", "enemy_options_at_game_size.png")
    assert os.path.exists(out) and "3 option(s)" in r.stdout and "18x13" in r.stdout, r.stdout
    w, h = Image.open(out).size
    assert w > 3 * h > 0
    run("contact_sheet.py", p("raw", "enemy", "enemy_option_*.png"), "--game-width", "30", "--frame", "120x80",
        "-o", p("raw", "frame.png"), "--title", "enemy picks", "--cols", "2")
    run("contact_sheet.py", "--grid", p("raw", "enemy", "enemy_option_*.png"), "-o", p("raw", "grid.jpg"))
    assert Image.open(p("raw", "grid.jpg")).size == (960, 720)


# ---------------------------------------------------------------------------
# fetch, build
# ---------------------------------------------------------------------------

@test
def fetch_art_file_urls_and_ledger():
    from pathlib import Path
    game = p("game_fetch", "x")
    game = os.path.dirname(game)
    os.makedirs(os.path.join(game, "docs"), exist_ok=True)
    tpl = os.path.join(ROOT, "plugins", "pixel-forge", "skills", "pixel-forge", "assets", "project", "docs", "assets.md")
    if os.path.exists(tpl):
        shutil.copy(tpl, os.path.join(game, "docs", "assets.md"))
    srcs = []
    for v, c in (("a", (200, 0, 0)), ("b", (0, 200, 0))):
        f = p("dl", "hero_%s_src.png" % v)
        Image.new("RGB", (64, 32), c).save(f)
        srcs.append((v, Path(f).resolve().as_uri()))
    lines = "# picks\n" + "".join("hero %s %s cid%s imagen-nano-banana-2\n" % (v, u, v) for v, u in srcs)
    open(p("dl", "b07.txt"), "w").write(lines)
    r = run("fetch_art.py", p("dl", "b07.txt"), "--batch", "b07", "--root", game, "--prompt-ref", "prompts.md#b07")
    assert "2 row(s) added" in r.stdout, r.stdout
    assert os.path.exists(os.path.join(game, "raw_art", "b07", "hero_a.png"))
    assert os.path.exists(os.path.join(game, "raw_art", "b07", "sheet_hero.jpg"))
    assert os.path.exists(os.path.join(game, "raw_art", ".gdignore"))
    led = open(os.path.join(game, "docs", "assets.md")).read()
    assert "| b07 | hero | a | `raw_art/b07/hero_a.png` | cida | imagen-nano-banana-2 | prompts.md#b07 |" in led, led
    r = run("fetch_art.py", "-", "--batch", "b07", "--root", game, stdin=lines)
    assert "0 row(s) added" in r.stdout and "exists" in r.stdout
    run("fetch_art.py", "-", "--batch", "b08", "--root", game, "--retries", "1", expect=1,
        stdin="hero z file:///definitely/not/here.png\n")
    # a ledger with no Raw batches section gets one
    open(os.path.join(game, "docs", "other.md"), "w").write("# Ledger\n\n## Sprites\n\n| a | b |\n|---|---|\n")
    run("fetch_art.py", p("dl", "b07.txt"), "--batch", "b09", "--root", game, "--ledger", "docs/other.md")
    o = open(os.path.join(game, "docs", "other.md")).read()
    assert "## Raw batches" in o and o.count("| b09 |") == 2 and "## Sprites" in o


@test
def art_build_manifest_incremental_hd():
    game = os.path.dirname(p("game_build", "x"))
    os.makedirs(os.path.join(game, "raw_art", "b1"), exist_ok=True)
    os.makedirs(os.path.join(game, "art", "boxes"), exist_ok=True)
    make_overlap_sheet(os.path.join(game, "raw_art", "b1", "kit.png"))
    make_grid_sheet(os.path.join(game, "raw_art", "b1", "grid.png"))
    make_pink_on_green(os.path.join(game, "raw_art", "b1", "pink.png"))
    open(os.path.join(game, "forge.json"), "w").write('{"view_w": 360, "view_h": 640, "pixel_scale": 2}\n')
    write_palette(os.path.join(game, "art", "pal.hex"), ["141414", "966e46", "5a7840", "3c508c", "6e3c6e", "f4f6f0"])
    json.dump({"items": {"pink_icon": {"sheet": "../../raw_art/b1/pink.png", "box": [40, 20, 260, 220],
                                       "size": "16x16", "key": "green"}}},
              open(os.path.join(game, "art", "boxes", "b.json"), "w"))
    manifest = {"raw_dir": "raw_art", "out_dir": "art/sprites", "hd_dir": "art/sprites_hd",
                "post_options": {"soften_edges": {"ground": "5f7a4c"}},
                "entries": [
                    {"sheet": "b1/kit.png", "cutter": "blob", "prefix": "home", "sizes": ["40x60", "40x40", "36x48"],
                     "despill": True, "palette": "art/pal.hex", "hd": [2]},
                    {"sheet": "b1/grid.png", "cutter": "profile", "prefix": "gr", "sizes": "20x20", "rows": 2,
                     "clean_fringe": True, "post": ["soften_edges"]},
                    {"cutter": "boxes", "boxes": "art/boxes/b.json", "hd": [2]},
                    {"cutter": "plate", "sheet": "b1/grid.png", "out": "art/backgrounds/grid.png", "target": 100,
                     "palette": "art/pal.hex"},
                    {"cutter": "plate", "sheet": "b1/grid.png", "out": "art/backgrounds/off.png", "target": 10,
                     "enabled": False}]}
    mp = os.path.join(game, "art", "manifest.json")
    json.dump(manifest, open(mp, "w"), indent=1)
    sub = os.path.join(game, "art")          # run from a subfolder: the root is found via forge.json
    r = run("art_build.py", cwd=sub)
    assert "built 4 entries" in r.stdout and "now run: godot --headless --path . --import" in r.stdout, r.stdout
    assert "not density x" not in r.stdout, r.stdout
    sp = os.path.join(game, "art", "sprites")
    assert sorted(os.listdir(sp)) == ["gr_00.png", "gr_01.png", "gr_02.png",
                                      "home_00.png", "home_01.png", "home_02.png", "pink_icon.png"], os.listdir(sp)
    pal = {(20, 20, 20), (150, 110, 70), (90, 120, 64), (60, 80, 140), (110, 60, 110), (244, 246, 240)}
    for i in range(3):
        a = rgba(os.path.join(sp, "home_%02d.png" % i))
        assert {tuple(c) for c in opaque(a)} <= pal, "palette lock"
        assert magenta_left(a) == 0
        hd = rgba(os.path.join(game, "art", "sprites_hd", "home_%02d.png" % i))
        assert hd.shape[0] == 2 * a.shape[0] and hd.shape[1] == 2 * a.shape[1]
    assert rgba(os.path.join(sp, "gr_00.png"))[..., 3].max() == 255
    assert 150 in np.unique(rgba(os.path.join(sp, "gr_00.png"))[..., 3]), "soften_edges post pass"
    assert Image.open(os.path.join(game, "art", "backgrounds", "grid.png")).size == (100, 75)
    assert not os.path.exists(os.path.join(game, "art", "backgrounds", "off.png"))
    r = run("art_build.py", cwd=game)
    assert "built 0 entries" in r.stdout and "4 unchanged" in r.stdout, r.stdout
    manifest["entries"][1]["sizes"] = "24x24"
    json.dump(manifest, open(mp, "w"), indent=1)
    r = run("art_build.py", cwd=game)
    assert "built 1 entry" in r.stdout and "3 unchanged" in r.stdout, r.stdout
    assert Image.open(os.path.join(sp, "gr_00.png")).size == (24, 24)
    r = run("art_build.py", "--list", cwd=game)
    assert "STALE" not in r.stdout
    r = run("art_build.py", "--dry-run", "--force", "--only", "home", cwd=game)
    assert "slice_sheet.py" in r.stdout


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------

def wav_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / float(w.getframerate())


@test
def synth_sfx_cli():
    r = run("synth_sfx.py", "--list")
    assert "rain-loop" in r.stdout and "thunder-roll" in r.stdout and "hit" in r.stdout
    run("synth_sfx.py", "--preset", "tone", "-o", p("audio", "tap.wav"), "--freq", "660", "--seconds", "0.12")
    assert abs(wav_seconds(p("audio", "tap.wav")) - 0.12) < 0.01
    run("synth_sfx.py", "gust", "-o", p("audio", "gust.wav"))                 # positional form
    run("synth_sfx.py", "--all", p("audio", "all"), "--rate", "22050")
    files = glob.glob(p("audio", "all", "*.wav"))
    assert len(files) >= 40 and os.path.exists(p("audio", "all", "thunder_roll_3.wav")), len(files)
    if ffmpeg_path():
        run("synth_sfx.py", "--preset", "wind-loop", "-o", p("audio", "wind_loop.ogg"), "--seconds", "3")
        assert os.path.getsize(p("audio", "wind_loop.ogg")) > 1000
    else:
        SKIPS.append("synth_sfx .ogg output (no ffmpeg)")


@test
def synth_music_cli():
    r = run("synth_music.py", "--example", "calm")
    spec = json.loads(r.stdout)
    spec["chords"] = ["Dm", "C"]
    spec["melody"] = [[0, "D5", 2], [4, "A4", 4]]
    spec["drums"] = "D.s.d.s."
    json.dump(spec, open(p("audio", "song.json"), "w"))
    r = run("synth_music.py", p("audio", "song.json"), "-o", p("audio", "song.wav"), "--rate", "22050")
    want = 2 * 2 * 4 * 60.0 / spec["bpm"]
    assert abs(wav_seconds(p("audio", "song.wav")) - want) < 0.05, (wav_seconds(p("audio", "song.wav")), want)
    assert "peak -12.0 dBFS" in r.stdout, r.stdout
    with wave.open(p("audio", "song.wav")) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32767
    assert abs(20 * np.log10(np.abs(x).max()) + 12) < 0.2
    run("synth_music.py", "--list")


@test
def audio_encode_cli():
    if not ffmpeg_path():
        SKIPS.append("audio_encode reencode/loudnorm (no ffmpeg)")
        raise Skip("no ffmpeg")
    run("synth_sfx.py", "--preset", "storm-loop", "-o", p("audio", "enc", "storm_loop.wav"), "--seconds", "4")
    run("synth_sfx.py", "--preset", "chime", "-o", p("audio", "enc", "chime.wav"))
    r = run("audio_encode.py", "reencode", p("audio", "enc"), "-O", p("audio", "enc_ogg"), "--format", "ogg")
    assert r.stdout.count("OK") == 2 and "MB ->" in r.stdout, r.stdout
    assert os.path.exists(p("audio", "enc_ogg", "storm_loop.ogg"))
    r = run("audio_encode.py", "loudnorm", p("audio", "enc", "chime.wav"), "-O", p("audio", "enc_norm"))
    assert "OK" in r.stdout
    r = run("audio_encode.py", "reencode", p("audio", "enc", "storm_loop.wav"), "-O", p("audio", "enc_mp3"),
            "--format", "mp3")
    assert "loops should be OGG" in r.stdout
    r = run("audio_encode.py", "probe", p("audio", "enc_ogg"))
    assert "vorbis" in r.stdout


# ---------------------------------------------------------------------------
# reports, environment, delivery
# ---------------------------------------------------------------------------

@test
def bot_report_tables():
    lines = [
        'noise line',
        'BOT|{"kind":"unit","level":1,"unit":1,"attempt":1,"result":"fail","time_s":300,"hits":10,"earned":40,"goal":100}',
        'BOT|{"kind":"unit","level":1,"unit":1,"attempt":2,"result":"complete","time_s":360,"hits":12}',
        'BOT|{"kind":"unit","level":2,"unit":1,"attempt":1,"result":"fail","time_s":200,"hits":3,"earned":69,"goal":100}',
        'BOT|{"kind":"done","level":2}']
    open(p("bots", "run.log"), "w").write("\n".join(lines) + "\n")
    open(p("bots", "seeds.jsonl"), "w").write(
        '{"kind":"attempt","seed":1,"level":3,"result":"clear","time_s":600,"hits":2}\n'
        '{"kind":"attempt","seed":2,"level":3,"result":"stuck","time_s":1800,"hits":0}\n')
    r = run("bot_report.py", p("bots"), "--title", "Bots")
    out = r.stdout
    assert "| 1 | 1 | 2 | 1/2 | a2 | 0% |" in out, out
    assert "**FAIL 69%**" in out and "| 3 | - | 2 | 1/2 | a1 | 50% |" in out, out
    run("bot_report.py", p("bots", "run.log"), "-o", p("bots", "report.md"))
    assert "Cleared 1 of 2" in open(p("bots", "report.md")).read()


@test
def doctor_json_and_write_local():
    local = p("doctor", "CLAUDE.local.md")
    open(local, "w").write("# notes\n\n## Keep me\n\nhello\n")
    r = run("doctor.py", "--json", "--write-local", local, expect=None, timeout=180)
    assert r.returncode in (0, 1), r.stderr
    res = json.loads(r.stdout)
    names = {c["name"] for c in res["checks"]}
    assert {"python", "Pillow", "numpy", "godot", "git", "ffmpeg", "forge.json"} <= names, names
    run("doctor.py", "--write-local", local, expect=None, timeout=180)
    text = open(local).read()
    assert text.count("## Machine paths") == 1 and "## Keep me" in text and "hello" in text, text
    assert "PYTHON=" in text


@test
def stage_push_zip():
    git = shutil.which("git")
    if not git:
        SKIPS.append("stage_push (no git)")
        raise Skip("no git")
    repo = os.path.dirname(p("sp", "origin", "x"))
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    subprocess.run([git, "init", "-q", repo], check=True, env=env)
    open(os.path.join(repo, "a.txt"), "w").write("one\n")
    open(os.path.join(repo, "gone.txt"), "w").write("bye\n")
    subprocess.run([git, "-C", repo, "add", "-A"], check=True, env=env)
    subprocess.run([git, "-C", repo, "-c", "commit.gpgsign=false", "commit", "-qm", "init"], check=True, env=env)
    src = os.path.dirname(p("sp", "work", "x"))
    open(os.path.join(src, "a.txt"), "w").write("two\n")
    open(os.path.join(src, "new.txt"), "w").write("new\n")
    os.makedirs(os.path.join(src, ".godot"), exist_ok=True)
    open(os.path.join(src, ".godot", "cache.bin"), "w").write("x")
    open(os.path.join(src, "icon.png.import"), "w").write("x")
    r = run("stage_push.py", "--repo", repo, "--src", src, "--out", p("sp", "push.zip"))
    assert "deletions: 1" in r.stdout and "gone.txt" in r.stdout, r.stdout
    names = zipfile.ZipFile(p("sp", "push.zip")).namelist()
    assert any(n.endswith("/new.txt") for n in names) and any("/.git/" in n for n in names)
    assert not any(".godot" in n or n.endswith(".import") for n in names), names


# ---------------------------------------------------------------------------

def main():
    global TMP
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", default="", help="only tests whose name contains this")
    ap.add_argument("--keep", action="store_true", help="keep the temp folder")
    a = ap.parse_args()
    TMP = tempfile.mkdtemp(prefix="pf_tests_")
    print("Pixel Forge script tests  (python %s, scripts: %s)" % (sys.version.split()[0], SCRIPTS))
    passed = failed = skipped = 0
    t0 = time.time()
    for fn in TESTS:
        if a.k and a.k not in fn.__name__:
            continue
        t = time.time()
        try:
            fn()
            passed += 1
            print("  PASS  %-44s %5.1fs" % (fn.__name__, time.time() - t))
        except Skip as e:
            skipped += 1
            print("  SKIP  %-44s %s" % (fn.__name__, e))
        except Exception as e:
            failed += 1
            print("  FAIL  %-44s %5.1fs" % (fn.__name__, time.time() - t))
            msg = str(e) if isinstance(e, AssertionError) else traceback.format_exc()
            print("        " + msg.strip().replace("\n", "\n        ")[:4000])
    for s in SKIPS:
        print("  note: skipped", s)
    print("\n%d passed, %d failed, %d skipped in %.0fs" % (passed, failed, skipped, time.time() - t0))
    if a.keep or failed:
        print("temp folder kept:", TMP)
    else:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
