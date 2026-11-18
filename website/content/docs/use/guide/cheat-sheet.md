---
title: "Cheat sheet"
weight: 20
diataxis: reference
description: "Every label, comment command, Slack action, coding-agent tool and maku command on one page."
---

Every way to talk to Maku, on one page. Labels and comments go on the GitHub issue unless the
row says otherwise; only a maintainer's count.

## Labels you put on {#labels}

| Label | What happens |
|---|---|
| `factory/ready` | Starts the issue as a task |
| `workflow:<name>` | Before `factory/ready`: picks `workflow:quick` or `workflow:careful` (no label runs `standard`) |
| `factory/stop` | Ends the task's runs; its branch stays. On the pinned control issue, it stops every task |
| `factory/revert` | On a pull request merged automatically, within 7 days: opens the revert |
| `factory/publish` | On a RunLore proposal's stub issue (`factory/proposed`): files the fix issue ([RunLore]({{< relref "/docs/how-it-works/runlore.md" >}})) |

## Comments you write {#comments}

| Comment | What happens |
|---|---|
| `/factory retry` | Tries a failed or escalated task again, or proceeds on the scoper's assumption |
| `/factory split` | Accepts a proposed split; the parts then open one at a time |

## On the pull request {#pull-request}

| You do | What happens |
|---|---|
| Request changes | A new run revises the same branch, with your review as its brief |
| Approve, from the web page | The commit you approved merges within a minute |
| `gh api repos/<owner>/<repo>/pulls/<n>/reviews -f commit_id=<sha> -f event=APPROVE` | Approves exactly the commit you read |

## Labels the factory puts on {#factory-labels}

| Label | It means |
|---|---|
| `factory/needs-author` | It asked a question: answer in the Slack thread or with `answer` in your coding agent |
| `factory/split-proposed` | It proposed a split: `/factory split` or `/factory retry` |
| `factory/class:<class>` | On every pull request: the merge class predicted for its diff |
| `factory/child-of:#<n>` | On a part's issue: the split it belongs to |
| `factory/stale` | On a pull request it closed after 14 days with no maintainer activity |

## In Slack {#slack}

| You write or press | You get |
|---|---|
| `@factory link` / `@factory unlink` | A one-time page that links your Slack user to your GitHub login / removes the link |
| `@factory <request>` | One plan message: issue, Workflow select, Budget |
| A reply in the plan's thread, or a workflow choice | The same plan message, updated in place |
| **Confirm**, or a ✅ reaction (a maintainer) | The issue filed and the task started |
| `status`, `needs me`, `what changed`, `the pull request` | State, budget and gate decision, read from the broker |
| Reply to a question, then **Confirm** | Writes the decision record to the issue; restarts the task when you are a maintainer |
| `stop` or **Stop**, then **Confirm** (a maintainer) | Ends the task's run; the pull request stays open (`Ended: stopped`) |
| `retry` or **Retry**, then **Confirm** (a maintainer) | Runs an escalated task again and edits the end line in place |

## In your coding agent {#coding-agent}

| You type | You get |
|---|---|
| `/maku handoff <what>` | A stored plan (`handoff`), then a confirmation form (`start`) that files and starts the task |
| `/maku task [task or #issue]` | Where the task stands, what it needs, what changed, its budget and the gate's decision |
| `/maku inbox` | Everything waiting for you across your tasks |

The six tools behind them ([Maku CLI reference]({{< maku "docs/cli.md" >}})):

| Tool | Does |
|---|---|
| `handoff` | Plan work from your words and answer at most one question; stores the plan on the broker |
| `start` | Show a confirmation form with the issue, workflow and budget; files with your `gh` and starts the task |
| `inbox` | List what is waiting for you across your tasks |
| `task` | Read one task's state, needs, changes since your last call, budget, and merge gate decision |
| `wait` | Wait in a background task until a task needs you, opens a pull request or ends |
| `answer` | Answer an open question (and restart the task when you maintain the repository) or leave a note for the next run |

`maku setup <client> --advanced` additionally exposes `room_tail`, `room_fork`, `room_checkout` and the
`coordination_*` tools. No tool approves or stops a task on the agent's say.

## In your terminal {#terminal}

```bash
maku setup claude                 # configures, signs in, registers maku and runs doctor
maku doctor                       # every line should read ok
maku rooms --mine                 # your tasks; also --needs-me, --all
maku needs                        # what needs you, new since your last call
maku status <task>                # brief, card, what needs you
maku changes <task>               # what changed since your last call
maku post <task> --queue "<note>" # a note for the next run
maku checkout <task>              # the branch in a worktree beside the repo
maku watch <task>                 # follow a room live
```

Every command and flag: [Reference › Commands]({{< relref "/docs/reference/commands.md" >}}).

**Back to:** [the guide's contents]({{< relref "_index.md" >}}).
