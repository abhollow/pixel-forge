#!/usr/bin/env python3
"""Measure an animation cycle before wiring it: are the frames different
enough, and is any frame ghosting or clipped?

    python check_cycle.py art/sprites/enemy_walk_f*.png
    python check_cycle.py art/sprites/dw_0*.png --json --strict

Why: the model repeats poses. Asked for "two drawn poses", it often returns
two frames under 12% different -- at game size the cycle just shimmers. The
fix is to discard the duplicate and MIRROR pose A (a near-duplicate around 6%
typically becomes 15%+ different). The ghost
check compares opaque-pixel counts: a frame more than ~25% off frame 0 is
usually a ghost double, a clipped limb or a frame cut from the wrong box.

Reports, for the frames in the order given (the cycle wraps last -> first):
  * % of pixels that differ between neighbouring frames, over the union of
    their opaque pixels (alpha differs, or RGB differs by more than --tol);
    the widest and narrowest step in the cycle;
  * opaque-pixel count per frame and its drift from frame 0;
  * flags: steps under --min-diff (default 12%) as near-duplicates, with the
    difference you would get by using frame 0 mirrored instead; drift over
    --max-drift (default 25%) as ghosting/clipping.
Every frame must be the same size (cut them with one shared box).
Exit code 1 with --strict when anything is flagged.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image


def load(paths):
    frames = [np.array(Image.open(p).convert("RGBA")) for p in paths]
    sizes = {f.shape[:2] for f in frames}
    if len(sizes) > 1:
        raise SystemExit("frames differ in size %s -- cut them with one shared box (slice_sheet.py --shared-box)"
                         % sorted((s[1], s[0]) for s in sizes))
    return frames


def diff_pct(a, b, tol=24):
    oa, ob = a[..., 3] > 0, b[..., 3] > 0
    union = oa | ob
    if not union.any():
        return 0.0
    rgb = np.abs(a[..., :3].astype(int) - b[..., :3].astype(int)).sum(-1) > tol
    differ = (oa != ob) | (oa & ob & rgb)
    return 100.0 * differ.sum() / union.sum()


def analyse(frames, tol=24, min_diff=12.0, max_drift=25.0):
    n = len(frames)
    counts = [int((f[..., 3] > 0).sum()) for f in frames]
    steps = []
    for i in range(n):
        j = (i + 1) % n
        if n == 2 and i == 1:
            break                      # a 2-frame cycle has one distinct step
        steps.append({"from": i, "to": j, "diff": round(diff_pct(frames[i], frames[j], tol), 1)})
    mirror0 = frames[0][:, ::-1]
    flags = []
    for s in steps:
        if s["diff"] < min_diff:
            # replace the later frame (or, on the wrap step, the earlier one)
            # with frame 0 mirrored, and measure it against its neighbour
            repl = s["to"] if s["to"] != 0 else s["from"]
            neighbour = s["from"] if repl == s["to"] else s["to"]
            alt = round(diff_pct(frames[neighbour], mirror0, tol), 1)
            s["mirror0_diff"] = alt
            flags.append("frames %d->%d only %.1f%% different (near-duplicate); frame 0 mirrored would differ "
                         "by %.1f%% -- consider replacing frame %d with a mirror of frame 0"
                         % (s["from"], s["to"], s["diff"], alt, repl))
    drift = []
    for i, c in enumerate(counts):
        d = 0.0 if counts[0] == 0 else 100.0 * (c - counts[0]) / counts[0]
        drift.append(round(d, 1))
        if abs(d) > max_drift:
            flags.append("frame %d has %+.0f%% opaque pixels vs frame 0 (ghosting, clipping or a wrong box?)" % (i, d))
    diffs = [s["diff"] for s in steps] or [0.0]
    return {"frames": n, "size": [int(frames[0].shape[1]), int(frames[0].shape[0])],
            "steps": steps, "widest_step": max(diffs), "narrowest_step": min(diffs),
            "opaque": counts, "drift_pct": drift, "flags": flags}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frames", nargs="+", help="frame PNGs in cycle order (globs are expanded and sorted)")
    ap.add_argument("--tol", type=int, default=24, help="summed RGB difference that counts as a changed pixel")
    ap.add_argument("--min-diff", type=float, default=12.0, help="flag steps less different than this %%")
    ap.add_argument("--max-drift", type=float, default=25.0, help="flag opaque-count drift beyond this %%")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is flagged")
    a = ap.parse_args()
    paths = []
    for f in a.frames:
        paths += sorted(glob.glob(f)) if any(ch in f for ch in "*?[") else [f]
    if len(paths) < 2:
        raise SystemExit("need at least two frames")
    r = analyse(load(paths), a.tol, a.min_diff, a.max_drift)
    r["files"] = [os.path.basename(p) for p in paths]
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print("%d frames, %dx%d" % (r["frames"], r["size"][0], r["size"][1]))
        for s in r["steps"]:
            print("  %s -> %s  %5.1f%% different" % (r["files"][s["from"]], r["files"][s["to"]], s["diff"]))
        print("  widest step %.1f%%, narrowest %.1f%%" % (r["widest_step"], r["narrowest_step"]))
        for f, c, d in zip(r["files"], r["opaque"], r["drift_pct"]):
            print("  %-28s %6d opaque px  %+6.1f%% vs frame 0" % (f, c, d))
        for fl in r["flags"]:
            print("FLAG:", fl)
        if not r["flags"]:
            print("OK: no near-duplicates, no ghosting")
    if a.strict and r["flags"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
