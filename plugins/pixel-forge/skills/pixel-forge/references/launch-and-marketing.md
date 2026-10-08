# Stage 8: Launch and marketing

Marketing is a production stage, not an epilogue. A game nobody sees is
indistinguishable from a game that doesn't exist.

The single biggest marketing mistake in small games is starting at launch.
By then there's no audience to tell.

Platform rules, store requirements and which channels work change
constantly — **search the web** rather than answering from memory when
specifics matter.

---

## Start at stage 1, not stage 8

From the moment the concept is locked:

- **Pick a handle and hold it.** Same name across every platform.
- **Post progress from the beginning.** A GIF of grey-box prototyping is
  more interesting to other developers than a finished screenshot, and
  developers are the first audience that amplifies anything.
- **Keep a capture habit.** Record every time something new works. You
  cannot recreate the early-development footage later, and it's the most
  shareable material you'll ever have.
- **Name the game early** and check the name is searchable. A game named
  after a common word is invisible.

## Pitches and showcase pieces

Users often ask for these mid-project, to show where the game is at.
`/pixel-forge:pitch` builds one.

- **Match the format asked for.** A one-page pitch is one page. Don't design
  the game inside the pitch.
- **Real screenshots and real numbers only.** Capture with `tools/capture.gd`,
  crop with PIL, and pull the counts from the code (levels, units, upgrades,
  tracks, smoke checks). "Nothing is made up" is the point.
- **One-page PDF:** write HTML, print with headless Chrome
  (`chrome --headless --print-to-pdf=out.pdf --no-pdf-header-footer
  --virtual-time-budget=5000 page.html`), render a PNG of it, check the page
  count. Why: HTML and CSS lay out a page more easily than reportlab.
- **Slides:** in Claude Code with Artifacts, the Slides artifact type gives a
  shareable deck; otherwise a single HTML slide.
- **Concept art for a pitch** can be generated (painterly models at 2k suit
  it) — but if the art must illustrate a rule (an exact grid size, a precise
  count), fix it in PIL rather than re-rolling until the model gets it right.
- **Key art stills / wallpapers:** re-render the scene with its code-drawn
  layers (glow, snow) frozen in one frame, then nearest-upscale to 1920x1080,
  3840x2160 and 1080x1920.
- **Promo video:** if a video skill such as HyperFrames is installed, use it;
  feed it gameplay captures and the game's palette. Users may skip storyboard
  approval and ask for a one-shot render.
- **A menu over a live showcase world** (`architecture.md`) doubles as trailer
  footage.

## Positioning

Write these before writing any store copy:

1. **The one-liner.** Subject, verb, twist. Short enough to say out loud.
2. **The comparison.** "Like X, but Y." People understand new things only
   in terms of old things. Pick a comparable that's flattering and
   accurate.
3. **The audience.** Specifically who. "Casual players" is not an audience.
4. **The screenshot.** One image that communicates the hook with no text.
   If no such image exists, that's a design finding, not a marketing one.

## Store page

The store page is the product for most people who encounter it. Rough
priority of what converts:

| Element | Notes |
|---|---|
| **Icon** | Seen at tiny size. One shape, high contrast, no text. For a pixel game, nearest-upscale the real icon rather than drawing a separate hi-res one — a mismatched icon reads as a bait-and-switch. |
| **First screenshot** | Most people see only this one. It should show the hook mid-action, not a menu. |
| **First line of description** | Treated as a headline. The one-liner goes here. |
| **Video / preview** | Hook in the first three seconds, no logo intro, no build-up. |
| **Rest of the description** | Short paragraphs, concrete nouns. What you do, not how it made the developer feel. |

Screenshots for a pixel game should be captured at design resolution and
**nearest-upscaled** to the required size. A screen recording gives you a
bilinear-filtered, slightly soft image that undersells the art. The capture
harness (`assets/godot/capture.gd`) renders exact frames of staged scenes —
use it for every store screenshot.

## Channels that work for small 2D games

Pick two and do them properly. Five done badly is worth less than two done
well.

- **Short-form video.** Satisfying loops from a pixel game perform
  unusually well. Fifteen to thirty seconds, no narration needed, the hook
  visible immediately.
- **Communities for the genre.** Find the specific forums and subreddits
  where this sub-genre's players already are. Participate for weeks before
  posting your game; drive-by promotion gets ignored or removed.
- **Developer communities.** Screenshot-sharing days and devlog threads.
  This audience shares things, which is worth more than their direct
  installs.
- **Itch.io.** Low friction, a real discovery audience for pixel games, and
  a good place to put a free demo or prototype build well before launch.
- **Press and curators.** Small outlets and individual curators respond to
  short, specific, personal emails with a GIF attached. Mass mailshots
  don't work. Expect a low response rate and don't take it personally.
- **A demo.** For many small games the demo does more than any promotional
  post. It's the only marketing asset that is also the product.

Paid acquisition is almost never right for a first game — the economics
need a tuned monetization model and a lot of data.

## Launch

- **Soft launch first** if the platform allows it: one small region, a week,
  watch for crashes and early drop-off before the wider push.
- **Cluster the launch.** Store listing, video, community posts and any
  press outreach in the same 48 hours. Attention compounds; spread out, it
  dissipates.
- **Be present on launch day.** Answer every comment and review. Early
  responsiveness has an outsized effect on both ratings and word of mouth.
- **Have the first patch ready.** Something will be wrong. Shipping a fix
  within 48 hours converts a bad first impression into a good one.

## After launch

The launch spike is not the game's life. Most small games find their
audience gradually.

- **Watch where players stop.** If there's an analytics-free way to learn
  this — reviews, community posts, direct messages — use it. The first
  drop-off point is the highest-value thing you can fix.
- **Reviews are a feature backlog** written by people who cared enough to
  type. Read all of them.
- **Updates are marketing.** Each one is a legitimate reason to post again
  and a signal to the store's algorithm that the game is alive.
- **Write a post-mortem** while it's fresh: what worked, what didn't, what
  the next game should do differently. This is the highest-return hour in
  the whole project.

## Expectations

Be honest with the user about this. Most first games find a small audience.
That is the normal, expected outcome, and it is not failure — a shipped
game is a complete skill set proven end to end, and the second game starts
from a much better place than the first.

The developers who succeed are overwhelmingly the ones who shipped
something small, learned, and shipped again.
