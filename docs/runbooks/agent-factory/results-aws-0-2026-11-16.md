# AWS v4 feature validation and screencasts — 2026-11-16

**Status:** in progress; live matrix paused at the foundation's owner-only GitHub prerequisites. **Procedure:**
[runbook 28](28-v4-aws-validation.md). **Design:**
[the approved campaign](../../superpowers/specs/2026-11-16-v4-aws-validation-design.md).

## Baseline

| Item | Value |
|---|---|
| ai-native-ref SHA | `1d1a14aa9d4b10e67cfefbf5630ebe6d853371d0` (`origin/main`) |
| ai-native-ref artifact tag and digest | Signed PR artifact `v3.27.1-pr412.gc50d1017`, source `c50d101734e13d850ef27c9235df18f6e2d2a7d6`, digest `sha256:79d80a7270afbe3d407ebcc614f0d95f199d5a9a865c4e5de0fdfa86b0d116ff`; no release tag created |
| cloud-native-ref SHA | Bootstrap `b7395ca66bbc9a32be8ce5bc5fe216a57e55e33e`; v4 pin PR [#2863](https://github.com/Smana/cloud-native-ref/pull/2863), branch commit `2a067fec` |
| Maku version | `v0.53.1`, source `417ddd5409152a0dc3f9574a872d4ead9dc33860`; local CLI `maku-linux-amd64` checksum verified |
| Harness and bridge image digests | Harness `sha256:104c1749567ccff3864aeab7856bf1d9c2b4f7bd0398d522f6f59b69b36813cf`; bridge `sha256:3648b20957f64a6c0a18f7dedd8bc8e8b8a73ffd1981ea042e8c5aa4b8f456ea` |
| aws-0 Kubernetes and agentgateway versions | EKS API `1.36`, nodes `v1.36.5-eks-577a51e`; agentgateway chart and image `v1.6.0` |
| Campaign start / end | Started 2026-11-17 08:24 Europe/Paris; running |
| Final `task check` at the tested SHA | ai-native-ref #412 CI passed; host #2863 local `task check`: 3,409 resources valid, 85 passed, 1 skipped, 0 failed |

## Foundation and adjacent regression

| ID | Result | Evidence |
|---|---|---|
| B1 — fixed source and released pins | PASS | Cosign verified the artifact against `ci.yaml@refs/pull/412/merge`; Flux applies digest `79d80a72` and Maku `v0.53.1`. No GCP deployment or release tag. |
| B2 — Flux, Helm, pod health and strict preflight | BLOCKED | Flux, Helm and required workloads are Ready. `maku preflight --strict --json`: 11 pass, 3 fail, 4 skip. `github-link=link_client`; merge-gate/private-code were initially undecided. The merger App has `statuses:read`, but `gateStatus` requires `statuses:write`; the GitHub OAuth client is absent from `agents/github-link`. |
| B3 — Factory, Repository and MergePolicy readiness | PASS | Factory and all four Repositories were Accepted and Connected; the evaluation overlay was removed. All merge classes remained shadow (`LIVE=0`). A temporary `policyBot: true`, `gateStatus: false` fallback proved intake, then was fully removed and the shipped built-in-gate defaults restored. |
| B4 — identity, short-lived tokens, gVisor and egress | NOT RUN | Paused by B2; no campaign task filed. |
| B5 — settings live edit, refused edit and Git restore | NOT RUN | Paused by B2. |
| B6 — OpenCode and Slack L1–L17 proofs | BLOCKED | GitHub account link, Slack console URLs, and second-person/unlinked Slack actors are unavailable. The public Slack endpoint correctly returns `401` to an unsigned POST. |
| B7 — repository checks, observability and alerts | NOT RUN | Paused by B2. |
| B8 — role and charged-identity cost | NOT RUN | Paused by B2. |
| B9 — RunLore `kb_search` from a triager | NOT RUN | RunLore principals and both webhook keys are restored; live incident/entry proof paused by B2. |

## Workflows

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| W1 — repository default selects `standard` | NOT RUN | | Paused by B2; no campaign task filed. |
| W2 — `quick` by override and scheduled/revert source | NOT RUN | | Paused by B2. |
| W3 — `careful` role chain and judge continuation | NOT RUN | | Paused by B2. |
| W4 — label and confirmation selection | NOT RUN | | Paused by B2. |
| W5 — legacy, unknown, conflicting and non-maintainer pins | NOT RUN | | Non-maintainer actor also unavailable. |
| W6 — `quick` with a verdict-requiring policy | NOT RUN | | Paused by B2. |
| W7 — `maku repo add` and `repo check` for four repositories | FAIL | [maku#616](https://github.com/Smana/maku/issues/616) | v0.53.1 `repo add` requires public `GET /apps/{slug}` metadata. All three private Apps answer 404; no declarations were generated and no App visibility was changed. |
| W8 — planner catalog discovery on `runlore-kb` | NOT RUN | | Paused by B2. |

## Merge policies

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| M1 — diff selection and `no_policy_matched` | NOT RUN | | Paused by B2. |
| M2 — unbound catalog shadow evidence | NOT RUN | | Paused by B2. |
| M3 — bounds, protected paths, size and `modifyOnly` | NOT RUN | | Paused by B2. |
| M4 — hold and approval precedence | NOT RUN | | Paused by B2. |
| M5 — strictest selection, cap/pause and no fall-through | NOT RUN | | Paused by B2. |
| M6 — reviewer verdict requirement | NOT RUN | | Paused by B2. |
| M7 — UI, CLI and API maintainer journeys | NOT RUN | | Exact Maku `v0.53.1` source staged for offline fixtures; GitHub link and merger permission missing. |
| M8 — live merge, revert, breaker and recovery | BLOCKED | | Built-in gate unavailable while the merger lacks `statuses:write`; valid existing `docs-links` promotion evidence is also unproven. No threshold or policy was changed. |

## Screencasts

| ID | Result | Source issue / PR | Export and publication links |
|---|---|---|---|
| S1 — 20–30 second handoff-to-PR cut | BLOCKED | | Browser-based 1920×1080 WebM recording is proven with Playwright and system Chromium. The real task, GitHub link and approval-as-merge path are unavailable. |
| S2 — approximately one-minute end-to-end cut | BLOCKED | | Same foundation blockers; no raw task footage exists yet. |

## Failures, fixes and reruns

| Test ID | Failure evidence | Fix PR | Rerun result |
|---|---|---|---|
| Bootstrap | The task timeout interrupted EKS creation before state recorded it; a stale lock and 409 followed. | Operational recovery only | Released the known stale lock, imported the existing ACTIVE cluster, restored the generated module file, and completed deployment plus OpenBao OIDC verification. |
| Foundation | Broker migrate recorded through `20261120120000`; Atlas then completed `20261121120000`, triggering the two-ledger refusal. | [ai-native-ref#413](https://github.com/Smana/ai-native-ref/pull/413) | Verified Atlas 9/9 and the shipped hash, recorded the applied migration, and both broker and factory became Ready. PR `task check`: 67 passed, 4 skipped, 0 failed. |
| B3 | aws-0 shipped `evaluation: {controlPercent: 70, treatment: careful}` despite the campaign forbidding it. | [ai-native-ref#414](https://github.com/Smana/ai-native-ref/pull/414) | Live overlay removed; PR `task check`: 67 passed, 4 skipped, 0 failed. |
| B2 | Merger App has `statuses:read`; `MergerPermissions(..., status=true)` requires write. Direct factory-App mint succeeds. | Owner console required | Temporary legacy fallback connected all four repositories with all classes shadow. Built-in merge-gate tests remain paused. |
| B2 / B6 | `agents/github-link` is absent and the ExternalSecret cannot sync. | Owner console required | Factory OAuth callback and OpenBao path documented; no credential was invented or shared with the ZITADEL OAuth client. |
| W7 | Private factory, agents and merger Apps all return 404 from the public app endpoint. | [maku#616](https://github.com/Smana/maku/issues/616) | Recorded without changing App visibility. |

## Out of scope and residual gaps

- The workflow value experiment and runbook 27's 40-task comparison.
- GCP, the laptop quickstart, generic-cluster installation and a release tag.
- Historical runbooks unrelated to the shipped workflow and merge-policy changes.

| Gap | Reason | Follow-up |
|---|---|---|
| Merger `statuses:write` | GitHub App permissions cannot be changed through the REST API. | In `ogenki-agent-merger` settings, grant Statuses read/write and approve the permission change. |
| GitHub account link OAuth client | The factory App's OAuth client secret was not present in the restored OpenBao snapshot. | Store `client_id` and `client_secret` in `agents/github-link`; callback `https://rooms.priv.aws.ogenki.io/link/github/callback`. |
| Slack Request URLs | No Slack console access is available. | Set Event Subscriptions and Interactivity to `https://factory-slack.cloud.ogenki.io/slack/events`. |
| Second-person and unlinked Slack actors | The owner and second accounts are unavailable. | Run L10, L11, L15, L16 and W5-untrusted with the real actors. |
| Credential exposure during operations | A Kubernetes Secret inspection accidentally printed restored credentials into the operator transcript. | Rotate the exposed provider API keys and factory/agents/merger private keys; do not reuse the transcript values. |

## Cleanup

| Check | Result | Evidence |
|---|---|---|
| Temporary switches and test-specific limits removed | PASS | Evaluation and Atlas are removed live. The legacy fallback and every repository override were removed; shipped `gateStatus: true` / `policyBot: false` defaults are restored. |
| No active test tasks or unintended open test PRs | PASS | No campaign task was filed. Host #2863 and fixes #413/#414 await their normal gates. |
| Final baseline healthy | NOT RUN | Flux and workloads are Ready; strict preflight remains blocked as recorded. |
| aws-0 retained for verification; no automatic teardown | PASS | aws-0 remains running. No GCP deployment or release tag occurred. |
