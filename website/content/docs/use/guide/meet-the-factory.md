---
title: "1. Meet the factory"
linkTitle: "1. Meet the factory"
weight: 1
description: "What the Agent Factory does for you, the deal between you and the agents, and its four safety rules."
---

By the end of this chapter you will know what the factory does for you, and the rules it keeps.

{{< hero-video clip="agent-factory" alt="The Agent Factory in 32 seconds: a labelled issue becomes an agent run, watched in a room, and ends as a pull request a person approves." />}}

You have more small fixes than time. A dead link, a version number that drifted, a script that needs
one more flag. The Agent Factory takes that kind of work off your plate.

Here is the deal. You put the label `factory/ready` on a GitHub issue. The factory hands it to an AI
agent, which works on its own branch, in a locked-down sandbox, and opens a pull request.

A second agent reviews that pull request before you see it. If the checks fail, the first agent fixes
them. Only then does the factory ask for you.

You review it the way you review any pull request. Ask for changes, and the agent revises it on the
same branch, with your review as its instructions. Approve it, and that approval is the merge.

Every task has a room: a live page of what each agent did and said. You can watch it, leave a note,
or stop the task at any time.

## Four safety rules {#never}

- **It never merges without your approval**, except a few low-risk kinds of change your platform team
  lets through, such as link fixes.
- **It never touches CI, branch protection or its own configuration.**
- **It never sees a long-lived secret.** Each run gets short-lived credentials for one repository.
- **It never reaches the internet** beyond the few hosts it needs.

Every run also has a deadline and a spending cap, so a confused agent stops on its own.

Two names you will meet. *Maku* is the software inside the factory, and `maku` its command-line tool.
Your *platform team* is the people who run the factory for your organisation.

**Next:** [chapter 2]({{< relref "before-your-first-task.md" >}}) checks you have what you need.
