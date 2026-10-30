# Agent Factory runbooks — gcp-0

Live procedures for the Agent Factory on the test cluster `gcp-0`. Every command is copy-paste, and
every step names its expected output. A **room** is the per-task workspace the room broker serves at
`https://rooms.<domain>/r/<id>`: one shared log of messages, handoffs and notes for one factory task.

## State

gcp-0 was torn down on 2026-10-29. The next bootstrap is fresh, on Maku v0.32.0 (CRD group
`maku.ogenki.io`): start with [runbook 14](14-gcp-0-session.md), then
[Runbook 00](#runbook-00-one-time-cluster-setup). The runbooks stay written for that session.

| What | In the source today |
|---|---|
| Live auto-merge | cloud-native-ref's `docs-links` (Markdown link fixes) and `revert`, `autoMergesPerDay: 1` ([12](12-live-auto-merge-drill.md)) |
| Shadow | `dead-links` on both repositories ([15](15-dead-links.md)), `deps-patch` ([16](16-deps-patch.md)); `deps-minor` observed only |
| Budgets | Gateway budgets refuse (`SHADOW_MODE: "false"`, [04 Part D](04-gateway-secrets-budgets.md#part-d--enforcing-the-agents-budgets)); the fleet's and each person's day are counted, never refused (`enforcePrincipal: false`, [04 Part C](04-gateway-secrets-budgets.md#part-c--per-person-caps-the-shadow-week)) |
| Session switches, off after each live session | `testFirst` on `scripts` ([21](21-test-first-tester.md)), RunLore ([20](20-runlore-agent-to-agent.md)), the `docs` row's provider `models`, `human.mcp.sessionStart` ([19](19-factory-from-your-agent.md)) |

`maku setup <client>` installs the factory MCP server and the `factory-handoff` skill for a coding
agent client (`claude`, `opencode`, ...): [runbook 19](19-factory-from-your-agent.md).

### Known issues

The runbooks keep their intended expectation for each, with a "Known issue" note at the step.

| Bug | What you see | Runbook |
|---|---|---|
| F12 | A deleted pod of a run with a `roomRef` is re-created within ~1 s, the run stays `Running`, and the harness re-runs the task | 01 Step 7 |
| F15 | A run refused the room's lease still executes its task, unmirrored, on the room's branch | rooms only, no step here |
| F16 | Each MCP call through `agent-router` opens its own root trace instead of joining the run's | 08 Step 8 |
| [maku#279](https://github.com/Smana/maku/issues/279) | A task's status cost freezes before the run's final settle | 04 Part F |
| [maku#280](https://github.com/Smana/maku/issues/280) | A budget-exhausted run's ledger misses its last spend | 04 Part G |

## What each runbook proves

| Runbook | Proves (SC / Q / R) | Needs an owner action? | Est. time |
|---|---|---|---|
| [00](#runbook-00-one-time-cluster-setup) (below, this file) | — (setup only) | Yes — 1–4 (see checklist) | 10 min + owner actions |
| [01-runtime-sandbox.md](01-runtime-sandbox.md) | SC-01, SC-02, SC-03, SC-08, Q1, R7 | No | ~20 min |
| [02-identity-tokens.md](02-identity-tokens.md) | R2 (token TTL), Q8, SC-05, SC-07 | Yes — 1 | ~30 min |
| [03-egress.md](03-egress.md) | SC-09, Q3, Q4 | No | ~15 min |
| [04-gateway-secrets-budgets.md](04-gateway-secrets-budgets.md) | SC-10, SC-17 (listener half), SP4 frontier route + budgets | Yes — 1, 2 | ~20 min |
| [05-github-octo-sts.md](05-github-octo-sts.md) | SC-11, sts listener end to end | Yes — 1, 3, 4 | ~25 min |
| [06-mcp.md](06-mcp.md) | SC-12, SC-17 (MCP half) | Yes — 1 | ~15 min |
| [07-end-to-end.md](07-end-to-end.md) | SC-04, SC-06, SC-13, SC-14 | Yes — 1–5 | ~2 h |
| [08-observability.md](08-observability.md) | The VMRules (`agent-platform`, `agent-platform-logs`, `agent-factory`, `agent-rooms`), the dashboards, SP4 gateway metrics, the per-run view (SO-1…SO-5) | No | ~15 min |
| [09-app-key-compromise.md](09-app-key-compromise.md) | The App key-compromise procedure (SD14): stop, rotate, reload, revoke, resume and audit, for all four Apps | Yes — the App's installation page and settings | ~20 min |
| [10-disruption.md](10-disruption.md) | Disruption design acceptance 1–6 | Yes — a maintainer's `factory/ready`; aws-0 Step 7 needs IAM | ~60 min |
| [11-v1-validation.md](11-v1-validation.md) | Local-first UX: the skill, `maku status`, the room page, zoomable diagrams, D7 room access, observability on one run, one task end to end on release pins | Yes — a maintainer's `factory/ready`; a second, non-admin identity and a private test repo | ~90 min |
| [12-live-auto-merge-drill.md](12-live-auto-merge-drill.md) | Design D4, gate G1–G3: an unattended `docs-links` merge at the run-reported head, its revert and the breaker (both classes live in the source) | Yes — the owner's go, the merger App's `issues: write` and `actions: write`, the `agent-merge` and `agent-branches` rulesets, policy-bot on aws-0, a maintainer's `factory/ready`, `factory/drill` on the drilled PR | ~2 h |
| [13-rooms-restore.md](13-rooms-restore.md) | Issue #27: the rooms database restores from `rooms-pre-destroy` on a rebuild, and into a scratch namespace; RPO and RTO | Part A: a teardown and rebuild. Part B: the owner's go (writes a seed) | A: the rebuild + 10 min; B: ~30 min |
| [14-gcp-0-session.md](14-gcp-0-session.md) | The ordered gcp-0 session: gcp-0 up alone, the v2.1 blockers live, runbook 11 as the full test, v2 on gcp-0, the Substrate spike | Yes — Google auth, the quota request, the identity-provider topology, the agents keys, the go-live commit | a day, plus the spike's two |
| [15-dead-links.md](15-dead-links.md) | Merge gate classes: the `dead-links` class in shadow (an oracle-backed intake, a would-arm decision, the post-merge monitor) and, on the owner's go, one live drill with its revert | Shadow (in the source): no. The drill: the owner's go, the merger App's `actions` permission, a host `.policy.yml` rule | shadow: a day; drill: ~1 h |
| [16-deps-patch.md](16-deps-patch.md) | Merge gate classes: the `deps-patch` class in shadow (Renovate's PRs adopted, a would-arm decision, a Flux monitor) and, on the owner's go, one live drill with its revert | Shadow (in the source): no. The drill: the owner's go, the merger App's `issues: write`, cloud-native-ref PR K | shadow: a day; drill: ~1 h |
| [17-splitter.md](17-splitter.md) | The splitter: a hard issue proposed as a split, approved, landed part by part as sub-issues, declined by `/factory retry`, stopped, and charged to the approver within the family's cap | Yes — the owner's go, a maintainer's `factory/ready` and `/factory split`, the scoper's live proofs first | ~2 h |
| [18-factory-interfaces.md](18-factory-interfaces.md) | Factory interfaces: a sponsored principal filing through intake `api`, the broker's signed webhooks and the Slack App; the switch-on (merged), live proofs 2 to 5, and off again | Yes — the owner's go, the Slack App's console | ~3 h |
| [19-factory-from-your-agent.md](19-factory-from-your-agent.md) | The factory from your coding agent, live proofs 1 to 5 in Claude Code and OpenCode: start from the form, wait for an approval, the card and `room_changes`, the checkout, a hostile note shown inert; then off again | Yes — the owner's go, the cloud-native-ref skill-copy PR merged first | ~2 h |
| [20-runlore-agent-to-agent.md](20-runlore-agent-to-agent.md) | RunLore as the factory's internal principal, live proofs 1 to 5: the paths open, one incident filed as an `investigate` task and replayed idempotently, the old intake silent (stage 1); a fix verified after its soak, and a fix that does not hold (stage 2) | Yes — the owner's go, the ZITADEL sync and the webhook key seeded (runbook 14), a maintainer's `factory/publish` label created | ~2 h |
| [21-test-first-tester.md](21-test-first-tester.md) | The tester's contract on a seeded `scripts` issue, the hook and row 2c that hold it, a renamed holdout | Yes — F1 to F5 live and the owner's go | ~2 h |
| [22-slack.md](22-slack.md) | Slack, configure: the App from its manifest, the keys, the machine user, the Request URL, a channel's repositories (three places), who may file, one mention end to end. Users: the [user guide](../../../website/content/docs/platform/ai-platform/agents/user-guide.md) | Yes — the Slack console, OpenBao, the ZITADEL sync | ~1 h |

**Out of scope:** SC-15/SC-16 (gVisor overhead ratio and `validate-manifests.sh`/`task check`
exit codes) are already closed by the phase-0 spike and by CI — no live step adds evidence.

## Prerequisites (all runbooks)

Every runbook starts from the root of a `cloud-native-ref` checkout, the host, with `CLOUD` set: the
CA paths under `opentofu/` and `task agent:run` are the host's. The probe and check scripts live
here, so `AI_NATIVE_REF_DIR` names an `ai-native-ref` checkout; the host's `task agent:run` calls
`$AI_NATIVE_REF_DIR/scripts/ops/k8s/agent-run.sh` with the host's CA. gcp-0 is the target; the
aws variants are kept for an aws-0 rebuild. When a run's sandbox is lost mid-run (spot reclaim,
eviction, node loss), [runbook 10](10-disruption.md) covers how the factory checkpoints and resumes it.

```bash
CLOUD=gcp    # or aws
export AI_NATIVE_REF_DIR=~/Sources/ai-native-ref
```

| | gcp-0 | aws-0 |
|---|---|---|
| kube context | `gke_ogenki-435905_europe-west4-a_gcp-0` | the EKS context of `aws-0` |
| Tailnet reaches | `*.priv.gcp.ogenki.io` | `*.priv.aws.ogenki.io` |
| Cloud credentials | gcloud ADC (`gcloud auth application-default print-access-token >/dev/null && echo ADC-OK`) | `aws sts get-caller-identity` |
| gVisor node label | `sandbox.gke.io/runtime=gvisor` (GKE Sandbox pool) | `agents.ogenki.io/runtime=gvisor` (Karpenter pool) |

- No command here needs AWS credentials on gcp-0: gcp-0 generates its own gateway client keys
  in-cluster (runbook 04 Part B's promptfoo key).
- OpenBao CLI, with `VAULT_ADDR=https://bao.priv.$CLOUD.ogenki.io:8200` and
  `VAULT_CACERT=opentofu/$CLOUD/openbao/management/.tls/ca.pem`.
- `gh` CLI authenticated as an account that can call the GitHub API for `Smana/cloud-native-ref`.
- **VictoriaMetrics: through the API server proxy only**, never a direct URL or an
  `mcp__victoriametrics__*` tool call (no trusted-CA path):

  ```bash
  kubectl get --raw "/api/v1/namespaces/observability/services/vmsingle-victoria-metrics-k8s-stack:8428/proxy/api/v1/query?query=<url-encoded-promql>"
  ```

- **Every curl to a private host carries the private CA:**
  `--cacert opentofu/$CLOUD/openbao/management/.tls/ca.pem`. Without it, `curl -s` prints nothing.
- **Never put a token or API key on a command line.** Read it into a shell variable from a file,
  `kubectl create token`, or `bao ... -field=token`, and never `echo`/`print` the variable itself —
  only curl's `%{http_code}` or a redacted prefix (`token[:4]`).
- **A run that must still exist later needs a paced task.** An "Idle. Do nothing" task now finishes in
  about a minute, and the pod goes with it. Use `Run 'sleep N' in the terminal, then finish.`

To rotate the merger GitHub App's private key, see [09-app-key-compromise.md](09-app-key-compromise.md).

## Runbook 00: one-time cluster setup

### What is already in place

gcp-0 tracks cloud-native-ref's `main`, on release pins: the `ai-native-ref` source, Maku
and crossplane-configuration. The go-live commit on `main` un-suspends the source and the
`ai-gateway` and `agent-platform` umbrellas, and names `gcp-0` in the ownership fence.

Because the umbrellas are unsuspended **in git**, there is nothing to `flux resume`. A live resume
would be reverted on the next `flux-system` reconcile.

```bash
kubectl get gitrepository -n flux-system flux-system -o jsonpath='{.spec.ref.name}{"\n"}'
flux get kustomizations -n flux-system | grep -E '^(ai-gateway|agent-platform)[[:space:]]'
```

> `flux get kustomization` (flux CLI 2.9.5) reads only the first name it is given and silently drops
> the rest. Every runbook lists, then greps.

Expected: `refs/heads/main`; both `Ready=True`, `Suspended=False`.

### Owner actions, in order

| # | Action | Unblocks | Command |
|---|---|---|---|
| 1 | OpenBao policy `agents-secrets` + JWT role `agents-secrets` on `jwt/<cluster>` — applied by the `opentofu/$CLOUD/openbao/management` stack | `agent-secrets` → `agent-router` → `agent-mcp`, `octo-sts` (runbooks 02, 04–07) | see below |
| 2 | The agents' Z.ai key | runbook 04 (frontier route), 07 | `bao kv put -mount=agents zai api_key=-` (key on stdin, never as an argument) |
| 2b | The agents' Anthropic key, read by the ExternalSecret `agents-anthropic-api-key` | the internal tier on Claude (agentgateway's Anthropic backend) | `bao kv put -mount=agents anthropic api_key=-` |
| 2c | The agents' own Kimi Code and Mistral keys (feature 15), each capped on its console: Mistral's spend cap (pay-as-you-go, $20; billing active first), and Kimi Code's flat-rate plan as its cap. Moonshot processes in China and Mistral in the EU, so both serve public data only | the selectable `kimi-frontier`, `mistral-standard`, `mistral-light` aliases, switched on per class with `loops.<class>.models` | `bao kv put -mount=agents moonshot api_key=-` and `bao kv put -mount=agents mistral api_key=-` |
| 3 | Branch ruleset, **before** the App exists | runbook 05 | `task ops:github:agent-branch-ruleset -- Smana/cloud-native-ref` |
| 4 | GitHub App `ogenki-agents` on `Smana`, installed on `Smana/cloud-native-ref` only | runbook 05, 07 | `bao kv put -mount=agents github-app app_id=<id> private_key=@<pem file>` |
| 4b | The `factory-app` GitHub App key, read by SP3's ExternalSecret `agent-factory-github` | the `agent-factory` Kustomization | `bao kv put -mount=agents factory-app app_id=<id> private_key=@<pem file>` |
| 4c | The merger App `ogenki-agent-merger` key, read by the ExternalSecret `agent-factory-merger`. The App: Contents write, Checks read, Statuses read, Pull requests write, Metadata read, webhook off, installed on `Smana/cloud-native-ref` only (R16) | the `agent-factory` Deployment, which mounts it non-optionally | `bao kv put -mount=agents merger-app app_id=<id> private_key=@<pem file>` |
| 4d | Retired by feature 14's PR 7: the RunLore intake token (`runlore-intake`, `platform/runlore/factory-intake`) is no longer read; RunLore is a standard client ([runbook 20](20-runlore-agent-to-agent.md)). Delete both paths where they remain | — | — |
| 4e | The Slack App's keys (bot token, signing secret, bot user id), written from the Slack console | `maku-slack`, the Slack intake ([runbook 22](22-slack.md)) | `bao kv put -mount=agents factory-slack-app -` (one JSON document on stdin, [runbook 22 §2](22-slack.md#2-owner-store-the-keys-in-openbao)) |
| 4f | The machine users the Slack App and RunLore act as, created by the host's ZITADEL sync | intake `api`: the Slack App and RunLore as sponsored and internal principals ([runbook 18](18-factory-interfaces.md#1-prerequisites), [runbook 20](20-runlore-agent-to-agent.md#0-prerequisites)) | `zitadel-oidc-clients.sh sync --apply` on the host |
| 4g | One webhook signing key in two mounts, the broker's and RunLore's | the broker's signed webhooks to RunLore ([runbook 20](20-runlore-agent-to-agent.md)) | `bao kv put -mount=agents runlore-webhook signing-key=…` and `bao kv put -mount=platform runlore/factory-webhook signing-key=…`, the same key ([runbook 14 §5](14-gcp-0-session.md#5-owner-the-agents-keys-once-per-gcp-lineage)) |
| 4h | The `factory/publish` label on each repository RunLore files on | publishing RunLore's proposals ([runbook 20](20-runlore-agent-to-agent.md#0-prerequisites)) | `gh label create factory/publish -R <owner/repo>` |
| 5 | A trivial issue URL (e.g. a broken relative link) | runbook 07 SC-04 | — |

These keys (2, 2b, 2c, 4, 4b, 4c, 4e, 4g) are the platform's one owner-written exception: GitHub, Z.ai, Anthropic, Moonshot, Mistral and Slack issue
them, and the AWS snapshot cannot be restored across KMS seals (GCP parity). Once per GCP lineage.
Without 4c the factory pod never starts: its Secret volumes are not optional.

Action 1 is already applied by the management stack. See
[`clusters/gcp-0-agent-platform/README.md`](../../../clusters/gcp-0-agent-platform/README.md#resume)
for the full resume sequence (`opentofu/gcp/openbao/management` then `opentofu/gcp/gke/configure`,
the latter needing `TF_VAR_flux_git_ref` on a feature-branch cluster) if it ever needs re-applying on
a fresh lineage. To confirm it is live:

```bash
flux reconcile kustomization agent-secrets -n flux-system --with-source
kubectl get secretstore -n agent-system agents-secrets -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

Expected: `True`.

After actions 2 and 4, force the ExternalSecrets to re-read rather than waiting out their interval:

```bash
kubectl annotate externalsecret -n agent-system --all force-sync=$(date +%s) --overwrite
flux get kustomizations -n flux-system | grep -E '^(agent-router|agent-mcp|octo-sts|agent-factory)[[:space:]]'
```

Expected: all four `Ready=True`.

Runs use the harness released by Maku, pinned by digest in the crossplane-configuration release the
host runs ([runbook 07 Step 1](07-end-to-end.md#step-1--confirm-the-harness-pin)). A harness pre-release for a live gate
is a pre-release `v*` tag on Maku (its `release.yaml`; tags are admin-only under the
release-tags ruleset) or the `-pr<N>.<sha8>` image its `ci.yaml` pushes for same-repo PRs;
cloud-native-ref verifies only signatures from `release.yaml@refs/tags/v…`.

### Cleanup and teardown

```bash
kubectl delete agentruns -n agents --all --wait
kubectl delete -f "$AI_NATIVE_REF_DIR"/scripts/ops/k8s/agent-probe.yaml --ignore-not-found
```

To take the agent platform down while keeping the cluster, revert the go-live commit on
cloud-native-ref's `main`: the umbrellas and the source go back to `suspend: true`, which stops
reconciling without removing anything, so follow the cluster README's Teardown for the children.
Destroying the cluster is a separate owner call.

## v3 loop and sandbox layers on the `docs` class

v3 features are switched on for the `docs` class one at a time, one commit each in
`tooling/base/agent-factory/helm-values-configmap.yaml`, so a failure is attributable. Prove them in this
order; the next layer waits for the previous one's proofs. Layers 1 to 4 and the splitter's `scripts` row
are on in the source; `testFirst` (layer 6) is a session switch, off. The class is
declared by both repositories, so each switch reads for `Smana/ai-native-ref` and
`Smana/cloud-native-ref`; the drills below file on ai-native-ref unless said otherwise. Each issue is
public. A maintainer labels it `class:docs` first (without the label the task's class is `review`, which
reads `default`'s row, off), then `factory/ready`.

The drills' issue texts live on the operator's machine (`~/.cache/v3/drills/`), not here: the agents
read this README, and an agent that recognises a drill ("this task is the repository's own Drill E")
answers the drill rather than the issue. This page keeps each drill's
name, purpose and expected outcome; reword a drill's text before it runs again.

| Layer | Switch (`loops.docs`, or `classes.docs` per repository) | Design |
|---|---|---|
| 1. Scoper | `scope: scoper` | [scoper](../../superpowers/specs/2026-10-22-scoper-design.md#gate) |
| 2. Loop policy | `stallSteps: 60`, `continuations: 2`, `judge: tier-light` | [loops](../../superpowers/specs/2026-10-21-loops-and-teams-design.md), [harness reference](../../../website/content/docs/platform/ai-platform/agents/harness.md#loop-policy) |
| 3. Sandbox checks | `checks: true` | [sandbox checks](../../superpowers/specs/2026-10-22-sandbox-checks-design.md#gate) |
| 4. Search tool | `search: true` | [search tool](../../superpowers/specs/2026-10-23-search-tool-design.md) |
| 5. Splitter (`scripts`) | `split: {…}` | [splitter](../../superpowers/specs/2026-10-23-splitter-design.md) |
| 6. Test-first tester (`scripts`) | `testFirst: true` | [test-first tester](../../superpowers/specs/2026-10-22-test-first-tester-design.md) |

Before layer 1: the pins carry Maku v0.23.2 and crossplane-configuration v0.9.20 or later
(`spec.loop` with `search`, `checks` and `judgeModel`), and `scripts/ops/k8s/gcp-0-platform-gates.sh`
passes. Read a task with `kubectl -n agent-system get task <name> -o yaml`.

### Layer 1: the scoper

The factory runs a read-only triager first. Under `scope: scoper` it either scopes the issue (the scope
reaches the room and the implementer's brief) or asks its author the one question it cannot answer.

| # | Do | Expected reading |
|---|---|---|
| 1 | File drill issue A below; a maintainer applies `class:docs`, then `factory/ready` | A triager run, then an implementer. `status.scope` on the task is `ready` and holds the scope; the room shows the same scope; the implementer's brief holds it; `spec.scopeMode` is `scoper` |
| 2 | File drill issue B below and label it | One comment on the issue (the question, the assumption it would make), the label `factory/needs-author`, the task `Escalated` with reason `needs_author`, no implementer run |
| 3 | Edit issue B's body to add the acceptance check, then re-apply `factory/ready` | A new task (a new generation) scopes `ready`; the first one is superseded |
| 4 | File drill issue B again as a new issue, label it, then comment `/factory retry` | The implementer starts on the assumption (`status.scope` `assumed`), no second scoper run, the label is removed |
| 5 | Read the counters | `maku_factory_scoper_runs_total` and `maku_factory_scope_bounces_total` carry one outcome per run above |

Steering (live proof 3) needs a note at `.github/agent-factory/steering/docs.md` on the target's default
branch, which exists on ai-native-ref and not yet on cloud-native-ref. To prove it, switch the row to
`scope: steering` for this one step, then back: the implementer's brief carries the note, and
`spec.steering` names its blob sha (`git rev-parse origin/main:.github/agent-factory/steering/docs.md`).

**Drill A, a vague issue** the scoper can still bound (title and body, ready to file on ai-native-ref). If it asks a question instead of scoping, record it, answer by an edit as in step 3, and take the second task as step 1's evidence:

Text: `~/.cache/v3/drills/drill-a.md`, on the operator's machine, never in a repository the agents read.

**Drill B, no acceptance check, should bounce:**

Text: `~/.cache/v3/drills/drill-b.md`, on the operator's machine, never in a repository the agents read.

### Layer 2: the loop policy

Prerequisites: layer 1's proofs passed (the judge reads the scope's checks) and the capability profiles'
sidecar ([#103](https://github.com/Smana/ai-native-ref/pull/103)) is live: a command in the
sandbox that posts to the identity proxy's `/judge/v1` reaches the judge alias. Without the sidecar the
judge call is refused (403 or 404) and silently skipped: the run ends as `finished`, as with no judge, and
no error shows. Drills D and E run only after #103 is live; drill C (the stall rule) does not need it.
The row reads `docs: {scope: scoper, stallSteps: 60, continuations: 2, judge: tier-light, search: true}`.
The factory copies it into every implementer claim of the class: `kubectl -n agent-system get task <name> -o
jsonpath='{.spec.loop}'` shows `stallSteps`, `continuations` and `judgeModel`.

| # | Do | Expected reading |
|---|---|---|
| 1 | In a commit of the session, set `loops.docs.stallSteps` to 20 for this drill. File drill issue C (a stall drill) and label it as in layer 1 | The implementer ends with no commit by step 20: the task is `Escalated`, reason `stalled`; the room holds the run's findings as a note; the issue carries the fixed narration with the reason category only; `maku_factory_loop_runs_total{end="stalled"}` is 1. The run's cost stays under the tier's `runUSD` |
| 2 | File drill issue D (a clear issue whose first attempt misses a check) and label it | After the first run ends on its own, the judge answers `not_yet` against the scope's checks; the same conversation continues (the room shows one run's conversation, not a restart), at most twice |
| 3 | On step 2's task, read the cache | `cache_read` over `input` for the continued steps is high (runbook 04, Part E); a continuation that restarted the conversation reads as a cold prefix |
| 4 | An issue whose acceptance cannot be met (drill E) | The judge answers `impossible`: `Escalated`, reason `judge_impossible`, the judge's text only in the room, the issue carries the category only |
| 5 | Read the reviewer's role in the room on any of the runs above | The reviewer's brief and calls hold no implementer transcript |
| 6 | Read the counters | `maku_factory_loop_runs_total` by `end` (`finished`, `stalled`, `not_met`, `judge_impossible`) matches the runs above |

After the drill, put `stallSteps` back to 60 (a real docs run takes 15 to 40 steps before its first
commit; do not go under about 50), then set it from the accepted runs' step counts.

**Drill C, a stall** (a task that sends the run searching without ever committing):

Text: `~/.cache/v3/drills/drill-c.md`, on the operator's machine, never in a repository the agents read.

The route's old name does not exist, so the run reads and never finds a line to change; at step 20 the
stall rule stops it. If it commits a change, pick a stricter wording ("or change nothing and say so")
and file it again.

**Drill D, a continuation** (acceptance with two checks; the second is easy to miss):

Text: `~/.cache/v3/drills/drill-d.md`, on the operator's machine, never in a repository the agents read.

**Drill E, an impossible acceptance** (the judge should answer `impossible`, a human takes over). The judge may answer `not_yet` first and `impossible` after a continuation: either order passes if the task ends `Escalated` with `judge_impossible`. A task that ends `not_met` (continuations spent) is recorded as observed, not as a pass:

Text: `~/.cache/v3/drills/drill-e.md`, on the operator's machine, never in a repository the agents read.

### Layer 3: the sandbox checks

Both repositories carry `docs: {checks: true}` (egress `[pypi]` on cloud-native-ref, `[golang, pypi]`
on ai-native-ref). Prerequisites: each repository's `.github/agent-checks.yaml` is on its default branch
(`gh api repos/<repo>/contents/.github/agent-checks.yaml`), the cluster's `AgentRun` XRD has
`spec.loop.checks` (crossplane-configuration v0.9.20 or later), and `internal` runs never get it: the XRD
refuses the combination, and the factory sets it on public implementer and reviewer claims only. Watch the
egress during every step: `hubble observe --namespace agent-system --verdict DROPPED`.

| # | Do | Expected reading |
|---|---|---|
| 1 | File drill issue F on ai-native-ref, label it as in layer 1 | The implementer's claim has `spec.loop.checks` true (`kubectl -n agent-system get agentrun -l agents.ogenki.io/task=<task> -o jsonpath='{.items[*].spec.loop.checks}'`), the toolchain installs through the CNP, and `hubble` shows no DROPPED flow to a declared host |
| 2 | Read the run's checks note in the room | Each step of ai-native-ref's `agent-checks.yaml` ends `pass` or `skip`; the result matches offline proof 4's on `main` |
| 3 | The same for drill issue G on cloud-native-ref | The same, with the host's steps (`overlay`, `suites`, `shellcheck`, `links`, `pre-commit`) |
| 4 | Read each drill's first pushed head | The seeded defect was reported before the push; the first head's CI is green; `status.fixRuns` is 0 on the task (`kubectl -n agent-system get task <name> -o jsonpath='{.status.fixRuns}'`) |
| 5 | After a few real `docs` issues, compare each final head | The sandbox's step results agree with the CI's check conclusions on at least 90% of final heads; explain each miss |

The drills' seeded defect is a broken relative Markdown link, caught by the `links` step of both
repositories. The host's `shellcheck` step needs a script change, outside the `docs` class: prove it
under a `scripts` class switch in a later session.

**Drill F, a seeded defect on ai-native-ref:**

Text: `~/.cache/v3/drills/drill-f.md`, on the operator's machine, never in a repository the agents read.

**Drill G, a seeded defect on cloud-native-ref:**

Text: `~/.cache/v3/drills/drill-g.md`, on the operator's machine, never in a repository the agents read.

Both links end in a wrong extension (`.mdx`, `.yml`): the `links` step reports each before the push,
and the pushed head carries the corrected link.

### Layer 4: the search tool

`docs: {…, search: true}` offers the class's implementer runs the search tool (a read-only child on the
run's token: 40 iterations, 300k tokens, 300 s, six calls a run). It never switches the loop on. Design:
[search tool](../../superpowers/specs/2026-10-23-search-tool-design.md) (live proofs, SQ5). Prerequisite:
layers 1 and 2 passed, so a difference between the arms is the tool's alone.

| # | Do | Expected reading |
|---|---|---|
| 1 | File drill issues H1 to H3 below, label each as in layer 1 | The task has `spec.search: true`, every implementer claim `spec.loop.search: true` (`kubectl -n agent-system get agentrun -l agents.ogenki.io/task=<task> -o jsonpath='{.items[*].spec.loop.search}'`), the run calls the search tool at least once, the gateway's log shows the child's calls under the run's identity |
| 2 | Read the ledger of each run | The child's tokens are inside the run's; `budget` and `error` outcomes are under a quarter of the calls |
| 3 | Paired gate (SQ5a): flip `search` to `false` in a commit, file the same three issues again as new issues, then flip it back | Acceptance not lower over the pairs; steps per run (children included) and cost per accepted PR not higher with search on |

**Drill H1, a multi-file lookup** (the answer is spread over several files, so searching beats reading):

Text: `~/.cache/v3/drills/drill-h1.md`, on the operator's machine, never in a repository the agents read.

**Drill H2, a rename sweep:**

Text: `~/.cache/v3/drills/drill-h2.md`, on the operator's machine, never in a repository the agents read.

**Drill H3, a cross-reference:**

Text: `~/.cache/v3/drills/drill-h3.md`, on the operator's machine, never in a repository the agents read.

Cost: six runs for the three pairs, each capped by the docs tier's task cap (standard: $5.10); a docs
run costs about $0.50 to $1.50 and a search adds at most the child's 300k tokens, so the layer is
about $5 expected and $31 at the caps, inside `tasksPerDay: 20` and `factoryDailyUSD: 42.50`.

### Layer 5: the splitter

`scripts: {scope: scoper, split: {maxChildren: 4, familyUSD: 20.40, childTier: standard, anyTier: true}}` lets the
scoper propose a split of a hard `scripts` task; nothing splits before a maintainer comments `/factory
split`. The proofs are [runbook 17](17-splitter.md) section 3. Prerequisites: layer 1 passed (the split
needs the scoper), the factory App holds `issues: write`. File the cohort on cloud-native-ref, label each
`class:scripts` then `factory/ready` (without `class:scripts` the task's class is `review`, off).

**Drill S1, a hard issue of three separable parts:**

Text: `~/.cache/v3/drills/drill-s1.md`, on the operator's machine, never in a repository the agents read.

**Drill S2, a second hard issue:**

Text: `~/.cache/v3/drills/drill-s2.md`, on the operator's machine, never in a repository the agents read.

Step 4 of runbook 17 (`/factory retry` on a second proposal) uses S2's proposal; steps 1 to 3 and 5
use S1's. Cost: a family is capped at familyUSD $20.40 per issue, so the two issues are $40.80 at the
caps and exceed `factoryDailyUSD: 42.50` together with any other run that day: file them on separate
days, or expect about $4 to $8 per family in practice (a scoper run, then up to four parts at about
$1 to $2).

### Layer 6: the test-first tester

Design: [test-first tester](../../superpowers/specs/2026-10-22-test-first-tester-design.md) (TF1, TO4).
The switch is `repositories[].classes.scripts.testFirst: true` on cloud-native-ref only (TO4: none on
ai-native-ref, whose tests live under the gate path `scripts/ci/`), with `merge: {contractCheck: "Test
contract 🧪"}`. A session commit sets it, the session's last commit reverts it. The drills run on
cloud-native-ref with `class:scripts` then `factory/ready`; [runbook 21](21-test-first-tester.md) holds
the steps. Proofs: the tester runs first and commits a test that fails on the base; `status.contract`
holds `{runId, commit, files, ids}`; the implementer's pull request passes "Test contract 🧪"; the gate
reads `contract_modified` if the implementer edits a contract file.

The texts below are T1 and T2 (`not_testable`). Runbook 21's own T2 (the contract holds) and T3
(holdouts) have no text in `~/.cache/v3/drills/` yet: write them before that session.

**Drill T1, testable behaviour** (a pure function with a clear contract):

Text: `~/.cache/v3/drills/drill-t1.md`, on the operator's machine, never in a repository the agents read.

**Drill T2, not testable** (the tester should end `not_testable`, the implementer runs without a contract):

Text: `~/.cache/v3/drills/drill-t2.md`, on the operator's machine, never in a repository the agents read.

Cost: the tester run is a writer on the task's caps, so each drill is one tester run plus the implementer
and reviewer, about $2 to $4 expected and $5.10 (standard) at the task cap: two drills stay inside
`tasksPerDay: 20` and `factoryDailyUSD: 42.50`.

## Recording results

Each runbook ends with a results table (step, expected, observed, pass/fail). Fill it in place as
you go — there is no separate consolidated form. Paste failing steps' `kubectl`/`curl` output
verbatim; a summary line ("worked") is not evidence per this repo's evidence rule.

### Platform findings

Fixed findings from the earlier rounds (aws-0 rounds 1 to 6, gcp-0 rounds 7 and 9); each runbook's
Results tables keep the evidence.

| Finding | Cause | Fix |
|---|---|---|
| A deleted run's CNP went before its pod, so the GitHub-token revoke could not reach GitHub (SC-07): the token lived up to 1 h | The `Usage` was keyed on the Sandbox, which leaves the API at once; the harness profile set no `preStop` | crossplane-configuration PR #29: a `preStop` revoke (`4857e3f`) and the Usage keyed on the **Pod** (`c304bbf`); #2110 `17ec1f97` grants Crossplane `get pods` in `agents` only |
| octo-sts's installation-token mint answered 422 for every trust policy | The `ogenki-agents` App lacked `pull_requests: read & write`, and the installation had not accepted the change | The owner granted and accepted it; runbook 05 re-verified both roles |
| The OpenHands SDK crashed on the first model response (`'PromptTokensDetailsWrapper' object has no attribute 'cache_creation_tokens'`) | LiteLLM did not map `agent-default` and fell back to a wrapper without Anthropic's cache fields | OpenHands 1.49.6 with litellm `<1.95.1` (software-agent-sdk#5213) in the harness |
| An `AgentRun` idled at `Running`: the upstream `agent-server` image never submitted a task | No wrapper read `TASK_FILE`/`CONVERSATION_ID` | The repo-built harness (#2110) |
| `GET /v1/models` on the public listener answered `200` to any token, or none (SC-05) | AI Gateway's ext_proc answered `/v1/models` before `jwt_authn` ran | #2108 (`4fda7196`): an Exact-path `/v1/models` route with no ext_proc; check A7 in `scripts/ci/flux-schema/assert-ai-gateway.py`. agentgateway now answers it `404` behind the JWT ([02 Step 2](02-identity-tokens.md#step-2--the-401403-matrix-and-header-forgery-attribution-sc-05)). Not covered: the human gateway's `llm.priv…/v1/models` answers without credentials (tailnet only, model names only) |
| `agent-sandbox` release rejected; `envoy-ai-gateway` upgrade stalled | `reconcileStrategy: Revision` put `+<sha>` in `helm.sh/chart`; ESO's second write cancelled an in-flight upgrade | A postRenderer replaces the label; the HelmRelease retries |

**R7: a lost pod ends its run as `Failed` and is not recreated** (runbook 01 Step 7, by design).
agent-sandbox v1.0.3 reports `Finished=PodFailed` for every pod that ends `Failed`, a deleted or evicted
one included, so the composition latches `Failed` and withholds the run's ServiceAccount; the Sandbox
controller's recreate is then refused:

```
{"level":"error","ts":"...23:49:10Z","msg":"Failed to create", ... "error":"pods \"xplane-run-kcerjyh5\" is forbidden: error looking up service account agents/xplane-run-kcerjyh5: serviceaccount \"xplane-run-kcerjyh5\" not found"}
```

Recovery: a new run on the same branch (`task agent:run -- … --branch agent/<id>`); a factory run
resumes on its own ([runbook 10](10-disruption.md)). F12 (above) is the exception seen on a run with a
`roomRef`.
