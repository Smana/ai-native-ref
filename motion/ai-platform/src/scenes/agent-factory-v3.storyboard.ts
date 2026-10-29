// The editable part of the v3 clip: beats, timings and wording.
// Wrap words in **…** to accent them; \u00a0 keeps two words on one line.

import type { Beat } from './agent-factory.storyboard.js';

// No title card: the clip is meant for a docs page, where the heading does that job.
export const title = { url: 'airef.ogenki.io', licence: 'Apache-2.0' };

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
  search: { title: 'Search', sub: 'fresh context' },
  checks: 'runs the repo checks before pushing',
  stall: 'no commit by step 80 → stop',
  judge: { title: 'Judge', sub: 'fresh context · no tools' },
  verdicts: 'met · not yet · impossible',
  reviewer: { title: 'Reviewer', sub: 'never reads the transcript' },
  evidence: 'evidence, or abstain',
  gate: { title: 'Merge gate', sub: 'holdout checks · one lane at a time' },
  edges: {
    label: 'labels issue',
    review: 'reviews ·\nmerges',
    question: 'one question to the author',
    scope: 'scope',
    oneAtATime: 'one at a time',
    finished: 'finished',
    notYet: 'not yet',
    met: 'met',
    pr: 'PR · merge',
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
    caption: 'The implementer runs the repo\u2019s **own\u00a0checks**, asks a **search\u00a0helper**, and **stops if it wanders**.',
  } as Beat,
  judge: {
    start: 20,
    end: 27,
    caption: 'An independent **judge** says done. A reviewer that never saw the transcript needs **evidence**.',
  } as Beat,
  outro: {
    start: 27,
    end: 33,
    caption: 'Every switch off by default. **Each lane earns lights-out on evidence.**',
  } as Beat,
};

/** The last second fades to the background, so the loop restarts on an empty cluster. */
export const duration = beats.outro.end;
