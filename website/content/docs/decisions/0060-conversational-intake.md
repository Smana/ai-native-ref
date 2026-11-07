---
title: A request in plain words becomes a governed plan before any issue is filed, through one planner for every channel
linkTitle: 0060 · Conversational intake
weight: 600
description: Accepted. Natural language replaces the command and field grammars, but a confirmed issue still creates the room. One planner in the broker serves Slack and coding agents alike, its issues pass the existing validator, and configuration, not the model, fixes roles and money. Its one model call is public text only, through the AI Gateway under its own client identity. A planner per channel was rejected.
lastVerified: 2026-11-05
---

**Status**: Accepted
**Date**: 2026-11-05
**Deciders**: Smana (Platform Owner)
**Related**: [design, decisions CD1 to CD18](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-05-v3x-conversational-devex-design.md#decisions), [the planner's model call](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-05-v3x-conversational-devex-design.md#model-call), [ADR-0049]({{< relref "/docs/decisions/0049-room-client-and-human-auth.md" >}}), [ADR-0059]({{< relref "/docs/decisions/0059-factory-from-your-coding-agent.md" >}})

---

## Context

Work reaches the factory as an issue. Slack drafts one from a mention with a keyword composer, and a
coding agent drafts one with its own model through `issue_draft` ([ADR-0059]({{< relref "/docs/decisions/0059-factory-from-your-coding-agent.md" >}})).
Both ask the person to speak a grammar: a command, a field, an `owner/repo`. Each channel also reads
the request its own way, so the same sentence can become two different issues depending on where it
was typed.

What was missing is one reading of a request, shared by every channel, that proposes the repository,
the issue and its class, shows its evidence, and leaves the filing and the money where they already
are.

---

## Decision Drivers

- The issue stays the task's snapshot and audit text: no room without one
- One reading of a request, so channels cannot drift
- No new validator, template or relaxed rule for what gets filed
- The model chooses nothing that costs money or changes the run
- One new data path, governed like every other model call: identity, route, bounds, audit

---

## Considered Options

| Question | Options | Chosen |
|---|---|---|
| What a confirmed request creates | An issue, a room directly from chat | An issue (CD1) |
| Where the reading happens | One boundary in the broker, a planner per channel | One boundary (CD2, CD18) |
| What the boundary emits | The existing draft, a plan-specific template | The existing draft (CD3) |
| Who fixes roles and budget | Configuration, the model | Configuration (CD17) |
| Whose model plans | The broker's, through the gateway; the coding agent's own | The broker's (CD18) |

- **A room straight from chat.** A room with no issue has no task, no gate and no `--mine`. Keeping
  the field grammar as the only path was rejected too: it is what people stumble over.
- **A planner per channel.** Two planners read the same sentence two ways, and "shared" is only true
  if the reading is shared. A second planner that also splits work after filing was rejected for
  the same reason: the in-task scoper stays the only decomposition after filing, and its scope is
  what the implementer, judge and reviewer all read.
- **A plan-specific template.** A second template, or a free-form body the factory parses later,
  is a second validator that drifts from the one the factory's intake, the API and Slack share.
- **A model that names its roles or budget.** It is a model that can widen them. Both numbers already
  exist and are already enforced; the class is the one lever the model needs, and it is shown.
- **The coding agent's model as the planner.** It would make the session's model an alternate
  planner. A private or self-hosted model in the broker was rejected as a second, ungoverned data path.

---

## Decision Outcome

Decided by the owner, with the design's numbering.

| # | Decision |
|---|---|
| CD1 | Natural language replaces the command and field grammars; **the issue does not go away**. A confirmed issue creates the room, and no surface offers `room_create` |
| CD2 | One pre-filing boundary, shared by Slack and coding agents, with one implementation. The in-task scoper stays the only post-filing decomposition |
| CD3 | Every proposed issue passes the existing draft validator and the broker's redactor: no new template, no relaxed title rule |
| CD17 | The model proposes the repository, the title, the body and the class. Roles and the budget ceiling come from the class's row in the broker's config and are echoed back by the broker; a model-named value for either is dropped and logged |
| CD18 | One planner, `intake_plan` in the broker, for both channels, through one governed model route. A coding agent passes context, never a plan. A deterministic composer exists as a degraded mode only, off by default |

**The data path.** The planner reads public text only: it runs for a repository GitHub reports as
public and on the broker's allowlist, and refuses a private one before any call. It calls the AI
Gateway in the cluster under its own client identity, `planner`, naming the one alias
`tier-frontier`, with temperature 0, at most 4 000 tokens of answer, a 20 s deadline and a 64 KiB
reply, decoded strictly and refused whole when it does not fit. It makes one call per attempt, with
no retry, under a per-requester daily cap. Its audit is one log line with the requester, the
surface, the repository, the plan's hash, the model, the token counts, the outcome and the duration:
the hash, never the request or the plan text.

**The degraded composer is not this feature.** With `fallback: composer` set, a planner that is
unavailable yields a template draft, and every surface labels it as one. It stays off by default and
is never described as the natural-language experience.

**In this deployment:** the planner is on in gcp-0, for one public repository,
`Smana/ai-native-ref`, with the `docs-links` class at a $2.00 ceiling. The base and aws-0 copies
keep it off.

**Amendment, 2026-11-07:** the planner is on in aws-0 too, with the same scope: one public
repository, `Smana/ai-native-ref`, the same class and ceiling. The owner's live session runs on aws-0
alone, with gcp-0 torn down, and the planner had no cluster to run on otherwise. Base keeps it off.
The planner's key, mounts and network rules were already in base on both clouds; only the switch
differs. This is the "another cluster" change the Neutral consequence below names, reviewed on its own.

**Amendment, 2026-11-07 (second repository):** the planner's allowlist adds `Smana/runlore-kb`, on
every copy, so that a coordination plan (`coordination: plan`, aws-0 only) can name the platform and
its knowledge base together. Nothing else widens: runlore-kb is public, the factory already serves
it (fenced to aws-0), and the class each plan names is still checked against that repository's own
class table. This is the "second repository" change the Neutral consequence below names.

---

## Consequences

### Positive

- The same sentence becomes the same plan in Slack and in a coding agent's session
- A person states the work in their own words; the plan shows why it chose the repository, and asks
  one question when several fit
- Filing, the maintainer check, the factory's caps and the scoper are unchanged

### Negative

- Private repositories get no planner: the developer files with `issue_draft` and `issue_file` and
  their own model, until an internal route exists
- A frontier-tier call per plan attempt, bounded by the daily cap and attributed to `planner` in the
  gateway's spend by identity

### Neutral

- The planner's reply is untrusted text: the broker validates it like any draft before showing it
- A second repository, or another cluster, is a config change reviewed on its own, not a copy of
  this one
