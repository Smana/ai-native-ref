# ai-native-ref

This repository deploys self-hosted open-weights GPU model serving (`llm-platform` + `ai-gateway`)
and the GitOps reference deployment of [Maku](https://maku.ogenki.io/) (`agent-platform`) onto
[Cloud Native Reference](https://github.com/Smana/cloud-native-ref). It ships the Flux manifests,
admission and network policies, merge-gate resources, alerts, dashboards, live validation runbooks,
and reference site ([airef.ogenki.io](https://airef.ogenki.io/)).

> [!TIP]
> **Maku product docs & interactive demo live at [maku.ogenki.io](https://maku.ogenki.io/).**
> Looking to run Maku standalone on your laptop or your own Kubernetes cluster? Start with the
> [15-minute quickstart](https://maku.ogenki.io/docs/get-started/quickstart/), the
> [12-chapter user guide](https://maku.ogenki.io/docs/guide/), or the
> [Tier-1 Pilot guide](https://maku.ogenki.io/docs/get-started/pilot/).

## What lives here

| Layer | Flux umbrella | Documentation |
|---|---|---|
| **Self-hosted GPU model serving** | `llm-platform` + `ai-gateway`: vLLM on spot L4 GPUs declared via Crossplane `InferenceService` claims, scaled by KEDA, behind Envoy AI Gateway and Semantic Router | [Model serving](https://airef.ogenki.io/docs/serving/) · [AI Gateway](https://airef.ogenki.io/docs/serving/ai-gateway/) · [Coding clients](https://airef.ogenki.io/docs/serving/coding-clients/) |
| **Maku on Cloud Native Ref** | `agent-platform`: digest-pinned Maku charts wired to ZITADEL OIDC, CloudNativePG, Cilium egress, OpenBao, `maku-gateway` (`agentgateway`), and the Victoria observability stack | [Maku on CNR](https://airef.ogenki.io/docs/maku-deployment/) · [Day-2 operations](https://airef.ogenki.io/docs/maku-deployment/day-2/) |
| **Host contract & ADRs** | Signed OCI artifact consumed by `cloud-native-ref` + the 7 serving and host-deployment ADRs | [Host contract](https://airef.ogenki.io/docs/reference/host-contract/) · [Decisions](https://airef.ogenki.io/docs/decisions/) |
| **Live validation evidence** | End-to-end runbooks, drills, and measured cost snapshots verifying Maku releases on real AWS and GCP clusters | [Reference status](https://airef.ogenki.io/docs/status/) · [Runbooks](docs/runbooks/agent-factory/README.md) · [Cost snapshot](docs/superpowers/specs/2026-10-18-cost-snapshot.md) |

## Try it

- [Maku laptop quickstart (15 min)](https://maku.ogenki.io/docs/get-started/quickstart/) — run Maku locally on kind or k3d from a labelled issue to a pull request.
- [Model serving on Cloud Native Ref](https://airef.ogenki.io/docs/serving/) — deploy open-weights vLLM models behind Envoy AI Gateway.
- [Maku on Cloud Native Ref](https://airef.ogenki.io/docs/maku-deployment/) — inspect the pinned host seams, active policies, and Day-2 procedures.

## Status

Active reference cluster, pinned Maku release, and serving status live on the
[reference status page](https://airef.ogenki.io/docs/status/). Maku product maturity and the v5 roadmap live on [maku.ogenki.io/docs/status/](https://maku.ogenki.io/docs/status/).

## Repository layout

| Directory | Holds |
|---|---|
| `clusters/<cluster>-{ai-gateway,llm-platform,agent-platform}/` | Children of each of the host's three opt-in Flux umbrellas |
| `infrastructure/`, `security/`, `tooling/`, `observability/`, `apps/` | Manifests, policies, factory resources, alerts, and dashboards those children apply |
| `flux/sources/` | AI-owned Flux sources applied by the `ai-sources` child |
| `website/` | Reference documentation site ([airef.ogenki.io](https://airef.ogenki.io/)) and serving/host ADRs |
| `scripts/` | CI gates and operator helpers (`task agent:run`, `task factory:walkthrough`) |
| `docs/` | Runbooks, design specs, plans, and architecture diagram sources |

## Turning it on in a cluster

A host built from [cloud-native-ref](https://github.com/Smana/cloud-native-ref) pulls each signed release as `OCIRepository/ai-native-ref`; the [host contract reference](https://airef.ogenki.io/docs/reference/host-contract/) documents the contract and the commands that resume the umbrellas.

## Validating a change

```bash
task check   # builds the host profile, then runs the host's gates on it
```

CI renders this tree inside `cloud-native-ref` at the commit in `HOST_REF`, so every change passes the host's own manifest, schema, policy, and documentation gates.

## Support this work

One person maintains this reference and pays for the cloud and model-API time its live sessions use; [sponsoring it](https://github.com/sponsors/Smana) helps cover that.

## License

[Apache-2.0](LICENSE).
