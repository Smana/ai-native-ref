# 01 — Runtime and sandbox

Proves that an `AgentRun` boots a gVisor-sandboxed pod on the dedicated `agents-gvisor` pool (a GKE
Sandbox node pool on gcp-0, a Karpenter pool on aws-0), that admission control rejects a pod or a run
not created by its one creator, that the harness has no Kubernetes API access, and that a lost pod
fails its run closed (R7). On aws-0 it also proves the pinned `runsc` release is installed correctly;
on gcp-0 Google manages `runsc`. See [README.md](README.md) for prerequisites and `CLOUD`; run
[00](README.md#runbook-00-one-time-cluster-setup) first.

Runs are `maku.ogenki.io` AgentRuns named `run-<id>` in `agents`, rendered by Maku's run-controller in
the `room-broker` release (R3). `task agent:run` prints the 8-character id; the AgentRun, its
ServiceAccount and its pod are all `run-<id>`. The commands name the resource in full,
`agentruns.maku.ogenki.io`: a cluster that still serves the Crossplane `AgentRun` XRD would make the
short name ambiguous.

## Prerequisites

- Runbook 00's first check passes (`main` tracked, both umbrellas `Ready`).
- No owner action specific to this runbook. No run is suspendable (owner ruling Q10).

## Steps

### Step 1 — confirm the platform is up

```bash
KS='agent-platform|agent-runtime|agent-policies|agent-factory-crds|room-broker'
[ "$CLOUD" = aws ] && KS="$KS|agents-nodepool|runtimeclass-gvisor"   # GKE provides both on gcp-0
flux get kustomizations -n flux-system | grep -E "^($KS)[[:space:]]"
kubectl get runtimeclass gvisor -o jsonpath='{.handler}{"\n"}'
kubectl get crd agentruns.maku.ogenki.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}{"\n"}'
kubectl get deploy -n agent-system -o name | grep -E 'run-controller|egress-proxy'
kubectl get resourcequota -n agents
```

Expected: every listed Kustomization `Ready=True` (5 on gcp-0, 7 on aws-0); `gvisor` on gcp-0 or
`runsc` on aws-0; `True`; the run-controller and egress-proxy Deployments; the runs quota.

**What this proves:** the umbrella and its children reconciled, the `AgentRun` CRD is installed, and
the run-controller, its egress proxy and the runs quota are in place.

### Step 2 — start a run and time the node (Q1)

```bash
T0=$(date +%s)
ID=$(task agent:run -- --role implementer --class public --task "Run 'sleep 900' in the terminal, then finish. Change nothing." | tail -1); RUN=run-$ID; echo "$RUN"
kubectl wait -n agents agentruns.maku.ogenki.io/$RUN --for=jsonpath='{.status.phase}'=Running --timeout=15m
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
glibc ≥ 2.34 thread start; see gvisor#14688). The run pod policy refuses `kubectl debug`; `kubectl
exec` is not an ephemeral container and still works.

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

Expected: `No such file or directory`, `exit=2`; a connection or timeout error, `exit=1` —
`automountServiceAccountToken: false` on the run's ServiceAccount and pod, and no API server egress in
the run's NetworkPolicy.

**What this proves:** SC-08.

### Step 6 — SC-03: admission rejects a pod and a run from anyone but their creator

Maku's ValidatingAdmissionPolicies admit a pod in `agents` only from the run-controller, and an
`AgentRun` only from the factory. Both dry runs below are made as you, so both are refused, whatever
their shape.

```bash
kubectl apply --dry-run=server -n agents -f - <<'YAML' 2>&1 | grep -c 'only the run-controller'
apiVersion: v1
kind: Pod
metadata: {name: sc03-pod}
spec:
  runtimeClassName: gvisor
  automountServiceAccountToken: false
  securityContext: {runAsNonRoot: true, runAsUser: 10001, seccompProfile: {type: RuntimeDefault}}
  containers:
    - name: c
      image: busybox
      securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
YAML
kubectl apply --dry-run=server -f - <<'YAML' 2>&1 | grep -c 'only the factory creates AgentRuns'
apiVersion: maku.ogenki.io/v1alpha1
kind: AgentRun
metadata: {name: run-7f3cq2xz, namespace: agents}
spec: {role: implementer, repository: Smana/cloud-native-ref, principal: "human:1", dataClass: public, task: {text: x}}
YAML
kubectl apply --dry-run=server -f - <<'YAML' 2>&1 | grep -c "should match '^agent/"
apiVersion: maku.ogenki.io/v1alpha1
kind: AgentRun
metadata: {name: run-7f3cq2xz, namespace: agents}
spec: {role: implementer, repository: Smana/cloud-native-ref, principal: "human:1", dataClass: public, branch: main, task: {text: x}}
YAML
```

Expected: `1`, `1` and `1`. The third run is refused by the CRD's schema (`spec.branch` must start
with `agent/`) before any admission policy runs. If a `0` prints, re-run without the `grep` and read
which control denied it. Not yet recorded on the run-controller.

**What this proves:** SC-03.

### Step 7 — R7: a lost pod ends the run, and a new run resumes its branch

A lost pod (spot interruption, eviction, `kubectl delete`) ends its run as `Failed`, reason
`PodLost`. The run-controller never re-creates a run's pod (`restartPolicy: Never`); recovery is a new
run on the same branch.

```bash
BRANCH=$(kubectl get agentruns.maku.ogenki.io -n agents $RUN -o jsonpath='{.status.branch}'); echo "$BRANCH"
kubectl delete pod -n agents $RUN --wait=true
kubectl wait -n agents agentruns.maku.ogenki.io/$RUN --for=jsonpath='{.status.phase}'=Failed --timeout=2m
kubectl get agentruns.maku.ogenki.io -n agents $RUN -o jsonpath='{.status.phase} {.status.reason}{"\n"}'
kubectl get pod -n agents $RUN 2>&1 | tail -1
ID2=$(task agent:run -- --role implementer --class public --branch "$BRANCH" --task "Run 'sleep 600' in the terminal, then finish. Change nothing." | tail -1); RUN2=run-$ID2
kubectl wait -n agents agentruns.maku.ogenki.io/$RUN2 --for=jsonpath='{.status.phase}'=Running --timeout=15m
kubectl get agentruns.maku.ogenki.io -n agents $RUN2 -o jsonpath='{.status.branch}{"\n"}'
```

Expected:
- `Failed PodLost`;
- `Error from server (NotFound)` for the old pod, a minute later still;
- the new run `Running` on the same `$BRANCH`.

**What this proves:** R7 as built. A lost pod fails closed, and `agent-run --branch` resumes the work; a factory run resumes on its own ([10](10-disruption.md)).

### Cleanup

```bash
kubectl delete agentruns.maku.ogenki.io -n agents $RUN $RUN2 --wait
kubectl get sa,cm,secret,networkpolicy,pod -n agents -o name | grep -E "run-($ID|$ID2)"
```

Expected: nothing (this doubles as an early look at SC-14, fully proven in runbook 07).

## Results

The rounds below ran on the Crossplane `AgentRun` XR (`xplane-run-<id>`), before R3.

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
