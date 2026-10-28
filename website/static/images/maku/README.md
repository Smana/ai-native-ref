# Maku assets

The product marks and room screenshots used by the *Meet Maku* section of
[Agents](https://airef.ogenki.io/docs/platform/ai-platform/agents/).

Copied unmodified from [Smana/agent-platform](https://github.com/Smana/agent-platform), which owns
them. Do not redraw, recolour or rotate them: the brand rules in its
[`docs/naming.md`](https://github.com/Smana/agent-platform/blob/main/docs/naming.md#the-mark) and
[`docs/assets/brand/README.md`](https://github.com/Smana/agent-platform/blob/main/docs/assets/brand/README.md)
are authoritative.

| File | Source | Commit |
|---|---|---|
| `maku-mark-light.svg`, `maku-mark-dark.svg` | `docs/assets/brand/svg/` | `49153a7` (brand integration) |
| `room-light.png`, `room-dark.png` | `docs/assets/` | `d72f4d6` (live v0.29.3 frames) |

- **Which mark on which ground.** `maku-mark-light.svg` is the ink mark: it is for Paper or white
  grounds. `maku-mark-dark.svg` is the Paper mark: it is for Ink or Surface grounds.
- **Both variants ship, one is shown.** The site's theme toggle sets a class rather than the OS
  preference, so the pair is swapped in CSS (`.anr-maku`, in `assets/css/custom.css`) and not with
  `<picture media="(prefers-color-scheme: …)">`.
- **Screenshots are 1280×800**, of a real factory room (a public data class task), re-captured
  upstream from the demo that the section links to.
- **Licence.** agent-platform is Apache-2.0; the screenshots are of this platform's own web UI, and
  were taken on a room from this repository.

Re-syncing is a copy from that repository plus a `lastVerified` bump on the Agents page; nothing here
is generated at build time.
