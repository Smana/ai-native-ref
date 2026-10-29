# 21 — The test-first tester: the live proofs

Proves feature 4 of v3 on gcp-0 (drills T1 to T3): the tester's contract on a seeded `scripts` issue,
the hook and row 2c that hold it, and a renamed holdout. Every switch is off in the repository; a
session commit flips `scripts` and the same session reverts it. The bench (live proof 4) waits with the
bench. Design: [the test-first tester](../../superpowers/specs/2026-10-22-test-first-tester-design.md).
The drills' issue texts stay out of the repository (an agent that reads one here answers the drill, not
the issue): each drill names its file under `~/.cache/v3/drills/` and what it must ask for.
See [README.md](README.md) for `CLOUD`.

## 0. Preconditions

- [ ] The factory and broker run F3's release: `kubectl -n agent-factory get deploy agent-factory -o jsonpath='{..image}'`.
- [ ] A run's harness is F1's: start any run and read `kubectl -n agents get pod xplane-run-<id> -o jsonpath='{.spec.containers[?(@.name=="harness")].image}'`.
- [ ] The host's tester trust policy is `contents: write`: `gh api repos/Smana/cloud-native-ref/contents/.github/chainguard/agent-tester.sts.yaml --jq .content | base64 -d | grep 'contents: write'`.
- [ ] The factory logged no config warning since its start: `kubectl -n agent-factory logs deploy/agent-factory | grep -c 'config warning'` → `0`.
- [ ] A session commit on ai-native-ref switches the host's `scripts` to `{checks: true, testFirst: true}`
  (and nothing else); Flux reconciled it. The same session's last commit reverts it.

## 1. Live 1 (drill T1): a contract on a seeded `scripts` issue

Drill T1 (`~/.cache/v3/drills/drill-t1.md`, never in this repository) must ask for one small, testable behaviour change in a
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

## 2. Live 2 (drill T2): the contract holds

Drill T2 (`~/.cache/v3/drills/drill-t2.md`) must ask for a change whose shortest route edits a test the tester will write (a
behaviour the issue states loosely). File it as T1.

| Step | Action | Expected |
|---|---|---|
| 1 | Watch the implementer's room | if it edits a contract file and commits: the step log shows `pre-commit: these files are the test contract…` and the commit refused |
| 2 | If it hands off to `tester` | `Escalated`, `contract_disputed`; the issue carries the category only. Record it; the next step needs a pull request |
| 3 | Deterministic half, on any open contract task: a maintainer pushes one commit changing a contract file to `agent/<t>` | the next decision: `AwaitingHuman`, `contract_modified` (row 2c decides before the author mode's `head_unreported`). If the push turns "Test contract 🧪" red, row 2b decides first and the fix run's own guard hands off as `human_commit_in_pr`: keep the loosened test passing at the head so 2c is what answers |
| 4 | A head rebased so it no longer descends from the contract commit (`git rebase` the branch onto `main` and force-push, as a maintainer) | `contract_modified` again (F3-R9's fail-closed read) |

## 3. Live 3 (drill T3): holdouts

R20 replaced the spec's `holdout_absent`: an absent holdout waits.

| Step | Action | Expected |
|---|---|---|
| 1 | In a session commit, rename ai-native-ref's `docs-links` holdout to `validate-renamed`; file drill T3 (`~/.cache/v3/drills/drill-t3.md`; a `docs-links` fix) on ai-native-ref | the decision waits `holdout_pending`; after `awaitingCIFor` (24 h, or set it to `30m` in the same session commit) the task hands off naming `validate-renamed` as never reported (`ChecksNeverReported`) |
| 2 | Revert the rename; file drill T3 again | `shadow_would_arm` as before the change: `scripts/shadow-merge-tally.sh` (Maku) counts the decision with the others |
| 3 | `agent_factory_class_without_holdout` | no series (F5 declared every live class's holdout) |

## 4. After the session

Revert the `scripts` switch and any `awaitingCIFor` change; delete the drill
branches; record the readings in the runbook's results section.

## 5. Results

_To fill in by the session._
