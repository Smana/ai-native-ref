---
title: Day-2 operations
linkTitle: Day-2 operations
weight: 25
description: "Operate Maku on this host: stop the factory in an emergency, upgrade the pinned release, restore the room database, and switch the active cluster."
lastVerified: 2026-11-15
diataxis: how-to
---

Routine and emergency procedures for operating Maku on this host: stopping every run, bumping the
pinned release, restoring the room log across a cluster rebuild, and switching which cluster owns
intake.

## Stop everything {#stop-everything}

Create the `agent-factory-stop` ConfigMap in `agent-system` to engage the cluster kill switch:

```bash
kubectl create configmap agent-factory-stop -n agent-system
```

That single object pauses issue, Slack and API intake across every served repository, refuses new
`AgentRun` objects, and revokes running tasks from outside their sandboxes. Remove the ConfigMap when
you are ready to resume normal intake:

```bash
kubectl delete configmap agent-factory-stop -n agent-system
```

If you cannot reach the cluster API, apply the stop label on the pinned control issue on GitHub so the
factory stops itself on its next poll. If a GitHub App key is suspected compromised, suspend the
`ogenki-agents` or `ogenki-agent-merger` App installation in GitHub settings to cut git writes at
GitHub's edge immediately.

See Maku's [escalated tasks and the kill switch]({{< maku "docs/operations/failures.md#escalated-tasks-and-the-kill-switch" >}})
and [runbook 09 (App key compromise)](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/09-app-key-compromise.md).

## Upgrade Maku {#upgrade-maku}

Every Maku artifact on this platform is pinned by version and digest in git so Flux never deploys a
moving tag:

| Artifact | Path in this repository |
|---|---|
| Factory image and startup config | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Factory chart and CRDs chart | `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/crds/ocirepository.yaml` |
| Room broker, run-controller, harness, bridge and schema | `infrastructure/base/room-broker/ocirepository.yaml`, `infrastructure/base/room-broker/helmrelease.yaml`, `infrastructure/base/room-broker/crd-rooms.yaml`, `infrastructure/base/room-broker/sqlinstance.yaml` |
| Model gateway chart and Slack app | `infrastructure/base/agent-gateway/model-gateway/ocirepository.yaml`, `tooling/base/agent-factory/slack-app/deployment.yaml` |
| Documentation pin and host commit | `website/hugo.yaml` (`params.makuVersion`), `HOST_REF` |

Running `task check` composes both cloud overlays against the `cloud-native-ref` commit in `HOST_REF`
and validates Kustomize, Helm and PromQL outputs. It also loads the factory configuration and merge
policies through Maku's strict parser, checks that chart, CRD and image pins agree, and runs the
documentation gates. Live verification on the active cluster is recorded in the runbook's results table
under `docs/runbooks/agent-factory/` and summarized on the
[status page]({{< relref "/docs/status.md" >}}).

Follow this checklist on every Maku upgrade:

1. Bump the chart and image digests (`tooling/base/agent-factory/helm-values-configmap.yaml`,
   `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/crds/ocirepository.yaml`, and
   the broker, gateway and Slack pins) together with `params.makuVersion` in `website/hugo.yaml`.
2. Re-read the three merge-policy values pages —
   [merge policies]({{< relref "/docs/use/guide/merge-policies.md" >}})
   (`website/content/docs/use/guide/merge-policies.md`),
   [the merge gate]({{< relref "/docs/how-it-works/merge-gate.md" >}})
   (`website/content/docs/how-it-works/merge-gate.md`) and
   [run auto-merge safely]({{< relref "/docs/operate/auto-merge-safety.md" >}})
   (`website/content/docs/operate/auto-merge-safety.md`) — against `tooling/base/agent-factory/resources/`
   so no statement drifts across the release.
3. Run `task check` locally and confirm every pin, schema and site-contract guard exits zero before
   opening the pull request.
4. Once the new release reconciles and passes its live check on the active cluster, update
   `lastVerified` on `website/content/docs/status.md`.

See Maku's [upgrades]({{< maku "docs/operations/rooms.md#upgrades" >}}) and
[runbook 11 (end-to-end validation)](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/11-v1-validation.md).

## Restore {#restore}

The room broker stores every room, event, handoff and GitHub account link in PostgreSQL (`xplane-rooms`
in `agent-system`, declared in `infrastructure/base/room-broker/sqlinstance.yaml`). CloudNativePG takes
daily base backups and archives WAL segments continuously to the cluster's object-storage backup bucket.

Before tearing a cluster down, promote a verified backup seed to the `rooms-pre-destroy` alias so the
rebuilt cluster's `objectStoreRecovery` boots with the existing rooms intact. On a running cluster you
can also promote a seed without moving the alias and restore it into a scratch namespace to inspect
records or measure recovery time.

A rebuild loses three things if they were not captured beforehand:

- Room events written after the last promoted seed (or after the last archived WAL segment if the
  cluster died without a planned teardown).
- Unpushed files inside ephemeral run sandboxes in `agents`; commits already pushed to `agent/**`
  branches remain on GitHub.
- Cloud-local OpenBao secrets when bootstrapping onto a new KMS lineage, until the owner re-seeds the
  GitHub App, model provider and Slack keys.

See Maku's [backups and rebuilds]({{< maku "docs/operations/rooms.md#backups-and-rebuilds" >}}) and
[runbook 13 (rooms database restore)](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/13-rooms-restore.md).

## Switch the active cluster {#switch-the-active-cluster}

The two host clusters alternate so the platform stays proven on both clouds, and only one cluster runs
the factory at a time. Each served repository names the active cluster in `.github/agent-factory.yaml`
(`factory: <cluster>`), and a factory controller ignores any repository whose fence names another
cluster.

To hand intake from one cluster to the other:

1. Drain active runs on the outgoing cluster (`kubectl get agentruns.maku.ogenki.io -n agents`) or pause
   intake with `agent-factory-stop` until in-flight runs finish.
2. Update `factory:` in `.github/agent-factory.yaml` and update `activeCluster:` plus the `Active:` line
   under [Clusters]({{< relref "/docs/status.md#clusters" >}}) on `website/content/docs/status.md` in
   the same commit; `scripts/ci/check-site-contract.py` refuses one without the other.
3. Flip `.github/agent-factory.yaml` in the other served repositories and switch the Flux umbrella
   `suspend` flags on the host repository so the incoming cluster reconciles `agent-platform`.

See Maku's [factory operations]({{< maku "docs/operations/factory.md" >}}) and
[runbook 00 (cluster setup and teardown)](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md#runbook-00-one-time-cluster-setup).
