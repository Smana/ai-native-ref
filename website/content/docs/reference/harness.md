---
title: Harness reference
weight: 10
description: "Every setting of an agent run, from the factory's tiers to the OpenHands loop: its example value, what it does, its bounds, and whether it is on by default."
lastVerified: 2026-10-31
aliases:
  - /docs/platform/ai-platform/agents/harness-reference/
  - /docs/platform/ai-platform/agents/tune/harness-reference/
---

Every knob of a run, layer by layer. How to use them is on
[Harness tuning]({{< relref "/docs/operate/tune-a-run.md" >}}).

{{< cards >}}
  {{< card link="#tiers" title="Tiers" icon="adjustments" subtitle="USD cap, deadline and model per tier." >}}
  {{< card link="#templates" title="Templates and triage" icon="user-group" subtitle="Which roles run, and how a task gets its template." >}}
  {{< card link="#caps" title="Caps, resume, suspend" icon="shield-check" subtitle="Concurrency, daily caps, resumes and suspension." >}}
  {{< card link="#run-api" title="Run API" icon="terminal" subtitle="Flags of a run started by hand." >}}
  {{< card link="#claim" title="AgentRun claim" icon="document-text" subtitle="The fields a run is created with." >}}
  {{< card link="#harness" title="Harness" icon="cog" subtitle="The loop's settings, baked into the image." >}}
{{< /cards >}}

**Pins on `main`:** Maku `v0.32.3`, composed by crossplane-configuration `v0.9.31`. Values below are
examples: the reference host's configuration.

| Status | Meaning |
|---|---|
| {{< badge content="default" color="green" >}} | On by default |
| {{< badge content="experimental" color="yellow" >}} | Built, on for a few classes only; its benefit is still measured |
| {{< badge content="off" color="gray" >}} | Shipped, switched off |
| {{< badge content="planned" color="blue" >}} | Specified, not built |

## Factory: tiers {#tiers}

`config.tiers` in `tooling/base/agent-factory/helm-values-configmap.yaml`. Triage fixes one tier per
task; every run of the task inherits it. {{< badge content="default" color="green" >}}

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
([gateways]({{< relref "/docs/how-it-works/gateways.md#budgets" >}})).

## Factory: templates and triage {#templates}

`config.templates`: the roles that run, in order, on one branch. {{< badge content="default" color="green" >}}

| Template | Roles | Review rounds |
|---|---|---|
| `solo` | implementer | — |
| `pair` | implementer, reviewer | 2 |
| `trio` | implementer, reviewer: `pair`'s shape until the bench; the tester runs first through `testFirst`, not the template | 2 |
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

The tier would come from the complexity classifier, which is {{< badge content="planned" color="blue" >}}: every task falls back to
`standard`, except one in ten (`triage.controlPercent: 10`), the control group, on `frontier`.
`defaults.template` and `defaults.tier` choose nothing at run time, but the factory still validates
them at startup, as it requires `triage.classifierURL`: they leave the config only with an
Maku release that drops them.

The reviewer runs on **the other tier**: `frontier` for a `standard` or `light` implementer,
`standard` for a `frontier` one. The reviewer's tier's USD cap applies; its tokens and minutes stay the
implementer's tier's. The tester keeps the implementer's tier.

## Factory: caps, resume and suspend {#caps}

| Key | Value here | What it does |
|---|---|---|
| `caps.activeTasks` | 3 | Tasks worked at once |
| `caps.concurrentRuns` | 4 | Sandboxes at once |
| `caps.tasksPerDay` | 20 | Past it, a labelled issue is refused with a comment |
| `caps.maxTextBytes` | 14,336 | The longest task text accepted |
| `caps.maxPendingMinutes` | 30 (5 … 480) | A run still `Pending` escalates as `run_unschedulable` |
| `resume.maxPerTask` | 2 (1 … 5) | Runs lost to infrastructure are resumed; never a `PodFailed` one. {{< badge content="default" color="green" >}} |
| `sandbox.suspend.enabled` | `true` (example) | An attended run waiting on an approval gives up its pod after 5 min. {{< badge content="default" color="green" >}} |
| `budgets.*` | `factoryDailyUSD` $42.50, `humanDailyUSD` $8.50 | Daily caps in USD at `meter.prices` (the USD gauges since Maku v0.16.0). The fleet's and each person's count in shadow while `enforcePrincipal` is `false` |
| `loops.<class>` | `default: {scope: off}`; `docs` (scoper, loop policy, search) and `scripts` (scoper, splitter) | The loop policy and the scope, off for every class without a row. `scope` is `off`, `steering` or `scoper` ([what a brief holds](#brief)). A row sets `stallSteps` (default 80, 1 … 500), `continuations` (2, 0 … 5) and `judge` (one of the four model aliases, default `tier-light`, or `none`); any one of them switches the class on. [Loop policy]({{< relref "/docs/operate/tune-a-run.md#loop-policy" >}}) |
| `scoper.nudgeAt`, `scoper.maxToolCalls` | 25 and 40 (Maku's defaults; this repository sets no `scoper:` key) | The scoper's exploration bound: a nudge to wrap up at 25 tool calls, a stop at 40 with the end `budget_calls`; any end without a handoff leaves the implementer to run unscoped |
| `loops.<class>.search` | `true` on `docs` only | The implementer's `search` tool; never switches the loop on. [Search]({{< relref "/docs/operate/tune-a-run.md#search" >}}) |

## Factory: what a brief holds {#brief}

`loops.<class>.scope` picks the mode per class; `loops.default` covers a class with no row and
`review`. `docs` and `scripts` are `scoper` here; every other class is `off`.

| Brief | `off` | `steering` | `scoper` |
|---|---|---|---|
| Scoper (a triager run) | — | — | preamble · steering · snapshot · how to scope, ask or assume, and hand off |
| First implementer | preamble · snapshot (today) | preamble · steering · snapshot | preamble · steering · scope · snapshot |
| Revision, CI fix, retry, resume (≤ 13 KiB) | today | steering before the room log | steering and scope before the room log |
| Judge's continuation | the issue's acceptance section | the same | the scope's acceptance checks |
| Reviewer | the room | the room; steering once the reviewer's brief carries it | the room (the scope is a handoff); steering and scope once it does |

The steering note and the scope are never clipped. The snapshot is inlined whole while the brief stays
within 16 KiB, else the brief tells the implementer to read it with `room_read`. The scope is an
agent's text drawn from an untrusted issue: sanitised and fenced as the snapshot is. The steering note
is fenced as trusted. Example (the reference host): on for `docs` and `scripts`.

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
| `role` | required | `implementer` writes and pushes; `reviewer` and `triager` read only; the tester writes tests the harness signs and pushes |
| `dataClass` | required | `public`: Z.ai, GitHub egress. `internal`: Claude, read-only clone, no egress, cluster read tools, prompt caching |
| `model` | `agent-default` | The harness's `MODEL` |
| `budget.maxTokens` | 2 M (1 … 5 M) | The token cap when the run is not priced |
| `budget.maxMinutes` | 120 (1 … 480) | The pod's deadline and the TTL of its tokens |
| `size` | `small` | `small` 1→2 CPU, 2→4 GiB; `medium` ×2; `large` ×4 |
| `egress.profiles` | `[]` | Package registries on top of GitHub; refused on `internal` |
| `roomRef` | — | Adds the maku-bridge sidecar (container `room-bridge`) and the room rules |
| `suspendable` | — | `/workspace` on a PVC, so the run can be suspended |
| `loop.checks` | — | Runs the repository's checks in the sandbox: `AGENT_CHECKS=1`, refused on `internal` |
| `loop.search` | — | The `search` tool for an implementer: `AGENT_SEARCH=1`. Alone, no loop policy |

## Composition {#composition}

[`apis/agentrun/kcl/main.k`](https://github.com/Smana/crossplane-configuration/blob/main/apis/agentrun/kcl/main.k)
turns the claim into the pod. Nothing here is set per run.

| Setting | Value |
|---|---|
| Harness image | `ghcr.io/smana/maku-harness:v0.32.3@sha256:d6ec677262d10342dee4e8ba53af087e7d6f227502c0cc7c2ecfe4d6636c040e` (the release's image, composed by crossplane-configuration v0.9.31, where the composition pin lives): a harness change reaches runs only through the composition's digest, so the harness roles reach runs with that bump |
| Environment | `MODEL`, `DATA_CLASS`, `ROLE`, `LLM_BASE_URL`, `MCP_URL`, `TASK_FILE`, `RULES_FILE`, tracing; `AGENT_CHECKS` and `AGENT_RUN_SECONDS` with `loop.checks`; `AGENT_SEARCH` with `loop.search`. `LLM_REASONING_EFFORT` is not set |
| `rules.md` | One branch, one PR, never `.github/workflows/`, "a 429 means the budget is spent: stop". Each rule is also enforced outside the sandbox |
| `task.md` | The task text: the biggest driver of a run's length |
| Egress | `github.com` and its API, codeload, content and release-asset hosts, plus each profile's registries (`golang` includes `dl.google.com`) |
| Grace period | 30 s, 45 s with a room: checkpoint, final read, stop, revoke |
| Read-only MCP tools | Flux, VictoriaMetrics and VictoriaLogs reads and the `room_*` tools; any other needs an approval in a room |

## Harness {#harness}

Set in [`agent_run.py`](https://github.com/Smana/maku/blob/main/images/maku-harness/agent_run.py)
and [`sitecustomize.py`](https://github.com/Smana/maku/blob/main/images/maku-harness/site/sitecustomize.py),
or left at the [SDK v1.49.6 defaults](https://github.com/OpenHands/software-agent-sdk/tree/v1.49.6/openhands-sdk/openhands/sdk).
None is a claim field.

| Knob | Value | Effect | Status |
|---|---|---|---|
| `reasoning_effort` | `high` | Unsent, GLM-5.3 thinks at maximum: 150 s per reply instead of 11 s | {{< badge content="default" color="green" >}} |
| Model timeout | 300 s per call | A call that timed out before its first token is retried once when the run has time left; a second timeout ends the run | {{< badge content="default" color="green" >}} |
| Retries | 3 attempts, 10 s then 20 s apart | On a 503 or a reset. **Never** a 429; a timeout has its own single retry (above) | {{< badge content="default" color="green" >}} |
| `max_iterations` | 500 | Past it the run ends `error`; the USD cap and deadline usually end it first | {{< badge content="default" color="green" >}} |
| Stuck detection | last 20 events | Ends the run `stuck` on 4 identical cycles, 3 repeated errors or 3 messages with no action | {{< badge content="default" color="green" >}} |
| Condenser | 80 events, keep first 4 | Summarises history with the same model, on the run's budget | {{< badge content="default" color="green" >}} |
| Event size | 30,000 chars | A huge output is truncated, not refused | {{< badge content="default" color="green" >}} |
| Tools | terminal, file editor, task tracker, MCP | No browser; MCP tools filtered per role by the gateway | {{< badge content="default" color="green" >}} |
| `search` | 40 iterations, 300k tokens, 300 s, 6 a run, effort `low`, 8,000 characters back | A read-only child (`grep`, `glob`, `read_file`, `list_directory`) on the run's token; its steps are the run's; ledger `/workspace/.agent-search.jsonl` | {{< badge content="experimental" color="yellow" >}} |
| Prompt caching | on for `internal` | 85% of input from cache: $0.48 instead of $2.13 | {{< badge content="default" color="green" >}} |
| `autotitle` | off | Saves a model call per title | {{< badge content="default" color="green" >}} |
| `agent-checks` | the CI's fast subset from `.github/agent-checks.yaml` | Before every push; the harness re-runs it on a finished implementer's head and notes the result | {{< badge content="default" color="green" >}} |
| Step log | every 15 s | Lines arrive in batches | {{< badge content="default" color="green" >}} |
| Progress notes | 5 milestones, ≤ 8 a run | Fixed texts in the room, nothing the model wrote | {{< badge content="default" color="green" >}} |
| Checkpoint on SIGTERM | implementer only | A reclaimed run's work survives on its branch | {{< badge content="default" color="green" >}} |
| Tracing | span per model and MCP call | No prompt or output content | {{< badge content="default" color="green" >}} |

```promql
# One run's tokens by model and type, as the meter prices them
sum by (gen_ai_request_model, gen_ai_token_type) (
  max_over_time(gen_ai_client_token_usage_sum{ar_agent="system:serviceaccount:agents:xplane-run-<id>"}[1d]))
```
