# AWS v4 residual cases — 2026-11-17 evening

**Status:** complete for this session (2026-11-17 evening to 2026-11-18). Follows [the 2026-11-16 campaign](results-aws-0-2026-11-16.md) on the same
aws-0 factory, Maku v0.53.1 with the fixes recorded there. **Procedure:** [runbook 28](28-v4-aws-validation.md).
Evidence directory: `$DRILL_DIR` (`~/.cache/v4-aws-validation`), subdirectories `w7/`, `w7-release/`,
`m5/`, `baseline/` and `onboarding/`.

## Results

| Test ID | Result | Evidence | Notes |
|---|---|---|---|
| W7 — `maku repo add` and `repo check`, four repositories | PASS | Maku [v0.53.2](https://github.com/Smana/maku/releases/tag/v0.53.2) (fix [maku#620](https://github.com/Smana/maku/pull/620)), release CLI checksum-verified; `w7-release/add-*.log`, `w7-release/check-*.log`, `w7-release/no-flag.log`, `w7/diff-ai-native-ref.txt` | With `--factory-app-id 5095249`, every `repo add` wrote 5 files and applied nothing (ai-native-ref round trip 1.6 s). Every `repo check` line is PASS: fence, repository, apps, merge-gate, private-code. Without the flag, the private App's 404 exits 1 naming `--factory-app-id`. The rendered Repository differs from the committed one only by platform additions (the shadow policy bindings, the dead-links schedule, `checks.egress`, `merge.maxPerDay`, `fixRuns`, `checkReruns`, `${cluster_name}`). An unset `workflow.default` resolves to `standard` (Maku `internal/factory/config/workflows.go:104`). `leakScanCheck` defaults to the first required check (`validate`); the committed `lint` is a choice `--leak-scan-check` reproduces. |
| W2-source — scheduled and revert sources | PARTIAL | Tasks `m3size45`, `m3shape5`, `m3path46` | Schedule-sourced Tasks select `quick` with no label (`status.profile.source` `schedule`; `m3path46`, on the `ai-native-ref-dead-links` key, records `oracle`). They are M3 fixtures, not a cron firing with genuine findings. No revert-sourced Task exists: a revert is requested in M8, which stays blocked. |
| M5 — strictest selection, cap and pause | NOT RUN | `m5/markers.txt`, `m5/policy-*.json` | Across the 16 ai-native-ref PRs #419–#450 with a gate marker, no decision had two holding policies: each `considered=` lists one candidate at most and refuses the rest. The overlap needs a dead-links-class task whose diff only changes links in `website/content/*.md`, so `docs` and `dead-links` both hold. Cap and pause need M8. |
| CP4 — warm node outside its window | PASS (one reading) | `kubectl -n agent-system get scaledobject agents-headroom` at 23:12 Europe/Paris | Ready; cron trigger `0 8 * * 1-5` to `0 19 * * 1-5` Europe/Paris, `desiredReplicas: 1`; the Deployment at 0 replicas; Flux's `agents-headroom` Kustomization Ready. The in-window reading and the week's start and cost readings remain. |
| M1 — detailed `considered=` on a config-only PR | PARTIAL | [#462](https://github.com/Smana/ai-native-ref/issues/462) / `75o7t6ia` / [#464](https://github.com/Smana/ai-native-ref/pull/464) | Rerun on a fresh task: #452's task had spent its budget on last night's red `validate` and refused `/factory retry` and ignored an approval (maku#628). #464 changes only `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml` (and a test whose `"source"` guard matched "resources"); the gate answered `review: a human decides, no_policy_matched`, the expected hand-off. FAIL on the detail: a no-match decision writes no record, so `GET …/decisions/464` has 0 entries and the PR carries no `considered=` (maku#628 comment). Merged on approval. |
| Cache-costs lot 1 baseline, `docs` run | PARTIAL | [#451](https://github.com/Smana/ai-native-ref/issues/451) / `i2o3xm46` / [#455](https://github.com/Smana/ai-native-ref/pull/455); `baseline/*-harness.log` | Outside the warm node's window, pod created to harness started: **167 s and 172 s cold** (implementers `x72r2xcl`, `pvysry3e`: Karpenter created the gVisor node at 00:07:06), **4 s and 5 s** for the reviewers on the same node. `agent-checks`: 160–213 s a run; 0 model retries; no `agent-run cache:` or `condensation:` line in any harness log, so no `miss=unexpected`. Boot and clone spans are in traces, not read here. #455's diff is exactly the acceptance line and the reviewer approved; its fix run for the red `validate` spent the run budget (task escalated, 1.8 M tokens). The `scripts` and internal-investigation baseline runs remain (the latter needs the internal credential). |

## Devex validation, 2026-11-18

After #457 (Start now) and the v3.27.2 bundle (Maku v0.53.3: start's form waits 5 min; rooms cookie `SameSite=Lax`; room dashboard on 24 h), the developer journeys were run from Claude Code 2.1.325 and OpenCode 2.3.2. Full table and owner journeys: `devex-tests.md` in the evidence directory.

| Journey | Result | Notes |
|---|---|---|
| Handoff → form → Start now → PR → approve → merge (Claude Code) | PASS | #458/#459: 17 min, $0.14; #463/#465: merged 27 s after approval |
| Same in OpenCode | PASS on 2.3.2, FAIL on 2.0.22 | 2.0.22 never shows MCP forms (`/form` 404) |
| Unanswered form | PASS | 5 min 7 s, "the plan is kept … call start again"; needs the v0.53.3 **CLI** |
| Broker unreachable | PASS | `FAIL dns … connect your VPN (Tailscale)` |
| Slack plan | FAIL → fixed | Every asked plan refused `unresolved_marker` (maku#623, fixed in v0.53.4) |
| Planner quality | FINDINGS | `planner_invalid` retries (up to 3), a second question for a stated done-when, wrong recommendations, a repository guessed without context (maku#625, #626) |

## Found: `validate` is red on `main` since the PR #618 branch was deleted

`scripts/ci/validate-factory-config.sh` builds the CLI from the factory image's version. For the PR
image `v0.53.2-pr618.9d0bdb48` it runs `go install github.com/Smana/maku/cmd/maku@9d0bdb48`, and that
commit no longer resolves (`invalid version: unknown revision 9d0bdb48`): the PR branch was
squash-merged and deleted. Every pull request on `main` now fails `validate`, and a factory fix run
spends its budget on a failure outside its diff (#455). [#454](https://github.com/Smana/ai-native-ref/pull/454)
pins the released Maku v0.53.2 everywhere; its own `validate` passed. Merging it needs the
`maku/merge-gate` admin bypass, which this session's operator was not allowed to use.

## Blocked on the owner

| Case | Needs |
|---|---|
| B9, and the baseline's internal investigation run | A valid internal provider credential for `agent-default` |
| B6, W5-untrusted, M7 authorization | A second, non-maintainer GitHub and Slack actor |
| W4 confirmation source, W8 filed hand-off | The owner's answer to the `start` form, during the screencast session |
| Credential exposure follow-up | The key rotation listed in the 2026-11-16 results |
