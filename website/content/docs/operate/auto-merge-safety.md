---
title: Run auto-merge safely
linkTitle: Auto-merge safety
weight: 15
description: "The revert breaker, post-merge monitor, drill labels, alerts and Renovate adoption configured on this platform."
lastVerified: 2026-11-15
diataxis: values
---

Maku bounds unattended merges with a post-merge monitor, a revert and regression circuit breaker, a
drill label, and optional adoption of bot-authored pull requests; how the breaker, drills, recovery and
adopted classes work is in Maku's
[post-merge monitor and breaker documentation]({{< maku "docs/factory.md#the-post-merge-monitor" >}}).

## Safety and adoption values on this platform {#go-live}

<span id="revert"></span><span id="breaker"></span><span id="drills"></span><span id="recovery"></span><span id="after-a-merge"></span><span id="metrics"></span><span id="adopted-classes"></span>

Example (the reference host): the shared breaker and verification windows live in
`tooling/base/agent-factory/resources/factory.yaml`, and per-class monitors and adopted authors live in
`tooling/base/agent-factory/resources/mergepolicy-*.yaml`:

| Platform setting | Value on this platform | Manifest path |
|---|---|---|
| Post-merge CI watch and revert window | `verifyFor: 30m`, `revertWindow: 168h`, `awaitingCIFor: 24h` | `tooling/base/agent-factory/resources/factory.yaml` |
| Circuit breaker (`mergeDefaults.breaker`) | `{window: 10, maxReverts: 1, maxFollowUps: 1, recoverAfter: 3}` | `tooling/base/agent-factory/resources/factory.yaml` |
| Revert and drill labels | `factory/revert` (triggers a merger revert PR) and `factory/drill` (applied before `factory/revert` so the breaker skips the drill) | `tooling/base/agent-factory/resources/factory.yaml` |
| Flux reader for post-merge monitors | `monitor.flux.enabled: true`, `merge.fluxSource: flux-system/flux-system` on `Smana/cloud-native-ref` | `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml` |
| Class monitors (`spec.monitor`) | `dead-links`: `{oracleRuns: 2, followUpWindow: 168h}`; `deps-patch` and `deps-minor`: `{flux: {within: 1h}, followUpWindow: 168h}`; `alert-rules`: `{verification: {within: 2h}, followUpWindow: 2h}` | `tooling/base/agent-factory/resources/mergepolicy-dead-links.yaml`, `tooling/base/agent-factory/resources/mergepolicy-deps-patch.yaml`, `tooling/base/agent-factory/resources/mergepolicy-deps-minor.yaml`, `tooling/base/agent-factory/resources/mergepolicy-alert-rules.yaml` |
| Adopted Renovate policies (`author.adopt`) | `deps-patch` (`semver-patch`, `maxPerDay: 2`) and `deps-minor` (`semver-minor`), matching `logins: ["renovate[bot]"]`, `branches: ['^renovate/']`, `maxPatchFiles: 3`, `maxModifiedLines: 10`, `releaseAgeCheck: renovate/stability-days`, bound `shadow` on `Smana/cloud-native-ref` | `tooling/base/agent-factory/resources/mergepolicy-deps-patch.yaml`, `tooling/base/agent-factory/resources/mergepolicy-deps-minor.yaml`, `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml` |
| Adopted RunLore KB policy | `kb-entries` (`logins: ["runlore[bot]"]`, `branches: ["^runlore/kb-"]`, `diffShape: added-entry`, `maxPerDay: 5`), bound `shadow` on `Smana/runlore-kb` | `tooling/base/agent-factory/resources/mergepolicy-kb-entries.yaml`, `tooling/base/agent-factory/resources/repository-runlore-kb.yaml` |
| Auto-merge alert rules | `AgentFactoryAutoMergeReverted`, `AgentFactoryMergeRegression`, `AgentFactoryClassPausedLong`, `PolicyBotUnavailable` | `observability/base/agent-platform/vmrule-agent-factory.yaml` |

Unlike Maku's defaults (which leave `breaker`, `monitor.flux`, and `author.adopt` unset), this platform
pauses any live class on a single revert or follow-up fix within its last 10 merges until 3 mature
clean merges follow, and shadows Renovate's patch and minor pull requests behind a 3-file, 10-line
fence and `renovate/stability-days` check while excluding ZITADEL, Crossplane core, Gateway API and
VictoriaMetrics values paths.
