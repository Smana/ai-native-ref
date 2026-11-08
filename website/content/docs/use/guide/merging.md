---
title: "7. Merging"
linkTitle: "7. Merging"
weight: 7
description: "Live and shadow classes, why a pull request comes to you and what each reason asks, approving the exact commit you read, and undoing a merge."
---

By the end of this chapter you will know why a pull request is waiting for you, what to do about it, and
how to make sure the commit that merges is the one you read.

**The short version:** approve the pull request on GitHub once no run is in progress, and the merge bot
merges the commit you approved within a minute. No agent merges its own work. The flow, as a
diagram: [when a pull request merges]({{< relref "/docs/how-it-works/merge-gate.md#when-it-merges" >}}).

## Live and shadow {#live-and-shadow}

A pull request merges with no human only when its [class]({{< relref "writing-a-good-task.md#classes" >}})
is **live** and every one of its checks holds: CI is green, the reviewer approved the current commit, the
diff stays inside the class's limits, and the class's daily cap is not reached.

A **shadow** class runs the same checks and records what it *would* have done, then hands the pull
request to you. Each shadow decision you merge unchanged is evidence; a class goes live only on enough of
it. So when you merge a shadow pull request without changes, you are also teaching the gate.

Most classes are neither: they always come to you. That is the default, not a failure.

## Why a pull request comes to you {#why-a-human}

The hand-off comment carries a reason. The ones you will meet:

| Reason | What it means | What you do |
|---|---|---|
| `class_unarmed` | This kind of change never merges on its own | Review it; approve to merge, or request changes |
| `policy_pending` | The repository's policy waits for a maintainer | Approve the current commit |
| `shadow_would_arm` | A shadow class would have merged it | Review it; approve if the gate was right |
| `approval_stale` | Your approval was of an older commit, or came while an agent was pushing | Approve again, on the current head |
| `approval_required` | The diff touches files that always need a maintainer | Review those files, then approve |
| `auto_merge_cap`, `class_paused` | A live class hit its daily cap, or the breaker paused it | Approve, or wait for tomorrow's cap |
| `human_commit_in_pr` | A person pushed a commit to the agent's branch | Read that commit; an admin merges, or close the pull request |

The last row is the one an approval cannot fix. The factory cannot vouch for a commit it did not make,
so the merge bot refuses it, and the ruleset blocks a plain merge. A maintainer with admin rights and the
ruleset bypass merges it by hand, after reading it.

Every reason, with the check behind it: [the gate's reasons]({{< relref "/docs/reference/gate-reasons.md" >}}).

## Approve the exact head {#approve-the-exact-head}

GitHub attaches an approval to the latest commit at the moment it arrives. If an agent pushes while you
read, a command-line approval can approve a commit you never saw, and the merge bot then merges it.

1. Wait until the room shows no run in progress: no **NOW** line, the rail's last node finished.
2. Approve from GitHub's web page, which shows you the commit you are approving.
3. From a terminal, name the commit you read:

```bash
gh api repos/<owner>/<repo>/pulls/<number>/reviews \
  -f commit_id=<sha> -f event=APPROVE
```

If the factory comments `approval_stale`, a new commit arrived after your approval: read it, approve
again.

## The merge policy in the room {#merge-policy}

Every factory room has a **Merge policy** fold. Open it to see the task's class and mode (`live`,
`shadow` or `unarmed`), the class's conditions, what it takes to merge, and, once there is one, the gate's
decision. It is read-only: a repository's policy changes through a pull request.

{{< callout type="info" >}}
From Maku v0.40.0, maintainers also get **Settings** pages in the rooms UI: each repository's merge
policies with their promotion evidence, a policy editor that checks and simulates a change, a
**Promote to live** flow that hands you the pull request to open, a decision timeline per pull request,
and *approval memory*: a saved grant that lets a later pull request touching the same reviewed files
merge without asking again. The model, every field and the rollout are in Maku's
[merge policies guide](https://github.com/Smana/maku/blob/main/docs/merge-policies.md).
{{< /callout >}}

## Undo a merge {#revert}

Label a pull request the factory merged on its own `factory/revert`, within 7 days. The factory opens a
pull request that undoes it, and the class's breaker counts the revert. A merge you approved, you revert
by hand, as usual.

The design behind all of this: [the merge gate]({{< relref "/docs/how-it-works/merge-gate.md" >}}).

**Next:** [chapter 8]({{< relref "terminal-and-coding-agent.md" >}}) brings the factory into your terminal
and your coding agent.
