---
title: Decisions
weight: 60
description: The AI platform's architecture decision records — what was chosen, and what it was chosen over.
lastVerified: 2026-10-16
---

The records behind the AI platform: serving, the agent factory and the split from its host. They
moved here from [cloud-native-ref](https://cnref.ogenki.io/docs/decisions/) with their numbers
(split design §8); the next record here is **0059**. Host decisions (Flux, Cilium, OpenBao, EKS Pod
Identity, …) stay on the host site and are linked, not copied.

A technology choice with a rejected alternative needs a record before merge. Version bumps,
chart-value changes and single-file fixes never do. Start from the host's
[template](https://github.com/Smana/cloud-native-ref/blob/main/website/content/docs/decisions/template.md).

## The records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0003]({{< relref "/docs/decisions/0003-vllm-production-stack-over-kserve.md" >}}) | Use vLLM Production Stack over KServe + llm-d for v1 LLM Platform | Accepted | 2026-04-30 |
| [0004]({{< relref "/docs/decisions/0004-amazon-s3-files-for-model-weights-storage.md" >}}) | Use Amazon S3 Files for LLM Model Weights Storage | Accepted | 2026-05-01 |
| [0021]({{< relref "/docs/decisions/0021-gcs-fuse-for-model-weights-on-gcp.md" >}}) | Cloud Storage FUSE for LLM model weights on GCP | Accepted | 2026-08-26 |
| [0041]({{< relref "/docs/decisions/0041-agent-sandbox-gvisor-al2023.md" >}}) | Coding agents run in agent-sandbox Sandboxes under gVisor, on a dedicated spot pool per cloud, with OpenHands as the harness profile | Accepted | 2026-09-26 |
| [0042]({{< relref "/docs/decisions/0042-agent-router-identity-gateway.md" >}}) | Agent Router is the agents' identity gateway, with role and data class encoded in the token audience and an in-pod proxy holding the tokens | Partly superseded by [0053]({{< relref "/docs/decisions/0053-agent-router-on-agentgateway.md" >}}): Option 1, agent router only | 2026-09-26 |
| [0043]({{< relref "/docs/decisions/0043-octo-sts-for-agent-github-tokens.md" >}}) | Agents get GitHub tokens from a self-hosted octo-sts, scoped per repository and role, and two rulesets confine their App to agent branches and no tags | Accepted | 2026-09-26 |
| [0044]({{< relref "/docs/decisions/0044-room-session-protocol.md" >}}) | Rooms are an AHP-shaped log we own, stored in CNPG, fanned out with Postgres LISTEN/NOTIFY | Accepted | 2026-09-27 |
| [0045]({{< relref "/docs/decisions/0045-merge-policy-gate.md" >}}) | palantir/policy-bot, required through a repository ruleset, decides which agent PRs merge | Accepted | 2026-09-27 |
| [0046]({{< relref "/docs/decisions/0046-frontier-providers-zai-and-bedrock.md" >}}) | Frontier models through Z.ai and keyless Anthropic per cloud (Bedrock on aws-0, Vertex on gcp-0) | Partly superseded by [0054]({{< relref "/docs/decisions/0054-agent-model-providers-anthropic-direct.md" >}}): internal-data provider only | 2026-09-25 |
| 0047 | Reserved, not yet written: how a request's complexity is classified for routing (SP4) | Reserved | — |
| [0048]({{< relref "/docs/decisions/0048-agent-factory-orchestrator.md" >}}) | A custom Task controller with Kueue admission orchestrates the agent factory | Accepted | 2026-09-27 |
| [0049]({{< relref "/docs/decisions/0049-room-client-and-human-auth.md" >}}) | Humans reach rooms through a web UI the broker serves, behind oauth2-proxy | Accepted | 2026-09-27 |
| [0050]({{< relref "/docs/decisions/0050-token-budgets-envoy-gateway-rate-limit.md" >}}) | Token budgets on Envoy Gateway's global rate limit, costed from response metadata | Partly superseded by [0053]({{< relref "/docs/decisions/0053-agent-router-on-agentgateway.md" >}}): Option 1, agent router only | 2026-09-25 |
| [0051]({{< relref "/docs/decisions/0051-otel-collector-agent-trace-gate.md" >}}) | An OpenTelemetry Collector is the agent trace gate | Accepted | 2026-09-27 |
| [0053]({{< relref "/docs/decisions/0053-agent-router-on-agentgateway.md" >}}) | The agent router runs on agentgateway, pinned to a minor that passes our live gate; ai-gateway stays on Envoy Gateway | Accepted | 2026-10-01 |
| [0054]({{< relref "/docs/decisions/0054-agent-model-providers-anthropic-direct.md" >}}) | Internal agent work calls the Anthropic API directly; public work stays on Z.ai, with OpenRouter optional | Accepted | 2026-10-01 |
| [0056]({{< relref "/docs/decisions/0056-local-first-factory-ux.md" >}}) | The factory is driven from the developer's local agent through a skill and roomctl, and a room is as visible as its repo on GitHub | Accepted | 2026-10-08 |
| [0057]({{< relref "/docs/decisions/0057-ai-platform-own-repository.md" >}}) | The AI platform moves to its own repository, consumed by cloud-native-ref as a pinned artifact | Accepted | 2026-10-12 |
| [0058]({{< relref "/docs/decisions/0058-reviewer-on-another-model.md" >}}) | The factory's reviewer on public tasks runs on another model family | Proposed | 2026-10-16 |
