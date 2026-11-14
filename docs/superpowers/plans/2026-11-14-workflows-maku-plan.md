# Workflows, roles and onboarding: Maku implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maku offers three named workflows (`quick`, `standard`, `careful`), measures them on live
traffic, lets a maintainer pick one by label, and onboards a repository with `maku repo add` and
`maku repo check`.

**Architecture:** Release N adds without breaking: the three workflows become defaults of the
factory's config (over today's `harnessProfiles`, `templates` and `loops`), old names warn, and one
new key, `evaluation.treatment`, gives the existing cohort draw a second arm. Release N+1 moves the
choice of workflow off the class (label, source, repository default), renames the CRD field to
`workflows`, and refuses everything N warned about. The onboarding commands reuse `internal/install`
and the preflight.

**Tech Stack:** Go (the `maku-factory`, `maku-broker` and `maku` binaries), controller-gen CRDs,
Helm charts, envtest; `task check` is the gate.

**Spec:** [`docs/superpowers/specs/2026-11-14-workflows-review-design.md`](../specs/2026-11-14-workflows-review-design.md)
in ai-native-ref. Copy the spec and this plan into Maku's `docs/superpowers/` when execution starts.

**This plan runs in the Maku repository**, in a worktree from `origin/main`. Paths below are Maku's.

## Global Constraints

- `task check` exits 0 before every commit (Maku `AGENTS.md`). Lint through `task lint` only.
- After any change under `api/` or to a `+kubebuilder` type: `task crd:gen`, and commit the generated
  CRDs, deepcopy and chart copies (`crd:check` fails otherwise).
- Every `.go` file opens with `// SPDX-License-Identifier: Apache-2.0`.
- Commits are conventional, in English, with no trailers.
- Workflow names are exactly `quick`, `standard`, `careful`, and `none` for adopted pull requests.
- Descriptions are at most 120 characters (`config.MaxDescription`).
- No metric or label is renamed: metrics keep `agent_factory_*`, and the `profile` label carries the
  workflow's name.
- Frozen until the measurement decides (WF8): no new evaluation mode, cohort, refusal code or role
  beyond `evaluation.treatment`; `evaluation.mode` stays `observe` by default.
- Removals follow WF13: release N accepts with a warning in `Config.Warnings`, release N+1 refuses.
  Both releases are v0.4x minors before v4.0.0.
- Tasks 7 to 9 ship in the same release as the diff-chosen gate of the merge policies plan
  (`2026-11-14-merge-policies-maku-plan.md`). That plan removes the fields from the `MergePolicy`
  CRD; this plan only stops reading them and lands where they go.

## One departure from the spec

The spec says "the chart ships the three workflows". No chart renders a `Factory` object: the
platform applies its own, and `maku install --print` writes one. So Task 1 ships the workflows as
**defaults of the config**, filled key by key when a `Factory` omits them, and Task 6 has the
installer write them out. A `Factory` that names none of them still offers all three.

## Pull requests

| PR | Tasks | Release |
|---|---|---|
| A | 1, 2 | N |
| B | 3 | N |
| C | 4 | N |
| D | 5, 6 | N |
| E | 7, 8, 9 | N+1, with the merge policies plan's gate |
| F | 10, 11 | either |
| G | 12 | either |

## Review Focus

1. **A platform already defines `harnessProfiles.standard`, or a `careful` loops row, with its own
   content.** The shipped default must not replace or merge into it. Pinned by
   `TestShippedWorkflowsNeverOverride` (Task 1).
2. **A class row that sets only `models` starts inheriting `default`'s `judge`, and the loop switches
   on for a class that never had one.** Inheritance must be reported before it changes a run. Pinned
   by `TestLoopInheritanceWarnsWhenItSwitchesALoopOn` (Task 2).
3. **A treatment-cohort task whose class cannot run the treatment workflow** (a live or shadow class,
   a schedule, an adopted pull request, a class that does not allow it). It runs its floor and must
   be told apart from a real treatment task in the metrics. Pinned by
   `TestTreatmentArmFallsBackAndIsLabelled` (Task 4).
4. **Both spellings at once**: `workflows` and `harnessProfiles` on one `Factory`, or a `profile:x`
   and a `workflow:y` label on one issue. Pinned by `TestWorkflowsAndHarnessProfilesTogetherRefused`
   and `TestProfileAndWorkflowLabelsConflict` (Task 3).
5. **`maku repo add` on a repository whose branch protection the caller cannot read.** It must not
   write a `Repository` with an empty `requiredChecks` that then merges on no check. Pinned by
   `TestRepoAddUnreadableChecksFails` (Task 10).

---

## Release N

### Task 1: The three workflows as config defaults

**Files:**
- Create: `internal/factory/config/workflows.go`
- Modify: `internal/factory/config/config.go` (`Parse`, after `MergeDefaults` are applied;
  `validateTriageTemplates` at `:2641`)
- Modify: `internal/factory/triage/classify.go:24-37` (`Matrix`)
- Test: `internal/factory/config/workflows_test.go`, `internal/factory/triage/classify_test.go`

**Interfaces:**
- Produces: `func ShippedWorkflows() (profiles map[string]HarnessProfile, templates map[string]Template, loops map[string]Loop)`
  and `func (c *Config) applyShippedWorkflows()`. Later tasks rely on the names `quick`, `standard`,
  `careful`, `none` always resolving in `c.HarnessProfiles`.

The shipped values, verbatim from the spec:

```yaml
templates:
  solo: {roles: [implementer]}
  pair: {roles: [implementer, reviewer], maxReviewRounds: 2}
  investigate: {roles: [triager]}
harnessProfiles:
  quick:    {template: solo, description: "One implementer. For changes a check can verify."}
  standard: {template: pair, description: "An implementer and a reviewer. The default."}
  careful:  {template: pair, tier: frontier, loop: careful,
             description: "Scoped first, judged before review. For wide or unclear tasks."}
  none:     {template: none}
loops:
  default: {scope: "off"}
  careful: {scope: scoper, judge: tier-light, search: true,
            split: {maxChildren: 4, childTier: standard}}
```

- [ ] **Step 1: Write the failing tests**

```go
func TestShippedWorkflowsFillAnEmptyFactory(t *testing.T) {
	c := parse(t, minimalConfig) // the package's existing helper for a config with no profiles
	for _, n := range []string{"quick", "standard", "careful", "none"} {
		if _, ok := c.HarnessProfiles[n]; !ok {
			t.Fatalf("workflow %s is not shipped", n)
		}
	}
	if got := c.Templates["solo"].Roles; !slices.Equal(got, []string{"implementer"}) {
		t.Fatalf("solo roles = %v", got)
	}
	if c.ScopeFor("careful") != ScopeScoper || c.LoopFor("careful").JudgeModel != "tier-light" || !c.SearchFor("careful") {
		t.Fatal("the careful row is not the shipped one")
	}
}

func TestShippedWorkflowsNeverOverride(t *testing.T) {
	c := parse(t, minimalConfig+`
harnessProfiles: {standard: {template: solo, checks: true}}
loops: {careful: {scope: steering}}
templates: {solo: {roles: [implementer, reviewer], maxReviewRounds: 2}}
`)
	if p := c.HarnessProfiles["standard"]; p.Template != "solo" || !p.Checks || p.Description != "" {
		t.Fatalf("the platform's standard was touched: %+v", p)
	}
	if c.ScopeFor("careful") != ScopeSteering || c.LoopFor("careful") != nil {
		t.Fatal("the platform's careful row was merged with the shipped one")
	}
	if got := c.Templates["solo"].Roles; len(got) != 2 {
		t.Fatalf("the platform's solo was replaced: %v", got)
	}
}

func TestTrioIsOptional(t *testing.T) { // config: no templates.trio
	c := parse(t, minimalConfig)
	if _, ok := c.Templates["trio"]; ok {
		t.Fatal("trio is shipped")
	}
}
```

In `classify_test.go`, change the `Matrix` table row `{"tests", "schedule", "frontier", "trio"}` to
expect `"pair"`, and add `TestMatrixNeverReturnsTrio` asserting `Matrix(c, s, "frontier") != "trio"`
for every class and source in the table.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run 'ShippedWorkflows|TrioIsOptional' ./internal/factory/triage -run Matrix`
Expected: FAIL (`ShippedWorkflows` undefined; `templates.trio is missing`; `Matrix` returns `trio`).

- [ ] **Step 3: Implement**

- `ShippedWorkflows` returns the three maps above. `applyShippedWorkflows` adds a map entry only
  when its key is absent; it never touches an existing entry.
- `validateTriageTemplates` requires `solo` and `pair` only.
- `Matrix` returns `pair` where it returned `trio`.

- [ ] **Step 4: Run the tests, then the package and its dependents**

Run: `go test ./internal/factory/...`
Expected: PASS. Fixtures that assert `trio` at frontier are updated to `pair` in this commit.

- [ ] **Step 5: Commit**

```bash
git add internal/factory
git commit -m "feat(factory): the quick, standard and careful workflows as config defaults"
```

### Task 2: A loops row inherits `default` key by key (WF10)

**Files:**
- Modify: `internal/factory/config/evaluation.go` (`rowOf`), `internal/factory/config/config.go`
  (the `Loops` and `Loop` doc comments at `:157` and `:2342`, and the warning site near `:1776`)
- Test: `internal/factory/config/loops_test.go`

**Interfaces:**
- Consumes: `Config.Loops`, `Loop`.
- Produces: `rowOf(name)` returns `default`'s row with every key the named row sets laid over it.
  `ModelFor`, `LoopFor`, `ScopeFor`, `SearchFor` keep their signatures.

- [ ] **Step 1: Write the failing tests**

```go
func TestLoopRowInheritsDefaultKeyByKey(t *testing.T) {
	c := parse(t, minimalConfig+`
loops:
  default: {scope: scoper, search: true, models: {reviewer: {frontier: kimi-frontier}}}
  docs: {stallSteps: 60}
`)
	if c.ScopeFor("docs") != ScopeScoper || !c.SearchFor("docs") {
		t.Fatal("docs did not inherit default's scope and search")
	}
	if *c.LoopFor("docs").StallSteps != 60 {
		t.Fatal("docs lost its own key")
	}
	if got := c.ModelFor("docs", "public", "reviewer", "frontier"); got != "kimi-frontier" {
		t.Fatalf("models not inherited: %q", got)
	}
}

func TestLoopRowOverridesDefault(t *testing.T) { // scope: "off" on the row beats default's scoper
	c := parse(t, minimalConfig+`
loops: {default: {scope: scoper}, docs: {scope: "off"}}
`)
	if c.ScopeFor("docs") != ScopeOff {
		t.Fatal("an explicit off was overridden")
	}
}

func TestLoopInheritanceWarnsWhenItSwitchesALoopOn(t *testing.T) {
	c := parse(t, minimalConfig+`
loops: {default: {judge: tier-light}, revert: {models: {reviewer: {frontier: kimi-frontier}}}}
`)
	want := "loops.revert now inherits default's judge: its loop switches on"
	if !slices.ContainsFunc(c.Warnings, func(w string) bool { return strings.Contains(w, want) }) {
		t.Fatalf("no warning; got %v", c.Warnings)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run LoopRow -run LoopInheritance`
Expected: FAIL (a row is read whole).

- [ ] **Step 3: Implement the merge in `rowOf`**

A pointer or string key is inherited when unset on the row. `Search` is a bool with no "unset":
decode it as `*bool` in the row's unmarshal so an absent key inherits and `search: false` does not,
and keep the public field a bool. `Models` merges
role by role, tier by tier. `Split` is taken whole. Append the warning when a row that switched no
loop on before (none of `stallSteps`, `continuations`, `judge`) inherits one of them.

- [ ] **Step 4: Run the tests**

Run: `go test ./internal/factory/...`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/config
git commit -m "feat(factory): a loops row inherits default key by key"
```

### Task 3: Old names warn; `workflows` and `workflow:` are synonyms (WF9, WF13)

**Files:**
- Modify: `api/factory/v1alpha1/factoryconfig_types.go:47` (`FactorySpec`)
- Modify: `internal/factory/config/config.go` (`Config`, the warnings near `:1776`),
  `internal/factory/resources/assemble.go` (the spec-to-config mapping)
- Modify: `internal/factory/triage/classify.go:144-165` (the pin's labels)
- Modify: `internal/config/config.go:270-330` (the broker's `human.intake.plan.classes`)
- Modify: `docs/upgrading.md`
- Test: `internal/factory/config/workflows_test.go`, `internal/factory/triage/pin_test.go`,
  `internal/factory/resources/assemble_test.go`, `internal/config/config_test.go`

**Interfaces:**
- Produces: `FactorySpec.Workflows map[string]config.HarnessProfile` (json `workflows`), read into
  `Config.HarnessProfiles`; `triage.LabelPin` built from `workflow:<name>` and `profile:<name>` alike.

- [ ] **Step 1: Write the failing tests**

```go
func TestDeadSettingsWarn(t *testing.T) {
	c := parse(t, minimalConfig+`
templates: {trio: {roles: [implementer, reviewer]}}
triage: {classifierURL: "http://c7"}
defaults: {template: solo, tier: standard}
harnessProfiles: {mine: {template: pair}}
`)
	for _, want := range []string{"templates.trio", "triage.classifierURL", "defaults.template", "defaults.tier", "harnessProfiles"} {
		if !slices.ContainsFunc(c.Warnings, func(w string) bool {
			return strings.Contains(w, want) && strings.Contains(w, "refused from the next minor")
		}) {
			t.Errorf("no warning for %s", want)
		}
	}
}

func TestWorkflowsIsReadAsHarnessProfiles(t *testing.T) { // assemble: spec.workflows only
	res := assemble(t, factoryWith(`workflows: {mine: {template: pair}}`))
	if _, ok := res.Config.HarnessProfiles["mine"]; !ok || len(res.Warnings) != 0 {
		t.Fatalf("workflows not read, or warned: %v", res.Warnings)
	}
}

func TestWorkflowsAndHarnessProfilesTogetherRefused(t *testing.T) {
	_, err := assembleErr(factoryWith(`
workflows: {a: {template: pair}}
harnessProfiles: {b: {template: pair}}`))
	if err == nil || !strings.Contains(err.Error(), "workflows and harnessProfiles: set one") {
		t.Fatalf("got %v", err)
	}
}

func TestWorkflowLabelIsAPin(t *testing.T) { // labels: workflow:careful by a maintainer
	pin := resolve(t, []LabelPin{{Name: "careful", Actor: "alice"}})
	if !pin.Honoured() {
		t.Fatalf("refused: %s", pin.Refused)
	}
}

func TestProfileAndWorkflowLabelsConflict(t *testing.T) { // profile:standard and workflow:careful
	d := triageIssue(t, "profile:standard", "workflow:careful")
	if d.Pin.Refused != intake.ProfileConflict {
		t.Fatalf("got %q", d.Pin.Refused)
	}
}
```

In the broker's config test: a config with `human.intake.plan.classes` loads and reports
`human.intake.plan.classes` in its ignored-with-warning list.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/... ./internal/config -run 'DeadSettings|Workflows|WorkflowLabel|LabelsConflict|PlanClasses'`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `FactorySpec` gains `Workflows` with the same bounds as `HarnessProfiles`; `task crd:gen`.
- `assemble.go`: `workflows` fills `HarnessProfiles`; both set is the refusal above.
- Warnings, each ending "refused from the next minor (WF13)": one per dead setting present, and one
  for a non-empty `harnessProfiles`.
- `classify.go`: the label loop cuts either prefix. A task pinned through `profile:` gets one
  narration line: "the `profile:` label is read as `workflow:` and is ignored from the next minor".
- `docs/upgrading.md`: a section headed by release N's version listing the five warnings and the two
  synonyms.

- [ ] **Step 4: Run the gate**

Run: `task check`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add api config charts internal docs/upgrading.md
git commit -m "feat(factory): workflows and workflow: are read; the dead settings warn"
```

### Task 4: `evaluation.treatment`, the measurement's second arm (WF8)

**Files:**
- Modify: `internal/factory/config/evaluation.go` (`Evaluation`, `validateEvaluation`)
- Modify: `internal/factory/reconciler/reconciler.go:1203-1227` (`floorProfile`)
- Modify: `internal/factory/catalogue/catalogue.go:59` (`Evaluation`)
- Modify: `docs/factory.md` (the evaluation section, `:603-609`)
- Test: `internal/factory/config/evaluation_test.go`, `internal/factory/reconciler/profile_test.go`

**Interfaces:**
- Consumes: `triage.Decision.Cohort`, `Config.ProfileFor(cl, name)`, `catalogue.ModeOf`.
- Produces: `Evaluation.Treatment string` (json `treatment`); `ProfileStatus.Source` gains the value
  `"treatment"`. The metrics already carry `cohort`, `profile` and `source`
  (`fmetrics.go:499`, `:564`); nothing is added there.

The rule: a task in the `treatment` cohort runs `evaluation.treatment` when all hold: the key is
set, the task is not pinned, its source is an issue (not `schedule`, not an adopted pull request),
its class is neither live nor shadow, and `ProfileFor(class, treatment)` allows it. Otherwise it
runs its floor with `source: floor`, as today.

- [ ] **Step 1: Write the failing tests**

```go
func TestEvaluationTreatmentMustBeAWorkflow(t *testing.T) {
	_, err := parseErr(minimalConfig + `evaluation: {controlPercent: 50, treatment: nope}`)
	if err == nil || !strings.Contains(err.Error(), `evaluation.treatment "nope" is not a workflow`) {
		t.Fatalf("got %v", err)
	}
}

func TestTreatmentArmRunsTheNamedWorkflow(t *testing.T) {
	// class review: harness standard, harnessAllowed [careful], bound off; treatment: careful
	task := triaged(t, cfgTreatment, issueTask("review"), triage.CohortTreatment)
	p := task.Status.Profile
	if p.Name != "careful" || p.Source != "treatment" || p.Cohort != triage.CohortTreatment {
		t.Fatalf("got %+v", p)
	}
	if task.Spec.ScopeMode != "scoper" || task.Spec.Budget.Tier != "frontier" {
		t.Fatal("the careful workflow's spec was not applied")
	}
}

func TestControlArmRunsTheFloor(t *testing.T) {
	p := triaged(t, cfgTreatment, issueTask("review"), triage.CohortControl).Status.Profile
	if p.Name != "standard" || p.Source != "control" {
		t.Fatalf("got %+v", p)
	}
}

func TestTreatmentArmFallsBackAndIsLabelled(t *testing.T) {
	for name, task := range map[string]*v1alpha1.Task{
		"a live class":          issueTask("docs-links"), // bound live in cfgTreatment
		"a schedule":            scheduleTask("review"),
		"a class not allowing":  issueTask("tests"), // harnessAllowed empty
	} {
		p := triaged(t, cfgTreatment, task, triage.CohortTreatment).Status.Profile
		if p.Name == "careful" || p.Source != "floor" {
			t.Errorf("%s: got %+v, want its floor with source floor", name, p)
		}
	}
}

func TestPinnedTaskIgnoresTreatment(t *testing.T) { // cohort labeled keeps the pin
	p := triaged(t, cfgTreatment, pinnedTask("review", "standard"), triage.CohortLabeled).Status.Profile
	if p.Name != "standard" || p.Source != "label" {
		t.Fatalf("got %+v", p)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run EvaluationTreatment ./internal/factory/reconciler -run 'TreatmentArm|ControlArm|PinnedTaskIgnores'`
Expected: FAIL (`treatment` is an unknown key).

- [ ] **Step 3: Implement**

`Evaluation.Treatment` with `MaxLength=253`; `validateEvaluation` refuses a name absent from
`HarnessProfiles`; `floorProfile` applies the rule above and sets `Source: "treatment"`; the
catalogue's `Evaluation` gains `Treatment string` (json `treatment`). `task crd:gen`.

- [ ] **Step 4: Document the reading**

In `docs/factory.md`, replace the cohort paragraph with: what the two arms run, the exclusions, and
the query pair, by `cohort` with `source=~"control|treatment"`:
cost per merged pull request is `agent_factory_task_usd_total` over
`agent_factory_task_outcomes_total{outcome=~"accepted|merged_human"}`; merge rate is that count over
every ended task. Use the names the factory serves (check `/metrics`; the docs write
`maku_factory_*` in places, correct whichever is wrong).

- [ ] **Step 5: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add api config charts internal docs/factory.md
git commit -m "feat(factory): evaluation.treatment names the treatment cohort's workflow"
```

### Task 5: "workflow" in what a person reads (WF1, WF6)

**Files:**
- Modify: `internal/factory/narrate/` (the profile sentences, `ProfileRefused` included),
  `internal/roomview/words.go`, `internal/summary/`, `internal/intake/reviseprofile.go:52-57`,
  `internal/humanapi/mcp.go` (the `classes_list` description), `web/src/` (the room page's profile
  line, the plan's select)
- Modify: `docs/concepts.md` (the glossary's roles row, `:56`), `docs/factory.md` (the templates and
  profiles sections), `docs/cli.md`, `docs/web-ui.md`, `docs/slack.md`
- Test: the narration and room-view goldens beside each file; `web/` vitest snapshots

**Interfaces:**
- Consumes: nothing new.
- Produces: no identifier changes. JSON fields, config keys, metric labels and event types keep
  their names; only sentences change.

The renames, verbatim from the spec:

| Today | Becomes |
|---|---|
| harness profile, template, class (as shown to a person) | workflow |
| capability profile | role permissions |
| `approvals.profile` (attended, unattended) | approval mode |
| egress profile | egress allow-list |

Five roles in every reader-facing table: scoper, tester, implementer, judge, reviewer. The splitter
is "the scoper may propose parts"; search is "a tool of the implementer"; the triager is named on
the RunLore page only.

- [ ] **Step 1: Write the failing test**

Add `hack/vocabulary_test.sh` and `hack/vocabulary.sh`, wired into `task docs`: the reader pages
(`docs/*.md` except `api.md`, `upgrading.md`, `event-envelope.md`, `room-log.md`) contain no
`harness profile`, `capability profile`, `egress profile` or `trio`. The test feeds the script a
fixture page with each phrase and expects a non-zero exit naming the line.

A plan record written before this release must still parse:

```go
func TestRevisePlanReadsBothSpellings(t *testing.T) {
	for _, text := range []string{"profile: careful, pinned by the developer", "workflow: careful, pinned by the developer"} {
		if got := pinnedProfile(recordsWith(text)); got != "careful" {
			t.Errorf("%q: got %q", text, got)
		}
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `bash hack/vocabulary_test.sh && go test ./internal/intake -run RevisePlanReadsBothSpellings`
Expected: FAIL.

- [ ] **Step 3: Change the sentences and the pages; regenerate the goldens**

New records are written with `workflow:`; both are read. Rebuild the UI bundle (`task ui:check`
compares it).

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal web docs hack taskfile.yaml
git commit -m "feat: one noun, workflow, in the room page, the plan, the narration and the docs"
```

### Task 6: The installer writes the workflows

**Files:**
- Modify: `internal/install/factory.go:83-99` (`factoryConfig`)
- Test: `internal/install/write_test.go`, `internal/install/testdata/golden/{generic,ghes}/factory/factory.yaml`

**Interfaces:**
- Consumes: `config.ShippedWorkflows()` (Task 1).

- [ ] **Step 1: Write the failing test**

```go
func TestInstalledFactoryCarriesTheWorkflows(t *testing.T) {
	f := renderedFactory(t, genericAnswers) // the golden's factory/factory.yaml, decoded
	for _, n := range []string{"quick", "standard", "careful"} {
		if _, ok := f.Spec.Workflows[n]; !ok {
			t.Errorf("workflow %s not written", n)
		}
	}
	if _, ok := f.Spec.Templates["trio"]; ok {
		t.Error("trio is written")
	}
	if got := f.Spec.Templates["solo"].Roles; !slices.Equal(got, []string{"implementer"}) {
		t.Errorf("solo = %v", got)
	}
	if f.Spec.Defaults.Template != "" || f.Spec.Defaults.Tier != "" {
		t.Error("defaults.template or defaults.tier is written")
	}
	if len(f.Spec.HarnessProfiles) != 0 {
		t.Error("harnessProfiles is written; workflows is the key")
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/install -run InstalledFactoryCarriesTheWorkflows`
Expected: FAIL.

- [ ] **Step 3: Implement**

`factoryConfig` takes the three maps from `ShippedWorkflows`, writes them under `workflows`,
`templates` and `loops`, drops `defaults.template`, `defaults.tier`, `trio` and the two per-class
`loops` rows it writes today. Regenerate both goldens with the test's update flag.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0; `maku config validate` on the golden passes without a warning.

```bash
git add internal/install
git commit -m "feat(install): the wizard writes the three workflows and no dead setting"
```

---

## Release N+1

Tasks 7 to 9 are one pull request and one release, with the merge policies plan's diff-chosen gate.

### Task 7: The objects name workflows

**Files:**
- Modify: `api/factory/v1alpha1/factoryconfig_types.go` (`FactorySpec`, `RepositorySpec`)
- Modify: `internal/factory/config/mergepolicy.go:43` (`HarnessProfile`), `config.go:409`
  (`Repository`), `config.go:1033` (`Schedule`), `evaluation.go`
- Test: `api/factory/v1alpha1/factoryconfig_crd_test.go`, `internal/factory/config/workflows_test.go`

**Interfaces:**
- Produces:
  - `HarnessProfile.Escalation *Escalation` (json `escalation`; the type moves from `classes.go`).
  - `type RepositoryWorkflow struct { Default string; TestFirst bool }`, json `default`, `testFirst`,
    as `Repository.Workflow` / `RepositorySpec.Workflow` (json `workflow`).
  - `Schedule.Workflow string` (json `workflow`).
  - `func (r Repository) DefaultWorkflow() string`, `"standard"` when unset.

- [ ] **Step 1: Write the failing tests**

```go
func TestRepositoryDefaultWorkflow(t *testing.T) {
	if got := (Repository{}).DefaultWorkflow(); got != "standard" {
		t.Fatalf("got %q", got)
	}
}

func TestRepositoryWorkflowProblems(t *testing.T) {
	cases := map[string]string{
		`workflow: {default: nope}`:   `workflow.default "nope" is not a workflow`,
		`workflow: {default: none}`:   `workflow.default: none is for adopted pull requests`,
		`workflow: {testFirst: true}`: `workflow.testFirst needs merge.contractCheck`,
	}
	for y, want := range cases {
		if _, err := parseErr(repoWith(y)); err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%s: got %v", y, err)
		}
	}
}

func TestScheduleWorkflowDefaultsToQuick(t *testing.T) {
	c := parse(t, repoWith(`schedules: [{name: s, cron: "0 7 * * *", class: dead-links, probe: dead-links, text: x}]`))
	if got := c.Repos()[0].Schedules[0].WorkflowOr(); got != "quick" {
		t.Fatalf("got %q", got)
	}
}

func TestLoopsKeyedByWorkflow(t *testing.T) {
	_, err := parseErr(minimalConfig + `loops: {docs: {scope: scoper}}`)
	if err == nil || !strings.Contains(err.Error(), `loops.docs: a row is named default or a workflow`) {
		t.Fatalf("got %v", err)
	}
}

func TestHarnessProfilesRefused(t *testing.T) {
	_, err := assembleErr(factoryWith(`harnessProfiles: {a: {template: pair}}`))
	if err == nil || !strings.Contains(err.Error(), "harnessProfiles: renamed workflows") {
		t.Fatalf("got %v", err)
	}
}
```

The CRD test: a `Repository` with `spec.workflow.default: careful` is admitted; one whose
`workflow.default` is 300 characters is refused.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config ./api/... -run 'Workflow|LoopsKeyed|HarnessProfilesRefused'`
Expected: FAIL.

- [ ] **Step 3: Implement the types, the validation and `task crd:gen`**

`testFirst` keeps today's two conditions (a `contractCheck`, public tasks only). `FactorySpec` drops
`HarnessProfiles`; the config keeps the Go field `HarnessProfiles` filled from `workflows` so the
reconciler's call sites do not move in this task.

- [ ] **Step 4: Run and commit with Tasks 8 and 9** (one pull request).

### Task 8: The workflow is chosen by label, source, then repository

**Files:**
- Create: `internal/factory/triage/workflow.go`
- Modify: `internal/factory/triage/pin.go` (`ResolvePin`, `PinRefusal`),
  `internal/factory/triage/classify.go` (the label loops at `:158`, `:212`),
  `internal/factory/reconciler/reconciler.go:1150-1227` (`floorProfile`, `profileSpec`),
  `internal/factory/reconciler/profile.go:150-175` (`variantFor`),
  `internal/factory/config/evaluation.go` (`ProfileFor`, `belowFloor`, `variantProblems`, `RowFor`),
  `internal/intake/` (the codes `ClassNoProfiles`, `ClassProfileFixed`, `ProfileNotAllowed`),
  `internal/factory/catalogue/catalogue.go` (`Class.Floor`, `Class.Allowed` go; `Catalogue` gains
  `DefaultWorkflow string`, json `defaultWorkflow`)
- Test: `internal/factory/triage/workflow_test.go`, `pin_test.go`,
  `internal/factory/reconciler/profile_test.go`

**Interfaces:**
- Produces:

```go
// WorkflowFor is the workflow t runs and why: the first of a maintainer's pin, the task's source,
// the repository's default.
func WorkflowFor(cfg *config.Config, t *v1alpha1.Task, pin Pin) (name, source string)
```

`source` is one of `label`, `schedule`, `revert`, `oracle`, `adopted`, `repository`.

- [ ] **Step 1: Write the failing tests**

```go
func TestWorkflowFor(t *testing.T) {
	cases := []struct {
		name       string
		task       *v1alpha1.Task
		pin        Pin
		want, from string
	}{
		{"a maintainer's label wins", issueTask(), Pin{Name: "careful"}, "careful", "label"},
		{"a maintainer may pick below the default", issueTask(), Pin{Name: "quick"}, "quick", "label"},
		{"a refused pin is ignored", issueTask(), Pin{Name: "quick", Refused: intake.NotMaintainer}, "standard", "repository"},
		{"a schedule names its own", scheduleTask("careful"), Pin{}, "careful", "schedule"},
		{"a schedule without one runs quick", scheduleTask(""), Pin{}, "quick", "schedule"},
		{"a revert runs quick", revertTask(), Pin{}, "quick", "revert"},
		{"an oracle finding runs quick", oracleTask(), Pin{}, "quick", "oracle"},
		{"an adopted pull request runs none", adoptedTask(), Pin{}, "none", "adopted"},
		{"the repository's default", issueTaskIn("careful-repo"), Pin{}, "careful", "repository"},
	}
	for _, c := range cases {
		if got, from := WorkflowFor(cfg, c.task, c.pin); got != c.want || from != c.from {
			t.Errorf("%s: got %s from %s", c.name, got, from)
		}
	}
}

func TestPinRefusalsAfterStageB(t *testing.T) {
	// only these codes remain
	for code, labels := range map[string][]LabelPin{
		intake.NotMaintainer:   {{Name: "quick", Actor: "mallory"}},
		intake.ProfileUnknown:  {{Name: "nope", Actor: "alice"}},
		intake.ProfileConflict: {{Name: "quick", Actor: "alice"}, {Name: "careful", Actor: "alice"}},
	} {
		if got := ResolvePin(cfg, repo, "", labels, "", "", true).Refused; got != code {
			t.Errorf("want %s, got %s", code, got)
		}
	}
}

func TestClassAndProfileLabelsAreIgnoredAndNarrated(t *testing.T) {
	d := triageIssue(t, "class:docs", "profile:careful")
	if d.Pin.Name != "" || d.PredictedClass != "" {
		t.Fatalf("a removed label was read: %+v", d)
	}
	if !slices.Contains(d.Notes, "the class: and profile: labels are no longer read; use workflow:<name>") {
		t.Fatalf("not narrated: %v", d.Notes)
	}
}

func TestTreatmentMayDropTheReviewer(t *testing.T) { // evaluation.treatment: quick, default standard
	p := triaged(t, cfgTreatmentQuick, issueTask(), triage.CohortTreatment).Status.Profile
	if p.Name != "quick" || p.Source != "treatment" {
		t.Fatalf("got %+v", p)
	}
}

func TestTestFirstFollowsTheRepository(t *testing.T) {
	on := triaged(t, cfgTestFirstRepo, pinned("careful"), "").Status.Profile
	off := triaged(t, cfgTestFirstRepo, pinned("standard"), "").Status.Profile
	if !on.TestFirst || off.TestFirst {
		t.Fatalf("careful=%v standard=%v", on.TestFirst, off.TestFirst)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/triage ./internal/factory/reconciler -run 'WorkflowFor|PinRefusals|IgnoredAndNarrated|TreatmentMayDrop|TestFirstFollows'`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `floorProfile` becomes: `WorkflowFor`, then the treatment rule of Task 4 with its class conditions
  removed (pinned, scheduled and adopted tasks stay excluded). `ProfileStatus.Source` records
  `WorkflowFor`'s source.
- `RowFor` returns the workflow's `loop`, else `default`; its `class` parameter goes.
- `belowFloor`, `ProfileFor`'s class check, `HarnessAllowed` reads and the three class refusal codes
  are deleted, with the sentences that name them.
- `Decision` gains `Notes []string` for the narration line; the reconciler narrates each once.
- The tester runs when the repository sets `workflow.testFirst` and the workflow is `careful`.
- `escalation` is read from the workflow; `notConverged`'s target must be a defined workflow.

- [ ] **Step 4: Run and commit with Tasks 7 and 9.**

### Task 9: Everything warned in N is refused

**Files:**
- Modify: `internal/factory/config/config.go` (`templates()` at `:1605`, `Defaults` at `:655`,
  `Triage` at `:667`, the warnings of Task 3), `internal/factory/config/hardening.go:654`,
  `internal/app/factory.go:581-583`, `internal/factory/triage/classify.go:116`,
  `internal/config/config.go` (`human.intake.plan.classes`),
  `internal/factory/coordination/checks.go:142`, `child.go:71` (the last readers of
  `Defaults.Template`: use the repository's default workflow's template)
- Modify: `docs/upgrading.md`, `docs/factory.md` (the config table rows)
- Test: `internal/factory/config/workflows_test.go`, `internal/config/config_test.go`

**Interfaces:**
- Consumes: Task 7's types.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

```go
func TestRemovedSettingsRefused(t *testing.T) {
	cases := map[string]string{
		`templates: {trio: {roles: [implementer]}}`: "templates.trio: removed",
		`triage: {classifierURL: "http://c7"}`:      "triage.classifierURL: removed",
		`defaults: {template: solo}`:                "defaults.template: removed",
		`defaults: {tier: standard}`:                "defaults.tier: removed",
	}
	for y, want := range cases {
		_, err := parseErr(minimalConfig + y)
		if err == nil || !strings.Contains(err.Error(), want) || !strings.Contains(err.Error(), "docs/upgrading.md") {
			t.Errorf("%s: got %v", y, err)
		}
	}
}
```

The broker: a config with `human.intake.plan.classes` fails to load with
`human.intake.plan.classes: removed, the factory's catalog names the workflows`.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/factory/config ./internal/config -run 'RemovedSettings|PlanClassesRemoved'`
Expected: FAIL (they warn).

- [ ] **Step 3: Implement the refusals, delete `HTTPClassifier`'s wiring, write the upgrade note**

`docs/upgrading.md` gets one table: old key or label, what to write instead, the release that
refused it. `hack/vocabulary.sh` (Task 5) adds `harnessProfiles` and `profile:` to its list.

- [ ] **Step 4: Run the gate**

Run: `task check`
Expected: exit 0.

- [ ] **Step 5: Commit Tasks 7 to 9**

```bash
git add api config charts internal docs hack
git commit -m "feat(factory)!: the workflow comes from a label, the source or the repository; the old names are refused"
```

---

## Either release

### Task 10: `maku repo add`

**Files:**
- Create: `internal/install/repo.go`, `internal/app/maku_repo.go`
- Modify: `internal/app/maku.go:218-229` (the command switch), `internal/install/factory.go`
  (export what `Render` uses to write one `Repository`), `docs/cli.md`
- Test: `internal/install/repo_test.go`, `internal/app/maku_repo_test.go`,
  `internal/install/testdata/golden/repo-add/`

**Interfaces:**
- Consumes: `install.Ruleset(appID string) ([]byte, error)`, `install.Write(dir string, t Tree, force bool) error`,
  `install.CheckOut(dir string, force bool) error`, the `applyRuleset` script writer.
- Produces:

```go
// RepoInputs is what one repository's onboarding files are written from.
type RepoInputs struct {
	Repository     string   // owner/name
	Factory        string   // the Factory's name; the fence's value
	Namespace      string
	Maintainers    []string
	RequiredChecks []string // the default branch's required checks
	LeakScanCheck  string
	Private        bool
	Acknowledged   bool     // spec.privateCode.acknowledged, asked when Private
	FactoryAppID   string
}

// RepoTree is the files `maku repo add` writes: factory/repository-<name>.yaml,
// repo/.github/agent-factory.yaml, github/ruleset-merge-gate.json, github/apply-ruleset.sh, README.md.
func RepoTree(in RepoInputs) (Tree, error)
```

`maku repo add <owner/name> --out DIR [--factory NAME] [--namespace NS] [--maintainer LOGIN]... [--check NAME]... [--leak-scan-check NAME] [--acknowledge-private-code] [--force]`.
It reads the default branch, its required checks and visibility through the caller's `gh`
authentication, writes the tree, and prints the two App install links. It applies nothing and opens
no pull request.

- [ ] **Step 1: Write the failing tests**

```go
func TestRepoTreeForAPublicRepository(t *testing.T) {
	tree, err := RepoTree(RepoInputs{Repository: "acme/my-service", Factory: "agent-factory", Namespace: "maku",
		Maintainers: []string{"alice"}, RequiredChecks: []string{"ci"}, LeakScanCheck: "ci", FactoryAppID: "123"})
	if err != nil {
		t.Fatal(err)
	}
	golden(t, tree, "testdata/golden/repo-add/public") // the spec's Repository, byte for byte
	repo := tree["factory/repository-my-service.yaml"]
	if n := bytes.Count(repo, []byte("\n")); n >= 15 {
		t.Fatalf("the Repository is %d lines, the target is under 15", n)
	}
	if bytes.Contains(repo, []byte("mergePolicies")) {
		t.Fatal("a binding was written")
	}
	if got := string(tree["repo/.github/agent-factory.yaml"]); got != "factory: agent-factory\n" {
		t.Fatalf("the fence is %q", got)
	}
}

func TestRepoTreePrivateNeedsTheAcknowledgement(t *testing.T) {
	_, err := RepoTree(RepoInputs{Repository: "acme/secret", Private: true, RequiredChecks: []string{"ci"}})
	if err == nil || !strings.Contains(err.Error(), "--acknowledge-private-code") {
		t.Fatalf("got %v", err)
	}
}

func TestRepoAddUnreadableChecksFails(t *testing.T) { // gh fake: 403 on the branch's protection
	err := runRepoAdd(t, fakeGH{protection: forbidden}, "acme/my-service", "--out", t.TempDir())
	if err == nil || !strings.Contains(err.Error(), "cannot read the required checks of acme/my-service: pass --check") {
		t.Fatalf("got %v", err)
	}
}

func TestRepoAddNoRequiredChecksFails(t *testing.T) { // readable, and empty
	err := runRepoAdd(t, fakeGH{}, "acme/my-service", "--out", t.TempDir())
	if err == nil || !strings.Contains(err.Error(), "no required check: the factory merges on one") {
		t.Fatalf("got %v", err)
	}
}

func TestRepoAddRefusesAnExistingDirWithoutForce(t *testing.T) // as maku install --print does
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/install ./internal/app -run 'RepoTree|RepoAdd'`
Expected: FAIL (`RepoTree` undefined).

- [ ] **Step 3: Implement `RepoTree`, then the command**

The `Repository` is written by the same function `Render` uses, so `maku install --print` and
`maku repo add` cannot drift; a test renders one repository both ways and compares.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal docs/cli.md
git commit -m "feat(cli): maku repo add writes a repository's onboarding files"
```

### Task 11: `maku repo check`

**Files:**
- Create: `internal/app/maku_repo_check.go`
- Modify: `internal/app/maku_preflight.go` (share the fetch and the printer),
  `internal/app/factory_preflight.go:96` (a `repository` filter on `apps`, `merge-gate`,
  `private-code`), `docs/cli.md`, `docs/install.md` (the generated checks table, through its task)
- Test: `internal/app/maku_repo_check_test.go`, `internal/app/factory_preflight_test.go`

**Interfaces:**
- Consumes: `preflight.Result`, the factory's `/preflight` route, the `Repository`'s conditions
  `Accepted`, `BindingsValid`, `PrivateCode`.
- Produces: `GET /preflight?repository=owner/name` returns only the three repository checks, for
  that repository. `maku repo check <owner/name>` exits 0 when every line passes, 1 otherwise.

Output, one line per check, then one line per failure with its fix:

```
PASS  fence          .github/agent-factory.yaml names agent-factory
PASS  repository     Accepted
PASS  apps           both Apps installed with their permissions
FAIL  merge-gate     merge_gate_not_required
      Fix: run github/apply-ruleset.sh (written by maku repo add), or require the maku/merge-gate status on the default branch.
```

- [ ] **Step 1: Write the failing tests**

```go
func TestPreflightFiltersToOneRepository(t *testing.T) {
	res := preflightFor(t, twoRepositories, "acme/my-service")
	ids := checkIDs(res)
	if !slices.Equal(ids, []string{"apps", "merge-gate", "private-code"}) {
		t.Fatalf("got %v", ids)
	}
	for _, r := range res {
		if strings.Contains(r.Message, "acme/other") {
			t.Fatalf("another repository leaked: %s", r.Message)
		}
	}
}

func TestRepoCheck(t *testing.T) {
	cases := map[string]struct {
		world fakeWorld
		code  int
		line  string
	}{
		"all good":            {healthy, 0, "PASS  merge-gate"},
		"no fence":            {noFence, 1, "FAIL  fence          .github/agent-factory.yaml is missing on the default branch"},
		"another factory":     {fenceNames("other"), 1, "FAIL  fence          names other, this factory is agent-factory"},
		"repository unknown":  {noRepositoryObject, 1, "FAIL  repository     no Repository serves acme/my-service"},
		"repository refused":  {notAccepted, 1, "FAIL  repository     Accepted is False"},
		"gate not required":   {gateMissing, 1, "Fix: run github/apply-ruleset.sh"},
		"private unacknowledged": {privateNoAck, 1, "FAIL  private-code   private_code_unacknowledged"},
	}
	for name, c := range cases {
		out, code := runRepoCheck(t, c.world, "acme/my-service")
		if code != c.code || !strings.Contains(out, c.line) {
			t.Errorf("%s: exit %d\n%s", name, code, out)
		}
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/app -run 'PreflightFilters|RepoCheck'`
Expected: FAIL.

- [ ] **Step 3: Implement the filter, then the command**

The fence is read from the default branch with the caller's `gh` authentication; the rest comes
from the factory. Every `FAIL` code maps to exactly one fix sentence, in one table in the file.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal docs
git commit -m "feat(cli): maku repo check verifies one repository's onboarding"
```

### Task 12: The broker plans for the repositories the factory serves (WF12)

**Files:**
- Modify: `internal/factory/catalogue/catalogue.go` (a list beside `Build`), the factory's catalogue
  route in `internal/factory/api/`, `internal/humanapi/catalogue.go` (`CatalogueSource`,
  `CatalogueCache`), `internal/config/config.go:208-211`, `:270`, `:301`
  (`human.intake.plan.repositories`), `docs/cli.md`, `docs/upgrading.md`
- Test: `internal/factory/catalogue/catalogue_test.go`, `internal/humanapi/catalogue_test.go`,
  `internal/config/config_test.go`

**Interfaces:**
- Produces:
  - `func Repositories(cfg *config.Config) []string`: the served repositories, public ones and
    private ones whose acknowledgement is set, sorted.
  - `CatalogueSource.Repositories(ctx context.Context, accessToken string) ([]string, error)`, cached
    like a catalogue.
- `human.intake.plan.repositories`: when set, it narrows the factory's list (an entry the factory
  does not serve is a load warning naming it); when empty, the planner's candidates are the
  factory's list. The key is no longer required when the planner is enabled.

- [ ] **Step 1: Write the failing tests**

```go
func TestRepositoriesServed(t *testing.T) {
	got := Repositories(cfgWith("acme/b", "acme/a", privateUnacknowledged("acme/secret")))
	if !slices.Equal(got, []string{"acme/a", "acme/b"}) {
		t.Fatalf("got %v", got)
	}
}

func TestPlannerCandidatesComeFromTheFactory(t *testing.T) { // no plan.repositories in the broker's config
	got := candidates(t, brokerWith(planEnabled), factoryServing("acme/a", "acme/b"))
	if !slices.Equal(got, []string{"acme/a", "acme/b"}) {
		t.Fatalf("got %v", got)
	}
}

func TestPlanRepositoriesNarrows(t *testing.T) {
	got := candidates(t, brokerWith(planEnabled, planRepositories("acme/a", "acme/gone")), factoryServing("acme/a", "acme/b"))
	if !slices.Equal(got, []string{"acme/a"}) {
		t.Fatalf("got %v", got)
	}
}

func TestPlannerRefusesWhenTheFactoryIsUnreachable(t *testing.T) { // no stale list older than the cache's lifetime
	_, err := candidatesErr(brokerWith(planEnabled), factoryDown)
	if !errors.Is(err, errCatalogueUnavailable) {
		t.Fatalf("got %v", err)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/catalogue ./internal/humanapi ./internal/config -run 'RepositoriesServed|PlannerCandidates|PlanRepositoriesNarrows|PlannerRefuses'`
Expected: FAIL.

- [ ] **Step 3: Implement the list, the route, the cache entry and the config change**

The route answers a caller with the member role, like the catalogue's. It returns names only.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal docs
git commit -m "feat(broker): the planner's repositories come from the factory"
```

---

## Left to the builder (from the spec)

- Whether `checks: true` belongs on `standard` and `careful`: read what a run does when the
  repository has no `.github/agent-checks.yaml`; default to leaving it off.
- The `split` and `search` values of the `careful` row beyond those shown, if validation asks for
  more (`familyUSD` needs a gateway identity: leave it unset in the shipped row).
- The exact wording of the descriptions, within 120 characters.
- `maku repo add --pr`: not in this plan.

## Self-review

| Spec item | Task |
|---|---|
| WF1, WF6, the renames | 5 |
| WF2, the shipped YAML | 1, 6 |
| WF3, WF4, how the workflow is chosen | 3 (synonym), 8 |
| WF5 | 5 (docs only) |
| WF7, where the fields land | 7, 8 |
| WF8, the measurement | 4, 8 (`quick` as treatment) |
| WF9, WF13 | 3, 9 |
| WF10 | 2 |
| WF11 | 10, 11 |
| WF12 | 12 |
| The profile choice keeps its mechanics; class refusal codes go | 8 |
