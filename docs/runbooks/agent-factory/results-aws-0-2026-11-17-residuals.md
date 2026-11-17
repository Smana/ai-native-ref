# AWS v4 residual cases — 2026-11-17 evening

**Status:** in progress. Follows [the 2026-11-16 campaign](results-aws-0-2026-11-16.md) on the same
aws-0 factory, Maku v0.53.1 with the fixes recorded there. **Procedure:** [runbook 28](28-v4-aws-validation.md).
Evidence directory: `$DRILL_DIR` (`~/.cache/v4-aws-validation`), subdirectories `w7/`, `m5/` and
`onboarding/`.

## Results

| Test ID | Result | Evidence | Notes |
|---|---|---|---|
| W7 — `maku repo add` and `repo check`, four repositories | PASS on a pre-release build | [maku#620](https://github.com/Smana/maku/pull/620) at `4ccbd7db`, built locally; `w7/add-*.log`, `w7/check-*.log`, `w7/diff-ai-native-ref.txt` | With `--factory-app-id 5095249`, every `repo add` wrote 5 files and applied nothing (ai-native-ref round trip 3 s). Every `repo check` line is PASS: fence, repository, apps, merge-gate, private-code. The rendered Repository differs from the committed one only by platform additions (the shadow policy bindings, the dead-links schedule, `checks.egress`, `merge.maxPerDay`, `fixRuns`, `checkReruns`, `${cluster_name}`). An unset `workflow.default` resolves to `standard` (Maku `internal/factory/config/workflows.go:104`). `leakScanCheck` defaults to the first required check (`validate`); the committed `lint` is a choice `--leak-scan-check` reproduces. Final once #620 ships in a release. |
| W2-source — scheduled and revert sources | PARTIAL | Tasks `m3size45`, `m3shape5`, `m3path46` | Schedule-sourced Tasks select `quick` with no label (`status.profile.source` `schedule`; `m3path46`, on the `ai-native-ref-dead-links` key, records `oracle`). They are M3 fixtures, not a cron firing with genuine findings. No revert-sourced Task exists: a revert is requested in M8, which stays blocked. |
| M5 — strictest selection, cap and pause | NOT RUN | `m5/markers.txt`, `m5/policy-*.json` | Across the 16 ai-native-ref PRs #419–#450 with a gate marker, no decision had two holding policies: each `considered=` lists one candidate at most and refuses the rest. The overlap needs a dead-links-class task whose diff only changes links in `website/content/*.md`, so `docs` and `dead-links` both hold. Cap and pause need M8. |
| CP4 — warm node outside its window | PASS (one reading) | `kubectl -n agent-system get scaledobject agents-headroom` at 23:12 Europe/Paris | Ready; cron trigger `0 8 * * 1-5` to `0 19 * * 1-5` Europe/Paris, `desiredReplicas: 1`; the Deployment at 0 replicas; Flux's `agents-headroom` Kustomization Ready. The in-window reading and the week's start and cost readings remain. |
| M1 — detailed `considered=` on a config-only PR | PENDING | [#452](https://github.com/Smana/ai-native-ref/issues/452) | Rejected at 22:10 UTC with `daily_task_cap` (20 Tasks on 2026-11-17 UTC); re-applied after the UTC day turns. |
| Cache-costs lot 1 baseline, `docs` run | PENDING | [#451](https://github.com/Smana/ai-native-ref/issues/451) | Rejected at 22:09 UTC with `daily_task_cap`; re-applied after the UTC day turns. |

## Blocked on the owner

| Case | Needs |
|---|---|
| B9, and the baseline's internal investigation run | A valid internal provider credential for `agent-default` |
| W7 final | maku#620 merged and released |
| B6, W5-untrusted, M7 authorization | A second, non-maintainer GitHub and Slack actor |
| W4 confirmation source, W8 filed hand-off | The owner's answer to the `start` form, during the screencast session |
| Credential exposure follow-up | The key rotation listed in the 2026-11-16 results |
