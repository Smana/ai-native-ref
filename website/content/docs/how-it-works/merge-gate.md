---
title: The merge gate
aliases:
  - /docs/platform/ai-platform/agents/how-it-works/agents-and-merge-gate/
linkTitle: The merge gate
weight: 15
description: "Which gate status, GitHub Apps, approval rule and daily auto-merge caps this platform uses."
lastVerified: 2026-11-27
diataxis: values
---

The merge gate is the controller loop in `maku-factory` that decides whether an agent pull request
merges unattended, merges on a maintainer's approval, or waits for a human; its evaluation order,
class modes and reason codes are in Maku's
[merge gate documentation]({{< maku "docs/factory.md#the-merge-gate" >}}).

## Gate settings on this platform {#when-it-merges}

<span id="classes"></span><span id="merge-gate"></span><span id="approve-to-merge"></span><span id="approve-the-commit-you-read"></span><span id="hand-off"></span>

Example (the reference host): the shared defaults live under `spec.mergeDefaults` in
`tooling/base/agent-factory/resources/factory.yaml`, and each repository overrides its own checks and
daily cap in `tooling/base/agent-factory/resources/repository-<name>.yaml`:

| Platform setting | Value on this platform | Manifest path |
|---|---|---|
| Gate status check | `gateStatus: true`, `policyBot: false` (`maku/merge-gate` posted by the factory's gate) | `tooling/base/agent-factory/resources/factory.yaml` |
| Agents App (branch pushes and PR creation) | `ogenki-agents[bot]`, Secret `agent-factory-agents-app` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Factory App (issue narration and status) | `ogenki-agent-factory[bot]`, Secret `agent-factory-github` | `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Merger App (the only identity allowed to merge) | `ogenki-agent-merger[bot]`, `apps.merger.mode: separate`, Secret `agent-factory-merger` | `tooling/base/agent-factory/resources/factory.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Approve-to-merge | `approveToMerge: true` (one maintainer approval of the current commit triggers the merger App outside the daily cap) | `tooling/base/agent-factory/resources/factory.yaml` |
| Daily auto-merge cap (`merge.maxPerDay`) | `1` on `Smana/cloud-native-ref` (`dead-links` also sets `maxPerDay: 1`, `deps-patch` `2`), `2` on `Smana/ai-native-ref`, `3` on `Smana/image-gallery`, `5` on `Smana/runlore-kb` and `Smana/runlore` | `tooling/base/agent-factory/resources/repository-<name>.yaml` |
| CI fix runs and check re-runs | `fixRuns: 2, checkReruns: 1` on `Smana/cloud-native-ref`; `fixRuns: 1, checkReruns: 0` on the other four repositories | `tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml`, `tooling/base/agent-factory/resources/repository-ai-native-ref.yaml` |

Unlike Maku's default (`apps.merger.mode: factory` sharing one App), this platform isolates the right to
merge in a dedicated third GitHub App (`ogenki-agent-merger[bot]`) so neither the agents App nor the
factory App can merge code.

Which policies are bound in `live`, `shadow` or `disabled` mode on each repository is listed in
[Configure merge policies]({{< relref "/docs/use/guide/merge-policies.md#configuration" >}}), and the
reasons those policies can produce are listed in
[Gate reasons]({{< relref "/docs/reference/gate-reasons.md" >}}).
