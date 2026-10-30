# otari (mozilla-ai): evaluation against the platform's gateways

**Date:** 2026-10-20 · **Verdict:** watch · **Read at:** otari
[`e6226a5`](https://github.com/mozilla-ai/otari/tree/e6226a5cdd42945a29c36e6327afa5394241734e)
(just after v0.30.1) and any-llm
[`d6b76fd`](https://github.com/mozilla-ai/any-llm/tree/d6b76fd9e594d308a1932fe5172bc8e37ec4d17d).
Every claim is checked in code at these commits unless marked *unverified*. Summary on the site:
[alternatives considered](../../../website/content/docs/platform/ai-platform/agents/alternatives.md#otari).

## Conclusion

otari is an open-source (Apache-2.0) LLM gateway in Python, with a dashboard and a hosted control
plane, otari.ai. Its budgets are stronger than ours in one respect: **it reserves the worst case
before the call**, and it **refuses unpriced models by default**. But it cannot replace agentgateway
for agent runs (no MCP federation, no token exchange, no listener per data class, no OpenTelemetry
export, per-run identity only with one key per run) nor Envoy AI Gateway for people (no prompt-based
model choice, no generic OIDC sign-in, no Gateway API), and it has no Kubernetes packaging. It is a
0.x project changing very fast. Borrow the pre-call reservation idea; watch the project.

## 1. What it is

| Aspect | Finding |
|---|---|
| Process | One Python 3.13 FastAPI/uvicorn process serving the API and a React dashboard ([pyproject](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/pyproject.toml#L15-L100), [Dockerfile](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/Dockerfile#L49-L81)) |
| any-llm | Mozilla.ai's Python SDK, imported in-process to call providers; not a separate service ([pyproject L17](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/pyproject.toml#L17)) |
| Storage | PostgreSQL in production, SQLite to try it; Redis optional, for rate-limit counting only. 117 Alembic migrations run at startup ([database.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/core/database.py#L498-L499)); no lock found around them, so replicas upgrading together may race (*unverified*) |
| Modes | Standalone; hosted control plane only; hybrid, a data plane reporting to otari.ai ([modes.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/modes.md#L9-L16)) |
| Open source vs otari.ai | The hosted control-plane mode is in the Apache-2.0 repository; otari.ai is a proprietary overlay. Billing is overlay-only; enterprise SSO, deeper RBAC and audit are provisionally overlay ([ARCHITECTURE.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/ARCHITECTURE.md#L220-L235)) |
| Maturity | v0.1.0 on [2026-06-25](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/CHANGELOG.md#L1573) to v0.30.1 on [2026-10-20](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/CHANGELOG.md#L7), with 27 breaking entries. On 2026-10-20: 703 stars, 42 contributors, 247 open issues, 64 open PRs, 622 PRs merged in 30 days |
| Kubernetes | None: no Helm chart, operator or CRDs. Docker image, Compose or Railway ([deployment.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/deployment.md#L65-L86)); the image runs as uid 1000 with health endpoints ([Dockerfile](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/Dockerfile#L53-L74)) |
| Config model | YAML or environment, plus database state edited by API or dashboard. Budgets and keys declared in YAML are written at startup and never deleted ([configuration.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/configuration.md#L262-L370)). The `providers:` block, deprecated in 0.30.0, is copied into the database once and then ignored ([main.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/main.py#L374-L417)): a GitOps drift trap. Per-key model allow-lists and identity-federation rules are API-only ([api_keys.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/core/settings/api_keys.py#L36-L80)) |

## 2. Features, checked in code

| Feature | Finding |
|---|---|
| Z.ai GLM | A built-in `zai` provider with an overridable base URL ([zai.py](https://github.com/mozilla-ai/any-llm/blob/d6b76fd9e594d308a1932fe5172bc8e37ec4d17d/src/any_llm/providers/zai/zai.py#L11-L22)); named OpenAI-compatible backends through `api_base` ([example](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/config.example.yml#L30-L36)) |
| vLLM | Built in ([registry.py](https://github.com/mozilla-ai/any-llm/blob/d6b76fd9e594d308a1932fe5172bc8e37ec4d17d/src/any_llm/providers/registry.py#L221-L226)) |
| Anthropic and prompt caching | Calls Anthropic's own Messages API ([base.py](https://github.com/mozilla-ai/any-llm/blob/d6b76fd9e594d308a1932fe5172bc8e37ec4d17d/src/any_llm/providers/anthropic/base.py#L323-L341)) and keeps `cache_control` ([messages_compat.py](https://github.com/mozilla-ai/any-llm/blob/d6b76fd9e594d308a1932fe5172bc8e37ec4d17d/src/any_llm/utils/messages_compat.py#L1132-L1150)); the request is rebuilt by the SDK, not passed byte for byte |
| Routing | Aliases, failover, weighted and spill-over. The kNN "learned" router learns only from examples posted to an API; its stickiness is per process ([routing.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/routing.md#L170-L215)) |
| API keys | Hashed, checked against the database on every request ([deps.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/deps.py#L286-L330)); per-key model allow-list, expiry, service keys that bill end users |
| JWT / OIDC | Verified against the issuer's JWKS, asymmetric algorithms only, at most 24 h lifetime, https issuers. A token maps to **one key** by exact `sub` or email plus `aud` ([_federation.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/services/api_keys/_federation.py#L148-L212), [deps.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/deps.py#L371-L410)); the `sub` is not kept as an identity afterwards |
| Dashboard sign-in | Password, passkeys, Google, GitHub ([access-control.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/access-control.md#L559)); no generic OIDC, so no ZITADEL |
| Budgets | USD, tokens and requests, per user, end user, key, workspace, organisation or member, optionally per provider ([budgets.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/models/budgets.py#L200-L235)) |
| Budget timing | **The worst case is reserved before the call** (prompt characters / 4 plus `max_tokens`) and settled after ([_reservations.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/services/budgets/_reservations.py#L400-L450)); refusal is a 403 `budget_exceeded` ([access-control.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/access-control.md#L477-L489)) |
| Rate limits across replicas | Counted in Redis; with Redis down each replica counts alone, so limits fail open ([configuration.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/configuration.md#L148-L168)) |
| Unpriced models | `require_pricing=true` by default: a 402, fallback models checked too ([pricing.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/core/settings/pricing.py#L84-L92), [_pipeline.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/routes/_pipeline.py#L2349-L2367)); keys exempt from budgets skip the check ([_pipeline.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/routes/_pipeline.py#L3103-L3107)) |
| Price table | Your own, USD per million tokens, database entries winning; a models.dev fallback, off by default, with a bundled snapshot dated 2026-10-08 ([bundled.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/services/pricing/bundled.py#L1-L30)) |
| MCP | **Client only**: it runs the tool loop itself, or lists stored servers' tools and runs one call on request, with a tool allow-list per server ([mcp.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/mcp.md#L1-L60)); not an MCP server agents connect to |
| A2A | None in `src/gateway` |
| Guardrails | Input only, before the provider call; opt-in per request or mandated by the organisation; in block mode an unreachable guardrail service rejects the request ([guardrails.md](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/guardrails.md#L79-L91)) |
| Observability | Prometheus metrics named `gateway_*` ([metrics.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/metrics.py#L136-L155)); only the OpenTelemetry API as a dependency, so no export; gen_ai conventions appear only in an OTLP *receiver* for clients' telemetry ([otlp.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/routes/otlp.py#L1-L35)); traces kept in its own database; no JSON log formatter ([log_config.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/log_config.py#L36-L60)) |
| Audit, cache, streaming | A usage row per request ([usage.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/models/usage.py#L29)), no audit trail; no response cache, only `Idempotency-Key` replay; streaming works |

**Hybrid mode and privacy.** On every request the gateway sends the model, the provider and the
caller's user token to otari.ai, which **returns the provider API keys** for that request
([_platform.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/routes/_platform.py#L612-L630),
[protocol](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/docs/hybrid-mode-protocol.md#L236-L300));
after each attempt it reports token and cache counts, status, error class, session label and
time to first token ([_platform.py](https://github.com/mozilla-ai/otari/blob/e6226a5cdd42945a29c36e6327afa5394241734e/src/gateway/api/routes/_platform.py#L742-L800)).
"Metadata only" holds (no prompts or completions), but otari.ai holds the provider keys and sits on
every request's path. Standalone mode sends nothing except feedback a user submits explicitly.
What otari.ai's own hosted gateway keeps is *unverified*.

## 3. Fit with our requirements

| Requirement (agent gateway) | otari | Why |
|---|---|---|
| A per-run JWT checked on every call | Partly | Checked on every call, but each `sub` must first be bound to a key by a rule: a key and a rule per run, created with the master key. In-cluster issuers need `federation_allow_private_hosts` |
| Listeners per data class | No | One port; keys, workspaces and allow-lists only approximate it |
| Z.ai, Anthropic direct with caching | Yes | Section 2 |
| Static aliases, other names refused | Yes | Aliases and per-key allow-lists, the latter API-only |
| MCP federation, per-role allow-lists | No | Client only |
| Token exchange with octo-sts | No | Its `/oauth/token` issues otari's own tokens only |
| Per-run, fleet and provider budgets | Mostly | Stronger timing than ours (reserve first); per run needs a key per run or a self-declared `user`; refuses with 403, not 429 |
| Our own prices, unpriced fails closed | Yes | Except budget-exempt keys |
| OpenTelemetry gen_ai, JSON logs | No | |
| Network policy, restricted pods, probes, limits | Partly | Non-root image and health endpoints; every manifest would be ours |
| Spot nodes on EKS and GKE | Yes | Stateless replicas over a CNPG database; the migration race is the caveat |
| No long-lived credential in a sandbox | Yes | Through OIDC federation |
| Open source, no SaaS in the data path | Standalone only | Hybrid puts otari.ai on every request |
| Kubernetes-native configuration | No | |

- **Instead of agentgateway:** no. MCP federation, the token exchange, separated listeners, OpenTelemetry
  and per-run identity without extra setup would all be lost.
- **Instead of Envoy AI Gateway for people:** closer (keys per client, budgets, a dashboard, an OpenCode
  guide, vLLM), but nothing picks a model from the prompt (the kNN router needs labelled examples),
  sign-in has no generic OIDC, and there is no Gateway API.
- **Beside them:** any-llm inside the harness would bypass the gateway's controls; otari behind
  agentgateway adds a hop and a second budget engine. Neither.

## 4. Compared

Only the otari column is checked in code here.

| | otari | agentgateway | Envoy AI Gateway | LiteLLM proxy |
|---|---|---|---|---|
| JWT per call | Through a rule per key | Native | Through Envoy Gateway's SecurityPolicy | JWT auth, partly enterprise |
| MCP federation | No | Yes | Yes | Yes |
| Budget timing | Reserve before the call | After the call | After the call | Mostly after; reservation since v1.84.0 |
| Unpriced models | 402 | Our CEL rules | n/a | $0 |
| Kubernetes configuration | None | Gateway API, Helm | CRDs | Helm chart |
| OpenTelemetry gen_ai | No | Yes | Yes | Through callbacks |
| Maturity | 0.x, fast churn | v1.6, Linux Foundation | v1.1 | Large community |

## 5. Recommendation: watch

**Borrow now, without adopting it:** reserve a call's worst case before it runs (prompt estimate plus
`max_tokens`) and re-check pricing for every fallback model. Our ratelimit/CEL budget path could do
the first; the second is already our fail-closed rule.

**Reconsider when:**
1. A Helm chart ships and configuration is declarative: providers, allow-lists and federation rules
   in config, config winning over the database.
2. Spans and metrics are exported over OTLP with the gen_ai conventions.
3. Federation can match a claim pattern, or pass the `sub` through as the end user, so per-run identity
   needs no key per run.
4. otari can act as an MCP server that federates tools with allow-lists.
5. Generic OIDC sign-in reaches the open-source core.
6. A 1.0 with a deprecation policy, or a quarter without breaking releases.
