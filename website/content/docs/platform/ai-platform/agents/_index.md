---
title: Agents
weight: 20
description: "The Agent Factory: autonomous coding agents that run sandboxed under their own identity, collaborate with humans in rooms, and ship small changes end to end."
lastVerified: 2026-10-29
aliases:
  - /docs/platform/agent-factory/
---

{{< callout type="info" >}}
**v1 shipped on 2026-10-08 and v2.0 on 2026-10-18; v3 is built and was proven live on `gcp-0` by 2026-10-29.**
A labelled issue, a Slack thread, your coding agent or RunLore starts a task; a scoper bounds it, a tester writes
its contract, the implementer checks its work in the sandbox, a judge reads it against its checks, and a reviewer
gives its verdict. A human merges, except a link fix, which the merge gate merges on its own. Runs are metered,
capped, resumed after a reclaim and stopped by the kill switch; people follow and approve in rooms. What is proven,
what is left and what comes next are on the
[status page]({{< relref "/docs/platform/ai-platform/status.md#roadmap" >}}).
{{< /callout >}}

## What it is

The LLM platform serves models; the Agent Factory puts them to work. A maintainer labels an issue,
and agents (an implementer, then a reviewer) work it on their own branch in a gVisor sandbox. They
open a pull request, and the factory narrates each step on the issue. Humans steer through GitHub reviews, or by
joining the agents' room. Only policy-defined low-risk changes merge themselves; everything else
waits for a human.

The Agent Factory is a bundle of open-source tools: Maku, agentgateway, OpenHands, gVisor, octo-sts, RunLore, Kueue and others. [Maku](https://github.com/Smana/maku) is one component of it: the factory controller, the rooms, the harness and bridge, the Slack app and the `maku` CLI.

Which alternatives were considered, and why these choices? See
[Alternatives considered]({{< relref "/docs/platform/ai-platform/agents/alternatives.md" >}}).

## New here? The ideas in two minutes

| Term | In plain words |
|---|---|
| **Agent** | A language model in a loop: it reads a task, runs tools (shell, git, file edits, queries), looks at the result and decides the next step, until the task is done or its budget runs out |
| **Harness** | The program that runs that loop inside the sandbox. Here it is [OpenHands](https://github.com/OpenHands/software-agent-sdk), wrapped by a small `agent-run` entrypoint that clones the repository, starts the conversation and prints a step log |
| **Run** | One agent, one role, one task, one branch, with a deadline. Declared as an `AgentRun` object in Kubernetes |
| **Role** | What a run is allowed to do. An *implementer* pushes to its own `agent/<id>` branch and opens a PR; a *reviewer*, *tester* or *triager* only reads and reports to the room, which posts a reviewer's verdict on the PR |
| **Sandbox** | The pod a run lives in, isolated by [gVisor](https://gvisor.dev) (a user-space kernel), with no long-lived credential and a network policy that denies everything not named |
| **Run identity** | A token issued for that run only. Every call to a model or a tool carries it, and the run exchanges it for a short-lived GitHub token, so every action is attributed to the run that made it |
| **agent-router** | The gateway every agent call goes through, an [agentgateway](https://agentgateway.dev) Gateway (ADR-0053): it checks the run's token, meters its tokens and routes to the model |
| **Room** | A shared, append-only log of a task: what each agent did, what humans said, the handoffs between roles. Humans watch it live, post into it, steer the running agent and approve its actions |
| **Factory** | The controller that turns a labelled issue into runs, narrates progress on the issue, meters each run's tokens and owns the kill switch |
| **Merge gate** | The rule that decides which agent PRs may merge themselves: only low-risk classes, only with green CI |

The agent in the loop is not a trusted component. Every control sits **outside the sandbox**:
- network policy;
- per-run identity;
- scoped, short-lived GitHub tokens;
- branch and tag rulesets;
- token budgets;
- the merge gate.

## Architecture

### At a glance

One task, end to end. A maintainer labels an issue; the factory starts a sandboxed agent run and
opens a room; every call the agent makes goes through the gateway under the run's own identity;
the agent pushes an `agent/**` branch and opens a PR; a human review decides the merge.

![The Agent Factory at a glance: one task, end to end. A maintainer labels a GitHub issue. The factory controller, maku-factory, turns the issue into a task, starts an agent run and opens a room on maku-broker. The run is a gVisor sandbox holding the coding agent, OpenHands. The maintainer watches and steers through the room, which exchanges events and steering with the run. Every call the agent makes goes through the agent gateway, agentgateway, with per-run identity and budgets, to the models (Z.ai GLM, Kimi and Mistral for public work, Claude for internal work), the MCP tools, and octo-sts for a GitHub token limited to agent/** branches. The agent pushes a branch and opens a PR on GitHub, where the maintainer's review decides the merge. Traces, logs and metrics go to the Victoria stack and Grafana](/images/diagrams/agent-factory-overview.svg)

*Source: [`docs/architecture/agent-factory-overview.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/agent-factory-overview.drawio).*

### In detail

The diagram below shows the **target** architecture, the whole programme once built. Its legend
marks how far each box had got; where it and the status page disagree, the
[status page]({{< relref "/docs/platform/ai-platform/status.md" >}}) wins.

![The Agent Factory's target architecture. Triggers: a GitHub repository (the factory/ready and factory/stop labels; a PR review asking for changes, built but not deployed), RunLore as an agent-to-agent client through POST /v1/tasks and signed webhooks, with its fix verdict (deployed), the task agent:run CLI, a developer in a browser who can also approve an agent action, the maku CLI, and a Slack thread where maku-slack drafts an issue and a maintainer's check mark files it (deployed). The factory controller, maku-factory, turns a labelled issue into a task: intake and narration from a fixed template, then the Task controller, which starts one implementer per task, opens a room and runs the run meter, with a kill switch beside it; all deployed on gcp-0. The reviewer pair and revise flow are built but not deployed; the run roles (scoper, tester with its test contract, implementer with search, completion judge, reviewer and splitter) are deployed per class and proven live; Kueue admission is planned, and the merge gate (policy-bot and a merger App, auto-merge and rollback in shadow) is built, not yet proven live. Rooms: a web UI behind oauth2-proxy and ZITADEL SSO, maku-broker and its append-only CNPG log are deployed, with steering, room tools, verdicts and approval cards; fork is planned. The runtime turns an AgentRun claim, through Crossplane, into a default-deny CiliumNetworkPolicy, projected tokens and a gVisor Sandbox pod holding the maku-bridge sidecar, the maku-harness running OpenHands and an Envoy identity-proxy, on a GKE Sandbox pool on gcp-0 (deployed) or a Karpenter AL2023 pool on aws-0 (built). The proxy sends every call with a per-run JWT to agentgateway (Gateway agent-router in namespace agent-gateway, listeners public :8080, internal :8081 and sts :8082), which routes to Z.ai GLM-5.3 (deployed), Moonshot Kimi K3.1 Pro and Mistral Medium 3.5 and Small 4 for public data only (proven 2026-10-29), the Anthropic API direct for internal data with a gateway-held key (planned), Bedrock and Vertex AI optional per cloud (planned), the MCP federation agent-mcp (flux-operator-mcp, mcp-victoriametrics, mcp-victorialogs and the room-broker's room_* tools), and, behind the sts listener, octo-sts, which mints a token for the agents' GitHub App, confined by rulesets to agent/** branches and no tags. The agent-ratelimit server counts the per-run and fleet budgets B1 and B2 in shadow mode on Valkey; model tiers by data class are planned. The maku-bridge streams events to the broker over TLS with a room token, and the broker posts verdicts on the PR. Spans go through the agent-traces-collector to VictoriaTraces, step logs to VictoriaLogs, and access logs, gen_ai metrics and AgentRun state to VictoriaMetrics, all shown on the agent-run and agent-fleet Grafana dashboards. The same manifests deploy to gcp-0, the live cluster, and aws-0, destroyed and rebuilt on demand](/images/diagrams/agent-factory.svg)

*Source: [`docs/architecture/agent-factory.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/agent-factory.drawio).*

## The parts

| Part | What it covers |
|---|---|
| [Runtime]({{< relref "/docs/platform/ai-platform/agents/runtime.md" >}}) | The gVisor sandbox on each cloud, per-run identity, octo-sts, the branch and tag rulesets, network policy |
| [Harness tuning]({{< relref "/docs/platform/ai-platform/agents/harness.md" >}}) | Which knob moves cost, time and quality; measuring a change; failure modes and recipes |
| [Harness reference]({{< relref "/docs/platform/ai-platform/agents/harness-reference.md" >}}) | Every setting of a run, from the factory's tiers to the OpenHands loop, with its value and status |
| [Rooms]({{< relref "/docs/platform/ai-platform/agents/rooms.md" >}}) | The broker's append-only log, the bridge, the web view, steering, room tools, approvals |
| [Factory]({{< relref "/docs/platform/ai-platform/agents/factory.md" >}}) | Intake, triage, teams, revise, the merge gate and the kill switch |
| [Run roles]({{< relref "/docs/platform/ai-platform/agents/roles.md" >}}) | The scoper, tester, implementer, judge, search tool, reviewer and splitter, and what each may call |
| [Slack]({{< relref "/docs/platform/ai-platform/agents/slack.md" >}}) | Hand work to the factory from a Slack thread |
| [RunLore]({{< relref "/docs/platform/ai-platform/agents/runlore.md" >}}) | Agent to agent: an incident in, a verified fix out |
| [Providers]({{< relref "/docs/platform/ai-platform/agents/providers.md" >}}) | Kimi and Mistral for public work, switched on per class |
| [Gateways]({{< relref "/docs/platform/ai-platform/gateways.md#the-agent-gateway-agent-runs" >}}) | The agent gateway: per-run identity, models, MCP tools, token exchange |
| [Observability]({{< relref "/docs/platform/ai-platform/observability.md#agents" >}}) | Per-run traces, step logs, `gen_ai` metrics, `AgentRun` state, dashboards |
| [User guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md" >}}) | What a developer does with it |

Everything that runs on the cluster is open source. The external services are GitHub and the model
providers.

## More than one repository

The factory serves two repositories since v2.0. Nothing in it is tied to one repository: the agents'
App, the trust policies and the rulesets live in the repository they protect, and every
token audience names its repository. Adding another needs:

1. The agents' GitHub App installed on it, and the factory's App for narration.
2. The octo-sts trust policies for the roles it allows, in that repository.
3. The `agent/**` branch ruleset and the tag ruleset applied to it.
4. Two platform changes: its four audiences added to the gateway's token-exchange listener (at
   most eight per listener), and a factory intake that polls more than one repository.

Runs are per repository: a task never spans two.

## Design documents

- [Programme design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-factory-design.md): the contracts between the sub-projects, and the owner decisions.
- [Runtime and identity](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-runtime-identity-design.md) · [Rooms](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-collaboration-rooms-design.md) · [Factory](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-dark-factory-design.md) · [Model routing and budgets](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-llm-complexity-routing-design.md) · [Observability](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-27-agent-observability-design.md)
- [User guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md" >}}): what a developer does with it.
- [Status]({{< relref "/docs/platform/ai-platform/status.md#landed" >}}): what has landed, what is left, and the roadmap.
