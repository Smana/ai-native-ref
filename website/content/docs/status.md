---
title: Reference deployment status
aliases:
  - /docs/platform/ai-platform/status/
linkTitle: Status
weight: 60
description: "Active reference cluster, pinned Maku release, self-hosted serving posture, and live validation runbooks."
activeCluster: gcp-0
lastVerified: 2026-11-27
---

This page tracks the **reference deployment** on [Cloud Native Reference](https://cnref.ogenki.io/): which cluster currently owns intake, which Maku release is pinned on `main`, where self-hosted GPU serving stands, and where live validation logs live.

For **Maku product maturity, proven capabilities, and the v5 roadmap**, see [Maku › Status and roadmap]({{< maku "status/" >}}).

<span id="clusters"></span><span id="rebuild"></span><span id="roadmap"></span><span id="v2-roadmap"></span><span id="experimental"></span>

## Current deployment {#deployment}

- **Active:** `gcp-0` (pinned in `.github/agent-factory.yaml`; `aws-0` stays ready to swap via [Day-2 operations]({{< relref "/docs/maku-deployment/day-2.md#switch-the-active-cluster" >}})).
- **Pinned Maku release on `main`:** Maku {{< maku-version >}} (`tooling/base/agent-factory/helm-values-configmap.yaml`).
- **Default harness:** OpenCode since 2026-11-27 (OpenHands via `harness:openhands` or automatic fallback on Gemini/Vertex aliases).
- **Live unattended merge policies:** `docs-links` on `Smana/cloud-native-ref` only; all other policies run in `shadow`.
- **Upkeep routines:** six starter `Routine` objects enabled in catalog (`routines.uiWrite: false`), inert until bound in GitOps.

{{< partner-card >}}

## Self-hosted serving status {#serving-roadmap}

| Area | State | Reference |
|---|---|---|
| `ai-gateway` (Envoy AI Gateway + `tier-frontier`) | Active (`spec.suspend: false`), CPU-only | [AI Gateway]({{< relref "/docs/serving/ai-gateway.md" >}}) |
| `llm-platform` (vLLM on L4 spot GPUs, KEDA, Semantic Router) | Built and verified; ships suspended (`spec.suspend: true`) to avoid the 4-GPU always-warm cost floor | [Model serving]({{< relref "/docs/serving/_index.md" >}}), [Autoscaling & GPUs]({{< relref "/docs/serving/autoscaling-and-gpu.md" >}}) |
| Known serving gaps | `xplane-llamaguard3-1b` has no Semantic Router rule; 3 of 4 claims still use hand-written routes; Inference Extension endpoint picker is off (mutually exclusive with LoRA canaries); Semantic Router decisions are not yet exported as VictoriaMetrics series; Claude Code (`/v1/messages`) and Codex (`/v1/responses`) are not served by `ai-gateway` | [Serving known gaps]({{< relref "/docs/serving/_index.md#known-gaps" >}}) |
| Serving next steps | Native GPU time-slicing (`--gpu-memory-utilization`) and `kvcached` once GPU sharing is justified | [Autoscaling & GPUs]({{< relref "/docs/serving/autoscaling-and-gpu.md#gpu-sharing" >}}) |

## Live validation runbooks {#runbooks}

Every capability marked "Proven live" on [Maku › Status]({{< maku "status/" >}}) cites runbooks and session logs in this repository:

- [Runbook index](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md)
- [04 · Gateway secrets, budgets, and cost cross-check](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md)
- [07 · End-to-end issue-to-PR run](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/07-end-to-end.md) · [10 · Spot disruption recovery](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/10-disruption.md)
- [12 · Live auto-merge & revert breaker drill](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md) · [Results (2026-10-30)](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-aws-0-2026-10-30.md)
- [19 · Coding agents](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/19-factory-from-your-agent.md) · [20 · RunLore agent-to-agent](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/20-runlore-agent-to-agent.md) · [22 · Slack](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/22-slack.md)
- [28 · v4 validation](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/28-v4-aws-validation.md) · [Results (2026-11-16)](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-aws-0-2026-11-16.md)
