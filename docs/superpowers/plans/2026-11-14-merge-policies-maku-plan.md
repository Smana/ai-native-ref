# Merge policies review, Maku Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The merge gate picks a pull request's policy from its diff, every repository evaluates a shipped catalog in shadow with no binding, and the policy surface is bounded and smaller.

**Architecture:** Release N is additive: new fields, defaults, a catalog and `Deprecated` conditions, with the gate still deciding on the intake class. Release N+1 rewires `DecideArm` to evaluate every candidate policy and removes the deprecated fields. Policy resolution stays in `internal/factory/config` (`resolve`, `finish`), selection is a new file beside `arm.go`, and the catalog is a chart template.

**Tech Stack:** Go (controller-runtime, kubebuilder markers, envtest), Helm (`charts/agent-factory`), shell test suites under `scripts/` and `charts/*/tests/`.

**Spec:** `docs/superpowers/specs/2026-11-14-merge-policies-review-design.md` in ai-native-ref (branch `docs/review-merge-policies`). Copy it to Maku's `docs/superpowers/specs/` in the first PR.

## Global Constraints

- Executed in the Maku repository, in a worktree from `origin/main`. Paths below are Maku's.
- `task check` exits 0 before every commit and push; lint only through `task lint`.
- Conventional commits in English, one concern per commit, no trailers. Squash-merge: the PR title is itself a conventional commit.
- After any change to `api/` or `internal/factory/config` types: `task crd:gen`, and commit `config/crd`, `api` and the chart CRD copies (`crd:check`).
- Every `.go` file opens with `// SPDX-License-Identifier: Apache-2.0`; exported symbols carry doc comments.
- Release N refuses nothing that v0.47.0 accepts, except an unbounded evaluated policy (MR6). Release N+1 refuses every field release N marked `Deprecated` (MR13). Both land before v4.0.0.
- Modes are `live`, `shadow`, `disabled`. Evidence is `low` (5) or `standard` (20). Guardrail defaults: `protectedFiles: ['^\.github/', '^\.policy\.yml$', '^CODEOWNERS$']`, `maxPatchFiles: 10`, `maxModifiedLines: 300`, `maxPerDay: 5`.
- Decision strings: `Merged automatically by policy <name>` and `Waits for a human: <reason>`.
- Workflow fields (`harness`, `harnessAllowed`, `escalation`, `testFirst`, `checks`) get their new home from `2026-11-14-workflows-review-design.md`; PR E here only removes them from `MergePolicy` and must merge in the same release as that design's stage B.
- `docs/merge-policies.md` and `docs/upgrading.md` change in the PR that changes the behaviour; `hack/docs.sh` must pass.

## Review Focus

1. **A platform policy above the new guardrail defaults.** A v0.47.0 policy with `maxModifiedLines: 400` and no guardrails set must not vanish silently: it resolves with `GuardrailMismatch` and the Repository's status says which cap. Pinned in Task 5.
2. **A catalog name the platform already owns.** Installing with `mergePolicies.catalog.enabled: true` over an existing `MergePolicy/docs` must fail at `helm template`-time validation with the object's name, not at apply. Pinned in Task 10.
3. **Two live policies hold and the strictest is capped.** The pull request goes to a human with `auto_merge_cap`; the looser policy never merges it. Pinned in Task 12.
4. **`quick` workflow, path-bound policy.** No reviewer role and no shape: `reviewer_verdict_missing`, never `arm`. Pinned in Task 13.
5. **A diff no policy admits, with a stale `class:` label.** `no_policy_matched`, no `class_mismatch`, and no shadow count for the labelled class. Pinned in Task 14.

---

## Release N (additive)

### PR A: `feat(factory): policy evidence levels, the bound rule and guardrail defaults`

### Task 1: `evidence` on a policy

**Files:**
- Modify: `internal/factory/config/classes.go` (the `Class` struct, `validateClass`)
- Modify: `internal/factory/evidence/service.go:453,479`
- Test: `internal/factory/config/classes_test.go`, `internal/factory/evidence/service_test.go`

**Interfaces:**
- Produces: `Class.Evidence string` (json `evidence`, enum `low;standard`); `func (cl Class) MinClean(name string) int` returning 5 for `low`, else 20; consts `EvidenceLow = "low"`, `EvidenceStandard = "standard"`, `MinCleanLow = 5`.

- [ ] **Step 1: Write the failing tests**

```go
func TestEvidenceLevels(t *testing.T) {
	if got := (Class{Evidence: "low", DiffShape: "links-only"}).MinClean("x"); got != 5 { t.Fatalf("low = %d", got) }
	if got := (Class{}).MinClean("x"); got != 20 { t.Fatalf("default = %d", got) }
	if got := (Class{Evidence: "low"}).MinClean("docs-links"); got != 5 { t.Fatalf("built-in shape = %d", got) }
}
func TestEvidenceLowNeedsShapeOrOracle(t *testing.T) {
	var got []string
	validateClass("docs", Class{Evidence: "low", AllowedFiles: []string{`^.+\.md$`}}, func(f string, a ...any) { got = append(got, fmt.Sprintf(f, a...)) })
	if len(got) != 1 || !strings.Contains(got[0], "evidence: low needs a diffShape or an oracle") { t.Fatalf("%v", got) }
}
```

In `service_test.go`, `TestReportMinimumIsThePolicys`: a class with `Evidence: "low"` reports `Minimum == 5`; `mergeGuardrails.minPromotionEvidence: 40` is ignored.

- [ ] **Step 2: Run** `go test ./internal/factory/config ./internal/factory/evidence -run 'Evidence|ReportMinimum'` — FAIL, `Evidence` undefined.
- [ ] **Step 3: Implement.** `MinClean` reads `BuiltInShape(name)` so `docs-links` and `revert` count as shaped. Both call sites in `service.go` use the class's `MinClean`. `MergeGuardrails.MinPromotion` stays until Task 16.
- [ ] **Step 4: Run** the same command — PASS. `task crd:gen`.
- [ ] **Step 5: Commit** `feat(factory): evidence low or standard on a merge policy`

### Task 2: the bound rule on the resolved policy

**Files:**
- Modify: `internal/factory/config/binding.go` (`finish`, the reasons), `internal/factory/config/config.go:2287-2291`
- Test: `internal/factory/config/bound_test.go`

**Interfaces:**
- Produces: `ReasonUnbounded = "Unbounded"`; `func (cl Class) Bounded(name string) bool` (true with `AllowedFiles`, a `DiffShape`, or a `BuiltInShape(name)`).

- [ ] **Step 1: Write the failing test** `TestUnboundedIsRefusedInShadowAndLive`: table over `{mode, policy, binding, wantReason}`:
  - shadow, `PolicySpec{}`, no parameters → `Unbounded`;
  - live, `PolicySpec{}`, binding `allowedFiles` → resolves;
  - shadow, `Class{DiffShape: "semver-patch"}` → resolves;
  - shadow, name `docs-links`, `PolicySpec{}` → resolves;
  - `off`, `PolicySpec{}` → resolves (not evaluated).
- [ ] **Step 2: Run** `go test ./internal/factory/config -run Unbounded` — FAIL.
- [ ] **Step 3: Implement** in `finish`, replacing the `!m.UsesPolicyBot() && cl.Live` rule: `(cl.Live || cl.Shadow) && !cl.Bounded(name)` → `ReasonUnbounded`, message `class <name>: an evaluated policy needs allowedFiles or a diffShape`. Remove the duplicate in `config.go`.
- [ ] **Step 4: Run** `go test ./internal/factory/config ./internal/factory/resources` — PASS (fix fixtures that bind an empty policy in shadow).
- [ ] **Step 5: Commit** `feat(factory)!: an evaluated merge policy is bounded by paths or a shape`

### Task 3: a binding narrows `allowedFiles`

**Files:**
- Modify: `internal/factory/config/classes.go` (`Class`), `internal/factory/config/binding.go` (`resolve`), `internal/factory/filefence/filefence.go` (`AllowedFiles`, `Refusal`)
- Test: `internal/factory/config/binding_test.go`, `internal/factory/filefence/filefence_test.go`

**Interfaces:**
- Produces: `Class.NarrowedFiles []string` (json `narrowedFiles`, set only by `resolve`, refused on a `MergePolicy` by `policyShapeProblems`). `filefence.AllowedFiles` returns `file_not_allowed` unless a path matches `AllowedFiles` and, when set, `NarrowedFiles`.

- [ ] **Step 1: Write the failing tests** `TestBindingNarrowsAllowedFiles` (policy `^.+\.mdx?$`, binding `^website/content/.+\.md$`: resolves; `AllowedFiles` is the policy's, `NarrowedFiles` the binding's) and `TestNarrowedFilesBothMustAdmit` (`docs/x.md` → `file_not_allowed`; `website/content/a.md` → `""`).
- [ ] **Step 2: Run** `go test ./internal/factory/config ./internal/factory/filefence -run Narrow` — FAIL with `ParameterTwice`.
- [ ] **Step 3: Implement.** Drop `allowedFiles` from the fill-once table; the other three fields keep `ParameterTwice`.
- [ ] **Step 4: Run** — PASS. `task crd:gen`.
- [ ] **Step 5: Commit** `feat(factory): a binding's allowedFiles narrows its policy's`

### Task 4: `mode: disabled`

**Files:**
- Modify: `internal/factory/config/binding.go` (`ModeDisabled`, the enum marker, `resolve`)
- Test: `internal/factory/config/binding_test.go`

**Interfaces:**
- Produces: `ModeDisabled = "disabled"`; enum `live;shadow;disabled;off`; `resolve` treats `off` as `disabled`.

- [ ] **Step 1: Write the failing test** `TestModeDisabled`: `disabled` and `off` both resolve to a class with `Live == false && Shadow == false`; `paused` is refused with `mode "paused" is live, shadow or disabled`.
- [ ] **Step 2–4:** run `go test ./internal/factory/config -run ModeDisabled`, implement, run, `task crd:gen`.
- [ ] **Step 5: Commit** `feat(factory): mode disabled on a binding`

### Task 5: guardrail defaults

**Files:**
- Modify: `internal/factory/config/mergepolicy.go` (`MergeGuardrails`), the place `PolicyContext.Guardrails` is built: `internal/factory/resources/bindings.go` (`policyContext`)
- Test: `internal/factory/config/mergepolicy_test.go`, `internal/factory/resources/bindings_test.go`

**Interfaces:**
- Produces: `func (g MergeGuardrails) WithDefaults() MergeGuardrails`: each zero cap takes its default; `ProtectedFiles` is the default three, then the platform's, de-duplicated.

- [ ] **Step 1: Write the failing tests** `TestGuardrailDefaults` (zero value → the four spec values; `MaxPatchFiles: 4` stays 4; a platform path is appended) and, for Review Focus 1, `TestPolicyAboveDefaultGuardrailIsNamed` in `bindings_test.go`: a policy with `maxModifiedLines: 400`, no guardrails set, resolves with reason `GuardrailMismatch` and a message containing `maxModifiedLines 400` and `300`.
- [ ] **Step 2: Run** `go test ./internal/factory/config ./internal/factory/resources -run Guardrail` — FAIL.
- [ ] **Step 3: Implement**; `policyContext` calls `WithDefaults()`. `ValidatePolicy` keeps its empty guardrails.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(factory)!: merge guardrails ship with defaults`; note the three caps in `docs/upgrading.md`.

### PR B: `feat(factory): one policy-management stage, merge.maxPerDay, factory/hold`

### Task 6: `policyManagement.stage`

**Files:**
- Modify: `internal/factory/config/mergepolicy.go` (`PolicyManagement`, `Validate`)
- Modify call sites: `internal/app/broker.go:780`, `internal/app/factory.go:517-524,590,749`, `internal/app/maku_policy.go:83`, `internal/config/config.go:1183-1184`, `internal/factory/api/evidence.go:39`, `internal/factory/config/config.go:552`, `internal/factory/config/mergepolicy.go:225,236`, `internal/factory/policyview/preview.go:122`, `internal/factory/reconciler/dual.go:62`, `internal/factory/reconciler/grants.go:30`
- Test: `internal/factory/config/mergepolicy_test.go`

**Interfaces:**
- Produces: `PolicyManagement.Stage string` (`read|simulate|manage`); `func (pm PolicyManagement) EffectiveStage() string`; `Reads()`, `Simulates()`, `Manages() bool`. No call site reads a switch field directly after this task.

- [ ] **Step 1: Write the failing test** `TestEffectiveStage`: `{}` → `manage`; `{Stage: "read"}` → `read`; `{Read: true}` → `read`; `{Read: true, Simulation: true, DualEvaluation: true}` → `simulate`; `{Read: true, Promotion: true}` → `manage`; `{Stage: "read", Promotion: true}` → a `Validate` problem `stage and the six switches are not set together`.
- [ ] **Step 2: Run** `go test ./internal/factory/config -run EffectiveStage` — FAIL.
- [ ] **Step 3: Implement.** `Reads()` is every stage; `Simulates()` is `simulate` and `manage`; `Manages()` is `manage`. Map: `Read`→`Reads`, `Simulation` and `DualEvaluation`→`Simulates`, `Promotion`, `ApprovalMemory`, `RepositoryAuthority`→`Manages`. In `internal/config/config.go:1184`, a broker at stage `manage` with no `FactoryURL` serves no promotion pages instead of failing to start.
- [ ] **Step 4: Run** `go test ./internal/... -run 'Policy|Stage|Dual|Grant|Evidence'` — PASS.
- [ ] **Step 5: Commit** `feat(factory): policyManagement.stage replaces the six switches`

### Task 7: `merge.maxPerDay`

**Files:** Modify `internal/factory/config/config.go:711,2312`, `internal/factory/reconciler/arm.go:227`. Test: `internal/factory/config/mergedefaults_test.go`.

**Interfaces:** Produces `Merge.MaxPerDay int` (json `maxPerDay`) and `func (m Merge) PerDay() int` (`MaxPerDay`, else `AutoMergesPerDay`; both set and different is a validation problem).

- [ ] **Step 1: Test** `TestMergePerDay`: `{MaxPerDay: 2}` → 2; `{AutoMergesPerDay: 3}` → 3; both `2` and `3` → problem `merge.maxPerDay and merge.autoMergesPerDay differ`.
- [ ] **Step 2–4:** run `go test ./internal/factory/config -run MergePerDay`, implement, run, `task crd:gen`.
- [ ] **Step 5: Commit** `feat(factory): merge.maxPerDay, the name a policy's cap already has`

### Task 8: `factory/hold`

**Files:**
- Modify: `internal/factory/forge/forge.go:185` (`PR`: add `Labels []string` if the read does not already carry them, and the query that fills it), `internal/factory/reconciler/arm.go` (`baseChecks`), `internal/factory/narrate/narrate.go:308-330`, `internal/factory/policyview/timeline.go:67`
- Test: `internal/factory/reconciler/arm_test.go`, `internal/factory/narrate/narrate_test.go`

**Interfaces:** Produces `const LabelHold = "factory/hold"` in `internal/factory/reconciler`; reason `held`, narrated `a maintainer put this pull request on hold (factory/hold)`.

- [ ] **Step 1: Test** `TestHoldLabelStopsEveryPath`: a pull request that would `arm` (class conditions) and one that would arm on `maintainer_approved` both return `Verdict: "human", Reason: "held"` with the label; without it the verdicts are unchanged; a shadow class with the label records no `shadow_would_arm`.
- [ ] **Step 2: Run** `go test ./internal/factory/reconciler -run HoldLabel` — FAIL.
- [ ] **Step 3: Implement** as the last base check, before the author mode.
- [ ] **Step 4: Run** `go test ./internal/factory/reconciler ./internal/factory/narrate ./internal/factory/policyview` — PASS.
- [ ] **Step 5: Commit** `feat(factory): factory/hold keeps a pull request from auto-merging`

### Task 9: the `Deprecated` condition

**Files:**
- Create: `internal/factory/config/deprecated.go`
- Modify: `internal/factory/statuswriter/desired.go:42-45` and where it builds the conditions of `Factory`, `Repository` and `MergePolicy`
- Test: `internal/factory/config/deprecated_test.go`, the statuswriter's desired-status test

**Interfaces:** Produces `ConditionDeprecated = "Deprecated"`; `func PolicyDeprecations(p PolicySpec) []string`, `func RepositoryDeprecations(r *Repository) []string`, `func FactoryDeprecations(c *Config) []string`, each returning field paths in a fixed order.

- [ ] **Step 1: Test** `TestDeprecations`: a policy with `harness`, `checks` and `requires` → `["checks", "harness", "requires"]`; a repository with a binding `mode: off` and `merge.autoMergesPerDay` → `["merge.autoMergesPerDay", "mergePolicies[docs].mode: off"]`; a config with `policyManagement.read` and `mergeGuardrails.minPromotionEvidence` → both paths; clean objects → nil.
- [ ] **Step 2: Run** `go test ./internal/factory/config -run Deprecations` — FAIL.
- [ ] **Step 3: Implement.** The condition is `True` with reason `RemovedNextRelease` and the joined paths as the message; absent when the list is empty. It never affects `Ready`.
- [ ] **Step 4: Run** `go test ./internal/factory/config ./internal/factory/statuswriter` — PASS.
- [ ] **Step 5: Commit** `feat(factory): a Deprecated condition names the fields the next release refuses`

### PR C: `feat(charts): a catalog of four merge policies, evaluated in shadow`

### Task 10: the catalog in the chart

**Files:**
- Create: `charts/agent-factory/templates/merge-policies-catalog.yaml`
- Modify: `charts/agent-factory/values.yaml`, `values.schema.json`, `values-demo.yaml`, `charts/agent-factory/tests/render.sh`, `tests/golden/*.yaml`, `charts/agent-factory/README.md`
- Test: `charts/agent-factory/tests/render.sh`

**Interfaces:** Produces values `mergePolicies.catalog.enabled` (default `true`) and `mergePolicies.catalog.exclude` (list of names, default `[]`); four `MergePolicy` objects labelled `maku.ogenki.io/catalog: "true"`, with exactly the specs in the design's "The catalog" section.

- [ ] **Step 1: Extend `render.sh`** with three assertions: the default render holds four `MergePolicy` objects with the label; `exclude: [docs]` renders three; each rendered spec, piped through `yq`, equals the design's YAML (keep the four expected specs in `tests/golden/catalog.yaml`). For Review Focus 2, add to `charts/agent-factory/templates/_helpers.tpl` a `lookup`-based check and assert in `tests/install.sh` (k3d) that installing over an existing unlabelled `MergePolicy/docs` fails with `MergePolicy docs exists and is not the catalog's: add it to mergePolicies.catalog.exclude`.
- [ ] **Step 2: Run** `task chart:check` — FAIL.
- [ ] **Step 3: Implement** the template and values; regenerate goldens with `tests/normalize.sh`.
- [ ] **Step 4: Run** `task chart:check` and `task install:schemas` — PASS.
- [ ] **Step 5: Commit** `feat(charts): the merge policy catalog`

### Task 11: unbound catalog policies are evaluated in shadow; the drill is per repository

**Files:**
- Modify: `internal/factory/resources/bindings.go` (`resolveBindings`), `internal/factory/resources/manifests.go` (reading the label), `internal/factory/evidence/evidence.go` (`Evaluate`), `internal/factory/evidence/service.go`
- Test: `internal/factory/resources/bindings_test.go`, `internal/factory/evidence/evidence_test.go`

**Interfaces:**
- Consumes: `ModeDisabled` (Task 4), `ReasonUnbounded` (Task 2).
- Produces: `resolveBindings` adds `Binding{Name: n, Mode: ModeShadow}` for each catalog-labelled policy the repository does not bind; `Evaluate(sh ShadowTally, out OutcomeTally, reverts []Revert, repo string, minimum int, repoDrilled bool) Evidence`, where `repoDrilled` is true when any merged `factory/drill` revert exists in the repository.

- [ ] **Step 1: Tests.** `TestCatalogPolicyIsShadowWithoutABinding`: a Repository with no `mergePolicies` and a labelled `docs` → class `docs` resolved with `Shadow == true`; with a binding `mode: disabled` → neither; an unlabelled unbound policy → not resolved. `TestDrillIsPerRepository`: a class with no drilled pull request of its own and `repoDrilled == true` has no `BlockNoDrill`.
- [ ] **Step 2: Run** `go test ./internal/factory/resources ./internal/factory/evidence -run 'Catalog|DrillIsPer'` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `task check` — exit 0.
- [ ] **Step 5: Commit** `feat(factory): catalog policies in shadow with no binding; one drill per repository`. Update `docs/merge-policies.md` ("Start here", promotion) in this PR.

---

## Release N+1 (with the workflows design's stage B)

### PR D: `feat(factory)!: the gate picks the policy from the diff`

### Task 12: candidates and the strictest live policy

**Files:**
- Create: `internal/factory/reconciler/select.go`
- Modify: `internal/factory/reconciler/arm.go` (`DecideArm`, `decide`, `gateOf`)
- Test: `internal/factory/reconciler/select_test.go`

**Interfaces:**
- Produces:
  - `type held struct { Name string; Class config.Class; Rows decision.Rows; Reason string }` (`Reason == ""` means it holds);
  - `func candidates(rc *config.Repository, t *v1alpha1.Task) []string`: every class of `rc.Classes` that is live or shadow, not adopted and without an oracle, in name order; for a task with `Spec.Findings` or an adopted pull request, only `t.Spec.PredictedClass`;
  - `func stricter(a, b held) bool`: a `DiffShape` (or built-in shape) first; then lower `MaxModifiedLines`; then lower `MaxPatchFiles`; 0 sorts last in both; then `Name`;
  - `DecideArm` returns the strictest live `held`'s decision, with `ArmDecision.Shadows []string` naming every shadow policy that holds.

- [ ] **Step 1: Write the failing tests**
  - `TestStricterOrder`: `docs-links` (shape, 20 lines) before `docs` (no shape, 100 lines); two shaped policies order by lines; equal caps order by name; a 0 cap sorts after any positive cap.
  - `TestNoFallThrough` (Review Focus 3): live `docs-links` and live `docs` both hold, `docs-links` has `ClassArmedToday >= MaxPerDay` → `human`, `auto_merge_cap`, `Matched: "docs-links"`. Same with the breaker open → `class_paused`.
  - `TestOracleAndAdoptedKeepOnePolicy`: a task with findings evaluates `PredictedClass` only, whatever else would hold.
  - `TestApproveToMergeStillFirst`: an approved head arms with `maintainer_approved` before any candidate is read.
- [ ] **Step 2: Run** `go test ./internal/factory/reconciler -run 'Stricter|NoFallThrough|OracleAndAdopted|ApproveToMergeStillFirst'` — FAIL.
- [ ] **Step 3: Implement.** `decide` keeps its base, author and approval rows; the part from `class_unarmed` down runs once per candidate. Per-policy `ClassArmedToday` comes from the ledger keyed by policy name (extend `ArmInputs` with `ArmedByClass map[string]int`).
- [ ] **Step 4: Run** `go test ./internal/factory/reconciler` — PASS; update fixtures that relied on `class_unarmed`.
- [ ] **Step 5: Commit** `feat(factory)!: the merge gate evaluates every policy of the repository`

### Task 13: a reviewer's verdict where no shape checks the diff (MR12)

**Files:** Modify `internal/factory/reconciler/arm.go:548` (`agentEvidence`), `internal/factory/narrate/narrate.go`. Test: `internal/factory/reconciler/arm_test.go`.

**Interfaces:** Produces `agentEvidence(in ArmInputs, cfg *config.Config, name string, cl config.Class) string`; reason `reviewer_verdict_missing`, narrated `no reviewer read this change, and its policy has no shape to check it`.

- [ ] **Step 1: Test** `TestVerdictRequiredWithoutShape` (Review Focus 4), table: template without a reviewer × {`docs` path-bound → `reviewer_verdict_missing`; `docs-links` → `""`; a policy with `Oracle` → `""`}; template with a reviewer and `Status.Verdict != "approve"` → `no_approving_verdict` for all three, as today.
- [ ] **Step 2–4:** run `go test ./internal/factory/reconciler -run VerdictRequired`, implement, run.
- [ ] **Step 5: Commit** `feat(factory)!: a policy with no shape or oracle needs a reviewer's verdict`

### Task 14: shadow evidence for every holding policy, `considered=`, `no_policy_matched`

**Files:**
- Modify: `internal/factory/decision/decision.go` (`Rows`, `Marker`), `internal/factory/decision/recorder.go`, `internal/factory/reconciler/merge.go` (where the decision comment and `Recorder.Record` are written), `internal/factory/reconciler/gate.go:81`, `internal/factory/narrate/narrate.go`, `internal/factory/policyview/timeline.go:72`, `scripts/shadow-merge-tally.sh`
- Test: `internal/factory/decision/decision_test.go`, `internal/factory/reconciler/merge_gate_test.go`, `scripts/shadow-merge-tally_test.sh`

**Interfaces:**
- Consumes: `ArmDecision.Shadows`, `held` (Task 12).
- Produces: `Rows.Considered string`, printed as ` considered=<policy>:<reason>,…` before `reviewer=`, omitted when empty; one marker line per shadow policy that holds, each `class=<policy> decision=shadow:shadow_would_arm`, after the primary line; reason `no_policy_matched` replacing `class_unarmed` and, on agent pull requests, `class_mismatch`.

- [ ] **Step 1: Tests.** `TestMarkerConsidered`: `Rows{Considered: "docs:file_not_allowed,alert-rules:patch_too_large"}` prints that token before `reviewer=`. `TestShadowRecordedForEachHoldingPolicy`: live `docs-links` merges and shadow `docs` holds → the comment has two marker lines and `Recorder.Latest` has both. `TestNoPolicyMatched` (Review Focus 5): a task labelled `class:docs` whose diff touches `main.go` → `no_policy_matched`, `Matched: ""`, no marker line with `class=docs decision=shadow`. In `shadow-merge-tally_test.sh`: a comment with two marker lines counts once per class.
- [ ] **Step 2: Run** `go test ./internal/factory/decision ./internal/factory/reconciler -run 'Considered|ShadowRecorded|NoPolicyMatched'` and `task scripts` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `task check` — exit 0.
- [ ] **Step 5: Commit** `feat(factory)!: shadow evidence for every policy that holds`

### Task 15: the decision names its policy

**Files:** Modify `internal/summary/policy.go:49` (`PolicyDecision`), the `envelope.TaskFacts` policy struct, the reconciler code that fills it. Test: `internal/summary/policy_test.go`.

**Interfaces:** Produces `envelope` policy field `Name string`; `PolicyDecision` returns `Merged automatically by policy <name>` for `MergedHow == "class"`, `Waits for a human: <reason text>` for an `AwaitingHuman` hand-off, and keeps the approval sentence. Before a head is reported it returns `""`.

- [ ] **Step 1: Test** `TestPolicyDecisionNamesThePolicy`: the three cases above with `Name: "docs-links"` and reason `auto_merge_cap`; no pull request → `""`.
- [ ] **Step 2–4:** run `go test ./internal/summary -run PolicyDecisionNames`, implement, run `task check` (the UI bundle and golden narrations change: `task ui:check`).
- [ ] **Step 5: Commit** `feat(factory): the merge decision names its policy`

### PR E: `feat(factory)!: remove the fields release N deprecated`

### Task 16: the removals

**Files:**
- Modify: `internal/factory/config/binding.go` (`PolicySpec`, `Requirable`, `policyShapeProblems`, `ModeOff`, the `review` cases), `internal/factory/config/classes.go`, `internal/factory/config/mergepolicy.go` (the six switches, `MinPromotionEvidence`, `MinPromotion`), `internal/factory/config/config.go` (`AutoMergesPerDay`, `Schedule`), `api/factory/v1alpha1/factoryconfig_types.go:119-121,239-241,292`, `internal/factory/config/deprecated.go` (now the refusal list), `internal/factory/resources/migrate.go`, `docs/upgrading.md`
- Test: `internal/factory/config/deprecated_test.go`, `api/factory/v1alpha1/mergepolicy_crd_test.go`, `internal/factory/resources/migrate_test.go`

**Interfaces:**
- Produces: `PolicySpec` embeds a `MergeClass` that has no `Live`, `Shadow`, `Harness`, `HarnessAllowed`, `Escalation`, `TestFirst`, `Checks`; `Schedule.Workflow string` (json `workflow`); a schedule's `class` is refused unless its policy has an `oracle.probe`; `maku config migrate` rewrites every removed field (`off`→ deleted binding or `disabled` for a catalog name, switches → `stage`, `autoMergesPerDay` → `maxPerDay`, drops `requires` and `minPromotionEvidence`, moves workflow fields per the workflows design).

- [ ] **Step 1: Tests.** `TestRemovedFieldsAreRefused` (envtest, in `mergepolicy_crd_test.go`): a `MergePolicy` with `harness`, `requires`, `live` is rejected by the API server as an unknown field. `TestMigrateRewritesEveryRemovedField`: the v0.47.0 fixture `internal/factory/resources/testdata/anr-legacy-config.json` migrates to objects that `Assemble` accepts with no problem. `TestScheduleClassNeedsAProbe`.
- [ ] **Step 2: Run** `go test ./api/... ./internal/factory/config ./internal/factory/resources -run 'Removed|Migrate|ScheduleClass'` — FAIL.
- [ ] **Step 3: Implement**; `task crd:gen`.
- [ ] **Step 4: Run** `task check` — exit 0.
- [ ] **Step 5: Commit** `feat(factory)!: MergePolicy drops the workflow fields, requires and mode off`

### Task 17: evidence carries over

**Files:** Test only: `internal/factory/evidence/evidence_test.go`.

- [ ] **Step 1: Test** `TestEvidenceCountsBothEras`: five pull requests whose marker says `class=docs` from a label-chosen decision and five from a diff-chosen one give `ShadowTally` for `docs` a clean count of 10. Evidence is keyed by the marker's `class=`, which the policy name fills in both eras, so no migration is written.
- [ ] **Step 2: Run** `go test ./internal/factory/evidence -run BothEras` — PASS; if it fails, the marker changed its key and Task 14 is wrong.
- [ ] **Step 3: Commit** `test(factory): shadow evidence spans the label-chosen and diff-chosen gates`

### Task 18: the guide

**Files:** Modify `docs/merge-policies.md`, `docs/factory.md` (the merge gate section's selection rule), `docs/upgrading.md`; `internal/app/maku_policy_docs_test.go` if it reads the guide's blocks.

- [ ] **Step 1:** Replace "Start here" with the zero-binding path; add the field-tier table, the one table of the seven check names, and the design's three worked examples verbatim; delete the `.policy.yml` rule steps (they stay only under "policy-bot, an optional integration").
- [ ] **Step 2: Run** `task docs` — exit 0.
- [ ] **Step 3: Commit** `docs: merge policies chosen from the diff, the catalog and three worked examples`

## Self-review notes

- Spec items with no task here, by design: the workflow fields' new home and `loops` re-keying (workflows plan); where Slack, the CLI and MCP show the decision string (UX plan); page splits (docs plan).
- `stage` defaults to `manage` (the design's call). Task 6 keeps a broker without `factoryURL` starting.
