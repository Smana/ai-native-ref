---
title: Harness reference
aliases:
  - /docs/platform/ai-platform/agents/tune/harness-reference/
weight: 10
description: "The tier budgets, workflows, roles, concurrency caps, run-controller mounts and harness values set on this platform."
lastVerified: 2026-11-25
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
- [Factory: workflows, roles and triage](#templates)
- [Factory: caps and budgets](#caps)
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

## Factory: workflows, roles and triage {#templates}

<span id="workflows"></span>

Example (the reference host), `spec.workflows`, `spec.roles`, `spec.outcomes`, `spec.defaults` and
`spec.triage` in `tooling/base/agent-factory/resources/factory.yaml`. A workflow is an ordered list of
stages and a `budget`, the tier its runs take:

| Setting | Value on this platform | Notes |
|---|---|---|
| `workflows.quick` | Maku's shipped entry: `budget: standard`, one implementer that stops a stalled run | Scheduled runs and `workflow:quick`; steps up to `standard` |
| `workflows.standard` | `budget: standard`, `stepUp: careful`; implementer (`checks`, `stall`), reviewer (`maxRounds: 2`) | Every repository's default (`Repository.spec.workflow.default: standard`) |
| `workflows.careful` | `budget: frontier`; scoper (`split: {maxParts: 4}`, `gate: {when: plan-first}`), tester (`when: repository.testFirst`), implementer (`checks`, `search`, `stall`, `judge: evidence`), reviewer | `workflow:careful`, or one step up from `standard` |
| `workflows.thorough` | `budget: frontier`; tester, implementer, `security-reviewer`, reviewer | Reached only by the label `workflow:thorough` |
| `roles.security-reviewer` | `{capability: read, brief: roles/security-reviewer.md}` | A custom role reads the diff with the reviewer's read-only token; the built-in reviewer still decides |
| `outcomes` | `[change, plan-first, review, report]` | The labels `plan-first`, `factory/review` and `report` pick the other three |
| `scoper.planTier` | `frontier` | The scoper plans on the strong model |
| `defaults` / `triage.controlPercent` | `{dataClass: public}` / `0` | Triage picks a `workflow:<name>` label, the schedule's workflow, or `Repository.spec.workflow.default` (`standard`) |

The reviewer runs on **the other tier** (`frontier` for a `standard` or `light` implementer, `standard`
for a `frontier` one) with that tier's `runUSD` cap, keeping the implementer's `runTokens` and
`runMinutes`.

## Factory: caps and budgets {#caps}

Example (the reference host), `spec.caps`, `spec.budgets`, `spec.resume`, `spec.facts`, `spec.brief`
and `spec.scoper` in `tooling/base/agent-factory/resources/factory.yaml`:

| Key | Value on this platform | Effect here |
|---|---|---|
| `caps` | `{activeTasks: 3, concurrentRuns: 4, tasksPerDay: 20, maxTextBytes: 14336, awaitingHumanWIP: 5, preferRevisions: true}` | Caps active tasks and sandboxes, prioritizes revision runs, and pauses new intake when 5 tasks await human review |
| `budgets` | `{enforceTask: true, enforcePrincipal: false, factoryDailyUSD: 42.50, humanDailyUSD: 8.50, perPerson: {enabled: true}}` | Task and run USD caps enforced; fleet and per-person daily caps counted in shadow |
| `resume` | `{maxPerTask: 2}` | Resumes `Disrupted` and `PodLost` runs up to twice within `taskTokens`; never resumes `PodFailed` |
| `facts.finalSpend` · `brief.ciEvidence` | `true` · `true` | Posts one final spend fact after settle; inlines reviewer comments and failing check annotations in revision briefs |
| `scoper.nudgeAt` / `scoper.maxToolCalls` | `25` / `40` (Maku defaults; unset in `factory.yaml`) | Nudges the scoper at 25 tool calls and stops it at 40 (`budget_calls`) |

## Factory: what a brief holds {#brief}

A workflow's stages select what the factory places in each run's brief (a scoper on `careful`, none
on `quick`, `standard` and `thorough`):

- **Scoper:** preamble, repository steering note (`.github/agent-factory/steering/<workflow>.md`,
  fenced as trusted), sanitised issue snapshot (fenced as untrusted), and instructions to scope, ask one
  question, or propose a split.
- **Implementer:** preamble, steering note, scoper handoff, and issue snapshot (inlined up to 16 KiB, or
  fetched via `room_read`). Revisions, CI fixes, retries and resumes prepend steering and scope ahead
  of up to 13 KiB of room log.
- **Judge and reviewer:** the completion judge reads the scoper's acceptance checks (or the issue's
  acceptance section when no scoper ran); the reviewer reads the pull request and room handoff without
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
| Harness | OpenHands by default. The OpenCode image is pinned by digest and admitted: a maintainer's `harness:opencode` label runs one task on OpenCode, and a trial (`evaluation: {controlPercent: 50, treatmentHarness: opencode}` on one cluster) runs half of the unlabelled tasks on it. `/factory retry harness=openhands` moves a task back | `infrastructure/base/room-broker/helmrelease.yaml` (`runController.images.opencode`) |
| Tools, checks and telemetry | Terminal, file editor, task tracker, room MCP (`:8090`), optional `search` child (40 iterations, 300k tokens, 300 s, max 6/run at `low` effort), `.github/agent-checks.yaml` pre-push and end-of-run check, 15 s step batches, SIGTERM checkpoint commit, OTLP spans without prompt text | [`agent_run.py`]({{< maku "images/maku-harness/agent_run.py" >}}) |
