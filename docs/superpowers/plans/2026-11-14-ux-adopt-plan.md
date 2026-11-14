# Six tools and a Slack thread that acts: adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** This platform runs Maku's six tools and the acting Slack thread, with its own config reduced to the values that differ from Maku's defaults, and each journey proven live on aws-0.

**Architecture:** Four ai-native-ref pull requests. The first changes only the generator and the gates, so it merges before any Maku release. The second adopts release N (the pin, the broker's start key, the notification default, the site pages). The third and fourth adopt release N+1 in two switch-ons, each behind an owner go: stop and retry, then answer. The pin lives in base, so both clouds' manifests change together; only aws-0 is validated live.

**Tech Stack:** Flux Kustomizations and HelmReleases, Kustomize overlays (`base`, `aws-0`, `gcp-0`), Python and shell suites under `scripts/ci/tests/`, Hugo for the site, `task` as the runner.

**Spec:** [the UX review design](../specs/2026-11-14-ux-review-design.md). The Maku side is [the Maku plan](2026-11-14-ux-maku-plan.md); "release N" and "release N+1" are its two releases.

## Global Constraints

- **Worktree.** Work in a git worktree branched from `origin/main`; rebase onto a freshly fetched `origin/main` before every push.
- **The evidence.** `task check`, never a claim without its output. Where a suite fails for a known local reason, run `task links docs sources` by hand and report both.
- **Clusters.** aws-0 and gcp-0 alternate; one is active at a time. Every live proof here runs on aws-0. gcp-0's copies change so they still decode under the shared pin, and are proven at gcp-0's next turn as the active cluster.
- **Release order.** No config key precedes the Maku release that decodes it, and no removed key outlives the release that refuses it. `scripts/ci/tests/test-maku-config-load.sh` loads every copy through the pinned tag and is the guard.
- **One declaration for Slack.** `tooling/base/agent-factory/slack-bindings.yaml` is the only place a channel's binding is written; `scripts/ci/gen-slack-bindings.py --write` renders its consumers.
- **Site pages follow `docs/docs-style.md`:** no cluster name, session date or plan id in prose; second person, present tense. This platform's pages carry its values and link to Maku for the rest. The vocabulary pass over the whole site belongs to [the docs review](../specs/2026-11-14-docs-review-design.md); this plan changes only the pages its features make wrong.
- **Not renamed:** the `/factory retry` and `/factory split` comments on GitHub and the `factory/*` labels are the factory's own commands, not the coding agent's `/factory` command, and stay.
- **Switch-ons need the owner's go.** Tasks 6 and 7 turn on routes that act on tasks; neither merges without it.
- Commits are conventional, in English, with no trailers.

## Review Focus

1. **The end line is never edited because the broker stopped sending `room.merged`.** Dropping `notify` must not drop the subscription. Pinned in Task 1 (`test_broker_events_keep_merged_and_reverted`).
2. **A key written before its release wedges the broker's rollout.** Pinned in Task 2 (`test-room-broker-mcp-start.py`, both ends of the order).
3. **`sessionStart` removed from base but left in one cloud's copy.** Release N+1 refuses it and that cloud's broker fails to start. Pinned in Task 2 (every copy is read).
4. **A channel lists `stop` in `intentActions` while its cloud's broker has no `slackStop`.** A person presses a button that answers nothing useful. Pinned in Task 6 (`test_intent_actions_need_their_broker_route`).
5. **A site page still tells a person to re-label the issue after answering.** Pinned in Task 4 (`task docs` plus the grep in its step 4).

---

### PR 1: the generator and the gates (merges before any Maku release)

### Task 1: The bindings generator takes Maku's notification default

**Files:**
- Modify: `scripts/ci/gen-slack-bindings.py`
- Test: `scripts/ci/tests/test-gen-slack-bindings.py`, `scripts/ci/tests/slack-bindings-fixtures/`

**Interfaces:**
- Produces: in a channel, `notify` becomes optional and `intentActions` is a new optional key (a list drawn from `stop`, `retry`, `answer`, each once). Constants `DEFAULT_NOTIFY = ["room.task_triaged", "room.waiting_for_human", "room.pr_opened", "room.ended"]` and `ALWAYS_SUBSCRIBED = ["room.merged", "room.reverted"]`. The broker's `events` is the union of every channel's `notify` (or `DEFAULT_NOTIFY`), then `ALWAYS_SUBSCRIBED`, each once.

- [ ] **Step 1: Write the failing tests.**
  - `test_notify_is_optional`: a channel without `notify` renders `{repositories: […], maxCostUSD: …}` with no `notify` key in the App's `channels`.
  - `test_broker_events_keep_merged_and_reverted`: with no channel naming them, the broker's `events` still holds `room.merged` and `room.reverted`.
  - `test_explicit_notify_kept`: a channel that lists its own `notify` renders it unchanged.
  - `test_intent_actions_rendered`: `intentActions: [stop, retry]` renders after `approvals` and before `notify`.
  - `test_intent_actions_closed`: `intentActions: [steer]` and a duplicate entry are refused with the channel id in the message.
- [ ] **Step 2: Run** `python3 scripts/ci/tests/test-gen-slack-bindings.py`. Expected: FAIL on the five.
- [ ] **Step 3: Implement** in `validate`, `channels_block` and `notify_union`. Add `intentActions` to `OPTIONAL_KEYS` and move `notify` there.
- [ ] **Step 4: Run** the suite, then `python3 scripts/ci/gen-slack-bindings.py`. Expected: PASS, and exit 0 (the committed files are still the rendering).
- [ ] **Step 5: Commit** `feat(ci): the Slack bindings take the notification default and intentActions`.

### Task 2: The release order of the start key

**Files:**
- Create: `scripts/ci/tests/test-room-broker-mcp-start.py`

**Interfaces:**
- Produces: constants `START_RELEASE` (release N's tag) and `REMOVAL_RELEASE` (release N+1's tag), set to placeholders `v9.9.9` until each release is cut; the task that bumps the pin sets them in the same commit, as `INTAKE_RELEASE` is set in `test-room-broker-intake-classes.py`.

- [ ] **Step 1: Write the suite.** It builds each cloud's broker config with `kustomize` (base, aws-0, gcp-0) and reads the Maku pin from `infrastructure/base/room-broker/helmrelease.yaml`, then checks:
  - below `START_RELEASE`: no copy carries `human.mcp.start`;
  - at or above `START_RELEASE`: no copy carries `human.mcp.sessionStart`, and a copy that carries `human.mcp.start` has only the keys `default` and `except`, every `except` entry being `owner/name` and a repository the factory serves;
  - at or above `REMOVAL_RELEASE`: additionally, no copy of the Slack App config carries `proposals`.
- [ ] **Step 2: Run** `python3 scripts/ci/tests/test-room-broker-mcp-start.py`. Expected: PASS on today's tree (the pin is below both releases, and no copy has `start`).
- [ ] **Step 3: Prove it bites.** Add `start: {default: true}` to `infrastructure/base/room-broker/config.yaml` locally, run the suite, expect `FAIL: base: human.mcp.start must not precede`, then revert.
- [ ] **Step 4: Run** `task check`. Expected: exit 0, or the known local failures with `task links docs sources` passing.
- [ ] **Step 5: Commit** `test(ci): hold human.mcp.start to its Maku release`. Open PR 1.

---

### PR 2: adopt release N

### Task 3: The pin, the start key and the notification default

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/slack-app/deployment.yaml`, `tooling/base/agent-factory/crds/ocirepository.yaml`, `infrastructure/base/room-broker/ocirepository.yaml`, `infrastructure/base/room-broker/helmrelease.yaml`, `infrastructure/base/room-broker/crd-rooms.yaml` (when the release changes it)
- Modify: `infrastructure/base/room-broker/config.yaml`, `infrastructure/aws-0/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` and its `kustomization.yaml` comment
- Modify: `tooling/base/agent-factory/slack-bindings.yaml`, then the generator's outputs
- Modify: `scripts/ci/tests/test-room-broker-mcp-start.py` (`START_RELEASE`)

**Interfaces:**
- Consumes: Maku release N (the Maku plan's Task 12); Tasks 1 and 2.

- [ ] **Step 1: Bump every Maku pin to release N**, tag and digest together, and set `START_RELEASE`. Run `python3 scripts/ci/tests/test-agent-factory-pins.py`. Expected: PASS.
- [ ] **Step 2: Run** `python3 scripts/ci/tests/test-room-broker-mcp-start.py`. Expected: FAIL, naming `sessionStart` in base, aws-0 and gcp-0.
- [ ] **Step 3: Remove `sessionStart`** and its comments from the three copies. Write no `start` block: the default (start offered wherever the planner serves the repository) is what this platform wants. Rewrite the comment above `mcp:` to one line saying so.
- [ ] **Step 4: Drop `notify`** and its comment from `slack-bindings.yaml`, then run `python3 scripts/ci/gen-slack-bindings.py --write`. Check the diff: the App's channel loses `notify`; each cloud's broker `events` is the four defaults plus `room.merged` and `room.reverted`.
- [ ] **Step 5: Run** `scripts/ci/tests/test-maku-config-load.sh` with `MAKU_DIR` pointing at a clone holding the release tag. Expected: PASS for the three broker copies and the Slack App config. A SKIP here is not evidence: fetch the tag.
- [ ] **Step 6: Run** `task check`. Expected: exit 0, or the known local failures with `task links docs sources` passing.
- [ ] **Step 7: Commit** `feat(agent-factory): Maku <release N>, start by default and the four Slack notifications`.

### Task 4: The site pages the six tools make wrong

**Files:**
- Modify: `website/content/docs/use/coding-clients.md`, `website/content/docs/use/slack.md`, `website/content/docs/use/guide/cheat-sheet.md`, `website/content/docs/use/guide/terminal-and-coding-agent.md`, `website/content/docs/use/guide/when-the-factory-needs-you.md`, `website/content/docs/use/guide/following-and-steering.md`, `website/content/docs/use/guide/_index.md` (the diagram's `/factory` label), `website/content/docs/status.md`

- [ ] **Step 1: `coding-clients.md` and `terminal-and-coding-agent.md`.** Setup is `maku setup <client>`, one command. The command is `/maku` with three verbs: `handoff`, `task`, `inbox`. Replace the tool list with the six and one line each on what you do with it; link to Maku's `docs/cli.md` at the pinned tag for inputs and outputs. Delete the `/factory:handoff` caveat.
- [ ] **Step 2: `cheat-sheet.md`.** The coding agent table becomes the six tools and the three `/maku` verbs. Keep the GitHub comment and label rows (`/factory retry`, `/factory split`, `factory/*`).
- [ ] **Step 3: `when-the-factory-needs-you.md` and `following-and-steering.md`.** Answering a question: from your coding agent, `answer` writes it and restarts the task when you maintain the repository; otherwise it tells you who can. `wait` replaces `room_wait`. Remove the instruction to edit the issue and re-label it.
- [ ] **Step 4: `slack.md`.** The plan shows the workflow and the budget; the thread posts four lines (started, needs you, pull request opened, ended) and its last line carries the outcome, the spend, the duration and the gate's decision; `status` answers with the budget. Remove the draft keywords section. Then check nothing stale is left:

```bash
grep -rn -E "intake_plan|plan_check|issue_draft|issue_file|room_summary|room_brief|needs_list|rooms_list|need_answer|room_wait|/factory (handoff|status|inbox|resume)|/factory:handoff|Should:|Acceptance:" website/content/docs/use
```

Expected: no output.
- [ ] **Step 5: `status.md`.** One row: six tools and the Slack end line, with the Maku release, marked as awaiting its live proof.
- [ ] **Step 6: Run** `task links docs`. Expected: exit 0 (the reader-first check passes: no cluster name or plan id in the new prose).
- [ ] **Step 7: Commit** `docs(site): the six tools, /maku and the Slack end line`. Open PR 2.

### Task 5: Live proof of release N on aws-0

**Files:**
- Create: `docs/runbooks/agent-factory/27-six-tools-and-slack-acts.md`
- Modify: `docs/runbooks/agent-factory/README.md` (the index row), `website/content/docs/status.md` (the row from Task 4)

- [ ] **Step 1: Write the runbook** with these proofs, each with its command and the exact text to expect, and a results table left empty:

| # | Proof | Passes when |
|---|---|---|
| L1 | On a machine with no Maku config, `maku setup claude` | It asks for the rooms URL, signs in, registers a server named `maku` and ends on the doctor's lines |
| L2 | In a session, list the tools | Exactly `handoff`, `start`, `inbox`, `task`, `wait`, `answer` |
| L3 | `handoff` with one sentence, answer its question, `start` | The form shows the issue, the workflow and the budget, no merge line; "Start now" is pre-set to yes; the issue is filed as you and carries `factory/ready` |
| L4 | `task` before and after the pull request's gate decision | No `Merge` row before; one after; the budget row shows spent of limit |
| L5 | `@factory <request>` in the bound channel, then Confirm | One plan message with `Workflow` and `Budget`; then `Started #<n>. Room: …` |
| L6 | Let that task end, then merge it | One end line; the merge edits it in place; the thread holds no second end line |
| L7 | Count the thread's lines for L5 and L6 | Started, needs you (if it asked), pull request opened, ended: no verdict, budget or approval-closed line |
| L8 | `intake_plan` called by name without `--advanced` | Answers, with the deprecation line |

- [ ] **Step 2: Run L1 to L8 on aws-0** while it is the active cluster. Record each result, the room id and the date in the runbook's results table.
- [ ] **Step 3: Update** the status row to the proven state and the runbook index.
- [ ] **Step 4: Run** `task links docs`. Expected: exit 0.
- [ ] **Step 5: Commit** `docs(runbooks): the six tools and the Slack end line, proven on aws-0`.

---

### PR 3: adopt release N+1, stop and retry (owner's go required)

### Task 6: The pin, the removals and the stop and retry switch

**Files:**
- Modify: the pin files of Task 3; `scripts/ci/tests/test-room-broker-mcp-start.py` (`REMOVAL_RELEASE`)
- Modify: `tooling/base/agent-factory/slack-app/config.yaml` (drop `proposals`), `tooling/base/agent-factory/slack-bindings.yaml` (`intentActions: [stop, retry]`), then the generator's outputs
- Modify: `infrastructure/aws-0/room-broker/config.yaml` (`human.slackStop`, `human.slackRetry`, each naming the Slack App's sponsored principal as `slackDecide` does)
- Modify: `scripts/ci/tests/test-factory-slack-switchon.py`
- Modify: `website/content/docs/use/slack.md`, `website/content/docs/use/guide/cheat-sheet.md`

**Interfaces:**
- Consumes: Maku release N+1 (the Maku plan's Tasks 13 to 16).

- [ ] **Step 1: Write the failing test** in `test-factory-slack-switchon.py`: `test_intent_actions_need_their_broker_route`. For each cloud whose Slack App config lists `stop` or `retry` in a channel's `intentActions`, that cloud's broker config must carry `human.slackStop` or `human.slackRetry` naming the same principal as `human.slackDecide`. A cloud with the route and no channel listing the action passes.
- [ ] **Step 2: Bump every pin to release N+1** and set `REMOVAL_RELEASE`. Run `python3 scripts/ci/tests/test-room-broker-mcp-start.py`. Expected: FAIL, naming `proposals` in the Slack App config.
- [ ] **Step 3: Drop `proposals`** from the Slack App config. Add `intentActions: [stop, retry]` to the channel in `slack-bindings.yaml` and run the generator with `--write`. Run the switch-on suite. Expected: FAIL, aws-0's broker has no `slackStop`.
- [ ] **Step 4: Add `slackStop` and `slackRetry`** to aws-0's broker copy. gcp-0's copy gets them at its next turn; until then the bound channel is served by one cluster at a time, so state in the bindings comment that `intentActions` is honoured only where the broker serves the route.
- [ ] **Step 5: Site.** `slack.md` gains "Stop or retry a task": type `stop` or `retry`, or press the button, then confirm; only a maintainer of the repository can. The cheat sheet's Slack table gains the two rows.
- [ ] **Step 6: Run** `scripts/ci/tests/test-maku-config-load.sh` against the release tag, then `task check`. Expected: PASS and exit 0, or the known local failures with `task links docs sources` passing.
- [ ] **Step 7: Commit** `feat(agent-factory): Maku <release N+1>, stop and retry from Slack on aws-0`. Open PR 3 as a draft; it merges on the owner's go.
- [ ] **Step 8: Live proof on aws-0**, added to runbook 27 and recorded there:

| # | Proof | Passes when |
|---|---|---|
| L9 | Type `stop` in a running task's thread as a maintainer, confirm | The confirm names you; after Confirm the run ends, the pull request stays open, the end line reads `Ended: stopped` |
| L10 | A second person presses your confirm | `Only @<you> confirms this.`; the task is untouched |
| L11 | A linked non-maintainer types `stop` and confirms | `Only a maintainer of this repository can stop a task.` |
| L12 | Press Retry on an `Ended: escalated` line | The task runs again; a later end line replaces nothing: the same line is edited |
| L13 | A removed tool called by name | `unknown tool` |

---

### PR 4: answer from the thread (owner's go required)

### Task 7: The answer switch

**Files:**
- Modify: `tooling/base/agent-factory/slack-bindings.yaml` (`intentActions: [stop, retry, answer]`), the generator's outputs
- Modify: `infrastructure/aws-0/room-broker/config.yaml` (`human.slackAnswer`)
- Modify: `scripts/ci/tests/test-factory-slack-switchon.py` (the Task 6 test covers `answer` and `slackAnswer`)
- Modify: `website/content/docs/use/slack.md`, `website/content/docs/use/guide/when-the-factory-needs-you.md`

**Interfaces:**
- Consumes: Maku release N+1's answer route (the Maku plan's Task 17).

- [ ] **Step 1: Extend the test** to the pair `answer` and `human.slackAnswer`. Add `answer` to the bindings and run the generator. Run the suite. Expected: FAIL, aws-0's broker has no `slackAnswer`.
- [ ] **Step 2: Add `slackAnswer`** to aws-0's broker copy. Run the suite. Expected: PASS.
- [ ] **Step 3: Site.** `slack.md` and `when-the-factory-needs-you.md`: when a task asks a question, reply in the thread and confirm; a maintainer's answer restarts the task, the issue author's answer is recorded and a maintainer restarts it.
- [ ] **Step 4: Run** `task check`. Expected: exit 0, or the known local failures with `task links docs sources` passing.
- [ ] **Step 5: Commit** `feat(agent-factory): answer a task's question from Slack on aws-0`. Open PR 4 as a draft; it merges on the owner's go.
- [ ] **Step 6: Live proof on aws-0**, added to runbook 27 and recorded there:

| # | Proof | Passes when |
|---|---|---|
| L14 | A task asks a question; a maintainer replies and confirms | The issue's `## Decisions` section gains one record naming the maintainer's GitHub login; a new task starts, scoped again; the thread says `Answered. The task starts again with your answer.` |
| L15 | The issue's author, not a maintainer, replies and confirms | The record is written; no task starts; `Answered. A maintainer must restart the task.` |
| L16 | An unlinked person replies | Refused with one line; the issue is unchanged |
| L17 | The same question answered from a coding agent with `answer` | The record is written with your `gh`; "Restart the task" is pre-set to yes and restarts it |

- [ ] **Step 7: Update** the status page's row to the proven state; run `task links docs`; commit `docs(runbooks): stop, retry and answer from Slack, proven on aws-0`.

---

## Self-review notes

- **Spec coverage ("What changes where", this platform's column):** `sessionStart` removed from base and the per-cloud copies (Task 3); `notify` dropped, `intentActions: [stop, retry]`, then the answer switch (Tasks 3, 6, 7); the site pages reduced to this platform's values (Task 4, and steps in 6 and 7); the live session on aws-0 (Tasks 5, 6, 7). The vocabulary over the rest of the site is the docs review's.
- **Decided here, not in the spec:** the broker keeps its subscription to `room.merged` and `room.reverted` when `notify` is dropped; no `start` block is written because the default is what this platform wants; the route flags go in aws-0's copy only.
- **Depends on:** Maku releases N and N+1. PR 1 depends on neither.
