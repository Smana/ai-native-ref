// The editable part of the Agent Factory clip: beats, timings and wording.
// Shift a beat's `start` and everything in it moves; the drawing code in
// agent-factory.ts only knows beat names. Wrap words in **…** to accent them.

import type { Beat } from './beat.js';

export const title = {
  text: 'Agent Factory',
  subtitle: ['Agents you can hand work to,', 'not just sit next to.'],
  kicker: 'self-hosted · sandboxed · on Kubernetes',
  url: 'airef.ogenki.io',
  licence: 'Apache-2.0',
};

export const labels = {
  cluster: 'Kubernetes',
  maintainer: { title: 'Maintainer', sub: 'labels · reviews' },
  github: { title: 'GitHub', sub: 'issue · pull request' },
  readyLabel: 'factory/ready',
  room: { title: 'Room', sub: 'watch · steer' },
  factory: { title: 'Maku', sub: 'issue → task' },
  run: { title: 'Agent run', sandbox: 'gVisor sandbox', inside: 'coding agent · OpenHands' },
  gateway: { title: 'agentgateway', sub: 'per-run identity · budgets' },
  models: { title: 'Models', sub: 'Z.ai GLM · Claude' },
  tools: { title: 'MCP tools', sub: 'Flux · Victoria' },
  token: { title: 'GitHub token', sub: 'octo-sts' },
  edges: {
    label: 'labels issue',
    review: 'reviews ·\nmerges',
    open: 'opens',
    start: 'starts run',
    steer: 'events ·\nsteering',
    watch: 'watches · steers',
    call: 'every call',
    pr: 'branch · PR',
  },
};

export const beats = {
  hook: { start: 0, end: 4 } as Beat,
  intake: {
    start: 4,
    end: 11,
    caption: 'Label an issue. It becomes a **sandboxed\u00a0agent\u00a0run** you can watch and steer.',
  } as Beat,
  identity: {
    start: 11,
    end: 18,
    caption: 'Every call goes through a gateway under the run\u2019s **own\u00a0identity**, with a **budget**.',
  } as Beat,
  pr: {
    start: 18,
    end: 24,
    caption: 'The agent opens a **pull\u00a0request**. A **human review** decides the merge.',
  } as Beat,
  outro: {
    start: 24,
    end: 32,
    caption: 'Trusted, metered, audited, stoppable. **Agents a team can hand work to.**',
  } as Beat,
};

/** Total length. The last frame crossfades back to the hook, so the clip loops. */
export const duration = beats.outro.end;
