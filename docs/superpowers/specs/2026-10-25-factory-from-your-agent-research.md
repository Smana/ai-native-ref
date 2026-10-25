# Research: the factory from a developer's coding agent

**Date:** 2026-10-25 · **For:** [the design](2026-10-25-factory-from-your-agent-design.md) · Vendor
docs fetched 2026-10-25. **Confidence:** §1 medium-high (Amp, Factory, Ona and Warp not searched); §2
medium, the per-client cells rest mostly on two aggregators, and a cell marked **(u)** was not
confirmed at a fetched source. The only signal a server can trust is the capabilities a client
declares at `initialize`.

## 1. How the best tools hand work from a local session to a remote agent

**Conclusion.** One keystroke prefix or flag inside the local session starts a remote run; the branch
is the shared state; a URL or id comes back at once; one command brings the result back. Steering and
approvals stay on the vendor's web or mobile surface: **no verified tool proxies a remote approval
into the local session.**

| Tool | Start | Follow | Steer / approve | Bring back |
|---|---|---|---|---|
| Claude Code ([cloud](https://code.claude.com/docs/en/claude-code-on-the-web)) | `claude --cloud "task"` (`--remote` deprecated): clones the GitHub remote at the current branch, or uploads a bundle of tracked files | claude.ai/code URL; `/tasks` | `claude -p "msg" --cloud <id>` queues a message; permission mode on the web | `claude --teleport [id]`, `/teleport`: branch and the **whole conversation**, needs a clean tree |
| Codex ([cloud](https://developers.openai.com/codex/cloud)) | `codex cloud`, `codex cloud exec` | `codex cloud list --json` (`id, url, status, attempt_total`) | web; `codex queue` for sessions (cloud **unverified**) | `codex apply`: the diff, non-zero on conflict |
| Copilot CLI ([delegate](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/delegate-tasks-to-cca)) | `/delegate <task>` or the `&` prefix: asks to commit unstaged work as a checkpoint on a new branch, opens a draft PR | PR and session link; `gh agent-task list` | PR review comments | `gh pr checkout` |
| Cursor ([CLI](https://cursor.com/docs/cli/using)) | `&` prefix moves the live conversation (Jan 2026); Plan → Build in Cloud | cursor.com/agents, iOS | follow-ups, approval cards | branch or PR; the Agents Window moves cloud → local |
| Jules ([CLI](https://jules.google/docs/cli/reference/)) | `jules remote new --repo . --session "…" [--parallel N]` | `jules remote list` | web | `jules remote pull --session <id> --apply` |
| Devin ([handoff](https://docs.devin.ai/work-with-devin/devin-handoff)) | `/handoff [task]`; for other agents a skill over a script sending the branch, `git diff HEAD` (≤100 KB) and a brief | URL; `poll` exits when done **or waiting on you** | web | PR |
| OpenCode | No cloud handoff. `opencode serve`, `attach`, `run --attach`, `export`/`import` exist | — | — | `opencode pr <n>` |

| # | Pattern that recurs | Evidence |
|---|---|---|
| 1 | One prefix or command starts remote work from inside the session | `&` in Copilot CLI and Cursor; `/delegate`; `--cloud`; `/handoff` |
| 2 | The branch is the shared state; unpushed work is the first trap | Copilot's checkpoint commit; Claude's "branch is not on GitHub" |
| 3 | A brief and a diff travel, not the transcript | Devin `--context` + `git diff HEAD`; [claude-code#95073](https://github.com/anthropics/claude-code/issues/95073) |
| 4 | A URL or id comes back at once, then list or poll, `--json` for agents | Claude, `codex cloud list --json`, Devin `poll`, `gh agent-task list` |
| 5 | Bringing back is one command that checks its preconditions | `--teleport`, `codex apply`, `jules remote pull --apply` |
| 6 | Approvals live on web or mobile; a run waiting on one can expire | Claude cloud sessions; Cursor approval cards |
| 7 | When an agent calls the dispatch tool, a human confirms first | [Jules skill](https://github.com/openclaw/skills/blob/main/skills/ajstafford/jules-cli/SKILL.md) confirms before `new` and `pull --apply` |
| 8 | Known pains: one-way moves, copies that diverge after a teleport, no "the remote branch moved" signal, worktree sprawl | [vscode#266476](https://github.com/microsoft/vscode/issues/266476), [HN 49258045](https://news.ycombinator.com/item?id=49258045) |

## 2. What an MCP integration can rely on, per client

Sources: [canimcp.dev](https://canimcp.dev/) (updated 2026-09-24, spec 2026-07-28), the
[MCP extension matrix](https://modelcontextprotocol.io/extensions/client-matrix), the
[MCP Apps announcement](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps) (2026-01-26),
[OpenCode V2 MCP](https://opencode.ai/v2/docs/mcp-servers/) and [skills](https://opencode.ai/v2/docs/skills/),
[Codex MCP](https://developers.openai.com/codex/mcp), the
[Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference).

| Client | MCP Apps | Prompts → commands | Forms / URL forms | Tasks | Skills read from | Bundle format |
|---|---|---|---|---|---|---|
| Claude Code | no (u) | `/mcp__<server>__<prompt>` (u) | ? / yes | no client | `.claude/skills`, `~/.claude/skills` | plugins, marketplaces |
| OpenCode | no (u) | `/<server>:<prompt>` | yes / yes (a link) | no client | `.opencode/skills`, `.agents/skills`, `.claude/skills`, `~/.agents/skills` | JS plugins, no MCP + skill manifest |
| Codex CLI | ChatGPT only | ? | ? | no client | `.agents/skills` (u) | `.codex-plugin/plugin.json` |
| Copilot (VS Code) | yes | yes | yes (1.102) / yes (1.107) | no client | `.github/skills` | extensions, Agent Plugins (u) |
| Copilot CLI | ? | ? | ? | no client | (u) | plugins; reads Agent Plugins 1.x |
| Cursor | yes | yes | yes / ? | no client | `.cursor/skills`, `.claude/skills` | `.cursor-plugin/` |
| Gemini CLI | no (u) | yes | ? | no client | `~/.gemini/skills` | `gemini-extension.json` |
| Claude Desktop, Goose, ChatGPT | yes | yes | Goose: yes / ? | no client | — | MCPB (u), recipes |

Takeaways:

1. **Tools returning Markdown text work everywhere.** Keep the text equivalent to the structured
   result: terminal agents mostly hand results to the model, which relays them.
2. **MCP Apps render in Claude Desktop, ChatGPT, VS Code, Cursor and Goose, in no terminal agent.** An
   upgrade later, on the same tools, with the text as the fallback.
3. **Tasks have no verified client**, and the 2026-07-28 revision moved them to an extension and
   deprecated logging. Follow by polling.
4. **Forms are uneven; read the declared capability.** OpenCode documents both modes; Claude Code's form
   mode is unconfirmed.
5. **The skill is the portable layer; bundles are not.** [Agent Plugins](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
   1.x standardises MCP servers and skills, "not portable agents, hooks, commands, rules"; subagent
   formats differ per client.
