# Stage 1: Concept and research

Read this the moment a user brings a game idea, however casually. Do not
start designing or generating art before working through it.

The failure mode this prevents: someone spends three months building a
competent game that nobody wants, because the concept was never tested
against what already exists.

---

## The shape of this stage

```
raw idea → research comparables → find the gap → sharpen the hook
   → scope it down → one-line pitch → exit to the bible
```

**Exit criterion:** a one-sentence pitch the user can say out loud, a named
hook, and a scoped feature list that fits their real available time — written
to `docs/concept.md`. (Tracker stages: Idea 0–9, Concept 10–19.)

`/pixel-forge:start` walks this stage.

---

## 1. Take the idea seriously, then interrogate it

Start by getting the idea out of their head in their own words. Then ask,
in roughly this order:

1. **What's the moment?** Describe the single most satisfying five seconds
   of play. If they can't, that's the first thing to find.
2. **Why this and not the obvious comparable?** What does a player get here
   that they don't get from the nearest existing game?
3. **How long is a session, and why would they open it again tomorrow?**
4. **What's the constraint?** Time available, skill level, budget, deadline.
   This determines scope more than taste does.

Don't fix the idea yet. Collect it. Quote the moment back to them and write
it into `docs/handoff.md` §1 — it is the yardstick for every later cut.

Ways to get a quiet idea talking:

- **Name the tradition, not the port.** "A tower-defence game in the
  tradition of the genre's classics" is a direction; a port of a named game
  is an IP problem. Say so early.
- **Ask what they loved in the games they name.** Why: the part they loved is
  the part to keep — and anything expensive that isn't it (a companion
  character, a crafting tree) becomes cuttable.
- **Use their other projects.** If they have earlier games, offer to reuse
  what worked — input handling (drag-to-scroll, a tap/drag split), camera
  code and a test harness can carry over in the first hour.
- **Offer two or three concrete shapes** when they are stuck, each in one
  line, with a recommendation.

## 2. Research the comparables — actually search

Use web search. Don't answer from memory: the indie 2D landscape shifts
constantly, and what charted two years ago isn't what charts now.

Search for:

- The nearest three to five comparable games, by mechanic rather than by
  theme. "Garden-tidying game" is a theme; "incremental resource gathering
  with tool upgrades" is the mechanic, and the mechanic is what to research.
- What reviewers and players actually praised and complained about in those
  games — store reviews and community threads are more useful than
  marketing copy.
- Whether the sub-genre is currently crowded, and what the recent entrants
  did differently.
- For mobile specifically: monetization norms in that sub-genre, because
  they shape design (an ad-gated game is designed differently from a
  premium one).

Then report back concretely. Not "roguelikes are popular" but "these four
games do X; three of them solve problem Y the same way; none of them do Z."

## 3. What tends to work in small 2D games

Patterns worth testing an idea against. They're heuristics, not laws — a
game can succeed by breaking any of them, but it should break them on
purpose.

| Pattern | Why it works |
|---|---|
| **One legible hook** | If the pitch needs two sentences, it's hard to share and hard to market. |
| **A five-second loop inside a five-minute loop inside a five-hour arc** | Nested loops give both moment-to-moment satisfaction and a reason to return. |
| **Visible progress** | Numbers going up, a map filling in, tools improving. Especially true for the gather/upgrade genre. |
| **Readable at a glance** | Small screens, brief sessions. If a player can't tell what's happening in a screenshot, they won't install. |
| **A strong first 60 seconds** | Most players who quit do it before the first meaningful choice. Front-load an early win. |
| **Distinct visual identity** | Locked palette, consistent perspective, one memorable silhouette. This is what makes a screenshot stop a thumb. |
| **Finishable scope** | A shipped small game beats an unshipped large one, every time. |

Anti-patterns in first projects: multiplayer, procedural generation as a
core pillar, story-heavy content, open-ended sandboxes, and anything where
the fun depends on content volume rather than on the loop.

## 4. Find the gap, sharpen the hook

The goal is a concept that is **either** genuinely novel **or** a familiar
form executed unusually well — and much better if both.

Three moves that usually get there:

- **Recombine.** Take a proven loop and swap its context or its verb.
  Familiar enough to be legible, fresh enough to be interesting.
- **Subtract.** Take a known genre and remove its defining friction —
  no fail state, no timer, no grind. "Genre X but relaxing" has worked
  repeatedly.
- **Specify.** Replace a generic setting with a very particular one.
  Specificity reads as authorship and gives marketing something to say.

Write the hook as one sentence with a subject, a verb, and a twist. If the
user can't say it out loud in a breath, it isn't done.

## 5. Cut the scope

Assume the first feature list is five to ten times too big. Be direct about
this; it is the most useful thing you'll say all project.

Sort every feature into:

- **Hook** — without this it's a different game. Usually two or three items.
- **Support** — makes the hook work. Keep the smallest set that does.
- **Later** — everything else. Write it in `docs/later.md`, which is a real
  file and a real place for good ideas to live without derailing the build.

Sanity check against the user's actual hours. A solo first project in
evenings and weekends is realistically a two-to-three month thing if the
scope is right. If the plan needs more, the plan is wrong, not the person.

## 6. Write it down

Produce a short concept doc at `docs/concept.md`:

```markdown
# <Title>

**Pitch:** one sentence.
**Hook:** the one thing that makes this worth playing.
**Loop:** 5 seconds / 5 minutes / 5 hours.
**Session:** how long, and why they return.
**Comparables:** 3-5 games, what each does well, where we differ.
**Audience:** who specifically.
**Scope:** hook / support / later.
**Risks:** the two things most likely to sink this.
```

(The scaffolder writes a fuller template with a moment line, a Cut column
and a risk/guard table.) Then lock the technical and visual decisions in
`docs/bible.md` (`project-docs.md`).

## 7. Talk out each system before building it

The concept names the loop; each system in it (economy, enemies, progression,
crafting) gets its own short design doc before code — `docs/templates/system.md`:
the model as tables, a proposed build order, and **Questions for the user**
with a recommendation each. Send it, build nothing, wait for **Decisions
(user, date)**. Why: this catches design changes no amount of coding would — a
risky choice that should pay *more*, a missing resource, an ability that
shouldn't be able to do something.

When the user changes direction mid-project (a pillar turns out to be more
than the team can build), treat it the same way: a short **Before | Now**
table, what is kept, what is shelved, then build.

## 8. Concept art and pitches at this stage

- A few **mood frames** (4 options, one call) are cheap and make the
  conversation concrete — but they are not production art. See
  `art-direction.md`.
- If the user wants a pitch for someone else, it is a **one-page** document
  unless they say otherwise (`launch-and-marketing.md` §pitch). Don't start
  designing the game inside the pitch.
- Flag IP: names, characters and mechanics owned by someone else. If the
  concept builds on another person's work, name the original author in the
  pitch.

---

## Handling a weak idea

Sometimes the research says the idea is thin. Say so, kindly and
specifically — which comparable already does it better, and why that
matters. Then offer two or three concrete reshapings rather than a flat no.
Almost every weak idea has a strong version one twist away, and finding it
is the job.

What not to do: agree enthusiastically and let them find out in three
months.
