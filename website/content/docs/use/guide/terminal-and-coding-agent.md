---
title: "6. From your terminal and your coding agent"
linkTitle: "6. Terminal and coding agent"
weight: 6
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
factory's tools and a short skill for handing work over.

## Hand off a side task {#handoff}

You are in the middle of something and spot a dead link. Tell your agent (in OpenCode; Claude Code
spells it `/mcp__factory__handoff`):

```text
/factory:handoff fix the dead link in the install guide
```

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

- `/factory:inbox`: the tasks that need you first, then your other open tasks.
- "wait for it": your agent follows the task and tells you when it needs you, opens its pull request
  or ends.
- "check it out": you get the task's branch in a new folder beside your repository, ready to read or
  run.

Every `maku` command, and what each coding agent supports, is in
[Reference › Commands]({{< relref "/docs/reference/commands.md" >}}).

**Next:** [chapter 7]({{< relref "when-things-go-wrong.md" >}}) covers what to do when something goes
wrong.
