---
title: Agent runs hold a read-only GitHub token and write only through outputs the factory validates and applies
linkTitle: 0061 · Safe outputs
weight: 610
description: Proposed. A run that reads strangers' text no longer holds a write token. It requests a push, a pull request, a comment, labels or an issue, and the factory checks each one, protected paths included, before writing it under its own identity. Keeping the write token behind classifiers, and checking protected paths only at merge, were rejected.
lastVerified: 2026-11-07
---

**Status**: Proposed
**Date**: 2026-11-07
**Deciders**: Smana (Platform Owner)
**Related**: [design, decisions UH1 to UH14](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-11-07-untrusted-input-hardening-design.md#decisions), [ADR-0043]({{< relref "/docs/decisions/0043-octo-sts-for-agent-github-tokens.md" >}}), [ADR-0042]({{< relref "/docs/decisions/0042-agent-router-identity-gateway.md" >}})

---

## Context

An agent run reads text that anyone can write: an issue body, a comment, a log line, a tool result.
The same run holds a GitHub token. An implementer's token can push and edit pull requests
([ADR-0043]({{< relref "/docs/decisions/0043-octo-sts-for-agent-github-tokens.md" >}})), and the
approval classifier that watches the run's commands cannot see a script or a `curl` that uses the
token.

GitHub cannot scope a token to one branch. Published injection filters fail against adaptive
attacks more than nine times in ten. A pushed branch also runs CI from that branch's own scripts,
so a check at merge time comes after the damage.

---

## Decision Drivers

- The run that reads untrusted text must not be able to change state on its own
- Every write must pass one validator, the way the factory's own comments and issues already do
- A legitimate change to CI or agent instructions must stay possible, with a maintainer's approval
- Filters may add evidence; they must not be the boundary

---

## Considered Options

| Question | Options | Chosen |
|---|---|---|
| Who holds the write token | The run, behind classifiers; the factory | The factory |
| How the code reaches GitHub | The run pushes; the run hands over a bundle the factory pushes | A bundle |
| Where protected paths are enforced | At merge; at push | At push |
| How a run asks | A file at the end of the run; tools on its existing MCP server | Tools |

- **The run keeps its token, with classifiers in front.** Classifiers are filters, and the
  approval classifier documents what it cannot see. Rejected as the boundary; classifiers stay as
  one layer of the threat check.
- **Protected paths checked at merge only.** The branch's CI has run by then, with that branch's
  scripts. Rejected.
- **Outputs written to a file at the end of the run.** A run pushes several times and needs each
  answer as it works. Rejected.

---

## Decision Outcome

Sandbox roles get read-only GitHub tokens. A run asks for a push (a git bundle for its own
branch), a pull request, a comment, labels from an allowlist, or a follow-up issue, through tools on
its existing MCP server. Each request is recorded in the room log.

The factory checks each request in order: schema and caps, text sanitisation, secrets and a
planted canary, protected paths, then an injection classifier. It writes the output under a
`publisher` identity that the sandbox never sees. A push that touches a protected path waits for a
maintainer's approval of that exact bundle.

### Consequences

**Good**:
- An injected run can only ask; every write it causes is validated and traceable to a request
- The pull request footer is written by the factory and can no longer be bypassed
- The same check serves the knowledge base and multi-repository coordination

**Bad**:
- Each output type needs a schema and an applier
- A push costs a round trip to the factory, up to about 10 seconds
- A run can still read HTML pages on `github.com`, which `git` needs

---

## References

- [gh-aw safe outputs](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/safe-outputs.md)
- [gh-aw threat detection and protected files](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/threat-detection.md)
- [Willison on adaptive attacks and the Rule of Two](https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/)
