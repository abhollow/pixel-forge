#!/usr/bin/env python3
"""Check this machine for everything the Pixel Forge workflow uses, and say
how to install what is missing. Installs nothing.

    python doctor.py                              # human-readable report
    python doctor.py --json                       # machine-readable
    python doctor.py --write-local CLAUDE.local.md   # record the paths for this game

Checks: Python + Pillow + numpy (+ scipy, optional); the Godot CONSOLE
executable and its --version (vs forge.json's godot_version); git, and on
Windows core.longpaths; gh and `gh auth status`; ffmpeg/ffprobe; node;
forge.json; and, inside a game, tools/forge/VERSION against this forge.

Why: a lot of session time goes to the machine, not the game. On Windows
`python` can be the Microsoft Store stub, the GUI Godot exe prints nothing
to a terminal (use Godot_v4.x-stable_win64_console.exe, which winget puts
under %LOCALAPPDATA%\\Microsoft\\WinGet\\Packages and not on PATH), gh.exe is
often not on Git Bash's PATH, and deep scratch folders break git without
core.longpaths. Finding each once and writing it to the game's
CLAUDE.local.md (gitignored) means no session has to rediscover them.

Exit code 1 when a REQUIRED item (Python libs, Godot) is missing.
"""
import argparse
import datetime
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SYSTEM = platform.system()          # Windows / Darwin / Linux
INSTALL = {
    "Windows": {"python": "winget install Python.Python.3.12",
                "pylibs": "python -m pip install Pillow numpy scipy",
                "godot": "winget install GodotEngine.GodotEngine",
                "git": "winget install Git.Git", "gh": "winget install GitHub.cli",
                "ffmpeg": "winget install Gyan.FFmpeg", "node": "winget install OpenJS.NodeJS.LTS",
                "longpaths": "git config --global core.longpaths true", "gh_auth": "gh auth login"},
    "Darwin": {"python": "brew install python", "pylibs": "python3 -m pip install Pillow numpy scipy",
               "godot": "brew install --cask godot", "git": "brew install git", "gh": "brew install gh",
               "ffmpeg": "brew install ffmpeg", "node": "brew install node", "gh_auth": "gh auth login"},
    "Linux": {"python": "sudo apt install python3 python3-pip",
              "pylibs": "python3 -m pip install Pillow numpy scipy",
              "godot": "flatpak install flathub org.godotengine.Godot  (or the godotengine.org download)",
              "git": "sudo apt install git", "gh": "sudo apt install gh  (see cli.github.com)",
              "ffmpeg": "sudo apt install ffmpeg", "node": "sudo apt install nodejs", "gh_auth": "gh auth login"},
}


def hint(key):
    return INSTALL.get(SYSTEM, INSTALL["Linux"]).get(key, "")


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def godot_candidates():
    c = []
    env = os.environ.get("GODOT")
    if env:
        c.append(env)
    for n in ("godot", "godot4", "Godot", "godot.exe"):
        p = shutil.which(n)
        if p:
            c.append(p)
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        pats = [os.path.join(la, "Microsoft", "WinGet", "Packages", "GodotEngine*", "**", "Godot*.exe"),
                os.path.join(pf, "Godot*", "**", "Godot*.exe"), os.path.join(pf, "Godot*.exe"),
                os.path.join(os.path.expanduser("~"), "scoop", "apps", "godot*", "current", "*.exe"),
                os.path.join(pfx, "Steam", "steamapps", "common", "Godot Engine", "*.exe"),
                os.path.join(os.path.expanduser("~"), "Desktop", "Godot*.exe"),
                os.path.join(os.path.expanduser("~"), "Downloads", "Godot*", "Godot*.exe")]
    elif SYSTEM == "Darwin":
        pats = ["/Applications/Godot*.app/Contents/MacOS/Godot",
                os.path.expanduser("~/Applications/Godot*.app/Contents/MacOS/Godot")]
    else:
        pats = [os.path.expanduser("~/.local/bin/godot*"), "/usr/local/bin/godot*", "/usr/bin/godot*",
                "/opt/godot*/godot*", "/var/lib/flatpak/exports/bin/org.godotengine.Godot"]
    for pat in pats:
        c += sorted(glob.glob(pat, recursive=True), reverse=True)
    seen, out = set(), []
    for p in c:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen and os.path.isfile(p):
            seen.add(k)
            out.append(p)
    return out


def godot_version(exe):
    code, out = run([exe, "--headless", "--version"], timeout=40)
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)\.(stable|rc\d*|beta\d*|dev\d*)[^\s]*", out)
    if m:
        return m.group(0).strip()
    m = re.search(r"Godot_v(\d+\.\d+(?:\.\d+)?)", os.path.basename(exe))
    return (m.group(1) + " (from the file name)") if m else None


def pick_godot(cands):
    """Prefer: $GODOT, then console builds (Windows), then the newest by name."""
    if not cands:
        return None
    env = os.environ.get("GODOT")
    if env and os.path.isfile(env):
        return env
    if os.name == "nt":
        con = [c for c in cands if "console" in os.path.basename(c).lower()]
        if con:
            return sorted(con, key=lambda p: os.path.basename(p))[-1]
    return cands[0]


def find_gh():
    p = shutil.which("gh")
    if p:
        return p
    if os.name == "nt":
        for c in (os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "GitHub CLI", "gh.exe"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "GitHub CLI", "gh.exe")):
            if os.path.isfile(c):
                return c
    for c in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
        if os.path.isfile(c):
            return c
    return None


def python_command():
    """The command a shell should use for Python here (the Store stub fails)."""
    for cmd in (["python"], ["py", "-3"], ["python3"]):
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        code, out = run(cmd + ["--version"], timeout=15)
        if code == 0 and out.strip().startswith("Python 3"):
            return " ".join(cmd), out.strip()
    return None, None


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------

def check_all():
    checks, paths = [], {}

    def add(name, status, detail, fix="", required=False):
        checks.append({"name": name, "status": status, "detail": detail, "fix": fix, "required": required})

    # python + libraries
    add("python", "OK", "%s (%s)" % (platform.python_version(), sys.executable), required=True)
    paths["PYTHON_EXE"] = sys.executable
    cmd, ver = python_command()
    if cmd:
        add("python command", "OK", "`%s` -> %s" % (cmd, ver))
        paths["PYTHON"] = cmd
    else:
        add("python command", "WARN", "none of python / py -3 / python3 answers in a shell (Store stub?)",
            hint("python"))
        paths["PYTHON"] = sys.executable
    for mod, req in (("PIL", True), ("numpy", True), ("scipy", False)):
        try:
            m = __import__(mod)
            add("Pillow" if mod == "PIL" else mod, "OK", getattr(m, "__version__", "?"), required=req)
        except Exception:
            add("Pillow" if mod == "PIL" else mod, "MISSING" if req else "WARN",
                "not importable" + ("" if req else " (optional: the scripts fall back to numpy)"),
                hint("pylibs"), required=req)

    # godot
    cands = godot_candidates()
    exe = pick_godot(cands)
    cfg = {}
    try:
        import forge_config
        cfg = forge_config.load()
    except Exception:
        forge_config = None
    if exe:
        v = godot_version(exe)
        detail = "%s -> %s" % (exe, v or "no --version output")
        status = "OK" if v else "WARN"
        fix = ""
        if os.name == "nt" and "console" not in os.path.basename(exe).lower():
            status, fix = "WARN", "use the *_console.exe build (the GUI exe prints nothing to a terminal)"
        want = cfg.get("godot_version") if cfg.get("_path") else None
        if want and v and not v.startswith(str(want)):
            status = "WARN"
            fix = (fix + "; " if fix else "") + "forge.json pins Godot %s" % want
        add("godot", status, detail, fix, required=True)
        paths["GODOT"] = exe
        if len(cands) > 1:
            add("godot (others)", "INFO", "; ".join(c for c in cands if c != exe)[:400])
    else:
        add("godot", "MISSING", "no Godot found ($GODOT, PATH, WinGet, Program Files)", hint("godot"), required=True)

    # git
    git = shutil.which("git")
    if git:
        code, out = run([git, "--version"])
        add("git", "OK", out.strip() or git)
        paths["GIT"] = git
        if os.name == "nt":
            code, lp = run([git, "config", "--get", "core.longpaths"])
            if lp.strip().lower() == "true":
                add("git core.longpaths", "OK", "true")
            else:
                add("git core.longpaths", "WARN", "not set: deep paths (scratch folders, .godot caches) fail",
                    hint("longpaths"))
    else:
        add("git", "MISSING", "not on PATH", hint("git"))

    # gh
    gh = find_gh()
    if gh:
        code, out = run([gh, "--version"])
        add("gh", "OK", "%s (%s)" % (out.strip().splitlines()[0] if out.strip() else "?", gh))
        paths["GH"] = gh
        if not shutil.which("gh"):
            add("gh on PATH", "WARN", "gh.exe exists but is not on this shell's PATH -- call it by full path")
        code, out = run([gh, "auth", "status"])
        acct = re.search(r"Logged in to (\S+)(?: account| as) (\S+)", out)
        if code == 0:
            add("gh auth", "OK", "logged in" + (" to %s as %s" % (acct.group(1), acct.group(2)) if acct else ""))
        else:
            add("gh auth", "WARN", "not logged in (pushes and PRs need it)", hint("gh_auth"))
    else:
        add("gh", "WARN", "not found (optional: PRs, releases)", hint("gh"))

    # ffmpeg
    try:
        from audio_encode import find_ffmpeg, find_ffprobe
        ff, fp = find_ffmpeg(), find_ffprobe()
    except Exception:
        ff = fp = None
    if ff:
        code, out = run([ff, "-version"])
        add("ffmpeg", "OK", "%s (%s)" % ((out.splitlines() or ["?"])[0][:60], ff))
        paths["FFMPEG"] = ff
    else:
        add("ffmpeg", "WARN", "not found (needed for .ogg/.mp3 and audio_encode.py)", hint("ffmpeg"))
    if fp:
        paths["FFPROBE"] = fp
    elif ff:
        add("ffprobe", "WARN", "ffmpeg found but no ffprobe next to it", hint("ffmpeg"))

    # node
    node = shutil.which("node")
    if node:
        code, out = run([node, "--version"])
        add("node", "OK", "%s (%s)" % (out.strip(), node))
    else:
        add("node", "INFO", "not found (optional: web exports, page tooling)", hint("node"))

    # forge.json and the vendored copy
    fj = cfg.get("_path") if cfg else None
    if fj:
        add("forge.json", "OK", "%s (%sx%s @%sx, Godot %s)" % (fj, cfg.get("view_w"), cfg.get("view_h"),
                                                            cfg.get("pixel_scale"), cfg.get("godot_version")))
        root = os.path.dirname(fj)
        vf = os.path.join(root, "tools", "forge", "VERSION")
        mine = forge_config.forge_version() if forge_config else "?"
        if os.path.isfile(vf):
            with open(vf, encoding="utf-8") as fh:
                theirs = fh.read().strip()
            if theirs == mine:
                add("tools/forge", "OK", "vendored forge %s matches" % theirs)
            else:
                add("tools/forge", "WARN", "game vendors forge %s, this forge is %s" % (theirs, mine),
                    "re-vendor: copy this forge's scripts into tools/forge/ and update VERSION")
        else:
            add("tools/forge", "INFO", "no tools/forge/VERSION (game not scaffolded by Pixel Forge?)")
    else:
        add("forge.json", "INFO", "none here or above (fine outside a game; new_godot_project.py writes one)")

    ok = all(c["status"] in ("OK", "INFO", "WARN") or not c["required"] for c in checks) and \
        not any(c["required"] and c["status"] == "MISSING" for c in checks)
    return {"ok": ok, "system": SYSTEM, "checks": checks, "paths": paths}


def write_local(path, paths):
    """Replace (or add) the '## Machine paths' section of CLAUDE.local.md."""
    def q(v):
        return '"%s"' % str(v).replace("\\", "/")
    lines = ["## Machine paths", "",
             "Written by doctor.py on %s. Machine-specific -- keep this file out of git." % datetime.date.today(), "",
             "```sh"]
    for k in ("GODOT", "PYTHON", "PYTHON_EXE", "GH", "GIT", "FFMPEG", "FFPROBE"):
        if k in paths:
            lines.append("%s=%s" % (k, q(paths[k])))
    lines += ["```", "",
              "Shell: `G=\"${GODOT:-godot}\"` then `\"$G\" --headless --path . --import`. "
              "Python: `%s` (fallbacks: `py -3`, `python3`)." % paths.get("PYTHON", "python"), ""]
    section = "\n".join(lines)
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    m = re.search(r"(?ms)^## Machine paths\s*\n.*?(?=^## |\Z)", text)
    if m:
        text = text[:m.start()] + section + ("\n" if text[m.end():].strip() else "") + text[m.end():]
    else:
        if not text.strip():
            text = "# CLAUDE.local.md\n\nLocal notes for this machine (gitignored).\n\n"
        text = text.rstrip("\n") + "\n\n" + section
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text.rstrip("\n") + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--write-local", metavar="PATH",
                    help="write the found paths into PATH's '## Machine paths' section (e.g. CLAUDE.local.md)")
    a = ap.parse_args()
    r = check_all()
    if a.write_local:
        write_local(a.write_local, r["paths"])
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print("Pixel Forge doctor  (%s %s)" % (SYSTEM, platform.release()))
        for c in r["checks"]:
            print("  %-7s %-18s %s" % (c["status"], c["name"], c["detail"]))
            if c["fix"] and c["status"] != "OK":
                print("  %-7s %-18s -> %s" % ("", "", c["fix"]))
        if a.write_local:
            print("wrote the '## Machine paths' section of", a.write_local)
        print("\n%s" % ("ready" if r["ok"] else "NOT READY: install the MISSING items above (nothing was installed)"))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
