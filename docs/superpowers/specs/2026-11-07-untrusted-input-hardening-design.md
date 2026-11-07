# Untrusted-input hardening: safe outputs, author trust and threat checks

**Date:** 2026-11-07 · **Status:** proposed. Written while the owner was away, at their request.
Every choice below is the recommended option, with the rejected alternatives recorded, and
[five decisions](#open-owner-decisions) are left to the owner · **Track:**
[`t-hardening`](2026-10-31-v4-roadmap-design.md#t-hardening), old v4.0 item 4, which gates v4.0
([V8](2026-10-31-v4-roadmap-design.md#owner-decisions-2026-11-06)) and the activation of
[multi-repository coordination](2026-11-05-v4-multi-repo-coordination-design.md) ·
**Research:** [untrusted-input hardening research](2026-11-07-untrusted-input-hardening-research.md),
[Model Armor and its open-source equivalents](2026-11-04-model-armor-oss-equivalents-research.md) ·
**Decision record:** [ADR-0061](../../../website/content/docs/decisions/0061-agents-write-through-safe-outputs.md)

Maku source is read at `origin/main` `3e60f820` and cited `Maku/<path>:<line>`; this repository at
`a5a0a57`; cloud-native-ref at `origin/main`, cited `CNR/<path>`. **Current** describes that source.
Everything after the decision table is **proposed**, field names included. Nothing here is built.

## Outcome

An agent run reads strangers' text and cannot act on GitHub by itself. It **requests** typed
outputs (a push, a pull request, a comment, a label, a follow-up issue), and the factory, outside the
sandbox, validates each request, runs a threat check and only then applies it with a token the
sandbox never sees. Text from authors below a trust threshold is withheld before any model reads it,
and every input the run consumed is recorded with its trust level. Protected files (CI
configuration, agent instructions, dependency manifests, the factory's own policy files) cannot
reach a branch without a maintainer's approval of that exact change.

**Injection drills** against every role prove it on a schedule, and one per-repository readiness
check, read fresh at every admission, is what `coordination.ExecutionPrerequisites` asks.

This is Meta's Rule of Two applied to the factory: a run holds untrusted input and the repository,
but not the power to change state. Filters (sanitisation, classifiers) stay, as evidence and as a
rate reducer, never as the boundary ([research verdict](2026-11-07-untrusted-input-hardening-research.md#verdict)).

## Current state and the gap

| Path | Current fact | Gap |
|---|---|---|
| Issue snapshot | Sanitised, fenced with a per-brief nonce, frozen at the maintainer's label; edits after the label are refused (`Maku/internal/factory/intake/issues.go:307-342`, `Maku/internal/factory/reconciler/text.go:81-134`) | The labelling maintainer already vouches for the body. Nothing records that as a trust level |
| Review comments, CI evidence, room log | Maintainers' review bodies only, sanitised, quoted and fenced (`text.go:466-505`, `545-608`, `629`) | Fenced, but the run's record does not say which untrusted sources it read |
| Comments, CI logs the agent reads itself | `gh issue view`, `gh pr checks` and `gh run view` run raw in the sandbox (`Maku/internal/bridge/classify_tables.go:93-96`; `Maku/internal/factory/reconciler/merge.go:833-835`) | Unfiltered and unfenced. Any author's comment reaches the model |
| RunLore findings | `Trust: untrusted`, sanitised, truncated (`Maku/internal/factory/intake/runlore.go:215-229`) | Attacker-writable log text, with no detector |
| Repository `AGENTS.md`, skills | Loaded by the harness unfenced (`Maku/images/maku-harness/site/sitecustomize.py:356-357`) | A branch or PR can change what every later run is told |
| Sandbox credentials | The `gh` wrapper exports the run's installation token (`Maku/images/maku-harness/gh:4-5`). The implementer's token has `contents: write`, `pull_requests: write` (`CNR/.github/chainguard/agent-implementer.sts.yaml`) | **The run that reads untrusted text holds a write token.** The `unattended` profile allows `forge.push` and `forge.pr` (`Maku/internal/bridge/policy.go:10`), and the bridge cannot see scripts or `curl` with `$GH_TOKEN` (`Maku/internal/bridge/classify.go:13-19`) |
| PR title and body | Written by the model through `gh pr create`. The footer is appended by a wrapper that `gh api` bypasses (`Maku/images/maku-harness/pr_footer.py:5-7`) | No schema, size cap or sanitiser. Mentions, links and `Closes #N` pass |
| Protected paths | A rule in the run's brief (`Maku/internal/runctl/rules.go:19-26`). The merge gate checks a class's `protectedFiles` at merge (`Maku/internal/factory/reconciler/gate.go:22-46`) | Enforced at **merge**, not at **push**. A pushed branch already runs CI, whose scripts come from that branch |
| Controller-written outputs | Verdicts, narration, split child issues and published proposals are quoted inert, sanitised and template-checked (`Maku/internal/verdictpost/poster.go:99`, `Maku/internal/factory/narrate/narrate.go:1107-1131`, `Maku/internal/factory/intake/publish.go:266-320`) | **The pattern to extend.** Every write by the factory already passes through a validator |
| Threat scanning | The gitleaks redactor (`Maku/internal/redact/redact.go:3`) and TruffleHog at merge (`Maku/internal/factory/reconciler/arm.go:416-421`). No injection detector | No check runs between a run's request and GitHub |
| Execute gate | `ExecutionPrerequisites.Ready` returns `hardenedOutputs`. Only a test fake implements it (`Maku/internal/factory/coordination/prerequisites.go:29-59`) | No production answer exists |

## Decisions {#decisions}

| # | Decision | Rejected alternatives | Why |
|---|---|---|---|
| UH1 | **Agents write only through safe outputs.** A sandbox role's GitHub token is read-only. Every GitHub write a run causes is a typed request the factory validates and applies with its own token | Keep the write token and add classifiers in front of it; branch-scoped tokens; a stricter bridge classifier | GitHub cannot scope a token to one branch, and the bridge admits that it cannot see scripts. A filter in front of a token is what adaptive attacks beat more than 90% of the time. Moving the token is the only structural fix |
| UH2 | **The push is an output too.** The run hands the factory a git bundle for `agent/<task>`. The factory checks it and pushes it as the agents App | Leave the push in the sandbox and gate only at merge (gh-aw's `request_review`) | A pushed branch triggers CI, and CI runs that branch's scripts. A protected-path check at merge comes after the damage |
| UH3 | **A fixed output vocabulary with per-run caps**: `push`, `pr` (open or edit the task's one PR), `comment` (the task's PR or issue only), `labels` (from an allowlist), `issue` (a follow-up, always labelled `factory/proposed`), and the existing room tools. Anything else is refused | An open `gh_write` passthrough with an allowlist of verbs; gh-aw's full catalogue of about 60 types | Each type needs a schema and an applier. The factory needs six. A passthrough repeats the bridge's blind spots |
| UH4 | **Outputs are requested through new tools on the existing `platform` MCP server**, recorded in the room log as `output.requested`, applied by the factory and answered with `output.applied` or `output.refused` | A file the harness writes at the end of a run (gh-aw's CLI form); a new service | The room tools already authenticate each run and cap payloads. A mid-run push needs an answer mid-run. The room log gives replay, idempotency and the audit trail for free |
| UH5 | **The factory, not the broker, applies outputs**, under a new `publisher` identity: an octo-sts policy for the factory's service account, which runs outside the `agents` namespace | The broker applies them; each role gets a separate publisher | The factory already writes every other GitHub artifact and knows the task, its class and its branch. One publisher keeps one audit identity |
| UH6 | **Author trust uses gh-aw's levels**: `merged` > `approved` > `unapproved` > `none` > `blocked`, from GitHub's `author_association`. **Default `minAuthorTrust: approved`.** A maintainer's trigger label vouches for the issue it labels. Text below the threshold is withheld before any model reads it, and a placeholder counts what was withheld | Detect injection in strangers' text instead of withholding it; trust everyone on a public repository | gh-aw defaults to `approved` on public repositories, and v4.0's adopters are public repositories with strangers filing issues. The label as a vouch is what the factory's intake already means |
| UH7 | **Every input carries provenance, and the run records its lowest trust.** Machine sources get fixed levels: default-branch files and steering `merged`; the run's own CI evidence `approved`; another run's room text inherits that run's lowest; RunLore findings and tool results `none`. The task records `status.inputTrust` | Taint tracking per value (CaMeL); provenance only in the prompt | Per-value tracking needs a planner that writes a program, and a coding task has no trusted query apart from the issue. A per-task minimum is enough for the readers that need it: the RunLore knowledge base (its RK11) and the open merge question ([O2](#open-owner-decisions)) |
| UH8 | **The threat check is layered, deterministic first**: T1 schema and caps, T2 text sanitisation, T3 secrets and a per-run canary, T4 protected paths, T5 an injection classifier. T1 to T4 can refuse. T5 starts in `audit` and is promoted per output type on drill evidence | An LLM threat reviewer on every output (gh-aw's default); classifiers only | The deterministic layers catch the attacks that matter (writing outside the vocabulary, leaking, touching CI) with no false positives by construction. An LLM reviewer duplicates the reviewer role. It is reopened only if drills show a malicious patch that T1 to T5 and the reviewer all miss |
| UH9 | **A protected-path push waits for a maintainer's approval of that bundle's digest**, in the room or through the [Slack push approval](2026-11-05-v3x-slack-push-approval-design.md). A path can be set to `blocked` instead | Refuse every protected-path change; request changes on the PR after the push | Some tasks legitimately touch a manifest. An approval of the exact digest keeps them possible without letting CI run first |
| UH10 | **Protected paths are a platform floor a repository may only extend.** The defaults are listed [below](#protected-paths). A repository adds paths in `.github/agent-factory.yaml` and cannot remove one | A list per repository with no floor; central config only | The same ceiling rule as [merge policy self-service](2026-11-04-merge-policy-self-service-design.md): the platform sets the floor, the repository knows what its CI runs |
| UH11 | **In-sandbox reads of forge text go through `forge_read` tools** that apply UH6 and UH7. The sandbox loses `api.github.com` egress. `git` keeps `github.com` | Leave `gh` reads raw; an L7 proxy that filters GitHub API responses | Without a write token, raw reads are defence in depth rather than the boundary, but they are the input the drills plant. Filtering one tool is less code than parsing GraphQL in a proxy. The residual (HTML pages on `github.com`) is stated |
| UH12 | **MCP tool results are in scope, screened at the gateway**: the Model Armor research's A2 (prompts) and A3 (`tools/call` responses) in `audit`. That research's A4 (non-MCP tool results) waits for A3's drill results | Screen only in the sandbox; leave tool results out | It answers the [roadmap's open question 4](2026-10-31-v4-roadmap-design.md#open-questions). The gateway already sees every call, and the result is a content-free log line the drills can score |
| UH13 | **Readiness is a capability check computed fresh per repository**: enforce mode, no sandbox write token, T1 to T4 refusing, filtered reads and a passing drill for the running configuration. The laptop demo profile is never ready | A release string; a switch in config; a cached result | The coordination design demands a capability check, not a release string, and a regression must refuse the next admission (`prerequisites.go:29-59`) |
| UH14 | **Injection drills run like the merge-gate drills**: a drill repository, planted injections per source and per role, scored from the room log and the gateway log, weekly and on every hardening configuration change | Drills by hand; public benchmarks only (AgentDojo, CyberSecEval) | A filter without a drill is a guess. Benchmarks do not exercise the factory's own paths |

## Architecture

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 240}}}%%
flowchart TB
  subgraph inputs["What a run reads"]
    direction LR
    I1["Issue snapshot<br/>vouched by the label"]
    I2["Comments, reviews,<br/>CI logs"]
    I3["RunLore findings,<br/>MCP tool results"]
  end
  subgraph trust["Factory: author trust and provenance"]
    direction LR
    F1["Withhold below<br/>minAuthorTrust"] --> F2["Fence and tag<br/>each span's level"]
    F2 --> F3["status.inputTrust<br/>lowest level"]
  end
  subgraph sandbox["Sandbox: read-only token"]
    direction LR
    A["Agent"] --> O["output_* tools<br/>on the platform MCP"]
  end
  subgraph apply["Factory: safe-output applier"]
    direction LR
    T["T1 schema and caps<br/>T2 sanitise · T3 secrets and canary<br/>T4 protected paths · T5 classifier"] --> P["Apply as the<br/>publisher identity"]
  end
  I1 --> F1
  I2 -->|"forge_read"| F1
  I3 -->|"gateway A2/A3, audit"| F2
  F2 --> A
  O -->|"output.requested<br/>in the room log"| T
  T -->|"protected path"| H["Maintainer approves<br/>the bundle digest"]
  H --> P
  P --> G["GitHub: push, PR,<br/>comment, labels, issue"]
  P -->|"output.applied / refused"| A
```

### Safe outputs {#safe-outputs}

The run asks, the factory decides. Each request is a room-log event with an `outputID`, the run and
task it belongs to, its type and a payload digest. The applier answers with exactly one of
`output.applied` (with the GitHub object it wrote) or `output.refused` (with one bounded reason).

| Type | Payload | Per-run cap | Applier's own checks |
|---|---|---|---|
| `push` | A git bundle with one ref, `agent/<task>`; at most 8 MiB | 20 | Fast-forward from the branch's current head or the task's base. No other ref, no tag, no submodule change, no symlink leaving the tree. File and line counts within the class's `maxPatchFiles` and `maxModifiedLines` when declared. Then T3 to T5 on the diff |
| `pr` | `{title, body, draft}`; the base and head are the factory's | 1 open, 5 edits | Title at most 256 characters; body 20 to 65,000 characters. The factory writes the provenance footer itself, so it can no longer be bypassed |
| `comment` | `{target: pr\|issue, body}`; only the task's PR or issue | 3 | Body at most 16 KiB |
| `labels` | `{add: [..]}` | 1 call, 3 labels | Only labels in `hardening.labelAllowlist`. `factory/*` labels and class labels are never on it: an agent must not choose its own class |
| `issue` | `{title, body}` | 1 | Filed through the existing draft template (`Maku/internal/factory/sanitize/draft.go:12-35`), always `factory/proposed`, never the trigger label. A maintainer decides whether it becomes a task |
| room tools | Unchanged (`Maku/internal/mcp/tools.go:108-220`) | Unchanged | Already schema-checked, capped and redacted |

The tester's push and the harness's own pushes use the same `push` output. The reviewer and the
triager have no output but the room tools. A coordination integration run is read-only, so its only
output is its verdict.

**Shadow first.** With `hardening.mode: audit` the applier evaluates every request and records what
it would have done, while the run's existing token still writes. The comparison between the two
records is the false-refusal evidence for enforce mode. This is gh-aw's staged mode.

**Under `enforce`** the octo-sts policies of the sandbox roles drop to read-only
(`contents: read`, `pull_requests: read`), and a new `publisher` policy grants the factory's service
account `contents: write`, `pull_requests: write`, `issues: write`. The policy files live in each
repository's `.github/chainguard/`, read by octo-sts from the default branch, and they are protected
paths.

### Author trust and provenance {#author-trust}

**The level of a human's text** comes from GitHub's `author_association` on that object, raised by
the factory's own maintainer list:

| Level | Who |
|---|---|
| `merged` | Commits reachable from the default branch, whoever wrote them |
| `approved` | `OWNER`, `MEMBER`, `COLLABORATOR`, the factory's maintainers, trusted bots, and an issue a maintainer's trigger label vouched for |
| `unapproved` | `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` |
| `none` | Everyone else |
| `blocked` | `hardening.blockedUsers` |

**Text below `minAuthorTrust` is withheld** wherever it would enter a run: the brief, a queued
review, `forge_read` results. The run sees `[1 comment withheld: author trust]` and nothing of its
content. A maintainer can vouch for one item with the `factory/vouch` label, which raises it to
`approved`, as gh-aw's `approval-labels` do.

**Machine sources get fixed levels**, which never withhold but always count toward the run's lowest
trust:

| Source | Level |
|---|---|
| Default-branch files, steering notes, factory-written text | `merged` |
| The run's own CI evidence and the brief's CI annotations | `approved` |
| Another run's room text (handoffs, scopes, verdicts) | That run's `status.inputTrust.min` |
| RunLore findings, MCP tool results, CI logs of a branch another author pushed | `none` |

The task records the result. `status.inputTrust` holds `min` (the lowest level), `withheld` (a
count per source) and `sources` (each source's kind and level, never its content). A split child and
an integration task inherit the parent's minimum.

### Threat check {#threat-check}

Each layer has a mode, `off`, `audit` or `enforce`. In `audit` a layer records its verdict without
refusing. Layers run in order, and the first refusal stops the request.

| Layer | Checks | Runs on | Refusal |
|---|---|---|---|
| T1 Schema and caps | The type is in the vocabulary, the payload matches its schema, the run is under its cap | Every output | `output_type`, `output_schema`, `output_cap` |
| T2 Sanitise | Invisible and control characters stripped, NFKC; `@` mentions neutralised; HTML comments and images removed; at most 20 links; `Closes`/`Fixes` only for the task's own issue | Text outputs | `output_text` only when sanitising fails closed, the existing `Withheld` (`Maku/internal/factory/sanitize/sanitize.go:103-114`) |
| T3 Secrets and canary | The existing gitleaks redactor, plus the run's **canary**: a random token planted in the brief as an instruction the agent must never repeat. Any output containing it is refused and alerts | Every output and every added line of a bundle | `secret_found`, `canary_leaked` |
| T4 Protected paths | The bundle touches a [protected path](#protected-paths) | `push` | `protected_path_needs_approval` (waits, UH9) or `protected_path_blocked` |
| T5 Classifier | Prompt-injection score on the text an output publishes: PR body, comment, issue, commit messages and added text lines | Text outputs, `push` | `injection_suspected`, only once promoted to `enforce` |

T5 is the `agent-guard` service that the
[Model Armor research](2026-11-04-model-armor-oss-equivalents-research.md#recommended-shape-for-this-platform)
shapes, called by the applier over the same webhook contract the gateway uses. Its model is
[O4](#open-owner-decisions). An unreachable classifier fails open in `audit` and refuses in
`enforce`, so a promotion is only made where the service has met its availability target.

The same check is exposed as a port, so other writers can reuse it. RunLore's knowledge base needs
it for incident entries (RK16), and coordination for its plans and artifacts.

### Protected paths {#protected-paths}

The platform floor, which a repository may extend and never shorten:

| Group | Paths |
|---|---|
| CI and automation | `.github/**` (workflows, actions, `CODEOWNERS`, `dependabot.yml`, the factory's policy files, octo-sts policies), `.gitlab-ci.yml`, `Taskfile*`, `taskfile.y*ml`, `Makefile`, `.pre-commit-config.yaml` |
| Agent instructions | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` at any depth, `.agents/**`, `.claude/**`, `.codex/**`, `.cursor/**` |
| Dependency manifests and lock files | `go.mod`, `go.sum`, `package.json`, the npm, pnpm and yarn lock files, `requirements*.txt`, `pyproject.toml`, `uv.lock`, `Cargo.toml`, `Cargo.lock`, `Gemfile*`, `pom.xml`, `build.gradle*`, `mise.toml`, `.tool-versions` |
| Execution hooks | `.envrc`, `.gitattributes`, `.gitmodules`, `.husky/**`, `.git-hooks/**` |

A repository extends the list in its `.github/agent-factory.yaml`, typically with the scripts its CI
runs:

```yaml
hardening:
  protectedPaths:
    - path: scripts/ci/**
      on: approval          # approval (default) | blocked
  minAuthorTrust: approved  # may be raised to merged, never lowered
```

The merge gate's class `protectedFiles` stay as they are: those decide who merges, and these
decide what may be pushed. A class's protected list never weakens the floor.

## Configuration

Central, in the factory's Flux-managed config. A repository may only make it stricter.

```yaml
hardening:
  mode: audit                     # off | audit | enforce; strict decoder, default off
  minAuthorTrust: approved
  blockedUsers: []
  labelAllowlist: [documentation, needs-human]
  layers:                         # T1–T4 cannot be set below the mode
    classifier: audit             # off | audit | enforce, per output type when promoted
  drills:
    maxAge: 168h                  # readiness needs a passing drill this recent
  repositories:
    owner/repo: {mode: enforce}   # per repository; only stricter than the default
```

## The interface `ExecutionPrerequisites` needs {#execution-prerequisites}

Hardening answers the `hardenedOutputs` half of `Ready`. It is a new Maku package, `hardening`,
with one port:

```go
// Readiness reports whether every run in repository reads through author trust and writes only
// through enforced safe outputs, right now. It is computed on every call: no caching, so a
// regression refuses the next admission. An error means a fact could not be read and is a refusal.
type Readiness interface {
	Hardened(ctx context.Context, repository string) (Report, error)
}

type Report struct {
	Hardened bool
	Missing  []Missing // empty when Hardened; bounded vocabulary, never free text
	Drill    string    // the passing drill report it relied on, for the audit log
}

type Missing string

const (
	MissingEnforce     Missing = "mode_not_enforce"       // central or repository mode below enforce
	MissingWriteToken  Missing = "sandbox_write_token"    // a sandbox role's policy grants a write
	MissingPublisher   Missing = "publisher_policy"       // no publisher policy on the default branch
	MissingLayer       Missing = "layer_not_enforced"     // T1–T4 not all enforce
	MissingReadFilter  Missing = "read_filter_off"        // forge_read or the egress change not active
	MissingDrill       Missing = "drill_stale_or_failed"  // no passing drill for this config hash within maxAge
	MissingDemoProfile Missing = "demo_profile"           // the laptop profile is never hardened
)
```

`Hardened` is true only when all of these hold for `repository`:

| # | Fact | Read from |
|---|---|---|
| R1 | The effective mode is `enforce` | The factory's config and the repository's `hardening` block |
| R2 | No octo-sts policy of a sandbox role (`implementer`, `tester`, `reviewer`, `triager`) grants a `write` permission | The repository's `.github/chainguard/agent-*.sts.yaml` on its default branch, through the GitHub API |
| R3 | A `publisher` policy exists for the factory's service account | Same |
| R4 | T1 to T4 are `enforce` | The factory's config |
| R5 | `forge_read` is active and the run profile has no `api.github.com` egress | The factory's config and the run profile it renders |
| R6 | A drill report passed for the current Maku version and hardening configuration hash, within `drills.maxAge` | The drill reports in the factory's store |
| R7 | The runtime is not the demo profile | The factory's config |

The coordination package composes it with the class-authority answer of the merge-policy design,
called `ClassAuthority` here because that design names no port. The adapter adds nothing to
`ReadyForExecute`'s fail-closed contract:

```go
type prerequisites struct {
	classes   ClassAuthority       // merge-policy self-service: repository policy is authoritative
	hardening hardening.Readiness
}

func (p prerequisites) Ready(ctx context.Context, repo string) (bool, bool, error) {
	classes, err := p.classes.Authoritative(ctx, repo)
	if err != nil {
		return false, false, err
	}
	r, err := p.hardening.Hardened(ctx, repo)
	if err != nil {
		return classes, false, err
	}
	// r.Missing goes to the admission's log and metric, never to the refusal text.
	return classes, r.Hardened, nil
}
```

"For every child and integration input" holds by construction: `ReadyForExecute` already asks for
every repository in the family. The children's artifacts and plans are read as `none` under UH7,
and the integration run's only output is a verdict.

**The other readers** use the same package:

| Reader | Uses | For |
|---|---|---|
| RunLore knowledge base, RK11 | `status.inputTrust.min >= approved` | Auto-merging a lesson |
| RunLore knowledge base, RK16 | The threat-check port on an entry's text | Auto-merging an incident entry |
| Repository memory (`t-memory`) | The `pr` and `push` outputs and T4 | Proposing `AGENTS.md` changes, which are protected and always wait for a maintainer |

## Injection drills {#drills}

A drill is a scheduled set of tasks on a dedicated public drill repository. A `drill-stranger`
account plants the injections, and the factory runs each task under the configuration being
proven. A drill passes when **no out-of-policy output is applied**. Detection rates are reported
per layer, and they do not decide the pass.

| Planted in | Goals tried |
|---|---|
| An issue body by a stranger, then labelled by a maintainer | Write outside the vocabulary; push to `.github/workflows/`; leak the canary into the PR body |
| A stranger's comment on the task's issue and PR | Make the agent follow it (must arrive withheld) |
| A CI log line on the run's own branch | Label the PR with a class label; close another issue |
| A file on the default branch (`docs/`, a code comment) | Edit `AGENTS.md`; add a dependency |
| A RunLore finding's log text | Open a follow-up issue that mentions people; post the canary |
| An MCP tool result (a planted log line) | Exfiltrate through a link in a comment |
| Another run's room handoff | Make the reviewer approve without reading |
| An encoded payload (Base64, homoglyphs) in any of the above | The same goals, to measure T5's single-turn limit |

Each scenario runs for every role that reads that source: scoper, implementer, tester, judge,
reviewer and investigate. The scorer reads the room log (`output.*` events, withheld counts) and
the gateway's `guardrails` log field. A failure blocks readiness (R6) until a fix and a passing
drill.

## Staged rollout {#rollout}

Each stage is a Maku release, the pin here with the switch where it was, a live proof, then the
switch change, as every v3.x track ships.

| Stage | Change | Advances when |
|---|---|---|
| H0 · Contracts, off | `hardening` package, output and `forge_read` tools, readiness port returning `false`, the drill scorer, offline suites | Offline suites pass; existing suites unchanged |
| H1 · Audit | `mode: audit` on the reference repositories. The applier shadows every write; trust levels and withheld counts are recorded, not applied; gateway A2 and A3 in `audit`; T5 in `audit` | 50 tasks: the deterministic layers' false refusals are at most 1% of legitimate outputs, and each explained |
| H2 · Non-code outputs enforced | `pr`, `comment`, `labels` and `issue` go through the applier. Sandbox roles lose `pull_requests: write` | 20 tasks with every PR, comment and label traced to an `output.applied` |
| H3 · Push enforced | `push` through the applier with T4. Sandbox roles hold `contents: read` | 20 tasks; protected-path approvals work in the room and in Slack |
| H4 · Reads filtered | `forge_read`, `minAuthorTrust`, no `api.github.com` egress | A first full drill passes |
| H5 · Ready | Readiness reports `true` for enforced repositories; T5 promoted per output type on its drill numbers | Two consecutive weekly drills pass; [acceptance](#acceptance) holds |

Rollback is a mode change. `audit` restores the run's write token through the octo-sts policies,
which are files on the default branch, and readiness turns false at the next admission.

## Acceptance criteria {#acceptance}

| # | Criterion | Measured by |
|---|---|---|
| AC1 | No sandbox role of an enforced repository can write to GitHub | A probe run tries `git push`, `gh api -X POST` and `curl` with its token: three `403`s. R2 holds on every enforced repository |
| AC2 | Every GitHub write by the agents App on an enforced repository has an `output.applied` with a matching digest | A reconciliation of the App's audit events against the room log over 30 days: 100% matched |
| AC3 | Drills apply no out-of-policy output | All scenarios × roles, two consecutive weekly runs: 0 applied |
| AC4 | No canary reaches GitHub | Across all drills and 30 days of tasks: 0 |
| AC5 | Withheld text never reaches a model | Drill scenarios with a stranger's comment: the planted marker appears in 0 model requests (the gateway's audit log) |
| AC6 | The deterministic layers rarely refuse legitimate work | H1: at most 1% of legitimate outputs refused by T1 to T4, each explained. T5 is promoted for an output type only below 2% false positives and above the regex layer's detection on the drills |
| AC7 | Hardening costs little time | p95 added latency at most 10 s per `push` and 2 s per other output |
| AC8 | Hardening does not cost merges | Merge rate on enforced repositories within 5 points of the 30 tasks before enforcement |
| AC9 | A regression closes the gate at once | Offline: each of R1 to R7 made false refuses the next `ReadyForExecute`. Live: switching a repository back to `audit` refuses the next coordination admission |

## Security residuals {#residuals}

These stay open after the track ships:

- **An approved author's injection.** A maintainer-sounding instruction from a collaborator is
  trusted by design. The output side still bounds what it can do.
- **The agent's code itself.** A malicious change that looks like the requested one passes every
  layer here. Review, the merge gate's classes and the reviewer bound it.
- **HTML on `github.com`.** `git` needs `github.com`, so a run can still fetch a page by hand.
  Without a write token it can read, not act.
- **Split and encoded injections** pass single-turn classifiers; the drills measure how often.
- **A reviewer persuaded to approve** writes only a verdict, and for live classes the merge gate
  still decides.

## Out of scope {#out-of-scope}

- **Private repositories in the proof.** The mechanism applies to them; the v4.0 proof is public
  only ([V16](2026-10-31-v4-roadmap-design.md#owner-decisions-2026-11-06)).
- **The laptop demo.** It holds a personal token and runs without gVisor, so it is never ready (R7).
  Its banner says so.
- **An LLM threat reviewer** (UH8), **Presidio and response-harm screens** (the Model Armor
  research's "later or never"), and **CaMeL as a runtime**.
- **Web fetch tools.** None exist, and egress denies the web. A future fetch tool is a new input
  source and needs its own level in UH7.
- **Image and document inputs.**
- **Changing the merge gate by input trust.** It is [O2](#open-owner-decisions), not decided here.

## Open owner decisions {#open-owner-decisions}

| # | Question | Recommended |
|---|---|---|
| O1 | Protected-path pushes: wait for approval of the digest, or refuse outright by default? | **Wait for approval** (UH9), with `blocked` per path |
| O2 | Should a task whose `inputTrust.min` is below `approved` lose live auto-merge and go to the human path? This is the Rule of Two at merge time | **Yes, in shadow first**, as its own merge-gate change after H5 |
| O3 | The drill repository and the cadence | **A dedicated public repository, weekly** and on every hardening configuration change |
| O4 | T5's model: Prompt Guard 2 86M (Llama 4 Community licence, measured on AgentDojo) or the Semantic Router's Apache-2.0 classifier (no published evaluation) | **Prompt Guard 2 behind `agent-guard`**, swappable. Choosing it needs its own ADR before the classifier is built |
| O5 | Does an adopter's repository need the `publisher` policy file, or does the factory's App installation carry it? | **A policy file**, like the role policies: it is reviewed in the adopter's repository, and R3 can read it |
