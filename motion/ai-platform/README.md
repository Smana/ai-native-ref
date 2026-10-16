# AI Platform explainers

Short animated clips about the AI Platform, for LinkedIn and the docs. `POST.md` holds the
post caption draft. `out/` is ignored by git. The docs homepage serves a web encode from `website/static/media/` (see [Publish on the site](#publish-on-the-site)). Each clip is a
TypeScript scene drawn on a canvas, rendered frame by frame in headless Chromium and
encoded with ffmpeg. No Motion Canvas: npm access was not available when this was built,
so the project depends only on `typescript`, `tsx` and `playwright`.

Output: 1080×1350 (4:5), 30 fps, H.264, no audio, captions burned in. The last frame
crossfades to the first, so the clip loops.

## Render

```bash
cd motion/ai-platform
npm install                      # typescript, tsx, playwright
npx playwright install chromium  # once; a browser download
npm run render                   # → out/agent-factory.mp4
```

`ffmpeg` must be on your PATH (`brew install ffmpeg`). The logo is read from
`website/static/images/ogenki-mark-white.svg` at render time; nothing under `website/`
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

The homepage hero plays a 720×900 web encode, with the opening frame as its poster:

```bash
ffmpeg -i out/agent-factory.mp4 -vf scale=720:900 -c:v libx264 -crf 26 -preset slow \
  -pix_fmt yuv420p -movflags +faststart -an ../../website/static/media/agent-factory.mp4
ffmpeg -i out/agent-factory-0.00s.png -vf scale=720:900 -q:v 3 ../../website/static/media/agent-factory-poster.jpg
```

## Change the clip

Most edits need no engine knowledge:

| To change… | Edit |
|---|---|
| Timings, captions, node wording, the URL | `src/scenes/agent-factory.storyboard.ts` |
| Colours, fonts, canvas size | `src/components/theme.ts` |
| An icon | `assets/icons/glyphs/<name>.svg`, then copy it to `assets/icons/` (see the README there) |
| Positions and choreography | `src/scenes/agent-factory.ts` |

Beats are named (`hook`, `intake`, `identity`, `pr`, `outro`). Each has a
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

Conventions: cyan is the platform, amber is reserved for planned work, grey is humans and third
parties (GitHub). Dim what is no longer the active path; keep at most ten nodes on screen.
