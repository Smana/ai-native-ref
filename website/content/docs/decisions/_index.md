---
title: Decisions
weight: 70
description: "Architecture decision records for self-hosted model serving and the Cloud Native Reference deployment (0003–0057)."
lastVerified: 2026-11-27
---

This section holds the **7 architecture decision records** that govern self-hosted GPU model serving and this repository's host integration with [Cloud Native Reference](https://cnref.ogenki.io/docs/decisions/).

The **15 Maku product ADRs** (`0041`–`0045`, `0048`–`0049`, `0051`, `0053`, `0056`, `0058`–`0062`) moved to [maku.ogenki.io/docs/decisions/](https://maku.ogenki.io/docs/decisions/) keeping their original numbers (next Maku ADR: **0063**). Host infrastructure decisions (Flux, Cilium, OpenBao, cloud IAM) stay on [cnref.ogenki.io](https://cnref.ogenki.io/docs/decisions/).

## Serving and host-deployment records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0003]({{< relref "/docs/decisions/0003-vllm-production-stack-over-kserve.md" >}}) | Use vLLM Production Stack over KServe + llm-d for v1 LLM Platform | Accepted | 2026-04-30 |
| [0004]({{< relref "/docs/decisions/0004-amazon-s3-files-for-model-weights-storage.md" >}}) | Use Amazon S3 Files for LLM Model Weights Storage | Accepted | 2026-05-01 |
| [0021]({{< relref "/docs/decisions/0021-gcs-fuse-for-model-weights-on-gcp.md" >}}) | Cloud Storage FUSE for LLM model weights on GCP | Accepted | 2026-08-26 |
| [0046]({{< relref "/docs/decisions/0046-frontier-providers-zai-and-bedrock.md" >}}) | Frontier models through Z.ai and keyless Anthropic per cloud (Bedrock on aws-0, Vertex on gcp-0) | Partly superseded by [0054]({{< relref "/docs/decisions/0054-agent-model-providers-anthropic-direct.md" >}}): internal-data provider only | 2026-09-25 |
| 0047 | Reserved, not yet written: how a request's complexity is classified for routing (SP4) | Reserved | — |
| [0050]({{< relref "/docs/decisions/0050-token-budgets-envoy-gateway-rate-limit.md" >}}) | Token budgets on Envoy Gateway's global rate limit, costed from response metadata | Partly superseded by [ADR-0053](https://maku.ogenki.io/docs/decisions/0053-agent-router-on-agentgateway/): agent router only | 2026-09-25 |
| [0054]({{< relref "/docs/decisions/0054-agent-model-providers-anthropic-direct.md" >}}) | Internal agent work calls the Anthropic API directly; public work stays on Z.ai, with OpenRouter optional | Accepted | 2026-10-01 |
| [0057]({{< relref "/docs/decisions/0057-ai-platform-own-repository.md" >}}) | The AI platform moves to its own repository, consumed by cloud-native-ref as a pinned artifact | Accepted | 2026-10-12 |
