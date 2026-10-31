---
title: How it works
weight: 20
description: "The parts of the Agent Factory: the roles and the merge gate, the factory, rooms, the runtime, Runlore and the providers."
---

{{< cards >}}
  {{< card link="/docs/platform/ai-platform/agents/how-it-works/agents-and-merge-gate/" title="Agents and the merge gate" subtitle="Every agent role and the two Apps around them; how the merge gate decides, how one approval merges, and how the breaker, drills and recovery keep auto-merge reversible." >}}
  {{< card link="/docs/platform/ai-platform/agents/how-it-works/factory/" title="Factory" subtitle="From a labelled issue to a merged PR: intake, triage, teams, revise, the merge gate and the kill switch." >}}
  {{< card link="/docs/platform/ai-platform/agents/how-it-works/rooms/" title="Rooms" subtitle="The shared, append-only log of a task: the broker, the bridge, the web view, steering, room tools, approvals, and maku." >}}
  {{< card link="/docs/platform/ai-platform/agents/how-it-works/runtime/" title="Runtime" subtitle="How one AgentRun becomes an isolated, attributed run: a gVisor sandbox on each cloud, per-run identity, octo-sts, branch and tag rulesets, and default-deny network policy." >}}
  {{< card link="/docs/platform/ai-platform/agents/how-it-works/runlore/" title="RunLore" subtitle="Agent to agent: RunLore hands an incident to the factory, follows the fix, and checks after the merge that the alert is gone." >}}
  {{< card link="/docs/platform/ai-platform/agents/how-it-works/providers/" title="Providers" subtitle="Moonshot (Kimi K3.1 Pro) and Mistral (Medium, Small) as selectable providers for public work: what they are, where data is processed, and how a class switches them on." >}}
{{< /cards >}}
