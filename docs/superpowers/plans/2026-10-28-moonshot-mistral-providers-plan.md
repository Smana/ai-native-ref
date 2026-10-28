# Feature 15: Moonshot and Mistral as selectable providers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a public class can run a role on `kimi-frontier`, `mistral-standard` or `mistral-light`
by one config value. Each run is priced by the meter, internal work cannot reach either provider,
and no default changes.

**Architecture:** the work is three code PRs and two pin bumps, plus an owner probe that comes
first:

| # | Repository | What |
|---|---|---|
| 0 | none (owner shell) | Probe both APIs with the owner's keys: ids, prices, usage fields, rejected fields |
| 1 | ai-native-ref | The backends, routes, ExternalSecrets, egress, prices, profiles and gates, plus the wire test. It merges first and on its own: the routes exist, but no factory config can name the aliases yet |
| 2 | agent-platform | The three aliases join the C5 names (CRDs, `models()`, API), and `loops.<class>.models` for public tasks, with validation. Release |
| 3 | crossplane-configuration | The AgentRun XRD's `model` and `judgeModel` enums. Release |
| 4 | cloud-native-ref | The crossplane-configuration pin bump. Then this repository's `HOST_REF` bump |
| 5 | ai-native-ref | The agent-platform pin bump and runbook 14's owner lines. No class row: every row stays off (D4) |
| 6 | gcp-0 session | Live proofs |

**Spec:** [the design](../specs/2026-10-28-moonshot-mistral-providers-design.md), F1 to F10.

**Tech stack:** agentgateway 1.6.0 CRDs, Python 3 with PyYAML (generators and gates), Bash and
Docker (the wire test), Go and kubebuilder (agent-platform), KCL (crossplane-configuration).

**Out of this plan:** every item in the design's "Not in scope" list. No class row is added to
`loops`: a row is the owner's switch, set for the live session and removed after it.

## Task 0 [OWNER]: probe the providers (done 2026-10-28)

**Results**, which amend everything below (the design's amendment section has the table): Kimi is the
owner's Kimi Code subscription at `https://api.kimi.ai/coding/v1`, model `k3.1-pro`, a flat-rate plan
priced nominally; the cached-token field is the standard one (go); `reasoning_content` eats
`max_tokens`; Mistral passes on the paid plan (cache field `prompt_tokens_details.cached_tokens`; Small cached on the 2nd call, Medium showed 0, unverified); Moonshot data is
processed in China (public only) and Mistral's in the EU. `loops.<class>.models` (Task 2) is pending
behind agent-platform's rebrand code freeze.

The original steps, kept for the record:

Run it from the owner's shell with the agents' own keys, and never in the cluster. Its output
fills the `[verify]` values below, and the executor never sees a key.

- [ ] **Step 1: seed the keys**

  ```bash
  bao kv put -mount=agents moonshot api_key=-
  bao kv put -mount=agents mistral api_key=-
  ```

- [ ] **Step 2: list the models.** Record the exact ids for Medium 3.5 and Small 4, and confirm
  `k3.1-pro`:

  ```bash
  curl -s https://api.kimi.ai/coding/v1/models -H "Authorization: Bearer $MOONSHOT" | jq -r '.data[].id'
  curl -s https://api.mistral.ai/v1/models  -H "Authorization: Bearer $MISTRAL"  | jq -r '.data[].id' | grep -E 'medium|small'
  ```

- [ ] **Step 3: check the cache field and the rejected fields.** Send the same request, with a
  prompt over 2,000 tokens, twice to each provider. Send it once with `"reasoning_effort":"high"`
  and once with `"temperature":0.2`. Keep each full `usage` object and every non-200 body in
  `scratchpad/owner/f15-probe.txt`. Record where cached tokens appear (`usage.cached_tokens` or
  `usage.prompt_tokens_details.cached_tokens`), whether Moonshot reports cache writes, and which
  fields return 4xx.

- [ ] **Step 4: read the official price pages** (platform.kimi.ai/docs/pricing/chat,
  mistral.ai/pricing) and record input, cache hit, cache write and output for each id.

**Go / no-go.** If Moonshot reports cached tokens only at the top level, stop the Moonshot half:
agentgateway would count no cache reads (design F5). Mistral goes on.

## Task 1: ai-native-ref, the gateway half (one PR)

Work in a worktree from `origin/main`.

**Files:**
- Create `infrastructure/base/agent-gateway/moonshot.yaml` and `mistral.yaml`: the backend, plus
  the ExternalSecret `agents-<provider>-api-key` (store `agents-secrets`, `remoteRef.key`
  `<provider>`, property `api_key`), shaped like `agent-router/externalsecret-zai.yaml` without its
  handover annotation.
- Modify `infrastructure/base/agent-gateway/kustomization.yaml`: add both files.
- Modify `infrastructure/base/agent-gateway/llm.yaml`: add the HTTPRoute `agentgateway-models`
  rules `moonshot` and `mistral` (`PathPrefix /v1` plus header `x-ar-model` `Exact`, one match per
  alias), and the alias table in the header comment.
- Modify `infrastructure/base/agent-gateway/network-policy.yaml`: add `api.kimi.ai` and
  `api.mistral.ai` to the providers' `toFQDNs`.
- Modify `tooling/base/agent-factory/helm-values-configmap.yaml`: add the three `meter.prices`
  rows, with `source` and `checkedAt` from Task 0.
- Modify `scripts/ci/gen-prices.py`: `PROVIDERS += (("kimi-", "moonshot"), ("mistral-", "mistral"))`.
- Regenerate `infrastructure/base/agent-gateway/model-catalog.yaml` and the
  `llm-gateway-prices` group with `gen-prices.py --write`.
- Modify `infrastructure/base/agent-gateway/policy-budgets.yaml`: the three cost strings, set to
  the string AG8 prints.
- Modify `scripts/ci/check-price-drift.py`: `MAPPING`, plus `ABSENT` for any catalog that lacks a
  row.
- Modify `infrastructure/base/agent-gateway/profiles/*.public.yaml`: add `models += [kimi-frontier,
  mistral-standard, mistral-light]`, then run `gen-capabilities.py --write`.
- Modify `scripts/ci/gen-capabilities.py`: refuse a provider alias in an `*.internal.yaml` profile.
- Modify `scripts/ci/flux-schema/assert-agent-gateway.py`:
  - `PROVIDER_LISTENERS["Moonshot"|"Mistral"] = {"public"}` and `provider_name()`, by
    `providerOverride`;
  - AG12 per-backend aliases: `BACKEND_MODELS = {"zai": AGENT_MODELS, "anthropic": AGENT_MODELS,
    "moonshot": ("kimi-frontier",), "mistral": ("mistral-light", "mistral-standard")}`, with the
    transformation allow-list built from that backend's names;
  - AG14 `model_rule_ok`: models ⊆ the names the listener's backends serve;
  - AG5 `providerOverride` ∈ `gen-prices.PROVIDERS` for each custom backend;
  - AG11 typed routes for every custom backend, not only Z.ai.
- Test files:
  - `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`;
  - `scripts/ci/tests/test-gen-prices.py`, `test-gen-capabilities.py` and
    `test-check-price-drift.py`;
  - `scripts/ci/tests/test-agent-gateway-cache-wire.sh`, or a sibling
    `test-agent-gateway-providers-wire.sh` if the first grows past reading.

**Steps:**

- [ ] **Step 1: write the failing gate fixtures** in `test-assert-agent-gateway.py`:
  - a `moonshot` backend attached to the `internal` listener → `AG5 … Moonshot is public-only`;
  - a `mistral` backend that also aliases `tier-light` → `AG12 … must alias exactly
    ['mistral-light', 'mistral-standard']`;
  - an internal capability alternative listing `kimi-frontier` → `AG14`;
  - a backend with `providerOverride: kimi` → `AG5`.
- [ ] **Step 2: run the tests and watch them fail:**
  `python3 scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`.
- [ ] **Step 3: change the gate** as listed under Files, until Step 2 passes.
- [ ] **Step 4: write the failing generator goldens** (catalog provider keys, an internal profile
  refused, the three drift `MAPPING` rows), then make the generator changes.
- [ ] **Step 5: add the manifests**, run the two generators with `--write`, and paste AG8's
  expected cost string into `policy-budgets.yaml`.
- [ ] **Step 6: wire test.** Add fake Moonshot and Mistral upstreams, using the existing fake's
  pattern, and assert the following:
  - `x-ar-model: kimi-frontier` → Moonshot's fake gets `model: kimi-k3.1-pro`, with no
    `temperature` or `top_p` if Task 0 found them refused (the backend's transformations null
    them);
  - `mistral-standard` and `mistral-light` → Mistral's fake, with the dated ids; `reasoning_effort`
    is absent if Task 0 found it refused;
  - a body-only `kimi-frontier` with no header → 400, and neither fake is called;
  - a reply with `prompt_tokens_details.cached_tokens: 900` of `1000` → `cached_input` 900 in
    `gen_ai_client_token_usage_sum`, and `agentgateway_cost_catalog_lookups_total{status="Exact"}`
    for both providers;
  - a control request on today's `tier-light` still reaches the Z.ai fake.
- [ ] **Step 7: run the whole check.** Expected exit status 0:

  ```bash
  ~/.cache/v3/check.sh "$PWD"     # wraps `task check`: composite, host validate, gates, suites, links, site
  pre-commit run --all-files
  ```

- [ ] **Step 8: commit and open the PR.** Commit message
  `feat(agent-gateway): Moonshot and Mistral backends on public, priced, every alias unselected
  (F15)`. Open the PR, and don't merge it before review.

## Task 2: agent-platform, the aliases and `loops.<class>.models` (one PR, then a release)

**Files:**
- Modify `internal/factory/config/config.go`:
  - `models()` gains the three names, with a `providerModels` map (alias → tier) for them;
  - `Loop` gains `Models map[string]map[string]string` (`json:"models,omitempty"`);
  - validation refuses an unknown role, a tier other than the alias's own (design F2), a name
    outside `providerModels`, and a model unpriced while `meter.prices` is set.
- Modify the place that picks a run's model, wherever `Tier.Model` and `ReviewerModel` resolve
  today (`internal/factory/reconciler/implement.go`, `team.go`): `Models[role][tier]` applies when
  `task.Spec.DataClass == "public"`, and otherwise today's model. Record the source in the run's
  provenance.
- Modify `api/factory/v1alpha1/task_types.go` and `api/v1alpha1/agentrun_types.go`: widen the
  enums, then regenerate the CRDs (`make generate manifests`).
- Modify `internal/factory/api/server.go`: widen `models`.
- Tests: `internal/factory/config/config_test.go` and the reconciler's model-selection test.

**Steps:**

- [ ] **Step 1: write the failing table tests:**
  - the public task of class `docs`, tier `standard`, with `models.implementer.standard:
    mistral-standard` → `MODEL=mistral-standard`;
  - the same task with `dataClass: internal` → `agent-default`;
  - `models.implementer.frontier: mistral-light` → config error `tier`;
  - an unknown alias → config error;
  - the reviewer with no entry → its `reviewerModel`.
- [ ] **Step 2: run them and watch them fail:** `go test ./internal/factory/...`.
- [ ] **Step 3: implement** the changes listed under Files until the tests pass. Then run
  `make generate manifests`, `go test ./...` and the repository's lint.
- [ ] **Step 4: commit, open the PR and release.** Commit message
  `feat(factory): provider aliases and loops.<class>.models for public tasks (v3 F15)`. After
  review and merge, cut the release (the chart's appVersion).

## Task 3: crossplane-configuration, the XRD enums (one PR, then a release)

**Files:** modify `apis/agentrun/definition.yaml`, the `model` and `loop.judgeModel` enums, and
`apis/agentrun/kcl/main_test.k`, with one case each for `kimi-frontier` and `mistral-light`.

- [ ] **Step 1:** write the failing KCL case, then make the enum change, then run the repository's
  test target.
- [ ] **Step 2:** commit `feat(agentrun): accept the provider aliases (v3 F15)`, open the PR,
  merge it after review, and release.

## Task 4: cloud-native-ref, the crossplane-configuration pin, then `HOST_REF`

- [ ] **Step 1:** bump the three `crossplane-configuration-{core,aws,gcp}` tags in
  `infrastructure/base/crossplane/configuration-*/` to Task 3's release. Run the host's
  `test-crossplane-configuration-pins.sh`, then open the PR, `chore(crossplane): crossplane-configuration
  <v> (provider aliases)`.
- [ ] **Step 2:** once it merges, bump `HOST_REF` here to the merge commit and run
  `~/.cache/v3/check.sh "$PWD"`.

## Task 5: ai-native-ref, the agent-platform pin and the owner lines

**Files:**
- `tooling/base/agent-factory/` holds the chart and appVersion pins: set them to Task 2's release.
- `docs/runbooks/agent-factory/14-gcp-0-session.md` §5 gains the two `bao kv put` lines.
- The runbooks README's owner actions gain the item "agents' own Moonshot and Mistral keys, and a
  console spend cap on each".

- [ ] **Step 1:** make the edits and run `~/.cache/v3/check.sh "$PWD"`. Expected: exit 0, and AG14
  still passes, because no tier pins a provider alias.
- [ ] **Step 2:** commit `feat(agent-factory): agent-platform <v>, provider aliases selectable, none
  selected (F15)` and open the PR.

## Task 6: live proofs (gcp-0 session checklist)

Add these lines to the session's checklist (runbook 14, the v3 live list). Each result goes in its
runbook table:

- [ ] **1. Smoke.** With a run's token, through the identity proxy:
  - three tool-call turns on each alias;
  - on `mistral-standard`, one forced condensation and one judge continuation.

  Pass when no 4xx appears.
- [ ] **2. One run per provider.** Add a one-session class row: `models: {implementer: {frontier:
  kimi-frontier}}`, or `{standard: mistral-standard}`. Run one public issue on each, then remove
  the row. Record cost per run from the meter (`agent_factory_run_spend_usd`), the gateway's cost
  counter (within 1%), and a cache-read share above 0. `kimi-frontier` runs only once Q1 is
  answered.
- [ ] **3. Refusal.** On an internal run's token, `x-ar-model: kimi-frontier` → 403, and neither
  provider's FQDN shows a flow in Hubble.

**Fallback on failure.** If the smoke fails on Kimi's `reasoning_content` replay or on Mistral's
tool-call ids, the alias stays unselected. The harness fix becomes an agent-platform issue,
following the design's F9 table.

## Estimate

| Task | Size |
|---|---|
| 0 | Owner, 20 minutes |
| 1 | 1 to 1.5 days: gates and wire test are most of it |
| 2 | 0.5 to 1 day |
| 3 and 4 | 2 hours, plus release and review latency |
| 5 | 1 hour |
| 6 | About 1.5 hours of a gcp-0 session, at under $10 of model spend (one frontier run at most $6.80, one standard run at most $2.55) |
| **Total** | **About 3 to 4 working days of build, plus the review round-trips of five PRs** |
