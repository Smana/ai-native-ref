# 28 — AWS v4 feature validation and the two screencasts

Runs the [approved campaign](../../superpowers/specs/2026-11-16-v4-aws-validation-design.md) on
aws-0. It validates shipped workflows and merge policies, performs targeted adjacent regression, and
records the two screencasts from issue #394. Record every result in
[results-aws-0-2026-11-16.md](results-aws-0-2026-11-16.md); the residual cases run after it are in
[results-aws-0-2026-11-17-residuals.md](results-aws-0-2026-11-17-residuals.md).

The separate [workflow comparison](32-workflow-comparison.md) is out of scope. Do not enable its
`evaluation` overlay, file repeated tasks for a cohort, raise a budget, or tag a release.

## 1. Rules and evidence

- Use one fixed ai-native-ref `origin/main` SHA and its released Maku, host and image pins. A fix
  lands by PR; record the new SHA and rerun the failed test and its adjacent checks.
- Use real, small ai-native-ref defects for successful paths. Use synthetic inputs for ambiguity,
  stalls, invalid configuration and boundary cases. Keep issue text under `$DRILL_DIR`, never in a
  checkout an agent can read.
- A foundation failure stops the campaign. A workflow or policy failure pauses its dependent cases;
  continue independent cases. Record raw output and links before fixing anything.
- Unsafe diffs stay unmerged. The only autonomous chain is M8, and only after its evidence gate
  passes. Existing production caps remain unchanged.
- The operator may execute every approved step without another checkpoint. Pause for missing
  credentials, a budget increase, an unexpected effect outside the test, or teardown.

## 2. Baseline, bootstrap and foundation gates (B1–B8)

### 2.1 Set and record the baseline (B1)

Use a cloud-native-ref checkout for host commands and an ai-native-ref checkout at the selected SHA:

```bash
export CLOUD=aws
export HOST_DIR="$HOME/Sources/cloud-native-ref"
export AI_NATIVE_REF_DIR="$HOME/Sources/ai-native-ref"
export TARGET_REPO=Smana/ai-native-ref
export DRILL_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/v4-aws-validation"
mkdir -p "$DRILL_DIR"

git -C "$AI_NATIVE_REF_DIR" rev-parse HEAD
git -C "$AI_NATIVE_REF_DIR" status --short --branch
git -C "$HOST_DIR" rev-parse HEAD
git -C "$AI_NATIVE_REF_DIR" show HEAD:HOST_REF
```

Expected: one clean ai-native-ref checkout at the intended `origin/main` SHA. Record the SHA, host
commit and the artifact and image versions actually reconciled. Do not start from a dirty or moving
checkout.

Bootstrap aws-0 with the host's AWS rebuild procedure, then complete
[runbook 00](README.md#runbook-00-one-time-cluster-setup) and
[the aws-0 resume prerequisites](../../../clusters/aws-0-agent-platform/README.md#resume). Do not
resume or reseed gcp-0.

### 2.2 Health and released pins (B2–B3)

```bash
cd "$HOST_DIR"
flux get kustomizations -n flux-system
flux get helmreleases -A
kubectl get pods -n agent-system -o wide
kubectl get factories,repositories,mergepolicies -n agent-system
kubectl get secretstore -n agent-system agents-secrets \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
kubectl get factory -n agent-system aws-0 \
  -o jsonpath='{.spec.evaluation}{"\n"}'
kubectl get deploy -n agent-system \
  -o custom-columns='NAME:.metadata.name,IMAGES:.spec.template.spec.containers[*].image'
maku preflight --namespace agent-system --strict --json | tee "$DRILL_DIR/preflight.json"
```

Expected: every required release and workload Ready; the SecretStore prints `True`; all Factory,
Repository and MergePolicy objects are accepted and synchronized; `spec.evaluation` is empty; the
strict live preflight passes with no failed check. Record the deployed digests and preflight output.
A missing owner key, an unready foundation object, a failed preflight, or a nonempty evaluation
overlay stops the campaign.

### 2.3 Identity, sandbox and network (B4)

Run the targeted checks in [runbook 01](01-runtime-sandbox.md) and
[runbook 03](03-egress.md) against the first validation run. On its Task, capture the run ID and
read the runtime and access shape without printing a token:

```bash
kubectl get task -n agent-system "$TASK" -o json \
  | jq '{workflow: .status.profile.name, phase: .status.phase, runs: [.status.runs[] | {id, role, phase}]}'
kubectl get agentrun -n agents "$RUN" -o yaml > "$DRILL_DIR/$RUN-agentrun.yaml"
kubectl get pod -n agents "$RUN" -o jsonpath='{.spec.runtimeClassName}{"\n"}'
kubectl get networkpolicy -n agents
```

Expected: the run uses gVisor, its own ServiceAccount and short-lived git/model credentials, and the
run's default-deny network policy. The positive broker and proxied-GitHub checks pass; direct
GitHub, the API server and broker metrics from the sandbox are denied. Never paste a credential into
the report.

### 2.4 Settings as objects (B5)

Prove a harmless live edit, a refused edit and Git restore. Use the current object names from B3 if
they differ.

1. Change only `Factory.spec.workflows.standard.description` with a merge patch. Confirm the next
   plan reads the new description without a factory restart, then restore it through Flux:

   ```bash
   kubectl patch factory -n agent-system aws-0 --type=merge \
     -p '{"spec":{"workflows":{"standard":{"description":"An implementer and a reviewer. Validation edit."}}}}'
   flux reconcile kustomization agent-factory-resources -n flux-system --with-source
   ```

2. Apply a semantically invalid repository default. The API accepts the string; the factory must
   refuse the object and keep serving the last good configuration:

   ```bash
   kubectl patch repository -n agent-system ai-native-ref --type=merge \
     -p '{"spec":{"workflow":{"default":"not-a-workflow"}}}'
   kubectl get repository -n agent-system ai-native-ref -o yaml
   ```

   Expected: an accepted/refused condition names the invalid workflow; a new plan still offers
   `standard`. If intake loses the last good configuration, stop and restore immediately.

3. Restore and verify:

   ```bash
   flux reconcile kustomization agent-factory-resources -n flux-system --with-source
   kubectl get repository -n agent-system ai-native-ref \
     -o jsonpath='{.spec.workflow.default}{"\n"}'
   ```

   Expected: `standard`, Accepted True, and no restart.

### 2.5 Intake, checks, observability and cost (B6–B8)

1. Configure the recording client: `maku setup opencode`, then `maku doctor`. Expected: every line
   `ok`; OpenCode lists the six current tools (`handoff`, `start`, `inbox`, `task`, `wait`,
   `answer`). Complete the GitHub account link before using private-tailnet pages.
2. Run the complete L1–L17 sequence in [runbook 27](27-six-tools-and-slack-acts.md): clean client
   setup, six tools, coding-agent and Slack intake, task decisions, the four Slack transitions and
   edited end line, stop/retry/answer, removed tools, confirmation ownership, maintainer and
   non-maintainer behavior, and unlinked-user refusal. Reuse its tasks elsewhere only when their
   workflow and diff fit the other test. Missing second-person or unlinked accounts block the
   affected rows; they do not justify skipping the authorization assertion.
3. On one standard and one careful PR, confirm the repository's checks run before the gate and the
   gate status explains its decision. Read the Agents overview, room, run and factory dashboards for
   the same time window; the required VMRules are loaded and no campaign alert is firing.
4. Compare the terminal task card, room and Grafana with the Task's settled cost. Expected: one
   consistent total after settlement, a per-role breakdown, and the charged human or Slack
   identity. Do not judge moving interim totals as final.

### 2.6 RunLore knowledge search (B9)

The live-only `kb_search` proof needs an existing reviewed knowledge entry and an internal triager
run. Follow [runbook 25](25-runlore-kb-phase-1.md)'s prerequisites and live 2 only as far as that
entry and triager require; the other RunLore phases and its full phase gate are out of scope.

Expected: the triager's tool list includes `kb_search`; a real call returns the entry; the room's
tool event names `room-broker__kb_search`; and
`maku_rooms_knowledge_calls_total{tool="kb_search",outcome="ok"}` increases. An `upstream_error` or
`timeout` is a failure. Record the triager run and the reviewed entry, not the entry's confidential
contents.

## 3. Test input and lookup helpers

Write each issue body to `$DRILL_DIR/<test>.md`. Include one observable `Acceptance:` line for every
successful implementation task. Reword inherited drills and do not call them a test in the text the
agent reads.

Create and start an issue:

```bash
issue_url=$(gh issue create -R "$TARGET_REPO" --title '<one real defect>' \
  --body-file "$DRILL_DIR/<test>.md" --label factory/ready)
issue=${issue_url##*/}
printf '%s\n' "$issue_url"
```

Add exactly one maintainer workflow pin only where the test requires it:

```bash
gh issue edit "$issue" -R "$TARGET_REPO" --add-label workflow:quick
```

Find the newest Task for the issue and inspect its chain:

```bash
TASK=$(kubectl get tasks -n agent-system -o json | jq -r --argjson n "$issue" \
  '[.items[] | select(.spec.issue == $n and .spec.repository == "Smana/ai-native-ref")] |
   sort_by(.metadata.creationTimestamp) | last | .metadata.name')
kubectl get task -n agent-system "$TASK" -o json \
  | jq '{workflow: .status.profile.name, tier: .spec.tier, phase: .status.phase,
         reason: .status.reason, profile: .status.profile,
         runs: [.status.runs[] | {id, role, phase}]}'
```

Expected: the selected workflow and roles match the test. Record the issue, Task, room, runs and PR.
An empty `TASK` after one intake poll is a failure, not a passing refusal.

## 4. Workflow acceptance (W1–W8)

Run W1, W2 and W3 on separate genuine defects of suitable complexity. W2's defect must change prose
in `website/content/` so W6 can reuse its PR. Do not file the same defect twice for a measurement.

| ID | Do | Passes when |
|---|---|---|
| W1 | File a normal issue with `factory/ready` and no workflow or class label | Repository default selects `standard`; one implementer and at most two review rounds run; the standard tier and checks apply |
| W2 | File a small mechanical issue, then apply `workflow:quick` as a maintainer | One implementer and no reviewer run; no scoper, judge or search child appears; the quick task keeps its shipped tier ceiling |
| W2-source | Observe one actual `ai-native-ref-dead-links` schedule task and one revert task | Their Tasks select `quick`; no label supplies the choice. A cron wait is acceptable; do not enable another schedule |
| W3 | Choose `careful` in the OpenCode confirmation for a wide or unclear real issue | Scoper, implementer with search, judge and reviewer run in order at the frontier ceiling; the tester runs only if the repository opted in |
| W3-judge | Use a careful task with two acceptance checks, the second easy to miss | A `not_yet` verdict continues the same bounded conversation, or a first-pass `met` is recorded and a second careful task exercises the continuation |
| W4 | Compare W1, W2 and W3's source, label and confirmation records | Each records the intended selection source; the plan's default is prefilled but may be changed by a maintainer |
| W5-legacy | File with `class:docs` and `profile:careful`, without a workflow label | The issue narrates that legacy labels are not read; the repository default still selects `standard` |
| W5-unknown | Apply `workflow:nope` as a maintainer | `profile_unknown` is narrated; the Task records the refused request and runs the repository default, never an invented workflow |
| W5-conflict | Apply two different `workflow:` labels as a maintainer | `profile_conflict` is narrated; no pin applies and the Task runs the repository default |
| W5-untrusted | Have a non-maintainer apply `workflow:careful` to an otherwise valid issue | `not_maintainer` is narrated and the Task runs the repository default, not careful. If no such actor is available, record BLOCKED rather than simulating the actor |
| W6 | Let W2's quick prose PR reach the merge gate | The `docs` policy's `considered=` entry is `reviewer_verdict_missing`; no autonomous merge occurs |
| W7 | Render each served repository with `maku repo add`, then run `maku repo check` | Every generated declaration is reviewable and every repository check passes; record the first ai-native-ref round-trip duration |
| W8 | Hand off one genuine `Smana/runlore-kb` issue from OpenCode | The plan names that repository and its workflow from the factory catalog; no broker-side repository list supplies a second answer |

For W5 refusals, a Task still exists and runs as if unpinned. Use the issue narration and
`status.profile.requested` / `status.profile.refused` as evidence; a refusal is not an intake or
Task failure.

For W7, write only into the evidence directory and never apply the generated files automatically:

```bash
for repo in Smana/ai-native-ref Smana/cloud-native-ref Smana/runlore Smana/runlore-kb; do
  name=${repo##*/}
  maku repo add "$repo" --out "$DRILL_DIR/onboarding/$name" --factory aws-0 --namespace agent-system \
    --factory-app ogenki-agent-factory --agents-app ogenki-agents
  maku repo check "$repo"
done
difft "$DRILL_DIR/onboarding/ai-native-ref/factory/repository-ai-native-ref.yaml" \
  "$AI_NATIVE_REF_DIR/tooling/base/agent-factory/resources/repository-ai-native-ref.yaml"
```

Expected: every `repo check` line PASS. Review each rendering difference against the platform's
intentional additions; a missing workflow, merge requirement or ownership fence is a failure. The
wizard writes and never applies.

## 5. Merge-policy acceptance (M1–M8)

### 5.1 Diff decisions and safety cases (M1–M6)

Reuse suitable workflow PRs. Create additional synthetic PRs only for boundaries not already covered.
Never merge an unsafe fixture.

| ID | Do | Passes when |
|---|---|---|
| M1 | Use an unlabelled task whose PR changes only a non-Markdown configuration comment outside every policy | Human hand-off with `no_policy_matched`; `considered=` names each evaluated policy's refusal |
| M2 | In a focused config PR, remove only ai-native-ref's shadow `docs` binding; run a genuine prose PR while it is unbound; restore the binding | The chart catalog still evaluates `docs` in shadow and records `shadow_would_arm` when all rows hold; no binding is required |
| M3-path | A PR touches both eligible prose and a protected `.github/` or `.policy.yml` path | `file_protected`; nothing auto-merges |
| M3-size | A PR exceeds the bound's file or line cap | The exact cap reason is recorded; nothing auto-merges |
| M3-shape | A links-only task adds a file, deletes one, or changes non-link prose | `file_added_or_deleted` or the shape refusal; no other policy silently takes over |
| M4-hold | Apply `factory/hold` to an otherwise eligible PR | `held`, before policy selection and without a shadow would-merge; removing it re-enters the same head |
| M4-approval | Approve the current head of a normal PR after its runs end | The merger performs the approved merge outside autonomous caps and records `mergedHow=approved` |
| M4-stale | Approve, then create a new head through the normal revision path | The old approval never merges the new head; the gate waits for approval of the current head |
| M5 | Inspect overlapping policy decisions during M2–M4, then observe M8's pause/cap | The strictest matching live policy is named; when paused or capped, the PR waits for a human and no looser live policy merges it |
| M6 | Read W2's decision, then compare a standard or careful prose PR | Quick records `reviewer_verdict_missing`; the reviewer-backed workflow supplies the verdict the shape-less `docs` policy requires |

Read each decision from the PR, its marker, and the Settings decision page. Expected: the same head,
policy, verdict and reason in all three. A disagreement is a failure in both the decision test and
M7.

### 5.2 Maintainer interfaces (M7)

Use the Settings link on the room list and Maku's current
[merge-policy guide](https://github.com/Smana/maku/blob/main/docs/merge-policies.md). Keep the
rendered factory configuration, resource bundle and repository file used by CLI checks together in
`$DRILL_DIR`; never hand-edit a copied policy to make results agree.

1. **Inspect:** open `/settings/merge-policies/Smana/ai-native-ref` and one decision. Expected:
   catalog and custom policies, mode, bounds, evidence and the same decision explanation as GitHub.
2. **Edit and validate:** in the editor, prepare a tighter shadow `docs` binding for
   `^website/content/.+\.md$`. Check it in guided and YAML modes. Expected: valid input produces a
   GitHub edit link; an unknown field and an unbounded policy name their locations and are refused.
   Open no PR unless the change is intended for M2 or a fix.
3. **Structural diff and simulation:** run the current commands against the saved configuration:

   ```bash
   maku policy diff --config "$DRILL_DIR/factory.yaml" --manifests "$DRILL_DIR/resources.yaml" \
     --repository "$TARGET_REPO" "$DRILL_DIR/policy-old.yaml" "$DRILL_DIR/policy-new.yaml"
   maku policy check --config "$DRILL_DIR/factory.yaml" --manifests "$DRILL_DIR/resources.yaml" \
     --repository "$TARGET_REPO" "$DRILL_DIR/policy-new.yaml"
   maku policy simulate --config "$DRILL_DIR/factory.yaml" --repository "$TARGET_REPO" \
     "$DRILL_DIR/policy-new.yaml" <Maku-checkout>/internal/factory/reconciler/testdata/conformance/*.json
   ```

   Expected: tightening/relaxation is correctly classified, `check` reports its migration meaning,
   and every applicable fixture agrees with the gate's evaluator. Record the exact Maku CLI version.
4. **Evidence and promotion:** open `/settings/evidence`, select ai-native-ref's `docs-links`, and
   compare its clean-decision count and drill state with the PR ledger. Set `MAKU_DIR` to a checkout
   at the deployed Maku tag and run the independent tally:

   ```bash
   bash "$MAKU_DIR/scripts/shadow-merge-tally.sh" --repo "$TARGET_REPO" --outcomes
   ```

   Expected: the `docs` and `docs-links` rows agree with the recorded shadow decisions. If eligible,
   prepare but do not bypass the maintainer promotion PR. If ineligible, the UI must say what is
   missing.
5. **Approval memory:** open `/settings/approval-memory` authenticated. Expected: the approval-memory
   page, not a 404. Then, only if a live policy has an eligible `requiresApproval` subset, exercise
   preview, save, use, audit and revocation through the UI and API. Otherwise record NOT APPLICABLE
   with the page and configuration proof; do not create an unsafe policy to force it.
6. **Authorization:** repeat one read and one write attempt with a linked non-maintainer. Expected:
   reads follow repository visibility; writes are refused server-side, not merely hidden in the UI.

### 5.3 The live safety chain (M8)

**Evidence gate.** M7's evidence view and ledger must prove ai-native-ref's `docs-links` eligible
under `evidence: low`, including its repository drill. If not, mark M8 BLOCKED and continue the
recordings. Do not lower the threshold, use a fixture repository, or make `revert` live just for
this campaign.

Before starting, confirm `main` is green, no unrelated task is active, today's autonomous cap has
room, and the merger rulesets permit the approved merge and revert. Record all values.

1. Create one real link-only ai-native-ref issue with `workflow:quick`; let its PR merge under
   `docs-links` without a GitHub approval. Expected: the reported head is merged by the merger App,
   `factory/auto-merged:docs-links` appears, and the Task verifies the merge.
2. Request a normal revert with `factory/revert`. **Do not add `factory/drill`**: this campaign
   intends the revert to exercise the breaker. If `revert` remains shadow, a maintainer merges the
   revert PR; the resulting outcome still counts.
3. Confirm the revert and `class_paused{docs-links}=1`. File another eligible link PR and confirm it
   waits for a human with `class_paused`; a looser policy must not merge it.
4. Land three clean, mature link-fix merges using the normal maintainer path. Leave
   `merge.verifyFor` unchanged. Expected: the policy returns from pause after the configured three
   clean recoveries; a subsequent shadow or live decision shows `paused=false`.
5. If the chain fails before the intended revert, stop M8 and preserve the evidence. If it fails
   after the revert, keep the policy paused until its normal recovery rule or a reviewed operational
   fix restores it; do not hide the failure with a drill label.

## 6. Record the two screencasts (S1–S2)

### 6.1 Preflight

- The exact handoff, planner question, standard workflow, PR checks, approve-to-merge, terminal
  status and Grafana cost paths are green in the earlier tests.
- OpenCode is configured and linked; the rooms, ai-native-ref issues and agent-factory Grafana tabs
  are open. Personal tabs and notifications are hidden.
- One genuine, small and visual ai-native-ref defect is written in `$DRILL_DIR/screencast.md` but not
  filed. Its initial handoff leaves one genuine gap so the planner asks a clarification question.
- A warm gVisor node is available. Use 1920×1080, browser zoom 125%, terminal font at least 16 pt,
  and one OBS scene per window. Never show `maku token`, a key, an internal IP or an email.

### 6.2 Capture one task

1. In a fresh ai-native-ref worktree, ask OpenCode to inspect the chosen page without changing it,
   then use `/maku handoff` with the prepared defect.
2. Capture the planner's clarification question. Accept its recommendation, review the plan's
   `standard` workflow and price ceiling, then use `start` with **Start now** selected.
3. Capture the issue filed as the linked GitHub user and carrying `factory/ready`, the room's role
   chain, and `kubectl get agentruns.maku.ogenki.io -n agents` with the run objects.
4. When the PR is ready, capture its App author, diff, checks and `maku/merge-gate` explanation.
   Review the current head and approve it; capture the factory's merger merging it.
5. Capture the terminal's final task card and Grafana's task spend and per-role cost. Save each raw
   segment separately before editing.

### 6.3 Export and publish

- **S1:** edit to 20–30 seconds: handoff, plan, room chain, PR approval, merged terminal status and
  spend. Omit the clarification and intermediate trust details. Use captions, no narration.
- **S2:** edit the same footage to approximately one minute: retain clarification, issue identity,
  separate sandboxed roles, Kubernetes run objects, gate explanation, approval-as-merge and cost.
- Review both exports for secrets and private data. Link them in issue #394 and open the site/README
  PR that adds both links. A raw recording is not an exported deliverable.

## 7. Cleanup and completion

1. Restore the M2 binding and any reviewed promotion only as intended; remove every temporary
   session switch, test-specific limit and evaluation overlay.
2. Stop unwanted test issues with `factory/stop`, close unintended issues/PRs, and remove local
   `room_checkout` worktrees. Keep genuine merged fixes and the recorded merged PR.
3. Confirm no campaign Task is outside a final phase, no unsafe fixture remains open, and the
   baseline is healthy:

   ```bash
   kubectl get tasks -n agent-system
   kubectl get agentruns -n agents
   flux get helmreleases -n agent-system
   gh pr list -R "$TARGET_REPO" --state open --label factory/drill
   ```

4. Complete every row in the campaign report, including BLOCKED and NOT APPLICABLE reasons. Link all
   fixes and passing reruns.
5. Keep aws-0 available until the report and both exported videos are verified. Do not tear it down
   without a separate owner decision.
