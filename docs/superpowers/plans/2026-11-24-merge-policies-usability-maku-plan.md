# Merge policies usability, Maku Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** A maintainer reads why a pull request merged or waited without opening the page source, sees what each policy allows in plain words, and promotes a policy with one click and one merge.

**Architecture:** One table of words per reason replaces five maps. A new read endpoint lists recent decisions from the records the gate already writes. The settings pages are rebuilt on that endpoint and on a backtest that re-decides recorded diffs with the existing evaluator. Promotion gains one write: the factory App opens a pull request against the GitOps repository.

**Tech Stack:** Go (broker `internal/humanapi`, factory `internal/factory`), TypeScript (`web/`, vitest, the offline preview under `web/preview`), Helm.

**Spec:** `docs/superpowers/specs/2026-11-24-merge-policies-trust-and-usability-design.md` in ai-native-ref, sections 3 to 5 (ids `U`, `W`).

## Global Constraints

- Executed in the Maku repository, after the safety plan's PRs A to D are merged. Paths below are Maku's.
- `task check` exits 0 before every commit and push. Conventional commits, no trailers, squash-merge.
- The user-facing word is **policy**. `class=` stays in the decision record; no metric or reason code is renamed in this plan.
- Every string a person reads comes from the reason table of Task 1.
- `web/DESIGN.md` governs the pages: tokens, type scale and components already there; no new dependency.
- Every page change ships with its `web/preview` fixture, a vitest, and a screenshot at 1280 px and 390 px attached to the PR.
- Pages work without the new endpoints (an older factory): they say what is missing, they do not break.
- Maku writes exactly one thing to a repository in this plan: the promotion pull request of Task 12, behind `Factory.spec.gitops`.

## Status: merged, not yet released or validated live (2026-11-25)

The implementation checkboxes below are complete. The pull requests were squash-merged in dependency order:

| Plan item | Maku pull request | Merge commit |
|---|---|---|
| E, readable decisions | [#687](https://github.com/Smana/maku/pull/687) | `30f96b7f` |
| F, decision CLI and pause controls | [#689](https://github.com/Smana/maku/pull/689) | `ec95c5b1` |
| G and H, CRDs, guide and observability | [#695](https://github.com/Smana/maku/pull/695) | `1470f1b8` |
| I, settings UI and backtest | [#691](https://github.com/Smana/maku/pull/691) | `a8185845` |
| J, promotion workflow | [#692](https://github.com/Smana/maku/pull/692) | `0dccddbd` |

#690 was closed by stacked-branch maintenance and replaced by #695 without losing the change. Full local `task check`, pull-request CI, and post-merge Maku `main` CI passed. #691 contains the required light/dark screenshots at 1280 px and 390 px. No live-cluster validation or real GitHub promotion was performed. Maku `v0.53.11` predates all of these merges.

### Live validation handoff

Deploy a release containing #687 through #692 before attempting these checks. Keep the policies in shadow until the specific promotion drill. Record the release, cluster, repository, pull request heads, decision JSON and screenshots as evidence.

- [ ] **Readable decision:** on a scratch pull request over a line cap, confirm the gate comment, room, Slack and `maku policy explain <owner/name>#<PR>` name the matched policy and show the measured value and limit. Confirm `maku policy list --repository <owner/name> --output json` returns the same decision.
- [ ] **Pause and resume:** run `maku policy pause --repository <owner/name> --reason "live validation"` and `maku policy resume --repository <owner/name>` against a GitOps-enabled Factory. Each opens a pull request but never merges it; while paused, shadow decisions still record and maintainer approve-to-merge still works.
- [ ] **CRD admission and status:** submit the invalid `diffShape`, negative cap, unanchored pattern and invalid low-evidence combinations from Task 5. Admission names the object, field and fix. Check the new printer columns, binding `servedMode`, and `Ready=False` on a refused generation or binding.
- [ ] **Observability:** confirm `maku_factory_policy_considered_total` carries repository, policy and reason; the new dashboard panels populate; a refused binding for 15 minutes and a paused policy for 24 hours fire their alerts. Use test time windows or recording-rule evaluation rather than leaving production policies paused.
- [ ] **Decision-centered UI:** check recent decisions, repository summaries, the policy editor, presets and backtest against an older factory and the new one. Missing endpoints explain themselves; missing backtest diffs and original oracle findings read `unknown`, never `unchanged`.
- [ ] **Responsive and accessible UI:** repeat the 1280 px and 390 px, light/dark screenshots against the deployed UI. At 390 px, Chromium must report equal viewport and document widths with no horizontal overflow; keyboard focus and the mode radio group must remain usable.
- [ ] **Promotion with GitOps disabled:** `maku policy promote` returns the blockers with counts when ineligible, and returns a `gh pr create` command without writing a branch when `Factory.spec.gitops` is unset.
- [ ] **Promotion with GitOps enabled:** promote an eligible shadow policy. The factory opens exactly `factory/promote-<repository>-<policy>` with the one-line change and evidence-rich body; it does not merge. The record remains `pr_opened`, then closes only after the served binding becomes live.
- [ ] **Unmerged promotion:** close a second promotion pull request without merging. Its record becomes abandoned automatically and another promotion can be requested; there are no manual Merged or Abandon controls.
- [ ] **Drill and rollback:** run `maku policy drill <owner/name>#<PR>` for a merged promotion, confirm the labelled rollback drill and current mode, then follow the repository's recovery procedure. Do not roll back a production policy merely to complete the checklist unless the owner approved that drill.

The generic proof check, rendered-manifest proof and tamper checks remain deferred; this live checklist does not claim them.

## Review Focus

1. **A decision with numbers.** A pull request over the line cap reads "`docs`: 131 lines changed, limit 100" in the comment, the room, Slack and `maku policy explain`. Pinned in Task 2.
2. **The policy named is the one matched.** A task predicted `review` and merged under `docs-links` reads `docs-links` in the status and the comment. Pinned in Task 2.
3. **The editor cannot produce a refused manifest.** No `off`, no removed field, expert fields only where valid. Pinned in Task 9.
4. **A backtest row is a real pull request.** Each row links to it and shows before and after; a rule matching none warns. Pinned in Task 10.
5. **A promotion nobody merged.** The pull request closes unmerged: the record is abandoned on its own and a second request is possible. Pinned in Task 12.

---

## PR E: `feat(gate): decisions say the policy, the numbers and the next step`

### Task 1: one reason table (U10)

**Files:** new `internal/factory/reasons/reasons.go`, test; `internal/factory/narrate/narrate.go`, `internal/summary/waiting.go`, `internal/roomview/words.go`, `internal/slackapp/endline.go`, `internal/humanapi/tasktool.go`

- [x] Failing test: every reason the reconciler can emit has `{short, long, next}`; none mentions policy-bot unless `policyBot` is on.
- [x] The five maps read the table. A test fails when a reason is added without its words.
- [x] `docs/merge-policies.md`'s reasons table is generated from it (`hack/docs.sh`).

### Task 2: render the record (U1, U2, U3, U22)

**Files:** `internal/factory/narrate/narrate.go`, `internal/factory/reconciler/gatestatus.go`, `merge.go`, `internal/summary/policy.go`, tests

- [x] Failing tests: Review Focus 1 and 2; the shadow comment carries "n of m clean decisions".
- [x] The comment renders `Rows` and `considered=`: matched policy with measured over limit, and each policy that refused with its reason.
- [x] `statusFor` and the merged comment take `d.Matched`.
- [x] "merge wave" and "nothing is armed" are gone.

## PR F: `feat(cli): maku policy on the default path`

### Task 3: `list`, `explain`, `validate` (U4, U21)

**Files:** `internal/app/maku_policy.go`, new `internal/humanapi/policy_decisions.go`, `docs/cli.md`, tests

- [x] Failing tests: the three verbs against a fake broker; `--output json` on each.
- [x] `GET /api/policy/repositories/{owner}/{name}/decisions?since=` lists recorded decisions (pull request, head, outcome, policy, rows, considered).
- [x] `export` and `check` move to `maku config migrate`, with the old names kept one minor as aliases that print the new one.

### Task 4: `pause` (U14)

**Files:** `api/`, `internal/factory/config/mergedefaults.go`, `internal/factory/reconciler/arm.go`, `internal/app/maku_policy.go`, tests

- [x] Failing test: `spec.merge.paused: {reason}` makes every policy decide `paused`, shadow records included, and approve-to-merge still works.
- [x] `maku policy pause` and `resume` print the one-line manifest change; with `Factory.spec.gitops` they open it as a pull request.

## PR G: `docs(crd): the objects explain themselves`

### Task 5: schema, columns, conditions (U12, U13, M13, M19, U14)

**Files:** `internal/factory/config/classes.go`, `binding.go`, `api/factory/v1alpha1/`, `internal/factory/statuswriter/desired.go`, generated CRDs, `api/factory/v1alpha1/mergepolicy_crd_test.go`

- [x] Failing envtest cases: `diffShape: nonsense`, a negative cap, an unanchored pattern and `evidence: low` with no shape or proof are refused at admission, each with object, field and fix.
- [x] Doc comments rewritten without decision ids; enum on `diffShape`; `Minimum=0` on caps; default `standard` on `evidence`.
- [x] Printer columns: `POLICIES`, `LIVE`, `BINDINGSVALID`; a `Description` column on `MergePolicy`.
- [x] `servedMode` per binding; a `Ready` condition false while a generation or a binding is refused.

### Task 6: the guide (U5, U6, U7, U11, U15, U17, U18, U19)

**Files:** `docs/merge-policies.md`, `docs/upgrading.md`, `docs/quickstart.md`, `docs/concepts.md`, `docs/factory.md`, `docs/reference/config.md`, `docs/reference/metrics.md`, `docs/reference/api.md`, `docs/reference/web-ui-settings.md`, `docs/cli.md`, new `examples/merge-policies/docs-scoped.yaml`

- [x] Page one: what ships; how to read a decision; the first drill in three steps; how to promote; narrow one policy; write one policy.
- [x] One field table: meaning, type and unit, default, who sets it, refusal reason, example.
- [x] Repository-file authority, policy-bot and the stage ladder move to `docs/upgrading.md` under "Repository-file authority".
- [x] The seven pages naming refused switches are corrected; the example is validated by `maku config validate` in `hack/docs.sh`.

## PR H: `feat(observability): auto-merge share by policy`

### Task 7: one counter, one panel, two alerts (U16)

**Files:** `internal/factory/reconciler/merge.go`, `charts/agent-factory/files/dashboards/agent-factory.json`, `charts/agent-factory/files/rules/`, `charts/agent-factory/tests/monitoring/`, `docs/observability.md`

- [x] Failing rule test: a refused binding for 15 minutes fires; a policy paused for 24 hours fires.
- [x] `maku_factory_policy_considered_total{repository,policy,reason}`, fed from `considered`.
- [x] Panel "Merged with no human, by policy" and "Why the rest waited".

## PR I: `feat(ui): settings pages built around decisions`

### Task 8: recent decisions and the repository page (W4, W5, W6)

**Files:** `web/src/settings.ts`, new `web/src/decisions.ts`, `web/src/class-card.ts`, `web/src/policy-describe.ts`, `web/preview/settings-fixtures.ts`, `web/test/`

- [x] Failing vitest: the page renders the decisions table first; a healthy repository shows no status chip; a refused binding shows one note with the field and the fix.
- [x] Decisions table: pull request, outcome, policy, deciding criterion with numbers, age.
- [x] The all-repositories table: merged on its own, would have merged, waited (7 days), closest to going live.
- [x] The statistics move under a fold "How sure is this?".

### Task 9: the policy card and the editor (W1, W2, W3)

**Files:** `web/src/class-card.ts`, `web/src/binding-editor.ts`, `web/src/policy-fields.ts`, `web/src/policy-page.ts`, new `web/src/policy-words.ts`, tests

- [x] Failing vitests: Review Focus 3; `policyWords` turns each catalog policy into its sentence; a pattern is shown with a gloss ("Markdown under `website/content/`") and the raw form on demand.
- [x] The mode ladder (Off, Shadow, Live) replaces the select; "Off" writes `disabled`.
- [x] Essential fields open; "Shape and checks" and "Expert" folded, each listing only fields valid for this policy.
- [x] Presets: the shipped policies, each with "show the YAML".

### Task 10: the backtest (U4)

**Files:** new `internal/factory/policyview/backtest.go`, `internal/humanapi/policy.go`, `internal/app/maku_policy.go`, `web/src/binding-editor.ts`, tests

- [x] Failing tests: Review Focus 4; a recorded decision re-decided under a tighter cap changes from "would merge" to "waits" with the reason.
- [x] The preview endpoints re-decide the recorded diffs of the last 30 days with the edited policy, using the gate's own evaluator, and return only the changed decisions plus counts.
- [x] A decision whose diff was not recorded is "unknown", never "unchanged".
- [x] `maku policy backtest` prints the same table.

### Task 11: responsive and accessible

**Files:** `web/src/app.css`, the pages above

- [x] The pages read at 390 px with no horizontal scroll; tables collapse to labelled rows.
- [x] Every control is reachable by keyboard and labelled; the mode ladder is a radio group.
- [x] Screenshots at both widths, light and dark, attached to the PR.

## PR J: `feat(promotion): the factory opens the pull request`

### Task 12: one write, and a record that closes itself (U8, U23)

**Files:** `api/` (`Factory.spec.gitops`), `internal/factory/promote/`, `internal/humanapi/policy.go`, `internal/store/policy.go`, a migration, `web/src/class-card.ts`, `internal/app/maku_policy.go`, tests

- [x] Failing tests: Review Focus 5; with `gitops` unset the response carries the `gh pr create` command; the pull request body lists the decisions the promotion rests on.
- [x] The factory App opens `factory/promote-<repository>-<policy>` with the one-line change; it never merges it.
- [x] The record closes when the served binding turns live and is abandoned when the pull request closes unmerged; the "Merged" and "Abandon" buttons are removed.
- [x] A refusal returns the blockers with counts.
- [x] `maku policy promote` and `maku policy drill owner/name#PR`.
- [x] `docs/security.md`: the new write, its branch prefix, and why it cannot merge.

## Carried to the criteria plan

Proof checks, the rendered-manifest proof and the tamper checks (spec section 2) are planned after PRs E to J are released. The presets of Task 9 gain the three proofs then.
