---
title: Observability
linkTitle: Observability
aliases:
  - /docs/operate/observability/
  - /docs/platform/ai-platform/observability/
weight: 40
diataxis: explanation
description: "How serving and Maku signals wire into Cloud Native Reference's shared VictoriaMetrics, VictoriaLogs, VictoriaTraces, and Grafana stack."
lastVerified: 2026-11-27
---

Both self-hosted model serving and Maku emit into Cloud Native Reference's shared Victoria stack and Grafana; nothing here runs a second telemetry pipeline. Serving is watched per model; Maku runs are watched per run.

```mermaid
flowchart LR
  subgraph serving["Serving"]
    V["vLLM pods<br/>vllm:* :8000"]
    AIG["ai-gateway extproc<br/>gen_ai_* :1064"]
  end
  subgraph agents["Maku (agent-platform)"]
    RUN["Agent run<br/>OTLP spans, step log"]
    AGW["agentgateway model-gateway<br/>access log, gen_ai_* :15020"]
    KSM["kube-state-metrics<br/>AgentRun state"]
  end
  VM[("VictoriaMetrics")]
  VL[("VictoriaLogs")]
  VT[("VictoriaTraces")]
  COL["agent-traces-collector<br/>allowlisted metadata"]
  KEDA["KEDA<br/>three triggers"]
  G["Grafana"]
  V --> VM
  AIG --> VM
  VM --> KEDA
  RUN --> COL --> VT
  RUN -->|step log| VL
  AGW --> VL
  AGW --> VM
  KSM --> VM
  VM --> G
  VL --> G
  VT --> G
```

## Serving telemetry {#serving}

| Signal | Source | Read it in |
|---|---|---|
| Engine metrics | Each vLLM pod's `/metrics` on port 8000 (`vllm:*` labelled by `model_name`), scraped by the `VMServiceScrape` each claim renders (`30s` interval) | *LLM Platform — Self-hosted vLLM Fleet*: replicas, queue depth, throughput, TTFT and decode latency, GPU KV-cache usage, prefix-cache hit rate |
| Gateway metrics | The AI Gateway extproc's `/metrics` on port 1064 (`gen_ai_*` OTel semantic conventions) | *LLM Gateway — Envoy AI Gateway GenAI Telemetry*: token spend per model, base-vs-canary attribution, TTFT and decode latency |
| Autoscaling | KEDA's three triggers query the same `vllm:*` series every 15 s | [Autoscaling & GPUs]({{< relref "/docs/serving/autoscaling-and-gpu.md" >}}) |

Both dashboards live in Grafana folder `llm` (`apps/base/ai/llm/grafana-folder.yaml`), created once `llm-platform` is resumed.

**Serving alerts** are lagging signals, deliberately not scale triggers:

| File | Alerts |
|---|---|
| `apps/base/ai/llm/vmrule-llm-slo.yaml` | Sustained queue depth, TTFT breached, replica scaled to zero, missing `gen_ai` telemetry, scrape down, high error rate, canary regressions |
| `apps/base/ai/llm/vmrule-ai-fleet.yaml` | Fleet abort rate, Semantic Router down, Promptfoo regression and staleness |

## Shared Victoria wiring for Maku {#agents}

On this host, `observability/base/agent-platform/` wires Maku's `maku_factory_*`, `maku_rooms_*`, and `agentgateway` signals into the same Victoria stack:

| Signal | Manifest path on this host |
|---|---|
| Grafana dashboards (`agent-run`, `agent-fleet`, `agents-overview`, `agent-room`, `agent-gateway`, `agent-identity`, `agent-factory`) | `observability/base/agent-platform/` |
| Factory and gateway alert rules (`VMRule`) | `observability/base/agent-platform/vmrule-agent-factory.yaml`, `observability/base/agent-platform/vmrule.yaml` |
| Metadata-only OTel trace gate (`agent-traces-collector`) | `observability/base/agent-platform/agent-traces-collector.yaml` |
| `agentgateway` → `gen_ai_*` cache-token scrape relabelling | `infrastructure/base/agent-gateway/vmpodscrape.yaml` |

Full Maku metric definitions, alert runbooks, and standalone observability setup live on Maku's documentation site: [Install › Observability]({{< maku "install/observability/" >}}), [Reference › Metrics]({{< maku "reference/metrics/" >}}), and [Reference › Alerts]({{< maku "reference/alerts/" >}}).
