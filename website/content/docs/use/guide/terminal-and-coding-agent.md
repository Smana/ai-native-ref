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

Your agent drafts the issue, with an acceptance check, and shows it to you in a form. You file it and,
if you like, start it. Only your answer to the form can start a task, never the agent.

Other agents' spellings: [Reference › Commands]({{< relref "/docs/reference/commands.md#clients" >}}).

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
