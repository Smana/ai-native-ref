# Merge gate human path, PRs 4 and 5: adopt the release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the Maku release that carries the human path (its PRs 1–3), turn approve-to-merge
and the breaker's recovery on for both repositories, give the dashboards and alerts the new
series, write the drill label into runbook 12, point both fence files at aws-0, and document it.

**Architecture:** Six tasks in ai-native-ref, one pull request (PR 4), each commit leaving
`task check` green. Task 7 is a one-line cloud-native-ref pull request (PR 5), held to the eve of
the aws-0 session and merged by the owner with a bypass, since the fence file is a gate path.

- **Task 1** reads the release and changes nothing. If it lacks the two keys, the plan stops.
- **Task 2** moves every Maku pin and turns the two keys on in the same commit, since the strict
  decoder refuses them on an older Maku.
- **Task 3** gives the dashboards and alerts the new outcome, labels, histogram and gauge, and
  fixes the stale text of `AgentFactoryAutoMergeReverted`.
- **Task 4** writes the drill label into runbook 12 and the docs site, and links the design from
  the status page.
- **Task 5** points this repository's fence file at aws-0.
- **Task 6** verifies, pushes and opens PR 4.
- **Task 7** is PR 5 in cloud-native-ref.

**Tech Stack:** Python 3 with PyYAML (the suites, run by `scripts/ci/run-tests.sh` inside
`.composite/`), promtool (the alert tests), Hugo (the site), `oras`, `cosign`, `helm`, `docker
buildx imagetools` and `gh` to read the release, Flux 2.

**Spec:** [the human path design](../specs/2026-10-29-merge-gate-human-path-design.md):
"Configuration, labels and status fields", "The decision record and the human path" (the
metrics table), "Rollout and pull requests, in order" rows 4 and 5, AM6 (the drill label), AM9,
AM12. The names come from [the Maku plan](2026-10-29-merge-gate-human-path-maku-plan.md):

- the config keys `merge.approveToMerge` (bool) and `merge.breaker.recoverAfter` (int);
- the labels `factory/drill` and `factory/approved-merge`;
- the series `maku_factory_pr_outcomes_total{outcome="approved_merged"}`,
  `maku_factory_merge_decisions_total{repository,class,verdict,reason}`,
  `maku_factory_human_wait_seconds_total{phase,principal,reason,class}`,
  `maku_factory_handoff_to_merge_seconds` (histogram, `class,reason,how`),
  `maku_factory_class_paused{repository,class}`.

**Out of this PR:** the live proofs (the [session plan](2026-10-29-aws-0-merge-gate-session-plan.md)),
every Maku change, PR K.

## Global Constraints

- **Worktree:** `/home/smana/Sources/ai-native-ref-human-path-adopt`, branch
  `feat/merge-gate-human-path-adopt`, from a freshly fetched `origin/main`; `mise trust mise.toml`
  once. Rebase onto `origin/main` before every push.
- **`task check` is the evidence** (AGENTS.md): run it before each commit through
  `~/.cache/v3/check.sh <worktree>` (it logs to `~/.cache/v3/check-<dir>.log` and ends `exit=N`;
  it puts a `python3` with PyYAML first). Docker suites SKIP unless the daemon runs. Run
  `pre-commit run --all-files` before pushing: CI's `lint` runs detect-secrets, which `task check`
  does not.
- **Pin and keys in one commit** (the spec's "Configuration, labels and status fields"): "The
  strict decoder refuses the two keys on a Maku older than the release that carries them, so the
  pin and the config move in one commit".
- **Off outside the session?** No: `approveToMerge: true` and `recoverAfter: 3` stay on in
  the committed config. They change nothing while no factory runs, and the session proves them.
  The rollback is the key, not a revert of the pin.
- **The site links outside itself by absolute URL only**; the link check fetches each one.
- **Never vendor host scripts** (R49). The fence file is a gate path: PR 5 is human-authored.
- **Commits** conventional, in English, no trailers; PR descriptions in English.
- **Naming.** "Agent Factory" is the product; Maku is the controller.

---

### Task 1: Read the release

**Files:** none changed.

- [ ] **Step 1: Find the release and its contents**

```bash
V=$(gh release list -R Smana/maku --limit 5 --json tagName,isLatest --jq '.[] | select(.isLatest) | .tagName')
echo "$V"
gh api "repos/Smana/maku/contents/docs/factory.md?ref=$V" --jq .content | base64 -d | grep -c "approveToMerge\|recoverAfter\|factory/drill\|factory/approved-merge"
```

Expected: the tag of the release that merged the Maku plan's PR 3 (`v0.32.0` or later), and a
count of at least 4. A count under 4 means the release lacks the human path: stop, the Maku plan
is not done.

- [ ] **Step 2: Read the digests**

```bash
d(){ docker buildx imagetools inspect --raw "$1" | sha256sum | cut -d' ' -f1; }
for i in maku-factory maku-broker maku-slack; do echo "$i $(d ghcr.io/smana/$i:$V)"; done; echo "chart $(d ghcr.io/smana/charts/maku-factory:${V#v})"
```

Expected: four 64-hex digests. Keep them for Task 2.

### Task 2: The pin and the two keys

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml` (the chart tag and digest)
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml` (the factory image; `merge.approveToMerge`, `merge.breaker.recoverAfter` on both repositories)
- Modify: `infrastructure/base/room-broker/app.yaml`, `retention-cronjob.yaml`, `sqlinstance.yaml`, `crd-rooms.yaml` (the broker image, the ref, the CRD)
- Modify: `tooling/base/agent-factory/slack-app/deployment.yaml` (the Slack image)
- Modify: `observability/base/agent-platform/vmrule-agent-factory.yaml` (the "pinned here at" comment)
- Test: `scripts/ci/tests/test-agent-factory-pins.py` (every pin on one version), `test-agent-merge-gate-parity.py` (unchanged fences)

- [ ] **Step 1: Write the failing test**

Append to `scripts/ci/tests/test-agent-factory-pins.py`, beside its last check:

```python
def test_human_path_keys_on_both_repositories(values):
    """Human path AM1 and AM7: approve-to-merge and the breaker's recovery are on for every repository."""
    for repo in values["config"]["repositories"]:
        merge = repo["merge"]
        assert merge.get("approveToMerge") is True, repo["name"]
        assert merge["breaker"].get("recoverAfter") == 3, repo["name"]
```

`values` is the fixture the file already uses to load the helm values ConfigMap; if the file is
not pytest-style, add the check in its existing style (a function called from `main`).

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py` (or through `scripts/ci/run-tests.sh test-agent-factory-pins`)
Expected: FAIL on `approveToMerge`.

- [ ] **Step 3: Move the pins**

With `cur` the version currently pinned (`grep -o 'tag: "0\.[0-9]*\.[0-9]*"' flux/sources/ocirepo-agent-factory.yaml`)
and `new` the release's, apply the same edits `~/.cache/v3/maku-pin.sh` makes: the chart tag and
digest in `flux/sources/ocirepo-agent-factory.yaml`; `v$cur@sha256:<old>` to `v$new@sha256:<new>`
and `maku v$cur` to `maku v$new` in the helm values ConfigMap, `room-broker/app.yaml`,
`retention-cronjob.yaml` and `slack-app/deployment.yaml`; `ref: v$cur` in `sqlinstance.yaml`;
`pinned here at v$cur` in the VMRule; the room CRD from the release's `crd-rooms.yaml` asset with
the file's three-line header updated. `git diff --stat` shows those eight files.

- [ ] **Step 4: The keys**

In the helm values ConfigMap, in the host's `merge:` block after `awaitingCIFor: 24h`:

```yaml
            # Human path AM1: a maintainer's approval of the current head is the merge; the merger
            # merges it as a human merge, outside the caps. The hand-off comment names that one action.
            approveToMerge: true
            # R41: 1 revert in the last 10 merges demotes a class; human path AM7: 3 clean mature merges
            # after the bad one lift it (half-open), and a maintainer's factory/drill revert never counts (AM6).
            breaker: {window: 10, maxReverts: 1, maxFollowUps: 1, recoverAfter: 3}
```

replacing the existing `breaker:` line, and the same two lines in this repository's `merge:`
block. The comment on `autoMergesPerDay: 1` stays.

- [ ] **Step 5: Run the suites and the check**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-human-path-adopt`
Expected: `exit=0`; the pins suite passes; the parity suite passes (no fence changed).

- [ ] **Step 6: Commit**

```bash
git add flux infrastructure tooling observability scripts/ci/tests/test-agent-factory-pins.py
git commit -m "feat(agent-factory): maku $V, approve-to-merge and the breaker's recovery on"
```

### Task 3: Dashboards and alerts

**Files:**
- Modify: `observability/base/agent-platform/grafana-dashboard-agent-factory.yaml` (panels 3, 4; a "Human path" row)
- Modify: `observability/base/agent-platform/grafana-dashboard-agents-overview.yaml`, `grafana-dashboard-agent-identity.yaml` (the `auto_merged|human_merged` expressions)
- Modify: `observability/base/agent-platform/vmrule-agent-factory.yaml` (`AgentFactoryClassPausedLong`; the `AgentFactoryAutoMergeReverted` description)
- Create: `scripts/ci/tests/test-agent-class-paused-alert.sh`
- Test: `scripts/ci/tests/test-agent-dashboard-conventions.py`, `test-agent-dashboard-queries.sh`, `test-agent-alert-annotations.sh`

- [ ] **Step 1: Write the failing alert test**

`scripts/ci/tests/test-agent-class-paused-alert.sh`, modelled on
`test-agent-merge-regression-alert.sh` (copy its promtool harness: it extracts the VMRule's
groups into a promtool rules file and runs `promtool test rules`):

```yaml
# The promtool unit test the script writes
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="docs-links"}'
        values: '1x10100'   # 7 days and a minute
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="dead-links"}'
        values: '0x10100'
    alert_rule_test:
      - eval_time: 7d1m
        alertname: AgentFactoryClassPausedLong
        exp_alerts:
          - exp_labels: {severity: warning, repository: Smana/cloud-native-ref, class: docs-links}
            exp_annotations:
              summary: "docs-links on Smana/cloud-native-ref has been paused for 7 days"
              description: "The breaker holds the class. Three clean mature merges lift it (recoverAfter), or a maintainer's factory/drill on a drill revert. Read the window: scripts/shadow-merge-tally.sh --class docs-links --outcomes --since <date> in agent-platform."
              runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md#know-before-the-go"
              dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
      - eval_time: 6d
        alertname: AgentFactoryClassPausedLong
        exp_alerts: []
```

- [ ] **Step 2: Run it to see it fail**

Run: `bash scripts/ci/tests/test-agent-class-paused-alert.sh`
Expected: FAIL, the alert does not exist.

- [ ] **Step 3: The alert and the text fix**

In the VMRule, after `AgentFactoryMergeRegression`:

```yaml
        - alert: AgentFactoryClassPausedLong
          # Human path AM9: a class the breaker holds for a week is a class nobody is unpausing.
          expr: max by (repository, class) (maku_factory_class_paused) == 1
          for: 7d
          labels:
            severity: warning
          annotations:
            summary: "{{ $labels.class }} on {{ $labels.repository }} has been paused for 7 days"
            description: "The breaker holds the class. Three clean mature merges lift it (recoverAfter), or a maintainer's factory/drill on a drill revert. Read the window: scripts/shadow-merge-tally.sh --class {{ $labels.class }} --outcomes --since <date> in agent-platform."
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md#know-before-the-go"
            dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
```

and change `AgentFactoryAutoMergeReverted`'s description to: `"Its class is paused by the
breaker: 1 revert in its last 10 merges (R41), lifted by 3 clean mature merges (recoverAfter) or
when the revert was a maintainer's factory/drill. Read why on the task: kubectl get task -n
agent-system -o wide | grep Reverted"`.

- [ ] **Step 4: The dashboards**

In `grafana-dashboard-agent-factory.yaml`: panel 3's denominator and panel 4's outcomes list gain
`approved_merged`; add a row "Human path" with three panels, following the file's conventions
(`test-agent-dashboard-conventions.py` names them: ids, titles, descriptions, `increase_pure`):

| Panel | Type | Expression |
|---|---|---|
| Hand-off to merge, median by reason (7 d) | timeseries | `histogram_quantile(0.5, sum by (le, reason) (rate(maku_factory_handoff_to_merge_seconds_bucket[7d])))` |
| Waiting on a human, by reason | table | `sum by (reason, class) (increase_pure(maku_factory_human_wait_seconds_total[7d]))` |
| Classes paused | stat | `sum by (repository, class) (maku_factory_class_paused)` |

In the overview and identity dashboards, every `outcome=~"auto_merged\|human_merged"` becomes
`outcome=~"auto_merged|human_merged|approved_merged"`.

- [ ] **Step 5: Run the suites**

Run: `bash scripts/ci/tests/test-agent-class-paused-alert.sh && ~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-human-path-adopt`
Expected: the alert test passes; `exit=0` (the dashboard conventions and queries suites, the
alert annotations suite).

- [ ] **Step 6: Commit**

```bash
git add observability scripts/ci/tests/test-agent-class-paused-alert.sh
git commit -m "feat(observability): the human path row, the class_paused alert, approved merges counted"
```

### Task 4: Runbook 12, the docs site, the status page

**Files:**
- Modify: `docs/runbooks/agent-factory/12-live-auto-merge-drill.md` ("Know before the go", the revert step)
- Modify: `docs/runbooks/agent-factory/README.md` (row 12's prerequisites)
- Modify: `website/content/docs/platform/ai-platform/agents/how-it-works/factory.md` (the merge gate section)
- Modify: `website/content/docs/platform/ai-platform/status.md` (row 8)

- [ ] **Step 1: Runbook 12**

Replace the "Know before the go" bullet "The drill pauses `docs-links` afterwards" with:

```markdown
- **Label the drill before the revert.** `gh pr edit <n> --add-label factory/drill` on the merged
  pull request, then `factory/revert`: the merger copies `factory/drill` to its revert PR, the
  breaker does not count it (human path AM6), and the class keeps its shadow and live clocks. A
  revert without the label pauses the class until 3 clean mature merges land (`recoverAfter`, AM7).
  The label is honoured only from a maintainer, as `factory/revert` is.
- **Retroactively:** the drill of 2026-10-18 reverted #2520 through #2521 without the label. Before
  the next session, `gh pr edit 2521 -R Smana/cloud-native-ref --add-label factory/drill`: the next
  ledger read no longer counts it, and `docs-links` resumes.
```

In the drill's step 5 (G3), add the label command before the `factory/revert` one. In the
README's row 12, add "`factory/drill` on the drilled PR" to the prerequisites.

- [ ] **Step 2: The docs site**

In `agents/factory.md`'s merge gate section, after the paragraph on the human's merge, add:

```markdown
**One approval merges.** With `merge.approveToMerge`, a maintainer's approval of the current head
is the merge: the merger merges that head, as a human merge, outside the daily caps, and the
pull request carries `factory/merged:<class>` and `factory/approved-merge`. The hand-off comment
names that one action. The eight hand-offs a human fixes by hand (a gate path, a foreign trailer,
a steering note, a refused merge) keep the bypass instructions. Shadow decisions ignore the
breaker and the caps, a maintainer's `factory/drill` revert never trips the breaker, and a tripped
class resumes after three clean mature merges
([design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-29-merge-gate-human-path-design.md)).
```

- [ ] **Step 3: The status page**

Row 8's text gains, after "stay the one live class", the sentence below (the design's URL on
`main` is valid once the design's PR, #233, has merged, which precedes this plan):

```markdown
, and one maintainer approval merges any other agent pull request ([the human path](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-29-merge-gate-human-path-design.md), proof pending on aws-0)
```

- [ ] **Step 4: Run the check**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-human-path-adopt`
Expected: `exit=0` (the site builds, the link check fetches the GitHub URL, the doc-path check
resolves the runbook's paths).

- [ ] **Step 5: Commit**

```bash
git add docs website
git commit -m "docs(agent-factory): the drill label in runbook 12; approve-to-merge on the site"
```

### Task 5: This repository's fence to aws-0

**Files:**
- Modify: `.github/agent-factory.yaml`

- [ ] **Step 1: Flip the fence**

```yaml
# Names the agent factory that may act on this repository (agent-platform ownership fence): only aws-0 takes its issues, runs and merges.
factory: aws-0
```

- [ ] **Step 2: Run the check and commit**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-human-path-adopt`
Expected: `exit=0`.

```bash
git add .github/agent-factory.yaml
git commit -m "chore(agent-factory): the fence names aws-0 for the next live session"
```

### Task 6: Verify, push, PR 4

- [ ] **Step 1: pre-commit and rebase**

```bash
pre-commit run --all-files
git fetch origin && git rebase origin/main
```

Expected: pre-commit passes; the rebase is clean.

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin feat/merge-gate-human-path-adopt
gh pr create --title "feat(agent-factory): maku $V, approve-to-merge, the breaker's recovery, the human-path panels" --body-file - <<'EOF'
Adopts the Maku release that carries the merge gate's human path (design: docs/superpowers/specs/2026-10-29-merge-gate-human-path-design.md).

- Pins maku $V (chart, factory, broker, Slack App, room CRD, SQL ref).
- `merge.approveToMerge: true` and `breaker.recoverAfter: 3` on both repositories.
- The agent-factory dashboard's "Human path" row, `approved_merged` counted, `AgentFactoryClassPausedLong`, the stale text of `AgentFactoryAutoMergeReverted` fixed.
- Runbook 12: `factory/drill` before a drill revert, and the retroactive label on cloud-native-ref#2521.
- The fence names aws-0 for the next live session.

Evidence: `task check` exit 0 (log attached), pre-commit clean.
EOF
```

The fence file is a gate path: policy-bot reads `error` on this PR, and the owner merges it with a
bypass, as every human-authored gate-path change.

### Task 7: PR 5, cloud-native-ref: the fence to aws-0 (held)

**Files:**
- Modify: `cnref/.github/agent-factory.yaml`

- [ ] **Step 1: Branch, flip, test**

```bash
git -C ~/Sources/cloud-native-ref fetch origin && git -C ~/Sources/cloud-native-ref worktree add ~/Sources/cloud-native-ref-fence-aws-0 -b chore/fence-aws-0 origin/main
cd ~/Sources/cloud-native-ref-fence-aws-0
sed -i 's/factory: gcp-0/factory: aws-0/; s/only gcp-0 takes/only aws-0 takes/' .github/agent-factory.yaml
scripts/ci/tests/run.sh
```

Expected: the suites pass (the fence file's shape is unchanged).

- [ ] **Step 2: Commit and push, do not merge**

```bash
git add .github/agent-factory.yaml
git commit -m "chore(agent-factory): the fence names aws-0 for the next live session"
git push -u origin chore/fence-aws-0
gh pr create --title "chore(agent-factory): the fence names aws-0 for the next live session" --body "Human path AM12: the next merge-gate session runs on aws-0. A gate path: merged by the owner with a bypass on the session's eve, after the aws-0 OpenBao secrets are in place (session plan, step 0)."
```

The owner merges it on the session's eve (session plan, step 0.5). Until then the host's fence
still names gcp-0, so a gcp-0 factory brought up by another session keeps acting on it.

## Self-review

- **Spec coverage.** Row 4 of "Rollout and pull requests": the pin and both keys (Task 2), the
  dashboards and alert (Task 3), runbook 12's drill step (Task 4), the docs (Task 4), this
  repository's fence (Task 5). Row 5: Task 7. AM9's five series: the three panels and the alert
  read four of them; `merge_decisions_total{repository}` feeds the existing decisions table, whose
  expression needs no change. The study's drift item on `AgentFactoryAutoMergeReverted`: Task 3.
- **Placeholders.** `$V` is read in Task 1 and used verbatim after; the pins suite's fixture name
  is whatever the file already uses, named in Task 2 Step 1.
- **Consistency.** The keys, labels and series are the Maku plan's names, listed under **Spec**.
