---
title: "4. Write a good task"
linkTitle: "4. Write a good task"
weight: 4
description: "The issue template, good and bad issues and Slack requests side by side, and what a task's class means for whether it merges on its own."
---

By the end of this chapter you will write requests the agents finish on the first try, and know which
of them can merge without you.

The agents read the issue and nothing else. They cannot ask you what you meant halfway through, so the
issue is the whole brief. Whether you write it yourself, your coding agent drafts it, or the Slack
planner composes it, check it before it is filed.

## The template {#write-an-issue}

One defect per issue, with a title and three sections:

| Part | What goes in it |
|---|---|
| **Title** | An area and the defect: `docs: …`, `fix(scripts): …`, `ci(tests): …` |
| `## What is wrong` | What you saw, and where: the file, the line, the page, the command and its output |
| `## What it should be` | The end state, not the steps to reach it |
| `## Acceptance check` | How anyone can tell it is done: a command that exits 0, a line a file must contain |

The acceptance check matters most. The implementer runs it before it opens the pull request, and the
reviewer runs it again before it gives its verdict.

## Good and bad issues {#examples}

| Bad | Why it fails | Good |
|---|---|---|
| `fix the docs` | No defect, no place, no end state | `docs: the logging page lists the wrong chart version` |
| "The test is flaky sometimes" | Nothing an agent can reproduce | "`test-storage-dashboard.py` finds no dashboard when the checkout is under `.claude/`" |
| "Clean up the scripts folder and fix the dead links" | Two tasks in one; the first has no end | Two issues; the second names the links |
| Acceptance: "it works" | Nothing to run | Acceptance: "`python3 scripts/ci/tests/test-storage-dashboard.py` exits 0" |
| "Use a regex here, then refactor the loop, then…" | Steps, not an outcome: the agent follows them even when they are wrong | "SKIP is matched against the path relative to the repository root" |

A good issue, complete:

```markdown
docs: the logging page lists the wrong chart version

## What is wrong
docs/observability/logs.md says version 0.13.9. The repository pins 0.13.10
(clusters/base/victoria-logs.yaml).

## What it should be
The page says 0.13.10, the version the repository pins.

## Acceptance check
- docs/observability/logs.md names 0.13.10.
- `grep -rn 0.13.9 docs/` finds nothing for this chart.
```

Two habits pay off. End with "change nothing else" when the fix is narrow, and paste the error you saw
rather than describing it.

## Requests in Slack and your coding agent {#slack-requests}

In Slack and your coding agent you write in your own words, and a planner turns them into the issue. It
writes what you said, well formed. **It does not check your facts against the repository.** A false
premise in your request becomes a confident, wrong issue.

Example (the reference host), a request that went wrong:

```text
@factory the Slack runbook only shows gcp-0, it should cover aws-0 too
```

The planner proposed an issue saying the runbook named one cluster only. The runbook already covered
both, in its section "Which cloud serves Slack": the premise was wrong, and the planner wrote it into
the issue as a fact. Confirmed, it would have sent an agent to "fix" a page that was right.

Open the file before you ask. Here there was nothing to fix. When there is, state what you saw and
where, so the planner has facts to copy rather than a belief:

<!-- example -->
```text
@factory docs/install.md, section "Download", links to maku-linux, which 404s.
It should link to maku-linux-amd64, the asset the release publishes.
Acceptance: the link resolves, and the link check passes.
```

Before you press **Confirm**, or answer **file: yes** in your agent's form:

1. **Read the issue section as filed.** Is every fact in it true? Open the file it names.
2. **Read the acceptance check.** Could you run it yourself? Would it fail today?
3. **Check the repository and the class.** The proposal names both; a docs fix in the wrong
   repository is a wasted run.
4. **Reply to change it.** In Slack, a reply re-plans the same message. In your agent, say what to
   change before you confirm.

## Classes: what may merge on its own {#classes}

The factory sorts every task into a **class**, the kind of change it is. The class decides who
merges the pull request:

| Mode of the class | Who merges |
|---|---|
| **live** | The merge bot, with no human, when every check holds |
| **shadow** | You. The gate records what it would have done, to build the class's track record |
| **unarmed** | You. A normal pull request |

A maintainer can predict the class with a label `class:<name>` on the issue, before `factory/ready`.
Without one, the task is in class `review`, which never merges on its own. The planner picks the class
in Slack and your coding agent, from the classes its configuration offers.

Example (the reference host), the classes and what they cover:

| Class | Covers |
|---|---|
| `docs-links` | Markdown link targets only, nothing else in the diff |
| `revert` | The factory's own revert of a merge it made |
| `dead-links` | Dead external links, replaced by their archived copy |
| `deps-patch`, `deps-minor` | Renovate's patch and minor bumps, adopted from Renovate's own pull requests |
| `alert-rules` | Alerting rules |
| `docs`, `scripts`, `tests`, `dashboards` | Any change in those areas |
| `review` | Everything else |

Which of them are live where you are is on the status page's
[class modes]({{< relref "/docs/status.md#class-modes" >}}). Most work lands in a class you merge; that
is by design. [Chapter 7]({{< relref "merging.md" >}}) covers merging, and
[the merge gate]({{< relref "/docs/how-it-works/merge-gate.md#classes" >}}) every condition a live class
checks.

The class also sets the task's **tier**: how much time and money each run may spend
([chapter 5]({{< relref "following-and-steering.md#budgets" >}})).

## When the issue is not enough {#not-enough}

For some classes a *scoper* reads the issue before anyone writes code. When the issue leaves something
open it asks you a question instead of guessing, and a big issue may come back with a plan to split it
into parts. [Chapter 6]({{< relref "when-the-factory-needs-you.md#scoper-question" >}}) shows how to
answer both.

**Next:** [chapter 5]({{< relref "following-and-steering.md" >}}) shows how to follow a task as it runs,
and how to steer it.
