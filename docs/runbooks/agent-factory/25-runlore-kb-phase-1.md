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
- A merged entry files again: the next generation starts.
- A generation is decided when its verdict is `persisting` or a regression, its fix room ended without a
  merge, or the alert is reverted. Only a repeat that arrives after that starts the next generation.

Read the spend after the first session (step 9): the repeats are investigations the gate does not count.

## 0. Prerequisites, once

- [ ] **[OWNER]** The `runlore` machine user's keys mirrored to OpenBao (the host plan's Task 6 command),
  before the first session.
- [ ] **[OWNER]** The webhook key seeded in both mounts, as
  [runbook 14](14-gcp-0-session.md#5-owner-the-agents-keys-once-per-gcp-lineage) does. The ExternalSecret sits
  in the off state's comment, so nothing syncs until the switch.
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
   run `python3 scripts/ci/gen-webhook-egress.py --write`; list `- path: network-policy-webhooks-patch.yaml`
   under `patches:`. The owner cuts the release.
2. One host pull request carries the three places (the `# - ../base/runlore` line in
   `observability/aws-0/kustomization.yaml`, the Alertmanager route, and the `runlore.yaml` and
   `runlore-spend.yaml` rule files) and the new ai-native-ref tag and digest. No Flux dependency orders the two
   halves. What holds is that nothing delivers until a room event, so run no factory task, and seed nothing,
   until this returns:

   ```bash
   kubectl -n runlore wait --for=condition=Ready pod/runlore-0
   ```

3. Check `RoomWebhookDisabled` is silent. If a delivery failed and the subscriber was disabled, bump
   `generation` in `aws-0`'s `runlore` entry and say so in the pull request.

## 2. Live 1: a restart keeps the soak

Restart `runlore-0` in the middle of a soak. Pass: the Lease `runlore-leader` still exists with one holder
(the holder identity is `<pod>_<podIP>` and changes with the pod's IP: do not compare it), there is one
replica, and `factory.jsonl` on the volume still lists the soak. After a previous session's switch-off the
ledgers are still there.

## 3. Live 2: one incident, to a verified entry

Seed a `vector(1)` rule, publish the stub (`factory/publish`), and merge the fix. Pass, in order:

- `alert-rules` is in the stub task's `status.published.class`.
- After the owner's merge, `room.monitor_verdict` appears in RunLore's log.
- One pull request on `Smana/runlore-kb` carries `ready-to-merge`, and its `resolution` names the fix. The
  label comes from RunLore's curation pass on the verified generation, not from a sweep.
- Repeats of the alert inside this window file nothing. RunLore logs "a generation is undecided; filing
  nothing for this re-detection", and no second task and no second stub appear. A second stub during this
  check is a failure of that rule, not a new generation.
- The internal triager's run (`kubectl -n agent-system logs` of its pod, or the run's transcript) names
  `runlore-kb_kb_search`: the triager reached the knowledge base.

## 4. Live 3: a second generation

Run [runbook 20's live 5](20-runlore-agent-to-agent.md#5-live-5-a-fix-that-does-not-hold), then let the verified
generation complete the entry. The next generation starts only when a repeat arrives after the first is
decided. The repeat before that files nothing (live 2). With the route's repeat at 1 h, the second generation
starts up to 1 h after the first one's verdict, and its own verdict waits another soak.

## 5. Live 4: the replay (RK17)

```bash
kubectl -n runlore exec runlore-0 -- lore kb resolve --config /etc/runlore/runlore.yaml …
```

Run it on #157 to #163 with cloud-native-ref #2638 and #2659. It exercises the entry path only: it writes no
outcome event, so #157 to #163 stay `unverified` under Decide, and RK17's test of the outcome join is not
exercised (K13). Then write the first queue issue, listing the backlog (the schedule is empty, so nothing else
does), and record live 4:

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

1. `lore curate queue-issue --config /etc/runlore/runlore.yaml` again, to list what is left.
2. The owner clears the queue; run `queue-issue` once more.
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

The gate is three sessions in a row whose queue was cleared before the next one. From the first session,
record RK20's `D`: the highest daily `runlore:investigation_cost_usd:increase1d`. It sets the host's daily
spend alert, and the provider's monthly limit at 1.5 × `D` × the session days expected in a month. Because
every repeat investigates (see the top of this page), `D` includes them. Record the results in the status
record.
