# 27 — Workflow comparison: `standard` vs `careful`

Measures whether `careful` (the scoper, the completion judge and the search tool together, at
`frontier`) lands more accepted pull requests per dollar than `standard` (`pair` at `standard` with
repository checks) on real issues of `Smana/ai-native-ref`. Design:
[workflows review](../../superpowers/specs/2026-11-14-workflows-review-design.md) (WF9).

## 1. The overlay

`tooling/aws-0/agent-factory/resources/factory-evaluation.yaml` patches the `aws-0` `Factory`:

```yaml
spec:
  evaluation:
    controlPercent: 70
    treatment: careful
```

Every task on `Smana/ai-native-ref` that would take the repository's default workflow (`standard`), with
no `workflow:` label, is assigned deterministically by `SHA-256(repository + "#" + issueNumber)`: 30%
run `careful` (`status.cohort: treatment`) and 70% run `standard` (`status.cohort: control`). A task
with a `workflow:` label, a scheduled task or an investigation is `status.cohort: none` and is not
counted in either arm.

## 2. The cohort

40 unlabelled default tasks on `Smana/ai-native-ref` (about 12 `treatment` and 28 `control`). Do not
add `workflow:` labels to issues you want in the comparison.

## 3. Reading the arms

From the room broker's outcome page or the factory's tasks:

```bash
kubectl -n agent-system get tasks.maku.ogenki.io \
  -o custom-columns='NAME:.metadata.name,ISSUE:.spec.issue,WORKFLOW:.spec.harnessProfile,COHORT:.status.cohort,PHASE:.status.phase,COST:.status.costMicroUSD'
```

Record the four numbers in [results-workflow-comparison-1.md](results-workflow-comparison-1.md):

| Arm | Tasks | Merged without a human commit | Median time to merge | Cost per accepted PR |
|---|---|---|---|---|
| `control` (`standard`) | | | | |
| `treatment` (`careful`) | | | | |

## 4. Decision rule

- `careful` keeps its place in the three-workflow table if its acceptance rate is at least 15 percentage
  points higher than `standard`'s on tasks that touch more than three files, or its cost per accepted
  pull request across the cohort is no higher than 1.5x `standard`'s.
- Otherwise, Comparison 2 tests which piece of `careful` (`scoper`, `judge` or `search`) pays for
  itself, using a one-field `-trial` workflow under the same `evaluation` block.

## 5. Ending the comparison

Delete `tooling/aws-0/agent-factory/resources/factory-evaluation.yaml` and its entry in
`tooling/aws-0/agent-factory/resources/kustomization.yaml` in the commit that records the table in
`results-workflow-comparison-1.md`.
