# Live gates on aws-0 — 2026-10-30 and 31

The merge gate's human path, proven live on the Agent Factory's return to aws-0: approve-to-merge, the
lifted `changes_requested`, force-push safety, the regression breaker and its recovery, and one
`dead-links` drill with the merger's unattended revert. The cluster is `aws-0`, tracking
cloud-native-ref `main`. The session started on Maku v0.32.0 and ended on **v0.32.3** (broker, factory,
harness and bridge; crossplane-configuration v0.9.31), through session pins of ai-native-ref
(`v2.8.21-pr248`, then `-pr262`, `-pr268`, `-pr267`). The plan was
[the aws-0 merge gate session plan](../../superpowers/plans/2026-10-29-aws-0-merge-gate-session-plan.md);
the design, the [human path](../../superpowers/specs/2026-10-29-merge-gate-human-path-design.md). Times are UTC.

**Verdict.** The human path works on aws-0. Of the proofs run, every one passes except that the approved
merge's *record* (N6) failed on v0.32.0 and its re-proof on v0.32.3 is **pending**. The session found and
fixed five bugs, all but one (the room's "Your move" text) shipped in v0.32.1 to v0.32.3. Five proofs were
not run. Release tags, merges to `main` and every approval were the owner's.

## Proofs

| ID | Result | Evidence |
|---|---|---|
| S0 — workloads, RBAC, keys | PASS | 8 nodes; every Kustomization Ready (`llm-platform` suspended by design); `agent-factory` 2/2, `room-broker` 2/2, `policy-bot` 2/2. `can-i list helmreleases` yes, `create` no. `approveToMerge: true` and `recoverAfter: 3` on both repositories |
| S0 — ledger and gauge | PASS, at the first decision | v0.32.0 reads the ledger at the first decision, not at boot. 22:47:12Z on ANR #241: `merge ledger read from GitHub` classes=7; `class_paused{docs} 0` |
| policy-bot | PASS, after a fix | First deliveries on scratch ANR #239 failed the signature: the webhook secret restored from the OpenBao snapshot of 2026-10-16 did not match the App's ([ops findings](#ops-findings)). After the owner set the App's secret to the OpenBao value, `policy-bot: main = success`, deliveries 200 |
| AM3 and AM8 | PASS | ANR #241's hand-off comment: one action named ("approve this pull request"), and a decision record `<!-- agent-factory-decision head=67dfa768 class=docs decision=human:class_unarmed … -->`. Unread fields print `-` since [maku#303](https://github.com/Smana/maku/pull/303) |
| L3 — negative half | PASS | 0 adopted Tasks is right: the 5 open Renovate PRs are all ineligible. #2688 touches `opentofu/` (outside `allowedFiles`), #2689 and #2685 workflows, #2681 a major, #2629 `mise.toml`. `github_up=1`, kill switch 0 |
| N6 — approve-to-merge | PARTIAL: merge PASS, record FAIL on v0.32.0 | ANR #249, 07:19:24Z owner approved `a369c962` → 07:19:34 `reentered_approved` → 07:19:36 `arm` / `maintainer_approved` → 07:19:39 merged by `ogenki-agent-merger[bot]` at the approved head. But the PR carried `factory/auto-merged:docs`, the task sat in `Verifying`, and `mergedHow` / `approvedBy` were lost ([bug 1](#bugs-found-and-fixed)). **The re-proof on v0.32.3 is pending**: ANR #270 (12:21Z), waiting for the owner's approval; it must end `Done` / `merged`, `mergedHow: approved`, `factory/approved-merge`, `approved_merged` |
| A5 — lifted `changes_requested` | PASS (step 1 live) | The owner requested changes at `67dfa768` on ANR #242: 22:49:02Z the task turned to `revising` ("is revising after @Smana's review"), implementer run `j3pkh5vy` at 22:49:04Z. The approval half rode on N6's merge path; N6 attempt 1 was abandoned (revisions oscillated and the next push dismissed the approval) |
| A7 — approval vs force-push | PASS (safe) | ANR #250: the owner approved `bf5bac0d` at 07:19:24.2Z; force-push to `e009d19a` at 07:19:25.9Z; policy-bot dismissed the approval ("Invalidated by push of e009d19"). No merge; the task stayed `AwaitingHuman` / `class_unarmed`; its status head stayed `bf5bac0d` |
| M1 — regression breaker | PASS | ANR #251 → PR #252 (shadow class `docs-links`): `shadow:shadow_would_arm`; merged by the owner 07:46Z; the monitor labelled it `factory/merged:docs-links`, then `factory/monitor:regression`; after a factory restart the ledger was re-read (classes=7) and `class_paused{docs-links}` = 1 at 07:48Z; no revert opened |
| M2 — follow-up detection | PASS | #256 (a follow-up rewriting #252's line) labelled `factory/follow-up-of:#252` at 07:58:38Z; #257 (unrelated, merged 07:58:16Z) unlabelled: precision 1/1, recall 1/1 |
| AM4 — shadow while paused | PASS | With `docs-links` paused: PR #258 (07:58:52Z) and #260 (07:58:48Z) record `shadow:shadow_would_arm` with `paused=true capped=false` |
| N8 — recovery | PASS | #258, #259, #260 merged 08:02:45 to 51Z, all clean through maturity. `class_paused{docs-links}` 1 → 0 at 09:05:51Z, t1 + 63 min (`followUpWindow: 1h`, `recoverAfter: 3`). Probe on ANR #265: `shadow_would_arm paused=false` after `policy_pending` → return |
| L2 — the `dead-links` drill | PASS | [below](#l2-the-dead-links-drill) |
| L2 — [maku#158](https://github.com/Smana/maku/pull/158), the unattended revert merge | PASS | 11:47:22Z `ogenki-agent-merger` merged its own drill revert cnref #2698, no human; the dead-links gauge stayed 0 |
| L2 — tally | PASS | `shadow-merge-tally.sh --class dead-links --repo Smana/cloud-native-ref --outcomes`: `merges=1 bad=0 reverted=0 drill=1` (#2697, a drill, not counted). The ANR `docs-links` tally lists 4 merges, all immature under the default 168 h window (the session used 1 h); `--strictness --replay`: `merged_unchanged=4 changed=0 would_arm=4 would_refuse=0 unreplayable=0` |
| N7 — shadow under a cap (bonus) | PASS | cnref #2700, 12:18:23Z: `capped=true` (the day's cap spent by #2697's armed merge at 11:11:40Z) yet the shadow still records `shadow_would_arm` (AM4) |
| Metrics (A9) | PASS | `human_wait_seconds_total{reason}` shows only closed codes; `merge_decisions_total{repository,class,verdict,reason}`; first live `handoff_to_merge_seconds{how="human",reason="policy_pending"}`: p50 150 s (the reason is the *first* hand-off) |
| Dashboards and alerts (A10) | PASS (deployed, not viewed) | The "Human path" row and "Classes paused" panel synced; `AgentFactoryClassPausedLong`, `AgentFactoryAutoMergeReverted` and `AgentFactoryMergeRegression` loaded, health ok, inactive. Grafana is behind ZITADEL, so the rendering was not viewed |
| N1 — policy replay | NOT RUN | Needs the policy-bot UI token |
| N3 — release age | NOT RUN | No eligible Renovate PR |
| #182 — the `AwaitingCI` bound | NOT RUN | Needs a scratch class |
| A4 — next-day return (`reentered_day_turned`) | NOT RUN | Clock-bound |
| G1 — the drill label on cnref #2521 lifts `docs-links` | NOT RUN | The host exports only `class_paused{dead-links}` = 0; no host `docs-links` decision happened, so the lift was never read |

## L2: the dead-links drill

[Runbook 15](15-dead-links.md) §3. The host is `Smana/cloud-native-ref`; the class and its fence came
from cnref #2692 (the `low-risk: dead-links` rule and the plant). Two attempts: the first, on v0.32.0, was
blocked by [bug 2](#bugs-found-and-fixed); the second ran on v0.32.3.

| Step | Result | Evidence |
|---|---|---|
| Plant and detector | PASS | `https://kubernetes.io/docs/setup/production-environment/turnkey/aws/` in `docs/architecture/README.md`: 404, with a Wayback snapshot (`web/20201102042446/…`). Runs `41185811826` and `41186006619`: 1 finding of 21 carried an archive |
| First attempt, v0.32.0 | FAIL (bug 2) | 09:20Z the probe created Task `syib7lmo`, but every status write was refused: `status.classification.fallback: Unsupported value: ""`. Rolled back (cnref #2694) and waited for v0.32.3 |
| Resume on v0.32.3 | PASS | 11:01Z cnref #2696: the factory on v0.32.3, `dead-links {live: true}`, cron `*/10`. `syib7lmo` (stuck since 09:20) progressed to `Implementing`, no `Unsupported value` error: [maku#306](https://github.com/Smana/maku/pull/306) holds live |
| Diff | PASS | cnref #2697: one line in `docs/architecture/README.md`, the plant → `web.archive.org/web/20201102042446/<plant>`; nothing else |
| Merge | PASS | 11:11:41Z `arm` / `armed` (`class=dead-links lines=2/20 oracle=ok paused=false capped=false`), merged by `ogenki-agent-merger` at `aded5317`; `factory/auto-merged:dead-links`; `mergedHow=class` (the [#302](https://github.com/Smana/maku/pull/302) fix: the record is kept) |
| Verified | PASS | Oracle runs `41195877806` and `41196103891` (dispatched after the merge): success, finding gone. 11:41:59Z `Done` / `merged_verified`; `factory/merged:dead-links` |
| Drill revert | PASS | `factory/drill` 11:42:16Z, `factory/revert` 11:42:52Z → `Reverted` / `revert_requested`, `revertNumber` 2698, `drill=true`. #2698 opened by the merger with `factory/drill` + `factory/revert-of:#2697`; exactly one revert PR (no duplicate) |
| Notices (AM6) | PASS | #2188 carries the `ClassDrill` notice ("reverted as a drill … the class's breaker does not count the revert"), no `ClassDemoted`; #2697 the revert note |
| Back in shadow | PASS | cnref #2699 12:01Z (`dead-links` shadow, `*/10` probe). The plant is back on `main`; cnref #2700 (task `dcw4pf7g`) decided `shadow_would_arm paused=false capped=true` at 12:18:23Z: the drill revert was not counted |

## Bugs found and fixed

| # | Bug | Fix |
|---|---|---|
| 1 | **Lost approved-merge record.** A pass that merged on a stale cache then conflicted on its end-of-pass status update, dropping `mergedHow`, `approvedBy`, the comment and the decision metric; the replay took the lost-write branch and recorded a class auto-merge. The same race could open a second revert PR | [maku#302](https://github.com/Smana/maku/pull/302), in v0.32.2: the merge and the revert write a narrow patch right after GitHub takes them. Live: `mergedHow=class` kept on the L2 merge, one revert PR. The approved path is re-proved on v0.32.3 (ANR #270, pending) |
| 2 | **Oracle-class fallback.** Triage's oracle-class branch returned a classification with no `fallback`; the CRD refused every status write, so every `dead-links` task was stuck on v0.32.0 | [maku#306](https://github.com/Smana/maku/pull/306), in v0.32.3: fallback `none`, plus an envtest against the CRD. Proven live: the stuck task progressed |
| 3 | **cnref #2691.** The host's `test-ai-overlay-from-git` failed on any pre-release pin of ai-native-ref (the session's `v2.8.21-pr248`): its tree half runs `ai-overlay.sh --from-git`, which refuses a pre-release by design | cnref #2691: the tree half runs on a release pin only and says why it skips. Maku's own `harness-checks` got the same skip in [maku#305](https://github.com/Smana/maku/pull/305) (v0.32.3) |
| 4 | **Judge path (#297).** The harness read `…/12-live-auto-merge-drill.md: proves` as the path `…/12-live-auto-merge-drill`, judged it missing, said `not_yet` three times and stalled the task on a done PR. Found and fixed by another session | [maku#297](https://github.com/Smana/maku/pull/297), in v0.32.1 (matches whole paths). Reaches runs with the harness bump to v0.32.2 or later (xpc v0.9.31 carries v0.32.3) |
| 5 | **The room's "Your move" text** ignores `approveToMerge`: it always tells the human to bypass (`--admin`), when the move is to approve | Reported, being fixed; not shipped |

Findings kept open: [maku#304](https://github.com/Smana/maku/issues/304) (the approval binding's residuals R1 to
R3; the review's commit id is reported as the new head after a force-push, so safety rests on the dismissal and on
counting `APPROVED` only, and #301 binds on the head's push time too), and a minor one fixed by
[#303](https://github.com/Smana/maku/pull/303) (unread `paused=` and `capped=` printed `false`).

## Ops findings

- **A restored OpenBao snapshot can hold a stale policy-bot webhook secret.** Check it after every restore: a
  mismatch with the GitHub App's secret fails every delivery's signature, and `policy-bot: main` never posts.
  The owner re-set the App's secret to the OpenBao value (also in [Runbook 00](README.md#runbook-00-one-time-cluster-setup)).
- **The Z.ai wallet.** Every public run uses GLM through Z.ai, and the other providers' keys were absent, so an
  empty open-platform wallet (`LLMRateLimitError … Insufficient balance`, error 1113) stopped every agent-run proof
  for about 7 hours, until the owner recharged it at 06:53Z on 2026-10-31. A `/factory retry` restarted the tasks.
- **Approvals are human clicks.** An agent session's auto-mode refuses `gh pr review --approve` as
  self-approval, even with the owner's allow rule. Requesting changes was allowed. N6 and A7 waited for the owner,
  and an approval counts only on the head it reviewed, after the runs end and a minute passes
  ([runbook 24](24-screencast.md)).
- **A pre-release pin turned the CI red.** While cloud-native-ref pinned `v2.8.21-pr248` (and later
  `-pr262`/`-pr268`), `ai-overlay --from-git` refused it: maku's `harness-checks` was red on every PR and on `main`
  (maku#305 now skips it), and the host's own test failed the same way (cnref #2691). Judge such PRs on the other
  checks meanwhile; an admin merge was the owner's.
- **The `policy_pending` race returns on policy-bot's status.** A new hand-off first reads `human:policy_pending`
  (the check has not posted), then re-decides as `reentered_policy`/`reentered_approved` once `policy-bot: main`
  lands. Expect this pair on every first decision: the hand-off record is on the issue, the re-decision on the PR.
  An early M1 marker read `paused=false` because of it; the later read is the one that counts.
- **A spot reclaim ends running implementers `Disrupted`** (F1): two runs at once on 2026-10-30; they resume.
- **The session ran the v0.31.0 harness** until cnref #2695 (xpc v0.9.31) composed v0.32.3, so the harness
  changes of v0.32.0 reached runs only then.

## Not run, and why

| Proof | Why |
|---|---|
| N1 policy replay | The policy-bot UI token was not available |
| N3 release age | No eligible Renovate PR in the window |
| #182 `AwaitingCI` bound | Needs a scratch class |
| A4 next-day return | Clock-bound: it needs a day turn with a cap hand-off |
| G1 host `docs-links` lift | No host `docs-links` decision; only `dead-links` was exercised on the host |
| N6 re-proof on v0.32.3 | Pending: ANR #270 awaits the owner's approval |

`dead-links` is back in shadow on cloud-native-ref, and `docs-links` in shadow on ai-native-ref. A class leaves
shadow after a full day's live proof, not after this session.
