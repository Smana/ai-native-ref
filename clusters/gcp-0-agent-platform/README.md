# gcp-0 agent platform (opt-in)

Children of the `agent-platform` umbrella (`../gcp-0/agent-platform.yaml`), live on gcp-0: the host's
go-live commit un-suspends it, with `ai-gateway` and the source, and names gcp-0 as the factory.
GCP parity with `aws-0-agent-platform/`: the sandbox pool is OpenTofu (`gke/init` `sandbox.tf`,
`agents-gvisor`) and GKE ships the `gvisor` RuntimeClass itself, so there is no node-pool child and
no gVisor RuntimeClass child here (GKE provides it, GP-9).

| Child Kustomization | Path | Holds |
|---|---|---|
| `agent-sandbox` | `infrastructure/base/agent-sandbox` | Sandbox CRD and controller in `agent-system` |
| `agent-runtime` | `infrastructure/base/agent-runtime` | identity-proxy ConfigMap, `agents` default deny |
| `agent-policies` | `security/base/agent-policies` | Kyverno admission and GC for runs |
| `agent-secrets` | `security/gcp-0/agent-secrets` | `SecretStore agents-secrets` -> the `agents` mount |
| `agent-router` | `infrastructure/gcp-0/agent-router` | `agent-router` Gateway, JWT per listener, the agents' Z.ai backend |
| `agentgateway` | `infrastructure/gcp-0/agentgateway` | agentgateway controller and CRDs in `agentgateway-system` (ADR-0053) |
| `agent-gateway` | `infrastructure/gcp-0/agent-gateway` | The agent router on agentgateway, beside `agent-router` until the cutover: Gateway `agent-gateway/agent-router`, JWT per listener, B1-B2 in shadow on its own rate-limit server and Valkey |
| `octo-sts` | `security/gcp-0/octo-sts` | GitHub token exchange for the agents' App, reached only through agent-router's `sts` listener |
| `agent-mcp` | `infrastructure/gcp-0/agent-mcp` | Flux, VictoriaMetrics, VictoriaLogs MCP servers and their MCPRoutes |
| `room-broker` | `infrastructure/gcp-0/room-broker` | Room CRD, broker, room log (CNPG), retention, and from phase 2 oauth2-proxy (SP2) |
| `room-broker-suspend` (unlisted) | `infrastructure/base/room-broker/suspend` | `patch` on `agentruns`, for the broker's suspend trigger (v2 warm-sandboxes S3). Listing it, with `suspend.enabled: true` in the broker config, turns suspend on |
| `kueue` | `infrastructure/gcp-0/kueue` | Kueue controller: admits sandbox pods by integration, pod-only, `agents` namespace only (SP3) |
| `kueue-queues` | `infrastructure/base/kueue-queues` | ResourceFlavor, the `agents-factory`/`agents-interactive` ClusterQueues and their LocalQueues (SP3) |
| `agents-headroom` | `infrastructure/base/karpenter-nodepools-agents/headroom` | One preemptible pod keeping a warm `agents-gvisor` node with the run images pulled (v2 warm sandboxes, step 1); it holds one `e2-standard-8` up |
| `agent-factory` | `tooling/gcp-0/agent-factory` | The factory: Task CRD and controller, issue intake, run meter (SP3) |
| `agent-observability` | `observability/gcp-0/agent-platform` | VMRules, the dashboards (`agent-platform`, `agent-run`, `agent-fleet`) and the agent trace collector |
| `runlore-factory` | `observability/base/runlore-factory` | RunLore's notifier and intake token, merged into the host's RunLore through its optional `valuesFrom` (SP3 §1) |

`AgentGvisorPoolNearLimit` and the dashboard's pool-usage panel read Karpenter metrics, so they stay
silent here. A full `agents-gvisor` pool, or the cluster ceiling in `gke/init/variables.tfvars`,
shows up as `AgentSandboxPodPending`.

## Resume

This umbrella `dependsOn` `ai-gateway`. The host goes live with one commit, not `flux resume`, which
lasts only until the parent Kustomization re-applies `suspend: true`. That commit sets
`suspend: false` on `gcp-0/ai-gateway.yaml` and `gcp-0/agent-platform.yaml`, un-suspends
`OCIRepository/ai-native-ref` with a patch in `gcp-0/flux/flux-sources.yaml`, and sets
`factory: gcp-0` in the host's ownership fence.

Only once the crossplane-configuration pin serves `AgentRun`. Before it, `agent-policies` installs
Kyverno policies against an API that does not exist, and Flux still reports it Ready.

On an **existing** cluster, first apply `opentofu/gcp/openbao/management` then
`opentofu/gcp/gke/configure` — they create the `agents-secrets` policy and JWT role, without which
`SecretStore agents-secrets` never goes Ready. On a feature-branch cluster, `gke/configure` needs
`TF_VAR_flux_git_ref=refs/heads/<branch>`.

The owner prerequisites come next, in this order (ADR-0043): the agents' rulesets
(`task ops:github:agent-branch-ruleset -- Smana/cloud-native-ref` applies every ruleset this
repository ships), then the GitHub App installed
and its key written to `github-app` on gcp-0's `agents` mount:

    bao kv put -mount=agents github-app app_id=<id> private_key=@<pem file>

Without the key, `octo-sts` sits in `CreateContainerConfigError` and its child fails the health
check. The GCP lineage's raft snapshot cannot be restored across the AWS lineage's KMS seal, so the
other two agent keys are written the same way, once per GCP lineage:

    bao kv put -mount=agents zai api_key=-
    bao kv put -mount=agents anthropic api_key=-
    bao kv put -mount=agents factory-app app_id=<App ID> private_key=@<pem file>
    bao kv put -mount=agents merger-app app_id=<App ID> private_key=@<pem file>

`anthropic` backs the internal tier on Claude. `merger-app` and the RunLore intake token
(`runlore-intake`, [runbook README](../../docs/runbooks/agent-factory/README.md) action 4d) are
mounted non-optionally: without them the factory pod never starts.

`factory-app` is the factory App `ogenki-agent-factory`'s key (SP3's, created early). From SP2
phase 3 the room broker posts reviewers' verdicts with it; without it the broker still runs, and
the verdicts stay in the room instead of reaching the pull request.


## Teardown

Suspending leaves the children in place. To remove them:

    kubectl delete agentruns -n agents --all --wait
    flux suspend kustomization agent-platform -n flux-system
    kubectl kustomize clusters/gcp-0-agent-platform | awk '/^  name:/{print $2}' | xargs flux delete kustomization -n flux-system --silent
