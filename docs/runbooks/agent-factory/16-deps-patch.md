# 16 — The `deps-patch` class: shadow, then the drill

Brings the merge gate's `deps-patch` class from declared and off to shadow, then, on the owner's go,
to one live drill. Design: [merge gate classes](../../superpowers/specs/2026-10-22-merge-gate-classes-design.md)
(MC10 to MC12). The class takes Renovate's pull requests (patch bumps of Flux-deployed YAML: at most
3 files and 10 lines, Renovate's stability days, 2 a day) and `deps-minor` sits beside it, shadow
only. Both are declared on the host with no `live` or `shadow` key: until a session writes one, they
adopt nothing and decide nothing. See [README.md](README.md) for `CLOUD`.

## 1. Prerequisites

- [ ] Maku v0.22.0 or later pinned (`flux/sources/ocirepo-agent-factory.yaml`): the adopted
  classes (`author.adopt`, `semver-patch`, `semver-minor`, `releaseAgeCheck`).
- [ ] The host's `renovate` policy rule carries the gate list (cloud-native-ref PR I) on its `main`.
- [ ] The merger App is installed with pull requests, contents and checks read on the host, and
  `issues: write` on both repositories (B1, an owner action: GitHub, the App's installation,
  Permissions). `factory/merged:deps-patch` and the outcome labels are written in shadow too, and a
  missing permission only logs, so check it before the session.
- [ ] The factory's token can read organisation membership. This matters only on an organisation-owned
  repository (a reviewer's association is read from it); the Smana repositories are user-owned.
- [ ] The Flux ClusterRole is rendered on gcp-0:

  ```bash
  kubectl auth can-i list helmreleases.helm.toolkit.fluxcd.io \
    --as system:serviceaccount:agent-system:agent-factory -A
  ```

  Expected: `yes`.

## 2. Shadow (L3)

One commit, at the rebuild (M3): `deps-patch: {…, shadow: true}` and `deps-minor: {…, shadow: true}`
on the host's entries in `tooling/base/agent-factory/helm-values-configmap.yaml`. Renovate keeps
merging meanwhile (MC12). An adopted Task runs no agent, costs nothing and fills no factory cap.

| # | Do | Expected reading |
|---|---|---|
| 1 | Wait for the next eligible Renovate PR | An adopted Task: `kubectl -n agent-system get tasks -o wide \| grep adopt` |
| 2 | Read the PR before Renovate merges it | A `would-arm head=<sha>` comment |
| 3 | Read the PR after the merge | The label `factory/merged:deps-patch` |
| 4 | Read the monitor within 2 h | A `flux:` reading (`healthy`, `regression` or `inconclusive`) |
| 5 | `scripts/shadow-merge-tally.sh --class deps-patch --author app/renovate` | The PR counts as `merged_unchanged` (Renovate's own automerge of the judged head) |

Record how many eligible PRs Renovate merged before the factory decided: they are not counted.

## 3. The drill (L4)

On the owner's go, after 20 shadow decisions merged unchanged and 0 bad mature.

1. Cloud-native-ref PR K (the switch) is merged first. The ai-native-ref commit that follows bumps
   `HOST_REF` to PR K's merge (L12).
2. `deps-patch: {…, live: true}` in the same commit. `deps-minor` stays `shadow: true`: the config
   refuses it `live`.
3. The next patch PR is merged by the merger at its head (the merge is pinned by `ExpectedHeadOid`);
   the monitor reads `main: healthy` and `flux: healthy`.
4. Label that PR `factory/revert`: the revert PR opens and merges (once PR K's revert rule is live),
   and the next decision reads `class_paused`.
5. Back to `shadow: true`, unless the owner keeps the class live.

## 4. What fails closed

No merge, and no adoption where the shape or the fence fails:

- a lockfile, a digest-only update (a digest may change only when attached to the moved version), a
  minor in `deps-patch`, a gate path, a protected file, a fourth file, an 11th line;
- a fork, a release younger than the stability days, a human's commit or push on the branch, a
  maintainer's approval, a stability status by anyone but Renovate;
- a `CHANGES_REQUESTED` from a repository member or collaborator, a truncated review list, a dismissed
  review or a reviewer GitHub no longer shows;
- a Renovate push after the decision (GitHub refuses the pinned merge); Renovate's next head is decided
  again, at most 3 times.

## 5. Afterwards

Back to the declared-off state or to `shadow: true` (the session's last commit); the owner decides
whether `deps-patch` stays live.
