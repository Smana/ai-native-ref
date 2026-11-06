---
title: "5. When the factory needs you"
linkTitle: "5. When the factory needs you"
weight: 5
description: "The hand-off comment and what to do about it, approving the commit you read, answering the factory's question, and a proposed split."
---

By the end of this chapter you will know what to do each time the factory stops and waits for you.

When the factory needs you, it says so on the issue, and the room list marks the task **needs you**.
You answer with a label, a review, or a comment starting with `/factory`. Other comments are not read.

## One list, wherever you look {#one-list}

Every place that shows what needs you builds its items the same way and lists them in the same order.
What differs is how much each one covers:

- `maku needs` in your terminal, and your coding agent's `inbox` and `resume`, cover every room you
  can read. `maku needs` then shows only what is new since your last call
  ([chapter 6]({{< relref "terminal-and-coding-agent.md#come-back" >}}) shows how to see it all).
- The room page's **Needs you** panel covers that room.
- A task's Slack thread answers `what needs me` for that task.

Each item carries one action and one link. An approval opens its card on the room page; a merge, a
review or a question opens the pull request or the issue on GitHub. The list decides nothing for you.

Items with a deadline come first, then the rest by kind. A [proposed split](#split) is an item too: a
*plan confirmation*. Its action is a comment on the issue: `/factory split` to accept the parts, or
`/factory retry` to run the task whole.

## The hand-off {#hand-off}

When the agents have done what they can, the factory *hands off* the task to you. It comments on the
issue once, with the reason and one thing to do. Most of the time that is: **approve the pull
request**, and the merge bot merges it.

![A room page waiting on a maintainer. The status line reads "Waiting — review and merge PR #42", the Next box gives the hand-off reason, and Needs you reads "a maintainer approves PR #42: approve the head you read on the PR page, or run gh api … -f commit_id=SHA -f event=APPROVE; the merger merges that head".](/images/screenshots/room-page-waiting-on-approval.png)

*A room after a hand-off. **Needs you** names your one move: approve the commit you read, and the merge bot merges it.*

The bot follows the factory's *merge gate*: its rules for what may merge, and when. Each hand-off
carries a reason code. The four you will meet most:

| Reason | What it means | What you do |
|---|---|---|
| `class_unarmed` | This kind of change never merges on its own | Review it; approve to merge, or request changes |
| `policy_pending` | The merge gate waits for a maintainer | Approve the latest commit |
| `approval_stale` | Your approval was of an older commit, or came while an agent was still pushing | Approve again |
| `human_commit_in_pr` | A person pushed a commit to the agent's branch | Read that commit, then have an admin merge it, or close the pull request |

When an approval merges the pull request, its item tells you to approve the head you read, and the
room's next step reads *review, then approve the current commit*. When an approval does not merge it,
the item names a maintainer with admin rights and the ruleset bypass, because the ruleset blocks a
plain merge. In the last row's case the room's step says why only an admin can: a person pushed a
commit the factory cannot vouch for.

Will your change merge on its own, with no approval? Only if its class is *live*: see
[when a pull request merges]({{< relref "/docs/how-it-works/merge-gate.md#when-it-merges" >}}) and the
status page's [class modes]({{< relref "/docs/status.md#class-modes" >}}).

Want the detail? See [when a pull request merges]({{< relref "/docs/how-it-works/merge-gate.md#when-it-merges" >}}),
[every hand-off reason]({{< relref "/docs/how-it-works/merge-gate.md#hand-off" >}}) and
[the gate's checks]({{< relref "/docs/reference/gate-reasons.md#decision-rows" >}}).

## Approve the commit you read {#approve-the-commit-you-read}

GitHub attaches an approval to the latest commit when it arrives. If an agent pushes while you read, a
command-line approval can approve a commit you never saw.

So wait until the room shows no run in progress, then approve from GitHub's web page. From a terminal,
name the commit:

```bash
gh api repos/<owner>/<repo>/pulls/<number>/reviews -f commit_id=<sha> -f event=APPROVE
```

## The factory asks a question {#scoper-question}

For some classes, a first agent, the *scoper*, reads your issue before anyone writes code. When the
issue leaves something open, it asks instead of guessing: it comments its question and the assumption it
would make, and labels the issue `factory/needs-author`.

- **To answer**, edit the issue, then remove `factory/ready` and put it back. A reply comment changes nothing.
- **To go ahead on its assumption**, comment `/factory retry`.
- **If you do nothing**, the task stops after 7 days.

## The factory proposes a split {#split}

A big issue may come back with a plan instead: two to four parts, each with its own acceptance check,
and the label `factory/split-proposed`.

- **To accept the plan**, comment `/factory split`. Every part's cost counts toward your own
  spending total.
- **To run it as one task anyway**, comment `/factory retry`.
- **To change the plan**, edit the issue, then remove `factory/ready` and put it back.

The parts then open one at a time, as sub-issues, each with its own pull request. The parent issue
closes after the last one merges.

**Next:** [chapter 6]({{< relref "terminal-and-coding-agent.md" >}}) brings all of this to your
terminal and your coding agent.
