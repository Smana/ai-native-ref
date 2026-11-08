---
title: "Cheat sheet"
weight: 20
description: "Every label, comment command, Slack phrase, coding-agent tool and maku command of the Agent Factory on one page."
---

Every way to talk to the factory, on one page. Labels and comments go on the GitHub issue unless the
row says otherwise; only a maintainer's count.

## Labels you put on {#labels}

| Label | What happens |
|---|---|
| `factory/ready` | The factory takes the issue as a task. After an edit, remove it and put it back |
| `class:<name>` | Before `factory/ready`: predicts the task's class, such as `class:docs-links` |
| `factory/stop` | Ends the task's runs; its branch stays. On the pinned control issue, it stops every task |
| `factory/revert` | On a pull request the factory merged on its own, within 7 days: it opens the revert |
| `factory/publish` | On a RunLore proposal's stub issue (`factory/proposed`): files the fix issue ([RunLore]({{< relref "/docs/how-it-works/runlore.md" >}})) |

## Comments you write {#comments}

| Comment | What happens |
|---|---|
| `/factory retry` | Tries a failed or stopped-for-you task again, or goes ahead on the scoper's assumption |
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
| `factory/needs-author` | It asked a question: edit the issue, then re-apply `factory/ready` |
| `factory/split-proposed` | It proposed a split: `/factory split` or `/factory retry` |
| `factory/class:<class>` | On the pull request: the class it predicted |
| `factory/child-of:#<n>` | On a part's issue: the split it belongs to |
| `factory/stale` | On a pull request it closed after 14 days with no maintainer activity |

## In Slack {#slack}

| You write | You get |
|---|---|
| `@factory link` / `@factory unlink` | A one-time page that links your Slack user to your GitHub login / the link removed |
| `@factory <what is wrong, what it should be>` | A proposal: repository, issue, roles, ceiling |
| A reply in the proposal's thread | The same proposal, re-planned with your change |
| **Confirm**, or a ✅ reaction (a maintainer) | The issue filed and started |
| `status`, `needs me`, `what changed`, `the pull request`, `stop` | The answer, read from the room |

## In your coding agent {#coding-agent}

| You type | You get |
|---|---|
| `/factory handoff <what>` | A plan or a draft, filed and started after you confirm in a form |
| `/factory status [#issue]` | The task's card; without an argument, your latest |
| `/factory inbox` | Everything that needs you |
| `/factory resume [room]` | The brief of the first task that needs you, and its next step |

The tools behind them:

| Tool | Does |
|---|---|
| `intake_plan`, `plan_check` | Plan the work from your words; re-check a plan you were shown |
| `issue_draft`, `issue_file` | Check an issue against the template; file it, after your confirmation |
| `rooms_list`, `room_summary`, `room_brief`, `needs_list` | Read rooms, one room, its brief, what needs you |
| `room_changes`, `room_tail` | What changed; the latest events |
| `room_wait` | Returns when a room needs you, opens a pull request or ends |
| `room_checkout` | The room's branch in a new worktree beside your repository |
| `room_queue`, `room_fork` | A note for the next run; a room of your own from a point in another |
| `coordination_plan` | A plan across two repositories; files nothing |

No tool approves, steers, stops or labels.

## In your terminal {#terminal}

```bash
maku setup claude                 # or opencode, codex, gemini, cursor…
maku doctor                       # every line should read ok
maku rooms --mine                 # your tasks; also --needs-me, --all
maku needs                        # what needs you, new since your last call
maku status <room>                # brief, card, what needs you
maku changes <room>               # what changed since your last call
maku post <room> --queue "<note>" # a note for the next run
maku checkout <room>              # the branch in a worktree beside the repo
maku watch <room>                 # follow a room live
```

Every command and flag: [Reference › Commands]({{< relref "/docs/reference/commands.md" >}}).

**Back to:** [the guide's contents]({{< relref "_index.md" >}}).
