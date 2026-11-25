# Merge policies safety and correctness, Maku Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** No known way is left to merge a pull request outside its policy's bound, and no edit fails open.

**Architecture:** Every task is a tightening inside an existing package: the shape in `internal/factory/mdlinks`, the forge reads in `internal/factory/forge`, selection in `internal/factory/reconciler`, resolution in `internal/factory/resources` and `internal/factory/config`, counting in `internal/factory/evidence`. Nothing new is configured; three defaults change and are listed in `docs/upgrading.md`.

**Tech Stack:** Go (controller-runtime, envtest), Helm (`charts/agent-factory`), the shell suites under `scripts/`.

**Spec:** `docs/superpowers/specs/2026-11-24-merge-policies-trust-and-usability-design.md` in ai-native-ref, section 1 and the findings table (ids `S`, `M`). Copy it to Maku's `docs/superpowers/specs/` in the first PR.

## Global Constraints

- Executed in the Maku repository, in a worktree from `origin/main`. Paths below are Maku's.
- `task check` exits 0 before every commit and push; lint only through `task lint`.
- Conventional commits in English, one concern per commit, no trailers. Squash-merge: the PR title is itself a conventional commit.
- Test first: each task starts with the failing test named in it, run and seen red.
- Each PR is releasable alone as a v0.53 patch. A PR that changes a default says so in `docs/upgrading.md` in the same PR.
- A fix never loosens: where a rule is unclear the pull request goes to a human with a named reason.
- After any change to `api/` or `internal/factory/config` types: `task crd:gen`, and commit the generated copies.

## Status: merged, not yet validated live (2026-11-25)

PRs A to D and the carried low-severity fixes were merged in Maku [#678](https://github.com/Smana/maku/pull/678), squash commit `c599a3d4`. The implementation checkboxes below are complete. Maku's full `task check`, pull-request CI, and post-merge `main` CI passed. No live-cluster validation was performed, and Maku `v0.53.11` does not contain this work.

### Live validation handoff

Run these checks only after a Maku release containing #678 is deployed. Use one scratch pull request at a time on a repository whose fence names the bootstrapped cluster's factory. Record the Maku version, cluster, pull request URL and head SHA, and the `maku/merge-gate` decision for each case. Do not use an administrator bypass: a bypass proves nothing about the gate.

- [ ] **Markdown-only shape:** try the YAML regex-group, Go call-argument and Markdown footnote cases from Task 1. Each waits with `class_mismatch`; a genuine Markdown link retarget still passes the shape row.
- [ ] **Unreadable or unchanged input:** try a submodule move, a symlink, an empty changed-file list and byte-equal sides. The gate refuses with the typed reason; it never treats missing input as a link-only diff.
- [ ] **Host rule:** change a shared-host link to another owner and try an archive URL for another target. Both refuse; an archive of the same target passes.
- [ ] **Hold authority:** remove `factory/hold` with the implementer/agents identity; the pull request stays held. Remove it as a maintainer; the next decision may proceed. Also exercise the labels-truncation fixture if the live harness provides it.
- [ ] **Decision-to-merge race:** after a green decision, separately add `factory/hold`, retarget the base, and request changes. None may merge. Push an extra commit to a generated `revert-<n>` branch; that head must not merge.
- [ ] **Repository-wide guards:** on a pull request matching two live policies, make the stricter policy's `requiresApproval` catch a file. Expect `approval_required`, not a merge under the looser policy. Confirm an unrelated path-filtered holdout is not awaited and a skipped leak scan is not green.
- [ ] **Refused edits fail closed:** replace a live binding with `mode: disabled`, introduce a demotion typo, and delete a bound `MergePolicy`. Confirm the old live policy does not outrank the edit and `servedMode` reflects the refusal.
- [ ] **Changed defaults and reverts:** verify the guardrail cap applies when `merge.maxPerDay` is unset, a cap above the guardrail is clamped, `merge.autoRevert: true` works without a `revert` binding, and a legacy binding reports `Deprecated`.
- [ ] **Evidence:** merge scratch cases under the intended policy and confirm only maintainer/merger merges count, an edited policy counts only when the recorded resolution was at least as tight, and bots or untrusted label actors do not create clean evidence.

For each failure, preserve the decision JSON with `maku policy explain <owner/name>#<PR> --output json` when the deployed release includes that command; otherwise capture the gate comment and Task status. Close scratch pull requests without merging unless the scenario explicitly requires a merge.

## Review Focus

1. **A `links-only` policy over a non-Markdown file.** `pattern: '^[a-z](-?[a-z0-9])*$'` to `'^[a-z](.*)*$'` in a YAML file must refuse `class_mismatch`. Pinned in Task 1.
2. **A submodule move under `docs-links` live.** Refused, never skipped. Pinned in Task 2.
3. **`{name: dead-links, mode: disabled}` replacing a live binding with parameters.** The policy stops serving at once. Pinned in Task 7.
4. **An implementer token removes `factory/hold`.** The pull request stays held. Pinned in Task 4.
5. **Two live policies, the stricter one's `requiresApproval` catches a file.** `approval_required`, never a merge under the looser one. Pinned in Task 6.

---

## PR A: `fix(gate): bind links-only to Markdown link targets`

### Task 1: Markdown only, and real links only (S2)

**Files:** `internal/factory/mdlinks/mdlinks.go`, `internal/factory/mdlinks/mdlinks_test.go`, `internal/factory/config/classes.go`

- [x] Failing tests: the three replayed cases (YAML regex group, Go call argument, footnote definition) each return "not links-only"; a `.md` file with a real retarget still passes.
- [x] `LinksOnly` refuses any listed path not matching `\.mdx?$`.
- [x] The target expression skips footnote definitions (`[^`) and requires the `](` to close a `[` on the same line.
- [x] `Bounded` documents that `links-only` carries its own path bound.
- [x] `docs/merge-policies.md`: one sentence under "Built-in shape".

### Task 2: a file that reads unchanged is refused (S1)

**Files:** `internal/factory/mdlinks/mdlinks.go`, `internal/factory/forge/github.go`, their tests

- [x] Failing tests: a listed file with equal sides refuses; an empty file list refuses; `fileAt` on a submodule and on a symlink returns a typed error.
- [x] `fileAt` applies the guards `file()` has (`type != "file"`, symlink target).
- [x] `LinksOnly` returns "not links-only" for a listed file whose sides are byte-equal.

### Task 3: the host rule (S3)

**Files:** `internal/factory/mdlinks/mdlinks.go`, test

- [x] Failing tests: `github.com/org/tool/…` to `github.com/evil/tool/…` refuses; an archive URL of another URL refuses; an archive URL of the same URL passes.
- [x] Shared hosts (`github.com`, `gitlab.com`, `raw.githubusercontent.com`, `bitbucket.org`) need the same first path segment.
- [x] `web.archive.org` is accepted only when its archived URL equals the old target.

## PR B: `fix(gate): human controls hold between the decision and the merge`

### Task 4: `factory/hold` needs a maintainer to lift it (S5)

**Files:** `internal/factory/reconciler/arm.go`, `internal/factory/reconciler/merge.go`, `internal/factory/forge/github.go`, tests

- [x] Failing tests: a hold removed by the agents login is still held; a hold removed by a maintainer clears; 31 labels fails closed as `labels_truncated`.
- [x] The forge returns the newest `labeled`/`unlabeled` event for `factory/hold` with its actor, and a truncation flag for labels.
- [x] `reentered_unheld` only on a maintainer's removal.

### Task 5: re-read before the merge, and pin the revert (S4, S15)

**Files:** `internal/factory/reconciler/merge.go`, `internal/factory/forge/github.go`, tests

- [x] Failing tests: a hold added, a base retarget or a "request changes" after the decision each stop the merge; a commit pushed onto `revert-<n>` stops the revert merge.
- [x] One PR re-read (labels, base ref, review decision) immediately before the success status.
- [x] The revert head GitHub created is recorded on the Task and is the only head merged; native auto-merge is no longer enabled for it.

### Task 6: guards are repository-wide, and the diff is read first (S6, S7, S9, S11)

**Files:** `internal/factory/reconciler/select.go`, `gate.go`, `arm.go`, `internal/factory/forge/github.go`, tests

- [x] Failing tests: Review Focus 5; a path-filtered holdout on an unrelated pull request yields `no_policy_matched` in one pass; a 2 MB changed file hands off `diff_unreadable`; a skipped leak scan is not green.
- [x] A live candidate whose diff conditions hold but whose `protectedFiles`, `requiresApproval` or holdout refuses decides the pull request with that reason.
- [x] The diff is read before any holdout is judged; a holdout is awaited only for a policy whose diff conditions hold.
- [x] A typed unreadable-file error hands off like `ErrDiffTooLarge`.
- [x] `leakScanCheck` needs the raw `SUCCESS` conclusion.

## PR C: `fix(factory): a refused or impossible edit never fails open`

### Task 7: the last resolved policy never outranks the edit (M1)

**Files:** `internal/factory/resources/bindings.go`, `internal/factory/mergepolicy/watch.go`, tests

- [x] Failing tests: Review Focus 3; a demotion with a typo serves shadow; a deleted `MergePolicy` stops serving.
- [x] `disabled` is dropped before resolution.
- [x] A last resolved class is put back only at the lower of its mode and the binding's written mode, and never for `MissingRef`.

### Task 8: cutover, caps and the dropped rules (M2, M5, M7, M8, M9, M11)

**Files:** `internal/factory/resources/bindings.go`, `internal/factory/config/mergepolicy.go`, `config.go`, `binding.go`, `mergedefaults.go`, `internal/factory/mergepolicy/resolve.go`, `internal/factory/policyview/bindings.go`, tests

- [x] Failing Assemble-level test: catalog on, `classAuthority: repository`, no `mergePolicies`: accepted, and its file's bindings carry the default guardrails.
- [x] Implied catalog bindings are skipped for a cut-over repository; default guardrails key on "no classes in the config file".
- [x] `merge.maxPerDay` unset resolves to the guardrail's cap.
- [x] The TO5 warning and the "docs-links and revert are required" rule are deleted in all three places.
- [x] A policy cap above the guardrail is clamped; a binding's explicit raise is still refused.
- [x] `docs/upgrading.md`: the three changed defaults.

### Task 9: `merge.autoRevert`, and `revert` leaves the catalog (M4)

**Files:** `internal/factory/config/mergedefaults.go`, `internal/factory/reconciler/merge.go`, `select.go`, `charts/agent-factory/templates/merge-policies-catalog.yaml`, `api/`, tests

- [x] Failing tests: `autoRevert: true` merges the factory's revert with no `revert` policy; a `revert` binding still loads and sets `autoRevert` with a `Deprecated` condition.
- [x] `merge.autoRevert` (default false) replaces `Classes["revert"].Live`.
- [x] `revert` is removed from the catalog and from `BuiltInShape`.

## PR D: `fix(evidence): count what the gate recorded, under the policy that earned it`

### Task 10: one reader, per policy (S8, M3, S12, S13)

**Files:** `internal/factory/evidence/evidence.go`, `scripts/shadow-merge-tally.sh`, a shared fixture, tests

- [x] Failing test: a fixture comment with two decision lines gives both policies one clean decision, in Go and in the script.
- [x] The Go reader parses every `agent-factory-decision` line; `shadow_would_require_approval` is not counted.
- [x] The comment author is compared by full bot login.

### Task 11: who merged, and under which policy (M6, M12, S17)

**Files:** `internal/factory/evidence/evidence.go`, `service.go`, `internal/factory/reconciler/ledger.go`, tests

- [x] Failing tests: a merge by a bot is not clean; 20 decisions under `^docs/` and 40 lines do not count after an edit to `^.+$` and 300 lines, and do count after a tightening.
- [x] "Clean" needs `mergedBy` in `maintainers`.
- [x] A decision counts when its `resolved=` class is at least as tight as the current one (`mergepolicy.ClassChange`).
- [x] Ledger labels need the merger or a maintainer as labeller.

## Carried, low severity

One PR, `fix(gate): small holes`, when A to D are merged: caps read through `GetAPIReader()` (S16); a file with no line counts refuses under a line cap (S18); `added-entry` enforces append-at-end (S21); the intent (policy, how, head) is persisted before the merge call (S14); approval memory is keyed on the matched policy (S10); a pattern matching three sentinel paths is refused as unbounded (M15); a binding's `companionFiles` never widens (M16); `Structural` reads `evidence` (M17).
