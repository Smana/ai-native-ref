---
title: "10. When things go wrong"
linkTitle: "10. When things go wrong"
weight: 10
description: "Fix a set-up problem with maku doctor, a Slack user that is not linked, a stuck room, a failed run, stopping one task or all of them, and the questions people ask."
---

By the end of this chapter you will fix the common set-up problems yourself, unstick a task, and know
how the factory recovers on its own.

## Start with `maku doctor` {#doctor}

`maku doctor` checks your set-up in the order things fail, and prints the fix of each. Run it first,
whatever is wrong:

```text
ok   dns: rooms.example resolves
ok   tls: the certificate chain is trusted
ok   login: the token is valid
ok   github: your GitHub identity is linked
ok   skill: /home/you/.claude/skills/factory-handoff is v0.39.0
```

A failing check reads `FAIL <check>: …` with its fix, and a `warn` line flags something to look at
without failing the run.

| Symptom | Cause | Fix |
|---|---|---|
| `maku: command not found` | Not installed | Download it from a [Maku release](https://github.com/Smana/maku/releases), check it against `maku.sha256` |
| `not configured` | No config yet | Copy the `maku configure …` line from the room list's **Use maku from your terminal** fold |
| `FAIL dns`, or `no such host` on the rooms address | Off the private network | Connect to the VPN, then run `maku doctor` again |
| `FAIL tls`, or `x509: certificate signed by unknown authority` | The platform's certificate is not trusted | Add the certificate your platform team gave you to your system ([chapter 2]({{< relref "before-your-first-task.md#five-things" >}})) |
| `FAIL login`, `not_logged_in` | Your session ended | `maku login` |
| `FAIL github`; `maku rooms` lists nothing | Your GitHub account is not linked to your sign-in | Link it on the sign-in page |
| A `403` on the room list | You are not in `agents-member` | Ask an admin to add you |
| `FAIL skill` | A `factory-handoff` skill from another `maku` release | Run `maku setup <client>` again, or delete the stale copy |
| Your coding agent has no factory tools | The client was running before `maku setup` | Restart it; for OpenCode, `maku doctor` says whether its background service needs a restart |

## Slack says no {#slack}

| You see | Fix |
|---|---|
| `Not proposed: … is not linked to a GitHub account here` | Mention `@factory link`, open the page it sends you, press **Link** |
| `Not filed: … is not a maintainer of …` | Ask a maintainer of the repository to press **Confirm** |
| `Not proposed: the planner reads public repositories only` | The work is in a private repository: hand it off from your coding agent instead |
| `Proposal not posted: this plan covers N issues and Slack files one` | One mention per issue, or use your coding agent |
| No answer at all | The app is not in the channel, or the channel is not served: invite `@factory`, ask your platform team |

Every other line, with its fix: [Slack › When it says no]({{< relref "/docs/use/slack.md#when-it-says-no" >}}).

## A task looks stuck {#stuck}

1. **Open the room and read the status line and NEXT.** A task waiting for you says so, and names the
   move. Check **Needs you** ([chapter 6]({{< relref "when-the-factory-needs-you.md" >}})).
2. **Read NOW.** An agent still calling tools is working; long runs are normal up to their deadline.
3. **Queued, with no run?** Another task may hold the factory's run slots, or you hold the room's driver
   token ([hold]({{< relref "when-the-factory-needs-you.md#hold" >}})).
4. **Nothing moves, nothing needs you?** Label the issue `factory/stop`, then
   [continue it](#continue) or start over with `factory/ready`.

The factory answers a `factory/ready` it will not act on with a comment, and removes the label:

| Reason | Fix |
|---|---|
| `unauthorised_labeller` | The label was not a maintainer's: ask one to apply it |
| `edited_after_label` | The issue changed after the label: re-apply it |
| `task_active` | A task for this issue is still running: wait, or stop it first |
| `unsanitisable` | The text could not be made safe for an agent: simplify its markup |

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

Every run has a deadline and a spending cap, set by the task's tier, and the whole task has a cap too
([chapter 5]({{< relref "following-and-steering.md#budgets" >}})). A task out of budget waits for you:
`/factory retry` starts a fresh run if the task can still afford one. The factory also takes only so
many tasks a day; past that, it refuses a labelled issue with a comment. The numbers:
[Reference › Harness]({{< relref "/docs/reference/harness.md#caps" >}}).

## Stop everything {#stop-everything}

To stop one task, label its issue `factory/stop` ([chapter 5]({{< relref "following-and-steering.md#stop" >}})).

To stop every task at once, label the factory's pinned control issue `factory/stop`. The factory stops
taking new issues and ends every run. Your platform team has an emergency switch of its own.

## Continue a stopped task {#continue}

A stopped task stays stopped. Its branch keeps everything the agents pushed, and a new run can carry on
from there. Ask your platform team to start it, or start it yourself with the command in
[Reference › Commands]({{< relref "/docs/reference/commands.md#run-by-hand" >}}).

## Undo an automatic merge {#revert}

Label the merged pull request `factory/revert` within 7 days
([chapter 7]({{< relref "merging.md#revert" >}})).

## Questions people ask {#frequently-asked-questions}

**Can an agent push to `main`?** No. Agents may push only to their own `agent/` branches. The merge
bot merges, and only what you approved or one of the few low-risk kinds of change.

**Can my coding agent approve or start work on its own?** No. `maku` and the factory's tools never
approve, label or merge. Starting a task is your answer to a form, or your own label.

**Can it read our secrets?** It holds no long-lived credential: each run's GitHub token covers one
repository and ends with the run.

**Can it reach the internet?** Only GitHub, the model gateway and, when needed, package registries.

**Does a comment on the issue reach the agents?** No. The factory reads the issue's title and body when it
is labelled, and comments that start with `/factory`. Edit the issue and re-apply `factory/ready`, or
queue a note in the room.

**What if it goes in circles?** Its deadline or spending cap ends it, and you can stop it any time.

**Next:** keep the [cheat sheet]({{< relref "cheat-sheet.md" >}}) at hand. It has every label, comment,
tool and command on one page.
