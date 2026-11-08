---
title: "5. Follow and steer a task"
linkTitle: "5. Follow and steer"
weight: 5
description: "Find your tasks, read a room page from top to bottom, get told when a task needs you, queue a note or steer the running agent, and stay inside the budget."
---

By the end of this chapter you will find any of your tasks, see where it stands, be told when it needs
you, give the agents a note or a correction, and know what a task may spend.

## Where to follow a task {#notifications}

You do not have to watch. Each place you started from tells you when a task needs you:

| Started from | You are told by | Ask for more |
|---|---|---|
| Slack | Lines in the thread: `Triaged.`, `Pull request #… opened.`, `The work waits for a human (…)`, `#… merged.` | Reply `status`, `needs me`, `what changed` |
| Your coding agent | `room_wait`, running in the background, returns when the room needs you, opens a pull request or ends | `/factory status`, `/factory inbox` |
| GitHub | The factory's comments on the issue, and GitHub's own notifications | The room link in the first comment |
| Anywhere | The room list's tab title counts the rooms that need you: `(2) Maku rooms` | `maku needs` in a terminal |

## The room list {#the-room-list}

Every task has a room, and the room list shows them all, the ones that need you first. Open it from the
*Watch* link in the factory's first comment, the Slack thread's room link, or the address your platform
team gave you.

![The room list: a filter bar with "mine", "needs me" and "all repositories", then one row per task with its repository, status, pull request and last activity. Two rows carry a "needs you" badge.](/images/screenshots/rooms-list-needs-you.png)

*The room list. Tick **needs me** to see only the tasks waiting for you.*

| Filter | Shows |
|---|---|
| **mine** | Tasks whose issue you filed or labelled, or whose pull request you authored or review |
| **needs me** | Rows with something waiting for you |
| Repository picker | One repository's rooms |

The list refreshes itself every 10 seconds; the control beside **New room** changes the interval or
pauses it. A room you expect but cannot see is almost always a missing GitHub link
([chapter 2]({{< relref "before-your-first-task.md#five-things" >}})).

## The room page {#the-room-page}

Click a row to open its room. The page reads from top to bottom:

```mermaid
flowchart LR
  subgraph head["1 · Header"]
    direction TB
    S["Status line"] --> T["Issue and title"] --> F["Facts: run, cost,<br/>links, who"]
  end
  subgraph now["2 · What is happening"]
    direction TB
    NX["NEXT: your move"] --> NW["NOW: the latest call"] --> NY["Needs you: cards"]
  end
  subgraph body["3 · The work"]
    direction TB
    RL["Run rail"] --> CV["Conversation"] --> MP["Merge policy"]
  end
  subgraph dock["4 · Dock"]
    direction TB
    CO["Composer:<br/>Room, Queue, Steer"] --> CT["Controls:<br/>Run, Driver, Room"]
  end
  head --> now --> body --> dock
```

| Part | What it tells you |
|---|---|
| **Status line** | Where the task stands, in fixed words: `⏳ Waiting for you — approve a pending action`, `✓ Done — merged` |
| **Facts** | The run (role, id, model, age), the cost (`Tokens 189 k of 1.5 M`, and dollars when the task is priced), the pull request and dashboards, the data class and who drives |
| **NEXT** | Shown while the task waits: why, then `Your move:` and the one step |
| **NOW** | What the agent is doing: its latest call, its status and how long ago |
| **Needs you** | One card per thing waiting for you ([chapter 6]({{< relref "when-the-factory-needs-you.md" >}})) |
| **Notes** | The agents' own account of their progress, labelled as their claim. Useful, but the pull request is what counts |
| **Merge policy** | A fold: the task's class, its mode, and what it takes to merge ([chapter 7]({{< relref "merging.md" >}})) |
| **Run rail** | One node per run: implementer, reviewer, then the merge, each with its state, cost and model. Click a node to see only that run's events |
| **Conversation** | Every message and tool call. Plumbing folds into one line per turn; **Raw events** shows everything |
| **Dock** | The composer, the theme button and the connection |

![A room page waiting on a maintainer. The status line reads "Waiting — review and merge PR #42", the Next box gives the hand-off reason, and Needs you reads "a maintainer approves PR #42: approve the head you read on the PR page, or run gh api … -f commit_id=SHA -f event=APPROVE; the merger merges that head".](/images/screenshots/room-page-waiting-on-approval.png)

*A room after the hand-off: the NEXT box says why it waits, and **Needs you** names your one move.*

{{< callout type="info" >}}
From Maku v0.40.0 the header groups its facts into four clusters (run, cost, links, who), the status
line is a tinted pill, and every need in **Needs you** ends in a card with its one action.
{{< /callout >}}

## Talk to the agents {#queue-a-note}

The composer at the foot of the page has a **Deliver to** choice. Pick by how urgent the correction is:

| Deliver to | Who reads it | When | Use it for |
|---|---|---|---|
| **Room** | People only; no agent receives it | Now | A note to the other people in the room |
| **Queue** | The next run, in its instructions | When the next run starts | "Also update the README", a detail the reviewer should check |
| **Steer** | The running agent | At once: it reads it on its next step | "Stop, you are editing the wrong file" |

Most of the time a queued note, or a **Request changes** review on the pull request, is enough. A queued
note never interrupts the run in progress, and you can remove it from **Queued for the next run** until
it is delivered.

From a terminal or your coding agent you can queue too, but never steer:

```bash
maku post <room> --queue "the acceptance check also covers docs/README.md"
```

## Steer the running agent {#steer}

Steering is the *driver's* alone. The driver holds the room's driver token; for a factory task that is
the factory itself, until someone takes it.

1. Open **Driver** in the controls. Ask the driver for the token with **request**, or, as the room's
   owner, **take** it with a reason.
2. Choose **Steer** in the composer and write your correction. **Interrupt** stops the agent's current
   step first.
3. When you are done, **give** the token back to the factory. While you hold it, the task waits for you:
   the room shows a *hold* ([chapter 6]({{< relref "when-the-factory-needs-you.md#hold" >}})).

Steering, interrupting and taking the token work only in the browser. A token issued to `maku` is
refused, because an agent on your machine can type into a terminal.

## Budgets and ceilings {#budgets}

Every run has a deadline and a spending cap, and every task has a cap of its own, so a confused agent
stops on its own. You see them in three places:

| Where | What it shows |
|---|---|
| The factory's first comment | The run's cap and deadline: `Budget: 1.5 M tokens, 45 minutes (tier standard)` |
| The room's facts, and `maku status` | Spent so far against the task's cap: `$0.16 of $5.10 (3 %)` |
| The Slack proposal, and your agent's plan | The **ceiling**: the most the task may cost, and where that number comes from |

The caps come from the task's *tier*. A ceiling from Slack or your coding agent can only lower the
task's cap, never raise it.

Example (the reference host), the `standard` tier: each run at most 1.5 M tokens, 45 minutes and $2.55,
the whole task at most $5.10. A link fix planned in Slack has a $2.00 ceiling.

When a run reaches its cap, it stops. When the task cannot afford another whole run, it waits for you
with the reason `budget-task`. The factory also starts only so many tasks a day; past that it answers a
new label with a comment. Every number: [Reference › Harness]({{< relref "/docs/reference/harness.md#caps" >}}).

## Stop a task {#stop}

Put the label `factory/stop` on the issue or its pull request. The task's runs end within a minute, and
the branch keeps whatever the agents pushed. From Slack, reply `stop` and the thread tells you where the
label goes; the thread itself never stops anything.

To pick a stopped task up later, see [chapter 10]({{< relref "when-things-go-wrong.md#continue" >}}).

**Next:** [chapter 6]({{< relref "when-the-factory-needs-you.md" >}}) covers each moment the factory stops
and asks for you.
