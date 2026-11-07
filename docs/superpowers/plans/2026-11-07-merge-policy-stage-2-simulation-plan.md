# Merge policy self-service, stage 2 (simulation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One evaluator decides a class read from a repository's `.github/agent-factory.yaml` exactly as the gate decides a central class, with `any` and the approval subset; a policy can be simulated on versioned decision fixtures and diffed structurally, behind `policyManagement.simulation`, with the central config still the only merge authority.

**Architecture:** `DecideArm` is split into `decide(in, rc, cl)`, and `DecideArmUnder(in, variants, approval)` runs that same rule on each `any` branch of a resolved repository class (MP16 by construction, not by parity testing). `mergepolicy` resolves a class into variants, refuses predicates that check nothing, keeps the resolved classes in its snapshot and evaluates a fence file once per hash. Simulation and the structural diff are offline `maku policy` verbs.

**Tech Stack:** Go (Maku), `sigs.k8s.io/yaml`, OpenTelemetry metrics through `internal/factory/fmetrics`.

**Spec:** [`docs/superpowers/specs/2026-11-04-merge-policy-self-service-design.md`](../specs/2026-11-04-merge-policy-self-service-design.md) · **Predecessor:** [the stage 0 and 1 plan](2026-11-04-merge-policy-stage-1-read-plan.md) · **Successor:** [the stage 3 plan](2026-11-07-merge-policy-stage-3-dual-evaluation-plan.md)

**Read against:** Maku `origin/main` `3e60f820`. Unlike plan 1, every code block below is the compiled code of [Smana/maku#381](https://github.com/Smana/maku/pull/381), written test first.

## Deviation: written before the stage-1 exit

The program (plan 1) writes each plan after its predecessor's exit. Stage 1's exit is a live proof
on aws-0 (plan 1, Task 10) that has not run: ai-native-ref#321, which switches `policyManagement.read`
on, is open. The owner asked on 2026-11-07 for stages 2 and 3 to be built now. So this plan and the
stage 3 plan were written alongside their implementation, against Maku as it stands, and:

- **Nothing is enabled.** `policyManagement.simulation` and `policyManagement.dualEvaluation` stay
  `false` in this repository's config until stage 1's exit criteria pass (Task 10 of plan 1: the
  canary's file valid and equivalent, `repository_owned` still 1). Stage 2's live step (Task 9
  here) runs only after that.
- **The risk is the order, not the code.** Both stages decide nothing; with their switches off
  the factory behaves as on `3e60f820`, which the full `task check` proves.

## Global Constraints

- Merge authority stays central through stage 3: every decision the gate acts on is `DecideArm`'s on the central config. `DecideArm`'s decisions and records are unchanged (Task 5 proves it).
- New behaviour sits behind `policyManagement.simulation` (default off); `read` keeps stage 1's meaning.
- The closed vocabulary grows by `any` only. `any` is one level of branches, each a conjunction of leaves; no nesting, no new leaf.
- Metric labels stay bounded (MP18); no new metric in this stage.
- Maku: `task check` exits 0 before every PR; each Go file starts with the SPDX line; conventional commits in English, no trailers.
- This machine: wrap each test run in `systemd-run --user --scope -q -p MemoryMax=6G`. Never override `HOME`. `internal/store` needs Docker; when it is down, say so and rely on CI.

## Rulings this plan takes from reading the code

| # | The spec or plan 1 says | The code says | This plan |
|---|---|---|---|
| S1 | Plan 2 delivers a `merge_policy_snapshots` table | The factory has no database client: the broker owns the store, and its grant/decision API arrives with plan 5. The table's reader is the settings UI (plan 6) | A snapshot is the in-process `mergepolicy.Snapshot` (hash, validity, resolved classes, read time), bound into each decision record by stage 3 (MP12). The table lands with plan 5's broker API |
| S2 | Plan 2 delivers an internal simulation API | Its only consumer is the human API's settings pages (plan 6) | Simulation is `maku policy simulate` over fixtures, the gate's own evaluator. The HTTP endpoint lands with plan 6, calling the same `reconciler.Simulate` |
| S3 | `all`/`any` composition | Policy-bot's `if` is a conjunction (R5) | `any: [[leaf...], [leaf...]]`: at least 2 and at most 8 branches, none empty, a key in `all` or in the branches, never both. Each branch resolves to a whole `config.Class` (a variant) |
| S4 | "Most restrictive rule wins" (MP6) | Deny paths are in every variant, so a deny refuses every branch | A class holds when one variant does: arm outranks shadow, shadow a wait, a wait any refusal; with none holding, the first variant's refusal is the decision's reason |
| S5 | Q3: a shadow class with an approval subset and no grant records would-require-approval | Grants are plan 5's | `DecideArmUnder` applies `requiresApproval` to a class arm or shadow once the diff is read: live → `human:approval_required`, shadow → `shadow:shadow_would_require_approval`. No grant exists yet, so none is consulted |
| S6 | Every class has a policy-bot `low-risk:` rule | A class using `any` needs one rule per branch (R5) | Not generated here. Plan 4 refuses authority to a class using `any` until each branch has its rule |
| S7 | "Simulator divergence disables simulation" | The verbs are offline | `maku policy simulate` and `maku policy diff` refuse a config with `policyManagement.simulation` off: the switch is the kill switch |
| S8 | Plan 1 carried the Observe cost to plan 4 | Observe parsed and compiled every pattern on each fence read: a crafted file cost 2.8 to 8 s a read | Pulled forward at the owner's request: an unchanged hash is not evaluated again, a file holds at most 256 patterns in all (`MaxFilePatterns`), and R4's "bound length and count only" is corrected in `policy.go`'s comment. Measured after: the worst file under the bounds, 46 ms on first read, 95 µs unchanged |
| S9 | Stage 2 exits when the simulator matches runtime "on fixtures and recent PRs" | A past decision's inputs (the task's status, room events, the head's pushes) are not on GitHub | Fixtures here. Recent PRs come from stage 3: every real decision is evaluated under both, on the inputs the gate actually read |
| S10 | Structural relaxation detection (MP8) | Patterns are regular expressions; containment between two is undecidable in general here | Patterns compare as written: a removed one tightens, an added or rewritten one relaxes. Uncertainty fails toward relaxation, as MP8 says |

## Files

| File | Responsibility |
|---|---|
| `internal/factory/mergepolicy/policy.go` | `any`, empty-predicate refusal, per-file pattern bound |
| `internal/factory/mergepolicy/resolve.go` | Variants, `OnlyGuardrail`, guardrails per variant |
| `internal/factory/mergepolicy/export.go` | Pinned profiles skipped; `any` has no central form |
| `internal/factory/mergepolicy/watch.go` | Evaluate once per hash; resolved classes in the snapshot |
| `internal/factory/mergepolicy/structural.go` | Tightening or relaxation, class by class |
| `internal/factory/config/mergepolicy.go` | `simulation`, `dualEvaluation` (stage 3) |
| `internal/factory/reconciler/arm.go`, `evaluate.go` | `decide`, `DecideArmUnder` |
| `internal/factory/reconciler/simulate.go`, `merge.go` | Fixtures, `Simulate`, the extracted `provenance` row |
| `internal/factory/reconciler/testdata/conformance/*.json` | Sixteen version-1 fixtures |
| `internal/app/maku_policy.go` | `policy simulate`, `policy diff` |

---

### Task 1: `any`, and predicates that check nothing

**Files:**
- Modify: `internal/factory/mergepolicy/policy.go`
- Modify: `internal/factory/mergepolicy/policy_test.go` (drop the `"any, until stage 2"` row)
- Test: `internal/factory/mergepolicy/policy_any_test.go`

**Interfaces:**
- Produces: `Conditions.Any [][]Leaf`; constants `MaxFilePatterns = 256`, `MaxBranches = 8`; `ClassPolicy.patterns() [][]string`

Plan 1 carried: `allowedFiles: []`, `maxPatchFiles: 0`, `deny: [{}]` and `requiresApproval: [{}]` read as absent and pass as equivalent; a negative cap was labelled a guardrail fault. All are shape errors now.

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"strings"
	"testing"
)

// any is a list of branches, each a list of leaves: the class holds when all holds and one branch
// does (MP4). One level only, so the vocabulary stays closed.
func TestParseAny(t *testing.T) {
	f, err := Parse([]byte("factory: aws-0\nclasses:\n  c:\n    mode: shadow\n    author: agents\n    harness: p\n" +
		"    conditions:\n      all: [{maxPatchFiles: 3}]\n      any:\n        - [{diffShape: links-only}]\n        - [{allowedFiles: ['^docs/']}, {maxModifiedLines: 5}]\n"))
	if err != nil {
		t.Fatal(err)
	}
	if b := f.Classes["c"].Conditions.Any; len(b) != 2 || len(b[0]) != 1 || len(b[1]) != 2 {
		t.Fatalf("%+v", b)
	}
}

// An empty predicate reads as absent, so it would pass as equivalent and check nothing: refused
// before any gate reads the parser's output (plan 1, carried to plan 2).
func TestParseRefusesWhatChecksNothing(t *testing.T) {
	cl := func(cond string) string {
		return "factory: aws-0\nclasses:\n  c: {mode: shadow, author: agents, harness: p, " + cond + "}\n"
	}
	many := strings.Repeat("[{maxPatchFiles: 1}], ", MaxBranches+1)
	for name, tc := range map[string]struct{ in, want string }{
		"allowedFiles empty":        {cl("conditions: {all: [{allowedFiles: []}]}"), "allowedFiles is empty"},
		"holdoutChecks empty":       {cl("conditions: {all: [{holdoutChecks: []}]}"), "holdoutChecks is empty"},
		"companionFiles empty":      {cl("conditions: {all: [{companionFiles: []}]}"), "companionFiles is empty"},
		"maxPatchFiles zero":        {cl("conditions: {all: [{maxPatchFiles: 0}]}"), "maxPatchFiles is at least 1"},
		"maxModifiedLines neg":      {cl("conditions: {all: [{maxModifiedLines: -1}]}"), "maxModifiedLines is at least 1"},
		"diffShape empty":           {cl("conditions: {all: [{diffShape: ''}]}"), "diffShape is empty"},
		"releaseAgeCheck empty":     {cl("conditions: {all: [{releaseAgeCheck: ''}]}"), "releaseAgeCheck is empty"},
		"requiredLabel empty":       {cl("conditions: {all: [{requiredLabel: ''}]}"), "requiredLabel is empty"},
		"an empty pattern":          {cl("conditions: {all: [{allowedFiles: ['']}]}"), "an empty pattern"},
		"an empty deny":             {cl("conditions: {deny: [{}]}"), "protectedFiles is empty"},
		"an empty approval":         {cl("requiresApproval: [{}]"), "changedFiles is empty"},
		"a negative day cap":        {cl("limits: {maxPerDay: -1}"), "maxPerDay is 0 (the guardrail's) or more"},
		"an empty any":              {cl("conditions: {any: []}"), "any holds at least two branches"},
		"one branch":                {cl("conditions: {any: [[{maxPatchFiles: 1}]]}"), "any holds at least two branches"},
		"an empty branch":           {cl("conditions: {any: [[], [{maxPatchFiles: 1}]]}"), "a branch of any is empty"},
		"too many branches":         {cl("conditions: {any: [" + many + "]}"), "branches"},
		"a key in all and a branch": {cl("conditions: {all: [{maxPatchFiles: 1}], any: [[{maxPatchFiles: 2}], [{modifyOnly: true}]]}"), "maxPatchFiles is in all and in a branch"},
		"a leaf twice in a branch":  {cl("conditions: {any: [[{maxPatchFiles: 1}, {maxPatchFiles: 2}], [{modifyOnly: true}]]}"), "twice"},
		"two keys in a branch leaf": {cl("conditions: {any: [[{maxPatchFiles: 1, modifyOnly: true}], [{modifyOnly: true}]]}"), "exactly one"},
		"nested any":                {cl("conditions: {any: [[{any: []}], [{modifyOnly: true}]]}"), "any"},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := Parse([]byte(tc.in))
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

// The per-list bound let 32 classes carry thousands of patterns, each compiled on every read (a
// crafted file cost 2.8 to 8 s): the file's total is bounded too.
func TestParseBoundsThePatternsOfTheWholeFile(t *testing.T) {
	var b strings.Builder
	b.WriteString("factory: aws-0\nclasses:\n")
	for i := range 5 {
		b.WriteString("  c" + string(rune('a'+i)) + ":\n    mode: off\n    author: agents\n    harness: p\n    conditions:\n      all:\n        - allowedFiles: [")
		for j := range MaxPatterns {
			if j > 0 {
				b.WriteString(", ")
			}
			b.WriteString("'^d/'")
		}
		b.WriteString("]\n")
	}
	if _, err := Parse([]byte(b.String())); err == nil || !strings.Contains(err.Error(), "patterns in the file") {
		t.Fatalf("got %v", err)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/mergepolicy/`
Expected: FAIL to build: `Conditions has no field or method Any`, `undefined: MaxBranches`.

- [ ] **Step 3: Implement**

```diff
@@ -23,13 +23,16 @@ import (
 	"github.com/Smana/maku/internal/factory/fence"
 )

-// The file's bounds. The patterns compile to RE2, linear in their input, so only their size is
-// bounded here: GitHub's contents API and the validator do the rest.
+// The file's bounds. The patterns compile to RE2, linear in the paths they match, but compiling
+// them is not free: a crafted file of 32 classes at 64 patterns a list cost 2.8 to 8 s a read. So
+// the count is bounded per list and per file, and Watch compiles a file once, not on every read.
 const (
 	MaxFileBytes    = 256 << 10
 	MaxClasses      = 32
 	MaxPatterns     = 64
+	MaxFilePatterns = 256
 	MaxPatternBytes = 512
+	MaxBranches     = 8
 )

 // Mode is a class's state: live merges, shadow records, off does neither.
@@ -80,9 +83,12 @@ type ClassPolicy struct {
 	Monitor          *config.Monitor `json:"monitor,omitempty"`
 }

-// Conditions are a class's predicates. Any leaf absent from All is not checked.
+// Conditions are a class's predicates. Any leaf absent from All and Any is not checked. Any is
+// one level of branches, each a conjunction of leaves: the class holds when All holds and one
+// branch does. A key is in All or in the branches, never both, so no branch overrides All.
 type Conditions struct {
 	All  []Leaf     `json:"all,omitempty"`
+	Any  [][]Leaf   `json:"any,omitempty"`
 	Deny []DenyLeaf `json:"deny,omitempty"`
 }

@@ -167,7 +173,11 @@ func Parse(raw []byte) (*File, error) {
 		return nil, fmt.Errorf("mergepolicy: at most %d classes", MaxClasses)
 	}
 	var errs []error
+	total := 0
 	for _, name := range slices.Sorted(maps.Keys(f.Classes)) {
+		for _, list := range f.Classes[name].patterns() {
+			total += len(list)
+		}
 		if err := f.Classes[name].shape(); err != nil {
 			errs = append(errs, fmt.Errorf("class %s: %w", name, err))
 		}
@@ -175,6 +185,9 @@ func Parse(raw []byte) (*File, error) {
 			errs = append(errs, fmt.Errorf("%q is not a class name", name))
 		}
 	}
+	if total > MaxFilePatterns {
+		errs = append(errs, fmt.Errorf("at most %d patterns in the file, not %d", MaxFilePatterns, total))
+	}
 	if err := errors.Join(errs...); err != nil {
 		return nil, fmt.Errorf("mergepolicy: %w", err)
 	}
@@ -195,35 +208,50 @@ func (p ClassPolicy) shape() error {
 	if p.Harness == "" {
 		errs = append(errs, errors.New("harness is required: a profile of the central list"))
 	}
-	seen := map[string]bool{}
-	var patterns [][]string
-	for _, l := range p.Conditions.All {
-		names := l.names()
-		if len(names) != 1 {
-			errs = append(errs, fmt.Errorf("a leaf of all sets exactly one key, not %v", names))
-			continue
+	if p.Limits.MaxPerDay < 0 {
+		errs = append(errs, errors.New("limits.maxPerDay is 0 (the guardrail's) or more"))
+	}
+	inAll := map[string]bool{}
+	errs = append(errs, leaves(p.Conditions.All, inAll)...)
+	if b := p.Conditions.Any; b != nil {
+		switch {
+		case len(b) < 2:
+			errs = append(errs, errors.New("any holds at least two branches: one is all"))
+		case len(b) > MaxBranches:
+			errs = append(errs, fmt.Errorf("any holds at most %d branches", MaxBranches))
 		}
-		if seen[names[0]] {
-			errs = append(errs, fmt.Errorf("%s is declared twice", names[0]))
+	}
+	for _, branch := range p.Conditions.Any {
+		if len(branch) == 0 {
+			errs = append(errs, errors.New("a branch of any is empty: it would hold on everything"))
 		}
-		seen[names[0]] = true
-		if l.ModifyOnly != nil && !*l.ModifyOnly {
-			errs = append(errs, errors.New("modifyOnly: false says nothing: leave it out"))
+		seen := map[string]bool{}
+		errs = append(errs, leaves(branch, seen)...)
+		for _, k := range slices.Sorted(maps.Keys(seen)) {
+			if inAll[k] {
+				errs = append(errs, fmt.Errorf("%s is in all and in a branch of any", k))
+			}
 		}
-		patterns = append(patterns, l.AllowedFiles, l.CompanionFiles)
 	}
 	for _, d := range p.Conditions.Deny {
-		patterns = append(patterns, d.ProtectedFiles)
+		if len(d.ProtectedFiles) == 0 {
+			errs = append(errs, errors.New("a deny's protectedFiles is empty: it refuses nothing"))
+		}
 	}
 	for _, a := range p.RequiresApproval {
-		patterns = append(patterns, a.ChangedFiles)
+		if len(a.ChangedFiles) == 0 {
+			errs = append(errs, errors.New("a requiresApproval's changedFiles is empty: it asks about nothing"))
+		}
 	}
-	for _, list := range patterns {
+	for _, list := range p.patterns() {
 		if len(list) > MaxPatterns {
 			errs = append(errs, fmt.Errorf("a list holds at most %d patterns", MaxPatterns))
 		}
 		for _, pat := range list {
-			if len(pat) > MaxPatternBytes {
+			switch {
+			case pat == "":
+				errs = append(errs, errors.New("an empty pattern matches every path"))
+			case len(pat) > MaxPatternBytes:
 				errs = append(errs, fmt.Errorf("a pattern is at most %d bytes", MaxPatternBytes))
 			}
 		}
@@ -231,6 +259,60 @@ func (p ClassPolicy) shape() error {
 	return errors.Join(errs...)
 }

+// patterns are the class's path lists, each compiled when the class is validated.
+func (p ClassPolicy) patterns() [][]string {
+	var out [][]string
+	for _, l := range slices.Concat(append([][]Leaf{p.Conditions.All}, p.Conditions.Any...)...) {
+		out = append(out, l.AllowedFiles, l.CompanionFiles)
+	}
+	for _, d := range p.Conditions.Deny {
+		out = append(out, d.ProtectedFiles)
+	}
+	for _, a := range p.RequiresApproval {
+		out = append(out, a.ChangedFiles)
+	}
+	return out
+}
+
+// leaves checks a conjunction: each leaf sets exactly one key, no key twice, and no leaf is empty,
+// since an empty value reads as absent and would pass as equivalent while checking nothing. The
+// keys go into seen.
+func leaves(ls []Leaf, seen map[string]bool) []error {
+	var errs []error
+	for _, l := range ls {
+		names := l.names()
+		if len(names) != 1 {
+			errs = append(errs, fmt.Errorf("a leaf sets exactly one key, not %v", names))
+			continue
+		}
+		if seen[names[0]] {
+			errs = append(errs, fmt.Errorf("%s is declared twice", names[0]))
+		}
+		seen[names[0]] = true
+		if err := l.empty(names[0]); err != nil {
+			errs = append(errs, err)
+		}
+	}
+	return errs
+}
+
+// empty is the error of a leaf whose one key holds nothing.
+func (l Leaf) empty(key string) error {
+	switch {
+	case l.ModifyOnly != nil && !*l.ModifyOnly:
+		return errors.New("modifyOnly: false says nothing: leave it out")
+	case l.AllowedFiles != nil && len(l.AllowedFiles) == 0, l.HoldoutChecks != nil && len(l.HoldoutChecks) == 0,
+		l.CompanionFiles != nil && len(l.CompanionFiles) == 0:
+		return fmt.Errorf("%s is empty: leave it out", key)
+	case l.MaxPatchFiles != nil && *l.MaxPatchFiles < 1, l.MaxModifiedLines != nil && *l.MaxModifiedLines < 1:
+		return fmt.Errorf("%s is at least 1: leave it out for the guardrail's", key)
+	case l.DiffShape != nil && *l.DiffShape == "", l.ReleaseAgeCheck != nil && *l.ReleaseAgeCheck == "",
+		l.RequiredLabel != nil && *l.RequiredLabel == "":
+		return fmt.Errorf("%s is empty: leave it out", key)
+	}
+	return nil
+}
+
 // exactKeys walks a decoded document against t: encoding/json matches keys case-insensitively, so
 // {mode: shadow, Mode: live} would otherwise read as live. At a struct, every key must equal a
 // field's JSON name exactly. Map keys are free-form; other values end the walk.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/mergepolicy/`
Expected: FAIL in `TestResolveRefuses` on its two negative-cap rows, which `Parse` now refuses before `Resolve` sees them. Delete those two rows (Task 2's guard has no negative case), run again: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/mergepolicy
git commit -m "feat(mergepolicy): any branches as class variants, and refuse predicates that check nothing"
```

### Task 2: Variants, the guardrail label, and pinned profiles

**Files:**
- Modify: `internal/factory/mergepolicy/resolve.go`, `internal/factory/mergepolicy/export.go`
- Test: `internal/factory/mergepolicy/resolve_any_test.go`

**Interfaces:**
- Consumes: `Conditions.Any` (Task 1)
- Produces: `Resolved{Class config.Class; Branches []config.Class; Approval []string; Profile config.HarnessProfile}`, `Resolved.Variants() []config.Class`, `OnlyGuardrail(err error) bool`

Plan 1 carried three more: `errors.Is` across a joined error labelled a mixed file `guardrail_mismatch`; `review` is central-only, which `Validate`'s comment now says; and `profileFor` must not pick a profile pinning a template, tier or loop, or an exported class would change how it runs.

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"errors"
	"fmt"
	"slices"
	"strings"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
)

const anyClass = "factory: aws-0\nclasses:\n  docs-broad:\n    mode: live\n    author: agents\n    harness: plain\n" +
	"    conditions:\n      all: [{maxPatchFiles: 3}]\n      any:\n        - [{diffShape: links-only}]\n        - [{allowedFiles: ['^docs/']}, {maxModifiedLines: 5}]\n" +
	"      deny: [{protectedFiles: ['^docs/specs/']}]\n"

// Each branch of any is a class of its own as the gate reads it: all's leaves, the branch's, the
// deny and the guardrails. The gate decides a variant at a time (the evaluator).
func TestResolveExpandsAnyIntoVariants(t *testing.T) {
	c := central()
	c.MergeGuardrails = config.MergeGuardrails{MandatoryChecks: []string{"Leak scan"}, MaxModifiedLines: 100}
	r := resolved(t, anyClass, c)
	v := r.Variants()
	if len(v) != 2 {
		t.Fatalf("%d variants", len(v))
	}
	for i, cl := range v {
		if cl.MaxPatchFiles != 3 || !slices.Equal(cl.ProtectedFiles, []string{"^docs/specs/"}) || !slices.Contains(cl.HoldoutChecks, "Leak scan") || !cl.Live {
			t.Fatalf("variant %d lost all, deny or a guardrail: %+v", i, cl)
		}
	}
	switch {
	case v[0].DiffShape != "links-only" || v[0].AllowedFiles != nil || v[0].MaxModifiedLines != 100:
		t.Fatalf("variant 0: %+v", v[0])
	case v[1].DiffShape != "" || !slices.Equal(v[1].AllowedFiles, []string{"^docs/"}) || v[1].MaxModifiedLines != 5:
		t.Fatalf("variant 1: %+v", v[1])
	}
	if got := resolved(t, example, central()).Variants(); len(got) != 1 {
		t.Fatalf("a class without any is one variant: %d", len(got))
	}
}

// A branch's cap is held to the guardrail like all's.
func TestABranchCapOverTheGuardrailIsRefused(t *testing.T) {
	c := central()
	c.MergeGuardrails.MaxModifiedLines = 4
	f, err := Parse([]byte(anyClass))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Resolve("docs-broad", f.Classes["docs-broad"], c); !errors.Is(err, ErrGuardrail) || !strings.Contains(err.Error(), "maxModifiedLines 5") {
		t.Fatalf("got %v", err)
	}
}

// Compare has no central form for any: a class using it diverges, as requiresApproval does.
func TestCompareNamesAny(t *testing.T) {
	rc := &config.Repository{Classes: map[string]config.Class{"docs-broad": {Live: true, MaxPatchFiles: 3}}}
	f, err := Parse([]byte(anyClass))
	if err != nil {
		t.Fatal(err)
	}
	if d := Compare(rc, f, central()); !slices.ContainsFunc(d, func(s string) bool { return strings.Contains(s, "any has no central form") }) {
		t.Fatalf("%v", d)
	}
}

// A file both invalid and over a guardrail is invalid: guardrail_mismatch names a file whose every
// fault is the central config's (plan 1, carried to plan 2).
func TestOnlyGuardrail(t *testing.T) {
	g := fmt.Errorf("class a: %w: harness", ErrGuardrail)
	for name, tc := range map[string]struct {
		err  error
		want bool
	}{
		"nil":                {nil, false},
		"a guardrail":        {g, true},
		"two guardrails":     {errors.Join(g, fmt.Errorf("class b: %w: cap", ErrGuardrail)), true},
		"mixed":              {errors.Join(g, errors.New("class b: must start with ^")), false},
		"nested mixed":       {errors.Join(errors.Join(g), errors.Join(errors.New("x"))), false},
		"wrapped guardrails": {fmt.Errorf("mergepolicy: %w", errors.Join(g, g)), true},
		"invalid":            {errors.New("not YAML"), false},
	} {
		t.Run(name, func(t *testing.T) {
			if got := OnlyGuardrail(tc.err); got != tc.want {
				t.Fatalf("got %t", got)
			}
		})
	}
}

// Export picks a profile that runs the class as today: one pinning a tier, a loop or a template
// would change how it runs (plan 1, carried to plan 2).
func TestExportSkipsAPinnedProfile(t *testing.T) {
	c := &config.Config{Factory: "aws-0", HarnessProfiles: map[string]config.HarnessProfile{
		"a-pinned": {Tier: "light"}, "b-looped": {Loop: config.LoopOff}, "c-solo": {Template: "solo"}, "z-plain": {},
	}}
	rc := &config.Repository{Classes: map[string]config.Class{"docs-links": {Live: true}}}
	f, err := Export(rc, c)
	if err != nil {
		t.Fatal(err)
	}
	if h := f.Classes["docs-links"].Harness; h != "z-plain" {
		t.Fatalf("got %q", h)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go vet ./internal/factory/mergepolicy/`
Expected: `r.Variants undefined`.

- [ ] **Step 3: Implement**

```diff
@@ -17,14 +17,26 @@ var ErrGuardrail = errors.New("guardrail")

 // Resolved is a class as the gate would read it, with what the gate does not read yet.
 type Resolved struct {
-	Class    config.Class
-	Approval []string // requiresApproval's paths; the gate reads them from stage 5
+	// Class is all's leaves, the deny and the guardrails: the class itself when it has no any.
+	Class config.Class
+	// Branches are Class with each branch of any added, one variant per branch; nil without any.
+	Branches []config.Class
+	Approval []string // requiresApproval's paths
 	Profile  config.HarnessProfile
 }

+// Variants are the classes the evaluator decides on, one at a time: the class holds when one
+// variant does.
+func (r Resolved) Variants() []config.Class {
+	if r.Branches != nil {
+		return r.Branches
+	}
+	return []config.Class{r.Class}
+}
+
 // Resolve turns a parsed class into the config.Class the gate decides on, under the guardrails:
 // they add protected paths and mandatory checks, an undeclared cap inherits theirs, and a declared
-// cap above theirs is refused (MP6).
+// cap above theirs is refused (MP6). Each branch of any is resolved the same way.
 func Resolve(name string, p ClassPolicy, c *config.Config) (Resolved, error) {
 	profile, ok := c.HarnessProfiles[p.Harness]
 	if !ok {
@@ -40,34 +52,68 @@ func Resolve(name string, p ClassPolicy, c *config.Config) (Resolved, error) {
 		cl.Author = &config.Author{Adopt: p.Adopt}
 	}
 	for _, l := range p.Conditions.All {
-		cl.AllowedFiles = append(cl.AllowedFiles, l.AllowedFiles...)
-		cl.HoldoutChecks = append(cl.HoldoutChecks, l.HoldoutChecks...)
-		cl.CompanionFiles = append(cl.CompanionFiles, l.CompanionFiles...)
-		switch {
-		case l.ModifyOnly != nil:
-			cl.ModifyOnly = *l.ModifyOnly
-		case l.MaxPatchFiles != nil:
-			cl.MaxPatchFiles = *l.MaxPatchFiles
-		case l.MaxModifiedLines != nil:
-			cl.MaxModifiedLines = *l.MaxModifiedLines
-		case l.DiffShape != nil:
-			cl.DiffShape = *l.DiffShape
-		case l.ReleaseAgeCheck != nil:
-			cl.ReleaseAgeCheck = *l.ReleaseAgeCheck
-		case l.Oracle != nil:
-			cl.Oracle = l.Oracle
-		case l.RequiredLabel != nil:
-			cl.RequiredLabel = *l.RequiredLabel
-		}
+		apply(&cl, l)
 	}
 	for _, d := range p.Conditions.Deny {
 		cl.ProtectedFiles = append(cl.ProtectedFiles, d.ProtectedFiles...)
 	}
-	var approval []string
+	r := Resolved{Profile: profile}
 	for _, a := range p.RequiresApproval {
-		approval = append(approval, a.ChangedFiles...)
+		r.Approval = append(r.Approval, a.ChangedFiles...)
+	}
+	for _, branch := range p.Conditions.Any {
+		v := clone(cl)
+		for _, l := range branch {
+			apply(&v, l)
+		}
+		r.Branches = append(r.Branches, v)
+	}
+	var errs []error
+	for i := range r.Branches {
+		errs = append(errs, guard(name, &r.Branches[i], c.MergeGuardrails))
+	}
+	errs = append(errs, guard(name, &cl, c.MergeGuardrails))
+	if err := errors.Join(errs...); err != nil {
+		return Resolved{}, err
+	}
+	r.Class = cl
+	return r, nil
+}
+
+// apply adds one leaf to a class.
+func apply(cl *config.Class, l Leaf) {
+	cl.AllowedFiles = append(cl.AllowedFiles, l.AllowedFiles...)
+	cl.HoldoutChecks = append(cl.HoldoutChecks, l.HoldoutChecks...)
+	cl.CompanionFiles = append(cl.CompanionFiles, l.CompanionFiles...)
+	switch {
+	case l.ModifyOnly != nil:
+		cl.ModifyOnly = *l.ModifyOnly
+	case l.MaxPatchFiles != nil:
+		cl.MaxPatchFiles = *l.MaxPatchFiles
+	case l.MaxModifiedLines != nil:
+		cl.MaxModifiedLines = *l.MaxModifiedLines
+	case l.DiffShape != nil:
+		cl.DiffShape = *l.DiffShape
+	case l.ReleaseAgeCheck != nil:
+		cl.ReleaseAgeCheck = *l.ReleaseAgeCheck
+	case l.Oracle != nil:
+		cl.Oracle = l.Oracle
+	case l.RequiredLabel != nil:
+		cl.RequiredLabel = *l.RequiredLabel
 	}
-	g := c.MergeGuardrails
+}
+
+// clone copies a class's lists, so a branch's additions stay its own.
+func clone(cl config.Class) config.Class {
+	cl.AllowedFiles = slices.Clone(cl.AllowedFiles)
+	cl.ProtectedFiles = slices.Clone(cl.ProtectedFiles)
+	cl.HoldoutChecks = slices.Clone(cl.HoldoutChecks)
+	cl.CompanionFiles = slices.Clone(cl.CompanionFiles)
+	return cl
+}
+
+// guard applies the guardrails to one variant. Parse has refused a negative cap.
+func guard(name string, cl *config.Class, g config.MergeGuardrails) error {
 	for _, pf := range g.ProtectedFiles {
 		if !slices.Contains(cl.ProtectedFiles, pf) {
 			cl.ProtectedFiles = append(cl.ProtectedFiles, pf)
@@ -84,21 +130,43 @@ func Resolve(name string, p ClassPolicy, c *config.Config) (Resolved, error) {
 		limit int
 	}{{"maxPatchFiles", &cl.MaxPatchFiles, g.MaxPatchFiles}, {"maxModifiedLines", &cl.MaxModifiedLines, g.MaxModifiedLines}, {"maxPerDay", &cl.MaxPerDay, g.MaxPerDay}} {
 		switch {
-		case *f.value < 0:
-			return Resolved{}, fmt.Errorf("class %s: %w: %s %d is negative", name, ErrGuardrail, f.key, *f.value)
 		case f.limit == 0:
 		case *f.value == 0:
 			*f.value = f.limit
 		case *f.value > f.limit:
-			return Resolved{}, fmt.Errorf("class %s: %w: %s %d is over the guardrail's %d", name, ErrGuardrail, f.key, *f.value, f.limit)
+			return fmt.Errorf("class %s: %w: %s %d is over the guardrail's %d", name, ErrGuardrail, f.key, *f.value, f.limit)
+		}
+	}
+	return nil
+}
+
+// OnlyGuardrail is true when every fault err joins is ErrGuardrail's: a file that is also invalid
+// is invalid, whatever errors.Is finds somewhere in the join.
+func OnlyGuardrail(err error) bool {
+	if err == nil {
+		return false
+	}
+	switch e := err.(type) { //nolint:errorlint // walking the tree is the point: errors.Is answers "any", this is "all"
+	case interface{ Unwrap() []error }:
+		for _, c := range e.Unwrap() {
+			if !OnlyGuardrail(c) {
+				return false
+			}
+		}
+		return true
+	case interface{ Unwrap() error }:
+		if e.Unwrap() == ErrGuardrail { //nolint:errorlint // the sentinel itself, one level down
+			return true
 		}
+		return OnlyGuardrail(e.Unwrap())
 	}
-	return Resolved{Class: cl, Approval: approval, Profile: profile}, nil
+	return false
 }

 // Validate is the whole file against the central config: a file with no classes has no policy and
 // passes; one with classes declares docs-links and revert, never review, and each class passes
-// Resolve and the gate's own class check.
+// Resolve and the gate's own class check, every variant of it. review stays central: its settings
+// are the repository's merge block (approveToMerge, maintainers), which no class file holds.
 func Validate(f *File, c *config.Config) error {
 	if f.Classes == nil {
 		return nil
@@ -118,7 +186,9 @@ func Validate(f *File, c *config.Config) error {
 			errs = append(errs, err)
 			continue
 		}
-		config.ValidateClass(name, r.Class, func(format string, a ...any) { errs = append(errs, fmt.Errorf(format, a...)) })
+		for _, v := range r.Variants() {
+			config.ValidateClass(name, v, func(format string, a ...any) { errs = append(errs, fmt.Errorf(format, a...)) })
+		}
 	}
 	return errors.Join(errs...)
 }
```

```diff
@@ -86,10 +86,14 @@ func exportClass(cl config.Class, c *config.Config) (ClassPolicy, error) {
 	return p, nil
 }

-// profileFor is the first profile by name that runs the class as it runs today.
+// profileFor is the first profile by name that runs the class as it runs today: one pinning a
+// template, a tier or a loop would change how it runs, so it is never picked.
 func profileFor(cl config.Class, c *config.Config) (string, bool) {
 	for _, name := range slices.Sorted(maps.Keys(c.HarnessProfiles)) {
 		p := c.HarnessProfiles[name]
+		if p.Tier != "" || p.Loop != "" || (p.Template != "" && p.Template != config.TemplateNone) {
+			continue
+		}
 		if (p.Template == config.TemplateNone) == cl.Adopted() && p.Checks == cl.Checks && p.TestFirst == cl.TestFirst {
 			return name, true
 		}
@@ -126,6 +130,9 @@ func Compare(rc *config.Repository, f *File, c *config.Config) []string {
 				out = append(out, fmt.Sprintf("%s: %v", name, err))
 				continue
 			}
+			if r.Branches != nil {
+				out = append(out, name+": any has no central form")
+			}
 			if len(r.Approval) > 0 {
 				out = append(out, name+": requiresApproval has no central form")
 			}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/mergepolicy/`
Expected: PASS

- [ ] **Step 5: Commit** (with Task 1's when done in one sitting, as Maku#381 did)

```bash
git add internal/factory/mergepolicy
git commit -m "feat(mergepolicy): resolve any into variants, label only an all-guardrail file guardrail_mismatch"
```

### Task 3: Evaluate a fence file once per hash

**Files:**
- Modify: `internal/factory/mergepolicy/watch.go`
- Test: `internal/factory/mergepolicy/watch_cache_test.go`

**Interfaces:**
- Consumes: `Resolve`, `OnlyGuardrail` (Task 2)
- Produces: `Snapshot{Hash string; HasClasses bool; Err error; Divergences []string; Classes map[string]Resolved; Read time.Time}`; `Watch.Now func() time.Time`

The config is the process's (a change rolls the pod by checksum), so a file with the last read's hash has the last read's result. Metrics are still recorded on every read: the load-error counter's rate must keep showing a bad file.

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"strings"
	"testing"
	"time"
)

// The fence reads every five minutes and the file rarely moves: an unchanged file is not parsed
// or compiled again, and its metrics are recorded as if it were, so a rate still shows a bad file.
func TestObserveSkipsAnUnchangedFile(t *testing.T) {
	w, r := watchRig()
	bad := "factory: aws-0\nclasses: [no]\n"
	for range 3 {
		w.Observe(t.Context(), "o/r", []byte(same))
		w.Observe(t.Context(), "o/q", []byte(same)) // unlisted: never evaluated
	}
	w.Observe(t.Context(), "o/r", []byte(bad))
	w.Observe(t.Context(), "o/r", []byte(bad))
	if w.evaluations != 2 {
		t.Fatalf("%d evaluations, want one per distinct file", w.evaluations)
	}
	if len(r.gauge) != 3 || len(r.reasons) != 2 {
		t.Fatalf("every read records: gauge %v reasons %v", r.gauge, r.reasons)
	}
}

// The snapshot holds the resolved classes the evaluator reads, and when the file was read.
func TestTheSnapshotHoldsTheResolvedClasses(t *testing.T) {
	w, _ := watchRig()
	at := time.Date(2026, 11, 7, 12, 0, 0, 0, time.UTC)
	w.Now = func() time.Time { return at }
	w.Observe(t.Context(), "O/R", []byte(same))
	s, ok := w.Snapshot("o/r")
	if !ok || len(s.Classes) != 2 || !s.Classes["docs-links"].Class.Live || !s.Read.Equal(at) {
		t.Fatalf("%+v", s)
	}
	w.Observe(t.Context(), "o/r", []byte("factory: aws-0\nclasses: [no]\n"))
	if s, _ := w.Snapshot("o/r"); s.Classes != nil || s.Err == nil {
		t.Fatalf("an invalid file resolves nothing: %+v", s)
	}
}

// A file mixing a guardrail fault with an invalid class is invalid.
func TestAMixedFileIsInvalid(t *testing.T) {
	w, r := watchRig()
	mixed := "factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: nope}\n  revert: {mode: live, author: agents, harness: plain}\n" +
		"  bad:\n    mode: shadow\n    author: agents\n    harness: plain\n    conditions: {all: [{allowedFiles: ['docs/.+']}]}\n"
	w.Observe(t.Context(), "o/r", []byte(mixed))
	if strings.Join(r.reasons, ",") != ReasonInvalid {
		t.Fatalf("%v", r.reasons)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go vet ./internal/factory/mergepolicy/`
Expected: `w.evaluations undefined`.

- [ ] **Step 3: Implement**

```diff
@@ -6,11 +6,10 @@ import (
 	"context"
 	"crypto/sha256"
 	"encoding/hex"
-	"errors"
 	"log/slog"
-	"slices"
 	"strings"
 	"sync"
+	"time"

 	"github.com/Smana/maku/internal/factory/config"
 )
@@ -28,64 +27,104 @@ type Recorder interface {
 	PolicyDivergence(ctx context.Context, repository string, n int)
 }

-// Snapshot is the last file read for a repository, and what it came to.
+// Snapshot is the last file read for a repository, and what it came to: what a decision binds to
+// (MP12). Classes holds the resolved classes of a valid file, nil otherwise.
 type Snapshot struct {
 	Hash        string
 	HasClasses  bool
 	Err         error
 	Divergences []string
+	Classes     map[string]Resolved
+	Read        time.Time
 }

-// Watch observes each owned repository's file as the fence reads it. It decides nothing: stage 1
-// compares, and the gate keeps reading the central config.
+// Watch observes each owned repository's file as the fence reads it. It decides nothing: the gate
+// keeps reading the central config, and dual evaluation reads Snapshot beside it.
 type Watch struct {
 	Cfg     *config.Config
 	Metrics Recorder
 	Log     *slog.Logger
+	Now     func() time.Time

-	mu    sync.RWMutex
-	state map[string]Snapshot
+	mu          sync.RWMutex
+	state       map[string]Snapshot
+	evaluations int // files parsed and validated, for the cache's test
 }

 // Observe reads one file. A file with no classes has no policy and records no divergence, and a
 // failed read records none either: the gauge keeps the last comparison's value, and a repository
 // never compared has no series, so 0 is never "nothing to compare". It logs only when the file or
 // its result changes: the fence reads every five minutes. The load-error counter counts every
-// failed read, so a rate shows it is still bad.
+// failed read, so a rate shows it is still bad. A file whose hash is the last read's is not
+// evaluated again: the config is the process's, so the result cannot have moved.
 func (w *Watch) Observe(ctx context.Context, repository string, body []byte) {
 	rc := w.listed(repository)
 	if rc == nil {
 		return
 	}
 	sum := sha256.Sum256(body)
-	s := Snapshot{Hash: hex.EncodeToString(sum[:])}
-	f, err := Parse(body)
-	if err == nil {
-		s.HasClasses = f.Classes != nil
-		err = Validate(f, w.Cfg)
+	hash := hex.EncodeToString(sum[:])
+	key := strings.ToLower(repository)
+	w.mu.RLock()
+	prev, seen := w.state[key]
+	w.mu.RUnlock()
+	s := prev
+	if !seen || prev.Hash != hash {
+		s = w.evaluate(rc, hash, body)
 	}
+	s.Read = w.now()
 	switch {
-	case errors.Is(err, ErrGuardrail):
+	case s.Err != nil && OnlyGuardrail(s.Err):
 		w.Metrics.PolicyLoadError(ctx, repository, ReasonGuardrail)
-	case err != nil:
+	case s.Err != nil:
 		w.Metrics.PolicyLoadError(ctx, repository, ReasonInvalid)
 	case s.HasClasses:
-		s.Divergences = Compare(rc, f, w.Cfg)
 		w.Metrics.PolicyDivergence(ctx, repository, len(s.Divergences))
 	}
-	s.Err = err
 	w.mu.Lock()
 	if w.state == nil {
 		w.state = map[string]Snapshot{}
 	}
-	key := strings.ToLower(repository)
-	prev, seen := w.state[key]
 	w.state[key] = s
 	w.mu.Unlock()
-	if !seen || prev.Hash != s.Hash || !slices.Equal(prev.Divergences, s.Divergences) {
+	if !seen || prev.Hash != s.Hash {
 		w.log().Info("repository merge policy read", "repository", repository, "hash", s.Hash,
-			"classes", s.HasClasses, "err", err, "divergences", s.Divergences)
+			"classes", s.HasClasses, "err", s.Err, "divergences", s.Divergences)
+	}
+}
+
+// evaluate parses, validates, resolves and compares one file.
+func (w *Watch) evaluate(rc *config.Repository, hash string, body []byte) Snapshot {
+	w.mu.Lock()
+	w.evaluations++
+	w.mu.Unlock()
+	s := Snapshot{Hash: hash}
+	f, err := Parse(body)
+	if err == nil {
+		s.HasClasses = f.Classes != nil
+		err = Validate(f, w.Cfg)
+	}
+	s.Err = err
+	if err != nil || !s.HasClasses {
+		return s
+	}
+	s.Divergences = Compare(rc, f, w.Cfg)
+	s.Classes = map[string]Resolved{}
+	for name, p := range f.Classes {
+		r, rerr := Resolve(name, p, w.Cfg)
+		if rerr != nil { // Validate resolved it: unreachable, and never half a snapshot
+			return Snapshot{Hash: hash, HasClasses: true, Err: rerr}
+		}
+		s.Classes[name] = r
+	}
+	return s
+}
+
+func (w *Watch) now() time.Time {
+	if w.Now == nil {
+		return time.Now()
 	}
+	return w.Now()
 }

 // Snapshot is the last read of repository.
```

In `internal/app/factory.go`, pass `Now: time.Now` where the `Watch` is built (the stage 3 plan rewrites that block).

- [ ] **Step 4: Run the tests to verify they pass, and measure**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/factory/mergepolicy/`
Expected: PASS. A throwaway probe (four classes of 64 patterns, each a 480-byte RE2 with 48 bounded repeats, plus the required two) measured 46 ms on the first read and 95 µs on the next; record your figures in the PR, then delete the probe.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/mergepolicy
git commit -m "fix(mergepolicy): evaluate a fence file once per hash, bound its patterns, and keep its resolved classes"
```

### Task 4: The switches

**Files:**
- Modify: `internal/factory/config/mergepolicy.go`
- Test: `internal/factory/config/mergepolicy_test.go`

**Interfaces:**
- Produces: `PolicyManagement{Read, Simulation, DualEvaluation bool}` (`dualEvaluation` is the stage 3 plan's; both land here so one release carries the schema)

- [ ] **Step 1: Write the failing test.** Add to `TestHarnessProfilesAndGuardrailsValidate`'s table:

```go
"simulation alone": {Config{PolicyManagement: PolicyManagement{Simulation: true}}, ""},
"dual with read":   {Config{PolicyManagement: PolicyManagement{Read: true, DualEvaluation: true}}, ""},
"dual alone":       {Config{PolicyManagement: PolicyManagement{DualEvaluation: true}}, "dualEvaluation needs read"},
```

- [ ] **Step 2: Run it to verify it fails**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run TestHarnessProfilesAndGuardrailsValidate ./internal/factory/config/`
Expected: FAIL to build: unknown fields `Simulation`, `DualEvaluation`.

- [ ] **Step 3: Implement**

```diff
@@ -59,6 +59,13 @@ type PolicyManagement struct {
 	// Read observes each owned repository's class policy and compares it with this config. It
 	// decides nothing.
 	Read bool `json:"read,omitempty"`
+	// Simulation lets `maku policy simulate` and `maku policy diff` run against this config: the
+	// switch a simulator that disagrees with the gate turns off (stage 2). Offline, decides nothing.
+	Simulation bool `json:"simulation,omitempty"`
+	// DualEvaluation decides every merge decision a second time under the repository's policy, as
+	// Read last observed it, and records whether the two agree (stage 3). It decides nothing: the
+	// central decision is the one acted on. Needs Read.
+	DualEvaluation bool `json:"dualEvaluation,omitempty"`
 }

 var profileRE = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$`)
@@ -85,6 +92,9 @@ func (c *Config) validateMergePolicy(bad func(string, ...any)) {
 			bad("harnessProfiles.%s: template none runs nothing, so it takes no other key", name)
 		}
 	}
+	if pm := c.PolicyManagement; pm.DualEvaluation && !pm.Read {
+		bad("policyManagement.dualEvaluation needs read: it evaluates the policy read observes")
+	}
 	g := c.MergeGuardrails
 	for _, f := range []struct {
 		key string
```

Add both rows to `docs/factory.md`'s config table, under `policyManagement.read`.

- [ ] **Step 4: Run it to verify it passes**, same command: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/config docs/factory.md
git commit -m "feat(config): policyManagement.simulation and dualEvaluation, both off"
```

### Task 5: One evaluator

**Files:**
- Modify: `internal/factory/reconciler/arm.go` (`DecideArm`, `gateOf`)
- Create: `internal/factory/reconciler/evaluate.go`
- Test: `internal/factory/reconciler/evaluate_test.go`

**Interfaces:**
- Consumes: `Resolved.Variants()` and `Resolved.Approval` (Task 2), by the caller
- Produces: `DecideArmUnder(in ArmInputs, variants []config.Class, approval []string) ArmDecision`; `decide(in ArmInputs, rc *config.Repository, cl config.Class) ArmDecision`; `withShape(cl config.Class, class string) config.Class`; the reasons `approval_required` and `shadow_would_require_approval`

`DecideArm` read its class through `gateOf` in two places. Both now read the `cl` argument, so a class from any source goes through the one rule: the fixed base, the author mode, the declared conditions, the caps.

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"reflect"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/forge"
)

// MP16: the evaluator is DecideArm's own rule with the class handed in, so under the central
// class it is DecideArm, decision and record alike, on every input.
func TestDecideArmUnderTheCentralClassIsDecideArm(t *testing.T) {
	for name, mutate := range map[string]func(*ArmInputs){
		"arms":             func(*ArmInputs) {},
		"a protected file": func(in *ArmInputs) { in.Stats[0].Path = "docs/specs/x.md" },
		"21 lines":         func(in *ArmInputs) { in.Stats[0].Additions = 20 },
		"the holdout runs": func(in *ArmInputs) { in.Checks.Runs[2].State = "PENDING" },
		"diff unread":      func(in *ArmInputs) { in.DiffRead, in.Stats = false, nil },
		"not the agent":    func(in *ArmInputs) { in.PR.Author = "someone" },
		"ci red":           func(in *ArmInputs) { in.Checks.Runs[0].State = "FAILURE" },
		"capped":           func(in *ArmInputs) { in.ClassArmedToday = 1 },
		"shadow": func(in *ArmInputs) {
			cl := declaredClass()
			cl.Live, cl.Shadow = false, true
			in.Cfg.Classes["dead-links"] = cl
		},
	} {
		t.Run(name, func(t *testing.T) {
			in := gateInputs()
			mutate(&in)
			cl := gateOf(in.Cfg.RepositoryFor(""), "dead-links")
			if got, want := DecideArmUnder(in, []config.Class{cl}, nil), DecideArm(in); !reflect.DeepEqual(got, want) {
				t.Fatalf("got %+v, want %+v", got, want)
			}
		})
	}
}

// any: the class holds when one variant does; a wait outranks a refusal; with none holding, the
// first variant's refusal is the decision's.
func TestDecideArmUnderAny(t *testing.T) {
	strict := declaredClass()
	strict.MaxModifiedLines = 1 // the rig's retarget is two lines
	waits := declaredClass()
	waits.HoldoutChecks = []string{"Never reported"}
	for name, tc := range map[string]struct {
		variants        []config.Class
		verdict, reason string
	}{
		"the second holds":      {[]config.Class{strict, declaredClass()}, "arm", ""},
		"none holds":            {[]config.Class{strict, strict}, "human", "patch_too_large"},
		"a wait over a refusal": {[]config.Class{strict, waits}, "wait", "holdout_pending"},
		"a hold over a wait":    {[]config.Class{waits, declaredClass()}, "arm", ""},
		"no variant: no class":  {nil, "human", "class_unarmed"},
	} {
		t.Run(name, func(t *testing.T) {
			d := DecideArmUnder(gateInputs(), tc.variants, nil)
			if d.Verdict != tc.verdict || d.Reason != tc.reason {
				t.Fatalf("got %s:%s", d.Verdict, d.Reason)
			}
		})
	}
}

// requiresApproval (owner's Q3): a live class asks a human about a pull request in its subset; a
// shadow class records would-require-approval and sends nobody. The subset reads the diff, so it
// holds until the diff is read, as every condition on it does.
func TestDecideArmUnderAnApprovalSubset(t *testing.T) {
	shadow := declaredClass()
	shadow.Live, shadow.Shadow = false, true
	for name, tc := range map[string]struct {
		cl              config.Class
		approval        []string
		mutate          func(*ArmInputs)
		verdict, reason string
	}{
		"live, in the subset":     {declaredClass(), []string{"^website/"}, func(*ArmInputs) {}, "human", "approval_required"},
		"shadow, in the subset":   {shadow, []string{"^website/"}, func(*ArmInputs) {}, "shadow", "shadow_would_require_approval"},
		"live, outside it":        {declaredClass(), []string{"^website/content/security/"}, func(*ArmInputs) {}, "arm", ""},
		"the diff unread":         {declaredClass(), []string{"^website/"}, func(in *ArmInputs) { in.DiffRead, in.Stats = false, nil }, "arm", ""},
		"a refusal stays refused": {declaredClass(), []string{"^website/"}, func(in *ArmInputs) { in.Stats[0].Additions = 20 }, "human", "patch_too_large"},
	} {
		t.Run(name, func(t *testing.T) {
			in := gateInputs()
			tc.mutate(&in)
			d := DecideArmUnder(in, []config.Class{tc.cl}, tc.approval)
			if d.Verdict != tc.verdict || d.Reason != tc.reason {
				t.Fatalf("got %s:%s", d.Verdict, d.Reason)
			}
		})
	}
}

// A rename from a path in the subset is in the subset: the path it leaves is changed too.
func TestTheApprovalSubsetReadsTheRenamedFromPath(t *testing.T) {
	in := gateInputs()
	cl := declaredClass()
	cl.ModifyOnly = false
	in.Stats = []forge.FileStat{{Path: "docs/a.md", Previous: "docs/security/a.md", Status: "renamed"}}
	if d := DecideArmUnder(in, []config.Class{cl}, []string{"^docs/security/"}); d.Reason != "approval_required" {
		t.Fatalf("got %s:%s", d.Verdict, d.Reason)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run 'DecideArmUnder|ApprovalSubset' ./internal/factory/reconciler/`
Expected: FAIL to build: `undefined: DecideArmUnder`.

- [ ] **Step 3: Implement**

```diff
@@ -27,7 +27,7 @@ type ArmInputs struct {
 	PR           forge.PR
 	Checks       forge.Checks
 	Task         *v1alpha1.Task
-	Cfg          *config.Config
+	Cfg          *config.Config `json:"-"` // a fixture is decided under the config it is run with
 	ArmedToday   int
 	Paused       bool
 	ReportedHead string
@@ -114,9 +114,15 @@ func CIState(c forge.Checks, required []string) string {
 // DecideArm is §5.1's merge-actor rule: a fixed base no class can remove, one author mode, and
 // the conditions the class declares (merge gate classes MC1). Every "no" fails towards a human
 // (property 3), each with its own reason. Every decision carries the rows it read (AM8).
-func DecideArm(in ArmInputs) (d ArmDecision) {
+func DecideArm(in ArmInputs) ArmDecision {
 	rc := in.Cfg.RepositoryFor(in.Task.Spec.Repository)
-	rows := recordOf(in, gateOf(rc, in.Task.Spec.PredictedClass))
+	return decide(in, rc, gateOf(rc, in.Task.Spec.PredictedClass))
+}
+
+// decide is DecideArm's rule on the class cl, wherever it was read: the central config, or a
+// repository's policy (DecideArmUnder). Everything else is read from the central config.
+func decide(in ArmInputs, rc *config.Repository, cl config.Class) (d ArmDecision) {
+	rows := recordOf(in, cl)
 	defer func() { d.Rows = rows }()
 	if d, done := baseChecks(in, rc); done {
 		return d
@@ -125,7 +131,6 @@ func DecideArm(in ArmInputs) (d ArmDecision) {
 		return ArmDecision{Verdict: "human", Reason: reason, Matched: matched}
 	}
 	class := in.Task.Spec.PredictedClass
-	cl := gateOf(rc, class)
 	if cl.Adopted() {
 		if reason := adoptAuthor(in, cl); reason != "" {
 			return human(reason, class)
@@ -394,7 +399,11 @@ func runsEnded(t *v1alpha1.Task) time.Time {
 // gateOf is the class as the gate reads it: its config, with the diff shape built into
 // docs-links and revert (R52) when the config names none.
 func gateOf(rc *config.Repository, class string) config.Class {
-	cl := rc.Classes[class]
+	return withShape(rc.Classes[class], class)
+}
+
+// withShape is cl with the built-in diff shape of its name when it declares none.
+func withShape(cl config.Class, class string) config.Class {
 	if cl.DiffShape == "" {
 		cl.DiffShape = config.BuiltInShape(class)
 	}
```

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/filefence"
)

// DecideArmUnder is DecideArm with the task's class read from a repository's policy rather than
// the central config (merge policy MP16): one evaluator, so a simulation or a dual evaluation
// cannot disagree with the gate on the same inputs. variants are the class's resolved branches of
// any (one without any; none when the policy lacks the class, which arms nothing), each decided
// as DecideArm decides a class. The class holds when one variant does: an arm outranks a shadow,
// a shadow a wait, a wait any refusal, and with none holding the first variant's refusal stands.
// approval is the class's requiresApproval subset: a class decision touching it asks a human in a
// live class and is recorded as would-require-approval in a shadow one (the owner's Q3). Through
// stage 3 nothing merges on this decision.
func DecideArmUnder(in ArmInputs, variants []config.Class, approval []string) ArmDecision {
	rc := in.Cfg.RepositoryFor(in.Task.Spec.Repository)
	class := in.Task.Spec.PredictedClass
	if len(variants) == 0 {
		return decide(in, rc, config.Class{})
	}
	var best ArmDecision
	for i, v := range variants {
		d := decide(in, rc, withShape(v, class))
		if i == 0 || rank(d) > rank(best) {
			best = d
		}
	}
	return withApproval(best, in, approval)
}

// rank orders a variant's decisions for any: what holds first, a wait before a refusal.
func rank(d ArmDecision) int {
	switch d.Verdict {
	case "arm":
		return 3
	case "shadow":
		return 2
	case "wait":
		return 1
	}
	return 0
}

// withApproval applies the approval subset to a class decision: an arm or a shadow of the class,
// not a maintainer's approval, which is a human's judgement already (AM1). The subset reads the
// diff and holds until it is read.
func withApproval(d ArmDecision, in ArmInputs, approval []string) ArmDecision {
	classArm := d.Verdict == "arm" && d.Reason == ""
	if len(approval) == 0 || !in.DiffRead || (!classArm && d.Verdict != "shadow") {
		return d
	}
	if filefence.ProtectedFiles(config.Class{ProtectedFiles: approval}, in.Stats) == "" {
		return d
	}
	if d.Verdict == "shadow" {
		d.Reason = reasonShadowApproval
		return d
	}
	return ArmDecision{Verdict: "human", Reason: reasonApprovalRequired, Matched: d.Matched, Rows: d.Rows}
}
```

The `json:"-"` on `Cfg` serves Task 6's fixtures.

- [ ] **Step 4: Run the whole package**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/factory/reconciler/`
Expected: PASS, every existing gate test included: `DecideArm` is unchanged.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/reconciler
git commit -m "feat(reconciler): one evaluator for a class read from a repository policy, with any and the approval subset"
```

### Task 6: Conformance fixtures and `Simulate`

**Files:**
- Create: `internal/factory/reconciler/simulate.go`
- Modify: `internal/factory/reconciler/merge.go` (extract `provenance`)
- Create: `internal/factory/reconciler/testdata/conformance/NN-<name>.json` (16)
- Test: `internal/factory/reconciler/simulate_test.go`

**Interfaces:**
- Consumes: `DecideArmUnder` (Task 5); `mergepolicy.Export`, `Marshal`, `Parse`, `Validate`, `Resolve`
- Produces: `CaseVersion = 1`; `Case{Version int; Name string; Inputs ArmInputs; Pushed string; Want Outcome}`; `Outcome{Verdict, Reason string}`; `ReadCase([]byte) (Case, error)`; `Row{Name, Class string; Central, Repository Outcome; Change string; Conforms bool}`; `Simulate(cfg, policy map[string]mergepolicy.Resolved, cases []Case) []Row`; `Change*` constants

The spec asks for fixtures "including the final push-provenance check". That check ran inline in `awaitingCI`; it is now `provenance`, which the gate and `Simulate` both call.

- [ ] **Step 1: Extract the provenance row** (a refactor, the package's tests are its proof)

```diff
@@ -132,6 +132,7 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		}
 	}
 	d := DecideArm(in)
+	evaluated := d // the evaluator's own decision, before the rows read after it, for dual evaluation
 	// A maintainer's approval arms on a human's judgement of the head, never on its diff: reading it
 	// again could only hand the approved head off for the diff the approval already covered (AM1).
 	approved := d.Verdict == "arm" && d.Reason == "maintainer_approved"
@@ -150,6 +151,7 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		default:
 			in.Files.Base, in.Files.Head, in.Stats, in.DiffRead = diff.Base, diff.Head, diff.Files, true
 			d = DecideArm(in)
+			evaluated = d
 		}
 	}
 	if adopted && d.Reason == "push_unrecorded" && r.pushRecordWait(t, pr) {
@@ -164,13 +166,11 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		if err != nil {
 			return err
 		}
-		switch {
-		case pushed == pushUnrecorded && r.Now().Before(pushDeadline(t)):
+		if pushed == pushUnrecorded && r.Now().Before(pushDeadline(t)) {
 			r.log().Info("the head's push is not recorded yet: waiting", "task.id", t.Name, "head", pr.HeadSHA)
 			return nil
-		case pushed != pushFactory:
-			d = ArmDecision{Verdict: "human", Reason: "human_commit_in_pr", Rows: d.Rows}
 		}
+		d = provenance(d, adopted, pushed)
 	}
 	if d.Verdict == "arm" && closesParent(t, pr.Body) { // a part closes its own issue only: the parent closes with the last part
 		d = ArmDecision{Verdict: "human", Reason: "closes_parent", Rows: d.Rows}
@@ -181,6 +181,7 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 	if d.Verdict != "wait" {
 		class, verdict, reason := t.Spec.PredictedClass, d.Verdict, cmp.Or(d.Reason, "armed")
 		record(ctx, func(ctx context.Context) { r.Metrics.MergeDecision(ctx, class, verdict, reason) })
+		r.dual(ctx, t, in, evaluated, &d)
 		r.log().Info("merge decision", "task.id", t.Name, "head", pr.HeadSHA, "verdict", d.Verdict, "reason", reason, "rows", d.Rows)
 	}
 	switch d.Verdict {
@@ -610,6 +611,16 @@ func (r *Reconciler) factoryCommits(ctx context.Context, t *v1alpha1.Task, head
 // GitHub's activity to record the run's push; past it, an unrecorded head hands off.
 const pushRecordGrace = 2 * time.Minute

+// provenance is the gate's last row on an agents pull request, after the evaluator: every move of
+// its branch the factory App's (#82). An unrecorded push has waited out its deadline before this.
+// Simulation applies it as the gate does, so a fixture's decision includes it (MP16).
+func provenance(d ArmDecision, adopted bool, pushed pushCheck) ArmDecision {
+	if !adopted && (d.Verdict == "arm" || d.Verdict == "shadow") && pushed != pushFactory {
+		return ArmDecision{Verdict: "human", Reason: "human_commit_in_pr", Rows: d.Rows}
+	}
+	return d
+}
+
 // pushCheck is factoryPushed's answer.
 type pushCheck int

```

Only the `provenance` hunk and the `if` that replaced the one-case `switch` belong to this task; the `evaluated` lines are the stage 3 plan's.

- [ ] **Step 2: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// conformanceCfg is the config the fixtures under testdata/conformance were decided under.
func conformanceCfg() *config.Config {
	c := gateInputs().Cfg
	c.Factory = "aws-0"
	c.HarnessProfiles = map[string]config.HarnessProfile{"plain": {}}
	return c
}

func conformanceCases(t *testing.T) []Case {
	t.Helper()
	paths, err := filepath.Glob("testdata/conformance/*.json")
	if err != nil || len(paths) == 0 {
		t.Fatalf("no fixtures: %v", err)
	}
	var out []Case
	for _, p := range paths {
		raw, err := os.ReadFile(p)
		if err != nil {
			t.Fatal(err)
		}
		c, err := ReadCase(raw)
		if err != nil {
			t.Fatalf("%s: %v", p, err)
		}
		out = append(out, c)
	}
	return out
}

// exported is the central config's classes through the migration's round trip: Export, Marshal,
// Parse, Validate and Resolve, as a repository file the factory reads.
func exported(t *testing.T, c *config.Config) map[string]mergepolicy.Resolved {
	t.Helper()
	f, err := mergepolicy.Export(c.RepositoryFor(""), c)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := mergepolicy.Marshal(f)
	if err != nil {
		t.Fatal(err)
	}
	if f, err = mergepolicy.Parse(raw); err != nil {
		t.Fatal(err)
	}
	if err := mergepolicy.Validate(f, c); err != nil {
		t.Fatal(err)
	}
	out := map[string]mergepolicy.Resolved{}
	for name, p := range f.Classes {
		if out[name], err = mergepolicy.Resolve(name, p, c); err != nil {
			t.Fatal(err)
		}
	}
	return out
}

// Stage 2's exit, offline: every fixture still decides as recorded (the runtime has not moved),
// and the central classes exported as a repository policy decide every fixture the same way, the
// final push provenance included (the simulator is the gate).
func TestConformance(t *testing.T) {
	c := conformanceCfg()
	for _, row := range Simulate(c, exported(t, c), conformanceCases(t)) {
		if !row.Conforms {
			t.Errorf("%s: the gate now decides %+v: rewrite the fixture or find the regression", row.Name, row.Central)
		}
		if row.Change != ChangeUnchanged {
			t.Errorf("%s: central %+v, exported %+v", row.Name, row.Central, row.Repository)
		}
	}
}

// A policy that differs shows in the change column.
func TestSimulateNamesTheChange(t *testing.T) {
	c := conformanceCfg()
	policy := exported(t, c)
	loose := policy["dead-links"]
	loose.Class.MaxModifiedLines = 0 // no line cap: 21 lines would merge
	loose.Approval = []string{"^README"}
	policy["dead-links"] = loose
	delete(policy, "docs")
	got := map[string]string{}
	for _, row := range Simulate(c, policy, conformanceCases(t)) {
		got[row.Name] = row.Change
	}
	for name, want := range map[string]string{
		"arms":                   ChangeUnchanged,
		"too-many-lines":         ChangeNewlyMerged,
		"a-file-outside-allowed": ChangeUnchanged, // refused by allowedFiles before the subset
		"docs-unarmed":           ChangeUnchanged, // absent from the policy: still no class
	} {
		if got[name] != want {
			t.Errorf("%s: got %q, want %q", name, got[name], want)
		}
	}
	policy["dead-links"] = mergepolicy.Resolved{Class: loose.Class, Approval: []string{"^website/"}}
	for _, row := range Simulate(c, policy, conformanceCases(t)[:1]) {
		if row.Change != ChangeNewlyApproval {
			t.Errorf("%s: %q", row.Name, row.Change)
		}
	}
	strict := policy["dead-links"]
	strict.Approval, strict.Class.MaxModifiedLines = nil, 1
	policy["dead-links"] = strict
	if row := Simulate(c, policy, conformanceCases(t)[:1])[0]; row.Change != ChangeNewlyBlocked {
		t.Errorf("%s: %q", row.Name, row.Change)
	}
}

func TestReadCaseRefuses(t *testing.T) {
	for name, tc := range map[string]struct{ raw, want string }{
		"not json":       {"{", "case"},
		"a later format": {`{"version": 2, "name": "x"}`, "version 2"},
		"no task":        {`{"version": 1, "name": "x", "pushed": "factory", "inputs": {}}`, "Task"},
		"bad pushed":     {`{"version": 1, "name": "x", "pushed": "who", "inputs": {"Task": {}}}`, "pushed"},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := ReadCase([]byte(tc.raw)); err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v", err)
			}
		})
	}
}
```

- [ ] **Step 3: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run 'Conformance|Simulate|ReadCase' ./internal/factory/reconciler/`
Expected: FAIL to build: `undefined: Simulate`, `Case`, `ReadCase`.

- [ ] **Step 4: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"encoding/json"
	"fmt"

	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// CaseVersion is the conformance fixtures' format. A change to ArmInputs that reads an old fixture
// differently bumps it, and the fixtures are rewritten against the new one.
const CaseVersion = 1

// Case is one decision as a fixture (merge policy MP16): its inputs, what GitHub recorded of the
// head's pushes (the final provenance row), and the decision the central config makes on them.
// The config is the caller's: a fixture holds none.
type Case struct {
	Version int       `json:"version"`
	Name    string    `json:"name"`
	Inputs  ArmInputs `json:"inputs"`
	// Pushed is factory, stranger or unrecorded: factoryPushed's answer on an agents pull request.
	Pushed string  `json:"pushed"`
	Want   Outcome `json:"want"`
}

// Outcome is a decision's verdict and reason.
type Outcome struct {
	Verdict string `json:"verdict"`
	Reason  string `json:"reason,omitempty"`
}

// ReadCase decodes one fixture strictly.
func ReadCase(raw []byte) (Case, error) {
	var c Case
	if err := json.Unmarshal(raw, &c); err != nil {
		return Case{}, fmt.Errorf("case: %w", err)
	}
	if c.Version != CaseVersion {
		return Case{}, fmt.Errorf("case %q: version %d, this build reads %d", c.Name, c.Version, CaseVersion)
	}
	if c.Inputs.Task == nil {
		return Case{}, fmt.Errorf("case %q: inputs.Task is required", c.Name)
	}
	if _, ok := pushes[c.Pushed]; !ok {
		return Case{}, fmt.Errorf("case %q: pushed %q is factory, stranger or unrecorded", c.Name, c.Pushed)
	}
	return c, nil
}

var pushes = map[string]pushCheck{"factory": pushFactory, "stranger": pushStranger, "unrecorded": pushUnrecorded}

// The changes a simulation names, the spec's impact preview.
const (
	ChangeUnchanged        = "unchanged"
	ChangeNewlyMerged      = "newly_auto_merged"
	ChangeNewlyBlocked     = "newly_blocked"
	ChangeNewlyApproval    = "newly_approval_required"
	ChangeOther            = "changed"
	reasonApprovalRequired = "approval_required"
	reasonShadowApproval   = "shadow_would_require_approval"
)

// Row is one case simulated: the central decision, the repository policy's, and the change.
// Conforms is false when the central decision is no longer the fixture's: the runtime moved, and
// the simulation of that case proves nothing until the fixture is rewritten.
type Row struct {
	Name, Class         string
	Central, Repository Outcome
	Change              string
	Conforms            bool
}

// Simulate decides each case twice with the gate's own evaluator, under cfg's central class and
// under policy's, and names the change. It has no side effect: nothing is read from GitHub.
func Simulate(cfg *config.Config, policy map[string]mergepolicy.Resolved, cases []Case) []Row {
	out := make([]Row, 0, len(cases))
	for _, c := range cases {
		in := c.Inputs
		in.Cfg = cfg
		class := in.Task.Spec.PredictedClass
		cl := gateOf(cfg.RepositoryFor(in.Task.Spec.Repository), class)
		pushed := pushes[c.Pushed]
		central := provenance(DecideArm(in), cl.Adopted(), pushed)
		var repo ArmDecision
		if r, ok := policy[class]; ok {
			repo = provenance(DecideArmUnder(in, r.Variants(), r.Approval), r.Class.Adopted(), pushed)
		} else {
			repo = DecideArmUnder(in, nil, nil)
		}
		a, b := outcome(central), outcome(repo)
		out = append(out, Row{Name: c.Name, Class: class, Central: a, Repository: b, Change: change(a, b), Conforms: a == c.Want})
	}
	return out
}

func outcome(d ArmDecision) Outcome { return Outcome{Verdict: d.Verdict, Reason: d.Reason} }

// change names how the repository's decision differs from the central one.
func change(central, repo Outcome) string {
	classArm := func(o Outcome) bool { return o.Verdict == "arm" && o.Reason == "" }
	switch {
	case central == repo:
		return ChangeUnchanged
	case repo.Reason == reasonApprovalRequired || repo.Reason == reasonShadowApproval:
		return ChangeNewlyApproval
	case classArm(repo):
		return ChangeNewlyMerged
	case classArm(central):
		return ChangeNewlyBlocked
	}
	return ChangeOther
}
```

- [ ] **Step 5: Write the fixtures.** Generate them once from `gateInputs()` with a throwaway test, then delete it: each case is a mutation of the rig, `Want` is `provenance(DecideArm(in), false, pushes[pushed])` under `conformanceCfg()`. The sixteen: `arms`, `a-file-outside-allowed`, `a-protected-file`, `an-added-file`, `too-many-lines`, `beyond-link-targets`, `the-holdout-pending`, `the-holdout-red`, `ci-red`, `not-agent-authored`, `the-class-cap`, `paused`, `a-human-push` (`pushed: stranger`), `the-diff-unread`, `head-unreported`, `docs-unarmed`.

```go
cs := Case{Version: CaseVersion, Name: name, Inputs: in, Pushed: pushed, Want: outcome(d)}
b, _ := json.MarshalIndent(cs, "", "  ")
os.WriteFile(fmt.Sprintf("testdata/conformance/%02d-%s.json", i+1, name), append(b, '\n'), 0o600)
```

- [ ] **Step 6: Run the tests to verify they pass, and that they can fail.** Same command: PASS. Then change one fixture's `want.reason` and run `TestConformance` again: it must fail naming that fixture. Restore it.

- [ ] **Step 7: Commit**

```bash
git add internal/factory/reconciler
git commit -m "feat(reconciler): simulate a repository policy on versioned conformance fixtures, push provenance included"
```

### Task 7: The structural diff

**Files:**
- Create: `internal/factory/mergepolicy/structural.go`
- Test: `internal/factory/mergepolicy/structural_test.go`

**Interfaces:**
- Consumes: `Resolve`, `Resolved.Variants()` (Task 2)
- Produces: `Structural(old, next *File, c *config.Config) ([]Change, error)`; `Change{Class, Kind string; Why []string}`; `KindUnchanged`, `KindTightening`, `KindRelaxation`

A new class is a tightening only when bounded by an old one: for every new variant some old variant bounds it on every row. Stage 4 returns a relaxed class to shadow; here it is reported only.

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"strings"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
)

const base = `factory: aws-0
classes:
  docs-broad:
    mode: shadow
    author: agents
    harness: plain
    conditions:
      all:
        - allowedFiles: ['^docs/', '^README\.md$']
        - maxPatchFiles: 10
        - holdoutChecks: [links]
      deny:
        - protectedFiles: ['^docs/specs/']
    requiresApproval:
      - changedFiles: ['^docs/security/']
    limits:
      maxPerDay: 2
    monitor:
      followUpWindow: 168h
`

func structural(t *testing.T, old, next string) Change {
	t.Helper()
	c := central()
	c.HarnessProfiles["other"] = config.HarnessProfile{}
	parse := func(raw string) *File {
		f, err := Parse([]byte(raw))
		if err != nil {
			t.Fatal(err)
		}
		return f
	}
	ch, err := Structural(parse(old), parse(next), c)
	if err != nil {
		t.Fatal(err)
	}
	if len(ch) != 1 {
		t.Fatalf("%+v", ch)
	}
	return ch[0]
}

// MP8: only a change proven to narrow what merges is a tightening; anything else, or anything
// unproven, is a relaxation and returns the class to shadow (from stage 4).
func TestStructural(t *testing.T) {
	r := strings.Replace
	for name, tc := range map[string]struct {
		next, kind, why string
	}{
		"the same":                {base, KindUnchanged, ""},
		"a lower cap":             {r(base, "maxPatchFiles: 10", "maxPatchFiles: 5", 1), KindTightening, ""},
		"a higher cap":            {r(base, "maxPatchFiles: 10", "maxPatchFiles: 11", 1), KindRelaxation, "maxPatchFiles"},
		"a cap removed":           {r(base, "        - maxPatchFiles: 10\n", "", 1), KindRelaxation, "maxPatchFiles"},
		"a cap added":             {r(base, "        - maxPatchFiles: 10\n", "        - maxPatchFiles: 10\n        - maxModifiedLines: 9\n", 1), KindTightening, ""},
		"a path removed":          {r(base, `, '^README\.md$'`, "", 1), KindTightening, ""},
		"a path added":            {r(base, `'^docs/', `, `'^docs/', '^site/', `, 1), KindRelaxation, "allowedFiles"},
		"a path rewritten":        {r(base, `'^docs/'`, `'^docs/a/'`, 1), KindRelaxation, "allowedFiles"},
		"a deny added":            {r(base, `['^docs/specs/']`, `['^docs/specs/', '^docs/adr/']`, 1), KindTightening, ""},
		"a deny removed":          {r(base, "      deny:\n        - protectedFiles: ['^docs/specs/']\n", "", 1), KindRelaxation, "protectedFiles"},
		"an approval narrowed":    {r(base, "    requiresApproval:\n      - changedFiles: ['^docs/security/']\n", "", 1), KindRelaxation, "requiresApproval"},
		"an approval widened":     {r(base, `['^docs/security/']`, `['^docs/security/', '^docs/arch/']`, 1), KindTightening, ""},
		"a holdout removed":       {r(base, "        - holdoutChecks: [links]\n", "", 1), KindRelaxation, "holdoutChecks"},
		"promoted":                {r(base, "mode: shadow", "mode: live", 1), KindRelaxation, "mode"},
		"demoted":                 {r(base, "mode: shadow", "mode: off", 1), KindTightening, ""},
		"another harness":         {r(base, "harness: plain", "harness: other", 1), KindRelaxation, "harness"},
		"the monitor removed":     {r(base, "    monitor:\n      followUpWindow: 168h\n", "", 1), KindRelaxation, "monitor"},
		"the monitor shortened":   {r(base, "168h", "24h", 1), KindRelaxation, "monitor"},
		"a day cap raised":        {r(base, "maxPerDay: 2", "maxPerDay: 3", 1), KindRelaxation, "maxPerDay"},
		"a shape added":           {r(base, "        - holdoutChecks: [links]\n", "        - holdoutChecks: [links]\n        - diffShape: links-only\n", 1), KindTightening, ""},
		"modifyOnly added":        {r(base, "        - holdoutChecks: [links]\n", "        - holdoutChecks: [links]\n        - modifyOnly: true\n", 1), KindTightening, ""},
		"split into two branches": {r(base, "      deny:\n", "      any:\n        - [{maxModifiedLines: 5}]\n        - [{modifyOnly: true}]\n      deny:\n", 1), KindTightening, ""},
	} {
		t.Run(name, func(t *testing.T) {
			ch := structural(t, base, tc.next)
			if ch.Kind != tc.kind || !strings.Contains(strings.Join(ch.Why, ";"), tc.why) {
				t.Fatalf("got %s %v, want %s naming %q", ch.Kind, ch.Why, tc.kind, tc.why)
			}
		})
	}
}

// A branch that no old variant bounds is a relaxation, even when the others tighten.
func TestABroadeningBranchRelaxes(t *testing.T) {
	two := strings.Replace(strings.Replace(base, "        - maxPatchFiles: 10\n", "", 1), "      deny:\n", "      any:\n        - [{maxPatchFiles: 3}]\n        - [{maxPatchFiles: 5}]\n      deny:\n", 1)
	if ch := structural(t, two, strings.Replace(two, "maxPatchFiles: 5", "maxPatchFiles: 6", 1)); ch.Kind != KindRelaxation {
		t.Fatalf("%+v", ch)
	}
	if ch := structural(t, two, strings.Replace(two, "maxPatchFiles: 5", "maxPatchFiles: 2", 1)); ch.Kind != KindTightening {
		t.Fatalf("%+v", ch)
	}
}

// A class added is new authority; one removed merges nothing more.
func TestAddedAndRemovedClasses(t *testing.T) {
	c := central()
	old, _ := Parse([]byte(base))
	added, _ := Parse([]byte(base + "  more: {mode: shadow, author: agents, harness: plain}\n  idle: {mode: off, author: agents, harness: plain}\n"))
	ch, err := Structural(old, added, c)
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]string{}
	for _, x := range ch {
		got[x.Class] = x.Kind
	}
	if got["more"] != KindRelaxation || got["idle"] != KindTightening || got["docs-broad"] != KindUnchanged {
		t.Fatalf("%+v", ch)
	}
	ch, err = Structural(added, old, c)
	if err != nil || len(ch) != 3 || ch[1].Kind != KindTightening || ch[1].Class != "idle" || ch[2].Kind != KindTightening {
		t.Fatalf("%+v %v", ch, err)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/mergepolicy/`
Expected: FAIL to build: `undefined: Structural`.

- [ ] **Step 3: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"slices"

	"github.com/Smana/maku/internal/factory/config"
)

// The structural verdicts (MP8).
const (
	KindUnchanged  = "unchanged"
	KindTightening = "tightening"
	KindRelaxation = "relaxation"
)

// Change is one class's structural verdict from one policy to the next, and why it is not a
// tightening.
type Change struct {
	Class string
	Kind  string
	Why   []string
}

// Structural compares two valid policies class by class (MP8). A change is a tightening only when
// every variant of the new class is bounded by a variant of the old one on every row: fewer
// allowed paths, more denied ones, a wider approval subset, lower caps, more evidence, a lower
// mode. Anything else, or anything it cannot prove, such as a rewritten pattern or another
// harness profile, is a relaxation. Simulation illustrates the impact; only this proves it.
func Structural(old, next *File, c *config.Config) ([]Change, error) {
	names := map[string]bool{}
	for n := range old.Classes {
		names[n] = true
	}
	for n := range next.Classes {
		names[n] = true
	}
	var out []Change
	var errs []error
	for _, name := range slices.Sorted(maps.Keys(names)) {
		o, inOld := old.Classes[name]
		n, inNext := next.Classes[name]
		switch {
		case !inNext:
			out = append(out, Change{Class: name, Kind: KindTightening})
			continue
		case !inOld && n.Mode == ModeOff:
			out = append(out, Change{Class: name, Kind: KindTightening})
			continue
		case !inOld:
			out = append(out, Change{Class: name, Kind: KindRelaxation, Why: []string{"the class is new"}})
			continue
		}
		ro, err := Resolve(name, o, c)
		if err != nil {
			errs = append(errs, err)
			continue
		}
		rn, err := Resolve(name, n, c)
		if err != nil {
			errs = append(errs, err)
			continue
		}
		out = append(out, classChange(name, o, n, ro, rn))
	}
	return out, errors.Join(errs...)
}

func classChange(name string, o, n ClassPolicy, ro, rn Resolved) Change {
	if jsonOf(o) == jsonOf(n) { // as written, every list in order
		return Change{Class: name, Kind: KindUnchanged}
	}
	var why []string
	if o.Harness != n.Harness {
		why = append(why, fmt.Sprintf("harness %s to %s: not proven evidence-neutral", o.Harness, n.Harness))
	}
	if !superset(rn.Approval, ro.Approval) {
		why = append(why, "requiresApproval narrowed")
	}
	for i, v := range rn.Variants() {
		best := []string(nil)
		for j, ov := range ro.Variants() {
			w := looser(v, ov)
			if len(w) == 0 {
				best = nil
				break
			}
			if j == 0 {
				best = w
			}
		}
		for _, w := range best {
			if len(rn.Variants()) > 1 {
				w = fmt.Sprintf("branch %d: %s", i+1, w)
			}
			why = append(why, w)
		}
	}
	if len(why) > 0 {
		return Change{Class: name, Kind: KindRelaxation, Why: why}
	}
	return Change{Class: name, Kind: KindTightening}
}

func jsonOf(v any) string {
	b, err := json.Marshal(v)
	if err != nil { // the policy types hold strings, ints, bools and Durations
		return err.Error()
	}
	return string(b)
}

// looser is why n is not bounded by o, row by row: nil when it is.
func looser(n, o config.Class) []string {
	var why []string
	add := func(ok bool, row string) {
		if !ok {
			why = append(why, row)
		}
	}
	add(modeRank(n) <= modeRank(o), "mode raised")
	add(jsonOf(n.Author) == jsonOf(o.Author) || adoptNarrower(n.Author, o.Author), "authorship broadened")
	add(len(o.AllowedFiles) == 0 || (len(n.AllowedFiles) > 0 && superset(o.AllowedFiles, n.AllowedFiles)), "allowedFiles broadened or rewritten")
	add(len(o.CompanionFiles) == 0 && len(n.CompanionFiles) == 0 || superset(o.CompanionFiles, n.CompanionFiles), "companionFiles broadened or rewritten")
	add(superset(n.ProtectedFiles, o.ProtectedFiles), "protectedFiles narrowed")
	add(n.ModifyOnly || !o.ModifyOnly, "modifyOnly removed")
	add(capBounded(n.MaxPatchFiles, o.MaxPatchFiles), "maxPatchFiles raised or removed")
	add(capBounded(n.MaxModifiedLines, o.MaxModifiedLines), "maxModifiedLines raised or removed")
	add(capBounded(n.MaxPerDay, o.MaxPerDay), "maxPerDay raised or removed")
	add(o.DiffShape == "" || n.DiffShape == o.DiffShape, "diffShape changed or removed")
	add(superset(n.HoldoutChecks, o.HoldoutChecks), "holdoutChecks removed")
	add(o.ReleaseAgeCheck == "" || n.ReleaseAgeCheck == o.ReleaseAgeCheck, "releaseAgeCheck changed or removed")
	add(o.RequiredLabel == "" || n.RequiredLabel == o.RequiredLabel, "requiredLabel changed or removed")
	add(o.Oracle == nil || jsonOf(n.Oracle) == jsonOf(o.Oracle), "oracle changed or removed")
	add(o.Monitor == nil || jsonOf(n.Monitor) == jsonOf(o.Monitor), "monitor changed or removed: its evidence")
	return why
}

func modeRank(cl config.Class) int {
	switch {
	case cl.Live:
		return 2
	case cl.Shadow:
		return 1
	}
	return 0
}

// adoptNarrower: both adopt, and the new logins and branches are among the old ones.
func adoptNarrower(n, o *config.Author) bool {
	if n == nil || o == nil || n.Adopt == nil || o.Adopt == nil {
		return false
	}
	return superset(o.Adopt.Logins, n.Adopt.Logins) && superset(o.Adopt.Branches, n.Adopt.Branches)
}

// capBounded: no old cap, or a new one at most the old.
func capBounded(n, o int) bool { return o == 0 || (n > 0 && n <= o) }

// superset: every element of sub is in set, compared as written.
func superset(set, sub []string) bool {
	return !slices.ContainsFunc(sub, func(s string) bool { return !slices.Contains(set, s) })
}
```

- [ ] **Step 4: Run them to verify they pass**, same command: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/mergepolicy
git commit -m "feat(mergepolicy): structural relaxation diff between two policies"
```

### Task 8: `maku policy simulate` and `maku policy diff`

**Files:**
- Modify: `internal/app/maku_policy.go`, `internal/app/maku.go` (usage)
- Test: `internal/app/maku_policy_sim_test.go`

**Interfaces:**
- Consumes: `reconciler.ReadCase`, `reconciler.Simulate` (Task 6), `mergepolicy.Structural` (Task 7)
- Produces: `maku policy simulate --config F --repository R POLICY CASE...` and `maku policy diff --config F --repository R OLD NEW`, both refused with `policyManagement.simulation` off

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package app

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// simulationConfig is policyConfig with policyManagement.simulation on.
func simulationConfig(t *testing.T) string {
	t.Helper()
	raw, err := os.ReadFile(policyConfig)
	if err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(t.TempDir(), "factory.yaml")
	if err := os.WriteFile(p, append(raw, []byte("policyManagement: {simulation: true}\n")...), 0o600); err != nil {
		t.Fatal(err)
	}
	return p
}

func exportedPolicy(t *testing.T, cfg string) string {
	t.Helper()
	var out bytes.Buffer
	if err := (Maku{Dir: t.TempDir(), Out: &out, Err: &out}).run(t.Context(), []string{"policy", "export", "--config", cfg, "--repository", policyRepo(t)}); err != nil {
		t.Fatalf("%v\n%s", err, out.String())
	}
	p := filepath.Join(t.TempDir(), "agent-factory.yaml")
	if err := os.WriteFile(p, out.Bytes(), 0o600); err != nil {
		t.Fatal(err)
	}
	return p
}

const fixtures = "../factory/reconciler/testdata/conformance/"

func TestPolicySimulate(t *testing.T) {
	cfg := simulationConfig(t)
	policy := exportedPolicy(t, cfg)
	var out bytes.Buffer
	err := Maku{Dir: t.TempDir(), Out: &out, Err: &out}.run(t.Context(), []string{"policy", "simulate", "--config", cfg,
		"--repository", policyRepo(t), policy, fixtures + "01-arms.json", fixtures + "16-docs-unarmed.json"})
	if err != nil {
		t.Fatalf("%v\n%s", err, out.String())
	}
	if lines := strings.Split(strings.TrimSpace(out.String()), "\n"); len(lines) != 3 || strings.Count(out.String(), "unchanged") != 2 {
		t.Fatalf("a header and two unchanged rows:\n%s", out.String())
	}
}

func TestPolicyDiff(t *testing.T) {
	cfg := simulationConfig(t)
	old := exportedPolicy(t, cfg)
	raw, err := os.ReadFile(old)
	if err != nil {
		t.Fatal(err)
	}
	next := filepath.Join(t.TempDir(), "next.yaml")
	if err := os.WriteFile(next, []byte(strings.Replace(string(raw), "mode: shadow", "mode: live", 1)), 0o600); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	if err := (Maku{Dir: t.TempDir(), Out: &out, Err: &out}).run(t.Context(), []string{"policy", "diff", "--config", cfg, "--repository", policyRepo(t), old, next}); err != nil {
		t.Fatalf("%v\n%s", err, out.String())
	}
	if !strings.Contains(out.String(), "relaxation") || !strings.Contains(out.String(), "mode raised") {
		t.Fatalf("%s", out.String())
	}
}

// The switch a simulator that disagrees with the gate turns off (stage 2).
func TestSimulateAndDiffNeedTheSwitch(t *testing.T) {
	policy := exportedPolicy(t, policyConfig)
	for _, verb := range []string{"simulate", "diff"} {
		var out bytes.Buffer
		err := Maku{Dir: t.TempDir(), Out: &out, Err: &out}.run(t.Context(), []string{"policy", verb, "--config", policyConfig,
			"--repository", policyRepo(t), policy, policy})
		if err == nil || !strings.Contains(err.Error(), "policyManagement.simulation") {
			t.Fatalf("%s: got %v", verb, err)
		}
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run 'Policy|Simulate' ./internal/app/`
Expected: FAIL: `policy: unknown verb "simulate"`.

- [ ] **Step 3: Implement**

```diff
@@ -3,22 +3,26 @@
 package app

 import (
+	"cmp"
 	"errors"
 	"flag"
 	"fmt"
 	"os"
 	"path/filepath"
 	"strings"
+	"text/tabwriter"

 	"github.com/Smana/maku/internal/factory/config"
 	"github.com/Smana/maku/internal/factory/mergepolicy"
+	"github.com/Smana/maku/internal/factory/reconciler"
 )

-// policy is `maku policy`: offline, against a factory config file, for the migration's export
-// and for a repository's own CI.
+// policy is `maku policy`: offline, against a factory config file, for the migration's export,
+// for a repository's own CI, and (behind policyManagement.simulation) to simulate a policy on
+// decision fixtures and to tell a tightening from a relaxation.
 func (r Maku) policy(args []string) error {
 	if len(args) == 0 {
-		return fmt.Errorf("policy export or policy check\n%s", makuUsage)
+		return fmt.Errorf("policy export, check, simulate or diff\n%s", makuUsage)
 	}
 	verb, args := args[0], args[1:]
 	fs := flag.NewFlagSet("policy "+verb, flag.ContinueOnError)
@@ -60,25 +64,112 @@ func (r Maku) policy(args []string) error {
 		if len(pos) != 1 {
 			return errors.New("policy check takes one policy file")
 		}
-		raw, err := os.ReadFile(filepath.Clean(pos[0]))
+		f, err := readPolicy(pos[0], cfg)
 		if err != nil {
 			return err
 		}
-		f, err := mergepolicy.Parse(raw)
-		if err != nil {
-			return err
-		}
-		if f.Factory != cfg.Factory {
-			return fmt.Errorf("policy: the file names factory %q, this config is factory %q", f.Factory, cfg.Factory)
-		}
-		if err := mergepolicy.Validate(f, cfg); err != nil {
-			return err
-		}
 		if d := mergepolicy.Compare(rc, f, cfg); len(d) > 0 {
 			return fmt.Errorf("policy: not equivalent to the central config:\n%s", strings.Join(d, "\n"))
 		}
 		_, err = fmt.Fprintln(r.Out, "equivalent")
 		return err
+	case "simulate", "diff":
+		if !cfg.PolicyManagement.Simulation {
+			return fmt.Errorf("policy %s: policyManagement.simulation is off in %s", verb, *cfgPath)
+		}
+		if verb == "diff" {
+			return r.policyDiff(pos, cfg)
+		}
+		return r.policySimulate(pos, cfg, rc)
 	}
 	return fmt.Errorf("policy: unknown verb %q", verb)
 }
+
+// readPolicy reads a policy file as check does: strictly, naming this config's factory, valid
+// against it.
+func readPolicy(path string, cfg *config.Config) (*mergepolicy.File, error) {
+	raw, err := os.ReadFile(filepath.Clean(path))
+	if err != nil {
+		return nil, err
+	}
+	f, err := mergepolicy.Parse(raw)
+	if err != nil {
+		return nil, err
+	}
+	if f.Factory != cfg.Factory {
+		return nil, fmt.Errorf("policy: the file names factory %q, this config is factory %q", f.Factory, cfg.Factory)
+	}
+	if err := mergepolicy.Validate(f, cfg); err != nil {
+		return nil, err
+	}
+	return f, nil
+}
+
+// policySimulate decides each fixture under the central config and under the policy file, with
+// the gate's own evaluator (MP16), and prints the change. A fixture recorded under another config
+// shows the decision it recorded beside this config's.
+func (r Maku) policySimulate(pos []string, cfg *config.Config, rc *config.Repository) error {
+	if len(pos) < 2 {
+		return errors.New("policy simulate takes a policy file and one or more fixtures")
+	}
+	f, err := readPolicy(pos[0], cfg)
+	if err != nil {
+		return err
+	}
+	policy := map[string]mergepolicy.Resolved{}
+	for name, p := range f.Classes {
+		if policy[name], err = mergepolicy.Resolve(name, p, cfg); err != nil {
+			return err
+		}
+	}
+	var cases []reconciler.Case
+	for _, p := range pos[1:] {
+		raw, err := os.ReadFile(filepath.Clean(p))
+		if err != nil {
+			return err
+		}
+		c, err := reconciler.ReadCase(raw)
+		if err != nil {
+			return fmt.Errorf("%s: %w", p, err)
+		}
+		c.Inputs.Task.Spec.Repository = rc.Name // the simulation is of this repository
+		cases = append(cases, c)
+	}
+	w := tabwriter.NewWriter(r.Out, 0, 4, 2, ' ', 0) // buffered: Flush returns the write error
+	_, _ = fmt.Fprintln(w, "CASE\tCLASS\tCENTRAL\tREPOSITORY\tCHANGE")
+	for _, row := range reconciler.Simulate(cfg, policy, cases) {
+		change := row.Change
+		if !row.Conforms {
+			change += " (the fixture recorded another central decision)"
+		}
+		_, _ = fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", row.Name, row.Class, show(row.Central), show(row.Repository), change)
+	}
+	return w.Flush()
+}
+
+func show(o reconciler.Outcome) string { return o.Verdict + ":" + cmp.Or(o.Reason, "armed") }
+
+// policyDiff prints each class's structural change from the first file to the second (MP8).
+func (r Maku) policyDiff(pos []string, cfg *config.Config) error {
+	if len(pos) != 2 {
+		return errors.New("policy diff takes the old policy file and the new one")
+	}
+	old, err := readPolicy(pos[0], cfg)
+	if err != nil {
+		return err
+	}
+	next, err := readPolicy(pos[1], cfg)
+	if err != nil {
+		return err
+	}
+	changes, err := mergepolicy.Structural(old, next, cfg)
+	if err != nil {
+		return err
+	}
+	w := tabwriter.NewWriter(r.Out, 0, 4, 2, ' ', 0) // buffered: Flush returns the write error
+	_, _ = fmt.Fprintln(w, "CLASS\tCHANGE\tWHY")
+	for _, c := range changes {
+		_, _ = fmt.Fprintf(w, "%s\t%s\t%s\n", c.Class, c.Kind, strings.Join(c.Why, "; "))
+	}
+	return w.Flush()
+}
```

- [ ] **Step 4: Run them to verify they pass**, same command: PASS. `task lint` exits 0 (the tabwriter writes are `_, _ =`: `Flush` returns their error).

- [ ] **Step 5: Commit**

```bash
git add internal/app
git commit -m "feat(maku): policy simulate and policy diff, behind policyManagement.simulation"
```

### Task 9: The stage 2 exit

Offline half, in the PR: `TestConformance` passes (every fixture decides as recorded; the exported central classes decide each the same way), and `task check` exits 0.

Live half, **only after plan 1's Task 10 has passed** (the deviation above):

- [ ] **Step 1:** Release Maku with this plan and the stage 3 plan; bump the pin here.
- [ ] **Step 2:** A one-line config PR sets `policyManagement.simulation: true`. Nothing in the factory reads it.
- [ ] **Step 3:** From a checkout of cloud-native-ref, run
  `maku policy simulate --config <rendered factory config> --repository Smana/cloud-native-ref .github/agent-factory.yaml <Maku>/internal/factory/reconciler/testdata/conformance/*.json`.
  Expected: every row `unchanged` (the canary's file is the export). A row marked "the fixture recorded another central decision" is a config difference from the fixtures' rig, not a failure.
- [ ] **Step 4:** Record the output in `docs/runbooks/agent-factory/results-merge-policy-stage-2-<date>.md`. Stage 2 exits when the offline half holds and the stage 3 plan's first week of decisions starts with no `unexplained` (S9).

---

## Carried to later plans

| To | Item |
|---|---|
| Plan 4 | A relaxation (Task 7) returns the class to shadow under repository authority; a class using `any` gets authority only once each branch has its policy-bot rule (S6) |
| Plan 4 | ai-native-ref's `test-agent-repo-files.py` still pins its own fence file to `factory: aws-0` (plan 1) |
| Plan 5 | The `merge_policy_snapshots` table, with the broker's decision API (S1); grants consulted by `DecideArmUnder`'s approval branch (S5) |
| Plan 6 | The internal simulation endpoint over `reconciler.Simulate` (S2); the editor calls `Structural` before it offers a link |
| Separate PR | `fence.Parse`'s case-insensitive keys (plan 1), unchanged here |

## Self-review

- **Coverage:** plan 1's program row for plan 2 (structural diff, one evaluator with `any`, snapshots, simulation, fixtures) maps to Tasks 7, 5 and 1–2, 3 (S1), 6 and 8 (S2), 6. Plan 1's four carried items: Tasks 1, 2. The Observe cost: Task 3. MP8, MP12 (in-process half), MP16 are implemented; Q3 is S5.
- **Placeholders:** none; Task 6 Step 5 generates data from the rig, and its code is given.
- **Names:** `Variants`, `OnlyGuardrail`, `Snapshot.Classes`, `DecideArmUnder`, `decide`, `withShape`, `provenance`, `Case`, `ReadCase`, `Simulate`, `Row`, `Structural`, `Change` are consistent across tasks and with the stage 3 plan.
