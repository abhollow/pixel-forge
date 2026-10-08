---
name: playtest
description: Playtesting — prepare a human playtest, turn the user's feedback into numbered changes, or (only when asked) run bot campaigns and report.
argument-hint: "[prep | feedback <notes> | bot <scope>]"
disable-model-invocation: true
---

# Playtest

Mode and input: $ARGUMENTS

Load the `pixel-forge` skill; read `references/playtesting.md`.

## prep — get a human playtest ready

1. Smoke test green; build runs from the main menu.
2. Make the build easy to test: debug-only level select (`OS.is_debug_build()`),
   no dev overlays the user didn't ask for.
3. For a phone: export a **debug** APK (`references/mobile-export.md`) or tell
   the user which preset to use.
4. Write 4–5 "what to feel for" questions per level/unit under test (in the
   level docs), and list them for the user.
5. For strangers: the rules — say nothing, watch hands, ask what they expected.

## feedback — the user played and sent notes

1. Answer in **their numbering**. Flag anything unclear instead of guessing.
2. Sort: broken / unclear → fix now; missing → `docs/later.md` (ask);
   taste → change it if it's theirs.
3. **Reproduce and measure** each report before changing anything.
4. Change the knob that hits the binding constraint; one number where possible.
   Onboarding and "not fun" are judged by people — believe them over metrics.
5. Smoke test; render anything visual; **no bot runs unless asked**.
6. Log in `docs/handoff.md`; report per number with knob + file; ask about
   anything that changes the feel.

## bot — only when the user asked for one

1. Confirm scope (levels/units, seeds) and that it may take a while; run in the
   background with `run_in_background`, `timeout` per run, `--max-fps 0`, and
   a separate user dir per run.
2. **Baseline before changing anything.**
3. Summarise with `bot_report.py`: clears, first-try rate, time vs target,
   hits/min, stuck events, and `grep -c "SCRIPT ERROR"`.
4. Separate bot-tooling problems from game problems.
5. If asked to fix: one change at a time, re-measure, comment each change with
   its reason. For unattended runs, follow the overnight protocol in
   `references/collaboration.md` §6 and write `docs/playtest-YYYY-MM-DD.md`.

Framing for the report: a bot clear means a competent player can clear it; a
bot failure means "play it yourself", not "impossible".
