---
title: Keep agent-sandbox and OpenHands; defer both kagent and Agent Substrate
linkTitle: 0062 · Agent runtime reaffirmed
weight: 620
description: Accepted. kagent 1.0 and Agent Substrate improve isolation, identity, egress and snapshot lifecycle, but neither removes enough of the existing factory to justify another control plane. agent-sandbox + gVisor + OpenHands remains the runtime. No migration or proof of concept is approved; measured runtime pain and explicit security, operability and net-simplification triggers gate reconsideration.
lastVerified: 2026-11-11
---

**Status**: Accepted; partly superseded
**Partly superseded** (2026-11-14): agent-sandbox as the runtime. Since R3, Maku's run-controller runs each run as its own gVisor pod. Deferring kagent and Agent Substrate stands.
**Date**: 2026-11-11
**Deciders**: Smana (Platform Owner)
**Related**: [ADR-0041]({{< relref "/docs/decisions/0041-agent-sandbox-gvisor-al2023.md" >}}), [ADR-0044]({{< relref "/docs/decisions/0044-room-session-protocol.md" >}}), [ADR-0053]({{< relref "/docs/decisions/0053-agent-router-on-agentgateway.md" >}}), [kagent evaluation](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-04-kagent-evaluation-research.md)

---

## Context

kagent 1.0 is a clean-break rewrite on its Agent Substrate fork. It adds A2A Sessions, immutable Agent
revisions, native Claude Code and Codex harnesses, Actor JWTs, default-deny egress, gateway credential
injection, checkpoints and automatic turn-boundary suspension. These changes make the October alpha
evaluation partly stale.

The current platform has also moved on. agent-sandbox supplies PVC-backed attended suspend/resume,
while the factory already recovers interrupted work from its branch and room log. Warm-pool adoption
remains a separate agent-sandbox track. The question is therefore not whether kagent 1.0 is credible.
It is whether kagent or direct Substrate
removes enough cost and custom code to justify replacing the current runtime.

---

## Decision Drivers

- Preserve per-run identity, default-deny egress, resource admission and restricted workload policy
- Keep humans, agents and approvers distinct in an ordered, attributable room log
- Keep short-lived provider and GitHub credentials outside untrusted code and snapshots
- Run on EKS and GKE, including controlled node and Spot loss
- Prefer open-source, non-bypassable authorization over perimeter-only containment
- Require a measured runtime need and net operational simplification before migration

---

## Considered Options

### Option 1: Retain agent-sandbox + gVisor + OpenHands

One Pod per run preserves the existing ServiceAccount, CiliumNetworkPolicy, restricted-PSS and Kueue
models. Maku, rooms, agentgateway, octo-sts and policy-bot remain the surrounding controls.

**Pros**:
- Lowest migration and operational cost; no additional lifecycle or persistence plane
- Existing attended suspend/resume and branch recovery cover current requirements; warm-pool work can
  continue on the same runtime
- Crossplane continues to compose the complete per-run security boundary

**Cons**:
- Cold starts and reconstruction are slower than Substrate's best golden-snapshot result
- Process memory does not survive Pod replacement
- The identity proxy and current recovery machinery remain ours to operate

### Option 2: Adopt upstream Agent Substrate directly behind `AgentRun`

Substrate multiplexes isolated Actors over warm workers and supports richer snapshots, forks and
external credential injection without kagent's Session layer.

**Pros**:
- Memory-preserving restore, golden starts and possible density gains
- A future backend can fit behind the existing `AgentRun` abstraction
- Direct upstream adoption avoids kagent's Session-per-Actor mapping and pinned fork

**Cons**:
- Actors are not Pods: ServiceAccounts, Cilium policy, restricted PSS and Kueue need new mappings
- Per-run octo-sts injection needs a custom provider; Actor identity still has an open recreation and
  cache-confusion issue
- PostgreSQL, snapshot storage, workers and versioned runtime assets add a second runtime control plane
- EKS installation, Spot recovery, upgrades and garbage collection remain unproven for our full factory

### Option 3: Adopt kagent + its Substrate fork behind `AgentRun`

kagent adds Agent, Harness and Session APIs on top of Substrate.

**Pros**:
- Packaged A2A/MCP agent management, checkpoints, revisions and native coding harnesses
- Strong Actor authentication and useful default-deny egress

**Cons**:
- OSS still defaults to caller-selected identity and permissive authorization
- One-Agent Sessions and read-only shares do not replace attributed rooms or delegated approvers
- No cumulative budget enforcement; agentgateway remains
- OpenHands requires a BYO A2A adapter, and automatic Data-only turn snapshots differ from `AgentRun`
  lifecycle semantics
- Adds kagent's database and coupled kagent/Substrate upgrades without removing Maku, rooms or the
  factory

---

## Decision Outcome

**Choose Option 1.** ADR-0041 remains in force. There is **no kagent or Substrate migration and no
runtime proof of concept at this time**.

Direct Substrate is the first candidate to reassess if a measured cold-start, memory-continuity or
density requirement emerges. kagent follows only if its additional agent-management layer would then
delete more custom code than it adds.

### Crossplane boundary for any future candidate

`AgentRun` stays the stable interface. Maku would select an allowlisted Composition for each new run;
live runs would never change Composition. Flux owns installation and shared configuration, Crossplane
owns common per-run resources and one backend hand-off, and runtime controllers own their generated
resources. Crossplane must not reconcile backend-generated Actors, Sessions or database rows.

This records an integration boundary only. It does not approve a new Composition or Maku change.

### Reconsideration triggers

Reopen **direct Substrate** when a measured runtime problem justifies a PoC and the candidate release
can demonstrate:

- the target EKS and GKE installation and upgrade paths;
- safe per-run identity, including Actor recreation, and external octo-sts injection;
- per-run DNS/FQDN egress and Kueue-equivalent admission;
- controlled node/Spot loss without lost or duplicated side effects;
- finalizer-backed cleanup and a net operational/code reduction.

Reconsider **kagent** only when it additionally has:

- non-bypassable OSS authentication and deny-by-default authorization;
- attributed multi-participant sessions and distinct delegated approver evidence;
- supported OpenHands/BYO restore and a clean one-run/one-identity mapping;
- a demonstration that it deletes more custom code than its adapters and operations add.

---

## Consequences

### Positive

- Avoids two unnecessary runtime control planes and their databases, snapshot stores and upgrade
  coupling
- Preserves the existing per-run security and admission model
- Prevents a second session and approval model from weakening room attribution

### Negative

- Does not capture Substrate's potential golden-start, memory-restore or density benefits
- Retains the current identity proxy and recovery code
- Requires another evidence-based review if those limitations become measured product problems

### Neutral

- kagent and Substrate remain watched alternatives, not planned dependencies
- Existing warm-pool, suspend/resume and recovery improvements continue on agent-sandbox

---

## References

- [kagent v1.0.0](https://github.com/kagent-dev/kagent/releases/tag/v1.0.0)
- [kagent identity](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/identity/)
- [kagent Session lifecycle](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/suspend-and-resume/)
- [Agent Substrate v1.0.0-rc.3](https://github.com/agent-substrate/substrate/releases/tag/v1.0.0-rc.3)
- [Substrate security status](https://github.com/agent-substrate/substrate/blob/4ee8f66ac237adfc3303086b12275aefc150fd6f/docs/security/security.md)
- [Substrate OpenHands spike](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-17-substrate-spike.md)
