# Workflows, roles and onboarding: ai-native-ref adoption plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The platform runs Maku's three workflows, measures them on aws-0's live traffic, records
the decision, and onboards its four repositories with `maku repo add`.

**Architecture:** Each task follows a Maku release of the
[Maku plan](2026-11-14-workflows-maku-plan.md): bump the pin, change the `Factory`, `Repository` and
`MergePolicy` objects under `tooling/base/agent-factory/resources/`, and pin the change with a suite
under `scripts/ci/tests/`. The measurement's switch lives in the aws-0 overlay only, so it is on
exactly when aws-0 is the active cluster. Results go in a runbook's results file and in `status.md`.

**Tech Stack:** Flux kustomizations, Kustomize overlays, the Maku CRDs (`maku.ogenki.io/v1alpha1`),
Python and shell suites, Hugo for the site, `task check`.

**Spec:** [`docs/superpowers/specs/2026-11-14-workflows-review-design.md`](../specs/2026-11-14-workflows-review-design.md)

## Global Constraints

- **Work in a git worktree** branched from `origin/main`; rebase onto a freshly fetched
  `origin/main` before every push (`AGENTS.md`).
- **`task check` is the evidence.** Never claim a task done without its output. On a Mac it stops at
  `test` for known environment reasons (GNU `sed`, `git grep -E '\b'`, Colima not sharing
  `/var/folders`); when the failing suites are only those, run `task links docs sources` by hand and
  report both outputs.
- **Validation is on aws-0 only.** Two clusters alternate, one active at a time; gcp-0 is active
  while this plan is written. A task's live check waits for aws-0 to be the active cluster.
- Objects change in `tooling/base/agent-factory/resources/`; what must differ on aws-0 goes in
  `tooling/aws-0/agent-factory/resources/` as a Kustomize patch. gcp-0's overlay is not edited.
- Every Maku pin moves together and by digest: the factory image and chart
  (`tooling/base/agent-factory/helm-values-configmap.yaml`, its `OCIRepository`), the broker
  (`infrastructure/base/room-broker/helmrelease.yaml`, `ocirepository.yaml`, `crd-rooms.yaml`), the
  CRDs (`tooling/base/agent-factory/crds`). `test-agent-factory-pins.py` fails otherwise.
- A host change is a cloud-native-ref pull request first, then a `HOST_REF` bump here.
- Site pages follow `docs/docs-style.md`; `task docs` enforces it. The site links to Maku and to the
  host by absolute URL.
- Workflow names are exactly `quick`, `standard`, `careful`, `none`. No metric or label is renamed.
- Commits are conventional, in English, with no trailers.
- YAML structure edits use `yq -i`; diffs are read with `difft`.

## Gates

| Task | Needs Maku release | Needs |
|---|---|---|
| 1 | N (Maku plan tasks 1 to 3, 5, 6) | — |
| 2 | N (Maku plan task 4) | Task 1 live on aws-0 |
| 3 | N+1 (Maku plan tasks 7 to 9), with the merge policies adoption of N+1 | Task 2's decision recorded |
| 4 | N+1 | Task 3 live on aws-0 |
| 5 | the release carrying Maku plan task 12 | Task 3 |
| 6 | N | Task 1 |
| 7 | the release carrying Maku plan tasks 10 and 11 | policy-bot and octo-sts retired here (Maku `docs/v4-readiness.md`, row 14) |

## Review Focus

1. **A live or shadow class given `harnessAllowed`.** Maku refuses it (TE2) and the binding is
   dropped, so `docs-links` and `revert` would stop merging on cloud-native-ref. Pinned by
   `test-agent-factory-workflows.py`, case "a merging class has one workflow" (Task 1).
2. **Removing the `docs` and `scripts` loops rows changes what those tasks run** (no scoper, judge,
   search or splitter unless `careful`). The split drill's runbook then describes a path that no
   longer exists. Pinned by the suite's case "no per-class loops row" and by the runbook edit in
   Task 1.
3. **The measurement left on when gcp-0 becomes active**, or read across a cluster switch: the
   counters restart with the factory. Pinned by `test-agent-factory-evaluation-overlay.py` (the
   block is absent from base and from gcp-0) and by the runbook's per-session tally (Task 2).
4. **`triage.controlPercent` and `evaluation.controlPercent` confused.** The first sends tasks to
   `frontier`, the second draws the cohort. Pinned by the suite's case "triage.controlPercent is 0".
5. **A broker config that still names `intake.plan.classes` after the pin that refuses it**: the
   broker does not start and nobody can file a task. Pinned by
   `test-room-broker-intake-classes.py`, rewritten in Task 5 to fail on the block's presence.

---

### Task 1: Adopt release N, the three workflows

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml`, the factory `OCIRepository`,
  `tooling/base/agent-factory/crds/`, `infrastructure/base/room-broker/{helmrelease,ocirepository,crd-rooms}.yaml`
  (the pins)
- Modify: `tooling/base/agent-factory/resources/factory.yaml`
- Modify: `tooling/base/agent-factory/resources/mergepolicy-*.yaml` (12 files)
- Modify: `docs/runbooks/agent-factory/17-splitter.md`, `docs/runbooks/agent-factory/README.md`
  ("v3 loop and sandbox layers")
- Create: `scripts/ci/tests/test-agent-factory-workflows.py`
- Modify: `scripts/ci/tests/test-agent-merge-policy-profiles.py` (profile names)

**Interfaces:**
- Consumes: `scripts/ci/factory_config.py`, `factory_config.config(ROOT)`: the values file with the
  `Factory`, `Repository` and `MergePolicy` objects laid over it.
- Produces: every `MergePolicy` carries `spec.harness` naming a workflow. Later tasks read it.

Which class runs which workflow in release N:

| Classes | `harness` | `harnessAllowed` |
|---|---|---|
| `docs-links`, `revert`, `dead-links` | `quick` | none: they merge, or are in shadow |
| `deps-patch`, `deps-minor` (adopted pull requests) | `none` | none |
| `alert-rules`, `kb-entries` | `standard` | none: bound in shadow |
| `review`, `docs`, `scripts`, `tests`, `dashboards` | `standard` | `[careful]` |

`docs` keeps `checks: true`. Before writing, confirm each class's bindings across the four
`repository-*.yaml` files: a class bound `live` or `shadow` anywhere takes no `harnessAllowed`.

- [ ] **Step 1: Write the failing suite**

`scripts/ci/tests/test-agent-factory-workflows.py`, header `# requires: python3`, same shape as
`test-agent-merge-policy-profiles.py`. It loads `factory_config.config(ROOT)` and fails with one
line per problem:

| Case | Assertion |
|---|---|
| the three workflows | `quick`, `standard`, `careful` and `none` resolve: defined in `harnessProfiles` or `workflows`, or absent from both (Maku ships them) but never redefined with another `template` |
| no dead setting | no `templates.trio`, no `triage.classifierURL`, no `defaults.template`, no `defaults.tier` |
| `triage.controlPercent` is 0 | the key is `0` or absent |
| no per-class loops row | `loops` has no key other than `default` and workflow names |
| every class names a workflow | each `MergePolicy`'s `spec.harness` is one of the four names |
| a merging class has one workflow | a class bound `live` or `shadow` in any `Repository` has no `harnessAllowed` and no `escalation` |
| `careful` is reachable | every class whose `harness` is `standard` and that is bound `"off"` everywhere lists `careful` in `harnessAllowed` |
| the old profile names are gone | no `plain`, `checked`, `adopted-none` anywhere under `tooling/` |

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero, listing `trio`, `controlPercent: 10`, the `docs`, `scripts`, `docs-links`,
`revert`, `dead-links`, `deps-patch` loops rows, twelve policies without `harness`, and the three old
profile names.

- [ ] **Step 3: Bump the pins to Maku release N**

Every file listed under "the pins", by digest.

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py`
Expected: exit 0.

- [ ] **Step 4: Edit `factory.yaml`**

With `yq -i`:
- delete `spec.templates.trio`, the `spec.harnessProfiles` block (Maku ships the four), and the
  `loops` rows `docs`, `scripts`, `docs-links`, `revert`, `dead-links`, `deps-patch`;
- set `spec.triage.controlPercent` to `0`;
- keep `loops.default: {scope: "off"}`.

Rewrite the comments above `templates`, `triage` and `loops` to say what is true now, in two or
three lines each: the workflows come from Maku; a class names one; `careful` carries the scoper,
the judge, search and the split. The Kimi reviewer rows go because `quick` runs no reviewer and the
adopted classes run `none`; say so in the commit message, not in a comment.

- [ ] **Step 5: Set `harness` on each `MergePolicy`**

One `yq -i` per file, from the table above. Where a policy's `checked` profile carried
`checks: true`, the policy's own `checks: true` stays.

- [ ] **Step 6: Update the two runbooks**

`17-splitter.md` and the README's "v3 loop and sandbox layers": a split, a scoped run or a judged
run now needs the `workflow:careful` label on the issue (release N reads `profile:careful` too).
Replace the instructions that edit a `loops` row.

- [ ] **Step 7: Run the suites and the gate**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && python3 scripts/ci/tests/test-agent-merge-policy-profiles.py && task check`
Expected: both suites exit 0; `task check` exit 0, or the known environment failures followed by a
clean `task links docs sources`.

- [ ] **Step 8: Commit**

```bash
git add tooling infrastructure scripts docs/runbooks
git commit -m "feat(agent-factory): the quick, standard and careful workflows (Maku release N)"
```

- [ ] **Step 9: Live check on aws-0, recorded**

When aws-0 is active: `kubectl get factory,repository,mergepolicy -n agent-system -o json | jq`
shows `Accepted` and `Ready` true on every object and no dropped binding. File one issue with no
label and one with `workflow:careful` on Smana/ai-native-ref; the first room shows an implementer
and a reviewer, the second a scoper first. Record both task names and the object conditions in a new
`docs/runbooks/agent-factory/results-workflows-<date>.md`.

### Task 2: Comparison 1, `standard` against `careful`

**Files:**
- Create: `tooling/aws-0/agent-factory/resources/factory-evaluation.yaml` (a Kustomize patch)
- Modify: `tooling/aws-0/agent-factory/resources/kustomization.yaml`
- Create: `docs/runbooks/agent-factory/27-workflow-comparison.md`
- Create: `docs/runbooks/agent-factory/results-workflow-comparison-1.md`
- Create: `scripts/ci/tests/test-agent-factory-evaluation-overlay.py`
- Modify: `docs/runbooks/agent-factory/README.md` (the runbook index), `website/content/docs/status.md`

**Interfaces:**
- Consumes: Task 1's objects; Maku's `evaluation.treatment`.
- Produces: the results file's tally table, which Task 4 reuses for comparison 2.

The patch, applied on aws-0 only:

```yaml
apiVersion: maku.ogenki.io/v1alpha1
kind: Factory
metadata: {name: "${cluster_name}", namespace: agent-system}   # base's name, substituted by Flux
spec:
  evaluation: {controlPercent: 50, treatment: careful, mode: observe}
```

- [ ] **Step 1: Write the failing suite**

`scripts/ci/tests/test-agent-factory-evaluation-overlay.py`, header `# requires: python3 kustomize`.
It builds `tooling/base/agent-factory/resources`, `tooling/aws-0/agent-factory/resources` and
`tooling/gcp-0/agent-factory/resources` (when the directory exists) and asserts:

| Case | Assertion |
|---|---|
| base is silent | the base `Factory` has no `spec.evaluation` |
| gcp-0 is silent | the gcp-0 `Factory` has no `spec.evaluation` |
| aws-0 measures | the aws-0 `Factory` has `controlPercent: 50`, `mode: observe`, and a `treatment` that is `careful` or `quick` |
| the arm exists | every class bound `"off"` whose `harness` is `standard` allows the `treatment` workflow (release N only; skipped once `spec.workflows` is the key) |
| the tier draw is off | `spec.triage.controlPercent` is 0 or absent |

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-agent-factory-evaluation-overlay.py`
Expected: non-zero on "aws-0 measures".

- [ ] **Step 3: Add the patch and list it in the overlay's `kustomization.yaml`**

Run: `kustomize build tooling/aws-0/agent-factory/resources | yq 'select(.kind == "Factory") | .spec.evaluation'`
Expected: `{controlPercent: 50, treatment: careful, mode: observe}`.

- [ ] **Step 4: Write runbook 27**

`docs/runbooks/agent-factory/27-workflow-comparison.md`, with these sections and nothing else:

1. **What is compared.** `control` runs `standard`, `treatment` runs `careful`. Excluded from both
   arms: pinned tasks, scheduled and adopted work, classes that merge or are in shadow.
2. **The rule, fixed before the first task.** Copy the spec's decision table verbatim: "better" and
   "worse" mean a merge rate at least 15 points apart, or a cost per merged pull request at least
   20% apart with the merge rate no worse; better keeps the role, worse removes it from the shipped
   workflow, neither keeps it and allows 30 more tasks per arm once.
3. **Size.** 30 ended tasks per arm. No dollar stop.
4. **The reading.** Three queries against VictoriaMetrics, by `cohort`, filtered to
   `source=~"control|treatment"` so a task that fell back to its floor is not counted. Use the
   metric names the factory serves (Maku's code registers `agent_factory_*`):

   ```promql
   # ended tasks per arm
   sum by (cohort) (increase(agent_factory_task_outcomes_total{source=~"control|treatment"}[$__range]))
   # merged per arm
   sum by (cohort) (increase(agent_factory_task_outcomes_total{source=~"control|treatment", outcome=~"accepted|merged_human"}[$__range]))
   # dollars per arm
   sum by (cohort) (increase(agent_factory_task_usd_total{source=~"control|treatment"}[$__range]))
   ```

   Cost per merged pull request is the third over the second; merge rate is the second over the
   first. A fourth query, `agent_factory_run_cost_usd` by `role` and `cohort`, explains a difference
   and decides nothing.
5. **Sessions.** The counters restart with the factory and the cluster alternates. At the end of
   each aws-0 session, before the switch, read the three figures over the session's range and add
   one row to the results file. The comparison's totals are the sum of the rows.
6. **Closing.** When both arms reach 30: compute the two figures from the totals, apply the rule,
   write the decision in the results file and in `status.md`, and remove the patch or move it to
   comparison 2.

- [ ] **Step 5: Create the results file**

`results-workflow-comparison-1.md` with the header (comparison, arms, rule, start date) and an empty
tally table:

| Session (aws-0) | Range | `control` ended | `control` merged | `control` USD | `treatment` ended | `treatment` merged | `treatment` USD |
|---|---|---|---|---|---|---|---|

and a "Decision" heading left empty.

- [ ] **Step 6: Add the status row and the runbook index line**

`website/content/docs/status.md`: one row, "Workflow comparison 1 (`standard` against `careful`)",
state "running on aws-0 since <date>", linking the runbook by absolute GitHub URL. Follow
`docs/docs-style.md` (written for a reader who was not there; no per-row status tag the style check
refuses).

- [ ] **Step 7: Run the suites and the gate**

Run: `python3 scripts/ci/tests/test-agent-factory-evaluation-overlay.py && task check`
Expected: exit 0, or the known environment failures followed by a clean `task links docs sources`.

- [ ] **Step 8: Commit**

```bash
git add tooling/aws-0 docs/runbooks scripts/ci/tests website/content/docs/status.md
git commit -m "feat(agent-factory): workflow comparison 1 on aws-0, standard against careful"
```

- [ ] **Step 9: Run the comparison, then record its decision**

Follow runbook 27 across aws-0 sessions. The closing commit changes only the results file, the
`status.md` row and, by the rule:

| Decision | Change in the same commit |
|---|---|
| Better | `evaluation.mode: apply` in the aws-0 patch stays out until Task 3 is live; record that it is allowed |
| Worse | `careful` removed from every `harnessAllowed`; the suite's "`careful` is reachable" case inverted |
| Neither | nothing; one extension of 30 per arm may be opened, once |

```bash
git commit -m "docs(agent-factory): workflow comparison 1, the decision"
```

### Task 3: Adopt release N+1, the workflow off the class

This task shares its pull request with the merge policies adoption of release N+1
(`2026-11-14-merge-policies-adopt-plan.md`), which deletes the empty policies and the `"off"`
bindings. One pin bump, one rollout.

**Files:**
- Modify: the pins (as Task 1)
- Modify: `tooling/base/agent-factory/resources/factory.yaml`,
  `repository-{ai-native-ref,cloud-native-ref,runlore,runlore-kb}.yaml`, the remaining
  `mergepolicy-*.yaml`
- Modify: `tooling/aws-0/agent-factory/resources/factory-evaluation.yaml`
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`,
  `test-agent-factory-evaluation-overlay.py`; delete `test-agent-merge-policy-profiles.py`
- Modify: `docs/runbooks/agent-factory/17-splitter.md`, `README.md`

**Interfaces:**
- Consumes: Maku's `Factory.spec.workflows`, `Repository.spec.workflow.{default,testFirst}`,
  `Schedule.workflow`.
- Produces: no `MergePolicy` carries `harness`, `harnessAllowed`, `escalation`, `testFirst` or
  `checks`.

- [ ] **Step 1: Change the suite first**

`test-agent-factory-workflows.py`, replacing the release N cases about classes:

| Case | Assertion |
|---|---|
| no workflow field on a policy | no `MergePolicy` has `harness`, `harnessAllowed`, `escalation`, `testFirst` or `checks` |
| every repository has a default | each `Repository` has `spec.workflow.default`, one of `quick`, `standard`, `careful`, or omits it (`standard`) |
| every schedule names its workflow | each schedule has `workflow`, and a schedule with a `probe` runs `quick` |
| `testFirst` has its check | a `Repository` with `workflow.testFirst: true` sets `merge.contractCheck` |
| `checks` moved | `spec.workflows.standard.checks` and `.careful.checks` are set where `docs`' `checks: true` was relied on (ai-native-ref's `docs` tasks) or the commit message says why not |
| no old key | no `harnessProfiles`, no `profile:` or `class:` label in a runbook's instructions |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero on every new case.

- [ ] **Step 2: Bump the pins to release N+1; edit the objects with `yq -i`**

- `factory.yaml`: any platform override moves from `harnessProfiles` to `workflows`.
- Each `Repository`: `spec.workflow.default: standard` written out; each schedule gains
  `workflow: quick`.
- Each remaining `MergePolicy`: delete the five fields.

- [ ] **Step 3: Decide `checks`**

ai-native-ref's `docs` class carried `checks: true`. Read what a `standard` run does on a repository
without `.github/agent-checks.yaml` (the Maku plan leaves this to its builder; read the answer in
Maku's `docs/factory.md` at the pinned tag). If a missing file is a no-op, set
`spec.workflows.standard.checks: true` and `.careful.checks: true`; if it fails the run, leave both
off and open a Maku issue for a per-repository switch. Record the choice in the commit message.

- [ ] **Step 4: Update the runbooks' labels**

`workflow:<name>` only; remove every `class:` and `profile:` label from the instructions.

- [ ] **Step 5: Run the suites and the gate**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && task check`
Expected: exit 0, or the known environment failures followed by a clean `task links docs sources`.

- [ ] **Step 6: Commit**

```bash
git add tooling infrastructure scripts docs/runbooks
git commit -m "feat(agent-factory): the workflow comes from the repository and the label (Maku release N+1)"
```

- [ ] **Step 7: Live check on aws-0, recorded**

Every object `Accepted` and `Ready`. Three issues on Smana/ai-native-ref: no label (an implementer
and a reviewer), `workflow:quick` by a maintainer (an implementer only, and its pull request waits
for a human unless its diff matches a policy with a shape), `workflow:quick` by a non-maintainer
(ignored and narrated, runs `standard`). Add the three task names to the results file of Task 1.

### Task 4: Comparison 2, `standard` against `quick`

**Files:**
- Modify: `tooling/aws-0/agent-factory/resources/factory-evaluation.yaml` (`treatment: quick`)
- Create: `docs/runbooks/agent-factory/results-workflow-comparison-2.md`
- Modify: `docs/runbooks/agent-factory/27-workflow-comparison.md` (one paragraph),
  `website/content/docs/status.md`

**Interfaces:**
- Consumes: Task 2's runbook, results layout and suite; Task 3's objects.

- [ ] **Step 1: Set the treatment**

Run: `yq -i '.spec.evaluation.treatment = "quick"' tooling/aws-0/agent-factory/resources/factory-evaluation.yaml`
Then: `python3 scripts/ci/tests/test-agent-factory-evaluation-overlay.py`
Expected: exit 0.

- [ ] **Step 2: Add the paragraph to runbook 27**

Comparison 2 measures the reviewer: `control` runs `standard`, `treatment` runs `quick`. A `quick`
pull request merges on its own only when its diff matches a policy with a shape or an oracle;
otherwise a human merges it, and `merged_human` counts it only when the human added a commit. So
read `outcome=~"accepted|merged_human"` as the spec says, and add the count of `quick` pull requests
a maintainer rejected (`outcome="rejected"`) to the results table as a ninth column: it is the
reviewer's missing catch.

- [ ] **Step 3: Create the results file, add the status row, run the gate, commit**

Run: `task check`
Expected: exit 0, or the known environment failures followed by a clean `task links docs sources`.

```bash
git add tooling/aws-0 docs/runbooks website/content/docs/status.md
git commit -m "feat(agent-factory): workflow comparison 2 on aws-0, standard against quick"
```

- [ ] **Step 4: Run it, then record its decision** as in Task 2, step 9. "Worse" for `quick` keeps
  the reviewer in `standard`, which is today's shape: nothing changes but the record.

### Task 5: The broker's own lists go (WF12)

**Files:**
- Modify: `infrastructure/base/room-broker/config.yaml` (`human.intake.plan`),
  `infrastructure/aws-0/room-broker/` (its copy of the block), the broker pins if this release is
  newer than Task 3's
- Modify: `scripts/ci/tests/test-room-broker-intake-classes.py`, `test-intake-plan-wiring.py`

**Interfaces:**
- Consumes: Maku's catalogue route listing the served repositories.

- [ ] **Step 1: Rewrite the suite's assertions first**

`test-room-broker-intake-classes.py` now asserts, for base and the aws-0 overlay: no
`human.intake.plan.classes`; no `human.intake.plan.repositories`, or a list every entry of which is
a `Repository` object's `spec.repository`; the broker pin is at or above the release that reads the
factory's list. Rename the file `test-room-broker-intake-catalog.py` and update its docstring.

Run: `python3 scripts/ci/tests/test-room-broker-intake-catalog.py`
Expected: non-zero, naming both blocks.

- [ ] **Step 2: Delete the two blocks with `yq -i`, in base and in the aws-0 overlay**

Keep `enabled`, `url`, `model`, `apiKeyFile`, `deadline`, `reasoningEffort`, `dailyPlans`,
`fallback`. Remove the comments that describe the class table.

- [ ] **Step 3: Run the suites and the gate, commit**

Run: `python3 scripts/ci/tests/test-room-broker-intake-catalog.py && python3 scripts/ci/tests/test-intake-plan-wiring.py && task check`
Expected: exit 0, or the known environment failures followed by a clean `task links docs sources`.

```bash
git add infrastructure scripts/ci/tests
git commit -m "refactor(room-broker): the planner's repositories and workflows come from the factory"
```

- [ ] **Step 4: Live check on aws-0**

From a coding agent, hand off one task for Smana/runlore-kb: the plan names the repository and a
workflow. Record the task name in the results file of Task 1.

### Task 6: The site says five roles and three workflows

The [docs design](../specs/2026-11-14-docs-review-design.md) owns the pages' structure and their
reduction to this platform's values; this task changes only the words that become false with
Task 1. If the docs plan has already rewritten a page, apply the vocabulary there instead.

**Files:**
- Modify: `website/content/docs/how-it-works/roles.md`,
  `website/content/docs/how-it-works/factory.md`,
  `website/content/docs/use/guide/meet-the-factory.md`,
  `website/content/docs/use/guide/writing-a-good-task.md`,
  `website/content/docs/use/guide/cheat-sheet.md`,
  `website/content/docs/reference/factory-configuration.md`,
  `website/content/docs/operate/tune-a-run.md`
- Test: `task docs`, `task links`

**Interfaces:**
- Consumes: the spec's tables "The three workflows", "The roles" and "The renames".

- [ ] **Step 1: Find what is false**

Run: `grep -rn -i -E 'trio|harness profile|capability profile|egress profile|profile:|splitter|eight roles|class:' website/content/docs --include=*.md`
Expected: the list of lines to change. Lines under `decisions/` are history and stay.

- [ ] **Step 2: Rewrite**

- `roles.md`: the five-role table from the spec; one sentence each for "the scoper may propose
  parts" and "search is a tool of the implementer"; the triager moves to `runlore.md`. One mermaid
  diagram, the spec's flowchart of the three workflows.
- The guide: a task runs a workflow; the factory picks `standard`; a maintainer changes it with the
  `workflow:<name>` label or at confirmation. No class, template, tier or loop in the guide.
- `factory-configuration.md` and `tune-a-run.md`: templates, `loops`, tiers and cohorts are named
  once, as the advanced layer, with a link to Maku's reference at the pinned tag.
- Renames: "role permissions", "approval mode", "egress allow-list".

- [ ] **Step 3: Run the docs gates**

Run: `task docs links`
Expected: exit 0. Then repeat Step 1's `grep`: only `decisions/` lines remain.

- [ ] **Step 4: Commit**

```bash
git add website/content/docs
git commit -m "docs(site): five roles and three workflows"
```

### Task 7: The four repositories, re-rendered with `maku repo add`

**Files:**
- Modify: `tooling/base/agent-factory/resources/repository-{ai-native-ref,cloud-native-ref,runlore,runlore-kb}.yaml`
- Create: `scripts/ci/tests/test-agent-factory-repositories-rendered.sh`
- Modify: `docs/runbooks/agent-factory/README.md` (an "Onboard a repository" entry linking Maku's
  page by absolute URL at the pinned tag)

**Interfaces:**
- Consumes: `maku repo add <owner/name> --out DIR`, writing
  `DIR/factory/repository-<name>.yaml`; `maku repo check <owner/name>`.

- [ ] **Step 1: Write the failing suite**

`test-agent-factory-repositories-rendered.sh`, header `# requires: bash yq`. For each of the four
files it asserts: under 15 lines once comments and the platform's own additions are removed, where
the additions are exactly the keys in an allow-list at the top of the script (`schedules`,
`mergePolicies` entries the merge policies plan keeps, `workflow`); no key outside
`factoryRef`, `repository`, `maintainers`, `merge.requiredChecks`, `merge.leakScanCheck` and that
allow-list.

Run: `bash scripts/ci/tests/test-agent-factory-repositories-rendered.sh`
Expected: non-zero, naming the extra keys of each file.

- [ ] **Step 2: Render each repository and compare**

```bash
maku repo add Smana/ai-native-ref --out "$SCRATCH/ai-native-ref" --factory aws-0 --namespace agent-system
difft "$SCRATCH/ai-native-ref/factory/repository-ai-native-ref.yaml" tooling/base/agent-factory/resources/repository-ai-native-ref.yaml
```

For each difference, either the rendered value replaces ours, or our key joins the suite's
allow-list with a one-line reason. Time the first run from the command to a passing
`maku repo check`: the spec's target is under 15 minutes. Record the time in the results file of
Task 1.

- [ ] **Step 3: Check each repository on aws-0**

Run: `maku repo check Smana/ai-native-ref` (and the three others)
Expected: every line `PASS`.

- [ ] **Step 4: Run the suite and the gate, commit**

Run: `bash scripts/ci/tests/test-agent-factory-repositories-rendered.sh && task check`
Expected: exit 0, or the known environment failures followed by a clean `task links docs sources`.

```bash
git add tooling scripts/ci/tests docs/runbooks
git commit -m "refactor(agent-factory): the four repositories as maku repo add writes them"
```

---

## Self-review

| Spec item (ANR table) | Task |
|---|---|
| 1. Adopt N | 1 |
| 2. Comparison 1 | 2 |
| 3. Adopt N+1 | 3 |
| 4. Comparison 2 | 4 |
| 5. Broker config | 5 |
| 6. The site | 6 |
| 7. Re-render with `maku repo add` | 7 |
| The measurement: draw, arms, exclusions, figures, size, rule, where | 2 (runbook 27), 4 |
| `triage.controlPercent: 0` | 1 |
| Validation on aws-0 only | every live check; the overlay in 2 |
