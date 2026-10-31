---
title: Commands
weight: 15
description: "Every maku command, the setup options, what each coding agent supports, the room states, how a run ends, and starting a run by hand."
---

Look-up tables for the Agent Factory's commands. The [user guide]({{< relref "/docs/use/guide/_index.md" >}})
shows how to use them; the [cheat sheet]({{< relref "/docs/use/guide/cheat-sheet.md" >}}) lists the labels
and comment commands.

- [The `maku` CLI](#maku)
- [`maku setup`](#setup)
- [The tools a coding agent gets](#tools)
- [What each coding agent supports](#clients)
- [Room states](#room-states)
- [How a run ends](#run-ends)
- [Start a run by hand](#run-by-hand)

## The `maku` CLI {#maku}

Download `maku-<os>-<arch>` from a [Maku release](https://github.com/Smana/maku/releases) and check it
against `maku.sha256`, or build it with `go build ./cmd/maku`.

```bash
maku configure --url … --issuer … --client-id … --project-id …  # the room list's "CLI setup" prints it
maku login                                    # device flow: open the URL, enter the code
maku rooms --mine                             # issues you filed or labelled, PRs you authored or review
maku rooms --needs-me                         # an approval you could decide; --repo owner/name filters
maku status <room> --json                     # phase, run, budget, PR, what needs you, the agents' notes
maku changes <room>                           # what changed since your last call (first call: 24 h)
maku checkout <room>                          # the room's branch in a new worktree beside the repository
maku setup <client>                           # the MCP server and the skill, for a coding agent
maku doctor                                   # checks the set-up; every check should read ok
maku watch <room>                             # the last 50 events, then live
maku post <room> --queue "address L42"        # for the next run's brief; without --queue, a chat
maku fork <room> --at <seq> --role implementer --egress pypi --note "try uv"
maku token                                    # your access token, for scripts
```

`maku` reads, chats, queues and forks. It never drives a run, interrupts it or approves: those stay in
the browser, because a local agent can type into a terminal
([ADR-0049]({{< relref "/docs/decisions/0049-room-client-and-human-auth.md" >}})). A task waiting for
your merge is not listed under `--needs-me` ([maku#51](https://github.com/Smana/maku/issues/51)).

## `maku setup` {#setup}

`maku setup <client>` registers `maku mcp` as the `factory` MCP server and writes the `factory-handoff`
skill where that client reads skills. The clients: `claude`, `opencode`, `codex`, `gemini`, `cursor`,
`copilot`.

| Option | Effect |
|---|---|
| (none) | User-level set-up |
| `--project` | Writes both into the repository instead, for a team that commits them |
| `--print` | Shows every command and file, changes nothing |

It is idempotent. It runs the client's own `mcp add` when that is on the `PATH`, and otherwise prints
the snippet to paste: it never edits a config file itself. Gemini CLI starts a local server only in a
folder you trust.

## The tools a coding agent gets {#tools}

| Tool or prompt | What it does |
|---|---|
| `handoff` | Drafts an issue, one defect per issue; a form shows it to you, files it and offers to start it |
| `status [room or #issue]` | The room card; without an argument, your most recently updated room |
| `inbox` | The rooms that need you first, then your other open rooms |
| `room_wait` | Follows a room and returns when it needs you, opens a pull request or ends |
| `room_checkout` | The room's branch in a new git worktree, at the commit it checked |

The other tools are `rooms_list`, `room_summary`, `room_changes`, `issue_draft` and `issue_file`.

Starting a task is a form field, never a tool argument: your agent can file an issue but cannot answer
the form. It is offered only on repositories the platform lists and you can write to. A checkout that
changes agent or editor config, hooks, symlinks or non-ASCII paths asks first. Everything an agent wrote
comes back in code spans, as data. The design: [ADR-0059]({{< relref "/docs/decisions/0059-factory-from-your-coding-agent.md" >}}).

## What each coding agent supports {#clients}

Text views work everywhere. The rest depends on what each client declares. `unconfirmed` means no
source says. Which clients are tested end to end: the [status page]({{< relref "/docs/status.md" >}}).

| Client | Forms | Slash commands | Skill directory |
|---|---|---|---|
| Claude Code | unconfirmed | `/mcp__factory__<prompt>` (unconfirmed) | `~/.claude/skills` |
| OpenCode | yes | `/factory:<prompt>` | `~/.agents/skills` |
| Codex CLI | unconfirmed | unconfirmed | `~/.agents/skills` |
| Gemini CLI | unconfirmed | yes | `~/.gemini/skills` |
| Copilot CLI | unconfirmed | unconfirmed | `~/.copilot/skills` |
| Cursor | yes | yes | `~/.cursor/skills` |

Without forms the draft is shown for you to file with `gh`, nothing starts, and a checkout that needs
to confirm refuses. Codex CLI may cut a call at 60 s; the skill then calls `room_wait` again.

## Room states {#room-states}

| State | Meaning |
|---|---|
| `needs you` | An item names you: an approval, a hand-off |
| `waiting for a human` | The task waits for a maintainer |
| `running` | A run is working |
| `queued` | A run is waiting for a free sandbox |
| `done`, `failed`, `stopped` | The task ended |

## How a run ends {#run-ends}

| Reason | Meaning | Resumed? |
|---|---|---|
| `Disrupted` | Its node was reclaimed or drained: a spot reclaim, an eviction, an upgrade | Yes |
| `PodLost` | Its pod was deleted, or vanished with its node, before a final state was read | Yes |
| `PodFailed` | The run failed on its own, or hit its deadline | No: the task waits for you |

The factory resumes at most twice per task, within its budget; `/factory retry` does not give the
resumes back. A lost review run starts again without using a review round. On the way out, within
15 s, an implementer commits its changes with the trailer `Agent-Checkpoint: disruption` and pushes
them, so the resumed run starts from that commit. Limits: [Reference › Harness]({{< relref "/docs/reference/harness.md#caps" >}}).

## Start a run by hand {#run-by-hand}

With `agents-member`, after `maku login`:

```bash
task agent:run -- --role implementer --class public --task-url <issue>
task agent:run -- --role implementer --class public --task-url <issue> --branch agent/<task>   # continue a stopped task
```

The factory creates the run under your sign-in identity: the run is yours.
`internal` work and `triager` runs need `agents-admin`. The run API: [Reference › Harness]({{< relref "/docs/reference/harness.md#run-api" >}}).
