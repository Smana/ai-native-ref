---
title: Status and roadmap
weight: 60
description: "What the AI platform does today, what is in progress, and what comes next."
lastVerified: 2026-10-17
aliases:
  - /docs/platform/agent-factory/status/
  - /docs/platform/ai-platform/roadmap/
---

The other pages of this section describe the design. This page says what of it you can use today,
what is being finished, and what comes next. The evidence behind each line is on the page it links to.

```mermaid
flowchart LR
  subgraph landed["Landed"]
    v1["Agent factory v1"]
    rooms["Attended rooms"]
    priv["Private repositories"]
    internal["Internal work on Claude"]
    gw["agentgateway, model tiers"]
    repo["Own repository and site"]
    cloud["v2.1: the factory on gcp-0"]
  end
  subgraph progress["In progress"]
    warm["Warm sandboxes"]
    caps["Per-person caps"]
    merge["Live auto-merge"]
    second["A second repository"]
  end
  subgraph next["Next"]
    loop["Continuation loop, if needed"]
    serving["Serving paths"]
  end
  landed --> progress --> next
```

## Landed {#landed}

| Feature | What it does for you |
|---|---|
| Agent factory v1, shipped 2026-10-08 | A labelled issue becomes a reviewed pull request that a human merges, built by agents in a gVisor sandbox under their own identity ([agents]({{< relref "/docs/platform/ai-platform/agents/_index.md" >}})) |
| Attended rooms with approval deadlines | Follow, steer and approve a run live; an approval answered after its deadline is refused ([rooms]({{< relref "/docs/platform/ai-platform/agents/rooms.md" >}})) |
| Private repositories | Room access follows each person's GitHub permission, proven on a private repository ([runbook 11](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/11-v1-validation.md)) |
| Agents work on internal data through Claude, with prompt caching | Investigations and cluster or log reads run on Claude through the Anthropic API, clone read-only, and are priced at the gateway's price ([evidence](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/plans/2026-10-15-agent-router-agentgateway-plan.md#live-evidence-internal-run-2026-10-16)) |
| agentgateway as the agents' gateway, with model tiers | Every agent call is checked, metered and routed to the model its tier names ([ADR-0053]({{< relref "/docs/decisions/0053-agent-router-on-agentgateway.md" >}})) |
| The reviewer keeps the implementer's model | Public work never goes to Anthropic for review ([ADR-0058]({{< relref "/docs/decisions/0058-reviewer-on-another-model.md" >}})) |
| A measured comparison on harder tasks | The factory against a hosted agent on 15 harder issues: the gap follows the model, not the factory ([results](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-12-v2-hard-task-cohort-design.md#results)) |
| The AI platform in its own repository and site | Versioned and signed on its own, documented here; a rebuild from release pins closes the move ([ADR-0057]({{< relref "/docs/decisions/0057-ai-platform-own-repository.md" >}})) |
| v2.1: the factory on `gcp-0` | The whole factory runs on GKE alone: a labelled issue became a merged pull request on release pins, its room followed live, and the gVisor pool scaled to its second node ([runbook 14](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/14-gcp-0-session.md)) |
| Self-hosted model serving | vLLM on L4 GPUs behind an OpenAI-compatible gateway, off by default on both clouds ([known gaps]({{< relref "/docs/platform/ai-platform/serving/_index.md#known-gaps" >}})) |

v1 is a pilot, not yet dependable: its hardening is tracked on the **v1 hardening** milestones of
[agent-platform](https://github.com/Smana/agent-platform/milestone/1) and
[cloud-native-ref](https://github.com/Smana/cloud-native-ref/milestone/1).

## In progress {#in-progress}

{{< callout type="info" >}}
**Live on `gcp-0` since 2026-10-17.** `aws-0` is torn down; `gcp-0` runs alone, hosts the identity
provider and runs the factory. The work below continues there in the [order below](#next-on-gcp-0).
{{< /callout >}}

| Feature | What is left |
|---|---|
| Warm sandboxes: runs start in seconds, not minutes | Compressed same-day test 2026-10-17: runs start in 16–17 s (target 30 s), and a run preempts the warm capacity, never the reverse. The warm node costs about $126 a month, over its $50 cap, so the owner picks a smaller node, a schedule or a new cap. The warm pool and suspend are not built ([results](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-16-v2-warm-sandboxes-design.md#results)) |
| Per-person spend caps | Counting, not refusing. Compressed same-day test 2026-10-17: every run was charged to its person, and none would have been refused. The recommended daily limit is the 5M-token default. Enforcing waits on a longer record ([runbook 04](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#parts-c-and-d--gcp-0-2026-10-17-compressed-same-day-test)) |
| Live auto-merge of link fixes and their reverts | GitHub setup (the merger App's permissions and two rulesets), then a live drill ([runbook 12](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md)) |
| A second repository, `ai-native-ref` | The repository is prepared; GitHub setup, then the live checks ([design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-16-v2-second-repository-design.md)) |

### Next on gcp-0 {#next-on-gcp-0}

1. The owner's call on the warm node's idle cost: a smaller node, a schedule or a new cap.
2. The shadow budget alert fixed so it fires on the first overrun, then a longer shadow record before either cap is enforced.
3. The GitHub setup, then the live auto-merge drill and the second repository.

## Roadmap {#v2-roadmap}

Each gate is a go/no-go on evidence; how each v2 decision is weighed is in the [v1 review](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-12-agent-factory-v1-review.md#how-v2-is-judged).

| Next | When |
|---|---|
| A sandbox runtime spike, Substrate against agent-sandbox | Two days at the next `gcp-0` rebuild ([alternatives]({{< relref "/docs/platform/ai-platform/agents/alternatives.md" >}})) |
| A continuation loop that picks a PR's next step from its state | Only if a cohort shows tasks abandoned on PRs that could still have been fixed |
| Budgets enforced at the gateway | Built behind one flag, still in shadow. Compressed same-day test 2026-10-17: no real run went over, and a deliberate overrun was admitted and counted. Its alert did not fire, which is to be fixed first. Then the owner flips the flag ([runbook 04, Part D](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#parts-c-and-d--gcp-0-2026-10-17-compressed-same-day-test)) |

### Serving {#serving-roadmap}

| Path | Trigger |
|---|---|
| The endpoint picker on a high-traffic model | A model at two replicas or more without a LoRA canary (it is built, enabled on no claim) |
| Saturation of the InferencePool as an autoscaling trigger | Specified, not built: when the endpoint picker is on |
| A bigger coder model on the same L4 GPUs | The 7B coder hits its tool-call or correctness limits |
| A frontier coder on L40S in a second region | The quantized model's quality loss becomes measurable, or full-context work outgrows one L4 |
| Tensor-parallel on four L4 GPUs | The quantized model is not enough, and a second region costs more to run |
| Claude Code on the self-hosted models, through a protocol relay | The open-weights models get close enough to be a daily backend, or a no-telemetry workflow needs it |
| Heavier dense models (GLM-4.6, DeepSeek-Coder-V3) | A budget for H100-class GPUs, and stable tool-call parsing in vLLM |
| Cost per tenant | Several consumers share the platform, even simulated by LoRA adapter names |
