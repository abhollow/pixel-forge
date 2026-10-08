#!/usr/bin/env python3
"""Consistency checks for the Pixel Forge package. Run before every commit.

    python tools/check_package.py            # errors fail, warnings print
    python tools/check_package.py --no-run   # skip running every script's --help

Checks: manifests parse and agree; every skill and agent has valid frontmatter;
command skills are user-invoked only; every scripts/, assets/ and references/
path mentioned in the docs exists; reference cross-links resolve; every Python
script answers --help; stage tables agree; no personal paths leaked into the
plugin.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "pixel-forge")
SKILL = os.path.join(PLUGIN, "skills", "pixel-forge")
STAGES = ["idea", "concept", "design", "prototype", "core", "content", "polish", "launch", "shipped"]
# Generic personal-data patterns that must never ship inside the plugin: a real
# Windows user folder (placeholders like C:\Users\you\ or %USERPROFILE% are fine)
# and Claude desktop's internal session paths.
PERSONAL = [r"[A-Za-z]:[\\/]+Users[\\/]+(?!you\b|<|%|\{)[A-Za-z0-9_.-]+[\\/]",
            r"local-agent-mode-sessions"]
# Project-specific words (the maintainer's own game names, people, places) live
# in tools/denylist.local.txt, which is gitignored: the public repo must not
# contain the very words it guards against. One regex per line, case-insensitive.
DENYLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "denylist.local.txt")


def load_denylist():
    if not os.path.exists(DENYLIST_FILE):
        return []
    with open(DENYLIST_FILE, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]


GAME_TERMS = load_denylist()

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    text = read(path)
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None, text
    fields = {}
    for line in m.group(1).splitlines():
        k = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if k:
            fields[k.group(1)] = k.group(2).strip().strip('"')
    return fields, text[m.end():]


def check_manifests():
    try:
        market = json.loads(read(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
        plugin = json.loads(read(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))
    except Exception as e:  # noqa: BLE001
        err(f"manifest does not parse: {e}")
        return None
    entry = next((p for p in market.get("plugins", []) if p.get("name") == plugin.get("name")), None)
    if not entry:
        err("marketplace.json has no entry matching plugin.json name")
    elif entry.get("source") != "./plugins/pixel-forge":
        err(f"marketplace source is {entry.get('source')!r}")
    for key in ("name", "version", "description", "author"):
        if key not in plugin:
            warn(f"plugin.json missing {key}")
    hooks = os.path.join(PLUGIN, "hooks", "hooks.json")
    if os.path.exists(hooks):
        try:
            json.loads(read(hooks))
        except Exception as e:  # noqa: BLE001
            err(f"hooks.json does not parse: {e}")
    return plugin.get("version")


def check_skills():
    for path in sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md"))):
        d = os.path.basename(os.path.dirname(path))
        fm, _ = frontmatter(path)
        if fm is None:
            err(f"skills/{d}/SKILL.md has no frontmatter")
            continue
        if fm.get("name") != d:
            err(f"skills/{d}: name {fm.get('name')!r} does not match folder")
        desc = fm.get("description", "")
        if not desc:
            err(f"skills/{d}: empty description")
        if len(desc) > 1024:
            err(f"skills/{d}: description {len(desc)} chars > 1024")
        if d != "pixel-forge" and fm.get("disable-model-invocation") != "true":
            err(f"skills/{d}: command skills must set disable-model-invocation: true")
        if d != "pixel-forge" and len(desc) > 200:
            warn(f"skills/{d}: description {len(desc)} chars (keep command descriptions short)")
    for path in sorted(glob.glob(os.path.join(PLUGIN, "agents", "*.md"))):
        fm, _ = frontmatter(path)
        name = os.path.splitext(os.path.basename(path))[0]
        if not fm or fm.get("name") != name or not fm.get("description"):
            err(f"agents/{name}.md: needs name (= file name) and description")


def check_paths():
    md_files = glob.glob(os.path.join(PLUGIN, "**", "*.md"), recursive=True)
    ref_names = {os.path.basename(p) for p in glob.glob(os.path.join(SKILL, "references", "*.md"))}
    pat = re.compile(r"(?<![\w/.])((?:scripts|assets|references)/[\w./-]+?\.(?:gdshader|py|gd|sh|md|json|yml))(?![\w])")
    for path in md_files:
        rel = os.path.relpath(path, ROOT)
        if os.sep + "assets" + os.sep + "project" + os.sep in path:
            continue  # game templates refer to the game's own paths
        text = read(path)
        for m in pat.finditer(text):
            target = m.group(1).rstrip(".")
            if not os.path.exists(os.path.join(SKILL, target)):
                err(f"{rel}: mentions missing {target}")
        if os.sep + "references" + os.sep in path:
            for m in re.finditer(r"`([\w-]+\.md)`", text):
                name = m.group(1)
                if name in ("SKILL.md", "CLAUDE.md", "README.md", "CHANGELOG.md", "STEERING.md"):
                    continue
                if name.startswith(("concept", "bible", "handoff", "status", "later", "assets", "art-manifest", "art-prompt", "system", "level", "playtest-", "retro-", "pixel-forge-proposals")) and name not in ref_names:
                    continue  # project doc names, not references
                if name not in ref_names:
                    err(f"{rel}: links to unknown reference {name}")


def check_scripts(run):
    scripts = sorted(glob.glob(os.path.join(SKILL, "scripts", "*.py")))
    skill_md = read(os.path.join(SKILL, "SKILL.md"))
    for s in scripts:
        name = os.path.basename(s)
        if name.startswith("_"):
            continue
        if run:
            try:
                r = subprocess.run([sys.executable, s, "--help"], capture_output=True, text=True, timeout=60,
                                   cwd=os.path.dirname(s))
                if r.returncode != 0:
                    err(f"scripts/{name} --help exited {r.returncode}: {r.stderr.strip()[-200:]}")
            except subprocess.TimeoutExpired:
                err(f"scripts/{name} --help timed out")
        mentioned = name in skill_md or any(name in read(p) for p in glob.glob(os.path.join(SKILL, "references", "*.md")))
        if not mentioned and name not in ("forge_config.py", "forge_image.py", "forge_ndimage.py"):
            warn(f"scripts/{name} is not mentioned in SKILL.md or any reference")


SUBCOMMANDS = {"palette_build.py": ["init", "build", "coverage"], "fit_ratio.py": ["pad", "crop", "paste-keep"],
               "audio_encode.py": ["loudnorm", "reencode", "probe"], "make_palette.py": ["extract", "ramp"],
               "forge_config.py": ["init", "show"]}


def check_flags():
    """Every --flag written after a forge script in the docs must exist in its --help."""
    cache = {}

    def helptext(script, sub):
        if (script, sub) not in cache:
            cmd = [sys.executable, "-I", os.path.join(SKILL, "scripts", script)] + ([sub] if sub else []) + ["--help"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            cache[(script, sub)] = r.stdout + r.stderr
        return cache[(script, sub)]

    docs = [p for p in glob.glob(os.path.join(PLUGIN, "**", "*.md"), recursive=True)
            if os.sep + "project" + os.sep not in p and os.sep + "tracker" + os.sep not in p]
    for path in docs:
        text = re.sub(r"\\\n\s*", " ", read(path))
        for line in text.splitlines():
            for m in re.finditer(r"([a-z_]+\.py)\"?((?:\s+[^`#|\n]*)?)", line):
                script, rest = m.group(1), m.group(2)
                if not os.path.exists(os.path.join(SKILL, "scripts", script)):
                    continue
                words = rest.split()
                sub = words[0] if script in SUBCOMMANDS and words and words[0] in SUBCOMMANDS[script] else None
                for fl in re.findall(r"(?<![\w-])(--?[a-zA-Z][\w-]*)", rest):
                    if not re.search(r"(?<![\w-])" + re.escape(fl) + r"(?![\w-])", helptext(script, sub)):
                        err(f"{os.path.relpath(path, ROOT)}: {script} {sub or ''} has no {fl}  [{line.strip()[:90]}]")


def check_stages():
    stages_json = os.path.join(PLUGIN, "tracker", "stages.json")
    if os.path.exists(stages_json):
        data = json.loads(read(stages_json))
        items = data if isinstance(data, list) else data.get("stages", [])
        ids = [s.get("id") for s in items]
        if ids != STAGES:
            err(f"tracker/stages.json ids {ids} != {STAGES}")
    status = os.path.join(SKILL, "assets", "project", "docs", "status.md")
    if os.path.exists(status):
        text = read(status)
        for s in STAGES:
            if f"| {s} |" not in text:
                err(f"status.md template missing stage {s}")


def check_game_terms():
    roots = [PLUGIN, os.path.join(ROOT, "docs"), os.path.join(ROOT, "tools"), os.path.join(ROOT, "tests"),
             os.path.join(ROOT, "README.md"), os.path.join(ROOT, "CHANGELOG.md"),
             os.path.join(ROOT, "USER-GUIDE.md"), os.path.join(ROOT, ".github")]
    exts = (".md", ".py", ".gd", ".sh", ".json", ".html", ".ps1", ".tmpl", ".yml", ".gdshader", ".tres", ".svg")
    files = []
    for r in roots:
        if os.path.isfile(r):
            files.append(r)
        else:
            files += [p for p in glob.glob(os.path.join(r, "**", "*"), recursive=True) if p.endswith(exts)]
    me = os.path.abspath(__file__)
    for path in files:
        if os.path.abspath(path) == me:
            continue
        text = read(path)
        for t in GAME_TERMS:
            m = re.search(t, text, re.I)
            if m:
                line = text[:m.start()].count("\n") + 1
                err(f"{os.path.relpath(path, ROOT)}:{line}: denylisted term (see tools/denylist.local.txt)")


def check_personal():
    for path in glob.glob(os.path.join(PLUGIN, "**", "*"), recursive=True):
        if os.path.isdir(path) or os.path.splitext(path)[1] not in (".md", ".py", ".gd", ".sh", ".json", ".html", ".ps1", ".tmpl", ".yml", ".gdshader"):
            continue
        text = read(path)
        for p in PERSONAL:
            if re.search(p, text):
                err(f"{os.path.relpath(path, ROOT)}: personal/machine detail matches {p!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-run", action="store_true", help="don't run scripts with --help")
    a = ap.parse_args()
    version = check_manifests()
    check_skills()
    check_paths()
    check_scripts(not a.no_run)
    if not a.no_run:
        check_flags()
    check_stages()
    check_personal()
    check_game_terms()
    changelog = os.path.join(ROOT, "CHANGELOG.md")
    if version and os.path.exists(changelog) and version not in read(changelog):
        warn(f"CHANGELOG.md has no entry for {version}")
    for w in warnings:
        print("warn: ", w)
    for e in errors:
        print("ERROR:", e)
    print(f"{len(errors)} errors, {len(warnings)} warnings (plugin v{version})")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
