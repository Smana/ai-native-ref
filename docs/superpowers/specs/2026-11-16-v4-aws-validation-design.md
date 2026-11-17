# AWS v4 feature validation and the two factory screencasts: design

**Status:** approved by the owner in a grilling session on 2026-11-16. **Execution:**
[runbook 28](../../runbooks/agent-factory/28-v4-aws-validation.md). **Evidence:**
[the dated campaign report](../../runbooks/agent-factory/results-aws-0-2026-11-16.md).

## Outcome

One aws-0 campaign has two independent deliverables:

1. Validate the features shipped since Agent Factory v3, with deep functional coverage of workflows
   and merge policies and targeted regression of the shared surfaces they use.
2. Record and export the two screencasts required by issue #394: a 20–30 second handoff-to-PR cut
   and an approximately one-minute end-to-end cut. Both use one real `Smana/ai-native-ref` defect,
   handed off from OpenCode.

This is not the roadmap's full "anyone can run it" release gate. It does not include a laptop
quickstart, a generic-cluster production install, GCP, or a release tag.

## Owner decisions

| # | Decision | Excluded alternative |
|---|---|---|
| D1 | Validate shipped v4 behavior on aws-0, especially workflows and merge policies | Treating an EKS rebuild as the whole v4 adoption gate |
| D2 | Produce exactly the two screencasts in issue #394 | Recording every test or making a separate long showcase |
| D3 | Workflow functional acceptance only | The 30-task-per-arm value experiment and runbook 27's 40-task comparison |
| D4 | Full merge-policy functional coverage with controlled live drills | Generating 5/20 decisions only to satisfy promotion thresholds |
| D5 | Deep core coverage plus targeted adjacent regression | Repeating every historical runbook |
| D6 | Real ai-native-ref PRs for the drills; unsafe cases stay unmerged | Moving validation to a disposable repository |
| D7 | Fail fast on foundation faults; continue independent feature tests after isolated failures | Stopping everything on any failure, or continuing through foundation faults |
| D8 | Real defects for successful paths and media; synthetic inputs for adversarial cases | Synthetic text everywhere, or waiting for organic failures |
| D9 | Exercise merge-policy gate, UI, CLI and API | Testing only merge decisions |
| D10 | Exercise all three workflows and every selection path | Testing only the role chains or only user-facing selection |
| D11 | Keep existing production caps; split the campaign across days if needed | A temporary budget increase |
| D12 | Fix core blockers in focused PRs and rerun affected tests | Validation without fixes, or fixing only media blockers |
| D13 | Test one recorded `origin/main` SHA with released pins | A moving main or an unmerged validation branch |
| D14 | Use OpenCode and one recorded task for both edits | Different clients or tasks for the two cuts |
| D15 | Publish one dated report and update affected runbooks | Evidence scattered only in issue comments |
| D16 | One representative autonomous merge/revert/breaker/recovery chain | Repeating the live chain for every eligible policy |
| D17 | Restore aws-0 and retain it temporarily for verification; teardown is separate | Immediate teardown or leaving temporary switches on |
| D18 | Execute autonomously inside this approved matrix | A checkpoint before every state-changing test |

## Test matrix

The runbook gives the commands and expected observations. The report carries one row per test ID.

| Group | IDs | Coverage |
|---|---|---|
| Foundation | B1–B9 | Fixed baseline, bootstrap health, preflight, released pins, settings objects, identity, gVisor, the complete coding-agent/Slack L1–L17 proofs, observability, cost and RunLore `kb_search` |
| Workflows | W1–W8 | `quick`, `standard`, `careful`; defaults, labels, confirmation, schedules, refusals, role order, caps, gate interaction, repository onboarding and catalog discovery |
| Merge policies | M1–M8 | Diff selection, shadow evidence, bounds, precedence, strictest selection, reviewer rule, all maintainer interfaces, and one live safety chain |
| Screencasts | S1–S2 | The short and long cuts from issue #394, from the same recorded task |

### Workflow acceptance

- An ordinary repository task defaults to `standard` and runs implementer then reviewer.
- `quick` runs an implementer only, both through an explicit maintainer choice and the scheduled or
  revert source that defaults to it.
- `careful` runs scoper, implementer with search, judge and reviewer; the tester remains a
  repository opt-in. A judge's `not_yet` uses the shipped continuation bound.
- Repository defaults, maintainer labels and confirmation choices select the intended workflow.
  Legacy `class:` and `profile:` labels select nothing and produce the shipped narration. Unknown,
  conflicting and non-maintainer pins are refused and narrated; the task then runs as if unpinned.
- A `quick` PR evaluated by a policy without a diff shape or oracle waits with
  `reviewer_verdict_missing`; adding a reviewer changes that input on a subsequent task.
- `maku repo add` writes a repository's current declaration into scratch space without applying it,
  and `maku repo check` passes for all four served repositories. A coding-agent handoff for
  `Smana/runlore-kb` discovers the repository and its workflow from the factory catalog, not a
  second broker list.

### Merge-policy acceptance

- A PR needs no class label: every applicable policy reads the reported diff. No match yields
  `no_policy_matched` and a `considered=` explanation.
- Catalog policies collect shadow evidence without a binding. Bounds, protected paths, size caps,
  `modifyOnly`, holdouts and the reported head are evaluated as declared.
- `factory/hold` yields `held`; a current-head maintainer approval takes the approved-merge path;
  stale approval never merges.
- The strictest matching live policy decides. Pause or cap sends the PR to a human without falling
  through to a looser policy.
- Settings UI, CLI and API agree on inspection, editing, structural validation, simulation,
  evidence, promotion and any eligible remembered approval.
- The live chain runs only with valid existing promotion evidence. It proves one ai-native-ref
  `docs-links` merge, its revert, breaker pause and recovery. Missing evidence blocks this test; it
  never justifies lowering the promotion requirement or moving the drill elsewhere.

## Execution and completion

Foundation failures stop the campaign. A feature failure pauses dependent cases, while independent
cases continue. Core blockers are fixed through focused PRs; the baseline and affected evidence are
then refreshed. Existing per-run, task, policy and daily caps stay unchanged.

Record the screencasts only after their exact path is green. Capture one complete task and edit the
same footage twice. The long cut retains the planner's clarification question and trust evidence;
the short cut omits them.

The campaign is complete when:

- every foundation, workflow and merge-policy row is PASS, or an explicitly recorded BLOCKED row has
  an owner-visible reason and linked follow-up;
- every failure fixed during the campaign has a passing rerun;
- both recordings are exported and issue #394 has their links and remaining site/README work;
- temporary switches and test-specific limits are gone, no test task is still active, and the
  baseline is healthy;
- the report names the final versions and any residual gaps.
