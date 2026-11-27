---
title: "12. Automate repository upkeep"
linkTitle: "12. Upkeep routines"
weight: 12
description: "Run recurring repository maintenance inside bounded budgets, open-PR caps, and yield breakers from the Routines UI, CLI, or GitOps."
lastVerified: 2026-11-27
diataxis: how-to
---

Upkeep routines run recurring repository maintenance — broken links, failing Renovate pull requests,
documentation drift, unreachable code, flaky tests, and duplicated helpers — without competing with
human work or opening unbounded pull requests.

Every `Routine` object stays inert until a maintainer binds it under a repository's `spec.routines[]`.
Upkeep routines never auto-merge on their own: automatic merges still require a `live`
[merge policy]({{< relref "merge-policies.md" >}}). Full schemas and API contracts live in Maku's
[factory reference]({{< maku "docs/factory.md#upkeep-routines" >}}) and
[web UI reference]({{< maku "docs/reference/web-ui-settings.md#routines" >}}).

## Safety guardrails

| Guardrail | What it enforces |
|---|---|
| **Explicit opt-in** | Unbound `Routine` definitions never schedule or trigger runs |
| **Isolated upkeep budget** | Charged against `budgets.upkeepDailyUSD`, separate from interactive and human budgets |
| **Open PR cap and cooldown** | Skips slots once `maxOpenPRs` is reached or inside `cooldown` |
| **Zero-token probes** | `dead-links`, `renovate-red`, and `actions-findings` check deterministically before running a model |
| **Progressive modes** | Graduate from `propose` (read-only issue) to `draft` (draft PR) to `pr` |
| **Yield breaker** | Trips `half_open` or `paused` when merge rate drops or consecutive runs close or fail |

A `Repository` binding can only tighten a `Routine`'s ceilings (`maxOpenPRs`, `maxCostUSD`,
`cooldown`, `egress`, and breaker thresholds); widening any bound is refused at validation.

## Browse the catalog and enable a routine

Open **Routines** (`/routines`) in the rooms web UI and choose **Browse catalog** (`/routines/catalog`)
to inspect every shipped (`catalog`) and cluster-authored (`custom`) `Routine`.

![Routine catalog showing six starter routines with probe type, workflow, open-PR and cost ceilings, breaker rules, active consumers, and a target repository selector.](/images/screenshots/routines-catalog.png)

1. Pick your target repository in the selector.
2. Review each routine's probe, workflow, cost ceiling, and required fill-once parameters (`oracleClass` or `probeWorkflow`).
3. Click **Enable on repository →** (or **Configure on repository →** for an existing binding) to open the guided configurator.

## Configure mode, schedule, and prompt

The configurator (`/routines/<owner>/<repo>/<routine>/edit`) walks through delivery mode, UTC cron
schedule (with live local and UTC previews of the next three runs), bounds, and an optional
repository-owned prompt (placed in the target repository under .github/agent-factory/upkeep as
`<routine>.md`, validated live for size, sections, and a `## Verify` checklist).

![Guided Routine Configurator showing delivery mode cards, UTC cron schedule with next runs preview, bounds, split-view prompt editor, and Check and Generate YAML button.](/images/screenshots/routines-configurator.png)

1. Start in **Propose** or **Draft PR** until the routine produces consistent patches.
2. Click **Check & Generate YAML** to validate against the factory and copy or download the `Repository` manifest snippet for GitOps.
3. When an operator enables `routines.uiWrite: true`, **Save to cluster** persists UI-managed bindings into ConfigMap `agent-factory-routine-bindings` while keeping GitOps-declared bindings immutable in the cluster.

## Monitor yield and control runs

The **Routines** overview (`/routines`) sorts routines needing attention (`paused` or `half-open`)
first, displaying 14-day outcome sparklines, rolling merge rate, cost per merged PR, open PR count,
and the next scheduled run.

![Routines overview listing bound routines with 14-day outcome sparklines, merge rate, cost per merged PR, open PR counts, breaker badges, and Run now, Pause, and Configure buttons.](/images/screenshots/routines-overview.png)

Maintainers with GitHub write access can trigger **Run now** (with an optional one-shot mode override),
**Pause**, or **Resume**, or run the equivalent `maku routine list`, `maku routine run`, and
`maku routine pause|resume` commands from the terminal.

## Add a custom routine

Apply any `Routine` (`maku.ogenki.io/v1alpha1`) custom resource in the factory's namespace to add it
to the catalog as `custom`. Example (the reference host): the chart ships six starter routines
(`dead-links`, `renovate-red`, `doc-drift`, `dead-code`, `flaky-tests`, `dup-unifier`) with
`routines.catalog.enabled: true` and keeps `routines.uiWrite: false` so repository bindings stay in
GitOps (`tooling/base/agent-factory/resources/`).

## Check component versions and environment

Open **Settings** (`/settings`) to view the **Environment** panel below the section cards. It prints
the broker and factory versions (flagging version skew), factory name, namespace, sign-in mode,
default harness, merge policy stage, hardening mode, routines UI write setting, and active install notices.

![Settings home displaying the Merge policies, Evidence, and Approval memory cards above the Environment panel with broker and factory versions and cluster settings.](/images/screenshots/settings-environment.png)
