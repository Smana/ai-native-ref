# 19 — The factory from your coding agent: the live proofs

Proves feature 13 on gcp-0, in Claude Code and in OpenCode: a developer hands a side task to the
factory from the session, follows it to an approval, and brings the branch back. Design:
[the factory from your coding agent](../../superpowers/specs/2026-10-25-factory-from-your-agent-design.md)
(its Gate lists the five proofs below). Since Maku v0.53.0 the developer's agent sees six MCP tools,
`handoff`, `start`, `inbox`, `task`, `wait` and `answer` (with `cancel` listed after them), and
`start`'s form offers **Start now** on every repository the planner serves: `human.mcp.start` is
unset in every committed broker config, so nothing is switched on for these proofs. To keep one
repository out, list it in `human.mcp.start.except`. See [README.md](README.md) for `CLOUD`.

```mermaid
sequenceDiagram
  actor Dev as Developer
  participant A as Claude Code or OpenCode
  participant R as maku mcp
  participant B as maku-broker /mcp
  participant GH as GitHub
  Dev->>A: /maku handoff (or the handoff prompt)
  A->>B: handoff (plan, at most one question)
  A->>R: start {id}
  R->>Dev: form: file this issue? start now?
  R->>GH: gh issue create, then add label factory/ready (as you)
  R-->>A: the task view, within 60 s
  A->>R: wait, in the background
  R-->>A: needs you, with the approval link
  Dev->>B: approves on the room page
  R-->>A: PR opened
  A->>R: room_checkout (--advanced), or maku checkout
  R-->>A: new worktree path
```

## 1. Prerequisites

- [ ] **[OWNER]** Maku v0.53.0 or later pinned (`flux/sources/ocirepo-agent-factory.yaml`), with
  `human.mcp.enabled` and the planner (`human.intake.plan.enabled`) on in the cloud's broker config.
- [ ] `maku` v0.53.0 or later, configured and logged in (`maku doctor`: `dns`, `tls`, `login`, `github` ok).
- [ ] Claude Code and OpenCode installed, each able to run a background subagent.
- [ ] The cloud-native-ref pull request that removes the drifted v0.11.0 `factory-handoff` skill copy
  (design PR 7, plan Task 8) is merged. Until it is, the doctor's `skill` check FAILs in every
  cloud-native-ref checkout (section 2, step 2).
- [ ] A test repository the factory serves, where the developer can write, and a small `docs` issue to
  file for proof 1.
- [ ] gcp-0 is up and the factory's intake is on (see [runbook 14](14-gcp-0-session.md)).

## 2. Setup

### 2.1 Setup

| # | Do | Expected |
|---|---|---|
| 1 | `maku setup claude --advanced`, then `maku setup opencode --advanced` | Each prints the MCP registration of the `maku` server (the client's own `mcp add`, or the snippet to paste), the `maku-handoff` skill directory and the `/maku` command it wrote. An older `factory` entry is rewritten to `maku`, with a note |
| 2 | `maku doctor` | Every check `ok`, `skill` included |
| 3 | `opencode`'s config after setup | The server sits under `mcp.servers.maku` with `"codemode": false`, the shape `opencode mcp add` writes, and opencode lists it as connected. **Record the opencode version.** A docs-shaped `mcp.maku` that opencode ignores is a FAIL for `setup`'s snippet |
| 4 | In each client, list the MCP tools, prompts and commands | The six tools `handoff`, `start`, `inbox`, `task`, `wait`, `answer`, then `cancel`, then the `--advanced` tools (`room_checkout` among them); prompts `handoff`, `task`, `inbox`; the command `/maku` with `handoff`, `task` and `inbox`. **Record the slash spelling** each client shows for the prompts (`/mcp__maku__handoff` in Claude Code) |

### 2.3 The planner's identity: nothing to write

The planner calls the model gateway (`agent-gateway/model-gateway`) on its `clients` listener, at
`/clients/planner/v1`, with a projected ServiceAccount token of audience `maku-gateway.client.planner`.
The chart mounts that token at `/var/run/secrets/maku/model-gateway/planner` (`broker.modelGateway` in
`infrastructure/base/room-broker/helmrelease.yaml`), and the kubelet rotates it hourly. No key exists, so
there is nothing to seed in OpenBao and nothing to rotate. The `agents/planner` and `apps/planner`
entries an earlier release needed are unused: delete them when convenient.

The gateway admits only `system:serviceaccount:agent-system:room-broker` there and maps the call's
`tier-frontier` to Z.ai `glm-5.3` (`clients.planner` in
`infrastructure/base/agent-gateway/model-gateway/helmrelease.yaml`). A planner that answers 401 or 403
points at the token's audience or the gateway's `broker` values; one that times out points at the
network policies on either side.

## 3. Live proofs

Run each in Claude Code, then in OpenCode. Mark PASS or FAIL per client; a FAIL names what was seen.

| # | Do | Expected | Claude Code | OpenCode |
|---|---|---|---|---|
| 1a | `/maku handoff <the small docs issue>` | `handoff` returns the plan with at most one question; once it is answered or accepted, the agent calls `start` and a form shows the issue, the `workflow` and the `budget`, with **File this issue** defaulting to no and **Start now** to yes | | |
| 1b | Answer File this issue + Start now | The issue is filed and labelled `factory/ready`; GitHub's timeline shows the developer, not a bot, as the labeller; the task view appears within 60 s | | |
| 1c | In a second session, the model is asked to start the work without the form | No tool argument starts it: the form is the only path | | |
| 2a | "wait for it" (a background `wait`) | It returns when the run asks an approval, with the card and the approval link; the main session stayed usable meanwhile | | |
| 2b | In a client with URL forms | The URL form opens the room page at the approval, and only for a URL on the rooms host that came from the broker | | |
| 2c | Decide the approval on the room page, then "wait for it" again | The next wait returns on the pull request. Approvals stayed on the room page: no tool in the session approved | | |
| 3a | `/maku task #<issue>` | The task view shows its state, the budget in dollars and what needs you, with states in words | | |
| 3b | Force a resume (leave a note with `answer {task, text}`, or stop and restart the run), then call `task` again with the returned cursor as `since` | The milestones appear; turns and tool calls are collapsed; a second call shows only what is new | | |
| 3c | **L8.** The same task from `/maku inbox` and `task` | The client displays the Markdown `content` text, not the JSON `structuredContent`. If a client shows the JSON instead, record which and FAIL: the view is hidden | | |
| 4a | `room_checkout` (`--advanced`) for the room, or `maku checkout <room>` | A new worktree appears beside the repository at the checked commit; the current checkout and its branch are untouched; a second call returns the same path | | |
| 4b | Plant `.opencode/plugins/<file>` in the room's branch (a test branch the factory pushed, or a fork of it), then `room_checkout` | The form lists the file and defaults to no; answering no creates nothing | | |
| 5 | Queue a hostile note (`maku post <room> --queue` with a link, a heading, a table row, an ANSI escape and a bidi character in the text), then show the card in both clients | Each appears as a quoted code span: no link, heading or table from the note, no escape in the terminal | | |

### 3.1 Checks collected during the build

| # | Do | Expected | Claude Code | OpenCode |
|---|---|---|---|---|
| a | Sign in with a deliberately wrong client id or a revoked token (`maku login`, then a tool call) | **Record ZITADEL's exact `invalid_client` wording** and what `maku doctor` and the tools return; the fix named must be one that works | | |
| b | Have a reviewer on a test PR delete their GitHub account (or use a known ghost user), then look at the card | **Record the login GitHub's GraphQL returns** for the deleted reviewer (a ghost, or null). The card must not crash or show an empty name | | |

## 4. Claude Code without forms

If Claude Code declares no form mode at `initialize`, proofs 1 and 4 run the no-forms path there and
the result says so:

| Proof | The no-forms path | Expected |
|---|---|---|
| 1 | `start` writes nothing and returns one `gh issue create` command; the developer runs it and labels the issue `factory/ready` | Nothing starts without the developer; the task then appears as in 1b |
| 4 | `room_checkout` for a branch with a flagged file | It refuses and names the file; a clean branch still checks out |

Record "no forms" in the user guide's portability table, in the Forms cell.

## 5. Off again

1. Nothing to revert in the broker config: **Keep** `human.mcp.enabled`, and `human.mcp.start`
   stays unset.
2. Remove the planted `.opencode/plugins/` test branch and the checked-out worktrees
   (`git worktree remove <path>`).
3. In the user guide's portability table (`website/content/docs/platform/ai-platform/agents/use/user-guide.md`),
   the Claude Code and OpenCode Status cells become `proven, <date>`, and fix any cell a proof
   contradicted. In the design's Status line, replace "live proofs wait" with the session's date.
4. File the three recorded wordings (opencode's shape, ZITADEL's `invalid_client`, the deleted
   reviewer's login) where the next reader finds them.
