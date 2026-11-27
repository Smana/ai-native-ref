---
title: Documentation
weight: 1
description: "Self-hosted GPU model serving and the Cloud Native Reference deployment of Maku, shipped as one signed Flux artifact."
lastVerified: 2026-11-27
---

This site documents `Smana/ai-native-ref`: the manifests the host's three umbrella Kustomizations (`ai-gateway`, `llm-platform`, `agent-platform`) deploy onto [Cloud Native Reference](https://cnref.ogenki.io/).

For Maku's product documentation — laptop quickstart, 12-chapter user guide, architecture, Kubernetes install seams, operations, reference, and product ADRs — visit **[maku.ogenki.io](https://maku.ogenki.io/)**.

{{< cards >}}
  {{< card link="serving/" title="Model serving" icon="chip" subtitle="vLLM on L4 spot GPUs, KEDA autoscaling, Envoy AI Gateway, Semantic Router, coding clients, and telemetry." >}}
  {{< card link="maku-deployment/" title="Maku on CNR" icon="cog" subtitle="How ai-native-ref wires Maku's Flux umbrella onto Cloud Native Reference, plus Day-2 operations." >}}
  {{< card link="reference/" title="Reference & host contract" icon="link" subtitle="The InferenceService claim and the Cloud Native Reference host contract." >}}
  {{< card link="decisions/" title="Decisions" icon="scale" subtitle="The 7 serving and host-deployment ADRs (Maku product ADRs live on maku.ogenki.io)." >}}
  {{< card link="status/" title="Reference deployment status" icon="map" subtitle="Active cluster, pinned Maku release, serving status, and live validation runbooks." >}}
{{< /cards >}}
