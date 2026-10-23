# v3: the loop policy, how a run knows it is done, stuck or wrong

**Date:** 2026-10-21 · **Status:** draft; decision O3 taken 2026-10-21 (the
[review](2026-10-21-v3-review.md#decisions-for-the-owner)) · **Part of:** the v3 review; it
replaces roadmap feature 2 (stall limit) and amends features 4, 5 and 7 · **Research:**
[§2](2026-10-21-v3-landscape-research.md#2-loops-and-teams) · **Runtime:** both; the judge's
model alias needs the gateway

## Outcome

Every class of task runs under a declared loop policy. A run ends because an independent judge
says the task is met or impossible, because it stopped committing, or because its budget ran out,
and never because the implementer declared itself done. Writes stay single-threaded.

## What exists

Sequential roles on one branch (`solo`, `pair`, `trio`); two review rounds, then escalation; two
CI-fix runs; two resumes; OpenHands' stuck detector (identical cycles); 500 iterations; a USD cap and
a deadline; a reviewer that may read the whole room and runs the implementer's model on the other
tier's caps; verdicts posted on the PR at once; weekly schedules. The known failure the detector
misses is the wandering run: 319 different `grep` steps, no commit, the whole budget.

## Decisions

| # | Decision | Rejected | Why |
|---|---|---|---|
| L1 | **One writer, sequential roles**; no teams, swarms or parallel candidates in production | Agent Teams; best-of-N in production | About 7× the tokens for sequential work; five of six multi-agent systems trail a single agent; the field's shape is one writer and a fresh-context judge |
| L2 | **A completion judge closes every implementer run that ends on its own.** When the conversation ends `finished`, `agent-run` asks the class's `judge` alias (default `tier-light` of the run's data class), in a fresh context with no tools, for `met`, `not_yet` or `impossible` against the acceptance checks and the checks' output. The acceptance checks are the scoper's once it exists, and until then the issue's acceptance section (the `factory-handoff` template has one) or the fenced issue text. The checks' output is the repository's checks run in the sandbox once feature 3 lands, and until then the CI check runs on the pushed head, read with `gh`. `not_yet` sends one follow-up message **into the same conversation** with the reason; at most `continuations` of them (default 2). `impossible` ends the run and posts the reason. The call leaves the pod through the identity proxy's judge path, pinned to the judge alias ([profiles P4](2026-10-21-capability-profiles-design.md#decisions)) | Self-assessment by the implementer; a judge per step; a separate run per continuation | Claude Code's and Codex's `/goal`; "tuning a standalone evaluator to be skeptical turns out to be far more tractable"; the same conversation keeps the 95% cache reads a fresh run would lose. Small judges flip with answer position, so the judge sees check output, never two candidates, and a verdict with no evidence or no parse counts `not_yet` once, then `impossible` |
| L3 | **The stall rule counts commits, and a stall ends the run without a judge.** No commit by `stallSteps` cumulative steps (default 80, above the p90 of accepted runs; the bench sets it) ends the run with what it found. A continuation that ends without a new commit is a failed iteration; two consecutive failed iterations end the run. OpenHands' detector and the 500-iteration cap stay, so the worst case is bounded by them and the USD cap | Identical-cycle detection alone; a wall-clock stall (the deadline exists) | Ralph's one-commit iteration; Symphony's `max_turns` 20; AgentForge's retries saturate after about two |
| L4 | **The reviewer never reads the implementer's transcript.** Its brief is the task, the diff, the checks' output and the handoff; `room_read` for the reviewer is argument-scoped to `handoff`, `task_state` and `review_verdict` entries ([profiles P3](2026-10-21-capability-profiles-design.md#decisions)) | The reviewer reading the room | Cognition: review works best "when the coding and review agents do not share any context beforehand"; Anthropic's QA agent "talked itself into approving" |
| L5 | **A verdict carries executable evidence or it is an abstention.** The reviewer cites the checks' output (the sandbox's after feature 3, the CI check runs before); `room_verdict` gains an `evidence` field, and the broker records an `approve` with none as `abstain`. An abstention spends no review round and sends the task to the gate, which reads it as `no_approving_verdict` (a human); it counts as the rounds ending for L6. Three to five few-shot verdicts with score breakdowns calibrate the role | A bare verdict | No review product exceeds 52% precision; position bias on small open models; Anthropic's calibration |
| L6 | **Findings reach the implementer first.** A `changes` verdict starts the revision as today, but its PR comment is posted only when the rounds end or the task escalates; every verdict stays in the room | A comment per verdict | Devin, 2026-09-30: only unfixed findings become comments; two rounds are already the cap |
| L7 | **Holdout checks for `live` classes.** A class that merges alone names, in `classes.<class>.holdoutChecks` of the factory config, checks whose definition the pull request cannot change. A CI workflow qualifies because `.github/` is a gate path (a PR touching it matches no rule), so `docs-links` is covered today by "Check the documentation links 🔗"; a class whose oracle is not in CI names a scanner re-run or a scenario suite in another repository. They must pass before the gate arms | The implementer's or tester's visible tests as the only oracle | StrongDM's holdout scenarios; ExecCritic: visible tests can be gamed; Abenhaim's "two consecutive clean passes" |
| L8 | **Models are chosen per role, never per step.** `roles.<dataClass>.<role>` names the alias per data class, and `loops.<class>.roles` overrides it per task class: the scoper and reviewer on the strong alias (the scoper's key is `triager`: the scoper is a triager run, scoper design SC1), the implementer on the bench's winner for the class; inside one conversation the model and effort never change. `roles` retires `tiers.*.model` and `templates.*.reviewerModel`; the reviewer keeps the other tier's caps. ADR-0058's data-class rule stands (no public work to Anthropic); its "same model" rule becomes "the same provider, the size per role" | Per-step switching (rejected before); the reviewer on another provider | Devin Fusion: "when the judgment is the deliverable, delegating it backfires"; a weaker primary cannot use a stronger model as a tool. **Decision O3: yes, bench-gated; ADR-0058 revised** |
| L9 | **Scheduled loops deduplicate.** A schedule skips its slot while a PR from the same schedule is open; one PR per task and the daily cap exist | — | gh-aw's `deduplicate-by-title` and `max: 1` |
| L10 | **The search subagent is an OpenHands child conversation** (`start_child_conversation`, SDK ≥ 1.56.0) on the run's own token, with a hard budget (at most 40 tool calls, a return of at most 2k tokens); the bridge mirrors its events | A second `AgentRun` | The SDK's facility; the v1 review's concern (a bridge bound to one conversation) becomes a bridge change |
| L11 | **Best-of-N lives on the bench only** (N = 3) to separate models | Production best-of-N | About +2 points for N× the cost |

## The loop

```mermaid
sequenceDiagram
  autonumber
  participant F as factory
  participant I as implementer run
  participant J as judge (tier-light, fresh context)
  participant R as reviewer run
  participant G as merge gate
  F->>I: task · acceptance checks · plan (from the scoper)
  loop until met, impossible, a stall or the budget
    I->>I: steps; commits; runs the checks
    Note over I: no commit by stallSteps → the run ends `stalled`, no judge
    I->>J: on `finished`: diff · check output · acceptance checks
    J-->>I: met | not_yet (reason) | impossible (reason)
    Note over I: not_yet → one message into the same conversation,<br/>at most `continuations` times; a continuation with no new commit is a failed iteration
  end
  I->>F: handoff (commit)
  F->>R: task · diff · check output · handoff (no transcript)
  R->>R: runs the fast checks
  R-->>F: approve + evidence | changes + findings | abstain
  Note over F,R: changes → a revision run; the PR comment waits for the rounds to end
  F->>G: head · verdict · holdout check (live classes)
```

## The policy, in the factory config

```yaml
loops:
  default:    {stallSteps: 80,  continuations: 2, judge: tier-light, reviewRounds: 2, holdout: false}
  docs-links: {stallSteps: 40,  continuations: 1, judge: none,       reviewRounds: 0, holdout: true}
  dashboards: {stallSteps: 120, continuations: 2, judge: tier-light, reviewRounds: 2, holdout: false}
roles:   # the alias per role and data class; a conversation never changes model
  public:   {triager: tier-frontier, implementer: agent-default, reviewer: tier-frontier, tester: agent-default}
  internal: {triager: tier-frontier, implementer: agent-default, reviewer: tier-frontier, tester: agent-default}
```

`implementer: agent-default` until the bake-off names a cheaper alias per class. The judge's calls
are metered on the run's token and count against the run's cap; the composition passes the judge
alias to the sidecar as `JUDGE_MODEL`, and the role's capability profile lists it.

### How a run ends, and what leaves the room

| End | Harness status | Room | Task | On the issue |
|---|---|---|---|---|
| Judge `met` | `finished` | handoff | the next role | as today |
| Judge `impossible` | `finished`, reason `judge_impossible` | `state_changed{run_phase}` with the reason; the judge's text as a run note | `Escalated`, reason `judge_impossible` | the fixed narration with the reason **category** only; no judge prose (C7: a public task's room text stays in the room) |
| Stall | `finished`, reason `stalled` | the run's findings as a note | `Escalated`, reason `stalled` | the same |
| Continuations spent | `finished`, reason `not_met` | the last `not_yet` reason as a note | `Escalated`, reason `not_met` | the same |

The per-class values reach the run through the claim: `spec.loop: {stallSteps, continuations,
judgeModel}`, an XRD field crossplane-configuration adds and the composition turns into the
harness's and the sidecar's environment. Until that release the harness image ships one default of
each, and the per-class rows in the config are not read, which the harness reference records.

## Where each piece runs

| Piece | Where | Reaches runs through |
|---|---|---|
| Judge, continuation, commit-counting stall | `agent-run` (the harness) | the harness image digest |
| `spec.loop` on the claim, `JUDGE_MODEL` on the sidecar | the `AgentRun` XRD and composition | a crossplane-configuration release and the host's pin |
| `abstain` and the `evidence` field; the end reasons | the broker's `room_verdict` and the bridge's status mapping | agent-platform |
| Loop policy, per-role aliases, deduplicated schedules | the factory config | a Flux release |
| Reviewer's brief and the deferred PR comment | the factory's brief builder and the broker's verdict post | agent-platform |
| Argument-scoped `room_read` | the gateway's capability profiles | a Flux release |
| Child conversation mirroring | the room bridge | agent-platform |
| Holdout checks | each repository's CI and steering note | the repository |

## Gate: what the bench must show

| Metric | Expected | Reading |
|---|---|---|
| Wandering share (runs past `stallSteps` with no commit) | down | the stall rule works |
| Cost per accepted PR | not up | the judge's calls pay for themselves |
| Acceptance | not down | continuations do not degrade work |
| Judge false-`met` rate (judge said met, the maintainer rejected) | measured, then a threshold | whether a `tier-light` judge is enough |
| Reviewer yield (real defects over false alarms) with L4 and L5 | up | isolation and evidence help |
| Abstentions | counted | how often an open-weight reviewer cannot decide |

Three runs per issue per variant, as the roadmap requires.

## Not in this design

Teams, swarms, parallel writers; per-step model switching; a continuation loop keyed on the PR's
state (bench-gated, as the roadmap says); memory across tasks; a standalone architect.

## Left to the builder

The judge's prompt and its few-shot set; how `agent-run` detects a commit (the branch's head
against the start); the `evidence` field's shape; the bridge's handling of child conversation ids;
the SDK bump from 1.49.6 to 1.56.0 and its gateway regression tests; the order between the
harness release (defaults) and the composition release (`spec.loop`).
