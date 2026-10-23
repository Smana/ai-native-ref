---
title: Harness reference
weight: 16
description: "Every setting of an agent run, from the factory's tiers to the OpenHands loop: its value on gcp-0, what it does, its bounds, and whether it is proven live."
lastVerified: 2026-10-18
---

Every knob of a run, layer by layer. How to use them is on
[Harness tuning]({{< relref "/docs/platform/ai-platform/agents/harness.md" >}}).

{{< cards >}}
  {{< card link="#tiers" title="Tiers" icon="adjustments" subtitle="USD cap, deadline and model per tier." >}}
  {{< card link="#templates" title="Templates and triage" icon="user-group" subtitle="Which roles run, and how a task gets its template." >}}
  {{< card link="#caps" title="Caps, resume, suspend" icon="shield-check" subtitle="Concurrency, daily caps, resumes and suspension." >}}
  {{< card link="#run-api" title="Run API" icon="terminal" subtitle="Flags of a run started by hand." >}}
  {{< card link="#claim" title="AgentRun claim" icon="document-text" subtitle="The fields a run is created with." >}}
  {{< card link="#harness" title="Harness" icon="cog" subtitle="The loop's settings, baked into the image." >}}
{{< /cards >}}

**On `gcp-0`, 2026-10-18:** harness `v0.15.2`, composed by crossplane-configuration `v0.9.15`.
| Status | Meaning |
|---|---|
| {{< badge content="live" color="green" >}} | Seen working on a real run |
| {{< badge content="deployed" color="blue" >}} | Configured, not yet exercised |
| {{< badge content="off" color="gray" >}} | Shipped, switched off |
| {{< badge content="design" color="yellow" >}} | Specified, not built |

## Factory: tiers {#tiers}

`config.tiers` in `tooling/base/agent-factory/helm-values-configmap.yaml`. Triage fixes one tier per
task; every run of the task inherits it. {{< badge content="deployed" color="blue" >}}, the USD cap {{< badge content="live" color="green" >}}

| Tier | `runUSD` / `taskUSD` | `runMinutes` | `runTokens` / `taskTokens` |
|---|---|---|---|
| light | 0.51 / 1.02 | 20 | 300 k / 600 k |
| standard | 2.55 / 5.10 | 45 | 1.5 M / 3 M |
| frontier | 6.80 / 13.60 | 90 | 4 M / 8 M |

| Field | What it does | Bounds |
|---|---|---|
| `model` | The logical model the run asks for. Every tier asks for `agent-default` today, so the tier changes caps, not the model | A logical name |
| `runUSD` | The meter revokes the run at this cost (`BudgetExhausted`, limit `run-usd`). Cache reads are priced at their own rate | Positive; needs a `meter.prices` row |
| `runTokens` | The claim's `budget.maxTokens`. Caps the run only when the meter cannot price it | 1 … 5 M |
| `taskUSD`, `taskTokens` | The whole task, every run and resume. A new run starts only if a whole run still fits | ≥ the run cap |
| `runMinutes` | The pod's deadline. A kill at the deadline is `PodFailed` and never resumed | 1 … 480 |

A priced run is held to USD, not tokens: `kk2egjta` passed 12.5 M tokens against a 4 M `maxTokens`
at $4.46 of $6.80, since 95% were cache reads. The gateway's per-run budget B1 is the backstop
([gateways]({{< relref "/docs/platform/ai-platform/gateways.md#budgets" >}})).

## Factory: templates and triage {#templates}

`config.templates`: the roles that run, in order, on one branch. {{< badge content="deployed" color="blue" >}}

| Template | Roles | Review rounds |
|---|---|---|
| `solo` | implementer | — |
| `pair` | implementer, reviewer | 2 |
| `trio` | implementer, tester, reviewer | 2 |
| `investigate` | triager: proposes an issue text, never writes | — |

- `maxReviewRounds`: every revision or restarted review uses one. Out of rounds, the task escalates.
- `reviewerModel`: the reviewer's model whatever the tier says. Unset here:
  [ADR-0058]({{< relref "/docs/decisions/0058-reviewer-on-another-model.md" >}}) keeps the public
  reviewer on the implementer's model.

Triage picks the template from the class and the tier:

| Task | Template |
|---|---|
| A RunLore finding | `investigate`, forced `internal` |
| `docs-links` | `solo`; `pair` on `frontier` |
| Any other class | `pair`; `trio` on `frontier` |

The tier would come from the complexity classifier, which is {{< badge content="design" color="yellow" >}}: every task falls back to
`standard`, except one in ten (`triage.controlPercent: 10`), the control group, on `frontier`.
`defaults.template` and `defaults.tier` choose nothing at run time, but the factory still validates
them at startup, as it requires `triage.classifierURL`: they leave the config only with an
agent-platform release that drops them.

The reviewer runs on **the other tier**: `frontier` for a `standard` or `light` implementer,
`standard` for a `frontier` one. It keeps the implementer's `maxTokens`. The tester keeps the
implementer's tier.

## Factory: caps, resume and suspend {#caps}

| Key | Value here | What it does |
|---|---|---|
| `caps.activeTasks` | 3 | Tasks worked at once |
| `caps.concurrentRuns` | 4 | Sandboxes at once |
| `caps.tasksPerDay` | 20 | Past it, a labelled issue is refused with a comment |
| `caps.maxTextBytes` | 14,336 | The longest task text accepted |
| `caps.maxPendingMinutes` | 30 (5 … 480) | A run still `Pending` escalates as `run_unschedulable` |
| `resume.maxPerTask` | 2 (1 … 5) | Runs lost to infrastructure are resumed; never a `PodFailed` one. {{< badge content="live" color="green" >}} aws-0 |
| `sandbox.suspend.enabled` | `true` on gcp-0 | An attended run waiting on an approval gives up its pod after 5 min. {{< badge content="live" color="green" >}} 2026-10-18 |
| `budgets.*` | `factoryDailyUSD` $42.50, `humanDailyUSD` $8.50 | Daily caps in USD at `meter.prices` (agent-platform v0.17.1). The fleet's and each person's count in shadow while `enforcePrincipal` is `false` |

## Run API: runs started by hand {#run-api}

`task agent:run -- --role … --class … --task …` asks the factory for one run.

| Flag | Default | Note |
|---|---|---|
| `--max-tokens` | 2,000,000 (≤ 5 M) | A hand-started run has no tier, so it is capped in tokens |
| `--model` | `agent-default` | One of the four logical names |
| `--profiles` | none | Egress profiles: `pypi`, `npm`, `golang`, `crates` |
| `--minutes`, `--size` | refused | Fixed at 120 min and `small` |

## AgentRun claim {#claim}

The XRD `agentruns.cloud.ogenki.io`
([definition](https://github.com/Smana/crossplane-configuration/blob/main/apis/agentrun/definition.yaml)).
Only `budget.maxTokens` can change on a live run. The factory always writes `size: small`.

| Field | Default | Effect |
|---|---|---|
| `role` | required | `implementer` writes and pushes; `reviewer`, `tester`, `triager` read only |
| `dataClass` | required | `public`: Z.ai, GitHub egress. `internal`: Claude, read-only clone, no egress, cluster read tools, prompt caching |
| `model` | `agent-default` | The harness's `MODEL` |
| `budget.maxTokens` | 2 M (1 … 5 M) | The token cap when the run is not priced |
| `budget.maxMinutes` | 120 (1 … 480) | The pod's deadline and the TTL of its tokens |
| `size` | `small` | `small` 1→2 CPU, 2→4 GiB; `medium` ×2; `large` ×4 |
| `egress.profiles` | `[]` | Package registries on top of GitHub; refused on `internal` |
| `roomRef` | — | Adds the room-bridge sidecar and the room rules |
| `suspendable` | — | `/workspace` on a PVC, so the run can be suspended |

## Composition {#composition}

[`apis/agentrun/kcl/main.k`](https://github.com/Smana/crossplane-configuration/blob/main/apis/agentrun/kcl/main.k)
turns the claim into the pod. Nothing here is set per run.

| Setting | Value |
|---|---|
| Harness image | `ghcr.io/smana/agent-harness:v0.15.2@sha256:c49c…`: a harness change reaches runs only through this digest |
| Environment | `MODEL`, `DATA_CLASS`, `ROLE`, `LLM_BASE_URL`, `MCP_URL`, `TASK_FILE`, `RULES_FILE`, tracing. `LLM_REASONING_EFFORT` is not set |
| `rules.md` | One branch, one PR, never `.github/workflows/`, "a 429 means the budget is spent: stop". Each rule is also enforced outside the sandbox |
| `task.md` | The task text: the biggest driver of a run's length |
| Egress | `github.com` and its API, codeload and content hosts, plus each profile's registries |
| Grace period | 30 s, 45 s with a room: checkpoint, final read, stop, revoke |
| Read-only MCP tools | Flux, VictoriaMetrics and VictoriaLogs reads and the `room_*` tools; any other needs an approval in a room |

## Harness {#harness}

Set in [`agent_run.py`](https://github.com/Smana/agent-platform/blob/main/images/agent-harness/agent_run.py)
and [`sitecustomize.py`](https://github.com/Smana/agent-platform/blob/main/images/agent-harness/site/sitecustomize.py),
or left at the [SDK v1.49.6 defaults](https://github.com/OpenHands/software-agent-sdk/tree/v1.49.6/openhands-sdk/openhands/sdk).
None is a claim field.

| Knob | Value | Effect | Status |
|---|---|---|---|
| `reasoning_effort` | `high` | Unsent, GLM-5.3 thinks at maximum: 150 s per reply instead of 11 s | {{< badge content="live" color="green" >}} |
| Model timeout | 300 s per call | A timeout is not retried: it ends the run | {{< badge content="live" color="green" >}} |
| Retries | 3 attempts, 10 s then 20 s apart | On a 503 or a reset. **Never** a 429 or a timeout | {{< badge content="live" color="green" >}} |
| `max_iterations` | 500 | Past it the run ends `error`; the USD cap and deadline usually end it first | {{< badge content="deployed" color="blue" >}} |
| Stuck detection | last 20 events | Ends the run `stuck` on 4 identical cycles, 3 repeated errors or 3 messages with no action | {{< badge content="live" color="green" >}} |
| Condenser | 80 events, keep first 4 | Summarises history with the same model, on the run's budget | {{< badge content="deployed" color="blue" >}} |
| Event size | 30,000 chars | A huge output is truncated, not refused | {{< badge content="deployed" color="blue" >}} |
| Tools | terminal, file editor, task tracker, MCP | No browser; MCP tools filtered per role by the gateway | {{< badge content="live" color="green" >}} |
| Prompt caching | on for `internal` | 85% of input from cache: $0.48 instead of $2.13 | {{< badge content="live" color="green" >}} |
| `autotitle` | off | Saves a model call per title | {{< badge content="live" color="green" >}} |
| Step log | every 15 s | Lines arrive in batches | {{< badge content="live" color="green" >}} |
| Progress notes | 5 milestones, ≤ 8 a run | Fixed texts in the room, nothing the model wrote | {{< badge content="live" color="green" >}} |
| Checkpoint on SIGTERM | implementer only | A reclaimed run's work survives on its branch | {{< badge content="live" color="green" >}} aws-0 |
| Tracing | span per model and MCP call | No prompt or output content | {{< badge content="live" color="green" >}} |

```promql
# One run's tokens by model and type, as the meter prices them
sum by (gen_ai_request_model, gen_ai_token_type) (
  max_over_time(gen_ai_client_token_usage_sum{ar_agent="system:serviceaccount:agents:xplane-run-<id>"}[1d]))
```
