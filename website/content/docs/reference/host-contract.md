---
title: Host contract
weight: 30
description: What cloud-native-ref guarantees the AI platform, and what the AI platform guarantees back.
lastVerified: 2026-10-16
aliases:
  - /docs/host-contract/
---

The AI platform runs on a cluster built by
[Cloud Native Reference](https://cnref.ogenki.io/), which pulls this repository as one signed,
digest-pinned `OCIRepository` (`ai-native-ref` in `flux-system`, suspended until a cluster opts in).
What the host guarantees (Flux names, substitution variables, Gateways, namespaces, OpenBao mounts,
compute, storage, observability) and what this repository guarantees back is the
[host contract](https://github.com/Smana/ai-native-ref/blob/main/HOST-CONTRACT.md). Changing an
item is a breaking change for both repositories.

Turning the platform on, from the host:

```bash
flux resume source oci ai-native-ref -n flux-system
flux resume kustomization ai-gateway -n flux-system
flux resume kustomization llm-platform -n flux-system
flux resume kustomization agent-platform -n flux-system
```
