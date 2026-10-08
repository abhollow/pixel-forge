#!/usr/bin/env python3
"""Download Magnific picks to raw_art/<batch>/, build a review sheet per label,
and record every file in the docs/assets.md ledger.

    python fetch_art.py raw_art/b07.txt --batch b07 --prompt-ref "docs/art-prompts.md#b07"
    python fetch_art.py - --batch b08 < urls.txt

Input lines (a file, or - for stdin), '#' comments allowed:

    label variant url [creation_id] [model]
    hero  a  https://pikaso.cdnpk.net/private/production/.../render.png?token=exp=...  aB3dE5fG7h  imagen-nano-banana-2

-> raw_art/<batch>/<label>_<variant>.png, raw_art/<batch>/sheet_<label>.jpg
   (a labelled 2x2 contact sheet to look at with Read), and one row per file
   in docs/assets.md under "## Raw batches" (created if missing):
   | Date | Batch | Label | Variant | File | Creation id | Model | Prompt ref |

SIGNED URLS EXPIRE. creations_wait / creations_register_download return links
with an exp= token: download them in the same turn you get them. The creation
id is the durable handle -- creations_get re-issues a fresh URL -- so always
pass it; the ledger is what lets raw_art/ (gigabytes over a project) stay
out of git. This is the only forge script that touches the network. In the
claude.ai / Cowork sandbox the CDN is blocked (403): the user downloads picks
and uploads them instead.

Retries with backoff; a 403 is reported as "expired or blocked"; files already
present are skipped (--force re-downloads); every file is checked to open as
an image. Also drops a .gdignore into raw_art/ so Godot never imports it.
"""
import argparse
import datetime
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

HEADER = "| Date | Batch | Label | Variant | File | Creation id | Model | Prompt ref |"
SEP = "|---|---|---|---|---|---|---|---|"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def parse_lines(text):
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 3:
            raise SystemExit("line %d: need 'label variant url [creation_id] [model]': %r" % (n, s[:80]))
        label, variant, url = parts[0], parts[1], parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        model = parts[4] if len(parts) > 4 else ""
        rows.append({"label": label, "variant": variant, "url": url, "creation_id": cid, "model": model})
    return rows


def ext_of(url):
    path = urllib.parse.urlparse(url).path.lower()
    for e in IMAGE_EXT:
        if path.endswith(e):
            return ".jpg" if e == ".jpeg" else e
    return ".png"


def download(url, dest, retries=3, timeout=60):
    tmp = dest + ".part"
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pixel-forge-fetch/2"})
            with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as fh:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    fh.write(chunk)
            os.replace(tmp, dest)
            return None
        except urllib.error.HTTPError as e:
            last = "HTTP %d" % e.code
            if e.code in (401, 403, 404, 410):
                if os.path.exists(tmp):
                    os.remove(tmp)
                return last + (" -- signed URL expired or blocked; re-issue it with creations_get "
                               "(or, in the claude.ai sandbox, ask the user to download it)" if e.code in (401, 403, 410) else "")
        except Exception as e:  # network blips, timeouts
            last = "%s: %s" % (type(e).__name__, e)
        if os.path.exists(tmp):
            os.remove(tmp)
        if attempt < retries:
            time.sleep(min(8, 2 ** attempt * 0.5))
    return last


def check_image(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.size
    except Exception as e:
        return "not an image (%s)" % e


def append_ledger(ledger, rows):
    """Append rows to the '## Raw batches' table, creating it if needed.
    Rows whose file is already in the ledger are skipped. Returns count added."""
    text = ""
    if os.path.exists(ledger):
        with open(ledger, encoding="utf-8") as fh:
            text = fh.read()
    lines = text.splitlines()
    have = set()
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 5:
                have.add(cells[4].strip("`"))
    new = []
    for r in rows:
        if r["file"] in have:
            continue
        new.append("| %s | %s | %s | %s | `%s` | %s | %s | %s |" % (
            r["date"], r["batch"], r["label"], r["variant"], r["file"],
            r["creation_id"] or "-", r["model"] or "-", r["prompt_ref"] or "-"))
    if not new:
        return 0
    sec = next((i for i, ln in enumerate(lines) if ln.strip().lower().startswith("## raw batches")), None)
    if sec is None:
        if not lines:
            lines = ["# Asset ledger", ""]
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["## Raw batches", "", "(`fetch_art.py` appends rows here.)", "", HEADER, SEP] + new
    else:
        end = next((i for i in range(sec + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        hdr = next((i for i in range(sec + 1, end) if lines[i].startswith("|")), None)
        if hdr is None:
            insert = end
            while insert > sec + 1 and not lines[insert - 1].strip():
                insert -= 1
            block = ["", HEADER, SEP] + new
            lines[insert:insert] = block
        else:
            last = hdr
            while last + 1 < end and lines[last + 1].startswith("|"):
                last += 1
            lines[last + 1:last + 1] = new
    os.makedirs(os.path.dirname(os.path.abspath(ledger)), exist_ok=True)
    with open(ledger, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(new)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list", help="file of 'label variant url [creation_id] [model]' lines, or - for stdin")
    ap.add_argument("--batch", required=True, help="batch folder name, e.g. b07")
    ap.add_argument("--root", default=".", help="game root (default: current folder)")
    ap.add_argument("--raw-dir", default="raw_art", help="raw art folder under the root")
    ap.add_argument("--ledger", default="docs/assets.md", help="asset ledger under the root")
    ap.add_argument("--prompt-ref", default="", help="where the prompt is recorded, e.g. docs/art-prompts.md#b07")
    ap.add_argument("--model", default="", help="model for lines that do not name one")
    ap.add_argument("--no-ledger", action="store_true")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--force", action="store_true", help="download even when the file exists")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()

    text = sys.stdin.read() if a.list == "-" else open(a.list, encoding="utf-8").read()
    rows = parse_lines(text)
    if not rows:
        raise SystemExit("no download lines found")
    print("NOTE: signed URLs expire -- if any fail with 403, re-issue them (creations_get <creation id>).")
    raw = os.path.join(a.root, a.raw_dir)
    out_dir = os.path.join(raw, a.batch)
    os.makedirs(out_dir, exist_ok=True)
    gd = os.path.join(raw, ".gdignore")
    if not os.path.exists(gd):
        open(gd, "w").close()
    groups = OrderedDict()
    ledger_rows, failed = [], []
    today = datetime.date.today().isoformat()
    for r in rows:
        name = "%s_%s%s" % (r["label"], r["variant"], ext_of(r["url"]))
        dest = os.path.join(out_dir, name)
        if os.path.exists(dest) and not a.force:
            status = "exists"
        else:
            err = download(r["url"], dest, a.retries, a.timeout)
            if err:
                failed.append((name, err))
                print("  FAIL %-28s %s" % (name, err))
                continue
            status = "downloaded"
        size = check_image(dest)
        if isinstance(size, str):
            failed.append((name, size))
            print("  FAIL %-28s %s" % (name, size))
            os.remove(dest)
            continue
        print("  %-10s %-28s %dx%d" % (status, name, size[0], size[1]))
        groups.setdefault(r["label"], []).append((r["variant"], dest))
        rel = os.path.relpath(dest, a.root).replace(os.sep, "/")
        ledger_rows.append({"date": today, "batch": a.batch, "label": r["label"], "variant": r["variant"],
                            "file": rel, "creation_id": r["creation_id"], "model": r["model"] or a.model,
                            "prompt_ref": a.prompt_ref})
    if not a.no_sheet and groups:
        from contact_sheet import grid_sheet
        for label, items in groups.items():
            sheet = os.path.join(out_dir, "sheet_%s.jpg" % label)
            grid_sheet([p for _, p in items], [v for v, _ in items], sheet, cols=2, tile=480)
            print("  sheet %s (%d) -> %s" % (label, len(items), sheet))
    if not a.no_ledger and ledger_rows:
        n = append_ledger(os.path.join(a.root, a.ledger), ledger_rows)
        print("ledger: %d row(s) added to %s" % (n, a.ledger))
        missing = [r["file"] for r in ledger_rows if not r["creation_id"]]
        if missing:
            print("WARNING: %d file(s) have no creation id -- add them to the ledger, or the originals "
                  "cannot be re-fetched once raw_art/ is gone" % len(missing))
    if failed:
        print("%d failed:" % len(failed))
        for n, e in failed:
            print("  ", n, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
