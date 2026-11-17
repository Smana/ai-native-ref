# AWS v4 feature validation and screencasts — 2026-11-16

**Status:** core validation is complete; the trial screencasts were rejected and deleted, and focused residual cases are listed below. aws-0 is healthy and retained. **Procedure:**
[runbook 28](28-v4-aws-validation.md). **Design:**
[the approved campaign](../../superpowers/specs/2026-11-16-v4-aws-validation-design.md).

## Baseline

| Item | Value |
|---|---|
| Initial ai-native-ref SHA | `1d1a14aa9d4b10e67cfefbf5630ebe6d853371d0` (`origin/main`) |
| Initial artifact tag and digest | Signed PR artifact `v3.27.1-pr412.gc50d1017`, source `c50d101734e13d850ef27c9235df18f6e2d2a7d6`, digest `sha256:79d80a7270afbe3d407ebcc614f0d95f199d5a9a865c4e5de0fdfa86b0d116ff`; no release tag created |
| Final ai-native-ref artifact | Digest `sha256:dfea1ab19cce1769e29bc9ebcd8e5d8f7b13674c2898a1bfe6e92b36344b4548`, reconciled from `main` through #432 |
| cloud-native-ref SHA | Bootstrap `b7395ca66bbc9a32be8ce5bc5fe216a57e55e33e`; v4 pin PR [#2863](https://github.com/Smana/cloud-native-ref/pull/2863), merged as `e7bf01f0b761fce08a3c94874f62827b078fa2b8` |
| Initial Maku version | `v0.53.1`, source `417ddd5409152a0dc3f9574a872d4ead9dc33860`; local CLI `maku-linux-amd64` checksum verified |
| Factory and broker corrections | Maku #617, #618 and #619 merged. Deployed chart `0.53.2-pr618.g9d0bdb48+312dd4d13e15`; factory image digest `sha256:8cd74cd52b0b55d23e682420e92674ce4351cb0961dfd3f2b38cdf385eb84319`; broker digest `sha256:f388790e9173fb3e67f0e06813785e2691b524eedc7db3233eca5c5b17746ee2` |
| Harness and bridge image digests | Harness `sha256:104c1749567ccff3864aeab7856bf1d9c2b4f7bd0398d522f6f59b69b36813cf`; bridge `sha256:3648b20957f64a6c0a18f7dedd8bc8e8b8a73ffd1981ea042e8c5aa4b8f456ea` |
| aws-0 Kubernetes and agentgateway versions | EKS API `1.36`, nodes `v1.36.5-eks-577a51e`; agentgateway chart and image `v1.6.0` |
| Campaign start / end | Started 2026-11-17 08:24 Europe/Paris; core validation, publication and cleanup completed 2026-11-17 |
| Validation gates | Host #2863 local `task check`: 3,409 resources valid, 85 passed, 1 skipped, 0 failed. Maku #617/#618 full checks passed; all merged fix PR checks were green. |

## Foundation and adjacent regression

| ID | Result | Evidence |
|---|---|---|
| B1 — fixed source and released pins | PASS | Cosign verified the initial artifact against `ci.yaml@refs/pull/412/merge`. Subsequent fixes use signed PR artifacts recorded above; no GCP deployment or release tag. |
| B2 — Flux, Helm, pod health and strict preflight | PASS | Final Flux and Helm reconciliation is Ready. Factory and broker are 2/2 Ready. Final strict preflight has 15 pass, 3 expected skip and 0 fail. GitHub login/link, required App permissions and Slack URLs were verified. Raw final output: `preflight-final.json` in the campaign evidence directory. |
| B3 — Factory, Repository and MergePolicy readiness | PASS | Factory and all four Repositories are Accepted and Connected; all four MergePolicy objects exist and are accepted. `spec.evaluation` is empty. |
| B4 — identity, short-lived tokens, gVisor and egress | PASS | Run `z7cl6h2k` used gVisor, its own ServiceAccount token and seccomp `0`, per-run default-deny, and proxied GitHub. Direct GitHub/API/example egress was denied. Raw claim: `run-z7cl6h2k-agentrun.yaml` in the campaign evidence directory. |
| B5 — settings live edit, refused edit and Git restore | PASS | An invalid workflow was refused while the previous configuration remained available; Flux restored `standard`. |
| B6 — OpenCode and Slack L1–L17 proofs | PARTIAL | `maku setup opencode` and `maku doctor` pass. MCP exposes exactly `handoff`, `start`, `inbox`, `task`, `wait`, `answer`; removed `intake_plan` returns `unknown tool`. Second-person/unlinked Slack actors remain unavailable. |
| B7 — repository checks, observability and alerts | PASS | #436's PR checks completed before the gate. `agent-factory`, `agent-platform`, `agent-platform-logs` and `agent-rooms` VMRules are loaded; the ALERTS query returned no firing campaign alerts. |
| B8 — role and charged-identity cost | PASS | #436's Task and terminal card agree at 1,523,896 tokens / $0.540329, charged to github:smana. VictoriaMetrics shows implementer $0.446182 and reviewer $0.094147 with matching run IDs and model glm-5.3. The recording task #441 independently settled at 621,074 tokens / $0.253427. |
| B9 — RunLore `kb_search` from a triager | FAIL | RunLore principals, both webhook keys, fences and required rulesets are restored, and strict preflight confirms `kb_search` and `kb_get`. Correct RunLore/investigate Task `bkbsea23` started triager `kffdqnks`, but its first model call failed `401 invalid x-api-key` through `agent-default`; no `kb_search` call occurred and the metric stayed at zero. Public implementer runs succeeded, isolating the failure to the internal model credential or route. Raw evidence: `b9-triager-agent.log` and `b9-metric-before.json`. A valid internal provider credential is required before rerun. |

## Workflows

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| W1 — repository default selects `standard` | PASS | [#416](https://github.com/Smana/ai-native-ref/issues/416) / `2kglebvy` / [#421](https://github.com/Smana/ai-native-ref/pull/421) | Repository default selected standard; implementer and reviewer succeeded, with standard-tier checks and the expected human hand-off. |
| W2 — `quick` by override and scheduled/revert source | PARTIAL | [#417](https://github.com/Smana/ai-native-ref/issues/417) / `mao2ils5` / [#419](https://github.com/Smana/ai-native-ref/pull/419) | Quick ran one implementer, no reviewer, and no scoper/judge/search child. Separate actual scheduled and revert-source observations remain. |
| W3 — `careful` role chain and judge continuation | PASS | #438/`p2d5d3pn`/#439 | Documented fallback selected careful: triager, implementer, integrated `Judge met` at 17:01 UTC, then reviewer approve. There is no separate judge AgentRun. `factory/hold` returned `held`; removal returned `reentered_unheld`. |
| W4 — label and confirmation selection | PARTIAL | W1–W3 | W1 repository default and W2 maintainer label sources are recorded; W3 used a documented fallback, so the confirmation-source comparison remains. |
| W5 — legacy, unknown, conflicting and non-maintainer pins | PARTIAL | #423/`57bkwslw`/#424; #359/`nhqxxxhw`; #425/`hwmzeu5n` | Legacy labels are narrated as ignored and select `standard`. `workflow:nope` records `profile_unknown`; conflicting labels record `profile_conflict` and select `standard`. An early unknown-label run was invalidated by the then-live evaluation overlay and stopped. Non-maintainer actor remains unavailable. |
| W6 — `quick` with a verdict-requiring policy | PASS | #433/`nxtm6cnu`/#435 | Actual website prose ran quick with one implementer and no reviewer. The decision records `considered=docs:reviewer_verdict_missing,docs-links:class_mismatch,revert:class_mismatch`; no autonomous merge occurred. The runbook-only #430 correctly records `docs:file_not_allowed`. |
| W7 — `maku repo add` and `repo check` for four repositories | FAIL | [maku#616](https://github.com/Smana/maku/issues/616) | v0.53.1 `repo add` requires public `GET /apps/{slug}` metadata. All three private Apps answer 404; no declarations were generated and no App visibility was changed. |
| W8 — planner catalog discovery on `runlore-kb` | PARTIAL | OpenCode handoff `wirqahhpa2inaj3m2ssmx6u5x4` | The planner selected `Smana/runlore-kb` and `standard` from the factory catalog without a broker-side repository list. The vague command-replacement draft was not filed because no such stale command exists; this is catalog proof only. |

## Merge policies

| ID | Result | Issue / task / PR | Evidence |
|---|---|---|---|
| M1 — diff selection and `no_policy_matched` | PARTIAL | [#418](https://github.com/Smana/ai-native-ref/issues/418) / `7k4yfmcw` / [#420](https://github.com/Smana/ai-native-ref/pull/420) | Standard implementer/reviewer succeeded and human hand-off is present. Detailed catalog `considered=` evidence for every refusal remains. |
| M2 — unbound catalog shadow evidence | PASS | #440/`kae57zin`/#442 | With the Repository's `docs` binding removed, the chart catalog still evaluates `docs` and records `shadow_would_arm` with reviewer approve. The binding was restored through Flux. The first, broader issue #437 exhausted its run budget before a PR and was not counted. |
| M3 — bounds, protected paths, size and `modifyOnly` | PASS | `m3path46`/#450; `m3size45`/#449; `m3shape5`/#447 | Agents-App-authored fixtures with green CI returned `dead-links:file_protected`, `docs:patch_too_large` plus the links/revert size refusals, and `docs-links:file_added_or_deleted` plus the revert refusal. All three ended at `AwaitingHuman` or `no_policy_matched`; none merged and all were closed. An earlier custom schedule without findings did not arm dead-links and was not counted. |
| M4 — hold and approval precedence | PASS | #436; #439; #442 | Approved head merges as `approved`. `factory/hold` blocks #439 and removal re-enters as `reentered_unheld`. On #442, old-head approval was followed by new head `610eae5a30479a32145da681081558be3da6bad8`; it stayed unmerged and the PR was closed during cleanup. An earlier attempt on already-merged #435 was invalid and is not counted. |
| M5 — strictest selection, cap/pause and no fall-through | NOT RUN | | Overlapping-policy and cap/pause observations were not exercised; M8's evidence gate remains blocked. |
| M6 — reviewer verdict requirement | PASS | #433/#435 versus #434/`buwtrs4p`/#436 | Quick records `docs:reviewer_verdict_missing`; standard's reviewer-backed prose records `shadow_would_arm` with policy `docs`, verdict `approve`, and `considered=docs-links:class_mismatch,revert:class_mismatch`. Neither merged autonomously. |
| M7 — UI, CLI and API maintainer journeys | PARTIAL | [ai-native-ref#415](https://github.com/Smana/ai-native-ref/pull/415); `editor-valid.json` in the campaign evidence directory | All three authenticated settings routes return 200; unprivileged approval-memory API returns 401. The guided editor accepted `docs.maxModifiedLines: 50`, classified `docs: shadow, tightening`, and produced a downloadable Repository manifest without saving or opening a PR. The UI exposes no YAML-editing mode or GitHub edit link. Maku v0.53.1 export/diff/check/simulate agrees with all applicable conformance fixtures. Linked non-maintainer authorization journeys remain. |
| M8 — live merge, revert, breaker and recovery | BLOCKED | `/api/policy/repositories/Smana/ai-native-ref` evidence | `docs-links` has 4/5 clean decisions, one bad outcome, and no drill. The API reports `below_minimum`, `bad_outcome`, `no_drill`. No threshold or policy was changed and no evidence was manufactured. |

## Screencasts

| ID | Result | Source issue / PR | Outcome |
|---|---|---|---|
| S1 — 20–30 second handoff-to-PR cut | REJECTED | [#441](https://github.com/Smana/ai-native-ref/issues/441) / `e2dgpqn3` / [#443](https://github.com/Smana/ai-native-ref/pull/443) | The owner rejected the export's quality. The local WebM files and issue #394 media comment were deleted; no deliverable remains. |
| S2 — approximately one-minute end-to-end cut | REJECTED | #441 / `e2dgpqn3` / #443 | Rejected and deleted with S1. The owner will record replacements. |

The source PR merged through `ogenki-agent-merger[bot]` with `mergedHow=approved`. Its final Task cost is 621,074 tokens / $0.253427, charged to github:smana; implementer `iefrjoyj` cost $0.171757 and reviewer `zpcsz376` cost $0.081670. The rejected exports used the settled terminal card and a VictoriaMetrics per-role rendering, not the Grafana dashboard. README, homepage and issue-media links were removed. Deleting the temporary public media repository is blocked by the CLI token's missing `delete_repo` OAuth scope.

## Failures, fixes and reruns

| Test ID | Failure evidence | Fix PR | Rerun result |
|---|---|---|---|
| Bootstrap | The task timeout interrupted EKS creation before state recorded it; a stale lock and 409 followed. | Operational recovery only | Released the known stale lock, imported the existing ACTIVE cluster, restored the generated module file, and completed deployment plus OpenBao OIDC verification. |
| Foundation | Broker migrate recorded through `20261120120000`; Atlas then completed `20261121120000`, triggering the two-ledger refusal. | [ai-native-ref#413](https://github.com/Smana/ai-native-ref/pull/413), merged | Verified Atlas 9/9 and the shipped hash, recorded the applied migration, and both broker and factory became Ready. |
| B3 | aws-0 shipped `evaluation: {controlPercent: 70, treatment: careful}` despite the campaign forbidding it. | [ai-native-ref#414](https://github.com/Smana/ai-native-ref/pull/414), merged | Live overlay is empty and remains absent after Flux reconciliation. |
| B2 | Merger App initially lacked `statuses:write`; Agents lacked `issues:write`; the GitHub-link OAuth client and Slack URLs were absent. | Owner console, completed | Permissions approved; login/link succeeded; Slack endpoint and `maku doctor` checks are healthy. |
| M7 | `/settings/approval-memory` returned 404 because `human.approvalMemory` was unset. | [ai-native-ref#415](https://github.com/Smana/ai-native-ref/pull/415), merged | Direct page 200; unprivileged API 401. Full check: 67 passed, 4 skipped. |
| W3 | OpenCode received `handoff_expired` because the rendered plan displayed the digest instead of the random ID. | [maku#617](https://github.com/Smana/maku/pull/617), merged; [ai-native-ref#432](https://github.com/Smana/ai-native-ref/pull/432) | Full check passed and the corrected broker is deployed. Real-ID clarification and complete recording task #441 passed. |
| B3 / W6 | Standalone `maku-factory` omitted the umbrella's controller and catalog. The umbrella schema then rejected top-level `config`. | [maku#618](https://github.com/Smana/maku/pull/618) and #619, merged; [ai-native-ref#422](https://github.com/Smana/ai-native-ref/pull/422) | Controller and catalog are live. Final layout uses `maku-factory.config` and umbrella-level `mergePolicies.catalog`, with `exclude: [deps-patch]`. |
| #422 | Empty sponsored `maku-factory:` erased the base subchart map; sponsored principals were siblings of `api`; config validation assumed a released CLI. | ai-native-ref #422, merged | Empty keys removed, principals nested without changing budgets/identities, prerelease CLI built from its source commit. Full gate passed: 71 suites. |
| Rollout | The catalog was incorrectly nested under the subchart; factory config was incorrectly placed at umbrella level, causing `503` and Helm rollback. | ai-native-ref #428/#429/#432; host #2866/#2867/#2868/#2869; Maku #619 | Corrected artifacts reconciled from `main`; catalog shadow decisions, W2/W3/W6, M2/M4/M6 and recording paths passed afterward. |
| Final Helm health | The initial failed install had no successful rollback target, leaving the HelmRelease stalled despite healthy pods. | Operational recovery only | `flux reconcile helmrelease agent-factory --force --reset` completed release v3. HelmRelease and Kustomization are Ready; final strict preflight is 15 pass / 3 skip / 0 fail. |
| W7 | Private factory, agents and merger Apps all return 404 from the public app endpoint. | [maku#616](https://github.com/Smana/maku/issues/616) | Recorded without changing App visibility. |
| B9 | The correct internal triager's first model call failed `401 invalid x-api-key`; strict preflight's run-alias probe is only a skip. | Valid internal provider credential required | No `kb_search` call occurred. Replace or rotate the internal credential, then rerun `bkbsea23`'s read-only search and room/metric assertions. |

## Out of scope and residual gaps

- The workflow value experiment and runbook 27's 40-task comparison.
- GCP, the laptop quickstart, generic-cluster installation and a release tag.
- Historical runbooks unrelated to the shipped workflow and merge-policy changes.

| Gap | Reason | Follow-up |
|---|---|---|
| Second-person and unlinked Slack actors | The owner and second accounts are unavailable. | Run L10, L11, L15, L16 and W5-untrusted with the real actors. |
| Focused matrix cases | M1 detailed `considered=`, M5, M7 YAML/authorization, W2 scheduled/revert sources and W4 confirmation source were not completed. M3 passed all three boundary cases. | Execute the focused cases without weakening their fixtures or evidence requirements. |
| B9 internal model credential | Triager `kffdqnks` received `401 invalid x-api-key` before it could call `kb_search`. | Replace or rotate the internal provider credential, then rerun B9's triager, room-event and metric assertions. |
| M8 evidence | `docs-links` has 4/5 clean decisions, one bad outcome and no drill. | Keep blocked unless the ledger and evidence view meet the shipped low-evidence gate. |
| Screencasts and temporary media repository | The owner rejected the trial exports and will record replacements. Local WebM files and links are deleted; GitHub refuses repository deletion without the CLI token's `delete_repo` scope. | Record replacements manually. Authorize `delete_repo`, then delete `Smana/ai-native-ref-screencasts`; no current video is claimed. |
| Credential exposure during operations | A Kubernetes Secret inspection accidentally printed restored credentials into the operator transcript. | Rotate the exposed provider API keys and factory/agents/merger private keys; do not reuse the transcript values. |

## Cleanup

| Check | Result | Evidence |
|---|---|---|
| Temporary switches and test-specific limits removed | PASS | Evaluation is empty; the M2 `docs` binding was restored through Flux; temporary `profile:careful` and `workflow:nope` labels were deleted. |
| No active test tasks or unsafe open fixture | PASS | No AgentRun is active; all are terminal. Campaign Tasks are Done, Closed, Stopped, Escalated or AwaitingHuman. Every synthetic M3 PR and #442's stale-test head was closed unmerged; no unsafe fixture was merged. Other genuine documentation PRs remain for normal maintainer review. |
| Final baseline healthy | PASS | Factory and broker are 2/2 Ready, the factory HelmRelease and Kustomization are Ready, all four policy objects remain, and strict preflight is 15 pass / 3 skip / 0 fail. |
| aws-0 retained for verification; no automatic teardown | PASS | aws-0 remains running. No GCP deployment or release tag occurred. |
