---
title: Factory configuration
weight: 12
description: "Where each factory setting lives: the Factory, Repository and MergePolicy objects the factory reads live, and the values file that keeps the plumbing and the startup switches. Which edit applies at once and which needs a rollout."
---

The factory reads its configuration from two places. Three Kubernetes objects hold what you change
often: the catalogue, the repositories and their merge policies. The factory reads them live, so an
edit applies on its next decision with no restart. The Helm values file holds the plumbing and the
startup switches, which the factory reads once when it starts.

## Where each setting lives {#where}

| Setting | Where | Applies |
|---|---|---|
| The catalogue: `control`, `defaults`, `triage.controlPercent`, `tiers`, `templates`, `caps`, `budgets`, `facts`, `brief`, `resume`, `loops`, `harnessProfiles`, and the price table (`prices`, read as `meter.prices`) | The `Factory`, `tooling/base/agent-factory/resources/factory.yaml` | Live |
| A repository: its maintainers, trigger label, check egress and schedules | One `Repository` per repository, `tooling/base/agent-factory/resources/repository-<name>.yaml` | Live |
| A repository's classes and merge rules | One `MergePolicy` per `Repository`, `tooling/base/agent-factory/resources/mergepolicy-<name>.yaml` | Live |
| The factory's name, `policyManagement`, `api`, `broker`, `github`, `meter`'s queries and URLs, `poll`, `tracing`, the bot logins, `roomsURL` | `config:` in `tooling/base/agent-factory/helm-values-configmap.yaml` | At the next rollout |
| The API's sponsored and internal principals | `config.api` in each cluster's `tooling/<cluster>/agent-factory/helm-values-sponsored.yaml` | At the next rollout |

Adding a repository is a new `Repository` and its `MergePolicy`: the factory connects to it on its next
read. Removing both stops the factory serving that repository, and its tasks wait until it is served
again. The exception is the last repository: the factory then has nothing servable, so it keeps
serving the current configuration until it restarts, and a restart then waits, not Ready.

The three objects live in the factory's namespace, `agent-system`. A Flux Kustomization of their own,
`agent-factory-resources`, applies them, apart from the factory's HelmRelease: their CRDs come with
the factory's chart. The `Factory` is named after the factory, and every `Repository` names it in
`factoryRef`. Here both are the cluster's name, `${cluster_name}`, which Flux substitutes.

Every file in `tooling/base/agent-factory/` is a gate path in `.policy.yml`: an agent never changes
the factory's policy, and a maintainer merges each edit.

## Live fields and fields that need a rollout {#live}

| Live: the next decision reads it | Startup: a rollout reads it |
|---|---|
| Everything in the `Factory`, every `Repository` and `MergePolicy`, adding or removing a repository | `factory`, `policyManagement`, `coordination`, `hardening`, `api`, `runs`, `sandbox`, `broker`, `github`, `meter.url`, `meter.query`, `meter.logsURL`, `meter.throttleQuery`, `poll`, `tracing`, `factoryLogin`, `agentsLogin`, `roomsURL`, `runlore.listen`, `triage.classifierURL` |

A change to the values file reaches the factory as a Helm upgrade, which restarts its pods. Maku's
[architecture](https://github.com/Smana/maku/blob/main/docs/architecture.md#live-fields-and-fields-that-need-a-rollout)
has the same table with how the factory reads each side.

## When the factory refuses an edit {#refused}

The factory checks every object against the rest of the configuration, as it checks the file. An edit
it refuses is marked `Accepted=False` with the reason. The last version it accepted keeps serving,
while the factory runs.

After a restart, an object that is still invalid is not served. A factory with nothing to serve, no
repository among the file and the objects, waits at startup: its pods run and answer their probes but
are not Ready, and it starts serving as soon as the objects exist (Maku v0.41.1 and later). So the
objects and the factory can be applied in either order, and a refused edit is fixed, or reverted,
before the next rollout.

`task check` refuses such an edit before it merges: `scripts/ci/validate-factory-config.sh` runs
`maku config validate`, from the release the HelmRelease pins, on the values file and the objects of
each cluster.

## See what the factory serves {#status}

```bash
kubectl get factory,repository,mergepolicy -n agent-system
```

Each object reports `Accepted`. A `Repository` also reports `Connected`, its GitHub connection, and a
`MergePolicy` reports each class's mode (`live`, `shadow` or `unarmed`) and its last decision. The
`Factory` reports `Ready`. Every condition and reason is in Maku's
[merge policies guide](https://github.com/Smana/maku/blob/main/docs/merge-policies.md#status).

To change a class, see [Configure merge policies]({{< relref "/docs/use/guide/merge-policies.md#change-a-class" >}}).
