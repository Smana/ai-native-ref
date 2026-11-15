---
title: "11. Configure merge policies"
linkTitle: "11. Merge policies"
weight: 11
description: "Which merge policies are bound on this platform and in which mode, where their manifests live, and how they differ from Maku's defaults."
lastVerified: 2026-11-15
diataxis: values
---

A `MergePolicy` defines a class of change the factory's merge gate can evaluate, and each `Repository`
object binds the policies it uses with a mode (`live`, `shadow` or `disabled`); every field, validation
rule, editor workflow and promotion step is in Maku's
[merge policies guide]({{< maku "docs/merge-policies.md" >}}).

## Bound policies and modes {#configuration}

<span id="where"></span><span id="change-a-class"></span><span id="starter"></span><span id="by-hand"></span><span id="editor"></span><span id="promote"></span><span id="limits"></span>

Example (the reference host): the central `Repository` objects decide every merge, while
`policyManagement.stage: manage` compares each repository's `.github/agent-factory.yaml`, runs dual
evaluation, and serves the Settings pages:

| Repository | `live` | `shadow` | `disabled` | Manifest path |
|---|---|---|---|---|
| `Smana/cloud-native-ref` | `docs-links`, `revert` | `alert-rules`, `dead-links`, `deps-patch`, `deps-minor` | `docs`, `tests`, `dashboards`, `scripts`, `review` | `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml` |
| `Smana/ai-native-ref` | — | `docs-links`, `revert`, `dead-links` | `docs`, `tests`, `dashboards`, `scripts` | `tooling/base/agent-factory/resources/repository-ai-native-ref.yaml` |
| `Smana/runlore-kb` | — | `docs-links`, `revert`, `kb-entries` | — | `tooling/base/agent-factory/resources/repository-runlore-kb.yaml` |
| `Smana/runlore` | — | `docs-links`, `revert` | — | `tooling/base/agent-factory/resources/repository-runlore.yaml` |

<!-- example -->
| Platform setting | Value on this platform | Manifest path |
|---|---|---|
| Policy management stage | `stage: manage` (factory and broker), `operators: [Smana]` | `tooling/base/agent-factory/helm-values-configmap.yaml`, `infrastructure/base/room-broker/config.yaml` |
| Reusable policy definitions | Twelve `MergePolicy` objects (`alert-rules`, `dashboards`, `dead-links`, `deps-minor`, `deps-patch`, `docs-links`, `docs`, `kb-entries`, `revert`, `review`, `scripts`, `tests`) | `tooling/base/agent-factory/resources/mergepolicy-docs-links.yaml` (and sibling `mergepolicy-*.yaml` files) |
| Central guardrails | Unset (Maku's defaults hold: `.github/`, `.policy.yml` and `CODEOWNERS` protected; at most 10 files, 300 lines and 5 merges/day) | `tooling/base/agent-factory/resources/factory.yaml` |
| Ownership fence and repo mirror | `factory: <active-cluster>` in every served repository ([active cluster]({{< relref "/docs/status.md#clusters" >}})); `cloud-native-ref` also mirrors its bindings under `mergePolicies:` | `.github/agent-factory.yaml` |
| policy-bot rules | One `low-risk:` rule per unattended class | `.policy.yml` |

Example (the reference host), from `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml`:

```yaml
spec:
  mergePolicies:
    - {name: docs-links, mode: live, holdoutChecks: ["Check the documentation links 🔗"]}
    - {name: revert, mode: live, holdoutChecks: ["Check the documentation links 🔗"]}
    - {name: docs, mode: disabled}
    - name: dead-links
      mode: shadow
      allowedFiles: ['^(docs|website/content)/.+\.md$']
      oracleWorkflow: dead-links.yaml
```

Unlike Maku's default (`policyManagement.stage` off, only the two starter policies), this platform
runs `stage: manage` with central authority (`classAuthority: central`) and binds `docs-links` and
`revert` as `live` on `Smana/cloud-native-ref` only, keeping every other repository in `shadow` or
`disabled` until its shadow cohort reaches 20 clean decisions.

**Next:** keep the [cheat sheet]({{< relref "cheat-sheet.md" >}}) at hand.
