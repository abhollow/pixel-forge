#!/usr/bin/env python3
"""Build the claude.ai / Claude desktop upload of the main Pixel Forge skill.

    python tools/build_skill_zip.py            # -> dist/pixel-forge-skill.zip
    python tools/build_skill_zip.py --short    # 200-char description for strict uploaders

The plugin's skill folder is the source of truth. Outside Claude Code:
  * only some frontmatter keys are accepted (others are a hard error), so the
    rest are stripped;
  * ${CLAUDE_SKILL_DIR} / ${CLAUDE_PLUGIN_ROOT} are not substituted, so they are
    rewritten to plain words;
  * the zip must contain one folder named exactly like the skill's `name`.
Slash commands, agents, hooks and the tracker are Claude Code features and are
not included.
"""
import argparse
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "pixel-forge", "skills", "pixel-forge")
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
SHORT_DESCRIPTION = (
    "Idea-to-launch workflow for pixel-art games with Claude, Godot 4 and Magnific: "
    "concept, art pipeline, GDScript, playtesting, debugging, export and launch."
)
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_EXT = {".pyc", ".pyo"}


def split_frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        sys.exit("SKILL.md has no frontmatter")
    return m.group(1), text[m.end():]


def clean_frontmatter(fm, short):
    out, keep = [], False
    for line in fm.splitlines():
        key = re.match(r"^([A-Za-z_-]+):", line)
        if key:
            keep = key.group(1) in ALLOWED_KEYS
            if keep and key.group(1) == "description" and short:
                line = "description: " + SHORT_DESCRIPTION
        if keep:
            out.append(line)
    return "\n".join(out)


def rewrite_vars(text):
    text = text.replace("${CLAUDE_SKILL_DIR}", "the folder containing this SKILL.md")
    text = text.replace("${CLAUDE_PLUGIN_ROOT}/skills/pixel-forge", "this skill's folder")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "dist", "pixel-forge-skill.zip"))
    ap.add_argument("--short", action="store_true", help="use a <=200-character description")
    a = ap.parse_args()

    with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
        fm, body = split_frontmatter(f.read())
    name = re.search(r"^name:\s*(\S+)", fm, re.M).group(1)
    skill_md = "---\n" + clean_frontmatter(fm, a.short) + "\n---\n" + rewrite_vars(body)
    desc = re.search(r"^description:\s*(.*)$", clean_frontmatter(fm, a.short), re.M).group(1)
    if len(desc) > 1024:
        sys.exit(f"description is {len(desc)} chars (max 1024)")
    if len(desc) > 200 and not a.short:
        print(f"note: description is {len(desc)} chars; if the uploader rejects it, rebuild with --short")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    count = 0
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{name}/SKILL.md", skill_md)
        count += 1
        for root, dirs, files in os.walk(SKILL):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for fn in sorted(files):
                if os.path.splitext(fn)[1] in SKIP_EXT:
                    continue
                path = os.path.join(root, fn)
                rel = os.path.relpath(path, SKILL).replace(os.sep, "/")
                if rel == "SKILL.md":
                    continue
                if fn.endswith(".md"):
                    with open(path, encoding="utf-8") as f:
                        z.writestr(f"{name}/{rel}", rewrite_vars(f.read()))
                else:
                    z.write(path, f"{name}/{rel}")
                count += 1
    size = os.path.getsize(a.out)
    print(f"wrote {a.out}: {count} files, {size / 1024:.0f} KB, skill '{name}'")


if __name__ == "__main__":
    main()
