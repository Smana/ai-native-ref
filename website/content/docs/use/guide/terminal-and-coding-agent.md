---
title: "8. From your terminal and your coding agent"
linkTitle: "8. Terminal and coding agent"
weight: 8
diataxis: chapter
description: "Set up maku with one command, hand off and start a side task from your coding agent, follow it, and answer its questions."
---

By the end of this chapter you will connect your coding agent in one command, hand off and start a side
task without leaving your session, and follow it to its pull request.

## Install and set up `maku` {#from-a-terminal-maku}

Download `maku` from a [Maku release](https://github.com/Smana/maku/releases) and put it on your `PATH`.
One command configures the rooms URL, signs in, registers the `maku` MCP server and `/maku` skill, and
runs the doctor checks:

```bash
maku setup claude      # or opencode, codex, gemini, cursor, copilot
```

It ends on `maku doctor`'s lines (`dns`, `tls`, `login`, `github`, `skill`). Pass `--advanced`
(`maku setup claude --advanced`) if you also want `room_tail`, `room_fork`, `room_checkout` and the
`coordination_*` tools listed.

## Six tools and `/maku` {#hand-off-from-your-coding-agent}

`maku setup` registers the server as `maku` with three `/maku` verbs:

| You type | What it does |
|---|---|
| `/maku handoff <what>` | Plans the work (`handoff`), then opens a form (`start`) to file and start it |
| `/maku task [task or #issue]` | Shows where a task stands, what it needs, what changed, its budget and the gate's decision |
| `/maku inbox` | Lists everything waiting for you across your tasks |

Your coding agent sees six tools ([inputs and outputs in Maku]({{< maku "docs/cli.md" >}})):

| Tool | What you do with it |
|---|---|
| `handoff` | Send your request in plain words, answer at most one question, and get a plan stored on the broker |
| `start` | Confirm the issue, workflow and budget in a form; files with your `gh` and applies `factory/ready` ("Start now" defaults to yes) |
| `inbox` | List what is waiting for you across your tasks |
| `task` | Read one task's state, needs, changes since your last call, budget, and merge gate decision |
| `wait` | Wait in a background task until a task needs you, opens a pull request or ends |
| `answer` | Answer a task's question (and restart it when you maintain the repository) or leave a note for the next run |

## Hand off a side task {#handoff}

Spot a bug while working and tell your agent:

```text
/maku handoff fix the dead link in the install guide
```

[Chapter 3]({{< relref "your-first-task.md#paths" >}}) walks through a full hand-off.

1. `handoff` stores the plan on the broker and returns the issue text, the workflow and the budget (with
   no merge policy line until a pull request exists). If something is ambiguous, it asks one question;
   your reply updates the stored plan by id.
2. `start` re-validates the stored plan and opens a form you answer yourself: **File** (defaults to no)
   and **Start now** (defaults to yes wherever the planner serves the repository and you can write to
   it). You can also change the workflow in the form.
3. On confirmation, `maku` files the issue with your own `gh` and applies `factory/ready`. Where the
   planner is off ([status page]({{< relref "/docs/status.md" >}})), `handoff` returns
   `Planning is not available here; file on GitHub.`

## Follow and come back {#follow}

<span id="come-back"></span>

While you keep working, your agent runs `wait` in the background and wakes when the task needs you,
opens a pull request or ends. Ask `/maku task` (or run `maku status <task>`) at any time:

```text
#412 docs: runbook 18 never says where the key lives        ai-native-ref
State     waiting for a review
Needs you nothing
Budget    $0.31 of $1.50 (21 %)
Merge     Waits for a human: policy docs is in shadow here
Since you last looked (12 min)
  11:02  pull request #418 opened
  11:04  review started
Room      https://rooms.example/r/k3f7q2ab
```

Before the gate evaluates a pull request, the `Merge` row is omitted.

When you return after time away, run `/maku inbox` (or `maku needs`) to see every task waiting on you,
then `/maku task <id>` to inspect its state and milestones, or `answer` to reply to a question or queue
a note. Every CLI command: [Reference › Commands]({{< relref "/docs/reference/commands.md" >}}).

**Next:** [chapter 9]({{< relref "multi-repository.md" >}}) plans one change across two repositories.
