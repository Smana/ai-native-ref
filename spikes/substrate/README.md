# Substrate spike

A time-boxed experiment on gcp-0, outside every umbrella: nothing here is applied by Flux. Plan,
status and results: [the spike doc](../../docs/superpowers/specs/2026-10-17-substrate-spike.md).
Every object created, and its cleanup: [`OBJECTS.md`](OBJECTS.md).

## Run

Set `KUBECONFIG` (gcp-0; the scripts refuse any other cluster) and `SUBSTRATE` (a v0.5.0 checkout of
agent-substrate/substrate with `ate-setup` and `kubectl-ate` built into `$SUBSTRATE/bin`), then:

| Script | Does | State on 2026-10-17 |
|---|---|---|
| `inventory.sh` | every object in the cluster, for the cleanup diff | taken before any write: `inventory-before.txt` |
| `1-images.sh` | builds and pushes every image to the spike's Artifact Registry repo | done |
| `2-base.sh` | namespaces, network policy, rustfs | applied |
| `3-install.sh` | the upstream installer | **refused by the permission classifier; the owner runs it** |
| `4-post-install.sh` | patches, WorkerPool, atespace, ActorTemplates | not run |

## Measure

```bash
export PATH=$SUBSTRATE/bin:$PATH          # kubectl ate
kubectl -n ate-system port-forward svc/atenet-router 18000:80 &
./measure.sh start openhands-cold 5       # M1
./measure.sh start openhands-warm 5       # M2
./measure.sh conversation                 # M3-M7
./measure.sh baseline 5                   # B1
```
