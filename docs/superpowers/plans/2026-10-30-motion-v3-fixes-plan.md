# The v3 motion clip, the fixes before publishing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the v3 clip on `feat/motion-agent-factory-v3` so it says what the factory does: the
four high findings, the medium labels, the publishing defects, and the conventions; then build it
and attach stills to its pull request.

**Architecture:** Four tasks on the owner's branch. Task 1 is storyboard-only (words). Task 2 is
the scene (edges, pills, the tester). Task 3 is the README, POST.md and the shortcode. Task 4
builds, cuts stills, rebases and pushes. Nothing in `task check` covers `motion/`: the evidence
is `npm run build` and the stills.

**Tech Stack:** TypeScript on the repository's own canvas engine (`motion/ai-platform/src/engine`),
Node 22 (`npm ci`, `npm run build`, `npm run still`), ffmpeg for the published MP4.

**Spec:** [the harness roles design](../specs/2026-10-30-harness-roles-design.md), HR12; the
findings F1–F16, V1–V7, T, R and C are the study's section 6 and its note 06.

## Global Constraints

- **Branch:** `feat/motion-agent-factory-v3`, checked out in a worktree
  (`git worktree add /home/smana/Sources/ai-native-ref-motion-v3 feat/motion-agent-factory-v3`).
  Rebase onto a freshly fetched `origin/main` first (16 commits behind, no conflict). Commits go
  on the branch; the PR is the branch's.
- **Facts the clip must match** (from the docs at `origin/main`): the implementer opens the PR,
  then the reviewer runs; the gate merges `docs-links` and `revert` on the host unattended, every
  other class waits for a human (and, once the merge-gate human path lands, one approval merges);
  `docs-links` runs `solo` with no scoper, judge or reviewer; the `docs` row sets `stallSteps: 60`;
  the reviewer's L5 evidence/abstain is not built; the judge is a call, not a run; search runs
  inside the implementer; the tester sits between scoper and implementer behind `testFirst`.
- **Nine nodes on screen, at most ten.** Cyan is the run, violet the judgement roles, neutral the
  humans; amber means planned or shadow.
- **Naming.** Nothing on screen says "Maku"; "Agent Factory" is the product.
- **Commits** conventional, in English, no trailers.

---

### Task 1: The words (storyboard)

**Files:**
- Modify: `motion/ai-platform/src/scenes/agent-factory-v3.storyboard.ts`

- [ ] **Step 1: Replace the labels and captions**

| Key | From | To | Finding |
|---|---|---|---|
| `labels.stall` | `no commit by step 80 → stop` | `no commit by step N → stop` | F11 |
| `labels.judge.sub` | `fresh context · no tools` | `a call, not a run · no tools` | F8 |
| `labels.search.sub` | `fresh context` | `in-process · read-only` | F7 |
| `labels.reviewer.sub` | `never reads the transcript` | `fresh context · the diff, not the story` | F16 |
| `labels.evidence` | `evidence, or abstain` | `cites the checks' output` | F16 |
| `labels.gate.sub` | `holdout checks · one lane at a time` | `holdout checks · low-risk classes only` | F12 |
| `labels.edges.review` | `reviews ·\nmerges` | `approves ·\nmerges` | F1 |
| `labels.edges.pr` | `PR · merge` | `merge · low-risk classes only` | F1 |
| `labels.edges.oneAtATime` | `one at a time` | `next part after the merge` | F6 |
| new `labels.edges.openPR` | — | `branch · PR` | F1 |
| new `labels.edges.escalate` | — | `escalates to a maintainer` | F9 |
| new `labels.needsAuthor` | — | `factory/needs-author` | F10 |
| new `labels.tester` | — | `{ title: 'Tester', sub: 'failing test first · the contract' }` | F4 |
| new `labels.legend` | — | `docs: scoper · judge · search  ·  scripts: scoper · split · judge  ·  docs-links: implementer → gate` | F2, F5 |
| `beats.judge.caption` | `An independent **judge** says done. A reviewer that never saw the transcript needs **evidence**.` | `An independent **judge** says done. A reviewer that never saw the transcript reads the **diff** and cites the **checks**.` | F16, V7 (≤ 80 chars? 94: shorten to `A fresh-context **judge** says done. A fresh-context **reviewer** cites the **checks**.`) |
| `beats.outro.caption` | `Every switch off by default. **Each lane earns lights-out on evidence.**` | `Each stage is a per-class switch. **Only link fixes and reverts merge without a human.**` | F3 |
| `beats.implement.caption` | 90 chars | `The implementer runs the repo's **own checks**, asks a **search helper**, and **stops if it wanders**.` → keep, it is 88: shorten to `The implementer runs the repo's **own checks**, asks **search**, and **stops if it wanders**.` | V7 |

Also F11's `step N` is right because the row sets 60 on `docs` and 80 is the default; and the
`import type { Beat } from './agent-factory.storyboard.js'` becomes an import from a shared
`./beat.js` that both storyboards use (C).

- [ ] **Step 2: Commit**

```bash
git add motion/ai-platform/src/scenes/agent-factory-v3.storyboard.ts motion/ai-platform/src/scenes/beat.ts motion/ai-platform/src/scenes/agent-factory.storyboard.ts
git commit -m "fix(motion): the v3 clip's words: per-class switches, low-risk merges, the reviewer cites the checks"
```

### Task 2: The scene

**Files:**
- Modify: `motion/ai-platform/src/scenes/agent-factory-v3.ts`

- [ ] **Step 1: The edges and pills**

- **F1:** add `eOpenPR` from the implementer to GitHub (`[[820, 640], [1062, 640], [1062, 200], [1030, 200]]`, label `L.edges.openPR`), drawn in the implement beat; `ePR` keeps its route but its label is `L.edges.pr` ("merge · low-risk classes only") and it draws in the outro only; `eReview` is drawn in the judge beat (`eReview.drawIn(...)` then a packet, as the v1 scene does at its line ~166) so the human's approve-and-merge arrow exists.
- **F2, F5:** a `Caption`-sized legend line (`L.legend`, size 20, neutral) under the cluster label, shown from the implement beat on; or three `Pill`s with class names on the scoper, judge and gate nodes. Pick the legend line: one element, no new node.
- **F4:** a `Pill` `L.tester` (violet, `tag: 'switch'`) between the task and the implementer, at `[300, 548]`, shown in the implement beat; it stays a pill, so the node count stays at nine.
- **F9:** one dashed neutral edge from the judge's verdict tag region to the maintainer (`[[120, 865], [120, 300], [220, 300], [220, 270]]`, label `L.edges.escalate`), drawn when the `impossible` tag appears.
- **F10:** when the question edge draws, `task.dim()` (or set its alpha track to 0.35) and show a `Pill` `L.needsAuthor` (neutral) at `[220, 335]`; undim on the next beat.
- **V1, V2:** `subSize: 22` on the maintainer and scoper nodes (their subs overflow 380 px at 26).
- **V4, V5, V6:** move `verdictTag` to `[270, 1000]` (below the judge, not on `eJudge`'s head), `evidenceTag` to `[800, 1010]`, and `splitTag` to `[220, 300]`; add a short edge from `splitTag` to the parts (`[[220, 320], [220, 390]]`, neutral, dashed).
- **V7:** captions at size 36 and `maxWidth: 1000`.
- **C:** delete the unused `title` export, the unused `labels.edges.scope`; keep `height: 1280`, `offset` and the caption `y` as named constants at the top of the file (`CANVAS_H`, `OFFSET_Y`, `CAPTION_Y`) with one comment.

- [ ] **Step 2: Build and look**

Run: `cd motion/ai-platform && npm ci && npm run build && npm run still -- 3 --scene agent-factory-v3 && npm run still -- 10 --scene agent-factory-v3 && npm run still -- 17 --scene agent-factory-v3 && npm run still -- 24 --scene agent-factory-v3 && npm run still -- 30 --scene agent-factory-v3`
Expected: the build passes; in the stills no sub crosses its node border, no pill covers an
arrowhead, every caption is at most two lines, the PR edge leaves the implementer, the human
approve-and-merge edge exists in the judge beat, the legend reads.

- [ ] **Step 3: Commit**

```bash
git add motion/ai-platform/src/scenes/agent-factory-v3.ts
git commit -m "fix(motion): the v3 clip's edges: the PR from the implementer, the human merge drawn, the tester and the legend"
```

### Task 3: README, POST.md, the shortcode

**Files:**
- Modify: `motion/ai-platform/README.md`, `motion/ai-platform/POST.md`
- Modify: the site's video shortcode (`website/layouts/shortcodes/hero-video.html` or wherever `hero-video` lives: `grep -rn "hero-video" website/layouts`)

- [ ] **Step 1: The README**

- The dimensions paragraph (lines ~9–10): v1 is 1080×1350; v3 is 1080×1280 with no title card.
- The publish recipe (lines ~42–44): `scale=720:-2` (never `720:900`), the poster taken at 26 s
  (`-ss 26`), and the clip's own filename.
- The clips table: the v3 row names its scene, its duration (33 s) and its beats mapped to the
  runbook layers (1 scoper, 2 loop policy and judge, 4 search, 5 splitter, 6 tester), as the
  study's S1 suggests.
- `theme.ts`'s header comment: name both clips.

- [ ] **Step 2: POST.md and the shortcode**

POST.md gains a v3 section (one paragraph and the caption list). The shortcode takes the clip's
basename, an `alt` text and respects `prefers-reduced-motion` (a poster only), so both clips can
be embedded; `roles.md` embeds v3 under its mermaid, as the study's S5 suggests.

- [ ] **Step 3: Commit**

```bash
git add motion/ai-platform/README.md motion/ai-platform/POST.md website/layouts website/content/docs/platform/ai-platform/agents/roles.md
git commit -m "docs(motion): the v3 clip's publishing recipe, a generalised video shortcode, the clip on the roles page"
```

### Task 4: Build, stills, rebase, push

- [ ] **Step 1: The evidence**

Run: `cd motion/ai-platform && npm run build` and the five stills from Task 2 Step 2 again;
`~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-motion-v3` for the site change
(`roles.md`, the shortcode).
Expected: the build passes; `exit=0`.

- [ ] **Step 2: Push, PR**

```bash
git fetch origin && git rebase origin/main && git push --force-with-lease origin feat/motion-agent-factory-v3
gh pr create --title "feat(motion): agent-factory-v3 clip: the scoper, the split, the loop policy and the judgement roles" --body "<the storyboard and scene fixes F1–F16 and V1–V7; the publishing recipe; the stills attached; npm run build output>"
```

Attach the five stills to the PR description.

## Self-review

- **Spec coverage.** HR12's four high findings: F1 (Tasks 1–2), F2 (legend), F3 (outro caption),
  F16 (the reviewer labels and caption); the mediums F4–F10; the lows F11–F12; V1–V7; T (the
  poster); R (README, shortcode); C (the shared `Beat`, dead strings, named constants).
- **Not done on purpose:** no beat on the shadow gate (S7): the owner decides; no state tags
  (S3) beyond the tester's `switch` tag, since the clip now says which classes run what.
