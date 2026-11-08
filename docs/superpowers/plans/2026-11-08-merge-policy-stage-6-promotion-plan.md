# Merge policy self-service, stage 6 (Maku settings UI and promotion workflow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The spec's whole "Maku settings UI", behind `policyManagement.promotion` (off). Readers see each repository's classes, their evidence and each decision's timeline. Maintainers edit a class in a guided form or in the expert YAML view, then check it: strict validation against the central guardrails, the structural change, and a simulation with the gate's own evaluator. The answer is a file plus a GitHub edit link that the maintainer submits themselves. Maintainers also request promotion of an eligible shadow class, and operators approve exceptions below the evidence minimum.

**Architecture:** The factory owns everything that reads GitHub or decides. That covers the evidence (`internal/factory/evidence`, the shadow tally ported to Go), the editor's check, simulation and decision timeline (`internal/factory/policyview`, over `mergepolicy.Parse/Validate/Resolve/Structural` and `reconciler.Simulate`), and the routes `/v1/policy/*` on its API. The broker's human API forwards these with the caller's own token, the coordination gateway's pattern. It also records promotions and exceptions in two new PostgreSQL tables and serves the settings pages of the existing SPA. Nothing new runs.

**Tech Stack:** Go (Maku factory, broker, store), PostgreSQL through Atlas migrations and testcontainers, TypeScript (the `web/` SPA, Vitest), OpenTelemetry metrics.

**Spec:** [`docs/superpowers/specs/2026-11-04-merge-policy-self-service-design.md`](../specs/2026-11-04-merge-policy-self-service-design.md) ("Maku settings UI": routes, policy editor, simulation, promotion, decision timeline; "Storage, APIs, audit, and observability"; "Migration and rollout" stage 6; "Testing" Promotion and Web UI rows; MP7, MP8, MP14, MP16, MP17, MP18) · **Predecessor:** [the stage 3 plan](2026-11-07-merge-policy-stage-3-dual-evaluation-plan.md)

**Read against:** Maku `origin/main` `10c7747a`. Every code block is the compiled code of [Smana/maku#401](https://github.com/Smana/maku/pull/401), written test first. Long files are shown only in the part each task adds; the PR holds them whole.

## Deviation: built beside stages 4 and 5

Stages 4 (repository authority) and 5 (approval memory) are being built in parallel, and this plan does not depend on either. It starts from Maku `origin/main`, touches no gate path, and reads the repository's policy file only to check a proposal or propose a mode change. Until stage 4 cuts a repository over to its own policy, a merged editor or promotion pull request changes only what the comparison reads; the central config stays the merge authority, and the settings page says so. The timeline keeps a grant row and a grant-version row for stage 5, marked `reserved`. `policyManagement.promotion` stays `false` until stage 4 has cut the canary over.

## Global Constraints

- Maku never writes the policy, never authors the pull request and never edits `factory:` (MP1, MP14). The editor and promotion return a file and a GitHub edit link, and the check refuses a changed `factory:`.
- One evaluator (MP16): the editor's check runs the same `mergepolicy.Parse`, `Validate`, `Resolve` and `Structural` as the policy read and `maku policy diff`, and its simulation runs `reconciler.Simulate`, as `maku policy simulate` does (`internal/app/maku_policy.go`), behind `policyManagement.simulation`.
- `policyManagement.promotion` defaults to off. While off, the factory registers no `/v1/policy/*` route and the broker no `/settings*` or `/api/policy/*` route. Each answers exactly as a path that never existed (a test compares the bytes), and nothing reads GitHub, the factory or the store.
- Authorization is enforced server side, per handler (MP17), with one test row per role per handler on both the factory and the broker. A reader is anyone who reads the repository on GitHub. A maintainer has `repoaccess.CanWrite` and may check, get edit links, request promotion and ask for exceptions. An operator is listed in `policyManagement.operators` and decides exceptions.
- The Go evidence agrees with `scripts/shadow-merge-tally.sh` on every fixture of `scripts/testdata/tally/`; the tests read those files.
- Metric labels stay bounded (MP18): `repository` and `class` only as the factory's evidence named them, and `change` from a closed list.
- Request bodies are bounded, at 8 KiB, or the policy file's 256 KiB for a check, and unknown fields are refused. CSRF protection is the authenticator's `Origin` check.
- Every settings route loads directly (the SPA fallback) and has Vitest coverage; the bundle is rebuilt and `task ui:check` passes. One screenshot per page, taken with fixtures, lives on the orphan branch `screenshots/merge-policy-stage-6`, never in the PR.
- Maku: `task check` exits 0, every file carries the SPDX line, and commits are conventional, in English, with no trailers. Test runs are wrapped in `systemd-run --user --scope -q -p MemoryMax=6G`.

## Rulings this plan takes from reading the code

| # | The spec says | The code says | This plan |
|---|---|---|---|
| P1 | Evidence: clean decisions, bad mature outcomes, Clopper-Pearson bound, reviewer attribution, drill status | `scripts/shadow-merge-tally.sh` computes all of them from GitHub (`:44` `limit=500`, `:80` `$drilled`, `:128` the bound), in two modes. The broker has no reader for pull requests; the factory has one per repository | The factory computes it. `internal/factory/evidence` ports both modes, `--strictness` and `scripts/clopper-pearson.py:11`, tested on the script's own fixtures. The broker forwards it with the caller's token, as it does coordination (`internal/humanapi/coordination_write.go:21`) |
| P2 | "Drill passed" | No drill state exists beside the tally's count. A drill is a revert labelled `factory/drill` (AM6, `docs/factory.md:858`, `scripts/shadow-merge-tally.sh:76`) | `drill` is `passed` when a merged `factory/drill` revert targets one of the class's judged pull requests or merges; `open` when such a revert exists but is still open; else `none`. This is an existing source, so no operator attestation is added |
| P3 | Bad mature outcomes | Shadow classes with a monitor get `factory/merged:<class>` on every merge, so `--outcomes` reads them | `bad` is `--outcomes`' bad among mature, conclusive merges. `immature` counts merges younger than the class's `followUpWindow` (168h without a monitor, the script's default). `pending` counts mature merges that are not conclusive |
| P4 | Widening keeps 29/46/61 | The script's test proves 0 bad in 29, 1 in 46 and 2 in 61 stay under 10% | Reported only, as a three-step ladder: each step is reached with that many conclusive merges and at most 0, 1 or 2 bad. `widen` is true when the bound is under 0.10 |
| P5 | Operators may require stronger evidence; weaker needs an exception | `MergeGuardrails` (`internal/factory/config/mergepolicy.go:49`) has caps only | Adds `mergeGuardrails.minPromotionEvidence`: 0 means 20, and below 20 is refused. An exception lowers it per request, never in config |
| P6 | Operators approve exceptions | No operator list exists: `maintainers` are per repository, and the human API's `agents-admin` is a ZITADEL group | Adds `policyManagement.operators` (GitHub logins), which the broker reads with the factory's type, the same way it reads `coordination` (`internal/config/config.go:505`) |
| P7 | "Prefilled GitHub edit link" | GitHub's `/edit/<branch>/<path>` takes no content for an existing file; only `/new/` takes `value=` | The answer carries the whole proposed file, plus the changed line for a promotion, and the edit link on the default branch. The page shows the file with a copy button |
| P8 | `policy_promotions`: request, evidence, threshold, approver, PR, outcome; insert plus terminal state | `approvals` moves once, out of `pending`, enforced by trigger (`20261005120000_approvals.sql:49`) | `requested` → `pr_opened` (names its pull request) → `merged` or `abandoned`; `requested` may also go straight to `abandoned`. One open request per class (partial unique index). The approver is the human who merges on GitHub; Maku records `closed_by` for each move |
| P9 | `operator_exceptions`: request, approver, justification, scope, expiry | — | A maintainer requests one, giving `minimum` and a justification of 20 to 2,000 characters. An operator decides it once. An approval lasts 14 days and carries a promotion only for its own class and minimum, checked by trigger. It waives the count only: bad outcomes and the drill still block |
| P10 | `maku_factory_policy_changes_total{repository,class,change}` | The broker writes the promotion records, and its families are `maku_rooms_*` (`internal/metrics/metrics.go:313`) | Named `maku_rooms_policy_changes_total`, with `change` one of `promotion_requested`, `promotion_pr_opened`, `promotion_merged`, `promotion_abandoned`, `exception_requested`, `exception_approved`, `exception_refused`. The structural changes (tightening, relaxation, demotion) are counted when stage 4 decides on them |
| P11 | Simulate "historical PRs and synthetic fixtures"; show the strictness counterfactual | `reconciler.Simulate` (`internal/factory/reconciler/simulate.go:78`) decides `Case`s, whose full `ArmInputs` exist only in the conformance fixtures; a historical PR's record holds its rows' readings, not its inputs | The simulation runs on the embedded conformance fixtures (`reconciler.ConformanceCases`), exactly what `maku policy simulate` runs on (`internal/app/maku_policy.go`). Each row says whether the fixture still conforms. History supplies the strictness counterfactual (`--strictness` on the class's recent decisions) |
| P12 | Structural diff against the current policy | Before stage 4 most repositories declare their classes centrally | The proposal is compared with the file's classes when it declares valid ones, else with the central classes as `mergepolicy.Export` writes them |
| P13 | The guided form edits conditions, deny, approval subset, limits, monitor, harness | The vocabulary includes `any` branches and an `oracle` leaf whose form would be its own design | The form edits every `all` leaf except `oracle`, plus deny, `requiresApproval`, limits, `monitor.followUpWindow`, mode, author/adopt and the harness, picked from the central list. It keeps `any` branches and `oracle` untouched, and the page says to edit them in the expert view, which takes the whole file |
| P14 | Decision timeline: base, author, class, conditions, deny/approval, grant, breaker/cap, verdict, every revision, links to the policy commit and the comment | The decision record (`internal/factory/decision/decision.go:41`) holds the rows' readings, the verdict, `paused`/`capped`, and, with dual evaluation, the policy's hash. It holds no per-base-row result and no commit | The timeline walks the stages in gate order. Each stage before the one that decided passed, that stage is refused (its reason maps to a stage), and later ones are not reached. Revisions show what the record holds; guardrails and profiles are the pod's config, bound by its checksum. It links the decision's comment and the policy file's commit history |
| P15 | Settings routes, SPA on direct load | `GET /r/{id}` serves the index (`internal/humanapi/server.go:220`) | Serves `/settings`, `/settings/merge-policies`, `/settings/merge-policies/{owner}/{name}`, `/settings/merge-policies/{owner}/{name}/decisions/{pr}` and `/settings/evidence`, registered only while the switch is on. `/settings/approval-memory` belongs to stage 5 |
| P16 | Evidence freshness | One read is about four searches plus one per class merge | Reads 180 days back (the decision index's retention), cached 10 minutes per repository and replica, one read at a time. A truncated read (over 500 records, or unread labels) is refused, never served short |

## Files

| File | Responsibility |
|---|---|
| `internal/factory/config/mergepolicy.go`, `internal/config/config.go` | `Promotion`, `Operators`, `MinPromotionEvidence`; the broker reads the key |
| `internal/factory/evidence/evidence.go` | `Shadow` (and its strictness), `Outcomes`, `UpperBound`, `Evaluate` |
| `internal/factory/evidence/promote.go`, `service.go` | `Propose`; `Service.Report`, including the editor's inputs |
| `internal/factory/forge/records.go` | `MergedRecords`, `RevertRecords`, `AnyMerged` |
| `internal/factory/reconciler/conformance.go` | `ConformanceCases`: the fixtures, embedded |
| `internal/factory/policyview/preview.go`, `timeline.go`, `service.go` | `Check`, `Decisions`, `Service` |
| `internal/factory/api/evidence.go`, `access.go`, `server.go`; `internal/app/factory.go` | `/v1/policy/{evidence,repositories,preview,decisions}`; `CanRead`; the wiring |
| `internal/store/migrations/20261108120000_policy_promotions.sql`, `internal/store/policy.go` | The two tables and their methods |
| `internal/runrequest/coordination.go`, `policy.go` | `call` (extracted); the four forwards |
| `internal/metrics/metrics.go` | `maku_rooms_policy_changes_total` |
| `internal/humanapi/policy.go`, `server.go`; `internal/app/broker.go` | The settings routes and the workflow |
| `web/src/settings.ts`, `web/src/policy-editor.ts`, `web/src/main.ts`, `web/src/app.css` | The pages, the editor, the timeline |
| `docs/factory.md`, `docs/operations.md`, `docs/api.md`, `docs/web-ui.md` | The switch, the evidence, the editor, the timeline, the routes, the tables, the metric |

---

### Task 1: The switch, the operators, the minimum

**Files:** Modify `internal/factory/config/mergepolicy.go` and `internal/config/config.go`. Test in `internal/factory/config/mergepolicy_test.go` and `internal/config/config_test.go`.

- [ ] **Step 1: Write the failing tests**

```go
// MP7: twenty clean decisions unless the operators raise it; 0 is the default, never "none".
func TestMinPromotionEvidenceDefaultsToTwenty(t *testing.T) {
	if got := (MergeGuardrails{}).MinPromotion(); got != 20 || DefaultMinPromotionEvidence != 20 {
		t.Fatal(got)
	}
	if got := (MergeGuardrails{MinPromotionEvidence: 46}).MinPromotion(); got != 46 {
		t.Fatal(got)
	}
}

// IsOperator is case-insensitive, as GitHub logins are.
func TestIsOperator(t *testing.T) {
	pm := PolicyManagement{Operators: []string{"Smana"}}
	if !pm.IsOperator("smana") || pm.IsOperator("") || pm.IsOperator("other") {
		t.Fatal(pm)
	}
}

// and in TestHarnessProfilesAndGuardrailsValidate's table:
		"promotion alone":  {Config{PolicyManagement: PolicyManagement{Promotion: true}}, ""},
		"an operator":      {Config{PolicyManagement: PolicyManagement{Operators: []string{"Smana"}}}, ""},
		"a bad operator":   {Config{PolicyManagement: PolicyManagement{Operators: []string{"not a login"}}}, "operators"},
		"evidence at 20":   {Config{MergeGuardrails: MergeGuardrails{MinPromotionEvidence: 20}}, ""},
		"evidence raised":  {Config{MergeGuardrails: MergeGuardrails{MinPromotionEvidence: 29}}, ""},
		"evidence lowered": {Config{MergeGuardrails: MergeGuardrails{MinPromotionEvidence: 10}}, "minPromotionEvidence"},
```

```go
// Stage 6: the broker reads the factory's policyManagement key, off by default; promotion needs the
// factory, whose evidence it serves, and operators are GitHub logins.
func TestPolicyManagementConfig(t *testing.T) {
	cfg, err := Load(write(t, valid))
	if err != nil || cfg.PolicyManagement.Promotion || len(cfg.PolicyManagement.Operators) != 0 {
		t.Fatalf("omitted: %+v %v", cfg.PolicyManagement, err)
	}
	factory := "factoryURL: https://agent-factory.agent-system.svc.cluster.local:8080\n"
	cfg, err = Load(write(t, valid+factory+"policyManagement:\n  promotion: true\n  operators: [Smana]\n"))
	if err != nil || !cfg.PolicyManagement.Promotion || !cfg.PolicyManagement.IsOperator("smana") {
		t.Fatalf("%+v %v", cfg.PolicyManagement, err)
	}
	for name, body := range map[string]string{
		"promotion without the factory": valid + "policyManagement:\n  promotion: true\n",
		"an operator that is no login":  valid + factory + "policyManagement:\n  operators: [\"not a login\"]\n",
		"an unknown key":                valid + factory + "policyManagement:\n  promote: true\n",
	} {
		if _, err := Load(write(t, body)); err == nil || !strings.Contains(err.Error(), "promot") && !strings.Contains(err.Error(), "operators") {
			t.Errorf("%s: %v", name, err)
		}
	}
}
```

- [ ] **Step 2: Run** `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/config/ ./internal/config/`. Expect a build failure: unknown field `MinPromotionEvidence`.

- [ ] **Step 3: Implement**

```diff
@@ -8,6 +8,7 @@ import (
 	"maps"
 	"regexp"
 	"slices"
+	"strings"
 )

 // TemplateNone is the harness of an adopted class: another author's pull requests, no run.
@@ -52,6 +53,18 @@ type MergeGuardrails struct {
 	MaxPatchFiles    int      `json:"maxPatchFiles,omitempty"`
 	MaxModifiedLines int      `json:"maxModifiedLines,omitempty"`
 	MaxPerDay        int      `json:"maxPerDay,omitempty"`
+	// MinPromotionEvidence is the clean shadow decisions a class needs before it may be promoted to
+	// live (MP7): 0 is DefaultMinPromotionEvidence, and less is refused here. A promotion on less
+	// needs an operator's exception, recorded per request, never a lower number here.
+	MinPromotionEvidence int `json:"minPromotionEvidence,omitempty"`
+}
+
+// DefaultMinPromotionEvidence is MP7's twenty: zero bad in twenty bounds the bad rate at 13.9%.
+const DefaultMinPromotionEvidence = 20
+
+// MinPromotion is the clean decisions a promotion needs without an exception.
+func (g MergeGuardrails) MinPromotion() int {
+	return max(g.MinPromotionEvidence, DefaultMinPromotionEvidence)
 }

 // PolicyManagement holds the rollout's switches, all off by default (merge policy stages).
@@ -66,6 +79,31 @@ type PolicyManagement struct {
 	// Read last observed it, and records whether the two agree (stage 3). It decides nothing: the
 	// central decision is the one acted on. Needs Read.
 	DualEvaluation bool `json:"dualEvaluation,omitempty"`
+	// Promotion serves the promotion workflow (stage 6): each class's shadow evidence on the
+	// factory API, and the broker's settings pages and promotion records. It changes no class:
+	// a maintainer's own pull request does. The broker reads the same key with this type.
+	Promotion bool `json:"promotion,omitempty"`
+	// Operators are the GitHub logins who approve a promotion below minPromotionEvidence (MP7's
+	// exception). Read by the broker; none approves nothing.
+	Operators []string `json:"operators,omitempty"`
+}
+
+// IsOperator is whether login is one of the operators; GitHub logins are case-insensitive.
+func (pm PolicyManagement) IsOperator(login string) bool {
+	return login != "" && slices.ContainsFunc(pm.Operators, func(o string) bool { return strings.EqualFold(o, login) })
+}
+
+// Validate reports the switches' own rules; the factory and the broker, which reads the same key,
+// both apply it.
+func (pm PolicyManagement) Validate(bad func(string, ...any)) {
+	if pm.DualEvaluation && !pm.Read {
+		bad("policyManagement.dualEvaluation needs read: it evaluates the policy read observes")
+	}
+	for _, o := range pm.Operators {
+		if !githubLoginRE.MatchString(o) {
+			bad("policyManagement.operators: %q is not a GitHub login", o)
+		}
+	}
 }

 var profileRE = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$`)
@@ -92,10 +130,11 @@ func (c *Config) validateMergePolicy(bad func(string, ...any)) {
 			bad("harnessProfiles.%s: template none runs nothing, so it takes no other key", name)
 		}
 	}
-	if pm := c.PolicyManagement; pm.DualEvaluation && !pm.Read {
-		bad("policyManagement.dualEvaluation needs read: it evaluates the policy read observes")
-	}
+	c.PolicyManagement.Validate(bad)
 	g := c.MergeGuardrails
+	if n := g.MinPromotionEvidence; n != 0 && n < DefaultMinPromotionEvidence {
+		bad("mergeGuardrails.minPromotionEvidence %d is below %d (MP7): a weaker promotion is an operator's exception", n, DefaultMinPromotionEvidence)
+	}
 	for _, f := range []struct {
 		key string
 		n   int
```

```diff
@@ -503,6 +503,10 @@ type Config struct {
 	// Coordination is the factory's multi-repository switch, read here with the factory's own type
 	// and rules (v4 MR16): coordination_plan is listed only while it is not off.
 	Coordination fconfig.Coordination `json:"coordination,omitzero"`
+	// PolicyManagement is the factory's merge-policy switches, read here with the factory's own type
+	// (merge policy stage 6): promotion serves the settings pages and the promotion records, and
+	// operators approve exceptions. The broker reads nothing else of it.
+	PolicyManagement fconfig.PolicyManagement `json:"policyManagement,omitzero"`
 }

 // WebhookConfig is one subscriber (factory interfaces F6, O7): declared here because subscribers
@@ -725,6 +729,10 @@ func (c *Config) Validate() error {
 		// tool that would refuse every request.
 		errs = append(errs, fmt.Errorf("coordination.mode %s needs human.intake.plan.enabled: coordination_plan plans through its route", c.Coordination.Mode))
 	}
+	c.PolicyManagement.Validate(func(f string, a ...any) { errs = append(errs, fmt.Errorf(f, a...)) })
+	if c.PolicyManagement.Promotion && c.FactoryURL == "" {
+		errs = append(errs, errors.New("policyManagement.promotion needs factoryURL: the evidence is the factory's GET /v1/policy/evidence"))
+	}
 	return errors.Join(errs...)
 }

```

- [ ] **Step 4: Run the same command again**: PASS.

### Task 2: The tally in Go, MP7 on it

**Files:** Create `internal/factory/evidence/evidence.go`. Test in `internal/factory/evidence/evidence_test.go`, which reads `scripts/testdata/tally/*.json`.

- [ ] **Step 1: Write the failing tests**

```go
// SPDX-License-Identifier: Apache-2.0

package evidence

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"
)

// The fixtures are scripts/shadow-merge-tally_test.sh's: the Go count must agree with the script
// on every one of them (stage 6), so the evidence page and the operator's tally never disagree.
func fixture[T any](t *testing.T, name string) T {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("..", "..", "..", "scripts", "testdata", "tally", name))
	if err != nil {
		t.Fatal(err)
	}
	var v T
	if err := json.Unmarshal(b, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

var logins = Logins{Factory: "ogenki-agent-factory", Merger: "ogenki-agent-merger"}

const repo = "Smana/cloud-native-ref"

// shadow-merge-tally_test.sh's "decision record" block: --class docs-links on prs-decisions.json
// with reverts-drill.json.
func TestShadowAgreesWithTheTallyOnItsDecisionFixture(t *testing.T) {
	got := Shadow(fixture[[]PR](t, "prs-decisions.json"), fixture[[]Revert](t, "reverts-drill.json"), "docs-links", repo, logins)
	// --strictness: refused=3 refused_merged_unchanged=2, as the script's test says.
	want := ShadowTally{MergedUnchanged: 2, Changed: 1, Reverted: 1, Drill: 1, Refused: 3, RefusedMergedUnchanged: 2,
		Reviewers: []Reviewer{{Model: "glm-5.3", MergedUnchanged: 2}, {Model: "kimi-k3", Changed: 1}},
		Judged:    []int{21, 22, 23, 29}, Drilled: []int{21}}
	if fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}
}

// The adopted block: Renovate's pull requests, judged by WouldArmAdopted comments.
func TestShadowAgreesWithTheTallyOnTheAdoptedFixture(t *testing.T) {
	got := Shadow(fixture[[]PR](t, "prs-adopted.json"), nil, "deps-patch", repo, logins)
	if got.MergedUnchanged != 1 || got.Changed != 1 || got.Reverted != 0 || got.AutoMerged != 0 || got.Drill != 0 {
		t.Fatalf("%+v", got)
	}
}

// The script's first block, inline there: only the factory's head-pinned would-arm comments count,
// the newest decides, a merge at another head is changed, a merger's merge is auto_merged.
func TestShadowCountsOnlyTheFactorysHeadPinnedComments(t *testing.T) {
	wa := func(author, at, class, head string) Comment {
		ts, _ := time.Parse(time.RFC3339, at)
		return Comment{Author: Actor{Login: author}, CreatedAt: ts,
			Body: "would auto-merge: `" + class + "` <!-- agent-factory scope=x event=would-arm-1 head=" + head + " -->"}
	}
	pr := func(n int, head, by string, cs ...Comment) PR {
		return PR{Number: n, HeadRefOid: head, MergedBy: &Actor{Login: by}, Comments: cs}
	}
	prs := []PR{
		pr(1, "aaa", "Smana", wa("ogenki-agent-factory", "2026-10-01T00:00:00Z", "docs-links", "aaa")),
		pr(2, "bbb", "Smana", wa("app/ogenki-agent-factory", "2026-10-01T00:00:00Z", "docs-links", "aaa")),
		pr(3, "ccc", "Smana", wa("ogenki-agent-factory", "2026-10-01T00:00:00Z", "docs-links", "bbb"), wa("ogenki-agent-factory", "2026-10-02T00:00:00Z", "docs-links", "ccc")),
		pr(4, "ddd", "Smana", wa("someone", "2026-10-01T00:00:00Z", "docs-links", "ddd")),
		pr(5, "eee", "Smana", wa("ogenki-agent-factory", "2026-10-01T00:00:00Z", "review", "eee")),
		pr(6, "fff", "Smana", wa("ogenki-agent-factory", "2026-10-01T00:00:00Z", "docs-links", "fff")),
		pr(7, "abc", "ogenki-agent-merger", wa("ogenki-agent-factory", "2026-10-01T00:00:00Z", "docs-links", "abc")),
	}
	reverts := []Revert{{Body: "Reverts Smana/cloud-native-ref#6", State: "MERGED"},
		{Labels: []Label{{Name: "factory/revert-of:#1"}}, State: "CLOSED"}}
	got := Shadow(prs, reverts, "docs-links", repo, logins)
	if got.MergedUnchanged != 2 || got.Changed != 1 || got.Reverted != 1 || got.AutoMerged != 1 || !slices.Equal(got.Judged, []int{1, 2, 3, 6, 7}) {
		t.Fatalf("%+v", got)
	}
}

func outcomes(t *testing.T, fx string) OutcomeTally {
	t.Helper()
	name, rev := "prs.json", []Revert(nil)
	if fx != "" {
		name = "prs-" + fx + ".json"
	}
	if fx == "drill" {
		rev = fixture[[]Revert](t, "reverts-drill.json")
	}
	followed := map[int]bool{}
	if fx == "followup" {
		followed[100] = true // gh-stub.sh: only #100 has a follow-up
	}
	now := time.Date(2026, 10, 23, 0, 0, 0, 0, time.UTC)
	return Outcomes(fixture[[]PR](t, name), rev, followed, repo, logins, now, 168*time.Hour)
}

// Offline proof 7 of the script's test: the same counts, fixture by fixture.
func TestOutcomesAgreeWithTheTally(t *testing.T) {
	for fx, want := range map[string]OutcomeTally{
		"":           {Merges: 31, Mature: 30, Conclusive: 29, Inconclusive: 1},
		"regression": {Merges: 31, Mature: 30, Conclusive: 29, Inconclusive: 1, Bad: 1, Regression: 1},
		"followup":   {Merges: 31, Mature: 30, Conclusive: 29, Inconclusive: 1, Bad: 1, FollowUp: 1},
		"regcomment": {Merges: 31, Mature: 30, Conclusive: 29, Inconclusive: 1, Bad: 1, Regression: 1},
		"drill":      {Merges: 3, Mature: 3, Conclusive: 2, Inconclusive: 1, Bad: 1, Reverted: 1, Drill: 1},
	} {
		t.Run(fx, func(t *testing.T) {
			got := outcomes(t, fx)
			got.Numbers, got.Drilled = nil, nil
			if fmt.Sprint(got) != fmt.Sprint(want) {
				t.Fatalf("got  %+v\nwant %+v", got, want)
			}
		})
	}
}

// clopper-pearson.py's answers, to its six decimals, and the ladder the script's test proves.
func TestUpperBoundAgreesWithTheScript(t *testing.T) {
	for _, tc := range []struct {
		bad, n int
		want   string
	}{{0, 20, "0.139108"}, {0, 29, "0.098145"}, {0, 28, "0.101466"}, {1, 46, "0.099024"}, {2, 61, "0.099635"}, {3, 10, "0.606624"}} {
		if got := fmt.Sprintf("%.6f", UpperBound(tc.bad, tc.n)); got != tc.want {
			t.Errorf("UpperBound(%d, %d) = %s, want %s", tc.bad, tc.n, got, tc.want)
		}
	}
	if UpperBound(0, 0) != 1 {
		t.Fatal("nothing observed bounds nothing")
	}
}

// MP7: twenty merged unchanged at their heads, no bad mature outcome, a passed drill.
func TestEligibility(t *testing.T) {
	clean := func(n int) ShadowTally { return ShadowTally{MergedUnchanged: n, Judged: []int{21}} }
	drilled := []Revert{{Body: "Reverts " + repo + "#21", Labels: []Label{{Name: "factory/drill"}}, State: "MERGED"}}
	open := []Revert{{Body: "Reverts " + repo + "#21", Labels: []Label{{Name: "factory/drill"}}, State: "OPEN"}}
	for name, tc := range map[string]struct {
		sh       ShadowTally
		out      OutcomeTally
		reverts  []Revert
		min      int
		eligible bool
		blockers []string
		drill    string
	}{
		"twenty, clean, drilled":   {clean(20), OutcomeTally{}, drilled, 20, true, nil, DrillPassed},
		"nineteen":                 {clean(19), OutcomeTally{}, drilled, 20, false, []string{BlockBelowMinimum}, DrillPassed},
		"a raised minimum":         {clean(20), OutcomeTally{}, drilled, 29, false, []string{BlockBelowMinimum}, DrillPassed},
		"a bad mature outcome":     {clean(20), OutcomeTally{Bad: 1}, drilled, 20, false, []string{BlockBadOutcome}, DrillPassed},
		"no drill":                 {clean(20), OutcomeTally{}, nil, 20, false, []string{BlockNoDrill}, DrillNone},
		"a drill not yet merged":   {clean(20), OutcomeTally{}, open, 20, false, []string{BlockNoDrill}, DrillOpen},
		"everything short at once": {clean(3), OutcomeTally{Bad: 2}, nil, 20, false, []string{BlockBelowMinimum, BlockBadOutcome, BlockNoDrill}, DrillNone},
	} {
		t.Run(name, func(t *testing.T) {
			e := Evaluate(tc.sh, tc.out, tc.reverts, repo, tc.min)
			if e.Eligible != tc.eligible || !slices.Equal(e.Blockers, tc.blockers) || e.Drill != tc.drill || e.Minimum != tc.min {
				t.Fatalf("%+v", e)
			}
		})
	}
}

// The widening ladder (MP7: 29/46/61) is reported, never acted on: each step tolerates one more
// bad outcome among the mature, conclusive merges.
func TestTheWideningLadder(t *testing.T) {
	e := Evaluate(ShadowTally{}, OutcomeTally{Merges: 50, Mature: 47, Conclusive: 46, Inconclusive: 1, Bad: 1}, nil, repo, 20)
	want := []Step{{Merges: 29, MaxBad: 0}, {Merges: 46, MaxBad: 1, Reached: true}, {Merges: 61, MaxBad: 2}}
	if !slices.Equal(e.Ladder, want) || !e.Widen || e.Immature != 3 || e.Pending != 1 {
		t.Fatalf("%+v", e)
	}
	if e := Evaluate(ShadowTally{}, OutcomeTally{Conclusive: 28}, nil, repo, 20); e.Widen || e.Ladder[0].Reached {
		t.Fatalf("0 in 28 is not under 10%%: %+v", e)
	}
}
```

- [ ] **Step 2: Run** `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/evidence/`. Expect a build failure: undefined `Shadow`.

- [ ] **Step 3: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

// Package evidence is a class's promotion evidence (merge policy stage 6, MP7): the count
// scripts/shadow-merge-tally.sh makes, in Go, from the same pull request records. Shadow is the
// script's default mode (merged unchanged at the judged head, per reviewer model), Outcomes its
// --outcomes mode (bad mature outcomes and the Clopper-Pearson bound), Evaluate the eligibility
// MP7 sets. Pure: the caller reads GitHub, and the tests read the script's own fixtures.
package evidence

import (
	"maps"
	"math"
	"regexp"
	"slices"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Actor is a GitHub login as gh prints it: {"login": ...}.
type Actor struct {
	Login string `json:"login"`
}

// Label is a label as gh prints it.
type Label struct {
	Name string `json:"name"`
}

// Comment is one issue comment of a pull request.
type Comment struct {
	Author    Actor     `json:"author"`
	CreatedAt time.Time `json:"createdAt"`
	Body      string    `json:"body"`
}

// PR is a merged pull request in `gh pr list --json number,headRefOid,mergedBy,mergedAt,labels,comments`
// shape, the script's input.
type PR struct {
	Number     int       `json:"number"`
	HeadRefOid string    `json:"headRefOid"`
	MergedBy   *Actor    `json:"mergedBy"`
	MergedAt   time.Time `json:"mergedAt"`
	Labels     []Label   `json:"labels"`
	Comments   []Comment `json:"comments"`
}

// Revert is a pull request titled "Revert", any state: GitHub's revert body or the merger's
// factory/revert-of:#<n> label names what it reverts.
type Revert struct {
	Body   string  `json:"body"`
	Labels []Label `json:"labels"`
	State  string  `json:"state"`
}

// Logins are the factory App's comment author and the merger App's merge actor.
type Logins struct {
	Factory, Merger string
}

// login is the script's: lowercased, without app/ or [bot].
func login(s string) string {
	s = strings.TrimPrefix(strings.ToLower(s), "app/")
	return strings.TrimSuffix(s, "[bot]")
}

func (p PR) labelled(name string) bool {
	return slices.ContainsFunc(p.Labels, func(l Label) bool { return l.Name == name })
}

// The labels and markers the script reads.
const (
	labelDrill       = "factory/drill"
	labelRevertOf    = "factory/revert-of:#"
	labelRegression  = "factory/monitor:regression"
	stateClosed      = "CLOSED"
	stateMerged      = "MERGED"
	verdictHealthy   = "healthy"
	verdictRegressed = "regression"
)

var (
	wouldArm = regexp.MustCompile(`event=would-arm-[0-9]+ head=([0-9a-f]+)`)
	monitor  = regexp.MustCompile(`event=monitor-[0-9]+ verdict=([a-z]+)`)
	record   = regexp.MustCompile(`agent-factory-decision head=([^ ]+) class=([^ ]+) decision=([a-z_]+):([a-z_]+) files=([0-9]+|-)/([0-9]+) lines=([0-9]+|-)/([0-9]+) .*reviewer=([^ ]+) -->`)
)

// targets are the pull requests r reverts.
func (r Revert) targets(repo string) []int {
	var out []int
	re := regexp.MustCompile(`Reverts ` + regexp.QuoteMeta(repo) + `#([0-9]+)`)
	for _, m := range re.FindAllStringSubmatch(r.Body, -1) {
		if n, err := strconv.Atoi(m[1]); err == nil {
			out = append(out, n)
		}
	}
	for _, l := range r.Labels {
		if n, err := strconv.Atoi(strings.TrimPrefix(l.Name, labelRevertOf)); strings.HasPrefix(l.Name, labelRevertOf) && err == nil {
			out = append(out, n)
		}
	}
	return out
}

func (r Revert) drill() bool {
	return slices.ContainsFunc(r.Labels, func(l Label) bool { return l.Name == labelDrill })
}

// reverted are the pull requests an open or merged revert reverts, drills apart (AM6).
func reverted(reverts []Revert, repo string, drill bool) map[int]bool {
	out := map[int]bool{}
	for _, r := range reverts {
		if r.State == stateClosed || r.drill() != drill {
			continue
		}
		for _, n := range r.targets(repo) {
			out[n] = true
		}
	}
	return out
}

// own are the factory's comments of p matching re, oldest first; the newest is the last.
func own(p PR, factory string, re *regexp.Regexp) []Comment {
	var out []Comment
	for _, c := range p.Comments {
		if login(c.Author.Login) == login(factory) && re.MatchString(c.Body) {
			out = append(out, c)
		}
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].CreatedAt.Before(out[j].CreatedAt) })
	return out
}

// Reviewer is one reviewer model's share of the judged pull requests (AM10).
type Reviewer struct {
	Model           string `json:"model"`
	MergedUnchanged int    `json:"mergedUnchanged"`
	Changed         int    `json:"changed"`
}

// ShadowTally is the script's default mode for one class: each merged pull request whose newest
// factory would-arm comment names the class, by what became of the head it judged.
type ShadowTally struct {
	MergedUnchanged int        `json:"mergedUnchanged"`
	Changed         int        `json:"changed"`
	Reverted        int        `json:"reverted"`
	AutoMerged      int        `json:"autoMerged"`
	Drill           int        `json:"drill"`
	Reviewers       []Reviewer `json:"reviewers"`
	// Refused and RefusedMergedUnchanged are --strictness: the newest decisions a class row refused,
	// and those a human then merged unchanged at that head (the gate's too-strict side).
	Refused                int `json:"refused"`
	RefusedMergedUnchanged int `json:"refusedMergedUnchanged"`
	// Judged and Drilled are the pull request numbers, for the drill check.
	Judged  []int `json:"-"`
	Drilled []int `json:"-"`
}

// Shadow counts prs as `shadow-merge-tally.sh --class class` does.
func Shadow(prs []PR, reverts []Revert, class, repo string, l Logins) ShadowTally {
	rev, drilled := reverted(reverts, repo, false), reverted(reverts, repo, true)
	var t ShadowTally
	models := map[string]*Reviewer{}
	for _, p := range prs {
		t.strictness(p, class, l)
		mine := own(p, l.Factory, wouldArm)
		if len(mine) == 0 {
			continue
		}
		last := mine[len(mine)-1]
		if !strings.Contains(last.Body, "would auto-merge: `"+class+"`") {
			continue
		}
		head := wouldArm.FindStringSubmatch(last.Body)[1]
		by := ""
		if p.MergedBy != nil {
			by = login(p.MergedBy.Login)
		}
		t.Judged = append(t.Judged, p.Number)
		if drilled[p.Number] {
			t.Drill++
			t.Drilled = append(t.Drilled, p.Number)
		}
		model := "-"
		if m := record.FindStringSubmatch(last.Body); m != nil {
			model = m[9]
		}
		r := models[model]
		if r == nil {
			r = &Reviewer{Model: model}
			models[model] = r
		}
		switch {
		case by == login(l.Merger):
			t.AutoMerged++
		case rev[p.Number]:
			t.Reverted++
		case p.HeadRefOid == head:
			t.MergedUnchanged++
			r.MergedUnchanged++
		default:
			t.Changed++
			r.Changed++
		}
	}
	for _, m := range slices.Sorted(maps.Keys(models)) {
		if m != "-" {
			t.Reviewers = append(t.Reviewers, *models[m])
		}
	}
	return t
}

// strictRows are the class rows whose refusal --strictness counts.
var strictRows = []string{"patch_too_large", "file_not_allowed", "file_protected", "file_added_or_deleted", "class_mismatch",
	"holdout_red", "oracle_finding_open", "oracle_unrequested", "release_age_red"}

var handOff = regexp.MustCompile(`event=human-([a-z_]+)-[0-9]+`)

// strictness counts p as --strictness does: its newest factory decision record, when it is
// class's, refused by a class row (a hand-off takes the reason its event names).
func (t *ShadowTally) strictness(p PR, class string, l Logins) {
	rs := own(p, l.Factory, record)
	if len(rs) == 0 {
		return
	}
	body := rs[len(rs)-1].Body
	m := record.FindStringSubmatch(body)
	if m[2] != class {
		return
	}
	verdict, reason := m[3], m[4]
	if h := handOff.FindStringSubmatch(body); h != nil {
		verdict, reason = "human", h[1]
	}
	if verdict != "human" || !slices.Contains(strictRows, reason) {
		return
	}
	t.Refused++
	if p.HeadRefOid == m[1] && (p.MergedBy == nil || login(p.MergedBy.Login) != login(l.Merger)) {
		t.RefusedMergedUnchanged++
	}
}

// OutcomeTally is the script's --outcomes mode: what became of the class's merges.
type OutcomeTally struct {
	Merges       int `json:"merges"`
	Mature       int `json:"mature"`
	Conclusive   int `json:"conclusive"`
	Inconclusive int `json:"inconclusive"`
	Bad          int `json:"bad"`
	Reverted     int `json:"reverted"`
	FollowUp     int `json:"followUp"`
	Regression   int `json:"regression"`
	Drill        int `json:"drill"`
	// Numbers and Drilled are the merges' numbers, for the drill check.
	Numbers []int `json:"-"`
	Drilled []int `json:"-"`
}

// Outcomes counts the class's merges (labelled factory/merged:<class> or factory/auto-merged:<class>,
// one per number) as `--outcomes --window window` does at now; followed names the merges a merged
// pull request labelled factory/follow-up-of:#<n> fixed.
func Outcomes(merges []PR, reverts []Revert, followed map[int]bool, repo string, l Logins, now time.Time, window time.Duration) OutcomeTally {
	rev, drilled := reverted(reverts, repo, false), reverted(reverts, repo, true)
	cutoff := now.Add(-window)
	var t OutcomeTally
	seen := map[int]bool{}
	for _, p := range merges {
		if seen[p.Number] {
			continue
		}
		seen[p.Number] = true
		t.Merges++
		t.Numbers = append(t.Numbers, p.Number)
		verdict := "none"
		if v := own(p, l.Factory, monitor); len(v) > 0 {
			verdict = monitor.FindStringSubmatch(v[len(v)-1].Body)[1]
		}
		isRev, isFollow := rev[p.Number], followed[p.Number]
		isReg := p.labelled(labelRegression) || verdict == verdictRegressed
		bad := isRev || isFollow || isReg
		if drilled[p.Number] {
			t.Drill++
			t.Drilled = append(t.Drilled, p.Number)
		}
		if p.MergedAt.After(cutoff) {
			continue // immature: neither counts nor blocks
		}
		t.Mature++
		if verdict != verdictHealthy && verdict != verdictRegressed && !bad {
			t.Inconclusive++
			continue
		}
		t.Conclusive++
		if bad {
			t.Bad++
		}
		t.Reverted += b2i(isRev)
		t.FollowUp += b2i(isFollow)
		t.Regression += b2i(isReg)
	}
	return t
}

func b2i(b bool) int {
	if b {
		return 1
	}
	return 0
}

// UpperBound is clopper-pearson.py's one-sided 95% upper bound on a failure rate after bad
// failures in n: the p at which P(X <= bad) = 0.05, X ~ Binomial(n, p), by the same 60 bisections.
// n == 0 bounds nothing: 1.
func UpperBound(bad, n int) float64 {
	if n == 0 {
		return 1
	}
	lo, hi := 0.0, 1.0
	for range 60 {
		p := (lo + hi) / 2
		if cdf(bad, n, p) > 0.05 {
			lo = p
		} else {
			hi = p
		}
	}
	return hi
}

// cdf is P(X <= k), X ~ Binomial(n, p), each term in log space so a large n never overflows.
func cdf(k, n int, p float64) float64 {
	sum := 0.0
	for i := 0; i <= k; i++ {
		ln, _ := math.Lgamma(float64(n + 1))
		li, _ := math.Lgamma(float64(i + 1))
		lni, _ := math.Lgamma(float64(n - i + 1))
		sum += math.Exp(ln - li - lni + float64(i)*math.Log(p) + float64(n-i)*math.Log1p(-p))
	}
	return sum
}

// Budget is the class bad-rate budget the widening bound is compared with (MP7's 10%).
const Budget = 0.10

// The drill states: a factory/drill revert (AM6) of one of the class's pull requests merged, one
// still open, or none.
const (
	DrillPassed = "passed"
	DrillOpen   = "open"
	DrillNone   = "none"
)

// The reasons a class is not eligible, in this order.
const (
	BlockBelowMinimum = "below_minimum"
	BlockBadOutcome   = "bad_outcome"
	BlockNoDrill      = "no_drill"
)

// Step is one rung of the widening ladder (MP7): Merges mature, conclusive merges with at most
// MaxBad bad bound the bad rate under Budget.
type Step struct {
	Merges  int  `json:"merges"`
	MaxBad  int  `json:"maxBad"`
	Reached bool `json:"reached"`
}

// Evidence is a class's promotion evidence and MP7's verdict on it.
type Evidence struct {
	Shadow   ShadowTally  `json:"shadow"`
	Outcomes OutcomeTally `json:"outcomes"`
	// Clean is the shadow decisions merged unchanged at their exact heads; Bad the bad mature
	// outcomes; Immature the merges younger than the follow-up window; Pending the mature ones
	// with no verdict yet.
	Clean    int      `json:"clean"`
	Bad      int      `json:"bad"`
	Immature int      `json:"immature"`
	Pending  int      `json:"pending"`
	Bound    float64  `json:"bound"`
	Budget   float64  `json:"budget"`
	Widen    bool     `json:"widen"`
	Ladder   []Step   `json:"ladder"`
	Drill    string   `json:"drill"`
	Minimum  int      `json:"minimum"`
	Eligible bool     `json:"eligible"`
	Blockers []string `json:"blockers,omitempty"`
}

// Evaluate is MP7 on one class: eligible with at least minimum clean decisions, no bad mature
// outcome, and a passed drill on one of its pull requests.
func Evaluate(sh ShadowTally, out OutcomeTally, reverts []Revert, repo string, minimum int) Evidence {
	e := Evidence{Shadow: sh, Outcomes: out, Clean: sh.MergedUnchanged, Bad: out.Bad,
		Immature: out.Merges - out.Mature, Pending: out.Inconclusive,
		Bound: UpperBound(out.Bad, out.Conclusive), Budget: Budget, Minimum: minimum, Drill: DrillNone}
	e.Widen = e.Bound < Budget
	for i, n := range []int{29, 46, 61} {
		e.Ladder = append(e.Ladder, Step{Merges: n, MaxBad: i, Reached: out.Conclusive >= n && out.Bad <= i})
	}
	mine := map[int]bool{}
	for _, n := range slices.Concat(sh.Judged, out.Numbers) {
		mine[n] = true
	}
	for _, r := range reverts {
		if !r.drill() || r.State == stateClosed || !slices.ContainsFunc(r.targets(repo), func(n int) bool { return mine[n] }) {
			continue
		}
		if r.State == stateMerged {
			e.Drill = DrillPassed
		} else if e.Drill != DrillPassed {
			e.Drill = DrillOpen
		}
	}
	if e.Clean < minimum {
		e.Blockers = append(e.Blockers, BlockBelowMinimum)
	}
	if e.Bad > 0 {
		e.Blockers = append(e.Blockers, BlockBadOutcome)
	}
	if e.Drill != DrillPassed {
		e.Blockers = append(e.Blockers, BlockNoDrill)
	}
	e.Eligible = len(e.Blockers) == 0
	return e
}
```

- [ ] **Step 4: Run the same command again**: PASS. The counts match the script's test line for line, and `UpperBound` matches `clopper-pearson.py` to six decimals.

### Task 3: The proposal

**Files:** Create `internal/factory/evidence/promote.go`. Test in `promote_test.go`.

```go
// SPDX-License-Identifier: Apache-2.0

package evidence

import (
	"errors"
	"strings"
	"testing"
)

const policyFile = `# the canary's policy
factory: aws-0

classes:
  docs-links:
    mode: shadow   # promoted after the drill
    author: agents
    harness: docs-standard
  revert:
    mode: shadow
    author: agents
    harness: docs-standard
`

// Promotion changes one token, the class's mode, and nothing else of the file: comments, order
// and the other classes stay, so the maintainer's pull request reviews as a one-line diff.
func TestProposeChangesOnlyTheClassMode(t *testing.T) {
	got, line, err := Propose([]byte(policyFile), "docs-links")
	if err != nil {
		t.Fatal(err)
	}
	want := strings.Replace(policyFile, "    mode: shadow   # promoted", "    mode: live   # promoted", 1)
	if string(got) != want || line != 6 {
		t.Fatalf("line %d:\n%s", line, got)
	}
	if got, _, _ := Propose([]byte(policyFile), "revert"); !strings.Contains(string(got), "  revert:\n    mode: live\n") ||
		!strings.Contains(string(got), "docs-links:\n    mode: shadow") {
		t.Fatalf("%s", got)
	}
}

func TestProposeRefusesWhatIsNotAShadowClass(t *testing.T) {
	live := strings.Replace(policyFile, "mode: shadow   #", "mode: live   #", 1)
	quoted := strings.Replace(policyFile, "mode: shadow   #", `mode: "shadow"   #`, 1)
	for name, tc := range map[string]struct {
		file, class string
		want        error
	}{
		"absent":          {policyFile, "deps-patch", ErrNoClass},
		"already live":    {live, "docs-links", ErrNotShadow},
		"not a policy":    {"factory: aws-0\nclasses: [\n", "docs-links", ErrInvalidPolicy},
		"a quoted shadow": {quoted, "docs-links", nil},
	} {
		t.Run(name, func(t *testing.T) {
			_, _, err := Propose([]byte(tc.file), tc.class)
			if !errors.Is(err, tc.want) {
				t.Fatalf("%v, want %v", err, tc.want)
			}
		})
	}
}
```

```go
// SPDX-License-Identifier: Apache-2.0

package evidence

import (
	"bytes"
	"errors"
	"fmt"
	"slices"

	"go.yaml.in/yaml/v3"

	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// Propose's refusals.
var (
	ErrInvalidPolicy = errors.New("the repository's policy file does not parse")
	ErrNoClass       = errors.New("the repository's policy file declares no such class")
	ErrNotShadow     = errors.New("the class is not in shadow")
)

// Propose is file with class's mode changed from shadow to live and nothing else: the one-line
// change a maintainer submits as their own pull request (MP1, MP14). line is the 1-based line it
// changes. The result is parsed again, so a proposal is always a valid file whose class is live.
func Propose(file []byte, class string) (out []byte, line int, err error) {
	f, err := mergepolicy.Parse(file)
	if err != nil {
		return nil, 0, fmt.Errorf("%w: %w", ErrInvalidPolicy, err)
	}
	p, ok := f.Classes[class]
	switch {
	case !ok:
		return nil, 0, ErrNoClass
	case p.Mode != mergepolicy.ModeShadow:
		return nil, 0, ErrNotShadow
	}
	var doc yaml.Node
	if err := yaml.Unmarshal(file, &doc); err != nil || len(doc.Content) != 1 {
		return nil, 0, ErrInvalidPolicy
	}
	mode := child(child(child(doc.Content[0], "classes"), class), "mode")
	if mode == nil || mode.Kind != yaml.ScalarNode {
		return nil, 0, ErrNoClass
	}
	lines := bytes.SplitAfter(file, []byte("\n"))
	l := lines[mode.Line-1]
	col := mode.Column - 1
	token := []byte("shadow")
	if mode.Style&(yaml.DoubleQuotedStyle|yaml.SingleQuotedStyle) != 0 {
		col++ // the scalar's column is its opening quote's
	}
	if col+len(token) > len(l) || !bytes.Equal(l[col:col+len(token)], token) {
		return nil, 0, ErrNotShadow
	}
	lines[mode.Line-1] = slices.Concat(l[:col], []byte("live"), l[col+len(token):])
	out = bytes.Join(lines, nil)
	if g, err := mergepolicy.Parse(out); err != nil || g.Classes[class].Mode != mergepolicy.ModeLive {
		return nil, 0, fmt.Errorf("%w: the proposal does not read back as live", ErrInvalidPolicy)
	}
	return out, mode.Line, nil
}

// child is mapping node n's value under key, nil when n is no mapping or has no such key.
func child(n *yaml.Node, key string) *yaml.Node {
	if n == nil || n.Kind != yaml.MappingNode {
		return nil
	}
	for i := 0; i+1 < len(n.Content); i += 2 {
		if n.Content[i].Value == key {
			return n.Content[i+1]
		}
	}
	return nil
}
```

### Task 4: Reading GitHub as the tally does

**Files:** Create `internal/factory/forge/records.go`. Modify `internal/factory/forge/github_test.go` to add the fake's `records` hook. Test in `records_test.go`.

```go
// The records come back in the shape the tally reads from gh: a Bot's login with [bot], the
// newest comments, the labels, across pages.
func TestMergedRecordsReadEveryPageInTheTallysShape(t *testing.T) {
	r := newRig(t)
	var queries []string
	r.gh.records = func(q string, after any) string {
		queries = append(queries, q)
		if after == nil {
			return `{"data":{"search":{"pageInfo":{"hasNextPage":true,"endCursor":"c1"},"nodes":[{"number":21,"headRefOid":"a21",` +
				`"mergedAt":"2026-10-01T00:00:00Z","mergedBy":{"__typename":"User","login":"Smana"},` +
				`"labels":{"nodes":[{"name":"factory/merged:docs-links"}],"pageInfo":{"hasNextPage":false}},` +
				`"comments":{"nodes":[{"author":{"__typename":"Bot","login":"ogenki-agent-factory"},"createdAt":"2026-10-01T00:00:00Z","body":"x"}]}}]}}}`
		}
		return `{"data":{"search":{"pageInfo":{"hasNextPage":false},"nodes":[{"number":22,"headRefOid":"a22"}]}}}`
	}
	prs, err := r.g.MergedRecords(t.Context(), `author:app/ogenki-agents merged:>=2026-05-01`)
	if err != nil {
		t.Fatal(err)
	}
	if len(prs) != 2 || prs[0].Number != 21 || prs[0].MergedBy.Login != "Smana" || prs[0].Comments[0].Author.Login != "ogenki-agent-factory[bot]" ||
		!prs[0].MergedAt.Equal(time.Date(2026, 10, 1, 0, 0, 0, 0, time.UTC)) || prs[0].Labels[0] != (evidence.Label{Name: "factory/merged:docs-links"}) ||
		prs[1].MergedBy != nil {
		t.Fatalf("%+v", prs)
	}
	if queries[0] != "repo:Smana/demo is:pr is:merged author:app/ogenki-agents merged:>=2026-05-01" {
		t.Fatalf("%q", queries)
	}
	if b := r.gh.graphqlBodies(); !strings.Contains(b[len(b)-1], "comments(last: 50)") {
		t.Fatalf("the query: %s", b[len(b)-1])
	}
}

// A short read is refused, never counted: a pull request with unread labels, or more pages than
// the bound.
func TestRecordsPastTheirBoundAreRefused(t *testing.T) {
	r := newRig(t)
	r.gh.records = func(string, any) string {
		return `{"data":{"search":{"pageInfo":{"hasNextPage":false},"nodes":[{"number":1,"labels":{"nodes":[],"pageInfo":{"hasNextPage":true}}}]}}}`
	}
	if _, err := r.g.MergedRecords(t.Context(), ""); !errors.Is(err, ErrRecordsTruncated) {
		t.Fatalf("unread labels: %v", err)
	}
	r.gh.records = func(string, any) string {
		return `{"data":{"search":{"pageInfo":{"hasNextPage":true,"endCursor":"c"},"nodes":[]}}}`
	}
	if _, err := r.g.RevertRecords(t.Context()); !errors.Is(err, ErrRecordsTruncated) {
		t.Fatalf("endless pages: %v", err)
	}
}
```

```go
// SPDX-License-Identifier: Apache-2.0

package forge

import (
	"context"
	"errors"
	"fmt"

	"github.com/shurcooL/githubv4"

	"github.com/Smana/maku/internal/factory/evidence"
)

// ErrRecordsTruncated is a promotion-evidence read past its bound: records past it are unread, so
// the evidence would be short and is refused instead (stage 6).
var ErrRecordsTruncated = errors.New("forge: more pull request records than the evidence reads")

// recordPages bounds the record reads: shadow-merge-tally.sh's --limit 500, in pages of 50 small
// enough that the newest 50 comments of each stay a bounded answer. The newest comment decides every count, so
// older ones are never needed.
const recordPages = 10

type recordNode struct {
	PullRequest struct {
		Number     int
		HeadRefOid string
		State      string
		Body       string
		MergedAt   *githubv4.DateTime
		MergedBy   *actor
		Labels     struct {
			Nodes    []struct{ Name string }
			PageInfo struct{ HasNextPage bool }
		} `graphql:"labels(first: 50)"`
		Comments struct {
			Nodes []struct {
				Author    *actor
				CreatedAt githubv4.DateTime
				Body      string
			}
		} `graphql:"comments(last: 50)"`
	} `graphql:"... on PullRequest"`
}

// search runs q over at most recordPages pages and returns every pull request node.
func (g *GitHub) search(ctx context.Context, q string) ([]recordNode, error) {
	var out []recordNode
	var after *githubv4.String
	for range recordPages {
		var r struct {
			Search struct {
				Nodes    []recordNode
				PageInfo struct {
					HasNextPage bool
					EndCursor   githubv4.String
				}
			} `graphql:"search(type: ISSUE, first: 50, after: $after, query: $q)"`
		}
		err := g.v4.Query(ctx, &r, map[string]any{"q": githubv4.String(q), "after": after})
		g.mark(err)
		if err != nil {
			return nil, wrap("search pull request records", err)
		}
		for _, n := range r.Search.Nodes {
			if n.PullRequest.Labels.PageInfo.HasNextPage {
				return nil, ErrRecordsTruncated
			}
		}
		out = append(out, r.Search.Nodes...)
		if !r.Search.PageInfo.HasNextPage {
			return out, nil
		}
		c := r.Search.PageInfo.EndCursor
		after = &c
	}
	return nil, ErrRecordsTruncated
}

func labels(n recordNode) []evidence.Label {
	var out []evidence.Label
	for _, l := range n.PullRequest.Labels.Nodes {
		out = append(out, evidence.Label{Name: l.Name})
	}
	return out
}

// MergedRecords are the merged pull requests matching filter (search qualifiers the caller builds
// from config, never from a request), in the shape shadow-merge-tally.sh reads from gh.
func (g *GitHub) MergedRecords(ctx context.Context, filter string) ([]evidence.PR, error) {
	nodes, err := g.search(ctx, fmt.Sprintf("repo:%s/%s is:pr is:merged %s", g.owner, g.name, filter))
	if err != nil {
		return nil, err
	}
	out := make([]evidence.PR, 0, len(nodes))
	for _, n := range nodes {
		p := n.PullRequest
		pr := evidence.PR{Number: p.Number, HeadRefOid: p.HeadRefOid, Labels: labels(n)}
		if p.MergedAt != nil {
			pr.MergedAt = p.MergedAt.Time
		}
		if p.MergedBy != nil {
			pr.MergedBy = &evidence.Actor{Login: p.MergedBy.login()}
		}
		for _, c := range p.Comments.Nodes {
			pr.Comments = append(pr.Comments, evidence.Comment{Author: evidence.Actor{Login: c.Author.login()}, CreatedAt: c.CreatedAt.Time, Body: c.Body})
		}
		out = append(out, pr)
	}
	return out, nil
}

// RevertRecords are the pull requests titled Revert, any state: the script's reverts_of.
func (g *GitHub) RevertRecords(ctx context.Context) ([]evidence.Revert, error) {
	nodes, err := g.search(ctx, fmt.Sprintf("repo:%s/%s is:pr Revert in:title", g.owner, g.name))
	if err != nil {
		return nil, err
	}
	out := make([]evidence.Revert, 0, len(nodes))
	for _, n := range nodes {
		out = append(out, evidence.Revert{Body: n.PullRequest.Body, State: n.PullRequest.State, Labels: labels(n)})
	}
	return out, nil
}

// AnyMerged is whether a merged pull request matches filter: one follow-up search of the script.
func (g *GitHub) AnyMerged(ctx context.Context, filter string) (bool, error) {
	var r struct {
		Search struct{ IssueCount int } `graphql:"search(type: ISSUE, first: 1, query: $q)"`
	}
	err := g.v4.Query(ctx, &r, map[string]any{"q": githubv4.String(fmt.Sprintf("repo:%s/%s is:pr is:merged %s", g.owner, g.name, filter))})
	g.mark(err)
	if err != nil {
		return false, wrap("search merged pull requests", err)
	}
	return r.Search.IssueCount > 0, nil
}
```

### Task 5: The report, cached, with the editor's inputs

**Files:** Create `internal/factory/evidence/service.go`. Test in `service_test.go`.

```go
// The canary at its exit: twenty decisions merged unchanged, no bad outcome, a merged drill. The
// report proposes the one-line change and is served from the cache for TTL.
func TestServiceReportsAndProposes(t *testing.T) {
	now := time.Date(2026, 11, 8, 0, 0, 0, 0, time.UTC)
	src := &fakeSource{file: policyFile, found: true,
		merged:  map[string][]PR{"author:app/ogenki-agents": cleanPRs(20)},
		reverts: []Revert{{Body: "Reverts Smana/cloud-native-ref#100", Labels: []Label{{Name: "factory/drill"}}, State: "MERGED"}}}
	s := &Service{Cfg: serviceCfg(), Sources: func(string) (Source, bool) { return src, true }, Now: func() time.Time { return now }}
	r, err := s.Report(t.Context(), "smana/cloud-native-ref")
	if err != nil {
		t.Fatal(err)
	}
	if r.Repository != "Smana/cloud-native-ref" || r.Minimum != 20 || len(r.Classes) != 2 {
		t.Fatalf("%+v", r)
	}
	c := r.Classes[0]
	if c.Class != "docs-links" || c.Source != "repository" || c.Mode != "shadow" || !c.Evidence.Eligible || c.Evidence.Clean != 20 ||
		c.Proposal == nil || c.Proposal.Line != 6 || c.Proposal.EditURL != "https://github.com/Smana/cloud-native-ref/edit/main/.github/agent-factory.yaml" ||
		!strings.Contains(c.Proposal.File, "mode: live   # promoted") {
		t.Fatalf("%+v", c)
	}
	if !slices.Contains(src.filters, "author:app/ogenki-agents merged:>=2026-05-12") ||
		!slices.Contains(src.filters, `label:"factory/merged:docs-links" merged:>=2026-05-12`) {
		t.Fatalf("%q", src.filters)
	}
	n := len(src.filters)
	if _, err := s.Report(t.Context(), "Smana/cloud-native-ref"); err != nil || len(src.filters) != n {
		t.Fatalf("read again inside the TTL: %v", err)
	}
}

// Without classes in the file, the central classes are reported with no proposal: a promotion
// edits the repository's file (MP1), never the central config.
func TestServiceFallsBackToTheCentralClasses(t *testing.T) {
	src := &fakeSource{file: "factory: aws-0\n", found: true}
	s := &Service{Cfg: serviceCfg(), Sources: func(string) (Source, bool) { return src, true }, Now: time.Now}
	r, err := s.Report(t.Context(), "Smana/cloud-native-ref")
	if err != nil || len(r.Classes) != 1 || r.Classes[0].Source != "central" || r.Classes[0].Proposal != nil ||
		r.Classes[0].Unproposed != "not_in_repository_policy" || r.Classes[0].Evidence.Eligible {
		t.Fatalf("%+v %v", r, err)
	}
	if _, err := s.Report(t.Context(), "Smana/elsewhere"); !errors.Is(err, ErrUnknownRepository) {
		t.Fatal(err)
	}
	bad := &fakeSource{file: "factory: aws-0\n", found: true, err: errors.New("github")}
	s = &Service{Cfg: serviceCfg(), Sources: func(string) (Source, bool) { return bad, true }, Now: time.Now}
	if _, err := s.Report(t.Context(), "Smana/cloud-native-ref"); err == nil {
		t.Fatal("a failed read is an error, never an empty report")
	}
}
```

```go
// Service reads and caches each configured repository's report. Sources is the repository's
// connection, false without one.
type Service struct {
	Cfg     *config.Config
	Sources func(repository string) (Source, bool)
	Now     func() time.Time

	mu    sync.Mutex // one read at a time: the cache bounds GitHub, and so does this
	cache map[string]Report
}

// Report is a repository's promotion evidence as read at ReadAt.
type Report struct {
	Repository  string        `json:"repository"`
	Minimum     int           `json:"minimum"`
	PolicyError string        `json:"policyError,omitempty"`
	Classes     []ClassReport `json:"classes"`
	ReadAt      time.Time     `json:"readAt"`
	// The editor's inputs: the policy file as read ("" when absent), its parsed form when it
	// parses, the factory it must keep naming, the default branch its edit link opens, the central
	// harness profiles a class may reference, and the guardrails it is validated against.
	File            string                 `json:"file,omitempty"`
	Policy          *mergepolicy.File      `json:"policy,omitempty"`
	Factory         string                 `json:"factory"`
	DefaultBranch   string                 `json:"defaultBranch"`
	HarnessProfiles []string               `json:"harnessProfiles"`
	Guardrails      config.MergeGuardrails `json:"guardrails"`
}

func (s *Service) read(ctx context.Context, rc *config.Repository, src Source, now time.Time) (Report, error) {
	r := Report{Repository: rc.Name, Minimum: s.Cfg.MergeGuardrails.MinPromotion(), ReadAt: now}
	body, found, err := src.FenceFile(ctx)
	if err != nil {
		return Report{}, fmt.Errorf("evidence: %w", err)
	}
	var file *mergepolicy.File
	if found {
		if file, err = mergepolicy.Parse(body); err != nil {
			r.PolicyError = "invalid" // the reason, never the parser's text: the file is the repository's
			file = nil
		}
	}
	reverts, err := src.RevertRecords(ctx)
	if err != nil {
		return Report{}, fmt.Errorf("evidence: %w", err)
	}
	branch, err := src.DefaultBranch(ctx)
	if err != nil {
		return Report{}, fmt.Errorf("evidence: %w", err)
	}
	r.File, r.Policy, r.Factory, r.DefaultBranch = string(body), file, s.Cfg.Factory, branch
	r.HarnessProfiles = slices.Sorted(maps.Keys(s.Cfg.HarnessProfiles))
	r.Guardrails = s.Cfg.MergeGuardrails
	l := Logins{Factory: s.Cfg.FactoryLogin, Merger: rc.Merge.MergerLogin}
	since := now.Add(-Lookback).UTC().Format("2006-01-02")
	for _, c := range s.classes(rc, file) {
		e, err := collect(ctx, src, c, reverts, rc.Name, l, now, since, r.Minimum)
		if err != nil {
			return Report{}, err
		}
		cr := ClassReport{Class: c.name, Source: c.source, Mode: c.mode, Evidence: e}
		switch {
		case c.source != sourceRepository:
			cr.Unproposed = "not_in_repository_policy"
		case c.mode != string(mergepolicy.ModeShadow):
			cr.Unproposed = "not_shadow"
		default:
			out, line, err := Propose(body, c.name)
			if err != nil {
				return Report{}, fmt.Errorf("evidence: propose %s: %w", c.name, err)
			}
			cr.Proposal = &Proposal{Path: PolicyPath, Line: line, File: string(out),
				EditURL: EditURL(rc.Name, branch)}
		}
		r.Classes = append(r.Classes, cr)
	}
	return r, nil
}

// collect reads one class: the script's two modes, then MP7.
func collect(ctx context.Context, src Source, c class, reverts []Revert, repo string, l Logins, now time.Time, since string, minimum int) (Evidence, error) {
	var judged []PR
	for _, a := range c.authors {
		prs, err := src.MergedRecords(ctx, fmt.Sprintf("author:%s merged:>=%s", a, since))
		if err != nil {
			return Evidence{}, fmt.Errorf("evidence: %s: %w", c.name, err)
		}
		judged = append(judged, prs...)
	}
	var merges []PR
	for _, label := range []string{"factory/merged:", "factory/auto-merged:"} {
		prs, err := src.MergedRecords(ctx, fmt.Sprintf(`label:"%s%s" merged:>=%s`, label, c.name, since))
		if err != nil {
			return Evidence{}, fmt.Errorf("evidence: %s: %w", c.name, err)
		}
		merges = append(merges, prs...)
	}
	followed := map[int]bool{}
	for _, p := range merges {
		if _, seen := followed[p.Number]; seen {
			continue
		}
		hit, err := src.AnyMerged(ctx, fmt.Sprintf(`label:"factory/follow-up-of:#%d"`, p.Number))
		if err != nil {
			return Evidence{}, fmt.Errorf("evidence: %s: %w", c.name, err)
		}
		followed[p.Number] = hit
	}
	sh := Shadow(judged, reverts, c.name, repo, l)
	out := Outcomes(merges, reverts, followed, repo, l, now, c.window)
	return Evaluate(sh, out, reverts, repo, minimum), nil
}
```

### Task 6: The editor's check and the decision timeline

**Files:** Create `internal/factory/reconciler/conformance.go` and `internal/factory/policyview/{preview,timeline,service}.go`. Test in `internal/factory/reconciler/conformance_embed_test.go` and `internal/factory/policyview/policyview_test.go`.

- [ ] **Step 1: Write the failing tests**

```go
// The editor's check is the factory's own: strict parsing, factory: read-only, the guardrails;
// a valid file comes back with its structural change, the counterfactual and the edit link.
func TestCheck(t *testing.T) {
	r := strings.Replace
	for name, tc := range map[string]struct {
		file, err, kind, why string
	}{
		"unchanged":            {base, "the proposal is the file as it is", "", ""},
		"not YAML":             {"factory: aws-0\nclasses: [\n", "not YAML", "", ""},
		"an unknown condition": {r(base, "maxPatchFiles: 10", "maxFiles: 10", 1), "not a field", "", ""},
		"factory: edited":      {r(base, "factory: aws-0", "factory: gcp-0", 1), "factory: is read-only", "", ""},
		"an unlisted profile":  {r(base, "harness: plain", "harness: frontier", 1), "frontier", "", ""},
		"a lower cap":          {r(base, "maxPatchFiles: 10", "maxPatchFiles: 5", 1), "", mergepolicy.KindTightening, ""},
		"promoted":             {r(base, "mode: shadow", "mode: live", 1), "", mergepolicy.KindRelaxation, "mode"},
		"a deny removed":       {r(base, "      deny:\n        - protectedFiles: ['^docs/specs/.+$']\n", "", 1), "", mergepolicy.KindRelaxation, "protectedFiles"},
	} {
		t.Run(name, func(t *testing.T) {
			cfg, rc, rep := rig(false)
			pv := Check(cfg, rc, rep, tc.file)
			if tc.err != "" {
				if pv.Valid || !strings.Contains(strings.Join(pv.Errors, "\n"), tc.err) || pv.Proposal != nil {
					t.Fatalf("%+v", pv)
				}
				return
			}
			i := slices.IndexFunc(pv.Structural, func(c Change) bool { return c.Class == "docs-links" })
			if !pv.Valid || i < 0 || pv.Structural[i].Kind != tc.kind || !strings.Contains(strings.Join(pv.Structural[i].Why, ";"), tc.why) {
				t.Fatalf("%+v", pv)
			}
			if pv.Proposal.File != tc.file || pv.Proposal.EditURL != "https://github.com/Smana/cloud-native-ref/edit/main/.github/agent-factory.yaml" ||
				pv.Strictness[0] != (Strictness{Class: "docs-links", Refused: 3, RefusedMergedUnchanged: 2}) {
				t.Fatalf("%+v", pv)
			}
			if pv.Simulation.Enabled || len(pv.Simulation.Rows) != 0 {
				t.Fatal("simulation is policyManagement.simulation's")
			}
		})
	}
}

// With policyManagement.simulation on, every conformance fixture is decided under the central
// config and the proposal by the gate's own evaluator, and counted by change.
func TestCheckSimulatesOnTheFixtures(t *testing.T) {
	cfg, rc, rep := rig(true)
	pv := Check(cfg, rc, rep, strings.Replace(base, "maxPatchFiles: 10", "maxPatchFiles: 5", 1))
	total := 0
	for _, n := range pv.Simulation.Counts {
		total += n
	}
	if !pv.Simulation.Enabled || len(pv.Simulation.Rows) == 0 || total != len(pv.Simulation.Rows) {
		t.Fatalf("%+v", pv.Simulation)
	}
	for _, row := range pv.Simulation.Rows {
		if !slices.Contains(Changes(), row.Change) {
			t.Fatalf("%+v", row)
		}
	}
}

// A decision's timeline: each stage before the deciding one passed, that one refused, the rest
// not reached; an arm passes them all; the grant is reserved for stage 5; someone else's record
// is not the factory's.
func TestDecisionsTimeline(t *testing.T) {
	refused := "x <!-- agent-factory scope=task event=human-patch_too_large-2 -->\n\n<!-- agent-factory-decision head=a24 class=docs-links " +
		"decision=human:patch_too_large files=1/3 lines=30/20 shape=ok holdout=n/a oracle=n/a age=n/a evidence=ok paused=- capped=- reviewer=glm-5.3 -->"
	shadow := "<!-- agent-factory-decision head=a25 class=docs-links decision=shadow:shadow_would_arm files=1/3 lines=2/20 shape=ok " +
		"holdout=ok oracle=n/a age=n/a evidence=ok paused=false capped=false policy=0123456789ab dual=agree reviewer=glm-5.3 -->"
	tl := Decisions("Smana/cloud-native-ref", 24, "ogenki-agent-factory[bot]", []Comment{
		comment(2, "ogenki-agent-factory[bot]", "2026-10-02T00:00:00Z", shadow),
		comment(1, "ogenki-agent-factory", "2026-10-01T00:00:00Z", refused),
		comment(3, "someone", "2026-10-03T00:00:00Z", shadow),
	})
	if len(tl.Decisions) != 2 {
		t.Fatalf("%+v", tl)
	}
	d := tl.Decisions[0]
	status := map[string]string{}
	for _, s := range d.Steps {
		status[s.Row] = s.Status
	}
	if d.Verdict != "human" || d.Reason != "patch_too_large" || status["fixed_base"] != "passed" || status["author_mode"] != "passed" ||
		status["class"] != "refused" || status["deny"] != "not_reached" || status["grant"] != "reserved" || status["breaker_and_caps"] != "not_reached" ||
		d.CommentURL != "https://github.com/Smana/cloud-native-ref/pull/24#issuecomment-1" {
		t.Fatalf("%+v", d)
	}
	if i := slices.IndexFunc(d.Steps, func(s Step) bool { return s.Row == "condition: modified lines" }); i < 0 || d.Steps[i].Detail != "30/20" {
		t.Fatalf("%+v", d.Steps)
	}
	a := tl.Decisions[1]
	for _, s := range a.Steps {
		if s.Status == "refused" || s.Status == "not_reached" {
			t.Fatalf("a shadow decision passes every stage: %+v", s)
		}
	}
	if a.Revisions[0].Detail != "sha256 0123456789ab, dual=agree" || d.Revisions[0].Detail != "not recorded: dual evaluation was off" {
		t.Fatalf("%+v %+v", a.Revisions, d.Revisions)
	}
}
```

- [ ] **Step 2: Run** `systemd-run --user --scope -q -p MemoryMax=6G go test -count=1 ./internal/factory/policyview/`. Expect a build failure: undefined `Check`.

- [ ] **Step 3: Implement.** First the fixtures, embedded, so the simulation runs on exactly what the conformance test reads:

```go
// SPDX-License-Identifier: Apache-2.0

package reconciler

import (
	"embed"
	"fmt"
	"io/fs"
	"sort"
)

// conformance is the versioned decision fixtures (MP16), the cases the settings editor's
// simulation decides a proposed policy on (merge policy stage 6) with the gate's own evaluator.
//
//go:embed testdata/conformance/*.json
var conformance embed.FS

// ConformanceCases are the embedded fixtures, in name order, each set to repository.
func ConformanceCases(repository string) ([]Case, error) {
	names, err := fs.Glob(conformance, "testdata/conformance/*.json")
	if err != nil {
		return nil, err
	}
	sort.Strings(names)
	out := make([]Case, 0, len(names))
	for _, n := range names {
		raw, err := conformance.ReadFile(n)
		if err != nil {
			return nil, err
		}
		c, err := ReadCase(raw)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", n, err)
		}
		c.Inputs.Task.Spec.Repository = repository
		out = append(out, c)
	}
	return out, nil
}
```

```go
// Check previews file for the repository rc, whose current state rep is: strict parsing, the
// factory it must keep naming, the central guardrails and profiles (Validate, Resolve), the
// structural change from the current policy (the file's classes, else the central ones as
// exported), and the simulation. Errors are the parser's and validator's own messages: the file
// is the caller's, so they may read about it.
func Check(cfg *config.Config, rc *config.Repository, rep evidence.Report, file string) Preview {
	bad := func(msgs ...string) Preview { return Preview{Errors: msgs} }
	if strings.TrimSpace(file) == strings.TrimSpace(rep.File) {
		return bad(ErrUnchanged.Error())
	}
	next, err := mergepolicy.Parse([]byte(file))
	if err != nil {
		return bad(err.Error())
	}
	if next.Factory != cfg.Factory {
		return bad("factory: is read-only here: it must stay " + cfg.Factory)
	}
	if err := mergepolicy.Validate(next, cfg); err != nil {
		return bad(strings.Split(err.Error(), "\n")...)
	}
	policy := map[string]mergepolicy.Resolved{}
	for name, p := range next.Classes {
		r, err := mergepolicy.Resolve(name, p, cfg)
		if err != nil {
			return bad(err.Error())
		}
		policy[name] = r
	}
	pv := Preview{Valid: true, Proposal: &evidence.Proposal{Path: evidence.PolicyPath, File: file,
		EditURL: evidence.EditURL(rc.Name, rep.DefaultBranch)}}
	if old := current(cfg, rc, rep); old != nil {
		if cs, err := mergepolicy.Structural(old, next, cfg); err == nil {
			for _, c := range cs {
				pv.Structural = append(pv.Structural, Change{Class: c.Class, Kind: c.Kind, Why: c.Why})
			}
		} else {
			pv.Errors = append(pv.Errors, "structural comparison unavailable: "+err.Error())
		}
	}
	pv.Simulation = simulate(cfg, rc, policy)
	for _, c := range rep.Classes {
		pv.Strictness = append(pv.Strictness, Strictness{Class: c.Class, Refused: c.Evidence.Shadow.Refused,
			RefusedMergedUnchanged: c.Evidence.Shadow.RefusedMergedUnchanged})
	}
	return pv
}

// current is the policy the proposal changes: the file's classes when it declares any and is
// valid, else the central classes as the migration exports them.
func current(cfg *config.Config, rc *config.Repository, rep evidence.Report) *mergepolicy.File {
	if rep.Policy != nil && len(rep.Policy.Classes) > 0 && mergepolicy.Validate(rep.Policy, cfg) == nil {
		return rep.Policy
	}
	f, err := mergepolicy.Export(rc, cfg)
	if err != nil {
		return nil
	}
	return f
}

func simulate(cfg *config.Config, rc *config.Repository, policy map[string]mergepolicy.Resolved) Simulation {
	if !cfg.PolicyManagement.Simulation {
		return Simulation{}
	}
	cases, err := reconciler.ConformanceCases(rc.Name)
	if err != nil {
		return Simulation{}
	}
	s := Simulation{Enabled: true, Counts: map[string]int{}}
	for _, r := range reconciler.Simulate(cfg, policy, cases) {
		s.Rows = append(s.Rows, SimRow{Name: r.Name, Class: r.Class, Central: r.Central, Repository: r.Repository,
			Change: r.Change, Conforms: r.Conforms})
		s.Counts[r.Change]++
	}
	return s
}
```

```go
// Decisions reads every decision record the factory wrote on a pull request: only factory's own
// comments count, as for the tally. A hand-off's record is a hand-off whatever decision= says.
func Decisions(repository string, pr int, factory string, comments []Comment) Timeline {
	t := Timeline{Repository: repository, PullRequest: pr, Decisions: []Decision{}}
	mine := func(a string) bool {
		n := func(s string) string {
			return strings.TrimSuffix(strings.TrimPrefix(strings.ToLower(s), "app/"), "[bot]")
		}
		return n(a) == n(factory)
	}
	sort.SliceStable(comments, func(i, j int) bool { return comments[i].At.Before(comments[j].At) })
	for _, c := range comments {
		m := record.FindStringSubmatch(c.Body)
		if m == nil || !mine(c.Author) {
			continue
		}
		d := Decision{At: c.At, Head: m[1], Class: m[2], Verdict: m[3], Reason: m[4],
			CommentURL: fmt.Sprintf("https://github.com/%s/pull/%d#issuecomment-%d", repository, pr, c.ID),
			PolicyURL:  "https://github.com/" + repository + "/commits/HEAD/.github/agent-factory.yaml"}
		if h := event.FindStringSubmatch(c.Body); h != nil {
			d.Verdict, d.Reason = "human", h[1]
		}
		rows := map[string]string{}
		for _, f := range field.FindAllStringSubmatch(m[5], -1) {
			rows[f[1]] = f[2]
		}
		d.Steps, d.Revisions = steps(d, rows), revisions(rows)
		t.Decisions = append(t.Decisions, d)
	}
	return t
}

// steps walks the stages in order: each before the deciding one passed, that one refused, each
// after it not reached; an arm or a shadow decision passed them all. The class's own readings
// are the record's.
func steps(d Decision, rows map[string]string) []Step {
	decided, refused := stageOf(d.Reason), d.Verdict == "human"
	at := len(stages)
	for i, s := range stages {
		if refused && s == decided {
			at = i
		}
	}
	var out []Step
	for i, s := range stages {
		st := Step{Row: s, Status: "passed"}
		switch {
		case s == "grant":
			st.Status, st.Detail = "reserved", "approval memory (stage 5) records grant use here"
		case i == at:
			st.Status, st.Detail = "refused", d.Reason
		case i > at:
			st.Status = "not_reached"
		}
		if s == "author_mode" {
			st.Detail = strings.TrimSpace(st.Detail + " " + "class " + d.Class)
		}
		if s == "breaker_and_caps" && st.Status != "not_reached" {
			st.Detail = strings.TrimSpace(st.Detail + fmt.Sprintf(" paused=%s capped=%s", dash(rows["paused"]), dash(rows["capped"])))
		}
		out = append(out, st)
		if s == "class" {
			for _, r := range []struct{ key, label string }{{"files", "files"}, {"lines", "modified lines"}, {"shape", "diff shape"},
				{"holdout", "holdout checks"}, {"oracle", "oracle"}, {"age", "release age"}, {"evidence", "evidence"}} {
				out = append(out, Step{Row: "condition: " + r.label, Status: "recorded", Detail: dash(rows[r.key])})
			}
		}
	}
	return append(out, Step{Row: "verdict", Status: d.Verdict, Detail: d.Reason})
}
```

- [ ] **Step 4: Run the same command again**: PASS.

### Task 7: The factory's policy routes

**Files:** Create `internal/factory/api/evidence.go`. Modify `server.go`, `access.go` and `internal/app/factory.go`. Test in `internal/factory/api/evidence_test.go`, with one row per role per handler, and `access_test.go`.

- [ ] **Step 1: Write the failing tests**

```go
// Stage 6, one row per role per handler: readers read evidence, repositories and timelines;
// only a maintainer previews a policy; nobody else reaches the editor; off, no route exists.
func TestPolicyHandlersByRole(t *testing.T) {
	preview := `{"repository":"` + coordPrimary + `","file":"factory: aws-0\n"}`
	routes := map[string]struct{ method, path, body string }{
		"evidence":  {http.MethodGet, "/v1/policy/evidence?repository=" + coordPrimary, ""},
		"repos":     {http.MethodGet, "/v1/policy/repositories", ""},
		"decisions": {http.MethodGet, "/v1/policy/decisions?repository=" + coordPrimary + "&pr=12", ""},
		"preview":   {http.MethodPost, "/v1/policy/preview", preview},
	}
	want := map[string]map[string]int{
		"human":      {"evidence": 200, "repos": 200, "decisions": 200, "preview": 200},
		"onlyreader": {"evidence": 200, "repos": 200, "decisions": 200, "preview": 403},
		"reader":     {"evidence": 404, "repos": 200, "decisions": 404, "preview": 404},
		"slack":      {"evidence": 403, "repos": 403, "decisions": 403, "preview": 403},
		"":           {"evidence": 401, "repos": 401, "decisions": 401, "preview": 401},
	}
	for role, codes := range want {
		for name, rt := range routes {
			t.Run(role+" "+name, func(t *testing.T) {
				for _, on := range []bool{true, false} {
					s, _ := evidenceServer(on)
					req := httptest.NewRequestWithContext(context.Background(), rt.method, rt.path, strings.NewReader(rt.body))
					if role != "" {
						req.Header.Set("Authorization", "Bearer "+role)
					}
					w := httptest.NewRecorder()
					s.Handler().ServeHTTP(w, req)
					code := codes[name]
					if !on {
						code = http.StatusNotFound
					}
					if w.Code != code {
						t.Fatalf("on=%v: %d %s, want %d", on, w.Code, w.Body, code)
					}
				}
			})
		}
	}
}
```

- [ ] **Step 2: Implement**

```go
// SPDX-License-Identifier: Apache-2.0

package api

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/Smana/maku/internal/authn"
	"github.com/Smana/maku/internal/factory/evidence"
	"github.com/Smana/maku/internal/factory/mergepolicy"
)

// EvidenceSource is each repository's promotion evidence (merge policy stage 6); *evidence.Service
// implements it.
type EvidenceSource interface {
	Report(ctx context.Context, repository string) (evidence.Report, error)
}

// ReadChecker answers whether a human may read a repository on GitHub, as WriteChecker answers
// write; GitHubAccess implements both.
type ReadChecker interface {
	CanRead(ctx context.Context, p authn.Principal, repository string) (bool, error)
}

// promotionOn is whether policyManagement.promotion serves the evidence routes: off is a 404.
func (s *Server) promotionOn() bool {
	return s.Cfg.PolicyManagement.Promotion && s.Evidence != nil
}

// policyReader is a human caller; sponsored and system principals read no evidence.
func (s *Server) policyReader(w http.ResponseWriter, r *http.Request) (authn.Principal, bool) {
	p, err := s.Auth.Authenticate(r)
	switch {
	case errors.Is(err, authn.ErrForbidden):
		refuse(w, http.StatusForbidden, "not_permitted")
		return p, false
	case err != nil:
		refuse(w, http.StatusUnauthorized, "unauthenticated")
		return p, false
	case p.Sponsored || p.Sub == "":
		refuse(w, http.StatusForbidden, "human_only")
		return p, false
	}
	return p, true
}

// reads is whether p may read repository on GitHub; an error is no answer.
func (s *Server) reads(ctx context.Context, p authn.Principal, repository string) (bool, error) {
	rc, ok := s.Access.(ReadChecker)
	if !ok {
		return false, nil
	}
	return rc.CanRead(ctx, p, repository)
}

// configured is repository as the config spells it, "" when it lists none.
func (s *Server) configured(repository string) string {
	for _, r := range s.Cfg.Repos() {
		if strings.EqualFold(r.Name, repository) {
			return r.Name
		}
	}
	return ""
}

// policyEvidence is GET /v1/policy/evidence?repository=owner/name: the repository's promotion
// evidence, for a reader of it on GitHub (MP17). A repository the caller cannot read, or the
// config does not list, is a 404 alike, so the answer tells no repository's existence.
func (s *Server) policyEvidence(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyReader(w, r)
	if !ok {
		return
	}
	asked := r.URL.Query().Get("repository")
	if asked == "" {
		refuse(w, http.StatusBadRequest, "repository_required")
		return
	}
	repo := s.readable(w, r, p, asked)
	if repo == "" {
		return
	}
	rep, err := s.Evidence.Report(r.Context(), repo)
	if err != nil {
		if s.Log != nil {
			s.Log.WarnContext(r.Context(), "policy evidence unread", "repository", repo, "error", err)
		}
		refuse(w, http.StatusServiceUnavailable, "evidence_unavailable")
		return
	}
	reply(w, http.StatusOK, rep)
}

// policyRepositories is GET /v1/policy/repositories: the configured repositories the caller reads.
// One that cannot be checked is left out, never shown.
func (s *Server) policyRepositories(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyReader(w, r)
	if !ok {
		return
	}
	out := []string{}
	for _, rc := range s.Cfg.Repos() {
		if can, err := s.reads(r.Context(), p, rc.Name); err == nil && can {
			out = append(out, rc.Name)
		}
	}
	reply(w, http.StatusOK, map[string][]string{"repositories": out})
}

// PolicyEditor is the settings editor's check and the decision timeline (stage 6), each answered
// as the JSON document it is; app wires *policyview.Service through it. The documents are any so
// this package does not import the reconciler: intake's tests import this package, and the
// reconciler imports intake.
type PolicyEditor interface {
	Preview(ctx context.Context, repository, file string) (any, error)
	Timeline(ctx context.Context, repository string, pr int) (any, error)
}

// maxPreviewBody bounds a proposed policy: the file's own bound and its envelope.
const maxPreviewBody = mergepolicy.MaxFileBytes + 4<<10

// readable answers the caller's read of repository, refusing for them when not: the repository as
// the config spells it, or "".
func (s *Server) readable(w http.ResponseWriter, r *http.Request, p authn.Principal, asked string) string {
	repo := s.configured(asked)
	if repo == "" {
		refuse(w, http.StatusNotFound, "not_found")
		return ""
	}
	switch can, err := s.reads(r.Context(), p, repo); {
	case err != nil:
		refuse(w, http.StatusServiceUnavailable, reasonLinkUnverified)
		return ""
	case !can:
		refuse(w, http.StatusNotFound, "not_found")
		return ""
	}
	return repo
}

// policyPreview is POST /v1/policy/preview {repository, file}: a maintainer's proposed policy file,
// checked strictly, compared structurally and simulated (MP8, MP16). It writes nothing: the answer
// is the file to submit and the GitHub page to submit it from.
func (s *Server) policyPreview(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyReader(w, r)
	if !ok {
		return
	}
	var in struct {
		Repository string `json:"repository"`
		File       string `json:"file"`
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxPreviewBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		refuse(w, http.StatusBadRequest, "bad_json")
		return
	}
	repo := s.readable(w, r, p, in.Repository)
	if repo == "" {
		return
	}
	switch can, err := s.Access.CanWrite(r.Context(), p, repo); {
	case err != nil:
		refuse(w, http.StatusServiceUnavailable, reasonLinkUnverified)
		return
	case !can:
		refuse(w, http.StatusForbidden, "not_a_maintainer")
		return
	}
	pv, err := s.Editor.Preview(r.Context(), repo, in.File)
	if err != nil {
		refuse(w, http.StatusServiceUnavailable, "evidence_unavailable")
		return
	}
	reply(w, http.StatusOK, pv)
}

// policyDecisions is GET /v1/policy/decisions?repository=owner/name&pr=N: the pull request's
// decision timeline, for a reader of the repository.
func (s *Server) policyDecisions(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyReader(w, r)
	if !ok {
		return
	}
	pr, err := strconv.Atoi(r.URL.Query().Get("pr"))
	if err != nil || pr < 1 {
		refuse(w, http.StatusBadRequest, "pr_required")
		return
	}
	repo := s.readable(w, r, p, r.URL.Query().Get("repository"))
	if repo == "" {
		return
	}
	tl, err := s.Editor.Timeline(r.Context(), repo, pr)
	if err != nil {
		refuse(w, http.StatusServiceUnavailable, "decisions_unavailable")
		return
	}
	reply(w, http.StatusOK, tl)
}
```

```go
// policyPreview is POST /v1/policy/preview {repository, file}: a maintainer's proposed policy file,
// checked strictly, compared structurally and simulated (MP8, MP16). It writes nothing: the answer
// is the file to submit and the GitHub page to submit it from.
func (s *Server) policyPreview(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyReader(w, r)
	if !ok {
		return
	}
	var in struct {
		Repository string `json:"repository"`
		File       string `json:"file"`
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxPreviewBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		refuse(w, http.StatusBadRequest, "bad_json")
		return
	}
	repo := s.readable(w, r, p, in.Repository)
	if repo == "" {
		return
	}
	switch can, err := s.Access.CanWrite(r.Context(), p, repo); {
	case err != nil:
		refuse(w, http.StatusServiceUnavailable, reasonLinkUnverified)
		return
	case !can:
		refuse(w, http.StatusForbidden, "not_a_maintainer")
		return
	}
	pv, err := s.Editor.Preview(r.Context(), repo, in.File)
	if err != nil {
		refuse(w, http.StatusServiceUnavailable, "evidence_unavailable")
		return
	}
	reply(w, http.StatusOK, pv)
}

// policyDecisions is GET /v1/policy/decisions?repository=owner/name&pr=N: the pull request's
// decision timeline, for a reader of the repository.
func (s *Server) policyDecisions(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyReader(w, r)
	if !ok {
		return
	}
	pr, err := strconv.Atoi(r.URL.Query().Get("pr"))
	if err != nil || pr < 1 {
		refuse(w, http.StatusBadRequest, "pr_required")
		return
	}
	repo := s.readable(w, r, p, r.URL.Query().Get("repository"))
	if repo == "" {
		return
	}
	tl, err := s.Editor.Timeline(r.Context(), repo, pr)
	if err != nil {
		refuse(w, http.StatusServiceUnavailable, "decisions_unavailable")
		return
	}
	reply(w, http.StatusOK, tl)
}
```

```diff
@@ -53,6 +53,25 @@ func (a GitHubAccess) Person(ctx context.Context, p authn.Principal, repository
 	return factoryv1.Person(login), nil
 }

+// CanRead implements ReadChecker: read or higher, through the same link CanWrite resolves. A Perms
+// without CanRead reads nothing.
+func (a GitHubAccess) CanRead(ctx context.Context, p authn.Principal, repository string) (bool, error) {
+	r, ok := a.Perms.(interface {
+		CanRead(ctx context.Context, repository, login string) (bool, error)
+	})
+	if !ok || p.Sub == "" {
+		return false, nil
+	}
+	login, err := a.Identity.Login(ctx, p.Sub, repository)
+	if err != nil {
+		return false, fmt.Errorf("access: %w", err)
+	}
+	if login == "" {
+		return false, nil
+	}
+	return r.CanRead(ctx, repository, login)
+}
+
 // CanWriteLogin is write or higher for an already-resolved login: a sponsored principal's
 // onBehalfOf maintainer, who drafts a coordination plan on the primary (v4 MR4) as the planner
 // requires of the effective requester.
@@ -112,6 +112,11 @@ type Server struct {
 	// Coordination is the multi-repository draft and confirmation flow (v4 MR4, MR5), served only
 	// while coordination.mode is plan or execute; nil or off serves no coordination route.
 	Coordination CoordinationService
+	// Evidence is each repository's promotion evidence (merge policy stage 6), served only while
+	// policyManagement.promotion is on; nil or off serves no policy route.
+	Evidence EvidenceSource
+	// Editor is the settings editor's check and the decision timeline, served beside Evidence.
+	Editor PolicyEditor
 }

 // SlackLinkReader is the broker's self-serve link records: the ZITADEL sub a Slack user linked;
@@ -165,6 +170,14 @@ func (s *Server) Handler() http.Handler {
 		mux.HandleFunc("POST /v1/coordinations/{task}/confirmations", s.confirmCoordination)
 		mux.HandleFunc("POST /v1/coordinations/{task}/recovery", s.recoverCoordination)
 	}
+	if s.promotionOn() { // stage 6: off lists no policy route, so each is a 404
+		mux.HandleFunc("GET /v1/policy/evidence", s.policyEvidence)
+		mux.HandleFunc("GET /v1/policy/repositories", s.policyRepositories)
+		if s.Editor != nil {
+			mux.HandleFunc("POST /v1/policy/preview", s.policyPreview)
+			mux.HandleFunc("GET /v1/policy/decisions", s.policyDecisions)
+		}
+	}
 	return mux
 }

```

```diff
@@ -39,6 +39,7 @@ import (
 	"github.com/Smana/maku/internal/factory/config"
 	"github.com/Smana/maku/internal/factory/coordination"
 	"github.com/Smana/maku/internal/factory/demo"
+	"github.com/Smana/maku/internal/factory/evidence"
 	"github.com/Smana/maku/internal/factory/fence"
 	"github.com/Smana/maku/internal/factory/fluxwatch"
 	"github.com/Smana/maku/internal/factory/fmetrics"
@@ -48,6 +49,7 @@ import (
 	"github.com/Smana/maku/internal/factory/ledger"
 	"github.com/Smana/maku/internal/factory/mergepolicy"
 	"github.com/Smana/maku/internal/factory/meter"
+	"github.com/Smana/maku/internal/factory/policyview"
 	"github.com/Smana/maku/internal/factory/reconciler"
 	"github.com/Smana/maku/internal/factory/rooms"
 	"github.com/Smana/maku/internal/factory/runs"
@@ -403,6 +405,24 @@ func runFactory(ctx context.Context, log *slog.Logger, getenv func(string) strin
 			return nil
 		}}
 	apiSrv.Coordination, rec.Coordination = coord, coord // the manager has not started: rec reads it from its first pass
+	// Stage 6 (merge policy): each repository's promotion evidence, through its own App connection.
+	if cfg.PolicyManagement.Promotion {
+		ev := &evidence.Service{Cfg: cfg, Now: time.Now, Sources: func(repo string) (evidence.Source, bool) {
+			c, ok := conns.get(repo)
+			if !ok || c.gh == nil {
+				return nil, false
+			}
+			return evidenceSource{c.gh}, true
+		}}
+		apiSrv.Evidence = ev
+		apiSrv.Editor = policyEditor{&policyview.Service{Cfg: cfg, Reports: ev, Comments: func(repo string) (policyview.CommentReader, bool) {
+			c, ok := conns.get(repo)
+			if !ok || c.gh == nil {
+				return nil, false
+			}
+			return commentReader(c.gh), true
+		}}}
+	}
 	// The api intake and factory/publish scan what they publish, and both fail closed without it.
 	redactor, err := redact.New()
 	if err != nil {
@@ -685,3 +705,35 @@ func (p *pinger) tick() (<-chan time.Time, func()) {
 	t := time.NewTicker(p.every)
 	return t.C, t.Stop
 }
+
+// evidenceSource is a repository's connection as the promotion evidence reads it: the default
+// branch is RepositoryInfo's.
+type evidenceSource struct{ *forge.GitHub }
+
+func (e evidenceSource) DefaultBranch(ctx context.Context) (string, error) {
+	info, err := e.RepositoryInfo(ctx)
+	return info.DefaultBranch, err
+}
+
+// commentReader is a pull request's 50 newest comments as the decision timeline reads them.
+func commentReader(gh *forge.GitHub) policyview.CommentReader {
+	return func(ctx context.Context, pr int) ([]policyview.Comment, error) {
+		cs, err := gh.RecentComments(ctx, pr)
+		out := make([]policyview.Comment, 0, len(cs))
+		for _, c := range cs {
+			out = append(out, policyview.Comment{ID: c.ID, Author: c.Author, Body: c.Body, At: c.At})
+		}
+		return out, err
+	}
+}
+
+// policyEditor is the policy view as the API serves it, documents as any (api.PolicyEditor).
+type policyEditor struct{ *policyview.Service }
+
+func (e policyEditor) Preview(ctx context.Context, repository, file string) (any, error) {
+	return e.Service.Preview(ctx, repository, file)
+}
+
+func (e policyEditor) Timeline(ctx context.Context, repository string, pr int) (any, error) {
+	return e.Service.Timeline(ctx, repository, pr)
+}
```

The API's `PolicyEditor` answers `any`: intake's in-package tests import the API, and the reconciler imports intake, so the policy view's types would close an import cycle in a test build (`go vet ./internal/factory/intake/` shows it).

- [ ] **Step 3: Run** `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/factory/... ./internal/app/`: PASS.

### Task 8: The tables

**Files:** Create `internal/store/migrations/20261108120000_policy_promotions.sql` and `internal/store/policy.go`. Modify `kustomization.yaml`, `atlas.sum` (regenerated with `atlas migrate hash`) and `internal/store/migrations/embed_test.go`. Test in `internal/store/policy_test.go`, which runs on testcontainers.

```go
// Stage 6: a promotion enters requested on its evidence, moves to pr_opened naming its pull
// request, then once to merged or abandoned, by someone, never back; one open per class.
func TestPromotionMovesOnceToItsEnd(t *testing.T) {
	ctx := t.Context()
	s, _, _, _ := open(t)
	p, err := s.RecordPromotion(ctx, Promotion{ID: "aaaaaaaa", Repository: canary, Class: "docs-links", Threshold: 20,
		Evidence: snapshot, RequestedBy: "Smana"})
	if err != nil || p.State != PromotionRequested || p.RequestedAt.IsZero() || !strings.Contains(string(p.Evidence), `"clean": 20`) {
		t.Fatalf("%+v %v", p, err)
	}
	if _, err := s.RecordPromotion(ctx, Promotion{ID: "bbbbbbbb", Repository: canary, Class: "docs-links", Threshold: 20,
		Evidence: snapshot, RequestedBy: "Smana"}); !errors.Is(err, ErrPromotionOpen) {
		t.Fatalf("a second open promotion: %v", err)
	}
	if _, err := s.MovePromotion(ctx, "aaaaaaaa", PromotionPROpened, 0, "Smana"); !errors.Is(err, ErrPolicyMoved) {
		t.Fatalf("pr_opened names its pull request: %v", err)
	}
	if p, err = s.MovePromotion(ctx, "aaaaaaaa", PromotionPROpened, 42, "Smana"); err != nil || p.PullRequest != 42 || p.ClosedBy != "Smana" {
		t.Fatalf("%+v %v", p, err)
	}
	if _, err := s.MovePromotion(ctx, "aaaaaaaa", PromotionMerged, 43, "Smana"); !errors.Is(err, ErrPolicyMoved) {
		t.Fatalf("the pull request is the one named: %v", err)
	}
	if p, err = s.MovePromotion(ctx, "aaaaaaaa", PromotionMerged, 0, "Smana"); err != nil || p.State != PromotionMerged || p.PullRequest != 42 {
		t.Fatalf("%+v %v", p, err)
	}
	for _, st := range []string{PromotionAbandoned, PromotionRequested, PromotionPROpened} {
		if _, err := s.MovePromotion(ctx, "aaaaaaaa", st, 0, "Smana"); !errors.Is(err, ErrPolicyMoved) {
			t.Fatalf("a merged promotion moved to %s: %v", st, err)
		}
	}
	if _, err := s.MovePromotion(ctx, "zzzzzzzz", PromotionAbandoned, 0, "Smana"); !errors.Is(err, ErrNoPolicyRecord) {
		t.Fatal(err)
	}
	// The class is free again once its promotion ended.
	if _, err := s.RecordPromotion(ctx, Promotion{ID: "bbbbbbbb", Repository: canary, Class: "docs-links", Threshold: 20,
		Evidence: snapshot, RequestedBy: "Smana"}); err != nil {
		t.Fatal(err)
	}
	ps, es, err := s.PolicyAudit(ctx, canary)
	if err != nil || len(ps) != 2 || len(es) != 0 || ps[0].ID != "bbbbbbbb" {
		t.Fatalf("%+v %+v %v", ps, es, err)
	}
}

// MP7's exception: requested with a justification, decided once by an operator, and only an
// approved, unexpired exception of the class and minimum carries a promotion.
func TestExceptionCarriesAPromotionOnlyWhileApproved(t *testing.T) {
	ctx := t.Context()
	s, _, _, _ := open(t)
	ask := func(id, class string) Exception {
		e, err := s.RequestException(ctx, Exception{ID: id, Repository: canary, Class: class, Minimum: 10,
			Justification: "the canary's docs class is narrow: ten clean decisions bound it", RequestedBy: "Smana"})
		if err != nil || e.State != ExceptionRequested {
			t.Fatalf("%+v %v", e, err)
		}
		return e
	}
	promote := func(id, exc string, threshold int) error {
		_, err := s.RecordPromotion(ctx, Promotion{ID: id, Repository: canary, Class: "docs-links", Threshold: threshold,
			Evidence: snapshot, ExceptionID: exc, RequestedBy: "Smana"})
		return err
	}
	ask("cccccccc", "docs-links")
	if err := promote("pppppppp", "cccccccc", 10); !errors.Is(err, ErrExceptionUnusable) {
		t.Fatalf("a requested exception carried a promotion: %v", err)
	}
	if _, err := s.DecideException(ctx, "cccccccc", ExceptionApproved, "Smana", "", time.Now().Add(-time.Hour)); !errors.Is(err, ErrPolicyMoved) {
		t.Fatalf("an approval expires in the future: %v", err)
	}
	e, err := s.DecideException(ctx, "cccccccc", ExceptionApproved, "Smana", "drill passed on the canary", time.Now().Add(14*24*time.Hour))
	if err != nil || e.State != ExceptionApproved || e.DecidedBy != "Smana" || e.ExpiresAt == nil {
		t.Fatalf("%+v %v", e, err)
	}
	if _, err := s.DecideException(ctx, "cccccccc", ExceptionRefused, "Smana", "", time.Time{}); !errors.Is(err, ErrPolicyMoved) {
		t.Fatalf("decided twice: %v", err)
	}
	if err := promote("pppppppp", "cccccccc", 9); !errors.Is(err, ErrExceptionUnusable) {
		t.Fatalf("another minimum: %v", err)
	}
	ask("dddddddd", "revert")
	if _, err := s.DecideException(ctx, "dddddddd", ExceptionApproved, "Smana", "", time.Now().Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if err := promote("pppppppp", "dddddddd", 10); !errors.Is(err, ErrExceptionUnusable) {
		t.Fatalf("another class's exception: %v", err)
	}
	if err := promote("pppppppp", "cccccccc", 10); err != nil {
		t.Fatal(err)
	}
	if _, err := s.RequestException(ctx, Exception{ID: "eeeeeeee", Repository: canary, Class: "docs-links", Minimum: 10,
		Justification: "short", RequestedBy: "Smana"}); err == nil {
		t.Fatal("a justification is written, not a word")
	}
}

// The broker records and moves, never rewrites what was asked or on what evidence.
func TestBrokerCannotRewriteAPromotion(t *testing.T) {
	ctx := t.Context()
	s, broker, _, _ := open(t)
	if _, err := s.RecordPromotion(ctx, Promotion{ID: "aaaaaaaa", Repository: canary, Class: "docs-links", Threshold: 20,
		Evidence: snapshot, RequestedBy: "Smana"}); err != nil {
		t.Fatal(err)
	}
	for _, q := range []string{
		`UPDATE policy_promotions SET evidence = '{}' WHERE promotion_id = 'aaaaaaaa'`,
		`UPDATE policy_promotions SET threshold = 1 WHERE promotion_id = 'aaaaaaaa'`,
		`UPDATE operator_exceptions SET justification = 'x' WHERE true`,
		`DELETE FROM policy_promotions`,
	} {
		if err := run(ctx, broker, q); err == nil || !strings.Contains(err.Error(), "permission denied") {
			t.Errorf("%s: %v", q, err)
		}
	}
}
```

```sql
-- Merge policy stage 6, the promotion workflow (merge policy self-service design, "Storage"): the
-- audit of each request to promote a shadow class to live and of each operator exception below
-- the evidence minimum. Git owns the class's mode; these rows record who asked, on what evidence,
-- and what became of the request. Insert, then one constrained move to a terminal state.

-- An exception lowers the clean decisions one class needs (MP7), nothing else: bad outcomes and
-- the drill still block. A maintainer asks with a written justification; an operator approves or
-- refuses it once, and an approval lasts until expires_at.
CREATE TABLE operator_exceptions (
  exception_id  text        PRIMARY KEY CHECK (exception_id ~ '^[a-z2-7]{8}$'),
  repository    text        NOT NULL CHECK (repository ~ '^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$'),
  class         text        NOT NULL CHECK (class ~ '^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$'),
  minimum       integer     NOT NULL CHECK (minimum BETWEEN 1 AND 1000),
  justification text        NOT NULL CHECK (length(justification) BETWEEN 20 AND 2000),
  requested_by  text        NOT NULL CHECK (requested_by ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$'),
  requested_at  timestamptz NOT NULL DEFAULT now(),
  state         text        NOT NULL CHECK (state IN ('requested', 'approved', 'refused')),
  decided_by    text        CHECK (decided_by IS NULL OR decided_by ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$'),
  decided_at    timestamptz,
  note          text        CHECK (note IS NULL OR length(note) <= 2000),
  expires_at    timestamptz
);
CREATE INDEX operator_exceptions_repository ON operator_exceptions (repository, requested_at DESC);

CREATE FUNCTION operator_exceptions_move_once() RETURNS trigger
  LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF TG_OP = 'INSERT' AND (NEW.state <> 'requested' OR NEW.decided_by IS NOT NULL OR NEW.decided_at IS NOT NULL
      OR NEW.note IS NOT NULL OR NEW.expires_at IS NOT NULL OR NEW.requested_at <> now()) THEN
    RAISE EXCEPTION 'policy: exception % enters requested, undecided, at now()', NEW.exception_id USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND (OLD.state <> 'requested' OR NEW.state = 'requested') THEN
    RAISE EXCEPTION 'policy: exception % moves once, out of requested (% to %)', OLD.exception_id, OLD.state, NEW.state
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND (NEW.decided_by IS NULL OR NEW.decided_at IS DISTINCT FROM now()
      OR (NEW.state = 'approved') <> (NEW.expires_at IS NOT NULL AND NEW.expires_at > now())) THEN
    RAISE EXCEPTION 'policy: exception % is decided at now(), by someone, and only an approval expires', OLD.exception_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER operator_exceptions_move_once BEFORE INSERT OR UPDATE ON operator_exceptions
  FOR EACH ROW EXECUTE FUNCTION operator_exceptions_move_once();

-- A promotion request: the evidence it was granted on, the minimum applied (the configured one,
-- or an approved exception's), and who asked. requested moves to pr_opened when the maintainer
-- names their pull request, then to merged or abandoned; requested may also be abandoned. One open
-- request per class at a time.
CREATE TABLE policy_promotions (
  promotion_id  text        PRIMARY KEY CHECK (promotion_id ~ '^[a-z2-7]{8}$'),
  repository    text        NOT NULL CHECK (repository ~ '^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$'),
  class         text        NOT NULL CHECK (class ~ '^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$'),
  threshold     integer     NOT NULL CHECK (threshold BETWEEN 1 AND 1000),
  evidence      jsonb       NOT NULL CHECK (jsonb_typeof(evidence) = 'object' AND octet_length(evidence::text) <= 65536),
  exception_id  text        REFERENCES operator_exceptions (exception_id),
  requested_by  text        NOT NULL CHECK (requested_by ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$'),
  requested_at  timestamptz NOT NULL DEFAULT now(),
  state         text        NOT NULL CHECK (state IN ('requested', 'pr_opened', 'merged', 'abandoned')),
  pull_request  integer     CHECK (pull_request IS NULL OR pull_request > 0),
  closed_by     text        CHECK (closed_by IS NULL OR closed_by ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$'),
  closed_at     timestamptz
);
CREATE INDEX policy_promotions_repository ON policy_promotions (repository, requested_at DESC);
CREATE UNIQUE INDEX policy_promotions_one_open ON policy_promotions (repository, class)
  WHERE state IN ('requested', 'pr_opened');

CREATE FUNCTION policy_promotions_move() RETURNS trigger
  LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF TG_OP = 'INSERT' AND (NEW.state <> 'requested' OR NEW.pull_request IS NOT NULL OR NEW.closed_by IS NOT NULL
      OR NEW.closed_at IS NOT NULL OR NEW.requested_at <> now()) THEN
    RAISE EXCEPTION 'policy: promotion % enters requested, open, at now()', NEW.promotion_id USING ERRCODE = 'check_violation';
  END IF;
  -- An exception carries a promotion only while approved and unexpired, for its own class.
  IF TG_OP = 'INSERT' AND NEW.exception_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.operator_exceptions e
      WHERE e.exception_id = NEW.exception_id AND e.state = 'approved' AND e.expires_at > now()
      AND e.repository = NEW.repository AND e.class = NEW.class AND e.minimum = NEW.threshold) THEN
    RAISE EXCEPTION 'policy: promotion % names no approved exception of its class', NEW.promotion_id USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND NOT ((OLD.state = 'requested' AND NEW.state IN ('pr_opened', 'merged', 'abandoned'))
      OR (OLD.state = 'pr_opened' AND NEW.state IN ('merged', 'abandoned'))) THEN
    RAISE EXCEPTION 'policy: promotion % cannot move % to %', OLD.promotion_id, OLD.state, NEW.state USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND (NEW.closed_by IS NULL OR NEW.closed_at IS DISTINCT FROM now()
      OR (NEW.state IN ('pr_opened', 'merged') AND NEW.pull_request IS NULL)
      OR (OLD.pull_request IS NOT NULL AND NEW.pull_request IS DISTINCT FROM OLD.pull_request)) THEN
    RAISE EXCEPTION 'policy: promotion % moves at now(), by someone, and keeps the pull request it names', OLD.promotion_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER policy_promotions_move BEFORE INSERT OR UPDATE ON policy_promotions
  FOR EACH ROW EXECUTE FUNCTION policy_promotions_move();

-- The broker records and moves them, never rewrites what was asked or on what evidence. No
-- retention role reads them: they are the audit record, kept with the Git history they explain.
GRANT SELECT, INSERT ON operator_exceptions, policy_promotions TO rooms_broker;
GRANT UPDATE (state, decided_by, decided_at, note, expires_at) ON operator_exceptions TO rooms_broker;
GRANT UPDATE (state, pull_request, closed_by, closed_at) ON policy_promotions TO rooms_broker;
ALTER TABLE operator_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_promotions ENABLE ROW LEVEL SECURITY;
CREATE POLICY broker_operator_exceptions ON operator_exceptions FOR ALL TO rooms_broker USING (true) WITH CHECK (true);
CREATE POLICY broker_policy_promotions   ON policy_promotions   FOR ALL TO rooms_broker USING (true) WITH CHECK (true);
```

```go
// RequestException records e as requested, now.
func (s *Store) RequestException(ctx context.Context, e Exception) (Exception, error) {
	row := s.pool.QueryRow(ctx, `INSERT INTO operator_exceptions (exception_id, repository, class, minimum, justification,
		requested_by, state) VALUES ($1, $2, $3, $4, $5, $6, 'requested') RETURNING `+exceptionCols,
		e.ID, e.Repository, e.Class, e.Minimum, e.Justification, e.RequestedBy)
	out, err := scanException(row)
	return out, policyErr(err, ErrPolicyMoved)
}

// DecideException approves (until expires) or refuses a requested exception, once.
func (s *Store) DecideException(ctx context.Context, id, state, by, note string, expires time.Time) (Exception, error) {
	var exp *time.Time
	if state == ExceptionApproved {
		exp = &expires
	}
	row := s.pool.QueryRow(ctx, `UPDATE operator_exceptions SET state = $2, decided_by = $3, decided_at = now(),
		note = nullif($4, ''), expires_at = $5 WHERE exception_id = $1 RETURNING `+exceptionCols, id, state, by, note, exp)
	out, err := scanException(row)
	return out, policyErr(err, ErrPolicyMoved)
}

// RecordPromotion records p as requested, now: ErrPromotionOpen beside an open one of its class,
// ErrExceptionUnusable when its exception cannot carry it.
func (s *Store) RecordPromotion(ctx context.Context, p Promotion) (Promotion, error) {
	var exc *string
	if p.ExceptionID != "" {
		exc = &p.ExceptionID
	}
	row := s.pool.QueryRow(ctx, `INSERT INTO policy_promotions (promotion_id, repository, class, threshold, evidence,
		exception_id, requested_by, state) VALUES ($1, $2, $3, $4, $5, $6, $7, 'requested') RETURNING `+promotionCols,
		p.ID, p.Repository, p.Class, p.Threshold, p.Evidence, exc, p.RequestedBy)
	out, err := scanPromotion(row)
	return out, policyErr(err, ErrExceptionUnusable)
}

// MovePromotion moves a promotion to state, naming its pull request (0 keeps the one it names).
func (s *Store) MovePromotion(ctx context.Context, id, state string, pullRequest int, by string) (Promotion, error) {
	var pr *int
	if pullRequest > 0 {
		pr = &pullRequest
	}
	row := s.pool.QueryRow(ctx, `UPDATE policy_promotions SET state = $2, pull_request = coalesce($3, pull_request),
		closed_by = $4, closed_at = now() WHERE promotion_id = $1 RETURNING `+promotionCols, id, state, pr, by)
	out, err := scanPromotion(row)
	return out, policyErr(err, ErrPolicyMoved)
}

// policyErr maps the tables' refusals: a trigger's check_violation is a move the state does not
// allow, a unique violation the class's open promotion, no row an unknown id.
func policyErr(err error, check error) error {
	var pg *pgconn.PgError
	switch {
	case err == nil:
		return nil
	case errors.Is(err, pgx.ErrNoRows):
		return ErrNoPolicyRecord
	case errors.As(err, &pg) && pg.Code == "23505":
		return ErrPromotionOpen
	case errors.As(err, &pg) && pg.Code == "23514":
		return check
	}
	return fmt.Errorf("store: policy record: %w", err)
}
```

Run `atlas migrate validate --dir file://internal/store/migrations` and `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/store/ ./internal/store/migrations/`: PASS (Docker must be running).

### Task 9: The broker's routes

**Files:** Create `internal/humanapi/policy.go` and `internal/runrequest/policy.go`. Modify `internal/humanapi/server.go`, `internal/runrequest/coordination.go`, `internal/metrics/metrics.go` and `internal/app/broker.go`. Test in `internal/humanapi/policy_test.go` (byte-identical off; one row per role per handler; promotion and exception flows), `internal/runrequest/policy_test.go`, `internal/metrics/metrics_test.go` and `internal/app/broker_test.go`.

- [ ] **Step 1: Write the failing tests**

```go
// Off (policyManagement.promotion false), every stage 6 path answers exactly as a path that never
// existed: the route table is the one before stage 6, and nothing reads the factory or the store.
func TestPolicyOffIsByteIdentical(t *testing.T) {
	e := setup(t, func(s *Server, _ *fanout.Hub, _ *hubView) { s.Humans, s.UI = tokenAuth{}, policyIndex })
	wantCode, want := sendJSON(t, e, http.MethodGet, "/never-a-route", header("maint"), "")
	for _, p := range policyPaths {
		if code, body := sendJSON(t, e, p.method, p.path, header("maint"), "{}"); code != wantCode || body != want {
			t.Errorf("%s %s: %d %q, want %d %q", p.method, p.path, code, body, wantCode, want)
		}
	}
}

// MP7 server side: a maintainer's request is recorded on the evidence read again here; anyone
// else, a short count, or a class with no proposal is refused, and nothing is recorded.
func TestPromotionRequest(t *testing.T) {
	req := map[string]string{"repository": policyRepo, "class": "docs-links"}
	for name, tc := range map[string]struct {
		user   string
		clean  int
		bad    int
		drill  string
		body   any
		code   int
		reason string
	}{
		"a maintainer, eligible": {"maint", 20, 0, evidence.DrillPassed, req, http.StatusCreated, ""},
		"a reader":               {"anyone", 20, 0, evidence.DrillPassed, req, http.StatusForbidden, "not_a_maintainer"},
		"nineteen":               {"maint", 19, 0, evidence.DrillPassed, req, http.StatusConflict, "not_eligible"},
		"a bad outcome":          {"maint", 30, 1, evidence.DrillPassed, req, http.StatusConflict, "not_eligible"},
		"no drill":               {"maint", 30, 0, evidence.DrillOpen, req, http.StatusConflict, "not_eligible"},
		"a live class":           {"maint", 30, 0, evidence.DrillPassed, map[string]string{"repository": policyRepo, "class": "revert"}, http.StatusConflict, "not_promotable"},
		"no such class":          {"maint", 30, 0, evidence.DrillPassed, map[string]string{"repository": policyRepo, "class": "nope"}, http.StatusNotFound, "no_such_class"},
		"another repository":     {"maint", 30, 0, evidence.DrillPassed, map[string]string{"repository": "Smana/other", "class": "docs-links"}, http.StatusNotFound, "not_found"},
		"an unknown field":       {"maint", 30, 0, evidence.DrillPassed, `{"repository":"Smana/maku","class":"docs-links","mode":"live"}`, http.StatusBadRequest, "bad_json"},
		"an unbounded body":      {"maint", 30, 0, evidence.DrillPassed, `{"repository":"` + strings.Repeat("a", 9<<10) + `"}`, http.StatusBadRequest, "bad_json"},
	} {
		t.Run(name, func(t *testing.T) {
			f, m := newPolicy(tc.clean)
			f.bad, f.drill = tc.bad, tc.drill
			e := setup(t, policyOn(f, m))
			code, body := promote(t, e, tc.user, tc.body)
			if code != tc.code || (tc.reason != "" && !strings.Contains(body, `"`+tc.reason+`"`)) {
				t.Fatalf("%d %s", code, body)
			}
			if (code == http.StatusCreated) != (len(m.promotions) == 1) {
				t.Fatalf("recorded %d", len(m.promotions))
			}
		})
	}
}

// MP7's exception: a maintainer asks below the minimum with a justification, an operator alone
// decides it, once, and the approved exception carries a promotion at its own minimum.
func TestExceptionIsAnOperatorsDecision(t *testing.T) {
	f, m := newPolicy(12)
	e := setup(t, policyOn(f, m))
	ask := map[string]any{"repository": policyRepo, "class": "docs-links", "minimum": 10, "justification": "a narrow class: ten clean decisions bound it"}
	if code, body := sendJSON(t, e, http.MethodPost, "/api/policy/exceptions", header("maint"),
		map[string]any{"repository": policyRepo, "class": "docs-links", "minimum": 20, "justification": ask["justification"]}); code != http.StatusBadRequest ||
		!strings.Contains(body, "minimum_not_below") {
		t.Fatalf("%d %s", code, body)
	}
	if code, _ := sendJSON(t, e, http.MethodPost, "/api/policy/exceptions", header("anyone"), ask); code != http.StatusForbidden {
		t.Fatalf("a reader asked: %d", code)
	}
	code, body := sendJSON(t, e, http.MethodPost, "/api/policy/exceptions", header("maint"), ask)
	var exc store.Exception
	if code != http.StatusCreated || json.Unmarshal([]byte(body), &exc) != nil || exc.RequestedBy != "maint" {
		t.Fatalf("%d %s", code, body)
	}
	if code, body := promote(t, e, "maint", map[string]string{"repository": policyRepo, "class": "docs-links", "exceptionId": exc.ID}); code != http.StatusConflict ||
		!strings.Contains(body, "exception_unusable") {
		t.Fatalf("a requested exception carried it: %d %s", code, body)
	}
	path := "/api/policy/exceptions/" + exc.ID
	if code, _ := sendJSON(t, e, http.MethodPost, path, header("maint"), map[string]string{"decision": "approved"}); code != http.StatusForbidden {
		t.Fatalf("a maintainer approved: %d", code)
	}
	if code, body := sendJSON(t, e, http.MethodPost, path, header("ops"), map[string]string{"decision": "approved", "note": "ok for the canary"}); code != http.StatusOK ||
		!strings.Contains(body, `"decidedBy":"ops"`) {
		t.Fatalf("%d %s", code, body)
	}
	if code, _ := sendJSON(t, e, http.MethodPost, path, header("ops"), map[string]string{"decision": "refused"}); code != http.StatusConflict {
		t.Fatalf("decided twice: %d", code)
	}
	code, body = promote(t, e, "maint", map[string]string{"repository": policyRepo, "class": "docs-links", "exceptionId": exc.ID})
	if code != http.StatusCreated || !strings.Contains(body, `"threshold":10`) || !strings.Contains(body, `"exceptionId":"`+exc.ID+`"`) {
		t.Fatalf("%d %s", code, body)
	}
}
```

```go
// MP17, one row per role per handler: anyone who reads the repository views; a maintainer
// (write) previews, gets the edit link, requests and moves promotions and asks for exceptions;
// an operator decides exceptions; a machine and an anonymous caller do nothing.
func TestPolicyHandlersByRole(t *testing.T) {
	type route struct{ method, path, body string }
	routes := map[string]route{
		"repositories":     {http.MethodGet, "/api/policy/repositories", ""},
		"repository":       {http.MethodGet, "/api/policy/repositories/Smana/maku", ""},
		"decisions":        {http.MethodGet, "/api/policy/repositories/Smana/maku/decisions/12", ""},
		"settings":         {http.MethodGet, "/settings/merge-policies/Smana/maku", ""},
		"preview":          {http.MethodPost, "/api/policy/repositories/Smana/maku/preview", `{"file":"factory: aws-0\n"}`},
		"promote":          {http.MethodPost, "/api/policy/promotions", `{"repository":"Smana/maku","class":"docs-links"}`},
		"move":             {http.MethodPost, "/api/policy/promotions/pppppppp", `{"state":"pr_opened","pullRequest":12}`},
		"ask exception":    {http.MethodPost, "/api/policy/exceptions", `{"repository":"Smana/maku","class":"docs-links","minimum":10,"justification":"a narrow class: ten clean decisions bound it"}`},
		"decide exception": {http.MethodPost, "/api/policy/exceptions/xxxxxxxx", `{"decision":"approved"}`},
	}
	ok := func(code int) map[string]int {
		return map[string]int{"repositories": 200, "repository": 200, "decisions": 200, "settings": 200, "preview": code,
			"promote": code, "move": code, "ask exception": code, "decide exception": 403}
	}
	maint := ok(200)
	maint["promote"], maint["ask exception"] = 201, 201
	ops := ok(403)
	ops["decide exception"] = 200
	refused := func(code int) map[string]int {
		m := map[string]int{}
		for n := range routes {
			m[n] = code
		}
		m["settings"] = 200 // the page loads; every call it makes is refused
		return m
	}
	for role, want := range map[string]struct {
		h     http.Header
		codes map[string]int
	}{
		"reader":     {header("anyone"), ok(403)},
		"maintainer": {header("maint"), maint},
		"operator":   {header("ops"), ops},
		"machine":    {header("bot", "X-Test-Kind", "system"), refused(403)},
		"anonymous":  {http.Header{}, refused(401)},
	} {
		for name, rt := range routes {
			t.Run(role+" "+name, func(t *testing.T) {
				f, m := newPolicy(20)
				m.promotions["pppppppp"] = store.Promotion{ID: "pppppppp", Repository: policyRepo, Class: "revert", State: store.PromotionRequested}
				m.exceptions["xxxxxxxx"] = store.Exception{ID: "xxxxxxxx", Repository: policyRepo, Class: "docs-links", Minimum: 10, State: store.ExceptionRequested}
				e := setup(t, policyOn(f, m))
				var body any = ""
				if rt.body != "" {
					body = rt.body
				}
				code, out := sendJSON(t, e, rt.method, rt.path, want.h, body)
				if code != want.codes[name] {
					t.Fatalf("%d %s, want %d", code, out, want.codes[name])
				}
			})
		}
	}
}
```

- [ ] **Step 2: Implement**

```go
// Policy is the promotion workflow, policyManagement.promotion (stage 6): the settings pages, each
// class's evidence read through the factory, and the promotion and exception records. Maku records
// and links; a maintainer's own pull request changes the class (MP1, MP14).
type Policy struct {
	Factory PolicyGateway
	Records PolicyRecords
	// Operator is whether a GitHub login approves exceptions (policyManagement.operators).
	Operator func(login string) bool
	NewID    func() string
}

// policyRoutes registers the settings pages and the policy API; only with Policy set.
func (s *Server) policyRoutes(mux *http.ServeMux, index http.Handler) {
	for _, p := range []string{"GET /settings", "GET /settings/merge-policies", "GET /settings/merge-policies/{owner}/{name}",
		"GET /settings/merge-policies/{owner}/{name}/decisions/{pr}", "GET /settings/evidence"} {
		mux.Handle(p, withCSP(index))
	}
	mux.HandleFunc("GET /api/policy/repositories", s.policyRepositories)
	mux.HandleFunc("GET /api/policy/repositories/{owner}/{name}", s.policyRepository)
	mux.HandleFunc("POST /api/policy/repositories/{owner}/{name}/preview", s.policyPreview)
	mux.HandleFunc("GET /api/policy/repositories/{owner}/{name}/decisions/{pr}", s.policyDecisions)
	mux.HandleFunc("POST /api/policy/promotions", s.requestPromotion)
	mux.HandleFunc("POST /api/policy/promotions/{id}", s.movePromotion)
	mux.HandleFunc("POST /api/policy/exceptions", s.requestException)
	mux.HandleFunc("POST /api/policy/exceptions/{id}", s.decideException)
}

// requestPromotion is POST /api/policy/promotions {repository, class, exceptionId?}: a maintainer's
// request to promote a shadow class (MP7). The evidence is read again here, server side, and must
// hold: the minimum (or an approved exception's), no bad mature outcome, a passed drill. The
// answer is the recorded request and the one-line proposal; Maku opens no pull request.
func (s *Server) requestPromotion(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyCaller(w, r)
	if !ok {
		return
	}
	var in struct {
		Repository  string `json:"repository"`
		Class       string `json:"class"`
		ExceptionID string `json:"exceptionId"`
	}
	if !decodePolicy(w, r, &in) {
		return
	}
	rep, ok := s.report(w, r, p, in.Repository)
	if !ok {
		return
	}
	who, ok := s.maintainerOf(w, r, p, rep.Repository)
	if !ok {
		return
	}
	c, found := classOf(rep, in.Class)
	switch {
	case !found:
		refuseJSON(w, http.StatusNotFound, "no_such_class")
		return
	case c.Proposal == nil:
		refuseJSON(w, http.StatusConflict, "not_promotable")
		return
	}
	threshold := rep.Minimum
	if in.ExceptionID != "" {
		e, err := s.Policy.Records.Exception(r.Context(), in.ExceptionID)
		if err != nil || e.State != store.ExceptionApproved || e.Repository != rep.Repository || e.Class != c.Class ||
			e.ExpiresAt == nil || !e.ExpiresAt.After(s.now()) {
			refuseJSON(w, http.StatusConflict, "exception_unusable")
			return
		}
		threshold = e.Minimum
	}
	ev := c.Evidence
	if ev.Clean < threshold || ev.Bad > 0 || ev.Drill != evidence.DrillPassed {
		refuseJSON(w, http.StatusConflict, "not_eligible")
		return
	}
	snap, err := json.Marshal(promotionSnapshot{ReadAt: rep.ReadAt, Minimum: rep.Minimum, Threshold: threshold, Mode: c.Mode,
		Evidence: ev, Line: c.Proposal.Line})
	if err != nil {
		refuseJSON(w, http.StatusInternalServerError, "snapshot")
		return
	}
	out, err := s.Policy.Records.RecordPromotion(r.Context(), store.Promotion{ID: s.Policy.NewID(), Repository: rep.Repository,
		Class: c.Class, Threshold: threshold, Evidence: snap, ExceptionID: in.ExceptionID, RequestedBy: who.Login})
	if !s.recorded(w, err) {
		return
	}
	s.policyChange(r.Context(), out.Repository, out.Class, "promotion_requested")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(struct {
		Promotion store.Promotion   `json:"promotion"`
		Proposal  evidence.Proposal `json:"proposal"`
	}{out, *c.Proposal})
}

// decideException is POST /api/policy/exceptions/{id} {decision, note}: an operator approves (for
// ExceptionLifetime) or refuses a requested exception, once.
func (s *Server) decideException(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyCaller(w, r)
	if !ok {
		return
	}
	var in struct {
		Decision string `json:"decision"`
		Note     string `json:"note"`
	}
	if !decodePolicy(w, r, &in) {
		return
	}
	if (in.Decision != store.ExceptionApproved && in.Decision != store.ExceptionRefused) || len(in.Note) > 2000 {
		refuseJSON(w, http.StatusBadRequest, "bad_decision")
		return
	}
	cur, err := s.Policy.Records.Exception(r.Context(), r.PathValue("id"))
	if !s.recorded(w, err) {
		return
	}
	who, err := s.rolesOn(r.Context(), p, cur.Repository)
	switch {
	case err != nil:
		refuseJSON(w, http.StatusServiceUnavailable, reasonAccessUnverified)
		return
	case !who.Operator:
		refuseJSON(w, http.StatusForbidden, "not_an_operator")
		return
	}
	out, err := s.Policy.Records.DecideException(r.Context(), cur.ID, in.Decision, who.Login, in.Note, s.now().Add(ExceptionLifetime))
	if !s.recorded(w, err) {
		return
	}
	s.policyChange(r.Context(), out.Repository, out.Class, "exception_"+out.State)
	writeJSON(w, out)
}
```

```go
// policyPreview is POST /api/policy/repositories/{owner}/{name}/preview {file}: the editor's check
// of a proposed policy file, for a maintainer (MP17). The factory parses, validates against the
// central guardrails, compares structurally and simulates; nothing is written anywhere.
func (s *Server) policyPreview(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyCaller(w, r)
	if !ok {
		return
	}
	var in struct {
		File string `json:"file"`
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxPreviewBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil || dec.More() {
		refuseJSON(w, http.StatusBadRequest, "bad_json")
		return
	}
	rep, ok := s.report(w, r, p, r.PathValue("owner")+"/"+r.PathValue("name"))
	if !ok {
		return
	}
	if _, ok := s.maintainerOf(w, r, p, rep.Repository); !ok {
		return
	}
	pv, err := s.Policy.Factory.PolicyPreview(r.Context(), p.AccessToken, rep.Repository, in.File)
	if !s.forwarded(w, err) {
		return
	}
	writeJSON(w, pv)
}

// policyDecisions is GET /api/policy/repositories/{owner}/{name}/decisions/{pr}: a pull request's
// decision timeline, which the factory reads for a reader of the repository.
func (s *Server) policyDecisions(w http.ResponseWriter, r *http.Request) {
	p, ok := s.policyCaller(w, r)
	if !ok {
		return
	}
	pr, err := strconv.Atoi(r.PathValue("pr"))
	if err != nil || pr < 1 {
		refuseJSON(w, http.StatusBadRequest, "pr_required")
		return
	}
	tl, err := s.Policy.Factory.PolicyDecisions(r.Context(), p.AccessToken, r.PathValue("owner")+"/"+r.PathValue("name"), pr)
	if !s.forwarded(w, err) {
		return
	}
	writeJSON(w, tl)
}
```

```go
// SPDX-License-Identifier: Apache-2.0

package runrequest

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"strconv"

	"github.com/Smana/maku/internal/factory/evidence"
	"github.com/Smana/maku/internal/factory/policyview"
)

// PolicyEvidence is GET /v1/policy/evidence (merge policy stage 6) with the caller's own token: the
// repository's promotion evidence, which the factory reads for a reader of it on GitHub.
func (f Factory) PolicyEvidence(ctx context.Context, accessToken, repository string) (evidence.Report, error) {
	var out evidence.Report
	err := f.call(ctx, http.MethodGet, accessToken, "/v1/policy/evidence?repository="+url.QueryEscape(repository), http.NoBody, &out)
	return out, err
}

// PolicyRepositories is GET /v1/policy/repositories with the caller's own token: the configured
// repositories they read.
func (f Factory) PolicyRepositories(ctx context.Context, accessToken string) ([]string, error) {
	var out struct {
		Repositories []string `json:"repositories"`
	}
	err := f.call(ctx, http.MethodGet, accessToken, "/v1/policy/repositories", http.NoBody, &out)
	return out.Repositories, err
}

// PolicyPreview is POST /v1/policy/preview with the caller's own token: a proposed policy file
// checked, compared and simulated by the factory for a maintainer of the repository.
func (f Factory) PolicyPreview(ctx context.Context, accessToken, repository, file string) (policyview.Preview, error) {
	body, err := json.Marshal(map[string]string{"repository": repository, "file": file})
	if err != nil {
		return policyview.Preview{}, err
	}
	var out policyview.Preview
	err = f.call(ctx, http.MethodPost, accessToken, "/v1/policy/preview", bytes.NewReader(body), &out)
	return out, err
}

// PolicyDecisions is GET /v1/policy/decisions with the caller's own token: a pull request's
// decision timeline, for a reader of the repository.
func (f Factory) PolicyDecisions(ctx context.Context, accessToken, repository string, pr int) (policyview.Timeline, error) {
	var out policyview.Timeline
	q := url.Values{"repository": {repository}, "pr": {strconv.Itoa(pr)}}
	err := f.call(ctx, http.MethodGet, accessToken, "/v1/policy/decisions?"+q.Encode(), http.NoBody, &out)
	return out, err
}
```

```diff
@@ -199,6 +199,9 @@ type Set struct {
 	// rooms_coordination_checkout_manifests_total{outcome} (v4): a parent's filtered views and
 	// checkout documents, by a closed outcome.
 	coordViews, coordCheckouts metric.Int64Counter
+	// policyChanges is rooms_policy_changes_total{repository,class,change} (merge policy stage 6):
+	// the promotion workflow's records, by a closed change.
+	policyChanges metric.Int64Counter

 	meter             metric.Meter
 	appended          metric.Int64Counter
@@ -310,6 +313,9 @@ func New(meter metric.Meter) (*Set, error) {
 	s.needsList, err = meter.Int64Counter("needs_list_total", metric.WithDescription("Needs lists served, by surface, principal and outcome."))
 	check(err)
 	check(s.registerNeeds())
+	s.policyChanges, err = meter.Int64Counter("rooms_policy_changes_total",
+		metric.WithDescription("Merge policy promotion records, by repository, class and change: a promotion requested, its pull request opened, merged or abandoned; an exception requested, approved or refused."))
+	check(err)
 	s.coordViews, err = meter.Int64Counter("rooms_coordination_views_total", metric.WithDescription("Coordination parent views served, by outcome."))
 	check(err)
 	s.coordCheckouts, err = meter.Int64Counter("rooms_coordination_checkout_manifests_total",
@@ -444,6 +450,22 @@ func closed(set map[string]bool, v string) string {
 	return "other"
 }

+// PolicyChanges are rooms_policy_changes_total's change values.
+func PolicyChanges() []string {
+	return []string{"promotion_requested", "promotion_pr_opened", "promotion_merged", "promotion_abandoned",
+		"exception_requested", "exception_approved", "exception_refused"}
+}
+
+// PolicyChange counts one promotion record. repository and class are bounded by the caller: a
+// configured repository and a class its evidence named (MP18); a change off the list is not counted.
+func (s *Set) PolicyChange(ctx context.Context, repository, class, change string) {
+	if !slices.Contains(PolicyChanges(), change) {
+		return
+	}
+	s.policyChanges.Add(ctx, 1, metric.WithAttributes(attribute.String("repository", repository),
+		attribute.String("class", class), attribute.String("change", change)))
+}
+
 // CoordinationView counts one coordination view served: ok (every child readable), restricted (at
 // least one withheld), not_found or unverified.
 func (s *Set) CoordinationView(ctx context.Context, outcome string) {
```

```diff
@@ -234,6 +234,7 @@ func serveBroker(ctx context.Context, log *slog.Logger, getenv func(string) stri
 			humans.CoordinationWrites = g
 		}
 	}
+	humans.Policy = policyWorkflow(cfg, st)
 	if humans.Intake != nil {
 		// A sponsored plan resolves the Slack user to the account it is linked to, so the link tables
 		// are the planner's too (internal/humanapi/intake.go's requester).
@@ -582,6 +583,17 @@ func coordinationViews(cfg config.Config, r client.Reader, ns string) humanapi.C
 	return coordinationview.Source{Reader: r, Namespace: ns}
 }

+// policyWorkflow is the promotion workflow (merge policy stage 6): nil while
+// policyManagement.promotion is off, which serves no settings page and no policy route. The
+// evidence is the factory's, read with the caller's own token at the config's URL, never a request's.
+func policyWorkflow(cfg config.Config, st *store.Store) *humanapi.Policy {
+	if !cfg.PolicyManagement.Promotion || cfg.FactoryURL == "" {
+		return nil
+	}
+	return &humanapi.Policy{Factory: runrequest.Factory{URL: cfg.FactoryURL, CAFile: cfg.FactoryCAFile},
+		Records: st, Operator: cfg.PolicyManagement.IsOperator, NewID: runrequest.NewID}
+}
+
 // coordinationWrites is the factory's coordination routes, forwarded with the caller's own token:
 // nil while coordination is off or no factory is configured. The URL is the config's, never a
 // request's.
@@ -169,6 +169,9 @@ type Server struct {
 	// Coordination is coordination_plan (v4 MR4): listed beside the planner while its mode is not
 	// off. Nil, or off, lists nothing.
 	Coordination *CoordinationPlanner
+	// Policy is the promotion workflow (policyManagement.promotion, merge policy stage 6): the
+	// settings pages and the policy API. Nil serves neither: each path is the mux's 404.
+	Policy *Policy

 	// Connection bounds; zero takes the default.
 	HelloWait time.Duration // the first frame must arrive within it (10 s)
@@ -240,6 +243,9 @@ func (s *Server) Routes() http.Handler {
 	mux.HandleFunc("GET /api/roomctl", s.roomctlSetup)
 	mux.HandleFunc("GET /.well-known/roomctl", s.publicSetup)
 	mux.HandleFunc("GET /v1/ws", s.ws)
+	if s.Policy != nil {
+		s.policyRoutes(mux, index)
+	}
 	if s.SlackLink != nil {
 		s.slackLinkRoutes(mux)
 	}
```

- [ ] **Step 3: Run** `systemd-run --user --scope -q -p MemoryMax=6G go test -race -count=1 ./internal/humanapi/ ./internal/runrequest/ ./internal/metrics/ ./internal/app/` and `task lint`: PASS, `0 issues.`

### Task 10: The pages

**Files:** Create `web/src/settings.ts` and `web/src/policy-editor.ts`. Modify `web/src/main.ts` and `web/src/app.css`, then rebuild `internal/humanapi/ui/dist/`. Test in `web/test/settings.test.ts`.

- [ ] **Step 1: Write the failing tests**

```ts
describe("settings routes", () => {
  it("answers the four settings paths and nothing else", () => {
    for (const p of ["/settings", "/settings/merge-policies", "/settings/merge-policies/Smana/cloud-native-ref", "/settings/evidence",
      "/settings/merge-policies/Smana/cloud-native-ref/decisions/12"]) {
      expect(isSettings(p)).toBe(true);
    }
    for (const p of ["/", "/r/abcdefgh", "/settings/approval-memory", "/settings/merge-policies/Smana", "/settings/x/y/z"]) {
      expect(isSettings(p)).toBe(false);
    }
  });
});

describe("evidence", () => {
  it("writes MP7's numbers in one line and the widening ladder", () => {
    expect(evidenceLine(ev())).toBe("20/20 clean · 0 bad · 2 immature · 1 pending · bound 0.139 · drill passed");
    expect(ladderLine(ev({ ladder: [{ merges: 29, maxBad: 0, reached: true }, { merges: 46, maxBad: 1, reached: false }, { merges: 61, maxBad: 2, reached: false }] })))
      .toBe("29 ✓ / 46 / 61");
  });
  it("explains a refusal by its code, and names an unknown one", () => {
    expect(explain("not_eligible")).toMatch(/minimum/);
    expect(explain("brand_new")).toBe("Refused: brand_new");
  });
});

describe("the repository page", () => {
  it("offers a maintainer the promotion of an eligible shadow class, and shows the proposal it gets", async () => {
    const calls: string[] = [];
    const proposal = { path: ".github/agent-factory.yaml", line: 6, file: "factory: aws-0\nclasses: {}\n", editURL: "https://github.com/Smana/cloud-native-ref/edit/main/.github/agent-factory.yaml" };
    const get = fakeFetch({ "/api/policy/repositories/Smana/cloud-native-ref": page(), "/api/policy/promotions": { promotion: { id: "aaaaaaaa" }, proposal } }, calls);
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref", get);
    expect(app.textContent).toContain("20/20 clean");
    expect(app.textContent).toContain("glm-5.3 20/21");
    expect(app.textContent).toContain("not shadow");
    const buttons = [...app.querySelectorAll("button")].filter((b) => b.textContent === "Promote to live");
    expect(buttons).toHaveLength(1);
    buttons[0].click();
    await settle();
    expect(calls).toContain(`POST /api/policy/promotions {"repository":"Smana/cloud-native-ref","class":"docs-links"}`);
    const pre = app.querySelector("pre.proposal-file");
    expect(pre?.textContent).toBe(proposal.file);
    const edit = [...app.querySelectorAll("a")].find((a) => a.textContent === "edit the file on GitHub");
    expect(edit?.getAttribute("href")).toBe(proposal.editURL);
  });

  it("offers a reader no button: the broker would refuse it", async () => {
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref",
      fakeFetch({ "/api/policy/repositories/Smana/cloud-native-ref": page({ you: { login: "dev", maintainer: false, operator: false } }) }));
    expect(app.querySelectorAll("button.primary:not([disabled])")).toHaveLength(0);
  });

  it("offers a maintainer an exception below the minimum, and an operator its decision", async () => {
    const short = page();
    short.report.classes[0].evidence = ev({ clean: 12, eligible: false, blockers: ["below_minimum"] });
    short.exceptions = [{ id: "cccccccc", repository: "Smana/cloud-native-ref", class: "docs-links", minimum: 10,
      justification: "a narrow class: ten clean decisions bound it", requestedBy: "Smana", requestedAt: "2026-11-08T00:00:00Z", state: "requested" }];
    short.you = { login: "ops", maintainer: true, operator: true };
    const calls: string[] = [];
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref",
      fakeFetch({ "/api/policy/repositories/Smana/cloud-native-ref": short, "/api/policy/exceptions/cccccccc": {} }, calls));
    expect(app.textContent).toContain("below_minimum");
    expect([...app.querySelectorAll("button")].some((b) => b.textContent === "Ask an operator for an exception")).toBe(true);
    const approve = [...app.querySelectorAll("button")].find((b) => b.textContent === "Approve")!;
    approve.click();
    await settle();
    expect(calls).toContain(`POST /api/policy/exceptions/cccccccc {"decision":"approved"}`);
  });

  it("says why a repository cannot be read, not a blank page", async () => {
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/secret", fakeFetch({}));
    expect(app.textContent).toContain("Not found, or not readable");
  });
});
```

```ts
describe("the policy editor", () => {
  it("writes the file as YAML: factory first, patterns double-quoted, scalar lists in flow", () => {
    expect(fileYAML({ factory: "aws-0", classes: { "docs-links": { mode: "off", author: "agents", harness: "p",
      conditions: { all: [{ allowedFiles: ["^docs/.+\\.md$"] }, { maxPatchFiles: 3 }], any: [[{ modifyOnly: true }]] } } } }))
      .toBe('factory: "aws-0"\nclasses:\n  docs-links:\n    mode: "off"\n    author: "agents"\n    harness: "p"\n    conditions:\n' +
        '      all:\n        - allowedFiles: ["^docs/.+\\\\.md$"]\n        - maxPatchFiles: 3\n      any:\n        - - modifyOnly: true\n');
    expect(toYAML({ a: {}, b: undefined, c: [] })).toBe("c: []");
  });
  it("sets a leaf in place, and an empty value removes it", () => {
    const all = [{ allowedFiles: ["^a$"] }, { maxPatchFiles: 3 }];
    expect(setLeaf(all, "maxPatchFiles", 5)).toEqual([{ allowedFiles: ["^a$"] }, { maxPatchFiles: 5 }]);
    expect(setLeaf(all, "allowedFiles", [])).toEqual([{ maxPatchFiles: 3 }]);
    expect(setLeaf(all, "modifyOnly", true)).toEqual([...all, { modifyOnly: true }]);
  });
  it("edits a class in the form, rewrites the expert view, and shows the factory's check", async () => {
    const calls: string[] = [];
    const preview = { valid: true, structural: [{ class: "docs-links", kind: "tightening" }],
      simulation: { enabled: true, counts: { unchanged: 15, newly_blocked: 1 }, rows: [{ name: "01-arms", class: "docs-links",
        central: { verdict: "arm" }, repository: { verdict: "human", reason: "patch_too_large" }, change: "newly_blocked", conforms: true }] },
      strictness: [{ class: "docs-links", refused: 3, refusedMergedUnchanged: 2 }],
      proposal: { path: ".github/agent-factory.yaml", file: "factory: aws-0\n", editURL: "https://github.com/Smana/cloud-native-ref/edit/main/.github/agent-factory.yaml" } };
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref",
      fakeFetch({ "/api/policy/repositories/Smana/cloud-native-ref": page(), "/api/policy/repositories/Smana/cloud-native-ref/preview": preview }, calls));
    const yaml = app.querySelector("textarea.expert-yaml") as HTMLTextAreaElement;
    expect(yaml.value).toBe("factory: aws-0\nclasses:\n  docs-links:\n    mode: shadow\n"); // the file as it is, comments and all
    const cap = [...app.querySelectorAll(".editor-field")].find((l) => l.textContent?.startsWith("maxPatchFiles"))!.querySelector("input")!;
    cap.value = "5";
    cap.dispatchEvent(new Event("input"));
    expect(yaml.value).toContain("        - maxPatchFiles: 5\n");
    expect(yaml.value).toContain('factory: "aws-0"');
    const check = [...app.querySelectorAll("button")].find((b) => b.textContent === "Check, compare and simulate")!;
    check.click();
    await settle();
    expect(calls.at(-1)).toMatch(/^POST \/api\/policy\/repositories\/Smana\/cloud-native-ref\/preview /);
    expect(app.textContent).toContain("docs-links: tightening");
    expect(app.textContent).toContain("newly blocked: 1");
    expect(app.textContent).toContain("3 refused by a class row, 2 of them then merged unchanged");
    expect(app.querySelector(".editor-preview pre.proposal-file")?.textContent).toBe("factory: aws-0\n");
  });
  it("starts a new class from a template, on a central profile", async () => {
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref", fakeFetch({ "/api/policy/repositories/Smana/cloud-native-ref": page() }));
    const pick = app.querySelector('select[aria-label="class to edit"]') as HTMLSelectElement;
    pick.value = "template:deps-patch";
    pick.dispatchEvent(new Event("change"));
    const mode = app.querySelector(".editor-form select") as HTMLSelectElement;
    mode.value = "shadow";
    mode.dispatchEvent(new Event("change"));
    const yaml = (app.querySelector("textarea.expert-yaml") as HTMLTextAreaElement).value;
    expect(yaml).toContain("  deps-patch:\n");
    expect(yaml).toContain('harness: "docs-standard"');
    expect(yaml).toContain('logins: ["renovate[bot]"]');
  });
  it("lets a reader see the editor but not check: the broker would refuse it", async () => {
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref",
      fakeFetch({ "/api/policy/repositories/Smana/cloud-native-ref": page({ you: { login: "dev", maintainer: false, operator: false } }) }));
    const check = [...app.querySelectorAll("button")].find((b) => b.textContent === "Check, compare and simulate")!;
    expect(check.disabled).toBe(true);
  });
});

describe("the decision timeline", () => {
  it("renders each decision's rows, revisions and links", async () => {
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref/decisions/24", fakeFetch({
      "/api/policy/repositories/Smana/cloud-native-ref/decisions/24": { repository: "Smana/cloud-native-ref", pullRequest: 24, decisions: [{
        at: "2026-10-01T00:00:00Z", head: "a24", class: "docs-links", verdict: "human", reason: "patch_too_large",
        steps: [{ row: "fixed_base", status: "passed" }, { row: "class", status: "refused", detail: "patch_too_large" }, { row: "grant", status: "reserved" }],
        revisions: [{ row: "repository policy", status: "recorded", detail: "sha256 0123456789ab, dual=agree" }],
        commentURL: "https://github.com/Smana/cloud-native-ref/pull/24#issuecomment-1", policyURL: "https://github.com/Smana/cloud-native-ref/commits/HEAD/.github/agent-factory.yaml" }] } }));
    expect(app.textContent).toContain("docs-links · human:patch_too_large");
    expect(app.textContent).toContain("refused");
    expect(app.textContent).toContain("sha256 0123456789ab");
    expect(app.querySelector('a[href="https://github.com/Smana/cloud-native-ref/pull/24#issuecomment-1"]')).not.toBeNull();
  });
  it("says so when the pull request has no decision", async () => {
    const app = document.createElement("div");
    await mountSettings(app, "/settings/merge-policies/Smana/cloud-native-ref/decisions/9", fakeFetch({
      "/api/policy/repositories/Smana/cloud-native-ref/decisions/9": { repository: "Smana/cloud-native-ref", pullRequest: 9, decisions: [] } }));
    expect(app.textContent).toContain("recorded no decision");
  });
});
```

- [ ] **Step 2: Implement.** The page's routing, evidence and proposal:

```ts
// The routes this module answers, as the broker serves them.
export function isSettings(path: string): boolean {
  return /^\/settings(\/merge-policies(\/[^/]+\/[^/]+(\/decisions\/[0-9]+)?)?|\/evidence)?$/.test(path);
}

// evidenceLine is a class's evidence in one line, the numbers MP7 decides on.
export function evidenceLine(e: Evidence): string {
  return `${e.clean}/${e.minimum} clean · ${e.bad} bad · ${e.immature} immature · ${e.pending} pending · bound ${e.bound.toFixed(3)} · drill ${e.drill}`;
}

export function ladderLine(e: Evidence): string {
  return e.ladder.map((s) => `${s.merges}${s.reached ? " ✓" : ""}`).join(" / ");
}

// showProposal shows the one-line change and where to submit it: GitHub's edit page takes no
// prefilled content for an existing file, so the file is shown whole, its changed line named.
export function showProposal(main: HTMLElement, p: Proposal) {
  const box = el("section", undefined, "proposal");
  box.append(el("h2", "Your promotion pull request"));
  const lead = el("p", `Change line ${p.line} of ${p.path} from mode: shadow to mode: live, as below, then propose it as a pull request: `);
  lead.append(link(p.editURL, "edit the file on GitHub"));
  box.append(lead, el("pre", p.file, "proposal-file"));
  const copy = el("button", "Copy the file");
  copy.type = "button";
  copy.onclick = () => void navigator.clipboard?.writeText(p.file);
  box.append(copy);
  main.prepend(box);
}
```

The editor's YAML, leaves and cleanup:

```ts
// toYAML writes a policy file as YAML: block mappings, scalar lists in flow, every string
// double-quoted (JSON's escapes are YAML's), so a pattern is never read as anything else.
export function toYAML(v: unknown, indent = 0): string {
  const pad = " ".repeat(indent);
  const lines: string[] = [];
  if (Array.isArray(v)) {
    for (const item of v) {
      if (isScalar(item)) { lines.push(`${pad}- ${scalar(item)}`); continue; }
      const sub = toYAML(item, indent + 2).split("\n");
      sub[0] = `${pad}- ${sub[0].slice(indent + 2)}`;
      lines.push(...sub);
    }
    return lines.join("\n");
  }
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
    if (val === undefined || val === null) continue;
    if (isScalar(val)) lines.push(`${pad}${k}: ${scalar(val)}`);
    else if (Array.isArray(val) && val.every(isScalar)) lines.push(`${pad}${k}: [${val.map(scalar).join(", ")}]`);
    else if (!Array.isArray(val) && Object.keys(val as object).length === 0) continue;
    else lines.push(`${pad}${k}:`, toYAML(val, indent + 2));
  }
  return lines.join("\n");
}

// setLeaf sets (or, for an empty value, removes) the leaf of key in all, in place of the old one.
export function setLeaf(all: Leaf[], key: string, v: unknown): Leaf[] {
  const empty = v === undefined || v === "" || v === false || (Array.isArray(v) && v.length === 0) || (typeof v === "number" && isNaN(v));
  const i = all.findIndex((l) => key in l);
  const out = all.filter((_, j) => j !== i);
  if (empty) return out;
  const at = i < 0 ? out.length : i;
  out.splice(at, 0, { [key]: v });
  return out;
}

// cleanClass is a class as the form edited it, with the empty sections dropped.
export function cleanClass(c: ClassPolicy): ClassPolicy {
  const out = structuredClone(c);
  if (out.conditions) {
    if (!out.conditions.all?.length) delete out.conditions.all;
    if (!out.conditions.deny?.length) delete out.conditions.deny;
    if (!out.conditions.any?.length) delete out.conditions.any;
    if (Object.keys(out.conditions).length === 0) delete out.conditions;
  }
  if (out.monitor && typeof out.monitor.followUpWindow === "string") out.monitor.followUpWindow = duration(out.monitor.followUpWindow);
  return out;
}
```

```diff
@@ -2,6 +2,7 @@

 import { fetchDashboards } from "./dashboards";
 import { mountRoom } from "./room";
+import { isSettings, mountSettings } from "./settings";
 import { initTheme } from "./theme";
 import { listRooms } from "./view";

@@ -12,4 +13,6 @@ const app = document.getElementById("app")!;
 const theme = initTheme();

 const m = location.pathname.match(/^\/r\/([a-z2-7]{8})$/);
-if (m) mountRoom(app, m[1], theme, { dashboards: () => fetchDashboards(fetch) }); else void listRooms(app, fetch, {}, theme);
+if (m) mountRoom(app, m[1], theme, { dashboards: () => fetchDashboards(fetch) });
+else if (isSettings(location.pathname)) void mountSettings(app, location.pathname, fetch, theme);
+else void listRooms(app, fetch, {}, theme);
```

- [ ] **Step 3: Run** `task ui:test && task ui:build && task ui:check`: PASS.

- [ ] **Step 4: Screenshots.** Start a fixture server that serves the built `dist/` for `/settings*` and canned `/api/policy/*` answers. A one-click state is triggered by a `?click=<button>` parameter, which only that server reads. Capture each page with `chromium --headless=new --screenshot`:

| Page | File |
|---|---|
| `/settings` | `01-settings.png` |
| `/settings/merge-policies` | `02-merge-policies.png` |
| `/settings/merge-policies/<repo>` (classes, records, editor) | `03-repository.png` |
| the same page after **Check** | `04-editor-check.png` |
| the same page after **Promote to live** | `05-promote.png` |
| `/settings/evidence` | `06-evidence.png` |
| `/settings/merge-policies/<repo>/decisions/<pr>` | `07-decision-timeline.png` |

Push them to the orphan branch `screenshots/merge-policy-stage-6` and embed their raw URLs in the PR body. They are never committed to the PR branch.

### Task 11: Docs

- [ ] Update `docs/factory.md`: the switch and operators rows, `minPromotionEvidence`, and a `### Promotion` section covering the evidence, the editor and the timeline. Update `docs/operations.md` for the metric, `docs/api.md` for the broker's and the factory's policy routes, and `docs/web-ui.md` for the settings pages and who may do what. `task docs && task names`: PASS.

### Task 12: The gate

```bash
systemd-run --user --scope -q -p MemoryMax=6G task check
```

Expect exit 0. Push, update the PR body with `gh api -X PATCH`, read it back, and poll `gh pr view <n> --repo Smana/maku --json statusCheckRollup` until `check` and `analyze` are green.

### Task 13: The stage 6 exit (live, after stage 4's cutover of the canary)

- [ ] **Step 1: Preconditions.** Stage 4 has cut cloud-native-ref over to its own policy file, the Maku release holding this plan is pinned, and a shadow class of the canary's file has a monitor.
- [ ] **Step 2: Switch it on** with one config PR in ai-native-ref: `policyManagement: {promotion: true, simulation: true, operators: [Smana]}`, in both the factory's and the broker's config. The owner merges it.
- [ ] **Step 3: Compare the page with the script.** Run `scripts/shadow-merge-tally.sh --class <class> --repo Smana/cloud-native-ref`, both plain and with `--outcomes --since <180 days ago> --window <followUpWindow>`, then with `--strictness`. Expected: the page's clean, bad, bound, reviewer lines and strictness match.
- [ ] **Step 4: One editor change.** A maintainer lowers a cap in the form and runs **Check**. Expected: a `tightening`, the simulation counts shown, and a proposed file whose only diff is that cap.
- [ ] **Step 5: One promotion request.** When the class is eligible (20 clean decisions, no bad outcome, a merged `factory/drill` revert), a maintainer presses **Promote to live**, opens the pull request from the edit link with the proposed file, and records its number. Expected: the pull request changes exactly the named line, `mode: shadow` to `mode: live`. policy-bot holds it for a human (MP14). `maku_rooms_policy_changes_total{change="promotion_requested"}` and `{change="promotion_pr_opened"}` are both 1, and the row holds the evidence.
- [ ] **Step 6: Record the result** in `docs/runbooks/agent-factory/results-merge-policy-stage-6-<date>.md`. Stage 6 exits when one promotion request has produced a correct, human-reviewed pull request.

---

## Not built here

| Not built | Why |
|---|---|
| Checking `merged` against GitHub | The maintainer records it. The fence read sees the class live once stage 4 decides on the repository's file |
| A settings link on the room list | The pages are reached by address and from each other. The room list's header is outside this spec |
| `/settings/approval-memory` | Stage 5's page |

## Self-review

- **Coverage:** The spec's "Maku settings UI" maps to Tasks 6, 7, 9 and 10. The routes are P15. The policy editor (guided form, templates, expert YAML, strict validation, structural diff, simulation, edit link) is P11–P13. Promotion and evidence are Tasks 2–5, 8 and 9. The decision timeline is P14. Stage 6's exit is Task 13. In the Testing table: the Promotion row is `TestEligibility`, `TestTheWideningLadder`, the fixture tests and the exception audit; the Web UI row is the Vitest settings, editor and timeline tests; the Human API row is the per-role tables, the bounded bodies and the byte-identical off test.
- **Placeholders:** none. What is not built is named above with its reason.
- **Names:** `Promotion`, `Operators`, `MinPromotionEvidence`, `Evidence`, `Report`, `Proposal`, `Propose`, `Check`, `Decisions`, `ConformanceCases`, `PolicyEditor`, `Policy`, `PolicyChange`, `policy_promotions` and `operator_exceptions` are used consistently across tasks.
