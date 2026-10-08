#!/usr/bin/env python3
"""Turn playtest-bot JSON lines into a markdown results table.

    python bot_report.py bots_out/*.jsonl
    python bot_report.py bots_out/ -o docs/playtest-YYYY-MM-DD.md --title "Bot pass after the jump fix"
    python bot_report.py run.log --unit wave --win-values won,cleared

Why: a headless bot that plays at human pace is the tuning instrument -- a
clear rate per level before and after a fix shows whether the fix worked. But
the evidence lives in one JSON line per attempt, and building the results
table by hand every pass is slow and error-prone. This builds it.

Input: .jsonl files, folders of them, or logs where bot lines are prefixed
"BOT|" (what assets/godot/playtest_bot.gd prints). One JSON object per
attempt. Keys (rename with the flags):
  level     --level-key   which level/map/city
  unit      --unit-key    the unit inside a level (wave, round, stage); absent = "-"
  attempt   --attempt-key retry number, 1 = first try; absent = every line is a
                          first try (the forge template's seeds=N runs)
  result    --result-key  win when in --win-values (complete, clear, win, ...);
                          "stuck" also counts as a stuck event
  time_s    --time-key    game seconds the attempt took
  hits      --hits-key    times the player was hurt (shown per minute)
  stuck_events --stuck-key
  earned / goal           progress of a failed attempt, shown as "best n%"
Only lines whose "kind" is in --kinds (default attempt,unit; the forge
template assets/godot/playtest_bot.gd writes "attempt") or that have no
"kind" are counted; "done", "start", trace lines and the like are skipped.

Output: per level x unit: attempts, cleared (on which attempt), first-try
rate, mean minutes of the clearing attempts, hits/min, stuck events, best
progress when never cleared; then a totals line. Read a bot as a stress
test, not a human: a clear means "a competent player can do this"; a fail
means "play it yourself".
"""
import argparse
import glob
import json
import os
import sys
from collections import OrderedDict


def read_lines(paths):
    rows, bad = [], 0
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "*.jsonl")) + glob.glob(os.path.join(p, "*.log")))
        elif any(c in p for c in "*?["):
            files += sorted(glob.glob(p))
        else:
            files.append(p)
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if "BOT|" in s:
                    s = s.split("BOT|", 1)[1]
                if not s.startswith("{"):
                    continue
                try:
                    rows.append(json.loads(s))
                except ValueError:
                    bad += 1
    return rows, files, bad


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def sort_key(v):
    try:
        return (0, float(v), "")
    except (TypeError, ValueError):
        return (1, 0.0, str(v))


def summarise(rows, k):
    groups = OrderedDict()
    for r in rows:
        if ("kind" in r and r["kind"] not in k.kind_set) or k.result not in r:
            continue
        key = (r.get(k.level, "-"), r.get(k.unit, "-"))
        groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(groups, key=lambda t: (sort_key(t[0]), sort_key(t[1]))):
        g = groups[key]
        g.sort(key=lambda r: num(r.get(k.attempt, 1), 1))
        won = [str(r.get(k.result, "")).lower() in k.wins for r in g]
        wins = [r for r, w in zip(g, won) if w]
        firsts = [w for r, w in zip(g, won) if num(r.get(k.attempt, 1), 1) <= 1]
        times = [num(r.get(k.time)) for r in wins if k.time in r]
        all_t = sum(num(r.get(k.time)) for r in g)
        hits = sum(num(r.get(k.hits)) for r in g)
        stuck = sum(num(r.get(k.stuck)) for r in g) + sum(1 for r in g if str(r.get(k.result)).lower() == "stuck")
        best = None
        if not wins:
            prog = [num(r.get("earned")) / num(r.get("goal"), 0) for r in g if num(r.get("goal"), 0) > 0]
            best = max(prog) * 100 if prog else None
        out.append({"level": key[0], "unit": key[1], "attempts": len(g), "clears": len(wins),
                    "cleared": len(wins) > 0,
                    "cleared_on": int(num(wins[0].get(k.attempt, 1), 1)) if wins else None,
                    "first_try_rate": (100.0 * sum(firsts) / len(firsts)) if firsts else None,
                    "mean_min": (sum(times) / len(times) / 60.0) if times else None,
                    "hits_per_min": (hits / (all_t / 60.0)) if all_t > 0 else None, "stuck": int(stuck),
                    "best_pct": best})
    return out


def markdown(summary, k, title=None, files=()):
    lines = []
    if title:
        lines += ["# " + title, ""]
    if files:
        lines += ["From %d file(s): %s" % (len(files), ", ".join(os.path.basename(f) for f in files[:6])
                                           + (" ..." if len(files) > 6 else "")), ""]
    lines += ["| %s | %s | attempts | clears | result | first try | mean min (clears) | hits/min | stuck |"
              % (k.level, k.unit), "|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        if s["cleared"]:
            res = "a%d" % s["cleared_on"]
        else:
            res = "**FAIL%s**" % (" %.0f%%" % s["best_pct"] if s["best_pct"] is not None else "")
        lines.append("| %s | %s | %d | %d/%d | %s | %s | %s | %s | %d |" % (
            s["level"], s["unit"], s["attempts"], s["clears"], s["attempts"], res,
            "%.0f%%" % s["first_try_rate"] if s["first_try_rate"] is not None else "-",
            "%.1f" % s["mean_min"] if s["mean_min"] is not None else "-",
            "%.1f" % s["hits_per_min"] if s["hits_per_min"] is not None else "-", s["stuck"]))
    n = len(summary)
    cleared = sum(1 for s in summary if s["cleared"])
    att = sum(s["attempts"] for s in summary)
    clears = sum(s["clears"] for s in summary)
    unit = k.unit if any(s["unit"] != "-" for s in summary) else k.level
    lines += ["", "**Cleared %d of %d %s(s); %d of %d attempts won.** `aN` = first cleared on attempt N; "
              "`FAIL n%%` = the best attempt reached n%% of the goal; first try = share of first attempts "
              "(or seeds) that won." % (cleared, n, unit, clears, att)]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help=".jsonl files, folders or logs with BOT| lines")
    ap.add_argument("-o", "--output", help="write the markdown here (default: print it)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--level-key", dest="level", default="level")
    ap.add_argument("--unit-key", "--unit", dest="unit", default="unit")
    ap.add_argument("--attempt-key", dest="attempt", default="attempt")
    ap.add_argument("--result-key", dest="result", default="result")
    ap.add_argument("--win-values", default="complete,clear,cleared,win,won,pass,passed,ok")
    ap.add_argument("--time-key", dest="time", default="time_s")
    ap.add_argument("--hits-key", dest="hits", default="hits")
    ap.add_argument("--stuck-key", dest="stuck", default="stuck_events")
    ap.add_argument("--kinds", default="attempt,unit",
                    help="which \"kind\" values are attempts (lines without a kind always count)")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON instead")
    a = ap.parse_args()
    a.wins = {w.strip().lower() for w in a.win_values.split(",")}
    a.kind_set = {w.strip() for w in a.kinds.split(",") if w.strip()}
    rows, files, bad = read_lines(a.inputs)
    if not rows:
        raise SystemExit("no bot JSON lines found in %s" % ", ".join(a.inputs))
    summary = summarise(rows, a)
    if a.json:
        print(json.dumps(summary, indent=2))
        return
    md = markdown(summary, a, a.title, files)
    if bad:
        md += "\n(%d unreadable line(s) skipped)\n" % bad
    if a.output:
        os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
        with open(a.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
        print("wrote", a.output)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
