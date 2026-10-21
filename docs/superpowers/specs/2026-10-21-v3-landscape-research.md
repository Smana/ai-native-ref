# Research: the field at 2026-10-21, for the v3 review

**Topic**: v3-landscape · **Conducted**: 2026-10-21 · **Researcher**: Claude (five web subagents, one
question each) · **Feeds**: the [v3 review](2026-10-21-v3-review.md) and its four designs

Primary sources were fetched where they exist (vendor docs and changelogs, specs, papers, release
pages); a page without a date is marked *acc.* (accessed 2026-10-21). Anything only a secondary
source supports is marked **UNVERIFIED** and is not to be cited as fact. The five questions were:
how other apps and agents interact with a factory, which loop and team shapes work, how tools and
models get fine-grained permissions, how to tune prompt and KV caching, and what the dark-factory
peers shipped that is worth reproducing.

## TL;DR

| Question | Finding |
|---|---|
| How do other agents and apps reach a factory? | Through an **MCP server that starts and reads sessions** (GitHub, Devin, Notion), with **MCP Tasks** as the poll-or-block shape; outbound through **signed, id-only webhooks** fetched on notify (Managed Agents); every product forces a **human-bound identity** to start work. A2A 1.0 is stable but, among the tools we care about, only Atlassian's Rovo connector consumes it |
| Which loops and teams work? | The field converged on **one writer plus a fresh-context judge**. The cheapest high-value addition is a **goal loop with a separate completion evaluator** (Claude Code and Codex `/goal`). Testers pay only when test quality is gated fail-closed. Agent teams, swarms and auto-generated multi-agent scaffolds lose on cost and outcome |
| How fine can permissions be? | agentgateway 1.6.0 already evaluates route-level `authorization` CEL on `llm.requestModel` and on `mcp.tool.arguments`: per-role model lists and argument-scoped tools need policy, not an upgrade. The MCP spec of 2026-07-28 made RFC 9728 and audience validation mandatory and left per-tool scopes to servers. Only ToolHive lets policy read tool annotations |
| How to tune caching? | The marker, not the TTL, is the first-order lever: the gateway path reached 85% reads on Opus only after the harness shim, and a regression would re-price internal runs about 20× silently. The **1-hour TTL is unreachable** today (agentgateway 1.6 forces `ttl: None`; its fix was closed unmerged on 2026-10-21). The **condenser is the biggest cache event** in a run. Opus 5.5's prior reasoning is not replayed through the Chat Completions path. Semantic caching is wrong for tool-calling traffic, and vendors now say so |
| What did the peers ship? | The merge gate is where the field moved: Meta's RADAR lands 331K+ diffs with risk scores calibrated on revert and incident rates; GitHub lets a bot's path-scoped approval count toward required reviews; gh-aw ships a declared merge-gate vocabulary. Runtime kept commoditising (agent-sandbox 1.0.7, Substrate 0.5.0, Modal VM sandboxes). The bake-off should run on Terminal-Bench and SWE-bench Pro, not the saturated SWE-bench Verified |

## 1. How other apps and agents interact with a factory

### 1.1 The products

| Product | Intake | Observe | Outbound | Delegation protocol | Caller auth | Human attribution |
|---|---|---|---|---|---|---|
| GitHub Copilot cloud agent, Agent HQ | Issue assign (UI, REST `agent_assignment`), `POST /agents/repos/{o}/{r}/tasks`, `gh agent-task`, GitHub MCP `assign_copilot_to_issue`, chat, Jira/Slack/Linear, Automations ([API](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api) acc., [automations](https://github.blog/changelog/2026-06-02-schedule-and-automate-tasks-with-copilot-cloud-agent/) 2026-06-02) | Agents tab; `GET /agents/tasks` with states `queued, in_progress, completed, failed, idle, waiting_for_user, timed_out, cancelled`; `gh agent-task view --log --follow` | Draft PR, comments, session log link per commit. No session webhook found | None open; gh-aw delegates with `create-agent-session` | **User-to-server tokens only**; installation tokens rejected | Starter is co-author; only write-access users may start; hidden characters filtered ([responsible use](https://docs.github.com/en/copilot/responsible-use/copilot-coding-agent) acc.) |
| OpenAI Codex cloud | Slack `@ChatGPT`, Linear assign ([Slack](https://learn.chatgpt.com/docs/third-party/slack), [Linear](https://learn.chatgpt.com/docs/third-party/linear) acc.) | Thread replies, Linear activity | Thread messages | None: the SDK drives local threads; `codex mcp-server` removed; cloud task API **UNVERIFIED/absent** | Requester's account, linked | Runs under the requester; triage rules run as the issue creator |
| Cursor cloud agents, Automations | `POST /v1/agents`, follow-ups, Automations on schedule, repo events, Slack, Linear, Sentry, PagerDuty, a private webhook ([endpoints](https://cursor.com/docs/cloud-agent/api/endpoints), [automations](https://cursor.com/docs/automations) acc.) | `GET /v1/agents/{id}`, SSE run stream, per-run token usage | v0 webhooks: one `statusChange`, HMAC `X-Webhook-Signature` ([webhooks](https://cursor.com/docs/cloud-agent/api/webhooks) acc.) | None | User or service-account key | "Run as me" bills the user; service account bills the team pool and authors as `cursor` |
| Devin | `POST /v3/.../sessions` with `max_acu_limit`, `create_as_user_id`; MCP `devin_session_create/_interact/_events`; Slack; Linear ([sessions](https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions.md), [MCP](https://docs.devin.ai/work-with-devin/devin-mcp.md) acc.) | Session status, `acus_consumed`, `pull_requests[]`, MCP events | Slack thread. Webhooks **UNVERIFIED** | MCP server | Service users with RBAC; `ImpersonateOrgSessions` to act as a user | Response carries `user_id` and `service_user_id`; spend capped per session |
| Google Jules | `POST /v1alpha/sessions` with `requirePlanApproval`, `automationMode: AUTO_CREATE_PR` ([sessions](https://jules.google/docs/api/reference/sessions/) acc.) | Append-only `activities` feed | None, poll only | None | API key | Key owner only |
| OpenHands Cloud | `POST /api/v1/app-conversations`; Slack, Jira, Linear mentions ([API](https://docs.openhands.dev/openhands/usage/cloud/cloud-api.md) acc.) | `execution_status` ∈ `idle, running, paused, waiting_for_confirmation, finished, error, stuck` | Slack thread; no webhooks documented | None | API key | Every chat user links an OpenHands account by email |
| Anthropic Managed Agents (beta) | `POST /v1/sessions` with `budget.max_list_cost`; events `user.message`, `user.interrupt` ([sessions](https://platform.claude.com/docs/en/managed-agents/sessions) acc.) | SSE event stream; `session.status_idle` with `stop_reason` ∈ `end_turn, budget_reached, requires_action` | **Signed webhooks, id-only payload**, ≤3 retries, no ordering, auto-disabled on 3xx or a private IP ([webhooks](https://platform.claude.com/docs/en/managed-agents/webhooks) acc.) | Internal threads | Workspace key | The budget is the accountability primitive |
| Claude Code routines | Schedule, GitHub events, `POST .../routines/{id}/fire` with a fire-only token, 30/h ([fire](https://platform.claude.com/docs/en/api/claude-code/routines-fire) acc.) | Session URL | Session URL | None | Per-routine bearer, no read scope | Runs as the owner; the payload arrives wrapped as untrusted text |
| GitHub Agentic Workflows | `slash_command`, `label_command`, `repository_dispatch`, schedule ([triggers](https://github.github.io/gh-aw/reference/triggers/) acc.) | Actions logs | **Safe outputs only**: the agent job is read-only; a separate job applies sanitised outputs ([safe outputs](https://github.github.io/gh-aw/reference/safe-outputs/) acc.) | `create-agent-session` to Copilot | `on.roles` allowlist, default `[admin, maintainer, write]` | Triggering actor's role is checked |
| Linear agents | OAuth app with `app:assignable`, `app:mentionable`; `AgentSession` created on mention or delegate ([agents](https://linear.app/developers/agents.md) acc.) | `agentActivityCreate` (`thought, action, elicitation, response, error`); states derived from the last activity | Linear → agent webhooks, reply ≤5 s | — | OAuth app identity | The agent is a **delegate, not an assignee** |
| Slack agents | `features.agent_view`; `agents.sessions.setStatus` with `initiator_user_id` ([recap](https://slack.dev/slack-developer-changelog-recap-april-june-2026/) 2026-07-21) | Session status, streaming | — | Slackbot MCP client | Bot token | `initiator_user_id` |
| Atlassian Rovo | `rovo:agentConnector`: remote agents **must speak A2A 1.0** ([connector](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-agent-connector/) 2026-10-09) | 55 s sync, 900 s streaming | — | A2A 1.0 | Token passing | Connector user is the mentionable identity |

### 1.2 Protocols

| Protocol | State | What it gives a factory | Source |
|---|---|---|---|
| **A2A 1.0** | First stable spec; >150 organisations; Azure AI Foundry, Copilot Studio, Bedrock AgentCore | Signed Agent Card at `/.well-known/agent-card.json`; `SendMessage`, `GetTask`, `SubscribeToTask`, push configs; task states `SUBMITTED, WORKING, INPUT_REQUIRED, AUTH_REQUIRED, COMPLETED, FAILED, CANCELED, REJECTED`; push notifications are at-least-once and "SHOULD validate webhook URLs to prevent SSRF" | [LF](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) 2026-04-09, [spec](https://a2a-protocol.org/latest/specification/) acc. |
| **MCP Tasks** (extension `io.modelcontextprotocol/tasks`) | Experimental in 2025-11-25, an extension in 2026-07-28 | `tasks/get` polling, `input_required` for human approvals, `tasks/update`; "receivers MUST bind tasks to the authorization context" | [tasks](https://modelcontextprotocol.io/extensions/tasks/overview) |
| MCP as a control plane | In the wild | GitHub `assign_copilot_to_issue`, Devin `devin_session_*`, Notion `notion-spawn-session` and `notion-wait-session` (observed in a live tool list 2026-10-21; docs **UNVERIFIED**) | above |
| Event formats | No agent-specific CloudEvents profile found; OTel GenAI semconv still "Development" | The de-facto pattern is vendor `{domain}.{action}` names, id-only payloads, signed headers | — |

### 1.3 Auth and accountability patterns worth copying

| Pattern | Who | Why it matters here |
|---|---|---|
| Refuse machine identity for starting work; require a human-bound token | GitHub (installation tokens rejected) | Every PR has a human who pays attention and pays the bill |
| Service identity plus explicit on-behalf-of, gated by a stronger permission | Devin `create_as_user_id` under `ImpersonateOrgSessions`; both ids recorded | The audit shows the sponsor and the automation |
| Two run-as modes with different billing pools | Cursor "run as me" vs service account | The spend owner is a first-class choice |
| Hard per-run cost cap set by the caller | Managed Agents `max_list_cost`, Devin `max_acu_limit` | The caller declares the ceiling it answers for |
| Fire-only, single-purpose intake token | Claude routines `sk-ant-oat01-…`, no read, 30/h | A leak's blast radius is extra runs, not data |
| Payload from a token holder is data, not instruction | Routines `<routine-fire-payload>`; gh-aw sanitisation; Copilot hidden-character filter | Prompt-injection containment at the intake boundary |
| Trigger only from privileged actors | Copilot write-access rule; gh-aw `on.roles` | `factory/ready` from a maintainer already does this ([Trail of Bits on Copilot issue injection](https://blog.trailofbits.com/2025/08/06/prompt-injection-engineering-for-attackers-exploiting-github-copilot/) 2025-08-06) |
| Account linking per chat user | Devin, OpenHands, Claude | Chat identity becomes an SSO identity before anything runs |

## 2. Loops and teams

### 2.1 Patterns

| Pattern | What it is | Evidence | Cost multiplier | Fits a sequential single-writer factory on open weights? |
|---|---|---|---|---|
| Ralph loop, fresh context per iteration | `while :; do cat PROMPT.md \| agent; done`; one task per iteration, state on disk, exit on green | Anecdotes only; the author would not use it "in an existing code base"; failure modes "go in circles, ignore instructions" ([Huntley](https://ghuntley.com/ralph/) 2025-07-14, [how-to](https://github.com/ghuntley/how-to-ralph-wiggum)) | 1× per iteration, unbounded by default | With caveat: adopt the mechanics (fresh context, one task, cap), not the loop |
| Ralph via Stop hook, same session | A hook blocks exit and re-injects the prompt | Plugin default iterations **unlimited**; Claude Code caps consecutive Stop-hook continuations at 8 ([plugin](https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/README.md), [hooks](https://code.claude.com/docs/en/hooks)) | 1× but the context grows | No: context pollution is the documented failure |
| **Goal loop with a separate evaluator** (Claude Code and Codex `/goal`) | After each turn a *different, cheap* model judges met / not yet / impossible; the agent continues on "not yet" with the reason | Claude Code: evaluator calls no tools, stops after "no tool use for several turns", 3 retries then pause ([/goal](https://code.claude.com/docs/en/goal)); Codex 0.128.0 loops until the goal or the token budget ends ([Willison](https://simonwillison.net/2026/Apr/30/codex-goals/) 2026-04-30; GA 2026-05-21) | A small-model call per turn, "typically negligible" | **Yes**: the cheapest high-value addition |
| Generator and evaluator with fresh context | The reviewer sees the diff and criteria, never the coder's history | Cognition: review "work[s] best when the coding and review agents do not share any context beforehand"; Devin Review finds "an average of 2 bugs per PR, roughly 58% severe" ([Cognition](https://cognition.com/blog/multi-agents-working) 2026-04-22); Anthropic: a QA agent "found real issues, then talked itself into approving them" until calibrated with few-shot score breakdowns ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps) 2026-03-24) | 5–10% of the build cost per round | Yes, we have it; isolate the reviewer from the room log and calibrate it |
| Execution-grounded tester or critic | Tests must run in the sandbox before a patch propagates | AgentForge on SWE-bench Lite: full 42% against 28% without the tester; retries saturate after about two ([AgentForge](https://arxiv.org/html/2604.13120v1) 2026-04-13). ExecCritic: bad tests hurt (61.2% → 57.3%), a post-trained test agent adds 11.4 points ([ExecCritic](https://arxiv.org/abs/2609.09133) 2026-09-08) | 2.7× (AgentForge) | Yes with a caveat: test quality decides the sign; gate agent-written tests fail-closed |
| Scoper or clarifier stage | Detects underspecification and asks, or assumes with a stated assumption | 69.40% on underspecified SWE-bench Verified, "closing the performance gap" with fully specified issues ([Ask or Assume](https://arxiv.org/abs/2603.26233) v3 2026-09-07); agents in the wild ask in 1.4% of turns ([SWE-chat](https://arxiv.org/html/2604.20779v1) 2026-04) | One short run | Yes: the strongest evidence of any added stage |
| Planner then implementer | A plan produced separately | "A subpar plan hurts performance even more than no plan at all"; periodic plan reminders reduce violations ([Plan-to-Action](https://arxiv.org/abs/2604.12147) 2026) | Small | With caveat: fold the plan into the scoper's output and re-inject it each round |
| Agent Teams (lead, teammates, shared task list) | Parallel full sessions | Anthropic: "approximately 7x more tokens"; "for sequential tasks, same-file edits… a single session or subagents are more effective" ([agent teams](https://code.claude.com/docs/en/agent-teams), [costs](https://code.claude.com/docs/en/costs)) | about N× | **No** |
| Read-only subagents | A fresh-context worker returns a summary | Anthropic's rule of thumb: "ten or more files, or… three or more independent pieces of work" ([Anthropic](https://claude.com/blog/how-and-when-to-use-subagents-in-claude-code) 2026-04-07) | Saves main-context tokens | Yes, planned |
| Best-of-N candidates plus a judge | N attempts, a judge picks | Cursor auto-judge, no numbers; LLM-as-a-Verifier: 3 candidates lift 76.1% → 78.2%, oracle 84.4% ([paper](https://arxiv.org/abs/2607.05391) 2026-07-06) | N× for about +2 points | No in production; a bench tool for the bake-off |
| Mixed-model routing per role | A strong model plans and reviews, a cheap one executes | Devin Fusion: 63.1 at $1.35 a task against Opus 5 63.6 at $3.51; "when the judgment is the deliverable, delegating it backfires"; a stronger model as a tool "doesn't yet work with a weaker primary" ([Cognition](https://cognition.com/blog/devin-fusion) 2026-06-29) | −35–60% | With caveat: per role, never per step |
| Dark factory (spec → agent → holdout scenarios → judge) | "Code must not be written by humans. Code must not be reviewed by humans"; scenarios kept outside the repository | No production numbers ([StrongDM](https://factory.strongdm.ai/) 2026-02-06). Attractor loop: `max_turns=0` unlimited, repeated tool-call window 10 ([spec](https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md)). "Death Mode": **UNVERIFIED**, not found in any StrongDM source | Very high | No as a whole; yes for holdout checks the implementer cannot read |
| Scheduled loops | Cron-triggered unattended runs | gh-aw: `max-turns` 500, `stop-after`, `max-daily-ai-credits` 5000, `create-pull-request max: 1`, `deduplicate-by-title` ([rate limits](https://github.github.com/gh-aw/reference/rate-limiting-controls/)); Claude Code routines min 1 h, 100/h/account ([routines](https://code.claude.com/docs/en/routines)) | Bounded by daily caps | Yes for the mechanics |

### 2.2 Stall and continuation numbers

| System | Rule | Value | Source |
|---|---|---|---|
| OpenAI Symphony | silence kills and retries; turns per worker session; backoff | stall 300 s; turn 3,600 s; `max_turns` 20; 10 s × 2ⁿ⁻¹ capped at 300 s | [SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md) |
| Claude Code `/goal` | no-progress stop; retries | "no tool use for several turns in a row"; 3 retries then pause | [/goal](https://code.claude.com/docs/en/goal) |
| Claude Code Stop hook | runaway cap | 8 consecutive continuations, reset on a tool call | [hooks](https://code.claude.com/docs/en/hooks) |
| OpenHands SDK | stuck detector | same action and observation 4+; same action and error 3+; monologue 3+; ping-pong 6+ | [docs](https://docs.openhands.dev/sdk/guides/agent-stuck-detector) |
| Attractor | repeated tool-call pattern | window 10, then "try a different approach" is injected | [spec](https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md) |
| gh-aw | run bounds | `max-turns` 500; agent step 20 min | [docs](https://github.github.com/gh-aw/reference/frontmatter/) |
| AgentForge | debug retries | 3; "gains saturate after about two" | [paper](https://arxiv.org/html/2604.13120v1) |

No source documents a literal "no diff by step N" rule; the nearest are Claude Code's "no tool use for several turns" and the Ralph convention that an iteration ends with exactly one commit.

### 2.3 Verification evidence

| Finding | Number | Source |
|---|---|---|
| Review agents on human-verified bugs | the best configuration catches 71.9% in its top five, up from 47.7% a generation earlier; a sharp drop on proprietary repositories | [Lights-off](https://arxiv.org/abs/2610.13668) 2026-10-09 |
| Review agents on c-CRAB tasks | about 40% solved (PR-agent, Devin, Claude Code, Codex) | [c-CRAB](https://arxiv.org/abs/2603.23448) 2026-03 |
| A production review bot | 38.7% of comments led to a change; PR cycle time −30.8% | [RovoDev, ICSE'26](https://arxiv.org/abs/2601.01129) |
| Position bias of small open judges on code | 86.93% against 16.79% accuracy depending on the answer's position (Qwen2.5-Coder-3B); abstain when unstable | [Bias in the Loop](https://arxiv.org/html/2604.16790v1) 2026-04-18 |
| Self-grading | "agents tend to respond by confidently praising the work" | [Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps) 2026-03-24 |
| Test quality as the oracle | a weak test agent lowered resolve by 3.9 points; TDD instructions without targeted test context raised regressions from 6.08% to 9.94% | [ExecCritic](https://arxiv.org/abs/2609.09133); [TDAD](https://arxiv.org/abs/2603.17973) 2026-03-18 |
| AI review precision, vendor-run | no reviewer above about 52% precision (Codex 51.9/40.3, Claude 42.3/43.3, Bugbot 34.4/46.3, CodeRabbit 24.8/49.2) | [Entelligence](https://entelligence.ai/code-review-benchmark-2026) 2026-09, conflict of interest |

A reviewer on an open-weight model must not issue a bare verdict: it must produce executable evidence and abstain to a human when its judgment is unstable. A reviewer verdict is a block signal, never a merge signal on its own.

## 3. Fine-grained permissions for tools and models

### 3.1 The MCP specification, revision 2026-07-28

| Topic | What the spec says | Source |
|---|---|---|
| Base | OAuth 2.1; the server MUST implement RFC 9728 protected-resource metadata; the client MUST send RFC 8707 `resource`; the server MUST validate the audience; 401 for an invalid token, 403 `insufficient_scope` | [authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) |
| Client registration | Client ID Metadata Documents SHOULD; dynamic registration deprecated | [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) |
| Scopes | `scope=` in the 401 challenge; a 403 step-up; "required scopes may be determined dynamically based on the specific request arguments"; per-tool scopes are **not standardised**, but `tools/list` MAY vary by the authorization presented | same; [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |
| Tool annotations | `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`; "clients MUST consider tool annotations to be untrusted unless they come from trusted servers" | [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |
| Elicitation | A multi-round-trip request: `resultType: "input_required"`, the client retries with `inputResponses`; a mid-call approval gate | [elicitation](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation) |
| Enterprise-managed authorization | **Stable** extension: the IdP issues an ID-JAG (RFC 8693), the MCP AS issues the access token; the client never holds a token for an unauthorised server | [EMA](https://modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization); [draft-04](https://www.ietf.org/archive/id/draft-ietf-oauth-identity-assertion-authz-grant-04.html) 2026-05-21 |
| Transport | A stateless mode without `Mcp-Session-Id`; `x-mcp-header` mirrors a parameter into `Mcp-Param-*` so "network intermediaries… route and process requests based on parameter values without parsing the request body" | changelog |
| Registry | `server.json` metadata under verified namespaces; still "preview"; no tool-level or security metadata | [registry](https://github.com/modelcontextprotocol/registry) |

### 3.2 agentgateway 1.6.0 against `main`, and the Envoy Agent Router

| Capability | v1.6.0 (2026-10-02) | `main` (2026-10-21) | Source |
|---|---|---|---|
| MCP authorization CEL | `mcp.tool.name`, `mcp.tool.target`, `mcp.prompt.name`, `mcp.resource.name`, `jwt.*`; denied items hidden from lists | same | [reference](https://agentgateway.dev/docs/standalone/latest/documentation/configuration/security/mcp-authz/) |
| Arguments in `mcpAuthorization` | **No**: "`mcp.tool.arguments` isn't set when `mcpAuthorization` rules run… use a route-level `authorization` policy" | same | same |
| Arguments in route-level HTTP `authorization` | **Yes**: `mcp.tool.arguments` is request-time; a denial is a 403, not a hidden tool | same | [CEL variables](https://agentgateway.dev/docs/standalone/latest/reference/cel/variables/) |
| Arguments through ExtMCP | A gRPC guardrail hook per method receives the params and returns pass, reject or mutated; `failureMode: FailClosed` | same | [guardrails](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/guardrails/about.md) |
| Model authorization | `authorization` rule `action: Require` on `llm.requestModel in [...]` answers **403**; `allowedModels` per API key filters `/v1/models` | The router's 403 skipped the request snapshot, so the audit log "cannot name the caller of a refused model call": fixed by #3996 on 2026-10-16, **unreleased** | [virtual keys](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/cost-controls/virtual-keys.md); [#3989](https://github.com/agentgateway/agentgateway/issues/3989) |
| Token exchange | `backendAuth.oauthTokenExchange`: RFC 8693, RFC 7523, Entra OBO, cross-app access, per MCP backend | same | [MCP exchange](https://agentgateway.dev/docs/kubernetes/latest/documentation/security/backend-authn/token-exchange/mcp.md) |
| v1.7 | Does not exist yet | — | [releases](https://github.com/agentgateway/agentgateway/releases) |

The Envoy Agent Router (ex Envoy AI Gateway, v1.2) evaluates argument CEL inside its `MCPRoute` (`request.mcp.params.arguments.text.matches(...)`) and filters tools per backend with `toolSelector` ([docs](https://theagentrouter.ai/docs/capabilities/mcp/)). A field report found that name-based CEL "cannot distinguish deploy to staging from deploy to production", hence ExtMCP ([learncloudnative](https://learncloudnative.com/blog/2026-08-14-7-practical-mcp-policies-agentgateway) 2026-08-14).

### 3.3 Other gateways, engines and products

| Mechanism | Granularity | Source |
|---|---|---|
| ToolHive (Stacklok), Cedar | Principal from JWT claims and groups; `Tool::<name>` with `readOnlyHint…` and `arg_<name>` attributes; default deny; a `VirtualMCPServer` aggregates servers with per-tool filters and annotation **overrides** | [cedar](https://docs.stacklok.com/toolhive/concepts/cedar-policies), [vMCP](https://docs.stacklok.com/toolhive/guides-vmcp/tool-aggregation) |
| Cerbos behind agentgateway `extAuthz` | Per model, per tool, per argument (`R.attr.arguments.amount_cents > 5000`); `failureMode: deny` | [Cerbos](https://www.cerbos.dev/blog/governing-ai-agents-at-the-gateway-with-cerbos-and-agentgateway.md) 2026-06-10 |
| OpenFGA | `tool` type with `can_call`; arguments not modelled | [OpenFGA](https://openfga.dev/docs/use-cases/mcp-server-authorization.md) |
| Kubernetes Tool Auth API (proposal 0008) | `XBackend`, `XAccessPolicy`, ServiceAccount or SPIFFE principals, default-deny `tools/call`, name only; "Do NOT use in production" | [proposal](https://kube-agentic-networking.sigs.k8s.io/proposals/0008-toolauthapi/) |
| OpenID AuthZEN | Core 1.0 final (Cerbos claim, **partially UNVERIFIED**); June 2026 drafts AARP and COAZ-MCP let tools declare authorization intent | [openid.net](https://openid.net/openid-foundation-advances-authorization-for-the-agent-era-with-new-authzen-working-group-drafts/) |
| Claude Code and Agent SDK | Rules `Tool(specifier)`; order deny → ask → mode → allow → callback; MCP rules with arguments are skipped; `_meta["anthropic/requiresUserInteraction"]` prompts in every mode; `PreToolUse` hooks bind even in bypass | [permissions](https://code.claude.com/docs/en/permissions), [SDK](https://code.claude.com/docs/en/agent-sdk/permissions) |
| Claude Managed Agents | `permission_policy` `always_allow`, `always_ask`, `auto` per toolset; `auto` "considers the tool, the call's input, and the session's content" | [policies](https://platform.claude.com/docs/en/managed-agents/permission-policies) |
| GitHub Copilot coding agent | Firewall allowlist per repo (not MCP); per-repo MCP config with a required per-server `tools` list; custom agents in `.github/agents/*.agent.md` with a tool allowlist | [firewall](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-firewall), [agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents) |
| OpenAI Codex | `approval_policy` with categories; `sandbox_mode`; a `network_proxy` allowlist; `approvals_reviewer: auto_review` fails closed; destructive-annotated MCP tools need approval | [Codex](https://learn.chatgpt.com/docs/agent-approvals-security) |
| OpenHands SDK | Security analyzers (LLM, pattern, policy, ensemble) rate LOW to HIGH; `ConfirmRisky(threshold)` | [OpenHands](https://docs.openhands.dev/sdk/guides/security) |
| Model access at LLM gateways | LiteLLM access groups with group budgets; Kong `AIGatewayModel` ACLs per consumer group; Bedrock IAM on model ARNs; Cloudflare dynamic routes; Vertex Model Armor is content only | [LiteLLM](https://docs.litellm.ai/docs/proxy/model_access), [Kong](https://developer.konghq.com/operator/get-started/ai-gateway/consumers/), [AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html) |

"Model access by data classification" has no vendor primitive: it is composed from a principal attribute and a model allow-list, which is what the agent gateway already does per listener.

## 4. Prompt and KV caching

### 4.1 Providers

| | Anthropic (Opus, Sonnet, Haiku 5.5) | Z.ai GLM-5.3 | OpenAI (GPT-5.6+) | vLLM, self-hosted |
|---|---|---|---|---|
| Trigger | Explicit `cache_control`, or a top-level automatic marker | Implicit, no markers | Implicit; explicit `prompt_cache_breakpoint` on GPT-5.6+ | Automatic prefix caching, on by default in V1 |
| Minimum | 512 tokens | not stated | 1,024 | one block, 64 tokens typical |
| TTL | 5 min default, 1 h option, refreshed on a hit; **measured from the start of the request** that writes or reads | "reasonable time limits" | 30 min default, 12 h option | LRU under memory pressure |
| Read price | 0.05× (Opus and Sonnet 5.5), 0.1× others | 0.186× | 0.1× | — |
| Write price | 1.25× (5 min), 2× (1 h) | free, "limited time" | 1.25× (30 min), 2.5× (12 h) | — |
| Hit field | `cache_read_input_tokens`, `cache_creation.ephemeral_{5m,1h}_input_tokens` | `prompt_tokens_details.cached_tokens` | `input_tokens_details.cached_tokens` | `vllm:prefix_cache_hits` and `_queries` counters |
| Rate limits | Reads do not count toward input tokens per minute | — | Cached tokens still count | — |
| Source | [caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [pricing](https://platform.claude.com/docs/en/about-claude/pricing), [rate limits](https://platform.claude.com/docs/en/api/rate-limits) | [cache](https://docs.z.ai/guides/capabilities/cache), [pricing](https://docs.z.ai/guides/overview/pricing) | [OpenAI](https://developers.openai.com/api/docs/guides/prompt-caching) | [V1 blog](https://vllm.ai/blog/2025-01-27-v1-alpha-release), [metrics](https://docs.vllm.ai/en/latest/design/metrics/) |

Anthropic details that matter in a long loop: a tool-definition change invalidates tools, system and messages; "treat any thinking or top-level effort change as starting the cache over" ([thinking](https://platform.claude.com/docs/en/build-with-claude/thinking)); the breakpoint looks back at most 20 positions, where a run of consecutive `tool_use` or `tool_result` blocks counts as one; an entry becomes readable only after the first response begins; pre-warming with `max_tokens: 0` is rejected with extended thinking, which Opus 5.5 always runs; server-side compaction "doesn't count as an edit" and keeps a system-prompt breakpoint, while client edits before a thinking block invalidate every later block on the 5.5 models ([preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking), [compaction](https://platform.claude.com/docs/en/build-with-claude/compaction-threshold)). Claude Code's `/usage` line is the telemetry to copy: "91% of input tokens from cache · 2 misses (310.2k tokens re-cached) · 1 expected rebuild (compaction or tool-result clearing)… likely cause: tool definitions changed" ([costs](https://code.claude.com/docs/en/costs)).

### 4.2 What our harness path sends

Read at software-agent-sdk v1.49.5, litellm `main` and agentgateway v1.6.0.

| Component | Verified behaviour | Source |
|---|---|---|
| `LLM.caching_prompt` | On by default; markers only when `supports_prompt_cache`, whose fallback list names `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5` and **not `claude-haiku-5-5`** ([#5702](https://github.com/OpenHands/software-agent-sdk/issues/5702)); no `glm` pattern, which is right (Z.ai caches implicitly) | [model_features.py](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.5/openhands-sdk/openhands/sdk/llm/utils/model_features.py) |
| Breakpoints | Exactly two: the static system block and the last content block of the last user or tool message; the dynamic system block is left unmarked "to enable cross-conversation prompt caching"; no TTL field exists | [llm.py](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.5/openhands-sdk/openhands/sdk/llm/llm.py) |
| Tools | Built once at start, sent every step in insertion order; an MCP `tools/list_changed` notification **can** change the list mid-run, a tools-level invalidation | [base.py](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.5/openhands-sdk/openhands/sdk/agent/base.py) |
| Resume | The persisted `SystemPromptEvent` is reused, so the dynamic block is not re-rendered: the prefix stays byte-stable | [agent.py](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.5/openhands-sdk/openhands/sdk/agent/agent.py) |
| Condenser | Triggers past 80 events, forgets events 4 to `len−35`, inserts one summary at offset 4; the summary call carries no markers. **The biggest cache event in a run**: a rewrite of everything after event 4 about every 40 events, plus an uncached call | [condenser](https://github.com/OpenHands/software-agent-sdk/blob/v1.49.5/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py) |
| agentgateway conversion | Only `prompt_cache_breakpoint` on text parts becomes `cache_control`, **always `ttl: None`**; tools and `tool_use` blocks never carry a marker. Assistant thinking is forwarded only with a `reasoning_signature`, which the SDK does not store: **Opus 5.5's prior reasoning is not replayed** through this path (Anthropic measured +4.6% to +67.1% output tokens when blocks are dropped every turn) | [messages.rs @ v1.6.0](https://github.com/agentgateway/agentgateway/blob/v1.6.0/crates/llm/src/conversion/messages.rs), [preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking) |
| The 1-hour TTL | Unreachable today: [#3167](https://github.com/agentgateway/agentgateway/issues/3167) open, its fix [#3265](https://github.com/agentgateway/agentgateway/pull/3265) closed unmerged on 2026-10-21, no 1.7 release | [releases](https://github.com/agentgateway/agentgateway/releases) |
| Our shim's baseline | agent-platform [#132](https://github.com/Smana/agent-platform/pull/132) (2026-10-16): before the rewrite, 15 Opus 5.5 calls read "500,930 input tokens, 0 cached"; after it, the offline test shows `cache_control` on the system block and the newest tool result | PR |

LiteLLM pins later calls to the deployment that wrote the cache ([tutorial](https://docs.litellm.ai/docs/tutorials/claude_code_prompt_cache_routing)), because Anthropic caches are per workspace; the Envoy Agent Router passes `cache_control` through unchanged ([docs](https://theagentrouter.ai/docs/capabilities/llm-integrations/prompt-caching)).

### 4.3 Self-hosted

vLLM's automatic prefix caching costs "<1% decrease in throughput even when the cache hit rate is 0%" ([design](https://docs.vllm.ai/en/latest/design/prefix_caching/)); CPU offload (`--kv-offloading-size`, LMCache or native) lowers time to first token "X2–X22" on hits ([blog](https://vllm.ai/blog/2026-01-08-kv-offloading-connector) 2026-01-08). The Gateway API Inference Extension's approximate prefix scorer keeps a per-server LRU of seen chunks and "degrades with multiple EPP replicas" ([proposal 0602](https://github.com/kubernetes-sigs/gateway-api-inference-extension/blob/main/docs/proposals/0602-prefix-cache-aware-routing-proposal/README.md)); llm-d's precise mode indexes KV events but runs a single router replica ([guide](https://github.com/llm-d/llm-d/blob/main/guides/precise-prefix-cache-routing/README.md)). Vendors report >95% prefix hits on agent replays ([LMSYS](https://www.lmsys.org/blog/2026-06-27-netpreme-xmem) 2026-07-08); no independent 2026 measurement was found.

### 4.4 Semantic caching is wrong for tool-calling traffic

TrueFoundry (2026-10-16): a semantic cache is "designed for single-shot prompts; on multi-turn or agentic traffic it will replay stale responses", successive turns' "embeddings stay ~0.99 similar", and "assistant tool_calls are not part of the embedded text" ([source](https://www.truefoundry.com/blog/litellm-caching)). The vLLM Semantic Router scored "enable 2FA" against "disable 2FA" at 0.823 ([#2691](https://github.com/vllm-project/semantic-router/issues/2691)). GPTCache no longer adds support for new models ([README](https://github.com/zilliztech/GPTCache)).

### 4.5 Levers

| Lever | Provider | Effect | Cost or risk | Measure |
|---|---|---|---|---|
| The SDK's two breakpoints (static system, moving last message) | Anthropic | about 85% reads today | none | `cached_input / input` per step |
| 1 h TTL on both breakpoints for attended runs | Anthropic | survives 5–60 min gaps and steps over 5 min | 2× write; blocked by `ttl: None` | `ephemeral_1h_input_tokens > 0` |
| A frozen tool list; `tool_choice: none` instead of removal; ignore `list_changed` mid-run | Anthropic, OpenAI | no tools-level invalidation | capability drift inside a run | a hash of `tools` per step |
| Thinking and effort fixed per run | Anthropic | no full restart | none | a miss with unchanged tools and system |
| Rarer condensation, or server-side compaction with the system breakpoint kept | Anthropic | fewer and cheaper rebuilds | beta headers must cross the gateway (UNVERIFIED) | expected against unexpected rebuilds |
| A byte-stable request (no timestamps, deterministic JSON) | all | hits at all | none | diff two consecutive upstream bodies |
| One key and workspace per route | Anthropic | no cross-workspace misses | — | hit ratio per key |
| APC plus CPU offload, prefix-aware routing from two replicas | vLLM | lower time to first token | memory | `vllm:prefix_cache_hits / _queries` |
| No semantic cache | all | no stale tool calls | — | — |

### 4.6 Cost arithmetic

Opus 5.5 ($4 in, $5 a 5-minute write, $8 a 1-hour write, $0.20 a read, per million tokens). A 45-minute run of 30 steps whose context grows from 30k to 150k tokens sends about 2.7M prompt tokens.

| Scenario | Writes | Reads | Prompt cost |
|---|---|---|---|
| No caching | — | — | **$10.80** |
| 5-minute TTL, no gap | 150k × $5 = $0.75 | 2.55M × $0.20 = $0.51 | **$1.26** |
| 1-hour TTL, no gap | 150k × $8 = $1.20 | $0.51 | **$1.71** |
| 5-minute TTL, a 20-minute suspension after step 15 (context 88k) | $0.75 + 88k × $5 = $1.19 | $0.49 | **$1.68** |
| 1-hour TTL, the same suspension | $1.20 | $0.51 | **$1.71** |
| Either TTL, a gap over an hour | a full rewrite at resume | | 5 min about $1.68, 1 h about $2.15 |

The 1-hour TTL costs an extra `3 × final context` ($0.45 here) and saves `5 × context at the gap` for each 5–60 minute gap ($0.44 at 88k): it pays when at least one such gap is expected after about 60% of the final context exists. Output tokens dominate once caching works (30 steps × about 4k tokens of thinking and text at $20 is $2.40), so the TTL is a second-order decision; the first-order one is never losing the marker.


## 5. The peers, and what is worth reproducing

### 5.1 Practitioners and research

| Source | What it says | Our layer | Reproduce? |
|---|---|---|---|
| [StrongDM manifesto](https://factory.strongdm.ai/) 2026-02-06, [principles](https://factory.strongdm.ai/principles), [techniques](https://factory.strongdm.ai/techniques) | Scenarios as user stories stored **outside** the codebase and judged by an LLM; "satisfaction" (the fraction of trajectories that satisfy the user) replaces "the suite is green"; the loop ends when "holdout scenarios pass (and stay passing)"; "Shift Work" separates interactive from fully specified work. Last update: the Weather Report of 2026-09-28, which routes Opus 5.5 to architecture and security review, cheaper models to bulk work | merge gate, harness, intake | Yes: holdout scenarios, a satisfaction threshold per class, per-task-class model routing |
| [strongdm/attractor](https://github.com/strongdm/attractor/blob/main/attractor-spec.md) | Pipelines as a DOT subset: `codergen`, `wait.human`, `parallel`/`fan_in`, `goal_gate=true` nodes, checkpoints after each node, model and effort "stylesheets" per node class. **No budget in the spec** | harness, rooms | Yes: goal gates, per-class model and effort selection |
| [Abenhaim](https://arxiv.org/abs/2608.12440) 2026-08-12 | A 717k-LOC app with no test oracle and no human review: spec-vs-code audit cycles, stop rule "two consecutive zero-finding passes", 201 defects caught, 3 days, $2,430 | harness, merge gate | Yes: the two-clean-passes stop rule for the reviewer |
| [Xia and Miller](https://arxiv.org/abs/2607.09902) 2026-07-10 | 182 repositories: agentic PRs need more corrective maintenance; each +10 points of no-review rate adds about 6% maintenance burden | merge gate, observability | Yes: the breaker should count follow-up fixes, not only reverts |
| [Ronacher, The Coming Loop](https://lucumr.pocoo.org/2026/6/23/the-coming-loop/) 2026-06-23 | Outer loops work for ports, experiments and disposable artefacts and hurt long-lived code; keep a human on "done" for lasting code | intake, merge gate | Yes: route loop-driven work to low-risk classes only |
| [Willison, 2026 in LLMs so far](https://simonwillison.net/2026/Sep/27/2026-in-llms-so-far/) 2026-09-27 | Agents have "broken out" of sandboxes in exercises; "high" reasoning is "a terrible default" | runtime, gateway | Yes: effort as a per-class dial |
| [Meta RADAR](https://arxiv.org/abs/2605.30208) 2026-05-28 | Authorship class → eligibility gates → heuristics → a Diff Risk Score → LLM review → deterministic validation → land. 535K+ reviewed, 331K+ landed; moving the score threshold from the 25th to the 50th percentile raised the approve rate to 60.31%; revert rate a third, incident rate a fiftieth of other diffs; observational | merge gate | Yes: calibrate class thresholds on revert and incident rates, start conservative |
| [Monperrus, The End of Code Review](https://arxiv.org/abs/2606.13175) 2026-06-11 | Mandatory human review of agent code is "a dead end"; no replacement mechanism | — | Citation only |

### 5.2 Products, September to October 2026

| Product | Shipped | Our layer | Reproduce? |
|---|---|---|---|
| GitHub | [Copilot code review can approve](https://github.blog/changelog/2026-09-01-copilot-code-review-can-now-approve-pull-requests/) 2026-09-01: off by default; the approval **counts toward required approvals**, dismissed on new commits, and admins choose **which paths** it may approve | merge gate | **Yes**: path-scoped reviewer authority |
| GitHub | [Agentic autofix GA](https://github.blog/changelog/2026-10-15-agentic-autofix-for-code-scanning-alerts-general-availability/) 2026-10-15: fixes validated by re-running CodeQL, ≤25 alerts per draft PR | intake, merge gate | Yes: alert → fix → re-run the detector is an oracle-backed class |
| GitHub Agentic Workflows | [`create-pull-request`](https://github.github.com/gh-aw/reference/safe-outputs-pull-requests/): draft by default, `max-patch-files: 100`, `allowed-files`, `allowed-base-branches`, `protected-files: request-review`; **`merge-pull-request`** (experimental): default-branch merges refused, `required-labels`, status checks, review decision, `staged: true` dry run; [threat detection](https://github.github.com/gh-aw/reference/threat-detection/) fails closed to `REQUEST_CHANGES` when the detector is down | merge gate | **Yes**: a declared merge-gate vocabulary close to ours |
| GitHub coding agent | [Risks and mitigations](https://docs.github.com/en/copilot/responsible-use/copilot-coding-agent): pushes only to `copilot/*`; Actions on agent PRs need a write user's approval; hidden-character filtering; commits linked to session logs | runtime, rooms | Yes: hidden-character filter, commit-to-room link |
| Cursor | [Rollouts and Security Review](https://cursor.com/changelog) 2026-09-23: a monitor per PR writes a monitoring plan and reports healthy, regression or inconclusive per environment, never merges or rolls back itself | observability, merge gate | **Yes**: a post-merge monitoring plan feeds the revert breaker |
| Devin | [Release notes](https://docs.devin.ai/release-notes/2026): autoreview triggers composable on author, labels, branches, files, diff size (2026-09-25); review findings routed back to the authoring session, only unfixed findings posted (2026-09-30); effort per trigger (2026-10-05); **"ACUs per merged PR"** analytics (2026-10-07) | merge gate, rooms, observability | Yes: findings back to the implementer first; cost per merged PR as the KPI |
| Factory.ai | [Changelog](https://docs.factory.com/changelog/release-notes): hook risk levels, subagents read-only in spec mode (0.223–0.225, 2026-09); `@`-mentioned files cannot alter instructions (0.240.0, 2026-10-13); org-required Droid reviews wired to branch rules (0.244.0, 2026-10-16); `droid exec --only-tools` | harness, merge gate | Yes: prompt-injection hygiene, per-run tool lists |
| OpenHands SDK | [Releases](https://github.com/OpenHands/software-agent-sdk/releases): tools from one server catalog (1.51.0, 2026-10-03); security analyzer verdict per batch and a workspace disk budget (1.54.0); **shell AST analysis replaces policy regexes** (1.55.0, 2026-10-15); `start_child_conversation` (1.56.0, 2026-10-19) | harness | **Yes**: we pin 1.49.6; the AST policy and child conversations are the search subagent's and the bridge classifier's upgrade path |
| Anthropic Claude Code | [Changelog](https://code.claude.com/docs/en/changelog) 2.1.295–2.1.306: hooks `onFailure: "block"`; OTel `tool_decision` carries `classifier_verdict` and `permission_mode`; cloud sessions never let a hook approve shell or subagents; routines do not re-run partial runs from the start | harness, observability, intake | Yes: fail-closed hooks, decision telemetry |
| Amazon Kiro | [Kiro Crew 0.1](https://kiro.dev/changelog/crew/0-1/) 2026-08-04: 10h+ runs with disk checkpoints, cron and webhook triggers, a governance ceiling at the tool gate "the agent cannot read or change", 137 denied patterns even under auto-approval, fail-closed without the sandbox | harness, gateway | Yes: the ceiling outside the agent's reach, which is our design |
| OpenAI Codex | [Reusable cloud environments, Codex Security](https://techcrunch.com/2026/09/29/openai-gives-codex-reusable-cloud-environments-that-work-across-devices/) 2026-09-29: scans on demand, schedule or commit; fixes prepared, a human opens the PR. Best-of-N and budgets: **not found** in Sept–Oct sources | intake | Yes: scan-on-commit intake |
| Augment Intent | [Public beta](https://www.augmentcode.com/blog/intent-a-workspace-for-agent-orchestration) 2026-04-15: coordinator → spec → implementer waves → an explicit **verifier** agent | harness | Yes: the verifier role |
| Google Jules | [Changelog](https://jules.google/docs/changelog/) has no entry after 2026-03-09; a planning critic, a CI fixer and scheduled tasks are the relevant older items | — | Watch |

### 5.3 Runtime changes since 2026-10-04

| Project | Change | Matters because |
|---|---|---|
| kubernetes-sigs/agent-sandbox | [v1.0.6](https://github.com/kubernetes-sigs/agent-sandbox/releases) 2026-10-08 (v1beta1 name length, scoped-token v2, warm-pool fixes) and [v1.0.7](https://github.com/kubernetes-sigs/agent-sandbox/releases) 2026-10-15 (bearer auth on `sandboxd`, warm pools with scheduling gates). Suspend and memory snapshots stay [GKE-only, Python-only](https://agent-sandbox.sigs.k8s.io/docs/sandbox/snapshots/); a generic suspend API is [#694](https://github.com/kubernetes-sigs/agent-sandbox/issues/694), open | A pin bump; no upstream suspend yet |
| Agent Substrate | [v0.4.0](https://github.com/agent-substrate/substrate/releases) 2026-10-08 and [v0.5.0](https://github.com/agent-substrate/substrate/releases) 2026-10-14: a snapshot fidelity ladder, usage records per actor, ingress denied by default in `ate-system`; v0.2.0 made "no egress policy means no egress" | Converging on our model; the 2026-12-15 re-check stands |
| google/ax | 14k stars, `ax suspend/resume`, no tagged release | Nothing to pin |
| kagent | [The future of kagent](https://kagent.dev/blog/the-future-of-kagent): the runtime is being rebuilt on Substrate with a breaking API | Hold |
| E2B | Filesystem-only pauses replace `keepMemory` (2026-10-12); fork count enforced | A cheap suspend tier we could mirror with PVC snapshots |
| Modal | [VM sandboxes GA](https://modal.com/blog/vm-sandboxes-agent-computers) 2026-10-01, gVisor stays the default | Confirms gVisor-default with a VM escape hatch |

### 5.4 The open-weight bake-off

Vals archived SWE-bench Verified on 2026-09-01 as saturated ([Vals](https://www.vals.ai/benchmarks/swebench)) and Terminal-Bench 2.1 on 2026-09-28 ([Vals](https://www.vals.ai/benchmarks/terminal-bench-2-1)); SWE-bench Pro is served from a [mirror](https://benchlm.ai/benchmarks/swe-bench-pro) (2026-10-20) and about 30% of its public split was flagged broken by an OpenAI audit. Vendor-reported numbers are marked (v). "Cost per resolved" is Vals' cost per test divided by its pass rate, derived here.

| Model (licence) | SWE-bench Verified (Vals, $/test) | Terminal-Bench 2.1 (Vals, $/test) | SWE-bench Pro | Price $/M in, cached, out (provider) | Tool-calling notes | Cost per resolved (TB 2.1) |
|---|---|---|---|---|---|---|
| **Kimi K3** (MIT-like with a MaaS clause, weights 2026-07-27) | 93.4% ($0.76) | **80.9%** ($0.34); 88.3 (v) | not on the board | $3.00 / — / $15.00 (Together, Moonshot) | Thinking always on; **`reasoning_content` must be passed back with `tool_calls`** in multi-turn tool use ([card](https://huggingface.co/moonshotai/Kimi-K3)) | $0.42 |
| **DeepSeek V4.1 Flash** (MIT, 2026-09-10) | not run | **74.5%** ($0.10); 90.6 (v) | not on the board | $0.15 / — / $0.60 off-peak (DeepSeek); $0.30 / $1.20 (Together) | A 16-point vendor-to-independent gap: verify tool-loop stability | $0.13 |
| **GLM-5.3** (MIT, the incumbent) | 95.4% ($0.34) | 71.5% ($0.31) | GLM-5.2 62.1% | $1.40 / $0.26 / $4.40 ([Z.ai](https://docs.z.ai/guides/overview/pricing)) | `tools`, `parallel_tool_calls`, `response_format` accepted; more verbose than 5.2 | $0.43 (baseline) |
| **GLM-5.3-Flash** (MIT) | 92.0% ($0.02) | 62.9% ($0.03) | — | $0.15 / $0.03 / $0.50 (Z.ai) | the same API | **$0.05** |
| **Qwen3.8-Max** (open weights per HF; licence **UNVERIFIED**) | 85.6% ($1.13) | 67.4% ($0.45) | **67.7%** (v), the top open row | $2.00 / $0.25 / $6.00 (Together) | — | $0.67 |
| **MiniMax M3** (MiniMax Community, 1M context) | 75.0% ($0.42) | 53.6% ($0.21); 66.0 (v) | 59.0% (v) | $0.30 / $0.06 / $1.20 (Together) | — | $0.39 |
| Qwen3.8-27B (Apache-2.0, dense, self-hostable) | 86.0% ($1.08) | 58.4% ($0.68) | 61.7% (v) | self-host | Willison's local pick | $1.16 |
| DeepSeek V4 Pro 0813 (MIT; API retired by DeepSeek) | 96.4% ($0.10) | 54.7% ($0.20) | 55.4% | $1.32 / — / $3.96 (Together) | — | $0.37 |

Shortlist of six: Kimi K3 (the accuracy ceiling; licence review), DeepSeek V4.1 Flash (price for performance; MIT), GLM-5.3 (incumbent), GLM-5.3-Flash (a low-risk-class tier), Qwen3.8-Max (SWE-bench Pro leader among open rows), MiniMax M3 (1M context). No October 2026 open-weight tool-calling ranking was found; [attractorbench](https://github.com/strongdm/attractorbench) and our own tool-loop suite are the tie-breakers. Published cost-per-resolved-issue tables mix denominators and are **UNVERIFIED**.

### 5.5 Ranked: worth reproducing in an open self-hosted factory

1. **Holdout checks outside the repository, and a satisfaction threshold per risk class** (StrongDM; Abenhaim's two-clean-passes stop rule).
2. **Risk calibration with an evidence bar** (RADAR): a conservative threshold per class, widened only while revert and incident rates hold.
3. **A declared merge-gate vocabulary** copied from gh-aw: `required-labels`, `allowed-base-branches`, `max-patch-files`, `protected-files: request-review`, `staged` dry run, the default branch always refused.
4. **Path-scoped reviewer authority** that counts toward required approvals (GitHub, 2026-09-01).
5. **Fail-closed everywhere**: hooks that block on failure, a detector outage that requests changes, exec disabled without a sandbox, no egress without a policy.
6. **Reviewer findings routed to the implementer before anything is posted** (Devin).
7. **A post-merge monitoring plan per PR feeding the revert breaker**, and a follow-up-fix rate beside the revert rate (Cursor Rollouts; Xia and Miller).
8. **AST-based shell policy** instead of regexes (OpenHands SDK 1.55.0).
9. **Goal gates, checkpoints and per-class model and effort selection** (Attractor).
10. **Cost per merged PR as the fleet KPI** (Devin), and cost per test divided by pass rate as the bake-off metric.
11. **Oracle-backed intake classes**: a code-scanning alert → a fix → the detector re-run, as the next auto-merge class after Markdown links.
12. **Prompt-injection hygiene at intake**: hidden-character filtering, mentioned files that cannot alter instructions, threat detection on outputs and patches.

## 6. Not found, or unverified

"Death Mode" as a StrongDM practice; a Codex cloud task API, best-of-N flags and budgets; Devin webhooks and pricing; Jules after 2026-03-09; Agent HQ-titled changelog entries; MCP Registry GA; AuthZEN 1.0 "final"; Cursor per-tool MCP allowlists (forum reports only); the Qwen3.8-Max licence; a 2026 Google paper on reviewing AI-authored changes; a CloudEvents profile for agents; A2A joining the Agentic AI Foundation.
