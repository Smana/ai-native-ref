# Deciding `forge.push` from Slack — Implementation Plan (Maku PRs 1–4, release, ai-native-ref adoption)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A room's `forge.push` approval appears in the thread it was filed from as one Block Kit card whose Approve/Deny buttons decide it — for `forge.push` only, resolved to the linked human's room standing *and* repository write, under the store's existing single-decision fence and four-eyes — with the card inert after any close, and merging left exactly as it is: a review of the current head on GitHub.

**Architecture:** Four Maku pull requests, each merging on its own offline evidence, then one release, then two ai-native-ref pull requests (documentation and gates first, the switch-on last, behind an owner go). PR 1 adds the durable binding — `approvals.binding_branch`, the `approval_requested.branch` payload field, and the `bridgeapi` line that fills it from `run.Branch`. PR 2 adds the broker's one new route, `POST /api/slack/decisions`, behind `human.slackDecide`, and calls `store.Decide` unchanged. PR 3 adds the shared primitives the card and the conversational design both ride: `Slack.Update` (`chat.update`), a tagged `Metadata.EventPayload` whose draft wire bytes do not move, `webhook.Classes()`/`Decisions()`, the approval ids on `room.waiting_for_human`, and the new `room.approval_closed`. PR 4 adds the interactivity branch inside `POST /slack/events` (same door, same signature check, dispatched by content type), the card renderer, the post-or-update path, the ephemeral answer and the inert teardown. Every behaviour ships off: no `human.slackDecide`, no `approvals: true`, no card has a button, and the App answers the new path as nothing.

**Tech Stack:** Go 1.25 (controller-runtime, `pgx`/PostgreSQL 17, `atlas` migrations, `golang.org/x/time/rate`, OpenTelemetry metrics), Slack Web API (`chat.postMessage`, `chat.postEphemeral`, `chat.update`, `conversations.replies`), Slack Block Kit and interactivity payloads, `task` as the runner, Python 3 + `promtool` for the ai-native-ref gates.

**Spec:** [the Slack push-approval design](../specs/2026-11-05-v3x-slack-push-approval-design.md) — decisions D1–D15, the two owner decisions of 2026-11-05, §Contracts 1–7, §Security analysis, §Test matrix (27 rows), §Live proofs (L1–L8), §Documentation amendments. This plan lives in ai-native-ref and is copied to Maku's `docs/superpowers/plans/` by the first PR that executes it. *`maku/…` in the spec is the Maku repository at `4685672f`.*

## Global Constraints

- **Repositories.** Maku is `github.com/Smana/maku`; the review used `/tmp/opencode/maku-devex-read` at `4685672f0f40973286a121f83ea92dd3428b8120`. Set `MAKU` to the executor's checkout of `origin/main`; one worktree per PR: `git -C "$MAKU" worktree add "$MAKU-<topic>" -b <branch> origin/main`. Branches: PR 1 `feat/approval-binding`, PR 2 `feat/slack-decide-route`, PR 3 `feat/slack-card-primitives`, PR 4 `feat/slack-decide-cards`. Rebase onto a freshly fetched `origin/main` before every push. ai-native-ref work happens in this repository, on `feat/slack-push-approval-docs` (PR A) and `feat/slack-push-approval-switch-on` (PR B).
- **The evidence.** Maku: `task check` exits 0 (its `test` step needs a Docker daemon for the store's testcontainers, and envtest assets from `setup-envtest` 1.36.x are taken by `task test` itself); `task lint` reports 0 issues; after a new migration, `task migrations` (`atlas migrate validate`) passes because `atlas migrate hash --dir file://internal/store/migrations` rewrote `atlas.sum`; `task crd:check` and `task chart:check` are unaffected (no API type changes). ai-native-ref: `task check` exits 0 in this repository.
- **Conventions.** `// SPDX-License-Identifier: Apache-2.0` on every Maku `.go` file; doc comments on exported symbols, stating the ruling; a package's `// Package …` comment is its contract; interfaces belong to the consumer and stay minimal. Commits are conventional, in English, with no trailers; PR titles and descriptions in English.
- **Off by default, both switches (D14).** The broker's `human.slackDecide` unset ⇒ `POST /api/slack/decisions` is the mux's 404, exactly as `/mcp` is when `MCP` is false. The App's `channels.<id>.approvals` absent ⇒ false ⇒ today's text line and no button.
- **Verbatim values from the spec.**
  - D13: `slackDecidableClass = "forge.push"` — a constant, never config.
  - Route body cap 4 KiB; `Content-Type: application/json` required; one request per HTTP request, read through `http.MaxBytesReader`.
  - Rate limit: **10/min per `(team,user)` with a burst of 5**, per replica; over it, `429 rate_limited`.
  - Field shapes: `team` `^T[A-Z0-9]{2,20}$` and equal to the configured team; `user` `^[UW][A-Z0-9]{2,20}$`; `channel` `^[CG][A-Z0-9]{2,20}$`; `messageTS` `^[0-9]{1,12}\.[0-9]{1,8}$`; `approvalId` `^[0-9A-HJKMNP-TV-Z]{26}$`; `branch` `^agent/[a-z0-9][a-z0-9._/-]{0,100}$`; `decision` ∈ `approved`\|`denied`.
  - The decision draft: `Actor{Kind: human, ID: "human:"+sub}`, `Origin: client`, `OriginClient: "human:"+sub+":slack:"+approvalId`, `OriginSeq: 1` for `approved` and `2` for `denied`, empty reason.
  - Webhook tolerance stays 5 minutes; Slack's body cap stays 1 MiB; Slack answers the click within 3 s, and the worker gets `handleTimeout` (30 s).
  - `webhook.Types()` goes 12 → 13; `decision` ∈ `approved | denied | expired | superseded`.
  - Refusals are 200 with a closed code (`already_decided`, `approval_expired`, `not_linked`, `link_unverified`, `not_permitted`, `repository_permission`, `four_eyes`, `binding_mismatch`, `not_supported`, `not_found`, `sealed`), 400 `bad_request`, 401/403 for a wrong principal, 429 `rate_limited`, 503 `unavailable`.
- **Out of scope, and no task may add it:** merging (stays a GitHub review of the current head), any other approval class, reason text, answers to `needs_author`, steering, egress or capability widening, a second public path, a modal, a slash command, a DM, a commit SHA in the binding (D5, owner-signed-off on 2026-11-05), and `store.Decide`'s semantics (called unchanged, D7).
- **Owner gates.** No live cluster action — merging the switch-on PR, the Slack console change, or any proof below — happens before the owner's explicit go in Task 24. Tasks 1–23 are offline.

## Review Focus

The five input classes and failure modes this design implies but no test in the spec exercises. Each line's test is added to the task that owns the code, in that task's own step style.

1. **A press that arrives while every worker slot is taken.** A click is enqueued after the 200; when `enqueue` reports false (queue full, or draining) today's events path answers `503 busy` *and forgets the dedup id* so Slack's retry is handled. An interaction that keeps its dedup id on that path loses the click permanently, and the person's decision silently never happens. Owning task: 13.
2. **Two concurrent redeliveries of one press** (the same known race the events path documents: both can pass the in-memory `add` before either finishes). A person pressing once expects one decision and one answer line — never two broker calls that each append an event. Owning task: 14.
3. **`container.message_ts` and `message.ts` disagreeing, or one being absent.** The design says they agree; Slack's own payload does not promise it. A click must still name one message and one card lifetime rather than 400 or guess between two. Owning task: 13.
4. **A card drawn for a channel that stopped serving the room's repository** (config drift between the webhook and the click). The card must not be posted by a channel that no longer lists the repository, and a press from a channel whose `repositories` changed must still be decided by the broker's own standing — the App has no repository in the payload and must not invent one. Owning tasks: 14 (the press) and 15 (the card).
5. **A wait whose deadline already passed when the card is drawn** (a webhook redelivery after expiry). A person must not be shown live buttons for an approval the store will refuse: the card is posted already inert, with the prose and the room link and no buttons — the App's own clock decides only *what it draws*, never the decision (D10: the card is a view).

---

## File structure

| File | Responsibility | PR |
|---|---|---|
| `internal/envelope/envelope.go` | `ValidBranch`: the one branch pattern three packages check | 1 |
| `internal/envelope/payloads.go` | `ApprovalRequestedPayload.Branch` | 1 |
| `internal/store/migrations/20261105120000_approval_binding.sql` (new) | `approvals.binding_branch` and the replaced `approvals_are_their_events()` | 1 |
| `internal/store/approvals.go` | `Approval.BindingBranch`, `approvalCols`, the INSERT | 1 |
| `internal/bridgeapi/approvals.go` | `Branch: run.Branch` on the request | 1 |
| `internal/config/config.go` | `human.slackDecide {principal, teamID}` and its validation | 2 |
| `internal/metrics/metrics.go` | `rooms_slack_decisions_total{result, decision}` | 2 |
| `internal/humanapi/slackdecide.go` (new) | The route, §2's resolution in order, §1's closed codes, the decision draft, the limiter | 2 |
| `internal/humanapi/server.go` | `SlackDecide *SlackDecider` and its `mux.HandleFunc` | 2 |
| `internal/app/broker.go` | Wire `SlackDecide` from the config | 2 |
| `internal/webhook/events.go`, `webhook.go` | `Event` fields, `Classes()`, `Decisions()`, `Clip("decision")`, the tracker's two emissions | 3 |
| `internal/slackapp/slack.go` | Tagged `Metadata`, `draftPayload()`/`approvalPayload()`, `PostCard`, `Update` | 3 |
| `internal/slackapp/app.go` | `postDraft`/`threadDraft` read the tagged payload; then the interactivity branch, the card, the answer and the teardown | 3, 4 |
| `internal/slackapp/card.go` (new) | The Block Kit card, the button value, the refusal lines | 4 |
| `internal/slackapp/broker.go` | `Decide(ctx, Decision) (DecisionResult, error)` on `/api/slack/decisions` | 4 |
| `internal/slackapp/config.go` | `Channel.Approvals` | 3 |
| `docs/api.md`, `docs/integration.md` | The route and the switch | 2 |
| `docs/slack.md`, `docs/security.md`, `web/src/needs.ts` | The card, the manifest, invariant 8, the "one decide path" comment | 4 |
| `tooling/gcp-0/agent-factory/slack-app/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` | The channel flag, `human.slackDecide`, `room.approval_closed` | B |
| `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` | The Maku release pin | B |
| `scripts/ci/tests/test-factory-slack-switchon.py`, `test-room-broker-suspend.py` | The gates the two new keys touch | A |
| `observability/base/agent-platform/vmrule-agent-factory.yaml`, `scripts/ci/tests/test-agent-factory-slack-alerts.sh` (new) | `SlackDecisionsSpike`, `SlackCardUpdatesFailing`, and their gate | A |
| `docs/runbooks/agent-factory/22-slack.md`, `18-factory-interfaces.md` | The operator procedure | A |
| `website/content/docs/decisions/0049-…`, `0059-…`, `website/content/docs/use/slack.md` | The amended decisions and the user guide | A |

---

## Maku PR 1 — `feat/approval-binding`: the branch a run may push to

### Task 1: `envelope.ValidBranch` and the request payload's branch

**Files:**
- Modify: `internal/envelope/envelope.go` (beside `ValidID`, line ~23)
- Modify: `internal/envelope/payloads.go` (`type ApprovalRequestedPayload`)
- Test: `internal/envelope/envelope_test.go`, `internal/envelope/payloads_test.go`

**Interfaces:**
- Produces: `envelope.ValidBranch(branch string) bool`; `envelope.ApprovalRequestedPayload.Branch string` (`json:"branch,omitempty"`).

- [ ] **Step 1: Write the failing test**

In `envelope_test.go`:

```go
// D5: the branch a forge.push approval binds is the AgentRun CRD's own pattern, checked in one
// place by the store's trigger's neighbour, the webhook and the App's button.
func TestValidBranch(t *testing.T) {
	for _, ok := range []string{"agent/26zfnuxm", "agent/a", "agent/a.b_c-d/e"} {
		if !ValidBranch(ok) {
			t.Errorf("%q refused", ok)
		}
	}
	for _, bad := range []string{"", "main", "agent/", "agent/A", "agents/x", "agent/" + strings.Repeat("a", 102)} {
		if ValidBranch(bad) {
			t.Errorf("%q accepted", bad)
		}
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/envelope/ -run TestValidBranch -count=1`
Expected: FAIL at compile (`ValidBranch undefined`).

- [ ] **Step 3: Implement it**

```go
var branchRE = regexp.MustCompile(`^agent/[a-z0-9][a-z0-9._/-]{0,100}$`)

// ValidBranch reports whether s is an AgentRun's branch (v1alpha1.AgentRunSpec.Branch's pattern):
// the one thing a forge.push approval binds (v3.x Slack push approval D5).
func ValidBranch(s string) bool { return branchRE.MatchString(s) }
```

`internal/envelope` imports nothing of Kubernetes on purpose: `webhook`, `humanapi` and `slackapp` all import it, and the spec keeps the tracker free of Kubernetes imports.

- [ ] **Step 4: The payload field**

In `payloads.go`'s `ApprovalRequestedPayload`, after `Class`:

```go
	// Branch is the run's branch, set by the bridge for the classes it forwards (D5): the one
	// thing a forge.push approval binds. Empty for every other class and for older requests.
	Branch string `json:"branch,omitempty"`
```

In `payloads_test.go`, extend the existing round-trip case for `ApprovalRequestedPayload` with `Branch: "agent/26zfnuxm"`; the marshalled JSON must carry `"branch":"agent/26zfnuxm"` and a payload built without it must not carry the key.

- [ ] **Step 5: Run both packages**

Run: `go test ./internal/envelope/ -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/envelope
git commit -m "feat(envelope): an approval request carries the run's branch"
```

### Task 2: `approvals.binding_branch` and the trigger that holds it

**Files:**
- Create: `internal/store/migrations/20261105120000_approval_binding.sql`
- Modify: `internal/store/migrations/atlas.sum` (regenerated, never hand-edited)
- Modify: `internal/store/approvals.go` (`type Approval`, `approvalCols`, `scanApproval`, `requestApproval`'s payload and INSERT)
- Test: `internal/store/approvals_test.go` (`TestApprovalBinding`; `TestApprovalsAreTheirEvents` amended), `internal/store/migrations/embed_test.go` (amended)

**Interfaces:**
- Consumes: `envelope.ApprovalRequestedPayload.Branch` (Task 1).
- Produces: `store.Approval.BindingBranch string`; `approvalCols` gains `binding_branch` (last); `RequestApproval` writes `a.BindingBranch` and the payload's `branch` from the same value.

- [ ] **Step 1: Write the failing test**

Append to `approvals_test.go`:

```go
// D5: a forge.push approval binds the run's branch, and nothing else. The column round-trips, the
// row stays its event down to the branch (a differing one is refused), and the broker's grant
// cannot rewrite it after the fact.
func TestApprovalBinding(t *testing.T) {
	ctx := t.Context()
	s, _, _, _ := open(t)
	holdBridge(t, s, room, approvalRun)
	a := approval("ap1", "e1", "c1", time.Hour)
	a.Class, a.BindingBranch = "forge.push", "agent/26zfnuxm"
	got, ev, err := s.RequestApproval(ctx, a, approvalDraft())
	if err != nil || got.BindingBranch != "agent/26zfnuxm" {
		t.Fatalf("%+v %v", got, err)
	}
	var p envelope.ApprovalRequestedPayload
	if json.Unmarshal(ev.Payload, &p) != nil || p.Branch != "agent/26zfnuxm" {
		t.Fatalf("the event's branch: %s", ev.Payload)
	}
	again, _, err := s.Approval(ctx, "ap1")
	if err != nil || again.BindingBranch != "agent/26zfnuxm" {
		t.Fatalf("read back: %+v %v", again, err)
	}
	// An unbranched approval keeps the default, and its event says nothing about a branch.
	if _, _, err := s.RequestApproval(ctx, approval("ap2", "e2", "c2", time.Hour), approvalDraft()); err != nil {
		t.Fatal(err)
	}
	for tc, want := range map[string]struct{ sql, code, msg string }{
		// The fixture differs from ap1's event in the binding branch and in nothing the trigger reads:
		// same requested_seq, run, call id, class and action (the event id is fresh, so the row does
		// not trip the (room, run, event) unique key, and the trigger never compares it). The old
		// trigger accepts it; only the new clause rejects it.
		"a row whose branch differs from its event's": {`INSERT INTO approvals (approval_id, room_id, run_id, event_id, call_id, class, action, binding_branch, state, requested_seq, expires_at)
			SELECT 'apX', room_id, run_id, 'eX', call_id, class, action, 'agent/other', 'pending', requested_seq, expires_at
			FROM approvals WHERE approval_id = 'ap1'`, "23514", "not its approval_requested"},
		"a branch outside the CRD's pattern": {`UPDATE approvals SET binding_branch = 'main' WHERE approval_id = 'ap1'`, "42501", ""},
	} {
		t.Run(tc, func(t *testing.T) {
			err := inTx(ctx, s, want.sql)
			var pg *pgconn.PgError
			if !errors.As(err, &pg) || pg.Code != want.code || !strings.Contains(pg.Message, want.msg) {
				t.Fatalf("want SQLSTATE %s mentioning %q, got %v", want.code, want.msg, err)
			}
		})
	}
}
```

`approval`, `approvalDraft`, `holdBridge`, `open`, `inTx` and `room` are `approvals_test.go`'s and `store_test.go`'s existing helpers; `approval()` builds an `Approval` whose `BindingBranch` is empty, so every existing case keeps its default.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/store/ -run TestApprovalBinding -count=1` (Docker running)
Expected: FAIL at compile (`a.BindingBranch undefined`).

- [ ] **Step 3: The migration**

`internal/store/migrations/20261105120000_approval_binding.sql`, additive and CRD-shaped:

```sql
-- v3.x Slack push approval D5: the durable binding of a forge.push approval is the branch the run
-- may push to, and deliberately no commit — no pushed commit exists before the push, so any SHA
-- shown at request time is one the person did not approve. Defaulted, so every row an older
-- broker wrote stays valid and a code rollback needs no database change.
ALTER TABLE approvals ADD COLUMN binding_branch text NOT NULL DEFAULT ''
  CHECK (binding_branch = '' OR binding_branch ~ '^agent/[a-z0-9][a-z0-9._/-]{0,100}$');

-- The row stays its approval_requested event, down to the new field: CREATE OR REPLACE keeps
-- the trigger and the function's other clauses exactly as 20261005120000_approvals.sql left them,
-- and only the insert check gains the branch comparison.
CREATE OR REPLACE FUNCTION approvals_are_their_events() RETURNS trigger
  LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF (SELECT sealed FROM public.rooms WHERE room_id = NEW.room_id) THEN
    RAISE EXCEPTION 'room log: room % is sealed and its approvals stay', NEW.room_id USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'INSERT' AND (NEW.state <> 'pending' OR NEW.decided_by IS NOT NULL OR NEW.decided_at IS NOT NULL
      OR NEW.reason IS NOT NULL OR NEW.requested_at <> now()) THEN
    RAISE EXCEPTION 'room log: approval % enters pending, undecided, at now()', NEW.approval_id USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'INSERT' AND NOT EXISTS (SELECT 1 FROM public.events WHERE room_id = NEW.room_id AND seq = NEW.requested_seq
      AND type = 'approval_requested' AND run_id = NEW.run_id AND payload->>'approvalId' = NEW.approval_id
      AND payload->>'callId' = NEW.call_id AND payload->>'class' = NEW.class AND payload->'action' = NEW.action
      AND coalesce(payload->>'branch', '') = NEW.binding_branch) THEN
    RAISE EXCEPTION 'room log: approval % is not its approval_requested event', NEW.approval_id
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND (OLD.state <> 'pending' OR NEW.state = 'pending') THEN
    RAISE EXCEPTION 'room log: approval % moves once, out of pending (% to %)', OLD.approval_id, OLD.state, NEW.state
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND (NEW.decided_by IS NULL OR NEW.decided_at IS DISTINCT FROM now()) THEN
    RAISE EXCEPTION 'room log: approval % is closed at now(), by someone', OLD.approval_id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
```

Then regenerate the hash: `atlas migrate hash --dir file://internal/store/migrations` (it rewrites `atlas.sum`; never edit it by hand). The column is not in the broker's `UPDATE (state, decided_by, decided_at, reason)` grant, so a binding cannot be rewritten after the fact — that is the second case above.

- [ ] **Step 4: The column, and the one INSERT argument**

In `approvals.go`: `Approval` gains

```go
	// BindingBranch is the branch a forge.push approval binds, from the run's AgentRun (D5): the
	// boundary the repository ruleset already enforces on that run's token. Empty otherwise.
	BindingBranch string
```

`approvalCols` gains `, binding_branch` as its last column; `scanApproval` scans `&a.BindingBranch` last. In `requestApproval`, add `Branch: a.BindingBranch` to the `envelope.ApprovalRequestedPayload{…}` literal and `binding_branch` to the INSERT's column list with `$11` bound to `a.BindingBranch`.

- [ ] **Step 5: Amend the two tests the schema moves**

`TestApprovalsAreTheirEvents`: its `row` constant inserts into the **ten** original columns (`approval_id, room_id, run_id, event_id, call_id, class, action, state, requested_seq, expires_at`), so every case keeps `binding_branch = ''` and still satisfies the trigger — leave its cases as they are; the new refusal cases live in `TestApprovalBinding` (Step 1). `internal/store/migrations/embed_test.go`: `wantNames` gains `"20261105120000_approval_binding.sql"` as the eleventh entry, `versions[len-1]` becomes `"20261105120000"`, `wantNoTx` is unchanged (this file is transactional), and the test's doc comment says eleven files instead of ten.

- [ ] **Step 6: Run the store suite and the hash check**

Run: `go test ./internal/store/... -count=1 && task migrations`
Expected: PASS; `atlas migrate validate` silent.

- [ ] **Step 7: Commit**

```bash
git add internal/store
git commit -m "feat(store): a forge.push approval binds the run's branch, and its event must agree"
```

### Task 3: the bridge fills the branch

**Files:**
- Modify: `internal/bridgeapi/approvals.go` (`s.Approvals.RequestApproval(ctx, store.Approval{…})`, ~line 112)
- Test: `internal/bridgeapi/approvals_test.go`

**Interfaces:**
- Consumes: `store.Approval.BindingBranch` (Task 2).
- Produces: every forwarded approval whose class is one of the five carries `run.Branch`; a class outside them is refused before the store, as today.

- [ ] **Step 1: Amend the existing approval test**

In `internal/bridgeapi/approvals_test.go`, `fakeApprovals` already records the `store.Approval` each request sent (`f.got`); assert on **that**, not on the envelope payload — the fake stores no event, and the payload is the store's to build (Task 2's `TestApprovalBinding` already pins it). Extend `TestApprovalRequests` with:

```go
	// D5: the request carries the run's own branch, and the row's binding is that branch.
	if len(f.got) == 0 || f.got[0].BindingBranch != "agent/26zfnuxm" {
		t.Fatalf("the request's binding: %+v", f.got)
	}
```

The rig's claim must carry the branch: `agentRun` builds an `unstructured` object, and `runwatch.Run.Branch` reads `status.branch` and falls back to `spec.branch`, so set `run.Object["status"].(map[string]any)["branch"] = "agent/26zfnuxm"` before `w.Upsert`. Then a second case posts the same request for a run with neither key and asserts `f.got[1].BindingBranch == ""` (and that the request still succeeds: an unbranched approval is today's behaviour, not a refusal).

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/bridgeapi/ -run TestApprovalRequests -count=1`
Expected: FAIL (`BindingBranch` empty).

- [ ] **Step 3: Set it**

In `approval`'s `store.Approval{…}` literal, after `Prompters: prompters`:

```go
		// D5: the branch is the run's, as the claim carries it; the bridge never invents one.
		BindingBranch: run.Branch,
```

- [ ] **Step 4: Run the package, then the gate**

Run: `go test ./internal/bridgeapi/ -count=1 && task check`
Expected: PASS, exit 0 (store tests need Docker).

- [ ] **Step 5: Commit, push, open PR 1**

```bash
git add internal/bridgeapi
git commit -m "feat(bridgeapi): a forwarded approval names the run's branch"
git fetch origin && git rebase origin/main && git push -u origin feat/approval-binding
gh pr create --title "feat(store): a forge.push approval binds the run's branch" --body "D5 of docs/superpowers/specs/2026-11-05-v3x-slack-push-approval-design.md: approvals.binding_branch, the approval_requested branch, the trigger that holds them equal, and the bridge line that fills it. No commit SHA, by the owner's 2026-11-05 decision. Evidence: task check exit 0, task migrations clean."
```

---

## Maku PR 2 — `feat/slack-decide-route`: one route that decides `forge.push`

### Task 4: `human.slackDecide` in the config, and the counter

**Files:**
- Modify: `internal/config/config.go` (`HumanConfig`, new `SlackDecideConfig`, `validateHuman`)
- Modify: `internal/metrics/metrics.go` (beside `SlackLinks`, ~line 162 and ~line 235)
- Test: `internal/config/config_test.go` (`TestLoadSlackDecide`)

**Interfaces:**
- Produces: `config.HumanConfig.SlackDecide *SlackDecideConfig` (`json:"slackDecide,omitempty"`) with `Principal string` and `TeamID string`; `metrics.Set.SlackDecisions metric.Int64Counter` = `rooms_slack_decisions_total`.

- [ ] **Step 1: Write the failing test**

In `config_test.go`, beside `TestLoadSlackLink`:

```go
// human.slackDecide is human.slackLink's neighbour: off by default; on, it names a declared
// sponsored principal and one workspace, and needs the GitHub check, since the route resolves the
// linked human's login.
const slackDecide = access + "  roomctlClientIDFile: /etc/room-broker/oidc/roomctl\n  mcp:\n    enabled: true\n" +
	"    sponsored: [{name: slack-app, clientIDFile: /etc/slack/client-id}]\n" +
	"  slackDecide:\n    principal: slack-app\n    teamID: T01ABC\n"

// decideConfig is slackDecide with what a sponsored principal and an enabled /mcp already need:
// valid's config has no factoryURL, and human.mcp.sponsored refuses to load without one.
const decideConfig = slackDecide + "factoryURL: https://agent-factory.agent-system.svc.cluster.local:8080\n"

func TestLoadSlackDecide(t *testing.T) {
	if c, err := Load(write(t, valid)); err != nil || c.Human.SlackDecide != nil {
		t.Fatalf("off by default: %+v %v", c.Human.SlackDecide, err)
	}
	c, err := Load(write(t, valid+decideConfig))
	if err != nil || c.Human.SlackDecide == nil || c.Human.SlackDecide.Principal != "slack-app" || c.Human.SlackDecide.TeamID != "T01ABC" {
		t.Fatalf("%+v %v", c.Human.SlackDecide, err)
	}
	for name, c := range map[string]struct{ body, want string }{
		"an undeclared principal": {strings.Replace(decideConfig, "principal: slack-app", "principal: other", 1), "human.slackDecide.principal"},
		"a bad team":              {strings.Replace(decideConfig, "teamID: T01ABC", "teamID: x", 1), "human.slackDecide.teamID"},
		"no GitHub check":         {strings.Replace(decideConfig, access, "", 1), "human.slackDecide needs human.access"},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := Load(write(t, valid+c.body))
			if err == nil || !strings.Contains(err.Error(), c.want) {
				t.Fatalf("got %v, want %q", err, c.want)
			}
		})
	}
	// mode local has no sponsored principal and no GitHub check to resolve a login with, so it
	// refuses the switch on its own key. localConfig is the existing local fixture, not valid
	// rewritten: a local config carries no issuer, no OAuth client and a loopback publicURL.
	local := strings.Replace(localConfig, "human:\n", "human:\n  slackDecide:\n    principal: slack-app\n    teamID: T01ABC\n", 1)
	if _, err := Load(write(t, local)); err == nil || !strings.Contains(err.Error(), "human.slackDecide") {
		t.Fatalf("mode local: %v", err)
	}
}
```

`valid`, `access` and `localConfig` are `config_test.go`'s existing fixtures.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/config/ -run TestLoadSlackDecide -count=1`
Expected: FAIL at compile (`SlackDecide undefined`).

- [ ] **Step 3: The key and its validation**

Beside `SlackLinkConfig`:

```go
// SlackDecideConfig is human.slackDecide: the sponsored principal (the Slack App) that may post a
// decision, and the one Slack workspace whose clicks are this broker's (v3.x Slack push approval
// D14). On, it serves POST /api/slack/decisions; off, the path is a 404.
type SlackDecideConfig struct {
	Principal string `json:"principal"`
	TeamID    string `json:"teamID"`
}
```

`HumanConfig` gains it after `SlackLink`. Validation, in the same block as `SlackLink`'s and with the same three refusals plus `h.Access == nil`, appends one more entry to `mode local`'s refused list: `{"human.slackDecide", h.SlackDecide != nil, "a decision names a sponsored principal and a GitHub link, neither of which mode local has"}`. Nothing else is configurable: the class is a constant (D13).

- [ ] **Step 4: The counter**

In `metrics.go`, beside `SlackLinks`:

```go
	// SlackDecisions is rooms_slack_decisions_total{result, decision}: the one route the Slack App
	// decides through, by the closed code it answered with and the decision it recorded (empty when
	// it recorded none).
	SlackDecisions metric.Int64Counter
```

and in `New`, beside `SlackLinks`'s constructor:

```go
	s.SlackDecisions, err = meter.Int64Counter("rooms_slack_decisions_total",
		metric.WithDescription("Slack decisions on forge.push approvals, by the closed result code and the decision."))
	check(err)
```

- [ ] **Step 5: Run the two packages**

Run: `go test ./internal/config/ ./internal/metrics/ -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/config internal/metrics
git commit -m "feat(config): human.slackDecide, and the Slack decision counter"
```

### Task 5: the route and §2's resolution

**Files:**
- Create: `internal/humanapi/slackdecide.go`
- Modify: `internal/humanapi/server.go` (`Server.SlackDecide`, its route in `Routes()`)
- Test: `internal/humanapi/slackdecide_test.go` (new), `internal/humanapi/sponsored_test.go` (amended)

**Interfaces:**
- Consumes: `store.Approval.BindingBranch` (Task 2); `s.sponsoredPrincipal` (`mcp.go:160`), `s.room` (`server.go:410`), `s.Identity`, `s.Access`, `s.Runs` (all already on `Server`).
- Produces: `humanapi.SlackDecider` (fields `Store SlackDecideStore; Principal, TeamID string; Rooms client.Reader; Namespace string; Groups policy.Groups; Identity *ghidentity.Resolver; Access *repoaccess.Checker; Runs Runs; Logger *slog.Logger`), `humanapi.SlackDecideStore`, `humanapi.SlackDecision`, `slackDecidableClass`, and `Server.SlackDecide *SlackDecider`.

- [ ] **Step 1: Write the failing tests**

`slackdecide_test.go`:

```go
// The route's rig: the App's principal, a link, an approval and the two standings.
func slackDecideOn(t *testing.T, ...) option // sets s.SlackDecide with the rig's fakes
```

Give the file three helpers and pin them (they are this task's contract, not a suggestion):

```go
// slackDecideOn serves POST /api/slack/decisions as the App: the team T01ABC, the rig's rooms, the
// rig's GitHub gate, and memLog-backed readings plus a decision log the test inspects.
func slackDecideOn(t *testing.T, links map[string]string, aps map[string]store.Approval, decided *[]decided) option

// press is a body of §1 as the App sends it: the team, the clicker, the approval, the hint's branch
// and the decision. Every case names its team, so a peer workspace's click is expressible.
func press(team, user, ap, branch, decision string) SlackDecision

// decide posts b as the App and returns the HTTP status and the result code.
func decide(t *testing.T, e env, b SlackDecision) (int, string)
```

`decided` records what reached the store: `type decided struct{ by, decision, reason, originClient string; seq int64 }`. The rig's GitHub gate answers `Login` per sub, so `U05` is a linked user whose account read fails outright (a `ghidentity` error, not `ErrInactive`) and `U06` a user whose `CanWrite` errors — the two `link_unverified` rows below.

```go
// D1, D15, D3: one case per row of §1's table, each with its exact code, and the refusal says
// nothing else.
func TestSlackDecideRefusals(t *testing.T) {
	for name, c := range map[string]struct {
		body   SlackDecision
		status int
		result string
	}{
		"a peer workspace":         {press("T02PEER", "U02", ap1, branch, "approved"), 200, "not_permitted"},
		"an unlinked user":         {press(team, "U03", ap1, branch, "approved"), 200, "not_linked"},
		"an account with no GitHub": {press(team, "U04", ap1, branch, "approved"), 200, "not_linked"},
		"no such approval":         {press(team, "U02", "01M4A1B2C3D4E5F6G7H8J9K0MN", branch, "approved"), 200, "not_found"},
		"a sealed room":            {press(team, "U02", ap1, branch, "approved"), 200, "sealed"},
		"the wrong branch":         {press(team, "U02", ap1, "agent/other", "approved"), 200, "binding_mismatch"},
		// §1's table row for a ZITADEL or GitHub read that cannot be made: it fails closed, with no
		// detail, and never as a decision.
		"the account cannot be read":    {press(team, "U05", ap1, branch, "approved"), 200, "link_unverified"},
		"the permission cannot be read": {press(team, "U06", ap1, branch, "approved"), 200, "link_unverified"},
		"a malformed decision":     {press(team, "U02", ap1, branch, "maybe"), 400, "bad_request"},
		"a bad approval id":        {press(team, "U02", "not-a-ulid", branch, "approved"), 400, "bad_request"},
		"a bad branch shape":       {press(team, "U02", ap1, "main", "approved"), 400, "bad_request"},
	} {
		t.Run(name, func(t *testing.T) {
			got, result := decide(t, e, c.body)
			if got != c.status || result != c.result {
				t.Fatalf("%d %s, want %d %s", got, result, c.status, c.result)
			}
			if len(*decided) != 0 {
				t.Fatalf("a refusal decided: %+v", *decided)
			}
		})
	}
}

// D4: both standings, both required. An approver without repository write and a writer without
// standing are each refused with their own code; owner and writer decides. A ZITADEL admin outside
// the Room CR is refused here (D15) and may still decide on the room page.
func TestSlackDecideNeedsBothStandings(t *testing.T)

// D6: the hint is a hint. The request's branch must be the run's, and an approval with no branch
// decides nothing.
func TestSlackDecideBinding(t *testing.T)

// D13: one class. Every other class is not_supported, whatever the clicker's standing, and no
// GitHub call is made for it.
func TestSlackDecideClasses(t *testing.T)
```

`TestSlackDecideNeedsBothStandings` cases and assertions: approver-without-write → `200 repository_permission`; writer-without-standing → `200 not_permitted`; owner-and-writer → `200 approved` with one `decided` record whose `decision` is `approved`; an admin-group member with no `spec.owner`/`members` entry → `200 not_permitted`, and the same principal on the room page (`/v1/ws` decide frame) still decides. `TestSlackDecideBinding` cases: the request's branch ≠ the run's → `binding_mismatch`; `BindingBranch == ""` → `binding_mismatch`; the run absent from `Runs.InRoom` → `binding_mismatch`; the right branch → `approved`. `TestSlackDecideClasses` loops `forge.pr`, `forge.other`, `mcp.write`, `shell.high`, `egress.new` → `200 not_supported`, and asserts the GitHub fake counted zero calls (`w.checked() == 0`, the rig's counter).

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestSlackDecide' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The route**

`server.go`: `Server` gains

```go
	// SlackDecide is human.slackDecide: the App's one route that records a decision, for forge.push
	// only (v3.x Slack push approval D2, D13). Nil serves nothing: the path is the mux's 404.
	SlackDecide *SlackDecider
```

and in `Routes()`, after the `SlackLink` block:

```go
	if s.SlackDecide != nil {
		mux.HandleFunc("POST /api/slack/decisions", s.slackDecide)
	}
```

No other route, no `GET`, and no cookie is read: the route has no CSRF surface because it has no cookie surface.

- [ ] **Step 4: The handler and §2**

`slackdecide.go` (new). Declarations the rest of the plan uses:

```go
// slackDecidableClass is the one class this route decides (D13): a constant, never config, so a
// widening costs a code change and a design.
const slackDecidableClass = "forge.push"

// SlackDecision is §1's body. Every field is checked against its shape before any read.
type SlackDecision struct {
	Team       string `json:"team"`
	User       string `json:"user"`
	Channel    string `json:"channel"`
	MessageTS  string `json:"messageTS"`
	ApprovalID string `json:"approvalId"`
	Branch     string `json:"branch"`
	Decision   string `json:"decision"`
}

// SlackDecideStore is the part of the store the route reads and writes; *store.Store has it.
type SlackDecideStore interface {
	SlackLink(ctx context.Context, team, user string) (sub string, found bool, err error)
	Approval(ctx context.Context, id string) (store.Approval, error)
	Decide(ctx context.Context, approvalID, decision, by, reason string, d envelope.Draft) (envelope.Event, store.Approval, error)
	Room(ctx context.Context, id string) (store.RoomState, error)
}

// SlackDecider is human.slackDecide: who may call, for which workspace, and the readings standing
// is resolved from. Groups is left zero on purpose (D15): the broker holds no token for the linked
// human, so standing is exactly the Room CR's.
type SlackDecider struct {
	Store     SlackDecideStore
	Principal string // "system:slack-app"
	TeamID    string
	Rooms     client.Reader
	Namespace string
	Groups    policy.Groups
	Identity  *ghidentity.Resolver
	Access    *repoaccess.Checker
	Runs      Runs
	Metrics   *metrics.Set
	OnDecided func(time.Duration)
	Logger    *slog.Logger

	mu     sync.Mutex
	limits map[string]*rate.Limiter // (team,user) → 10/min, burst 5, per replica
}
```

`s.slackDecide` (on `*Server`) is the HTTP shell, in this order, and nothing before the first step:

1. `p, ok := s.sponsoredPrincipal(r)`; `!ok` → `403` with no body code. Then `p.ID != s.SlackDecide.Principal || !p.Sponsored` → `403`. A human's or a machine's token is refused here.
2. **Body**: `http.MaxBytesReader(w, r.Body, 4<<10)`; `mime.ParseMediaType(r.Header.Get("Content-Type"))` must be `application/json`; `dec := json.NewDecoder(body); dec.DisallowUnknownFields()`; one value only (`dec.More()` after the decode is false). Anything else → `400 bad_request`.
3. **Shapes**, before any read: each field against its regex (Global Constraints) and `in.Decision` ∈ `approved`\|`denied`; anything else is `400 bad_request`. The team is *not* a shape: it is step 2 of `resolve`, so a peer workspace's click gets a closed code and not a 400.
4. **The limiter**: `s.SlackDecide.allow(in.Team+"/"+in.User)` → `rate.NewLimiter(rate.Every(6*time.Second), 5)` per key → over it `429 rate_limited`.
5. `result, decided := s.SlackDecide.resolve(r.Context(), p, in)`; count `rooms_slack_decisions_total{result, decision=decided}`; `writeJSON(w, slackDecisionResult{Result: result})` with the status §1's table gives it: `200` for every closed code, refusals included, so the App never retries one, and `503` for `unavailable` alone (steps 2 and 4 already answered `bad_request` and `rate_limited`).

`resolve` is §2's resolution, **in this order**, each step returning the code on its right; the comment names the spec step it is (the table's rows 2–13 are §2's steps 2–11 plus the decision itself):

| # | Step | Code |
|---|---|---|
| 1 | the App's principal (done by the shell) | — |
| 2 | `in.Team == d.TeamID` | `not_permitted` |
| 3 | `d.Store.SlackLink(ctx, in.Team, in.User)` | `not_linked` (`err` → `unavailable`) |
| 4 | `d.Store.Approval(ctx, in.ApprovalID)`; and `d.Store.Room(ctx, ap.RoomID)` | `not_found` / `unavailable` |
| 5 | `ap.Class == slackDecidableClass` — free, and before any GitHub call | `not_supported` |
| 6 | the `Room` CR read through `d.Rooms.Get(ctx, client.ObjectKey{Namespace: d.Namespace, Name: ap.RoomID}, room)` (`apierrors.IsNotFound` → `not_found`; the route has no `*Server`) and the `store.RoomState` from step 4; sealed (`st.Sealed`) | `not_found` / `sealed` |
| 7 | `d.Groups.Resolve(room, authn.Principal{Kind: envelope.ActorHuman, ID: "human:" + sub, Sub: sub}, "", true)`, then `policy.Allowed(subj, policy.Decide)` | `not_permitted` |
| 8 | `room.Spec.Repository == ""` | `not_permitted` |
| 9 | `d.Identity.Login(ctx, sub, room.Spec.Repository)` | `not_linked` (`ErrInactive`/empty) / `link_unverified` |
| 10 | `d.Access.CanWrite(ctx, room.Spec.Repository, login)` | `repository_permission` / `link_unverified` |
| 11 | the run's branch from `d.Runs.InRoom(ap.RoomID)` by `ap.RunID`; `expected != in.Branch` or `expected == ""` | `binding_mismatch` |
| 12 | `room.Spec.Approvals.FourEyes && slices.Contains(ap.Prompters, "human:"+sub)` | `four_eyes` |
| 13 | `d.Store.Decide(…)` with §2's draft | `already_decided` / `approval_expired` / `sealed` / `not_found` / `bad_request` / `unavailable` |

Steps 7 and 9–10 are one `ctx` bounded by `accessWait` (10 s), as `access.go` does. Step 13's `store` error mapping is the same switch `acts.go`'s `reason()` uses, with `unavailable` for anything else, and `OnDecided(time.Since(ap.RequestedAt))` only when `ap.State == store.ApprovalPending && err == nil` — a replay was already observed once.

- [ ] **Step 5: Run them**

Run: `go test ./internal/humanapi/ -run 'TestSlackDecideRefusals|TestSlackDecideNeedsBothStandings|TestSlackDecideBinding|TestSlackDecideClasses' -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/humanapi
git commit -m "feat(humanapi): POST /api/slack/decisions resolves a forge.push decision from a linked human"
```

### Task 6: who is recorded, once

**Files:**
- Modify: `internal/humanapi/slackdecide.go` (the draft, the four-eyes read, the expiry and supersede codes)
- Test: `internal/humanapi/slackdecide_test.go`

**Interfaces:**
- Consumes: Task 5's `resolve`.
- Produces: the draft of §2's table; the result code is the decision (`approved`/`denied`) when `err == nil`.

- [ ] **Step 1: Write the failing tests**

```go
// D8: the log names the person, never the App. One actor is stamped, and the surface lives in the
// idempotency scope.
func TestSlackDecideActorIsHuman(t *testing.T)

// D7: the same click twice is one decision and the same answer; approve then deny is
// already_decided and still one approval_decided.
func TestSlackDecideIdempotent(t *testing.T)

// OD-16: a prompter is four_eyes and another approver decides; with four-eyes off the prompter
// decides.
func TestSlackDecideFourEyes(t *testing.T)

// A click past the deadline, before the sweep: approval_expired, the row expired, one event, and
// the sweep afterwards appends nothing.
func TestSlackDecideExpired(t *testing.T)

// A call answered after the request, and a run that ended: already_decided with the row
// superseded.
func TestSlackDecideSuperseded(t *testing.T)
```

`TestSlackDecideActorIsHuman`'s assertions, exactly: the `envelope.Event` the store recorded has `Actor.Kind == envelope.ActorHuman`, `Actor.ID == "human:2918"` (the rig's sub), `Origin == envelope.OriginClient`, `OriginClient == "human:2918:slack:01M4A1B2C3D4E5F6G7H8J9K0MN"`, `OriginSeq == 1`, and `!strings.Contains(string(ev.Payload), "slack-app")` and `ev.Actor.ID != "system:slack-app"`. `TestSlackDecideIdempotent` asserts two identical posts both answer `approved`, the `*decided` slice holds exactly one record, and a following `denied` answers `already_decided` with the slice still at one. `TestSlackDecideFourEyes`'s first case sets `ap.Prompters = []string{"human:2918"}` and `room.Spec.Approvals.FourEyes = true`. `TestSlackDecideExpired` sets `ExpiresAt` a second in the past on the fake store, which must answer `store.ErrApprovalExpired` for it as `actLog.Decide` already does; it then asserts the route appended nothing of its own — the fake's `decisions` slice holds one entry (the store's refusal path closed the row) and the `memLog` gained exactly one `approval_decided`, the sweep's, not two. `TestSlackDecideSuperseded` uses `store.ErrAlreadyDecided` from the fake with a `superseded` row and asserts the code.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestSlackDecideActor|TestSlackDecideIdempotent|TestSlackDecideFourEyes|TestSlackDecideExpired|TestSlackDecideSuperseded' -count=1`
Expected: FAIL.

- [ ] **Step 3: The draft and the codes**

Step 13 builds exactly (the variable is `dr`, not `d`: `d` is the `*SlackDecider` receiver, and `d.Store.Decide(…, dr)` must compile):

```go
	dr := envelope.Draft{
		RoomID: ap.RoomID, RunID: ap.RunID,
		Actor:  envelope.Actor{Kind: envelope.ActorHuman, ID: "human:" + sub}, // D8: the person, never the App
		Origin: envelope.OriginClient,
		// The surface is in the scope, not the actor: one key per approval, and one per decision
		// within it (D7), so a replayed click replays and the opposite decision is not a replay.
		OriginClient: "human:" + sub + ":slack:" + ap.ID,
		OriginSeq:    map[string]int64{store.ApprovalApproved: 1, store.ApprovalDenied: 2}[in.Decision],
	}
	ev, _, err := d.Store.Decide(ctx, ap.ID, in.Decision, "human:"+sub, "", dr) // the reason is empty, always (D12)
```

`resolve` returns `(in.Decision, in.Decision)` on success and `(code, "")` on every refusal, so the counter's `decision` label is empty for a refusal and the HTTP body is always one closed code.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/humanapi/ -count=1`
Expected: PASS, the acts tests included (the web decide path is untouched).

- [ ] **Step 5: Commit**

```bash
git add internal/humanapi
git commit -m "feat(humanapi): a Slack decision is recorded as the linked human's, once"
```

### Task 7: transport, wiring, and the two boundaries the spec pins

**Files:**
- Modify: `internal/humanapi/slackdecide.go` (the limiter, the size/content-type refusals, `unavailable`)
- Modify: `internal/app/broker.go` (wire `SlackDecide`, beside `humanapi.SlackLinker`)
- Modify: `internal/humanapi/sponsored_test.go` (`TestSponsoredTokenElsewhere` amended)
- Test: `internal/humanapi/slackdecide_test.go`; **create** `internal/app/slackdecide_wiring_test.go` (there is no `TestSlackAppWiring` today: the spec's row 27 is a new test, written whole here)
- Docs: `docs/api.md` (`:8080` route table + a `### POST /api/slack/decisions` section), `docs/integration.md` (`human.slackDecide` row)

**Interfaces:**
- Produces: `Server.SlackDecide` wired from `config.HumanConfig.SlackDecide`; the route absent (404) when it is nil.

- [ ] **Step 1: Write the failing tests**

```go
// D14: every transport failure is its own status, and a store, room-reader or log failure is 503
// unavailable so the App may retry. The limiter is 10 a minute, burst 5, per (team,user).
func TestSlackDecideUnavailable(t *testing.T)
```

Cases, exact: `store.Approval` error → `503 unavailable`; `SlackLink` error → `503 unavailable`; `Decide` returning a bare error → `503 unavailable`; a 5 KiB body → `400 bad_request`; `Content-Type: text/plain` → `400 bad_request`; an unknown key (`"reason":"x"`) → `400 bad_request`; five presses from one `(team,user)` all served, the sixth `429 rate_limited`. Do not sleep to prove the refill: the rig's option replaces `s.SlackDecide` with a fresh `SlackDecider` (same store, same fakes) and asserts the next press is served — the limiter's per-instance state is the contract, its refill rate is `golang.org/x/time/rate`'s.

`TestSponsoredTokenElsewhere` gains the two halves the spec asks for: the App's bearer reaches `POST /api/slack/decisions` (its answer is a closed code, not `401`) and nowhere else in that list; a human bearer on the new route is `403`. Keep its existing three paths untouched.

`TestSlackAppWiring` is a **new** test in a **new** file, `internal/app/slackdecide_wiring_test.go` (grep first: no test of that name exists in `internal/app`). It reuses `humanSide`'s existing fake rig shape (`internal/app/access_test.go:221` builds one with `&fakeActLog{}`, `&fakeGitHubUsers{}`, `add`, `m`, `log`):

```go
// D14: human.slackDecide exists in the wiring or it does not. On, POST /api/slack/decisions is a
// route (no bearer is 403, the sponsored authenticator's refusal); off, it is the mux's 404,
// exactly as /mcp is when MCP is false. Routes() alone is enough: the mux is what is under test,
// and a Server with no Sponsored refuses every bearer rather than serving one.
func TestSlackAppWiring(t *testing.T) {
	off := &humanapi.Server{}
	if code := postRoute(t, off.Routes(), "/api/slack/decisions"); code != http.StatusNotFound {
		t.Fatalf("off: %d", code)
	}
	on := &humanapi.Server{SlackDecide: &humanapi.SlackDecider{Principal: "system:slack-app", TeamID: "T01ABC"}}
	if code := postRoute(t, on.Routes(), "/api/slack/decisions"); code != http.StatusForbidden {
		t.Fatalf("on: %d", code)
	}
}
```

with `postRoute(t *testing.T, h http.Handler, path string) int` doing the `httptest.NewRequest` + `httptest.NewRecorder` round trip. Task 15 extends this same test (same file) with the card path; it never renames it.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestSlackDecideUnavailable|TestSponsoredTokenElsewhere' -count=1 && go test ./internal/app/ -run TestSlackAppWiring -count=1`
Expected: FAIL.

- [ ] **Step 3: The limiter and the wiring**

The limiter lives on `SlackDecider` (`allow(key string) bool`, `s.limitMu`-style mutex, `rate.NewLimiter(rate.Every(6*time.Second), 5)`), documented with the reason: *a person presses a button a few times and never in a stream; the human limiter's 10/s burst 20 is for chat.*

In `internal/app/broker.go`, after the `human.slackLink` block:

```go
	if l := cfg.Human.SlackDecide; l != nil { // the App's one deciding route (v3.x Slack push approval D14)
		humans.SlackDecide = &humanapi.SlackDecider{Store: st, Principal: "system:" + l.Principal, TeamID: l.TeamID,
			Rooms: mgr.GetClient(), Namespace: ns, Identity: humans.Identity, Access: humans.Access, Runs: humans.Runs,
			Metrics: m, Logger: log,
			OnDecided: func(d time.Duration) { m.DecisionSeconds.Record(context.Background(), d.Seconds()) }}
		// Groups stays zero on purpose (D15): standing is the Room CR's alone, never a ZITADEL grant the
		// broker would have to hold a token for.
	}
```

- [ ] **Step 4: The docs**

`docs/api.md`'s `:8080` table gains one row:

```
| `POST /api/slack/decisions` | The Slack App's one deciding route, when `human.slackDecide`: `{team, user, channel, messageTS, approvalId, branch, decision}` → `{"result": "<code>"}`. Bearer: the App's sponsored principal only. 200 with a closed code for every refusal, `400` for shape, size or content type, `429` over 10 a minute (burst 5, per `(team,user)`, per replica), `503` when the store, the room or the log cannot be read. `forge.push` only; the human is resolved from `slack_links`, and must be an approver or owner of the room *and* write on its repository |
```

and a `### POST /api/slack/decisions` section quoting §1's table and §2's order. `docs/integration.md` gains a `human.slackDecide` row after `human.slackLink`: `{principal, teamID}`, one of `human.mcp.sponsored`, needs `human.access`, off by default, and the App's own `channels.<id>.approvals` is the other half of the pair.

- [ ] **Step 5: Run everything, push, open PR 2**

Run: `task check && task lint`
Expected: exit 0, 0 issues.

```bash
git add internal docs
git commit -m "feat(humanapi): the Slack decision route's transport, its wiring and its docs"
git fetch origin && git rebase origin/main && git push -u origin feat/slack-decide-route
gh pr create --title "feat(humanapi): POST /api/slack/decisions, one route that decides forge.push" --body "D2, D3, D4, D6, D7, D8, D12, D13, D14, D15 of the design: human.slackDecide, §2's resolution with the zero Groups, store.Decide unchanged with a per-(approval,decision) scope, and rooms_slack_decisions_total. Off by default: the path is a 404. Evidence: task check exit 0, task lint 0."
```

---

## Maku PR 3 — `feat/slack-card-primitives`: what a card needs, and nothing visible

### Task 8: the wait line carries the approval

**Files:**
- Modify: `internal/webhook/webhook.go` (`type Event`), `internal/webhook/events.go` (`Classes()`, `Decisions()`, `Clip`, the `ApprovalRequested` branch)
- Test: `internal/webhook/events_test.go` (`TestWaitingCarriesApproval`; `TestEvents` amended)

**Interfaces:**
- Consumes: `envelope.ValidBranch` (Task 1).
- Produces: `webhook.Classes() []string`, `webhook.Decisions() []string`, `webhook.Clip("decision", v)`; `Event.ApprovalID`, `Event.Class`, `Event.Branch`, `Event.ExpiresAt` (all `omitempty`, declared after `Verdict`), and `Event.Decision` in Task 9.

- [ ] **Step 1: Write the failing test**

```go
// §4: the wait line for an approval carries room, repo, approval id, class, branch and deadline;
// a value outside a closed set is dropped, not clipped to "other" — an approval card with a made-up
// class is not a card.
func TestWaitingCarriesApproval(t *testing.T) {
	var tr Tracker
	ev := envelope.Event{RoomID: "aaaaaaaa", Seq: 1, RunID: "cf4ato2x", Type: envelope.ApprovalRequested,
		Payload: envelope.Must(envelope.ApprovalRequestedPayload{ApprovalID: "01M4A1B2C3D4E5F6G7H8J9K0MN", CallID: "c1",
			Class: "forge.push", Branch: "agent/26zfnuxm", ExpiresAt: time.Date(2026, 11, 5, 19, 45, 0, 0, time.UTC)})}
	got := tr.Events("aaaaaaaa", "Smana/ai-native-ref", ev)
	if len(got) != 1 {
		t.Fatalf("%v", got)
	}
	e := got[0]
	if e.Type != "room.waiting_for_human" || e.Repo != "Smana/ai-native-ref" || e.Reason != "approval" ||
		e.ApprovalID != "01M4A1B2C3D4E5F6G7H8J9K0MN" || e.Class != "forge.push" || e.Branch != "agent/26zfnuxm" ||
		e.ExpiresAt != "2026-11-05T19:45:00Z" {
		t.Fatalf("%+v", e)
	}
	// A class outside the five is dropped; a branch outside the CRD's pattern is dropped, while a
	// valid class on the same event is kept: the values are judged one by one, never the event.
	wait := func(p envelope.ApprovalRequestedPayload) Event {
		t.Helper()
		var tr Tracker
		got := tr.Events("aaaaaaaa", "Smana/ai-native-ref", envelope.Event{RoomID: "aaaaaaaa", Seq: 1,
			Type: envelope.ApprovalRequested, Payload: envelope.Must(p)})
		if len(got) != 1 {
			t.Fatalf("%v", got)
		}
		return got[0]
	}
	if e := wait(envelope.ApprovalRequestedPayload{ApprovalID: "01M4A1B2C3D4E5F6G7H8J9K0MN", CallID: "c1",
		Class: "shell", Branch: "agent/26zfnuxm"}); e.Class != "" || e.Branch != "agent/26zfnuxm" {
		t.Fatalf("a class outside the five: %+v", e)
	}
	if e := wait(envelope.ApprovalRequestedPayload{ApprovalID: "01M4A1B2C3D4E5F6G7H8J9K0MN", CallID: "c1",
		Class: "forge.push", Branch: "main"}); e.Class != "forge.push" || e.Branch != "" {
		t.Fatalf("a branch outside the pattern: %+v", e)
	}
	if e := wait(envelope.ApprovalRequestedPayload{ApprovalID: "ap1", CallID: "c1", Class: "forge.push",
		Branch: "agent/26zfnuxm"}); e.ApprovalID != "" || e.Class != "forge.push" {
		t.Fatalf("an id that is not a ULID: %+v", e)
	}
}
```

`events_test.go` gains `"time"` in its imports (it has none today), and `01M4A1B2C3D4E5F6G7H8J9K0MN` is a well-formed ULID of the alphabet `ulidRE` accepts.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/webhook/ -run TestWaitingCarriesApproval -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The fields and the closed lists**

`Event` gains, after `Verdict`:

```go
	// The approval a wait line is about (§4): ids and closed values only, so the App can draw one
	// card with buttons without reading the room.
	ApprovalID string `json:"approvalId,omitempty"`
	Class      string `json:"class,omitempty"`
	Branch     string `json:"branch,omitempty"`
	ExpiresAt  string `json:"expiresAt,omitempty"` // RFC 3339, UTC
```

`events.go`:

```go
// classes are the five classes the broker forwards to approvers (bridgeapi's list), repeated here as
// this package's contract: a class outside them is dropped from an event, never clipped to "other".
var classes = []string{"forge.push", "forge.pr", "forge.other", "mcp.write", "shell.high"}

// Classes lists the values an event's class may hold.
func Classes() []string { return slices.Clone(classes) }

// decisions are the four ways an approval closes (store.Approval*).
var decisions = []string{"approved", "denied", "expired", "superseded"}

// Decisions lists the values an event's decision may hold.
func Decisions() []string { return slices.Clone(decisions) }
```

`Clip` gains `case "decision": list = Decisions()`, and its doc comment's vocabulary list becomes `"reason", "limit", "state", "verdict" or "decision"`. The `ApprovalRequested` branch becomes:

```go
	if ev.Type == envelope.ApprovalRequested {
		e := Event{Type: "room.waiting_for_human", Room: room, Repo: repo, Reason: "approval"}
		var p envelope.ApprovalRequestedPayload
		if json.Unmarshal(ev.Payload, &p) != nil {
			return []Event{e}
		}
		// Each value is dropped when it is outside its closed shape: the App then draws today's line.
		if ulidRE.MatchString(p.ApprovalID) {
			e.ApprovalID = p.ApprovalID
		}
		if slices.Contains(classes, p.Class) {
			e.Class = p.Class
		}
		if envelope.ValidBranch(p.Branch) {
			e.Branch = p.Branch
		}
		if !p.ExpiresAt.IsZero() {
			e.ExpiresAt = p.ExpiresAt.UTC().Format(time.RFC3339)
		}
		return []Event{e}
	}
```

with `var ulidRE = regexp.MustCompile(`^[0-9A-HJKMNP-TV-Z]{26}$`)` in `events.go` and its comment naming `bridgeapi` as the only producer.

- [ ] **Step 4: Amend `TestEvents`**

Its `approval(9)` expectation (line ~68) becomes the marshalled form of the new event. `approval()`'s payload is `ApprovalID: "ap1"` — not a ULID, so `ulidRE` **drops** it — with class `shell` (outside the five), no branch and no expiry. The event is then exactly type, room, repo and reason:

```go
		{approval(9), []string{`{"type":"room.waiting_for_human","room":"aaaaaaaa","repo":"Smana/ai-native-ref","reason":"approval"}`}},
```

The replay list at line ~85 already includes `approval(9)` and must still emit nothing. Task 8's own `TestWaitingCarriesApproval` is where a valid ULID appears, so the dropped-id branch is pinned here and the carried one there, once each.

- [ ] **Step 5: Run the package**

Run: `go test ./internal/webhook/ -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/webhook
git commit -m "feat(webhook): the wait line for an approval carries its ids, class, branch and deadline"
```

### Task 9: `room.approval_closed`

**Files:**
- Modify: `internal/webhook/events.go` (`types`, the new branch), `internal/webhook/webhook.go` (`Event.Decision`)
- Test: `internal/webhook/events_test.go` (`TestApprovalClosed`; `TestEvents`' `wantTypes` amended)

**Interfaces:**
- Produces: the thirteenth type `room.approval_closed`; `Event.Decision`.

- [ ] **Step 1: Write the failing test**

```go
// §4: every close is one event, once per approval, with its closed decision.
func TestApprovalClosed(t *testing.T) {
	for _, d := range Decisions() {
		var tr Tracker
		ev := envelope.Event{RoomID: "aaaaaaaa", Seq: 1, Type: envelope.ApprovalDecided,
			Payload: envelope.Must(envelope.ApprovalDecidedPayload{ApprovalID: "01M4A1B2C3D4E5F6G7H8J9K0MN", Decision: d})}
		got := tr.Events("aaaaaaaa", "Smana/ai-native-ref", ev)
		b, _ := json.Marshal(got)
		want := `[{"type":"room.approval_closed","room":"aaaaaaaa","approvalId":"01M4A1B2C3D4E5F6G7H8J9K0MN","decision":"` + d + `"}]`
		if string(b) != want {
			t.Fatalf("%s, want %s", b, want)
		}
		if again := tr.Events("aaaaaaaa", "Smana/ai-native-ref", ev); len(again) != 0 {
			t.Fatalf("a replay emitted %v", again)
		}
	}
	var tr Tracker
	for _, bad := range []envelope.ApprovalDecidedPayload{
		{ApprovalID: "ap1", Decision: "approved"},                                     // not a ULID: dropped
		{ApprovalID: "01M4A1B2C3D4E5F6G7H8J9K0MN", Decision: "bogus"},                 // a made-up decision: dropped
	} {
		if got := tr.Events("aaaaaaaa", "r", envelope.Event{RoomID: "aaaaaaaa", Seq: 2, Type: envelope.ApprovalDecided,
			Payload: envelope.Must(bad)}); len(got) != 0 {
			t.Fatalf("%+v emitted %v", bad, got)
		}
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/webhook/ -run TestApprovalClosed -count=1`
Expected: FAIL.

- [ ] **Step 3: The type**

`types` gains `"room.approval_closed"` as its last entry (thirteen). `Event` gains, after `ExpiresAt`:

```go
	Decision string `json:"decision,omitempty"` // approved | denied | expired | superseded
```

In `events()`, after the `ApprovalRequested` branch:

```go
	if ev.Type == envelope.ApprovalDecided {
		var p envelope.ApprovalDecidedPayload
		if json.Unmarshal(ev.Payload, &p) != nil || !ulidRE.MatchString(p.ApprovalID) || !slices.Contains(decisions, p.Decision) {
			return nil // a close the App cannot act on is not an event
		}
		return []Event{{Type: "room.approval_closed", Room: room, ApprovalID: p.ApprovalID, Decision: p.Decision}}
	}
```

`TestEvents`' `wantTypes` gains `"room.approval_closed"` at the end.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/webhook/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/webhook
git commit -m "feat(webhook): room.approval_closed, the thirteenth event"
```

### Task 10: the metadata payload becomes tagged, and the draft does not notice

**Files:**
- Modify: `internal/slackapp/slack.go` (`Metadata`, `DraftPayload`'s neighbours, new `ApprovalPayload`, `draftPayload()`, `approvalPayload()`, the two `Message` conversions in `Message`/`Thread`)
- Modify: `internal/slackapp/app.go` (`postDraft`, `threadDraft`, `reply`, `file`)
- Test: `internal/slackapp/app_test.go` (`TestMetadataShapes`; the `payload()`/`post.meta` helpers amended)

**Interfaces:**
- Produces: `Metadata{EventType string; EventPayload json.RawMessage}`; `Metadata.draftPayload() (DraftPayload, bool)`; `Metadata.approvalPayload() (ApprovalPayload, bool)`; `ApprovalPayload{ApprovalID, Class, Branch string}` with `approvalEventType = "factory_approval"`.

- [ ] **Step 1: Write the failing test**

```go
// §5: the metadata payload is tagged and decoded on demand. A draft's JSON on the wire is
// byte-identical to today's, and its hash still validates; a card's decodes as an approval payload;
// an unknown event_type, a card where a draft is expected, and an unreadable payload are all "not a
// draft" to threadDraft — no draft, no panic; "filed" is still seen and the newest valid draft wins.
func TestMetadataShapes(t *testing.T)
```

Assertions, exactly: `json.Marshal(&Metadata{EventType: draftEventType, EventPayload: mustJSON(t, DraftPayload{Repo: "Smana/ai-native-ref", Title: "t", Body: "b", SHA256: draftHash("Smana/ai-native-ref", "t", "b")})})` equals `[]byte(`{"event_type":"factory_draft","event_payload":{"repo":"Smana/ai-native-ref","title":"t","body":"b","sha256":"<hex>"}}`)` (byte-identical: build the expected string with the same `draftHash`); `threadDraft` finds it; a message whose payload is `{"approvalId":"ap1","class":"forge.push","branch":"agent/x"}` with `event_type` `factory_approval` yields `latest == nil`; a message with `event_type: "factory_draft"` and a card payload yields `latest == nil`; a message with `event_payload` being the JSON string `"nope"` yields `latest == nil`; and after two drafts plus a `factory_filed`, `threadDraft` returns `filed == true` and the second draft.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/slackapp/ -run TestMetadataShapes -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The tagged payload**

```go
// Metadata is what the App attaches to its own messages (R23); Slack keeps it off the visible text.
// EventPayload is tagged: the App decodes it on demand by EventType, so a card and a draft share one
// message shape (v3.x Slack push approval §5). A draft's bytes on the wire do not change.
type Metadata struct {
	EventType    string          `json:"event_type"`
	EventPayload json.RawMessage `json:"event_payload"`
}

// ApprovalPayload is a card's metadata (§5): what finds the card again without a search scope.
type ApprovalPayload struct {
	ApprovalID string `json:"approvalId"`
	Class      string `json:"class"`
	Branch     string `json:"branch"`
}

// approvalEventType marks a card the App posted for an approval.
const approvalEventType = "factory_approval"

// draftPayload decodes the payload as the draft the event type claims; false when it is anything
// else, which reads as "not a draft", the branch a foreign message already takes.
func (m *Metadata) draftPayload() (DraftPayload, bool) {
	if m == nil || m.EventType != draftEventType {
		return DraftPayload{}, false
	}
	var p DraftPayload
	if err := json.Unmarshal(m.EventPayload, &p); err != nil {
		return DraftPayload{}, false
	}
	return p, true
}

// approvalPayload decodes the payload as a card's; false when it is anything else.
func (m *Metadata) approvalPayload() (ApprovalPayload, bool) { …the same shape with approvalEventType… }
```

`postDraft` marshals its `DraftPayload` to `json.RawMessage` before building `Metadata` (a marshal error keeps today's `too_large`-style refusal), `threadDraft` uses `m.draftPayload()`, and `reply`/`file` take `p, ok := m.draftPayload()` and treat `!ok` as today's "not the App's draft" (`ignored`). Inside `SlackClient`, `slackAnswer`'s nested metadata struct becomes `EventType string` + `EventPayload json.RawMessage`, and the two conversions in `Message` and `Thread` copy both fields as they do today.

- [ ] **Step 4: Amend the rig's helpers**

`app_test.go`'s `post.meta` stays `*Metadata`; `rig.payload(p post) DraftPayload` becomes `p.meta.draftPayload()` (failing the test when false), and every direct `DraftPayload{…}` literal inside a `Metadata` becomes `json.RawMessage` built through one new helper `metaOf(t, eventType string, v any) *Metadata`. `fakeSlack.Post` stores the same pointer it was given, so no other change is needed.

- [ ] **Step 5: Run the package**

Run: `go test ./internal/slackapp/ -count=1`
Expected: PASS, `TestReactionFlow`, `TestReplyAddsTheAcceptanceCheck` and the rest of the draft suite included: they prove the draft path did not notice.

- [ ] **Step 6: Commit**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): the message metadata is tagged, and the draft's bytes do not move"
```

### Task 11: `chat.update` and a card post

**Files:**
- Modify: `internal/slackapp/slack.go` (`Slack` interface, `SlackClient.PostCard`, `SlackClient.Update`, `slackAnswer` unchanged)
- Test: `internal/slackapp/slack_test.go` (new `TestUpdateAndCardWire`), `internal/slackapp/app_test.go` (`fakeSlack` gains both methods)

**Interfaces:**
- Produces, on the `Slack` interface:
  - `PostCard(ctx context.Context, channel, threadTS, text string, blocks json.RawMessage, meta *Metadata) (ts string, err error)`
  - `Update(ctx context.Context, channel, ts, text string, blocks json.RawMessage) error`

- [ ] **Step 1: Write the failing test**

`slack_test.go` drives `SlackClient` against an `httptest.Server` and asserts the exact bodies:

```go
// §6: chat.update rewrites the App's own message in place; chat.postMessage with blocks posts the
// card. chat:write already covers both, and no metadata is touched by an update.
func TestUpdateAndCardWire(t *testing.T)
```

Cases: `Update(ctx, "C03", "1729.0001", "Approval needed", blocks)` posts to `/chat.update` with `{"channel":"C03","ts":"1729.0001","text":"Approval needed","blocks":[…],"unfurl_links":false,"unfurl_media":false}` and no `metadata` key; `PostCard` posts to `/chat.postMessage` with `thread_ts`, `text`, `blocks` and `metadata`; both send `Authorization: Bearer <Token()>`; a non-`ok` answer (`"error":"cant_update_message"`) returns an error whose text is Slack's code and never the token.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/slackapp/ -run TestUpdateAndCardWire -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The two calls**

Both are `c.url("chat.update")` / `c.url("chat.postMessage")` through `c.do`, with the body built as a map exactly as `Post` builds it plus `"blocks": blocks` when `len(blocks) > 0`. `PostCard` is separate from `Post` on purpose: `Post`'s seven call sites and the draft's wire bytes stay untouched, and the conversational design's proposal message rides `PostCard`/`Update` unchanged.

`fakeSlack` (in `app_test.go`) gains `func (f *fakeSlack) PostCard(...)` recording a `post` with `blocks` and its metadata (its `ts` from the same counter as `Post`), and `func (f *fakeSlack) Update(...)` replacing the seeded message and appending to a new `updates []post` slice, with a `failUpdates int` counter for the failure path. Add `blocks json.RawMessage` to the `post` struct.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/slackapp/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): chat.update and a Block Kit post on the Slack interface"
```

### Task 12: `channels.<id>.approvals`

**Files:**
- Modify: `internal/slackapp/config.go` (`type Channel`)
- Test: `internal/slackapp/config_test.go` (`TestLoadConfigApprovals`)

**Interfaces:**
- Produces: `Channel.Approvals bool` (`json:"approvals,omitempty"`).

- [ ] **Step 1: Write the failing test**

```go
// D14: who gets the affordance is a per-channel switch, false when absent; an unknown key is still
// refused, so an older App refuses a config that asks for cards rather than ignoring it.
func TestLoadConfigApprovals(t *testing.T)
```

Assertions: a config whose channel has no `approvals` loads with `Channels["C03"].Approvals == false`; `approvals: true` decodes true; `approvals: "yes"` fails to decode; an unknown channel key (`cards: true`) fails with the strict-decoder error; a channel with `approvals: false` and no `repositories` still fails as today.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/slackapp/ -run TestLoadConfigApprovals -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The field**

```go
type Channel struct {
	Repositories []string `json:"repositories"`
	MaxCostUSD   float64  `json:"maxCostUSD"`
	// Approvals draws this channel's forge.push approvals as a card with two buttons (v3.x Slack push
	// approval D14). Off, the thread keeps today's line and a press answers not_enabled.
	Approvals bool `json:"approvals,omitempty"`
}
```

No other validation: a channel with `approvals: true` and no repository to serve simply never matches a card.

- [ ] **Step 4: Run the package, then the gate**

Run: `go test ./internal/slackapp/ -count=1 && task check`
Expected: PASS, exit 0.

- [ ] **Step 5: Commit, push, open PR 3**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): channels.<id>.approvals, and the primitives a card rides"
git fetch origin && git rebase origin/main && git push -u origin feat/slack-card-primitives
gh pr create --title "feat(slackapp): the card's primitives — chat.update, tagged metadata, the approval webhook" --body "§4 and §5 of the design, and the seam CD7/CD9/CD20/CD29 consume: room.waiting_for_human carries the approval's ids, room.approval_closed is the thirteenth event, Slack gains PostCard and Update, the metadata payload is tagged while a draft's bytes stay identical (TestReactionFlow and TestReplyAddsTheAcceptanceCheck prove it), and channels.<id>.approvals defaults false. Nothing visible changes. Evidence: task check exit 0."
```

---

## Maku PR 4 — `feat/slack-decide-cards`: the card, the press and the teardown

### Task 13: the interactivity branch inside `POST /slack/events`

**Files:**
- Modify: `internal/slackapp/app.go` (`Events` gains the content-type dispatch; `handleInteraction` and the `interaction` struct live in the new file)
- Create: `internal/slackapp/interactions.go` (the interaction struct, `parseInteraction`, `handleInteraction`, the worker shell)
- Test: `internal/slackapp/interactions_test.go` (new), `internal/slackapp/app_test.go` (`appRig` gains `interact`/`postInteraction`)

**Interfaces:**
- Produces: `a.interaction(ctx context.Context, body []byte) string` returning the route's outcome, and `parseInteraction(body []byte) (interaction, bool)`; `actionApprove = "factory_approval_approve"`, `actionDeny = "factory_approval_deny"`.

- [ ] **Step 1: Write the failing tests**

`interactions_test.go` (its rig extends `appRig` with a form post and a signed body):

```go
// Invariant 5 over the second body shape: unsigned, stale and oversized interactivity posts are 401
// bad_signature, counted, and reach no broker call; the JSON events path still works from the same
// handler.
func TestSlackInteractivitySignature(t *testing.T)

// §6 step 3: a shape the App does not recognise answers 200 ignored, with no broker call and no
// message.
func TestInteractivityShape(t *testing.T)

// A press answered 503 busy must be retried by Slack and handled then, never read as a duplicate and
// dropped: the dedup id is forgotten on the busy path, as the events path already does (F-10).
func TestInteractivityBusyRetries(t *testing.T)
```

`TestSlackInteractivitySignature` cases: no `X-Slack-Signature` → `401`, `factory_slack_requests_total{route="interactions",outcome="bad_signature"}` +1, broker calls 0; a timestamp 6 minutes old, signed → `401`; a body over 1 MiB → `401`; a correctly signed form body → `200`; a correctly signed JSON events body in the same rig → `200` and today's handling (the draft path still runs).

`TestInteractivityShape` cases, each → `200` with `outcome="ignored"` (asserted through the rig's metrics fake) and zero broker calls: `Content-Type: application/json` carrying a form body; two `payload` fields; a form with no `payload`; `type: "view_submission"`; `block_actions` with two actions; an unknown `action_id`; a value without the `v1|` prefix; a value whose class is not `forge.push`; `team.id` another workspace; `is_enterprise_install: true`; a user id outside `^[UW][A-Z0-9]{2,20}$`; a channel id outside `^[CG][A-Z0-9]{2,20}$`. Three further cases: `container.message_ts` and `message.ts` both present and equal → the click proceeds; `container.message_ts` empty and `message.ts` set → the click proceeds with `message.ts`; both empty → `ignored`.

`TestInteractivityBusyRetries`: the rig's `Async` hook runs every queued function immediately, so the busy path needs the App set up as full or draining. The test is in the package: set `r.app.Async = nil`, then `r.app.poolOnce.Do(func() {})`, `r.app.poolMu.Lock()`, `r.app.queue = make(chan func(), 1)`, `r.app.queue <- func() {}` (one slot, full), `r.app.draining = false`, `r.app.poolMu.Unlock()`. Post the same signed interaction twice: both are `503` and `factory_slack_requests_total{route="interactions",outcome="busy"}` +2, and the broker saw nothing. Then restore `r.app.Async = func(f func()) { f() }` and post the same body a third time: it is `200`, handled once (`decided`), and the broker saw exactly one `Decide` call — which is only true because the 503 path forgot the dedup key.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestSlackInteractivitySignature|TestInteractivityShape|TestInteractivityBusyRetries' -count=1`
Expected: FAIL.

- [ ] **Step 3: The branch**

In `Events()`, after the verification it already does and **before** the JSON decode:

```go
		if ct, _, err := mime.ParseMediaType(r.Header.Get("Content-Type")); err == nil && ct == "application/x-www-form-urlencoded" {
			a.handleInteraction(w, r, body) // §6: the second body shape, one door and one lock
			return
		}
```

`handleInteraction` decodes the form from the bytes already verified (`url.ParseQuery(string(body))`, exactly one `payload` key, the payload under 64 KiB), parses a closed struct, checks the shapes above, looks the channel up (`a.Channels[ch]`, `ch.Approvals` true, else `200` `not_enabled` — answered locally, no broker call, and the clicker gets the room page line), takes the dedup key `"i|" + approvalID + "/" + user + "/" + actionID + "/" + actionTS` from `a.events`, then `enqueue`s the three-step work and answers `200` at once (Slack's 3 s); on `enqueue` false it **forgets the key** and answers `503`, so Slack's retry is handled. The work runs under `context.WithTimeout(context.WithoutCancel(ctx), handleTimeout)`, like `handle`'s.

`interaction` struct fields and the exact shapes are Global Constraints'; the comment names §6 step 3 for each.

- [ ] **Step 4: Run them**

Run: `go test ./internal/slackapp/ -run 'TestSlackInteractivitySignature|TestInteractivityShape|TestInteractivityBusyRetries' -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): interactivity is dispatched by content type inside the one signed door"
```

### Task 14: the broker call, the answer line, and the closed refusals

**Files:**
- Modify: `internal/slackapp/broker.go` (`Decide`, `Decision`, `DecisionResult`, the `BrokerAPI` addition in `app.go`)
- Modify: `internal/slackapp/interactions.go` (the worker: the call, the ephemeral, the metric outcome)
- Create: `internal/slackapp/card.go` (the refusal lines; the card itself is Task 15)
- Test: `internal/slackapp/interactions_test.go`, `internal/slackapp/broker_test.go` (`TestDecideCall`)

**Interfaces:**
- Produces on `BrokerAPI`: `Decide(ctx context.Context, d Decision) (DecisionResult, error)`; `slackapp.Decision{Team, User, Channel, MessageTS, ApprovalID, Branch, Decision string}`; `slackapp.DecisionResult{Result string}`; `refusalLine(code, user, pageURL string) string`.

- [ ] **Step 1: Write the failing tests**

```go
// §1 and §6: an Approve reaches the broker exactly once with the body of §1 and the clicker sees one
// answer; a Deny likewise; a thread reply saying "approve" reaches nothing (that is
// TestSlackNeverDecides' half, amended in Task 17).
func TestSlackDecidesForgePushOnly(t *testing.T)

// §6 step 4: Slack's own retry of one interaction is one broker call, one chat.update and one
// ephemeral. Two concurrent redeliveries of one press (the known race) are one decision too: the
// store's fence answers the second already_decided, and the record is one event.
func TestSlackInteractivityDedup(t *testing.T)

// Every refusal code has one fixed line, in a closed vocabulary that names no repository, branch,
// GitHub login or other person.
func TestSlackDecideRefusalLines(t *testing.T)
```

`TestSlackDecidesForgePushOnly` asserts the exact `Decision` the stub recorded: `Team: "T01ABC"`, `User: "U02DEF"`, `Channel: "C03"`, `MessageTS: "1729.0500"`, `ApprovalID: "01M4A1B2C3D4E5F6G7H8J9K0MN"`, `Branch: "agent/26zfnuxm"`, `Decision: "approved"`; one ephemeral whose `user` is `U02DEF` and whose `channel`/`thread` are the card's; and `factory_slack_requests_total{route="interactions",outcome="decided"}` +1. Its further cases: (a) a second card in the same thread for another approval id — pressing one decides only that one and updates only its message; (b) a press from a channel that still has `approvals: true` but whose `repositories` no longer lists the room's repo — the broker is still called (the App has no repository in the payload and must not invent one); (c) a `denied` press posts `Decision: "denied"`.

`TestSlackInteractivityDedup`: the same signed body twice sequentially → one broker call, one update, one ephemeral, and the second counts `duplicate`; then a distinct `action_ts` from the same user → a second broker call answered `already_decided` → the clicker sees the `already_decided` line once and the outcome is `duplicate`; finally the concurrent case: two goroutines post the same body, and the store (the stub, told to answer `already_decided` to the loser) leaves one decision — assert the stub's `decide` count is 1 or 2 with at most one `decided` answer, and exactly one `chat.update`.

`TestSlackDecideRefusalLines` iterates the thirteen refusal lines **and** the two success lines (`lineApproved`, `lineDenied`) and asserts each string exactly; then asserts that no line contains `"Smana/"`, `"agent/"`, `"@"` + a login, or the words `branch` outside `binding_mismatch`'s own sentence — i.e. that a refusal names no repository, branch, GitHub login or other person.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestSlackDecidesForgePushOnly|TestSlackInteractivityDedup|TestSlackDecideRefusalLines' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The call**

```go
// Decision is one press, as POST /api/slack/decisions takes it (§1 of the design). The App fills it
// from the signed click only; no field comes from the card's text.
type Decision struct {
	Team, User, Channel, MessageTS, ApprovalID, Branch, Decision string
}

// DecisionResult is the broker's closed code; Result is the decision when it recorded one.
type DecisionResult struct{ Result string }

// Decide posts one decision to the broker's human listener as the App's principal, with the same
// token cache and the same 401 retry every other call uses. A non-200 answer is an error: the
// route answers a closed code with 200 for every refusal, so anything else is transport.
func (b Broker) Decide(ctx context.Context, d Decision) (DecisionResult, error)
```

The body is `{"team":…,"user":…,"channel":…,"messageTS":…,"approvalId":…,"branch":…,"decision":…}` to `strings.TrimSuffix(b.URL, "/") + "/api/slack/decisions"`, `Content-Type: application/json`, `Authorization: Bearer <token>`; the 401 retry mirrors `post`'s loop (`b.Tokens.Invalidate()` then once more).

The worker, in order and each step independent:

1. `res, err := a.Broker.Decide(ctx, d)`; `err` → outcome `error`, line `refusalLine("unavailable", d.User, pageURL)`.
2. outcome: `res.Result` ∈ `approved`\|`denied` → `decided`; `already_decided` → `duplicate`; `not_supported` → `not_supported`; any other closed code → `refused`; a transport error → `error`.
3. `a.Slack.PostEphemeral(ctx, d.Channel, d.User, msgThreadTS, refusalLine(res.Result, d.User, pageURL))` — **always**, including on success (the success line names the outcome: `Decided: the push goes out.` / `Decided: nothing is pushed.`). A failed ephemeral is logged and counted `error`, never retried. `msgThreadTS` is the card's `ThreadTS` (the thread the App read for the card, Task 15); `pageURL` is `strings.TrimSuffix(a.RoomsURL, "/")` — the rooms page root, not the room's own URL: the click carries a channel and a message ts, and `Threads` maps room→thread only, so the App cannot name the room without a reverse index this plan does not add. The card's own context block already carries the room's exact URL, and the refusal's job is to send the person back to the page.
4. `chat.update` of the card to its inert form (Task 16's `inertCard`).

- [ ] **Step 4: The lines**

`card.go` holds the thirteen refusal lines of §6 verbatim plus the two success lines, with `refusalLine` returning the map's value for a known code and `unavailable`'s line for anything else:

```go
const (
	lineApproved   = "Decided: the push goes out."
	lineDenied     = "Decided: nothing is pushed."
	lineNotLinked  = "Not decided: <@%s> is not linked to a GitHub account here. Mention me with `link`, then press the button again."
	lineUnverified = "Not decided: the factory could not check your GitHub account just now. Press the button again in a minute."
	lineNotPermit  = "Not decided: only this room's approvers decide here. Ask an owner to add you as an approver."
	lineRepoPerm   = "Not decided: your GitHub account cannot write to this room's repository."
	lineFourEyes   = "Not decided: you prompted this run, and four-eyes asks another approver to decide it."
	lineDecided    = "Already decided; nothing changed."
	lineExpired    = "Not decided: the deadline had passed."
	lineBinding    = "Not decided: this card no longer matches the request. Open the room page: %s"
	lineNotSupport = "Not decided from Slack: this approval is on the room page only: %s"
	lineNotFound   = "Not decided: this request is no longer in the room's log."
	lineSealed     = "Not decided: this room is sealed."
	lineRateLimit  = "Too many presses just now; wait a minute."
	lineUnavailable = "Not decided: the factory could not be reached just now. Press the button again."
)
```

`refusalLine(code, user, pageURL string) string` formats the two placeholders: `<@user>` from the signed click, and `pageURL` (the rooms page root) for `binding_mismatch` and `not_supported`. `slackText`'s escapes apply to nothing here: every value is an id or a fixed string.

- [ ] **Step 5: Run them**

Run: `go test ./internal/slackapp/ -run 'TestSlackDecidesForgePushOnly|TestSlackInteractivityDedup|TestSlackDecideRefusalLines' -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): a press reaches the broker once and the clicker sees one closed line"
```

### Task 15: the card, when it is drawn, and the press that reads only the event

**Files:**
- Modify: `internal/slackapp/card.go` (`approvalCard`, `cardValue`, `parseCardValue`, `inertCard`, `cardTS`)
- Modify: `internal/slackapp/app.go` (`deliver` dispatches the card path; `line` keeps today's text for everything else)
- Test: `internal/slackapp/interactions_test.go` (`TestCardOnlyForForgePush`, `TestCardIsPostedInertPastItsDeadline`), `internal/slackapp/app_test.go` (`TestThreadMessagesCarryNoText` amended)

**Interfaces:**
- Produces: `approvalCard(e webhook.Event, roomsURL string, now time.Time) (text string, blocks json.RawMessage)`; `cardValue(approvalID, branch string) string` = `"v1|forge.push|<id>|<branch>"`; `parseCardValue(v string) (approvalID, branch string, ok bool)`.
- The card path needs **no wiring**: `newSlackApp` already hands the App `cfg.Channels`, so `Channel.Approvals` (Task 12) reaches it. Task 7's `TestSlackAppWiring` therefore stays the route's test and is not extended here.

- [ ] **Step 1: Write the failing tests**

```go
// §5: a card only when every condition holds. Everything else keeps today's line and has no button,
// and a press in a channel with approvals off answers not_enabled and reaches no broker.
func TestCardOnlyForForgePush(t *testing.T)
```

Cases, each asserting `rig.lastPost().blocks == nil` and today's exact text line: a `forge.pr` wait; a `mcp.write` wait; an `egress.new` wait; a wait with no `approvalId`; a wait with no `branch`; a channel with `approvals: false`; a channel whose `repositories` does not contain the event's `repo`; a room with no thread in `factory-slack-threads`. And the positive case: a `forge.push` wait in a channel with `approvals: true` serving the repo, in a room with a thread → one `PostCard` whose `text` is `Approval needed: push to the forge`, whose metadata is `{event_type:"factory_approval", event_payload:{approvalId, class, branch}}`, and whose blocks contain the four rows of §5 verbatim: the header, the `fields` section with `Class`/`Branch`/`Approval`/`Deadline`, the two-sentence section, and the three actions (`factory_approval_approve` primary, `factory_approval_deny` danger, an `url` button ending `/r/<room>`) plus the context block with the room URL. A second delivery of the same wait under a **fresh webhook-id** (`rig.webhook`, not `webhookReplay`) posts nothing new and calls `Update` with the same blocks — post-or-update by `approvalId`, found through `Thread`.

```go
// Review Focus 5: a wait whose deadline had already passed when the card is drawn is posted inert —
// prose and the room link, no buttons. The App decides only what it draws: the store still refuses
// a press on an older card (approval_expired).
func TestCardIsPostedInertPastItsDeadline(t *testing.T)
```

Assertions: with `ExpiresAt` a minute in the past (the rig's `now` is fixed), the posted card has the header, the fields and the section, a single `url` button, and **no** `factory_approval_*` action; and pressing the *previously posted* live card for the same approval still reaches the broker (the App did not become a fence).

`TestThreadMessagesCarryNoText` (amended, kept): it already asserts every posted message's text is a template of ids, states, codes and the room's URL. Extend it over the card: build a `forge.push` wait for a room whose `repo` and `branch` are the most hostile values the closed shapes allow, and assert the card's marshalled blocks contain neither the event's reason, nor any room text, nor `<!channel>`/`<@`, and that a branch outside `envelope.ValidBranch` never appears (it is dropped, so the card is not a card at all).

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestCardOnlyForForgePush|TestCardIsPostedInertPastItsDeadline|TestThreadMessagesCarryNoText' -count=1`
Expected: FAIL.

- [ ] **Step 3: The card body**

`approvalCard` returns the `text` fallback (`Approval needed: push to the forge`) and the blocks of §5, in this order, with these exact strings:

- `header` → `{"type":"header","text":{"type":"plain_text","text":"Approval needed: push to the forge"}}`
- `section` with `fields`, four `mrkdwn` fields: `*Class*\nforge.push`, `*Branch*\n<slackText(branch)>`, `*Approval*\n<approvalId>`, `*Deadline*\n<!date^<unix>^{date_short_pretty} at {time}|by <unix>>` — the unix value from `time.Parse(time.RFC3339, e.ExpiresAt)`; no clock in the App, no timezone in the message
- `section` → `If you approve: the push goes out and the run continues.\nIf you deny: nothing is pushed; the agent is told no and none of it runs.`
- `actions` → `Approve` (`style: primary`, `action_id: factory_approval_approve`), `Deny` (`style: danger`, `action_id: factory_approval_deny`), and `Open the room` (`type: button`, `url: strings.TrimSuffix(roomsURL,"/")+"/r/"+e.Room"`), each deciding button's `value` = `cardValue(e.ApprovalID, e.Branch)` (≤ 2 000 chars by construction)
- `context` → one `mrkdwn` element with the room URL

No `commit` label, no reason, no login, no other person's name (D5, D12). When `now.After(parsed deadline)` the actions block holds only the URL button and the section gains nothing (Review Focus 5).

`deliver` currently calls `a.line(e)` *before* it reads the thread map (`a.Threads.Get`). Hoist that read above the dispatch — the type check is `slices.Contains(webhook.Types(), e.Type)` and the room check `roomRE.MatchString(e.Room)`, unchanged — then, before `a.line(e)`:

```go
	if e.Type == "room.waiting_for_human" && a.cardWanted(e, th) { // §5's four conditions, the thread's included
		return a.postOrUpdateCard(ctx, th, e) // post-or-update by approvalId; ErrThreadTooLong posts and counts too_long
	}
```

- [ ] **Step 4: Run them**

Run: `go test ./internal/slackapp/ -run 'TestCardOnlyForForgePush|TestCardIsPostedInertPastItsDeadline|TestThreadMessagesCarryNoText' -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): a forge.push wait is one card, posted or updated by its approval id"
```

### Task 16: the teardown — inert on a close, inert after a click

**Files:**
- Modify: `internal/slackapp/card.go` (`inertCard`), `internal/slackapp/app.go` (`deliver`'s `room.approval_closed` path; `line`'s new case)
- Test: `internal/slackapp/interactions_test.go` (`TestCardCloseIsInert`)

**Interfaces:**
- Produces: `inertCard(e webhook.Event, roomsURL, line string) (text string, blocks json.RawMessage)` — the header and the fields, the outcome line, and **no** `actions` block.

- [ ] **Step 1: Write the failing test**

```go
// D10: room.approval_closed makes the card inert — no buttons, one fixed line — and a redelivery is
// idempotent. A thread too long to read is counted, never fatal.
func TestCardCloseIsInert(t *testing.T)
```

Assertions: for each of the four decisions, a `room.approval_closed` webhook finds the card by `approvalId` and calls `Update` once with blocks holding the header, the fields and one line (`approved by <@user>` isn't available to the close path, so the four lines are `Approved.`, `Denied.`, `The deadline passed.`, `No longer open.` — fixed, no names), and **zero** `factory_approval_*` actions; a redelivery calls `Update` once more with the same blocks (idempotent) and no `PostCard`; a room with no thread is `ignored`; `Thread` returning `ErrThreadTooLong` counts `error` and posts nothing, and the webhook answer is `200` so the broker does not disable the subscriber.

The redelivery needs a **fresh webhook-id**: `rig.webhookReplay()` re-sends the same `webhook-id`, which the App answers `duplicate` without doing anything, so it proves the delivery dedup and not the card's idempotence. Use two separate `rig.webhook(body)` calls (each signs with its own `evt_<seq>` id) and assert the second produces a second `Update` and no second `PostCard`.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/slackapp/ -run TestCardCloseIsInert -count=1`
Expected: FAIL.

- [ ] **Step 3: The close path**

In `deliver`, beside Task 15's card branch and after the same hoisted thread read:

```go
	if e.Type == "room.approval_closed" {
		return a.closeCard(ctx, th, e) // D10: best effort, counted, never retried into a loop
	}
```

`closeCard` reads the thread (`Thread`), finds the message whose `approvalPayload()` has `e.ApprovalID`, and `Update`s it with `inertCard`; no card found → `ignored`; a Slack failure → log `card update failed` with `approval`, `channel` and `err`, count `error`, and answer `200` for the webhook (the card is a view, not the fence). `line` gains `case "room.approval_closed": return fmt.Sprintf("The approval closed: %s. Room: %s", webhook.Clip("decision", e.Decision), url), true` for the thread that has no card.

A card decided from Slack is therefore written twice: once by the click's worker (Task 14, with the clicker's line) and once by this close (with `Approved.`), because the broker emits `approval_decided` for both surfaces (the design's flow diagram shows both `chat.update`s). The second write wins and is idempotent — it is not a duplicate to suppress.

Task 14's step 4 reuses `inertCard` for the post-click update, with `lineApproved`/`lineDenied`.

- [ ] **Step 4: Run it**

Run: `go test ./internal/slackapp/ -run TestCardCloseIsInert -count=1 && go test ./internal/slackapp/ -count=1`
Expected: PASS both.

- [ ] **Step 5: Commit**

```bash
git add internal/slackapp
git commit -m "feat(slackapp): a closed or decided approval leaves an inert card behind"
```

### Task 17: the invariant, renamed and narrowed; the App's docs

**Files:**
- Modify: `internal/slackapp/app_test.go` (`TestSlackNeverDecides` renamed and narrowed)
- Modify: `docs/security.md` (the Slack App section: invariant 8 as amended, the "One class, one surface" bullet, the refusal table's new codes, T12's residual), `docs/slack.md` (intro, manifest, Config, Flows, State, "What it never does", Live proof 5), `web/src/needs.ts` (the comment on line 5)
- Test: `internal/slackapp/app_test.go`

- [ ] **Step 1: Rename and narrow the test**

`TestSlackNeverDecides` becomes `TestSlackNeverDecidesOnAThreadReply`, keeping every existing case: a reply saying `approve`, `stop`, `/factory retry` and `approve <room>` in a draft's thread reaches no broker and decides nothing; a ✅ reply still files a draft. Add the two new cases the amendment implies: a reply in a thread that holds a **card** reaches neither `Decide` nor the broker's `Decide`, and a reaction on the card's message does nothing (only the two `action_id`s decide).

- [ ] **Step 2: Run it**

Run: `go test ./internal/slackapp/ -run TestSlackNeverDecidesOnAThreadReply -count=1`
Expected: PASS (the amendment is a rename plus two negative cases).

- [ ] **Step 3: The docs**

- `docs/security.md`: invariant 8's row becomes the spec's amended sentence, its Test cell `TestSlackNeverDecidesOnAThreadReply`, `TestSponsoredToolList`, `TestSlackDecidesForgePushOnly`; a bullet **One class, one surface.** naming the route, the two standings, four-eyes, the empty reason and the actor; the refusal table gains `not_linked`, `link_unverified`, `not_permitted`, `repository_permission`, `four_eyes`, `binding_mismatch`, `not_supported`, `not_found`, `sealed`; T12's residual notes it covers a compromised App pod casting one `forge.push` decision as a linked human.
- `docs/slack.md`: the intro line becomes "Steering, every other approval class, and merges stay in the web UI; a `forge.push` approval has a card you can decide". The manifest's `"interactivity": { "is_enabled": false }` becomes `"interactivity": { "is_enabled": true, "request_url": "https://factory-slack.<domain>/slack/events" }` — the same URL as events, with one sentence saying why (one door, one signature check); the scopes do not change (`chat:write` covers `chat.update`). The Config table gains `channels.<id>.approvals`; Flows gains the card flow and its teardown; State's closed outcome list gains `interactions`' outcomes (`decided`, `duplicate`, `refused`, `not_enabled`, `not_supported`, `ignored`, `bad_signature`, `busy`, `error`, `closed`, `too_long`) and the two switches; "What it never does" is rewritten with the one exception first and its four limits (one class, no reason, no answers, no steering); Live proof 5 points at the design's eight proofs and keeps the two Slack-fact checks it already asks for.
- `web/src/needs.ts`: the comment on line 5 ("the page's one decide path") says the page is still the only place every class is decided, and that a `forge.push` approval is also decidable from its Slack card — a comment, no behaviour, so `task ui:check`'s committed bundle changes only in its source map if at all; run `task ui:check` and commit whatever it produces.

- [ ] **Step 4: Run everything, push, open PR 4**

Run: `task check && task lint`
Expected: exit 0, 0 issues.

```bash
git add internal docs web
git commit -m "feat(slackapp): a forge.push approval is a card you can decide; invariant 8 says what remains"
git fetch origin && git rebase origin/main && git push -u origin feat/slack-decide-cards
gh pr create --title "feat(slackapp): approve a forge.push from the thread's card" --body "D1, D9, D10, D11, D12 of the design, plus invariant 8 as amended: interactivity inside the one signed POST /slack/events, the Block Kit card, post-or-update by approval id, one ephemeral answer per press in a closed vocabulary, and a best-effort inert teardown on a click and on room.approval_closed. Nothing else decides: no other class, no reason, no merge, no reply. Evidence: task check exit 0, task lint 0."
```

### Task 18: the release

**Files:** none (a tag).

- [ ] **Step 1: Tag the next minor after PR 4 merges**

Run: `git -C "$MAKU" fetch origin && git -C "$MAKU" log --oneline -1 origin/main`; confirm `main` holds PRs 1–4, then `git tag v0.<next>.0 && git push origin v0.<next>.0` (`v0.32.0` or the next free minor — take it from `git tag --list 'v0.*' | sort -V | tail -1`). The release workflow builds the images and the chart; the ai-native-ref pin in Task 24 reads it.

Expected: the tag exists, and the release workflow finishes green. Do not start Task 24 before the images are published: the switch-on's config would be refused by the previous image's strict decoder.

## ai-native-ref — PR A `feat/slack-push-approval-docs`: documentation and gates, nothing switched on

### Task 19: runbook 22

**Files:**
- Modify: `docs/runbooks/agent-factory/22-slack.md`

- [ ] **Step 1: §1's "Not enabled" row**

The manifest table's `Not enabled` value `interactivity, slash commands, socket mode` becomes `slash commands, socket mode`, and a line under it: the App now serves interactivity on the **same** Request URL as events (`https://factory-slack.<public_domain>/slack/events`), set in §4; a manifest carried from before this change must be updated in the console (**Interactivity & Shortcuts** → on → Request URL = the events URL) and the App reinstalled if Slack asks.

- [ ] **Step 2: §4 gains the interactivity URL**

After the events Request URL check, one owner step: **Interactivity & Shortcuts** → **Interactivity** on, **Request URL** = the same `/slack/events` URL, **Save**. Check: Slack accepts it (the App already verifies signatures there, so Slack's own URL verification is the events one that already passed).

- [ ] **Step 3: §5 gains the two keys and the event**

The three-places table gains a fourth row and the YAML block gains the two keys:

```yaml
# 1. slack-app/config.yaml — a channel that draws approvals as cards
teamID: T07J97G2K2P
channels:
  C0CC4M8SNVD: {repositories: [Smana/cloud-native-ref, Smana/ai-native-ref], maxCostUSD: 0.5, approvals: true}
# 3. room-broker/config.yaml — the decide route, and the close event. The events list changed, so the
# subscriber's generation is bumped and the broker restarted: webhooks apply at restart only.
human:
  slackDecide: {principal: slack-app, teamID: T07J97G2K2P}
webhooks:
  - name: slack-app
    generation: 2
    events: [room.task_triaged, room.run_started, room.waiting_for_human, room.pr_opened,
             room.verdict_posted, room.merged, room.reverted, room.budget_reached, room.ended,
             room.approval_closed]
```

with the paragraph the design fixes: the two switches fail differently — the broker's `human.slackDecide` is the authority (a card without it answers `unavailable`), the channel's `approvals: true` is who gets the affordance; turning the channel off is the fast rollback. `human.slackDecide` needs `human.access` and names one of `human.mcp.sponsored`. Because this PR changes the `webhooks` list, it bumps that entry's `generation` (one more than it stands at today) and restarts the broker explicitly — a `webhooks` change is read at startup, so a `configMapGenerator` roll alone is not guaranteed to be the read that counts, and a subscriber the emitter disabled stays disabled until the bump. Then:

```bash
kubectl -n agent-system rollout restart deploy/room-broker
kubectl -n agent-system rollout status deploy/factory-slack-app deploy/room-broker
```

Check: both rollouts complete and `kubectl -n agent-system logs deploy/room-broker | head` shows it read its config with the new subscriber list.

- [ ] **Step 4: §7 gains the eight checks and the symptoms**

§7's table gains a row per proof L1–L8 (the same `Do`/`Expected` wording as the design's table), pointing at the design for the evidence lines; the symptom table gains four rows: `not_permitted` (the clicker is not the room's owner or an approver: the CR's `spec.members[].approver`, and a ZITADEL admin outside the CR cannot decide from Slack — D15), `repository_permission` (the linked GitHub login has read only), `four_eyes` (the clicker prompted the run), and `result=unavailable` (the broker's switch is off, or the store, the room or the log could not be read: check `human.slackDecide` first, then the broker's logs).

- [ ] **Step 5: Check**

Run: `./scripts/ci/validate-links.sh && ./scripts/ci/verify-doc-paths.sh`
Expected: both silent.

### Task 20: runbook 18

**Files:**
- Modify: `docs/runbooks/agent-factory/18-factory-interfaces.md`

- [ ] **Step 1: The diagram and its caption**

The `flowchart LR`'s `A -->|"/mcp, token of the machine user"| B` edge gains a sibling `A -->|"POST /api/slack/decisions, same listener"| B`, and the caption under the diagram says the App now calls one route besides `/mcp`, on the same human listener and the same Cilium network policy, so H4 and the host pin do not move.

- [ ] **Step 2: The subscription list**

Where §5 declares the webhook's events, the list gains `room.approval_closed` (thirteen types), with one sentence: a subscriber that does not list it never receives it, so a channel that draws cards needs the App's entry to list it; and the App's `channels.<id>.approvals` is the other half (runbook 22 §5).

- [ ] **Step 3: Check**

Run: `./scripts/ci/validate-links.sh`
Expected: silent.

### Task 21: ADR-0049 and ADR-0059 FA7

**Files:**
- Modify: `website/content/docs/decisions/0049-room-client-and-human-auth.md`, `website/content/docs/decisions/0059-factory-from-your-coding-agent.md`

- [ ] **Step 1: ADR-0049**

In **Consequences → Negative**, the consequence "no phone approvals" becomes: "no phone approvals except `forge.push`, which a Slack card may decide under the same fence and the same four-eyes; every other class and every reason stays browser-only". Add one paragraph under it, dated 2026-11-05: the decision (a broker-served UI, a session the broker re-validates, nothing approving from a place a local agent drives) is untouched, and Slack is not such a place — the click is Slack-signed, and the human is resolved from a link only that human could have confirmed. `lastVerified` becomes `2026-11-05`.

- [ ] **Step 2: ADR-0059 FA7**

The FA7 row's text becomes `Approvals stay on the room page ([ADR-0049](…)); the card links to them — except a forge.push approval, which the thread's card may decide`. `lastVerified` unchanged unless the page's other content moved.

- [ ] **Step 3: Check**

Run: `cd website && hugo --gc --minify`
Expected: builds; no unresolved `relref`.

### Task 22: the user guide

**Files:**
- Modify: `website/content/docs/use/slack.md`

- [ ] **Step 1: The Act row and the new section**

The step table's **Act** row becomes: "Approve a `forge.push` from the card in the thread (two buttons), or open the room page for every other approval, an answer or a steer; approve the pull request on GitHub to merge it." Then a `## Approve a push from the thread` section after `## Edit the draft`: what the card shows (the class, the destination branch, the approval's id, the deadline and the room link — and no commit: the pushed commit arrives after the fact, in the pull request), who may press it (the room's owner or one of its approvers *and* someone who can write the repository, and never the person who prompted the run when four-eyes is on), what a refusal means (one line, only to you: not linked, not an approver, no write, four eyes, expired, already decided), and that **merging is still your review on GitHub**: the push approval releases one push and never a merge. `lastVerified: 2026-11-05`.

- [ ] **Step 2: Check**

Run: `task docs`
Expected: the site builds, `verify-doc-paths.sh` and `check-reader-first.py` pass (no status tags, no session history).

### Task 23: the gates and the alerts

**Files:**
- Modify: `scripts/ci/tests/test-factory-slack-switchon.py`, `scripts/ci/tests/test-room-broker-suspend.py`
- Modify: `observability/base/agent-platform/vmrule-agent-factory.yaml`
- Create: `scripts/ci/tests/test-agent-factory-slack-alerts.sh`
- Modify: `scripts/ci/tests/test-agent-alert-annotations.sh` (the new alerts' annotations)

- [ ] **Step 1: `test-room-broker-suspend.py`**

`minus_switches`'s docstring and body admit `human.slackDecide` alongside `mcp` and `slackLink`:

```python
def minus_switches(cfg):
    """The config without the keys a gcp-0 session may declare: suspend, webhooks, human.mcp,
    human.slackLink and human.slackDecide."""
    out = {k: v for k, v in cfg.items() if k not in ("suspend", "webhooks")}
    out["human"] = {k: v for k, v in out["human"].items() if k not in ("mcp", "slackLink", "slackDecide")}
    return out
```

and the check's description and the module docstring say `human.slackDecide` too.

- [ ] **Step 2: `test-factory-slack-switchon.py`**

Three new checks, each passing **before** the switch-on (they assert consistency, never presence):

```python
# D14's two switches: each is optional, and when one side is on the other must be able to answer.
decide = broker["human"].get("slackDecide")
checks["human.slackDecide, when set, names the sponsored principal and the App's team"] = decide is None or (
    decide["principal"] == principal["name"] and decide["teamID"] == app["teamID"])
checks["every channel's approvals, when set, is a bool"] = all(
    isinstance(c.get("approvals", False), bool) for c in app["channels"].values())
checks["a channel drawing cards has room.approval_closed in the broker's webhook list"] = not any(
    c.get("approvals") for c in app["channels"].values()) or "room.approval_closed" in hook["events"]
```

- [ ] **Step 3: The two alerts**

In `observability/base/agent-platform/vmrule-agent-factory.yaml`'s `agent-factory` group:

```yaml
        - alert: SlackDecisionsSpike
          expr: sum(increase(maku_rooms_slack_decisions_total{result="approved"}[10m])) > 5
          labels:
            severity: warning
          annotations:
            summary: "More than five forge.push approvals were decided from Slack in ten minutes"
            description: "The design's per-(team,user) clause is not computable from this metric's labels — maku_rooms_slack_decisions_total carries only {result, decision} — and this aggregate is its computable stand-in: six approvals in ten minutes from anywhere is already worth reading. Take the broker's 'slack decision' log lines (room, approval, user, principal, result, seq) for those decisions and the room log for the approvals they closed. An unexpected burst is the shape of a compromised App pod casting decisions as linked humans (the design's accepted residual, alerted here). Whoever reads it also checks the rooms' policies: no forge.push approval should ever be decided from Slack in an unattended room, and that half is a log read too."
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/22-slack.md#7-verify-end-to-end"
            dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
        - alert: SlackCardUpdatesFailing
          expr: sum(rate(factory_slack_requests_total{route=~"interactions|webhooks", outcome="error"}[10m])) > 0
          for: 1h
          labels:
            severity: warning
          annotations:
            summary: "The Slack App has failed an approval-card update for an hour"
            description: "The cards are then lying about being live, which is worse than not having them (D10). This is an aggregate over both routes: factory_slack_requests_total carries {route, outcome} and no approval id, so a single flapping card and a hundred failures read the same here — take the App's 'card update failed' lines (approval, channel, err) to tell them apart. Causes: a revoked chat:write, a removed message, Slack refusing metadata. The decisions themselves still land — the store, not the card, is the fence."
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/22-slack.md#7-verify-end-to-end"
            dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
```

Both expressions are aggregates, and that is the decision this task records: `maku_rooms_slack_decisions_total` carries only `{result, decision}` and `factory_slack_requests_total` only `{route, outcome}`, so the design's per-`(team,user)`, per-room-policy and per-approval clauses have no computable form from these metrics. **No `user`, `principal`, `room` or `approval` label is added** to either metric: they are unbounded, and a broker metric with a per-person label is a cardinality and a privacy problem the design does not ask for. Each alert's description says what the log answers instead. Record the limitation in the PR body so the owner can widen a metric deliberately if they prefer. Both alerts point at the same runbook anchor (`#7-verify-end-to-end`), which Task 19 creates and `verify-doc-paths.sh` checks.

- [ ] **Step 4: The gate**

`scripts/ci/tests/test-agent-factory-slack-alerts.sh` follows `test-agent-factory-budget-alerts.sh`'s shape (promtool, synthetic series, annotations stripped): `maku_rooms_slack_decisions_total{result="approved"}` at 5 in ten minutes stays silent, at 6 fires; `factory_slack_requests_total{route="interactions",outcome="error"}` at 1 fires only after the hour. Add it to `scripts/ci/run-tests.sh`'s list if the runner enumerates files, else confirm it is picked up by the glob. Add both alerts' `summary`/`description`/`runbook_url`/`dashboard` to `test-agent-alert-annotations.sh`'s table.

- [ ] **Step 5: Run the gates**

Run: `task test && task check`
Expected: exit 0, every new check printed `ok`.

- [ ] **Step 6: Commit, push, open PR A**

```bash
git add docs website scripts observability
git commit -m "docs(slack): approve a forge.push from the thread, and the gates the two switches need"
git fetch origin && git rebase origin/main && git push -u origin feat/slack-push-approval-docs
gh pr create --title "docs(slack): a forge.push approval is decidable from its card" --body "The documentation half of the design (runbooks 18 and 22, ADR-0049's consequence, ADR-0059 FA7, the user guide) plus the gates and alerts the two switches need. Nothing is switched on: no config key changes behaviour, both switches stay absent, and every new gate passes with them absent. Evidence: task check exit 0."
```

---

## ai-native-ref — PR B `feat/slack-push-approval-switch-on`: the switches, on owner go

### Task 24: the switch-on — **STOP for the owner's go**

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml` (tag + digest), `tooling/base/agent-factory/helm-values-configmap.yaml` (image tag@digest) — the Task 18 release
- Modify: `tooling/gcp-0/agent-factory/slack-app/config.yaml` (`approvals: true` on the one channel), `infrastructure/gcp-0/room-broker/config.yaml` (`human.slackDecide`, `room.approval_closed`, and that webhook entry's `generation` bumped)

- [ ] **Step 1: STOP — ask the owner, and wait**

Post this, and do nothing else until the answer is a go:

> Ready to switch on `forge.push` Slack decisions on gcp-0, one channel (`C0CC4M8SNVD`), on Maku `v0.<next>.0`. This changes a live cluster in four ways: the broker runs the new migration (`approvals.binding_branch`, additive and defaulted); the broker serves `POST /api/slack/decisions`; the App draws cards with **live Approve/Deny buttons** in that channel and calls `chat.update`; the thread gains `room.approval_closed`. Merging stays a GitHub review of the current head, and no other class is decidable. You also need to set **Interactivity & Shortcuts → Request URL = https://factory-slack.<public_domain>/slack/events** in the Slack console (runbook 22 §4). Go, or hold?

No merge, no Slack console change, no kubectl write happens before an explicit go.

- [ ] **Step 2: Bump the pin (after the go)**

Take the tag and digest from the Task 18 release (`crane digest <image>` or the release's output): `flux/sources/ocirepo-agent-factory.yaml`'s `spec.ref.tag` and `spec.ref.digest`, and `tooling/base/agent-factory/helm-values-configmap.yaml`'s `image.tag` as `<version>@sha256:<digest>`. Run `python3 scripts/ci/tests/test-agent-factory-pins.py` until it is silent (the chart's appVersion and the image tag must agree).

- [ ] **Step 3: The two keys**

`tooling/gcp-0/agent-factory/slack-app/config.yaml`: the one channel becomes `C0CC4M8SNVD: {repositories: [Smana/cloud-native-ref, Smana/ai-native-ref], maxCostUSD: 2, approvals: true}`. `infrastructure/gcp-0/room-broker/config.yaml`: under `human`, beside `slackLink`,

```yaml
  # The App's one deciding route (v3.x Slack push approval D14, agent-platform v0.<next>.0): a
  # forge.push approval is decidable from its card, resolved to the linked human's room standing and
  # repository write. The principal is human.mcp.sponsored's slack-app, the team the App's own. Needs
  # human.access. Off: the path is a 404 and a card's press answers unavailable.
  slackDecide:
    principal: slack-app
    teamID: T07J97G2K2P
```

and the `webhooks[slack-app].events` list gains `room.approval_closed` as its last entry, with that entry's `generation` bumped (one more than it stands at today) — a `webhooks` change applies at the broker's startup, and a subscriber the emitter disabled stays disabled until the bump.

- [ ] **Step 4: The gates, offline**

Run: `task check`
Expected: exit 0, `test-factory-slack-switchon.py`'s and `test-room-broker-suspend.py`'s new checks `ok`, `test-agent-factory-pins.py` silent. This is the last offline step.

- [ ] **Step 5: Merge, then the owner's console step**

Commit `feat(gcp-0): decide a forge.push approval from its Slack card`, push `feat/slack-push-approval-switch-on`, open the PR with the rollback order from the design (§Rollout: App first, then the console, then the broker), and merge only on the owner's go. Then, in this order:

```bash
kubectl -n agent-system rollout restart deploy/room-broker   # the webhooks list is read at startup, and it changed
kubectl -n agent-system rollout status deploy/room-broker deploy/factory-slack-app --timeout=5m
kubectl -n agent-system logs deploy/room-broker | grep -c 'migrat' # the migration ran once
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://factory-slack.<public_domain>/slack/events # 401
```

Expected: both rollouts complete; the unsigned probe is `401` (the door is the same door). Then the owner sets the interactivity URL (runbook 22 §4), and Task 25 begins.

---

### Task 25: the live proofs — **STOP for the owner's go before each cluster action**

**Files:**
- Create: `docs/runbooks/agent-factory/results-slack-push-approval-2026-11-05.md` (the transcript)

- [ ] **Step 1: STOP, and record the setup**

Ask the owner for a go for the proofs, naming the room and the `forge.push` class the run uses. Then one channel (`C0CC4M8SNVD`), one room, one attended policy. Keep two `maku watch <room>` sessions and one `kubectl -n agent-system logs -f deploy/room-broker | grep 'slack decision'` open, plus the App's log and its `:9090/metrics` (`kubectl -n agent-system port-forward deploy/factory-slack-app 9090`).

- [ ] **Step 2: L1 — a double press and a replay**

Press **Approve** twice quickly, then replay the signed interaction (re-POST the captured body with the same `X-Slack-Request-Timestamp`/`X-Slack-Signature` — the App's clock is the signing time, so re-sign only if Slack's own retry would). Expect one decision, the card inert once, one answer to the clicker. Evidence: one broker `slack decision … result=approved seq=N`; `maku_rooms_slack_decisions_total{result="approved"}` +1 and `{result="already_decided"}` +1; one `approval_decided` in `maku watch`; `factory_slack_requests_total{route="interactions",outcome="decided"}` +1 and `{outcome="duplicate"}` +1.

- [ ] **Step 3: L2 — past the deadline, before and after the sweep**

In a room whose sweep interval is longer than the wait, let the card's deadline pass, press **Approve** before the sweep and again after it. Expect `approval_expired` both times, no decision, one `approval_decided decision=expired`. Evidence: two broker lines `result=approval_expired`; `maku_rooms_slack_decisions_total{result="approval_expired"}` +2; the row `expired` (`maku watch` shows the expired close and no approval decision).

- [ ] **Step 4: L3 — the wrong human, three ways**

Three presses: a Slack user with no link; a linked user who is not an approver in the room; a linked approver whose GitHub login cannot write the repository. Expect `not_linked`, `not_permitted`, `repository_permission`, no decision. Evidence: one App log line per press with its code; three broker lines with the same codes; one `maku_rooms_slack_decisions_total` series each; the only `approval_decided` is the eventual legitimate one.

- [ ] **Step 5: L4 — four eyes**

The person who prompted the run presses **Approve**; a second approver presses afterwards. Expect `four_eyes`, then decided. Evidence: broker `result=four_eyes` then `result=approved`; the room log names only the second human (`actor_id=human:<sub>`).

- [ ] **Step 6: L5 — tampering, unsigned, cross-room**

Press a card whose signed body is tampered with (change the value's branch), then POST an unsigned body to the same URL, then press a card whose `approvalId` belongs to another room (crafted the same way). Expect `401` for the unsigned; the tampered value gives `binding_mismatch` at the broker (its shape passes, its branch does not); the cross-room value gives `binding_mismatch`, and no event lands in either room. Evidence: `factory_slack_requests_total{outcome="bad_signature"}` +1; broker `result=binding_mismatch` twice; no `approval_decided` in either room.

- [ ] **Step 7: L6 — another class keeps today's line**

Provoke a `forge.pr` or `shell.high` approval in the same thread. Expect a text line with the room link and **no** button, beside the `forge.push` card that keeps its buttons. Evidence: the thread as rendered; `factory_slack_requests_total{route="interactions"}` unchanged; `maku_rooms_slack_decisions_total{result="not_supported"}` stays at 0 from real clicks.

- [ ] **Step 8: L7 — the supersede race, both ways**

Approve on the card in the same second the room page answers the call, twice over (once the page wins, once the card wins). Expect exactly one decision each time; the loser is `already_decided` or `superseded`; the card goes inert either way. Evidence: two `approval_decided` across the two races, one per approval; the App's card update counted twice and failing zero times.

- [ ] **Step 9: L8 — a card that cannot be updated**

Revoke the bot's `chat:write` (or point the App at a Slack stub that answers 5xx for `chat.update`), then decide a card. Expect the decision to land, the failure logged and counted, and the stale card's button afterwards to answer `already_decided`. Evidence: the broker log's decision; the App's `card update failed` line; `factory_slack_requests_total{outcome="error"}` +1; the stale press yields `already_decided`, not a second event.

- [ ] **Step 10: Teardown, and the record**

Restore `chat:write`. Write the transcript to `docs/runbooks/agent-factory/results-slack-push-approval-2026-11-05.md`: each proof with its log line, metric value and room event, and one row per proof in a table with `Do`/`Expected`/`Seen`, and state the rollback that was **not** taken and why. Open it as its own PR (`docs(runbooks): the Slack push approval's live proofs`). Then ask the owner whether a second channel is widened (the design's step 4) — do not widen it in this plan.

---

## Self-review

- **Spec coverage.** D1 Tasks 13–17; D2 Tasks 5–7; D3 Tasks 5, 6; D4 Task 5; D5 Tasks 1–3; D6 Tasks 13–15; D7 Task 6; D8 Task 6; D9 Task 15; D10 Tasks 14, 16; D11 Task 13; D12 Tasks 6, 14; D13 Tasks 4, 5; D14 Tasks 4, 12, 24; D15 Task 5 (+ its naming of the residual in Task 17). §Contracts 1: Tasks 5–7; 2: Tasks 5–6; 3: Tasks 1–3; 4: Tasks 8–9; 5: Tasks 10–12, 15; 6: Tasks 13–16; 7 (the seam): Tasks 10–12 supply `Update`, the tagged payload and the interactivity branch; no task consumes the conversational design's proposals. §Security: the invariant's amendment is Task 17, the anti-oracle rule Task 14, the App-pod residual Task 17 and Task 23's alert. §Observability: the three metrics in Tasks 4, 13–16, the three log lines in Tasks 14 and 16, the two alerts in Task 23. §Rollout's order is Tasks 18 → 24 → 25, and its rollback order is Task 24's PR body. §Test matrix: rows 1–2 → Task 13; 3–4 → Task 14; 5 → Task 15; 6 → Task 16; 7 → Task 15; 8 → Task 10; 9 → Task 17; 10–11 → Task 5; 12 → Task 6; 13 → Task 5; 14–17 → Task 6; 18 → Task 5; 19 → Task 7; 20 → Task 7 (a verify step: the list does not change); 21 → Task 7; 22 → Task 2; 23 → Task 8; 24 → Task 9; 25 → Task 4; 26 → Task 12; 27 → Task 7. §Live proofs: Task 25, one step per proof, plus the teardown. §Documentation amendments: Maku's four pages in Tasks 7 and 17, ai-native-ref's five in Tasks 19–23.
- **Review Focus coverage.** 1 → Task 13 `TestInteractivityBusyRetries`; 2 → Task 14 `TestSlackInteractivityDedup`'s concurrent case; 3 → Task 13 `TestInteractivityShape`'s two `message_ts` cases; 4 → Task 15 `TestCardOnlyForForgePush`'s unserved-repository case and Task 14 `TestSlackDecidesForgePushOnly`'s case (b); 5 → Task 15 `TestCardIsPostedInertPastItsDeadline`.
- **Step ambiguity.** Every code step names the file, the symbol and the exact values; every test step names the test and its assertions; every verification step names the command and its expected output. Two steps deliberately leave the body to the implementer or the spec: Task 5's `resolve` (the order and the codes are the contract; the code is its transcription) and Task 15's block JSON (the spec fixes the texts, the plan fixes the shapes and the two action ids).
- **Type consistency.** `envelope.ValidBranch`/`ApprovalRequestedPayload.Branch` (Tasks 1, 2, 3, 8, 15); `store.Approval.BindingBranch` (Tasks 2, 3, 5); `humanapi.SlackDecider`/`SlackDecision`/`SlackDecideStore` (Tasks 4, 5, 7); `config.SlackDecideConfig`/`Channel.Approvals` (Tasks 4, 12, 24); `webhook.Classes`/`Decisions`/`Event.{ApprovalID,Class,Branch,ExpiresAt,Decision}` (Tasks 8, 9, 15, 16); `slackapp.Metadata{EventType,EventPayload}` with `draftPayload()`/`approvalPayload()` (Tasks 10, 15, 16); `Slack.PostCard`/`Slack.Update` (Tasks 11, 14–16); `Broker.Decide(ctx, Decision) (DecisionResult, error)` (Tasks 14); `refusalLine`/`inertCard`/`approvalCard`/`cardValue`/`parseCardValue` (Tasks 14–16); `rooms_slack_decisions_total` (Tasks 4, 25).
- **Proportion.** Twenty-five tasks against a 697-line spec; code blocks are the spec's fixed copy (the trigger, the lines, the card's texts) and signatures, not implementations.
- **Recorded decisions, for the owner.** Two, both landing in Task 23 and neither changing a PR boundary. (a) `SlackDecisionsSpike` as designed (more than five `approved` in ten minutes from one `(team,user)`, or any `approved` in an unattended room) has no computable form from `rooms_slack_decisions_total{result, decision}`: the per-`(team,user)` clause is not computable from this metric's labels, and the aggregate is its computable stand-in. `SlackCardUpdatesFailing` has the same shape on `factory_slack_requests_total{route, outcome}`: it cannot tell one flapping card from a hundred failures. Both ship as aggregates, with the limitation in the alert's own description and the PR body, and **no** `user`/`principal`/`room`/`approval` label is added — that is an unbounded, privacy-bearing label set the design does not grant. If the owner prefers the design's exact rules, a metric needs a label: a change to §Observability, not to this plan. (b) The two refusal lines that name a URL (`binding_mismatch`, `not_supported`) print the rooms page root, not the room's own URL: a click carries a channel and a message ts, `Threads` maps room→thread only, and adding a reverse index is scope this amendment does not need. The card's own context block still carries the room's exact URL (§5, Task 15), so no reader loses the way back.
