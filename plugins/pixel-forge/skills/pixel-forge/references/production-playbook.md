# Production playbook: Design → Shipped

Stage by stage, with exit criteria. Tell the user the current stage and its
exit criterion; a stage without one runs forever. Concept work is in
`concept-and-research.md`; this file picks up at Design.

## Contents
1. Design (20–34%)
2. Prototype and the playtest gate (35–49%)
3. Core build (50–64%)
4. Art & content (65–79%)
5. Polish & test (80–89%)
6. Launch prep (90–99%)
7. The round: one batch at a time
8. The chunk loop: one level at a time
9. Managing the project

---

## 1. Design (20–34%)

Lock the bible (`project-docs.md` §3) and scaffold the project:

```bash
python "$FORGE/scripts/new_godot_project.py" ~/Games/MyGame --name "My Game" \
    --width 360 --height 640 --scale 2 --aspect keep --orientation portrait \
    --perspective three-quarter
```

Decide resolution by the short side and how busy the screen is
(`godot4-pixel-setup.md`): 360x640 at 2x gives chunky, readable sprites for a
portrait game with a few large actors; many small actors on screen need
something like 960x540. Changing it later means rescaling every layout
number — if you must, do it on day one, by script.

**Exit:** bible locked, `forge.json` written, project runs, smoke test green.

## 2. Prototype and the playtest gate (35–49%)

The core loop playable with **no art**: coloured rectangles, `Label`s showing
raw numbers. If the loop isn't fun as rectangles, art won't save it.

Build in this order:

1. The single most satisfying action — just the verb.
2. Its feedback — number goes up, thing disappears, a tween fires.
3. The conversion step — resource becomes currency/progress.
4. One upgrade or choice with a visible effect on step 1.
5. Loop closed. Stop.

Keep a debug overlay with the live numbers; tuning blind doesn't work. Put
every number in the tuning block from the first line of code.

**The gate.** Write three honest questions in `docs/handoff.md` (e.g. "Is
the main action a decision, or a reflex?") and play. `playtesting.md` covers running it.

**If the user waives the gate** (they want to lead with the look), say what
it risks, log the waiver, and sequence art so it survives a redesign:

| Safe early | Wait until layout and mechanics settle |
|---|---|
| Mood frame, palette, style anchor | Maps and painted backgrounds |
| Character, creature and building kits | Painted scenes tied to a layout |
| Icons, UI frame, title | Anything measured into gameplay zones |

Why: character and building kits survive pivots; maps and painted
backgrounds tied to a layout get repainted after every redesign and can eat
more than half the art budget.

**Exit:** the user plays the grey-box for five minutes unprompted, or the
waiver is logged.

## 3. Core build (50–64%)

- The loop end to end: start → play → end condition → next unit → save.
- Architecture that scales: rules / life / HUD split, a systems registry,
  content in data (`architecture.md`).
- **Lock art direction** before volume: 4 mood frames → the user picks →
  palette and style anchor (`art-direction.md`).
- Build the mechanic before its art: code-drawn placeholder plus an art slot,
  so the user's pick drops in with no code change.

**Exit:** a full unit plays start to finish; art direction locked.

## 4. Art & content (65–79%)

- **Hero asset first** — whatever is on screen most. Let it set the standard.
- **Style plate** once three or four assets exist: render them together at game
  scale; judge new assets against the plate, never alone.
- **Placeholder sweep**: every needed asset to "acceptable" before any to "great".
- **Content through data**: a new level, upgrade or structure is a data entry,
  not a duplicated scene. If adding content means duplicating, refactor first.
- **Juice before more content** — cheap and large:

| Add | Cost | Effect |
|---|---|---|
| Scale-and-fade on pickup (~120 ms) | minutes | Enormous |
| Screen shake 2–4 px (camera/world offset, always returns to zero) | minutes | Large |
| Number pop-ups on gain | ~30 min | Large |
| Easing on every UI transition | minutes | Large |
| Idle bob / sway | minutes | A static scene feels alive |
| Particle burst on completion | ~1 hour | Large on milestones |
| A short beat before the results panel (~0.85 s) | minutes | Finishing stops feeling like a form submission |

**Exit:** every asset at "acceptable", content lives in data.

## 5. Polish & test (80–89%)

The closing passes, in order:

1. **Balance** — human playtests, plus an unattended bot pass if the user wants
   one (`playtesting.md`).
2. **Forgiveness** — the first level for a *new* player: a beginner knob block,
   a grace window after hits, adaptive difficulty that eases more on level 1.
3. **Optimization and cleanup** — parallel read-only reviewers, verify, apply in
   batches, re-test (`debugging-and-optimization.md`). Delete code-drawn
   fallbacks for art that now always exists; switch art slots to `preload`.
4. **Doc sweep** (`project-docs.md` §9).

Device checks: a real phone (cheap and recent), touch targets ≥ 48 screen px,
aspect ratios 16:9 to 21:9 and notches, interruption (call, background, kill
and reopen — saves survive all three), cold start.

**Exit:** a full session plays with no placeholders and no dead moments; human
playtests done; smoke green.

## 6. Launch prep (90–99%)

Release checklist and export: `delivery.md`, `mobile-export.md`. Store page,
screenshots, trailer, pitch: `launch-and-marketing.md`.

**Exit:** a signed release build a stranger can install and finish without help.

## 7. The round: one batch at a time

Work moves in agreed batches. `/pixel-forge:round` runs this:

1. **Agree** the batch — the user's numbered list or your numbered proposal.
   New mechanics need a yes; visual polish inside the batch doesn't.
2. **Build** — tuning block, art slots, visuals in the read-only life layer.
3. **Test** — smoke test (×2 with randomness); prove new checks fail without
   the fix; bot only if agreed.
4. **Look** — render affected scenes with `tools/capture.gd`, read them, fix what
   reads badly; grep logs for `SCRIPT ERROR` and `SHADER ERROR`.
5. **Log** — handoff entry, status.md, assets.md, `CLAUDE.md` *Current state*.
6. **Deliver** — commit/push per the agreement; send key renders; numbered report.

## 8. The chunk loop: one level at a time

For a game built level by level, each level approved in turn:

1. **Brainstorm** 2–3 options for the level's mechanic and signature event,
   with a recommendation. The user chooses.
2. **Build a rough**: values in a data table, code-drawn placeholder plus art
   slot, tests. Build a mechanic only when its level comes up — every
   mechanic changes once it is played.
3. **Render a preview** from real art at game scale and fix what reads badly.
4. **Write the level doc** (`docs/templates/level.md`) with 4–5 "what to feel
   for" questions.
5. **Deliver** per the commit agreement.
6. **Playtest → revise → approve**, recording the verdict in the user's words
   ("APPROVED after playtest — '<their verdict>'") and every reversal
   ("<feature> removed: playtest found it pointless").

Protect the onboarding level from feature creep: keep level 1 basic even when
every other level gains a twist.

## 9. Managing the project

- `docs/status.md` front-matter: stage, progress, next three, blockers, open
  questions. Update every round.
- `docs/later.md` makes cutting scope emotionally possible.
- **Timebox the art pass** — it has no natural end.
- **Split the monolith** once a script passes ~1,500 lines. Why: in a file of
  several thousand lines, exact-match edits get fragile and every change
  risks hitting the wrong spot.
- **Ship at "good", not "done".** Done doesn't arrive.
- After shipping: `/pixel-forge:retro` — and fold the lessons back into Pixel Forge.
