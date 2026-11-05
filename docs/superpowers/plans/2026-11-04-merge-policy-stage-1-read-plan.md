# Merge policy self-service, stages 0 and 1 (read and import) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A factory can read, validate and compare a repository's merge classes from `.github/agent-factory.yaml`, behind `policyManagement.read`, with the central config still the only merge authority.

**Architecture:** A new pure package, `internal/factory/mergepolicy`, parses the repository file strictly, resolves each class to the existing `config.Class`, and compares it with the central class. The fence keeps deciding ownership alone and hands its file to an observer, so no second GitHub read and no new runnable exist. Nothing in the gate, the reconciler or the store changes.

**Tech Stack:** Go (Maku), `sigs.k8s.io/yaml`, OpenTelemetry metrics through `internal/factory/fmetrics`; Flux-rendered Helm values in this repository; YAML in cloud-native-ref.

**Spec:** [`docs/superpowers/specs/2026-11-04-merge-policy-self-service-design.md`](../specs/2026-11-04-merge-policy-self-service-design.md)

**Read against:** Maku `origin/main` `9a60f0eb`, which adds one commit to the spec's `844d2a0a`. Nothing in this plan has been compiled yet: treat the code as the design, and let the failing test decide the details.

## Global Constraints

- Merge authority stays central through stage 1: no file under `internal/factory/reconciler/`, `internal/factory/intake/` or `internal/factory/triage/` changes.
- `policyManagement.read` defaults to off. Off, no behaviour changes except the fence accepting a `classes` key.
- The closed vocabulary is `allowedFiles`, `protectedFiles` (only under `deny`), `changedFiles` (only under `requiresApproval`), `modifyOnly`, `maxPatchFiles`, `maxModifiedLines`, `diffShape`, `holdoutChecks`, `releaseAgeCheck`, `oracle`, `companionFiles`, `requiredLabel`. Unknown names fail strict decoding.
- `factory:` stays the ownership fence. Invalid class policy never changes who owns a repository (MP13).
- Every repository policy declares `docs-links` and `revert`; `review` is implicit and is never declared.
- A harness profile comes from the central list; a class cannot invent one.
- Metric labels stay bounded: repository through `s.repository()`, reason from a closed list (MP18).
- Maku: `task check` exits 0 before every commit; each Go file starts with the SPDX line; conventional commits in English, no trailers.
- This machine: run tests as `ulimit -v 16000000; timeout 600 go test -p 1 <packages>`, at most two test-running agents at once. Never override `HOME`.

## Rulings this plan takes from reading the code

| # | The spec says | The code says | This plan |
|---|---|---|---|
| R1 | The resolution flowchart checks breaker and caps before the class mode | `reconciler/arm.go:185-189` (AM4): a shadow decision records `Paused` and `Capped` and nothing blocks it, and the spec says shadow decisions carry forward | Keep AM4. Stage 1 does not touch the gate; the evaluator plan moves the spec's chart to mode-aware caps |
| R2 | `mode: off`, and `loop: off` in a profile | `sigs.k8s.io/yaml` reads a bare `off` as `false`, which is why `config.ScopeMode` has its own `UnmarshalJSON` | `Mode` and `LoopRef` read `false` as `off` the same way |
| R3 | The fence file "becomes the repository class policy file" | `fence.Parse` refuses unknown keys, and refusal means not owned: no intake, runs or merges | Task 1 must be released and pinned on every factory **before** any repository adds `classes`. Task 10 is gated on it |
| R4 | Regexes are "guarded against catastrophic backtracking" | Go's and policy-bot's `regexp` are RE2, linear by construction | Bound length and count only |
| R5 | `conditions.any` | The gate reads a flat `config.Class`, and policy-bot's `if` is a conjunction | `any` stays an unknown key here. It needs the evaluator and one policy-bot rule per branch, so it lands with stage 2 |
| R6 | Guardrails include a breaker floor, grant lifetime and promotion evidence | The repository schema has no breaker field; grants and promotion do not exist yet | Stage 1's guardrails hold protected paths, mandatory checks and the three caps. The others arrive with the plan that reads them |

## The program

Each plan is written when its predecessor has merged, against the code as it then stands.

| Plan | Stages | Delivers | Blocked on |
|---|---|---|---|
| **This one** | 0, 1 | Strict parser, profiles, guardrails, export, comparison, observer, CLI, canary file | The spec's review |
| 2 | 2 | Structural relaxation diff, one evaluator with `any`, snapshots table, internal simulation API, conformance fixtures | Plan 1 |
| 3 | 3 | Dual evaluation on every real decision, divergence evidence | Plan 2 |
| 4 | 4 | Repository authority and fail-closed pause: the 24 lines reading `Classes` across 11 files outside `config`, schedules naming a class a repository can delete, per-repository loops (`Config.Loops` is global today) | Plan 3, one week without unexplained divergence |
| 5 | 5 | Grant tables, broker API, `requiresApproval` in the gate, approval-memory UI | Plan 4 |
| 6 | 6 | Settings UI, editor, promotion workflow, class templates | Plan 4, the two checks under Q1 |

---

### Task 1: The fence accepts a `classes` key and hands over its file

**Files:**
- Modify: `internal/factory/fence/fence.go`
- Test: `internal/factory/fence/fence_test.go`

**Interfaces:**
- Produces: `Fence.OnFile func(ctx context.Context, repository string, body []byte)`, called after a successful read of a file that names this factory.

- [ ] **Step 1: Write the failing tests**

Add these rows to `TestParse`'s table, keeping `"an unknown key"` as it is:

```go
"classes beside factory": {"factory: aws-0\nclasses: {docs-links: {mode: live}}\n", "aws-0", true},
"invalid classes still own": {"factory: aws-0\nclasses: [not, a, map]\n", "aws-0", true},
"classes without factory": {"classes: {}\n", "", false},
```

Add this test:

```go
// The fence decides ownership alone (MP13): a class policy it cannot read is the observer's
// problem, and it reaches the observer only from a repository this factory owns.
func TestRefreshHandsTheOwnedFileToOnFile(t *testing.T) {
	fs := &files{by: map[string]file{
		"o/mine":   {body: "factory: aws-0\nclasses: {}\n", found: true},
		"o/theirs": {body: "factory: gcp-0\n", found: true},
		"o/broken": {err: errors.New("github down")},
	}}
	var got []string
	f := &Fence{Name: "aws-0", Read: fs.read, Repositories: []string{"o/mine", "o/theirs", "o/broken"},
		Stale: time.Hour, Now: time.Now,
		OnFile: func(_ context.Context, repo string, body []byte) { got = append(got, repo+"="+string(body)) }}
	if err := f.Refresh(t.Context()); err == nil {
		t.Fatal("the failed read is reported")
	}
	if want := []string{"o/mine=factory: aws-0\nclasses: {}\n"}; !slices.Equal(got, want) {
		t.Fatalf("got %q, want %q", got, want)
	}
}
```

Add `"slices"` to the test's imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `go test -p 1 ./internal/factory/fence/`
Expected: FAIL: the `classes` rows read as not owned, and `OnFile` is undefined.

- [ ] **Step 3: Implement**

In `Parse`, decode `classes` without reading it:

```go
var f struct {
	Factory string `json:"factory"`
	// Classes is the repository's merge policy (mergepolicy), which never decides ownership: a
	// class this factory cannot read pauses that class's automation, not the repository's intake.
	Classes json.RawMessage `json:"classes"`
}
```

Add the field beside `OnState`:

```go
// OnFile hears the fence file of a repository this factory owns, after each successful read.
OnFile func(ctx context.Context, repository string, body []byte)
```

In `Refresh`, after the state is stored in the success branch:

```go
if f.OnFile != nil && owner == f.Name {
	f.OnFile(ctx, repo, body)
}
```

Replace `Parse`'s doc comment with: `Parse reads a fence file's ownership: factory, and a classes key it does not read. Any other key is an error, and the caller treats the repository as not owned.` Update the two error strings only if a test requires it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `go test -p 1 ./internal/factory/fence/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/factory/fence
git commit -m "feat(factory): the fence file may carry classes, and the fence hands it to an observer"
```

### Task 2: Harness profiles, guardrails and the flag in the central config

**Files:**
- Create: `internal/factory/config/mergepolicy.go`
- Modify: `internal/factory/config/config.go` (the `Config` struct, `Duration`, `Validate`)
- Modify: `internal/factory/config/classes.go` (export the class check)
- Modify: `docs/factory.md` (the config file section)
- Test: `internal/factory/config/mergepolicy_test.go`

**Interfaces:**
- Produces:
  - `config.HarnessProfile{Template, Tier string; Checks, TestFirst bool; Loop LoopRef}`
  - `config.MergeGuardrails{ProtectedFiles, MandatoryChecks []string; MaxPatchFiles, MaxModifiedLines, MaxPerDay int}`
  - `config.PolicyManagement{Read bool}`
  - `Config.HarnessProfiles`, `Config.MergeGuardrails`, `Config.PolicyManagement`
  - `config.ValidateClass(name string, cl Class, bad func(string, ...any))`
  - `config.TemplateNone = "none"`
  - `Duration.MarshalJSON`

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package config

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"
)

func policyProblems(c *Config) string {
	var out []string
	c.validateMergePolicy(func(f string, a ...any) { out = append(out, fmt.Sprintf(f, a...)) })
	return strings.Join(out, "\n")
}

func TestHarnessProfilesAndGuardrailsValidate(t *testing.T) {
	loops := map[string]Loop{"docs": {Judge: NoJudge}}
	for name, tc := range map[string]struct {
		cfg  Config
		want string
	}{
		"none is fine":     {Config{}, ""},
		"a plain profile":  {Config{HarnessProfiles: map[string]HarnessProfile{"plain": {}}}, ""},
		"a full profile":   {Config{Loops: loops, HarnessProfiles: map[string]HarnessProfile{"p": {Template: "solo", Tier: "light", Checks: true, TestFirst: true, Loop: "docs"}}}, ""},
		"adopted":          {Config{HarnessProfiles: map[string]HarnessProfile{"a": {Template: TemplateNone}}}, ""},
		"bad name":         {Config{HarnessProfiles: map[string]HarnessProfile{"Not_A_Name": {}}}, "is not a profile name"},
		"bad template":     {Config{HarnessProfiles: map[string]HarnessProfile{"p": {Template: "duo"}}}, "template"},
		"bad tier":         {Config{HarnessProfiles: map[string]HarnessProfile{"p": {Tier: "huge"}}}, "tier"},
		"unknown loop":     {Config{HarnessProfiles: map[string]HarnessProfile{"p": {Loop: "nope"}}}, "loop"},
		"testFirst alone":  {Config{HarnessProfiles: map[string]HarnessProfile{"p": {TestFirst: true}}}, "testFirst needs checks"},
		"none with checks": {Config{HarnessProfiles: map[string]HarnessProfile{"p": {Template: TemplateNone, Checks: true}}}, "runs nothing"},
		"negative cap":     {Config{MergeGuardrails: MergeGuardrails{MaxPerDay: -1}}, "maxPerDay"},
		"bad protected":    {Config{MergeGuardrails: MergeGuardrails{ProtectedFiles: []string{"("}}}, "protectedFiles"},
		"blank check":      {Config{MergeGuardrails: MergeGuardrails{MandatoryChecks: []string{""}}}, "mandatoryChecks"},
	} {
		t.Run(name, func(t *testing.T) {
			got := policyProblems(&tc.cfg)
			if (tc.want == "") != (got == "") || !strings.Contains(got, tc.want) {
				t.Fatalf("got %q, want %q", got, tc.want)
			}
		})
	}
}

// A bare off is YAML's false (ScopeMode's reason): the profile must still read it.
func TestLoopRefReadsFalseAsOff(t *testing.T) {
	var p HarnessProfile
	if err := json.Unmarshal([]byte(`{"loop": false}`), &p); err != nil || p.Loop != LoopOff {
		t.Fatalf("%q %v", p.Loop, err)
	}
}

func TestDurationMarshalsAsItsString(t *testing.T) {
	b, err := json.Marshal(Monitor{FollowUpWindow: Duration{2 * time.Hour}})
	if err != nil || !strings.Contains(string(b), `"followUpWindow":"2h0m0s"`) {
		t.Fatalf("%s %v", b, err)
	}
	var m Monitor
	if err := json.Unmarshal(b, &m); err != nil || m.FollowUpWindow.Duration != 2*time.Hour {
		t.Fatalf("%v %v", m, err)
	}
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `go test -p 1 -run 'TestHarnessProfiles|TestLoopRef|TestDurationMarshals' ./internal/factory/config/`
Expected: FAIL to compile: `validateMergePolicy` and `HarnessProfile` are undefined.

- [ ] **Step 3: Implement**

`internal/factory/config/mergepolicy.go`:

```go
// SPDX-License-Identifier: Apache-2.0

package config

import (
	"encoding/json"
	"fmt"
	"maps"
	"regexp"
	"slices"
)

// TemplateNone is the harness of an adopted class: another author's pull requests, no run.
const TemplateNone = "none"

// LoopOff is a profile with no loop.
const LoopOff LoopRef = "off"

// LoopRef names a row of loops, or off.
type LoopRef string

// UnmarshalJSON reads a string, or false as off: YAML reads a bare off as false.
func (l *LoopRef) UnmarshalJSON(b []byte) error {
	if string(b) == "false" {
		*l = LoopOff
		return nil
	}
	var s string
	if err := json.Unmarshal(b, &s); err != nil {
		return fmt.Errorf("loop is off or a row of loops: %s", b)
	}
	*l = LoopRef(s)
	return nil
}

// HarnessProfile is a named, centrally approved way of running a class (merge policy MP2). Stage 1
// reads Checks and TestFirst; Template, Tier and Loop are validated here and read from repository
// cutover on. Empty keeps what the factory selects today.
type HarnessProfile struct {
	Template  string  `json:"template,omitempty"`
	Tier      string  `json:"tier,omitempty"`
	Checks    bool    `json:"checks,omitempty"`
	TestFirst bool    `json:"testFirst,omitempty"`
	Loop      LoopRef `json:"loop,omitempty"`
}

// MergeGuardrails bound every repository's class policy (MP3, MP6): a class may add protected
// paths and mandatory checks and choose lower caps, never the reverse. A cap of 0 is no guardrail.
type MergeGuardrails struct {
	ProtectedFiles   []string `json:"protectedFiles,omitempty"`
	MandatoryChecks  []string `json:"mandatoryChecks,omitempty"`
	MaxPatchFiles    int      `json:"maxPatchFiles,omitempty"`
	MaxModifiedLines int      `json:"maxModifiedLines,omitempty"`
	MaxPerDay        int      `json:"maxPerDay,omitempty"`
}

// PolicyManagement holds the rollout's switches, all off by default (merge policy stages).
type PolicyManagement struct {
	// Read observes each owned repository's class policy and compares it with this config. It
	// decides nothing.
	Read bool `json:"read,omitempty"`
}

var profileRE = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$`)

func (c *Config) validateMergePolicy(bad func(string, ...any)) {
	for _, name := range slices.Sorted(maps.Keys(c.HarnessProfiles)) {
		p := c.HarnessProfiles[name]
		if !profileRE.MatchString(name) {
			bad("harnessProfiles: %q is not a profile name", name)
		}
		if p.Template != "" && p.Template != TemplateNone && !slices.Contains(templates(), p.Template) {
			bad("harnessProfiles.%s: template %q is not one of %v or %s", name, p.Template, templates(), TemplateNone)
		}
		if p.Tier != "" && !slices.Contains(tiers(), p.Tier) {
			bad("harnessProfiles.%s: tier %q is not one of %v", name, p.Tier, tiers())
		}
		if _, ok := c.Loops[string(p.Loop)]; p.Loop != "" && p.Loop != LoopOff && !ok {
			bad("harnessProfiles.%s: loop %q is off or a row of loops", name, p.Loop)
		}
		if p.TestFirst && !p.Checks {
			bad("harnessProfiles.%s: testFirst needs checks (R17)", name)
		}
		if p.Template == TemplateNone && (p.Checks || p.TestFirst || p.Tier != "" || p.Loop != "") {
			bad("harnessProfiles.%s: template none runs nothing, so it takes no other key", name)
		}
	}
	g := c.MergeGuardrails
	for _, f := range []struct {
		key string
		n   int
	}{{"maxPatchFiles", g.MaxPatchFiles}, {"maxModifiedLines", g.MaxModifiedLines}, {"maxPerDay", g.MaxPerDay}} {
		if f.n < 0 {
			bad("mergeGuardrails.%s must be 0 (no guardrail) or more", f.key)
		}
	}
	for _, p := range g.ProtectedFiles {
		if _, err := regexp.Compile(p); err != nil || p == "" {
			bad("mergeGuardrails.protectedFiles %q is not a regular expression", p)
		}
	}
	for _, n := range g.MandatoryChecks {
		if n == "" {
			bad("mergeGuardrails.mandatoryChecks names an empty check")
		}
	}
}
```

In `config.go`, add to `Config` beside `Loops`:

```go
// HarnessProfiles, MergeGuardrails and PolicyManagement are the central half of the repository
// merge policy (mergepolicy): what a repository's class may reference and how far it may go.
HarnessProfiles  map[string]HarnessProfile `json:"harnessProfiles,omitempty"`
MergeGuardrails  MergeGuardrails           `json:"mergeGuardrails,omitzero"`
PolicyManagement PolicyManagement          `json:"policyManagement,omitzero"`
```

Beside `Duration.UnmarshalJSON`:

```go
// MarshalJSON writes the form UnmarshalJSON reads.
func (d Duration) MarshalJSON() ([]byte, error) { return json.Marshal(d.String()) }
```

Before relying on it, run `git grep -n 'json.Marshal' -- 'internal/factory/**/*.go'` and confirm nothing marshals a `config.Duration` for a reader expecting the old object form.

In `Validate`, call `c.validateMergePolicy(bad)` where the other `validate*` helpers are called, using that function's existing reporter. In `classes.go`, add:

```go
// ValidateClass reports one class's problems, for a class read from outside this config.
func ValidateClass(name string, cl Class, bad func(string, ...any)) { validateClass(name, cl, bad) }
```

In `docs/factory.md`'s config file section, add one row each for `harnessProfiles`, `mergeGuardrails` and `policyManagement.read`, stating that stage 1 decides nothing.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `go test -p 1 ./internal/factory/config/`
Expected: PASS, with the package's existing tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/config docs/factory.md
git commit -m "feat(factory): harness profiles, merge guardrails and the policy read switch"
```

### Task 3: The strict repository policy parser

**Files:**
- Create: `internal/factory/mergepolicy/policy.go`
- Test: `internal/factory/mergepolicy/policy_test.go`

**Interfaces:**
- Consumes: `fence.ValidName`, `config.Adopt`, `config.Oracle`, `config.Monitor`
- Produces:
  - `mergepolicy.Parse(raw []byte) (*File, error)`
  - `mergepolicy.File{Factory string; Classes map[string]ClassPolicy}`
  - `mergepolicy.ClassPolicy{Mode Mode; Author string; Adopt *config.Adopt; Harness string; Conditions Conditions; RequiresApproval []ApprovalLeaf; Limits Limits; Monitor *config.Monitor}`
  - `mergepolicy.Conditions{All []Leaf; Deny []DenyLeaf}`
  - `mergepolicy.Leaf`, `DenyLeaf{ProtectedFiles []string}`, `ApprovalLeaf{ChangedFiles []string}`, `Limits{MaxPerDay int}`
  - constants `ModeLive`, `ModeShadow`, `ModeOff`, `AuthorAgents`, `AuthorAdopt`

- [ ] **Step 1: Write the failing test**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"strings"
	"testing"
)

const example = `factory: aws-0
classes:
  docs-broad:
    mode: shadow
    author: agents
    harness: plain
    conditions:
      all:
        - allowedFiles: ['^docs/.+\.md$', '^README\.md$']
        - maxPatchFiles: 10
        - maxModifiedLines: 200
        - holdoutChecks: ['Check the documentation links 🔗']
      deny:
        - protectedFiles: ['^docs/superpowers/', '^docs/specs/']
    requiresApproval:
      - changedFiles: ['^docs/security/']
    limits:
      maxPerDay: 2
    monitor:
      followUpWindow: 168h
`

func TestParseTheSpecsExample(t *testing.T) {
	f, err := Parse([]byte(example))
	if err != nil {
		t.Fatal(err)
	}
	cl, ok := f.Classes["docs-broad"]
	switch {
	case f.Factory != "aws-0" || !ok:
		t.Fatalf("%+v", f)
	case cl.Mode != ModeShadow || cl.Author != AuthorAgents || cl.Harness != "plain":
		t.Fatalf("%+v", cl)
	case len(cl.Conditions.All) != 4 || len(cl.Conditions.Deny) != 1 || len(cl.RequiresApproval) != 1:
		t.Fatalf("%+v", cl)
	case cl.Limits.MaxPerDay != 2 || cl.Monitor == nil:
		t.Fatalf("%+v", cl)
	}
}

// A file naming only the factory has no policy: not an error, and no classes.
func TestParseAFenceOnlyFile(t *testing.T) {
	f, err := Parse([]byte("factory: aws-0\n"))
	if err != nil || f.Classes != nil {
		t.Fatalf("%+v %v", f, err)
	}
}

func TestABareOffIsTheOffMode(t *testing.T) {
	f, err := Parse([]byte("factory: aws-0\nclasses:\n  c: {mode: off, author: agents, harness: p}\n"))
	if err != nil || f.Classes["c"].Mode != ModeOff {
		t.Fatalf("%+v %v", f, err)
	}
}

func TestParseRefuses(t *testing.T) {
	cl := func(body string) string { return "factory: aws-0\nclasses:\n  c: " + body + "\n" }
	long := strings.Repeat("a", MaxPatternBytes+1)
	for name, tc := range map[string]struct{ in, want string }{
		"not yaml":            {"factory: [\n", "not YAML"},
		"too big":             {"factory: aws-0\n#" + strings.Repeat("x", MaxFileBytes), "bytes"},
		"bad factory":         {"factory: AWS 0\n", "factory"},
		"unknown top key":     {"factory: aws-0\nalso: x\n", "also"},
		"a duplicate key":     {cl("{mode: shadow, mode: live, author: agents, harness: p}"), "mode"},
		"an invalid mode":     {cl("{mode: armed, author: agents, harness: p}"), "mode"},
		"no mode":             {cl("{author: agents, harness: p}"), "mode"},
		"an invalid author":   {cl("{mode: shadow, author: people, harness: p}"), "author"},
		"adopt with no block": {cl("{mode: shadow, author: adopt, harness: p}"), "adopt"},
		"a block on agents":   {cl("{mode: shadow, author: agents, harness: p, adopt: {logins: [], branches: []}}"), "adopt"},
		"no harness":          {cl("{mode: shadow, author: agents}"), "harness"},
		"a bad class name":    {"factory: aws-0\nclasses:\n  Bad_Name: {mode: off, author: agents, harness: p}\n", "class name"},
		"an unknown leaf":     {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{sizeBelow: 3}]}}"), "sizeBelow"},
		"protected under all": {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{protectedFiles: [a]}]}}"), "protectedFiles"},
		"changed under deny":  {cl("{mode: shadow, author: agents, harness: p, conditions: {deny: [{changedFiles: [a]}]}}"), "changedFiles"},
		"any, until stage 2":  {cl("{mode: shadow, author: agents, harness: p, conditions: {any: []}}"), "any"},
		"two keys in a leaf":  {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{maxPatchFiles: 1, maxModifiedLines: 1}]}}"), "exactly one"},
		"an empty leaf":       {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{}]}}"), "exactly one"},
		"a repeated leaf":     {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{maxPatchFiles: 1}, {maxPatchFiles: 2}]}}"), "twice"},
		"modifyOnly false":    {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{modifyOnly: false}]}}"), "modifyOnly"},
		"a long pattern":      {cl("{mode: shadow, author: agents, harness: p, conditions: {all: [{allowedFiles: [" + long + "]}]}}"), "bytes"},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := Parse([]byte(tc.in))
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test -p 1 ./internal/factory/mergepolicy/`
Expected: FAIL to compile: the package has no `Parse`.

- [ ] **Step 3: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

// Package mergepolicy reads a repository's merge classes from its fence file: a closed, typed
// vocabulary (merge policy MP4), each class resolved to the config.Class the gate already decides
// on, under the central guardrails and harness profiles. It holds no state of GitHub's and makes no
// decision: through stage 3, the central config is the only merge authority.
package mergepolicy

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"regexp"
	"slices"

	"sigs.k8s.io/yaml"

	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/fence"
)

// The file's bounds. The patterns compile to RE2, linear in their input, so only their size is
// bounded here: GitHub's contents API and the validator do the rest.
const (
	MaxFileBytes    = 256 << 10
	MaxClasses      = 32
	MaxPatterns     = 64
	MaxPatternBytes = 512
)

// Mode is a class's state: live merges, shadow records, off does neither.
type Mode string

// The modes.
const (
	ModeLive   Mode = "live"
	ModeShadow Mode = "shadow"
	ModeOff    Mode = "off"
)

// UnmarshalJSON reads a string, or false as off: YAML reads a bare off as false.
func (m *Mode) UnmarshalJSON(b []byte) error {
	if string(b) == "false" {
		*m = ModeOff
		return nil
	}
	var s string
	if err := json.Unmarshal(b, &s); err != nil {
		return fmt.Errorf("mode is live, shadow or off: %s", b)
	}
	*m = Mode(s)
	return nil
}

// The author modes.
const (
	AuthorAgents = "agents"
	AuthorAdopt  = "adopt"
)

// File is .github/agent-factory.yaml.
type File struct {
	Factory string                 `json:"factory"`
	Classes map[string]ClassPolicy `json:"classes,omitempty"`
}

// ClassPolicy is one class as a repository declares it.
type ClassPolicy struct {
	Mode             Mode            `json:"mode"`
	Author           string          `json:"author"`
	Adopt            *config.Adopt   `json:"adopt,omitempty"`
	Harness          string          `json:"harness"`
	Conditions       Conditions      `json:"conditions,omitzero"`
	RequiresApproval []ApprovalLeaf  `json:"requiresApproval,omitempty"`
	Limits           Limits          `json:"limits,omitzero"`
	Monitor          *config.Monitor `json:"monitor,omitempty"`
}

// Conditions are a class's predicates. Any leaf absent from All is not checked.
type Conditions struct {
	All  []Leaf     `json:"all,omitempty"`
	Deny []DenyLeaf `json:"deny,omitempty"`
}

// Leaf is one predicate: exactly one field set.
type Leaf struct {
	AllowedFiles     []string       `json:"allowedFiles,omitempty"`
	ModifyOnly       *bool          `json:"modifyOnly,omitempty"`
	MaxPatchFiles    *int           `json:"maxPatchFiles,omitempty"`
	MaxModifiedLines *int           `json:"maxModifiedLines,omitempty"`
	DiffShape        *string        `json:"diffShape,omitempty"`
	HoldoutChecks    []string       `json:"holdoutChecks,omitempty"`
	ReleaseAgeCheck  *string        `json:"releaseAgeCheck,omitempty"`
	Oracle           *config.Oracle `json:"oracle,omitempty"`
	CompanionFiles   []string       `json:"companionFiles,omitempty"`
	RequiredLabel    *string        `json:"requiredLabel,omitempty"`
}

// names are the keys the leaf sets.
func (l Leaf) names() []string {
	var out []string
	for _, f := range []struct {
		key string
		set bool
	}{
		{"allowedFiles", l.AllowedFiles != nil}, {"modifyOnly", l.ModifyOnly != nil},
		{"maxPatchFiles", l.MaxPatchFiles != nil}, {"maxModifiedLines", l.MaxModifiedLines != nil},
		{"diffShape", l.DiffShape != nil}, {"holdoutChecks", l.HoldoutChecks != nil},
		{"releaseAgeCheck", l.ReleaseAgeCheck != nil}, {"oracle", l.Oracle != nil},
		{"companionFiles", l.CompanionFiles != nil}, {"requiredLabel", l.RequiredLabel != nil},
	} {
		if f.set {
			out = append(out, f.key)
		}
	}
	return out
}

// DenyLeaf refuses a pull request touching one of its paths.
type DenyLeaf struct {
	ProtectedFiles []string `json:"protectedFiles"`
}

// ApprovalLeaf asks a human about a pull request touching one of its paths, even in a live class.
type ApprovalLeaf struct {
	ChangedFiles []string `json:"changedFiles"`
}

// Limits are a class's own caps, below the guardrails.
type Limits struct {
	MaxPerDay int `json:"maxPerDay,omitempty"`
}

var classRE = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$`)

// Parse reads the file strictly: duplicate and unknown keys, a key in the wrong layer and a leaf
// that is not exactly one predicate are all errors. It checks shape, not the guardrails: Validate.
func Parse(raw []byte) (*File, error) {
	if len(raw) > MaxFileBytes {
		return nil, fmt.Errorf("mergepolicy: the file is over %d bytes", MaxFileBytes)
	}
	j, err := yaml.YAMLToJSONStrict(raw)
	if err != nil {
		return nil, fmt.Errorf("mergepolicy: not YAML: %w", err)
	}
	dec := json.NewDecoder(bytes.NewReader(j))
	dec.DisallowUnknownFields()
	var f File
	if err := dec.Decode(&f); err != nil {
		return nil, fmt.Errorf("mergepolicy: %w", err)
	}
	if !fence.ValidName(f.Factory) {
		return nil, fmt.Errorf("mergepolicy: factory %q is not a factory name", f.Factory)
	}
	if len(f.Classes) > MaxClasses {
		return nil, fmt.Errorf("mergepolicy: at most %d classes", MaxClasses)
	}
	var errs []error
	for _, name := range slices.Sorted(maps.Keys(f.Classes)) {
		if err := f.Classes[name].shape(); err != nil {
			errs = append(errs, fmt.Errorf("class %s: %w", name, err))
		}
		if !classRE.MatchString(name) {
			errs = append(errs, fmt.Errorf("%q is not a class name", name))
		}
	}
	if err := errors.Join(errs...); err != nil {
		return nil, fmt.Errorf("mergepolicy: %w", err)
	}
	return &f, nil
}

func (p ClassPolicy) shape() error {
	var errs []error
	if !slices.Contains([]Mode{ModeLive, ModeShadow, ModeOff}, p.Mode) {
		errs = append(errs, fmt.Errorf("mode %q is not live, shadow or off", p.Mode))
	}
	switch {
	case p.Author != AuthorAgents && p.Author != AuthorAdopt:
		errs = append(errs, fmt.Errorf("author %q is not agents or adopt", p.Author))
	case (p.Author == AuthorAdopt) != (p.Adopt != nil):
		errs = append(errs, errors.New("adopt is required with author: adopt, and refused otherwise"))
	}
	if p.Harness == "" {
		errs = append(errs, errors.New("harness is required: a profile of the central list"))
	}
	seen := map[string]bool{}
	var patterns [][]string
	for _, l := range p.Conditions.All {
		names := l.names()
		if len(names) != 1 {
			errs = append(errs, fmt.Errorf("a leaf of all sets exactly one key, not %v", names))
			continue
		}
		if seen[names[0]] {
			errs = append(errs, fmt.Errorf("%s is declared twice", names[0]))
		}
		seen[names[0]] = true
		if l.ModifyOnly != nil && !*l.ModifyOnly {
			errs = append(errs, errors.New("modifyOnly: false says nothing: leave it out"))
		}
		patterns = append(patterns, l.AllowedFiles, l.CompanionFiles)
	}
	for _, d := range p.Conditions.Deny {
		patterns = append(patterns, d.ProtectedFiles)
	}
	for _, a := range p.RequiresApproval {
		patterns = append(patterns, a.ChangedFiles)
	}
	for _, list := range patterns {
		if len(list) > MaxPatterns {
			errs = append(errs, fmt.Errorf("a list holds at most %d patterns", MaxPatterns))
		}
		for _, pat := range list {
			if len(pat) > MaxPatternBytes {
				errs = append(errs, fmt.Errorf("a pattern is at most %d bytes", MaxPatternBytes))
			}
		}
	}
	return errors.Join(errs...)
}
```

If `sigs.k8s.io/yaml` v1.6.0 does not export `YAMLToJSONStrict`, stop and report: the duplicate-key refusal is a requirement, and silently losing it lets `mode: shadow, mode: live` read as live.

- [ ] **Step 4: Run the test to verify it passes**

Run: `go test -p 1 ./internal/factory/mergepolicy/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/factory/mergepolicy
git commit -m "feat(factory): parse a repository's merge classes strictly"
```

### Task 4: Resolve and validate against the central config

**Files:**
- Create: `internal/factory/mergepolicy/resolve.go`
- Test: `internal/factory/mergepolicy/resolve_test.go`

**Interfaces:**
- Consumes: Task 2's config types, Task 3's `File` and `ClassPolicy`
- Produces:
  - `mergepolicy.Resolved{Class config.Class; Approval []string; Profile config.HarnessProfile}`
  - `mergepolicy.Resolve(name string, p ClassPolicy, c *config.Config) (Resolved, error)`
  - `mergepolicy.Validate(f *File, c *config.Config) error`
  - `mergepolicy.ErrGuardrail`, wrapped by every guardrail and profile refusal

- [ ] **Step 1: Write the failing test**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"errors"
	"slices"
	"strings"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
)

func central() *config.Config {
	return &config.Config{HarnessProfiles: map[string]config.HarnessProfile{
		"plain":        {},
		"checked":      {Checks: true},
		"adopted-none": {Template: config.TemplateNone},
	}}
}

func resolved(t *testing.T, raw string, c *config.Config) Resolved {
	t.Helper()
	f, err := Parse([]byte(raw))
	if err != nil {
		t.Fatal(err)
	}
	r, err := Resolve("docs-broad", f.Classes["docs-broad"], c)
	if err != nil {
		t.Fatal(err)
	}
	return r
}

func TestResolveFillsTheClassTheGateReads(t *testing.T) {
	r := resolved(t, example, central())
	cl := r.Class
	switch {
	case cl.Live || !cl.Shadow || cl.Adopted():
		t.Fatalf("%+v", cl)
	case !slices.Equal(cl.AllowedFiles, []string{`^docs/.+\.md$`, `^README\.md$`}):
		t.Fatalf("%v", cl.AllowedFiles)
	case !slices.Equal(cl.ProtectedFiles, []string{"^docs/superpowers/", "^docs/specs/"}):
		t.Fatalf("%v", cl.ProtectedFiles)
	case cl.MaxPatchFiles != 10 || cl.MaxModifiedLines != 200 || cl.MaxPerDay != 2:
		t.Fatalf("%+v", cl)
	case len(cl.HoldoutChecks) != 1 || cl.Monitor == nil || cl.Monitor.FollowUpWindow.Hours() != 168:
		t.Fatalf("%+v", cl)
	case !slices.Equal(r.Approval, []string{"^docs/security/"}):
		t.Fatalf("%v", r.Approval)
	}
}

func TestTheProfileSetsChecks(t *testing.T) {
	raw := strings.Replace(example, "harness: plain", "harness: checked", 1)
	if r := resolved(t, raw, central()); !r.Class.Checks || r.Class.TestFirst {
		t.Fatalf("%+v", r.Class)
	}
}

// Guardrails add to a class, and an undeclared cap inherits the guardrail's.
func TestGuardrailsOnlyTighten(t *testing.T) {
	c := central()
	c.MergeGuardrails = config.MergeGuardrails{ProtectedFiles: []string{"^secrets/"}, MandatoryChecks: []string{"Leak scan"},
		MaxPatchFiles: 20, MaxModifiedLines: 500, MaxPerDay: 5}
	cl := resolved(t, example, c).Class
	switch {
	case !slices.Contains(cl.ProtectedFiles, "^secrets/") || !slices.Contains(cl.HoldoutChecks, "Leak scan"):
		t.Fatalf("%+v", cl)
	case cl.MaxPatchFiles != 10 || cl.MaxModifiedLines != 200 || cl.MaxPerDay != 2:
		t.Fatalf("a lower cap stands: %+v", cl)
	}
	bare := "factory: aws-0\nclasses:\n  docs-broad: {mode: shadow, author: agents, harness: plain}\n"
	cl = resolved(t, bare, c).Class
	if cl.MaxPatchFiles != 20 || cl.MaxModifiedLines != 500 || cl.MaxPerDay != 5 {
		t.Fatalf("an undeclared cap inherits: %+v", cl)
	}
}

func TestResolveRefuses(t *testing.T) {
	over := func() *config.Config { c := central(); c.MergeGuardrails.MaxPatchFiles = 5; return c }
	for name, tc := range map[string]struct {
		raw  string
		cfg  *config.Config
		want string
	}{
		"an unknown profile": {strings.Replace(example, "harness: plain", "harness: nope", 1), central(), "nope"},
		"a cap over":         {example, over(), "maxPatchFiles"},
		"agents with none":   {strings.Replace(example, "harness: plain", "harness: adopted-none", 1), central(), "runs nothing"},
	} {
		t.Run(name, func(t *testing.T) {
			f, err := Parse([]byte(tc.raw))
			if err != nil {
				t.Fatal(err)
			}
			_, err = Resolve("docs-broad", f.Classes["docs-broad"], tc.cfg)
			if err == nil || !strings.Contains(err.Error(), tc.want) || !errors.Is(err, ErrGuardrail) {
				t.Fatalf("got %v, want %q and ErrGuardrail", err, tc.want)
			}
		})
	}
}

func TestValidate(t *testing.T) {
	required := "  docs-links: {mode: live, author: agents, harness: plain}\n  revert: {mode: live, author: agents, harness: plain}\n"
	head := "factory: aws-0\nclasses:\n"
	for name, tc := range map[string]struct{ raw, want string }{
		"fine":           {head + required, ""},
		"fence only":     {"factory: aws-0\n", ""},
		"no revert":      {head + "  docs-links: {mode: live, author: agents, harness: plain}\n", "revert"},
		"review":         {head + required + "  review: {mode: off, author: agents, harness: plain}\n", "review is implicit"},
		"the class rule": {head + required + "  bad:\n    mode: shadow\n    author: agents\n    harness: plain\n    conditions: {all: [{allowedFiles: ['docs/.+']}]}\n", "must start with ^"},
	} {
		t.Run(name, func(t *testing.T) {
			f, err := Parse([]byte(tc.raw))
			if err != nil {
				t.Fatal(err)
			}
			err = Validate(f, central())
			if (tc.want == "") != (err == nil) || (err != nil && !strings.Contains(err.Error(), tc.want)) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test -p 1 -run 'TestResolve|TestTheProfile|TestGuardrails|TestValidate' ./internal/factory/mergepolicy/`
Expected: FAIL to compile: `Resolve` is undefined.

- [ ] **Step 3: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"errors"
	"fmt"
	"maps"
	"slices"

	"github.com/Smana/maku/internal/factory/config"
)

// ErrGuardrail marks a class refused by the central config rather than by its own shape, for the
// load-error metric's reason.
var ErrGuardrail = errors.New("guardrail")

// Resolved is a class as the gate would read it, with what the gate does not read yet.
type Resolved struct {
	Class    config.Class
	Approval []string // requiresApproval's paths; the gate reads them from stage 5
	Profile  config.HarnessProfile
}

// Resolve turns a parsed class into the config.Class the gate decides on, under the guardrails:
// they add protected paths and mandatory checks, an undeclared cap inherits theirs, and a declared
// cap above theirs is refused (MP6).
func Resolve(name string, p ClassPolicy, c *config.Config) (Resolved, error) {
	profile, ok := c.HarnessProfiles[p.Harness]
	if !ok {
		return Resolved{}, fmt.Errorf("class %s: %w: harness %q is not in harnessProfiles", name, ErrGuardrail, p.Harness)
	}
	adopted := p.Author == AuthorAdopt
	if none := profile.Template == config.TemplateNone; none != adopted {
		return Resolved{}, fmt.Errorf("class %s: %w: harness %q: template none runs nothing, and only an adopted class takes it", name, ErrGuardrail, p.Harness)
	}
	cl := config.Class{Live: p.Mode == ModeLive, Shadow: p.Mode == ModeShadow,
		Checks: profile.Checks, TestFirst: profile.TestFirst, MaxPerDay: p.Limits.MaxPerDay, Monitor: p.Monitor}
	if adopted {
		cl.Author = &config.Author{Adopt: p.Adopt}
	}
	for _, l := range p.Conditions.All {
		cl.AllowedFiles = append(cl.AllowedFiles, l.AllowedFiles...)
		cl.HoldoutChecks = append(cl.HoldoutChecks, l.HoldoutChecks...)
		cl.CompanionFiles = append(cl.CompanionFiles, l.CompanionFiles...)
		switch {
		case l.ModifyOnly != nil:
			cl.ModifyOnly = *l.ModifyOnly
		case l.MaxPatchFiles != nil:
			cl.MaxPatchFiles = *l.MaxPatchFiles
		case l.MaxModifiedLines != nil:
			cl.MaxModifiedLines = *l.MaxModifiedLines
		case l.DiffShape != nil:
			cl.DiffShape = *l.DiffShape
		case l.ReleaseAgeCheck != nil:
			cl.ReleaseAgeCheck = *l.ReleaseAgeCheck
		case l.Oracle != nil:
			cl.Oracle = l.Oracle
		case l.RequiredLabel != nil:
			cl.RequiredLabel = *l.RequiredLabel
		}
	}
	for _, d := range p.Conditions.Deny {
		cl.ProtectedFiles = append(cl.ProtectedFiles, d.ProtectedFiles...)
	}
	var approval []string
	for _, a := range p.RequiresApproval {
		approval = append(approval, a.ChangedFiles...)
	}
	g := c.MergeGuardrails
	for _, p := range g.ProtectedFiles {
		if !slices.Contains(cl.ProtectedFiles, p) {
			cl.ProtectedFiles = append(cl.ProtectedFiles, p)
		}
	}
	for _, n := range g.MandatoryChecks {
		if !slices.Contains(cl.HoldoutChecks, n) {
			cl.HoldoutChecks = append(cl.HoldoutChecks, n)
		}
	}
	for _, f := range []struct {
		key   string
		value *int
		limit int
	}{{"maxPatchFiles", &cl.MaxPatchFiles, g.MaxPatchFiles}, {"maxModifiedLines", &cl.MaxModifiedLines, g.MaxModifiedLines}, {"maxPerDay", &cl.MaxPerDay, g.MaxPerDay}} {
		switch {
		case f.limit == 0:
		case *f.value == 0:
			*f.value = f.limit
		case *f.value > f.limit:
			return Resolved{}, fmt.Errorf("class %s: %w: %s %d is over the guardrail's %d", name, ErrGuardrail, f.key, *f.value, f.limit)
		}
	}
	return Resolved{Class: cl, Approval: approval, Profile: profile}, nil
}

// Validate is the whole file against the central config: a file with no classes has no policy and
// passes; one with classes declares docs-links and revert, never review, and each class passes
// Resolve and the gate's own class check.
func Validate(f *File, c *config.Config) error {
	if f.Classes == nil {
		return nil
	}
	var errs []error
	for _, name := range []string{"docs-links", "revert"} {
		if _, ok := f.Classes[name]; !ok {
			errs = append(errs, fmt.Errorf("class %s is required", name))
		}
	}
	if _, ok := f.Classes["review"]; ok {
		errs = append(errs, errors.New("class review is implicit: it is never declared"))
	}
	for _, name := range slices.Sorted(maps.Keys(f.Classes)) {
		r, err := Resolve(name, f.Classes[name], c)
		if err != nil {
			errs = append(errs, err)
			continue
		}
		config.ValidateClass(name, r.Class, func(format string, a ...any) { errs = append(errs, fmt.Errorf(format, a...)) })
	}
	return errors.Join(errs...)
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `go test -p 1 ./internal/factory/mergepolicy/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/factory/mergepolicy
git commit -m "feat(factory): resolve a repository's classes under the central guardrails"
```

### Task 5: Export from central, and compare both ways

**Files:**
- Create: `internal/factory/mergepolicy/export.go`
- Create: `internal/factory/mergepolicy/testdata/classes-cloud-native-ref.yaml`
- Create: `internal/factory/mergepolicy/testdata/classes-ai-native-ref.yaml`
- Test: `internal/factory/mergepolicy/export_test.go`

**Interfaces:**
- Consumes: `Resolve`, `Validate`, `Parse`
- Produces:
  - `mergepolicy.Export(rc *config.Repository, c *config.Config) (*File, error)`
  - `mergepolicy.Marshal(f *File) ([]byte, error)`
  - `mergepolicy.Compare(rc *config.Repository, f *File, c *config.Config) []string`, each string one divergence, sorted; empty means structurally equivalent

- [ ] **Step 1: Fix the real classes as fixtures**

Run from the Maku worktree, with `ANR` set to a checkout of ai-native-ref at `origin/main`:

```bash
python3 - "$ANR/tooling/base/agent-factory/helm-values-configmap.yaml" internal/factory/mergepolicy/testdata <<'EOF'
import sys, yaml
src, out = sys.argv[1:]
values = yaml.safe_load(yaml.safe_load(open(src))["data"]["values.yaml"])
for r in values["config"]["repositories"]:
    name = r["name"].split("/")[1]
    with open(f"{out}/classes-{name}.yaml", "w") as f:
        f.write(f"# {r['name']}'s classes as ai-native-ref declares them centrally: copied, not edited.\n")
        yaml.safe_dump(r["classes"], f, sort_keys=True, allow_unicode=True)
EOF
```

Expected: both files exist and hold `docs-links`, `revert` and `review`.

- [ ] **Step 2: Write the failing test**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"sigs.k8s.io/yaml"

	"github.com/Smana/maku/internal/factory/config"
)

func repoFrom(t *testing.T, file string) *config.Repository {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", file))
	if err != nil {
		t.Fatal(err)
	}
	var classes map[string]config.Class
	if err := yaml.UnmarshalStrict(raw, &classes); err != nil {
		t.Fatal(err)
	}
	return &config.Repository{Name: "o/r", Classes: classes}
}

// Stage 1's exit: every real class survives export, the file, and the parser, unchanged.
func TestRealClassesRoundTrip(t *testing.T) {
	for _, file := range []string{"classes-cloud-native-ref.yaml", "classes-ai-native-ref.yaml"} {
		t.Run(file, func(t *testing.T) {
			rc, c := repoFrom(t, file), central()
			c.Factory = "aws-0"
			f, err := Export(rc, c)
			if err != nil {
				t.Fatal(err)
			}
			raw, err := Marshal(f)
			if err != nil {
				t.Fatal(err)
			}
			g, err := Parse(raw)
			if err != nil {
				t.Fatalf("%v\n%s", err, raw)
			}
			if err := Validate(g, c); err != nil {
				t.Fatalf("%v\n%s", err, raw)
			}
			if d := Compare(rc, g, c); len(d) != 0 {
				t.Fatalf("%v\n%s", d, raw)
			}
			if _, ok := g.Classes["review"]; ok {
				t.Fatal("review is never exported")
			}
		})
	}
}

func TestExportNeedsAProfile(t *testing.T) {
	rc := &config.Repository{Name: "o/r", Classes: map[string]config.Class{"docs-links": {Checks: true}}}
	c := &config.Config{Factory: "aws-0", HarnessProfiles: map[string]config.HarnessProfile{"plain": {}}}
	if _, err := Export(rc, c); err == nil || !strings.Contains(err.Error(), "no harness profile") {
		t.Fatalf("got %v", err)
	}
}

// A setting that moved is reported whichever way, so a list reordered is not a divergence.
func TestCompareReportsEveryDifference(t *testing.T) {
	c := central()
	rc := &config.Repository{Name: "o/r", Classes: map[string]config.Class{
		"docs-links": {Live: true},
		"revert":     {Live: true},
		"gone":       {Shadow: true},
		"moved":      {Shadow: true, MaxPatchFiles: 3},
		"sorted":     {Shadow: true, ProtectedFiles: []string{"^a", "^b"}},
		"review":     {Checks: true},
	}}
	f, err := Parse([]byte(`factory: aws-0
classes:
  docs-links: {mode: live, author: agents, harness: plain}
  revert: {mode: live, author: agents, harness: plain}
  moved:
    mode: shadow
    author: agents
    harness: plain
    conditions: {all: [{maxPatchFiles: 4}]}
  sorted:
    mode: shadow
    author: agents
    harness: plain
    conditions: {deny: [{protectedFiles: ['^b', '^a']}]}
  extra: {mode: off, author: agents, harness: plain}
`))
	if err != nil {
		t.Fatal(err)
	}
	got := strings.Join(Compare(rc, f, c), "\n")
	for _, want := range []string{"extra: only in the repository", "gone: only in the central config", "moved: "} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q in:\n%s", want, got)
		}
	}
	for _, not := range []string{"sorted", "review", "docs-links"} {
		if strings.Contains(got, not) {
			t.Errorf("%q is no divergence:\n%s", not, got)
		}
	}
}

// requiresApproval has no central form: a class declaring it is not yet the same class.
func TestCompareCountsAnApprovalSubset(t *testing.T) {
	rc := &config.Repository{Name: "o/r", Classes: map[string]config.Class{"c": {Shadow: true}}}
	f, err := Parse([]byte("factory: aws-0\nclasses:\n  c:\n    mode: shadow\n    author: agents\n    harness: plain\n    requiresApproval: [{changedFiles: ['^a']}]\n"))
	if err != nil {
		t.Fatal(err)
	}
	if d := Compare(rc, f, central()); len(d) != 1 || !strings.Contains(d[0], "requiresApproval") {
		t.Fatalf("%v", d)
	}
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `go test -p 1 -run 'TestRealClasses|TestExport|TestCompare' ./internal/factory/mergepolicy/`
Expected: FAIL to compile: `Export` is undefined.

- [ ] **Step 4: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"slices"

	"sigs.k8s.io/yaml"

	"github.com/Smana/maku/internal/factory/config"
)

// Export writes a repository's central classes as a policy file (MP15): behaviour preserved, so
// each class keeps its mode. review stays implicit. A class whose checks and testFirst no profile
// holds is an error: the operator adds the profile first.
func Export(rc *config.Repository, c *config.Config) (*File, error) {
	f := &File{Factory: c.Factory, Classes: map[string]ClassPolicy{}}
	var errs []error
	for _, name := range slices.Sorted(maps.Keys(rc.Classes)) {
		if name == "review" {
			continue
		}
		p, err := exportClass(rc.Classes[name], c)
		if err != nil {
			errs = append(errs, fmt.Errorf("class %s: %w", name, err))
			continue
		}
		f.Classes[name] = p
	}
	return f, errors.Join(errs...)
}

func exportClass(cl config.Class, c *config.Config) (ClassPolicy, error) {
	harness, ok := profileFor(cl, c)
	if !ok {
		return ClassPolicy{}, fmt.Errorf("no harness profile holds checks=%t testFirst=%t adopted=%t", cl.Checks, cl.TestFirst, cl.Adopted())
	}
	p := ClassPolicy{Mode: ModeOff, Author: AuthorAgents, Harness: harness, Limits: Limits{MaxPerDay: cl.MaxPerDay}, Monitor: cl.Monitor}
	switch {
	case cl.Live:
		p.Mode = ModeLive
	case cl.Shadow:
		p.Mode = ModeShadow
	}
	if cl.Adopted() {
		p.Author, p.Adopt = AuthorAdopt, cl.Author.Adopt
	}
	add := func(l Leaf) { p.Conditions.All = append(p.Conditions.All, l) }
	if len(cl.AllowedFiles) > 0 {
		add(Leaf{AllowedFiles: cl.AllowedFiles})
	}
	if cl.ModifyOnly {
		add(Leaf{ModifyOnly: new(true)})
	}
	if cl.MaxPatchFiles > 0 {
		add(Leaf{MaxPatchFiles: new(cl.MaxPatchFiles)})
	}
	if cl.MaxModifiedLines > 0 {
		add(Leaf{MaxModifiedLines: new(cl.MaxModifiedLines)})
	}
	if cl.DiffShape != "" {
		add(Leaf{DiffShape: new(cl.DiffShape)})
	}
	if len(cl.HoldoutChecks) > 0 {
		add(Leaf{HoldoutChecks: cl.HoldoutChecks})
	}
	if cl.ReleaseAgeCheck != "" {
		add(Leaf{ReleaseAgeCheck: new(cl.ReleaseAgeCheck)})
	}
	if cl.Oracle != nil {
		add(Leaf{Oracle: cl.Oracle})
	}
	if len(cl.CompanionFiles) > 0 {
		add(Leaf{CompanionFiles: cl.CompanionFiles})
	}
	if cl.RequiredLabel != "" {
		add(Leaf{RequiredLabel: new(cl.RequiredLabel)})
	}
	if len(cl.ProtectedFiles) > 0 {
		p.Conditions.Deny = []DenyLeaf{{ProtectedFiles: cl.ProtectedFiles}}
	}
	return p, nil
}

// profileFor is the first profile by name that runs the class as it runs today.
func profileFor(cl config.Class, c *config.Config) (string, bool) {
	for _, name := range slices.Sorted(maps.Keys(c.HarnessProfiles)) {
		p := c.HarnessProfiles[name]
		if (p.Template == config.TemplateNone) == cl.Adopted() && p.Checks == cl.Checks && p.TestFirst == cl.TestFirst {
			return name, true
		}
	}
	return "", false
}

// Marshal writes the file. It is read back through Parse by the caller's test, never trusted.
func Marshal(f *File) ([]byte, error) { return yaml.Marshal(f) }

// Compare lists how the repository's classes differ from the central ones, class by class, with
// path and check lists read as sets. review is implicit on both sides.
func Compare(rc *config.Repository, f *File, c *config.Config) []string {
	var out []string
	names := map[string]bool{}
	for n := range rc.Classes {
		names[n] = true
	}
	for n := range f.Classes {
		names[n] = true
	}
	delete(names, "review")
	for _, name := range slices.Sorted(maps.Keys(names)) {
		central, inCentral := rc.Classes[name]
		repo, inRepo := f.Classes[name]
		switch {
		case !inRepo:
			out = append(out, name+": only in the central config")
		case !inCentral:
			out = append(out, name+": only in the repository")
		default:
			r, err := Resolve(name, repo, c)
			if err != nil {
				out = append(out, fmt.Sprintf("%s: %v", name, err))
				continue
			}
			if len(r.Approval) > 0 {
				out = append(out, name+": requiresApproval has no central form")
			}
			if a, b := canonical(central), canonical(r.Class); a != b {
				out = append(out, fmt.Sprintf("%s: central %s, repository %s", name, a, b))
			}
		}
	}
	return out
}

// canonical is a class's JSON with its sets sorted, for comparison and for the message.
func canonical(cl config.Class) string {
	for _, list := range []*[]string{&cl.AllowedFiles, &cl.ProtectedFiles, &cl.HoldoutChecks, &cl.CompanionFiles} {
		*list = slices.Sorted(slices.Values(*list))
	}
	b, err := json.Marshal(cl)
	if err != nil { // strings, ints, bools and Durations: Marshal cannot fail
		return err.Error()
	}
	return string(b)
}
```

`slices.Sorted` returns a new slice, so `canonical` never reorders the caller's lists.

- [ ] **Step 5: Run the test to verify it passes**

Run: `go test -p 1 ./internal/factory/mergepolicy/`
Expected: PASS. A failure in `TestRealClassesRoundTrip` is real: a central class that does not survive is exactly what stage 1 exists to find. Report it; do not edit the fixture to pass.

- [ ] **Step 6: Commit**

```bash
git add internal/factory/mergepolicy
git commit -m "feat(factory): export central classes and compare them with a repository's"
```

### Task 6: The observer and its metrics

**Files:**
- Create: `internal/factory/mergepolicy/watch.go`
- Modify: `internal/factory/fmetrics/fmetrics.go`
- Modify: `internal/app/factory.go` (the `fenced` construction, line 187 at `9a60f0eb`)
- Test: `internal/factory/mergepolicy/watch_test.go`
- Test: `internal/factory/fmetrics/repository_test.go`

**Interfaces:**
- Consumes: `Fence.OnFile`, `Parse`, `Validate`, `Compare`
- Produces:
  - `mergepolicy.Recorder` interface: `PolicyLoadError(ctx context.Context, repository, reason string)`, `PolicyDivergence(ctx context.Context, repository string, n int)`
  - `mergepolicy.Watch{Cfg *config.Config; Metrics Recorder; Log *slog.Logger}` with `Observe(ctx context.Context, repository string, body []byte)` and `Snapshot(repository string) (Snapshot, bool)`
  - `mergepolicy.Snapshot{Hash string; Err error; Divergences []string; HasClasses bool}`
  - Metric reasons `ReasonInvalid = "invalid"`, `ReasonGuardrail = "guardrail_mismatch"`

- [ ] **Step 1: Write the failing tests**

`watch_test.go`:

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"context"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
)

type rec struct {
	reasons []string
	gauge   []int
}

func (r *rec) PolicyLoadError(_ context.Context, _, reason string) {
	r.reasons = append(r.reasons, reason)
}
func (r *rec) PolicyDivergence(_ context.Context, _ string, n int) { r.gauge = append(r.gauge, n) }

func watchRig() (*Watch, *rec) {
	c := central()
	c.Repositories = []config.Repository{{Name: "o/r", Classes: map[string]config.Class{
		"docs-links": {Live: true}, "revert": {Live: true},
	}}}
	r := &rec{}
	return &Watch{Cfg: c, Metrics: r}, r
}

const same = "factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: plain}\n  revert: {mode: live, author: agents, harness: plain}\n"

func TestObserve(t *testing.T) {
	for name, tc := range map[string]struct {
		body    string
		reasons []string
		gauge   []int
		classes bool
	}{
		"no policy":      {"factory: aws-0\n", nil, []int{0}, false},
		"equivalent":     {same, nil, []int{0}, true},
		"divergent":      {"factory: aws-0\nclasses:\n  docs-links: {mode: shadow, author: agents, harness: plain}\n  revert: {mode: live, author: agents, harness: plain}\n", nil, []int{1}, true},
		"invalid":        {"factory: aws-0\nclasses: [no]\n", []string{ReasonInvalid}, nil, false},
		"a class rule":   {"factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: plain}\n", []string{ReasonInvalid}, nil, true},
		"a guardrail":    {"factory: aws-0\nclasses:\n  docs-links: {mode: live, author: agents, harness: nope}\n  revert: {mode: live, author: agents, harness: plain}\n", []string{ReasonGuardrail}, nil, true},
	} {
		t.Run(name, func(t *testing.T) {
			w, r := watchRig()
			w.Observe(t.Context(), "o/r", []byte(tc.body))
			if len(r.reasons) != len(tc.reasons) || (len(tc.reasons) == 1 && r.reasons[0] != tc.reasons[0]) {
				t.Fatalf("reasons %v", r.reasons)
			}
			if len(r.gauge) != len(tc.gauge) || (len(tc.gauge) == 1 && r.gauge[0] != tc.gauge[0]) {
				t.Fatalf("gauge %v", r.gauge)
			}
			s, ok := w.Snapshot("o/r")
			if !ok || s.Hash == "" || s.HasClasses != tc.classes || (s.Err != nil) != (len(tc.reasons) > 0) {
				t.Fatalf("%+v", s)
			}
		})
	}
}

// A repository the config does not list has nothing to compare with, and its name must not reach
// a metric through this path.
func TestObserveIgnoresAnUnlistedRepository(t *testing.T) {
	w, r := watchRig()
	w.Observe(t.Context(), "o/other", []byte(same))
	if len(r.reasons)+len(r.gauge) != 0 {
		t.Fatalf("%+v", r)
	}
	if _, ok := w.Snapshot("o/other"); ok {
		t.Fatal("no snapshot")
	}
}
```

Add to `repository_test.go`:

```go
// Merge policy: bounded by the repository list and the closed reason list (MP18).
func TestPolicyMetricsAreBounded(t *testing.T) {
	c := fake.NewClientBuilder().WithScheme(scheme()).Build()
	s, scrape := rig(t, c, func() bool { return true })
	s.ListRepositories("Smana/a")
	s.PolicyLoadError(t.Context(), "Smana/a", "invalid")
	s.PolicyLoadError(t.Context(), "Smana/a", "not-a-reason")
	s.PolicyDivergence(t.Context(), "Smana/a", 2)
	out := scrape()
	for _, want := range []string{
		`maku_factory_policy_load_errors_total{reason="invalid",repository="Smana/a"`,
		`maku_factory_policy_central_divergence{repository="Smana/a"`,
	} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %s in\n%s", want, out)
		}
	}
	if strings.Contains(out, "not-a-reason") {
		t.Fatal("a reason outside the list")
	}
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `go test -p 1 -run 'TestObserve|TestPolicyMetrics' ./internal/factory/mergepolicy/ ./internal/factory/fmetrics/`
Expected: FAIL to compile: `Watch` and `PolicyLoadError` are undefined.

- [ ] **Step 3: Implement the observer**

```go
// SPDX-License-Identifier: Apache-2.0

package mergepolicy

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"log/slog"
	"slices"
	"strings"
	"sync"

	"github.com/Smana/maku/internal/factory/config"
)

// The reasons a policy fails to load. Unreadable and stale arrive with repository authority: until
// then the fence's own metric reports a failed read, and nothing depends on a fresh policy.
const (
	ReasonInvalid   = "invalid"
	ReasonGuardrail = "guardrail_mismatch"
)

// Recorder is the part of the factory's metrics Watch writes.
type Recorder interface {
	PolicyLoadError(ctx context.Context, repository, reason string)
	PolicyDivergence(ctx context.Context, repository string, n int)
}

// Snapshot is the last file read for a repository, and what it came to.
type Snapshot struct {
	Hash        string
	HasClasses  bool
	Err         error
	Divergences []string
}

// Watch observes each owned repository's file as the fence reads it. It decides nothing: stage 1
// compares, and the gate keeps reading the central config.
type Watch struct {
	Cfg     *config.Config
	Metrics Recorder
	Log     *slog.Logger

	mu    sync.RWMutex
	state map[string]Snapshot
}

// Observe reads one file. It logs only when the file or its result changes: the fence reads every
// five minutes. The load-error counter counts every failed read, so a rate shows it is still bad.
func (w *Watch) Observe(ctx context.Context, repository string, body []byte) {
	rc := w.listed(repository)
	if rc == nil {
		return
	}
	sum := sha256.Sum256(body)
	s := Snapshot{Hash: hex.EncodeToString(sum[:])}
	f, err := Parse(body)
	if err == nil {
		s.HasClasses = f.Classes != nil
		err = Validate(f, w.Cfg)
	}
	switch {
	case errors.Is(err, ErrGuardrail):
		w.Metrics.PolicyLoadError(ctx, repository, ReasonGuardrail)
	case err != nil:
		w.Metrics.PolicyLoadError(ctx, repository, ReasonInvalid)
	case s.HasClasses:
		s.Divergences = Compare(rc, f, w.Cfg)
		w.Metrics.PolicyDivergence(ctx, repository, len(s.Divergences))
	default:
		w.Metrics.PolicyDivergence(ctx, repository, 0)
	}
	s.Err = err
	w.mu.Lock()
	if w.state == nil {
		w.state = map[string]Snapshot{}
	}
	key := strings.ToLower(repository)
	prev, seen := w.state[key]
	w.state[key] = s
	w.mu.Unlock()
	if !seen || prev.Hash != s.Hash || !slices.Equal(prev.Divergences, s.Divergences) {
		w.log().Info("repository merge policy read", "repository", repository, "hash", s.Hash,
			"classes", s.HasClasses, "err", err, "divergences", s.Divergences)
	}
}

// Snapshot is the last read of repository.
func (w *Watch) Snapshot(repository string) (Snapshot, bool) {
	w.mu.RLock()
	defer w.mu.RUnlock()
	s, ok := w.state[strings.ToLower(repository)]
	return s, ok
}

func (w *Watch) listed(repository string) *config.Repository {
	for _, r := range w.Cfg.Repos() {
		if strings.EqualFold(r.Name, repository) {
			return &r
		}
	}
	return nil
}

func (w *Watch) log() *slog.Logger {
	if w.Log == nil {
		return slog.New(slog.DiscardHandler)
	}
	return w.Log
}
```

- [ ] **Step 4: Implement the metrics**

In `fmetrics.go`, add to `Set`: `policyLoadErrors metric.Int64Counter` and `policyDivergence metric.Int64Gauge`. Register them in `New`, beside `s.owned`, following its shape:

```go
s.policyLoadErrors, err = meter.Int64Counter("agent_factory_policy_load_errors_total",
	metric.WithDescription("Reads of a repository's merge policy that failed: invalid, or over a guardrail."))
check(err)
s.policyDivergence, err = meter.Int64Gauge("agent_factory_policy_central_divergence",
	metric.WithDescription("Classes on which a repository's merge policy differs from the central config, as last read."))
check(err)
```

Add the methods beside `RepositoryOwned`:

```go
func policyLoadReasons() []string { return []string{"invalid", "guardrail_mismatch"} }

// PolicyLoadError counts a failed read of repository's merge policy; a reason outside the list is
// not counted.
func (s *Set) PolicyLoadError(ctx context.Context, repository, reason string) {
	if !slices.Contains(policyLoadReasons(), reason) {
		return
	}
	s.policyLoadErrors.Add(ctx, 1, metric.WithAttributes(attribute.String("repository", s.repository(repository)), attribute.String("reason", reason)))
}

// PolicyDivergence records how many classes differ from the central config (stage 1's exit: 0).
func (s *Set) PolicyDivergence(ctx context.Context, repository string, n int) {
	s.policyDivergence.Record(ctx, int64(n), metric.WithAttributes(attribute.String("repository", s.repository(repository))))
}
```

`maku_factory_policy_central_divergence` is not in the spec's metric table. It is this plan's addition, because stage 1 has an exit criterion no listed metric can show, and it is bounded by repository.

- [ ] **Step 5: Wire it behind the flag**

In `internal/app/factory.go`, directly after the `fenced` literal:

```go
// Stage 1 (merge policy): observed and compared, deciding nothing.
if cfg.PolicyManagement.Read {
	fenced.OnFile = (&mergepolicy.Watch{Cfg: cfg, Metrics: m, Log: log}).Observe
}
```

Add the import. `*fmetrics.Set` satisfies `mergepolicy.Recorder` structurally.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `ulimit -v 16000000; timeout 600 go test -p 1 ./internal/factory/mergepolicy/ ./internal/factory/fmetrics/ ./internal/factory/fence/ ./internal/app/`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add internal/factory/mergepolicy internal/factory/fmetrics internal/app/factory.go
git commit -m "feat(factory): observe each owned repository's merge policy behind policyManagement.read"
```

### Task 7: `maku policy export` and `maku policy check`

**Files:**
- Create: `internal/app/maku_policy.go`
- Modify: `internal/app/maku.go` (the `run` switch, and `makuUsage`)
- Test: `internal/app/maku_policy_test.go`
- Create: `internal/app/testdata/policy-factory.yaml`, a minimal valid factory config

**Interfaces:**
- Consumes: `config.Load`, `mergepolicy.Export`, `Marshal`, `Parse`, `Validate`, `Compare`
- Produces:
  - `maku policy export --config <file> --repository <owner/name>`: writes the policy file to stdout
  - `maku policy check --config <file> --repository <owner/name> <policy-file>`: prints `equivalent` and returns nil, or returns an error naming each problem. Neither touches the network nor needs `maku configure`.

- [ ] **Step 1: Create the config fixture**

Copy `internal/factory/config/testdata/sponsored.yaml` to `internal/app/testdata/policy-factory.yaml`, then add a `harnessProfiles` block holding `plain: {}` and `adopted-none: {template: none}`. Remove any key tied to files on disk that `config.Load` would refuse. Confirm with a throwaway `config.Load` in the test of Step 2.

- [ ] **Step 2: Write the failing test**

```go
// SPDX-License-Identifier: Apache-2.0

package app

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Smana/maku/internal/factory/config"
)

const policyConfig = "testdata/policy-factory.yaml"

func policyRepo(t *testing.T) string {
	t.Helper()
	c, err := config.Load(policyConfig)
	if err != nil {
		t.Fatal(err)
	}
	return c.Repos()[0].Name
}

func TestPolicyExportThenCheck(t *testing.T) {
	repo := policyRepo(t)
	var out bytes.Buffer
	m := Maku{Dir: t.TempDir(), Out: &out, Err: &out}
	if err := m.run(t.Context(), []string{"policy", "export", "--config", policyConfig, "--repository", repo}); err != nil {
		t.Fatalf("%v\n%s", err, out.String())
	}
	file := filepath.Join(t.TempDir(), "agent-factory.yaml")
	if err := os.WriteFile(file, out.Bytes(), 0o600); err != nil {
		t.Fatal(err)
	}
	out.Reset()
	if err := m.run(t.Context(), []string{"policy", "check", "--config", policyConfig, "--repository", repo, file}); err != nil {
		t.Fatalf("%v\n%s", err, out.String())
	}
	if !strings.Contains(out.String(), "equivalent") {
		t.Fatalf("%s", out.String())
	}
}

func TestPolicyCheckNamesWhatIsWrong(t *testing.T) {
	repo := policyRepo(t)
	file := filepath.Join(t.TempDir(), "agent-factory.yaml")
	if err := os.WriteFile(file, []byte("factory: aws-0\nclasses: {docs-links: {mode: live, author: agents, harness: plain}}\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	err := Maku{Dir: t.TempDir(), Out: &out, Err: &out}.run(t.Context(), []string{"policy", "check", "--config", policyConfig, "--repository", repo, file})
	if err == nil || !strings.Contains(err.Error(), "revert") {
		t.Fatalf("got %v", err)
	}
}

func TestPolicyRefusesAnUnlistedRepository(t *testing.T) {
	var out bytes.Buffer
	err := Maku{Dir: t.TempDir(), Out: &out, Err: &out}.run(t.Context(), []string{"policy", "export", "--config", policyConfig, "--repository", "o/nope"})
	if err == nil || !strings.Contains(err.Error(), "not listed") {
		t.Fatalf("got %v", err)
	}
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `go test -p 1 -run TestPolicy ./internal/app/`
Expected: FAIL: `unknown command "policy"`.

- [ ] **Step 4: Implement**

In `maku.go`'s `run` switch, beside `case "skill":`:

```go
case "policy":
	return r.policy(args)
```

Add one line to `makuUsage`: `  policy export|check   write or check a repository's merge policy file, offline`.

`internal/app/maku_policy.go`:

```go
// SPDX-License-Identifier: Apache-2.0

package app

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// policy is `maku policy`: offline, against a factory config file, for the migration's export
// and for a repository's own CI.
func (r Maku) policy(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("policy export or policy check\n%s", makuUsage)
	}
	verb, args := args[0], args[1:]
	fs := flag.NewFlagSet("policy "+verb, flag.ContinueOnError)
	cfgPath := fs.String("config", "", "the factory config file")
	repository := fs.String("repository", "", "owner/name")
	pos, err := flags(fs, args)
	if err != nil {
		return err
	}
	if *cfgPath == "" || *repository == "" {
		return errors.New("policy: --config and --repository are required")
	}
	cfg, err := config.Load(*cfgPath)
	if err != nil {
		return err
	}
	var rc *config.Repository
	for _, c := range cfg.Repos() {
		if strings.EqualFold(c.Name, *repository) {
			rc = &c
		}
	}
	if rc == nil {
		return fmt.Errorf("policy: %s is not listed in %s", *repository, *cfgPath)
	}
	switch verb {
	case "export":
		f, err := mergepolicy.Export(rc, cfg)
		if err != nil {
			return err
		}
		raw, err := mergepolicy.Marshal(f)
		if err != nil {
			return err
		}
		_, err = r.Out.Write(raw)
		return err
	case "check":
		if len(pos) != 1 {
			return errors.New("policy check takes one policy file")
		}
		raw, err := os.ReadFile(filepath.Clean(pos[0]))
		if err != nil {
			return err
		}
		f, err := mergepolicy.Parse(raw)
		if err != nil {
			return err
		}
		if err := mergepolicy.Validate(f, cfg); err != nil {
			return err
		}
		if d := mergepolicy.Compare(rc, f, cfg); len(d) > 0 {
			return fmt.Errorf("policy: not equivalent to the central config:\n%s", strings.Join(d, "\n"))
		}
		_, err = fmt.Fprintln(r.Out, "equivalent")
		return err
	}
	return fmt.Errorf("policy: unknown verb %q", verb)
}
```

`Repos()` may return a copy, so `rc = &c` must point at the loop's per-iteration variable, which Go 1.22 and later give.

- [ ] **Step 5: Run the test to verify it passes**

Run: `go test -p 1 -run TestPolicy ./internal/app/`
Expected: PASS

- [ ] **Step 6: Run the full gate and commit**

Run: `ulimit -v 16000000; timeout 1500 task check`
Expected: exit 0. Keep the output for the pull request.

```bash
git add internal/app
git commit -m "feat(maku): policy export and policy check, offline"
```

Open the Maku pull request. Its merge and the release are the owner's.

### Task 8: Pin the release and describe the profiles in ai-native-ref

Starts only after a Maku release holds Tasks 1 to 7. In a worktree of this repository, branched from `origin/main`.

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml`, plus whatever `test-agent-factory-pins.py` requires for a pin bump
- Test: `scripts/ci/tests/test-agent-merge-policy-profiles.py`

**Interfaces:**
- Consumes: the Maku release's `harnessProfiles` key
- Produces: three profiles, `plain`, `checked`, `adopted-none`. `policyManagement.read` stays absent here; Task 10 turns it on.

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
# requires: python3
"""Every central class has a harness profile to export to, or stage 1's export fails at migration."""
import pathlib
import sys

import yaml

values = yaml.safe_load(yaml.safe_load(
    pathlib.Path("tooling/base/agent-factory/helm-values-configmap.yaml").read_text())["data"]["values.yaml"])
config = values["config"]
profiles = config.get("harnessProfiles", {})
missing = []
for repo in config["repositories"]:
    for name, cl in repo["classes"].items():
        if name == "review":
            continue
        adopted = "adopt" in (cl.get("author") or {})
        match = [p for p in profiles.values()
                 if (p.get("template") == "none") == adopted
                 and p.get("checks", False) == cl.get("checks", False)
                 and p.get("testFirst", False) == cl.get("testFirst", False)]
        if not match:
            missing.append(f"{repo['name']}: {name}")
if missing:
    sys.exit("no harness profile for: " + ", ".join(missing))
print("every class has a harness profile")
```

Register it the way `scripts/ci/run-tests.sh` registers its neighbours, if it does not discover tests by name.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 scripts/ci/tests/test-agent-merge-policy-profiles.py`
Expected: FAIL, naming every class.

- [ ] **Step 3: Implement**

Bump the factory image and chart pins to the release, as the last pin commit did (`git log -3 --format='%h %s' -- tooling/base/agent-factory/helm-values-configmap.yaml`). Under `config:`, beside `factory:`:

```yaml
      # Merge policy stage 1: what a repository's class may reference (MP2). Read only by the
      # observer, which is off: template, tier and loop stay what the factory selects today.
      harnessProfiles:
        plain: {}
        checked: {checks: true}
        adopted-none: {template: none}
```

- [ ] **Step 4: Run the full gate**

Run: `python3 scripts/ci/tests/test-agent-merge-policy-profiles.py && task check`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add tooling scripts flux
git commit -m "feat(agent-factory): maku with the policy reader, and the harness profiles"
```

### Task 9: Export the canary's file and prove equivalence offline

**Files:**
- Create in cloud-native-ref: the new content of `.github/agent-factory.yaml`, as a draft pull request. It must not merge before Task 10's precondition holds.

**Interfaces:**
- Consumes: `maku policy export`, `maku policy check`, Task 8's profiles

- [ ] **Step 1: Render the central config**

```bash
python3 - tooling/base/agent-factory/helm-values-configmap.yaml "$SCRATCH/factory.yaml" <<'EOF'
import sys, yaml
src, out = sys.argv[1:]
raw = yaml.safe_load(open(src))["data"]["values.yaml"].replace("${cluster_name}", "aws-0")
yaml.safe_dump(yaml.safe_load(raw)["config"], open(out, "w"), allow_unicode=True)
EOF
```

If `config.Load` refuses other Flux substitutions in that file, replace each with a valid placeholder in this same script. The file stays in the scratch directory: it is never committed.

- [ ] **Step 2: Export and check**

```bash
maku policy export --config "$SCRATCH/factory.yaml" --repository Smana/cloud-native-ref > "$SCRATCH/agent-factory.yaml"
maku policy check --config "$SCRATCH/factory.yaml" --repository Smana/cloud-native-ref "$SCRATCH/agent-factory.yaml"
```

Expected: `equivalent`. This is stage 1's offline exit for the canary. Keep the output for the pull request.

- [ ] **Step 3: Open the draft**

In a cloud-native-ref worktree, replace `.github/agent-factory.yaml` with the exported file, keeping the comment naming the fence at the top. Run its `task` gates. The path is a gate path, so a human merges it (MP14). Commit `feat(agent-factory): the classes in the repository's policy file, comparison only` and open it as a **draft**, stating in the description that it must not merge until Task 10's precondition holds, and why (R3).

### Task 10: The live proof (a session on aws-0)

Run in the next live session, per the offline-first rule. Nothing here can be proven before a factory reads a real GitHub file.

- [ ] **Step 1: Check the precondition**

Every factory whose repository list includes cloud-native-ref runs a Maku release holding Task 1. A factory older than that reads the new file as not owned and stops all work on the repository (R3).

```bash
kubectl --context aws-0 -n agent-system get deploy -o wide | grep -i factory
```

Expected: the release from Task 8 or later on each such cluster.

- [ ] **Step 2: Turn on the read switch**

Add `policyManagement: {read: true}` under `config:` for the session. It is a one-line pull request here, which the owner merges.

- [ ] **Step 3: Merge the canary's file, then read the signals**

The owner merges Task 9's draft. Within one fence period (5 minutes):

```promql
maku_factory_repository_owned{repository="Smana/cloud-native-ref"}             # 1: still owned
maku_factory_policy_central_divergence{repository="Smana/cloud-native-ref"}    # a series, at 0: a policy was compared
maku_factory_policy_load_errors_total{repository="Smana/cloud-native-ref"}     # no series
```

Read the raw counter, not a `rate`: it is born at 1 and moves only once per fence period, so a `rate` read this early shows nothing even for an invalid file. The exit needs both signals together, since the gauge keeps its last value after a failed read.

- [ ] **Step 4: Prove a real factory fails safe**

On a session branch, change one class's `harness:` to a name not in the list and let the factory read it through the file on the default branch only if the owner approves that merge. Otherwise replay the same bytes through `maku policy check` and record that this proof stayed offline. Expected when run live: a `guardrail_mismatch` count rises, `repository_owned` stays 1, intake continues and merge decisions are unchanged.

- [ ] **Step 5: Record the result**

Add `docs/runbooks/agent-factory/results-merge-policy-stage-1-<date>.md` with the signals above, and update the spec's status line. Stage 1 exits when both hold: the file is valid and equivalent on the canary, and owned stays 1.

---

## The owner's answers (2026-11-05)

The spec now carries all three.

- **Q1, who authors a policy pull request (plan 6)?** A prefilled GitHub edit link that the maintainer submits as their own pull request. No agents App pull request, dedicated policy App or stored user token. In this repository's `.policy.yml` (cloud-native-ref's is the same design: confirm when planning) `agent change approved by a maintainer` skips any change under `.github/` or to `.policy.yml`, so a pull request from the agents App can never merge. Plan 6 must settle two things first: a link edits one file, while the spec keeps the class policy and the policy-bot rule in one pull request; and GitHub documents no prefill for an existing file, so test `/edit/` with `?value=` on `github.com` before building on it.
- **Q2, symlinks and mode changes (plan 6)?** The `docs-broad` template drops the promise. It matches on paths and limits only, because `forge.FileStat` holds no mode.
- **Q3, the spec's shadow branch (plan 2)?** A shadow class with an approval subset and no grant records `would-require-approval` and does not go to a human. R1 still keeps AM4: the chart checks caps before the class mode on the would-arm path, which the spec has yet to absorb.

## Carried to later plans (from the final review of Tasks 1 to 7)

| To | Item |
|---|---|
| Plan 2 | Empty predicates read as absent and pass as equivalent (`allowedFiles: []`, `maxPatchFiles: 0`, `deny: [{}]`, `requiresApproval: [{}]`): refuse them before any gate reads the parser's output |
| Plan 2 | `errors.Is` across a joined error labels a mixed file `guardrail_mismatch`, and a negative cap is labelled guardrail too |
| Plan 2 | `review` stays central-only, so a non-zero central row compares as equal: say where its settings live |
| Plan 2 | `profileFor` picks the first matching profile by name, even one pinning a tier or loop: require those empty before anyone adds a pinned profile such as the spec's `docs-standard` |
| Plan 4 | Observe recompiles every pattern on each read. A crafted 256 KiB file cost 2.8 to 8 s per read in the review's probe, per replica, inside the sequential fence refresh. Skip work when the hash is unchanged, cap total patterns per file (`MaxPatterns` is per list), and correct R4 and `policy.go`'s bounds comment |
| Plan 4 | ai-native-ref's `scripts/ci/tests/test-agent-repo-files.py` requires its own fence file to be exactly `factory: aws-0`, which blocks its migration after the canary |
| Separate PR | `fence.Parse` decodes case-insensitively, so `Factory: aws-0` is owned and with `FACTORY:` and `Factory:` together ownership follows key order. Tightening it changes who owns a repository, so it needs its own release note |

## Self-review

- **Coverage:** the spec's stage 0 is the flag default, and stage 1 is Tasks 1 to 10. MP1, MP2, MP4, MP13 (ownership half) and MP15 (export half) are implemented here. Every other decision sits in the program table.
- **Placeholders:** none in code steps. Task 7 Step 1 and Task 9 Step 1 ask the implementer to adapt to what `config.Load` refuses, because that depends on files read at use.
- **Names:** `Resolve`, `Resolved`, `Validate`, `Compare`, `Export`, `Marshal`, `Watch.Observe`, `Recorder`, `ReasonInvalid`, `ReasonGuardrail`, `PolicyLoadError` and `PolicyDivergence` are consistent across tasks.
