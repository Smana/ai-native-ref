---
title: User guide
aliases:
  - /docs/platform/ai-platform/agents/use/user-guide/
weight: 10
description: "Hand work to the Agent Factory from Slack, your coding agent or a GitHub issue, follow it, answer what it needs, and merge its pull request."
lastVerified: 2026-11-08
---

Hand the Agent Factory a small, well-defined fix, and an AI agent turns it into a reviewed pull request
while you keep working. This guide shows you how, from three places: a Slack thread, your coding agent,
or a GitHub issue with a label.

**In a hurry?** Do the one-time [set-up]({{< relref "before-your-first-task.md" >}}), then follow
[Get started in five minutes]({{< relref "your-first-task.md" >}}) on the path you prefer.

```mermaid
flowchart TB
  subgraph ask["1 · You ask"]
    direction LR
    S["Slack:<br/>@factory + your words"] ~~~ C["Coding agent:<br/>/factory handoff"] ~~~ G["GitHub:<br/>issue + factory/ready"]
  end
  subgraph work["2 · The factory works"]
    direction LR
    I["implementer<br/>opens a PR"] --> R["reviewer<br/>gives a verdict"]
  end
  subgraph you["3 · You decide"]
    direction LR
    N["answer what<br/>it needs"] --> M["approve the PR:<br/>it merges"]
  end
  ask --> work --> you
```

## Contents {#contents}

| Chapter | You will be able to |
|---|---|
| 1. [Meet the factory]({{< relref "meet-the-factory.md" >}}) | Say what the factory does, and the four rules it keeps |
| 2. [Before your first task]({{< relref "before-your-first-task.md" >}}) | Get the five things you need, from the right person |
| 3. [Get started in five minutes]({{< relref "your-first-task.md" >}}) | Take one task from request to merged pull request, from Slack, your coding agent or GitHub |
| 4. [Write a good task]({{< relref "writing-a-good-task.md" >}}) | Write a request the agents can finish, and know what may merge on its own |
| 5. [Follow and steer a task]({{< relref "following-and-steering.md" >}}) | Read a room page, leave a note, steer a run, and stay inside the budget |
| 6. [When the factory needs you]({{< relref "when-the-factory-needs-you.md" >}}) | Answer each kind of need, and know where each is answered |
| 7. [Merging]({{< relref "merging.md" >}}) | Know why a pull request comes to you, and approve the right commit |
| 8. [From your terminal and coding agent]({{< relref "terminal-and-coding-agent.md" >}}) | Set up `maku`, hand off side tasks, follow them and check their branches out |
| 9. [Work across repositories]({{< relref "multi-repository.md" >}}) | Plan one change that spans two repositories |
| 10. [When things go wrong]({{< relref "when-things-go-wrong.md" >}}) | Fix a set-up problem, unstick a task, stop everything, and undo a merge |

Keep the [cheat sheet]({{< relref "cheat-sheet.md" >}}) at hand: every label, comment, Slack phrase,
tool and command on one page.

The reference pages behind this guide: [Slack]({{< relref "/docs/use/slack.md" >}}) for every message
the Slack app sends, [Commands]({{< relref "/docs/reference/commands.md" >}}) for every `maku` command
and tool, and [the merge gate]({{< relref "/docs/how-it-works/merge-gate.md" >}}) for every merge rule.
