# Maku v0.54.x live checks on gcp-0 — 2026-11-25

The results of [runbook 29](29-maku-v054-live-checks.md) on gcp-0, run from 2026-11-25 to
2026-11-26. The factory started on Maku v0.54.0 (ANR v4.1.0) and moved through v0.54.1 (ANR
v4.1.1), v0.54.3 (v4.1.2), v0.54.4 (v4.1.3) and v0.54.5 (v4.1.4) as the fixes below shipped;
v0.54.2 was tagged but not deployed. A check that failed and passed on a later release names the
fix. `NOT RUN` says why. `Date` is when the result was observed.

Results over the runbook's 31 checks: **PASS** 7, **PARTIAL** 5, **FAIL** 4, **NOT RUN** 15. The
merge-policy safety drills in [section 6b](#6b-merge-policy-safety-drills) add 4 PASS and one
NOT RUN row.

## 0. Baseline

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| `Factory` is `Accepted` and `Ready` with no deprecation warning (no `templates`) | | NOT RUN | | `Ready` was read on the v4.0.0 / Maku v0.53.11 baseline only; no condition reading is recorded after the v0.54.0 adoption ([#496]). |
| Every `Repository` is `Ready` with `BindingsValid` true | | NOT RUN | | Not recorded. The `Repository` status read for safety item 8 shows cloud-native-ref serving `merge.autoRevert: true` with no `revert` binding. |
| The brief ConfigMap holds `security-reviewer.md` | | NOT RUN | | Not read directly; the `security-reviewer` stage did run (section 4). |
| Factory, broker and run-controller image digests recorded | | NOT RUN | | Run pods ran by digest under gVisor with no `shareProcessNamespace`; the three control-plane digests are not recorded. The broker's `/.well-known/maku` reported v0.54.5 at the end. |

## 1. Step up once

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Automatic: unlabelled impossible-edit issue steps up to `careful` | [#499], [#508] | FAIL | 2026-11-26 | #499 ended NoOp: its text told the agent to do nothing, so the drill needs new wording. #508 escalated `stuck` (not a step-up trigger), then `budget-task` with no step-up and no **deeper** offer. Fix [maku#718] (v0.54.4); not re-run after it. |
| Pinned: `workflow:standard` on the same text gives an offer; `/factory retry deeper` steps it | [#497] | PARTIAL | 2026-11-25 | Stepped with `maku retry --deeper`: `careful`, `stepUp` `mode: manual`, ceiling held at the confirmed $5.10. The escalation was `no_verdict` from the MCP rate limit ([maku#708]), not a stall, and the offer text is not recorded. The card's step-up figure showed the base ceiling ([maku#720]). |
| Slack: the same request over Slack (`maxCostUSD: 2`) never steps; **Run again deeper** refused `deeper_over_cap` | | NOT RUN | | Needs the owner in Slack. Over the confirmed cap the factory offers and does not run ([maku#720]). |
| Host: one issue on `Smana/cloud-native-ref` gets the host's `stepUp: ask` offer | [cnref#2912] | NOT RUN | | The host issue ran for the required-plan check; it ended out of run budget with no step-up offer reading recorded. |

## 2. Outcomes and the plan gate

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| `plan-first`: plan comment, `factory/plan-proposed`, **Approve** and **Revise** | [#512] | PASS | 2026-11-26 | Parked waiting on a maintainer with the scoper done. **Revise** first failed: the `Task` CRD enums (`status.nextTrigger`, `status.runs[].trigger`) lacked `plan_revise`, so every status update was refused. Passed on a live CRD patch: revised plan, three clicks deduped; fix [maku#711]. **Approve** moved it to Implementing. Revise and Approve on the same issue, not a second one. The plan comment leaves a code fence open when an acceptance item holds one, swallowing the `/factory plan` answer block (no fix yet). |
| `review`: a person's pull request labelled `factory/review` gets one verdict, no push, no merge | [#515] | PASS | 2026-11-26 | First escalated `loop_unsupported`: the `AgentRun` branch pattern `^agent/` refused the PR head. Fix [maku#725] (v0.54.4); the retry ended `review_posted`, verdict approve. The gate's status on the PR is not recorded. |
| `report`: a "why" issue gets findings on the issue, no branch; `/factory fix` files a `change` task | [#503] | PARTIAL | 2026-11-25 | The first run posted nothing (MCP rate limit, [maku#708]); the rerun on v0.54.1 ended `findings_posted`. `/factory fix` was not tried. |
| Required plan: an unlabelled change under `observability/` on the host scopes before implementing | [cnref#2912] | FAIL | 2026-11-26 | Ran `standard` with no scoper: `requires: [plan]` did not apply. No fix or issue is filed. |

## 3. The room's acts and whole plans

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Answer | | NOT RUN | | No room **Answer** is recorded. A false `needs_author` (an `Acceptance:` line followed by a list) was answered on GitHub; fix [maku#714]. |
| Retry | | NOT RUN | | Retries went through `maku retry` and `/factory retry`, not the room page. |
| Run again deeper | | NOT RUN | | Done from the CLI only ([#497], section 1). |
| Accept the split | | NOT RUN | | No task proposed a split. |
| Approve a plan | [#512] | PASS | 2026-11-26 | The task moved to Implementing, but the click gave no visible acknowledgement; fix [maku#713] (v0.54.3). |
| Revise a plan | [#512] | PASS | 2026-11-26 | After the CRD patch ([maku#711]); three clicks deduped into one revision. No acknowledgement either; fix [maku#713]. |
| Split a plan | | NOT RUN | | Not tried. |
| Stop | | NOT RUN | | Not recorded from the room page. |
| New task (`file`) | [#512], [#529] | PASS | 2026-11-26 | On v0.54.1, the web form filed #512 as the factory App, which refused its own `factory/ready` (`unauthorised_labeller`) and ignored its `workflow:careful`. Fix [maku#722] (v0.54.4): #529 was filed and started, `requestedBy github:Smana`. |
| A request wide enough for three issues: `start` files all three in order | [#519] | FAIL | 2026-11-25 | The terminal `maku start` files only the first issue of a whole plan (`internal/maku/client.go`); #519 is 1 of 3. The MCP `start` tool files all of them. No fix filed. |

## 4. The custom workflow

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| One issue labelled `workflow:thorough`: rail, `AgentRun` persona and gate verdict | [#501] | PARTIAL | 2026-11-25 | Stages ran implement, then `security-reviewer`, then review. The persona label, the read-only token and the gate's verdict source are not recorded. The settings page's Workflows row lists `thorough` as implementer and reviewer only. |

## 5. OpenCode, one task

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| One small issue labelled `harness:opencode`: profile, image and admission | [#502], [#505] | PASS | 2026-11-25 | `harness: opencode`, `harnessSource: labeled`; `maku-opencode` by digest, admitted under gVisor; PR #505 was a correct three-line change. Fixes made OpenCode runs work end to end: [maku#712] (server started outside the clone, v0.54.2), [maku#727] (no task sent on a pushed branch) and [maku#728] (image venv), both v0.54.5. |
| If it escalates: `/factory retry harness=openhands` moves it back (`cohort: rescue`) | [#502] | PASS | 2026-11-25 | Cohort `rescue` on OpenHands; ended AwaitingHuman, `shadow_would_arm`. |
| The 50/50 trial report once each arm has 30 ended tasks | | NOT RUN | | Neither arm reached 30 ended tasks. Tasks before [maku#727] and [maku#728] are to be discarded. |

## 6. Merge policies

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Reverts merge themselves: `factory/revert` on a merged `docs-links` pull request | | NOT RUN | | Not tried; `merge.autoRevert` is served on the host. |
| Pause and resume: `maku policy pause` and `maku policy resume` | [#506] | FAIL | 2026-11-25 | Without `--config`, pause only prints the edit. With it, it opened #506, which rewrote the whole manifest (comments gone, zero values injected) while saying only `spec.merge.paused` changes. Closed unmerged; fix [maku#709] (v0.54.2), not re-run. Resume not tried. |
| Promotion: **Promote to live** for `dead-links` after five clean decisions and a passed drill | | NOT RUN | | Not reached. The evidence reader refused cloud-native-ref past 500 records; fix [maku#717]. Backtest answered 503 until [maku#710]. |
| The reasons: `maku policy list` and `maku policy explain` on one decision of each repository | | PARTIAL | 2026-11-25 | Both commands worked and the timeline was readable; which repositories were read is not recorded. |

### 6b. Merge-policy safety drills

Agent pull requests on `Smana/ai-native-ref`, with `docs-links` in shadow; each was closed unmerged.

| Drill | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Links-only refuses a non-Markdown file | [#522] | PASS | 2026-11-26 | `human:no_policy_matched` on an `icons/manifest.json` change. |
| Links-only arms on a genuine relative retarget | [#521] | PASS | 2026-11-26 | `docs-links · shadow:shadow_would_arm`. |
| The host rule refuses a GitHub owner change | [#520] | PASS | 2026-11-25 | `human:no_policy_matched`, considered `docs:file_not_allowed`, `docs-links:class_mismatch`. |
| Links-only refuses an archive URL of another target | [#524] | PASS | 2026-11-26 | `human:no_policy_matched`. |
| Archive URL of the same target; footnote; submodule, symlink, empty or byte-equal diff; hold authority; decision race; two live policies; refused edits; evidence from maintainer merges only | | NOT RUN | | No docs-only agent diff produces them, they need a live arm or a second live policy, or they need config edits. |

## 7. Close

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Scratch and promotion pull requests closed, scratch labels removed, paused repository resumed, every failure recorded | | PARTIAL | 2026-11-26 | Drill PRs #510, #511, #520–#522 and #524 closed unmerged; real fixes #498, #505 and #513 merged on review. No repository was paused (#506 never merged). Scratch labels are not recorded as removed. Every failure is above. |

[#496]: https://github.com/Smana/ai-native-ref/pull/496
[#497]: https://github.com/Smana/ai-native-ref/issues/497
[#499]: https://github.com/Smana/ai-native-ref/issues/499
[#501]: https://github.com/Smana/ai-native-ref/issues/501
[#502]: https://github.com/Smana/ai-native-ref/issues/502
[#503]: https://github.com/Smana/ai-native-ref/issues/503
[#505]: https://github.com/Smana/ai-native-ref/pull/505
[#506]: https://github.com/Smana/ai-native-ref/pull/506
[#508]: https://github.com/Smana/ai-native-ref/issues/508
[#512]: https://github.com/Smana/ai-native-ref/issues/512
[#515]: https://github.com/Smana/ai-native-ref/pull/515
[#519]: https://github.com/Smana/ai-native-ref/issues/519
[#520]: https://github.com/Smana/ai-native-ref/pull/520
[#521]: https://github.com/Smana/ai-native-ref/pull/521
[#522]: https://github.com/Smana/ai-native-ref/pull/522
[#524]: https://github.com/Smana/ai-native-ref/pull/524
[#529]: https://github.com/Smana/ai-native-ref/issues/529
[cnref#2912]: https://github.com/Smana/cloud-native-ref/issues/2912
[maku#708]: https://github.com/Smana/maku/pull/708
[maku#709]: https://github.com/Smana/maku/pull/709
[maku#710]: https://github.com/Smana/maku/pull/710
[maku#711]: https://github.com/Smana/maku/pull/711
[maku#712]: https://github.com/Smana/maku/pull/712
[maku#713]: https://github.com/Smana/maku/pull/713
[maku#714]: https://github.com/Smana/maku/pull/714
[maku#717]: https://github.com/Smana/maku/pull/717
[maku#718]: https://github.com/Smana/maku/pull/718
[maku#720]: https://github.com/Smana/maku/pull/720
[maku#722]: https://github.com/Smana/maku/pull/722
[maku#725]: https://github.com/Smana/maku/pull/725
[maku#727]: https://github.com/Smana/maku/pull/727
[maku#728]: https://github.com/Smana/maku/pull/728
