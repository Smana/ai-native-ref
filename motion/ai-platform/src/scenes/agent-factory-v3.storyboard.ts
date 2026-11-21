// The editable part of the roles clip (Agent Factory v4): beats, timings and wording.
// Wrap words in **…** to accent them;   keeps two words on one line.

import type { Beat } from './beat.js';

// No title card: the clip is meant for a docs page, where the heading does that job.
// A workflow picks the roles (quick, standard, careful); the merge gate ends every task.

export const labels = {
  cluster: 'Kubernetes',
  maintainer: { title: 'Maintainer', sub: 'labels · approves' },
  github: { title: 'GitHub', sub: 'issue · pull request' },
  readyLabel: 'factory/ready',
  workflows: ['quick', 'standard', 'careful'],
  picks: ['workflow:quick', 'default', 'workflow:careful'],
  scoper: { title: 'Scoper', sub: 'read-only · bounds the task' },
  author: { title: 'Author', sub: 'one question' },
  tester: 'Tester · failing tests first',
  testerTag: 'if testFirst',
  implementer: { title: 'Implementer', sandbox: 'gVisor sandbox', inside: 'one branch: agent/<task>' },
  checks: 'runs the repo’s checks before pushing',
  search: { title: 'Search', sub: 'read-only' },
  judge: { title: 'Judge', sub: 'a call, not a run' },
  verdicts: 'met · not yet',
  reviewer: { title: 'Reviewer', sub: 'fresh context · the diff, not the story' },
  gate: { title: 'Merge gate', sub: 'maku/merge-gate · reads the diff' },
  policies: {
    live: 'live → merges · daily cap',
    shadow: 'shadow → records only',
    human: 'else → one approval merges',
  },
  edges: {
    label: 'labels issue',
    review: 'approves =\nthe merge',
    task: 'bounded task',
    pr: 'merger App\nmerges',
  },
};

export const beats = {
  intake: {
    start: 0,
    end: 4.5,
    caption: 'A **workflow** picks the roles: from the handoff form, a **label** or the repository’s default.',
  } as Beat,
  quick: {
    start: 4.5,
    end: 9,
    caption: '**quick**: the implementer alone. Small, obvious fixes and scheduled tasks.',
  } as Beat,
  standard: {
    start: 9,
    end: 14,
    caption: '**standard**, the default: the implementer, then a fresh-context **reviewer**.',
  } as Beat,
  scope: {
    start: 14,
    end: 20.5,
    caption: '**careful**: a **scoper** bounds the task first, or asks the author **one question**.',
  } as Beat,
  build: {
    start: 20.5,
    end: 26,
    caption: 'The implementer **searches** the repo; a **judge** call says done before the reviewer.',
  } as Beat,
  gate: {
    start: 26,
    end: 34,
    caption: 'Policies judge the **diff**. A **live** policy merges alone; otherwise **one approval** merges.',
  } as Beat,
};

/** The last second fades to the background, so the loop restarts on an empty cluster. */
export const duration = beats.gate.end;
