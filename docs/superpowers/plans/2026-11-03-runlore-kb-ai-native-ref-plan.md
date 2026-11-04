# RunLore's knowledge base from the factory, ai-native-ref PRs 4 and 7, runlore-kb PR 6 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire phase 1 into the platform on aws-0, where the fence says the factory acts: RunLore's
session switch (its internal principal, and its broker subscriber off on `main`), `publishStarts` and `alert-rules` in shadow,
the deferred curation, the internal triager reading the knowledge base, the measures (PR 4, then the
aws-0 session and the replay). Then phase 2: `Smana/runlore-kb` adopted (PR 6) and the
`kb-entries` class in shadow (PR 7).

**Architecture:** Feature 14 put every switch in gcp-0's copies; gcp-0 is torn down and aws-0 is
the fenced factory, so this plan adds aws-0 copies for RunLore's two switches only, and widens the
off-by-default suite by exactly those two (RK15). RunLore runs only on purpose, for a demo session:
the subscriber is this repository's half of the switch, flipped with the host's three places by
runbook 25. Everything else lands in base, where both clusters
render it and only the fenced factory acts: the class settings, RunLore's factory values, the agent
router's `runlore-kb` target and the internal triager's tools.

**Tech Stack:** Python 3 with PyYAML; Bash suites run by `scripts/ci/run-tests.sh` inside
`.composite/`; kustomize, Flux, ESO, Cilium, agentgateway; `gh`; `task check`.

**Spec:** [RunLore's knowledge base, filled by the agent factory](../specs/2026-11-03-runlore-kb-from-the-factory-design.md):
RK3, RK5, RK12, RK15, RK17, RK20, "Interfaces", "Phases and gates", rows 4, 6, 7 of "Pull requests,
in order", the Gate. The other plans: [Maku](2026-11-03-runlore-kb-maku-plan.md)
(PRs 1, 5), [RunLore](2026-11-03-runlore-kb-runlore-plan.md) (PR 2),
[cloud-native-ref](2026-11-03-runlore-kb-cloud-native-ref-plan.md) (PRs 3, 4b, 7b). The mechanics this plan
repeats (pins, the subscriber, the principal) are the
[feature 14 plan](2026-10-27-runlore-a2a-ai-native-ref-plan.md)'s Tasks 2 to 4.

**Out of this plan:** phases 3 and 4 (planned at their gates). RunLore's own pin and its curate
values (the host's, PR 3). The fence flip on `Smana/cloud-native-ref` (already `aws-0`, runbook 12).
The ai-native-ref releases themselves: each is the owner's decision, as every release is. This plan
says where one is needed (the table's 4b and 7b, every session switch) and never cuts one.
Follow-up, not here: the site page `website/content/docs/how-it-works/runlore.md:37` still lists the
label steps RK15 removes for a session; update it after the phase 1 gate, following
`docs/docs-style.md` (no cluster names, no session or plan IDs).

## Pull requests across the five repositories

Releases are named by the plan that cuts them: Maku `vK1` (PR 1) and `vK2` (PR 5),
RunLore `vL1` (PR 2). Read each from its repository's releases when the step that pins it runs.

| # | Repository | Content | Pins | Proof | Depends on |
|---|---|---|---|---|---|
| 1 | Maku | `room.monitor_verdict`, `publishStarts`, the class inferred at publish; `vK1` | — | offline 1, 2 | — |
| 2 | RunLore | curation deferral, the outcome observation, `lore kb resolve`, the Queue pass, the queue issue and `lore curate queue-issue`, `/mcp`; `vL1` | — | offline 3–6, 9 | — |
| 3 | cloud-native-ref | RunLore's session switch on aws-0, off: one replica on a volume, its ingress from the agent router, curate values with `stale_after: 0s`; contract H8 | RunLore `vL1` | host CI | 2 |
| 3b | cloud-native-ref | `stale_after: 720h` | — | host CI | live 4 |
| 3c | cloud-native-ref | the daily spend alert (RK20) | — | host CI | the first session |
| 4 | ai-native-ref | Tasks 1–9 | Maku `vK1`, `HOST_REF` = PR 3's merge | `task check` | 1, 3 |
| — | ai-native-ref | an owner's release (or PR pre-release) carrying PR 4 | — | its release workflow, cosigned | 4 |
| 4b | cloud-native-ref | pins that release's tag and digest (CNR plan, Task 9) | the ai-native-ref release | host CI | the release |
| — | aws-0 | phase 1 session and the replay, runbook 25 | | live 1–4 | 4b |
| 5 | Maku | the adopted shape of a RunLore entry PR, its required label; `vK2` | — | offline 7 | 1 |
| 6 | runlore-kb | Task 10: the fence file and `.policy.yml` | — | the merge gate reads it | phase 1 gate |
| 7 | ai-native-ref | Task 11 | Maku `vK2` | `task check` | 5, 6 |
| — | ai-native-ref | an owner's release carrying PR 7 | — | its release workflow | 7 |
| 7b | cloud-native-ref | pins that release's tag and digest (CNR plan, Task 9) | the ai-native-ref release | host CI | the release |

An ai-native-ref change reaches aws-0 only through the host's `OCIRepository/ai-native-ref`, pinned by
tag and digest and cosigned (`HOST-CONTRACT.md` H1): a merged PR here does nothing on the cluster
until a release carries it and the host pin moves. The same holds for every session switch (K9, runbook
25).

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| K1 | **The D4 exception is two keys on aws-0**: `api.internalPrincipals` in aws-0's factory values, and a broker `webhooks` list in aws-0's config whose every entry is named `runlore`. `SWITCHED_ON` stays `gcp-0` for everything else | RK15. `SESSION_START` is the precedent (runbook 19): a set of clouds per switch, not a second switched-on cloud |
| K2 | **aws-0's principal is a file of its own**, `tooling/aws-0/agent-factory/helm-values-internal.yaml`, merged last through `valuesFrom`, as gcp-0's `helm-values-sponsored.yaml` is. Its client id and project id come from a new aws-0 `agent-factory-sponsored` ExternalSecret holding `runlore-principal`'s two properties only | aws-0 applies no Slack App, so the base `slack-app/externalsecret-sponsored.yaml` never renders there |
| K3 | **`alert-rules` gets `shadow: true` in base** | RK15: decisions recorded, nothing armed. Both clusters render base; only the fenced factory acts. The host's `.policy.yml` has no `low-risk: alert-rules` rule, and the parity suite says a rule is what lets a shadow decision reach "would arm" (`test-agent-merge-gate-parity.py`, R50): so in phase 1 an `alert-rules` shadow decision can never arm, and nothing in phase 1 reads it. Accepted; a rule is phase 3's work |
| K4 | **`runlore-kb` is a static target in base `mcp.yaml`**, `runlore.runlore.svc.cluster.local:8080`, `/mcp`, StreamableHTTP, listed only by `profiles/triager.internal.yaml` (`kb_search`, `kb_get`) | RK12: phase 1 is the internal triager only. A cluster without RunLore is Review Focus 1 |
| K5 | **`factory.curation: {defer: true, window: 7d}`** in `observability/base/runlore-factory/helm-values-configmap.yaml` | The factory values are this repository's (H8). 7 days covers a publish, a merge and `alert-rules`' 2h `followUpWindow` |
| K6 | **Human touches per incident come from `scripts/ops/kb-measures.py`**, from GitHub alone: on each RunLore stub of the session (`factory/proposed`, opened by the factory's App, and carrying RunLore's origin) and on what it published, count label events and merges whose actor is not a bot. The follow-up issue the monitor files (RA12, title `RunLore: the fix in #<pr> did not hold (<alert>)`) carries `factory/proposed` too and is not an incident; neither is a stub from another source | RK1. GitHub outlives the Task CRs and rooms; the factory's Apps are the only non-human actors that label or merge. Counting every `factory/proposed` issue would overcount incidents |
| K7 | **The phase 1 session is runbook 25**, not a rewrite of runbook 20 | Runbook 20 is feature 14's evidence and stays as run. 25 is the next free number |
| K8 | **`Smana/runlore-kb` is the factory's third repository**, every class shadow until its own 20 shadow decisions | The rule the second repository set (v2 design D9); the spec's phase 2 gate is the same count |
| K9 | **This repository's half of the switch is a set of edits in aws-0's `room-broker` directory, never one line.** Off (as committed): the `runlore` entry commented in `config.yaml`; `externalsecret-webhook-runlore.yaml` out of `resources` (commented, so nothing syncs a key nobody seeded); no `network-policy-webhooks-patch.yaml` and no `patches:` line for it. On: the entry, the ExternalSecret in `resources`, the patch that `gen-webhook-egress.py --write` generates, and its `- path:` line under `patches:`. The principal stays declared, inert while RunLore is off | RK15. A subscriber left on while RunLore is off is disabled after three failed deliveries (factory interfaces F6) and stays so; a principal nobody calls costs nothing. `gen-webhook-egress.py` fails on a patch file the overlay no longer needs and on a config with subscribers whose patch is unlisted, and `--write` neither deletes the file nor edits the kustomization, so on and off differ in all four edits. Plus the host's three places |
| K10 | **`/mcp` has no token and is open to any caller the port admits** (from the 2026-11-04 review) | The owner's decision stands: network policy only, read-only, public text (RK13). The router's rule is L4, so the host's H8 says "any caller the port admits reaches `/mcp`" (the router, the broker, the whole `observability` namespace, the Gateway's data plane); the wording changes, not the design. RunLore warns at start-up that `/mcp` has no token | A caller in an admitted namespace reads public entries; a token would need the router to inject it (`room-broker`'s `policies.auth`) and buys nothing the repository does not already publish |
| K11 | **Each ai-native-ref release is the owner's decision**, and each on or off flip needs one (from the 2026-11-04 review) | The host applies this repository only through its pinned, cosigned artifact. A release (or the PR pre-release the host's D2 allows on a feature branch), then a host PR with the new tag and digest, stands between a merge here and the cluster, for PR 4, PR 7 and every session switch | A plan that cuts a release itself decides for the owner |
| K12 | **PR 7's entry sets `leakScanCheck: validate`** (owner note, from the 2026-11-04 review) | `Smana/runlore-kb` is public text with secret redaction at each tool output (RK13), and has no leak scan of its own; Maku's validation refuses a repository with a shadow class and no `leakScanCheck` in both check lists, so the one check the repository has stands in | A real scan on the KB repository is later work |
| K13 | **RK17's replay exercises the entry path only** (from the 2026-11-04 review) | `lore kb resolve` writes no outcome event, so #157 to #163 stay `unverified` under Decide, and RK17's test of the outcome join is not exercised by it. Runbook 25 says so | Reading the replay as proof of the join would overstate live 4 |
| K14 | **Phase 3 only, not built:** `status: draft` has no writer after a merge, because the gate only merges and a modified entry is refused (RK10) (from the 2026-11-04 review) | RunLore writes `status: draft` in the PR itself, and a human merge promotes it | Noted so phase 3 plans for it |

## Global Constraints

- **Worktrees:** one per PR, from a freshly fetched `origin/main`, rebased before every push.
- **`task check` is the evidence** (AGENTS.md). A new suite is `git add`ed before it runs
  (`run-tests.sh` discovers suites with `git ls-files`). `pre-commit run --all-files` before pushing.
- **The suite contract:** line 1 the shebang, line 2 `# requires: <tools>`; exit 77 is SKIP.
- **Git hygiene:** `export PYTHONDONTWRITEBYTECODE=1`; `git add` named paths, never `-A`. Never `git stash`.
- **Commits:** conventional, in English, no trailers. PR bodies carry no attribution line.
- **Paths:** repo-relative, never a machine's absolute path.
- **Verbatim from the spec:** the aws-0 principal `{name: runlore, sponsor: Smana, repositories: [Smana/cloud-native-ref], dailyUSD: 10, maxCostUSD: 2, maxOpenTasks: 3, minConfidence: 0.75, dailyTasks: 5, verification: true, publishStarts: true}`;
  `factory.curation: {defer: true, window: 7d}`; the target `runlore-kb`; the class `kb-entries`, `maxPerDay: 5`.

## Review Focus

1. **A cluster without RunLore**: gcp-0, or aws-0 while the switch is off (the target stays in base, so
   both clusters render it). The triager's `tools/list` must still carry its other servers' tools. The
   backend's `failureMode: FailOpen` (`mcp.yaml:34`) is what keeps an unreachable `runlore` host from
   taking them down; Task 7 adds an offline assertion that it stays while a `runlore-kb` target exists.
   The wire suite runs a fake `flux-operator-mcp` only and says nothing about it.
2. **The D4 exception widening by accident**: a second subscriber in aws-0's broker config, or a
   sponsored principal in aws-0's values, must still fail the suite (Task 3).
3. **The window shorter than the loop**: a `window` under the longest `followUpWindow` would draft
   every entry unverified. Task 6's values suite pins `7d` and checks it against `alert-rules`.
4. **The KB class armed early**: `kb-entries` with `live: true` before 20 shadow decisions. Task 11's
   suite refuses `live` on the class.
5. **A bot counted as a human touch**: the factory's App labelling its stub `factory/proposed`, or the
   merger App merging, must not count. Task 8's fixture carries an App-applied label and expects it excluded.
6. **A suite whose input this plan changes without naming it**: `test-agent-class-paused-alert.sh` and
   the rule and dashboard it reads (Task 6), `test-agent-mcp-scope.sh` (Task 7),
   `test-agent-merge-gate-parity.py` and `test-agent-factory-pins.py` (Task 11); `assert-agent-gateway.py`
   needs no change (Task 7). Each is run in its task, and `task check` runs all of them.

## File structure

| File | Change | Task |
|---|---|---|
| `HOST_REF`, `HOST-CONTRACT.md` | the host at CNR PR 3, contract version 6 (H8 only) | 1 |
| the Maku pin sites | `vK1`, then `vK2` | 2, 11 |
| `scripts/ci/tests/test-factory-interfaces-off.py` | K1 | 3 |
| `infrastructure/aws-0/room-broker/{config,kustomization}.yaml`, new `externalsecret-webhook-runlore.yaml` (not in `resources` while off), `scripts/ci/tests/test-room-broker-suspend.py`; the generated `network-policy-webhooks-patch.yaml` exists only in the on state | the subscriber on aws-0 | 4 |
| `tooling/aws-0/agent-factory/kustomization.yaml`, new `helm-values-internal.yaml`, new `externalsecret-sponsored.yaml` | the principal on aws-0 | 5 |
| `tooling/base/agent-factory/helm-values-configmap.yaml:54-56`, `observability/base/agent-platform/vmrule-agent-factory.yaml:51`, `observability/base/agent-platform/grafana-dashboard-agent-factory.yaml:88`, `scripts/ci/tests/test-agent-class-paused-alert.sh` | `alert-rules` shadow, and the live-class regex that follows it | 6 |
| `observability/base/runlore-factory/helm-values-configmap.yaml`, `scripts/ci/tests/test-runlore-factory-values.py` | `factory.curation` | 6 |
| `infrastructure/base/agent-gateway/{mcp,network-policy}.yaml`, `profiles/triager.internal.yaml`, the generated `policy-capabilities.yaml`, `scripts/ci/tests/test-gen-capabilities.py`, `scripts/ci/tests/test-agent-mcp-scope.sh` | `runlore-kb` | 7 |
| new `scripts/ops/kb-measures.py`, new `scripts/ci/tests/test-kb-measures.py`, new `scripts/ci/tests/kb-measures-fixtures/` | the measures | 8 |
| new `docs/runbooks/agent-factory/25-runlore-kb-phase-1.md`, `docs/runbooks/agent-factory/README.md` (a row, and line 20's session-switch row), the spec's status line | the session | 9 |
| `Smana/runlore-kb`: new `.github/agent-factory.yaml`, new `.policy.yml` | adoption | 10 |
| `tooling/base/agent-factory/helm-values-configmap.yaml` (a third repository, its full `merge` block), `scripts/ci/tests/test-agent-merge-gate-parity.py`, new `scripts/ci/tests/test-kb-class-shadow.py`; read by `test-agent-factory-pins.py` and `test-agent-class-paused-alert.sh` | `kb-entries` | 11 |

---

## PR 4: phase 1

### Task 1: The host at CNR PR 3

**Files:** `HOST_REF`, `HOST-CONTRACT.md` (header, version table, H8)

- [ ] **Step 1: Read the host.** `gh pr view <CNR PR 3> -R Smana/cloud-native-ref --json mergeCommit,state`:
  `MERGED`. At that commit, `observability/aws-0/kustomization.yaml` carries the commented
  `# - ../base/runlore` with its session-switch comment, and `flux/sources/gitrepo-runlore.yaml` names `vL1`.
- [ ] **Step 2: Bump.** The commit into `HOST_REF`. `HOST-CONTRACT.md` version 6, "Changes from 5:
  H8: RunLore's ingress admits the agent router, which reads its knowledge base at `/mcp` on 8080; RunLore
  is a session switch on aws-0". H8 takes the cloud-native-ref plan's Task 4 Step 4 words exactly. No other
  row changes (H5 is unchanged: aws-0 hosts ZITADEL, so the machine user is the existing `runlore`).
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
- [ ] **Step 2: Move every pin**, then `task check` green. The Maku plan says to roll the broker
  first; nothing here consumes that order, since every pin moves at once and RunLore is off, so the
  new event reaches no subscriber.

```bash
git add flux tooling infrastructure observability website
git commit -m "feat(agent-factory): Maku vK1, the monitor verdict event and publish that starts"
```

### Task 3: The D4 exception, two keys on aws-0

**Files:** Modify `scripts/ci/tests/test-factory-interfaces-off.py:8-27,54-90`

**Interfaces:**
- Produces: `RUNLORE_ON = {"gcp-0", "aws-0"}` and `runlore_only(doc) -> bool` (true when a broker
  config's `webhooks` is a non-empty list whose every entry has `name: runlore`). Task 4 repeats the
  three-line predicate in `test-room-broker-suspend.py` with a comment naming this one: a suite file here
  is a hyphenated script that runs its checks and calls `sys.exit` at import, so it cannot be imported.

- [ ] **Step 1: Write the failing cases.** A scratch copy under `$TMPDIR` of
  `infrastructure/aws-0/room-broker/config.yaml` with `webhooks: [{name: runlore}]` must pass;
  with `webhooks: [{name: runlore}, {name: slack-app}]` it must fail naming `declares webhooks (D4)`.
  A scratch aws-0 values file with `api.internalPrincipals: [{name: runlore}]` must pass; with
  `api.sponsored: [{name: slack-app}]` it must fail. The script gains `--root <dir>` (parsed from
  `sys.argv` before `ROOT` is set) so the cases run on a scratch tree.
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
- Modify: `infrastructure/aws-0/room-broker/config.yaml:72-80`, `infrastructure/aws-0/room-broker/kustomization.yaml`, `infrastructure/gcp-0/room-broker/config.yaml`, `scripts/ci/tests/test-room-broker-suspend.py`
- Create: `infrastructure/aws-0/room-broker/externalsecret-webhook-runlore.yaml` (gcp-0's, unchanged)
- Generate, in the on state only: `infrastructure/aws-0/room-broker/network-policy-webhooks-patch.yaml`

The two states differ in four edits (K9): the config entry, the ExternalSecret in `resources`, the generated
patch file, and its `patches:` line. `gen-webhook-egress.py` fails on any mix, and `--write` writes the
patch only: it neither lists it nor deletes it.

- [ ] **Step 1: The subscriber.** Replace the commented `webhooks:` example with gcp-0's `runlore`
  entry, its `events` plus `room.monitor_verdict`. Add the same event to gcp-0's entry.
- [ ] **Step 2: The on state.** The ExternalSecret in aws-0's `resources`;
  `python3 scripts/ci/gen-webhook-egress.py --write` writes aws-0's patch; the kustomization lists it
  under `patches` as gcp-0's does (`- path: network-policy-webhooks-patch.yaml`). The base `app.yaml`
  already mounts `webhook-runlore`, optional.
- [ ] **Step 3: The suspend suite.** `test-room-broker-suspend.py:8-12,97-110` holds aws-0's copy to
  base's but for `human.mcp.sessionStart`; it now also allows a `webhooks` list that is RunLore's alone.
  Repeat the predicate there (a list that is non-empty and whose every entry is named `runlore`), with a
  comment "the same rule as `runlore_only` in test-factory-interfaces-off.py (K1)", and say so in its
  docstring. First run it on the Step 1 tree: FAIL naming aws-0; after: PASS.
- [ ] **Step 4: Run, on**: `python3 scripts/ci/gen-webhook-egress.py && python3 scripts/ci/tests/test-gen-webhook-egress.py && bash scripts/ci/tests/test-room-broker-webhook-egress.sh && python3 scripts/ci/tests/test-factory-interfaces-off.py && python3 scripts/ci/tests/test-room-broker-suspend.py`;
  PASS.
- [ ] **Step 5: Off, as committed (K9).** Make all four edits: comment the `runlore` entry, its comment:
  "RunLore's session switch (RK15): for a demo session, uncomment this entry, list
  `externalsecret-webhook-runlore.yaml` under `resources`, run `gen-webhook-egress.py --write` and list
  `- path: network-policy-webhooks-patch.yaml` under `patches` (runbook 25), together with the host's three
  places"; move `externalsecret-webhook-runlore.yaml` out of `resources` into a comment beside it (the
  file stays); **delete** `network-policy-webhooks-patch.yaml` and keep no `patches:` line for it. Then run
  `python3 scripts/ci/gen-webhook-egress.py` (no `--write`): it must not FAIL, and Step 4's suites again:
  PASS.

```bash
git add infrastructure/aws-0/room-broker infrastructure/gcp-0/room-broker/config.yaml scripts/ci/tests/test-room-broker-suspend.py
git commit -m "feat(room-broker): RunLore's webhook subscriber on aws-0, a session switch, with the monitor verdict"
```

### Task 5: The internal principal on aws-0

**Files:**
- Create: `tooling/aws-0/agent-factory/helm-values-internal.yaml`, `tooling/aws-0/agent-factory/externalsecret-sponsored.yaml`
- Modify: `tooling/aws-0/agent-factory/kustomization.yaml`

- [ ] **Step 1: The values.** A ConfigMap `agent-factory-helm-values-internal` whose `values.yaml`
  sets `config.api.projectIDFile: /etc/agent-factory-sponsored/project-id` and
  `config.api.internalPrincipals` to the Global Constraints' entry, with
  `clientIDFile: /etc/agent-factory-sponsored/runlore-client-id`. Its comment carries gcp-0's dollar
  note and "declared on aws-0, inert while RunLore is off (K9)".
- [ ] **Step 2: The secret.** `agent-factory-sponsored` in `agent-system` from `agents-secrets`:
  `runlore-client-id` and `project-id`, both from `runlore-principal`.
- [ ] **Step 3: The patch.** aws-0's kustomization lists both files and appends the ConfigMap to the
  HelmRelease's `valuesFrom`, as gcp-0's does for `agent-factory-helm-values-sponsored`.
- [ ] **Step 4: Run**: `python3 scripts/ci/tests/test-factory-interfaces-off.py`, then
  `kustomize build tooling/aws-0/agent-factory | yq 'select(.kind=="ConfigMap" and .metadata.name=="agent-factory-helm-values-internal") | .data["values.yaml"]' | yq '.config.api.internalPrincipals[0].publishStarts'`
  prints `true`.

```bash
git add tooling/aws-0/agent-factory
git commit -m "feat(agent-factory): RunLore's internal principal on aws-0, publish starts its fix"
```

### Task 6: `alert-rules` in shadow; RunLore's curation values

**Files:**
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml:51-56`
- Modify: `observability/base/agent-platform/vmrule-agent-factory.yaml:51`, `observability/base/agent-platform/grafana-dashboard-agent-factory.yaml:88`
- Modify: `observability/base/runlore-factory/helm-values-configmap.yaml:30-60`
- Test: `scripts/ci/tests/test-runlore-factory-values.py`, `scripts/ci/tests/test-agent-class-paused-alert.sh`

`test-agent-class-paused-alert.sh:19-30` derives the live classes of `Smana/cloud-native-ref` (not shadow,
and live or monitored) and requires both `AgentFactoryClassPausedLong`'s regex and the dashboard's "Classes
paused" panel to select exactly that set. `alert-rules` has a monitor today, so it is in the set; once it
is shadow the set is `docs-links|revert`, and the suite fails until the rule and the panel follow.

- [ ] **Step 1: Write the failing assertions** in `test-runlore-factory-values.py`:

```python
cur = values["config"]["factory"]["curation"]
check("curation defers", cur == {"defer": True, "window": "7d"})
fu = classes["alert-rules"]["monitor"]["followUpWindow"]
check("the window covers alert-rules' follow-up", hours("7d") > hours(fu))
check("alert-rules is shadow, nothing armed", classes["alert-rules"].get("shadow") is True and "live" not in classes["alert-rules"])
```

`hours` parses `Nd`/`Nh`/`Nm`; `classes` is cloud-native-ref's block of the factory values. In
`test-agent-class-paused-alert.sh`, move the `alert-rules` fixture series (line 50) to the shadow group
(`1x11600`, paused 8 days) so the test proves a paused shadow class never fires.
- [ ] **Step 2: Run**: `python3 scripts/ci/tests/test-runlore-factory-values.py`; FAIL on `curation`. Make
  the `alert-rules` change of Step 3 alone, run `bash scripts/ci/tests/test-agent-class-paused-alert.sh`;
  FAIL "alert regex ... != live classes".
- [ ] **Step 3: The values.** `curation: {defer: true, window: 7d}` under `factory:` with one line
  "RK5: an accepted incident is drafted once verified; 7d covers a publish, a merge and the
  follow-up". `alert-rules: {shadow: true, …}`, its comment: "shadow since RK15: decisions recorded,
  a maintainer merges". In `vmrule-agent-factory.yaml:51` and `grafana-dashboard-agent-factory.yaml:88` change
  `class=~"docs-links|revert|alert-rules"` to `class=~"docs-links|revert"`, and say so in the commit.
- [ ] **Step 4: Replay the config through `vL1`.** Render RunLore's chart at `vL1` with the host's values and
  this overlay's `runlore-factory-values` (the procedure in the host's `helmrelease.yaml:93-95`), and load the
  result through `vL1`'s own `config.Load`. Expected: no error, with `window: 7d` parsed. An unknown key
  crashloops RunLore (`KnownFields`), and the dict check of Step 1 cannot see it.
- [ ] **Step 5: Run**: `python3 scripts/ci/tests/test-runlore-factory-values.py && bash scripts/ci/tests/test-agent-class-paused-alert.sh`;
  PASS. **Commit**

```bash
git add tooling/base/agent-factory/helm-values-configmap.yaml observability/base/runlore-factory/helm-values-configmap.yaml observability/base/agent-platform/vmrule-agent-factory.yaml observability/base/agent-platform/grafana-dashboard-agent-factory.yaml scripts/ci/tests/test-runlore-factory-values.py scripts/ci/tests/test-agent-class-paused-alert.sh
git commit -m "feat(runlore-factory): RunLore drafts verified entries; alert-rules in shadow, out of the paused-class alert"
```

### Task 7: The internal triager reads the knowledge base

**Files:**
- Modify: `infrastructure/base/agent-gateway/mcp.yaml:48-60` (targets), `infrastructure/base/agent-gateway/network-policy.yaml:120-135`
- Modify: `infrastructure/base/agent-gateway/profiles/triager.internal.yaml`
- Test: `scripts/ci/tests/test-gen-capabilities.py`, `scripts/ci/tests/test-agent-mcp-scope.sh`, `scripts/ci/tests/test-agent-capabilities-wire.sh`

`test-agent-mcp-scope.sh` pins the backend's exact target names (`:92-107`, against the public set), every
route's granted tools per audience (`EXPECTED_ROLE_TOOLS`, `:118-141`, where `agent-router.triager.internal` has no
`runlore-kb`) and each profile's grants (`:150-160`). The new target, profile entry and generated expression
fail all three until the suite names them. `scripts/ci/flux-schema/assert-agent-gateway.py` needs no change,
read in full for this: its grammar takes `runlore-kb` and `kb_search` (`[a-z0-9-]+`, `[a-z0-9_]+`), AG4 only checks
targets that inject a key (this one has none), and AG8 already requires `failureMode: FailOpen`; it runs inside
`validate-manifests.sh`.

- [ ] **Step 1: Write the failing assertions** in `test-gen-capabilities.py`:

```python
exprs = rendered_expressions("internal")  # the internal listener's policy items
check("the internal triager reaches runlore-kb's two tools",
      any('"runlore-kb"' in e and 'kb_search' in e and 'kb_get' in e and '"triager"' in e for e in exprs))
check("no other profile names runlore-kb",
      not any('"runlore-kb"' in e and '"triager"' not in e for e in all_expressions()))
check("no public listener names runlore-kb", not any('"runlore-kb"' in e for e in rendered_expressions("public")))
```

  And in `test-agent-mcp-scope.sh`, written first as well: add `"runlore-kb": {"kb_search", "kb_get"}` to both
  `EXPECTED_BACKEND_TOOLS["agent-mcp-public"]` and `["agent-mcp-internal"]` (the target set is one list for both
  routes and `names` is compared against the public entry, so the public entry names the target; its value is
  documentation, grants come from `EXPECTED_ROLE_TOOLS`); define
  `_TRIAGER_INTERNAL = {**_FULL_READER_INTERNAL, "runlore-kb": {"kb_search", "kb_get"}}` and use it for
  `"agent-router.triager.internal": with_room(_TRIAGER_INTERNAL, "triager")` only, leaving every other audience
  without the target. Add one assertion beside the backend checks:

```python
    if any(t["name"] == "runlore-kb" for t in mcp["targets"]) and mcp.get("failureMode") != "FailOpen":
        errors.append("agent-mcp backend: failureMode must stay FailOpen while runlore-kb is a target (a down RunLore drops its own tools only)")
```

- [ ] **Step 2: Run**: `python3 scripts/ci/tests/test-gen-capabilities.py && bash scripts/ci/tests/test-agent-mcp-scope.sh`; FAIL.
- [ ] **Step 3: The target, the tools, the egress.** In `mcp.yaml` after `mcp-victorialogs`:
  `{name: runlore-kb, static: {host: runlore.runlore.svc.cluster.local, port: 8080, path: /mcp, protocol: StreamableHTTP}}`,
  commented "RunLore's read-only knowledge (RK12), the host's Service (H8); public text, no token (K10)". The profile gains
  `runlore-kb: [kb_search, kb_get]`. The gateway's CNP gains an egress rule to
  `{io.kubernetes.pod.namespace: runlore, app.kubernetes.io/name: runlore}` on 8080/TCP. Then
  `python3 scripts/ci/gen-capabilities.py --write`.
- [ ] **Step 4: Run**: `python3 scripts/ci/tests/test-gen-capabilities.py && bash scripts/ci/tests/test-agent-mcp-scope.sh && bash scripts/ci/tests/test-agent-capabilities.sh && bash scripts/ci/tests/test-agent-capabilities-wire.sh`;
  PASS, and `python3 scripts/ci/tests/flux-schema/test-assert-agent-gateway.py` still PASS. The wire suite
  runs a fake `flux-operator-mcp` and lists only its tools; it does not exercise `runlore-kb`, an unresolvable
  `runlore` host or the other servers' tools, so Review Focus 1 rests on the `failureMode` assertion above and on
  live 2's check that the internal triager's run names `runlore-kb_kb_search`. **Commit**

```bash
git add infrastructure/base/agent-gateway scripts/ci/tests/test-gen-capabilities.py scripts/ci/tests/test-agent-mcp-scope.sh
git commit -m "feat(agent-gateway): the internal triager reads RunLore's knowledge base (kb_search, kb_get)"
```

### Task 8: The measures

**Files:**
- Create: `scripts/ops/kb-measures.py`, `scripts/ci/tests/test-kb-measures.py`, `scripts/ci/tests/kb-measures-fixtures/{stubs,events,kb-prs}.json`

**Interfaces:**
- Produces: `python3 scripts/ops/kb-measures.py --since YYYY-MM-DD [--until YYYY-MM-DD] [--fixtures DIR]`
  (reads GitHub through `gh api` and the caller's own `gh` authentication: no token on a command line or in
  the script),
  printing one Markdown table: incidents, human touches per incident (median, max), KB PRs opened,
  merged, closed, open at the end, the oldest open's age in days. `measures(stubs, events, kb_prs) -> dict`.

- [ ] **Step 0: Name RunLore's origin.** Read one real RunLore stub from the first runbook 20 session
  (`gh issue list -R Smana/cloud-native-ref -l factory/proposed -L 20 --json number,title,body,author`) and put
  what marks it as RunLore's (not the follow-up's title prefix, which is the exclusion) in one constant of the
  script; the fixture copies the shape.
- [ ] **Step 1: Write the failing test.** Fixtures: two stubs; on the first, `factory/publish` by
  `Smana` and the fix merged by `Smana`; on the second, `factory/proposed` by `factory-app[bot]`,
  `factory/publish` by `Smana`, the fix merged by `merger-app[bot]`; three KB PRs, one merged by `Smana`; a third `factory/proposed` issue that is a follow-up (title
`RunLore: the fix in #11 did not hold (X)`) and a fourth that is not RunLore's.

```python
m = kb.measures(stubs, events, kb_prs)
check("touches per incident", m["touches"] == {"median": 1.5, "max": 2})
check("a bot's label is not a touch", m["touches_by_incident"]["#2"] == 1)
check("kb counts", (m["kb_opened"], m["kb_merged"], m["kb_open_end"]) == (3, 1, 2))
check("a follow-up and a foreign stub are not incidents", m["incidents"] == 2)
```

- [ ] **Step 2: Run**: `python3 scripts/ci/tests/test-kb-measures.py`; FAIL (`No module named`).
- [ ] **Step 3: Implement `measures`** and the `gh api` reads behind `--fixtures`: stubs are
  `Smana/cloud-native-ref` issues labelled `factory/proposed` by the factory's App in the window; the
  fix is the issue the stub's `factory/publish` comment links; a follow-up (the title prefix) and a
  stub without RunLore's origin are skipped; an actor is a bot when its `type` is
  `Bot` or its login ends `[bot]`. KB PRs are `Smana/runlore-kb`'s, labelled `runlore`.
- [ ] **Step 4: Run**: PASS. **Commit**

```bash
git add scripts/ops/kb-measures.py scripts/ci/tests/test-kb-measures.py scripts/ci/tests/kb-measures-fixtures
git commit -m "feat(ops): kb-measures, human touches per incident and the knowledge queue from GitHub"
```

### Task 9: Runbook 25, the README, the PR

**Files:** Create `docs/runbooks/agent-factory/25-runlore-kb-phase-1.md`; modify
`docs/runbooks/agent-factory/README.md` (a row after row 24, and line 20's session-switch row), the spec's status line.

- [ ] **Step 1: Runbook 25**, after runbook 20's shape. Every command that runs `lore` in the pod passes
  `--config /etc/runlore/runlore.yaml` (the default `runlore.yaml` is a path relative to a working directory the
  image does not set).

  0. **Prerequisites, once.** The `runlore` machine user's keys mirrored to OpenBao (the cloud-native-ref plan's
     Task 6 command, before the first session); the webhook key seeded in both mounts as runbook 14 does (the
     ExternalSecret is in the off state's comment, so nothing syncs until the switch); the KB repository's
     `Knowledge queue` issue absent or closed; and the three labels created, because RunLore adds a label
     without creating it and GitHub creates none on first use:
     `gh label create ready-to-merge -R Smana/runlore-kb`, `runlore-queue`, `runlore-resolve`, the same way.
     The ai-native-ref release carrying PR 4 is cut (the owner's decision) and the host pins it (PR 4b).
  1. **Switch on, in this order** (RK15). The subscriber must not exist while RunLore is off: three failed
     deliveries disable it for good. (a) A PR here makes aws-0's four edits (K9): the entry, the ExternalSecret in
     `resources`, `gen-webhook-egress.py --write`, the `patches:` line; the owner cuts the release. (b) One host
     PR carries the three places (the `# - ../base/runlore` line, the Alertmanager route, `runlore.yaml` and
     `runlore-spend.yaml`) **and** the new ai-native-ref tag and digest. No Flux dependency orders the two halves;
     what holds is that nothing delivers until a room event, so run no factory task, and seed nothing, until
     `kubectl -n runlore wait --for=condition=Ready pod/runlore-0` returns. (c) Check `RoomWebhookDisabled` is
     silent. If a delivery failed and the subscriber was disabled, bump `generation` in aws-0's `runlore` entry
     and say so in the PR.
  2. **Live 1.** A restart of `runlore-0` mid-soak keeps the soak: the Lease `runlore-leader` still exists with one
     holder (the holder identity is `<pod>_<podIP>` and changes with the pod's IP: do not compare it), there is
     one replica, and `factory.jsonl` on the volume still lists the soak. After a previous session's switch-off its
     ledgers are still there.
  3. **Live 2.** A seeded `vector(1)` rule, one `factory/publish`, `alert-rules` in the stub task's
     `status.published.class`, the owner's merge, `room.monitor_verdict` in RunLore's log, one KB PR labelled
     `ready-to-merge` whose `resolution` names the fix (the label lands from RunLore's curation pass on the
     verified generation, not from a sweep). `kubectl -n agent-system logs` of the internal triager's run, or the
     run's transcript, names `runlore-kb_kb_search`: the triager reached the knowledge base.
  4. **Live 3** = runbook 20's live 5, then the verified generation completes the entry. The next generation
     waits for Alertmanager's repeat, which the `runlore` route sets to 1h.
  5. **Live 4, the replay (RK17).** `kubectl -n runlore exec runlore-0 -- lore kb resolve --config /etc/runlore/runlore.yaml …`
     on #157 to #163 with CNR #2638 and #2659. It exercises the entry path only: it writes no outcome event, so
     #157 to #163 stay `unverified` under Decide and RK17's test of the outcome join is not exercised (K13). Then
     `kubectl -n runlore exec runlore-0 -- lore curate queue-issue --config /etc/runlore/runlore.yaml` writes the first
     queue issue listing the backlog (the schedule is empty, so nothing else does); record live 4. CNR PR 3b (`stale_after: 720h`)
     merges after the session's switch-off, not during it: a restart at `720h` would make its first sweep a full
     interval later and the session would not see it.
  6. **Clear the queue while RunLore is on**: a human merge conflicts the next entry PR, and RunLore's
     refresh of entry PRs (RunLore plan, the refresh task) rebuilds it only while it runs.
  7. **Switch off, in this order** (RK15, the reverse): `lore curate queue-issue --config …` again to list what
     is left; the owner clears the queue; `queue-issue` once more; then the subscriber off (a PR here, the four
     edits reversed per K9, a release, the host pin); then the host PR with the three places off. The volume stays.
  8. **Time.** Budget about 5h a session: a `healthy` verdict needs the 2h `followUpWindow` plus about 5m of
     search lag, read at most every 10m, so about 2h15 after the merge before live 2's entry; live 3 waits one
     Alertmanager repeat (1h); each flip is a PR here, a release and a host PR.
  9. **The phase 1 gate**, read after each session: `python3 scripts/ops/kb-measures.py --since <session start>`, three
     sessions in a row whose queue was cleared before the next one; RK20 from the first session: `D`, its highest
     daily `runlore:investigation_cost_usd:increase1d`, for CNR PR 3c, and the provider's monthly limit
     set at 1.5 × `D` × the session days expected in a month; the results recorded in the status record.
- [ ] **Step 2: The README.** A row after row 24: proves live 1–4 and the phase 1 gate; needs the owner's go,
  the ZITADEL sync, the seeded keys, the labels, two releases and two host pins per flip; about 5 h a session,
  three sessions for the gate. In line 20's "Session switches" row, name RunLore's two halves: the host's three
  places and aws-0's `runlore` subscriber ([25](25-runlore-kb-phase-1.md)).
- [ ] **Step 3: `task check`** green, `pre-commit run --all-files`, the PR.

```bash
git add docs/runbooks/agent-factory/25-runlore-kb-phase-1.md docs/runbooks/agent-factory/README.md docs/superpowers/specs/2026-11-03-runlore-kb-from-the-factory-design.md
git commit -m "docs(runbooks): 25, RunLore's knowledge base, phase 1 on aws-0"
```

---

## PR 6: `Smana/runlore-kb` adopted (phase 2)

### Task 10: The fence file and the policy

**Files** (in `Smana/runlore-kb`): Create `.github/agent-factory.yaml`, `.policy.yml`.

- [ ] **Step 1: The owner installs** the factory's App and policy-bot on `Smana/runlore-kb`
  (runbook 12's adoption steps for a repository).
- [ ] **Step 2: The fence**: `.github/agent-factory.yaml` naming `aws-0`, the content
  `Smana/cloud-native-ref`'s holds.
- [ ] **Step 3: The policy**: `.policy.yml` with one approval rule, `low-risk: kb-entries`, admitting
  a RunLore entry PR (one added `incidents/*.md`, `index.md` and `log.md` modified) from `runlore[bot]`
  on a `runlore/kb-` branch, labelled `ready-to-merge`; every other PR needs a maintainer's approval.
  A human-authored gate-path PR, as AM12 requires.
- [ ] **Step 4: The validator**: branch protection on `main` requires the `validate` check of
  `.github/workflows/validate-kb.yml`. Its `lore@v0.10.0` already passes the new frontmatter
  (`origin`, `resolution`): the loader ignores unknown keys (RunLore plan KP11).

## PR 7: the `kb-entries` class in shadow (phase 2)

### Task 11: Pin `vK2`; the third repository

**Files:**
- Modify: the Maku pin sites; `tooling/base/agent-factory/helm-values-configmap.yaml` (a
  third entry under `repositories`); `scripts/ci/tests/test-agent-merge-gate-parity.py`
- Create: `scripts/ci/tests/test-kb-class-shadow.py`

Two suites read every repository of the config and break on a third: `test-agent-merge-gate-parity.py:30,80-81`
builds `POLICY` for two repositories and does `POLICY[r["name"]]` (`KeyError: 'Smana/runlore-kb'`), and
`test-agent-factory-pins.py:53-58` requires `merge.approveToMerge is True` and `merge.breaker.recoverAfter == 3` on
each (`KeyError: 'merge'` for an entry with no `merge` block). Maku's own validation
(`internal/factory/config/config.go:1499,1503-1507,1566-1600`) refuses an entry with no `triggerLabel`, no
`docs-links` and `revert` classes, or a shadow class and no full `merge` block with `leakScanCheck` in both check
lists. So the entry is the full one.

- [ ] **Step 1: Write the failing suite**:

```python
kb = next(r for r in repos if r["name"] == "Smana/runlore-kb")
c = kb["classes"]["kb-entries"]
check("kb-entries is shadow", c.get("shadow") is True and "live" not in c)
check("a RunLore entry PR's shape", (c["diffShape"], c["allowedFiles"], c["companionFiles"]) ==
      ("added-entry", [r"^incidents/[^/]+\.md$"], [r"^index\.md$", r"^log\.md$"]))
check("runlore[bot]'s labelled PRs only", c["author"]["adopt"] == {"logins": ["runlore[bot]"], "branches": ["^runlore/kb-"]}
      and c["requiredLabel"] == "ready-to-merge")
check("the validator holds", c["holdoutChecks"] == ["validate"])
check("five a day at most", c["maxPerDay"] == 5)
check("the classes the factory requires, all shadow", set(kb["classes"]) == {"kb-entries", "docs-links", "revert"}
      and all(cl.get("shadow") is True and "live" not in cl for cl in kb["classes"].values()))
m = kb["merge"]
check("the merge block the factory's validation needs",
      kb["triggerLabel"] == "factory/ready" and m["requiredChecks"] == ["validate"] and m["verifyChecks"] == ["validate"]
      and m["leakScanCheck"] == "validate" and m["approveToMerge"] is True and m["autoMergesPerDay"] == 5
      and m["breaker"] == {"window": 10, "maxReverts": 1, "maxFollowUps": 1, "recoverAfter": 3})
```
- [ ] **Step 2: Run**: FAIL (`StopIteration`). Also run `python3 scripts/ci/tests/test-agent-merge-gate-parity.py` and
  `python3 scripts/ci/tests/test-agent-factory-pins.py` on the Step 3 tree before the parity change to see their
  `KeyError`.
- [ ] **Step 3: Pin `vK2`** as Task 2, with the grep `'added-entry|companionFiles|requiredLabel'` in `"v$V" -- internal/factory/config`
  (those keys do not exist before Maku PR 5: `DiffShapes()` is links-only and semver); **stop and report** if it
  finds nothing. Then the entry: `name: Smana/runlore-kb`, `maintainers: [Smana]`, `triggerLabel: factory/ready`,

```yaml
          classes:
            docs-links: {shadow: true, holdoutChecks: [validate]}
            revert: {shadow: true, holdoutChecks: [validate]}
            kb-entries:
              shadow: true
              author: {adopt: {logins: ["runlore[bot]"], branches: ["^runlore/kb-"]}}
              diffShape: added-entry
              allowedFiles: ['^incidents/[^/]+\.md$']
              companionFiles: ['^index\.md$', '^log\.md$']
              requiredLabel: ready-to-merge
              holdoutChecks: [validate]
              maxPerDay: 5
          merge:
            requiredChecks: [validate]
            verifyChecks: [validate]
            policyBotLogin: ogenki-merge-gate[bot]
            mergerLogin: ogenki-agent-merger[bot]
            autoMergesPerDay: 5
            fixRuns: 1
            checkReruns: 0
            verifyFor: 30m
            revertWindow: 168h
            # Owner note (K12): the knowledge base is public text with secret redaction at each tool
            # output (RK13) and has no leak scan of its own; `validate` stands in, in both lists above.
            leakScanCheck: validate
            awaitingCIFor: 24h
            approveToMerge: true
            breaker: {window: 10, maxReverts: 1, maxFollowUps: 1, recoverAfter: 3}
```

  (the Maku plan's Task 8 values for `kb-entries`), with the comment "RK3: RunLore drafts, the merge gate merges
  verified entries; shadow until 20 decisions (K8)".
- [ ] **Step 4: The parity suite.** In `test-agent-merge-gate-parity.py`, read the policy with `POLICY.get(name)` and skip
  the comparison for a repository whose policy file is not in this tree, with the comment "its fence is checked by that
  repository's own `.policy.yml` (Task 10)"; leave `FENCE` as it is, since no policy of `Smana/runlore-kb` is here to hold
  `companionFiles` against.
- [ ] **Step 5: Replay through `vK2`'s config loader.** Render the factory's values (`yq` of the ConfigMap's `values.yaml`
  `.config`) into a file, check out Maku at `vK2` in a scratch worktree, and load the file with
  `config.Load(path)` (`internal/factory/config/config.go:1043`) from a throwaway `main` under that worktree (an
  `internal` package is importable inside the module). Expected: no error. The suites never load the values
  through Maku, so this is the only check that its validation accepts the entry.
- [ ] **Step 6: Run** `python3 scripts/ci/tests/test-kb-class-shadow.py`, `python3 scripts/ci/tests/test-agent-factory-pins.py`,
  `python3 scripts/ci/tests/test-agent-merge-gate-parity.py`, `bash scripts/ci/tests/test-agent-class-paused-alert.sh`
  (its non-host-repository guard needs the new repository to have no live class) and `task check`: PASS. **Commit**,
  the PR.

```bash
git add flux tooling infrastructure observability website scripts/ci/tests/test-kb-class-shadow.py scripts/ci/tests/test-agent-merge-gate-parity.py
git commit -m "feat(agent-factory): Maku vK2; runlore-kb's kb-entries class in shadow"
```

- [ ] **Step 7: After the release and PR 7b.** Once the owner has cut the ai-native-ref release carrying this PR and the
  host pins it, the factory's log on aws-0 names `Smana/runlore-kb` fenced to `aws-0` (the factory reads only the
  repositories it lists, so this cannot pass before PR 7).

## Gate

The spec's offline proof 8 and live proofs 1 to 4 (runbook 25), then the phase 1 gate (three
sessions in a row whose queue was cleared before the next one; the seven showcase entries merged;
live 3 passed). Phase 2's gate (20 shadow decisions, none a "would merge" on an entry a human closed,
the threat check) is read from the factory's shadow record after each session and recorded in the
status record.
