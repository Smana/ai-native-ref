# Multi-repository parent experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the parent-only experience for two-repository coordination: filtered parent planning/progress views, parent-UI confirmation, a distinct live coordination rail, unified attention/resume, Slack and coding-agent journeys, and safe per-repository checkout, without adding execution or merge authority.

**Architecture:** A broker-side internal reader consumes the core engine's `CoordinationView` and applies an intersection of GitHub-read and sponsored/channel allowlists at every read. `summary/v1`, the existing card/overview/needs/brief renderers, and a new `flow.coordination` projection carry only that filtered view; the rail reuses role glyphs and milestones but never splitter facts or chips. Slack reuses the sibling proposal message, metadata recovery, edit lock, and one interactivity dispatcher, while all parent/child confirmations and recovery actions remain in the parent UI and merges remain on GitHub. Parent checkout composes the existing safe git helpers into detached exact-SHA worktrees and a versioned local manifest.

**Tech Stack:** Go 1.25, controller-runtime live readers and fakes, `httptest`, existing `internal/summary`, `internal/roomview`, `internal/humanapi`, `internal/slackapp`, and `internal/maku` packages, TypeScript + Vitest + esbuild, Slack Block Kit and existing proposal/interactivity machinery, git worktrees, OpenTelemetry, `task`; ai-native-ref kustomize/Flux, Python render gates, and Hugo.

**Spec:** [the multi-repository coordination design](../specs/2026-11-05-v4-multi-repo-coordination-design.md), specifically MR13–MR15, “Roles and the parent view”, read privacy, parent checkout, interface seams, O11–O13, and the experience parts of L1/L2/L8. The exact engine contracts come from [the completed core plan](2026-11-05-v4-multi-repo-coordination-maku-plan.md#experience-neutral-contracts-declared-here-rendered-elsewhere), especially PR 7 Task 16. Sibling contracts consumed without redesign are [conversational intake](2026-11-05-v3x-conversational-intake-maku-plan.md#seam-coordination), [attention and resume](2026-11-05-v3x-attention-resume-maku-plan.md), [Slack proposals](2026-11-05-v3x-slack-proposals-maku-plan.md), and the [Slack approval design](../specs/2026-11-05-v3x-slack-push-approval-design.md#the-seam-to-the-conversational-devex-design-seam).

## Global Constraints

- **Source and branches.** Maku is `github.com/Smana/maku`, reviewed at `/tmp/opencode/maku-devex-read` commit `4685672f0f40973286a121f83ea92dd3428b8120`. Set `MAKU` to a fresh checkout of `origin/main`; use one worktree per PR from freshly fetched `origin/main`, and rebase before every push. Branches are `feat/coordination-projection`, `feat/coordination-room`, `feat/coordination-parent-ui`, `feat/coordination-slack`, `feat/coordination-checkout`, and `feat/coordination-experience-docs`. ai-native-ref uses `feat/coordination-experience-off` and, only after the live proof, `docs/coordination-experience-proof`.
- **Required landed contracts.** Rebase onto the core plan PRs 1–7 and its release before PR 1. The core planner already supplies `coordination_plan`; do not write another planner, model route, Task kind, filing path, artifact/integration engine, or confirmation service. Attention PRs 1–8 supply `needs/v1`, `room_brief`, and `webhook.Meaningful`; Slack approval supplies `chat.update`, tagged metadata, and the single `POST /slack/events` interactivity branch; Slack proposals supply the proposal payload/update/recovery/edit-lock/five-answer flow. If landed names differ from their plans, adapt to the actual public interface without widening it.
- **Exact core types, imported, not forked.** JSON is lower camel case; hashes are lowercase hex without a `sha256:` prefix. `ParentConfirmation`, `ChildAuthorization`, `IntegrationRelease`, `RecoveryProposal`, `CoordinationIncident`, and `LandedArtifact` remain their CRD aliases. `DependsOn` holds child IDs and `Consumes` holds `<from>/<artifact>` IDs. Checkout `Issue` and `PR` are validated URLs.

```go
type CoordinationConfirmation struct {
    Plan     v1alpha1.CoordinationPlan `json:"plan"`
    PlanHash string                    `json:"planHash"`
    Parent   *ParentConfirmation       `json:"parent,omitempty"`
    Child    *ChildAuthorization       `json:"child,omitempty"`
    Planning PlanningReconciliation    `json:"planning"`
}
type PlanningReconciliation struct {
    AttemptID          string `json:"attemptID"`
    EffectiveRequester string `json:"effectiveRequester"`
    ReservationID      string `json:"reservationID,omitempty"`
    SettlementID       string `json:"settlementID,omitempty"`
    ReservedMicroUSD   int64  `json:"reservedMicroUSD"`
    SettledMicroUSD    int64  `json:"settledMicroUSD"`
}
type CoordinationView struct {
    ParentTask              string                         `json:"parentTask"`
    Phase                   string                         `json:"phase"`
    Reason                  string                         `json:"reason"`
    Plan                    v1alpha1.CoordinationPlan      `json:"plan"`
    PlanHash                string                         `json:"planHash"`
    ParentConfirmation      *ParentConfirmation            `json:"parentConfirmation,omitempty"`
    ChildAuthorizations     []ChildAuthorization           `json:"childAuthorizations"`
    Children                []CoordinationChildView        `json:"children"`
    Artifacts               []v1alpha1.LandedArtifact      `json:"artifacts"`
    IntegrationAttempts     []IntegrationAttemptView       `json:"integrationAttempts"`
    MergeOrder              []string                       `json:"mergeOrder"`
    Budget                  CoordinationBudgetView         `json:"budget"`
    Recovery                *v1alpha1.RecoveryProposal     `json:"recovery,omitempty"`
    PostCompletionIncidents []CoordinationIncident         `json:"postCompletionIncidents,omitempty"`
}
type CoordinationChildView struct {
    ID                      string                        `json:"id"`
    Repository              string                        `json:"repository"`
    Task                    string                        `json:"task"`
    Room                    string                        `json:"room"`
    IssueURL                string                        `json:"issueURL"`
    PRURL                   string                        `json:"prURL,omitempty"`
    Phase                   string                        `json:"phase"`
    Reason                  string                        `json:"reason"`
    Fingerprint             string                        `json:"fingerprint"`
    DependsOn               []string                      `json:"dependsOn"`
    Consumes                []string                      `json:"consumes"`
    HeadSHA                 string                        `json:"headSHA,omitempty"`
    MergeCommitSHA          string                        `json:"mergeCommitSHA,omitempty"`
    AllocationMicroUSD      int64                         `json:"allocationMicroUSD"`
    SettledMicroUSD         int64                         `json:"settledMicroUSD"`
    ReservedMicroUSD        int64                         `json:"reservedMicroUSD"`
    IntegrationAcceptedHead string                        `json:"integrationAcceptedHead,omitempty"`
    IntegrationRelease      *v1alpha1.IntegrationRelease `json:"integrationRelease,omitempty"`
}
type IntegrationAttemptView struct {
    Task         string                        `json:"task"`
    Purpose      string                        `json:"purpose"`
    PlanHash     string                        `json:"planHash"`
    ManifestHash string                        `json:"manifestHash"`
    State        string                        `json:"state"`
    Reason       string                        `json:"reason"`
    Subjects     []v1alpha1.IntegrationSubject `json:"subjects"`
    RunMicroUSD  int64                         `json:"runMicroUSD"`
    CostMicroUSD int64                         `json:"costMicroUSD"`
}
type CoordinationBudgetView struct {
    PlanningMicroUSD             int64 `json:"planningMicroUSD"`
    PlanningReservedMicroUSD     int64 `json:"planningReservedMicroUSD"`
    PlanningSettledMicroUSD      int64 `json:"planningSettledMicroUSD"`
    TotalMicroUSD                int64 `json:"totalMicroUSD"`
    AllocatedMicroUSD            int64 `json:"allocatedMicroUSD"`
    ChildrenReservedMicroUSD     int64 `json:"childrenReservedMicroUSD"`
    ChildrenSettledMicroUSD      int64 `json:"childrenSettledMicroUSD"`
    IntegrationReservedMicroUSD  int64 `json:"integrationReservedMicroUSD"`
    IntegrationSettledMicroUSD   int64 `json:"integrationSettledMicroUSD"`
    IntegrationMaxRuns           int   `json:"integrationMaxRuns"`
    IntegrationRuns              int   `json:"integrationRuns"`
}
type CheckoutManifest struct {
    ParentTask  string           `json:"parentTask"`
    PlanVersion int32            `json:"planVersion"`
    PlanHash    string           `json:"planHash"`
    Children    []CheckoutChild  `json:"children"`
}
type CheckoutChild struct {
    ID             string                     `json:"id"`
    Repository     string                     `json:"repository"`
    Worktree       string                     `json:"worktree"`
    Room           string                     `json:"room"`
    Issue          string                     `json:"issue"`
    PR             string                     `json:"pr"`
    DependsOn      []string                   `json:"dependsOn"`
    Artifacts      []v1alpha1.LandedArtifact  `json:"artifacts"`
    HeadSHA        string                     `json:"headSHA,omitempty"`
    MergeCommitSHA string                     `json:"mergeCommitSHA,omitempty"`
}
```

- **One logical switch.** `coordination.mode: off|plan|execute`, `publicOnly: true`, and `maxChildren: 2` remain core-owned and projected into both strict configs. `off` registers no coordination read/draft/confirmation/checkout route and no Slack coordination branch. `plan` permits parent drafts and confirmations but no issues or runs. `execute` additionally requires the core capability gate; this plan adds no independent Slack or UI enable flag.
- **Read-time intersection, always.** Parent admission first uses the ordinary primary-room check. Every child is then filtered independently by the viewer's linked GitHub `CanRead`; `agents-admin` confers no child access, and identity/access failure restricts that child. Sponsored visibility is the configured principal repository upper bound, with the Slack channel's repositories applied as a second filter in the App. Never cache a filtered projection or fold an unfiltered view into a parent event.
- **Restricted means restricted.** An unauthorized child contributes only `restrictedChildren` to a human projection: no repository, title, scope, issue/PR URL, room, artifact metadata, error text, fingerprint, or child/family-inferable budget. Filter nested plan children, authorizations, merge order, artifacts, integration subjects/attempts, recovery, and incidents too. An unreadable child API remains `404`, not a revealing `403`. Checkout refuses the whole family when any required child is restricted.
- **Slack channel rule.** A channel not serving the primary receives no parent event and cannot originate a family. A channel serving some but not every displayed repository gets only coarse parent phase/reason and the parent-room link. Only a channel explicitly serving every displayed repository gets child/artifact/integration details. Recompute this at every proposal render, answer, and webhook delivery.
- **No new authority or semantics.** No new Task/CRD/engine semantics, AgentRun role, gateway audience, STS policy, parent code/merge path, Slack plan/merge approval, atomic cross-repository merge, rollback/playbook, fleet/cross-factory/arbitrary fan-out, private integrated family, or live parallel claim. No `Split`, `spec.parent`, `status.split`, `TaskFacts.split/parent`, `factory/child-of`, `.rail-part`, or splitter chip is reused for coordination.
- **Parent confirmation is UI-only.** Slack and MCP may plan, open a draft, read, resume, and check out; they may not confirm a parent/child plan or invoke recovery. Browser confirmation routes require the web client and the core's fresh repository authority. Every child merge is a GitHub current-head review/class-gate decision. Slack's separate `forge.push` approval is unchanged and is not a coordination approval.
- **Sibling behavior is reused, not duplicated.** `plan/v1` stays single-repository. Existing proposal metadata bytes and legacy `plan/v1` goldens remain unchanged. Coordination Slack metadata is a pointer to the core's full stored snapshot, not a second plan store or a parsed rendered message. Needs use the existing kind/order/standing derivation and resume uses `roomview.Brief`; no coordination-specific inbox, ranking, notification vocabulary, or resume algorithm.
- **Slack routing is deterministic, not another parser.** Exactly two unique explicit `owner/repo` mentions select coordination; the first is the user-selected primary shown for confirmation. Zero or one keeps the existing single-repository flow. More than two is refused before a model call. A primary change starts a new mention/draft, as the core requires; an edit never silently moves primary.
- **Checkout is local, exact, and non-destructive.** Use existing origin checks, flagged-file and symlink checks, one combined confirmation, and no-hook/no-smudge git execution. Never clone implicitly, create/move a branch, update the current checkout, or run a manifest command. A changed plan/head returns `checkout_stale`; an incomplete new root is reported, never silently repaired or deleted.
- **The evidence.** Maku: `task lint` reports 0 issues and `task check` exits 0, including race tests, envtest 1.36.x, store testcontainers, chart/UI/name/docs checks. Run `task crd:check && task chart:check` after the broker RBAC change and `task ui:test && task ui:check` after web changes; commit the generated UI bundle. ai-native-ref: `task docs && task check` both exit 0. Never claim completion without those outputs.
- **Conventions and rebases.** Maku `AGENTS.md` applies: SPDX, package/export comments naming MR/CD decisions, stdlib table tests and hand-written fakes, consumer-owned interfaces, bounded data, and no plan text/artifact bytes/viewer/channel IDs in telemetry. Commits and PRs are conventional English with no trailers or attribution. Shared files (`humanapi/mcp.go`, `sponsored_test.go`, `summary/needs.go`, `roomview/*`, `slackapp/*`, `web/src/*`, Slack bindings and broker configs) are rebased over all sibling landings; never overwrite their tool lists, needs clauses, metadata decoders, or meaningful-notification table.
- **Owner gate.** The ai-native-ref adoption only pins and declares `mode: off`. No live issue, branch, run, merge, Slack post, cluster mutation, or `plan`/`execute` switch-on occurs without a separate explicit owner go naming the cluster, two public proof repositories and primary, both maintainers, proof channels/viewers, coding client, failure injection, and time-bounded merge window. Live work starts only after core activation and its prerequisites are verified.

## Review Focus

1. **An admin, an unlinked viewer, or a transient access error reaches a child nested inside an otherwise authorized parent.** The child must collapse to a count with every nested field and inferable budget removed; no admin bypass or cached success is allowed. Owning test: PR 1, Task 2 (`TestCoordinationFilterIntersectionHasNoAdminBypass`).
2. **A fully served Slack channel becomes partial, or read access is revoked between deliveries.** The next render must be coarse or dropped immediately, with no child details retained from an earlier full message or summary. Owning test: PR 4, Task 8 (`TestSlackProjectionRecomputedAfterChannelOrAccessChange`).
3. **A plan edit lands between a parent summary read and Confirm.** The confirmation must return `stale_plan`, change no draft/Task/run, refresh the diagram, and never fall back to Slack confirmation. Owning test: PR 3, Task 6 (`TestCoordinationConfirmationStalePlanRefreshesWithoutWrite`).
4. **A remote branch moves or a merge SHA stops being an ancestor between manifest resolution and worktree creation.** Checkout must refuse without moving an existing worktree or touching the initiating checkout, and report any incomplete new root. Owning test: PR 5, Task 10 (`TestCoordinationCheckoutMovingRemoteAndStaleManifestRefuse`).
5. **A parent has its own confirmation/recovery need while a child independently has a merge or review need.** The unified list must contain the parent item once plus the child's ordinary item once, with no second parent inbox or duplicated child operational items. Owning test: PR 2, Task 4 (`TestCoordinationNeedsAreUnifiedAndDoNotDuplicateChildren`).

---

## File structure

| File | Responsibility | PR |
|---|---|---|
| `internal/coordinationview/source.go`, `filter.go`, `checkout.go` (new) | Live core-view reader, fail-closed per-viewer sanitization, checkout document derivation | 1, 5 |
| `internal/factory/ledger/ledger.go` | Exported read-only outstanding reservations across retained UTC days used by the core `View` signature | 1 |
| `charts/maku/templates/broker-rbac.yaml` | Read-only Tasks/ConfigMaps for the broker's uncached internal reader | 1 |
| `internal/humanapi/coordination.go`, `coordination_checkout.go` (new) | Filtered human routes; no raw-view route | 1, 5 |
| `internal/config/config.go`, `internal/app/{broker,rooms}.go`, `internal/humanapi/server.go` | Sponsored repository upper bound, live reader and mode wiring | 1 |
| `internal/summary/coordination.go` (new), `flow.go`, `summary.go` | Filtered summary field and distinct coordination flow/overview types | 2 |
| `internal/humanapi/{summary,rooms}.go` | Attach filtered projection to summary, rows, and unified needs | 2 |
| `internal/roomview/{card,overview,brief}.go`, `coordination.go` (new) | Parent card/row/Slack text and resume additions over existing renderers | 2, 4 |
| `internal/summary/needs.go`, `internal/humanapi/brief.go` | Parent confirmation/recovery in `needs/v1`; coordination plan in the existing brief | 2 |
| `web/src/{coordination,summary,rail,room,view,app.css}`, `web/test/*`, `internal/humanapi/ui/dist/*` (generated) | Parent diagram, room/overview projection, confirmation controls, and committed browser bundle | 3 |
| `internal/humanapi/coordination_write.go` (new), `internal/runrequest/coordination.go` (new), `internal/factory/api/coordination.go`, `internal/factory/api/coordination_test.go` | Token-forwarding draft/confirmation/recovery gateway and core identity transport; web-only decisions | 3, 4 |
| `internal/slackapp/{proposal,slack,broker,app}.go`, `coordination.go` (new) | Coordination pointer payload, two-repository origin/edit, channel-filtered follow | 4 |
| `internal/factory/reconciler/coordination.go`, `internal/factory/reconciler/coordination_test.go` | Parent-room sponsored watcher membership for filtered Slack reads | 4 |
| `internal/maku/coordination_checkout.go` (new), `client.go`, `localtools.go`, `internal/app/maku.go`, `internal/mcpwire/mcpwire.go` | Draft opening, exact detached worktrees, manifest, CLI and local MCP tools | 3, 5 |
| `internal/metrics/metrics.go`, Maku `docs/{api,cli,slack,security,operations}.md`, `docs/superpowers/plans/2026-11-05-v4-multi-repo-experience-maku-plan.md` | Bounded experience observability, operator/security docs, and this plan's Maku copy | 6 |
| ai-native-ref pins including `tooling/base/agent-factory/slack-app/deployment.yaml`, `infrastructure/base/room-broker/{rbac,config}.yaml`, Slack binding generator/tests | Released Maku, read-only RBAC, sponsored upper bound, `mode: off` | 7 |
| ai-native-ref reader/runbook/dashboard/status/decision/results docs | User/operator guidance, observability, owner-gated evidence and precise non-claims | 7–8 |

---

## PR 1 — `feat/coordination-projection`: internal core reads and per-viewer filtering

### Task 1: Live `CoordinationView` source and broker read-only RBAC

**Files:**
- Create: `internal/coordinationview/source.go`, `internal/coordinationview/source_test.go`
- Modify: `internal/factory/ledger/ledger.go`, `internal/factory/ledger/reserve_test.go`, `charts/maku/templates/broker-rbac.yaml`, `charts/maku/tests/render.sh`

**Interfaces:**
- Consumes: core PR 7 `coordination.View(parent, children, integrations, ledger)` and its exact `CoordinationView`; `v1alpha1.LabelCoordinationParent`.
- Produces: `type Source struct { Reader client.Reader; Namespace string }`; `func (s Source) View(ctx context.Context, parentTask string) (coordination.CoordinationView, error)`, plus `var ErrNoCoordination, ErrCoordinationUnavailable error`, returning the first for a missing/non-coordination parent and the second for a read failure.
- Produces: `func ledger.ReservedByRun(ctx context.Context, c client.Reader, ns string) (map[string]int64, error)` reading and summing each run's outstanding `reserved.<run>.maxMicroUSD` across every retained UTC-day ledger through the existing decoder. No reservation or ledger mutation.
- RBAC: broker gets only `get,list` on `tasks` and `configmaps`; no watch, create, update, patch, delete, or new RoleBinding.

- [ ] **Step 1: Write failing source and RBAC tests**

`TestSourceUsesTheCoreViewAndLiveReads` builds a parent, two labelled children, pre/final integration Tasks, and reserved/settled entries on consecutive UTC days; assert the result is identical to calling core `View` directly, including exact subjects, allocations, and one recovery. Assert `Reader` is used live (a fake cached reader that would return stale objects is not called), non-coordination/missing parents return `ErrNoCoordination`, and any Task/ConfigMap error returns `ErrCoordinationUnavailable`. `TestReservedByRunReadsAllOutstandingDays` covers reservations on two days, a released entry, a malformed amount, and a non-ledger ConfigMap. The chart render assertion pins exactly `get,list` for Tasks/ConfigMaps and no other new verb.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/coordinationview/ ./internal/factory/ledger/ -run 'TestSource|TestReservedByRun' -count=1 && bash charts/maku/tests/render.sh`
Expected: FAIL at compile (`coordinationview.Source` and `ReservedByRun` undefined) and missing RBAC rules.

- [ ] **Step 3: Implement the narrow live reader**

Read the parent with the injected uncached `client.Reader`, list implementation children by the parent's coordination label, read integration Tasks named by the parent's bounded status lineage, obtain settled usage through `ledger.SettledByRun` and all outstanding reservations through `ReservedByRun`, assemble the core `coordination.LedgerUsage{ByRun: map[string]coordination.RunUsage}`, then call core `View` unchanged. Keep the unfiltered value internal to `coordinationview` and `humanapi`; add no HTTP handler here.

- [ ] **Step 4: Run tests and generated checks**

Run: `go test ./internal/coordinationview/ ./internal/factory/ledger/ -count=1 && task crd:check && task chart:check`
Expected: PASS and the only chart change is the two read-only resource rules.

- [ ] **Step 5: Commit**

```bash
git add internal/coordinationview internal/factory/ledger charts/maku
git commit -m "feat(coordination): read the core view through a narrow broker source"
```

### Task 2: Sanitizing filter, sponsored upper bound, and filtered human route

**Files:**
- Create: `internal/coordinationview/filter.go`, `internal/coordinationview/filter_test.go`, `internal/humanapi/coordination.go`, `internal/humanapi/coordination_test.go`
- Modify: `internal/humanapi/server.go`, `internal/config/config.go`, `internal/config/config_test.go`, `internal/app/broker.go`, `internal/app/rooms.go`, `internal/app/broker_test.go`

**Interfaces:**
- Produces: `type View struct { coordination.CoordinationView; RestrictedChildren int \`json:"restrictedChildren"\` }`; the anonymous embedding preserves every core JSON field and adds no replacement field.
- Produces: `type RepositoryReader interface { Login(ctx context.Context, sub, repository string) (string, error); CanRead(ctx context.Context, repository, login string) (bool, error) }`; `type Viewer struct { Sub string; Sponsored bool; Repositories map[string]bool }`; `func Filter(ctx context.Context, raw coordination.CoordinationView, viewer Viewer, access RepositoryReader) View`.
- Produces: `config.SponsoredConfig.Repositories []string`; `humanapi.Server.Coordination *coordinationview.Source` and `SponsoredRepositories map[string]map[string]bool`, populated only when mode is not `off` from the same config as the planner and keyed by the authenticated principal ID `system:<name>`. Repository entries use the existing `repositoryRE` validation and reject duplicates.
- Route: `GET /api/coordinations/{task}` returns the filtered `coordinationview.View`; `off` is 404. There is no route returning raw `coordination.CoordinationView`.

- [ ] **Step 1: Write the failing privacy matrix**

`TestCoordinationFilterIntersectionHasNoAdminBypass` covers ordinary viewer, admin, unlinked viewer, sponsored principal, `CanRead=false`, and login/access errors for each child independently. Start with a fixture carrying hostile unique markers in every restricted field: repository/title/scope, child authorization/fingerprint, room/issue/PR, produced and consumed artifacts, dependency/merge order, integration subject and acceptance text, recovery/reason, incident, and child/family budget. Assert none of those markers survives; only `restrictedChildren: 1` is added. An allowed child's own fields retain exact core values except references to a restricted child are removed from its `DependsOn`, `Consumes`, produced/consumed artifact references, `IntegrationAcceptedHead`, and `IntegrationRelease`. Family totals and plan-budget fields are zeroed when any child is restricted; primary/integration rationale and acceptance text, integration attempts touching a restricted subject, and affected recovery are removed; no raw parent log event is written.

`TestCoordinationRouteUsesPrimaryGateThenFilters` proves an unlinked non-admin gets 404, an admin with primary access but no child B read gets A plus a restricted count rather than admin widening, a non-coordination room is 404, and `off` registers no route. `TestSponsoredConfigRepositoriesValidateAndKeyByPrincipal` pins repository shape/duplicate validation and the `system:<name>` lookup key; `TestSponsoredRepositoriesAreOnlyAnUpperBound` proves no GitHub login or admin substitution is synthesized.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/coordinationview/ ./internal/humanapi/ ./internal/config/ -run 'TestCoordinationFilter|TestCoordinationRoute|TestSponsoredConfigRepositoriesValidateAndKeyByPrincipal|TestSponsoredRepositoriesAreOnlyAnUpperBound' -count=1`
Expected: FAIL at compile and 404 for the new route.

- [ ] **Step 3: Implement fail-closed sanitization and wiring**

Deep-copy the two-child view before filtering. Resolve the viewer login separately per child and treat every false/error/empty login as restricted; do not pass an admin flag into `Filter`. For sponsored viewers, use only `Viewer.Repositories`. Filter every nested collection and cross-reference named in the test, clear integration releases whenever any child is restricted, and preserve only parent phase/reason as coarse bounded state. When any child is restricted, zero both `Plan.Budget` and `View.Budget`, and clear `Plan.Primary.Rationale`, `Plan.Integration.Acceptance`, and `Plan.Integration.BeforeDependentsRationale` so prose and subtraction cannot reveal restricted data. Register the factory Task scheme in the broker manager and wire `mgr.GetAPIReader()` into `Source` so typed reads never use a stale informer cache. Register the route only when mode is not off.

- [ ] **Step 4: Run package and full PR checks**

Run: `go test ./internal/coordinationview/ ./internal/humanapi/ ./internal/config/ ./internal/app/ -count=1 && task lint && task check`
Expected: PASS, 0 issues, exit 0.

- [ ] **Step 5: Commit, rebase, and open PR 1**

```bash
git add internal/coordinationview internal/humanapi internal/config internal/app
git commit -m "feat(humanapi): filter coordination projections by each repository reader"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-projection
gh pr create --title "feat(humanapi): per-viewer coordination projections" \
  --body "Internal core-view reader with read-only RBAC and read-time per-child GitHub filtering. No raw human view and no admin widening. Evidence: task check exit 0, task lint 0 issues."
```

---

## PR 2 — `feat/coordination-room`: parent summary, overview, needs, and resume

### Task 3: Distinct `flow.coordination` and existing card/overview projections

**Files:**
- Create: `internal/summary/coordination.go`, `internal/summary/coordination_test.go`, `internal/roomview/coordination.go`, `internal/roomview/coordination_test.go`
- Modify: `internal/summary/flow.go`, `internal/summary/summary.go`, `internal/humanapi/summary.go`, `internal/humanapi/rooms.go`, `internal/roomview/card.go`, `internal/roomview/overview.go`, `internal/roomview/overview_test.go`

**Interfaces:**
- Produces: `summary.Summary.Coordination *coordinationview.View`; `summary.Flow.Coordination *CoordinationFlow`; `func summary.AttachCoordination(s *Summary, v coordinationview.View)`.
- Produces: `CoordinationFlow{PlanVersion int32, PlanHash string, Nodes []CoordinationNode, Edges []CoordinationEdge, RestrictedChildren int}`; `CoordinationNode{ID, Kind, ChildID, Repository, Phase, Reason string, Roles []string, Room, IssueURL, PRURL string, Disabled bool, RequiredConfirmation string}`; `CoordinationEdge{From, To, Kind, Name, State string}`. `Kind` is `child|integration`; `RequiredConfirmation` is `parent|child|""`; edge kind is `artifact|integration`.
- Produces: `summary.CoordinationOverview{PlanVersion int32, RestrictedChildren int, Children []CoordinationChildState, RecoveryCode string}` on `humanapi.roomRow` and `roomview.Row`, with `CoordinationChildState{ID, Phase, Reason, IssueURL, PRURL string; DependsOn []string}`; no splitter field is added anywhere.
- Produces: `func roomview.CoordinationLines(v coordinationview.View, o Options) []string`, used by the card and later Slack renderer.

- [ ] **Step 1: Write failing before/after projection tests**

`TestCoordinationFlowBeforeAndAfterFiling` uses two children and one dependency. Before filing, assert planned child and final/pre-dependent integration nodes are disabled until parent and each child authorization exists, roles remain `[implementer, reviewer]` and integration is `triager`, and no parent implementer/merge node exists. After filing, the same nodes carry child phase/reason, room/issue/PR links, artifact edge `contract/consumer-v1-schema`, pre-integration acceptance only for the exact head, and final integration state. A dependent waiting for its landed artifact remains disabled with `artifact_pending`. Assert `split` and `parent` stay nil and no node has splitter part semantics.

`TestCoordinationProjectionDropsRestrictedIntegration` proves integration nodes/attempts touching a restricted child are absent and family-inferable totals are not rendered. `TestRoomSummaryCoordinationAttachesFilteredView` drives `summaryOf`, `room_summary`, and `roomRows` with B denied and asserts only A plus the restricted count reaches each response. Card and overview goldens assert the same allowed child states/recovery appear through existing renderers, restricted output says only the count, untrusted titles cannot form markup, and `Coordinating` is not described as merged or executing.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/summary/ ./internal/roomview/ ./internal/humanapi/ -run 'TestCoordinationFlow|TestCoordinationProjection|TestRoomSummaryCoordination' -count=1`
Expected: FAIL at compile (`CoordinationFlow` and `AttachCoordination` undefined).

- [ ] **Step 3: Implement the read-only projection and attach it once per request**

Derive nodes solely from the filtered plan/view, never TaskFacts. `AttachCoordination` creates `Flow` when needed and leaves its existing plan/nodes/ghosts/milestones untouched. `summaryOf`, `roomRows`, and `room_summary` call one `coordinationFor` helper per parent room, then attach the same value used by needs in Task 4. Add card lines for plan version/hash prefix, allowed dependencies/artifacts, integration subjects, visible budget, and one recovery; the row shows compact child state and restricted count without introducing a new list.

- [ ] **Step 4: Run the suites and commit**

Run: `go test ./internal/summary/ ./internal/roomview/ ./internal/humanapi/ -count=1`
Expected: PASS, with all existing split fixtures byte-identical.

```bash
git add internal/summary internal/roomview internal/humanapi
git commit -m "feat(summary): project coordination plans and progress in the parent room"
```

### Task 4: Unified parent needs and the existing resume brief

**Files:**
- Modify: `internal/summary/needs.go`, `internal/summary/needs_test.go`, `internal/summary/testdata/needs/cases.json`, `internal/humanapi/rooms.go`, `internal/humanapi/brief.go`, `internal/humanapi/needs_test.go`, `internal/roomview/brief.go`, `internal/roomview/brief_test.go`, `internal/roomview/testdata/brief/*`

**Interfaces:**
- Extends sibling `NeedsIn` with `Coordination *coordinationview.View` and `CoordinationStanding map[string]GitHubStanding`; the existing `Items`/`Ordered` functions remain the only derivation.
- Produces parent `plan_confirmation` IDs `<parent>/parent/v<version>` and `<parent>/<child>/v<version>` with the sibling's existing action kind `decide` and URL `<parent-room>#coordination`; recovery keeps `NeedRecovery`, ID `<parent>/<recovery.code>/v<version>`, action kind `retry`, and the same anchor. Zero `At` values participate in the existing deterministic sort. No new need or action kind is introduced.
- Extends `roomview.PlanVersion.Source` with `"coordination"` and `BriefIn` with `Coordination *CoordinationBrief`; `CoordinationBrief{Title string, RestrictedChildren int, Children []CoordinationBriefChild}` where each child is `{ID, Phase, Reason, IssueURL, PRURL string, DependsOn []string}`. The existing `/api/rooms/{id}/brief` and `room_brief` doors are unchanged.

- [ ] **Step 1: Write failing unified-fixture and brief tests**

Add parent cases to the existing `cases.json`: missing parent confirmation, missing child B authorization, one recovery, and no parent need when waiting only on artifact/integration. Assert only a viewer with the relevant repository write gets the action; sponsored viewers get a link but no decision. `TestCoordinationNeedsAreUnifiedAndDoNotDuplicateChildren` runs `/api/needs`, human `needs_list`, room rows, and `room_summary` against the same fixture and asserts identical keys/order: one parent item plus each child's ordinary need once. `TestCoordinationNeedsAndRowsHideRestrictedChild` gives a viewer GitHub read on A but not B and asserts no B need, B authorization action, B room/issue/PR/budget/artifact text, or B row detail appears, while the parent/A needs and the single restricted count remain.

`TestCoordinationBriefUsesPlanAndOneRecovery` asserts `Plan: coordination v3 <hash> · budget $12.75 ceiling`, parent title, changed milestones, one recovery/next action, links only to allowed child issues/PRs, and `1 restricted child` with no restricted fields. A no-cursor brief omits `Changed since`; hostile plan titles remain inert.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/summary/ ./internal/humanapi/ ./internal/roomview/ -run 'TestCoordinationNeeds|TestCoordinationBrief' -count=1`
Expected: FAIL because parent items and coordination brief data are absent.

- [ ] **Step 3: Extend the existing derivation and brief, not their routing**

`Items` appends parent confirmation/recovery clauses through `coordinationNeeds(in)` and never derives child merge/review/CI items from the parent view. `needsFor` fills per-repository standing using the existing identity/access resolvers, with no admin or sponsored write substitution. The brief maps the filtered view to `CoordinationBrief`, uses the first unified need as its blocker, and keeps the existing cursor and milestone pipeline.

- [ ] **Step 4: Run full PR checks and commit/push**

Run: `go test ./internal/summary/ ./internal/humanapi/ ./internal/roomview/ -count=1 && task lint && task check`
Expected: PASS, 0 issues, exit 0.

```bash
git add internal/summary internal/humanapi internal/roomview
git commit -m "feat(roomview): fold coordination into unified needs and resume"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-room
gh pr create --title "feat(summary): parent coordination views in existing room and attention surfaces" \
  --body "Distinct flow.coordination plus existing card, overview, needs/v1 and room_brief. No splitter reuse and no second inbox. Evidence: task check exit 0, task lint 0 issues."
```

---

## PR 3 — `feat/coordination-parent-ui`: diagram and UI-only decisions

### Task 5: Live coordination rail and room-list projection in the browser

**Files:**
- Create: `web/src/coordination.ts`, `web/test/coordination.test.ts`
- Modify: `web/src/summary.ts`, `web/src/rail.ts`, `web/src/room.ts`, `web/src/view.ts`, `web/src/app.css`, `web/test/rail.test.ts`, `web/test/room.test.ts`, `web/test/view.test.ts`, `internal/humanapi/ui/dist/*`

**Interfaces:**
- TypeScript mirrors the Task 2/3 JSON: `CoordinationView`, `CoordinationFlow`, `CoordinationNode`, `CoordinationEdge`, and `RoomRow.coordination`; no TypeScript-only fields become control input.
- Produces: `mountCoordinationPanel(root: HTMLElement): { set(v?: CoordinationView): HTMLElement }`; `renderCoordinationNode(n: CoordinationNode): HTMLLIElement`; and `confirmCoordination(input: CoordinationConfirmation): Promise<void>` wired in Task 6.

- [ ] **Step 1: Write failing DOM tests**

`draws a distinct plan and live coordination diagram` asserts two child nodes plus pre/final integration, disabled planned nodes before confirmation, exact dependency/artifact labels before and after filing, room/issue/PR links only for readable children, and no parent run or merge node. Query the DOM to prove no `.rail-part`, `.rail-parent`, or splitter chip is emitted and existing split tests are unchanged. `renders only restricted count for a denied child` asserts no hidden text/attribute contains its markers. `shows coordination in the room list` asserts compact state and one recovery, not a second needs list.

- [ ] **Step 2: Run the UI tests to verify RED**

Run: `cd web && npm test -- coordination rail view room && npm run typecheck`
Expected: FAIL because `flow.coordination` is unknown and no coordination panel exists.

- [ ] **Step 3: Implement the projection with existing rail vocabulary**

Reuse `glyphFor`, `personaLabel`, `tone`, `roomLink`, timestamps, and reduced-motion behavior. Add `.rail-coordination`, `.rail-coordination-node`, and `.rail-coordination-edge` renderers rather than calling splitter `parts()` or adding split chip classes. Planned nodes are disabled buttons; live child nodes link to their own room. `room.ts` mounts one panel beside the summary and refreshes it from the same `summary/v1` frame as the rail; `view.ts` renders the additive row field.

- [ ] **Step 4: Build and verify**

Run: `task ui:test && task ui:check`
Expected: typecheck and Vitest PASS; generated bundle committed and clean.

- [ ] **Step 5: Commit**

```bash
git add web/src web/test internal/humanapi/ui/dist
git commit -m "feat(web): draw the parent coordination plan and live dependency rail"
```

### Task 6: Token-forwarded draft/confirmation/recovery and parent controls

**Files:**
- Create: `internal/humanapi/coordination_write.go`, `internal/humanapi/coordination_write_test.go`, `internal/runrequest/coordination.go`, `internal/runrequest/coordination_test.go`
- Modify: `internal/factory/api/coordination.go`, `internal/factory/api/coordination_test.go`, `internal/humanapi/server.go`, `internal/app/broker.go`, `internal/mcpwire/mcpwire.go`, `internal/maku/localtools.go`, `internal/maku/client.go`, `internal/maku/coordination_checkout.go` (created here for draft opening only), `internal/maku/coordination_checkout_test.go`, `web/src/coordination.ts`, `web/src/api.ts`, `web/test/coordination.test.ts`

**Interfaces:**
- Produces on `runrequest.Factory`: `CoordinationDraft(ctx context.Context, accessToken, parent string, in coordination.CoordinationConfirmation, onBehalfOf string) (coordination.CoordinationConfirmation, error)`; `CoordinationConfirm(ctx context.Context, accessToken, parent string, in coordination.CoordinationConfirmation) (coordination.CoordinationConfirmation, error)`; `CoordinationRecover(ctx context.Context, accessToken, parent, code string, planVersion int32) error`. They forward the caller's token to core `PUT /v1/coordinations/{task}/draft`, `POST .../confirmations`, and `POST .../recovery`; no login is asserted by the broker.
- Produces `humanapi.Server.CoordinationWrites CoordinationGateway` with that exact three-method consumer interface. Routes are `PUT /api/coordinations/{task}/draft`, `POST /api/coordinations/{task}/confirmations`, and `POST /api/coordinations/{task}/recovery`; all strict-decode ≤128 KiB and are 404 while off.
- Produces `mcpwire.CoordinationOpen = "coordination_open"` as a local human-relay-only tool taking `{confirmation}` and returning `{parentTask, roomURL}`. It opens a draft only, never files or confirms. Its transport is `func (c Client) CoordinationDraft(ctx context.Context, parent string, in coordination.CoordinationConfirmation) (coordination.CoordinationConfirmation, error)`.
- Core factory draft accepts an optional transport `onBehalfOf` only for the existing sponsored Slack principal and resolves it through `SlackLinks` + `Logins`; human and linked-on-behalf actors still produce the exact core `Actor`. Neutral `CoordinationConfirmation` is unchanged.

- [ ] **Step 1: Write failing authority, transport, and stale-plan tests**

Assert draft is allowed in `plan` for a roomctl human and sponsored `on_behalf_of`, creates only the core parent draft, and is rejected without a linked identity. Parent/child confirmation and recovery require the web client; a roomctl bearer, sponsored token, Slack reply, or MCP tool cannot call them. The factory still performs parent/child maintainer+write checks. `onBehalfOf` is forbidden for humans and for any sponsored principal other than the configured Slack linker. No `run_create`, issue, AgentRun, merge, or new sponsored tool is called.

`TestCoordinationConfirmationStalePlanRefreshesWithoutWrite` submits v1 after v2 and asserts `stale_plan`, no changed confirmation/Task/run, and one fresh summary render. UI tests assert parent and child controls bind the exact current plan/hash/fingerprint, are disabled when `restrictedChildren > 0`, and show one recovery action only when the core proposes it. `coordination_open` returns a parent-room URL but has no confirm, file, merge, or recovery field.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/humanapi/ ./internal/runrequest/ ./internal/factory/api/ ./internal/maku/ -run 'TestCoordination(Draft|Confirm|Recover|Open)' -count=1 && cd web && npm test -- coordination`
Expected: FAIL at compile and missing routes/controls.

- [ ] **Step 3: Implement forwarding and exact-hash controls**

The broker forwards `p.AccessToken`, never a login or actor. Core resolves the human or linked Slack identity as it does for existing sponsored intake. Parent controls construct `CoordinationConfirmation` with the current full plan/hash, only the selected parent or child record, and `PlanningReconciliation{ReservedMicroUSD, SettledMicroUSD}` read from the current view; they invent no attempt/reservation/settlement ID and no AgentRun ID. Recovery sends only `{code, planVersion}` to the core's one-action endpoint. Errors refresh the summary rather than mutating local authority state.

- [ ] **Step 4: Run full PR checks and commit/push**

Run: `go test ./internal/humanapi/ ./internal/runrequest/ ./internal/factory/api/ ./internal/maku/ -count=1 && task ui:test && task ui:check && task lint && task check`
Expected: PASS, 0 issues, exit 0.

```bash
git add internal/humanapi internal/runrequest internal/factory/api internal/maku internal/mcpwire web internal/app
git commit -m "feat(coordination): confirm plans only in the parent UI"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-parent-ui
gh pr create --title "feat(web): parent coordination diagram and UI-only confirmation" \
  --body "Distinct live coordination rail and exact-hash parent/child controls. Token-forwarded core decisions; no Slack or MCP approval. Evidence: task check exit 0, task lint 0 issues."
```

---

## PR 4 — `feat/coordination-slack`: originate, edit, and follow without Slack decisions

### Task 7: Two-repository origin/edit through `coordination_plan` and the existing proposal

**Files:**
- Create: `internal/slackapp/coordination.go`, `internal/slackapp/coordination_test.go`
- Modify: `internal/slackapp/proposal.go`, `internal/slackapp/proposal_test.go`, `internal/slackapp/slack.go`, `internal/slackapp/broker.go`, `internal/slackapp/broker_test.go`, `internal/slackapp/app.go`, `internal/slackapp/app_test.go`, `internal/roomview/coordination.go`

**Interfaces:**
- Produces: `CoordinationProposal{ParentTask, PlanHash string, Version int32}`; `ProposalPayload.Coordination *CoordinationProposal \`json:"coordination,omitempty"\``. Existing `Plan`, `Hash`, `Author`, and `Rev` fields and legacy JSON bytes are unchanged. Exactly one of a legacy plan or coordination pointer is valid.
- Produces on `BrokerAPI`: `CoordinationPlan(ctx context.Context, in CoordinationPlanRequest) (CoordinationPlanResult, error)` and `CoordinationDraft(ctx context.Context, parent string, in coordination.CoordinationConfirmation, onBehalfOf string) (coordination.CoordinationConfirmation, error)`. Request is `{Text, Context, Primary string, Candidates []string, OnBehalfOf string; ID string \`json:"id,omitempty"\`; Version int32 \`json:"version,omitempty"\`}`, matching the core tool's `id?`/`version?`; result is `{Plan v1alpha1.CoordinationPlan, Hash string, Diagnostics []coordination.Diagnostic, Planning coordination.PlanningReconciliation}` exactly matching the core tool. Initial origin leaves ID/Version absent; replan sends the previous plan's ID and previous version+1.
- Produces: `explicitRepositories(text string) []string`, bounded to two unique names; `func (a *App) proposeCoordination(...)` and `replanCoordination(...)`, called inside the existing `propose`/`replan` branches and `editMu` critical section.

- [ ] **Step 1: Write failing origin/edit parity tests**

`TestSlackCoordinationOriginUsesTheSharedPlanner` sends text naming `Smana/public-contracts` then `Smana/public-consumer`; assert `primary=Smana/public-contracts`, ordered candidates, one governed fake call, `on_behalf_of`, the exact typed plan/hash/diagnostics/planning returned, and a separate `CoordinationDraft` carrying those values. Assert one parent draft and proposal, one existing `Threads.Put` mapping the parent room to the origin thread, and no parent/child issue, child Task, AgentRun, `run_create`, or Slack confirmation. An unserved candidate or a third explicit repository makes zero model calls. Zero/one explicit repository follows the legacy intake tests byte-for-byte.

`TestSlackCoordinationReplyEditsTheSameSnapshotAndMessage` asserts the outgoing `CoordinationPlanRequest` carries the previous plan's `ID` and `Version == previous.Version+1`, omits both on initial origin, keeps primary unchanged, includes both replies in bounded context, performs one `chat.update`, marks changed sections, and posts no new proposal. Concurrent replies serialize exactly as the sibling test. `primary_requires_new_parent` yields a fixed start-new-mention line and no draft mutation. `TestSlackCoordinationDraftRoomPending` makes the first `room_summary` return not-found and asserts one bounded `Parent room is being prepared` proposal using the just-returned typed attempt, with no second planner/draft call and no background retry. The metadata holds only `{parentTask, planHash, version}`; recovery compares it to the current filtered parent summary, never rendered text.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/slackapp/ ./internal/roomview/ -run 'TestSlackCoordination|TestCoordinationProposal' -count=1`
Expected: FAIL at compile and no coordination proposal branch.

- [ ] **Step 3: Implement the union payload by extending existing mechanics**

Refactor proposal post/update/recovery only enough to select legacy `proposalSections` or `coordinationSections` from the same `ProposalPayload`; do not add another message store, interaction route, hash implementation, or update fallback. Two explicit repositories select coordination and first-primary; all other text keeps the current flow. After every accepted attempt, call the separate draft gateway and record the parent-room mapping through the existing `Threads.Put(ctx, parentTask, Thread{Channel, TS, At})` path so later webhooks can find the thread. Render the current filtered parent view with a single `Open the parent room to confirm` URL button and no Confirm/Cancel buttons. If the reconciled Room is not yet readable, render only the just-returned typed attempt and the fixed `Parent room is being prepared` line; the next ordinary reply/webhook re-reads it, with no planner/draft replay or retry goroutine.

- [ ] **Step 4: Run package tests and commit**

Run: `go test ./internal/slackapp/ ./internal/roomview/ -count=1`
Expected: PASS, including all legacy metadata, proposal, approval, and intake tests.

```bash
git add internal/slackapp internal/roomview
git commit -m "feat(slackapp): originate and edit coordination through the shared planner"
```

### Task 8: Channel-filtered follow, unified answers, and no Slack approval

**Files:**
- Modify: `internal/slackapp/coordination.go`, `internal/slackapp/coordination_test.go`, `internal/slackapp/proposal.go`, `internal/slackapp/app.go`, `internal/slackapp/answers.go`, `internal/slackapp/answers_test.go`, `internal/slackapp/slack.go`, `internal/roomview/coordination.go`, `internal/roomview/coordination_test.go`, `internal/factory/reconciler/coordination.go`, `internal/factory/reconciler/coordination_test.go`

**Interfaces:**
- Extends `MarkerPayload` with `Coordination string \`json:"coordination,omitempty"\``, the parent Task; existing draft/approval metadata is unchanged.
- Produces: `func coordinationWatchers(cfg *factoryconfig.Config) []v1alpha1.Member` where `factoryconfig` is `github.com/Smana/maku/internal/factory/config`, returning one `watcher` member `system:<name>` for each existing sponsored principal with `onBehalfOf.slackLinks` enabled. The parent reconciler includes these members in `rooms.Ensure` and idempotently adds a missing watcher to an existing parent Room, without changing owner, driver, repository, approvals, or any child Room.
- Produces: `type SlackCoordinationProjection struct { Phase, Reason, RoomURL string; Children []SlackCoordinationChild; Integration []coordination.IntegrationAttemptView; Recovery *v1alpha1.RecoveryProposal }`; `func projectCoordination(v coordinationview.View, ch Channel, roomsURL string) (SlackCoordinationProjection, bool)`, where false means no parent event. Full projection requires `RestrictedChildren == 0` and every displayed child repository in `ch.Repositories`; partial channels or any restricted child return only the first three fields.

- [ ] **Step 1: Write failing channel and no-authority tests**

`TestSlackProjectionFullServesEveryChild` uses an A+B channel and asserts child states, exact artifact/integration subjects, and one recovery. `TestSlackProjectionPartialIsCoarseOnly` uses A only and asserts only phase/reason/room link. `TestSlackProjectionUnservedPrimaryDropsIntakeAndEvents` asserts no post and no intake/model call. `TestSlackProjectionRecomputedAfterChannelOrAccessChange` first renders full, then removes B and revokes its read: the next webhook and `status` answer are coarse with no B details and no previously rendered child block is updated back into visibility. `TestSlackProjectionRoomLogUnavailableIsReadOnly` renders `rooms unavailable` and changes no execution state.

`TestParentRoomAdmitsOnlyConfiguredSponsoredWatcher` proves the configured Slack principal can read the parent through ordinary room membership, an unrelated sponsored principal cannot, an older parent gains only the missing watcher idempotently, and no child Room changes. `TestSlackReplyAfterParentUIFilingAnswersWithoutReplanning` moves the current view to both child issues filed, asserts the proposal becomes the explicit `factory_filed` marker text `Filed through the parent UI; merges stay on GitHub`, and a later `status` reply makes no planner call. Before filing, replies still edit the same plan.

`TestSlackCoordinationAnswersUseUnifiedProjection` asserts `status`, `needs me`, `what changed`, and `the pull request` use the same projection/unified needs and parent PR answers list allowed child PRs only. `TestSlackCoordinationNoApprovalForgedActionsAreRefused` sends forged `factory_proposal_confirm` and `factory_proposal_cancel` actions and asserts the fixed parent-UI line with no `run_create`, draft confirmation, recovery, approval, or merge. Existing `forge.push` approval tests remain unchanged, and no new action ID, sponsored tool, public route, or webhook type appears.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/slackapp/ ./internal/roomview/ -run 'TestSlackProjection|TestSlackCoordinationAnswers|TestSlackCoordinationNoApproval|TestParentRoomAdmitsOnlyConfiguredSponsoredWatcher|TestSlackReplyAfterParentUIFilingAnswersWithoutReplanning' -count=1`
Expected: FAIL because generic parent lines bypass the channel intersection and coordination payload actions are unhandled.

- [ ] **Step 3: Implement read-time projection on every path**

Add `coordinationWatchers` to the parent Room's existing `rooms.Ensure` call and patch only a missing watcher into older parent Rooms; no new principal, config flag, Task phase, run, or Room-creation route is introduced. After the existing meaningful/channel/thread checks, detect a coordination parent and call sponsored `room_summary` for each delivery/answer, then apply `projectCoordination`. Keep `webhook.Meaningful` and `Channel.notifies` as the only notification policy. Reuse `CoordinationLines` for full output and fixed coarse text otherwise. Recover proposal pointers with the same `threadProposal` scan; a stale pointer re-renders the current view and no action uses a rendered message as control input. Once every child has a factory issue URL, update the one proposal to the tested `factory_filed` marker so subsequent replies use the five-question path rather than replanning; this marker records UI filing, never a Slack decision.

- [ ] **Step 4: Run full PR checks and commit/push**

Run: `go test ./internal/slackapp/ ./internal/roomview/ -count=1 && task lint && task check`
Expected: PASS, 0 issues, exit 0.

```bash
git add internal/slackapp internal/roomview
git commit -m "feat(slackapp): follow coordination only in channels serving every child"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-slack
gh pr create --title "feat(slackapp): coordination originate, edit and filtered follow" \
  --body "Two explicit repositories use coordination_plan and the existing proposal. Parent UI confirms. Full/coarse/dropped channel projection and unified answers; no Slack filing, approval or merge. Evidence: task check exit 0, task lint 0 issues."
```

---

## PR 5 — `feat/coordination-checkout`: exact worktrees and a versioned manifest

### Task 9: Filtered checkout document and route

**Files:**
- Create: `internal/coordinationview/checkout.go`, `internal/coordinationview/checkout_test.go`, `internal/humanapi/coordination_checkout.go`, `internal/humanapi/coordination_checkout_test.go`
- Modify: `internal/humanapi/server.go`, `internal/maku/client.go`, `internal/maku/coordination_checkout.go`, `internal/maku/coordination_checkout_test.go`

**Interfaces:**
- Produces: `type CheckoutDocument struct { APIVersion string \`json:"apiVersion"\`; Kind string \`json:"kind"\`; coordination.CheckoutManifest; IntegrationAttempts []coordination.IntegrationAttemptView \`json:"integrationAttempts"\` }`; `APIVersion` is exactly `coordination-checkout/v1`, `Kind` exactly `CoordinationCheckout`, and the embedded core manifest is unchanged.
- Produces: `func Checkout(v View) (CheckoutDocument, error)` and `var ErrCheckoutRestricted error`, returning that error when `RestrictedChildren != 0`; `func ManifestHash(d CheckoutDocument) string` over bounded canonical JSON after local absolute worktree paths are filled.
- Route: `GET /api/coordinations/{task}/checkout` returns the document with relative child worktree IDs. `func (c Client) CoordinationCheckout(ctx context.Context, parent string) (coordinationview.CheckoutDocument, error)` reads it; no partial manifest is returned.

- [ ] **Step 1: Write failing lineage/privacy tests**

`TestCheckoutDocumentLinksAllFamilyState` asserts `parentTask`, plan version/hash, each child `{repository,worktree,room,issue,pr,dependsOn,artifacts,headSHA|mergeCommitSHA}`, and all filtered integration attempts with exact subjects/manifest hashes. `TestCheckoutRefusesAnyRestrictedChild` covers denied read and lookup failure and expects 404 with no repository/child fields in the body. Wrong URLs, both SHA kinds on one child, and an unreadable source fail closed. Off remains 404.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/coordinationview/ ./internal/humanapi/ ./internal/maku/ -run 'TestCheckoutDocument|TestCheckoutRefuses|TestCoordinationCheckoutRoute' -count=1`
Expected: FAIL at compile.

- [ ] **Step 3: Derive the document from the already filtered view**

Order children by filtered `MergeOrder`; attach produced artifacts and exact consumed references to the appropriate child, include pre/final integration attempts, and validate GitHub issue/PR URLs. Keep worktree paths relative until the CLI knows its deterministic root. This is a local file data format, not a Kubernetes Kind or CRD.

- [ ] **Step 4: Run tests and commit**

Run: `go test ./internal/coordinationview/ ./internal/humanapi/ ./internal/maku/ -count=1`
Expected: PASS.

```bash
git add internal/coordinationview internal/humanapi internal/maku
git commit -m "feat(coordination): expose a fully authorized checkout manifest"
```

### Task 10: Detached per-repository worktrees, CLI, and local MCP checkout

**Files:**
- Modify: `internal/maku/coordination_checkout.go`, `internal/maku/coordination_checkout_test.go`, `internal/maku/client.go`, `internal/maku/localtools.go`, `internal/maku/mcp_test.go`, `internal/mcpwire/mcpwire.go`, `internal/app/maku.go`, `internal/app/maku_test.go`

**Interfaces:**
- Produces: `type CoordinationCheckout struct { Git Git; Workspace string; Workspaces map[string]string; Document coordinationview.CheckoutDocument; Confirm func(ctx context.Context, files []string, more int) (bool, error) }`; `func (c CoordinationCheckout) Run(ctx context.Context) (CoordinationCheckedOut, error)`.
- Produces: `CoordinationCheckedOut{Root, ManifestPath string, Children []CoordinationWorktree, Reused bool}` and `CoordinationWorktree{ChildID, Repository, Path, SHA string, Reused bool}`.
- Commands: `maku coordination checkout <parent> [--workspace owner/name=path]` (repeatable); `mcpwire.CoordinationCheckout = "coordination_checkout"` as a local human-relay tool with closed `{parent, workspaces?}`. Current directory is the primary clone; every non-primary repository needs its flag/workspace entry. Missing clones refuse with `gh repo clone owner/name`.

- [ ] **Step 1: Write failing exact-SHA and safety tests**

`TestCoordinationCheckoutCreatesDetachedVerifiedWorktrees` uses root `../<primary-directory>.<parent>` and `<root>/<childID>`; assert open children fetch `agent/<childTask>` and equal manifest PR heads, merged children fetch the remote default branch and require the merge SHA to be an ancestor, and every add is `worktree add --detach <path> <verifiedSHA>`. The written `maku-coordination.json` has absolute worktrees, `coordination-checkout/v1`, exact lineage/artifacts/integration attempts, and a stable manifest hash. A second identical call verifies and reuses both without rewriting them.

`TestCoordinationCheckoutMovingRemoteAndStaleManifestRefuse` covers remote movement before add, a changed plan/head against an existing manifest, and a merge SHA no longer on the default branch. Table-test wrong/multiple origins, missing clone, restricted manifest, symlink/path escape, flagged files without forms, declined combined confirmation, non-ASCII paths, and failure after the first worktree. Assert no `checkout`, `switch`, `reset`, branch creation/update, hook, smudge, implicit clone, or write to the initiating dirty tree occurs; the error names an incomplete new root rather than deleting or updating it.

- [ ] **Step 2: Run the tests to verify RED**

Run: `go test ./internal/maku/ ./internal/app/ -run 'TestCoordinationCheckout' -count=1`
Expected: FAIL at compile and `unknown command "coordination"`.

- [ ] **Step 3: Compose the existing safe helpers**

Reuse `originRE`, `revParse`, `freePath`, `listWorktrees`, `lockRoom`, `Checkout.flaggedFiles`, and `RunGit`; do not fork their checks. Resolve/fetch/verify every child first and collect the union of flagged files prefixed by child ID. Ask once, then recheck paths and SHAs before creating. Write the manifest only after all worktrees verify, using a same-directory temporary file and atomic rename. Reuse only worktrees whose current HEAD equals the exact manifest SHA and whose existing document hash matches.

- [ ] **Step 4: Run full PR checks and commit/push**

Run: `go test -race ./internal/maku/ ./internal/app/ -count=1 && task lint && task check`
Expected: PASS, 0 issues, exit 0, including all existing single-room checkout tests.

```bash
git add internal/maku internal/mcpwire internal/app
git commit -m "feat(maku): check out coordination children at verified commits"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-checkout
gh pr create --title "feat(maku): safe per-repository coordination checkout" \
  --body "Detached exact-SHA worktrees and coordination-checkout/v1 with full lineage and integration state. Existing unsafe-path/config confirmations; no current-checkout mutation and no partial family. Evidence: task check exit 0, task lint 0 issues."
```

---

## PR 6 — `feat/coordination-experience-docs`: bounded observability and offline release gate

### Task 11: Metrics, docs, and O11/O12/O13 evidence

**Files:**
- Modify: `internal/metrics/metrics.go`, `internal/metrics/metrics_test.go`, `internal/humanapi/coordination.go`, `internal/slackapp/app.go`, `internal/slackapp/coordination.go`
- Modify: `docs/api.md`, `docs/cli.md`, `docs/slack.md`, `docs/security.md`, `docs/operations.md`
- Create: `docs/superpowers/plans/2026-11-05-v4-multi-repo-experience-maku-plan.md` (copy of this plan)

**Interfaces:**
- Produces OTel `rooms_coordination_views_total{outcome}` with `ok|restricted|unlinked|unverified|not_found`, `rooms_coordination_checkout_manifests_total{outcome}` with `served|restricted|unavailable`, and `slack_coordination_projection_total{outcome}` with `full|coarse|dropped`. The first two are served as `maku_rooms_coordination_views_total` and `maku_rooms_coordination_checkout_manifests_total`; `slack_coordination_projection_total` is served under its own name because `MakuName` does not map `slack_*`. No repository/viewer/channel/family/artifact label is added.

- [ ] **Step 1: Write failing metric and final offline tests**

Pin exact served names and closed label sets, including `MakuName("rooms_coordination_views_total") == "maku_rooms_coordination_views_total"` and `MakuName("slack_coordination_projection_total") == ""` with the latter scraped verbatim as `slack_coordination_projection_total`; assert no payload, viewer, channel, repository, plan text, or artifact bytes reaches metrics/logs. Complete the offline matrix in existing suites: O11 viewer×repository including admins/errors/raw logs and full/coarse/unserved Slack; O12 equivalent Slack/coding-agent calls through one fake governed route with effective identity, no `plan/v1` change, no Slack/MCP merge or second inbox; O13 both detached worktrees, exact manifest/integration state, unchanged dirty checkout, moving remote/wrong origin/restricted/flagged/stale refusals.

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `go test ./internal/metrics/ ./internal/coordinationview/ ./internal/humanapi/ ./internal/slackapp/ ./internal/maku/ -run 'TestCoordination|TestSlackProjection|TestMakuName' -count=1`
Expected: FAIL on missing instruments and any uncovered matrix assertion.

- [ ] **Step 3: Add bounded counters and write operator/security documentation**

Document the internal reader and filtering order, web-only confirmation, Slack two-repository routing and channel rule, unified needs/resume, checkout discovery/confirmation/stale behavior, off/plan/execute rollout, and every non-goal. Do not add an alert based on text or a new notification event.

- [ ] **Step 4: Run the complete gate and commit/tag**

Run: `task crd:check && task chart:check && task ui:test && task ui:check && task lint && task check`
Expected: all exit 0, lint 0 issues, existing splitter/intake/gate/UI fixtures unchanged.

```bash
git add internal/metrics internal/humanapi internal/slackapp docs
git commit -m "docs(coordination): document the parent experience and its offline proof"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-experience-docs
gh pr create --title "docs(coordination): parent experience, observability and offline proof" \
  --body "Bounded view/projection/checkout metrics and complete O11-O13 evidence, with operator/security docs. Evidence: task check exit 0, task lint 0 issues."
```

After merge, tag the next Maku minor and record its version and manifest-list digests for PR 7.

---

## PR 7 — ai-native-ref `feat/coordination-experience-off`: adopt, document, keep off

### Task 12: Released pin, read-only RBAC, sponsored intersection, dashboard, and reader docs

**Files:**
- Modify: `flux/sources/ocirepo-agent-factory.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml`, `tooling/base/agent-factory/slack-app/deployment.yaml`
- Modify: `infrastructure/base/room-broker/{app.yaml,retention-cronjob.yaml,config.yaml,rbac.yaml}`, `infrastructure/gcp-0/room-broker/config.yaml`
- Modify after the Slack proposal plan lands: `tooling/base/agent-factory/slack-bindings.yaml`, `scripts/ci/gen-slack-bindings.py`, `scripts/ci/tests/test-gen-slack-bindings.py`, `scripts/ci/tests/slack-bindings-fixtures/**`
- Create: `scripts/ci/tests/test-coordination-experience.py`
- Modify: `observability/base/agent-platform/grafana-dashboard-agent-room.yaml`
- Modify: `website/content/docs/reference/commands.md`, `website/content/docs/use/slack.md`, `website/content/docs/use/guide/{terminal-and-coding-agent,when-the-factory-needs-you}.md`, `website/content/docs/how-it-works/rooms.md`, `docs/runbooks/agent-factory/{18-factory-interfaces,19-factory-from-your-agent,22-slack}.md`

**Interfaces:**
- Consumes: PR 6's tag/digests and core PR 8's existing `coordination: {mode: off, publicOnly: true, maxChildren: 2}` in both configs.
- Produces: broker `get,list` Tasks/ConfigMaps only; generated `human.mcp.sponsored[].repositories` from the one Slack declaration, intersected with each channel at runtime; dashboard queries for `maku_rooms_coordination_views_total`, `maku_rooms_coordination_checkout_manifests_total`, and the verbatim `slack_coordination_projection_total`. No `maku_slack_*` series or proof repository/channel is declared and no `plan`/`execute` value is shipped.

- [ ] **Step 1: Pin the release and write the failing adoption gate**

Set chart and every Maku image to immutable `vX.Y.Z@sha256:…`, retaining Renovate comments. `test-coordination-experience.py` initially fails unless both strict configs are off, broker RBAC has only `get,list` Tasks/ConfigMaps, generated sponsored repositories match the declaration, and no new AgentRun role/audience/third repository/host edit appears. Run it before completing the edits and record the failure.

- [ ] **Step 2: Generate the sponsored upper bound and add the read-only resources**

Extend the sibling Slack generator rather than creating a second declaration: its existing App channels, factory sponsored repositories, and webhook repositories stay byte-compatible, and the broker sponsored entry gains the same repository list. Keep all proof-only channels out of this PR. Add dashboard panels for view outcomes, projection outcomes, and checkout manifests using exactly the three series named in Interfaces; no high-cardinality variable or `maku_slack_*` query.

- [ ] **Step 3: Write reader/operator docs without live claims**

Document `maku coordination checkout <parent> --workspace owner/name=path`, `coordination_plan`/`coordination_open`/`coordination_checkout` for coding agents, two-explicit-repository Slack origin and first-primary ordering, parent-UI confirmation, full/coarse/dropped Slack visibility, the single needs/resume path, manifest fields and `checkout_stale`. Operator pages cover read-only RBAC, generated sponsored repositories, off default, prerequisites, and owner-gated rollout. Site prose follows `docs-style.md`; no cluster/date/proof claim is added here.

- [ ] **Step 4: Verify and commit/open the PR**

Run: `git add scripts/ci/tests/test-coordination-experience.py && task docs && task check`
Expected: both exit 0, including the new suite and Slack drift tests; `git diff -- infrastructure/base/agent-gateway` is empty.

```bash
git add flux/sources/ocirepo-agent-factory.yaml tooling infrastructure observability scripts/ci website/content/docs docs/runbooks
git commit -m "feat(factory): adopt the coordination parent experience switched off"
git fetch origin && git rebase origin/main && git push -u origin feat/coordination-experience-off
gh pr create --title "feat(factory): adopt the coordination parent experience switched off" \
  --body "Pins the experience release, read-only broker RBAC, generated sponsored repository intersection, dashboard and reader/operator docs. Both configs remain off and no proof channel or gateway change is declared. Evidence: task docs and task check exit 0."
```

---

## Owner-gated live experience proof and PR 8 — `docs/coordination-experience-proof`

**Nothing below is an action until the owner explicitly says go.** PR 7, an off deployment, and plan review are not permission. Core activation and v4 items 3/4 must already be live and verified. The owner answer must name the cluster, `<owner>/public-contracts` as proposed primary, `<owner>/public-consumer`, both maintainers, a fully served Slack channel, a primary-only channel, an unserved channel, an unlinked non-admin viewer, the coding client, permission to force one pre-integration failure, and the bounded merge window. Missing any item stops the proof.

### Task 13: Two separate dependent families, diagram/attention/privacy/checkout evidence, and teardown

**Files:**
- Create only after evidence exists: `docs/runbooks/agent-factory/results-coordination-experience-<cluster>-<date>.md`
- Record: release/digests, owner approval, repositories, Slack channels and viewers, plan versions/hashes, before/after diagram captures, issue/Task/room/PR links, exact SHAs/artifact digest, integration manifests, unified needs/resume output, refusal output, checkout root/manifest, metrics/traces, and teardown.

- [ ] **Step 1: Ask for owner go and verify without mutation**

Record the complete answer. Verify PR 7 deployed off, core prerequisites on both repositories, hardened read-only integration manifests, anonymous exact artifact fetch, the sibling Slack proposal/approval release, and no parallel/private family in scope. Do not turn on `plan` to bypass a missing prerequisite.

- [ ] **Step 2: In `plan`, originate separately from Slack and a coding agent and capture pre-filing diagrams**

With owner approval, enable `plan` for the bounded window. In the fully served Slack channel, mention both repositories with contracts first and create the v1 schema plan. In a separate coding-agent session, call `coordination_plan` for the v2 schema plan and `coordination_open`. Assert equivalent typed diagnostics and planning identity, no issues/child runs, and distinct parent drafts. In each parent UI capture the planned roles/dependency/integration diagram with disabled unconfirmed nodes and no parent run/merge/split chips. Confirm parent and each child separately in the UI. Show that no Slack or MCP confirmation route exists.

- [ ] **Step 3: Execute the Slack-originated family and prove live diagram, recovery, and unified attention**

Switch to `execute` only for the approved window. File the parent plus two child issues and capture the same diagram now live. Merge A on GitHub, prove only the exact landed schema unlocks B, force pre-integration failure, and verify B cannot merge and A is untouched. In `maku needs`, coding-agent `needs_list`, the parent web panel, and Slack `needs me`, record the same single parent recovery item with no duplicate child operational items and no second inbox. Apply only the proposed action in the parent UI, rerun on the new exact head, merge B through its GitHub current-head gate, and require final integration before parent Done. Record pre/final subjects and the diagram after each transition.

- [ ] **Step 4: Execute the coding-agent family and prove resume, follow, checkout, and final integration**

Drive the second family through `coordination_plan`, edits, `needs_list`, and `room_brief`; merges remain on GitHub. After a cursor interval, resume and record plan vN/hash, changed milestones, one blocker/action, and allowed child links. Complete pre/final integration, then run `maku coordination checkout <parent> --workspace <owner>/public-consumer=<clone>` from a dirty primary clone with a sentinel branch/file. Assert two detached worktrees at exact verified merge SHAs, no current-tree change, one combined flagged-file confirmation if applicable, and `maku-coordination.json` containing full lineage plus final passed integration. Repeat for `Reused=true`; record the manifest hash and final integration state.

- [ ] **Step 5: Prove unauthorized viewer and Slack channel refusals**

As the unlinked non-admin, request parent summary and checkout: both are 404 with no parent/child details. Record that per-repository denied-read/admin matrices are covered offline because both live repositories are public. Attempt origin in the unserved channel and forward a parent event there: zero model calls, no intake, no parent details. In the primary-only channel, the same event and `status` answer contain only coarse parent state and the room link; no B repository/scope/artifact/PR/budget. Fully served output contains both. Confirm no Slack plan confirmation, approval, recovery, or merge control appears.

- [ ] **Step 6: Restore off and state exact non-claims**

Restore both configs and any proof channel declarations to their previous values/off. Verify no new coordination family can be drafted/filed and an ordinary single-repository task still works. The report states exactly: **two public repositories/two children/one file dependency proven twice, independently from Slack and a coding agent; parent before/after diagrams, unified needs/resume, privacy/channel refusals, and detached checkout with final integration proven**. Independent parallel children remain only offline-tested; private integrated families remain unproven; fleet, atomic merges, distributed rollback, arbitrary fan-out/artifacts, and cross-factory remain out of scope.

### Task 14: Results, ADR, status, and final verification

**Files:**
- Modify: `website/content/docs/status.md`, `website/content/docs/decisions/_index.md`
- Create: `website/content/docs/decisions/0062-multi-repository-coordination.md` (renumber if sibling ADRs 0060/0061 or later have landed), `docs/runbooks/agent-factory/results-coordination-experience-<cluster>-<date>.md`

- [ ] **Step 1: Write the evidence and decision record**

The results file links every command/output or machine-readable transcript and contains no token, secret, unredacted personal data, or hidden private plan. The ADR records MR13–MR15, first-explicit-primary Slack routing, pointer-only coordination metadata, UI-only decisions, read-time intersection, and detached checkout. The status page moves only the parent experience row to the proven state with evidence and explicitly retains parallel/private/fleet limitations; it does not broaden the core's claim.

- [ ] **Step 2: Verify and open PR 8**

Run: `task docs && task check`
Expected: both exit 0, including absolute host-link and doc-path checks.

```bash
git add website/content/docs docs/runbooks/agent-factory/results-coordination-experience-*.md
git commit -m "docs(status): record the two-repository parent experience proof"
git fetch origin && git rebase origin/main && git push -u origin docs/coordination-experience-proof
gh pr create --title "docs(status): record the two-repository parent experience proof" \
  --body "Two dependent public families driven separately from Slack and a coding agent, with parent diagrams, unified attention, privacy/channel refusals, checkout/final integration and teardown to off. Parallel children and private families remain unproven. Evidence: task docs and task check exit 0."
```

---

## Self-review

**1. Spec coverage for the experience subset.**

| Requirement | Owning task/test |
|---|---|
| Parent plan confirmation and live roles/dependency diagram, disabled planned nodes, no parent execution node | PR 2 Task 3; PR 3 Tasks 5–6; live Task 13 Steps 2–4 |
| Distinct coordination projection, existing rail vocabulary, never splitter chips/facts | PR 2 Task 3; PR 3 Task 5 DOM assertions |
| Parent room/summary/overview projections on Go, MCP, CLI, web, and Slack | PR 2 Task 3; PR 3 Task 5; PR 4 Task 8 |
| Per-viewer GitHub-read filtering for every nested child field, no admin widening, fail closed | PR 1 Task 2 and Review Focus 1 |
| Slack only for channels serving every displayed repo; coarse partial and no unserved-primary event/intake | PR 4 Task 8 and Review Focus 2; live Task 13 Step 5 |
| Coding-agent/Slack originate/edit/follow through `coordination_plan`; no duplicate planner/proposal/interactivity | PR 3 Task 6 (`coordination_open`); PR 4 Tasks 7–8; O12 in Task 11 |
| Plan confirmation parent UI and merges GitHub; no Slack/MCP approval or recovery | PR 3 Task 6; PR 4 Task 8; live Task 13 Steps 2–5 |
| Unified needs/inbox/resume/meaningful notifications and one recovery | PR 2 Task 4 and Review Focus 5; PR 4 Task 8 |
| Filtered all-or-nothing checkout manifest and exact detached worktrees at verified commits | PR 5 Tasks 9–10 and Review Focus 4; O13 in Task 11 |
| Manifest links child room/issue/PR/dependencies/artifacts/integration state | PR 5 Task 9 `CheckoutDocument`; live Task 13 Step 4 |
| Existing unsafe-path/config confirmations and no current-checkout mutation | PR 5 Task 10 safety matrix |
| Core off adoption, docs/observability, owner-go cross-surface proof and teardown | PR 7 Task 12; live Tasks 13–14 |
| Two public repos/two children/one dependency, separately Slack and coding agent, before/after diagram, privacy, checkout/final state | Live Task 13; report Task 14 |
| Parallel children and private integrated families explicitly unproven | Global Constraints; live Task 13 Step 6; status Task 14 |

Deliberately excluded, with no silent gap: new Task/CRD/execution semantics (the only controller additions are authenticated draft identity transport and parent-room watcher membership), core planner internals, proposal/interactivity/metadata reimplementation, inbox ranking/routing or notification vocabulary, parent code/merge authority, Slack approval/merge, private/parallel live claims, fleet/cross-factory/arbitrary fan-out, and any new role/audience.

**2. Step scan and ambiguity closed.** Every implementation task has named failing assertions, a red command, a minimal implementation boundary, a green command, and a conventional commit; live evidence is committed by Task 14 after it exists. First-explicit-repository primary is deliberate and tested, avoiding an inferred Slack primary or new command language. Coordination Slack metadata points to the core snapshot because the core, not Slack, owns full versions; this resolves the single-repository 7 KiB metadata limit without another store. Confirmation reconstructs planning amounts from the current view and invents no identifiers. Non-primary checkout workspaces are explicit flags rather than guessed directories. Local `coordination-checkout/v1` embeds the exact core manifest and adds integration attempts rather than forking it.

**3. Cross-plan type consistency.** Core `CoordinationView` is wrapped anonymously as `coordinationview.View` with only `restrictedChildren`; it is not redefined. `summary.AttachCoordination` consumes that same value for flow, needs, rows, cards, Slack, and checkout. `CoordinationConfirmation`/`PlanningReconciliation` are used unchanged from draft through UI and Slack to the core. `summary.Need` retains sibling kinds/order/actions. `PlanVersion` adds only the `coordination` source. `CheckoutDocument` embeds exact `CheckoutManifest`/`CheckoutChild`; `IntegrationAttemptView` is reused unchanged. Legacy `plan/v1`, splitter fields, sponsored tools, and meaningful webhook types are not mutated.

**4. Review Focus.** All five highest-risk experience conditions have owning red/green tests: nested/admin filtering (1.2), channel/access revocation (4.8), stale confirmation (3.6), moving/stale checkout (5.10), and unified parent/child needs (2.4). Additional matrices cover raw-log leakage, restricted integration subjects and inferable budgets, partial manifests, forged Slack actions, hostile rendering, and incomplete checkout roots.

**5. Proportion.** Six Maku PRs isolate privacy, existing room/attention surfaces, browser decisions, Slack composition, checkout, and release evidence. The ai-native-ref PR only adopts off and documents; the live section runs exactly two dependent public families and one report. Steps specify interfaces, exact values, test names/assertions, commands, and commits rather than implementation transcripts. No third planner, second inbox, generic workflow engine, or parallel checkout safety implementation is planned.
