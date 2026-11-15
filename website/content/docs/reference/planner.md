---
title: Planner settings
weight: 17
description: "The planner model, gateway route, repository allowlist, class table and coordination mode configured on this platform."
lastVerified: 2026-11-15
diataxis: values
---

The room broker's governed planner (`human.intake.plan`) turns a natural-language request from Slack or
a coding agent into a validated issue plan bounded by a repository allowlist and a class table; every
planner and coordination key is in Maku's
[configuration reference]({{< maku "docs/reference/config.md#broker-configuration" >}}) and
[multi-repository guide]({{< maku "docs/multi-repository.md" >}}).

## Planner values on this platform {#classes}

<span id="coordination"></span><span id="never"></span>

Example (the reference host): the shared planner definition lives in
`infrastructure/base/room-broker/config.yaml`, and the cluster overlays switch it on for the served
public repositories:

<!-- example -->
| Setting | Value on this platform | Manifest path |
|---|---|---|
| Enabled switch (`human.intake.plan.enabled`) | `false` in base; `true` in the cloud overlays | `infrastructure/base/room-broker/config.yaml`, `infrastructure/aws-0/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` |
| Gateway route and token (`url`, `apiKeyFile`) | `http://model-gateway.agent-gateway.svc.cluster.local:8082/clients/planner/v1`, projected ServiceAccount token at `/var/run/secrets/maku/model-gateway/planner` (audience `maku-gateway.client.planner`) | `infrastructure/base/room-broker/config.yaml`, `infrastructure/base/room-broker/helmrelease.yaml` |
| Model, reasoning effort and deadline | `model: tier-frontier` (mapped to Z.ai `glm-5.3` on the gateway's `clients` listener), `reasoningEffort: low`, `deadline: 20s` | `infrastructure/base/room-broker/config.yaml`, `infrastructure/base/agent-gateway/model-gateway/helmrelease.yaml` |
| Daily cap and fallback | `dailyPlans: 50` per user per UTC day, `fallback: "off"` | `infrastructure/base/room-broker/config.yaml` |
| Repository allowlist (`repositories`) | `[Smana/ai-native-ref, Smana/runlore-kb, Smana/runlore, Smana/cloud-native-ref]` in base and `infrastructure/aws-0/room-broker/config.yaml`; `[Smana/ai-native-ref]` in `infrastructure/gcp-0/room-broker/config.yaml` | `infrastructure/base/room-broker/config.yaml`, `infrastructure/aws-0/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` |
| Class table (`classes`) | `docs-links` (`[scoper, implementer, reviewer]`, `$2.00`), `docs` (`[scoper, implementer, reviewer]`, `$2.00`), `scripts` (`[scoper, implementer, reviewer]`, `$5.10`), `review` (`[implementer, reviewer]`, `$2.00`) | `infrastructure/base/room-broker/config.yaml` |
| Multi-repository coordination (`coordination.mode`) | `off` in base; `plan` in `infrastructure/aws-0/room-broker/config.yaml` (`maxRepositories: 2`, `dailyPlans: 10`) | `infrastructure/aws-0/room-broker/config.yaml` |

Unlike Maku's defaults (`human.intake.plan.enabled: false`, `reasoningEffort` unset, `coordination.mode: off`),
this platform sets `reasoningEffort: low` so Z.ai `glm-5.3` finishes within the 20-second planner
deadline, prices `docs-links`, `docs` and `review` at a $2.00 ceiling and `scripts` at the `standard`
tier's $5.10 `taskUSD`, and enables two-repository `coordination.mode: plan` in the AWS overlay.
