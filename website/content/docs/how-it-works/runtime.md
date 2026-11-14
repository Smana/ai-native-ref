---
title: Runtime
aliases:
  - /docs/platform/ai-platform/agents/how-it-works/runtime/
weight: 40
description: "How one AgentRun becomes an isolated, attributed run: Maku's run-controller, a gVisor pod, per-run tokens for the model gateway and GitHub, and default-deny network policy with an egress proxy."
lastVerified: 2026-11-14
---

One `AgentRun` object becomes a fully isolated, fully attributed run. The agent in the loop is not
trusted, so every control on this page sits outside the sandbox. This page describes the design;
what runs today is on the [status page]({{< relref "/docs/status.md#landed" >}}).

<!-- TODO: redraw ai-platform.drawio page 3 for the run-controller: the picture still shows the Crossplane composition, the Envoy identity proxy and octo-sts. -->
![The agent runtime. The factory creates an AgentRun, and Maku's run-controller renders its ServiceAccount, task ConfigMap, NetworkPolicy and one gVisor pod. Inside it, the maku-harness runs OpenHands with the run's own model-gateway token, and the maku-bridge sidecar holds the room token for maku-broker. The harness reaches GitHub through the egress proxy, with a git token the factory minted for that run](/images/diagrams/ai-platform-3.svg)

*Source: [`docs/architecture/ai-platform.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/ai-platform.drawio), page 3.*

## Components and software

| Component | Software | What it does |
|---|---|---|
| Run API | `AgentRun` (`maku.ogenki.io`), from the `agent-factory-crds` release | One object per run, named `run-<id>`. Only the factory creates one |
| Run controller | Maku's run-controller, in the broker's `maku` chart | Renders the run's ServiceAccount, task ConfigMap, NetworkPolicy and pod, and projects its phase back |
| Isolation | [gVisor](https://gvisor.dev/docs/) (`runsc`) on a dedicated pool: GKE Sandbox on GKE, a [Karpenter](https://karpenter.sh/docs/) pool on EKS | An exploit has to break gVisor's user-space kernel before it reaches the node's |
| Harness | [OpenHands](https://github.com/OpenHands/software-agent-sdk), wrapped by `agent-run` | The agent loop. Its settings: [Harness tuning]({{< relref "/docs/operate/tune-a-run.md" >}}) |
| Model access | The model gateway, `model-gateway` in `agent-gateway` | Every model call carries the run's own token; only the gateway holds provider keys |
| Network | Kubernetes NetworkPolicies and Maku's egress proxy | Default deny; HTTPS leaves only through the proxy, to the run's own hosts |
| GitHub access | The agents' GitHub App, minted per run by the factory | A token for one repository and one role, in the run's own Secret, revoked at the end |
| Admission | Maku's ValidatingAdmissionPolicies | Only the run-controller creates run pods; only the factory creates runs |
| Capacity | A `ResourceQuota` on `agents` | Bounds the number of run pods and their CPU and memory |
| Secrets | [OpenBao](https://openbao.org/docs/) and [External Secrets](https://external-secrets.io) | Holds the platform's secrets; none reaches a sandbox |

Why gVisor: strong isolation without VMs, on ordinary nodes (Kata would need bare metal or nested
virtualisation). Why OpenHands: open source, headless, model-agnostic, with MCP support.
[Alternatives considered]({{< relref "/docs/how-it-works/alternatives.md" >}}) covers the rest.

## What a run holds

A run's pod is `run-<id>` in namespace `agents`. The harness container is where the model's commands
run. A run with a room adds two more: `room-bridge`, a sidecar that streams the run's events to the
room, and `room-gate`, which must pass before the harness starts.

The harness never holds a Kubernetes API token. It reads projected tokens, each bound to one
audience, and a git token from the run's own Secret, `run-<id>-git`:

| Token | Audience | Used for |
|---|---|---|
| Model | `maku-gateway.<class>.<alias>` | The run's model on the model gateway. A completion judge gets a second token for its own alias |
| Room tools | `room-tools` | The `room_*` tools on the broker's `:8090`, which checks the token with a TokenReview |
| Room | `room-broker` | The bridge's events to the broker, held by `room-bridge` only |
| Git | — | GitHub, through the egress proxy; minted by the factory for this run |

The room tools are a run's only MCP server: a run without a room gets none.

## Security boundaries

| Boundary | Mechanism |
|---|---|
| Code execution | gVisor, restricted pod security, no ServiceAccount token mounted, images pinned by digest |
| Network | Default deny per run; HTTPS only through the egress proxy, to GitHub, the run's egress profiles and the model |
| Identity | Every token names the run's ServiceAccount, `system:serviceaccount:agents:run-<id>`, and one audience |
| Model | The gateway serves a run only the alias its token names, on its data class's listener |
| GitHub | A per-run token for one repository and the role's permissions; rulesets let the agents' App push only `agent/**` branches, and no tags |

Confinement on GitHub is per repository: any run may push any `agent/**` branch, with no per-run
branch isolation. DNS stays open to the run in this network mode, so DNS tunnelling is the residual
risk; Cilium policies, which filter DNS names, would close it.

Spend, merge and stop are the factory's controls: see
[Factory → Controls]({{< relref "/docs/how-it-works/factory.md#controls" >}}).
