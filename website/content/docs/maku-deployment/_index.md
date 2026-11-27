---
title: Maku on Cloud Native Ref
linkTitle: Maku on CNR
weight: 30
diataxis: values
description: "How ai-native-ref deploys Maku via the agent-platform Flux umbrella on Cloud Native Reference: pinned host seams, active policies, and day-2 operations."
lastVerified: 2026-11-27
---

This repository deploys [Maku](https://maku.ogenki.io/) on [Cloud Native Reference](https://cnref.ogenki.io/) as the `agent-platform` Flux umbrella (`clusters/aws-0-agent-platform/` and `clusters/gcp-0-agent-platform/`). For Maku's product guides, installation on any Kubernetes cluster, user guide, architecture, and reference, see [maku.ogenki.io](https://maku.ogenki.io/) — [Quickstart]({{< maku "get-started/quickstart/" >}}), [User guide]({{< maku "guide/" >}}), [Install]({{< maku "install/" >}}), and [Operate]({{< maku "operate/" >}}).

## Host seams pinned here {#seams}

| Seam | Choice on this host | Manifest path |
|---|---|---|
| **Flux umbrella** | `agent-platform` child Kustomizations, pinned Maku OCI charts and image digests | `tooling/base/agent-factory/helm-values-configmap.yaml`, `infrastructure/base/room-broker/helmrelease.yaml` |
| **Database** | CloudNativePG `SQLInstance` (`xplane-rooms` in `agent-system`), WAL archived to object storage | `infrastructure/base/room-broker/sqlinstance.yaml` |
| **Identity & exposure** | ZITADEL OIDC (`rooms-proxy`, `agents-member`, `agents-admin`) behind `oauth2-proxy` on the Tailscale Gateway | `infrastructure/base/room-broker/config.yaml` |
| **Model gateway** | `maku-gateway` (`agentgateway`) with `public` (Z.ai, Kimi, Mistral) and `internal` (Anthropic) listeners + `agent-ratelimit` | `infrastructure/base/agent-gateway/model-gateway/helmrelease.yaml` |
| **Secrets** | Dedicated OpenBao `agents` mount (GitHub Apps, provider API keys, Slack tokens) isolated from `openbao-platform` | `security/base/agent-secrets/` |
| **Sandbox runtime** | `maku-run-controller` scheduling gVisor pods on dedicated spot `agents-gvisor` pools + default-deny Cilium egress | `infrastructure/base/runtimeclass-gvisor/` |
| **Observability** | Shared VictoriaMetrics, VictoriaLogs, VictoriaTraces (behind `agent-traces-collector`), and Grafana dashboards | `observability/base/agent-platform/` |

## Active policies and upkeep routines {#policies}

- **Merge policies:** chart catalog enabled (`docs-links`, `docs`; custom `deps-patch`, `deps-minor`, `dead-links`, `alert-rules`, `kb-entries`) with `policyManagement.stage: manage` and `maku/merge-gate` (`tooling/base/agent-factory/resources/`). Only `docs-links` on `cloud-native-ref` runs `live`; all other bindings run `shadow` ([Merge policies]({{< maku "use/merge-policies/" >}})).
- **Upkeep routines:** six starter `Routine` objects enabled in the catalog (`routines.catalog.enabled: true`) with `routines.uiWrite: false` so repository bindings stay GitOps-managed ([Upkeep routines]({{< maku "use/upkeep-routines/" >}})).
- **Single-owner fence:** `.github/agent-factory.yaml` pins `factory:` to the single active cluster ([Status]({{< relref "/docs/status.md#clusters" >}})).

## Operating this deployment {#operate}

{{< cards >}}
  {{< card link="day-2/" title="Day-2 operations" icon="shield-check" subtitle="Kill switch, upgrading pinned Maku releases, restoring xplane-rooms, and switching the active cluster." >}}
  {{< card link="/docs/reference/host-contract/" title="Host contract" icon="link" subtitle="What Cloud Native Reference guarantees and how to resume the umbrellas." >}}
  {{< card link="/docs/status/" title="Reference deployment status" icon="map" subtitle="Active cluster, pinned Maku release, and live validation runbooks." >}}
{{< /cards >}}
