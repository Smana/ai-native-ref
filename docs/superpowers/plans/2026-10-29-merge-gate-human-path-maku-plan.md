# Merge gate human path, Maku PRs 1–3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In Maku (agent-platform), a maintainer's approval merges an agent pull request; shadow
decisions ignore the pause and the caps; drills never trip the breaker and a tripped class recovers
on three clean mature merges; every decision leaves a replayable record, and the human path is
measured. Released as the next minor, which ai-native-ref pins.

**Architecture:** Three pull requests in agent-platform, each merging on its offline proof. PR 1
changes row 3 of `DecideArm` and the returns to the gate (AM1–AM3, AM5). PR 2 re-orders the
blockers and changes the breaker's inputs and recovery (AM4, AM6, AM7, the paused gauge). PR 3 adds
the decision record, the metrics' labels and histogram, and the tally's replay (AM8–AM10). Every new
behaviour ships off by default (`approveToMerge: false`, `recoverAfter: 0`), so the release changes
nothing until ai-native-ref's adopt plan turns it on.

**Tech Stack:** Go 1.25 (controller-runtime, envtest, `githubv4`), OpenTelemetry metrics, bash and
jq for the tally, `task` as the runner.

**Spec:** [the human path design](../specs/2026-10-29-merge-gate-human-path-design.md), decisions
AM1–AM10, the sections "Approve-to-merge", "The breaker", "The decision record and the human path",
"Configuration, labels and status fields" and "Testing". This plan lives in ai-native-ref and is
copied to agent-platform's `docs/superpowers/plans/` by the first PR that executes it, as the
feature 13 plan was.

## Global Constraints

- **Repository and branches.** agent-platform at `/home/smana/Sources/agent-platform`, module
  `github.com/Smana/maku`. One worktree per PR from a freshly fetched `origin/main`:
  `git -C /home/smana/Sources/agent-platform worktree add /home/smana/Sources/agent-platform-<topic> -b <branch> origin/main`.
  Branches: PR 1 `feat/approve-to-merge`, PR 2 `feat/breaker-evidence`, PR 3
  `feat/decision-record`. Rebase onto a freshly fetched `origin/main` before every push.
- **The evidence.** `task check` exits 0 (store tests need Docker; start the daemon for the final
  run of each PR only), `task lint` 0 issues, envtest with
  `KUBEBUILDER_ASSETS=/home/smana/.local/share/kubebuilder-envtest/k8s/1.36.2-linux-amd64` and
  `-p 1`, `task crd:gen` then `task crd:check` and `task chart:check` after an API change.
- **Conventions** (agent-platform's AGENTS.md): `// SPDX-License-Identifier: Apache-2.0` on every
  `.go` file; doc comments on exported symbols in the file's register (short, factual, naming the
  ruling); every "no" fails towards a human with its own reason (property 3).
- **Off by default.** `merge.approveToMerge` defaults to false and `merge.breaker.recoverAfter` to
  0: a Maku upgraded without a config change behaves as today, except that shadow decisions no
  longer read `class_paused` or `auto_merge_cap` (AM4, deliberate) and the metrics carry more labels.
- **Commits** are conventional, in English, with no trailers. PR descriptions in English.
- **Naming.** "Agent Factory" is the product; Maku is the controller. Logins fold case
  (`forge.SameLogin`).
- **Verbatim from the spec:**
  - AM1: "a maintainer's `APPROVED` review of the current head arms the merger: it merges that head,
    outside the caps, recorded as a human merge. Agents author mode only".
  - AM2: "From any hand-off a human's judgement covers, on the hand-off head, once per review,
    uncounted against `maxGateReentries`"; the refused reasons are `not_agent_authored`,
    `gate_path`, `contract_modified`, `not_owned`, `steering_path`, `foreign_trailer`,
    `not_mergeable`, `changes_requested`.
  - AM4: "A shadow class records `shadow_would_arm` whatever the breaker and the day's count say;
    the marker says `paused=` and `capped=`".
  - AM6: "the ledger does not count that revert"; "A `main_red` revert is never a drill".
  - AM7: "the class resumes if the `recoverAfter` newest merges are all newer than the newest bad
    merge, carry no revert, follow-up or regression, and are mature".
  - AM8: the marker vector `files=2/3 lines=12/20 shape=ok holdout=ok oracle=ok age=n/a evidence=ok paused=false capped=false reviewer=glm-5.3`.

## File structure

| File | Responsibility | PR |
|---|---|---|
| `internal/factory/forge/forge.go`, `github.go` | `Review.Commit`; `LabelledPull.Labels` | 1, 2 |
| `internal/factory/config/config.go` | `Merge.ApproveToMerge`, `Breaker.RecoverAfter` | 1, 2 |
| `api/factory/v1alpha1/task_types.go` | `PullRequestRef.MergedHow`, `ApprovedBy`, `Drill`, `HandedOffAt`; `AnnotationDrill` | 1, 2, 3 |
| `internal/factory/reconciler/arm.go` | Row 3 (`approval`), the blockers' order, `ArmDecision.Rows` | 1, 2, 3 |
| `internal/factory/reconciler/merge.go` | The approved merge, `reenter`, `paused`/`Demoted`, the record and the histogram | 1, 2, 3 |
| `internal/factory/reconciler/ledger.go` | `DrillLabel`, `ApprovedMergeLabel`, reverts without drills, `Merge.Mature` | 1, 2 |
| `internal/factory/reconciler/implement.go` | `prEnded` records the hand-off-to-merge time | 3 |
| `internal/factory/intake/issues.go` | `factory/drill` read beside `factory/revert` | 2 |
| `internal/factory/narrate/narrate.go` | `WaitingForApproval`, `ArmedByApproval`, `WouldArm` blockers, `Decision` | 1, 2, 3 |
| `internal/factory/fmetrics/fmetrics.go` | `approved_merged`, `class_paused`, `repository`, `reason`/`class`, the histogram | 1, 2, 3 |
| `scripts/shadow-merge-tally.sh`, `scripts/shadow-merge-tally_test.sh` | `drill=`, `--replay`, `--strictness`, per-model counts | 2, 3 |
| `docs/factory.md`, `docs/operations.md` | The merge gate, the reason table, calibration, the metrics | 1, 2, 3 |

---

## PR 1 — `feat/approve-to-merge`: a maintainer's approval merges (AM1–AM3, AM5)

### Task 1: `forge.Review.Commit`

**Files:**
- Modify: `internal/factory/forge/forge.go` (`type Review struct`)
- Modify: `internal/factory/forge/github.go` (the pull request query's `Reviews.Nodes`, and the `Review{…}` conversion near `out.Reviews = append`)
- Modify: `internal/factory/forge/forgetest/fake.go` (nothing to change: `SetPR` takes a `forge.PR` whose reviews now carry `Commit`)

**Interfaces:**
- Produces: `forge.Review.Commit string` — the full oid of the commit the review was submitted on, `""` when GitHub did not say.

- [ ] **Step 1: Add the field**

```go
type Review struct {
	ID     int64
	Author string
	State  string // APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED
	// Association ... (unchanged)
	Association string
	// Commit is the head the review was submitted on (GitHub's review.commit): row 3 arms on an
	// approval of the current head only (human path AM1), and "" never matches a head.
	Commit   string
	Body     string
	At       time.Time
	Comments []ReviewComment
}
```

- [ ] **Step 2: Fetch and convert it**

In the query's review node, beside `AuthorAssociation`:

```go
						Commit *struct{ Oid string } `graphql:"commit"`
```

In the conversion:

```go
		rv := Review{ID: r.DatabaseID, Author: r.Author.login(), State: r.State, Body: r.Body, Association: r.AuthorAssociation}
		if r.Commit != nil {
			rv.Commit = r.Commit.Oid
		}
```

- [ ] **Step 3: Build and run the forge tests**

Run: `go build ./... && go test ./internal/factory/forge/... -count=1`
Expected: PASS (no test reads the field yet; Task 2's do, through the fake).

- [ ] **Step 4: Commit**

```bash
git add internal/factory/forge/forge.go internal/factory/forge/github.go
git commit -m "feat(forge): a review carries the commit it was submitted on"
```

### Task 2: Row 3 — the approval arms when `approveToMerge` is on

**Files:**
- Modify: `internal/factory/config/config.go` (`type Merge struct`)
- Modify: `internal/factory/reconciler/arm.go` (`DecideArm`, new `approval`)
- Test: `internal/factory/reconciler/arm_test.go`

**Interfaces:**
- Consumes: `forge.Review.Commit` (Task 1).
- Produces: `config.Merge.ApproveToMerge bool`; `ArmDecision.Approver string`; the reasons `approval_stale` and `changes_requested` on agent tasks; `approval(in ArmInputs, rc *config.Repository) (forge.Review, string)` returning the state `""`, `"approved"`, `"stale"` or `"veto"`.

- [ ] **Step 1: Write the failing tests**

Append to `arm_test.go`:

```go
// Human path AM1: with merge.approveToMerge, a maintainer's APPROVED review of the current head
// arms the merger; off, it hands off as before. Only the current head counts, the newest review of
// each maintainer counts, and a truncated list is a veto.
func TestAMaintainersApprovalArmsWhenTheSwitchIsOn(t *testing.T) {
	review := func(login, state, commit string, at int) forge.Review {
		return forge.Review{ID: int64(at), Author: login, State: state, Commit: commit, At: now.Add(time.Duration(at) * time.Minute)}
	}
	for name, c := range map[string]struct {
		on              bool
		reviews         []forge.Review
		truncated       bool
		verdict, reason string
	}{
		"off: an approval hands off as today":       {false, []forge.Review{review("Smana", "APPROVED", head, 1)}, false, "human", "maintainer_approved"},
		"on: an approval of the head arms":          {true, []forge.Review{review("Smana", "APPROVED", head, 1)}, false, "arm", "maintainer_approved"},
		"on: an approval of another head is stale":  {true, []forge.Review{review("Smana", "APPROVED", oldHead, 1)}, false, "human", "approval_stale"},
		"on: an approval with no commit is stale":   {true, []forge.Review{review("Smana", "APPROVED", "", 1)}, false, "human", "approval_stale"},
		"on: a newer request for changes vetoes":    {true, []forge.Review{review("Smana", "APPROVED", head, 1), review("Smana", "CHANGES_REQUESTED", head, 2)}, false, "human", "changes_requested"},
		"on: a later approval lifts the request":    {true, []forge.Review{review("Smana", "CHANGES_REQUESTED", head, 1), review("Smana", "APPROVED", head, 2)}, false, "arm", "maintainer_approved"},
		"on: a non-maintainer's approval is advice": {true, []forge.Review{review("alice", "APPROVED", head, 1)}, false, "shadow", "shadow_would_arm"},
		"on: a truncated review list vetoes":        {true, []forge.Review{review("Smana", "APPROVED", head, 1)}, true, "human", "changes_requested"},
	} {
		t.Run(name, func(t *testing.T) {
			cfg := armCfg()
			cfg.Merge.ApproveToMerge = c.on
			cfg.Classes["docs-links"] = config.Class{Shadow: true}
			pr := agentPR()
			pr.Reviews, pr.ReviewsTruncated = c.reviews, c.truncated
			tk := armTask("docs-links", "solo", "")
			d := DecideArm(ArmInputs{PR: pr, Checks: green("SUCCESS"), Task: tk, Cfg: cfg, ReportedHead: head,
				Files: changed("[a](https://x/old)", "[a](https://x/new)"), DiffRead: true})
			if d.Verdict != c.verdict || d.Reason != c.reason {
				t.Fatalf("%s %s, want %s %s", d.Verdict, d.Reason, c.verdict, c.reason)
			}
			if d.Verdict == "arm" && d.Approver != "Smana" {
				t.Fatalf("approver %q", d.Approver)
			}
		})
	}
}
```

`now` is the package's test clock (`merge_test.go`); `armCfg`, `green`, `armTask`, `agentPR`,
`changed`, `head`, `oldHead` are `arm_test.go`'s helpers.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler/ -run TestAMaintainersApprovalArmsWhenTheSwitchIsOn -count=1`
Expected: FAIL, `cfg.Merge.ApproveToMerge undefined` (a compile error is the failure here).

- [ ] **Step 3: The config key**

In `config.go`'s `Merge`:

```go
	// ApproveToMerge: a maintainer's APPROVED review of the current head arms the merger on an
	// agents pull request (human path AM1). Off, the approval hands off to a human merge.
	ApproveToMerge bool `json:"approveToMerge,omitempty"`
```

Nothing to validate: a bool. The strict decoder refuses it on an older Maku, which the adopt plan
relies on.

- [ ] **Step 4: Row 3**

In `arm.go`, replace the loop over `in.PR.Reviews` in `DecideArm` with:

```go
	switch rv, st := approval(in, rc); st {
	case "veto":
		return human("changes_requested", "review")
	case "stale":
		return human("approval_stale", "review")
	case "approved":
		if !rc.Merge.ApproveToMerge {
			return human("maintainer_approved", "review") // success came from a human: a human merges
		}
		return ArmDecision{Verdict: "arm", Reason: "maintainer_approved", Matched: "review", Approver: rv.Author}
	}
```

and add, after `DecideArm`:

```go
// approval is row 3's read of an agents pull request (human path AM1): the newest review of each
// maintainer. veto when one of them is a request for changes, or when GitHub cut the list, so a
// veto may be unseen; stale when the newest approval is of another head, or of no head GitHub
// named (fail closed); approved when it is of the current head. With the switch off an approval
// of any head reads approved, as the rule always did: the switch changes what row 3 does, not
// what it sees. Adopted pull requests read nothing here: their veto is adoptEvidence's.
func approval(in ArmInputs, rc *config.Repository) (forge.Review, string) {
	if in.PR.ReviewsTruncated && rc.Merge.ApproveToMerge {
		return forge.Review{}, "veto"
	}
	newest := map[string]forge.Review{}
	for _, rv := range in.PR.Reviews {
		if !rc.IsMaintainer(rv.Author) || rv.State == "COMMENTED" {
			continue
		}
		if cur, ok := newest[strings.ToLower(rv.Author)]; !ok || rv.At.After(cur.At) {
			newest[strings.ToLower(rv.Author)] = rv
		}
	}
	var approved forge.Review
	for _, rv := range newest {
		switch rv.State {
		case "CHANGES_REQUESTED":
			if rc.Merge.ApproveToMerge {
				return rv, "veto"
			}
		case "APPROVED":
			approved = rv
		}
	}
	switch {
	case approved.Author == "":
		return forge.Review{}, ""
	case !rc.Merge.ApproveToMerge, approved.Commit == in.PR.HeadSHA:
		return approved, "approved"
	default:
		return approved, "stale"
	}
}
```

Add `Approver string` to `ArmDecision` with the comment `// Approver is the maintainer whose
approval armed row 3 (AM1); "" otherwise.`

- [ ] **Step 5: Run the tests**

Run: `go test ./internal/factory/reconciler/ -run 'TestAMaintainersApprovalArmsWhenTheSwitchIsOn|TestHeadAndVerdictMustBeFresh' -count=1`
Expected: PASS. Then `go test ./internal/factory/reconciler/ -count=1 -p 1` with
`KUBEBUILDER_ASSETS` set: PASS (the off path is unchanged).

- [ ] **Step 6: Commit**

```bash
git add internal/factory/config/config.go internal/factory/reconciler/arm.go internal/factory/reconciler/arm_test.go
git commit -m "feat(factory): row 3 arms on a maintainer's approval of the head when approveToMerge is on"
```

### Task 3: The approved merge: status, labels, outcome, no Verifying

**Files:**
- Modify: `api/factory/v1alpha1/task_types.go` (`type PullRequestRef struct`)
- Modify: `internal/factory/reconciler/ledger.go` (`ApprovedMergeLabel`)
- Modify: `internal/factory/reconciler/merge.go` (`awaitingCI`'s arm path; `autoMerging`; `revertable`; `paused`)
- Modify: `internal/factory/fmetrics/fmetrics.go` (the `approved_merged` outcome, documented beside `auto_merged`)
- Test: `internal/factory/reconciler/merge_test.go`
- Generated: `config/crd/`, `charts/maku-factory/crds/` through `task crd:gen`

**Interfaces:**
- Produces: `PullRequestRef.MergedHow string` (`class` | `approved`), `PullRequestRef.ApprovedBy string`; `ApprovedMergeLabel = "factory/approved-merge"`; the outcome `approved_merged`.

- [ ] **Step 1: Write the failing test**

Append to `merge_test.go`:

```go
// Human path AM1: an approved merge is the merger's merge of the head a maintainer approved. It is
// outside the caps (no armedAt), labelled factory/merged:<class> and factory/approved-merge, counted
// approved_merged, and Done at once: no Verifying, so main_red never reverts it. A maintainer's
// factory/revert still opens the revert.
func TestAnApprovedMergeIsAHumanMergeTheMergerMade(t *testing.T) {
	g := mergeRig(t, v1alpha1.PhaseAwaitingCI)
	g.r.Cfg.Merge.ApproveToMerge = true
	g.r.Cfg.Classes["docs-links"] = config.Class{} // unarmed: only the approval can merge it
	pr := g.f.PR(12)
	pr.Reviews = []forge.Review{{ID: 1, Author: "Smana", State: "APPROVED", Commit: "abc", At: now}}
	g.f.SetPR(pr)
	g.f.SetChecks(12, green("SUCCESS"))
	got := g.reconcile(t, "3buqdlot", 1)
	if got.Status.Phase != v1alpha1.PhaseAutoMerging || got.Status.PullRequest.MergedHow != "approved" ||
		got.Status.PullRequest.ApprovedBy != "Smana" || got.Status.PullRequest.ArmedAt != nil {
		t.Fatalf("%s %+v", got.Status.Phase, got.Status.PullRequest)
	}
	if m := g.f.Merged(12); m != "abc" {
		t.Fatalf("merged at %q, want the approved head", m)
	}
	pr = g.f.PR(12)
	pr.State, pr.MergedBy, pr.MergedAt = "MERGED", "ogenki-agent-merger[bot]", now
	g.f.SetPR(pr)
	got = g.reconcile(t, "3buqdlot", 1)
	if got.Status.Phase != v1alpha1.PhaseDone || got.Status.Reason != "merged" || got.Status.PullRequest.AutoMerged {
		t.Fatalf("%s %s autoMerged=%v", got.Status.Phase, got.Status.Reason, got.Status.PullRequest.AutoMerged)
	}
	labels := g.f.Labels(12)
	if !slices.Contains(labels, MergedLabel("docs-links")) || !slices.Contains(labels, ApprovedMergeLabel) || slices.Contains(labels, AutoMergedLabel("docs-links")) {
		t.Fatalf("labels %v", labels)
	}
	if n := g.m.Outcomes("docs-links", "approved_merged"); n != 1 {
		t.Fatalf("approved_merged %d", n)
	}
}
```

`g.f.PR`, `g.f.Merged`, `g.f.Labels` and `g.m.Outcomes` are the rig's readers; if a name differs
in `forgetest/fake.go` or the metrics fake, use the existing reader (`TestArmMergeVerifyDone` and
`TestAnAutoMergeIsLabelledWithItsClass` show them).

- [ ] **Step 2: Run it to see it fail**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/reconciler/ -run TestAnApprovedMergeIsAHumanMergeTheMergerMade -count=1 -p 1`
Expected: FAIL at compile (`MergedHow undefined`).

- [ ] **Step 3: The status fields and the label**

In `task_types.go`'s `PullRequestRef`, after `AutoMerged`:

```go
	// MergedHow says who judged the merge the merger made (human path AM1): "class", the class's
	// own conditions (AutoMerged), or "approved", a maintainer's approval of the head, named in
	// ApprovedBy. Empty for a merge the merger did not make.
	// +kubebuilder:validation:Enum=class;approved
	MergedHow  string `json:"mergedHow,omitempty"`
	ApprovedBy string `json:"approvedBy,omitempty"`
```

In `ledger.go`, after `MergedLabel`:

```go
// ApprovedMergeLabel marks a merge the merger made on a maintainer's approval (human path AM1),
// beside MergedLabel: a human merge in the breaker's window, outside the daily caps.
const ApprovedMergeLabel = "factory/approved-merge"
```

Run `task crd:gen` and commit what it writes.

- [ ] **Step 4: The arm path**

In `awaitingCI`, after a successful `Merge`:

```go
	armed := metav1.NewTime(r.Now())
	ref := t.Status.PullRequest
	ref.HeadSHA, ref.DecidedHeadSHA = pr.HeadSHA, pr.HeadSHA
	if d.Reason == "maintainer_approved" {
		// AM1: a human judged it. Outside the caps (no ArmedAt), Done once merged, never reverted
		// on main_red; the approval is the record.
		ref.MergedHow, ref.ApprovedBy = "approved", d.Approver
		r.to(t, v1alpha1.PhaseAutoMerging, "")
		narrateOn(t, pr.Number, narrate.ArmedByApproval(t, d.Approver))
		return nil
	}
	ref.ArmedAt, ref.MergedHow = &armed, "class"
	r.to(t, v1alpha1.PhaseAutoMerging, "")
	narrateOn(t, pr.Number, narrate.Armed(t))
	return nil
```

`narrate.ArmedByApproval` is Task 5's; until then return `narrate.Armed(t)` for both and let Task
5 switch it.

In `autoMerging`, the `MERGED` case becomes:

```go
	case pr.State == "MERGED":
		now := r.mergedAt(pr)
		ref.MergedBy, ref.MergeCommitSHA, ref.MergedAt = pr.MergedBy, pr.MergeCommitSHA, &now
		merger := forge.SameLogin(pr.MergedBy, r.repo(t).Merge.MergerLogin)
		if merger && ref.MergedHow == "approved" {
			// AM1: the merger's merge on a maintainer's approval is a human merge in the ledger.
			r.label(ctx, pr, MergedLabel(class))
			r.label(ctx, pr, ApprovedMergeLabel)
			record(ctx, func(ctx context.Context) { r.Metrics.PROutcome(ctx, class, "approved_merged") })
			return r.end(ctx, t, v1alpha1.PhaseDone, "merged")
		}
		if merger {
			r.label(ctx, pr, AutoMergedLabel(class))
		}
		ref.AutoMerged = merger // AutoMerged: merged by the merger App on the class's conditions (R52)
		if !ref.AutoMerged {
			record(ctx, func(ctx context.Context) { r.Metrics.PROutcome(ctx, class, "human_merged") })
			return r.end(ctx, t, v1alpha1.PhaseDone, "merged")
		}
		record(ctx, func(ctx context.Context) { r.Metrics.PROutcome(ctx, class, "auto_merged") })
		r.to(t, v1alpha1.PhaseVerifying, "")
```

In `revertable`, replace `ref.AutoMerged` with `(ref.AutoMerged || ref.MergedHow == "approved")`,
and in `revert`, label `AutoMergedLabel` only when `ref.AutoMerged` (an approved merge keeps its
two labels). In `paused`, the Task view's `Auto: ref.ArmedAt != nil` already reads an approved
merge as a human one. Add `approved_merged` to the outcomes list in `fmetrics.go`'s doc comment
for `prOutcomes` and to `docs/operations.md`'s metrics table.

- [ ] **Step 5: Run the tests**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/... -count=1 -p 1`
Expected: PASS, `TestArmMergeVerifyDone` and `TestMainRedRevertsAndPausesTheClass` included (the
class path is unchanged). Then `task crd:check && task chart:check`: pass.

- [ ] **Step 6: Commit**

```bash
git add api config charts internal/factory/reconciler/ledger.go internal/factory/reconciler/merge.go internal/factory/reconciler/merge_test.go internal/factory/fmetrics/fmetrics.go docs/operations.md
git commit -m "feat(factory): an approved merge is outside the caps, labelled, Done without Verifying"
```

### Task 4: Returns on an approval, on the next day and when the pause lifts (AM2, AM5)

**Files:**
- Modify: `internal/factory/reconciler/merge.go` (`reenter`)
- Test: `internal/factory/reconciler/merge_test.go`

**Interfaces:**
- Produces: the status reasons `reentered_approved`, `reentered_day_turned`, `reentered_unpaused` (each a `backToGate` reason); `byHandReasons`.

- [ ] **Step 1: Write the failing tests**

```go
// Human path AM2: a maintainer's approval of the hand-off head returns an agent task to the gate
// from any hand-off a human's judgement covers, once per review and uncounted; the eight by-hand
// reasons never return on it.
func TestAnApprovalReturnsATaskToTheGate(t *testing.T) {
	for _, tc := range []struct {
		reason string
		back   bool
	}{
		{"class_unarmed", true}, {"patch_too_large", true}, {"no_approving_verdict", true}, {"maintainer_approved", true},
		{"policy_pending", true}, {"gate_path", false}, {"not_mergeable", false}, {"steering_path", false}, {"foreign_trailer", false},
	} {
		t.Run(tc.reason, func(t *testing.T) {
			g := mergeRig(t, v1alpha1.PhaseAwaitingHuman)
			g.r.Cfg.Merge.ApproveToMerge = true
			var tk v1alpha1.Task
			_ = g.c.Get(t.Context(), types.NamespacedName{Namespace: g.r.Namespace, Name: "3buqdlot"}, &tk)
			tk.Status.Reason, tk.Status.GateReentries = tc.reason, maxGateReentries // the cap never counts an approval
			since := metav1.NewTime(now.Add(-time.Hour))
			tk.Status.PhaseSince = &since
			_ = g.c.Status().Update(t.Context(), &tk)
			pr := g.f.PR(12)
			pr.Reviews = []forge.Review{{ID: 77, Author: "Smana", State: "APPROVED", Commit: "abc", At: now}}
			g.f.SetPR(pr)
			got := g.reconcile(t, "3buqdlot", 1)
			if back := got.Status.Phase == v1alpha1.PhaseAwaitingCI && got.Status.Reason == "reentered_approved"; back != tc.back {
				t.Fatalf("%s: %s %s", tc.reason, got.Status.Phase, got.Status.Reason)
			}
			if tc.back {
				if got.Status.GateReentries != maxGateReentries || !slices.Contains(got.Status.Handled, int64(77)) {
					t.Fatalf("reentries %d handled %v", got.Status.GateReentries, got.Status.Handled)
				}
				got.Status.Phase, got.Status.Reason = v1alpha1.PhaseAwaitingHuman, tc.reason
				_ = g.c.Status().Update(t.Context(), &got)
				if again := g.reconcile(t, "3buqdlot", 1); again.Status.Reason == "reentered_approved" {
					t.Fatal("one review returns once")
				}
			}
		})
	}
}

// Human path AM5: an agent task capped today returns on the next UTC day, and a paused one once
// the pause lifts, both on the same head and counted.
func TestACappedOrPausedTaskReturnsWhenTheBlockerLifts(t *testing.T) {
	g := mergeRig(t, v1alpha1.PhaseAwaitingHuman)
	var tk v1alpha1.Task
	_ = g.c.Get(t.Context(), types.NamespacedName{Namespace: g.r.Namespace, Name: "3buqdlot"}, &tk)
	tk.Status.Reason = "auto_merge_cap"
	since := metav1.NewTime(now.Add(-time.Hour))
	tk.Status.PhaseSince = &since
	_ = g.c.Status().Update(t.Context(), &tk)
	if got := g.reconcile(t, "3buqdlot", 1); got.Status.Reason != "auto_merge_cap" {
		t.Fatalf("same day: %s", got.Status.Reason)
	}
	g.r.Now = func() time.Time { return now.Add(26 * time.Hour) }
	got := g.reconcile(t, "3buqdlot", 1)
	if got.Status.Phase != v1alpha1.PhaseAwaitingCI || got.Status.Reason != "reentered_day_turned" || got.Status.GateReentries != 1 {
		t.Fatalf("%s %s %d", got.Status.Phase, got.Status.Reason, got.Status.GateReentries)
	}
}
```

`g.r.Now` is the rig's clock; if the rig exposes it under another name (`g.clock`), use that.

- [ ] **Step 2: Run them to see them fail**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/reconciler/ -run 'TestAnApprovalReturnsATaskToTheGate|TestACappedOrPausedTaskReturnsWhenTheBlockerLifts' -count=1 -p 1`
Expected: FAIL (the task stays `AwaitingHuman` with its reason).

- [ ] **Step 3: The returns**

In `merge.go`, before `reenter`:

```go
// byHandReasons are the hand-offs a human fixes on the pull request itself, which no approval
// returns to the gate (human path AM2): the gate would refuse them again, or GitHub would.
var byHandReasons = map[string]bool{"not_agent_authored": true, "gate_path": true, "contract_modified": true, "not_owned": true,
	"steering_path": true, "foreign_trailer": true, "not_mergeable": true, "changes_requested": true}

// approvalReturn is AM2's return: a maintainer's APPROVED review of the hand-off head, submitted
// after the hand-off and not yet handled, on a repository with approveToMerge. Once per review,
// uncounted against maxGateReentries: a human act is not a flap.
func (r *Reconciler) approvalReturn(t *v1alpha1.Task, pr forge.PR) bool {
	rc := r.repo(t)
	if !rc.Merge.ApproveToMerge || byHandReasons[t.Status.Reason] || pr.HeadSHA == "" || pr.HeadSHA != t.Status.PullRequest.HeadSHA ||
		t.Status.PhaseSince == nil {
		return false
	}
	for _, rv := range pr.Reviews {
		if rv.State == "APPROVED" && rc.IsMaintainer(rv.Author) && rv.Commit == pr.HeadSHA &&
			rv.At.After(t.Status.PhaseSince.Time.Add(-retrySkew)) && !slices.Contains(t.Status.Handled, rv.ID) {
			markHandled(t, rv.ID)
			t.Status.GateReentries-- // backToGate counts one; an approval is uncounted
			r.backToGate(t, t.Status.Reason, "reentered_approved", pr.HeadSHA)
			return true
		}
	}
	return false
}
```

At the top of `reenter`'s agents branch (after the adopted `if`), add:

```go
	if r.approvalReturn(t, pr) {
		return true, nil
	}
	switch why {
	case "policy_pending", "policy_absent", "head_unreported", "ci_cancelled", "auto_merge_cap", "class_paused":
	default:
		return false, nil
	}
```

and, after the `head_unreported` block, before the checks read:

```go
	switch why {
	case "auto_merge_cap": // AM5: the day turned
		if sameUTCDay(t.Status.PhaseSince.Time, r.Now()) {
			return false, nil
		}
		r.backToGate(t, why, "reentered_day_turned", pr.HeadSHA)
		return true, nil
	case "class_paused": // AM5: the pause lifted
		paused, err := r.paused(ctx, r.repo(t), t.Spec.PredictedClass)
		if err != nil || paused {
			return false, err
		}
		r.backToGate(t, why, "reentered_unpaused", pr.HeadSHA)
		return true, nil
	}
```

The `GateReentries--` before `backToGate` keeps `backToGate` the one place that counts; guard it
with `if t.Status.GateReentries > 0` is wrong (it would count the first approval), so decrement
unconditionally: `backToGate` increments right after.

- [ ] **Step 4: Run the tests**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/reconciler/ -count=1 -p 1`
Expected: PASS, `TestASubstantiveHandOffStaysWithTheHuman` and `TestAFlappingPolicyCannotLoop`
included (they run with the switch off).

- [ ] **Step 5: Commit**

```bash
git add internal/factory/reconciler/merge.go internal/factory/reconciler/merge_test.go
git commit -m "feat(factory): an approval, the next day and a lifted pause return a task to the gate"
```

### Task 5: Narration and docs: the one action (AM3)

**Files:**
- Modify: `internal/factory/narrate/narrate.go` (`WaitingForHuman`, new `WaitingForApproval`, `ArmedByApproval`, the `reasons()` table)
- Modify: `internal/factory/reconciler/merge.go` (the `human` case and the arm path pick the variant)
- Modify: `docs/factory.md` ("When the factory waits for you", "The merge gate"), `docs/operations.md`
- Test: `internal/factory/narrate/narrate_test.go`

- [ ] **Step 1: Write the failing test**

```go
// Human path AM3: with approveToMerge, the hand-off names the one action; the by-hand reasons keep
// the bypass instructions; an approved merge says who approved.
func TestTheHandOffNamesTheOneAction(t *testing.T) {
	tk := &v1alpha1.Task{ObjectMeta: metav1.ObjectMeta{Name: "3buqdlot"}, Spec: v1alpha1.TaskSpec{Repository: "Smana/x"},
		Status: v1alpha1.TaskStatus{PullRequest: &v1alpha1.PullRequestRef{Number: 12}}}
	if got := WaitingForApproval(tk, "class_unarmed").Body; !strings.Contains(got, "To merge: approve this pull request") || strings.Contains(got, "--admin") {
		t.Fatalf("%q", got)
	}
	if got := WaitingForHuman(tk, "gate_path").Body; !strings.Contains(got, "--admin") {
		t.Fatalf("%q", got)
	}
	if got := ArmedByApproval(tk, "Smana").Body; !strings.Contains(got, "@Smana approved") {
		t.Fatalf("%q", got)
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/factory/narrate/ -run TestTheHandOffNamesTheOneAction -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The events**

```go
// WaitingForApproval is WaitingForHuman on a repository with approveToMerge (human path AM3): the
// one action is a review, and the merger does the merge. The by-hand reasons keep WaitingForHuman.
func WaitingForApproval(t *v1alpha1.Task, reason string) Event {
	body := fmt.Sprintf("Agent factory task `%s` waits for a maintainer's review: %s.", t.Name, Reason(reason))
	if pr := t.Status.PullRequest; pr != nil && pr.Number > 0 {
		body += "\n\nTo merge: approve this pull request (a GitHub review by a maintainer). The merger merges the approved head within a minute, or says why not."
	}
	return Event{Key: "human-" + reason + "-" + fmt.Sprint(len(t.Status.Runs)), Body: body}
}

// ArmedByApproval is Armed for a merge a maintainer's approval decided (AM1).
func ArmedByApproval(t *v1alpha1.Task, login string) Event {
	return Event{Key: "armed-" + fmt.Sprint(len(t.Status.Runs)), Body: fmt.Sprintf("Agent factory task `%s`: CI is green, policy-bot "+
		"passed and @%s approved this head, so it is merged now, at the approved head: GitHub re-checks that head at merge time and refuses "+
		"a moved one. It counts as a human merge: no automatic revert, the monitor watches it.", t.Name, login)}
}
```

In `reasons()`, change `maintainer_approved` to `"a maintainer approved it"` and add
`"approval_stale": "a maintainer's approval is of an older head: approve the current one"`,
`"reentered_approved": "a maintainer approved the head it was handed off at, so the gate decides it again"`,
`"reentered_day_turned": "the UTC day turned, so the cap is counted again"`,
`"reentered_unpaused": "the class's pause lifted, so the gate decides it again"`.

In `merge.go`'s `human` case, replace `narrateLater(t, narrate.WaitingForHuman(t, d.Reason))` with:

```go
		ev := narrate.WaitingForHuman(t, d.Reason)
		if r.repo(t).Merge.ApproveToMerge && !adopted && !byHandReasons[d.Reason] {
			ev = narrate.WaitingForApproval(t, d.Reason)
		}
		narrateLater(t, ev)
```

and in the arm path, `narrate.ArmedByApproval(t, d.Approver)` for the approved branch, where Task
3 left `narrate.Armed(t)` as the stand-in.

- [ ] **Step 4: Docs**

In `docs/factory.md`, "The merge gate": a paragraph "Approve-to-merge" after the row list,
quoting AM1 and the switch; in "When the factory waits for you", the AwaitingHuman preamble gains
"With `merge.approveToMerge`, a maintainer's approval of the current head is the merge: the merger
merges it, outside the caps, as a human merge", and the rows `approval_stale`, the three
`reentered_*` (under AwaitingCI) and the changed `maintainer_approved` text. In "The config file",
`approveToMerge` under `merge`. In `docs/operations.md`, the outcome `approved_merged` and the
labels `factory/approved-merge`.

- [ ] **Step 5: Run the tests, lint, check**

Run: `go test ./internal/factory/narrate/ -count=1 && task lint && KUBEBUILDER_ASSETS=… task check`
Expected: PASS, 0 issues, exit 0.

- [ ] **Step 6: Commit, push, open PR 1**

```bash
git add internal/factory/narrate internal/factory/reconciler/merge.go docs/factory.md docs/operations.md
git commit -m "feat(factory): the hand-off names the one action; approved merges say who approved"
git fetch origin && git rebase origin/main && git push -u origin feat/approve-to-merge
gh pr create --title "feat(factory): approve-to-merge, a maintainer's approval merges an agent pull request" --body "<the design's AM1–AM3, AM5; the evidence: task check exit 0, task lint 0, crd:check, chart:check>"
```

---

## PR 2 — `feat/breaker-evidence`: shadow before the blockers, drills, recovery (AM4, AM6, AM7)

### Task 6: The blockers after the shadow split (AM4)

**Files:**
- Modify: `internal/factory/reconciler/arm.go` (`DecideArm`'s tail; `ArmDecision.Paused`, `Capped`)
- Modify: `internal/factory/narrate/narrate.go` (`WouldArm`, `WouldArmAdopted` take the blockers)
- Modify: `internal/factory/reconciler/merge.go` (the `shadow` case passes them)
- Modify: `scripts/shadow-merge-tally.sh` (the marker regex no longer anchors ` -->` after `head=`)
- Test: `internal/factory/reconciler/arm_test.go`, `internal/factory/narrate/narrate_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// Human path AM4: a shadow class arms nothing, so the breaker and the caps block nothing: it
// records shadow_would_arm and the decision says what a live class would have met.
func TestAShadowDecisionIgnoresThePauseAndTheCaps(t *testing.T) {
	cfg := armCfg()
	cfg.Classes["docs-links"] = config.Class{Shadow: true}
	cfg.Merge.AutoMergesPerDay = 1
	d := DecideArm(ArmInputs{PR: agentPR(), Checks: green("SUCCESS"), Task: armTask("docs-links", "solo", ""), Cfg: cfg,
		ReportedHead: head, Paused: true, ArmedToday: 1, Files: changed("[a](https://x/old)", "[a](https://x/new)"), DiffRead: true})
	if d.Verdict != "shadow" || d.Reason != "shadow_would_arm" || !d.Paused || !d.Capped {
		t.Fatalf("%+v", d)
	}
	cfg.Classes["docs-links"] = config.Class{Live: true}
	if d := DecideArm(ArmInputs{PR: agentPR(), Checks: green("SUCCESS"), Task: armTask("docs-links", "solo", ""), Cfg: cfg,
		ReportedHead: head, Paused: true, Files: changed("[a](https://x/old)", "[a](https://x/new)"), DiffRead: true}); d.Reason != "class_paused" {
		t.Fatalf("a live class is paused: %+v", d)
	}
}
```

and in `narrate_test.go`:

```go
func TestTheWouldArmMarkerSaysWhatBlocked(t *testing.T) {
	tk := &v1alpha1.Task{ObjectMeta: metav1.ObjectMeta{Name: "3buqdlot"}}
	if k := WouldArm(tk, "docs-links", "abc", true, false).Key; k != "would-arm-0 head=abc paused=true capped=false" {
		t.Fatalf("%q", k)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler/ ./internal/factory/narrate/ -run 'TestAShadowDecisionIgnoresThePauseAndTheCaps|TestTheWouldArmMarkerSaysWhatBlocked' -count=1`
Expected: FAIL (`class_paused` for the shadow class; a compile error in narrate).

- [ ] **Step 3: The order and the marker**

`DecideArm`'s tail becomes:

```go
	paused, capped := in.Paused, in.ArmedToday >= rc.Merge.AutoMergesPerDay || (cl.MaxPerDay > 0 && in.ClassArmedToday >= cl.MaxPerDay)
	if !cl.Live { // R32, AM4: every condition holds; the gate is in shadow, which nothing blocks
		return ArmDecision{Verdict: "shadow", Reason: "shadow_would_arm", Matched: class, Paused: paused, Capped: capped}
	}
	if paused {
		return human("class_paused", class)
	}
	if capped {
		return human("auto_merge_cap", class)
	}
	return ArmDecision{Verdict: "arm", Matched: class}
```

with `Paused, Capped bool` on `ArmDecision` (`// Paused and Capped say what a shadow decision would
have met as a live one (AM4).`). `WouldArm(t, class, head string, paused, capped bool)` keys
`fmt.Sprintf("would-arm-%d head=%s paused=%t capped=%t", …)`; `WouldArmAdopted` the same; the
`shadow` case in `awaitingCI` passes `d.Paused, d.Capped`. In the tally, change both
`head=(?<h>[0-9a-f]+) -->` captures to `head=(?<h>[0-9a-f]+)` and the `test(…)` filters to
`event=would-arm-[0-9]+ head=[0-9a-f]+`.

- [ ] **Step 4: Run the tests**

Run: `go test ./internal/factory/... -count=1 -p 1` (with `KUBEBUILDER_ASSETS`)
Expected: PASS, `TestShadowNarratesAndNeverArms` and `TestTheShadowRecordCarriesItsHead` included
(update their expected keys to the new marker).

- [ ] **Step 5: Commit**

```bash
git add internal/factory/reconciler/arm.go internal/factory/reconciler/arm_test.go internal/factory/reconciler/merge.go internal/factory/narrate scripts/shadow-merge-tally.sh
git commit -m "feat(factory): a shadow decision ignores the pause and the caps, and says what it met"
```

### Task 7: `factory/drill` (AM6)

**Files:**
- Modify: `internal/factory/forge/forge.go` (`LabelledPull.Labels`), `github.go` (the `PullsWithLabel` query fetches `labels(first: 30)`)
- Modify: `api/factory/v1alpha1/task_types.go` (`AnnotationDrill`, `PullRequestRef.Drill`)
- Modify: `internal/factory/intake/issues.go` (beside `factory/revert`, around the `IsMaintainer(actor)` check at line ~558: read `factory/drill` the same way)
- Modify: `internal/factory/reconciler/ledger.go` (`DrillLabel`; reverts without drills), `merge.go` (`revert` copies the label and sets `Drill`; `paused` reads it)
- Modify: `scripts/shadow-merge-tally.sh` (`--outcomes`: a revert PR labelled `factory/drill` is `drill`, not `reverted`)
- Test: `internal/factory/reconciler/ledger_test.go`, `merge_test.go`, `internal/factory/intake/issues_test.go`

**Interfaces:**
- Produces: `DrillLabel = "factory/drill"`, `v1alpha1.AnnotationDrill = "agents.ogenki.io/drill"`, `PullRequestRef.Drill bool`, `forge.LabelledPull.Labels []string`.

- [ ] **Step 1: Write the failing tests**

In `ledger_test.go`:

```go
// Human path AM6: a revert PR carrying factory/drill does not count as a revert of what it
// reverts, on GitHub's side (a rebuild) as on the Task's.
func TestADrillRevertDoesNotTripTheBreaker(t *testing.T) {
	g := mergeRig(t, v1alpha1.PhaseAwaitingCI)
	g.f.SetChecks(12, green("SUCCESS"))
	g.f.SetPR(forge.PR{Number: 9, State: "MERGED", MergedBy: "ogenki-agent-merger[bot]", MergedAt: now.Add(-48 * time.Hour),
		Labels: []string{AutoMergedLabel("docs-links")}})
	g.f.SetPR(forge.PR{Number: 30, State: "MERGED", MergedAt: now.Add(-47 * time.Hour), Labels: []string{RevertOfLabel(9), DrillLabel}})
	got := g.reconcile(t, "3buqdlot", 1)
	if got.Status.Reason == "class_paused" {
		t.Fatal("a drill revert paused the class")
	}
}
```

In `merge_test.go`, extend `TestAMaintainersRevertAfterDone`: with `AnnotationDrill: "true"` on
the Task, the revert PR the fake records carries `DrillLabel`, `got.Status.PullRequest.Drill` is
true, and a later `paused` read of the class is false. In `issues_test.go`, beside the existing
`factory/revert` test: `factory/drill` by a maintainer sets `AnnotationDrill`; by a non-maintainer
it does not.

- [ ] **Step 2: Run them to see them fail**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/reconciler/ ./internal/factory/intake/ -run 'Drill' -count=1 -p 1`
Expected: FAIL at compile (`DrillLabel undefined`).

- [ ] **Step 3: The label, the read, the ledger**

`ledger.go`:

```go
// DrillLabel marks a pull request a maintainer reverts as a drill (human path AM6): the merger
// copies it to the revert PR, and a revert carrying it is no revert to the breaker. Maintainer-only,
// read as factory/revert is.
const DrillLabel = "factory/drill"
```

`forge.LabelledPull` gains `Labels []string`; `PullsWithLabel`'s query gains
`Labels struct{ Nodes []struct{ Name string } } \`graphql:"labels(first: 30)"\`` and the conversion
copies the names. In `githubLedger`, the revert read becomes:

```go
			// A revert PR counts, as a Task counts from the revert's opening: a rebuild must not
			// change the breaker's verdict. A drill's does not (AM6).
			rv, err := r.merger(ctx).PullsWithLabel(ctx, RevertOfLabel(ms[i].Number))
			if err != nil {
				return nil, fmt.Errorf("read the merge ledger: %w", err)
			}
			ms[i].Reverted = slices.ContainsFunc(rv, func(p forge.LabelledPull) bool { return !slices.Contains(p.Labels, DrillLabel) })
```

`task_types.go`: `AnnotationDrill = "agents.ogenki.io/drill"` beside `AnnotationRevert`, and on
`PullRequestRef`: `// Drill: the revert was a maintainer's drill (AM6); the breaker does not count it.`
`Drill bool \`json:"drill,omitempty"\``. Run `task crd:gen`.

`intake/issues.go`: where the poller sets `AnnotationRevert` after `IsMaintainer(actor)`, read
`factory/drill` on the same pull request with the same `Generation(evs, IsMaintainer)` read and set
`AnnotationDrill: "true"` when its newest label event is a maintainer's.

`merge.go` `revert`: after `RevertPR` succeeds:

```go
	ref.RevertNumber = rv.Number
	if why == "revert_requested" && t.Annotations[v1alpha1.AnnotationDrill] == "true" { // AM6: never a main_red
		ref.Drill = true
		if err := r.merger(ctx).AddLabels(ctx, rv.Number, DrillLabel); err != nil {
			r.log().Error("label the drill revert", "pr", rv.Number, "err", err)
		}
	}
```

and in `paused`, `Reverted: o.Status.Phase == v1alpha1.PhaseReverted && !ref.Drill`.

The tally's `$reverted` set, in both jq programs, excludes a revert whose `labels` hold
`factory/drill`, and `--outcomes` prints `drill=<n>` after `regression=`.

- [ ] **Step 4: Run the tests**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/... -count=1 -p 1 && task crd:check && task chart:check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api config charts internal/factory/forge internal/factory/intake internal/factory/reconciler scripts/shadow-merge-tally.sh
git commit -m "feat(factory): factory/drill marks a revert the breaker does not count"
```

### Task 8: Half-open recovery (AM7)

**Files:**
- Modify: `internal/factory/config/config.go` (`Breaker.RecoverAfter`, validated `>= 0`)
- Modify: `internal/factory/reconciler/ledger.go` (`Merge.Mature`; `Demoted`'s recovery rule), `merge.go` (`paused` computes maturity)
- Test: `internal/factory/reconciler/ledger_test.go`

- [ ] **Step 1: Write the failing test**

```go
// Human path AM7: with recoverAfter, a tripped class resumes once its recoverAfter newest merges
// are all newer than the newest bad one, clean and mature; immature ones count neither way, and a
// new bad merge trips it again.
func TestATrippedClassRecoversOnCleanMatureMerges(t *testing.T) {
	b := config.Breaker{Window: 10, MaxReverts: 1, RecoverAfter: 3}
	at := func(i int, reverted, mature bool) Merge {
		return Merge{Number: i + 1, At: now.Add(time.Duration(i) * time.Hour), Reverted: reverted, Mature: mature}
	}
	bad := []Merge{at(0, true, true)}
	if d, _ := Demoted(bad, b); !d {
		t.Fatal("one revert trips")
	}
	two := append(slices.Clone(bad), at(1, false, true), at(2, false, true))
	if d, _ := Demoted(two, b); !d {
		t.Fatal("two clean merges are not three")
	}
	immature := append(slices.Clone(two), at(3, false, false))
	if d, _ := Demoted(immature, b); !d {
		t.Fatal("an immature merge does not count")
	}
	three := append(slices.Clone(two), at(3, false, true))
	if d, _ := Demoted(three, b); d {
		t.Fatal("three clean mature merges after the bad one recover")
	}
	again := append(slices.Clone(three), at(4, true, true))
	if d, _ := Demoted(again, b); !d {
		t.Fatal("a new bad merge trips again")
	}
	if d, _ := Demoted(three, config.Breaker{Window: 10, MaxReverts: 1}); !d {
		t.Fatal("recoverAfter 0 keeps today's rule")
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/factory/reconciler/ -run TestATrippedClassRecoversOnCleanMatureMerges -count=1`
Expected: FAIL at compile (`RecoverAfter`, `Mature`).

- [ ] **Step 3: The rule**

`config.go`:

```go
	// RecoverAfter: a tripped class resumes once this many of its newest merges, all newer than the
	// newest bad one, are clean and mature (human path AM7); 0 keeps the window rule alone.
	RecoverAfter int `json:"recoverAfter,omitempty"`
```

validated `>= 0` beside `Window`'s check. `Merge` gains `// Mature: merged longer ago than the
class's follow-up window (or the revert window without a monitor): its outcome is known.`
`Mature bool`. `Demoted`:

```go
func Demoted(merges []Merge, b config.Breaker) (bool, int) {
	newestFirst(merges)
	reverts, followUps := 0, 0
	for _, m := range merges[:min(len(merges), b.Window)] {
		if m.Reverted {
			reverts++
		}
		if m.FollowUp || m.Regression {
			followUps++
		}
	}
	demoted := reverts >= b.MaxReverts || (b.MaxFollowUps > 0 && followUps >= b.MaxFollowUps)
	if demoted && b.RecoverAfter > 0 && recovered(merges, b.RecoverAfter) {
		return false, reverts
	}
	return demoted, reverts
}

// recovered: the n newest merges are all clean and mature, and no bad merge is among them (AM7).
// An immature merge among the newest n is unknown, so not recovered.
func recovered(newestFirst []Merge, n int) bool {
	if len(newestFirst) < n {
		return false
	}
	for _, m := range newestFirst[:n] {
		if m.Reverted || m.FollowUp || m.Regression || !m.Mature {
			return false
		}
	}
	return true
}
```

In `paused`, compute `Mature` on both views: the Task view with
`r.Now().Sub(ref.MergedAt.Time) > maturity(rc, class)` and the GitHub view in `uniteMerges`'s
caller the same way, where:

```go
// maturity is how long after a merge its outcome is known (AM7): the class's follow-up window, or
// the revert window for a class without a monitor.
func maturity(rc *config.Repository, class string) time.Duration {
	if m := rc.Classes[class].Monitor; m != nil && m.FollowUpWindow.Duration > 0 {
		return m.FollowUpWindow.Duration
	}
	return rc.Merge.RevertWindow.Duration
}
```

- [ ] **Step 4: Run the tests**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/... -count=1 -p 1`
Expected: PASS, `TestRevertsAmongTheLastMergesDemoteTheClass` and
`TestAHumanMergeOfADemotedClassRefillsTheWindow` unchanged (they build breakers without
`RecoverAfter`).

- [ ] **Step 5: Commit**

```bash
git add internal/factory/config/config.go internal/factory/reconciler/ledger.go internal/factory/reconciler/ledger_test.go internal/factory/reconciler/merge.go
git commit -m "feat(factory): breaker.recoverAfter, a tripped class resumes on clean mature merges"
```

### Task 9: The paused gauge and the docs; PR 2

**Files:**
- Modify: `internal/factory/fmetrics/fmetrics.go` (`classPaused` gauge, `ClassPaused(ctx, repository, class string, paused bool)`)
- Modify: `internal/factory/reconciler/merge.go` (`paused` records the gauge), `monitor.go` (the poll refreshes it per class)
- Modify: `docs/factory.md` (the breaker, calibration, the drill), `docs/operations.md` (the gauge)
- Test: `internal/factory/fmetrics/fmetrics_test.go`

- [ ] **Step 1: Write the failing test**

Beside the existing exposition tests in `fmetrics_test.go`:

```go
func TestClassPausedIsAGauge(t *testing.T) {
	s, read := testSet(t)
	s.ClassPaused(t.Context(), "Smana/cloud-native-ref", "docs-links", true)
	if got := read(); !strings.Contains(got, `maku_factory_class_paused{class="docs-links",repository="Smana/cloud-native-ref"} 1`) {
		t.Fatalf("%s", got)
	}
	s.ClassPaused(t.Context(), "Smana/cloud-native-ref", "docs-links", false)
	if got := read(); !strings.Contains(got, `maku_factory_class_paused{class="docs-links",repository="Smana/cloud-native-ref"} 0`) {
		t.Fatalf("%s", got)
	}
}
```

`testSet` is whatever the file's other tests use to build a `Set` and read the exposition; use
that name.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/factory/fmetrics/ -run TestClassPausedIsAGauge -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The gauge**

```go
	s.classPaused, err = meter.Int64Gauge("agent_factory_class_paused",
		metric.WithDescription("1 while the breaker holds the class paused (human path AM9)."))
	check(err)
```

```go
// ClassPaused records the breaker's verdict for a class (AM9), at each decision and each monitor poll.
func (s *Set) ClassPaused(ctx context.Context, repository, class string, paused bool) {
	v := int64(0)
	if paused {
		v = 1
	}
	s.classPaused.Record(ctx, v, metric.WithAttributes(attribute.String("repository", repository), attribute.String("class", class)))
}
```

`paused` records it before returning; `monitor`'s poll calls `paused` for each class with a
switch (`Live || Shadow`) of each repository once per `monitorEvery` and records it, so a class with
no decision still reports.

- [ ] **Step 4: Docs**

`docs/factory.md`, "The merge gate": the breaker paragraph gains `recoverAfter` and the drill
label (quote AM6 and AM7); "Calibration": "a pause no longer stops a shadow class's would-arm
record (AM4): the tally counts through it". "The config file": `breaker.recoverAfter`.
`docs/operations.md`: `maku_factory_class_paused{repository,class}`.

- [ ] **Step 5: Run everything, push, open PR 2**

Run: `task lint && KUBEBUILDER_ASSETS=… task check`
Expected: 0 issues, exit 0.

```bash
git add internal/factory/fmetrics internal/factory/reconciler docs
git commit -m "feat(factory): the class_paused gauge; the breaker's docs"
git fetch origin && git rebase origin/main && git push -u origin feat/breaker-evidence
gh pr create --title "feat(factory): shadow before the blockers, drill reverts, half-open recovery" --body "<AM4, AM6, AM7, AM9's gauge; the evidence>"
```

---

## PR 3 — `feat/decision-record`: the record, the human path, the tally (AM8–AM10)

### Task 10: The decision record (AM8)

**Files:**
- Modify: `internal/factory/reconciler/arm.go` (`DecisionRows`, filled by `declared` and `DecideArm`)
- Modify: `internal/factory/reconciler/merge.go` (`awaitingCI` appends the record to the hand-off, would-arm and armed events, and logs it)
- Modify: `internal/factory/narrate/narrate.go` (`Decision(d, head) string` renders the second marker line)
- Test: `internal/factory/reconciler/arm_test.go`, `internal/factory/narrate/narrate_test.go`

**Interfaces:**
- Produces: `ArmDecision.Rows DecisionRows` with `Files, MaxFiles, Lines, MaxLines int; Shape, Holdout, Oracle, Age, Evidence string; Paused, Capped bool; Reviewer string`; the marker line `<!-- agent-factory-decision head=<sha> decision=<verdict>:<reason> files=<n>/<max> lines=<n>/<max> shape=<s> holdout=<s> oracle=<s> age=<s> evidence=<s> paused=<b> capped=<b> reviewer=<m> -->`.

- [ ] **Step 1: Write the failing tests**

```go
// Human path AM8: every decision carries its row vector, so the tally can replay a cap and count
// the refusals a human merged unchanged.
func TestADecisionCarriesItsRows(t *testing.T) {
	cfg := armCfg()
	cfg.Classes["docs-links"] = config.Class{Shadow: true, MaxPatchFiles: 3, MaxModifiedLines: 20}
	tk := armTask("docs-links", "pair", "approve")
	tk.Status.Runs = append(tk.Status.Runs, v1alpha1.RunRecord{ID: "r3vnwr3v", Role: "reviewer", Verdict: "approve", HeadSHA: head,
		Provenance: v1alpha1.RunProvenance{ServedModels: []string{"glm-5.3"}}})
	d := DecideArm(ArmInputs{PR: agentPR(), Checks: green("SUCCESS"), Task: tk, Cfg: cfg, ReportedHead: head,
		Verifiers: []v1alpha1.RunRecord{tk.Status.Runs[2]}, Stats: []forge.FileStat{{Path: testFile, Additions: 1, Deletions: 1}},
		Files: changed("[a](https://x/old)", "[a](https://x/new)"), DiffRead: true})
	want := DecisionRows{Files: 1, MaxFiles: 3, Lines: 2, MaxLines: 20, Shape: "ok", Holdout: "n/a", Oracle: "n/a", Age: "n/a", Evidence: "ok", Reviewer: "glm-5.3"}
	if d.Rows != want {
		t.Fatalf("%+v\nwant %+v", d.Rows, want)
	}
}
```

The rows type lives in a package of its own, `internal/factory/decision` (Step 3), which
`reconciler` and `narrate` both import; the test above reads `decision.Rows` for `DecisionRows`.
Beside it, `internal/factory/decision/decision_test.go`:

```go
func TestTheMarkerIsOneLine(t *testing.T) {
	got := Marker("abc", "shadow", "shadow_would_arm", Rows{Files: 1, MaxFiles: 3, Lines: 2, MaxLines: 20,
		Shape: "ok", Holdout: "n/a", Oracle: "n/a", Age: "n/a", Evidence: "ok", Reviewer: "glm-5.3"})
	want := "<!-- agent-factory-decision head=abc decision=shadow:shadow_would_arm files=1/3 lines=2/20 shape=ok holdout=n/a oracle=n/a age=n/a evidence=ok paused=false capped=false reviewer=glm-5.3 -->"
	if got != want {
		t.Fatalf("%q\nwant %q", got, want)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/reconciler/ ./internal/factory/decision/ -run 'TestADecisionCarriesItsRows|TestTheDecisionMarker' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The rows**

`internal/factory/decision/decision.go`:

```go
// SPDX-License-Identifier: Apache-2.0

// Package decision is the merge gate's per-decision record (human path AM8): the values each
// declared row read, so a tally can replay a cap and count what the gate refused that a human
// merged unchanged.
package decision

import "fmt"

// Rows are the declared rows' readings. A string row is "ok", "n/a" (the class declares none) or
// the row's refusal reason; Files and Lines are GitHub's counts against the class's caps (0 = none).
type Rows struct {
	Files, MaxFiles, Lines, MaxLines int
	Shape, Holdout, Oracle, Age, Evidence string
	Paused, Capped                        bool
	Reviewer                              string
}

// Marker is the hidden one-line record appended to the decision's comment.
func Marker(head, verdict, reason string, r Rows) string {
	return fmt.Sprintf("<!-- agent-factory-decision head=%s decision=%s:%s files=%d/%d lines=%d/%d shape=%s holdout=%s oracle=%s age=%s evidence=%s paused=%t capped=%t reviewer=%s -->",
		head, verdict, reason, r.Files, r.MaxFiles, r.Lines, r.MaxLines, r.Shape, r.Holdout, r.Oracle, r.Age, r.Evidence, r.Paused, r.Capped, r.Reviewer)
}
```

In `arm.go`, `ArmDecision` gains `Rows decision.Rows`. `declared(cl, in)` becomes
`declared(cl, in) (rows decision.Rows, reason string, wait bool)`: it fills `Files`/`MaxFiles`
from `len(in.Stats)`/`cl.MaxPatchFiles`, `Lines`/`MaxLines` from the stats' additions plus
deletions/`cl.MaxModifiedLines`, and each string row as it evaluates (`"n/a"` when the class
declares none, `"ok"` when it holds, the reason otherwise; `Age` reads `pending` while waiting).
`DecideArm` sets `Rows.Evidence` from `agentEvidence`/`adoptEvidence` (`"ok"` or the reason),
`Rows.Reviewer` from the newest reviewer run's `Provenance.ServedModels` joined with `+` (`"none"`
without one), `Paused`/`Capped` from Task 6, and returns the rows on every decision, refusals
included (a refusal's later rows stay `""`: unread).

In `awaitingCI`, after the metrics record:

```go
	if d.Verdict != "wait" {
		r.log().Info("merge decision", "task.id", t.Name, "head", pr.HeadSHA, "verdict", d.Verdict, "reason", cmp.Or(d.Reason, "armed"), "rows", d.Rows)
	}
```

and each `narrateOn`/`narrateLater` of a `WaitingForHuman`, `WaitingForApproval`, `WouldArm`,
`WouldArmAdopted`, `Armed` or `ArmedByApproval` event appends
`"\n\n" + decision.Marker(pr.HeadSHA, d.Verdict, cmp.Or(d.Reason, "armed"), d.Rows)` to the
event's `Body` through a helper `withRecord(ev narrate.Event, d ArmDecision, head string) narrate.Event`.

- [ ] **Step 4: Run the tests**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/... -count=1 -p 1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/decision internal/factory/reconciler internal/factory/narrate
git commit -m "feat(factory): every merge decision carries its row vector"
```

### Task 11: The human-path metrics (AM9)

**Files:**
- Modify: `internal/factory/fmetrics/fmetrics.go` (`MergeDecision` gains `repository`; `HumanWait` gains `reason`, `class`; new `HandoffToMerge` histogram)
- Modify: `internal/factory/reconciler/reconciler.go` (`waited` takes the Task), `merge.go` (`MergeDecision` call; `HandedOffAt`), `implement.go` (`prEnded` records the histogram), `api/factory/v1alpha1/task_types.go` (`PullRequestRef.HandedOffAt`)
- Test: `internal/factory/fmetrics/fmetrics_test.go`, `internal/factory/reconciler/merge_test.go`

- [ ] **Step 1: Write the failing tests**

In `fmetrics_test.go`, update the `merge_decisions_total` expectation to carry
`repository="Smana/cloud-native-ref"` and the `human_wait_seconds_total` one to carry
`class="docs-links",reason="policy_pending"`, and add:

```go
func TestHandoffToMergeIsAHistogram(t *testing.T) {
	s, read := testSet(t)
	s.HandoffToMerge(t.Context(), "docs-links", "policy_pending", "approved", 10*time.Minute)
	if got := read(); !strings.Contains(got, `maku_factory_handoff_to_merge_seconds_bucket{class="docs-links",how="approved",reason="policy_pending",le="900"} 1`) {
		t.Fatalf("%s", got)
	}
}
```

In `merge_test.go`, extend `TestAnApprovedMergeIsAHumanMergeTheMergerMade`: the task first hands
off `class_unarmed` at `now`, the approval comes at `now + 10 min`, and the metrics fake holds one
`handoff_to_merge` observation with `how=approved`, `reason=class_unarmed`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/factory/fmetrics/ -count=1`
Expected: FAIL (labels missing, method undefined).

- [ ] **Step 3: The series**

```go
	s.handoffToMerge, err = meter.Float64Histogram("agent_factory_handoff_to_merge_seconds",
		metric.WithDescription("From the first hand-off to a human to the merge, by hand-off reason and how it merged (human path AM9)."),
		metric.WithExplicitBucketBoundaries(300, 900, 3600, 14400, 86400, 259200, 604800))
	check(err)
```

```go
// MergeDecision counts one non-wait decision of the gate (v2 D2), by repository too (AM9).
func (s *Set) MergeDecision(ctx context.Context, repository, class, verdict, reason string) { … attribute.String("repository", repository) … }

// HumanWait adds a written exit from AwaitingHuman or Escalated to the payer's waits (SI8), by
// the hand-off's reason and the task's class (AM9).
func (s *Set) HumanWait(ctx context.Context, phase, reason, class string, d time.Duration) { … }

// HandoffToMerge records how long a pull request waited from its first hand-off to its merge (AM9).
func (s *Set) HandoffToMerge(ctx context.Context, class, reason, how string, d time.Duration) {
	if d <= 0 {
		return
	}
	s.handoffToMerge.Record(ctx, d.Seconds(), metric.WithAttributes(attribute.String("class", class), attribute.String("reason", reason), attribute.String("how", how)))
}
```

`waited(ctx, t, before, after)` passes `before.Reason` and `t.Spec.PredictedClass`. `PullRequestRef`
gains `HandedOffAt *metav1.Time` and `HandedOffReason string` (`// HandedOffAt is the first
hand-off to a human and its reason (AM9): the histogram's start.`), set in `awaitingCI`'s `human`
and `shadow` cases when nil; `prEnded` (a human merge) and `autoMerging`'s approved branch record
`HandoffToMerge(class, ref.HandedOffReason, how, mergedAt - HandedOffAt)` when `HandedOffAt` is
set, with `how` `human` or `approved`. Run `task crd:gen`.

- [ ] **Step 4: Run the tests**

Run: `KUBEBUILDER_ASSETS=… go test ./internal/factory/... -count=1 -p 1 && task crd:check && task chart:check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api config charts internal/factory
git commit -m "feat(metrics): decisions by repository, waits by reason and class, hand-off to merge"
```

### Task 12: The tally: replay, strictness, models, drills

**Files:**
- Modify: `scripts/shadow-merge-tally.sh`
- Create: `scripts/shadow-merge-tally_test.sh` (a fake `gh` through `GH=`)

- [ ] **Step 1: Write the failing test**

`scripts/shadow-merge-tally_test.sh`:

```bash
#!/usr/bin/env bash
# The tally against a fake gh (GH=): would-arm counts, drills, --replay and --strictness.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fake="$(mktemp -d)"; trap 'rm -rf "$fake"' EXIT
cat >"$fake/gh" <<'EOF'
#!/usr/bin/env bash
# Answers the two pr list shapes the tally issues: merged PRs by author, and reverts.
case "$*" in
  *"--author"*) cat "$FIXTURE/merged.json" ;;
  *"Revert in:title"*) cat "$FIXTURE/reverts.json" ;;
  *) echo "[]" ;;
esac
EOF
chmod +x "$fake/gh"
export FIXTURE="$here/testdata/tally" GH="$fake/gh"
out=$("$here/shadow-merge-tally.sh" --class docs-links)
grep -q "merged_unchanged=2 changed=1 reverted=0 auto_merged=0 drill=1" <<<"$out" || { echo "$out"; exit 1; }
grep -q "reviewer glm-5.3: merged_unchanged=2" <<<"$out" || { echo "$out"; exit 1; }
out=$("$here/shadow-merge-tally.sh" --class docs-links --replay lines=10)
grep -q "replay lines=10: would_arm=1 would_refuse=2" <<<"$out" || { echo "$out"; exit 1; }
out=$("$here/shadow-merge-tally.sh" --class docs-links --strictness)
grep -q "refused_merged_unchanged=1" <<<"$out" || { echo "$out"; exit 1; }
echo ok
```

with `scripts/testdata/tally/merged.json` holding four merged pull requests: two decided
`shadow:shadow_would_arm` with `lines=12/20` and `lines=4/20` merged at their head (the second
by a human after a `human:patch_too_large` decision at an earlier head? no: keep it simple), one
`shadow:shadow_would_arm` merged at another head (`changed`), and one `human:patch_too_large`
(`lines=30/20`) merged unchanged at its head, each comment carrying the `agent-factory-decision`
marker with `reviewer=glm-5.3`; `reverts.json` holding one revert labelled `factory/revert-of:#1`
and `factory/drill`. The expected counts above follow from that fixture: write it first, then
the numbers.

- [ ] **Step 2: Run it to see it fail**

Run: `bash scripts/shadow-merge-tally_test.sh`
Expected: exit 1 (no `drill=`, no `--replay`).

- [ ] **Step 3: The tally**

Add the options `--replay key=value` (keys `lines`, `files`) and `--strictness` to the parser. In
the would-arm program, read the decision marker beside the would-arm one:
`capture("agent-factory-decision head=(?<h>[0-9a-f]+) decision=(?<v>[a-z]+):(?<r>[a-z_]+) files=(?<f>[0-9]+)/(?<fm>[0-9]+) lines=(?<l>[0-9]+)/(?<lm>[0-9]+)(?<rest>.*)reviewer=(?<m>[^ ]+)")`,
keep the newest per pull request, and:

- print `drill=<n>` in the totals (a revert labelled `factory/drill` is `drill`, not `reverted`);
- print one `reviewer <model>: merged_unchanged=<n> changed=<n>` line per model;
- with `--replay lines=N`: `replay lines=N: would_arm=<decisions whose lines <= N and verdict was shadow or arm, or whose only refusal was lines> would_refuse=<the rest>`;
- with `--strictness`: `refused_merged_unchanged=<decisions whose verdict was human with a class-row reason (patch_too_large, file_not_allowed, file_protected, file_added_or_deleted, class_mismatch, holdout_red, oracle_finding_open, oracle_unrequested, release_age_red) whose pull request a human merged at that head>`.

- [ ] **Step 4: Run the test, then shellcheck**

Run: `bash scripts/shadow-merge-tally_test.sh && shellcheck scripts/shadow-merge-tally.sh scripts/shadow-merge-tally_test.sh`
Expected: `ok`, no findings. Add the test to `taskfile.yaml`'s `check` beside the other script tests.

- [ ] **Step 5: Commit**

```bash
git add scripts taskfile.yaml
git commit -m "feat(tally): drills, per-model counts, --replay and --strictness"
```

### Task 13: Docs, the release

**Files:**
- Modify: `docs/factory.md` ("The merge gate": the record; "Calibration": `--replay`, `--strictness`, per model, AM10's rule), `docs/operations.md` (the series' labels, the histogram)

- [ ] **Step 1: Docs**

"Calibration" gains: "The record (AM8) makes two more counts possible: `--replay lines=40` says how
many recorded decisions would arm under another cap, and `--strictness` counts the decisions a
class row refused that a human then merged unchanged, the gate's too-strict side. The tally prints
its counts per reviewer model: a change of a live class's reviewer model is a config change
reviewed as a class switch is (AM10), and starts a new count."

- [ ] **Step 2: Run everything, push, open PR 3**

Run: `task lint && KUBEBUILDER_ASSETS=… task check`
Expected: 0 issues, exit 0.

```bash
git add docs
git commit -m "docs(factory): the decision record, the replay and the per-model counts"
git fetch origin && git rebase origin/main && git push -u origin feat/decision-record
gh pr create --title "feat(factory): the decision record, the human-path metrics, the tally's replay" --body "<AM8–AM10; the evidence>"
```

- [ ] **Step 3: Release**

After PR 3 merges: tag the next minor (`v0.32.0`, or the next free minor) on `main`, as the
previous releases were (`git tag v0.32.0 && git push origin v0.32.0`; the release workflow builds
the images and the chart). Tell the peer session before the tag if one holds a Maku freeze. The
adopt plan's Task 1 reads the release.

## Self-review

- **Spec coverage.** AM1 Tasks 2–3; AM2 Task 4; AM3 Task 5; AM4 Task 6; AM5 Task 4; AM6 Task 7;
  AM7 Task 8; AM8 Task 10; AM9 Tasks 9 and 11; AM10 Tasks 12–13. "Configuration, labels and
  status fields": `approveToMerge` (Task 2), `recoverAfter` (Task 8), `factory/drill` (Task 7),
  `factory/approved-merge` (Task 3), `mergedHow`, `approvedBy`, `drill` (Tasks 3, 7),
  `reentered_approved`, `approval_stale`, `approved_merged` (Tasks 2–5). "Testing": every row of
  the spec's table has a task.
- **Type consistency.** `ArmDecision{Verdict, Reason, Matched, Approver, Paused, Capped, Rows}`;
  `approval(in, rc) (forge.Review, string)`; `Demoted(merges, b) (bool, int)` unchanged;
  `decision.Rows`, `decision.Marker(head, verdict, reason, rows)`; `MergeDecision(ctx, repository,
  class, verdict, reason)`; `HumanWait(ctx, phase, reason, class, d)`; `HandoffToMerge(ctx, class,
  reason, how, d)`; `ClassPaused(ctx, repository, class, paused)`.
- **Placeholders.** None: every code step shows its code; the rig's reader names are to be taken
  from the existing tests named in each step.
