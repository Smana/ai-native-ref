# Agent Factory live test session — gcp-0

Exercises SP1 (agent runtime and identity), SP4 PR 1 (AI gateway: frontier route and token budgets)
and the agent observability work on the live test cluster `gcp-0`. Every command is copy-paste, and every step names its expected output.
Start with [Runbook 00](#runbook-00-one-time-cluster-setup): the cluster is already deployed, but four
owner actions gate most runbooks.

`maku setup <client>` installs the factory MCP server and the `factory-handoff` skill for that coding agent client (`claude`, `opencode`, ...); see [Runbook 19](19-factory-from-your-agent.md).
When a run's sandbox is lost mid-run (spot reclaim, eviction, node loss), [10-disruption.md](10-disruption.md) covers how the factory checkpoints and resumes it.

## Status (2026-10-17)

gcp-0 is the live target again since 2026-10-17 ([runbook 14](14-gcp-0-session.md)), from `main` on release
pins. Rounds 1–6 and v1 (to 2026-10-16) ran on aws-0, now torn down. The round 7 and 9 columns are
gcp-0's earlier build, on `integration/agent-factory`.

| Runbook | Round 7, gcp-0 (PASS/FAIL/OWNER) | Round 9, gcp-0 (PASS/FAIL/OWNER) | Still open |
|---|---|---|---|
| [01](01-runtime-sandbox.md) | 7 / 1 / 1 | 1 / 1 / 0 | Step 2's FAIL (F2) is fixed (d9d75413, 5b77d0db) and passed from zero in round 9. Step 7: F12. Step 4 (SC-02) is aws-0 only |
| [02](02-identity-tokens.md) | 8 / 0 / 1 | — | B.2 GitHub-token timing needs the owner's interactive session (credential capture) |
| [03](03-egress.md) | 6 / 0 / 0 | — | — |
| [04](04-gateway-secrets-budgets.md) | 10 / 0 / 1 | — | A.3's OpenBao half mints a token: owner |
| [05](05-github-octo-sts.md) | 12 / 0 / 0 | — | — |
| [06](06-mcp.md) | 7 / 0 / 0 | — | The `room_*` tools (since c6a56f78) are not yet observed live in Steps 3–4 |
| [07](07-end-to-end.md) | 1 / 0 / 0 | — | Only SC-04 is recorded on gcp-0 (issue #2140 → PR #2141) |
| [08](08-observability.md) | 5 / 0 / 1 | 9 / 1 / 2 | Step 10's FAIL (F18) is fixed in 60e02d9a; re-run pending. F16 |
| [10](10-disruption.md) | — | — | Ran on aws-0 on 2026-10-07 (v3 @ `1d288ea6`): Steps 1–7 PASS, acceptance 1–6 met, §5 decided (no early warning on aws-0). gcp-0 not run yet |
| **Total** | **56 / 1 / 4** | **10 / 2 / 2** | |

Round 7 ran on `integration/agent-factory` @ `a2c645ba`, round 9 on `147819ff`. Round 9 re-ran only 01
Steps 2 and 7 (as the F2 smoke probe and a room run) and 08 Steps 6–10.

Open bugs the runbooks keep their intended expectation for, with a "Known issue" note at the step:

| Bug | What you see today | Runbook |
|---|---|---|
| F12 | A deleted run pod is re-created within ~1 s, the run stays `Running`, and the harness re-runs the task | 01 Step 7 |
| F15 | A run refused the room's lease still executes its task, unmirrored, on the room's branch | rooms only, no step here |
| F16 | Each MCP call through `agent-router` opens its own root trace instead of joining the run's | 08 Step 8 |

### Latest aws-0 result per runbook (history)

Mixes rounds 4 to 6 (from `580042e6` on). Round 6 took issue #2112 to PR #2114 (SC-04) and ran a
58-minute run with no `401` (SC-06).

| Runbook | PASS | FAIL | BLOCKED | Notes |
|---|---|---|---|---|
| [01](01-runtime-sandbox.md) | 9 | 0 | 0 | R7 fails closed by design and resumes via `--branch` (see Platform findings) |
| [02](02-identity-tokens.md) | 5 | 1 | 1 | The FAIL (`/v1/models` auth bypass) is fixed in #2108 and verified live. GitHub-token timing needs the owner's interactive session (credential capture) |
| [03](03-egress.md) | 6 | 0 | 0 | — |
| [04](04-gateway-secrets-budgets.md) | 10 | 0 | 0 | Run by the coordinator directly |
| [05](05-github-octo-sts.md) | 12 | 0 | 0 | The round-3 octo-sts 422 is fixed (see Platform findings) |
| [06](06-mcp.md) | 6 | 0 | 0 | — |
| [07](07-end-to-end.md) | 7 | 0 | 0 | Round 6: SC-04 (68 s to a PR the owner merged), SC-06 (58 min, 44 × `200`, 0 × `401`) |
| [08](08-observability.md) | 5 | 0 | 0 | Data verified through the VM/VL proxy calls. The UI is SSO-gated |
| **Total** | **60** | **1** | **1** | |

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
| [08-observability.md](08-observability.md) | Agent-platform VMRules, dashboard, SP4 gateway metrics, the per-run view (SO-1…SO-5) | No | ~15 min |
| [09-app-key-compromise.md](09-app-key-compromise.md) | The App key-compromise procedure (SD14): stop, rotate, reload, revoke, resume and audit, for all four Apps | Yes — the App's installation page and settings | ~20 min |
| [10-disruption.md](10-disruption.md) | Disruption design acceptance 1–6 | Yes — a maintainer's `factory/ready`; aws-0 Step 7 needs IAM | ~60 min |
| [11-v1-validation.md](11-v1-validation.md) | Local-first UX: the skill, `maku status`, the room page, zoomable diagrams, D7 room access, observability on one run, one task end to end on release pins | Yes — a maintainer's `factory/ready`; a second, non-admin identity and a private test repo | ~90 min |
| [12-live-auto-merge-drill.md](12-live-auto-merge-drill.md) | Design D4, gate G1–G3: the first unattended `docs-links` merge at the run-reported head, its revert and the breaker | Yes — the owner's go, the merger App's `issues: write` and `actions: write`, the `agent-merge` and `agent-branches` rulesets, policy-bot on gcp-0, a maintainer's `factory/ready` | ~2 h |
| [13-rooms-restore.md](13-rooms-restore.md) | Issue #27: the rooms database restores from `rooms-pre-destroy` on a rebuild, and into a scratch namespace; RPO and RTO | Part A: a teardown and rebuild. Part B: the owner's go (writes a seed) | A: the rebuild + 10 min; B: ~30 min |
| [14-gcp-0-session.md](14-gcp-0-session.md) | The ordered gcp-0 session: gcp-0 up alone, the v2.1 blockers live, runbook 11 as the full test, v2 on gcp-0, the Substrate spike | Yes — Google auth, the quota request, the identity-provider topology, the agents keys, the go-live commit | a day, plus the spike's two |
| [15-dead-links.md](15-dead-links.md) | Merge gate classes: the `dead-links` class in shadow (an oracle-backed intake, a would-arm decision) and, on the owner's go, one live drill with its revert | Shadow: no. The drill: the owner's go, the merger App's `actions` permission, a host `.policy.yml` rule | shadow: a day; drill: ~1 h |
| [16-deps-patch.md](16-deps-patch.md) | Merge gate classes: the `deps-patch` class in shadow (Renovate's PRs adopted, a would-arm decision, a Flux monitor) and, on the owner's go, one live drill with its revert | Shadow: no. The drill: the owner's go, the merger App's `issues: write`, cloud-native-ref PR K | shadow: a day; drill: ~1 h |
| [17-splitter.md](17-splitter.md) | Splitter design, live proofs 1–4: a hard issue proposed as a split, approved, landed part by part as sub-issues, stopped, and charged to the approver within the family's cap | Yes — the owner's go, a maintainer's `factory/ready` and `/factory split`, the scoper's live proofs first | ~2 h |
| [18-factory-interfaces.md](18-factory-interfaces.md) | Factory interfaces, the switch-on: a sponsored principal filing through intake `api`, the broker's signed webhooks and the Slack App; live proofs 2 to 5, then off again | Yes — the owner's go, the Slack App's console, a host PR for the public listener | ~3 h |
| [19-factory-from-your-agent.md](19-factory-from-your-agent.md) | The factory from your coding agent, live proofs 1 to 5 in Claude Code and OpenCode: start from the form, wait for an approval, the card and `room_changes`, the checkout, a hostile note shown inert; then off again | Yes — the owner's go, the cloud-native-ref skill-copy PR merged first | ~2 h |
| [20-runlore-agent-to-agent.md](20-runlore-agent-to-agent.md) | RunLore as the factory's internal principal, stage 1, live proofs 1 to 3: the paths open, one incident filed as an `investigate` task and replayed idempotently, the old intake silent | Yes — the owner's go, the ZITADEL sync and the webhook key seeded (runbook 14), a maintainer's `factory/publish` label created | ~2 h |
| [21-test-first-tester.md](21-test-first-tester.md) | The tester's contract on a seeded `scripts` issue, the hook and row 2c, a renamed holdout | Yes — F1 to F5 live and the owner's go | ~2 h |
| [22-slack.md](22-slack.md) | Slack, configure: the App from its manifest, the keys, the machine user, the Request URL, a channel's repositories (three places), who may file, one mention end to end. Users: the [user guide](../../../website/content/docs/platform/ai-platform/agents/user-guide.md) | Yes — the Slack console, OpenBao, the ZITADEL sync | ~1 h |
| [23-showcase.md](23-showcase.md) | Showcase for developers: seven scenarios (from the editor, from Slack, the factory asks back, a split, watch and steer, an alert to a verified fix, guardrails and cost), the prep checklist, the session switches, 30- and 60-minute agendas, and what not to promise | Yes — the owner's session switches (the tester on `scripts`, a reviewer on Kimi, RunLore), a maintainer to label and merge | 30 or 60 min, plus an hour of seeds |

**Out of scope:** SC-15/SC-16 (gVisor overhead ratio and `validate-manifests.sh`/`task check`
exit codes) are already closed by the phase-0 spike and by CI — no live step adds evidence.

## Prerequisites (all runbooks)

Every runbook starts from the root of a `cloud-native-ref` checkout, the host, with `CLOUD` set: the
CA paths under `opentofu/` and `task agent:run` are the host's. The probe and check scripts live
here, so `AI_NATIVE_REF_DIR` names an `ai-native-ref` checkout; the host's `task agent:run` calls
`$AI_NATIVE_REF_DIR/scripts/ops/k8s/agent-run.sh` with the host's CA. gcp-0 is the live target; the
aws variants are kept for the next aws-0 rebuild.
A **room** is the per-task workspace the room broker serves at `rooms.<domain>`: one shared log of messages, handoffs and notes for a single factory task, reached at `https://rooms.<domain>/r/<id>`.

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
`ai-gateway` and `agent-platform` umbrellas, and names `gcp-0` in the ownership fence. Rounds 7 and 9
ran on the earlier `integration/agent-factory` branch instead.

Because the umbrellas are unsuspended **in git**, there is nothing to `flux resume`. A live resume
would be reverted on the next `flux-system` reconcile.

```bash
kubectl get gitrepository -n flux-system flux-system -o jsonpath='{.spec.ref.name}{"\n"}'
flux get kustomizations -n flux-system | grep -E '^(ai-gateway|agent-platform)[[:space:]]'
```

> Corrected 2026-09-27: `flux get kustomization` (flux CLI 2.9.5) silently reads only the first
> name given and drops the rest — it never errors, so a multi-name invocation quietly checks one
> Kustomization and reports nothing on the others. Every runbook command below now lists then
> greps instead of passing multiple names positionally.

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
| 4d | Retired by feature 14's PR 7: the RunLore intake token (`runlore-intake`, `platform/runlore/factory-intake`) is no longer read; RunLore is a standard client ([runbook 20](20-runlore-agent-to-agent.md)). Delete both paths once PR 7 runs | — | — |
| 4e | v3: the Slack App's keys (bot token, signing secret, bot user id), written from the Slack console | `maku-slack`, the Slack intake ([runbook 22](22-slack.md)) | `bao kv put -mount=agents factory-slack-app -` (one JSON document on stdin, [runbook 22 §2](22-slack.md#2-owner-store-the-keys-in-openbao)) |
| 4f | v3: the machine users the Slack App and RunLore act as, created by the host's ZITADEL sync | intake `api`: the Slack App and RunLore as sponsored and internal principals ([runbook 18](18-factory-interfaces.md#1-prerequisites), [runbook 20](20-runlore-agent-to-agent.md#0-prerequisites)) | `zitadel-oidc-clients.sh sync --apply` on the host |
| 4g | v3: one webhook signing key in two mounts, the broker's and RunLore's | the broker's signed webhooks to RunLore ([runbook 20](20-runlore-agent-to-agent.md)) | `bao kv put -mount=agents runlore-webhook signing-key=…` and `bao kv put -mount=platform runlore/factory-webhook signing-key=…`, the same key ([runbook 14 §5](14-gcp-0-session.md#5-owner-the-agents-keys-once-per-gcp-lineage)) |
| 4h | v3: the `factory/publish` label on each repository RunLore files on | publishing RunLore's proposals ([runbook 20](20-runlore-agent-to-agent.md#0-prerequisites)) | `gh label create factory/publish -R <owner/repo>` |
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

Runs use the harness released by Maku, pinned by digest in the composition
(`agent-harness:v0.15.2` at crossplane-configuration `v0.9.15`). A harness pre-release for a live gate
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

The gcp-0 session of 2026-10-27 switches v3 features on for the `docs` class only, one commit
each in `tooling/base/agent-factory/helm-values-configmap.yaml`, so a failure is attributable. Merge
and prove them in this order; the next layer waits for the previous one's proofs. The class is
declared by both repositories, so each switch reads for `Smana/ai-native-ref` and
`Smana/cloud-native-ref`; the drills below file on ai-native-ref unless said otherwise. Each issue is
public. A maintainer labels it `class:docs` first (without the label the task's class is `review`, which
reads `default`'s row, off), then `factory/ready`.

The drills' issue texts live on the operator's machine (`~/.cache/v3/drills/`), not here: the agents
read this README, and on the 2026-10-27 session they recognised the drills from it ("this task is the
repository's own Drill E") and answered the drill rather than the issue. This page keeps each drill's
name, purpose and expected outcome; reword a drill's text before it runs again.

| Layer | Switch (`loops.docs`, or `classes.docs` per repository) | Design |
|---|---|---|
| 1. Scoper | `scope: scoper` | [scoper](../../superpowers/specs/2026-10-22-scoper-design.md#gate) |
| 2. Loop policy | `stallSteps: 60`, `continuations: 2`, `judge: tier-light` | [loops](../../superpowers/specs/2026-10-21-loops-and-teams-design.md), [harness reference](../../../website/content/docs/platform/ai-platform/agents/harness.md#loop-policy) |
| 3. Sandbox checks | `checks: true` | [sandbox checks](../../superpowers/specs/2026-10-22-sandbox-checks-design.md#gate) |

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
| 5 | Read the counters | `agent_factory_scoper_runs_total` and `agent_factory_scope_bounces_total` carry one outcome per run above |

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
sidecar ([#103](https://github.com/Smana/ai-native-ref/pull/103)) is merged and live: a command in the
sandbox that posts to the identity proxy's `/judge/v1` reaches the judge alias. Without the sidecar the
judge call is refused (403 or 404) and silently skipped: the run ends as `finished`, as with no judge, and
no error shows. Drills D and E run only after #103 is live; drill C (the stall rule) does not need it.
The row now reads `docs: {scope: scoper, stallSteps: 60, continuations: 2, judge: tier-light}`.
The factory copies it
into every implementer claim of the class: `kubectl -n agent-system get task <name> -o
jsonpath='{.spec.loop}'` shows `stallSteps`, `continuations` and `judgeModel`.

| # | Do | Expected reading |
|---|---|---|
| 1 | In a commit of the session, set `loops.docs.stallSteps` to 20 for this drill. File drill issue C (a stall drill) and label it as in layer 1 | The implementer ends with no commit by step 20: the task is `Escalated`, reason `stalled`; the room holds the run's findings as a note; the issue carries the fixed narration with the reason category only; `agent_factory_loop_runs_total{end="stalled"}` is 1. The run's cost stays under the tier's `runUSD` |
| 2 | File drill issue D (a clear issue whose first attempt misses a check) and label it | After the first run ends on its own, the judge answers `not_yet` against the scope's checks; the same conversation continues (the room shows one run's conversation, not a restart), at most twice |
| 3 | On step 2's task, read the cache | `cache_read` over `input` for the continued steps is high (runbook 04, Part E); a continuation that restarted the conversation reads as a cold prefix |
| 4 | An issue whose acceptance cannot be met (drill E) | The judge answers `impossible`: `Escalated`, reason `judge_impossible`, the judge's text only in the room, the issue carries the category only |
| 5 | Read the reviewer's role in the room on any of the runs above | The reviewer's brief and calls hold no implementer transcript |
| 6 | Read the counters | `agent_factory_loop_runs_total` by `end` (`finished`, `stalled`, `not_met`, `judge_impossible`) matches the runs above |

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

Both repositories now carry `docs: {checks: true}` (egress `[pypi]` on cloud-native-ref, `[golang, pypi]`
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

`scripts: {scope: scoper, split: {maxChildren: 4, familyUSD: 20.40, childTier: standard}}` lets the
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

### Layer 6: the test-first tester (proven 2026-10-29)

**Since 2026-10-29** the switch exists and the tester is proven live on cloud-native-ref's `scripts`
class, the `not_testable` case included: [runbook 21](21-test-first-tester.md) holds the drills and
their results. The text below records why this layer was blocked on 2026-10-27.

Design: [test-first tester](../../superpowers/specs/2026-10-22-test-first-tester-design.md) (TF1, TO4). Its
switch is `repositories[].classes.scripts.testFirst: true` on cloud-native-ref only (TO4: none on
ai-native-ref, whose tests live under the gate path `scripts/ci/`). **No commit sets it yet**, for two
reasons found on 2026-10-27:

- `testFirst` and `merge.contractCheck` are in no Maku release (v0.25.0's `Class` has no such
  key, and the factory's strict parse refuses an unknown one). Only the contract check (plan PR 1, the
  harness's `test-contract`) is built; the factory slice (plan PR 6) is not.
- The host's `.github/chainguard/agent-tester.sts.yaml` grants `contents: read`; TO2 needs `contents: write`,
  a gate path and so a human pull request on cloud-native-ref.

When both land: pin the release, then one commit sets `scripts: {testFirst: true}` on cloud-native-ref with
`merge: {contractCheck: "Test contract 🧪"}`, and the drills run on cloud-native-ref with `class:scripts`
then `factory/ready`. Proofs, from the design's live proofs: the tester runs first and commits a test that
fails on the base; `status.contract` holds `{runId, commit, files, ids}`; the implementer's pull request
passes "Test contract 🧪"; the gate reads `contract_modified` if the implementer edits a contract file.

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

**FIXED in round 6: a deleted run's CNP went before its pod, so the GitHub-token revoke could not
reach GitHub (SC-07).** Two defects:
- **The `Usage` was keyed on the Sandbox.** The Usage that should hold the run's CNP until the pod is
  gone named the Sandbox as its `by` resource. A Sandbox has no finalizer and leaves the API the
  moment it is deleted. Crossplane releases a composed Usage as soon as a GET of `by` returns
  NotFound (`internal/controller/protection/usage/reconciler.go:327`, v2.4.2), and replayed the CNP
  deletion in the same second.
- **The harness profile never set `preStop`.**

The consequences: once the CNP was gone, the namespace `default-deny` cut the pod's egress while
`agent-run` was still revoking, so the token stayed live until GitHub expired it, up to 1 h.

| Run | Endpoint removed | CNP deleted |
|---|---|---|
| Before: `qeh6rf2k` (B.2) | 09:52:32 | 09:52:11.6, **21 s before the pod** |
| After: `hb545ti2` | 10:38:37.1 | 10:38:40.3, **3 s after the pod** |

The fix:
- crossplane-configuration PR #29 `4857e3f` adds the `preStop` revoke.
- crossplane-configuration PR #29 `c304bbf` keys the Usage on the **Pod**, which stays in the API until kubelet has finished
  `preStop` and the SIGTERM cleanup.
- #2110 `17ec1f97` grants Crossplane `get pods` in `agents` only. Checked with `kubectl auth can-i`:
  `get` yes; `list`, and `get` in any other namespace, no. Without it the Usage could never release,
  and run deletion would hang.

Rolled out as `v0.7.2-pr29.3ad168a`. The earlier round's `usage_order_live.sh` (on the PR #27 pin) had
passed only because the upstream image died within its 2 s poll.

**FIXED for round 4 (owner) — octo-sts's installation-token mint returned 422 for every trust
policy, both roles tested (round 3).** Cause confirmed by the owner: the `ogenki-agents` App was
missing `pull_requests: read & write`, and the installation had not accepted that permission change.
Both fixed; round 4 re-verified live on real implementer and reviewer runs — exchange, `GET
/repos/...`, push-allowed-to-own-branch, push-refused-to-`main`, push-refused-for-reviewer, and the
audience-mismatch case in both directions all now behave exactly as designed. See runbook 05's
Results table.

<details><summary>Original round-3 write-up</summary>

`agent-router`'s `sts` listener correctly verifies the caller
and forwards to octo-sts (confirmed: cross-repo and non-run-subject requests are denied with the
*right* octo-sts-level errors, not a network failure), but the actual GitHub call octo-sts makes to
mint the scoped installation token always fails:

```
github_api_call method=POST path_raw=/app/installations/165342698/access_tokens status_code=422
```

Reproduced from a real implementer run (`xplane-run-bx7qwi6i`, trust policy `contents:write,
pull_requests:write, issues:read, checks:read, actions:read`) and a real reviewer run
(`xplane-run-iqeuqxbv`, `contents:read, pull_requests:read, issues:read, checks:read, actions:read`)
— both roles' *scoped* mint 422s identically, even though the *unscoped* installation token octo-sts
uses internally to read the trust-policy file from the repo succeeds (`201`) most of the time. Since
both a write-heavy and a read-only permission set fail the same way, the likely cause is a permission
declared in **every** trust policy that the `ogenki-agents` GitHub App installation was not actually
granted — `checks: read` and `actions: read` are the two most easily missed in the App's repository
permissions UI (`docs/superpowers/plans/2026-09-25-agent-runtime-identity-plan.md` line ~5080 has the
intended table). GitHub 422s an installation-token request that asks for a permission the app-level
grant doesn't include. **Owner check:** compare `Smana` → Settings → GitHub Apps → `ogenki-agents` →
Permissions against that table; if it was edited after the initial install, GitHub also requires the
installation to re-accept the updated permission set before tokens honoring it can mint. This blocked
every push-capable path in runbooks 05 and 07 until the round-4 fix above.

</details>

**FIXED in round 6, by OpenHands 1.49.6 with litellm `<1.95.1` (software-agent-sdk#5213) in the
harness. Round 5 (2026-09-27, live on `c1691cee`, real harness `v0.1.0-pr2110.d8134ede`) — the
OpenHands SDK crashes on the first model response, every time, before any git operation.** Everything
up to and including the model call works: the run clones the repo, checks out `agent/<id>`, starts a
conversation, and `agent-router` proxies one `POST /api/paas/v4/chat/completions` → `200` in 4539ms
(`glm-5.3`; the gateway meters `8144` tokens for it, `sum(gen_ai_client_token_usage_sum{ar_agent=...})`).
Then, inside the harness's own SDK, before the agent ever acts on that response:

```
AttributeError: 'PromptTokensDetailsWrapper' object has no attribute 'cache_creation_tokens'
  File ".../openhands/sdk/llm/utils/telemetry.py", line 68, in normalize_usage
    cache_write = int(prompt_details.cache_creation_tokens or 0)
openhands.sdk.conversation.exceptions.ConversationRunError: Conversation run failed for id=...
```

A `UserWarning` just before it is the likely root: `Cost calculation failed: This model isn't mapped
yet. model=agent-default, custom_llm_provider=openai` — LiteLLM doesn't recognize `agent-default`,
falls back to a generic OpenAI-shaped response wrapper, and that wrapper's `prompt_tokens_details`
lacks the Anthropic-style `cache_creation_tokens` field `normalize_usage` unconditionally reads.
**Reproduced twice**, back to back (`xplane-run-3s7i55r7`, `xplane-run-mun2l7g2`), both crashing
`phase=Failed`/`PodFailed` 30-45s after `Running`, before any octo-sts exchange or git push — no
branch ever reaches GitHub, no PR is possible. This blocks every real end-to-end run (SC-04, SC-06)
until either the SDK is patched/pinned past this bug or the gateway advertises a model name LiteLLM
maps to a provider whose usage shape it expects. Not fixed here (no code changed).

**FIXED by #2110 (the repo-built harness). Round 3 (2026-09-27, live on `580042e6`) — the upstream
`agent-server` image never submits a task; an `AgentRun` idles at `Running` doing nothing.** With the
repo-built harness image (#2110) not yet published, the Sandbox's only app container runs the bare OpenHands image with
`command: ["--port","8000"]` — no wrapper reads the composition's `TASK_FILE`/`CONVERSATION_ID` env
vars and calls `POST /api/conversations`. Verified on `xplane-run-n7tfcziv` (issue `#2112`): phase
reached `Running`, `status.conversationId` was allocated, but after 8+ minutes: zero rows for
`sum(gen_ai_client_token_usage_sum{ar_agent="system:serviceaccount:agents:xplane-run-n7tfcziv"})`,
zero `agent-router` access-log lines for that `x_ar_agent`, zero octo-sts activity, no PR. This is a
harder block than "no git credential helper" — the agent loop itself never starts. Expected until
#2110 ships; not fixed here.

> **FIXED 2026-09-27, in #2108 (PR 3, 4fda7196), live on `980b789f`.** The root cause was filter
> order, not the `Overridden` status. On `public` the chain is
> `ext_proc/aigateway → custom_response → jwt_authn → …`, and AI Gateway enables its ext_proc only on
> the `agent-models` routes, where it answers `/v1/models` itself before `jwt_authn` runs.
> A dedicated Exact-path `/v1/models` route with no ext_proc now answers 404 behind the
> listener's JWT policy. Check A7 in `scripts/ci/flux-schema/assert-ai-gateway.py` requires that guard on every agent-router listener carrying an
> AIGatewayRoute. Live after the fix:
> - `/v1/models`: no token 401, forged 401, valid 404;
> - chat: no token 401, valid 200, served by `glm-5.3`.
>
> Not covered: the human gateway's `llm.priv…/v1/models` also answers without credentials. It is
> tailnet-only and exposes model names only.

**Round 2 (2026-09-27, live on `580042e6`) — `GET /v1/models` bypasses `agent-router`'s JWT
authentication entirely (SC-05).** Every token combination tested against the public listener's
`/v1/models` returns `200`, including no `Authorization` header at all and a self-signed,
wrong-signature JWT:

```
none→public 200
sts→public 200
internal→public 200
self-signed→public 200
```

The `agent-router-public` SecurityPolicy (JWT, `agent-router.implementer.public` etc. audiences) is
correctly `Accepted=True` but carries an `Overridden=True` condition:

```
message: 'This policy is being overridden by other securityPolicies for these
  routes: [agent-system/ai-eg-mcp-main-agent-mcp-public]'
```

`POST /v1/chat/completions` on the same listener, same Gateway, enforces JWT correctly
(`none→401`, `sts→403`, `internal→403`, `public→200`) — the SecurityPolicy mechanism itself works.
Only the ai-gateway-synthesized `/v1/models` listing bypasses it, most likely because that endpoint
is answered by the `ai-gateway-extproc` filter before the JWT filter runs, independent of the
per-route SecurityPolicy attachment. Anyone with network access to `agent-router` (any pod in the
cluster, absent a CiliumNetworkPolicy restricting it) can currently enumerate configured models with
no credential. Not fixed here per this session's scope (no code changes); use
`/v1/chat/completions` for auth-matrix testing until this is fixed.

**Fixed in git during the round-1 run (live since `76716898`):**
- **`agent-sandbox`:** `reconcileStrategy: Revision` put `+<sha>` into the chart's `helm.sh/chart`
  label, and the API server rejected the release. A postRenderer now replaces the label.
- **`envoy-ai-gateway`:** ESO's second write to the watched MCP seed Secret cancelled an in-flight
  upgrade. The HelmRelease had no upgrade remediation, so it stalled. It now retries.

**R7: a lost pod ends its run as `Failed` and is not recreated.** Runbook 01, Step 7. This is by
design, and Step 7 now tests it that way. The composition withholds the run's ServiceAccount once
the run is terminal. agent-sandbox v1.0.3 reports `Finished=PodFailed` for every pod that ends in
phase `Failed`, a deleted or evicted pod included. So the composition latches `Failed` before the
Sandbox controller's recreate, which the missing ServiceAccount then refuses:

```
{"level":"info","ts":"...23:49:10Z","msg":"Creating a new Pod", ... "Sandbox":{"name":"xplane-run-kcerjyh5","namespace":"agents"}}
{"level":"error","ts":"...23:49:10Z","msg":"Failed to create", ... "error":"pods \"xplane-run-kcerjyh5\" is forbidden: error looking up service account agents/xplane-run-kcerjyh5: serviceaccount \"xplane-run-kcerjyh5\" not found"}
```

Recovery is the spec's documented mitigation: a new run on the same branch
(`task agent:run -- … --branch agent/<id>`). The spike's "recreated at once, same name" held for the
Sandbox controller alone, before the composition withheld the ServiceAccount and suspended a finished
Sandbox. The spec's R7 text is corrected on #2092.

> Known issue (F12, round 9): on `147819ff`, a deleted run pod was re-created within ~1 s, the run
> stayed `Running`, and the harness re-ran the task in a fresh conversation. That run had a
> `roomRef`; round 7 on a run without one still saw `Failed PodFailed`.

Transparent resume would need the composition to see the pod itself (`deletionTimestamp` or a
`DisruptionTarget` condition), so it could tell pod loss from a crash. That is a crossplane-configuration
follow-up for the owner to decide.
