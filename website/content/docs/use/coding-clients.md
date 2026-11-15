---
title: Coding Clients
aliases:
  - /docs/platform/ai-platform/coding-clients/
weight: 30
diataxis: how-to
description: "Connecting a coding client to the platform: the ai-gateway for models and Maku for hand-offs, on AWS and GCP, with each client's configuration and the six tools."
lastVerified: 2026-11-15
---

A coding client can use the platform in two ways, and they are independent:

| Integration | What it gives you | How you connect |
|---|---|---|
| **Models** through the `ai-gateway` | The platform's models in your client's chat, edits and completions | A base URL and an API key in the client's own config |
| **Hand-offs** to Maku | Plan a task, file and start it, follow it, answer its questions, and check out its branch | `maku setup <client>` |

Each model snippet is checked against its client's configuration reference, linked next to it.
[Verifying the connection](#verifying-the-connection) shows the live checks for both integrations.

## Two integrations, one table

| Client | Models through `ai-gateway` | Maku hand-offs |
|---|---|---|
| [OpenCode](#opencode) | Yes: `opencode.json` provider block | `maku setup opencode` |
| [Claude Code](#claude-code) | No: speaks the Anthropic Messages API only | `maku setup claude` |
| [Codex CLI](#codex-cli) | Not yet: speaks only the Responses API | `maku setup codex` |
| [Cursor](#cursor-gemini-cli-and-copilot-cli) | Not verified | `maku setup cursor` |
| [Gemini CLI](#cursor-gemini-cli-and-copilot-cli) | No custom endpoint documented | `maku setup gemini` |
| [Copilot CLI](#cursor-gemini-cli-and-copilot-cli) | Yes: custom OpenAI-compatible provider | `maku setup copilot` |
| [VS Code + Continue](#vs-code-and-continue) | Yes: chat and FIM | not applicable |
| [OpenWebUI](#openwebui) | Yes: in-cluster, on AWS only | not applicable |

- **Models.** The `ai-gateway` is the platform's gateway for humans and coding clients. It speaks
  the OpenAI chat-completions API. See [Gateways]({{< relref "/docs/how-it-works/gateways.md" >}}).
- **Hand-offs.** One command, `maku setup <client>`, configures the rooms URL, signs in, registers
  the `maku` MCP server and `/maku` command (`handoff`, `task`, `inbox`), and runs `maku doctor`.
  See [Hand off from your coding agent]({{< relref "/docs/use/guide/terminal-and-coding-agent.md#hand-off-from-your-coding-agent" >}})
  and Maku's [CLI reference]({{< maku "docs/cli.md" >}}) for tool inputs and outputs.

## Endpoints per cloud {#endpoints-per-cloud}

Both endpoints are Tailscale-fronted (`tag:k8s` ACL, see
[Private Access](https://cnref.ogenki.io/docs/platform/networking/private-access/)) and serve the
OpenAI API under `/v1`. Example (the reference host), one cluster per cloud:

| Cluster | Base URL | Serves |
|---|---|---|
| aws-0 | `https://llm.priv.aws.ogenki.io/v1` | `tier-frontier` always; the four `xplane-*` models and `MoM` once `llm-platform` is resumed |
| gcp-0 | `https://llm.priv.gcp.ogenki.io/v1` | `tier-frontier` (GLM-5.3 through Z.ai, no GPU needed); `xplane-qwen3-8b` and `MoM` once `llm-platform` is resumed |

`llm-platform` is suspended by default on both clouds: until it is resumed, `MoM` has no model to
route to and the `xplane-*` names return an error. The GPU models need all three
[opt-in gates]({{< relref "/docs/how-it-works/serving/_index.md#turning-it-on" >}}).
`tier-frontier` needs none of them.

## Authentication

Clients send `Authorization: Bearer <key>`. An Envoy Gateway `SecurityPolicy`
(`infrastructure/base/envoy-ai-gateway/security-policy.yaml`) compares it with the keys of the
Secret `ai-gateway-api-keys` in `envoy-ai-gateway-system`. Read a key into an environment variable
and never paste it into a config file.

| | AWS | GCP |
|---|---|---|
| Source | AWS Secrets Manager entry `platform-llm-api-keys` (a JSON object keyed by client identity), seeded once outside OpenTofu | Generated in-cluster by External Secrets `Password` generators (`refreshPolicy: CreatedOnce`) |
| Identities today | `openwebui_apikey`, `promptfoo_apikey` | `openwebui`, `promptfoo` |

On AWS:

```bash
export OPENAI_API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id platform-llm-api-keys \
  --query SecretString --output text | jq -r .openwebui_apikey)
```

On GCP:

```bash
export OPENAI_API_KEY=$(kubectl get secret -n envoy-ai-gateway-system ai-gateway-api-keys \
  -o jsonpath='{.data.openwebui}' | base64 -d)
```

To onboard another identity on AWS, add a property to the Secrets Manager JSON and a matching key in
`infrastructure/base/envoy-ai-gateway/api-keys-externalsecret.yaml`. On GCP, add a `Password`
generator in `infrastructure/gcp-0/envoy-ai-gateway/password-generators.yaml` and a `dataFrom` entry in
`api-keys-patch.yaml`.

The gateway strips `Authorization`, `x-ar-agent`, `x-ar-human` and `x-ai-gateway-client-id` before
forwarding. Daily token budgets (5M per key, 10M per human, 20M on frontier spend) are counted in
shadow mode ([ADR-0050]({{< relref "/docs/decisions/0050-token-budgets-envoy-gateway-rate-limit.md" >}})).

## Models exposed

`GET /v1/models` lists what a cloud serves:

| Model ID | Backed by | AWS | GCP | Purpose |
|---|---|---|---|---|
| `tier-frontier` | GLM-5.3 through Z.ai | yes | yes | Frontier model on CPU only; works with `llm-platform` suspended |
| `MoM` | Semantic Router | with `llm-platform` | with `llm-platform` | Classifies the prompt and picks an `xplane-*` model |
| `xplane-qwen-coder` | Qwen2.5-Coder-7B-Instruct | yes | no | Code chat, agentic edits, function calling; 10% canary onto `xplane-qwen-coder-sql-dpo` |
| `xplane-qwen-coder-fim` | Qwen2.5-Coder-1.5B | yes | no | FIM tab completion |
| `xplane-qwen3-8b` | Qwen3-8B | yes | yes | Multilingual, math, longer context (32k) |
| `xplane-llamaguard3-1b` | Llama-Guard-3-1B | yes | no | Reachable only by name |
| `xplane-qwen-coder-sql-dpo`, `xplane-qwen-coder-securecode` | LoRA adapters on `xplane-qwen-coder` | yes | no | Naming one always gets the adapter |

The other `tier-*` aliases (`tier-light`, `tier-standard`) and `agent-default` belong to the model
gateway for runs. How each name is routed and priced:
[Model routing and cost]({{< relref "/docs/how-it-works/routing-and-cost.md" >}}).

## OpenCode {#opencode}

Put the provider block in `~/.config/opencode/opencode.json` or an `opencode.json` at the project root
(<https://opencode.ai/docs/providers/>):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ogenki-aws": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ogenki AI Gateway (aws-0)",
      "options": {
        "baseURL": "https://llm.priv.aws.ogenki.io/v1",
        "apiKey": "{env:OPENAI_API_KEY}"
      },
      "models": {
        "xplane-qwen-coder": { "name": "Qwen Coder 7B" },
        "tier-frontier": { "name": "GLM-5.3 (frontier)" }
      }
    }
  },
  "model": "ogenki-aws/xplane-qwen-coder"
}
```

On GCP, use that cluster's [base URL](#endpoints-per-cloud) and `tier-frontier` or `xplane-qwen3-8b`.
Hand-offs: `maku setup opencode`, then `/maku handoff`, `/maku task` or `/maku inbox` in the session.

## Claude Code {#claude-code}

Models: **not available**. Claude Code speaks the Anthropic Messages API (`/v1/messages`) only
([LLM gateway guide](https://code.claude.com/docs/en/llm-gateway)), while `ai-gateway` serves the
OpenAI API. See the [roadmap]({{< relref "/docs/status.md#serving-roadmap" >}}).

Hand-offs: `maku setup claude`, then `/maku handoff`, `/maku task` or `/maku inbox`.

## Codex CLI {#codex-cli}

Models: **not yet**. Codex requires `wire_api = "responses"`
([config reference](https://learn.chatgpt.com/docs/config-file/config-reference)) and `ai-gateway`
serves chat completions. If `POST /v1/responses` is enabled, configure `~/.codex/config.toml`
([reference](https://learn.chatgpt.com/docs/config-file/config-advanced)):

```toml
model = "tier-frontier"
model_provider = "ogenki"

[model_providers.ogenki]
name = "Ogenki AI Gateway"
base_url = "https://llm.priv.aws.ogenki.io/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
```

Hand-offs: `maku setup codex`.

## Cursor, Gemini CLI and Copilot CLI {#cursor-gemini-cli-and-copilot-cli}

- **Cursor.** No base URL override is documented on the Plus plan. Hand-offs: `maku setup cursor`.
- **Gemini CLI.** No custom endpoint is documented
  ([authentication docs](https://geminicli.com/docs/get-started/authentication/)). Hand-offs:
  `maku setup gemini` (trust the folder first so Gemini CLI connects the stdio MCP server).
- **Copilot CLI.** Generate `~/.copilot/providers.json` from your shell
  ([BYOK docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models)):

```bash
umask 077 && mkdir -p ~/.copilot && jq -n --arg key "$OPENAI_API_KEY" '{
  providers: [{name: "ogenki", type: "openai",
               baseUrl: "https://llm.priv.aws.ogenki.io/v1", apiKey: $key}],
  models: [{id: "xplane-qwen-coder", provider: "ogenki"}]
}' > ~/.copilot/providers.json
copilot --model ogenki/xplane-qwen-coder
```

Hand-offs: `maku setup copilot`.

## VS Code and Continue {#vs-code-and-continue}

In `~/.continue/config.yaml`
([reference](https://docs.continue.dev/reference),
[OpenAI provider](https://docs.continue.dev/customize/model-providers/top-level/openai)):

```yaml
name: Ogenki platform
version: 0.0.1
schema: v1

models:
  - name: Qwen Coder (chat / agentic)
    provider: openai
    model: xplane-qwen-coder
    apiBase: https://llm.priv.aws.ogenki.io/v1
    apiKey: ${{ secrets.OPENAI_API_KEY }}
    roles: [chat, edit, apply]
    defaultCompletionOptions:
      maxTokens: 2048
      temperature: 0.2

  - name: Qwen Coder FIM (autocomplete)
    provider: openai
    model: xplane-qwen-coder-fim
    apiBase: https://llm.priv.aws.ogenki.io/v1
    apiKey: ${{ secrets.OPENAI_API_KEY }}
    useLegacyCompletionsEndpoint: true
    roles: [autocomplete]
    defaultCompletionOptions:
      maxTokens: 256
      temperature: 0.0
```

Continue picks the Qwen FIM template from the `xplane-qwen-coder-fim` name
([source](https://github.com/continuedev/continue/blob/main/core/autocomplete/templating/AutocompleteTemplate.ts)),
and `useLegacyCompletionsEndpoint` calls `/v1/completions`. On GCP there is no FIM model: use the
chat profile with `xplane-qwen3-8b` or `tier-frontier`.

## OpenWebUI {#openwebui}

`https://chat.priv.aws.ogenki.io` (Tailscale, `tag:k8s` ACL) runs on AWS only, in `llm-platform`,
defaulting to `xplane-qwen3-8b`. The Semantic Router rewrites `body.model` only when the client sends
`MoM` (or `auto`) and sets `x-vsr-selected-model` on the response. Scaling:
[Autoscaling & GPUs]({{< relref "/docs/how-it-works/serving/autoscaling-and-gpu.md" >}}).

## Verifying the connection {#verifying-the-connection}

Models, on either cloud:

```bash
BASE=https://llm.priv.gcp.ogenki.io/v1   # or https://llm.priv.aws.ogenki.io/v1

# What the cloud serves
curl -sS "$BASE/models" -H "Authorization: Bearer $OPENAI_API_KEY" | jq '.data[].id'

# Chat completion on a model that needs no GPU
curl -sS "$BASE/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model": "tier-frontier", "messages": [{"role": "user", "content": "Say hi"}]}'

# FIM, aws-0 with llm-platform resumed
curl -sS "$BASE/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model": "xplane-qwen-coder-fim",
       "prompt": "<|fim_prefix|>def fib(n):\n    <|fim_suffix|>\n    return fib(n-1) + fib(n-2)<|fim_middle|>",
       "max_tokens": 50, "temperature": 0.0}'
```

Hand-offs ([user guide]({{< relref "/docs/use/guide/terminal-and-coding-agent.md" >}})): `maku setup <client>`
ends on `maku doctor` with every check `ok`, registers `/maku` (`handoff`, `task`, `inbox`), and exposes
six tools ([inputs and outputs in Maku]({{< maku "docs/cli.md" >}})):

| Tool | What you do with it |
|---|---|
| `handoff` | Describe work in your own words, answer at most one question, and get a stored plan |
| `start` | Confirm the plan's issue, workflow and budget in a form to file and start the task |
| `inbox` | See what is waiting for you across your tasks |
| `task` | See where one task stands, what it needs, what changed, its budget and the gate's decision |
| `wait` | Wait in the background until a task needs you, opens a pull request or ends |
| `answer` | Answer a task's question (and restart it when you maintain the repository) or leave a note for the next run |
