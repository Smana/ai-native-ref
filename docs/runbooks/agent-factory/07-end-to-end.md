# 07 — End to end

The capstone: a real implementer run, on a real issue, opens a real PR within budget (SC-04); a
long-running read-only run's tokens survive without a single 401 across most of an hour (SC-06);
revoking a run by annotation drives it to `BudgetExhausted` (SC-13); and after deletion nothing tagged with the run's id survives anywhere in the cluster
(SC-14). This is the longest runbook — budget close to two hours, most of it waiting. See
[README.md](README.md) for prerequisites; run [00](README.md#runbook-00-one-time-cluster-setup) and
ideally 01, 03 and 04 first (they de-risk the pieces this one composes).

## Prerequisites

- Runbook 00 done.
- Owner actions 1–4 (OpenBao policy and role, Z.ai key, ruleset, GitHub App).
- **Owner action 5**: a trivial issue URL ready, exported as `ISSUE_URL`.

Runs are `maku.ogenki.io` AgentRuns named `run-<id>` (R3): `task agent:run` prints the id, and the
commands below name the resource in full, `agentruns.maku.ogenki.io`.

## Step 1 — confirm the harness pin

```bash
kubectl get helmrelease -n agent-system room-broker -o jsonpath='{.spec.values.runController.images.harness.tag}{"\n"}'
```

Expected: one line, `v<x.y.z>@sha256:…`: the harness of the Maku release the broker's chart runs,
pinned by digest in `infrastructure/base/room-broker/helmrelease.yaml`.

## Step 2 — SC-04: an implementer run ends in a PR within 30 minutes

```bash
ID=$(task agent:run -- --role implementer --class public --task-url "$ISSUE_URL" | tail -1); RUN=run-$ID; echo "$RUN"
date -u +%FT%TZ
kubectl wait -n agents agentruns.maku.ogenki.io/$RUN --for=jsonpath='{.status.phase}'=Succeeded --timeout=30m
kubectl get agentruns.maku.ogenki.io -n agents $RUN -o jsonpath='{.status.startedAt} {.status.finishedAt} {.status.branch}{"\n"}'
BRANCH=$(kubectl get agentruns.maku.ogenki.io -n agents $RUN -o jsonpath='{.status.branch}')
gh pr list --repo Smana/cloud-native-ref --head "$BRANCH" --json number,author,headRefName
PR=$(gh pr list --repo Smana/cloud-native-ref --head "$BRANCH" --json number --jq '.[0].number')
gh pr view --repo Smana/cloud-native-ref "$PR" --json commits --jq '.commits[].messageBody' | grep -c "Agent-Run: $ID"
```

Expected: `Succeeded` within 30 minutes of the printed start; one PR from `agent/<runId>` whose
author login is `app/ogenki-agents`; at least one commit carrying `Agent-Run: <runId>`. (Only the
factory sets `spec.branch` to `agent/<taskId>`; `task agent:run --task-url` leaves the
run-controller's default, `agent/<runId>`.)

If it fails: read `kubectl logs -n agents $RUN -c harness` and the model gateway's access log for the
run (`gateway-name:"model-gateway"`, `log.x_ar_agent:"system:serviceaccount:agents:$RUN"`) before
changing anything.

**What this proves:** SC-04 — the whole chain (run-controller → gVisor pod → model gateway → GLM-5.3,
and the factory's per-run git token → PR) works, unattended, inside the time budget.

Keep this PR open — it's the owner's to review, not to merge or close as part of this session.

## Step 3 — SC-06: a long run gets no 401s across its lifetime

```bash
LID=$(task agent:run -- --role implementer --class public \
  --task "Read every Markdown file under docs/superpowers/specs one at a time, and run 'sleep 110' in the terminal between two files. For each, list the relative links it contains. Stop after 45 minutes. Do not change, commit or push anything. Finish with the full list." | tail -1); LONG=run-$LID
kubectl wait -n agents agentruns.maku.ogenki.io/$LONG --for=jsonpath='{.status.phase}'=Running --timeout=15m
```

The factory sizes the run: a run started with `task agent:run` belongs to no task, carries no
tier, and runs for a fixed 120 minutes (SP3 §R47) — not a requested duration, so time Step 3's
checks against that.

At minute 45 or later (or at the run's end if it finishes sooner — record actual duration either
way):

```bash
Q="rate(gen_ai_client_token_usage_sum{ar_agent=\"system:serviceaccount:agents:$LONG\"}[5m])"
ENC=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$Q")
kubectl get --raw "/api/v1/namespaces/observability/services/vmsingle-victoria-metrics-k8s-stack:8428/proxy/api/v1/query?query=$ENC" | jq .
curl -sS --cacert opentofu/$CLOUD/openbao/management/.tls/ca.pem https://vl.priv.$CLOUD.ogenki.io/select/logsql/query --data-urlencode \
  "query=kubernetes.pod_namespace:\"agent-gateway\" AND kubernetes.pod_labels.gateway.networking.k8s.io/gateway-name:\"model-gateway\" _time:1h | unpack_json | log.x_ar_agent:\"system:serviceaccount:agents:$LONG\" | stats by (log.http.status) count() n"
```

Expected: the VM query confirms the run is actually making calls; the LogsQL result shows no `401`
bucket for this run at any point in its lifetime. Its model token lives until its 120-minute
deadline (`budget.maxMinutes`): nothing has to rotate. The `sleep 110` pacing keeps the run making
calls for most of the session; a run that finishes early still counts, so record its actual duration.

```bash
kubectl delete agentruns.maku.ogenki.io -n agents $LONG --wait
```

**What this proves:** SC-06 — a run's token lasts a realistic run length.

## Step 4 — SC-13: revocation by annotation

The run meter revokes a run at its cap by annotating it `agents.ogenki.io/revoked=<reason>`; the
run-controller ends a run whose reason is a budget reason as `BudgetExhausted`, and one marked
`manual` as `Revoked`. The `AgentRun` carries no `status.usage`, so the projection guards the
Crossplane XR had (a malformed `usage-tokens` never reaching status) are retired with it.

```bash
BID=$(task agent:run -- --role implementer --class public --task "Run 'sleep 600' in the terminal, then finish. Change nothing." | tail -1); B=run-$BID
kubectl wait -n agents agentruns.maku.ogenki.io/$B --for=jsonpath='{.status.phase}'=Running --timeout=15m
T0=$(date +%s); kubectl annotate agentruns.maku.ogenki.io -n agents $B agents.ogenki.io/revoked=budget-run
kubectl wait -n agents agentruns.maku.ogenki.io/$B --for=jsonpath='{.status.phase}'=BudgetExhausted --timeout=2m
until ! kubectl get pod -n agents $B >/dev/null 2>&1; do sleep 2; done; echo "BudgetExhausted, pod gone after $(( $(date +%s) - T0 )) s"
```

Expected: `BudgetExhausted` reached, with the pod gone ≤ 60 s after the `revoked=budget-run`
annotation. Not yet recorded on the run-controller.

**What this proves:** SC-13 — the revocation path the run meter drives at a run's cap tears the run
down.

## Step 5 — SC-14: nothing left after deletion

```bash
kubectl delete agentruns.maku.ogenki.io -n agents $B --wait
for r in $LONG $B; do
  echo "== $r =="
  kubectl get sa,cm,secret,networkpolicy,pod -n agents -o name | grep -E "^[a-z]+/$r(-|$)"
done
```

Expected: no line under either run.

**What this proves:** SC-14 — deletion is complete: no ServiceAccount, ConfigMap, git token Secret,
NetworkPolicy or pod outlives its `AgentRun`.

## Cleanup

Nothing further — every run this runbook created is already deleted except `$RUN`'s PR (Step 2),
which stays open for owner review.

## Results

The rounds below ran on the Crossplane `AgentRun` XR (`xplane-run-<id>`), before R3.

> Every round below predates phase H (#2429): gateway lines were read on Envoy's agent-router
> (`log.response_code`).

### Round 7 — gcp-0, 2026-09-30 (`integration/agent-factory` @ `a2c645ba`)

Only these rows were recorded on gcp-0.

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 1 — harness pin | The repo-built harness | `ghcr.io/smana/agent-harness:v0.1.0-pr2110.29b5f228@sha256:3cc93e00…` (crossplane-configuration `v0.7.2-pr31.988146f`) | PASS |
| 2 — SC-04 | `Succeeded` ≤ 30 min; PR by `app/ogenki-agents`; trailer present | `xplane-run-4iv2rpdq` took issue #2140 to PR #2141. Pod on `gke-gcp-0-agents-gvisor-0166ac85-plzh` (`sandbox.gke.io/runtime=gvisor`); `agent-router` `:8080` `200` ×10 and `:8082` (sts) `200` ×1 for its `x_ar_agent`, with the GKE-issued token accepted by `agent-router` and octo-sts | PASS |
| 5 — SC-14 | `No resources found` | Runbook 01's `xplane-run-peiuqflu`: CNP, pod and Usage still present right after `delete --wait` returned, all gone by the final sweep | PASS |

### Earlier rounds — aws-0

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 1 — harness pin | `1` (or `0`, noted) | `0` — composition still pins `ghcr.io/openhands/agent-server:1.49.5-python@sha256:1e7b0...`, not the repo-built harness (#2110 not landed, as expected) | PASS (the documented `0` outcome) |
| 2 — SC-04 (round 3, upstream image) | `Succeeded` ≤ 30 min; PR by `app/ogenki-agents`; trailer present | `xplane-run-n7tfcziv` on `#2112`: reached `phase=Running`, `conversationId=396c8ad6-...` allocated, but zero LLM calls, zero `agent-router` traffic, zero octo-sts activity, no PR after 8+ minutes idle — the task was never submitted at all (upstream image, no bootstrap) | BLOCKED (harness image, #2110) — historical, image now replaced |
| 2 — SC-04 (round 5, real harness `v0.1.0-pr2110.d8134ede`) | `Succeeded` ≤ 30 min; PR by `app/ogenki-agents`; trailer present | Real harness works — cloned, branched `agent/<id>`, started a conversation, called the model (`POST /api/paas/v4/chat/completions` → `200`, 4539ms, 8144 tokens metered by the gateway) — **then the OpenHands SDK itself crashes** parsing that response's usage: `AttributeError: 'PromptTokensDetailsWrapper' object has no attribute 'cache_creation_tokens'` in `openhands/sdk/llm/utils/telemetry.py:68` (`normalize_usage`). `phase=Failed`/`PodFailed` within ~30-45s of `Running`, every time. **Reproduced twice** (`xplane-run-3s7i55r7`, `xplane-run-mun2l7g2`), both on the very first model turn, before any git push — no octo-sts activity, no branch pushed to GitHub, no PR, no `status.usage`/`status.pullRequest`. See Platform findings | **FAIL** (platform bug, harness SDK, see Platform findings) |
| 1 — harness pin (round 6) | `1` | The live composition pins the pre-release harness `ghcr.io/smana/agent-harness:v0.1.0-pr2110.29b5f228@sha256:3cc93e00…` (crossplane-configuration PR #29, `v0.7.2-pr29.9d7d479`). The step's old grep for a plain `v0.1.0` tag could not match a pre-release pin; Step 1 now prints the tag | PASS |
| 2 — SC-04 (round 6, harness `v0.1.0-pr2110.29b5f228`) | `Succeeded` ≤ 30 min; PR by `app/ogenki-agents`; trailer present | `xplane-run-zma62cms` on `#2112`: `Pending` 07:44:06 → `Running` 07:46:17 → `Succeeded` 07:47:25. That is 68 s of agent work over 10 steps, visible in the step log in VictoriaLogs. PR **#2114** by `app/ogenki-agents` on `agent/zma62cms` changes one file; its body is `Fixes #2112` and commit 2e3b4f33 carries `Agent-Run: zma62cms`. CI went green after one public-ECR 429 rerun. The owner merged it (3dea2b7a), which closed `#2112`. Two harness fixes made the difference: OpenHands 1.49.6 with litellm `<1.95.1` (software-agent-sdk#5213), and `reasoning_effort` sent in the request body (litellm had dropped it, so GLM-5.3 ran at maximum thinking) | **PASS**. It supersedes rounds 3 and 5 |
| 3 — SC-06 (round 6) | No 401 bucket for the run's `x_ar_agent` | `xplane-run-hbrkmjrj`, 60-minute budget. The runbook's read-only task now finishes in about a minute, so the task paced itself with `sleep 110` between model calls. It ran 31 steps over 58 min (gateway traffic from 09:38:18 to 10:36:43Z): 44 × `200`, **0 × `401`**. The only other codes were MCP noise in the first minute (1 × `400` ping, agent-router#2715; 2 × `405` GET; 7 × `202`). The run ended `Failed`/`PodFailed` at its deadline because the agent overshot "stop after 50 min" by 5 steps; the 60-min deadline is enforced as designed | **PASS** |
| 4 — SC-13 negative | Empty `status.usage` | `xplane-run-lkorndmd`, after `usage-tokens=-5`: `status.usage` empty on every poll | PASS |
| 4 — SC-13 valid | `1234` | After `usage-tokens=1234` (overwrite): `status.usage.tokens` = `1234` immediately | PASS |
| 4 — SC-13 revoke | `BudgetExhausted`, pod gone ≤ 60 s | After `revoked=budget-run`: `phase=BudgetExhausted` reached, pod gone 4 s later | PASS |
| 5 — SC-14 | `No resources found` ×2 | `kubectl get sa,cm,cnp,sandbox,pod,usages.protection.crossplane.io -A -l agents.ogenki.io/run-id=<id>` for both `n7tfcziv` and `lkorndmd`: `No resources found`. `n7tfcziv` was round 3's SC-04 run, not a `$LONG`; round 6's `$LONG` (`hbrkmjrj`) was not recorded | PASS |

**Static verification (code on `main`):** the XRD's `status` schema has exactly `branch,
conversationId, finishedAt, phase, pullRequest, reason, runId, startedAt, usage.tokens`, and
`phase` enum is `Pending, Running, Succeeded, Failed, BudgetExhausted, Revoked` — matching every
`jsonpath` this runbook reads. `docs/superpowers/plans/2026-09-25-agent-runtime-identity-plan.md`
carries the composition's own KCL unit tests asserting `agents.ogenki.io/usage-tokens: "-5"` is
rejected and `agents.ogenki.io/revoked: "budget-run"` maps to `BudgetExhausted` — exactly the two
cases Step 4 exercises, now also confirmed live.
