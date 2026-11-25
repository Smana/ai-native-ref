# 29 — Maku v0.54.0: the live checks

What the Maku v0.54.0 adoption turned on, checked one feature at a time on the cluster the fences
name. Each check is one scratch issue or pull request; keep its URL, the task name, the head SHA and
the `maku/merge-gate` decision in a results file beside this runbook
(`results-<cluster>-<date>.md`). Nothing here raises a cap or merges a scratch pull request by an
administrator bypass.

Sources: the [usability adoption plan](../../superpowers/plans/2026-11-24-merge-policies-usability-adopt-plan.md)
(Tasks 4 and 5) and the workflows and roles adoption plan, phases C, E, F, G, H and I.

## 0. Baseline

```bash
kubectl -n agent-system get factory,repository,mergepolicy
kubectl -n agent-system get factory -o jsonpath='{.items[0].status.conditions}' | jq
kubectl -n agent-system get repository -o custom-columns=NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,BINDINGS:.status.conditions[?(@.type=="BindingsValid")].status
kubectl -n agent-system get configmap agent-factory-role-briefs -o yaml | head
```

Expected: the `Factory` is `Accepted` and `Ready` with no deprecation warning (no `templates`), every
`Repository` is `Ready` with `BindingsValid` true, and the brief ConfigMap holds
`security-reviewer.md`. Record the factory, broker and run-controller image digests.

## 1. Step up once

| Drill | Do | Expected |
|---|---|---|
| Automatic | An unlabelled issue on `Smana/ai-native-ref` that asks to edit a file that does not exist and forbids creating it | `standard` stalls; the task goes back to `Queued` as `careful`, `status.profile.stepUp` is `{from: standard, to: careful, trigger: stalled, mode: auto}`, same branch |
| Pinned | The same text with `workflow:standard` | `Escalated` with an offer; `/factory retry deeper` steps it (`mode: manual`) |
| Slack | The same request from the Slack channel (`maxCostUSD: 2`) | An offer, never a step; **Run again deeper** is refused `deeper_over_cap` |
| Host | One issue on `Smana/cloud-native-ref` | An offer: the host's `stepUp: ask` |

## 2. Outcomes and the plan gate

| Drill | Do | Expected |
|---|---|---|
| `plan-first` | Label an issue `plan-first` and `workflow:careful` | The scoper's plan comment, `factory/plan-proposed`, no `AgentRun` while it waits; **Approve** from the room starts the implementer; on a second issue **Revise** re-plans |
| `review` | Label a person's pull request `factory/review` | One verdict comment, no push, no merge; the gate's status on it is unchanged |
| `report` | An issue that asks "why", labelled `report` | Findings on the issue, no branch; `/factory fix` files a `change` task |
| Required plan | An unlabelled change under `observability/` on the host | A scoper run before the implementer: `alert-rules` requires a plan |

## 3. The room's acts and whole plans

On the room page, do each act once: **Answer**, **Retry**, **Run again deeper**, **Accept the
split**, **Approve** / **Revise** / **Split** a plan, **Stop**, and **New task** (`file`). Each must
reach the factory with your own token; a refused one names its reason. Then hand off a request wide
enough for three issues from a coding agent: `start` files all three in order, each later one
naming the earlier ones it waits for.

## 4. The custom workflow

Label one issue `workflow:thorough` on `Smana/ai-native-ref`. Expected: the rail shows implementer,
`security-reviewer`, reviewer; the security reviewer's `AgentRun` carries
`agents.ogenki.io/persona: security-reviewer` and the reviewer's read-only token; the gate reads the
built-in reviewer's verdict only.

## 5. OpenCode, one task

Label one small issue `harness:opencode` (a maintainer applies it). Expected: `Task.status.profile`
shows `harness: opencode, harnessSource: labeled`; the run pod's image is `ghcr.io/smana/maku-opencode`
by digest and the admission policy admits it. If it escalates, `/factory retry harness=openhands`
moves it back (`cohort: rescue`). Do not set `defaults.harness` or `evaluation.treatmentHarness`.

## 6. Merge policies

1. **Reverts merge themselves.** On the host, `factory/drill` then `factory/revert` on a merged
   `docs-links` pull request: the factory's revert merges at the head GitHub created, with no
   `revert` binding.
2. **Pause and resume.** `maku policy pause --repository Smana/ai-native-ref --reason "drill"` opens a
   pull request on the `gitops` manifest; once merged, a shadow decision waits `paused` and the
   `Paused` condition carries the reason. `maku policy resume` removes it.
3. **Promotion.** On `/settings`, **Promote to live** for `dead-links` on `Smana/ai-native-ref` once
   it has five clean decisions and a passed drill: the factory opens `factory/promote-…`, a maintainer
   merges it, Flux serves the live binding, the record closes `merged`.
4. **The reasons.** `maku policy list` and `maku policy explain <pr>` on one decision of each
   repository.

## 7. Close

Close unmerged scratch and promotion pull requests, remove scratch labels, resume any paused
repository, and record every failure rather than weakening a policy to pass it.
