---
title: Factory
weight: 30
description: "Work in progress. From a labelled issue to a merged PR: intake, triage, teams, revise, the merge gate and the kill switch."
lastVerified: 2026-10-01
---

The factory is the controller that turns a labelled issue into runs, narrates progress on the issue,
meters each run's tokens and owns the kill switch. It is the only component that creates runs, so
every run has a task and a budget. This page describes the design; what runs today is on the
[status page]({{< relref "/docs/platform/ai-platform/status.md#landed" >}}).

![The factory, from issue to merge. A maintainer labels a GitHub issue factory/ready; intake snapshots it, and triage picks the task's class, team and budget. The Task controller runs the team as sequential agent runs in one room: an implementer, then a reviewer, and a tester in the larger teams. Kueue admits each sandbox. The implementer opens a PR; a maintainer's "Request changes" review becomes a new run on the same branch. The merge gate, policy-bot and a separate merger App, merges only low-risk classes with green CI; every other PR waits for a human. The run meter revokes a run at its token cap, and the kill switch, a stop ConfigMap or a label on a pinned control issue, pauses intake and stops every task](/images/diagrams/ai-platform-5.svg)

*Source: [`docs/architecture/ai-platform.drawio`](https://github.com/Smana/ai-native-ref/blob/main/docs/architecture/ai-platform.drawio), page 5.*

## From issue to merge

| Step | What happens |
|---|---|
| **Intake** | A maintainer adds `factory/ready` to an issue. The factory takes a snapshot of it, so a later edit does not change a task already under way, and comments with the run id, branch, budget and a *watch* link. A task already running refuses a second label |
| **Sponsored intake** | A second intake kind, `api`, takes a task from a machine principal: a ZITADEL machine user declared under `api.sponsored`, never from a request body. Each principal names a **sponsor** (a maintainer, named in the issue's footer and on the Task, accountable for what it files), a **daily** dollar ceiling and a per-task `maxCostUSD`; every request must carry `max_cost`, and the Task records who asked, the sponsor, the person it acts for and the cap. The runs are charged to the principal. Nothing is declared today: the Slack App ([user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#from-slack" >}})) is its first client, and a gcp-0 session switches it on |
| **Triage** | Once per task: which class it is (for example `docs-links`), which team of roles works it, and how big a budget it gets. A refusal is explained in a comment. What triage predicts only chooses the team and the budget; risk is enforced on the diff at merge time |
| **Teams** | Roles run as sequential `AgentRun`s in one room, on one `agent/<task>` branch: an implementer, then a reviewer, with a tester in larger teams. Only the implementer writes |
| **Revise** | A GitHub review with "Request changes" becomes the input of a new run on the same branch. `/factory retry` tries again after a failure |
| **Merge gate** | Only low-risk classes, and only with green CI and the policy agreeing: `docs-links` and `revert` (the factory's revert of an auto-merged `docs-links` change). Everything else waits for a human. Each class declares its conditions (allowed and protected files, size, diff shape, holdout checks) on top of a base it cannot remove; `dead-links`, which fixes dead external links a nightly scan found twice, is declared and switched off. Since v2.0 the gate is live: link fixes merge with no human, at most once a day, and a revert breaker demotes the class to human review |
| **Scope** | `loops.<class>.scope` is `off`, `steering` or `scoper`, and every class is `off`. `steering` adds the class's note (`.github/agent-factory/steering/<class>.md`) to the implementer's brief. `scoper` first runs a read-only triager that turns the issue into a bounded task with acceptance checks, or asks the author the question it could not answer (the [user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#scoper-question" >}})). Three counters by repository and class: scoper outcomes, steering reads (`used`, `absent`, `invalid`) and bounce exits (`relabel`, `retry`, `expired`) |
| **Split** | `loops.<class>.split` is absent for every class. A row needs `scope: scoper` on the same row and never applies to `docs-links`, `revert` or an oracle class. Its keys: `maxChildren` (2 to 5, required), `familyUSD` (the cap on the parent and every part together; default four of the child tier's task caps, $20.40 on `standard`) and `childTier` (default `standard`). A split is only proposed for a task C7 puts on `frontier`, and parts open one at a time after a maintainer's `/factory split` ([user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#split" >}})). Two counters by repository and class: `agent_factory_splits_total` (by outcome) and `agent_factory_split_children_total` (`landed`, `dropped`, `reverted`) |
| **Test-first tester** | Per class, `testFirst: true` (it needs `checks: true`) runs the tester before the implementer: its tests, failing on the base, become the contract the implementer works against. `merge.contractCheck` names the host's `Test contract 🧪` check, required on a task that has a contract (row 2b) and report-only otherwise; row 2c refuses a head that changed the contract. Reasons: `contract_invalid`, `contract_disputed`, `contract_modified`. `holdoutChecks` on a live or shadow class names the checks the implementer cannot read. Metrics: `agent_factory_contracts_total` and `agent_factory_class_without_holdout`. `testFirst` is `false` everywhere and `trio` is the implementer and the reviewer until the bench |
| **Kill switch** | One task: the label `factory/stop`. Every task: the stop ConfigMap, or a label on a pinned control issue |

The developer's view of the same journey is in the
[user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md" >}}).

## Dependency bumps

The factory authors no bump. A class that declares `author.adopt` takes Renovate's pull requests: a
poller turns an eligible open one into a Task that runs no agent and costs nothing, and the same merge
gate decides it. `deps-patch` takes patch bumps of the YAML Flux deploys, and `deps-minor` observes
minors in shadow only. Both are declared and switched off.

| What is checked | How |
|---|---|
| The pull request | Into `main`, from the same repository (never a fork), by `renovate[bot]` on a `renovate/` branch; at most 10 open Tasks per repository and class |
| The diff | Computed by the factory, never read from Renovate's label: at most 3 files and 10 lines, version tokens only, a digest only when attached to the moved version, no lockfile, none of the never-automerge files |
| The age | Renovate's `stability-days` status must be green |
| The people | A `CHANGES_REQUESTED` from a repository member parks it; so does a human commit or push on the branch |
| The merge | Pinned to the head it judged, so a push by Renovate afterwards refuses it; Renovate's next head is decided again, at most 3 times, then monitored on Flux |

First `shadow`: Renovate keeps merging, and the factory records the decision it would have made.

## After a merge

Every merge of a class that declares a monitor stays under watch, whoever merged it. The monitor reads
main's CI, the detector's next scheduled runs and, for a class that declares it, Flux, then records
`healthy`, `regression` or `inconclusive` (an unreadable answer is always `inconclusive`). It also counts
the follow-up fixes merged within the class's window. It never reverts and never widens a class.
`dead-links` is the first class under it (two detector runs, 7 days of follow-ups); declaring it never
back-fills older merges. The merger labels the pull request (`factory/merged:<class>`,
`factory/monitor:regression`, and `factory/follow-up-of:#<n>` on a fixing PR), so the record survives a
rebuild. A regression or a follow-up counts against the breaker like a revert and sends the class back to
human review, and the `AgentFactoryMergeRegression` alert fires on a regression.

## Components and software

| Component | Software | What it does | Why this software |
|---|---|---|---|
| Task controller | A Go controller (controller-runtime) | Turns a labelled issue into a task: snapshot, a room, the team's runs on its branch; narrates on the issue. Starts a reviewer after the implementer, and turns "Request changes" into a new run | The only component that creates runs, so every run has a task and a budget |
| Admission | [Kueue](https://kueue.sigs.k8s.io) | Queues sandboxes so a burst of tasks waits instead of overloading the node pool. Until it lands, the factory's own caps bound concurrency | The Kubernetes-native job queue, with quotas |
| Run meter and kill switch | Part of the controller | The run meter revokes any run, hand-launched ones included, at its token cap. The `agent-factory-stop` ConfigMap pauses intake and stops every task; so does a label on a pinned control issue | Controls that act from outside the sandbox |
| Merge gate | [policy-bot](https://github.com/palantir/policy-bot) and a merger GitHub App | Decides which agent PRs may merge themselves (only low-risk classes, green CI), then merges the PR at the head commit the checks ran on; only the factory's own revert PRs use GitHub's auto-merge. A separate App holds that right, and only it | The policy lives in the repository and is reviewable; the right to merge is isolated from everything else |
| Admission policy | [Kyverno](https://kyverno.io) | Denies `AgentRun` creation to anyone but the factory | One path in, so no run escapes its budget |

## Controls

| Boundary | Mechanism |
|---|---|
| Spend | Per-run deadline; the factory's run meter revokes a run at its token cap; token budgets at the gateway; at most 20 tasks a day |
| Merge | Only low-risk classes (`docs-links`, `revert`) merge themselves, through policy-bot and a separate merger App, live since v2.0, with a revert breaker; everything else waits for a human |
| Stop | `kubectl -n agent-system create configmap agent-factory-stop` pauses intake and stops every task; one label on a pinned control issue also refuses new runs and revokes every running one |

The sandbox, identity and GitHub boundaries are on
[Runtime → Security boundaries]({{< relref "/docs/platform/ai-platform/agents/runtime.md#security-boundaries" >}}).
The [factory design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-09-23-agent-dark-factory-design.md)
has the full merge policy, gate paths and the five-layer kill switch.
