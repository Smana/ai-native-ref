---
title: Get started
aliases:
  - /docs/platform/
  - /docs/platform/ai-platform/
linkTitle: Get started
weight: 10
description: "Deploy self-hosted GPU model serving and the Maku reference deployment onto a Cloud Native Reference cluster."
lastVerified: 2026-11-27
diataxis: tutorial
---

Two halves, one GitOps artifact for [Cloud Native Reference](https://cnref.ogenki.io/). **Model serving** runs open-weights vLLM models on cluster GPUs behind Envoy AI Gateway (`ai-gateway` + `llm-platform`). **Maku on Cloud Native Ref** deploys the standalone [Maku](https://maku.ogenki.io/) coding-agent factory (`agent-platform`) wired to this host's ZITADEL, CloudNativePG, Cilium, OpenBao, and Victoria stack.

Looking to run Maku on your laptop or your own Kubernetes cluster without Cloud Native Reference? Start on [maku.ogenki.io](https://maku.ogenki.io/): [Laptop quickstart (15 min)]({{< maku "get-started/quickstart/" >}}) · [Tier-1 Pilot]({{< maku "get-started/pilot/" >}}) · [Install on Kubernetes]({{< maku "install/" >}}).

![The AI Platform in one view: on the serving side, developers and coding clients reach ai-gateway over the tailnet to vLLM models on L4 GPUs scaled by KEDA; on the agents side, Maku runs sandboxed gVisor agents through model-gateway and rooms on maku-broker. Both halves export telemetry to the Victoria stack and Grafana](/images/diagrams/ai-platform-1.svg)

*Source: [`docs/architecture/ai-platform.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/ai-platform.drawio), page 1.*

## Deploy on Cloud Native Reference {#path}

1. **Review the host contract.** Check what the host cluster provides (Gateways, OpenBao mounts, CNPG, Victoria stack) in [Host contract]({{< relref "/docs/reference/host-contract.md" >}}).
2. **Resume the Flux umbrellas.** Resume `ai-gateway`, `agent-platform`, and (optionally, when GPU quota is ready) `llm-platform` from the host cluster.
3. **Use and operate.** Hand off your first task with Maku's [User guide]({{< maku "guide/your-first-task/" >}}), connect editors to `ai-gateway` via [Coding clients]({{< relref "/docs/serving/coding-clients.md" >}}), and manage upgrades and restores with [Day-2 operations]({{< relref "/docs/maku-deployment/day-2.md" >}}).

## Next steps {#next-steps}

{{< cards >}}
  {{< card link="/docs/serving/" title="Model serving" icon="chip" subtitle="vLLM on L4 spot GPUs, KEDA autoscaling, Envoy AI Gateway, Semantic Router, and coding clients." >}}
  {{< card link="/docs/maku-deployment/" title="Maku on CNR" icon="cog" subtitle="Pinned host seams, active policies, and Day-2 operations for Maku on Cloud Native Reference." >}}
  {{< card link="/docs/reference/host-contract/" title="Host contract" icon="link" subtitle="The Flux OCI artifact contract between ai-native-ref and Cloud Native Reference." >}}
  {{< card link="/docs/status/" title="Reference deployment status" icon="map" subtitle="Active cluster, pinned Maku release, serving status, and live validation runbooks." >}}
{{< /cards >}}
