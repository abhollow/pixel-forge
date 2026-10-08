# Working with the user

Framework defaults for how Claude and the user work together on a game. They
are defaults — when a user states a different preference, follow theirs and
write it into the game's `CLAUDE.md` under *How we work*.

## Contents
1. Asking: numbered options, never pop-ups
2. Talking ideas out
3. Autonomy comes in batches
4. Questions that are not requests
5. Reports
6. Overnight and unattended runs
7. Commits
8. Safety checks before you run anything
9. Taste: write it down
10. Keeping rules where the next session will find them

---

## 1. Asking: numbered options, never pop-ups

Offer choices in text. Why: pop-up question widgets interrupt the flow and
tend to get dismissed; people answer in prose anyway.

- Options as a **numbered list in text**, each with its trade-off in a line,
  and **your recommendation and why**.
- Users reply by number ("go ahead with 1, both changes in 2"), so **number
  every proposed fix** in a feedback report too.
- When the user sends a numbered list, **answer in the same numbering**. If an
  item is empty or unclear (a bare "4."), flag it — don't guess.
- If the user closes a question, hold off and say so.

## 2. Talking ideas out

The "talk it out" stage is a conversation, then a document.

1. Get the idea out in their words. Ask for **the moment**: the single most
   satisfying five seconds. Quote it in `docs/handoff.md` — every later cut is
   measured against it. Why: once you know the moment, any expensive feature
   that doesn't serve it (a companion system, a crafting tree) is cuttable.
2. Research before you shape (`concept-and-research.md`).
3. For each new **system**, write a design doc from `docs/templates/system.md`:
   the model in tables, the build order, then **Questions for the user** with a
   recommendation each. Send it and wait. The answers come back as
   **Decisions (user, date)**, and they routinely change the design (a cost
   that should pay more, an action that must be limited, a resource added) —
   far cheaper to find on paper than in code.
4. **Push back with reasons.** If the user proposes a new resource, check it
   buys something the existing ones can't — otherwise suggest a role that
   makes it matter (e.g. the second resource becomes repair material).
   Pushback with a fix lands better than a flat no.
5. **Samples before a full build** when taste is involved: show 2–3 renders at
   game scale and recommend one before committing to the whole set.

## 3. Autonomy comes in batches

Autonomy usually grows in steps — first "create, implement, test, refine" on
one feature, then art at your discretion, then long unattended batches with a
short overview at the end. The protocol:

- **Inside an agreed batch:** build all of it, test, render, log, commit and
  push (if that's the agreement), then one numbered report. No per-step
  check-ins.
- **Still ask before new design directions** — new rules, new mechanics, new
  resources. A unit or role that implies mechanics nobody has designed (a
  builder implies construction rules) needs a yes. Visual-only life (weather,
  critters, smoke) is safe.
- **Decisions that change the feel** (a finale, onboarding, a beloved mechanic)
  are flagged with options, not made — even with blanket permission.
- **Balance-changing bug fixes are offered, not imposed.** If a fix measurably
  hardens a tuned level, revert it and report it as "found but deliberately
  left alone".
- When the user grants "do it without my input" on art, do **one vibe
  checkpoint first** (a few options at game scale), then proceed.
- The user may give permission to refuse ("say no if it's too much
  processing"). Judge honestly and say what you decided.

## 4. Questions that are not requests

- An exploratory question ("I'm just asking about options") gets an answer,
  not an edit.
- "Don't build this yet, let's consider the scope" — reply with measurements,
  an options table (work / risk) and a recommendation. `/pixel-forge:scope`
  does this.
- A question about what a UI label means — explain, then note that the wording
  is too cryptic (a design finding).
- "Quickly check whether you can" — check feasibility only. Do **not** run a
  suite that wipes the save (see §8).
- **Match the deliverable.** "A basic one-page pitch" means one page; don't
  start building out the game's content inside it.

## 5. Reports

Reports with this shape get read in full, whatever their length:

- Mirror their numbering; one block per item.
- **Name each knob and its file**: "`SPAWN_RATE` (0.5) in game.gd".
- Before/after numbers when you measured (bot clears, timings, sizes).
- Test count ("All N smoke checks pass"); bot result if run.
- Magnific **credits spent** this round and the balance.
- Key renders sent as files, with a one-line caption each.
- **What you couldn't check**: "I can't listen to audio — both files attached",
  "I couldn't check the motion itself, take a look in-game".
- **Decisions I made that you may want to change.**
- **Commit status**: pushed, or "Nothing is committed yet".
- **Open questions** carried from `docs/status.md` `open:` until answered. Why:
  a question asked once and never repeated gets lost, and the bug it was about
  ships.

## 6. Overnight and unattended runs

When the user says they won't be around and to change whatever is needed:

1. **Baseline first** — measure before changing anything.
2. Fix → re-measure, one change at a time; comment each change in code with
   the playtest reason.
3. Work on a **branch** (or leave changes uncommitted) unless the standing
   agreement is to push every batch.
4. Write the report to `docs/playtest-YYYY-MM-DD.md` (template:
   `docs/templates/playtest.md`): results table, numbered global changes with
   files, per-unit *Changed / Result / Suggest*, and *Suggested, not
   implemented* for anything that changes the feel.
5. End with what's committed, or "Nothing is committed: review with git diff".

Leave the feel of the finale and onboarding for the user to decide, however
good the numbers look.

## 7. Commits

- Follow the standing agreement in `CLAUDE.md`. The two common ones: commit to
  `main` only when asked, or commit and push every batch. Ask once per
  project and record the answer.
- Never commit to a side branch when the user works on `main` — merge it and
  say so.
- Hygiene checklist and push retries: `delivery.md`.

## 8. Safety checks before you run anything

- **Know what a test deletes.** A smoke test that resets saves erases the
  user's real save if it shares the game's save path — and backing up the
  wrong folder doesn't help. `user://` is
  `%APPDATA%\Godot\app_userdata\<config/name>` (the *project name*, not the
  folder). The Pixel Forge smoke template uses its own save path.
- **Ask once per project** whether tests may wipe saves, and record the answer
  in `CLAUDE.md` (some users have a developer mode and don't mind; others keep
  a real save).
- Credentials stay with the user: they run `gh auth login` themselves. Ask
  before installing tools unless they have given standing permission.
- Paid generation: check `account_balance`, preflight big batches with
  `simulate_cost`, and say what you will spend unless the user pre-authorised it.

## 9. Taste: write it down

A user's taste is consistent and expensive to relearn. Record it in
`docs/bible.md` → *Taste* the moment they say it, in their words. An example of
the axes worth capturing (fill in the user's side of each):

- Art: cozy vs. gritty; chunky vs. detailed pixels ("a hint of pixel art" vs.
  bold blocks); organic, jagged edges vs. clean geometry; whether repeated
  elements vary in scale.
- UI: minimal and semi-transparent vs. framed panels; text only for numbers the
  player acts on, or full readouts; indicators always on, or only when
  something is neglected.
- Effects: varied each time vs. one repeating sprite; cartoon vs. naturalistic
  (one big flash vs. several thin random strikes).
- Audio: music level vs. SFX — which one carries the game; silence or
  continuous music between tracks.
- Scale: expect "too small" then "too big" — a second round on sizes is normal;
  offer the in-between.

Map requests onto the user's mental model. A user who thinks in image-editor
terms ("replace color, increase the fuzziness") wants the same knobs exposed.

## 10. Keeping rules where the next session will find them

Auto-memory is per project folder: sessions started in a scratch folder and
moved into the game write memory where the game never reads it. So:

- Standing agreements → `CLAUDE.md` *How we work*.
- Taste → `docs/bible.md` *Taste*.
- Decisions and reversals → `docs/handoff.md`.
- Unanswered questions → `docs/status.md` `open:`.
- Machine paths → `CLAUDE.local.md` (gitignored).

Save a memory too if you like, but the project files are the source of truth.
