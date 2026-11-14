# Caching, performance and costs: ai-native-ref Adoption Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt Maku's measurement and its free gains on this platform, keep a gVisor node warm on aws-0 during working hours, and run the effort and model trials on aws-0, each with a before and after reading on record.

**Architecture:** Base carries the Maku pin and every value both clusters share. The aws-0 overlay carries what is proven there only: the warm node's schedule and each trial's second workflow definition. Each gain is one pull request with one results section: a reading before, a reading after, and the rollback.

**Tech Stack:** Flux Kustomizations and HelmReleases, kustomize overlays, KEDA (`ScaledObject`, cron trigger), Karpenter, the suites under `scripts/ci/tests/`, Hugo site pages.

**Spec:** [`docs/superpowers/specs/2026-11-14-cache-costs-review-design.md`](../specs/2026-11-14-cache-costs-review-design.md). The Maku half is [`2026-11-14-cache-costs-maku-plan.md`](2026-11-14-cache-costs-maku-plan.md).

## Global Constraints

- Work in a git worktree branched from `origin/main`; rebase onto a freshly fetched `origin/main` before every push (`AGENTS.md`).
- `task check` is the evidence for every task. Paste its tail in the pull request. Never claim done without it.
- Validation is on **aws-0 only**. gcp-0 keeps today's values (`replicas: 0`, no trial) until it is the cluster under test.
- Every child names `sourceRef: {kind: OCIRepository, name: ai-native-ref}` and depends only on the host Kustomizations in `HOST-CONTRACT.md` H2.
- Workloads follow the host's platform constitution: default-deny CiliumNetworkPolicy, requests and limits, restricted security context, least-privilege RBAC.
- Site pages follow `docs/docs-style.md`; versions and cluster state live on `status.md` only.
- No Maku field, reason code or metric table is restated on the site: link to Maku.
- Readings go in one file per live session, `docs/runbooks/agent-factory/results-aws-0-<YYYY-MM-DD>.md`, as the existing results files do.
- Commits are conventional, in English, with no trailers.

## Prerequisites

Read before Task 1. A task whose prerequisite is unmet waits; the others proceed.

| Prerequisite | Needed by | State on `main` at `47b6557` | Where it is tracked |
|---|---|---|---|
| Maku release N (lots 1 and 2) is cut | Tasks 1 to 4 | not cut | the Maku plan |
| Runs go through Maku's run-controller on aws-0 | Task 4 (the light alias), Task 3's image list | off: `infrastructure/base/room-broker/helmrelease.yaml` says "Runs stay on the AgentRun XR until R3" | Maku `docs/v4-readiness.md` row 13 |
| The chart's dashboards replace this repository's copies | Task 2's three panels | this repository still ships `observability/base/agent-platform/grafana-dashboard-*.yaml` | readiness row 18 |
| Maku release N+1, and the workflows measurement's verdict for the role | Task 5 | — | the workflows plans |

## Review Focus

1. **Flux reverting the schedule.** A reconcile must not set `agents-headroom` back to a fixed replica count. Pinned in Task 3 (`test-agents-headroom-schedule.py`: the aws-0 render has no `spec.replicas`).
2. **A warm node holding stale images.** The pod must pre-pull the images runs actually use, or the node is warm and the pull is still cold. Pinned in Task 3 (the suite compares the images with the run images' pins).
3. **gcp-0 warming by accident.** A base edit that turns the node on in both clusters costs about $126 a month on the other one. Pinned in Task 3 (the gcp-0 render keeps `replicas: 0` and no `ScaledObject`).
4. **A reading taken on the wrong cluster or the wrong release.** Every results section names the cluster, the Maku version and the time window. Pinned in Task 2 (the results template, checked by `task docs`' path check and by review).
5. **A trial left on.** A second workflow definition and a cohort share that outlive their trial keep half the traffic on an unshipped setting. Pinned in Task 5 (`test-agent-trial-off.py`: base carries no trial definition).

---

### Task 1: pin Maku release N in base

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml` (tag and digest), `tooling/base/agent-factory/helm-values-configmap.yaml` (:19, `image.tag`), the CRDs chart's source beside it, `infrastructure/base/room-broker/helmrelease.yaml` (the broker's chart pin)
- Modify: `website/content/docs/status.md` (the version, the one place it is stated)
- Test: `scripts/ci/tests/test-agent-factory-pins.py`, `scripts/ci/tests/test-room-broker-chart.py`, `task factory-config`

- [ ] **Step 1: Bump the four pins to release N, each by digest**

- [ ] **Step 2: Run the gates**

Run: `task check`
Expected: exit 0; `test-agent-factory-pins` prints no problem. If `task test` fails only on suites that need GNU sed, GNU grep or a Docker bind mount of `/var/folders` (a macOS workstation), run `task links docs sources` by hand and name those suites in the pull request.

- [ ] **Step 3: Commit**

```bash
git commit -am "chore(deps): Maku <release N>: boot and clone spans, cache lines, the light alias"
```

### Task 2: lot 1 live on aws-0, and the baseline

**Files:**
- Create: `docs/runbooks/agent-factory/results-aws-0-<date>.md`
- Modify: `docs/runbooks/agent-factory/README.md` (one row in its results list)
- Modify: `website/content/docs/operate/observability.md` (where to read the start row and cost per merged pull request; links to Maku for the definitions)
- Test: `task links docs`

**Interfaces:**
- Produces: the baseline table below. Tasks 3 and 4 append their "after" column to the same file or to the next session's file, naming this one.

- [ ] **Step 1: With aws-0 active on release N, run three tasks** (one `docs`, one `scripts`, one internal investigation) through the normal path.

- [ ] **Step 2: Record the baseline**

```markdown
## Baseline, lot 1

Cluster aws-0 · Maku <release N> · window <start> to <end> UTC · <n> runs

| Reading | Value | Read from |
|---|---|---|
| Pod created → Ready, p50 / p90 | | the run dashboard's start row |
| `agent-run.boot`, p50 | | traces |
| `agent-run.clone`, p50 / p90, `filter=none` | | traces |
| Condensations per internal run | | `agent-run condensation:` lines |
| `miss=unexpected` lines | (must be 0) | `agent-run cache:` lines |
| Search spend per run with search on | | the search ledger line, priced |
| Waits between runs over 5 min, by role | | `agent_factory_run_wait_seconds` |
| Cost per merged pull request, by workflow | | the factory dashboard (after readiness row 18) |
```

Any `miss=unexpected` is a defect: open a Maku issue with the run's log before going further.

- [ ] **Step 3: Run the gates and commit**

Run: `task links docs`
Expected: exit 0.

```bash
git commit -am "docs(runbooks): the lot 1 baseline on aws-0"
```

### Task 3: the warm node on aws-0, weekdays 08:00 to 19:00 Europe/Paris (CP4)

**Files:**
- Create: `infrastructure/aws-0/agents-headroom/kustomization.yaml`, `infrastructure/aws-0/agents-headroom/scaledobject.yaml`
- Modify: `clusters/aws-0-agent-platform/infrastructure-agents-headroom.yaml` (`path`, `dependsOn`)
- Modify: `infrastructure/base/karpenter-nodepools-agents/headroom/deployment.yaml` (the three images and the comment above them)
- Create: `scripts/ci/tests/test-agents-headroom-schedule.py`
- Modify: `website/content/docs/operate/tune-a-run.md` (:223, the cold-start row), `clusters/aws-0-agent-platform/README.md`
- Test: `scripts/ci/tests/test-agents-headroom-schedule.py`, `task validate`

**Interfaces:**
- Produces: on aws-0, `ScaledObject/agents-headroom` in `agent-system` owning the Deployment's replicas; on gcp-0 nothing changes.

- [ ] **Step 1: Write the failing suite** `test-agents-headroom-schedule.py`

It renders both paths with `kustomize build` and asserts:

```python
aws = render("infrastructure/aws-0/agents-headroom")
gcp = render("infrastructure/base/karpenter-nodepools-agents/headroom")

so = one(aws, "ScaledObject", "agents-headroom")
assert so["spec"]["scaleTargetRef"] == {"name": "agents-headroom"}
assert (so["spec"]["minReplicaCount"], so["spec"]["maxReplicaCount"]) == (0, 1)
assert so["spec"]["triggers"] == [{"type": "cron", "metadata": {
    "timezone": "Europe/Paris", "start": "0 8 * * 1-5", "end": "0 19 * * 1-5", "desiredReplicas": "1"}}]
assert "replicas" not in one(aws, "Deployment", "agents-headroom")["spec"]      # Flux must not own it

assert one(gcp, "Deployment", "agents-headroom")["spec"]["replicas"] == 0
assert not any(o["kind"] == "ScaledObject" for o in gcp)

# The warm pod pre-pulls what a run pulls: same repository and digest as the run images' pins.
assert headroom_images(aws) == run_images()
```

`run_images()` reads the harness and bridge pins from the values that configure the run path: the run-controller's `images.harness` and `images.bridge` once readiness row 13 is done, the Crossplane composition's pin until then. Write it against whichever `main` carries when this task runs, and name the source in the suite's docstring.

- [ ] **Step 2: Run it and see it fail**

Run: `python3 scripts/ci/tests/test-agents-headroom-schedule.py`
Expected: FAIL, `infrastructure/aws-0/agents-headroom` does not exist.

- [ ] **Step 3: Write the overlay**

`kustomization.yaml` takes the base headroom directory as its resource, adds `scaledobject.yaml`, and removes `/spec/replicas` from the Deployment with a JSON 6902 patch. The Flux child for aws-0 points at the overlay and adds `dependsOn: [{name: infrastructure}]` (KEDA, `HOST-CONTRACT.md` H2). In the base Deployment, bring the three images to the pins `run_images()` reads, and replace the comment's cost and cluster with a link to the spec.

- [ ] **Step 4: Run the gates**

Run: `task check`
Expected: exit 0, the new suite included.

- [ ] **Step 5: Verify live on aws-0, over one working week**

| Check | Command or panel | Passes when |
|---|---|---|
| The schedule holds | `kubectl -n agent-system get scaledobject agents-headroom -o json \| jq '.status.conditions'` | `Ready` is `True`; replicas are 1 inside the window and 0 outside |
| Flux leaves it alone | `flux get kustomization agents-headroom` after two reconciles | `Ready`, replicas unchanged |
| The start | pod created → Ready over the week, working hours only | p90 near 17 s, against the baseline's p90 |
| The cost | the node's hours in the week | about 55 node-hours, about $38 a month |

Record the four in the results file, beside the baseline.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(aws-0): a warm gVisor node on weekdays, 08:00 to 19:00 Europe/Paris"
```

**Rollback:** point the aws-0 child back at `./infrastructure/base/karpenter-nodepools-agents/headroom` (replicas 0). The node consolidates after 5 minutes.

### Task 4: lot 2 live on aws-0, gain by gain

**Files:**
- Modify: the run-controller's values in base (`model.gateway.lightAlias` is left at its default; the internal and public alias lists must include `tier-light`)
- Modify: `scripts/ci/tests/test-model-gateway-values.py` (one assertion)
- Modify: the results file; `website/content/docs/how-it-works/routing-and-cost.md` (the measured effect, one short section, linking to Maku for the mechanism)
- Test: `scripts/ci/tests/test-model-gateway-values.py`, `task check`

- [ ] **Step 1: Write the failing assertion**

In `test-model-gateway-values.py`: each listener's alias list that the run-controller's values name contains `tier-light`; the failure message names the listener. Maku refuses the config at load otherwise, so this fails in CI rather than on the cluster.

- [ ] **Step 2: Run it** (FAIL if a list lacks the alias), **fix the values, run `task check`** (exit 0).

- [ ] **Step 3: Verify each gain live and record it**

| Gain | Reading after | Passes when | Rollback |
|---|---|---|---|
| CP5 blobless clone | `agent-run.clone` p50 and p90, `filter=blob:none` | every run's span says `blob:none`; p50 is not higher than the baseline; the declared checks still pass | pin the previous Maku release |
| CP12 the light alias | the run pod's env and the gateway's access log | an internal run and a search-on run carry `LIGHT_*`; a search and a condensation are answered by `tier-light`; a public run without search carries none | same |
| CP6 the condenser | `condensation` lines per internal run; `AgentCacheReadShareLow` | fewer condensations than the baseline at the same step count; the alert stays quiet for the week | same |
| CP7 search on the light alias | search spend per run; the implementer's own lookups after a search | spend near 0.11× (public) or 0.125× (internal) of the baseline; lookups after a search do not rise | same |

A gain that fails its "passes when" is recorded as failed, with the reading, and a Maku issue is opened. It is not tuned on the cluster.

- [ ] **Step 4: Commit**

```bash
git commit -am "docs: the lot 2 readings on aws-0"
```

### Task 5: a trial on aws-0 (lot 3)

One pass of this task per trial, in the spec's order: scoper at effort `medium`, reviewer at `medium`, reviewer on `tier-standard` for internal tasks, triager at `medium`, triager on `tier-standard` or `tier-light`. One trial at a time for a given workflow. The cohort keys, the 30 tasks an arm, the threshold and the indecisive rule are the workflows spec's: read `2026-11-14-workflows-review-design.md` before starting, and do not restate them here.

**Files:**
- Create or modify: a patch under `tooling/aws-0/agent-factory/` adding the trial's second workflow definition and the cohort share to the `Factory` (aws-0 only)
- Create: `scripts/ci/tests/test-agent-trial-off.py`
- Modify: the session's results file
- Test: `scripts/ci/tests/test-agent-trial-off.py`, `task factory-config`

- [ ] **Step 1: Write the suite** `test-agent-trial-off.py`

```python
base = render("tooling/base/agent-factory")
aws = render("tooling/aws-0/agent-factory")
# Base never carries a trial: no workflow whose name ends in "-trial", no evaluation.treatment.
assert not trial_workflows(base) and not treatment(base)
# At most one trial per workflow on aws-0, and it differs from the shipped definition in exactly one field.
for name, trial in trial_workflows(aws).items():
    assert len(diff_fields(shipped(aws, name), trial)) == 1
```

- [ ] **Step 2: Add the trial's patch**

The second definition is the shipped workflow's name with `-trial`, differing in the one field under trial, for example:

```yaml
workflows:
  standard-trial:
    effort: {reviewer: medium}
```

Run: `task check`
Expected: exit 0; `task factory-config` accepts the object through the pinned Maku.

- [ ] **Step 3: Run the trial on live traffic**

Tasks merge normally. Read the two arms on the factory dashboard by the `cohort` label. Trials 4 and 5 read cost per investigation and the share of proposed issues a maintainer accepts.

- [ ] **Step 4: Record the verdict**

```markdown
## Trial <n>: <role> at <setting>

Cluster aws-0 · Maku <version> · <start> to <end> · control n=<n>, treatment n=<n>

| | Control | Treatment |
|---|---|---|
| Cost per merged pull request | | |
| Merge rate | | |

Verdict: ships / does not ship / indecisive (the default does not change).
```

- [ ] **Step 5: Remove the patch in the same pull request that records the verdict**

Run: `task check`
Expected: exit 0; aws-0 carries no `-trial` workflow.

```bash
git commit -am "docs(runbooks): trial <n>, <role> at <setting>: <verdict>"
```

A verdict of "ships" becomes a Maku change (the Maku plan's Task 13) and reaches this platform with the next pin, in base.

---

## Self-review

| Spec item (the ANR column of "Who changes what") | Task |
|---|---|
| Lot 1: pin the release in base; the aws-0 live check | 1, 2 |
| Lot 2: the headroom schedule in the aws-0 overlay; its image list from the run path's values | 3 |
| Lot 2: each gain verified by a before and after reading | 4 |
| Lot 3: the trial's second workflow definition and the cohort share on aws-0; a ledger entry per trial | 5 |
| gcp-0 unchanged | 3 (suite), 5 (suite) |
