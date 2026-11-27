---
title: Coding clients
linkTitle: Coding clients
aliases:
  - /docs/use/coding-clients/
  - /docs/platform/ai-platform/coding-clients/
weight: 30
diataxis: how-to
description: "Connect coding clients (OpenCode, Continue, Copilot CLI, OpenWebUI) to ai-gateway for self-hosted and frontier models."
lastVerified: 2026-11-27
---

This page configures coding clients to call **`ai-gateway`** for chat, edits, and FIM autocomplete on this deployment. To hand off background tasks to Maku from your coding agent (`maku setup <client>` and the `/maku` MCP tools), see Maku's [Terminal and coding agent guide]({{< maku "guide/terminal-and-coding-agent/" >}}) and [CLI reference]({{< maku "use/cli/" >}}).

## Support matrix

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

`ai-gateway` speaks the OpenAI chat-completions API; see [AI Gateway]({{< relref "/docs/serving/ai-gateway.md" >}}).

## Endpoints per cloud {#endpoints-per-cloud}

Both endpoints are Tailscale-fronted (`tag:k8s` ACL, see [Private Access](https://cnref.ogenki.io/docs/platform/networking/private-access/)) and serve the OpenAI API under `/v1`. Example (the reference host), one cluster per cloud:

| Cluster | Base URL | Serves |
|---|---|---|
| aws-0 | `https://llm.priv.aws.ogenki.io/v1` | `tier-frontier` always; the four `xplane-*` models and `MoM` once `llm-platform` is resumed |
| gcp-0 | `https://llm.priv.gcp.ogenki.io/v1` | `tier-frontier` (GLM through Z.ai, no GPU needed); `xplane-qwen3-8b` and `MoM` once `llm-platform` is resumed |

`llm-platform` is suspended by default on both clouds; resuming GPU models requires the [opt-in gates]({{< relref "/docs/serving/_index.md#turning-it-on" >}}). `tier-frontier` needs none of them.

## Authentication

Clients send `Authorization: Bearer <key>`. An Envoy Gateway `SecurityPolicy` (`infrastructure/base/envoy-ai-gateway/security-policy.yaml`) compares it with Secret `ai-gateway-api-keys` in `envoy-ai-gateway-system`. Read a key into an environment variable and never paste it into a config file.

| | AWS | GCP |
|---|---|---|
| Source | AWS Secrets Manager entry `platform-llm-api-keys` | Generated in-cluster by External Secrets `Password` generators (`refreshPolicy: CreatedOnce`) |
| Identities | `openwebui_apikey`, `promptfoo_apikey` | `openwebui`, `promptfoo` |

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

To onboard another identity, add a key in `infrastructure/base/envoy-ai-gateway/api-keys-externalsecret.yaml` (AWS) or `infrastructure/gcp-0/envoy-ai-gateway/password-generators.yaml` and `api-keys-patch.yaml` (GCP). Daily token budgets are counted in shadow mode ([ADR-0050]({{< relref "/docs/decisions/0050-token-budgets-envoy-gateway-rate-limit.md" >}})).

## Models exposed

| Model ID | Backed by | AWS | GCP | Purpose |
|---|---|---|---|---|
| `tier-frontier` | GLM through Z.ai | yes | yes | Frontier model on CPU only; works with `llm-platform` suspended |
| `MoM` | Semantic Router | with `llm-platform` | with `llm-platform` | Classifies the prompt and picks an `xplane-*` model |
| `xplane-qwen-coder` | Qwen2.5-Coder-7B-Instruct | yes | no | Code chat, edits, function calling; 10% canary onto `xplane-qwen-coder-sql-dpo` |
| `xplane-qwen-coder-fim` | Qwen2.5-Coder-1.5B | yes | no | FIM tab completion |
| `xplane-qwen3-8b` | Qwen3-8B | yes | yes | Multilingual, math, longer context (32k) |
| `xplane-llamaguard3-1b` | Llama-Guard-3-1B | yes | no | Reachable only by name |
| `xplane-qwen-coder-sql-dpo`, `xplane-qwen-coder-securecode` | LoRA adapters on `xplane-qwen-coder` | yes | no | Naming one always gets the adapter |

## OpenCode {#opencode}

Put the provider block in `~/.config/opencode/opencode.json` or an `opencode.json` at the project root (<https://opencode.ai/docs/providers/>):

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
        "tier-frontier": { "name": "GLM (frontier)" }
      }
    }
  },
  "model": "ogenki-aws/xplane-qwen-coder"
}
```

On GCP, use that cluster's [base URL](#endpoints-per-cloud) and `tier-frontier` or `xplane-qwen3-8b`.

## Claude Code & Codex CLI {#claude-code}

<span id="codex-cli"></span>

- **Claude Code:** speaks the Anthropic Messages API (`/v1/messages`) only, while `ai-gateway` serves the OpenAI API ([Status]({{< relref "/docs/status.md#serving-roadmap" >}})). Maku hand-offs work via `maku setup claude`.
- **Codex CLI:** requires `wire_api = "responses"`, not yet enabled on `ai-gateway`. Maku hand-offs work via `maku setup codex`.

## Cursor, Gemini CLI and Copilot CLI {#cursor-gemini-cli-and-copilot-cli}

- **Cursor / Gemini CLI:** no custom OpenAI base URL override documented; use `maku setup cursor` or `maku setup gemini` for Maku hand-offs.
- **Copilot CLI:** generate `~/.copilot/providers.json` ([BYOK docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models)):

```bash
umask 077 && mkdir -p ~/.copilot && jq -n --arg key "$OPENAI_API_KEY" '{
  providers: [{name: "ogenki", type: "openai",
               baseUrl: "https://llm.priv.aws.ogenki.io/v1", apiKey: $key}],
  models: [{id: "xplane-qwen-coder", provider: "ogenki"}]
}' > ~/.copilot/providers.json
copilot --model ogenki/xplane-qwen-coder
```

## VS Code and Continue {#vs-code-and-continue}

In `~/.continue/config.yaml` ([reference](https://docs.continue.dev/reference)):

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

Continue selects the Qwen FIM template from `xplane-qwen-coder-fim` and calls `/v1/completions`.

## OpenWebUI {#openwebui}

`https://chat.priv.aws.ogenki.io` (Tailscale, `tag:k8s` ACL) runs on AWS in `llm-platform`, defaulting to `xplane-qwen3-8b`. Sending `MoM` lets the Semantic Router choose the model and sets `x-vsr-selected-model` on the response ([Autoscaling & GPUs]({{< relref "/docs/serving/autoscaling-and-gpu.md" >}})).

## Verifying the connection {#verifying-the-connection}

```bash
BASE=https://llm.priv.gcp.ogenki.io/v1   # or https://llm.priv.aws.ogenki.io/v1

curl -sS "$BASE/models" -H "Authorization: Bearer $OPENAI_API_KEY" | jq '.data[].id'

curl -sS "$BASE/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model": "tier-frontier", "messages": [{"role": "user", "content": "Say hi"}]}'
```
