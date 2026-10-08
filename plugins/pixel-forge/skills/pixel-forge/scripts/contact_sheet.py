#!/usr/bin/env python3
"""Decision images: options side by side AT GAME SCALE, on the real
background, next to a sprite the player already knows.

    python contact_sheet.py raw_art/b07/enemy_*.png --game-width 18 \\
        --reference art/sprites/hero_00.png --background art/bg_level1.png \\
        -o docs/screens/keep/enemy_options_at_game_size.png
    python contact_sheet.py --subject raw/enemy --game-width 18 --reference art/sprites/hero_00.png
    python contact_sheet.py raw_art/b03/house_*.png --game-width 105 --frame 240x135 --captions A,B,C,D -o pick.png
    python contact_sheet.py --grid raw_art/b07/*.png -o raw_art/b07/sheet.jpg        # 2x2 batch review

Why: a 1536 px generation tells you nothing about how a 24 px sprite will
read. Choose every piece of art from an "*_options_at_game_size" image --
each option keyed, scaled to its target width, on the real level background
beside the hero sprite and a familiar prop -- and send it to the user with a
recommendation. It is also where problems show (an option whose legs vanish
at 18 px).

Each option is keyed (alpha if it has one, else --key auto: magenta/green
from the border, or the corner colour; --key none keeps the whole image),
trimmed, BOX-downscaled to --game-width (or --game-height) with hard alpha,
placed on a panel (--frame WxH in game px, or just big enough) over the
--background (scaled to cover) or --bg-colour, next to --reference, then the
panel is blown up with NEAREST by --scale so the pixels are visible. Captions
default to the file names (A, B... with --letters).

--subject DIR follows the options-folder convention: DIR/<name>_option_N.png ->
DIR/<name>_options_at_game_size.png.

--grid is the batch-review layout: whole images, --tile px wide, --cols per
row (default 2 -> a 2x2 sheet for four variants), each labelled. fetch_art.py
builds one per label after a download.
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import forge_image as fi  # noqa: E402

BG_DARK = (20, 20, 20)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:          # Pillow < 10.1
        return ImageFont.load_default()


def text_w(draw, text, f):
    try:
        b = draw.textbbox((0, 0), text, font=f)
        return b[2] - b[0]
    except Exception:
        return 7 * len(text)


def prepare(path, key="auto", game_w=None, game_h=None):
    """Key, trim and scale one option to game size -> RGBA array."""
    arr = np.array(Image.open(path).convert("RGBA"))
    if not fi.has_alpha(arr) and key != "none":
        bg, _ = fi.background_mask(arr, key)
        arr[..., 3] = np.where(bg, 0, 255)
    bb = fi.tight_bbox(arr[..., 3] > 0)
    if bb:
        arr = arr[bb[1]:bb[3], bb[0]:bb[2]]
    h, w = arr.shape[:2]
    if game_w:
        k = game_w / w
    elif game_h:
        k = game_h / h
    else:
        k = 1.0
    return fi.scale_sprite(arr, k) if abs(k - 1.0) > 1e-9 else fi.hard_alpha(arr)


def cover(img, size):
    """Scale an RGB background to cover `size`, centre-cropped (BOX)."""
    w, h = img.size
    k = max(size[0] / w, size[1] / h)
    nw, nh = max(size[0], round(w * k)), max(size[1], round(h * k))
    img = img.resize((nw, nh), Image.Resampling.BOX if k < 1 else Image.Resampling.NEAREST)
    x0, y0 = (nw - size[0]) // 2, (nh - size[1]) // 2
    return img.crop((x0, y0, x0 + size[0], y0 + size[1]))


def panel(option, reference, frame, background, bg_colour, anchor, pad=6, gap=4):
    group_w = option.shape[1] + ((gap + reference.shape[1]) if reference is not None else 0)
    group_h = max(option.shape[0], reference.shape[0] if reference is not None else 0)
    if frame:
        pw, ph = frame
    else:
        pw, ph = group_w + 2 * pad, group_h + 2 * pad
    if background is not None:
        base = cover(background, (pw, ph)).convert("RGBA")
    else:
        base = Image.new("RGBA", (pw, ph), bg_colour + (255,))
    x = (pw - group_w) // 2
    ground = ph - pad
    if group_w > pw or group_h > ph:
        print("  WARNING: option + reference (%dx%d) overflow the %dx%d frame" % (group_w, group_h, pw, ph))
    items = [option] + ([reference] if reference is not None else [])
    for it in items:
        y = (ground - it.shape[0]) if anchor == "bottom" else (ph - it.shape[0]) // 2
        im = Image.fromarray(it, "RGBA")
        base.paste(im, (x, y), im)        # hard alpha, so a masked paste == composite
        x += it.shape[1] + gap
    return base.convert("RGB")


def compose(panels, captions, scale, cols, title=None, cap_h=28):
    f = font(16)
    tiles = []
    for p, cap in zip(panels, captions):
        big = p.resize((p.width * scale, p.height * scale), Image.Resampling.NEAREST)
        t = Image.new("RGB", (big.width, big.height + cap_h), BG_DARK)
        t.paste(big, (0, 0))
        d = ImageDraw.Draw(t)
        d.text(((big.width - text_w(d, cap, f)) // 2, big.height + 5), cap, fill=(235, 235, 235), font=f)
        tiles.append(t)
    cols = cols or len(tiles)
    rows = (len(tiles) + cols - 1) // cols
    gut = 10
    cw = max(t.width for t in tiles)
    ch = max(t.height for t in tiles)
    top = 34 if title else 0
    out = Image.new("RGB", (gut + cols * (cw + gut), top + gut + rows * (ch + gut)), BG_DARK)
    if title:
        ImageDraw.Draw(out).text((gut, 9), title, fill=(255, 255, 255), font=font(18))
    for i, t in enumerate(tiles):
        out.paste(t, (gut + (i % cols) * (cw + gut), top + gut + (i // cols) * (ch + gut)))
    return out


def grid_sheet(paths, labels, out_path, cols=2, tile=480):
    """Batch review: whole images, `tile` px wide, labelled, `cols` per row."""
    f = font(16)
    ims = [Image.open(p).convert("RGB") for p in paths]
    tiles = [im.resize((tile, max(1, round(tile * im.height / im.width))), Image.Resampling.BOX
                       if im.width > tile else Image.Resampling.NEAREST) for im in ims]
    th = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tile * cols, th * rows), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, (t, lab) in enumerate(zip(tiles, labels)):
        x, y = (i % cols) * tile, (i // cols) * th
        sheet.paste(t, (x, y))
        w = text_w(d, lab, f) + 12
        d.rectangle([x, y, x + w, y + 22], fill=(0, 0, 0))
        d.text((x + 6, y + 3), lab, fill=(255, 255, 255), font=f)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if out_path.lower().endswith((".jpg", ".jpeg")):
        sheet.save(out_path, quality=88)
    else:
        sheet.save(out_path)
    return out_path


def expand(items):
    out = []
    for f in items:
        out += sorted(glob.glob(f)) if any(c in f for c in "*?[") else [f]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", help="option images (globs ok)")
    ap.add_argument("-o", "--output", help="output PNG/JPG")
    ap.add_argument("--subject", help="folder with <name>_option_N.png (writes <name>_options_at_game_size.png)")
    ap.add_argument("--game-width", type=int, help="each option's width in the game, px")
    ap.add_argument("--game-height", type=int, help="or its height in the game, px")
    ap.add_argument("--reference", help="a game-size sprite to stand beside each option")
    ap.add_argument("--reference-width", type=int, help="scale the reference to this width first")
    ap.add_argument("--background", help="real level background (scaled to cover the panel)")
    ap.add_argument("--bg-colour", "--bg-color", default="5a5a5a", help="panel colour without --background")
    ap.add_argument("--frame", help="panel size in game px, WxH (e.g. a device screen 360x640)")
    ap.add_argument("--anchor", choices=["bottom", "centre"], default="bottom", help="stand on the ground, or centre")
    ap.add_argument("--key", choices=["auto", "magenta", "green", "corner", "none"], default="auto")
    ap.add_argument("--scale", type=int, default=0, help="display upscale (NEAREST); default fits ~360 px tall")
    ap.add_argument("--captions", help="comma list, one per option (default: file names)")
    ap.add_argument("--letters", action="store_true", help="caption A, B, C ... instead of file names")
    ap.add_argument("--title", help="a line of text above the panels")
    ap.add_argument("--cols", type=int, default=0, help="panels per row (default: all in one row)")
    ap.add_argument("--grid", action="store_true", help="batch-review mode: whole images in a labelled grid")
    ap.add_argument("--tile", type=int, default=480, help="--grid: tile width")
    a = ap.parse_args()

    images = expand(a.images)
    if a.subject:
        name = os.path.basename(os.path.normpath(a.subject))
        images = sorted(glob.glob(os.path.join(a.subject, name + "_option_*.*")),
                        key=lambda p: (len(p), p)) or images
        if not a.output:
            a.output = os.path.join(a.subject, name + "_options_at_game_size.png")
    if not images:
        ap.error("no images (give files, globs or --subject DIR)")
    if not a.output:
        ap.error("give -o OUTPUT")
    if a.captions:
        caps = [c.strip() for c in a.captions.split(",")]
        caps = (caps + [""] * len(images))[:len(images)]
    elif a.letters:
        caps = [chr(65 + i) if i < 26 else str(i + 1) for i in range(len(images))]
    else:
        caps = [os.path.splitext(os.path.basename(p))[0] for p in images]

    if a.grid:
        grid_sheet(images, caps, a.output, a.cols or 2, a.tile)
        print("grid of %d -> %s" % (len(images), a.output))
        return

    if not (a.game_width or a.game_height):
        ap.error("give --game-width or --game-height (the size the player will see)")
    ref = None
    if a.reference:
        ref = prepare(a.reference, a.key, a.reference_width) if a.reference_width else \
            fi.hard_alpha(np.array(Image.open(a.reference).convert("RGBA")))
        bb = fi.tight_bbox(ref[..., 3] > 0)
        if bb:
            ref = ref[bb[1]:bb[3], bb[0]:bb[2]]
    bg = Image.open(a.background).convert("RGB") if a.background else None
    frame = fi.parse_size(a.frame) if a.frame else None
    opts = [prepare(p, a.key, a.game_width, a.game_height) for p in images]
    panels = [panel(o, ref, frame, bg, fi.hex_to_rgb(a.bg_colour), a.anchor) for o in opts]
    ph = max(p.height for p in panels)
    scale = a.scale or max(1, min(8, round(360 / ph)))
    out = compose(panels, caps, scale, a.cols, a.title)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    out.save(a.output)
    sizes = ", ".join("%dx%d" % (o.shape[1], o.shape[0]) for o in opts)
    print("%d option(s) at game size [%s], x%d -> %s" % (len(opts), sizes, scale, a.output))


if __name__ == "__main__":
    main()
