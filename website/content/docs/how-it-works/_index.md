---
title: How it works
weight: 30
description: "The parts of the platform: the agent roles and the merge gate, the factory, rooms, the runtime, RunLore, the providers, the gateways, routing and cost, serving, and the alternatives considered."
aliases:
  - /docs/platform/ai-platform/agents/how-it-works/
---

{{< cards >}}
  {{< card link="/docs/how-it-works/merge-gate/" title="Agents and the merge gate" subtitle="Every agent role and the two Apps around them; how the merge gate decides, how one approval merges, and how the breaker, drills and recovery keep auto-merge reversible." >}}
  {{< card link="/docs/how-it-works/factory/" title="Factory" subtitle="From a labelled issue to a merged PR: intake, triage, teams, revise, the merge gate and the kill switch." >}}
  {{< card link="/docs/how-it-works/rooms/" title="Rooms" subtitle="The shared, append-only log of a task: the broker, the bridge, the web view, steering, room tools, approvals, and maku." >}}
  {{< card link="/docs/how-it-works/runtime/" title="Runtime" subtitle="How one AgentRun becomes an isolated, attributed run: a gVisor sandbox on each cloud, per-run identity, octo-sts, branch and tag rulesets, and default-deny network policy." >}}
  {{< card link="/docs/how-it-works/runlore/" title="RunLore" subtitle="Agent to agent: RunLore hands an incident to the factory, follows the fix, and checks after the merge that the alert is gone." >}}
  {{< card link="/docs/how-it-works/providers/" title="Providers" subtitle="Moonshot (Kimi K3.1 Pro) and Mistral (Medium, Small) as selectable providers for public work: what they are, where data is processed, and how a class switches them on." >}}
  {{< card link="/docs/how-it-works/gateways/" title="Gateways" subtitle="ai-gateway for humans and coding clients, the agent gateway for agent runs: identity, routing and what they share." >}}
  {{< card link="/docs/how-it-works/routing-and-cost/" title="Model routing and cost" subtitle="Where each request is routed, how to tune quality, cost and latency, what a run costs, and when self-hosting pays." >}}
  {{< card link="/docs/how-it-works/serving/" title="Serving" subtitle="Turning the opt-in serving platform on, what it deploys, and its security posture." >}}
  {{< card link="/docs/how-it-works/alternatives/" title="Alternatives considered" subtitle="The alternatives considered for each layer of the Agent Factory, why the current choices won, and what would make us reconsider." >}}
{{< /cards >}}
