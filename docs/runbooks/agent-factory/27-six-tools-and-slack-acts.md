# 27 — Six tools, `/maku`, the Slack end line, and stop, retry and answer from Slack: the live proofs

Proves the coding-agent and Slack UX rollout on `aws-0`
([design](../../superpowers/specs/2026-11-14-ux-review-design.md)):

- **L1–L8 (six tools and the Slack end line):** `maku setup <client>` as a single command, the six default MCP tools (`handoff`, `start`, `inbox`, `task`, `wait`, `answer`), `start` offering "Start now: yes" by default wherever the planner serves the repository, `task`'s merge row appearing once the gate decides, the four default Slack notifications, and the single thread end line edited in place on merge.
- **L9–L13 (stop, retry and removals):** `stop` and `retry` from a Slack thread behind a confirmation addressed to the presser, maintainer standing checks, and removal of replaced tool names.
- **L14–L17 (answer from Slack and from a coding agent):** replying to a scoper's question in Slack behind a confirmation (restarting the task for a maintainer, recording only for a non-maintainer issue author, refusing an unlinked user) and answering with `answer` from a coding agent.

See [README.md](README.md) for `CLOUD=aws` prerequisites.

## 1. Prerequisites

- [ ] **[OWNER]** Maku v0.53.0 or later pinned and reconciled on `aws-0`, with `sessionStart` removed from all three broker copies, `proposals` removed from `tooling/base/agent-factory/slack-app/config.yaml`, `intentActions: [stop, retry, answer]` rendered from `tooling/base/agent-factory/slack-bindings.yaml`, and `human.slackStop`, `human.slackRetry` and `human.slackAnswer` on `infrastructure/aws-0/room-broker/config.yaml`.
- [ ] `maku` v0.53.0 or later on `PATH`; `gh` authenticated as a maintainer of the target repository.
- [ ] Claude Code (or OpenCode) installed.
- [ ] In the bound Slack channel (`C0CC4M8SNVD`), one linked maintainer account, one linked non-maintainer account (issue author for L11 and L15), and one unlinked Slack account (for L10 and L16).

## 2. Live proofs

### 2.1 Six tools and the Slack end line (L1–L8)

| # | Proof | Command / action | Passes when |
|---|---|---|---|
| L1 | On a machine with no Maku config, `maku setup claude` | Move `~/.config/maku` aside, then run `maku setup claude` | It asks for the rooms URL (`https://rooms.priv.aws.ogenki.io`), signs in, registers an MCP server named `maku` and `/maku` (`handoff`, `task`, `inbox`), and ends on `maku doctor` with every line `ok` |
| L2 | In a session, list the tools | Start a fresh Claude Code session and list the tools registered by `maku` | Exactly six tools are listed: `handoff`, `start`, `inbox`, `task`, `wait`, `answer` |
| L3 | `handoff` with one sentence, answer its question, `start` | Run `/maku handoff <one-sentence request>`, answer the planner's question (`handoff {id, answer}`), then call `start {id}` | The confirmation form shows the issue, the `Workflow` (default pre-filled) and the `Budget`, with no merge policy line; `Start now` is pre-set to `yes`; on confirmation the issue is filed as your GitHub login via `gh` and carries `factory/ready` |
| L4 | `task` before and after the pull request's gate decision | Call `task {task: "<id>"}` while the implementer runs, and again after the pull request is evaluated by the gate | Before the gate decision, no `Merge` row is printed; after the gate decision, one `Merge` row appears (`Merged automatically by policy …` or `Waits for a human: …`); the `Budget` row shows `$<spent> of $<limit>` |
| L5 | `@factory <request>` in the bound channel, then Confirm | Post `@factory <request>` in `C0CC4M8SNVD`, then press **Confirm** as a maintainer | One plan message is posted with `Workflow` and `Budget` (no merge line); pressing **Confirm** edits the message to `Started #<n>. Room: https://rooms.priv.aws.ogenki.io/r/<id>` |
| L6 | Let that task end, then merge it | Wait for the task from L5 to reach its first end (`room.ended`), then approve and merge its pull request (`room.merged`) | One end line is posted on `room.ended`; `room.merged` edits that same message in place to `Merged #<pr> · $<spent> of $<budget> · <duration> · …`; the thread holds no second end line |
| L7 | Count the thread's lines for L5 and L6 | Read the entire Slack thread from L5 and L6 | Only the four default transitions appear: started (`Started #<n>…`), needs you (if it asked), pull request opened (`Pull request #<pr> opened.`), and the single edited end line — no verdict, budget-reached or approval-closed line |
| L8 | `intake_plan` called by name without `--advanced` | Send a raw `tools/call` for `intake_plan` to `maku mcp` (only applicable on a two-step release N; on v0.53.0 see L13) | On release N: answers with the deprecation line; on v0.53.0 (combined N+1): answers `unknown tool` (covered by L13) |

### 2.2 Stop, retry and tool removals (L9–L13)

| # | Proof | Command / action | Passes when |
|---|---|---|---|
| L9 | Type `stop` in a running task's thread as a maintainer, confirm | In a running task's Slack thread, reply `stop` as a linked maintainer, then press **Stop the task** | The confirmation message names `@<you>`; after pressing **Stop the task**, the active run ends, the pull request stays open, and the thread's end line reads `Ended: stopped` |
| L10 | A second person presses your confirm | Reply `stop` as `@alice` in a running task's thread, then have `@bob` press `@alice`'s **Stop the task** button | Slack answers `@bob` with `Only @<alice> confirms this.`; the task and confirmation stay untouched |
| L11 | A linked non-maintainer types `stop` and confirms | As a linked user without write access to the repository, reply `stop` in a running task's thread and press **Stop the task** | Refused with `Only a maintainer of this repository can stop a task.`; the task keeps running |
| L12 | Press Retry on an `Ended: escalated` line | On a task whose thread shows `Ended: escalated` with a **Retry** button, press **Retry** and confirm as a maintainer | The task runs again; when the new run finishes, the existing end line is edited in place and no second end line is posted |
| L13 | A removed tool called by name | Call `intake_plan`, `issue_draft`, `issue_file`, `room_summary`, `room_brief`, `needs_list`, `rooms_list`, `need_answer` or `room_wait` via `tools/call` on `maku mcp` | Refused with `unknown tool` |

### 2.3 Answer a question from Slack and from a coding agent (L14–L17)

| # | Proof | Command / action | Passes when |
|---|---|---|---|
| L14 | A task asks a question; a maintainer replies and confirms | Trigger a scoper question (`factory/needs-author`); in the Slack thread, reply with the answer as a linked maintainer and press **Confirm** | The issue's `## Decisions` section gains one record naming the maintainer's GitHub login; `factory/ready` is re-applied so a new task starts and is scoped again; the thread posts `Answered. The task starts again with your answer.` |
| L15 | The issue's author, not a maintainer, replies and confirms | On a task with an open scoper question filed by a linked non-maintainer, reply in the Slack thread as that author and press **Confirm** | The decision record is written to the issue's `## Decisions` section; no task starts; the thread posts `Answered. A maintainer must restart the task.` |
| L16 | An unlinked person replies | Reply to a scoper question in the Slack thread from an unlinked Slack user | Refused with one line; the issue body is unchanged |
| L17 | The same question answered from a coding agent with `answer` | On a task with an open scoper question, call `answer {task: "<id>", text: "<answer>"}` from Claude Code as a maintainer | The form shows the question, recommendation and issue diff, with `Restart the task` pre-set to `yes`; confirming writes the record with your local `gh` and re-applies `factory/ready` to restart the task |

## 3. Results

| # | Proof | Result | Room / PR | Date |
|---|---|---|---|---|
| L1 | `maku setup claude` from a clean config | | | |
| L2 | List tools (`handoff`, `start`, `inbox`, `task`, `wait`, `answer`) | | | |
| L3 | `handoff`, answer question, `start` ("Start now" pre-set to yes) | | | |
| L4 | `task` before and after the gate's decision | | | |
| L5 | `@factory <request>` in Slack, then Confirm | | | |
| L6 | Task ends, then merges (end line edited in place) | | | |
| L7 | Thread line count for L5 and L6 (four default transitions only) | | | |
| L8 | `intake_plan` without `--advanced` | | | |
| L9 | Maintainer types `stop` and confirms (`Ended: stopped`) | | | |
| L10 | Second person presses confirm (`Only @<you> confirms this.`) | | | |
| L11 | Linked non-maintainer types `stop` and confirms | | | |
| L12 | Press Retry on `Ended: escalated` (end line edited in place) | | | |
| L13 | Removed tool called by name (`unknown tool`) | | | |
| L14 | Maintainer replies to a question in Slack and confirms | | | |
| L15 | Non-maintainer issue author replies in Slack and confirms | | | |
| L16 | Unlinked person replies in Slack | | | |
| L17 | Question answered from a coding agent with `answer` | | | |
