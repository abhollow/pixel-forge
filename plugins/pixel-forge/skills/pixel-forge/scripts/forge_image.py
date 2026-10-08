#!/usr/bin/env python3
"""Shared image helpers for the Pixel Forge scripts (keying, despill, fitting,
palettes). Not a tool you run on art; the cutters import it.

    python forge_image.py --self-test

Why one module: the same five operations -- find the key colour, key only the
background, pull the key's colour cast out of the subject, scale to a box with
hard alpha, snap to a palette -- run in slice_sheet, cut_boxes, pixelize,
contact_sheet and art_build. Separate copies of the magenta test drift apart
and get their bugs fixed one at a time. Here there is one copy.

Keying is by RATIO, not exact colour: a "#FF00FF" background often measures
off-key, e.g. (252, 52, 252), and its drop shadows are darker magenta. A pixel
is magenta-key when red and blue are both bright and green is well below both
(g < 0.62*r and g < 0.62*b); green-key when green is well above both.
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_ndimage as ndi  # noqa: E402

KEYS = ("magenta", "green", "auto", "corner", "hue", "none")


# ---------------------------------------------------------------------------
# small parsers
# ---------------------------------------------------------------------------

def hex_to_rgb(text):
    t = str(text).strip().lstrip("#")
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", t):
        raise ValueError("not a hex colour: %r" % text)
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(c):
    return "%02x%02x%02x" % tuple(int(v) for v in c[:3])


def parse_size(text):
    """'105x82' -> (105, 82). Also accepts [105, 82]."""
    if isinstance(text, (list, tuple)):
        return int(text[0]), int(text[1])
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", str(text))
    if not m:
        raise ValueError("size must look like 24x32, got %r" % text)
    return int(m.group(1)), int(m.group(2))


def parse_sizes(spec):
    """'16x16,16x20' or ['16x16', '16x20'] -> [(16, 16), (16, 20)]."""
    if isinstance(spec, str):
        parts = [p for p in spec.split(",") if p.strip()]
    else:
        parts = list(spec)
    return [parse_size(p) for p in parts]


def scaled_sizes(sizes, k):
    return [(max(1, int(round(w * k))), max(1, int(round(h * k)))) for w, h in sizes]


# ---------------------------------------------------------------------------
# load / save
# ---------------------------------------------------------------------------

def load_rgba(path):
    return np.array(Image.open(path).convert("RGBA"))


def save_rgba(arr, path):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    Image.fromarray(np.asarray(arr, np.uint8), "RGBA").save(path)


def has_alpha(arr):
    return arr.shape[2] == 4 and int(arr[..., 3].min()) < 250


# ---------------------------------------------------------------------------
# keying
# ---------------------------------------------------------------------------

def key_candidates(rgb, key="magenta", tol=60.0, corner_at=None):
    """Pixels that LOOK like background for the chosen key (no connectivity).

    magenta  ratio test: r, b > 90 and g < 0.62 * min(r, b). Catches #FF00FF,
             off-key (252, 52, 252) and the darker magenta of drop shadows.
    green    g > 90 and g > 1.4 * max(r, b). For pink/red/magenta subjects.
    corner   within `tol` (float RGB distance) of the corner colour -- for a
             sheet that came back on some other flat colour (e.g. an icon
             sheet on flat dark rose). `corner_at` = (x, y) to
             sample one pixel instead of the median of the four corners.
    hue      halo/glow key: r > g + tol and b > g + tol (tol default 28 here).
             Kills a pink glow that blended into magenta; tan, red and blue
             survive (e.g. a glowing title logo).
    """
    a = np.asarray(rgb)[..., :3].astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if key == "green":
        return (g > 90) & (g > r * 1.4) & (g > b * 1.4)
    if key == "corner":
        if corner_at is not None:
            ref = a[int(corner_at[1]), int(corner_at[0])]
        else:
            ref = np.median(np.stack([a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]), axis=0)
        return np.sqrt(((a - ref) ** 2).sum(axis=2)) < tol
    if key == "hue":
        m = 28.0 if tol in (None, 60.0) else float(tol)
        return (r > g + m) & (b > g + m)
    if key == "none":
        return np.zeros(a.shape[:2], bool)
    return (r > 90) & (b > 90) & (g < r * 0.62) & (g < b * 0.62)


def detect_key(rgb):
    """Guess the key from the border pixels: 'magenta', 'green' or 'corner'."""
    a = np.asarray(rgb)[..., :3]
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])[None]
    mag = key_candidates(border, "magenta").mean()
    grn = key_candidates(border, "green").mean()
    if mag >= 0.3 and mag >= grn:
        return "magenta"
    if grn >= 0.3:
        return "green"
    return "corner"


def background_mask(rgb, key="magenta", tol=60.0, border_connected=True,
                    enclosed="auto", corner_at=None):
    """True where the pixel is background.

    border_connected  only key-coloured regions that reach the image border
                      count (the classic rule): a hot-pink shirt inside a black outline
                      survives a magenta key.
    enclosed          what to do with key-coloured pockets walled off inside a
                      sprite (the gap between an arm and a body): 'auto' keys
                      them too when their colour is within 40 RGB of the
                      measured background (a pocket of pure key), and keeps
                      anything further away (the pink shirt). 'keep' = never
                      key enclosed pockets (border-connected only).
    Returns (mask, info) where info has 'key' (resolved) and 'enclosed_keyed'.
    """
    a = np.asarray(rgb)[..., :3]
    if key == "auto":
        key = detect_key(a)
    cand = key_candidates(a, key, tol, corner_at)
    info = {"key": key, "enclosed_keyed": 0}
    if not border_connected or key == "none":
        return cand, info
    bg = ndi.keep_border_connected(cand)
    if enclosed == "auto" and bg.any():
        pockets = cand & ~bg
        if pockets.any():
            ref = np.median(a[bg].reshape(-1, 3).astype(np.float32), axis=0)
            lab, n = ndi.label(pockets)
            if n:
                af = a.reshape(-1, 3).astype(np.float32)
                flat = lab.ravel()
                cnt = np.bincount(flat, minlength=n + 1).astype(np.float32)
                means = np.stack([np.bincount(flat, weights=af[:, c], minlength=n + 1) for c in range(3)], 1)
                means = means / np.maximum(cnt, 1)[:, None]
                close = np.sqrt(((means - ref) ** 2).sum(1)) < 40.0
                close[0] = False
                close &= cnt >= 2
                if close.any():
                    bg = bg | close[lab]
                    info["enclosed_keyed"] = int(close.sum())
    return bg, info


# ---------------------------------------------------------------------------
# despill
# ---------------------------------------------------------------------------

def despill(rgb, key="magenta", strength=1.0, where=None):
    """Pull the key's colour cast out of the subject.

    magenta: where min(r, b) > g, subtract the excess from r and b (brown-grey
    walls come back as purple-grey like 403040, and a palette then snaps them
    to heather). green: where g > max(r, b), pull g down to max(r, b).
    `where` (bool mask) limits it -- pass the kept alpha so the background
    itself is never touched. Returns float32 RGB.
    """
    x = np.asarray(rgb)[..., :3].astype(np.float32).copy()
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    if key == "green":
        excess = np.clip(g - np.maximum(r, b), 0, None) * strength
        if where is not None:
            excess = np.where(where, excess, 0)
        x[..., 1] -= excess
    elif key == "magenta":
        excess = np.clip(np.minimum(r, b) - g, 0, None) * strength
        if where is not None:
            excess = np.where(where, excess, 0)
        x[..., 0] -= excess
        x[..., 2] -= excess
    return np.clip(x, 0, 255)


def edge_band(alpha_mask, width):
    """Opaque pixels within `width` px of transparency."""
    inner = ndi.binary_erosion(alpha_mask, width)
    return alpha_mask & ~inner


# ---------------------------------------------------------------------------
# alpha, fitting
# ---------------------------------------------------------------------------

def hard_alpha(arr, threshold=128):
    out = np.array(arr, np.uint8, copy=True)
    out[..., 3] = np.where(out[..., 3] >= threshold, 255, 0)
    return out


def key_to_black(arr):
    """Transparent pixels become transparent BLACK before any resize.

    Why: a resampler that does not premultiply alpha blends a transparent
    pixel's colour into its neighbours, so keyed
    magenta leaves a pink fringe. Pillow premultiplies for RGBA, Godot's
    Image.resize does not -- zeroing costs nothing and makes either safe.
    """
    out = np.array(arr, np.uint8, copy=True)
    out[out[..., 3] == 0, :3] = 0
    return out


RESAMPLE = {"box": Image.Resampling.BOX, "lanczos": Image.Resampling.LANCZOS,
            "nearest": Image.Resampling.NEAREST, "bilinear": Image.Resampling.BILINEAR}


def resize_rgba(arr, size, resample="box"):
    img = Image.fromarray(key_to_black(arr), "RGBA")
    return np.array(img.resize((max(1, int(size[0])), max(1, int(size[1]))), RESAMPLE[resample]))


def close_pinholes(arr, max_px=6):
    """Fill tiny enclosed transparent specks left by the alpha threshold.

    Downscaling then hard-thresholding can punch a stray hole through a solid
    area. Anything transparent, walled off from the border and no bigger than
    max_px is an artefact, not a real gap; it takes its neighbours' mean colour.
    """
    out = np.array(arr, np.uint8, copy=True)
    clear = out[..., 3] == 0
    holes = clear & ~ndi.keep_border_connected(clear)
    if not holes.any():
        return out
    lab, n = ndi.label(holes)
    sz = ndi.sizes(lab, n)
    for idx in range(1, n + 1):
        if sz[idx - 1] > max_px:
            continue
        sel = lab == idx
        ring = ndi.binary_dilation(sel) & ~sel & (out[..., 3] > 0)
        if not ring.any():
            continue
        out[sel, :3] = out[ring][:, :3].mean(axis=0).astype(np.uint8)
        out[sel, 3] = 255
    return out


def clean_fringe(arr, key):
    """Drop leftover key-coloured pixels on a cut sprite (never on a subject
    coloured like the key)."""
    px = np.array(arr, np.int32, copy=True)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    if key == "green":
        bad = (g > r + 25) & (g > b + 25)
    else:
        bad = (b > g + 25) & (r > g + 25)
    px[bad & (px[..., 3] > 0), 3] = 0
    return px.astype(np.uint8)


ANCHORS = ("centre", "center", "bottom", "top", "left", "right")


def place(arr, canvas_size, anchor="centre"):
    """Put a sprite on a transparent canvas by anchor, cropping any overflow.

    bottom = feet on the bottom edge, centred across; top = top edge;
    left/right = against that side, centred vertically; centre = both.
    Returns (canvas, overflow_px).
    """
    cw, ch = canvas_size
    h, w = arr.shape[:2]
    if anchor in ("left",):
        ox = 0
    elif anchor in ("right",):
        ox = cw - w
    else:
        ox = (cw - w) // 2
    if anchor == "bottom":
        oy = ch - h
    elif anchor == "top":
        oy = 0
    else:
        oy = (ch - h) // 2
    out = np.zeros((ch, cw, 4), np.uint8)
    sx0, sy0 = max(0, -ox), max(0, -oy)
    dx0, dy0 = max(0, ox), max(0, oy)
    ww = min(w - sx0, cw - dx0)
    hh = min(h - sy0, ch - dy0)
    if ww > 0 and hh > 0:
        out[dy0:dy0 + hh, dx0:dx0 + ww] = arr[sy0:sy0 + hh, sx0:sx0 + ww]
    overflow = max(0, w - cw) + max(0, h - ch)
    return out, overflow


def fit_factor(src_size, target):
    sw, sh = src_size
    tw, th = target
    return min(tw / max(1, sw), th / max(1, sh))


def scale_sprite(arr, k, resample="box", threshold=128, pinholes=True):
    """Scale by factor k with key-to-black first, then hard alpha."""
    h, w = arr.shape[:2]
    nw, nh = max(1, int(round(w * k))), max(1, int(round(h * k)))
    small = resize_rgba(arr, (nw, nh), resample)
    small = hard_alpha(small, threshold)
    if pinholes:
        small = close_pinholes(small)
    return small


def tight_bbox(alpha_mask):
    ys, xs = np.nonzero(alpha_mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


# ---------------------------------------------------------------------------
# palettes
# ---------------------------------------------------------------------------

_HEX_LINE = re.compile(r"^\s*#?([0-9a-fA-F]{6})(?![0-9a-fA-F])")


def parse_palette_text(text):
    """Hex colours, one per line. Accepts 'ff00aa', '#ff00aa', 'ff00aa name',
    GIMP .gpl rows ('255 0 170 name'); skips '//', ';' and '# comment' lines."""
    cols = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith(";"):
            continue
        m = _HEX_LINE.match(s)
        if m:
            cols.append(hex_to_rgb(m.group(1)))
            continue
        g = re.match(r"^\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\b", s)
        if g and all(int(v) <= 255 for v in g.groups()):
            cols.append(tuple(int(v) for v in g.groups()))
    return cols


def load_palette(path):
    """Palette from .hex/.txt/.gpl (one colour per line) or an image (every
    unique opaque colour). Returns an (N, 3) uint8 array, order kept."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".hex", ".txt", ".gpl", ""):
        with open(path, encoding="utf-8") as fh:
            cols = parse_palette_text(fh.read())
        if not cols:
            raise SystemExit("no colours found in %s" % path)
        return np.array(list(dict.fromkeys(cols)), dtype=np.uint8)
    if ext == ".json":
        import json
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        cols = data.get("colors") or data.get("colours") or data
        return np.array([hex_to_rgb(c) for c in cols], dtype=np.uint8)
    img = Image.open(path).convert("RGBA")
    arr = np.array(img).reshape(-1, 4)
    arr = arr[arr[:, 3] > 0][:, :3]
    _, idx = np.unique(arr, axis=0, return_index=True)
    return arr[np.sort(idx)].astype(np.uint8)


def quantize_to_palette(rgb, palette):
    """Snap every pixel to its nearest palette entry (luma-weighted distance:
    tracks perception better than raw RGB and keeps shading ramps apart)."""
    rgb = np.asarray(rgb)
    w = np.array([0.30, 0.59, 0.11], dtype=np.float32)
    px = rgb.reshape(-1, 3).astype(np.float32) * w
    pal = np.asarray(palette).astype(np.float32) * w
    out = np.empty(px.shape[0], dtype=np.int32)
    chunk = 65536
    for i in range(0, px.shape[0], chunk):
        block = px[i:i + chunk]
        d = ((block[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        out[i:i + chunk] = d.argmin(axis=1)
    return np.asarray(palette, np.uint8)[out].reshape(rgb.shape)


def lock_rgba(arr, palette):
    """Snap the opaque pixels of an RGBA array to the palette."""
    out = np.array(arr, np.uint8, copy=True)
    m = out[..., 3] > 0
    if m.any():
        out[m, :3] = quantize_to_palette(out[m, :3], palette)
    return out


def off_palette(arr, palette):
    """Count opaque pixels whose colour is not exactly a palette colour."""
    a = np.asarray(arr)
    px = a[a[..., 3] > 0][:, :3] if a.shape[-1] == 4 else a.reshape(-1, 3)
    if not len(px):
        return 0
    pal = {tuple(int(v) for v in c) for c in np.asarray(palette)}
    uniq, counts = np.unique(px, axis=0, return_counts=True)
    return int(sum(c for u, c in zip(uniq, counts) if tuple(int(v) for v in u) not in pal))


def colour_count(arr):
    a = np.asarray(arr)
    px = a[a[..., 3] > 0][:, :3] if a.shape[-1] == 4 else a.reshape(-1, 3)
    return int(len(np.unique(px, axis=0))) if len(px) else 0


# ---------------------------------------------------------------------------
# forge.json (optional)
# ---------------------------------------------------------------------------

def forge_cfg():
    """forge.json settings when present, else {} -- never fails."""
    try:
        from forge_config import load
        cfg = load()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

def self_test():
    # keying: off-key magenta and its darker shadow are background; brown is not
    px = np.array([[[252, 52, 252], [150, 40, 150], [120, 80, 50], [0, 255, 0]]], np.uint8)
    m = key_candidates(px, "magenta")[0]
    assert m.tolist() == [True, True, False, False], m
    assert key_candidates(px, "green")[0].tolist() == [False, False, False, True]
    # border-connected keying keeps an enclosed pink shirt, keys an enclosed pure pocket
    img = np.zeros((20, 30, 3), np.uint8)
    img[:] = (255, 0, 255)
    img[3:17, 3:13] = (20, 20, 20)            # outlined figure 1
    img[6:14, 6:10] = (255, 105, 180)         # pink shirt inside it
    img[3:17, 16:27] = (20, 20, 20)           # outlined figure 2
    img[7:12, 19:24] = (250, 5, 250)          # a pocket of pure key inside it
    bg, info = background_mask(img, "auto")
    assert info["key"] == "magenta", info
    assert not bg[10, 8], "pink shirt was keyed"
    assert bg[9, 21] and info["enclosed_keyed"] == 1, info
    bg_keep, _ = background_mask(img, "magenta", enclosed="keep")
    assert not bg_keep[9, 21]
    # despill: purple shadow -> neutral, brown untouched, masked pixels untouched
    d = despill(np.array([[[64, 48, 64], [120, 80, 50]]], np.uint8), "magenta")[0]
    assert abs(d[0][0] - d[0][2]) < 2 and d[0][0] <= 50 and tuple(d[1]) == (120, 80, 50), d
    dg = despill(np.array([[[90, 140, 100], [200, 120, 150]]], np.uint8), "green")[0]
    assert dg[0][1] <= 100 and tuple(dg[1]) == (200, 120, 150), dg
    # place / fit
    spr = np.zeros((10, 4, 4), np.uint8)
    spr[..., 3] = 255
    can, over = place(spr, (8, 12), "bottom")
    assert over == 0 and can[11, 3, 3] == 255 and can[0, 3, 3] == 0
    # palettes
    pal = np.array(parse_palette_text("#ff0000 red\n00ff00\n// skip\n# a comment\n0 0 255 blue\n"), np.uint8)
    assert pal.tolist() == [[255, 0, 0], [0, 255, 0], [0, 0, 255]], pal
    q = quantize_to_palette(np.array([[[250, 10, 10], [10, 10, 200]]], np.uint8), pal)
    assert q.tolist() == [[[255, 0, 0], [0, 0, 255]]]
    # pinholes
    a = np.zeros((7, 7, 4), np.uint8)
    a[1:6, 1:6] = (100, 50, 20, 255)
    a[3, 3, 3] = 0
    assert close_pinholes(a)[3, 3, 3] == 255
    print("forge_image self-test OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="run the built-in checks")
    a = ap.parse_args()
    if a.self_test:
        self_test()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
