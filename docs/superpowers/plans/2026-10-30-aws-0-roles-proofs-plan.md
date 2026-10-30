# The aws-0 session, the roles' proofs — Live Proof Plan

> **For agentic workers:** this plan is run live with the owner at the keyboard, as a section of
> the [aws-0 merge-gate session plan](2026-10-29-aws-0-merge-gate-session-plan.md) once that
> plan's pull request (#233) has merged; until then it stands alone. Every `[OWNER]` step is
> theirs. Record every result in `~/.cache/v3/aws-0-session-<date>.md` as it lands.

**Goal:** One paired measurement per role on aws-0, in the runbook layers' order, so that at
teardown every role has a cost and a value number, and the open drills (SQ5a, the accepted split,
the tester's holds, the reviewer's evidence, a judged `scripts` part) have a reading.

**Architecture:** The session switches (HR10) are session-only config commits, reverted at
teardown. The proofs (HR11) run in the layers' order: scoper, judge, checks, search, splitter,
tester, then the reviewer arm throughout and the triager's stage 2. Each proof names its pass
criterion and its stop condition.

**Spec:** [the harness roles design](../specs/2026-10-30-harness-roles-design.md), HR10 and HR11;
the [study](../specs/2026-10-30-harness-roles-research.md), section 8 (P1–P10).

## Global Constraints

- **Prerequisites:** the Maku release with the roles' PRs 1–2 pinned (the adopt PR 3 merged), the
  harness image pin bumped in the composition (or P1 and P2's HR2/HR5 rows are skipped and said
  so), the merge-gate session plan's section 0 done.
- **Session switches, each one commit, reverted at teardown:** `loops.docs.models.reviewer.frontier: kimi-frontier`
  (the F15 arm; check the exact key in `helm-values-configmap.yaml`'s `loops` comments and the
  F15 design before writing it); `testFirst: true` and `checks: true` on cloud-native-ref
  `scripts`; `search: false` on a scratch class `docs-nosearch` cloned from `docs` for SQ5a's off
  arm.
- **Nothing goes live** (no class switch to `live`); the drills use scratch issues the drill texts
  of which live outside the repositories the agents read (`~/.cache/v3/drills/`).
- **Stop** means record and move on; no fix on the cluster.
- **Naming.** "Agent Factory" is the product; Maku is the controller.

---

## The proofs

| # | Role, layer | Drill | Pass | Stop |
|---|---|---|---|---|
| P1 | Scoper, layer 1 | A (vague), B (no acceptance), I (inline `Acceptance:`), W (a whole-tree `docs` issue) | A → `ready`; B → `needs_author` with the acceptance question; I → `ready` (HR3); W → a nudge logged at 25 calls and either a handoff or `budget_calls` at 40 (HR2), never a USD budget-run; `maku_factory_scoper_runs_total{outcome="budget"}` unchanged over the session | A scoper over 40 tool calls still running |
| P2 | Judge, layer 2 | D (met), E (a failing check), E2 (a missing path), E3 (unmakeable), Pn (a check pending at `finished`) | D `met` with evidence; E never `met`; E2 `not_yet`; E3 `impossible`; Pn: no continuation sent while only pending (HR5), the run ends `met` or `not_met` within the box; a failing check's continuation quotes the log tail or the "not readable" sentence | A continuation sent on a pending-only guard |
| P3 | Judge on a `scripts` part | One part of P6's family | An `agent-run judge 1:` line on the part's run reading the part's acceptance (HR7); `maku_factory_loop_runs_total{class="scripts"}` ≥ 1; no `met` with a red check | The part ends with no judge line |
| P4 | Implementer checks, layer 3 | F2-type seeded failure on both repositories | Fixed before the first push; one push; `fixRuns` 0; the ANR run's step log shows no `helm` install (HR8) | A `helm` install in the step log |
| P5 | Search, layer 4 (SQ5a) | Two pairs of `docs` drills with identical text, one on `docs` (search on), one on `docs-nosearch` | Per arm: acceptance (the owner merges or not), cost per accepted PR, calls made, the ledger's `budget` + `error` share; pass when the on arm's acceptance ≥ off and its cost per accepted PR ≤ off; with N = 2 pairs the result is directional and recorded as such | — |
| P6 | Splitter, layer 5 | A three-area `scripts` issue → proposal → `/factory split` | Part 1 "Part 1 of N of #p" with `factory/child-of:#p`, `pair` at `standard`, no scoper, judged (P3); part 2 opens only after part 1 is `Done`; the parent `Done children_merged`; family spend ≤ $20.40; each part's diff within its `touches` | Part 2 opens before part 1 merges; a part outside its `touches` |
| P7 | Tester, layer 6 (T1–T3) | Testable, holds and holdout drills on cloud-native-ref `scripts` with the switches on | T1 `contract_ready`, `Test contract` passing; a staged contract edit refused by the pre-commit hook; a handoff to `tester` → `Escalated contract_disputed`; an edited contract at the gate → `contract_modified`; a rebase keeps the contract; a README task → `not_testable` with no grep test | The implementer changes a contract file and merges |
| P8 | Reviewer, the arm | Every review run of the session; `docs` tasks alternate the arm | 100% of summaries name at least one acceptance check (HR4) and cite `agent-checks`' first line or a check run; verdicts on the Kimi arm carry `servedModels [k3.1-pro]`; agreement with the owner's merge decision counted per arm; cost per review per arm from the `role` label (HR6) | A summary that quotes the implementer's handoff |
| P9 | Triager | RunLore stage 2 | A `persisting` verdict recorded; an intake past the cap answers `429 daily_task_cap`; one real proposal published | — |
| P10 | Cross-role, teardown | The session's read | Per-role cost and duration from `maku_factory_run_cost_usd{role}`; the false-`met` count (judge `met`, maintainer rejected); for every implementer run the time from handoff to `finished`; the scoper's outcome distribution | — |

## Order

1. P1 and P2 on this repository's `docs` (scratch issues), P4 on both.
2. P5's two pairs, interleaved with P1/P2 so the day's cap is not met.
3. P6 on cloud-native-ref `scripts`, then P3 on its first part.
4. P7 with the `testFirst` switch on, then off.
5. P8 throughout; P9 when a RunLore finding arrives or is seeded.
6. P10 at teardown, before the switches are reverted.

## Teardown

- [ ] The session file holds every proof's PASS/FAIL/STOP with its evidence line and P10's table.
- [ ] The switches are reverted (three commits, or one).
- [ ] The status page's rows 1, 2, 4, 5 and 6 and the roles page read what passed; the "used live
      once" wording for search changes only if P5 passed.
- [ ] The design's open questions get their answers (the condenser, `actions: read`, the tester on
      parts, the `scripts` p90 steps, `GET /v1/models` per cloud).
- [ ] Worth filing to the wiki: anything that contradicts a runbook.

## Self-review

- **Spec coverage.** HR10's three switches; HR11's P1–P10 with pass and stop criteria; the order
  follows the runbook layers.
- **Placeholders.** The F15 key is to be read from the config comments before the commit, named
  as such; the drill texts live outside the repositories, as the contamination finding requires.
