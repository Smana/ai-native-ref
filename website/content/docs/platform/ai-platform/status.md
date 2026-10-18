---
title: Status and roadmap
weight: 60
description: "What the AI platform does today, what is in progress, and what comes next."
lastVerified: 2026-10-18
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
    cloud["The factory on gcp-0"]
    warm["Warm sandboxes, off by default"]
    second["A second repository"]
    suspend["Suspend"]
    merge["Live auto-merge"]
    budgets["Gateway budgets enforced"]
  end
  subgraph progress["In progress"]
    caps["Per-person caps"]
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
| The factory on `gcp-0` | Part of v2.0, first planned as a separate v2.1. The whole factory runs on GKE alone: a labelled issue became a merged pull request on release pins, its room followed live, and the gVisor pool scaled to its second node ([runbook 14](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/14-gcp-0-session.md)) |
| Warm sandboxes, off by default on this platform | Turned on, a run starts in 16–17 s instead of 1.5–3.5 min (target 30 s), and a run preempts the warm capacity, never the reverse. Off here, since the warm node costs about $126 a month; a production platform turns it on with one value ([headroom](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-16-v2-warm-sandboxes-design.md#headroom-off-by-default-on-for-production)) |
| A second repository, `ai-native-ref` | The factory takes issues from both repositories side by side. A room, a resumed branch or a run's token never crosses to the other repository, and a fence file names the one factory that acts on each. Proven on gcp-0 on 2026-10-18, except the read-only caller check (P5), not proven live ([results](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-16-v2-second-repository-design.md#results)) |
| Suspend | A run waiting on a human gives up its pod and resumes with the same workspace and conversation, proven on gcp-0 on 2026-10-18 ([runbook 01](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/01-runtime-sandbox.md#step-8--gcp-0-2026-10-18-ai-native-ref-v0114)) |
| Live auto-merge of link fixes and their reverts | A pull request that only fixes Markdown link targets merges without a human, at most once a day, at the head the gate decided. A revert asked with `factory/revert` is opened by the merger and demotes the class to human review. Proven on gcp-0 on 2026-10-18; the revert's own unattended merge is fixed in agent-platform #158 and proven offline ([runbook 12](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md#2026-10-18-afternoon-gcp-0-g2-and-g3)) |
| Budgets enforced at the gateway | Since 2026-10-18 the gateway refuses an agent's call over its run, fleet or Anthropic budget with `429 agent_budget_exhausted`, instead of only counting it; a refusal was proven live the same day. Before the flip, a shadow record showed no real run over, and the overrun alert fires. The refusal alert reads the ratelimit service since [#81](https://github.com/Smana/ai-native-ref/issues/81), replay-proven on the live refusal ([runbook 04, Part D](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-d--enforcing-the-agents-budgets)) |
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
| Per-person spend caps | Counting, not refusing. Compressed same-day test 2026-10-17: every run was charged to its person, and none would have been refused. The recommended daily limit is the 5M-token default. Enforcing waits on counting cache reads at their discounted weight (agent-platform #155) and a longer record ([runbook 04](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#parts-c-and-d--gcp-0-2026-10-17-compressed-same-day-test)) |

### Next on gcp-0 {#next-on-gcp-0}

1. Per-person caps: count cache reads at their weight (agent-platform #155), then a longer shadow record before enforcing.
2. The breaker's live proof and the revert's unattended merge, at the next `docs-links` pull request and revert.

## Roadmap {#v2-roadmap}

Each gate is a go/no-go on evidence; how each v2 decision is weighed is in the [v1 review](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-12-agent-factory-v1-review.md#how-v2-is-judged).

| Next | When |
|---|---|
| Substrate as the sandbox runtime | Spike passed on `gcp-0` 2026-10-18: a run restores on another node with its conversation intact, and warm-starts in 2.9 s. Not adopted now (beta kubelet gates, a second control plane, no published images); next look 2026-12-15, or sooner if those costs shrink upstream ([spike](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-17-substrate-spike.md#conclusion)) |
| The warm pool: pre-warmed sandboxes handed to a run (binder W1) | After v2; needs the owner's acceptance of the binder's token-minting authority ([results](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-16-v2-warm-sandboxes-design.md#results)) |
| A continuation loop that picks a PR's next step from its state | Only if a cohort shows tasks abandoned on PRs that could still have been fixed |

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
