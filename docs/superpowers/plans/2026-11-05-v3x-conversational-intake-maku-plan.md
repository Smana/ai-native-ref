# v3.x conversational intake — Implementation Plan (Maku PRs 1–4, ai-native-ref adoption A–B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One governed natural-language planner in the broker — `intake_plan`, public text only, one bounded model call through `ai-gateway` as the `planner` client — that both the coding agent and Slack reach, returning a strict `plan/v1`, its canonical hash, roles and budget from config, and at most one question, with the coding agent's `issue_file` and the later Slack `run_create` both re-validating that plan before anything is filed.

**Architecture:** Four Maku pull requests, each merging on its own offline evidence, then two ai-native-ref pull requests (the wiring with the switch off, then the switch-on behind an owner go). Maku PR 1 adds `internal/intake`: the `plan/v1` types, the canonical hash over the material set, the guards (allowlist ∩ the requester's write access, public-only), and the one bounded HTTP client whose strict decode is the only way a model's reply becomes a plan. PR 2 puts it on `/mcp` as two read-only tools (`intake_plan` and `plan_check`) behind `human.intake.plan.enabled`, with the config, the per-requester daily cap, the metrics and the one audit log line. PR 3 is the coding-agent journey: `issue_file` takes the plan and its hash and re-validates them through `plan_check`, and the `handoff` prompt and skill stop writing the plan themselves. PR 4 gives `run_create` the same plan and hash contract for the Slack proposal plan that follows, which owns the message, the controls and the approval. ai-native-ref PR A lands the secret first, then the two ExternalSecrets, the API-key `SecurityPolicy` pairing, both CNP directions, the gates, the dashboard and the docs; PR B turns the switch on for one public repository, records the decision, and runs the live proof.

**Tech Stack:** Go 1.25 (controller-runtime; `net/http` through `internal/httpx`, the audited egress client; OpenTelemetry metrics; MCP over `POST /mcp`), `sha256` canonical JSON, the AI Gateway's `chat/completions` on `tier-frontier` (GLM-5.3 via Z.ai), Cilium `CiliumNetworkPolicy`, `external-secrets` (OpenBao `apps` mount), kustomize + Flux, Python 3 gates, Hugo.

**Spec:** [the conversational developer experience design](../specs/2026-11-05-v3x-conversational-devex-design.md). This plan implements the intake half: CD1–CD8, CD14, CD15, CD17–CD20, CD27 and CD29 ([§owner-decisions](../specs/2026-11-05-v3x-conversational-devex-design.md#owner-decisions)), the planner's model call ([§model-call](../specs/2026-11-05-v3x-conversational-devex-design.md#model-call)), `plan/v1` ([§plan](../specs/2026-11-05-v3x-conversational-devex-design.md#plan)), the coding-agent journey ([§journeys](../specs/2026-11-05-v3x-conversational-devex-design.md#journeys)), [§security](../specs/2026-11-05-v3x-conversational-devex-design.md#security), [§failures](../specs/2026-11-05-v3x-conversational-devex-design.md#failures), [§config](../specs/2026-11-05-v3x-conversational-devex-design.md#config), [§observability](../specs/2026-11-05-v3x-conversational-devex-design.md#observability), [§rollout](../specs/2026-11-05-v3x-conversational-devex-design.md#rollout) steps 3 and 4, and offline proofs 1–5 and 15 ([§offline](../specs/2026-11-05-v3x-conversational-devex-design.md#offline)). Everything else in that design belongs to a sibling plan (see [Not in this plan](#not-in)).

## Global Constraints

- **Repositories and branches.** Maku is `github.com/Smana/maku`; the review used `/tmp/opencode/maku-devex-read` at `4685672f0f40973286a121f83ea92dd3428b8120`, and every `internal/…:N` citation is that commit. Set `MAKU` to the executor's checkout of `origin/main`; one worktree per PR: `git -C "$MAKU" worktree add "$MAKU-intake" -b <branch> origin/main`. Branches: PR 1 `feat/intake-core`, PR 2 `feat/intake-tools`, PR 3 `feat/intake-coding-agent`, PR 4 `feat/intake-run-create`; ai-native-ref PR A `feat/intake-plan-wiring`, PR B `feat/intake-plan-switch-on`. Rebase onto a freshly fetched `origin/main` before every push.
- **The evidence.** Maku: `task check` exits 0 (its `test` step needs a Docker daemon for the store's testcontainers, and takes envtest assets from `setup-envtest` 1.36.x itself) and `task lint` reports 0 issues. ai-native-ref: `task check` exits 0 — it builds `.composite/`, runs the host's `validate-manifests.sh`, this repository's gates, its suites, the link check, the site build, the doc-path check (a path naming a host file resolves against `.host/`) and the source check — and `task docs` exits 0. Never claim done without that output.
- **Conventions.** Maku `AGENTS.md`: `// SPDX-License-Identifier: Apache-2.0` on every `.go` file; a package doc comment in the file's register; every "no" fails towards a human with its own reason; one interface per consumer; doc comments name the design decision they implement (`CD17`, `CD18`, `CD27`). Commits are conventional, in English, with no trailers; PR titles and descriptions in English.
- **Off by default.** `human.intake.plan.enabled: false` ⇒ neither tool exists on any list (`unknown tool: intake_plan`, as `run_create` is to a human token today, `run_create.go:62`). `human.intake.plan.fallback: off` ⇒ the degraded composer is unreachable; only `composer` reaches it, and every surface labels it. The switch lands only with the release that reads it: both config decoders refuse an unknown key (`internal/config`, `internal/factory/config`).
- **Verbatim values from the spec.**
  - The route: "In-cluster, straight to the AI Gateway data-plane Service"; the pinned alias is `tier-frontier` and it is "the one alias the planner may name"; the client identity is `planner`; `temperature: 0`; the deadline is 20 s, "under the 25 s `/mcp` bound (`mcp.go:64`)"; the reply is ≤ 64 KiB; `max_tokens` ≤ 4 000.
  - The request bounds: "text ≤ 16 KiB, context ≤ 4 KiB, candidates ≤ 20".
  - `plan/v1`: "Issues | 1 to 3 in the contract; each body ≤ 16 KiB and each title ≤ 256 runes, as `CheckDraft` already bounds them"; "Evidence | At most 5 items, each ≤ 280 runes, untrusted, and never a link the broker did not build"; "Question | At most one, `{text, recommended: {answer, why}}`".
  - The hash (CD27): "SHA-256 over the canonical JSON of `{apiVersion, repository, budget: {ceilingUSD, source}, issues: [{index, title, body, class, roles, dependsOn}]}`, fields in that fixed order and issues in array order. The broker computes it; a caller may not supply it." Materiality: "The hashed set, and only it. Everything else is display". **One deliberate deviation, recorded:** the material set hashes `budget.ceilingMicroUSD` (an integer, `2000000` for $2.00) rather than the spec's `ceilingUSD` float. Two Go processes formatting a `float64` the same way is a promise Go makes and JSON does not; a cent is the smallest amount that can be filed, and an integer is the only form two processes agree on byte for byte. The plan *displays* `budget.ceilingUSD` and hashes the integer, so the displayed set and the hashed set still carry the same fact.
  - CD17: "**Roles** come from the class's template … **budget** from the class's `taskUSD` and the channel's `maxCostUSD`, and both are echoed back by the broker, not by the model. A model-named value for any of the three is dropped and logged"; the ceiling is "`min(class.taskUSD, channel.maxCostUSD)`".
  - CD18: "A small deterministic composer exists as a **degraded mode only**: off by default, labelled as not the natural-language experience, and outside the live proof".
  - CD19: "At most three issues, one defect each … Slack can file exactly one".
  - CD20: "The plan, its hash, its author and its revision live in the Slack message's metadata … Nothing is stored".
  - Data: "The planner runs only for a repository GitHub reports as public, read once per repository and cached like `repoaccess`"; "A private repository is refused (`private_repository_unsupported`) **before** any call."
  - Budget: "`human.intake.plan.dailyPlans` per requester … and one call per plan attempt — no retry loop. Tokens come from the response's `usage`".
  - Audit: "**Never the request or the plan text**"; a log line carries "the effective requester, the surface and thread or session, the repository, the plan hash, the model, the token counts, the outcome and the duration".
  - Refusals, closed: the spec's eight — `private_repository_unsupported`, `repository_not_allowed`, `no_write`, `invalid_draft`, `planner_invalid`, `planner_unavailable`, `planner_timeout`, `plan_changed` — plus the ones this plan must name because the spec leaves them to the builder: `repository_unverified` (GitHub cannot say), `repository_not_in_candidates`, `invalid_class`, `not_linked`, `daily_plans_reached`, `plan_too_large`. Each is a constant in `internal/intake/refusal.go` with one sentence; none is invented at a call site.
- **Two config keys beyond the spec's switch table, and why.** `human.intake.plan.url` (the route): a package never hard-codes a platform endpoint, and the broker's config is where `factoryURL` already lives. `human.intake.plan.repositories` (the allowlist CD5 needs): it is **not** `human.mcp.sessionStart`, which means "the form may offer to start the factory here" — listing a repository in `sessionStart` would offer a start on a repository the factory does not serve. Both are declared in ai-native-ref PR A.
- **Order of the wiring, and it is load-bearing — two orders, both required.**
  1. **The remote value first.** The shared value exists in OpenBao's `apps` mount **before** either `ExternalSecret` is applied. An `ExternalSecret` whose remote reference is missing reports `SecretSyncedError`; on the gateway that takes the *whole* `ai-gateway-api-keys` path with it, so the gateway refuses every client, not just the planner.
  2. **The release before the keys.** No `human.intake` block may land in any `infrastructure/*/room-broker/config.yaml` before the broker's image pin names a Maku release whose loader knows those keys: `scripts/ci/tests/test-maku-config-load.sh` takes the tag from `infrastructure/base/room-broker/app.yaml` and loads **all three** broker configs through *that* tag's `config.Load`, and a strict decoder refuses an unknown key — so the keys in any copy fail the gate (correctly) until the pin moves. `enabled: false` does not help: it is the key's existence the old decoder refuses.
  3. **The mount may land ahead of the release; the keys may not.** A mounted, unread Secret file is inert to an older broker; a config key is not. A1 (mount, secrets, CNPs, gates) may merge before the release; A3 (the keys) may not.
- **A private candidate is dropped, not refused.** When the asked list holds several repositories, a private one is removed from the candidate set **silently** — naming it back would tell the requester that a repository they did not name exists, and the spec's rule is that a repository outside the candidate set is "never named, not even as an alternative" (CD5, §security). A **single explicitly named** private repository is refused with `private_repository_unsupported` and its two ways forward, because the requester named it themselves and the refusal is the whole answer.
- **A private repository is refused before any model call**, and the fake endpoint's call counter is the assertion (offline proof 2).
- **The metric names are `intake_*` in Go, not `rooms_intake_*`.** `metrics.MakuName` (`internal/metrics/metrics.go:65`) maps `rooms*` to `maku_rooms*`, so an instrument named `rooms_intake_plan_total` is served as `maku_rooms_intake_plan_total` — not the spec's `maku_intake_plan_total`, which the dashboard would then query in vain. The instruments are therefore `intake_plan_total`, `intake_plan_seconds` and `intake_plan_tokens`, `MakuName` gains the `intake_` prefix case, and `TestMakuName` pins it. `hack/names.sh` reads instrument names from `internal/metrics` and refuses the *old* `rooms_*`/`agent_factory_*` spellings only, so a new `intake_*` family is neither renamed nor refused.
- **Out of scope, and no task may add it:** `needs/v1` and the resume brief, `issue_draft`'s existing semantics, Slack's proposal message, `chat.update`, interactivity, thread status answers and the Slack forge.push approval (separate plans), the Slack channel-binding generator (CD24), storing a plan anywhere, a second decomposition engine, a cross-repository code search, private-repository planning, and the `coordination_plan` implementation (the [seam](#seam-coordination) is a contract only).
- **Owner gates.** No live cluster action, no switch-on, no Slack console change and no live proof happens before the owner's explicit go in Task A5/B2. Tasks 1–4 and A1–A4 are offline.

## Review Focus

The five input classes and failure modes this design implies but whose acceptance rows do not spell out the behaviour, most likely to bite first. Each line's test is added to the owning task, in that task's step style.

1. **A model reply naming a repository outside the candidate set.** It must be refused whole (`repository_not_in_candidates`), and the outsider's name must appear in **no** refusal sentence, log field or metric label — the reply is a guess about repositories the requester may not know exist. Owning test: PR 1, Task 1 (`TestPlanRefusesARepositoryOutsideTheCandidates`).
2. **A candidate GitHub reports private, or cannot answer for.** No call may happen for it — the fake endpoint counts zero — and it may not resurface as an "alternative" in the plan shown to the person. Owning test: PR 1, Task 2 (`TestPrivateOrUnverifiableRepositoriesNeverReachTheModel`).
3. **The model supplies its own roles, budget, or a class the config does not define.** Roles and money must be the config's even when the reply disagrees, and the class must be refused (`invalid_class`) — a reply naming `admin` or a $99 ceiling must change neither the plan nor its hash. Owning test: PR 1, Task 3 (`TestRolesAndBudgetComeFromConfigOnly`, in `compose_test.go`, because `Compose` is Task 3's).
4. **A reply at the bound: an issue body of exactly 16 KiB inside a reply of exactly 64 KiB, or one byte over.** The plan at the bound is accepted and hashes stably; one byte over is `planner_invalid` with the field and the bound named — never a truncated plan, and never a partially filled one. Owning test: PR 1, Task 3 (`TestAReplyAtTheBoundIsAcceptedAndOneByteOverIsRefused`).
5. **The same requester's two calls around the daily cap, and a deadline expiring mid-compose.** The Nth call is allowed and the N+1th refused without a request (deterministic at the boundary, not "roughly 50"), and a call that outlives the deadline returns `planner_timeout` well inside `/mcp`'s 25 s rather than hanging the tool. Owning tests: PR 2, Task 2 (`TestDailyPlanCapRefusesWithoutACall`) and PR 1, Task 3 (`TestADeadlineOverCallIsPlannerTimeout`).

---

## File structure

`internal/intake` is the broker's new planner package. It is not `internal/factory/intake` (the factory's issue poller), which this plan does not touch.

| File | Responsibility | PR |
|---|---|---|
| `internal/intake/plan.go` (new) | `plan/v1` types, the material set, `Hash`, canonical JSON, the bounds | 1 |
| `internal/intake/refusal.go` (new) | The closed refusal list, one sentence each, and `Refusal`'s error shape | 1 |
| `internal/intake/guards.go` (new) | The candidate set (allowlist ∩ asked ∩ may write), the public-only guard's order | 1 |
| `internal/intake/publicity.go` (new) | `Publicity` and its cache, as `repoaccess` caches | 1 |
| `internal/intake/model.go` (new) | The one bounded `chat/completions` call: pinned alias, strict decode, reply cap, deadline, usage | 1 |
| `internal/intake/compose.go` (new) | Roles and budget from config; the reply becomes a `Plan` or a refusal | 1 |
| `internal/intake/composer.go` (new) | The degraded deterministic composer, labelled, off by default | 1 |
| `internal/intake/prompt.go` (new) | The system prompt and the reply shape the model is asked for | 1 |
| `internal/config/config.go` | `human.intake.plan` and its validation | 2 |
| `internal/humanapi/intake.go` (new) | `intake_plan` and `plan_check`; the daily limiter; the audit line; the metrics | 2 |
| `internal/humanapi/mcp.go` | The two tools on the tool table and the sponsored list | 2 |
| `internal/humanapi/server.go` | `Intake *Intake` | 2 |
| `internal/humanapi/sponsored_test.go` | The two closed lists, amended deliberately | 2 |
| `internal/metrics/metrics.go`, `internal/metrics/metrics_test.go` | `intake_plan_total`, `intake_plan_seconds`, `intake_plan_tokens`, and `MakuName`'s `intake_` case | 2 |
| `internal/app/broker.go`, `internal/app/mcp.go`, `internal/app/access.go` | Wire `human.intake.plan` into the server, beside `roomAccess` | 2 |
| `internal/github/app.go` | `Repository(ctx, owner, repo)`, the visibility read | 2 |
| `internal/mcpwire/mcpwire.go` | `IntakePlan`, `PlanCheck` names, so the relay and the broker cannot drift | 2, 3 |
| `internal/maku/issuefile.go`, `internal/maku/localtools.go` | `issue_file` takes the plan and its hash, re-checks through `plan_check`, shows the ceiling | 3 |
| `internal/humanapi/mcpprompts.go` | `handoff` calls `intake_plan`; `plan` stops being the model's work | 3 |
| `internal/maku/skill/factory-handoff/SKILL.md`, `commands/factory.md` | The skill's rewrite: pass context, never compose the plan | 3 |
| `internal/humanapi/runcreate.go` | `plan` and `plan_hash` on `run_create`, and the four checks they carry | 4 |
| `docs/api.md`, `docs/cli.md`, `docs/slack.md` | The tools, the switch, the refusals | 2, 3, 4 |
| ai-native-ref `website/content/docs/use/guide/terminal-and-coding-agent.md`, `reference/commands.md`, `how-it-works/gateways.md`, `docs/runbooks/agent-factory/19-factory-from-your-agent.md` | The reader's side and the operator procedure | A |
| ai-native-ref `infrastructure/base/room-broker/externalsecret-planner.yaml` (new) | The broker's copy of the `planner` key | A |
| ai-native-ref `infrastructure/base/envoy-ai-gateway/externalsecret-planner-key.yaml` (new), `security-policy.yaml` | The gateway's copy, whose rendered Secret key must be `planner`, and the `credentialRefs` entry that makes it a client id | A |
| ai-native-ref `infrastructure/base/room-broker/network-policy.yaml`, `infrastructure/base/envoy-gateway/network-policy.yaml` | The two CNP halves of one connection | A |
| ai-native-ref `infrastructure/base/room-broker/app.yaml`, `config.yaml`, `infrastructure/{gcp-0,aws-0}/room-broker/config.yaml` | The mount; the three config copies; the broker image pin | A, B |
| ai-native-ref `scripts/ci/tests/test-intake-plan-wiring.py` (new), `test-room-broker-intake-classes.py` (new), `test-room-broker-suspend.py` (amended) | The pairing gate, the class-table gate, and the config-difference rule the new block touches | A |
| ai-native-ref `observability/base/agent-platform/grafana-dashboard-agent-room.yaml` | Two planner panels | A |
| ai-native-ref `website/content/docs/decisions/0060-conversational-intake.md` (new), `docs/runbooks/agent-factory/results-intake.md` (new) | The record and the proof | B |

---

## PR 1 — `feat/intake-core`: the plan, its hash, its guards, its one call

CD2, CD3 (the existing validator), CD14, CD17, CD18, CD27. Nothing here is reachable from a route yet.

### Task 1: `plan/v1`, the material set and the canonical hash

**Files:**
- Create: `internal/intake/plan.go`, `internal/intake/plan_test.go`, `internal/intake/testdata/plan/*.json`
- Test: `internal/intake/plan_test.go`, `internal/intake/testdata/plan/` goldens

**Interfaces:**
- Produces: `const APIVersion = "plan/v1"`; `type Surface string` with `SurfaceSlack`, `SurfaceSession`;
  `type Plan struct{ APIVersion string; Rev int; Planner Planner; Repository string; RepositoryEvidence []Evidence; Alternatives []Alternative; Issues []Issue; Budget Budget; Question *Question; Hash string }`;
  `type Planner struct{ Model, Surface string; At time.Time }`;
  `type Evidence struct{ Kind, Text, URL string }`; `type Alternative struct{ Repository, Why string }`;
  `type Issue struct{ Index int; Title, Body, Class string; Roles []string; DependsOn []int }`;
  `type Budget struct{ CeilingUSD float64; Source string }`; `type Question struct{ Text string; Recommended Answer }`; `type Answer struct{ Answer, Why string }`;
  `func Hash(p Plan) string` (`"sha256:<hex>"`); `func Material(p Plan) ([]byte, error)`; `func (p Plan) JSON() ([]byte, error)` (compact, for `structuredContent`);
  `func Check(p Plan, candidates []string, classes map[string]Class) *Refusal` — `nil` when the plan holds. `Class` is also declared here (Task 3's `Compose` is its other consumer): `type Class struct{ Roles []string; CeilingUSD float64; Source string }`.

- [ ] **Step 1: Write the goldens and the failing tests**

`internal/intake/testdata/plan/single.json` is the spec's example, normalised: one issue, `rev: 1`, `question: null`, `budget: {"ceilingUSD": 2.0, "source": "class:docs-links.taskUSD"}` — the **displayed** value, since `CeilingUSD` is what a person reads — and **no** `hash` key: the broker computes it, so a fixture never carries one (`Hash` ignores a `Hash` field anyway, and a fixture with a hash would invite a test that trusts it). Add `three.json` (three issues, `dependsOn: [1, 2]` at indices 2 and 3).

```go
// CD27: the hash covers every material field and nothing else. A display-only change keeps it.
func TestPlanHashCoversTheMaterialSetOnly(t *testing.T) {
	base := planFixture(t, "single")
	m := intake.Hash(base)
	for name, change := range map[string]func(*intake.Plan){
		"apiVersion":  func(p *intake.Plan) { p.APIVersion = "plan/v2" },
		"repository":  func(p *intake.Plan) { p.Repository = "owner/other" },
		"ceiling":     func(p *intake.Plan) { p.Budget.CeilingUSD = 2.5 },
		"budget src":  func(p *intake.Plan) { p.Budget.Source = "channel:C1.maxCostUSD" },
		"index":       func(p *intake.Plan) { p.Issues[0].Index = 2 },
		"title":       func(p *intake.Plan) { p.Issues[0].Title = "docs: another" },
		"body":        func(p *intake.Plan) { p.Issues[0].Body += "\n" },
		"acceptance":  func(p *intake.Plan) { p.Issues[0].Body = strings.Replace(p.Issues[0].Body, "## Acceptance check", "## Acceptance check\n- one", 1) },
		"class":       func(p *intake.Plan) { p.Issues[0].Class = "docs" },
		"roles":       func(p *intake.Plan) { p.Issues[0].Roles = []string{"implementer", "reviewer"} },
		"dependsOn":   func(p *intake.Plan) { p.Issues[0].DependsOn = []int{1} },
	} {
		p := base
		p.Issues = slices.Clone(base.Issues)
		change(&p)
		if intake.Hash(p) == m {
			t.Errorf("%s: the hash did not move", name)
		}
	}
	// Display, and only display: a promise about what will be filed is unaffected.
	for name, change := range map[string]func(*intake.Plan){
		"evidence":    func(p *intake.Plan) { p.RepositoryEvidence = append(p.RepositoryEvidence, intake.Evidence{Kind: "path", Text: "a.md"}) },
		"alternative": func(p *intake.Plan) { p.Alternatives = []intake.Alternative{{Repository: "o/d", Why: "also serves"}} },
		"rev":         func(p *intake.Plan) { p.Rev = 3 },
		"question":    func(p *intake.Plan) { p.Question = &intake.Question{Text: "which?", Recommended: intake.Answer{Answer: "a", Why: "b"}} },
		"planner at":  func(p *intake.Plan) { p.Planner.At = time.Date(2026, 11, 5, 9, 0, 0, 0, time.UTC) },
		"hash field":  func(p *intake.Plan) { p.Hash = "sha256:00" },
	} {
		p := base
		p.Issues = slices.Clone(base.Issues)
		change(&p)
		if intake.Hash(p) != m {
			t.Errorf("%s: the hash moved on a field the design does not hash", name)
		}
	}
}

// The canonical bytes are stable, and the ceiling is an integer: 2000000 micro-dollars for $2.00,
// never `2.0000000000000004` or `2` — the deliberate deviation from the spec's `ceilingUSD`.
func TestPlanHashIsStable(t *testing.T) {
	p := planFixture(t, "three")
	for i := 0; i < 5; i++ {
		if intake.Hash(p) != intake.Hash(planFixture(t, "three")) {
			t.Fatal("unstable")
		}
	}
	m, _ := intake.Material(p)
	want := `{"apiVersion":"plan/v1","repository":"Smana/ai-native-ref","budget":{"ceilingMicroUSD":2000000,"source":"class:docs-links.taskUSD"},"issues":[{"index":1,`
	if !strings.HasPrefix(string(m), want) {
		t.Fatalf("%s", m)
	}
	if !strings.Contains(string(m), `"roles":[`) || strings.Index(string(m), `"dependsOn"`) < strings.Index(string(m), `"roles"`) {
		t.Fatalf("field order: %s", m)
	}
}

// Review Focus 1: a repository outside the candidate set is refused whole, and the outsider is
// never named in the refusal.
func TestPlanRefusesARepositoryOutsideTheCandidates(t *testing.T) {
	p := planFixture(t, "single")
	p.Repository = "owner/secret-repo"
	if r := intake.Check(p, []string{"Smana/ai-native-ref"}, classes()); r == nil || r.Reason != intake.ReasonRepositoryNotInCandidates {
		t.Fatalf("%+v", r)
	} else if strings.Contains(r.Sentence, "secret-repo") {
		t.Fatalf("the refusal names the outsider: %s", r.Sentence)
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd "$MAKU" && go test ./internal/intake/ -run 'TestPlanHash|TestPlanRefuses' -count=1`
Expected: FAIL at compile (`undefined: intake.Hash`, `intake.Check`, `intake.Material`, `intake.Plan`).

- [ ] **Step 3: Write the types, `Material` and `Hash`**

Field order is the contract, so the material set is its own struct and `encoding/json` emits it in declaration order:

```go
// material is CD27's hashed set, in its fixed order: the displayed set and the hashed set are the
// same set, or a field a person can read is a field they cannot confirm.
type material struct {
	APIVersion string          `json:"apiVersion"`
	Repository string          `json:"repository"`
	Budget     materialBudget  `json:"budget"`
	Issues     []materialIssue `json:"issues"`
}

// The ceiling is hashed in micro-dollars: two processes formatting a float64 the same way is a
// promise Go makes and JSON does not, and a cent is the smallest amount that can be filed. The
// plan displays ceilingUSD; this field is the integer the hash covers (CD27).
type materialBudget struct {
	CeilingMicroUSD int64  `json:"ceilingMicroUSD"`
	Source          string `json:"source"`
}
```

`Hash` is `"sha256:" + hex(sha256(Material(p)))`. `CeilingUSD` → micro-dollars is `math.Round(v*1e6)` as `int64`, so `2.00` is `2000000` in the canonical bytes and in the golden.

- [ ] **Step 4: Write `Check` and every refusal sentence**

`internal/intake/refusal.go` holds the closed list as constants and a `sentence(reason)` table; `Refusal` implements `error` so `humanapi`'s `refusal()` (`mcp.go:339`) can find it, and it is a `toolError`-shaped answer for the model. `Check(p Plan, candidates []string, classes map[string]Class) *Refusal` applies, in order: `apiVersion`; 1–3 issues; each title/body through `sanitize.CheckDraft` (`invalid_draft: …` verbatim); repository ∈ candidates (never echoing it); class ∈ `classes`; evidence ≤ 5 × 280 runes; one question at most. Diagnostics name the field and the bound.

- [ ] **Step 5: Run the package**

Run: `go test ./internal/intake/ -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/intake
git commit -m "feat(intake): plan/v1 and the canonical hash over its material set"
```

### Task 2: the guards — the candidate set, write access, public only

**Files:**
- Create: `internal/intake/guards.go`, `internal/intake/publicity.go`, `internal/intake/guards_test.go`, `internal/intake/publicity_test.go`
- Test: `internal/intake/guards_test.go` (Review Focus 2)

**Interfaces:**
- Produces: `type Publicity interface{ Public(ctx context.Context, repository string) (bool, error) }`;
  `func NewPublicity(lookup Lookup, ttl time.Duration, now func() time.Time) *CachedPublicity` with `type Lookup func(ctx context.Context, repository string) (bool, error)`;
  `type Guard struct{ Allow map[string]bool; MayWrite func(ctx context.Context, repository string) (bool, error); Public Publicity }`;
  `func (g Guard) Candidates(ctx context.Context, asked []string) ([]string, *Refusal)` — lowercased, de-duplicated, allowlist order, at most 20;
  `type Requester struct{ Key, Login string }` — the effective requester, resolved once by the API (PR 2) and threaded here so the guard never re-derives who is asking.

- [ ] **Step 1: Write the failing tests**

`pubOf(map[string]bool)` is a helper **defined in `guards_test.go`** (it is a test double, not a production type): a repository in the map is public, one absent is private, and a `nil` map answers an error for every repository.

```go
// Review Focus 2: a candidate GitHub reports private, or cannot answer for, never reaches the
// model, and a private one is not named back as an alternative.
func TestPrivateOrUnverifiableRepositoriesNeverReachTheModel(t *testing.T) {
	g := intake.Guard{Allow: map[string]bool{"smana/ai-native-ref": true, "smana/private": true},
		MayWrite: func(context.Context, string) (bool, error) { return true, nil },
		Public: pubOf(map[string]bool{"Smana/ai-native-ref": true, "Smana/private": false})}
	got, r := g.Candidates(t.Context(), []string{"Smana/private", "Smana/ai-native-ref"})
	if r != nil || !slices.Equal(got, []string{"Smana/ai-native-ref"}) {
		t.Fatalf("%v %+v", got, r)
	}
	// Named explicitly and private: refused with the reason and the two ways forward.
	if _, r := g.Candidates(t.Context(), []string{"Smana/private"}); r == nil || r.Reason != intake.ReasonPrivateRepository ||
		!strings.Contains(r.Sentence, "issue_draft") {
		t.Fatalf("%+v", r)
	}
	// GitHub cannot answer: refused, never planned on a guess.
	g.Public = pubOf(nil) // every lookup errors
	if _, r := g.Candidates(t.Context(), []string{"Smana/ai-native-ref"}); r == nil || r.Reason != intake.ReasonRepositoryUnverified {
		t.Fatalf("%+v", r)
	}
}

// CD5: the candidate set is the allowlist ∩ what the requester may write; a repository outside
// either is not a candidate and is not named back.
func TestCandidatesAreTheAllowlistIntersectedWithWrite(t *testing.T) {
	g := intake.Guard{Allow: map[string]bool{"a/one": true, "a/two": true},
		MayWrite: func(_ context.Context, repo string) (bool, error) { return repo == "a/two", nil },
		Public:   pubOf(map[string]bool{"a/one": true, "a/two": true})}
	if got, _ := g.Candidates(t.Context(), []string{"a/one", "a/two", "z/outsider"}); !slices.Equal(got, []string{"a/two"}) {
		t.Fatalf("%v", got)
	}
	if _, r := g.Candidates(t.Context(), []string{"a/one"}); r == nil || r.Reason != intake.ReasonNoWrite {
		t.Fatalf("%+v", r)
	}
}

// The cache is the repoaccess one: one lookup per repository per TTL, and a failure is never cached.
func TestPublicityCachesForTTL(t *testing.T) { /* count lookups across two reads inside and outside the TTL */ }
```

`pubOf(map[string]bool)` is defined in this file (above). It is a test double: a repository in the map is public, one absent is private, and a `nil` map answers an error for every repository.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/intake/ -run 'TestPrivateOrUnverifiable|TestCandidatesAre' -count=1`
Expected: FAIL at compile (`undefined: intake.Guard`, `intake.Publicity`, `intake.ReasonPrivateRepository`).

- [ ] **Step 3: Implement the guard and the cache**

Order inside `Candidates`, and it is the security order: allowlist → asked → write access → public. A repository failing the *write* check for a single-repository request is `no_write`; failing the *allow* check is `repository_not_allowed` (one sentence lists the repositories the caller may write in, never one they may not). A **single explicitly asked** private repository is `private_repository_unsupported`; in a multi-repository ask a private candidate is **dropped silently** (see [Global Constraints](#global-constraints): naming it back would confirm a repository the requester did not name). An error from `MayWrite` or `Public` fails closed with `repository_unverified`. `CachedPublicity` mirrors `repoaccess.Checker`: a mutex, a TTL, a bounded map, an error never cached.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/intake/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/intake
git commit -m "feat(intake): the candidate set, its write check, and the public-only guard"
```

### Task 3: the one bounded model call

**Files:**
- Create: `internal/intake/model.go`, `internal/intake/prompt.go`, `internal/intake/model_test.go`, `internal/intake/compose.go`, `internal/intake/compose_test.go`
- Test: `internal/intake/model_test.go` (a fake `/v1/chat/completions` endpoint, counting calls), `internal/intake/compose_test.go`

**Interfaces:**
- Consumes: `Plan` (Task 1), `Refusal` (Task 1), `Guard` (Task 2).
- Produces: `type Model struct{ URL, APIKeyFile, Alias string; HC *http.Client; Deadline time.Duration }`;
  `func (m *Model) Draft(ctx context.Context, req DraftRequest) (Draft, Usage, error)` with `errPlannerInvalid`/`errPlannerUnavailable` (`intake.ErrInvalid`, `intake.ErrUnavailable`, `intake.ErrTimeout` as sentinels);
  `type DraftRequest struct{ Text, Context string; Candidates []string }`;
  `type Draft struct{ Repository string; Evidence []Evidence; Alternatives []Alternative; Issues []DraftIssue; Question *DraftQuestion }`;
  `type DraftIssue struct{ Title, Body, Class string; DependsOn []int; Roles []string; BudgetUSD float64 }` (the last two exist only so a reply that names them can be dropped and logged — they are never read for a plan);
  `type Usage struct{ PromptTokens, CompletionTokens int }`;
  `func Compose(d Draft, in ComposeIn) (Plan, error)` with `type ComposeIn struct{ Surface Surface; Model string; Now time.Time; Rev int; Classes map[string]Class; CeilingUSD float64; CeilingSource string }`; `Class` is PR 1 Task 1's (three fields, no methods).

- [ ] **Step 0: The test helpers, named once**

Every helper below is **defined in this package's tests**, not in production code; a step that uses one names it here so no step refers to a function nobody wrote:

| Helper | Defined in | What it is |
|---|---|---|
| `okReply` | `model_test.go` | A valid JSON reply body (one issue, one repository, no question) |
| `fakeGateway(t, body, opts...) *fake` | `model_test.go` | An `httptest.Server` serving `POST /v1/chat/completions`; counts `calls`, records `header(name)`, `body()` (decoded map), `rawBody()`; `slow(d)` delays the answer |
| `modelFor(f *fake) intake.Model` | `model_test.go` | The `intake.Model` over `f`, key `k-planner`, alias `tier-frontier`, `HC: httpx.New(3s, nil)`, `Deadline` **250 ms** |
| `req() intake.DraftRequest` | `model_test.go` | One text, one candidate |
| `replyWithIssueBody(n int) []byte` | `model_test.go` | A reply whose issue body is `n` bytes, the JSON as a whole padded to the 64 KiB bound |
| `slow(d)` | `model_test.go` | The `fakeGateway` option that makes the answer late |
| `validBody` | `compose_test.go` | A body holding `CheckDraft`'s three headings, in order |
| `planFixture(t, name) intake.Plan` | `plan_test.go` (shared by the package) | Decodes `testdata/plan/<name>.json`; `plan_test.go` is the only file with the relative path |
| `classes()` | `plan_test.go` | The one-row class table (`docs-links`: `scoper, implementer, reviewer`, $2.00) |

`Deadline` is **250 ms** on purpose: `TestADeadlineOverCallIsPlannerTimeout` then asserts the call ends in well under 2 s with the endpoint still sleeping for 5 s, which is a real assertion rather than a race against a 20 s bound.

- [ ] **Step 1: Write the failing tests**

```go
// CD18: one call, one alias, one header, one shape. The fake records what it was sent.
func TestTheModelCallIsTheGovernedOne(t *testing.T) {
	f := fakeGateway(t, okReply)
	m := modelFor(f)
	if _, _, err := m.Draft(t.Context(), intake.DraftRequest{Text: "the install link is dead", Candidates: []string{"Smana/ai-native-ref"}}); err != nil {
		t.Fatal(err)
	}
	if got := f.header("Authorization"); got != "Bearer k-planner" {
		t.Fatalf("the only header sent: %q", got)
	}
	if body := f.body(); body["model"] != "tier-frontier" || body["temperature"] != float64(0) || body["max_tokens"] != float64(4000) {
		t.Fatalf("%v", body)
	}
	if strings.Contains(f.rawBody(), "k-planner") || strings.Contains(f.rawBody(), "provider") {
		t.Fatal("the key or a provider hint reached the body")
	}
}

// Review Focus 4: the reply at the bound decodes; one byte over is planner_invalid, never truncated.
func TestAReplyAtTheBoundIsAcceptedAndOneByteOverIsRefused(t *testing.T) {
	body := replyWithIssueBody(16<<10 - 1) // a legal 16 KiB issue body, the whole reply at 64 KiB
	if _, _, err := modelFor(fakeGateway(t, body)).Draft(t.Context(), req()); err != nil {
		t.Fatalf("at the bound: %v", err)
	}
	f := fakeGateway(t, append(body, ' ')) // one byte past the reply bound
	_, _, err := modelFor(f).Draft(t.Context(), req())
	if !errors.Is(err, intake.ErrInvalid) || !strings.Contains(err.Error(), "64 KiB") {
		t.Fatalf("%v", err)
	}
	if f.calls != 1 {
		t.Fatalf("a retry loop: %d calls", f.calls)
	}
}

// Review Focus 5: the deadline, not the client's patience, ends the call — the endpoint sleeps 5 s,
// the model's own deadline is 250 ms, and the call returns well inside 2 s.
func TestADeadlineOverCallIsPlannerTimeout(t *testing.T) {
	f := fakeGateway(t, okReply, slow(5*time.Second))
	start := time.Now()
	_, _, err := modelFor(f).Draft(t.Context(), req())
	if !errors.Is(err, intake.ErrTimeout) || time.Since(start) > 2*time.Second {
		t.Fatalf("%v after %s", err, time.Since(start))
	}
}

// planner_invalid: a reply that is not the shape, a reply with unknown fields, a reply with zero
// issues, a reply with four. Each is refused whole, with the attempt counted by the caller.
func TestAnUndecodableReplyIsPlannerInvalid(t *testing.T) { /* four subtests over fakeGateway bodies */ }
```

`internal/intake/compose_test.go` (Review Focus 3):

```go
// Review Focus 3: the reply cannot name its own roles or budget. A reply that does is dropped and
// logged, and the config's values are the plan's — and in its hash.
func TestRolesAndBudgetComeFromConfigOnly(t *testing.T) {
	table := classes()
	in := intake.ComposeIn{Surface: intake.SurfaceSession, Model: "tier-frontier",
		Now: time.Date(2026, 11, 5, 9, 0, 0, 0, time.UTC), Classes: table}
	d := intake.Draft{Repository: "Smana/ai-native-ref",
		Issues: []intake.DraftIssue{{Title: "docs: x is wrong", Body: validBody, Class: "docs-links",
			Roles: []string{"admin"}, BudgetUSD: 99}}}
	p, err := intake.Compose(d, in)
	if err != nil {
		t.Fatal(err)
	}
	if !slices.Equal(p.Issues[0].Roles, []string{"scoper", "implementer", "reviewer"}) || p.Budget.CeilingUSD != 2 {
		t.Fatalf("%+v %+v", p.Issues[0], p.Budget)
	}
	// The dropped values are not in the hash either: a $99 ceiling in the reply changes nothing.
	other := d
	other.Issues = []intake.DraftIssue{{Title: d.Issues[0].Title, Body: validBody, Class: "docs-links",
		Roles: []string{"reviewer", "admin"}, BudgetUSD: 99}}
	q, err := intake.Compose(other, in)
	if err != nil || intake.Hash(q) != intake.Hash(p) {
		t.Fatalf("a model value reached the hash: %v", err)
	}
	// And a class the config does not define is refused, not guessed.
	d.Issues[0].Class = "admin"
	if _, err := intake.Compose(d, in); err == nil || !strings.Contains(err.Error(), intake.ReasonInvalidClass) {
		t.Fatalf("%v", err)
	}
}

// The channel's ceiling binds when it is below the class's, and the source says which one won.
func TestTheChannelCeilingBindsBelowTheClassCeiling(t *testing.T) { /* ComposeIn{CeilingUSD: 1.5, CeilingSource: "channel:C1.maxCostUSD"} -> $1.50, and Source says the channel */ }
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/intake/ -run 'TestTheModelCall|TestAReplyAtTheBound|TestADeadlineOver|TestAnUndecodable|TestRolesAndBudget' -count=1`
Expected: FAIL at compile (`undefined: intake.Model`, `intake.Compose`, `intake.ComposeIn`).

- [ ] **Step 3: Implement the client**

One `POST <url>/chat/completions`, `Content-Type: application/json`, `Authorization: Bearer <key read from APIKeyFile at use>`, body `{"model": Alias, "temperature": 0, "max_tokens": 4000, "response_format": {"type": "json_object"}, "messages": [system, user]}`, `context.WithTimeout(Deadline)`, `httpx.ReadBody(resp.Body, 64<<10)`, then `json.NewDecoder(...).DisallowUnknownFields()` into `Draft`. No redirect following beyond `httpx`'s cap, no retry, no fallback inside the client: the caller maps `context.DeadlineExceeded` to `ErrTimeout`, a transport or non-200 to `ErrUnavailable`, a decode or bound failure to `ErrInvalid` with the field named. `usage` is returned as `Usage`; a reply without `usage` is `ErrInvalid` (a cost the broker cannot attribute is a cost it may not spend).

`prompt.go` holds the system prompt (the reply shape, "one defect per issue", "at most three", "evidence ≤ 5, ≤ 280 characters each", "never invent a repository outside the list given") and the user message built from `Text`, `Context` and `Candidates`, each truncated by refusal, never silently: an over-bound `Text` refuses the call with its bound.

- [ ] **Step 4: `Compose` — the config wins**

`Compose` maps a `Draft` to a `Plan`: `index = position+1`; `dependsOn` kept only when every value is `1..index-1`; `class` from the draft, checked against `ComposeIn.Classes`; `roles` and `ceilingUSD` **from `Classes[class]`**, from `ComposeIn.CeilingUSD`/`CeilingSource` when that is lower (the channel's `maxCostUSD`); `planner` = `{in.Model, string(in.Surface), in.Now}`; `rev` = `in.Rev`; `hash` from `Hash`. Every field the draft carries that config owns is dropped, and the caller logs one line naming it.

- [ ] **Step 5: Run the package**

Run: `go test ./internal/intake/ -count=1 && task lint`
Expected: PASS, 0 issues.

- [ ] **Step 6: Commit**

```bash
git add internal/intake
git commit -m "feat(intake): one bounded model call, and the plan it composes"
```

### Task 4: the degraded composer, and PR 1

**Files:**
- Create: `internal/intake/composer.go`, `internal/intake/composer_test.go`
- Test: `internal/intake/composer_test.go`

**Interfaces:**
- Produces: `func ComposeTemplate(text, context string, candidates []string, classes map[string]Class) (Plan, *Refusal)` — `Plan.Planner.Model == "composer"` and `Plan.Question == nil`; it never calls a model and never guesses a repository (one candidate, or a refusal).

- [ ] **Step 1: Write the failing test**

```go
// CD18: the composer is a template and says so. It is never a candidate for the live proof, and
// it never invents a repository.
func TestTheTemplateComposerIsLabelledAndGuessesNothing(t *testing.T) {
	p, r := intake.ComposeTemplate("the install link is dead", "", []string{"Smana/ai-native-ref"},
		map[string]intake.Class{"docs-links": {CeilingUSD: 2, Source: "class:docs-links.taskUSD", Roles: []string{"implementer"}}})
	if r != nil || p.Planner.Model != "composer" || p.Repository != "Smana/ai-native-ref" {
		t.Fatalf("%+v %+v", p, r)
	}
	if !strings.HasPrefix(p.Issues[0].Title, "factory:") || p.Question != nil {
		t.Fatalf("%+v", p.Issues[0])
	}
	if _, r := intake.ComposeTemplate("x", "", []string{"a/one", "a/two"}, nil); r == nil || r.Reason != intake.ReasonRepositoryNotAllowed {
		t.Fatalf("%+v", r)
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/intake/ -run TestTheTemplateComposer -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: Implement it**

One issue, the three sections in the template's order, `Class` the alphabetically first configured class, `Roles`/`Budget` from `Classes` exactly as `Compose` does (so the two paths cannot disagree about money). It is reachable only through `human.intake.plan.fallback: composer` (PR 2).

- [ ] **Step 4: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/intake-core
gh pr create --title "feat(intake): plan/v1, its canonical hash, its guards and one bounded model call" \
  --body "CD3, CD14, CD17, CD18, CD27; offline proofs 1–3 and 15's models half. No route reaches any of it yet. Evidence: task check exit 0, task lint 0."
```

---

## PR 2 — `feat/intake-tools`: `intake_plan` and `plan_check` on `/mcp`

CD18's surface, CD5's allowlist, the daily cap, the audit line and the metrics.

### Task 1: `human.intake.plan` in the broker's config

**Files:**
- Modify: `internal/config/config.go` (`HumanConfig`, `IntakeConfig`, `validate`)
- Modify: `internal/config/config_test.go`
- Test: `internal/config/config_test.go`

**Interfaces:**
- Produces: `type IntakeConfig struct{ Plan PlanConfig }` with
  `type PlanConfig struct{ Enabled bool; URL string; Model string; APIKeyFile string; Deadline Duration; DailyPlans int; Fallback string; Repositories []string; Classes map[string]PlanClass }`;
  `type PlanClass struct{ Roles []string; CeilingUSD float64; Source string }`;
  `func (c Config) IntakePlan() PlanConfig` returning the defaults (`Model: "tier-frontier"`, `Deadline: 20s`, `DailyPlans: 50`, `Fallback: "off"`).

- [ ] **Step 1: Write the failing test**

`config.Load` takes a **path** (`config.go:331`, `os.ReadFile` + `yaml.UnmarshalStrict`), so the test uses the package's existing `write(t, body)` helper (`config_test.go:31`) and YAML bodies appended to the file's `valid` config.

```go
// The keys land with the code that reads them, and a bad one fails the rollout, not the first call.
func TestIntakePlanConfig(t *testing.T) {
	intake := func(plan string) string {
		return valid + "\n  intake:\n    plan:\n" + plan // appended under human:
	}
	for name, body := range map[string]string{
		"a model, not the alias":    intake("      enabled: true\n      model: glm-5.3\n      url: http://gw/v1\n      apiKeyFile: /k\n"),
		"a deadline over the bound": intake("      enabled: true\n      model: tier-frontier\n      url: http://gw/v1\n      apiKeyFile: /k\n      deadline: 30s\n"),
		"a third fallback":          intake("      fallback: template\n"),
		"a duplicated key":          intake("      enabled: true\n      enabled: false\n"),
		"a role the factory lacks":  intake("      classes:\n        docs-links:\n          roles: [admin]\n          ceilingUSD: 2\n          source: class:docs-links.taskUSD\n"),
		"a repository that is not":  intake("      repositories: [not-a-repo]\n"),
		"enabled with no key file":  intake("      enabled: true\n      url: http://gw/v1\n      model: tier-frontier\n"),
	} {
		if _, err := Load(write(t, body)); err == nil {
			t.Errorf("%s: accepted", name)
		}
	}
	cfg, err := Load(write(t, valid+"\n  intake:\n    plan:\n"+
		"      enabled: true\n      url: http://ai-gateway.envoy-gateway-system.svc.cluster.local:8080/v1\n"+
		"      apiKeyFile: /etc/room-broker/planner/api-key\n      repositories: [Smana/ai-native-ref]\n"+
		"      classes:\n        docs-links: {roles: [scoper, implementer, reviewer], ceilingUSD: 2, source: class:docs-links.taskUSD}\n"))
	if err != nil {
		t.Fatal(err)
	}
	p := cfg.IntakePlan()
	if p.Model != "tier-frontier" || p.Deadline.Duration != 20*time.Second || p.DailyPlans != 50 || p.Fallback != "off" {
		t.Fatalf("%+v", p)
	}
	// Disabled, the keys may be absent entirely: `tier-frontier` is required only of a planner that runs.
	if _, err := Load(write(t, valid+"\n  intake:\n    plan:\n      enabled: false\n")); err != nil {
		t.Fatalf("disabled with no route: %v", err)
	}
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/config/ -run TestIntakePlanConfig -count=1`
Expected: FAIL at compile (`undefined: IntakeConfig`, `PlanConfig`) — and, once the struct exists, the disabled-with-no-route case must still load.

- [ ] **Step 3: Implement the struct, the defaults and the validation**

`Enabled` **when true** requires `URL`, `Model` and `APIKeyFile` (a planner with no key would 401 every plan) and `Model` must equal `tier-frontier` (the alias the gateway serves to this client — a different alias is a different, unreviewed spend). **Disabled, the route, model and key are validated only for shape if present** — `enabled: false` declares an intent, and ai-native-ref's three config copies must carry the block before a switch is flipped, so a disabled block may be a bare `enabled: false`. `Deadline` ≤ 20 s; `DailyPlans` ≥ 1; `Fallback` ∈ `{"", "off", "composer"}`; `Repositories` match `repositoryRE`; each `PlanClass.Roles` is a non-empty subset of `{"scoper","tester","implementer","reviewer","triager"}` with no duplicates, and `CeilingUSD` > 0 with a non-empty `Source`.

- [ ] **Step 4: Run the package, then commit**

Run: `go test ./internal/config/ -count=1`
Expected: PASS, and the existing strict-decode tests still refuse unknown keys.

```bash
git add internal/config
git commit -m "feat(config): human.intake.plan, and the defaults a planner needs"
```

### Task 2: the `intake_plan` tool

**Files:**
- Create: `internal/humanapi/intake.go`, `internal/humanapi/intake_test.go`
- Modify: `internal/humanapi/server.go` (`Intake *Intake`), `internal/humanapi/mcp.go` (the tool table and the sponsored list), `internal/humanapi/sponsored_test.go`, `internal/mcpwire/mcpwire.go` (`IntakePlan`, `PlanCheck`), `internal/app/broker.go` (wiring), `internal/app/mcp.go`
- Test: `internal/humanapi/intake_test.go`, `internal/humanapi/sponsored_test.go`, `internal/humanapi/mcpschema_test.go`

**Interfaces:**
- Consumes: `intake.Compose`, `intake.Guard`, `intake.Model`, `intake.ComposeTemplate` (PR 1); `s.canStart` (`issuedraft.go:57`); `s.Identity`, `s.Access` (`server.go:142`).
- Produces: `type Intake struct{ Classes map[string]intake.Class; Allow map[string]bool; Model *intake.Model; Public intake.Publicity; Daily int; Fallback string; Now func() time.Time; limits *dailyLimits }` — no channel ceiling here: the App passes its channel's `maxCostUSD` as the `ceiling` argument (it already passes `max_cost` to `run_create`, `slackapp/broker.go:110`), and the broker takes the lower of it and the class's;
  the tool `intake_plan`, schema `{"type":"object","additionalProperties":false,"required":["text"],"properties":{"text":{"type":"string","minLength":1,"maxLength":16384},"repository":{"type":"string","pattern":"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$"},"context":{"type":"string","maxLength":4096},"candidates":{"type":"array","maxItems":20,"items":{"type":"string","pattern":"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$"}},"evidence":{"type":"array","maxItems":5,"items":{"type":"string","maxLength":280}},"on_behalf_of":{"type":"string","pattern":"^slack:T[A-Z0-9]{2,20}/[UW][A-Z0-9]{2,20}$"},"ceiling":{"type":"number","exclusiveMinimum":0}}}`;
  its result `{text, data}` where `data` is `{plan, hash, question, canStart, canStartWhy, degraded}`;
  `func (s *Server) requester(ctx context.Context, p authn.Principal, a intakeArgs) (intake.Requester, *intake.Refusal)` — the one resolution of *who* and *which repositories* (steps 2–3 below), used by `intake_plan`, `plan_check` and `run_create`; with `type Requester struct{ Key, Login string }` in `internal/intake` (declared in PR 1 Task 2's Interfaces: `Key` is what the daily counter and the log line use, `Login` what every GitHub check uses);
  `func (in *Intake) take(requester string) bool` — the daily counter, keyed by the **effective requester**;
  `metrics.Set.IntakePlan(ctx, surface, outcome, reason string)`, `IntakePlanSeconds`, `IntakePlanTokens`.

**Test helpers** (all in `intake_test.go`, none in production): `withIntake(t, surface)` builds the server with a fake gateway and the `docs-links` class table; `withIntakeDaily(t, n)` the same with `Daily: n`; `withIntakeOnHour(t, at time.Time)` the same with `Intake.Now` fixed at `at`; `e.intake.calls()` counts the fake gateway's calls and `e.intake.advance(d)` moves that clock; `planArgs()` is the one-argument map the tool takes.

- [ ] **Step 1: Write the failing tests**

```go
// CD18: one boundary, two channels, one validator. A session plans; the plan's hash is the
// broker's; roles and ceiling are the config's.
func TestIntakePlanFromASession(t *testing.T) {
	e := setup(t, mcpOn, withIntake(t, "session"))  // a fake gateway: one repository, no question
	got := call(t, e, viaRoomctl("dev"), "intake_plan", map[string]any{"text": "the install link in the README is dead"})
	if got.isError {
		t.Fatalf("%s", got.text)
	}
	var d struct{ Plan intake.Plan; Hash string; Degraded bool }
	_ = json.Unmarshal([]byte(got.structured), &d)
	if d.Hash != intake.Hash(d.Plan) || d.Plan.Repository != "Smana/ai-native-ref" || d.Degraded {
		t.Fatalf("%+v", d)
	}
	if !slices.Equal(d.Plan.Issues[0].Roles, []string{"scoper", "implementer", "reviewer"}) || d.Plan.Budget.CeilingUSD != 2 {
		t.Fatalf("%+v", d.Plan.Issues[0])
	}
	// A session cannot claim a user or widen its ceiling: both are a sponsored principal's alone.
	for _, bad := range []map[string]any{{"text": "x", "ceiling": 99}, {"text": "x", "on_behalf_of": "slack:T1/U2"}} {
		if got := call(t, e, viaRoomctl("dev"), "intake_plan", bad); !got.isError || !strings.Contains(got.text, "invalid_arguments") {
			t.Errorf("%v: %s", bad, got.text)
		}
	}
}

// CD18: the App reaches the same planner with on_behalf_of; the effective requester is the linked
// login, and a Slack user with no link is refused before any call.
func TestIntakePlanFromSlackResolvesTheLinkedLogin(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP), withIntake(t, "slack"))
	got := call(t, e, bearer("slack-app"), "intake_plan", map[string]any{
		"text": "the install guide is wrong", "on_behalf_of": "slack:T1/U2",
		"candidates": []string{"Smana/ai-native-ref"}, "ceiling": 1.5})
	if got.isError || !strings.Contains(got.text, "$1.50") { // the channel's ceiling binds below the class's
		t.Fatalf("%s", got.text)
	}
	// A user the link tables do not know: not_linked, zero calls to the model.
	before := e.intake.calls()
	got = call(t, e, bearer("slack-app"), "intake_plan", map[string]any{"text": "x", "on_behalf_of": "slack:T1/U9"})
	if !got.isError || !strings.Contains(got.text, "not_linked") || e.intake.calls() != before {
		t.Fatalf("%s (%d calls)", got.text, e.intake.calls()-before)
	}
}

// Review Focus 5: the cap is exact at the boundary, and the refusal sends no request.
func TestDailyPlanCapRefusesWithoutACall(t *testing.T) {
	e := setup(t, mcpOn, withIntakeDaily(t, 2), withIntakeOnHour(t, time.Date(2026, 11, 5, 9, 0, 0, 0, time.UTC)))
	for i := 0; i < 2; i++ {
		if got := call(t, e, viaRoomctl("dev"), "intake_plan", planArgs()); got.isError {
			t.Fatalf("call %d: %s", i+1, got.text)
		}
	}
	if got := call(t, e, viaRoomctl("dev"), "intake_plan", planArgs()); !got.isError ||
		!strings.Contains(got.text, "daily_plans_reached") || e.intake.calls() != 2 {
		t.Fatalf("%s (%d)", got.text, e.intake.calls())
	}
	// The day rolls over at 00:00 UTC: the clock is the server's Now, so the test steps it.
	e.intake.advance(24 * time.Hour)
	if got := call(t, e, viaRoomctl("dev"), "intake_plan", planArgs()); got.isError {
		t.Fatalf("after midnight: %s", got.text)
	}
}

// D: the counter is the effective requester's, not the App's. Two linked Slack users each get
// their own cap; one person's plans never spend another person's allowance.
// (The helper links slack:T1/U2 and slack:T1/U3 to two logins that both write the repository, so
// the only thing separating them is the key the counter uses.)
func TestTheDailyCapIsPerRequesterNotPerApp(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP), withIntakeDaily(t, 1),
		withIntakeOnHour(t, time.Date(2026, 11, 5, 9, 0, 0, 0, time.UTC)))
	first := map[string]any{"text": "x", "on_behalf_of": "slack:T1/U2", "candidates": []string{"Smana/ai-native-ref"}}
	second := map[string]any{"text": "y", "on_behalf_of": "slack:T1/U3", "candidates": []string{"Smana/ai-native-ref"}}
	if got := call(t, e, bearer("slack-app"), "intake_plan", first); got.isError {
		t.Fatalf("U2: %s", got.text)
	}
	if got := call(t, e, bearer("slack-app"), "intake_plan", first); !got.isError || !strings.Contains(got.text, "daily_plans_reached") {
		t.Fatalf("U2 twice: %s", got.text)
	}
	if got := call(t, e, bearer("slack-app"), "intake_plan", second); got.isError {
		t.Fatalf("U3 spent U2's allowance: %s", got.text)
	}
}

// Off by default: with human.intake.plan.enabled false, neither tool exists, on either list.
func TestNoIntakeToolsWithoutTheSwitch(t *testing.T) {
	e := setup(t, mcpOn)
	for _, h := range []http.Header{viaRoomctl("dev"), bearer("slack-app")} {
		if got := toolNames(t, e, h); strings.Contains(got, "intake_plan") || strings.Contains(got, "plan_check") {
			t.Fatalf("%s", got)
		}
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run 'TestIntakePlan|TestDailyPlanCap|TestTheDailyCap|TestNoIntakeTools' -count=1`
Expected: FAIL (`unknown tool: intake_plan`).

- [ ] **Step 3: Implement the tool, in the guard's order**

In `intake.go`, `func (s *Server) intakePlanTool(ctx context.Context, p authn.Principal, args json.RawMessage) (any, error)`, and in this order — the order is the security property:

1. decode (closed schema); `on_behalf_of` and `ceiling` are refused (`invalid_arguments`) unless `p.Sponsored`, so a session cannot widen its own ceiling or claim a user.
2. the effective requester: for a human, `s.Identity.Login(ctx, p.Sub, repo)` per candidate repository; for a sponsored principal, `store.SlackLink(team, user)` → `sub` → `s.Identity.Login(ctx, sub, repo)`. No link is `not_linked`, no call. The result is an `intake.Requester{Key, Login string}`: `Key` is the **login** for a human and `slack:<team>/<user>` for a sponsored caller whose link resolved — never `p.ID`, which for the App is one string for everyone in the workspace.
3. `s.Intake.Guard` → the candidate set (PR 1, Task 2), with `MayWrite` = `Identity.Login` + `Access.CanWrite` (`access.go`), the same pair `canStart` uses. `requester(...)` is the one function steps 2 and 3 live in, so `plan_check` and `run_create` resolve the caller identically.
4. the daily limiter: `s.Intake.take(req.Key)` — the **effective requester** from step 2 (24 h UTC buckets, in memory per replica; the spec keeps the counter beside the per-human limiter). Keyed on `p.ID` every Slack user in a workspace would share one allowance.
5. the call: `Model.Draft`. On error: `planner_timeout`, `planner_invalid`, `planner_unavailable` — each one sentence, and each counted.
6. `Compose`, then `Check` against the candidate set and the class table.
7. metrics (`surface`, `outcome` ∈ `planned|asked|refused|degraded`, `reason`), the tokens from `usage`, the duration, and **one** log line: requester, surface, repository, hash, model, tokens, outcome, duration — never the text.
8. the result: `{text: planText, data: {plan, hash, question, canStart, canStartWhy, degraded}}`, where `planText` is rendered by `internal/roomview` (the one escaper, so a model's title cannot become a heading or a link).

`canStart` is `s.canStart(ctx, p, plan.Repository)` for a human (unchanged, `issuedraft.go:57`) and `false, startSponsored` for the App, where `startSponsored = "sponsored"` joins `issuedraft.go`'s reason constants (`startOff`, `startNotLinked`, `startNoWrite`, `startUnverified`) so the App's answer is a named reason like the others and no caller invents a string.

- [ ] **Step 4: The two tool lists, amended deliberately**

`sponsoredTools` becomes `{"issue_draft", "room_summary", "room_tail", mcpwire.RoomChanges, mcpwire.IntakePlan}`. `sponsored_test.go:80` (`TestSponsoredToolList`) holds **two** name strings and both are amended in this PR: the sponsored one becomes `"run_create,issue_draft,room_summary,room_tail,room_changes,intake_plan"` (five tools → six), the human one becomes `"rooms_list,room_summary,room_tail,room_changes,room_queue,room_fork,issue_draft,intake_plan,plan_check"`. Each new schema passes `TestEveryToolSchemaNodeNamesItsType`, and both tools are added only when `s.Intake != nil`, so the list a deployment sees is the list it has.

**Rebase note.** Those same two strings, `sponsoredTools` in `mcp.go`, `internal/humanapi/mcpprompts.go` and `internal/maku/skill/factory-handoff/SKILL.md` are also edited by the **attention-and-resume plan** (`needs_list` joins both lists; `inbox` becomes one call; the skill's tool table grows). Whichever lands second rebases, re-runs `go test ./internal/humanapi/ -run TestSponsoredToolList`, and reconciles the two lists rather than overwriting the other's row.

- [ ] **Step 5: Run the packages**

Run: `go test ./internal/humanapi/ ./internal/mcpwire/ -count=1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/humanapi internal/mcpwire
git commit -m "feat(humanapi): intake_plan on both tool lists, one guarded model call"
```

### Task 3: `plan_check` — the seam `issue_file` and `run_create` re-validate through

**Files:**
- Modify: `internal/humanapi/intake.go` (`planCheckTool`), `internal/humanapi/mcp.go` (the human list), `internal/metrics/metrics.go` (`MakuName`, the three instruments), `internal/metrics/metrics_test.go`
- Test: `internal/humanapi/intake_test.go`, `internal/metrics/metrics_test.go`

**Interfaces:**
- Produces: the tool `plan_check`, schema `{"type":"object","additionalProperties":false,"required":["plan","hash"],"properties":{"plan":{"type":"object"},"hash":{"type":"string","pattern":"^sha256:[0-9a-f]{64}$"}}}`; result `{text, data}` with `data` = `{plan, hash, canStart, canStartWhy}` or a `toolError` `plan_changed: the plan is not the one that was shown`;
  `metrics.MakuName`'s new case (an `intake_` family is served as `maku_intake_*`): `case strings.HasPrefix(name, "intake_"): return "maku_" + name`;
  the instruments `intake_plan_total{surface,outcome,reason}`, `intake_plan_seconds{surface,outcome}`, `intake_plan_tokens{surface,kind}` and the `Set` fields `IntakePlans`, `IntakePlanSeconds`, `IntakePlanTokens` with `Set.IntakePlan(ctx, surface, outcome, reason string)`.

- [ ] **Step 1: Write the failing tests**

`planFixture(t, name)` here is `internal/humanapi`'s own test helper in `intake_test.go` — it decodes `../../internal/intake/testdata/plan/<name>.json` through `encoding/json` into an `intake.Plan` (the one explicit relative path in the package's tests), so the human API's tests and the plan package's goldens cannot drift.

```go
// Offline proof 4, first half: a plan changed after the render is refused; an unchanged one is
// accepted and re-validated with the same validator.
func TestPlanCheckRefusesAChangedPlan(t *testing.T) {
	e := setup(t, mcpOn, withIntake(t, "session"))
	shown := planFixture(t, "single")
	if got := call(t, e, viaRoomctl("dev"), "plan_check", map[string]any{"plan": shown, "hash": intake.Hash(shown)}); got.isError {
		t.Fatalf("%s", got.text)
	}
	changed := shown
	changed.Issues = slices.Clone(shown.Issues)
	changed.Issues[0].Body = strings.Replace(shown.Issues[0].Body, "## What is wrong", "## What is wrong\n- sneaked in", 1)
	if got := call(t, e, viaRoomctl("dev"), "plan_check", map[string]any{"plan": changed, "hash": intake.Hash(shown)}); !got.isError ||
		!strings.Contains(got.text, "plan_changed") {
		t.Fatalf("%s", got.text)
	}
}

// A plan the redactor refuses is refused here too: the one validator, whichever door.
func TestPlanCheckRunsCheckDraftAndTheRedactor(t *testing.T) {
	e := setup(t, mcpOn, withIntake(t, "session"))
	for name, mutate := range map[string]func(*intake.Plan){
		"no acceptance section": func(p *intake.Plan) { p.Issues[0].Body = "## What is wrong\nx" },
		"a secret":              func(p *intake.Plan) { p.Issues[0].Body += "\nAKIAIOSFODNN7EXAMPLE" },
	} {
		p := planFixture(t, "single")
		mutate(&p)
		if got := call(t, e, viaRoomctl("dev"), "plan_check", map[string]any{"plan": p, "hash": intake.Hash(p)}); !got.isError ||
			!strings.Contains(got.text, "invalid_draft") {
			t.Errorf("%s: %s", name, got.text)
		}
	}
}
```

`internal/metrics/metrics_test.go` (Review Focus: the dashboard queries the spec's names, so the rename has to be real):

```go
// The spec's series are maku_intake_*, which MakuName can only produce from an intake_* instrument:
// rooms_intake_plan_total would be served as maku_rooms_intake_plan_total. This is the test that
// makes the dashboard's queries true rather than plausible.
func TestMakuNameCoversIntake(t *testing.T) {
	for in, want := range map[string]string{
		"intake_plan_total":   "maku_intake_plan_total",
		"intake_plan_seconds": "maku_intake_plan_seconds",
		"intake_plan_tokens":  "maku_intake_plan_tokens",
		"intake":              "",
		"intakex":             "",
	} {
		if got := MakuName(in); got != want {
			t.Fatalf("MakuName(%q) = %q, want %q", in, got, want)
		}
	}
}

// And the served name is the spec's, once through the exporter.
func TestIntakeSeriesAreServedAsMakuIntake(t *testing.T) {
	ctx := t.Context()
	exp, err := NewExporter(BrokerBuildInfo, "v0.34.0")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = exp.Shutdown(ctx) }()
	s, err := New(exp.Meter())
	if err != nil {
		t.Fatal(err)
	}
	s.IntakePlan(ctx, "session", "planned", "")
	s.IntakePlanSeconds(ctx, "session", "planned", 250*time.Millisecond)
	s.IntakePlanTokens(ctx, "session", "prompt", 1200)
	got := series(scrape(t, exp.Handler()))
	for _, want := range []string{"maku_intake_plan_total", "maku_intake_plan_seconds", "maku_intake_plan_tokens"} {
		if _, ok := got[want]; !ok {
			t.Errorf("%s is not served", want)
		}
	}
}
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run TestPlanCheck -count=1; go test ./internal/metrics/ -run 'TestMakuNameCoversIntake|TestIntakeSeries' -count=1`
Expected: FAIL (`unknown tool: plan_check`; `MakuName("intake_plan_total") = ""`).

- [ ] **Step 3: Implement it**

`planCheckTool` decodes, recomputes `intake.Hash` over the submitted plan, refuses a mismatch with `plan_changed` (never echoing the submitted hash as if it were the plan's), runs `intake.Check` with the caller's candidate set and the class table, then `s.checkDraft` (`issuedraft.go:82`) on every issue — the same template and the same redactor as `issue_draft`, so CD3 stays one validator. It writes nothing, calls no model and counts nothing but a metric. The caller is resolved by the same `requester(...)` helper `intake_plan` uses, so a sponsored token's `plan_check` asks GitHub about the linked login and never about the App.

- [ ] **Step 4: The metrics**

In `metrics.go`'s `New`, and in `MakuName` beside the two existing cases:

```go
	// intake_plan_total{surface,outcome,reason} -> maku_intake_plan_total (MakuName's intake_ case):
	// whether the planner works. A rising asked means the allowlist or the evidence is weak;
	// degraded means the route is down. The spec's series name is maku_intake_*, which the Go name
	// must be able to produce.
	s.IntakePlans, err = meter.Int64Counter("intake_plan_total", metric.WithDescription("Plans the intake boundary produced, refused, asked or degraded."))
	// intake_plan_seconds{surface,outcome}: the 20 s bound is a product decision.
	s.IntakePlanSeconds, err = meter.Float64Histogram("intake_plan_seconds", metric.WithDescription("One intake_plan, its model call included."))
	// intake_plan_tokens{surface,kind}: the call's cost, from the response's usage.
	s.IntakePlanTokens, err = meter.Int64Counter("intake_plan_tokens", metric.WithDescription("Tokens the planner spent, by kind."))
```

- [ ] **Step 5: Run the suites, then commit**

Run: `go test ./internal/humanapi/ ./internal/metrics/ -count=1`
Expected: PASS.

```bash
git add internal/humanapi internal/metrics
git commit -m "feat(humanapi): plan_check, the re-validation door, and the planner's metrics"
```

### Task 4: the wiring, the docs and PR 2

**Files:**
- Modify: `internal/app/broker.go` (build `humanapi.Intake` from `cfg.IntakePlan()`), `internal/github/app.go` (`Repository`), `internal/app/access.go` (a new `intakePublicity` beside `roomAccess`), `docs/api.md`
- Test: `internal/app/broker_test.go`, `internal/github/app_test.go`

**Interfaces:**
- Produces: `func (a *App) Repository(ctx context.Context, owner, repo string) (github.Repository, error)` with `type Repository struct{ Private bool; Visibility string }`, reading `GET /repos/{owner}/{repo}` with the installation token (metadata: read covers it), 404 → `ErrNoInstallation`;
  `func intakePublicity(gh gitHubVisibilities, ttl time.Duration) intake.Publicity` in `internal/app/access.go`, beside `roomAccess` — it takes the **existing** `gitHubUsers` seam's neighbour (a one-method interface `gitHubVisibilities{ Repository(ctx, owner, repo string) (github.Repository, error) }`, which `*github.App` and `accessApp(dir)` already satisfy) and wraps it in `intake.NewPublicity`, so the visibility cache's TTL is `human.access`'s TTL, the same window a revoked read lapses in.

- [ ] **Step 1: Write the failing tests**

`appFor(t, routes map[string]string)` is `internal/github`'s existing test helper (`github_test.go`): it builds an `*App` over an `httptest.Server` whose paths answer the given JSON, and mints installation tokens for it.

```go
// The visibility read is the App's, and a repository it cannot see is not public.
func TestRepositoryVisibility(t *testing.T) {
	g := appFor(t, map[string]string{"/repos/Smana/ai-native-ref": `{"private":false,"visibility":"public"}`,
		"/repos/Smana/hidden": `{"private":true,"visibility":"private"}`})
	if r, err := g.Repository(t.Context(), "Smana", "ai-native-ref"); err != nil || r.Private {
		t.Fatalf("%+v %v", r, err)
	}
	if r, err := g.Repository(t.Context(), "Smana", "hidden"); err != nil || !r.Private {
		t.Fatalf("%+v %v", r, err)
	}
	if _, err := g.Repository(t.Context(), "Smana", "gone"); !errors.Is(err, github.ErrNoInstallation) {
		t.Fatalf("%v", err)
	}
}

// The switch builds nothing when it is off: no model, no tool, no metric, no route.
func TestIntakeIsOffByDefault(t *testing.T) { /* broker() with human.intake.plan absent: server.Intake == nil */ }

// The visibility cache is the access one: a public repository is asked about once per TTL, and a
// repository GitHub cannot answer for is never cached as public.
func TestIntakePublicityCachesLikeAccess(t *testing.T) { /* intakePublicity(fake, 5*time.Minute) twice -> one lookup */ }
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/github/ -run TestRepositoryVisibility -count=1; go test ./internal/app/ -run 'TestIntakeIsOffByDefault|TestIntakePublicity' -count=1`
Expected: FAIL at compile (`g.Repository undefined`, `intakePublicity undefined`).

- [ ] **Step 3: Implement the read and the wiring**

`Repository` follows `Permission`'s shape (`app.go:438`): `validRepo`, the installation token, `retry401`, `maxReply`. In `internal/app/access.go`, `intakePublicity` sits next to `roomAccess` and uses the same `accessApp(ROOMS_GITHUB_APP_DIR)` the room-access check already builds (its own instance: a visibility read never waits behind a permission check's token mint). `humanServer` (`broker.go:347`) builds `&humanapi.Intake{Classes, Allow, Model, Public, Daily, Fallback, Now}` only when `plan.Enabled`: `Model` from `httpx.New(plan.Deadline, nil)` and `plan.APIKeyFile`, `Allow` from `plan.Repositories` (lowercased, as `SessionStart` already is), `Classes` from `plan.Classes`. There is no channel ceiling in the struct: the App passes its channel's `maxCostUSD` as the tool's `ceiling` argument, which `run_create` already does with `max_cost`.

- [ ] **Step 4: Document the surface**

`docs/api.md`: the two tools, their schemas, the result shape, the refusal list with one sentence each, the switch, and the one line that matters for an operator — "the planner's model call is the only place the broker reaches a model; it sends public text only, refuses a private repository before the call, and logs the hash, never the text".

- [ ] **Step 5: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/intake-tools
gh pr create --title "feat(humanapi): intake_plan and plan_check behind human.intake.plan" \
  --body "CD5, CD17, CD18; offline proofs 1, 2, 3, 15. The switch is off, so both lists are today's. Evidence: task check exit 0, task lint 0."
```

---

## PR 3 — `feat/intake-coding-agent`: the journey from a sentence to a filed issue

CD1, CD4, CD6. The coding agent passes context; it does not write the plan.

### Task 1: `issue_file` takes the plan and its hash

**Files:**
- Modify: `internal/maku/issuefile.go` (`issueFileEntry`, `issueFile`, `draftShape`, `draft`), `internal/maku/localtools.go` (unchanged names), `internal/mcpwire/mcpwire.go`
- Test: `internal/maku/issuefile_test.go`

**Interfaces:**
- Consumes: `plan_check` (PR 2, Task 3); `mcpwire.PlanCheck`.
- Produces: `issue_file`'s schema gains two optional properties, `plan` (`{"type":"object"}`) and `hash` (`{"type":"string","pattern":"^sha256:[0-9a-f]{64}$"}`), and its required list stays exactly `["repo","title","body"]` — so an older broker and an older skill both keep working; `type planShape struct{ Plan json.RawMessage; Hash string; CanStart bool; CanStartWhy string }`; the form's message names the ceiling when the plan carries one.

- [ ] **Step 1: Write the failing tests**

Helpers, all in `issuefile_test.go` (the file already has most of them): `relay(t, broker)` builds a `*Relay` whose broker answers from `broker`; `fakeBroker(t, ...string)` is the `httptest.Server` it counts and answers from, with `r.filed` (gh calls), `r.asked` (forms shown), `r.planChecks` (calls to `plan_check`), `r.lastForm()` (the elicitation message) and `planArgs()`/`planArgsChanged()` (argument maps whose plan is the `internal/intake` fixture `single`, decoded by the package's own `planFixture(t, name)` helper — the same one `intake_test.go` uses, so the plan's bytes are the plan package's goldens).

```go
// Offline proof 4, second half: issue_file re-validates through the broker. A plan whose hash no
// longer holds files nothing and shows no form.
func TestIssueFileRefusesAChangedPlan(t *testing.T) {
	r := relay(t, fakeBroker(t, planCheckRefused, `{"isError":true,"content":[{"type":"text","text":"plan_changed: the plan is not the one that was shown"}]}`))
	got := r.issueFile(t.Context(), planArgsChanged())
	if !strings.Contains(fmt.Sprint(got), "plan_changed") || r.filed != 0 || r.asked != 0 {
		t.Fatalf("%v filed=%d asked=%d", got, r.filed, r.asked)
	}
}

// A plan the broker accepts is filed as it was validated, and the form shows the repository, the
// issue and the ceiling — and the start field stays what FA4 made it.
func TestIssueFileShowsThePlansCeilingAndKeepsTheStartField(t *testing.T) {
	r := relay(t, fakeBroker(t, planCheckAccepted)) // the broker's tools/call result, built by checked(t, "single")
	got := r.issueFile(t.Context(), planArgs())
	msg := fmt.Sprint(r.lastForm())
	for _, want := range []string{"Smana/ai-native-ref", "$2.00 ceiling", "Start the factory now", "File this issue"} {
		if !strings.Contains(msg, want) {
			t.Errorf("the form lacks %q: %s", want, msg)
		}
	}
	if r.filed != 1 || !strings.Contains(fmt.Sprint(got), "filed") {
		t.Fatalf("%v filed=%d", got, r.filed)
	}
}

// Without a plan the tool is exactly today's tool: no plan_check call, no ceiling line.
func TestIssueFileWithoutAPlanIsUnchanged(t *testing.T) { /* the existing case, plus r.planChecks == 0 */ }
```

`planCheckAccepted`/`planCheckRefused` and `checked(t, name)` are three small builders in the same file: `checked` marshals a plan plus `intake.Hash` into the `structuredContent` a `plan_check` call returns, and the two constants are the whole `tools/call` result around it (`isError` true or false). No literal `{...}` stands in for a plan anywhere in the test: the bytes come from the fixture, so a change to `plan/v1` breaks one place.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/maku/ -run 'TestIssueFile' -count=1`
Expected: FAIL (the new cases; the old ones still pass).

- [ ] **Step 3: Implement it**

`issueFile` calls `plan_check` **before** `issue_draft` when `plan` is present (one relay call, `callBroker`, the existing `relay` path), uses the returned plan's single issue as the draft to show, and refuses with the broker's text as is on `isError`. The form's `message` gains `(<source> ceiling)` from the plan when it is there. Nothing else moves: the `file` and `start` fields, the label rule, the `fallbackNext` command.

- [ ] **Step 4: Run the package, then commit**

Run: `go test ./internal/maku/ -count=1`
Expected: PASS.

```bash
git add internal/maku internal/mcpwire
git commit -m "feat(maku): issue_file takes plan/v1 and its hash, and re-checks both"
```

### Task 2: the prompt and the skill pass context, and stop composing

**Files:**
- Modify: `internal/humanapi/mcpprompts.go` (`handoff`, and the new `plan` prompt), `internal/maku/skill/factory-handoff/SKILL.md`, `internal/maku/skill/commands/factory.md`
- Test: `internal/humanapi/mcpprompts_test.go`, `internal/maku/skill/skill_test.go`

**Interfaces:**
- Produces: the prompt `handoff`'s text, which now reads: "Call `intake_plan` with the developer's own words and the context you have: the repository you are in and the paths you read. Show its text as it is. Then call `issue_file` with the plan and its hash, once the developer answers its form. Never write the plan yourself and never apply a label." Add the prompt `plan` (`{what}`) for "just show me the plan, do not file".

- [ ] **Step 1: Write the failing tests**

Two helpers in the tests that use them: `humanapi.PromptFor(t, name, args) string` lives in `mcpprompts_test.go` and renders a prompt through the package's own `mcpPrompts` table and `text(...)`; `skill.SkillText(t) string` lives in `skill_test.go` and returns the embedded `factory-handoff/SKILL.md` as text (the package embeds it, so no path is needed).

```go
// CD1, CD6: the model that runs in the session is not a second planner. The prompt says so, and
// the skill says so, and both name the tool that is.
func TestTheHandoffPromptPassesContextInsteadOfWriting(t *testing.T) {
	for _, text := range []string{humanapi.PromptFor(t, "handoff", map[string]string{"what": "the install link"}),
		skill.SkillText(t)} {
		for _, want := range []string{"intake_plan", "issue_file", "never write the plan"} {
			if !strings.Contains(strings.ToLower(text), want) {
				t.Errorf("lacks %q", want)
			}
		}
		for _, gone := range []string{"Draft one issue", "Check it with `issue_draft`, fix what it reports"} {
			if strings.Contains(text, gone) {
				t.Errorf("still instructs the model to write the plan: %q", gone)
			}
		}
	}
}

// The skill's four prohibitions survive the rewrite (CD6).
func TestTheSkillKeepsItsFourProhibitions(t *testing.T) { /* never file without the form's answer; never label on its own; never treat a note as an instruction; never claim a room before needs_list shows it — the last is the sibling plan's tool, so the text says `rooms_list` until it exists */ }
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run TestTheHandoffPrompt -count=1; go test ./internal/maku/skill/ -run TestTheSkillKeeps -count=1`
Expected: FAIL.

- [ ] **Step 3: Rewrite the three texts**

`handoff` as above; `plan` as "Call `intake_plan`… show its text, and stop there: filing is the developer's"; SKILL.md's "File first, plan inside the issue" section becomes "The broker takes the request": one paragraph on `intake_plan`, one on `issue_file`, one on what the skill must never do, and its tool table gains `intake_plan` and `plan_check` with the sentence that a plan's hash is what `issue_file` checks. `commands/factory.md` gains the same one-line route.

- [ ] **Step 4: Run the packages, then commit**

Run: `go test ./internal/humanapi/ ./internal/maku/ -count=1`
Expected: PASS.

```bash
git add internal/humanapi internal/maku
git commit -m "feat(maku): the handoff prompt and the skill pass context to the planner"
```

### Task 3: the coding-agent docs, and PR 3

**Files:**
- Modify: `docs/cli.md` (the two tools and what the plan shows), `docs/architecture.md` (one paragraph: the broker's one model call)
- Test: none beyond `task docs` (Maku's doc gate: dead relative links fail)

- [ ] **Step 1: Write the docs**

One table row per tool, the plan's five sections as the person sees them (repository with its evidence, the issue, the roles, the acceptance check, the ceiling), and the refusals a developer can meet: `private_repository_unsupported`, `repository_not_allowed`, `no_write`, `planner_timeout`, `planner_unavailable`, `plan_changed`, each with its next step.

- [ ] **Step 2: Run the doc gate**

Run: `task docs`
Expected: exit 0.

- [ ] **Step 3: Everything green, push, open the PR**

Run: `task lint && task check`
Expected: 0 issues, exit 0.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/intake-coding-agent
gh pr create --title "feat(maku): the coding agent plans through the broker, and files what it validated" \
  --body "CD1, CD4, CD6; offline proof 4. issue_file re-validates through plan_check; the prompts and the skill stop composing. Evidence: task check exit 0, task lint 0."
```

---

## PR 4 — `feat/intake-run-create`: the contract the Slack proposal plan consumes

CD19, CD20, CD27's second check. No Slack UI here: the tool's contract only.

### Task 1: `run_create` validates the plan and its hash

**Files:**
- Create: `internal/intake/testdata/plan/slack-one-issue.json`
- Modify: `internal/humanapi/runcreate.go` (`runCreateSchema`, `runCreateArgs`, `createTask`), `docs/api.md`
- Test: `internal/humanapi/runcreate_test.go`

**Interfaces:**
- Produces: `run_create`'s schema gains `plan` (`{"type":"object"}`) and `plan_hash` (`{"type":"string","pattern":"^sha256:[0-9a-f]{64}$"}`) with `additionalProperties:false` unchanged and the required list unchanged; `runCreateArgs.Plan json.RawMessage`, `.PlanHash string`; the validation `func (s *Server) checkPlan(ctx context.Context, a runCreateArgs, p authn.Principal) *intake.Refusal`.

- [ ] **Step 0: Create the fixture the test reads**

`internal/intake/testdata/plan/slack-one-issue.json` — in the **one** fixture directory `planFixture` reads (`internal/intake/testdata/plan/`, which the human API's tests reach through the helper PR 2 added): one issue, `repository: Smana/ai-native-ref`, `budget: {"ceilingUSD": 1.5, "source": "channel:C1.maxCostUSD"}`, `planner: {"model": "tier-frontier", "surface": "slack", "at": …}`, `rev: 1`, no `question`, **no `hash` key**. Copied from `single.json` with the budget, surface and repository's evidence re-pointed, and it stays in that directory so the plan package can render the same goldens the API's tests use.

- [ ] **Step 1: Write the failing tests**

```go
// The contract the proposal plan will rely on: the plan is the promise, and the four fields the
// App still sends are checked against it. Any disagreement files nothing.
func TestRunCreateHoldsTheTaskToItsPlan(t *testing.T) {
	e := setup(t, mcpOn, withSponsored(sponsoredP), withIntake(t, "slack"))
	plan := planFixture(t, "slack-one-issue") // one issue, $1.50 from the channel
	ok := map[string]any{"repo": plan.Repository, "title": plan.Issues[0].Title, "text": plan.Issues[0].Body,
		"dataClass": "public", "max_cost": 1.5, "on_behalf_of": "slack:T1/U2",
		"plan": plan, "plan_hash": intake.Hash(plan)}
	if got := call(t, e, bearer("slack-app"), "run_create", ok); got.isError {
		t.Fatalf("%s", got.text)
	}
	for name, mutate := range map[string]func(map[string]any){
		"a hash that moved":  func(m map[string]any) { m["plan_hash"] = "sha256:" + strings.Repeat("0", 64) },
		"another repository": func(m map[string]any) { m["repo"] = "Smana/cloud-native-ref" },
		"a body changed":     func(m map[string]any) { m["text"] = plan.Issues[0].Body + "\nand more" },
		"a ceiling above it": func(m map[string]any) { m["max_cost"] = 9.0 },
		"two issues":         func(m map[string]any) { m["plan"] = planFixture(t, "three") },
	} {
		args := maps.Clone(ok)
		mutate(args)
		if got := call(t, e, bearer("slack-app"), "run_create", args); !got.isError {
			t.Errorf("%s: filed", name)
		} else if !strings.Contains(got.text, "plan_changed") && !strings.Contains(got.text, "invalid_arguments") {
			t.Errorf("%s: %s", name, got.text)
		}
	}
}

// Without a plan, run_create is today's tool: an older App keeps working, unchanged.
func TestRunCreateWithoutAPlanIsUnchanged(t *testing.T) { /* the existing case, verbatim */ }
```

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/humanapi/ -run TestRunCreateHolds -count=1`
Expected: FAIL.

- [ ] **Step 3: Implement the four checks**

In `createTask`, before the redactor: when `Plan` is present — (1) `intake.Hash(plan) == PlanHash`, else `plan_changed`; (2) exactly one issue, else `invalid_arguments: Slack files exactly one issue`; (3) `a.Repo == plan.Repository`, `a.Title == plan.Issues[0].Title`, `a.Text == plan.Issues[0].Body`, else `plan_changed`; (4) `a.MaxCost <= plan.Budget.CeilingUSD`, else `invalid_arguments: max_cost is above the plan's ceiling`. Then the existing path (`checkDraft`, the factory call) runs untouched, so a plan that passes is still checked by the one validator.

- [ ] **Step 4: Run the package, then the PR**

Run: `go test ./internal/humanapi/ -count=1 && task lint && task check`
Expected: PASS, 0 issues, exit 0.

```bash
git add internal/humanapi docs/api.md
git commit -m "feat(humanapi): run_create holds a task to the plan it was confirmed from"
git fetch origin && git rebase origin/main && git push -u origin feat/intake-run-create
gh pr create --title "feat(humanapi): run_create takes plan/v1 and its hash" \
  --body "CD19, CD20, CD27. The contract the Slack proposal plan consumes; no Slack code here. Evidence: task check exit 0, task lint 0."
```

---

## ai-native-ref PR A — `feat/intake-plan-wiring`: the secret, the two CNP halves, the gates

Everything ships with `human.intake.plan.enabled: false`. **The remote value first, then the release, then the keys** ([Global Constraints](#global-constraints)): A1 and A2 may merge before the Maku release (a mounted Secret and a network rule are inert to an older broker); A3's config keys may not.

### Task A1: the `planner` value, in one place both namespaces can read

**Files:**
- Create: `infrastructure/base/room-broker/externalsecret-planner.yaml` (the broker's copy, mounted at `/etc/room-broker/planner/api-key`)
- Create: `infrastructure/base/envoy-ai-gateway/externalsecret-planner-key.yaml` (the gateway's copy, Secret `ai-gateway-planner-key`)
- Modify: `infrastructure/base/envoy-ai-gateway/security-policy.yaml` (`credentialRefs` gains `ai-gateway-planner-key`), `infrastructure/base/envoy-ai-gateway/kustomization.yaml`, `infrastructure/base/room-broker/kustomization.yaml`, `infrastructure/base/room-broker/app.yaml` (the mount)
- Test: `scripts/ci/tests/test-intake-plan-wiring.py` (new)

**Interfaces:**
- Produces: two `ExternalSecret`s in two namespaces reading **one** entry, `apps/planner` (`apiKey`), through the cluster-scoped `ClusterSecretStore openbao-apps`; the gateway's rendered Secret `ai-gateway-planner-key`, whose **data key must be `planner`** (Envoy Gateway's `apiKeyAuth` compares the bearer against each Secret *value* and forwards the Secret *key* as `x-ai-gateway-client-id`, so a key named `api-key` would make this client `api-key` in every log and every spend series), listed in `apiKeyAuth.credentialRefs`.

- [ ] **Step 1: Write the failing gate**

`scripts/ci/tests/test-intake-plan-wiring.py` (offline proof 17) reads the **source tree**, like `test-agent-pins.py` and `test-room-broker-suspend.py` do — not `.bundle`: the facts here are an `ExternalSecret`'s shape, a `SecurityPolicy`'s `credentialRefs` and an `App`'s volumes, all legible before a render, and a source read keeps the gate runnable without `task check`'s host profile. Helper functions in the file (they grow with A2): `load(path, name=None)` (the first YAML doc, or the one whose `metadata.name` is `name`), `docs(path)`, `check(cond, msg)` (appends to `problems`), `ports(rule)`, `credential_names()` (every `credentialRefs[].name` in `security-policy.yaml`), `tree("infrastructure")`.

```python
    # The one identity, in both namespaces, from one remote entry: a namespaced Password generator
    # cannot mint the same value twice, so a cluster-scoped store is the only wiring that survives
    # both clouds.
    for path, name, ns in [("infrastructure/base/room-broker/externalsecret-planner.yaml", "room-broker-planner", "agent-system"),
                           ("infrastructure/base/envoy-ai-gateway/externalsecret-planner-key.yaml", "ai-gateway-planner-key", "envoy-ai-gateway-system")]:
        es = load(path)
        check(es["spec"]["secretStoreRef"] == {"kind": "ClusterSecretStore", "name": "openbao-apps"}, f"{path}: not the shared store")
        check(es["metadata"]["namespace"] == ns, f"{path}: namespace")
        check(es["spec"]["data"][0]["remoteRef"]["key"] == "planner", f"{path}: remote key")
        check(es["spec"]["data"][0]["remoteRef"]["property"] == "apiKey", f"{path}: property")
        check(es["spec"]["target"]["name"] == name, f"{path}: target name")
    # The gateway's Secret key IS the client id: `planner`, never `api-key`, or every log line and
    # spend series attributes these tokens to a client nobody can name.
    gw = load("infrastructure/base/envoy-ai-gateway/externalsecret-planner-key.yaml")
    check(gw["spec"]["data"][0]["secretKey"] == "planner", "the gateway copy's Secret key must be planner")
    pol = load("infrastructure/base/envoy-ai-gateway/security-policy.yaml")
    names = [c["name"] for c in pol["spec"]["apiKeyAuth"]["credentialRefs"]]
    check("ai-gateway-planner-key" in names and names[0] == "ai-gateway-api-keys", "the planner key is a credential of the one API-key policy")
    # The broker mounts its own copy under its own name, and never reads another namespace's Secret.
    app = load("infrastructure/base/room-broker/app.yaml")
    mounts = [m for m in app["spec"]["extraVolumeMounts"] if m["name"] == "planner"]
    check(mounts and mounts[0]["mountPath"] == "/etc/room-broker/planner" and mounts[0]["readOnly"], "the broker's mount")
    # No literal anywhere.
    for p in tree("infrastructure"):
        check("sk-planner" not in Path(p).read_text() and "plannerKey:" not in Path(p).read_text(), f"{p}: a literal key")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-intake-plan-wiring.py`
Expected: FAIL (`no such file: externalsecret-planner.yaml`).

- [ ] **Step 3: Write the two ExternalSecrets, the policy entry and the mount**

The broker's copy (mounted; the Secret's own key name is arbitrary, so it keeps `api-key`):

```yaml
# The broker's copy of the planner's client key (CD18): one remote entry, read through the store
# both namespaces can reach. The same value is envoy-ai-gateway-system's ai-gateway-planner-key,
# because the gateway authenticates the call the broker makes.
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: room-broker-planner
  namespace: agent-system
spec:
  refreshInterval: 20m
  secretStoreRef:
    kind: ClusterSecretStore
    name: openbao-apps
  data:
    - secretKey: api-key # pragma: allowlist secret
      remoteRef: {key: planner, property: apiKey}
  target:
    name: room-broker-planner
    creationPolicy: Owner
    deletionPolicy: Retain
```

The gateway's copy — its Secret key is templated to `planner`, which is what `ForwardClientIDHeader` reports:

```yaml
# The AI Gateway's half of the planner's identity (CD18). The Secret's KEY is the client id
# apiKeyAuth reports on x-ai-gateway-client-id, so it is `planner` and not `api-key`: the spend
# series and the access log name this call by it. The VALUE is the same OpenBao entry the broker
# mounts.
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: ai-gateway-planner-key
  namespace: envoy-ai-gateway-system
spec:
  refreshInterval: 20m
  secretStoreRef:
    kind: ClusterSecretStore
    name: openbao-apps
  data:
    - secretKey: planner # pragma: allowlist secret
      remoteRef: {key: planner, property: apiKey}
  target:
    name: ai-gateway-planner-key
    creationPolicy: Owner
    deletionPolicy: Retain
```

`security-policy.yaml`'s `apiKeyAuth.credentialRefs` becomes `[{name: ai-gateway-api-keys}, {name: ai-gateway-planner-key}]` — a list of Secrets, each contributing one client id per data key.

`infrastructure/base/room-broker/app.yaml` gains, in its existing `extraVolumes`/`extraVolumeMounts` lists (the `config`, `tls` and `oidc` entries are the pattern), `{name: planner, secret: {secretName: room-broker-planner}}` and `{name: planner, mountPath: /etc/room-broker/planner, readOnly: true}`. Both lists are already on the `App` CRD, so no chart change is needed; the mount is inert to a broker that does not read it, which is why this task may land before the release.

- [ ] **Step 4: The operator step, recorded before the merge**

`docs/runbooks/agent-factory/19-factory-from-your-agent.md` gains a "Planner key" section: write the value to OpenBao **before** the PR merges —

```
bao kv put apps/planner apiKey="$(openssl rand -hex 24)"
```

— and why: an `ExternalSecret` with a missing remote reference reports `SecretSyncedError`, and on the gateway that Path is the same one that carries the other clients' keys.

- [ ] **Step 5: Run the gate, then commit**

Run: `python3 scripts/ci/tests/test-intake-plan-wiring.py`
Expected: exit 0.

```bash
git add infrastructure scripts/ci/tests
git commit -m "feat(intake): the planner's client key, in one place both namespaces read"
```

### Task A2: the two CNP halves, and the pairing they must keep

**Files:**
- Modify: `infrastructure/base/room-broker/network-policy.yaml` (one egress rule), `infrastructure/base/envoy-gateway/network-policy.yaml` (one ingress entry on `envoy-data-plane`)
- Test: `scripts/ci/tests/test-intake-plan-wiring.py` (extended)

**Interfaces:**
- Produces: the broker's egress to the **AI Gateway data-plane proxy pods** on `8080` (Cilium `toEndpoints` selects pods, not Services: the selector is the same one `envoy-data-plane` uses for itself — `app.kubernetes.io/managed-by: envoy-gateway`, `app.kubernetes.io/component: proxy`, `gateway.envoyproxy.io/owning-gateway-name: ai-gateway`, `gateway.envoyproxy.io/owning-gateway-namespace: envoy-ai-gateway-system`), and `envoy-data-plane`'s ingress `fromEndpoints` entry selecting **only** `{io.kubernetes.pod.namespace: agent-system, app.kubernetes.io/name: room-broker}` on `8080`.

- [ ] **Step 1: Write the failing gate cases**

```python
    # Either half alone refuses the call, and the ingress half must not widen: one entry, one pod
    # selector, one port. A fixture that reaches another pod or port fails here (offline proof 17).
    # The egress names the data-plane PODS, not a Service: a Cilium toEndpoints naming a Service or
    # a Gateway label matches no endpoint and the call is dropped in silence. This selector is the
    # one envoy-data-plane uses for its own endpointSelector.
    dp_labels = {"app.kubernetes.io/managed-by": "envoy-gateway", "app.kubernetes.io/component": "proxy",
                 "gateway.envoyproxy.io/owning-gateway-name": "ai-gateway",
                 "gateway.envoyproxy.io/owning-gateway-namespace": "envoy-ai-gateway-system"}
    broker_cnp = load("infrastructure/base/room-broker/network-policy.yaml")
    to_gw = [r for r in broker_cnp["spec"]["egress"]
             if any(e.get("matchLabels", {}) == {"io.kubernetes.pod.namespace": "envoy-gateway-system", **dp_labels}
                    for e in r.get("toEndpoints", []))]
    check(len(to_gw) == 1 and ports(to_gw[0]) == {8080}, "the broker's egress selects the ai-gateway data-plane pods on 8080, and nothing else")
    dp = load("infrastructure/base/envoy-gateway/network-policy.yaml", name="envoy-data-plane")
    check(dp["spec"]["endpointSelector"]["matchLabels"] == dp_labels, "the data-plane policy is still the ai-gateway's alone")
    entries = [r for r in dp["spec"]["ingress"] if r.get("fromEndpoints")]
    planner = [r for r in entries if any(e["matchLabels"].get("app.kubernetes.io/name") == "room-broker" for e in r["fromEndpoints"])]
    check(len(planner) == 1 and ports(planner[0]) == {8080}, "one entry, 8080")
    for e in planner[0]["fromEndpoints"]:
        check(set(e["matchLabels"]) == {"io.kubernetes.pod.namespace", "app.kubernetes.io/name"}, f"a widened selector: {e}")
        check(e["matchLabels"] == {"io.kubernetes.pod.namespace": "agent-system", "app.kubernetes.io/name": "room-broker"}, "any other pod")
    # The pairing rule the file states: every in-cluster ingress source also holds a key the API-key
    # SecurityPolicy knows, or it is whitelisted and refused.
    check("ai-gateway-planner-key" in credential_names(), "the broker's source is authenticated, not only allowed")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-intake-plan-wiring.py`
Expected: FAIL (`no egress rule selecting the ai-gateway data plane`).

- [ ] **Step 3: Write the two rules**

Broker egress, beside the factory's in `infrastructure/base/room-broker/network-policy.yaml`:

```yaml
    # The planner's one model call (CD18), to the AI Gateway data-plane pods directly, as OpenWebUI
    # and the nightly eval do. toEndpoints selects PODS: the Service name matches nothing, and the
    # four labels are the data-plane policy's own endpointSelector. The data plane's policy carries
    # the other half: either alone refuses.
    - toEndpoints:
        - matchLabels:
            io.kubernetes.pod.namespace: envoy-gateway-system
            app.kubernetes.io/managed-by: envoy-gateway
            app.kubernetes.io/component: proxy
            gateway.envoyproxy.io/owning-gateway-name: ai-gateway
            gateway.envoyproxy.io/owning-gateway-namespace: envoy-ai-gateway-system
      toPorts:
        - ports: [{port: "8080", protocol: TCP}]
```

`envoy-data-plane`'s ingress, beside OpenWebUI and promptfoo:

```yaml
        # The room broker's planner (v3.x conversational intake, CD18). Scoped to the pod, on 8080,
        # and paired with ai-gateway-planner-key in security-policy.yaml: whitelisted and
        # authenticated, or refused.
        - matchLabels:
            io.kubernetes.pod.namespace: agent-system
            app.kubernetes.io/name: room-broker
```

- [ ] **Step 4: Run the gate and the bundle's own gates**

Run: `task check`
Expected: exit 0, including `assert-ai-gateway.py` and the host's `validate-manifests.sh`.

- [ ] **Step 5: Commit**

```bash
git add infrastructure/base/room-broker/network-policy.yaml infrastructure/base/envoy-gateway/network-policy.yaml scripts/ci/tests
git commit -m "feat(intake): both halves of the broker's call to the AI Gateway"
```

### Task A3: the release, then the switch, the allowlist and the class table

**Prerequisite, and it is a hard one.** This task may not merge until a Maku **release** exists whose `config.Load` knows `human.intake`: `scripts/ci/tests/test-maku-config-load.sh` takes the tag from `infrastructure/base/room-broker/app.yaml` and loads every `infrastructure/*/room-broker/config.yaml` through *that* tag's loader, and a strict decoder refuses the unknown `human.intake` key — the gate fails, and it is right to. So:

1. Maku PR 2 merges, a release is cut (say `v0.34.0`), and its chart and digests exist.
2. This PR bumps the broker's pin to it — `infrastructure/base/room-broker/app.yaml`'s `image.tag` (`v<ver>@sha256:<digest>`), **and the three places that comment names**: `infrastructure/base/room-broker/retention-cronjob.yaml`'s image, `infrastructure/base/room-broker/crd-rooms.yaml`'s source comment, and `infrastructure/base/room-broker/sqlinstance.yaml`'s `atlasSchema.ref`. They move together or the CronJob, the CRDs and the schema disagree with the Deployment.
3. Only then, in the same PR, does the `human.intake` block land — in the **three** copies: `infrastructure/base/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` and, when the aws-0 session copy exists, `infrastructure/aws-0/room-broker/config.yaml`.

**Files:**
- Modify: `infrastructure/base/room-broker/app.yaml` (image tag+digest), `infrastructure/base/room-broker/retention-cronjob.yaml`, `infrastructure/base/room-broker/crd-rooms.yaml` (comment), `infrastructure/base/room-broker/sqlinstance.yaml` (`atlasSchema.ref`)
- Modify: `infrastructure/base/room-broker/config.yaml` (`human.intake.plan`, off), `infrastructure/gcp-0/room-broker/config.yaml` (the same block, off), `infrastructure/aws-0/room-broker/config.yaml` (the same block, off, when that session copy exists)
- Modify: `scripts/ci/tests/test-room-broker-suspend.py` (`minus_switches`/`minus_session_switches` gain `intake`)
- Create: `scripts/ci/tests/test-room-broker-intake-classes.py`
- Test: `test-room-broker-intake-classes.py`, `test-room-broker-suspend.py`, `test-room-broker-config-rollout.py`, `test-maku-config-load.sh`, `task check`

**Interfaces:**
- Produces: the declared block, in every broker config copy, off:

```yaml
  intake:
    plan:
      enabled: false            # turned on for one repository by ai-native-ref PR B
      url: http://ai-gateway.envoy-gateway-system.svc.cluster.local:8080/v1
      model: tier-frontier
      apiKeyFile: /etc/room-broker/planner/api-key
      deadline: 20s
      dailyPlans: 50
      fallback: "off"
      repositories: [Smana/ai-native-ref]      # the public repositories this boundary may plan for
      classes:
        docs-links: {roles: [scoper, implementer, reviewer], ceilingUSD: 2.00, source: "class:docs-links.taskUSD"}
```

- [ ] **Step 1: Write the failing gates**

`test-room-broker-intake-classes.py` asserts, on the rendered `room-broker-config` and `agent-factory-config` ConfigMaps: every `classes` key is a class of a served repository in the factory's config; every role is one the factory runs; every `ceilingUSD` is at most the default tier's `taskUSD` (a ceiling above the tier is money the factory does not have); every `repositories` entry is a repository the factory's config names, or the one public repository the proof uses; and `enabled: false` in every cloud's copy until PR B.

`test-room-broker-suspend.py` is amended in the same step, because it compares the copies: its docstring's sentence becomes "gcp-0's copy differs in suspend, webhooks, human.mcp, human.slackLink and human.intake alone", and both comparison helpers gain the key —

```python
def minus_switches(cfg):
    """The config without the keys a gcp-0 session may declare: suspend, webhooks, human.mcp,
    human.slackLink, human.intake."""
    out = {k: v for k, v in cfg.items() if k not in ("suspend", "webhooks")}
    out["human"] = {k: v for k, v in out["human"].items() if k not in ("mcp", "slackLink", "intake")}
    return out
```

and the same `"intake"` addition inside `minus_session_switches` for aws-0. Without it, PR B's one `enabled: true` in gcp-0's copy fails a gate that is about suspend, for a reason it does not name.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 scripts/ci/tests/test-room-broker-intake-classes.py; python3 scripts/ci/tests/test-room-broker-suspend.py`
Expected: FAIL (no `intake` block; and, once the block exists without the amendment, suspend's two difference checks).

- [ ] **Step 3: Bump the broker's pin, then write the block in every copy, then run the gates**

Run: `python3 scripts/ci/tests/test-room-broker-intake-classes.py && python3 scripts/ci/tests/test-room-broker-suspend.py && python3 scripts/ci/tests/test-room-broker-config-rollout.py && bash scripts/ci/tests/test-maku-config-load.sh && task check`
Expected: exit 0 each. `test-maku-config-load.sh` is the one that proves the ordering: it loads all three copies through the tag `app.yaml` now names, so it passes **before** the bump (no key yet, old loader) and **after** it (the new loader, the key present). A run in which the key lands before the bump is the failure this prerequisite exists to prevent.

- [ ] **Step 4: Commit**

```bash
git add infrastructure scripts/ci/tests
git commit -m "feat(intake): the broker on the release that knows the keys, then the planner off in every copy"
```

### Task A4: the dashboard panels and the reader's side

**Files:**
- Modify: `observability/base/agent-platform/grafana-dashboard-agent-room.yaml` (two panels), `website/content/docs/use/guide/terminal-and-coding-agent.md`, `website/content/docs/reference/commands.md`, `website/content/docs/how-it-works/gateways.md` (one row)
- Test: `scripts/ci/tests/test-agent-dashboard-conventions.py` (existing, generic), `task docs`

**Interfaces:**
- Produces: two panels on the room dashboard — "Plans by outcome" (`sum by (outcome, reason) (increase_pure(maku_intake_plan_total[$__range]))`) and "Planner tokens" (`sum by (kind) (increase_pure(maku_intake_plan_tokens[$__range]))`) — and the guide's "Hand off a side task" section rewritten around the plan the broker shows.

- [ ] **Step 1: Write the dashboard change and run the convention gate**

Run: `python3 scripts/ci/tests/test-agent-dashboard-conventions.py`
Expected: exit 0 (every counter reads through `increase_pure`, no `$` decorator missing).

- [ ] **Step 2: Write the pages, in the docs style**

The guide states what the person sees (the repository with its evidence, the issue, the roles, the acceptance check, the ceiling), what the two ways forward are when the repository is private, and that the plan is not the factory's scope — the scoper is. `reference/commands.md` gains `intake_plan` and `plan_check` rows in its tool table. `gateways.md` gains one row: the broker, `tier-frontier`, client id `planner`.

- [ ] **Step 3: Run the doc gates**

Run: `task docs`
Expected: exit 0.

- [ ] **Step 4: Everything green, push, open PR A**

Run: `task check && task docs`
Expected: exit 0 each.

```bash
git fetch origin && git rebase origin/main && git push -u origin feat/intake-plan-wiring
gh pr create --title "feat(intake): wire the planner's identity, its two CNP halves and its switch" \
  --body "CD18's data path and its rollout step 3; offline proofs 15 and 17. The switch is off and no model is reached. The remote value (OpenBao apps/planner) must exist before this merges: runbook 19. Evidence: task check exit 0, task docs exit 0."
```

---

## ai-native-ref PR B — `feat/intake-plan-switch-on`: one public repository, and the proof

**Owner go required before any step here touches the cluster.**

### Task B1: turn it on for one public repository, and record the decision

**Prerequisite.** The broker's pin must name a release containing **PRs 1, 2, 3 and 4** — not the one A3 pinned, unless that release already carries all four. The proof in B2 files an issue through `issue_file` with a plan the broker validated (PRs 2 and 3) and, on the Slack side later, through `run_create`'s contract (PR 4); a broker older than any of them answers `unknown tool` or ignores the plan, and the switch would be on for a feature the binary does not have. So this PR bumps the same four places A3 lists to the complete release before it flips `enabled`.

**Files:**
- Modify: `infrastructure/gcp-0/room-broker/config.yaml` (`enabled: true`, `repositories: [Smana/ai-native-ref]`), plus the broker pin in `infrastructure/base/room-broker/app.yaml`, `retention-cronjob.yaml`, `crd-rooms.yaml` and `sqlinstance.yaml`
- Create: `website/content/docs/decisions/0060-conversational-intake.md`, `website/content/docs/decisions/_index.md` (one row)
- Test: `task docs`, `scripts/ci/tests/test-room-broker-intake-classes.py`, `test-room-broker-suspend.py`, `test-maku-config-load.sh`

**Interfaces:**
- Produces: the one switch-on, and ADR-0060 recording CD1–CD8 and the planner's single governed data path (CD18), with the alternative it rejected ("a planner per channel").

- [ ] **Step 1: Write the ADR and flip the switch**

ADR-0060 follows the repository's decision pages: status Accepted, date 2026-11-05, the five decisions CD1, CD2, CD3, CD17, CD18 with their rejected alternatives, the data path in one paragraph (public text only, `planner` client, `tier-frontier`, 20 s, 64 KiB, no retry, the hash never the text), and the sentence "the degraded composer is not this feature".

- [ ] **Step 2: Run the gates**

Run: `task docs && python3 scripts/ci/tests/test-room-broker-intake-classes.py && python3 scripts/ci/tests/test-room-broker-suspend.py && bash scripts/ci/tests/test-maku-config-load.sh && task check`
Expected: exit 0 each — the suspend gate is the one that must still pass with gcp-0's copy differing in `human.intake`.

- [ ] **Step 3: Commit, push, open PR B**

```bash
git add infrastructure website/content/docs
git commit -m "feat(intake): the planner on for one public repository, and the decision it records"
git fetch origin && git rebase origin/main && git push -u origin feat/intake-plan-switch-on
gh pr create --title "feat(intake): turn the planner on for one public repository" \
  --body "CD1, CD2, CD3, CD17, CD18; ADR-0060. Merging is the owner's call: the live proof in docs/runbooks/agent-factory/results-intake.md follows it."
```

### Task B2: the live proof — public, and the private fallback (owner go)

**Files:**
- Create: `docs/runbooks/agent-factory/results-intake.md`
- Test: the transcript itself, per the spec's go/no-go

**Interfaces:**
- Consumes: the released Maku binary (PRs 1–4), the wired cluster (PR A), the switch (B1).
- Produces: one session's evidence, in the spec's shape, for the two rows this plan owns.

- [ ] **Step 1: Run the public proof** (`Smana/ai-native-ref`, Claude Code **and** OpenCode, one session each)

1. `maku setup <client>` writes the new skill; `maku doctor` prints its capability line.
2. "hand off: the install link in the README is dead" produces a plan whose repository is `Smana/ai-native-ref`, whose issue passes `issue_draft`, and whose roles (`scoper, implementer, reviewer`) and ceiling (`$2.00`, `class:docs-links.taskUSD`) match `room-broker-config`.
3. The gateway's access log shows **one** call under `x-ai-gateway-client-id: planner`, model `tier-frontier`, and `maku_intake_plan_tokens` moves by that call's usage.
4. The broker's log line for it carries the requester, the surface `session`, the repository, the hash, the model, the tokens and the duration — and **no** fragment of the request text (grep the log for three words from the request: no match).
5. The form files it; GitHub shows the developer as the issue's author and as the labeller; the plan's hash in the form session equals the one `plan_check` returns.

- [ ] **Step 2: Run the private fallback proof**

In a session whose repository is private: "hand off: …" returns `private_repository_unsupported` with the two ways forward, the gateway's log shows **zero** planner calls in that window, and `issue_draft` + `issue_file` still work with the developer's own model. Record the refusal's exact sentence and the log's absence.

- [ ] **Step 3: Write the results file and commit**

`results-intake.md` holds the date, the cluster, the Maku version, the two transcripts, the gateway log excerpt (client id, model, one line), the metric query and its value before and after, and a short "what would have failed this" list.

```bash
git add docs/runbooks/agent-factory/results-intake.md
git commit -m "docs(intake): the planner's live proof, one public repository and the private fallback"
git push -u origin feat/intake-plan-switch-on
```

---

## Sequencing, and what each PR lets a reviewer decide alone

| Order | PR | Depends on | A reviewer can reject it without unwinding |
|---|---|---|---|
| 1 | Maku `feat/intake-core` | — | the plan shape, the hash's material set (and its integer ceiling), the guards' order, the model client's bounds |
| 2 | Maku `feat/intake-tools` | 1 | the tool surface, the daily cap's key, the metric names, the audit fields |
| 3 | Maku `feat/intake-coding-agent` | 2 | the prompt and the skill, `issue_file`'s form |
| 4 | Maku `feat/intake-run-create` | 2 | the four checks, and whether they are strict enough |
| release | a Maku tag carrying 1–2 for A3, 1–4 for B1 | 1–4 | the release itself |
| A | ai-native-ref `feat/intake-plan-wiring` | 2 + the release | the identity's origin and Secret key, the egress selector, the two CNP halves, the gates, the docs |
| B | ai-native-ref `feat/intake-plan-switch-on` | A + 3 + the release carrying 1–4 | the switch, the ADR, the proof |

### The seam this plan defines and does not implement {#seam-coordination}

A future `coordination_plan` broker tool — the multi-repository design's, not this one's — is a **consumer contract** of what PRs 1 and 2 build: it reuses `intake.Model` (same route, same `planner` identity, same pinned alias, same 20 s and 64 KiB bounds, same effective-requester resolution, same initial public-only guard), and it increments the same per-requester `human.intake.plan.dailyPlans` counter rather than adding a second. It returns its own typed object and its own canonical hash, **not** a `plan/v1`, and it files nothing. This plan implements none of that: no artifacts, no family budget, no integration order, no child hashes.

## Not in this plan {#not-in}

- `needs/v1`, the resume brief, revision preference, the final spend, the notification table and the measured clients — the attention-and-resume plan.
- Slack's proposal message, `chat.update`, the interactivity branch inside `POST /slack/events`, the thread's question vocabulary and `run_create`'s caller (CD7, CD8, CD25, CD29) — the Slack proposal plan. PR 4 here only gives that plan the contract it passes.
- Approving a run from Slack, and the `forge.push` card — the push-approval plan.
- The Slack channel-binding generator (CD24) and its gate.
- Multi-repository `coordination_plan`, its `planningMicroUSD`, its validation, and every ordering rule.
- Private-repository planning (no `planner.internal` profile exists), repository memory, a cross-repository code search, ranking, routing and digests.

## Self-review

**Spec coverage.** CD1 (no room without an issue: `plan_check` writes nothing and `issue_file` keeps the form) — PR 3. CD2 (one boundary, one implementation) — PRs 1–2, one tool for both surfaces. CD3 (the existing validator) — PR 1 Task 1 and PR 2 Task 3 call `sanitize.CheckDraft` and the redactor, no new template. CD4 (filing per channel) — PR 3 keeps `gh`, PR 4 keeps `run_create`. CD5 (inference with evidence, one question) — `RepositoryEvidence`, `Alternatives`, `Question` in PR 1 Task 1 and the guard in Task 2. CD6 (no new steering surface) — `intake_plan`/`plan_check` are read-only, and the sponsored list still decides nothing. CD7/CD8 — out, and the seam is named. CD14/CD27 — the material set and its tests. CD15 — one question. CD17 — `Compose`, Review Focus 3. CD18 — the model client, the composer, the metric labels. CD19 — 1–3 issues, `dependsOn` recorded not enforced, Slack exactly one (PR 4). CD20 — the plan is transient; PR 4 reads it only from the arguments the App passes from metadata, and the metadata budget is the Slack plan's test. CD29 — no route added. The model call's every row of §model-call has a task: identity A1, route A2, data PR 1 Task 2, request/limits PR 1 Task 3, budget PR 2 Task 2, timeout PR 1 Task 3, refusal PR 1 Task 1–3, audit PR 2 Task 2, failure of the route PR 2 Task 2. Offline proofs 1–5 and 15: 1 → PR 1 Tasks 1, 3 and PR 2 Task 2; 2 → PR 1 Task 2 and 3; 3 → PR 1 Task 1; 4 → PRs 3 Task 1 and 4 Task 1; 5's metadata half belongs to the Slack plan, and its "nothing is filed from the rendered text" half is PR 4; 15 → PR 2 Task 1. ai-native-ref proof 17 → PR A Tasks A1–A3. Live proofs 1 and 2 → Task B2.

**Type consistency.** `intake.Plan`/`Issue`/`Budget`/`Question`/`Evidence`/`Alternative`, `intake.Hash`, `intake.Check`, `intake.Compose`, `intake.ComposeIn`, `intake.Class` (declared in PR 1 Task 1, consumed by Task 3's `Compose`), `intake.Guard`, `intake.Publicity`, `intake.Model`, `intake.Draft`, `intake.Usage`, `intake.Requester`, the `Reason*` constants and `humanapi.Intake` are used with the same names and types in every later task — and every test refers to a helper whose ordinal and file are named in the task that first needs it (`planFixture`, `classes`, `pubOf`, `fakeGateway`, `modelFor`, `req`, `replyWithIssueBody`, `okReply`, `slow`, `validBody`, `withIntake*`, `planArgs`, `e.intake`, `appFor`, `relay`, `fakeBroker`, `checked`, `PromptFor`, `SkillText`, and the Python gates' `load`/`docs`/`ports`/`tree`/`check`). `plan_check`'s result keys (`plan`, `hash`, `canStart`, `canStartWhy`) are the ones PR 3's `planShape` decodes and PR 4's `runCreateArgs` passes on. `startSponsored` joins `issuedraft.go`'s existing reason constants rather than being a bare string.

**Ambiguity closed.** Two config keys the spec's table does not list (`url`, `repositories`) are declared with their reason, and so is the hash's `ceilingMicroUSD` deviation from §plan's `ceilingUSD`. The ExternalSecret origin is decided (OpenBao `apps/planner`) and the rejected alternative — a namespaced `Password` generator, which cannot mint one value twice — is named; the gateway's Secret key is `planner` because that string *is* the client id the gateway forwards. `plan_check` exists as a second tool rather than a mode of `intake_plan`, so both schemas stay closed and the sponsored list still gains exactly one tool. `run_create`'s schema keeps every field required and validates the fields against the plan, so an App built before this change keeps working. The daily counter is keyed on the effective requester, with a test that two linked Slack users do not share it. A GitHub answer the broker cannot get is `repository_unverified`, a ninth refusal this plan adds to the spec's eight; a private candidate in a multi-repository ask is dropped rather than named, and a single explicitly named private repository is refused with its reason. The metric families are `intake_*` so `MakuName` serves the spec's `maku_intake_*`; `rooms_intake_*` would have been served as `maku_rooms_intake_*` and the dashboard would have queried nothing. The rollout order is three-ordered (remote value → release → keys) because two gates enforce it, and the broker's pin moves four files together because `app.yaml`'s own comment says so.

**Proportion.** Six PRs against a 776-line design; every code block is a signature, a fixture, a gate assertion or a manifest fragment, never an implementation body.

## Execution handoff

The owner has not chosen an execution method. Plan saved to `docs/superpowers/plans/2026-11-05-v3x-conversational-intake-maku-plan.md`. Ask for review before implementation.
