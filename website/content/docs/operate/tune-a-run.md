---
title: Harness tuning
aliases:
  - /docs/platform/ai-platform/agents/tune/harness/
linkTitle: Tune a run
weight: 10
diataxis: how-to
description: "How to tune an agent run: which lever moves cost, time and quality, how to measure a change, what goes wrong and how to fix it."
lastVerified: 2026-10-31
---

The harness runs the agent loop inside the sandbox: OpenHands
[`agent-server`](https://github.com/OpenHands/software-agent-sdk), driven by a small entrypoint,
`agent-run`. This page is the guide; every setting with its value and bounds is on the
[Harness reference]({{< relref "/docs/reference/harness.md" >}}).

{{< callout type="info" >}}
**The levers that matter are outside the harness.** Money, time and model come from the **tier**,
the team from the **template**, the tools from the **data class**, and the run's length from the
**task text**. The cheapest optimization is a bounded task: an open "find out why" once spent its
whole $2.55 on 319 `grep` steps and pushed nothing.
{{< /callout >}}

## The five levers {#levers}

<span id="start"></span><span id="loop"></span><span id="layers"></span>

| Lever | Sets | Changed in | Reference |
|---|---|---|---|
| 🎚️ **Tier** | USD cap, deadline, model | Factory config | [Tiers]({{< relref "/docs/reference/harness.md#tiers" >}}) |
| 👥 **Template** | Which roles run: solo, pair, trio | Factory config | [Templates]({{< relref "/docs/reference/harness.md#templates" >}}) |
| 🔒 **Data class** | Provider, egress, tools, prompt caching | The task's source | [AgentRun]({{< relref "/docs/reference/harness.md#claim" >}}) |
| 📝 **Task text** | How far the agent wanders | The issue | [Writing a good task]({{< relref "/docs/use/guide/writing-a-good-task.md" >}}) |
| ⚙️ **Harness** | Iterations, condenser, timeouts, reasoning effort | A harness release, not per run | [Agent loop]({{< relref "/docs/reference/harness.md#loop" >}}) |

How `agent-run` drives `agent-server`, the tester's contract ([runbook 21](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/21-test-first-tester.md), [the roles]({{< relref "/docs/how-it-works/roles.md#tester" >}})) and where each setting layer is pinned are in [the repository's design records](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md#harness-tuning-measurements).

## Trade-offs {#trade-offs}

| Turn up | It costs | Watch for |
|---|---|---|
| ⬆️ Tier, `standard` → `frontier` ([tiers]({{< relref "/docs/reference/harness.md#tiers" >}})) | Caps ×2.7, deadline 45 → 90 min | A wandering run spends all of it |
| ⬆️ `runMinutes` alone ([tiers]({{< relref "/docs/reference/harness.md#tiers" >}})) | Wall time | A deadline kill is never resumed: add money too |
| ⬆️ `runUSD` alone ([tiers]({{< relref "/docs/reference/harness.md#tiers" >}})) | Money | Keep `taskUSD ≥ 2 × runUSD` so a resume fits |
| ⬆️ `maxReviewRounds` ([caps]({{< relref "/docs/reference/harness.md#caps" >}})) | One implementer and one reviewer run per round | Out of rounds, the task escalates |
| ⬆️ `trio` over `pair` ([templates]({{< relref "/docs/reference/harness.md#templates" >}})) | One more run | The tester keeps the implementer's tier |
| ⬆️ `reasoning_effort` ([loop]({{< relref "/docs/reference/harness.md#loop" >}})) | Reasoning tokens, seconds per step | Above `high`, GLM-5.3 hits the 300 s timeout |
| ✅ Prompt caching ([loop]({{< relref "/docs/reference/harness.md#loop" >}})) | Nothing: cache reads cost 5% | Needs the marker carried end to end |

## Measuring a change {#measuring}

<span id="examples"></span>

Change one lever, run the same kind of task, compare. A run's id is the 8 characters after
`run-`. Measured in October 2026; sample runs and their step counts and costs are in [the repository's design records](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md#what-real-runs-look-like).

{{< tabs >}}
{{< tab name="Dashboard" icon="chart-bar" >}}
On the `agent-run` dashboard:

| Question | Panel |
|---|---|
| What did it cost? | *Cost (USD)* |
| How much input was cached? | *Tokens in / out* |
| How many steps, which tools? | *Steps*, *Distinct steps* |
| How long, and where did the time go? | *Duration*, *Run traces* |
| How slow was the model? | *Model latency p50 / p95* |
| Why did it end? | *Run*, *Errors* |
{{< /tab >}}
{{< tab name="LogsQL" icon="document-text" >}}
```logsql
# The step log, then the tool mix
kubernetes.pod_name:"run-<id>" AND kubernetes.container_name:"harness" AND _msg:~"^agent-run"
kubernetes.pod_name:"run-<id>" AND kubernetes.container_name:"harness" AND _msg:~"^agent-run step "
  | extract "agent-run step <n>: <tool> |" | stats by (tool) count() steps
```
{{< /tab >}}
{{< tab name="PromQL" icon="presentation-chart-line" >}}
```promql
# Cost, as the meter computes it
maku_factory_run_spend_usd{run="<id>"}
# Was the tier right? fit = under | fit | over
sum by (tier, fit) (maku_factory_tier_fit_total)
# Why runs end
sum by (reason) (agentrun_outcome_info)
```
{{< /tab >}}
{{< /tabs >}}

## Failure modes {#failure-modes}

### Budget and time

| You see | Do this |
|---|---|
| Out of budget, no commit, hundreds of `grep`/`cat` steps | The task has no stopping rule: [scope it](#recipes) |
| Out of budget with limit `run-tokens` | A hand-started run or an unpriced model: raise `--max-tokens`, or add a `meter.prices` row ([caps]({{< relref "/docs/reference/harness.md#caps" >}})) |
| `PodFailed` near the deadline | Raise `runMinutes` together with `runUSD` ([tiers]({{< relref "/docs/reference/harness.md#tiers" >}})) |
| A `429`, then the agent stops | A gateway budget, never retried by design: check `maku_factory_run_revocations_total` |

### Loops and errors

| You see | Do this |
|---|---|
| `maximum iterations limit (500)` | The run looped: [debug it](#debug) ([loop]({{< relref "/docs/reference/harness.md#loop" >}})) |
| `execution_status=stuck` | The same action or error repeated: fix the tool, host or test it trips on |
| `LLMServiceUnavailableError` after `model retry 2/2` | The provider failed 3 times: `/factory retry` |
| Steps take minutes, calls fail at 300 s | `reasoning_effort` is not reaching the model: check the request body ([loop]({{< relref "/docs/reference/harness.md#loop" >}})) |

Tester-contract (`contract_not_red`, `contract_outside_tests`, `not_testable`) and environment/room failure modes ([bridge]({{< relref "/docs/reference/harness.md#bridge" >}}), [pod]({{< relref "/docs/reference/harness.md#pod" >}})) are in [the repository's design records](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md#failure-modes-tester-and-rooms).

## Recipes {#recipes}

{{< tabs >}}
{{< tab name="Stop a run that wanders" icon="fire" >}}
A wandering run is hundreds of reads and no commit. The stuck detector misses it, because every
command differs.

1. Give the task a **scope**: which files, which component.
2. Give it an **exit**: "if X is not found, say so and stop".
3. Only then try a bigger tier ([tiers]({{< relref "/docs/reference/harness.md#tiers" >}})).
{{< /tab >}}
{{< tab name="Give long tasks more room" icon="clock" >}}
1. Check it is large, not wandering: a large run posts `committed.` and `pushed its branch.` notes.
2. Raise the tier's `runUSD` **and** `runMinutes` together; keep `taskUSD ≥ 2 × runUSD` ([tiers]({{< relref "/docs/reference/harness.md#tiers" >}})).
3. A task that installs packages needs `--profiles` on a hand-started run: the factory adds none ([AgentRun]({{< relref "/docs/reference/harness.md#claim" >}})).
{{< /tab >}}
{{< tab name="Make reviews cheaper" icon="currency-dollar" >}}
A review of a small PR takes under 10 steps: the cost is in the rounds.

1. Keep `maxReviewRounds` at 2, or 1 for mechanical fixes ([caps]({{< relref "/docs/reference/harness.md#caps" >}})).
2. Leave `docs-links` on `solo`: the matrix skips the reviewer below `frontier` ([templates]({{< relref "/docs/reference/harness.md#templates" >}})).
3. For a smaller reviewer, set `templates.pair.reviewerModel: tier-standard`.
   [ADR-0058]({{< relref "/docs/decisions/0058-reviewer-on-another-model.md" >}}) weighs it: cheaper,
   but a smaller model judging a larger one's work.
{{< /tab >}}
{{< /tabs >}}

## Debug a run that loops {#debug}

```mermaid
flowchart TB
  A["Run long<br/>or failed"]:::start --> B{"execution<br/>status?"}
  B -- stuck --> S["Fix the repeated<br/>tool or host"]:::fix
  B -- error --> E{"Error line?"}
  E -- "max iterations" --> L
  E -- unavailable --> P["Retry the task"]:::fix
  E -- timeout --> R["Check<br/>reasoning_effort"]:::fix
  B -- "revoked or<br/>deadline" --> L{"Step mix?"}
  L -- "reads, no commit" --> W["Scope the task"]:::fix
  L -- "commits, pushes" --> G["More runUSD<br/>+ runMinutes"]:::fix
  L -- "refused in a room" --> Q["Approve, or fork<br/>with egress"]:::fix
  classDef start fill:#dc2626,stroke:#b91c1c,color:#fff
  classDef fix fill:#059669,stroke:#047857,color:#fff
```

1. `kubectl get agentruns.maku.ogenki.io -n agents run-<id>`: phase and reason.
2. The step log's last 30 lines: repeating, or changing?
3. The tool mix (the LogsQL tab above): 95% `terminal` and no commit is searching, not working.
4. The room transcript for the model's reasoning; the trace for timings.
5. If it burns money, stop it: `factory/stop` on the issue.

## Loop policy and search {#loop-policy}

<span id="search"></span><span id="limits"></span>

The loop policy (`loops.<class>` in `tooling/base/agent-factory/resources/factory.yaml`, [reference]({{< relref "/docs/reference/harness.md#caps" >}})) stops wandering runs (`stallSteps`), checks a finished run against the task's acceptance checks (`judge`) and continues the conversation (`continuations`), while `loops.<class>.search: true` gives the implementer an experimental read-only search helper ([agent loop]({{< relref "/docs/reference/harness.md#loop" >}})). The loop-policy end states, search sequence diagram and untunable-settings table are in [the repository's design records](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md#loop-policy-details).

Related: [Harness reference]({{< relref "/docs/reference/harness.md" >}}) ·
[Factory]({{< relref "/docs/how-it-works/factory.md" >}}) ·
[Rooms]({{< relref "/docs/how-it-works/rooms.md" >}}) ·
[Observability]({{< relref "/docs/operate/observability.md#agents" >}}) ·
[User guide]({{< relref "/docs/use/guide/_index.md" >}})
