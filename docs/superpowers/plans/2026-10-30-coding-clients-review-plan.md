# The Coding Clients page, a complete review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `website/content/docs/platform/ai-platform/coding-clients.md` as the current
reference for connecting a coding client to the platform: both integrations (the `ai-gateway` for
models, the factory for hand-offs), both clouds, every client the platform names, each config in
the client's current syntax, each claim verified.

**Architecture:** Five tasks, one pull request, independent of the Maku release. Task 1 inventories
what the manifests and the docs say today and writes the facts file the page is built from. Task 2
reads each client's current configuration docs. Task 3 writes the page. Task 4 verifies: links,
the site build, every snippet either run or marked schema-checked. Task 5 opens the PR.

**Tech Stack:** Hugo (Hextra), `task check` (the link check, the site build, the doc-path check),
context7 for the clients' docs, `curl` against the gateways when a cluster is up.

**Spec:** [the harness roles design](../specs/2026-10-30-harness-roles-design.md), HR14 and "The
Coding Clients page" (the section table is the page's outline and each row's "verified against"
column is this plan's checklist).

## Global Constraints

- **Worktree:** `/home/smana/Sources/ai-native-ref-coding-clients`, branch
  `docs/coding-clients-review`, from a freshly fetched `origin/main`; `mise trust mise.toml` once.
- **`task check` is the evidence**, through `~/.cache/v3/check.sh <worktree>`; `pre-commit run --all-files` before pushing.
- **The site links outside itself by absolute URL only** (`https://cnref.ogenki.io/…` for host pages); the link check fetches each one.
- **No secret in the page.** Keys are read from Secrets Manager or the cluster into an environment variable; the page shows the command, never a value.
- **Every snippet is labelled**: "run on <cloud> on <date>" or "schema-checked against <docs URL>, not run". No snippet is left unlabelled.
- **Naming.** "Agent Factory" is the product; Maku is the controller; `maku` is the CLI (named `roomctl` before v0.30.0).
- **Commits** conventional, in English, no trailers; the PR description in English.

---

### Task 1: The facts file

**Files:**
- Create: `/tmp/claude-1000/…/scratchpad/coding-clients-facts.md` (the session's scratchpad; not committed)

- [ ] **Step 1: The gateways and endpoints**

Read and record, with file and line:

- `website/content/docs/platform/ai-platform/gateways.md`: the `ai-gateway` request shape, the `MoM` path, the `tier-frontier` section (gcp-0 serves `tier-*` through Z.ai with `llm-platform` suspended), the shadow budgets (ADR-0050).
- `website/content/docs/platform/ai-platform/routing.md` "What is real today", "one price table": the `tier-*` aliases and `agent-default`, which a human may name on `ai-gateway`.
- `clusters/aws-0-ai-gateway/*.yaml`, `clusters/gcp-0-ai-gateway/*.yaml`, `infrastructure/aws-0/envoy-ai-gateway/*`, `infrastructure/gcp-0/*` (and the host's `security/…` where the API keys live): the hostnames per cloud (`llm.priv.aws.ogenki.io`, `llm.priv.gcp.ogenki.io`), the API-key source per cloud (the Secrets Manager entry `platform-llm-api-keys` on aws-0; the in-cluster Secret `ai-gateway-api-keys` in `envoy-ai-gateway-system` on gcp-0), the ExternalSecret names and namespaces the troubleshooting section must name.
- `clusters/aws-0-llm-platform/`, `clusters/gcp-0-llm-platform/`: which `xplane-*` InferenceService claims exist per cloud and whether the umbrella is suspended (the opt-in gates).
- `website/content/docs/platform/ai-platform/agents/use/user-guide.md` "Hand off from your coding agent" and "From a terminal: `maku`": the six clients, `maku setup <client>`, `--project`, `--print`, the Gemini trusted-folder caveat, the tool and prompt names, `maku doctor`.
- `website/content/docs/platform/ai-platform/status.md` row 186: "Claude Code on the self-hosted models, through a protocol relay" (the roadmap row).

- [ ] **Step 2: What the current page claims that is now false or missing**

List each claim of the current page against the facts: the OpenCode TOML (`~/.opencode/config.toml`, `[providers.local]`) against OpenCode's current `opencode.json` `provider` block; "Claude Code (not implemented)" against the roadmap row and `maku setup claude`; aws-0-only endpoints against gcp-0; the models table against each cloud's claims; the troubleshooting ExternalSecret name against both clouds; `lastVerified: 2026-08-27`.

### Task 2: The clients' current syntax

- [ ] **Step 1: Read each client's docs through context7**

For each, `mcp__context7__resolve-library-id` then `mcp__context7__query-docs`, and record the
exact config shape with the docs URL and version:

| Client | What to read | Expected shape (verify, do not assume) |
|---|---|---|
| OpenCode | provider configuration, `opencode.json`, custom OpenAI-compatible providers, models | `"provider": {"<name>": {"npm": "@ai-sdk/openai-compatible", "name": "…", "options": {"baseURL": "…", "apiKey": "{env:OPENAI_API_KEY}"}, "models": {"<id>": {"name": "…"}}}}` and `"model": "<name>/<id>"` |
| Continue | `config.yaml` models, roles, `apiBase`, autocomplete templates | as the current page, re-checked against the schema |
| Codex CLI | `config.toml` `model_providers`, `base_url`, `env_key`, `wire_api` | `[model_providers.<name>] name = "…" base_url = "https://…/v1" env_key = "OPENAI_API_KEY"` and `model_provider = "<name>"` |
| Cursor | custom OpenAI base URL in settings | the settings path and its limits (which features honour the base URL) |
| Gemini CLI | OpenAI-compatible endpoints | likely unsupported for models; the factory side only |
| Copilot CLI | custom models | likely unsupported for models; the factory side only |
| Claude Code | `ANTHROPIC_BASE_URL` and OpenAI-compatible gateways | the Anthropic API only: the roadmap row stands unless Envoy AI Gateway's Anthropic-compatible listener is deployed here (check the manifests; it is not expected) |

- [ ] **Step 2: Record what each client supports**

A table clients × (models through `ai-gateway`: yes/no/how; the factory through `maku setup`:
yes) for the page's first section.

### Task 3: Write the page

**Files:**
- Modify: `website/content/docs/platform/ai-platform/coding-clients.md`

- [ ] **Step 1: The outline**

Front matter: `title: Coding Clients`, `weight: 10`, `description: Connecting a coding client to the platform: the ai-gateway for models and the factory for hand-offs, on aws-0 and gcp-0, with each client's current configuration and the failure modes their errors mean.`, `lastVerified: <today>`.

Sections, in this order, each from the facts file:

1. **Two integrations, one table.** Clients × (models, hand-offs), with a line on each integration and links to `gateways.md` and the user guide's hand-off section.
2. **Endpoints per cloud.** `llm.priv.aws.ogenki.io` and `llm.priv.gcp.ogenki.io`; which models each serves today; the opt-in gates for the GPU models.
3. **Authentication.** Per cloud: how to read a key into `OPENAI_API_KEY`; how a new identity is added; the gateway's header stripping and the shadow budgets in one sentence each.
4. **Models exposed.** The `xplane-*` table (per cloud) and the `tier-*` aliases.
5. **OpenCode.** `opencode.json` snippet in the verified shape; `maku setup opencode`.
6. **Claude Code.** The roadmap row for models, stated as such; `maku setup claude` for the factory.
7. **Codex CLI.** `config.toml` snippet; `maku setup codex`.
8. **Cursor, Gemini CLI, Copilot CLI.** One paragraph each: models where supported, the factory through `maku setup <client>`, Gemini's trusted-folder caveat.
9. **VS Code + Continue.** The chat and FIM profiles, re-checked.
10. **OpenWebUI.** Per cloud.
11. **Verifying the connection.** The smoke tests per cloud; `maku doctor` for the factory side.
12. **Troubleshooting.** 401, 404, 403, slow FIM, "the factory tools are missing", with the per-cloud ExternalSecret names.

Every snippet carries a one-line label: `run on gcp-0 on <date>` or
`schema-checked against <docs URL>, not run`.

- [ ] **Step 2: Write it**

Write the page. Keep the site's register: short sentences, tables over prose, no marketing.
Cross-link the user guide, the gateways page, the routing page and the status page with `relref`;
the host's pages by absolute URL.

### Task 4: Verify

- [ ] **Step 1: Links and the build**

Run: `~/.cache/v3/check.sh /home/smana/Sources/ai-native-ref-coding-clients`
Expected: `exit=0` (the relative link check, the external link job on push, the site build).

- [ ] **Step 2: Run what can be run**

If a cluster is up (the aws-0 session), run the smoke tests of section 11 against it and the
OpenCode and Codex snippets with a scratch config; replace their labels with "run on <cloud> on
<date>". If none is up, the labels stay "schema-checked".

- [ ] **Step 3: Commit**

```bash
git add website/content/docs/platform/ai-platform/coding-clients.md
git commit -m "docs(ai-platform): the Coding Clients page, rewritten for both integrations, both clouds and the clients' current syntax"
```

### Task 5: PR 4

- [ ] **Step 1: pre-commit, rebase, push, PR**

```bash
pre-commit run --all-files && git fetch origin && git rebase origin/main && git push -u origin docs/coding-clients-review
gh pr create --title "docs(ai-platform): the Coding Clients page, reviewed and rewritten" --body-file - <<'EOF'
A complete review of the Coding Clients page (harness roles design HR14).

- Both integrations: the ai-gateway for models, the factory for hand-offs (`maku setup <client>`, six clients).
- Both clouds, with each one's endpoint, key source and models.
- Each client's configuration in its current syntax, read from the client's docs: OpenCode (`opencode.json` provider block), Codex CLI (`model_providers`), Continue, Cursor, Gemini CLI, Copilot CLI, Claude Code (the roadmap row stands for models).
- Every snippet labelled "run on <cloud> on <date>" or "schema-checked, not run".
- What was false or missing before: <the Task 1 Step 2 list>.

Evidence: `task check` exit 0; the external link job on this PR.
EOF
```

## Self-review

- **Spec coverage.** Every row of the design's "The Coding Clients page" table is a section in
  Task 3 and a check in Task 1 or Task 2.
- **Placeholders.** The config shapes in Task 2 are expectations to verify, named as such; the
  page is written from the facts file, not from memory.
