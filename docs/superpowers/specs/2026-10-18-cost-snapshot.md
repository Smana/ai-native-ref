# Cost snapshot — 2026-10-18

The measurements the [Model routing and cost](https://airef.ogenki.io/docs/platform/ai-platform/routing/)
page and the [harness tuning](https://airef.ogenki.io/docs/platform/ai-platform/agents/tune/harness/)
page carried until 2026-10-31. The pages keep the generic facts and label the reference host's
values as examples; the dated figures, run IDs and plan IDs live here.

## Method

Read-only queries against `gcp-0`'s VictoriaMetrics and its `Task` objects on 2026-10-18 (11:40 UTC).
`gcp-0` had run the factory for about 17 hours, so "24 h" and "7 d" windows cover the same traffic.
Prices are the list prices the repository pins in `meter.prices`, read on 2026-10-16.

## State on `gcp-0`, 2026-10-18

| Piece | State |
|---|---|
| Agent model per data class | Deployed, proven live |
| `kimi-frontier`, `mistral-standard`, `mistral-light` (v3 feature 15) | Proven live on 2026-10-29 |
| Triage classifier (C7) | Design only: all 12 tasks read `classifier: static, fallback: static` |
| 10% control group at `frontier` | Live: 2 of 12 tasks |
| Run meter priced in USD | Proven live ([plan, internal run](../plans/2026-10-15-agent-router-agentgateway-plan.md#live-evidence-internal-run-2026-10-16)) |
| Gateway budgets B1, B2, B6 | Enforced since 2026-10-18 |
| SR `complexity` signal, PII gate, fail-open | Design only (SP4 PR 4: SR 0.3.0) |
| Semantic Router series in VictoriaMetrics | None on `gcp-0`; not investigated |

## Caching

| Where | Cache reads / input |
|---|---|
| `gcp-0`, all agent calls, 24 h to 2026-10-18 | **95.1%** (27.40M of 28.83M) |
| Cohort arm A (GLM-5.3, factory) | 91–96% |
| `wfeiraim`, Opus 5.5 internal run (triager) | 85%: $0.477 for 303,477 input tokens |

On those 24 hours the meter's figure was **$10.40**; the same tokens with no cache discount, **$41.64**.

## The worked example

Run `xplane-run-jcp6kl72`, an implementer on a `standard` task, `public`, served by `glm-5.3`, which
opened [cloud-native-ref#2508](https://github.com/Smana/cloud-native-ref/pull/2508). Its gateway
counters on 2026-10-18 priced at $1.6487; the meter recorded `costMicroUSD: 1648658`, an exact match.

## Runs on `gcp-0`, 2026-10-18, all on GLM-5.3

| Run | Task | Steps | Cost | End |
|---|---|---|---|---|
| `dkpa4r4o` | docs-links | 10 | $0.03 | succeeded |
| `b4cnoos7` | docs | 36 | $0.17 | PR opened |
| `jcp6kl72` | docs-links | 225 | $1.65 | PR opened |
| `d3jacb5z` | dashboards | 319 | $2.65 | out of budget, nothing pushed |
| `kk2egjta` | dashboards, frontier | 444+ | $4.46+ | still running at 66 min |

Under the old 1.5M token cap, `jcp6kl72` (4.48M tokens, $1.65) would have been revoked at a third of
its work; `d3jacb5z` (7.42M, $2.56) was revoked at its USD cap (`budget-run`, fit `under`). The caps
moved to USD by the owner's decision OD-6 ([cloud-native-ref#2369](https://github.com/Smana/cloud-native-ref/issues/2369)).

## Daily caps

Until Maku v0.16.0 the daily caps counted raw tokens, a cache read as a full token: on 2026-10-18 the
fleet's 25M and a person's 5M both read 0 remaining after about $10 of real spend.

## Latency and spend

- Model latency on `glm-5.3`: p50 2.8 s, p95 18.4 s.
- Four always-warm L4 models (about $876 a month on spot) buy about 84 days of the agents'
  2026-10-18 GLM-5.3 spend.

## IDs the page cited

SP4 S5, S6, S7, S8, R10, R13, PR 4, PR 5 and §5 refer to the
[routing design](2026-09-23-llm-complexity-routing-design.md); D8 to the
[factory design](2026-09-23-agent-factory-design.md); plan R11 and AGW-8 to the
[agentgateway plan](../plans/2026-10-15-agent-router-agentgateway-plan.md); gate AG12 to the agent
gateway's gate suite.
