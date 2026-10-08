#!/usr/bin/env python3
"""new_godot_project.py - scaffold a Godot 4 pixel-art game that is crisp,
tested and versioned from the first minute.

    python new_godot_project.py ~/Games/my-game --name "My Game" \\
        --width 360 --height 640 --scale 2 --aspect keep --perspective top-down

Refuses to touch a folder that already has a project.godot. Files that already
exist (say a docs/concept.md written during the concept stage) are kept, never
overwritten. Needs only the Python standard library.

WHY EACH project.godot SETTING (the rationale lives here and in the docs, never
in project.godot: the editor rewrites that file, strips comments and drops keys
that hold default values - a `#` comment there can swallow the key after it):
  config/features          the Godot version the game is built with: --godot-version,
                           else what $GODOT --version reports, else 4.3. forge.json
                           keeps the full version; CI downloads exactly that one.
  run/max_fps=60           battery; physics runs at 60 Hz anyway. Bots and
                           benchmarks pass --max-fps 0.
  config/quit_on_go_back=false   Android back opens the pause screen instead of
                           killing the app.
  viewport W x H           the design resolution all art and layout use.
  window override          desktop dev window only: the largest whole multiple
                           that fits a laptop screen.
  stretch canvas_items     the canvas scales to the device, text and UI stay sharp.
  stretch aspect           keep (letterbox; painted, fixed layouts) or expand
                           (more world on odd screens; scrolling worlds).
  handheld/orientation     portrait or landscape.
  importer_defaults        lossless, no mipmaps, no alpha-border fix - otherwise
                           Godot compresses and mipmaps sprites into blur.
  emulate_touch_from_mouse a desktop mouse drives touch-only controls (joysticks).
  emulate_mouse_from_touch phones turn touches into mouse events: one input path.
  gl_compatibility         widest mobile support; plenty for 2D.
  default_texture_filter=0 NEAREST: the pixel-art setting.
  snap 2D transforms/vertices   sprites never land on half pixels (no shimmer).
No [autoload]: Session is a static class. (A global "Game" autoload tends to
assume one game's economy - credits, upgrades - and gets deleted; a game can
ship with no autoloads at all.)

WHAT ELSE IT WRITES
  scenes/main.tscn, scripts/main.gd   grey-box with the tuning block, systems
                           registry, run lifecycle and art slots (assets/godot)
  scripts/session.gd       settings, audio buses, atomic versioned save
  scripts/pause.gd         auto-pause + save on focus loss
  default_bus_layout.tres  SFX, Music, Ambience, MusicTrack (under Music)
  tools/smoke_test.gd, capture.gd, watch.gd, run_tests.sh
  tools/forge/             a vendored copy of the forge scripts + VERSION, so a
                           clone or CI works without the plugin
  forge.json               the screen settings every forge tool reads
  art/sprites/             art slots load from here
  raw_art/.gdignore        Magnific originals: never imported, never exported
  docs/.gdignore, docs/screens/.gdignore, docs/screens/keep/   review renders
                           (gitignored except keep/)
  everything under assets/project/  (CLAUDE.md, docs/*.md, .gitignore,
                           .gitattributes, CI workflow, icon) with {{TOKENS}} filled
  CLAUDE.local.md          machine paths (gitignored), when Godot was found
  git init -b main         unless --no-git or already inside a repository
                           (nothing is committed)
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)   # `python -I` leaves the script's folder off sys.path
sys.dont_write_bytecode = True   # no __pycache__ in the plugin or in a game's tools/forge
import forge_config  # noqa: E402

SKILL_DIR = os.path.dirname(HERE)
GODOT_TEMPLATES = os.path.join(SKILL_DIR, "assets", "godot")
PROJECT_TEMPLATES = os.path.join(SKILL_DIR, "assets", "project")

# assets/godot file -> place in the new game
GODOT_FILES = [
    ("main.tscn", "scenes/main.tscn"),
    ("main.gd", "scripts/main.gd"),
    ("session.gd", "scripts/session.gd"),
    ("pause.gd", "scripts/pause.gd"),
    ("default_bus_layout.tres", "default_bus_layout.tres"),
    ("smoke_test.gd", "tools/smoke_test.gd"),
    ("capture.gd", "tools/capture.gd"),
    ("watch.gd", "tools/watch.gd"),
    ("run_tests.sh", "tools/run_tests.sh"),
]

# empty marker files
MARKERS = [
    "art/sprites/.gitkeep",
    "raw_art/.gdignore",
    "docs/.gdignore",
    "docs/screens/.gdignore",
    "docs/screens/keep/.gitkeep",
]

SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".icns", ".wav", ".ogg",
              ".mp3", ".ttf", ".otf", ".woff", ".woff2", ".zip", ".res", ".scn", ".pdf", ".apk", ".aab"}

PROJECT_GODOT = """\
config_version=5

[application]

config/name="{name}"
run/main_scene="res://scenes/main.tscn"
config/quit_on_go_back=false
config/features=PackedStringArray("{features}", "GL Compatibility")
run/max_fps=60
config/icon="res://icon.svg"

[display]

window/size/viewport_width={width}
window/size/viewport_height={height}
{window_override}window/stretch/mode="canvas_items"
window/stretch/aspect="{aspect}"
window/handheld/orientation={orientation}

[importer_defaults]

texture={{
"compress/mode": 0,
"detect_3d/compress_to": 0,
"mipmaps/generate": false,
"process/fix_alpha_border": false
}}

[input_devices]

pointing/emulate_touch_from_mouse=true
pointing/emulate_mouse_from_touch=true

[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
textures/canvas_textures/default_texture_filter=0
2d/snap/snap_2d_transforms_to_pixel=true
2d/snap/snap_2d_vertices_to_pixel=true
"""

LOCAL_MD = """\
# CLAUDE.local.md

Local notes for this machine (gitignored; never commit).

## Machine paths

Written by new_godot_project.py on {date}. `python tools/forge/doctor.py --write-local CLAUDE.local.md`
replaces this section with a full check (gh, git, ffmpeg too).

```sh
GODOT="{godot}"
PYTHON="{python}"
```

In Bash: `export GODOT="{godot}"`, then `sh tools/run_tests.sh`.
"""


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "game"


def find_godot():
    """The Godot executable to ask for its version: $GODOT, PATH, then the
    usual install places. Console builds first on Windows (the plain exe
    prints nothing)."""
    env = os.environ.get("GODOT")
    if env and os.path.isfile(env):
        return env
    for n in ("godot", "godot4", "Godot"):
        p = shutil.which(n)
        if p:
            return p
    pats = []
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pats += [os.path.join(la, "Microsoft", "WinGet", "Packages", "GodotEngine*", "Godot*_console.exe"),
                 os.path.join(pf, "Godot*", "Godot*_console.exe"),
                 os.path.join(pf, "Godot*_console.exe"),
                 os.path.join(os.path.expanduser("~"), "scoop", "apps", "godot*", "current", "*console.exe"),
                 os.path.join(la, "Microsoft", "WinGet", "Packages", "GodotEngine*", "Godot*.exe"),
                 os.path.join(pf, "Godot*.exe")]
    elif sys.platform == "darwin":
        pats += ["/Applications/Godot*.app/Contents/MacOS/Godot"]
    else:
        pats += [os.path.expanduser("~/.local/bin/godot*"), "/usr/local/bin/godot*", "/opt/godot*/godot*"]
    for pat in pats:
        hits = sorted(glob.glob(pat), reverse=True)   # newest version first, by name
        if hits:
            return hits[0]
    return None


def godot_version_of(exe):
    """'4.7.2' from `exe --version` (or from the file name), else None."""
    out = ""
    try:
        r = subprocess.run([exe, "--headless", "--version"], capture_output=True, text=True, timeout=30)
        out = (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError):
        pass
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?\.(?:stable|rc|beta|dev)", out) or \
        re.search(r"Godot_v(\d+)\.(\d+)(?:\.(\d+))?", os.path.basename(exe))
    if not m:
        return None
    return ".".join(g for g in m.groups() if g is not None)


def major_minor(v):
    return ".".join(str(v).split(".")[:2])


def is_binary(path, data):
    if os.path.splitext(path)[1].lower() in BINARY_EXT:
        return True
    if b"\0" in data[:8192]:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def substitute(text, tokens):
    for k, v in tokens.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


class Writer:
    """Writes into the new game, never over an existing file, and keeps a log."""

    def __init__(self, root, tokens):
        self.root = root
        self.tokens = tokens
        self.created = []
        self.kept = []
        self.unknown = set()

    def _dest(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def text(self, rel, content, executable=False):
        dst = self._dest(rel)
        if os.path.exists(dst):
            self.kept.append(rel)
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        content = content.replace("\r\n", "\n")
        with open(dst, "wb") as f:
            f.write(content.encode("utf-8"))
        if executable:
            os.chmod(dst, 0o755)
        self.created.append(rel)
        return True

    def copy(self, src, rel, fill=True):
        """Copy one file; text files get {{TOKENS}} filled unless fill=False."""
        with open(src, "rb") as f:
            data = f.read()
        if not fill or is_binary(src, data):
            dst = self._dest(rel)
            if os.path.exists(dst):
                self.kept.append(rel)
                return False
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            self.created.append(rel)
            return True
        content = substitute(data.decode("utf-8"), self.tokens)
        self.unknown.update(re.findall(r"\{\{[A-Z][A-Z0-9_]*\}\}", content))
        return self.text(rel, content, executable=rel.endswith(".sh"))

    def tree(self, src_root, rel_root=""):
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for fn in sorted(filenames):
                if fn in SKIP_FILES or fn.endswith(".pyc"):
                    continue
                src = os.path.join(dirpath, fn)
                rel = os.path.relpath(src, src_root).replace(os.sep, "/")
                self.copy(src, (rel_root + "/" + rel) if rel_root else rel)


def inside_git_repo(path):
    try:
        r = subprocess.run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and r.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def git_init(root):
    if not shutil.which("git"):
        return "git not found: skipped `git init` (install git, then run `git init -b main`)"
    parent = os.path.dirname(os.path.abspath(root))
    if inside_git_repo(parent):
        return "already inside a git repository: skipped `git init`"
    r = subprocess.run(["git", "init", "-b", "main"], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:   # git older than 2.28
        r = subprocess.run(["git", "init"], cwd=root, capture_output=True, text=True)
        if r.returncode != 0:
            return "git init failed: " + (r.stderr or r.stdout).strip()
        subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=root, capture_output=True)
    return "git repository initialised on branch main (nothing committed)"


def window_override(w, h):
    """The largest whole multiple of the viewport that fits a 1600x900 area."""
    k = max(1, min(1600 // w, 900 // h))
    return (w * k, h * k) if k > 1 else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", nargs="?", help="project folder to create (may exist, but not with a project.godot)")
    p.add_argument("--name", default="Pixel Game", help="the game's name")
    p.add_argument("--width", type=int, default=360, help="viewport width in screen px (default 360)")
    p.add_argument("--height", type=int, default=640, help="viewport height in screen px (default 640)")
    p.add_argument("--scale", type=int, default=2,
                   help="screen pixels per art pixel: 2 = chunky (art drawn at half), 1 = native detail")
    p.add_argument("--aspect", choices=forge_config.ASPECTS, default="keep",
                   help="keep for painted fixed scenes, expand for tile maps and scrolling worlds")
    p.add_argument("--orientation", choices=forge_config.ORIENTATIONS,
                   help="default: landscape when width > height, else portrait")
    p.add_argument("--cell", type=int, default=32, help="sprite/tile unit in art px (default 32)")
    p.add_argument("--perspective", choices=forge_config.PERSPECTIVES,
                   help="camera view the art is drawn for; leave out until the bible decides")
    p.add_argument("--godot-version",
                   help="e.g. 4.7.2 (default: from $GODOT --version if Godot is found, else 4.3)")
    p.add_argument("--no-git", action="store_true", help="skip `git init`")
    p.add_argument("--self-test", action="store_true",
                   help="scaffold into a temp folder, check the result, delete it (no Godot needed)")
    a = p.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.path:
        p.error("the project folder is required")

    if a.width <= 0 or a.height <= 0 or a.scale < 1 or a.cell < 1:
        p.error("width, height, scale and cell must be positive")
    root = os.path.abspath(os.path.expanduser(a.path))
    if os.path.exists(os.path.join(root, "project.godot")):
        print(f"refusing: {os.path.join(root, 'project.godot')} already exists - this folder is already a Godot project")
        return 1
    for need in (GODOT_TEMPLATES, PROJECT_TEMPLATES):
        if not os.path.isdir(need):
            print(f"templates missing: {need} (is this a complete Pixel Forge skill folder?)")
            return 1
    os.makedirs(root, exist_ok=True)

    godot_exe = find_godot()
    if a.godot_version:
        gv = a.godot_version.strip()
        if not re.fullmatch(r"\d+\.\d+(\.\d+)?", gv):
            p.error(f"--godot-version wants e.g. 4.3 or 4.7.2, got {gv!r}")
        gv_src = "--godot-version"
    else:
        gv = godot_version_of(godot_exe) if godot_exe else None
        gv_src = f"detected from {godot_exe}" if gv else "default (Godot not found)"
        gv = gv or "4.3"
    if tuple(int(x) for x in gv.split(".")[:2]) < (4, 3):
        print(f"warning: Godot {gv} - the templates target 4.3 and newer")

    orientation = a.orientation or ("landscape" if a.width > a.height else "portrait")
    if a.width % a.scale or a.height % a.scale:
        print(f"warning: {a.width}x{a.height} is not a whole multiple of scale {a.scale}")
    version = forge_config.forge_version()
    today = datetime.date.today().isoformat()
    tokens = {
        "GAME_NAME": a.name, "GAME_SLUG": slugify(a.name), "DATE": today,
        "VIEW_W": a.width, "VIEW_H": a.height, "PIXEL_SCALE": a.scale,
        "ART_W": a.width // a.scale, "ART_H": a.height // a.scale,
        "ASPECT": a.aspect, "ORIENTATION": orientation, "GODOT_VERSION": gv,
        "PERSPECTIVE": a.perspective or "not chosen yet", "CELL": a.cell, "FORGE_VERSION": version,
    }
    w = Writer(root, tokens)

    wo = window_override(a.width, a.height)
    w.text("project.godot", PROJECT_GODOT.format(
        name=a.name.replace("\\", "\\\\").replace('"', '\\"'), features=major_minor(gv),
        width=a.width, height=a.height, aspect=a.aspect,
        orientation=1 if orientation == "portrait" else 0,
        window_override=(f"window/size/window_width_override={wo[0]}\n"
                         f"window/size/window_height_override={wo[1]}\n") if wo else ""))

    for src, rel in GODOT_FILES:
        w.copy(os.path.join(GODOT_TEMPLATES, src), rel)
    w.tree(PROJECT_TEMPLATES)
    for rel in MARKERS:
        w.text(rel, "")

    # vendored forge scripts: a clone or CI works without the plugin
    for src in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        w.copy(src, "tools/forge/" + os.path.basename(src), fill=False)   # verbatim
    w.text("tools/forge/VERSION", version + "\n")

    if os.path.exists(os.path.join(root, "forge.json")):
        w.kept.append("forge.json")
    else:
        forge_config.write(os.path.join(root, "forge.json"), {
            "view_w": a.width, "view_h": a.height, "pixel_scale": a.scale, "aspect": a.aspect,
            "orientation": orientation, "perspective": a.perspective or "", "cell": a.cell,
            "godot_version": gv, "forge_version": version, "palette": "art/palette.hex",
            "tracker": {"id": slugify(a.name), "icon": ""}})
        w.created.append("forge.json")

    if godot_exe:
        w.text("CLAUDE.local.md", LOCAL_MD.format(date=today, godot=godot_exe.replace("\\", "/"),
                                                  python=sys.executable.replace("\\", "/")))

    git_note = "--no-git: skipped `git init`" if a.no_git else git_init(root)

    # --- report ---
    print(f"Created {a.name} in {root}\n")
    groups = {}
    for rel in w.created:
        top = rel.split("/")[0] if "/" in rel else "."
        groups.setdefault(top, []).append(rel)
    for top in sorted(groups):
        items = groups[top]
        if top == "tools" and len(items) > 8:
            forge = [r for r in items if r.startswith("tools/forge/")]
            rest = [r for r in items if not r.startswith("tools/forge/")]
            print("  " + "  ".join(rest))
            print(f"  tools/forge/  ({len(forge)} files: vendored forge scripts, VERSION {version})")
        else:
            print("  " + "  ".join(items))
    if w.kept:
        print("\nKept (already there, not overwritten):\n  " + "  ".join(w.kept))
    if w.unknown:
        print("\nwarning: unfilled placeholders in templates: " + " ".join(sorted(w.unknown)))
    print(f"\nGodot {gv} ({gv_src}) | {a.width}x{a.height} at {a.scale}x (art canvas "
          f"{a.width // a.scale}x{a.height // a.scale}) | aspect {a.aspect} | {orientation} | cell {a.cell}"
          f" | perspective {a.perspective or 'not chosen yet'}")
    print(git_note)
    g = (godot_exe or "<path to the Godot console exe>").replace("\\", "/")
    print(f"""
Next:
  1. cd "{root}"
  2. GODOT="{g}" sh tools/run_tests.sh
       imports, then the smoke test: expect "=== N checks, 0 failed ===" and exit code 0
  3. "{g}" --path . --script res://tools/capture.gd ++ scenario=main,round_end
       a WINDOWED render into docs/screens/ - read the PNGs; grep the output for SHADER ERROR
  4. Fill docs/concept.md and docs/bible.md, then replace the grey-box toy in scripts/main.gd
     with the real loop - keep the tuning block, the systems registry and the art slots.
  5. Commit when the user says so (CI: .github/workflows/smoke-test.yml pins Godot {gv} from forge.json).""")
    return 0


def _self_test():
    """Scaffold a landscape game into a temp folder and check what came out.
    (Running it in Godot - import, smoke test, capture - is the real test;
    this one needs only Python.)"""
    import contextlib
    import io
    import tempfile
    token_re = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "game")
        os.makedirs(os.path.join(root, "docs"))
        with open(os.path.join(root, "docs", "concept.md"), "wb") as f:
            f.write(b"keep me\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([root, "--name", 'Self "Test"', "--width", "320", "--height", "180", "--scale", "1",
                       "--aspect", "expand", "--godot-version", "4.7.2", "--no-git"])
        assert rc == 0, buf.getvalue()
        pg = open(os.path.join(root, "project.godot"), encoding="utf-8").read()
        assert not any(ln.lstrip().startswith((";", "#")) for ln in pg.splitlines()), "comments in project.godot"
        for want in ('config/features=PackedStringArray("4.7", "GL Compatibility")', 'window/stretch/aspect="expand"',
                     "window/handheld/orientation=0", "textures/canvas_textures/default_texture_filter=0",
                     "pointing/emulate_touch_from_mouse=true", 'config/name="Self \\"Test\\""', "run/max_fps=60"):
            assert want in pg, want
        assert "[autoload]" not in pg
        need = [rel for _, rel in GODOT_FILES] + MARKERS + [
            "forge.json", "tools/forge/VERSION", "tools/forge/forge_config.py", ".gitignore", ".gitattributes",
            ".github/workflows/smoke-test.yml"]
        for rel in need:
            assert os.path.exists(os.path.join(root, *rel.split("/"))), rel
        assert open(os.path.join(root, "docs", "concept.md"), "rb").read() == b"keep me\n", "an existing file was overwritten"
        cfg = forge_config.load(root)
        assert (cfg["godot_version"], cfg["view_w"], cfg["orientation"], cfg["aspect"]) == ("4.7.2", 320, "landscape", "expand"), cfg
        for dirpath, _, files in os.walk(root):
            if os.sep + os.path.join("tools", "forge") in dirpath:
                continue
            for fn in files:
                path = os.path.join(dirpath, fn)
                data = open(path, "rb").read()
                if is_binary(path, data):
                    continue
                text = data.decode("utf-8")
                assert not token_re.search(text), f"unfilled token in {path}: {token_re.search(text).group(0)}"
                assert "\r\n" not in text, f"CRLF in {path}"
        for src in glob.glob(os.path.join(HERE, "*.py")):
            dst = os.path.join(root, "tools", "forge", os.path.basename(src))
            assert open(src, "rb").read() == open(dst, "rb").read(), f"vendored copy differs: {dst}"
        with contextlib.redirect_stdout(io.StringIO()):
            assert main([root, "--no-git"]) == 1, "a second scaffold over a project must be refused"
    print("new_godot_project self-test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
