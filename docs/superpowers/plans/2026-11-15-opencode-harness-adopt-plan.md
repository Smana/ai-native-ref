# OpenCode Second Harness: ai-native-ref Adoption Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the Maku release that carries opt-in OpenCode, prove it on aws-0 only after explicit authorization, compare it with OpenHands without changing models or workflows, and cut over only if the strict outcome gate passes.

**Architecture:** Base pins Maku and leaves `defaults.harness` and `evaluation.treatmentHarness` absent, so OpenHands remains default. The aws-0 overlay alone enables provider smoke tasks and the 50/50 harness cohort. Both arms use the same careful workflow, models, efforts, limits, repositories, and test-contract settings. Rescue uses a separate cohort and never erases the failed arm.

**Tech Stack:** Flux Kustomizations and HelmReleases, Maku CRDs, kustomize overlays, Kubernetes Task objects, gVisor, VictoriaMetrics/Traces/Logs, Python CI suites, Hugo.

**Spec:** [`docs/superpowers/specs/2026-11-15-opencode-harness-design.md`](../specs/2026-11-15-opencode-harness-design.md). The Maku half is [`2026-11-15-opencode-harness-maku-plan.md`](2026-11-15-opencode-harness-maku-plan.md).

## Global Constraints

- Work in a git worktree branched from `origin/main`; rebase onto freshly fetched `origin/main` before every push. Run `task check` before every commit.
- This plan starts only in the platform v5.x programme, after Maku's offline parity release and the current workflow/cache/cost comparisons are complete.
- Base never selects OpenCode and never carries a harness trial. Only aws-0 may carry an explicitly enabled trial; gcp-0 remains unchanged.
- Rebuilding or resuming aws-0 requires a separate owner authorization recorded in the live PR. No `task check`, script, or implementation step performs it automatically.
- Both trial arms use identical workflow, models, efforts, repository checks, tester settings, limits, and traffic exclusions. Only `evaluation.treatmentHarness` differs.
- No duplicate historical tasks and no automatic mid-task harness switch. Rescue is `/factory retry harness=openhands`, recorded under `rescue`.
- Every live reading is real: record cluster, Maku version/digest, time window, ended-task counts, exclusions, and query output. Never fill a result from an estimate.
- Site pages follow `docs/docs-style.md`; availability lives on `status.md` only. Repository specs and runbooks use GitHub links.
- Every child names `sourceRef: {kind: OCIRepository, name: ai-native-ref}` and depends only on host Kustomizations in `HOST-CONTRACT.md` H2.
- Commits are conventional, in English, with no trailers.

## Prerequisites

| Prerequisite | Required by |
|---|---|
| Maku release H contains all 14 Maku-plan tasks and its offline matrix passes | Task 1 |
| Current workflow and cache/cost experiments are closed with no treatment left enabled | Tasks 3–6 |
| Owner approves aws-0 infrastructure and running costs in a live PR | Tasks 3–6 |
| The strict outcome gate passed and is recorded | Task 6 |
| At least 30 days and 30 ended default tasks passed without a rollback trigger | Task 7 |

## Review Focus

1. **Accidental default adoption:** base has no `defaults.harness`, no `evaluation.treatmentHarness`, and no `harness:opencode` label on ordinary tasks.
2. **Confounded comparison:** trial objects contain no other treatment, and both arms resolve to identical careful workflow definitions and model/effort values.
3. **Hidden rescue:** original OpenCode failure is counted under its original cohort; only the OpenHands rescue appears under `rescue`.
4. **Provider blind spots:** GLM/Z.ai, Anthropic, Kimi, and Mistral each have a real served-model/cache reading before cutover.
5. **Premature removal:** OpenHands remains pinned and selectable throughout the soak, independent of the default.

---

### Task 1: Pin Maku H with the harness trial off everywhere

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml`, the agent-factory CRDs chart source, `infrastructure/base/room-broker/helmrelease.yaml`
- Modify: `website/content/docs/status.md`
- Create: `scripts/ci/tests/test-agent-harness-trial-off.py`
- Test: `scripts/ci/tests/test-agent-harness-trial-off.py`, `task factory-config`, `task check`

**Interfaces:**
- Consumes: Maku H's `AgentRun.spec.harness`, `runController.images.opencode`, `Factory.spec.defaults.harness`, and `evaluation.treatmentHarness`.

- [ ] **Step 1: Write the failing trial-off suite**

```python
base = render("tooling/base/agent-factory/resources") + render("tooling/base/agent-factory")
gcp = render("tooling/gcp-0/agent-factory/resources") + render("tooling/gcp-0/agent-factory")
for objects in (base, gcp):
    factory = one(objects, "Factory", "agent-factory")
    assert "harness" not in factory["spec"].get("defaults", {})
    assert "treatmentHarness" not in factory["spec"].get("evaluation", {})
    assert "treatment" not in factory["spec"].get("evaluation", {})
assert "opencode" in crd_enum("agentruns.maku.ogenki.io", "spec.harness")
assert image_digest("ghcr.io/smana/maku-opencode") == RUN_CONTROLLER_VALUES["images"]["opencode"].split("@")[-1]
```

The digest assertion compares the Maku H chart's rendered OpenCode image with ANR's run-controller values. No tag-only pin is accepted.

- [ ] **Step 2: Run and see it fail**

Run: `python3 scripts/ci/tests/test-agent-harness-trial-off.py`
Expected: FAIL because the Maku H pin and OpenCode enum/image are absent.

- [ ] **Step 3: Pin Maku H everywhere by digest**

Update the OCI source, factory chart, CRDs chart, broker/run-controller chart, and `runController.images.opencode` to the artifacts published by Maku H. Leave `defaults.harness` and both evaluation treatment fields absent. `status.md` records the Maku version and “OpenCode harness: planned” until live validation finishes.

- [ ] **Step 4: Run all gates and commit**

Run: `task check`
Expected: exit 0, including strict Maku config loading and the new trial-off suite.

```bash
git commit -am "chore(deps): Maku H, opt-in OpenCode with OpenHands default"
```

### Task 2: Prove the composite offline contract before any infrastructure action

**Files:**
- Modify: `scripts/ci/tests/test-agent-factory-pins.py`, `scripts/ci/tests/test-model-gateway-values.py`, `scripts/ci/tests/test-agent-harness-trial-off.py`
- Create: `scripts/ci/tests/test-opencode-render.py`
- Test: both new suites, `task validate`, `task check`

**Interfaces:**
- Produces: composite proof that an OpenCode AgentRun selects only the pinned image/driver, while default renders remain OpenHands.

- [ ] **Step 1: Write failing render assertions**

```python
def test_opencode_claim_uses_pinned_image_and_loopback_driver():
    run = agent_run(harness="opencode", role="implementer", data_class="public")
    pod = render_run_controller(run)
    harness = container(pod, "harness")
    bridge = container(pod, "room-bridge")
    assert harness["image"].startswith("ghcr.io/smana/maku-opencode@sha256:")
    assert env(harness)["AGENT_HARNESS"] == "opencode"
    assert env(bridge)["AGENT_HARNESS"] == "opencode"
    assert env(harness)["HARNESS_URL"] == "http://127.0.0.1:8000"
    assert restricted_security_context(pod)

def test_default_claim_render_is_unchanged():
    assert agent_run().pod == golden("default-agentrun-pod.yaml")
```

Add schema refusal for `harness: other`, a post-creation mutation, a missing image digest, and an internal run carrying a public provider alias.

- [ ] **Step 2: Run and see the failure**

Run: `python3 scripts/ci/tests/test-opencode-render.py`
Expected: FAIL until the composite contains Maku H's CRD, chart, and admission behavior.

- [ ] **Step 3: Correct pins or composite wiring only**

Do not add a host-specific script to ANR. If the host needs a change, stop this task and open the cloud-native-ref PR first, then bump `HOST_REF` here as `AGENTS.md` requires.

- [ ] **Step 4: Run gates and commit**

Run: `task check`
Expected: exit 0. No aws-0 command has been run.

```bash
git commit -am "test: the OpenCode render is pinned and opt-in"
```

### Task 3: Authorize aws-0, then record the real baseline and provider smoke matrix

**Files:**
- Create: `docs/runbooks/agent-factory/results-aws-0-<date>.md`
- Modify: `docs/runbooks/agent-factory/README.md`
- Test: `task links docs`

**Interfaces:**
- Produces: baseline and smoke evidence required by Tasks 4 and 5.

- [ ] **Step 1: Record authorization and start the existing platform path**

The live PR quotes the owner's explicit approval for aws-0 infrastructure and running costs, links the platform's existing rebuild/resume runbook used, and records who performed it. Do not add an automatic rebuild to this plan or CI. Confirm the Maku H digest before any task.

- [ ] **Step 2: Run labeled smoke tasks for every role and provider**

Use `harness:opencode` on new real tasks; these are `labeled`, not trial traffic. A `careful` task with the repository's test-contract option covers scoper, tester, implementer, judge, and reviewer. An internal investigation covers triager. `quick` and `standard` smoke tasks cover the other workflows. Run these provider cases separately and record the served model from the gateway:

| Case | Data class and model | Required evidence |
|---|---|---|
| GLM/Z.ai | public, `agent-default` | tools, effort, retry behavior, usage/cache fields, issue-to-PR result |
| Anthropic | internal, `tier-standard` | prompt cache markers, no public egress, restored internal session |
| Kimi | public, `kimi-frontier` | served model, tools, usage/cache fields |
| Mistral | public, `mistral-standard` and `mistral-light` | served model, tools, usage/cache fields |

Every case checks room completeness, approvals, checks, commits, final read, and no leaked secret/content. Suspend and resume one permission-waiting run and disrupt one implementer with a long-running shell: checkpoint, process cleanup, final room event, and revocation must all appear within their independent boxes.

- [ ] **Step 3: Record baseline measurements**

```markdown
Cluster aws-0 · Maku H (<digest>) · <start> to <end> UTC

| Reading | OpenHands | OpenCode |
|---|---|---|
| Final image bytes | | |
| Harness ready p50 / p95, runsc | | |
| Pod created → Ready p50 / p95 | | |
| Median end-to-end task duration | | |
| Cost per merged PR | | |
| Merge rate | | |
| Input / output / cache-read / cache-write tokens | | |
| Critical security, audit, recovery regressions | 0 required | 0 required |
```

Include per-role/provider smoke rows and every failure. No A/B trial starts if any parity or provider case fails.

- [ ] **Step 4: Run docs gates and commit**

Run: `task links docs`
Expected: exit 0.

```bash
git commit -am "docs(runbooks): OpenCode baseline and provider smoke on aws-0"
```

### Task 4: Enable only the 50/50 harness cohort on aws-0

**Files:**
- Create: `tooling/aws-0/agent-factory/resources/factory-harness-trial.yaml`
- Modify: the aws-0 participating `Repository` objects, `scripts/ci/tests/test-agent-harness-trial-off.py`
- Create: `scripts/ops/harness-trial-report.py`
- Test: `scripts/ci/tests/test-agent-harness-trial-off.py`, `task factory-config`, `task check`

**Interfaces:**
- Consumes: Task 3's passing smoke matrix.
- Produces: `evaluation: {controlPercent: 50, treatmentHarness: opencode}` only on aws-0; both arms use `careful` and identical model/effort/check settings.

- [ ] **Step 1: Extend the trial-off suite to enforce a single-variable trial**

```python
aws = render("tooling/aws-0/agent-factory/resources") + render("tooling/aws-0/agent-factory")
f = one(aws, "Factory", "agent-factory")
assert f["spec"]["evaluation"] == {"controlPercent": 50, "treatmentHarness": "opencode"}
assert "treatment" not in f["spec"]["evaluation"]
for repo in trial_repositories(aws):
    assert repo["spec"]["workflow"]["default"] == "careful"
    assert repo["spec"]["workflow"]["testFirst"] is True
    assert repo["spec"]["merge"]["contractCheck"]
    assert model_and_effort(repo) == model_and_effort(shipped_repository(repo))
assert not any("harness" in f["spec"].get("defaults", {}) for _ in [0])
```

The suite proves base and gcp-0 still have no trial and rejects any second trial or model/effort/workflow difference.

- [ ] **Step 2: Add the aws-0-only trial object and reporting script**

`factory-harness-trial.yaml` sets only `controlPercent` and `treatmentHarness`. The participating repositories set `workflow.default: careful` and `testFirst: true` in both arms and keep the required `merge.contractCheck` check configured. `harness-trial-report.py` reads real Task CRs and VictoriaMetrics and prints cohort/harness counts, merge rates, cost per merged PR, median end-to-end durations, token types, rescues, and exclusions. It rejects fewer than 30 ended tasks per arm and marks results `indecisive`, never passes them automatically.

- [ ] **Step 3: Run all gates and commit the opt-in trial**

Run: `task check`
Expected: exit 0; no default harness changes.

```bash
git commit -am "feat(aws-0): compare OpenCode and OpenHands on careful tasks"
```

### Task 5: Run 30 ended tasks per arm, extend once if needed, and record the verdict

**Files:**
- Modify: `docs/runbooks/agent-factory/results-aws-0-<date>.md`
- Delete after verdict: `tooling/aws-0/agent-factory/resources/factory-harness-trial.yaml` and participating repository trial overrides
- Test: `scripts/ops/harness-trial-report.py`, `scripts/ci/tests/test-agent-harness-trial-off.py`, `task check`

- [ ] **Step 1: Run normal new traffic without duplicate replay**

Allow new real tasks to arrive through the existing stable hash. Do not pin them and do not file a task twice. Scheduled, adopted, integration-only, and explicitly labeled work is excluded. Record any manual intervention.

- [ ] **Step 2: Evaluate after 30 ended tasks per arm**

Run: `python3 scripts/ops/harness-trial-report.py --context aws-0 --out docs/runbooks/agent-factory/results-aws-0-<date>.md`
Expected: real counts and query output. Extend once to 60 per arm if the result is inconclusive; do not evaluate a third sample.

- [ ] **Step 3: Apply the frozen decision rule**

```markdown
Verdict requirements:
- critical security/audit/recovery regressions = 0;
- merge-rate difference (OpenHands − OpenCode) <= 5 percentage points;
- cost-per-merged-PR regression <= 10%;
- cost-per-merged-PR improvement >= 15% OR median end-to-end duration improvement >= 15%.
```

A rescue appears as the original arm's failed outcome and a separate `rescue` outcome. It never counts as an OpenCode success or an OpenHands trial success. Mark verdict `passes`, `does not pass`, or `indecisive`; only `passes` authorizes Task 6.

- [ ] **Step 4: Remove the trial in the verdict PR and run gates**

Run: `task check`
Expected: exit 0; base, gcp-0, and aws-0 carry no harness treatment or repository trial override.

```bash
git commit -am "docs(runbooks): the OpenCode harness verdict on aws-0"
```

### Task 6: Cut over only after a passing verdict

**Files:**
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`defaults.harness: opencode`)
- Modify: `website/content/docs/status.md`, `website/content/docs/how-it-works/alternatives.md`, `website/content/docs/reference/harness.md`
- Test: `scripts/ci/tests/test-agent-harness-trial-off.py` (updated to admit the approved default while forbidding trials), `task check`

- [ ] **Step 1: Link the passing verdict and set only the default**

The PR links Task 5's real results and sets `defaults.harness: opencode` in base. It does not remove OpenHands, its image, adapter, selector, tests, or runbooks. The alternatives page now points to the verdict instead of only the design.

- [ ] **Step 2: Verify rollback and both selections**

Render one default run and assert OpenCode; render an explicit `harness:openhands` run and assert the unchanged OpenHands image/driver. Run `task check` and the Maku H real-server suite again on the release candidate.

- [ ] **Step 3: Commit and operate under the rollback trigger**

```bash
git commit -am "feat: default to OpenCode after the measured replacement gate"
```

A critical regression or sustained breach of the 5-point/10% quality-cost limits opens an immediate rollback PR restoring `defaults.harness: openhands`; no removal work proceeds during that PR.

### Task 7: Decide OpenHands removal only after the soak

**Files:**
- Create: `docs/runbooks/agent-factory/results-opencode-soak-<date>.md`
- Modify only after owner approval: Maku and ANR OpenHands image/adapter/selector/docs and their suites
- Test: `task check`, Maku `task check`, both remaining image suites

- [ ] **Step 1: Record at least 30 days and 30 ended default tasks**

Include rollback incidents, merge rate, cost per merged PR, median duration, provider failures, recovery events, and all rescue counts. Any critical regression or sustained threshold breach fails the soak and triggers rollback.

- [ ] **Step 2: Ask for a separate owner removal decision**

Present the soak evidence and the maintenance savings in a dedicated PR. Do not infer removal consent from the earlier opt-in, cutover, or this plan.

- [ ] **Step 3: Only after approval, remove OpenHands and prove every remaining path**

Remove the OpenHands adapter, image, config, selector fallback, and suites in Maku, then its ANR image/pins/docs. `spec.harness` may remain for forward compatibility, but `opencode` is the only admitted value and the default. Run both repositories' full gates and a final opt-in live smoke before closing the removal PR.

---

## Self-review

| Design requirement | Tasks |
|---|---|
| OpenHands remains default and no current implementation | 1–2 and the specification PR |
| Real composite and pinned image proof | 1–2 |
| Separate aws-0 authorization | 3 |
| Every role and provider family, recovery, tracing | 3 |
| Identical careful workflow/model/effort and 50/50 cohort | 4 |
| 30→60 ended tasks, frozen strict gate, trial removed | 5 |
| Default only after evidence, OpenHands rollback retained | 6 |
| 30 days + 30 ended default tasks before separate removal decision | 7 |
| Browser and runner language discussions remain separate | out of scope |
