---
title: AI Gateway
linkTitle: AI Gateway
aliases:
  - /docs/how-it-works/gateways/
  - /docs/platform/ai-platform/gateways/
weight: 20
diataxis: explanation
description: "Envoy AI Gateway for humans and coding clients: OpenAI-compatible API, API keys, Semantic Router (MoM), LoRA canaries, and shadow token budgets."
lastVerified: 2026-11-27
---

Humans and coding clients reach self-hosted and frontier models through **`ai-gateway`** (Envoy Gateway + Envoy AI Gateway). It speaks the OpenAI API: a client points at one endpoint, names a model — or asks the Semantic Router (`model: MoM`) to choose one — and never learns which pod answered.

For agent runs, Maku uses its own **`model-gateway`** (`agentgateway`, configured by the `maku-gateway` chart with per-run JWT audiences and data-class listeners): see Maku's [Model gateway]({{< maku "install/gateway/" >}}), [Model routing and cost]({{< maku "concepts/routing-and-cost/" >}}), and [Maku on Cloud Native Ref]({{< relref "/docs/maku-deployment/_index.md" >}}).

![The two gateways side by side: humans and coding clients reach ai-gateway over the tailnet with an API key, while agent runs call Maku's model-gateway with per-run tokens. Both write access logs and gen_ai metrics to the Victoria stack](/images/diagrams/ai-platform-2.svg)

*Source: [`docs/architecture/ai-platform.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/ai-platform.drawio), page 2.*

## Sending a request {#sending-a-request}

Example (the reference host):

```bash
# What's available
curl -sS https://llm.priv.aws.ogenki.io/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY" | jq '.data[].id'

# Name a model explicitly — skips classification entirely
curl -sS https://llm.priv.aws.ogenki.io/v1/chat/completions \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
        "model": "xplane-qwen-coder",
        "messages": [{"role": "user", "content": "Write a Go worker pool."}]
      }'

# Let the Semantic Router choose from the prompt
curl -sS https://llm.priv.aws.ogenki.io/v1/chat/completions \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
        "model": "MoM",
        "messages": [{"role": "user", "content": "Write a Go worker pool."}]
      }'
```

The two calls reach the same pod. The difference is roughly **250–300 ms** of classification on the `MoM` path — worth it when the client cannot know which model suits the prompt, wasted when it can. See [Coding Clients]({{< relref "/docs/serving/coding-clients.md" >}}) for which client pins which model, and why.

## The request path {#the-request-path}

The [hop-by-hop request path](/images/diagrams/llm-platform-1.svg) shows each stage below in one picture.

**Ingress.** External clients arrive over Tailscale at the Cilium Gateway `platform-tailscale-general` and are forwarded to the Envoy AI Gateway data-plane Service. In-cluster clients — OpenWebUI and the nightly Promptfoo eval — address that Service directly. Nothing is reachable from the public internet; see [Private access](https://cnref.ogenki.io/docs/platform/networking/private-access/).

**Authentication.** A `SecurityPolicy` (`apiKeyAuth`) targets the Gateway, so every route inherits it rather than each declaring its own. Keys come from the cloud secret store or External Secrets generators, and the gateway strips the `Authorization` header before forwarding — vLLM never sees a credential.

| Client id | Who holds it | What it names |
|---|---|---|
| `openwebui` | OpenWebUI, in cluster | Whatever model its user picks, `MoM` included |
| `promptfoo` | The nightly evaluation, in cluster | The models its suites name |

**Prompt classification (`ext_proc`, filter index 0).** The Semantic Router is wired in as an Envoy `ext_proc` gRPC filter, inserted **ahead of** the AI Gateway's own extproc by an `EnvoyPatchPolicy` (`infrastructure/base/envoy-ai-gateway/envoypatchpolicy-semantic-router.yaml`). The router rewrites `body.model` only when the client sent `model: MoM` (or `auto`); an explicit `xplane-*` name passes through untouched.

**Routing.** The AI Gateway extproc derives the `x-ai-eg-model` header from the (possibly rewritten) body and emits `gen_ai_*` telemetry. An `AIGatewayRoute` matches that header and forwards through an `AIServiceBackend` → `Backend` → the model's Service on port 8000. Three of the four claims still route via a hand-written route; see [known gaps]({{< relref "/docs/serving/_index.md#known-gaps" >}}).

## Semantic routing — `model: MoM` {#semantic-routing}

Sending `model: MoM` lets the Semantic Router (`infrastructure/base/vllm-semantic-router/helmrelease.yaml`) pick from the prompt; the priority table and guardrail exclusions are in [the repository's design records](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md#gateway-routing-and-budgets).

## LoRA canaries {#lora-canaries}

`xplane-qwen-coder` carries two LoRA adapters, each addressable as a model name of its own, and sends 10% of its traffic to one of them:

```yaml
  gateway:
    enabled: true
    canaries:
      - adapter: xplane-qwen-coder-sql-dpo
        weightPercent: 10
```

The adapter name is matched **verbatim** against `loraAdapters[].name` — it is not derived from the base model's name, so a typo produces a route to nothing rather than a validation error. Canaries are mutually exclusive with the Gateway API Inference Extension's endpoint picker ([Status]({{< relref "/docs/status.md#serving-roadmap" >}})).

## Frontier models and shadow budgets {#frontier-models}

`tier-frontier` is served by GLM through Z.ai with the platform key, which only the gateway holds. It needs no GPU, so it answers with `llm-platform` suspended. The `ai-gateway` umbrella generates its API keys in-cluster (Secret `ai-gateway-api-keys` in `envoy-ai-gateway-system`). Identity-header stripping and shadow token budgets ([ADR-0050]({{< relref "/docs/decisions/0050-token-budgets-envoy-gateway-rate-limit.md" >}})) are recorded in [the routing design records](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md#gateway-routing-and-budgets).

## Maku's model gateway {#the-agent-gateway-agent-runs}

Agent runs and the room broker's planner do not call `ai-gateway`; they call Maku's `model-gateway` (`infrastructure/base/agent-gateway/model-gateway/`), deployed on `agentgateway` with per-run projected ServiceAccount tokens, data-class listeners (`public` and `internal`), and rate-limit backstops. See Maku's [Model gateway reference]({{< maku "install/gateway/" >}}) and [ADR-0053]({{< maku "decisions/0053-agent-router-on-agentgateway/" >}}).
