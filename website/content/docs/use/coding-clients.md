---
title: Coding Clients
weight: 30
description: "Connecting a coding client to the platform: the ai-gateway for models and the factory for hand-offs, on AWS and GCP, with each client's current configuration and the failure modes their errors mean."
lastVerified: 2026-10-30
---

A coding client can use the platform in two ways, and they are independent:

| Integration | What it gives you | How you connect |
|---|---|---|
| **Models** through the `ai-gateway` | The platform's models in your client's chat, edits and completions | A base URL and an API key in the client's own config |
| **Hand-offs** to the Agent Factory | File an issue, follow its run and bring its branch back without leaving the session | `maku setup <client>` |

Each snippet is checked against its client's configuration reference, linked next to it, not run
against a live endpoint. [What needs a live run](#verifying-the-connection) is listed at the end of
that section.

## Two integrations, one table

| Client | Models through `ai-gateway` | Factory hand-offs |
|---|---|---|
| [OpenCode](#opencode) | Yes: `opencode.json` provider block | `maku setup opencode` |
| [Claude Code](#claude-code) | No: it speaks the Anthropic Messages API only | `maku setup claude` |
| [Codex CLI](#codex-cli) | Not yet: it speaks only the Responses API | `maku setup codex` |
| [Cursor](#cursor-gemini-cli-and-copilot-cli) | Not verified | `maku setup cursor` |
| [Gemini CLI](#cursor-gemini-cli-and-copilot-cli) | No custom endpoint documented | `maku setup gemini` |
| [Copilot CLI](#cursor-gemini-cli-and-copilot-cli) | Yes: a custom OpenAI-compatible provider | `maku setup copilot` |
| [VS Code + Continue](#vs-code-and-continue) | Yes: chat and FIM | not applicable |
| [OpenWebUI](#openwebui) | Yes: in-cluster, on AWS only | not applicable |

- **Models.** The `ai-gateway` is the platform's gateway for humans and coding clients. It speaks
  the OpenAI chat-completions API. See [Gateways]({{< relref "/docs/how-it-works/gateways.md" >}}).
- **Hand-offs.** The factory takes work from a coding agent through an MCP server that `maku`
  registers. See [Hand off from your coding agent]({{< relref "/docs/use/guide/terminal-and-coding-agent.md#hand-off-from-your-coding-agent" >}}).

## Endpoints per cloud

Both are Tailscale-fronted (`tag:k8s` ACL, see
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
Secret `ai-gateway-api-keys` in `envoy-ai-gateway-system`, which each cloud fills differently.
Read a key into an environment variable and never paste it into a config file.

| | AWS | GCP |
|---|---|---|
| Source | AWS Secrets Manager entry `platform-llm-api-keys` (a JSON object keyed by client identity), seeded once and kept outside OpenTofu | Generated in the cluster by External Secrets `Password` generators, once (`refreshPolicy: CreatedOnce`) |
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

A client shares the identity of the key it uses. To onboard another identity on AWS, add a
property to the Secrets Manager JSON and a matching key to the template in
`infrastructure/base/envoy-ai-gateway/api-keys-externalsecret.yaml`. On GCP, add a `Password`
generator in `infrastructure/gcp-0/envoy-ai-gateway/password-generators.yaml` and a `dataFrom` entry in
`api-keys-patch.yaml`.

The gateway strips `Authorization` before forwarding, so a model server never sees a credential,
and it strips `x-ar-agent`, `x-ar-human` and `x-ai-gateway-client-id` before authenticating, so a
client cannot forge the identity it is charged to. Daily token budgets (5M per key, 10M per human,
20M on frontier spend) are counted in shadow mode: nothing is refused yet
([ADR-0050]({{< relref "/docs/decisions/0050-token-budgets-envoy-gateway-rate-limit.md" >}})).

## Models exposed

`GET /v1/models` lists what a cloud serves. The names a client may use:

| Model ID | Backed by | AWS | GCP | Purpose |
|---|---|---|---|---|
| `tier-frontier` | GLM-5.3 through Z.ai | yes | yes | A frontier model on CPU only; works with `llm-platform` suspended |
| `MoM` | Semantic Router | with `llm-platform` | with `llm-platform` | Classifies the prompt and picks an `xplane-*` model |
| `xplane-qwen-coder` | Qwen2.5-Coder-7B-Instruct | yes | no | Code chat, agentic edits, function calling; 10% canary onto `xplane-qwen-coder-sql-dpo` |
| `xplane-qwen-coder-fim` | Qwen2.5-Coder-1.5B | yes | no | FIM tab completion |
| `xplane-qwen3-8b` | Qwen3-8B | yes | yes | Multilingual, math, longer context (32k) |
| `xplane-llamaguard3-1b` | Llama-Guard-3-1B | yes | no | In no `MoM` rule, reachable only by name |
| `xplane-qwen-coder-sql-dpo`, `xplane-qwen-coder-securecode` | LoRA adapters on `xplane-qwen-coder` | yes | no | Naming one always gets the adapter |

The other `tier-*` aliases (`tier-light`, `tier-standard`) and `agent-default` belong to the agent
gateway: a human client cannot name them here. Pick a specific model when the workload is known:
it skips the 250-300 ms classifier round-trip of `MoM`. How each name is routed and priced:
[Model routing and cost]({{< relref "/docs/how-it-works/routing-and-cost.md" >}}).

## OpenCode

Models. The shape is OpenCode's `provider` block with the OpenAI-compatible package, and the key is
read from the environment. Put it in `~/.config/opencode/opencode.json`, or in an `opencode.json` at
the project root.
(Schema-checked against <https://opencode.ai/docs/providers/>, not run.)

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

On GCP, use that cluster's [base URL](#endpoints-per-cloud) and models `tier-frontier` or
`xplane-qwen3-8b`. A tool call needs a model with function calling: `xplane-qwen-coder` and
`tier-frontier` have it. If a model must be reached through `/v1/responses`, OpenCode wants
`@ai-sdk/openai` instead, and the `ai-gateway` does not serve that path.

Hand-offs: `maku setup opencode`, then `/factory:handoff` in the session.

## Claude Code

Models: **not available**. Claude Code speaks the Anthropic Messages API (`/v1/messages`) and
Anthropic states it does not support routing it to non-Claude models through a gateway
([other LLM gateways](https://code.claude.com/docs/en/llm-gateway),
[compatibility guide](https://code.claude.com/docs/en/llm-gateway-protocol.md)). The `ai-gateway`
serves the OpenAI API only. Claude Code on the self-hosted models is a row of the
[roadmap]({{< relref "/docs/status.md#serving-roadmap" >}}), waiting for a
protocol relay. OpenCode covers the same agentic workflow today.

Hand-offs: `maku setup claude`, then `/mcp__factory__handoff` in the session.

## Codex CLI

Models: **not yet**. Codex's documented provider shape is below, but `responses` is the only
`wire_api` value Codex supports
([config reference](https://learn.chatgpt.com/docs/config-file/config-reference)) and the
`ai-gateway` manifests serve chat completions, not `POST /v1/responses`. Whether the gateway
answers that path has not been probed: until it has, point Codex at the platform only for
hand-offs. If `POST /v1/responses` answers on the gateway, this is the configuration, in
`~/.codex/config.toml`
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

## Cursor, Gemini CLI and Copilot CLI

**Cursor.** Its current pricing and models pages do not document a base URL override, and they
exclude your own API keys from the Plus plan, so this page does not claim one. Hand-offs work:
`maku setup cursor`.

**Gemini CLI.** Its authentication page documents Google sign-in, `GEMINI_API_KEY` and Vertex AI,
and no custom endpoint ([docs](https://geminicli.com/docs/get-started/authentication/)), so models
are not available. Hand-offs: `maku setup gemini`. Gemini CLI connects a local (stdio) MCP server
only in a folder you trust, so trust the folder first.

**Copilot CLI.** A bring-your-own-model provider is documented
([docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models)):
`~/.copilot/providers.json` with a provider of `type: openai` and a model that names it. The file
does not expand environment variables and keeps the key in plain text, so generate it from your
shell, keep it private and never commit it:

```bash
umask 077 && mkdir -p ~/.copilot && jq -n --arg key "$OPENAI_API_KEY" '{
  providers: [{name: "ogenki", type: "openai",
               baseUrl: "https://llm.priv.aws.ogenki.io/v1", apiKey: $key}],
  models: [{id: "xplane-qwen-coder", provider: "ogenki"}]
}' > ~/.copilot/providers.json
copilot --model ogenki/xplane-qwen-coder
```

The `jq` call and the `copilot --model` form are the documented ones; the exact top-level keys of the
file follow the page's description and are the first thing to check on a live run. Hand-offs:
`maku setup copilot`.

## VS Code and Continue

Continue takes a model per role. The chat profile and the FIM profile use different models. Note
that `template: qwen`, which the previous version of this page set, is not a model key in Continue's
reference. The only template key is `autocompleteOptions.template`, a Mustache template, and
without it Continue picks the Qwen FIM template from the model name, and `xplane-qwen-coder-fim`
contains `qwen` and `coder`
([source](https://github.com/continuedev/continue/blob/main/core/autocomplete/templating/AutocompleteTemplate.ts)).

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

`useLegacyCompletionsEndpoint` makes Continue call `/v1/completions`, the FIM path, instead of chat
completions. How Continue resolves `${{ secrets.OPENAI_API_KEY }}` from a local file (a `.env`
file next to the config) is not on the pages read, so confirm it on first use. On GCP there is no
FIM model: use the chat profile with `xplane-qwen3-8b` or `tier-frontier`, and no autocomplete.

## OpenWebUI

`https://chat.priv.aws.ogenki.io` (Tailscale, `tag:k8s` ACL). OpenWebUI runs on AWS only, in
`llm-platform`, and is not wired on GCP. Its default model is `xplane-qwen3-8b`. The Semantic
Router rewrites `body.model` only when the client sent `MoM` (or `auto`): a named model is honoured
as is, and the response header `x-vsr-selected-model` shows what served the request. Scaling is in
[Autoscaling & GPUs]({{< relref "/docs/how-it-works/serving/autoscaling-and-gpu.md" >}}).

## Verifying the connection

Models, on either cloud (set `BASE` to the cloud's base URL; the endpoints are described in
[Gateways]({{< relref "/docs/how-it-works/gateways.md" >}})):

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

Hand-offs (the flow is in the [user guide]({{< relref "/docs/use/guide/terminal-and-coding-agent.md" >}})): `maku doctor` must show every check `ok`, then ask the client to list the factory tools
(`rooms_list`, `room_summary`, `room_changes`, `room_wait`, `room_checkout`, `issue_draft`,
`issue_file`) and prompts (`handoff`, `status`, `inbox`).

**Needs a live run** before the labels can change to `run on CLOUD on DATE`: each snippet above
on both clouds; whether `POST /v1/responses` answers on the `ai-gateway` (decides Codex); the
Copilot `providers.json` keys; Continue's `secrets` resolution and the FIM call; Cursor's base URL
override.

## Troubleshooting

- **`401 Unauthorized`.** The header is missing or matches no key. Check `echo ${OPENAI_API_KEY:+set}`.
  On AWS a changed key takes up to 1 h to reach the cluster (External Secrets refresh); force it with
  `kubectl annotate externalsecret/ai-gateway-api-keys -n envoy-ai-gateway-system force-sync=$(date +%s) --overwrite`.
  On GCP the Secret is generated once and a sync does not change it: read the key again from the
  cluster instead.
- **`404 The model 'X' does not exist`.** The name is not served on that cloud. Check
  `GET /v1/models`: `xplane-qwen-coder*` and the guard model do not exist on GCP, and none of the
  `xplane-*` models exist while `llm-platform` is suspended. For `MoM`, look at the router pod logs
  in the `llm` namespace.
- **`403 Access denied` from Envoy.** A Cilium L7 policy refused it. Either the source lacks an
  egress rule to the AI Gateway data plane or the model's policy does not admit the client; see the
  checklist in [Policies](https://cnref.ogenki.io/docs/platform/security/policies/).
- **Autocomplete is slow (over 1 s).** Continue is calling chat completions instead of FIM. Check
  `roles: [autocomplete]` and `useLegacyCompletionsEndpoint: true`, and on AWS that the Service
  exists: `kubectl get svc -n llm xplane-qwen-coder-fim`.
- **The factory tools are missing in the client.** Run `maku doctor` and fix the first check that
  is not `ok`, then `maku setup <client> --print` to see what would be registered. For Gemini CLI,
  open the client from a trusted folder.
