# 15 — The `dead-links` class: shadow, then the drill

Brings the merge gate's `dead-links` class from declared and off to shadow, then, on the owner's go, to
one live drill. Design: [merge gate classes](../../superpowers/specs/2026-10-22-merge-gate-classes-design.md)
(MC1 to MC14). The class is declared on both repositories and has no `live` or `shadow` key: until a
session writes one, it has no intake and takes no decision. See [README.md](README.md) for `CLOUD`.

## 1. Prerequisites

- [ ] agent-platform v0.19.0 or later pinned (`flux/sources/ocirepo-agent-factory.yaml`): the
  vocabulary (`allowedFiles`, `protectedFiles`, `modifyOnly`, `maxModifiedLines`, `diffShape`,
  `holdoutChecks`, `oracle`) and the `dead-links` probe.
- [ ] The host's `dead-links` workflow (`.github/workflows/dead-links.yaml`) has run on `main` twice,
  each run holding a `findings` artifact (written by `.github/scripts/dead-links/findings.py`):

  ```bash
  gh run list -R Smana/cloud-native-ref --workflow dead-links.yaml --branch main
  ```

- [ ] The merger App's `actions` permission holds ([runbook 12's mint test](12-live-auto-merge-drill.md#the-mint-test)).
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
3. The merger merges at the head the checks ran on. After the post-merge monitor's release, its verdict.
4. Label the merge `factory/revert`: the revert merges, and the next decision reads `class_paused`.
5. Back to `shadow: true`.

## 4. What fails closed

No task is created for: a failed scan run, a pull request run, a stranger's dispatch, a finding in one
run only, an http target, a protected file, a URL in prose or a code block. An unreadable artifact
(egress, permission) makes the tick error
(`agent_factory_intake_errors_total{source="schedule"}`) and creates nothing.
