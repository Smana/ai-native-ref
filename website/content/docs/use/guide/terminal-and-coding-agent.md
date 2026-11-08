---
title: "8. From your terminal and your coding agent"
linkTitle: "8. Terminal and coding agent"
weight: 8
description: "Install maku, connect it to your coding agent, hand off a side task without leaving your session, and bring its branch back."
---

By the end of this chapter you will hand the factory a side task from your coding agent, follow it, and
check its branch out, without leaving your terminal.

## Install `maku` {#from-a-terminal-maku}

`maku` is the factory's command-line tool. Download it for your system from a
[Maku release](https://github.com/Smana/maku/releases) and put it on your `PATH`.

Connect it once:

1. Open the room list and click **CLI setup**. It shows a ready-made `maku configure …` line. Copy it
   and run it.
2. Run `maku login`. It prints a link and a code: open the link, enter the code, sign in.

Try `maku rooms --mine`: it lists your tasks. `maku` never approves anything; approvals stay in your
browser, so an agent driving your terminal cannot approve for you.

## Connect your coding agent {#hand-off-from-your-coding-agent}

One command connects `maku` to your coding agent. For Claude Code:

```bash
maku setup claude
maku doctor        # every check should say ok
```

For other agents use `opencode`, `codex`, `gemini`, `cursor` or `copilot`. It gives your agent the
factory's tools and a short skill for handing work over. For Claude Code and OpenCode it also installs
one short command, `/factory`, with four verbs:

| Type | Does |
|---|---|
| `/factory handoff <what>` | Plans or drafts the issue, shows it to you, files it once you confirm |
| `/factory status [room or #issue]` | The task's card; without an argument, your latest task |
| `/factory inbox` | Everything that needs you, in one list |
| `/factory resume [room]` | The brief of the first task that needs you, ending on its next step |

Other agents offer the same four as their own slash commands
([Reference › Commands]({{< relref "/docs/reference/commands.md#clients" >}})).
`maku doctor` checks the VPN, the certificate, your login, your GitHub link and the installed skill, in
the order they fail, and prints the fix of each.

## Hand off a side task {#handoff}

You are in the middle of something and spot a dead link. Tell your agent:

```text
/factory handoff fix the dead link in the install guide
```

[Chapter 3]({{< relref "your-first-task.md#paths" >}}) follows one hand-off from this line to the merge.

Your agent brings back a **plan**, and shows it to you before anything exists. A plan names:

- the repository it will file into, and the evidence it read to choose it — a path, an issue, a thread;
- one to three issues, as they will be filed, each with an acceptance check;
- the roles that will run, in that order;
- the ceiling, what the work may cost, and where that number came from.

Example (the reference host): one issue in `Smana/ai-native-ref`, roles `scoper`, `implementer` and
`reviewer`, and a ceiling of $2.00 from the `docs-links` class's own budget.

Most plans carry no question. When the evidence points two ways, the plan asks you exactly one, with
its recommendation, and settles the rest itself.

The planner reads public text only. Name a private repository and it stops before it calls a model,
then offers you the two ways forward: draft the issue yourself with your own model and file it with
`issue_draft` and `issue_file`, or wait for the internal route.

You answer the form, and only then does an issue exist. One confirmation files the plan's **first**
issue: when the plan holds two or three, the others are not filed, and your agent says so rather than
letting the filed one stand for the rest. A plan is what gets filed, not what gets done: the scoper
still reads the issue, checks the acceptance check and turns it into runs. A plan you edited, or one
that went stale while you sat on it, is refused when you confirm it, so read the one in front of you.

Where the planner is off, there is no plan to read — the [status page]({{< relref "/docs/status.md" >}})
says where it is on. Your agent then writes the issue itself, in the template's three sections
`## What is wrong`, `## What it should be` and `## Acceptance check`, has `issue_draft` check it, and
files it once you confirm. A draft you were shown is not a plan the broker composed, and your agent
says which of the two you are looking at.

Other agents' spellings: [Reference › Commands]({{< relref "/docs/reference/commands.md#clients" >}}).
What each setting of the planner means is in [Planner settings]({{< relref "/docs/reference/planner.md" >}}),
and what is switched on where you are is on the [status page]({{< relref "/docs/status.md" >}}).

## Follow it {#follow}

Ask your agent for the status, or run `maku status` yourself. Both show the same card:

```markdown
### <task> · #<issue> docs: fix the dead link in the install guide
**needs you** · waiting for a human · owner/repo · [open the room](https://rooms.example/r/<task>)

| | |
|---|---|
| Run | implementer (your review) · started 8 min ago |
| Spend | $0.31 of $1.50 (21 %) |
| PR | #<pr> · reviewer approved |

**You can** queue a note for the next run · stop it with the label `factory/stop`
```

Three more things to ask your agent:

- `/factory inbox`: everything that needs you, in one list. When nothing does, it says so.
- "wait for it": your agent follows the task and tells you when it needs you, opens its pull request
  or ends.
- "check it out": you get the task's branch in a new folder beside your repository, ready to read or
  run.

## Come back to a task {#come-back}

Back after a day away? Start wide, then close in:

1. Run `maku needs`. It lists what needs you, across your tasks. After your first call it shows only
   what is new since the last one; `--since <time>` asks from a moment you choose.
2. Run `maku status <room>`. It opens with the task's *brief*, a few fixed lines on where it stands,
   then the card.
3. In your coding agent, type `/factory resume`. It reads the same
   list, then the full brief of the first task that needs you, or of the task you name.

An approval still open from before your last call is not new, so `maku needs` leaves it out. To see
everything that waits on you, ask from a moment before any of it:

```bash
maku needs --since 2000-01-01T00:00:00Z
```

The brief holds:

- **Asked**: the issue the work started from.
- **Plan**: the plan or scope it runs under, and its ceiling.
- **Changed since**: what moved in the last 24 hours.
- **Blocked on**: the one thing it waits for.
- **Next**: the one step, with its link.

The full brief also lists the acceptance checks the work runs under and the links to the issue, the
pull request and the room.

When the task is stuck on something you can fix, the full brief adds a **Fix** line that names what to
change: a permission the factory App lacks, a check the factory cannot read, or a CI log host outside
the egress policy.

Every `maku` command, and what each coding agent supports, is in
[Reference › Commands]({{< relref "/docs/reference/commands.md" >}}).

**Next:** [chapter 9]({{< relref "multi-repository.md" >}}) plans one change across two repositories.
