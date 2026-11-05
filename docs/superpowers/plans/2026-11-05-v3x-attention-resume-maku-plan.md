# v3.x attention and resume — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One `needs/v1` derivation behind every surface, a step that never says admin-merge when an approval
merges, a deterministic resume brief, revision-first scheduling, final dollars that settle, evidence and
actionable failures in the briefs, a measured client-capability report — and the adoption, docs, status and live
proofs for them.

**Architecture:** Nine Maku pull requests, each independently shippable, then three ai-native-ref pull requests
and one live proof. Maku's broker gains one pure derivation in `internal/summary` that the room rows, the room
summary, `/api/needs`, the sponsored and human `needs_list` and the web panel all call; the broker's
`internal/roomview` gains the brief renderer, which is the one place untrusted text is made inert. Maku's
factory gains two admission/settlement behaviours behind their own switches, and the forge gains one read for a
revision brief's evidence. ai-native-ref only pins the release, declares the switches, drops one transition from
the live webhook subscription, documents the surfaces, and holds the live proof and the status record.

**Tech Stack:** Go 1.25 (controller-runtime, envtest), `goldmark` for the renderers' inertness assertions,
TypeScript + `vitest` + `esbuild` for the web panel, Hugo (goldmark) for the site, `task` as the runner on both
sides.

**Spec:** [the conversational developer experience design](../specs/2026-11-05-v3x-conversational-devex-design.md).
This plan implements the spec's read-only and settlement half — `needs/v1` ([§needs](../specs/2026-11-05-v3x-conversational-devex-design.md#needs),
CD10, CD21, CD26, CD28), the resume brief ([§brief](../specs/2026-11-05-v3x-conversational-devex-design.md#brief),
CD11), revision preference (CD22), the final spend (CD23), CI and review evidence and the actionable-failure
fixes (CD12, fast-follow 6), the approve-not-admin step (fast-follow 1), the notification table (CD11) and the
measured clients (fast-follow 4) — plus its own adoption and live proof. It is deliberately independent of the
natural-language planner (`intake_plan`, `plan/v1`, the model call), the Slack proposal message and its
controls, approving a run from Slack, the Slack binding generator and multi-repository work: it **defines the
contracts those plans consume** (`Need`/`PlanVersion`/`webhook.Meaningful`) and never calls a model, adds no
Slack UI, and touches no channel declaration.

**PR order.** PR 1 lands the derivation every later PR reads. PR 2 lands the step correction immediately after
it, because both edit `internal/summary/waiting.go`, `internal/roomview/card.go` and `internal/roomview/overview.go`
— doing it before the needs' consumers, the brief and the evidence exist means one pass over those files
instead of a second rewrite after the brief has begun to quote them.

## Global Constraints

- **Repository and branches.** Maku is at `/tmp/opencode/maku-devex-read` (module `github.com/Smana/maku`) at
  `4685672f0f40973286a121f83ea92dd3428b8120`; every citation below is that commit. ai-native-ref is this
  worktree. One worktree per PR, from a freshly fetched `origin/main`; rebase onto `origin/main` before every
  push. Branch names are in each PR heading.
- **The evidence.** Maku: `task check` exits 0 (`KUBEBUILDER_ASSETS` from `go tool setup-envtest use -p path
  1.36.x`, as `taskfile.yaml`'s `test` target sets it) and `task lint` reports 0 issues; the web tasks run
  through `task ui:test` and `task ui:check` inside `task check`, so a `web/src` change also rebuilds
  `internal/humanapi/ui/dist`. ai-native-ref: `task check` exits 0 — it builds `.composite/`, runs the host's
  `validate-manifests.sh`, this repository's gates, its suites, the link check, the site build, the doc-path
  check (a path naming a host file resolves against `.host/`) and the source check — and `task docs` exits 0.
  Never claim done without that output.
- **Conventions.** Maku `AGENTS.md`: `// SPDX-License-Identifier: Apache-2.0` on every `.go` file; a package
  doc comment in the file's register; every "no" fails towards a human with its own reason; one interface per
  consumer. Commits are conventional, in English, with no trailers. PR descriptions in English.
- **Doc comments are the vocabulary.** Every new exported identifier gets a comment naming the design decision
  it implements (`CD21`, `CD23`, `FA10`) — those names are how a later reader finds the reason.
- **Verbatim from the spec:**
  - CD21: "`needs/v1` is one function. The room-row list, the room summary, the CLI, the MCP tool, the web
    panel and the Slack lines all read it".
  - The kind order: "a deadline ascending (none last), then the kind order above, then the room id —
    deterministic and documented, so two surfaces cannot disagree. No scoring, no routing, no expiry." The
    kinds in that order: `plan_confirmation`, `approval`, `question`, `merge`, `review`, `failed_check`,
    `recovery`, `hold`.
  - CD22: "while any task in the factory is waiting for a slot to run a **revision** (a run that continues a
    task which already has one), a task whose next run is its **first** waits with the reason
    `waiting_revision_first`. Caps still bind".
  - CD23: "A terminal task requeues once at its last run's end plus `endSettle` plus a margin, prices its runs
    again, and posts one `spend_final` fact; the facts key stops bucketing dollars for a terminal task".
  - CD26: "`needs/v1` asks two different questions: may this login merge, review or answer on GitHub (the
    existing access check), and may they close the room (the policy's `Close`)".
  - CD28: "`/api/needs` stays the human-token route for the browser and the CLI"; the sponsored `needs_list`
    has "a closed read-only schema" and "no field that could carry a decision".
  - CD11: "Notifications are meaningful transitions only, and the resume brief is deterministic".
  - Fast-follow 1: "for a task whose class is approve-to-merge, every renderer (card, brief, needs list, Slack
    line) says 'approve the head', and a golden fails if `--admin` appears in a step for such a task".
  - Fast-follow 4: "`maku doctor --client <name>` prints forms, URL mode, roots, prompts and the protocol
    revision it read from `initialize`".
- **Switches land with the code that reads them.** `human.needs.enabled` (default `true`), `caps.preferRevisions`,
  `facts.finalSpend`, `brief.ciEvidence` (defaults `false`). Both config decoders refuse an unknown key, so
  ai-native-ref's declarations only land with the release that reads them (PR 10 pins it).
- **Out of scope, by construction.** No model call anywhere in this plan; no `plan/v1`, no `intake_plan`, no
  Slack message, button, modal or channel declaration; no multi-repository ordering; no `internal/maku/skill/`
  edit (the planner plan owns the skill's rewrite). `PlanVersion` and `webhook.Meaningful` are written here as
  the contracts those plans fill and read.
- **Rebase ownership, file by file.** Five paths are edited by this plan *and* by a sibling plan. Whichever
  lands second rebases and re-runs the count and fixture tests it names:

  | File | This plan | Sibling |
  |---|---|---|
  | `internal/humanapi/mcp.go` (`sponsoredTools`), `internal/humanapi/sponsored_test.go` (both name strings) | PR 3 (adds `needs_list`), PR 4 (adds `room_brief`) | the planner plan adds `intake_plan` to both lists |
  | `internal/factory/config/config.go` (`Config`) | PR 5 (`caps`), PR 6 (`facts`), PR 7 (`brief`) | the planner plan adds `human.intake.plan`; each change is its own section, so the rebase is mechanical |
  | `internal/webhook/events.go` (the closed vocabulary) | PR 8 reads it, changes no type | the approval design adds `room.approval_closed`, taking the list to thirteen |
  | ai-native-ref `infrastructure/gcp-0/room-broker/config.yaml` (`webhooks[slack-app].events`) | PR 10 drops `room.run_started` | the approval design adds `room.approval_closed` to the same list; whoever lands second rebases and re-runs the webhook-egress test |
  | `internal/factory/reconciler/reconciler.go` (the `metrics` interface) | PR 5 (`RevisionDeferred`), PR 6 (`TaskSpendFinal`) | any sibling adding a metric implements it in `fmetrics` in the same PR |

  `internal/summary/waiting.go` is edited by PR 1 and PR 2 only; that is why PR 2 follows PR 1 directly.

## Review Focus

The six inputs and conditions the spec implies but no acceptance row spells out, most likely to bite first.
Each line's test is in the task named after it.

1. **A room's facts cannot be read.** The list must still return the other rooms, and say in one line that a
   room's state was unreadable — without naming a room the caller may not read. (PR 3, Task 1.)
2. **A need's link points at work that moved.** A pull request merged or a room sealed between the fold and
   the render must not leave an item whose action is dead: a sealed room contributes nothing. (PR 1, Task 1.)
3. **`since` is malformed or in the future.** It must be refused with one line naming the format, never read as
   "everything" or as "nothing". (PR 3, Task 1.)
4. **Untrusted text in a heading.** An issue title carrying `]`, `\`, `<`, a table pipe, ANSI or a bidi
   control must not become a link, a heading or a table in the brief. (PR 4, Task 1.)
5. **A neighbour that waits on a cap, not a slot.** A first run must not be starved by revision preference when
   the "waiting revision" is itself stopped by `waiting_active_tasks` or `waiting_review_wip`. (PR 5, Task 1.)
6. **A terminal task with no run.** Nothing to settle, so nothing to requeue and no final fact — a task that
   died before its first claim must not hold a reconcile loop open. (PR 6, Task 2.)

---

## File structure

| File | Responsibility | PR |
|---|---|---|
| `internal/summary/needs.go` (new) | `needs/v1`: the kinds, `Items`, `Ordered`, `Need`'s new fields, `Caller`, `GitHubStanding` | 1 |
| `internal/summary/summary.go` | `View` lists needs from `needs/v1` and takes the caller's GitHub standing; `Approval.At`; the four old clauses go | 1 |
| `internal/summary/waiting.go` | `MergeNeed`/`QuestionNeed` carry the prose, `MergeHow` takes `byApproval`, `human_commit_in_pr`'s sentence | 1, 2 |
| `internal/summary/step.go` | `StepFor`'s `human_commit_in_pr` label | 2 |
| `internal/summary/testdata/needs/cases.json` (new) | One fixture per kind, per caller, shared by every surface's test | 1, 3 |
| `internal/humanapi/rooms.go` | The row's count and first need come from `needs/v1`; the standing is resolved once | 1, 2 |
| `internal/humanapi/summary.go` | `summaryOf` resolves the standing and passes it to `View`, so `room_summary` keeps its merge need | 1 |
| `internal/factory/narrate/narrate.go` | The issue comment's step says approve, or says why admin is the only path | 2 |
| `internal/roomview/card.go`, `overview.go` | `mergeLine`/`needPhrase` read `Need.Approve` only | 1, 2 |
| `internal/humanapi/needs.go` (new) | `GET /api/needs`: the human door, the `since` cursor, the unread line | 3 |
| `internal/humanapi/mcpneeds.go` (new) | `needs_list` on both tool lists, one closed schema each | 3 |
| `internal/humanapi/mcp.go` | `needs_list` in the tool table and in `sponsoredTools` | 3 |
| `internal/config/config.go` | `HumanConfig.Needs`, the decode-side field behind `human.needs.enabled` | 3 |
| `internal/app/broker.go` | Wires `Server.Needs` from the decoded config | 3 |
| `internal/metrics/metrics.go` | `needs_list_total`, `needs_items`, and `MakuName`'s `needs_` case, served as `maku_needs_*` | 3 |
| `internal/roomview/needs.go` (new) | The needs list as text, for the CLI and the tool's `text` | 3 |
| `internal/maku/client.go`, `internal/maku/needs.go` (new), `internal/app/maku.go` | `maku needs [--since] [--room] [--repo]` | 3 |
| `web/src/summary.ts`, `web/src/needs.ts`, `web/src/api.ts`, `web/test/*` | The panel reads `/api/needs?room=` | 1, 3 |
| `internal/roomview/brief.go` (new) | The resume brief: fixed prose, quoted data, one escaper | 4 |
| `internal/humanapi/brief.go` (new) | `GET /api/rooms/{id}/brief` and the `room_brief` tool | 4, 7 |
| `internal/humanapi/mcpprompts.go` | The `resume` prompt; `inbox` becomes one call | 4 |
| `internal/maku/status.go`, `internal/app/maku_views.go` | `maku status`'s brief head | 4 |
| `internal/factory/config/config.go` | `Caps.PreferRevisions`, `Facts.FinalSpend`, `Brief.CIEvidence` | 5, 6, 7 |
| `internal/factory/reconciler/implement.go` | `waiting_revision_first` in `slotFree` | 5 |
| `internal/factory/reconciler/reconciler.go`, `facts.go` | The final requeue, the re-price, the exact final dollars | 6 |
| `internal/factory/meter/meter.go` | `Costs` keeps a run's settled cost past the tick that drops it | 6 |
| `internal/factory/forge/{forge,github,absent}.go`, `forgetest` | `Annotation` and `CheckAnnotations` | 7 |
| `internal/factory/reconciler/text.go` | The revision brief's evidence block, behind `brief.ciEvidence` | 7 |
| `internal/summary/fix.go` (new) | `Cause` and `Fix`: a permission, configuration or egress failure, and its one fix | 7 |
| `internal/webhook/meaningful.go` (new), Maku `docs/slack.md` | The notification table: nine of the thirteen types, and the App's documented count | 8 |
| `internal/maku/capabilities.go` (new), `internal/maku/mcp.go`, `internal/maku/doctor.go` | Measured client capabilities | 9 |
| ai-native-ref `tooling/base/agent-factory/helm-values-configmap.yaml`, `infrastructure/base/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` | The pin, the four switches, and the dropped transition | 10 |
| ai-native-ref `website/content/docs/reference/commands.md`, `use/guide/{when-the-factory-needs-you,terminal-and-coding-agent}.md` | The reader's side | 11 |
| ai-native-ref `website/content/docs/status.md`, `decisions/0061-*.md`, `decisions/_index.md`, `docs/runbooks/agent-factory/results-*.md` | State, the record, and the proof | 12 |

---

## PR 1 — `feat/needs-v1`: one derivation, and the two holes it closes

Closes G4: `summary.View` and `humanapi.needs` stop being two implementations; `split_proposed` and a
non-owner maintainer's merge stop falling through. The merge need's prose is `waiting.go`'s from the start, so
PR 2 corrects one table rather than rebuilding the item.

### Task 1: `needs/v1` in `internal/summary`

**Files:**
- Create: `internal/summary/needs.go`, `internal/summary/needs_test.go`, `internal/summary/testdata/needs/cases.json`
- Modify: `internal/summary/summary.go` (`Approval.At`, `Need`'s fields, `View`), `internal/summary/waiting.go` (`MergeNeed`, `QuestionNeed`, `MergeHow`'s `byApproval` argument)

**Interfaces:**
- Consumes: `envelope.TaskFacts` (`Phase`, `Reason`, `PR`, `Issue`, `MergeByApproval`) and `policy.Subject`.
- Produces: `NeedPlanConfirmation|NeedApproval|NeedQuestion|NeedMerge|NeedReview|NeedFailedCheck|NeedRecovery|NeedHold`
  (the eight kind strings); `NeedsIn`, `Caller`, `GitHubStanding`, `NeedAction`, `NeedSource`; `func Items(in NeedsIn) []Need`;
  `func Ordered(items []Need) []Need`; `func (n Need) Key() string` (`"<room>/<kind>/<id>"`); `Approval.At time.Time`;
  `func MergeNeed(f *envelope.TaskFacts) (Need, bool)`; `func QuestionNeed(f *envelope.TaskFacts) (Need, bool)`;
  `func MergeHow(repo string, n int, byApproval bool) string`; `View(st State, room, url string, sub policy.Subject,
  standing GitHubStanding, after int64, now time.Time) Summary`; `Need`'s new fields `Room, Issue, PR int, Why string,
  At time.Time, Action NeedAction, Source NeedSource`.

- [ ] **Step 1: Write the fixture and the failing table test**

`internal/summary/testdata/needs/cases.json`, one case per kind plus the three the old clauses drop:

```json
{
  "now": "2026-11-04T19:10:00Z",
  "cases": [
    {
      "name": "split_proposed has a plan_confirmation and no pull request",
      "room": "26zfnuxm", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T18:31:00Z",
      "facts": {"phase": "Escalated", "reason": "split_proposed",
                "issue": {"number": 2238, "url": "https://github.com/Smana/ai-native-ref/issues/2238"}},
      "callers": {"owner": {"login": "ann", "canClose": true, "mayWrite": true, "webui": true, "canRelease": true}},
      "want": {"owner": [{"kind": "plan_confirmation", "id": "2238", "action": "comment",
                          "url": "https://github.com/Smana/ai-native-ref/issues/2238",
                          "whatPrefix": "a maintainer comments"}]}
    },
    {
      "name": "a merge for a maintainer who is not the room's owner",
      "room": "3kq7x2ma", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T18:52:00Z",
      "facts": {"phase": "AwaitingHuman",
                "pr": {"number": 2239, "url": "https://github.com/Smana/ai-native-ref/pull/2239"}},
      "callers": {"owner": {"login": "ann", "canClose": true, "mayWrite": true},
                  "maintainer": {"login": "bob", "mayWrite": true},
                  "reader": {"login": "cid", "canClose": true}},
      "want": {"owner": [{"kind": "merge", "id": "2239", "action": "merge", "approve": false,
                          "whatPrefix": "a maintainer with admin on Smana/ai-native-ref merges PR #2239",
                          "url": "https://github.com/Smana/ai-native-ref/pull/2239"}],
               "maintainer": [{"kind": "merge", "id": "2239", "action": "merge", "approve": false,
                               "url": "https://github.com/Smana/ai-native-ref/pull/2239"}],
               "reader": []}
    },
    {
      "name": "an approve-to-merge hand-off says approve, with the flag the renderers read",
      "room": "3kq7x2mb", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T18:55:00Z",
      "facts": {"phase": "AwaitingHuman", "mergeByApproval": true,
                "pr": {"number": 2244, "url": "https://github.com/Smana/ai-native-ref/pull/2244"}},
      "callers": {"maintainer": {"login": "bob", "mayWrite": true}},
      "want": {"maintainer": [{"kind": "merge", "id": "2244", "action": "merge", "approve": true,
                               "whatPrefix": "a maintainer approves PR #2244"}]}
    },
    { "name": "ci_wait_expired is a failed_check", "room": "4h8km2pd", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T19:02:00Z",
      "facts": {"phase": "AwaitingCI", "reason": "ci_wait_expired",
                "pr": {"number": 2240, "url": "https://github.com/Smana/ai-native-ref/pull/2240"}},
      "callers": {"owner": {"login": "ann", "mayWrite": true}},
      "want": {"owner": [{"kind": "failed_check", "id": "ci_wait_expired", "action": "retry"}]} },
    { "name": "a review the caller owes", "room": "5m2nq8rs", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T19:04:00Z",
      "facts": {"phase": "AwaitingHuman", "pr": {"number": 2241, "url": "https://github.com/Smana/ai-native-ref/pull/2241"}},
      "reviewers": ["bob"],
      "callers": {"reviewer": {"login": "bob", "mayWrite": true}, "stranger": {"login": "zed"}},
      "want": {"reviewer": [{"kind": "review", "id": "2241", "action": "review"}], "stranger": []} },
    { "name": "a question for the issue's author", "room": "6p3rq9tv", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T19:05:00Z",
      "facts": {"phase": "Escalated", "reason": "needs_author",
                "issue": {"number": 2242, "url": "https://github.com/Smana/ai-native-ref/issues/2242", "author": "dana"}},
      "callers": {"owner": {"login": "ann", "canClose": true}},
      "want": {"owner": [{"kind": "question", "id": "2242", "action": "answer"}]} },
    { "name": "a recovery decision", "room": "7t4sm3vw", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T19:06:00Z",
      "facts": {"phase": "Escalated", "reason": "budget_reached",
                "issue": {"number": 2243, "url": "https://github.com/Smana/ai-native-ref/issues/2243"}},
      "callers": {"owner": {"login": "ann", "canClose": true}},
      "want": {"owner": [{"kind": "recovery", "id": "budget_reached", "action": "retry"}]} },
    { "name": "a hold the caller could release", "room": "8v5tn4wx", "repository": "Smana/ai-native-ref",
      "factsAt": "2026-11-04T19:07:00Z",
      "facts": {"phase": "Queued", "reason": "waiting_human_driver"},
      "callers": {"driver": {"login": "ann", "canRelease": true}, "reader": {"login": "bob"}},
      "want": {"driver": [{"kind": "hold", "id": "waiting_human_driver", "action": "release"}], "reader": []} },
    { "name": "an approval with a deadline sorts first",
      "room": "9w6vp5xy", "repository": "Smana/ai-native-ref", "factsAt": "2026-11-04T19:08:00Z",
      "facts": {"phase": "Running"},
      "approvals": [{"id": "01JBX3K8", "what": "push --force", "expiresAt": "2026-11-04T19:20:00Z",
                     "at": "2026-11-04T19:00:00Z"}],
      "callers": {"owner": {"login": "ann", "webui": true, "canDecide": true}},
      "want": {"owner": [{"kind": "approval", "id": "01JBX3K8", "action": "decide"}]} },
    { "name": "an escalated reason the factory could act on alone is no need",
      "room": "2a7xq1bz", "repository": "Smana/ai-native-ref", "factsAt": "2026-11-04T19:08:00Z",
      "facts": {"phase": "Done"}, "callers": {"owner": {"login": "ann", "canClose": true, "mayWrite": true}},
      "want": {"owner": []} }
  ]
}
```

`internal/summary/needs_test.go`:

```go
// The fixture is the contract: every surface asserts against these same cases (CD21, offline proof 6).
func TestNeedsCases(t *testing.T) {
	for _, c := range loadNeedsCases(t) { // the file's decoder; see the schema below
		for caller := range c.Callers {
			got := summary.Ordered(summary.Items(c.in(caller)))
			var kinds []string
			for _, n := range got {
				kinds = append(kinds, n.Kind+"/"+n.ID+"/"+n.Action.Kind)
				if n.Action.URL != "" && !allowedURL(n.Action.URL) {
					t.Fatalf("%s/%s: off-allowlist url %q", c.Name, caller, n.Action.URL)
				}
			}
			if !slices.Equal(kinds, c.wantKinds(caller)) {
				t.Fatalf("%s/%s: %v, want %v", c.Name, caller, kinds, c.wantKinds(caller))
			}
			for i, n := range got {
				if p := c.want(i, caller).WhatPrefix; p != "" && !strings.HasPrefix(n.What, p) {
					t.Fatalf("%s/%s: %q does not start with %q", c.Name, caller, n.What, p)
				}
				if want := c.want(i, caller).Approve; n.Approve != want {
					t.Fatalf("%s/%s: approve %v, want %v (CD26, AM3)", c.Name, caller, n.Approve, want)
				}
			}
		}
	}
}

// CD21's kind order is the only ordering: a deadline first, then the kind, then the room (offline proof 6).
func TestNeedsOrder(t *testing.T) {
	in := []summary.Need{
		{Room: "bbbbbbbb", Kind: "hold", ID: "x"},
		{Room: "aaaaaaaa", Kind: "merge", ID: "12"},
		{Room: "cccccccc", Kind: "merge", ID: "13"},
		{Room: "aaaaaaaa", Kind: "approval", ID: "01", Deadline: time.Date(2026, 11, 4, 19, 20, 0, 0, time.UTC)},
	}
	var got []string
	for _, n := range summary.Ordered(in) {
		got = append(got, n.Key())
	}
	want := []string{"aaaaaaaa/approval/01", "aaaaaaaa/merge/12", "cccccccc/merge/13", "bbbbbbbb/hold/x"}
	if !slices.Equal(got, want) {
		t.Fatalf("%v", got)
	}
}
```

The fixture's schema, decoded by the test (write it as the test's own structs):
`{name, room, repository, factsAt, facts (envelope.TaskFacts), reviewers []string, approvals [{id, what, expiresAt,
at}], callers map[string]{login, webui, canClose, canDecide, canRelease, mayWrite, roomScoped}, want
map[string][]{kind, id, action, url?, whatPrefix?, approve?}}`; `c.in(caller)` builds
`NeedsIn{GitHub: GitHubStanding{Login: cu.Login, MayWrite: cu.MayWrite, Reviewers: c.Reviewers}, Caller:
Caller{WebUI: cu.WebUI, CanDecide: cu.CanDecide, CanClose: cu.CanClose, CanRelease: cu.CanRelease, RoomScoped:
cu.RoomScoped}, …}` with `Now` from the file's `now`.

Add the Review Focus 2 test in the same file:

```go
// A sealed room contributes nothing: its last facts outlive the PR it names (Review Focus 2).
func TestASealedRoomHasNoNeeds(t *testing.T) {
	got := summary.Items(summary.NeedsIn{Room: "26zfnuxm", Sealed: true,
		Facts: &envelope.TaskFacts{Phase: "AwaitingHuman", PR: &envelope.PRFact{Number: 9, URL: "https://github.com/Smana/ai-native-ref/pull/9"}},
		GitHub: summary.GitHubStanding{Login: "ann", MayWrite: true}})
	if len(got) != 0 {
		t.Fatalf("%v", got)
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/summary/ -run 'TestNeedsCases|TestNeedsOrder|TestASealedRoomHasNoNeeds' -count=1`
Expected: FAIL at compile (`undefined: summary.Items`, `NeedsIn`, `Ordered`, `Need.Key`, `Sealed`,
`GitHubStanding`).

- [ ] **Step 3: Implement the derivation**

`internal/summary/needs.go` — the types, then one clause per kind. The signatures the rest of the plan uses:

```go
// NeedsIn is one room, as the caller sees it (CD21). Sealed, and facts that cannot be read, contribute nothing.
type NeedsIn struct {
	Room       string
	URL        string         // the room page
	Repository string         // owner/name, for the sentences and the pull request's URL
	Sealed     bool
	FactsRead  bool           // false: the room's state could not be read
	Facts      *envelope.TaskFacts
	FactsAt    time.Time      // the ts of the event that carried Facts
	Approvals  []Approval     // the live approvals the caller may decide, as the fold lists them
	GitHub     GitHubStanding // what only the server can resolve
	Caller     Caller         // what the policy says, and how the caller reads the room
	Now        time.Time
}

// GitHubStanding is the caller's standing where a merge, a review and an answer happen (CD26): their login,
// whether they may write the room's repository, and the pull request's requested reviewers. The server
// resolves it once per room and hands it to every derivation, so the rows, the summary and the tools agree.
type GitHubStanding struct {
	Login     string
	MayWrite  bool
	Reviewers []string
}

// Caller is who asks, from where the action happens: the policy decides an approval, closing a room and
// releasing a hold; GitHub decides the rest (CD26). RoomScoped is a sponsored principal: the App reads a
// room's needs, never a login's, and every item's action is a link it cannot follow for anyone.
type Caller struct {
	WebUI      bool // decides approvals in the browser
	CanDecide  bool // the policy's Decide: an approval item
	CanClose   bool // the policy's Close: a question, a recovery
	CanRelease bool // the policy's StartRun, as summary.Hold asks it: a hold
	RoomScoped bool
}

// Need's action: the one thing to do, and where.
type NeedAction struct {
	Kind  string `json:"kind"`  // decide | comment | answer | merge | review | retry | release
	Label string `json:"label"` // one sentence
	URL   string `json:"url,omitempty"`
}

// NeedSource says where an item was derived from: for the tests, not for the reader.
type NeedSource struct {
	Kind   string `json:"kind"`             // approval | facts | review_request | room
	Seq    int64  `json:"seq,omitempty"`
	Reason string `json:"reason,omitempty"` // the factory's wait reason
}

func Items(in NeedsIn) []Need
func Ordered(items []Need) []Need
func (n Need) Key() string
```

Clauses, each with its comment naming the decision:

```go
// Split a proposed split reaches nobody today: Merge needs a PR and Answer needs needs_author, so the row had
// no need and no step (G4). A plan confirmation has no PR precondition, which is what it needs (needs/v1).
case f.Phase == "Escalated" && f.Reason == "split_proposed":  // -> NeedPlanConfirmation, action comment
// CD26: a merge is GitHub's, not the room's: the maintainer who may merge sees it whoever opened the task.
// The prose is waiting.go's MergeNeed, so Approve and "approve the current commit" come from one table (AM3).
case f.Phase == "AwaitingHuman" && f.PR != nil && (in.GitHub.MayWrite || in.Caller.RoomScoped): // -> MergeNeed
// review: the caller is in the pull request's requested reviewers, and may act there.
case f.PR != nil && slices.ContainsFunc(in.GitHub.Reviewers, func(l string) bool {
	return strings.EqualFold(l, in.GitHub.Login) })
// failed_check: ci_wait_expired, contract_*, release_age_red, verdict_stale -> retry
// recovery: budget_reached, Reverted, resumes exhausted ("resumed", "pod_lost", "disrupted" past Resume.Max)
// hold: summary.Hold's two Queued reasons, for in.Caller.CanRelease (policy.StartRun, as Hold asks it)
// question: f.Phase == "Escalated" && f.Reason == "needs_author" && (in.Caller.CanClose || in.Caller.RoomScoped)
// approval: one item per live, unexpired, still-undecided approval, sorted by id
```

`Ordered` sorts by `(deadline.IsZero(), deadline, kindRank, room)`; `kindRank` is the constants' declared
order. Bounds: `What` ≤ 200 runes (`maxWhat`), `Why` from `reasons()[f.Reason]` and not repeated in `What`;
`Action.URL` built here from the room URL and the facts' validated URLs, never from a note.

In `waiting.go`, split the prose from the standing, and make the bypass decision a parameter:

```go
// MergeNeed is the merge need's prose alone: standing is the derivation's (CD26), the sentence is the gate's.
// When the facts say an approval returns the hand-off, the sentence is ApproveHow's and Need.Approve is set,
// so no renderer can print the bypass for it (AM3, fast-follow 1).
func MergeNeed(f *envelope.TaskFacts) (Need, bool)

// QuestionNeed is the needs_author prose alone (SC8).
func QuestionNeed(f *envelope.TaskFacts) (Need, bool)

// MergeHow is how pull request n is merged under the repository ruleset; byApproval selects the approval's
// sentence. Merge and Answer keep their signatures as standing-checked wrappers over the two prose helpers.
func MergeHow(repo string, n int, byApproval bool) string
```

- [ ] **Step 4: Rewire `View`, `Approval` and the old clauses**

In `summary.go`: `Approval` gains `At time.Time` (the `approval_requested` event's `TS`, set in `State.Add`);
`Need` gains the new fields; `View` gains one parameter — the standing only the server can resolve — and hands
it to the one derivation:

```go
// View is st as sub sees it (CD21): needs-you from the one derivation, which takes the caller's GitHub
// standing because a merge, a review and an answer are GitHub's to decide (CD26).
func View(st State, room, url string, sub policy.Subject, standing GitHubStanding, after int64, now time.Time) Summary {
	…
	s.NeedsYou = Ordered(Items(NeedsIn{Room: room, URL: url, Repository: repoOf(st.Facts),
		FactsRead: true, Facts: st.Facts, FactsAt: st.FactsAt, Approvals: live(st.Pending, now),
		GitHub: standing,
		Caller: Caller{WebUI: web.WebUI, CanDecide: policy.Allowed(web, policy.Decide),
			CanClose: policy.Allowed(sub, policy.Close), CanRelease: policy.Allowed(sub, policy.StartRun)},
		Now: now}))
	…
}
```

`viewStep` keeps reading `NeedsYou`'s kinds (update `"answer"` → `"question"`); `Summary.NeedsYou`'s JSON
unchanged in shape. Every `View` caller in the package's own tests passes a `GitHubStanding`: the merge and
question cases pass `{Login: "ann", MayWrite: true}`, the rest the zero value — which is what a caller with no
GitHub link gets, and is itself a case worth keeping.

- [ ] **Step 5: Run the package's tests**

Run: `go test ./internal/summary/ -count=1`
Expected: PASS, and the existing `summary_test.go` cases for merge/answer/hold still pass (their needs now carry
`Room`, `Action` and `Source`).

- [ ] **Step 6: Rename the need kind `answer` to `question` everywhere it is read**

`internal/summary/summary.go` (`viewStep`), `internal/roomview/card.go` (`answerLine` → reads
`summary.NeedQuestion`), `internal/roomview/overview.go` (`needPhrase`), `web/src/summary.ts` (the `needsYou`
union and `needsItems`). Add to `internal/roomview/card_test.go`:

```go
func TestAQuestionNeedRendersAsTheAnswerLine(t *testing.T) {
	s := summary.Summary{NeedsYou: []summary.Need{{Kind: summary.NeedQuestion, ID: "2242", Author: "dana",
		Action: summary.NeedAction{Kind: "answer", Label: "answer on #2242", URL: "https://github.com/o/r/issues/2242"}}}}
	s.Status.Phase = "Escalated"
	var b strings.Builder
	if err := roomview.Card(&b, s, roomview.Options{Format: roomview.Markdown, Now: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(b.String(), "answers the scoper's question by editing issue #2242") {
		t.Fatalf("%s", b.String())
	}
}
```

In `web/src/summary.ts`, `needsItems`' answer branch becomes `if (n.kind === "question")` with the label
`Answer`; `web/test` gains the same case in the needs panel's existing suite.

- [ ] **Step 7: Run the Go and web suites, then commit**

Run: `go test ./internal/summary/ ./internal/roomview/ -count=1 && cd web && npm run typecheck && npm test`
Expected: PASS.

```bash
git add internal/summary internal/roomview web/src web/test
git commit -m "feat(summary): one needs/v1 derivation, with the split proposal and the merge need it was missing"
```

### Task 2: the rows, `room_summary` and `room_wait` read the same list

**Files:**
- Modify: `internal/humanapi/rooms.go` (`needs`, `firstNeed`, `held`, `answer`, `prNeed`, `rowStep`, `roomRows`),
  `internal/humanapi/summary.go` (`summaryOf`)
- Test: `internal/humanapi/rooms_list_test.go`, `internal/humanapi/summary_test.go`, `internal/maku/roomwait_test.go`

**Interfaces:**
- Consumes: `summary.Items`, `summary.Ordered`, `summary.NeedsIn`, `summary.Caller`, `summary.GitHubStanding`,
  `summary.View` (Task 1).
- Produces: `func (s *Server) standing(ctx context.Context, room *v1alpha1.Room, p authn.Principal) summary.GitHubStanding`
  — the one resolver of `Login`, `MayWrite` and the requested reviewers; `func (s *Server) needsFor(ctx
  context.Context, room *v1alpha1.Room, p authn.Principal, sub policy.Subject) ([]summary.Need, bool)` — the one
  place a room's needs are computed for an HTTP caller; `roomRow.NeedsYou` still an `int`, `roomRow.Need` still
  the first item.

- [ ] **Step 1: Write the failing tests**

In `rooms_list_test.go`, against a `split_proposed` task and a maintainer who is not the owner:

```go
// G4: the split proposal and a second maintainer's merge are in the row list, and appear in room_wait
// (offline proofs 6 and 9).
func TestRowsListTheSplitProposalAndAMaintainersMerge(t *testing.T) {
	w := world(nil)
	w.task("Smana/a", "26zfnuxm", envelope.TaskFacts{Phase: "Escalated", Reason: "split_proposed",
		Issue: &envelope.IssueFact{Number: 2238, URL: "https://github.com/Smana/a/issues/2238"}})
	e := setup(t, roomsOn, w.gate)
	rows := getRows(t, e, "dev") // the file's helper; the caller may write Smana/a, not own the room
	if rows["26zfnuxm"].NeedsYou != 1 || rows["26zfnuxm"].Need == nil || rows["26zfnuxm"].Need.Kind != "plan_confirmation" {
		t.Fatalf("%+v", rows["26zfnuxm"])
	}
}
```

In `summary_test.go`, the door that broke when `View`'s standing was left zero:

```go
// CD26 at the summary's door: room_summary lists the merge need for a maintainer who is not the room's owner,
// because the server resolves the standing and hands it to View (B1).
func TestRoomSummaryKeepsTheMergeNeedForAMaintainer(t *testing.T) {
	w := world(nil)
	w.task("Smana/a", "3kq7x2ma", envelope.TaskFacts{Phase: "AwaitingHuman",
		PR: &envelope.PRFact{Number: 2239, URL: "https://github.com/Smana/a/pull/2239"}})
	e := setup(t, roomsOn, w.gate)
	s := getSummary(t, e, "dev", "3kq7x2ma") // the file's helper, the caller may write Smana/a
	if len(s.NeedsYou) != 1 || s.NeedsYou[0].Kind != "merge" {
		t.Fatalf("%+v", s.NeedsYou)
	}
}
```

In `internal/maku/roomwait_test.go`:

```go
// room_wait's needs_you condition is the same list: a split proposal now ends a wait.
func TestRoomWaitReturnsOnASplitProposal(t *testing.T) {
	r := relay(t, fakeBroker(t, row("26zfnuxm", 0, 0), row("26zfnuxm", 1, 1))) // second poll: needsYou 1
	got := r.roomWait(t.Context(), localCall{args: map[string]any{"rooms": []any{"26zfnuxm"}, "until": []any{"needs_you"}}})
	if !strings.Contains(fmt.Sprint(got), "needs_you") {
		t.Fatalf("%v", got)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestRowsListTheSplitProposal|TestRoomSummaryKeepsTheMergeNeed' -count=1; go test ./internal/maku/ -run TestRoomWaitReturnsOnASplitProposal -count=1`
Expected: FAIL (`NeedsYou` is 0: the row still counts the four old clauses; `getSummary` finds no need).

- [ ] **Step 3: One resolver, one call**

In `rooms.go`, delete `needs`, `firstNeed`, `held`, `answer` and `prNeed`'s need-building half (keep
`prURLOf`), and add:

```go
// standing is the caller's GitHub standing in room's repository (CD26): their login, whether they may write
// it, and the pull request's requested reviewers as the room projects them. The rows, the summary and the
// needs all take it from here, so a merge need cannot exist on one surface and not another (B1).
func (s *Server) standing(ctx context.Context, room *v1alpha1.Room, p authn.Principal) summary.GitHubStanding {
	var gh summary.GitHubStanding
	if t := room.Status.Task; t != nil {
		gh.Reviewers = t.PRReviewers
	}
	if p.Sponsored || s.Identity == nil || room.Spec.Repository == "" {
		return gh // a sponsored principal has no login, and GitHub decides nothing for it
	}
	if login, err := s.Identity.Login(ctx, p.Sub, room.Spec.Repository); err == nil {
		gh.Login = login
	}
	if gh.Login != "" && s.Access != nil {
		gh.MayWrite, _ = s.Access.CanWrite(ctx, room.Spec.Repository, gh.Login)
	}
	return gh
}

// needsFor is the room's needs for this caller, from the one derivation (CD21). read is false when the room's
// facts could not be read: its other needs still stand, and its state is not guessed.
func (s *Server) needsFor(ctx context.Context, room *v1alpha1.Room, p authn.Principal, sub policy.Subject) (items []summary.Need, read bool) {
	facts := s.taskFacts(ctx, room) // one indexed read, already memoised per request
	web := sub
	web.WebUI = true
	live, _ := s.liveApprovals(ctx, room, web)
	in := summary.NeedsIn{Room: room.Name, URL: s.PublicURL + "/r/" + room.Name, Repository: room.Spec.Repository,
		Sealed: room.Status.Phase == "Closed" || room.Status.Phase == "Sealed",
		FactsRead: true, Facts: facts(), FactsAt: s.foldFactsAt(ctx, room), Approvals: live, Now: s.now(),
		GitHub: s.standing(ctx, room, p),
		Caller: summary.Caller{WebUI: web.WebUI, CanDecide: policy.Allowed(web, policy.Decide),
			CanClose: policy.Allowed(sub, policy.Close), CanRelease: policy.Allowed(sub, policy.StartRun),
			RoomScoped: p.Sponsored}}
	return summary.Ordered(summary.Items(in)), facts() != nil
}
```

`s.foldFactsAt` reads the fold's newest facts ts; the fold gains `State.FactsAt time.Time`, set in
`foldState`'s `task` branch. `roomRows` then sets `count = len(items)` and `row = items[0]`; a `needsMe` filter
is `count > 0`. `rowStep` reads the first item's `Action.Kind` instead of re-deriving. In `summary.go`'s
`summaryOf`, resolve once and pass it: `summary.View(st, id, url, sub, s.standing(ctx, room, p), after, now)` —
that is the whole of B1, and it is why `room_summary` and `maku status` keep their merge and review needs.

- [ ] **Step 4: Run the suites**

Run: `go test ./internal/humanapi/ ./internal/maku/ ./internal/summary/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/humanapi internal/maku internal/summary
git commit -m "feat(humanapi): the rows, room_summary and room_wait read needs/v1, from one standing"
```

### Task 3: PR 1

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/needs-v1
gh pr create --title "feat(summary): one needs/v1 derivation behind the rows, the summary and room_wait" \
  --body "CD10, CD21, CD26. The split proposal and a non-owner maintainer's merge stop falling through; the four old clauses are gone, and the standing is resolved once and handed to View. Evidence: task check exit 0, task lint 0."
```

---

## PR 2 — `feat/approve-not-admin`: the next step matches the gate

Fast-follow 1, immediately after PR 1 because both edit `waiting.go`, `card.go` and `overview.go`. PR 1 set
`Need.Approve` from `MergeNeed`; this PR makes every renderer read that flag and nothing else, and gives the one
case where admin merge is truly the only path its sentence.

### Task 1: `MergeHow` from the gate's decision

**Files:**
- Modify: `internal/summary/waiting.go` (`MergeHow`, `nextStep`, `approveNext`), `internal/summary/step.go`
  (`StepFor`), `internal/roomview/card.go` (`mergeLine`), `internal/roomview/overview.go` (`needPhrase`),
  `internal/factory/narrate/narrate.go` (the issue comment's step)
- Test: `internal/summary/waiting_test.go`, `internal/summary/step_test.go`, `internal/roomview/card_test.go`,
  `internal/roomview/overview_test.go`, `internal/factory/narrate/narrate_test.go`

**Interfaces:**
- Consumes: `Need.Approve` and `MergeHow(repo, n, byApproval)` (PR 1).
- Produces: `Need.Approve` as the only switch a renderer reads; `StepFor`'s `human_commit_in_pr` label
  `"a repository admin merges PR #%d: a person pushed a commit the factory cannot vouch for"`; `nextStep`'s
  sentence for the same reason; `narrate`'s issue comment carrying it verbatim.

- [ ] **Step 1: Write the failing goldens**

```go
// Fast-follow 1: an approve-to-merge task never sees --admin, in the card, in a row's cell or in the step.
func TestNoRendererSaysAdminMergeForApproveToMerge(t *testing.T) {
	s := summary.Summary{NeedsYou: []summary.Need{{
		Kind:    summary.NeedMerge,
		ID:      "42",
		Approve: true,
		What:    summary.ApproveHow("Smana/ai-native-ref", 42),
		URL:     "https://github.com/Smana/ai-native-ref/pull/42",
		Action:  summary.NeedAction{Kind: "merge", Label: "review, then approve the current commit", URL: "https://github.com/Smana/ai-native-ref/pull/42"},
	}}}
	s.Status.Phase = "AwaitingHuman"
	var card strings.Builder
	if err := roomview.Card(&card, s, roomview.Options{Format: roomview.Markdown, Now: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(card.String(), "--admin") {
		t.Fatalf("%s", card.String())
	}
	if got := summary.MergeHow("Smana/ai-native-ref", 42, true); strings.Contains(got, "--admin") {
		t.Fatalf("the byApproval sentence is %q", got)
	}
	if got := summary.MergeHow("Smana/ai-native-ref", 42, false); !strings.Contains(got, "--admin") {
		t.Fatalf("the bypass sentence is %q", got)
	}
}

// Where admin merge is the only path, the next step and the step itself say why, in one sentence.
func TestTheHumanCommitStepSaysWhy(t *testing.T) {
	f := &envelope.TaskFacts{Phase: "AwaitingHuman", Reason: "human_commit_in_pr",
		PR: &envelope.PRFact{Number: 42, URL: "https://github.com/o/r/pull/42"}}
	_, next := summary.Waiting(f)
	if !strings.Contains(next, "a person pushed a commit the factory cannot vouch for") {
		t.Fatalf("next: %q", next)
	}
	step := summary.StepFor(summary.StepIn{Phase: "AwaitingHuman", Reason: "human_commit_in_pr", PR: 42,
		PRURL: "https://github.com/o/r/pull/42", CanClose: true})
	if step == nil || !strings.Contains(step.Label, "a repository admin merges PR #42") {
		t.Fatalf("step: %+v", step)
	}
}
```

and in `narrate_test.go`: the comment the factory posts for a `human_commit_in_pr` hand-off holds the same
sentence (it is the text a maintainer reads on GitHub, so a divergence is a real defect).

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/summary/ ./internal/roomview/ ./internal/factory/narrate/ -run 'TestNoRendererSaysAdminMerge|TestTheHumanCommitStepSaysWhy' -count=1`
Expected: FAIL (`MergeHow` takes two arguments; `StepFor`'s label says "review and merge or close").

- [ ] **Step 3: The choice**

`summary.Waiting(f *envelope.TaskFacts) (reason, next string)` becomes the exported spelling of `waiting`;
`nextStep("human_commit_in_pr", …)` returns "a person pushed a commit the factory cannot vouch for, so only a
repository admin can merge it: read that commit, then tick \"bypass rules\" on the PR page, or run
`gh pr merge --admin`". `StepFor` gains, before the two `AwaitingHuman` branches:

```go
	case in.CanClose && in.Phase == "AwaitingHuman" && in.PR > 0 && in.Reason == "human_commit_in_pr":
		return &Step{Kind: StepPR, URL: in.PRURL,
			Label: fmt.Sprintf("a repository admin merges PR #%d: a person pushed a commit the factory cannot vouch for", in.PR)}
```

`card.mergeLine` and `overview.needPhrase` read `n.Approve` only; every `MergeHow` caller passes
`f.MergeByApproval` (or `n.Approve`, which is the same value), so the bypass sentence is unreachable for an
approve-to-merge hand-off in the card, the brief, the needs list and the row. `narrate.go`'s hand-off comment
uses `summary.Waiting`'s next step verbatim rather than its own copy: grep
`git grep -n "MergeHow(" -- internal` for the callers, and let the compiler find the rest.

- [ ] **Step 4: Run the suites**

Run: `go test ./internal/summary/ ./internal/roomview/ ./internal/humanapi/ ./internal/factory/... -count=1 -p 1 && task lint`
Expected: PASS, 0 issues. `internal/factory/narrate`'s reasons test (`summary.Reasons()`) still passes.

- [ ] **Step 5: Commit**

```bash
git add internal/summary internal/roomview internal/humanapi internal/factory/narrate
git commit -m "fix(summary): an approve-to-merge task's step never says --admin"
```

### Task 2: PR 2

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task check`
Expected: exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/approve-not-admin
gh pr create --title "fix(summary): the next step never says admin-merge when an approval merges" \
  --body "Fast-follow 1. Goldens fail if '--admin' appears for an approve-to-merge task, in the card, the row's cell, the step and the issue comment; the human-commit path says why. Evidence: task check exit 0."
```

---

## PR 3 — `feat/needs-ends`: the two front doors, one shape

CD28: `/api/needs` for the human token, a closed read-only `needs_list` on the sponsored `/mcp`, and the CLI
and the panel reading the same items.

### Task 1: `GET /api/needs`

**Files:**
- Create: `internal/humanapi/needs.go`, `internal/humanapi/needs_test.go`
- Modify: `internal/humanapi/server.go` (the route), `internal/humanapi/rooms.go` (the shared scan),
  `internal/config/config.go` (`HumanConfig.Needs`), `internal/app/broker.go` (the wiring), `internal/metrics/metrics.go`
  (the two instruments and `MakuName`'s `needs_` case)
- Test: `internal/humanapi/needs_test.go`, `internal/metrics/metrics_test.go`, `internal/config/config_test.go`

**Interfaces:**
- Consumes: `needsFor` (PR 1, Task 2).
- Produces: `GET /api/needs?since&room&repo` → `{"apiVersion":"needs/v1","items":[summary.Need...],"cursor":"<RFC3339>","access":"ok|unlinked|unverified","unread":["<room>"]}`;
  `config.HumanConfig.Needs config.NeedsConfig` with `Enabled bool` (`human.needs.enabled`, default true);
  `humanapi.Server.Needs bool`, set in `broker.go` beside `MCP: h.MCP.Enabled`;
  `metrics.Set.NeedsList(ctx, surface, principal, outcome)` (`needs_list_total`) and
  `metrics.Set.Needs(kinds map[string]int)` (`needs_items`); `metrics.MakuName`'s `needs_` prefix case.

- [ ] **Step 1: Write the failing tests**

```go
// CD10: the human door lists the caller's needs across rooms, in the one order, with a cursor.
func TestNeedsAcrossRooms(t *testing.T) {
	e := setup(t, roomsOn, worldWithSplitAndMerge(t).gate)
	var got struct {
		APIVersion string         `json:"apiVersion"`
		Items      []summary.Need `json:"items"`
		Cursor     string         `json:"cursor"`
		Unread     []string       `json:"unread"`
	}
	if code := getJSON(t, e, viaRoomctl("dev"), "/api/needs", &got); code != 200 {
		t.Fatalf("%d", code)
	}
	var keys []string
	for _, n := range got.Items {
		keys = append(keys, n.Key())
	}
	if !slices.Equal(keys, []string{"26zfnuxm/plan_confirmation/2238", "3kq7x2ma/merge/2239"}) {
		t.Fatalf("%v", keys)
	}
}

// Review Focus 3: a cursor that is not an RFC 3339 instant is refused, never read as everything or nothing.
func TestNeedsRefusesAMalformedSince(t *testing.T) {
	e := setup(t, roomsOn, worldWithSplitAndMerge(t).gate)
	for _, since := range []string{"yesterday", "2026-11-04 19:10:00", "9999-99-99T00:00:00Z"} {
		code, body := get(t, e, viaRoomctl("dev"), "/api/needs?since="+url.QueryEscape(since))
		if code != 400 || !strings.Contains(body, "since is an RFC 3339 instant") {
			t.Errorf("%s: %d %s", since, code, body)
		}
	}
}

// Review Focus 1: a room whose facts cannot be read contributes no item, is named in unread, and the other
// rooms still answer.
func TestNeedsSaysWhenARoomsStateIsUnread(t *testing.T) {
	e := setup(t, roomsOn, worldWithSplitAndMerge(t).gate, brokenLogFor(t, "3kq7x2ma"))
	// ... assert items hold only 26zfnuxm's and unread == ["3kq7x2ma"]
}

// `since` keeps only the items whose cause is newer than it: an approval asked at 19:00 is out at 19:05.
func TestNeedsSinceFiltersByTheItemsOwnTime(t *testing.T) {
	e := setup(t, roomsOn, worldWithSplitAndMerge(t).gate)
	// ... GET /api/needs?since=2026-11-04T19:01:00Z; the approval asked at 19:00 is absent, the merge is present
}
```

`internal/metrics/metrics_test.go` (the dashboard queries the spec's `maku_needs_*`, so the prefix has to be real):

```go
// The spec's series are maku_needs_*, which MakuName can only produce from a needs_* instrument:
// rooms_needs_list_total would be served as maku_rooms_needs_list_total. This is the test that makes
// the dashboard's queries true rather than plausible.
func TestMakuNameCoversNeeds(t *testing.T) {
	for in, want := range map[string]string{
		"needs_list_total": "maku_needs_list_total",
		"needs_items":      "maku_needs_items",
		"needs":            "",
		"needsx":           "",
	} {
		if got := MakuName(in); got != want {
			t.Fatalf("MakuName(%q) = %q, want %q", in, got, want)
		}
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestNeeds' -count=1; go test ./internal/metrics/ -run TestMakuNameCoversNeeds -count=1`
Expected: FAIL (404 on `/api/needs`; `MakuName("needs_list_total") = ""`).

- [ ] **Step 3: The route**

`needs.go`: `func (s *Server) needsRoute(w http.ResponseWriter, r *http.Request)` — the principal, the same
`routeTimeout`, the same `X-Rooms-Access` header the room list sets, then one pass over the rooms the caller may
read (reuse `s.roomRows`' gate loop, not its rows: `s.needsScan(ctx, p, filter) (items, unread, access, err)`),
`Ordered`, the `since` filter (`item.At.After(since)`, a zero `At` always kept), the `room`/`repo` filters, and
the cursor `s.now().UTC().Truncate(time.Second).Format(time.RFC3339)`. `needsScan` is the single scan both doors
call.

In `server.go`, beside the room list: `if s.Needs { mux.HandleFunc("GET /api/needs", s.needsRoute) }`. The
switch is decoded, not assumed: `internal/config/config.go`'s `HumanConfig` gains
`Needs NeedsConfig \`json:"needs,omitzero"\`` with `type NeedsConfig struct{ Enabled bool \`json:"enabled"\` }`
and a default of true where `MCPConfig`'s is applied, and `internal/app/broker.go` passes
`Needs: h.Needs.Enabled` in the `humanapi.Server` literal beside `MCP: h.MCP.Enabled`.

- [ ] **Step 4: The metrics**

In `metrics.go`'s `New`, two instruments and their accessors, and in `MakuName` beside the existing cases
(a `needs_` family is served as `maku_needs_*`):

```go
	// needs_list_total{surface,principal,outcome} -> maku_needs_list_total (MakuName's needs_ case): needs/v1's adoption.
	s.NeedsList, err = meter.Int64Counter("needs_list_total", metric.WithDescription("Needs lists served, by surface, principal and outcome."))
	// needs_items{kind} -> maku_needs_items: what the inbox is made of; the split hole showed here first.
	needsGauge, err = meter.Int64ObservableGauge("needs_items", metric.WithDescription("Items the last list held, by kind."))
```

with `func (s *Set) Needs(kinds map[string]int)` storing a copy behind a mutex the gauge callback reads, and
`case strings.HasPrefix(name, "needs_"): return "maku_" + name` in `MakuName` — without it `MakuName("needs_list_total")` is
empty and the dashboard's `maku_needs_*` queries match nothing; the alternative, `rooms_needs_*` instruments, would
have been served as `maku_rooms_needs_*`, which is not the spec's name either.

- [ ] **Step 5: Run the tests**

Run: `go test ./internal/humanapi/ ./internal/metrics/ ./internal/config/ -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/humanapi internal/metrics internal/config internal/app
git commit -m "feat(humanapi): GET /api/needs, the human door onto needs/v1"
```

### Task 2: `needs_list` on the human tool list

**Files:**
- Create: `internal/humanapi/mcpneeds.go`
- Modify: `internal/humanapi/mcp.go` (the tool table), `internal/humanapi/sponsored_test.go` (the human names string)
- Test: `internal/humanapi/mcpneeds_test.go`

**Interfaces:**
- Consumes: `needsScan` (Task 1).
- Produces: the tool `needs_list`, schema
  `{"type":"object","additionalProperties":false,"properties":{"since":{"type":"string","pattern":"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},"room":{"type":"string","pattern":"^[a-z2-7]{8}$"},"repo":{"type":"string","pattern":"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$"}}}`;
  the result `{text, data}` where `data` is the same envelope as `/api/needs`.

- [ ] **Step 1: Write the failing test**

```go
// CD10: the tool's items are the route's items, in the same order, and its text is the list to show as it is.
func TestNeedsListMatchesTheRoute(t *testing.T) {
	e := setup(t, mcpOn, worldWithSplitAndMerge(t).gate)
	got := call(t, e, viaRoomctl("dev"), "needs_list", map[string]any{})
	var data struct{ Items []summary.Need }
	if err := json.Unmarshal([]byte(got.structured), &data); err != nil {
		t.Fatal(err)
	}
	var keys []string
	for _, n := range data.Items {
		keys = append(keys, n.Key())
	}
	if !slices.Equal(keys, []string{"26zfnuxm/plan_confirmation/2238", "3kq7x2ma/merge/2239"}) {
		t.Fatalf("%v", keys)
	}
	if !strings.Contains(got.text, "needs you") {
		t.Fatalf("%s", got.text)
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/humanapi/ -run TestNeedsListMatchesTheRoute -count=1`
Expected: FAIL (`unknown tool: needs_list`).

- [ ] **Step 3: The tool and its renderer**

`mcpneeds.go`: `func (s *Server) needsList(ctx context.Context, p authn.Principal, args json.RawMessage) (any, error)`
— decode into `needsArgs{Since, Room, Repo string}`, call `needsScan`, render `roomview.Needs` into `text`, return
`viewResult`. Refuse a bad `since` as `toolError("invalid_arguments: since is an RFC 3339 instant")`. Append the
entry **after `issue_draft`** in `mcpTools`' `all` slice — `issue_draft` is the last broker-read entry, and
`issue_file` is a relay tool that is not in this table — with a description that quotes the kinds and the order.

`internal/roomview/needs.go` (new): `func Needs(w io.Writer, items []summary.Need, unread []string, o Options) error`
— one line per item (`kind — what → action label`), the room link, and one line for `unread` when it is not
empty. Every string through the card's `text`/`quoted` helpers.

- [ ] **Step 4: Run the test, then the package**

Run: `go test ./internal/humanapi/ -run TestNeedsListMatchesTheRoute -count=1 && go test ./internal/roomview/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/humanapi internal/roomview
git commit -m "feat(humanapi): needs_list on the human tool list, rendered by the one view package"
```

### Task 3: the sponsored door, and the auth boundary tests

**Files:**
- Modify: `internal/humanapi/mcpneeds.go`, `internal/humanapi/mcp.go` (`sponsoredTools`), `internal/humanapi/sponsored_test.go`
- Test: `internal/humanapi/sponsored_test.go`, `internal/humanapi/needs_test.go`

**Interfaces:**
- Produces: `sponsoredTools = []string{"issue_draft", "room_summary", "room_tail", mcpwire.RoomChanges, "needs_list"}`;
  the sponsored call's `Caller` has `RoomScoped: true`; the sponsored tool's schema is the same closed object
  (no field may carry a decision).

- [ ] **Step 1: Write the failing boundary tests**

```go
// CD28: adding needs_list to the sponsored set is a deliberate, tested amendment: the list is closed.
func TestSponsoredToolList(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP))
	if got := toolNames(t, e, bearer("slack-app")); got != "run_create,issue_draft,room_summary,room_tail,room_changes,needs_list" {
		t.Fatalf("%s", got)
	}
	if got := toolNames(t, e, viaRoomctl("dev")); got != "rooms_list,room_summary,room_tail,room_changes,room_queue,room_fork,issue_draft,needs_list" {
		t.Fatalf("a human's list changed: %s", got)
	}
}

// CD28: nothing outside {since, room, repo} is accepted, on either door: the schema is the whole surface.
func TestSponsoredNeedsListRefusesAFieldOutsideTheSchema(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP))
	_, out := rpc(t, e, bearer("slack-app"), "tools/call", map[string]any{"name": "needs_list",
		"arguments": map[string]any{"decide": "01JBX3K8"}})
	if rpcCode(out) != -32602 {
		t.Fatalf("%v", out)
	}
}

// CD28: the human door is not a sponsored token's.
func TestNeedsRouteRefusesASponsoredToken(t *testing.T) {
	e := setup(t, roomsOn, withSponsored(sponsoredP))
	if code, _ := get(t, e, bearer("slack-app"), "/api/needs"); code != 401 {
		t.Fatalf("%d", code)
	}
}

// A sponsored list is the room's, not a login's: the maintainer's merge is in it, with a link and no decision.
func TestSponsoredNeedsListIsTheRooms(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP), sponsoredRooms(t, worldWithSplitAndMerge(t)))
	// ... assert one merge item, Action.Kind == "merge", Action.URL == the pull request's
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestSponsored|TestNeedsRouteRefuses' -count=1`
Expected: FAIL on the two name strings and `unknown tool: needs_list`.

- [ ] **Step 3: The sponsored call**

`s.needsList` sets `in.Caller.RoomScoped = true` when `p.Sponsored`, and `s.standing` already returns no login
for it, so no `repoaccess` read happens for the App: the merge, question and review clauses accept
`RoomScoped` without a login and give a link, never a decision. The schema stays one constant used by both
lists, so a field cannot appear on one door only.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/humanapi/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/humanapi
git commit -m "feat(humanapi): needs_list on the sponsored list, with the boundary tests that pin both doors"
```

### Task 4: `maku needs`

**Files:**
- Create: `internal/maku/needs.go`, `internal/maku/needs_test.go`
- Modify: `internal/maku/client.go`, `internal/app/maku.go` (the command table and the case)
- Test: `internal/app/maku_test.go`, `internal/maku/needs_test.go`

**Interfaces:**
- Consumes: `GET /api/needs` (Task 1).
- Produces: `maku.Client.Needs(ctx context.Context, f maku.NeedsFilter) (maku.NeedsPage, error)`;
  `NeedsFilter{Since, Room, Repo string}`; `NeedsPage{Items []summary.Need, Cursor string, Unread []string}`;
  `maku needs [--since RFC3339] [--room id] [--repo owner/name] [--format md|text] [--json]`, and a
  `cursors.json` entry `needs` holding the last cursor when `--since` is omitted.

- [ ] **Step 1: Write the failing tests**

```go
// The CLI's list is the route's, and its empty case says so once.
func TestMakuNeeds(t *testing.T) {
	r, out := makuRig(t) // the file's helper: a fake broker serving /api/needs
	r.serves(`{"apiVersion":"needs/v1","items":[{"kind":"merge","id":"2239","room":"3kq7x2ma","what":"a maintainer approves PR #2239","action":{"kind":"merge","label":"review, then approve the current commit","url":"https://github.com/Smana/ai-native-ref/pull/2239"},"source":{"kind":"facts","reason":"policy_pending"}}],"cursor":"2026-11-04T19:10:00Z"}`)
	if err := r.Run(t.Context(), []string{"needs"}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "merge — a maintainer approves PR #2239") {
		t.Fatalf("%s", out.String())
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/app/ -run TestMakuNeeds -count=1`
Expected: FAIL (`unknown command "needs"`).

- [ ] **Step 3: The command**

`client.go`: `Needs` is `roomsBody`'s shape — the same token header, `GET /api/needs` with the query, the same
`Refusal` mapping. `internal/app/maku.go`: `"needs"` joins the command table's switch, with a `flag.FlagSet`,
the usage line, `--since` validated by `time.Parse(time.RFC3339, …)` before the call, and the cursor read from
`Cursors.Get("needs")` / written after a successful call.

- [ ] **Step 4: Run the suites**

Run: `go test ./internal/app/ ./internal/maku/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/maku internal/app
git commit -m "feat(maku): maku needs, one list from the one derivation"
```

### Task 5: the web panel reads `/api/needs`

**Files:**
- Modify: `web/src/needs.ts`, `web/src/api.ts`, `web/src/summary.ts`, `web/test/needs.test.ts`
- Rebuild: `internal/humanapi/ui/dist` (through `task ui:build`, which is what `task ui:check` compares)

**Interfaces:**
- Consumes: `GET /api/needs?room=<id>` (Task 1) and the room's `summary/v1` frame.
- Produces: `fetchNeeds(room: string, since?: string): Promise<NeedsPage>` in `api.ts`; `mountNeeds`'s
  "other needs" list renders `NeedsPage.items` (approvals stay the panel's own cards, since deciding is theirs).

- [ ] **Step 1: Write the failing test**

```ts
// CD21: the panel's non-approval items are the route's, whatever the summary frame says.
it("renders the needs route's items", async () => {
  const page = { apiVersion: "needs/v1", cursor: "2026-11-04T19:10:00Z", items: [
    { kind: "plan_confirmation", id: "2238", room: "26zfnuxm", what: "the scoper proposes a split",
      action: { kind: "comment", label: "comment /factory split on issue #2238", url: "https://github.com/Smana/ai-native-ref/issues/2238" }, source: { kind: "facts" } }] };
  const panel = mount(t, { needs: async () => page }); // the test's fake fetch
  await panel.refresh();
  expect(panel.root.textContent).toContain("comment /factory split on issue #2238");
});
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd web && npm test -- needs`
Expected: FAIL (no fetch; the panel still reads `summary.needsYou`).

- [ ] **Step 3: The fetch and the render**

`api.ts` gains `fetchNeeds`, mirroring the existing `api(path)` helper (same credentials, same error shape).
`needs.ts` keeps the approval cards and replaces the `needsItems` list with the fetched items, filtered
`kind !== "approval"`, each rendered as `action.label` linking to `action.url` through the page's existing
`safeLink`. A failed fetch leaves the summary's items in place and adds one line saying the list could not be
refreshed — never an empty panel.

- [ ] **Step 4: Rebuild the bundle and run the gates**

Run: `task ui:test && task ui:check`
Expected: typecheck clean, tests pass, and `git diff --exit-code -- internal/humanapi/ui/dist` is clean after the
build (so the bundle is committed).

- [ ] **Step 5: Commit**

```bash
git add web/src web/test internal/humanapi/ui/dist
git commit -m "feat(web): the needs panel reads /api/needs, the same list as the CLI and the tools"
```

### Task 6: PR 3

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/needs-ends
gh pr create --title "feat(humanapi): /api/needs and a closed sponsored needs_list, one shape" \
  --body "CD9's seam, CD10, CD28. Both doors, the CLI and the panel read needs/v1; the sponsored list is closed and tested. Evidence: task check exit 0, task lint 0."
```

---

## PR 4 — `feat/resume-brief`: the deterministic brief

CD11 and G6: the need, the plan version, what changed, the blocker and the links, in one read, escaped by the
one package that escapes. The brief's `Cause` hook exists and stays empty here: PR 7 fills it.

### Task 1: `internal/roomview/brief.go`

**Files:**
- Create: `internal/roomview/brief.go`, `internal/roomview/brief_test.go`, `internal/roomview/testdata/brief/*.md`, `internal/roomview/testdata/brief/*.json`
- Test: `internal/roomview/brief_test.go` (goldens, plus `assertInert` from `goldmark_test.go`)

**Interfaces:**
- Consumes: `ChangeSet`/`Milestones` (`changes.go`), `summary.Need`, `envelope.TaskFacts`, `Options`.
- Produces: `type PlanVersion struct`, `type BriefIn struct`, `func Brief(w io.Writer, in BriefIn, o Options) error`;
  `PlanVersion.Source` is `"proposal"`, `"scope"` or `""` — the planner plan fills `"proposal"`, this plan fills
  `"scope"` (the last handoff's `Scope.State`); `BriefIn.Cause` is written by PR 7 and left empty here.

- [ ] **Step 1: Write the goldens and the failing test**

`testdata/brief/normal.json` and `normal.md`. The golden is the spec's example, normalised to what the room
holds and to the fields this PR renders:

```markdown
**Resume: 26zfnuxm · #2238 docs: the install link points at a moved page**

Asked: #2238, the install link points at a moved page
Acceptance: `README.md's install link returns 200`
Plan: scope ready · budget $2.00 ceiling
Changed since 2026-11-04 18:20 UTC (16 h):
- 18:31 the reviewer requested changes → implementer started
- 18:52 CI `links` failed
- 19:04 the implementer pushed a fix; CI is running
Blocked on: `failed_check` — a check it waits on never reported within merge.awaitingCIFor
Next: read the failing check, then `/factory retry` → https://github.com/Smana/ai-native-ref/pull/2239
Links: room https://rooms.example/r/26zfnuxm · issue https://github.com/Smana/ai-native-ref/issues/2238 · PR https://github.com/Smana/ai-native-ref/pull/2239
```

`testdata/brief/hostile.json` and `hostile.md` are the Review Focus 4 case: the title inputs carry a literal
`]`, `<`, `|`, `\x1b[31m` and `\u202e`, and the golden holds what the renderer writes (escaped brackets, the
control bytes gone, no table and no link outside the allowlist). `no-cursor.json`/`no-cursor.md` is the same
brief with `since` zero: no `Changed since` header.

```go
// CD11: the brief is fixed prose and quoted data, and every rendering parses inert (offline proof 8).
func TestBriefGoldens(t *testing.T) {
	for _, name := range []string{"normal", "no-cursor", "hostile"} {
		in := loadBrief(t, name) // the test's decoder for testdata/brief/<name>.json
		var b strings.Builder
		if err := roomview.Brief(&b, in, roomview.Options{Format: roomview.Markdown, Now: in.Now, Rooms: "https://rooms.example"}); err != nil {
			t.Fatal(err)
		}
		want, err := os.ReadFile(filepath.Join("testdata", "brief", name+".md"))
		if err != nil {
			t.Fatal(err)
		}
		if b.String() != string(want) {
			t.Fatalf("%s:\n%s", name, b.String())
		}
		assertInert(t, b.String(), "https://rooms.example", in.Untrusted())
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/roomview/ -run TestBriefGoldens -count=1`
Expected: FAIL at compile (`undefined: roomview.Brief`).

- [ ] **Step 3: The renderer**

```go
// PlanVersion is which plan ran: the proposal a task was filed from (the plan tool's version and hash, filled
// by that plan), or the scoper's own scope state. Source is "proposal", "scope", or "" for neither.
type PlanVersion struct {
	Source          string
	Rev             int
	Hash            string
	Class           string
	CeilingMicroUSD int64
	CeilingSource   string
}

// BriefIn is everything the brief renders. Every string that an agent, a person or GitHub wrote is untrusted.
type BriefIn struct {
	Room    string
	RoomURL string
	Issue   *envelope.IssueFact
	PR      *envelope.PRFact
	Facts   *envelope.TaskFacts
	Plan    PlanVersion
	Since   time.Time     // the cursor's time; zero: no "Changed since" header
	Changed ChangeSet
	Blocker *summary.Need
	// Cause is summary.Cause's code and is rendered as one "Fix:" line. It is empty here: the table that
	// produces it lands with brief.ciEvidence (PR 7), and until then the line never appears.
	Cause string
	Now   time.Time
}

// Brief writes the resume brief: fixed prose, quoted data. The plan version is display only; nothing here
// decides anything, and no line carries a command that acts (CD11).
func Brief(w io.Writer, in BriefIn, o Options) error
```

Layout, in order and each line omitted when its data is absent: the title line (room id, `#<issue>`, the
escaped title); `Asked:` (the issue's title, ≤ 300 runes in a code span) and `Acceptance:` (the last handoff
scope's checks); `Plan:` (`proposal v<N> <hash>`, or `scope <state>`, plus the ceiling from `CeilingMicroUSD`);
`Changed since …` with `span(now.Sub(in.Since))` and one line per `Milestone` via the existing
`card.milestone`; `Blocked on:` (`Blocker.Kind` in a code span, then `Blocker.What`); `Fix:` only when
`Cause != ""` (never in this PR's goldens); `Next:` (`Blocker.Action.Label`, then the URL as a link only if
`allowed`); `Links:` the room, the issue, the PR, each `allowed`. Reuse `escapeTitle`, `code`, `link`, `stamp`,
`span`, `dollars`.

- [ ] **Step 4: Run the renderer's tests**

Run: `go test ./internal/roomview/ -count=1`
Expected: PASS, `assertInert` included.

- [ ] **Step 5: Commit**

```bash
git add internal/roomview
git commit -m "feat(roomview): the resume brief, fixed prose over quoted data"
```

### Task 2: the brief's two doors

**Files:**
- Create: `internal/humanapi/brief.go`, `internal/humanapi/brief_test.go`
- Modify: `internal/humanapi/server.go` (the route), `internal/humanapi/mcp.go` (the tool), `internal/humanapi/summary.go` (share the fold read)
- Test: `internal/humanapi/brief_test.go`, `internal/humanapi/sponsored_test.go` (the human names string)

**Interfaces:**
- Consumes: `roomview.Brief`, `roomview.Milestones`, `needsFor` (PR 1).
- Produces: `GET /api/rooms/{id}/brief?since=<RFC3339>|seq:<n>` → `{"apiVersion":"brief/v1","text":"…","room":"…","cursor":"seq:N"}`;
  the MCP tool `room_brief` with schema `{room, since?}` (human list only).

- [ ] **Step 1: Write the failing tests**

```go
// room_brief returns the brief and the cursor the caller passes back next time, as room_changes does.
func TestRoomBrief(t *testing.T) {
	e := setup(t, mcpOn, worldWithSplitAndMerge(t).gate)
	got := call(t, e, viaRoomctl("dev"), "room_brief", map[string]any{"room": "3kq7x2ma"})
	if !strings.HasPrefix(got.text, "**Resume: 3kq7x2ma") {
		t.Fatalf("%s", got.text)
	}
	var data struct{ Cursor string }
	if err := json.Unmarshal([]byte(got.structured), &data); err != nil || !maku.IsCursor(data.Cursor) {
		t.Fatalf("%q %v", data.Cursor, err)
	}
}

// The brief is the human list's: the App's sponsored principal has no brief, and its tool list says so.
func TestSponsoredToolList(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP))
	if got := toolNames(t, e, bearer("slack-app")); strings.Contains(got, "room_brief") {
		t.Fatalf("the sponsored list gained a tool: %s", got)
	}
	if got := toolNames(t, e, viaRoomctl("dev")); !strings.HasSuffix(got, ",needs_list,room_brief") {
		t.Fatalf("the human list: %s", got)
	}
}

// A sponsored token on the route is refused like every other human route.
func TestBriefRouteRefusesASponsoredToken(t *testing.T) {
	e := setup(t, roomsOn, withSponsored(sponsoredP))
	if code, _ := get(t, e, bearer("slack-app"), "/api/rooms/3kq7x2ma/brief"); code != 401 {
		t.Fatalf("%d", code)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestRoomBrief|TestSponsoredToolList|TestBriefRoute' -count=1`
Expected: FAIL (404, and the human names string is short one tool).

- [ ] **Step 3: The route and the tool**

`brief.go`'s handler folds the room once (`s.summaryOf`'s path: `s.fold`, `s.Log`), builds `roomview.BriefIn`:
the facts, the last handoff's `Scope.State` and `Acceptance` (from the fold's events, newest handoff with a
`Scope`), `Changed: roomview.Milestones(MilestoneInput{Room, URL, Base: nil, Events: sinceEvents, Limit: 20})`,
and `Blocker: needsFor(…)[0]`. `Cause` is left zero here. `since` is either a cursor (`seq:N`, the CLI's stored
one) or an RFC 3339 instant; a malformed value is a 400 naming both forms. The tool returns
`viewResult{text: rendered, data: the same envelope}`.

Cost note: the route reads one room; `since` defaults to 24 h back when absent, as `room_changes` does.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/humanapi/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/humanapi
git commit -m "feat(humanapi): /api/rooms/{id}/brief and the room_brief tool"
```

### Task 3: the `resume` prompt, the one-call `inbox`, and the CLI's head

**Files:**
- Modify: `internal/humanapi/mcpprompts.go`, `internal/maku/status.go`, `internal/maku/client.go`, `internal/app/maku_views.go`
- Test: `internal/humanapi/mcpprompts_test.go`, `internal/maku/maku_test.go`, `internal/app/maku_test.go`

**Interfaces:**
- Produces: the prompt `resume` (arguments: `room`); `maku.BriefHead(text string) string` (the brief's first six
  section lines); `maku.Client.Brief(ctx, room, since string) (string, error)` (the tool).

- [ ] **Step 1: Write the failing tests**

```go
// The resume prompt is one call to needs_list, then one brief for the first item's room.
func TestResumePrompt(t *testing.T) {
	e := setup(t, mcpOn)
	got := promptText(t, e, viaRoomctl("dev"), "resume", map[string]string{})
	for _, want := range []string{"needs_list", "room_brief", "show each tool's text as it is", "never say a room exists before room_brief shows it"} {
		if !strings.Contains(got, want) {
			t.Fatalf("missing %q in %q", want, got)
		}
	}
}

// maku status leads with the brief's head, and the rest of the card follows unchanged.
func TestStatusLeadsWithTheBrief(t *testing.T) {
	r, out := makuRig(t) // the file's helper, serving room_brief and the room's summary
	r.servesBrief("**Resume: 26zfnuxm · #2238 docs: the install link points at a moved page**\n\nAsked: #2238, …\nPlan: scope ready · budget $2.00 ceiling\nBlocked on: `failed_check` — …\nNext: read the failing check\nLinks: room …\n\n**Waiting on you**\n…")
	if err := r.Run(t.Context(), []string{"status", "26zfnuxm"}); err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(out.String(), "\n")
	if !strings.HasPrefix(lines[0], "**Resume: 26zfnuxm") || !strings.Contains(out.String(), "Waiting on you") {
		t.Fatalf("%s", out.String())
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run TestResumePrompt -count=1; go test ./internal/app/ -run TestStatusLeadsWithTheBrief -count=1`
Expected: FAIL (`unknown prompt: resume`; no head).

- [ ] **Step 3: The prompt, the head**

`mcpprompts.go` gains, in `mcpPrompts`' order after `status`:

```go
	{
		name: "resume", description: "Come back to a task: what it needs, the plan, what changed, and the one next step.",
		args: []promptArg{{"room", "a room id, #<issue> or PR #<n>; default: the first room in your needs list"}},
		text: func(a map[string]string) string { /* needs_list, then room_brief for the first item's room (or the
			named room), then the item's action; show each text as it is; never say a room exists before
			room_brief shows it */ },
	},
```

and `inbox`'s text becomes "Call `needs_list`. Show its text as it is. If it is empty, say so in one line and
name `rooms_list` with `mine` for the rest." `internal/maku/status.go` gains `BriefHead`, which keeps the first
six lines that start a section (`**Resume`, `Asked`, `Plan`, `Changed since`, `Blocked on`, `Next`);
`maku_views.go` prints it above the card only when `maku status` has a room and the broker serves `room_brief`
(an `maku.ErrUnknownTool` leaves the card alone, as `maku changes` does for an older broker).

- [ ] **Step 4: Run the suites**

Run: `go test ./internal/humanapi/ ./internal/maku/ ./internal/app/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/humanapi internal/maku internal/app
git commit -m "feat(maku): the resume prompt, an inbox of one call, and maku status's brief head"
```

### Task 4: PR 4

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/resume-brief
gh pr create --title "feat(roomview): the resume brief, on both doors and in maku status" \
  --body "CD11, G6. Every rendering is parsed inert; the goldens cover the normal, no-cursor and hostile cases. Evidence: task check exit 0, task lint 0."
```

---

## PR 5 — `feat/revision-first`: a revision goes before new intake

CD22, one condition and one wait reason. No queue, no reservation, no new component.

### Task 1: `waiting_revision_first`

**Files:**
- Modify: `internal/factory/config/config.go` (`Caps.PreferRevisions`), `internal/factory/reconciler/implement.go` (`slotFree`), `internal/summary/waiting.go` (the prose), `internal/factory/fmetrics/fmetrics.go` (`RevisionDeferred`), `internal/factory/reconciler/reconciler.go` (the `metrics` interface)
- Test: `internal/factory/config/config_test.go`, `internal/factory/reconciler/implement_test.go`, `internal/summary/waiting_test.go`

**Interfaces:**
- Consumes: `r.countTasks`, `v1alpha1.Task.Status.Runs`.
- Produces: `config.Caps.PreferRevisions bool` (`caps.preferRevisions`); the wait reason `waiting_revision_first`;
  `func (r *Reconciler) revisionWaiting(ctx context.Context, t *v1alpha1.Task) (bool, error)`;
  `metrics.RevisionDeferred(ctx context.Context)` → `maku_revision_deferred_total`.

- [ ] **Step 1: Write the failing tests**

```go
// CD22: a first run yields one slot-time to a revision; the revision itself does not wait.
func TestAFirstRunYieldsToARevision(t *testing.T) {
	g := rig(t, withCaps(config.Caps{ConcurrentRuns: 4, PreferRevisions: true}))
	first := g.task("aaaaaaaa", 0) // no runs yet: the next run would be its first
	rev := g.task("bbbbbbbb", 2)   // two runs: its next run continues it
	g.queued(rev, "waiting_run_slot")
	if got := g.reason(t, first); got != "waiting_revision_first" {
		t.Fatalf("%q", got)
	}
	if got := g.reason(t, rev); got == "waiting_revision_first" {
		t.Fatalf("the revision yielded to itself: %q", got)
	}
}

// The switch off changes nothing.
func TestWithoutTheSwitchNothingChanges(t *testing.T) {
	g := rig(t, withCaps(config.Caps{ConcurrentRuns: 4}))
	g.queued(g.task("bbbbbbbb", 2), "waiting_run_slot")
	if got := g.reason(t, g.task("aaaaaaaa", 0)); got != "" {
		t.Fatalf("%q", got)
	}
}

// Caps still bind: a neighbour stopped by the review WIP cap is not a revision waiting for a slot (Review Focus 5).
func TestANeighbourOnACapIsNoReasonToYield(t *testing.T) {
	g := rig(t, withCaps(config.Caps{ConcurrentRuns: 4, PreferRevisions: true}))
	g.queued(g.task("bbbbbbbb", 2), "waiting_review_wip")
	if got := g.reason(t, g.task("aaaaaaaa", 0)); got != "" {
		t.Fatalf("%q", got)
	}
}
```

and in `waiting_test.go`:

```go
func TestTheRevisionFirstReasonHasProseAndAStep(t *testing.T) {
	why, next := summary.Waiting(&envelope.TaskFacts{Phase: "Queued", Reason: "waiting_revision_first"})
	if why == "" || why == "waiting_revision_first" || next == "" {
		t.Fatalf("%q %q", why, next)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `KUBEBUILDER_ASSETS=$(go tool setup-envtest use -p path 1.36.x) go test ./internal/factory/reconciler/ -run 'TestAFirstRunYields|TestWithoutTheSwitch|TestANeighbourOnACap' -count=1 -p 1; go test ./internal/summary/ -run TestTheRevisionFirstReason -count=1`
Expected: FAIL (`PreferRevisions` undefined; the reason has no prose).

- [ ] **Step 3: The condition**

In `implement.go`, after the `live >= r.Cfg.Caps.ConcurrentRuns` block and before the room read:

```go
	// CD22: a revision goes first. preferRevisions waits only for a task whose next run continues it and which
	// a *slot* holds: a neighbour stopped by any other cap is not waiting for the slot, and priority never
	// overrides a limit. A first run waits one slot-time; nothing is reserved.
	if r.Cfg.Caps.PreferRevisions && len(t.Status.Runs) == 0 {
		if waiting, err := r.revisionWaiting(ctx, t); err != nil || waiting {
			if err != nil {
				return false, "", err
			}
			record(ctx, func(ctx context.Context) { r.Metrics.RevisionDeferred(ctx) })
			return false, "waiting_revision_first", nil
		}
	}
```

```go
// revisionWaiting is whether another task is queued for a slot to run a run that continues it.
func (r *Reconciler) revisionWaiting(ctx context.Context, t *v1alpha1.Task) (bool, error) {
	queued, err := r.countTasks(ctx, func(o *v1alpha1.Task) bool {
		return o.Name != t.Name && o.Status.Phase == v1alpha1.PhaseQueued && len(o.Status.Runs) > 0 &&
			o.Status.Reason == "waiting_run_slot"
	})
	return queued > 0, err
}
```

`config.Caps` gains `PreferRevisions bool \`json:"preferRevisions,omitempty"\`` with the comment quoting CD22;
`summary.reasons()` gains `"waiting_revision_first": "a revision of another task runs before new intake"` and
`nextStep` gains `"nothing to do: it starts once no revision waits for the slot"`.

- [ ] **Step 4: Run the tests**

Run: `KUBEBUILDER_ASSETS=$(go tool setup-envtest use -p path 1.36.x) go test ./internal/factory/... ./internal/summary/ -count=1 -p 1 && task lint`
Expected: PASS, 0 issues.

- [ ] **Step 5: Commit**

```bash
git add internal/factory internal/summary docs
git commit -m "feat(factory): a revision goes before new intake, one wait reason and no reservation"
```

### Task 2: PR 5

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task check`
Expected: exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/revision-first
gh pr create --title "feat(factory): caps.preferRevisions, waiting_revision_first" \
  --body "CD22. Three fake tasks prove the yield, the off switch, and that a cap-stopped neighbour is no reason to yield. Evidence: task check exit 0."
```

---

## PR 6 — `feat/final-spend`: the dollars settle once

CD23 and G7's second truth: a terminal task requeues once past the settle window, prices again, and posts one
final fact whose number it will never change.

### Task 1: `Costs` keeps a run's settled cost

**Files:**
- Modify: `internal/factory/meter/meter.go` (`Costs`, `put` → `Put`, the tick's call)
- Test: `internal/factory/meter/meter_test.go`

**Interfaces:**
- Produces: `func (c *Costs) Put(m map[string]Cost, now time.Time)` — the tick writes its map once per tick, with
  the tick's clock; `func (c *Costs) Get(id string) (Cost, bool)` returns an entry kept for `costsRetain` (15
  min) after the tick that last saw the run. Nothing else writes or forgets: `Put` is the only writer, and an
  entry ages out on the first `Put` past the bound.

- [ ] **Step 1: Write the failing test**

```go
// CD23: the meter drops an ended run from its active set endSettle after it ended; its settled cost stays
// readable for the reconciler's final re-price, and no longer.
func TestCostsKeepARunsSettledValuePastItsEnd(t *testing.T) {
	now := time.Date(2026, 11, 4, 19, 0, 0, 0, time.UTC)
	var c meter.Costs
	c.Put(map[string]meter.Cost{"r1": {MicroUSD: 420_000}}, now)
	c.Put(map[string]meter.Cost{}, now.Add(3*time.Minute)) // the run left the tick's set
	if got, ok := c.Get("r1"); !ok || got.MicroUSD != 420_000 {
		t.Fatalf("%+v %v", got, ok)
	}
	c.Put(map[string]meter.Cost{}, now.Add(20*time.Minute))
	if _, ok := c.Get("r1"); ok {
		t.Fatal("a 20-minute-old entry is still served")
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/factory/meter/ -run TestCostsKeepARunsSettledValue -count=1`
Expected: FAIL (`Put` undefined; the map is replaced whole today).

- [ ] **Step 3: The retention**

```go
// costsRetain is how long a run's last priced cost stays readable after the tick that dropped it: the
// reconciler's final re-price lands endSettle after the last run's end, and the meter drops an ended run from
// its active set at that same moment (CD23).
const costsRetain = 15 * time.Minute

type costEntry struct {
	Cost
	at time.Time // the tick that last held the run
}
```

`Put(m, now)` merges: this tick's entries replace theirs with `at = now`; an entry absent from `m` is kept while
`now.Sub(at) < costsRetain` and dropped after. `Get` returns `false` past that bound. The tick calls
`m.Costs.Put(costs, m.now())`; no other caller exists, which is why `Put` is the only writer.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/factory/meter/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/meter
git commit -m "feat(meter): a run's settled cost stays readable past the tick that drops it"
```

### Task 2: the final requeue and the exact final fact

**Files:**
- Modify: `internal/factory/config/config.go` (`Facts.FinalSpend`), `internal/factory/reconciler/reconciler.go` (`Reconcile`, `spendFinalAt`, the `metrics` interface), `internal/factory/reconciler/facts.go` (`factsKey`, `factsFor`), `internal/envelope/payloads.go` (`TaskFacts.SpendFinal`), `internal/factory/fmetrics/fmetrics.go` (`TaskSpendFinal`)
- Test: `internal/factory/reconciler/final_spend_test.go`

**Interfaces:**
- Produces: `config.Facts{FinalSpend bool}` (`facts.finalSpend`); `envelope.TaskFacts.SpendFinal bool`
  (`spendFinal`); `func (r *Reconciler) spendFinalAt(t *v1alpha1.Task) (time.Time, bool)`;
  `func (r *Reconciler) spendFinalDue(t *v1alpha1.Task) bool`; `metrics.TaskSpendFinal(ctx context.Context, d time.Duration)`.

- [ ] **Step 1: Write the failing tests**

```go
// CD23: a terminal task requeues exactly once, prices again, and posts one fact whose dollars it will not change.
func TestAFinalSpendLandsOnce(t *testing.T) {
	g := rig(t, withFacts(config.Facts{FinalSpend: true}))
	tk := g.ended("26zfnuxm", run("r1", 2*time.Hour, 0)) // ended, its last run ended now
	_, requeue := g.reconcileOnce(t, tk)
	if requeue == 0 || requeue > 3*time.Minute {
		t.Fatalf("requeue %s", requeue)
	}
	g.meterPrices("r1", 420_000)
	got, requeue := g.reconcileAt(t, g.now().Add(3*time.Minute))
	if requeue != 0 {
		t.Fatalf("a second requeue: %s", requeue)
	}
	if got.Status.Facts == nil || g.posted(t, "spendFinal") != 1 {
		t.Fatalf("facts %+v", got.Status.Facts)
	}
	if f := g.facts(); f.Spend.UsedMicroUSD != 420_000 || !f.SpendFinal {
		t.Fatalf("%+v", f)
	}
}

// Review Focus 6: a task that ended without a run has nothing to settle.
func TestATaskWithoutRunsNeverRequeuesForSpend(t *testing.T) {
	g := rig(t, withFacts(config.Facts{FinalSpend: true}))
	_, requeue := g.reconcileOnce(t, g.endedNoRun("26zfnuxm"))
	if requeue != 0 || g.posted(t, "spendFinal") != 0 {
		t.Fatalf("requeue %s, facts %d", requeue, g.posted(t, "spendFinal"))
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `KUBEBUILDER_ASSETS=$(go tool setup-envtest use -p path 1.36.x) go test ./internal/factory/reconciler/ -run 'TestAFinalSpend|TestATaskWithoutRuns' -count=1 -p 1`
Expected: FAIL (`Facts` undefined; no `SpendFinal`).

- [ ] **Step 3: The requeue, the re-price, the fact**

```go
// spendFinalMargin is past the meter's own settle window, so the re-price reads a figure that has landed.
const spendFinalMargin = time.Minute

// spendFinalAt is when a terminal task's dollars are final: its last run's end, plus the settle window, plus a
// margin. false for a task that never ran, or when the switch is off (CD23).
func (r *Reconciler) spendFinalAt(t *v1alpha1.Task) (time.Time, bool) {
	if !r.Cfg.Facts.FinalSpend || !v1alpha1.TerminalPhase(t.Status.Phase) || len(t.Status.Runs) == 0 {
		return time.Time{}, false
	}
	last := t.Status.Runs[len(t.Status.Runs)-1]
	end := last.Started
	if last.Finished != nil {
		end = last.Finished
	}
	if end == nil {
		end = t.Status.PhaseSince
	}
	if end == nil {
		return time.Time{}, false
	}
	return end.Add(r.settleWindow() + spendFinalMargin), true
}

func (r *Reconciler) spendFinalDue(t *v1alpha1.Task) bool {
	at, ok := r.spendFinalAt(t)
	return ok && !r.Now().Before(at)
}
```

In `Reconcile`, the early return becomes:

```go
	if ended && !watchWait && len(t.Status.Outbox) == 0 && !r.spanDue(&t) && !r.settling(&t) && !r.factsDue(&t) && !r.spendFinalDue(&t) && !closeDue {
		left := closeWait
		if at, ok := r.spendFinalAt(&t); ok {
			left = soonest(left, max(at.Sub(r.Now()), time.Second)) // one timed requeue, not a poll
		}
		return ctrl.Result{RequeueAfter: left}, nil
	}
```

and, when `spendFinalDue` holds, the pass ends with `r.price(ctx, &t)` (already idempotent, `max` per record)
followed by the existing `postFacts`. `factsFor` sets `f.SpendFinal = r.spendFinalDue(t)`; `factsKey` buckets
dollars only for a fact that is not final:

```go
	if sp := f.Spend; sp != nil && !f.SpendFinal { // the final figure is a claim about money: never bucketed (CD23)
		…existing 10 % step…
	}
```

`TaskSpendFinal` records `r.Now().Sub(lastRunEnd)` once, in the pass that posts. `TaskFacts.SpendFinal` is a
room fact, not a `TaskStatus` field, so no CRD schema changes and `task crd:check` stays green.

- [ ] **Step 4: Run the suites**

Run: `KUBEBUILDER_ASSETS=$(go tool setup-envtest use -p path 1.36.x) go test ./internal/factory/... ./internal/envelope/ -count=1 -p 1 && task crd:check`
Expected: PASS, and `task crd:check` reports no diff.

- [ ] **Step 5: Commit**

```bash
git add internal/factory internal/envelope
git commit -m "feat(factory): the final spend lands once, after the settle window, and stops moving"
```

### Task 3: the words, in the card and the brief

**Files:**
- Modify: `internal/summary/summary.go` (`Status.SpendFinal`), `internal/roomview/card.go` (`spend`), `internal/roomview/brief.go` (the plan line), `internal/roomview/overview.go` (a row's cell), `web/src/summary.ts`
- Test: `internal/roomview/card_test.go`, `internal/roomview/brief_test.go` (the two spend-settling tests)

**Interfaces:**
- Produces: `summary.Summary.Status.SpendFinal bool \`json:"spendFinal,omitempty"\``; the sentence
  `spend settling` in place of a dollar figure; `web/src/summary.ts`'s `status.spendFinal?: boolean`.

- [ ] **Step 1: Write the failing tests**

```go
// CD23: a finished task says its dollars are still settling, in the card and in the brief, and names no figure
// it will change.
func TestTheCardSaysSpendSettling(t *testing.T) {
	var s summary.Summary
	s.Status.Phase = "Done"
	s.Status.Spend = &envelope.SpendFact{UsedMicroUSD: 3_100_000, LimitMicroUSD: 5_000_000}
	var b strings.Builder
	if err := roomview.Card(&b, s, roomview.Options{Format: roomview.Text, Now: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(b.String(), "spend settling") || strings.Contains(b.String(), "$3.10") {
		t.Fatalf("%s", b.String())
	}
}

// The same words in the brief, whose plan line reads the facts and not a Summary.
func TestTheBriefSaysSpendSettling(t *testing.T) {
	in := roomview.BriefIn{Room: "26zfnuxm", RoomURL: "https://rooms.example/r/26zfnuxm",
		Facts: &envelope.TaskFacts{Phase: "Done", Spend: &envelope.SpendFact{UsedMicroUSD: 3_100_000, LimitMicroUSD: 5_000_000}},
		Plan: roomview.PlanVersion{Source: "scope", CeilingMicroUSD: 5_000_000}, Now: time.Now()}
	var b strings.Builder
	if err := roomview.Brief(&b, in, roomview.Options{Format: roomview.Text, Now: in.Now}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(b.String(), "spend settling") {
		t.Fatalf("%s", b.String())
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/roomview/ -run 'TestTheCardSaysSpendSettling|TestTheBriefSaysSpendSettling' -count=1`
Expected: FAIL (the card prints `$3.10 of $5.00`; the plan line prints the ceiling alone).

- [ ] **Step 3: The sentence**

`card.spend` returns `spend settling` when `cardState(s)` is `StateDone`, `StateFailed` or `StateStopped` and
`!s.Status.SpendFinal`; otherwise the existing figure. The brief's `Plan:` line adds `· spend settling` under the
same condition, reading `BriefIn.Facts.SpendFinal` (the brief has no `Summary`). `web/src/summary.ts` gains the
field and the panel shows the same words (one branch, one test).

- [ ] **Step 4: Run the suites and the web gates**

Run: `go test ./internal/roomview/ ./internal/summary/ -count=1 && task ui:test && task ui:check`
Expected: PASS, bundle clean.

- [ ] **Step 5: Commit**

```bash
git add internal/summary internal/roomview web/src web/test internal/humanapi/ui/dist
git commit -m "feat(roomview): a finished task's dollars say when they are still settling"
```

### Task 4: PR 6

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/final-spend
gh pr create --title "feat(factory): facts.finalSpend, one final fact after the settle window" \
  --body "CD23. The meter keeps a settled cost readable long enough to re-price; the card and the brief say 'spend settling' before it. The ledger's own gap (maku#280) is named here, not fixed. Evidence: task check exit 0."
```

---

## PR 7 — `feat/brief-evidence`: what the reviewer and CI said, and a failure you can act on

CD12 and fast-follow 6. The revision brief carries the reviewer's comments and the failing check's annotations,
fenced and bounded; the resume brief turns a permission, configuration or egress failure into one fix.

### Task 1: `CheckAnnotations` on the merger

**Files:**
- Modify: `internal/factory/forge/forge.go` (`Annotation`, the `Merger` interface), `internal/factory/forge/github.go`, `internal/factory/forge/absent.go`, `internal/factory/forge/forgetest/fake.go`
- Test: `internal/factory/forge/github_test.go`

**Interfaces:**
- Produces: `type Annotation struct{ Path, Message, Level string; StartLine int }`;
  `Merger.CheckAnnotations(ctx context.Context, id int64) ([]Annotation, error)`; the fake's
  `FakeCheckAnnotations(id int64, as []Annotation, err error)`.

- [ ] **Step 1: Write the failing test**

```go
// CD12: a failing check's annotations are what the revision brief quotes, and a merge App that cannot read them
// says so instead of failing the pass.
func TestCheckAnnotations(t *testing.T) {
	srv := ghFake(t, map[string]string{
		"/repos/o/r/check-runs/9001/annotations": `{"annotations":[{"path":"docs/install.md","start_line":14,"annotation_level":"failure","message":"dead link"}]}`,
	})
	got, err := srv.CheckAnnotations(t.Context(), 9001)
	if err != nil || len(got) != 1 || got[0].Path != "docs/install.md" || got[0].StartLine != 14 {
		t.Fatalf("%+v %v", got, err)
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/factory/forge/ -run TestCheckAnnotations -count=1`
Expected: FAIL (`CheckAnnotations` undefined).

- [ ] **Step 3: The read**

`github.go`: one REST `GET /repos/{owner}/{repo}/check-runs/{id}/annotations`, the package's existing `wrap`
and error conventions, at most 50 annotations (one page), `Message` bounded to 500 runes. `absent.go`:
`func (Absent) CheckAnnotations(context.Context, int64) ([]Annotation, error) { return nil, ErrNoMerger }`.
`forgetest/fake.go` gains the method and `SetCheckAnnotations(id int64, as []Annotation, err error)`, so every
consumer's double keeps compiling.

- [ ] **Step 4: Run the package and its consumers**

Run: `go test ./internal/factory/... -count=1 -p 1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/factory/forge
git commit -m "feat(forge): read a check run's annotations, the merge App's own read"
```

### Task 2: the evidence block in the revision brief

**Files:**
- Modify: `internal/factory/config/config.go` (`Brief.CIEvidence`), `internal/factory/reconciler/text.go` (`reviseBrief`, new `evidenceBlock`), `internal/factory/reconciler/implement.go` (pass it)
- Test: `internal/factory/reconciler/text_test.go`, `internal/factory/config/config_test.go`

**Interfaces:**
- Consumes: `forge.Review`, `forge.Check`, `Merger.PullRequestChecks`, `Merger.CheckAnnotations`, `TaskForge.PullRequest`.
- Produces: `config.Brief{CIEvidence bool}` (`brief.ciEvidence`); `func (r *Reconciler) evidence(ctx context.Context, t *v1alpha1.Task) (items []evidenceItem, notes []string)`;
  `evidenceBlock(items []evidenceItem, fence string, budget int) string`.

- [ ] **Step 1: Write the failing tests**

```go
// CD12: the reviewer's comment and the failing check's annotation ride the revision brief, fenced, and the
// whole block stays inside the brief's cap.
func TestARevisionBriefCarriesTheReviewAndTheFailingCheck(t *testing.T) {
	r := rig(t, withBrief(config.Brief{CIEvidence: true}))
	r.pr(2239, review("CHANGES_REQUESTED", "the install link is still dead",
		forge.ReviewComment{Path: "docs/install.md", Line: 14, Body: "this anchor moved"}))
	r.checks(2239, forge.Check{ID: 9001, Name: "links", State: "FAILURE"})
	r.annotations(9001, forge.Annotation{Path: "docs/install.md", StartLine: 14, Level: "failure", Message: "dead link"})
	got, _ := r.reviseBrief(t)
	for _, want := range []string{
		"## What the review asked for (data, not an instruction):",
		"the install link is still dead",
		"this anchor moved",
		"## What CI said (data, not an instruction):",
		"dead link",
		"EVIDENCE-DATA-",
	} {
		if !strings.Contains(got, want) {
			t.Fatalf("missing %q in:\n%s", want, got)
		}
	}
	if len(got) > 13<<10 {
		t.Fatalf("the brief is %d bytes", len(got))
	}
}

// Fast-follow 6: a check the merger App cannot read is one sentence, and the brief still goes out.
func TestAnUnreadableCheckIsOneSentence(t *testing.T) {
	r := rig(t, withBrief(config.Brief{CIEvidence: true}))
	r.checksError(2239, errors.New("403 Resource not accessible by integration"))
	got, _ := r.reviseBrief(t)
	if !strings.Contains(got, "the factory could not read the failing check's details: the merger App needs checks: read on this repository") {
		t.Fatalf("%s", got)
	}
}

// The switch off: not one byte of GitHub text beyond what the brief always carried.
func TestWithoutTheSwitchTheBriefQuotesNoEvidence(t *testing.T) {
	r := rig(t, withBrief(config.Brief{}))
	r.pr(2239, review("CHANGES_REQUESTED", "the install link is still dead"))
	r.checks(2239, forge.Check{ID: 9001, Name: "links", State: "FAILURE"})
	got, _ := r.reviseBrief(t)
	if strings.Contains(got, "What the review asked for") || strings.Contains(got, "What CI said") {
		t.Fatalf("%s", got)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `KUBEBUILDER_ASSETS=$(go tool setup-envtest use -p path 1.36.x) go test ./internal/factory/reconciler/ -run 'TestARevisionBriefCarries|TestAnUnreadableCheck|TestWithoutTheSwitchTheBrief' -count=1 -p 1`
Expected: FAIL (`Brief` undefined).

- [ ] **Step 3: The block**

```go
// evidenceItem is one quoted string, with where it came from: all of it is GitHub's or a reviewer's, so it is
// data and never an instruction (CD12, the untrusted header).
type evidenceItem struct{ source, where, text string }

// evidence is what a revision brief quotes from GitHub: the open change requests' bodies and their comments,
// and the failing checks' annotations. Each source failing yields one note, never a lost brief.
func (r *Reconciler) evidence(ctx context.Context, t *v1alpha1.Task) (items []evidenceItem, notes []string)
```

`evidenceBlock` writes the two headings above, `clean()`s every string (text.go's untrusted sanitiser), puts
each in the block's fence `EVIDENCE-DATA-<nonce>`, cuts the whole to `min(4<<10, budget)` with `cut` on a rune
boundary, and appends the notes as plain sentences. `reviseBrief` calls it last, inside `reviseCap`, and before
`queuedBlock` so a queue never loses a message to evidence.

- [ ] **Step 4: Run the suites**

Run: `KUBEBUILDER_ASSETS=$(go tool setup-envtest use -p path 1.36.x) go test ./internal/factory/... -count=1 -p 1 && task lint`
Expected: PASS, 0 issues.

- [ ] **Step 5: Commit**

```bash
git add internal/factory
git commit -m "feat(factory): a revision brief carries the review and the failing check, fenced and bounded"
```

### Task 3: a failure you can act on — `Cause`, `Fix`, and the brief that renders it

**Files:**
- Create: `internal/summary/fix.go`, `internal/summary/fix_test.go`, `internal/roomview/testdata/brief/permission-failure.{json,md}`, `internal/roomview/testdata/brief/egress-failure.{json,md}`
- Modify: `internal/roomview/brief.go` (the `Fix:` line), `internal/roomview/brief_test.go` (the golden list), `internal/humanapi/brief.go` (fill `Cause`)
- Test: `internal/summary/fix_test.go`, `internal/roomview/brief_test.go`, `internal/humanapi/brief_test.go`

**Interfaces:**
- Produces: `func Cause(f *envelope.TaskFacts, notes []Note) (string, bool)` with the codes
  `app_permission`, `check_unreadable`, `ci_log_egress`; `func Fix(cause string) string`; the brief's `Cause`
  field filled by `Cause` in `humanapi`'s handler.

- [ ] **Step 1: Write the failing tests**

```go
// Fast-follow 6: the three failures the platform meets most, from what the room already holds.
func TestCause(t *testing.T) {
	for _, c := range []struct {
		name  string
		facts *envelope.TaskFacts
		notes []summary.Note
		want  string
	}{
		{"a check that never reported", &envelope.TaskFacts{Phase: "AwaitingCI", Reason: "ci_wait_expired"}, nil, "check_unreadable"},
		{"a log outside the egress policy", &envelope.TaskFacts{Phase: "AwaitingHuman"},
			[]summary.Note{{Text: "the CI log is not readable from the sandbox: do not try to fetch it"}}, "ci_log_egress"},
		{"an App missing a permission", &envelope.TaskFacts{Phase: "Escalated", Reason: "agent_error"},
			[]summary.Note{{Text: "gh: Resource not accessible by integration (HTTP 403)"}}, "app_permission"},
		{"nothing to say", &envelope.TaskFacts{Phase: "AwaitingHuman"}, nil, ""},
	} {
		got, _ := summary.Cause(c.facts, c.notes)
		if got != c.want {
			t.Errorf("%s: %q", c.name, got)
		}
	}
}

// Each cause has one fix, and it names the file or the host the person must change.
func TestFix(t *testing.T) {
	for cause, want := range map[string]string{
		"app_permission":   "the factory App is missing a permission on this repository: read the 403's scope in the run's note and grant it",
		"check_unreadable": "the factory cannot read that check: `.github/agent-factory.yml`'s `merge.checks` must name a check the App may read",
		"ci_log_egress":    "the CI log's host is outside the factory's egress policy: quote the failing check's annotations instead, or add the host",
	} {
		if got := summary.Fix(cause); got != want {
			t.Errorf("%s: %q", cause, got)
		}
	}
}
```

and in `internal/roomview/brief_test.go` the golden list becomes
`{"normal", "no-cursor", "hostile", "permission-failure", "egress-failure"}`, with the two new pairs asserting
one `Fix:` line each; `internal/humanapi/brief_test.go` asserts the route's text for a room whose last note is
the 403 carries the same line.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/summary/ -run 'TestCause|TestFix' -count=1; go test ./internal/roomview/ -run TestBriefGoldens -count=1`
Expected: FAIL at compile (`Cause`/`Fix` undefined); the two goldens are missing.

- [ ] **Step 3: The table, and the line**

`fix.go`: the three codes, `Cause` with the three exact rules above (the note strings are the ones
`images/maku-harness/agent_run.py`'s `LOG_UNREADABLE` and `gh`'s own 403 write), and `Fix`. The brief prints
`Fix: <sentence>` right after `Blocked on:`, escaped as prose (it is the broker's own words, so `text` not
`quoted`). `internal/humanapi/brief.go`'s handler sets `in.Cause` from `summary.Cause(facts, foldNotes)` — the
fold's notes are already in hand there, so nothing new is read.

- [ ] **Step 4: Run the suites**

Run: `go test ./internal/summary/ ./internal/roomview/ ./internal/humanapi/ -count=1`
Expected: PASS, the two new goldens byte-exact.

- [ ] **Step 5: Commit**

```bash
git add internal/summary internal/roomview internal/humanapi
git commit -m "feat(summary): a permission, configuration or egress failure names its fix in the brief"
```

### Task 4: PR 7

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/brief-evidence
gh pr create --title "feat(factory): brief.ciEvidence and the three failures that name their fix" \
  --body "CD12, fast-follow 6. Evidence is fenced, bounded and switched; an unreadable source is one sentence; the resume brief's Fix line comes from the room's own notes. Evidence: task check exit 0."
```

---

## PR 8 — `feat/meaningful-signals`: the notification table, as data

CD11's first half, and the only thing this plan says about Slack: which transitions are news. No message, no
button, no channel, and no change to the vocabulary — that type is the approval design's.

### Task 1: `webhook.Meaningful`

**Files:**
- Create: `internal/webhook/meaningful.go`, `internal/webhook/meaningful_test.go`, `internal/webhook/testdata/meaningful.json`
- Modify: `docs/slack.md` (the App's list and its count)

**Interfaces:**
- Produces: `func Meaningful(t string) bool` — true for exactly the nine transitions a person is told about;
  `func Notify() []string` — the same list, sorted, for a subscriber's `events:` declaration.

- [ ] **Step 1: Write the golden and the failing test**

`testdata/meaningful.json`:

```json
{
  "room.task_triaged": true,
  "room.run_started": false,
  "room.waiting_for_human": true,
  "room.pr_opened": true,
  "room.verdict_posted": true,
  "room.merged": true,
  "room.reverted": true,
  "room.budget_reached": true,
  "room.ended": true,
  "room.task_received": false,
  "room.run_ended": false,
  "room.monitor_verdict": false,
  "room.approval_closed": true
}
```

```go
// CD11: a run starting is not news; a review request, a red check and a hand-off are. The table answers for
// every type the vocabulary names, and for room.approval_closed before that design lands its type (offline
// proof: the count test), which is the one entry this file may name ahead of the vocabulary.
func TestMeaningful(t *testing.T) {
	want := loadMeaningful(t)
	for typ := range want {
		known := slices.Contains(webhook.Types(), typ)
		if !known && typ != "room.approval_closed" {
			t.Fatalf("%s is neither in the vocabulary nor the one seam ahead of it", typ)
		}
		if got := webhook.Meaningful(typ); got != want[typ] {
			t.Errorf("%s: %v", typ, got)
		}
	}
	for _, typ := range webhook.Types() {
		if _, listed := want[typ]; !listed {
			t.Errorf("the table is silent about %s", typ)
		}
	}
	if webhook.Meaningful("room.run_started") || !webhook.Meaningful("room.waiting_for_human") {
		t.Fatal("the table's two anchors moved")
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/webhook/ -run TestMeaningful -count=1`
Expected: FAIL (`Meaningful` undefined).

- [ ] **Step 3: The table, and the App's documented list**

`meaningful.go`: one `var notify = map[string]bool{…}` with the nine `true`s and the four `false`s written out
(naming a type `false` is a decision, not an omission), `Meaningful` defaulting to `false` for an unknown type
(an unlisted transition is not news), `Notify` returning the sorted `true`s.

`docs/slack.md`: the `events` example at line 76 drops `room.run_started` (eight entries), and the sentence at
line 83 becomes "`events` are the eight above, by their full names: the broker refuses a short one. The App
posts no line for `room.run_started`; it ignores `room.task_received` and `room.run_ended`." Add one sentence:
"`room.approval_closed` joins this list when the approval design releases its type." The document describes
the rule; the deployment's own list is ai-native-ref's (PR 10).

- [ ] **Step 4: Run the package**

Run: `go test ./internal/webhook/ -count=1 && task docs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/webhook docs/slack.md
git commit -m "feat(webhook): the notification table, nine of the thirteen transitions"
```

### Task 2: PR 8

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task check`
Expected: exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/meaningful-signals
gh pr create --title "feat(webhook): which transitions are news, as one table" \
  --body "CD11. The Slack proposal renderer consumes this table; this PR posts nothing and adds no webhook type — room.approval_closed stays the approval design's change. Evidence: task check exit 0."
```

---

## PR 9 — `feat/measured-clients`: capabilities from the client's own initialize

Fast-follow 4: what a coding client declared is recorded when it declared it, and `maku doctor` reports it.

### Task 1: record what `initialize` said

**Files:**
- Create: `internal/maku/capabilities.go`, `internal/maku/capabilities_test.go`
- Modify: `internal/maku/mcp.go` (the `initialize` branch), `internal/maku/config.go` (the file's directory)
- Test: `internal/maku/capabilities_test.go`, `internal/maku/mcp_test.go`

**Interfaces:**
- Produces: `type Caps struct{ Client, Version, Protocol string; Forms, URLs, Roots, Prompts bool; At time.Time }`;
  `type CapsStore struct{ Path string }` with `Put(Caps) error` and `Get(client string) (Caps, bool)`;
  `CapsPath(dir string) string` (`<dir>/capabilities.json`, the same directory as `config.json`).

- [ ] **Step 1: Write the failing tests**

```go
// Fast-follow 4: the relay records the client's own capabilities under its name and version.
func TestInitializeRecordsTheClientsCapabilities(t *testing.T) {
	r := relayAt(t, t.TempDir()) // the file's helper: a relay whose Dir is that temp dir
	r.initialize(`{"protocolVersion":"2025-06-18","capabilities":{"elicitation":{},"roots":{},"prompts":{}},
		"clientInfo":{"name":"claude-code","version":"2.0.1"}}`)
	got, ok := (maku.CapsStore{Path: maku.CapsPath(r.Dir)}).Get("claude-code")
	if !ok || !got.Forms || !got.Roots || !got.Prompts || got.Version != "2.0.1" || got.Protocol != "2025-06-18" {
		t.Fatalf("%+v %v", got, ok)
	}
}

// A client that declares nothing is recorded as declaring nothing: never left unmeasured once seen.
func TestAClientThatDeclaresNothing(t *testing.T) {
	r := relayAt(t, t.TempDir())
	r.initialize(`{"protocolVersion":"2025-06-18","clientInfo":{"name":"codex","version":"0.9.0"}}`)
	got, ok := (maku.CapsStore{Path: maku.CapsPath(r.Dir)}).Get("codex")
	if !ok || got.Forms || got.URLs || got.Roots || got.Prompts {
		t.Fatalf("%+v %v", got, ok)
	}
}

// The file keeps one entry per client: a second session replaces the first.
func TestCapsStoreKeepsOneEntryPerClient(t *testing.T) {
	store := maku.CapsStore{Path: maku.CapsPath(t.TempDir())}
	if err := store.Put(maku.Caps{Client: "claude-code", Version: "2.0.0"}); err != nil {
		t.Fatal(err)
	}
	if err := store.Put(maku.Caps{Client: "claude-code", Version: "2.0.1", Forms: true}); err != nil {
		t.Fatal(err)
	}
	got, ok := store.Get("claude-code")
	if !ok || got.Version != "2.0.1" || !got.Forms {
		t.Fatalf("%+v %v", got, ok)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/maku/ -run 'TestInitializeRecords|TestAClientThatDeclaresNothing|TestCapsStoreKeepsOneEntry' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The record**

`capabilities.go`: the struct, `CapsPath`, `Put` (load, replace the entry keyed by `Client`, bump `At`, write
0600 atomically through `SaveJSON`), `Get`. `mcp.go`'s `initialize` branch already parses `capabilities`; it
gains `Prompts json.RawMessage` and `ClientInfo{Name, Version string}`, and after the relay answers, writes one
`Caps` — a write error is logged and never fails the initialize (the relay's job is the conversation).

- [ ] **Step 4: Run the package**

Run: `go test ./internal/maku/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/maku
git commit -m "feat(maku): the relay records what each client declared at initialize"
```

### Task 2: `maku doctor --client`

**Files:**
- Modify: `internal/maku/doctor.go`, `internal/app/maku.go` (the flag)
- Test: `internal/maku/doctor_test.go`, `internal/app/maku_test.go`

**Interfaces:**
- Consumes: `CapsStore` (Task 1).
- Produces: `maku doctor --client <name>` prints one line:
  `factory capabilities (claude-code 2.0.1, MCP 2025-06-18): forms yes · url mode no · roots yes · prompts yes — measured 2026-11-04`
  or `factory capabilities (codex): not measured yet — run a session and ask again`; without `--client`, one
  line per measured client, bounded to five.

- [ ] **Step 1: Write the failing test**

```go
// Fast-follow 4: doctor reports what the client declared, and never "unconfirmed" about one it has seen.
func TestDoctorReportsTheMeasuredClient(t *testing.T) {
	dir := t.TempDir()
	store := maku.CapsStore{Path: maku.CapsPath(dir)}
	if err := store.Put(maku.Caps{Client: "claude-code", Version: "2.0.1", Protocol: "2025-06-18",
		Forms: true, Roots: true, Prompts: true, At: time.Date(2026, 11, 4, 0, 0, 0, 0, time.UTC)}); err != nil {
		t.Fatal(err)
	}
	var out strings.Builder
	d := maku.Doctor{Config: maku.Config{URL: "https://rooms.example", Issuer: "https://id.example"},
		TokenPath: filepath.Join(dir, "token.json"), Caps: store, Client: "claude-code"}
	if err := d.Run(t.Context(), &out); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out.String(), "unconfirmed") || !strings.Contains(out.String(), "forms yes") {
		t.Fatalf("%s", out.String())
	}
}

// A client never seen says so once, and says what to do.
func TestDoctorSaysWhenAClientIsNotMeasured(t *testing.T) {
	dir := t.TempDir()
	var out strings.Builder
	d := maku.Doctor{Config: maku.Config{URL: "https://rooms.example", Issuer: "https://id.example"},
		TokenPath: filepath.Join(dir, "token.json"), Caps: maku.CapsStore{Path: maku.CapsPath(dir)}, Client: "codex"}
	if err := d.Run(t.Context(), &out); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "not measured yet") {
		t.Fatalf("%s", out.String())
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/maku/ -run 'TestDoctorReportsTheMeasuredClient|TestDoctorSaysWhenAClientIsNotMeasured' -count=1`
Expected: FAIL (`Doctor` has no `Caps`/`Client` fields).

- [ ] **Step 3: The line**

`Doctor` gains `Caps CapsStore` and `Client string`; its `Run` gains one `report` call in the fixed order
(after `skill`, before `github`); `internal/app/maku.go`'s doctor branch parses `--client` and fills both. The
line is emitted for every run: without `--client`, it names every measured entry (bounded to five), which is
what makes the reference page's table fillable.

- [ ] **Step 4: Run the suites**

Run: `go test ./internal/maku/ ./internal/app/ -count=1 && task lint`
Expected: PASS, 0 issues.

- [ ] **Step 5: Commit**

```bash
git add internal/maku internal/app
git commit -m "feat(maku): maku doctor reports what each client actually declared"
```

### Task 3: PR 9

- [ ] **Step 1: Everything green, push, open the PR**

Run: `task check`
Expected: exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/measured-clients
gh pr create --title "feat(maku): measured client capabilities, from the client's own initialize" \
  --body "Fast-follow 4. The relay records; doctor reports; no cell needs 'unconfirmed' for a client the platform has run. Evidence: task check exit 0."
```

### Task 4: release

- [ ] **Step 1: Tag the next minor**

After PR 9 merges, tag the next minor on `main` as the previous releases were, and note the version: PR 10
pins it. Tell a peer session before the tag if one holds a Maku freeze.

---

## PR 10 — ai-native-ref `feat/devex-pin-and-switches`: the release, the switches, one transition dropped

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml` (every `ghcr.io/smana/maku-*` tag, and the
  factory's config block), `infrastructure/base/room-broker/config.yaml` (`human.needs`),
  `infrastructure/gcp-0/room-broker/config.yaml` (`webhooks[slack-app].events`)
- Test: `task check` (the bundle render, the host's `validate-manifests.sh`, the webhook-egress test)

**Interfaces:**
- Consumes: the release from PR 9's tag.
- Produces: `human.needs: {enabled: true}` on the broker; `caps: {…, preferRevisions: true}`,
  `facts: {finalSpend: true}`, `brief: {ciEvidence: true}` on the factory; the Slack App's subscription without
  `room.run_started`.

- [ ] **Step 1: Pin the release**

In `helm-values-configmap.yaml`, replace the tag on each `ghcr.io/smana/maku-*` image with the release's
`vX.Y.Z@sha256:…` (the digest from the release's manifest list), keeping the `# maku vX.Y.Z, the chart's
appVersion.` comment above each. Do not touch the `renovate:` lines: renovate owns the next bump.

- [ ] **Step 2: Declare the switches**

Broker, under `human:` beside `mcp:`:

```yaml
  # needs/v1 (CD21, CD28): one list, read by /api/needs and by the CLI. Read-only, so it ships on.
  needs:
    enabled: true
```

Factory, in `helm-values-configmap.yaml`'s config block: the three factory keys go in their own sections, and
`preferRevisions` goes inside the existing `caps:` mapping rather than beside it —

```yaml
      # CD22: a revision of another task runs before new intake. One wait reason, no reservation; the review
      # WIP cap and the run slot are still checked first. Added in the release this PR pins, because an older
      # decoder refuses the key.
      caps: {activeTasks: 3, concurrentRuns: 4, tasksPerDay: 20, maxTextBytes: 14336, awaitingHumanWIP: 5, preferRevisions: true}
      # CD23: one final spend fact after the settle window, so the card's dollars stop moving.
      facts: {finalSpend: true}
      # CD12: the reviewer's comments and the failing check's annotations in a revision brief.
      brief: {ciEvidence: true}
```

- [ ] **Step 3: Drop `room.run_started` from the live subscription**

In `infrastructure/gcp-0/room-broker/config.yaml`, the `webhooks[slack-app].events` list loses
`room.run_started`: a run starting is not news (CD11, and Maku's `docs/slack.md` now says so). Leave every
other entry as it is, and do not add `room.approval_closed`: that type arrives with the approval design, which
edits this same list.

Then run `python3 scripts/ci/gen-webhook-egress.py` (no `--write`): the generated network policies key on the
subscribers' hosts and networks, not on event names, so the expected output is "no drift". Commit nothing from
it. A `webhooks` change applies only at a broker restart, so the roll-out note on the PR says the broker is
restarted once the release is pinned.

- [ ] **Step 4: Check**

Run: `task check`
Expected: exit 0, including `scripts/ci/tests/test-gen-webhook-egress.py` and the room-broker webhook-egress
test.

- [ ] **Step 5: Commit and open the PR**

```bash
git add tooling/base/agent-factory infrastructure/base/room-broker infrastructure/gcp-0/room-broker
git commit -m "feat(factory): pin the release that reads needs, revision-first, the final spend and the brief's evidence"
git fetch origin && git rebase origin/main && git push -u origin feat/devex-pin-and-switches
gh pr create --title "feat(factory): the dev-experience release, its four switches, and one transition dropped" \
  --body "Pins Maku vX.Y.Z; declares human.needs.enabled, caps.preferRevisions, facts.finalSpend and brief.ciEvidence; drops room.run_started from the Slack subscription (CD11). The broker is restarted after the pin. Evidence: task check exit 0."
```

---

## PR 11 — ai-native-ref `feat/devex-docs`: the reader's side

**Files:**
- Modify: `website/content/docs/reference/commands.md`,
  `website/content/docs/use/guide/when-the-factory-needs-you.md`,
  `website/content/docs/use/guide/terminal-and-coding-agent.md`
- Test: `task docs` and `task check`

**Interfaces:**
- Consumes: the surfaces PRs 1, 2, 3, 4 and 9 shipped.
- Produces: the commands, the inbox chapter and the client table, written per [`docs-style.md`](../../docs-style.md):
  no cluster name, no session date, no proof ID; state stays on the status page.

- [ ] **Step 1: `reference/commands.md`**

In the CLI block, after `maku rooms --needs-me`:

```bash
maku needs                                    # everything that needs you, across rooms, in one order
maku needs --since 2026-11-04T18:20:00Z        # only what appeared since then; without --since, your last call
```

Replace the sentence "A task waiting for your merge is not listed under `--needs-me`
([maku#51](https://github.com/Smana/maku/issues/51))" with the one-line pointer to the guide's inbox section. In the tool table add
`needs_list` ("everything that needs you, with its one action and link, and a `since` cursor") and `room_brief`
("come back to a room: what it needs, the plan, what changed, the blocker and the next step"); in the prompt
table add `resume` and reword `inbox`. In the client table, add a `Measured` column
(`<client> <version>, <month year>`), fill every client `maku doctor` has reported, and keep `unconfirmed` only
in the cells of a client nobody has run.

- [ ] **Step 2: `use/guide/when-the-factory-needs-you.md`**

Add a section "One list, wherever you look" before "The hand-off": what the four surfaces show (the same items,
the same order), that each item carries one action and one link, and that a proposed split appears as a plan
confirmation whose action is the `/factory split` comment. In the hand-off section, replace the paragraph that
sends a `human_commit_in_pr` reader straight to `gh pr merge --admin` with two sentences: the item says *approve
the current commit* when an approval merges the pull request, and says *a repository admin merges it* — with the
reason, that a person pushed a commit the factory cannot vouch for — only in that case.

- [ ] **Step 3: `use/guide/terminal-and-coding-agent.md`**

Add "Come back to a task": `maku needs`, then `maku status <room>`'s brief head, then the `resume` prompt in a
coding agent — what the brief holds (asked, plan, changed since, blocked on, next), and that a permission,
configuration or egress failure names its fix.

- [ ] **Step 4: Check**

Run: `task docs && task check`
Expected: both exit 0 (the reader-first rules, every relref and anchor, the link check).

- [ ] **Step 5: Commit and open the PR**

```bash
git add website/content/docs
git commit -m "docs(use): one needs list, the resume brief, and the clients we have measured"
git fetch origin && git rebase origin/main && git push -u origin feat/devex-docs
gh pr create --title "docs(use): the inbox, the resume brief and the measured clients" \
  --body "Reference and the two guides. State stays on the status page. Evidence: task docs exit 0, task check exit 0."
```

---

## Live proof — one repository, one session per surface

**Owner go is required before any live action.** Nothing in this section runs, and no switch is turned on in a
shared cluster, until the owner says so in the session. Every step's evidence goes into the results file PR 12
adds; a step that fails is a finding with its own row, never a silent retry.

The repository is `Smana/ai-native-ref`; the session's cluster is the one PR 10 deployed.

### Live 1: cross-surface needs, the split proposal, and a second maintainer

- [ ] **Step 1: Ask the owner**

Ask, in one message: which cluster, which room, and whether to use an existing maintainer account other than the
one that filed the task. Record the answer in the results file's header. Do not proceed without it.

- [ ] **Step 2: Cross-surface identical needs (the spec's live proof 13)**

In one room waiting on you, read its needs four ways: `maku needs`; the coding agent's `needs_list`; the room
page's panel; `curl` on `/api/needs?room=<id>` with the CLI's token. Record the item keys from each.

Expected: the same keys, in the same order, with the same ids.

- [ ] **Step 3: `split_proposed` in all four (the spec's live proof 14)**

Take a task at `Escalated` with reason `split_proposed` (the splitter runbook produces one) and repeat step 2.
Expected: a `plan_confirmation` item in all four, whose action is the `/factory split` comment and whose link is
the issue.

- [ ] **Step 4: a non-owner maintainer's merge (offline proof 6, live half)**

With the second maintainer's token, `maku needs`. Expected: the `merge` item for the pull request, which the
task's owner also sees, and which the second maintainer's `maku rooms --needs-me` now lists.

### Live 2: resume after a cursor, revision preference, the final cost, and the evidence

- [ ] **Step 1: Resume after a 10-minute-old cursor (the spec's live proof 5)**

Wait ten minutes with no call, then `maku status <room>` in one go. Expected: the brief's `Changed since` list
matches `maku changes <room>` from the same cursor, line for line.

- [ ] **Step 2: Revision preference (offline proof 12, live half)**

Queue a first run of another task while a revision is waiting for the slot. Expected: the first run's row reads
`waiting_revision_first` for one slot-time, the revision starts, and `maku_revision_deferred_total` is non-zero.
Record both rows' reason codes and the metric's value.

- [ ] **Step 3: the final cost (offline proof 13, live half)**

When a task ends, read its card twice: immediately, and after five minutes. Expected: `spend settling` first,
then one figure that matches the ledger's settled total for the run and does not move again;
`maku_task_spend_final_seconds` is under the settle window plus the margin.

- [ ] **Step 4: the evidence and the fix (offline proof 14, live half)**

After a reviewer requests changes, read the revision run's brief in the room. Expected: the review's comment and
the failing check's annotation, fenced and bounded; and, in the resume brief, the `Fix:` line for the cause the
platform actually met.

### Live 3: the measured clients

- [ ] **Step 1: Measure each client the platform runs**

For each of Claude Code and OpenCode, run one session against the broker, then `maku doctor --client <name>`.
Expected: forms, url mode, roots, prompts and the protocol revision, with the measurement's date.

- [ ] **Step 2: Feed PR 11's table**

Copy the two measured lines into the branch PR 11 opens (or a follow-up commit on it). No cell that has a
measurement keeps `unconfirmed`.

---

## PR 12 — ai-native-ref `feat/devex-status`: state, the record, and the proof

**Files:**
- Modify: `website/content/docs/status.md`, `website/content/docs/decisions/_index.md`
- Create: `website/content/docs/decisions/0061-conversational-feedback.md`,
  `docs/runbooks/agent-factory/results-<cluster>-<date>.md`
- Test: `task check` (the link check and the doc-path check)

**Interfaces:**
- Consumes: Live 1–3's evidence.
- Produces: the status rows, the ADR, and the results file the status rows link to.

- [ ] **Step 1: The results file**

`docs/runbooks/agent-factory/results-<cluster>-<date>.md`, in the register of the existing `results-*.md`: the
header (cluster, `integration/agent-factory` revision, the release pinned), a verdict sentence, a findings table
(`# | finding | where it shows | severity | status`), then one section per Live 1–3 step with its command and
its observed output, `[OWNER]` where the step needed the owner.

- [ ] **Step 2: The ADR**

`decisions/0061-conversational-feedback.md`: front matter as `0059`'s (`title`, `linkTitle: "0061 · …"`,
`weight: 610`, `description`, `lastVerified`), then `**Status**: Accepted`, the date, the deciders, and
`**Related**` linking this design, ADR-0059 and ADR-0049. The body records **this subset's** decisions and
nothing of the planner's: CD10 (one inbox, one order), CD11 (meaningful transitions, a deterministic brief),
CD12 (review and CI feedback in the same room, revisions preferred), CD21 (one `needs/v1` function), CD22
(`caps.preferRevisions`, caps still bind), CD23 (the final spend), CD26 (standing read from GitHub), CD28 (two
front doors, one closed sponsored schema) — and one line saying the intake half is the same design's ADR-0060.
If `0060` or `0061` is taken when this runs, renumber and link both from the design.

- [ ] **Step 3: `_index.md` and `status.md`**

`_index.md`: one row, `| [0061]({{< relref "/docs/decisions/0061-conversational-feedback.md" >}}) | One inbox
across four surfaces, a deterministic resume brief, revisions before new intake, and dollars that settle |
Accepted | 2026-11-05 |`.

`status.md`: update the `lastVerified` line; add to the v3 group in the mermaid graph a node
`needs["One inbox and a resume brief"]`; and in the capability table add three rows, each naming the cluster it
was proven on and linking the results file — `needs/v1 across four surfaces`, `The resume brief`,
`Revisions before new intake, and final dollars` — plus, under known limitations, the two this proof leaves: an
approval cannot be decided from a thread (the approval design's), and a room whose facts cannot be read
contributes no item.

- [ ] **Step 4: Check**

Run: `task docs && task check`
Expected: both exit 0, the link check fetching every absolute host link.

- [ ] **Step 5: Commit and open the PR**

```bash
git add website/content/docs docs/runbooks/agent-factory
git commit -m "docs(status): the inbox, the resume brief and the settled dollars, with their proof"
git fetch origin && git rebase origin/main && git push -u origin feat/devex-status
gh pr create --title "docs(status): needs/v1, the resume brief and the final spend, recorded" \
  --body "ADR-0061, the status rows and the live proof's results file. Evidence: task docs exit 0, task check exit 0."
```

---

## Self-review

**1. Spec coverage (this subset).**

| Spec item | Task |
|---|---|
| One `needs/v1` derivation; `summary.View` and `humanapi.needs` become one (CD21, G4) | PR 1 T1, T2 |
| The split hole (`split_proposed`, no PR) yields a `plan_confirmation` | PR 1 T1 (fixture 1), T2 |
| The merge hole: standing read from GitHub, not the room's owner (CD26) | PR 1 T1 (fixtures 2, 3), T2 |
| The merge need's prose and `Approve` come from `waiting.go`'s one table (AM3) | PR 1 T1 (`MergeNeed`, fixture 3) |
| `room_summary` and `maku status` keep the merge and review needs (the standing reaches `View`) | PR 1 T2 (`standing`, `summaryOf`) |
| A `review` need and a `failed_check` need, which no clause carried | PR 1 T1 (fixtures 4, 5) |
| A hold judged by the right to release it (`policy.StartRun`) | PR 1 T1 (fixture 8) |
| The fixed order and the documented tie-breaks | PR 1 T1 (`Ordered`, `TestNeedsOrder`) |
| Approve-the-current-commit, never admin-merge, for an approve-to-merge task (fast-follow 1) | PR 2 T1 |
| Admin merge only where it is the only path, with the reason, in card, step and issue comment | PR 2 T1 |
| `/api/needs`, human token, `since` cursor, read-only, behind `human.needs.enabled` (CD28) | PR 3 T1 |
| `needs_list` on `/mcp`: human list and the closed sponsored list, both schemas closed (CD28) | PR 3 T2, T3 |
| The auth boundary, tested: sponsored token on `/api/needs`, a field outside the schema, the amended `sponsored_test.go` | PR 3 T3 |
| CLI and web read the same list | PR 3 T4, T5 |
| Deterministic, escaped resume brief (CD11, G6) | PR 4 T1 |
| The brief on both doors, and in `maku status` | PR 4 T2, T3 |
| The `resume` prompt and a one-call `inbox` | PR 4 T3 |
| `caps.preferRevisions`, `waiting_revision_first`, caps still bind (CD22) | PR 5 T1 |
| Final settled spend: one requeue, one re-price, one fact, unbucketed dollars (CD23) | PR 6 T1, T2 |
| The words before the number settles | PR 6 T3 |
| Review and CI evidence in a revision brief, untrusted and bounded (CD12, `brief.ciEvidence`) | PR 7 T1, T2 |
| A permission, configuration or egress failure with its fix (fast-follow 6) | PR 7 T3 |
| Meaningful transitions as data, and the App's documented list (CD11) | PR 8 T1 |
| Measured client capabilities (fast-follow 4) | PR 9 T1, T2 |
| The switches, the release they need, and the dropped transition | PR 10 |
| The reader's pages | PR 11 |
| The live proofs: cross-surface identical needs, `split_proposed`, non-owner merge, resume after a cursor, revision preference, final cost, evidence, measured clients | Live 1–3 |
| Status, the ADR, the results file | PR 12 |

**Deliberate deviations, recorded.**

- **Four fast-follows are pulled ahead into the increment.** The spec ships fast-follows 1, 2, 4 and 6 *after*
  the increment's live proof. This plan lands them as PRs 2, 6, 9 and 7, inside it, because each is a defect in
  a surface the increment's own proof reads — a card that says admin-merge, dollars that move after they are
  read, an "unconfirmed" cell the proof would have to explain, and a failure the brief would report without its
  fix. Fast-follows 3 (a reserved slot for revisions) and 5 (the Slack binding generator) stay out: neither is
  read by a proof here, and 5 is the sibling design's declaration work.
- **The resume brief's CI evidence** comes from the room's milestones and the cause table rather than fetched
  annotations, because the broker has no forge; the annotations ride the *revision* brief (PR 7 T2), which is
  where the factory holds them.
- **The notification table** names `room.approval_closed` ahead of the vocabulary, since that type is the
  approval design's to add; PR 8 T1's test pins exactly that seam, and PR 10 leaves the type out of the live
  subscription.

**2. Step scan.** Every "write the test" step carries the test's name and its assertions with the spec's exact
values; every "implement" step carries the signature and the file, and a body only where the signature and the
tests leave a choice (the derivation's clauses, the requeue arithmetic, the retention rule). No step says "handle
edge cases", "add tests for the above" or names a type no task defines. Two places leave a body to the
implementer on purpose: `roomview.Needs`' line format, which its test pins in words (`merge — a maintainer
approves PR #2239`) rather than in a golden, and `BriefIn.Cause`'s hook, which PR 7 fills and its own goldens
then pin.

**3. Type consistency (checked after the renumbering).** `NeedsIn`/`Caller`/`GitHubStanding`/`NeedAction`/
`NeedSource`/`Need.Key`/`Items`/`Ordered` (PR 1) are used verbatim in PR 3, PR 4 and the web's `NeedsPage`;
`Caller.CanRelease` is `policy.StartRun`, and no `CanQueue` remains; `MergeNeed`/`QuestionNeed`/`MergeHow(repo, n,
byApproval)` (PR 1) are what PR 2 corrects and what the card, `StepFor` and `narrate` read; `View`'s new
`GitHubStanding` parameter (PR 1) is filled by `Server.standing`, the same resolver `needsFor` uses;
`Approval.At` (PR 1) is what `since` filters on (PR 3); `PlanVersion`/`BriefIn`/`Brief` (PR 4) are the only shape
the brief has, and `BriefIn.Cause` is written only by PR 7; `config.Caps.PreferRevisions` (PR 5),
`config.Facts.FinalSpend` and `envelope.TaskFacts.SpendFinal` (PR 6), `config.Brief.CIEvidence` (PR 7) are
distinct keys in three sections of one file, and each PR adds its own; `Costs.Put` is the exported writer both
the tick and the test call, and `Costs.Get` the only reader; `summary.Cause`/`Fix` (PR 7) are what
`humanapi/brief.go` sets and the brief renders; `forge.Annotation`/`Merger.CheckAnnotations` (PR 7) are consumed
only by `evidence`; `webhook.Meaningful`/`Notify` (PR 8) are read by nothing yet, by design; `maku.Caps`/
`CapsStore` (PR 9) are what `Doctor`'s two new fields carry. The metric names are the exporter's:
`needs_list_total` → `maku_needs_list_total`, `needs_items` → `maku_needs_items` (`MakuName`'s `needs_` case;
`rooms_needs_*` would have been served as `maku_rooms_needs_*`),
`maku_revision_deferred_total` and `maku_task_spend_final_seconds` as the spec writes them.

**4. Review Focus.** Six lines, six tests, each in the task that owns the code: an unreadable room's facts (PR 3
T1), a need whose work moved (PR 1 T1), a malformed `since` (PR 3 T1), untrusted text in the brief's heading
(PR 4 T1), a neighbour stopped by a cap rather than a slot (PR 5 T1), and a terminal task with no run (PR 6 T2).
Two conditions the spec implies and the six-line limit leaves out are pinned anyway, in the task that owns them:
a client that never declares `clientInfo` (PR 9 T2, "not measured yet", which fails loud rather than silently)
and an App with no GitHub login (PR 1 T1's `reader` caller, which gets no merge need).

**5. Placeholders.** Test helpers are taken from or added to the files each task names, and none is invented
where an existing one will do. This plan expects these, extending the package's own suite:
`loadNeedsCases`, `cases[].in`, `cases[].wantKinds`, `cases[].want`, `allowedURL` (`internal/summary`);
`world`, `worldWithSplitAndMerge`, `getRows`, `getSummary`, `getJSON`, `get`, `brokenLogFor`, `setup`'s options
(`internal/humanapi`); `relay`, `fakeBroker`, `row`, `localCall`, `makuRig`, `promptText`, `call`, `toolNames`,
`rpc`, `rpcCode`, `viaRoomctl`, `bearer`, `withSponsored`, `sponsoredRooms` (`internal/maku`, `internal/humanapi`);
`loadBrief`, `loadMeaningful`, `relayAt`, `ghFake` (`internal/roomview`, `internal/webhook`, `internal/maku`,
`internal/factory/forge`); and, for the factory's, `rig` with the options `withCaps`, `withFacts`, `withBrief`,
plus its `task`, `queued`, `reason`, `ended`, `endedNoRun`, `reconcileOnce`, `reconcileAt`, `meterPrices`, `posted`,
`facts`, `pr`, `checks`, `checksError`, `annotations`, `reviseBrief` and the `review` builder
(`internal/factory/reconciler`). A helper marked with a comment in a test step is the one to add if the file
lacks it.

**6. Proportion.** Nine Maku PR sections, three ai-native-ref PR sections and one live-proof section for a
740-line spec: each task is a test and the signature it needs, and the largest single code block is the
`needs.go` type block, which is mostly the contract later PRs consume. No implementation transcript: no function
body appears for anything the signature plus the test determines, and the four bodies that do appear (the
derivation's clauses, the requeue, the retention rule, `standing`) are the four places where a reasonable
implementer would otherwise guess.
