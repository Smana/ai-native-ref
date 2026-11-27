---
title: Status and roadmap
aliases:
  - /docs/platform/ai-platform/status/
linkTitle: Status
weight: 60
description: "What is proven live, what awaits validation, what is in progress, and what is planned next."
activeCluster: gcp-0
lastVerified: 2026-11-27
---

Use this page to see what the platform can do and what is coming next. **Proven live** means
demonstrated end to end on a real cluster; it does not describe the current deployment.

**Current release:** the Agent Factory [v4.0.0](https://github.com/Smana/ai-native-ref/releases/tag/v4.0.0): the factory runs on its own, without our cluster's Crossplane, Kueue or octo-sts, and you drive it in plain words from a coding agent or Slack. [Watch a real run](https://blog.ogenki.io/maku/).
**On `main`:** Maku {{< maku-version >}} for every component.

For installation, upgrades, restoration, and cluster operations, see
[Day-2 operations]({{< relref "/docs/operate/day-2.md" >}}).

{{< partner-card >}}

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
| A coding agent hands work off in plain words and a form confirms it; the merge gate chooses a policy from the diff, in shadow | [v4 validation](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/28-v4-aws-validation.md), [results](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-aws-0-2026-11-16.md), [screencast](https://blog.ogenki.io/maku/) |
| Gateway budgets, cache alerts, and cost by role or charged identity make spend visible | [Budgets and cache](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md), [cost cross-check](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-g--the-cost-cross-check) |
| A run reaches GitHub's release-download hosts only while its pinned toolchain installs, before the agent starts; the closed window refuses later downloads | [GitHub egress drill](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/31-github-egress-drill.md), [results](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-github-egress-drill-2026-11-27.md) |
| Upkeep routines catalog, `/routines` UI, preview/ceiling validation, and `/settings` environment and version panel run live with least-privilege RBAC | [Upkeep routines]({{< relref "/docs/use/guide/upkeep-routines.md" >}}), [Maku v0.58.0](https://github.com/Smana/maku/releases/tag/v0.58.0) |

<span id="class-modes"></span>

Only link fixes, and the factory's reverts of them, currently merge without a person. Other classes are being evaluated
in shadow, and every other change still requires review.

## Implemented, awaiting validation {#experimental}

Built, but either switched off, limited to a small scope, or waiting for live evidence.

| Capability | Current state |
|---|---|
| Agent search and self-hosted model serving | Search benefit is unmeasured; serving is off by default. [Search](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/README.md#layer-4-the-search-tool), [serving]({{< relref "/docs/how-it-works/serving/_index.md" >}}) |
| Merge policies declared in a repository | Repository-file decisions and remembered approvals are built and off. [UX review](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-08-merge-policy-ux-review.md) |
| Conversational UX | The needs list, return brief, Slack push approval, and animated run view need live proof. Slack's proposal message works live. [Following and steering]({{< relref "/docs/use/guide/following-and-steering.md" >}}) |
| RunLore knowledge search from a room | The incident-to-entry loop is proven; `kb_search` failed its live check on an invalid gateway key and needs a rerun. [Runbook](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/25-runlore-kb-phase-1.md) |
| Settings as objects and team evaluation profiles | Both are built and need live proof. [Factory configuration]({{< relref "/docs/reference/factory-configuration.md" >}}) |
| Multi-repository integration runtime | Exact-commit worktrees and the typed integration result are built and inert. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-05-v4-multi-repo-coordination-design.md) |
| Untrusted-input hardening | H0's contracts are built and switched off. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-07-untrusted-input-hardening-design.md) |
| The factory on a laptop | The Maku demo and quickstart are built; outside-user validation remains. [Quickstart]({{< maku "docs/quickstart.md" >}}) |
| Workflows as stage lists, one step up, and custom read-only roles | On: a `standard` task that fails runs once more as `careful`, and a `thorough` workflow adds a security reviewer. Needs live proof. [Harness reference]({{< relref "/docs/reference/harness.md#templates" >}}) |
| Plan first, review only and findings only | On, with acts on the room page and whole multi-issue plans filed at once. Needs live proof. [Scope and split]({{< relref "/docs/how-it-works/factory.md" >}}) |
| Promotion by pull request and the factory's own reverts | The promotion button opens its pull request on one repository's manifest; reverts of an unattended merge merge themselves. Needs live proof. [Merge policies]({{< relref "/docs/use/guide/merge-policies.md#promote-a-policy" >}}) |
| OpenCode, the default harness | Every unlabelled task runs on OpenCode since 2026-11-27, the owner's decision ahead of the 30-per-arm trial; a maintainer's `harness:openhands` label runs one task on OpenHands, and a task pinned to a Gemini/Vertex alias runs on OpenHands, with one comment on the issue saying so (Smana/maku#798). [Harness reference]({{< relref "/docs/reference/harness.md#composition" >}}) |
| Gemini on Vertex AI | `gemini-standard` and `gemini-light` serve public work on `gcp-0` only, with the gateway's own Workload Identity (no key) and metered at list price. The integration test passed; the comparison against `agent-default` is deferred, and the planner stays on Z.ai (Gemini missed its 20 s deadline). [Providers]({{< relref "/docs/how-it-works/providers.md" >}}), [results](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-gcp-0-gemini-2026-11-27.md) |
| Developer additions from Maku v0.56–v0.58 | A pull request that conflicts with main gets one rebase run; the pull request body ends with **Try it**; `maku why` and `maku help`; the **New task** picker lists every served repository; `maven` and `node` egress profiles; a repository's own runtime image and size. Built and pinned; each needs live proof. [Cheat sheet]({{< relref "/docs/use/guide/cheat-sheet.md" >}}) |
| Developers with write access start tasks | Maku's `access.start: write` is built and off here: it takes effect only once per-person caps are enforced. [Factory configuration]({{< relref "/docs/reference/factory-configuration.md" >}}) |
| Per-person caps and more auto-merge classes | Daily caps are counted in shadow; additional classes are evaluated before promotion. [Caps](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-c--per-person-caps-the-shadow-week), [classes](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/16-deps-patch.md) |
| Upkeep routines scheduled runs and yield breaker | All six starter `Routine` objects are accepted and inert on `gcp-0` with `/routines`, catalog, preview validation, and `routines.uiWrite: false` active; binding routines on repositories to measure live merge yield and breaker trips is next. [Upkeep routines]({{< relref "/docs/use/guide/upkeep-routines.md" >}}) |
| Harness visual verification and service sidecars | On: `ai-native-ref`'s implementer and tester runs get a loopback browser and keep their screenshots in the room, and `image-gallery`'s runs get a loopback Postgres, empty at each start. Both need live proof ([runbook 33](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/33-browser-verification.md)). [Browser verification]({{< maku "docs/browser-verification.md" >}}), [repository ready]({{< relref "/docs/use/make-your-repository-ready.md#services" >}}) |

## In progress {#v3x}

<span id="in-progress"></span>

| Work | Where it stands |
|---|---|
| Merge policies declared in a repository | Stages 1–3 and 6 are on. Stages 4 and 5 are built and off; central guardrails and generated policy-bot rules remain. [Guide]({{< relref "/docs/use/guide/merge-policies.md" >}}) |
| Slack and room conversations | The proposal works live. Thread answers, the needs list, return briefs, and push approval are being proven. [Slack]({{< relref "/docs/use/slack.md" >}}) |
| Multi-repository execution | Planning is on. Execution stays blocked until repository merge policies and untrusted-input hardening ship. [Multi-repository]({{< relref "/docs/use/guide/multi-repository.md" >}}) |
| Untrusted-input hardening | H1–H5 follow H0: audit, enforced non-code outputs, enforced pushes, filtered reads, and readiness. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-07-untrusted-input-hardening-design.md) |
| Workflow and model trials | The comparison is built; the reference trial was turned off ([#414](https://github.com/Smana/ai-native-ref/pull/414)) before it recorded a task. It will compare quick, standard, and careful workflows by cost per merged pull request and merge rate. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-14-workflows-review-design.md) |

## Next: v5, proven in the field {#v5}

v4 lets anyone run the factory. v5 proves Maku with one external GitHub and Kubernetes team on its own private repositories — as an Apache-2.0 open-source collaboration (bootstrap support, with optional freelance integration days) rather than a commercial product.

| Goal | What it takes |
|---|---|
| **Pre-pitch readiness** | Private-repository planning, Tier-1 hardened bundled PostgreSQL (PVC, TLS, automatic three-role bootstrap, optional S3 backups) plus a one-step Tier-2 CNPG or external-database bootstrapper, one recorded generic Kubernetes Helm install, outside-user laptop quickstart checks ([Quickstart]({{< maku "docs/quickstart.md" >}})), a standalone `Smana/maku` front door, a two-minute real-run video, and a static room replay. |
| **External team pilot on private repositories** | One GitHub and Kubernetes team runs a Tier-1 Pilot (one GitHub App, shadow merge gate, bundled PostgreSQL, standard OIDC/Ingress or Slack Socket Mode, mandatory gVisor) and lands at least ten merged pull requests. Hardening (H1–H5), team RBAC (`write` access and GitHub Teams), and per-repository runtime images land alongside the team's stack. [Get in touch](https://blog.ogenki.io/about/) |
| **Pluggable harnesses** | OpenCode is the default and OpenHands the fallback (since 2026-11-27); next, OpenCode on Gemini/Vertex once agentgateway translates exclusive schema bounds, the weekly cost and merge-rate read against OpenHands, and best-effort bring-your-own Claude Code. |
| **Upkeep routines in production** | Bind starter and custom routines (`dead-links`, `renovate-red`, `doc-drift`, and repository-specific hygiene) across `propose` → `draft` → `pr`, track rolling merge yield and `$/merged` via the weekly Slack upkeep digest, and prove the yield breaker live ([Upkeep routines]({{< relref "/docs/use/guide/upkeep-routines.md" >}})). |
| **Slack security model and Socket Mode** | Evolve the Slack app to personal-bound principals over one workspace bot (no personal Slack user tokens): direct-message intake with dynamic per-user repository access and per-person USD budgets, strict author-only thread isolation, Socket Mode as the zero-public-ingress default, and broker-verified `X-Slack-Signature` closing the Slack deputy residual in Events API mode while keeping live steering on the room page. |
| **Spec-driven development intake** | Ingest open markdown specs (GitHub Spec Kit, OpenSpec, or EARS sections in issues or `specs/`) natively when present, falling back to a minimal compatible Maku spec written by the planner and scoper. |
| **Outcome analytics and live merge proof** | Join merge rate, revert rate, human wait time, and USD cost per merged pull request into one view by repository, policy, model, and workflow; prove at least one class beyond `docs-links` (`deps-patch` or `docs`) live with a revert drill and a second-family reviewer ([ADR-0058]({{< relref "/docs/decisions/0058-reviewer-on-another-model.md" >}})). |
| **Time-boxed `kagent` and Agent Substrate check** | After the first external team pilot ships, run a strict two-day check against [ADR-0062]({{< relref "/docs/decisions/0062-agent-runtime-remains-agent-sandbox.md" >}})'s reconsideration triggers, then adopt, borrow, or keep deferring each. |

## Next plans {#later}

<span id="v4"></span><span id="v4-core"></span><span id="v4-increments"></span><span id="serving-roadmap"></span>

| Plan | Why it matters |
|---|---|
| PR continuation loop, cloud-to-local takeover, and review inbox | Partner-triggered v5.x fast-follows: fix inline review comments and merge conflicts, pull stalled runs locally (`maku takeover`), and give maintainers one risk-ranked review queue. |
| Reviewer calibration and verification on real services | Measure judge and reviewer agreement against real merge outcomes and test live dependencies before opening a pull request. |
| GitLab, Jira, and Linear integrations | Deferred until after PoC #1 proves the core GitHub and Kubernetes loop. |
| Event triggers and fleet campaigns | Start work from CI failures, alerts, or schedules, and roll a change out across repositories once hardening is live. |
| Signed provenance and reviewed repository memory | Attest how a change was produced and capture what agents learn as reviewed instructions. |
| Gemini comparison | Rerun Gemini's roles at a lower reasoning effort, then the paired comparison against `agent-default` under its frozen rule. [Results](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/results-gcp-0-gemini-2026-11-27.md#to-resume-later) |
| OpenCode on Vertex | Run OpenCode on a Gemini alias once agentgateway translates its tool schemas' exclusive bounds (tracked in [maku#798](https://github.com/Smana/maku/issues/798)). |
| An in-cluster Go module proxy | Give runs one in-cluster `GOPROXY` as their only route to Google Cloud Storage, then drop it from the `golang` profile (tracked in [maku#808](https://github.com/Smana/maku/issues/808)). |
| CI logs through the room tools | A run reads a failing Actions job's log server-side, since runs cannot reach GitHub's log storage (tracked in [maku#804](https://github.com/Smana/maku/issues/804)). |
| A run's harness event log after its pod is gone | Keep the log so a stalled run can be diagnosed (tracked in [maku#801](https://github.com/Smana/maku/issues/801)). |
| Pins on a review-only task | Honour `model:` and `harness:` labels on a `factory/review` task (tracked in [maku#797](https://github.com/Smana/maku/issues/797)). |
| Serving improvements | GPU sharing, larger or denser models, and cost per tenant, each with its own measured trigger. [Serving]({{< relref "/docs/how-it-works/serving/_index.md" >}}) |
| Dedicated Maku documentation site | Keep `Smana/maku`'s README and docs as the standalone front door through PoC #1; spin up a dedicated site only after field validation. |
| Eval bench and open-weight bake-off | Fixed issues will compare acceptance and cost per accepted pull request when funded. [Design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-22-eval-bench-design.md) |

## Known limitations {#before-v3}

- The planner reads public repositories only; for a private repository, file the issue on GitHub.
- A judge can quote a CI log only when the sandbox's egress policy allows GitHub's Actions log host ([maku#804](https://github.com/Smana/maku/issues/804)).
- A queued task whose issue was closed still starts ([maku#811](https://github.com/Smana/maku/issues/811)).
- A `factory/ready` label on a repository the factory does not serve gets no answer ([maku#784](https://github.com/Smana/maku/issues/784)).
- Some final costs settle after the task status is written ([maku#279](https://github.com/Smana/maku/issues/279), [maku#280](https://github.com/Smana/maku/issues/280)); a few approval-binding edge cases remain ([maku#304](https://github.com/Smana/maku/issues/304)).
- Mistral can spend an entire run budget on a small change, so it is not recommended as the implementer.
- Semantic Router decisions are not yet available as VictoriaMetrics series.

<span id="dark-factory"></span>
