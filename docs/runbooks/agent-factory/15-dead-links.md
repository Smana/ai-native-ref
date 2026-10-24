# 15 — The `dead-links` class: shadow, then the drill

Brings the merge gate's `dead-links` class from declared and off to shadow, then, on the owner's go, to
one live drill. Design: [merge gate classes](../../superpowers/specs/2026-10-22-merge-gate-classes-design.md)
(MC1 to MC14). The class is declared on both repositories and has no `live` or `shadow` key: until a
session writes one, it has no intake and takes no decision. See [README.md](README.md) for `CLOUD`.

## 1. Prerequisites

- [ ] agent-platform v0.21.0 or later pinned (`flux/sources/ocirepo-agent-factory.yaml`): the
  vocabulary (`allowedFiles`, `protectedFiles`, `modifyOnly`, `maxModifiedLines`, `diffShape`,
  `holdoutChecks`, `oracle`) and the `dead-links` probe, and the post-merge monitor.
- [ ] The host's `dead-links` workflow (`.github/workflows/dead-links.yaml`) has run on `main` twice,
  each run holding a `findings` artifact (written by `.github/scripts/dead-links/findings.py`):

  ```bash
  gh run list -R Smana/cloud-native-ref --workflow dead-links.yaml --branch main
  ```

- [ ] The merger App's `actions` permission holds ([runbook 12's mint test](12-live-auto-merge-drill.md#the-mint-test)).
- [ ] The merger App's installation grants `issues: write` on both repositories (an owner action:
  GitHub, the App's installation, Permissions; accept the update if GitHub asks). The monitor's labels
  are written in shadow too, so this is needed before the first shadow merge.
- [ ] The factory's egress reaches GitHub's artifact storage (`productionresultssa*.blob.core.windows.net`,
  `tooling/base/agent-factory/network-policy.yaml`): GitHub redirects an artifact's download there.

## 2. Shadow (L1)

One commit: `dead-links: {…, shadow: true}` on the host's entry in
`tooling/base/agent-factory/helm-values-configmap.yaml`, and the `link-rot` schedule removed (M4: the
two schedules would fix the same links twice).

| Proof | Reading |
|---|---|
| The next 07:00 UTC slot with findings creates one Task | `kubectl -n agent-system get tasks -l agents.ogenki.io/source-ref=dead-links`: one Task, `solo`, tier `light`, `spec.findings` set |
| Its pull request is held for the holdout check | The check "External links 🔗" and a `would-arm head=<sha>` comment |
| The decision is recorded | `vm 'sum by (class, verdict, reason) (agent_factory_merge_decisions_total{class="dead-links"})'` shows `shadow_would_arm` |
| No egress drop | `hubble observe --namespace agent-system --verdict DROPPED --to-fqdn '*.blob.core.windows.net'` is empty |

The panel "Merge decisions by class and reason (7 days)" on the agent-factory dashboard shows the same.

## 3. The drill, L2 (the owner's go)

1. Plant `[x](https://<host>/does-not-exist)` in a host document and dispatch the workflow twice.
2. A host PR first adds `low-risk: dead-links` to the host's `.policy.yml` (the `docs-links` rule renamed,
   R23); then the class goes `live: true`.
3. The merger merges at the head the checks ran on. After two scheduled detector runs,
   `kubectl -n agent-system get task <id> -o jsonpath='{.status.monitor}'` shows `oracle: healthy` and
   `main: healthy`, and the PR carries `factory/merged:dead-links`. The verdict comment arrives at 168 h
   (a drill does not wait for it).
4. Label the merge `factory/revert`: the revert merges, and the next decision reads `class_paused`.
5. Back to `shadow: true`.

## 4. What fails closed

No task is created for: a failed scan run, a pull request run, a stranger's dispatch, a finding in one
run only, an http target, a protected file, a URL in prose or a code block. An unreadable artifact
(egress, permission) makes the tick error
(`agent_factory_intake_errors_total{source="schedule"}`) and creates nothing.

## 5. The post-merge monitor

Declared on the host's `dead-links` only (`oracleRuns: 2`, `followUpWindow: 168h`, no `flux`). Each
merge of the class, whoever merged it, is watched for main's CI, the detector's next two scheduled runs
and the 7 days of later merges. The verdicts are `healthy`, `regression` and `inconclusive`; every
unreadable answer is `inconclusive`, never `healthy`. Declaring the monitor never back-fills older
merges: only merges made after the pin are watched.

### What the monitor never does

- Revert on its own: main red within `verifyFor` still opens the revert (design §6.4), nothing else does.
- Widen a class: it records a verdict, labels the PR, comments and feeds the breaker. Widening is the
  owner's config PR, citing the calibration tally.

### When `AgentFactoryMergeRegression` fires {#regression}

Nothing was reverted. The class is demoted (`class_paused`) at its next decision.

1. Read the verdict comment on the PR (it ends `verdict=regression`) and its labels
   (`factory/monitor:regression`, `factory/merged:dead-links`, any `factory/follow-up-of:#<n>`).
2. Find the signal that regressed: main's CI (red on the merge commit), the detector (a scheduled run
   reports gone a target the merge wrote), or a follow-up (a later PR fixing lines this merge wrote).
   Flux is not declared on `dead-links`, so it is never the cause here.
3. Revert or fix: label the PR `factory/revert` to revert it, or open the fix as a normal PR.
4. Know the demotion: `maxFollowUps: 1` in a window of 10 counts a follow-up or a regression like a
   revert, and one is enough. The class stays at human review until the breaker's newest 10 merges of
   the class no longer hold the bad outcome.
5. To un-demote: merge clean PRs of the class (a maintainer's merge counts, it refills the window) until
   the regressed merge is out of the newest 10. The labels live on GitHub, so a rebuild of the factory
   keeps the demotion. Do not widen the class meanwhile.
