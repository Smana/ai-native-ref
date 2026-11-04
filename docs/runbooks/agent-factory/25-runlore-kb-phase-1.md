# 25 — RunLore's knowledge base, phase 1: the live proofs

Phase 1 of [RunLore's knowledge base, filled by the agent factory](../../superpowers/specs/2026-11-03-runlore-kb-from-the-factory-design.md)
(RK1 to RK20). The factory investigates each incident RunLore reports; when the fix is merged and the alert
stays quiet, RunLore drafts a knowledge entry in `Smana/runlore-kb`, and the internal triager reads those
entries back through `kb_search` and `kb_get`. Phase 1 is `aws-0`, `Smana/cloud-native-ref` only, with a
person merging every fix and every entry. This runbook turns RunLore on for a live session and off after
(a session switch, RK15), and records four live checks and the phase 1 gate. It follows
[runbook 20](20-runlore-agent-to-agent.md), whose live 5 it reuses. See [README.md](README.md) for `CLOUD`.

Every command that runs `lore` in the pod passes `--config /etc/runlore/runlore.yaml`: the default,
`runlore.yaml`, is a path relative to a working directory the image does not set.

## What a repeat of an alert does

Alertmanager repeats a firing alert every hour (the `runlore` route). RunLore investigates every repeat,
which costs spend, and files nothing while a generation is undecided. The rules, which each live check relies on:

- A stub nobody publishes gets no newer stub until the curation window (7 days) has passed.
- A drafted entry with an open pull request and no fix files nothing on a repeat.
- A merged entry files again: the next generation starts. So does an entry pull request closed unmerged.
- A generation with a fix is decided by any verdict (`resolved` included), a refusal outcome, the fix being
  reverted, a regression, its fix room ending without a merge, or, while the fix is unmerged, the window
  passing. A merged fix keeps its soak past the window. Only a repeat that arrives after that starts the
  next generation.

Read the spend after the first session (step 9): the repeats are investigations the gate does not count.

## 0. Prerequisites, once

- [ ] **[OWNER]** The `runlore` machine user's keys mirrored to OpenBao, before the first session. Run it from
  the cloud-native-ref checkout, with the OpenBao values of `aws-0`:

  ```bash
  IDP_URL=https://auth.<public_domain_name> PRIVATE_DOMAIN=<private_domain_name> \
    scripts/provision/zitadel-oidc-clients.sh sync --cluster aws-0 --cloud aws --region eu-west-3 \
    --openbao-url <openbao_url> --openbao-root-token-secret <root_token_secret_name> \
    --openbao-ca-file <ca.pem> --mirror-openbao --apply
  ```

  Expected: `runlore` converged, with `runlore-factory-principal` and `agents-runlore-principal` among the
  mirrored keys. A failure here is silent: the stack still deploys. Check the factory's sponsored Secret now
  (it reads `runlore-principal` only): `SecretSynced`. Its refresh is 20 m; force it with the annotation.

  ```bash
  kubectl -n agent-system annotate externalsecret agent-factory-sponsored force-sync="$(date +%s)" --overwrite
  kubectl -n agent-system get externalsecret agent-factory-sponsored
  ```

  Unsynced, the factory's principal has no client id.
- [ ] **[OWNER]** The webhook key seeded in both mounts, as
  [runbook 14](14-gcp-0-session.md#5-owner-the-agents-keys-once-per-gcp-lineage) does. The broker's
  ExternalSecret sits in the off state's comment, so nothing syncs until the switch.
- [ ] RunLore's client credentials synced, checked after the key above: `runlore-factory-principal` also reads
  `runlore/factory-webhook`, so it cannot read `SecretSynced` before that key is seeded, and its refresh is
  1 h. Force it:

  ```bash
  kubectl -n runlore annotate externalsecret runlore-factory-principal force-sync="$(date +%s)" --overwrite
  kubectl -n runlore get externalsecret runlore-factory-principal
  ```

  Unsynced, RunLore's client stays off (its env is empty, the Secret being optional) and nothing says so. Once
  RunLore runs (step 1), its log must not contain "the factory client is off":

  ```bash
  kubectl -n runlore logs runlore-0 | grep -c "the factory client is off"
  ```

  Expected `0`.
- [ ] The knowledge repository's `Knowledge queue` issue is absent or closed.
- [ ] The three labels exist on `Smana/runlore-kb`: RunLore adds a label without creating it, and GitHub
  creates none on first use.

  ```bash
  for l in ready-to-merge runlore-queue runlore-resolve; do gh label create "$l" -R Smana/runlore-kb; done
  ```

- [ ] RunLore's values carry `curate.sweeps.mode: apply`. Dry-run gates `Resolve` and the `ready-to-merge`
  label through the guard, though not the curator's own draft, so a session on dry-run drafts entries that
  never get their resolution or label.
- [ ] **[OWNER]** The ai-native-ref release carrying phase 1 is cut and the host pins it.

## 1. Switch on, in this order

The subscriber must not exist while RunLore is off: three failed deliveries disable it for good.

1. A pull request here makes `aws-0`'s four edits (K9): uncomment the `runlore` entry in
   `infrastructure/aws-0/room-broker/config.yaml`; list `externalsecret-webhook-runlore.yaml` under `resources`;
   run `python3 scripts/ci/gen-webhook-egress.py --write`; add a `patches:` block listing
   `- path: network-policy-webhooks-patch.yaml` (the off state has no `patches:` key). Refresh the
   "none declared (D4)" header comment above the `webhooks` list in the same file: with the entry on, a
   webhook is declared. The owner cuts the release.
2. One host pull request carries the three places (the `# - ../base/runlore` line in
   `observability/aws-0/kustomization.yaml`, the Alertmanager route, and the `runlore.yaml` and
   `runlore-spend.yaml` rule files) and the new ai-native-ref tag and digest. No Flux dependency orders the two
   halves. What holds is that nothing delivers until a room event, so run no factory task, and seed nothing,
   until this returns. RunLore's first start is slow, and `wait` fails at once on a pod that does not exist yet,
   so retry on `NotFound`:

   ```bash
   kubectl -n runlore wait --for=condition=Ready pod/runlore-0 --timeout=15m
   ```

3. After the first task of the session, check `RoomWebhookDisabled` is silent (it needs a delivery and
   `for: 1m`, so it is silent trivially before one). If a delivery failed and the subscriber was disabled, bump
   `generation` in `aws-0`'s `runlore` entry and say so in the pull request.

## 1b. The off-state check: the gateway with no RunLore

Run this once, right after the release carrying phase 1 lands and while RunLore is still off. The new
`runlore-kb` target has no Service behind it, and every role's tools must still list (the backend fails open).
From [runbook 06, step 4](06-mcp.md#step-4--internal-adds-real-read-tools-gated-by-role), the internal probe:

```bash
kubectl exec -n agents agent-probe -c probe -- sh /tmp/mcp.sh internal tools/list | grep -o '"name":"[^"]*"'
```

Expected: the same list as before the release, and no `runlore-kb_*` tool (the probe is an implementer, which
the profile does not grant it). An error or an empty list is a failure: the unresolvable target failed the
listing for everyone.

## 2. Live 1: a restart keeps the soak

Live 1 needs a soak, which exists only after a fix has merged: run it inside live 2, between the merge and the
verdict. Restart `runlore-0`. Pass: the Lease `runlore-leader` still exists with one holder (the holder identity
is `<pod>_<podIP>` and changes with the pod's IP: do not compare it), there is one replica, and the soak is
still in the ledger. The ledger is `/var/lib/runlore/catalog/factory.jsonl` on the volume. The image is
distroless, so read it from an ephemeral container:

```bash
kubectl -n runlore debug runlore-0 -it --image=busybox --target=<RunLore's container name> -- \
  cat /proc/1/root/var/lib/runlore/catalog/factory.jsonl
```

After a previous session's switch-off its ledgers are still there.

## 3. Live 2: one incident, to a verified entry

**The seed.** A hand-applied rule would fail this check: its fix lists a path outside `observability/`, so the
class infers `review`, or the fix lands in Git and leaves the hand-applied rule firing, which ends `persisting`
with no `ready-to-merge`. Seed through Git instead, so the fix is a change to a file under `observability/`
and the alert clears when it merges:

1. A cloud-native-ref pull request adds a `VMRule` file under
   `observability/aws-0/` (listed in that directory's `kustomization.yaml`) whose rule is the real failure
   shape: `severity: critical`, `for: 5m`, and an expression that always fires because its selector names a
   Deployment that does not exist, for example
   `absent(kube_deployment_status_replicas_available{namespace="apps",deployment="podnfo"} > 0)` with the
   typo `podnfo`, where `podinfo` (or any Deployment in `apps`) is the real name. Merge it only after
   step 1.2's `wait` returns: seed nothing before RunLore is up. The rule pages every hour from its merge
   until the fix lands, so merge it when the session is ready to run.
2. The published fix must correct the selector in that file. When it merges, Flux applies it, the expression
   matches a series with replicas, and the alert resolves: that is what makes the verdict `resolved` and
   lets the entry get `ready-to-merge`.

Wait for RunLore's finding, publish the stub (`factory/publish`), and merge the fix. Pass, in order:

- `alert-rules` is in the stub task's `status.published.class` (the fix's `## Files` is under `observability/`).
  Once the class is live, a maintainer adds `class:alert-rules` at publish; while it is shadow the factory
  infers it.
- Live 1 passes in the soak after the merge.
- After the soak, `room.monitor_verdict` appears in RunLore's log.
- One pull request on `Smana/runlore-kb` carries `ready-to-merge`, and its `resolution` names the fix. The
  label comes from RunLore's curation pass on the verified generation, not from a sweep.
- Repeats of the alert inside this window file nothing. RunLore still investigates each repeat, which is spend,
  and logs "a generation is undecided; filing nothing for this re-detection". No second task and no second
  stub appear. A second stub during this check is a failure of that rule, not a new generation.
- The internal triager's run names `runlore-kb_kb_search`. Runs live in the `agents` namespace
  (`xplane-run-*`): read the triager's pod log (`kubectl -n agents logs <pod>`) for the `agent-run tools:` line,
  or the run's transcript. This proves the tool was listed to the triager, not that it read an entry.

## 4. Live 3: a second generation

A second seeded rule, of the same shape, whose published fix edits only its `for:`, so it keeps firing. The
class is in shadow, so read the decisions as a shadow class's. Pass, in order:

- The fix merges (a maintainer merges it: `alert-rules` never arms), and after the soak the verdict is
  `persisting`; the pull request is labelled `factory/monitor:regression`.
- A follow-up stub issue labelled `factory/proposed`, titled `RunLore: the fix in #<pr> did not hold (<alert>)`
  and carrying no evidence text. It is not a new incident.
- The class's next decision reads `shadow_would_arm`, not `class_paused`: the shadow branch answers before the
  paused one. A pause shows only as `paused=true` in the `would-arm` marker the factory posts on the task.
- **Keep the second seeded rule until the second generation is filed.** The next generation starts only from a
  repeat that arrives after the first is decided, and a repeat needs the alert still firing. With the route's
  repeat at 1 h, the new stub appears up to 1 h after the verdict; its own verdict waits another soak. Then
  correct the rule through Git and delete both seeded rules.

## 5. Live 4: the replay (RK17)

`lore kb resolve` records an applied fix on the entry a pull request carries. It needs `--pr`, `--fix` and
`--verdict` for each entry, and takes `--merge-sha`. The seven showcase entries, #157 to #163 on
`Smana/runlore-kb`, map to two merged fixes in cloud-native-ref; the other four have no fix pull request
to name:

| KB PR | Entry | Fix | Merge commit | Verdict |
|---|---|---|---|---|
| #159 | `PodinfoNoAvailableReplica` typo `podnfo` | [#2638](https://github.com/Smana/cloud-native-ref/pull/2638) | `eb562c16241a18b0803c6c8eb7fcec4ce0b85f40` | `resolved` |
| #162 | `AppWizardNoAvailableReplica` typo `app-wizzard`: the same rule as #163, under its first name | [#2659](https://github.com/Smana/cloud-native-ref/pull/2659) | `4230652db3b4fba1339b666261d0233d1076817f` | `resolved` |
| #163 | `AppWizardUnavailable` typo `app-wizzard` | [#2659](https://github.com/Smana/cloud-native-ref/pull/2659) | `4230652db3b4fba1339b666261d0233d1076817f` | `resolved` |
| #157, #158, #160, #161 | spend, a stalled HelmRelease, and a typo in a rule a later change removed | none | none | not replayable |

```bash
replay() {  # replay <kb pr> <fix pr> <merge sha>
  kubectl -n runlore exec runlore-0 -- lore kb resolve --config /etc/runlore/runlore.yaml \
    --pr "$1" --fix "https://github.com/Smana/cloud-native-ref/pull/$2" --merge-sha "$3" --verdict resolved
}
replay 159 2638 eb562c16241a18b0803c6c8eb7fcec4ce0b85f40
replay 162 2659 4230652db3b4fba1339b666261d0233d1076817f
replay 163 2659 4230652db3b4fba1339b666261d0233d1076817f
```

#162 and #163 are one rule: cloud-native-ref #2647 added it as `AppWizardNoAvailableReplica` with the
typo, #2654 renamed it `AppWizardUnavailable`, and #2659 fixed the selector.

It exercises the entry path only: it writes no outcome event, so the entries stay `unverified` under Decide
and RK17's test of the outcome join is not exercised (K13). The other four stay in the queue for the stale
sweep. Then write the first queue issue, listing the backlog. `queue-issue` is not read-only: each run
reconciles labels, refreshes entry pull requests and rewrites the issue, force-pushing rebuilt ones (see
`lore curate --help`). The schedule is empty, so nothing else writes it. Record live 4:

```bash
kubectl -n runlore exec runlore-0 -- lore curate queue-issue --config /etc/runlore/runlore.yaml
```

The `stale_after: 720h` change in the host merges after the session's switch-off, not during it: a restart at
`720h` would make the first sweep a full interval later, and the session would not see it.

## 6. Clear the queue while RunLore is on

A human merge conflicts the next entry pull request, and RunLore's refresh of entry pull requests (KP19)
rebuilds it only while it runs. The automatic refresh takes only a pull request labelled `ready-to-merge` or
with held evidence, at most 10 a run, so rebuild by hand the backlog entry the owner is about to review, after
each merge:

```bash
kubectl -n runlore exec runlore-0 -- lore curate refresh-entries --pr <n> --config /etc/runlore/runlore.yaml
```

Any other conflicting pull request waits in Decide as `conflict`. On the first rebuild, record four checks:

1. **Shape and signature after the force-update.** Every commit must read `runlore[bot]`, `web-flow`, `true`,
   and a second conflict then rebuilds again. RunLore refuses any other shape (KP19), so a rebuild that lands
   unsigned would strand the next one in Decide.

   ```bash
   gh api repos/Smana/runlore-kb/pulls/<n>/commits --jq '.[] | [.author.login, .committer.login, .commit.verification.verified]'
   ```

2. **The `force_push` row.** The App-token PATCH is listed as `force_push` by `runlore[bot]`, and Maku's
   `pushedBy` (`merge.go:699-722`) still reads the branch as the adopted author's, not `pushStranger`.

   ```bash
   gh api 'repos/Smana/runlore-kb/activity?ref=refs/heads/<branch>'
   ```

3. **`mergeable` timing.** How long GitHub reports it null after the rebuild and after the base moves, and
   whether a recompute alone bumps the pull request's `updated_at`, which RK17's stale sweep reads.
4. **A `pull_request` run on the rebuilt pull request.** `validate` and `leak-scan` both report on the new
   head, since a push made with an App token must start the workflows the merge checks need.

## 7. Switch off, in this order (the reverse)

1. Rewrite the queue issue to list what is left (this reconciles and may force-push rebuilds, as in live 4):
   `kubectl -n runlore exec runlore-0 -- lore curate queue-issue --config /etc/runlore/runlore.yaml`.
2. The owner clears the queue; run the same `queue-issue` command once more.
3. The subscriber off: a pull request here reverses the four edits (K9: comment the entry, take the
   ExternalSecret out of `resources`, delete `network-policy-webhooks-patch.yaml` and its `patches:` line), a
   release, and the host pin.
4. The host pull request with the three places off.

The volume stays.

## 8. Time

A `healthy` verdict needs the 2 h `followUpWindow` plus about 5 min of search lag, read at most every 10 min:
about 2 h 15 after the merge, before live 2's entry. Live 3 is two such waits in a row and a repeat between
them (up to 1 h, and the repeats inside the first wait file nothing): about 5 h 30 from the first merge before
the second generation's merge is even soaking. Budget about 8 h for a session that proves live 2 and live 3 on
separate alerts started together, not 5 h. Each flip is a pull request here, a release and a host pull request.

## 9. The phase 1 gate

Read after each session:

```bash
python3 scripts/ops/kb-measures.py --since <session start>
```

The gate is three sessions in a row whose queue was cleared before the next one. "KB PRs open at the end" counts
every open `runlore` pull request whenever it was opened, so the backlog shows in it. From the first session,
record RK20's `D`: the highest daily `runlore:investigation_cost_usd:increase1d`. It sets the host's daily
spend alert, and the provider's monthly limit at 1.5 × `D` × the session days expected in a month. Because
every repeat investigates (see the top of this page), `D` includes them. Record the results in the status
record.

## 10. Follow-up: TLS on the broker-to-factory hop

The broker's `factoryURL` is `http://` with `factoryInsecure: true` in each cloud's config, which Maku v0.33.0
requires to be stated because the broker forwards each human's token on that hop. The follow-up is its own pull
request: set the factory chart's `api.tls.secretName` and an issuer, switch `factoryURL` to `https://`, trust
the issuing CA through `factoryCAFile` if it is private, and drop `factoryInsecure`. Prove it in an aws-0
session by creating a room task from the room page (the hand-to-role path) and reading the broker's log for a
successful call to the factory.
