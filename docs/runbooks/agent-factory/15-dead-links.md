# 15 — The `dead-links` class: shadow, then the drill

Brings the merge gate's `dead-links` class from declared and off to shadow, then, on the owner's go, to
one live drill, run on aws-0 on 2026-10-31 ([results](results-aws-0-2026-10-30.md#l2-the-dead-links-drill)). Design: [merge gate classes](../../superpowers/specs/2026-10-22-merge-gate-classes-design.md)
(MC1 to MC14). The class is declared on both repositories and is in shadow on both (`shadow: true`,
§2): it decides, never arms. A class with no `live` or `shadow` key has no intake and takes no decision. See [README.md](README.md) for `CLOUD`.

## 1. Prerequisites

- [ ] Maku v0.21.0 or later pinned (`flux/sources/ocirepo-agent-factory.yaml`): the
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
two schedules would fix the same links twice). `link-rot` stays beside the class until the live drill's
breaker and revert proof (§3) is done; then a host change removes it.

| Proof | Reading |
|---|---|
| The next 07:00 UTC slot with findings creates one Task | `kubectl -n agent-system get tasks -l agents.ogenki.io/source-ref=dead-links`: one Task, `solo`, tier `light`, `spec.findings` set |
| Its pull request is held for the holdout check | The check "External links 🔗" and a `would-arm head=<sha>` comment |
| The decision is recorded | `vm 'sum by (class, verdict, reason) (maku_factory_merge_decisions_total{class="dead-links"})'` shows `shadow_would_arm` |
| No egress drop | `hubble observe --namespace agent-system --verdict DROPPED --to-fqdn '*.blob.core.windows.net'` is empty |

The panel "Merge decisions by class and reason (7 days)" on the agent-factory dashboard shows the same.

## 3. The drill, L2 (the owner's go)

1. Plant a link to a **real dead page that the Wayback Machine holds a snapshot of**, in a file that
   **sorts before the existing findings**, then dispatch the workflow twice. A finding becomes a task
   only with an archive URL, and `findings.py` looks up at most 20 archives per run, in file order: a
   host with 20 findings already (cloud-native-ref's, all under `website/`) spends the budget on them.
   `[x](https://<host>/does-not-exist)` has no snapshot and can never become a task. The drill used
   `https://kubernetes.io/docs/setup/production-environment/turnkey/aws/` (404 today, a Wayback
   snapshot answering 200) in `docs/architecture/README.md`, which sorts before `website/`. Check
   the plant first: both detector runs report it `404` and the newest carries its `archive`.
   The class rewrites it to the snapshot, one line.
2. The probe only fires in the hour after a cron slot (`0 7 * * *`). For a drill, override the
   host's `dead-links` schedule to `cron: "*/10 * * * *"` for the session, never merged to stay:
   it weighs the newest two detector runs every ten minutes while no task of the schedule is open.
   A host PR first adds `low-risk: dead-links` to the host's `.policy.yml` (the `docs-links` rule renamed,
   R23); then the class goes `live: true`.
   **Use Maku v0.32.3 or later**: before it, the oracle-class branch of triage returned no
   `classification.fallback`, the CRD refused every status write, and every `dead-links` task was stuck
   (fixed by [maku#306](https://github.com/Smana/maku/pull/306); the stuck task progressed on the new
   release).
3. The merger merges at the head the checks ran on. After two detector runs dispatched after the merge,
   `kubectl -n agent-system get task <id> -o jsonpath='{.status.monitor}'` shows `oracle: healthy` and
   `main: healthy`, and the PR carries `factory/merged:dead-links`. The verdict comment arrives at 168 h
   (a drill does not wait for it).
4. Label the merge `factory/drill`, then `factory/revert`: the merger opens the revert and merges it
   itself, unattended; the breaker does not count a drill revert, so the next decision is not
   `class_paused` (without the drill label it would be). The tally reads `drill=1 bad=0`.
5. Back to `shadow: true`.

## 4. What fails closed

No task is created for: a failed scan run, a pull request run, a stranger's dispatch, a finding in one
run only, an http target, a protected file, a URL in prose or a code block. An unreadable artifact
(egress, permission) makes the tick error
(`maku_factory_intake_errors_total{source="schedule"}`) and creates nothing.

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

### When `AgentFactoryMergeRegression` fires

Nothing was reverted. The class is demoted (`class_paused`) at its next decision.

1. Read the verdict comment on the PR (it ends `verdict=regression`) and its labels
   (`factory/monitor:regression`, `factory/merged:dead-links`, any `factory/follow-up-of:#<n>`).
2. Find the signal that regressed: main's CI (red on the merge commit), the detector (a scheduled run
   reports gone a target the merge wrote), or a follow-up (a later PR fixing lines this merge wrote).
   Flux is not declared on `dead-links`, so it is never the cause here.
3. Revert or fix: label the PR `factory/revert` to revert it, or open the fix as a normal PR.
4. Know the demotion: `maxFollowUps: 1` counts a follow-up or a regression like a revert, and one is
   enough. The class stays at human review (`class_paused`) until `recoverAfter: 3` clean, mature
   merges of the class land after the bad one (a maintainer's merge counts, once its follow-up window
   has passed).
5. To un-demote: merge clean PRs of the class until three are mature. Proven on aws-0 with a
   one-hour window: three clean `docs-links` merges, gauge `class_paused` 1 to 0 about an hour later. The labels live on GitHub, so a rebuild of the factory
   keeps the demotion. Do not widen the class meanwhile.

## 6. ai-native-ref

This repository runs its own lane: `.github/workflows/dead-links.yaml` (the nightly `scan` at 04:41 UTC
and the "External links 🔗" holdout on pull requests), the `ai-native-ref-dead-links` schedule at 07:15 UTC (schedule names are unique across repositories, so not `dead-links`, the host's), the
monitor (`oracleRuns: 2`, `followUpWindow: 168h`) and the rule `low-risk: dead-links` in `.policy.yml`.
Its Flux signal is absent by design: its changes reach a cluster only through a host pin bump.

L1 here, in order:

1. Two scheduled runs of the workflow on `main`, each holding a `findings` artifact:

   ```bash
   gh run list -R Smana/ai-native-ref --workflow dead-links.yaml --branch main
   ```

2. The merger App's installation on this repository grants `actions: read` and `issues: write` (B1: the
   monitor's labels). Accept the permission update on the installation if GitHub asks.
3. Then `shadow: true` on this repository's `dead-links` entry, in
   `tooling/base/agent-factory/helm-values-configmap.yaml`.

From the rule's merge, `low-risk: dead-links` approves any agents pull request inside the class's fence
on this repository, `docs-links` and `docs` shadow pull requests included. Their shadow decisions can
then reach `would-arm` and count in the `docs-links` tally: read that tally with this in mind.
