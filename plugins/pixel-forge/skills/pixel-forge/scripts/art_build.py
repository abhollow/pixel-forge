#!/usr/bin/env python3
"""Rebuild every game sprite, background plate and HD set from raw art, from ONE
declarative manifest (art/manifest.json). Incremental: only entries whose raw
art, settings, palette or forge scripts changed are rebuilt.

    python art_build.py --init                 # write a starter art/manifest.json
    python art_build.py                        # build what changed
    python art_build.py --only home,wanim --force
    python art_build.py --list                 # what is stale, what is up to date
    python art_build.py --dry-run              # print the commands, run nothing

Why: with every sprite's sizes in one place (a line per sheet), "all sprites
x1.25, re-cut from raw" and then "buildings back to their original size" are
one-line changes. A build kept as a shell script goes wrong in two ways: a
second build (the HD set) ends up PARSING the script, and both point at a
hard-coded tool path that breaks on any other machine. Here the manifest is
data, the 1x and HD builds read the same entries, and the forge scripts are
called by path next to this file with the current Python.

Manifest (paths relative to the game root = the folder holding forge.json):

    {
      "raw_dir": "raw_art",              sheets are looked up here first
      "out_dir": "art/sprites",          1x sprites
      "hd_dir": "art/sprites_hd",        density 2 (3 -> art/sprites_hd_3x, or "hd_dirs": {"3": ...})
      "work_dir": "raw_art/.build",      intermediate cuts + the hash cache
      "palette": null,                   default palette for every entry (null = no lock)
      "post_options": {"soften_edges": {"ground": "5f7a4c", "alpha": 150, "toward": 0.35}},
      "entries": [
        {"sheet": "b7/homes_a.png", "cutter": "blob", "prefix": "home",
         "sizes": ["105x82", "105x75", "105x78"], "palette": "art/palette_build.hex", "hd": [2]},
        {"sheet": "b1/trees_b.png", "cutter": "profile", "prefix": "treeb", "sizes": "50x104,60x88",
         "despill": true, "clean_fringe": true, "post": ["soften_edges"], "hd": [2]},
        {"sheet": "b10/wolf.png", "cutter": "profile", "prefix": "wanim", "sizes": ["54x30"],
         "rows": 2, "shared_box": true, "anchor": "bottom"},
        {"cutter": "boxes", "boxes": "art/boxes/icons.json", "palette": "art/palette_icons.hex"},
        {"cutter": "plate", "sheet": "b2/meadow_a.png", "out": "art/backgrounds/meadow.png",
         "target": 960, "stretch": "2560x1440", "palette": "art/palette_world.hex"}
      ]
    }

Entry keys:
  cutter      blob | profile (slice_sheet.py modes) | boxes (cut_boxes.py) |
              plate (pixelize.py: one whole painting, e.g. a background)
  sheet, prefix, sizes, key (magenta|green|auto|corner), despill, clean_fringe,
  shared_box, anchor, rows, gap, row_gap, grow, speck, expect, scale_by,
  feature_px, scale     -> slice_sheet.py flags (sizes/feature_px/scale x density)
  boxes       the JSON box file for cutter boxes
  out, target plate output and its LONG side (x density)
  palette     lock to this palette (false = no lock even if the manifest has one)
  post        ["soften_edges", {"remap_reserved": {"reserved": "8c2519", "to": "2d251d"}}, "recolor"]
              options merge over post_options; keys become --flags
  stretch     "WxH": resize the sheet first (a reimagine came back at another size)
  recolor     {...}: recolor.py options applied to the sheet before cutting
  hd          [2] or [2, 3]: also cut again FROM RAW at that density; checked to be
              within 2 px of density x the 1x size. Flames, icons, HUD: leave out --
              chunky pixels are part of the look.
  hd_post     false to skip post passes on the HD set
  args        extra CLI args for the cutter (escape hatch)
  enabled     false to skip

Ends by reminding you to re-import:  now run: godot --headless --path . --import
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SCRIPT_DEPS = ["slice_sheet.py", "cut_boxes.py", "pixelize.py", "soften_edges.py", "remap_reserved.py",
               "recolor.py", "forge_image.py", "forge_ndimage.py", "despill.py"]

EXAMPLE = {
    "_doc": "Pixel Forge art manifest. Run: python tools/forge/art_build.py  (see --help for every key)",
    "raw_dir": "raw_art",
    "out_dir": "art/sprites",
    "hd_dir": "art/sprites_hd",
    "work_dir": "raw_art/.build",
    "palette": None,
    "post_options": {"soften_edges": {"ground": "5f7a4c", "alpha": 150, "toward": 0.35}},
    "entries": [
        {"sheet": "b01/folk_a.png", "cutter": "profile", "prefix": "folk", "sizes": ["10x15", "9x15", "10x15"],
         "key": "magenta", "despill": True, "clean_fringe": True},
        {"sheet": "b07/homes_a.png", "cutter": "blob", "prefix": "home", "sizes": ["105x82", "105x75", "70x68"],
         "palette": "art/palette_build.hex", "hd": [2]},
        {"sheet": "b10/wolf_a.png", "cutter": "profile", "prefix": "wolf_run", "sizes": ["54x30"], "rows": 1,
         "shared_box": True, "anchor": "bottom", "clean_fringe": True},
        {"cutter": "boxes", "boxes": "art/boxes/icons.json", "enabled": False},
        {"cutter": "plate", "sheet": "b02/meadow_a.png", "out": "art/backgrounds/meadow.png", "target": 960,
         "enabled": False}
    ]
}


class BuildError(Exception):
    pass


# ---------------------------------------------------------------------------
# paths, hashing
# ---------------------------------------------------------------------------

def find_root(start="."):
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, "forge.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.abspath(start)
        d = parent


class Ctx:
    def __init__(self, root, m, args):
        self.root, self.m, self.a = root, m, args
        self.raw = self.p(m.get("raw_dir", "raw_art"))
        self.work = self.p(m.get("work_dir", "raw_art/.build"))
        self._hashes = {}

    def p(self, path):
        return path if os.path.isabs(path) else os.path.normpath(os.path.join(self.root, path))

    def sheet(self, rel):
        for c in (os.path.join(self.raw, rel), self.p(rel)):
            if os.path.exists(c):
                return c
        raise BuildError("sheet not found: %s (looked in %s and the game root)" % (rel, self.raw))

    def out_dir(self, e, d):
        if d == 1:
            return self.p(e.get("out_dir") or self.m.get("out_dir", "art/sprites"))
        hd = self.m.get("hd_dirs", {}).get(str(d))
        if hd:
            return self.p(hd)
        base = self.m.get("hd_dir", "art/sprites_hd")
        return self.p(base if d == 2 else "%s_%dx" % (base, d))

    def fhash(self, path):
        st = os.stat(path)
        k = (path, st.st_size, st.st_mtime_ns)
        if k not in self._hashes:
            h = hashlib.sha1()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            self._hashes[k] = h.hexdigest()
        return self._hashes[k]


def entry_key(e):
    return e.get("name") or e.get("prefix") or e.get("out") or e.get("boxes") or e.get("sheet") or "?"


_OUTPUT_KEYS = {"out", "out_dir", "name", "prefix", "_doc", "_comment"}


def _files_in(obj, ctx, acc):
    """Every existing INPUT file named anywhere in obj (outputs excluded)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in _OUTPUT_KEYS:
                _files_in(v, ctx, acc)
    elif isinstance(obj, list):
        for v in obj:
            _files_in(v, ctx, acc)
    elif isinstance(obj, str) and len(obj) < 400:
        for c in (os.path.join(ctx.raw, obj), ctx.p(obj)):
            if os.path.isfile(c):
                acc.add(c)
                break


def entry_hash(e, ctx, densities):
    files = set()
    _files_in(e, ctx, files)
    post = {n: ctx.m.get("post_options", {}).get(n) for n in post_names(e)}
    _files_in(post, ctx, files)
    pal = e.get("palette", ctx.m.get("palette"))
    _files_in(pal, ctx, files)
    if e.get("cutter") == "boxes" and e.get("boxes") and os.path.exists(ctx.p(e["boxes"])):
        try:
            with open(ctx.p(e["boxes"]), encoding="utf-8") as fh:
                bx = json.load(fh)
            base = os.path.dirname(ctx.p(e["boxes"]))
            items = bx.get("items", {})
            for it in (items.values() if isinstance(items, dict) else items):
                for c in (os.path.join(base, it.get("sheet", "")), ctx.p(it.get("sheet", ""))):
                    if it.get("sheet") and os.path.isfile(c):
                        files.add(c)
                        break
        except (ValueError, OSError):
            pass
    blob = {"entry": e, "post": post, "palette": pal, "densities": densities,
            "dirs": [ctx.m.get(k) for k in ("out_dir", "hd_dir", "hd_dirs", "raw_dir")],
            "files": {os.path.relpath(f, ctx.root): ctx.fhash(f) for f in sorted(files)},
            "scripts": {s: ctx.fhash(os.path.join(HERE, s)) for s in SCRIPT_DEPS if os.path.exists(os.path.join(HERE, s))}}
    return hashlib.sha1(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()


def post_names(e):
    out = []
    for p in e.get("post", []):
        out.append(p if isinstance(p, str) else next(iter(p)))
    return out


# ---------------------------------------------------------------------------
# running the forge scripts
# ---------------------------------------------------------------------------

def run(ctx, script, args):
    cmd = [sys.executable, os.path.join(HERE, script)] + [str(x) for x in args]
    if ctx.a.dry_run or ctx.a.verbose:
        print("    $", " ".join('"%s"' % c if " " in c else c for c in cmd[1:]))
    if ctx.a.dry_run:
        return ""
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ctx.root)
    if ctx.a.verbose and r.stdout.strip():
        print("      " + r.stdout.strip().replace("\n", "\n      "))
    if r.returncode != 0:
        tail = (r.stdout + "\n" + r.stderr).strip().splitlines()[-12:]
        raise BuildError("%s failed:\n      %s" % (script, "\n      ".join(tail)))
    return r.stdout


def flag_args(opts):
    args = []
    for k, v in opts.items():
        if v is None or v is False:
            continue
        flag = "--" + k.replace("_", "-")
        if v is True:
            args.append(flag)
        elif isinstance(v, (list, tuple)):
            args += [flag, ",".join(str(x) for x in v)]
        else:
            args += [flag, str(v)]
    return args


def prepare_sheet(ctx, e, work):
    """Apply stretch / recolor to the sheet into the work dir; returns the path to cut."""
    src = ctx.sheet(e["sheet"])
    if not (e.get("stretch") or e.get("recolor")):
        return src
    os.makedirs(work, exist_ok=True)
    cur = src
    if e.get("stretch"):
        from PIL import Image
        import forge_image as fi
        w, h = fi.parse_size(e["stretch"])
        dst = os.path.join(work, "stretched.png")
        if not ctx.a.dry_run:
            im = Image.open(cur)
            im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB").resize(
                (w, h), Image.Resampling.LANCZOS).save(dst)
        cur = dst
    if e.get("recolor"):
        dst = os.path.join(work, "recolored.png")
        run(ctx, "recolor.py", [cur, "-o", dst] + flag_args(e["recolor"] if isinstance(e["recolor"], dict) else {}))
        cur = dst
    return cur


def scaled(sizes, d):
    import forge_image as fi
    return ",".join("%dx%d" % (w * d, h * d) for w, h in fi.parse_sizes(sizes))


def build_density(ctx, e, d):
    """Cut one entry at one density; returns the list of output files."""
    key = entry_key(e)
    cutter = e.get("cutter", "profile")
    work = os.path.join(ctx.work, "".join(c if c.isalnum() or c in "-_" else "_" for c in key), "d%d" % d)
    if not ctx.a.dry_run:
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work, exist_ok=True)
    pal = e.get("palette", ctx.m.get("palette"))
    pal = ctx.p(pal) if pal else None
    out_dir = ctx.out_dir(e, d)
    report = os.path.join(work, "report.json")
    if cutter == "plate":
        src = prepare_sheet(ctx, e, work)
        out = ctx.p(e["out"])
        if d != 1:
            od = os.path.dirname(out)
            out = os.path.join(od + ("_hd" if d == 2 else "_%dx" % d), os.path.basename(out))
        args = [src, "-o", out, "--target", int(e["target"]) * d, "--no-pad"]
        if pal:
            args += ["--palette", pal]
        run(ctx, "pixelize.py", args + e.get("args", []))
        return [out]
    cut_dir = os.path.join(work, "cut")
    if cutter in ("blob", "profile"):
        src = prepare_sheet(ctx, e, work)
        args = [src, "--mode", cutter, "--prefix", e["prefix"], "--sizes", scaled(e["sizes"], d),
                "--out-dir", cut_dir, "--key", e.get("key", "magenta"), "--report", report]
        for k in ("despill", "clean_fringe", "shared_box", "keep_enclosed"):
            if e.get(k):
                args.append("--" + k.replace("_", "-"))
        for k in ("anchor", "rows", "gap", "row_gap", "grow", "speck", "expect", "scale_by", "resample",
                  "key_tol", "despill_strength"):
            if e.get(k) is not None:
                args += ["--" + k.replace("_", "-"), e[k]]
        for k in ("feature_px", "scale"):
            if e.get(k) is not None:
                args += ["--" + k.replace("_", "-"), float(e[k]) * d]
        run(ctx, "slice_sheet.py", args + e.get("args", []))
    elif cutter == "boxes":
        run(ctx, "cut_boxes.py", [ctx.p(e["boxes"]), "--out-dir", cut_dir, "--density", d, "--report", report]
            + e.get("args", []))
    else:
        raise BuildError("unknown cutter %r (blob, profile, boxes, plate)" % cutter)
    if ctx.a.dry_run:
        return []
    with open(report, encoding="utf-8") as fh:
        cuts = [s["file"] for s in json.load(fh)["sprites"]]
    os.makedirs(out_dir, exist_ok=True)
    outs = [os.path.join(out_dir, os.path.basename(c)) for c in cuts]
    if pal:
        run(ctx, "pixelize.py", cuts + ["-O", out_dir, "--keep-size", "--palette", pal])
    else:
        for c, o in zip(cuts, outs):
            shutil.copyfile(c, o)
    return outs


def post_passes(ctx, e, outs, d):
    if not outs or (d != 1 and e.get("hd_post") is False):
        return
    for p in e.get("post", []):
        name, opts = (p, {}) if isinstance(p, str) else next(iter(p.items()))
        merged = dict(ctx.m.get("post_options", {}).get(name, {}))
        merged.update(opts or {})
        if name == "soften_edges":
            run(ctx, "soften_edges.py", outs + flag_args(merged))
        elif name == "remap_reserved":
            run(ctx, "remap_reserved.py", outs + flag_args(merged))
        elif name == "recolor":
            for o in outs:
                run(ctx, "recolor.py", [o, "-o", o] + flag_args(merged))
        else:
            raise BuildError("unknown post pass %r (soften_edges, remap_reserved, recolor)" % name)


def check_hd(outs1, outs_d, d):
    from PIL import Image
    off = []
    base = {os.path.basename(o): o for o in outs1}
    for o in outs_d:
        b = base.get(os.path.basename(o))
        if not b or not os.path.exists(b) or not os.path.exists(o):
            continue
        w1, h1 = Image.open(b).size
        w2, h2 = Image.open(o).size
        if abs(w2 - d * w1) > 2 or abs(h2 - d * h1) > 2:
            off.append("%s %dx%d vs %dx%d" % (os.path.basename(o), w2, h2, w1, h1))
    return off


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="art/manifest.json", help="relative to the game root")
    ap.add_argument("--root", default=None, help="game root (default: folder of forge.json, else here)")
    ap.add_argument("--only", default=None, help="comma list of entry keys (prefix / out / boxes)")
    ap.add_argument("--force", action="store_true", help="rebuild even when nothing changed")
    ap.add_argument("--no-hd", action="store_true", help="skip the density sets")
    ap.add_argument("--list", action="store_true", help="show each entry and whether it is up to date")
    ap.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    ap.add_argument("--keep-going", action="store_true", help="carry on after a failing entry")
    ap.add_argument("--verbose", action="store_true", help="show every command and its output")
    ap.add_argument("--init", action="store_true", help="write a starter manifest and stop")
    a = ap.parse_args()

    root = os.path.abspath(a.root) if a.root else find_root()
    mpath = os.path.normpath(a.manifest if os.path.isabs(a.manifest) else os.path.join(root, a.manifest))
    if a.init:
        if os.path.exists(mpath):
            raise SystemExit("%s exists" % mpath)
        os.makedirs(os.path.dirname(mpath), exist_ok=True)
        with open(mpath, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(EXAMPLE, fh, indent=2)
            fh.write("\n")
        print("wrote", mpath, "- edit the entries, then run art_build.py")
        return
    if not os.path.exists(mpath):
        raise SystemExit("no manifest at %s (art_build.py --init writes a starter)" % mpath)
    with open(mpath, encoding="utf-8") as fh:
        m = json.load(fh)
    ctx = Ctx(root, m, a)
    cache_path = os.path.join(ctx.work, "build_cache.json")
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cache = json.load(fh)
        except ValueError:
            cache = {}
    only = set(a.only.split(",")) if a.only else None
    entries = [e for e in m.get("entries", []) if e.get("enabled", True) is not False]
    keys = [entry_key(e) for e in entries]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        raise SystemExit("duplicate entry keys %s -- give each a unique prefix / out / name" % sorted(dup))

    built = skipped = failed = 0
    n_out = 0
    hd_off = []
    for e in entries:
        key = entry_key(e)
        if only and key not in only:
            continue
        dens = [1] + ([] if a.no_hd else [int(x) for x in e.get("hd", []) if int(x) != 1])
        try:
            h = entry_hash(e, ctx, dens)
        except BuildError as ex:
            print("  %-16s ERROR %s" % (key, ex))
            failed += 1
            if not a.keep_going:
                break
            continue
        prev = cache.get(key, {})
        fresh = prev.get("hash") == h and all(os.path.exists(o) for o in prev.get("outputs", []))
        if a.list:
            print("  %-16s %-8s %s%s" % (key, e.get("cutter", "profile"), "up to date" if fresh else "STALE",
                                         "  hd %s" % dens[1:] if len(dens) > 1 else ""))
            continue
        if fresh and not a.force:
            skipped += 1
            continue
        print("  %-16s %s%s" % (key, e.get("cutter", "profile"), "  + hd %s" % dens[1:] if len(dens) > 1 else ""))
        try:
            if not a.dry_run:
                for o in prev.get("outputs", []):          # remove last build's files (sizes list may have shrunk)
                    if os.path.exists(o):
                        os.remove(o)
            all_outs, per = [], {}
            for d in dens:
                outs = build_density(ctx, e, d)
                post_passes(ctx, e, outs, d)
                per[d] = outs
                all_outs += outs
            for d in dens[1:]:
                hd_off += check_hd(per[1], per[d], d)
            if not a.dry_run:
                cache[key] = {"hash": h, "outputs": all_outs}
            built += 1
            n_out += len(all_outs)
        except BuildError as ex:
            print("  %-16s FAILED: %s" % (key, ex))
            failed += 1
            cache.pop(key, None)
            if not a.keep_going:
                break
    if a.list:
        return
    if not a.dry_run:
        os.makedirs(ctx.work, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=1)
        gd = os.path.join(ctx.raw, ".gdignore")
        if os.path.isdir(ctx.raw) and not os.path.exists(gd):
            open(gd, "w").close()
    print("built %d entr%s (%d files), %d unchanged%s" % (built, "y" if built == 1 else "ies", n_out, skipped,
                                                       ", %d FAILED" % failed if failed else ""))
    if hd_off:
        print("WARNING: HD sprites not density x the 1x size (within 2 px):")
        for o in hd_off:
            print("   ", o)
    if built and not a.dry_run:
        print("now run: godot --headless --path . --import")
        print('        (with the console exe: "$GODOT" --headless --path . --import)')
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
