---
title: Get started
aliases:
  - /docs/platform/
  - /docs/platform/ai-platform/
linkTitle: Get started
weight: 10
description: "Three steps from zero to a merged pull request: run Maku on a laptop, deploy this platform on the host cluster, and hand the factory your first task."
lastVerified: 2026-11-15
diataxis: tutorial
---

Two halves, one platform. **Serving** runs open-weights models on the cluster's own GPUs behind an
OpenAI-compatible gateway. **Maku** puts models to work: a labelled issue becomes a sandboxed agent
run that opens a pull request, under its own identity and in a room humans can watch and steer.

{{< callout type="warning" >}}
What runs today, what is experimental and what comes next live on one page:
[Status and roadmap]({{< relref "/docs/status.md" >}}). Every other page describes the design.
{{< /callout >}}

![The AI Platform in one view. On the serving side, developers and coding clients send OpenAI-compatible requests over the tailnet to ai-gateway (Envoy AI Gateway with an API key and the Semantic Router), which routes them to vLLM models declared as InferenceService claims, on L4 GPUs and scaled by KEDA. On the agents side, a maintainer labels a GitHub issue; the factory controller, maku-factory, turns it into a task, starts an agent run in a gVisor sandbox and opens a room on maku-broker that the maintainer watches and steers. Every model call the agent makes goes through the model gateway with a per-run identity, to frontier models (Z.ai GLM and Claude, with Kimi and Mistral for public work only); with a GitHub token the factory minted for the run, the agent pushes a branch and opens a PR. Both halves send traces, logs and metrics to the Victoria stack and Grafana](/images/diagrams/ai-platform-1.svg)

*Source: [`docs/architecture/ai-platform.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/ai-platform.drawio), page 1.*

## Three steps to a running factory {#path}

```mermaid
flowchart LR
  s1["1 · Try it on a laptop<br/>Maku quickstart · 15 min"] --> s2["2 · Deploy on the host<br/>Host contract + Maku install"]
  s2 --> s3["3 · Hand over a first task<br/>Slack · coding agent · GitHub issue"]
```

1. **Try it on a laptop.** Follow Maku's [quickstart]({{< maku "docs/quickstart.md" >}}) to run the
   full loop on kind or k3d in about 15 minutes: one command asks for your model endpoint and key,
   creates a demo GitHub App and a repository from a template, watches the agents open a pull request
   in a room, and lets the merge gate decide it.
2. **Deploy it on the host.** On a Cloud Native Reference cluster, resume the umbrella Kustomizations
   (`ai-gateway`, `agent-platform`, and optionally `llm-platform`) as described in the
   [host contract]({{< relref "/docs/reference/host-contract.md#turning-the-umbrellas-on" >}}). To
   install Maku on your own Kubernetes cluster with your own identity provider, secrets store and
   GitOps tool, follow Maku's [install guide]({{< maku "docs/install.md" >}}) and
   [repository onboarding guide]({{< maku "docs/onboard-a-repository.md" >}}).
3. **Hand over a first task.** Once the factory is running, walk through
   [Get started in five minutes]({{< relref "/docs/use/guide/your-first-task.md" >}}) in the user
   guide to file one small fix from Slack, your coding agent or a GitHub issue, watch the room, and
   approve the pull request.

## Next steps {#next-steps}

{{< cards >}}
  {{< card link="/docs/use/guide/" title="User guide" icon="book-open" subtitle="How a developer gives work to agents, follows it, steers it and stops it." >}}
  {{< card link="/docs/how-it-works/" title="How it works" icon="cog" subtitle="The parts of the platform: roles, the merge gate, the factory, rooms, the runtime, providers, gateways and serving." >}}
  {{< card link="/docs/operate/" title="Operate" icon="chart-bar" subtitle="Day-2 operations, auto-merge safety, harness tuning and observability." >}}
  {{< card link="/docs/status/" title="Status and roadmap" icon="map" subtitle="The one place state lives: the pinned Maku version, the active cluster, and what is available." >}}
{{< /cards >}}
