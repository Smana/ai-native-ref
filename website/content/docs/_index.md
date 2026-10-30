---
title: Documentation
weight: 1
description: The AI platform hosted on Cloud Native Reference — serving, the Agent Factory, their decisions and the host contract.
lastVerified: 2026-10-16
---

This site documents `Smana/ai-native-ref`: the manifests the host's three umbrella Kustomizations
(`ai-gateway`, `llm-platform`, `agent-platform`) deploy, and why they are built that way. The
clusters, Flux, Cilium, OpenBao and the rest of the platform are documented on the host site,
[cnref.ogenki.io](https://cnref.ogenki.io/).

{{< cards >}}
  {{< card link="platform/ai-platform/" title="AI platform" icon="sparkles" subtitle="Serving, gateways, the Agent Factory, its rooms and runtime." >}}
  {{< card link="host-contract/" title="Host contract" icon="link" subtitle="What cloud-native-ref guarantees this platform, and what it guarantees back." >}}
  {{< card link="decisions/" title="Decisions" icon="scale" subtitle="The AI platform's architecture decision records." >}}
{{< /cards >}}
