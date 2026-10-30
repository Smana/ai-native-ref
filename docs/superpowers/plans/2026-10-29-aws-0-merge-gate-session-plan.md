# The aws-0 merge-gate session — Live Proof Plan

> **For agentic workers:** this plan is run live with the owner at the keyboard: every `[OWNER]`
> step is theirs, every other step is the session agent's, read-only unless the step says what it
> writes. Steps use checkbox (`- [ ]`) syntax for tracking. Record every result in
> `~/.cache/v3/aws-0-session-<date>.md` as it lands, never only in the scratchpad.

**Goal:** On aws-0, measure the human path and prove the merge gate's paths built since 2026-10-18,
the three human-path changes included, before any class widens. No class goes live in this
session; `dead-links`' drill runs last and only after the drill label is deployed.

**Architecture:** The session is a measurement session. Readiness first; then the proofs that
need nothing but time run passively from boot; then the short active proofs on this repository's
`docs-links` class (shadow here, so nothing merges by itself); the human-path proofs mid-session;
the `dead-links` drill with its unattended revert merge last. Every proof has a pass criterion and
a stop condition, and the owner's go gates the drill.

**Tech Stack:** aws-0 (EKS, Karpenter's gVisor pool), Flux, OpenBao through the aws
management CLI, `gh`, `kubectl`, VictoriaMetrics through the API server proxy, the Maku release
pinned by PR 4, policy-bot's App `ogenki-merge-gate`, the merger App `ogenki-agent-merger`.

**Spec:** [the human path design](../specs/2026-10-29-merge-gate-human-path-design.md), "The
live proofs" and "Open questions"; the [study](../specs/2026-10-29-automerge-criteria-research.md),
sections 9 and 10; agent-platform's merge gate follow-ups plan, "Next gcp-0 session: live proofs"
(S0, L1–L5, M1, M2, #182), re-ordered here for aws-0.

## Global Constraints

- **The cloud.** `CLOUD=aws`; the kube context of aws-0; the tailnet reaches `*.priv.aws.ogenki.io`;
  `aws sts get-caller-identity` for credentials; the gVisor node label is
  `agents.ogenki.io/runtime=gvisor` (runbook README, "gcp-0 versus aws-0"). VictoriaMetrics only
  through `kubectl get --raw "/api/v1/namespaces/observability/services/vmsingle-victoria-metrics-k8s-stack:8428/proxy/api/v1/query?query=…"`.
  Every curl to a private host carries `--cacert opentofu/aws/openbao/management/.tls/ca.pem`. No
  token on a command line.
- **Prerequisites, all before boot:** PR 4 merged and tagged in ai-native-ref; the host pins that
  tag; PR 5 merged (the host's fence names aws-0); the owner's OpenBao secrets on aws (step 0);
  the policy-bot App's webhook pointed at aws-0 (step 0); cnref #2521 labelled `factory/drill`
  (step 0).
- **Nothing goes live.** `dead-links`, `deps-patch` and `deps-minor` stay `shadow: true`;
  `docs-links` and `revert` stay as committed (live on the host at 1 a day, shadow here). M1 and
  M2 run on this repository's `docs-links` only, never on `dead-links` or `deps-patch`.
- **The drill last.** L2 and #158 run only after the gauge reads `docs-links` unpaused (L5/G1
  passed) and with the owner's go.
- **Stop conditions** are per proof below. A stop means: record it, do not improvise a fix on the
  cluster; file it for the next offline round.
- **Naming.** "Agent Factory" is the product; Maku is the controller.

---

## 0. [OWNER] Before boot

- [ ] **0.1 policy-bot's App secret on aws.** The `merge-gate` mount exists on aws
  (`opentofu/aws/openbao/management/mounts.tf`). With `VAULT_ADDR=https://bao.priv.aws.ogenki.io:8200`
  and `VAULT_CACERT=opentofu/aws/openbao/management/.tls/ca.pem`:

  ```bash
  bao kv put -mount=merge-gate policy-bot app_id=<id> private_key=@<pem file> webhook_secret=@<file> oauth_client_id=<id> oauth_client_secret=@<file>
  ```

  Expected: `Success!`. Without it policy-bot never starts and every decision is `policy_absent`.
- [ ] **0.2 The merger App key on aws** (runbook README row 4c):
  `bao kv put -mount=agents merger-app app_id=<id> private_key=@<pem file>`. The installation
  holds `issues: write` (B1) and `actions: write` on both repositories: check
  `gh api /app/installations` with the App's JWT, or the App's settings page, and record it.
- [ ] **0.3 The App's webhook.** In `ogenki-merge-gate`'s settings, the webhook URL becomes
  `https://policy-bot.<public_domain_name>/api/github/hook`, where `public_domain_name` is
  `eks-aws-0-vars`' value (read it after boot with
  `kubectl get cm eks-aws-0-vars -n flux-system -o jsonpath='{.data.public_domain_name}'`; it is
  the same value the last aws-0 session used). gcp-0's hook stops receiving deliveries.
- [ ] **0.4 The drill label on #2521:**
  `gh pr edit 2521 -R Smana/cloud-native-ref --add-label factory/drill`. Create the label first if
  it does not exist: `gh label create factory/drill -R Smana/cloud-native-ref --description "A maintainer's drill revert: the breaker does not count it" --color 5319e7`,
  and the same label on `Smana/ai-native-ref`.
- [ ] **0.5 Merge PR 5** (the host's fence to aws-0) with a bypass.
- [ ] **0.6 The rulesets on this repository:**
  `gh api repos/Smana/ai-native-ref/rulesets --jq '.[].name'` lists `agent-merge`,
  `agent-merge-gate`, `agent-branches`. If not, apply them with the host's
  `scripts/ops/github/agent-*-ruleset.sh` (open question 6 of the design, settled here).

## 1. Boot and readiness (S0)

- [ ] **1.1 [OWNER] Deploy aws-0** as the host's runbooks say; the `agent-platform` umbrella is
  live on aws-0 (`clusters/aws-0/agent-platform.yaml`, `suspend: false`) and un-suspends the
  `ai-native-ref` source.
- [ ] **1.2 Flux green.** `flux get kustomizations -A | grep -v True` prints nothing for
  `agent-factory`, `policy-bot`, `merge-gate-secrets`, `agent-observability`, `room-broker`.
- [ ] **1.3 S0, readiness.** Pass when all of:
  - `kubectl auth can-i list helmreleases.helm.toolkit.fluxcd.io -A --as system:serviceaccount:agent-system:agent-factory` → `yes`, and `… create helmreleases …` → `no`;
  - the factory's log shows `merge ledger read from GitHub` for both repositories and no `label the merge ledger` error (B1);
  - `maku_factory_class_paused` is exported for every class with a switch, both repositories;
  - policy-bot's Deployment is Ready and a scratch PR on this repository gets a `policy-bot: main` status within 2 minutes.
  - Stop: a mint refused for `issues` (B1 not granted); a ClusterRole with a write verb; no `policy-bot: main` on the scratch PR (the webhook URL, 0.3).

## 2. Passive from boot

| ID | Proof | Pass | Stop |
|---|---|---|---|
| L5 / G1 | The breaker survives a rebuild and the drill label lifts it | At boot, with 0.4 done, the host's `docs-links` reads `maku_factory_class_paused{class="docs-links",repository="Smana/cloud-native-ref"} 0` and the log's ledger line names #2521 as a drill. Then, with 0.4 undone on a scratch copy (remove the label, restart the factory), it reads 1: the ledger still demotes on an unlabelled revert | The gauge reads 1 with the label present (the ledger does not read labels on revert PRs) |
| L3 | `deps-patch` and `deps-minor` shadow | Every eligible Renovate PR gets an adopted Task and `would-arm head=<sha> paused=false capped=…`; ineligible ones get none; Renovate's merge gets `factory/merged:deps-patch` and a Flux reading within 2 h; `shadow-merge-tally.sh --class deps-patch --author app/renovate` counts it | A Renovate PR on a gate path decided `shadow`; a merge with no `factory/merged:deps-patch` and a ledger error in the log |
| N3 | Release age against the host's registries | Every L3 decision's marker carries `age=ok`, `age=pending` or `age=n/a`; no PR stays `pending` beyond `minimumReleaseAge` + 24 h; the session lists each registry (ghcr.io, quay.io, Docker Hub, OCI charts) with its outcome | — (a finding, not a stop): a registry whose bumps stay pending is the design's AM11 input for PR K |
| L1 | `dead-links` shadow, both repositories | A finding becomes a Task and a PR with `would-arm`; after a human merges at that head, `factory/merged:dead-links`, then `monitor.oracle: healthy` after two detector runs | A verdict posted before the follow-up window ends |
| N7 | Shadow under a cap | On a day with one merger merge on the host (L2's day, or a scratch approved merge does not count: caps read `armedAt` only), a shadow decision still posts `would-arm … capped=true` | `auto_merge_cap` on a shadow class |
| N4 | The human-path baseline | For every hand-off of the session: reason, hand-off time, merge time, `how`; at teardown, `histogram_quantile(0.5, …handoff_to_merge_seconds…)` by reason, and `human_wait_seconds_total` by reason and class, recorded in the session file | — |
| #182 | AwaitingCI's bound | A scratch class in shadow with a misspelt holdout and `awaitingCIFor: 1h` hands off `ci_wait_expired` naming the check after 1 h | The task waits silently past 1 h |

## 3. Active, on this repository's `docs-links` (shadow here)

| ID | Proof | Steps | Pass | Stop |
|---|---|---|---|---|
| N1 | Policy replay of #226 | policy-bot's simulate API on this repository's #226, #223 and the host's #2652, #2670 (`curl --cacert … https://policy-bot.priv.aws.ogenki.io/api/simulate/Smana/ai-native-ref/226 -H "Authorization: Bearer $(cat token)"`, the UI's token) | Each rule's state and the predicate that skipped it; the #226 answer settles the design's open question 3 | — |
| N6 | Approve-to-merge | A scratch docs task (`class:docs`, unarmed) → PR → `class_unarmed` hand-off whose comment says "To merge: approve this pull request"; the owner approves on GitHub | Within one reconcile: `reentered_approved`, then the merger merges at the approved head; the PR carries `factory/merged:docs` and `factory/approved-merge`; `pr_outcomes_total{outcome="approved_merged"}` 1; `armedToday` unchanged (a second scratch task the same day is not `auto_merge_cap`); the task is `Done`/`merged` with no `Verifying`. Then on a third task: approve, push a commit after the approval → `head_moved`, policy-bot pending, no merge until a new approval | The merger merges a head other than the approved one; a merge under a `CHANGES_REQUESTED` newer than the approval; `Verifying` after an approved merge |
| M1 | The regression path | The owner merges a planted docs PR of `docs-links` whose required check turns red on `main` after (or sets `factory/monitor:regression` on a merged PR and restarts the factory) | `monitor.main: regression`, the label, the control-issue narration, `AgentFactoryMergeRegression` fires, the next `docs-links` decision here reads `class_paused` (shadow: the marker says `paused=true`, the verdict stays `shadow_would_arm`, AM4), the gauge reads 1; nothing is reverted | A revert PR opens (MC7) |
| M2 | Follow-up detection | A later PR rewrites a line the M1 merge wrote; a second one touches an unrelated file | `factory/follow-up-of:#<n>` and `outcome="follow_up"` on the first; nothing on the second (N5: precision, both counts recorded) | The unrelated merge is labelled |
| N8 | Recovery | After M1, three clean human merges of `docs-links` here, with `followUpWindow` shortened to 1 h for the session on this repository's class (a session-only config commit, reverted at teardown) | After the third matures, the gauge reads 0 and the next decision's marker says `paused=false` (AM7) | The gauge stays 1 after three mature clean merges |

## 4. Last: the `dead-links` drill and the unattended revert merge (L2, #158)

Only with the owner's go, after section 3's N8 passed (the gauge and the drill label are proven),
and with the host's `low-risk: dead-links` rule in place (PR L's host side, or runbook 15's note on
the rule).

| Step | Pass | Stop |
|---|---|---|
| A planted link on the host (runbook 15 §3) → two detector runs → task → PR | `would-arm head=<sha>` for `dead-links` on the host, then the owner flips `dead-links: {live: true}` for the drill only | — |
| The merger merges at the head | `factory/auto-merged:dead-links`, `AutoMerging` → `Verifying` → `Done`; the monitor's `oracle: healthy` after two runs | A merge at another head |
| `gh pr edit <n> --add-label factory/drill`, then `factory/revert` | The merger opens the revert carrying `factory/revert-of:#<n>` and `factory/drill`; **the merger merges its own revert unattended** (#158) within `verifyFor`; the gauge for `dead-links` stays 0 (AM6) | The revert waits on a human (#158 not proven); the gauge reads 1 |
| `dead-links` back to `{shadow: true}` | The tally's `--outcomes` prints `drill=1 bad=0` | — |

## 5. Teardown record

- [ ] The session file holds: every proof's PASS/FAIL/STOP with its evidence line; N4's medians by
  reason; N3's registry table; N1's per-rule states; the tally output per class.
- [ ] Runbook 12's result table and runbook 15's gain a row for this session; the status page's
  row 8 reads "proven on aws-0 on <date>" for what passed and names what did not.
- [ ] The session-only config commit (N8's `followUpWindow`) is reverted.
- [ ] The design's open questions 1–6 get their answers in the design's table, as a follow-up PR.
- [ ] Worth filing to the wiki: anything in the session that contradicts a runbook.

## Self-review

- **Spec coverage.** The design's "The live proofs": readiness (1.3), the breaker's survival and
  lift (L5/G1), the shadow classes (L3, L1), the human-path baseline (N4), the policy replay (N1),
  the release-age reading (N3), the three new proofs (N6, N7, N8), the drill last (section 4); L4
  stays clock-bound and is absent on purpose. The open questions 3 and 6 are settled in N1 and 0.6.
- **Order.** Nothing in section 3 touches `dead-links` or `deps-patch`; the drill waits for N8
  and the owner's go, as the design's AM6 note requires.
- **Placeholders.** Every command is complete but the secrets' values and the public domain,
  which the owner reads from the cluster; `<date>` is the session's.
