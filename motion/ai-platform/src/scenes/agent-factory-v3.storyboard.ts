// The editable part of the v3 clip: beats, timings and wording.
// Wrap words in **…** to accent them; \u00a0 keeps two words on one line.

import type { Beat } from './beat.js';

// No title card: the clip is meant for a docs page, where the heading does that job.
// Beats map to the runbook layers: scoper (1), judge and loop policy (2), search (4),
// splitter (5), tester (6).

export const labels = {
  cluster: 'Kubernetes',
  maintainer: { title: 'Maintainer', sub: 'labels · approves · merges' },
  github: { title: 'GitHub', sub: 'issue · pull request' },
  readyLabel: 'factory/ready',
  scoper: { title: 'Scoper', sub: 'read-only · before any code' },
  task: { title: 'Bounded task', sub: 'touches · plan · acceptance checks' },
  parts: ['Part 1', 'Part 2', 'Part 3'],
  splitCommand: '/factory split',
  implementer: { title: 'Implementer', sandbox: 'gVisor sandbox', inside: 'one writer · one branch' },
  search: { title: 'Search', sub: ['in-process', 'read-only'] },
  checks: 'runs the repo checks before pushing',
  tester: 'Tester \u00b7 test first',
  needsAuthor: 'factory/needs-author',
  legend: 'docs: scoper \u00b7 judge \u00b7 search  |  scripts: scoper \u00b7 split \u00b7 judge  |  docs-links: implementer \u2192 gate',
  stall: 'no commit by step N → stop',
  judge: { title: 'Judge', sub: 'a call, not a run · no tools' },
  verdicts: 'met · not yet · impossible',
  reviewer: { title: 'Reviewer', sub: 'fresh context · the diff, not the story' },
  evidence: 'cites the checks\u2019 output',
  gate: { title: 'Merge gate', sub: 'holdout checks · low-risk classes only' },
  edges: {
    label: 'labels issue',
    review: 'approves ·\nmerges',
    question: 'one question to the author',
    oneAtATime: 'next part after the merge',
    finished: 'finished',
    notYet: 'not yet',
    met: 'met',
    pr: 'merge · low-risk\nclasses only',
    openPR: 'branch · PR',
    escalate: 'escalates to\na maintainer',
  },
};

export const beats = {
  scoper: {
    start: 0,
    end: 7,
    caption: 'Before any code, a **scoper** bounds the task. Or asks the author **one\u00a0question**.',
  } as Beat,
  split: {
    start: 7,
    end: 13,
    caption: 'Too big? **Split** into parts a maintainer approves, landed **one\u00a0by\u00a0one**.',
  } as Beat,
  implement: {
    start: 13,
    end: 20,
    caption: 'The implementer runs the repo\u2019s **own\u00a0checks**, asks **search** and **stops if it wanders**.',
  } as Beat,
  judge: {
    start: 20,
    end: 27,
    caption: 'A fresh-context **judge** says done. A fresh-context **reviewer** cites the **checks**.',
  } as Beat,
  outro: {
    start: 27,
    end: 33,
    caption: 'Each stage is a per-class switch. **Only link fixes and reverts merge without a human.**',
  } as Beat,
};

/** The last second fades to the background, so the loop restarts on an empty cluster. */
export const duration = beats.outro.end;
