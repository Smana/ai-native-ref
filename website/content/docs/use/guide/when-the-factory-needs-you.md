---
title: "6. When the factory needs you"
linkTitle: "6. When it needs you"
weight: 6
diataxis: chapter
description: "Every kind of need, what to do for each and where: an approval in the room or Slack, a merge or review on GitHub, answering the scoper's question from Slack or your coding agent, a split, a failed check, a recovery, a hold, a coordination plan."
---

By the end of this chapter you will know what to do each time a task stops and waits for you.

## Every kind of need {#kinds}

| Need | Where you answer | Room button |
|---|---|---|
| [Plan confirmation](#split): proposed split | Issue: `/factory split` or `/factory retry` | No |
| [Approval](#approval): agent asks first | Room page card (or Slack for `forge.push`) | **Yes** |
| [Question](#scoper-question): scoper asks | Reply in Slack and confirm, or `answer` in your coding agent | No |
| [Merge](#hand-off) or [review](#review) | GitHub: review or approve the current head | No |
| [Failed check](#failed-check) or [recovery](#recovery) | GitHub re-run, Slack `retry`, or issue `/factory retry` | Close only |
| [Hold](#hold) or [coordination](#coordination) | Room controls (**Driver**) or coordination panel | **Yes** |

### Why most needs have no button in the room {#why-no-button}

GitHub is the authority for merges and reviews, so the room links you there. In your coding agent,
`start` and `answer` open a form before your own `gh` writes anything; in Slack every action sits behind
a confirmation button checked against your linked GitHub rights.

## One list, wherever you look {#one-list}

Every surface lists what needs you in the same order: deadlines first, then by the table above.

| Where | Covers |
|---|---|
| `maku needs` and `/maku inbox` (`inbox`) | Every task you can read |
| The room page's **Needs you** panel | That task |
| A Slack thread (`needs me`) | That thread's task |

See [Chapter 8]({{< relref "terminal-and-coding-agent.md#come-back" >}}) for returning after time away.

## An agent asks for approval {#approval}

An agent that asks before pushing, opening a pull request, calling a write tool, running a flagged
command, or reaching an external host raises a card in **Needs you** with **approve** and **deny**
(subject to four-eyes when enabled).

A `forge.push` approval also posts a card in the Slack thread
([Slack]({{< relref "/docs/use/slack.md#approve-a-push-from-the-thread" >}})); every other approval class
stays on the room page.

## Merge and review on GitHub {#hand-off}

<span id="approve-the-commit-you-read"></span><span id="review"></span>

Review the pull request on GitHub. Approve the current commit to merge it
([chapter 7]({{< relref "merging.md#approve-the-exact-head" >}})); **Request changes** starts a revision run.

## The scoper asks a question {#scoper-question}

When an issue leaves something ambiguous, the scoper posts one question with its recommended assumption
and pauses the task (`factory/needs-author`):

- **From your coding agent:** call `answer`. It shows the question, recommendation and issue diff in a
  form, writes your decision to `## Decisions` with your `gh`, and restarts the task when you maintain
  the repository (otherwise it names who can).
- **From the Slack thread:** reply in the thread and press **Confirm**
  ([Slack]({{< relref "/docs/use/slack.md#answer-a-question" >}})). A maintainer's answer writes the
  record and restarts the task; the issue author's answer is recorded and a maintainer restarts it.
- **To proceed on the assumption instead:** type `retry` in Slack or comment `/factory retry` on the issue.

## Splits, failed checks, recovery, holds and coordination {#split}

<span id="failed-check"></span><span id="recovery"></span><span id="hold"></span><span id="coordination"></span>

- **Split (`factory/split-proposed`):** comment `/factory split` to accept, or `/factory retry` to run as one task.
- **Failed check or recovery (`budget-task`, `resumes_exhausted`, reverted merge):** re-run a flaky
  check on GitHub, or retry from Slack (`retry`) or the issue (`/factory retry`).
- **Hold:** return the room's driver token under **Driver** so runs can resume.
- **Coordination:** confirm and authorize two-repository plans in the room's coordination panel
  ([chapter 9]({{< relref "multi-repository.md" >}})).

**Next:** [chapter 7]({{< relref "merging.md" >}}) explains why a pull request comes to you.
