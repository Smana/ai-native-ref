# 03 — Egress

Proves the run's egress model: a default-deny `NetworkPolicy` per run, and Maku's egress proxy, which
holds each run's HTTPS to the hosts of its `maku.ogenki.io/egress` annotation (GitHub and the run's
egress profiles; the in-cluster model gateway is opened by the NetworkPolicy, not the proxy). An allowed host connects through the proxy, any other is refused by the
proxy, and a direct connection that skips it is dropped. See [README.md](README.md) for
prerequisites; run [00](README.md#runbook-00-one-time-cluster-setup) first.

DNS stays open to the run in this mode (`networkPolicies.mode: kubernetes`): a name outside the
allow-list still resolves, and DNS tunnelling is the residual risk. The Cilium DNS proxy checks of the
rounds below belonged to the per-run `CiliumNetworkPolicy` the runs had before R3.

## Prerequisites

- Runbook 00 done. No owner action.

## Steps

### Step 1 — start a run

```bash
ID=$(task agent:run -- --role implementer --class public --task "Run 'sleep 900' in the terminal, then finish. Change nothing." | tail -1); RUN=run-$ID; echo "$RUN"
kubectl wait -n agents agentruns.maku.ogenki.io/$RUN --for=jsonpath='{.status.phase}'=Running --timeout=15m
```

### Step 2 — the run's allow-list and policy

```bash
kubectl get pod -n agents $RUN -o jsonpath='{.metadata.annotations.maku\.ogenki\.io/egress}{"\n"}' | tr ',' '\n'
kubectl get networkpolicy -n agents -l agents.ogenki.io/run-id=$ID -o name
kubectl exec -n agents $RUN -c harness -- env | grep '^HTTPS_PROXY='
```

Expected: `host:port` pairs on 443 for GitHub (`github.com`, `api.github.com` and its content hosts)
and nothing else for a run with no egress profile; one NetworkPolicy for the run; the proxy's address
in `HTTPS_PROXY` (`NO_PROXY` keeps in-cluster Services off the proxy).

### Step 3 — allowed, refused and bypassed

```bash
kubectl exec -n agents $RUN -c harness -- git ls-remote https://github.com/Smana/cloud-native-ref HEAD
kubectl exec -n agents $RUN -c harness -- /usr/local/bin/python -c "import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)" ; echo "exit=$?"
kubectl exec -n agents $RUN -c harness -- /usr/local/bin/python -c "import socket; s=socket.create_connection(('example.com', 443), timeout=5)" ; echo "exit=$?"
```

Expected: a `HEAD` SHA; `exit=1` with `Tunnel connection failed: 403 Forbidden` (the proxy refuses a
host not on the run's allow-list); `exit=1` with a timeout (the NetworkPolicy drops a connection that
skips the proxy).

**What this proves:** SC-09 — allow and deny behave as the run's egress profile promises, and the
proxy is the only way out.

### Step 4 — the proxy's own record

```bash
kubectl logs -n agent-system deploy/egress-proxy --since=10m | grep -i "$ID\|example.com" | tail -5
```

Expected: a refusal for `example.com:443`, `not on the run's allow-list`. Not yet recorded on the
run-controller: note the exact log format in the results.

### Cleanup

```bash
kubectl delete agentruns.maku.ogenki.io -n agents $RUN --wait
```

## Results

The rounds below ran on the Crossplane `AgentRun` XR and its per-run `CiliumNetworkPolicy`, before R3.

### Round 7 — gcp-0, 2026-09-30 (`integration/agent-factory` @ `a2c645ba`)

Run `xplane-run-6qnowwxl`, on the NAP node `gke-gcp-0-nap-e2-standard-4-1h1w69k1-…` (`sandbox.gke.io/runtime=gvisor`).

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 2 — `git ls-remote` | A SHA | `299408d68b5cfb3fbc68b5564a453b8d76b0a796\tHEAD` | PASS |
| 2 — `example.com` | `exit=1` | `urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`, exit=1 | PASS |
| 2 — random `*.example.org` | `exit=1` | `socket.gaierror: [Errno -3] Temporary failure in name resolution`, exit=1 | PASS |
| 2 — `api.github.com` | An IP | `('140.82.121.5', 443)` | PASS |
| 3 — Hubble DNS | Allowed FORWARDED, denied REFUSED/DROPPED | `api.github.com` A+AAAA `dns-request proxy FORWARDED`; `example.com.agents.svc.cluster.local` and `6dc553fbd826.example.org` (plus its search-path forms) A+AAAA `dns-request proxy DROPPED` | PASS |
| 3 — Hubble DROPPED | No TCP reaches a denied host | Every `DROPPED` entry is a `dns-request proxy DROPPED`, with no TCP verdict toward any `example.*` address | PASS |

### Earlier rounds — aws-0

| Step | Expected | Observed | Pass/Fail |
|---|---|---|---|
| 2 — `git ls-remote` | A SHA | `674175608fa9bdcf05a44190748e8de6bcae94c6\tHEAD` | PASS |
| 2 — `example.com` | `exit=1` | `socket.gaierror: ... Temporary failure in name resolution`, exit=1 | PASS |
| 2 — random `*.example.org` | `exit=1` | Same `gaierror`, exit=1 | PASS |
| 2 — `api.github.com` | An IP | `('140.82.121.5', 443)` | PASS |
| 3 — Hubble DNS | Allowed FORWARDED, denied REFUSED/DROPPED | `github.com`/`api.github.com` A+AAAA `FORWARDED`; `example.com`/`*.example.org` A+AAAA `DROPPED` at the DNS proxy | PASS |
| 3 — Hubble DROPPED | No TCP reaches a denied host | All DROPPED entries are `dns-request proxy DROPPED`; no TCP verdict toward `example.com`/`example.org` IPs at all | PASS |
