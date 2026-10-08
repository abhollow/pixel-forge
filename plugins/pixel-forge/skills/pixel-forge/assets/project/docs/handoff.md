# {{GAME_NAME}} — decision log

Append-only. The point of this file is the "why not X" — the part that gets
lost. A new session reads the newest entries first; compaction-proof memory
lives here, not in chat.

**Status:** started {{DATE}}.

## 1. Origin

- The ask, in the user's words.
- The user's "most satisfying five seconds", quoted.
- IP notes (what this is "in the tradition of", not a port of).

## 2. Research findings

| Game | Finding | Consequence for us |
|---|---|---|
| | | |

**The gap:**

## 3. Design decisions, with rejected alternatives

Format: **Decision.** Reason. *Rejected:* X — because Y. *(user's call / assistant's call, offered for override)*

## 4. Open questions

(Move each to an entry below once answered.)

---

## Log

Each round appends one entry:

```
**YYYY-MM-DD — <round title> (user: "<short quote of the ask>").**
- What changed (constants named, files), and why.
- Rejected: <alternative> — <reason>.
- Who decided: user / assistant (offered for override).
- Tests: N smoke checks pass. Bot: <result, if run>. Renders: docs/screens/<names>.
- Known limits / worth your eye: ...
```

**{{DATE}} — Project created.**
- Scaffolded by Pixel Forge: Godot {{GODOT_VERSION}}, {{VIEW_W}}x{{VIEW_H}} at {{PIXEL_SCALE}}x, aspect {{ASPECT}}, {{ORIENTATION}}.
