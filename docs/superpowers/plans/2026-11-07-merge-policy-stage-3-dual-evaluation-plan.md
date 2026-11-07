# Merge policy self-service, stage 3 (dual evaluation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every merge decision the gate acts on is decided a second time under the repository's declared policy, and the agreement is counted and written into the decision record, behind `policyManagement.dualEvaluation`; the second decision decides nothing.

**Architecture:** `mergepolicy.Watch` already holds each owned repository's resolved classes (the stage 2 plan, Task 3). The reconciler gets a `Policy` source; at the point `awaitingCI` counts a decision, `dualOf` runs `DecideArmUnder` on the same `ArmInputs` the central decision read and classifies the difference with stage 1's comparison. A counter, a log line and two marker fields record it.

**Tech Stack:** Go (Maku), OpenTelemetry metrics through `internal/factory/fmetrics`, the decision record of `internal/factory/decision`.

**Spec:** [`docs/superpowers/specs/2026-11-04-merge-policy-self-service-design.md`](../specs/2026-11-04-merge-policy-self-service-design.md) · **Predecessor:** [the stage 2 plan](2026-11-07-merge-policy-stage-2-simulation-plan.md)

**Read against:** Maku `origin/main` `3e60f820` plus the stage 2 plan. Every code block is the compiled code of [Smana/maku#381](https://github.com/Smana/maku/pull/381), written test first.

## Deviation: written before the stage-1 exit

The same deviation as the stage 2 plan, recorded there in full: the owner asked on 2026-11-07 for
stages 2 and 3 to be built before stage 1's live proof (plan 1, Task 10; ai-native-ref#321 open).
`policyManagement.dualEvaluation` stays `false` here until stage 1's exit criteria pass, and its
week of evidence (Task 4) starts only then.

## Global Constraints

- The central decision is the one acted on, always: dual evaluation changes no verdict, phase, label, merge or narration text beyond the record's two fields.
- `policyManagement.dualEvaluation` defaults to off and needs `read` (config validation refuses it alone). Off, the factory reads no snapshot and the record is byte-for-byte as before.
- Metric labels stay bounded (MP18): `repository` through `s.repository()`, `class` is the task's predicted class (the central config's), `agreement` from a closed list. The policy hash goes to the record and the log, never to a label.
- The tally's regex must keep reading every record (`scripts/shadow-merge-tally.sh`): the new fields sit before `reviewer=`.
- Maku: `task check` exits 0 before every PR; SPDX line; conventional commits in English, no trailers. Wrap test runs in `systemd-run --user --scope -q -p MemoryMax=6G`.

## Rulings this plan takes from reading the code

| # | The spec says | The code says | This plan |
|---|---|---|---|
| D1 | Stage 3: "dual evaluation", no switch named | The spec's switch list has none for stage 3 | `policyManagement.dualEvaluation`, off, needing `read` |
| D2 | "Zero unexplained divergence" for a week | Two decisions can differ for a reason stage 1 already reports, or because the central gate never read an input the repository's class needs: it reads the diff only for a decision that would arm or shadow its own class | Five agreements: `agree`; `explained` (the class is in the snapshot's `Divergences`); `unread` (the repository's decision would arm or shadow and needs the unread diff); `unexplained`; `no_policy`. The exit counts `unexplained` only |
| D3 | Every decision binds to its policy and guardrail snapshot (MP12) | The guardrails and profiles are the process's config, already bound by the pod's config checksum | The record carries `policy=<first 12 hex of the file's sha256>`; the config hash is the rolled pod's |
| D4 | Divergence "recorded" | GitHub markers are the durable decision record; the database index is plan 5's | The decision record (`policy=`, `dual=`), the counter, and a log line with both decisions on every disagreement |
| D5 | Compare the decisions | `awaitingCI` adjusts the evaluator's decision after it: `patch_too_large` at GitHub's 300-file cap, `human_commit_in_pr`, `closes_parent` | Compare the evaluator's own decisions (`evaluated`, captured after each `DecideArm`), on the same inputs: the later rows read the same facts for both |
| D6 | A wait is no decision (D2 of the human path) | `awaitingCI` counts only a non-wait decision | Dual evaluation runs where `MergeDecision` is counted, so a reconcile loop waiting on CI evaluates nothing twice |

## Files

| File | Responsibility |
|---|---|
| `internal/factory/decision/decision.go` | `Rows.Policy`, `Rows.Dual`; printed only when `Dual` is set |
| `internal/factory/fmetrics/fmetrics.go` | `maku_factory_policy_dual_decisions_total`, `PolicyAgreements`, `PolicyDualDecision` |
| `internal/factory/reconciler/dual.go` | `dualOf`, `Reconciler.dual` |
| `internal/factory/reconciler/reconciler.go`, `merge.go` | The `Policy` source, the `evaluated` capture, the call |
| `internal/app/factory.go` | `Watch.Snapshot` as the source when both switches are on |
| `docs/factory.md`, `docs/operations.md` | The switch, the record's fields, the metric |

---

### Task 1: The record's dual fields

**Files:**
- Modify: `internal/factory/decision/decision.go`
- Test: `internal/factory/decision/decision_test.go`
- Modify: `scripts/testdata/tally/prs-decisions.json` (one record gains the fields)

**Interfaces:**
- Produces: `decision.Rows.Policy, Rows.Dual string`

- [ ] **Step 1: Write the failing test**

```go
// Dual evaluation (merge policy stage 3) binds the decision to the repository policy it was
// compared with, and says whether the two agreed. Off, the marker is as it was.
func TestTheDualFieldsPrintOnlyWhenRead(t *testing.T) {
	if got := Marker("abc", "c", "human", "r", Rows{}); strings.Contains(got, "policy=") || strings.Contains(got, "dual=") {
		t.Fatal(got)
	}
	got := Marker("abc", "c", "human", "r", Rows{Reviewer: "none", Policy: "0123456789ab", Dual: "agree"})
	if !strings.HasSuffix(got, " policy=0123456789ab dual=agree reviewer=none -->") {
		t.Fatal(got)
	}
	if got := Marker("abc", "c", "human", "r", Rows{Dual: "no_policy"}); !strings.Contains(got, " policy=- dual=no_policy ") {
		t.Fatal(got)
	}
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/decision/`
Expected: FAIL to build: unknown fields `Policy`, `Dual`.

- [ ] **Step 3: Implement**

```diff
@@ -22,16 +22,25 @@ type Rows struct {
 	Shape, Holdout, Oracle, Age, Evidence string
 	Paused, Capped, Gated                 bool
 	Reviewer                              string
+	// Policy and Dual are merge policy stage 3's dual evaluation: the first 12 hex digits of the
+	// repository policy's hash ("" when none was read) and whether its decision agreed with this
+	// one. Dual is "" with dual evaluation off, and then neither prints.
+	Policy, Dual string
 }
 
 // Marker is the hidden one-line record appended to the decision's comment. It is a line of its
 // own beside the comment's event marker (ruling R-m11), and class= lets the tally filter by
 // class (R-I9). An unread field prints "-" (R-m7): an empty string, and the counts of a diff not
 // read, so a replay never reads a count of 0 that nobody took. Every field is one token.
+// The dual fields sit before reviewer, which the tally reads last.
 func Marker(head, class, verdict, reason string, r Rows) string {
-	return fmt.Sprintf("<!-- agent-factory-decision head=%s class=%s decision=%s:%s files=%s/%d lines=%s/%d shape=%s holdout=%s oracle=%s age=%s evidence=%s paused=%s capped=%s reviewer=%s -->",
+	dual := ""
+	if r.Dual != "" {
+		dual = fmt.Sprintf(" policy=%s dual=%s", dash(r.Policy), r.Dual)
+	}
+	return fmt.Sprintf("<!-- agent-factory-decision head=%s class=%s decision=%s:%s files=%s/%d lines=%s/%d shape=%s holdout=%s oracle=%s age=%s evidence=%s paused=%s capped=%s%s reviewer=%s -->",
 		dash(head), dash(class), dash(verdict), dash(reason), count(r.Files, r.Counted), r.MaxFiles, count(r.Lines, r.Counted), r.MaxLines,
-		dash(r.Shape), dash(r.Holdout), dash(r.Oracle), dash(r.Age), dash(r.Evidence), flag(r.Paused, r.Gated), flag(r.Capped, r.Gated), dash(r.Reviewer))
+		dash(r.Shape), dash(r.Holdout), dash(r.Oracle), dash(r.Age), dash(r.Evidence), flag(r.Paused, r.Gated), flag(r.Capped, r.Gated), dual, dash(r.Reviewer))
 }
 
 // dash is s, or "-" for an unread value.
```

- [ ] **Step 4: Run it to verify it passes; prove the tally still reads a dual record.** In the tally fixture, give the first `capped=false reviewer=glm-5.3` record ` policy=0123456789ab dual=agree` before `reviewer=`, then:

```bash
systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/decision/
bash scripts/shadow-merge-tally_test.sh
```

Expected: PASS, and `ok`: the regex's `.*reviewer=` spans the new fields.

- [ ] **Step 5: Commit** (with Task 3 in Maku#381)

### Task 2: The counter

**Files:**
- Modify: `internal/factory/fmetrics/fmetrics.go`
- Test: `internal/factory/fmetrics/repository_test.go`

**Interfaces:**
- Produces: `PolicyAgreements() []string` = `agree, explained, unread, unexplained, no_policy`; `(*Set).PolicyDualDecision(ctx, repository, class, agreement string)`

- [ ] **Step 1: Write the failing test.** In `TestPolicyMetricsAreBounded`, record two decisions and expect one series:

```go
s.PolicyDualDecision(t.Context(), "Smana/a", "docs-links", "unexplained")
s.PolicyDualDecision(t.Context(), "Smana/a", "docs-links", "not-an-agreement")
// want:
`maku_factory_policy_dual_decisions_total{agreement="unexplained",class="docs-links",repository="Smana/a"`,
// and refuse "not-an-agreement" beside "not-a-reason"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run TestPolicyMetricsAreBounded ./internal/factory/fmetrics/`
Expected: FAIL to build: `s.PolicyDualDecision undefined`.

- [ ] **Step 3: Implement**

```diff
@@ -177,6 +177,7 @@ type Set struct {
 	owned                metric.Int64Gauge
 	policyLoadErrors     metric.Int64Counter
 	policyDivergence     metric.Int64Gauge
+	policyDual           metric.Int64Counter
 	refusals             metric.Int64Counter
 	unpricedModels       metric.Int64Counter
 	excludesCache        metric.Int64Counter
@@ -428,6 +429,9 @@ func New(meter metric.Meter, tasks client.Reader, ns string, leader func() bool)
 	s.policyDivergence, err = meter.Int64Gauge("agent_factory_policy_central_divergence",
 		metric.WithDescription("Classes on which a repository's merge policy differs from the central config, as last compared: 0 is equivalent. A repository never compared has no series; the value is the last comparison's."))
 	check(err)
+	s.policyDual, err = meter.Int64Counter("agent_factory_policy_dual_decisions_total",
+		metric.WithDescription("Merge decisions decided again under the repository's policy (stage 3), by agreement: agree, explained (the policy differs where the comparison says), unread (the diff it needed was not read), unexplained, or no_policy. Nothing is decided on it."))
+	check(err)
 	s.refusals, err = meter.Int64Counter("agent_factory_admission_refusals_total",
 		metric.WithDescription("Run requests refused on their repository: bound to another, no write on GitHub, or not this factory's."))
 	check(err)
@@ -566,6 +570,21 @@ func (s *Set) PolicyDivergence(ctx context.Context, repository string, n int) {
 	s.policyDivergence.Record(ctx, int64(n), metric.WithAttributes(attribute.String("repository", s.repository(repository))))
 }
 
+// PolicyAgreements are dual evaluation's agreement values (merge policy stage 3, MP18).
+func PolicyAgreements() []string {
+	return []string{"agree", "explained", "unread", "unexplained", "no_policy"}
+}
+
+// PolicyDualDecision counts one merge decision decided again under the repository's policy, by
+// the class's name and whether the two agreed; an agreement outside the list is not counted.
+func (s *Set) PolicyDualDecision(ctx context.Context, repository, class, agreement string) {
+	if !slices.Contains(PolicyAgreements(), agreement) {
+		return
+	}
+	s.policyDual.Add(ctx, 1, metric.WithAttributes(attribute.String("repository", s.repository(repository)),
+		attribute.String("class", class), attribute.String("agreement", agreement)))
+}
+
 // AdmissionRefused counts a run request refused on its repository, the one ctx names. Other
 // refusals have their own codes and are not counted here.
 func (s *Set) AdmissionRefused(ctx context.Context, reason string) {
```

Add its row to `docs/operations.md`'s metric table, beside `maku_factory_policy_central_divergence`.

- [ ] **Step 4: Run it to verify it passes**, same command: PASS.

### Task 3: Decide again, record, decide nothing

**Files:**
- Create: `internal/factory/reconciler/dual.go`
- Modify: `internal/factory/reconciler/reconciler.go` (the `metrics` interface, the `Policy` field), `internal/factory/reconciler/merge.go`, `internal/factory/reconciler/reconciler_test.go` (`fakeMetrics`)
- Modify: `internal/app/factory.go`
- Test: `internal/factory/reconciler/dual_test.go`

**Interfaces:**
- Consumes: `DecideArmUnder`, `withShape` (stage 2, Task 5); `mergepolicy.Snapshot` and `Watch.Snapshot` (stage 2, Task 3); `Rows.Policy/Dual` (Task 1); `PolicyDualDecision` (Task 2)
- Produces: `Reconciler.Policy func(repository string) (mergepolicy.Snapshot, bool)`; `dualOf(central ArmDecision, in ArmInputs, snap mergepolicy.Snapshot, ok bool) (ArmDecision, string)`

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"errors"
	"slices"
	"strings"
	"testing"

	v1alpha1 "github.com/Smana/maku/api/factory/v1alpha1"
	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

func snapshotOf(classes map[string]mergepolicy.Resolved, divergences ...string) mergepolicy.Snapshot {
	return mergepolicy.Snapshot{Hash: "0123456789abcdef", HasClasses: true, Classes: classes, Divergences: divergences}
}

// Stage 3: the decision is made again under the repository's policy and the two compared. The
// agreement is closed (fmetrics.PolicyAgreements) and explains each difference it can.
func TestDualAgreement(t *testing.T) {
	same := map[string]mergepolicy.Resolved{"dead-links": {Class: declaredClass()}}
	loose := declaredClass()
	loose.MaxModifiedLines = 0
	strict := declaredClass()
	strict.MaxModifiedLines = 1
	holdout := declaredClass()
	holdout.HoldoutChecks = nil
	for name, tc := range map[string]struct {
		snap   mergepolicy.Snapshot
		ok     bool
		mutate func(*ArmInputs)
		want   string
	}{
		"no snapshot":       {mergepolicy.Snapshot{}, false, func(*ArmInputs) {}, "no_policy"},
		"an invalid file":   {mergepolicy.Snapshot{Hash: "ab", Err: errors.New("x")}, true, func(*ArmInputs) {}, "no_policy"},
		"a fence-only file": {mergepolicy.Snapshot{Hash: "ab"}, true, func(*ArmInputs) {}, "no_policy"},
		"the same class":    {snapshotOf(same), true, func(*ArmInputs) {}, "agree"},
		"the same refusal":  {snapshotOf(same), true, func(in *ArmInputs) { in.Stats[0].Additions = 20 }, "agree"},
		"a known difference": {snapshotOf(map[string]mergepolicy.Resolved{"dead-links": {Class: strict}}, "dead-links: central {...}, repository {...}"),
			true, func(*ArmInputs) {}, "explained"},
		"an unknown difference": {snapshotOf(map[string]mergepolicy.Resolved{"dead-links": {Class: strict}}, "revert: only in the repository"),
			true, func(*ArmInputs) {}, "unexplained"},
		"the class absent": {snapshotOf(map[string]mergepolicy.Resolved{}, "dead-links: only in the central config"), true, func(*ArmInputs) {}, "explained"},
		"the diff it needs, unread": {snapshotOf(map[string]mergepolicy.Resolved{"dead-links": {Class: holdout}}), true,
			func(in *ArmInputs) { in.DiffRead, in.Stats = false, nil; in.Checks.Runs[2].State = "FAILURE" }, "unread"},
		"a looser class, the diff read": {snapshotOf(map[string]mergepolicy.Resolved{"dead-links": {Class: loose}}), true,
			func(in *ArmInputs) { in.Stats[0].Additions = 20 }, "unexplained"},
	} {
		t.Run(name, func(t *testing.T) {
			in := gateInputs()
			tc.mutate(&in)
			central := DecideArm(in)
			_, got := dualOf(central, in, tc.snap, tc.ok)
			if got != tc.want {
				t.Fatalf("got %q, want %q", got, tc.want)
			}
		})
	}
}

// The repository's decision is the evaluator's, under the snapshot's class.
func TestDualDecidesUnderTheSnapshot(t *testing.T) {
	strict := declaredClass()
	strict.MaxModifiedLines = 1
	in := gateInputs()
	repo, _ := dualOf(DecideArm(in), in, snapshotOf(map[string]mergepolicy.Resolved{"dead-links": {Class: strict}}), true)
	if repo.Verdict != "human" || repo.Reason != "patch_too_large" {
		t.Fatalf("%+v", repo)
	}
}

// Stage 3 wired: with dualEvaluation on, a decision the gate acts on is decided again, counted,
// and its record names the policy and the agreement. The central decision is the one acted on.
func TestTheGateEvaluatesTheRepositoryPolicyBesideTheCentral(t *testing.T) {
	g := mergeRig(t, v1alpha1.PhaseAwaitingCI)
	g.r.Cfg.Classes = map[string]config.Class{"docs-links": {Shadow: true}, "revert": {Shadow: true}}
	g.r.Cfg.PolicyManagement = config.PolicyManagement{Read: true, DualEvaluation: true}
	g.r.Policy = func(string) (mergepolicy.Snapshot, bool) {
		live := withShape(config.Class{Live: true}, "docs-links") // the repository would merge it
		return snapshotOf(map[string]mergepolicy.Resolved{"docs-links": {Class: live}}, "docs-links: central {...}, repository {...}"), true
	}
	g.f.SetChecks(12, green("SUCCESS"))
	if tk := g.reconcile(t, "3buqdlot", 1); tk.Status.Phase != v1alpha1.PhaseAwaitingHuman || len(g.f.Armed()) != 0 {
		t.Fatalf("the central shadow decision stands: %s %s", tk.Status.Phase, tk.Status.Reason)
	}
	if !slices.Contains(g.metrics.recorded, "policy_dual docs-links explained") {
		t.Fatalf("%q", g.metrics.recorded)
	}
	if c := strings.Join(g.f.Comments(12), "\n"); !strings.Contains(c, " policy=0123456789ab dual=explained reviewer=") {
		t.Fatalf("%s", c)
	}
}

// Off, nothing is read, counted or written beyond what the gate did before.
func TestDualEvaluationOffReadsNothing(t *testing.T) {
	g := mergeRig(t, v1alpha1.PhaseAwaitingCI)
	g.r.Cfg.Classes = map[string]config.Class{"docs-links": {Shadow: true}, "revert": {Shadow: true}}
	g.r.Cfg.PolicyManagement = config.PolicyManagement{Read: true}
	g.r.Policy = func(string) (mergepolicy.Snapshot, bool) {
		t.Fatal("read with the switch off")
		return mergepolicy.Snapshot{}, false
	}
	g.f.SetChecks(12, green("SUCCESS"))
	g.reconcile(t, "3buqdlot", 1)
	if c := strings.Join(g.f.Comments(12), "\n"); strings.Contains(c, "dual=") {
		t.Fatalf("%s", c)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run 'Dual|TheGateEvaluates' ./internal/factory/reconciler/`
Expected: FAIL to build: `undefined: dualOf`, `g.r.Policy undefined`.

- [ ] **Step 3: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"context"
	"slices"
	"strings"

	v1alpha1 "github.com/Smana/maku/api/factory/v1alpha1"
	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// The agreements of a dual evaluation (fmetrics.PolicyAgreements).
const (
	dualAgree       = "agree"
	dualExplained   = "explained"
	dualUnread      = "unread"
	dualUnexplained = "unexplained"
	dualNoPolicy    = "no_policy"
)

// dualOf decides in again under the repository policy snap (merge policy stage 3) and says how it
// compares with central, the decision the gate acts on: agree; explained when the two differ on
// a class the stage-1 comparison already lists as divergent; unread when the repository's
// decision would need the diff the central one did not read; unexplained otherwise; no_policy
// without a valid policy that has classes. Pure: the caller records it.
func dualOf(central ArmDecision, in ArmInputs, snap mergepolicy.Snapshot, ok bool) (ArmDecision, string) {
	if !ok || snap.Err != nil || !snap.HasClasses {
		return ArmDecision{}, dualNoPolicy
	}
	class := in.Task.Spec.PredictedClass
	r, inPolicy := snap.Classes[class]
	var repo ArmDecision
	if inPolicy {
		repo = DecideArmUnder(in, r.Variants(), r.Approval)
	} else {
		repo = DecideArmUnder(in, nil, nil)
	}
	switch {
	case repo.Verdict == central.Verdict && repo.Reason == central.Reason && repo.Matched == central.Matched:
		return repo, dualAgree
	case slices.ContainsFunc(snap.Divergences, func(d string) bool { return strings.HasPrefix(d, class+": ") }):
		return repo, dualExplained
	case !in.DiffRead && (repo.Verdict == "arm" || repo.Verdict == "shadow") && readsDiff(r, class):
		return repo, dualUnread
	}
	return repo, dualUnexplained
}

// readsDiff is whether deciding the class reads the diff, any variant or the approval subset.
func readsDiff(r mergepolicy.Resolved, class string) bool {
	return len(r.Approval) > 0 || slices.ContainsFunc(r.Variants(), func(v config.Class) bool { return v.ReadsDiff(class) })
}

// dual records a decision's dual evaluation, with policyManagement.dualEvaluation on: the counter,
// a log line with both decisions, and the record's policy and dual fields. It changes nothing the
// gate acts on: central's verdict is still the decision.
func (r *Reconciler) dual(ctx context.Context, t *v1alpha1.Task, in ArmInputs, central ArmDecision, d *ArmDecision) {
	if !r.Cfg.PolicyManagement.DualEvaluation || r.Policy == nil {
		return
	}
	snap, ok := r.Policy(t.Spec.Repository)
	repo, agreement := dualOf(central, in, snap, ok)
	d.Rows.Policy, d.Rows.Dual = shortHash(snap.Hash), agreement
	class := t.Spec.PredictedClass
	record(ctx, func(ctx context.Context) { r.Metrics.PolicyDualDecision(ctx, t.Spec.Repository, class, agreement) })
	if agreement != dualAgree {
		r.log().Info("merge decision under the repository policy", "task.id", t.Name, "head", in.PR.HeadSHA, "class", class,
			"agreement", agreement, "policy", d.Rows.Policy, "central", central.Verdict+":"+central.Reason,
			"repository", repo.Verdict+":"+repo.Reason)
	}
}

func shortHash(h string) string { return h[:min(len(h), 12)] }
```

```diff
@@ -32,6 +32,7 @@ import (
 	"github.com/Smana/maku/internal/factory/forge"
 	"github.com/Smana/maku/internal/factory/killswitch"
 	"github.com/Smana/maku/internal/factory/ledger"
+	"github.com/Smana/maku/internal/factory/mergepolicy"
 	"github.com/Smana/maku/internal/factory/meter"
 	"github.com/Smana/maku/internal/factory/narrate"
 	"github.com/Smana/maku/internal/factory/rooms"
@@ -109,6 +110,7 @@ type metrics interface {
 	TraceExportAbandoned(ctx context.Context)
 	ClassMismatch(ctx context.Context, predicted, matched string)
 	MergeDecision(ctx context.Context, class, verdict, reason string)
+	PolicyDualDecision(ctx context.Context, repository, class, agreement string)
 	ClassPaused(ctx context.Context, repository, class string, paused bool)
 	Resumed(ctx context.Context, reason string)
 	LoopRun(ctx context.Context, class, end string)
@@ -173,7 +175,11 @@ type Reconciler struct {
 	// Owned is v2 D7's fence: the merge gate hands a repository this factory does not own to a
 	// human. nil owns nothing.
 	Owned func(repository string) bool
-	Runs  RunClient
+	// Policy is a repository's merge policy as the fence last read it (mergepolicy.Watch), which
+	// policyManagement.dualEvaluation decides each merge decision under a second time, deciding
+	// nothing on it (stage 3). nil: no dual evaluation.
+	Policy func(repository string) (mergepolicy.Snapshot, bool)
+	Runs   RunClient
 	// Kind is the runs kind, required: SetupWithManager watches its AgentRuns.
 	Kind    runwatch.Kind
 	Rooms   RoomLog
```

In `merge.go`, capture the evaluator's decision after each `DecideArm` and call `dual` where the decision is counted:

```go
d := DecideArm(in)
evaluated := d // the evaluator's own decision, before the rows read after it, for dual evaluation
// ... after the diff pass's second DecideArm:
d = DecideArm(in)
evaluated = d
// ... where a non-wait decision is counted:
record(ctx, func(ctx context.Context) { r.Metrics.MergeDecision(ctx, class, verdict, reason) })
r.dual(ctx, t, in, evaluated, &d)
```

In `reconciler_test.go`'s `fakeMetrics`:

```go
func (m *fakeMetrics) PolicyDualDecision(_ context.Context, _, class, agreement string) {
	m.add("policy_dual " + class + " " + agreement)
}
```

And the wiring:

```diff
@@ -272,9 +272,15 @@ func runFactory(ctx context.Context, log *slog.Logger, getenv func(string) strin
 	// v2 D7: a repository is acted on only while its default branch names this factory.
 	fenced := &fence.Fence{Name: cfg.Factory, Repositories: conns.names(), Read: conns.fenceFile,
 		Every: fenceEvery, Stale: fenceStale, Now: time.Now, OnState: m.RepositoryOwned, Log: log}
-	// Stage 1 (merge policy): observed and compared, deciding nothing.
+	// Stages 1 and 3 (merge policy): observed and compared, then each merge decision decided again
+	// under it; neither decides anything.
+	var snapshots func(string) (mergepolicy.Snapshot, bool)
 	if cfg.PolicyManagement.Read {
-		fenced.OnFile = (&mergepolicy.Watch{Cfg: cfg, Metrics: m, Log: log}).Observe
+		w := &mergepolicy.Watch{Cfg: cfg, Metrics: m, Log: log, Now: time.Now}
+		fenced.OnFile = w.Observe
+		if cfg.PolicyManagement.DualEvaluation {
+			snapshots = w.Snapshot
+		}
 	}
 	costs := &meter.Costs{} // the meter writes each run's cost, the reconciler sums a task's
 	runUSD := map[string]float64{}
@@ -299,7 +305,7 @@ func runFactory(ctx context.Context, log *slog.Logger, getenv func(string) strin
 		c7 = triage.HTTPClassifier{URL: cfg.Triage.ClassifierURL, HC: httpx.New(classifierTimeout, nil)}
 	}
 	rec := &reconciler.Reconciler{Kind: cfg.Runs, Client: mgr.GetClient(), Ledger: live, Namespace: ns, Cfg: cfg, Clients: conns.task, Owned: fenced.Owned,
-		CanWrite: perms.CanWrite, Runs: rc, Rooms: broker,
+		Policy: snapshots, CanWrite: perms.CanWrite, Runs: rc, Rooms: broker,
 		Triage: triage.Classify{Cfg: cfg, C: c7,
 			Clients: conns.class},
 		Metrics: m, Now: time.Now, Nonce: taskid.Random, Log: log,
```

- [ ] **Step 4: Run the whole package, then the gate**

```bash
systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/factory/reconciler/ ./internal/factory/... ./internal/app/
systemd-run --user --scope -q -p MemoryMax=6G task check
```

Expected: PASS; `task check` exits 0 (with Docker down, `internal/store` fails to start its container: say so and rely on CI).

- [ ] **Step 5: Commit**

```bash
git add internal docs scripts/testdata
git commit -m "feat(factory): dual evaluation of every merge decision under the repository policy, behind policyManagement.dualEvaluation"
```

### Task 4: The stage 3 exit (live, after stage 1's and stage 2's)

- [ ] **Step 1: Check the preconditions.** Plan 1's Task 10 passed (the canary's file valid and equivalent, `repository_owned` 1), and the stage 2 plan's Task 9 ran. The Maku release holding this plan is pinned.
- [ ] **Step 2: Switch it on.** A one-line config PR here: `policyManagement: {read: true, dualEvaluation: true}`. The owner merges it.
- [ ] **Step 3: Read the signals daily for a week**

```promql
sum by (agreement) (increase(maku_factory_policy_dual_decisions_total{repository="Smana/cloud-native-ref"}[1d]))
```

Expected: `agree` grows with the decisions; `unexplained` has no series or stays at 0; `explained` only while `maku_factory_policy_central_divergence` is above 0; `no_policy` never once the canary's file is read. For any disagreement, the log line `merge decision under the repository policy` gives both decisions, and the PR's record gives `policy=`.

- [ ] **Step 4: Record the result** in `docs/runbooks/agent-factory/results-merge-policy-stage-3-<date>.md`: the week's counts, each `explained`/`unread` decision with its reason, and the policy hash. Stage 3 exits after one week with zero `unexplained`; then the stage 4 plan (repository authority) is written.

---

## Out of scope: stage 4 and later

| Stage | What remains | Where it starts |
|---|---|---|
| 4 | Repository authority: the gate decides on `DecideArmUnder` for a cut-over repository; invalid, unreadable or stale policy pauses auto-merge fail-closed; a relaxation (`Structural`) returns the class to shadow; the 24 central `Classes` readers, schedules naming a deletable class, per-repository loops; policy-bot rules per `any` branch; ai-native-ref's own fence-file pin | One week of this plan's signals without `unexplained` |
| 5 | Grants (`approval_grants`, events), the broker's decision index and `merge_policy_snapshots`, grants consulted by the approval branch | Plan 4 |
| 6 | Settings UI, editor, the internal simulation endpoint over `reconciler.Simulate`, promotion, templates | Plan 4, plan 1's Q1 checks |

## Self-review

- **Coverage:** the spec's stage 3 row (dual evaluation, divergence evidence, merge authority central) is Tasks 1–3; its exit is Task 4. MP12's binding is D3; MP18 is the counter's labels.
- **Placeholders:** none.
- **Names:** `Policy`, `dualOf`, `dual`, `evaluated`, `PolicyDualDecision`, `PolicyAgreements`, `Rows.Policy`, `Rows.Dual` are consistent across tasks.
