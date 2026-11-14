# Merge policies review, adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ai-native-ref runs Maku's merge policy catalog and the diff-chosen gate, with the bindings reduced to this platform's exceptions, proven on aws-0.

**Architecture:** Two adoptions, each one Maku release behind its pin. Adopt N turns the catalog on and renames what release N deprecates; adopt N+1 deletes what the diff-chosen gate makes useless. Everything lives in `tooling/base/agent-factory/` (the aws-0 overlay inherits it through `tooling/aws-0/agent-factory/kustomization.yaml`); one gate suite under `scripts/ci/tests/` holds the shape.

**Tech Stack:** Kustomize and Flux manifests, the Maku `agent-factory` chart values, Python gate suites run by `task check`, Hugo site pages.

**Spec:** `docs/superpowers/specs/2026-11-14-merge-policies-review-design.md`. Maku side: `docs/superpowers/plans/2026-11-14-merge-policies-maku-plan.md` (its task numbers are cited as M1–M18).

## Global Constraints

- Work in a git worktree branched from `origin/main`; rebase onto a freshly fetched `origin/main` before every push.
- `task check` is the evidence; quote its output in the PR. On the owner's Mac five suites fail for environment reasons (see the project memory): then run `task links docs sources` by hand and say so.
- Conventional commits in English, no trailers.
- Validation is on **aws-0 only** (MR14). gcp-0 inherits the base and is not checked in this plan. A live check is recorded in `docs/runbooks/agent-factory/results-aws-0-<date>.md`.
- Every child keeps `sourceRef: {kind: OCIRepository, name: ai-native-ref}`; no host file is edited here. A host change (branch protection on cloud-native-ref) is a cloud-native-ref PR first.
- Site pages follow `docs/docs-style.md`; they state what is switched on here and link to Maku for fields and reasons.
- YAML structure is edited with `yq -i`; manifests are compared with `difft`.
- **Prerequisite, not in this plan:** `mergeDefaults` at `gateStatus: true, policyBot: false` (Maku `docs/v4-readiness.md` row 14). Task 2 refuses to start without it.

## Review Focus

1. **A Helm ownership clash.** Turning the catalog on while `MergePolicy/docs-links` still belongs to the `resources` Kustomization fails the HelmRelease. Task 2's suite asserts no catalog name is both rendered by the chart and listed in `resources/kustomization.yaml`.
2. **`deps-patch` loses its Flux monitor.** The catalog's `deps-patch` has no `monitor`, and a binding cannot add one. Task 2 keeps ANR's object and excludes the name from the catalog; the suite asserts the resolved `deps-patch` still carries `monitor.flux`.
3. **A policy above the guardrail defaults.** Any ANR policy with more than 10 files, 300 lines or 5 a day stops resolving at the pin bump. Task 1's suite checks every policy and binding against the three caps.
4. **gcp-0 drifts.** A change made only in an overlay leaves the other cluster on the old shape. Task 1's suite renders both overlays and asserts the factory resources are identical.
5. **A binding left behind for a deleted policy.** After Task 4 a binding naming `scripts` would be `MissingRef`. Task 4's suite asserts every binding names a policy that the chart or `resources/` provides.

---

### Task 1: adopt release N, catalog off

Needs: the Maku release carrying M1–M11.

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml` (the image tag at line 19, `policyManagement` at line 43, add `mergePolicies.catalog.enabled: false`)
- Modify: `tooling/base/agent-factory/resources/repository-{ai-native-ref,cloud-native-ref,runlore,runlore-kb}.yaml` (`merge.autoMergesPerDay` → `merge.maxPerDay`)
- Create: `scripts/ci/tests/test-agent-merge-policy-surface.py`
- Modify: `website/content/docs/status.md` (the pin)

**Interfaces:**
- Produces: the suite's helpers `policies()`, `repositories()` and `chart_catalog()` (the chart's rendered `MergePolicy` names), reused by Tasks 2 and 4.

- [ ] **Step 1: Write the failing suite.** `test-agent-merge-policy-surface.py` renders `tooling/aws-0/agent-factory` and `tooling/gcp-0/agent-factory` with `kustomize build` and asserts:
  - no `autoMergesPerDay`, no `policyManagement.{read,simulation,dualEvaluation,repositoryAuthority,approvalMemory,promotion}`, and `policyManagement.stage == "manage"` (today's four switches include `promotion`, whose stage is `manage`);
  - every `MergePolicy` and every binding has `maxPatchFiles <= 10`, `maxModifiedLines <= 300`, `maxPerDay <= 5` where set (Review Focus 3);
  - the two overlays' `Factory`, `Repository` and `MergePolicy` objects are equal (Review Focus 4).
- [ ] **Step 2: Run** `python3 scripts/ci/tests/test-agent-merge-policy-surface.py` from `.composite/` after `task host-profile` — FAIL on the first assertion.
- [ ] **Step 3: Edit** the four repository files with `yq -i '.spec.merge.maxPerDay = .spec.merge.autoMergesPerDay | del(.spec.merge.autoMergesPerDay)'`, the values ConfigMap by hand (it is a string block), and bump the pin and its digest.
- [ ] **Step 4: Run** `task check` — the new suite passes; `test-agent-factory-pins.py` passes on the new tag.
- [ ] **Step 5: Commit** `chore(deps): Maku <N>: policy stage, merge.maxPerDay, the catalog off`

`manage` also switches on approval memory, which is off today. No policy here declares `requiresApproval`, so nothing changes; the PR body says so.

### Task 2: turn the catalog on

Needs: Task 1 live on aws-0, and the prerequisite flip.

**Files:**
- Delete: `tooling/base/agent-factory/resources/mergepolicy-docs-links.yaml`, `mergepolicy-revert.yaml`
- Modify: `tooling/base/agent-factory/resources/kustomization.yaml`, `mergepolicy-docs.yaml`, `mergepolicy-deps-patch.yaml`, `helm-values-configmap.yaml`
- Modify: `scripts/ci/tests/test-agent-merge-policy-surface.py`, `scripts/ci/tests/test-agent-merge-gate-parity.py`

**Interfaces:**
- Consumes: `chart_catalog()` from Task 1.
- Produces: values `mergePolicies.catalog: {enabled: true, exclude: [docs, deps-patch]}`.

- [ ] **Step 1: Extend the suite** (fails first):
  - it refuses to pass unless `mergeDefaults.gateStatus` is `true` and `policyBot` is `false`;
  - no name is both in `chart_catalog()` minus `exclude` and in `resources/kustomization.yaml` (Review Focus 1);
  - `MergePolicy/deps-patch` has `monitor.flux` and no `requires` (Review Focus 2);
  - `MergePolicy/docs` has `allowedFiles: ['^.+\.mdx?$']`, `maxPatchFiles: 5`, `maxModifiedLines: 100`, `maxPerDay: 2`, `evidence: standard`, and still `checks: true`.
- [ ] **Step 2: Rewrite `test-agent-merge-gate-parity.py`** to the new shape: it no longer reads `.policy.yml`. It asserts that every binding in mode `live` or `shadow`, resolved with its policy, has `allowedFiles` or a `diffShape` (or is `docs-links` or `revert`), and that a live binding's policy is not `evidence: low` without a shape or an oracle. Keep the file name: `run-tests.sh` and the docs cite it.
- [ ] **Step 3: Run** both suites — FAIL.
- [ ] **Step 4: Edit.** Delete the two objects and their kustomization lines. In `mergepolicy-docs.yaml` copy the catalog's fields beside `checks: true`. In `mergepolicy-deps-patch.yaml` drop `requires`, add `evidence: low`, keep the host's `protectedFiles` and the monitor. Set the values.
- [ ] **Step 5: Run** `task check`. Then render `tooling/aws-0/agent-factory` with `kustomize build` here and in a checkout of `origin/main`, and compare the two files with `difft`: only the objects named above differ.
- [ ] **Step 6: Commit** `feat(agent-factory): the merge policy catalog, with docs and deps-patch kept as this platform's`

### Task 3: live check on aws-0, release N

**Files:**
- Create: `docs/runbooks/agent-factory/results-aws-0-<date>.md`
- Modify: `docs/runbooks/agent-factory/README.md` (one index line)

- [ ] **Step 1: Verify the context:** `kubectx -c` prints the aws-0 context.
- [ ] **Step 2: Read the objects:** `kubectl get mergepolicy -n agent-system -o json | jq '[.items[] | {name: .metadata.name, catalog: .metadata.labels["maku.ogenki.io/catalog"], deprecated: ([.status.conditions[]? | select(.type=="Deprecated")] | length)}]'`. Expected: `docs-links` and `revert` with `catalog: "true"`; the `Deprecated` condition only on policies that still carry workflow fields.
- [ ] **Step 3: Read the repositories:** `kubectl get repository -n agent-system -o json | jq '[.items[] | {name: .metadata.name, ready: (.status.conditions[] | select(.type=="Ready").status)}]'` — every `ready` is `"True"`.
- [ ] **Step 4: One task per case**, on `Smana/ai-native-ref`, each recorded with its issue, pull request and decision line:
  - a `class:docs-links` task: `decision=shadow:shadow_would_arm` with no binding for `docs-links` in the Repository;
  - the same with `factory/hold` on the pull request: `human`, `held`;
  - a policy at `evidence: low`: the Evidence page shows a minimum of 5.
- [ ] **Step 5: Record** the three decision lines and the two `jq` outputs in the results file, with the Maku tag and the commit of this repository.
- [ ] **Step 6: Commit** `docs(runbooks): the catalog and factory/hold on aws-0`

### Task 4: adopt release N+1

Needs: the Maku release carrying M12–M18, and the workflows adoption plan's N+1 step in the same PR or merged first (it sets `Repository.spec.workflow.default` and the schedules' `workflow`).

**Files:**
- Delete: `tooling/base/agent-factory/resources/mergepolicy-{dashboards,scripts,tests,review,docs}.yaml`
- Modify: `resources/kustomization.yaml`, the four `repository-*.yaml`, `helm-values-configmap.yaml` (`exclude: [deps-patch]`, the pin)
- Modify: `scripts/ci/tests/test-agent-merge-policy-surface.py`

- [ ] **Step 1: Extend the suite** (fails first):
  - no binding has `mode: "off"`, and none is named `review`, `scripts`, `tests` or `dashboards`;
  - every binding names a policy from `chart_catalog()` minus `exclude`, or from `resources/` (Review Focus 5);
  - no `MergePolicy` carries `harness`, `harnessAllowed`, `escalation`, `testFirst`, `checks` or `requires`;
  - `Repository/ai-native-ref` binds `docs` as `{mode: shadow, allowedFiles: ['^website/content/.+\.md$'], maxModifiedLines: 60}` (the design's first example);
  - `Repository/cloud-native-ref` has exactly the five bindings of the design's "after" block, plus `deps-minor` and `kb-entries` where they are bound today.
- [ ] **Step 2: Run** the suite — FAIL.
- [ ] **Step 3: Edit.** For each repository: `yq -i 'del(.spec.mergePolicies[] | select(.mode == "off"))'`. Delete the five objects; `docs` now comes from the catalog. Add the `docs` binding to ai-native-ref.
- [ ] **Step 4: Run** `task check`.
- [ ] **Step 5: Commit** `feat(agent-factory)!: bindings are this platform's exceptions; the gate reads the diff`

### Task 5: live check on aws-0, release N+1

**Files:** Create `docs/runbooks/agent-factory/results-aws-0-<date>.md`; modify the runbooks `README.md`.

- [ ] **Step 1:** `kubectx -c` prints the aws-0 context.
- [ ] **Step 2: Four tasks**, each recorded with its decision line:
  - an **unlabelled** task fixing one link under `website/content/`: the line carries `class=docs-links` and `considered=`;
  - an unlabelled prose fix under `website/content/` with the `standard` workflow: `class=docs decision=shadow:shadow_would_arm`;
  - the same with the `quick` workflow: `human`, `reviewer_verdict_missing`;
  - a task touching `scripts/`: `human`, `no_policy_matched`.
- [ ] **Step 3: The tally:** `scripts/shadow-merge-tally.sh` from the Maku tag, on `Smana/ai-native-ref`, prints a `docs` row with the two shadow decisions.
- [ ] **Step 4: Record and commit** `docs(runbooks): the diff-chosen gate on aws-0`

### Task 6: the site says what runs here

**Files:**
- Modify: `website/content/docs/use/guide/merge-policies.md`, `website/content/docs/how-it-works/merge-gate.md`, `website/content/docs/operate/auto-merge-safety.md`, `website/content/docs/reference/gate-reasons.md`, `website/content/docs/status.md`

The docs review plan owns reducing and reorganising these pages. This task only keeps them true, in the PR of Task 2 and again in the PR of Task 4.

- [ ] **Step 1 (with Task 2):** replace the removed `classes:` and `.policy.yml` steps with the bindings in `tooling/base/agent-factory/resources/`; state that the catalog evaluates in shadow on every repository; link to Maku's `docs/merge-policies.md` at the pinned tag for fields.
- [ ] **Step 2 (with Task 4):** modes read `live`, `shadow`, `disabled`; `gate-reasons.md` gains `held`, `reviewer_verdict_missing`, `no_policy_matched` and drops `class_unarmed`; `merge-gate.md` gets one mermaid diagram of selection, copied from the design.
- [ ] **Step 3: Run** `task links docs` — exit 0.
- [ ] **Step 4: Commit** with the task it accompanies.

## Self-review notes

- The spec's ANR step 2 deletes `deps-patch` and moves its host paths to the binding. That loses the policy's `monitor`, which a binding cannot carry, so Task 2 keeps the object and excludes the name from the catalog. Raised in the Maku plan's Task 10 (`catalog.exclude`).
- `policyManagement.stage` is `manage`, the highest stage today's four switches cover.
