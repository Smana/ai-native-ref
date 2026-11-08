# Merge policy stages 1 and 2 — 2026-11-08

Stage 1's live proof ([plan 1, Task 10](../../superpowers/plans/2026-11-04-merge-policy-stage-1-read-plan.md))
and stage 2's live half ([plan 2, Task 9](../../superpowers/plans/2026-11-07-merge-policy-stage-2-simulation-plan.md)),
on aws-0 running Maku v0.39.0 with `policyManagement: {read: true}`. The canary is
Smana/cloud-native-ref at `feb0a140`, policy file `.github/agent-factory.yaml` (sha256 `3e8a410d7196…`).

| Check | Result |
|---|---|
| Precondition: every factory owning cloud-native-ref runs a release holding stage 1 | Both aws-0 replicas on `maku-factory:v0.39.0` |
| `maku_factory_repository_owned` | 1 for cloud-native-ref, ai-native-ref and runlore-kb, on both replicas |
| `maku_factory_policy_central_divergence{repository="Smana/cloud-native-ref"}` | A series at 0 on both replicas: compared, equivalent |
| `maku_factory_policy_load_errors_total{repository="Smana/cloud-native-ref"}` | No series |
| `maku policy check` on the canary's file | `equivalent`, exit 0 |
| Fail-safe (Task 10 Step 4), **offline** | The same file with one class's `harness:` set to `no-such-profile`: `class alert-rules: guardrail: harness "no-such-profile" is not in harnessProfiles`, exit 1 |
| `maku policy simulate` over the 16 conformance fixtures | 16 of 16 `unchanged` |

## What this does not prove

- **The fail-safe stayed offline.** The plan allows replaying the bytes through `maku policy check`
  instead of merging a bad file to the canary's default branch. The live counterpart (a
  `guardrail_mismatch` count while `repository_owned` stays 1) was not run.
- **The simulation stopped at CI.** Every fixture decides `wait:ci_pending` under both the central
  and the repository policy, each marked "the fixture recorded another central decision": the
  aws-0 config's required checks differ from the fixtures' rig, so no row reached a class rule.
  Equivalence of the class rules rests on `TestConformance` in Maku CI (#381) and on stage 3's
  dual evaluation, which re-decides real merges.

## Next

Stage 3 starts with this change: `policyManagement: {read: true, simulation: true, dualEvaluation: true}`.
It exits after one week of
`sum by (agreement) (increase(maku_factory_policy_dual_decisions_total{repository="Smana/cloud-native-ref"}[1d]))`
with no `unexplained`, recorded in `results-merge-policy-stage-3-<date>.md`.
