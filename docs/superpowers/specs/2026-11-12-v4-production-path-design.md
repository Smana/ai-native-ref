# v4 stage 2, the production path: ANR's part

**Status:** design, agreed with the owner on 2026-11-12. **The design lives in Maku** ([Smana/maku#479](https://github.com/Smana/maku/pull/479), the 2026-11-12 v4 production path design), decisions D1–D26. This file holds only what ANR and cnref change.

**Release:** nothing here cuts v4. Each step ships as an ANR minor following a Maku v0.4x minor;
the v4.0.0 release waits for the owner's explicit go.

## What ANR becomes (D15, D22)

ANR stays the AI layer cnref applies through `OCIRepository/ai-native-ref`, keeping the host
contract, its release cadence and the docs site. It shrinks to:

- the umbrella HelmRelease and its cnref values;
- the agentgateway routes (with the model overrides now held in its values);
- cnref-specific Secrets and ExternalSecrets (OpenBao behind the Secrets-by-name seam);
- the live-session runbooks and the gates that render the chart with the cnref values.

## Shrink checklist

One ANR PR per Maku rollout step, each followed by a gcp-0 live check recorded in the ledger.

| Maku step | ANR/cnref change | Decision |
|---|---|---|
| 1. Chart contract | install `agent-factory-crds` first; drop the Flux `CreateReplace` reliance | D13 |
| 2. Run path | switch from the Crossplane AgentRun XR to the run-controller; delete Kueue (ClusterQueue, LocalQueue, labels); delete the Kyverno policies a VAP now covers | D5, D16, D17 |
| 3. GitHub seams | switch the factory off octo-sts to per-run minted tokens; retire policy-bot for the `maku/merge-gate` status; branch protection requires it | D10, D11, D12 |
| 4. Gateway | move the planner and the classifier to agentgateway; delete the Envoy AI gateway path and its suspended overrides | D7 |
| 5. Identity and data | keep ZITADEL, CNPG and OpenBao, consumed only as an OIDC issuer, a DSN Secret and Secrets by name; drop the `readerFile` PAT | D8, D9, D14 |
| 6. Exposure, components, observability | `expose.mode: httproute` on the cnref Gateway; Slack subchart enabled in values; delete the VMRules for the chart's PrometheusRule; delete the duplicated room-broker and slack-app manifests | D19, D20, D21, D22 |
| 7. Proof | the manual GKE install on gcp-0 before any v4 announcement | D23 |
