---
title: Factory configuration
weight: 12
description: "The Factory, Repository, MergePolicy and Helm values set on this platform that differ from Maku's chart defaults."
lastVerified: 2026-11-15
diataxis: values
---

`maku-factory` reads its live catalogue, repository bindings and merge policies from `Factory`,
`Repository` and `MergePolicy` objects and its startup plumbing from the Helm values file; every
configuration key, default and status condition is in Maku's
[configuration reference]({{< maku "docs/reference/config.md" >}}),
[architecture guide]({{< maku "docs/architecture.md#live-fields-and-fields-that-need-a-rollout" >}})
and [merge policies guide]({{< maku "docs/merge-policies.md#status" >}}).

## Values that differ from Maku's defaults {#where}

<span id="live"></span><span id="refused"></span><span id="status"></span>

Example (the reference host): `scripts/ci/validate-factory-config.sh` validates the assembled
manifests in `tooling/base/agent-factory/` and each cluster overlay with `maku config validate` on
every `task check`:

| Setting | Value on this platform | Manifest path |
|---|---|---|
| Shared ClusterRoles | `clusterRoles: false` (rendered once by `agent-factory-crds` instead) | `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/crds/helmrelease.yaml` |
| Chart policy catalog | `mergePolicies.catalog: {enabled: true, exclude: [deps-patch]}` (ships `docs-links`, `revert`, `docs`; platform keeps its own `deps-patch`) | `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/resources/mergepolicy-deps-patch.yaml` |
| Post-merge Flux monitor RBAC | `monitor.flux.enabled: true` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| GitHub Apps and per-run git tokens | `apps.merger.mode: separate` (three Apps: `agent-factory-github`, `agent-factory-agents-app`, `agent-factory-merger`), `runTokens: {enabled: true, perRun: true}` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Ownership fence and policy stage | `config.factory: ${cluster_name}`, `config.policyManagement: {stage: manage}` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Human API and OIDC preset | `listen: ":8082"`, `preset: zitadel`, `access: {links: broker, ttl: 5m}` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Sponsored and internal principals | `slack-app` (`dailyUSD: 5`, `maxCostUSD: 2`) and `runlore` in the cluster overlays | `tooling/aws-0/agent-factory/helm-values-sponsored.yaml`, `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml` |
| Meter and throttle queries | VictoriaMetrics (`:8428`) `gen_ai_client_token_usage_sum` and VictoriaLogs (`:9428`) `reason:RateLimit` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Control issue, defaults and workflows | `control: {repository: Smana/cloud-native-ref, issue: 2188}`, `defaults: {dataClass: public, workflow: standard}`, `triage.controlPercent: 0`, `workflows: {quick, standard, careful}`, `templates.pair.reviewerModel: kimi-frontier` | `tooling/base/agent-factory/resources/factory.yaml` |
| Merge defaults (`spec.mergeDefaults`) | `gateStatus: true`, `policyBot: false`, `approveToMerge: true`, `verifyFor: 30m`, `revertWindow: 168h`, `awaitingCIFor: 24h`, `breaker: {window: 10, maxReverts: 1, maxFollowUps: 1, recoverAfter: 3}` | `tooling/base/agent-factory/resources/factory.yaml` |
| Concurrency, budgets and loops | `caps: {activeTasks: 3, concurrentRuns: 4, tasksPerDay: 20, awaitingHumanWIP: 5, preferRevisions: true}`, `budgets: {enforceTask: true, enforcePrincipal: false, factoryDailyUSD: 42.50, humanDailyUSD: 8.50, perPerson: {enabled: true}}`, `loops: {default: {scope: "off"}}` (`careful` uses Maku's shipped scoper, splitter and search defaults) | `tooling/base/agent-factory/resources/factory.yaml` |

Unlike Maku's chart defaults (which bundle ClusterRoles, default `apps.merger.mode` to `factory`, and
ship all four catalog policies), this platform splits the CRD ClusterRoles out for Flux ownership,
keeps a dedicated merger App, excludes the catalog `deps-patch` to preserve its six `protectedFiles`
and Flux monitor, and sets `templates.pair.reviewerModel: kimi-frontier` in
`tooling/base/agent-factory/resources/factory.yaml`.
