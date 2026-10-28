# 20 — RunLore agent to agent: the live proofs

Part 1 proves stage 1 of feature 14 on gcp-0: RunLore is a standard client of the factory. It calls
`POST /v1/tasks` as its internal principal, follows its tasks through the broker's signed webhooks, and
the old `/intake/runlore` path stays silent. Design:
[RunLore agent to agent](../../superpowers/specs/2026-10-27-runlore-agent-to-agent-design.md) (RA1 to
RA14). Part 2 (the verdict, stage 2) is added with PR 7. See [README.md](README.md) for `CLOUD`.

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

## End

The seeded rule stays for stage 2, or is deleted and the deletion recorded.
