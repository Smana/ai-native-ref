---
title: Harness reference
aliases:
  - /docs/platform/ai-platform/agents/tune/harness-reference/
weight: 10
description: "The tier budgets, templates, concurrency caps, loop rows, run-controller mounts and OpenHands harness values set on this platform."
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
- [Factory: templates and triage](#templates)
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

## Factory: templates and triage {#templates}

Example (the reference host), `spec.templates`, `spec.defaults` and `spec.triage` in
`tooling/base/agent-factory/resources/factory.yaml`:

| Setting | Value on this platform | Notes |
|---|---|---|
| `templates.solo` | `{roles: [implementer]}` | Used for `docs-links` on `standard` |
| `templates.pair` | `{roles: [implementer, reviewer], maxReviewRounds: 2}` | Default for `review` and most classes; `docs-links` on `frontier` |
| `templates.trio` | `{roles: [implementer, reviewer], maxReviewRounds: 2}` | Matches `pair` here; the tester runs through `testFirst` on the class |
| `templates.investigate` | `{roles: [triager]}` | Forced `internal` for RunLore findings; never writes code |
| `defaults` | `{dataClass: public, predictedClass: review}` | Fallback class when triage predicts none |
| `triage.controlPercent` | `10` | No classifier is deployed, so 90% of tasks run on `standard` and 10% on `frontier` |

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
| `loops.default` | `{scope: "off"}` | Classes without a row run unscoped with no completion judge |
| `loops.docs` | `{scope: scoper, stallSteps: 60, continuations: 2, judge: tier-light, search: true}` | Scoper, 60-step stall stop, up to 2 `tier-light` judge continuations, and the read-only `search` helper |
| `loops.scripts` | `{scope: scoper, split: {maxChildren: 4, familyUSD: 20.40, childTier: standard, anyTier: true}, judge: tier-light}` | Scoper, splitter (up to 4 parts, `$20.40` family cap) and `tier-light` completion judge |
| `loops.{docs-links,revert,dead-links,deps-patch}` | `{models: {reviewer: {frontier: kimi-frontier}}}` | Runs the `frontier` reviewer on Kimi K3.1 Pro ([providers]({{< relref "/docs/how-it-works/providers.md" >}})) |
| `scoper.nudgeAt` / `scoper.maxToolCalls` | `25` / `40` (Maku defaults; unset in `factory.yaml`) | Nudges the scoper at 25 tool calls and stops it at 40 (`budget_calls`) |

## Factory: what a brief holds {#brief}

`loops.<class>.scope` selects what the factory places in each run's brief (`scoper` on `docs` and
`scripts`, `off` on every other class):

- **Scoper (`scope: scoper`):** preamble, repository steering note (`.github/agent-factory/steering/<class>.md`,
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
| `AgentRun.spec` | `size: small` (1–2 CPU, 2–4 GiB), `dataClass: public` or `internal`, `model: agent-default` (or a class's provider alias on `public`), `loop.checks: true` on `docs` (`Repository.spec.checks.egress` adds `[pypi]` on `cloud-native-ref` and `[golang, pypi]` on `ai-native-ref`) |

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
