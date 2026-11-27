# Runbook 30 results — Gemini on Vertex AI on gcp-0 — 2026-11-27

The ledger of [runbook 30](30-gemini-live-comparison.md): every number below comes from a query
named beside it. The owner's go on spend for L2 to L5 was given on 2026-11-27 (about 07:40 UTC by
the lead's record).

| Item | Value |
|---|---|
| Cluster | gcp-0 (`gke_ogenki-435905_europe-west4-a_gcp-0`) |
| Platform | ANR v4.1.9, Maku v0.55.0 for L1 and the L2 baseline |
| L1 | Done by the lead before this ledger: T1 passed, the meter matched the list price exactly |

## L2 · The planner

### Baseline on Z.ai glm-5.3 (before #610)

Ten fixed prompts on `Smana/ai-native-ref`, each sent through `maku start` and answered `N` at the
filing prompt, so the broker planned and nothing was filed. The prompts are in
[the appendix](#appendix-the-l2-prompts). Window: 2026-11-27 07:16:33 to 07:17:36 UTC (the
workstation's clock).

Queries:

- broker: `kubectl -n agent-system logs <room-broker pod> -c room-broker --since=20m`, the `intake plan` lines' `duration`
- gateway: `kubectl -n agent-gateway logs <each model-gateway pod> --since=20m`, the lines whose `route` is the clients planner's, `duration`, `gen_ai.usage.*`, `cost.total`

| # | Broker `intake plan` (s) | Outcome | Gateway calls (ms) | Output tokens | Gateway cost (USD) | CLI wall (ms) |
|---|---|---|---|---|---|---|
| 1 | 3.69 | planned | 3514 | 232 | 0.00148 | 3888 |
| 2 | 3.97 | asked | 3963 | 232 | 0.00178 | 4179 |
| 3 | 11.96 | planned | 11753 | 305 | 0.00209 | 12171 |
| 4 | 11.19 | planned | 5721 + 5461 | 388 + 277 | 0.00420 | 11409 |
| 5 | 3.51 | planned | 3314 | 216 | 0.00169 | 3668 |
| 6 | 6.45 | asked | 6443 | 441 | 0.00268 | 6656 |
| 7 | 3.23 | planned | 3228 | 226 | 0.00174 | 3492 |
| 8 | 3.71 | planned | 3710 | 236 | 0.00178 | 3987 |
| 9 | 6.39 | planned | 6390 | 383 | 0.00243 | 6555 |
| 10 | 6.47 | asked | 6470 | 423 | 0.00261 | 6647 |

- Every call answered 200 on `glm-5.3`. No plan timed out against the 20 s deadline.
- p95 of the broker's durations (nearest rank, n=10): 11.96 s. The median is 5.18 s.
- Plan 4 made two planner calls, in one `intake plan` of 11.19 s.
- Total cost: USD 0.0225.

The plans' text is kept for the owner's blind ranking, with each plan's arm hidden.

### Neon on Vertex `eu` (#610 live, Maku v0.57.0, ANR v4.1.11) — **stop: planner timeouts**

The planner backend `vertex-planner` maps `tier-frontier` to `gemini-4-neon` (read from the
AgentgatewayBackend). The same ten prompts, the same way. Window: 2026-11-27 09:49:10 to 09:52:06
UTC.

| # | Broker `intake plan` (s) | Outcome | Gateway (ms) | Status | Output tokens (of which reasoning) | Gateway cost (USD) |
|---|---|---|---|---|---|---|
| 1 | 18.96 | asked | 14219 | 200 | 1412 (889) | 0.02753 |
| 2 | 12.16 | asked | 12144 | 200 | 1123 (810) | 0.02277 |
| 3 | 20.19 | refused `planner_timeout` | 20001 | — | — | — |
| 4 | 10.51 | planned | 10450 | 200 | 1041 (726) | 0.02139 |
| 5 | 20.24 | refused `planner_timeout` | 20001 | — | — | — |
| 6 | 12.63 | planned | 12573 | 200 | 1014 (709) | 0.02093 |
| 7 | 20.00 | refused `planner_timeout` | 20001 | — | — | — |
| 8 | 20.00 | refused `planner_timeout` | 19948 | — | — | — |
| 9 | 20.00 | refused `planner_timeout` | 19955 | — | — | — |
| 10 | 20.00 | refused `planner_timeout` | 19958 | — | — | — |

- **Six of ten plans timed out** at the broker's 20 s deadline. The gateway shows each of these
  calls cut at about 20 s with no status and no usage.
- The four plans that answered took 10.5 to 19.0 s. The median is 20.0 s and p95 is 20.24 s,
  against the runbook's pass line of p95 under 15 s with no timeout.
- `reasoning_effort: low` reached Vertex as `thinkingLevel: low`, yet each answer still spent 700
  to 900 thinking tokens, about 70 % of its output.
- Cost of the four answered calls: USD 0.0926, about USD 0.023 a plan against Z.ai's USD 0.002,
  roughly 11 times as much. The timed-out calls report no usage.

Verdict: **L2 fails on its stop condition** (a timeout; p95 ≥ 15 s). The runbook says to revert
the planner patch (#610) before anything else. Neon stays off the planner. The four Neon plans
that answered are kept for the owner's blind ranking beside the ten Z.ai plans.

## Appendix: the L2 prompts

1. Add a --json flag to scripts/ops/kb-measures.py that prints the measures as one JSON document instead of the table.
2. The runbooks README lists runbook 30; add a one-line link back to the README at the top of runbook 30.
3. scripts/ci/check-price-drift.py: print the catalog key next to each finding in the issue body.
4. test-model-gateway-values.py: name the failing listener in the M2 message when an alias is missing.
5. Make scripts/ops/cost-crosscheck.py accept --day today as the current UTC day.
6. The status page's Gemini row should link runbook 30 by its GitHub URL.
7. check-sources.sh: exit 2, not 1, when the repository root cannot be found.
8. Add a short "When to use" paragraph to runbook 27-workflow-comparison.md.
9. model-comparison-report.py: add --title-filter REGEX to keep only pairs whose title matches.
10. gen-prices.py: refuse a meter.prices row whose cacheRead exceeds its input rate.
