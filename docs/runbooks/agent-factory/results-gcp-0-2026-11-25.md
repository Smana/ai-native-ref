# Maku v0.54.0 live checks on gcp-0 — 2026-11-25

The pending results file for [runbook 29](29-maku-v054-live-checks.md): the Maku v0.54.0 adoption
checks, run one feature at a time on gcp-0. Each check is one scratch issue or pull request; its
URL goes in `Issue or PR`, and `Date` records when the result was observed. Nothing is run yet:
every check is `pending`.

## 0. Baseline

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| `Factory` is `Accepted` and `Ready` with no deprecation warning (no `templates`) | | pending | | |
| Every `Repository` is `Ready` with `BindingsValid` true | | pending | | |
| The brief ConfigMap holds `security-reviewer.md` | | pending | | |
| Factory, broker and run-controller image digests recorded | | pending | | |

## 1. Step up once

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Automatic: unlabelled impossible-edit issue steps up to `careful` | | pending | | |
| Pinned: `workflow:standard` on the same text gives an offer; `/factory retry deeper` steps it | | pending | | |
| Slack: the same request over Slack (`maxCostUSD: 2`) never steps; **Run again deeper** refused `deeper_over_cap` | | pending | | |
| Host: one issue on `Smana/cloud-native-ref` gets the host's `stepUp: ask` offer | | pending | | |

## 2. Outcomes and the plan gate

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| `plan-first`: plan comment, `factory/plan-proposed`, **Approve** and **Revise** | | pending | | |
| `review`: a person's pull request labelled `factory/review` gets one verdict, no push, no merge | | pending | | |
| `report`: a "why" issue gets findings on the issue, no branch; `/factory fix` files a `change` task | | pending | | |
| Required plan: an unlabelled change under `observability/` on the host scopes before implementing | | pending | | |

## 3. The room's acts and whole plans

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Answer | | pending | | |
| Retry | | pending | | |
| Run again deeper | | pending | | |
| Accept the split | | pending | | |
| Approve a plan | | pending | | |
| Revise a plan | | pending | | |
| Split a plan | | pending | | |
| Stop | | pending | | |
| New task (`file`) | | pending | | |
| A request wide enough for three issues: `start` files all three in order | | pending | | |

## 4. The custom workflow

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| One issue labelled `workflow:thorough`: rail, `AgentRun` persona and gate verdict | | pending | | |

## 5. OpenCode, one task

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| One small issue labelled `harness:opencode`: profile, image and admission | | pending | | |
| If it escalates: `/factory retry harness=openhands` moves it back (`cohort: rescue`) | | pending | | |
| The 50/50 trial report once each arm has 30 ended tasks | | pending | | |

## 6. Merge policies

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Reverts merge themselves: `factory/revert` on a merged `docs-links` pull request | | pending | | |
| Pause and resume: `maku policy pause` and `maku policy resume` | | pending | | |
| Promotion: **Promote to live** for `dead-links` after five clean decisions and a passed drill | | pending | | |
| The reasons: `maku policy list` and `maku policy explain` on one decision of each repository | | pending | | |

## 7. Close

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Scratch and promotion pull requests closed, scratch labels removed, paused repository resumed, every failure recorded | | pending | | |
