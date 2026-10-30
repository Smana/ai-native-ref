# aws-0 agent platform

Children of the `agent-platform` umbrella (`../aws-0/agent-platform.yaml`), released on aws-0
(`suspend: false`). aws-0 ran the factory until its teardown on 2026-10-16; the ownership fence
names `gcp-0`.
Design: `docs/superpowers/specs/2026-09-23-agent-runtime-identity-design.md`.

| Child Kustomization | Path | Holds |
|---|---|---|
| `agent-sandbox` | `infrastructure/base/agent-sandbox` | Sandbox CRD and controller in `agent-system` |
| `kueue` | `infrastructure/aws-0/kueue` | Kueue controller (SP3) |
| `kueue-queues` | `infrastructure/base/kueue-queues` | ResourceFlavor, ClusterQueues and LocalQueues (SP3) |
| `agents-nodepool` | `infrastructure/base/karpenter-nodepools-agents` | `agents-gvisor` NodePool + EC2NodeClass |
| `runtimeclass-gvisor` | `infrastructure/base/runtimeclass-gvisor` | RuntimeClass `gvisor` → `runsc` |
| `agents-headroom` | `infrastructure/base/karpenter-nodepools-agents/headroom` | Preemptible placeholder: one warm `agents-gvisor` node, run images pulled. Off by default (`replicas: 0`) |
| `agent-runtime` | `infrastructure/base/agent-runtime` | identity-proxy ConfigMap, `agents` default deny |
| `agent-policies` | `security/base/agent-policies` | Kyverno admission and GC for runs |
| `agent-secrets` | `security/aws-0/agent-secrets` | `SecretStore agents-secrets` → the `agents` mount |
| `agent-router` | `infrastructure/aws-0/agent-router` | The agents' provider keys (Z.ai, Anthropic) that agentgateway's backends read. Envoy's agent router was removed in phase H |
| `agentgateway` | `infrastructure/aws-0/agentgateway` | agentgateway controller and CRDs in `agentgateway-system` (ADR-0053), plus the PoC's namespaces |
| `agent-gateway` | `infrastructure/aws-0/agent-gateway` | The agent router on agentgateway: Gateway `agent-gateway/agent-router`, JWT per listener, budgets on its own rate-limit server and Valkey |
| `agentgateway-poc` | `infrastructure/aws-0/agentgateway-poc` | The PoC Gateway `agw-poc/agent-router-agw` (aws-0 only) |
| `octo-sts` | `security/aws-0/octo-sts` | GitHub token exchange for the agents' App, reached only through the agent router's `sts` listener |
| `merge-gate-secrets` | `security/base/merge-gate-secrets` | `SecretStore merge-gate-secrets` → the `merge-gate` OpenBao mount (SP3, R44) |
| `agent-mcp` | `infrastructure/aws-0/agent-mcp` | Flux, VictoriaMetrics and VictoriaLogs MCP servers |
| `room-broker` | `infrastructure/aws-0/room-broker` | Room CRD (`rooms.maku.ogenki.io`), broker, room log (CNPG), retention, oauth2-proxy |
| `room-broker-suspend` (unlisted) | `infrastructure/base/room-broker/suspend` | `patch` on `agentruns`, for the broker's suspend trigger. Listing it, with `suspend.enabled: true` in the broker config, turns suspend on |
| `agent-factory` | `tooling/aws-0/agent-factory` | The factory: Task CRD and controller, issue intake, run meter (SP3) |
| `policy-bot` | `tooling/base/policy-bot` | The merge gate: policy-bot, its public hook and tailnet UI (SP3, ADR-0045) |
| `agent-observability` | `observability/aws-0/agent-platform` | VMRules, the Agents folder's dashboards and the agent trace collector |
| `runlore-factory` | `observability/base/runlore-factory` | RunLore's factory client (feature 14), merged into RunLore's values only while this umbrella ships it |

## Resume

Only once the crossplane-configuration pin serves `AgentRun`. Before it, `agent-policies` installs
Kyverno policies against an API that does not exist, and Flux still reports it Ready.

On an **existing** cluster, first apply `opentofu/aws/openbao/management` then
`opentofu/aws/eks/configure` — they create the `agents-secrets` policy and JWT role, without which
`SecretStore agents-secrets` never goes Ready. On a feature-branch cluster, `eks/configure` needs
`TF_VAR_flux_git_ref=refs/heads/<branch>`.

The owner prerequisites come next, in this order (ADR-0043): the branch and tag rulesets
(`task ops:github:agent-branch-ruleset -- Smana/cloud-native-ref`), then the App installed and its
key written to `github-app` on the `agents` mount. Without the key, `octo-sts` sits in
`CreateContainerConfigError` and its child fails the health check.

The factory App `ogenki-agent-factory` is installed on `Smana/cloud-native-ref` with its key at
`factory-app` on the `agents` mount. Without it, the room broker still runs, and reviewers' verdicts
stay in the room instead of reaching the pull request.

## Teardown

Suspending leaves the children in place. To remove them:

    kubectl delete agentruns -n agents --all --wait
    flux suspend kustomization agent-platform -n flux-system
    kubectl kustomize clusters/aws-0-agent-platform | awk '/^  name:/{print $2}' | xargs flux delete kustomization -n flux-system --silent
