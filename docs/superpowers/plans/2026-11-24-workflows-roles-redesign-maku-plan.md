# Workflows and roles redesign: Maku implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maku starts every task on the cheapest path that fits, says on every surface what will
run, why and what it may cost, steps a failed task up once, measures every role on every task, and
lets a platform team describe a workflow as one readable definition.

**Architecture:** Nine phases, A to I, each a Maku release with its own switch. A repairs the
shipped configuration without a new behaviour. B is display only: one card and one path strip built
from facts the task already holds. C wires the existing `stepUp` to a shipped ladder. D records what
each role changed, from events the factory already holds. E turns the `careful` bundle into stage
switches on the `loops` row. F adds `Task.spec.outcome`. G moves each act to where a person reads.
H files whole plans and runs disjoint parts in parallel. I collapses template, tier and row into one
`Factory.spec.workflows` entry and makes a role a file bound to a capability profile.

**Tech Stack:** Go (the `maku-factory`, `maku-broker`, `maku-slack` and `maku` binaries),
controller-gen CRDs, Helm charts, envtest, TypeScript for `web/` (tests under `web/test/`), Python
for the harness image (`images/maku-harness/`); `task check` is the gate.

**Spec:** [`docs/superpowers/specs/2026-11-24-workflows-roles-redesign-design.md`](../specs/2026-11-24-workflows-roles-redesign-design.md)
in ai-native-ref, with its [research](../specs/2026-11-24-workflows-roles-redesign-research.md).
Copy the spec and this plan into Maku's `docs/superpowers/` when execution starts. The adoption of
each release is the [adoption plan](2026-11-24-workflows-roles-redesign-adopt-plan.md).

**This plan runs in the Maku repository**, in a worktree from `origin/main`. Paths below are Maku's.
File and line references were read on `origin/main` at `20da5466` (v0.53.11 plus 22 commits); open
pull requests on the reconciler and the factory API may shift lines, so find each site by the
function it names.

## Global Constraints

- `task check` exits 0 before every commit (Maku `AGENTS.md`). Lint through `task lint` only.
- After any change under `api/` or to a `+kubebuilder` type: `task crd:gen`, and commit the generated
  CRDs, deepcopy and chart copies (`task crd:check` fails otherwise).
- After any change under `web/src/`: `task ui:test` and `task ui:build`, and commit the built assets
  (`task ui:check` fails otherwise). After any change under `images/maku-harness/`:
  `task harness:test`.
- Every `.go` file opens with `// SPDX-License-Identifier: Apache-2.0`.
- Commits are conventional, in English, with no trailers.
- Workflow names stay `quick`, `standard`, `careful`, and `none` for adopted pull requests (WR-O4).
  No fourth named workflow.
- "Workflow" in every string a person reads. API keys, refusal codes and metrics keep their names:
  `status.profile`, `spec.intake.profile`, `profile_*` codes, `agent_factory_*` metrics and their
  `profile` label (WR-O4).
- The reviewer stays on every pull-request task except `quick`; the gate's reviewer-verdict rule
  (`internal/factory/reconciler/arm.go`, `no_approving_verdict`, `reviewer_verdict_missing`) is not
  touched by any task here (WR-O3).
- One writer per branch, one run `Running` per room (L1 stands). No task adds a parallel writer on
  one branch.
- Budgets only narrow down the chain (WR12): a `Repository` may lower a ceiling or add a stage the
  platform allows, never raise a ceiling or remove a stage the platform requires.
- Every human wait is a task state with a reason, a default and a deadline, and holds no pod
  (WR13).
- Descriptions are at most 120 characters (`config.MaxDescription`).
- A removed or renamed key follows WF13: the release that replaces it accepts the old spelling with
  a warning in `Config.Warnings`; the next minor refuses it and names `docs/upgrading.md`.

## Departures from the spec

1. **`stepUp` sits beside `escalation`, not in place of it.** The spec's phase I writes
   `stepUp: careful` on a workflow; the code has `escalation: {outOfBudget, notConverged}`
   (`internal/factory/config/mergepolicy.go:60-62`). Phase C adds `stepUp` as the one-target form
   and keeps `escalation` for a platform that already steps two groups to two workflows. Setting
   both on one workflow is refused.
2. **The stage switches are keys of the `loops` row in phase E**, as the spec's "a `loops` row
   already holds most of the switches" says, so phase I can use the name `stages` for its ordered
   list without a second meaning.
3. **"Repository checks red at run end" has no end reason in the code.** The harness records the
   repository's checks as evidence and never ends a run on them (`images/maku-harness/agent_run.py`,
   `checks_failed` is a span error only). Task C1 settles which recorded failure stands for it.
4. **A class is known from the diff, a plan gate runs before any diff.** Phase E's
   `requires: [plan, tests]` on a `MergePolicy` class can bind only the class a task is predicted to
   belong to at triage. Task E1 settles what that prediction reads.
5. **The judge already reads no narrative.** `loop_policy.judge_input` takes the acceptance, the
   diff, the head's check runs and the required paths, and no message of the agent. Task E5 pins
   that with a test and adds the missing half: the repository checks' exit codes and counts.
6. **`maku start` is a tool of `maku mcp`, not a terminal command.** The spec's "`maku start
   --workflow`" is the tool's argument in Task B5 and a new terminal command in Task G4.

## Releases and switches

| Phase | Release | Switch | Default in the release |
|---|---|---|---|
| A | A | None: repairs. A platform that writes its own `loops.default` or `loops.careful` keeps it whole | — |
| B | B | None: display only. `profile_*` codes stay accepted and emitted | — |
| C | C | `workflows.<name>.stepUp` (a workflow name) and `Repository.spec.workflow.stepUp` (`auto`, `ask`, `off`) | Shipped `quick` and `standard` name a target; a repository is `auto` |
| D | D | None for recording. "Typical cost" shows on the card only from 30 merged tasks of the class | — |
| E | E | The row keys `ask`, `plan`, `tests`, `search`, `judge`, `review`, `split`; `scoper.planTier`; `loops.<row>.judgeInput`; `MergePolicy` `requires` | Presets resolve to today's runs, plus `ask` on |
| F | F | `Factory.spec.outcomes` (a list) and `Repository.spec.workflow.planGate` (`ask`, `auto`) | `[change]`; `ask` |
| G | G | The broker's `human.roomActs` (a list) | `[answer, retry]` |
| H | H | `intake.wholePlans` and `loops.<row>.split.parallel` (1 or 2) | `false`; `1` |
| I | I | `workflows.<name>.stages` (a list) and `Factory.spec.roles` | Absent: the phase E keys still apply |

A release may carry two phases when both are merged; the adoption plan takes them in this order.

## Pull requests

| Phase | PR | Tasks |
|---|---|---|
| A | A-1 | A1, A2, A3 |
| A | A-2 | A4 |
| A | A-3 | A5, A6 |
| B | B-1 | B1, B2 |
| B | B-2 | B3 |
| B | B-3 | B4, B5 |
| B | B-4 | B6, B7 |
| C | C-1 | C1, C2, C3 |
| C | C-2 | C4, C5 |
| C | C-3 | C6 |
| D | D-1 | D1, D2, D3 |
| D | D-2 | D4, D5 |
| E | E-1 | E1, E2 |
| E | E-2 | E3, E4 |
| E | E-3 | E5, E6 |
| E | E-4 | E7 |
| F | F-1 | F1, F2 |
| F | F-2 | F3 |
| F | F-3 | F4, F5, F6 |
| G | G-1 | G1, G2 |
| G | G-2 | G3 |
| G | G-3 | G4 |
| G | G-4 | G5, G6 |
| H | H-1 | H1, H2 |
| H | H-2 | H3, H4 |
| H | H-3 | H5 |
| I | I-1 | I1, I2 |
| I | I-2 | I3, I4 |
| I | I-3 | I5 |

## Review Focus

1. **A row that switches its own loop on inherits `judge: none` from the new default row and loses
   its judge.** `Loop.over` takes `default`'s judge when the row sets none
   (`internal/factory/config/evaluation.go`, `over`). A platform row `{continuations: 1}` reads
   `tier-light` today. Pinned by `TestARowThatSwitchesItsOwnLoopOnKeepsItsJudge` (Task A2).
2. **A claim with no `judgeModel` reaches the harness as the default judge.** `loop_policy.parse`
   fills an absent `judgeModel` with `tier-light`. If the pod's `AGENT_LOOP` omits the key instead of
   writing `none`, every `standard` run gains a judge and two continuations. Settled by Task A1
   before A2 is written.
3. **A platform's own `careful` row loses the tester when the constant goes.** Today the tester runs
   on the name `careful` whatever the row holds. Pinned by
   `TestACarefulRowWithoutTheKeyKeepsTheTesterAndWarns` (Task A4).
4. **A step-up that spends past what the person confirmed.** A Slack request capped below the
   stepped-up ceiling must ask. Pinned by `TestACappedTaskAsksBeforeItStepsUp` (Task C3), beside the
   existing `TestAStepRespectsTheSponsorCeiling`.
5. **A pinned task stepped past its pin.** Today a labelled task steps (`TestALabelledTaskSteps`).
   After phase C it asks. That test is rewritten, not deleted (Task C3).
6. **A reason on the card that quotes a model.** The card's reason is built from `status.profile`
   fields through a closed switch; the scoper's `why` stays in its own quoted block. Pinned by
   `TestTheReasonIsBuiltFromFactsOnly` (Task B1).
7. **An effect counted twice when a task is replayed.** The reconciler replays an end after a lost
   status write. Each effect is recorded behind `status.profile.counted`'s pattern. Pinned by
   `TestAStageEffectCountsOnce` (Task D1).
8. **A plan gate that holds a pod, or a task that waits for ever with no word.** Pinned by
   `TestThePlanGateHoldsNoRun` and `TestAnExpiredPlanGateSaysItIsParked` (Task F3).
9. **A `review` outcome whose verdict reaches the merge gate.** Pinned by
   `TestTheGateIgnoresAVerdictOnAForeignPullRequest` (Task F4).
10. **Two parts running at once on overlapping files.** Pinned by
    `TestPartsWithASharedFileNeverRunTogether` (Task H3).
11. **A custom role that writes.** A role file bound to `read` gets the reviewer's read-only token,
    whatever its brief says. Pinned by `TestACustomRoleNeverGetsAWriteToken` (Task I3).

---

## Phase A · Repair the shipped model

Release A. No new behaviour beyond what the documentation already claims. No switch: a platform
that writes its own `loops.default` or `loops.careful` keeps its entry whole
(`FillShippedWorkflows` adds a shipped entry only when its key is absent).

### Task A1: Investigation: may a row set a stall rule with `judge: none`?

**Files (read only):**
- `internal/factory/config/config.go` (`Loop.On`, `LoopFor`, near `:2516-2545`)
- `internal/factory/reconciler/reconciler.go` (`profileSpec`, `:1186-1212`)
- `internal/factory/runs/runs.go` (`Loop`, `:158-163`; the claim's `spec.loop`, `:262-275`)
- The composition or pod builder that turns the claim's `spec.loop` into the `AGENT_LOOP`
  environment variable: find it with `git grep -n AGENT_LOOP -- charts internal images`
- `images/maku-harness/loop_policy.py` (`parse`, `decide`) and `images/maku-harness/agent_run.py`
  (the loop's end, `if code or policy.judge_model is None: return code, None, ""`)

What is already known from the first four files: `Loop.On()` is true as soon as `stallSteps` is set;
`LoopFor` then resolves `continuations: 2` and, for `judge: none`, `JudgeModel: ""`; the claim
writes no `judgeModel` for an empty one; a harness whose policy has no judge returns at the end of
the conversation and sends no continuation. So the stall rule alone is expressible in config.

The open link is the pod: `loop_policy.parse` defaults an absent `judgeModel` to `tier-light`.

- [ ] **Step 1: Read the builder and write down which of the two it does**

| What the builder writes for a claim with no `judgeModel` | What it changes in Task A2 |
|---|---|
| `"judgeModel": "none"` in `AGENT_LOOP` | Nothing: A2 is a config change only |
| No `judgeModel` key | A2 also changes `runs.go` to write `"judgeModel": "none"` when `JudgeModel == ""`, with a test in `internal/factory/runs/runs_test.go` asserting the claim's `spec.loop.judgeModel` is `none`, and the builder is left alone |

- [ ] **Step 2: Prove it with the harness's own test**

Add to `images/maku-harness/tests/test_loop_policy.py`:

```python
def test_a_stall_rule_with_no_judge_sends_no_continuation(self):
    policy = loop_policy.parse('{"stallSteps": 80, "continuations": 2, "judgeModel": "none"}')
    self.assertIsNone(policy.judge_model)
    self.assertEqual(policy.stall_steps, 80)
```

Run: `task harness:test`
Expected: PASS. It documents the contract A2 relies on.

- [ ] **Step 3: Record the answer** in the pull request description of A-1, with the file and line
  of the builder. No commit of its own: the test rides with Task A2.

### Task A2: The stall rule in every workflow

**Files:**
- Modify: `internal/factory/config/workflows.go:36-40` (`ShippedWorkflows`, the `default` row)
- Modify: `internal/factory/config/evaluation.go` (`Loop.over`)
- Modify: `internal/factory/runs/runs.go:262-275` only if Task A1 says so
- Modify: `internal/install/testdata/golden/generic/factory/factory.yaml` (the golden `loops`)
- Modify: `docs/reference/config.md` (the `loops` rows), `docs/factory.md` (the shipped YAML block)
- Test: `internal/factory/config/workflows_test.go`, `internal/factory/config/loops_test.go`,
  `internal/factory/reconciler/loop_test.go`

**Interfaces:**
- Consumes: Task A1's answer.
- Produces: `c.LoopFor("default")`, and so `LoopFor` of `quick` and `standard`, returns
  `&LoopPolicy{StallSteps: 80, Continuations: 2, JudgeModel: ""}` on a `Factory` that writes no
  `loops.default`. `careful` is unchanged.

The shipped row after the change:

```yaml
loops:
  default: {scope: "off", stallSteps: 80, judge: none}
```

- [ ] **Step 1: Write the failing tests**

In `workflows_test.go`:

```go
func TestTheShippedDefaultRowStopsARunThatCommitsNothing(t *testing.T) {
	c := mustParse(t, noTemplates) // the fixture writes no loops block, so the shipped rows fill in
	for _, name := range []string{"quick", "standard"} {
		p, _ := c.Workflow(name)
		lp := c.LoopFor(c.RowFor(name, p))
		if lp == nil || lp.StallSteps != DefaultStallSteps || lp.JudgeModel != "" {
			t.Fatalf("%s: %+v, want the stall rule and no judge", name, lp)
		}
	}
	p, _ := c.Workflow("careful")
	if lp := c.LoopFor(c.RowFor("careful", p)); lp == nil || lp.JudgeModel != DefaultJudge {
		t.Fatalf("careful lost its judge: %+v", lp)
	}
}

func TestAPlatformsDefaultRowIsKeptWhole(t *testing.T) {
	c := mustParse(t, good+`loops:
  default: {scope: "off"}
`)
	if lp := c.LoopFor("default"); lp != nil {
		t.Fatalf("the platform's default row gained a loop: %+v", lp)
	}
}
```

In `loops_test.go`:

```go
func TestARowThatSwitchesItsOwnLoopOnKeepsItsJudge(t *testing.T) {
	c := mustParse(t, good+`loops:
  default: {scope: "off", stallSteps: 80, judge: none}
  standard: {continuations: 1}
  careful: {scope: scoper}
`)
	if p := c.LoopFor("standard"); p == nil || p.JudgeModel != DefaultJudge || p.Continuations != 1 {
		t.Fatalf("a row with its own loop key lost the design's judge: %+v", p)
	}
	if p := c.LoopFor("careful"); p == nil || p.JudgeModel != "" || p.StallSteps != 80 {
		t.Fatalf("a row with no loop key must take default's stall rule and no judge: %+v", p)
	}
}
```

In `internal/factory/reconciler/loop_test.go`, beside `TestALoopEndEscalatesWithItsReason`:

```go
func TestAStandardTaskCarriesTheStallRuleAndNoJudge(t *testing.T) {
	cf := resolveCfg("observe", 0) // the package's config helper; its loops block is removed for this test
	delete(cf.Loops, "default")
	cf.HarnessProfiles, cf.Templates, cf.Loops = config.FillShippedWorkflows(cf.HarnessProfiles, cf.Templates, cf.Loops, false)
	tk := issueTask("3buqdlot", 7, "fix it")
	g := newRig(t, tk, roomOf("3buqdlot"))
	p, _ := cf.Workflow("standard")
	g.r.profileSpec(cf, tk, "standard", p)
	if l := tk.Spec.Loop; l == nil || l.StallSteps != 80 || l.JudgeModel != "" {
		t.Fatalf("spec.loop = %+v", l)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run 'ShippedDefaultRow|PlatformsDefaultRow|SwitchesItsOwnLoopOn' ./internal/factory/reconciler -run StandardTaskCarries`
Expected: FAIL (`LoopFor` of `quick` is nil; the `standard` row reads `JudgeModel: ""`).

- [ ] **Step 3: Implement**

In `ShippedWorkflows`:

```go
stall := int32(DefaultStallSteps)
loops = map[string]Loop{
	"default": {Scope: ScopeOff, StallSteps: &stall, Judge: NoJudge},
	// careful unchanged in this task
}
```

In `Loop.over`, replace `out.Judge = cmp.Or(out.Judge, def.Judge)`:

```go
// A row that sets a loop key of its own never inherits default's "no judge": it read the
// design's judge before default carried the stall rule, and keeps it.
if out.Judge == "" && !(def.Judge == NoJudge && (l.StallSteps != nil || l.Continuations != nil)) {
	out.Judge = def.Judge
}
```

Apply Task A1's `runs.go` change if its table says so. Regenerate the installer's golden with the
package's update flag (`go test ./internal/install -run Golden -update`) and read the diff: only
the `loops.default` line changes.

- [ ] **Step 4: Run the tests, then the package and its dependents**

Run: `go test ./internal/factory/... ./internal/install/... && task harness:test`
Expected: PASS. `TestLoopFor`'s `"quick": nil` row stays true: that test writes its own
`default: {}`.

- [ ] **Step 5: Update the two pages and commit**

`docs/reference/config.md` and the YAML block in `docs/factory.md` show the new `default` row and
one sentence: "`quick` and `standard` end a run that commits nothing in 80 steps; only `careful`
runs the completion judge."

```bash
git add internal images docs
git commit -m "fix(factory): quick and standard stop a run that commits nothing"
```

### Task A3: The `careful` split is reachable

**Files:**
- Modify: `internal/factory/config/workflows.go:38-39` (the shipped `careful` row)
- Modify: `docs/reference/config.md` (the `split.anyTier` line), `docs/factory.md`
- Test: `internal/factory/config/workflows_test.go`, `internal/factory/reconciler/split_test.go`

**Interfaces:**
- Produces: on a factory with a meter, prices and `runs.gatewayIdentity`,
  `c.SplitFor(repo, class, "careful").AnyTier == true`, so `splitAtTriage` offers a split to a
  `careful` task whose classification is `standard`.

- [ ] **Step 1: Write the failing tests**

```go
func TestTheShippedCarefulSplitNeedsNoClassifier(t *testing.T) {
	_, _, loops := ShippedWorkflows()
	if s := loops[WorkflowCareful].Split; s == nil || !s.AnyTier || s.MaxChildren != 4 {
		t.Fatalf("split = %+v, want anyTier with four parts", s)
	}
}
```

In `split_test.go`, beside `TestSplitAnyTierOffersEveryTier`, a case that builds the config from
`config.FillShippedWorkflows(nil, nil, nil, true)` over the package's base config, triages a task
labelled `workflow:careful` with the static classification `standard`, and asserts
`tk.Spec.Split != nil && tk.Spec.Split.MaxChildren == 4`. Name it
`TestAShippedCarefulTaskIsOfferedASplitAtStandard`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run ShippedCarefulSplit ./internal/factory/reconciler -run ShippedCarefulTask`
Expected: FAIL (`AnyTier` is false; `Spec.Split` is nil).

- [ ] **Step 3: Implement**

```go
WorkflowCareful: {Scope: ScopeScoper, Judge: DefaultJudge, Search: true,
	Split: &SplitPolicy{MaxChildren: 4, ChildTier: DefaultChildTier, AnyTier: true}},
```

The installer's golden does not change: a generic install has no priced meter, so
`FillShippedWorkflows` drops the row's `split`.

- [ ] **Step 4: Run the tests and commit**

Run: `go test ./internal/factory/... ./internal/install/...`
Expected: PASS.

```bash
git add internal docs
git commit -m "fix(factory): the shipped careful row offers a split without a classifier"
```

### Task A4: The tester follows a row key, not the name `careful`

**Files:**
- Modify: `internal/factory/config/config.go` (`Loop`, near `:2330-2356`: a `Tests` key and its
  `testsSet` twin, as `Search` has `searchSet`)
- Modify: `internal/factory/config/evaluation.go` (`over`, `UnmarshalJSON`)
- Modify: `internal/factory/config/workflows.go:38-39` (shipped row), `:112-116` (`TestFirstIn`)
- Modify the five callers of `TestFirstIn`: `internal/factory/catalogue/catalogue.go:194`,
  `internal/factory/reconciler/profile.go:48` and `:163`,
  `internal/factory/reconciler/reconciler.go:1242` and `:1250`,
  `internal/factory/reconciler/tester.go` (`testFirstOn`)
- Modify: `docs/reference/config.md`, `docs/factory.md` (the tester's line)
- Test: `internal/factory/config/tester_test.go`, `internal/factory/reconciler/profile_test.go`

**Interfaces:**
- Produces: `func (c *Config) TestFirstIn(r *Repository, workflow string) bool`: the repository
  opts in (`workflow.testFirst`) and the row the workflow reads (`RowFor`, `rowOf`) sets
  `tests: true`. The method on `*Repository` is removed. Phase E reuses the `tests` key as a stage
  switch.

- [ ] **Step 1: Write the failing tests**

In `tester_test.go`:

```go
func TestTheTesterFollowsTheRowKey(t *testing.T) {
	c := mustParse(t, good+`workflows:
  thorough: {template: pair, loop: thorough}
loops:
  thorough: {tests: true}
`)
	r := &Repository{Workflow: RepositoryWorkflow{TestFirst: true}}
	if !c.TestFirstIn(r, "thorough") {
		t.Fatal("a custom workflow whose row sets tests runs no tester")
	}
	if c.TestFirstIn(r, "standard") {
		t.Fatal("standard runs the tester")
	}
	if c.TestFirstIn(&Repository{}, "thorough") {
		t.Fatal("the repository did not opt in")
	}
}

func TestTheShippedCarefulRowSetsTests(t *testing.T) {
	c := mustParse(t, noTemplates)
	if !c.TestFirstIn(&Repository{Workflow: RepositoryWorkflow{TestFirst: true}}, "careful") {
		t.Fatal("careful lost its tester")
	}
}

func TestACarefulRowWithoutTheKeyKeepsTheTesterAndWarns(t *testing.T) {
	c := mustParse(t, good+`loops:
  careful: {scope: scoper}
`)
	if !c.TestFirstIn(&Repository{Workflow: RepositoryWorkflow{TestFirst: true}}, "careful") {
		t.Fatal("a platform's careful row lost the tester in the release that adds the key")
	}
	want := "loops.careful: set tests: true to keep the tester; read by key from the next minor"
	if !slices.ContainsFunc(c.Warnings, func(w string) bool { return strings.Contains(w, want) }) {
		t.Fatalf("no warning; got %v", c.Warnings)
	}
}
```

`TestTestFirstFollowsTheRepository` in `profile_test.go` keeps its assertions; its calls move to the
new signature.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run 'TesterFollowsTheRowKey|ShippedCarefulRowSetsTests|CarefulRowWithoutTheKey'`
Expected: FAIL to compile (`c.TestFirstIn` undefined, unknown field `tests`).

- [ ] **Step 3: Implement**

```go
// Tests starts a public task of the row with the tester when its repository opts in
// (Repository.spec.workflow.testFirst); absent is off. It never switches the loop on.
Tests bool `json:"tests,omitempty"`
testsSet bool `json:"-"`
```

```go
// TestFirstIn is whether a public task of r running workflow starts with the tester: the
// repository opts in, and the workflow's row sets tests. A repository not served (nil) runs none.
func (c *Config) TestFirstIn(r *Repository, workflow string) bool {
	if r == nil || !r.Workflow.TestFirst {
		return false
	}
	p, _ := c.Workflow(workflow)
	return c.rowOf(c.RowFor(workflow, p)).Tests
}
```

`over` inherits `Tests` as it inherits `Search`. In `Parse`, after the rows are read: a row named
`careful` that the platform wrote with no `tests` key is given `Tests: true` and the warning above.
The shipped `careful` row sets `Tests: true`. `RepositoryWorkflow.TestFirst`'s comment drops the
word "careful": "starts every public task whose workflow's row sets `tests`".

- [ ] **Step 4: Run the tests, regenerate, run the gate**

Run: `task crd:gen && go test ./internal/factory/... ./internal/install/... && task check`
Expected: PASS; the `Factory` CRD gains `loops.<row>.tests`.

- [ ] **Step 5: Commit**

```bash
git add api internal charts config docs
git commit -m "fix(factory): the tester follows the row's tests key, not the name careful"
```

### Task A5: `maku start` stops applying the dead `class:` label

**Files:**
- Modify: `internal/maku/start.go:89-102` (`planLabels`)
- Modify: `docs/cli.md` (the line "the plan's `class:<name>` label", near `:157`)
- Read: `internal/factory/intake/publish.go:142-151`, which also applies `class:<class>`
- Test: `internal/maku/start_test.go`

**Interfaces:**
- Produces: `planLabels()` returns `["workflow:<p>"]` when a maintainer's plan pins a workflow, and
  nothing otherwise. The class still travels in `spec.intake.class`
  (`internal/factory/triage/classify.go:213-226`).

- [ ] **Step 1: Write the failing test**

```go
func TestStartAppliesNoClassLabel(t *testing.T) {
	yes := true
	for name, tc := range map[string]struct {
		profile string
		want    []string
	}{
		"the factory's choice": {"", nil},
		"a pinned workflow":    {"careful", []string{"workflow:careful"}},
	} {
		t.Run(name, func(t *testing.T) {
			g := governed{planShape: planShape{Maintainer: &yes}}
			g.view.Issues = []planIssue{{Class: "docs", Profile: tc.profile}} // the view's own issue type
			if got := g.planLabels(); !slices.Equal(got, tc.want) {
				t.Fatalf("labels = %v, want %v", got, tc.want)
			}
		})
	}
}
```

Use the field and type names `start.go` declares for the plan view; the assertion is the point: no
element starts with `class:`.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/maku -run StartAppliesNoClassLabel`
Expected: FAIL (`[class:docs]`, `[class:docs workflow:careful]`).

- [ ] **Step 3: Implement**

```go
// planLabels are the labels start applies before factory/ready: workflow:<p> when the plan pins
// one, unless the catalogue says this developer does not maintain the repository.
func (g *governed) planLabels() []string {
	is := g.view.Issues[0]
	if is.Profile == "" || (g.Maintainer != nil && !*g.Maintainer) {
		return nil
	}
	return []string{"workflow:" + is.Profile}
}
```

Then read `publish.go:142-151`. If triage's "no longer read" notice
(`internal/factory/triage/classify.go:160-163`) fires for an issue that route files, remove the
label there too in this commit, with a case in `internal/factory/intake/publish_test.go` asserting
the filed labels hold the marker only. If the notice does not fire for it (the route files with a
marker triage recognises), leave it and say so in the commit body.

- [ ] **Step 4: Run the tests and commit**

Run: `go test ./internal/maku/... ./internal/factory/intake/...`
Expected: PASS.

```bash
git add internal docs/cli.md
git commit -m "fix(start): stop applying the class label triage no longer reads"
```

### Task A6: Maku's pages and one error text say what the code does

**Files:**
- Modify: `docs/factory.md:148` (the classifier sentence), `docs/roadmap.md:14` (the "Design, open
  (#443)" row), `docs/concepts.md:52` (run role) and `:64` (verdict), `docs/cli.md:203-205` (codes
  the upgrade notes call gone) and `:213` (the sample line "Workflow standard (scoper, implementer,
  reviewer)")
- Modify: `internal/factory/config/config.go:1988` (the error text that lists `trio`)
- Test: `internal/factory/config/config_test.go`

- [ ] **Step 1: Write the failing test**

```go
func TestAnUnknownTemplateNamesTheThreeThatExist(t *testing.T) {
	_, err := Parse([]byte(strings.Replace(good, "  solo: {roles: [implementer]}", "  duo: {roles: [implementer]}\n  solo: {roles: [implementer]}", 1)))
	if err == nil || strings.Contains(err.Error(), "trio") || !strings.Contains(err.Error(), "solo, pair, investigate") {
		t.Fatalf("got %v", err)
	}
}
```

Run: `go test ./internal/factory/config -run UnknownTemplateNames`
Expected: FAIL (the text lists `trio`).

- [ ] **Step 2: Fix the text and the five page sites**

| Site | Now reads |
|---|---|
| `config.go:1988` | `template %s is not one of solo, pair, investigate` |
| `docs/factory.md:148` | Every task is rated `standard`; no classifier is called. `triage.controlPercent` sends that share to `frontier` |
| `docs/roadmap.md:14` | The row is removed: the suggestion and the override at intake are built (`internal/maku/start.go`) |
| `docs/concepts.md:52` | A run's role is one of four: `implementer`, `reviewer`, `tester`, `triager`. The scoper is a `triager` run; the judge is a model call inside the implementer's run, not a run |
| `docs/concepts.md:64` | The reviewer's `approve` or `changes` |
| `docs/cli.md:203-205`, `:213` | The codes listed are `profile_unknown`, `profile_conflict`, `not_maintainer`, `profile_no_tests_paths`; the sample reads "Workflow standard (implementer, reviewer)" |

- [ ] **Step 3: Run the gate and commit**

Run: `task check`
Expected: exit 0 (`task docs` and `task names` included).

```bash
git add internal docs
git commit -m "docs: the classifier, the run roles and the workflow sample match the code"
```

---

## Phase B · One card, one strip, one vocabulary

Release B. Display only: no task changes what runs. No switch. Every string a person reads says
"workflow"; `profile_*` codes stay accepted and emitted in the API.

The card, in every format:

```text
Fix the broken link checker on the docs site          smana/ai-native-ref
Workflow   standard · this repository's default
Will run   implementer → reviewer → CI → merge gate
Cost       up to $5.10 · up to $13.60 if it steps up
```

The "if it steps up" half appears only when the workflow names a step-up target (phase C). Until
then the line is "up to $5.10".

### Task B1: The card as one model, built from facts

**Files:**
- Create: `internal/roomview/workflowcard.go`
- Modify: `internal/factory/catalogue/catalogue.go:114-129` (`Profile`), `:185-207`
  (`ceilingOf`, `profileOf`)
- Modify: `internal/envelope/payloads.go` (`ProfileFact`, the task facts' `profile`)
- Modify: `internal/factory/reconciler/facts.go` (where `ProfileFact` is filled)
- Test: `internal/roomview/workflowcard_test.go`, `internal/factory/catalogue/catalogue_test.go`

**Interfaces:**
- Produces, in `catalogue.Profile`: `CeilingUSD float64` (`json:"ceilingUSD"`), the task ceiling of
  the tier the workflow resolves to; `StepUp string` and `StepUpCeilingUSD float64`
  (`json:"stepUp,omitempty"`, `json:"stepUpCeilingUSD,omitempty"`), zero until phase C;
  `Path []string` (`json:"path"`), the roles in run order with `CI` and `merge gate` appended, the
  scoper and tester included when the row runs them.
- Produces, in `ProfileFact`: `Source`, `By` (the login of a pin's applier), `Recommended`,
  `Refused`, `CeilingMicroUSD`, `StepUpCeilingMicroUSD`, `Description`. Add only the fields the
  type lacks.
- Produces, in `roomview`:

```go
// WorkflowCard is the four facts every surface shows where a task is named (WR3).
type WorkflowCard struct {
	Title, Repository string
	Workflow, Reason  string   // Reason is built by Reason(), never model text
	Path              []string // implementer, reviewer, CI, merge gate
	CeilingUSD        float64
	StepUpUSD         float64 // 0: no step-up line
	TypicalUSD        float64 // 0 until phase D has data for the class
}

func CardOf(f *envelope.TaskFacts, title string) WorkflowCard
func CardOfPlan(c catalogue.Catalogue, workflow, source, by, suggested string) WorkflowCard
func Reason(source, by, recommended, trigger string, paths []string) string
func WorkflowCardText(w io.Writer, c WorkflowCard, o Options) error // Plain, Markdown, Slack
```

The reasons, a closed switch on `status.profile.source`:

| Source | Reason |
|---|---|
| `repository`, `floor`, `control` | `this repository's default` |
| `label` | `pinned by @<by>` |
| `schedule` | `this schedule's workflow` |
| `revert` | `a revert` |
| `oracle` | `a finding a check verifies` |
| `treatment` | `the comparison's second arm` |
| `scoper` | `the scoper recommended it` |
| `escalation` | `stepped up after <trigger words>` |

When `recommended` is set and differs from the workflow, the reason gains
`; the planner suggested <recommended>`.

- [ ] **Step 1: Write the failing tests**

```go
func TestTheReasonIsBuiltFromFactsOnly(t *testing.T) {
	for _, tc := range []struct{ source, by, rec, trigger, want string }{
		{"repository", "", "", "", "this repository's default"},
		{"repository", "", "quick", "", "this repository's default; the planner suggested quick"},
		{"label", "alice", "", "", "pinned by @alice"},
		{"escalation", "", "", "stalled", "stepped up after a run that committed nothing"},
		{"something-new", "", "", "", "this repository's default"}, // an unknown source never prints itself
	} {
		if got := Reason(tc.source, tc.by, tc.rec, tc.trigger, nil); got != tc.want {
			t.Errorf("Reason(%q) = %q, want %q", tc.source, got, tc.want)
		}
	}
}

func TestTheCardInPlainText(t *testing.T) {
	var b strings.Builder
	c := WorkflowCard{Title: "Fix the link checker", Repository: "owner/repo", Workflow: "standard",
		Reason: "this repository's default", Path: []string{"implementer", "reviewer", "CI", "merge gate"},
		CeilingUSD: 5.10}
	if err := WorkflowCardText(&b, c, Options{Format: Plain}); err != nil {
		t.Fatal(err)
	}
	want := "Workflow   standard · this repository's default\n" +
		"Will run   implementer → reviewer → CI → merge gate\n" +
		"Cost       up to $5.10\n"
	if !strings.HasSuffix(b.String(), want) || strings.Contains(b.String(), "tier") {
		t.Fatalf("got:\n%s", b.String())
	}
}

func TestTheCardNamesTheStepUpCeiling(t *testing.T) { // StepUpUSD: 13.60
	// asserts the cost line is "Cost       up to $5.10 · up to $13.60 if it steps up"
}
```

In `catalogue_test.go`, `TestAProfileCarriesItsCeilingAndPath`: on the package's base config,
`Build(cfg, repo, true).Profiles["careful"]` has `CeilingUSD` equal to the `frontier` tier's
`taskUSD` and `Path` equal to `[scoper, implementer, reviewer, CI, merge gate]`; `quick` has
`[implementer, CI, merge gate]`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/roomview -run 'Reason|TheCard' ./internal/factory/catalogue -run CeilingAndPath`
Expected: FAIL to compile.

- [ ] **Step 3: Implement**

`profileOf` resolves the tier as `profileSpec` does (the workflow's tier when above `standard`,
else `standard`) and reads `cfg.Tiers[tier].TaskUSD`. `Path` is built from `cfg.ScopeFor(row)`,
`cfg.TestFirstIn(rc, name)` and the template's roles. `Reason` maps the trigger through the
reason words `internal/factory/narrate/narrate.go` already holds (`reasons()`), so "stalled" reads
the same in the card and in the end comment. Dollars use the two-decimal form of
`internal/maku/start.go`'s `dollars`, moved to `roomview` and called from both.

- [ ] **Step 4: Run the tests and commit**

Run: `go test ./internal/roomview/... ./internal/factory/catalogue/... ./internal/envelope/... ./internal/maku/...`
Expected: PASS.

```bash
git add internal
git commit -m "feat(roomview): one workflow card, built from the task's facts"
```

### Task B2: The path strip as text

**Files:**
- Modify: `internal/summary/flow.go` (beside `flowView`, `:334`)
- Modify: `internal/roomview/card.go` (`Card`, `:133`; `facts`, `:257`)
- Modify: `internal/factory/narrate/status.go:29` (`Status`)
- Modify: `internal/slackapp/answers.go` (the `status` reply)
- Test: `internal/summary/flow_test.go`, `internal/roomview/card_test.go`,
  `internal/factory/narrate/status_test.go`

**Interfaces:**
- Produces: `func Strip(f *Flow) string` in `internal/summary`: one node per run, by persona, then
  the plan's ghosts, joined by ` · `, with `✓` done, `●` running, `✗` failed or stopped, `○`
  planned: `scoper ✓ · implementer ● · reviewer ○`. Closed review rounds fold as the rail folds them:
  `round 2 · implementer ✓ → reviewer ●`. Empty for a flow with no node and no plan.
- Produces: `narrate.StatusFacts{Workflow, Reason, Strip string; CeilingMicroUSD int64}` passed to
  `Status`, which gains two lines.

- [ ] **Step 1: Write the failing tests**

```go
func TestTheStripNamesDoneRunningAndPlanned(t *testing.T) {
	f := &Flow{Plan: []string{"scoper", "implementer", "reviewer"}, Nodes: []FlowNode{
		{Persona: "scoper", Outcome: "succeeded"},
		{Persona: "implementer"}, // no outcome: running
	}}
	if got, want := Strip(f), "scoper ✓ · implementer ● · reviewer ○"; got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}

func TestTheStripUsesThePersonaNotTheRole(t *testing.T) { // Role "triager", Persona "scoper"
	f := &Flow{Nodes: []FlowNode{{Persona: "scoper", Role: "triager", Outcome: "succeeded"}}}
	if got := Strip(f); strings.Contains(got, "triager") {
		t.Fatalf("got %q", got)
	}
}
```

In `status_test.go`:

```go
func TestTheStatusCommentCarriesTheWorkflowAndThePath(t *testing.T) {
	body := Status(statusTask(), "https://rooms.example", StatusFacts{Workflow: "standard",
		Reason: "this repository's default", Strip: "implementer ● · reviewer ○", CeilingMicroUSD: 5_100_000})
	for _, want := range []string{"Workflow: standard · this repository's default · up to $5.10", "Path: implementer ● · reviewer ○"} {
		if !strings.Contains(body, want) {
			t.Errorf("missing %q in:\n%s", want, body)
		}
	}
	if strings.Contains(body, "spent") { // the comment still omits live spend
		t.Fatal("the status comment carries live spend")
	}
}
```

In `card_test.go`, `TestTheStatusCardLeadsWithTheWorkflow`: `Card` on a summary whose facts carry a
profile prints the three card lines of Task B1 before `Run`, and a `Path` line holding the strip.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/summary -run TheStrip ./internal/factory/narrate -run StatusCommentCarries ./internal/roomview -run StatusCardLeads`
Expected: FAIL to compile.

- [ ] **Step 3: Implement**

`Strip` walks `flowView`'s nodes and `ghostsAfter`'s remainder (the cursor `web/src/flow.ts`
mirrors). `Status` keeps its variadic `mergeByApproval` and takes `StatusFacts` as a new third
parameter; its two callers in `internal/factory/reconciler/status_comment.go` build the facts from
`t.Status.Profile` and the room's summary. The ceiling is a stable fact; live spend stays out, as
the function's comment says. The Slack `status` reply appends the strip as its last line.

- [ ] **Step 4: Run the tests and commit**

Run: `go test ./internal/summary/... ./internal/roomview/... ./internal/factory/narrate/... ./internal/factory/reconciler/... ./internal/slackapp/...`
Expected: PASS.

```bash
git add internal
git commit -m "feat(summary): the task's path as one line on the card, the status comment and Slack"
```

### Task B3: GitHub says the workflow before the first run, in dollars, by role

**Files:**
- Modify: `internal/factory/narrate/narrate.go:377-384` (`Started`), `:1190-1214`
  (`ProfileChosen`), `:1218-1221` (`ProfileRefused`)
- Modify: `internal/factory/reconciler/reconciler.go` (`received`, after `notePin`, `:1146-1184`)
- Modify: `internal/factory/reconciler/profile.go` (where `ProfileChosen` is narrated after the
  scoper's end)
- Modify: `docs/reference/narration.md` (the `profile_chosen` row and the run-start sample)
- Test: `internal/factory/narrate/narrate_test.go`, `internal/factory/reconciler/profile_test.go`

**Interfaces:**
- Consumes: `roomview.CardOf`, `roomview.WorkflowCardText` (Task B1).
- Produces: `narrate.TaskCard(t, card roomview.WorkflowCard) Event` with key `task-card`, posted
  once at triage, before any run. `ProfileChosen` keeps its key `profile-chosen-<run>` and is
  posted only when the workflow changes after the card (a scoper pick under `evaluation.mode:
  apply`, a step-up), so a default task gets one comment, not two.
- Produces: `Started` prints the run's persona and dollars:

```text
Maku task `3buqdlot` started the scoper's run `r-01` on branch `agent/3buqdlot`.

- Budget: up to $2.55 for this run, 45 minutes
- Watch: https://rooms.example/r/3buqdlot (tailnet only)
- Stop: apply the label `factory/stop`
```

  A run the meter cannot price keeps its token figure: "Budget: 1.5 M tokens, 45 minutes".

- [ ] **Step 1: Write the failing tests**

```go
func TestTheRunStartNamesThePersonaAndDollars(t *testing.T) {
	tk := narrated("3buqdlot") // the package's task fixture
	tk.Spec.Budget.Tier, tk.Spec.Budget.RunMicroUSD = "standard", 2_550_000
	ev := Started(tk, runs.Spec{RunID: "r-01", Role: "triager", Persona: "scoper", Branch: "agent/3buqdlot", MaxMinutes: 45}, "https://rooms.example")
	if !strings.Contains(ev.Body, "the scoper's run") || !strings.Contains(ev.Body, "up to $2.55 for this run") {
		t.Fatalf("got:\n%s", ev.Body)
	}
	for _, bad := range []string{"(triager)", "tier ", "tokens"} {
		if strings.Contains(ev.Body, bad) {
			t.Errorf("the run-start comment says %q", bad)
		}
	}
}

func TestTheTaskCardIsPostedBeforeTheFirstRun(t *testing.T) {
	ev := TaskCard(narrated("3buqdlot"), roomview.WorkflowCard{Workflow: "standard",
		Reason: "this repository's default", Path: []string{"implementer", "reviewer", "CI", "merge gate"}, CeilingUSD: 5.10})
	if ev.Key != "task-card" || !strings.Contains(ev.Body, "To change it, a maintainer applies the label `workflow:<name>` before `factory/ready`") {
		t.Fatalf("%s:\n%s", ev.Key, ev.Body)
	}
}
```

In `profile_test.go`, `TestADefaultTaskGetsOneWorkflowComment`: after `received()` the outbox holds
`task-card` and no `profile-chosen-`; after a `careful` task's scoper ends under `observe`, it still
holds no `profile-chosen-`.

If `runs.Spec` carries no persona, add `Persona string` to it, filled where the reconciler builds
each spec (`startScoper` sets `scoper`; every other run sets its role).

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/narrate -run 'RunStartNames|TaskCardIsPosted' ./internal/factory/reconciler -run DefaultTaskGetsOne`
Expected: FAIL.

- [ ] **Step 3: Implement**, then update the two samples in `docs/reference/narration.md`.

- [ ] **Step 4: Run the gate and commit**

Run: `go test ./internal/factory/... && task check`
Expected: PASS. Golden narration fixtures that hold "(tier standard)" are updated in this commit.

```bash
git add internal docs
git commit -m "feat(narrate): the workflow, its reason and its ceiling before the first run"
```

### Task B4: The Slack plan message carries the card and a described select

**Files:**
- Modify: `internal/slackapp/proposal.go:405-431` (the sections), `:504` (the header)
- Modify: `internal/slackapp/pin.go:87-110` (`pinBlock`), `:27-32` (`pinSelect`)
- Modify: `internal/humanapi/handoff.go:419-432`, `:720-739` (the pins a re-validation returns)
- Modify: `docs/slack.md` (the plan message sample, near `:150`)
- Test: `internal/slackapp/pin_test.go`, `internal/slackapp/proposal_test.go`

**Interfaces:**
- Consumes: `catalogue.Profile.{Description, CeilingUSD, Path}` (Task B1).
- Produces: `pinSelect.Options []pinOption{Name, Description string; CeilingUSD float64}`; the
  broker returns the same three per offered workflow in `ProposalPayload.Pins`. The wire value of
  an option does not change (`profileValue`), so a select drawn by release A's app still pins.
- Slack's limits bind the text: an option's `text` and `description` hold 75 characters each.

The select's options:

| `text` | `description` |
|---|---|
| `Factory's choice: standard` | `An implementer and a reviewer. The default. Up to $5.10` |
| `quick` | `One implementer. For changes a check can verify. Up to $5.10` |
| `careful` | `Scoped first, judged before review. Up to $13.60` |

A description is cut at a word boundary to leave room for ` Up to $NN.NN`.

- [ ] **Step 1: Write the failing tests**

```go
func TestThePinSelectDescribesEachWorkflow(t *testing.T) {
	b := pinBlock("sha256:abc", 1, pinSelect{Workflow: "standard", Options: []pinOption{
		{Name: "quick", Description: "One implementer. For changes a check can verify.", CeilingUSD: 5.10},
		{Name: "careful", Description: "Scoped first, judged before review. For wide or unclear tasks.", CeilingUSD: 13.60},
	}})
	sel := b.Elements[0].(slackSelect)
	if got := sel.Options[0].Text.Text; got != "Factory's choice: standard" {
		t.Fatalf("first option %q", got)
	}
	for _, o := range sel.Options[1:] {
		if o.Description == nil || !strings.Contains(o.Description.Text, "Up to $") || len([]rune(o.Description.Text)) > 75 {
			t.Errorf("option %q: description %+v", o.Text.Text, o.Description)
		}
		if strings.HasPrefix(o.Text.Text, "Workflow: ") {
			t.Errorf("a bare name: %q", o.Text.Text)
		}
	}
}

func TestAnOldOptionValueStillPins(t *testing.T) {
	if _, p, ok := cutProfileValue(profileValue("sha256:abc", 1, "careful")); !ok || p != "careful" {
		t.Fatal("the option's value changed shape")
	}
}
```

In `proposal_test.go`, `TestTheProposalShowsTheCard`: the rendered blocks hold the three card lines
of Task B1 in one section, the header reads "Plan v1" and no block holds "Roles", "Ceiling" or
"tier".

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp -run 'PinSelectDescribes|OldOptionValue|ProposalShowsTheCard'`
Expected: FAIL to compile (`pinOption`, `slackOption.Description`).

- [ ] **Step 3: Implement**, with `slackOption` gaining
  `Description *slackBlockText `json:"description,omitempty"``.

- [ ] **Step 4: Run the tests and commit**

Run: `go test ./internal/slackapp/... ./internal/humanapi/...`
Expected: PASS.

```bash
git add internal docs/slack.md
git commit -m "feat(slack): the plan message carries the workflow card and a described select"
```

### Task B5: The `start` form, `maku status` and the `task` tool carry the card

**Files:**
- Modify: `internal/maku/start.go:258-284` (the form's `workflow` field and message)
- Modify: `internal/humanapi/tasktool.go` (the `task` tool's text)
- Modify: `internal/roomview/card.go:133` (`Card`, already extended in Task B2)
- Modify: `internal/roomview/catalogue.go` (`CatalogueText`, which has no caller: delete it, the
  card replaces it)
- Modify: `docs/cli.md` (the `status` sample `:96-112`, the form `:157`, the plan head `:212-214`)
- Test: `internal/maku/start_test.go`, `internal/humanapi/tasktool_test.go`

**Interfaces:**
- Consumes: `roomview.CardOfPlan`, `WorkflowCardText` (Task B1); the catalogue's per-workflow
  description and ceiling, which `checkHandoff` now returns in `checked.Workflows` as
  `[]workflowChoice{Name, Description string; CeilingUSD float64}`.
- Produces: the form's message holds the card, then one line per offered workflow; the field keeps
  its `enum` of names and gains `enumNames` for clients that draw them. The field stays optional.
- Produces: the `start` tool takes an optional `workflow` argument, the spec's "`maku start
  --workflow`": it preselects the form's field when the developer named a workflow in words, and is
  ignored with a line in the result when the name is not offered. Nothing is pinned without the
  form's answer. `start` is a tool of `maku mcp`, not a terminal command; the terminal command
  comes in Task G4.

The message's new middle:

```text
Workflow   standard · this repository's default
Will run   implementer → reviewer → CI → merge gate
Cost       up to $5.10

Other workflows a maintainer may choose below:
  quick     One implementer. For changes a check can verify. Up to $5.10
  careful   Scoped first, judged before review. For wide or unclear tasks. Up to $13.60
```

- [ ] **Step 1: Write the failing tests**

```go
func TestTheStartFormDescribesEachWorkflow(t *testing.T) {
	asked := askedForm(t, checkedPlan(withWorkflows( // the package's elicitation capture and plan fixture
		workflowChoice{"quick", "One implementer. For changes a check can verify.", 5.10},
		workflowChoice{"careful", "Scoped first, judged before review. For wide or unclear tasks.", 13.60})))
	for _, want := range []string{"Workflow   standard · this repository's default", "Cost       up to $5.10",
		"careful   Scoped first, judged before review. For wide or unclear tasks. Up to $13.60"} {
		if !strings.Contains(asked.Message, want) {
			t.Errorf("missing %q in:\n%s", want, asked.Message)
		}
	}
	wf := asked.Properties["workflow"]
	if !slices.Equal(wf.Enum, []string{"standard", "quick", "careful"}) || len(wf.EnumNames) != 3 ||
		!strings.Contains(wf.EnumNames[2], "up to $13.60") {
		t.Fatalf("workflow field: %+v", wf)
	}
}
```

In `tasktool_test.go`, `TestTheTaskToolLeadsWithTheCard`: the tool's text for a running task holds
the `Workflow`, `Will run`, `Cost` and `Path` lines. In `start_test.go`,
`TestStartsWorkflowArgumentPreselectsTheField`: `{"id": "...", "workflow": "careful"}` gives the
form's field `default: careful`, and `"workflow": "nope"` leaves the default and returns
`"workflow_ignored": "nope is not offered here"`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/maku -run StartFormDescribes ./internal/humanapi -run TaskToolLeads`
Expected: FAIL.

- [ ] **Step 3: Implement**, delete `CatalogueText` and its test, update `docs/cli.md`. Also fix the
  card's closing line there: it names `maku cancel` and drops the two acts the CLI cannot perform.

- [ ] **Step 4: Run the gate and commit**

Run: `go test ./internal/maku/... ./internal/humanapi/... ./internal/roomview/... && task check`
Expected: PASS.

```bash
git add internal docs/cli.md
git commit -m "feat(start): the form, maku status and the task tool carry the workflow card"
```

### Task B6: The room's header carries the card, open by default

**Files:**
- Modify: `web/src/profile.ts:17-25` (the fold), `web/src/strip.ts:226-288` (the header chips),
  `web/src/summary.ts` (the `profile` fact's new fields), `web/src/room.ts` (where the fold is
  mounted)
- Modify: `web/src/class-card.ts:145-152` (the settings row: description and ceiling, no "tier")
- Modify: `docs/web-ui.md`, `docs/reference/web-ui-settings.md` ("Workflow" row)
- Test: `web/test/profile.test.ts` (create), `web/test/class-card-profiles.test.ts`

**Interfaces:**
- Consumes: the summary's `status.profile` with Task B1's fields.
- Produces: `workflowCard(profile, flow): HTMLElement` in `profile.ts`: a `<section
  class="workflow-card">` with three rows (`Workflow`, `Will run`, `Cost`), always open. The details
  the fold held (`Source`, `Requested`, `Refused`, `Recommended`, `Why`) sit in a nested
  `<details>` titled "How it was chosen". The evaluation cohort leaves the heading and appears only
  inside the details, and only for `control` or `treatment`.

- [ ] **Step 1: Write the failing test**

```ts
import { test, expect } from "vitest"; // the runner web/package.json declares
import { workflowCard } from "../src/profile";

test("the workflow card is open and says why and how much", () => {
  const card = workflowCard({ name: "standard", source: "repository", cohort: "treatment",
    ceilingMicroUSD: 5_100_000, path: ["implementer", "reviewer", "CI", "merge gate"] }, { nodes: [] });
  expect(card.tagName).toBe("SECTION");
  expect(card.textContent).toContain("standard · this repository's default");
  expect(card.textContent).toContain("implementer → reviewer → CI → merge gate");
  expect(card.textContent).toContain("up to $5.10");
  expect(card.querySelector(":scope > .workflow-head")!.textContent).not.toMatch(/treatment|control|labeled|tier/);
});

test("a refused pin is named on the card, not only in the details", () => {
  const card = workflowCard({ name: "standard", source: "repository", requested: "quick", refused: "profile_conflict" }, { nodes: [] });
  expect(card.textContent).toContain("quick was not applied");
});
```

Use the imports the neighbouring tests under `web/test/` use if the runner differs.

- [ ] **Step 2: Run it to see it fail**

Run: `task ui:test`
Expected: FAIL (`workflowCard` is not exported).

- [ ] **Step 3: Implement**

The reason words are a `Record<string, string>` in `profile.ts` holding Task B1's table verbatim,
with the same fallback for an unknown source. The header strip gains one chip, the workflow's name,
before the phase chip.

- [ ] **Step 4: Build, test, commit**

Run: `task ui:test && task ui:build && task ui:check`
Expected: PASS.

```bash
git add web internal/humanapi/ui docs
git commit -m "feat(web): the room's header carries the workflow card, open by default"
```

### Task B7: One vocabulary: `workflow_*` shown, `profile_*` kept, "tier" gone from what a person reads

**Files:**
- Modify: `internal/intake/refusal.go` (the closed refusal list and its sentences)
- Modify: `internal/factory/triage/pin.go:55-67` (the constants stay; a `Shown(code)` helper)
- Modify: `internal/roomview/words.go`, `internal/summary/state.go` (the status words)
- Modify: `internal/maku/format.go` (`Explain`), `internal/slackapp/endline.go:186-225`
- Modify: `internal/roomview/proposal.go:262-281` (`SuggestionLine`: no class beside the workflow)
- Modify: `docs/reference/narration.md`, `docs/reference/api.md` (the catalogue's `profiles` key is
  documented as "the workflows, under their API key `profiles`")
- Test: `internal/intake/refusal_test.go`, `internal/summary/state_test.go`,
  `internal/roomview/proposal_test.go`, and a new `internal/vocabulary_test.go`

**Interfaces:**
- Produces: `func Shown(code string) string` in `internal/intake`: `profile_unknown` →
  `workflow_unknown`, `profile_conflict` → `workflow_conflict`, `profile_no_tests_paths` →
  `workflow_no_tests_paths`, `profile_not_offered` → `workflow_not_offered`; any other code
  unchanged. `func Accepted(code string) string` maps the other way, so an API caller may send
  either. The API, `status.profile.refused` and metrics keep emitting `profile_*`.
- Produces: `func StatusWord(phase, reason string) string` in `internal/summary`, the one status
  vocabulary:

| Word | Phases |
|---|---|
| `planning` | `Received`, `Triaged`, a scoper run |
| `working` | `Queued`, `Implementing`, a tester run |
| `checking` | `Reviewing`, `Verifying` |
| `waiting on you` | `Escalated`, `AwaitingHuman` |
| `waiting on a check` | `AwaitingCI` |
| `done` | `Merged`, `Done`, `NoOp` |
| `stopped` | `Stopped`, `Rejected`, `Closed`, `Sealed`, `Reverted` |

- [ ] **Step 1: Write the failing tests**

```go
func TestRefusalCodesAreShownAsWorkflow(t *testing.T) {
	for api, shown := range map[string]string{"profile_unknown": "workflow_unknown", "profile_conflict": "workflow_conflict",
		"profile_no_tests_paths": "workflow_no_tests_paths", "not_maintainer": "not_maintainer"} {
		if Shown(api) != shown || Accepted(shown) != api {
			t.Errorf("%s: shown %q, accepted %q", api, Shown(api), Accepted(shown))
		}
	}
}

func TestEveryPhaseHasOneStatusWord(t *testing.T) {
	words := []string{"planning", "working", "checking", "waiting on you", "waiting on a check", "done", "stopped"}
	for _, phase := range v1alpha1.Phases() { // the API's list of phases; add it beside the constants if absent
		if w := StatusWord(phase, ""); !slices.Contains(words, w) {
			t.Errorf("phase %s reads %q", phase, w)
		}
	}
}
```

`internal/vocabulary_test.go` walks the Go string literals of `internal/slackapp`,
`internal/roomview`, `internal/factory/narrate` and `internal/maku` with `go/parser` and fails on a
literal that matches `(?i)\btier (light|standard|frontier)\b`, `\bprofile\b` outside a `profile_`
code or a JSON key, or `\(triager\)`. Each exception is one entry of an allow-list in the test with
its reason. A matching test in `web/test/vocabulary.test.ts` reads `web/src/*.ts` for the same three
patterns in user-visible strings.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/intake -run RefusalCodesAreShown ./internal/summary -run EveryPhaseHasOne ./internal -run Vocabulary && task ui:test`
Expected: FAIL, listing each literal to change.

- [ ] **Step 3: Implement**, literal by literal, until the vocabulary tests list nothing.
  `SuggestionLine` becomes `workflow <w> (<roles>) · <merge words>`; the class leaves the line.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal web docs
git commit -m "feat: one vocabulary, workflow in what a person reads and one status word per phase"
```

---

## Phase C · Step up once, and "run again deeper"

Release C. Switches: `workflows.<name>.stepUp` and `Repository.spec.workflow.stepUp`. The engine's
`stepUp` (`internal/factory/reconciler/stepup.go:29-75`) already steps once, never to the same
workflow, never past the budget, and resets the review rounds and the CI-fix allowance.

### Task C1: Investigation: which recorded failure is "repository checks red at run end"?

**Files (read only):**
- `images/maku-harness/agent_run.py` (the checks' result near `:1250-1270`; the run's exit)
- `images/maku-harness/agent_checks.py` (the result file `/workspace/.agent-checks/<sha>.json`)
- `internal/factory/reconciler/implement.go` (`implementing`, `:745-833`: how a run's end reason is
  read), `internal/factory/reconciler/merge.go:1075-1104` (`fixCI`, `ci_red`)
- `internal/envelope/` (whether the checks' result is a room event the factory can read)
- `internal/factory/reconciler/stepup_test.go` (`TestStepTable`: `ci_red` and `budget-task` step
  nowhere today)

- [ ] **Step 1: Answer two questions and record them in the pull request of C-1**

| Question | If yes | If no |
|---|---|---|
| Does the factory receive the repository checks' pass or fail for the run's final head as an event or a handoff field? | Task C3 adds the trigger `checks_red`: an implementer run that ends `Succeeded` with a pull request whose final head has a failed check step, on a task whose `status.profile.checks` is true, ends `Escalated checks_red` only after the reviewer and CI path would otherwise start. The step-up runs before the reviewer is paid for | Task C3 uses `ci_red` (the required checks red after the repository's `merge.fixRuns` repairs) as the trigger, and the harness is not changed. The card's trigger words read "the checks stayed red" either way |
| Does `budget-task` leave room for a run under the stepped-up tier? | `budget-task` joins the triggers: `runFits` on the trial task already refuses a step that cannot hold a run | `budget-task` stays out and goes to a maintainer, as today |

- [ ] **Step 2: Write the trigger table Task C3 implements** from the answers: reason, group, the
  role whose run must be current. Start from:

| Reason | Trigger words on the card | Current run |
|---|---|---|
| `budget-run` | "the run's budget was spent" | implementer |
| `stalled` | "a run that committed nothing" | implementer |
| `not_met` | "the judge's rounds ran out" | implementer |
| `review_rounds_exhausted` | "the review rounds ran out" | reviewer |
| `checks_red` or `ci_red` (Step 1) | "the checks stayed red" | implementer |

Never a trigger: `judge_impossible`, `needs_author`, `split_proposed`, `scoper_failed`, a stop, a
capacity end.

### Task C2: `stepUp` in config, and the shipped ladder

**Files:**
- Modify: `internal/factory/config/mergepolicy.go:49-79` (`HarnessProfile`), `:176-207`
  (validation)
- Modify: `internal/factory/config/workflows.go:23-30` (shipped workflows), `:91-101`
  (`RepositoryWorkflow`), `:126-142` (`validateWorkflow`)
- Modify: `internal/factory/catalogue/catalogue.go` (`profileOf`: `StepUp`, `StepUpCeilingUSD`)
- Modify: `internal/install/testdata/golden/generic/factory/factory.yaml`
- Modify: `docs/reference/config.md`, `docs/factory.md`, `docs/upgrading.md`
- Test: `internal/factory/config/workflows_test.go`, `internal/factory/catalogue/catalogue_test.go`

**Interfaces:**
- Produces:

```go
// StepUp is the workflow a task runs once more under when a run fails in a way a deeper workflow
// can help (WR4); empty goes to a maintainer. It is escalation's one-target form: set one of them.
// +kubebuilder:validation:MaxLength=253
StepUp string `json:"stepUp,omitempty"`
```

```go
// StepUp is whether a task of the repository steps up without asking: auto (the default), ask
// (the task waits with a "run again deeper" offer) or off.
// +kubebuilder:validation:Enum=auto;ask;off
StepUp string `json:"stepUp,omitempty"`
```

  `func (c *Config) StepUpFor(workflow, reason string) string`: the workflow's `stepUp`, else its
  `escalation` entry for the reason's group, else `""`.
  `func (r *Repository) StepUpMode() string`: `auto` when unset or `r` is nil.
- The shipped ladder: `quick.stepUp: standard`, `standard.stepUp: careful`; `careful` names none.

- [ ] **Step 1: Write the failing tests**

```go
func TestTheShippedLadder(t *testing.T) {
	c := mustParse(t, noTemplates)
	for from, to := range map[string]string{"quick": "standard", "standard": "careful", "careful": ""} {
		if got := c.StepUpFor(from, "stalled"); got != to {
			t.Errorf("%s steps to %q, want %q", from, got, to)
		}
	}
}

func TestStepUpValidation(t *testing.T) {
	for name, tc := range map[string]struct{ yaml, want string }{
		"itself":      {`workflows: {mine: {template: pair, stepUp: mine}}`, "workflows.mine.stepUp: a workflow never steps up to itself"},
		"unknown":     {`workflows: {mine: {template: pair, stepUp: nope}}`, `workflows.mine.stepUp "nope" is not a workflow`},
		"none":        {`workflows: {mine: {template: pair, stepUp: none}}`, `workflows.mine.stepUp "none" is not a workflow`},
		"both":        {`workflows: {mine: {template: pair, stepUp: careful, escalation: {outOfBudget: careful}}}`, "workflows.mine: set stepUp or escalation, not both"},
		"a cycle":     {`workflows: {a: {template: pair, stepUp: b}, b: {template: pair, stepUp: a}}`, "workflows.a.stepUp: a and b step up to each other"},
		"cheaper":     {`workflows: {mine: {template: pair, tier: frontier, stepUp: quick}}`, "workflows.mine.stepUp: quick has a lower ceiling than mine"},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := Parse([]byte(good + tc.yaml + "\n")); err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

func TestAPlatformsWorkflowKeepsItsEscalation(t *testing.T) { // TestWorkflowEscalation's config
	c := mustParse(t, good+`workflows:
  floor: {template: pair, escalation: {outOfBudget: careful}}
`)
	if c.StepUpFor("floor", "budget-run") != "careful" || c.StepUpFor("floor", "not_met") != "" {
		t.Fatal("escalation's groups are no longer read")
	}
}
```

In `catalogue_test.go`: `Profiles["standard"].StepUp == "careful"` and its `StepUpCeilingUSD` is the
`frontier` tier's `taskUSD`; `Profiles["careful"].StepUp == ""`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/config -run 'ShippedLadder|StepUpValidation|KeepsItsEscalation' ./internal/factory/catalogue`
Expected: FAIL to compile.

- [ ] **Step 3: Implement**, then `task crd:gen`, the installer's golden, and the three pages.
  `docs/upgrading.md` gains a section "A task steps up once" that names both switches and says a
  platform that wrote its own `standard` entry keeps it whole and so gets no step-up until it adds
  `stepUp`.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add api internal charts config docs
git commit -m "feat(factory): stepUp on a workflow and on a repository, with the shipped ladder"
```

### Task C3: The engine steps on the five triggers, asks on a pin, and never outspends a confirmation

**Files:**
- Modify: `internal/factory/reconciler/stepup.go:18-87` (`group`, `stepUp`, `stepped`)
- Modify: `internal/factory/reconciler/implement.go` or `merge.go` (the new trigger's site, per
  Task C1)
- Modify: `api/factory/v1alpha1/task_types.go` (`ProfileStatus`, `IntakeSpec`)
- Modify: `internal/intake/plan.go` (the plan's budget block), `internal/humanapi/handoff.go` (what
  a confirmation writes into `spec.intake`)
- Test: `internal/factory/reconciler/stepup_test.go`

**Interfaces:**
- Consumes: `Config.StepUpFor`, `Repository.StepUpMode` (Task C2); Task C1's trigger table.
- Produces, on `ProfileStatus`:

```go
// StepUp records the one step this task took or was offered (WR4).
// +optional
StepUp *StepUpStatus `json:"stepUp,omitempty"`
```

```go
type StepUpStatus struct {
	// +kubebuilder:validation:MaxLength=63
	From string `json:"from"` // the workflow it ran
	// +kubebuilder:validation:MaxLength=63
	To string `json:"to"` // the workflow it stepped, or may step, to
	// +kubebuilder:validation:MaxLength=32
	Trigger string `json:"trigger"` // the escalated reason
	// +kubebuilder:validation:Enum=auto;manual;offered
	Mode string `json:"mode"`
	// +kubebuilder:validation:MaxLength=64
	// +optional
	By string `json:"by,omitempty"` // the maintainer, for manual
	// +kubebuilder:validation:Minimum=0
	CeilingMicroUSD int64 `json:"ceilingMicroUSD"`
}
```
- Produces, on the task's intake spec: `StepUpShown bool` (`json:"stepUpShown,omitempty"`), true
  when the plan a person confirmed carried the "if it steps up" figure. `handoff.go` sets it from
  the plan's `budget.stepUpCeilingUSD > 0`.
- The decision, in order:

| Condition | Result |
|---|---|
| No target, or the task already stepped (`status.profile.stepUp.mode` is `auto` or `manual`) | Escalates, as today |
| `Repository.StepUpMode() == "off"` | Escalates |
| The step does not fit (`runFits` on the trial) or the task's `maxMicroUSD` is below the target's ceiling | Escalates with `stepUp.mode: offered` |
| The workflow's source is `label` (a pin) | Escalates with `mode: offered` |
| Mode `ask` | Escalates with `mode: offered` |
| The task came from a confirmed plan and `stepUpShown` is false | Escalates with `mode: offered` |
| Otherwise | Steps, `mode: auto` |

  The `treatment`-source and `control`-cohort guards stay.

- [ ] **Step 1: Write the failing tests** in `stepup_test.go`, on the file's own rig. `stepCfg`
  gains `ladderCfg()`: the shipped workflows over `resolveCfg("observe", 0)`.

```go
func TestAStandardTaskStepsUpToCarefulOnce(t *testing.T) {
	g, tk := stepRig(t, ladderCfg(), func(tk *v1alpha1.Task) { tk.Status.Profile.Name = "standard" })
	got := g.fail(t, tk, "stalled")
	s := got.Status.Profile.StepUp
	if got.Status.Phase != v1alpha1.PhaseQueued || got.Status.Profile.Name != "careful" || s == nil ||
		s.From != "standard" || s.To != "careful" || s.Trigger != "stalled" || s.Mode != "auto" {
		t.Fatalf("%s %+v %+v", got.Status.Phase, got.Status.Profile, s)
	}
	again := g.fail(t, got, "stalled")
	wantEscalated(t, again, "stalled") // a second failure goes to a maintainer
}

func TestAPinnedTaskAsksInsteadOfStepping(t *testing.T) { // replaces TestALabelledTaskSteps
	g, tk := stepRig(t, ladderCfg(), func(tk *v1alpha1.Task) {
		tk.Status.Profile.Name, tk.Status.Profile.Source, tk.Status.Profile.Cohort = "standard", "label", "labeled"
	})
	got := g.fail(t, tk, "budget-run")
	if got.Status.Phase != v1alpha1.PhaseEscalated || got.Status.Profile.Name != "standard" ||
		got.Status.Profile.StepUp == nil || got.Status.Profile.StepUp.Mode != "offered" {
		t.Fatalf("%s %+v", got.Status.Phase, got.Status.Profile)
	}
}

func TestACappedTaskAsksBeforeItStepsUp(t *testing.T) {
	g, tk := stepRig(t, ladderCfg(), func(tk *v1alpha1.Task) {
		tk.Status.Profile.Name = "standard"
		tk.Spec.MaxMicroUSD = 2_000_000 // a Slack request capped at $2.00
	})
	got := g.fail(t, tk, "stalled")
	if got.Status.Phase != v1alpha1.PhaseEscalated || got.Status.Profile.StepUp.Mode != "offered" {
		t.Fatalf("a capped task stepped up: %+v", got.Status.Profile)
	}
}

func TestAConfirmedPlanStepsOnlyWhenTheFigureWasShown(t *testing.T) {
	for shown, phase := range map[bool]string{true: v1alpha1.PhaseQueued, false: v1alpha1.PhaseEscalated} {
		g, tk := stepRig(t, ladderCfg(), func(tk *v1alpha1.Task) {
			tk.Status.Profile.Name = "standard"
			tk.Spec.Intake = &v1alpha1.IntakeSpec{StepUpShown: shown}
		})
		if got := g.fail(t, tk, "stalled"); got.Status.Phase != phase {
			t.Errorf("stepUpShown=%v: phase %s, want %s", shown, got.Status.Phase, phase)
		}
	}
}

func TestARepositoryMaySwitchTheStepOffOrToAsk(t *testing.T) {
	// workflow.stepUp: off escalates with no StepUp record; ask escalates with mode offered
}

func TestNeverAStepOnImpossibleOrAQuestion(t *testing.T) {
	for _, reason := range []string{"judge_impossible", "needs_author", "split_proposed", "manual"} {
		g, tk := stepRig(t, ladderCfg(), func(tk *v1alpha1.Task) { tk.Status.Profile.Name = "standard" })
		wantEscalated(t, g.fail(t, tk, reason), reason)
	}
}
```

`TestStepTable` gains the row Task C1 decided (`checks_red` or `ci_red`, and `budget-task` if it
joined) and keeps `judge_impossible` and `needs_author` empty. `wantStepped` reads the group from
`StepUpFor`'s reason, so its `p.Reason` assertion becomes the trigger's group as before.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler -run 'StepsUpToCarefulOnce|PinnedTaskAsks|CappedTaskAsks|ConfirmedPlanSteps|SwitchTheStepOff|NeverAStepOn|StepTable'`
Expected: FAIL to compile, then FAIL on the pinned and capped cases.

- [ ] **Step 3: Implement**

`stepUp` reads the target from `cfg.StepUpFor(p.Name, reason)` in place of `cur.Escalation`, runs
the decision table, and writes `StepUp` in the same status write as the profile (`d.restore`
carries it, so the replay branch at the top of `stepUp` recovers it). "Already stepped" reads
`p.StepUp` beside the existing `p.Source == "escalation"` test, so a task stepped by release B's
engine is still stepped once.

- [ ] **Step 4: Run the package, regenerate, commit**

Run: `task crd:gen && go test ./internal/factory/... ./internal/intake/... ./internal/humanapi/...`
Expected: PASS.

```bash
git add api internal charts config
git commit -m "feat(factory): step up once on a verified failure, ask on a pin or a cap"
```

### Task C4: The step-up is announced once, everywhere, with its new ceiling

**Files:**
- Modify: `internal/factory/narrate/narrate.go:1228-1236` (`ProfileEscalated`)
- Modify: `internal/factory/reconciler/stepup.go` (`stepped`), `status_comment.go` (the pinned
  comment's reason)
- Modify: `internal/slackapp/app.go` (the thread's line for the event), `internal/slackapp/endline.go`
- Modify: `internal/roomview/workflowcard.go` (`CardOf`: the cost line after a step)
- Modify: `docs/reference/narration.md` (`profile_escalated`)
- Test: `internal/factory/narrate/narrate_test.go` (`TestProfileEscalated`),
  `internal/slackapp/app_test.go`, `internal/roomview/workflowcard_test.go`

**Interfaces:**
- Produces: `ProfileEscalated(from, to, trigger string, ceilingMicroUSD int64, run int) Event`, key
  unchanged (`profile-escalated-<run>`):

```text
Maku stepped this task up from `standard` to `careful`: a run that committed nothing.
It runs once more, scoped first and judged before review, on the same branch and pull request.
New ceiling: $13.60 for the task ($1.84 spent so far). To stop it, apply the label `factory/stop`.
```

  An offer (mode `offered`) is `StepUpOffered(t, from, to, trigger, ceilingMicroUSD, why)`, key
  `step-up-offered`:

```text
This task stopped under `standard`: the run's budget was spent. Maku did not step it up because
a maintainer pinned its workflow. A maintainer can run it again deeper under `careful` (up to
$13.60): comment `/factory retry deeper`.
```

- After a step the card's cost line reads `up to $13.60 · stepped up from standard`.

- [ ] **Step 1: Write the failing tests**

```go
func TestProfileEscalated(t *testing.T) { // rewritten
	ev := ProfileEscalated("standard", "careful", "stalled", 13_600_000, 2)
	for _, want := range []string{"from `standard` to `careful`", "a run that committed nothing", "New ceiling: $13.60", "`factory/stop`"} {
		if !strings.Contains(ev.Body, want) {
			t.Errorf("missing %q in:\n%s", want, ev.Body)
		}
	}
	if ev.Key != "profile-escalated-2" {
		t.Fatalf("key %q", ev.Key)
	}
}

func TestAnOfferSaysWhyItDidNotStep(t *testing.T) {
	for why, want := range map[string]string{"pinned": "a maintainer pinned its workflow", "capped": "its budget is capped below",
		"ask": "this repository asks first", "not_shown": "the plan you confirmed did not show the stepped-up cost"} {
		if ev := StepUpOffered(narrated("3buqdlot"), "standard", "careful", "budget-run", 13_600_000, why); !strings.Contains(ev.Body, want) {
			t.Errorf("%s: missing %q in:\n%s", why, want, ev.Body)
		}
	}
}
```

In `app_test.go`, `TestTheThreadSaysAStepUpOnce`: a `profile_escalated` narration event for a task
with a Slack thread posts one line in the thread, with no mention, and a second delivery of the same
event posts nothing.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/narrate -run 'ProfileEscalated|OfferSaysWhy' ./internal/slackapp -run ThreadSaysAStepUp`
Expected: FAIL.

- [ ] **Step 3: Implement.** The spent figure comes from the task's settled spend
  (`t.Status` micro-dollars, the figure the end comment uses); when it is not settled the
  parenthesis is omitted.

- [ ] **Step 4: Run the tests and commit**

Run: `go test ./internal/factory/... ./internal/slackapp/... ./internal/roomview/...`
Expected: PASS.

```bash
git add internal docs
git commit -m "feat(narrate): a step-up says what changed, why, its new ceiling and how to stop"
```

### Task C5: "Run again deeper" by hand: the comment, the route and `maku retry`

**Files:**
- Modify: `internal/factory/reconciler/watch.go:291` (`cmdRetry`), `:331` (`retryCommand`),
  `:381-441` (`escalated`)
- Modify: `internal/factory/reconciler/reconciler.go` (the `NoOp` phase's handler: a retry command
  is read there too)
- Modify: `internal/factory/api/acts.go:21-43` (`ActRequest`, the result codes)
- Modify: `internal/humanapi/acts.go` (a `retry` act beside `cancel`),
  `internal/humanapi/slackacts.go`
- Modify: `internal/app/maku.go:271` (the command list), and a `retry` case beside `cancel` (`:363`,
  `:960-990`)
- Modify: `internal/maku/client.go` (`Act` already carries a kind)
- Modify: `docs/cli.md`, `docs/factory.md`, `docs/reference/api.md`
- Test: `internal/factory/reconciler/stepup_test.go`, `internal/factory/api/acts_test.go`,
  `internal/app/maku_test.go`

**Interfaces:**
- Produces: the comment `/factory retry deeper`, a maintainer's, parsed by the rule that parses
  `/factory retry` (a whole line, no quote, no longer word).
- Produces: `ActRequest{OnBehalfOf string; Deeper bool `json:"deeper,omitempty"`}` on
  `POST /v1/tasks/{task}/retries`, and the results `stepped_up`, `no_deeper_workflow`,
  `deeper_over_cap` beside `retried`.
- Produces: the room act `{"kind": "retry", "deeper": true}`, allowed to a maintainer of the task's
  repository, forwarded to the factory's retries route.
- Produces: `maku retry <task> [--deeper]`.

```text
$ maku retry 3buqdlot --deeper
3buqdlot: running again under careful (up to $13.60), on the same branch and pull request
```

- Rules: a deeper retry is a maintainer's (the pin's rule, `triage.ResolvePin`'s maintainer check);
  it is allowed on `Escalated` and on `NoOp`; it uses the task's one step
  (`status.profile.stepUp.mode: manual`, `by` the maintainer); a task that already stepped answers
  `no_deeper_workflow`; a task whose cap is below the target's ceiling answers `deeper_over_cap`.
  A plain `/factory retry` is unchanged. The task keeps its room, branch, pull request and spend.

- [ ] **Step 1: Write the failing tests**

```go
func TestRetryDeeperStepsAPinnedTaskOnAMaintainersWord(t *testing.T) {
	g, tk := stepRig(t, ladderCfg(), func(tk *v1alpha1.Task) {
		tk.Status.Profile.Name, tk.Status.Profile.Source = "standard", "label"
	})
	tk = g.fail(t, tk, "budget-run") // offered, not stepped
	g.comment(t, tk, "alice", "/factory retry deeper") // the package's issue-comment helper; alice maintains
	got := g.reconcile(t, tk)
	s := got.Status.Profile.StepUp
	if got.Status.Phase != v1alpha1.PhaseQueued || got.Status.Profile.Name != "careful" || s.Mode != "manual" || s.By != "alice" {
		t.Fatalf("%s %+v %+v", got.Status.Phase, got.Status.Profile, s)
	}
	if got.Status.RoomRef != tk.Status.RoomRef || got.Name != tk.Name {
		t.Fatal("a deeper retry made a new task or room")
	}
}

func TestRetryDeeperIsAMaintainersOnly(t *testing.T) { // bob is not a maintainer: the command is answered not_maintainer, nothing moves
}

func TestRetryDeeperOnANoOpTask(t *testing.T) { // phase NoOp, reason no_pr: steps to the target and queues an implementer run
}

func TestAPlainRetryKeepsTheWorkflow(t *testing.T) { // "/factory retry": Profile.Name unchanged, StepUp nil
}
```

In `acts_test.go`, beside `TestRetryOnlyEscalated`: `TestRetryDeeperAnswersItsOwnCodes` posts
`{"onBehalfOf": "...", "deeper": true}` and reads `stepped_up`, then `no_deeper_workflow` on the
second call. In `maku_test.go`: `TestRetryCommandSendsTheAct` asserts the act the client sends is
`{"kind":"retry","deeper":true}` and the printed line names the workflow and the ceiling.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler -run 'RetryDeeper|PlainRetryKeeps' ./internal/factory/api -run RetryDeeper ./internal/app -run RetryCommand`
Expected: FAIL.

- [ ] **Step 3: Implement.** `escalated()` reads the command's `deeper` word after `markHandled`'s
  checks and calls a new `r.stepUpBy(ctx, cfg, t, by)`, which shares `stepUp`'s trial, `runFits`
  and `applyProfile` and skips only the "ask" rows of the decision table.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal docs
git commit -m "feat: run again deeper, from a comment, the API and maku retry"
```

### Task C6: The button in the room and in Slack

**Files:**
- Modify: `web/src/needs.ts:33-41` (titles), `:93-96` (the recovery card)
- Modify: `internal/summary/needs.go` (the recovery need carries the offer:
  `Deeper *DeeperOffer{Workflow string; CeilingMicroUSD int64}`)
- Modify: `internal/slackapp/acts.go:23-40` (the confirm lines), `internal/slackapp/endline.go`
  (the button on an escalated end line), `internal/intent/model.go` (the intent `retry_deeper`),
  `internal/slackapp/intents.go`
- Modify: `docs/slack.md` (the intents table; the line under "Never from Slack"), `docs/web-ui.md`
- Test: `web/test/needs.test.ts`, `internal/slackapp/acts_test.go`, `internal/intent/intent_test.go`

**Interfaces:**
- Consumes: the room act `retry` and the retries route (Task C5).
- Produces, in the room: the recovery card titled "Retry the task, or run it again deeper", with
  two buttons for a maintainer, "Retry" and "Run again deeper (careful, up to $13.60)", each behind
  the page's existing two-press confirm; a non-maintainer sees the card's text and no button. The
  out-link to the GitHub comment goes.
- Produces, in Slack: the escalated end line carries the buttons **Retry** and **Run again
  deeper**, shown only where the channel's `intentActions` holds `retry`; the confirm reads
  "<@user>: run task #N again under careful? It may spend up to $13.60 in all." The typed intent
  "run it again deeper" maps to `retry_deeper`. This is the one reversal of the Slack intents ruling
  that changing the workflow is not an intent.

- [ ] **Step 1: Write the failing tests**

```ts
test("a maintainer's recovery card offers both retries on the page", () => {
  const li = needCard({ kind: "recovery", what: "the run's budget was spent", issue: 12,
    deeper: { workflow: "careful", ceilingMicroUSD: 13_600_000 } }, { hands: maintainerHands() });
  const labels = [...li.querySelectorAll("button")].map((b) => b.textContent);
  expect(labels).toContain("Retry");
  expect(labels).toContain("Run again deeper (careful, up to $13.60)");
  expect(li.querySelector("a.need-go")).toBeNull();
});
```

```go
func TestTheDeeperConfirmNamesTheCeiling(t *testing.T) {
	line := deeperConfirm("U123", 12, "careful", 13.60)
	if line != "<@U123>: run task #12 again under careful? It may spend up to $13.60 in all." {
		t.Fatalf("got %q", line)
	}
}
```

In `intent_test.go`, the classifier's table gains "run it again deeper", "retry with careful" →
`retry_deeper`, and "retry" stays `retry`.

- [ ] **Step 2: Run them to see them fail**

Run: `task ui:test; go test ./internal/slackapp -run DeeperConfirm ./internal/intent`
Expected: FAIL.

- [ ] **Step 3: Implement**, build the UI, run `task intent:eval` and record its result in the pull
  request.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add web internal docs
git commit -m "feat: run again deeper as a button in the room and in Slack"
```

---

## Phase D · Measure every role on every task

Release D. No switch for recording: nothing a task runs changes. The "typical cost" on the card is
shown only from 30 merged tasks of the class. Metrics keep the `agent_factory_` prefix; existing
metrics and labels are not renamed.

The stages measured: `ask`, `plan`, `tests`, `implement`, `search`, `judge`, `review`, `split`, and
`step_up`.

### Task D1: One effect record per stage, on the task, counted once

**Files:**
- Modify: `api/factory/v1alpha1/task_types.go` (`TaskStatus`)
- Create: `internal/factory/reconciler/effects.go`
- Modify: `internal/factory/reconciler/outcome.go` (the task's end, where `TaskOutcome` is recorded)
- Modify: `internal/factory/fmetrics/fmetrics.go` (two instruments, near `:480-510`)
- Test: `internal/factory/reconciler/effects_test.go`, `internal/factory/fmetrics/fmetrics_test.go`

**Interfaces:**
- Produces, on `TaskStatus`:

```go
// Stages is what each stage of the task cost and changed (WR5), filled as the task goes and
// counted into the metrics once, at its end.
// +kubebuilder:validation:MaxItems=16
// +optional
Stages []StageRecord `json:"stages,omitempty"`
```

```go
type StageRecord struct {
	// +kubebuilder:validation:Enum=ask;plan;tests;implement;search;judge;review;split;step_up
	Stage    string `json:"stage"`
	Runs     int32  `json:"runs"`
	MicroUSD int64  `json:"microUSD"`
	// Effect is what the stage changed, a word of the stage's closed list.
	// +kubebuilder:validation:MaxLength=32
	Effect  string `json:"effect,omitempty"`
	Counted bool   `json:"counted,omitempty"`
}
```

- Produces, in `effects.go`: `func (r *Reconciler) noteStage(t *v1alpha1.Task, stage, effect string)`
  (sets or replaces the stage's effect), `func stageOf(run v1alpha1.RunRecord) string` (`triager`
  with persona `scoper` → `plan`; `tester` → `tests`; `implementer` → `implement`; `reviewer` →
  `review`), and `func (r *Reconciler) countStages(ctx, cfg, t, outcome string)`, called from the
  task's end.
- Produces, in `fmetrics`:
  `StageCost(ctx, repository, class, stage string, usd float64)` on
  `agent_factory_stage_cost_usd` (a histogram), and
  `StageEffect(ctx, repository, class, stage, effect, outcome string)` on
  `agent_factory_stage_effects_total`. `class` is the merge-policy class the gate chose, else the
  predicted one; `outcome` is `TaskOutcome`'s word. No `profile` label: the report is by stage.

- [ ] **Step 1: Write the failing tests**

```go
func TestAStageEffectCountsOnce(t *testing.T) {
	g, tk := stepRig(t, ladderCfg(), nil)
	g.r.noteStage(tk, "review", "changes_committed")
	m := g.metrics() // the rig's metric reader
	g.r.countStages(t.Context(), g.r.Cfg.Current(), tk, "accepted")
	g.r.countStages(t.Context(), g.r.Cfg.Current(), tk, "accepted") // a replayed end
	if n := m.Count("agent_factory_stage_effects_total", "stage", "review", "effect", "changes_committed", "outcome", "accepted"); n != 1 {
		t.Fatalf("counted %d times", n)
	}
}

func TestStageCostSumsTheStagesRuns(t *testing.T) {
	// two implementer runs of $0.40 and $0.10 and one reviewer run of $0.09:
	// status.stages holds implement {runs: 2, microUSD: 500000} and review {runs: 1, microUSD: 90000}
}

func TestStageOfReadsThePersona(t *testing.T) {
	if stageOf(v1alpha1.RunRecord{Role: "triager", Persona: "scoper"}) != "plan" || stageOf(v1alpha1.RunRecord{Role: "tester"}) != "tests" {
		t.Fatal("a scoper's run is not the plan stage")
	}
}
```

If `RunRecord` holds no persona, `stageOf` reads the run's trigger and the task's scope state as
`web/src/rail.ts` tells a scoper from a triager; keep the test's intent.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler -run 'StageEffectCountsOnce|StageCostSums|StageOfReads'`
Expected: FAIL to compile.

- [ ] **Step 3: Implement**, `task crd:gen`. A run's dollars are added to its stage where the run's
  cost is settled today (`RunCost`'s call site), so a task whose cost is not final records the
  stage with the figure known and `Counted` false until the settle.

- [ ] **Step 4: Run the package and commit**

Run: `go test ./internal/factory/... && task crd:check`
Expected: PASS.

```bash
git add api internal charts config
git commit -m "feat(factory): a cost and an effect per stage on every task"
```

### Task D2: What the reviewer and the judge changed

**Files:**
- Modify: `internal/factory/reconciler/team.go:118-122`, `:169-196` (the verdict's handling)
- Modify: `internal/factory/reconciler/implement.go:771-780` (where the loop's end is recorded),
  `internal/factory/reconciler/stepup.go` (`lastJudge`)
- Modify: `internal/factory/reconciler/merge.go` (the merge's and the close's site)
- Test: `internal/factory/reconciler/effects_test.go`

**Interfaces:**
- Consumes: `noteStage` (Task D1).
- Produces the reviewer's effects, one per task, the last that applies:

| Effect | When |
|---|---|
| `changes_committed` | A `changes` verdict was followed by a new commit on the branch |
| `changes_ignored` | A `changes` verdict was followed by no commit (rounds exhausted, or a maintainer merged as is) |
| `approve_agreed` | It approved, and the pull request merged with no commit after its verdict |
| `approve_overruled` | It approved, and a maintainer pushed a commit, requested changes or closed the pull request |
| `no_verdict` | It gave none |

- Produces the judge's effect as `<verdict>_<end>`: verdict `met`, `not_yet` or `impossible` (its
  last), end `merged` or `not_merged`. Six words: the confusion matrix. A task with no judge
  records no `judge` stage.

- [ ] **Step 1: Write the failing tests**

```go
func TestTheReviewersEffect(t *testing.T) {
	for name, tc := range map[string]struct {
		verdicts []string // in order
		commitAfterChanges, maintainerCommit, merged bool
		want string
	}{
		"changes led to a commit":   {[]string{"changes", "approve"}, true, false, true, "changes_committed"},
		"changes ignored":           {[]string{"changes", "changes"}, false, false, false, "changes_ignored"},
		"approve agreed":            {[]string{"approve"}, false, false, true, "approve_agreed"},
		"approve overruled":         {[]string{"approve"}, false, true, true, "approve_overruled"},
		"approved, then closed":     {[]string{"approve"}, false, false, false, "approve_overruled"},
	} {
		t.Run(name, func(t *testing.T) {
			got := reviewEffect(tc.verdicts, tc.commitAfterChanges, tc.maintainerCommit, tc.merged)
			if got != tc.want {
				t.Fatalf("got %q, want %q", got, tc.want)
			}
		})
	}
}

func TestTheJudgesEffectIsItsVerdictAgainstTheEnd(t *testing.T) {
	for _, tc := range []struct{ verdict string; merged bool; want string }{
		{"met", true, "met_merged"}, {"met", false, "met_not_merged"},
		{"not_yet", true, "not_yet_merged"}, {"impossible", false, "impossible_not_merged"},
	} {
		if got := judgeEffect(tc.verdict, tc.merged); got != tc.want {
			t.Errorf("got %q, want %q", got, tc.want)
		}
	}
}
```

One rig test, `TestAMergedPairTaskRecordsTheReviewStage`, drives a `standard` task through
`changes`, a revision commit, `approve` and a merge, and reads
`status.stages` for `review` with `changes_committed`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler -run 'ReviewersEffect|JudgesEffect|RecordsTheReviewStage'`
Expected: FAIL to compile.

- [ ] **Step 3: Implement** `reviewEffect` and `judgeEffect` as pure functions in `effects.go`, and
  call `noteStage` from the four sites. "A maintainer's commit" is a commit on the pull request's
  head after the reviewer's verdict whose author is not the agents App, read where the gate already
  reads the head's commits.

- [ ] **Step 4: Run the package and commit**

Run: `go test ./internal/factory/...`
Expected: PASS.

```bash
git add internal
git commit -m "feat(factory): record what the reviewer's and the judge's verdicts changed"
```

### Task D3: What the scoper, the tester and the step-up changed

**Files:**
- Modify: `internal/factory/reconciler/scoper.go:66-106`, `:259-275` (the scoper's ends),
  `internal/factory/reconciler/split.go:136-160` (the approval)
- Modify: `internal/factory/reconciler/tester.go:106-138`, `internal/factory/reconciler/implement.go:800-812`
  (`contract_disputed`)
- Modify: `internal/factory/reconciler/stepup.go` (`stepped`), `outcome.go`
- Test: `internal/factory/reconciler/effects_test.go`

**Interfaces:**
- Produces:

| Stage | Effects |
|---|---|
| `ask` | `not_needed` (acceptance stated), `asked_answered`, `asked_assumed` (a retry went on without an answer) |
| `plan` | `ready`, `asked` (it asked), `answer_changed_scope` (the bounded task after the answer differs from the one before), `failed_open` (it ended with no handoff and the task ran whole) |
| `split` | `proposed_accepted`, `proposed_declined`, `not_proposed` |
| `tests` | `contract_held` (the contract check stayed green to the merge), `contract_disputed`, `not_testable`, `contract_refused` (`contract_invalid`, `contract_too_large`, `contract_not_red`, `contract_outside_tests`) |
| `step_up` | `finished` (the task ended merged or `Done` after the step), `escalated` (it went to a maintainer again), `offered_taken`, `offered_left` |

  Until phase E moves the question to intake, `ask` is recorded from the scoper's forced question
  (`scoper.go:86-90`).

- [ ] **Step 1: Write the failing tests**: one table test per stage on the pure functions
  `planEffect(before, after *v1alpha1.Scope, asked, handoff bool) string`,
  `testsEffect(endCategory string, disputed, mergedGreen bool) string` and
  `stepUpEffect(mode, outcome string) string`, plus `TestAStepThatFinishesIsCountedAsRescued`: a
  `standard` task that stalls, steps to `careful` and merges records `step_up` with `finished`.

```go
func TestThePlanEffect(t *testing.T) {
	a := &v1alpha1.Scope{Text: "fix the checker"}
	b := &v1alpha1.Scope{Text: "fix the checker and its fixture"}
	for name, tc := range map[string]struct {
		before, after *v1alpha1.Scope
		asked, handoff bool
		want string
	}{
		"ready":         {nil, a, false, true, "ready"},
		"asked":         {nil, nil, true, true, "asked"},
		"answer moved":  {a, b, true, true, "answer_changed_scope"},
		"failed open":   {nil, nil, false, false, "failed_open"},
	} {
		t.Run(name, func(t *testing.T) {
			if got := planEffect(tc.before, tc.after, tc.asked, tc.handoff); got != tc.want {
				t.Fatalf("got %q, want %q", got, tc.want)
			}
		})
	}
}
```

Use the scope type and its text field as `api/factory/v1alpha1/task_types.go` names them.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler -run 'ThePlanEffect|TheTestsEffect|TheStepUpEffect|CountedAsRescued'`
Expected: FAIL to compile.

- [ ] **Step 3: Implement**, calling `noteStage` at each end site listed under Files.

- [ ] **Step 4: Run the package and commit**

Run: `go test ./internal/factory/...`
Expected: PASS.

```bash
git add internal
git commit -m "feat(factory): record what the scoper, the tester and a step-up changed"
```

### Task D4: The card's own health

**Files:**
- Modify: `internal/factory/fmetrics/fmetrics.go`
- Modify: `internal/factory/reconciler/outcome.go`, `internal/factory/reconciler/reconciler.go`
  (`notePin`)
- Modify: `docs/observability.md`
- Test: `internal/factory/fmetrics/fmetrics_test.go`, `internal/factory/reconciler/outcome_test.go`

**Interfaces:**
- Produces three instruments, each recorded once per task at its end:

| Metric | Labels | Meaning |
|---|---|---|
| `agent_factory_workflow_choices_total` | `repository`, `class`, `choice` (`kept`, `overridden`, `stepped_up`) | Whether the automatic choice was left as it was, pinned by a person, or stepped |
| `agent_factory_ceiling_use_ratio` (histogram, buckets 0.05 to 1.5) | `repository`, `class`, `stage_count` | The task's actual dollars over the "up to" figure its card showed |
| `agent_factory_step_ups_total` | `repository`, `class`, `trigger`, `mode`, `outcome` | Each step and each offer, with how the task ended |

- [ ] **Step 1: Write the failing tests**

```go
func TestACardThatWasLeftAloneCountsAsKept(t *testing.T) {
	// source repository, no pin, no step: choice="kept"
}

func TestAPinCountsAsOverridden(t *testing.T) { // source label
}

func TestTheCeilingRatioIsSpendOverTheShownCeiling(t *testing.T) {
	// taskMicroUSD 5_100_000, spent 540_000: one observation of ~0.106
}
```

Each asserts on the rig's metric reader, as `outcome_test.go`'s `TestAnEscalationCountsOnce` does.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler -run 'CountsAsKept|CountsAsOverridden|CeilingRatio'`
Expected: FAIL to compile.

- [ ] **Step 3: Implement**, and document the three metrics and Task D1's two in
  `docs/observability.md` with one PromQL line each:

```promql
# share of automatic choices left unchanged, per class
sum by (class) (increase(agent_factory_workflow_choices_total{choice="kept"}[30d]))
  / sum by (class) (increase(agent_factory_workflow_choices_total[30d]))
# share of escalated tasks one step-up rescued
sum(increase(agent_factory_step_ups_total{mode=~"auto|manual", outcome=~"accepted|merged_human"}[30d]))
  / sum(increase(agent_factory_step_ups_total{mode=~"auto|manual"}[30d]))
```

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal docs
git commit -m "feat(metrics): how often the card's choice holds, steps up, and what it cost against its ceiling"
```

### Task D5: The report by repository, class and stage, and the card's typical cost

**Files:**
- Create: `internal/factory/api/stages.go` (the route), `internal/factory/stages/report.go` (the
  fold over ended Tasks)
- Modify: `internal/factory/api/server.go:237-250` (register the route)
- Modify: `internal/factory/catalogue/catalogue.go` (`Class`: `TypicalUSD`, `TypicalOf`)
- Modify: `internal/roomview/workflowcard.go` (the cost line)
- Modify: `internal/app/maku.go` (a `stages` command), `internal/maku/client.go`
- Modify: `docs/reference/api.md`, `docs/cli.md`, `docs/observability.md`
- Test: `internal/factory/stages/report_test.go`, `internal/factory/api/stages_test.go`,
  `internal/roomview/workflowcard_test.go`

**Interfaces:**
- Produces: `GET /v1/stages?repository=<owner/name>&class=<class>&last=<n>`, for a caller with the
  member role, like the catalogue's route:

```json
{"repository": "owner/repo", "tasks": 42, "merged": 31,
 "classes": [{"class": "docs", "tasks": 30, "merged": 24, "typicalUSD": 0.41, "p90USD": 1.10,
   "stages": [
     {"stage": "implement", "tasks": 30, "usd": 9.80, "effects": {}},
     {"stage": "review", "tasks": 30, "usd": 2.10,
      "effects": {"changes_committed": 7, "approve_agreed": 19, "approve_overruled": 2, "changes_ignored": 2}},
     {"stage": "step_up", "tasks": 4, "usd": 6.20, "effects": {"finished": 3, "escalated": 1}}]}]}
```

  The fold reads `status.stages` of the factory's ended Tasks (the same list the policy evidence
  route reads), newest first, `last` capped at 500. `typicalUSD` is the median dollars of merged
  tasks of the class and is present only from 30 of them.
- Produces: `maku stages [--repository owner/name] [--class c]`, a table of the same figures.
- Produces: the card's cost line gains the typical figure when the class has one:
  `Cost       up to $5.10 · typically $0.41`.

- [ ] **Step 1: Write the failing tests**

```go
func TestTheReportFoldsStagesByClass(t *testing.T) {
	tasks := []v1alpha1.Task{
		ended("docs", "accepted", stage("implement", 400_000, ""), stage("review", 90_000, "approve_agreed")),
		ended("docs", "escalated", stage("implement", 2_550_000, "")),
	}
	rep := Fold("owner/repo", tasks, 500)
	c := rep.Classes[0]
	if c.Class != "docs" || c.Tasks != 2 || c.Merged != 1 || c.TypicalUSD != 0 { // under 30 merged: no typical figure
		t.Fatalf("%+v", c)
	}
	if got := c.Stage("review").Effects["approve_agreed"]; got != 1 {
		t.Fatalf("review effects %+v", c.Stage("review").Effects)
	}
}

func TestATypicalCostNeedsThirtyMergedTasks(t *testing.T) {
	// 29 merged: TypicalUSD == 0; 30 merged at $0.30..$0.59: TypicalUSD is the median
}

func TestTheCardShowsTheTypicalCostOnlyWhenItExists(t *testing.T) {
	// TypicalUSD 0: "Cost       up to $5.10"; 0.41: "Cost       up to $5.10 · typically $0.41"
}
```

`stages_test.go`: the route answers 200 to a member, 403 to a caller with no role, and 400 to
`last=0`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/stages ./internal/factory/api -run Stages ./internal/roomview -run TypicalCost`
Expected: FAIL to compile.

- [ ] **Step 3: Implement.** The catalogue reads the class's typical figure from a report the
  factory folds once per ten minutes and caches; a cold cache shows no figure.

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add internal docs
git commit -m "feat(factory): the per-stage report, maku stages, and a typical cost on the card"
```

---

## Phase E · Unbundle `careful`

Release E. Depends on phases C and D, and on v5 Track 1 for the harness half (Task E1). Switches:
the row keys themselves, `scoper.planTier`, `loops.<row>.judgeInput` and a class's `requires`. The
three presets resolve to the runs they have after phase A, plus `ask` on.

The presets as rows after this phase:

```yaml
loops:
  default:  {ask: true, review: true, stallSteps: 80, judge: none}        # standard
  quick:    {ask: true, review: false, stallSteps: 80, judge: none}
  careful:  {ask: true, plan: true, tests: true, search: true, judge: tier-light, judgeInput: evidence,
             review: true, split: {maxChildren: 4, childTier: standard, anyTier: true}}
```

### Task E1: Investigation: the harness under OpenCode, and what a class requirement can read at triage

**Files (read only):**
- ai-native-ref `docs/superpowers/specs/2026-11-22-v5-roadmap-design.md` (Track 1), and the
  OpenCode harness plan `docs/superpowers/plans/2026-11-15-opencode-harness-maku-plan.md`
- `images/maku-harness/loop_policy.py`, `images/maku-harness/agent_run.py:1586`, `:2086-2180`
  (the stall rule and the judge round), `images/maku-harness/test_contract.py`
- Maku's OpenCode harness image directory, if `git ls-tree origin/main images/` lists one
- `internal/factory/triage/classify.go:213-226` (`spec.intake.class`), `:92-119` (the predicted
  class), `internal/factory/reconciler/arm.go` (where the gate chooses the class from the diff)

- [ ] **Step 1: Where do the judge and the stall rule live once OpenCode is the default harness?**

| Answer | What it changes |
|---|---|
| Track 1 ports `loop_policy.py` into the OpenCode image, called the same way | Tasks E5 and E2's `judge` key are built once, in `loop_policy.py`, and both images run them |
| Track 1 moves the judge and the stall rule out of the image, into the run-controller or the factory | Task E5 is built there instead; `images/maku-harness/` keeps today's judge for the OpenHands fallback, and the row keys do not change |
| Track 1 has not decided when phase E starts | Tasks E5 and the `judgeInput` key wait for it; E2, E3, E4, E6 and E7 do not touch the harness and ship as release E without them |

- [ ] **Step 2: What can `requires` read before a diff exists?**

A class is chosen from the diff at the gate; triage holds only `spec.predictedClass`, which is the
schedule's class, a maintainer-sponsored `spec.intake.class`, the origin's class, or
`defaults.predictedClass`.

| Answer | What it changes in Task E7 |
|---|---|
| The predicted class is good enough (the planner names it on most tasks) | `requires` binds through `spec.predictedClass` at triage only |
| It is not: label-path tasks all predict `defaults.predictedClass` | E7 also evaluates `requires` after the scoper's plan, from the paths the plan lists, and after the first push, from the diff: a `tests` or `plan` requirement discovered late sends the task back through that stage once, and the room says why |

Record both answers in the pull request of E-1.

### Task E2: The stage switches as independent row keys

**Files:**
- Modify: `internal/factory/config/config.go` (`Loop`, `validateLoops` near `:2575-2632`),
  `internal/factory/config/evaluation.go` (`over`, `UnmarshalJSON`)
- Create: `internal/factory/config/stages.go`
- Modify: `internal/factory/config/workflows.go` (the shipped rows; `quick` gains a row)
- Modify: `internal/factory/reconciler/reconciler.go` (`profileSpec`), `internal/factory/catalogue/catalogue.go` (`Path`)
- Modify: `docs/reference/config.md`, `docs/factory.md`, `docs/upgrading.md`
- Test: `internal/factory/config/stages_test.go`, `internal/factory/reconciler/profile_test.go`

**Interfaces:**
- Produces the row keys `ask *bool`, `plan *bool`, `review *bool` beside the existing `tests`,
  `search`, `judge` and `split`. `plan: true` is `scope: scoper`; `scope: steering` stays its own
  value; a row that sets both `plan` and a contradicting `scope` is refused.
- Produces:

```go
// Stages is what a task of a workflow runs, every switch resolved (WR6).
type Stages struct {
	Ask, Plan, Tests, Search, Review bool
	Judge                            string       // "" is no judge
	Split                            *SplitPolicy // nil is no split
}

func (c *Config) StagesFor(r *Repository, workflow string) Stages
func (s Stages) Names() []string // ask, plan, tests, search, judge, review, split, in that order
```

- `review` resolves the template for a workflow that names none: `pair` when on, `solo` when off. A
  workflow that sets `template: solo` and a row with `review: true` is refused. The gate keeps
  reading the template's roles.
- A row that sets none of the three new keys resolves as it does today (`plan` from `scope`,
  `review` from the template, `ask` from the scoper's forced question), so a platform's rows do not
  move.
- Tests: `TestThePresetsResolveToTheirStages` (the design's table, row by row),
  `TestAPlatformRowWithoutTheNewKeysResolvesAsBefore`, `TestPlanAndScopeMayNotDisagree`,
  `TestReviewOffOnAPairTemplateIsRefused`, `TestACustomWorkflowMayRunTheJudgeAlone` (a row
  `{judge: tier-light}` with no `plan`, `search` or `split`: the comparison the workflows review
  could not express).
- Proof: `go test ./internal/factory/config -run 'Stages|PresetsResolve|JudgeAlone' && task check`.

### Task E3: `ask`, the acceptance guard at intake for every workflow

**Files:**
- Create: `internal/factory/reconciler/ask.go`
- Modify: `internal/factory/reconciler/scoper.go:86-90`, `:111-163` (the forced question and
  `acceptanceText` move to `ask.go`; the scoper keeps its own question)
- Modify: `internal/factory/reconciler/reconciler.go` (`received`: after `profileSpec`, before
  `PhaseTriaged`)
- Modify: `internal/intake/onequestion.go` (`DoneWhen`: the planner's plan already asks it; a plan
  that answered it marks the task `ask: answered`)
- Modify: `docs/factory.md`, `docs/reference/narration.md`
- Test: `internal/factory/reconciler/ask_test.go`

**Interfaces:**
- Consumes: `Stages.Ask` (Task E2); the stage effect `ask` (Task D3).
- Produces: at triage, a task with an issue whose text states no acceptance and whose stages hold
  `ask` ends `Escalated needs_author` with the label `factory/needs-author` and the one question
  "Which command or observation proves it is done?", with no run started. A schedule's task (no
  issue) goes on as `assumed`, as the scoper's rule does today. `/factory retry` goes on as
  `assumed`. One question at most per task: a `careful` task asked at intake is not asked again by
  the scoper's forced rewrite.
- Tests: `TestAStandardTaskWithNoAcceptanceIsAskedBeforeAnyRun` (no `AgentRun` exists, no dollars
  spent), `TestATaskWithAcceptanceRunsUnasked`, `TestAScheduledTaskIsNeverAsked`,
  `TestACarefulTaskIsAskedOnce`, `TestAnAnsweredPlanIsNotAskedAgain`.
- Proof: `go test ./internal/factory/reconciler -run 'IsAskedBeforeAnyRun|RunsUnasked|NeverAsked|AskedOnce|NotAskedAgain'`.

### Task E4: The scoper's plan step runs on the strong model

**Files:**
- Modify: `internal/factory/config/config.go:940-962` (the `scoper` block: `planTier`)
- Modify: `internal/factory/reconciler/scoper.go:29-46` (`scoperSpec`)
- Modify: `docs/reference/config.md`
- Test: `internal/factory/reconciler/scoper_test.go`, `internal/factory/config/config_test.go`

**Interfaces:**
- Produces: `Factory.spec.scoper.planTier` (`light`, `standard`, `frontier`; unset is `light`,
  today's behaviour). The shipped `maku install --print` writes `frontier`. `scoperSpec` takes the
  model and the run caps of that tier in place of the hard-coded `light`, still never above an API
  task's ceiling-derived run.
- Tests: `TestTheScoperRunsAtThePlanTier` (model and `MaxTokens` are the `frontier` tier's),
  `TestAnUnsetPlanTierIsLight`, `TestTheScopersCostCountsTowardTheTask`.
- Proof: `go test ./internal/factory/reconciler -run 'ScoperRunsAtThePlanTier|UnsetPlanTier'`.

### Task E5: The judge reads machine evidence

**Files:**
- Modify: `images/maku-harness/loop_policy.py` (`judge_input`, `Offered`, `JUDGE_SYSTEM`)
- Modify: `images/maku-harness/agent_run.py` (where `judge_input` is called, near `:2116-2140`)
- Modify: `internal/factory/config/config.go` (`Loop.JudgeInput`), `internal/factory/runs/runs.go`
  (`Loop`, the claim's `spec.loop.judgeInput`)
- Test: `images/maku-harness/tests/test_loop_policy.py`, `internal/factory/runs/runs_test.go`

**Interfaces:**
- Consumes: Task E1's answer on where the judge lives.
- What the code already does: `judge_input(checks_text, head, files, diff, runs, paths)` takes the
  acceptance, the diff, the head's check runs and the required paths. It takes no message of the
  agent. So the spec's "no longer reads the run's closing narrative" needs a test that pins it, not
  a removal.
- Produces: `loops.<row>.judgeInput: evidence` adds one evidence block, `REPOSITORY CHECKS (id:
  agent-checks)`, built from the harness's own `/workspace/.agent-checks/<sha>.json` (never the
  agent's copy, which `agent_run.py` moves aside): per step its name, exit code, result and
  duration, then `passed N · failed N · timed out N`. `Offered` gains `checks_failed: tuple`, and
  `guard` turns `met` into `not_yet` while a declared step failed, as it does for a failed check
  run. Without the key the judge's input is today's.
- Tests: `test_the_judge_input_holds_no_agent_message` (the input built from a conversation whose
  last message says "all checks pass" does not contain that sentence),
  `test_evidence_lists_each_declared_step_with_its_exit_code`,
  `test_a_failed_declared_step_is_never_met`, `test_the_agents_own_result_file_is_not_evidence`.
- Proof: `task harness:test && go test ./internal/factory/runs`.

### Task E6: The reviewer checks correctness only, and may say nothing

**Files:**
- Modify: `internal/factory/reconciler/text.go` (the reviewer's brief),
  `internal/factory/reconciler/team.go:56-62`, `:97-103`
- Modify: `docs/factory.md` (the reviewer's paragraph)
- Test: `internal/factory/reconciler/team_test.go`, `internal/factory/reconciler/text_test.go`

**Interfaces:**
- Produces: the brief asks for defects against the diff and the acceptance checks only; it says
  that style, naming and scope the task did not ask for are not findings, and that `approve` with
  no comment is a complete answer. The verdict's shape and the gate's reading of it do not change.
- Tests: `TestTheReviewersBriefAsksForCorrectnessOnly` (the brief holds the acceptance text and the
  sentence on an empty approval, and none of "style", "naming" as things to report),
  `TestAnApprovalWithNoCommentIsAVerdict`.
- Proof: `go test ./internal/factory/reconciler -run 'ReviewersBrief|ApprovalWithNoComment'`.
  Phase D's `review` effects before and after this release are the measure; the adoption plan
  records them.

### Task E7: A `MergePolicy` class may require stages

**Files:**
- Modify: `internal/factory/config/classes.go:17-75` (`MergeClass`), `internal/factory/config/binding.go`
- Modify: `internal/factory/config/stages.go` (`StagesFor` takes the class)
- Modify: `internal/factory/reconciler/reconciler.go` (`received`), and, if Task E1 says so,
  `scoper.go` (after the plan) and `implement.go` (after the first push)
- Modify: `internal/roomview/workflowcard.go` (`Reason`: "touches `infrastructure/`")
- Modify: `docs/merge-policies.md`, `docs/reference/config.md`
- Test: `internal/factory/config/stages_test.go`, `internal/factory/reconciler/profile_test.go`

**Interfaces:**
- Consumes: Task E1's second answer.
- Produces: `MergePolicy.spec.requires` (`+kubebuilder:validation:MaxItems=4`, items of the enum
  `plan;tests;judge;review`). `func (c *Config) StagesFor(r *Repository, workflow, class string) Stages`
  adds the class's stages to the workflow's and never removes one. `tests` is added only where the
  repository has `tests.paths` and `merge.contractCheck`; otherwise the requirement is narrated as
  unmet and the gate hands the pull request to a maintainer with the reason
  `required_stage_missing`. `quick` under a class that requires `review` runs the reviewer.
- The card's reason gains `; the class <class> requires a plan` and the path gains the stage.
- Tests: `TestAClassRequirementAddsStagesToAnyWorkflow`, `TestARequirementNeverRemovesAStage`,
  `TestARequiredTesterWithoutTestsPathsHandsOff`, `TestTheCardNamesTheRequiringClass`, and, when E1
  chose the late evaluation, `TestARequirementFoundFromTheDiffRunsTheStageOnce`.
- Proof: `task crd:gen && go test ./internal/factory/... && task check`.

---

## Phase F · Outcomes beyond a pull request

Release F. Depends on phase E, on v5 Track 2 (spec intake) for what a plan contains, and on Track 7
for who may press a button in Slack. Switches: `Factory.spec.outcomes` (default `[change]`) and
`Repository.spec.workflow.planGate` (`ask`, the default, or `auto`).

### Task F1: Investigation: does approve-to-merge pass a two-approval ruleset?

**Files (read only):**
- `internal/factory/reconciler/arm.go`, `merge.go` (the approve-to-merge path: who merges, with
  which token, by which API call), `internal/factory/reconciler/escalated_gate_test.go`
- `docs/merge-policies.md` and `docs/github-apps.md` (the merger App's permissions, bypass lists)
- GitHub's ruleset documentation for "required approvals" and App bypass

- [ ] **Step 1: Answer and record in the pull request of F-1**

| Answer | What it changes |
|---|---|
| The merge is an ordinary merge by the merger App with no bypass: GitHub refuses it until two people approved | Nothing in code. `docs/merge-policies.md` gains one paragraph: two-human sign-off is a ruleset; the plan gate's **Approve** is not an approval of the pull request |
| The merger App is on the ruleset's bypass list on the reference install, so one approval merges | Task F3's page says so plainly, `maku repo check` gains a line that fails when `approveToMerge` is on and the App bypasses a required-approvals rule, and the adoption plan removes the bypass |
| It cannot be read from code or docs | Task F3 adds a drill step to the adoption plan's phase F live check (a throwaway repository with a two-approval ruleset) and this plan's `repo check` line waits for its result |

### Task F2: `Task.spec.outcome`, inferred by the planner and shown on the card

**Files:**
- Modify: `api/factory/v1alpha1/task_types.go` (`TaskSpec`), `api/factory/v1alpha1/factoryconfig_types.go`
  (`FactorySpec.Outcomes`)
- Modify: `internal/intake/plan.go:108-128` (`Issue`), `internal/intake/prompt.go`,
  `internal/intake/compose.go`
- Modify: `internal/factory/triage/triage.go` (the decision carries the outcome)
- Modify: `internal/roomview/workflowcard.go`, `internal/maku/start.go`, `internal/slackapp/proposal.go`
- Test: `internal/intake/plan_test.go`, `internal/factory/triage/triage_test.go`,
  `internal/roomview/workflowcard_test.go`

**Interfaces:**
- Produces: `TaskSpec.Outcome` (`json:"outcome,omitempty"`, enum `change;plan-first;review;report`,
  unset is `change`); `intake.Issue.Outcome` in the plan, material to its hash; `FactorySpec.Outcomes
  []string`, the outcomes this factory offers.
- Inference is deterministic first: a request holding "investigate", "why", "find out" as its verb
  → `report`; a pull request URL with "review" → `review`; "plan first", "show me the plan" →
  `plan-first`; the model's choice applies only among the offered outcomes and is shown as inferred.
  An outcome not in `Factory.spec.outcomes` falls back to `change`, with one line saying so.
- The card gains its first row, `Outcome    a pull request` (`a plan to approve, then a pull
  request`, `a review of #N`, `findings on the issue`), and the button **Plan first** on the three
  confirmation surfaces sets `plan-first`.
- Tests: `TestTheOutcomeIsInferredFromTheRequest` (a table of twelve requests),
  `TestAnOutcomeNotOfferedFallsBackToChange`, `TestTheOutcomeChangesThePlansHash`,
  `TestTheCardNamesTheOutcome`.
- Proof: `task crd:gen && go test ./internal/intake/... ./internal/factory/triage/... ./internal/roomview/...`.

### Task F3: The plan gate

**Files:**
- Create: `internal/factory/reconciler/plangate.go`
- Modify: `internal/factory/reconciler/scoper.go:101-104` (a `ready` scope under `plan-first` goes
  to the gate), `internal/factory/reconciler/watch.go` (the commands), `reconciler.go` (dispatch)
- Modify: `internal/factory/config/workflows.go` (`RepositoryWorkflow.PlanGate`, `PlanGateHours`)
- Modify: `internal/factory/narrate/narrate.go` (the plan comment), `internal/factory/intake/issues.go`
  (the label `plan-first`)
- Modify: `internal/factory/api/acts.go` and `server.go` (`POST /v1/tasks/{task}/plans`)
- Modify: `docs/factory.md` (the state diagram), `docs/reference/narration.md`
- Test: `internal/factory/reconciler/plangate_test.go`, `internal/factory/api/acts_test.go`

**Interfaces:**
- Produces the state `AwaitingHuman plan_review`, with the label `factory/plan-proposed`, entered
  when a `plan-first` task's scoper hands off `ready`. No run exists while it waits.
- Produces the plan comment on the issue: the bounded task, the files it expects to touch, the
  acceptance checks, the parts if it would split, and the three answers.
- Produces the answers, a maintainer's or the issue author's:

| Answer | Comment | Route body | Then |
|---|---|---|---|
| Approve | `/factory plan approve` | `{"decision": "approve"}` | The task runs as `change` on the approved scope |
| Revise | `/factory plan revise <one comment>` | `{"decision": "revise", "note": "..."}` | One more scoper run with the note, then the gate again; one revision per task, then a maintainer |
| Split | `/factory plan split` | `{"decision": "split"}` | The splitter's approval path (`/factory split`) |

- Produces: `Repository.spec.workflow.planGate: auto` approves at once and says so in the room;
  `planGateHours` (default 72, 1 to 720) is the wait. Past it the task stays parked, its status
  comment reads "parked: the plan was not answered in 72 hours; any of the three answers resumes
  it", and one *needs you* notification is sent. It never expires into a run or a stop on its own.
- A class that requires `plan` (Task E7) makes the task `plan-first` whatever was asked.
- Tests: `TestThePlanGateHoldsNoRun`, `TestApproveRunsTheApprovedScope`,
  `TestReviseRunsTheScoperOnceMore`, `TestASecondReviseGoesToAMaintainer`,
  `TestAnExpiredPlanGateSaysItIsParked`, `TestPlanGateAutoApprovesAndSaysSo`,
  `TestOnlyTheAuthorOrAMaintainerAnswersThePlan`.
- Proof: `go test ./internal/factory/reconciler -run PlanGate ./internal/factory/api -run Plan && task check`.
- The default wait, 72 hours, is the spec's proposed value: the owner's review of this plan
  confirms or changes the constant `DefaultPlanGateHours`; nothing else depends on the number.

### Task F4: `review`, a verdict on a pull request the factory did not write

**Files:**
- Modify: `internal/factory/config/config.go:1581` (templates: add `review`), `:1990-2008` (a lone
  reviewer needs no implementer), `api/factory/v1alpha1/task_types.go:114` (the template enum)
- Modify: `internal/factory/config/workflows.go` (`ShippedWorkflows`: `review: {roles: [reviewer]}`)
- Modify: `internal/factory/intake/issues.go` or a new `internal/factory/intake/reviews.go` (the
  label `factory/review` on a pull request)
- Modify: `internal/factory/reconciler/reconciler.go:1567-1602` (`queued`), `team.go`, `arm.go`
- Modify: `internal/slackapp/intents.go` (a mention with a pull request URL)
- Test: `internal/factory/reconciler/review_outcome_test.go`, `internal/factory/intake/reviews_test.go`

**Interfaces:**
- Produces: a task with `outcome: review` and `source.kind: review` on a pull request number. It
  runs one reviewer run with the reviewer's read-only token, posts the verdict comment, and ends
  `Done review_posted`. It never pushes, never merges, never opens a room for a second run.
- Produces: the gate ignores a factory reviewer's verdict on a pull request whose author is not the
  agents App: `arm.go` reads the verdict only from the task that owns the pull request.
- An adopted pull request (`workflow: none`) is unchanged: `review` is asked for by label.
- Tests: `TestAReviewTaskRunsTheReviewerAlone`, `TestAReviewTaskNeverGetsAWriteToken`,
  `TestTheGateIgnoresAVerdictOnAForeignPullRequest`, `TestTheReviewLabelIsAMaintainersOrTheAuthors`.
- Proof: `task crd:gen && go test ./internal/factory/... && task check`.

### Task F5: `report`, read-only findings on the issue

**Files:**
- Modify: `internal/factory/triage/classify.go:36-48`, `:92-94` (`investigate` is no longer forced
  to the `internal` data class when the outcome is `report` on a public repository)
- Modify: `internal/factory/config/config.go:2634-2652` (the `investigate` validation)
- Modify: `internal/factory/reconciler/implement.go:784-799` (the end: findings posted on the issue,
  and the offer), `internal/factory/reconciler/text.go` (`TriagerBrief` for a public report)
- Modify: `internal/factory/narrate/narrate.go`
- Test: `internal/factory/reconciler/report_test.go`, `internal/factory/triage/classify_test.go`

**Interfaces:**
- Produces: a task with `outcome: report` runs the `investigate` template (`[triager]`) at the
  task's data class, with the reviewer's read-only token and the public egress of a `public` task.
  It ends `Done findings_posted` with one comment on the issue: the findings, then "To have this
  fixed, a maintainer comments `/factory fix`", which files the fix as a `change` task on the same
  issue with the findings as its scope.
- RunLore's internal path is unchanged: its source still forces `internal`.
- Tests: `TestAReportTaskStartsNoImplementer`, `TestAReportOnAPublicRepositoryKeepsItsDataClass`,
  `TestTheFindingsOfferAFix`, `TestFactoryFixFilesAChangeWithTheFindings`,
  `TestARunLoreFindingStaysInternal`.
- Proof: `go test ./internal/factory/reconciler -run Report ./internal/factory/triage -run Report`.

### Task F6: The entries: labels, the Slack mention and the status words

**Files:**
- Modify: `internal/factory/intake/issues.go` (the labels `plan-first`, `report`, read with
  `factory/ready`), `internal/factory/config/hardening.go:508` (the label allow-list)
- Modify: `internal/slackapp/intents.go`, `internal/intent/model.go`
- Modify: `internal/summary/state.go` (`StatusWord`: `AwaitingHuman plan_review` is "waiting on
  you"), `internal/summary/needs.go` (the need kind `plan_review`)
- Modify: `docs/factory.md`, `docs/slack.md`, `docs/cli.md`
- Test: `internal/factory/intake/issues_test.go`, `internal/intent/intent_test.go`,
  `internal/summary/needs_test.go`

**Interfaces:**
- Produces: an issue labelled `plan-first` or `report` before `factory/ready` sets the outcome; two
  outcome labels at once refuse with `outcome_conflict` and the task runs `change`. A Slack mention
  holding a pull request URL and "review" drafts a `review` plan.
- Tests: `TestAnOutcomeLabelSetsTheOutcome`, `TestTwoOutcomeLabelsConflict`,
  `TestAMentionWithAPullRequestIsAReview`, `TestAPlanToReviewIsANeed`.
- Proof: `go test ./internal/factory/intake/... ./internal/intent/... ./internal/summary/... && task intent:eval`.

---

## Phase G · Act where you read

Release G. Depends on phases B and F. Switch: the broker's `human.roomActs`, a list among `answer`,
`retry`, `split`, `plan`, `file`, `stop`; release G's default is `[answer, retry]`.

### Task G1: The broker's acts and the factory routes behind them

**Files:**
- Modify: `internal/humanapi/acts.go` (the act kinds), `internal/humanapi/server.go:275-323`
- Modify: `internal/factory/api/answers.go`, `acts.go`, `server.go:224-229` (the routes take a room
  member's act through the broker, not the Slack App's principal alone)
- Modify: `internal/factory/reconciler/split.go:136-160` (the approval read from the route as from
  the comment)
- Modify: `internal/config/config.go` (the broker's `human.roomActs`)
- Modify: `docs/reference/api.md`
- Test: `internal/humanapi/acts_test.go`, `internal/factory/api/acts_test.go`

**Interfaces:**
- Produces the room acts, each `{ "kind": ... }` over the room's connection:

| Kind | Fields | Who | Factory route |
|---|---|---|---|
| `answer` | `text` | The issue's author or a maintainer | `POST /v1/tasks/{task}/answers` |
| `split` | `decision`: `accept` or `decline` | A maintainer; accepting charges the approver | `POST /v1/tasks/{task}/splits` (new) |
| `plan` | `decision`, `note` | The author or a maintainer | `POST /v1/tasks/{task}/plans` (Task F3) |
| `retry` | `deeper` | A maintainer | `POST /v1/tasks/{task}/retries` (Task C5) |
| `stop` | — | The task's owner or a maintainer | The existing cancel route |

- Each act is refused with a closed code when its kind is not in `human.roomActs`
  (`act_not_enabled`), and the factory, never the broker, decides who may.
- Tests: `TestAnAnswerActReachesTheFactoryAsTheViewer`, `TestASplitAcceptChargesTheApprover`,
  `TestAnActOutsideRoomActsIsRefused`, `TestAWatcherMayNotAct`.
- Proof: `go test ./internal/humanapi/... ./internal/factory/api/... && task check`.

### Task G2: The room's cards act on the page

**Files:**
- Modify: `web/src/needs.ts:33-100`, `web/src/controls.ts:333-340`, `:388` (the stop controls)
- Modify: `internal/summary/needs.go` (each need carries the act it accepts)
- Modify: `docs/web-ui.md`
- Test: `web/test/needs.test.ts`, `web/test/controls.test.ts`, `internal/summary/needs_test.go`

**Interfaces:**
- Consumes: Task G1's acts.
- Produces, per card: `question` → a text box and **Answer**; `split` → **Accept the split** and
  **Run it whole**, with the charge named; `plan_review` → **Approve**, **Revise** (with a one-line
  box), **Split**; `recovery` → Task C6's two buttons. `merge` and `review` keep their link to
  GitHub: the pull request is where a merge is approved.
- Produces: one **Stop** button in the room's header for whoever may stop, behind the two-press
  confirm; "discard" becomes a checkbox of that confirm; the line "label the issue `factory/stop`"
  leaves the owner fold.
- Tests: one per card kind asserting its buttons and that no `a.need-go` remains for it;
  `a card whose act is not enabled keeps its link to GitHub`.
- Proof: `task ui:test && task ui:build && task ui:check`.

### Task G3: The CLI acts: `maku answer`, `maku split`, `maku plan`

**Files:**
- Modify: `internal/app/maku.go:271` (the command list) and one function per command, beside
  `cancel` (`:960-990`)
- Modify: `internal/maku/answer.go` (the existing answer helper writes the decision into the issue;
  the command sends the act and keeps that record)
- Modify: `internal/roomview/card.go:355-366` (`answerLine`: the card's "You can" line names the
  commands that exist)
- Modify: `docs/cli.md`
- Test: `internal/app/maku_test.go`

**Interfaces:**
- Produces:

```text
maku answer <task> "<one line>"
maku split accept|decline <task>
maku plan approve|split <task>
maku plan revise <task> "<one comment>"
maku retry <task> [--deeper]        (Task C5)
maku cancel <task> [--discard]      (exists)
```

  Each prints one line saying what happens next, and the refusal's sentence on a refusal.
- Tests: one per command asserting the act sent and the line printed; `TestAnAnswerIsOneLine`
  (a multi-line answer is refused before it is sent, as `AppendDecision` refuses it).
- Proof: `go test ./internal/app -run 'Answer|Split|PlanCommand'`.

### Task G4: "New task" in the web UI and `maku start` in a terminal, over the existing planner

**Files:**
- Create: `web/src/newtask.ts`
- Modify: `internal/app/maku.go:271` (the command list) with a `start` command,
  `internal/maku/client.go` (the three handoff routes)
- Modify: `web/src/view.ts:438`, `:487-517` (the button beside **New room**)
- Modify: `internal/humanapi/server.go` (three routes over the handoff the MCP tools already call:
  `POST /api/handoffs`, `POST /api/handoffs/{id}/check`, `POST /api/handoffs/{id}/start`)
- Modify: `internal/humanapi/handoff.go`
- Modify: `internal/slackapp/proposal.go:79` (the multi-issue refusal names the page that now
  exists)
- Modify: `docs/web-ui.md`
- Test: `web/test/newtask.test.ts`, `internal/humanapi/handoff_test.go`

**Interfaces:**
- Consumes: the planner (`handoff`, `handoff_check`, `start`'s broker half), Task B1's card, Task
  F2's outcome.
- Produces: a form with one text box ("What should change?") and a repository picker. **Plan**
  shows the card, the planner's one question when it has one, the issue's title and body, a
  described workflow select for a maintainer, and **Plan first**. **Start** files the issue as the
  viewer (through their GitHub link) and labels it; a viewer with no link sees "Link your GitHub
  account" and no button.
- This reverses the UX review's "File a task: web no" and "Choose the workflow: web no".
- Produces, for a plain terminal, where no command files a task today:

```text
maku start [--repository owner/name] [--workflow <name>] [--plan-first] "<request>"
```

  It plans through the same three routes, prints the card and the issue, asks `File and start?
  [y/N]`, and files with the developer's `gh`, as the `start` tool does. `--workflow` is a
  maintainer's; anyone else gets the refusal's sentence and the default.
- Tests: `the new task form shows the card before it files`, `a viewer with no GitHub link cannot
  start`, `TestTheHandoffRoutesNeedAMember`, `TestStartFromTheWebFilesAsTheViewer`,
  `TestTerminalStartPrintsTheCardAndAsks`, `TestTerminalStartFilesNothingOnNo`.
- Proof: `task ui:test && go test ./internal/humanapi -run Handoff ./internal/app -run TerminalStart && task check`.

### Task G5: One inbox of five types on every surface

**Files:**
- Modify: `internal/summary/needs.go` (the kinds), `internal/humanapi/inbox.go:29-60`,
  `internal/humanapi/needs.go`, `internal/roomview/needs.go`
- Modify: `web/src/needs.ts`, `web/src/view.ts` (the list's "needs me" filter)
- Modify: `internal/app/maku.go:857-900` (`maku needs`), `internal/slackapp/answers.go` (`needs me`)
- Modify: `docs/cli.md`, `docs/slack.md`, `docs/web-ui.md`
- Test: `internal/summary/needs_test.go`, `internal/humanapi/inbox_test.go`

**Interfaces:**
- Produces the five types and the kinds each folds:

| Type | Kinds today |
|---|---|
| `question` | `question` |
| `plan` | `plan_confirmation`, `plan_review`, a proposed split |
| `review` | `merge`, `review` |
| `blocked` | `hold`, `failed_check`, an approval |
| `failed` | `recovery` |

- One entry per task (its most urgent type), ordered `question`, `plan`, `review`, `blocked`,
  `failed`; an entry is dropped when its task ended, its pull request merged or closed, or its
  question was answered elsewhere. The API keeps each item's `kind` and adds `type`.
- Tests: `TestEveryNeedKindHasAType`, `TestOneEntryPerTask`, `TestAStaleNeedIsDropped`, and a
  golden of `maku needs` grouped by type.
- Proof: `go test ./internal/summary/... ./internal/humanapi/... ./internal/roomview/... && task ui:test`.

### Task G6: Three notification classes

**Files:**
- Modify: `internal/slackapp/app.go:905-984` (the thread's lines), `internal/slackapp/endline.go`,
  `internal/slackapp/threads.go`
- Modify: `internal/factory/narrate/narrate.go` (the mention rule of each event)
- Modify: `docs/slack.md`, `docs/reference/narration.md`
- Test: `internal/slackapp/app_test.go`, `internal/factory/narrate/narrate_test.go`

**Interfaces:**
- Produces, as a field of every narration event, `Class`: `needs_you`, `changed` or `done`.

| Class | Mention | Shape |
|---|---|---|
| `needs_you` | Yes, the one person who can act | What is asked, one recommended action as a button or a command, and what happens if nothing is done ("it stays parked", "it stops in 24 hours") |
| `changed` | No | One line in the thread: a step-up, a run start, a pull request opened |
| `done` | Yes, once | The end line |

- Tests: `TestEveryNarrationEventHasAClass` (walks the package's event constructors),
  `TestANeedsYouMessageNamesTheDefault`, `TestAChangedLineMentionsNobody`, `TestDoneMentionsOnce`.
- Proof: `go test ./internal/slackapp/... ./internal/factory/narrate/...`.

---

## Phase H · Decomposition

Release H, a v5.x release. Depends on phase F (a plan a person approved is what gets filed), on
GitHub stacks being available to the forge client, and on nothing from the multi-repository design,
which keeps its own blockers. Switches: the broker's `intake.wholePlans` (default `false`) and
`loops.<row>.split.parallel` (1, the default, or 2).

**What waits for an earlier phase's result:** the parallel cap stays at the proposed value, two,
until phase D's report shows what share of a split family's wall time is waiting (the `split` and
`implement` stage durations of accepted splits); Task H3's default moves only on that figure and the
owner's word. Whether dependent parts form a GitHub stack or stay one-after-another waits for Task
H1. What a part's plan declares (`files`, `checks`) is the shape phase F's plan gate shows, so its
field names are fixed by Task F3's plan comment.

### Task H1: Investigation: stacks on the forge, and the two proposed numbers

**Files (read only):**
- `internal/factory/forge/` (the GitHub client: how a pull request's base is set and updated)
- `internal/factory/reconciler/split.go:321-355`, `:386-448`, `:450-510` (how a part is opened, on
  which base, and what closes the family)
- GitHub's documentation for stacked pull requests, and whether the merger App's merge of a base
  pull request retargets its dependents

- [ ] **Step 1: Answer and record in the pull request of H-1**

| Answer | What it changes |
|---|---|
| The forge retargets a dependent pull request when its base merges, and the App may create one with another pull request's branch as base | Task H4 builds stacks: part k+1 branches from part k's branch and opens against it |
| It does not, or the App may not | Task H4 is not built in release H: dependent parts stay one after another on the default branch (today's order), and the plan's `dependsOn` is honoured by ordering only. H2, H3 and H5 ship without it |

- [ ] **Step 2: Confirm the two numbers with the owner in this pull request's review**: at most two
  parts at once, at most four parts per parent (today's `maxChildren`). They are the constants
  `MaxParallelParts` and the shipped `split.maxChildren`; no other task depends on their value.

### Task H2: `start` and Slack file every issue of a confirmed plan

**Files:**
- Modify: `internal/maku/start.go:278-280` (the line "this files the first") and the filing loop
- Modify: `internal/slackapp/proposal.go:79` (the multi-issue refusal), `proposalaction.go`
- Modify: `internal/humanapi/handoff.go` (the confirmation returns every issue),
  `internal/intake/plan.go` (`DependsOn` kept through the hash)
- Modify: `api/factory/v1alpha1/task_types.go` (`TaskSpec.DependsOn`)
- Modify: `internal/factory/intake/issues.go` (reads the dependency marker),
  `internal/factory/reconciler/reconciler.go` (`received`: a task waits while a dependency is open)
- Test: `internal/maku/start_test.go`, `internal/factory/reconciler/depends_test.go`

**Interfaces:**
- Produces: with `intake.wholePlans` on, a confirmed plan of N issues files N issues, each carrying
  a hidden marker `<!-- maku depends-on: #12, #13 -->` and a visible line "Waits for #12". The
  form's line reads "The plan holds 3 issues: this files all three, in order."
- Produces: `TaskSpec.DependsOn []int32` (issue numbers, `MaxItems=4`); a task whose dependency has
  no merged pull request waits in `Triaged` with the reason `waiting_dependency`, holding no run and
  no slot of `caps.activeTasks`. A dependency closed unmerged ends the dependents `NoOp
  dependency_dropped`.
- Tests: `TestStartFilesEveryIssueOfThePlan`, `TestADependentTaskWaitsWithNoRun`,
  `TestADroppedDependencyEndsItsDependents`, `TestWholePlansOffFilesTheFirstOnly`.
- Proof: `task crd:gen && go test ./internal/maku/... ./internal/factory/... && task check`.

### Task H3: Parts run two at a time when the plan declares disjoint files

**Files:**
- Modify: `internal/factory/config/config.go:2453-2467` (`SplitPolicy.Parallel`)
- Modify: `internal/factory/reconciler/split.go:71-113` (the proposal's parts gain `files` and
  `checks`), `:450-510` (the opening rule)
- Modify: `internal/envelope/scope.go` (the split handoff's part shape)
- Modify: `internal/factory/reconciler/text.go` (the scoper's split brief asks for the two fields)
- Test: `internal/factory/reconciler/split_family_test.go`

**Interfaces:**
- Produces: `split.parallel` (1 or 2). A part of a proposal declares `files` (path globs) and
  `checks` (a subset of the repository's declared checks). Two parts may be open at once only when
  `parallel` is 2, their `files` do not overlap, each names at least one check, and neither depends
  on the other. A part that touches a file outside its declaration ends `Escalated
  outside_declared_files` and the family returns to one at a time.
- Each part keeps its own branch, pull request and room: one writer per branch.
- Tests: `TestDisjointPartsRunTwoAtATime`, `TestPartsWithASharedFileNeverRunTogether`,
  `TestAPartWithoutItsOwnCheckRunsAlone`, `TestAPartOutsideItsFilesSerialisesTheFamily`,
  `TestNeverMoreThanTwoPartsOpen`, `TestTheFamilyCapStillEndsTheFamily`.
- Proof: `go test ./internal/factory/reconciler -run 'Parts|Family'`.

### Task H4: Dependent parts form a stack

Built only if Task H1's first answer holds.

**Files:**
- Modify: `internal/factory/reconciler/split.go:386-448` (a dependent part's base),
  `internal/factory/forge/` (create with a base branch; read a retarget)
- Modify: `internal/factory/reconciler/merge.go` (a part whose base is another part's branch arms
  only once its base merged)
- Test: `internal/factory/reconciler/split_family_test.go`

**Interfaces:**
- Produces: part k+1 that depends on part k branches from `agent/<part k>` and opens against it.
  The merge gate's unit stays one pull request: a stacked part is evaluated against its own diff,
  and is armed only after its base pull request merged and GitHub retargeted it to the default
  branch. A base closed unmerged ends the stack above it (`child_dropped`).
- Tests: `TestADependentPartOpensAgainstItsBase`, `TestAStackedPartArmsOnlyAfterItsBaseMerged`,
  `TestAClosedBaseDropsTheStackAboveIt`.
- Proof: `go test ./internal/factory/reconciler -run 'Stack|DependentPart'`.

### Task H5: One tree on every surface

**Files:**
- Modify: `internal/summary/flow.go` (the split's parts carry state, cost and their strip),
  `internal/envelope/payloads.go` (`PartFact`)
- Modify: `web/src/rail.ts:419-428` (a lane per part), `web/src/flow.ts`
- Modify: `internal/factory/narrate/narrate.go` (the parent issue's table),
  `internal/slackapp/endline.go` (the thread's summary line)
- Modify: `internal/roomview/card.go` (`maku status` of a parent)
- Test: `internal/summary/flow_test.go`, `web/test/rail.test.ts`,
  `internal/factory/narrate/narrate_test.go`

**Interfaces:**
- Produces: on the parent issue, one table kept up to date in the pinned comment (part, issue, path
  strip, state, cost); in the thread, one line "3 parts: 1 merged · 1 working · 1 waiting for #12";
  in the room, a lane per part under the scoper's node, each lane a rail of that part's runs.
- Tests: `TestAParentsStripSummarisesItsParts`, `a split draws one lane per part`,
  `TestTheParentCommentListsEveryPart`.
- Proof: `go test ./internal/summary/... ./internal/factory/narrate/... && task ui:test`.

---

## Phase I · A workflow as one definition, a role as a file

Release I, the last, a v5.x release. Depends on phase E's `StagesFor` and on phase D's numbers.
Switch: the presence of `workflows.<name>.stages` and of `Factory.spec.roles`; a workflow without
`stages` keeps reading its template, tier and row.

**What waits for an earlier phase's result:** which row keys retire, and whether `template` and
`tier` warn or stay as synonyms, waits for Task I1's reading of phase E as built. The set of stage
options a team may set (`maxRounds`, `stall`, `search`, `judge`, `split`, `gate`) is fixed here from
the spec; any option phase D shows no install changed is left out of the first schema rather than
shipped unused. `maku workflow dry-run` reads phase D's `status.stages`, so its cost column exists
only for tasks that ended after release D.

### Task I1: Investigation: what phase D measured and what phase E left in the row

**Files (read only):**
- `GET /v1/stages` on the reference install (phase D's report), over at least thirty merged tasks
- `internal/factory/config/stages.go` as phase E built it; `internal/factory/config/workflows.go`
- `charts/agent-factory/values-demo.yaml:144-185` (the demo's redefined `solo` and `standard`)

- [ ] **Step 1: Answer and record in the pull request of I-1**

| Question | What each answer changes |
|---|---|
| Does every stage switch map to exactly one stage option of the list form? | Yes: Task I2 compiles `stages` to a `Stages` value and nothing else. No (a switch needs two options, or an option has no switch): I2 first adds the missing key to `Stages`, with its own test |
| Did any install set `templates.<name>.roles` to something other than the shipped lists? | Yes (the demo does): the list form must express it, and `templates` warns in release I and is refused in the next minor. No: `templates` is refused in release I for a workflow that sets `stages` |
| Which stages does the report show at near-zero effect? | None is removed from the presets by this plan (WR5: no default changes from these numbers without an owner ruling). The figures go into the presets' `description` only if the owner rules so in this pull request |

### Task I2: `stages`, the list form, and the presets compiled to it

**Files:**
- Modify: `internal/factory/config/mergepolicy.go:49-79` (`HarnessProfile`: `Budget`, `Stages`)
- Create: `internal/factory/config/definition.go`
- Modify: `internal/factory/config/workflows.go` (`ShippedWorkflows` returns the list form)
- Modify: `internal/install/factory.go` and its golden (`maku install --print` writes the list form)
- Modify: `docs/reference/config.md`, `docs/factory.md`, `docs/upgrading.md`
- Test: `internal/factory/config/definition_test.go`

**Interfaces:**
- Produces:

```go
type StageDef struct {
	// +kubebuilder:validation:MaxLength=63
	Role      string     `json:"role"`
	When      string     `json:"when,omitempty"`      // repository.testFirst
	Checks    bool       `json:"checks,omitempty"`
	Search    bool       `json:"search,omitempty"`
	Stall     bool       `json:"stall,omitempty"`
	Judge     string     `json:"judge,omitempty"`     // evidence, or a model alias
	MaxRounds int32      `json:"maxRounds,omitempty"` // the stage's one bounded loop
	Split     *SplitDef  `json:"split,omitempty"`     // {maxParts}
	Gate      *GateDef   `json:"gate,omitempty"`      // {when: plan-first | always}
}

func (c *Config) compile(name string, p HarnessProfile) (Stages, Template, error)
```

  with `HarnessProfile.Budget` (`light`, `standard`, `frontier`: the tier, under the name a person
  reads) and `HarnessProfile.Stages []StageDef` (`MaxItems=8`).
- Rules checked at load: the list is linear and holds exactly one `implementer`; `scoper` and
  `tester` come before it and `reviewer` after; one loop option and one gate at most per stage; a
  workflow sets `stages` or the old keys (`template`, `tier`, `loop`), not both.
- Tests: `TestTheSpecsTwoDefinitionsCompile` (the spec's `standard` and `careful` YAML, verbatim,
  compile to the same `Stages` and budget as the phase E presets), `TestAStageListIsLinear`,
  `TestStagesAndTemplateTogetherAreRefused`, `TestAPlatformsOldWorkflowStillLoads`,
  `TestTheInstallerWritesTheListForm`.
- Proof: `task crd:gen && go test ./internal/factory/config/... ./internal/install/... && task check`.

### Task I3: A role as a file, bound to a capability profile

**Files:**
- Modify: `api/factory/v1alpha1/factoryconfig_types.go` (`FactorySpec.Roles`)
- Create: `internal/factory/config/roles.go`
- Modify: `internal/factory/config/config.go:1457` (`roles()`: the built-in five plus the declared)
- Modify: `internal/factory/reconciler/team.go` (a custom role's run spec),
  `internal/factory/runs/runs.go` (the persona on the claim)
- Modify: `charts/agent-factory/` (the briefs' ConfigMap mount), `docs/reference/config.md`
- Test: `internal/factory/config/roles_test.go`, `internal/factory/reconciler/roles_test.go`

**Interfaces:**
- Produces:

```yaml
roles:
  security-reviewer:
    capability: read
    model: agent-default
    effort: high
    brief: roles/security-reviewer.md
```

  `RoleDef{Capability, Model, Effort, Brief string}`, at most 16, a name matching the workflow
  name's pattern and never a built-in's. `brief` is a path under the factory's configuration
  directory, read at load, at most 16 KiB.
- Produces the closed capability profiles, where the enforcement lives:

| Profile | Run role on the claim | Token | May write |
|---|---|---|---|
| `read` | `reviewer` | Read-only | Nothing |
| `tests` | `tester` | Write, limited to the repository's `tests.paths` | Test paths |
| `write` | `implementer` | Write | The task's branch |

  The Task CRD's run-role enum does not grow: a custom role is a persona over one of the four run
  roles, as the scoper is a persona over `triager`. In release I a custom role may bind `read`
  only; `tests` and `write` are the built-in tester's and implementer's.
- Tests: `TestARoleBindsOneCapability`, `TestACustomRoleNeverGetsAWriteToken`,
  `TestABriefOutsideTheConfigDirectoryIsRefused`, `TestABuiltInRoleNameIsRefused`.
- Proof: `task crd:gen && go test ./internal/factory/... && task check`.

### Task I4: A custom read role as a stage, and a repository that only narrows

**Files:**
- Modify: `internal/factory/config/definition.go` (a stage's `role` may name a declared role)
- Modify: `internal/factory/reconciler/reconciler.go:1567-1602` (`queued`: the next stage from the
  compiled list, in place of the hard-coded order), `team.go`
- Modify: `internal/factory/reconciler/arm.go` only to pin, in a test, that it still reads the
  built-in reviewer's verdict
- Modify: `internal/factory/config/workflows.go` (`RepositoryWorkflow`: `budget`, `addStages`)
- Test: `internal/factory/reconciler/definition_test.go`, `internal/factory/config/workflows_test.go`

**Interfaces:**
- Produces: a stage `{role: security-reviewer}` after the implementer runs one read-only run with
  that role's brief and posts its findings as a comment; `maxRounds` on it sends `changes` back to
  the implementer like the reviewer's. The merge gate reads the built-in reviewer's verdict only.
- Produces: `Repository.spec.workflow.budget` (a tier at or below the workflow's) and
  `Repository.spec.workflow.addStages` (stages among those the factory's definition marks
  `allowed`). A repository that names a higher budget, or removes or reorders a stage, is refused at
  admission with the workflow's own value in the message (WR12).
- Tests: `TestTheSpecsMeasureIsExpressible` (a workflow with a tester and a second read-only
  reviewer loads and runs both, with no code change beyond config: the spec's last measure),
  `TestTheGateReadsTheBuiltInReviewerOnly`, `TestARepositoryMayLowerTheBudget`,
  `TestARepositoryMayNotRaiseTheBudget`, `TestARepositoryMayNotRemoveAStage`,
  `TestTheHardCodedOrderAndTheCompiledListAgreeOnThePresets`.
- Proof: `go test ./internal/factory/... && task check`.

### Task I5: `maku workflow dry-run`

**Files:**
- Create: `internal/factory/stages/dryrun.go`, `internal/factory/api/dryrun.go`
- Modify: `internal/factory/api/server.go` (`POST /v1/workflows/dry-run`)
- Modify: `internal/app/maku.go` (the `workflow` command), `internal/maku/client.go`
- Modify: `docs/cli.md`, `docs/reference/api.md`
- Test: `internal/factory/stages/dryrun_test.go`, `internal/app/maku_test.go`

**Interfaces:**
- Consumes: `status.stages` of ended Tasks (Task D1), `compile` (Task I2).
- Produces: `maku workflow dry-run <name> [--file definition.yaml] [--repository owner/name] [--last 20]`.
  For each of the last twenty ended tasks it prints what the named definition would have run (its
  stages against the task's class and outcome) and an estimate: the recorded dollars of the stages
  both runs share, plus the class's median dollars for each stage the definition adds, minus those
  it drops. The last line is the total against what the tasks cost.

```text
$ maku workflow dry-run thorough --file thorough.yaml --last 20
TASK      CLASS  RAN (standard)            WOULD RUN (thorough)                       COST    ESTIMATE
3buqdlot  docs   implementer → reviewer    implementer → reviewer → security-reviewer $0.54   $0.63
...
20 tasks: $9.80 as run · about $11.90 under thorough · 14 of 20 estimates use a class median
```

- With `--file` the definition is validated and compiled by the factory and never stored.
- Tests: `TestADryRunAddsTheMedianOfANewStage`, `TestADryRunDropsARemovedStagesCost`,
  `TestADryRunSaysWhenItHasNoFigure` (a stage with fewer than five recorded runs in the class prints
  `?` and is left out of the total), `TestADryRunStoresNothing`.
- Proof: `go test ./internal/factory/stages/... ./internal/app -run DryRun && task check`.

---

## Left to the builder (from the spec)

- The exact wording of each card line, reason and notification, within the shapes fixed above and
  Slack's 75-character limits.
- The buckets of `agent_factory_ceiling_use_ratio` beyond the range given.
- The style of the web card, the lanes and the "New task" form: they follow the room page's existing
  components (`web/src/controls.ts`, `web/src/rail.ts`).
- Whether `maku stages` and `maku workflow dry-run` also print JSON (`--json`): follow what
  `maku status --json` does.

## Self-review

| Spec item | Task |
|---|---|
| WR1 one path, three questions | C3 (depth), E7 (verification by class), H2 and H3 (decomposition) |
| WR2 repair first | A1 to A6 |
| WR3 one card on every surface | B1 to B6; D5 (typical cost); F2 (outcome row) |
| WR4 step up once, run again deeper | C1 to C6 |
| WR5 every role measured | D1 to D5 |
| WR6 `careful` unbundled | E2, E7 |
| WR7 roles change shape | E3 (question at intake), E4 (scoper model), E5 (judge evidence), E6 (reviewer) |
| WR8 outcomes | F2 to F6 |
| WR9 act where you read | C5, C6, G1 to G6 (file a task: G4, web and terminal) |
| WR10 decomposition | H2 to H5 |
| WR11 one definition, a role as a file | I2 to I5 |
| WR12 budgets only narrow | C3 (cap asks), I4 |
| WR13 a wait is a state with a reason, a default and a deadline | E3, F3, H2 |
| WR-O1 freeze lifted | C2 (the shipped ladder), D1 |
| WR-O3 reviewer kept | Global Constraints; E2 keeps `review` on in `standard` and `careful` |
| WR-O4 naming | B7 |
| Phase A table: stall rule, split, tester key, dead label, stale pages | A2, A3, A4, A5, A6 |
| The card's rules: reason from facts, roles as roles, dollars, strip, one vocabulary | B1, B3, B2, B7 |
| Phase C table: triggers, one step, pins, who pays, announcement, by hand, same task | C1, C3, C3, C3, C4, C5 and C6, C5 |
| Phase D table and the card's health | D2, D3, D4, D5 |
| "To settle": stall rule with `judge: none` | A1 |
| "To settle": the judge and the stall rule under OpenCode | E1 |
| "To settle": approve-to-merge under a two-approval ruleset | F1 |
| "To settle": the parallel cap and the plan-gate wait | H1 (cap), F3 (wait) |
| `maku workflow dry-run` | I5 |
