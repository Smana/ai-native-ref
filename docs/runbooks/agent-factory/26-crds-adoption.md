# 26 — Hand the factory's CRDs to `agent-factory-crds`

Moves the six `maku.ogenki.io` CRDs (Rooms, AgentRuns, Tasks, Factories, Repositories,
MergePolicies) to their own Helm release, `agent-factory-crds` in `agent-system`
(`tooling/base/agent-factory/crds`). Maku v4 step 8 needs it: the factory's chart stops carrying
CRDs. Run it once per live cluster (gcp-0 first, then aws-0 when it is up). It does not apply to a
fresh bootstrap: there, Helm creates the CRDs.

**Why it is manual.** Deleting a CRD deletes every object of its kind: every Task, Room, Factory,
Repository and MergePolicy. Helm takes over an existing CRD only when the CRD already names the
release, so these steps label each CRD first. Nothing in this change deletes a CRD:

| CRD | Today | After |
|---|---|---|
| `rooms` | `room-broker` (vendored `crd-rooms.yaml`) | Both `room-broker` and the release apply the same object. The file carries the release's labels and `kustomize.toolkit.fluxcd.io/prune: disabled`, so Flux labels it for Helm and never deletes it when a later change drops the file |
| `tasks`, `factories`, `repositories`, `mergepolicies` | `agent-factory`'s chart `crds/`, `crds: CreateReplace` | The release. `agent-factory` moves to `crds: Skip`, which never deletes a CRD |
| `agentruns` | Absent (the runs use `agentruns.cloud.ogenki.io`, Crossplane's) | Created, empty |

Every CRD the chart renders carries `helm.sh/resource-policy: keep` (`values.keep: true`), so an
uninstall leaves it. The HelmRelease has no remediation: a failed install stays failed and never
uninstalls. Flux orders the children: `room-broker`, then `agent-factory-crds`, then
`agent-factory` and `agent-factory-resources`.

## 1. Prerequisites

- [ ] The pull request that adds `agent-factory-crds` is open and still a draft.
- [ ] `kubectl` points at the cluster (`kubectl config current-context`), with rights to label CRDs.
- [ ] `agent-factory` is Ready on its current pin: `flux get helmreleases -n agent-system agent-factory`.

## 2. Record the CRDs and count every object

```bash
mkdir -p ~/crds-adoption && cd ~/crds-adoption
kubectl get crd -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,CREATED:.metadata.creationTimestamp \
  | grep -E '^NAME|\.maku\.ogenki\.io' | tee crds-before.txt
for crd in $(kubectl get crd -o name | grep '\.maku\.ogenki\.io$' | cut -d/ -f2); do
  echo "$crd $(kubectl get "$crd" -A --no-headers 2>/dev/null | wc -l)"
done | sort | tee counts-before.txt
kubectl get tasks.maku.ogenki.io,factories.maku.ogenki.io,repositories.maku.ogenki.io,mergepolicies.maku.ogenki.io,rooms.maku.ogenki.io \
  -A -o yaml > objects-before.yaml
```

Expected: five CRDs (`agentruns` absent), a count for each, and `objects-before.yaml` as the restore
copy. Keep the three files until step 6 passes.

## 3. Label the four factory CRDs for the release

Run it just before the rollout in step 4. `agent-factory`'s current `crds: CreateReplace` replaces
these CRDs on any of its upgrades, which drops the labels. Do not label `rooms`: the pull request
labels it through Flux, which would revert a `kubectl` label.

```bash
crds="crd/tasks.maku.ogenki.io crd/factories.maku.ogenki.io crd/repositories.maku.ogenki.io crd/mergepolicies.maku.ogenki.io"
# Only if step 2 listed agentruns.maku.ogenki.io:
# crds="$crds crd/agentruns.maku.ogenki.io"
kubectl label $crds app.kubernetes.io/managed-by=Helm --overwrite
kubectl annotate $crds meta.helm.sh/release-name=agent-factory-crds \
  meta.helm.sh/release-namespace=agent-system helm.sh/resource-policy=keep --overwrite
kubectl get crd -o custom-columns='NAME:.metadata.name,BY:.metadata.labels.app\.kubernetes\.io/managed-by,RELEASE:.metadata.annotations.meta\.helm\.sh/release-name,NS:.metadata.annotations.meta\.helm\.sh/release-namespace,KEEP:.metadata.annotations.helm\.sh/resource-policy' \
  | grep -E '^NAME|\.maku\.ogenki\.io'
```

Expected: the four rows read `Helm  agent-factory-crds  agent-system  keep`. `rooms` still shows
`<none>`: step 4 sets it.

## 4. Roll out

1. Mark the pull request ready, merge it, and cut the ai-native-ref release.
2. Bump the host's `ai-native-ref` pin to that release (a cloud-native-ref pull request).
3. Watch the children in order:

   ```bash
   flux get kustomizations room-broker agent-factory-crds agent-factory agent-factory-resources --watch
   ```

   Expected: `room-broker` Ready first, then `agent-factory-crds`, then the other two.

If `agent-factory-crds` fails with `... exists and cannot be imported into the current release`,
a CRD lost its labels. Nothing was deleted. Repeat step 3 for the CRD it names (for `rooms`, check
that `room-broker` is Ready on the new revision), then
`flux reconcile helmrelease -n agent-system agent-factory-crds`.

## 5. Check the release owns every CRD

```bash
helm -n agent-system list --filter agent-factory-crds
kubectl get crd -l app.kubernetes.io/part-of=agent-factory \
  -o custom-columns='NAME:.metadata.name,RELEASE:.metadata.annotations.meta\.helm\.sh/release-name,KEEP:.metadata.annotations.helm\.sh/resource-policy'
```

Expected: the release `deployed`, and six CRDs, each `agent-factory-crds  keep`.

## 6. Prove no object was lost

```bash
cd ~/crds-adoption
kubectl get crd -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,CREATED:.metadata.creationTimestamp \
  | grep -E '^NAME|\.maku\.ogenki\.io' > crds-after.txt
for crd in $(kubectl get crd -o name | grep '\.maku\.ogenki\.io$' | cut -d/ -f2); do
  echo "$crd $(kubectl get "$crd" -A --no-headers 2>/dev/null | wc -l)"
done | sort > counts-after.txt
diff crds-before.txt crds-after.txt; diff counts-before.txt counts-after.txt
```

Expected: one added line in each diff, `agentruns.maku.ogenki.io` (count 0), and no other change.
Each CRD keeps its UID and creation time: Helm adopted it in place. A count that moved by the
factory's normal traffic (a new Task) is fine; a count of 0 where there were objects is not:
stop and go to [Restore](#restore).

Then check the factory serves: `kubectl -n agent-system get factories,repositories,mergepolicies`
lists the same objects, and `flux get helmreleases -n agent-system agent-factory` is Ready.

## Rollback

Revert the pull request, release, and bump the host pin back. What happens:

- The `agent-factory-crds` child is pruned, its HelmRelease deleted, the release uninstalled. Every
  CRD carries `keep`, so Helm leaves it. Check that first: step 5's second command must show `keep`
  on all six.
- `agent-factory` returns to `crds: CreateReplace` and owns its four CRDs again on its next upgrade.
- `room-broker` applies `crd-rooms.yaml` without the release's metadata. The file stays in that
  child, so Flux does not prune the CRD.
- `agentruns.maku.ogenki.io` stays, empty. Delete it only after
  `kubectl get agentruns.maku.ogenki.io -A` lists nothing.

Run step 6 again after the rollback: the UIDs and counts match `crds-before.txt` and
`counts-before.txt`.

## Restore

Only if a CRD was deleted. Let Flux recreate it (`flux reconcile kustomization agent-factory-crds`),
then reapply the saved objects without their server-set fields:

```bash
yq 'del(.items[].metadata.uid, .items[].metadata.resourceVersion, .items[].metadata.creationTimestamp, .items[].metadata.managedFields, .items[].status)' \
  ~/crds-adoption/objects-before.yaml | kubectl apply -f -
```

The controllers rebuild their status; Flux reapplies the Factory, Repositories and MergePolicies
on its own. A Room's log lives in the broker's database, not in the Room, so it
survives.
