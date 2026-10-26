# The factory from your coding agent, PRs 6 and 7: adopt the release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the agent-platform release that carries feature 13 (its PRs 1–5), turn the broker's
`/mcp` on with `human.mcp.sessionStart: []`, and document it. A suite holds `sessionStart` empty.
ADR-0059 records the decisions, the user guide teaches `roomctl setup` and the four views with a
portability table, and runbook 19 is the platform session's live checklist. In cloud-native-ref, the
drifted v0.11.0 skill copy goes.

**Architecture:** Seven tasks in ai-native-ref, one pull request, each commit leaving `task check`
green. Task 8 is a separate cloud-native-ref pull request.

- **Task 1** reads the release and changes nothing. If the release is missing or lacks the names
  below, the plan stops.
- **Task 2** moves every agent-platform pin and turns `/mcp` on in the same commit, with the
  off-check for `sessionStart` written test first.
- **Tasks 3–5** write ADR-0059, the user guide section and runbook 19.
- **Task 6** links the design and both plans from the status page and the roadmap.
- **Task 7** verifies, pushes and opens the pull request.
- **Task 8**, in cloud-native-ref, merges before runbook 19 runs: until it does, `roomctl doctor`'s
  `skill` check FAILs in every cloud-native-ref checkout on the drifted copy, and runbook 19 step 2
  needs every check `ok`.

**Tech Stack:** Python 3 with PyYAML (the suites, run by `scripts/ci/run-tests.sh` inside
`.composite/`), Hugo (the site), `oras`, `cosign`, `helm` and `gh` to read the release, Flux 2.

**Spec:** [the design](../specs/2026-10-25-factory-from-your-agent-design.md): FA1, FA4, FA5, FA7,
FA9, "Setup and portability", "The switch", the live proofs, rows 6 and 7 of "Pull requests, in
order", and "Roadmap and decisions". The roadmap's D7, feature 13's row and the status page's row
are already on `main` with the design. The names come from agent-platform's plan,
`docs/superpowers/plans/2026-10-25-factory-from-your-agent-plan.md`:

- the broker config key `human.mcp.sessionStart` (a list of `owner/name`);
- the tools `rooms_list`, `room_summary`, `room_changes`, `issue_draft` (`canStart`), `issue_file`,
  `room_wait`, `room_checkout`, and the prompts `handoff`, `status`, `inbox`;
- the commands `roomctl setup <claude|opencode|codex|gemini|cursor|copilot> [--project] [--print]`,
  `roomctl changes <room>`, `roomctl checkout <room>`, and the doctor check `skill`.

**Owner decision, 2026-10-25:** `/mcp` has been off in every committed config. Only runbook 18's
gcp-0 session turns it on. Feature 13's tools all go through it, so this PR turns it on in base, as
the spec's "The switch" shows. `/mcp` admits only roomctl's token and sponsored principals, and
`sponsored` stays empty.

**Out of these PRs:** listing a repository in `sessionStart` (a gcp-0 session's copy, by runbook
19), the live proofs themselves, and every agent-platform change.

## Global Constraints

- **Worktree:** `.claude/worktrees/feat+factory-from-your-agent-adopt`, branch
  `feat/factory-from-your-agent-adopt`, from a freshly fetched `origin/main`. Rebase onto it before
  every push.
- **`task check` is the evidence** (AGENTS.md): run it before each commit. On macOS, four suites fail
  for reasons outside this change (BSD `sed -i`, no GNU `timeout`, Docker Desktop bind mounts, an
  unreachable registry). Compare against `origin/main` on the same machine, and let CI judge.
- **The start is held off (D4):** no committed broker config lists a `human.mcp.sessionStart` entry
  or a `human.mcp.sponsored` one.
- **gcp-0's broker config is base's plus `suspend`** (`test-room-broker-suspend.py`): every change to
  base's `config.yaml` is made in `infrastructure/gcp-0/room-broker/config.yaml` too.
- **The site links outside itself by absolute URL only**; the PR's "External links 🔗" job fetches
  every new one, so a URL to a file not yet on `main` waits for a later PR.
- **Doc paths:** every backticked repository path in `website/content/` must exist here or on the
  host (`scripts/ci/verify-doc-paths.sh`).
- **Wording, verbatim from the spec:** "Approvals stay on the room page"; the states `needs you`,
  `waiting for a human`, `running`, `queued`, `done`, `failed`, `stopped`; "a form field, never a tool
  argument".
- **Versions:** ai-native-ref pins agent-platform **v0.22.0** (PR J, #116). The release this plan
  adopts is **v0.23.0**, so `vX.Y.Z` below is `v0.23.0`. The diff base is always the tag pinned now,
  read from the repository, never a literal.
- **Commits:** conventional, in English, no trailers.

## Review Focus

- **The key lands before the release that reads it.** The broker decodes strictly, so an older
  image refuses `sessionStart` and the rollout fails. Task 1 checks the key in the release's source,
  and Task 2 moves the pins and the key in one commit.
- **A gcp-0 session forgets to empty `sessionStart`.** The suite from Task 2 fails on `main`, and
  runbook 19's last step removes the entry.
- **The portability table claims more than was proven.** Only Claude Code and OpenCode can become
  "proven", with the session's date, and neither is until runbook 19 runs. Every other cell links its
  source, and an unconfirmed cell says so. Task 4's step 3 checks this.
- **ADR-0056 reads as fully superseded.** Only D2 is; D1 is amended and D3–D7 stand. The index row
  says "Partly superseded".
- **Runbook 19 runs in only one client.** Each live proof has a column per client, and a proof passes
  only when both are filled.

---

### Task 1: Read the release

**Files:** none in the repository. Writes `$SCRATCH/vX.Y.Z.env`, `$SCRATCH/crd-rooms-vX.Y.Z/` and a
clone at `$SCRATCH/agent-platform`.

**Interfaces:**
- Produces: `$SCRATCH/vX.Y.Z.env`, which defines `CHART_DIGEST`, `FACTORY_DIGEST`, `BROKER_DIGEST`,
  `SLACK_DIGEST`, `BRIDGE_DIGEST` and `HARNESS_DIGEST`, each `sha256:<64 hex>`. It also produces
  `$SCRATCH/crd-rooms-vX.Y.Z/crd-rooms.yaml`. Task 2 reads both.

- [ ] **Step 1: Find the release**

Run: `gh release list -R Smana/agent-platform --limit 5 --json tagName,isDraft,isPrerelease,publishedAt`
Expected: `v0.23.0`, not a draft or prerelease, published after agent-platform PR 5 merged. Call it
`vX.Y.Z` below. The pinned one is v0.22.0 since PR J (#116); read it rather than assume it:

```bash
BASE=$(git grep -h 'tag: "' flux/sources/ocirepo-agent-factory.yaml | grep -o -E 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "$BASE"
```

Expected: `v0.22.0`. Anything else, stop: another pin PR is in flight.

- [ ] **Step 2: Check that it carries the feature**

```bash
git clone --quiet --filter=blob:none https://github.com/Smana/agent-platform "$SCRATCH/agent-platform"
git -C "$SCRATCH/agent-platform" grep -n -E 'json:"sessionStart|"room_wait"|"room_checkout"|"room_changes"' vX.Y.Z -- internal
```

Expected: `sessionStart` in `internal/config/config.go`, and each tool name at least once, as the
value of a Go `const` in `internal/` (agent-platform's plan names each tool by a constant: L16). If
any is missing, stop and report it.

- [ ] **Step 3: Read the digests, and check the chart's signature**

```bash
V=X.Y.Z
cat > "$SCRATCH/v$V.env" <<EOF
CHART_DIGEST=$(oras resolve ghcr.io/smana/charts/agent-factory:$V)
FACTORY_DIGEST=$(oras resolve ghcr.io/smana/agent-factory:v$V)
BROKER_DIGEST=$(oras resolve ghcr.io/smana/room-broker:v$V)
SLACK_DIGEST=$(oras resolve ghcr.io/smana/factory-slack-app:v$V)
BRIDGE_DIGEST=$(oras resolve ghcr.io/smana/room-bridge:v$V)
HARNESS_DIGEST=$(oras resolve ghcr.io/smana/agent-harness:v$V)
EOF
cat "$SCRATCH/v$V.env"
helm show chart oci://ghcr.io/smana/charts/agent-factory --version "$V" | grep appVersion
source "$SCRATCH/v$V.env"
cosign verify "ghcr.io/smana/charts/agent-factory@$CHART_DIGEST" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github\.com/Smana/agent-platform/\.github/workflows/release\.yaml@refs/tags/v.*$' \
  > /dev/null; echo "exit=$?"
```

Expected: six `sha256:` lines, then `appVersion: vX.Y.Z`, then `exit=0`. On a `not found` or a
failed verification, stop.

- [ ] **Step 4: What the release changes beside feature 13**

```bash
git -C "$SCRATCH/agent-platform" diff --stat "$BASE" vX.Y.Z -- \
  charts/agent-factory internal/factory/config internal/config internal/store/migrations
gh release download vX.Y.Z --repo Smana/agent-platform --pattern crd-rooms.yaml --dir "$SCRATCH/crd-rooms-vX.Y.Z"
diff <(tail -n +4 infrastructure/base/room-broker/crd-rooms.yaml) "$SCRATCH/crd-rooms-vX.Y.Z/crd-rooms.yaml"
```

| Path | Expected | If it differs |
|---|---|---|
| `internal/config` | `MCPConfig` gains `SessionStart []string`, validated as `owner/name` | **Stop and report** any other new required key |
| `internal/factory/config` | Unchanged by feature 13. If `perPerson.dailyTokens` is now refused (`tooling/base/agent-factory/helm-values-configmap.yaml:256`), remove it in Task 2 | **Stop and report** on a new required key |
| `charts/agent-factory/templates/`, `values.yaml` | Unchanged | **Stop and report**: a new object or RBAC rule is a decision beyond this plan |
| `internal/store/migrations` | Any. The broker migrates at start | Note it in the PR body |
| `crd-rooms.yaml` | Unchanged, or additive | Re-copy it in Task 2 |

### Task 2: Pins, `/mcp` on, and the start held off

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml`,
  `infrastructure/base/room-broker/app.yaml`, `infrastructure/base/room-broker/retention-cronjob.yaml`,
  `infrastructure/base/room-broker/sqlinstance.yaml`, `infrastructure/base/room-broker/crd-rooms.yaml`,
  `tooling/base/agent-factory/slack-app/deployment.yaml`,
  `infrastructure/base/karpenter-nodepools-agents/headroom/deployment.yaml`, and the "pinned here at"
  mentions in `observability/base/agent-platform/vmrule-agent-factory.yaml`,
  `website/content/docs/platform/ai-platform/agents/harness-reference.md` and
  `website/content/docs/platform/ai-platform/routing.md` (`git grep -n -F "${BASE#v}"`, from Task 1,
  lists them all)
- Modify: `infrastructure/base/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml`
- Test: `scripts/ci/tests/test-factory-interfaces-off.py`

- [ ] **Step 1: Write the failing check**

In `test-factory-interfaces-off.py` clause 2, next to the `sponsored` check:

```python
        if ((doc.get("human") or {}).get("mcp") or {}).get("sessionStart"):
            problems.append(f"{rel} lists human.mcp.sessionStart (D4: a gcp-0 session's copy only, runbook 19)")
```

Add "no repository may start from a session" to the module docstring and to the PASS line. Then add
a scratch entry: `yq -i '.human.mcp.sessionStart = ["Smana/cloud-native-ref"]' infrastructure/gcp-0/room-broker/config.yaml`.

- [ ] **Step 2: Run it, and see it fail**

Run: `python3 scripts/ci/tests/test-factory-interfaces-off.py`
Expected: FAIL, naming `infrastructure/gcp-0/room-broker/config.yaml lists human.mcp.sessionStart`.
Then `git checkout -- infrastructure/gcp-0/room-broker/config.yaml`, and run it again. Expected: PASS.

- [ ] **Step 3: Move every pin to `vX.Y.Z`**

Use the tags and digests from Task 1. The chart's tag has no `v`, while each image's `tag` is
`vX.Y.Z@<digest>`. `sqlinstance.yaml`'s `ref` moves too. Re-copy `crd-rooms.yaml` from
`$SCRATCH/crd-rooms-vX.Y.Z/` under its 3-line header. Comments that name the version change with it,
except those that say since when something holds (for example "since agent-platform v0.16.0").

- [ ] **Step 4: Turn `/mcp` on, with the start empty**

In both config files, replace the commented `mcp:` example under `human:` with live keys. The
`sponsored` example stays commented beneath them:

```yaml
  # The developer's MCP server (roomctl mcp, ADR-0059): only roomctl's token and sponsored principals
  # are admitted. sessionStart lists the repositories whose issue_file form offers "start the factory
  # now", applied with the developer's own gh (FA5); none here (D4), a gcp-0 session lists one (runbook 19).
  mcp:
    enabled: true
    sessionStart: []
    # Sponsored principals (factory interfaces part 2), none declared (D4): …the existing comment…
    # sponsored:
    #   - name: slack-app
    #     clientIDFile: /etc/room-broker/sponsored/slack-app-client-id
```

- [ ] **Step 5: Run the gates**

Run: `task check`
Expected: these pass: the pins suite, `test-factory-interfaces-off`, `test-room-broker-suspend` (the
two copies still differ in `suspend` alone) and `test-room-broker-config-rollout` (the config edit
rolls the pods). `validate` renders both clusters.

- [ ] **Step 6: Commit**

```bash
git add -A flux tooling infrastructure observability website scripts/ci/tests/test-factory-interfaces-off.py
git commit -m "feat(agent-factory): agent-platform vX.Y.Z, the factory from your coding agent: /mcp on, its start held off"
```

### Task 3: ADR-0059

**Files:**
- Create: `website/content/docs/decisions/0059-factory-from-your-coding-agent.md`
- Modify: `website/content/docs/decisions/_index.md`, `website/content/docs/decisions/0056-local-first-factory-ux.md`

- [ ] **Step 1: Write the ADR** in ADR-0058's shape. Front matter: `title`, `linkTitle: 0059 · The
  factory from your coding agent`, `weight: 590`, `description`, `lastVerified: <today>`. Then:
  Status (Accepted), Date (2026-10-25), Deciders, and Related (the design and the roadmap's D7 by
  absolute URL, ADR-0049 and ADR-0056 by `relref`).

| Section | Holds |
|---|---|
| Context | ADR-0056 D2 deferred a local MCP server, and `roomctl mcp` has shipped since v0.17.0 but `/mcp` was off here. Developers want to start and follow work from any coding agent, and the agent can already label with their `gh` |
| Decision drivers | Portable across clients; the human, not the model, starts work; approvals stay where the command and diff are shown; views that untrusted text can't break |
| Considered options | Who renders (A broker, B roomctl, C the skill); how work starts (a form field, a browser click, the label only); approvals (room page, session form); bringing back (worktree, in place, link only); install (setup, plugins, both) |
| Decision outcome | FA2, FA4, FA5, FA7, FA8, FA9, and `/mcp` on in this deployment with `sessionStart` empty (the owner, 2026-10-25) |
| Consequences | Positive: one view everywhere, no GitHub trip to start. Negative: **the accepted risk**, quoted: "a client that auto-accepts forms (some headless modes) lets the agent start work". Neutral: MCP Apps later on the same tools |

- [ ] **Step 2: Mark ADR-0056.** Under its Status line, add: "**Partly superseded** by
  [ADR-0059]({{< relref "/docs/decisions/0059-factory-from-your-coding-agent.md" >}}): D2 (a local
  MCP server now ships), and D1 amended (a confirmation form may start the work)."

- [ ] **Step 3: Index.** In `_index.md`, add the 0059 row (Accepted, 2026-10-25), and change 0056's
  status cell to `Partly superseded by [0059](…): D2, D1 amended`, in the shape of 0050's row.

- [ ] **Step 4: Build**

Run: `task docs`
Expected: the Hugo build passes (`refLinksErrorLevel: ERROR` resolves both `relref`s), and the doc-path
check passes.

- [ ] **Step 5: Commit**

```bash
git add website/content/docs/decisions
git commit -m "docs(decisions): ADR-0059, the factory from your coding agent"
```

### Task 4: The user guide

**Files:**
- Modify: `website/content/docs/platform/ai-platform/agents/user-guide.md`, section `### Hand off from your coding agent`, and the `roomctl` block in `### From a terminal: roomctl`

- [ ] **Step 1: Rewrite the section** around setup, then what you say. Drop the symlink advice and
  "`cloud-native-ref` carries it": `setup` writes the skill where each client reads it.

| Part | Content |
|---|---|
| Set it up | Needs `roomctl` vX.Y.Z or later. `roomctl setup <client>` (user-level; `--project` to commit it; `--print` to see what it would do), then `roomctl doctor` |
| What you say, what happens | `/factory:handoff …` drafts the issue, and the form files it and can start it; `/factory:status [room or #issue]` shows the card; `/factory:inbox` shows what needs you; "wait for it" runs `room_wait`; "check it out" runs `room_checkout` |
| What you see | One card mockup, copied from the design's view 2. The state words |
| What stays on the room page | Approvals and steering, ADR-0049. The card links to them |
| Safety | The start is a form field the model can't fill in, offered only on repositories the platform lists. A checkout that changes agent or editor config asks first |

- [ ] **Step 2: Add the portability table**: one row per client (Claude Code, OpenCode, Codex CLI,
  Gemini CLI, Copilot CLI, Cursor), with columns for tools and text views, forms, URL forms, slash
  commands, background wait, and skill directory. Claude Code and OpenCode are "documented" until
  runbook 19 marks them "proven" with the session's date. Each other cell links its source from
  [the research](../specs/2026-10-25-factory-from-your-agent-research.md#2-what-an-mcp-integration-can-rely-on-per-client),
  and an unconfirmed cell says "unconfirmed".

- [ ] **Step 3: Check the claims.** No cell says "proven" yet. Every command shown is in
  `roomctl help` of vX.Y.Z (`$SCRATCH/agent-platform`, `go run ./cmd/roomctl help`).

- [ ] **Step 4: Update the `roomctl` block** with `roomctl changes <room>`, `roomctl checkout <room>`
  and `roomctl setup <client>`.

- [ ] **Step 5: Build, then commit**

Run: `task docs`. Expected: PASS.

```bash
git add website/content/docs/platform/ai-platform/agents/user-guide.md
git commit -m "docs(agents): the factory from your coding agent, in the user guide"
```

### Task 5: Runbook 19, the live proofs

**Files:**
- Create: `docs/runbooks/agent-factory/19-factory-from-your-agent.md`
- Modify: `docs/runbooks/agent-factory/README.md` (the index), `docs/runbooks/agent-factory/18-factory-interfaces.md` (its gcp-0 config row: `human.mcp.enabled` is already on, since vX.Y.Z)

- [ ] **Step 1: Write the runbook** in runbook 18's shape. Start with the purpose and the design
  link, then a mermaid sequence of the journey. Prerequisites: `roomctl vX.Y.Z` logged in, both
  clients installed, and Task 8's cloud-native-ref pull request merged: until it is, the doctor's
  `skill` check FAILs on the drifted v0.11.0 copy in every cloud-native-ref checkout (step 2). Then:

| Section | Steps |
|---|---|
| 1. The switch-on | In the session's PR, gcp-0's broker copy lists one repository in `human.mcp.sessionStart`. `test-room-broker-suspend.py`'s parity widens to `suspend` and `human.mcp.sessionStart`. `test-factory-interfaces-off.py`'s `sessionStart` check skips gcp-0's copy |
| 2. Setup | `roomctl setup claude` and `roomctl setup opencode`, then `roomctl doctor` with every check `ok` |
| 3. Live proofs 1–5 | The design's five, each a table row with *Do*, *Expected* and a PASS or FAIL column **per client** |
| 4. Claude Code without forms | If Claude Code declares no form mode, proofs 1 and 4 take the no-forms path and the result says so (spec, Gate) |
| 5. Off again | Empty `sessionStart` and revert both suites; `test-factory-interfaces-off.py` passes on `main`. The user guide's two rows become "proven, <date>" |

- [ ] **Step 2: Index it** in `README.md`'s runbook table, and fix runbook 18's row.

- [ ] **Step 3: Check, then commit**

Run: `task links docs`. Expected: PASS.

```bash
git add docs/runbooks/agent-factory
git commit -m "docs(runbooks): 19, the factory from your coding agent, live proofs"
```

### Task 6: Link the design and plans

**Files:**
- Modify: `website/content/docs/platform/ai-platform/status.md` (feature 13's row), `docs/superpowers/specs/2026-10-19-v3-roadmap-design.md` (row 13), `docs/superpowers/specs/2026-10-25-factory-from-your-agent-design.md` (Status line)

- [ ] **Step 1:** In the status page's row, add
  `[design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-25-factory-from-your-agent-design.md)`
  beside its `why` link. In the roadmap's row 13, add
  `[plan](https://github.com/Smana/agent-platform/blob/main/docs/superpowers/plans/2026-10-25-factory-from-your-agent-plan.md)`
  after the design link, as feature 5's row does.
- [ ] **Step 2:** On the design's Status line, add "built in agent-platform vX.Y.Z; live proofs wait
  for a gcp-0 session (runbook 19)".
- [ ] **Step 3: Check, then commit**

Run: `task links docs`. Expected: PASS.

```bash
git add website/content/docs/platform/ai-platform/status.md docs/superpowers/specs
git commit -m "docs(v3): feature 13's design and plan linked from the roadmap"
```

### Task 7: Verify, push, open the pull request

- [ ] **Step 1:** `git fetch origin && git rebase origin/main`, then `task check`. Expected: exit 0,
  or only the four macOS suites named in Global Constraints, failing the same way on `origin/main`.
- [ ] **Step 2:** `git push -u origin feat/factory-from-your-agent-adopt`, then
  `gh pr create --title "feat(agent-factory): the factory from your coding agent, agent-platform vX.Y.Z" --body-file -`
  with a body that lists Tasks 2–6, names `/mcp` on with the start held off, notes Task 1's
  migrations, and links the design.
- [ ] **Step 3:** `gh pr checks --watch`. Expected: `ci` and "External links 🔗" green.

### Task 8: cloud-native-ref, the drifted skill copy (a separate pull request)

It merges before runbook 19 runs, and before agent-platform v0.23.0 is announced to developers: the
doctor's `skill` check reads project skill directories, and FAILs on this copy's
`roomctl-version: "v0.11.0"`.

**Files:**
- Delete: cloud-native-ref `.agents/skills/factory-handoff/` and the `.claude/skills` link to it, if
  one exists

- [ ] **Step 1:** In a cloud-native-ref worktree from `origin/main`, run
  `git grep -n -E 'factory-handoff|roomctl-version'` to find the copy and anything that names it.
- [ ] **Step 2:** Delete the copy, and replace each mention with "install it with
  `roomctl setup <client>`" (FA9: user-level by default, so no repository copy drifts again).
- [ ] **Step 3:** Run the host's own checks (`task check` or its README's equivalent). Expected:
  PASS.
- [ ] **Step 4:** Commit with `chore(agents): drop the v0.11.0 factory-handoff copy, roomctl setup
  installs it`, push, and open the pull request.
