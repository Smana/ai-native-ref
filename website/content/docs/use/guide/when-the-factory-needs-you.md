---
title: "6. When the factory needs you"
linkTitle: "6. When it needs you"
weight: 6
description: "Every kind of need, what to do for each and where: an approval in the room, a merge or review on GitHub, the scoper's question, a split, a failed check, a recovery, a hold, a coordination plan."
---

By the end of this chapter you will know what to do each time the factory stops and waits for you, and
where you do it.

When the factory needs you, the room list marks the task **needs you**, and your Slack thread or your
coding agent says so. Each need has exactly one action and one link.

## Every kind of need {#kinds}

| Need | Where you answer | Room button |
|---|---|---|
| [Plan confirmation](#split): a proposed split | Issue: `/factory split` or `/factory retry` | No |
| [Approval](#approval): an agent asks first | The room page's card | **Yes** |
| [Question](#scoper-question): the scoper asks | Edit the issue, re-apply `factory/ready` | No |
| [Merge](#hand-off): the pull request is ready | GitHub: approve the current head | No |
| [Review](#review): you are a requested reviewer | GitHub: review the pull request | No |
| [Failed check](#failed-check): a check never settled | GitHub: re-run it, or `/factory retry` | No |
| [Recovery](#recovery): nothing runs on alone | Issue: `/factory retry`, or close the room | Close only |
| [Hold](#hold): you drive the room | The room: give the driver back | **Yes** |
| [Coordination](#coordination): a two-repository plan | The room's coordination panel | **Yes** |

### Why most needs have no button in the room {#why-no-button}

GitHub is the authority for what happens on GitHub. A merge, a review, a comment on an issue: each is
decided by your GitHub account and its rights on the repository, so the room links you there rather
than acting for you. The room decides only what lives in the room: an agent's request, the driver
token, a coordination plan.

The same rule keeps your coding agent and `maku` read-only: neither approves, labels or merges, so an
agent on your machine can never approve its own work.

{{< callout type="info" >}}
From Maku v0.40.0, every need in the room's **Needs you** panel is a card that ends in its action: a
button for the room's own decisions, a link marked ↗ for GitHub's, with a line that says why the room
has no button for it.
{{< /callout >}}

## One list, wherever you look {#one-list}

Every place that shows what needs you builds the same items and lists them in the same order: those
with a deadline first, then by kind, in the order of the table above.

| Where | Covers |
|---|---|
| `maku needs`, your coding agent's `/factory inbox` and `/factory resume` | Every room you can read. `maku needs` then shows only what is new since your last call |
| The room page's **Needs you** panel | That room |
| A Slack thread, when you reply `needs me` | That thread's task |

Back after a day away? [Chapter 8]({{< relref "terminal-and-coding-agent.md#come-back" >}}) shows how to
see everything that waits on you.

## An agent asks for approval {#approval}

Some rooms make an agent ask before it pushes, opens a pull request, calls a write tool, runs a command
flagged risky, or reaches a host outside its allow list. The request appears as a card in **Needs you**:

1. **What the agent wants**, in plain words, and **why it stopped**: the rule that raised it.
2. **If you approve, if you deny**: what each answer does.
3. **The deadline**. If nobody decides, the request expires and the agent is told no.
4. **Whether you may decide**: the room's owner, or a member with the approver flag.

Press **approve** or **deny**, with an optional reason the agent reads. The first decision wins. In a
room with four-eyes on, whoever prompted the turn cannot decide it: ask another approver.

A push approval (`forge.push`) can also arrive as a card in the task's Slack thread, with **Approve** and
**Deny** ([Slack]({{< relref "/docs/use/slack.md#approve-a-push-from-the-thread" >}})). Every other
approval is decided on the room page only.

## The hand-off: a pull request to merge {#hand-off}

When the agents have done what they can, the factory *hands off* the task. It comments on the issue
once, with a reason and one thing to do. Most of the time that is: **approve the pull request**, and the
merge bot merges it.

```text
Agent factory task `gmmrmund` waits for a maintainer's review: the policy
needs a maintainer's approval.

To merge: approve this pull request (a GitHub review by a maintainer). The
merger merges the approved head within a minute, or says why not.
```

What each reason means, and when an approval is not enough, is in
[chapter 7]({{< relref "merging.md#why-a-human" >}}).

## Approve the commit you read {#approve-the-commit-you-read}

The merge bot merges only the commit you approved. If an agent pushes while you read, approve again.
[Chapter 7]({{< relref "merging.md#approve-the-exact-head" >}}) shows how to approve an exact commit
from a terminal.

## You are asked to review {#review}

When you are one of the pull request's requested reviewers, the need is yours: review it on GitHub. An
approval of the current head merges it, as for a hand-off; **Request changes** starts a revision.

## The factory asks a question {#scoper-question}

For some classes a first agent, the *scoper*, reads your issue before anyone writes code. When the
issue leaves something open, it asks instead of guessing: it comments its question and the assumption it
would make, and labels the issue `factory/needs-author`.

- **To answer**, edit the issue, then remove `factory/ready` and put it back. A reply comment changes
  nothing: the factory reads the issue, not its comments.
- **To go ahead on its assumption**, comment `/factory retry`.
- **If you do nothing**, the task stops after 7 days.

## The factory proposes a split {#split}

A big issue may come back with a plan instead: two to four parts, each with its own acceptance check,
and the label `factory/split-proposed`.

- **To accept the plan**, comment `/factory split`. Every part's cost counts toward your own spending
  total.
- **To run it as one task anyway**, comment `/factory retry`.
- **To change the plan**, edit the issue, then remove `factory/ready` and put it back.

The parts then open one at a time, as sub-issues `Part k of N of #<parent>`, each with its own pull
request. The parent closes after the last one merges. `factory/stop` on the parent stops every part.

## A check never settled {#failed-check}

The factory waited on a check, and it never came back green: CI ran past its wait, a reviewer's verdict
went stale after a push, a tester's contract was invalid or disputed. The need names the reason.

1. Open the link: the pull request, or the issue.
2. If the check is flaky, re-run it on GitHub.
3. If the work is wrong, comment `/factory retry` on the issue for a fresh run.

## Nothing runs on alone: recovery {#recovery}

The task cannot continue without a decision: it spent its budget (`budget-task`), lost its machine more
times than it may resume (`resumes_exhausted`), or its merge was reverted.

- **To try again**, comment `/factory retry` on the issue. Fix the issue first if it was unclear.
- **To give up**, close the room from **Room** in the controls, or close the issue.

## A hold on the room {#hold}

The task waits because of the room itself, not because of the work:

- **You hold the driver token.** While a person drives, the factory starts no run. Give the driver back to
  the factory under **Driver** in the controls.
- **Another run is in the room.** Nothing to do: the task starts when that run ends.

## A coordination plan {#coordination}

A plan that spans two repositories needs a maintainer to confirm it, and each repository's maintainer to
authorize their part. The room's coordination panel holds **Confirm**, **Authorize** and **Decide**
([chapter 9]({{< relref "multi-repository.md" >}})).

**Next:** [chapter 7]({{< relref "merging.md" >}}) explains why a pull request comes to you, and how to
approve exactly the commit you read.
