# 12 — Live auto-merge drill (`docs-links`, gcp-0)

Drills the first unattended merge to `main` and its revert, gate evidence G2 and G3 of the
[live auto-merge design](../../superpowers/specs/2026-10-16-v2-live-auto-merge-design.md) (D4).
The factory merges to `main` without a human for the drill's duration: **run it only on the
owner's go.** The drill runs on the factory that `Smana/cloud-native-ref`'s
`.github/agent-factory.yaml` names (the ownership fence): `gcp-0` today, the only live cluster.
Every other factory renders the same values and never acts on the repository. See
[README.md](README.md) for `CLOUD`.

## Owner's GitHub prerequisites

Nothing below reaches the cluster. All three must hold before ai-native-ref
[#21](https://github.com/Smana/ai-native-ref/pull/21) (the held config PR) merges.

- [ ] **The merger App `ogenki-agent-merger` holds `issues: write` and `actions: write`, accepted on
  the installation.** `issues` writes the ledger labels (GitHub labels PRs through the issues API);
  `actions` re-runs a cancelled check (`checkReruns: 1`). Settings → Developer settings → GitHub
  Apps → `ogenki-agent-merger` → Permissions → Issues and Actions: Read and write; then accept the
  change on the installation page. Proof: the [mint test](#the-mint-test) returns `201`.
- [ ] **The `agent-merge` ruleset exists on `Smana/cloud-native-ref`**, covering `refs/heads/main`,
  `refs/heads/revert-*` and `refs/heads/revert-*/**`, with the merger App on its bypass list. From a
  cloud-native-ref checkout (the App ID is on github.com/settings/apps/ogenki-agent-merger; a private
  App's `/apps/<slug>` 404s):

  ```bash
  MERGER_APP_ID=<merger App ID> task ops:github:agent-merge-ruleset -- Smana/cloud-native-ref
  gh api repos/Smana/cloud-native-ref/rulesets --jq '.[] | select(.name == "agent-merge") | .id'
  ```

- [ ] **The live `agent-branches` ruleset (24063626) no longer covers `main`.** This is the blocker:
  it excludes only `refs/heads/agent/**`, and its bypass list (human roles, Renovate) omits the
  merger App, so every live merge and revert is refused. After `agent-merge` exists (the script
  refuses before):

  ```bash
  task ops:github:agent-branch-ruleset -- Smana/cloud-native-ref
  gh api repos/Smana/cloud-native-ref/rulesets/24063626 --jq .conditions.ref_name.exclude
  ```

  Expected: `refs/heads/agent/**`, `refs/heads/main`, `refs/heads/revert-*`, `refs/heads/revert-*/**`.

Observed read-only on 2026-10-17:

| Item | Observed |
|---|---|
| Merger App permissions | Not readable with a user token (`/user/installations` answers 403). The mint test needs the factory's `agent-factory-merger` Secret, absent on gcp-0 while the `agent-factory` Kustomization is not Ready |
| `agent-merge` | Not applied: the repository's rulesets are `agent-branches` (24063626) and `agent-tags` (24293886) only |
| `agent-branches` | Still covers `main`: `exclude: ["refs/heads/agent/**"]`, bypass = repository roles 2, 4, 5 and Integration 2740 (Renovate) |

```mermaid
flowchart LR
  gh["owner: App permissions,<br/>agent-merge, agent-branches"] --> pin["cnref pin → release with<br/>docs-links + revert live"]
  pin --> issue["issue: class:docs-links<br/>+ factory/ready"]
  issue --> pr["agent PR"] --> gate{"merge gate"}
  gate -->|"arm, armed"| merge["merger App merges<br/>at the decided head"]
  merge --> lbl["label factory/auto-merged:docs-links"]
  merge --> verify["verify 30 min → Done"]
  verify -->|"factory/revert"| rv["revert PR, factory/revert-of:#n,<br/>auto-merged (revert live)"]
  rv --> demoted["ClassDemoted on #2188<br/>breaker: class_paused"]
  demoted --> back["cnref pin → release with<br/>both classes back in shadow"]
```

## Know before the go

- **The drill pauses `docs-links` afterwards.** With `breaker: {window: 10, maxReverts: 1}`, the
  drill's revert holds the class at `class_paused`, in shadow too (gate row 9 precedes row 11), until
  10 newer `docs-links` merges by maintainers push it out of the window. No `would-arm` comment, and so
  no tally progress for G4, until then. After a rebuild only labelled merges count, so the pause lasts
  until 10 merges made after the rebuild.
- **Live means `{live: true}`.** `{}` is "neither": a label only, the gate hands off `class_mismatch`.
- **Both classes go live in one commit** (D5): a live class with a shadow `revert` would wait for a
  human to merge its own revert.
- **A missing App grant stops every merger call.** Once a class is live, the factory asks the
  merger's tokens for `issues: write` and `actions: write`. GitHub refuses the whole mint if the
  installation lacks one, so the shadow calls stop too, not only the labels.

## Prerequisites

From a cloud-native-ref checkout, `kubectl` on the factory's cluster
(`gke_ogenki-435905_europe-west4-a_gcp-0` for gcp-0; `kubectl config current-context` shows it).

| # | Check | How |
|---|---|---|
| P1 | The factory runs agent-platform `v0.14.0` or later | cloud-native-ref pins ai-native-ref `v0.1.5` or later, and the pod runs that tag: `kubectl get deploy -n agent-system agent-factory -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'` → `ghcr.io/smana/agent-factory:v0.15.3@sha256:98e5…` at pin `v0.1.17` |
| P2 | The owner's GitHub prerequisites hold | The three boxes above ticked, and the mint test below returns `201` |
| P3 | The factory is idle on `Smana/cloud-native-ref` | `kubectl get tasks -n agent-system` shows no task outside a final phase (`Done`, `Rejected`, `NoOp`, `Reverted`, `Closed`, `Stopped`) |
| P4 | `main` is green | `gh run list -R Smana/cloud-native-ref --branch main --limit 3` |
| P5 | No auto-merge today | `gh pr list -R Smana/cloud-native-ref --state merged --label 'factory/auto-merged:docs-links'` is empty (the drill's cap is 1 a day, labelled merges count) |

### The mint test

It asks for exactly the merger's live scope. Nothing reaches a process's argv, and the token is
revoked at once:

```bash
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT; umask 077
kubectl get secret -n agent-system agent-factory-merger -o jsonpath='{.data.private_key}' | base64 -d >"$d/key.pem"
id=$(kubectl get secret -n agent-system agent-factory-merger -o jsonpath='{.data.app_id}' | base64 -d)
b64() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
now=$(date +%s)
h=$(printf '{"alg":"RS256","typ":"JWT"}' | b64)
p=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now-60)) $((now+540)) "$id" | b64)
s=$(printf '%s.%s' "$h" "$p" | openssl dgst -sha256 -sign "$d/key.pem" -binary | b64)
printf 'Authorization: Bearer %s.%s.%s\n' "$h" "$p" "$s" >"$d/jwt"
inst=$(curl -s -H @"$d/jwt" https://api.github.com/repos/Smana/cloud-native-ref/installation | jq -r .id)
curl -s -o "$d/tok.json" -w '%{http_code}\n' -X POST -H @"$d/jwt" \
  "https://api.github.com/app/installations/$inst/access_tokens" \
  -d '{"repositories":["cloud-native-ref"],"permissions":{"checks":"read","statuses":"read","contents":"write","pull_requests":"write","metadata":"read","actions":"write","issues":"write"}}'
printf 'Authorization: Bearer %s\n' "$(jq -r .token "$d/tok.json")" >"$d/tok"
curl -s -o /dev/null -w 'revoked %{http_code}\n' -X DELETE -H @"$d/tok" https://api.github.com/installation/token
```

Expected: `201`, then `revoked 204`. A `422` names the missing permission: fix the first box above before going on.

## Steps

Set once:

```bash
CLOUD=gcp    # the cloud of the factory the fence names
CA=opentofu/$CLOUD/openbao/management/.tls/ca.pem
VL=https://vl.priv.$CLOUD.ogenki.io
vm() { kubectl get --raw "/api/v1/namespaces/observability/services/vmsingle-victoria-metrics-k8s-stack:8428/proxy/api/v1/query?query=$(jq -rn --arg q "$1" '$q|@uri')" | jq -c '.data.result[] | [.metric, .value[1]]'; }
vm 'sum by (class, verdict, reason) (agent_factory_merge_decisions_total{class=~"docs-links|revert"})'   # the baseline
```

### Step 1 — switch the classes live

1. Merge the held ai-native-ref config PR, [#21](https://github.com/Smana/ai-native-ref/pull/21)
   (`docs-links` and `revert` `{live: true}`, `autoMergesPerDay: 1`), then cut its release: an
   admin pushes tag `v0.1.N` on the merge commit, and `release.yaml` publishes and signs the artifact.
2. In cloud-native-ref, bump `flux/sources/ocirepo-ai-native-ref.yaml` to that tag and its digest
   (`crane digest ghcr.io/smana/ai-native-ref:v0.1.N`), and merge it.
3. Watch it land:

```bash
flux reconcile source oci ai-native-ref -n flux-system
kubectl get cm -n agent-system agent-factory-helm-values -o jsonpath='{.data.values\.yaml}' | grep -E 'factory:|docs-links:|revert:|autoMergesPerDay'
kubectl rollout status deploy -n agent-system agent-factory --timeout=5m
```

Expected: `factory: gcp-0` (the name the fence holds), `docs-links: {live: true}`,
`revert: {live: true}`, `autoMergesPerDay: 1`; the rollout completes (a strictly parsed bad config
fails it, and the old pods keep serving).

### Step 2 — open the `docs-links` issue

```bash
gh issue create -R Smana/cloud-native-ref --label class:docs-links \
  --title "docs: fix broken external links (live auto-merge drill)" \
  --body "Find broken external links in Markdown under docs/ and website/content/, outside docs/superpowers/, docs/specs/ and website/content/docs/decisions/. Fix those with an obvious replacement, changing fewer than 21 lines in total and adding or deleting no file. If none is broken, change nothing and open no pull request."
gh issue edit <issue> -R Smana/cloud-native-ref --add-label factory/ready
```

This is the `link-rot` schedule's text. If the task ends `NoOp` (nothing broken), file a second issue
naming one external link you have seen fail, with its replacement. A maintainer adds `factory/ready`
after `class:docs-links`: the class is read at triage.

```bash
TASK=$(kubectl get task -n agent-system --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}'); echo "$TASK"
kubectl get task -n agent-system "$TASK" -o jsonpath='{.spec.predictedClass} {.status.phase} {.status.reason}{"\n"}'
```

Expected: `docs-links`, then `Implementing` → `AwaitingCI`.

### Step 3 — watch the gate decide

```bash
kubectl get task -n agent-system "$TASK" -w -o jsonpath='{.status.phase} {.status.reason}{"\n"}'
```

Expected: `AwaitingCI` (waits while checks run) → `AutoMerging` → `Verifying`. Any other ending (a
`human` verdict with `class_mismatch`, `policy_*`, `verdict_stale`) is a finding: record the reason
and stop at Step 6.

### Step 4 — verify the merge and its head pin (G2)

```bash
PR=$(kubectl get task -n agent-system "$TASK" -o jsonpath='{.status.pullRequest.number}')
kubectl get task -n agent-system "$TASK" -o jsonpath='{.status.pullRequest}' | jq '{headSHA, mergeCommitSHA, mergedBy, autoMerged, armedAt, mergedAt}'
gh pr view "$PR" -R Smana/cloud-native-ref --json headRefOid,mergedBy,mergeCommit,labels \
  -q '{head: .headRefOid, by: .mergedBy.login, merge: .mergeCommit.oid, labels: [.labels[].name]}'
gh api "repos/Smana/cloud-native-ref/commits/$(gh pr view "$PR" -R Smana/cloud-native-ref --json headRefOid -q .headRefOid)" -q .commit.message | grep '^Agent-Run:'
```

Expected:

- `mergedBy` is `ogenki-agent-merger[bot]` (`app/ogenki-agent-merger` in `gh`), `autoMerged: true`;
- the PR's `headRefOid` equals the task's `headSHA`: the head the run reported is the head merged
  (`expectedHeadOid`);
- the head carries an `Agent-Run:` trailer;
- labels include `factory/auto-merged:docs-links` (written after the merge, retried each pass: allow a minute).

After `merge.verifyFor` (30 min) with `main` green, the task ends `Done` / `merged_verified`.

### Step 5 — revert it and see the breaker count it (G3)

Within `merge.revertWindow` (168 h), from `Verifying` or `Done`:

```bash
gh pr edit "$PR" -R Smana/cloud-native-ref --add-label factory/revert
kubectl get task -n agent-system "$TASK" -w -o jsonpath='{.status.phase} {.status.reason} {.status.pullRequest.revertNumber}{"\n"}'
```

Expected: `Reverted` / `revert_requested` within a poll (60 s), with a `revertNumber`. Then:

```bash
RV=$(kubectl get task -n agent-system "$TASK" -o jsonpath='{.status.pullRequest.revertNumber}')
gh pr view "$RV" -R Smana/cloud-native-ref --json author,title,body,labels,autoMergeRequest,state,mergedBy \
  -q '{author: .author.login, title, body, labels: [.labels[].name], auto: (.autoMergeRequest != null), state, by: .mergedBy.login}'
gh issue view 2188 -R Smana/cloud-native-ref --json comments -q '.comments[-1].body'
```

Expected:

- the revert PR is authored by the merger App, titled `Revert "…"`, its body `Reverts #<PR> (agent factory task …)`;
- it carries `factory/revert-of:#<PR>`, and native auto-merge is on (the `revert` class is live);
- it ends `MERGED` once its required checks are green (and `policy-bot: main`, where the
  `agent-merge-gate` ruleset requires it);
- the control issue #2188's newest comment: "an auto-merge of `docs-links` was reverted … goes to human review".

The breaker now holds 1 revert in 1 merge. Its proof is the next `docs-links` decision, which must be
`human` / `class_paused`. If another `docs-links` PR reaches the gate during the window, read it there.
Otherwise the [G1 check](#g1-optional-the-breaker-survives-a-restart) below shows it.

### Step 6 — switch back to shadow

Revert the held config PR's merge commit in ai-native-ref (back to `{shadow: true}` for both classes
and `autoMergesPerDay: 10`), release it, and bump the cloud-native-ref pin to that release, as in
Step 1. Then:

```bash
kubectl get cm -n agent-system agent-factory-helm-values -o jsonpath='{.data.values\.yaml}' | grep -E 'docs-links:|revert:|autoMergesPerDay'
```

Expected: `{shadow: true}` twice, `autoMergesPerDay: 10`. The drill is over when this holds.

### G1 (optional): the breaker survives a restart

Owner call: deleting Tasks drops their history from `kubectl` (the PRs and comments stay).

```bash
kubectl delete task -n agent-system "$TASK"
kubectl rollout restart deploy -n agent-system agent-factory && kubectl rollout status deploy -n agent-system agent-factory
```

Then put one `docs-links` issue through the factory. Expected: the merge ledger is read from GitHub
(log below) and the PR's gate decision is `human` / `class_paused`.

## Evidence to record

```bash
# The gate's decisions over the drill (the counter appears at the first decision after the rollout)
vm 'sum by (class, verdict, reason) (increase(agent_factory_merge_decisions_total{class=~"docs-links|revert"}[6h]))'
vm 'sum by (class, outcome) (increase(agent_factory_pr_outcomes_total{class="docs-links"}[6h]))'

# The factory's own account: ledger read, label writes, the task's hand-offs
curl -sS --cacert $CA $VL/select/logsql/query --data-urlencode \
  "query=_time:6h kubernetes.pod_namespace:\"agent-system\" AND kubernetes.pod_labels.app.kubernetes.io/name:\"agent-factory\" AND (\"merge ledger\" OR \"$TASK\") | fields _time, _msg | sort by (_time)"

# GitHub's record: what the breaker and the daily cap read after a rebuild
gh pr list -R Smana/cloud-native-ref --state all --label 'factory/auto-merged:docs-links' --json number,mergedBy,mergedAt
gh pr list -R Smana/cloud-native-ref --state all --label "factory/revert-of:#$PR" --json number,state,author
```

Expected: `verdict="arm", reason="armed"` once for `docs-links`; no `label the merge ledger` error;
`merge ledger read from GitHub` at each factory start; one labelled merge, one revert-of PR; `agent_factory_pr_outcomes_total` counts `auto_merged` then `reverted`.

## Abort and roll back

| When | Do | Effect |
|---|---|---|
| Before the merge | `factory/stop` on the task's issue or PR | The task ends `Stopped`; nothing merges |
| Anything looks wrong, any time | `factory/stop` on the control issue #2188 | The kill switch: every task stops, intake pauses. `factory/revert` is still honoured, but a task already `Stopped` cannot be reverted by the factory |
| After the merge | `factory/revert` on the PR (Step 5) | The merger's revert PR. If it stalls, `merge.verifyFor` later its auto-merge is turned off: merge or close it by hand |
| The merge is wrong and the factory is stopped | Revert it yourself (GitHub's **Revert** button) and merge that PR | The breaker cannot see it until you add `factory/revert-of:#<PR>` to it |
| End the live window at once | Revert the cloud-native-ref pin bump (back to the previous ai-native-ref release, already verified) | Both classes back in shadow within one Flux reconcile; no ai-native-ref release needed |

## Results

Fill in during the drill.

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| P1–P5 | `v0.14.0`+; GitHub boxes ticked, mint `201`; idle; `main` green; no auto-merge today | | |
| 1 | both classes `{live: true}`, cap 1, rollout complete | | |
| 2 | task `docs-links`, PR opened | | |
| 3 | `AutoMerging` → `Verifying` | | |
| 4 | merged by the merger at the task's `headSHA`, `Agent-Run` trailer, `factory/auto-merged:docs-links` | | |
| 5 | revert PR by the merger, `factory/revert-of:#<PR>`, auto-merged; `ClassDemoted` on #2188 | | |
| 6 | both classes `{shadow: true}`, cap 10 | | |
| G1 | after the restart, `class_paused` | | |
