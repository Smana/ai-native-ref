---
title: "7. When things go wrong"
linkTitle: "7. When things go wrong"
weight: 7
description: "A lost machine, a run out of budget, stopping one task or all of them, undoing an auto-merge, and four common questions."
---

By the end of this chapter you will know how the factory recovers on its own, and what to do when it
cannot.

## The machine went away {#lost-machine}

Agents run on low-cost cloud machines, which the provider can take back at short notice. When that
happens, the factory says so on the issue and starts the run again on the same branch and room.

The agent saves its unfinished work as a commit on the way out, so the new run picks up where it
stopped. This happens at most twice per task, and you do nothing.

## A run failed {#run-failed}

A run that fails on its own, rather than losing its machine, is not restarted. The task waits for you,
and the issue says why. Comment `/factory retry` to try again, after fixing the issue if it was
unclear.

## Out of time or money {#caps}

Every run has a deadline and a spending cap in dollars, set by the task's tier, and the whole task has
a cap too. The factory also takes only so many tasks a day; past that, it refuses a labelled issue with
a comment. The numbers: [Reference › Harness]({{< relref "/docs/reference/harness.md#caps" >}}).

## Stop everything {#stop-everything}

To stop one task, label its issue `factory/stop` ([chapter 4]({{< relref "following-and-steering.md#stop" >}})).

To stop every task at once, label the factory's pinned control issue `factory/stop`. The factory stops
taking new issues and ends every run. Your platform team has an emergency switch of its own.

## Continue a stopped task {#continue}

A stopped task stays stopped. Its branch keeps everything the agents pushed, and a new run can carry on
from there. Ask your platform team to start it, or start it yourself with the command in
[Reference › Commands]({{< relref "/docs/reference/commands.md#run-by-hand" >}}).

## Undo an automatic merge {#revert}

Label the merged pull request `factory/revert` within 7 days. The factory opens a pull request that
undoes it.

This works for changes the factory merged on its own. A merge you approved, you revert by hand, as
usual.

## Questions people ask {#frequently-asked-questions}

**Can an agent push to `main`?** No. Agents may push only to their own `agent/` branches. The merge
bot merges, and only what you approved or one of the few low-risk kinds of change.

**Can it read our secrets?** It holds no long-lived credential: each run's GitHub token covers one
repository and ends with the run.

**Can it reach the internet?** Only GitHub, the model gateway and, when needed, package registries.

**What if it goes in circles?** Its deadline or spending cap ends it, and you can stop it any time.

**Next:** keep the [cheat sheet]({{< relref "cheat-sheet.md" >}}) at hand. It has every label and
command on one page.
