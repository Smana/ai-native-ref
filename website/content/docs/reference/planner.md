---
title: Planner settings
weight: 17
description: "The planner model, gateway route, live factory catalog lookup and coordination mode configured on this platform."
lastVerified: 2026-11-15
diataxis: values
---

The room broker's governed planner (`human.intake.plan`) turns a natural-language request from Slack or
a coding agent into a validated issue plan bounded by the factory's live catalog of served public
repositories and workflows; every planner and coordination key is in Maku's
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
| Repositories and workflows (`GET /v1/catalog`) | Read live from the factory's `GET /v1/catalog` endpoint: served public repositories, their default workflow (`standard`), the three workflows (`quick`, `standard`, `careful`), their roles and their `taskUSD` ceilings (`$5.10` on `quick` and `standard`, `$13.60` on `careful`) | `tooling/base/agent-factory/resources/factory.yaml`, `tooling/base/agent-factory/resources/repository-*.yaml` |
| Multi-repository coordination (`coordination.mode`) | `off` in base; `plan` in `infrastructure/aws-0/room-broker/config.yaml` (`maxRepositories: 2`, `dailyPlans: 10`) | `infrastructure/aws-0/room-broker/config.yaml` |

Unlike Maku's defaults (`human.intake.plan.enabled: false`, `reasoningEffort` unset, `coordination.mode: off`),
this platform sets `reasoningEffort: low` so Z.ai `glm-5.3` finishes within the 20-second planner
deadline, reads the repository allowlist and workflow ceilings live from the factory's `/v1/catalog`
endpoint, and enables two-repository `coordination.mode: plan` in the AWS overlay.
