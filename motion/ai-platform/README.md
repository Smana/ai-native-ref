# AI Platform explainers

Short animated clips about the Agent Factory, the bundle of open-source tools (Maku, agentgateway, OpenHands, gVisor, octo-sts…) behind the AI Platform, for LinkedIn and the docs. `POST.md` holds the
post caption draft. `out/` is ignored by git. The docs homepage serves a web encode from `website/static/media/` (see [Publish on the site](#publish-on-the-site)). Each clip is a
TypeScript scene drawn on a canvas, rendered frame by frame in headless Chromium and
encoded with ffmpeg. The project depends only on `typescript`, `tsx` and `playwright`.

Output: `agent-factory` is 1080×1350 (4:5, for the feed); `agent-factory-v3` is 1080×1280 with no
title card (for the docs). Both are 30 fps H.264, no audio, captions burned in. The last frame
crossfades to the first (v3 fades to an empty cluster), so the clip loops.

## Render

```bash
cd motion/ai-platform
npm install                      # typescript, tsx, playwright
npx playwright install chromium  # once; a browser download
npm run render                   # → out/agent-factory.mp4
```

`ffmpeg` must be on your PATH (`brew install ffmpeg`). The Ogenki logo is read from
`website/static/images/ogenki-mark-white.svg` at render time. The factory node's icon is the Maku mark (`assets/icons/factory.color.svg`, from the Maku brand kit); nothing under `website/`
is written.

Other commands:

```bash
npm run preview                        # interactive player at http://127.0.0.1:5173/?preview
npm run still -- 0,4.5,10              # PNG stills in out/
npm run render -- --from 4 --to 11     # a slice, for quick checks
npm run render -- --scene <name>       # another clip (see src/scenes/index.ts)
```

In the preview, space plays/pauses and the slider scrubs. The preview re-reads `build/`
on reload, so run `npm run build` after an edit.

## Publish on the site

The site plays a 720-wide web encode of each clip, with a poster named after it
(`static/media/<clip>.mp4` and `<clip>-poster.jpg`). Scale with `-2`, never a fixed height: a fixed
`720:900` stretches the 1080×1280 v3 clip. v1's poster is its opening frame; v3's first frame is an
empty grid, so its poster is taken at 26 s, when the diagram is complete:

```bash
CLIP=agent-factory-v3   # or agent-factory
ffmpeg -i out/$CLIP.mp4 -vf scale=720:-2 -c:v libx264 -crf 26 -preset slow \
  -pix_fmt yuv420p -movflags +faststart -an ../../website/static/media/$CLIP.mp4
ffmpeg -ss 26 -i out/$CLIP.mp4 -frames:v 1 -vf scale=720:-2 -q:v 3 ../../website/static/media/$CLIP-poster.jpg  # v1: -ss 0
```

Embed a clip with the `hero-video` shortcode: `{{< hero-video clip="agent-factory-v3" width="720"
height="854" alt="…" />}}` (self-closed: the clip alone, for a docs page; with inner content it is the homepage
hero). The `alt` text sits under the clip. Under `prefers-reduced-motion` only the poster shows.

`task check` does not cover `motion/`. The evidence for a clip change is `npm ci && npm run build`
and stills (`npm run still -- 3,10,17,24,30 --scene agent-factory-v3`) looked at one by one.

## Change the clip

Most edits need no engine knowledge:

| To change… | Edit |
|---|---|
| Timings, captions, node wording, the URL | `src/scenes/<clip>.storyboard.ts` |
| Colours, fonts, canvas size | `src/components/theme.ts` |
| An icon | `assets/icons/glyphs/<name>.svg`, then copy it to `assets/icons/` (see the README there) |
| Positions and choreography | `src/scenes/<clip>.ts` |

| Clip | Scene | Length | Made for |
|---|---|---|---|
| `agent-factory` | v1/v2, one task end to end, with a title card | 32 s | the feed and the homepage |
| `agent-factory-v3` | the scoper, the split, the loop policy and the judgement roles; no title card, 1080×1280, loops from an empty cluster | 33 s | the [run roles](../../website/content/docs/platform/ai-platform/agents/how-it-works/agents-and-merge-gate.md) page |

The v3 beats map to the harness runbook layers: `scoper` (0–7 s) is layer 1; `split` (7–13 s) is
layer 5, the splitter; `implement` (13–20 s) is layer 4 (search) plus the tester (layer 6, shown as a
`switch` pill) and the implementer's own checks; `judge` (20–27 s) is layer 2, the judge and the loop
policy, then the reviewer and the human approval; `outro` (27–33 s) is the merge gate, which merges
only low-risk classes. The legend line names which class runs which stage. Beats are named per clip (for example `hook`, `intake`, `identity`, `pr`, `outro`). Each has a
`start`, an `end` and a caption. The scene schedules every animation relative to its
beat's `start`, so moving a beat moves its contents.

Captions: wrap words in `**…**` to colour them with the beat's accent. Use ` `
(a non-breaking space) between words that must stay on one line.

Fonts: the theme asks for JetBrains Mono and Inter and falls back to DejaVu Sans Mono
and a system sans. Install JetBrains Mono for the intended look; the renderer uses
whatever the machine has.

## Make another clip

1. Copy `src/scenes/agent-factory.ts` and its `.storyboard.ts` under a new name.
2. Register it in `src/scenes/index.ts`.
3. `npm run render -- --scene <name>`.

Components, in `src/components/`:

| Component | What it is | Tracks |
|---|---|---|
| `Node` | A box: title, sublines, optional icon, optional dashed inner box or horizontal segments | `show`, `highlight`, `pulse`, `revealInner`, `revealSegments`, `segHighlight`, `dimAt` |
| `Edge` | A polyline arrow with a label; draws in, carries flowing dots and one-shot packets | `drawIn`, `flowOn/Off`, `packet(at, dur, text?)` |
| `Region` | A labelled area around nodes (a cluster, a half of the platform) | `show` traces the border |
| `Pill` | A small chip, with an optional leading tag such as `v2` | `show` |
| `Caption` | The burned-in caption band | `cue(text, from, to)` |
| `TitleCard` | The hook card; docks into a header and back | `dockAt`, `undockAt` |
| `Icon` | Generic glyphs, overridable by SVG files | — |

Every property is a `Track`: a list of keyframes evaluated as a pure function of time
(`src/engine/tween.ts`). Any frame renders independently, so stills and slices are exact.

Conventions: cyan is the run and the platform, violet is a judgement role (scoper, judge, reviewer),
amber is reserved for planned work, grey is humans and third parties (GitHub). Dim what is no longer the active path; keep at most ten nodes on screen.
