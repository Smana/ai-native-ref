# RunLore agent-to-agent, cloud-native-ref PRs 3 and 6b — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Target repository:** `Smana/cloud-native-ref` (`/home/smana/Sources/cloud-native-ref`), the host.
Every path below is in that repository unless it says otherwise. This file lives in ai-native-ref so
that one pull request carries the four feature-14 plans.

**Goal:** The host gives RunLore what feature 14 needs from it: a ZITADEL machine user for its
client credentials, a network path to the factory and to Alertmanager, an ingress from the room
broker, and a RunLore release that carries the client (PR 3); then the release that carries the
verifier (PR 6b).

**Architecture:** Every piece follows a host precedent. The machine user is a `MACHINE_USERS` entry,
as the Slack App's is (`scripts/provision/zitadel-oidc-clients.sh:458`). RunLore's network lives in
its HelmRelease's `networkPolicy` values (`observability/base/runlore/helmrelease.yaml:317-371`).
The pin moves the GitRepository tag and the image tag in lockstep (`flux/sources/gitrepo-runlore.yaml`,
`helmrelease.yaml:89-106`). The contract rows change in the host design's §2 and in ai-native-ref's
`HOST-CONTRACT.md` together.

**Tech Stack:** Bash suites (`# requires:` line 2), Python flux-schema gates, `task check` on the host.

**Spec:** [the RunLore agent-to-agent design](../specs/2026-10-27-runlore-agent-to-agent-design.md)
(ai-native-ref): "What exists", the Network row; row 3 of "Pull requests, in order"; live proof 1.
The order across repositories is in the [ai-native-ref plan](2026-10-27-runlore-a2a-ai-native-ref-plan.md).

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| R1 | **This PR also carries the machine user and the RunLore pin**, not only the network | Design gap: the design's row 3 names the network only, and row 4 puts "its ZITADEL client" and "pin both releases" in ai-native-ref. The ZITADEL machine users are the host's (H5: "provisioned by the host's scripts"), and RunLore is pinned by the host (`flux/sources/gitrepo-runlore.yaml`), not by ai-native-ref |
| R2 | **One machine user, two store keys.** `MACHINE_USERS` takes an optional third field; for `runlore` the full `{client-id, client-secret, project-id}` goes to `runlore-factory-principal` (OpenBao `platform/runlore/factory-principal`, which RunLore's `openbao-platform` store reads), and `{client-id, project-id}` only to `agents-runlore-principal` (`agents/runlore-principal`, which the factory's `agents-secrets` store reads) | RunLore and the factory read two different mounts (`platform` through `openbao-platform`, `agents` through `agents-secrets`; HOST-CONTRACT H5 "Stores"). The factory needs the client id, never the secret |
| R3 | **Network, in the HelmRelease's values:** `extraEgress` gains `agent-system`/`agent-factory` on 8082 and `observability`/`vmalertmanager` on 9093; `ingressFrom` gains `agent-system`/`room-broker` | The chart renders a NetworkPolicy from these (`deploy/helm/runlore/templates/networkpolicy.yaml` in RunLore). Port 8082 is the factory's API Service port; 9093 is `vmalertmanager-victoria-metrics-k8s-stack` (`observability/base/victoria-metrics-k8s-stack/httproute-vmalertmanager.yaml:14-15`). The broker posts to RunLore's Service port 8080 |
| R4 | **ZITADEL from RunLore on gcp-0 is a live question, answered in live 1.** If RunLore's token request is dropped there, a gcp-0 CiliumNetworkPolicy `runlore-zitadel` with `toEntities: [all]` and no ports follows, as every other gcp-0 ZITADEL client has (ruling AU) | The chart's permissive egress opens 443 to anywhere (`networkpolicy.yaml`), which ruling AU says a `toPorts` rule cannot carry to this cluster's own Gateway VIP (ai-native-ref `infrastructure/gcp-0/room-broker/kustomization.yaml`, the `room-broker` patch). Untested for RunLore |
| R5 | **The PR merges on its static evidence and the host's CI**, not after a live drop | Design gap: row 3 says "after live 1 shows the drop", but row 4 depends on row 3 and the live session depends on row 4, so live 1's "before" half cannot precede it. The static evidence is the extraEgress list itself (two rules, neither to `agent-system`); live 1 then proves "answered", and its "before" half is read from the current notifier's Hubble drops on `:8080` in any gcp-0 session that precedes this PR, or recorded as not taken |

## Global Constraints

- **Worktree:** `/home/smana/Sources/cloud-native-ref-f14`, branch `feat/runlore-factory-host`, from a
  freshly fetched `origin/main` (`b85b28eb` when written), rebased before every push. `mise trust mise.toml` once.
- **`task check` is the evidence**, exit 0, with `check-ai-boundary.py` and the ZITADEL suites.
- **Nothing touches a live cluster**: the machine user is created by `zitadel-oidc-clients.sh sync --apply`
  in a session, never by a merge; every `kubectl`, store and ZITADEL call is stubbed in tests.
- **Lockstep:** the GitRepository `tag` and the image `tag` move together (`helmrelease.yaml:89-106`).
- **Commits:** conventional, in English, no trailers.

## File structure

| File | Change | Task |
|---|---|---|
| `scripts/provision/zitadel-oidc-clients.sh:445-458,1610-1704,2071` | the entry, the third field | 1 |
| `scripts/lib/bao-map.sh:38-51` | two keys | 1 |
| `scripts/ci/tests/test-zitadel-machine-users.sh`, `scripts/ci/tests/test-bao-map.sh` | the cases | 1 |
| `observability/base/runlore/helmrelease.yaml:336-371` | egress, ingress | 2 |
| `flux/sources/gitrepo-runlore.yaml`, `observability/base/runlore/helmrelease.yaml:96-105` | the pin | 3, 5 |
| `docs/superpowers/specs/2026-10-12-ai-platform-split-design.md` §2 (H5, H8) | the contract | 4 |

---

## PR 3: the machine user, the network, RunLore `vR1`

### Task 1: The machine user `runlore`

**Files:**
- Modify: `scripts/provision/zitadel-oidc-clients.sh:445-458` (the entry and its comment), `:1610-1704`
  (`ensure_machine_user`'s third argument), `:2071` (the loop)
- Modify: `scripts/lib/bao-map.sh:51`
- Test: `scripts/ci/tests/test-zitadel-machine-users.sh`, `scripts/ci/tests/test-bao-map.sh`

**Interfaces:**
- Produces: `MACHINE_USERS=("factory-slack-app|agents-factory-slack-principal" "runlore|runlore-factory-principal|agents-runlore-principal")`;
  `ensure_machine_user name key [public_key]`.

- [ ] **Step 1: Write the failing cases**

In `test-zitadel-machine-users.sh`: make the store stub record each key's write,
`store_write_and_mirror() { printf '%s' "$1" >"$T/key"; tee "$T/written-$1" >"$T/written"; return "$WRITE_RC"; }`,
and after the existing cases add a block on the suite's own harness (`run`, `calls`, `written`, the
`STORED`/`USERS`/`ACCEPT`/`VALID_ID` fixtures; `store_read` answers `STORED` for every key):

```bash
echo "== runlore: one user, the full key for RunLore, the public half for the factory (R2) =="
KEY=runlore-factory-principal; PUBLIC=agents-runlore-principal; PUT_CLIENT_ID=runlore; VALID_ID=runlore
run_runlore() { rm -f "$T"/written* "$T/api" "$T/key" "$T/probed-as"; : >"$T/api"; mirrored_keys=(); failed_mirrors=""
                out="$(ensure_machine_user runlore "$KEY" "$PUBLIC" 2>&1)"; rc=$?
                mirrored_keys=(); failed_mirrors=""; ensure_machine_user runlore "$KEY" "$PUBLIC" >/dev/null 2>&1; }
STORED='{}'; USERS='{"result":[]}'; ACCEPT=0
run_runlore
check "runlore: exit 0" 0 "$rc"
check "runlore: the full key" '{"client-id":"runlore","client-secret":"NEWSECRET","project-id":"proj-1"}' "$(jq -c . "$T/written-$KEY")"  # pragma: allowlist secret
check "runlore: the public key holds no secret" '{"client-id":"runlore","project-id":"proj-1"}' "$(jq -c . "$T/written-$PUBLIC")"
check "runlore: prints no secret" 0 "$(grep -c NEWSECRET <<<"$out")"
STORED='{"client-id":"runlore","client-secret":"STOREDSECRET","project-id":"proj-1"}'  # pragma: allowlist secret
USERS='{"result":[{"id":"ID","userName":"runlore"}]}'
run_runlore
check "runlore converged: the public half equal, not written" absent "$([ -e "$T/written-$PUBLIC" ] && echo written || echo absent)"
STORED='{"client-id":"runlore","client-secret":"STOREDSECRET","project-id":"old"}'  # pragma: allowlist secret
run_runlore
check "runlore: a new project id rewrites the public half" '{"client-id":"runlore","project-id":"proj-1"}' "$(jq -c . "$T/written-$PUBLIC")"
VALID_ID=factory-slack-app; PUT_CLIENT_ID=factory-slack-app; KEY=agents-factory-slack-principal
check "the loop reads three fields" "runlore runlore-factory-principal agents-runlore-principal" \
  "$(IFS='|' read -r a b c <<<'runlore|runlore-factory-principal|agents-runlore-principal'; echo "$a $b $c")"
```

Add `write_public` to the suite's `load_function` list. In `test-bao-map.sh`:

```bash
check "runlore-factory-principal" "platform/runlore/factory-principal" "$(bao_target_for runlore-factory-principal)"
check "agents-runlore-principal" "agents/runlore-principal" "$(bao_target_for agents-runlore-principal)"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `ulimit -v 4000000; timeout 120 bash scripts/ci/tests/test-zitadel-machine-users.sh; timeout 60 bash scripts/ci/tests/test-bao-map.sh`
Expected: `could not extract write_public()`, exit 1; and two `FAIL` lines from the map.

- [ ] **Step 3: Implement**

`ensure_machine_user`: a third local `public="${3:-}"`. A helper:

```bash
# write_public key client_id: the factory's half of an internal principal (R2): its client id and the
# project id, never the secret, written only when it differs from what the store holds.
write_public() {
    local key="$1" cid="$2" want stored='{}' probe=0
    [ -n "$key" ] || return 0
    want="$(jq -cn --arg id "$cid" --arg proj "$project_id" '{"client-id": $id, "project-id": $proj}')"
    store_probe "$key" || probe=$?
    [ "$probe" -ge 2 ] && return 1
    [ "$probe" -eq 1 ] || stored="$(store_read "$key" | jq -c '{"client-id": ."client-id", "project-id": ."project-id"}')" || return 1
    [ "$stored" = "$want" ] && return 0
    printf '%s' "$want" | store_write_and_mirror "$key" && mirrored_keys+=("$key")
}
```

Call `write_public "$public" "$cid" || return 1` on the converged path before its `return 0`, and
after the full key's write on the stored path. Load it in the suite's `load_function` list. The loop
at `:2071`:

```bash
    for u in ${MACHINE_USERS[@]+"${MACHINE_USERS[@]}"}; do
        IFS='|' read -r mu_name mu_key mu_public <<<"$u"
        ensure_machine_user "$mu_name" "$mu_key" "$mu_public" || machine_failed=1
    done
```

The entry, with a comment: "RunLore, the agent factory's internal principal (ai-native-ref feature 14,
RA2). Its full key is RunLore's (`platform/runlore/factory-principal`, read through `openbao-platform`);
the factory reads only the client id and the project id (`agents/runlore-principal`)."
`bao-map.sh`, beside `agents-factory-slack-principal`:

```bash
        runlore-factory-principal) printf 'platform/runlore/factory-principal' ;;
        agents-runlore-principal) printf 'agents/runlore-principal' ;;
```

- [ ] **Step 4: Run every ZITADEL suite, commit**

```bash
ulimit -v 4000000
for t in scripts/ci/tests/test-zitadel-*.sh scripts/ci/tests/test-gcp-zitadel-project-id.sh scripts/ci/tests/test-bao-map.sh; do
  timeout 120 bash "$t" >/dev/null 2>&1 || echo "FAIL $t"
done
```

Expected: no `FAIL` line.

```bash
git add scripts/
git commit -m "feat(zitadel): RunLore as a machine user, its full key for RunLore and its client id for the factory"
```

### Task 2: RunLore reaches the factory and Alertmanager; the broker reaches RunLore

**Files:**
- Modify: `observability/base/runlore/helmrelease.yaml:336-371`

- [ ] **Step 1: The values**

`ingressFrom`, after the `observability` entry:

```yaml
        # The room broker's signed webhooks (ai-native-ref feature 14, RA7): POST /factory/webhook
        # on this port, forwarded to the leader by RunLore itself.
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: agent-system
          podSelector:
            matchLabels:
              app.kubernetes.io/name: room-broker
```

`extraEgress`, after the Hubble Relay rule:

```yaml
        # The agent factory's API (feature 14): POST /v1/tasks and the verdict, 8082 on its Service.
        - to:
            - namespaceSelector:
                matchLabels:
                  kubernetes.io/metadata.name: agent-system
              podSelector:
                matchLabels:
                  app.kubernetes.io/name: agent-factory
          ports:
            - port: 8082
              protocol: TCP
        # Alertmanager, read once a fix is merged and once its soak ends (feature 14, RA14).
        - to:
            - namespaceSelector:
                matchLabels:
                  kubernetes.io/metadata.name: observability
              podSelector:
                matchLabels:
                  app.kubernetes.io/name: vmalertmanager
          ports:
            - port: 9093
              protocol: TCP
```

Check the Alertmanager pod's label before committing:
`git grep -n 'app.kubernetes.io/name: vmalertmanager' -- observability` or, failing that, the
victoria-metrics operator's default labels for a `VMAlertmanager` (`app.kubernetes.io/name: vmalertmanager`);
if neither confirms it, use the namespace selector alone and say so in the PR.

- [ ] **Step 2: Render**

Run: `task check` (or the host's `validate-manifests.sh` alone while iterating).
Expected: the HelmRelease validates; `check-ai-boundary.py` passes (no AI path is named here).

- [ ] **Step 3: Commit**

```bash
git add observability/base/runlore/helmrelease.yaml
git commit -m "feat(runlore): reach the agent factory and Alertmanager; admit the room broker's webhooks"
```

### Task 3: Pin RunLore `vR1`

**Files:** `flux/sources/gitrepo-runlore.yaml` (`ref.tag`), `observability/base/runlore/helmrelease.yaml:96-105` (`image.tag` and its comment).

- [ ] **Step 1:** Read the release: `gh release view -R Smana/runlore --json tagName,publishedAt` and
  `git -C /home/smana/Sources/runlore grep -n 'factory/webhook' <vR1> -- internal/server`. Expected:
  the tag of RunLore PR 2's release (`vR1`), and one hit. Otherwise stop.
- [ ] **Step 2:** Move `tag: v0.16.2` to `tag: <vR1>` and `tag: "0.16.2"` to `tag: "<vR1 without v>"`,
  and the comment's version. Render the chart at `vR1` with these values and replay its config
  through `vR1`'s `config.Load` (the comment's own procedure, `helmrelease.yaml:93-95`): `factory`
  is absent here, so the config parses unchanged.
- [ ] **Step 3: Commit**

```bash
git add flux/sources/gitrepo-runlore.yaml observability/base/runlore/helmrelease.yaml
git commit -m "feat(runlore): pin <vR1>, the agent factory's client"
```

### Task 4: The contract; the PR

**Files:** `docs/superpowers/specs/2026-10-12-ai-platform-split-design.md` §2: the H5 ZITADEL row and
the H8 paragraph.

- [ ] **Step 1: The rows**, the same words as ai-native-ref's `HOST-CONTRACT.md` version 5 (its plan,
  Task 1):

H5 ZITADEL: `…, the factory-slack-app machine user (…at agents/factory-slack-principal), the runlore
machine user (client credentials, no project role; its full key at platform/runlore/factory-principal,
its client id and project id at agents/runlore-principal), and the link-only GitHub IdP, …`

H8, after the `runlore-factory-values` sentence: "RunLore's Service `runlore` in `runlore` serves the
room broker's webhooks on 8080 at `/factory/webhook`; RunLore's egress reaches the factory
(`agent-system`, `agent-factory`, 8082) and Alertmanager (`observability`, 9093), and its ingress
admits `agent-system`'s `room-broker`."

- [ ] **Step 2: Check, push, PR**

```bash
task check
git add docs/superpowers/specs/2026-10-12-ai-platform-split-design.md
git commit -m "docs(contract): H5 names RunLore's machine user, H8 its factory paths"
git fetch origin && git rebase origin/main && git push -u origin feat/runlore-factory-host
```

Title: `feat(runlore): the agent factory's client: a machine user, its network, RunLore <vR1>`.
Body: R1–R5; the owner's session step (`zitadel-oidc-clients.sh sync --apply` on gcp-0 creates
`runlore-gcp-0`); that live 1 is the network's proof (ai-native-ref runbook 20). No attribution line.

---

## PR 6b: pin RunLore `vR2`

### Task 5: Pin the verifier's release

- [ ] **Step 1:** Read the release as Task 3 Step 1, with `vR2` and `git grep -n 'alertmanager_url' <vR2> -- internal/config`.
- [ ] **Step 2:** Move both tags to `vR2` in lockstep; replay the config through `vR2`'s `config.Load`.
- [ ] **Step 3: Check, commit, PR**

```bash
task check
git add flux/sources/gitrepo-runlore.yaml observability/base/runlore/helmrelease.yaml
git commit -m "feat(runlore): pin <vR2>, which verifies the factory's fixes"
git fetch origin && git rebase origin/main && git push -u origin feat/runlore-verify-pin
```

## Gate

- [ ] `task check` exit 0 on each PR's head, the ZITADEL suites and `test-bao-map.sh` included.
- [ ] Live 1 (ai-native-ref runbook 20): from a RunLore pod, the factory on 8082 answers (any HTTP
  status), Alertmanager on 9093 answers, the token request to ZITADEL answers; the broker's delivery to
  RunLore is `2xx`. A drop names R4's follow-up.
