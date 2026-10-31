# 17 — The splitter: the live proof

Proves the splitter on gcp-0: a hard issue becomes sub-issues that land one by one, with the family's
cost bounded and charged to the approver. Design:
[splitter](../../superpowers/specs/2026-10-23-splitter-design.md). The switch is the
`loops.scripts.split` row: a session adds it for the proof and removes it after (D4). The source still
holds it. Run it
after the scoper's live proofs (the split needs `scope: scoper` on the same row). See
[README.md](README.md) for `CLOUD`.

## 1. Prerequisites

- [ ] Maku v0.19.0 or later pinned (`flux/sources/ocirepo-agent-factory.yaml`).
- [ ] The scoper's live proofs passed: a class with `scope: scoper` bounces and scopes as designed.
- [ ] The factory App holds `issues: write` (a child issue, the sub-issue link, closing the parent).
- [ ] A hard-task cohort: two issues of class `scripts`, filed again as new issues.

## 2. The row, in the session's first commit

In `tooling/base/agent-factory/helm-values-configmap.yaml`, under `loops`:

```yaml
      scripts: {scope: scoper, split: {maxChildren: 4, familyUSD: 20.40, childTier: standard, anyTier: true}}
```

`anyTier: true` offers the splitter to every `scripts` task: gcp-0 deploys no classifier, so no task is
ever `frontier`. The session's last commit removes the row.

## 3. Proofs

| # | Do | Expected reading |
|---|---|---|
| 1 | A maintainer labels each cohort issue `factory/ready` | At least one task has `spec.split` (`kubectl -n agent-system get task <name> -o jsonpath='{.spec.split}'`); its scoper proposes a split: one comment, the label `factory/split-proposed`, `status.split.state: proposed` |
| 2 | A maintainer comments `/factory split` on the proposal | `status.split.approvedBy` is the approver, the parent's phase is `Split`, part 1 is a sub-issue titled `Part 1 of N of #<parent>` carrying `factory/child-of:#<parent>` and the class label; its Task runs `pair` at `standard` |
| 3 | A human merges each part's pull request | The next part opens after each merge; the parent issue closes as completed on the last; the parent task ends `Done`, `children_merged` |
| 4 | On a second proposal, `/factory retry` | One implementer on `agent/<parent>` at `frontier`, no issue labelled `factory/child-of:#<parent>`, `maku_factory_splits_total{outcome="declined"}` 1 |
| 5 | Label a `Split` parent `factory/stop` | The running part's `AgentRun` is revoked within 60 s; the parent is `Stopped` |
| 6 | Read the spend | The spend-per-identity dashboard charges every part's runs to the approver; `sum(.status.usage.costMicroUSD)` over `-l agents.ogenki.io/parent=<parent>`, plus the parent's, stays within `familyUSD` |
| 7 | Read the factory's `/metrics` | `maku_factory_splits_total` and `maku_factory_split_children_total` carry the outcomes above |

## 4. What fails closed

No child exists before a maintainer's `/factory split`. A `factory/child-of` label a user adds is
ignored; only the factory App's counts. A split handoff on a task where none was offered is ignored
and counted `ignored`. A child closed with no landed task, or a merge reverted before the parent
closes, ends the parent `Closed`, `child_dropped`, and no later part is created. A family whose budget
cannot hold one more run ends `Escalated`, `budget-family`.

## 5. Afterwards

Remove the row (the session's last commit); every class is off again (D4).
