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

## L3 · Roles on both harnesses

| Run | Issue | Harness | State |
|---|---|---|---|
| Implementer, then reviewer (pinned together by `model:gemini-standard`) | #622 (task `4nsn6vsa`) | OpenHands | implementing on `gemini-standard`, `modelSource: label` |
| Implementer, then reviewer | #623 (task `e4wlawv6`) | OpenCode | **stop: Escalated `agent_error` at step 0** |

**#623, OpenCode: Vertex refuses OpenCode's tool schemas.** The run (`pmd4lwya`, 09:56 to 09:58
UTC) installed its toolchain, then the first model call failed (harness log, `kubectl -n agents logs
run-pmd4lwya -c harness`):

```text
agent-run error: provider.invalid-request Invalid JSON payload received. Unknown name "exclusiveMinimum"
at 'tools[0].function_declarations[21].parameters.properties[4].value': Cannot find field. ...
at 'tools[0].function_declarations[22].parameters.properties[3].value' ...
```

agentgateway's native `vertexai` translation passes each tool's JSON Schema to `generateContent` as is,
and Gemini's function declarations refuse the JSON Schema keyword `exclusiveMinimum`, which two of the
run's tools use. It is a 400 on the request, not a thought signature: 0 steps, no cost. The egress
install window did not cause it (`agent-checks: toolchain ready`). OpenCode runs cannot use Gemini
until the schema is accepted: the gateway (or the harness) has to drop or translate the keyword.

The three tools, from OpenCode's own request, dumped offline from the `maku-opencode:v0.57.0`
image: `generate_video.duration`, `glob.limit` and `grep.limit`, each with `exclusiveMinimum: 0`.
The cause is in agentgateway (`normalize_gemini_schema` keeps both exclusive bounds, which Vertex's
`Schema` lacks), already reported upstream as agentgateway/agentgateway#4242. Filed in Maku as
Smana/maku#798, with the interim fix: refuse OpenCode on a `vertex` alias, and say why.

#### Draft upstream text (for the owner to post; a comment on agentgateway/agentgateway#4242)

> Reproduced on v1.6.0 with the native `vertexai` provider (region `eu`), `gemini-4-neon`, from
> OpenCode 2.4: the first Chat Completions request fails with
> `Invalid JSON payload received. Unknown name "exclusiveMinimum" at
> 'tools[0].function_declarations[21].parameters.properties[4].value'`. OpenCode's built-in
> `generate_video.duration`, `glob.limit` and `grep.limit` each declare `exclusiveMinimum: 0`.
>
> The cause is `ALLOWED_SCHEMA_FIELDS` in `crates/llm/src/conversion/vertex_gemini.rs`, still the
> same on `main`. It lists `exclusiveMinimum` and `exclusiveMaximum`, and
> `normalize_gemini_schema(params, false)` keeps them for `functionDeclarations[].parameters`.
> Vertex's `Schema` (google/cloud/aiplatform/v1/openapi.proto) does not define them.
>
> Suggested fix: in the function-declaration path, translate the bounds rather than drop them.
> `exclusiveMinimum: n` becomes `minimum: n` (plus 1 for `type: integer`), and likewise for
> `exclusiveMaximum`, unless a `minimum`/`maximum` is already set. A test with OpenCode's `glob`
> schema should show the request accepted. Happy to send a PR.

Two legs of the runbook cannot run on v0.57.0 and are recorded as gaps, not stops:

- **A standalone reviewer** (`factory/review` on a pull request): triage reads no `model:` or
  `harness:` pin on a review outcome (Maku `Classify.pin` returns none for review), so the run would
  not be on Gemini. The reviewer leg is the reviewer run of #622 and #623, which the pin moves with
  the implementer and which must post through `room_verdict`.
- **The tester**: no Repository on gcp-0 sets `testFirst` (ai-native-ref's says why, TO4), so no
  workflow runs the tester.

## L4 · The rule, frozen before the first pair is filed

Frozen on 2026-11-27, before any L4 issue exists. B is `model:gemini-standard` on the implementer
and the reviewer; A is the factory's default (`agent-default`). Everything else is identical: the same
body, the same `workflow:standard` label, the OpenHands harness, the same efforts, caps and checks.

**B earns a 30+30 `evaluation.treatmentModel` trial only if all three hold:**

1. B's merged count is at least A's minus one.
2. B's USD per merged task (total USD / merged) is at most 1.5 × A's.
3. B has zero signature 400s: no run ends on one, and the gateway logs no 400 from `gcp.vertex_ai`
   in the window.

Read with `model-comparison-report.py --arm-a '[gemini A]' --arm-b '[gemini B]'`. A pair whose arms
the classifier rated at different tiers is dropped (`--drop-mismatched`) and named. A arm merging
nothing makes the rule indecisive. The owner may override the rule; an override is recorded here.

## L4 · Pairs

Filed 2026-11-27 09:58:36 to 09:58:50 UTC, each pair back to back: `workflow:standard`,
`harness:openhands` and `factory/ready` on both copies, `model:gemini-standard` on one. The titles
carry the suffixes `[L4 v]` and `[L4 w]`. Which suffix is which arm is in the key at the end of this
file. Five pairs today, five after 00:00 UTC (caps: tasksPerDay 20, activeTasks 3, awaitingHumanWIP 5;
none raised).

| Pair | Task | `[L4 v]` | `[L4 w]` |
|---|---|---|---|
| 1 | kb-measures `--json` | #625 | #626 |
| 2 | runbook 30 links back to the README | #627 | #628 |
| 3 | gen-prices refuses `cacheRead` above `input` | #629 | #630 |
| 4 | cost-crosscheck `--json` names its window | #631 | #632 |
| 5 | runbook 32 says when to run a comparison | #633 | #634 |

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

---

## The arm key (for after the blind review)

`[L4 v]` is arm A (`agent-default`); `[L4 w]` is arm B (`model:gemini-standard`). For each pair, the
blind packet's X and Y are listed here once its pull requests exist.
