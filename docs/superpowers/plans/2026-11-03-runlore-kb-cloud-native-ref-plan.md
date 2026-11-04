# RunLore's knowledge base from the factory, cloud-native-ref PRs 3, 3b and 3c — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Target repository:** `Smana/cloud-native-ref`, the host (the working tree is the worktree you create in the
Global Constraints). Every path below is in that repository unless it says otherwise: `RL/` is RunLore, `AIR/`
is ai-native-ref. This file lives in ai-native-ref beside its design (RK21).

**Goal:** RunLore's session switch on aws-0, prepared and off (RK15). Turned on for a demo, RunLore
runs as one replica on its volume: it receives every alert, serves its knowledge base to the agent
router, rewrites the knowledge queue at the session's end and records its model spend (PR 3). Once
the first queue has listed the backlog, its stale sweep closes what nobody kept (PR 3b); after the
first session, the daily spend alert (PR 3c). Between ai-native-ref's PR 4 and the session, and again
after its PR 7, the host pins the ai-native-ref release that carries them (PR 4b, PR 7b).

**Architecture:** Every piece follows a host precedent. The pin moves both tags in lockstep
(`helmrelease.yaml:89-106`). RunLore's config and network live in its HelmRelease values
(`observability/base/runlore/helmrelease.yaml`). Switching it on stays the owner's documented
three-place switch, off on `main` (`observability/aws-0/kustomization.yaml:15-20`); uninstalling
keeps its PVCs, so its ledgers carry over between sessions. The contract row changes in the
host design's §2 here and in ai-native-ref's `HOST-CONTRACT.md` there.

**Tech Stack:** Flux HelmRelease values, kustomize, VMRule (promtool via `validate-vmrules.sh`),
`task check` on the host.

**Spec:** [RunLore's knowledge base, filled by the agent factory](../specs/2026-11-03-runlore-kb-from-the-factory-design.md):
RK13, RK15, RK17, RK20; Interfaces; row 3 of "Pull requests, in order"; live proof 1.

**Out of this plan:** ai-native-ref PR 4 carries `factory.curation: {defer: true, window: 7d}` under
`config.factory` in `AIR/observability/base/runlore-factory/helm-values-configmap.yaml`, because that
ConfigMap owns RunLore's factory client (H8). It also carries the `runlore-kb` target (`static` host
`runlore.runlore.svc.cluster.local`, port 8080, path `/mcp`) in
`AIR/infrastructure/base/agent-gateway/mcp.yaml` with its egress rule in `network-policy.yaml`, the
triager's profile, the `runlore` principal on aws-0, `HOST-CONTRACT.md` version 6 (H8) and
runbook 25. Runbook 25 holds the session: R2's mirror, the webhook key and RK20's two reads. RunLore
PR 2 carries `curate.queue_issue`, `/mcp` and the release. The ai-native-ref release that carries
its PR 4 (and, later, its PR 7) is cut by the owner, as every release is, and reaches the cluster
only through this repository's pin: Task 9. Phase 2 changes nothing in the host: its
PRs land in Maku, runlore-kb and ai-native-ref, and the merge gate's config is an AI path
(`scripts/ci/flux-schema/ai-boundary.yaml:9`).

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| R1 | **This PR pins RunLore `vL1`** (RunLore PR 2's release) | The host pins RunLore (`flux/sources/gitrepo-runlore.yaml:49`, `helmrelease.yaml:106`). `curate.queue_issue` is a key only `vL1` parses, and the config is parsed with KnownFields(true) (`helmrelease.yaml:89-95`). Row 4 keeps the Maku pin. This repeats the a2a plan's R1 |
| R2 | **No ZITADEL code. The client is `runlore`, not `runlore-aws-0`** | aws-0 hosts the directory, so `APP_SUFFIX` is empty (`scripts/provision/zitadel-oidc-clients.sh:262-266`). `runlore` is already in `MACHINE_USERS` (`:463-466`), and aws-0's deploy-time sync creates it (`opentofu/aws/eks/init/workflows.tm.hcl:181-186`). That sync passes no `--mirror-openbao`, so both keys stay in AWS Secrets Manager, while RunLore reads `platform/runlore/factory-principal` and the factory reads `agents/runlore-principal`, both in OpenBao (H5). The session re-runs the sync with the OpenBao flags (Task 6) |
| R3 | **One replica, still a StatefulSet** | G8: each replica owns an RWO volume (`helmrelease.yaml:59-66`), and the factory ledger sits beside the outcome ledger on it (`RL/internal/app/factory.go:36-37`), so a failover lost the soak. With one replica a restart keeps it, because the verifier reschedules from the ledger (`RL/internal/factory/verifier.go:116-134`). The StatefulSet keeps the claim it already made; a Deployment would template another. No PDB renders at one replica (`RL/deploy/helm/runlore/templates/pdb.yaml:1`) |
| R4 | **`sweeps.mode: apply` with `stale_after: 0s` and the chart's `interval: 6h`; `720h` returns in PR 3b, after live 4** | With `apply` from RunLore's start and the chart's `stale_after: 720h` (`RL/deploy/helm/runlore/values.yaml:221`), the first sweep, 6h after start (`RL/internal/curate/sweeper.go:14-18`), closes every unprotected PR idle 30 days (`RL/internal/curate/lifecycle.go:139`). That closes most of the 47 before the first queue lists them, against RK17's order. Dry-run is no fix: one guarded sweep runs Suppress, Dedup, Lifecycle and Queue (`RL/internal/app/curate.go:118-130`, `sweep.go:36`), so it blocks every write through the guard, `ready-to-merge` and the entry's `Resolve` included, though not the curator's own draft (RunLore plan, Task 11), so a session on dry-run would draft entries that never earn their resolution or label. **No shorter `interval`** (decided on the 2026-11-04 review): a 10m sweep would make Suppress and Dedup act in `apply` on the 54 open PRs before the first queue lists them, which RK17 does not intend. The label live 2 needs does not wait for a sweep: RunLore's `Curation.Once` promotes the PR itself once a verified generation is recorded (RunLore plan, Task 11) |
| R5 | **The router's ingress names `agent-gateway`, L4 on 8080** | The router's pods run in `agent-gateway` with `gateway.networking.k8s.io/gateway-name: agent-router` (`AIR/infrastructure/base/agent-gateway/network-policy.yaml:22-27`); only its routes live in `agent-system`. No host policy has an L7 `http` rule. RunLore's rules are L4, as the broker's is (`helmrelease.yaml:341-348`). So the rule cannot narrow by path: any caller the port admits (the whole `observability` namespace, the room broker, the router, and the Gateway data plane through the CNP's `ingress` entity) reaches `/mcp`. The owner's decision stands: `/mcp` sits behind network policy only, no token, because it is read-only and serves public text (RK13). The public route is `POST` Exact `/slack/interactions` (`httproute.yaml`), so the internet cannot reach it. Targets are `static` hosts (`AIR/.../mcp.yaml:35-58`), so `runlore` needs no ReferenceGrant |
| R6 | **The route and the health rules stay in the shared base, flipped with the switch** | This is the owner's own switch (`observability/aws-0/kustomization.yaml:17-19`, #2604). Alertmanager's `routes` list sits in one values string, and a per-cluster copy would restate the whole list. Cost: a gcp-0 up during an aws-0 session, without RunLore, fails the route and fires `RunloreAgentDown`. The comments say so |
| R7 | **No aws-0 identity-provider policy** | gcp-0's `observability/gcp-0/runlore/cnp-identity-provider.yaml` exists because ZITADEL is that cluster's own Gateway VIP (ruling AU). On aws-0, ZITADEL sits behind an internet-facing NLB (`security/aws-0/zitadel/gateway-patch.yaml`), which other workloads reach on 443 (`AIR/infrastructure/base/room-broker`, `toFQDNs: auth.${public_domain_name}`), and the chart opens 443. The base already holds the factory, Alertmanager and broker paths (`helmrelease.yaml:341-348,381-401`). Live 1 proves the token request; a reset there calls for an aws-0 policy |
| R8 | **RK20 in dollars: `config.model.pricing` set, one recording rule in its own file, no panel; the daily alert is PR 3c, once the first session is measured** | With `model.pricing` RunLore reports `runlore_investigation_cost_usd`, a histogram (`RL/deploy/observability/grafana/runlore.json:1451`); without it nothing is priced (`RL/internal/config/config.go:531`). The dashboard's "Cost & efficiency" row already shows it. a session fits in vmsingle's 14 days (`helmrelease-vmsingle.yaml`, `retentionPeriod: "14d"`) |

## Global Constraints

- **Worktree:** `EnterWorktree` from a freshly fetched `origin/main` (`3f5a133c` when written), branch
  `feat/runlore-aws-0`, rebased before every push. Run `mise trust mise.toml` once.
- **`task check` is the evidence**, exit 0. While iterating, run `./scripts/ci/validate-manifests.sh`.
  It runs the boundary check, `validate-vmrules.sh`, the render into `.bundle/`, both schema gates,
  the cloud shape and the Alertmanager templates.
- **Lockstep:** the GitRepository `tag` and the image `tag` move together.
- **Edit by hand:** these files carry load-bearing comments that a `yq -i` round-trip can move. Use
  `yq` to read the render.
- **The merge changes nothing running:** the switch stays off (RK15); ai-native-ref's runbook 25
  flips it for a session, here and in aws-0's factory copies together. Each flip is a host PR that
  carries the three places and, when ai-native-ref changed since, its pin (Task 9). No step here runs `kubectl` or
  calls ZITADEL.
- **Commits:** conventional, in English, no trailers. PR bodies carry no attribution line.
- **Paths:** repo-relative, never a machine's absolute path.

## Review Focus

| # | Failure mode | Check |
|---|---|---|
| F1 | The stale sweep closes the backlog before the first queue lists it (R4) | Task 3 Step 2 |
| F2 | A key the binary does not know crashloops RunLore (KnownFields) | Task 1 Step 1, Task 3 Step 2 |
| F3 | G8 comes back: two replicas, or a second volume | Task 2 Step 2 |
| F4 | The router's rule names `agent-system` and matches nothing, or `/mcp` reaches the public route | Task 4 Step 3 |
| F6 | `/mcp` is off in RunLore by default and the backend is `FailOpen`: the router's `kb_search` answers 404 and its tools vanish silently | Task 4 Steps 2 and 3, the Gate |
| F7 | Pinning RunLore moves nothing for the AI platform: the cluster applies ai-native-ref only through its pinned artifact | Task 9 |
| F5 | The principal never reaches OpenBao on aws-0, and RunLore's client stays off silently (the env is `optional`) | Task 6 Step 2, the Gate |

## File structure

| File | Change | Task |
|---|---|---|
| `flux/sources/gitrepo-runlore.yaml:49`, `observability/base/runlore/helmrelease.yaml:96-97,106` | the pin | 1 |
| `observability/base/runlore/helmrelease.yaml:12-17,59-66` | one replica | 2 |
| `observability/base/runlore/helmrelease.yaml`, after `:521` (`forge`) | `config.curate` | 3, 7 |
| `observability/base/runlore/helmrelease.yaml:323-348`, `:536-537` (`server`) | the router's ingress, `server.mcp.enabled` | 4 |
| `docs/superpowers/specs/2026-10-12-ai-platform-split-design.md:159-162` | H8 | 4 |
| `observability/base/runlore/helmrelease.yaml` (`config.model`) | `model.pricing` | 5 |
| `flux/sources/ocirepo-ai-native-ref.yaml:15-16` | the ai-native-ref release pin | 9 |
| `observability/aws-0/kustomization.yaml:15-20`, `observability/gcp-0/kustomization.yaml:15-17` | RunLore's session switch on aws-0 | 5 |
| `observability/base/victoria-metrics-k8s-stack/vm-common-helm-values-configmap.yaml:418-425` | the route, with its `repeat_interval` | 5 |
| `observability/base/victoria-metrics-k8s-stack/vmrules/kustomization.yaml:28-29`, `vmrules/runlore-spend.yaml` (new) | the rules, the spend | 5 |

---

## PR 3: RunLore on aws-0

### Task 1: Pin RunLore `vL1`

**Files:** `flux/sources/gitrepo-runlore.yaml:49`, `observability/base/runlore/helmrelease.yaml:96-97,106`

- [ ] **Step 1: Read the release.** `gh release view -R Smana/runlore --json tagName,publishedAt`, then
  `git -C <RL> grep -n 'queue_issue' vL1 -- internal/config` and `git -C <RL> grep -n '"/mcp"' vL1 -- internal/server`.
  Expected: RunLore PR 2's tag and a hit for each. Otherwise stop. Note `queue_issue.schedule`'s form.
  `/mcp` sits behind `server.mcp.enabled` (RunLore plan KP2), which Task 4 sets.
- [ ] **Step 2:** Change `tag: v0.18.0` to `tag: vL1` and `tag: "0.18.0"` to `tag: "<vL1 without v>"`,
  and make the comment at `:96-97` name `vL1`.
- [ ] **Step 3: Verify, commit.** `yq '.spec.ref.tag' flux/sources/gitrepo-runlore.yaml` and
  `yq '.spec.values.image.tag' observability/base/runlore/helmrelease.yaml` print `vL1` and `<vL1 without v>`.

```bash
git add flux/sources/gitrepo-runlore.yaml observability/base/runlore/helmrelease.yaml
git commit -m "feat(runlore): pin vL1, the knowledge queue and the knowledge MCP"
```

### Task 2: One replica on its volume (G8)

**Files:** `observability/base/runlore/helmrelease.yaml:12-17,59-66`

- [ ] **Step 1:** Set `replicaCount: 1`, and keep `workloadKind: StatefulSet` and `persistence`. Replace the
  comment at `:59-64` with: "One replica on its volume (G8, RK15). Each StatefulSet replica owns an RWO
  volume, and the soaks (`factory.jsonl`) sit beside the outcome ledger on it, so a failover lost
  them. The StatefulSet keeps its claim; a Deployment would template another." At `:12-17`, drop
  "this deployment is the live validation of exactly that".
- [ ] **Step 2: Render, check.** Run `./scripts/ci/validate-manifests.sh`. Expected: `All gates passed`. Then:

```bash
yq ea 'select(.kind == "StatefulSet") | [.spec.replicas, (.spec.volumeClaimTemplates | length)]' .bundle/chart-*-runlore-runlore.yaml
yq ea 'select(.kind == "PodDisruptionBudget") | .metadata.name' .bundle/chart-*-runlore-runlore.yaml
```

Expected: `[1, 1]` for each render; no PDB.

- [ ] **Step 3:** `git commit -am "fix(runlore): one replica on its volume, so a restart keeps a soak (G8)"`

### Task 3: The knowledge queue; the sweeps act

**Files:** `observability/base/runlore/helmrelease.yaml`, a `curate` block after `forge` (`:521`), before `cloud`

- [ ] **Step 1: The values.** No `schedule`: the session's switch-off step runs `lore curate queue-issue`.

```yaml
      curate:
        # The `Knowledge queue` issue on forge.kb_repo, linked by one Slack line (RK4). Rewritten at
        # each demo session's end by `lore curate queue-issue` (runbook 25): RunLore runs only in sessions.
        queue_issue:
          slack: true
        # apply: the sweeps comment, label and close, and the factory's `Resolve` and `ready-to-merge` go
        # through the same guard, which dry-run would block (the curator's own draft is not gated). `interval` stays the
        # chart's 6h: a shorter one makes Suppress and Dedup act on the open PRs before the first queue
        # lists them (RK17). ready-to-merge does not wait for a sweep (RunLore's Curation.Once).
        sweeps:
          mode: apply
        # Off until the first queue has listed the backlog (RK17); PR 3b restores the chart's 720h.
        stale_after: 0s
```

- [ ] **Step 2: Replay the config.** Render the chart at `vL1` with these values and the overlay's
  `runlore-factory-values`, then load the result through `vL1`'s `config.Load` (the procedure in
  `helmrelease.yaml:93-95`). Expected: no error. Then
  `yq ea 'select(.kind == "ConfigMap") | .data."runlore.yaml"' .bundle/chart-*-runlore-runlore.yaml | yq '.curate'`.
  Expected: `stale_after: 0s`, `sweeps.mode: apply`, `queue_issue` present, and no `sweeps.interval`
  key, so the chart's 6h holds (F1, F2).
- [ ] **Step 3:** `git commit -am "feat(runlore): the knowledge queue; sweeps apply, the stale pass held for the first queue"`

### Task 4: The agent router reaches `/mcp`, which RunLore serves; the contract

**Files:** `observability/base/runlore/helmrelease.yaml:323-348` (ingress) and `:536-537` (`server`); `docs/superpowers/specs/2026-10-12-ai-platform-split-design.md:159-162`

- [ ] **Step 1: The ingress.** Add this after the `room-broker` entry, and add "the room broker and the
  agent router" to "In-cluster callers" at `:326`:

```yaml
        # The agent router's `runlore-kb` MCP target: kb_search and kb_get at /mcp on this port.
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: agent-gateway
          podSelector:
            matchLabels:
              gateway.networking.k8s.io/gateway-name: agent-router
```

- [ ] **Step 2: Switch `/mcp` on (F6).** In `config.server`, beside `webhook_token_env` (`:536-537`), add
  `mcp: {enabled: true}` with the comment "The agent router's `runlore-kb` target reads the knowledge base
  here (RK12). No token, by the owner's decision: any caller the port admits reaches it, it is read-only
  and serves public text (RK13). RunLore warns at start-up that `/mcp` has no token; that line is expected."
  Set no `token_env`.
- [ ] **Step 3: Render, check (F4, F6).** Run `./scripts/ci/validate-manifests.sh`, then
  `yq ea 'select(.kind == "NetworkPolicy") | .spec.ingress[0].from[] | select(.namespaceSelector.matchLabels."kubernetes.io/metadata.name" == "agent-gateway") | .podSelector.matchLabels' .bundle/chart-*-runlore-runlore.yaml`.
  Expected: `gateway.networking.k8s.io/gateway-name: agent-router`. Then
  `yq ea 'select(.kind == "ConfigMap") | .data."runlore.yaml"' .bundle/chart-*-runlore-runlore.yaml | yq '.server.mcp.enabled'`.
  Expected: `true` (Task 3 Step 2's replay through `config.Load` already covers the key's name). Also run
  `git grep -n mcp -- observability/base/runlore/httproute.yaml`. Expected: nothing.
- [ ] **Step 4: H8, in both places.** In `docs/superpowers/specs/2026-10-12-ai-platform-split-design.md:159-162`,
  end the paragraph's last sentence with: "…and its ingress admits `agent-system`'s `room-broker` and
  `agent-gateway`'s `agent-router`, which reads the knowledge base at `/mcp` on 8080. The rule is L4: any
  caller the port admits reaches `/mcp`, which is read-only and serves public text. RunLore itself is a
  session switch on aws-0." ai-native-ref's `HOST-CONTRACT.md` H8 takes these words exactly (its Task 1).
- [ ] **Step 5:** `git commit -am "feat(runlore): admit the agent router to the knowledge MCP and switch it on; H8 names it"`

### Task 5: RunLore's session switch on aws-0, its route, its rules and its spend

**Files:** `observability/aws-0/kustomization.yaml:15-20`; `observability/gcp-0/kustomization.yaml:15-17`;
`observability/base/victoria-metrics-k8s-stack/vm-common-helm-values-configmap.yaml:418-425`;
`observability/base/victoria-metrics-k8s-stack/vmrules/kustomization.yaml:28-29`; create `vmrules/runlore-spend.yaml`;
`observability/base/runlore/helmrelease.yaml` (`config.model`)

- [ ] **Step 1: aws-0.** `# - ../base/runlore` stays commented, its comment replaced with: "RunLore, a
  session switch (RK15): on for a demo session, off after. Flip it with the Alertmanager route in
  vm-common-helm-values-configmap.yaml and the two runlore rule files, and with aws-0's factory copies
  in ai-native-ref (runbook 25). Uninstalling keeps its PVCs."
- [ ] **Step 2: gcp-0's comment.** "Off; RunLore's demo sessions run on aws-0 (RK15)."
- [ ] **Step 3: The route.** `- receiver: "runlore"` / `continue: true` stay commented, with a third
  commented line `repeat_interval: 1h` (the root's 12h would make the next generation wait half a day
  in a session; 1h stays above `recurrence_cooldown: 30m` and the 30m `dedup.window`, so a repeat after a decided
  generation files the next one; a repeat while a generation is undecided files nothing, RunLore plan KP8, so the
  hourly repeat adds no stub and no triager run during a fix). Replace `:421-423` with: "RunLore's session switch
  (observability/aws-0/kustomization.yaml)."
- [ ] **Step 4: The rules.** At `:28-29`, `# - runlore.yaml` and a new `# - runlore-spend.yaml`, both
  commented, under the same comment.
- [ ] **Step 5: The price (RK20).** In `observability/base/runlore/helmrelease.yaml`, under
  `config.model`, set `pricing: {input_usd_per_mtok, output_usd_per_mtok, cached_input_usd_per_mtok}`
  to the configured model's rates from its provider's price page, with a comment naming the page and
  the date read, as the factory's `meter.prices` entries do. It sits in the always-on base: inert while
  RunLore is off.
- [ ] **Step 6: The spend (RK20).**

```yaml
# RunLore's model spend in dollars a day (RK20, step 1): measured over its first session; PR 3c alerts.
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: runlore-spend
  namespace: observability
  labels:
    app.kubernetes.io/name: runlore
    app.kubernetes.io/part-of: runlore
spec:
  groups:
    - name: runlore.spend
      interval: 5m
      rules:
        # Dollars a day of every delivered investigation, recalls included, priced from model.pricing.
        - record: runlore:investigation_cost_usd:increase1d
          expr: sum(increase(runlore_investigation_cost_usd_sum[1d]))
```

- [ ] **Step 7: Commit the edits first.** `git add -N observability/base/victoria-metrics-k8s-stack/vmrules/runlore-spend.yaml`
  (`validate-vmrules.sh` lists files with `git ls-files`, so a new file is invisible until it is added),
  then:

```bash
git add observability/
git commit -m "feat(observability): RunLore's session switch on aws-0, with its route, its rules and its spend"
```

- [ ] **Step 8: Render, check, both states.** The PromQL step counts `runlore.spend` in both states, since the
  file is tracked and the kustomization comment does not hide it from `validate-vmrules.sh`. Off, as
  committed: `./scripts/ci/validate-manifests.sh` prints `All gates passed` and no
  `.bundle/chart-observability-aws-0-runlore-runlore.yaml` exists.
  On: uncomment the three places in the working tree and run it again: `All gates passed`, the bundle
  exists, its RunLore config holds `model.pricing` with three non-zero rates, and
  `kubectl kustomize observability/base/victoria-metrics-k8s-stack | yq 'select(.metadata.name == "vm-common-helm-values") | .data."values.yaml"' | yq '.alertmanager.config.route.routes[1]'`
  prints `receiver: runlore`, `continue: true`, `repeat_interval: 1h`. Then
  `git checkout -- observability/aws-0/kustomization.yaml observability/base/victoria-metrics-k8s-stack`
  restores the committed off state (the commit of Step 7, which keeps Steps 1 to 6).

### Task 6: Check, push, PR

- [ ] **Step 1:** `task check`. Expected: exit 0.
- [ ] **Step 2:** `git fetch origin && git rebase origin/main && git push -u origin feat/runlore-aws-0`.
  Title: `feat(runlore): a session switch on aws-0: one replica, the knowledge queue, the router's MCP, RunLore vL1`.
  Body: R1–R8, and the owner's session step (F5), run once on aws-0 before the first session (the
  chart's mount of its key is optional, so ai-native-ref's PR 4 merges safely first):

```bash
IDP_URL=https://auth.<public_domain_name> PRIVATE_DOMAIN=<private_domain_name> \
  scripts/provision/zitadel-oidc-clients.sh sync --cluster aws-0 --cloud aws --region eu-west-3 \
  --openbao-url <openbao_url> --openbao-root-token-secret <root_token_secret_name> \
  --openbao-ca-file <ca.pem> --mirror-openbao --apply
```

  Expected: `runlore` converged, with `runlore-factory-principal` and `agents-runlore-principal` among
  the mirrored keys. No attribution line.

---

## PR 3b: the stale sweep

### Task 7: Close the backlog nobody kept (RK17)

- [ ] **Step 1: Gate.** Live 4 has been recorded (ai-native-ref runbook 25): the first `Knowledge queue`
  issue lists the backlog. Otherwise stop.
- [ ] **Step 2:** Change `stale_after: 0s` to `stale_after: 720h`, with the comment "RK17: the backlog has been through the
  first queue (live 4); this closes what nobody kept."
- [ ] **Step 3:**

```bash
task check
git commit -am "feat(runlore): the stale sweep closes the knowledge backlog nobody kept (RK17)"
git fetch origin && git rebase origin/main && git push -u origin feat/runlore-stale-sweep
```

## PR 3c: the daily spend alert

### Task 8: Alert at 80% of the daily cap (RK20)

- [ ] **Step 1: Gate.** Runbook 25 records `D`, in dollars: the first session's highest daily
  `runlore:investigation_cost_usd:increase1d`. Otherwise stop.
- [ ] **Step 2: The alert**, in `vmrules/runlore-spend.yaml`: `RunloreDailySpendHigh`, `expr:
  runlore:investigation_cost_usd:increase1d > <0.8 × 1.5 × D>`, `for: 15m`, `severity: warning`,
  its annotation naming the cap (`1.5 × D` a day) and the session it was measured on.
- [ ] **Step 3:** `./scripts/ci/validate-manifests.sh` counts the group as checked; `task check` exits 0.

```bash
git commit -am "feat(observability): RunLore's daily spend alert at 80% of its cap (RK20)"
git fetch origin && git rebase origin/main && git push -u origin feat/runlore-spend-alert
```

## PR 4b and PR 7b: the host pins ai-native-ref's release

### Task 9: Move the pin the AI platform reaches the cluster through (F7)

The host applies ai-native-ref only through `OCIRepository/ai-native-ref`, pinned by tag and digest and
cosign-verified (`flux/sources/ocirepo-ai-native-ref.yaml:15-16`, `HOST-CONTRACT.md` H1). Merging
ai-native-ref's PR 4 changes nothing on aws-0 until a release carries it and this pin moves. **That
release is an owner decision, as every release is**; the plan does not cut it.

**Files:** `flux/sources/ocirepo-ai-native-ref.yaml:15-16`

- [ ] **Step 1: Gate.** The owner has cut the ai-native-ref release (or its PR pre-release) that carries
  PR 4 (for 7b: PR 7). `gh release view -R Smana/ai-native-ref --json tagName,publishedAt`. Otherwise stop.
- [ ] **Step 2: Move the pin.** Set `tag` to the release and `digest` to its digest
  (`crane digest ghcr.io/smana/ai-native-ref:<tag>`), keeping the cosign `verify` block. Run
  `./scripts/ci/validate-manifests.sh`: `scripts/ci/ai-overlay.sh` reads this pin, so CI renders what the
  cluster applies.
- [ ] **Step 3: One PR per session switch.** Every flip of the session switch (runbook 25) is a host PR
  carrying the three places, and this pin whenever ai-native-ref changed since the last one.

```bash
git add flux/sources/ocirepo-ai-native-ref.yaml
git commit -m "chore(flux): pin ai-native-ref <tag>, RunLore's knowledge base"
git fetch origin && git rebase origin/main && git push -u origin feat/ai-native-ref-pin
```

## Gate

- [ ] `task check` exits 0 on each PR's head.
- [ ] Live 1 (ai-native-ref runbook 25, aws-0):
  - One pod, `runlore-0`, with one Bound PVC.
  - With a soak pending, `kubectl delete pod runlore-0 -n runlore`: the verdict still lands at the
    soak's deadline.
  - `kubectl get secret runlore-factory-principal -n runlore -o json | jq '.data.FACTORY_CLIENT_ID | length > 0'` prints `true` (F5).
  - The token request to ZITADEL answers.
  - Alertmanager's `runlore` webhook does not fail.
  - The router's `/mcp` call answers, with no Hubble drop on `runlore:8080` from `agent-gateway`: the
    internal triager's `tools/list` through the router names `runlore-kb_kb_search` and `runlore-kb_kb_get`
    (a `404` would drop them silently behind `FailOpen`; F6).
  - A reset on the token request calls for an aws-0 identity-provider policy (R7).
