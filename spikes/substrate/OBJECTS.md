# Objects the spike created

Cluster-scoped objects come from `inventory.sh` diffs against `inventory-before.txt`, taken before
any write. Namespaced ones live only in `ate-system`, `podcertificate-controller-system` and
`substrate-spike`, and go with them. Objects the cluster derives (pods, ReplicaSets,
CiliumEndpoints, PolicyReports, `default` ServiceAccounts, `kube-root-ca.crt`) are not listed.

## Outside the cluster

| Object | Created by | Delete |
|---|---|---|
| Artifact Registry repo `europe-west4-docker.pkg.dev/ogenki-435905/substrate-spike`: 16 ko images + `envoy-dataplane`, tag `v0.5.0` | the lead (repo), `1-images.sh` (images), 2026-10-17 | `gcloud artifacts repositories delete substrate-spike --location=europe-west4 --project=ogenki-435905 --quiet` |

## Step 2 (`2-base.sh`), applied 2026-10-17

| Kind | Namespace | Name |
|---|---|---|
| Namespace | | `ate-system` |
| Namespace | | `substrate-spike` |
| CiliumClusterwideNetworkPolicy | | `substrate-spike` |
| CiliumNetworkPolicy | `ate-system` | `atelet-egress` |
| NetworkPolicy | `ate-system` | `rustfs` |
| Secret | `ate-system` | `rustfs-credentials` (random, created by the script) |
| PersistentVolumeClaim | `ate-system` | `rustfs-data` (bound to PV `pvc-304aba6d-d14b-42a4-8104-ea8b20a56afd`, reclaim `Delete`) |
| Service | `ate-system` | `rustfs` |
| Deployment | `ate-system` | `rustfs` |
| Job | `ate-system` | `rustfs-bucket-init` |

Cleanup:

```bash
kubectl delete -k spikes/substrate/                            # all of the above, namespaces last
kubectl get pv pvc-304aba6d-d14b-42a4-8104-ea8b20a56afd        # NotFound once the PD is released
```

## Steps 3 and 4

Not run: the permission classifier refused `3-install.sh` on 2026-10-17. When they run, the
diff is appended here before any measurement. Their cleanup, in this order:

```bash
$SUBSTRATE/bin/kubectl-ate delete actor <name> -a substrate-spike --any-state   # each actor
$SUBSTRATE/bin/kubectl-ate delete actor-template openhands-cold -a substrate-spike
$SUBSTRATE/bin/kubectl-ate delete actor-template openhands-warm -a substrate-spike
$SUBSTRATE/bin/kubectl-ate delete atespace substrate-spike
kubectl -n substrate-spike delete workerpool openhands
(cd "$SUBSTRATE" && bin/ate-setup delete ate-system)
# then whatever the step 3-4 diff above still lists (CRDs, ClusterRoles, SandboxConfig, VAPs,
# ClusterTrustBundles, podcertificate-controller-system), then step 2's cleanup
```
