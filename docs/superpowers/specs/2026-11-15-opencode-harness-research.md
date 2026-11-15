# OpenCode as a second Agent Factory harness: research

**Date:** 2026-11-15 · **Status:** research supporting the [design](2026-11-15-opencode-harness-design.md) ·
**Target:** platform v5.x, no implementation in the current release line · **Method:** read Maku and
ai-native-ref at current `origin/main`, verify upstream documentation and source at pinned releases,
inspect container images, and run one local Docker readiness comparison.

## 1. Executive answer

OpenCode is a credible second harness, not a justified unconditional replacement. Its strongest
arguments are a much smaller runtime, fast server startup, native agent permissions, and a headless
HTTP/SSE API. Its strongest drawbacks are missing stuck-loop detection, a different event and
permission protocol, unknown provider/cache behavior, and the substantial recovery and room logic
that Maku has already built around OpenHands.

The useful experiment replaces the inner loop only. Maku's run-controller, gVisor pods, per-run
identities, gateway budgets, room broker, merge controls, judge, and workflow engine remain.
Local-to-cluster harness parity is not a requirement: a developer may use any local coding agent.

## 2. Sources and versions

| Source | Version read |
|---|---|
| Maku | `origin/main` at `6dc8340f` |
| ai-native-ref | `origin/main` at `f36306d` |
| OpenCode | v2.3.0, tag `a6b15d33`, image digest `sha256:998e3e184c650e603d8bacb5cbeaeb090837078262c25521a7136b0375d2b652` |
| OpenHands | agent-server and SDK 1.56.0, as pinned by `images/maku-harness/Dockerfile` and `requirements.in` |

Upstream primary sources:

- [OpenCode installation and images](https://opencode.ai/docs/)
- [OpenCode CLI commands](https://opencode.ai/docs/cli/commands/)
- [OpenCode server API](https://opencode.ai/docs/server/)
- [OpenCode agents](https://opencode.ai/docs/agents/) and [permissions](https://opencode.ai/docs/permissions/)
- [OpenCode providers](https://opencode.ai/docs/providers/), [MCP](https://opencode.ai/docs/mcp-servers/), and [migration](https://opencode.ai/docs/migrate-v1/)
- [OpenCode v2.3.0 release](https://github.com/anomalyco/opencode/releases/tag/v2.3.0)
- [OpenCode non-interactive renderer](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/cli/src/run/noninteractive.ts)
- [OpenCode session runner](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/session/runner/step.ts)
- [OpenHands stuck detector](https://docs.openhands.dev/sdk/guides/agent-stuck-detector)
- [OpenHands terminal session](https://github.com/OpenHands/software-agent-sdk/blob/v1.56.0/openhands-tools/openhands/tools/terminal/terminal/terminal_session.py)

No existing ai-native-ref PR duplicates this design. The search found the earlier, broader harness
roles study in PR #234; its conclusion was to measure role value rather than replace the harness.

## 3. What Maku actually runs

Maku has four AgentRun roles: `implementer`, `reviewer`, `tester`, and `triager`. A scoper is a
triager mode, the completion judge is a stateless model call inside an implementer run, and search
is a bounded child conversation. The three workflows select different role sets; four sequential
pods do not run on every task.

`images/maku-harness/agent_run.py` starts OpenHands agent-server on loopback, constructs the SDK
conversation, and drives it through its HTTP API. The image also contains the git credential
helper, GitHub CLI wrapper, repository checks, tester contract, safe-output push path, search tool,
loop policy, progress notes, tracing, and shutdown logic.

The room bridge is not a stdout reader:

- `internal/bridge/harness.go` reads an append-only event log with replay cursors and exposes
  steering, interruption, confirmation, resume, and run status.
- `internal/bridge/mapping.go` maps OpenHands events to bounded room payloads.
- `internal/bridge/bridge.go` handles back-pressure, idempotent delivery, approval reads ahead,
  reconnects, heartbeats, and final draining.
- `internal/runctl/pod.go` builds probes, images, projected identities, and shared pod state.

`AgentRun.spec.harness` already exists as an optional immutable field whose only admitted value is
`openhands` (`api/v1alpha1/agentrun_types.go:87`). This is the correct extension seam.

## 4. Claim-by-claim findings

### 4.1 Control-plane redundancy: mostly correct

Maku does not use OpenHands Agent Canvas, OpenHands sandbox lifecycle, or OpenHands webhook
orchestration. Those responsibilities already belong to Maku and ai-native-ref. OpenHands still
provides the inner agent loop, tool schemas, context condensation, terminal session, persistence,
and stuck detection.

The judge, room broker, merge gate, budgets, and workflow engine are Maku's, not OpenHands'.
Replacing the inner loop removes none of those components.

### 4.2 Image footprint and startup: strong early signal, incomplete comparison

Measurements on the local workstation:

| Image | Uncompressed size reported by Docker | Contents relevant to a Maku run |
|---|---:|---|
| `maku-harness:inspect` | 4,041,935,462 bytes | OpenHands plus Maku's complete harness tooling |
| `ghcr.io/anomalyco/opencode:2.0.22` | 226,580,836 bytes | OpenCode and ripgrep |
| `ghcr.io/anomalyco/opencode:2.3.0` | 276,885,237 bytes | OpenCode and ripgrep |

One concurrent, ordinary-Docker startup check measured server readiness at 426 ms for OpenCode
2.3.0 and 6,336 ms for the OpenHands agent-server in `maku-harness:inspect`. This was one sample,
not a gVisor benchmark, not an image-pull comparison, and not a task-duration measurement.

The upstream OpenCode image reported no explicit non-root user and lacked `git`, `gh`, and `mise`
in the tool check. A valid comparison therefore requires the final Maku-owned image with those
tools, checksum-pinned dependencies, a non-root user, no auto-update, and the same security
context as the current harness.

### 4.3 Local/cluster parity: available but deliberately not required

OpenCode supports `AGENTS.md`, repository skills, commands, and local or remote MCP servers. It can
therefore share supported repository-owned behavior with a cluster run.

This is a bonus, not a reason to couple the design to one local client. Personal global settings,
credentials, plugins, and interactive approval rules must not enter the sandbox. V2 also changed
plugin and server APIs, so parity claims need version-specific tests.

### 4.4 Provider routing: supported, with compatibility work

OpenCode's custom provider configuration supports OpenAI-compatible endpoints, environment-backed
credentials, custom headers, request bodies, model aliases, and variants. That is sufficient to
address agentgateway without putting provider keys in the sandbox.

It does not prove behavioral parity for GLM/Z.ai, Anthropic, Kimi, or Mistral. The current harness
has custom handling for reasoning effort, prompt caching, timeout/retry behavior, condenser models,
and usage accounting. Those behaviors must be compared on actual request and response streams.

### 4.5 JSON events: useful diagnostics, not Maku's room contract

`opencode run --format json` emits newline-delimited text, reasoning, tool, step, retry, error, and
usage records. The v2.3.0 renderer reconciles missed live events from the projected message log.

That output is still a CLI presentation format. It is not a promise of Maku's replay, idempotency,
approval, cursor, or shutdown semantics. The production seam should be the version-pinned server
API and SSE event stream, with the generated client and server upgraded together.

### 4.6 Role permissions: defense in depth, not a trust boundary

OpenCode agent profiles can deny edit, shell, subagent, skill, web, MCP, and external-directory
actions. Rules are ordered and support `allow`, `ask`, and `deny`.

A rule on the edit tool does not stop an unrestricted shell command from modifying a file. Reviewers
also need commands such as `agent-checks`, whose child processes are outside OpenCode's tool-call
permission scanner. Existing tokens, egress policies, safe outputs, approval checks, and merge
controls therefore remain authoritative.

### 4.7 Loop recovery: a real gap and an adoption blocker

OpenHands detects repeated action/observation cycles, repeated errors, monologues, alternating
patterns, and repeated context-window errors. Maku maps its terminal `stuck` state into run failure.

OpenCode's V2 permission documentation says `doom_loop` is not a current core action. Its v2.3.0
session runner contains no equivalent repeated-call comparison. Maku must implement detection over
normalized events, interrupt the run, and report `stuck`; budgets and the completion judge alone are
not equivalent.

### 4.8 Shell behavior: different, not simply stateless

OpenHands maintains a terminal session with cwd and interactive input handling. OpenCode creates
individual commands, but v2.3.0 also has persistent PTYs, background jobs, output retention, and
server handoffs. The statement that OpenCode has only a stateless shell is outdated.

The migration still needs explicit tests for cwd/environment persistence, long-running checks,
interruption, process-group cleanup, and output replay.

### 4.9 Browser tooling: no regression

The current Maku harness has no browser tool. Adding Playwright MCP would be a new capability, not
a migration requirement. It belongs in a separate design with its own network, image, and security
review.

## 5. Migration costs omitted from the original statement

1. **Replay and audit:** cursor stability, malformed events, duplicates, oversize payloads,
   redaction, and final reads after the server stops.
2. **Approvals:** mapping OpenCode permission requests to Maku's local and human decision paths.
3. **Disruption:** the 15-second pause/checkpoint/final-read/stop/revoke sequence and process-group
   cleanup.
4. **Persistence:** stable session IDs and restoration of server state on the suspendable run's PVC.
5. **Search:** a synchronous child with model, effort, step, token, time, call-count, and result
   limits; OpenCode 2.3.0's background-subagent default is not a drop-in equivalent.
6. **Provider behavior:** reasoning effort, prompt caching, condensation, usage fields, and retry
   semantics across every enabled provider family.
7. **Telemetry:** run trace context on model and MCP calls, metadata-only span content, and no
   unreviewed OpenCode OTLP logs.
8. **Evaluation accounting:** a failed OpenCode attempt must remain visible after an OpenHands
   rescue, and the rescue must not contaminate either trial arm.

The quoted “490k-token baseline” was not found in the current ai-native-ref documentation. It must
not anchor the decision. Use cost per merged PR, merge rate, end-to-end duration, and token usage by
input, output, cache read, and cache write.

## 6. Alternatives considered

| Approach | Assessment |
|---|---|
| Immediate full replacement | Rejected: provider, room, recovery, and quality evidence is insufficient |
| Optional second harness, all roles per task | Chosen: full-system evidence with a default and fallback unchanged |
| Implementer-only experiment | Rejected by the owner: it would not exercise every role in the next live evaluation |
| Per-role harness selection | Rejected: mixed tasks multiply compatibility and failure combinations |
| CLI NDJSON only | Rejected: steering, permissions, replay, and shutdown are weaker than the server API |
| Embedded TypeScript SDK | Rejected: another runtime in Maku's control path and tighter coupling to internals |
| Independent OpenCode bridge and runner | Rejected: duplicates delivery and recovery logic that must not diverge |
| Go or Rust runner rewrite now | Deferred to a separate specification after the harness decision |
| Local/cluster harness parity as a requirement | Rejected: developers remain free to use any local agent |

## 7. Evidence required for a replacement decision

The design fixes a strict gate: zero critical security, audit, or recovery regressions; no more than
5 percentage points of merge-rate regression; no more than 10% cost-per-merged-PR regression; and at
least 15% lower cost per merged PR or median end-to-end duration. Evaluate after 30 ended tasks per
arm and extend once to 60 when inconclusive. An unmet or underpowered result keeps OpenHands.

After that gate, OpenHands remains an immediate rollback for at least 30 days and 30 ended default
tasks. Its removal is a separate later decision and PR.
