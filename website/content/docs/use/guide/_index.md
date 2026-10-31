---
title: User guide
weight: 10
description: "A short book in seven chapters: hand an issue to the Agent Factory, follow it, steer it, approve its work, and recover when something goes wrong."
lastVerified: 2026-10-31
aliases:
  - /docs/platform/ai-platform/agents/user-guide/
  - /docs/platform/agent-factory/user-guide/
  - /docs/platform/ai-platform/agents/use/user-guide/
---

This guide is a short book. Read it front to back once, about twenty minutes in all, and you will be
able to hand the Agent Factory a task and see it through to the merge.

Each chapter opens with what you will be able to do, and ends with a link to the next.

## Contents {#contents}

1. [Meet the factory]({{< relref "meet-the-factory.md" >}}): what it does for you, and its four safety
   rules.
2. [Before your first task]({{< relref "before-your-first-task.md" >}}): the five things you need, and
   who gives you each one.
3. [Your first task, start to finish]({{< relref "your-first-task.md" >}}): write a good issue, label it,
   review the pull request, approve.
4. [Following and steering a task]({{< relref "following-and-steering.md" >}}): the room list, the room
   page, a note for the next run, stopping.
5. [When the factory needs you]({{< relref "when-the-factory-needs-you.md" >}}): the hand-off, a question,
   a proposed split.
6. [From your terminal and your coding agent]({{< relref "terminal-and-coding-agent.md" >}}): `maku`, and
   handing off a side task without leaving your session.
7. [When things go wrong]({{< relref "when-things-go-wrong.md" >}}): a lost machine, a failed run,
   stopping everything, undoing a merge.

Then keep the [cheat sheet]({{< relref "cheat-sheet.md" >}}) at hand: every label and command on one
page.

Prefer Slack? [Filing from a Slack thread]({{< relref "/docs/use/slack.md" >}}) has its own page.

## Looking for an old section? {#old-links}

This guide used to be one long page. A link to one of its sections lands here, and your browser moves on
to the section's new home. If it does not, pick it from this list.

<!-- Each id below is an anchor the old single page had, which other pages and external links still
     use. The script sends a visitor who arrives with one of them to its new home; the list is the
     fallback without JavaScript. Keep both in step. -->
<ul class="anr-old-anchors">
<li id="before-you-start"><a href="before-your-first-task/">Before you start</a></li>
<li id="what-happens-to-a-task"><a href="your-first-task/">What happens to a task</a></li>
<li id="one-real-task-end-to-end"><a href="your-first-task/">One real task, end to end</a></li>
<li id="what-the-factory-wrote-on-the-issue"><a href="your-first-task/#hand-it-over">What the factory wrote on the issue</a></li>
<li id="the-reclaim"><a href="when-things-go-wrong/#lost-machine">The reclaim</a></li>
<li id="what-you-can-do"><a href="cheat-sheet/">What you can do</a></li>
<li id="hand-off-from-your-coding-agent"><a href="terminal-and-coding-agent/#hand-off-from-your-coding-agent">Hand off from your coding agent</a></li>
<li id="from-a-terminal-maku"><a href="terminal-and-coding-agent/#from-a-terminal-maku">From a terminal: maku</a></li>
<li id="who-sees-a-room"><a href="../../operate/access/#who-sees-a-room">Who sees a room</a></li>
<li id="the-room-list"><a href="following-and-steering/#the-room-list">The room list</a></li>
<li id="the-room-page"><a href="following-and-steering/#the-room-page">The room page</a></li>
<li id="hand-off"><a href="when-the-factory-needs-you/#hand-off">The hand-off</a></li>
<li id="scoper-question"><a href="when-the-factory-needs-you/#scoper-question">When the factory asks a question</a></li>
<li id="split"><a href="when-the-factory-needs-you/#split">When the factory proposes a split</a></li>
<li id="from-slack"><a href="../slack/">Using the factory from Slack</a></li>
<li id="what-the-factory-never-does"><a href="meet-the-factory/#never">What the factory never does (now: Four safety rules)</a></li>
<li id="budgets-and-costs"><a href="when-things-go-wrong/#caps">Budgets and costs</a></li>
<li id="caps"><a href="../../reference/harness/#caps">Caps</a></li>
<li id="tiers"><a href="../../reference/harness/#tiers">Tiers</a></li>
<li id="observability-what-you-can-inspect"><a href="../../operate/observability/#what-you-can-inspect">Observability: what you can inspect</a></li>
<li id="frequently-asked-questions"><a href="when-things-go-wrong/#frequently-asked-questions">Frequently asked questions</a></li>
</ul>

<script>
(function () {
  var id = decodeURIComponent(location.hash.slice(1));
  if (!id) return;
  var li = document.getElementById(id);
  if (!li || !li.parentNode.classList.contains('anr-old-anchors')) return;
  var a = li.querySelector('a');
  if (a) location.replace(a.href);
})();
</script>
