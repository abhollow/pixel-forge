# Pixel Forge

**Make a retro pixel-art game from scratch — from the first idea to a shipped
build — with Claude, Godot 4 and Magnific.**

Pixel Forge is a Claude Code plugin. It turns Claude into a game-dev partner
that knows the whole road: talking an idea out, researching comparable games,
cutting scope, locking a design, generating art and converting it into real
sprites, building in Godot, playtesting, iterating, debugging, and shipping to
phones and stores. Every step has a process, a template, or a tool behind it.

**New here? Start with the one-page [User Guide](USER-GUIDE.md)** — install,
setup and your first game, on a fresh machine.

- **1 skill** that Claude loads whenever you work on your game
- **13 commands** for the rituals of a project (`/pixel-forge:start`, `/pixel-forge:round`, `/pixel-forge:ship`, …)
- **4 helper agents** (screenshot review, code review, market research, balance analysis)
- **~30 tools** for art, audio and testing, plus **Godot templates** and a project scaffold
- An optional **Idea → Launch tracker** for all your projects

## How a game goes

| Stage | What Pixel Forge does |
|---|---|
| **Idea → Concept** | `/pixel-forge:start` talks the idea out with you, searches the web for comparable games, finds the gap, cuts scope, and writes `docs/concept.md` |
| **Design** | `/pixel-forge:new-project` scaffolds a Godot project already tuned for crisp pixel art on phones, with a working brief for Claude (`CLAUDE.md`), a design bible, a decision log, a status file, an asset ledger, a smoke test, a screenshot harness and CI |
| **Prototype → Core** | `/pixel-forge:round` runs each agreed batch of work: build → test → render and *look* → log the decision → commit. Architecture patterns keep "make it feel alive" work from breaking game balance |
| **Art & content** | `/pixel-forge:art`: mood frames → style anchor → Magnific generation with prompts that work → download → side-by-side comparison at game scale → keying, despill, cutting, palettes → one-command rebuilds, 2x detail sets, big-map stitching, animation checks |
| **Audio** | Placeholder SFX presets and synthesized music from day one; recipes for generating real SFX and music; loudness and re-encoding tools |
| **Playtest & iterate** | `/pixel-forge:playtest` turns your playtest notes into numbered changes; optional bot playtests for balance; capture, motion-watch and phone-preview harnesses so Claude can see the game |
| **Debug & polish** | `/pixel-forge:debug` (reproduce → measure → fix → prove), `/pixel-forge:optimize` (parallel code reviewers), and a long list of Godot gotchas with fixes |
| **Ship & launch** | `/pixel-forge:ship` (a release checklist built from things that commonly slip), `/pixel-forge:pitch` (one-page pitch from real screenshots), store-asset and launch guidance |
| **Every session** | `/pixel-forge:status`, and a hook that resumes each session from the project's own docs |

## Install

### Claude Code (full package — recommended)

```
/plugin marketplace add abhollow/pixel-forge
/plugin install pixel-forge@pixel-forge
```

Then open a folder for your game and run:

```
/pixel-forge:doctor        # checks Python, Godot, git, ffmpeg, Magnific
/pixel-forge:start         # tell it your idea
```

**Update:** `/plugin marketplace update pixel-forge`, then update the plugin
from `/plugin` → Installed (or turn on auto-update for this marketplace).

### claude.ai / Claude desktop chat (skill only)

Download `pixel-forge-skill.zip` from the [latest release](https://github.com/abhollow/pixel-forge/releases/latest)
(or build it: `python tools/build_skill_zip.py`) and upload it under
**Customize → Skills**. Code execution must be on. Commands, agents, the hook
and the tracker are Claude Code features; in chat, ask for the same workflows
by name ("run the round checklist").

### What you need

| | |
|---|---|
| **Godot 4.3+** | Standard (not .NET) build. On Windows, CLI runs use the `_console.exe`. |
| **Python 3.9+** | With Pillow and numpy (`python -m pip install pillow numpy scipy`; scipy optional). |
| **Magnific MCP** | For image, music and sound generation — add `https://mcp.magnific.com` as a connector and sign in. Generation uses your Magnific credits. |
| Optional | git + GitHub CLI, ffmpeg, Node.js (for the Godot MCP). |

`/pixel-forge:doctor` checks all of it and tells you how to install what's
missing. Full setup guide: [`setup.md`](plugins/pixel-forge/skills/pixel-forge/references/setup.md).

## Commands

| Command | |
|---|---|
| `/pixel-forge:start` | New idea → concept |
| `/pixel-forge:new-project` | Scaffold the game |
| `/pixel-forge:status` | Stage, exit criterion, next three tasks, open questions |
| `/pixel-forge:round` | Run an agreed batch of work end to end |
| `/pixel-forge:art` | One asset or batch through the art pipeline |
| `/pixel-forge:playtest` | Prepare a playtest, turn feedback into changes, or run bots |
| `/pixel-forge:debug` | Disciplined bug fix |
| `/pixel-forge:scope` | Analysis only — options, costs, recommendation, no code |
| `/pixel-forge:optimize` | End-game review and optimization pass |
| `/pixel-forge:ship` | Release checklist and build |
| `/pixel-forge:pitch` | One-page pitch from real screenshots and numbers |
| `/pixel-forge:retro` | Post-mortem, and proposals to improve Pixel Forge |
| `/pixel-forge:doctor` | Check your tools; refresh a game's vendored scripts |
| `/pixel-forge:tracker-setup` | Set up the Idea → Launch tracker |

Agents: `visual-qa`, `code-reviewer`, `game-researcher`, `balance-analyst`.

## The stages

Every project moves through one shared stage table. Claude always tells you
which stage you're in and what finishes it.

| Stage | % | Done when |
|---|---|---|
| Idea | 0–9 | One paragraph captured |
| Concept | 10–19 | Pitch, hook, comparables, scoped feature list |
| Design | 20–34 | Bible locked, screen settings chosen, style direction picked |
| Prototype | 35–49 | Grey-box loop playable and playtested |
| Core build | 50–64 | Core loop end to end; art direction locked |
| Art & content | 65–79 | Every asset at "acceptable"; content lives in data |
| Polish & test | 80–89 | Full session with no placeholders; human playtests done |
| Launch prep | 90–99 | Signed release build, store page, screenshots/trailer |
| Shipped | 100 | Public release |

## Repo layout

```
.claude-plugin/marketplace.json     this repo is a plugin marketplace
plugins/pixel-forge/                the plugin
  skills/pixel-forge/               the main skill (also zipped for claude.ai)
    SKILL.md  references/  scripts/  assets/{godot,shaders,project}/
  skills/<command>/SKILL.md         the slash commands
  agents/  hooks/  tracker/
docs/                               STEERING.md, ARCHITECTURE.md
tools/                              build_skill_zip.py, check_package.py
tests/                              tests for the Python tools
```

## Contributing

Pixel Forge improves with every game made with it. Run `/pixel-forge:retro`
at a milestone; it writes proposals for this repo. See
[docs/STEERING.md](docs/STEERING.md) for where changes go and how to test and
release them. Issues and pull requests welcome.

## License

[MIT](LICENSE)
