---
title: Providers
aliases:
  - /docs/platform/ai-platform/agents/how-it-works/providers/
weight: 50
description: "Moonshot (Kimi K3.1 Pro) and Mistral (Medium, Small) as selectable providers for public work: what they are, where data is processed, and how a class switches them on."
lastVerified: 2026-10-29
diataxis: explanation
---

Every run asks for `agent-default` unless its class picks otherwise: GLM-5.3 on Z.ai for public work,
Claude for internal work. Two more providers are available **for public data only**, and selectable per class. Nothing changes by
default. Each run's cost is metered at the provider's list price, like any other run. Mistral is **not
recommended as an implementer**: it can spend a run's whole token budget on a small change. Their state
is on the [status page]({{< relref "/docs/status.md#roadmap" >}}).

| Alias | Model | Tier | Processed in |
|---|---|---|---|
| `kimi-frontier` | Kimi K3.1 Pro (`k3.1-pro`, Kimi Code subscription) | frontier | China |
| `mistral-standard` | Mistral Medium 3.5 (`mistral-medium-2604`) | standard | EU |
| `mistral-light` | Mistral Small 4 (`mistral-small-2603`) | light | EU |

{{< callout type="warning" >}}
**Public data only.** Both are processors approved for public repositories and tasks, not
for internal data. Internal tasks never get them, held three times: the model gateway serves them only
on its `public` listener, the `AgentRun` refuses an internal run that names one
([what a run may call]({{< relref "/docs/how-it-works/roles.md#profiles" >}})), and the factory applies
a class's choice to public tasks only.
{{< /callout >}}

## Switch a class on

No class names one today: the `loops` map in the `Factory`, `tooling/base/agent-factory/resources/factory.yaml`,
holds only `default: {scope: "off"}`. A class opts in with one key on its `loops` row:
`models.<role>.<tier>` is the alias that role runs on for a public task of that tier, as this sketch shows:

```yaml
loops:
  default: {scope: "off"}
  docs: {scope: scoper, …, models: {implementer: {standard: mistral-standard}, reviewer: {frontier: kimi-frontier}}}
```

| Rule | Why |
|---|---|
| Each alias serves its own tier only; the factory refuses one on another tier at config load | The run caps stay the tier's, and the gateway's hourly token limit stays above a run's cap spent on cache reads |
| A role or tier without an entry keeps today's model | No default changes |
| `loops.<class>.judge` may name `mistral-light` | The judge's field is already an alias |
| Each run is priced at the provider's list price, cache reads included (`meter.prices`) | The run's dollar cap and spend per identity stay true |

**Mistral reasons with `reasoning_effort: "none"`.** agentgateway v1.6.0 parses a Chat Completions
message's `content` as a string only, and Mistral answers with a list of chunks when it reasons, so the
`mistral` backend forces `reasoning_effort` to `"none"` (`infrastructure/base/agent-gateway/mistral.yaml`).
Kimi is unaffected.

A run never switches model mid-conversation, and there is no failover to another provider: a
provider's 429 ends the run, as Z.ai's does.

## Owner prerequisites

The agents' own keys, in OpenBao: `bao kv put -mount=agents moonshot api_key=-` and
`bao kv put -mount=agents mistral api_key=-`. Set a spend cap for each key on its provider's console.
A smoke test through the gateway is in
[runbook 14](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/14-gcp-0-session.md#feature-15-providers-a-smoke-through-the-gateway).

## Why self-host at all {#why-self-host-at-all}

A hosted API is cheaper, faster to adopt, and better at the frontier. The self-hosted serving layer on
this platform exists for the things a hosted API cannot give you:

- **Prompts never leave the tailnet.** Every request path here is private — there is no public
  endpoint, and no third party sees the code being completed. That is the whole reason the coding fleet
  exists.
- **The model is pinned to a commit.** `model.revision` is a HuggingFace commit SHA, so the model
  behind an endpoint cannot change under you. A hosted endpoint's weights move when the provider
  decides.
- **Latency is a scheduling problem, not a queue you do not control.** Tab-completion needs sub-200 ms;
  that is achievable when the replica is yours and always warm, and not negotiable with a shared API.
- **It is a real workload for the platform to carry.** GPUs, spot reclaim, saturation-based
  autoscaling, a shared RWX filesystem and an ext_proc-filtered gateway exercise parts of this platform
  that a stateless web app never touches.

And the honest side of the ledger: there is **no scale-to-zero** — see
[Autoscaling & GPUs]({{< relref "/docs/how-it-works/serving/autoscaling-and-gpu.md" >}}) for the
four-GPU cost floor that implies, and why it is a deadlock rather than a missing feature.
