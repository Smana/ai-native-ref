# AWS v4 feature validation and screencasts — 2026-11-16

**Status:** prepared, not run. **Procedure:** [runbook 28](28-v4-aws-validation.md). **Design:**
[the approved campaign](../../superpowers/specs/2026-11-16-v4-aws-validation-design.md).

## Baseline

| Item | Value |
|---|---|
| ai-native-ref SHA | |
| ai-native-ref artifact tag and digest | |
| cloud-native-ref SHA | |
| Maku version | |
| Harness and bridge image digests | |
| aws-0 Kubernetes and agentgateway versions | |
| Campaign start / end | |
| Final `task check` at the tested SHA | |

## Foundation and adjacent regression

| ID | Result | Evidence |
|---|---|---|
| B1 — fixed source and released pins | NOT RUN | |
| B2 — Flux, Helm, pod health and strict preflight | NOT RUN | |
| B3 — Factory, Repository and MergePolicy readiness | NOT RUN | |
| B4 — identity, short-lived tokens, gVisor and egress | NOT RUN | |
| B5 — settings live edit, refused edit and Git restore | NOT RUN | |
| B6 — OpenCode and Slack L1–L17 proofs | NOT RUN | |
| B7 — repository checks, observability and alerts | NOT RUN | |
| B8 — role and charged-identity cost | NOT RUN | |
| B9 — RunLore `kb_search` from a triager | NOT RUN | |

## Workflows

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| W1 — repository default selects `standard` | NOT RUN | | |
| W2 — `quick` by override and scheduled/revert source | NOT RUN | | |
| W3 — `careful` role chain and judge continuation | NOT RUN | | |
| W4 — label and confirmation selection | NOT RUN | | |
| W5 — legacy, unknown, conflicting and non-maintainer pins | NOT RUN | | |
| W6 — `quick` with a verdict-requiring policy | NOT RUN | | |
| W7 — `maku repo add` and `repo check` for four repositories | NOT RUN | | |
| W8 — planner catalog discovery on `runlore-kb` | NOT RUN | | |

## Merge policies

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| M1 — diff selection and `no_policy_matched` | NOT RUN | | |
| M2 — unbound catalog shadow evidence | NOT RUN | | |
| M3 — bounds, protected paths, size and `modifyOnly` | NOT RUN | | |
| M4 — hold and approval precedence | NOT RUN | | |
| M5 — strictest selection, cap/pause and no fall-through | NOT RUN | | |
| M6 — reviewer verdict requirement | NOT RUN | | |
| M7 — UI, CLI and API maintainer journeys | NOT RUN | | |
| M8 — live merge, revert, breaker and recovery | NOT RUN | | |

## Screencasts

| ID | Result | Source issue / PR | Export and publication links |
|---|---|---|---|
| S1 — 20–30 second handoff-to-PR cut | NOT RUN | | |
| S2 — approximately one-minute end-to-end cut | NOT RUN | | |

## Failures, fixes and reruns

| Test ID | Failure evidence | Fix PR | Rerun result |
|---|---|---|---|

## Out of scope and residual gaps

- The workflow value experiment and runbook 27's 40-task comparison.
- GCP, the laptop quickstart, generic-cluster installation and a release tag.
- Historical runbooks unrelated to the shipped workflow and merge-policy changes.

| Gap | Reason | Follow-up |
|---|---|---|

## Cleanup

| Check | Result | Evidence |
|---|---|---|
| Temporary switches and test-specific limits removed | NOT RUN | |
| No active test tasks or unintended open test PRs | NOT RUN | |
| Final baseline healthy | NOT RUN | |
| aws-0 retained for verification; no automatic teardown | NOT RUN | |
