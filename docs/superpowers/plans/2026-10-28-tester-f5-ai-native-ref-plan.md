# The test-first tester (v3 feature 4), F5: ai-native-ref, the pins and the config, every switch off — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin F3's agent-platform release and F4's host commit; write the config the release reads
with every switch off (`trio` without the tester, `holdoutChecks` on every live and shadow entry
class, `testFirst: false`, `merge.contractCheck` on the host); drop `room_verdict` from the tester's
capability profiles; document the stage; and write the runbook the gcp-0 session runs for live
proofs 1–3 (drills T1, T2, T3). Nothing switches on here (D4).

**Architecture:** Configuration only. The factory's values live in
`tooling/base/agent-factory/helm-values-configmap.yaml`; the gateway's tool lists are rendered from
`infrastructure/base/agent-gateway/profiles/` by `scripts/ci/gen-capabilities.py`; the host's paths
are reached through `HOST_REF`. Offline proof 6 parses the values under the pinned release's
`config.Parse` and asserts it **warns about nothing**: F5 is the change that clears the two warnings
F3 introduces.

**Tech Stack:** YAML, `yq`, Go (a throwaway test in a scratch worktree of the pinned release),
`task check`.

**Parent plan:** agent-platform `docs/superpowers/plans/2026-10-22-test-first-tester-plan.md` (the
inherit row F5, rulings R17, R18, R20). **F3:** agent-platform
`docs/superpowers/plans/2026-10-28-tester-f3-factory-plan.md` (F3-R10..R12: the warnings this plan
clears). **Spec:** [the test-first tester design](../specs/2026-10-22-test-first-tester-design.md)
(the config, TO4, offline proof 6, live proofs 1–3).

## What this builds on, re-measured on `main` (f2514b1, 2026-10-28)

| Piece | Today | Needed from |
|---|---|---|
| agent-platform pins (chart, image, room-broker, retention CronJob, `crd-rooms.yaml`, Slack App, the vmrule comment) | v0.29.0 | F3's release (**not cut**: F1 and F3 unmerged) |
| `HOST_REF` | `90ce50ef` | F4's merge on cloud-native-ref (**not opened**: the tester's trust policy `contents: write`, the composition pin) |
| The host's composition package | `crossplane-configuration-*:v0.9.22`, harness `v0.27.0` | a crossplane-configuration release with F2's tester rules **and a harness bump to F1's release** (F2 is in progress; the harness bump is in no plan yet — see the gaps) |
| The host's "Test contract 🧪" job | report-only, action pinned at v0.29.0 (`49153a7`) | unchanged: F1 does not change `test_contract.py`, so the pin need not move |
| `trio` | `[implementer, tester, reviewer]` | `[implementer, reviewer]` here |
| `holdoutChecks` on the host's live `docs-links`, `revert` and ai-native-ref's shadow ones | absent (the merge gate's PR D never declared them) | here |
| `tester.{public,internal}.yaml` | list `room_verdict` | dropped here |

**Dependency gaps (not merged, needed before this plan's PR can pass `task check` against real pins):**

1. **F1, F3** (agent-platform) and their release.
2. **F2** (crossplane-configuration, in progress) and its release.
3. **The harness bump** to F1's release in crossplane-configuration. F4's row names "the composition
   pin of F2's release"; that release must carry `agent-harness:<F1 release>`, or the tester's
   commit-only mode never reaches a run. If F2 is released before F1, a second crossplane-configuration
   release bumps the harness, and F4 pins that one.
4. **F4** (cloud-native-ref, human-authored gate paths).

Tasks 4–6 (profiles, docs, the runbook) depend on none of these and may be written first on this
branch; Tasks 2, 3 and 7 wait for the pins.

## This plan's rulings

| # | Ruling | Why |
|---|---|---|
| F5-R1 | **The host's `scripts` and a declared `review` read `{checks: false, testFirst: false}`** — declared so the switch is one edit in the session, not a new key | The inherit row; F3-R11 refuses `testFirst: true` without `checks: true`, so the session flips both together |
| F5-R2 | **`holdoutChecks`:** host `docs-links` and `revert`: `["Check the documentation links 🔗"]` (an invariant, a required check, unconditional in `ci.yaml`); ai-native-ref `docs-links` and `revert`: `[validate]` | The spec's "Holdouts in this deployment"; clears F3-R12's warning and gauge for the host's two live classes |
| F5-R3 | **Nothing for ai-native-ref's `testFirst` or `contractCheck`** (TO4: its tests live under the gate path `scripts/ci/`) | TO4 |
| F5-R4 | **Offline proof 6 asserts `len(cfg.Warnings) == 0`**, every `TestFirstFor` false, `trio` without the tester, and both repositories' entry classes holding their holdouts | The proof that F5 clears what F3 warns |
| F5-R5 | **The drills' issue texts stay off the repository** (`~/.cache/v3/drills/drill-t{1,2,3}.md`); the runbook names each drill's purpose and expected outcome only | The 2026-10-27 session: agents that read a drill's text in the runbooks recognised it and answered the drill instead of the issue |

## Global Constraints

- **Worktree:** this plan's branch is `docs/tester-f5-plan`. The build uses its own:
  `git -C /home/smana/Sources/ai-native-ref worktree add /home/smana/Sources/ai-native-ref-tester-f5 -b feat/tester-f5 origin/main && cd /home/smana/Sources/ai-native-ref-tester-f5 && mise trust mise.toml`.
  Rebase onto a freshly fetched `origin/main` before every push.
- **Evidence:** `task check` (clones the host at `HOST_REF` into `.host/`, runs the gates, the suites,
  the link check, the site build and the doc-path check). System `python3` with PyYAML; Docker is off
  by default and not needed here. Run `pre-commit run --all-files` before the push. Never claim done
  without the output.
- **Never run a command with `HOME=…` or `env -i`.** `$SCRATCH` is
  `/tmp/claude-1000/<session>/scratchpad` or any directory outside every repository.
- **Off by default (D4).** No `testFirst: true` anywhere; the live classes' behaviour is unchanged
  (their holdout is a check the gate already requires and that runs on every pull request).
- **A host change is a cloud-native-ref pull request first** (F4), then the `HOST_REF` bump here.
- **Commits:** conventional, English, no trailers. `git add` named paths only.

## File structure

| File | Task | Change |
|---|---|---|
| `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` (`image.tag`), `infrastructure/base/room-broker/{app,retention-cronjob,crd-rooms,sqlinstance}.yaml`, `tooling/base/agent-factory/slack-app/deployment.yaml`, `observability/base/agent-platform/vmrule-agent-factory.yaml` | 2 | F3's release, as #165 moved v0.29.0 |
| `HOST_REF` | 2 | F4's merge commit |
| `tooling/base/agent-factory/helm-values-configmap.yaml` | 3 | The config, every switch off |
| `infrastructure/base/agent-gateway/profiles/tester.{public,internal}.yaml`, `infrastructure/base/agent-gateway/mcp.yaml` | 4 | No `room_verdict` |
| `website/content/docs/platform/ai-platform/agents/{harness,factory}.md`, `website/content/docs/platform/ai-platform/status.md` | 5 | The stage documented |
| `docs/runbooks/agent-factory/21-test-first-tester.md`, `docs/runbooks/agent-factory/README.md` | 6 | Live proofs 1–3 |

---

### Task 1: The worktree

- [ ] **Step 1:**

```bash
git -C /home/smana/Sources/ai-native-ref fetch origin
git -C /home/smana/Sources/ai-native-ref worktree add /home/smana/Sources/ai-native-ref-tester-f5 -b feat/tester-f5 origin/main
cd /home/smana/Sources/ai-native-ref-tester-f5 && mise trust mise.toml
```

### Task 2: The pins and `HOST_REF`

**Depends on:** F3's release; F4 merged.

- [ ] **Step 1:** Move every agent-platform pin #165 (`f26d538`) moved, to F3's release, tag and
  digest (`crane digest ghcr.io/smana/<image>:<tag>` for each image; the chart's `ref.digest` from
  `flux` or `crane digest ghcr.io/smana/charts/agent-factory:<ver>`). Update the version in each pin's
  comment.
- [ ] **Step 2:** `HOST_REF` ← F4's merge commit on cloud-native-ref `main`.
- [ ] **Step 3:** `python3 scripts/ci/tests/test-agent-factory-pins.py` → `0 problem(s)`.
- [ ] **Step 4:** Commit `feat(agent-factory): agent-platform <release> and HOST_REF with the tester's write token (tester F5)`.

### Task 3: The config, every switch off

**Files:** Modify `tooling/base/agent-factory/helm-values-configmap.yaml`.

- [ ] **Step 1: Write offline proof 6 first** (it fails on today's values: `trio` lists the tester,
  two live classes have no holdouts):

```bash
yq '.data."values.yaml"' tooling/base/agent-factory/helm-values-configmap.yaml | yq '.config' > $SCRATCH/factory-config.yaml
git -C /home/smana/Sources/agent-platform fetch --tags origin
git -C /home/smana/Sources/agent-platform worktree add $SCRATCH/ap-release <F3 release tag>
cat > $SCRATCH/ap-release/internal/factory/config/zz_host_test.go <<'EOF'
// SPDX-License-Identifier: Apache-2.0

package config

import (
	"os"
	"slices"
	"testing"
)

func TestHostValues(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOST_CONFIG"))
	if err != nil {
		t.Fatal(err)
	}
	c, err := Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	if len(c.Warnings) != 0 {
		t.Errorf("warnings: %v", c.Warnings)
	}
	if slices.Contains(c.Templates["trio"].Roles, "tester") {
		t.Errorf("trio %v", c.Templates["trio"].Roles)
	}
	for _, r := range c.Repos() {
		for class := range r.Classes {
			if r.TestFirstFor(class) {
				t.Errorf("%s %s: testFirst is on", r.Name, class)
			}
		}
		for _, class := range []string{"docs-links", "revert"} {
			if len(r.Classes[class].HoldoutChecks) == 0 {
				t.Errorf("%s %s: no holdout", r.Name, class)
			}
		}
	}
	host := c.RepositoryFor("Smana/cloud-native-ref")
	if host.Merge.ContractCheck != "Test contract 🧪" {
		t.Errorf("host contractCheck %q", host.Merge.ContractCheck)
	}
	if c.RepositoryFor("Smana/ai-native-ref").Merge.ContractCheck != "" {
		t.Error("ai-native-ref names a contract check (TO4)")
	}
}
EOF
(cd $SCRATCH/ap-release && HOST_CONFIG=$SCRATCH/factory-config.yaml go test -count=1 -run TestHostValues ./internal/factory/config/)
```

  Expected now: `FAIL` naming the warnings and `trio`.
- [ ] **Step 2: Edit the values.**
  - `templates.trio`: `{roles: [implementer, reviewer], maxReviewRounds: 2}` with the comment
    `# TF2, TO1: the tester writes the tests first (testFirst), never a verdict; trio is pair's shape until the bench.`
  - Host `classes`: `docs-links: {live: true, holdoutChecks: ["Check the documentation links 🔗"]}`,
    `revert: {live: true, holdoutChecks: ["Check the documentation links 🔗"]}` (keep their comments),
    `scripts: {checks: false, testFirst: false}` and a new `review: {checks: false, testFirst: false}`,
    each with `# TO4: the bench's variant turns testFirst on; it needs checks: true (R17)`.
  - Host `merge`: `contractCheck: "Test contract 🧪"  # required on a task with a contract (TF8, row 2b); report-only otherwise`.
  - ai-native-ref `classes`: `docs-links: {shadow: true, holdoutChecks: [validate]}`,
    `revert: {shadow: true, holdoutChecks: [validate]}`, and a comment: `# no testFirst here (TO4): the tests live under the gate path scripts/ci/`.
- [ ] **Step 3:** Re-run Step 1's extract and test → `ok`. Then
  `git -C /home/smana/Sources/agent-platform worktree remove --force $SCRATCH/ap-release`.
- [ ] **Step 4:** `python3 scripts/ci/tests/test-agent-merge-gate-parity.py` and
  `python3 scripts/ci/tests/test-factory-interfaces-off.py` → pass (neither reads the new keys; run
  them to prove it).
- [ ] **Step 5:** Commit `feat(agent-factory): the tester's config, every switch off: trio without the tester, holdouts on the entry classes, the contract check named (tester F5)`.

### Task 4: The tester's capability profiles

**Files:** Modify `infrastructure/base/agent-gateway/profiles/tester.public.yaml`, `tester.internal.yaml`; regenerate `mcp.yaml`.

- [ ] **Step 1:** `bash scripts/ci/tests/test-agent-capabilities.sh` → passes (the baseline).
- [ ] **Step 2:** Remove `- room_verdict` from both files' `room-broker` list; add above the list
  `# TF2: the tester writes the contract and gives no verdict (capability profiles: the tester's drop room_verdict).`
- [ ] **Step 3:** `python3 scripts/ci/gen-capabilities.py --write` then `bash scripts/ci/tests/test-agent-capabilities.sh`,
  `bash scripts/ci/tests/test-agent-capabilities-wire.sh`, `bash scripts/ci/tests/test-agent-mcp-scope.sh` → pass;
  `git diff --stat` shows the two profiles and `mcp.yaml` only.
- [ ] **Step 4:** Commit `feat(agent-gateway): the tester's profiles drop room_verdict (tester F5)`.

### Task 5: The docs

**Files:** Modify `website/content/docs/platform/ai-platform/agents/tune/harness.md`, `factory.md`, `website/content/docs/platform/ai-platform/status.md`.

- [ ] **Step 1:** `harness.md`, "How a run works": a paragraph "The tester's run" — it writes tests
  under the repository's test paths and commits; the harness checks them red on the base, signs and
  pushes them, or answers once and pushes nothing; the implementer then cannot commit a change to
  them and is told when they still fail. Link the harness reference for the ends. In "Failure modes",
  three rows: `contract_not_red` ("the runner could not run": the toolchain, not the tester),
  `contract_outside_tests`, `not_testable`.
- [ ] **Step 2:** `factory.md`: the tester stage in the task's life; `testFirst`, `merge.contractCheck`,
  `holdoutChecks` in the config table; rows 2b and 2c and the reasons `contract_invalid`,
  `contract_disputed`, `contract_modified`; the metrics `agent_factory_contracts_total` and
  `agent_factory_class_without_holdout`.
- [ ] **Step 3:** `status.md`: the test-first tester row's badge stays `built, off`; its middle cell
  ends "Since <date>, the factory can run the tester first per class (`testFirst`, off everywhere) and
  requires the contract on a task that has one; the entry classes name their holdouts."
- [ ] **Step 4:** `./scripts/ci/verify-doc-paths.sh` (after `git add`; needs `.host/` from a `task check`)
  and `./scripts/ci/validate-links.sh` → pass.
- [ ] **Step 5:** Commit `docs(agent-factory): the test-first tester, its contract and the gate's rows (tester F5)`.

### Task 6: Runbook 21, the live proofs

**Files:** Create `docs/runbooks/agent-factory/21-test-first-tester.md`; modify `docs/runbooks/agent-factory/README.md` (its table row).

- [ ] **Step 1:** Write the runbook from [Live proofs](#live-proofs-the-gcp-0-session) below: the
  preconditions as a checklist, each proof as a table of step, action and expected reading, the
  commands in fenced blocks, and **no drill text** (F5-R5): each drill names its file under
  `~/.cache/v3/drills/` and what it must ask for.
- [ ] **Step 2:** README row: `21-test-first-tester.md` | the tester's contract on a seeded `scripts`
  issue, the hook and row 2c, a renamed holdout | needs F1–F5 live and the owner's go | ~2 h.
- [ ] **Step 3:** `./scripts/ci/validate-links.sh` → pass.
- [ ] **Step 4:** Commit `docs(runbooks): runbook 21, the test-first tester's live proofs (tester F5)`.

### Task 7: `task check` and the pull request

- [ ] **Step 1:** `task check` → exit 0; `pre-commit run --all-files` → pass. Paste the tails.
- [ ] **Step 2:**

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/tester-f5
gh pr create --title "feat(agent-factory): the test-first tester pinned and configured, every switch off (tester F5)" \
  --body-file $SCRATCH/f5-pr.md
```

  The body: the pins and `HOST_REF` with their sources; offline proof 6's output; that F5 clears
  F3's two warnings; the runbook; "nothing switches on".

## Live proofs: the gcp-0 session

Run after F1–F5 are live on gcp-0, in one session (the memory's rule: build offline first, batch the
live proofs). Drills T1–T3 use these steps. The bench (live proof 4) waits with the bench.

**Preconditions**

- [ ] The factory and broker run F3's release: `kubectl -n agent-factory get deploy agent-factory -o jsonpath='{..image}'`.
- [ ] A run's harness is F1's: start any run and read `kubectl -n agents get pod xplane-run-<id> -o jsonpath='{.spec.containers[?(@.name=="harness")].image}'`.
- [ ] The host's tester trust policy is `contents: write`: `gh api repos/Smana/cloud-native-ref/contents/.github/chainguard/agent-tester.sts.yaml --jq .content | base64 -d | grep 'contents: write'`.
- [ ] The factory logged no config warning since its start: `kubectl -n agent-factory logs deploy/agent-factory | grep -c 'config warning'` → `0`.
- [ ] A session commit on ai-native-ref switches the host's `scripts` to `{checks: true, testFirst: true}`
  (and nothing else); Flux reconciled it. The same session's last commit reverts it.

**Live proof 1 (drill T1): a contract on a seeded `scripts` issue**

Drill T1's text (`~/.cache/v3/drills/drill-t1.md`) asks for one small, testable behaviour change in a
host script under `scripts/` that a suite under `scripts/ci/tests/` can pin down (an exit code, a
printed line). File it on cloud-native-ref, `class:scripts`, then `factory/ready`.

| Step | Read | Expected |
|---|---|---|
| 1 | `kubectl -n agent-factory get task <t> -o jsonpath='{.status.runs[0].role} {.status.phase}'` | `tester Implementing` (after the scoper's run if the class's scope mode is `scoper`) |
| 2 | The room | `Harness (tester): contract_ready: scripts/ci/tests/test-….sh`; before it, no push by the model succeeded (`disabled://` in the step log if it tried) |
| 3 | `gh api 'repos/Smana/cloud-native-ref/activity?ref=refs/heads/agent/<t>' --jq '.[] \| [.activity_type, .actor.login, .after] \| @tsv'` | one `branch_creation` by `ogenki-agents[bot]` |
| 4 | `gh api repos/Smana/cloud-native-ref/commits/<after> --jq .commit.message` | subject `test: the test contract`; `Agent-Contract: <rid(0)>`, the files, the ids |
| 5 | `kubectl … -o jsonpath='{.status.contract}'` | `runId` the tester's, `commit` = step 3's `after`, the same files and ids |
| 6 | The implementer's claim: `kubectl -n agents get agentrun <rid(1)> -o jsonpath='{.spec.task.text}'` | holds "The test contract", the commit's first 12 and the ids |
| 7 | `gh pr checks <pr>`, then the "Test contract 🧪" summary | each tester id `fail` at base + tests and `pass` at the head; the check required (row 2b): the task waits for it |
| 8 | `agent_factory_contracts_total{class="scripts",end="ready"}` in VictoriaMetrics | 1 |

`scripts` is label-only: the task ends with a maintainer (`class_unarmed`). That is the expected end.

**Live proof 2 (drill T2): the contract holds**

Drill T2's text asks for a change whose shortest route edits a test the tester will write (a
behaviour the issue states loosely). File it as T1.

| Step | Action | Expected |
|---|---|---|
| 1 | Watch the implementer's room | if it edits a contract file and commits: the step log shows `pre-commit: these files are the test contract…` and the commit refused |
| 2 | If it hands off to `tester` | `Escalated`, `contract_disputed`; the issue carries the category only. Record it; the next step needs a pull request |
| 3 | Deterministic half, on any open contract task: a maintainer pushes one commit changing a contract file to `agent/<t>` | the next decision: `AwaitingHuman`, `contract_modified` (row 2c decides before the author mode's `head_unreported`). If the push turns "Test contract 🧪" red, row 2b decides first and the fix run's own guard hands off as `human_commit_in_pr`: keep the loosened test passing at the head so 2c is what answers |
| 4 | A head rebased so it no longer descends from the contract commit (`git rebase` the branch onto `main` and force-push, as a maintainer) | `contract_modified` again (F3-R9's fail-closed read) |

**Live proof 3 (drill T3): holdouts**

R20 replaced the spec's `holdout_absent`: an absent holdout waits.

| Step | Action | Expected |
|---|---|---|
| 1 | In a session commit, rename ai-native-ref's `docs-links` holdout to `validate-renamed`; file drill T3 (a `docs-links` fix) on ai-native-ref | the decision waits `holdout_pending`; after `awaitingCIFor` (24 h, or set it to `30m` in the same session commit) the task hands off naming `validate-renamed` as never reported (`ChecksNeverReported`) |
| 2 | Revert the rename; file drill T3 again | `shadow_would_arm` as before the change: `scripts/shadow-merge-tally.sh` (agent-platform) counts the decision with the others |
| 3 | `agent_factory_class_without_holdout` | no series (F5 declared every live class's holdout) |

**After the session:** revert the `scripts` switch and any `awaitingCIFor` change; delete the drill
branches; record the readings in the runbook's results section.

## Cross-task conflicts

| Between | Conflict | Resolution |
|---|---|---|
| Tasks 2 and 3 | Both edit `helm-values-configmap.yaml` (`image.tag`, `config`) | Different blocks; Task 2 first |
| Task 3 vs the RunLore stage 2 PR (#168) | Both edit `helm-values-configmap.yaml` | Rebase; `TestHostValues` re-runs after it |
| Task 3 vs the merge gate's PR D | It would declare the same `holdoutChecks` | Add only what is absent at rebase time |
| Task 4 vs capability profiles P3 | Both edit `profiles/` and `mcp.yaml` | Regenerate `mcp.yaml` after the rebase, never merge it by hand |
| F5 vs F2/F4 | The tester's rules and write token must be live before the runbook runs | Preconditions checklist above |

## Self-review

- **Inherit row F5:** the factory pin, `HOST_REF` (Task 2); `trio`, `holdoutChecks`, `scripts` and
  `review` off, `merge.contractCheck`, nothing for ai-native-ref (Task 3); the profiles and `mcp.yaml`
  (Task 4); the harness, factory and status pages (Task 5). Live proofs 1–3: Task 6 and the section above.
- **Offline proof 6:** Task 3's `TestHostValues` (the parse), Task 4 (the profiles and the drift gate),
  Task 7 (`task check`, the gate-path suite).
