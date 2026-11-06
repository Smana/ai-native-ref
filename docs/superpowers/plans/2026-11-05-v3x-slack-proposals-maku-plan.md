# v3.x Slack proposals — Implementation Plan (Maku PRs 5–7, release, ai-native-ref PRs A–B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Slack mention produces **one** proposal message that is edited in place as the requester replies — the whole `plan/v1` plan, its hash, its author and its revision living in that message's metadata — with Confirm and Cancel controls, a ✅ fallback that files through the same `run_create` validation, and a thread that afterwards answers five fixed questions and posts one line per meaningful transition, never steering the run.

**Architecture:** Three Maku pull requests and one release, then two ai-native-ref pull requests (the declaration, its generator and the pin first; the switch-on, the reader's page and the live proof last, behind an owner go). PR 5 adds the proposal's *shape*: the message, its tagged metadata payload (`factory_proposal`), the Block Kit sections rendered by `internal/roomview` (the one place untrusted text is made inert), `chat.update` that carries the metadata, recovery from that metadata alone, and the ✅ path that files a proposal through `run_create`'s plan validation — all behind `proposals.enabled`, false by default, so nothing is visible. PR 6 adds the *flows*: a mention plans through `intake_plan`, a reply re-plans and updates that one message, and Confirm/Cancel ride the interactivity branch the approval design already dispatches inside `POST /slack/events` — no second handler, no second route, no second public path. PR 7 adds what comes *after* filing: the five-question vocabulary answered from the sponsored `room_summary`, `room_changes` and `needs_list`, the stop guidance that only prints the label, and the per-channel `notify` projection that makes a run start post nothing. ai-native-ref then declares the channel binding once (`tooling/base/agent-factory/slack-bindings.yaml`) and generates the App's `channels`, the factory's sponsored `repositories` and the broker's webhook `repositories` and `events` from it, deletes the overlay copy of the App's config, and pins the release before either generated key can reach a decoder that refuses it.

**Tech Stack:** Go 1.25 (Maku: `internal/slackapp` over the Slack Web API, `internal/roomview` renderers, `internal/humanapi`'s MCP tools, OpenTelemetry metrics), Slack Web API (`chat.postMessage`, `chat.update`, `chat.postEphemeral`, `conversations.replies`), Slack Block Kit messages and `block_actions` interactivity payloads, `task` as the runner on both sides, Python 3 + PyYAML for the ai-native-ref generator and its gate.

**Spec:** [the conversational developer experience design](../specs/2026-11-05-v3x-conversational-devex-design.md) — CD7, CD8, CD14, CD20, CD24, CD25, CD27, CD28, CD29, §plan's Slack bound, §the Slack journey, §Security and privacy, §Failure and refusal cases, §Switches, §Acceptance offline 5, 10, 11 and 16, §Acceptance live 6–12 — and the [Slack push-approval design](../specs/2026-11-05-v3x-slack-push-approval-design.md) for the three primitives this plan consumes and does not change (D9–D11, §5's tagged metadata, §6's one door). This plan implements the Slack half of CD7/CD8/CD20/CD24/CD25/CD29 and nothing else. It lives in ai-native-ref and is copied to Maku's `docs/superpowers/plans/` by the first PR that executes it. *`maku/…` in the spec is the Maku repository at `4685672f`.*

## Global Constraints

- **Repositories and branches.** Maku is `github.com/Smana/maku`; the review read `/tmp/opencode/maku-devex-read` at `4685672f0f40973286a121f83ea92dd3428b8120`, and every `internal/…:N` citation below is that commit. Set `MAKU` to the executor's checkout of `origin/main`; one worktree per PR: `git -C "$MAKU" worktree add "$MAKU-<topic>" -b <branch> origin/main`. Branches: `feat/slack-proposal-message` (PR 5), `feat/slack-proposal-flows` (PR 6), `feat/slack-thread-answers` (PR 7), then ai-native-ref `feat/slack-bindings` (PR A) and `feat/slack-proposals-switch-on` (PR B) in this repository. Rebase onto a freshly fetched `origin/main` before every push.
- **This plan lands after the three plans whose contracts it consumes, and it changes none of them.** In merge order: (1) the Slack push-approval plan's Maku PRs 1–4 and its release — tagged `Metadata.EventPayload`, `Slack.Update`/`PostCard`, the interactivity branch inside `POST /slack/events`, `room.approval_closed`, `channels.<id>.approvals`; (2) the conversational-intake plan's PRs 1–4 and its release — `plan/v1`, `intake.Hash`, `intake_plan`, `plan_check`, `run_create` with `plan`/`plan_hash`; (3) the attention-and-resume plan's Maku PRs 1–8 and its ai-native-ref PR 10 — `needs_list` on both tool lists, `webhook.Meaningful`/`webhook.Notify`, and `room.run_started` dropped from the live subscription. This plan reads those interfaces exactly as their **Interfaces** blocks state them and adds no field to any of them.
- **The evidence.** Maku: `task check` exits 0 and `task lint` reports 0 issues; the store's suites need a Docker daemon and envtest assets, which `task test` sets up (`go tool setup-envtest use -p path 1.36.x`), and no task here touches the store, the CRDs or the chart. ai-native-ref: `task check` exits 0 — it builds `.composite/`, runs the host's `validate-manifests.sh`, this repository's gates, its suites (`scripts/ci/run-tests.sh` globs `git ls-files 'scripts/ci/tests/*'`, so `git add` a new suite before running it), the link check, the site build, the doc-path check (a path naming a host file resolves against `.host/`) and the source check — and `task docs` exits 0. Never claim done without that output.
- **Conventions.** Maku: `// SPDX-License-Identifier: Apache-2.0` on every `.go` file; a doc comment on every exported symbol naming the decision it implements (`CD7`, `CD20`, `CD25`); a "no" fails towards a human with its own code; one interface per consumer. Commits are conventional, in English, with no trailers. PR titles and descriptions in English.
- **The metadata is the whole of the proposal (CD20).** `Message.Metadata` carries `{event_type: "factory_proposal", event_payload: {plan, hash, author, rev}}`. Nothing is stored: the App re-reads the message after a restart, after an edit, and on every Confirm. **No code path anywhere parses the rendered mrkdwn to recover a plan, and no code path re-composes a plan from raw text.** A message whose metadata is absent, whose `event_type` differs, or whose `intake.Hash(plan) != hash` is **not** a proposal and is treated exactly as today's foreign message is.
- **Verbatim bounds and values from the spec.**
  - One issue in Slack: a plan with more than one issue is refused with a pointer to the coding agent or the web UI (CD19), never trimmed.
  - The plan's canonical JSON ≤ 7 KiB, so the metadata stays under `maxMetadata` (8 KiB, `app.go:33`); an oversized plan is refused whole with that pointer and nothing is filed from rendered text (§plan).
  - The message's revision cap: `maxProposalRevisions = 40`; over it the thread says to confirm or start a new mention. The broker's `human.intake.plan.dailyPlans` is the second bound.
  - The request text ≤ 16 KiB and the reply context ≤ 4 KiB, the bounds `intake_plan`'s schema already carries. The 16 KiB is measured on the planner input — the mention's text with the bot's `<@…>` removed and trimmed — not on the HTTP body Slack posts, which the verifier already caps at 1 MiB; a longer request is refused with its own line before the broker is called.
  - Action ids: `factory_proposal_confirm`, `factory_proposal_cancel`. Button value: `v1|proposal|sha256:<64 lowercase hex>|<rev>`, ≤ 2 000 characters by construction.
  - Interactivity: `application/x-www-form-urlencoded` with exactly one `payload` field, payload ≤ 64 KiB, answered 200 within Slack's 3 s, work done under `handleTimeout` (30 s); the signature is checked over the raw body first (±5 min, 1 MiB) by the approval design's branch, unchanged. **The common checks stop at the shape of the click** — a `v1|` prefix on the value, the team, the user and channel ids, one message ts, and an `action_id` in the union of the two families' ids. Which family a click belongs to, and what its value means, is decoded inside that family's own case: the approval case parses `v1|approval|forge.push|…`, the proposal case parses `parseProposalValue`'s four parts. A value the click's own family cannot parse is that family's refusal, never the dispatcher's.
  - Data class is `public` alone (`internal/humanapi/runcreate.go:32`): a private repository is refused `private_repository_unsupported` before any model call, and the refusal line points at the coding agent.
  - Switches: the App's `proposals: {enabled: true|false}` (default **false**) and `channels.<id>.notify` (absent ⇒ `webhook.Notify()`, the nine a person is told about). Both decoders refuse an unknown key, so a key never lands ahead of the release that reads it.
  - Metrics (served names): `maku_slack_proposal_updates_total{action}` with `action ∈ mention | reply | confirm | cancel | repost`, and `maku_slack_thread_answers_total{question}` with `question ∈ status | needs | changes | pr | stop | unknown`. **The OTel instrument names already carry `_total`** — `slack_proposal_updates_total` and `slack_thread_answers_total` — because this exporter adds no suffix of its own; `MakuName` serves a `slack_` family as `maku_slack_*`, so the served name and the registered name differ by the prefix alone. The spec's `maku_slack_thread_answer_total` is served plural because the counter's label is a set of questions, and both names are pinned by `TestProposalCounterName`.
  - ai-native-ref: one declaration, `tooling/base/agent-factory/slack-bindings.yaml`; `maxCostUSD` ≥ 0.01 and ≤ the sponsored principal's ceiling; every declared repository must be one the factory's `config.repositories` names; every `notify` entry must be one of the thirteen webhook types.
- **One public door (CD29).** No task adds a route, an `HTTPRoute` match, a listener, a host-contract version or a `HOST_REF` bump. `POST /slack/events` stays the only public path, and the proposal's controls are dispatched from the branch the approval design already wrote there.
- **No steering, ever.** Ordinary replies never reach the run: the App's sponsored token holds no steering, approval or stop tool, and the answers read only `room_summary`, `room_changes` and `needs_list`. A stop request prints the `factory/stop` label and the room link; nothing stops the run.
- **Out of scope, and no task may add it:** the planner, `intake_plan`'s internals, `plan/v1`'s shape, `needs/v1`'s derivation, the approval decide route or its cards, approving or merging from Slack, multi-repository coordination, private-repository planning, code search, a free-form chat engine, repository selection by menu, a modal, a slash command, a DM, and any implementation of the fast-follow pack.
- **Owner gates.** No live cluster action — merging the switch-on PR (Task B1), the Slack console change, or any proof in Task B3 — happens before the owner's explicit go. Tasks 1–A5 are offline.

## Review Focus

The five input classes and failure modes this design implies but no test in the spec exercises. Each line's test is added to the task that owns the code, in that task's own step style.

1. **A proposal the App cannot rewrite in place** — Slack refuses `chat.update` (an edit window, a metadata shape it rejects, a deleted message). The person must never be left with buttons that bind a hash the metadata no longer holds, and never with two live proposals. Owning tasks: Maku PR 5 Task 4 (the repost fallback and the inert old message) and PR 6 Task 3 (the button value checked against the metadata before filing).
2. **Two replies that arrive inside one re-plan.** The thread must end with one message carrying one plan and one revision, never an interleaved pair, and the losing word must not silently disappear. Owning task: Maku PR 6 Task 2.
3. **A channel re-pointed between the mention and the Confirm.** CD24 makes the channel's repository list a generated value, so it *will* change under a live proposal. A Confirm must be refused, not filed against a channel that no longer serves the plan's repository. Owning task: Maku PR 6 Task 3.
4. **A thread whose marker line is missing, or whose room id no longer holds** (a forwarded thread, a deleted message, a room pruned after 30 days). The answers must say the room is unknown, never guess a room from the issue number or the channel. Owning task: Maku PR 7 Task 1.
5. **A generated file hand-edited in the same commit as its declaration** so the value looks right in review. The gate must fail on the *rendering*, not on "the file moved". Owning task: ai-native-ref Task A3.

---

## File structure

| File | Responsibility | PR |
|---|---|---|
| `internal/slackapp/config.go` | `Proposals{Enabled}`, `Channel.Notify`, `Channel.notifies` | 5 |
| `internal/roomview/proposal.go` (new) | The proposal's sections in Slack mrkdwn: the plan's untrusted text, escaped once, and the changed marks | 5 |
| `internal/roomview/doc.go`, `card.go` | `Slack` as a `Format`, and the four escapers it needs | 5 |
| `internal/slackapp/slack.go` | `UpdateProposal` (chat.update with metadata), `proposalPayload()`, `markerPayload()` | 5 |
| `internal/slackapp/proposal.go` (new) | The payload, its value, the materiality table, the sections→blocks mapping, post/update/recover, `fileProposal` | 5, 6 |
| `internal/slackapp/broker.go` | `RunCreate.Plan`/`.PlanHash`, `IntakePlan`, `RoomSummary`, `RoomChanges`, `NeedsList` | 5, 6, 7 |
| `internal/slackapp/app.go` | `mention`/`reply` branch to the proposal flow; `file` dispatches a proposal; `deliver` filters by `notify` | 5, 6, 7 |
| `internal/slackapp/proposalaction.go` (new) | Confirm and Cancel, called from the approval design's one dispatcher | 6 |
| `internal/slackapp/answers.go` (new) | The five-question vocabulary and its answers, from the three sponsored reads | 7 |
| `internal/metrics/metrics.go` | `SlackProposalUpdates`, `SlackThreadAnswers`, `MakuName`'s `slack_` case | 6, 7 |
| `internal/app/slackapp.go` | `App.Proposals` from the config; `slackRecorder.ProposalUpdate` and `.ThreadAnswer` | 5, 6, 7 |
| `internal/slackapp/config_test.go`, `proposal_test.go`, `testdata/plan/*.json` (new), `proposalaction_test.go`, `answers_test.go`, `slack_test.go`, `app_test.go` | The offline proofs 5, 10, 11, on this package's own fixtures | 5, 6, 7 |
| Maku `docs/slack.md` | The flow, the controls, the vocabulary, the two switches, the manifest | 7 |
| ai-native-ref `tooling/base/agent-factory/slack-bindings.yaml` (new) | The one declaration of the workspace and its channels (CD24) | A |
| ai-native-ref `scripts/ci/gen-slack-bindings.py` (new) | The three consumers, rendered from the declaration, drift is a failure | A |
| ai-native-ref `scripts/ci/tests/test-gen-slack-bindings.py` (new), `scripts/ci/tests/slack-bindings-fixtures/` (new) | Proof 16: byte-for-byte, drift, and an unserved repository | A |
| ai-native-ref `tooling/base/agent-factory/slack-app/config.yaml` | `teamID` and `channels` are generated regions; the rest stays hand-kept | A, B |
| ai-native-ref `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml` | `api.sponsored[slack-app].repositories` is a generated region | A |
| ai-native-ref `infrastructure/gcp-0/room-broker/config.yaml` | `webhooks[slack-app].repositories` and `.events` are generated regions | A |
| ai-native-ref `tooling/base/agent-factory/helm-values-configmap.yaml` | The Maku release pin | A |
| ai-native-ref `tooling/gcp-0/agent-factory/slack-app/{config.yaml,kustomization.yaml}` | The overlay copy goes; the render is base's generated ConfigMap | A |
| ai-native-ref `scripts/ci/tests/test-factory-slack-switchon.py` | The gate that read the deleted copy, re-pointed at the declaration | A |
| ai-native-ref `docs/runbooks/agent-factory/22-slack.md`, `18-factory-interfaces.md` | The operator's one declaration, and the switch-on's file list | A, B |
| ai-native-ref `website/content/docs/use/slack.md`, `status.md` | The reader's page and the capability's row | B |
| ai-native-ref `docs/runbooks/agent-factory/results-*.md` (new) | The live proof's transcript | B |

---

## Maku PR 5 — `feat/slack-proposal-message`: the message, its metadata, its one renderer

Nothing in this PR is visible: `proposals.enabled` defaults false and no flow calls the new code yet. Its evidence is offline proof 5 (the metadata invariant) and the beginning of 10.

### Task 1: the switch, and the channel's notify list

**Files:**
- Modify: `internal/slackapp/config.go` (`Config`, `Channel`, `Channel.validate`'s loop), `internal/app/slackapp.go` (`App.Proposals` from the decoded config)
- Test: `internal/slackapp/config_test.go`

**Interfaces:**
- Consumes: `webhook.Types()`, `webhook.Notify()` (attention plan PR 8).
- Produces: `type Proposals struct{ Enabled bool \`json:"enabled,omitempty"\` }`; `Config.Proposals Proposals \`json:"proposals,omitempty"\``; `Channel.Notify []string \`json:"notify,omitempty"\``; `func (c Channel) notifies(t string) bool`; and on the App, `App.Proposals Proposals`, wired from `cfg.Proposals` in `internal/app/slackapp.go:261` beside `Channels: cfg.Channels`.

- [ ] **Step 1: Write the failing test**

```go
// CD11 and CD24: proposals are off unless the deployment says otherwise, and a channel's notify
// list is which transitions post a line there. Absent means webhook.Notify() (the nine); an
// explicit empty list means none, which is a choice, not an omission.
func TestLoadProposalsAndNotify(t *testing.T)
```

Assertions, exactly: a config with no `proposals` key loads with `Proposals.Enabled == false`; `proposals: {enabled: true}` decodes true; `proposals: true` and `proposals: {on: true}` both fail to decode (the strict decoder's error); a channel with no `notify` has `notifies("room.task_triaged") == true` and `notifies("room.run_started") == false`; `notify: [room.waiting_for_human, room.approval_closed]` answers true for those two and false for `room.merged`; `notify: []` answers false for every type; `notify: [nope]` fails with an error naming `nope` and the channel id; `notify: [room.waiting_for_human, room.waiting_for_human]` fails as a duplicate.

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/slackapp/ -run TestLoadProposalsAndNotify -count=1`
Expected: FAIL at compile (`c.Proposals undefined`).

- [ ] **Step 3: The two keys**

```go
// Proposals is the proposal message's switch (CD7): off, a mention drafts as it does today.
type Proposals struct {
	Enabled bool `json:"enabled,omitempty"`
}

// Channel is a channel the App serves: the repositories a mention there may name, the max_cost a
// confirmation there sends, whether approvals are drawn as cards, and which webhook transitions
// post a line (CD11, CD24 — declared once in ai-native-ref's slack-bindings.yaml).
type Channel struct {
	Repositories []string `json:"repositories"`
	MaxCostUSD   float64  `json:"maxCostUSD"`
	Approvals    bool     `json:"approvals,omitempty"`
	Notify       []string `json:"notify,omitempty"`
}
```

`notifies` returns `slices.Contains(c.Notify, t)` when `c.Notify != nil` and `slices.Contains(webhook.Notify(), t)` when it is nil — nil and empty must not be conflated, so validate reads the decoded slice, not a length. In `validate`, per channel: every `notify` entry must be in `webhook.Types()`; a duplicate is an error. No other change to `validate`.

- [ ] **Step 4: Run the package, then the linter**

Run: `go test ./internal/slackapp/ -count=1 && task lint`
Expected: PASS, 0 issues.

- [ ] **Step 5: Commit**

```bash
git -C "$MAKU" add internal/slackapp/config.go internal/slackapp/config_test.go
git -C "$MAKU" commit -m "feat(slackapp): proposals and notify, the two keys the proposal flow reads"
```

### Task 2: `roomview.Proposal`, the one renderer of a plan's text

**Files:**
- Create: `internal/roomview/proposal.go`, `internal/roomview/proposal_test.go`
- Modify: `internal/roomview/doc.go` (the `Slack` format), `internal/roomview/card.go` (`bold`, `url`, `text`, `quoted` gain the Slack branch)

**Interfaces:**
- Consumes: the package's own escapers (`strip`, `clean`, `code`), `Options`.
- Produces: `const Slack Format = iota + 3` (after `TextColor`); `type ProposalView struct{ Repository string; Evidence []ProposalEvidence; Alternatives []ProposalAlternative; Question *ProposalQuestion; Issue ProposalIssue; Budget ProposalBudget; Hash string; Rev int; Author string; Degraded bool; Confirm bool; Changed []string }`; `type ProposalEvidence struct{ Text, URL string }`; `type ProposalAlternative struct{ Repository, Why string }`; `type ProposalQuestion struct{ Text, Answer, Why string }`; `type ProposalIssue struct{ Title, Class string; Roles []string; DependsOn []int; What, Should, Acceptance, RawBody string }`; `type ProposalBudget struct{ CeilingUSD float64; Source string }`; `type ProposalSection struct{ Key, Heading, Body string; Changed bool }`; `func Proposal(p ProposalView, o Options) ([]ProposalSection, error)`.

`roomview` declares these plain structs rather than importing `internal/intake`: the consumer owns the shape (`intake.Plan` never enters the view package), and `slackapp` maps one onto the other in Task 3.

- [ ] **Step 1: Write the failing test**

```go
// CD13 and FA10/FA11: the plan's text is data. A title or body carrying links, Markdown, ANSI,
// bidi or a code fence yields no link, heading, table or escape in the rendering, and every URL
// in it is one the broker built.
func TestProposalRendersUntrustedTextInert(t *testing.T)

// CD14 and CD27: a section whose hashed content changed is marked, and only those; the header says
// a new confirmation is required exactly when Confirm is set.
func TestProposalMarksTheChangedSections(t *testing.T)
```

`TestProposalRendersUntrustedTextInert` cases, each a `ProposalView` with one hostile value: title `docs: [x](https://evil.example) <!channel>`, body `## What is wrong\n<script>alert(1)</script>`, evidence text `[click](https://evil.example)`, alternative why `\ansi\x1b[31m`, question text with `\u202e` and a `|` table pipe, roles `["implementer", "<!--"]`. Assertions for each: the section's body contains no `](http` outside the `<…|…>` form, no `<!channel>`, no `\x1b`, no `\u202e`, no line starting `#` or `|`, and every `<` either opens Slack's own link form the renderer built (`<https://rooms.example/…|…>`) or is the escaped `&lt;`. `TestProposalMarksTheChangedSections`: with `Changed: []string{"repository","budget"}`, exactly the `repository` and `budget` sections carry `Changed == true` and their heading ends ` ‹changed›`; with `Confirm: true` the `header` section's body ends `requires a new confirmation`; with `Changed` nil no section is marked and the header omits the phrase.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/roomview/ -run 'TestProposalRendersUntrustedTextInert|TestProposalMarksTheChangedSections' -count=1`
Expected: FAIL at compile (`Proposal` undefined).

- [ ] **Step 3: The format, the escapers, the sections**

In `doc.go`:

```go
// The formats a view comes in: Markdown for an agent's chat, Text for a pipe, TextColor for a
// terminal, and Slack for the one view Slack reads (CD7): Slack's mrkdwn, where bold is *x*,
// a link is <url|text>, and three characters are escaped.
const (
	Markdown Format = iota
	Text
	TextColor
	Slack
)
```

`card.md()` keeps returning `o.Format == Markdown`. `bold(s)` returns `"*"+s+"*"` when `!c.md()` and the format is `Slack`, `"**"+s+"**"` for Markdown, and `s` otherwise; `url(text, u)` returns `<u|text>` for Slack; `text`/`quoted` escape `&`, `<`, `>` (and replace ```` ``` ```` with `'''`) for Slack exactly as `slackapp.slackText` does today, so the two cannot disagree about which characters are inert.

`Proposal` returns the sections in this order and with these keys: `header` (no heading; body `Proposal v{n} · sha256:… · by <@{author}>` plus, when `Degraded`, `template draft: the plan service is unavailable`, plus, when `Confirm`, `requires a new confirmation`), `repository` (heading `Repository`; the repository, then at most 5 evidence lines, then each alternative as `also serves this channel: {repo} — {why}`), `issue` (heading `Issue`; `{title}`, then the three labelled parts from `What`/`Should`/`Acceptance`, or `RawBody` in a code span when `What` is empty, then `class {class}` and `depends on #1, #2` when set), `roles` (heading `Roles`; the roles in order, comma-separated, and `one issue` for Slack's subset), `budget` (heading `Ceiling`; `${ceiling} ({source})`), `question` (only when `p.Question != nil`; heading `One question`; the text, then `Recommended: {answer} — {why}`), `controls` (heading `Editing`; the fixed sentence naming `Edit issues` as a reply, the ✅ fallback, and the untouched plan). Every string goes through `clean` (untrusted) or `strip` (the broker's own words); numbers use `strconv`.

- [ ] **Step 4: Run the package, then the linter**

Run: `go test ./internal/roomview/ -count=1 && task lint`
Expected: PASS. The existing card, changes and needs goldens are unchanged: no caller passes `Format: Slack` yet.

- [ ] **Step 5: Commit**

```go
git -C "$MAKU" add internal/roomview
git -C "$MAKU" commit -m "feat(roomview): the proposal's sections, in Slack mrkdwn, escaped once"
```

### Task 3: the proposal's metadata, its value, and the materiality table

**Files:**
- Create: `internal/slackapp/proposal.go`, `internal/slackapp/proposal_test.go`, `internal/slackapp/testdata/plan/slack-one-issue.json`
- Modify: `internal/slackapp/slack.go` (`Metadata.proposalPayload()`, `Metadata.markerPayload()`, `MarkerPayload`)

**Interfaces:**
- Consumes: `intake.Plan`, `intake.Hash(p Plan) string`, `intake.Material(p Plan) ([]byte, error)`, `p.JSON() ([]byte, error)`, `intake.Question` (intake plan PR 1); `roomview.Proposal`, `roomview.ProposalView` (Task 2).
- Produces: `const proposalEventType = "factory_proposal"`, `maxProposalPlanBytes = 7 << 10`, `maxProposalRevisions = 40`, `actionProposalConfirm = "factory_proposal_confirm"`, `actionProposalCancel = "factory_proposal_cancel"`; `type ProposalPayload struct{ Plan intake.Plan \`json:"plan"\`; Hash string \`json:"hash"\`; Author string \`json:"author"\`; Rev int \`json:"rev"\` }`; `func (m *Metadata) proposalPayload() (ProposalPayload, bool)`; `type MarkerPayload struct{ Repo string \`json:"repo"\`; Room string \`json:"room,omitempty"\` }`; `func (m *Metadata) markerPayload() (MarkerPayload, bool)`; `func newProposal(p intake.Plan, hash, author string, rev int) (ProposalPayload, error)`; `func proposalHashHolds(p ProposalPayload) bool`; `func proposalValue(hash string, rev int) string`; `func parseProposalValue(v string) (string, int, bool)`; `func proposalChanged(prev, next ProposalPayload) []string`; `func proposalSections(p ProposalPayload, q *intake.Question, changed []string) (text string, blocks json.RawMessage, err error)`; `var errProposalTooLarge`.

- [ ] **Step 1: Write the failing tests**

```go
// CD20: the metadata is the whole proposal. It round-trips unchanged, and a payload whose hash does
// not hold — because a byte of the plan moved — is not a proposal.
func TestProposalMetadataRoundTrip(t *testing.T)

// §plan's Slack bound: a plan whose canonical JSON exceeds 7 KiB is refused, never truncated, so
// the metadata stays under maxMetadata.
func TestProposalTooLargeIsRefused(t *testing.T)

// CD7: a confirmation binds the version it showed. The button's value carries the hash and the
// revision; a value with anything else, or a hash of the wrong shape, binds nothing.
func TestProposalValueBindsTheHash(t *testing.T)

// CD14/CD27: materiality is exactly the hashed set. Each single hashed field moves its own section
// and no other; evidence, an alternative, the question's wording and the revision move none.
func TestProposalChangedFollowsTheMaterialTable(t *testing.T)

// One message, no parse of rendered text: the sections and their blocks come from the payload, and
// the text is the same sections joined, which is what Slack shows in a notification.
func TestProposalSectionsAndBlocks(t *testing.T)
```

`internal/slackapp/testdata/plan/slack-one-issue.json` is **this package's own** fixture, not the human API's test helper (which is unexported in another package's tests and must not be reached): one issue, `repository: Smana/ai-native-ref`, `budget: {"ceilingUSD": 1.5, "source": "channel:C1.maxCostUSD"}`, `planner: {"model": "tier-frontier", "surface": "slack", "at": …}`, `rev: 1`, no `question`, **no** `hash` key. `planFixture(t, name)` in `proposal_test.go` decodes it from `testdata/plan/<name>.json`; it is the only fixture this package reads, and its bytes match the intake plan's `slack-one-issue.json` because both describe the same plan.

`TestProposalMetadataRoundTrip`: `newProposal(planFixture(t, "slack-one-issue"), intake.Hash(plan), "U07JY4EQNDN", 1)` marshals under `maxMetadata`; decoding the marshalled `Metadata` yields `proposalPayload()` with `Plan` `reflect.DeepEqual` to the fixture, `Hash` equal, `Author`, `Rev`; `proposalHashHolds` true; then `p.Plan.Issues[0].Body += "\n"` in a copy leaves `Hash` untouched and `proposalHashHolds` false; `event_type: "factory_draft"` carrying a proposal payload yields `proposalPayload()` false; `event_payload` the JSON string `"nope"` yields false.

`TestProposalChangedFollowsTheMaterialTable` compares **the material set's own bytes** (`intake.Material`), never a displayed float: a table of mutations to `next` and the expected key sets — `Repository` → `{"repository"}`; `Budget.CeilingUSD` → `{"budget"}`; `Budget.Source` → `{"budget"}`; a ceiling that differs only by a display rounding (1.5 vs 1.5000001, if the plan's canonical form admits it) → `{"budget"}` too, because the comparison is on the material bytes and not on the two floats; `Issues[0].Title` → `{"issue"}`; `Issues[0].Body` → `{"issue"}`; `Issues[0].Class` → `{"issue"}`; `Issues[0].Roles` → `{"roles"}`; `Issues[0].DependsOn` → `{"roles"}`; a second issue appended → `{"issue","roles"}`; `Rev++` → empty; `RepositoryEvidence` changed → empty; `Alternatives` changed → empty; `Question.Text` changed → empty. And `Confirm` is `len(proposalChanged(prev, next)) > 0`.

`TestProposalSectionsAndBlocks`: `proposalSections` returns a `text` and `blocks`; decoded, the blocks are one `header` block whose text is `Proposal v1`, one `section` block per remaining section whose `text.text` is that section's heading and body, one `actions` block with exactly two `button` elements (`factory_proposal_confirm`, style `primary`; `factory_proposal_cancel`, style `danger`), and one `context` block holding the channel mention; the `text` equals the sections' headings and bodies joined by newlines; both buttons' `value` is `proposalValue(p.Hash, p.Rev)`; the total JSON stays under `maxSlackReply` for a plan whose canonical JSON fills the 7 KiB bound (the largest a message can carry — Slack allows 50 blocks and 3 000 characters per section; the renderer's sections are seven, so a plan at the bound is comfortably inside).

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestProposal' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The payload, the value, the table, the blocks**

`proposalPayload` decodes strictly (`json.Unmarshal` into the struct, then `proposalHashHolds`), and returns false when `EventType != proposalEventType` — the shape `draftPayload()` already has. `markerPayload` decodes a `filedEventType` message into `MarkerPayload`; today's Filed lines carry `{"repo":…}` and decode with an empty `Room`, which is why the type's second field is optional.

`newProposal` marshals `p` once: when `len(raw) > maxProposalPlanBytes` it returns the error `errProposalTooLarge`, whose text is the one line the thread shows ("the plan is too long for Slack; use your coding agent or the web UI"). `proposalHashHolds` compares `intake.Hash(p.Plan)` with `p.Hash` and checks the hash's shape `^sha256:[0-9a-f]{64}$`.

`proposalValue` is `"v1|proposal|" + hash + "|" + strconv.Itoa(rev)`; `parseProposalValue` splits on `|` into exactly four parts, requires `v1`, `proposal`, the hash's shape and a revision `1..maxProposalRevisions`.

`proposalChanged` returns keys from the fixed list `repository`, `issue`, `roles`, `budget`, and its input is **`intake.Material`'s canonical bytes**, not the display struct: it unmarshals `intake.Material(prev.Plan)` and `intake.Material(next.Plan)` into one private projection (repository; budget as its raw JSON members; each issue's index, title, body, class; each issue's roles and dependsOn, in array order) and compares those groups member by member. Two plans whose displayed `ceilingUSD` renders the same but whose material bytes differ therefore still mark `budget`, and a float comparison over the display value — the bug this avoids — cannot make a material change look like no change. `apiVersion` is part of the hash and is constant in one thread, so it marks nothing; a change there is refused earlier by `intake.Check`.

`proposalSections` maps `ProposalPayload` + `intake.Question` + the changed keys onto `roomview.ProposalView` (`What`/`Should`/`Acceptance` split by the package's existing `parseBody`, `RawBody` when it does not split), calls `roomview.Proposal` with `Format: Slack`, and builds the Block Kit JSON: `{"blocks":[…]}` where the section whose `Key` is `header` becomes a `{"type":"header","text":{"type":"plain_text","text":"Proposal v{n}"}}` block (its body's `sha256:…`, author mention and any `requires a new confirmation` follow in the next block), every other section becomes `{"type":"section","text":{"type":"mrkdwn","text":"*Heading*\nBody"}}`, then one `actions` block (`{"type":"actions","elements":[{"type":"button","text":{…},"action_id":actionProposalConfirm,"value":v,"style":"primary"},{"type":"button",…,"action_id":actionProposalCancel,"value":v,"style":"danger"}]}` with `v := proposalValue(p.Hash, p.Rev)` for both), and one `context` block naming the channel (`{"type":"context","elements":[{"type":"mrkdwn","text":"<#{channel}>"}]}`) — a proposal has no room yet, so it links none. The returned `text` is every section's heading and body joined by newlines: it is the message's fallback text, and it is never parsed back.

- [ ] **Step 4: Run them**

Run: `go test ./internal/slackapp/ -run 'TestProposal' -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```go
git -C "$MAKU" add internal/slackapp/slack.go internal/slackapp/proposal.go internal/slackapp/proposal_test.go
git -C "$MAKU" commit -m "feat(slackapp): a proposal's metadata, its bound value and its material table"
```

### Task 4: post it once, edit it in place, and find it again after a restart

**Files:**
- Modify: `internal/slackapp/slack.go` (`Slack` interface, `SlackClient.UpdateProposal`, `slackAnswer` untouched)
- Modify: `internal/slackapp/proposal.go` (`postProposal`, `updateProposal`, `threadProposal`)
- Test: `internal/slackapp/slack_test.go` (`TestUpdateProposalWire`), `internal/slackapp/proposal_test.go` (`TestOneProposalMessageAcrossRevisions`, `TestProposalRecoveredFromMetadataAlone`), `internal/slackapp/app_test.go` (`fakeSlack` gains `UpdateProposal`)

**Interfaces:**
- Consumes: `Slack.Update` and `Slack.PostCard` (approval plan PR 3), `Metadata.proposalPayload` (Task 3).
- Produces, on the `Slack` interface: `UpdateProposal(ctx context.Context, channel, ts, text string, blocks json.RawMessage, meta *Metadata) error`. In `proposal.go`: `func (a *App) postProposal(ctx context.Context, channel, thread string, p ProposalPayload, q *intake.Question) string`; `func (a *App) updateProposal(ctx context.Context, channel, ts string, prev, next ProposalPayload, q *intake.Question) string`; `func (a *App) threadProposal(msgs []Message) (latest *Message, closed bool)`.

- [ ] **Step 1: Write the failing tests**

```go
// CD7: forty revisions are one message. The thread ends with one ts, four chat.update calls, and
// the last message's metadata carrying the last plan.
func TestOneProposalMessageAcrossRevisions(t *testing.T)

// CD20 and acceptance 5: an App built from nothing — no memory of the thread — recovers the same
// plan and hash from the message's metadata, and a message whose metadata is absent or whose hash
// does not hold is not a proposal.
func TestProposalRecoveredFromMetadataAlone(t *testing.T)

// chat.update carries the metadata, so an edit never reposts and a restart never re-reads text.
func TestUpdateProposalWire(t *testing.T)
```

`TestOneProposalMessageAcrossRevisions`: post a proposal at `rev 1` in a fake thread, then call `updateProposal` four times with `rev 2..5`; assertions: the fake saw one `PostCard` and four `UpdateProposal` calls; every update names the same `ts`; `payload(fake.messages[ts])` decodes to the last plan and `Rev == 5`; `threadProposal` returns that one message and `closed == false`. Then seed an `UpdateProposal` failure (`fake.failProposalUpdates = 1`) on a sixth update: the App posts a new proposal (`PostCard` count 2), the old message is passed to `Update` with no blocks, and `threadProposal` returns the **newest** message — one live proposal, the older one inert (Review Focus 1).

`TestProposalRecoveredFromMetadataAlone`: build a second `App` from the fake's message slice alone (`a2 := &App{Slack: fake, BotUserID: "UBOT"}`), call `a2.threadProposal(fake.thread())` and assert `latest.Metadata.EventType == proposalEventType`, `intake.Hash(payload.Plan) == payload.Hash`, and the same plan as the first App read. Then: a message with `event_type: factory_proposal` and a payload whose `hash` is a hash of a different plan → `latest == nil`; a message whose `metadata` is nil → `latest == nil`; a `factory_proposal` message plus a `factory_filed` marker → `closed == true`.

`TestUpdateProposalWire`: against an `httptest.Server`, `UpdateProposal(ctx, "C03", "1729.0001", "text", blocks, meta)` posts to `/chat.update` with `{"channel":"C03","ts":"1729.0001","text":"text","blocks":[…],"metadata":{…},"unfurl_links":false,"unfurl_media":false}`, sends `Authorization: Bearer <Token()>`, and returns an error whose text is Slack's code (`invalid_metadata`) and never the token.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestOneProposalMessage|TestProposalRecovered|TestUpdateProposalWire' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The call, the post, the update, the recovery**

`UpdateProposal` is `chat.update` plus `"metadata": meta` (and `blocks` only when `len(blocks) > 0`), through `c.do`, exactly as `Post` builds its body. `fakeSlack` gains `UpdateProposal` recording into a new `proposalUpdates []update` slice, replacing the seeded message's metadata, with a `failProposalUpdates int` counter.

`postProposal` refuses first: `newProposal`'s `errProposalTooLarge` posts the one pointer line and returns `"too_large"`; a plan with more than one issue posts "this plan covers N issues and Slack files one: use your coding agent or the web UI" and returns `"multi_issue"`. Otherwise it posts with `PostCard` (thread reply), logs nothing about the plan's text, and returns `"proposed"`.

`updateProposal` calls `UpdateProposal` on the same `ts`; on error it logs `proposal update failed` with the channel and ts, counts `repost`, posts a fresh proposal with `postProposal` (new ts, the same payload), and makes the old message inert with `Update(ctx, channel, oldTS, "This proposal was replaced below.", nil)` — best effort, its failure logged and counted, never retried into a loop (D10's rule, applied here).

`threadProposal` scans like `threadDraft` (`app.go:513`): the bot's own messages only; `proposalPayload()` true **and** `proposalHashHolds` → the newest such message is `latest`; a `filedEventType` message (`markerPayload()` true) → `closed = true`. Nothing else counts.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/slackapp/ -count=1`
Expected: PASS, `TestMetadataShapes`, `TestReactionFlow` and `TestReplyAddsTheAcceptanceCheck` included: the draft path did not notice.

- [ ] **Step 5: Commit**

```go
git -C "$MAKU" add internal/slackapp
git -C "$MAKU" commit -m "feat(slackapp): one proposal message, edited in place, recoverable from its metadata"
```

### Task 5: the ✅ fallback files a proposal through `run_create`

**Files:**
- Modify: `internal/slackapp/broker.go` (`RunCreate` gains `Plan`/`PlanHash`; `Broker.RunCreate` sends them)
- Modify: `internal/slackapp/app.go` (`file` dispatches a proposal; `notFiled` gains `plan_changed`)
- Modify: `internal/slackapp/proposal.go` (`fileProposal`, `filedText`)
- Test: `internal/slackapp/app_test.go` (`TestReactionFlow` unchanged; new `TestCheckMarkFilesAProposal`), `internal/slackapp/broker_test.go` (`TestRunCreateSendsThePlan`)

**Interfaces:**
- Consumes: `run_create`'s `plan`/`plan_hash` (intake plan PR 4), `intake.Plan.JSON()`.
- Produces: `RunCreate.Plan json.RawMessage`, `RunCreate.PlanHash string`; `func (a *App) fileProposal(ctx context.Context, channel, thread, itemTS, user string, p ProposalPayload, confirm bool) string` (`confirm` is true for a button press and false for the ✅ fallback: the only thing it changes is the one refusal line's verb, and it is what makes the two paths one code path); `func (a *App) filedText(res RunResult, user string) string` (today's Filed line, one builder for the ✅ and the Confirm — a method because the room URL comes from `a.RoomsURL`, as `file` builds it today at `app.go:725`); `notFiled`'s new `case code == "plan_changed":`.

- [ ] **Step 1: Write the failing tests**

```go
// CD8's fallback and acceptance 10's last row: a ✅ on a proposal files it through the same
// run_create validation the Confirm uses, and the proposal message becomes the Filed line in place.
func TestCheckMarkFilesAProposal(t *testing.T)

// The draft path sends exactly today's arguments; a proposal adds the plan and its hash and nothing
// else changes.
func TestRunCreateSendsThePlan(t *testing.T)
```

`TestCheckMarkFilesAProposal`: seed a proposal (hash holding) and post ✅ as the linked maintainer; assertions: the fake broker saw one `RunCreate` whose `Plan` decodes to the fixture and whose `PlanHash` is `intake.Hash(fixture)`; the proposal message was `UpdateProposal`d with `event_type: factory_filed` and a `MarkerPayload{Room: "26zfnuxm"}`, no buttons, and the text `Filed #2238 for <@U2>…`; a second ✅ answers `Already filed` and calls `RunCreate` again (idempotent, the store's duplicate); a ✅ on a proposal whose `hash` does not hold refuses with `Not filed: this proposal no longer matches its check…` and calls nothing; **a ✅ on a proposal whose thread already closed it is `ignored`** — no line, no broker call, outcome `"ignored"`, exactly as today's ✅ on a message that is not the App's draft (the message itself already says `Proposal cancelled by <@U>` or carries the Filed line, so a second line would be noise); a broker refusal `rejected: plan_changed` renders `Not filed: the plan changed after this was drawn…`.

`TestRunCreateSendsThePlan`: the draft call's argument map is byte-for-byte today's (`run_create` args have no `plan`/`plan_hash` keys); a call with `Plan` set adds exactly `plan` (the object) and `plan_hash` (the string).

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestCheckMarkFilesAProposal|TestRunCreateSendsThePlan' -count=1`
Expected: FAIL.

- [ ] **Step 3: The dispatch and the filing**

In `file` (`app.go:630`), right after the `msg.Metadata` read, branch on the payload before the draft checks:

```go
	if p, ok := m.proposalPayload(); ok {
		return a.fileProposal(ctx, channel, thread, itemTS, user, p, false) // the ✅ fallback
	}
```

`fileProposal` repeats the checks the draft path makes and adds the proposal's own, in this order: the channel is served; `intake.Hash(p.Plan) == p.Hash` (else refuse `hash` with "this proposal no longer matches its check; mention me again"); the plan's repository is in the channel's `Repositories` (else refuse `repository`, the existing line); `threadProposal(msgs)` says the thread is not `closed` (else return `"ignored"` with no line and no broker call) and `latest.TS == itemTS` (else refuse `replaced`, the existing line); then one `a.Broker.RunCreate(RunCreate{Draft: Draft{Repo: p.Plan.Repository, Title: p.Plan.Issues[0].Title, Body: p.Plan.Issues[0].Body}, Plan: raw, PlanHash: p.Hash, MaxCostUSD: ch.MaxCostUSD, OnBehalfOf: "slack:" + a.TeamID + "/" + user, Ref: "slack/" + a.TeamID + "/" + channel + "/" + thread, Key: a.TeamID + "/" + channel + "/" + thread})`, where `raw` is `p.Plan.JSON()`.

On success: `a.Threads.Put(ctx, res.Room, Thread{Channel: channel, TS: thread, At: a.now()})` (unchanged), then rewrite the proposal message in place with `UpdateProposal(channel, itemTS, a.filedText(res, user), nil, &marked)` where `marked` is `Metadata{EventType: filedEventType, EventPayload: json.Marshal(MarkerPayload{Repo: p.Plan.Repository, Room: res.Room})}`; a marshal error, or a failed rewrite, falls back to `sayMeta(line, marked)` (today's separate Filed line) and is counted. `filedText` is today's Filed line as a method — it reads `a.RoomsURL` the way `file` does today — so the ✅ and the Confirm say the same thing. A duplicate answers `Already filed: <url>` and rewrites the message the same way.

`notFiled` gains one case: `plan_changed` → `"Not filed: the plan changed after this was drawn; mention me again to re-plan it."`

- [ ] **Step 4: Run the package, then the gate**

Run: `go test ./internal/slackapp/ -count=1 && task check`
Expected: PASS, exit 0.

- [ ] **Step 5: Commit, push, open PR 5**

```bash
git -C "$MAKU" add internal/slackapp
git -C "$MAKU" commit -m "feat(slackapp): a check mark files a proposal through run_create's plan check"
git -C "$MAKU" fetch origin && git -C "$MAKU" rebase origin/main && git -C "$MAKU" push -u origin feat/slack-proposal-message
gh pr create --repo Smana/maku --head feat/slack-proposal-message \
  --title "feat(slackapp): the proposal message, its metadata and its one renderer" \
  --body "CD7/CD20's shape, invisible behind proposals.enabled: the whole plan, its hash, its author and its revision live in the message's metadata and are the only place a plan is ever read from; chat.update carries that metadata so forty revisions are one message; a failed update reposts and makes the old message inert; a ✅ files a proposal through run_create's plan validation and rewrites the message into the Filed line. The draft path's wire bytes and behaviour are unchanged (TestMetadataShapes, TestReactionFlow). Evidence: task check exit 0, task lint 0 issues."
```

---

## Maku PR 6 — `feat/slack-proposal-flows`: the mention, the reply, Confirm and Cancel

PR 6 makes the message reachable. Everything stays behind `proposals.enabled`; with the switch off, `TestReactionFlow`, `TestReplyKinds` and every other draft test still describe the deployed behaviour.

### Task 1: a mention plans, and posts one proposal

**Files:**
- Modify: `internal/slackapp/app.go` (`mention` branches before `ParseMention`), `internal/slackapp/broker.go` (`IntakePlan`)
- Modify: `internal/slackapp/proposal.go` (`propose`, `notProposed`)
- Test: `internal/slackapp/app_test.go` (`TestMentionProposes`, `TestProposalRefusals`), `internal/slackapp/broker_test.go` (`TestIntakePlanCall`)

**Interfaces:**
- Consumes: `intake_plan`'s schema and its result `data {plan, hash, question, canStart, canStartWhy, degraded}` (intake plan PR 2).
- Produces: on `BrokerAPI`: `IntakePlan(ctx context.Context, in IntakeRequest) (IntakeResult, error)`, with `type IntakeRequest struct{ Text, Context, OnBehalfOf string; Candidates []string; CeilingUSD float64 }` and `type IntakeResult struct{ Plan intake.Plan; Hash string; Question *intake.Question; CanStart bool; CanStartWhy string; Degraded bool }`; `func (a *App) propose(ctx context.Context, ev slackEvent, ch Channel, thread, text string, rev int) string`; `func commandless(text, bot string) string`; `var RequestedTextTooLong` (its text is the one line `Not proposed: that request is longer than 16 KB; hand it off from your coding agent or the web UI.`); `func notProposed(refusal, user string) (code, text string, passing bool)`.

- [ ] **Step 1: Write the failing tests**

```go
// CD1 and the Slack journey: with proposals on, a mention in plain words is planned by the broker
// and posted as one proposal — the App no longer parses a repository line.
func TestMentionProposes(t *testing.T)

// The refusals a person actually meets, one fixed line each, and the one that names where to go
// instead (a private repository, a model that is down, a plan too large, more than one issue).
func TestProposalRefusals(t *testing.T)

// The call is intake_plan's schema exactly: the requester's words, the channel's repositories as the
// candidate set, the App's principal, and the channel's ceiling.
func TestIntakePlanCall(t *testing.T)
```

`TestMentionProposes`: `withProposals(t)` and a fake planner answering the `slack-one-issue` fixture; a mention `@factory the install link in the README is dead` in a served channel yields exactly one `PostCard` in the mention's thread, whose metadata is a `ProposalPayload` with `Rev == 1`, `Author` the mentioner, and whose blocks carry the fixture's repository and title; the fake broker's `intake_plan` arguments are `text` = the mention without the bot mention, `candidates` = the channel's repositories, `on_behalf_of` = `slack:T…/U…`, `ceiling` = the channel's `maxCostUSD`, and **no** `repository` key; with the switch off, the same mention posts today's draft and calls `issue_draft` (the existing `TestSingleLineMentionPostsTheComposedDraft`, unchanged).

`TestProposalRefusals`, each a fake planner answer or error and its exact thread line: `rejected: repository_not_allowed` → `Not proposed: this channel serves {a, b} and you may file in none of them; ask an operator…`; `rejected: no_write` → names the repositories the person can file in; `rejected: private_repository_unsupported` → `Not proposed: the planner reads public repositories only; use your coding agent (\`issue_draft\` then \`issue_file\`)…`; `rejected: planner_unavailable` → `Not proposed: the plan service is unavailable; mention me again in a minute.`; `rejected: planner_timeout`, `planner_invalid`, `daily_plans_reached` → their own one-liners; `ErrUnknownTool` → `This deployment does not plan from Slack yet; mention me in the old grammar.`; a plan with two issues → the multi-issue line; a plan over 7 KiB → the too-large line; a resulting `Degraded: true` → the proposal posts and its header carries `template draft: the plan service is unavailable`.

`TestIntakePlanCall`: the JSON-RPC arguments are exactly `{"text","candidates","on_behalf_of","ceiling"}` (a `context` key only when the App passes one), and a `structuredContent` shaped like the tool's answer decodes into `IntakeResult`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestMentionProposes|TestProposalRefusals|TestIntakePlanCall' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The branch, the call, the lines**

In `mention`, after the `link`/`unlink` commands and before `ParseMention`:

```go
	if a.Proposals.Enabled {
		return a.propose(ctx, ev, ch, thread, commandless(ev.Text, a.BotUserID), 1)
	}
```

`propose` refuses a request whose planner input — `commandless(ev.Text, a.BotUserID)`, the mention's text with the bot's `<@…>` removed and trimmed, **not** the HTTP body the verifier already capped at 1 MiB — is over 16 KiB, with `RequestedTextTooLong`'s one line; and a thread whose proposal is already `closed` (one line naming the room, since the idempotency key is the thread). It then builds the `IntakeRequest` and calls `a.Broker.IntakePlan`. `commandless` is the small helper in `proposal.go`: the one place a mention becomes the planner's input, and therefore the one place the 16 KiB bound is measured. `notProposed` maps the broker's `rejected:` codes to the fixed lines above — `repository_not_allowed`, `no_write`, `private_repository_unsupported`, `planner_unavailable`, `planner_timeout`, `planner_invalid`, `daily_plans_reached` — and passes anything it does not know through `shown(refusal)`.

`Broker.IntakePlan` is one `b.call(ctx, "intake_plan", …)` with exactly the four keys, decoding `data` into `IntakeResult`; `ErrUnknownTool` propagates untouched, so an older broker answers the one line rather than a draft.

- [ ] **Step 4: Run them**

Run: `go test ./internal/slackapp/ -run 'TestMentionProposes|TestProposalRefusals|TestIntakePlanCall' -count=1 && go test ./internal/slackapp/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```go
git -C "$MAKU" add internal/slackapp
git -C "$MAKU" commit -m "feat(slackapp): a mention plans through the broker and posts one proposal"
```

### Task 2: a reply re-plans and updates that one message

**Files:**
- Modify: `internal/slackapp/app.go` (`reply` branches to the proposal flow before the draft path)
- Modify: `internal/slackapp/proposal.go` (`replan`)
- Test: `internal/slackapp/app_test.go` (`TestReplyReplansInPlace`, `TestReplySerialised`, `TestReplyBounds`)

**Interfaces:**
- Consumes: `a.editMu` (`app.go:87`), `updateProposal` (Task 4 of PR 5), `IntakePlan` (Task 1).
- Produces: `func (a *App) replan(ctx context.Context, ev slackEvent, ch Channel, thread string, latest *Message, p ProposalPayload) string`; `func followUps(msgs []Message, thread, bot, author string, budget int) string`.

- [ ] **Step 1: Write the failing tests**

```go
// CD7 and CD14: five replies are one message with the changed sections marked, and the header says
// when a new confirmation is required.
func TestReplyReplansInPlace(t *testing.T)

// Review Focus 2: two replies inside one re-plan serialise on the App's edit lock; the thread ends
// with one message carrying the last plan and revision N+2, and neither word is lost from the
// planner's context.
func TestReplySerialised(t *testing.T)

// CD14's bound, and the draft rule the thread already has: over maxProposalRevisions the thread says
// to confirm; only the proposal's author's replies are read as edits, and a closed thread is never
// edited.
func TestReplyBounds(t *testing.T)
```

`TestReplyReplansInPlace`: a proposal at `rev 1`, then the author replies `it belongs in owner/docs` with a fake planner that answers a plan whose repository moved; assertions: one `UpdateProposal` call on the proposal's `ts`, none new posted; the new metadata's `Rev == 2`; the `repository` section is marked `‹changed›` and its heading carries it; the header carries `requires a new confirmation`; `intake.Hash(next) != intake.Hash(prev)`; the planner saw `text` = the thread's parent mention and `context` containing the reply.

`TestReplySerialised`: a fake planner that blocks on a channel until released; two replies posted concurrently; assert two `intake_plan` calls, two `UpdateProposal` calls on the same `ts` in revision order (`Rev == 2` then `Rev == 3`), the last metadata holding plan 3, and the second call's `context` containing **both** replies (the App reads the thread again under the lock).

`TestReplyBounds`: at `Rev == maxProposalRevisions` the reply answers `This proposal was planned the most it can be here: confirm it, or start a new mention.` and calls no planner; a reply from someone other than `p.Author` before filing returns `"ignored"` and calls no planner; a reply in a thread whose marker closed it returns `"ignored"`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestReplyReplans|TestReplySerialised|TestReplyBounds' -count=1`
Expected: FAIL.

- [ ] **Step 3: The re-plan**

In `reply`, after the channel/shape checks and after `threadProposal` finds a proposal, branch before the draft path: when `a.Proposals.Enabled` and a proposal exists, take `a.editMu`, re-read the thread inside the lock, and call `replan`. `replan` builds `IntakeRequest{Text: parent text, Context: followUps(...), OnBehalfOf: "slack:" + a.TeamID + "/" + ev.User, Candidates: ch.Repositories, CeilingUSD: ch.MaxCostUSD}` and calls `updateProposal(channel, latest.TS, p, next, question)` with `Rev: p.Rev + 1`. `followUps` collects the human messages after the parent in order (`Reply 1: …`), keeps the most recent that fit 4 KiB, and never includes the bot's own text.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/slackapp/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```go
git -C "$MAKU" add internal/slackapp
git -C "$MAKU" commit -m "feat(slackapp): a reply re-plans the proposal and updates one message"
```

### Task 3: Confirm and Cancel on the one interactivity branch

**Files:**
- Create: `internal/slackapp/proposalaction.go`, `internal/slackapp/proposalaction_test.go`
- Modify: `internal/slackapp/app.go` (`handleInteraction`'s dispatch: the common checks narrowed to the click's shape, each family's value parsed inside its own case)
- Test: `internal/slackapp/proposalaction_test.go` (`TestProposalConfirm`, `TestProposalConfirmRefusals`, `TestProposalCancel`, `TestProposalInteractionDispatch`), plus the approval design's `TestSlackInteractivitySignature`, `TestInteractivityShape` and `TestInteractivityBusyRetries`, re-run unchanged

**Interfaces:**
- Consumes: the approval design's `handleInteraction`/`parseInteraction`/`interaction` and its dedup key (its Task 13), `fileProposal(..., confirm bool)` (PR 5 Task 5), `proposalValue`/`parseProposalValue` (PR 5 Task 3).
- Produces: `func (a *App) proposalAction(ctx context.Context, in interaction) string`; `func proposalDedupKey(in interaction) string`; and the narrowed common check: `actionID` accepted from `{actionApprove, actionDeny, actionProposalConfirm, actionProposalCancel}` with the value's `v1|` prefix only.

- [ ] **Step 1: Write the failing tests**

```go
// CD7 and the live proof's row 9: a maintainer's Confirm files the plan the metadata holds and turns
// the message into the Filed line; the hash in the button must equal the hash in the metadata.
func TestProposalConfirm(t *testing.T)

// One line per refusal, no oracle about people or repositories, and every one of them an ephemeral
// to the presser: a stale value, a non-maintainer, a message whose metadata no longer holds, a
// channel that no longer serves the plan's repository. No refusal posts a second thread message.
func TestProposalConfirmRefusals(t *testing.T)

// Cancel is the author's and nobody else's, and a cancelled proposal cannot be filed afterwards.
func TestProposalCancel(t *testing.T)

// One dispatcher, two families: a proposal action never reaches the approval path, an approval
// action never reaches this one, and an unknown action id is dropped as it is today.
func TestProposalInteractionDispatch(t *testing.T)
```

`TestProposalConfirm`: a proposal from the author, a click by a linked maintainer with `value = proposalValue(metadata.Hash, 1)`; assertions: one `RunCreate` with the plan; the message `UpdateProposal`d to the Filed line with `filedEventType` and `MarkerPayload{Room}`; a second click (deduped) answers 200 and calls nothing; a click with a value whose hash differs from the metadata's → `Not filed: the plan changed after this was drawn…`, no `RunCreate`, and the message is re-rendered from the **metadata** (one `UpdateProposal`, no planner call).

`TestProposalConfirmRefusals`, each one `chat.postEphemeral` to the presser in the thread and no thread `Post` (the only `UpdateProposal` among them is the `plan_changed` re-render asserted above): a click the broker refuses `not_a_maintainer` → `Not filed: <@U>'s GitHub account is not a maintainer of {repo}; a maintainer must confirm it.` (the proposal's own verb — `notFiled`'s draft line says "a maintainer must react", which is the ✅'s wording, so `fileProposal`'s `confirm` flag swaps that one verb; the line goes to the presser alone, never to the thread); a click on a message whose `metadata` is gone → `Not filed: this proposal can no longer be read; mention me again.`; a channel whose `Repositories` no longer contains the plan's repository (Review Focus 3) → `Not filed: {repo} isn't served in this channel any more; ask an operator.`, no `RunCreate`; a value `parseProposalValue` refuses → `Not filed: this proposal's button no longer matches it; open the message again.`; a press in a channel whose `proposals` are off (the switch flipped under a live message) → the ✅ teaching line and no broker call.

`TestProposalCancel`: a click by `p.Author` → the message `UpdateProposal`d to `Proposal cancelled by <@U>; mention me again to plan another.` with a `filedEventType` marker and no blocks; a later ✅ on it is `ignored` — no line, no broker call (PR 5 Task 5's rule); a click by anyone else → `Only <@A> cancels this proposal; a maintainer confirms it.` and the message keeps its buttons.

`TestProposalInteractionDispatch`: `factory_proposal_confirm` in a channel with `approvals: false` reaches `proposalAction` (the card branch's flag must not gate it); `factory_approval_approve` in a channel with `proposals: {enabled: true}` reaches the approval path and not `proposalAction`; `factory_unknown` answers `ignored`, no broker call, no message. Then the split itself, which is what this task changed: a `factory_proposal_confirm` carrying an approval-shaped value (`v1|forge.push|<id>|<branch>`) is **the proposal family's** refusal — one ephemeral line, no `RunCreate`, outcome `refused`, never `ignored` — and a `factory_approval_approve` carrying a proposal-shaped value (`v1|proposal|sha256:…|1`) answers exactly what the approval design's own case answers for a value it cannot parse (its closed code's line, per its `TestInteractivityShape`), never `proposalAction`'s line and never a `RunCreate`: the common block no longer reads a value's class.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestProposalConfirm|TestProposalCancel|TestProposalInteractionDispatch' -count=1`
Expected: FAIL.

- [ ] **Step 3: The dispatcher's second family**

The approval design's branch parses one `v1|forge.push|<approvalId>|<branch>` value in its common checks, and that is what this task changes: **the common checks keep only the click's shape** — the value's `v1|` prefix, `team.id`, `user.id`, `channel.id`, one message ts (`container.message_ts`, else `message.ts`) and an `action_id` in the union `{actionApprove, actionDeny, actionProposalConfirm, actionProposalCancel}` — and **each family decodes its own value inside its own case**. The approval case's `v1|approval|forge.push|…` parse, its `class != forge.push` refusal and its `ch.Approvals` check move out of the common block into the approval case; the proposal case parses `parseProposalValue`. A value one family cannot parse is that family's refusal, never a silent drop by the dispatcher.

```go
	switch in.actionID {
	case actionApprove, actionDeny:
		// The approval design's case: its own ch.Approvals check, its own value parse and class
		// refusal, its broker call, its answer line and its teardown. Only the place it reads
		// `ch.Approvals` and its value moves — behaviour is identical, which its own interactivity
		// tests re-prove below.
	case actionProposalConfirm, actionProposalCancel:
		a.proposalAction(ctx, in) // CD7's controls: a different family, the same door
	default:
		return "ignored"
	}
```

`proposalAction` re-checks `a.Proposals.Enabled` (a channel with the switch flipped answers the ✅ teaching line locally, no broker call), reads the message with `Slack.Message`, decodes `proposalPayload()`, parses the button's value with `parseProposalValue` (a value it cannot parse is `Not filed: this proposal's button no longer matches it; open the message again.`, one line to the presser) and compares the parsed hash with `p.Hash`; then calls `fileProposal` (confirm) or rewrites the message to its cancelled form (cancel). It answers the presser with `chat.postEphemeral` in the thread, as the card branch does, and never dials a URL from the body. The dedup key is `proposalDedupKey(in)` = `"i|" + in.actionID + "/" + in.userID + "/" + in.actionTS + "/" + in.messageTS`, stable across Slack's retries of one interaction and distinct from the card's key.

Because this task edits the shared parser, it also re-runs the approval design's suites — `TestSlackInteractivitySignature`, `TestInteractivityShape` (its value-class cases now belong to the approval case and must still answer `ignored`/the card's line exactly as they did) and `TestInteractivityBusyRetries` — and says so in the PR body.

- [ ] **Step 4: Run the package, then the gate**

Run: `go test ./internal/slackapp/ -count=1 && task check`
Expected: PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git -C "$MAKU" add internal/slackapp
git -C "$MAKU" commit -m "feat(slackapp): Confirm and Cancel ride the one interactivity branch"
```

### Task 4: the counter, and PR 6

**Files:**
- Modify: `internal/metrics/metrics.go` (`MakuName`'s `slack_` case, `Set.SlackProposalUpdates`, `Set.ProposalUpdate`), `internal/metrics/metrics_test.go`
- Modify: `internal/slackapp/app.go` (`Recorder` gains `ProposalUpdate`; the App calls it at five outcomes), `internal/app/slackapp.go` (the wiring: `rec` already satisfies `Recorder`)
- Test: `internal/metrics/metrics_test.go` (`TestProposalCounterName`), `internal/slackapp/app_test.go` (`TestProposalActionsCounted`; the rig's `fakeRecorder` gains the method)

**Interfaces:**
- Consumes: `metrics.Set` (the broker's instruments), the App's existing `Recorder` port (`app.go:62`).
- Produces: `metrics.Set.SlackProposalUpdates metric.Int64Counter` (OTel name **`slack_proposal_updates_total`** — the exporter adds no `_total` of its own), `metrics.Set.ProposalUpdate(ctx context.Context, action string)`, and `MakuName`'s `case strings.HasPrefix(name, "slack_"): return "maku_" + name`; in `slackapp`, `Recorder` grows one method: `ProposalUpdate(ctx context.Context, action string)`, and the concrete `slackRecorder` in `internal/app/slackapp.go:267` gains `ProposalUpdate` forwarding to the instrument (the reason `internal/app/slackapp.go` is in this task's Files).

- [ ] **Step 1: Write the failing tests**

```go
// CD7's evidence: every action the proposal message takes is counted, under the name the dashboard
// reads, and a `factory_slack_*` family keeps its own name (MakuName must not catch it).
func TestProposalCounterName(t *testing.T)

// One count per action, and none on a path that answered nothing.
func TestProposalActionsCounted(t *testing.T)
```

`TestProposalCounterName`: `MakuName("slack_proposal_updates_total") == "maku_slack_proposal_updates_total"`, `MakuName("slack_thread_answers_total") == "maku_slack_thread_answers_total"`, `MakuName("factory_slack_requests_total") == ""`, and the spec's names are the served ones (the assertion quotes both strings, so a rename breaks it).

`TestProposalActionsCounted`: a mention counts `mention`; a reply counts `reply`; a Confirm counts `confirm`; a Cancel counts `cancel`; a failed `UpdateProposal` counts `repost` as well as `reply`; a refused plan counts nothing but `mention`.

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/metrics/ -run TestProposalCounterName -count=1 && go test ./internal/slackapp/ -run TestProposalActionsCounted -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The instrument and the five call sites**

The instrument is created beside the others with the name that is served minus the prefix — `Int64Counter("slack_proposal_updates_total", …)`, description naming CD7 — because this exporter appends nothing; `MakuName` then makes the series `maku_slack_proposal_updates_total`. `ProposalUpdate` refuses nothing: the label is the caller's closed set (`mention`, `reply`, `confirm`, `cancel`, `repost`). The App keeps one metrics port — the existing `Recorder` — so no new field on `App`; `slackRecorder` gains the forwarding method, and the call sites are the five returns that end a proposal action, each with the rig's fake recording the label.

- [ ] **Step 4: Run the packages, then the gate**

Run: `go test ./internal/metrics/ ./internal/slackapp/ -count=1 && task check`
Expected: PASS, exit 0.

- [ ] **Step 5: Commit, push, open PR 6**

```bash
git -C "$MAKU" add internal/metrics internal/slackapp internal/app
git -C "$MAKU" commit -m "feat(metrics): maku_slack_proposal_updates_total, one label per action"
git -C "$MAKU" fetch origin && git -C "$MAKU" rebase origin/main && git -C "$MAKU" push -u origin feat/slack-proposal-flows
gh pr create --repo Smana/maku --head feat/slack-proposal-flows \
  --title "feat(slackapp): the proposal's flows — a mention plans, a reply edits, a maintainer confirms" \
  --body "CD7/CD8/CD14/CD29 with proposals.enabled on: a mention calls intake_plan and posts one proposal; a reply re-plans under the App's edit lock and updates that message with the changed sections marked and 'requires a new confirmation' when a hashed field moved; Confirm files through the same run_create validation as the ✅ fallback and rewrites the message into the Filed line; Cancel is the author's and closes the proposal. Both controls are dispatched from the approval design's existing interactivity branch — no second handler, no second route — and maku_slack_proposal_updates_total{action} counts each. Evidence: task check exit 0, task lint 0 issues."
```

---

## Maku PR 7 — `feat/slack-thread-answers`: the five questions, the stop, and the projection

### Task 1: the question vocabulary, and the three reads behind it

**Files:**
- Create: `internal/slackapp/answers.go`, `internal/slackapp/answers_test.go`
- Modify: `internal/slackapp/app.go` (`reply` answers after a filed proposal; `Recorder` gains `ThreadAnswer`), `internal/slackapp/broker.go` (`RoomSummary`, `RoomChanges`, `NeedsList`), `internal/metrics/metrics.go` (`SlackThreadAnswers`, `Set.ThreadAnswer`), `internal/app/slackapp.go` (`slackRecorder.ThreadAnswer`, the wiring `Recorder` needs before the App can count a question)

**Interfaces:**
- Consumes: the sponsored tools `room_summary` (`summary/v1` `structuredContent`), `room_changes` (`roomview.ChangeSet`), `needs_list` (`needs/v1` envelope with `items []summary.Need`) — attention plan PR 3 and PR 1; each need's `Action` as the spec's `{kind, label, url}`; `MarkerPayload.Room` (PR 5 Task 3).
- Produces: `type Question string` with `QuestionStatus | QuestionNeeds | QuestionChanges | QuestionPR | QuestionStop | QuestionUnknown`; `func questionOf(text string) Question`; `func (a *App) answer(ctx context.Context, ev slackEvent, thread, room string) string`; on `BrokerAPI`: `RoomSummary(ctx context.Context, room string) (summary.Summary, error)`, `RoomChanges(ctx context.Context, room string) (roomview.ChangeSet, error)`, `NeedsList(ctx context.Context, room string) ([]summary.Need, error)`; on `Recorder`: `ThreadAnswer(ctx context.Context, question string)`, implemented by `slackRecorder`; `metrics.Set.SlackThreadAnswers` (OTel name **`slack_thread_answers_total`**, no suffix added by the exporter), `Set.ThreadAnswer(ctx context.Context, question string)`.

- [ ] **Step 1: Write the failing tests**

```go
// CD25: five questions and nothing else. Each known phrase answers from the room and never from the
// thread's text; each unknown phrase gets one line saying where it acts; a stop request only prints
// the label and the link.
func TestThreadQuestionVocabulary(t *testing.T)

// CD8 and CD25's security row: an answer carries no agent text as an instruction, and every value it
// quotes is escaped. A hostile issue title and a hostile milestone text change no link and no mark.
func TestThreadAnswersAreInert(t *testing.T)

// Review Focus 4: a marker with no room, or a room the broker cannot read, answers that the room is
// unknown — never a guess from the issue number.
func TestThreadAnswerUnknownRoom(t *testing.T)
```

`TestThreadQuestionVocabulary`, each phrase → its answer's anchor: `status`, `Status?`, `how is it going` → the line naming the phase and the room link; `needs me`, `what needs me` → one line per need with its action's label and URL, or `Nothing waits on this task right now.`; `what changed` → at most ten milestone lines and `More: the room page`; `the pull request`, `pr` → the PR number and its URL, or `No pull request yet in this room.`; `stop`, `stop it` → `I can't stop a run from here. Apply the \`factory/stop\` label on the issue, or use Stop on the room page: <url>` and **no** broker call at all; `please fix the tests` → `Progress is in this thread; approvals and steering are on the room page: <url>. Ask \`status\`, \`needs me\`, \`what changed\` or \`the pull request\`.`; and each answer's counter label (`status`, `needs`, `changes`, `pr`, `stop`, `unknown`).

`TestThreadAnswersAreInert`: a summary whose issue title is `docs: [x](https://evil.example) <!channel>` and a milestone whose `Text` is `\x1b[31m` with a `|` → the answer contains no `<https://evil.example|`, no `<!channel>`, no `\x1b`, and every `<` it does contain opens `<{roomsURL}/r/…|` the App built.

`TestThreadAnswerUnknownRoom`: a thread whose marker carries `Room: ""` → `I can't tell which room this thread filed; open the room page from the Filed line above.`; a room the broker answers `errLogUnreadable` for → `The room could not be read just now; try again in a minute.`

- [ ] **Step 2: Run them to see them fail**

Run: `go test ./internal/slackapp/ -run 'TestThreadQuestion|TestThreadAnswers|TestThreadAnswerUnknownRoom' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: The matcher, the three calls, the five answers**

`questionOf` lowercases, trims, strips trailing `?`, `.` and `!`, collapses whitespace, and matches a closed map of phrases (`status`, `how is it going`, `how's it going`, `where is it`, `what's the status`, `needs me`, `what needs me`, `what changed`, `what has changed`, `the pull request`, `pr`, `the pr`, `stop`, `stop it`, `how do i stop it`); anything else is `QuestionUnknown`. `answer` reads the room from the thread's marker (`markerPayload()`), refuses when it is empty, then makes exactly one sponsored call for the question's kind and renders with `slackText` on every value and `<url|label>` only for URLs the broker built (`summary.Need.Action.URL`, `summary.Summary.URL`, `roomview.Milestone.URL`) or the App built from `a.RoomsURL` and the room id. The stop answer makes **no** call: its label sentence and its room link come from `a.RoomsURL` alone. Every answer is at most 12 lines; a longer one is cut at the tenth line with `…`.

`Broker.RoomSummary`/`RoomChanges`/`NeedsList` are one `b.call` each, decoding `structuredContent` into the tool's own type; the needs envelope decodes into `struct{ Items []summary.Need }`.

- [ ] **Step 4: Run the package**

Run: `go test ./internal/slackapp/ -count=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```go
git -C "$MAKU" add internal/slackapp internal/metrics internal/app
git -C "$MAKU" commit -m "feat(slackapp): the thread answers five questions, and the stop only says how"
```

### Task 2: the meaningful projection — a run start posts nothing

**Files:**
- Modify: `internal/slackapp/app.go` (`deliver` filters by the channel's `notify`)
- Test: `internal/slackapp/app_test.go` (`TestNotifyProjection`)

**Interfaces:**
- Consumes: `Channel.notifies` (PR 5 Task 1), `webhook.Meaningful`/`webhook.Notify` (attention plan PR 8).
- Produces: no new symbol; `deliver` returns `"ignored"` for a transition its channel does not list, and `line()` keeps its `room.run_started` entry for another subscriber.

- [ ] **Step 1: Write the failing test**

```go
// CD11: a run starting is not news. A default channel posts nothing for room.run_started and does
// post for room.waiting_for_human; a channel that lists run_started posts "A run started."; a
// transition no channel lists is dropped, and the rendering table is untouched for a subscriber
// that asks for it.
func TestNotifyProjection(t *testing.T)
```

Cases: the default channel (no `notify`) + `room.run_started` → no `Post`, outcome `ignored`; + `room.waiting_for_human` → one line, outcome `posted`; a channel with `notify: [room.run_started]` + `room.run_started` → one line; + `room.merged` → no line; `a.line(room.run_started)` still returns `"A run started."` (the table is not what changed).

- [ ] **Step 2: Run it to see it fail**

Run: `go test ./internal/slackapp/ -run TestNotifyProjection -count=1`
Expected: FAIL (`room.run_started` posted).

- [ ] **Step 3: The filter**

In `deliver`, after the thread is found and before `Post`: `ch, ok := a.Channels[th.Channel]; if !ok || !ch.notifies(e.Type) { return "ignored" }`. A channel the config dropped is `ignored` too: a thread whose channel stopped being served posts nothing rather than guessing.

- [ ] **Step 4: Run the package, then the gate**

Run: `go test ./internal/slackapp/ -count=1 && task check`
Expected: PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git -C "$MAKU" add internal/slackapp
git -C "$MAKU" commit -m "feat(slackapp): a channel's notify list decides which transition posts a line"
```

### Task 3: the App's docs, and the release

**Files:**
- Modify: `docs/slack.md` (the flow, the controls, the vocabulary, the two switches, the manifest section, invariant 8's sentence)
- Test: `task check`, `task lint` (Maku has no site; the doc gate is the package's own)

**Interfaces:**
- Consumes: everything above.
- Produces: the release tag `vX.Y.Z` and its digest, which ai-native-ref PR A pins.

- [ ] **Step 1: Rewrite the App's flow in `docs/slack.md`**

Replace the "Flows" section's draft description with the proposal's, and add, in the document's own register: one proposal message per thread, updated in place, whose metadata carries the plan, its hash, its author and its revision and is the only place a plan is read from; the Confirm/Cancel controls and the ✅ fallback; a reply re-planning with the changed sections marked and `requires a new confirmation` when a hashed field moved; the five questions and the stop's label-only answer; `proposals.enabled` and `channels.<id>.notify`, with `room.run_started` out of the default list. Amend the manifest section: `interactivity: {is_enabled: true}` (the approval design's change) is what the controls need, and the Request URL is the same one path. Keep invariant 8 ("a thread reply is never a command") and add the sentence that says what a reply *is*: an edit before filing, one of five questions after, and never a way to steer a run. State the twelve-line bound and the token/label rule for the answers.

- [ ] **Step 2: Check the docs and the package**

Run: `task check && task lint`
Expected: exit 0, 0 issues.

- [ ] **Step 3: Commit, push, open PR 7**

```bash
git -C "$MAKU" add docs/slack.md
git -C "$MAKU" commit -m "docs(slack): the proposal message, the five questions and the two switches"
git -C "$MAKU" fetch origin && git -C "$MAKU" rebase origin/main && git -C "$MAKU" push -u origin feat/slack-thread-answers
gh pr create --repo Smana/maku --head feat/slack-thread-answers \
  --title "feat(slackapp): the thread answers five questions, and a run start says nothing" \
  --body "CD8 and CD25: after filing, a reply that matches one of five phrases is answered from the sponsored room_summary, room_changes or needs_list — never from the thread's text, never with a write, and the stop request only prints the factory/stop label and the room link. Anything else gets one line saying where it acts. channels.<id>.notify decides which webhook transitions post a line, so a run start posts nothing while the App's rendering table keeps its entry for another subscriber. maku_slack_thread_answers_total{question} counts the vocabulary, unknown included. Evidence: task check exit 0, task lint 0 issues."
```

- [ ] **Step 4: Tag the release**

```bash
git -C "$MAKU" tag vX.Y.Z && git -C "$MAKU" push origin vX.Y.Z
```

Record the release's digests from the published manifest list — the four images (the App's, the factory's, the broker's and its retention CronJob's) and the chart's — because PR A pins them all; the release is the first that reads `proposals` and `notify`, which is why no ai-native-ref config may carry either key before A's pin.

- [ ] **Step 5: Copy the plan into Maku**

```bash
mkdir -p "$MAKU/docs/superpowers/plans"
cp docs/superpowers/plans/2026-11-05-v3x-slack-proposals-maku-plan.md "$MAKU/docs/superpowers/plans/"
git -C "$MAKU" add docs/superpowers/plans && git -C "$MAKU" commit -m "docs(plans): the Slack proposals plan"
```

---

## ai-native-ref PR A — `feat/slack-bindings`: one declaration, three consumers, the pin

Offline and visible to nobody: the App's `proposals` stays absent, so nothing proposes. This PR lands **after** the three sibling plans' releases (it pins the release that carries them and reads `webhook.Notify`'s nine) and rebases over the attention plan's PR 10, whose hand edit of `webhooks[slack-app].events` this PR replaces with the declaration's rendering.

### Task A1: the declaration

**Files:**
- Create: `tooling/base/agent-factory/slack-bindings.yaml`

**Interfaces:**
- Produces: one file with `teamID` and `channels`, each channel `{repositories, maxCostUSD, notify}`; the generator (A2) is its only reader.

- [ ] **Step 1: Write the file**

```yaml
# The Slack workspace and the channels the factory's App serves (CD24): the one place a channel's
# binding is written. scripts/ci/gen-slack-bindings.py renders three consumers from it and fails on
# any difference — the App's `channels`, the factory's api.sponsored[slack-app].repositories, and
# the broker's webhooks[slack-app].repositories and .events. Edit here, run the generator with
# --write, commit both.
#
# OWNER-FILL: the team id and channel ids are the owner's; test-factory-slack-switchon.py refuses a
# marker while FACTORY_SLACK_LIVE=1.
teamID: T07J97G2K2P
channels:
  C0CC4M8SNVD:
    repositories: [Smana/cloud-native-ref, Smana/ai-native-ref]
    maxCostUSD: 2
    # CD11: a run starting is not news. The App's default is webhook.Notify(), the nine a person is
    # told about, and this list is what the broker subscribes to (the union across channels).
    notify: [room.task_triaged, room.waiting_for_human, room.pr_opened, room.verdict_posted,
             room.merged, room.reverted, room.budget_reached, room.ended, room.approval_closed]
```

- [ ] **Step 2: Check it parses as the shape the generator expects**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('tooling/base/agent-factory/slack-bindings.yaml')); assert set(d)=={'teamID','channels'} and all(set(c)>={'repositories','maxCostUSD','notify'} for c in d['channels'].values()), d"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add tooling/base/agent-factory/slack-bindings.yaml
git commit -m "feat(slack): one declaration of the workspace and its channels"
```

### Task A2: the generator

**Files:**
- Create: `scripts/ci/gen-slack-bindings.py`

**Interfaces:**
- Consumes: the declaration (A1), `tooling/base/agent-factory/slack-app/config.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` (the factory's `config.repositories`), `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml`, `infrastructure/gcp-0/room-broker/config.yaml`.
- Produces: `gen-slack-bindings.py [--write] [ROOT]` (exit 0 when the committed files are the rendering, 1 on drift or a bad declaration), and the module's `render(declaration, served, ceiling) -> {path: text}` plus the pure helpers `channels_block`, `notify_union`, `repositories_union`, `registries`, `splice`.

- [ ] **Step 1: Write the failing test first (A3), then the module**

The test in A3 is written before the module, run to see it fail (`ModuleNotFoundError`), and the module implements exactly what it asserts. Its rules, in the register of `gen-webhook-egress.py`'s docstring: the declaration's `teamID` replaces the App config's `teamID:` line whole; `channels:` is replaced whole by one line per channel, sorted by id, each `{repositories: […], maxCostUSD: …, notify: […]}`; the factory's sponsored `repositories` of the entry named `slack-app` is the sorted union of the channels' repositories; the broker's `webhooks[slack-app].repositories` is the same union and its `.events` is the union of the channels' `notify` in declaration order; every other byte of every file is preserved, and each splice is verified by re-parsing the file and comparing the decoded value with the rendering (gen-capabilities' "held" check). Failures: a channel id outside `^[CG][A-Z0-9]{2,20}$`; a `teamID` outside `^T[A-Z0-9]{2,20}$`; no channel; an empty `repositories`; a repository outside `^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$`; a repository the factory's `config.repositories` does not name (the declaration fails here, not in the cluster); `maxCostUSD < 0.01` or above the sponsored principal's `maxCostUSD`; a `notify` entry outside the thirteen `webhook.Types()` names; a duplicate entry; a `slack-app` entry missing from either consumer.

- [ ] **Step 2: Run it against the tree it must render**

Run: `python3 scripts/ci/gen-slack-bindings.py`
Expected: FAIL with a diff for each of the **three files** the declaration changes — the App's config, the sponsored values, the broker's config — and the message naming `--write`.

- [ ] **Step 3: Commit the module**

```bash
git add scripts/ci/gen-slack-bindings.py
git commit -m "feat(slack): a generator renders the channel binding's three consumers"
```

### Task A3: the gate — byte for byte, drift, and an unserved repository

**Files:**
- Create: `scripts/ci/tests/test-gen-slack-bindings.py`, `scripts/ci/tests/slack-bindings-fixtures/mini/{slack-bindings.yaml,slack-app-config.yaml,helm-values-sponsored.yaml,room-broker-config.yaml,helm-values-configmap.yaml}`

**Interfaces:**
- Consumes: the module (A2) through `importlib.util` as `test-gen-webhook-egress.py` loads its own (`ROOT = pathlib.Path(__file__).resolve().parents[3]`), and `main` for the drift case.
- Produces: offline proof 16 as three assertions, run by `scripts/ci/run-tests.sh`.

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
# requires: python3
"""gen-slack-bindings: one declaration, three consumers, and drift is a gate failure (CD24, proof 16)."""
```

```python
# Proof 16, first half: one declaration renders the App's channels, the factory's sponsored
# repositories and the broker's webhook repositories byte for byte.
def check_one_declaration_renders_three_consumers():
    ...

# Review Focus 5: a generated file edited by hand in the same commit as its declaration fails on the
# rendering, not on "the file moved".
def check_hand_editing_a_generated_region_fails():
    ...

# Proof 16, last clause: a channel naming a repository the factory does not serve fails at the
# declaration, before any cluster sees it.
def check_an_unserved_repository_fails_at_the_declaration():
    ...
```

Assertions, exactly: with the real `ROOT`, `gen.render(...)` returns **exactly three paths** — `tooling/base/agent-factory/slack-app/config.yaml`, `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` — and each rendering equals `pathlib.Path(root/p).read_text()`, and `gen.main(["gen-slack-bindings.py", str(ROOT)]) == 0`; running `--write` twice on the fixture tree leaves every file byte-identical the second time (idempotence: the second render is a no-op, which is what makes the drift gate meaningful); a copy of the five fixture files into `tempfile.mkdtemp()` where one byte of the App config's `channels:` line is changed yields `main([...]) == 1` and stderr naming that path; the same tree with the declaration's `repositories` extended by `acme/unserved` yields `main([...]) == 1` with `acme/unserved` in stderr and the words `config.repositories`.

- [ ] **Step 2: Run it to see it fail**

Run: `python3 scripts/ci/tests/test-gen-slack-bindings.py`
Expected: FAIL (`ModuleNotFoundError: gen-slack-bindings`, before A2's module exists; a traceback naming the missing assertion after).

- [ ] **Step 3: The fixtures**

`slack-bindings-fixtures/mini/` holds a five-file tree small enough to read: a declaration with one channel serving `acme/shop`, an App config whose `teamID: ""` and `channels: {}` are the base's shape today, a sponsored values ConfigMap with `repositories: [acme/shop]` and `maxCostUSD: 2`, a broker config with `webhooks: [{name: slack-app, …, repositories: [acme/shop], events: [...]}]`, and a factory values ConfigMap naming `acme/shop` under `config.repositories`. `gen.main([...])` must exit 0 on the *unspliced* copy after `--write` and 1 on a hand edit.

- [ ] **Step 4: Run it, then the suite**

Run: `python3 scripts/ci/tests/test-gen-slack-bindings.py && git add scripts/ci/tests && ./scripts/ci/host-profile.sh >/dev/null && ./scripts/ci/run-tests.sh`
Expected: the new suite `PASS gen-slack-bindings`, every other suite unchanged.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/tests/test-gen-slack-bindings.py scripts/ci/tests/slack-bindings-fixtures
git commit -m "test(slack): the binding generator's drift, byte-for-byte and unserved-repository gates"
```

### Task A4: the pin, the three regions, and the overlay copy goes

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml` (the chart's `ref.tag` and `ref.digest` — the factory image's tag must be the chart's version, `test-agent-factory-pins.py`'s rule), `tooling/base/agent-factory/helm-values-configmap.yaml` (the factory's `ghcr.io/smana/maku-factory` tag), `tooling/base/agent-factory/slack-app/deployment.yaml` (the App's `ghcr.io/smana/maku-slack` digest), `infrastructure/base/room-broker/app.yaml` (the broker's `spec.image.tag`), `infrastructure/base/room-broker/retention-cronjob.yaml` (the retention CronJob's `maku-broker` digest — the same digest `app.yaml` carries), `tooling/base/agent-factory/slack-app/config.yaml` (`teamID`, `channels`, the two comments that describe them), `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml` (`api.sponsored[slack-app].repositories`), `infrastructure/gcp-0/room-broker/config.yaml` (`webhooks[slack-app].repositories` and `.events`)
- Delete: `tooling/gcp-0/agent-factory/slack-app/config.yaml`
- Modify: `tooling/gcp-0/agent-factory/slack-app/kustomization.yaml` (drop the `configMapGenerator` `behavior: replace` block; keep `resources` and `patches`)
- Test: `scripts/ci/tests/test-gen-slack-bindings.py` (A3), `scripts/ci/tests/test-agent-factory-pins.py`, `task check`

**Interfaces:**
- Consumes: the release from Maku PR 7's tag, the declaration's rendering (A2).
- Produces: the chart's tag/digest and the four images at `vX.Y.Z@sha256:…` — the App's, the factory's, the broker's and its retention CronJob's — so **every** component that reads a `proposals`/`notify` key runs the release that decodes it before PR B turns the switch on.

- [ ] **Step 1: Pin the release, on every image that reads a new key**

Five pins, each following the comment convention already in its file: `flux/sources/ocirepo-agent-factory.yaml`'s `ref.tag`/`ref.digest` (`"X.Y.Z"  # maku vX.Y.Z`, with the released chart's digest — the values' image tag must equal the chart's version or `test-agent-factory-pins.py` fails); `tooling/base/agent-factory/helm-values-configmap.yaml`'s `image.tag` (keeping `# maku vX.Y.Z, the chart's appVersion.` and the `renovate:` line above it); `tooling/base/agent-factory/slack-app/deployment.yaml:33`'s `image:` (`vX.Y.Z@sha256:…`, replacing `v0.33.1@sha256:4a40…` — its comment says "with the factory's and the broker's pins", so all three move together); `infrastructure/base/room-broker/app.yaml`'s `spec.image.tag` (its comment, `# maku v0.33.1, by digest. Move it with the retention CronJob's, crd-rooms.yaml and atlasSchema.ref together.`, is the instruction: the retention CronJob's digest moves with it, and `crd-rooms.yaml`/`atlasSchema.ref` move only if this release changes the CRD or the schema — it does not, and the PR body says so); and `infrastructure/base/room-broker/retention-cronjob.yaml:35`'s `image:` (`# The same pin as app.yaml's.`).

The App's pin is the one that makes `proposals` and `notify` decodable, and the broker's is what makes the thirteen event names and `human.intake` readable: **PR B's `proposals: {enabled: true}` must not exist in any merged tree where the App's image is older than this pin.** Since both land in this repository and the pin is in PR A, that ordering is structural rather than a promise.

- [ ] **Step 2: Render the three regions**

Run: `python3 scripts/ci/gen-slack-bindings.py --write`
Expected: writes exactly three files — `tooling/base/agent-factory/slack-app/config.yaml`, `tooling/gcp-0/agent-factory/helm-values-sponsored.yaml`, `infrastructure/gcp-0/room-broker/config.yaml`. Read the diff: the App's `teamID` and `channels` are the declaration's, the sponsored `repositories` and the broker's `repositories`/`events` are the unions, and no other line of any of the three moved. Running `--write` a second time prints "is its declaration's rendering" for all three and changes nothing.

- [ ] **Step 3: Retire the overlay copy**

Delete `tooling/gcp-0/agent-factory/slack-app/config.yaml`, and remove the `configMapGenerator` block from that directory's `kustomization.yaml` with the comment that explained the replacement; the overlay's own `patches` stay. The rendered ConfigMap is now base's generated one (the declaration carries the ids, so base is no longer the "empty teamID" file — say that in the config's comment, since `gen-slack-bindings.py` owns those two regions and nothing else).

- [ ] **Step 4: Re-point the gate that read the deleted file**

`scripts/ci/tests/test-factory-slack-switchon.py`: `FILES` names `tooling/base/agent-factory/slack-bindings.yaml` instead of the deleted config; `app` becomes the declaration (so `app["channels"]` and `app["teamID"]` are its two keys); the `strip` lambda and the `the App's gcp-0 config is base's but for teamID and channels` check **go** (with `base_app`, now unused). Replace the later render check — `the render holds one App config ConfigMap, gcp-0's`, the one that already has `cms` and `docs` in hand — with these two, so the assertions sit where the render is parsed:

```python
# CD24: the declaration is the one place the channel binding is written, and the render is its
# picture — the overlay holds no copy to drift.
checks["the overlay holds no App config of its own"] = not (ROOT / "tooling/gcp-0/agent-factory/slack-app/config.yaml").exists()
rendered = yaml.safe_load(cms[0]["data"]["config.yaml"])
checks["the render is one App config, base's generated, with the declaration's binding"] = (
    len(cms) == 1
    and rendered["teamID"] == app["teamID"]
    and rendered["channels"] == app["channels"]
    and "factory-slack-app-config" not in {d["metadata"]["name"] for d in docs})
```

`onBehalfOf names the App's team` reads the declaration's `teamID` (unchanged code, new `app`); `every channel's maxCostUSD is at most the principal's` and `every channel's repositories are the principal's` read the declaration's channels; the `OWNER-FILL` markers are searched in the declaration and the sponsored values, not in the deleted file. Every other check stays as it is.

- [ ] **Step 5: Check**

Run: `task check`
Expected: exit 0 — the bundle renders, the host's `validate-manifests.sh` passes, `test-gen-slack-bindings` and `test-factory-slack-switchon` pass, the site builds, and `check-reader-first` is undisturbed (no site page changed in this PR).

- [ ] **Step 6: Commit, push, open PR A**

```bash
git add tooling infrastructure scripts/ci/tests
git commit -m "feat(slack): generate the channel binding's three consumers from one declaration"
git fetch origin && git rebase origin/main && git push -u origin feat/slack-bindings
gh pr create --title "feat(slack): one declaration for a channel's binding, three generated consumers, the release pin" \
  --body "CD24 and offline proof 16. tooling/base/agent-factory/slack-bindings.yaml declares teamID and each channel's repositories, maxCostUSD and notify; scripts/ci/gen-slack-bindings.py renders three consumers from it — the App's channels, the factory's sponsored repositories, and the broker's webhook repositories and events — byte for byte, and fails on drift, on a repository the factory does not serve, on a cost above the principal's ceiling and on an unknown event name. The overlay copy of the App's config is deleted and test-factory-slack-switchon reads the declaration instead. The release pin moves the chart and four images (the App's, the factory's, the broker's and its retention CronJob's) so every component decodes proposals and notify before either is set; both stay unset, so nothing proposes. crd-rooms.yaml and atlasSchema.ref do not move: the release changes neither. Evidence: task check exit 0."
```

### Task A5: the operator's runbooks

**Files:**
- Modify: `docs/runbooks/agent-factory/22-slack.md` (§5), `docs/runbooks/agent-factory/18-factory-interfaces.md` (§4's file list)

**Interfaces:**
- Consumes: the declaration and the generator (A1–A4).
- Produces: the procedure an operator follows instead of editing three files.

- [ ] **Step 1: Rewrite runbook 22 §5**

Replace the three-places table with: edit `tooling/base/agent-factory/slack-bindings.yaml`, run `python3 scripts/ci/gen-slack-bindings.py --write`, commit both; the rules that now fail at the declaration rather than at the cluster (a repository the factory does not serve, a `maxCostUSD` above the principal's, an event name the vocabulary does not hold); what each generated region governs (with the three-row table kept, its file column pointing at the declaration as the source and the generated file as the consumer); that the broker reads `webhooks` at start and the App reads its config at start, so `kubectl -n agent-system rollout status deploy/factory-slack-app deploy/room-broker` is the check; and that a subscriber the emitter disabled needs its `generation` bumped by hand, which the generator never writes.

- [ ] **Step 2: Amend runbook 18 §4**

Its file list gains the declaration and drops the deleted overlay copy, and one sentence says the pin in that PR is what brings `proposals` and `notify`.

- [ ] **Step 3: Check the doc paths and the links**

Run: `task docs && task check`
Expected: exit 0. Every path the runbooks name resolves in `.host/` or here.

- [ ] **Step 4: Commit**

```bash
git add docs/runbooks/agent-factory
git commit -m "docs(runbooks): a channel's binding is one declaration, generated"
```

---

## ai-native-ref PR B — `feat/slack-proposals-switch-on`: the switch, the page, the proof

### Task B1: the switch — **STOP for the owner's go**

**Files:**
- Modify: `tooling/base/agent-factory/slack-app/config.yaml` (`proposals: {enabled: true}`, a hand key outside the generated regions)

**Interfaces:**
- Consumes: the release pinned in A4, which is the first that reads `proposals`.
- Produces: `proposals: {enabled: true}` on the one channel the App serves.

- [ ] **Step 1: Ask, and wait**

Ask the owner, in these words: "Ready to turn the proposal message on for the one channel the App serves (`C0CC4M8SNVD`), on Maku `vX.Y.Z` (already pinned). A mention will plan through the broker's `planner` identity instead of the keyword composer, and the thread will carry one proposal message with Confirm/Cancel plus a ✅ fallback; a reply re-plans it; after filing the thread answers five fixed questions and posts no line for a run start. The planner reads public text only through `ai-gateway`, and `human.intake.plan.enabled` must already be on for the broker. Go, or hold?" Wait for an explicit go; record it in the PR body.

- [ ] **Step 2: Declare it**

```yaml
# CD7: one proposal message per thread, its controls, and the thread's five questions. Off, a
# mention drafts exactly as before (the fallback ✅ included).
proposals: {enabled: true}
```

Nothing else in that file changes: `teamID` and `channels` belong to the generator (A4).

- [ ] **Step 3: Check**

Run: `task check`
Expected: exit 0. `test-gen-slack-bindings` still passes: `proposals` is not a generated region.

- [ ] **Step 4: Commit and open the PR (no merge before the go)**

```bash
git add tooling/base/agent-factory/slack-app/config.yaml
git commit -m "feat(slack): turn the proposal message on for the one served channel"
git fetch origin && git rebase origin/main && git push -u origin feat/slack-proposals-switch-on
gh pr create --title "feat(slack): the proposal message on, one channel" --body "Owner go: <quoted>. CD7/CD8: proposals.enabled for C0CC4M8SNVD on Maku vX.Y.Z. The broker restarts are the ones A4 already noted (a webhooks change applies at start), and the App rolls on its config's content hash. Evidence: task check exit 0; live proof in Task B3."
```

### Task B2: the reader's side

**Files:**
- Modify: `website/content/docs/use/slack.md`

**Interfaces:**
- Consumes: the flow as B1 ships it.
- Produces: a page written for someone who was not there, per [`docs-style.md`](../../docs-style.md).

- [ ] **Step 1: Rewrite the page's flow sections**

`Write a mention` loses the `<owner/repo> <title>` rule and the keyword table, and says what a mention is: your own words, in a channel the App serves, and one question back when the repository is not obvious. `Edit the draft` becomes `Change the proposal`: reply in its thread; the message updates in place; the sections that changed are marked and the header says when a new confirmation is required; naming another repository in words moves the plan there. `File it` becomes `Confirm it`: the Confirm button, the ✅ fallback (and that the two do the same thing), and the `Filed #N` line in the same message. Add `Ask the thread` with the five questions in a table (question → what you get → where the link goes) and the sentence that nothing you type reaches the run; the stop row says the label is yours to apply, or the room page's Stop. `When it says no` gains the planner's refusals in the table's existing shape (a private repository, the plan service unavailable, more than one issue, a plan too long for Slack). Keep every path, id and dollar figure labelled `Example (the reference host):`, and say nothing about dates, clusters or proofs.

- [ ] **Step 2: Check the site**

Run: `task docs`
Expected: exit 0 — `hugo` builds, every `relref` resolves, every path the page names exists, and `check-reader-first.py` passes.

- [ ] **Step 3: Commit**

```bash
git add website/content/docs/use/slack.md
git commit -m "docs(use): the proposal message, and the thread's five questions"
```

### Task B3: the live proof — **STOP for the owner's go before each cluster action**

**Files:**
- Create: `docs/runbooks/agent-factory/results-gcp-0-<date>-slack-proposals.md`

**Interfaces:**
- Consumes: B1 merged and rolled out; the broker's `human.intake.plan.enabled` on; the App's `proposals.enabled` on.
- Produces: the transcripts of the spec's Slack rows 6–12, in one session, one public repository.

- [ ] **Step 1: Prove one message across five replies (spec row 7)**

Mention in the served channel in plain words that name no repository; then reply five times, one of them naming the other allowlisted repository. Record, from `kubectl -n agent-system logs deploy/factory-slack-app` and the thread's permalinks: one message `ts`, five `chat.update` calls (`maku_slack_proposal_updates_total{action="reply"} == 5`), the changed marks, and the header's `requires a new confirmation` after the repository moved.

- [ ] **Step 2: Prove a non-maintainer is refused, and a maintainer files (row 8)**

A confirm by a Slack user whose linked GitHub login is not a maintainer: one line, no issue. Then a maintainer's Confirm: the issue exists with its labels, the task starts, and the thread's one message reads `Filed #N`.

- [ ] **Step 3: Prove the restart before Confirm (row 9)**

Open a proposal, `kubectl -n agent-system rollout restart deploy/factory-slack-app`, wait for the rollout, then press Confirm: the same plan files from the metadata, and the App's log shows no `intake_plan` call between the restart and the filing.

- [ ] **Step 4: Prove the answers, the silence, and the fallback (rows 10–12)**

`how is it going?` → the card's status; `needs me?` → the room's needs with their links; `stop it` → the label and the room link, and the run keeps running (`room_summary`'s phase unchanged afterwards). Then a run start alone posts nothing — no new thread line, and `factory_slack_requests_total{route="webhooks",outcome="ignored"}` moves — while the next `room.waiting_for_human` posts its one line; and a `room.approval_closed` arriving from the approval design's path is accepted: one line, no `chat.update` of the proposal, no error in the App's log. Finally, with `proposals: {enabled: false}` (a one-line change, rolled out and reverted), the same thread shows the draft behaviour and the ✅ fallback works.

- [ ] **Step 5: Write the results file, the status row, and commit**

```bash
git add docs/runbooks/agent-factory/results-gcp-0-<date>-slack-proposals.md website/content/docs/status.md
git commit -m "docs(results): the Slack proposal session, rows 6 to 12, and the state it establishes"
```

The file holds each row, the command or click, and the observed output. `website/content/docs/status.md`'s Slack intake row becomes `| Slack intake | A mention proposes an issue; a maintainer confirms it and the thread follows the task | GKE | [runbook 22](…) |`, its evidence linking this file — one line, no session history, per [`docs-style.md`](../../docs-style.md) rule 4. Then `task docs` once more, and push.

---

## Sequencing and merge order

Each arrow is a rebase obligation: the later PR rebases onto `origin/main` after the earlier one merges and re-runs the tests this table names.

| # | Lands | What this plan consumes from it | What this plan must re-run after its rebase |
|---|---|---|---|
| 1 | Slack push-approval Maku PRs 1–4 and its release | `Metadata.EventPayload` as `json.RawMessage`; `Slack.Update`/`PostCard`; the interactivity branch, `parseInteraction`, its dedup; `room.approval_closed`; `Channel.Approvals` | `TestMetadataShapes` (the draft's bytes), `TestProposalMetadataRoundTrip`, `TestUpdateProposalWire`, `TestProposalInteractionDispatch` — and, because PR 6 Task 3 moves that branch's value-class cases into its own case, `TestSlackInteractivitySignature`, `TestInteractivityShape` and `TestInteractivityBusyRetries` |
| 2 | Conversational-intake Maku PRs 1–4 and its release | `plan/v1`, `intake.Hash`, `p.JSON()`, `intake_plan`'s schema and result, `plan_check`, `run_create`'s `plan`/`plan_hash` | `TestProposalTooLargeIsRefused`, `TestIntakePlanCall`, `TestRunCreateSendsThePlan`, `TestCheckMarkFilesAProposal` |
| 3 | Attention-and-resume Maku PRs 1–8 and its release | `needs_list` on both lists, `summary.Need`, `webhook.Meaningful`/`Notify`, `roomview.ChangeSet`, `summary.Summary` | `TestLoadProposalsAndNotify`, `TestNotifyProjection`, `TestThreadQuestionVocabulary` |
| 4 | Attention PR 10 (ai-native-ref) | Drops `room.run_started` from `webhooks[slack-app].events` | **this plan's PR A replaces that hand edit** with the declaration's rendering; the event list's final content is A1's nine, and `test-room-broker-webhook-egress` runs again |
| 5 | Approval PR B (ai-native-ref) | `room.approval_closed` in the `events` list, the App's `channels.<id>.approvals` | the same: A1's `notify` carries `room.approval_closed`, and `approvals: false` stays hand-kept in the App's config |
| 6 | **Maku PR 5 → 6 → 7 → release** | — | `task check` on each; the release is what A pins |
| 7 | **ai-native-ref PR A** | the release from 6 | `task check`; `test-factory-slack-switchon`, `test-gen-slack-bindings`, `test-room-broker-suspend` (it compares the broker config with base's), `test-agent-factory-pins.py` (the chart and the factory image move together) |
| 8 | **ai-native-ref PR B** | A merged and rolled out | `task check`, `task docs`, the live proof |

Files three plans edit, and who rebases: `internal/slackapp/app.go` (this plan's `mention`/`reply`/`file`/`deliver` branches sit beside the approval design's card and interaction code and the attention plan's `line()` entry — whoever lands second reads the other's comment and keeps both); `internal/metrics/metrics.go` (approval adds `rooms_slack_decisions_total`, this plan adds `slack_*`, both extend `MakuName`); `internal/slackapp/config.go` (approval adds `approvals`, attention adds nothing here, this plan adds `proposals` and `notify`); Maku `docs/slack.md` (three plans edit it: approval's card and interactivity, attention's notification table, this plan's flow); `infrastructure/gcp-0/room-broker/config.yaml`'s `webhooks[slack-app]` (after A, no plan edits it by hand — they edit the declaration).

## Not in this plan {#not-in}

- The planner, `plan/v1`'s shape, `intake_plan`'s internals, `plan_check`, the model route, the degraded composer: the conversational-intake plan.
- `needs/v1`, `needs_list`, the resume brief, revision preference, the final spend, the actionable failure: the attention plan.
- Approving or deciding from Slack, the decide route, the card, `room.approval_closed`'s emission: the Slack push-approval plan.
- Multi-repository coordination, private-repository planning, code search, a free-form chat engine, a repository menu, a modal, a slash command, a DM.
- Inbox ranking, digests, email, the fast-follow pack, and any change to the draft flow's wire bytes.

## Self-review

**1. Spec coverage.** CD7 → Maku 5 (metadata, blocks, one message) and 6 (post/update/flows); CD8 → Maku 7 (the five answers) and the notify projection in 7 Task 2; CD14/CD27 → PR 5 Task 3 (`proposalChanged`) and PR 6 Task 2 (the marks and the header); CD20 → PR 5 Tasks 3–4 (metadata only, never rendered text); CD24 → ai-native-ref A1–A5; CD25 → PR 7 Task 1; CD28 → PR 7 Task 1's three sponsored reads (no new tool is added: `needs_list` is the attention plan's); CD29 → PR 6 Task 3 (the approval design's one branch, extended). §plan's Slack bound → PR 5 Task 3. §Security's rows (stale confirm, rendered message as a second source, status question as steering, untrusted text as a link) → PR 5 Task 3 (`proposalHashHolds`), PR 6 Task 3 (the value-vs-metadata check), PR 7 Task 1 (`TestThreadAnswersAreInert`, stop reads nothing), PR 5 Task 2 (`roomview.Proposal`'s escape test). §Failures (a second Confirm, a restart, interactivity off, a status question the vocabulary does not know) → PR 5 Task 5 (`Already filed`), PR 5 Task 4 (`TestProposalRecoveredFromMetadataAlone`), PR 6 Task 3 (the `not_enabled` teaching line), PR 7 Task 1 (`unknown`). §Switches `proposals.enabled`/`notify` → PR 5 Task 1. §Acceptance offline 5, 10, 11 → PRs 5 and 6; 16 → A3. §Acceptance live 6–12 → B3. §Rollout 5 ("`proposals.enabled` in one channel, after the approval design's `chat.update` and interactivity are released; the fallback ✅ stays") → the merge order and B1. **Three deviations, named here rather than left to drift:** (a) the spec's `maku_slack_thread_answer_total` is served plural, `maku_slack_thread_answers_total`, because the counter's label is a set of questions; (b) both instruments register with a literal `_total` (`slack_proposal_updates_total`, `slack_thread_answers_total`) because this exporter appends no suffix, so the served name differs from the registered one by `MakuName`'s prefix alone; (c) `action` gains a `repost` label the spec's table does not list — a refused `chat.update` that reposts is a behaviour the operator must see, and folding it into `reply` would hide it. All three are pinned by `TestProposalCounterName` / `TestProposalActionsCounted`.

**2. Step scan.** Every task's first step is a named test with its assertions; every implementation step names a signature and the file; no step says "handle the edge cases" or "add validation". A few steps carry prose where the decision *is* the set or the order — `roomview.Proposal`'s section order, `proposalChanged`'s projection, `questionOf`'s phrase list — because none of those can be inferred from a signature; everything else defers its body to the test above it. The generator's rules are a list, not code: A2 defers its body to the test A3 writes first, which is the one place the exact strings appear.

**3. Type consistency.** `ProposalPayload`, `MarkerPayload`, `proposalValue`, `parseProposalValue`, `proposalHashHolds`, `proposalChanged`, `proposalSections`, `postProposal`, `updateProposal`, `threadProposal`, `fileProposal` (with its `confirm` flag), `(*App).filedText`, `propose`, `replan`, `followUps`, `commandless`, `RequestedTextTooLong`, `proposalAction`, `proposalDedupKey`, `questionOf`, `answer`, `Channel.notifies`, `IntakeRequest`/`IntakeResult`, `RunCreate.Plan`/`.PlanHash`, `Set.ProposalUpdate`/`Set.ThreadAnswer`, `Recorder.ProposalUpdate`/`.ThreadAnswer`, `slackRecorder`'s two forwarding methods are defined once, in the task that first uses them, and used with those names in every later task and in the sequencing table. The names this plan does **not** define — `intake.Hash`, `intake.Material`, `intake.Plan`, `intake.Check`, `intake.Question`, `webhook.Notify`, `webhook.Types`, `summary.Need`, `summary.Summary`, `roomview.ChangeSet`, `Slack.Update`, `Slack.PostCard`, `interaction`, `parseInteraction`, `actionApprove`/`actionDeny` — are used exactly as their owning plans' Interfaces blocks state them; a rename there is that plan's PR and this plan rebases on it (the sequencing table says which test re-runs). The one interface this plan *narrows* is the approval design's dispatcher: its common checks lose the value-class cases to its own case, so its `TestInteractivityShape` is re-run in PR 6 Task 3 and the sequencing table names it.

**4. Review Focus.** Five lines, five owning tasks, each with the test named in that task's own style: 1 → PR 5 Task 4 and PR 6 Task 3 (`TestOneProposalMessageAcrossRevisions`'s failure case; `TestProposalConfirm`'s stale value); 2 → PR 6 Task 2 (`TestReplySerialised`); 3 → PR 6 Task 3 (`TestProposalConfirmRefusals`'s re-served channel); 4 → PR 7 Task 1 (`TestThreadAnswerUnknownRoom`); 5 → A3 (`check_hand_editing_a_generated_region_fails`). An empty section would mean I checked and found none; these five are the ones a person meets first.

**5. Proportion.** This plan runs about 1 150 lines to cover one of the spec's six subsystems (the Slack half, ~250 lines of the spec's decisions, tables and acceptance rows), and the ratio holds because three of its five PRs are Maku code with a test cycle each rather than because a program was transcribed: the code blocks are signatures, test names with their assertions, one YAML declaration and one dispatcher sketch — no function body is written out, and every task defers its body to the test that pins it. Where a decision was mine rather than the spec's, it is named as mine: `maxProposalRevisions = 40`, cancel being the author's alone, the answer's twelve-line bound, the `MarkerPayload.Room` carrier (so a thread finds its room without a store), the repost-and-inert fallback for a refused `chat.update`, the two registered names carrying a literal `_total` and the `repost` label (item 1's deviations), and the answers' renderer living in `slackapp` with `slackText` rather than in `roomview` (whose `Slack` format this plan adds for the proposal only — giving every existing view a Slack format is a blast radius the increment does not need, and the answers are fixed prose plus values).

## Execution handoff

The tasks are interface-heavy and strictly ordered: PR 5's payload shape is read by PR 6's flows, PR 6's flows by PR 7's answers, and ai-native-ref PR A pins the release the three produce while replacing two sibling plans' hand edits of one file. A shipped mistake in the metadata shape (PR 5 Task 3) invalidates every later task's fixtures, and a shipped mistake in the generator (A2) reaches a live cluster's App config. That makes independent review worth its cost: **subagent-driven** is the recommendation — a fresh implementer per task and a fresh reviewer between them, then a whole-branch review before PR A opens. Native execution is defensible only if PR 5 Tasks 1–3 are reviewed before PR 6 starts.
