# Host contract

**Contract version 1**, tested against [cloud-native-ref](https://github.com/Smana/cloud-native-ref)
at the commit in [`HOST_REF`](HOST_REF). Copied from the design on 2026-10-16.

What `cloud-native-ref` guarantees, and `ai-native-ref` may rely on. Copied from the AI platform
split design, §2 (ADR-0057). Changing an item is a breaking change for both repositories: it lands
with a version bump of the pin and a note in both.

### H1 · Flux

| Item | Contract |
|---|---|
| Namespace | Every Flux `Kustomization` lives in `flux-system`; most sources and every HelmRelease live in their consumer's namespace (`agent-system`, `llm`, `envoy-*-system`, …); a few sources stay in `flux-system` |
| Shared sources | `HelmRepository/oauth2-proxy` (namespace `tooling`) |
| Source | `cloud-native-ref` defines one `OCIRepository` `ai-native-ref` in `flux-system`, `suspend: true` by default, pinned by digest with a tag for Renovate, verified with cosign against `ai-native-ref`'s release workflow identity (the `ocirepo-agent-factory` pattern) |
| Umbrellas | `ai-gateway`, `llm-platform`, `agent-platform`: names unchanged, `suspend: true` by default, `sourceRef` the `ai-native-ref` source, `path: ./clusters/<cluster>-<umbrella>`. `llm-platform` and `agent-platform` depend on `ai-gateway` |
| Children | Use `sourceRef: {kind: OCIRepository, name: ai-native-ref}`, replacing today's `ExternalArtifact`s from the `monorepo-split` ArtifactGenerator |
| Default deploy | Does not fetch `ai-native-ref`: the source is suspended until the opt-in (§3), so an unreachable artifact can never block a default deploy |
| Feature branches | `ai-native-ref` CI pushes a signed pre-release artifact per branch; the cluster variable `ai_native_ref_tag` (H3), set at deploy time like `TF_VAR_flux_git_ref`, makes the source follow that tag instead of the pinned digest |

### H2 · Host Kustomizations children may depend on

Stable names in `flux-system`. Renaming one breaks a child's `dependsOn`.

| Name | Provides |
|---|---|
| `crds` | Gateway API (with the Inference Extension), Cilium, External Secrets, VictoriaMetrics operator, grafana-operator, Kyverno, cert-manager, Karpenter CRDs |
| `crossplane-configuration` | The XRDs and compositions in `cloud.ogenki.io` |
| `security` | Kyverno, External Secrets, cert-manager, the platform PKI issuers |
| `security-openbao` | OpenBao reachable, its CA published |
| `eks-pod-identities` (aws) | The `EPI` composition's prerequisites |
| `karpenter-nodepools` (aws) | Karpenter and the shared `EC2NodeClass`es |
| `observability` | VictoriaMetrics, VictoriaLogs, VictoriaTraces, Grafana with its datasources |
| `apps` | The host apps layer, for children that must come after it |
| `infrastructure` | KEDA, the Atlas operator and the cluster add-ons `llm-platform-apps` waits for |

### H3 · Substitution variables

Children use `postBuild.substituteFrom` the ConfigMap `<eks|gke>-<cluster>-vars` in `flux-system`
(today `eks-aws-0-vars` and `gke-gcp-0-vars`). Keys the AI platform reads:

| Key | Used for |
|---|---|
| `cluster_name` | OpenBao JWT auth paths (`jwt/${cluster_name}`), Karpenter's node role |
| `environment` | Karpenter subnet and security-group discovery |
| `project_id` (gcp) | The model bucket and its volume, room-broker backups |
| `private_domain_name`, `public_domain_name` | Hostnames on the tailnet and public Gateways |
| `identity_provider_url` | ZITADEL issuer for humans (rooms, run API) |
| `oidc_issuer_url`, `oidc_issuer_host`, `oidc_jwks_uri`, `oidc_jwks_host` | The cluster's ServiceAccount issuer, for run tokens at the gateway, octo-sts and the broker |
| `region` | Cloud region in backends and buckets |
| `storage_class` | Persistent volumes |
| `llm_hf_token_secret` | The model-download secret name |
| `ai_native_ref_tag` (optional) | The feature-branch override (H1); unset on a default deploy |

Grafana dashboard variables (`${datasource}`, `${model}`) are not Flux substitutions.

### H4 · Network

| Item | Contract |
|---|---|
| Gateways | `platform-tailscale-general` (tailnet) and `platform-public` (internet), Gateway API, in the namespaces their routes reference today |
| Cilium | Default-deny CNP is the constitution's rule; `socketLB.hostNamespaceOnly: true` on both clouds (gVisor needs it) and the startup taint on every node pool (F2) |
| DNS | Hostnames under `private_domain_name` resolve on the tailnet |

### H5 · Namespaces, secrets and identity

| Item | Contract |
|---|---|
| Namespaces | The host creates `agents`, `agent-system`, `agent-gateway`, `llm`, `llm-gateway`, `envoy-ai-gateway-system`, `envoy-gateway-system` and `merge-gate`, with their PSA labels (`agents` is `restricted`) |
| OpenBao | Mounts `agents` (both clouds) and `merge-gate` (aws), with the policies in `opentofu/<cloud>/openbao/management` and the JWT auth roles at `jwt/${cluster_name}` from `opentofu/<cloud>/{eks,gke}/configure/openbao.tf` that the `agents-secrets` and `merge-gate-secrets` stores log in with |
| Stores | `ai-native-ref` creates its own namespaced stores (`agents-secrets`, `merge-gate-secrets`); it reads the cluster-wide `openbao-platform` store only where it does today, and the CA from `openbao-ca` |
| ZITADEL | The rooms and `roomctl` OIDC clients and the link-only GitHub IdP, provisioned by the host's scripts |
| PKI | The OpenBao PKI role signs certificates for the broker's in-cluster and private names (F7) |
| Workload identity | EKS Pod Identity (never IRSA) and GKE Workload Identity, through the `EPI` and `GCPWorkloadIdentity` compositions |

### H6 · Compute

| Item | Contract |
|---|---|
| AWS | Karpenter, its node role `Karpenter-${cluster_name}`, subnets and security groups discoverable by `${environment}`, GPU-capable instance families allowed in the account. The gVisor and GPU `EC2NodeClass`es are `ai-native-ref`'s |
| GCP | A GKE Sandbox node pool (`opentofu/gcp/gke/init/sandbox.tf`) and node auto-provisioning for GPUs |
| Kubernetes | The versions in `opentofu/config.tm.hcl`; GKE ≥ 1.35.0-gke.1171000 for the 120 s Spot window |

### H7 · Data and storage

CNPG through `SQLInstance`, Valkey through `KVStore`, and on AWS the S3 Files filesystem for model
weights from `opentofu/aws/llm-platform`, mounted through the EFS CSI driver.

### H8 · Observability

VictoriaMetrics accepts `VMServiceScrape` and `VMRule`, grafana-operator accepts `GrafanaDashboard`
in folders the AI platform names, the trace collector's OTLP endpoint is reachable, and the
datasource names in H2's `observability` are stable. The host's RunLore HelmRelease reads the
ConfigMap `runlore-factory-values` in `runlore` through `valuesFrom` with `optional: true`, so it
deploys without the AI platform.

### What `ai-native-ref` guarantees back

- Every workload keeps the constitution: `xplane-*` names for composed resources, default-deny CNP,
  requests and limits, both probes, restricted security context, least-privilege RBAC.
- It writes to two host namespaces only: `observability` (scrapes, rules, dashboards, the agent
  trace collector) and `runlore` (the `runlore-factory-values` ConfigMap, H8).
- Each release states the host contract version it was tested against.
