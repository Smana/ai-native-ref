---
title: Harness reference
aliases:
  - /docs/platform/ai-platform/agents/tune/harness-reference/
weight: 10
description: "The tier budgets, templates, workflows, concurrency caps, loop rows, run-controller mounts and OpenHands harness values set on this platform."
lastVerified: 2026-11-15
diataxis: reference
---

Every run on this platform is bounded by the `Factory` catalogue in
`tooling/base/agent-factory/resources/factory.yaml`, the run-controller values in
`infrastructure/base/room-broker/helmrelease.yaml`, and the OpenHands harness defaults in Maku's
`maku-harness` image. For the full schema of every `Factory`, `AgentRun` and budget key, see Maku's
[configuration reference]({{< maku "docs/reference/config.md" >}}) and
[budgets reference]({{< maku "docs/reference/budgets.md" >}}). How to tune these knobs is on
[Harness tuning]({{< relref "/docs/operate/tune-a-run.md" >}}).

- [Factory: tiers](#tiers)
- [Factory: templates, workflows and triage](#templates)
- [Factory: caps, budgets and loops](#caps)
- [Factory: what a brief holds](#brief)
- [Run API and AgentRun values](#run-api)
- [Run-controller and harness values](#composition)

## Factory: tiers {#tiers}

Example (the reference host), `spec.tiers` in `tooling/base/agent-factory/resources/factory.yaml`:

| Tier | `model` | `runUSD` / `taskUSD` | `runMinutes` | `runTokens` / `taskTokens` |
|---|---|---|---|---|
| `light` | `agent-default` | `$0.51` / `$1.02` | `20` | `300,000` / `600,000` |
| `standard` | `agent-default` | `$2.55` / `$5.10` | `45` | `1,500,000` / `3,000,000` |
| `frontier` | `agent-default` | `$6.80` / `$13.60` | `90` | `4,000,000` / `8,000,000` |

Every priced run is held to `runUSD` and `taskUSD` at the rates in `spec.prices` of
`tooling/base/agent-factory/resources/factory.yaml` (cache reads priced at their own rate); `runTokens`
and `taskTokens` cap a run only when the meter cannot price its model. The model gateway's per-run
token budget is the hard backstop ([gateways]({{< relref "/docs/how-it-works/gateways.md#budgets" >}})).

## Factory: templates, workflows and triage {#templates}

Example (the reference host), `spec.templates`, `spec.workflows`, `spec.defaults` and `spec.triage` in
`tooling/base/agent-factory/resources/factory.yaml`:

| Setting | Value on this platform | Notes |
|---|---|---|
| `templates.solo` | `{roles: [implementer]}` | Used by the `quick` workflow and scheduled tasks |
| `templates.pair` | `{roles: [implementer, reviewer], maxReviewRounds: 2, reviewerModel: kimi-frontier}` | Used by `standard` and `careful`; the `frontier` reviewer runs on Kimi K3.1 Pro ([providers]({{< relref "/docs/how-it-works/providers.md" >}})) |
| `templates.investigate` | `{roles: [triager]}` | Forced `internal` for RunLore findings; never writes code |
| `workflows.quick` | `{template: solo, tier: standard}` | Implementer alone; used by scheduled runs and `workflow:quick` |
| `workflows.standard` | `{template: pair, tier: standard, checks: true, stallSteps: 80, continuations: 2, judge: tier-light}` | Every repository's default (`Repository.spec.workflow.default: standard`) |
| `workflows.careful` | `{template: pair, tier: frontier, checks: true, stallSteps: 80, continuations: 2, judge: tier-light}` | Scoper first (`loops.careful`), implementer with `search` and checks, then reviewer |
| `defaults` / `triage.controlPercent` | `{dataClass: public}` / `0` | Triage picks `workflow:<name>` label, schedule workflow, `evaluation` arm (`treatment: careful` at 30%), or `Repository.spec.workflow.default` (`standard`) |

The reviewer runs on **the other tier** (`frontier` for a `standard` or `light` implementer, `standard`
for a `frontier` one) with that tier's `runUSD` cap, keeping the implementer's `runTokens` and
`runMinutes`.

## Factory: caps, budgets and loops {#caps}

Example (the reference host), `spec.caps`, `spec.budgets`, `spec.resume`, `spec.facts`, `spec.brief`
and `spec.loops` in `tooling/base/agent-factory/resources/factory.yaml`:

| Key | Value on this platform | Effect here |
|---|---|---|
| `caps` | `{activeTasks: 3, concurrentRuns: 4, tasksPerDay: 20, maxTextBytes: 14336, awaitingHumanWIP: 5, preferRevisions: true}` | Caps active tasks and sandboxes, prioritizes revision runs, and pauses new intake when 5 tasks await human review |
| `budgets` | `{enforceTask: true, enforcePrincipal: false, factoryDailyUSD: 42.50, humanDailyUSD: 8.50, perPerson: {enabled: true}}` | Task and run USD caps enforced; fleet and per-person daily caps counted in shadow |
| `resume` | `{maxPerTask: 2}` | Resumes `Disrupted` and `PodLost` runs up to twice within `taskTokens`; never resumes `PodFailed` |
| `facts.finalSpend` · `brief.ciEvidence` | `true` · `true` | Posts one final spend fact after settle; inlines reviewer comments and failing check annotations in revision briefs |
| `loops.default` | `{scope: "off"}` | `quick` and `standard` run without the scoper |
| `loops.careful` | `{scope: scoper, search: true, split: {maxChildren: 5, familyUSD: 20.40, childTier: standard, anyTier: true}}` | Runs the scoper, enables the `search` tool, and bounds splits to 5 parts and `$20.40` across the family |
| `scoper.nudgeAt` / `scoper.maxToolCalls` | `25` / `40` (Maku defaults; unset in `factory.yaml`) | Nudges the scoper at 25 tool calls and stops it at 40 (`budget_calls`) |

## Factory: what a brief holds {#brief}

`loops.<workflow>.scope` selects what the factory places in each run's brief (`scoper` on `careful`,
`off` on `quick` and `standard`):

- **Scoper (`scope: scoper`):** preamble, repository steering note (`.github/agent-factory/steering/<workflow>.md`,
  fenced as trusted), sanitised issue snapshot (fenced as untrusted), and instructions to scope, ask one
  question, or propose a split.
- **Implementer:** preamble, steering note, scoper handoff, and issue snapshot (inlined up to 16 KiB, or
  fetched via `room_read`). Revisions, CI fixes, retries and resumes prepend steering and scope ahead
  of up to 13 KiB of room log.
- **Judge and reviewer:** the completion judge reads the scoper's acceptance checks (or the issue's
  acceptance section when `scope: off`); the reviewer reads the pull request and room handoff without
  the implementer's transcript.

## Run API and AgentRun values {#run-api}

<span id="claim"></span>

`task agent:run` (`scripts/ops/k8s/agent-run.sh`) calls `POST /v1/runs` on `:8082`, and the factory
writes `agentruns.maku.ogenki.io` objects in `agents` (CRDs from
`tooling/base/agent-factory/crds/ocirepository.yaml`):

| Surface | Values on this platform |
|---|---|
| `task agent:run` flags | `--max-tokens` default `2,000,000` (max `5,000,000`), `--model` default `agent-default`, `--profiles` (`pypi`, `npm`, `golang`, `crates`), fixed at `120` min and `size: small` |
| `AgentRun.spec` | `size: small` (1–2 CPU, 2–4 GiB), `dataClass: public` or `internal`, `model: agent-default` (or `kimi-frontier` on the `frontier` reviewer), `loop.checks: true` on `standard` and `careful` (`Repository.spec.checks.egress` adds `[pypi]` on `cloud-native-ref` and `[golang, pypi]` on `ai-native-ref`) |

## Run-controller and harness values {#composition}

<span id="harness"></span>

Maku's run-controller (`infrastructure/base/room-broker/helmrelease.yaml`, under `runController`) turns
each `AgentRun` into a gVisor pod running [`agent_run.py`]({{< maku "images/maku-harness/agent_run.py" >}})
and [`sitecustomize.py`]({{< maku "images/maku-harness/site/sitecustomize.py" >}}):

| Setting | Value on this platform | Manifest / source |
|---|---|---|
| RuntimeClass and egress | `gvisor`, isolated via `egressProxy` to GitHub, the model gateway (`:8080` public, `:8081` internal) and allowed package registries | `infrastructure/base/room-broker/helmrelease.yaml` |
| Model and git credentials | Per-run projected gateway token (`LLM_API_KEY_FILE`) and per-run `<run>-git` Secret (`GIT_TOKEN_FILE`) | `infrastructure/base/room-broker/helmrelease.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Loop and call bounds | `reasoning_effort: high` (unset in env), 300 s call timeout (1 retry before first token), 3 retries on 503/reset (never 429), `max_iterations: 500`, stuck detector over last 20 events, condenser at 80 events (keeps first 4), 30,000-char event truncation | [`agent_run.py`]({{< maku "images/maku-harness/agent_run.py" >}}), [`sitecustomize.py`]({{< maku "images/maku-harness/site/sitecustomize.py" >}}) |
| Tools, checks and telemetry | Terminal, file editor, task tracker, room MCP (`:8090`), optional `search` child (40 iterations, 300k tokens, 300 s, max 6/run at `low` effort), `.github/agent-checks.yaml` pre-push and end-of-run check, 15 s step batches, SIGTERM checkpoint commit, OTLP spans without prompt text | [`agent_run.py`]({{< maku "images/maku-harness/agent_run.py" >}}) |
