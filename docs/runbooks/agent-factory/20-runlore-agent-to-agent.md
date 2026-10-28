# 20 — RunLore agent to agent: the live proofs

Part 1 proves stage 1 of feature 14 on gcp-0: RunLore is a standard client of the factory. It calls
`POST /v1/tasks` as its internal principal, follows its tasks through the broker's signed webhooks, and
the old `/intake/runlore` path stays silent. Design:
[RunLore agent to agent](../../superpowers/specs/2026-10-27-runlore-agent-to-agent-design.md) (RA1 to
RA14). Part 2 (RunLore's verdict on the fix, stage 2) follows PR 7. See [README.md](README.md) for `CLOUD`.

## 0. Prerequisites

- [ ] **[OWNER]** The host synced: `zitadel-oidc-clients.sh sync --apply` created `runlore-gcp-0`
  (see [runbook 18](18-factory-interfaces.md#1-prerequisites) for the flags), and
  `bao kv get -mount=agents runlore-principal` holds a client id and a project id but no `client-secret`.
- [ ] **[OWNER]** The webhook key seeded in both mounts ([runbook 14](14-gcp-0-session.md#5-owner-the-agents-keys-once-per-gcp-lineage)).
- [ ] The label exists on the repository:

  ```bash
  gh label create factory/publish -R Smana/cloud-native-ref --color 0E8A16 \
    --description "Publish the factory's proposal as a new issue"
  ```

## 1. Live 1: the paths are open

```bash
kubectl -n runlore exec runlore-0 -- wget -qO- -T5 --post-data '{}' \
  http://agent-factory.agent-system.svc.cluster.local:8082/v1/tasks
kubectl -n runlore exec runlore-0 -- wget -qO- -T5 \
  http://vmalertmanager-victoria-metrics-k8s-stack.observability.svc:9093/api/v2/status
hubble observe --from-pod runlore/runlore-0 --verdict DROPPED
```

Pass: both answer (a `401` from the factory is a pass: the path is open); RunLore's log shows a token
obtained at its first finding (a drop on ZITADEL is the cloud-native-ref plan's R4 follow-up); Hubble
names no policy on these.

## 2. Live 2: one incident, end to end

Seed a broken alerting rule: a `VMRule` in `apps` whose expression is `vector(1)` with
`severity: critical`, applied by hand, never through Git. Wait for RunLore's finding. Pass:

- the factory answers `201` (RunLore's log); the task is `api` / `system:runlore` / `internal` /
  `investigate`, and the stub issue is labelled `factory/proposed`;
- `kubectl -n runlore delete pod runlore-0` mid-way changes nothing;
- a replay (`curl` the same body with the same `Idempotency-Key`, with a token from the same client)
  answers `200 duplicate`;
- the Slack thread shows `task_received` and `ended` lines.

## 3. Live 3: the old intake is silent

Pass: `agent_factory_intake_errors_total` and the intake's request counter for `runlore` are flat for
the whole session (query both in VictoriaMetrics), and RunLore's rendered config holds no `templated`:

```bash
kubectl -n runlore get cm runlore-factory-values -o jsonpath='{.data.values\.yaml}' | grep -c templated
```

Expected `0`.

## End of part 1

The seeded rule stays for stage 2, or is deleted and the deletion recorded.

# Part 2: RunLore verifies the fix (stage 2)

PR 7 sets `verification: true` on gcp-0's `runlore` principal, adds the `alert-rules` class
(`monitor.verification: {within: 2h}`), gives RunLore a 30m soak and the Alertmanager to read, and
retires `/intake/runlore` (the factory's `runlore:` block and both intake ExternalSecrets).

## 4. Live 4: the stage 1 incident, end to end

- [ ] The proposal comment names `factory/publish`; the owner labels the stub.
- [ ] The fix issue appears unlabelled with the footer; the owner labels it `class:alert-rules` and
  `factory/ready`. The fix's Task has `spec.origin`.
- [ ] The broker's deliveries to RunLore carry `origin`:

  ```bash
  kubectl -n agent-system logs deploy/room-broker | grep runlore
  ```

- [ ] The fix merges (by the owner). RunLore posts "Soaking for 30m"; after it, `resolved`.
- [ ] The Task's monitor shows `verified: healthy` and, after `followUpWindow`, `verdict: healthy`:

  ```bash
  kubectl get task <fix> -o jsonpath='{.status.monitor}'
  ```

  `agent_factory_monitor_verifications_total{class="alert-rules",verdict="resolved"}` is 1.
- [ ] Before reading the verdict, one holder for the soak's span (G8: each RunLore replica has its own
  volume, so a failover loses the soak). A change of holder reruns the case.

  ```bash
  kubectl -n runlore get lease runlore-leader -o yaml
  ```

## 5. Live 5: a fix that does not hold

A second seeded case whose published fix edits the rule's `for:` only, so it keeps firing. Pass:

- [ ] `persisting`; the PR is labelled `factory/monitor:regression`;
- [ ] a follow-up stub issue labelled `factory/proposed`, with no evidence text;
- [ ] the next arm of the class reads `class_paused` (`maxFollowUps: 1` is the repository's breaker, G9);
- [ ] the owner clears the pause as [runbook 15](15-dead-links.md) does, and deletes both seeded rules.
