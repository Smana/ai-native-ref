---
title: Status and roadmap
aliases:
  - /docs/platform/ai-platform/status/
linkTitle: Status
weight: 60
description: "What is proven live, what awaits validation, what is in progress, and what is planned next."
activeCluster: aws-0
lastVerified: 2026-11-16
---

Use this page to see what the platform can do and what is coming next. **Proven live** means
demonstrated end to end on a real cluster; it does not describe the current deployment.

**Current release:** the Agent Factory [v3.0.0](https://github.com/Smana/ai-native-ref/releases/tag/v3.0.0).
**On `main`:** Maku {{< maku-version >}} for every component.

For installation, upgrades, restoration, and cluster operations, see
[Day-2 operations]({{< relref "/docs/operate/day-2.md" >}}).

<span id="clusters"></span><span id="rebuild"></span><span id="roadmap"></span><span id="v2-roadmap"></span>

## Highlights

{{< cards >}}
  {{< card link="#landed" title="From issue to pull request" icon="cog" subtitle="Maku plans, implements, reviews, and merges changes with per-run identity and budgets." >}}
  {{< card link="#landed" title="Safety by default" icon="shield-check" subtitle="A gVisor sandbox, scoped tokens, network policy, repository checks, and recovery." >}}
  {{< card link="#landed" title="Work with agents" icon="chat-alt-2" subtitle="Rooms, Slack, coding agents, and RunLore: follow, steer, and approve." >}}
  {{< card link="#landed" title="Automation with guardrails" icon="refresh" subtitle="Review gates, approve-to-merge, a regression breaker, and drills." >}}
  {{< card link="#landed" title="Models and spend" icon="currency-dollar" subtitle="Model routing, provider choice, caching, budgets, and cost by role." >}}
  {{< card link="#landed" title="Proof, not promises" icon="beaker" subtitle="Every available capability links to its live evidence." >}}
{{< /cards >}}

## Proven live {#landed}

These capabilities were demonstrated end to end on a real cluster.

| Capability | Evidence |
|---|---|
| A labelled issue becomes a reviewed pull request, with the run-controller, broker, factory, gateway, CRDs, and Slack app from Maku releases | [End-to-end run](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/07-end-to-end.md), [runtime]({{< relref "/docs/how-it-works/runtime.md" >}}) |
| Sandboxed runs have their own model and GitHub tokens, network policy, and egress controls | [Runtime]({{< relref "/docs/how-it-works/runtime.md" >}}), [run-controller proof](https://github.com/Smana/ai-native-ref/pull/383) |
| People follow, steer, and approve in attended rooms; private-repository access follows GitHub permissions and the account link | [Rooms]({{< relref "/docs/how-it-works/rooms.md" >}}), [private repositories](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/11-v1-validation.md) |
| A run lost to infrastructure resumes from its branch | [Disruption recovery](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/10-disruption.md) |
| Link fixes and their reverts can merge without a person; a regression pauses the class until clean merges restore it | [Auto-merge and breaker](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md), [results](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-aws-0-2026-10-30.md) |
| A maintainer can approve the current head to merge it | [Approve-to-merge results](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-aws-0-2026-10-30.md) |
| Scoping, completion judging, repository checks, test-first contracts, and splitting guide the implementation | [Scoper](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md#layer-1-the-scoper), [judge and checks](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md#layer-2-the-loop-policy), [tester](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/21-test-first-tester.md), [splitter](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/17-splitter.md) |
| Slack and coding agents can start and follow work | [Slack](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/22-slack.md), [coding agents](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/19-factory-from-your-agent.md) |
| RunLore can investigate an alert, ship a fix, and record reviewed knowledge | [Agent to agent](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/20-runlore-agent-to-agent.md), [knowledge base](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/25-runlore-kb-phase-1.md) |
| Model calls are authenticated, routed, and metered; Claude is available for internal work, and Kimi and Mistral for public work | [agentgateway]({{< relref "/docs/decisions/0053-agent-router-on-agentgateway.md" >}}), [providers]({{< relref "/docs/how-it-works/providers.md" >}}) |
| Gateway budgets, cache alerts, and cost by role or charged identity make spend visible | [Budgets and cache](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md), [cost cross-check](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-g--the-cost-cross-check) |

<span id="class-modes"></span>

Only link fixes and their reverts currently merge without a person. Other classes are being evaluated
in shadow, and every other change still requires review.

## Implemented, awaiting validation {#experimental}

Built, but either switched off, limited to a small scope, or waiting for live evidence.

| Capability | Current state |
|---|---|
| Agent search and self-hosted model serving | Search benefit is unmeasured; serving is off by default. [Search](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md#layer-4-the-search-tool), [serving]({{< relref "/docs/how-it-works/serving/_index.md" >}}) |
| Merge policies declared in a repository | Repository-file decisions and remembered approvals are built and off. [UX review](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-08-merge-policy-ux-review.md) |
| Conversational UX | The needs list, return brief, Slack push approval, and animated run view need live proof. Slack's proposal message works live. [Following and steering]({{< relref "/docs/use/guide/following-and-steering.md" >}}) |
| RunLore knowledge search from a room | The incident-to-entry loop is proven; `kb_search` still needs its live check. [Runbook](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/25-runlore-kb-phase-1.md) |
| Settings as objects and team evaluation profiles | Both are built and need live proof. [Factory configuration]({{< relref "/docs/reference/factory-configuration.md" >}}) |
| Multi-repository integration runtime | Exact-commit worktrees and the typed integration result are built and inert. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-05-v4-multi-repo-coordination-design.md) |
| Untrusted-input hardening | H0's contracts are built and switched off. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-07-untrusted-input-hardening-design.md) |
| The factory on a laptop | The Maku demo and quickstart are built; outside-user validation remains. [Quickstart]({{< maku "docs/quickstart.md" >}}) |
| Per-person caps and more auto-merge classes | Daily caps are counted in shadow; additional classes are evaluated before promotion. [Caps](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-c--per-person-caps-the-shadow-week), [classes](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/16-deps-patch.md) |

## In progress {#v3x}

<span id="in-progress"></span>

| Work | Where it stands |
|---|---|
| Merge policies declared in a repository | Stages 1–3 and 6 are on. Stages 4 and 5 are built and off; central guardrails and generated policy-bot rules remain. [Guide]({{< relref "/docs/use/guide/merge-policies.md" >}}) |
| Slack and room conversations | The proposal works live. Thread answers, the needs list, return briefs, and push approval are being proven. [Slack]({{< relref "/docs/use/slack.md" >}}) |
| Multi-repository execution | Planning is on. Execution stays blocked until repository merge policies and untrusted-input hardening ship. [Multi-repository]({{< relref "/docs/use/guide/multi-repository.md" >}}) |
| Untrusted-input hardening | H1–H5 follow H0: audit, enforced non-code outputs, enforced pushes, filtered reads, and readiness. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-07-untrusted-input-hardening-design.md) |
| Workflow and model trials | Live traffic will compare quick, standard, and careful workflows, then role effort and model choices, using cost per merged pull request and merge rate. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-workflows-review-design.md) |

## Next plans {#later}

<span id="v4"></span><span id="v4-core"></span><span id="v4-increments"></span><span id="serving-roadmap"></span>

| Plan | Why it matters |
|---|---|
| **OpenCode as a second harness** | Evaluate OpenCode beside OpenHands without changing the default; replacement requires parity and measured benefit. [Specification and plans](https://github.com/Smana/ai-native-ref/pull/404) |
| Outcome analytics and reviewer calibration | Compare merge rate, rework, reverts, duration, and cost by class, model, role, and repository. |
| Verification on real services and a review inbox | Test real dependencies before a pull request and give maintainers one risk-ranked review queue. |
| Continuation loop, event triggers, and fleet campaigns | Fix CI and reviews, start work from alerts or schedules, and roll a change out across repositories. |
| Signed provenance and reviewed repository memory | Attest how a change was produced and capture what agents learn as reviewed instructions. |
| Gemini as a provider | Add another public-work model with its own capability profile and cost checks. |
| Serving improvements | GPU sharing, larger or denser models, and cost per tenant, each with its own measured trigger. [Serving]({{< relref "/docs/how-it-works/serving/_index.md" >}}) |
| v4: anyone can run it | Production installation and upgrades are deferred with no date set; the laptop demo is built. [Quickstart]({{< maku "docs/quickstart.md" >}}) |
| Eval bench and open-weight bake-off | Fixed issues will compare acceptance and cost per accepted pull request when funded. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-22-eval-bench-design.md) |

## Known limitations {#before-v3}

- A judge can quote a CI log only when the sandbox's egress policy allows GitHub's Actions log host.
- Some final costs settle after the task status is written ([maku#279](https://github.com/Smana/maku/issues/279), [maku#280](https://github.com/Smana/maku/issues/280)); a few approval-binding edge cases remain ([maku#304](https://github.com/Smana/maku/issues/304)).
- Mistral can spend an entire run budget on a small change, so it is not recommended as the implementer.
- Semantic Router decisions are not yet available as VictoriaMetrics series.

<span id="dark-factory"></span>

<!-- Validation size fixture: 01 -->
<!-- Validation size fixture: 02 -->
<!-- Validation size fixture: 03 -->
<!-- Validation size fixture: 04 -->
<!-- Validation size fixture: 05 -->
<!-- Validation size fixture: 06 -->
<!-- Validation size fixture: 07 -->
<!-- Validation size fixture: 08 -->
<!-- Validation size fixture: 09 -->
<!-- Validation size fixture: 10 -->
<!-- Validation size fixture: 11 -->
<!-- Validation size fixture: 12 -->
<!-- Validation size fixture: 13 -->
<!-- Validation size fixture: 14 -->
<!-- Validation size fixture: 15 -->
<!-- Validation size fixture: 16 -->
<!-- Validation size fixture: 17 -->
<!-- Validation size fixture: 18 -->
<!-- Validation size fixture: 19 -->
<!-- Validation size fixture: 20 -->
<!-- Validation size fixture: 21 -->
<!-- Validation size fixture: 22 -->
<!-- Validation size fixture: 23 -->
<!-- Validation size fixture: 24 -->
<!-- Validation size fixture: 25 -->
<!-- Validation size fixture: 26 -->
<!-- Validation size fixture: 27 -->
<!-- Validation size fixture: 28 -->
<!-- Validation size fixture: 29 -->
<!-- Validation size fixture: 30 -->
<!-- Validation size fixture: 31 -->
<!-- Validation size fixture: 32 -->
<!-- Validation size fixture: 33 -->
<!-- Validation size fixture: 34 -->
<!-- Validation size fixture: 35 -->
<!-- Validation size fixture: 36 -->
<!-- Validation size fixture: 37 -->
<!-- Validation size fixture: 38 -->
<!-- Validation size fixture: 39 -->
<!-- Validation size fixture: 40 -->
<!-- Validation size fixture: 41 -->
<!-- Validation size fixture: 42 -->
<!-- Validation size fixture: 43 -->
<!-- Validation size fixture: 44 -->
<!-- Validation size fixture: 45 -->
<!-- Validation size fixture: 46 -->
<!-- Validation size fixture: 47 -->
<!-- Validation size fixture: 48 -->
<!-- Validation size fixture: 49 -->
<!-- Validation size fixture: 50 -->
<!-- Validation size fixture: 51 -->
<!-- Validation size fixture: 52 -->
<!-- Validation size fixture: 53 -->
<!-- Validation size fixture: 54 -->
<!-- Validation size fixture: 55 -->
<!-- Validation size fixture: 56 -->
<!-- Validation size fixture: 57 -->
<!-- Validation size fixture: 58 -->
<!-- Validation size fixture: 59 -->
<!-- Validation size fixture: 60 -->
<!-- Validation size fixture: 61 -->
