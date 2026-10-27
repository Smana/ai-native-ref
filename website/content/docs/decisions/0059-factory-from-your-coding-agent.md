---
title: The factory is started, followed and brought back from the developer's coding agent
linkTitle: 0059 · The factory from your coding agent
weight: 590
description: Accepted. The broker renders the views once, as the MCP tools' text; a confirmation form that only the developer answers can start the work with their own label, per repository and off by default; approvals stay on the room page; a checkout lands in a new worktree; roomctl setup installs it per client. /mcp is on in this deployment with the start held off. The accepted risk is a client that auto-accepts forms.
lastVerified: 2026-10-27
---

**Status**: Accepted
**Date**: 2026-10-25
**Deciders**: Smana (Platform Owner)
**Related**: [design, feature 13](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-25-factory-from-your-agent-design.md), [roadmap D7](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-19-v3-roadmap-design.md#owner-decisions-2026-10-25), [ADR-0049]({{< relref "/docs/decisions/0049-room-client-and-human-auth.md" >}}), [ADR-0056]({{< relref "/docs/decisions/0056-local-first-factory-ux.md" >}})

---

## Context

[ADR-0056]({{< relref "/docs/decisions/0056-local-first-factory-ux.md" >}}) D2 deferred a local MCP
server. `roomctl mcp` has shipped since v0.17.0, but `/mcp` was off in this deployment. Developers
want to start and follow work from whichever coding agent they use, and that agent can already label
an issue with the developer's own `gh`, so the label rule was "advice, not a control". What was
missing is one readable view of a room everywhere, a way to start that the model cannot answer for
itself, and a way to bring the branch back.

---

## Decision Drivers

- Portable across clients: text works in every one, richer surfaces are an upgrade
- The human, not the model, starts work
- Approvals stay where the command, the diff and the deadline are shown
- Views that untrusted text cannot break: no link, heading, table or terminal escape from an agent's words

---

## Considered Options

| Question | Options | Chosen |
|---|---|---|
| Who renders the views | A the broker, B `roomctl`, C the skill | A (FA2) |
| How work starts | A form field, a click in the rooms web, the label only | A form field (FA4) |
| Where approvals happen | The room page, a form in the session | The room page (FA7) |
| Bringing the result back | A new worktree, in place, a link only | A new worktree (FA8) |
| Install | `roomctl setup`, per-client plugins, both | `roomctl setup` (FA9) |

- **Who renders.** (A) keeps the escaping next to the data it escapes, and sponsored callers on
  `/mcp` get the same views. (B) leaves the broker a data API. (C) leaves the model to format and
  escape untrusted text, which breaks local-first D3.
- **How work starts.** A click in the rooms web sends the developer to a browser; the label alone is
  the status quo.
- **Approvals.** A form shows one line, not the command, the diff or the deadline, and an approval
  lets a sandboxed agent act.
- **Bringing back.** In place needs a clean tree and moves the session's branch; a link only leaves
  the last step to the developer.
- **Install.** Plugins mean a manifest per client per release, for a bundle standard that covers only
  MCP servers and skills.

---

## Decision Outcome

Decided by the owner on 2026-10-25, with the design's numbering.

| # | Decision |
|---|---|
| FA2 | One view package renders. The broker's views come back as the tools' `content` text, with the JSON as `structuredContent`; `roomctl` renders the same views for a terminal |
| FA4 | The start is a field of `issue_file`'s form, defaults to no, and is **a form field, never a tool argument**. On yes, `roomctl` files the issue and labels it `factory/ready` with the developer's `gh`. Amends [ADR-0056]({{< relref "/docs/decisions/0056-local-first-factory-ux.md" >}}) D1 |
| FA5 | Per repository, off by default: the broker lists the repositories in `human.mcp.sessionStart`, and `issue_draft` says `canStart` only for a listed one where the caller can write |
| FA7 | Approvals stay on the room page ([ADR-0049]({{< relref "/docs/decisions/0049-room-client-and-human-auth.md" >}})); the card links to them |
| FA8 | `room_checkout` and `roomctl checkout` create a new worktree beside the repository, pinned to the checked commit, and ask first when the branch touches agent or editor config, hooks, symlinks or non-ASCII paths |
| FA9 | `roomctl setup <client>` registers the MCP server and writes the skill where the client reads it |

**In this deployment:** `/mcp` is on (`human.mcp.enabled`) with `sessionStart` empty, so no
repository offers the start. The owner decided this on 2026-10-25. A gcp-0 session lists one
repository to prove it, and removes it after (`docs/runbooks/agent-factory/19-factory-from-your-agent.md`).

---

## Consequences

### Positive

- One view of a room, the same in every client's transcript and in a plain terminal
- Starting work no longer needs a trip to GitHub, and the answer comes from the developer, not the model

### Negative

- **The accepted risk**, quoted from the design: "a client that auto-accepts forms (some headless
  modes) lets the agent start work". That is not new, since the agent can already label with the
  developer's `gh`; the factory's maintainer check, per-person caps and dollar caps still bound it.
- A checked-out agent branch can carry config that runs when a tool opens it; the confirmation form
  is the control, and a client with no forms is refused

### Neutral

- MCP Apps (interactive panels in the clients that render them) can come later on the same tools,
  with today's text as the fallback
