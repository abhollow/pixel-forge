# Design patterns that playtest well

Patterns for unit length, goals, difficulty, events, fairness, onboarding and
UI that hold up when a real player plays on a real phone. Complements
`game-loop-patterns.md`.

## Contents
1. Session length, and the lever that sets it
2. One visible goal
3. Adaptive difficulty
4. One new thing per level
5. Events: telegraph, scale, reward
6. Fairness
7. Onboarding: intro cards and a tutorial
8. The finale
9. Make everything a knob
10. Balance lessons
11. Scarcity, idling and self-running worlds
12. Readable UI

---

## 1. Session length, and the lever that sets it

Mobile sessions run about **5 minutes** (GameAnalytics 2025 benchmarks:
median-tier games 5-6 min, top-tier 8-9). A playable unit -- a round, a stage,
a level -- should fit one sitting, and the save should let the player stop
cleanly after any unit.

If the unit ends on a **target** (earn N credits), its length is target ÷
earning rate. To change length, change the **rate** (pay per unit), not the
target: the unit earns the same total, so upgrade prices and shop pacing stay
balanced. Lowering targets instead halves income and doubles how long every
upgrade takes. Expect to try a few rates before it feels right: short enough
for a session, with enough work behind each upgrade.

## 2. One visible goal

A unit should end on **one condition the player can see**. Why: a unit that
needs credits AND a meter held above a target for a stretch (drawn as two
overlapping bars) can pass its credit target and simply not end -- a single
dip resets the second condition -- and the player reads it as broken. With one
goal (credits earned), put the tension somewhere visible: a fail countdown when
the meter hits zero, a bonus for a clean finish.

Count what's **earned**, not what's held: spending on upgrades never moves the
bar backwards, and skipping upgrades is no shortcut -- the player just earns
more slowly. So upgrades never need to be required.

## 3. Adaptive difficulty

Rather than hand-tuning every level:

| Outcome | Next attempt |
|---|---|
| Fail | 10% easier |
| Succeed first try | 6% harder |
| Succeed after failing | unchanged -- that was about right |

The uneven steps balance where ln(1/0.9) / (ln(1/0.9) + ln 1.06) ≈ **64%** of
units are cleared first try: mostly succeeding, still failing sometimes. Clamp
it (60-150%), carry it across levels (it measures the player, not the level),
save it, and tell the player ("the next attempt will be a little gentler").

## 4. One new thing per level

Each level introduces **one** new rule, on familiar ground where possible
(reuse the previous level's layout so the new rule is the only new thing).
Give every level a **core mechanic** plus a **signature event**, for example:

slippery ground + a thaw · darkness + a dawn that lifts it · moving platforms
+ a collapse · conveyor belts + a jam · a second enemy type + an ambush · a
split map + a bridge that opens · low gravity + a meteor shower · a finale arc
that combines the earlier rules.

Brainstorm 2-3 options per level and let the user choose; build a rough,
playtest, revise, approve, move on (see `production-playbook.md`).

## 5. Events: telegraph, scale, reward

- **Telegraph the danger.** Countable small warnings before the big hit; a
  sound cue before an obstacle appears; a hazard visibly drifting in for 20 s.
  A countable rhythm ("count the small ones, get out before the big one")
  turns an annoyance into a skill.
- **Scale events by stage.** The same event can affect, say, 20% / 30% / 60% /
  80% of loose items across stages 1-4 -- light before the player has gear,
  heavy once they own it. A flat 50% can be an instant loss in stage 1.
- **Give some events a positive goal.** Something to protect that needs its
  path cleared ("clear the way HERE, now") gives a different kind of urgency
  from another hazard -- and can pay out per item saved.
- **Gate events on gear where they'd be unfair.** A hazard that needs an
  upgrade to handle waits until the player owns it, arriving ~25 s after the
  purchase (not the next frame, which feels like a punishment).
- **A timed event must wait for its participants.** End it when everyone's
  done *or* time runs out -- not when nothing is moving (blocked counts as going).

## 6. Fairness

- The player can't avoid what they can't see: in darkness, give moving hazards
  a light of their own; keep the goal readable.
- Layout mustn't punish: a drop-off point on one edge of a round map makes the
  far side the longest trip every time. At the centre, every side is equal.
- Upgrades should visibly transform a level, not just speed it up: a top-tier
  vehicle that ignores the level's hazard, crosses its obstacle and lights the
  dark.
- If an upgrade feels optional, its threat is too small: a hazard active for
  12% of a unit makes its counter-upgrade feel useless; at ~33% of the unit
  with a strong slowdown, the upgrade becomes essential.

## 7. Onboarding: intro cards and a tutorial

- **An intro card per level** -- the level name in the title font over that
  level's art, one line on what's new, and a START button the player must tap.
  A new level is a reward the player should see, and a new rule deserves warning.
- **A short read-and-tap tutorial** on a new game: each step spotlights one
  thing (dim everything else, gold ring), with the tip card on the opposite
  side so it never covers its subject; NEXT, SKIP, and a final START button.
  Pause the game behind it and stage a small scene for the steps to point at.
  Basics only -- each level's twist belongs on its intro card.

## 8. The finale

End on a finale that **conducts systems the player already knows** through
one arc per stage, with a calm breather midway and one learned rule
**reversing** after it (a push that changes direction, safe ground that turns
dangerous), so every learned habit is backwards for the climax. Drive a
finale's phases by **progress through the unit**, not the clock, so the climax
always lands at the end however long the player takes.

## 9. Make everything a knob

Keep every level's tuning in one data table (strengths, timers, shares per
stage), with the reasoning in comments and in a per-level doc. Playtest
feedback like "a little stronger" or "split the difference" becomes a
one-number change, never a rewrite.

## 10. Balance lessons

Each of these is a common bug in a tuned game, usually found by a bot pass or
a human.

- **Count what matters.** A hazard capped by *groups* lets far more units
  through once late groups hold several units each. Cap by units.
- **Thresholds scale with what they judge.** A fixed "the level is a mess" line
  while the item cap grows means later stages start over the line.
- **Retry easing must hit the binding constraint.** Slowing spawns does nothing
  once the field is at its cap; ease the cap.
- **A punishing mechanic needs a recovery skill.** If spilling the load as tiny
  specks takes longer to re-gather (~14 s) than the fail meter takes to
  collapse (~9 s), the player can't recover. Fixes: drop a few big piles near
  the hit, no gathering while stunned, and a **2 s post-hit grace** with a soft
  blink to break hit loops.
- **Kept gear shortens later units.** Upgrades retained across levels can cut
  later units from ~5 min to ~2. Scale the target by what the player already
  owns that the shop wouldn't yet sell, held back on the hardest units.
- **Group the beginner knobs.** One `beginner` block on level 1 (slower
  threats, longer fail grace, fewer enemies); adaptive difficulty eases 20%
  there instead of 10%. Clearing first time still ramps, so strong players
  don't coast.
- **Event taxonomy.** Give each class of event one consistent consequence
  (e.g. characters make you drop your load; objects only knock you back).
  One-off events once per level, in a named unit, at a random time inside a
  window. Purely cosmetic events are welcome.
- **Impact analysis before adding to a tuned economy.** If upgrades map one per
  level, an extra upgrade creates a phantom level; make it something else
  (e.g. a hire or consumable re-bought each level).
- **Derive ranges from named constants**, never from collision shapes —
  shrinking a vehicle's hitbox would silently shrink its pickup range.
- **Revert changes that don't help**, the same session, and measure the real
  driver.
- **Combined multipliers need caps** (e.g. hazard drift × late-stage intensity).

## 11. Scarcity, idling and self-running worlds

- **Find the load-bearing scarcity and guard it.** If one currency is the only
  thing the player spends, idle income breaks the game. The fix: a trickle only
  while the player can't afford anything (a soft-lock guard), never as a
  reward for waiting.
- **Taps vs powers.** Taps are free and take only what is ready; powers cost
  currency and do what a tap can't. A free action saves waiting; a paid action
  must do something the free one can't (bulk, early, at range).
- **A world that runs without the player** -- settlements that feed and build
  on their own while the player steps in -- makes a better loop than a chore
  list. It only stays balanced if the visual life layer never touches the
  rules (`architecture.md`).
- **Ramp pressure by progress, not the clock.** A within-unit ramp that follows
  credits earned self-balances against gear.
- **Exploits hide in punishments.** Destroying the load on a hit makes a
  collision a free way to clear the field; scatter the load back instead.

## 12. Readable UI

- **Show only what the player acts on.** Secondary stats keep running
  underneath; they surface as warnings when they matter.
- **Indicators only when something is neglected** — status icons appear after
  ~8 s unattended, small and subtle.
- **Notices stay up by length**: 1.5 s + 0.065 s per character, clamped 3–11 s.
  Information the player asked for is pinned above news.
- **Show what changed**: hold a bar change ~1 s and flash it, so the player sees
  which act caused it.
- **Two-tap placement**: a ghost tinted red, tap again to confirm. Destructive
  menu actions also take two taps ("TAP AGAIN TO ERASE"), only when there is
  something to lose.
- **Remove indicators the art already gives** — a "ready" pulse is redundant
  when the sprite already shows it's ready. Cryptic labels are design bugs.
- **You hit what you see**: a tap anywhere on a building's picture hits it,
  front-most where pictures overlap; tap rects cover the whole sprite, not the
  footprint.
- **Minimal, semi-transparent panels**; the one number that matters (the main
  currency) is prominent and polished.
- **Tap vs drag**: a few pixels of slop (`TAP_SLOP` 4 px) so scrolling never
  triggers an action.
