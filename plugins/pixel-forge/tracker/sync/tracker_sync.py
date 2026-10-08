#!/usr/bin/env python3
"""Idea to Launch sync helper, cross-platform twin of tracker-sync.ps1.

Prints one JSON object {now, setups[], repos[]} describing every project folder in the projects root:
git push state, commit counts, the last 30 days of activity and the last 14 days of commit messages.
Existing projects are only read, never changed. Needs Python 3.8+ and git on PATH. Pillow is optional
(used by --icons to resize; without it only PNG icons of 192 px or less are copied). gh is used only
when a request asks for a GitHub repo and gh is installed.

  --root DIR          The projects root. Required unless tracker.config.json has "root".
                      Folders starting with "_" or "." are not projects.
  --config FILE       tracker.config.json to read. Default: the one next to this script.
                      { "root": "...", "gitignoreTemplate": "godot|node|generic", "iconsDir": "icons/auto" }
  --req RECORDS       Projects to set up, as one string: records separated by ";;", fields by "|":
                        id|folder|name|create|github|note
                      create 1 = make <root>/<folder> with README.md, .gitignore, git init and a first
                      commit (an existing folder is never touched); 0 = the folder already exists.
                      github private | public | none: create a GitHub repo with gh and push (only for a
                      git repo with commits and no remote yet). note: free text for the README.
  --requests FILE     Same requests as a JSON array of {id, folder, name, note, create, github}.
  --gitignore NAME    .gitignore for new folders: godot | node | generic (default: config, else generic).
  --icons             Also find each project's icon and save a <=192 px copy in the icons folder,
                      reported as icon {file, pixelArt, source}.
  --icons-dir DIR     Where --icons saves copies (default: config iconsDir, else icons/auto next to this script).
  --dry-run           Create nothing: no folders, no commits, no GitHub repos. Setups report what would happen.

Usage: python3 tracker_sync.py [--root DIR] [--req "..."] [--icons] [--dry-run]
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys

try:
    from PIL import Image  # optional
except Exception:  # pragma: no cover - Pillow missing
    Image = None

HERE = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"
SEP = "\\" if IS_WIN else "/"

GITIGNORE = {
    "godot": "# Godot 4\n.godot/\n/android/\n\n# Builds and signing keys\n*.apk\n*.aab\n*.keystore\n\n"
             "# OS and editor files\nThumbs.db\n.DS_Store\n*.tmp\n",
    "node": "node_modules/\ndist/\nbuild/\ncoverage/\n.env\n.env.*\n!.env.example\nnpm-debug.log*\n\n"
            "# OS and editor files\nThumbs.db\n.DS_Store\n*.tmp\n",
    "generic": "# OS and editor files\nThumbs.db\n.DS_Store\n*.tmp\n*.log\n.env\n",
}
FOLDER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\\/-]{0,119}$")
BAD_NAME = "Folder names can use letters, numbers, spaces, hyphens and underscores (60 characters at most)."
ICON_NAME_RE = re.compile(r"^(icon|app[_-]?icon|logo)([-_ ]?\d+)?$|^icon[-_]\d+$|-icon-\d+$", re.I)
ICON_SKIP_DIR_RE = re.compile(r"\.godot|\.git|node_modules|raw.*|videos?|capture", re.I)
ICON_EXTS = (".png", ".jpg", ".webp")


def fail(msg):
    sys.stderr.write("tracker-sync: " + msg + "\n")
    sys.exit(2)


def now_iso():
    return dt.datetime.now().astimezone().isoformat()


# ---------------------------------------------------------------- git
def git(path, *args):
    """Run git in path. Returns the output lines, or None when git fails (like the PowerShell helper)."""
    try:
        p = subprocess.run(["git", "-C", path] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    if p.returncode != 0:
        return None
    return [ln.rstrip("\r") for ln in p.stdout.decode("utf-8", "replace").split("\n") if ln.rstrip("\r") != ""]


def git1(path, *args):
    out = git(path, *args)
    return out[0] if out else None


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def repo_stats(path, rel):
    s = {"folder": rel, "isRepo": True}
    s["commitsTotal"] = to_int(git1(path, "rev-list", "--count", "HEAD"))
    s["branch"] = git1(path, "symbolic-ref", "--short", "HEAD")
    remotes = git(path, "remote") or []
    remote = "origin" if "origin" in remotes else (remotes[0] if remotes else None)
    s["remoteUrl"] = git1(path, "remote", "get-url", remote) if remote else None
    up = git1(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    s["upstream"] = up
    if s["commitsTotal"] > 0:
        if up:
            s["ahead"] = to_int(git1(path, "rev-list", "--count", "@{u}..HEAD"))
            s["behind"] = to_int(git1(path, "rev-list", "--count", "HEAD..@{u}"))
        elif remote:
            s["ahead"] = to_int(git1(path, "rev-list", "--count", "HEAD", "--not", "--remotes"))
            s["behind"] = 0
        else:
            s["ahead"] = s["commitsTotal"]
            s["behind"] = 0
        s["lastCommitAt"] = git1(path, "log", "-1", "--format=%cI")
        s["firstCommitAt"] = git1(path, "log", "--reverse", "--format=%cI")
        s["commits7d"] = to_int(git1(path, "rev-list", "--count", "--since=7 days ago", "HEAD"))
        act = {}
        for d in git(path, "log", "--since=30 days ago", "--format=%cd", "--date=short") or []:
            act[d] = act.get(d, 0) + 1
        s["activity"] = {k: act[k] for k in sorted(act)}
        recent = []
        for ln in git(path, "log", "--since=14 days ago", "-n", "40", "--format=%cI|%s") or []:
            i = ln.find("|")
            recent.append({"at": ln[:i], "subject": ln[i + 1:]})
        s["recentCommits"] = recent
    else:
        s.update({"ahead": 0, "behind": 0, "lastCommitAt": None, "firstCommitAt": None,
                  "commits7d": 0, "activity": {}, "recentCommits": []})
    # --no-optional-locks: read the status without refreshing the index, so a sync never writes into a repo.
    st = git(path, "--no-optional-locks", "status", "--porcelain")
    s["dirty"] = len(st) if st else 0
    return s


# ---------------------------------------------------------------- folders
def hidden(entry):
    """Hidden the way PowerShell's Get-ChildItem (without -Force) sees it."""
    if IS_WIN:
        try:
            attrs = entry.stat(follow_symlinks=False).st_file_attributes
        except OSError:
            return False
        return bool(attrs & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))
    return entry.name.startswith(".")


def scan(path):
    try:
        with os.scandir(path) as it:
            return sorted(it, key=lambda e: e.name.upper())
    except OSError:
        return []


def walk_files(path, max_depth, include_hidden=False, rel=()):
    """Yield (DirEntry, relative parts) for files up to max_depth folders below path (like -Depth)."""
    for e in scan(path):
        if not include_hidden and hidden(e):
            continue
        try:
            is_dir = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        if is_dir:
            if len(rel) < max_depth:
                yield from walk_files(e.path, max_depth, include_hidden, rel + (e.name,))
        elif e.is_file():
            yield e, rel + (e.name,)


def folder_stats(path, rel):
    newest = None
    for e, parts in walk_files(path, 3):
        if any(p.lower() in ("node_modules", ".godot") for p in parts[:-1]):
            continue
        try:
            m = e.stat().st_mtime
        except OSError:
            continue
        if newest is None or m > newest:
            newest = m
    return {"folder": rel, "isRepo": False,
            "lastModifiedAt": dt.datetime.fromtimestamp(newest).astimezone().isoformat() if newest is not None else None}


# ---------------------------------------------------------------- icons
def png_size(fp):
    with open(fp, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def project_icon(path, rel, icons_dir):
    cands = []
    pg = os.path.join(path, "project.godot")
    if os.path.isfile(pg):
        try:
            with open(pg, encoding="utf-8", errors="replace") as f:
                m = re.search(r'^config/icon="res://(.+)"', f.read(), re.I | re.M)
            if m:
                p = os.path.join(path, *m.group(1).split("/"))
                if os.path.isfile(p):
                    cands.append(p)
        except OSError:
            pass
    found = []
    for e, parts in walk_files(path, 4):
        base, ext = os.path.splitext(e.name)
        if ext.lower() not in ICON_EXTS or not ICON_NAME_RE.search(base):
            continue
        if any(ICON_SKIP_DIR_RE.fullmatch(p) for p in parts[:-1]):
            continue
        rank = 0 if base.lower() == "icon" else 1 if "icon" in base.lower() else 2
        try:
            size = e.stat().st_size
        except OSError:
            size = 0
        found.append((rank, -size, e.path))
    cands += [p for _, _, p in sorted(found, key=lambda t: (t[0], t[1]))]
    if not cands:
        return None
    src = cands[0]
    slug = re.sub(r"[^a-z0-9]+", "-", re.split(r"[\\/]", rel)[0].lower()).strip("-")
    try:
        os.makedirs(icons_dir, exist_ok=True)
        out = os.path.join(icons_dir, slug + ".png")
        if Image is not None:
            with Image.open(src) as img:
                w, h = img.size
                big = max(w, h)
                im = img if img.mode in ("1", "L", "LA", "P", "RGB", "RGBA", "I") else img.convert("RGBA")
                if big > 192:
                    k = 192 / big
                    im = im.convert("RGBA").resize((round(w * k), round(h * k)), Image.LANCZOS)
                im.save(out, "PNG")
        else:
            dims = png_size(src) if src.lower().endswith(".png") else None
            if not dims or max(dims) > 192:
                return None  # resizing needs Pillow: pip install Pillow
            big = max(dims)
            shutil.copyfile(src, out)
        return {"file": out, "pixelArt": big <= 64, "source": src}
    except Exception:
        return None


# ---------------------------------------------------------------- GitHub
_gh_owner = None


def repo_name(text):
    n = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(n) > 60:
        n = n[:60].strip("-")
    return n or "new-project"


def new_github_repo(path, name, visibility, description, dry_run, planned=False):
    global _gh_owner
    g = {"ok": False, "visibility": visibility, "name": None, "url": None, "error": None}
    gh = shutil.which("gh")
    if not gh:
        g["error"] = "The GitHub CLI (gh) isn't installed on this computer."
        return g
    if not _gh_owner:
        p = subprocess.run([gh, "api", "user", "--jq", ".login"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        _gh_owner = p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else None
        if not _gh_owner:
            g["error"] = "gh isn't signed in to GitHub. Run 'gh auth login' once."
            return g
    if not planned:
        if not os.path.exists(os.path.join(path, ".git")):
            g["error"] = "This folder isn't a git repo yet."
            return g
        if git(path, "rev-parse", "--verify", "HEAD") is None:
            g["error"] = "The repo has no commits to push yet."
            return g
        remotes = git(path, "remote") or []
        if remotes:
            g["error"] = "This repo already has a remote (%s)." % ", ".join(remotes)
            return g
    base = repo_name(name)
    pick = None
    for suffix in ("", "-2", "-3", "-4", "-5"):
        cand = base + suffix
        p = subprocess.run([gh, "repo", "view", "%s/%s" % (_gh_owner, cand), "--json", "name"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0:
            pick = cand
            break
    if not pick:
        g["error"] = "GitHub repos named %s to %s-5 already exist." % (base, base)
        return g
    g["name"] = pick
    g["url"] = "https://github.com/%s/%s" % (_gh_owner, pick)
    if dry_run:
        g["ok"] = True
        g["dryRun"] = True
        return g
    desc = (description or "").split("\n")[0].strip()[:100]
    args = [gh, "repo", "create", pick, "--public" if visibility == "public" else "--private",
            "--source", path, "--remote", "origin", "--push"]
    if desc:
        args += ["--description", desc]
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        g["error"] = "gh repo create failed: " + p.stdout.decode("utf-8", "replace").strip()
        return g
    subprocess.run(["git", "-C", path, "push", "-u", "origin", "HEAD"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g["ok"] = True
    return g


# ---------------------------------------------------------------- requests
def parse_req(req, setups):
    reqs = []
    for rec in req.split(";;"):
        if not rec.strip():
            continue
        f = rec.split("|")
        if len(f) < 3:
            setups.append({"id": None, "folder": None, "ok": False, "error": "Unreadable request: " + rec,
                           "warning": None, "github": None})
            continue
        reqs.append({"id": f[0].strip(), "folder": f[1].strip(), "name": f[2].strip(),
                     "create": not (len(f) > 3 and f[3].strip() == "0"),
                     "github": f[4].strip().lower() if len(f) > 4 else "none",
                     "note": "|".join(f[5:]).strip() if len(f) > 5 else ""})
    return reqs


def run_requests(reqs, root, root_name, template, dry_run):
    setups = []
    for r in reqs:
        res = {"id": r.get("id"), "folder": r.get("folder"), "ok": False, "error": None, "warning": None, "github": None}
        folder = str(r.get("folder") or "")
        c = r.get("create", True)
        create = not (c is not None and not isinstance(c, str) and c == 0)
        name = str(r.get("name") or folder)
        note = str(r.get("note") or "")
        planned = False
        path = None
        if not FOLDER_RE.match(folder) or ".." in folder:
            res["error"] = BAD_NAME
        elif create:
            path = os.path.join(root, folder)
            if re.search(r"[\\/]", folder):
                res["error"] = BAD_NAME
            elif os.path.exists(path):
                res["error"] = "A folder named %s already exists in %s. Pick another name." % (folder, root_name)
            elif dry_run:
                res.update(ok=True, dryRun=True, warning="Dry run: would create %s with README.md, a %s .gitignore, "
                                                         "git init and a first commit." % (folder, template))
                planned = True
            else:
                os.mkdir(path)
                date = dt.date.today().isoformat()
                with open(os.path.join(path, "README.md"), "w", encoding="utf-8", newline="\n") as f:
                    f.write("# %s\n\n%s\n\nStarted %s from the Idea to Launch brain dump.\n" % (name, note, date))
                with open(os.path.join(path, ".gitignore"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(GITIGNORE[template])
                q = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["git", "-C", path, "init", "-b", "main"], **q)
                subprocess.run(["git", "-C", path, "add", "-A"], **q)
                p = subprocess.run(["git", "-C", path, "commit", "-m", "Start " + name], **q)
                res["ok"] = True
                if p.returncode != 0:
                    res["warning"] = "Folder and repo created, but the first commit failed. Check git user.name and user.email."
        else:
            path = os.path.join(root, *re.split(r"[\\/]", folder))
            if os.path.exists(path):
                res["ok"] = True
            else:
                res["error"] = "%s%s%s doesn't exist." % (root_name, SEP, folder)
        gh = str(r.get("github") or "").lower()
        if res["ok"] and gh in ("private", "public"):
            res["github"] = new_github_repo(path, name, gh, note, dry_run, planned)
        setups.append(res)
    return setups


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Idea to Launch sync helper: prints {now, setups, repos} as JSON.")
    ap.add_argument("--root", default="")
    ap.add_argument("--config", default="")
    ap.add_argument("--req", default="")
    ap.add_argument("--requests", default="")
    ap.add_argument("--gitignore", default="")
    ap.add_argument("--icons", action="store_true")
    ap.add_argument("--icons-dir", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg, cfg_path = {}, a.config or os.path.join(HERE, "tracker.config.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8-sig") as f:
                cfg = json.load(f) or {}
        except (OSError, ValueError) as e:
            fail("Can't read %s as JSON: %s" % (cfg_path, e))
    cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
    root = a.root or cfg.get("root") or ""
    if root and not a.root and not os.path.isabs(root):
        root = os.path.join(cfg_dir, root)  # a relative root in the config is relative to the config file
    if not root:
        fail('No projects root. Pass --root DIR or put {"root": "..."} in %s.' % cfg_path)
    if not os.path.isdir(root):
        fail("The projects root '%s' doesn't exist." % root)
    root = os.path.abspath(root)
    template = (a.gitignore or cfg.get("gitignoreTemplate") or "generic").lower()
    if template not in GITIGNORE:
        fail("gitignoreTemplate must be godot, node or generic (got '%s')." % template)
    icons_dir = a.icons_dir or cfg.get("iconsDir") or ""
    if icons_dir and not a.icons_dir and not os.path.isabs(icons_dir):
        icons_dir = os.path.join(cfg_dir, icons_dir)
    icons_dir = icons_dir or os.path.join(HERE, "icons", "auto")

    # 1. create requested projects and GitHub repos
    pre = []
    if a.req:
        reqs = parse_req(a.req, pre)
    elif a.requests and os.path.isfile(a.requests):
        with open(a.requests, encoding="utf-8-sig") as f:
            data = json.load(f)
        reqs = data if isinstance(data, list) else [data]
    else:
        reqs = []
    setups = pre + run_requests(reqs, root, os.path.basename(root.rstrip("\\/")), template, a.dry_run)

    # 2. describe every project folder
    repos = []
    for top in scan(root):
        if not top.is_dir() or hidden(top) or top.name[:1] in ("_", "."):
            continue
        found = []
        if os.path.exists(os.path.join(top.path, ".git")):
            found.append((top.path, repo_stats(top.path, top.name)))
        else:
            subs = [d for d in scan(top.path) if d.is_dir() and os.path.exists(os.path.join(d.path, ".git"))]
            if subs:
                found += [(d.path, repo_stats(d.path, top.name + SEP + d.name)) for d in subs]
            else:
                found.append((top.path, folder_stats(top.path, top.name)))
        for path, rec in found:
            if a.icons:
                rec["icon"] = project_icon(path, rec["folder"], icons_dir)
            repos.append(rec)

    out = json.dumps({"now": now_iso(), "setups": setups, "repos": repos}, indent=2, ensure_ascii=False)
    sys.stdout.buffer.write((out + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
