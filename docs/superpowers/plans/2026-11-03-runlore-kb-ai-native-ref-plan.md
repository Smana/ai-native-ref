# RunLore's knowledge base from the factory, ai-native-ref PRs 4 and 7, runlore-kb PR 6 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire phase 1 into the platform on aws-0, where the fence says the factory acts: RunLore
as a standing internal principal and broker subscriber, `publishStarts` and `alert-rules` in shadow,
the deferred curation, the internal triager reading the knowledge base, the measures (PR 4, then the
aws-0 session and the replay). Then phase 2: `Smana/runlore-kb` adopted (PR 6) and the
`kb-entries` class in shadow (PR 7).

**Architecture:** Feature 14 put every switch in gcp-0's copies; gcp-0 is torn down and aws-0 is
the fenced factory, so this plan adds aws-0 copies for RunLore's two switches only, and widens the
off-by-default suite by exactly those two (RK15). Everything else lands in base, where both clusters
render it and only the fenced factory acts: the class settings, RunLore's factory values, the agent
router's `runlore-kb` target and the internal triager's tools.

**Tech Stack:** Python 3 with PyYAML; Bash suites run by `scripts/ci/run-tests.sh` inside
`.composite/`; kustomize, Flux, ESO, Cilium, agentgateway; `gh`; `task check`.

**Spec:** [RunLore's knowledge base, filled by the agent factory](../specs/2026-11-03-runlore-kb-from-the-factory-design.md):
RK3, RK5, RK12, RK15, RK17, RK20, "Interfaces", "Phases and gates", rows 4, 6, 7 of "Pull requests,
in order", the Gate. The other plans: [Maku](2026-11-03-runlore-kb-maku-plan.md)
(PRs 1, 5), [RunLore](2026-11-03-runlore-kb-runlore-plan.md) (PR 2),
[cloud-native-ref](2026-11-03-runlore-kb-cloud-native-ref-plan.md) (PR 3). The mechanics this plan
repeats (pins, the subscriber, the principal) are the
[feature 14 plan](2026-10-27-runlore-a2a-ai-native-ref-plan.md)'s Tasks 2 to 4.

**Out of this plan:** phases 3 and 4 (planned at their gates). RunLore's own pin and its curate
values (the host's, PR 3). The fence flip on `Smana/cloud-native-ref` (already `aws-0`, runbook 12).

## Pull requests across the five repositories

Releases are named by the plan that cuts them: Maku `vK1` (PR 1) and `vK2` (PR 5),
RunLore `vL1` (PR 2). Read each from its repository's releases when the step that pins it runs.

| # | Repository | Content | Pins | Proof | Depends on |
|---|---|---|---|---|---|
| 1 | Maku | `room.monitor_verdict`, `publishStarts`, the class inferred at publish; `vK1` | — | offline 1, 2 | — |
| 2 | RunLore | curation deferral, the outcome observation, `lore kb resolve`, the Queue pass, the weekly issue, `/mcp`; `vL1` | — | offline 3–6, 9 | — |
| 3 | cloud-native-ref | RunLore on aws-0, one replica on a volume, its ingress from the agent router, curate values with `stale_after: 0s`; contract H8 | RunLore `vL1` | host CI | 2 |
| 3b | cloud-native-ref | `stale_after: 720h` | — | host CI | live 4 |
| 4 | ai-native-ref | Tasks 1–9 | Maku `vK1`, `HOST_REF` = PR 3's merge | `task check` | 1, 3 |
| — | aws-0 | phase 1 session and the replay, runbook 25 | | live 1–4 | 4 |
| 5 | Maku | the adopted shape of a RunLore entry PR, its required label; `vK2` | — | offline 7 | 1 |
| 6 | runlore-kb | Task 10: the fence file and `.policy.yml` | — | the merge gate reads it | phase 1 gate |
| 7 | ai-native-ref | Task 11 | Maku `vK2` | `task check` | 5, 6 |

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| K1 | **The D4 exception is two keys on aws-0**: `api.internalPrincipals` in aws-0's factory values, and a broker `webhooks` list in aws-0's config whose every entry is named `runlore`. `SWITCHED_ON` stays `gcp-0` for everything else | RK15. `SESSION_START` is the precedent (runbook 19): a set of clouds per switch, not a second switched-on cloud |
| K2 | **aws-0's principal is a file of its own**, `tooling/aws-0/agent-factory/helm-values-internal.yaml`, merged last through `valuesFrom`, as gcp-0's `helm-values-sponsored.yaml` is. Its client id and project id come from a new aws-0 `agent-factory-sponsored` ExternalSecret holding `runlore-principal`'s two properties only | aws-0 applies no Slack App, so the base `slack-app/externalsecret-sponsored.yaml` never renders there |
| K3 | **`alert-rules` gets `shadow: true` in base** | RK15: decisions recorded, nothing armed. Both clusters render base; only the fenced factory acts |
| K4 | **`runlore-kb` is a static target in base `mcp.yaml`**, `runlore.runlore.svc.cluster.local:8080`, `/mcp`, StreamableHTTP, listed only by `profiles/triager.internal.yaml` (`kb_search`, `kb_get`) | RK12: phase 1 is the internal triager only. A cluster without RunLore is Review Focus 1 |
| K5 | **`factory.curation: {defer: true, window: 7d}`** in `observability/base/runlore-factory/helm-values-configmap.yaml` | The factory values are this repository's (H8). 7 days covers a publish, a merge and `alert-rules`' 2h `followUpWindow` |
| K6 | **Human touches per incident come from `scripts/ops/kb-measures.py`**, from GitHub alone: on each RunLore stub of the week (`factory/proposed`, opened by the factory's App) and on what it published, count label events and merges whose actor is not a bot | RK1. GitHub outlives the Task CRs and rooms; the factory's Apps are the only non-human actors that label or merge |
| K7 | **The phase 1 session is runbook 25**, not a rewrite of runbook 20 | Runbook 20 is feature 14's evidence and stays as run. 25 is the next free number |
| K8 | **`Smana/runlore-kb` is the factory's third repository**, every class shadow until its own 20 shadow decisions | The rule the second repository set (v2 design D9); the spec's phase 2 gate is the same count |

## Global Constraints

- **Worktrees:** one per PR, from a freshly fetched `origin/main`, rebased before every push.
- **`task check` is the evidence** (AGENTS.md). A new suite is `git add`ed before it runs
  (`run-tests.sh` discovers suites with `git ls-files`). `pre-commit run --all-files` before pushing.
- **The suite contract:** line 1 the shebang, line 2 `# requires: <tools>`; exit 77 is SKIP.
- **Git hygiene:** `export PYTHONDONTWRITEBYTECODE=1`; `git add` named paths, never `-A`. Never `git stash`.
- **Commits:** conventional, in English, no trailers.
- **Verbatim from the spec:** the aws-0 principal `{name: runlore, sponsor: Smana, repositories: [Smana/cloud-native-ref], dailyUSD: 10, maxCostUSD: 2, maxOpenTasks: 3, minConfidence: 0.75, dailyTasks: 5, verification: true, publishStarts: true}`;
  `factory.curation: {defer: true, window: 7d}`; the target `runlore-kb`; the class `kb-entries`, `autoMergesPerDay: 5`.

## Review Focus

1. **A cluster without RunLore**: gcp-0, or aws-0 before PR 3 lands. The triager's `tools/list` must
   still carry its other servers' tools. Task 7's wire suite asserts the target is one more backend,
   not a precondition of the others.
2. **The D4 exception widening by accident**: a second subscriber in aws-0's broker config, or a
   sponsored principal in aws-0's values, must still fail the suite (Task 3).
3. **The window shorter than the loop**: a `window` under the longest `followUpWindow` would draft
   every entry unverified. Task 6's values suite pins `7d` and checks it against `alert-rules`.
4. **The KB class armed early**: `kb-entries` with `live: true` before 20 shadow decisions. Task 11's
   suite refuses `live` on the class.
5. **A bot counted as a human touch**: the factory's App labelling its stub `factory/proposed`, or the
   merger App merging, must not count. Task 8's fixture carries an App-applied label and expects it excluded.

## File structure

| File | Change | Task |
|---|---|---|
| `HOST_REF`, `HOST-CONTRACT.md` | the host at CNR PR 3, contract version 6 | 1 |
| the Maku pin sites | `vK1`, then `vK2` | 2, 11 |
| `scripts/ci/tests/test-factory-interfaces-off.py` | K1 | 3 |
| `infrastructure/aws-0/room-broker/{config,kustomization}.yaml`, new `externalsecret-webhook-runlore.yaml`, new `network-policy-webhooks-patch.yaml`, `scripts/ci/tests/test-room-broker-suspend.py` | the subscriber on aws-0 | 4 |
| `tooling/aws-0/agent-factory/kustomization.yaml`, new `helm-values-internal.yaml`, new `externalsecret-sponsored.yaml` | the principal on aws-0 | 5 |
| `tooling/base/agent-factory/helm-values-configmap.yaml:54-56` | `alert-rules` shadow | 6 |
| `observability/base/runlore-factory/helm-values-configmap.yaml`, `scripts/ci/tests/test-runlore-factory-values.py` | `factory.curation` | 6 |
| `infrastructure/base/agent-gateway/{mcp,network-policy}.yaml`, `profiles/triager.internal.yaml`, `scripts/ci/tests/test-gen-capabilities.py` | `runlore-kb` | 7 |
| new `scripts/ops/kb-measures.py`, new `scripts/ci/tests/test-kb-measures.py`, new `scripts/ci/tests/kb-measures-fixtures/` | the measures | 8 |
| new `docs/runbooks/agent-factory/25-runlore-kb-phase-1.md`, `README.md`, the spec's status line | the session | 9 |
| `Smana/runlore-kb`: new `.github/agent-factory.yaml`, new `.policy.yml` | adoption | 10 |
| `tooling/base/agent-factory/helm-values-configmap.yaml` (a third repository), new `scripts/ci/tests/test-kb-class-shadow.py` | `kb-entries` | 11 |

---

## PR 4: phase 1

### Task 1: The host at CNR PR 3

**Files:** `HOST_REF`, `HOST-CONTRACT.md` (header, version table, H5 ZITADEL row, H8)

- [ ] **Step 1: Read the host.** `gh pr view <CNR PR 3> -R Smana/cloud-native-ref --json mergeCommit,state`:
  `MERGED`. At that commit, `observability/aws-0/kustomization.yaml` lists `./runlore`, and
  `flux/sources/gitrepo-runlore.yaml` names `vL1`.
- [ ] **Step 2: Bump.** The commit into `HOST_REF`. `HOST-CONTRACT.md` version 6, "Changes from 5:
  H8 states RunLore runs on aws-0 and admits the agent router, which reads its knowledge base at
  `/mcp` on 8080". H8 takes the cloud-native-ref plan's Task 4 Step 3 words exactly. H5 is unchanged:
  aws-0 hosts ZITADEL, so the machine user is the existing `runlore`.
- [ ] **Step 3: Check, commit.** `task check` green (the doc-path check resolves host paths against `.host/`).

```bash
git add HOST_REF HOST-CONTRACT.md
git commit -m "chore(host): HOST_REF at RunLore on aws-0; contract version 6"
```

### Task 2: Pin Maku `vK1`

**Files:** every Maku pin site, as the feature 14 plan's Task 2 lists them
(`git grep -n -F "$BASE"` finds them all).

- [ ] **Step 1: Read the release.** As that Task 2's Step 1, with the greps
  `'room.monitor_verdict|PublishStarts|json:"publishStarts'` in `"v$V" -- internal api`. **Stop and
  report** a new required config key or a chart object beyond PR 1's.
- [ ] **Step 2: Move every pin**, then `task check` green.

```bash
git add flux tooling infrastructure observability website
git commit -m "feat(agent-factory): Maku vK1, the monitor verdict event and publish that starts"
```

### Task 3: The D4 exception, two keys on aws-0

**Files:** Modify `scripts/ci/tests/test-factory-interfaces-off.py:8-27,54-90`

**Interfaces:**
- Produces: `RUNLORE_ON = {"gcp-0", "aws-0"}` and `runlore_only(doc) -> bool` (true when a broker
  config's `webhooks` is a non-empty list whose every entry has `name: runlore`).

- [ ] **Step 1: Write the failing cases.** A scratch copy under `$TMPDIR` of
  `infrastructure/aws-0/room-broker/config.yaml` with `webhooks: [{name: runlore}]` must pass;
  with `webhooks: [{name: runlore}, {name: slack-app}]` it must fail naming `declares webhooks (D4)`.
  A scratch aws-0 values file with `api.internalPrincipals: [{name: runlore}]` must pass; with
  `api.sponsored: [{name: slack-app}]` it must fail. The script gains `--root <dir>` so the cases run
  on a scratch tree.
- [ ] **Step 2: Run them**: `python3 scripts/ci/tests/test-factory-interfaces-off.py --root "$T"`;
  expected: the runlore-only cases FAIL today (`declares webhooks (D4)`).
- [ ] **Step 3: The exception.** In the broker loop, an aws-0 config whose `webhooks` is
  `runlore_only` passes; in `sponsored_in`'s caller, an aws-0 file whose `api` holds only
  `internalPrincipals` passes. The docstring names RK15 beside runbook 19's precedent.
- [ ] **Step 4: Run** the cases and the real tree: PASS. **Commit**

```bash
git add scripts/ci/tests/test-factory-interfaces-off.py
git commit -m "test(agent-factory): aws-0 may declare RunLore's principal and subscriber, nothing else (RK15)"
```

### Task 4: The broker's `runlore` subscriber on aws-0

**Files:**
- Modify: `infrastructure/aws-0/room-broker/config.yaml:72-80`, `infrastructure/aws-0/room-broker/kustomization.yaml`
- Create: `infrastructure/aws-0/room-broker/externalsecret-webhook-runlore.yaml` (gcp-0's, unchanged)
- Generate: `infrastructure/aws-0/room-broker/network-policy-webhooks-patch.yaml`

- [ ] **Step 1: The subscriber.** Replace the commented `webhooks:` example with gcp-0's `runlore`
  entry, its `events` plus `room.monitor_verdict`. Add the same event to gcp-0's entry.
- [ ] **Step 2: The key and the egress.** The ExternalSecret in aws-0's `resources`;
  `python3 scripts/ci/gen-webhook-egress.py --write` writes aws-0's patch; the kustomization lists it
  under `patches` as gcp-0's does. The base `app.yaml` already mounts `webhook-runlore`, optional.
- [ ] **Step 3: The suspend suite.** `test-room-broker-suspend.py:8-12,97-110` holds aws-0's copy to
  base's but for `human.mcp.sessionStart`; it now also allows a `webhooks` list that
  `test-factory-interfaces-off.runlore_only` accepts (import it, one rule), and its docstring says so.
  First run it on the Step 1 tree: FAIL naming aws-0; after: PASS.
- [ ] **Step 4: Run**: `python3 scripts/ci/tests/test-gen-webhook-egress.py && bash scripts/ci/tests/test-room-broker-webhook-egress.sh && python3 scripts/ci/tests/test-factory-interfaces-off.py && python3 scripts/ci/tests/test-room-broker-suspend.py`;
  PASS.

```bash
git add infrastructure/aws-0/room-broker infrastructure/gcp-0/room-broker/config.yaml scripts/ci/tests
git commit -m "feat(room-broker): RunLore as a standing webhook subscriber on aws-0, with the monitor verdict"
```

### Task 5: The internal principal on aws-0

**Files:**
- Create: `tooling/aws-0/agent-factory/helm-values-internal.yaml`, `tooling/aws-0/agent-factory/externalsecret-sponsored.yaml`
- Modify: `tooling/aws-0/agent-factory/kustomization.yaml`

- [ ] **Step 1: The values.** A ConfigMap `agent-factory-helm-values-internal` whose `values.yaml`
  sets `config.api.projectIDFile: /etc/agent-factory-sponsored/project-id` and
  `config.api.internalPrincipals` to the Global Constraints' entry, with
  `clientIDFile: /etc/agent-factory-sponsored/runlore-client-id`. Its comment carries gcp-0's dollar
  note and "standing on aws-0 (RK15)".
- [ ] **Step 2: The secret.** `agent-factory-sponsored` in `agent-system` from `agents-secrets`:
  `runlore-client-id` and `project-id`, both from `runlore-principal`.
- [ ] **Step 3: The patch.** aws-0's kustomization lists both files and appends the ConfigMap to the
  HelmRelease's `valuesFrom`, as gcp-0's does for `agent-factory-helm-values-sponsored`.
- [ ] **Step 4: Run**: `python3 scripts/ci/tests/test-factory-interfaces-off.py`, then
  `kustomize build tooling/aws-0/agent-factory | yq 'select(.kind=="ConfigMap" and .metadata.name=="agent-factory-helm-values-internal") | .data["values.yaml"]' | yq '.config.api.internalPrincipals[0].publishStarts'`
  prints `true`.

```bash
git add tooling/aws-0/agent-factory
git commit -m "feat(agent-factory): RunLore as a standing internal principal on aws-0, publish starts its fix"
```

### Task 6: `alert-rules` in shadow; RunLore's curation values

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml:51-56`
- Modify: `observability/base/runlore-factory/helm-values-configmap.yaml:30-60`
- Test: `scripts/ci/tests/test-runlore-factory-values.py`

- [ ] **Step 1: Write the failing assertions** in `test-runlore-factory-values.py`:

```python
cur = values["config"]["factory"]["curation"]
check("curation defers", cur == {"defer": True, "window": "7d"})
fu = classes["alert-rules"]["monitor"]["followUpWindow"]
check("the window covers alert-rules' follow-up", hours("7d") > hours(fu))
check("alert-rules is shadow, nothing armed", classes["alert-rules"].get("shadow") is True and "live" not in classes["alert-rules"])
```

`hours` parses `Nd`/`Nh`/`Nm`; `classes` is cloud-native-ref's block of the factory values.
- [ ] **Step 2: Run**: `python3 scripts/ci/tests/test-runlore-factory-values.py`; FAIL on `curation`.
- [ ] **Step 3: The values.** `curation: {defer: true, window: 7d}` under `factory:` with one line
  "RK5: an accepted incident is drafted once verified; 7d covers a publish, a merge and the
  follow-up". `alert-rules: {shadow: true, …}`, its comment: "shadow since RK15: decisions recorded,
  a maintainer merges".
- [ ] **Step 4: Run**: PASS. **Commit**

```bash
git add tooling/base/agent-factory/helm-values-configmap.yaml observability/base/runlore-factory/helm-values-configmap.yaml scripts/ci/tests/test-runlore-factory-values.py
git commit -m "feat(runlore-factory): RunLore drafts verified entries; alert-rules in shadow"
```

### Task 7: The internal triager reads the knowledge base

**Files:**
- Modify: `infrastructure/base/agent-gateway/mcp.yaml:48-60` (targets), `infrastructure/base/agent-gateway/network-policy.yaml:120-135`
- Modify: `infrastructure/base/agent-gateway/profiles/triager.internal.yaml`
- Test: `scripts/ci/tests/test-gen-capabilities.py`, `scripts/ci/tests/test-agent-capabilities-wire.sh`

- [ ] **Step 1: Write the failing assertions** in `test-gen-capabilities.py`:

```python
exprs = rendered_expressions("internal")  # the internal listener's policy items
check("the internal triager reaches runlore-kb's two tools",
      any('"runlore-kb"' in e and 'kb_search' in e and 'kb_get' in e and '"triager"' in e for e in exprs))
check("no other profile names runlore-kb",
      not any('"runlore-kb"' in e and '"triager"' not in e for e in all_expressions()))
check("no public listener names runlore-kb", not any('"runlore-kb"' in e for e in rendered_expressions("public")))
```

- [ ] **Step 2: Run**: `python3 scripts/ci/tests/test-gen-capabilities.py`; FAIL.
- [ ] **Step 3: The target, the tools, the egress.** In `mcp.yaml` after `mcp-victorialogs`:
  `{name: runlore-kb, static: {host: runlore.runlore.svc.cluster.local, port: 8080, path: /mcp, protocol: StreamableHTTP}}`,
  commented "RunLore's read-only knowledge (RK12), the host's Service (H8)". The profile gains
  `runlore-kb: [kb_search, kb_get]`. The gateway's CNP gains an egress rule to
  `{io.kubernetes.pod.namespace: runlore, app.kubernetes.io/name: runlore}` on 8080/TCP. Then
  `python3 scripts/ci/gen-capabilities.py --write`.
- [ ] **Step 4: Run**: `python3 scripts/ci/tests/test-gen-capabilities.py && bash scripts/ci/tests/test-agent-capabilities.sh && bash scripts/ci/tests/test-agent-capabilities-wire.sh`;
  PASS, and the wire suite's `tools/list` for the internal triager still lists every
  `flux-operator-mcp`, `mcp-victoriametrics` and `mcp-victorialogs` tool with `runlore-kb` unreachable
  (Review Focus 1). **Commit**

```bash
git add infrastructure/base/agent-gateway scripts/ci/tests/test-gen-capabilities.py scripts/ci/tests/test-agent-capabilities-wire.sh
git commit -m "feat(agent-gateway): the internal triager reads RunLore's knowledge base (kb_search, kb_get)"
```

### Task 8: The measures

**Files:**
- Create: `scripts/ops/kb-measures.py`, `scripts/ci/tests/test-kb-measures.py`, `scripts/ci/tests/kb-measures-fixtures/{stubs,events,kb-prs}.json`

**Interfaces:**
- Produces: `python3 scripts/ops/kb-measures.py --since YYYY-MM-DD [--until YYYY-MM-DD] [--fixtures DIR]`,
  printing one Markdown table: incidents, human touches per incident (median, max), KB PRs opened,
  merged, closed, open at the end, the oldest open's age in days. `measures(stubs, events, kb_prs) -> dict`.

- [ ] **Step 1: Write the failing test.** Fixtures: two stubs; on the first, `factory/publish` by
  `Smana` and the fix merged by `Smana`; on the second, `factory/proposed` by `factory-app[bot]`,
  `factory/publish` by `Smana`, the fix merged by `merger-app[bot]`; three KB PRs, one merged by `Smana`.

```python
m = kb.measures(stubs, events, kb_prs)
check("touches per incident", m["touches"] == {"median": 1.5, "max": 2})
check("a bot's label is not a touch", m["touches_by_incident"]["#2"] == 1)
check("kb counts", (m["kb_opened"], m["kb_merged"], m["kb_open_end"]) == (3, 1, 2))
```

- [ ] **Step 2: Run**: `python3 scripts/ci/tests/test-kb-measures.py`; FAIL (`No module named`).
- [ ] **Step 3: Implement `measures`** and the `gh api` reads behind `--fixtures`: stubs are
  `Smana/cloud-native-ref` issues labelled `factory/proposed` by the factory's App in the window; the
  fix is the issue the stub's `factory/publish` comment links; an actor is a bot when its `type` is
  `Bot` or its login ends `[bot]`. KB PRs are `Smana/runlore-kb`'s, labelled `runlore`.
- [ ] **Step 4: Run**: PASS. **Commit**

```bash
git add scripts/ops/kb-measures.py scripts/ci/tests/test-kb-measures.py scripts/ci/tests/kb-measures-fixtures
git commit -m "feat(ops): kb-measures, human touches per incident and the knowledge queue from GitHub"
```

### Task 9: Runbook 25, the README, the PR

**Files:** Create `docs/runbooks/agent-factory/25-runlore-kb-phase-1.md`; modify
`docs/runbooks/agent-factory/README.md` (the table after row 24), the spec's status line.

- [ ] **Step 1: Runbook 25**, after runbook 20's shape: 0. prerequisites (the `runlore` machine
  user's keys mirrored to OpenBao, the cloud-native-ref plan's Task 6 command; the webhook key seeded
  in both mounts as runbook 14 does; the KB repo's `Knowledge queue` issue absent or closed); 1. live 1, a restart of `runlore-0` mid-soak keeps the
  soak (`kubectl -n runlore get lease runlore-leader -o json | jq .spec.holderIdentity` unchanged,
  one replica); 2. live 2, a seeded `vector(1)` rule, one `factory/publish`, `alert-rules` in the stub
  task's `status.published.class`, the owner's merge, `room.monitor_verdict` in RunLore's log, one KB PR labelled
  `ready-to-merge` whose `resolution` names the fix; 3. live 3 = runbook 20's live 5, then the
  verified generation completes the entry; 4. the replay (RK17): `lore kb resolve` on #157 to #163
  with CNR #2638 and #2659, the first weekly issue listing the backlog, then CNR PR 3b (`stale_after:
  720h`); 5. the phase 1 gate: `python3 scripts/ops/kb-measures.py --since <session day>` each week,
  four cleared queues, RK20's two 14-day reads of `runlore:model_input_tokens:increase1d`, the
  results recorded in the status record.
- [ ] **Step 2: The README row**: proves live 1–4 and the phase 1 gate; needs the owner's go, the
  ZITADEL sync, the seeded keys; about 2 h plus four weeks.
- [ ] **Step 3: `task check`** green, `pre-commit run --all-files`, the PR.

```bash
git add docs/runbooks/agent-factory/25-runlore-kb-phase-1.md docs/runbooks/agent-factory/README.md docs/superpowers/specs/2026-11-03-runlore-kb-from-the-factory-design.md
git commit -m "docs(runbooks): 25, RunLore's knowledge base, phase 1 on aws-0"
```

---

## PR 6: `Smana/runlore-kb` adopted (phase 2)

### Task 10: The fence file and the policy

**Files** (in `Smana/runlore-kb`): Create `.github/agent-factory.yaml`, `.policy.yml`; modify
`.github/workflows/validate-kb.yml:29`.

- [ ] **Step 1: The owner installs** the factory's App and policy-bot on `Smana/runlore-kb`
  (runbook 12's adoption steps for a repository).
- [ ] **Step 2: The fence**: `.github/agent-factory.yaml` naming `aws-0`, the content
  `Smana/cloud-native-ref`'s holds.
- [ ] **Step 3: The policy**: `.policy.yml` with one approval rule, `low-risk: kb-entries`, admitting
  a RunLore entry PR (one added `incidents/*.md`, `index.md` and `log.md` modified) from `runlore[bot]`
  on a `runlore/kb-` branch, labelled `ready-to-merge`; every other PR needs a maintainer's approval.
  A human-authored gate-path PR, as AM12 requires.
- [ ] **Step 4: The validator**: `validate-kb.yml` installs `lore@vL1` instead of `v0.10.0`, so the new
  frontmatter (`origin`, `resolution`) validates; branch protection on `main` requires the
  `validate` check. Run it on #163's head: green.
- [ ] **Step 5: Check**: after a merge, the factory's log on aws-0 names `Smana/runlore-kb` fenced to
  `aws-0`.

## PR 7: the `kb-entries` class in shadow (phase 2)

### Task 11: Pin `vK2`; the third repository

**Files:**
- Modify: the Maku pin sites; `tooling/base/agent-factory/helm-values-configmap.yaml` (a
  third entry under `repositories`)
- Create: `scripts/ci/tests/test-kb-class-shadow.py`

- [ ] **Step 1: Write the failing suite**:

```python
kb = next(r for r in repos if r["name"] == "Smana/runlore-kb")
c = kb["classes"]["kb-entries"]
check("kb-entries is shadow", c.get("shadow") is True and "live" not in c)
check("one added validated file", c["diffShape"] == "<vK2's shape name>" and c.get("addOnly") is True)
check("five a day at most", c["autoMergesPerDay"] == 5)
check("the only class there", set(kb["classes"]) == {"kb-entries"})
```

  The shape's keys are the Maku plan's (read `vK2`'s `docs/factory.md`); fill them in
  before running.
- [ ] **Step 2: Run**: FAIL (`StopIteration`).
- [ ] **Step 3: Pin `vK2`** as Task 2, then the entry: `name: Smana/runlore-kb`, `maintainers: [Smana]`,
  `classes: {kb-entries: {shadow: true, …the shape…, autoMergesPerDay: 5}}`, the breaker as the
  others', its comment "RK3: RunLore drafts, the merge gate merges verified entries; shadow until 20
  decisions (K8)".
- [ ] **Step 4: Run** the suite and `task check`: PASS. **Commit**, the PR.

```bash
git add flux tooling infrastructure observability website scripts/ci/tests/test-kb-class-shadow.py
git commit -m "feat(agent-factory): Maku vK2; runlore-kb's kb-entries class in shadow"
```

## Gate

The spec's offline proof 8 and live proofs 1 to 4 (runbook 25), then the phase 1 gate (four cleared
weekly queues, none older than 14 days; the seven showcase entries merged; live 3 passed). Phase 2's
gate (20 shadow decisions, none a "would merge" on an entry a human closed, the threat check) is read
from the factory's shadow record each week and recorded in the status record.
