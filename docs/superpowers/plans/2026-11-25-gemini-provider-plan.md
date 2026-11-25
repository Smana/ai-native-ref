# Gemini as a Model Provider: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maku routes a run to Gemini 4 Neon or Hydrogen through the model gateway. On gcp-0 the
route goes through Vertex AI with Workload Identity and no key. A paired live comparison against
`agent-default` produces a recorded verdict.

**Architecture:**
- **Part A, Maku:** two gateway presets (`gemini`, `vertex`); alias-driven OpenCode config; per-alias prices for OpenHands; a `model:<alias>` pin; `evaluation.treatmentModel`; `maku stages --by model`.
- **Part H, cloud-native-ref:** a prediction-only role that Crossplane may grant.
- **Part B, ai-native-ref:** the gcp-0 adoption, tighter AG assertions, price rows, the comparison report and the live runbook.

**Tech Stack:** Go (controller-runtime), Helm (`charts/maku-gateway`), agentgateway v1.6 CRDs, Python suites (OpenCode image, ANR CI), Crossplane `GCPWorkloadIdentity`, OpenTofu (host), Flux.

**Spec:** [`docs/superpowers/specs/2026-11-25-gemini-provider-design.md`](../specs/2026-11-25-gemini-provider-design.md), decisions G1 to G12. Copy it to Maku's `docs/superpowers/specs/` in the first Maku PR.

## Global Constraints

- **Worktrees:** each repository's work is done in a worktree from a freshly fetched `origin/main`, after `mise trust`. `task check` exits 0 before every commit and push.
- **Test first:** every task starts with the failing test named in it, run and seen red.
- **Commits:** conventional, in English, with no trailers, one concern per commit. The squash title is itself a conventional commit.
- **Never a default:** Gemini is public only and selectable. Base ANR stays provider-neutral; only the gcp-0 overlay names `vertex`.
- **No Google key:** none is added to OpenBao for gcp-0. The `gemini` (API-key) preset is for other installs and is the fallback only if Part H stalls (G1).
- **Live work:**
  - It waits for the OpenCode harness trial to close (G12) and for the owner's go on spend.
  - Every live number comes from a query, recorded in the ledger. No number is ever an estimate.
- **Releases:** Maku minor/patch tags follow the standing merge grant. ANR stays on v3.x/v4.x: no major.

## Review Focus

1. **A tool loop's second turn.** The signature at `tool_calls[i].extra_content.google.thought_signature` survives every hop (A2, A5, A6).
2. **`vertex` renders no `secretRef`.** Every other preset still requires one (A1).
3. **An unknown provider in the ANR render fails AG5 and AG15** instead of passing silently (B2).
4. **`model:<alias>` from a non-maintainer is ignored,** and so is an alias outside the role's capability profile (A8).
5. **The comparison arms differ only in model.** The report refuses to run if they differ in anything else (B6).

---

## Part A · Maku

### PR A-1: `feat(gateway): gemini and vertex presets`

#### Task A1: the presets render, and refuse what they must

**Files:** `charts/maku-gateway/templates/_presets.tpl`, `templates/_helpers.tpl` (`mgw.validate`, `mgw.catalogKey`), `templates/backends.yaml`, `templates/networkpolicy.yaml`, `values.yaml`, `charts/maku-gateway/tests/` (unit fixtures)

- [ ] Failing fixtures:
  - (1) `vertex` with `existingSecret` fails;
  - (2) `vertex` without `projectId` fails;
  - (3) `projectId` on `mistral` fails;
  - (4) `region: mars` fails;
  - (5) a valid `vertex` renders `policies.auth.gcp.type: AccessToken` and no `secretRef`;
  - (6) a valid `gemini` renders `custom` with host `generativelanguage.googleapis.com` and path `/v1beta/openai/chat/completions`;
  - (7) the network policy for `region: eu` dials `eu-aiplatform.googleapis.com:443` and the metadata server.
- [ ] Add both presets with `alwaysReasons: ["*"]` and empty `fields`.
- [ ] `mgw.validate`:
  - require `existingSecret` for every preset except `vertex`, and forbid it there;
  - require `projectId` for `vertex` only;
  - check `region` against `global|us|eu|<region>`.
- [ ] `backends.yaml`: for `vertex`, render `vertexai: {projectId, region}` and `auth.gcp`.
- [ ] Network policy: for `vertex`, add the metadata server (`169.254.169.254`, ports 80 and 988).
- [ ] `values.yaml` comment: the preset list gains `gemini | vertex`.

#### Task A2: the wire probe, with a signature-enforcing fake

**Files:** `charts/maku-gateway/tests/probe/` (P4's harness), a new fake upstream `fake-gemini`

- [ ] Failing probe P5. Set up the fake upstream:
  - It speaks Chat Completions.
  - It returns a tool call with `extra_content.google.thought_signature: "sig-1"`.
  - It answers **400** to a follow-up whose assistant tool call lacks that exact signature.
- [ ] Drive a three-turn loop through agentgateway v1.6 and assert:
  - turn 2 succeeds;
  - `model` is the forced alias's model;
  - `reasoning_effort` arrives unchanged.
- [ ] Run P5 against both the `custom` (`gemini`) path and the native `vertexai` path. The fake
  stands in for Vertex's host through the probe's DNS override.
- [ ] Record which path the native `vertexai` provider calls for a Gemini model.
  - If it does not call `.../endpoints/openapi/chat/completions`, switch the `vertex` preset to `custom` with that path, built from `projectId` and `region`, and keep `auth.gcp`.
  - Commit the observation in the probe's README.
- [ ] If agentgateway drops `extra_content`:
  - open an upstream issue with the probe as reproduction;
  - add a preset field `extra_content` that injects `skip_thought_signature_validator`, with its `why` naming the issue;
  - keep P5 asserting the stopgap, so the probe goes red when upstream is fixed and the field can go.

#### Task A3: catalog key and cost

**Files:** `templates/_helpers.tpl` (`mgw.catalogKey`, `mgw.catalog`), chart unit tests

- [ ] Failing test: for a `vertex` provider, the rendered `catalog.json` keys `gemini-4-neon` under
  the provider name agentgateway emits for `vertexai`. Read that name from the probe's access log
  in A2, never guess it.
- [ ] Add a P5 assertion that the access log's `cost` for a fixture call equals tokens × rate to
  the micro-dollar, with thinking tokens counted as output.
- [ ] Make `mgw.catalogKey` return that name for `vertex`, and `gemini` for the `gemini` preset.

#### Task A4: docs

**Files:** `docs/gateway.md` ("Presets", "Providers"), `charts/maku-gateway/README.md`, `docs/upgrading.md`, `docs/roadmap.md`

- [ ] `docs/gateway.md` gets one row per preset and the Workload Identity binding:
  - which ServiceAccount the proxy runs as;
  - the role it needs (`aiplatform.endpoints.predict`);
  - the regions.
- [ ] State the thought-signature contract and the probe that holds it.
- [ ] `docs/upgrading.md`: "two new presets; no default changes".
- [ ] `docs/roadmap.md`: add the row given verbatim in the spec's [Roadmap rows](../specs/2026-11-25-gemini-provider-design.md#roadmap-rows).

### PR A-2: `feat(harness): any gateway alias, priced per alias`

#### Task A5: OpenCode reads its aliases

**Files:** `images/maku-opencode/role_config.py`, `tests/test_provider_contract.py`, `tests/contract-matrix.py`, the run controller's env builder (`internal/factory/runcontroller/…`, where `LLM_BASE_URL` is set)

- [ ] Failing tests:
  - With `MAKU_ALIASES=agent-default,gemini-standard`, the config lists exactly those two models, each with low, medium and high variants.
  - With the variable unset, it falls back to `DEFAULT_ALIASES`.
  - A contract case `gemini/public/gemini-standard/high` runs a three-turn tool loop against `fake-gemini` (A2), and the signature round-trips.
- [ ] Implement: the run controller sets `MAKU_ALIASES` from its class's alias list, and `role_config.py` reads it.
- [ ] Add `gemini` to `PROVIDERS` in `contract-matrix.py`.
- [ ] If `@ai-sdk/openai-compatible` drops `extra_content`:
  - record it in the test as an expected failure, with a link to the upstream issue;
  - rely on A2's gateway stopgap;
  - say so in `docs/gateway.md`.

#### Task A6: OpenHands carries the signature and the alias's prices

**Files:** `images/maku-harness/openhands_driver.py`, its tests, the run controller's env builder

- [ ] Failing tests:
  - A driver test runs the same three-turn loop against `fake-gemini` through LiteLLM `openai/<alias>`.
  - A controller test: a run on `gemini-standard` gets `LLM_INPUT_USD_PER_MTOK=3.00` and `LLM_OUTPUT_USD_PER_MTOK=15.00` from the catalog row, not GLM's defaults.
- [ ] Implement the controller env.
- [ ] If LiteLLM drops `extra_content`, find the setting that keeps it (provider-specific fields on the message). If none exists, take the same expected-failure path as A5.

### PR A-3: `feat(factory): pin and compare a model`

#### Task A7: `model:<alias>` label pin

**Files:** `internal/factory/triage/pin.go`, `classify.go`, `internal/factory/reconciler/` (as `harness_test.go`), `internal/factory/narrate/narrate.go`, `docs/workflows.md`

- [ ] Failing tests, modelled on `harness_test.go`:
  - A maintainer's `model:gemini-standard` pins the implementer and reviewer, and `Task.status.modelSource` is `label`.
  - An outsider's label is ignored and narrated, like `HarnessRefused`.
  - An alias outside the role's capability profile is refused and narrated.
  - A labelled task is excluded from evaluation cohorts.
- [ ] Implement `ResolveModelPin` beside `ResolveHarnessPin`.

#### Task A8: `evaluation.treatmentModel`

**Files:** `internal/factory/config/evaluation.go`, its tests, CRD (`task crd:gen`), `docs/workflows.md`

- [ ] Failing tests:
  - `treatmentModel: gemini-standard` changes only the model of `treatmentRoles` (default `[implementer]`). Workflow, harness, effort and caps are equal across cohorts.
  - Setting `treatmentModel` and `treatmentHarness` together is refused, under the single-variable rule.
  - An alias unknown to the gateway's alias list is refused.
- [ ] Implement, then run `task crd:gen`.

#### Task A9: `maku stages --by model`

**Files:** `internal/factory/stages/report.go`, its tests, `internal/app/maku.go`, `docs/cli.md`

- [ ] Failing test: a fixture of 6 ended tasks across two models gives, per model:
  - `tasks`, `merged`, `usd` and `usdPerMerged`;
  - per-stage `effects`.

  A task whose stages ran on two models counts each stage under its own model and the task under its implementer's model.
- [ ] Implement, using the model recorded on each stage's run.
- [ ] `--json` passes through.

**Release:** a Maku minor (v0.55.0) carrying A-1 to A-3, with its `docs/upgrading.md` entry.

---

## Part H · cloud-native-ref (host), before Part B's identity task

### Task H1: a prediction-only Vertex role Crossplane may grant

**Files:** `opentofu/gcp/gke/init/iam.tf`, the project services list

- [ ] First, a failing check: the host's IAM plan test, or a `tofu plan` reviewed in the PR, shows the role absent from `crossplane_grantable_roles`.
- [ ] Add `google_project_iam_custom_role.vertex_predict`, with the permission `aiplatform.endpoints.predict` only, and its comment in the file's style.
- [ ] Append it to `crossplane_grantable_roles`. Keep it out of the bucket list (N1).
- [ ] Enable `aiplatform.googleapis.com` if it is off.
- [ ] Check that the `GCPWorkloadIdentity` XRD's role pattern admits a custom role name, as `crossplane_dns` proves.
- [ ] Merge, then note the host commit for B3's `HOST_REF` bump.

---

## Part B · ai-native-ref adoption

### Task B1: an offline check from a laptop (O6)

No code. This is the owner's go for a few cents.

- [ ] Call Vertex's `openapi` endpoint in `eu` with `gcloud auth print-access-token`:
  - the model is `google/gemini-4-neon`;
  - send a two-tool loop, with the signature first returned, then dropped.
- [ ] Record in the ledger draft:
  - whether a dropped signature gives 400 on Gemini 4;
  - the exact `usage` fields, including thinking tokens;
  - the Vertex price for both models, from <https://cloud.google.com/vertex-ai/generative-ai/pricing>, with the date.
- [ ] If the custom role (H1) is in place, repeat the call as a test service account holding only that role. This proves G3.

### Task B2: AG assertions fail closed

**Files:** `scripts/ci/flux-schema/assert-agent-gateway.py`, `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`, `scripts/ci/tests/flux-schema/maku-gateway-render.yaml`

- [ ] Failing tests:
  - A backend with an unrecognised provider fails AG5 and AG15. Today `provider_name()` returns `None` and the check is skipped.
  - A `vertexai` backend on the internal listener fails.
  - A `vertexai` backend with a `secretRef` fails.
  - A `vertexai` backend without `auth.gcp.type: AccessToken` fails.
- [ ] Add `"Google": {"public"}` to `PROVIDER_LISTENERS`, detection by `ai.provider.vertexai` or the `generativelanguage.googleapis.com` host, and the aliases to `BACKEND_MODELS`.

### Task B3: identity on gcp-0

**Files:** `HOST_REF`, `infrastructure/gcp-0/agent-gateway/model-gateway/workloadidentity.yaml`, its `kustomization.yaml`

- [ ] Failing check: `task check`'s render shows no `GCPWorkloadIdentity` for the proxy's ServiceAccount. Add a suite assertion in `scripts/ci/tests/` that gcp-0 has exactly one claim, named `xplane-model-gateway`, with the single custom role.
- [ ] Bump `HOST_REF` to H1's commit and add the claim. The ServiceAccount name is the one A4 documents.

### Task B4: provider, aliases, profiles, prices on gcp-0

**Files:**
- `infrastructure/gcp-0/agent-gateway/model-gateway/` (a HelmRelease patch)
- `infrastructure/gcp-0/room-broker/` (the run controller's public alias list)
- `infrastructure/base/agent-gateway/profiles/{implementer,reviewer,tester}.public.yaml`
- `policy-capabilities.yaml`
- `tooling/base/agent-factory/resources/factory.yaml` (`prices`)
- `scripts/ci/gen-prices.py` and its output
- `scripts/ci/check-price-drift.py` (`MAPPING`)
- `scripts/ci/tests/test-model-gateway-values.py`, `test-agent-prices.sh`

- [ ] Failing tests:
  - `test-model-gateway-values.py` expects `gemini-standard` and `gemini-light` on gcp-0's public listener only, and on no listener of aws-0 or base.
  - AG10 expects price rows with `source` and `checkedAt`.
  - The drift check expects a `MAPPING` entry for each row.
- [ ] Add the gcp-0 patch: `providers.vertex: {preset: vertex, projectId: ${gcp_project_id} or the literal, region: eu, dataClasses: [public]}` and the two aliases.
- [ ] Add the profile and capability entries, as Mistral's.
- [ ] Add the price rows at the Vertex `eu` rate read in B1, then run `gen-prices.py --write`.
- [ ] Pin Maku v0.55.0 (chart, images, CRDs) in the same PR, with the `params.makuVersion` site pin.

### Task B5: the planner patch for the test window

**Files:** `infrastructure/gcp-0/agent-gateway/model-gateway/` (a separate, revertable patch file)

- [ ] Failing test: the suite asserts that base's `clients.planner.provider` is `zai`, and that gcp-0's is either `zai` or `vertex` with `gemini-4-neon`, nothing else.
- [ ] Add the patch, commented as test-window only. It merges just before L2 and is reverted after.

### Task B6: the comparison report

**Files:** `scripts/ops/model-comparison-report.py`, `scripts/ci/tests/test-model-comparison-report.py`, fixtures

- [ ] Failing tests, on fixtures:
  - Pairs by issue title across two repositories.
  - Refuses if the arms differ in workflow, harness, effort or caps.
  - Per arm, computes:
    - the merged share;
    - USD per merged task, as the median and the total;
    - the median duration;
    - verdict counts and review rounds;
    - ends by cap, by 400 and by stall.
  - Prints the frozen directional rule's verdict: merged share at least A's minus one; USD per merged at most 1.5 × A's; zero signature 400s.
- [ ] Implement it on `maku stages --by model --json` and the Task CRs, as `harness-trial-report.py` does.

### Task B7: the live runbook

**Files:** `docs/runbooks/agent-factory/<next-number>-gemini-provider.md`

- [ ] Write L1 to L5 as numbered steps, each with:
  - its command;
  - its pass line;
  - its stop condition, such as a 400 from a signature or a cost mismatch above 2 %, which stops the step and is recorded.
- [ ] Prerequisites:
  - the OpenCode trial is closed with no treatment left;
  - Maku v0.55.0 is deployed;
  - B3 to B5 are merged;
  - the owner's go is recorded;
  - the Ultra credits are checked on `ogenki-435905`'s billing account.

### Task B8: the status page

**Files:** `website/content/docs/status.md`

- [ ] After L4's verdict, update the status row only:
  - Experimental (selectable on the public listener), or a known limitation if L3 failed;
  - one sentence;
  - the spec linked by its GitHub URL once on `main`.

  Run `task docs`.

---

## Live session order (gcp-0, after the harness trial)

1. B1, already done offline.
2. L1: wire, identity and metering.
3. B5 merged, then L2: the planner. Revert B5.
4. L3: roles on both harnesses.
5. L4: the paired comparison. Run B6's report.
6. L5, optional: the second-family reviewer.
7. Write the ledger, B8, and the owner's decision on a 30+30 `treatmentModel` trial.
