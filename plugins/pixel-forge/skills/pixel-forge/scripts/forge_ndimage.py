#!/usr/bin/env python3
"""The few scipy.ndimage calls the forge scripts need, with a numpy fallback.

    python forge_ndimage.py --self-test

Not a tool you run on art -- the cutters, keyers and feathering scripts import
it. Why it exists: scipy is a large install and is missing on plenty of
machines (and in some sandboxes), but connected-component labelling, dilation
and a distance-into-mask are the heart of sprite cutting. With scipy present
every function below calls scipy.ndimage; without it a vectorised numpy
version runs instead (slower, same results for labelling and morphology; the
distance fallback is city-block, which is all a dithered feather needs).

Set PIXEL_FORGE_NO_SCIPY=1 to force the numpy path (the tests do, so both
paths stay honest).
"""
import argparse
import os
import sys

import numpy as np

HAVE_SCIPY = None      # decided on first use: importing scipy costs ~0.3 s per run
_ndi = None


def _scipy():
    """True when scipy.ndimage is usable (imported lazily, once)."""
    global HAVE_SCIPY, _ndi
    if HAVE_SCIPY is None:
        HAVE_SCIPY = False
        if os.environ.get("PIXEL_FORGE_NO_SCIPY", "") in ("", "0"):
            try:
                from scipy import ndimage
                _ndi = ndimage
                HAVE_SCIPY = True
            except Exception:  # scipy missing or broken: numpy fallback
                _ndi = None
    return HAVE_SCIPY


# ---------------------------------------------------------------------------
# morphology (4-neighbour cross, scipy's default structuring element)
# ---------------------------------------------------------------------------

def _grow4(m):
    out = m.copy()
    out[1:, :] |= m[:-1, :]
    out[:-1, :] |= m[1:, :]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _shrink4(m, border):
    out = m.copy()
    out[1:, :] &= m[:-1, :]
    out[:-1, :] &= m[1:, :]
    out[:, 1:] &= m[:, :-1]
    out[:, :-1] &= m[:, 1:]
    if not border:            # outside the image counts as background
        out[0, :] = False
        out[-1, :] = False
        out[:, 0] = False
        out[:, -1] = False
    return out


def binary_dilation(mask, iterations=1):
    """Grow a mask by `iterations` pixels (diamond-shaped, like scipy)."""
    m = np.asarray(mask, bool)
    if iterations <= 0:
        return m.copy()
    if _scipy():
        return _ndi.binary_dilation(m, iterations=iterations)
    for _ in range(iterations):
        m = _grow4(m)
    return m


def binary_erosion(mask, iterations=1):
    """Shrink a mask; pixels touching the image edge erode (scipy default)."""
    m = np.asarray(mask, bool)
    if iterations <= 0:
        return m.copy()
    if _scipy():
        return _ndi.binary_erosion(m, iterations=iterations)
    for _ in range(iterations):
        m = _shrink4(m, border=False)
    return m


def binary_opening(mask, iterations=1):
    """Erode then dilate: removes hairlines and single-pixel bridges."""
    return binary_dilation(binary_erosion(mask, iterations), iterations)


# ---------------------------------------------------------------------------
# connected components
# ---------------------------------------------------------------------------

def _label_numpy(m, eight):
    """Run-length union-find, vectorised: rows -> runs -> merged runs."""
    h, w = m.shape
    lab = np.zeros((h, w), np.int32)
    if not m.any():
        return lab, 0
    pad = np.zeros((h, w + 2), np.int8)
    pad[:, 1:-1] = m
    d = np.diff(pad, axis=1)
    sy, sx = np.nonzero(d == 1)      # run starts, raster order
    _, ex = np.nonzero(d == -1)      # run ends (exclusive), same order
    nruns = len(sx)
    first = np.searchsorted(sy, np.arange(h + 2))
    slack = 1 if eight else 0
    ea, eb = [], []
    for y in range(h - 1):
        a0, a1, b1 = first[y], first[y + 1], first[y + 2]
        if a0 == a1 or a1 == b1:
            continue
        As, Ae = sx[a0:a1], ex[a0:a1]
        Bs, Be = sx[a1:b1], ex[a1:b1]
        lo = np.searchsorted(Be + slack, As, side="right")
        hi = np.searchsorted(Bs, Ae + slack, side="left")
        cnt = np.maximum(hi - lo, 0)
        tot = int(cnt.sum())
        if not tot:
            continue
        ai = np.repeat(np.arange(len(As)), cnt)
        before = np.cumsum(cnt) - cnt
        bi = lo[ai] + np.arange(tot) - before[ai]
        ea.append(a0 + ai)
        eb.append(a1 + bi)
    parent = np.arange(nruns)
    if ea:
        ea = np.concatenate(ea)
        eb = np.concatenate(eb)
        while True:
            ra, rb = parent[ea], parent[eb]
            low = np.minimum(ra, rb)
            newp = parent.copy()
            np.minimum.at(newp, ra, low)
            np.minimum.at(newp, rb, low)
            while True:                       # pointer jumping to the roots
                nxt = newp[newp]
                if np.array_equal(nxt, newp):
                    break
                newp = nxt
            if np.array_equal(newp, parent):
                break
            parent = newp
    _, inv = np.unique(parent, return_inverse=True)
    run_label = (inv + 1).astype(np.int32)
    lab.flat[np.flatnonzero(m)] = np.repeat(run_label, ex - sx)
    return lab, int(run_label.max())


def label(mask, connectivity=4):
    """Label connected regions -> (labels int32 array, count).

    connectivity 4 (scipy's default) or 8 (diagonal neighbours join too).
    Labels follow raster order of each region's first pixel, as scipy's do.
    """
    m = np.asarray(mask, bool)
    if _scipy():
        st = np.ones((3, 3), bool) if connectivity == 8 else None
        lab, n = _ndi.label(m, structure=st)
        return lab.astype(np.int32), int(n)
    return _label_numpy(m, connectivity == 8)


def sizes(labels, n):
    """Pixel count of each label 1..n (numpy array of length n)."""
    return np.bincount(np.asarray(labels).ravel(), minlength=n + 1)[1:n + 1]


def find_objects(labels, n=None):
    """Bounding slices (rows, cols) of each label 1..n; None for empty labels."""
    labels = np.asarray(labels)
    if n is None:
        n = int(labels.max()) if labels.size else 0
    if _scipy():
        objs = list(_ndi.find_objects(labels, max_label=n))
        return objs + [None] * (n - len(objs))
    ys, xs = np.nonzero(labels)
    lab = labels[ys, xs]
    big = np.iinfo(np.int64).max
    y0 = np.full(n + 1, big, np.int64)
    x0 = np.full(n + 1, big, np.int64)
    y1 = np.full(n + 1, -1, np.int64)
    x1 = np.full(n + 1, -1, np.int64)
    np.minimum.at(y0, lab, ys)
    np.minimum.at(x0, lab, xs)
    np.maximum.at(y1, lab, ys)
    np.maximum.at(x1, lab, xs)
    out = []
    for i in range(1, n + 1):
        if y1[i] < 0:
            out.append(None)
        else:
            out.append((slice(int(y0[i]), int(y1[i]) + 1), slice(int(x0[i]), int(x1[i]) + 1)))
    return out


def keep_border_connected(mask, connectivity=4):
    """The parts of `mask` that touch the image border (the real background)."""
    lab, n = label(mask, connectivity)
    if n == 0:
        return np.zeros_like(np.asarray(mask, bool))
    edge = np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]])
    outside = np.unique(edge[edge > 0])
    return np.isin(lab, outside)


def drop_small(mask, min_px, connectivity=4):
    """Remove connected pieces smaller than min_px pixels."""
    if min_px <= 1:
        return np.asarray(mask, bool).copy()
    lab, n = label(mask, connectivity)
    if n == 0:
        return np.asarray(mask, bool).copy()
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes(lab, n) >= min_px
    return keep[lab]


# ---------------------------------------------------------------------------
# distance and blur
# ---------------------------------------------------------------------------

def distance_inside(mask, limit=None):
    """Distance from each True pixel to the nearest False pixel (0 outside).

    scipy: exact Euclidean. Fallback: city-block, counted by erosion up to
    `limit` (default 64) -- plenty for a feather a few dozen pixels wide.
    The image border does NOT count as outside (matches scipy's edt).
    """
    m = np.asarray(mask, bool)
    if _scipy():
        d = _ndi.distance_transform_edt(m).astype(np.float32)
        return np.minimum(d, limit) if limit else d
    cap = int(limit or 64)
    d = np.zeros(m.shape, np.float32)
    cur = m.copy()
    for _ in range(cap):
        if not cur.any():
            break
        d[cur] += 1.0
        cur = _shrink4(cur, border=True)
    return d


def gaussian_filter(arr, sigma):
    """Separable Gaussian blur (reflect at the edges, like scipy)."""
    a = np.asarray(arr, np.float32)
    if sigma <= 0:
        return a.copy()
    if _scipy():
        return _ndi.gaussian_filter(a, sigma).astype(np.float32)
    r = int(4.0 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    out = a
    for axis in (0, 1):
        pw = [(0, 0)] * out.ndim
        pw[axis] = (r, r)
        p = np.pad(out, pw, mode="symmetric")
        acc = np.zeros_like(out)
        n = out.shape[axis]
        for i, kv in enumerate(k):
            sl = [slice(None)] * out.ndim
            sl[axis] = slice(i, i + n)
            acc += kv * p[tuple(sl)]
        out = acc
    return out


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

def _same_partition(a, b):
    """True when two label images split the pixels the same way."""
    if a.shape != b.shape or ((a > 0) != (b > 0)).any():
        return False
    pairs = np.unique(np.stack([a[a > 0], b[b > 0]]), axis=1)
    return len(np.unique(pairs[0])) == pairs.shape[1] == len(np.unique(pairs[1]))


def self_test():
    global HAVE_SCIPY
    real = _scipy()
    m = np.zeros((9, 9), bool)
    m[1:3, 1:3] = True
    m[3, 3] = True            # touches the first blob only diagonally
    m[6:8, 5:9] = True
    try:
        for mode in ([True, False] if real else [False]):
            HAVE_SCIPY = mode
            name = "scipy" if mode else "numpy"
            lab4, n4 = label(m, 4)
            lab8, n8 = label(m, 8)
            assert n4 == 3 and n8 == 2, (name, n4, n8)
            assert list(sizes(lab4, n4)) == [4, 1, 8], (name, sizes(lab4, n4))
            objs = find_objects(lab4, n4)
            assert objs[2] == (slice(6, 8), slice(5, 9)), (name, objs)
            assert binary_dilation(m, 1).sum() > m.sum()
            assert binary_erosion(m, 1).sum() < m.sum()
            border = keep_border_connected(m)
            assert border[6, 8] and not border[1, 1], name
            assert drop_small(m, 2).sum() == 12, name
            d = distance_inside(np.ones((7, 7), bool) & ~np.eye(7, dtype=bool))
            assert d[0, 6] >= 1 and d[3, 3] == 0, name
            g = gaussian_filter(np.pad(np.ones((3, 3)), 5), 1.0)
            assert abs(g.sum() - 9.0) < 0.05 and g.max() < 1.0, (name, g.sum())
        if real:
            rng = np.random.default_rng(5)
            for trial in range(4):
                r = rng.random((120, 160)) < (0.35 + 0.1 * trial)
                for conn in (4, 8):
                    HAVE_SCIPY = True
                    a, na = label(r, conn)
                    HAVE_SCIPY = False
                    b, nb = label(r, conn)
                    assert na == nb and _same_partition(a, b), ("label mismatch", conn, na, nb)
                    assert (a == b).all(), "label order differs from scipy"
                HAVE_SCIPY = True
                da, ea = binary_dilation(r, 3), binary_erosion(r, 2)
                HAVE_SCIPY = False
                assert (binary_dilation(r, 3) == da).all() and (binary_erosion(r, 2) == ea).all()
                HAVE_SCIPY = True
                ga = gaussian_filter(r.astype(np.float32), 1.5)
                HAVE_SCIPY = False
                assert np.abs(gaussian_filter(r.astype(np.float32), 1.5) - ga).max() < 1e-3
    finally:
        HAVE_SCIPY = real
    print("forge_ndimage self-test OK (%s)" % ("scipy present: numpy fallback checked against it"
                                               if real else "numpy fallback only"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="check the numpy fallback (against scipy if present)")
    a = ap.parse_args()
    if a.self_test:
        self_test()
    else:
        print("scipy.ndimage: %s" % ("in use" if _scipy() else "not available - numpy fallback in use"))


if __name__ == "__main__":
    main()
