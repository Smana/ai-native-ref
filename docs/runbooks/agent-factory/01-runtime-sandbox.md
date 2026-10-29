# 01 — Runtime and sandbox

Proves that an `AgentRun` boots a gVisor-sandboxed pod on the dedicated `agents-gvisor` pool (a GKE
Sandbox node pool on gcp-0, a Karpenter pool on aws-0), that admission control rejects a malformed
pod or claim before it can run, that the harness has no Kubernetes API access, and that a lost pod
fails its run closed (R7). On aws-0 it also proves the pinned `runsc` release is installed correctly;
on gcp-0 Google manages `runsc`. See [README.md](README.md) for prerequisites and `CLOUD`; run
[00](README.md#runbook-00-one-time-cluster-setup) first.

## Prerequisites

- Runbook 00's first check passes (`main` tracked, both umbrellas `Ready`).
- No owner action specific to this runbook, except Step 8: the owner decides its approval in the room.

## Headroom: off by default, on for production

The warm-node headroom (`agents-headroom`, namespace `agent-system`) ships at `replicas: 0`: $0
idle, and the first run on an empty pool starts cold (~1.5–3.5 min). A production platform turns
it on for ~16 s starts at ~$126 a month per `e2-standard-8` spot node.

| | |
|---|---|
| Switch on | `spec.replicas: 1` in [`headroom/deployment.yaml`](../../../infrastructure/base/karpenter-nodepools-agents/headroom/deployment.yaml), shared by every cluster; `0` turns it off |
| Check | `kubectl get pods -n agent-system -l app.kubernetes.io/name=agents-headroom -o wide`: one pod `Running` on an `agents-gvisor` node |
| Options and costs | [Design: headroom off by default, on for production](../../superpowers/specs/2026-10-16-v2-warm-sandboxes-design.md#headroom-off-by-default-on-for-production) |

With the headroom off, Step 2 measures the cold path every time.

## Steps

### Step 1 — confirm the platform is up

```bash
KS='agent-platform|agent-sandbox|agent-runtime|agent-policies'
[ "$CLOUD" = aws ] && KS="$KS|agents-nodepool|runtimeclass-gvisor"   # GKE provides both on gcp-0
flux get kustomizations -n flux-system | grep -E "^($KS)[[:space:]]"
kubectl get runtimeclass gvisor -o jsonpath='{.handler}{"\n"}'
kubectl get xrd agentruns.cloud.ogenki.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}{"\n"}'
kubectl auth can-i --as=system:serviceaccount:crossplane-system:crossplane create sandboxes.agents.x-k8s.io -n agents
```

Expected: every listed Kustomization `Ready=True` (4 on gcp-0, 6 on aws-0); `gvisor`
on gcp-0 or `runsc` on aws-0; `True`; `yes`.

**What this proves:** the umbrella and its children reconciled, the `AgentRun` XRD is installed, and
Crossplane's aggregate ClusterRole (`agent-sandbox:aggregate-to-crossplane`) actually grants it
`Sandbox` writes.

### Step 2 — start a run and time the node (Q1)

```bash
T0=$(date +%s)
RUN=$(task agent:run -- --role implementer --class public --task "Run 'sleep 900' in the terminal, then finish. Change nothing." | tail -1); echo "$RUN"
kubectl wait -n agents agentrun/$RUN --for=jsonpath='{.status.phase}'=Running --timeout=15m
NODE=$(kubectl get pod -n agents $RUN -o jsonpath='{.spec.nodeName}')
kubectl get node "$NODE" -o jsonpath='{range .status.conditions[?(@.type=="Ready")]}{.lastTransitionTime}{"\n"}{end}'
kubectl get pod -n agents $RUN -o jsonpath='{.status.startTime}{"\n"}'
echo "elapsed: $(( $(date +%s) - T0 )) s"
kubectl get events -n agents --field-selector involvedObject.name=$RUN,reason=FailedCreatePodSandBox -o name | wc -l
```

Expected: `Running`; a node Ready timestamp shortly before the pod's `startTime`; the
`FailedCreatePodSandBox` count small (0–1) and not climbing if you re-run the last line a minute
later. The phase-0 spike measured ~34 s node-Ready-to-container-start and ~90 s submission-to-start
on a fresh node — a first run on an empty pool should land in the same range, not minutes longer.

**What this proves:** Q1 — no unresolved race between kubelet coming up and the node's gVisor and
Cilium setup finishing on a freshly launched `agents-gvisor` node.

### Step 3 — SC-01: the pod is actually sandboxed

```bash
kubectl get pod -n agents $RUN -o jsonpath='{.spec.runtimeClassName} {.spec.nodeName}{"\n"}'
LABEL='sandbox\.gke\.io/runtime'; [ "$CLOUD" = aws ] && LABEL='agents\.ogenki\.io/runtime'
kubectl get node "$NODE" -o jsonpath="{.metadata.labels.$LABEL}"; echo
kubectl exec -n agents $RUN -c harness -- dmesg | head -3
kubectl exec -n agents $RUN -c harness -- grep Seccomp /proc/self/status
```

Expected: `gvisor <node>`; `gvisor`; a `Starting gVisor...` banner line; `Seccomp: 0` (`oci-seccomp`
is deliberately off — gVisor does not honour `errnoRet`, so `RuntimeDefault` would block every
glibc ≥ 2.34 thread start; see gvisor#14688).

**What this proves:** SC-01.

### Step 4 — SC-02: runsc is registered correctly on the node (aws-0 only)

On gcp-0 this step is N/A: GKE Sandbox installs and versions `runsc` itself, and Step 1's
RuntimeClass plus Step 3's node label and gVisor banner are the evidence. On aws-0:

```bash
kubectl debug node/"$NODE" -n default --profile=general --image=public.ecr.aws/amazonlinux/amazonlinux:2023 -- chroot /host bash -c '
  /usr/local/bin/runsc --version | head -1
  containerd config dump | grep -A4 "runtimes.runsc"
  cat /etc/containerd/runsc.toml'
sleep 20; kubectl logs -n default "$(kubectl get pods -n default -o name | grep node-debugger | head -1)"
kubectl get pods -n default -o name | grep node-debugger | xargs -r kubectl delete -n default
```

Expected: `runsc version release-20260921.0`; the runsc runtime under the **v3** CRI plugin id with
`ConfigPath = "/etc/containerd/runsc.toml"`; `oci-seccomp = "false"`.

**What this proves:** SC-02.

### Step 5 — SC-08: the harness has no Kubernetes API access

```bash
kubectl exec -n agents $RUN -c harness -- ls /var/run/secrets/kubernetes.io ; echo "exit=$?"
kubectl exec -n agents $RUN -c harness -- /usr/local/bin/python -c "import urllib.request; urllib.request.urlopen('https://kubernetes.default.svc', timeout=5)" ; echo "exit=$?"
```

Expected: `No such file or directory`, `exit=2`; a connection/name-resolution or timeout error,
`exit=1` — `automountServiceAccountToken: false` on the composed ServiceAccount and no `kube-apiserver`
egress in the run's CNP.

**What this proves:** SC-08.

### Step 6 — SC-03: admission rejects a bad pod and a bad claim

Both test pods below carry a full restricted `securityContext` on purpose — PSS `restricted` runs
before Kyverno and would otherwise deny them first, proving nothing about `agents-pod-shape`.

```bash
kubectl apply --dry-run=server -n agents -f - <<'YAML' 2>&1 | grep -c 'every pod in agents runs under RuntimeClass gvisor'
apiVersion: v1
kind: Pod
metadata: {name: sc03-runc}
spec:
  automountServiceAccountToken: false
  securityContext: {runAsNonRoot: true, runAsUser: 10001, seccompProfile: {type: RuntimeDefault}}
  containers:
    - name: c
      image: busybox
      securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
YAML
kubectl apply --dry-run=server -n agents -f - <<'YAML' 2>&1 | grep -c 'a pod in agents never mounts a Kubernetes API token'
apiVersion: v1
kind: Pod
metadata: {name: sc03-token}
spec:
  runtimeClassName: gvisor
  automountServiceAccountToken: true
  securityContext: {runAsNonRoot: true, runAsUser: 10001, seccompProfile: {type: RuntimeDefault}}
  containers:
    - name: c
      image: busybox
      securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
YAML
```

Expected: `1` and `1` (each pod denied by `agents-pod-shape` with its own message). If a `0` prints,
re-run without the `grep` and read which admission control actually denied it.

Write `/tmp/agentrun-bad.yaml` (Write tool, not a heredoc):

```yaml
apiVersion: cloud.ogenki.io/v1alpha1
kind: AgentRun
metadata: {name: xplane-run-7f3cq2xz, namespace: agents}
spec: {role: implementer, repository: Smana/cloud-native-ref, principal: "human:1", dataClass: public, branch: main, task: {text: x}}
---
apiVersion: cloud.ogenki.io/v1alpha1
kind: AgentRun
metadata: {name: run-1, namespace: agents}
spec: {role: implementer, repository: Smana/cloud-native-ref, principal: "human:1", dataClass: public, task: {text: x}}
```

```bash
kubectl apply --dry-run=server -f /tmp/agentrun-bad.yaml
```

Expected: both claims denied — the first for `spec.branch: main` (must start with `agent/`, an XRD
OpenAPI `pattern` constraint, not CEL — the error reads `spec.branch in body should match
'^agent/[a-z0-9][a-z0-9._/-]{0,100}$'`), the second for its name (must match
`^xplane-run-[a-z2-7]{8}$` — the XRD's own CEL rule fires first and reads exactly `an AgentRun is
named xplane-run-<runId>, runId being 8 characters of [a-z2-7]`; the `agentrun-admission` Kyverno
policy carries the identical message as a second layer, but the CRD-level CEL check rejects the
object before any webhook runs, so Kyverno's copy is never the one you actually see here). Record
each denial message.

> Corrected 2026-09-27: the branch check is a schema `pattern`, not a CEL rule — the error format
> differs from the name check's CEL message. Verified live: both denied as above (dry-run=server).

**What this proves:** SC-03.

### Step 7 — R7: a lost pod ends the run, and a new run resumes its branch

A lost pod (spot interruption, eviction, `kubectl delete`) ends its run as `Failed`. It does not come
back. The Sandbox controller does try to recreate it, but first the pod passes through phase `Failed`.
agent-sandbox v1.0.3 then reports `Finished=PodFailed`, the same as for a crash. The composition
latches `Failed` and withholds the run's ServiceAccount, so the recreate is refused. That is the
fail-closed design. Recovery is a new run on the same branch.

```bash
BRANCH=$(kubectl get agentrun -n agents $RUN -o jsonpath='{.status.branch}'); echo "$BRANCH"
kubectl delete pod -n agents $RUN --wait=true
kubectl wait -n agents agentrun/$RUN --for=jsonpath='{.status.phase}'=Failed --timeout=2m
kubectl get agentrun -n agents $RUN -o jsonpath='{.status.phase} {.status.reason}{"\n"}'
kubectl get sa -n agents $RUN 2>&1 | tail -1
RUN2=$(task agent:run -- --role implementer --class public --branch "$BRANCH" --task "Run 'sleep 600' in the terminal, then finish. Change nothing." | tail -1)
kubectl wait -n agents agentrun/$RUN2 --for=jsonpath='{.status.phase}'=Running --timeout=15m
kubectl get agentrun -n agents $RUN2 -o jsonpath='{.status.branch}{"\n"}'
```

Expected:
- `Failed PodLost` (a plain delete leaves no `DisruptionTarget`; the composition sees the pod deleted);
- `Error from server (NotFound)` for the old run's ServiceAccount;
- the new run `Running` on the same `$BRANCH`.

The controller's `serviceaccount "xplane-run-<id>" not found` log line is the withheld ServiceAccount
refusing the recreate, not an error.

> Known issue (F12, round 9): a deleted pod can come back within ~1 s while the run stays `Running`,
> and the harness re-runs the task; the `kubectl wait … Failed` then times out. Seen on a run with a
> `roomRef` on `147819ff`; round 7 on a run without one still passed. Delete the run rather than
> waiting it out, and record the step as FAIL (F12).

**What this proves:** R7 as built. A lost pod fails closed, and `agent-run --branch` resumes the work; a factory run resumes on its own ([10](10-disruption.md)).

### Step 8 — suspend and resume a waiting run (gcp-0)

The live proof of the [warm-sandboxes design](../../superpowers/specs/2026-10-16-v2-warm-sandboxes-design.md#9-acceptance--live-proof-on-aws-0-owner-go)
rows S2–S4, on gcp-0, where suspend is on. A run in an **attended** room whose approval has
waited in an idle room for the broker's `suspend.after` (5 min) is suspended: its pod is deleted
and its `workspace` PVC kept. Once the approval is decided it resumes in a new gVisor pod, with the
same ServiceAccount and the same conversation.

| Piece | Where | What it does |
|---|---|---|
| Factory | `tooling/gcp-0/agent-factory/helm-values-suspend.yaml` | `sandbox.suspend.enabled`: a run created in an attended room gets `spec.suspendable: true`, immutable |
| Composition | crossplane-configuration ≥ v0.9.15 | A suspendable run: `workspace` on a PVC from the default class (`standard-rwo` on gcp-0), `AGENT_SUSPENDABLE=true` on the harness and the bridge, `operatingMode` from the `operating-mode` annotation |
| Broker | `infrastructure/gcp-0/room-broker/config.yaml` | `suspend: {enabled: true, after: 5m}`: writes `operating-mode` + `remaining-seconds` at suspend, `operating-mode` + `resumed-at` at resume |
| Grant | `room-broker-suspend` Kustomization | `patch` on `agentruns`, fenced by Kyverno's `agentrun-broker-patch-limit` to those three annotations of a suspendable run |
| Harness and bridge | Maku ≥ v0.15.2 | agent-run reattaches the conversation it finds on the PVC; the bridge answers the reloaded confirmation from the room's decision |

```bash
flux get kustomizations -n flux-system room-broker-suspend room-broker agent-factory
kubectl get validatingpolicy agentrun-broker-patch-limit -o jsonpath='{.status.conditionStatus.ready}{"\n"}'
```

Expected: the three `Ready=True`; `true`.

Open a new room in the rooms web view (`https://rooms.<private domain>`) on
`Smana/cloud-native-ref`, class `public`; its profile defaults to `attended`. Then start a run in it
whose task opens a pull request. In an attended room `forge.pr` asks a human.

```bash
ROOM=<room id from the web view>
SRUN=$(task agent:run -- --room "$ROOM" --role implementer --class public --task "Do not search for typos. Open docs/platform-constitution.md, reword one sentence for clarity (one line only), then commit, push and open a pull request. Change nothing else." | tail -1); echo "$SRUN"
kubectl get agentrun -n agents $SRUN -o jsonpath='{.spec.suspendable}{"\n"}'
kubectl wait -n agents agentrun/$SRUN --for=jsonpath='{.status.phase}'=Running --timeout=15m
kubectl get pod -n agents $SRUN -o jsonpath='{.spec.runtimeClassName} {.spec.serviceAccountName}{"\n"}'
kubectl get pvc -n agents workspace-$SRUN -o jsonpath='{.status.phase} {.spec.storageClassName}{"\n"}'
```

Expected: `true`; `Running`; `gvisor xplane-run-<id>`; `Bound standard-rwo`.

> The task names its file: an open-ended "find a typo" task on clean docs ran until the per-run
> token budget (2.2M tokens, `BudgetExhausted`, reason `budget-run`).

> Run the marker `kubectl exec` as soon as the approval appears: the run can suspend before a human
> gets there. If it does, the PVC uid unchanged across the suspend and a single conversation directory
> are the fallback evidence.

When the room page shows the pull-request approval pending, leave a marker on the PVC and wait
past `after`, keeping the room idle (a message resets the idle clock):

```bash
kubectl exec -n agents $SRUN -c harness -- sh -c 'date -u > /workspace/.suspend-proof; ls /workspace/conversations'
kubectl wait -n agents agentrun/$SRUN --for=jsonpath='{.status.phase}'=Suspended --timeout=10m
kubectl get agentrun -n agents $SRUN -o jsonpath='{.metadata.annotations.agents\.ogenki\.io/operating-mode} {.metadata.annotations.agents\.ogenki\.io/remaining-seconds}{"\n"}'
kubectl get pod -n agents $SRUN 2>&1 | tail -1
kubectl get pvc -n agents workspace-$SRUN -o jsonpath='{.status.phase}{"\n"}'
kubectl logs -n agent-system -l app.kubernetes.io/name=room-broker --prefix --tail=-1 | grep '"msg":"run suspended"' | tail -1
```

Expected:
- the conversation's directory (one 32-hex name);
- `Suspended` within about 6 min of the approval opening (5 min idle, then the broker's 15 s resync);
- `Suspended <seconds>`, under the tier's `runMinutes × 60`;
- `Error from server (NotFound)` for the pod;
- `Bound`: the PVC outlives the pod;
- the leader replica's `run suspended` line, naming the room and the run.

Now approve the pull request in the room page.

```bash
kubectl wait -n agents agentrun/$SRUN --for=jsonpath='{.status.phase}'=Running --timeout=15m
kubectl get agentrun -n agents $SRUN -o jsonpath='{.metadata.annotations.agents\.ogenki\.io/operating-mode} {.metadata.annotations.agents\.ogenki\.io/resumed-at}{"\n"}'
kubectl get pod -n agents $SRUN -o jsonpath='{.spec.runtimeClassName} {.spec.serviceAccountName} {.spec.activeDeadlineSeconds}{"\n"}'
kubectl exec -n agents $SRUN -c harness -- dmesg | head -3
kubectl exec -n agents $SRUN -c harness -- cat /workspace/.suspend-proof
kubectl wait -n agents agentrun/$SRUN --for=jsonpath='{.status.phase}'=Succeeded --timeout=30m
gh pr list -R Smana/cloud-native-ref --head "agent/$ROOM" --state all --json number,url
```

Expected:
- `Running` again, once the new pod is Ready;
- `Running <RFC 3339 UTC time>`: all three annotations are now set;
- `gvisor xplane-run-<id> <seconds>`: a new gVisor pod, same ServiceAccount, its deadline the
  `remaining-seconds` the broker wrote, not the full budget;
- the `Starting gVisor...` banner;
- the marker written before the suspend: the PVC came back, so nothing was re-cloned;
- `Succeeded`, and exactly one pull request: the approved call ran once. The room's first progress
  note after the resume starts with `(resumed)`.

Optional, S4: repeat with a fresh room and leave the approval undecided. The attended approval
expires at 30 min, the run resumes on the denial, the agent reads why, and the run ends with no
pull request.

**What this proves:** design rows S2 and S3 on gcp-0 under gVisor (S4 with the optional run). The
annotations, the PVC and the deadline carry the run across the pod's deletion, and nobody but the
room's decision continues the waiting call.

> If the run never suspends: `spec.suspendable` empty means the factory's flag did not reach the run
> (`kubectl get cm -n agent-system agent-factory-config -o yaml | grep -A2 sandbox`); a broker log
> `forbidden` means the grant is not applied; a Kyverno denial names the annotation it refused.

### Cleanup

```bash
kubectl delete agentrun -n agents $RUN $RUN2 $SRUN --wait
kubectl get sa,cm,cnp,sandbox,pod,usages.protection.crossplane.io -n agents -l agents.ogenki.io/run-id=${RUN#xplane-run-}
kubectl get pvc -n agents workspace-$SRUN 2>&1 | tail -1
```

Expected: `No resources found` (this doubles as an early look at SC-14, fully proven in runbook 07),
and `NotFound` for the suspendable run's PVC.

## Results

### Step 8 — gcp-0, 2026-10-18 (ai-native-ref v0.1.14)

**Suspend and resume pass on gcp-0 under gVisor** (design rows S2 and S3; S4 not run).

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| Pre-flight | Three `Ready=True`; policy `true`; suspend on | `room-broker-suspend`, `room-broker`, `agent-factory` `Ready=True`; `validatingpolicy agentrun-broker-patch-limit` ready=`true`; factory `sandbox.suspend.enabled` `true` | PASS |
| Run start | `true`; `Running`; PVC `Bound standard-rwo` | `xplane-run-r2mbw56k` in attended room `lr7e7kpk`, `spec.suspendable=true`, `Running` 06:13:55Z, workspace PVC `Bound standard-rwo` | PASS |
| Suspend | `Suspended` ~6 min after the approval; pod gone; PVC `Bound` | Approval opened ~06:14Z; broker `run suspended room=lr7e7kpk run=r2mbw56k remainingSeconds=6781` at 06:19:41Z; annotations `operating-mode=Suspended`, `remaining-seconds=6781`; pod gone 06:19:48Z; PVC `Bound` (uid `898caf65-1878-4d15-8d52-3bd88121f322`) | PASS |
| Marker | Written before the suspend | Not written: the run suspended before the owner ran it | N/A |
| Resume | New gVisor pod, same SA, deadline = `remaining-seconds`, same PVC | Owner approved; broker `run resumed` 06:21:26Z; annotations `Running 2026-10-18T06:21:26Z`; new pod uid `1b71533e…`, runtimeClass `gvisor`, SA `xplane-run-r2mbw56k`, `activeDeadlineSeconds=6781`; `Starting gVisor...`; same PVC uid; one conversation dir `d8cbb363990941aaa6dfa4633db3fd81` | PASS |
| Outcome | `Succeeded`, exactly one PR | `Succeeded`, 92,392 tokens, exactly one PR (Smana/cloud-native-ref#2499, closed afterwards as a test artifact) | PASS |
| Cleanup | `No resources found`; PVC `NotFound` | Both runs deleted; `agents` namespace left with only the `default` SA and the default-deny CNP; PVC gone | PASS |

Notes:
- The first attempt, `xplane-run-jede5jsq`, ended `BudgetExhausted`: the open-ended typo task, since reworded in Step 8.
- Steering from the room page is impossible for a CLI-started run: Smana/maku#147.
- The broker's `run resumed` log line carries an empty `remainingSeconds` (cosmetic).

### Round 7 — gcp-0, 2026-09-30 (`integration/agent-factory` @ `a2c645ba`)

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 1 — platform up | All `Ready=True`; XRD `True`; `yes` | `agent-platform`, `agent-sandbox`, `agent-runtime`, `agent-policies` `Ready=True`. `agents-nodepool` and `runtimeclass-gvisor` do not exist on gcp-0: the pool and the RuntimeClass are GKE-managed (`opentofu/gcp/gke/init/sandbox.tf`). XRD `Established=True`; `can-i` = `yes` | PASS |
| 2 — Q1 timing | Node Ready ≤ pod start; small `FailedCreatePodSandBox` count | `xplane-run-6qnowwxl`: node Ready `20:25:32Z`, pod start `20:27:57Z`, harness started `20:28:33Z`, 0 × `FailedCreatePodSandBox`, but submission to `Running` took 343 s. **The race Q1 asks about exists on gcp-0.** On a freshly scaled gVisor node, cilium-operator logged `Restarting unmanaged pod` for six of the ten run pods this round created (`4iv2rpdq`, `j2qh5avm`, `x5hf55tr`, `6qnowwxl`, `pttpamhs`, `x6jexfi4`), 53 s to 2 min 31 s after they started. Each of the six had landed on a node that was minutes old; the four that landed on a warm node were left alone. The pods tolerated `node.cilium.io/agent-not-ready` (a Kyverno mutate, since removed), so they landed before the Cilium agent was ready. A run whose pod is still Pending survives, because the Sandbox recreates the pod. A run that already reached `Running` fails for good, as R7 designs: `xplane-run-j2qh5avm` was `Running` at 20:19:12, its pod was deleted at 20:19:19, and the run ended `Failed PodFailed`. `xplane-run-pttpamhs` (the first SC-06 attempt) ended the same way. On a warm node, `zt7vyyi6` went from `Pending` to `Running` in 29 s | **FAIL** (F2 in `results-gcp-0-2026-09-30.md`; fixed by d9d75413 and 5b77d0db, passed in round 9) |
| 3 — SC-01 | `gvisor`/`gvisor`/gVisor banner/`Seccomp: 0` | `gvisor gke-gcp-0-nap-e2-standard-4-1h1w69k1-…`; node label `sandbox.gke.io/runtime=gvisor` (gcp-0 has no `agents.ogenki.io/runtime` label); `Starting gVisor...`; `Seccomp:\t0`; `uname -r` = `4.4.0` | PASS |
| 4 — SC-02 | pinned `runsc`, v3 plugin id, `oci-seccomp = "false"` | Not run. The step is AWS-shaped: its `amazonlinux` image, `/usr/local/bin/runsc` and `/etc/containerd/runsc.toml` do not apply to GKE Sandbox, where Google manages `runsc`. The privileged `kubectl debug node/…` adapted for GKE was refused by this session's permission classifier | [OWNER] |
| 5 — SC-08 | No `kubernetes.io` dir; API call fails | `ls: cannot access '/var/run/secrets/kubernetes.io': No such file or directory` exit=2; `urlopen('https://kubernetes.default.svc')` exit=1 | PASS |
| 6 — SC-03 pods | `1` and `1` | `1` and `1` | PASS |
| 6 — SC-03 claims | Both denied, correct messages | `spec.branch in body should match '^agent/[a-z0-9][a-z0-9._/-]{0,100}$'`; `an AgentRun is named xplane-run-<runId>, runId being 8 characters of [a-z2-7]` | PASS |
| 7 — R7 | `Failed PodFailed`; old SA NotFound; new run Running on `$BRANCH` | `xplane-run-6qnowwxl`: `BRANCH=agent/6qnowwxl`; `Failed PodFailed`; `serviceaccounts "xplane-run-6qnowwxl" not found`; `xplane-run-peiuqflu` Running, `spec=agent/6qnowwxl status=agent/6qnowwxl` | PASS |
| Cleanup | `No resources found` | `6qnowwxl`: `No resources found`. `peiuqflu`: CNP, pod (`Terminating`) and Usage still present right after `delete --wait` returned, which is the SC-07 ordering at work. All three were gone by the final sweep (see runbook 07, SC-14) | PASS |

Round 7 notes: the runbook's "Idle. Do nothing" task now finishes in about a minute (`x5hf55tr` `Succeeded` after 106 s), so runs that must stay up used `Run 'sleep N' in the terminal …`.

### Round 9 — gcp-0, 2026-10-01 (`integration/agent-factory` @ `147819ff`)

Not a full pass: Step 2's race was re-checked with the gVisor smoke probe, and Step 7 on a room run.

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 2 — F2 from zero | The pod waits for Cilium; no `Restarting unmanaged pod` | `agents-gvisor` resized to 0, then `scripts/ops/k8s/gvisor-smoke.yaml` (no Cilium toleration): scale-up 0→1, node Ready 07:40:45Z, operator cleared the `ignore-taint.cluster-autoscaler.kubernetes.io/cilium-agent-not-ready` taint at 07:41:38Z, pod started 07:41:38Z and `Succeeded`. `grep -c 'Restarting unmanaged pod'` → `0` on both operators. Side effect: `cilium-agent` OOM-killed at startup (F9, since fixed: 512Mi) | PASS |
| 7 — R7 | `Failed PodFailed` | `xplane-run-5sxrpflg` (room `crkdu3gx`): pod deleted at ~08:40:56, a new pod at 08:40:57Z, the run stayed `Running`, the harness re-ran the task. `kubectl wait … Failed --timeout=5m` timed out | **FAIL** (F12) |

### Earlier rounds — aws-0

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 1 — platform up | All `Ready=True`; XRD `True`; `yes` | All 6 Kustomizations `Ready=True`; XRD `Established=True`; `can-i` = `yes` | PASS |
| 2 — Q1 timing | Node Ready ≤ pod start; small `FailedCreatePodSandBox` count | Node Ready `23:44:45Z`, pod start `23:44:50Z` (5s after); submission-to-Running 178s; `FailedCreatePodSandBox` count `0` | PASS |
| 3 — SC-01 | `gvisor`/`gvisor`/gVisor banner/`Seccomp: 0` | `gvisor ip-10-0-23-81...`; node label `gvisor`; `Starting gVisor...`; `Seccomp:\t0` | PASS |
| 4 — SC-02 | `release-20260921.0`; v3 plugin id; `oci-seccomp = "false"` | `runsc version release-20260921.0`; `io.containerd.cri.v1.runtime`/runsc, `ConfigPath = '/etc/containerd/runsc.toml'`; `oci-seccomp = "false"` | PASS |
| 5 — SC-08 | No `kubernetes.io` dir; API call fails | `ls: cannot access ... No such file or directory` exit=2; `socket.gaierror: ... Temporary failure in name resolution` exit=1 | PASS |
| 6 — SC-03 pods | `1` and `1` | `1` and `1` (each pod also independently denied by `agents-pod-creator`, since the caller isn't the sandbox controller SA) | PASS |
| 6 — SC-03 claims | Both denied, correct messages | `spec.branch ... should match '^agent/...'` (schema pattern, not CEL — see correction above); `an AgentRun is named xplane-run-<runId>...` (XRD CEL) | PASS |
| 7 — R7 | `Failed PodFailed`; old SA NotFound; new run Running on `$BRANCH` | `xplane-run-rfguy2pm`: `BRANCH=agent/rfguy2pm`; `Failed PodFailed`; `serviceaccounts "xplane-run-rfguy2pm" not found`; `xplane-run-wimjedrr` Running with spec/status branch `agent/rfguy2pm agent/rfguy2pm` | PASS |
| Cleanup | `No resources found` | `No resources found` (sa/cm/cnp/sandbox/pod/usages) | PASS |
