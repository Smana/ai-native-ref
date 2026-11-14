# gcp-0 agent platform (opt-in)

Children of the `agent-platform` umbrella (`../gcp-0/agent-platform.yaml`). The host's go-live
commit un-suspends it, with `ai-gateway` and the source, and names gcp-0 as the factory. gcp-0 ran
the factory until its teardown on 2026-10-29; this is what the next bootstrap applies.
GCP parity with `aws-0-agent-platform/`: the sandbox pool is OpenTofu (`gke/init` `sandbox.tf`,
`agents-gvisor`) and GKE ships the `gvisor` RuntimeClass itself, so there is no node-pool child and
no gVisor RuntimeClass child here (GP-9).

| Child Kustomization | Path | Holds |
|---|---|---|
| `agent-sandbox` | `infrastructure/base/agent-sandbox` | Sandbox CRD and controller in `agent-system` |
| `agent-runtime` | `infrastructure/base/agent-runtime` | `agents` default deny |
| `agent-policies` | `security/base/agent-policies` | Kyverno: no secret import into `agents`, the reserved audiences, the kill switch, and the GC of finished `maku.ogenki.io` runs. The run pod's shape and the AgentRun's creator and patch limits are the `maku` chart's admission policies (R3) |
| `agent-secrets` | `security/gcp-0/agent-secrets` | `SecretStore agents-secrets` -> the `agents` mount |
| `agent-router` | `infrastructure/gcp-0/agent-router` | The agents' provider keys (Z.ai, Anthropic) that agentgateway's backends read. Envoy's agent router was removed in phase H |
| `agentgateway` | `infrastructure/gcp-0/agentgateway` | agentgateway controller and CRDs in `agentgateway-system` (ADR-0053) |
| `agent-gateway` | `infrastructure/gcp-0/agent-gateway` | The agent router on agentgateway: Gateway `agent-gateway/agent-router`, JWT per listener, capability profiles, budgets B1, B2 and B6 enforced on its own rate-limit server and Valkey |
| `model-gateway` | `infrastructure/gcp-0/agent-gateway/model-gateway` | Maku's `maku-gateway` chart: Gateway `agent-gateway/model-gateway` with agent-router's providers, aliases and prices under Maku's identity contract, plus budgets B1, B2 and B6 on agent-router's rate-limit server. No caller until runs move to it |
| `merge-gate-secrets` | `security/gcp-0/merge-gate-secrets` | `SecretStore merge-gate-secrets` -> the `merge-gate` mount, policy-bot's App secret (SP3 R44) |
| `agent-mcp` | `infrastructure/gcp-0/agent-mcp` | Flux, VictoriaMetrics and VictoriaLogs MCP servers |
| `room-broker` | `infrastructure/gcp-0/room-broker` | Room CRD (`rooms.maku.ogenki.io`), broker, room log (CNPG), retention, oauth2-proxy, and since R3 the run-controller: it runs each `maku.ogenki.io` AgentRun as a gVisor pod in `agents`, with the egress proxy, a NetworkPolicy per run, the runs quota and the run-pod admission policy. After `agent-factory-crds` |
| `agent-factory-crds` | `tooling/base/agent-factory/crds` | The six `maku.ogenki.io` CRDs (Rooms, AgentRuns, Tasks, Factories, Repositories, MergePolicies) from the `agent-factory-crds` chart, `helm.sh/resource-policy: keep`. Adopting existing CRDs: [runbook 26](../../docs/runbooks/agent-factory/26-crds-adoption.md). Before `agent-policies`, `room-broker` and the factory |
| `agent-factory` | `tooling/gcp-0/agent-factory` | The factory: controller, issue intake, run meter (SP3) |
| `agent-factory-resources` | `tooling/gcp-0/agent-factory/resources` | The factory's `Factory`, `Repository` and `MergePolicy` objects: its catalogue, repositories and merge policies, read live. After `agent-factory-crds`; the factory waits, not Ready, until these exist |
| `tooling-factory-slack-app` | `tooling/gcp-0/agent-factory/slack-app` | `maku-slack`, the Slack App, with gcp-0's team and channels (runbooks 18, 22) |
| `policy-bot` | `tooling/gcp-0/policy-bot` | The merge gate: policy-bot, its public hook and tailnet UI (SP3, ADR-0045) |
| `agent-observability` | `observability/gcp-0/agent-platform` | VMRules, the Agents folder's dashboards (overview, fleet, factory, gateway, identity, room, run) and the agent trace collector |
| `runlore-factory` | `observability/gcp-0/agent-platform/runlore-factory` | RunLore's factory client (feature 14): its principal and values, merged into the host's RunLore through its optional `valuesFrom` (H8) |

`AgentGvisorPoolNearLimit` and the dashboard's pool-usage panel read Karpenter metrics, so they stay
silent here. A full `agents-gvisor` pool, or the cluster ceiling in `gke/init/variables.tfvars`,
shows up as `AgentSandboxPodPending`.

## Resume

This umbrella `dependsOn` `ai-gateway`. The host goes live with one commit, not `flux resume`, which
lasts only until the parent Kustomization re-applies `suspend: true`. That commit sets
`suspend: false` on `gcp-0/ai-gateway.yaml` and `gcp-0/agent-platform.yaml`, un-suspends
`OCIRepository/ai-native-ref` with a patch in `gcp-0/flux/flux-sources.yaml`, and sets
`factory: gcp-0` in the host's ownership fence.

The runs' API, `agentruns.maku.ogenki.io`, comes from `agent-factory-crds`, which `agent-policies`,
`room-broker` and the factory wait for: no crossplane-configuration pin is involved since R3.

On an **existing** cluster, first apply `opentofu/gcp/openbao/management` then
`opentofu/gcp/gke/configure` — they create the `agents-secrets` and `merge-gate-secrets` policies
and JWT roles, without which their SecretStores never go Ready. On a feature-branch cluster, `gke/configure` needs
`TF_VAR_flux_git_ref=refs/heads/<branch>`.

The owner prerequisites come next, in this order (ADR-0043): the agents' rulesets
(`task ops:github:agent-branch-ruleset -- Smana/cloud-native-ref` applies every ruleset this
repository ships), then the GitHub App installed
and its key written to `github-app` on gcp-0's `agents` mount:

    bao kv put -mount=agents github-app app_id=<id> private_key=@<pem file>

Without the key, the factory mints no run its git token
(`tooling/base/agent-factory/externalsecret-agents-app.yaml`). The GCP lineage's raft snapshot cannot be restored across the AWS lineage's KMS seal, so the
other agent keys are written the same way, once per GCP lineage:

    bao kv put -mount=agents zai api_key=-
    bao kv put -mount=agents anthropic api_key=-
    bao kv put -mount=agents factory-app app_id=<App ID> private_key=@<pem file>
    bao kv put -mount=agents merger-app app_id=<App ID> private_key=@<pem file>

policy-bot's App `ogenki-merge-gate` goes on its own mount, with its webhook pointed at
`https://policy-bot.gcp.cloud.ogenki.io/api/github/hook`:

    bao kv put -mount=merge-gate policy-bot app_id=<id> private_key=@<pem file> webhook_secret=@<file> oauth_client_id=<id> oauth_client_secret=@<file>

Without it `policy-bot` never starts, and every merge-gate decision is `human`/`policy_absent`.

`anthropic` backs the internal tier on Claude. `merger-app` is mounted non-optionally: without it
the factory pod never starts. `factory-app` is the factory App `ogenki-agent-factory`'s key: the room
broker posts reviewers' verdicts with it; without it the verdicts stay in the room instead of
reaching the pull request.

## Teardown

Suspending leaves the children in place. To remove them:

    kubectl delete agentruns -n agents --all --wait
    flux suspend kustomization agent-platform -n flux-system
    kubectl kustomize clusters/gcp-0-agent-platform | awk '/^  name:/{print $2}' | xargs flux delete kustomization -n flux-system --silent
