# ai-native-ref

The AI platform of [cloud-native-ref](https://github.com/Smana/cloud-native-ref): the AI gateway,
LLM serving and the agent factory, as Flux children of the host's three opt-in umbrellas.

| Directory | Holds |
|---|---|
| `clusters/<cluster>-{ai-gateway,llm-platform,agent-platform}/` | The children of each umbrella |
| `infrastructure/`, `security/`, `tooling/`, `observability/`, `apps/` | What those children apply |
| `flux/sources/` | The AI-owned Flux sources, applied by the `ai-sources` child |
| `website/` | The docs site, [ainref.ogenki.io](https://ainref.ogenki.io/): the AI section, the AI ADRs (numbering continues at 0058) |
| `docs/` | Agent-factory runbooks, AI specs and plans, drawio sources (moved from the host with their history) |

## How the host consumes it

Each `v*` tag is a cosign-signed OCI artifact, `ghcr.io/smana/ai-native-ref:<tag>`. The host defines
`OCIRepository/ai-native-ref` in `flux-system`, pinned by digest and suspended by default, and the
children read it (`sourceRef: {kind: OCIRepository, name: ai-native-ref}`). Opting in on a cluster:

```bash
flux resume source oci ai-native-ref
flux resume kustomization ai-gateway
flux resume kustomization llm-platform
flux resume kustomization agent-platform
```

What the host provides and what this repository guarantees back is the
[host contract](HOST-CONTRACT.md).

## Validating

```bash
task check   # builds the host profile, then runs the host's gates on it
```

CI renders this tree inside cloud-native-ref at the commit in `HOST_REF`, so a change here is judged
by the same gates the host applies to its own tree.

Verifying a release:

```bash
cosign verify ghcr.io/smana/ai-native-ref:<tag> \
  --certificate-identity-regexp '^https://github\.com/Smana/ai-native-ref/\.github/workflows/release\.yaml@refs/tags/v.*$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```
