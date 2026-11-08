# Merge policy self-service, stage 4 (repository authority) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A repository cut over with `classAuthority: repository` is decided on its own `.github/agent-factory.yaml`, behind `policyManagement.repositoryAuthority`; invalid, unreadable or stale policy pauses its auto-merge fail-closed, and with the switch off the gate is byte-for-byte today's.

**Architecture:** `mergepolicy.Watch` already holds each owned repository's resolved classes (stage 2, Task 3). It gains `Authority` (the gate's read: fresh, valid, with classes, or an error) and `Classes` (every other reader's: the last valid file, live classes in shadow while no authority holds, relaxed classes in shadow). The config serves `Classes` through `Repos`/`RepositoryFor` for a cut-over entry, so the 40-odd central `Classes` readers read one source; the gate reads the snapshot once per pass and decides on `DecideArmUnder` (stage 2, Task 5), every `any` branch and the `requiresApproval` subset included.

**Tech Stack:** Go (Maku), OpenTelemetry metrics through `internal/factory/fmetrics`, the decision record of `internal/factory/decision`.

**Spec:** [`docs/superpowers/specs/2026-11-04-merge-policy-self-service-design.md`](../specs/2026-11-04-merge-policy-self-service-design.md) · **Predecessor:** [the stage 3 plan](2026-11-07-merge-policy-stage-3-dual-evaluation-plan.md)

**Read against:** Maku `origin/main` `c2a07b58`. Every code block is the compiled code of [Smana/maku#399](https://github.com/Smana/maku/pull/399), written test first; every `file:line` is main's.

## Deviation: written before the stage-3 exit

The owner asked on 2026-11-08 for stages 4, 5 and 6 to be built behind switches that stay off
while stage 3's week of dual evaluation runs. `policyManagement.repositoryAuthority` stays `false`
until stage 3 exits with zero `unexplained` (the stage 3 plan, Task 4); Task 6 below is the cutover.

## Global Constraints

- `policyManagement.repositoryAuthority` defaults to off and needs `read` (config validation refuses it alone). Off, no policy source is read, `Repos` returns the config's own slice, and the gate calls `DecideArm` exactly as on main: proven by `TestRepositoryAuthorityOffIsToday` and `TestTheSourceIsReadOnlyWithTheSwitch`.
- A repository never has two authoritative sources (MP15): `classAuthority: repository` refuses central `classes` on the same entry, and needs the switch.
- Fail closed (MP13): no read, a read older than the fence's 15-minute window, an invalid file or one with no classes never arms; the fixed base (CI, leak scan, fence, policy-bot) is still decided first (MP3).
- One evaluator (MP16): the gate decides on `DecideArmUnder`, the function simulation and dual evaluation already call.
- Metric labels stay bounded (MP18): `repository` through `s.repository()`, `class` the class name, `change` and `reason` from closed lists. Hashes go to the record and the log.
- The tally keeps reading every record (`scripts/shadow-merge-tally.sh`): `policy=` sits before `reviewer=`.
- Maku: `task check` exits 0 before every PR; SPDX line; conventional commits in English, no trailers. Wrap test runs in `systemd-run --user --scope -q -p MemoryMax=6G`.

## Rulings this plan takes from reading the code

| # | The spec says | The code says | This plan |
|---|---|---|---|
| D1 | "The central cutover then switches authority and removes that repository's central classes" | `Repository` (`internal/factory/config/config.go:306-314`) has no field saying which source is authoritative; `validateRepository` requires `docs-links` and `revert` centrally (`config.go:1734-1738`) | A per-entry `classAuthority: central \| repository`; `repository` skips the central-class requirements (the file's `Validate` already requires both) and refuses central `classes` |
| D2 | Repository YAML has merge authority | 40-odd readers read `RepositoryFor(...).Classes` or `Repos()[i].Classes` (triage, intake adoption, schedules, the monitor, the ledger, the revert path) | One seam: `Config.SetClassSource` makes `Repos` return a copy with a cut-over entry's classes from `Watch.Classes`; no reader changes |
| D3 | `any` branches | A `config.Class` holds one shape; `Resolved.Class` is `all`'s leaves, looser than any branch | Readers outside the gate see `Resolved.Class`; the gate decides on `Resolved.Variants()` through `DecideArmUnder`, and reads the diff when any variant needs it |
| D4 | "Invalid policy pauses auto-merge; transient reads use the staleness window then fail closed" | The fence calls `OnFile` only on a successful read (`internal/factory/fence/fence.go:115-117`) and ages ownership at `fenceStale` (`internal/app/factory.go:80`) | `ErrUnreadable` and `ErrStale` (the same 15 minutes) wait as `policy_unavailable`, bounded by `merge.awaitingCIFor`; `ErrInvalid` hands off as `policy_invalid`. Both are counted on `maku_factory_policy_load_errors_total` (`unreadable`, `stale` new) |
| D5 | Pausing must not stop everything else | The monitor, triage and intake read the classes too | `Watch.Classes` keeps the last valid file for them, every live class in shadow while authority fails: the monitor of merged tasks keeps running, and the revert path (`merge.go:1066`, `1127`) cannot auto-merge |
| D6 | A relaxation returns the class to shadow (MP8) | `Structural` (`internal/factory/mergepolicy/structural.go:30`) compares two parsed files; nothing durable records a demotion before stage 5's tables | The Watch compares each new valid file with the last; a relaxation of a live class runs it in shadow until the process restarts, logged and counted (`maku_factory_policy_changes_total`). The restart gap is closed by stage 6's promotion and stage 5's store; meanwhile the file change itself is a policy PR a human merged (MP14) |
| D7 | Every decision binds to its policy (MP12) | `awaitingCI` decides twice per pass (`merge.go:137`, `156`) | The snapshot is read once per pass (`gatePolicy`), both decisions bind to it, and the record carries `policy=<12 hex>` alone |
| D8 | Dual evaluation compares central with repository | A cut-over repository has no central classes | `dual` skips a cut-over repository; the stage 1 comparison and its divergence gauge are skipped for it too |
| D9 | Readers that build things at start | `NeedsMerger`, `AnyMonitored`, `AnyFlux` decide at start which Apps and readers the binary builds (`config.go:353`, `364`, `444`) | A cut-over repository answers `true` to each: its classes arrive at run time |
| D10 | Grants | `withApproval` (`internal/factory/reconciler/evaluate.go:51`) hands the `requiresApproval` subset of a live class to a human | Unchanged here: under authority the subset asks a maintainer (`approval_required`); stage 5 adds grants inside `withApproval` |

## Files

| File | Responsibility |
|---|---|
| `internal/factory/config/mergepolicy.go`, `config.go` | The switch, `classAuthority`, its validation, `RepositoryAuthoritative`, `SetClassSource` and `Repos`' copy |
| `internal/factory/mergepolicy/watch.go`, `resolve.go` | `Authority`, `Classes`, the demotion, `Resolved.inShadow`, the new reasons and errors |
| `internal/factory/fmetrics/fmetrics.go` | `maku_factory_policy_changes_total`; `unreadable` and `stale` load errors |
| `internal/factory/decision/decision.go` | `policy=` alone under authority |
| `internal/factory/reconciler/authority.go` | `gatePolicy`, `decideUnder`, `noAuthority`, `readsDiff` |
| `internal/factory/reconciler/merge.go`, `reconciler.go`, `dual.go` | The `Authority` source and the call |
| `internal/factory/narrate/narrate.go`, `internal/summary/waiting.go`, `internal/roomview/words.go` | Prose for `policy_unavailable`, `policy_invalid`, `approval_required` |
| `internal/app/factory.go` | The wiring |
| `docs/factory.md`, `docs/operations.md` | The switch, the record field, the metrics |

---

### Task 1: The switch and one authoritative source

**Files:**
- Modify: `internal/factory/config/mergepolicy.go:64-69` (`PolicyManagement`), `:95-97` (validation)
- Modify: `internal/factory/config/config.go:306-314` (`Repository`), `:385-390` (`Repos`), `:353`, `:364`, `:444`, `:1734-1738`, `:1772-1786`
- Test: `internal/factory/config/authority_test.go`

**Interfaces:**
- Produces: `PolicyManagement.RepositoryAuthority bool`; `Repository.ClassAuthority string`; `ClassAuthorityCentral`, `ClassAuthorityRepository`; `(*Config).RepositoryAuthoritative(*Repository) bool`; `(*Config).SetClassSource(func(string) (map[string]Class, bool))`

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package config

import (
	"fmt"
	"strings"
	"testing"
)

// cutOver is good's repository with its classes in its own policy file (merge policy stage 4).
func cutOver() Repository {
	c, err := Parse([]byte(good))
	if err != nil {
		panic(err)
	}
	r := c.Repos()[0]
	r.Name, r.Classes, r.ClassAuthority = "Smana/a", nil, ClassAuthorityRepository
	return r
}

func TestRepositoryAuthorityValidates(t *testing.T) {
	for name, tc := range map[string]struct {
		pm   PolicyManagement
		repo func(*Repository)
		want string
	}{
		"the switch with read":       {PolicyManagement{Read: true, RepositoryAuthority: true}, func(*Repository) {}, ""},
		"the switch alone":           {PolicyManagement{RepositoryAuthority: true}, func(*Repository) {}, "repositoryAuthority needs read"},
		"a cut-over without classes": {PolicyManagement{Read: true, RepositoryAuthority: true}, func(*Repository) {}, ""},
		"a cut-over, the switch off": {PolicyManagement{Read: true}, func(*Repository) {}, "needs policyManagement.repositoryAuthority"},
		"two sources": {PolicyManagement{Read: true, RepositoryAuthority: true},
			func(r *Repository) { r.Classes = map[string]Class{"docs-links": {}} }, "two authoritative sources"},
		"an unknown authority": {PolicyManagement{Read: true, RepositoryAuthority: true},
			func(r *Repository) { r.ClassAuthority = "git" }, `classAuthority "git"`},
		"a schedule naming a class the file declares": {PolicyManagement{Read: true, RepositoryAuthority: true},
			func(r *Repository) {
				r.Schedules = []Schedule{{Name: "links", Cron: "0 6 * * 1", Class: "dead-links", Text: "fix links", Probe: "dead-links", ProbeAuthor: "x"}}
			}, ""},
	} {
		t.Run(name, func(t *testing.T) {
			r := cutOver()
			tc.repo(&r)
			c := &Config{PolicyManagement: tc.pm, Caps: Caps{MaxTextBytes: 100}}
			var out []string
			bad := func(f string, a ...any) { out = append(out, fmt.Sprintf(f, a...)) }
			c.validateMergePolicy(bad)
			c.validateRepository(&r, map[string]bool{}, bad)
			got := strings.Join(out, "\n")
			if (tc.want == "") != (got == "") || !strings.Contains(got, tc.want) {
				t.Fatalf("got %q, want %q", got, tc.want)
			}
		})
	}
}

// The repository's classes reach every reader through Repos and RepositoryFor, once a source is
// set: the gate, triage, intake and the monitor read one set of classes (MP15).
func TestACutOverRepositoryReadsItsClassesFromTheSource(t *testing.T) {
	central := Repository{Name: "Smana/b", Classes: map[string]Class{"docs-links": {Shadow: true}}}
	c := &Config{Repositories: []Repository{cutOver(), central}, PolicyManagement: PolicyManagement{Read: true, RepositoryAuthority: true}}
	if got := c.RepositoryFor("smana/a").Classes; got != nil {
		t.Fatalf("no source yet: %v", got)
	}
	c.SetClassSource(func(repository string) (map[string]Class, bool) {
		if repository != "Smana/a" {
			t.Fatalf("asked for %s", repository)
		}
		return map[string]Class{"docs-links": {Live: true}}, true
	})
	if !c.RepositoryFor("Smana/a").Classes["docs-links"].Live {
		t.Fatal("the source's class")
	}
	if !c.RepositoryFor("Smana/b").Classes["docs-links"].Shadow {
		t.Fatal("a central repository keeps its classes")
	}
	if c.Repositories[0].Classes != nil {
		t.Fatal("the config itself is not written")
	}
}

// Off, a source is never read: the switch gates it, whatever is wired.
func TestTheSourceIsReadOnlyWithTheSwitch(t *testing.T) {
	r := cutOver()
	c := &Config{Repositories: []Repository{r}}
	c.SetClassSource(func(string) (map[string]Class, bool) {
		t.Fatal("read with the switch off")
		return nil, false
	})
	_ = c.Repos()
}

// A cut-over repository's classes arrive at run time, so what the binary builds at start assumes
// they may be live, monitored and watching Flux.
func TestACutOverRepositoryNeedsTheMerger(t *testing.T) {
	c := &Config{Repositories: []Repository{cutOver()}, PolicyManagement: PolicyManagement{Read: true, RepositoryAuthority: true}}
	if !c.NeedsMerger() || !c.AnyMonitored() || !c.AnyFlux() {
		t.Fatal("a cut-over repository may hold any class")
	}
	if (&Config{Repositories: []Repository{{Name: "Smana/b"}}}).NeedsMerger() {
		t.Fatal("no class, no merger")
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/config/`
Expected: FAIL to build: `unknown field ClassAuthority`, `undefined: ClassAuthorityRepository`, `unknown field RepositoryAuthority`.

- [ ] **Step 3: Implement**

```diff
diff --git a/internal/factory/config/config.go b/internal/factory/config/config.go
index 673adaf4..40948389 100644
--- a/internal/factory/config/config.go
+++ b/internal/factory/config/config.go
@@ -169,4 +169,6 @@ type Config struct {
 	// binary to log: Parse has no logger.
 	Warnings []string `json:"-"`
+	// classSource is a cut-over repository's classes (SetClassSource).
+	classSource func(repository string) (map[string]Class, bool)
 }

@@ -312,4 +314,7 @@ type Repository struct {
 	Schedules    []Schedule       `json:"schedules,omitempty"`
 	Checks       Checks           `json:"checks,omitzero"`
+	// ClassAuthority is central (the default) or repository: its classes are then its
+	// .github/agent-factory.yaml's, with policyManagement.repositoryAuthority on (stage 4, MP15).
+	ClassAuthority string `json:"classAuthority,omitempty"`
 }

@@ -352,4 +357,7 @@ func (r *Repository) IsMaintainer(login string) bool {
 // monitor reads main's checks and writes labels through the merger App.
 func (r *Repository) NeedsMerger() bool {
+	if r.ClassAuthority == ClassAuthorityRepository {
+		return true // its classes arrive at run time, from its file
+	}
 	for _, cl := range r.Classes {
 		if cl.Live || cl.Shadow || cl.Monitor != nil {
@@ -363,4 +371,7 @@ func (r *Repository) NeedsMerger() bool {
 // labels the merger writes in shadow too (merge gate R30).
 func (r *Repository) AnyMonitored() bool {
+	if r.ClassAuthority == ClassAuthorityRepository {
+		return true
+	}
 	for _, cl := range r.Classes {
 		if cl.Monitor != nil {
@@ -385,9 +396,25 @@ func (r *Repository) AnyLive() bool {
 func (c *Config) Repos() []Repository {
 	if len(c.Repositories) > 0 || reflect.ValueOf(c.legacyRepository()).IsZero() {
-		return c.Repositories
+		return c.withSource(c.Repositories)
 	}
 	return []Repository{c.legacyRepository()}
 }

+// withSource is rs with each cut-over repository's classes read from the source, on a copy: the
+// config itself is never written. Without a cut-over repository it is rs.
+func (c *Config) withSource(rs []Repository) []Repository {
+	if c.classSource == nil || !c.PolicyManagement.RepositoryAuthority ||
+		!slices.ContainsFunc(rs, func(r Repository) bool { return r.ClassAuthority == ClassAuthorityRepository }) {
+		return rs
+	}
+	out := slices.Clone(rs)
+	for i := range out {
+		if out[i].ClassAuthority == ClassAuthorityRepository {
+			out[i].Classes, _ = c.classSource(out[i].Name)
+		}
+	}
+	return out
+}
+
 func (c *Config) legacyRepository() Repository {
 	return Repository{Name: c.Repository, Maintainers: c.Maintainers, TriggerLabel: c.TriggerLabel,
@@ -444,4 +471,7 @@ func (c *Config) NeedsMerger() bool {
 func (c *Config) AnyFlux() bool {
 	for _, r := range c.Repos() {
+		if r.ClassAuthority == ClassAuthorityRepository {
+			return true // its file may declare monitor.flux
+		}
 		for _, cl := range r.Classes {
 			if cl.Monitor != nil && cl.Monitor.Flux != nil {
@@ -1732,6 +1762,8 @@ func (c *Config) validateRepository(r *Repository, seenSchedule map[string]bool,
 		bad("triggerLabel is required")
 	}
+	c.validateAuthority(r, bad)
+	cutOver := r.ClassAuthority == ClassAuthorityRepository // its file declares the classes, read at run time
 	for _, name := range []string{"docs-links", "revert"} {
-		if _, ok := r.Classes[name]; !ok {
+		if _, ok := r.Classes[name]; !ok && !cutOver {
 			bad("class %s is required (OD-8)", name)
 		}
@@ -1770,5 +1802,5 @@ func (c *Config) validateRepository(r *Repository, seenSchedule map[string]bool,
 			bad("schedule %s: cron %q does not parse", e.Name, e.Cron)
 		}
-		if e.Class != "review" {
+		if e.Class != "review" && !cutOver {
 			if _, ok := r.Classes[e.Class]; !ok {
 				bad("schedule %s: class %q is review or a declared class", e.Name, e.Class)
@@ -1781,5 +1813,5 @@ func (c *Config) validateRepository(r *Repository, seenSchedule map[string]bool,
 		case "", "renovate-red":
 		case "dead-links":
-			if o := r.Classes[e.Class].Oracle; o == nil || o.Probe != "dead-links" {
+			if o := r.Classes[e.Class].Oracle; !cutOver && (o == nil || o.Probe != "dead-links") {
 				bad("schedule %s: probe dead-links needs class %q to declare oracle.probe dead-links", e.Name, e.Class)
 			}
diff --git a/internal/factory/config/mergepolicy.go b/internal/factory/config/mergepolicy.go
index 0da9168d..c247a367 100644
--- a/internal/factory/config/mergepolicy.go
+++ b/internal/factory/config/mergepolicy.go
@@ -67,6 +67,16 @@ type PolicyManagement struct {
 	// central decision is the one acted on. Needs Read.
 	DualEvaluation bool `json:"dualEvaluation,omitempty"`
+	// RepositoryAuthority lets a repository whose entry says classAuthority: repository be decided
+	// on its own policy file rather than on central classes (stage 4). Invalid, unreadable or stale
+	// policy pauses its auto-merge; human merges continue. Needs Read.
+	RepositoryAuthority bool `json:"repositoryAuthority,omitempty"`
 }

+// The class authorities of a repository (MP15): central classes, or the repository's own file.
+const (
+	ClassAuthorityCentral    = "central"
+	ClassAuthorityRepository = "repository"
+)
+
 var profileRE = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$`)

@@ -96,4 +106,7 @@ func (c *Config) validateMergePolicy(bad func(string, ...any)) {
 		bad("policyManagement.dualEvaluation needs read: it evaluates the policy read observes")
 	}
+	if pm := c.PolicyManagement; pm.RepositoryAuthority && !pm.Read {
+		bad("policyManagement.repositoryAuthority needs read: it decides on the policy read observes")
+	}
 	g := c.MergeGuardrails
 	for _, f := range []struct {
@@ -116,2 +129,34 @@ func (c *Config) validateMergePolicy(bad func(string, ...any)) {
 	}
 }
+
+// validateAuthority is a repository's classAuthority (MP15): one authoritative source, so a
+// repository cut over to its own file declares no central class, and the cutover needs the switch.
+func (c *Config) validateAuthority(r *Repository, bad func(string, ...any)) {
+	switch r.ClassAuthority {
+	case "", ClassAuthorityCentral:
+		return
+	case ClassAuthorityRepository:
+	default:
+		bad("classAuthority %q is %s or %s", r.ClassAuthority, ClassAuthorityCentral, ClassAuthorityRepository)
+		return
+	}
+	if !c.PolicyManagement.RepositoryAuthority {
+		bad("classAuthority repository needs policyManagement.repositoryAuthority")
+	}
+	if len(r.Classes) > 0 {
+		bad("classAuthority repository: classes are declared centrally too, two authoritative sources (MP15): remove them")
+	}
+}
+
+// RepositoryAuthoritative is whether the repository's classes are its own file's (stage 4): cut
+// over, with the switch on.
+func (c *Config) RepositoryAuthoritative(r *Repository) bool {
+	return r != nil && r.ClassAuthority == ClassAuthorityRepository && c.PolicyManagement.RepositoryAuthority
+}
+
+// SetClassSource makes source the classes of every repository cut over to its own file (stage 4):
+// Repos and RepositoryFor return them, so every reader reads one set. The binary sets it once,
+// before anything reads the config; with the switch off it is never called.
+func (c *Config) SetClassSource(source func(repository string) (map[string]Class, bool)) {
+	c.classSource = source
+}
```

- [ ] **Step 4: Run them to verify they pass**, same command: `ok`.

- [ ] **Step 5: Commit** (with Tasks 2–5 in one PR)

### Task 2: The Watch's authority, pause and demotion

**Files:**
- Modify: `internal/factory/mergepolicy/watch.go:17-28` (reasons, `Recorder`), `:33-40` (`Snapshot.File`), `:46-55` (`Watch`), `:78-89` (`Observe`), `:111` (no comparison for a cut-over repository), `:138` (new methods before `listed`)
- Modify: `internal/factory/mergepolicy/resolve.go` (`Resolved.inShadow`)
- Test: `internal/factory/mergepolicy/authority_test.go`; `watch_test.go`'s `rec` gains `changes`

**Interfaces:**
- Consumes: `Structural`, `KindRelaxation` (stage 2); `Config.SetClassSource`, `RepositoryAuthoritative` (Task 1)
- Produces: `ErrUnreadable`, `ErrStale`, `ErrInvalid`; `ReasonUnreadable = "unreadable"`, `ReasonStale = "stale"`; `Recorder.PolicyChange(ctx, repository, class, change string)`; `Watch.Stale`; `(*Watch).Authority(repository string) (Snapshot, error)`; `(*Watch).Classes(repository string) (map[string]config.Class, bool)`

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"context"
	"errors"
	"slices"
	"testing"
	"time"

	"github.com/Smana/maku/internal/factory/config"
)

func (r *rec) PolicyChange(_ context.Context, _, class, change string) {
	r.changes = append(r.changes, class+" "+change)
}

// authorityRig is a Watch over one repository cut over to its own file (stage 4), at a clock the
// test moves.
func authorityRig() (*Watch, *rec, *time.Time) {
	c := central()
	c.PolicyManagement = config.PolicyManagement{Read: true, RepositoryAuthority: true}
	c.Repositories = []config.Repository{{Name: "o/r", ClassAuthority: config.ClassAuthorityRepository}}
	r := &rec{}
	now := time.Date(2026, 11, 8, 12, 0, 0, 0, time.UTC)
	w := &Watch{Cfg: c, Metrics: r, Stale: 15 * time.Minute, Now: func() time.Time { return now }}
	c.SetClassSource(w.Classes)
	return w, r, &now
}

const (
	liveDocs    = "factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: plain, conditions: {all: [{maxModifiedLines: 10}]}}\n  revert: {mode: shadow, author: agents, harness: plain}\n"
	tighterDocs = "factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: plain, conditions: {all: [{maxModifiedLines: 5}]}}\n  revert: {mode: shadow, author: agents, harness: plain}\n"
	looserDocs  = "factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: plain, conditions: {all: [{maxModifiedLines: 50}]}}\n  revert: {mode: shadow, author: agents, harness: plain}\n"
)

// Stage 4's fail-closed rule: no read yet, a stale read, an invalid file or one with no classes
// gives no authority; a fresh valid file does.
func TestAuthority(t *testing.T) {
	for name, tc := range map[string]struct {
		body string // "" reads nothing
		age  time.Duration
		want error
	}{
		"never read":       {"", 0, ErrUnreadable},
		"a valid file":     {liveDocs, 0, nil},
		"a stale read":     {liveDocs, 15 * time.Minute, ErrStale},
		"an invalid file":  {"factory: aws-0\nclasses: [no]\n", 0, ErrInvalid},
		"a fence-only one": {"factory: aws-0\n", 0, ErrInvalid},
		"a guardrail":      {"factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: nope}\n  revert: {mode: live, author: agents, harness: plain}\n", 0, ErrInvalid},
	} {
		t.Run(name, func(t *testing.T) {
			w, _, now := authorityRig()
			if tc.body != "" {
				w.Observe(t.Context(), "o/r", []byte(tc.body))
			}
			*now = now.Add(tc.age)
			s, err := w.Authority("O/R")
			if !errors.Is(err, tc.want) {
				t.Fatalf("got %v, want %v", err, tc.want)
			}
			if err == nil && !s.Classes["docs-links"].Class.Live {
				t.Fatalf("%+v", s.Classes)
			}
		})
	}
}

// A cut-over repository is compared with nothing: its central classes are gone by design.
func TestACutOverRepositoryRecordsNoDivergence(t *testing.T) {
	w, r, _ := authorityRig()
	w.Observe(t.Context(), "o/r", []byte(liveDocs))
	if s, _ := w.Snapshot("o/r"); len(s.Divergences) != 0 || len(r.gauge) != 0 {
		t.Fatalf("%v %v", s.Divergences, r.gauge)
	}
}

// Every other reader gets the last valid classes; while the file gives no authority, each live
// class reads as shadow, so nothing merges on it (MP13), and the monitor and triage keep working.
func TestClassesPauseWhileThePolicyGivesNoAuthority(t *testing.T) {
	w, _, _ := authorityRig()
	if _, ok := w.Classes("o/r"); ok {
		t.Fatal("never read: no classes")
	}
	w.Observe(t.Context(), "o/r", []byte(liveDocs))
	if cl, _ := w.Classes("o/r"); !cl["docs-links"].Live || !w.Cfg.RepositoryFor("o/r").Classes["docs-links"].Live {
		t.Fatalf("%+v", cl)
	}
	w.Observe(t.Context(), "o/r", []byte("factory: aws-0\nclasses: [no]\n"))
	cl, ok := w.Classes("o/r")
	if !ok || cl["docs-links"].Live || !cl["docs-links"].Shadow || cl["docs-links"].MaxModifiedLines != 10 {
		t.Fatalf("paused, as last valid: %+v", cl)
	}
}

// MP8: a valid file relaxing a live class runs that class in shadow, a tightening keeps it live,
// and both are counted. The demotion holds until the process restarts.
func TestARelaxationReturnsTheClassToShadow(t *testing.T) {
	w, r, _ := authorityRig()
	w.Observe(t.Context(), "o/r", []byte(liveDocs))
	w.Observe(t.Context(), "o/r", []byte(tighterDocs))
	if s, err := w.Authority("o/r"); err != nil || !s.Classes["docs-links"].Class.Live {
		t.Fatalf("a tightening stays live: %v %+v", err, s.Classes["docs-links"])
	}
	w.Observe(t.Context(), "o/r", []byte(looserDocs))
	s, err := w.Authority("o/r")
	if err != nil {
		t.Fatal(err)
	}
	if d := s.Classes["docs-links"]; d.Class.Live || !d.Class.Shadow || slices.ContainsFunc(d.Variants(), func(v config.Class) bool { return v.Live }) {
		t.Fatalf("relaxed: %+v", d)
	}
	if cl, _ := w.Classes("o/r"); cl["docs-links"].Live {
		t.Fatal("every reader sees the demotion")
	}
	w.Observe(t.Context(), "o/r", []byte(liveDocs)) // tighter than the relaxed file, still demoted
	if s, _ := w.Authority("o/r"); s.Classes["docs-links"].Class.Live {
		t.Fatal("a demotion is not undone by the next file")
	}
	if want := []string{"docs-links tightening", "docs-links relaxation", "docs-links tightening"}; !slices.Equal(r.changes, want) {
		t.Fatalf("%q", r.changes)
	}
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/factory/mergepolicy/`
Expected: FAIL to build: `undefined: ErrUnreadable`, `w.Authority undefined`, `unknown field Stale`.

- [ ] **Step 3: Implement**

```diff
diff --git a/internal/factory/mergepolicy/resolve.go b/internal/factory/mergepolicy/resolve.go
index 13dcd52a..cfc1929c 100644
--- a/internal/factory/mergepolicy/resolve.go
+++ b/internal/factory/mergepolicy/resolve.go
@@ -35,4 +35,23 @@ func (r Resolved) Variants() []config.Class {
 }

+// inShadow is r with every live variant in shadow (stage 4's pause and MP8's demotion).
+func (r Resolved) inShadow() Resolved {
+	shadow := func(cl config.Class) config.Class {
+		if cl.Live {
+			cl.Live, cl.Shadow = false, true
+		}
+		return cl
+	}
+	r.Class = shadow(r.Class)
+	if r.Branches != nil {
+		bs := make([]config.Class, len(r.Branches))
+		for i, b := range r.Branches {
+			bs[i] = shadow(b)
+		}
+		r.Branches = bs
+	}
+	return r
+}
+
 // Resolve turns a parsed class into the config.Class the gate decides on, under the guardrails:
 // they add protected paths and mandatory checks, an undeclared cap inherits theirs, and a declared
diff --git a/internal/factory/mergepolicy/watch.go b/internal/factory/mergepolicy/watch.go
index 4ad0b955..edf49450 100644
--- a/internal/factory/mergepolicy/watch.go
+++ b/internal/factory/mergepolicy/watch.go
@@ -7,4 +7,5 @@ import (
 	"crypto/sha256"
 	"encoding/hex"
+	"errors"
 	"log/slog"
 	"strings"
@@ -15,9 +16,19 @@ import (
 )

-// The reasons a policy fails to load. Unreadable and stale arrive with repository authority: until
-// then the fence's own metric reports a failed read, and nothing depends on a fresh policy.
+// The reasons a policy fails to load. Unreadable and stale are counted by the gate of a cut-over
+// repository (stage 4), the one reader that depends on a fresh policy.
 const (
-	ReasonInvalid   = "invalid"
-	ReasonGuardrail = "guardrail_mismatch"
+	ReasonInvalid    = "invalid"
+	ReasonGuardrail  = "guardrail_mismatch"
+	ReasonUnreadable = "unreadable"
+	ReasonStale      = "stale"
+)
+
+// Why a cut-over repository's policy gives no authority (stage 4, MP13): the gate pauses its
+// auto-merge on each.
+var (
+	ErrUnreadable = errors.New("the repository policy has not been read")
+	ErrStale      = errors.New("the repository policy's last read is older than the fence's staleness window")
+	ErrInvalid    = errors.New("the repository policy is invalid or declares no class")
 )

@@ -26,4 +37,5 @@ type Recorder interface {
 	PolicyLoadError(ctx context.Context, repository, reason string)
 	PolicyDivergence(ctx context.Context, repository string, n int)
+	PolicyChange(ctx context.Context, repository, class, change string)
 }

@@ -37,4 +49,6 @@ type Snapshot struct {
 	Classes     map[string]Resolved
 	Read        time.Time
+	// File is the parsed file of a valid snapshot, for the next one's structural comparison.
+	File *File
 }

@@ -46,8 +60,13 @@ type Watch struct {
 	Log     *slog.Logger
 	Now     func() time.Time
+	// Stale is how old a cut-over repository's last read may be and still decide (the fence's
+	// staleness window); 0 never ages.
+	Stale time.Duration

 	mu          sync.RWMutex
 	state       map[string]Snapshot
-	evaluations int // files parsed and validated, for the cache's test
+	valid       map[string]Snapshot            // each repository's last valid snapshot with classes
+	demoted     map[string]map[string][]string // a cut-over repository's relaxed live classes, and why
+	evaluations int                            // files parsed and validated, for the cache's test
 }

@@ -79,13 +98,27 @@ func (w *Watch) Observe(ctx context.Context, repository string, body []byte) {
 	case s.Err != nil:
 		w.Metrics.PolicyLoadError(ctx, repository, ReasonInvalid)
-	case s.HasClasses:
+	case s.HasClasses && !w.Cfg.RepositoryAuthoritative(rc):
 		w.Metrics.PolicyDivergence(ctx, repository, len(s.Divergences))
 	}
+	var changes []Change
 	w.mu.Lock()
 	if w.state == nil {
-		w.state = map[string]Snapshot{}
+		w.state, w.valid, w.demoted = map[string]Snapshot{}, map[string]Snapshot{}, map[string]map[string][]string{}
 	}
 	w.state[key] = s
+	if s.Err == nil && s.HasClasses {
+		if last, ok := w.valid[key]; ok && last.Hash != s.Hash && w.Cfg.RepositoryAuthoritative(rc) {
+			changes = w.demote(key, last, s)
+		}
+		w.valid[key] = s
+	}
 	w.mu.Unlock()
+	for _, c := range changes {
+		w.Metrics.PolicyChange(ctx, repository, c.Class, c.Kind)
+		if c.Kind == KindRelaxation {
+			w.log().Warn("repository merge policy relaxed: the class runs in shadow", "repository", repository,
+				"class", c.Class, "hash", s.Hash, "why", c.Why)
+		}
+	}
 	if !seen || prev.Hash != s.Hash {
 		w.log().Info("repository merge policy read", "repository", repository, "hash", s.Hash,
@@ -109,5 +142,8 @@ func (w *Watch) evaluate(rc *config.Repository, hash string, body []byte) Snapsh
 		return s
 	}
-	s.Divergences = Compare(rc, f, w.Cfg)
+	s.File = f
+	if !w.Cfg.RepositoryAuthoritative(rc) { // a cut-over repository has no central classes to compare with
+		s.Divergences = Compare(rc, f, w.Cfg)
+	}
 	s.Classes = map[string]Resolved{}
 	for name, p := range f.Classes {
@@ -136,4 +172,87 @@ func (w *Watch) Snapshot(repository string) (Snapshot, bool) {
 }

+// demote compares a cut-over repository's new valid file with its last (MP8), under w.mu: a
+// relaxation of a class the new file declares live runs that class in shadow until the process
+// restarts. It returns the changes that are not unchanged, for the caller to count. A comparison
+// that fails is a relaxation of every live class: uncertainty fails toward shadow.
+func (w *Watch) demote(key string, last, next Snapshot) []Change {
+	changes, err := Structural(last.File, next.File, w.Cfg)
+	if err != nil {
+		changes = nil
+		for name := range next.Classes {
+			changes = append(changes, Change{Class: name, Kind: KindRelaxation, Why: []string{err.Error()}})
+		}
+	}
+	var out []Change
+	for _, c := range changes {
+		if c.Kind == KindUnchanged {
+			continue
+		}
+		out = append(out, c)
+		if c.Kind == KindRelaxation && next.Classes[c.Class].Class.Live {
+			if w.demoted[key] == nil {
+				w.demoted[key] = map[string][]string{}
+			}
+			w.demoted[key][c.Class] = c.Why
+		}
+	}
+	return out
+}
+
+// Authority is a cut-over repository's policy as the gate decides on it (stage 4): its current
+// snapshot, fresh within Stale, valid and declaring classes, with each relaxed class in shadow.
+// Anything else is an error the gate pauses on (MP13): ErrUnreadable, ErrStale or ErrInvalid.
+func (w *Watch) Authority(repository string) (Snapshot, error) {
+	key := strings.ToLower(repository)
+	w.mu.RLock()
+	defer w.mu.RUnlock()
+	s, ok := w.state[key]
+	switch {
+	case !ok:
+		return Snapshot{}, ErrUnreadable
+	case w.Stale > 0 && w.now().Sub(s.Read) >= w.Stale:
+		return s, ErrStale
+	case s.Err != nil || !s.HasClasses:
+		return s, ErrInvalid
+	}
+	s.Classes = w.shadowed(s.Classes, w.demoted[key], false)
+	return s, nil
+}
+
+// Classes are a cut-over repository's classes for every reader but the gate's decision
+// (config.SetClassSource): the last valid file's, with relaxed classes in shadow, and every live
+// class in shadow while the current file gives no authority, so nothing merges on it.
+func (w *Watch) Classes(repository string) (map[string]config.Class, bool) {
+	_, authErr := w.Authority(repository)
+	key := strings.ToLower(repository)
+	w.mu.RLock()
+	defer w.mu.RUnlock()
+	s, ok := w.valid[key]
+	if !ok {
+		return nil, false
+	}
+	out := map[string]config.Class{}
+	for name, r := range w.shadowed(s.Classes, w.demoted[key], authErr != nil) {
+		out[name] = r.Class
+	}
+	return out, true
+}
+
+// shadowed is classes with each demoted class, or every class when all is set, live no more:
+// a live class runs in shadow, every variant of it.
+func (w *Watch) shadowed(classes map[string]Resolved, demoted map[string][]string, all bool) map[string]Resolved {
+	if !all && len(demoted) == 0 {
+		return classes
+	}
+	out := make(map[string]Resolved, len(classes))
+	for name, r := range classes {
+		if _, d := demoted[name]; all || d {
+			r = r.inShadow()
+		}
+		out[name] = r
+	}
+	return out
+}
+
 func (w *Watch) listed(repository string) *config.Repository {
 	for _, r := range w.Cfg.Repos() {
diff --git a/internal/factory/mergepolicy/watch_test.go b/internal/factory/mergepolicy/watch_test.go
index 13596c50..db6a14ad 100644
--- a/internal/factory/mergepolicy/watch_test.go
+++ b/internal/factory/mergepolicy/watch_test.go
@@ -13,4 +13,5 @@ type rec struct {
 	reasons []string
 	gauge   []int
+	changes []string
 }
```

`Classes` is called through `Config.Repos`, and `Observe` calls `Repos` (through `listed`) before it takes `w.mu`: no path calls `Repos` under the Watch's lock.

- [ ] **Step 4: Run them to verify they pass**, same command, `-race` on: `ok`.

### Task 3: The counters

**Files:**
- Modify: `internal/factory/fmetrics/fmetrics.go:180`, `:433`, `:577`
- Test: `internal/factory/fmetrics/repository_test.go` (`TestPolicyMetricsAreBounded`)

**Interfaces:**
- Produces: `(*Set).PolicyChange(ctx, repository, class, change string)` (`tightening`, `relaxation`); `PolicyLoadError` accepts `unreadable`, `stale`

- [ ] **Step 1: Write the failing test**

```diff
diff --git a/internal/factory/fmetrics/repository_test.go b/internal/factory/fmetrics/repository_test.go
index a4548453..d2337d31 100644
--- a/internal/factory/fmetrics/repository_test.go
+++ b/internal/factory/fmetrics/repository_test.go
@@ -83,4 +83,7 @@ func TestPolicyMetricsAreBounded(t *testing.T) {
 	s.PolicyDualDecision(t.Context(), "Smana/a", "docs-links", "unexplained")
 	s.PolicyDualDecision(t.Context(), "Smana/a", "docs-links", "not-an-agreement")
+	s.PolicyLoadError(t.Context(), "Smana/a", "stale")
+	s.PolicyChange(t.Context(), "Smana/a", "docs-links", "relaxation")
+	s.PolicyChange(t.Context(), "Smana/a", "docs-links", "not-a-change")
 	out := scrape()
 	for _, want := range []string{
@@ -88,4 +91,6 @@ func TestPolicyMetricsAreBounded(t *testing.T) {
 		`maku_factory_policy_central_divergence{repository="Smana/a"`,
 		`maku_factory_policy_dual_decisions_total{agreement="unexplained",class="docs-links",repository="Smana/a"`,
+		`maku_factory_policy_load_errors_total{reason="stale",repository="Smana/a"`,
+		`maku_factory_policy_changes_total{change="relaxation",class="docs-links",repository="Smana/a"`,
 	} {
 		if !strings.Contains(out, want) {
@@ -93,5 +98,5 @@ func TestPolicyMetricsAreBounded(t *testing.T) {
 		}
 	}
-	if strings.Contains(out, "not-a-reason") || strings.Contains(out, "not-an-agreement") {
+	if strings.Contains(out, "not-a-reason") || strings.Contains(out, "not-an-agreement") || strings.Contains(out, "not-a-change") {
 		t.Fatal("a reason outside the list")
 	}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 -run TestPolicyMetricsAreBounded ./internal/factory/fmetrics/`
Expected: FAIL to build: `s.PolicyChange undefined`.

- [ ] **Step 3: Implement**

```diff
diff --git a/internal/factory/fmetrics/fmetrics.go b/internal/factory/fmetrics/fmetrics.go
index e5530333..3a55c689 100644
--- a/internal/factory/fmetrics/fmetrics.go
+++ b/internal/factory/fmetrics/fmetrics.go
@@ -179,4 +179,5 @@ type Set struct {
 	policyDivergence     metric.Int64Gauge
 	policyDual           metric.Int64Counter
+	policyChanges        metric.Int64Counter
 	refusals             metric.Int64Counter
 	unpricedModels       metric.Int64Counter
@@ -431,4 +432,7 @@ func New(meter metric.Meter, tasks client.Reader, ns string, leader func() bool)
 		metric.WithDescription("Classes on which a repository's merge policy differs from the central config, as last compared: 0 is equivalent. A repository never compared has no series; the value is the last comparison's."))
 	check(err)
+	s.policyChanges, err = meter.Int64Counter("agent_factory_policy_changes_total",
+		metric.WithDescription("Structural changes of a cut-over repository's merge policy, by class: tightening, or relaxation, which runs a live class in shadow (stage 4, MP8)."))
+	check(err)
 	s.policyDual, err = meter.Int64Counter("agent_factory_policy_dual_decisions_total",
 		metric.WithDescription("Merge decisions decided again under the repository's policy (stage 3), by agreement: agree, explained (the policy differs where the comparison says), unread (the diff it needed was not read), unexplained, or no_policy. Nothing is decided on it."))
@@ -575,5 +579,17 @@ func (s *Set) RepositoryOwned(ctx context.Context, repository string, owned bool
 }

-func policyLoadReasons() []string { return []string{"invalid", "guardrail_mismatch"} }
+func policyLoadReasons() []string {
+	return []string{"invalid", "guardrail_mismatch", "unreadable", "stale"}
+}
+
+// PolicyChange counts one structural change of a cut-over repository's class (stage 4, MP8);
+// a change outside the list is not counted. Promotion and demotion arrive with stage 6.
+func (s *Set) PolicyChange(ctx context.Context, repository, class, change string) {
+	if change != "tightening" && change != "relaxation" {
+		return
+	}
+	s.policyChanges.Add(ctx, 1, metric.WithAttributes(attribute.String("repository", s.repository(repository)),
+		attribute.String("class", class), attribute.String("change", change)))
+}

 // PolicyLoadError counts a failed read of repository's merge policy; a reason outside the list is
```

- [ ] **Step 4: Run it to verify it passes**, same command: `ok`.

### Task 4: The record's policy field alone

**Files:**
- Modify: `internal/factory/decision/decision.go:24-28`, `:38-40`
- Test: `internal/factory/decision/decision_test.go`

**Interfaces:**
- Consumes: `Rows.Policy` (stage 3)

- [ ] **Step 1: Write the failing test**

```diff
diff --git a/internal/factory/decision/decision_test.go b/internal/factory/decision/decision_test.go
index fb7379d7..55a2408b 100644
--- a/internal/factory/decision/decision_test.go
+++ b/internal/factory/decision/decision_test.go
@@ -60,2 +60,11 @@ func TestTheDualFieldsPrintOnlyWhenRead(t *testing.T) {
 	}
 }
+
+// Repository authority (merge policy stage 4) binds the decision to the policy that made it,
+// with nothing compared: policy= alone, before reviewer.
+func TestThePolicyPrintsAloneUnderRepositoryAuthority(t *testing.T) {
+	got := Marker("abc", "c", "arm", "", Rows{Reviewer: "none", Policy: "0123456789ab"})
+	if !strings.HasSuffix(got, " capped=- policy=0123456789ab reviewer=none -->") || strings.Contains(got, "dual=") {
+		t.Fatal(got)
+	}
+}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/decision/`
Expected: FAIL: the marker has no `policy=` without `dual=`.

- [ ] **Step 3: Implement**

```diff
diff --git a/internal/factory/decision/decision.go b/internal/factory/decision/decision.go
index ef604597..b6e96efb 100644
--- a/internal/factory/decision/decision.go
+++ b/internal/factory/decision/decision.go
@@ -25,5 +25,6 @@ type Rows struct {
 	// Policy and Dual are merge policy stage 3's dual evaluation: the first 12 hex digits of the
 	// repository policy's hash ("" when none was read) and whether its decision agreed with this
-	// one. Dual is "" with dual evaluation off, and then neither prints.
+	// one. Dual is "" with dual evaluation off, and then neither prints, unless repository
+	// authority (stage 4) decided on Policy: it then prints alone.
 	Policy, Dual string
 }
@@ -36,6 +37,9 @@ type Rows struct {
 func Marker(head, class, verdict, reason string, r Rows) string {
 	dual := ""
-	if r.Dual != "" {
+	switch {
+	case r.Dual != "":
 		dual = fmt.Sprintf(" policy=%s dual=%s", dash(r.Policy), r.Dual)
+	case r.Policy != "": // repository authority (stage 4): the policy decided, nothing compared
+		dual = " policy=" + r.Policy
 	}
 	return fmt.Sprintf("<!-- agent-factory-decision head=%s class=%s decision=%s:%s files=%s/%d lines=%s/%d shape=%s holdout=%s oracle=%s age=%s evidence=%s paused=%s capped=%s%s reviewer=%s -->",
```

- [ ] **Step 4: Run it to verify it passes; the tally still reads it**

```bash
systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/decision/
bash scripts/shadow-merge-tally_test.sh
```

Expected: `ok`, and the tally's `ok`: its regex's `.*reviewer=` spans `policy=`.

### Task 5: The gate decides on the repository's policy

**Files:**
- Create: `internal/factory/reconciler/authority.go`
- Modify: `internal/factory/reconciler/merge.go:58`, `:64`, `:137`, `:142`, `:156`, `:184`; `reconciler.go:116`, `:190`; `dual.go:61`; `reconciler_test.go` (`fakeMetrics.PolicyLoadError`)
- Modify: `internal/factory/narrate/narrate.go`, `internal/summary/waiting.go`, `internal/roomview/words.go` (the reasons' prose)
- Modify: `internal/app/factory.go:276-285`, `:309`
- Modify: `docs/factory.md`, `docs/operations.md`
- Test: `internal/factory/reconciler/authority_test.go`

**Interfaces:**
- Consumes: `DecideArmUnder`, `withShape`, `readsDiff`, `shortHash` (stages 2 and 3); `Watch.Authority`, `Watch.Classes` (Task 2); `PolicyLoadError` reasons (Task 3); `Rows.Policy` alone (Task 4)
- Produces: `Reconciler.Authority func(repository string) (mergepolicy.Snapshot, error)`; `reasonPolicyUnavailable = "policy_unavailable"`, `reasonPolicyInvalid = "policy_invalid"`; `gatePolicy`, `decideUnder(in ArmInputs, p gatePolicy) ArmDecision` — stage 5's grants plug into `withApproval`, which `decideUnder` reaches through `DecideArmUnder`

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"fmt"
	"slices"
	"strings"
	"testing"

	v1alpha1 "github.com/Smana/maku/api/factory/v1alpha1"
	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// cutOverRig is mergeRig with its repository cut over to its own policy file (stage 4): no
// central class, the switch on, and the gate's policy and every reader's classes from the
// returned snapshot and error, as mergepolicy.Watch would serve them.
func cutOverRig(t *testing.T, snap mergepolicy.Snapshot, err error) *rig {
	g := mergeRig(t, v1alpha1.PhaseAwaitingCI)
	rc := g.r.Cfg.Repos()[0]
	rc.Classes, rc.ClassAuthority = nil, config.ClassAuthorityRepository
	g.r.Cfg.Repositories, g.r.Cfg.Classes = []config.Repository{rc}, nil
	g.r.Cfg.PolicyManagement = config.PolicyManagement{Read: true, RepositoryAuthority: true}
	g.r.Cfg.SetClassSource(func(string) (map[string]config.Class, bool) {
		out := map[string]config.Class{}
		for n, r := range snap.Classes {
			out[n] = r.Class
		}
		return out, snap.Classes != nil
	})
	g.r.Authority = func(string) (mergepolicy.Snapshot, error) { return snap, err }
	g.f.SetChecks(12, green("SUCCESS"))
	return g
}

func resolvedLive(class string) mergepolicy.Resolved {
	return mergepolicy.Resolved{Class: withShape(config.Class{Live: true}, class)}
}

// Stage 4: a cut-over repository's live class merges on its own policy, and the record binds the
// decision to the policy's hash (MP12).
func TestACutOverRepositoryMergesOnItsOwnPolicy(t *testing.T) {
	g := cutOverRig(t, snapshotOf(map[string]mergepolicy.Resolved{"docs-links": resolvedLive("docs-links")}), nil)
	g.reconcile(t, "3buqdlot", 1)
	if len(g.f.Armed()) != 1 {
		t.Fatalf("armed %v", g.f.Armed())
	}
	if c := strings.Join(g.f.Comments(12), "\n"); c != "" && !strings.Contains(c, " policy=0123456789ab reviewer=") {
		t.Fatalf("%s", c)
	}
}

// A shadow class records would-arm and merges nothing; a class the file does not declare is a
// maintainer's.
func TestACutOverRepositoryShadowsOrHandsOff(t *testing.T) {
	for name, tc := range map[string]struct {
		classes map[string]mergepolicy.Resolved
		reason  string
	}{
		"shadow":     {map[string]mergepolicy.Resolved{"docs-links": {Class: withShape(config.Class{Shadow: true}, "docs-links")}}, "shadow_would_arm"},
		"undeclared": {map[string]mergepolicy.Resolved{"revert": resolvedLive("revert")}, "class_unarmed"},
	} {
		t.Run(name, func(t *testing.T) {
			g := cutOverRig(t, snapshotOf(tc.classes), nil)
			tk := g.reconcile(t, "3buqdlot", 1)
			if len(g.f.Armed()) != 0 || tk.Status.Reason != tc.reason {
				t.Fatalf("%s %s %v", tk.Status.Phase, tk.Status.Reason, g.f.Armed())
			}
			if c := strings.Join(g.f.Comments(12), "\n"); tc.reason == "shadow_would_arm" && !strings.Contains(c, " policy=0123456789ab ") {
				t.Fatalf("%s", c)
			}
		})
	}
}

// MP13, the stage 4 exit: a policy that gives no authority pauses auto-merge. Unreadable or stale
// waits for the next read, counted; invalid is a maintainer's to fix; nothing arms either way.
func TestNoAuthorityPausesAutoMerge(t *testing.T) {
	for name, tc := range map[string]struct {
		err           error
		phase, reason string
		counted       string
	}{
		"unreadable": {mergepolicy.ErrUnreadable, v1alpha1.PhaseAwaitingCI, reasonPolicyUnavailable, "policy_load unreadable"},
		"stale":      {fmt.Errorf("x: %w", mergepolicy.ErrStale), v1alpha1.PhaseAwaitingCI, reasonPolicyUnavailable, "policy_load stale"},
		"invalid":    {mergepolicy.ErrInvalid, v1alpha1.PhaseAwaitingHuman, reasonPolicyInvalid, ""},
	} {
		t.Run(name, func(t *testing.T) {
			// The last valid file armed the class: an unusable read must not keep it armed.
			g := cutOverRig(t, snapshotOf(map[string]mergepolicy.Resolved{"docs-links": resolvedLive("docs-links")}), tc.err)
			tk := g.reconcile(t, "3buqdlot", 1)
			if len(g.f.Armed()) != 0 || tk.Status.Phase != tc.phase || tk.Status.Reason != tc.reason {
				t.Fatalf("%s %s %v", tk.Status.Phase, tk.Status.Reason, g.f.Armed())
			}
			if tc.counted != "" && !slices.Contains(g.metrics.recorded, tc.counted) {
				t.Fatalf("%q", g.metrics.recorded)
			}
		})
	}
}

// The fixed base is decided first, whatever the policy: a red CI is still the fix run's, never a
// policy pause (MP3).
func TestNoAuthorityKeepsTheFixedBase(t *testing.T) {
	in := gateInputs()
	in.Checks.Runs[0].State = "FAILURE"
	if d := decideUnder(in, gatePolicy{on: true, err: mergepolicy.ErrInvalid}); d.Verdict != "ci_red" {
		t.Fatalf("%+v", d)
	}
	in = gateInputs()
	if d := decideUnder(in, gatePolicy{on: true, err: mergepolicy.ErrUnreadable}); d.Verdict != "wait" || d.Reason != reasonPolicyUnavailable {
		t.Fatalf("%+v", d)
	}
}

// A live class's requiresApproval subset asks a human under repository authority (MP9): stage 5's
// grants are the only way it arms.
func TestTheApprovalSubsetAsksAHuman(t *testing.T) {
	in := gateInputs()
	r := mergepolicy.Resolved{Class: declaredClass(), Approval: []string{`^docs/`}}
	in.Stats[0].Path = "docs/a.md"
	if d := decideUnder(in, gatePolicy{on: true, snap: snapshotOf(map[string]mergepolicy.Resolved{"dead-links": r})}); d.Reason != reasonApprovalRequired {
		t.Fatalf("%+v", d)
	}
}

// Every branch of any is a variant of the class: the gate decides on each, not on the leaves all
// declares (a reader of the config's one class would read the looser class).
func TestTheGateDecidesEveryBranch(t *testing.T) {
	in := gateInputs()
	strict, loose := declaredClass(), declaredClass()
	strict.MaxModifiedLines, loose.MaxModifiedLines = 1, 0
	r := mergepolicy.Resolved{Class: loose, Branches: []config.Class{strict}}
	in.Stats[0].Additions = 10
	if d := decideUnder(in, gatePolicy{on: true, snap: snapshotOf(map[string]mergepolicy.Resolved{"dead-links": r})}); d.Reason != "patch_too_large" {
		t.Fatalf("the branch, not the leaves: %+v", d)
	}
	if !(gatePolicy{on: true, snap: snapshotOf(map[string]mergepolicy.Resolved{"dead-links": r})}).readsDiff(nil, "dead-links") {
		t.Fatal("a branch with a cap reads the diff")
	}
}

// Off, the gate is today's: nothing is read from a policy source, and the decision and its record
// are byte for byte the central ones.
func TestRepositoryAuthorityOffIsToday(t *testing.T) {
	run := func(wire bool) (string, []string) {
		g := mergeRig(t, v1alpha1.PhaseAwaitingCI)
		g.f.SetChecks(12, green("SUCCESS"))
		if wire {
			g.r.Cfg.PolicyManagement = config.PolicyManagement{Read: true}
			g.r.Authority = func(string) (mergepolicy.Snapshot, error) {
				t.Fatal("read with the switch off")
				return mergepolicy.Snapshot{}, nil
			}
		}
		tk := g.reconcile(t, "3buqdlot", 1)
		return tk.Status.Phase + " " + tk.Status.Reason + " " + strings.Join(g.f.Comments(12), "\n"), g.f.Armed()
	}
	before, armedBefore := run(false)
	after, armedAfter := run(true)
	if before != after || !slices.Equal(armedBefore, armedAfter) {
		t.Fatalf("%q\n%q", before, after)
	}
}

// Under repository authority the class is the repository's: dual evaluation has no central
// decision to compare it with, so it is not run.
func TestDualEvaluationSkipsACutOverRepository(t *testing.T) {
	g := cutOverRig(t, snapshotOf(map[string]mergepolicy.Resolved{"docs-links": resolvedLive("docs-links")}), nil)
	g.r.Cfg.PolicyManagement.DualEvaluation = true
	g.r.Policy = func(string) (mergepolicy.Snapshot, bool) {
		t.Fatal("dual evaluation of a cut-over repository")
		return mergepolicy.Snapshot{}, false
	}
	g.reconcile(t, "3buqdlot", 1)
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 -run 'CutOver|NoAuthority|ApprovalSubset|EveryBranch|AuthorityOff|SkipsACutOver' ./internal/factory/reconciler/`
Expected: FAIL to build: `g.r.Authority undefined`, `undefined: decideUnder`, `undefined: gatePolicy`.

- [ ] **Step 3: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"errors"

	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// The reasons a cut-over repository's gate pauses on its policy (stage 4, MP13).
const (
	// reasonPolicyUnavailable: no read, or one older than the fence's window. The gate waits for
	// the next read, bounded by merge.awaitingCIFor like any wait.
	reasonPolicyUnavailable = "policy_unavailable"
	// reasonPolicyInvalid: the default branch's file is invalid or declares no class. A
	// maintainer fixes the file, or merges by hand.
	reasonPolicyInvalid = "policy_invalid"
)

// gatePolicy is a cut-over repository's policy for one pass of the gate (stage 4), read once so
// both of the pass's decisions bind to the same snapshot (MP12). on is false for every other
// repository, and for every repository with policyManagement.repositoryAuthority off.
type gatePolicy struct {
	on   bool
	snap mergepolicy.Snapshot
	err  error
}

// gatePolicy reads the task's repository's policy when the repository is cut over. Without an
// Authority source a cut-over repository has no readable policy, and pauses.
func (r *Reconciler) gatePolicy(rc *config.Repository, repository string) gatePolicy {
	if !r.Cfg.RepositoryAuthoritative(rc) {
		return gatePolicy{}
	}
	if r.Authority == nil {
		return gatePolicy{on: true, err: mergepolicy.ErrUnreadable}
	}
	snap, err := r.Authority(repository)
	return gatePolicy{on: true, snap: snap, err: err}
}

// loadError is the policy load error the gate counts for p: unreadable or stale, which only the
// gate sees; an invalid file is counted on each read (mergepolicy.Watch).
func (p gatePolicy) loadError() string {
	switch {
	case !p.on:
		return ""
	case errors.Is(p.err, mergepolicy.ErrUnreadable):
		return mergepolicy.ReasonUnreadable
	case errors.Is(p.err, mergepolicy.ErrStale):
		return mergepolicy.ReasonStale
	}
	return ""
}

// decideUnder is the gate's decision: DecideArm on the central config, or, for a cut-over
// repository, DecideArmUnder on the class its policy declares, every branch of any and its
// requiresApproval subset (one evaluator, MP16). The record binds the decision to the policy's
// hash. A policy that gives no authority pauses: the fixed base is still decided first.
func decideUnder(in ArmInputs, p gatePolicy) ArmDecision {
	if !p.on {
		return DecideArm(in)
	}
	if p.err != nil {
		return noAuthority(in, p)
	}
	var d ArmDecision
	if r, ok := p.snap.Classes[in.Task.Spec.PredictedClass]; ok {
		d = DecideArmUnder(in, r.Variants(), r.Approval)
	} else {
		d = DecideArmUnder(in, nil, nil)
	}
	d.Rows.Policy = shortHash(p.snap.Hash)
	return d
}

// noAuthority is the decision on a policy that gives no authority (MP13): the fixed base's, when
// it refuses or waits; otherwise a wait for the next read, or a maintainer for an invalid file.
// Nothing arms or shadows: human merges continue.
func noAuthority(in ArmInputs, p gatePolicy) ArmDecision {
	rc := in.Cfg.RepositoryFor(in.Task.Spec.Repository)
	rows := recordOf(in, config.Class{})
	rows.Policy = shortHash(p.snap.Hash)
	d, done := baseChecks(in, rc)
	if !done {
		d = ArmDecision{Verdict: "wait", Reason: reasonPolicyUnavailable, Matched: in.Task.Spec.PredictedClass}
		if errors.Is(p.err, mergepolicy.ErrInvalid) {
			d.Verdict, d.Reason = "human", reasonPolicyInvalid
		}
	}
	d.Rows = rows
	return withIntegrationHold(in.Integration, d)
}

// readsDiff is whether deciding the task's class reads the diff: the central class's, or every
// variant and the approval subset of the repository's.
func (p gatePolicy) readsDiff(rc *config.Repository, class string) bool {
	if !p.on {
		return rc.Classes[class].ReadsDiff(class)
	}
	r, ok := p.snap.Classes[class]
	return ok && readsDiff(r, class)
}
```

```diff
diff --git a/internal/factory/reconciler/dual.go b/internal/factory/reconciler/dual.go
index 83c16186..f33b26e5 100644
--- a/internal/factory/reconciler/dual.go
+++ b/internal/factory/reconciler/dual.go
@@ -59,5 +59,6 @@ func readsDiff(r mergepolicy.Resolved, class string) bool {
 // gate acts on: central's verdict is still the decision.
 func (r *Reconciler) dual(ctx context.Context, t *v1alpha1.Task, in ArmInputs, central ArmDecision, d *ArmDecision) {
-	if !r.Cfg.PolicyManagement.DualEvaluation || r.Policy == nil {
+	// A cut-over repository's decision is the repository's own: there is no central one to compare.
+	if !r.Cfg.PolicyManagement.DualEvaluation || r.Policy == nil || r.Cfg.RepositoryAuthoritative(r.repo(t)) {
 		return
 	}
diff --git a/internal/factory/reconciler/merge.go b/internal/factory/reconciler/merge.go
index cb7bd402..8741416a 100644
--- a/internal/factory/reconciler/merge.go
+++ b/internal/factory/reconciler/merge.go
@@ -57,4 +57,5 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 	}
 	r.countApproves(ctx, t, pr)
+	policy := r.gatePolicy(r.repo(t), t.Spec.Repository) // stage 4: one read for the pass
 	// An adopted pull request is Renovate's: a maintainer's veto is the gate's changes_requested
 	// hand-off, never a revision run.
@@ -62,5 +63,5 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		return r.revise(ctx, t, pr, rvs)
 	}
-	if adoptedTask(t) && !gateOf(r.repo(t), t.Spec.PredictedClass).Adopted() {
+	if adoptedTask(t) && (!policy.on || policy.err == nil) && !gateOf(r.repo(t), t.Spec.PredictedClass).Adopted() {
 		// The class was removed, renamed or lost its author: there is no gate to decide this pull
 		// request by, and no room to ask (an adopted Task never had one).
@@ -135,10 +136,10 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		}
 	}
-	d := DecideArm(in)
+	d := decideUnder(in, policy)
 	evaluated := d // the evaluator's own decision, before the rows read after it, for dual evaluation
 	// A maintainer's approval arms on a human's judgement of the head, never on its diff: reading it
 	// again could only hand the approved head off for the diff the approval already covered (AM1).
 	approved := d.Verdict == "arm" && d.Reason == "maintainer_approved"
-	if !approved && (d.Verdict == "arm" || d.Verdict == "shadow") && (r.repo(t).Classes[t.Spec.PredictedClass].ReadsDiff(t.Spec.PredictedClass) ||
+	if !approved && (d.Verdict == "arm" || d.Verdict == "shadow") && (policy.readsDiff(r.repo(t), t.Spec.PredictedClass) ||
 		r.Cfg.SteeringOn()) {
 		// The diff is read late (steering on: always, to refuse a changed note): only a decision that would arm or shadow a class with a condition
@@ -154,5 +155,5 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		default:
 			in.Files.Base, in.Files.Head, in.Stats, in.DiffRead = diff.Base, diff.Head, diff.Files, true
-			d = DecideArm(in)
+			d = decideUnder(in, policy)
 			evaluated = d
 		}
@@ -182,4 +183,7 @@ func (r *Reconciler) awaitingCI(ctx context.Context, t *v1alpha1.Task) error {
 		r.postGateStatus(ctx, t, pr.HeadSHA, checks, d)
 	}
+	if reason := policy.loadError(); reason != "" {
+		record(ctx, func(ctx context.Context) { r.Metrics.PolicyLoadError(ctx, t.Spec.Repository, reason) })
+	}
 	if d.Verdict != "wait" {
 		class, verdict, reason := t.Spec.PredictedClass, d.Verdict, cmp.Or(d.Reason, "armed")
diff --git a/internal/factory/reconciler/reconciler.go b/internal/factory/reconciler/reconciler.go
index ab3b64ef..c30a90b3 100644
--- a/internal/factory/reconciler/reconciler.go
+++ b/internal/factory/reconciler/reconciler.go
@@ -115,4 +115,5 @@ type metrics interface {
 	MergeDecision(ctx context.Context, class, verdict, reason string)
 	PolicyDualDecision(ctx context.Context, repository, class, agreement string)
+	PolicyLoadError(ctx context.Context, repository, reason string)
 	ClassPaused(ctx context.Context, repository, class string, paused bool)
 	Resumed(ctx context.Context, reason string)
@@ -189,5 +190,9 @@ type Reconciler struct {
 	// nothing on it (stage 3). nil: no dual evaluation.
 	Policy func(repository string) (mergepolicy.Snapshot, bool)
-	Runs   RunClient
+	// Authority is a cut-over repository's policy as the gate decides on it (merge policy stage
+	// 4, mergepolicy.Watch.Authority): read once per pass, never cached here. nil: a cut-over
+	// repository's policy is unreadable, and its auto-merge pauses.
+	Authority func(repository string) (mergepolicy.Snapshot, error)
+	Runs      RunClient
 	// Kind is the runs kind, required: SetupWithManager watches its AgentRuns.
 	Kind    runwatch.Kind
diff --git a/internal/factory/reconciler/reconciler_test.go b/internal/factory/reconciler/reconciler_test.go
index 6a5e8f47..510a1a84 100644
--- a/internal/factory/reconciler/reconciler_test.go
+++ b/internal/factory/reconciler/reconciler_test.go
@@ -327,4 +327,8 @@ func (m *fakeMetrics) MergeDecision(_ context.Context, class, verdict, reason st
 	m.add("merge_decision " + class + " " + verdict + " " + reason)
 }
+func (m *fakeMetrics) PolicyLoadError(_ context.Context, _, reason string) {
+	m.add("policy_load " + reason)
+}
+
 func (m *fakeMetrics) PolicyDualDecision(_ context.Context, _, class, agreement string) {
 	m.add("policy_dual " + class + " " + agreement)
```

The prose of the three reasons a cut-over repository's gate can now return:

```diff
diff --git a/internal/factory/narrate/narrate.go b/internal/factory/narrate/narrate.go
index f170b6c3..34c8b0e1 100644
--- a/internal/factory/narrate/narrate.go
+++ b/internal/factory/narrate/narrate.go
@@ -288,4 +288,7 @@ func reasons() map[string]string {
 		"class_mismatch":              "the diff is not the class the triage predicted",
 		"class_unarmed":               "the factory does not merge this class: a maintainer reviews and merges it",
+		"policy_unavailable":          "the repository's merge policy could not be read recently, so auto-merge waits for the next read",
+		"policy_invalid":              "the repository's merge policy on its default branch is invalid, so auto-merge is paused: a maintainer fixes .github/agent-factory.yaml or merges it",
+		"approval_required":           "it changes a file its class asks a maintainer to approve",
 		"file_not_allowed":            "it changes a file outside its class's allowed files",
 		"file_protected":              "it changes a file its class protects",
diff --git a/internal/roomview/words.go b/internal/roomview/words.go
index e683b460..b1735b6f 100644
--- a/internal/roomview/words.go
+++ b/internal/roomview/words.go
@@ -106,4 +106,7 @@ var reasonPhrases = map[string]string{
 	"stalled":                   "the run made no commit",
 	"class_unarmed":             "a maintainer merges this class",
+	"policy_unavailable":        "waiting to read the merge policy",
+	"policy_invalid":            "the merge policy is invalid",
+	"approval_required":         "a maintainer approves this change",
 	"steering_path":             "it changes a steering note",
 	"stuck":                     "the run showed no activity",
diff --git a/internal/summary/waiting.go b/internal/summary/waiting.go
index e27edbef..6f5fca3b 100644
--- a/internal/summary/waiting.go
+++ b/internal/summary/waiting.go
@@ -168,4 +168,7 @@ func reasons() map[string]string {
 		"gate_path":                 "it touches a gate path, so an agent can never merge it",
 		"class_unarmed":             "the factory does not merge this class: a maintainer reviews and merges it",
+		"policy_unavailable":        "the repository's merge policy could not be read recently, so auto-merge waits",
+		"policy_invalid":            "the repository's merge policy is invalid, so auto-merge is paused",
+		"approval_required":         "it changes a file its class asks a maintainer to approve",
 		"steering_path":             "it changes a steering note, which only a maintainer on the default branch may do",
 		"verdict_stale":             "the reviewer's approval was not for the pull request's current head",
```

The wiring, with the Watch aging reads at the fence's window:

```diff
diff --git a/internal/app/factory.go b/internal/app/factory.go
index 26695c71..44a3e0f4 100644
--- a/internal/app/factory.go
+++ b/internal/app/factory.go
@@ -275,12 +275,18 @@ func runFactory(ctx context.Context, log *slog.Logger, getenv func(string) strin
 		Every: fenceEvery, Stale: fenceStale, Now: time.Now, OnState: m.RepositoryOwned, Log: log}
 	// Stages 1 and 3 (merge policy): observed and compared, then each merge decision decided again
-	// under it; neither decides anything.
+	// under it; neither decides anything. Stage 4: a cut-over repository is decided on it, and
+	// every reader reads its classes from it, aged out at the fence's own window.
 	var snapshots func(string) (mergepolicy.Snapshot, bool)
+	var authority func(string) (mergepolicy.Snapshot, error)
 	if cfg.PolicyManagement.Read {
-		w := &mergepolicy.Watch{Cfg: cfg, Metrics: m, Log: log, Now: time.Now}
+		w := &mergepolicy.Watch{Cfg: cfg, Metrics: m, Log: log, Now: time.Now, Stale: fenceStale}
 		fenced.OnFile = w.Observe
 		if cfg.PolicyManagement.DualEvaluation {
 			snapshots = w.Snapshot
 		}
+		if cfg.PolicyManagement.RepositoryAuthority {
+			cfg.SetClassSource(w.Classes)
+			authority = w.Authority
+		}
 	}
 	costs := &meter.Costs{} // the meter writes each run's cost, the reconciler sums a task's
@@ -307,5 +313,5 @@ func runFactory(ctx context.Context, log *slog.Logger, getenv func(string) strin
 	}
 	rec := &reconciler.Reconciler{Kind: cfg.Runs, Client: mgr.GetClient(), Ledger: live, Namespace: ns, Cfg: cfg, Clients: conns.task, Owned: fenced.Owned,
-		Policy: snapshots, CanWrite: perms.CanWrite, Runs: rc, Rooms: broker,
+		Policy: snapshots, Authority: authority, CanWrite: perms.CanWrite, Runs: rc, Rooms: broker,
 		Triage: triage.Classify{Cfg: cfg, C: c7,
 			Clients: conns.class},
```

And the docs:

```diff
diff --git a/docs/factory.md b/docs/factory.md
index d535dc53..6e32d8f6 100644
--- a/docs/factory.md
+++ b/docs/factory.md
@@ -933,5 +933,5 @@ or `ci_cancelled` starts a fix run or a re-run instead, and posts no record:
 | `evidence=` | `ok`, or the refusal's reason |
 | `paused=`, `capped=` | What the breaker and the day's count said, whether or not they stopped the decision (AM4). `-` when the decision stopped at a row before the gate read them |
-| `policy=`, `dual=` | Only with `policyManagement.dualEvaluation`: the first 12 hex digits of the repository policy's hash (`-` when none was read) and how its decision compared, as `maku_factory_policy_dual_decisions_total` counts it |
+| `policy=`, `dual=` | Only with `policyManagement.dualEvaluation`: the first 12 hex digits of the repository policy's hash (`-` when none was read) and how its decision compared, as `maku_factory_policy_dual_decisions_total` counts it. For a cut-over repository, `policy=` alone: the hash of the policy that decided |
 | `reviewer=` | The reviewer run's served models joined with `+`; `none` when the class has no reviewer run |

@@ -1477,4 +1477,5 @@ human-authored pull request changes it. Source: `internal/factory/config/config.
 | `policyManagement.simulation` | `true` lets `maku policy simulate` (a policy file decided on decision fixtures by the gate's own evaluator) and `maku policy diff` (tightening or relaxation, class by class) run against this config. Offline; turned off when the simulator disagrees with the gate | `false` |
 | `policyManagement.dualEvaluation` | `true` decides each merge decision again under the repository's policy as `read` last observed it, counts the agreement and writes it into the decision record. Needs `read`. Stage 3 decides nothing: merge authority stays central | `false` |
+| `policyManagement.repositoryAuthority` | `true` lets a repository whose entry sets `classAuthority: repository` be decided on its own `.github/agent-factory.yaml`: the gate decides on its classes (every `any` branch, the `requiresApproval` subset asking a maintainer), and every other reader (triage, intake, schedules, the monitor) reads them. The entry declares no central `classes` (one authoritative source, MP15). A file not yet read or older than the fence's window waits (`policy_unavailable`); an invalid one hands off (`policy_invalid`); both pause auto-merge while human merges continue. A relaxation of a live class runs it in shadow. Needs `read`. Rollback: restore the repository's exported central classes and drop `classAuthority` | `false` |

 Each `repositories` entry:
diff --git a/docs/operations.md b/docs/operations.md
index 98f85be6..c9b31110 100644
--- a/docs/operations.md
+++ b/docs/operations.md
@@ -274,6 +274,7 @@ absent rather than 0.
 | `maku_factory_trace_export_abandoned_total` | counter | — | Task spans given up after the collector refused them for a day |
 | `maku_factory_repository_owned` | gauge | `repository` | 1 while the repository's `.github/agent-factory.yaml` names this factory (`factory` in the config), per replica; 0 means no intake, schedules, API runs or merges there |
-| `maku_factory_policy_load_errors_total` | counter | `repository`, `reason` | Reads of a repository's merge policy (`classes` in its `.github/agent-factory.yaml`) that failed: `invalid`, or `guardrail_mismatch` (over the central config's guardrails). Counted at every read, so a rate shows it is still bad. Stage 1 only compares: the gate still reads the central config |
+| `maku_factory_policy_load_errors_total` | counter | `repository`, `reason` | Reads of a repository's merge policy (`classes` in its `.github/agent-factory.yaml`) that failed: `invalid`, or `guardrail_mismatch` (over the central config's guardrails), counted at every read, so a rate shows it is still bad; and, for a cut-over repository only, `unreadable` (no read yet) or `stale` (older than the fence's 15-minute window), counted at each gate pass that pauses on it |
 | `maku_factory_policy_central_divergence` | gauge | `repository` | Classes on which the repository's merge policy differs from the central config, as last read; 0 is equivalent. A repository never compared has no series; after a failed read or a removed policy the gauge keeps its last compared value until the process restarts, so stage 1's exit reads it together with `maku_factory_policy_load_errors_total`: divergence 0 and no load errors |
+| `maku_factory_policy_changes_total` | counter | `repository`, `class`, `change` | A cut-over repository's (`classAuthority: repository`) policy file changed a class: `tightening`, or `relaxation`, which runs a live class in shadow until the factory restarts (MP8). A relaxation also logs `repository merge policy relaxed` with why |
 | `maku_factory_policy_dual_decisions_total` | counter | `repository`, `class`, `agreement` | With `policyManagement.dualEvaluation`, each merge decision the gate acts on, decided again under the repository's policy: `agree`; `explained`, a difference on a class `maku_factory_policy_central_divergence` already counts; `unread`, the repository's decision needed the diff the central one did not read; `unexplained`; `no_policy`. Stage 3 exits after a week with no `unexplained`. Nothing is decided on it; the decision record carries `policy=<hash> dual=<agreement>` |
 | `maku_factory_admission_refusals_total` | counter | `repository`, `reason`, `principal` | Run requests refused on their repository: `repository_differs_from_the_room`, `repository_differs_from_the_branch`, `repository_permission`, `repository_not_owned`; and `person_budget_exhausted`, an API run or a label refused on its person's day ([per-person caps](factory.md#per-person-caps)) |
```

- [ ] **Step 4: Run the packages, then the gate**

```bash
systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/factory/... ./internal/app/ ./internal/summary/ ./internal/roomview/
systemd-run --user --scope -q -p MemoryMax=6G task check
```

Expected: PASS; `task check` exits 0.

- [ ] **Step 5: Commit**

```bash
git add internal docs
git commit -m "feat(factory): repository authority for a cut-over repository's merge classes, behind policyManagement.repositoryAuthority"
```

### Task 6: The stage 4 cutover (live, after stage 3's exit)

- [ ] **Step 1: Check the preconditions.** Stage 3's week passed with zero `unexplained` for `Smana/cloud-native-ref`; `maku_factory_policy_central_divergence{repository="Smana/cloud-native-ref"}` is 0; the Maku release holding this plan is pinned.
- [ ] **Step 2: Export the rollback.** Before the cutover, `maku policy export --config <the rendered central config> --repository Smana/cloud-native-ref` (stage 1) into the cutover PR's description: the central classes it removes, verbatim; `maku policy check` of the canary's file against the same config prints `equivalent`.
- [ ] **Step 3: Cut over, one PR here.** `policyManagement: {read: true, dualEvaluation: true, repositoryAuthority: true}`; the cloud-native-ref entry gains `classAuthority: repository` and loses its `classes` block. The owner merges it.
- [ ] **Step 4: Prove fail-closed live.** With the factory on the new config: `maku_factory_policy_load_errors_total{repository="Smana/cloud-native-ref"}` has no `unreadable`/`stale`/`invalid` increase; the next decision's record carries `policy=` and the canary file's hash prefix; one shadow decision and (if a live class fires) one merge match what stage 3's `agree` predicted. The fail-closed drill stays offline (an invalid default-branch file would pause the canary): `TestNoAuthorityPausesAutoMerge` and `TestAuthority` are its proof, cited by test name and `task check` exit code.
- [ ] **Step 5: Record the result** in `docs/runbooks/agent-factory/results-merge-policy-stage-4-<date>.md`: the config PR, the record lines, the counters. Rollback: revert the config PR (the exported classes return and `classAuthority` is dropped). Then ai-native-ref follows, only after the canary passes (MP19).

---

## Out of scope: stages 5 and 6

| Stage | What remains | Where it starts |
|---|---|---|
| 5 | Grants inside `withApproval` for a live class's subset, their store and lifecycle; the restart-durable record of a demotion | [The stage 5 plan](2026-11-08-merge-policy-stage-5-approval-memory-plan.md) |
| 6 | Evidence, promotion requests and the settings routes; promotion clears a demotion | [The stage 6 plan](2026-11-08-merge-policy-stage-6-promotion-plan.md) |

## Self-review

- **Coverage:** the spec's stage 4 row (repository YAML has merge authority; invalid or unreadable policy pauses auto-merge fail-closed) is Tasks 1, 2 and 5; MP8's structural return to shadow is Task 2 (D6); MP12's binding is D7 and Task 4; MP13 is `noAuthority`; MP15 is Task 1; MP16 is `decideUnder`; the exit is Task 6.
- **Placeholders:** none.
- **Names:** `RepositoryAuthority`, `ClassAuthority`, `RepositoryAuthoritative`, `SetClassSource`, `Authority`, `Classes`, `ErrUnreadable`/`ErrStale`/`ErrInvalid`, `PolicyChange`, `gatePolicy`, `decideUnder`, `noAuthority`, `reasonPolicyUnavailable`, `reasonPolicyInvalid` are consistent across tasks.
