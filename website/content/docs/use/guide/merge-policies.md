---
title: "11. Configure merge policies"
linkTitle: "11. Merge policies"
weight: 11
description: "Which merge policies are bound on this platform and in which mode, where their manifests live, and how they differ from Maku's defaults."
lastVerified: 2026-11-24
diataxis: values
---

A `MergePolicy` defines a class of change the factory's merge gate can evaluate, and each `Repository`
object binds the policies it uses with a mode (`live`, `shadow` or `disabled`); every field, validation
rule, editor workflow and promotion step is in Maku's
[merge policies guide]({{< maku "docs/merge-policies.md" >}}).

## Bound policies and modes {#configuration}

<span id="where"></span><span id="change-a-class"></span><span id="starter"></span><span id="by-hand"></span><span id="editor"></span><span id="promote"></span><span id="limits"></span>

Example (the reference host): the central `Repository` objects and the chart catalog
(`mergePolicies.catalog: {enabled: true, exclude: [deps-patch]}`) decide every merge, while
`policyManagement.stage: manage` compares each repository's `.github/agent-factory.yaml`, runs dual
evaluation, and serves the Settings pages:

| Repository | `live` | `shadow` | Manifest path |
|---|---|---|---|
| `Smana/cloud-native-ref` | `docs-links`, `revert` | `alert-rules`, `dead-links`, `deps-patch`, `deps-minor`, `docs` | `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml` |
| `Smana/ai-native-ref` | — | `docs-links`, `revert`, `dead-links`, `docs` (`^website/content/.+\.md$`, 60 lines) | `tooling/base/agent-factory/resources/repository-ai-native-ref.yaml` |
| `Smana/runlore-kb` | — | `docs-links`, `revert`, `kb-entries`, `docs` | `tooling/base/agent-factory/resources/repository-runlore-kb.yaml` |
| `Smana/runlore` | — | `docs-links`, `revert`, `docs` | `tooling/base/agent-factory/resources/repository-runlore.yaml` |

<!-- example -->
| Platform setting | Value on this platform | Manifest path |
|---|---|---|
| Policy management stage | `stage: manage` (factory and broker), `operators: [Smana]` | `tooling/base/agent-factory/helm-values-configmap.yaml`, `infrastructure/base/room-broker/config.yaml` |
| Chart catalog and custom policies | Chart catalog enabled (`docs-links`, `revert`, `docs` in `shadow`; `deps-patch` excluded) plus five custom `MergePolicy` objects (`alert-rules`, `dead-links`, `deps-minor`, `deps-patch`, `kb-entries`) | `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/resources/mergepolicy-*.yaml` |
| Gate status and guardrails | `mergeDefaults: {gateStatus: true, policyBot: false}`; `mergeGuardrails.protectedFiles` protects the factory configuration, CI gates and platform paths. Caps are unset, so Maku's defaults hold: at most 10 files, 300 lines and 5 merges/day | `tooling/base/agent-factory/resources/factory.yaml` |
| Ownership fence and repo mirror | `factory: <active-cluster>` in every served repository ([active cluster]({{< relref "/docs/status.md#clusters" >}})); `cloud-native-ref` also mirrors its bindings under `mergePolicies:` | `.github/agent-factory.yaml` |

Maku's own defaults are `policyManagement.stage: manage` and an enabled chart catalog. This platform
excludes the catalog's `deps-patch` because its custom `deps-patch` object adds the host's protected
paths and Flux monitor. It also keeps `cloud-native-ref` as the only repository with `live` unattended
merges (`docs-links` and `revert`) gated by `maku/merge-gate`.
