# Workflows and roles redesign: ai-native-ref adoption plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The platform's manifests, site and runbooks match what each Maku release of the redesign
does: a repaired configuration, one card on every surface, one step-up, a figure per role, stage
switches, outcomes beyond a pull request, acts where a person reads, whole plans and one readable
workflow definition.

**Architecture:** One section per phase, A to I, each following a release of the
[Maku plan](2026-11-24-workflows-roles-redesign-maku-plan.md). A section bumps every Maku pin
together, changes the `Factory`, `Repository` and `MergePolicy` objects under
`tooling/base/agent-factory/resources/`, pins the change with a suite under `scripts/ci/tests/`,
rewrites the site pages the release makes wrong, and ends on `task check`. What needs a cluster is a
last step of its task, recorded in a results file under `docs/runbooks/agent-factory/`.

**Tech Stack:** Flux kustomizations, Kustomize overlays, the Maku CRDs (`maku.ogenki.io/v1alpha1`),
Python and shell suites, Hugo for the site, `task check`.

**Spec:** [`docs/superpowers/specs/2026-11-24-workflows-roles-redesign-design.md`](../specs/2026-11-24-workflows-roles-redesign-design.md),
with its [research](../specs/2026-11-24-workflows-roles-redesign-research.md).

## Global Constraints

- **Work in a git worktree** branched from `origin/main`; rebase onto a freshly fetched
  `origin/main` before every push (`AGENTS.md`).
- **`task check` is the evidence.** Never claim a task done without its output. When it stops for
  an environment reason alone (no container runtime for a suite that needs one), run
  `task test links docs sources` by hand and report both outputs.
- **A live check needs a cluster.** None may be running when a task is built. The live step of a
  task waits for the factory named in `.github/agent-factory.yaml` to be up, and its result goes in
  the results file the task names. The task's commit does not wait for it.
- Objects change in `tooling/base/agent-factory/resources/`; what must differ on one cluster goes in
  that cluster's overlay as a Kustomize patch.
- **Every Maku pin moves together and by digest**: `flux/sources/ocirepo-agent-factory.yaml`,
  `tooling/base/agent-factory/helm-values-configmap.yaml`,
  `tooling/base/agent-factory/crds/ocirepository.yaml`,
  `tooling/base/agent-factory/slack-app/deployment.yaml`,
  `infrastructure/base/room-broker/{ocirepository,helmrelease,crd-rooms}.yaml`,
  `infrastructure/base/agent-gateway/model-gateway/ocirepository.yaml`,
  `infrastructure/base/karpenter-nodepools-agents/headroom/deployment.yaml`,
  `scripts/ci/flux-schema/vendored-crds/maku-{factory,repository,mergepolicy}.yaml`,
  `scripts/ci/tests/flux-schema/maku-gateway-render.yaml`, and `params.makuVersion` in
  `website/hugo.yaml`. `test-agent-factory-pins.py` and `check-site-contract.py` fail otherwise.
- A host change is a cloud-native-ref pull request first, then a `HOST_REF` bump here.
- **Site pages follow [`docs/docs-style.md`](../../docs-style.md)**; `task docs` enforces it. On a
  site page: no cluster name, date, handle, or plan and decision ID (such as WR4) in prose; state and
  "not yet" live on `status.md` only; the reference host's values are labelled "Example (the
  reference host):"; Maku is the product; a Maku file is linked with the `maku` shortcode; one
  Diátaxis type per page, under its word ceiling; a fact has one home and other pages link to it.
- Workflow names are exactly `quick`, `standard`, `careful`, `none`. No metric or label is renamed.
- Commits are conventional, in English, with no trailers.
- YAML structure edits use `yq -i`; diffs are read with `difft`.

## Gates

| Phase | Tasks | Needs Maku release | Needs |
|---|---|---|---|
| A | A1, A2, A3 | A (Maku plan A1 to A6) | A3 needs nothing from Maku and may merge first |
| B | B1, B2 | B (B1 to B7) | Phase A merged |
| C | C1, C2 | C (C1 to C6) | Phases A and B merged |
| D | D1, D2 | D (D1 to D5) | Phase A merged |
| E | E1, E2 | E (E1 to E7) | Phases C and D merged; the harness answer of Maku task E1 |
| F | F1, F2 | F (F1 to F6) | Phase E merged; the answer of Maku task F1 |
| G | G1, G2 | G (G1 to G6) | Phases B and F merged |
| H | H1 | H (H1 to H5) | Phase F merged; the answer of Maku task H1 |
| I | I1, I2 | I (I1 to I5) | Phase E merged; thirty merged tasks in phase D's report |

## Review Focus

1. **This repository writes its own `loops.default`, `workflows.standard` and `workflows.careful`,
   so Maku's repaired defaults do not reach it.** Maku fills a shipped entry only when its key is
   absent. The stall rule and, later, `stepUp` must be written here. Pinned by
   `test-agent-factory-workflows.py`, cases "standard stops a stalled run" (Task A1) and "the ladder"
   (Task C1).
2. **A `careful` row written here would hide Maku's.** This repository writes none today, so the
   shipped row, with its split and its `tests` key, applies. Pinned by the suite's case "no `careful`
   row of our own" (Task A1), removed only in Task I1.
3. **A site page that states a value the manifest does not hold.** Six pages did. Pinned by
   `test-site-workflow-claims.py` (Task A2), which reads the rendered `Factory` and the pages'
   tables together.
4. **A step-up that spends more than a Slack request allowed.** The channel's `maxCostUSD` is 2 and
   `careful`'s ceiling is 13.60: a Slack task must ask, never step. Pinned by the live step of Task
   C1 and by Maku's `TestACappedTaskAsksBeforeItStepsUp`.
5. **A broker or Slack value that names an act the pinned release does not know**: the broker does
   not start and nobody can file a task. Pinned by `test-room-broker-room-acts.py` (Task G1).
6. **A site page that describes a switch as on while the manifest leaves it off.** Each phase's site
   task lands in the pull request that turns the switch on, and `status.md` holds the state.

---

## Phase A · Repair the shipped model

Maku release A. No switch. Three pull requests: A3 first (it needs no pin), then A1 and A2 together
or one after the other.

### Task A1: Adopt release A: the stall rule, the reachable split, the tester by key

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`spec.loops` and its comment)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`
- Create: `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release A: the shipped `careful` row `{scope: scoper, judge: tier-light, search:
  true, tests: true, split: {maxChildren: 4, childTier: standard, anyTier: true}}`; a row may set
  `stallSteps` with `judge: none` (Maku task A1).
- Produces: the rendered `Factory` whose `default` row stops a stalled run. Later tasks read
  `spec.loops.default` and the absence of `spec.loops.careful`.

The block after the change:

```yaml
  # Loop policy: quick and standard stop a run that commits nothing in 80 steps and run no judge.
  # Maku ships the careful row (scoper, judge, search, tests, and a split of four parts at most).
  loops:
    default: {scope: "off", stallSteps: 80, judge: none}
```

- [ ] **Step 1: Write the failing cases**

Add to `scripts/ci/tests/test-agent-factory-workflows.py`, in its `check(name, ok)` style, over the
rendered base and each cluster overlay:

| Case | Assertion |
|---|---|
| standard stops a stalled run | `spec.loops.default.stallSteps` is an integer from 1 to 500 and `spec.loops.default.judge` is `none` |
| no `careful` row of our own | `spec.loops` has no `careful` key, so Maku's shipped row applies |
| no stale comment | the text of `factory.yaml` does not contain `stallSteps: 60` |
| the tester has a key to follow | no `Repository` sets `workflow.testFirst` without `merge.contractCheck` |

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero, on "standard stops a stalled run" and "no stale comment".

- [ ] **Step 3: Bump every pin to Maku release A, by digest**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py && python3 scripts/ci/check-site-contract.py`
Expected: both exit 0. Re-render `scripts/ci/tests/flux-schema/maku-gateway-render.yaml` with the
command in its first line, and copy the three CRDs from the release into
`scripts/ci/flux-schema/vendored-crds/`.

- [ ] **Step 4: Edit `factory.yaml`**

```bash
yq -i '.spec.loops.default = {"scope": "off", "stallSteps": 80, "judge": "none"}' \
  tooling/base/agent-factory/resources/factory.yaml
```

Replace the two comment lines above `loops:` with the two in the block above. `yq` drops the flow
style and the quotes on `"off"`: restore both by hand, so the line reads as in the block (an
unquoted `off` is a YAML boolean).

Run: `kustomize build tooling/base/agent-factory/resources | yq 'select(.kind == "Factory") | .spec.loops'`
Expected: `default: {scope: "off", stallSteps: 80, judge: none}` and nothing else.

- [ ] **Step 5: Run the suites and the gate**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && task check`
Expected: the suite exits 0 with every case `ok`; `task check` exits 0.

- [ ] **Step 6: Commit**

```bash
git add flux tooling infrastructure scripts website/hugo.yaml docs/runbooks
git commit -m "fix(agent-factory): standard and quick stop a stalled run (Maku release A)"
```

- [ ] **Step 7: Live check, recorded**

When the factory is up: `kubectl -n agent-system get factory -o json | jq '.items[0].status.conditions'`
shows `Accepted` and `Ready` true. File one issue with the label `workflow:careful` on
`Smana/ai-native-ref` whose text is wide enough to split; the task's `spec.split.maxChildren` is 4
and the room shows the scoper first. File one with no label; its `spec.loop` is
`{stallSteps: 80, continuations: 2}` with no `judgeModel`, and its room shows no judge mark. Record
both task names and the two fields in `results-workflows-roles-redesign.md`, section "Phase A".

### Task A2: The site states what the manifests and the code hold

**Files:**
- Modify: `website/content/docs/how-it-works/factory.md` (the "Workflows" and "Test-first tester"
  rows)
- Modify: `website/content/docs/reference/harness.md` (the rows `templates.pair`,
  `workflows.quick`, `workflows.standard`, `workflows.careful`, `defaults` / `triage.controlPercent`,
  `loops.careful`, and the "Judge and reviewer" bullet)
- Modify: `website/content/docs/reference/factory-configuration.md` (the "Control issue, defaults
  and workflows" row and the sentence naming `templates.pair.reviewerModel`)
- Modify: `website/content/docs/reference/planner.md` (the two `GET /v1/catalog` mentions)
- Modify: `website/content/docs/use/guide/writing-a-good-task.md` (the workflows table and the
  sentence "The planner picks the workflow")
- Modify: `website/content/docs/operate/tune-a-run.md` (the loop policy sentence that places
  `stallSteps` under `workflows.<name>`)
- Modify: `website/content/docs/how-it-works/roles.md` (the sentence on the split, which is now
  reachable, and the tester's sentence)
- Modify: `website/content/docs/status.md` (the "Workflow and model trials" row)
- Create: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Consumes: the rendered `Factory` of Task A1 and Maku release A's shipped rows.
- Produces: a suite later phases extend, one case per claim a page makes about a workflow.

What each page says after the change:

| Page | Was | Now |
|---|---|---|
| `how-it-works/factory.md`, Workflows | `standard` runs "the completion judge" | `standard` runs the implementer with its repository checks, then the reviewer; a run that commits nothing is stopped; the completion judge is `careful`'s |
| `how-it-works/factory.md`, Test-first tester | "on `standard` and `careful`" | on a task whose workflow's row sets `tests`: `careful` among the shipped three |
| `reference/harness.md`, `templates.pair` | `reviewerModel: kimi-frontier` | `{roles: [implementer, reviewer], maxReviewRounds: 2}`; the reviewer runs on the other tier's model |
| `reference/harness.md`, `workflows.*` | `stallSteps`, `continuations`, `judge` as workflow keys; `quick` with `tier: standard` | `quick: {template: solo}`, `standard: {template: pair, checks: true}`, `careful: {template: pair, tier: frontier, loop: careful, checks: true}` |
| `reference/harness.md`, `defaults` | an `evaluation` arm at 30% | no `evaluation` block: a task runs a maintainer's pin, else its source's workflow, else the repository's default |
| `reference/harness.md`, loops | `loops.careful` with `maxChildren: 5`, `familyUSD: 20.40` and no judge | two rows: `loops.default: {scope: "off", stallSteps: 80, judge: none}` (written here) and `loops.careful` (shipped by Maku), with the values of Task A1 |
| `reference/factory-configuration.md` | `templates.pair.reviewerModel: kimi-frontier` "in `factory.yaml`" | the sentence goes; the row lists the workflows and the `loops.default` line as the manifest holds them |
| `reference/planner.md` | `GET /v1/catalog` | `GET /v1/catalogue` |
| `use/guide/writing-a-good-task.md` | `standard` "with repository checks and the completion judge"; "The planner picks the workflow" | `standard`: implementer with repository checks, then reviewer. "Your repository's default workflow runs unless a maintainer chooses another, with a label or at confirmation. The planner may suggest one; a suggestion changes nothing until a maintainer picks it." |
| `operate/tune-a-run.md` | the loop policy under `workflows.<name>` | the loop policy is a `loops` row; a workflow names its row with `loop` |
| `how-it-works/roles.md` | the tester "for `careful` tasks" | the tester runs where the repository opts in and the workflow's row sets `tests` |
| `status.md` | "It will compare quick, standard, and careful" | Known limitation: no workflow or role has a measured value yet; per-role measurement is Planned (it becomes Experimental in phase D) |

- [ ] **Step 1: Write the failing suite**

`scripts/ci/tests/test-site-workflow-claims.py`, header `# requires: python3 kustomize`, same shape
as `test-agent-factory-workflows.py`. It renders the base `Factory`, reads the pages as text, and
fails with one line per problem:

| Case | Assertion |
|---|---|
| no judge in `standard` | no line of `how-it-works/factory.md`, `use/guide/writing-a-good-task.md` or `reference/harness.md` that contains `standard` also contains `judge`, unless it also contains `careful` or `none` |
| no workflow key that is a row key | no `reference/harness.md` table row starting `` `workflows. `` contains `stallSteps`, `continuations` or `judge:` |
| no reviewer model that the manifest lacks | `reviewerModel` appears on a site page only if the rendered `spec.templates.pair` has it |
| no evaluation arm that the manifest lacks | `treatment` appears in `reference/harness.md` only if the rendered `spec.evaluation` exists |
| the loops rows match | every `loops.<row>` row of `reference/harness.md` names `stallSteps` and `judge` values equal to the rendered ones for `default`, and `maxChildren: 4` and `anyTier: true` for `careful` |
| the route's spelling | no page contains `/v1/catalog` followed by anything but `ue` |
| nobody picks for you | no page contains "planner picks the workflow" |
| the tester's scope | no page contains "on `standard` and `careful`" |

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero, one line for each row of the table above except `status.md`.

- [ ] **Step 3: Rewrite the pages**

One page at a time, from the table. Keep each page's type: the two reference pages stay tables with
at most four columns and 25 words a cell; the guide chapter leads with what the reader does;
`roles.md` keeps the fact and links `reference/harness.md` for the values instead of repeating
them. Label the reference host's values "Example (the reference host):".

Run: `python3 scripts/ci/check-site-contract.py --report | grep -E 'harness|factory-configuration|writing-a-good-task|tune-a-run|roles|factory\.md'`
Expected: every listed page under its type's ceiling.

- [ ] **Step 4: Run the suite and the gate**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0 three times.

- [ ] **Step 5: Commit**

```bash
git add website scripts/ci/tests
git commit -m "docs(site): standard has no judge, nobody picks the workflow for you, and the rows match the manifest"
```

### Task A3: The comparison's runbook and results file say what happened

Needs no Maku release.

**Files:**
- Modify: `docs/runbooks/agent-factory/27-workflow-comparison.md`
- Modify: `docs/runbooks/agent-factory/results-workflow-comparison-1.md`
- Modify: `docs/runbooks/agent-factory/README.md` (the row for runbook 27)
- Modify: `scripts/ci/tests/test-agent-factory-evaluation-overlay.py`

**Interfaces:**
- Produces: a runbook whose commands run against the pinned CRDs, kept for a later comparison; a
  results file that states its outcome.

- [ ] **Step 1: Write the failing case**

Add to `test-agent-factory-evaluation-overlay.py`:

| Case | Assertion |
|---|---|
| the runbook reads fields that exist | `27-workflow-comparison.md` contains none of `.spec.harnessProfile`, `.status.cohort`, `.status.costMicroUSD`, `SHA-256`, `treatmentPercent`, `cohort: none` |
| the results file is not "collecting" | `results-workflow-comparison-1.md` does not contain `collecting` or `Pending 40 tasks` |
| the runbook names no file that is gone | every path under `tooling/` that the runbook names exists |

Run: `python3 scripts/ci/tests/test-agent-factory-evaluation-overlay.py`
Expected: non-zero on the three cases.

- [ ] **Step 2: Rewrite runbook 27**

| Section | Now |
|---|---|
| Lead | The comparison is not running. This is the procedure for a later one, and it is no longer a precondition for step-up or per-role measurement (the redesign's first owner ruling). Cite the design as WF8, not WF9 |
| The overlay | The patch to add under a cluster's overlay, as a code block: `spec.evaluation: {controlPercent: 50, treatment: careful, mode: observe}`. The file does not exist until someone starts a comparison |
| The draw | FNV-32a of `evaluation/<task name>` modulo 100, below `controlPercent` is `control`, else `treatment`; a pinned task is `labeled` |
| Reading the arms | `kubectl -n agent-system get tasks.maku.ogenki.io -o custom-columns='NAME:.metadata.name,ISSUE:.spec.issue,WORKFLOW:.status.profile.name,SOURCE:.status.profile.source,COHORT:.status.profile.cohort,PHASE:.status.phase'`, and dollars from `agent_factory_task_usd_total` by `cohort`, filtered to `source=~"control\|treatment"` |
| Size and rule | The design's: 30 ended tasks per arm; better or worse is 15 points of merge rate, or 20% of cost per merged pull request with the merge rate no worse |

- [ ] **Step 3: Close the results file**

Replace the status line and the decision:

```markdown
**Status:** closed without data. The overlay was removed before it recorded a task.

## Decision

None: no task ran in either arm. Per-role cost and effect are now recorded on every task instead
(the workflows and roles redesign, phase D); a comparison stays possible with runbook 27.
```

The empty table goes. Update the README's row to "Procedure for a workflow comparison; none is
running".

- [ ] **Step 4: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-evaluation-overlay.py && task check`
Expected: exit 0.

```bash
git add docs/runbooks scripts/ci/tests
git commit -m "docs(runbooks): the workflow comparison's runbook reads fields that exist, and its results are closed"
```

---

## Phase B · One card, one strip, one vocabulary

Maku release B. No switch: display only. Nothing under `tooling/base/agent-factory/resources/`
changes except the pins.

### Task B1: Adopt release B

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (the two workflow descriptions)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`
- Modify: `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release B: the catalogue serves each workflow's `description`, `ceilingUSD` and
  `path`; the description now reaches Slack's select (75 characters with its ceiling) and the
  `start` form.
- Produces: descriptions a person reads at confirmation.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| every workflow written here has a description | each key of `spec.workflows` has a non-empty `description` of at most 120 characters |
| a description fits Slack's select | each description, cut at the last word boundary before 60 characters, is still a sentence start (it holds at least one space) |
| a description names no internal word | no description contains `tier`, `template`, `loop`, `profile` or `triager` |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: exit 0 already for the first two (the manifest has descriptions): the cases are the pin
for later edits. If the third fails, fix the text in Step 3.

- [ ] **Step 2: Bump every pin to Maku release B, by digest**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py && python3 scripts/ci/check-site-contract.py`
Expected: both exit 0.

- [ ] **Step 3: Rewrite the two descriptions for a person choosing**

```yaml
    standard:
      description: "An implementer and a reviewer. The default."
    careful:
      description: "Planned first, judged before review. For wide or unclear tasks."
```

(`careful`'s matches the spec's wording.)

- [ ] **Step 4: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website/hugo.yaml
git commit -m "feat(agent-factory): the workflow card on every surface (Maku release B)"
```

- [ ] **Step 5: Live check, recorded**

On one task filed from each entry (a label, Slack, a coding agent's `start`), capture where the card appears:
the first GitHub comment before the first run, the Slack plan message, the `start` form, `maku
status`, the room's header. Each shows the workflow, its reason, the path and "up to $5.10"; none
shows "tier" or "(triager)". Record the five captures as text in the results file, section
"Phase B".

### Task B2: The site shows the card and uses one vocabulary

**Files:**
- Modify: `website/content/docs/use/guide/your-first-task.md` (the Slack plan sample, the first
  comment, the "Sorted the task" sentence, the `start` form's defaults)
- Modify: `website/content/docs/use/slack.md` (the plan message sample and the select)
- Modify: `website/content/docs/use/guide/writing-a-good-task.md` (the anchor `#classes` gains
  `{#workflows}` and keeps `{#classes}`; the table gains "Costs up to")
- Modify: `website/content/docs/use/guide/following-and-steering.md` (the room page's header, the
  status comment, the path strip, cost in dollars)
- Modify: `website/content/docs/use/guide/terminal-and-coding-agent.md` (the `status` sample, the
  form)
- Modify: `website/content/docs/use/guide/cheat-sheet.md` (one status vocabulary; the tool list
  matches the release)
- Modify: `website/content/docs/use/guide/merging.md` (says "merge policy" where it said "class" for
  the thing a person reads)
- Modify: `website/content/docs/operate/tune-a-run.md` (the callout that says "template")
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Consumes: the five captures of Task B1.
- Produces: one sample of the card, in `use/guide/your-first-task.md`; every other page links to it.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| no tier beside a workflow | no page under `use/` contains `(tier ` or `tier standard` |
| the scoper is a scoper | no page contains `(triager)` |
| one plan message | `use/slack.md` and `use/guide/your-first-task.md` do not both hold a fenced Slack plan sample: the guide holds it, the Slack page links to it |
| the card's three lines | `use/guide/your-first-task.md` holds a fenced block with lines starting `Workflow`, `Will run` and `Cost` |
| one status vocabulary | `use/guide/cheat-sheet.md` lists exactly the seven words: planning, working, checking, waiting on you, waiting on a check, done, stopped |
| budget is dollars | no page under `use/guide/` contains `M tokens` outside a fenced block |

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero on at least the first four.

- [ ] **Step 2: Rewrite the pages**

`your-first-task.md` gets the card as its one sample, labelled as the reference host's example:

````markdown
Example (the reference host):

```text
Fix the broken link checker on the docs site          owner/repo
Workflow   standard · this repository's default
Will run   implementer → reviewer → CI → merge gate
Cost       up to $5.10
```
````

Then three short paragraphs, one idea each: what "Workflow" and its reason mean, what "Will run"
lists, what "Cost" promises (a ceiling, not a price). The sentence "You do not pick either" becomes
"You do not have to pick anything: your repository's default workflow runs, and a maintainer may
choose another." The other pages lose their own copies of the plan message and link the guide's.

- [ ] **Step 3: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0.

```bash
git add website scripts/ci/tests
git commit -m "docs(site): one workflow card and one vocabulary across the user guide"
```

---

## Phase C · Step up once, and "run again deeper"

Maku release C. Switches: `spec.workflows.<name>.stepUp` on the `Factory` and
`spec.workflow.stepUp` on each `Repository`. This repository writes its own `standard` entry, so
nothing steps up here until Task C1 adds the key.

### Task C1: Adopt release C and switch the ladder on

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`spec.workflows.standard.stepUp`)
- Modify: `tooling/base/agent-factory/resources/repository-{ai-native-ref,cloud-native-ref,runlore,runlore-kb}.yaml`
  (`spec.workflow.stepUp`)
- Modify: `tooling/base/agent-factory/slack-bindings.yaml`, `tooling/base/agent-factory/slack-app/config.yaml`
  (nothing new to enable: `retry` already covers "run again deeper"; the case below pins it)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`
- Create: `docs/runbooks/agent-factory/29-step-up.md`
- Modify: `docs/runbooks/agent-factory/README.md`, `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release C: `stepUp` on a workflow; `Repository.spec.workflow.stepUp` (`auto`,
  `ask`, `off`); `/factory retry deeper`; `maku retry --deeper`; the metric
  `agent_factory_step_ups_total` arrives with release D.
- Produces: the ladder `standard` → `careful` on three repositories, and `ask` on the host.

The values:

| Object | Key | Value | Why |
|---|---|---|---|
| `Factory` | `spec.workflows.standard.stepUp` | `careful` | The one automatic step. `quick` is Maku's shipped entry and already steps to `standard` |
| `repository-ai-native-ref.yaml`, `repository-runlore.yaml`, `repository-runlore-kb.yaml` | `spec.workflow.stepUp` | `auto` | Written out although it is the default, so the suite can read it |
| `repository-cloud-native-ref.yaml` | `spec.workflow.stepUp` | `ask` | The host carries the two classes that merge alone; a deeper run there is a maintainer's call |

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| the ladder | the rendered `spec.workflows.standard.stepUp` is `careful`; `spec.workflows.careful` has no `stepUp` and no `escalation` |
| no workflow sets both | no workflow has both `stepUp` and `escalation` |
| every repository says how it steps | each `Repository` sets `spec.workflow.stepUp` to `auto`, `ask` or `off` |
| the host asks | `repository-cloud-native-ref.yaml` sets `ask` |
| a Slack task cannot step silently | for each Slack binding, `maxCostUSD` is below the `frontier` tier's `taskUSD`, or the binding's repositories all set `stepUp: ask` (Maku asks when the cap is below the stepped-up ceiling; the case fails if someone raises the cap past it without noticing) |
| the stepped-up ceiling is affordable | `caps.concurrentRuns` × the `frontier` tier's `runUSD` is at most `budgets.factoryDailyUSD` |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero on "the ladder" and "every repository says how it steps".

- [ ] **Step 2: Bump every pin to Maku release C, by digest**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py && python3 scripts/ci/check-site-contract.py`
Expected: both exit 0.

- [ ] **Step 3: Edit the objects**

```bash
yq -i '.spec.workflows.standard.stepUp = "careful"' tooling/base/agent-factory/resources/factory.yaml
for r in ai-native-ref runlore runlore-kb; do
  yq -i '.spec.workflow.stepUp = "auto"' "tooling/base/agent-factory/resources/repository-$r.yaml"
done
yq -i '.spec.workflow.stepUp = "ask"' tooling/base/agent-factory/resources/repository-cloud-native-ref.yaml
```

Read each diff with `difft`; restore any comment or flow style `yq` moved. Add one comment line
above `stepUp` in `factory.yaml`: "A standard task that stalls, runs out of budget or of review
rounds runs once more as careful."

- [ ] **Step 4: Write runbook 29**

`docs/runbooks/agent-factory/29-step-up.md`, with these sections and nothing else:

1. **What it proves.** One automatic step on a verified failure; an offer in place of a step on a
   pin, on a capped Slack task and on the host; "run again deeper" by comment, CLI, room and Slack.
2. **Drill 1, automatic.** An issue on `Smana/ai-native-ref` with no label, written so the
   implementer cannot commit in 80 steps (it asks for a change to a file that does not exist and
   forbids creating it). Expected: `Escalated stalled` never shows; the task goes back to `Queued`,
   `status.profile.name` becomes `careful`, `status.profile.stepUp` is `{from: standard, to:
   careful, trigger: stalled, mode: auto}`, one comment names the new ceiling, the same branch.
3. **Drill 2, pinned.** The same issue text with `workflow:standard`. Expected: `Escalated`,
   `stepUp.mode: offered`, the comment says a maintainer pinned it; then `/factory retry deeper`
   steps it, `mode: manual`.
4. **Drill 3, Slack.** The same request from the Slack channel. Expected: an offer, the reason
   "its budget is capped below", and the button **Run again deeper** refused with
   `deeper_over_cap`.
5. **Drill 4, the host.** One issue on `Smana/cloud-native-ref`. Expected: an offer, the reason
   "this repository asks first".
6. **Stop.** `factory/stop` during a stepped-up run ends it; the pull request stays open.
7. **Results.** One row per drill in the results file: task, trigger, mode, dollars before and
   after the step, how it ended.

- [ ] **Step 5: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website/hugo.yaml docs/runbooks
git commit -m "feat(agent-factory): a standard task steps up to careful once (Maku release C)"
```

- [ ] **Step 6: Live check, recorded**

Run the four drills of runbook 29 when the factory is up. Record them in the results file, section
"Phase C", with the share the spec asks for: of the tasks that would have escalated, how many one
step rescued.

### Task C2: The site explains the step-up

**Files:**
- Modify: `website/content/docs/use/guide/when-things-go-wrong.md` (a section "The factory tried
  once more, deeper")
- Modify: `website/content/docs/use/guide/when-the-factory-needs-you.md` (the offer and its button)
- Modify: `website/content/docs/use/guide/your-first-task.md` (the card's cost line)
- Modify: `website/content/docs/use/guide/cheat-sheet.md` (`/factory retry deeper`,
  `maku retry --deeper`)
- Modify: `website/content/docs/use/slack.md` (the **Run again deeper** button)
- Modify: `website/content/docs/how-it-works/factory.md` (a "Step-up" row replacing nothing)
- Modify: `website/content/docs/reference/harness.md` (the `stepUp` rows)
- Modify: `website/content/docs/reference/commands.md`
- Modify: `website/content/docs/status.md` (Step-up: Experimental, linking runbook 29's results)
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Produces: the step-up's one home, the section in `when-things-go-wrong.md`; the five other pages
  link to it in a sentence.

The section's content, in the guide's voice:

1. What you see: one message, in the thread, the room and the issue, saying the workflow changed,
   why, the new ceiling and how to stop it.
2. When it happens: a run that committed nothing, a spent run budget, a judge or a reviewer that
   ran out of rounds, checks that stayed red. Never because the task is impossible or waits for
   your answer.
3. When it asks instead: a maintainer pinned the workflow, your request had a lower cap, or the
   repository asks first. Then a maintainer presses **Run again deeper** or comments
   `/factory retry deeper`.
4. Once: a second failure comes to a maintainer.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| the card's cost line names the step | the card sample in `your-first-task.md` holds `if it steps up` exactly when the rendered `standard` workflow has `stepUp` |
| the ladder on the page is the manifest's | `reference/harness.md` names, for each workflow, the `stepUp` target the rendered `Factory` holds (and Maku's shipped `quick` → `standard`) |
| the command is spelled once | `/factory retry deeper` appears in `cheat-sheet.md` and `reference/commands.md`, and every other occurrence under `use/` is in a sentence that links one of them |
| no state off the status page | no page but `status.md` contains "Experimental" beside "step" |

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero on the first three.

- [ ] **Step 2: Write the section and the rows**, then update the card sample:

```text
Cost       up to $5.10 · up to $13.60 if it steps up
```

- [ ] **Step 3: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0.

```bash
git add website scripts/ci/tests
git commit -m "docs(site): what a step-up is, when it asks first, and how to run a task again deeper"
```

---

## Phase D · Measure every role on every task

Maku release D. No switch: recording is passive. The card's "typical cost" appears by itself once a
class has thirty merged tasks.

### Task D1: Adopt release D, with the stage view and its alerts

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/vmservicescrape.yaml` only if release D's notes name a new
  metrics port or path (they should not)
- Create: `observability/base/agent-platform/grafana-dashboard-agent-stages.yaml` ("Agent factory:
  stages"), in the shape of `grafana-dashboard-agent-factory.yaml` beside it
- Modify: `observability/base/agent-platform/kustomization.yaml` (list the dashboard)
- Modify: `observability/base/agent-platform/vmrule-agent-factory.yaml` (two recording rules)
- Create: `scripts/ci/tests/test-agent-factory-stage-metrics.py`
- Create: `docs/runbooks/agent-factory/30-stage-report.md`
- Modify: `docs/runbooks/agent-factory/README.md`, `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release D: `agent_factory_stage_cost_usd`, `agent_factory_stage_effects_total`,
  `agent_factory_workflow_choices_total`, `agent_factory_ceiling_use_ratio`,
  `agent_factory_step_ups_total`; `GET /v1/stages`; `maku stages`.
- Produces: one dashboard by repository, merge-policy class and stage, which v5 Track 3 (outcome
  analytics) takes over with stage, not workflow name, as its dimension.

The dashboard's panels, each one query:

| Panel | Query |
|---|---|
| Dollars per merged pull request, by stage | `sum by (stage) (increase(agent_factory_stage_cost_usd_sum[$__range])) / scalar(sum(increase(agent_factory_task_outcomes_total{outcome=~"accepted\|merged_human"}[$__range])))` |
| What the reviewer changed | `sum by (effect) (increase(agent_factory_stage_effects_total{stage="review"}[$__range]))` |
| The judge against the outcome | `sum by (effect) (increase(agent_factory_stage_effects_total{stage="judge"}[$__range]))` |
| Scoper, tester, split | the same, `stage=~"plan\|tests\|split\|ask"`, by `stage` and `effect` |
| Choices left unchanged, by class | `sum by (class) (increase(agent_factory_workflow_choices_total{choice="kept"}[$__range])) / sum by (class) (increase(agent_factory_workflow_choices_total[$__range]))` |
| Tasks that stepped up, and how they ended | `sum by (trigger, outcome) (increase(agent_factory_step_ups_total{mode=~"auto\|manual"}[$__range]))` |
| Spend against the ceiling shown | `histogram_quantile(0.5, sum by (le, class) (increase(agent_factory_ceiling_use_ratio_bucket[$__range])))`, and the same at 0.9 |

- [ ] **Step 1: Write the failing suite**

`scripts/ci/tests/test-agent-factory-stage-metrics.py`, header `# requires: python3`:

| Case | Assertion |
|---|---|
| every panel reads a metric the release serves | each `expr` of the dashboard names only metrics from a list at the top of the script (the five above and `agent_factory_task_outcomes_total`) |
| no panel is keyed by workflow name | no `expr` of the dashboard groups `by (profile)` |
| the rules parse | each new recording rule's `expr` is non-empty and its `record` starts `agent_factory:` |

Run: `python3 scripts/ci/tests/test-agent-factory-stage-metrics.py`
Expected: non-zero (no dashboard file).

- [ ] **Step 2: Bump every pin to Maku release D, by digest**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py && python3 scripts/ci/check-site-contract.py`
Expected: both exit 0.

- [ ] **Step 3: Add the dashboard and two recording rules**

`agent_factory:step_up_rescue:ratio30d` (stepped tasks that merged over stepped tasks) and
`agent_factory:choice_kept:ratio30d` (by class). No alert: nothing here pages anyone.

- [ ] **Step 4: Write runbook 30**

`docs/runbooks/agent-factory/30-stage-report.md`: how to read `maku stages --repository
Smana/ai-native-ref`, what each effect word means (one table, copied from Maku's
`docs/observability.md`), the rule that no default changes from these numbers without an owner
ruling, and the reading to record after the first thirty merged tasks: one row per stage and class
with tasks, dollars and effects.

- [ ] **Step 5: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-stage-metrics.py && task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure observability scripts website/hugo.yaml docs/runbooks
git commit -m "feat(agent-factory): a cost and an effect per stage, on one dashboard (Maku release D)"
```

- [ ] **Step 6: Live check, recorded**

After five ended tasks: `maku stages --repository Smana/ai-native-ref` lists `implement` and
`review` with dollars; the dashboard's first panel has a value. After thirty merged tasks, fill
runbook 30's table in the results file, section "Phase D". That table is the spec's measure "every
role has a cost and an effect figure per class".

### Task D2: The site says what is measured

**Files:**
- Modify: `website/content/docs/operate/observability.md` (a section "What each role costs and
  changes")
- Modify: `website/content/docs/how-it-works/roles.md` (one sentence per role linking that section)
- Modify: `website/content/docs/how-it-works/routing-and-cost.md` (the "typical cost" on the card)
- Modify: `website/content/docs/status.md` (per-role measurement: Experimental; the old "Workflow
  and model trials" limitation is reworded to the comparison alone)
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Produces: the measurement's one home, `operate/observability.md`. No figure goes on the site: the
  figures live in the results file and on the dashboard.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| each role's effect is defined before it is used | every effect word that appears on a site page (`changes_committed`, `approve_overruled`, `met_not_merged`, and the others) appears first in the table of `operate/observability.md` |
| no measured figure on the site | no page but `status.md` holds a dollar figure in a sentence that also holds "typical", "median" or "per merged" unless the paragraph is labelled as the reference host's example |

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: exit 0 before the edit (nothing uses the words); it pins the edit.

- [ ] **Step 2: Write the section**: a how-to page's section, leading with what the reader does
  ("Open the stages dashboard, pick a repository and a policy"), then one table, Stage / What is
  counted / What it tells you, of at most four columns.

- [ ] **Step 3: Run the gate and commit**

Run: `task docs && task check`
Expected: exit 0.

```bash
git add website scripts/ci/tests
git commit -m "docs(site): what each role costs and changes, and where to read it"
```

---

## Phase E · Unbundle `careful`

Maku release E. Switches: the row keys `ask`, `plan`, `tests`, `search`, `judge`, `review`, `split`;
`scoper.planTier`; `loops.<row>.judgeInput`; a `MergePolicy`'s `requires`. If Maku task E1 found the
harness half not ready, release E ships without `judgeInput`, and Step 3 below leaves that key out.

### Task E1: Adopt release E: the rows as stage switches, the plan on the strong model, one class that requires a plan

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`spec.loops`, `spec.scoper`,
  `spec.workflows`)
- Modify: `tooling/base/agent-factory/resources/mergepolicy-alert-rules.yaml` (`spec.requires`)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`
- Modify: `docs/runbooks/agent-factory/17-splitter.md`, `21-test-first-tester.md`
- Modify: `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release E.
- Produces: the three presets as three rows this repository can read in its own manifest.

The values:

```yaml
  scoper: {planTier: frontier}
  loops:
    default: {ask: true, review: true, scope: "off", stallSteps: 80, judge: none}
```

`spec.workflows.standard` and `careful` lose `template` only if release E's notes say `review`
resolves it; otherwise they keep it. The `careful` row stays Maku's.

`mergepolicy-alert-rules.yaml` gains `requires: [plan]`: a change to an alert rule is small and its
blast radius is not, which is the spec's own example of a class that wants the plan gate. It takes
effect as a gate only in phase F; in release E it makes such a task run the scoper.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| the presets are the spec's table | resolving each of `quick`, `standard`, `careful` against the rendered `Factory` and Maku's shipped rows (a table at the top of the script, copied from the release notes) gives: `ask` on for all three; `review` off for `quick` only; `plan`, `search`, `judge`, `split` on for `careful` only |
| the reviewer stays | no row sets `review: false` except `quick`'s |
| a required stage is one a class may require | every `MergePolicy` `spec.requires` entry is one of `plan`, `tests`, `judge`, `review` |
| a required tester has its paths | a policy that requires `tests` is bound only on repositories with `tests.paths` and `merge.contractCheck` |
| the plan runs on the strong model | `spec.scoper.planTier` is `frontier` |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero on the first and the last.

- [ ] **Step 2: Bump every pin to Maku release E, by digest**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py && python3 scripts/ci/check-site-contract.py`
Expected: both exit 0.

- [ ] **Step 3: Edit the objects** with `yq -i`, read the diffs, restore the quoted `"off"`.

Run: `kustomize build tooling/base/agent-factory/resources | yq 'select(.kind == "Factory") | .spec.loops, .spec.scoper'`
Expected: the block above.

- [ ] **Step 4: Update the two runbooks**: a split and a tester are reached through the row keys
  `split` and `tests`; the instruction "label the issue `workflow:careful`" stays as the way to get
  both on one task.

- [ ] **Step 5: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website/hugo.yaml docs/runbooks
git commit -m "feat(agent-factory): careful as stage switches, and a plan for alert rules (Maku release E)"
```

- [ ] **Step 6: Live check, recorded**

Three tasks: a `standard` issue with no acceptance (expected: one question, no run, no dollars); a
`careful` issue (expected: the scoper's run on the `frontier` tier's model, in the room's rail); a
change under the alert-rules class's paths with no label (expected: a scoper run before the
implementer, and the card's reason names the class). Then read phase D's `review` effects for the
twenty tasks before and after the release and record both rows: that is the measure of the
reviewer's new brief.

### Task E2: The site describes stages, not a bundle

**Files:**
- Modify: `website/content/docs/how-it-works/roles.md` (the roles table and the mermaid diagram:
  the question at intake, the plan on the strong model, the judge on machine evidence, the reviewer
  on correctness)
- Modify: `website/content/docs/how-it-works/factory.md` ("Workflows", "Scope and split",
  "Test-first tester" rows)
- Modify: `website/content/docs/use/guide/writing-a-good-task.md` (the workflows table becomes the
  spec's stage table, three columns of workflows; the acceptance question applies to every workflow)
- Modify: `website/content/docs/use/guide/when-the-factory-needs-you.md` (the question may come
  before any run)
- Modify: `website/content/docs/use/guide/merge-policies.md` (a policy may require a stage)
- Modify: `website/content/docs/reference/harness.md` (the `loops` rows with the seven keys)
- Modify: `website/content/docs/operate/tune-a-run.md` ("Run the judge alone", a how-to the old
  bundle could not offer)
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Produces: the stage table's one home, `use/guide/writing-a-good-task.md`; `roles.md` explains
  each role and links it.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| the page's stage table is the manifest's | the table in `writing-a-good-task.md` has one row per switch (`ask`, `plan`, `tests`, `search`, `judge`, `review`, `split`) and its on/off cells equal the resolution Task E1's suite computes |
| the diagram fits | the mermaid block in `roles.md` declares `flowchart TB` and at most twelve nodes (rule 17's ratio) |
| the judge is not said to read prose | no page says the judge reads the agent's "summary", "report" or "message" |
| five roles | `roles.md` names exactly scoper, tester, implementer, judge, reviewer in its table |

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero on the first.

- [ ] **Step 2: Rewrite the pages.** The roles table keeps three columns (Role / What it does /
  Writes code?). A term is defined before its first use: "stage" is defined once, in
  `writing-a-good-task.md`, as "one step of a task's path that a workflow turns on or off".

- [ ] **Step 3: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0.

```bash
git add website scripts/ci/tests
git commit -m "docs(site): a workflow is a list of stages, and each role's new shape"
```

---

## Phase F · Outcomes beyond a pull request

Maku release F. Switches: `Factory.spec.outcomes` and `Repository.spec.workflow.planGate`.

### Task F1: Adopt release F and offer the four outcomes

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`spec.outcomes`)
- Modify: the four `repository-*.yaml` (`spec.workflow.planGate`)
- Modify: `tooling/base/agent-factory/slack-bindings.yaml`, `slack-app/config.yaml` (a review by
  mention, if release F's notes name an intent action for it)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`
- Create: `docs/runbooks/agent-factory/31-outcomes.md`
- Modify: `docs/runbooks/agent-factory/README.md`, `results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release F: `Task.spec.outcome`; the labels `plan-first`, `report`,
  `factory/review`; the plan gate's three answers; `/factory fix`; the answer of Maku task F1 on
  approve-to-merge under a two-approval ruleset.
- Produces: `spec.outcomes: [change, plan-first, review, report]` and `planGate: ask` on every
  repository.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| the outcomes offered | the rendered `spec.outcomes` holds `change` and is a subset of the four |
| every repository says how its plan gate answers | each `Repository` sets `spec.workflow.planGate` to `ask` or `auto` |
| no unattended plan on the host | `repository-cloud-native-ref.yaml` sets `ask` |
| a class that requires a plan has a gate to wait at | if any `MergePolicy` requires `plan`, `plan-first` is among the outcomes |
| the labels exist where they are read | `plan-first`, `report` and `factory/review` are in the label allow-list the `Factory` holds, when it holds one |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero on the first two.

- [ ] **Step 2: Bump every pin, edit the objects, read the diffs** (as in the earlier phases).

- [ ] **Step 3: Apply the answer of Maku task F1**

| Maku's answer | Here |
|---|---|
| A two-approval ruleset holds the merge | Nothing to change; runbook 31 says two-human sign-off is a ruleset on the repository |
| The merger App bypasses it | A cloud-native-ref pull request removes the App from the ruleset's bypass list for the repositories that want two approvals, then a `HOST_REF` bump here; `maku repo check` passes on all four |
| Not readable from code | Runbook 31 gains drill 5: a throwaway repository with a required-approvals rule of two; one approval must not merge. Its result goes back to Maku's pull request F-1 |

- [ ] **Step 4: Write runbook 31**, four drills, one per outcome, each with the expected end:
  `plan-first` (the plan comment, **Approve**, then a pull request; then **Revise** on a second
  issue; then a gate left unanswered, which stays parked and says so, with no pod: `kubectl get
  agentrun` lists none for the task); `review` (the label on a person's pull request: a verdict
  comment, no push, no merge, and the gate's status on that pull request unchanged); `report` (an
  issue that asks "why": findings on the issue, no branch, then `/factory fix`); `change` (the
  control: unchanged).

- [ ] **Step 5: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website/hugo.yaml docs/runbooks
git commit -m "feat(agent-factory): plan first, review only and report only (Maku release F)"
```

- [ ] **Step 6: Live check, recorded**: the drills of runbook 31, in the results file, section
  "Phase F".

### Task F2: The site adds three ways a task can end

**Files:**
- Create: `website/content/docs/use/guide/outcomes.md` (a how-to chapter: "Ask for a plan, a review
  or an answer"), with its `weight` after `writing-a-good-task.md`
- Modify: `website/content/docs/use/guide/_index.md` (the chapter list),
  `website/content/docs/use/guide/cheat-sheet.md` (the three labels, the plan gate's three answers,
  `/factory fix`)
- Modify: `website/content/docs/use/guide/when-the-factory-needs-you.md` (a plan to approve)
- Modify: `website/content/docs/use/guide/merging.md` (two-human sign-off is a GitHub ruleset; a
  plan's approval is not a pull request's)
- Modify: `website/content/docs/how-it-works/factory.md` (an "Outcomes" row),
  `website/content/docs/how-it-works/roles.md` (the scoper's plan may wait at a gate)
- Modify: `website/content/docs/reference/commands.md`, `website/content/docs/reference/gate-reasons.md`
  (`required_stage_missing`, if phase E did not add it)
- Modify: `website/content/docs/status.md` (three lines: plan first, review only, report only)
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Produces: the outcomes' one home, the new chapter, under 1,200 words, `diataxis: how-to`.

The chapter's shape: one short section per outcome, each leading with what the reader does (the
label, the Slack sentence, the button), then what comes back, then what it never does (a `review`
never pushes or merges; a `report` opens no pull request; a plan that nobody answers stays parked).

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| the chapter exists and is listed | `use/guide/outcomes.md` declares `diataxis: how-to` and `_index.md` links it with a `relref` |
| the outcomes on the page are those offered | the chapter names exactly the outcomes in the rendered `spec.outcomes` |
| the wait is the manifest's | the hours the chapter states for the plan gate equal `planGateHours` of the rendered repositories, or Maku's default when unset |
| a reason is defined before it is shown | `plan_review` and `findings_posted` appear in code style only after a sentence that says what they report |

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero on the first.

- [ ] **Step 2: Write the chapter and the edits.**

- [ ] **Step 3: Run the suite and the gate, commit**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task links && task check`
Expected: exit 0.

```bash
git add website scripts/ci/tests
git commit -m "docs(site): ask for a plan, a review or an answer"
```

---

## Phase G · Act where you read

Maku release G. Switch: the broker's `human.roomActs`.

### Task G1: Adopt release G and enable the room's acts

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `infrastructure/base/room-broker/config.yaml` (`human.roomActs`), and each cluster's copy
  that overrides `human`
- Modify: `tooling/base/agent-factory/slack-bindings.yaml`, `slack-app/config.yaml`
  (`intentActions` gains the acts release G adds for Slack: the split's and the plan's buttons)
- Create: `scripts/ci/tests/test-room-broker-room-acts.py`
- Modify: `scripts/ci/tests/test-room-broker-config-parity.py` (the new key in every copy)
- Modify: `docs/runbooks/agent-factory/27-six-tools-and-slack-acts.md` (its results table gains the
  room and CLI columns), `results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release G: the acts `answer`, `retry`, `split`, `plan`, `file`, `stop`;
  `maku answer`, `maku split`, `maku plan`; the web "New task"; the five inbox types; the three
  notification classes.
- Produces: `human.roomActs: [answer, retry, split, plan, file, stop]` on the reference host.

- [ ] **Step 1: Write the failing suite**

`scripts/ci/tests/test-room-broker-room-acts.py`, header `# requires: python3`:

| Case | Assertion |
|---|---|
| every act is one the release knows | each entry of `human.roomActs`, in every copy of the broker's config, is in the list at the top of the script (the six above) |
| `plan` needs the outcome | `plan` is enabled only if the rendered `Factory.spec.outcomes` holds `plan-first` |
| `file` needs the planner | `file` is enabled only in a copy whose `intake.plan.enabled` is true |
| Slack offers no act the room refuses | every Slack `intentActions` entry that has a room act of the same name is also in `human.roomActs` |

Run: `python3 scripts/ci/tests/test-room-broker-room-acts.py`
Expected: non-zero (no `roomActs`).

- [ ] **Step 2: Bump every pin, edit the config copies, run the parity suite.**

Run: `python3 scripts/ci/tests/test-room-broker-room-acts.py && python3 scripts/ci/tests/test-room-broker-config-parity.py`
Expected: both exit 0.

- [ ] **Step 3: Run the gate and commit**

Run: `task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website/hugo.yaml docs/runbooks
git commit -m "feat(room-broker): answer, accept a split, approve a plan and file a task from the room (Maku release G)"
```

- [ ] **Step 4: Live check, recorded**: the spec's act table, one cell at a time. For each of the
  six acts and each of the four surfaces that the table marks, do the act once and record pass or
  fail in runbook 27's results table. The inbox: one task in each of the five types, listed
  identically by the room list's filter, `maku needs`, Slack's `needs me` and the `inbox` tool.

### Task G2: The site's guide follows the acts to where they now are

**Files:**
- Modify: `website/content/docs/use/guide/when-the-factory-needs-you.md` (the "Room buttons by
  need" table: a button for the question, the split, the plan and the retry; the five inbox types;
  the three kinds of notification)
- Modify: `website/content/docs/use/guide/following-and-steering.md` (**New task** beside **New
  room**; one **Stop** button)
- Modify: `website/content/docs/use/guide/terminal-and-coding-agent.md` (the CLI's acts)
- Modify: `website/content/docs/use/guide/when-things-go-wrong.md` (stopping: one verb, one place
  per surface)
- Modify: `website/content/docs/use/guide/cheat-sheet.md` (the acts table, four columns: act, web
  room, CLI, Slack; GitHub's column moves to `reference/commands.md`)
- Modify: `website/content/docs/use/slack.md` (the buttons; what a mention means)
- Modify: `website/content/docs/reference/commands.md`
- Modify: `website/content/docs/status.md`
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`

**Interfaces:**
- Produces: the acts table's one home, the cheat sheet.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| no act is sent to GitHub when the room has it | no page under `use/guide/` says "Answer it on GitHub", "Confirm it on GitHub" or "comment `/factory retry`" as the only way, when the matching act is in `human.roomActs` |
| the CLI's commands exist | every `maku <verb>` in the cheat sheet is in a list at the top of the script, taken from the pinned release's `maku help` |
| five inbox types | `when-the-factory-needs-you.md` lists exactly question, plan to review, pull request to review, blocked, failed |
| the table fits | the cheat sheet's acts table has at most four columns and 25 words a cell |

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero on the first three.

- [ ] **Step 2: Rewrite the pages**, then **Step 3: run the gate and commit**

Run: `python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0.

```bash
git add website scripts/ci/tests
git commit -m "docs(site): answer, accept, retry and file where you read"
```

---

## Phase H · Decomposition

Maku release H. Switches: the broker's `intake.wholePlans` and `loops.<row>.split.parallel`.

**What waits for an earlier result:** whether dependent parts are stacked is Maku task H1's answer;
if stacks were not built, drill 3 below is dropped and the site's page says parts run in order. The
parallel switch is turned on here only after phase D's report shows that waiting dominates a split
family's wall time on this host; until then Step 3 sets `wholePlans` alone.

### Task H1: Adopt release H: whole plans, then two parts at a time

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `infrastructure/base/room-broker/config.yaml` and each cluster's copy
  (`intake.wholePlans`)
- Create: `tooling/base/agent-factory/resources/` patch or key for the `careful` row's
  `split.parallel`: because this repository writes no `careful` row, the key is set by writing the
  whole row here, copied from Maku's shipped one with `parallel: 2` added, and the suite's case "no
  `careful` row of our own" becomes "our `careful` row equals Maku's shipped row but for `parallel`"
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`, `test-room-broker-config-parity.py`
- Modify: `docs/runbooks/agent-factory/17-splitter.md`
- Modify: `website/content/docs/use/guide/writing-a-good-task.md` (a big request becomes several
  issues, filed together), `website/content/docs/use/guide/following-and-steering.md` (the tree: a
  lane per part), `website/content/docs/how-it-works/factory.md` ("Scope and split"),
  `website/content/docs/use/guide/multi-repository.md` (one sentence: parts are within one
  repository; several repositories are a different feature), `website/content/docs/status.md`
- Modify: `scripts/ci/tests/test-site-workflow-claims.py`
- Modify: `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release H; phase D's report for the `split` and `implement` stages of accepted
  splits.
- Produces: whole plans filed on the reference host; `parallel: 2` only on the figure above.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| whole plans need the planner | `intake.wholePlans` is true only in a copy whose `intake.plan.enabled` is true |
| at most two | `split.parallel`, where set, is 1 or 2 |
| at most four parts | `split.maxChildren`, where set, is at most 4 |
| our row is Maku's but for one key | when `spec.loops.careful` exists, it differs from the shipped row (a table at the top of the script) in `split.parallel` only |
| the site says "in order" unless parallel is on | `writing-a-good-task.md` says parts run two at a time only if the rendered row has `parallel: 2` |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && python3 scripts/ci/tests/test-site-workflow-claims.py`
Expected: non-zero on the first.

- [ ] **Step 2: Bump every pin to Maku release H, by digest.**

- [ ] **Step 3: Set `intake.wholePlans: true`** in the broker's copies that run the planner.

- [ ] **Step 4: Rewrite runbook 17 and the four site pages.** Runbook 17 gains three drills: a
  plan of three issues filed at once with their "Waits for" lines; two disjoint parts open together
  (skipped while `parallel` is 1); a dependent part opened against its base (skipped if stacks were
  not built). The site pages describe one tree on three surfaces, with the thread's summary line as
  the labelled example.

- [ ] **Step 5: Run the suites and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website docs/runbooks
git commit -m "feat(agent-factory): a confirmed plan files every issue, in order (Maku release H)"
```

- [ ] **Step 6: Live check, then the parallel switch as its own commit**

Run runbook 17's first drill and record it. Read phase D's report: for accepted splits, the share
of the family's wall time during which no part was running. If that share is above a half, write
the `careful` row here with `parallel: 2`, change the suite's case as described under Files, run
`task check`, commit as `feat(agent-factory): two disjoint parts at a time`, and run the second
drill. If it is not, record the figure and leave the switch off. Re-walk the research's seventeen
scenarios and record how many still have no path: the spec's target is one.

---

## Phase I · A workflow as one definition, a role as a file

Maku release I. Switch: the presence of `spec.workflows.<name>.stages` and `spec.roles`.

**What waits for an earlier result:** the definitions written here are the spec's two YAML blocks,
adjusted to the stage options Maku task I1 kept; which keys of `factory.yaml` can be deleted
(`templates`, `tiers` references, the `loops` rows) is that task's answer and release I's upgrade
notes. The second, read-only reviewer of Task I2 is added only where phase D's report gives a reason
to: a class whose `review` stage shows `approve_overruled` on more than one task in five.

### Task I1: Adopt release I: `standard` and `careful` as two definitions

**Files:**
- Modify: every pin file listed in Global Constraints
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`spec.workflows` in the list form;
  the `loops` and `templates` blocks removed where release I's notes allow)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`,
  `scripts/ci/tests/test-site-workflow-claims.py`
- Modify: `website/content/docs/reference/harness.md`, `reference/factory-configuration.md`,
  `operate/tune-a-run.md` ("Write a workflow of your own", a how-to that copies one definition and
  edits it, with `maku workflow dry-run` as its second step), `how-it-works/factory.md`
- Modify: `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Maku release I: `stages`, `budget`, `maku workflow dry-run`.
- Produces: the two definitions, as the spec writes them:

```yaml
  workflows:
    standard:
      description: "An implementer and a reviewer. The default."
      budget: standard
      stepUp: careful
      stages:
        - {role: implementer, checks: true, stall: true}
        - {role: reviewer, maxRounds: 2}
    careful:
      description: "Planned first, judged before review. For wide or unclear tasks."
      budget: frontier
      stages:
        - {role: scoper, split: {maxParts: 4}, gate: {when: plan-first}}
        - {role: tester, when: repository.testFirst}
        - {role: implementer, checks: true, search: true, stall: true, judge: evidence}
        - {role: reviewer, maxRounds: 2}
```

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| a definition is whole | each workflow written here sets `description`, `budget` and `stages`, and none of `template`, `tier`, `loop` |
| one implementer, in order | each `stages` list holds exactly one `implementer`, `scoper` and `tester` before it, `reviewer` after |
| the reviewer stays | every workflow but `quick` holds a `reviewer` stage |
| the ladder holds | `standard.stepUp` is `careful`, and `careful`'s `budget` is not below `standard`'s |
| no orphan row | no `spec.loops` row is named after a workflow that sets `stages` |
| the change is a no-op | the script resolves the old form (kept as a fixture file `scripts/ci/tests/fixtures/workflows-before-release-i.yaml`, a copy of today's `spec.workflows` and `spec.loops`) and the new one to the same stages and budget for `standard` and `careful` |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero on the first.

- [ ] **Step 2: Bump every pin; save the fixture; rewrite `spec.workflows`.**

- [ ] **Step 3: Prove the no-op on real tasks**

Run, when the factory is up: `maku workflow dry-run standard --repository Smana/ai-native-ref --last 20`
Expected: every row's "RAN" equals its "WOULD RUN", and the estimate equals the cost. Record the
last line in the results file, section "Phase I". Without a cluster, the suite's last case is the
proof and this step waits.

- [ ] **Step 4: Rewrite the four site pages.** `reference/harness.md`'s workflow rows become one row
  per stage option (Option / Values / What it does); the how-to in `tune-a-run.md` stays under
  1,200 words and leads with the three commands a platform team runs: copy, edit, dry-run.

- [ ] **Step 5: Run the suites and the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && python3 scripts/ci/tests/test-site-workflow-claims.py && task docs && task check`
Expected: exit 0.

```bash
git add flux tooling infrastructure scripts website docs/runbooks
git commit -m "refactor(agent-factory): standard and careful as two readable definitions (Maku release I)"
```

### Task I2: One custom workflow, to prove the form: a tester and a second read-only reviewer

**Files:**
- Create: `tooling/base/agent-factory/resources/roles/security-reviewer.md` (the brief), listed in
  `tooling/base/agent-factory/resources/kustomization.yaml` through a `configMapGenerator` if
  release I's chart reads briefs from a ConfigMap, else through the mount its notes name
- Modify: `tooling/base/agent-factory/resources/factory.yaml` (`spec.roles`, one workflow
  `thorough`)
- Modify: `scripts/ci/tests/test-agent-factory-workflows.py`
- Modify: `website/content/docs/operate/tune-a-run.md` (the how-to's worked example),
  `website/content/docs/how-it-works/roles.md` (a custom role is a brief bound to a capability; it
  never gets a write token), `website/content/docs/status.md`
- Modify: `docs/runbooks/agent-factory/results-workflows-roles-redesign.md`

**Interfaces:**
- Consumes: Task I1; Maku release I's `Factory.spec.roles` and capability profiles (`read`,
  `tests`, `write`).
- Produces:

```yaml
  roles:
    security-reviewer:
      capability: read
      model: agent-default
      brief: roles/security-reviewer.md
  workflows:
    thorough:
      description: "Tests first, then two reviews: correctness and security."
      budget: frontier
      stages:
        - {role: tester, when: repository.testFirst}
        - {role: implementer, checks: true, stall: true}
        - {role: security-reviewer}
        - {role: reviewer, maxRounds: 2}
```

  No repository's default changes: `thorough` is reached by the label `workflow:thorough`.

- [ ] **Step 1: Write the failing cases**

| Case | Assertion |
|---|---|
| a custom role only reads | every `spec.roles` entry has `capability: read` |
| a brief is a file that exists | each `brief` path exists under `tooling/base/agent-factory/resources/` and is under 16 KiB |
| a brief holds no credential or host | no brief contains a token-shaped string, a cluster name or a private hostname |
| the built-in reviewer still gates | every workflow that holds a custom role after the implementer also holds the built-in `reviewer` |
| the custom workflow costs no more than the ceiling it names | `thorough`'s `budget` tier's `taskUSD` is at most `budgets.factoryDailyUSD` over `caps.activeTasks` |

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py`
Expected: non-zero (no `spec.roles`).

- [ ] **Step 2: Write the brief**: twenty lines at most. What to look for (secrets in the diff,
  widened RBAC, a network policy opened, an unpinned image or action), what not to report (style,
  scope), and that saying nothing is a complete answer.

- [ ] **Step 3: Add the role and the workflow; price it before it runs**

Run, when the factory is up: `maku workflow dry-run thorough --repository Smana/ai-native-ref --last 20`
Expected: a total and a count of estimates that used a class median. Record the line. This is the
spec's rule that a team forks a definition knowing what each stage costs.

- [ ] **Step 4: Rewrite the three site pages, run the gate, commit**

Run: `python3 scripts/ci/tests/test-agent-factory-workflows.py && task docs && task check`
Expected: exit 0.

```bash
git add tooling scripts website docs/runbooks
git commit -m "feat(agent-factory): a custom workflow with a tester and a second, read-only reviewer"
```

- [ ] **Step 5: Live check, recorded**: one issue labelled `workflow:thorough` on
  `Smana/ai-native-ref`. Expected: the rail shows tester (if the repository opted in), implementer,
  security-reviewer, reviewer; the security reviewer's run holds a read-only token (its
  `AgentRun`'s token audience is the reviewer's); the merge gate's status names the built-in
  reviewer's verdict only. This is the spec's last measure: a custom workflow with a tester and a
  second read-only reviewer, with no code change.

---

## Self-review

| Spec item | Task |
|---|---|
| Phase A: stall rule in every workflow, on this repository's own `default` row | A1 |
| Phase A: reachable split; `factory.yaml` matches what the site claims | A1 (shipped row applies), A2 (the site's values) |
| Phase A: tester by key | A1 (the pin and the case), A2 (the two pages) |
| Phase A: dead label | Maku only; A1's pin carries it |
| Phase A: the pages that say `standard` has a judge | A2: `how-it-works/factory.md`, `use/guide/writing-a-good-task.md`, `reference/harness.md` |
| Phase A: the page that says the planner picks the workflow | A2: `use/guide/writing-a-good-task.md` |
| Phase A: the pages that list keys a workflow does not have | A2: `reference/harness.md`, `reference/factory-configuration.md`, `operate/tune-a-run.md`, `reference/planner.md` |
| Phase A: the manifest's own stale comment | A1 |
| Phase A: the results file that says "collecting"; runbook 27's columns | A3 |
| Phase B: the card on five surfaces, the strip, the vocabulary | B1 (pin, descriptions, captures), B2 (the guide) |
| Phase C: the ladder, the switches, who pays, by hand | C1; C2 |
| Phase D: per-stage figures, the card's health, Track 3's dimension | D1; D2 |
| Phase E: the presets as stage switches; a class that requires stages; the roles' new shapes | E1; E2 |
| Phase F: the four outcomes, the plan gate, two-approval rulesets | F1; F2 |
| Phase G: acts, inbox, notifications | G1; G2 |
| Phase H: whole plans, parallel parts, the tree | H1 |
| Phase I: one definition, a role as a file, dry-run | I1; I2 |
| "How this is judged": the card on all five surfaces | B1's live step |
| "How this is judged": share of escalated tasks rescued | C1's live step, D1's recording rule |
| "How this is judged": a figure per role and class on thirty merged tasks | D1's live step |
| "How this is judged": scenarios with no path, from six to one | H1's last step |
| "How this is judged": a custom workflow with no code change | I2 |
| The standing rule: a Maku release, then a pin bump with the site pages and the manifests | the first task of every phase |
