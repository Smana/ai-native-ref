# AWS v4 feature validation and screencasts — 2026-11-16

**Status:** in progress; aws-0 is running and the catalog deployment blocker is being fixed. **Procedure:**
[runbook 28](28-v4-aws-validation.md). **Design:**
[the approved campaign](../../superpowers/specs/2026-11-16-v4-aws-validation-design.md).

## Baseline

| Item | Value |
|---|---|
| Initial ai-native-ref SHA | `1d1a14aa9d4b10e67cfefbf5630ebe6d853371d0` (`origin/main`) |
| Initial artifact tag and digest | Signed PR artifact `v3.27.1-pr412.gc50d1017`, source `c50d101734e13d850ef27c9235df18f6e2d2a7d6`, digest `sha256:79d80a7270afbe3d407ebcc614f0d95f199d5a9a865c4e5de0fdfa86b0d116ff`; no release tag created |
| cloud-native-ref SHA | Bootstrap `b7395ca66bbc9a32be8ce5bc5fe216a57e55e33e`; v4 pin PR [#2863](https://github.com/Smana/cloud-native-ref/pull/2863), merged as `e7bf01f0b761fce08a3c94874f62827b078fa2b8` |
| Initial Maku version | `v0.53.1`, source `417ddd5409152a0dc3f9574a872d4ead9dc33860`; local CLI `maku-linux-amd64` checksum verified |
| Catalog fix under validation | Maku [#618](https://github.com/Smana/maku/pull/618), merged; signed chart `0.53.2-pr618.g9d0bdb48` at digest `sha256:312dd4d13e15c7607ea75bb555e5d3506c8e1ab9469ee4de246f973c482caa4a`; ai-native-ref [#422](https://github.com/Smana/ai-native-ref/pull/422) |
| Harness and bridge image digests | Harness `sha256:104c1749567ccff3864aeab7856bf1d9c2b4f7bd0398d522f6f59b69b36813cf`; bridge `sha256:3648b20957f64a6c0a18f7dedd8bc8e8b8a73ffd1981ea042e8c5aa4b8f456ea` |
| aws-0 Kubernetes and agentgateway versions | EKS API `1.36`, nodes `v1.36.5-eks-577a51e`; agentgateway chart and image `v1.6.0` |
| Campaign start / end | Started 2026-11-17 08:24 Europe/Paris; running |
| Validation gates | Host #2863 local `task check`: 3,409 resources valid, 85 passed, 1 skipped, 0 failed. Maku #618 full `task check` passed, including 1,404 UI tests; all PR checks green. |

## Foundation and adjacent regression

| ID | Result | Evidence |
|---|---|---|
| B1 — fixed source and released pins | PASS | Cosign verified the initial artifact against `ci.yaml@refs/pull/412/merge`. Subsequent fixes use signed PR artifacts and are recorded above; no GCP deployment or release tag. |
| B2 — Flux, Helm, pod health and strict preflight | PARTIAL | Flux, Helm and required workloads are Ready. GitHub login and `/link/github` succeeded; `maku doctor` has no failures and its skill and OpenCode checks pass. Merger `statuses:write`, Agents `issues:write`, and Slack event/interactivity URLs are configured. An earlier strict preflight returned 15 pass, 3 skip, 0 fail; rerun after the catalog rollout is pending. |
| B3 — Factory, Repository and MergePolicy readiness | PARTIAL | Factory and all four Repositories were Accepted and Connected. Flux reintroduced `evaluation: {controlPercent: 70, treatment: careful}`; permanent removal merged in #414 and the corrected pin will remove it on rollout. |
| B4 — identity, short-lived tokens, gVisor and egress | PASS | Run `z7cl6h2k` used gVisor, its own ServiceAccount token and seccomp `0`, per-run default-deny, and proxied GitHub. Direct GitHub/API/example egress was denied. Raw claim: `run-z7cl6h2k-agentrun.yaml` in the campaign evidence directory. |
| B5 — settings live edit, refused edit and Git restore | PASS | An invalid workflow was refused while the previous configuration remained available; Flux restored `standard`. |
| B6 — OpenCode and Slack L1–L17 proofs | PARTIAL | `maku setup opencode` and `maku doctor` pass. MCP exposes exactly `handoff`, `start`, `inbox`, `task`, `wait`, `answer`; removed `intake_plan` returns `unknown tool`. Second-person/unlinked Slack actors remain unavailable. |
| B7 — repository checks, observability and alerts | NOT RUN | Waits for the corrected catalog rollout and terminal tasks. |
| B8 — role and charged-identity cost | NOT RUN | Waits for terminal tasks. |
| B9 — RunLore `kb_search` from a triager | NOT RUN | RunLore principals, both webhook keys, fences and required rulesets are restored. The reviewed-entry/triager proof is pending. |

## Workflows

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| W1 — repository default selects `standard` | PARTIAL | [#416](https://github.com/Smana/ai-native-ref/issues/416) / `2kglebvy` / [#421](https://github.com/Smana/ai-native-ref/pull/421) | Standard implementer and reviewer succeeded. AwaitingHuman/`no_policy_matched` because the chart catalog was absent; gate rerun pending. |
| W2 — `quick` by override and scheduled/revert source | PARTIAL | [#417](https://github.com/Smana/ai-native-ref/issues/417) / `mao2ils5` / [#419](https://github.com/Smana/ai-native-ref/pull/419) | Quick ran one implementer, no reviewer, and no scoper/judge/search child. AwaitingHuman/`no_policy_matched`; must become `reviewer_verdict_missing` after rollout. Scheduled/revert source observation pending. |
| W3 — `careful` role chain and judge continuation | PARTIAL | Prepared issue body `w3.md`; not filed | Two attempts failed with `handoff_expired` because only the handoff digest was displayed. Using the real random handoff ID reached clarification and confirmation. Maku #617 fixes the rendered plan text; rerun pending. |
| W4 — label and confirmation selection | PARTIAL | W1–W3 | W1 repository default and W2 maintainer label sources are recorded; W3 confirmation remains. |
| W5 — legacy, unknown, conflicting and non-maintainer pins | PARTIAL | #423/`57bkwslw`/#424; #359/`nhqxxxhw`; #425/`hwmzeu5n` | Legacy labels are narrated as ignored and select `standard` (#423, reviewer-approved, 399k tokens/$0.16 charged to github:smana). `workflow:nope` records `profile_unknown`; conflicting labels record `profile_conflict` and select `standard`. The unknown-label run selected `careful` only because the unintended evaluation overlay was still live, so that fallback was stopped. Non-maintainer actor remains unavailable. |
| W6 — `quick` with a verdict-requiring policy | PASS | #433/`nxtm6cnu`/#435 | Actual website prose ran quick with one implementer and no reviewer. The decision records `considered=docs:reviewer_verdict_missing,docs-links:class_mismatch,revert:class_mismatch`; no autonomous merge occurred. The separate runbook-only #430 correctly records `docs:file_not_allowed`. |
| W7 — `maku repo add` and `repo check` for four repositories | FAIL | [maku#616](https://github.com/Smana/maku/issues/616) | v0.53.1 `repo add` requires public `GET /apps/{slug}` metadata. All three private Apps answer 404; no declarations were generated and no App visibility was changed. |
| W8 — planner catalog discovery on `runlore-kb` | NOT RUN | | Pending corrected chart and #617 deployment. |

## Merge policies

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| M1 — diff selection and `no_policy_matched` | PARTIAL | [#418](https://github.com/Smana/ai-native-ref/issues/418) / `7k4yfmcw` / [#420](https://github.com/Smana/ai-native-ref/pull/420) | Standard implementer/reviewer succeeded. The expected human hand-off is present, but catalog `considered=` evidence awaits the corrected chart. |
| M2 — unbound catalog shadow evidence | NOT RUN | | Pending corrected catalog. |
| M3 — bounds, protected paths, size and `modifyOnly` | NOT RUN | | Pending corrected catalog. |
| M4 — hold and approval precedence | PARTIAL | #436 / `buwtrs4p` | Maintainer approval of `97c7804988aad59e77d4aa4a6728d7a1f439162f` caused `ogenki-agent-merger[bot]` to merge that exact head. Task is Done/merged with `mergedHow=approved` and `decidedHeadSHA` equal to the reviewed head. Hold and stale-head cases remain. |
| M5 — strictest selection, cap/pause and no fall-through | NOT RUN | | Pending corrected catalog. |
| M6 — reviewer verdict requirement | PASS | #433/#435 versus #434/`buwtrs4p`/#436 | Quick records `docs:reviewer_verdict_missing`; standard's reviewer-backed prose records `shadow_would_arm` with policy `docs`, verdict `approve`, and `considered=docs-links:class_mismatch,revert:class_mismatch`. Neither merged autonomously. |
| M7 — UI, CLI and API maintainer journeys | PARTIAL | [ai-native-ref#415](https://github.com/Smana/ai-native-ref/pull/415) | All three authenticated settings routes return 200; unprivileged approval-memory API returns 401. Maku v0.53.1 export/diff/check/simulate proves `docs: tightening`, reports intentional non-equivalence, and all applicable conformance fixtures agree. UI write and authorization journeys remain. |
| M8 — live merge, revert, breaker and recovery | BLOCKED | `/api/policy/repositories/Smana/ai-native-ref` evidence | `docs-links` has 4/5 clean decisions, one bad outcome, and no drill. The API reports `below_minimum`, `bad_outcome`, `no_drill`. No threshold or policy was changed. |

## Screencasts

| ID | Result | Source issue / PR | Export and publication links |
|---|---|---|---|
| S1 — 20–30 second handoff-to-PR cut | NOT RUN | [#394](https://github.com/Smana/ai-native-ref/issues/394) | Browser-based 1920×1080 WebM recording is proven with Playwright and system Chromium. Real task capture follows green workflow/approval paths. |
| S2 — approximately one-minute end-to-end cut | NOT RUN | #394 | Same footage will supply the longer cut; no exported deliverable yet. |

## Failures, fixes and reruns

| Test ID | Failure evidence | Fix PR | Rerun result |
|---|---|---|---|
| Bootstrap | The task timeout interrupted EKS creation before state recorded it; a stale lock and 409 followed. | Operational recovery only | Released the known stale lock, imported the existing ACTIVE cluster, restored the generated module file, and completed deployment plus OpenBao OIDC verification. |
| Foundation | Broker migrate recorded through `20261120120000`; Atlas then completed `20261121120000`, triggering the two-ledger refusal. | [ai-native-ref#413](https://github.com/Smana/ai-native-ref/pull/413), merged | Verified Atlas 9/9 and the shipped hash, recorded the applied migration, and both broker and factory became Ready. |
| B3 | aws-0 shipped `evaluation: {controlPercent: 70, treatment: careful}` despite the campaign forbidding it. | [ai-native-ref#414](https://github.com/Smana/ai-native-ref/pull/414), merged | Live overlay removed repeatedly; corrected rollout pending. |
| B2 | Merger App initially lacked `statuses:write`; Agents lacked `issues:write`; the GitHub-link OAuth client and Slack URLs were absent. | Owner console, completed | Permissions approved; login/link succeeded; Slack endpoint and `maku doctor` checks are healthy. |
| M7 | `/settings/approval-memory` returned 404 because `human.approvalMemory` was unset. | [ai-native-ref#415](https://github.com/Smana/ai-native-ref/pull/415), merged | Direct page 200; unprivileged API 401. Full check: 67 passed, 4 skipped. |
| W3 | OpenCode received `handoff_expired` because the rendered plan displayed the digest instead of the random ID. | [maku#617](https://github.com/Smana/maku/pull/617), merged | Full check passed; real-ID clarification path proven, full rerun pending deployment. |
| B3 / W6 | Standalone `maku-factory` omitted the umbrella's controller and catalog. The umbrella schema then rejected top-level `config`. | [maku#618](https://github.com/Smana/maku/pull/618), merged; [ai-native-ref#422](https://github.com/Smana/ai-native-ref/pull/422) | Maku full check and all PR checks green. Corrected ai-native-ref manifests render, 13 config objects accept per cloud, and all 71 suites passed before the final site-pin adjustment. |
| #422 | Empty sponsored `maku-factory:` erased the base subchart map; sponsored principals were siblings of `api`; config validation assumed a released CLI. | ai-native-ref #422, merged | Empty keys removed, principals nested without changing budgets/identities, prerelease CLI built from its source commit. Full gate passed: 71 suites. |
| Rollout | The catalog was incorrectly nested under the subchart; the factory config was incorrectly placed at umbrella level, causing `503` and Helm rollback. | ai-native-ref #428/#429, host #2866/#2867, Maku #619 | #428 moved only the catalog to umbrella scope. #429 nests base and sponsored config under `maku-factory`, updates every offline reader, and passed 70 suites/1 expected skip. Maku #619 rejects the unused top-level config. Final rollout pending #429's artifact. |
| W7 | Private factory, agents and merger Apps all return 404 from the public app endpoint. | [maku#616](https://github.com/Smana/maku/issues/616) | Recorded without changing App visibility. |

## Out of scope and residual gaps

- The workflow value experiment and runbook 27's 40-task comparison.
- GCP, the laptop quickstart, generic-cluster installation and a release tag.
- Historical runbooks unrelated to the shipped workflow and merge-policy changes.

| Gap | Reason | Follow-up |
|---|---|---|
| Second-person and unlinked Slack actors | The owner and second accounts are unavailable. | Run L10, L11, L15, L16 and W5-untrusted with the real actors. |
| Credential exposure during operations | A Kubernetes Secret inspection accidentally printed restored credentials into the operator transcript. | Rotate the exposed provider API keys and factory/agents/merger private keys; do not reuse the transcript values. |
| M8 evidence | `docs-links` has 4/5 clean decisions, one bad outcome and no drill. | Keep blocked unless the ledger and evidence view meet the shipped low-evidence gate. |
| Outbound GitHub connectivity | Requests alternate between HTTP 200 and `no route to host`; Terramate requires `origin/main`. | Restore stable networking, then deploy host #2869 and run M2, hold/stale-approval, W3/W8 and the recordings. |

## Cleanup

| Check | Result | Evidence |
|---|---|---|
| Temporary switches and test-specific limits removed | PARTIAL | Evaluation is removed and the M2 `docs` binding was restored through Flux after every intake failure. Temporary `profile:careful` and `workflow:nope` labels still need deletion when GitHub is stable. |
| No active test tasks or unintended open test PRs | PARTIAL | #436 merged through the normal approved path. #435's new local revision was not pushed. Other test PRs remain open for maintainer review or cleanup; no autonomous unsafe merge was forced. |
| Final baseline healthy | PASS | Factory is 2/2 Ready with all four policy objects. Strict preflight: 15 pass, 3 skip, 0 fail. |
| aws-0 retained for verification; no automatic teardown | PASS | aws-0 remains running. No GCP deployment or release tag occurred. |
