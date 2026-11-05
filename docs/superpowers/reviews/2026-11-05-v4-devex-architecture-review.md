# v4 DevEx architecture review: five findings, and where the work goes

**Date:** 2026-11-05 · **Verdict:** **GO WITH CHANGES** · **Reviewed:** three designs — the
[conversational developer experience](../specs/2026-11-05-v3x-conversational-devex-design.md), the
[Slack `forge.push` approval](../specs/2026-11-05-v3x-slack-push-approval-design.md) and the
[multi-repository coordination](../specs/2026-11-05-v4-multi-repo-coordination-design.md) — and their
five implementation plans, against the [v4 roadmap](../specs/2026-10-31-v4-roadmap-design.md#core) item
7 · **Closes into:** the [v3.x roadmap](../specs/2026-11-05-v3x-devex-roadmap-design.md) and [v4 owner
decision V7](../specs/2026-10-31-v4-roadmap-design.md#owner-decisions-2026-11-05) · **Nothing reviewed
here is built**

> **This is a record, not evidence.** No implementation, no switch-on and no live session existed when
> the review was taken, and none is claimed by it. Every state named below is *designed* or *planned*.

## Verdict

**GO WITH CHANGES.** The four designs are sound in their parts: each one names its boundary, its
closed vocabulary and its switch, and each one can be proven offline before a cluster is touched. The
problems were in how the parts were arranged — the release they sat in, the vocabulary they shared with
a neighbour, where a parent's durable state lived, which documents an approval amendment obliges, and
where planning stops and filing begins. Five findings, all design-level, none of them an argument to
drop an increment.

Accepting the changes produced four release-shaping resolutions:

1. **v3.x and v4.0 split the work.** The developer-experience increments ship on the released v3
   platform ([v3.x roadmap](../specs/2026-11-05-v3x-devex-roadmap-design.md)); v4.0 keeps "anyone can run it".
2. **Multi-repository coordination becomes a v4.0 target** with its design and switched-off build
   allowed beside that line, and activation still blocked by v4.0 items 3 and 4.
3. **The parent is coordination-only**, with its own discriminator, and no repository-local or merge
   authority.
4. **Slack decides `forge.push` only, bound to the branch**, with the absence of a commit SHA accepted
   by the owner and merging left on GitHub.

## Findings {#findings}

| # | Finding | Why it mattered | Resolution | Where it landed |
|---|---|---|---|---|
| F1 | **Roadmap inversion** — the DevEx designs deliver on the released v3 platform, but the roadmap places them in v4.0 item 7; and multi-repository coordination sits in v4.4 while needing only v4.0 items 3 and 4 | The dependency arrows and the release order disagreed with each other. A roadmap whose order contradicts its own dependencies is read as a promise it cannot keep, and the status page inherited the same inversion | DevEx becomes a v3.x line with its own roadmap; multi-repository coordination moves into v4.0 as an **activation-gated** core item and leaves v4.4; fleet campaigns stay in v4.4 | [v4 V7](../specs/2026-10-31-v4-roadmap-design.md#owner-decisions-2026-11-05), [v3.x roadmap](../specs/2026-11-05-v3x-devex-roadmap-design.md), [multi-repo §Roadmap position](../specs/2026-11-05-v4-multi-repo-coordination-design.md#roadmap-position-deliberately-resolved) |
| F2 | **Splitter collision** — a coordination family would reuse `Split`, `spec.parent`, `spec.split`, `status.split`, `TaskFacts.split/parent`, `agents.ogenki.io/parent` and `factory/child-of` | One-repository families and multi-repository families would become indistinguishable to intake, to the reconciler and to the room rail; the splitter's intake path can be re-entered by a label, so the collision was reachable by an operator action, not only by a bug | A coordination-only discriminator, and a stated prohibition on every splitter name ([MR2](../specs/2026-11-05-v4-multi-repo-coordination-design.md#decisions)); the splitter's own tests must pass unchanged | MR2, §Parent and child Tasks, offline proof O2 |
| F3 | **Parent durable state** — the parent's plan, confirmations, lineage and integration subjects risked living in the room log, in GitHub comments or in an in-memory graph | A controller restart or a crash between two issue writes would either lose the family or duplicate it, and a comment read by an agent would become an instruction. GitHub is not a control plane | `status.coordination` holds the current full plan snapshot, its hash and version, the confirmations, the lineage and the single recovery proposal; comments are **recovery evidence, never instructions**; filing is idempotent by factory-authored markers with an explicit `filing_incomplete` state | §Parent and child Tasks, §Issues and confirmations, §Operational states, proof O6 |
| F4 | **Slack approvals oblige amendments** — a Slack decision contradicts `docs/security.md` invariant 8 and the "no surface decides" wording in ADR-0049 and ADR-0059 FA7, and changes what runbooks 18 and 22 tell an operator | An amendment that lands only in code leaves every other document asserting the old prohibition, and the next reader believes the documents | One amendment design that rewrites the invariant to what remains true, keeps `TestSlackNeverDecides` (replies) and `TestSponsoredToolList` (tools), and adds `TestSlackDecidesForgePushOnly`; every affected document is amended in the same change and none is deleted | [approval design §Security analysis](../specs/2026-11-05-v3x-slack-push-approval-design.md#security), §Component impact, §Documentation amendments |
| F5 | **Planner, scoper and filing boundaries** — one design was drifting towards a shared plan object across single- and multi-repository work, and towards the planner having a say after filing | Two decomposers would disagree about the same issue, and a plan object widened after the fact either lies in its schema or breaks its hash. The scoper's scope is what the implementer, judge and reviewer all read | One governed planner route with **two typed outputs**: `plan/v1` stays single-repository, `coordination_plan` returns a `CoordinationPlan`. The scoper and its splitter remain the only post-filing decomposition. Filing stays per channel and separate from planning | [intake CD2/CD18](../specs/2026-11-05-v3x-conversational-devex-design.md#owner-decisions), [§seams](../specs/2026-11-05-v3x-conversational-devex-design.md#seams), MR4, §Seam to the shared intake contract |

## Minimal contracts

Every design was cut back to the smallest contract that carries its outcome. These are the ones the
review insisted on, and nothing beyond them:

| Contract | Minimal shape | Deliberately absent |
|---|---|---|
| The planner's call | One governed completion from the broker on its own gateway identity, a pinned alias, a deadline, a bounded reply, a strict decode, public text only | A retry loop, a second planner, a provider key in the broker, a private route, a cross-repository search |
| `plan/v1` | The repository, the issues, the class, roles and budget **from config**, the evidence, at most one question, one canonical hash over the material set | A plan object that survives, a post-filing role, enforcement between issues |
| `needs/v1` | One derivation over a room's facts and the caller's standing, a closed kind list, a fixed order, one action and one link per item | Ranking, routing, expiry, a stored inbox |
| The Slack decision route | One authenticated route, one class constant, the store's existing fence, the branch as the binding, closed result codes | Reason text, a tool on the MCP list, a second public path, a merge |
| The coordination parent | A discriminator, a frozen full plan snapshot with a hash and a version, separate confirmations, marker-idempotent filing | A parent run, branch, token, pull request or merge call; a workflow engine; automatic rollback |
| The dependency | One landed file reference at the producer's merge commit, with digests | Any other artifact kind, PR heads, prose handoffs |
| The switch | One logical value per increment, strict decoding, off by default | A per-channel matrix of independent enable flags |

## Scope cuts

The review removed work, it did not add any:

- **No third repository, no new AgentRun role, no new gateway audience.** The integration check uses
  the primary repository's existing read-only `triager` path, so no listener or trust policy grows.
- **No second Slack surface.** One `POST /slack/events`, one signature check, two request shapes.
- **No parent UI invented here.** The roles rail gains one projection; inbox, resume and notification
  rendering stay with the contract that owns them.
- **No multi-repository live claim.** Two public repositories, two children, one dependency. Parallel
  independent children are designed and tested offline and are **not** claimed live.
- **No planning for private repositories**, no internal planner route, no repository memory.
- **No fast-follow folded into a design.** Six defect-sized changes, each its own PR.
- **No configuration in five places.** A Slack channel's binding is one declaration with generated
  consumers and a drift gate.
- **No hidden state anywhere**: no stored plan, no stored inbox, no stored preference, no Slack state
  that is load-bearing (the store is the fence; a card is a view).

## Sequencing

The order the review accepted, and the reason for each edge:

1. **Slack `forge.push` approval**, first, because increment 4 consumes `chat.update`, the tagged
   metadata payload and the one interactivity branch. Without it, the proposal message would open a
   second public path and a second metadata format for the same app.
2. **Conversational intake**, next, because the resume brief reports the plan a task was filed from;
   there is no plan to report before the planner exists.
3. **Attention and resume**, then, because the thread answers from `needs_list`, which amends the
   App's read-only tool list once.
4. **Slack proposals**, last of the four, reading the three contracts above and adding no field to
   any of them.
5. **The fast-follow pack**, after the increment's live proof, one PR each.

Across releases: build offline, then one time-bounded live session per channel on an explicit owner
go, then teardown. Multi-repository coordination may be designed and built switched off at any point
in that order; **activating it is a capability gate**, not a version check — the existing class parser
is observation, never evidence that item 3 shipped.

## Refusal drills

Each design had to name the refusals that prove its boundary, because a boundary that is only
described is a boundary that will be crossed. These are the drills the review required, by owner:

| Drill | Owner | Proves |
|---|---|---|
| A click on an expired, superseded, already-decided or forged card is refused, and a non-approver, a non-writer and a four-eyes prompter each get their own line | approval design | The card is a view; the store is the fence |
| A private repository is refused before any model call, and the fake endpoint counts zero calls | intake plan | The public-only limit is a guard, not a convention |
| A plan changed after its render is refused by both filing paths; a secret, an oversized plan and a repository outside the candidate set are refused whole | intake plan | The confirmation binds what was shown |
| A coordination child on a repository the confirmer cannot write starts nothing; a parent push or merge attempt returns `coordination_read_only`; a mismatched child room or token is `cross_repository_lineage` | multi-repo design | No aggregated authority, no second merge authority |
| A producer artifact present at a PR head but different at the landed merge commit does not unlock the dependent; a stale plan confirmation changes nothing | multi-repo design | Dependencies are exact, confirmations are current |
| A splitter object and a coordination object can never be adopted by each other's intake | multi-repo design | The F2 discriminator holds under a label-driven path |
| A switch off restores today's behaviour with no data migration | every design | Rollback is one value |

## Owner resolutions, 2026-11-05

| Item | The owner's answer |
|---|---|
| Release split | **v3.x for developer experience, v4.0 for "anyone can run it".** The increments land on the released platform; each ships behind its own switch |
| Multi-repository | **A v4.0 target, out of v4.4**; fleet campaigns remain v4.4. Design and switched-off build may proceed; **activation and live proof blocked** until v4.0 items 3 and 4 ship |
| The parent | **A coordination-only parent Task with a discriminator**, no branch, no token-bearing run, no pull request and no merge call |
| Authority | **Per-child maintainer with repository write**, confirmed separately; a parent confirmation confers nothing on a child |
| Slack approval | **`forge.push` only, bound to the branch.** The owner accepted the absence of a commit SHA: no reliable pushed commit exists before the push. **Merging stays a review of the current head on GitHub** |
| The planner's reach | **Public repositories only** in v1 |
| The first multi-repository proof | **Two public repositories, two children, one dependency.** Parallel execution is designed but unproven |

## Closure

**Every finding is closed, by a change to the design record rather than by a change of mind.** The
spec reviews that followed this one closed the findings in place:

| Finding | Closed by |
|---|---|
| F1 | The [v3.x roadmap](../specs/2026-11-05-v3x-devex-roadmap-design.md) and [v4 V7](../specs/2026-10-31-v4-roadmap-design.md#owner-decisions-2026-11-05), which move the work and rewrite the order diagram, the item table and the open Slack question |
| F2, F3 | The multi-repository design's discriminator, durable parent status, marker-idempotent filing and `filing_incomplete` state, with offline proofs O1, O2 and O6 |
| F4 | The approval design's amended invariant 8, its decided owner signoff on the binding, and its documentation-amendment table |
| F5 | The conversational design's CD2 and CD18, its explicit `coordination_plan` seam, and the multi-repository design's "`plan/v1` is not reused unchanged" paragraph |

What remains open is implementation, not design: the plans are the record of how each increment is
built, and the [status page](../../../website/content/docs/status.md#v3x) is the one place that says
what is planned and what is available.
