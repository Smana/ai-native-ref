---
title: "Cheat sheet"
weight: 8
description: "Every label and comment command of the Agent Factory on one page."
---

Every way to talk to the factory, on one page. Labels and comments go on the GitHub issue unless the
row says otherwise.

## Labels you put on {#labels}

| Label | What happens |
|---|---|
| `factory/ready` | The factory takes the issue as a task. After an edit, remove it and put it back |
| `factory/stop` | Ends the task's runs; its branch stays. On the pinned control issue, it stops every task |
| `factory/revert` | On a pull request the factory merged on its own, within 7 days: it opens the revert |

## Comments you write {#comments}

| Comment | What happens |
|---|---|
| `/factory retry` | Tries a failed task again, or goes ahead on the factory's assumption |
| `/factory split` | Accepts a proposed split; the parts then open one at a time |

Only a maintainer's comment counts.

## On the pull request {#pull-request}

| You do | What happens |
|---|---|
| Request changes | A new run revises the same branch, with your review as its brief |
| Approve, from the web page | The commit you approved merges within a minute |

## Labels the factory puts on {#factory-labels}

| Label | It means |
|---|---|
| `factory/needs-author` | It asked a question: edit the issue, then re-apply `factory/ready` |
| `factory/split-proposed` | It proposed a split: `/factory split` or `/factory retry` |

## In your coding agent {#coding-agent}

| You say | You get |
|---|---|
| `/factory:handoff <what>` | A drafted issue, filed after you confirm |
| `/factory:status` | Your latest task's card |
| `/factory:inbox` | What needs you first |

**Back to:** [the guide's contents]({{< relref "_index.md" >}}).
