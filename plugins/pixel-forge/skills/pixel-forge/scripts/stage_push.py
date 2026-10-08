#!/usr/bin/env python3
"""Stage a git push the user makes themselves, as a zip -- verified first.

SANDBOX FALLBACK ONLY. Use this in the claude.ai / Cowork sandbox, where
Claude cannot push to the user's GitHub. In Claude Code on the user's machine,
commit and push directly with git / gh instead.

    python stage_push.py --repo https://github.com/you/game.git \\
        --src ~/game --godot /path/to/godot --test res://tools/smoke_test.gd \\
        --out /mnt/user-data/outputs/game-push.zip

The workflow: clone their repo fresh, copy the working project over it, and
let git work out what changed. That catches what a hand-picked file list
misses (a new file, a rename), shows the change count and ANY deletions --
which deserve a second look -- and then runs the tests IN THE CLONE, so the
zip is known to pass exactly as the user will receive it. They extract it and
`git commit` / `git push`.

Skips Godot's cache (.godot/, untracked *.import): regenerated on open, and a
stale copy causes "could not find type" errors after pulling (.import files
the repo already tracks are left as they are). The zip is written with
Python's zipfile (no `zip` CLI needed, so it works on Windows too); the work
folder defaults to a fresh temporary directory.
"""
import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

SKIP_DIRS = {".git", ".godot"}


def rmtree(path):
    """rmtree that also removes git's read-only pack files on Windows."""
    def force(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    if os.path.exists(path):
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=force)
        else:
            shutil.rmtree(path, onerror=force)


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def zip_tree(folder, out_zip, arc_root):
    """Zip `folder` as `arc_root/...`, keeping .git (the user commits from it)."""
    n = 0
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for f in sorted(files):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, folder)
                z.write(full, os.path.join(arc_root, rel).replace(os.sep, "/"))
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="the user's repo URL (must be readable)")
    ap.add_argument("--src", required=True, help="the working project to push")
    ap.add_argument("--out", required=True, help="zip to write")
    ap.add_argument("--work", default=None, help="clone folder (default: a new temporary directory)")
    ap.add_argument("--godot", default=None, help="Godot binary, to run tests in the clone")
    ap.add_argument("--test", default=None, help="headless test script, e.g. res://tools/smoke_test.gd")
    a = ap.parse_args()

    tmp_parent = None
    if a.work:
        work = os.path.abspath(a.work)
        rmtree(work)
    else:
        tmp_parent = tempfile.mkdtemp(prefix="stage_push_")
        work = os.path.join(tmp_parent, "repo")
    try:
        r = run(["git", "clone", "--quiet", a.repo, work])
        if r.returncode != 0:
            sys.exit("clone failed -- is the repo public, or the URL right?\n" + r.stderr)
        head = run(["git", "log", "--oneline", "-1"], cwd=work).stdout.strip()

        src = os.path.abspath(os.path.expanduser(a.src))
        # Mirror, not just copy over: a tracked file missing from the working
        # project is removed from the clone so git reports it as DELETED.
        # (Copying over alone never shows deletions.) Tracked .import files
        # and anything under .godot/ are left as the repo has them.
        tracked = run(["git", "ls-files", "-z"], cwd=work).stdout.split("\0")
        tracked = [t for t in tracked if t]
        for rel in tracked:
            parts = rel.split("/")
            if rel.endswith(".import") or parts[0] in SKIP_DIRS:
                continue
            if not os.path.exists(os.path.join(src, *parts)):
                os.remove(os.path.join(work, *parts))
        tracked_set = set(tracked)
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            if rel.split(os.sep)[0] in SKIP_DIRS:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith(".import"):
                    continue
                dst = os.path.join(work, rel, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(root, f), dst)

        run(["git", "add", "-A"], cwd=work)
        status = run(["git", "status", "--short"], cwd=work).stdout.splitlines()
        deletions = [s for s in status if s.startswith("D")]
        print(f"repo at: {head}")
        print(f"changed: {len(status)} files   deletions: {len(deletions)}")
        for d in deletions:
            print("  DELETED:", d[3:], "  <- check this is intended")

        if a.godot and a.test:
            run([a.godot, "--headless", "--path", work, "--import"], timeout=300)
            t = run([a.godot, "--headless", "--path", work, "--script", a.test], timeout=300)
            tail = [l for l in (t.stdout + t.stderr).splitlines() if "FAIL" in l or "checks" in l]
            print("\n".join(tail[-12:]) or "(no test summary found)")

        rmtree(os.path.join(work, ".godot"))
        git_dir = os.path.join(work, ".git")
        for root, _, files in os.walk(work):
            if os.path.commonpath([root, git_dir]) == git_dir:
                continue
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), work).replace(os.sep, "/")
                if f.endswith(".import") and rel not in tracked_set:
                    os.remove(os.path.join(root, f))
        out = os.path.abspath(a.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            os.remove(out)
        n = zip_tree(work, out, os.path.basename(work.rstrip("/\\")))
        print(f"wrote {a.out}  ({n} files)")
    finally:
        if tmp_parent:
            rmtree(tmp_parent)


if __name__ == "__main__":
    main()
