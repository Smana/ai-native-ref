# Research: Can kagent replace any part of the agent factory?

**Topic**: kagent-evaluation · **Conducted**: 2026-10-04 by Claude · **Rechecked**: 2026-11-11 by
Kimi (three parallel research passes: kagent, Substrate, migration and Crossplane)

---

## Scope and pinned sources

The October evaluation compared kagent v1.0.0-alpha7 and v0.10.3 with the proposed Agent Factory.
This reassessment asks whether the kagent 1.0 rewrite changes that conclusion for the platform as it
now exists. It evaluates three options:

1. retain agent-sandbox + gVisor + OpenHands;
2. adopt upstream Agent Substrate directly behind the existing Crossplane `AgentRun` API;
3. adopt kagent + its Substrate fork behind `AgentRun`.

The factory, attributed rooms, agentgateway, octo-sts, Kueue policy and merge gate remain requirements,
not components that a runtime candidate can silently remove.

| Source | Version | Commit |
|---|---|---|
| kagent | `v1.0.0`, released 2026-11-09 | `a08cde76ad6482dd758a4220b14213d79185ac30` |
| kagent's Substrate fork | `v1.0.0`, the kagent-tested pin | `563df06f6be751c101539986896c17c55aa22a9d` |
| upstream Agent Substrate | `v1.0.0-rc.3`, newest upstream release found | `4ee8f66ac237adfc3303086b12275aefc150fd6f` |
| earlier OpenHands/Substrate spike | Substrate `v0.5.0` on GKE | [local spike](2026-10-17-substrate-spike.md) |

Claims below come from tagged source, current project documentation and issue/PR state. Release-note
claims alone are not treated as proof of end-to-end enforcement.

## Decision

**Keep agent-sandbox + gVisor + OpenHands. Do not migrate to kagent or Substrate, and do not start a
runtime PoC now.** ADR-0062 records the decision.

- **kagent 1.0 is materially better**, but its additional Session, Harness and persistence plane
  overlaps ours without replacing the factory, rooms, approvals, budgets or GitHub controls.
- **Direct Substrate is the cleaner future runtime candidate**, but its incremental benefits do not
  currently justify its migration and operating costs.
- **No new component is adopted.** Reconsideration is driven by measured runtime pain and the explicit
  triggers below, not by release cadence.

## What kagent 1.0 changes

The rewrite is real and substantial:

- A Session runs as one Actor on Agent Substrate, multiplexed over pre-started Workers with gVisor by
  default and optional microVMs. `AgentTemplate`, `Harness`, immutable `Agent` revisions and `Session`
  replace the old long-lived agent Deployment model ([architecture](https://kagent.dev/docs/kagent/latest/about/architecture/kagent/),
  [core concepts](https://kagent.dev/docs/kagent/latest/about/core-concepts/)).
- Conversation uses A2A; tools use MCP. Built-in harnesses cover kagent's ADK, Claude Code and Codex,
  with a BYO gRPC A2A contract ([harnesses](https://kagent.dev/docs/kagent/latest/agents/agent-harness/),
  [BYO](https://kagent.dev/docs/kagent/latest/agents/bring-your-own-agent/)).
- Actor-to-controller authentication now verifies short-lived JWTs, including audience, lifetime and
  Session binding. Gateway-injected Actor JWTs also serve model, MCP and egress policies
  ([identity](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/identity/)).
- Per-Actor egress is default-deny, including policy-aware DNS. Credentials can be injected outside the
  sandbox ([egress](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/networking-and-egress/),
  [EgressPolicy](https://kagent.dev/docs/kagent/latest/agents/egress-policies/)).
- Turn-boundary persistence, automatic wake, checkpoints and forks are shipped
  ([lifecycle](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/suspend-and-resume/)).
- Session shares are now read-only. This removes the October concern that a share authorized writes as
  the owner, but it does not create a collaborative room
  ([sharing](https://kagent.dev/docs/kagent/latest/agents/share-a-session/)).

These changes close several alpha-era objections. They do not establish that kagent simplifies this
factory.

## Requirement comparison

| Requirement | kagent 1.0 evidence | Verdict |
|---|---|---|
| **Per-run identity** | Strong Actor authentication, but one Actor per kagent Session rather than per `AgentRun`; Agent identity needs a separate lookup | Keep our per-run ServiceAccount and run/role/repository contract |
| **Non-bypassable OSS authorization** | `insecure` mode is the default and accepts caller-selected identity. `trusted-proxy` does not verify JWT signature or expiry; the OSS authorizer remains permissive ([identity](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/identity/)) | Requires validating ingress, strict network lockdown and a custom authorizer before multi-tenant use |
| **Enterprise authorization** | Verified OIDC and RBAC policies exist, but access-control behavior is documented as under development ([Enterprise policies](https://docs.solo.io/kagent/latest/security/policies/)) | Assess separately; do not use Enterprise to rescue the OSS option |
| **Attributed rooms** | One Agent and one Actor per Session; shares are read-only | Rooms remain ours |
| **Delegated approvals and audit** | `requireApproval` records a tool-call decision, not a distinct authenticated approver. OTel audit is best-effort, not a tamper-proof ledger ([HITL](https://kagent.dev/docs/kagent/latest/agents/human-in-the-loop/), [audit](https://kagent.dev/docs/kagent/latest/observability/audit-prompts/)) | Keep room authorization and the append-only log |
| **Budgets and turn limits** | Usage reporting exists; cumulative spend/turn enforcement remains open ([kagent#2854](https://github.com/kagent-dev/kagent/issues/2854)) | agentgateway budgets remain |
| **OpenHands harness** | OpenHands is not a native harness; BYO requires gRPC A2A and has feature limitations | Keep OpenHands rather than add another adapter without a payoff |
| **Lifecycle** | Data snapshots preserve `/data`, not process memory. Mid-turn node loss can crash the Actor; `RevertSession` is not exposed in the CLI/UI | Does not replace our branch recovery and attended PVC suspend/resume |
| **Operations** | Kubernetes 1.37+, preview Substrate gates, PostgreSQL, snapshot storage, WorkerPools and coupled kagent/Substrate upgrades ([installation](https://kagent.dev/docs/kagent/latest/setup/installation/), [versions](https://kagent.dev/docs/kagent/latest/reference/versions/)) | More control planes and state to operate |
| **Factory and merge controls** | No replacement for GitHub intake, role sequencing, Kueue fairness, merge policy or stop controls | Maku and policy-bot remain |

## Why direct Substrate is also deferred

Substrate supplies most of the runtime benefits that make kagent attractive. Direct adoption behind
`AgentRun` avoids kagent's overlapping Session model and is therefore the better candidate if runtime
needs change.

Its incremental value over the current stack is specific:

- memory-preserving cross-node restore rather than reconstruction from a PVC and branch;
- golden-snapshot warm starts and potentially higher sandbox density;
- explicit snapshot/fork lifecycle and external credential injection.

The October spike supports feasibility, not adoption. OpenHands suspended, resumed and restored across
nodes with its conversation intact. It measured a 2.9-second p50 golden start and a 53.2-second
cross-node restore, but used Substrate v0.5.0 on GKE with a mock LLM rather than the complete
credentialed factory path ([spike](2026-10-17-substrate-spike.md)). The current platform has
PVC-backed attended suspend/resume and automatic branch recovery after node loss. Warm-pool adoption
remains a separate agent-sandbox track, so Substrate's golden starts are still a potential benefit.

The remaining bill is substantial:

- Actors are not Pods. Per-run ServiceAccounts, CiliumNetworkPolicies, restricted PSS and Kueue
  admission do not carry over literally ([architecture](https://github.com/agent-substrate/substrate/blob/4ee8f66ac237adfc3303086b12275aefc150fd6f/docs/concepts/architecture.md)).
- Workers require broad capabilities and cannot satisfy restricted PSS; the exemption would need
  dedicated nodes ([worker security](https://github.com/agent-substrate/substrate/blob/4ee8f66ac237adfc3303086b12275aefc150fd6f/docs/reference/api-guide.md#worker-security)).
- substrate#1660 delivered Actor JWT injection, but open substrate#2208 leaves certificate/cache
  confusion across same-name Actor recreation ([#2208](https://github.com/agent-substrate/substrate/issues/2208)).
- octo-sts injection needs a custom external credential provider. A direct in-Actor token exchange
  would expose the GitHub token response to untrusted code and potentially its snapshots.
- Substrate does not automatically suspend on worker SIGTERM. Durable boundaries require synchronous
  suspension, and abrupt node/Spot loss still needs proof ([eviction](https://github.com/agent-substrate/substrate/blob/4ee8f66ac237adfc3303086b12275aefc150fd6f/docs/reference/api-guide.md#eviction)).
- The AWS installer remains a PR, and current kagent CI documents kind/Kubernetes 1.35 while its
  installation requires 1.37+ ([#2241](https://github.com/agent-substrate/substrate/pull/2241),
  [versions](https://kagent.dev/docs/kagent/latest/reference/versions/)).
- PostgreSQL, snapshot storage, workers, runtime assets, version compatibility and garbage collection
  add a second runtime control plane without removing Maku or rooms.

There is no measured latency, recovery or density problem important enough to pay that bill now.

## Crossplane boundary if a future backend is justified

`AgentRun` remains the stable API. Maku would select an allowlisted Composition for each **new** run;
a live run would never change Composition. Flux would own installation and shared configuration,
Crossplane common per-run resources and one backend hand-off object, and each runtime controller its
own Pods, Workers, Actors or Sessions.

Crossplane must not mirror Substrate PostgreSQL rows or kagent-generated Sessions and Actors into a
Composition. That would create competing lifecycle owners. This is a future integration boundary, not
work approved by this evaluation.

## Reconsideration triggers

### Reopen direct Substrate only when both conditions hold

1. A measured cold-start, cross-node memory-continuity or density problem justifies a time-boxed PoC.
2. The candidate release demonstrates the target EKS and GKE path, safe per-run identity and octo-sts
   injection, Kueue-equivalent admission, controlled Spot loss, upgrades and garbage collection.

The PoC must compare against the complete current factory and show net code and operational removal,
not merely a successful Actor restore.

### Reconsider kagent when it additionally provides

- non-bypassable OSS authentication and deny-by-default authorization;
- attributed multi-participant sessions and distinct delegated approver evidence;
- a clean one-run/one-identity mapping and supported OpenHands/BYO restore;
- per-run credential, DNS/FQDN egress and Kueue integration;
- tested EKS/GKE upgrades with active and waiting runs;
- a net deletion of more custom code than the migration adds.

Until then, ADR-0041's agent-sandbox + gVisor + OpenHands choice stands, reaffirmed by ADR-0062.

## Primary references

- kagent [v1.0.0](https://github.com/kagent-dev/kagent/releases/tag/v1.0.0),
  [1.0 release notes](https://kagent.dev/docs/kagent/latest/reference/release-notes/1.0/) and
  [operations](https://kagent.dev/docs/kagent/latest/operations/operational-considerations/)
- Agent Substrate [v1.0.0-rc.3](https://github.com/agent-substrate/substrate/releases/tag/v1.0.0-rc.3),
  [security status](https://github.com/agent-substrate/substrate/blob/4ee8f66ac237adfc3303086b12275aefc150fd6f/docs/security/security.md)
  and [version skew](https://github.com/agent-substrate/substrate/blob/4ee8f66ac237adfc3303086b12275aefc150fd6f/docs/reference/version-skew-policy.md)
- Prior local records: [runtime design](2026-09-23-agent-runtime-identity-design.md),
  [Substrate spike](2026-10-17-substrate-spike.md) and
  [v4 landscape](2026-10-31-v4-landscape-research.md)
