---
title: The factory's reviewer on public tasks runs on another model family
linkTitle: 0058 · Reviewer on another model
weight: 580
description: Proposed. Which model reviews a public task's pull request — GLM as today, Claude through a public-listener Anthropic route for the reviewer only, or another open-weight family — and how the choice is measured on the cohort. Owner decision pending.
lastVerified: 2026-10-16
---

**Status**: Proposed — owner decision pending
**Date**: 2026-10-16
**Deciders**: Smana (Platform Owner)
**Related**: [status, v2 gate "A reviewer on another model"]({{< relref "/docs/platform/ai-platform/status.md#v2-roadmap" >}}), [ADR-0054]({{< relref "/docs/decisions/0054-agent-model-providers-anthropic-direct.md" >}}), [hard-task cohort results](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-12-v2-hard-task-cohort-design.md#results)

---

## Context

A `pair` or `trio` task ends with a reviewer whose verdict gates the merge. The factory picks the
reviewer's tier as the other tier than the implementer's ([agent-platform factory design, Triage](https://github.com/Smana/agent-platform/blob/main/docs/factory.md)).
On `public` the tiers are Z.ai GLM: `tier-light` → `glm-5.3-flash`, `tier-standard` →
`glm-5.3-flashx`, `tier-frontier` and `agent-default` → `glm-5.3`.

**Today the reviewer runs the implementer's model, not only its family.** Every tier in the
factory's config still asks for `agent-default` (`tooling/base/agent-factory/helm-values-configmap.yaml`,
R11), so the "other tier" changes the reviewer's caps and not its model: both roles run `glm-5.3`.
A reviewer that shares the implementer's model shares its blind spots, and the cohort showed that
on hard tasks the gap follows the model (Claude 13 of 15 accepted, GLM-5.3 0 of 15 in either
harness).

The cohort could not judge a reviewer: A's reviewer approved nothing the maintainer rejected
(its two PRs were correct). The question is open, not answered.

Since agent-platform#129, `templates.<name>.reviewerModel` sets the reviewer's gateway name apart
from the tiers. Each option below is a value of it plus whatever the gateway must serve.

---

## Decision Drivers

- The reviewer's errors independent of the implementer's: another family, not another size
- `public` content reaches only a processor whose terms we accept (ADR-0054)
- Spend per review measured, within the tier's USD caps
- Names, not models, cross the harness boundary: only listed logical names reach a model (gate AG12)

---

## Considered Options

### Option A: GLM for both roles

`reviewerModel` unset, or `tier-standard` (`glm-5.3-flashx`) to make the reviewer at least another size.

**Pros**:
- No gateway change, no new processor, no new key
- Cheapest: about $0.39 per million cohort-mix tokens on `glm-5.3`, $0.11 on `glm-5.3-flashx`

**Cons**:
- Same family: correlated mistakes, the property the gate exists to break
- `glm-5.3-flashx` is a smaller model judging a larger one's work

### Option B: Claude reviewer for public tasks (recommended)

A public-listener Anthropic route serving one new logical name to the reviewer role only.

**Pros**:
- Another family, and the one that accepted 13 of 15 cohort tasks
- No new processor: Anthropic already holds `internal` data under ADR-0054, a stricter class than
  `public`
- Spend neutral on Sonnet: $0.39 per million cohort-mix tokens, the same as `glm-5.3`

**Cons**:
- Public-class repository content goes to a second provider, under Anthropic's commercial terms
- A second spend line on `public`, which needs its own budget bucket
- A fifth logical name, and a route restricted by role

### Option C: another open-weight family through another provider

**No other family exists in the gateway catalog.** The agent router's `public` listener serves only
Z.ai. Two routes would add one:

- **OpenRouter** (ADR-0054's optional public backend, documented but not built): Qwen, DeepSeek or
  Kimi models behind one key.
- **The in-cluster vLLM stack** (ADR-0003): Qwen3-8B and qwen-coder on ai-gateway, never on the
  agent router.

**Pros**:
- Another family without a frontier provider; vLLM keeps the data in the cluster

**Cons**:
- OpenRouter is a second processor with an upstream we do not choose per request
- An 8B model is too small to judge a frontier model's diff; vLLM needs GPU nodes up for every review
- No cohort evidence for any of these families

---

## Spend estimate

From the cohort's token mix (arm A: 94% cache reads, 4% uncached input, 2% output) and the phase J
price overlay (`meter.prices`, read 2026-10-16). Uncached Claude input is priced as a cache write,
the safe direction.

| Model | USD per M tokens | 160 K-token review (#2267's reviewer) | 500 K-token review | 30 reviews at 500 K (15 tasks, 2 rounds) |
|---|---|---|---|---|
| `glm-5.3-flashx` (A) | 0.11 | $0.02 | $0.06 | $1.65 |
| `glm-5.3` (A, today) | 0.39 | $0.06 | $0.19 | $5.80 |
| `claude-sonnet-5-5` (B) | 0.39 | $0.06 | $0.20 | $5.90 |
| `claude-opus-5-5` (B variant) | 0.79 | $0.13 | $0.39 | $11.80 |

Each fits the reviewer's `frontier` caps (`runUSD` 6.80, `taskUSD` 13.60) with room to spare.

---

## Decision Outcome

**Recommended option**: "Option B" with `claude-sonnet-5-5`, owner decision pending.

**Rationale**: It is the only option that changes the family on evidence we already have, and it
costs what today's reviewer costs. Its data-class question is narrower than it looks: ADR-0054
already sends `internal` data to the same provider, and `public` content is in public
repositories. What the owner decides is therefore a second spend line on `public`, not a new
processor.

**The owner's decision**: whether public-class reviews may be sent to Anthropic, and under
which daily cap.

### What B needs

| Where | Change |
|---|---|
| ai-native-ref, `infrastructure/base/agent-gateway/` | An `AgentgatewayBackend` `anthropic-review` on the `public` listener with one alias, `review-claude` → `claude-sonnet-5-5`, and a `model` transformation listing only that name; the Anthropic key from OpenBao `agents/anthropic` (C1: no new key shared with humans) |
| ai-native-ref, agentgateway policy | `review-claude` authorized only for a reviewer-role token (the role is in the audience, ADR-0042); an implementer asking for it gets the 400 every unlisted name gets |
| ai-native-ref, budgets | Its own per-provider token bucket on `public` (ADR-0054, Consequences) and a daily cap the owner sets |
| ai-native-ref, gates | AG12 learns the fifth name on `public`; a new check refuses `review-claude` on any role but reviewer; AG10 already has the Sonnet price row |
| agent-platform | `review-claude` added to the C5 logical names `reviewerModel` accepts; then `templates.pair.reviewerModel: review-claude` and the same for `trio` |

---

## Measurement plan

Run before the change becomes the default, on the next **N = 20** `pair` tasks of the hard-task
cohort's classes (`scripts`, `tests`, `dashboards`). Each task gets both reviews of the same head:
today's (`glm-5.3`) and the candidate's, the candidate in shadow (its verdict recorded, never
gating).

| Measure | Definition | Pass for the candidate |
|---|---|---|
| Agreement with the human | The reviewer's verdict (`approve` / `changes`) against the maintainer's merge or rejection of that head | At least today's reviewer's, and no approve the maintainer then rejected |
| Tokens per review | Input, cached and output, per review run, from the meter | Recorded; no target |
| USD per review | The meter's price per served model (phase J) | Within the tier's `runUSD` |

Twenty tasks only tell apart large differences. The human verdict must be the maintainer's, not the
operating agent's (the cohort's limit). If the candidate passes, `reviewerModel` moves to it; if
not, the record moves to Option A and the gate closes.

---

## Consequences

### Positive

- The reviewer's mistakes stop being the implementer's
- `reviewerModel` makes the reviewer's model a config line, independent of the tier-routing gate

### Negative

- B: `public` content leaves for Anthropic; a second spend line to watch on `public`
- B: one more role-restricted name the gateway gates must keep honest

### Neutral

- A remains one config value away: `reviewerModel` unset

---

## References

- agent-platform [#129](https://github.com/Smana/agent-platform/pull/129): `templates.<name>.reviewerModel`
- [Z.ai pricing](https://docs.z.ai/guides/overview/pricing), [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing)
