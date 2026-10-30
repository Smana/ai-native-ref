# Harness roles, PR 3: adopt the release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the Maku release that carries the harness roles' PRs 1–2, give `scripts` a judge,
write the sandbox steering notes, make the docs and the status page say what is built and proven,
and give the dashboard the cost-by-role panel.

**Architecture:** Six tasks in ai-native-ref, one pull request, each commit leaving `task check`
green. Task 1 reads the release and changes nothing. Task 2 moves the pins and adds the `scripts`
judge row in one commit. Task 3 writes the steering notes. Task 4 is the docs-truth bundle. Task 5
the dashboard panel. Task 6 verifies, pushes and opens the PR.

**Tech Stack:** Python 3 with PyYAML (the suites), Hugo (the site), `oras`, `cosign`, `helm`,
`docker buildx imagetools` and `gh` to read the release, Flux 2.

**Spec:** [the harness roles design](../specs/2026-10-30-harness-roles-design.md): HR6–HR9,
"The judge round" (the `scripts` row), "Configuration, metrics and names", "Testing". The names
come from [the Maku plan](2026-10-30-harness-roles-maku-plan.md): the config key `scoper`
(defaults 25/40, nothing to set), the series `maku_factory_run_cost_usd{tier,role}`, the scoper
outcome `budget_calls`.

**Out of this PR:** the Coding Clients page ([its plan](2026-10-30-coding-clients-review-plan.md)),
the clip ([its plan](2026-10-30-motion-v3-fixes-plan.md)), the session proofs
([their plan](2026-10-30-aws-0-roles-proofs-plan.md)), every Maku change, the owner's local setups.

## Global Constraints

- **Worktree:** `/home/smana/Sources/ai-native-ref-harness-roles-adopt`, branch
  `feat/harness-roles-adopt`, from a freshly fetched `origin/main`; `mise trust mise.toml` once.
- **`task check` is the evidence**, through `~/.cache/v3/check.sh <worktree>`; `pre-commit run
  --all-files` before pushing.
- **Pin and config in one commit**: the `scripts` judge row needs no new key (the loop keys
  exist), but the harness image digest the composition pins must be the release's, or the scoper
  marker is written and never read. The harness image pin lives in crossplane-configuration's
  composition (`apis/agentrun/kcl/main.k`), not here: read the Maku release notes for the digest
  and, if the composition has not been bumped, file that as the first follow-up and say so in the
  PR (the factory-side changes still work without it; HR2 and HR5 wait for the composition pin).
- **The site links outside itself by absolute URL only.**
- **Commits** conventional, in English, no trailers; PR descriptions in English.
- **Naming.** "Agent Factory" is the product; Maku is the controller.

---

### Task 1: Read the release

- [ ] **Step 1: The tag and the keys**

```bash
V=$(gh release list -R Smana/maku --limit 5 --json tagName,isLatest --jq '.[] | select(.isLatest) | .tagName')
gh api "repos/Smana/maku/contents/docs/factory.md?ref=$V" --jq .content | base64 -d | grep -c "budget_calls\|nudgeAt\|judge the diff, not the story"
```

Expected: at least 3. Fewer means the release lacks the roles' PRs: stop.

- [ ] **Step 2: The digests, the harness image**

As the merge-gate adopt plan's Task 1 Step 2 (factory, broker, Slack, chart), plus the harness
image: `d ghcr.io/smana/maku-harness:$V`. Compare with the digest in
`https://github.com/Smana/crossplane-configuration/blob/main/apis/agentrun/kcl/main.k`: if they
differ, the composition pin is the follow-up named in the constraints.

### Task 2: The pin and the `scripts` judge row

**Files:**
- Modify: the eight pin files of the merge-gate adopt plan's Task 2 Step 3
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml` (the `loops.scripts` row)
- Test: `scripts/ci/tests/test-agent-factory-pins.py`; a loop-row check added to it

- [ ] **Step 1: Write the failing test**

Append to `scripts/ci/tests/test-agent-factory-pins.py`:

```python
def test_every_loop_row_with_a_scope_names_a_judge(values):
    """Harness roles HR7: a class whose parts or tests run through the loop gets a judge; a row with a
    scope or a split and no judge leaves split parts and test-first tasks unjudged."""
    loops = values["config"]["loops"]
    for name, row in loops.items():
        if name == "default":
            continue
        if row.get("scope") == "scoper" or "split" in row:
            assert row.get("judge"), f"loops.{name} has a scoper or a split but no judge"
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-agent-factory-pins.py`
Expected: FAIL on `loops.scripts`.

- [ ] **Step 3: The pins and the row**

Move the pins as the merge-gate adopt plan's Task 2 Step 3 does. Then the `scripts` row:

```yaml
        # scripts: … (the existing comment) … Harness roles HR7: judge tier-light switches the loop on for
        # scripts too (stallSteps 80, continuations 2 by default), so split parts and test-first tasks are
        # judged; the judge reads the head's GitHub check runs, so checks: false on the class is fine.
        scripts: {scope: scoper, split: {maxChildren: 4, familyUSD: 20.40, childTier: standard, anyTier: true}, judge: tier-light}
```

- [ ] **Step 4: Run the check, commit**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-harness-roles-adopt`
Expected: `exit=0`.

```bash
git add flux infrastructure tooling observability scripts/ci/tests/test-agent-factory-pins.py
git commit -m "feat(agent-factory): maku $V; a judge on the scripts loop row"
```

### Task 3: The steering notes (HR8)

**Files:**
- Modify: `.github/agent-factory/steering/docs.md`
- Create: `.github/agent-factory/steering/scripts.md`

- [ ] **Step 1: The notes**

Append to `docs.md`, and write `scripts.md` with the same section plus the `scripts` `## Verify`
and `## Leave alone` lines (`task test` and `scripts/ci/tests/run.sh` as the verify commands;
`scripts/ci/flux-schema/` and `taskfile.yaml` as leave-alone):

```markdown
## In the sandbox
- `agent-checks` is the evidence here: it runs the CI's fast subset from `.github/agent-checks.yaml`.
  `task check` runs in CI, not in the sandbox: it needs `helm`, Docker and hosts the sandbox cannot reach.
- Never install a tool the sandbox lacks (`helm`, Docker): the checks that need them are CI-only, listed
  under `ciOnly` in `.github/agent-checks.yaml`.
```

The steering notes' format is what `steering.Dir`'s reader accepts (`## Verify`, `## Leave alone`,
`## Write`, free sections): `task check`'s steering suite, if one exists, or the doc-path check,
proves the files.

- [ ] **Step 2: Run, commit**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-harness-roles-adopt`
Expected: `exit=0`.

```bash
git add .github/agent-factory/steering
git commit -m "docs(agent-factory): steering notes: agent-checks is the sandbox's evidence"
```

### Task 4: The docs-truth bundle (HR9)

**Files:**
- Modify: `website/content/docs/platform/ai-platform/status.md` (rows 4 and 5)
- Modify: `website/content/docs/platform/ai-platform/agents/harness-reference.md` (the harness image row, the model-timeout row, the reviewer caps sentence, the tester's "read only")
- Modify: `website/content/docs/platform/ai-platform/agents/roles.md` (the reviewer row, the mermaid order, the lastVerified)
- Modify: `docs/runbooks/agent-factory/README.md` (the search layer's status)

- [ ] **Step 1: The edits**

| File | From | To |
|---|---|---|
| `status.md` row 4 | "the implementer works to it and cannot change it. The `not_testable` case is proven too" | "the implementer works to it; that it cannot change it (the holds) is built and not yet read live. The `not_testable` case is proven" |
| `status.md` row 5 | "Proven live: … 3 calls in the drill" | badge `built`; "Used live in one drill (3 calls); its value is unmeasured until the paired search on/off proof" |
| `harness-reference.md` harness image row | `agent-harness:v0.15.2@sha256:c49c…` | the digest Task 1 read from the composition, named `maku-harness` |
| `harness-reference.md` model timeout row | "A timeout is not retried: it ends the run" | "A timed-out call is retried once (maku #224); a second timeout ends the run" |
| `harness-reference.md` the reviewer caps sentence (line ~83) | as written | "The reviewer runs on the other tier: that tier's USD cap applies; its tokens and minutes stay the implementer's tier's" |
| `harness-reference.md` role row (line ~138) | "`reviewer`, `tester`, `triager` read only" | "`reviewer` and `triager` read only; the tester writes tests the harness signs and pushes" |
| `roles.md` reviewer row | "Advice only" | "Its verdict is a gate input: the merge gate refuses a head without an approving verdict (`no_approving_verdict`)" |
| `roles.md` mermaid | `reviewer --> pr["Pull request"]` | `impl --> pr["Pull request"]` and `pr --> reviewer`: the reviewer's task is the pull request |
| `roles.md`, `harness-reference.md` front matter | `lastVerified` | the commit's date |
| runbooks README, layer 4 | "Live" for search | "Used live once; SQ5a open" |

- [ ] **Step 2: Run, commit**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-harness-roles-adopt`
Expected: `exit=0` (the site builds; the doc-path check resolves the runbook).

```bash
git add website docs/runbooks
git commit -m "docs(agent-factory): the status page and the harness reference say what is built and proven"
```

### Task 5: Cost by role on the dashboard

**Files:**
- Modify: `observability/base/agent-platform/grafana-dashboard-agent-factory.yaml`
- Test: `scripts/ci/tests/test-agent-dashboard-conventions.py`, `test-agent-dashboard-queries.sh`

- [ ] **Step 1: The panel**

A panel with the next free id (19), type `timeseries`, title "Cost by role (7 d)", description
"USD per role over the window, from `maku_factory_run_cost_usd` (harness roles HR6): the first
per-role number the factory reports", expression
`sum by (role) (increase_pure(maku_factory_run_cost_usd_sum[7d]))`, following the file's unit and
colour conventions (the conventions suite names them).

- [ ] **Step 2: Run, commit**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-harness-roles-adopt`
Expected: `exit=0`.

```bash
git add observability
git commit -m "feat(observability): cost by role on the agent-factory dashboard"
```

### Task 6: Verify, push, PR 3

- [ ] **Step 1: pre-commit, rebase, push, PR**

```bash
pre-commit run --all-files && git fetch origin && git rebase origin/main && git push -u origin feat/harness-roles-adopt
gh pr create --title "feat(agent-factory): maku $V, a judge on scripts, sandbox steering, the docs' truth" --body-file - <<'EOF'
Adopts the Maku release that carries the harness roles' changes (design: docs/superpowers/specs/2026-10-30-harness-roles-design.md).

- Pins maku $V (chart, factory, broker, Slack App, room CRD, SQL ref). The harness image pin lives in crossplane-configuration: <bumped | follow-up filed>.
- `loops.scripts` gains `judge: tier-light` (HR7).
- Steering notes: `agent-checks` is the sandbox's evidence (HR8).
- The status page's rows 4 and 5, the harness reference and the roles page say what is built and proven (HR9).
- Cost by role on the agent-factory dashboard (HR6).

Evidence: `task check` exit 0, pre-commit clean.
EOF
```

## Self-review

- **Spec coverage.** HR6 (Task 5), HR7 (Task 2), HR8 (Task 3), HR9 (Task 4); the pin (Tasks 1–2).
- **Placeholders.** `$V` and the harness digest are read in Task 1; the composition bump is a
  named follow-up, not a hidden step.
