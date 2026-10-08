#!/usr/bin/env python3
"""Turn a generated mascot portrait on a flat green background into a small transparent pixel-art PNG.

BOX-resizes to the pixel grid, flood-fills the green key from the border, de-spills green fringe near the
edge, quantizes to a few colours without dither and makes the key transparent. Needs Pillow.
Set CONFIG.mascot.size in the page to the grid you choose.
"""
# Usage: python3 make_mascot.py raw_pick.png mascot.png [grid=112] [colours=36]
import sys
from collections import deque
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
grid = int(sys.argv[3]) if len(sys.argv) > 3 else 112
colours = int(sys.argv[4]) if len(sys.argv) > 4 else 36

im = Image.open(src).convert("RGB").resize((grid, grid), Image.BOX)   # 1. BOX resize to the pixel grid
px, n = im.load(), grid
key = lambda c: c[1] > 140 and c[1] > c[0] + 50 and c[1] > c[2] + 50   # bright green background
bg, q = set(), deque([(x, y) for x in range(n) for y in (0, n - 1)] + [(x, y) for y in range(n) for x in (0, n - 1)])
while q:                                                                # 2. flood-fill the key from the border
    x, y = q.popleft()
    if (x, y) in bg or not (0 <= x < n and 0 <= y < n) or not key(px[x, y]):
        continue
    bg.add((x, y)); q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
near = {(x + dx, y + dy) for x, y in bg for dx in range(-2, 3) for dy in range(-2, 3)} - bg
for x, y in near:                                                       # 3. fringe: de-spill green near the edge
    if 0 <= x < n and 0 <= y < n:
        r, g, b = px[x, y]
        if g > max(r, b) + 8:
            px[x, y] = (r, max(r, b), b) if r + g + b > 330 else px[x, y]
fill = next(px[x, y] for y in range(n) for x in range(n) if (x, y) not in bg)
for x, y in bg:
    px[x, y] = fill                                                     # keep the key out of the palette
pal = im.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGBA")
qa = pal.load()                                                         # 4. ~36 colours, no dither
for x, y in bg:
    qa[x, y] = (0, 0, 0, 0)                                             # 5. transparent background
pal.save(out)
print(out, pal.size, len(pal.getcolors(4096)) - 1, "colours + transparent")
