---
title: Agents
aliases:
  - /docs/platform/ai-platform/agents/
linkTitle: Agents
weight: 10
description: "Maku on this platform: autonomous coding agents that run sandboxed under their own identity, collaborate with humans in rooms, and ship small changes end to end."
lastVerified: 2026-11-15
---

{{< callout type="info" >}}
A labelled issue, a Slack thread, your coding agent or RunLore starts a task; a scoper bounds it, a tester writes
its contract, the implementer checks its work in the sandbox, a judge reads it against its checks, and a reviewer
gives its verdict. A maintainer's approval merges; link fixes and their reverts merge on their own
([when a pull request merges]({{< relref "/docs/how-it-works/merge-gate.md#when-it-merges" >}})). Runs are metered,
capped, resumed after a reclaim and stopped by the kill switch; people follow and approve in rooms. What is available,
what is experimental and what comes next are on the
[status page]({{< relref "/docs/status.md#roadmap" >}}).
{{< /callout >}}

## What it is

The LLM platform serves models; Maku puts them to work. A maintainer labels an issue,
and agents (an implementer, then a reviewer) work it on their own branch in a gVisor sandbox. They
open a pull request, and the factory narrates each step on the issue. Humans steer through GitHub reviews, or by
joining the agents' room. Only policy-defined low-risk changes merge themselves; everything else
merges on a maintainer's approval.

[Maku](https://github.com/Smana/maku) is the product: the factory controller, the rooms, the run-controller, the harness and bridge, the model gateway's chart, the Slack app and the `maku` CLI. This platform bundles it with agentgateway, OpenHands, gVisor, RunLore and others.

<span id="new-here-the-ideas-in-two-minutes"></span>New to rooms, runs, classes and the merge gate?
Maku's [glossary]({{< maku "docs/concepts.md#glossary" >}}) defines each term. Which alternatives were
considered, and why these choices: [Alternatives considered]({{< relref "/docs/how-it-works/alternatives.md" >}}).

The agent in the loop is not a trusted component. Every control sits **outside the sandbox**:
- network policy;
- per-run identity;
- scoped, short-lived GitHub tokens;
- branch and tag rulesets;
- token budgets;
- the merge gate.

## Architecture

<span id="at-a-glance"></span><span id="in-detail"></span>

One task, end to end. A maintainer labels an issue; the factory starts a sandboxed agent run and
opens a room; every model call the agent makes goes through the gateway under the run's own identity;
the agent pushes an `agent/**` branch and opens a PR; a human review decides the merge.

<!-- TODO: redraw agent-factory-overview.drawio: the picture still shows the MCP tools and octo-sts behind the model gateway. -->
![Maku at a glance: one task, end to end. A maintainer labels a GitHub issue. The factory controller, maku-factory, turns the issue into a task, starts an agent run and opens a room on maku-broker. The run is a gVisor sandbox holding the coding agent, OpenHands. The maintainer watches and steers through the room, which exchanges events and steering with the run. Every model call the agent makes goes through the model gateway, agentgateway, with per-run identity and budgets, to the models (Z.ai GLM, Kimi and Mistral for public work, Claude for internal work). With a GitHub token the factory minted for the run, limited to agent/** branches, the agent pushes a branch and opens a PR on GitHub, where the maintainer's review decides the merge. Traces, logs and metrics go to the Victoria stack and Grafana](/images/diagrams/agent-factory-overview.svg)

*Source: [`docs/architecture/agent-factory-overview.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/agent-factory-overview.drawio).*

## The parts

| Part | What it covers |
|---|---|
| [Runtime]({{< relref "/docs/how-it-works/runtime.md" >}}) | The run-controller, the gVisor sandbox on each cloud, per-run tokens, the branch and tag rulesets, network policy |
| [Harness tuning]({{< relref "/docs/operate/tune-a-run.md" >}}) | Which knob moves cost, time and quality; measuring a change; failure modes and recipes |
| [Harness reference]({{< relref "/docs/reference/harness.md" >}}) | Every setting of a run, from the factory's tiers to the OpenHands loop, with its value and status |
| [Rooms]({{< relref "/docs/how-it-works/rooms.md" >}}) | The broker's append-only log, the bridge, the web view, steering, room tools, approvals |
| [Factory]({{< relref "/docs/how-it-works/factory.md" >}}) | Intake, triage, teams, revise and the kill switch |
| [Roles]({{< relref "/docs/how-it-works/roles.md" >}}) | Every role and a task's life |
| [The merge gate]({{< relref "/docs/how-it-works/merge-gate.md" >}}) | When a pull request merges by itself, approve-to-merge, the hand-off |
| [Run auto-merge safely]({{< relref "/docs/operate/auto-merge-safety.md" >}}) | Taking a class live, the breaker, drills and recovery |
| [Slack]({{< relref "/docs/use/slack.md" >}}) | Hand work to the factory from a Slack thread |
| [RunLore]({{< relref "/docs/how-it-works/runlore.md" >}}) | Agent to agent: an incident in, a verified fix out |
| [Providers]({{< relref "/docs/how-it-works/providers.md" >}}) | Kimi and Mistral for public work, switched on per class |
| [Gateways]({{< relref "/docs/how-it-works/gateways.md#the-agent-gateway-agent-runs" >}}) | The model gateway: per-run identity, models, budgets |
| [Observability]({{< relref "/docs/operate/observability.md#agents" >}}) | Per-run traces, step logs, `gen_ai` metrics, `AgentRun` state, dashboards |
| [User guide]({{< relref "/docs/use/guide/_index.md" >}}) | What a developer does with it |

Everything that runs on the cluster is open source. The external services are GitHub and the model
providers.

## More than one repository

<span id="one-repository-at-first"></span>

The factory serves the repositories listed on the
[status page]({{< relref "/docs/status.md#class-modes" >}}). Nothing in it is tied to one repository:
the agents' App and the rulesets live in the repository they protect, and every run's GitHub token
names its repository. Adding another needs:

1. The agents' GitHub App installed on it, and the factory's App for narration.
2. The `agent/**` branch ruleset and the tag ruleset applied to it.
3. A `Repository` object in `tooling/base/agent-factory/resources/`, binding the classes it uses.

Runs are per repository: a task never spans two.

## Design documents

- [System design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-factory-design.md): the contracts between the sub-projects, and the owner decisions.
- [Runtime and identity](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-runtime-identity-design.md) · [Rooms](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-collaboration-rooms-design.md) · [Factory](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-dark-factory-design.md) · [Model routing and budgets](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-llm-complexity-routing-design.md) · [Observability](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-27-agent-observability-design.md)
- [User guide]({{< relref "/docs/use/guide/_index.md" >}}): what a developer does with it.
- [Status]({{< relref "/docs/status.md#landed" >}}): what has landed, what is left, and the roadmap.
