# Substrate spike

A time-boxed experiment on gcp-0, outside every umbrella: nothing here is applied by Flux. Plan,
status and results: [the spike doc](../../docs/superpowers/specs/2026-10-17-substrate-spike.md).
Every object created, and its cleanup: [`OBJECTS.md`](OBJECTS.md).

## Run

Set `KUBECONFIG` (gcp-0; the scripts refuse any other cluster) and `SUBSTRATE` (a v0.5.0 checkout of
agent-substrate/substrate with `ate-setup` and `kubectl-ate` built into `$SUBSTRATE/bin`), then:

| Script | Does | State |
|---|---|---|
| `inventory.sh` | every object in the cluster, for the cleanup diff | taken before any write: `inventory-before.txt` |
| `1-images.sh` | builds and pushes every image to the spike's Artifact Registry repo | done 2026-10-17 |
| `2-base.sh` | namespaces, network policy, rustfs | applied 2026-10-17 |
| `3-install.sh` | the upstream installer | run by the owner 2026-10-18, after the edit below |
| `4-post-install.sh` | patches, WorkerPool, atespace, ActorTemplates | run 2026-10-18, then `patches/pin.yaml` by hand |

Workers run on a temporary `substrate-gvisor` node pool, not `agents-gvisor`: a pool created before
gcp-0's beta APIs were enabled lacks the kubelet trust-bundle gates (the spike doc's finding 2).

### Upstream edit and hand patches

| What | Why |
|---|---|
| In `$SUBSTRATE`, `manifests/ate-install/postgres/postgres.yaml` line 258: `500Gi` → `20Gi`, before `3-install.sh` | 500Gi exceeds gcp-0's regional `SSD_TOTAL_GB` quota (500), so `postgres-0` stays Pending. The installer reads manifests from disk, so the local edit is enough |
| `patches/pin.yaml` on the control plane, after `4-post-install.sh` | keeps it on node pools whose kubelet has the gates |

```bash
for w in deployment/ate-api-server deployment/ate-controller daemonset/atelet; do
  kubectl -n ate-system patch "$w" --patch-file patches/pin.yaml
done
```

## Measure

```bash
export PATH=$SUBSTRATE/bin:$PATH          # kubectl ate
kubectl -n ate-system port-forward svc/atenet-router 18081:8081 &   # the CONNECT listener
./measure.sh start openhands-cold 5       # M1
./measure.sh start openhands-warm 5       # M2
./measure.sh conversation                 # M3-M7
./measure.sh baseline 5                   # B1
```
