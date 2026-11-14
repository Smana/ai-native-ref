---
title: Planner settings
weight: 17
description: "Every setting of the planner a room broker runs: the route it calls, the model it may name, the repositories it may plan for, and the class table its roles and money come from."
lastVerified: 2026-11-14
---

The planner turns what you asked for into a [plan]({{< relref "/docs/use/guide/terminal-and-coding-agent.md#handoff" >}}):
one repository with its evidence, one to three issues, the roles that will run and the ceiling the
work is charged against. Its settings are one block of the room broker's config file,
`human.intake.plan` in `infrastructure/base/room-broker/config.yaml`.

Every value below is the reference host's. Repositories are `owner/name`; dollars are ceilings, not
prices.

| Key | Example value | What it does | Bounds |
|---|---|---|---|
| `enabled` | `false` | Serves the planner's two tools; off, both answer `unknown tool` | `true` or `false` |
| `url` | `http://model-gateway.agent-gateway.svc.cluster.local:8082/clients/planner/v1` | The model gateway's planner route, on its `clients` listener, where the one model call goes. The gateway admits only the broker's ServiceAccount there and maps `tier-frontier` to Z.ai `glm-5.3` | An absolute `http(s)://` URL, no credentials in it |
| `model` | `tier-frontier` | The model the plan call names | `tier-frontier`, and nothing else |
| `apiKeyFile` | `/var/run/secrets/maku/model-gateway/planner` | The broker's projected ServiceAccount token, audience `maku-gateway.client.planner`, mounted by the chart's `broker.modelGateway`. It is read at each call, so the kubelet's hourly rotation needs no restart | A path the broker already mounts |
| `deadline` | `20s` | How long the one call may take | Above 0, at most 20 s |
| `reasoningEffort` | `low` | Sent as the call's `reasoning_effort`; unset sends nothing. Set it for a model that always reasons, or a plan can outlast the deadline | `low`, `medium`, `high`, or unset |
| `dailyPlans` | `50` | Plans one person may ask for per day | At least 1 |
| `fallback` | `"off"` | Whether a deterministic draft stands in when no model answers | `off` or `composer` |
| `repositories` | `[Smana/ai-native-ref]` | The allowlist: the only repositories a plan may name | `owner/name`, each listed once |
| `classes` | see [the class table](#classes) | Per class: the roles a plan carries and the money it may cost | A class the factory serves |

## The class table {#classes}

A plan assigns each issue one class, and the class — not the model — decides the roles and the
ceiling. The broker checks the model's choice against this table and refuses a class it does not
hold, so a class here that no served repository has is a plan nobody can run.

Example (the reference host):

```yaml
      classes:
        docs-links: {roles: [scoper, implementer, reviewer], ceilingUSD: 2.00, source: "class:docs-links.taskUSD"}
```

| Field | What it is | Bounds |
|---|---|---|
| `roles` | The roles that run for this class, in order | Roles the factory has; no duplicates |
| `ceilingUSD` | The most this plan's work may cost | Above 0, at most the default tier's `taskUSD` |
| `source` | Where the ceiling came from, as the plan shows it | `class:<this class>.taskUSD`, or `channel:maxCostUSD` |

The ceiling is a cap to charge against, not a reservation: the runs it bounds are the factory's, and
their spend is counted as every other task's. A ceiling above the tier's own `taskUSD` would promise
money the factory does not have, which is why the tier is the upper bound.

## Multi-repository coordination {#coordination}

`coordination.mode`, a top-level key of the same config file, serves `coordination_plan`: one change
across two public repositories, planned through the same route, guard and daily count as above. Both repositories must be in
`repositories`.

| Value | What it does |
|---|---|
| `off` (the default) | Lists no tool |
| `plan` | Composes and validates a two-repository plan, with its hash; files nothing |
| `execute` | Plans as `plan` does; filing a coordinated change is not built |

The broker refuses any value but `off` unless `human.intake.plan.enabled` is on.

## What the planner never decides {#never}

The allowlist, the class, the roles and the ceiling are config. The model chooses a repository from
the allowlist and a class from the table, and writes the issue text; everything else a plan shows is
the broker's. A reply that names a repository outside the allowlist, or a class outside the table, is
refused whole rather than trimmed.

A plan is also not the factory's scope. It says what will be filed; the scoper still turns the issue
into the runs that do the work.

Which capabilities are switched on where you are is on the [status page]({{< relref "/docs/status.md" >}}).
The factory's own settings are in the [harness reference]({{< relref "/docs/reference/harness.md" >}}).
