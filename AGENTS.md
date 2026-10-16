# ai-native-ref

The AI platform, applied by [cloud-native-ref](https://github.com/Smana/cloud-native-ref) (the
host) through `OCIRepository/ai-native-ref`. [`HOST-CONTRACT.md`](HOST-CONTRACT.md) is what the host
provides; anything not in it is not yours to rely on.

## Rules

- **Work in a git worktree**, branched from `origin/main`. Rebase onto a freshly fetched
  `origin/main` before every push.
- **`task check` is the evidence.** It clones the host at `HOST_REF` into `.host/`, builds
  `.composite/` (the host with its AI paths replaced by this tree) and runs the host's own
  `validate-manifests.sh`, this repository's gates on the bundle it renders, its suites, the
  link check and the source check. Never claim done without its output.
- **Host scripts are used from the host profile, never vendored.** Only the AI-owned gates and suites
  live here (`scripts/ci/flux-schema/assert-*-gateway.py`, `scripts/ci/tests/`); they overwrite the
  host's copies in the composite.
- **Every child names `sourceRef: {kind: OCIRepository, name: ai-native-ref}`** and depends only on
  the host Kustomizations in H2. `check-sources.sh` and the host's `check-ai-boundary.py` enforce it.
- **A host change you need is a cloud-native-ref PR first**, then a `HOST_REF` bump here.
- The host's [platform constitution](https://github.com/Smana/cloud-native-ref/blob/main/docs/platform-constitution.md)
  applies to every workload: `xplane-*` names, default-deny CiliumNetworkPolicy, requests and
  limits, both probes, restricted security context, least-privilege RBAC, no hardcoded credentials.
- Commits are conventional, in English, with no trailers.
