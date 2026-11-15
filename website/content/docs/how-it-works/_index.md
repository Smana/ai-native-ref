---
title: How it works
aliases:
  - /docs/platform/ai-platform/agents/how-it-works/
  - /docs/platform/ai-platform/agents/
  - /docs/get-started/agent-factory/
weight: 30
description: "The parts of the platform: the agent roles, the merge gate, the factory, rooms, the runtime, RunLore, the providers, the gateways, routing and cost, serving, and the alternatives considered."
lastVerified: 2026-11-15
diataxis: explanation
---

## What it is {#what-it-is}

The LLM platform serves models; Maku puts them to work. A maintainer labels an issue, and agents (an
implementer, then a reviewer) work it on their own branch in a gVisor sandbox. They open a pull
request, and the factory narrates each step on the issue. Humans steer through GitHub reviews, or by
joining the agents' room. Only policy-defined low-risk changes merge themselves; everything else merges
on a maintainer's approval.

[Maku](https://github.com/Smana/maku) is the product: the factory controller, the rooms, the
run-controller, the harness and bridge, the model gateway's chart, the Slack app and the `maku` CLI.
This platform bundles it with agentgateway, OpenHands, gVisor, RunLore and others.

<span id="new-here-the-ideas-in-two-minutes"></span>New to rooms, runs, classes and the merge gate?
Maku's [glossary]({{< maku "docs/concepts.md#glossary" >}}) defines each term. Which alternatives were
considered, and why these choices:
[Alternatives considered]({{< relref "/docs/how-it-works/alternatives.md" >}}).

The agent in the loop is not a trusted component. Every control sits **outside the sandbox**:
- network policy;
- per-run identity;
- scoped, short-lived GitHub tokens;
- branch and tag rulesets;
- token budgets;
- the merge gate.

Everything that runs on the cluster is open source. The external services are GitHub and the model
providers.

## Architecture {#architecture}

<span id="at-a-glance"></span><span id="in-detail"></span>

One task, end to end. A maintainer labels an issue; the factory starts a sandboxed agent run and opens
a room; every model call the agent makes goes through the gateway under the run's own identity; the
agent pushes an `agent/**` branch and opens a PR; a human review decides the merge.

![Maku at a glance: one task, end to end. A maintainer labels a GitHub issue. The factory controller, maku-factory, turns the issue into a task, starts an agent run and opens a room on maku-broker. The run is a gVisor sandbox holding the coding agent, OpenHands. The maintainer watches and steers through the room, which exchanges events and steering with the run. Every model call the agent makes goes through the model gateway, agentgateway, with per-run identity and budgets, to the models (Z.ai GLM, Kimi and Mistral for public work, Claude for internal work). With a GitHub token the factory minted for the run, limited to agent/** branches, the agent pushes a branch and opens a PR on GitHub, where the maintainer's review decides the merge. Traces, logs and metrics go to the Victoria stack and Grafana](/images/diagrams/agent-factory-overview.svg)

*Source: [`docs/architecture/agent-factory-overview.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/agent-factory-overview.drawio).*

## The parts {#the-parts}

| Part | What it covers |
|---|---|
| [Roles]({{< relref "/docs/how-it-works/roles.md" >}}) | Every role in a task, the two GitHub Apps beside them, and a task's life |
| [The merge gate]({{< relref "/docs/how-it-works/merge-gate.md" >}}) | Which gate status and Apps this platform uses, and its daily auto-merge caps |
| [Factory]({{< relref "/docs/how-it-works/factory.md" >}}) | Intake, triage, teams, revise, multi-repository service and the kill switch |
| [Rooms]({{< relref "/docs/how-it-works/rooms.md" >}}) | The broker's append-only log, the bridge, the web view, steering, room tools and approvals |
| [Runtime]({{< relref "/docs/how-it-works/runtime.md" >}}) | The run-controller, the gVisor sandbox on each cloud, per-run tokens, rulesets and network policy |
| [RunLore]({{< relref "/docs/how-it-works/runlore.md" >}}) | Agent to agent: an incident in, a verified fix out |
| [Providers]({{< relref "/docs/how-it-works/providers.md" >}}) | Why self-host vs hosted APIs, and Kimi and Mistral for public work switched on per class |
| [Gateways]({{< relref "/docs/how-it-works/gateways.md" >}}) | `ai-gateway` for humans and coding clients; the model gateway for agent runs |
| [Model routing and cost]({{< relref "/docs/how-it-works/routing-and-cost.md" >}}) | Every routing decision, the knobs that tune it, the meter's prices, caching and budgets |
| [Serving]({{< relref "/docs/how-it-works/serving/_index.md" >}}) | vLLM, one Crossplane `InferenceService` claim per model, on Karpenter L4 GPUs, scaled by KEDA |
| [Alternatives considered]({{< relref "/docs/how-it-works/alternatives.md" >}}) | Why the current choices won at each layer, and what would make us reconsider |
| [Coding clients]({{< relref "/docs/use/coding-clients.md" >}}) | OpenCode, Claude Code, Codex, Cursor and Continue pointed at `ai-gateway`, and the hand-off to the factory |
| [Slack]({{< relref "/docs/use/slack.md" >}}) | Hand work to the factory from a Slack thread |
| [User guide]({{< relref "/docs/use/guide/_index.md" >}}) | What a developer does with a running factory |
| [Operate]({{< relref "/docs/operate/_index.md" >}}) | Day-2 operations, auto-merge safety, harness tuning and observability |
| [Reference]({{< relref "/docs/reference/_index.md" >}}) | Host contract, factory and harness values, commands and gate reasons |

## Design documents {#design-documents}

- [System design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-factory-design.md): the contracts between the sub-projects, and the owner decisions.
- [Runtime and identity](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-runtime-identity-design.md) · [Rooms](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-collaboration-rooms-design.md) · [Factory](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-dark-factory-design.md) · [Model routing and budgets](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-llm-complexity-routing-design.md) · [Observability](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-27-agent-observability-design.md)
- [User guide]({{< relref "/docs/use/guide/_index.md" >}}): what a developer does with it.
- [Status]({{< relref "/docs/status.md#landed" >}}): what has landed, what is left, and the roadmap.
