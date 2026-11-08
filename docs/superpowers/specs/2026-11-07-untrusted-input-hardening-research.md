# Untrusted-input hardening: how agent platforms keep strangers' text from becoming actions

**Date:** 2026-11-07 · **Status:** research, input to the
[untrusted-input hardening design](2026-11-07-untrusted-input-hardening-design.md) · **Builds on:**
the [v4 landscape research](2026-10-31-v4-landscape-research.md) (rank 8, "hardening beyond
validated outputs") and the [Model Armor research](2026-11-04-model-armor-oss-equivalents-research.md)
(detectors and gateway hooks). This page does not repeat either; it adds the mechanics of the
reference implementation and the capability-separation literature.

## Verdict

Every defence that holds up against adaptive attacks is **structural**: the component that reads
untrusted text cannot write, and the component that writes cannot be steered by that text. Filters
(classifiers, regex, an LLM judge) reduce the rate and produce evidence, but adaptive attacks beat
12 published filters more than 90% of the time
([Willison, 2025-11-02](https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/)). The
reference open implementation, gh-aw v1.0.0, stacks four layers on one structural move: the agent
job holds no write permission and *requests* typed actions that a separate job validates and applies
([safe outputs](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/safe-outputs.md)).
That shape fits the factory with one difference: the factory's agents must push code, which gh-aw
also routes through a buffered patch rather than a token.

## Patterns

| Pattern | Mechanism | Strength | Cost | Evidence |
|---|---|---|---|---|
| **Safe outputs** (gh-aw) | The agent calls MCP tools (`create_issue`, `add_comment`, `create_pull_request`, …) or the `safeoutputs` CLI; each call queues an operation and returns an `output_id`. A separate job with the write permission applies them after validation | Structural: no write token where untrusted text is read | Every write type needs a schema and an applier | [safe outputs](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/safe-outputs.md) |
| Per-type caps | Default `max` per run: create-issue 1, create-pull-request 1, add-comment 1, add-labels 5 calls (`max-labels` 10, `create-if-missing: false`), close-pull-request 10, noop 2 | Bounds blast radius even when the agent is steered | None | same |
| Text sanitisation on outputs | Issue body 20 to 65 000 characters, oversized rejected not truncated; `@mentions` neutralised except the parent item's author; HTML comments stripped from comments; `max-links` 50; closing keywords normalised | Stops outputs that page people, hide text or close issues | None | same (part of the page read via summary) |
| **Integrity filtering** (author trust) | `tools.github.min-integrity`: `merged` > `approved` (OWNER, MEMBER, COLLABORATOR, non-fork PRs, trusted bots, `trusted-users`) > `unapproved` (CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR) > `none` > `blocked`. **Default `approved` on public repositories.** Items below the threshold are removed by the MCP gateway *before the model sees them*, each logged as `DIFC_FILTERED`. `approval-labels` and `trusted-users` raise an item; `refusal-labels` lower it | Removes the input rather than detecting it | Maintainers must vouch for outsider text | [integrity](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/integrity.md) |
| **Threat detection** | A separate job scans the buffered outputs, the patch and the prompt, by default with an LLM returning `{prompt_injection, secret_leak, malicious_patch, reasons}`, plus optional scanners (trufflehog, semgrep). Warn mode (default) applies reviewable outputs with a `[!CAUTION]` block and a label, and refuses non-reviewable ones (merge, close); strict mode applies nothing. Detector failure follows the mode | A filter, but on the *output*, where the attacker must also smuggle the payload past a reviewer | One extra model call per run | [threat detection](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/threat-detection.md) |
| **Protected files** | On by default for PR-creating outputs: dependency manifests, `AGENTS.md`/`CLAUDE.md`/`.claude/`/`.codex/`, `.github/`, `.agents/`, `CODEOWNERS`. `request_review` (default) opens the PR with a `REQUEST_CHANGES` review; `blocked`; `fallback-to-issue`; `allowed`. "A warning marker or label alone is not a platform approval gate" | Static and deterministic | Legitimate edits to those paths need a human | same page, "Supply Chain Protection" |
| **Staged mode** | Writes are replaced by a preview in the step summary; custom appliers get `GH_AW_SAFE_OUTPUTS_STAGED=true` and must honour it | A shadow mode for the write path | None | [staged mode](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/staged-mode.md) |
| **Capability separation** (CaMeL) | Control flow is extracted from the trusted query only; untrusted data "can never impact the program flow"; capabilities on values enforce policy at each tool call. 77% of AgentDojo tasks with provable security against 84% undefended | Strongest guarantee in the literature | Needs a planner that writes a program; a coding agent's task *is* the untrusted text, so control flow cannot be extracted from a trusted query alone | [CaMeL](https://arxiv.org/abs/2503.18813), [code](https://github.com/google-research/camel-prompt-injection) |
| **Rule of Two** (Meta) | One session holds at most two of: untrusted input, sensitive access, the power to change state | A design check, not a mechanism | — | [Willison](https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/) |
| Provenance tagging / spotlighting | Untrusted spans are fenced or encoded and the prompt tells the model to treat them as data | Weak alone: a prompt instruction is a filter | None | The factory already fences issue snapshots ([harness reference](../../../website/content/docs/reference/harness.md)) |
| Inline tool-call reviewer (Goose adversary mode) | A second model sees each tool call before it runs | Filter; Goose's fails open | One call per tool call | [Goose](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/security/adversary-mode.md) |
| Gateway detectors | Prompt Guard 2 behind agentgateway `promptGuard` webhook and ExtMCP on `tools/call` responses | Filter, cheap, content-free audit log | One CPU service | [Model Armor research](2026-11-04-model-armor-oss-equivalents-research.md#recommended-shape-for-this-platform) |

## What transfers to the factory, and what does not

| gh-aw mechanism | Fits as is | Needs adapting | Reason |
|---|---|---|---|
| No write token in the agent job | ✓ for issues, comments, labels | Code | gh-aw buffers a patch (`aw.patch`) and the applier pushes it; the factory's implementer pushes from the sandbox today, so the push itself must become an output |
| Per-type `max` and schemas | ✓ | — | Same shape as the room tools' verdict, which the broker already posts |
| `min-integrity: approved` by default on public repositories | ✓ | The levels map onto GitHub `author_association` and the factory's maintainer check | Strangers' issues are exactly v4.0's adopter case |
| Threat detection by an LLM | Partly | Deterministic scanners first; an LLM check only where drills show they miss | A same-model judge shares the run's blind spots, and a different family on public work has no route: [ADR-0058](../../../website/content/docs/decisions/0058-reviewer-on-another-model.md) kept the reviewer on the implementer's model for data class and cost |
| Warn mode first | ✓ | — | Same as the merge gate's shadow promotion |
| Protected files `request_review` | Partly | The merge gate, not a review, is the factory's enforcement point | The factory already routes by class; a protected path can force the human class |
| Staged mode | ✓ | — | Maps onto shadow mode |
| CaMeL | ✗ as a runtime | Its principle applies to the *writer*: the applier's control flow comes from the schema and config, never from the text | A coding task has no trusted query separate from the untrusted issue |

## Residuals no layer closes

- A plausible maintainer-sounding instruction in an *approved* author's text: integrity filtering
  trusts it by design.
- Injection split across several tool results, or encoded (Base64, homoglyphs), passes single-turn
  detectors ([Model Armor research](2026-11-04-model-armor-oss-equivalents-research.md#recommended-shape-for-this-platform)).
- Malicious code that looks like the requested change: only review and the merge gate's classes
  bound it.
- False positives on YAML, PromQL and stack traces are the likelier first drill finding.

## Sources

- gh-aw v1.0.0: [release](https://github.com/github/gh-aw/releases/tag/v1.0.0),
  [safe outputs](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/safe-outputs.md),
  [threat detection and protected files](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/threat-detection.md),
  [integrity](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/integrity.md),
  [staged mode](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/staged-mode.md)
- [CaMeL, "Defeating Prompt Injections by Design"](https://arxiv.org/abs/2503.18813) (v2, 2025-06-24)
- [Willison on adaptive attacks and the Rule of Two](https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/)
- [Goose adversary mode](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/security/adversary-mode.md)
