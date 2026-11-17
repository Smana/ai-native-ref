---
title: AI Native Reference
layout: hextra-home
images: [media/agent-factory-poster.jpg]
description: "The AI platform of Cloud Native Reference: self-hosted model serving and the Agent Factory, which turns labelled issues into sandboxed agent runs, deployed on its host as one signed, pinned Flux artifact."
---

{{< hero-video clip="agent-factory" alt="The Agent Factory in 32 s: a labelled issue becomes a sandboxed agent run, watched and steered in a room; every call goes through agentgateway under the run's own identity and budget; the agent opens a pull request that a human reviews and merges." >}}

{{< hextra/hero-badge >}}
  Open source · Apache-2.0 · runs on a Cloud Native Reference cluster
{{< /hextra/hero-badge >}}

{{< hextra/hero-headline >}}
  Models and coding agents, on your own Kubernetes platform
{{< /hextra/hero-headline >}}

{{< hextra/hero-subtitle >}}
  Open-weights models served on the cluster's GPUs behind an OpenAI-compatible gateway, and
  the Agent Factory, which turns a labelled issue into a sandboxed run with its own identity and budget.
  One signed OCI artifact that Cloud Native Reference pins.
{{< /hextra/hero-subtitle >}}

{{< hextra/hero-button text="The AI platform" link="docs/get-started/" >}}
{{< hextra/hero-button text="The host: Cloud Native Ref ↗" link="https://cnref.ogenki.io/" style="background:transparent;border:1px solid rgba(148,163,184,0.45);color:inherit" >}}

{{< /hero-video >}}

## Watch a real task

Hand a defect from OpenCode to Maku, review its pull request and approve the merge.

- [Hand it off, get a PR — 23 seconds](https://github.com/Smana/ai-native-ref-screencasts/blob/main/ai-factory-short.webm)
- [The factory, end to end — 54 seconds](https://github.com/Smana/ai-native-ref-screencasts/blob/main/ai-factory-demo.webm)

Both recordings are silent and captioned. The longer cut includes the clarification, sandboxed roles, Kubernetes runs and per-role cost.
