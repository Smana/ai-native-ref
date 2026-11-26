# Maku v0.54.x live checks on gcp-0 — 2026-11-25

The results of [runbook 29](29-maku-v054-live-checks.md) on gcp-0, run from 2026-11-25 to
2026-11-26. The factory started on Maku v0.54.0 (ANR v4.1.0) and moved through v0.54.1 (ANR
v4.1.1), v0.54.3 (v4.1.2), v0.54.4 (v4.1.3) and v0.54.5 (v4.1.4) as the fixes below shipped;
v0.54.2 was tagged but not deployed. A check that failed and passed on a later release names the
fix. `NOT RUN` says why. `Date` is when the result was observed.

Results over the runbook's 31 checks: **PASS** 15, **PARTIAL** 5, **FAIL** 6, **NOT RUN** 5. The
merge-policy safety drills in [section 6b](#6b-merge-policy-safety-drills) add 4 PASS and one
NOT RUN row; the hardening checks in [section 6c](#6c-hardening-negatives-and-gate-paths) add 4
PASS and two NOT RUN rows. The room acts in section 3 were driven on 2026-11-26 from a headless
browser whose room connection carried the owner's token; screenshots are named `acts-*`.

## 0. Baseline

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| `Factory` is `Accepted` and `Ready` with no deprecation warning (no `templates`) | | PASS | 2026-11-26 | `gcp-0`: `Accepted=True`, `Ready=True`, no `templates`, no `Deprecated` event; read on Maku v0.54.5. |
| Every `Repository` is `Ready` with `BindingsValid` true | | PASS | 2026-11-26 | ai-native-ref, cloud-native-ref, runlore, runlore-kb: `Ready=True`, `BindingsValid=True`. |
| The brief ConfigMap holds `security-reviewer.md` | | PASS | 2026-11-26 | `agent-factory-role-briefs` holds `security-reviewer.md`. |
| Factory, broker and run-controller image digests recorded | | PASS | 2026-11-26 | v0.54.5: factory `sha256:5d37c521…`, broker `sha256:39f649a8…`, run-controller `sha256:06fb56be…`. |

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
| Answer | [#538] | FAIL | 2026-11-26 | An issue with no acceptance asked at intake (`needs_author`, task `4i3csk3w`) but has no room: the factory status reads `Room: none`, `maku needs` does not list it, and `maku answer 4i3csk3w` and `maku cancel 4i3csk3w` answer `404: no such room`. The room page's **Answer** card cannot appear for a question asked before any run; only the GitHub edit and re-label answer it. No fix yet. |
| Retry | [#519] | FAIL | 2026-11-26 | Web **Retry** on room `4za2no42` (escalated `budget-task`): the act reached the broker as the owner and the card said "Retry requested — a new run starts next" (ack `retried`), but the factory refused it on the issue only ("the task's cap is part of its spec: raise it on a new task"). The room never shows the refusal; on reload it offers **Retry** again, and `status.nextTrigger` stays `retry`. The room also reads "budget reached" at 1.9 M of 3 M tokens and $0.70 of $5.10, and its card title says "or run it again deeper" with no deeper button (no `deeper` in the need). Screens `acts-01-*`. No fix yet. |
| Run again deeper | [cnref#2912] | PASS | 2026-11-26 | Web **Run again deeper (careful, up to $13.60)** on room `xfav2em3` (escalated `budget-run`): ack `stepped_up`, card "Deeper run requested — it starts next", task `Queued` as `careful` with `stepUp {from: standard, to: careful, trigger: manual, mode: manual, by: smana}`. The room's **Will run** line for the stepped task omits the careful scoper. Stopped next (below). Screen `acts-02-deeper-ack.png`. |
| Accept the split | [#540], [#555] | NOT RUN | 2026-11-26 | No split was proposed to accept. #540 (`workflow:careful`, three independent files): the scoper ran it whole (PR #556, closed unmerged). #555 (four files, asking for one part each) queued behind `awaitingHumanWIP: 5` for over 25 minutes, the five places held by another session's pull requests, and was cancelled. The split part of the plan gate passed (**Split a plan**). |
| Approve a plan | [#512] | PASS | 2026-11-26 | The task moved to Implementing, but the click gave no visible acknowledgement; fix [maku#713] (v0.54.3). |
| Revise a plan | [#512] | PASS | 2026-11-26 | After the CRD patch ([maku#711]); three clicks deduped into one revision. No acknowledgement either; fix [maku#713]. |
| Split a plan | [#541], [#553] | PASS | 2026-11-26 | `plan-first` + `workflow:careful`, task `ajyrqj4k`: the scoper proposed a two-part plan ($0.01), the room offered **Approve** / **Revise** / **Split**; web **Split** got ack `plan_split`, the task went `Split` and opened part 1 as #553 (`factory/child-of:#541`, task `tlhkcohr`). The card vanished with no acknowledgement text; the rail shows the parts as `#? queued`; #553's body says the split was approved "with `/factory split`" though it came from the room. Screen `acts-04-plan-split-ack.png`. |
| Stop | [cnref#2912] | PASS | 2026-11-26 | Web **Stop** (with confirm) on room `xfav2em3` right after the deeper step: ack, task `Stopped`/`cancelled`, room header "Stopped — cancelled". Screen `acts-03-stop-ack.png`. |
| New task (`file`) | [#512], [#529] | PASS | 2026-11-26 | On v0.54.1, the web form filed #512 as the factory App, which refused its own `factory/ready` (`unauthorised_labeller`) and ignored its `workflow:careful`. Fix [maku#722] (v0.54.4): #529 was filed and started, `requestedBy github:Smana`. |
| A request wide enough for three issues: `start` files all three in order | [#519] | FAIL | 2026-11-26 | Re-checked with a `maku` built from Maku main `a26d990c` (after [maku#729]) against the v0.54.5 broker: the card read "The plan holds 3 issues: this files the first." The broker's `POST /api/handoffs/{id}/check` (`internal/humanapi/handoff.go`, `handoffCheckRoute`) never sets `wholePlans` or `issues` in its answer; only the MCP view does. So the terminal still files one issue, and v0.54.6 will too. Nothing was filed. The card's step-up figure is now on the plan's basis ("up to $15.30 · up to $40.80"). |

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
| Reverts merge themselves: `factory/revert` on a merged `docs-links` pull request | [#505] | FAIL | 2026-11-26 | On ai-native-ref (no `merge.autoRevert`), `factory/drill` then `factory/revert` on agent PR #505 (merged by the owner): the factory removed `factory/revert` without a revert PR or a comment, since a label revert serves only an auto-merged or approved-merged task. `maku policy drill Smana/ai-native-ref#505`, the documented drill for any merged PR, answered `503 drill_unavailable` twice with nothing in either factory pod's log. The breaker count could not be checked. Host drill not run. No fix yet. |
| Pause and resume: `maku policy pause` and `maku policy resume` | [#548], [#549] | PARTIAL | 2026-11-26 | Re-run after [maku#709] with `--config tooling/base/agent-factory/resources/factory.yaml`: pause opened #548, a one-line diff adding `paused: {reason: …}` under `spec.merge`, comments kept. Resume on an unpaused repository opened #549 with zero changed files instead of saying it is not paused. Both closed unmerged, so the served `paused` decision and the `Paused` condition were not read. |
| Promotion: **Promote to live** for `dead-links` after five clean decisions and a passed drill | | NOT RUN | | Not reached. The evidence reader refused cloud-native-ref past 500 records; fix [maku#717]. Backtest answered 503 until [maku#710]. |
| The reasons: `maku policy list` and `maku policy explain` on one decision of each repository | ai-native-ref#530, cnref#2876, runlore-kb#167 | PASS | 2026-11-26 | `list` on all four repositories (runlore has no decision) and `explain` on one decision each: every step of the timeline, the measurement and the comment link. `list` prints `1/0 files, 9/0 lines` for a decision with no policy. |

### 6b. Merge-policy safety drills

Agent pull requests on `Smana/ai-native-ref`, with `docs-links` in shadow; each was closed unmerged.

| Drill | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Links-only refuses a non-Markdown file | [#522] | PASS | 2026-11-26 | `human:no_policy_matched` on an `icons/manifest.json` change. |
| Links-only arms on a genuine relative retarget | [#521] | PASS | 2026-11-26 | `docs-links · shadow:shadow_would_arm`. |
| The host rule refuses a GitHub owner change | [#520] | PASS | 2026-11-25 | `human:no_policy_matched`, considered `docs:file_not_allowed`, `docs-links:class_mismatch`. |
| Links-only refuses an archive URL of another target | [#524] | PASS | 2026-11-26 | `human:no_policy_matched`. |
| Archive URL of the same target; footnote; submodule, symlink, empty or byte-equal diff; hold authority; decision race; two live policies; refused edits; evidence from maintainer merges only | | NOT RUN | | No docs-only agent diff produces them, they need a live arm or a second live policy, or they need config edits. |

### 6c. Hardening negatives and gate paths

Each admission check ran as a server-side dry run (`--dry-run=server`), so nothing was written.

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| The factory's `AgentRun` patch limit | | PASS | 2026-11-26 | As `agent-factory` on `run-scqdbavn`: a label refused ("never changes an AgentRun's labels"), another annotation refused ("only the usage-tokens, pull-request and revoked annotations"), `agents.ogenki.io/revoked` admitted. |
| Only the factory creates an `AgentRun` | | PASS | 2026-11-26 | An `AgentRun` created by a cluster administrator in `agents` refused by `agentrun-creators`. |
| Run pods | | PASS | 2026-11-26 | A restricted pod in `agents` refused for an administrator ("only the run-controller creates pods") and, as `run-controller`, without `runtimeClassName: gvisor`. |
| Run token Secrets | | PASS | 2026-11-26 | A Secret not named `<run>-git`, as `agent-factory`, refused by `run-token-secrets`. |
| Gate path: a maintainer-approved agent change under `scripts/ci/` hands off `gate_path` ([#493]) | [#550] | NOT RUN | 2026-11-26 | Task `5pkzxjii` queued behind `awaitingHumanWIP` with #555 and was cancelled. The earlier #511 (`scripts/ci/`) decided `human:no_policy_matched` before any approval; `gate_path` applies only once a maintainer approves. |
| SSRF and webhook guards, bundle and symlink refusals | | NOT RUN | | Need secrets or a crafted agent diff. |

## 7. Close

| Check | Issue or PR | Result | Date | Notes |
|---|---|---|---|---|
| Scratch and promotion pull requests closed, scratch labels removed, paused repository resumed, every failure recorded | | PARTIAL | 2026-11-26 | Drill PRs #510, #511, #520–#522 and #524 closed unmerged; real fixes #498, #505 and #513 merged on review. No repository was paused (#506 never merged). Scratch labels are not recorded as removed. Every failure is above. The 2026-11-26 drills closed #525, #548, #549, #556 and #558 unmerged, closed issues #538, #540, #541, #550, #553 and #555, stopped their tasks, removed `factory/drill` from #505 and paused nothing; they spent about $0.60. |

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
[#538]: https://github.com/Smana/ai-native-ref/issues/538
[#540]: https://github.com/Smana/ai-native-ref/issues/540
[#541]: https://github.com/Smana/ai-native-ref/issues/541
[#548]: https://github.com/Smana/ai-native-ref/pull/548
[#549]: https://github.com/Smana/ai-native-ref/pull/549
[#550]: https://github.com/Smana/ai-native-ref/issues/550
[#553]: https://github.com/Smana/ai-native-ref/issues/553
[#555]: https://github.com/Smana/ai-native-ref/issues/555
[#493]: https://github.com/Smana/ai-native-ref/pull/493
[maku#729]: https://github.com/Smana/maku/pull/729
