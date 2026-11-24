# Merge policies trust and usability, ai-native-ref Adoption Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** This platform's gate protects its own configuration again, its policies reach promotion in weeks instead of months, and its pages say what is deployed.

**Architecture:** PR 1 needs no Maku release: it moves the gate-path list to where the gate reads it and sets `evidence` on two policies. PRs 2 and 3 follow the Maku releases of the safety and usability plans, each as a pin bump with the manifests that release makes possible.

**Tech Stack:** Kustomize manifests under `tooling/base/agent-factory/resources/`, the Python and shell suites under `scripts/ci/tests/`, Hugo pages under `website/content/`.

**Spec:** `docs/superpowers/specs/2026-11-24-merge-policies-trust-and-usability-design.md` (ids `A`).

## Global Constraints

- In a git worktree from `origin/main`; rebase onto a fresh `origin/main` before every push.
- `task check` exits 0 before every commit; its output is the evidence in each PR.
- Changes go in `tooling/base/` unless a value is cluster-specific.
- Site pages follow `docs/docs-style.md`; `task docs` enforces it.
- Commits are conventional, in English, with no trailers. Merges are the owner's.
- No live cluster runs today. Each PR states what is proven offline and what waits for the next live session.

## Review Focus

1. **A gate path approved by a maintainer.** With the list in `mergeGuardrails.protectedFiles`, an agent pull request touching `scripts/ci/` or `tooling/base/agent-factory/resources/` and approved by a maintainer is handed off `gate_path`, not merged by the merger. Pinned in Task 1.
2. **No sentinel lost.** Every path `test-agent-repo-files.py` guards today is still refused after the list moves. Pinned in Task 1.
3. **`dead-links` at five.** The parity suite accepts `evidence: low` on it because it carries a shape and an oracle. Pinned in Task 2.

---

## PR 1: `fix(agent-factory): the gate reads this repository's gate paths`

### Task 1: move the list to the Factory (A1)

**Files:** `tooling/base/agent-factory/resources/factory.yaml`, `scripts/ci/tests/test-agent-repo-files.py`, `.policy.yml`, `tooling/base/agent-factory/resources/kustomization.yaml`

- [ ] Change `test-agent-repo-files.py` to read the gate list from `Factory.spec.mergeGuardrails.protectedFiles` (through `scripts/ci/factory_config.py`) and run it: it fails, the key is unset.
- [ ] Add `mergeGuardrails.protectedFiles` to `factory.yaml` with the paths `.policy.yml` lists under `no_changed_files`, plus `(^|/)(AGENTS|CLAUDE)\.md$` and `^\.(agents|claude)/`. Keep the caps unset: Maku's defaults hold.
- [ ] Run the suite: green, every sentinel refused.
- [ ] Add a case to `test-agent-resolved-classes.sh`: each bound policy's resolved `protectedFiles` contains `^scripts/ci/`.
- [ ] Delete `.policy.yml` and its mentions in comments. `gh api repos/Smana/ai-native-ref/rulesets` shows no ruleset requires `policy-bot: main` (read 2026-11-23: `maku/merge-gate`, `validate`, `lint`).
- [ ] The list applies to cloud-native-ref too, since guardrails are the Factory's: check each path against the host's own `.policy.yml` and keep only paths valid for both, moving the rest to each `Repository`'s policies' `protectedFiles`.

### Task 2: evidence and stale comments (A2, A4)

**Files:** `tooling/base/agent-factory/resources/mergepolicy-dead-links.yaml`, `mergepolicy-kb-entries.yaml`, `repository-*.yaml`, `mergepolicy-*.yaml`, `scripts/ci/tests/test-agent-merge-gate-parity.py`

- [ ] `evidence: low` on `dead-links` (shape and oracle) and on `kb-entries` (`added-entry`).
- [ ] Run the parity suite: green.
- [ ] Rewrite the six comments that describe `.policy.yml` `low-risk` rules or "20 shadow decisions" to say what is true: `maku/merge-gate` decides, 5 or 20 by `evidence`.
- [ ] Remove the `link-rot` schedule from `repository-cloud-native-ref.yaml` if the revert proof of runbook 15 §3 is recorded as done in `docs/runbooks/agent-factory/`; otherwise leave it and say so in the PR.

### Task 3: the site page (A3)

**Files:** `website/content/docs/use/guide/merge-policies.md`

- [ ] Correct the closing paragraph: Maku's defaults are `policyManagement.stage: manage` and the catalog enabled; this platform differs by excluding `deps-patch`, which it keeps as its own object for the host's protected paths and its Flux monitor.
- [ ] `lastVerified` to the day of the change; `task docs`.

## PR 2: `feat(agent-factory): maku v0.53.x, the safety fixes`

After the safety plan's PRs A to D are released.

### Task 4: pin and follow the changed defaults

**Files:** `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/resources/factory.yaml`, `repository-*.yaml`, `scripts/ci/flux-schema/vendored-crds/`, `scripts/ci/tests/`

- [ ] Bump the chart and image pins; refresh the vendored CRDs.
- [ ] `mergeDefaults.autoRevert: true`, and remove the `revert` bindings from the four repositories.
- [ ] Remove the `docs-links` bindings that exist only to satisfy the old "required" rule, keeping those that add `holdoutChecks`.
- [ ] `task check`. Offline proof: `test-maku-config-load.sh` loads the tree with the new binary.
- [ ] Runbook: add to the next live session's list the five Review Focus cases of the safety plan, each as one scratch pull request.

## PR 3: `feat(agent-factory): maku v0.54, readable decisions and promotion`

After the usability plan is released.

### Task 5: `gitops`, the pages and the dashboards

**Files:** `tooling/base/agent-factory/resources/factory.yaml`, `observability/base/agent-platform/`, `website/content/docs/use/guide/merge-policies.md`, `website/content/docs/reference/gate-reasons.md`, `website/content/docs/operate/auto-merge-safety.md`

- [ ] `Factory.spec.gitops: {repository: Smana/ai-native-ref, path: tooling/base/agent-factory/resources}`. The factory App's installation already has `contents: write` and `pull_requests: write` here; confirm with `gh api` and record it in the PR.
- [ ] Adopt the two shipped alerts; drop this repository's copies if they duplicate them (`test-agent-class-paused-alert.sh`).
- [ ] Site: the reasons page lists the codes this release emits (`paused`, `diff_unreadable`, `labels_truncated`; no `class_unarmed`); the guide gains "Promote a policy" with the one-click flow and a screenshot of the new repository page.
- [ ] Next live session: promote `dead-links` on this repository through the button, end to end, as the proof of v5 Go criterion 4's mechanics.
