---
title: Gate reasons and run endings
linkTitle: Gate reasons
weight: 15
description: "The merge-gate reason codes and role run endings that this platform's bound policies and workflow loop settings can produce."
lastVerified: 2026-11-15
diataxis: values
---

Every merge-gate decision and agent run writes a machine-readable reason code in the issue comment, the
pull request's hidden `agent-factory-decision` record, and the room log; the evaluation order and each
reason's meaning and next step are in Maku's
[merge gate reference]({{< maku "docs/factory.md#the-merge-gate" >}}) and
[narration reference]({{< maku "docs/reference/narration.md" >}}).

## Reasons and endings produced here {#terms}

<span id="bypass"></span><span id="decision-rows"></span><span id="settings"></span><span id="caps"></span><span id="reasons"></span><span id="role-endings"></span><span id="decision-record"></span>

Example (the reference host): because this platform runs `gateStatus: true` (the factory's gate
posts `maku/merge-gate`), `approveToMerge: true`, central policy bindings, oracle checks on
`dead-links`, and `renovate/stability-days` on adopted Renovate policies, its repositories can
produce the following subset of Maku's codes:

| Source on this platform | Codes produced here | Manifest path |
|---|---|---|
| Base and CI checks (`merge.leakScanCheck`, `merge.requiredChecks`, `merge.contractCheck`) | `secret_scan_red`, `not_owned`, `ci_red`, `contract_modified`, `not_mergeable` | `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml`, `tooling/base/agent-factory/resources/repository-ai-native-ref.yaml` |
| Maintainer review and approve-to-merge (`approveToMerge: true`) | `maintainer_approved`, `not_agent_authored`, `approval_stale`, `changes_requested`, `held`, `reentered_approved`, `reentered_unheld` | `tooling/base/agent-factory/resources/factory.yaml` |
| Bound policy mode and reviewer verdict (`spec.mergePolicies`) | `class_unarmed`, `shadow_would_arm`, `no_approving_verdict`, `head_unreported`, `verdict_stale`, `foreign_trailer`, `human_commit_in_pr` | `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml`, `tooling/base/agent-factory/resources/repository-ai-native-ref.yaml` |
| Policy fences, holdouts, oracle and release age (`MergePolicy.spec`) | `file_not_allowed`, `file_protected`, `file_added_or_deleted`, `patch_too_large`, `class_mismatch`, `holdout_red`, `oracle_finding_open`, `oracle_unrequested`, `release_age_pending` | `tooling/base/agent-factory/resources/mergepolicy-dead-links.yaml`, `tooling/base/agent-factory/resources/mergepolicy-deps-patch.yaml`, `tooling/base/agent-factory/resources/mergepolicy-kb-entries.yaml` |
| Breaker and daily caps (`mergeDefaults.breaker`, `merge.maxPerDay`) | `class_paused`, `auto_merge_cap`, `reentered_unpaused`, `reentered_day_turned` | `tooling/base/agent-factory/resources/factory.yaml`, `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml` |
| Role endings (`spec.workflows`, `spec.loops`, `spec.templates`) | Scoper (`careful`): `ready`, `question`, `split_proposed`, `budget_calls` (parent split ends `children_merged`, `child_dropped`, `budget-family`); Tester (`testFirst`): `contract_ready`, `not_testable`, `contract_not_red`, `contract_outside_tests`, `contract_invalid`, `contract_disputed`; Implementer/Judge: `met`, `not_yet`, `impossible`, `judge_impossible`, `stalled`, `not_met`, `deadline`, `budget-run`, `agent_error`, `stuck`; Reviewer (`standard`, `careful`): `review_rounds_exhausted`, `no_verdict`; Triager (`investigate`): `proposal_ready`, `no_action` | `tooling/base/agent-factory/resources/factory.yaml` |

Unlike a configuration that routes the gate through a separate policy engine or declares
`requiresApproval` policies, this platform evaluates policies in the factory gate (`maku/merge-gate`)
and declares no `requiresApproval` policies in `tooling/base/agent-factory/resources/`, so
`policy_absent`, `policy_pending` and approval-grant codes do not fire here.
