# 32 — Workflow comparison: `standard` vs `careful`

The comparison is not running. This is the procedure for a later one, and it is no longer a
precondition for step-up or per-role measurement (the workflows and roles redesign's first owner
ruling, WR-O1). Design:
[workflows review](../../superpowers/specs/2026-11-14-workflows-review-design.md) (WF8).

## When to run one

Run a comparison when the open question is which workflow a class of tasks should default to, and
cost or merge-rate data can settle it: a decision rule from both arms beats an argument from
impressions. It is not a tool for step-up or per-role measurement, which WR-O1 in the introduction
already routes elsewhere. A comparison is only worth its cost when the target cluster can supply
the cohort of section 2, 30 ended tasks per arm. Anything smaller cannot reach the rule of section 4.

## 1. The overlay

Add a `Factory` strategic-merge patch under the target cluster's overlay (the file does not exist
until someone starts a comparison):

```yaml
spec:
  evaluation: {controlPercent: 50, treatment: careful, mode: observe}
```

Every unlabelled task that would take the repository's default workflow is assigned deterministically
by FNV-32a of `evaluation/<task name>` modulo 100: below `controlPercent` is `control`, otherwise
`treatment`. A pinned task is `labeled` and is not counted in either arm.

## 2. The cohort

30 ended tasks per arm (60 total) on the target repository. Do not add `workflow:` labels to issues
you want in the comparison.

## 3. Reading the arms

List tasks with their workflow, source and cohort:

```bash
kubectl -n agent-system get tasks.maku.ogenki.io \
  -o custom-columns='NAME:.metadata.name,ISSUE:.spec.issue,WORKFLOW:.status.profile.name,SOURCE:.status.profile.source,COHORT:.status.profile.cohort,PHASE:.status.phase'
```

Read dollars per cohort from `agent_factory_task_usd_total` grouped by `cohort`, filtered to
`source=~"control|treatment"`.

Record the numbers in a results file beside this runbook (see
[results-workflow-comparison-1.md](results-workflow-comparison-1.md) for the closed first run).

## 4. Decision rule

30 ended tasks per arm. Better or worse is at least 15 percentage points of merge rate, or 20% of
cost per merged pull request with the merge rate no worse.

## 5. Ending the comparison

Delete the evaluation patch file and its entry in that cluster overlay's `kustomization.yaml` in the
commit that records the comparison's results.
