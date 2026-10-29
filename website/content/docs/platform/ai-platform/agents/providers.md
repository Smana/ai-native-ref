---
title: Providers
weight: 38
description: "Moonshot (Kimi K3.1 Pro) and Mistral (Medium, Small) as selectable providers for public work: what they are, where data is processed, and how a class switches them on."
lastVerified: 2026-10-29
---

Every run asks for `agent-default` unless its class picks otherwise: GLM-5.3 on Z.ai for public work,
Claude for internal work. Two more providers are **built and deployed, for public data only**, and
selectable per class. Nothing changes by default. Their live run is in progress (2026-10-29): see the
[status page]({{< relref "/docs/platform/ai-platform/status.md#roadmap" >}}).

| Alias | Model | Tier | Processed in |
|---|---|---|---|
| `kimi-frontier` | Kimi K3.1 Pro (`k3.1-pro`, Kimi Code subscription) | frontier | China |
| `mistral-standard` | Mistral Medium 3.5 (`mistral-medium-2604`) | standard | EU |
| `mistral-light` | Mistral Small 4 (`mistral-small-2603`) | light | EU |

{{< callout type="warning" >}}
**Public data only.** Both are processors the owner approved for public repositories and tasks, not
for internal data. Internal tasks never get them, held three times: the gateway routes them only from
its `public` listener, only the public [capability profiles]({{< relref "/docs/platform/ai-platform/agents/roles.md#profiles" >}})
list their aliases, and the factory applies a class's choice to public tasks only.
{{< /callout >}}

## Switch a class on

One key on the class's `loops` row, in `tooling/base/agent-factory/helm-values-configmap.yaml`:
`models.<role>.<tier>` is the alias that role runs on for a public task of that tier.

```yaml
loops:
  docs: {scope: scoper, …, models: {implementer: {standard: mistral-standard}, reviewer: {frontier: kimi-frontier}}}
```

| Rule | Why |
|---|---|
| Each alias serves its own tier only; the factory refuses one on another tier at config load | The run caps stay the tier's, and the gateway's hourly token limit stays above a run's cap spent on cache reads |
| A role or tier without an entry keeps today's model | No default changes |
| `loops.<class>.judge` may name `mistral-light` | The judge's field is already an alias |
| Each run is priced at the provider's list price, cache reads included (`meter.prices`) | The run's dollar cap and spend per identity stay true |

A run never switches model mid-conversation, and there is no failover to another provider: a
provider's 429 ends the run, as Z.ai's does.

## Owner prerequisites

The agents' own keys, in OpenBao: `bao kv put -mount=agents moonshot api_key=-` and
`bao kv put -mount=agents mistral api_key=-` (owner action 2c in the
[runbooks README](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md#owner-actions-in-order)),
each capped on its provider's console: Mistral is pay-as-you-go, capped at $20, and Kimi Code is a
flat-rate plan. The smoke through the gateway is in
[runbook 14](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/14-gcp-0-session.md#feature-15-providers-a-smoke-through-the-gateway).
