---
title: Factory configuration
weight: 12
description: "The Factory, Repository, MergePolicy and Helm values set on this platform that differ from Maku's chart defaults."
lastVerified: 2026-11-27
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
| Chart policy catalog | `mergePolicies.catalog: {enabled: true, exclude: [deps-patch]}` (ships `docs-links`, `docs`; platform keeps its own `deps-patch`) | `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/resources/mergepolicy-deps-patch.yaml` |
| Factory network policy | `networkPolicies.factory.enabled: false`: the platform's own CiliumNetworkPolicy also admits the run API from the tailnet gateway and RunLore | `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/network-policy.yaml` |
| Post-merge Flux monitor RBAC | `monitor.flux.enabled: true` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| GitHub Apps and per-run git tokens | `apps.merger.mode: separate` (three Apps: `agent-factory-github`, `agent-factory-agents-app`, `agent-factory-merger`), `runTokens: {enabled: true, perRun: true}` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Ownership fence and policy stage | `config.factory: ${cluster_name}`, `config.policyManagement: {stage: manage}` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Human API and OIDC preset | `listen: ":8082"`, `preset: zitadel`, `access: {links: broker, ttl: 5m}` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Sponsored and internal principals | `slack-app` (`dailyUSD: 5`, `maxCostUSD: 2`) and `runlore` in the cluster overlays | `tooling/aws-0/agent-factory/helm-values-sponsored.yaml`, `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml` |
| Meter and throttle queries | VictoriaMetrics (`:8428`) `gen_ai_client_token_usage_sum` and VictoriaLogs (`:9428`) `reason:RateLimit` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Control issue, defaults and workflows | `control: {repository: Smana/cloud-native-ref, issue: 2188}`, `defaults: {dataClass: public, predictedClass: review, harness: opencode}`, `triage.controlPercent: 0`, `outcomes: [change, plan-first, review, report]`, `scoper.planTier: frontier` | `tooling/base/agent-factory/resources/factory.yaml`, `tooling/base/agent-factory/resources/repository-*.yaml` |
| Workflows and roles | `standard` and `careful` as stage lists, `standard` stepping up to `careful`; a custom `thorough` with a read-only `security-reviewer` role, its brief in `maku-factory.roleBriefs`. Each Repository sets `workflow.default: standard`, `stepUp` (`ask` on `cloud-native-ref`, `auto` elsewhere) and `planGate: ask` | `tooling/base/agent-factory/resources/factory.yaml`, `tooling/base/agent-factory/resources/repository-*.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Policy pull requests | `gitops: {repository: Smana/ai-native-ref, path: tooling/base/agent-factory/resources/repository-ai-native-ref.yaml}` | `tooling/base/agent-factory/resources/factory.yaml` |
| Merge defaults (`spec.mergeDefaults`) | `gateStatus: true`, `policyBot: false`, `approveToMerge: true`, `verifyFor: 30m`, `revertWindow: 168h`, `awaitingCIFor: 24h`, `breaker: {window: 10, maxReverts: 1, maxFollowUps: 1, recoverAfter: 3}` | `tooling/base/agent-factory/resources/factory.yaml` |
| Concurrency and budgets | `caps: {activeTasks: 3, concurrentRuns: 4, tasksPerDay: 20, awaitingHumanWIP: 5, preferRevisions: true}`, `budgets: {enforceTask: true, enforcePrincipal: false, factoryDailyUSD: 42.50, humanDailyUSD: 8.50, perPerson: {enabled: true}}` | `tooling/base/agent-factory/resources/factory.yaml` |

Unlike Maku's chart defaults (which bundle ClusterRoles, default `apps.merger.mode` to `factory`, and
ship all three catalog policies), this platform splits the CRD ClusterRoles out for Flux ownership,
keeps a dedicated merger App, keeps its own factory network policy, and excludes the catalog
`deps-patch` to preserve its six `protectedFiles` and Flux monitor.
